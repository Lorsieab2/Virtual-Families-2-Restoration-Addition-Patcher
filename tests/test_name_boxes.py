"""No screen shortens a stored name just by showing it (the VF1 live-test bug, checked for VF2).

Every game screen with an editable text box (the desktop objects that call ldwTextControl::SetCanEdit) and what it
does with the box's text (static, from the objects' code):

* theVillagerScene (the family member screen): Activate puts the member's name (char[25], up to 24 bytes) into an
  18-byte box with SetText; Done (HandleMessage) and choosing another member (UpdateSelection) copy
  GetText(buf, 13h) - 18 bytes - over the name with strncpy(.., 19h) and CFamilyTree::ChangeName, unless it is empty.
  This is where a longer name would be cut just by viewing it.
* CAdoptionScene / CDatingScene: the box holds a generated candidate's name; accepting copies GetText(buf, 13h) the
  same way (skipping an empty text).
* theChangePlayerDlg / theCreateNickNameDlg: player names, char[20], GetText(.., 14h): a name at the full field
  size (19 bytes) always fits.
* CFamilyTreeInfoDlg: the note, GetText(record + 86h, 50h), the box limit 50h: the game's own notes always fit.
* theAlignVillagerScene: the developers' animation tool, not reachable by a player.

Emulated (unicorn) over an executable built from this repo with the test DLL's plan written in, the game's own
theVillagerScene::Activate, ::HandleMessage (Done) and ::UpdateSelection and ldwTextControlImpl::SetText run for real
(the scene's other calls are seams): a name at the full field size (24 bytes, ASCII and UTF-8, Cuneiform) survives
opening the screen, Done, and switching members; an 18-byte name too; a name the player edits is saved as before; and
without the DLL the stock code does cut the long name (the bug the DLL prevents).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(ROOT / "tests"))
sys.path.append(str(ROOT / "runtime"))
sys.path.append(str(ROOT / "runtime" / "tools"))

import vf2_game_text as T  # noqa: E402
from test_b200_unicode_dll import OBJS, World, dlls, exe  # noqa: E402,F401  (fixtures)

NAME = 0x6A64              # CVillager: char[25] name
NAME_SIZE = 0x19
ID = 0x1BB48               # CVillager: its id
DONE_ID = 0x4242


def _scan_objects():
    """{object: [(function, called symbol, pushed size or None)]} for every ldwTextControl call."""
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from gen_b200_unicode_sites import Coff
    out = {}
    for obj in ("theVillagerScene", "AdoptionScene", "DatingScene", "theChangePlayerDlg", "theCreateNickNameDlg",
                "FamilyTreeInfoDlg"):
        c = Coff(OBJS / f"{obj}.obj")
        rows = []
        for name in c.where:
            data, _mask, calls, _abs = c.function(name)
            wanted = {off: sym for off, sym in calls
                      if "GetText@ldwTextControl" in sym or "SetCanEdit@ldwTextControl" in sym}
            if not wanted:
                continue
            # the size: the second argument, pushed before the first (the push before the last one)
            md = Cs(CS_ARCH_X86, CS_MODE_32)
            md.skipdata = True
            pushed = []
            for ins in md.disasm(data, 0):
                if ins.mnemonic == "push":
                    op = ins.op_str
                    pushed.append(int(op, 16) if op.startswith("0x") else int(op) if op.isdigit() else None)
                if ins.mnemonic == "call" and ins.address + 1 in wanted:
                    rows.append((name, wanted[ins.address + 1].split("@")[0][1:], pushed[-2] if len(pushed) > 1 else None))
                    pushed = []
        out[obj] = rows
    return out


def test_every_name_box_reads_back_what_the_field_holds():
    if not (OBJS / "theVillagerScene.obj").is_file():
        pytest.skip("no desktop objects (work/desktop_obj_files)")
    rows = _scan_objects()
    sizes = {obj: sorted({s for _f, what, s in r if what == "GetText"}) for obj, r in rows.items()}
    assert sizes["theVillagerScene"] == [0x13]            # the 25-byte name read back through 19 bytes
    assert sizes["AdoptionScene"] == [0x13] and sizes["DatingScene"] == [0x13]
    assert sizes["FamilyTreeInfoDlg"] == [0x50]
    edits = {obj: sorted({s for _f, what, s in r if what == "SetCanEdit" and s is not None}) for obj, r in rows.items()}
    assert edits["theVillagerScene"] == [0x12] and edits["FamilyTreeInfoDlg"] == [0x50]


# ---------------------------------------------------------------------------------------------- the real code
def _locate(exe_path: Path, obj: str, func: str):
    """The function's address in the executable and its calls' targets: {symbol: address}."""
    import gen_b200_unicode_sites as G
    x = G.Exe(exe_path)
    data, mask, calls, _abs = G.Coff(OBJS / f"{obj}.obj").function(func)
    hits = G.find(x.code(), data, mask)
    assert len(hits) == 1, (func, len(hits))
    va = hits[0]
    targets = {}
    for off, sym in calls:
        rel = struct.unpack("<i", x.read(va + off, 4))[0]
        targets.setdefault(sym, (va + off + 4 + rel) & 0xFFFFFFFF)
    return va, targets


class SceneWorld:
    def __init__(self, exe_path: Path, dll: Path, with_dll: bool):
        self.w = w = World(exe_path, dll)
        self.e = e = w.e
        status, writes = w.plan(1)
        assert status == 1
        self.h = w.hooks()
        if with_dll:
            for wr in writes:
                e.write(wr["va"], wr["bytes"])
        self.villagers = {}
        self.changed = []
        self.gs = e.alloc(0x26000)
        funcs = {}
        for name in ("?Activate@theVillagerScene@@UAEX_N@Z", "?HandleMessage@theVillagerScene@@UAE_NHJ@Z",
                     "?UpdateSelection@theVillagerScene@@QAEXH@Z"):
            funcs[name], targets = _locate(exe_path, "theVillagerScene", name)
            for sym, at in targets.items():
                self._seam(sym, at)
        self.activate, self.handle, self.update = funcs.values()
        st, targets = _locate(exe_path, "ldwTextControl", "?SetText@ldwTextControlImpl@@QAEXPBD@Z")
        for sym, at in targets.items():
            self._seam(sym, at)
        # the family member screen: +8Ch the member shown, +130h its name box, +E4h the Done button, +8.. the list
        self.scene = e.alloc(0x200)
        e.w32(self.scene + 0xE4, DONE_ID)
        self.impl = e.alloc(0x80)
        e.write(self.impl + 0x24, b"\x01")                 # editable
        e.w32(self.impl + 0x28, 0x12)                      # SetCanEdit(1, 12h)
        ctl = e.alloc(0x20)
        e.w32(ctl + 0x10, self.impl)
        e.w32(self.scene + 0x130, ctl)

    def _seam(self, sym, at):
        e = self.e
        if "SetText@ldwTextControl" in sym or "GetText@ldwTextControl" in sym or "security_check_cookie" in sym \
                or "SetText@ldwTextControlImpl" in sym or sym == "_strncpy":
            return                                          # the game's own (hooked by the DLL's plan when written)
        if "VillagerExists" in sym:
            fn = (lambda em: (1 if em.arg(0) in self.villagers else 0, 8))
        elif "GetVillager@" in sym:
            fn = (lambda em: (self.villagers[em.arg(0)], 4))
        elif "ChangeName" in sym:
            def fn(em):
                self.changed.append(em.read(em.arg(1), 32).split(b"\0")[0])
                return 0, 8
        elif "theGameState" in sym:
            fn = (lambda em: (self.gs, 0))
        elif sym == "??3@YAXPAXI@Z":
            fn = (lambda em: (0, 0))
        elif sym == "??_U@YAPAXI@Z":
            fn = (lambda em: (em.alloc(em.arg(0) + 8), 0))
        elif "Play@CSound" in sym:
            fn = (lambda em: (0, 4))
        else:                                               # PopulateVillagerList, SortVillagers, SetNoFocus
            fn = (lambda em: (0, 0))
        e.seam_live(at, fn)

    def villager(self, vid: int, name: bytes) -> int:
        v = self.e.alloc(0x1BC00)
        self.e.write(v + NAME, name.ljust(NAME_SIZE, b"\0"))
        self.e.w32(v + ID, vid)
        self.villagers[vid] = v
        return v

    def name(self, vid: int) -> bytes:
        return self.e.read(self.villagers[vid] + NAME, NAME_SIZE)

    def show(self, vid: int):
        self.e.w32(self.gs + 0x25CC4, vid)
        self.e.call(self.activate, (1,), ecx=self.scene)

    def done(self):
        self.e.call(self.handle, (8, DONE_ID), ecx=self.scene)

    def pick(self, vid: int):
        self.e.w32(self.scene + 8 + 4 * 3, vid)              # the list's entry 3
        self.e.call(self.update, (3,), ecx=self.scene)

    def key(self, code: int, sym: int):
        self.e.call(self.h["handle_key"], (5, code, sym), ecx=self.impl, edx=0)


LONG_NAMES = [b"Maximilianus Fitzgerald1",                          # 24 bytes: the field's full size
              T.encode("Łukasz Żółć-Kowal"),   # UTF-8, 24 bytes
              T.encode("\U00012000\U00012001\U00012002\U00012003\U00012004\U00012005")]   # Cuneiform, 24 bytes


@pytest.fixture(scope="module")
def worlds(exe, dlls):
    if not (OBJS / "theVillagerScene.obj").is_file():
        pytest.skip("no desktop objects (work/desktop_obj_files)")
    return SceneWorld(exe, dlls[1], True), SceneWorld(exe, dlls[1], False)


@pytest.mark.parametrize("name", LONG_NAMES + [b"Eighteen bytes ok!", T.encode("Zoë")])
def test_viewing_a_member_never_changes_the_name(worlds, name):
    w, _stock = worlds
    assert len(name) <= NAME_SIZE - 1
    stored = name.ljust(NAME_SIZE, b"\0")
    w.villager(1, name)
    w.villager(2, b"Other")
    w.changed.clear()
    w.show(1)
    w.done()
    assert w.name(1) == stored
    w.show(1)
    w.pick(2)                                               # choose another member: the box's text goes back first
    assert w.name(1) == stored and w.name(2) == b"Other".ljust(NAME_SIZE, b"\0")
    w.pick(1)
    w.done()
    assert w.name(1) == stored
    # a name that fits is written back as it is (as the stock game does); a longer one is never touched
    assert all(c == name for c in w.changed) and (len(name) <= 18 or not w.changed)


def test_a_name_the_player_edits_is_saved(worlds):
    w, _stock = worlds
    w.villager(1, b"Maximilianus Fitzgerald1")
    w.show(1)
    for _ in range(7):
        w.key(0, 8)                                         # Backspace x 7: 17 bytes left
    w.key(0x00E9 | 0x40000000, 0)                           # + e-acute (Latin-1, one byte): 18
    w.done()
    assert w.name(1).split(b"\0")[0] == b"Maximilianus Fitz\xe9"


def test_the_stock_code_cuts_a_long_name_by_viewing_it(worlds):
    """Without the DLL: the bug the DLL prevents (the stock GetText cuts at 18 bytes)."""
    _w, stock = worlds
    stock.villager(1, b"Maximilianus Fitzgerald1")
    stock.show(1)
    stock.done()
    assert stock.name(1).split(b"\0")[0] == b"Maximilianus Fitzg"
