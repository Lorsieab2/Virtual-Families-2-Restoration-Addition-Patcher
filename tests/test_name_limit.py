"""Names up to 1,200 bytes in every name box (docs/UNICODE_TEXT.md, "One limit for every name box").

* static: the one limit (vf2_game_text.NAME_BOX_BYTES = 1,200, no character cap) and the DLL's header, which
  runtime/tools/gen_b200_name_limit.py writes from it; the
  ten name boxes in the generated header; the AUDIT of every ldwTextControl::SetCanEdit and ::GetText call in the
  game's desktop objects (which box, its stock limit, where its text is copied); vf2_names' rule;
* under unicorn, the REAL vf2unicode_b200 test DLL over the REAL executable (built from this repo), with the plan's
  writes in place:
  - the long names' group is proved: SetCanEdit, the text box's Draw, the game state's instance and the ten name
    boxes' return addresses are what runtime/tools/gen_b200_unicode_sites.py derives;
  - each of the ten boxes, made by the game's own SetCanEdit called from that box's own call site, takes 1,200
    one-byte characters and refuses the 1,201st, 300 four-byte characters (1,200 bytes) and nothing more, with
    guard bytes after the buffer the game allocates (one past, the byte limit one box holds, and the full 1,200 typed
    from empty in the first family box and the first member box); a SetCanEdit call from anywhere else keeps its stock limit;
  - every GetText copy site runs: the member names' four sites from the GetText call through the strncpy after it
    (the game's own instructions; ChangeName is a seam that records what it is given), the family names' seven
    straight into their fields; with names that fit exactly, one byte past the field, 300 characters, 300 accented
    characters and 1,200 bytes, nothing outside the destination field or the local buffer changes (guard bytes) and
    the destination holds vf2_names.short_form's answer, the Names file the whole name;
  - short forms of names that start alike are unique ("...", "2...") and equal the patcher's; a short form opens
    as the whole name in its box and is given back unchanged; the Names file is read again after a restart; a
    damaged one reads as empty;
  - DrawString and GetWidth draw and measure the whole name for a short form, fitted with an ellipsis into the room
    of as many "W" as the field holds (the patcher's text drawing, src/vf2_game_text.py, gives the same glyphs);
    DrawStringJustified gets it fitted into the short form's own width; a name box too long for its width draws a
    fitted copy (its start, or its end while typed into) and keeps its whole text.
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(ROOT / "tests"))
sys.path.append(str(ROOT / "runtime"))
sys.path.append(str(ROOT / "runtime" / "tools"))

import b200_unicode_sites as S  # noqa: E402
import vf2_game_text as T  # noqa: E402
import vf2_names as N  # noqa: E402
from test_b200_unicode_dll import GAME_IMAGES, NATIVE, OBJS, DrawWorld, dlls, exe  # noqa: E402,F401

CUNEIFORM = "\U00012000"            # four bytes in UTF-8
SAVES = "C:\\Saves\\"

# ---------------------------------------------------------------------------------------------- the audit
# Every ldwTextControl::SetCanEdit and ::GetText call in the game's desktop objects:
# (object, function, call, stock limit or GetText size, what it is / where the text goes, name box?)
AUDIT = (
    ("theChangePlayerDlg", "??0theChangePlayerDlg@@QAE@H@Z", "SetCanEdit", 0x14, "the slot menu's 5 family names", 5),
    ("theChangePlayerDlg", "?HandleMessage@theChangePlayerDlg@@UAE_NHJ@Z", "SetCanEdit", 0x14, "New Player", 1),
    ("theCreateNickNameDlg", "??0theCreateNickNameDlg@@QAE@H@Z", "SetCanEdit", 0x14, "the new family's name", 1),
    ("theVillagerScene", "??0theVillagerScene@@QAE@XZ", "SetCanEdit", 0x12, "a family member's name", 1),
    ("AdoptionScene", "??0CAdoptionScene@@AAE@XZ", "SetCanEdit", 0x12, "adoption", 1),
    ("DatingScene", "??0CDatingScene@@AAE@XZ", "SetCanEdit", 0x12, "dating: the partner", 1),
    ("RedeemCreditDlg", "??0RedeemCreditDlg@@QAE@XZ", "SetCanEdit", 0x14, "not a name (a code): stock", 0),
    ("FamilyTreeInfoDlg", "??0CFamilyTreeInfoDlg@@QAE@PAUSPeepRecord@CFamilyTree@@@Z", "SetCanEdit", 0x50,
     "the Family Tree note: stock", 0),
    ("theAlignVillagerScene", "?HandleMouse@theAlignVillagerScene@@UAE_NHUldwPoint@@@Z", "SetCanEdit", 0x14,
     "the developers' animation tool: stock", 0),
    ("theAlignVillagerScene", "?HandleMouse@theAlignVillagerScene@@UAE_NHUldwPoint@@@Z", "SetCanEdit", 0x1F,
     "the developers' animation tool: stock", 0),
    ("theVillagerScene", "?HandleMessage@theVillagerScene@@UAE_NHJ@Z", "GetText", 0x13,
     "local[20] -> ChangeName, strncpy(member+6A64h, local, 19h)", 1),
    ("theVillagerScene", "?UpdateSelection@theVillagerScene@@QAEXH@Z", "GetText", 0x13,
     "local[20] -> ChangeName, strncpy(member+6A64h, local, 19h)", 1),
    ("AdoptionScene", "?HandleMessage@CAdoptionScene@@UAE_NHJ@Z", "GetText", 0x13,
     "local[20] -> strncpy(member+6A64h, local, 19h)", 1),
    ("DatingScene", "?HandleMessage@CDatingScene@@UAE_NHJ@Z", "GetText", 0x13,
     "local[20] -> strncpy(member+6A64h, local, 19h)", 1),
    ("theCreateNickNameDlg", "?HandleMessage@theCreateNickNameDlg@@UAE_NHJ@Z", "GetText", 0x14,
     "gs+25ABCh (20-byte field)", 1),
    ("theChangePlayerDlg", "?HandleMessage@theChangePlayerDlg@@UAE_NHJ@Z", "GetText", 0x14,
     "gs+25B30h + 15h x k (5 x 21-byte fields) and local[20] (compared with \"New Player\")", 6),
    ("RedeemCreditDlg", "?GetName@RedeemCreditDlg@@QAEPADXZ", "GetText", 0x14, "this+64h: not a name box", 1),
    ("FamilyTreeInfoDlg", "?HandleMessage@CFamilyTreeInfoDlg@@UAE_NHJ@Z", "GetText", 0x50,
     "record+86h (the note, 80 bytes): not a name box", 1),
    ("theAlignVillagerScene", "?HandleMessage@theAlignVillagerScene@@UAE_NHJ@Z", "GetText", 0x1F,
     "the developers' tool: not a name box", 1),
    ("DayNightCycleTestDlg", "?HandleMessage@CDayNightCycleTestDlg@@UAE_NHJ@Z", "GetText", 0x64,
     "the developers' test dialog: not a name box", 1),
)


def _calls_in_objects():
    """{(object, function, call): [immediate size or limit per call]} for every SetCanEdit / GetText call."""
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from gen_b200_unicode_sites import Coff
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.skipdata = True
    out = {}
    for path in sorted(OBJS.glob("*.obj")):
        try:
            c = Coff(path)
        except Exception:                       # noqa: BLE001  (not an x86 object)
            continue
        for name in c.where:
            try:
                data, _m, calls, _a = c.function(name)
            except Exception:                   # noqa: BLE001
                continue
            wanted = {off: sym for off, sym in calls
                      if sym in ("?GetText@ldwTextControl@@QAEXPADH@Z", S.SET_CAN_EDIT)}
            if not wanted:
                continue
            imms = []
            for ins in md.disasm(data, 0):
                if ins.mnemonic == "push" and re.fullmatch(r"0x[0-9a-f]+|\d+", ins.op_str):
                    imms.append(int(ins.op_str, 0))
                if ins.mnemonic == "call" and ins.address + 1 in wanted:
                    what = "GetText" if "GetText" in wanted[ins.address + 1] else "SetCanEdit"
                    size = imms[-1] if what == "GetText" else imms[-2]
                    out.setdefault((path.stem, name, what), []).append(size)
    return out


def test_every_text_box_call_is_audited():
    if not (OBJS / "theVillagerScene.obj").is_file():
        pytest.skip("no desktop objects (work/desktop_obj_files)")
    pytest.importorskip("capstone")
    found = _calls_in_objects()
    expected = {}
    for obj, func, what, size, _where, count in AUDIT:
        expected.setdefault((obj, func, what), []).extend([size] * max(count, 1))
    assert {k: sorted(v) for k, v in found.items()} == {k: sorted(v) for k, v in expected.items()}


def test_the_ten_name_boxes_are_in_the_header():
    header = (NATIVE / "b200unicode_sites.h").read_text(encoding="utf-8")
    assert "#define UNI_NAME_BOX_COUNT 10u" in header
    kinds = re.findall(r"\{ \d+, '([FM])', 0x[0-9A-F]+u \},", header)
    assert "".join(kinds) == "FFFFFFFMMM"
    assert sum(count for _p, _k, count in S.NAME_BOXES) == 10
    assert sum(a[5] for a in AUDIT if a[2] == "SetCanEdit") == 10


def test_one_limit_in_one_place():
    """The one C copy of the limit (b200name_limit.h) is what runtime/tools/gen_b200_name_limit.py writes from the
    Python definition; no other native source or Python module writes the numbers, and nothing caps characters;
    every DLL that needs the limit includes the header."""
    import gen_b200_name_limit as G
    assert not hasattr(T, "NAME_LETTERS")
    assert T.NAME_BOX_BYTES == 1200 == T.TEXT_BOX_CEILING_BYTES
    header = (NATIVE / "b200name_limit.h").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert header == G.render()
    assert re.search(r"^static const unsigned kNameBoxBytes = %d;" % T.NAME_BOX_BYTES, header, re.M)
    assert "kNameLetters" not in header
    for path in list(NATIVE.glob("*")) + list((ROOT / "runtime" / "native" / "b200history").glob("*.cpp")):
        if path.name != "b200name_limit.h" and path.is_file():
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"kName(Letters|BoxBytes)\s*=\s*\d", text), path.name
            assert "kNameLetters" not in text and "NameLettersOk" not in text, path.name
    assert '#include "b200name_limit.h"' in (NATIVE / "b200unicode.cpp").read_text(encoding="utf-8")
    assert '#include "b200name_limit.h"' in (ROOT / "runtime" / "native" / "b200history" / "b200history.cpp").read_text(
        encoding="utf-8")
    for path in (ROOT / "src").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bNAME_LETTERS\b", text), path.name


# ---------------------------------------------------------------------------------------------- the rule
def test_short_forms():
    assert N.short_form("Maximilianus Fitzgerald", 18, {}) == "Maximilianus Fi..."
    taken = {"Maximilianus Fi...": "Maximilianus Fitzgerald"}
    assert N.short_form("Maximilianus Fitzgerald", 18, taken) == "Maximilianus Fi..."    # its own again
    assert N.short_form("Maximilianus Fitzroy", 18, taken) == "Maximilianus F2..."
    assert N.short_form("Eighteen bytes ok!", 18, {}) == "Eighteen bytes ok!"           # fits: as it is
    assert N.short_form("Maximilianus Fi...", 18, taken) == "Maximilianus F2..."         # no other's short form
    assert N.short_form("Ab    Cdefghijklmnopqrs", 8, {}) == "Ab..."                      # trailing spaces dropped
    s = N.short_form("Ł" * 300, 18, {})
    assert s == "Ł" * 7 + "..." and N.size(s) <= 18
    assert N.name_problem("a" * 1200) is None and N.name_problem("a" * 1201)          # bytes, no character cap
    assert N.name_problem("é" * 1200) is None and N.name_problem("é" * 1201)
    assert N.name_problem(CUNEIFORM * 300) is None and N.name_problem(CUNEIFORM * 301) and N.name_problem("a\tb")


def test_old_short_form_logs_still_read_back_as_whole_names(tmp_path):
    """A Family History log written before vf2history_b200.dll logged whole names holds short forms: the reader
    (vf2_family_history.whole_names, which the Family Tree Maker runs) still expands them from the Names file; a
    log of whole names reads the same, and a name the file does not hold stays as it is."""
    import vf2_family_history as FH
    whole, other = "Maximilianus Fitzgerald the Third", "Ł" * 300
    short = N.short_form(whole, N.MEMBER_ROOM, {})
    short_other = N.short_form(other, N.MEMBER_ROOM, {short: whole})
    N.write(N.names_path(tmp_path, 2), [N.Entry(short, N.MEMBER_ROOM, whole), N.Entry(short_other, N.MEMBER_ROOM, other)])
    folder = tmp_path / "Virtual Families 2 Patcher" / "Save 2" / "Logs" / "Family History"
    folder.mkdir(parents=True)

    def record(head, spouse):
        return FH.log_bytes("[2026-10-25 21:07:05] Marriage 1\n  Family member: " + head + "\n    Age: 25\n    Sex: Female\n"
                            "    Head: 3\n    Body: 4\n  Married: " + spouse + "\n    Age: 26\n    Sex: Male\n"
                            "    Head: 3\n    Body: 4\n  Current spouse of " + head + ": " + spouse + "\n  Generation: 1\n\n")
    old = b"Family: Ana (Save 2)\r\n" + record(short, "Unknown...").replace(b"\n", b"\r\n") + \
        record(short_other, "Bob").replace(b"\n", b"\r\n")
    (folder / "Family History 1.txt").write_bytes(old)
    h = FH.read(tmp_path, 2)
    assert [(m.head, m.spouse) for m in h.marriages] == [(short, "Unknown..."), (short_other, "Bob")]
    FH.whole_names(h, N.Book(tmp_path), 2)
    assert [(m.head, m.spouse) for m in h.marriages] == [(whole, "Unknown..."), (other, "Bob")]
    new = b"Family: Ana (Save 2)\r\n" + record(whole, "Unknown...").replace(b"\n", b"\r\n") + \
        record(other, "Bob").replace(b"\n", b"\r\n")                           # as the DLL writes it now
    (folder / "Family History 1.txt").write_bytes(new)
    h2 = FH.read(tmp_path, 2)
    FH.whole_names(h2, N.Book(tmp_path), 2)
    assert h2.marriages == h.marriages


def test_names_file_round_trip(tmp_path):
    entries = [N.Entry("Maximilianus Fi...", 18, "Maximilianus Fitzgerald"), N.Entry("Łukasz...", 19, "Ł" * 300)]
    N.write(N.names_path(tmp_path, 2), entries)
    assert N.read_slot(tmp_path, 2) == entries
    book = N.Book(tmp_path)
    assert book.full(2, "Maximilianus Fi...") == "Maximilianus Fitzgerald" and book.full(1, "Łukasz...") == "Ł" * 300
    N.names_path(tmp_path, 3).write_bytes(b"\xff\xfe damaged")
    assert N.read_slot(tmp_path, 3) == []
    bad = ("\n".join([N.HEADER] + [N.record_line(N.Entry(e.short, 1 if e.room == 18 else e.room, e.full))
                                   for e in entries]) + "\n").encode("utf-8")     # signed, but too long for its room
    assert N.parse(bad) == entries[1:]


def test_names_file_version_2_has_a_crc_and_version_1_is_still_read():
    """"VF2 Names 2": short, room, whole name, then the CRC-32 (zlib) of every byte before the last tab, 8 upper-case
    hex digits. A record with a wrong checksum, cut short or merged with another is skipped; "VF2 Names 1" has no
    checksum column and is still read."""
    import zlib
    assert N.HEADER == "VF2 Names 2" and N.HEADER_V1 == "VF2 Names 1"
    assert N.crc_of("abc") == "%08X" % zlib.crc32(b"abc") == "352441C2"
    a, b, c = (N.Entry("Maximilianus Fi...", 18, "Maximilianus Fitzgerald"), N.Entry("Åukasz...", 19, "Å" * 40),
               N.Entry("日本...", 19, "日本語のなまえ" * 4))
    data = N.render([a, b, c])
    lines = data.decode("utf-8").split("\n")
    assert lines[0] == "VF2 Names 2" and lines[-1] == "" and len(lines) == 5
    for line, e in zip(lines[1:], (a, b, c)):
        body, _tab, crc = line.rpartition("\t")
        assert body == f"{e.short}\t{e.room}\t{e.full}" and crc == "%08X" % zlib.crc32(body.encode("utf-8"))
        assert crc == crc.upper() and len(crc) == 8
    assert N.parse(data) == [a, b, c]
    # a wrong checksum, a cut record (no checksum, or a short one), two records merged into one line
    wrong = lines[2].rpartition("\t")[0] + "\t" + "0" * 8
    cut = lines[2][:-3]
    nocrc = lines[2].rpartition("\t")[0]
    merged = lines[1] + lines[3]
    for bad in (wrong, cut, nocrc, merged):
        got = N.parse("\n".join([lines[0], lines[1], bad, lines[3], ""]).encode("utf-8"))
        assert got == [a, c], bad
    assert N.parse("\n".join([lines[0], lines[1], lines[2], lines[3][:-1]]).encode("utf-8")) == [a, b]
    # a lower-case checksum is the same number
    low = lines[1].rpartition("\t")[0] + "\t" + lines[1].rpartition("\t")[2].lower()
    assert N.parse("\n".join([lines[0], low, ""]).encode("utf-8")) == [a]
    # version 1: three columns, no checksum; a version 1 line in a version 2 file has no checksum: skipped
    v1 = ("VF2 Names 1\n" + "\n".join(f"{e.short}\t{e.room}\t{e.full}" for e in (a, b, c)) + "\n").encode("utf-8")
    assert N.parse(v1) == [a, b, c]
    assert N.parse(b"VF2 Names 3\n") == [] and N.parse(b"") == []


# ---------------------------------------------------------------------------------------------- emulation
def _locate(exe_path: Path, obj: str, func: str):
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


def _locate_range(exe_path: Path, obj: str, func: str, start: int, end: int) -> int:
    """Where the function's bytes [start, end) are in the executable (exactly once): the run starts there. A matrix
    build can change other parts of a scene's function (CDatingScene::HandleMessage is not the stock one), so the
    copy site is found by its own instructions, relocated fields masked."""
    import gen_b200_unicode_sites as G
    x = G.Exe(exe_path)
    data, mask, _calls, _abs = G.Coff(OBJS / f"{obj}.obj").function(func)
    hits = G.find(x.code(), data[start:end], mask[start:end])
    assert len(hits) == 1, (func, hex(start), len(hits))
    return hits[0] - start


def test_the_executable_calls_settext_and_gettext_only_from_the_audited_sites(exe):
    """Every call in the executable's code to ldwTextControl::GetText and ::SetCanEdit (a rel32 call whose target is
    the function) is one of the AUDIT's calls, found by its own instructions (the 12 bytes before the call, relocated
    fields masked): no build-added code copies a box's text unaudited. (The core executable links 14 of the 15
    audited GetText calls: one developers' dialog is not linked.)"""
    if not (OBJS / "ldwTextControl.obj").is_file():
        pytest.skip("no desktop objects (work/desktop_obj_files)")
    import gen_b200_unicode_sites as G
    x = G.Exe(exe)
    get_text = G.resolve(x, G.load_pins(OBJS))["sites"]["GET_TEXT"]
    set_can_edit = G.resolve_names(x, G.load_name_pins(OBJS))["sites"]["SET_CAN_EDIT"]
    calls = {get_text: set(), set_can_edit: set()}
    for _n, va, raw, _c in x.code():
        for m in re.finditer(rb"\xE8", raw):
            k = m.start()
            if k + 5 <= len(raw):
                target = (va + k + 5 + struct.unpack_from("<i", raw, k + 1)[0]) & 0xFFFFFFFF
                if target in calls:
                    calls[target].add(va + k)
    audited = set()
    for obj, func, _what, _s, _w, _count in AUDIT:
        data, mask, fcalls, _abs = G.Coff(OBJS / f"{obj}.obj").function(func)
        for off, sym in fcalls:
            if sym in ("?GetText@ldwTextControl@@QAEXPADH@Z", S.SET_CAN_EDIT):
                lo = max(0, off - 13)
                hits = G.find(x.code(), data[lo:off + 4], mask[lo:off + 4])
                audited |= {h + (off - 1 - lo) for h in hits}
    found = calls[get_text] | calls[set_can_edit]
    assert found and found <= audited, sorted(hex(a) for a in found - audited)
    assert len(calls[set_can_edit]) == sum(max(a[5], 1) for a in AUDIT if a[2] == "SetCanEdit")


class NamesWorld(DrawWorld):
    """DrawWorld (the fonts, SDL and files seams) with the plan's writes in place, a game state whose save files
    are C:\\Saves\\Virtual Families 2<N>.ldw, and the DLL's ANSI file calls over an in-memory folder."""

    def __init__(self, exe_path, dll, glyph_dir):
        super().__init__(exe_path, dll, glyph_dir)
        e = self.e
        # a game font's baseline row is measured with GDI (Segoe UI's ascent) the first time the font is drawn
        from test_unicode_font import RealGdi
        self.real_gdi = RealGdi(e, {})
        import gen_b200_unicode_sites as G
        self.exe_path = exe_path
        _status, writes = self.plan(1)
        for wr in writes:
            e.write(wr["va"], wr["bytes"])
        self.writes = writes
        self.game_seams(self.s)
        self.tick = 100000                              # GetTickCount (the pending Names records retry every 2 s)
        self.fail_write = False                         # CreateFileA for writing fails (a Names file that cannot be written)
        e.imports["GetTickCount"] = lambda em: (self.tick, 0)
        out = e.alloc(4 * 32)
        e.call(e.dll_export("B200Unicode_TestNames"), (out,))
        self.names_on = e.r32(out)
        sites = [e.r32(out + 4 * (1 + i)) for i in range(6)]
        self.set_can_edit, self.box_draw, self.instance, self.gs_save, self.window_get, self.window_font = sites
        self.returns = [e.r32(out + 28 + 4 * i) for i in range(10)]
        self.proved = G.resolve_names(G.Exe(exe_path), G.load_name_pins(OBJS))
        # the game state
        self.gs = e.alloc(0x26000, fill=0xCD)
        e.w32(self.gs + S.GS_CURRENT_SLOT, 1)
        vt = e.alloc(0x40)
        make_path = e.alloc(16)
        self.paths = {}
        for slot in range(0, 6):
            p = e.alloc(64)
            e.write(p, f"{SAVES}Virtual Families 2{slot}.ldw".encode() + b"\0")
            self.paths[slot] = p
        e.seam_live(make_path, lambda em: (self.paths[em.arg(0)], 4))
        e.w32(vt + S.GAME_STATE_PATH_VSLOT, make_path)
        e.w32(self.gs, vt)
        e.w32(self.instance, self.gs)
        # the folder
        self.fs: dict[str, bytes] = {}
        self.writing: dict[int, list] = {}
        e.imports.update({
            "CreateFileA": self._open_a, "WriteFile": self._write_file, "FlushFileBuffers": lambda em: (1, 4),
            "MoveFileExA": self._move, "DeleteFileA": self._delete, "CreateDirectoryA": lambda em: (1, 8),
            "CloseHandle": self._close,
        })
        # SetCanEdit's allocator and free: the game's operator new[] (with guard bytes after) and delete
        _va, targets = _locate(exe_path, "ldwTextControl", S.SET_CAN_EDIT)
        self.buffers = []

        def new(em):
            n = em.arg(0)
            p = em.alloc(n + 32)
            em.write(p + n, b"\xAB" * 32)
            self.buffers.append((p, n))
            return p, 0
        e.seam_live(targets["??_U@YAPAXI@Z"], new)
        e.seam_live(targets["??3@YAXPAXI@Z"], lambda em: (0, 0))
        self.owner = e.alloc(0x20)
        e.write(self.owner + 8, b"\x01")

    # ---- files (ANSI)
    def _open_a(self, em):
        path, access = em.cstr(em.arg(0)), em.arg(1)
        handle = 0x900 + len(self.files) + len(self.writing)
        if access & 0x40000000:                       # GENERIC_WRITE
            if self.fail_write:
                return 0xFFFFFFFF, 28
            self.writing[handle] = [path, b""]
            return handle, 28
        if path not in self.fs:
            return 0xFFFFFFFF, 28
        self.files[handle] = self.fs[path]
        return handle, 28

    def _write_file(self, em):
        self.writing[em.arg(0)][1] += em.read(em.arg(1), em.arg(2))
        em.w32(em.arg(3), em.arg(2))
        return 1, 20

    def _close(self, em):
        h = em.arg(0)
        if h in self.writing:
            path, data = self.writing.pop(h)
            self.fs[path] = data
        return 1, 4

    def _move(self, em):
        a, b = em.cstr(em.arg(0)), em.cstr(em.arg(1))
        self.fs[b] = self.fs.pop(a)
        return 1, 12

    def _delete(self, em):
        self.fs.pop(em.cstr(em.arg(0)), None)
        return 1, 4

    def names_file(self, slot: int) -> list:
        data = self.fs.get(f"{SAVES}Virtual Families 2 Patcher Data\\Names\\Virtual Families 2{slot}.ldw.txt")
        return N.parse(data) if data is not None else []

    def forget(self):
        self.e.call(self.e.dll_export("B200Unicode_TestForgetNames"))

    # ---- a text box, made a name box (or not) by the game's own SetCanEdit called from `ret`
    def box(self, ret: int, stock_limit: int, font: int = 0):
        e = self.e
        impl = e.alloc(0x80)
        e.write(impl + 0x24, b"\x00\x01")             # not yet editable; +25h the cursor (being typed into)
        e.w32(impl + 0x1C, self.owner)
        e.w32(impl + 0x3C, font)
        ctl = e.alloc(0x20)
        e.w32(ctl + 0x10, impl)
        e.w32(ctl + 4, 77)
        esp = e.sp_top - 0x200
        e.run_frame(self.set_can_edit, {"esp": esp, "ecx": ctl},
                    [(esp, ret), (esp + 4, 1), (esp + 8, stock_limit), (esp + 12, 0x70001000)])
        return ctl, impl

    def type(self, impl, text):
        for ch in text:
            self.e.call(self.h["handle_key"], (5, ord(ch) | S.KEY_MARK, 0), ecx=impl, edx=0)

    def text(self, impl) -> bytes:
        return self.e.cstr(self.e.r32(impl + 0x30)).encode("latin-1")

    def set_text(self, impl, raw: bytes):
        p = self.e.alloc(len(raw) + 1)
        self.e.write(p, raw + b"\0")
        self.e.call(self.h["set_text"], (p,), ecx=impl, edx=0)


def _patch_run_frame():
    """Emu.run_frame takes unicorn register ids; NamesWorld passes names."""
    from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP
    return {"esp": UC_X86_REG_ESP, "ecx": UC_X86_REG_ECX}


@pytest.fixture(scope="module")
def world(exe, dlls, tmp_path_factory):
    if not (OBJS / "theVillagerScene.obj").is_file():
        pytest.skip("no desktop objects (work/desktop_obj_files)")
    if not (GAME_IMAGES / "Segoe24.png").is_file():
        pytest.skip("no original game folder (work/vanilla_runtime_payload)")
    import vf2_glyph_maker as M
    folder = tmp_path_factory.mktemp("names")
    M.write_sheets(GAME_IMAGES, folder)
    w = NamesWorld(exe, dlls[1], folder)
    regs = _patch_run_frame()
    real = w.e.run_frame
    w.e.run_frame = lambda start, r, stack: real(start, {regs[k]: v for k, v in r.items()}, stack)
    for ret in w.returns:                                         # a name box's SetCanEdit returns here: stop
        w.e.seam_live(ret, lambda em: (None, 0))
    return w, M.load_fonts(GAME_IMAGES)


def test_the_long_names_are_proved(world):
    w, _fonts = world
    assert w.names_on == 1
    assert w.set_can_edit == w.proved["sites"]["SET_CAN_EDIT"]
    assert w.box_draw == w.proved["sites"]["BOX_DRAW"]
    assert w.instance == w.proved["sites"]["GAME_STATE_INSTANCE"]
    assert w.gs_save == w.proved["sites"]["GS_SAVE"] == w.e.exe.get_dword_at_rva(w.proved["gs_vtable"] + S.GS_SAVE_VSLOT - w.e.base)
    assert w.returns == [at for _kind, at in w.proved["boxes"]]


BOXES = [(i, kind, limit) for i, (kind, limit) in enumerate(
    [("F", 0x14)] * 7 + [("M", 0x12)] * 3)]


@pytest.mark.parametrize("index,kind,stock", BOXES)
def test_each_name_box_takes_1200_bytes(world, index, kind, stock):
    """No character cap: the bytes as stored are the only limit. Every box is filled with set_text to just under
    the limit and typed into past it (the whole 1,200 typed from empty is tested in the first box of each kind)."""
    w, _fonts = world
    ret = w.returns[index]
    _ctl, impl = w.box(ret, stock)
    assert w.e.r32(impl + 0x28) == T.NAME_BOX_BYTES
    buf, size = w.buffers[-1]
    assert size == T.NAME_BOX_BYTES + 1

    def fresh(raw):
        _c, i = w.box(ret, stock)
        b, s = w.buffers[-1]
        w.set_text(i, raw)
        assert w.text(i) == raw
        return i, b, s
    impl, buf, size = fresh(b"a" * 1190)
    w.type(impl, "é" * 20)                                        # one byte each: 10 go in, the 11th is refused
    assert w.text(impl) == b"a" * 1190 + b"\xe9" * 10 and len(w.text(impl)) == 1200
    w.type(impl, "a")                                             # the box's bytes are full
    assert len(w.text(impl)) == 1200
    assert w.e.read(buf + size, 32) == b"\xAB" * 32
    impl, buf, size = fresh(b"a" * 1196)
    w.type(impl, CUNEIFORM * 2)                                   # four bytes: one goes in, the next is refused
    assert w.text(impl) == b"a" * 1196 + CUNEIFORM.encode("utf-8")
    w.type(impl, "b")
    assert len(w.text(impl)) == 1200
    assert w.e.read(buf + size, 32) == b"\xAB" * 32
    family = "\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466"     # 25 bytes, one character
    impl, buf, size = fresh(b"a" * 1175)
    w.type(impl, family * 2)                                      # 25 bytes left: one family, the next is refused
    assert w.text(impl) == b"a" * 1175 + family.encode("utf-8") and len(w.text(impl)) == 1200
    assert w.e.read(buf + size, 32) == b"\xAB" * 32
    if index in (0, 7):                                           # typed from empty, all 1,200
        _c, impl = w.box(ret, stock)
        buf, size = w.buffers[-1]
        w.type(impl, "é" * 1201)
        assert w.text(impl) == T.encode("é" * 1200) and T.length(T.decode(w.text(impl))) == 1200
        assert w.e.read(buf + size, 32) == b"\xAB" * 32
        _c, impl = w.box(ret, stock)
        w.type(impl, "a" * 1201)
        assert w.text(impl) == b"a" * 1200
        _c, impl = w.box(ret, stock)
        w.type(impl, CUNEIFORM * 301)
        assert w.text(impl) == T.encode(CUNEIFORM * 300) and len(w.text(impl)) == 1200
        _c, impl = w.box(ret, stock)
        w.type(impl, "e\u0301" * 401)                              # a letter and its mark: one character, 3 bytes
        assert T.length(T.decode(w.text(impl))) == 400 and len(w.text(impl)) == 1200


def test_another_box_keeps_its_stock_limit(world):
    w, _fonts = world
    other = w.returns[0] + 0x10                                   # not a name box's call
    w.e.seam_live(other, lambda em: (None, 0))
    _ctl, impl = w.box(other, 0x14)
    assert w.e.r32(impl + 0x28) == 0x14
    assert w.buffers[-1][1] == 0x15


# ---- every GetText copy site
MEMBER_SITES = (
    # object, function, start, end, how the frame is set up
    ("theVillagerScene", "?HandleMessage@theVillagerScene@@UAE_NHJ@Z", 0x65, 0x9C, "villager"),
    ("theVillagerScene", "?UpdateSelection@theVillagerScene@@QAEXH@Z", 0x40, 0x77, "villager"),
    ("AdoptionScene", "?HandleMessage@CAdoptionScene@@UAE_NHJ@Z", 0x9C, 0xC3, "adoption"),
    ("DatingScene", "?HandleMessage@CDatingScene@@UAE_NHJ@Z", 0x115, 0x142, "dating"),
)
NAMES = ["Eighteen bytes ok!", "Nineteen bytes ok!!", "A" * 300, "é" * 300, CUNEIFORM * 300,
         "Maximilianus Fitzgerald the Third"]


def _typed_box(w, kind_index, text):
    _ctl, impl = w.box(w.returns[kind_index], 0x12 if kind_index >= 7 else 0x14)
    ctl = _ctl
    w.type(impl, text)
    assert T.decode(w.text(impl)) == text
    return ctl, impl


@pytest.mark.parametrize("site", MEMBER_SITES, ids=lambda s: s[1].split("@")[0][1:] + "@" + s[0])
@pytest.mark.parametrize("name", NAMES, ids=range(len(NAMES)))
def test_member_name_sites_never_overrun(world, site, name):
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
                                   UC_X86_REG_ESP)
    w, _fonts = world
    e = w.e
    obj, func, start, end, how = site
    va = _locate_range(w.exe_path, obj, func, start, end)
    targets = _locate(w.exe_path, obj, func)[1] if obj == "theVillagerScene" else {}
    assert e.read(va + start, 1)[0] in (0x8B, 0x8D, 0x6A)          # the instruction the run starts at
    for sym, at in targets.items():
        if "ChangeName" in sym:
            if not hasattr(w, "changed"):
                w.changed = []
                e.seam_live(at, lambda em: (w.changed.append(em.read(em.arg(1), 32).split(b"\0")[0]) or 0, 8))
    if (va + end) not in getattr(w, "ends", set()):
        w.ends = getattr(w, "ends", set()) | {va + end}
        e.seam_live(va + end, lambda em: (None, 0))
    w.forget()
    w.fs.clear()
    ctl, _impl = _typed_box(w, 7, name)
    villager = e.alloc(0x1BC00, fill=0xCD)
    before_v = e.read(villager + 0x6A00, 0x200)
    ebp = e.sp_top - 0x400
    esp = ebp - 0x100
    e.write(ebp - 0x80, b"\xCD" * 0xA0)
    scene = e.alloc(0x100)
    e.w32(scene + 0x60, ctl)
    regs = {UC_X86_REG_EBP: ebp, UC_X86_REG_ESP: esp, UC_X86_REG_ECX: ctl, UC_X86_REG_EAX: villager}
    stack = [(esp, 0x70001000)]
    if how == "adoption":
        regs.update({UC_X86_REG_EDI: scene, UC_X86_REG_EBX: villager})
        stack = [(esp, 0x13), (esp + 4, 0x70001000)]
    if how == "dating":
        stack.append((ebp - 0x24, villager))
        stack.append((ebp - 0x20, villager))                    # the code keeps edi (= eax) there
    for addr, v in stack:
        e.w32(addr, v)
    before_frame = e.read(ebp - 0x80, 0xA0)
    for reg, v in regs.items():
        e.setreg(reg, v)
    e._run(va + start)
    expected = N.short_form(name, N.MEMBER_ROOM, {})
    field = e.read(villager + 0x6A64, 0x19)
    assert field == T.encode(expected).ljust(0x19, b"\0")
    after_v = e.read(villager + 0x6A00, 0x200)
    assert after_v[:0x64] == before_v[:0x64] and after_v[0x64 + 0x19:] == before_v[0x64 + 0x19:]
    frame = e.read(ebp - 0x80, 0xA0)
    local = 0x80 - 0x18
    assert frame[:local] == before_frame[:local] and frame[local + 0x13:] == before_frame[local + 0x13:]
    entries = w.names_file(1)
    assert entries == ([] if expected == name else [N.Entry(expected, N.MEMBER_ROOM, name)])


FAMILY_DESTS = [("player", k) for k in range(5)] + [("nickname", 0), ("local", 0)]


@pytest.mark.parametrize("dest", FAMILY_DESTS, ids=[f"{a}{b}" for a, b in FAMILY_DESTS])
@pytest.mark.parametrize("name", NAMES, ids=range(len(NAMES)))
def test_family_name_sites_never_overrun(world, dest, name):
    w, _fonts = world
    e = w.e
    w.forget()
    w.fs.clear()
    ctl, _impl = _typed_box(w, 0, name)
    where, k = dest
    region = (w.gs + S.GS_NICKNAME - 0x20, 0x120)
    if where == "player":
        dst, slot = w.gs + S.GS_PLAYER_NAMES + S.GS_PLAYER_STRIDE * k, k + 1
    elif where == "nickname":
        dst, slot = w.gs + S.GS_NICKNAME, 4
    else:
        dst, slot = e.alloc(0x60, fill=0xCD) + 0x20, None
        region = (dst - 0x20, 0x60)
    e.write(region[0], b"\xCD" * region[1])
    e.w32(w.gs + S.GS_CURRENT_SLOT, 4)
    before = e.read(region[0], region[1])
    e.call(w.s["GET_TEXT"], (dst, 0x14), ecx=ctl)                  # the game's call: GetText(field, 14h)
    expected = N.short_form(name, N.FAMILY_ROOM, {})
    assert e.read(dst, 0x14) == T.encode(expected).ljust(0x14, b"\0")
    after = e.read(region[0], region[1])
    off = dst - region[0]
    assert after[:off] == before[:off] and after[off + 0x14:] == before[off + 0x14:]
    want = [] if expected == name or slot is None else [N.Entry(expected, N.FAMILY_ROOM, name)]
    assert w.names_file(slot or 1) == want and (slot is not None or not w.fs)
    e.w32(w.gs + S.GS_CURRENT_SLOT, 1)


def test_names_that_start_alike_are_unique(world):
    w, _fonts = world
    e = w.e
    w.forget()
    w.fs.clear()
    taken = {}
    for whole in ("Maximilianus Fitzgerald", "Maximilianus Fitzroy", "Maximilianus Fitzgerald", "Maximilianus Fi..."):
        ctl, _impl = _typed_box(w, 8, whole)
        out = e.alloc(0x20, fill=0xCD)
        e.call(w.s["GET_TEXT"], (out, 0x13), ecx=ctl)
        short = N.short_form(whole, 18, taken)
        assert e.read(out, 0x13) == T.encode(short).ljust(0x13, b"\0")
        if short != whole:
            taken.setdefault(short, whole)
    assert [(x.short, x.full) for x in w.names_file(1)] == list(taken.items())


def test_a_short_form_opens_as_the_whole_name_and_survives_a_restart(world):
    w, _fonts = world
    e = w.e
    w.forget()
    w.fs.clear()
    whole = "Łukasz Żółć-Kowalski z Wielkopolski"
    ctl, impl = _typed_box(w, 7, whole)
    out = e.alloc(0x20, fill=0)
    e.call(w.s["GET_TEXT"], (out, 0x13), ecx=ctl)
    short = e.read(out, 0x13).split(b"\0")[0]
    assert short == T.encode(N.short_form(whole, 18, {}))
    w.forget()                                                     # the game started again: the file is read
    ctl, impl = w.box(w.returns[7], 0x12)
    w.set_text(impl, short)
    assert w.text(impl) == T.encode(whole)
    out2 = e.alloc(0x20, fill=0xCD)
    e.call(w.s["GET_TEXT"], (out2, 0x13), ecx=ctl)               # unchanged: the same short form back
    assert e.read(out2, 0x13).split(b"\0")[0] == short
    path = next(iter(w.fs))
    w.fs[path] = b"VF2 Names 1\n\xff\xfe\tdamaged"
    w.forget()
    ctl, impl = w.box(w.returns[7], 0x12)
    w.set_text(impl, short)
    assert w.text(impl) == short                                   # a damaged file: the short form shows


def _file(w, slot=1):
    return w.fs.get(f"{SAVES}Virtual Families 2 Patcher Data\\Names\\Virtual Families 2{slot}.ldw.txt")


def _set_file(w, data, slot=1):
    w.fs[f"{SAVES}Virtual Families 2 Patcher Data\\Names\\Virtual Families 2{slot}.ldw.txt"] = data


def _short_form_of(w, whole, index=8, room=0x13):
    """Type ``whole`` into a member-name box and let the game GetText it: the short form it stores."""
    ctl, _impl = _typed_box(w, index, whole)
    out = w.e.alloc(0x40, fill=0)
    w.e.call(w.s["GET_TEXT"], (out, room), ecx=ctl)
    return w.e.read(out, room).split(b"\0")[0]


def _opens_as(w, short: bytes) -> bytes:
    """What a name box opened with the stored ``short`` holds: the whole name when the DLL knows it, else short."""
    _ctl, impl = w.box(w.returns[7], 0x12)
    w.set_text(impl, short)
    return w.text(impl)


def test_the_dll_writes_version_2_with_crcs_the_patcher_reads(world):
    """The DLL's Names file is byte for byte what vf2_names.render writes: "VF2 Names 2", CRC-32 on each record."""
    w, _fonts = world
    w.forget()
    w.fs.clear()
    names = ["Maximilianus Fitzgerald the Third", "Åukasz Å»Ã³Å‚Ä‡-Kowalski z Wielkopolski", "日本語のなまえをここに書く", CUNEIFORM * 5]
    shorts = [_short_form_of(w, n) for n in names]
    taken = {}
    entries = []
    for n, s in zip(names, shorts):
        assert s == T.encode(N.short_form(n, N.MEMBER_ROOM, taken))
        taken[T.decode(s)] = n
        entries.append(N.Entry(T.decode(s), N.MEMBER_ROOM, n))
    data = _file(w)
    assert data == N.render(entries) and data.startswith(b"VF2 Names 2\n")
    assert N.parse(data) == entries


def test_the_dll_skips_a_record_whose_crc_fails_and_still_reads_version_1(world):
    w, _fonts = world
    w.forget()
    w.fs.clear()
    names = ["Maximilianus Fitzgerald the Third", "Bartholomew Cuthbertson Wellington", "Cornelius Dagobert Ellsworth",
             "Desdemona Evangeline Featherstone"]
    shorts = [T.encode(N.short_form(n, N.MEMBER_ROOM, {})) for n in names]
    # each name's own short form is the same here only if they start differently
    assert len(set(shorts)) == 4
    entries = [N.Entry(T.decode(s), N.MEMBER_ROOM, n) for s, n in zip(shorts, names)]
    lines = N.render(entries).decode("utf-8").split("\n")
    wrong = lines[2].rpartition("\t")[0] + "\t" + "0" * 8
    # 0: good; 1: wrong checksum; 2: cut short (no line feed after half of it); 3 merged into the line before is
    # below
    _set_file(w, "\n".join([lines[0], lines[1], wrong, lines[3], lines[4][:-4]]).encode("utf-8"))
    w.forget()
    assert _opens_as(w, shorts[0]) == T.encode(names[0])            # a good record
    assert _opens_as(w, shorts[1]) == shorts[1]                     # a wrong checksum: skipped, the short form shows
    assert _opens_as(w, shorts[2]) == T.encode(names[2])            # the next good one
    assert _opens_as(w, shorts[3]) == shorts[3]                     # a record cut short: skipped
    # two records on one line
    _set_file(w, "\n".join([lines[0], lines[1] + lines[2], lines[3], ""]).encode("utf-8"))
    w.forget()
    assert _opens_as(w, shorts[0]) == shorts[0] and _opens_as(w, shorts[1]) == shorts[1]
    assert _opens_as(w, shorts[2]) == T.encode(names[2])
    # version 1: three columns and no checksum, still read; the next name written makes it version 2
    v1 = ("VF2 Names 1\n" + "\n".join(f"{e.short}\t{e.room}\t{e.full}" for e in entries[:2]) + "\n").encode("utf-8")
    _set_file(w, v1)
    w.forget()
    assert _opens_as(w, shorts[0]) == T.encode(names[0]) and _opens_as(w, shorts[1]) == T.encode(names[1])
    short3 = _short_form_of(w, names[2])
    assert short3 == shorts[2]
    assert _file(w) == N.render(entries[:3])
    # a version 2 file whose records lack the checksum column is skipped whole, record by record
    _set_file(w, ("VF2 Names 2\n" + "\n".join(f"{e.short}\t{e.room}\t{e.full}" for e in entries) + "\n").encode("utf-8"))
    w.forget()
    assert _opens_as(w, shorts[0]) == shorts[0]


def test_a_record_that_cannot_be_written_stays_pending_and_is_retried(world):
    w, _fonts = world
    w.forget()
    w.fs.clear()
    whole = "Maximilianus Fitzgerald the Third"
    w.fail_write = True
    short = _short_form_of(w, whole)
    assert short == T.encode(N.short_form(whole, N.MEMBER_ROOM, {})) and _file(w) is None
    assert _opens_as(w, short) == T.encode(whole)                 # known in memory meanwhile
    w.draw("Segoe24", b"x")                                       # a draw: the first retry (still failing)
    w.tick += 1000
    w.fail_write = False
    w.draw("Segoe24", b"x")                                       # under 2 seconds since the last try: not yet
    assert _file(w) is None
    w.tick += 1500
    w.draw("Segoe24", b"x")                                       # 2.5 seconds: written whole
    assert _file(w) == N.render([N.Entry(T.decode(short), N.MEMBER_ROOM, whole)])
    before = _file(w)
    w.fs.pop(next(iter(w.fs)))                                    # written; no more tries
    w.tick += 10000
    w.draw("Segoe24", b"x")
    assert not w.fs and before


def test_a_record_made_while_no_slot_is_known_waits_for_one(world):
    w, _fonts = world
    e = w.e
    w.forget()
    w.fs.clear()
    e.w32(w.gs + S.GS_CURRENT_SLOT, 0xFFFFFFFF)                   # no save slot in play yet
    whole = "Maximilianus Fitzgerald the Third"
    short = _short_form_of(w, whole)
    assert short == T.encode(N.short_form(whole, N.MEMBER_ROOM, {})) and not w.fs
    assert _opens_as(w, short) == T.encode(whole)
    w.tick += 3000
    w.draw("Segoe24", b"x")                                       # still no slot: nothing written
    assert not w.fs
    e.w32(w.gs + S.GS_CURRENT_SLOT, 3)                            # the family in slot 3 is being played
    w.tick += 3000
    w.draw("Segoe24", b"x")
    assert _file(w, 3) == N.render([N.Entry(T.decode(short), N.MEMBER_ROOM, whole)]) and len(w.fs) == 1
    e.w32(w.gs + S.GS_CURRENT_SLOT, 1)


def _restore(w, slot_va=None, slot_value=None):
    """The executable's own bytes again where the plan wrote (the plan proves the stock bytes); then `slot_va`."""
    e = w.e
    for wr in w.writes:
        e.write(wr["va"], e.exe.get_data(wr["va"] - e.base, wr["len"]))
    if slot_va is not None:
        e.w32(slot_va, slot_value)


def _replan(w, slot_va=None, slot_value=None):
    _restore(w, slot_va, slot_value)
    status, writes = w.plan(1)
    assert status == 1
    for wr in writes:
        w.e.write(wr["va"], wr["bytes"])
    w.writes = writes
    return writes


def test_a_pending_record_is_written_by_the_games_save(world):
    """A name stored while no slot is known (the new family's name, before its save slot is chosen) is written to
    its Names file by the game's own save path, at once: theGameState's vtable +38h (Save) is chained, whatever it
    held (here a handler outside the executable, as the Time Controls DLL's), and the save's own answer is kept."""
    w, _fonts = world
    e = w.e
    slot_va = w.proved["gs_vtable"] + S.GS_SAVE_VSLOT
    calls = []
    time_controls = e.fake_code(b"\xC3")

    def save(em):
        calls.append((em.ecx, em.arg(0), e.r32(w.gs + S.GS_CURRENT_SLOT)))
        e.w32(w.gs + S.GS_CURRENT_SLOT, em.arg(0))                   # the game saves into the slot it plays
        return 1, 4
    e.seam_live(time_controls, save)
    try:
        writes = _replan(w, slot_va, time_controls)
        hooked = [wr for wr in writes if wr["va"] == slot_va]
        assert len(hooked) == 1 and e.r32(slot_va) != time_controls
        w.forget()
        w.fs.clear()
        e.w32(w.gs + S.GS_CURRENT_SLOT, 0xFFFFFFFF)                 # no save slot yet
        whole = "Maximilianus Fitzgerald the Third"
        short = _short_form_of(w, whole)
        assert not w.fs                                              # pending
        w.draw("Segoe24", b"x")                                      # a draw tries it now (no slot): the 2 s wait starts
        assert not w.fs
        got = e.call(e.r32(slot_va), (4,), ecx=w.gs)                 # at once the game saves into slot 4 and may quit
        assert calls == [(w.gs, 4, 0xFFFFFFFF)] and got & 0xFF == 1
        assert _file(w, 4) == N.render([N.Entry(T.decode(short), N.MEMBER_ROOM, whole)])   # no draw, no 2 s wait
        e.call(e.r32(slot_va), (4,), ecx=w.gs)                       # nothing pending: the save alone
        assert len(calls) == 2 and len(w.fs) == 1
    finally:
        _replan(w)
        e.w32(w.gs + S.GS_CURRENT_SLOT, 1)


def test_a_save_slot_holding_another_game_function_keeps_the_stock_limits(world):
    w, _fonts = world
    e = w.e
    slot_va = w.proved["gs_vtable"] + S.GS_SAVE_VSLOT
    try:
        _restore(w, slot_va, w.set_can_edit)                         # inside the executable, but not Save
        _status, writes = w.plan(1)
        out = e.alloc(4 * 32)
        e.call(e.dll_export("B200Unicode_TestNames"), (out,))
        assert e.r32(out) == 0 and len(writes) == 10                  # the Unicode text, without the long names
    finally:
        _replan(w)


def _fit(font, full: str, max_width: int) -> str:
    """vf2_names' fitting, as the DLL's FitName: the whole name, or its longest start + "…" that fits."""
    if T.get_width(font, T.encode(full)) <= max_width:
        return full
    cl = T.clusters(full)
    best = "…"
    for k in range(len(cl) + 1):
        t = "".join(cl[:k]).rstrip(" ") + "…"
        if T.get_width(font, T.encode(t)) <= max_width:
            best = t
        else:
            break
    return best


@pytest.mark.parametrize("fname", ["Segoe24", "Segoe32Bold"])
def test_short_forms_draw_as_whole_names(world, fname):
    w, fonts = world
    e = w.e
    font, sheet = fonts[fname]
    w.forget()
    w.fs.clear()
    whole = "Maximilianus Fitzgerald the Third"
    short = N.short_form(whole, 18, {})
    w.fs[f"{SAVES}Virtual Families 2 Patcher Data\\Names\\Virtual Families 21.ldw.txt"] = \
        N.render([N.Entry(short, 18, whole)])
    w.forget()
    widest = max(font.stock_rect(b)[2] - font.stock_rect(b)[0] for b in range(0x20, 0x7F))
    room = 18 * (widest + font.kerning) - font.kerning
    for text in (short, f"{short} and Zoë", f"Baby of {short}"):
        drawn = text.replace(short, _fit(font, whole, room))
        game = w.draw(fname, T.encode(text))
        mine = []
        for p in T.draw_string(font, T.encode(drawn), 3, 5):
            gw, gh, _data = T.glyph_pixels(font, p.glyph, sheet)
            mine.append((p.x, p.y, gw, gh))
        assert [(x, y, ww, hh) for x, y, ww, hh, _d in game] == mine, text
        assert w.width(fname, T.encode(text)) == T.get_width(font, T.encode(drawn))
    font_obj, _f, _s = w.font(fname)
    raw = e.alloc(64)
    e.write(raw, T.encode(short) + b"\0")
    got = e.call(e.dll_export("B200Unicode_TestExpand"), (font_obj, raw, 1))
    assert e.cstr(got).encode("latin-1") == T.encode(_fit(font, whole, T.get_width(font, T.encode(short))))
    e.write(raw, b"No name here...\0")
    assert e.call(e.dll_export("B200Unicode_TestExpand"), (font_obj, raw, 0)) == 0


def _seam_stock_draw(w, font):
    """The stock Draw after its first 7 bytes, once per world: it records the text it is handed and, while the box is
    editable (+24h), cuts it a byte at a time until it fits, as the stock loop does (Draw+147h..+163h: while
    GetWidth + left + 44h > right, text[--len] = 0). The game window and its font are the given font."""
    from unicorn import UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EBP, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP
    e = w.e
    if getattr(w, "drawn", None) is not None:
        return w.drawn
    w.drawn = []
    # the Hebrew, Hindi and Thai letters are drawn with GDI (the world's real GDI): the face names are compared
    from test_unicode_font import _kernel_seams
    probe = type("Probe", (), {"imports": {}})()
    _kernel_seams(probe)
    for name in ("lstrcmpiW", "lstrlenW"):
        e.imports.setdefault(name, probe.imports[name])
    font_obj, _f, _s = w.font("Segoe24")
    window = e.alloc(0x40)

    def stock(uc, address, size, user):
        impl = e.reg(UC_X86_REG_ECX)
        text = e.r32(impl + 0x30)
        raw = e.cstr(text).encode("latin-1")
        w.drawn.append(raw)
        right, left = e.r32(impl + 0x10), e.r32(impl + 0x08) + e.r32(impl + 0x44)
        while raw and e.read(impl + 0x24, 1)[0] and T.get_width(font, raw) + left > right:
            raw = raw[:-1]
            e.write(text + len(raw), bytes(1))
        ebp = e.reg(UC_X86_REG_EBP)
        e.setreg(UC_X86_REG_ESI, e.r32(e.reg(UC_X86_REG_ESP)))     # the esi it pushed
        e.setreg(UC_X86_REG_ESP, ebp + 8)
        e.setreg(UC_X86_REG_EIP, e.r32(ebp + 4))
        e.setreg(UC_X86_REG_EBP, e.r32(ebp))
    stock_body = w.box_draw + S.BOX_DRAW_STEAL
    e.uc.hook_add(UC_HOOK_CODE, stock, begin=stock_body, end=stock_body)
    e.seam_live(w.window_get, lambda em: (window, 0))
    e.seam_live(w.window_font, lambda em: (font_obj, 0))
    return w.drawn


def test_a_long_name_box_draws_a_fitted_copy(world):
    w, fonts = world
    e = w.e
    font, _sheet = fonts["Segoe24"]
    font_obj, _f, _s = w.font("Segoe24")
    drawn = _seam_stock_draw(w, font)
    whole = "Maximilianus Fitzgerald the Third of Wielkopolska"
    _ctl, impl = w.box(w.returns[7], 0x12, font_obj)
    w.type(impl, whole)
    e.w32(impl + 0x08, 0)
    e.w32(impl + 0x10, 200)
    e.w32(impl + 0x44, 4)
    avail = 200 - 0 - 4 - 4
    for typing in (1, 0):
        e.write(impl + 0x25, bytes([typing]))
        drawn.clear()
        e.call(w.h["box_draw"], (), ecx=impl, edx=0)
        cl = T.clusters(whole)
        if typing:
            best = ""
            for k in range(len(cl) + 1):
                t = "…" + "".join(cl[len(cl) - k:])
                if T.get_width(font, T.encode(t)) <= avail:
                    best = t
            want = best
        else:
            want = _fit(font, whole, avail)
        assert drawn == [T.encode(want)]
        assert w.text(impl) == T.encode(whole)                     # the box keeps its whole text


def test_a_name_box_without_its_own_font_keeps_what_is_typed(world):
    """The family member screen's name box has no font of its own (+3Ch is 0): the stock Draw draws it in the game
    window's font and, while it is typed into, cuts the text a byte at a time until it fits the box (the loop at
    Draw+147h..+163h: width + left + 44h > right). Live (B209), every Thai consonant typed past the box's width was
    cut by that loop after HandleKey had taken it, and only the zero-width marks stayed ("สวัสดี" became "สัี").
    The DLL draws a fitted copy in the window's font, so the stock loop never cuts the box's own text. The
    stock Draw's body is the cut loop itself (_seam_stock_draw), run after every keystroke."""
    w, fonts = world
    e = w.e
    font, _sheet = fonts["Segoe24"]
    assert w.window_get == w.proved["sites"]["WINDOW_GET"] and w.window_font == w.proved["sites"]["WINDOW_FONT"]
    _seam_stock_draw(w, font)
    live = "שלום नमस्ते สวัสดี"
    _ctl, impl = w.box(w.returns[7], 0x12, 0)
    assert e.r32(impl + 0x3C) == 0
    e.write(impl + 0x24, b"\x01\x01")                              # editable, being typed into
    e.w32(impl + 0x08, 0)
    e.w32(impl + 0x10, 120)                                        # narrower than the whole name
    e.w32(impl + 0x44, 4)
    assert T.get_width(font, T.encode(live)) + 4 > 120
    for ch in live:
        e.call(w.h["handle_key"], (5, ord(ch) | S.KEY_MARK, 0), ecx=impl, edx=0)
        e.call(w.h["box_draw"], (), ecx=impl, edx=0)                 # the next frame draws the box
    assert T.decode(w.text(impl)) == live


def test_a_changed_long_names_byte_keeps_the_unicode_text(exe, dlls):
    """The long names are their own group: an executable whose SetCanEdit differs gets the Unicode text's ten writes
    and not the long names' two (never nothing at all)."""
    if not (OBJS / "ldwTextControl.obj").is_file():
        pytest.skip("no desktop objects (work/desktop_obj_files)")
    import gen_b200_unicode_sites as G
    from test_b200_unicode_dll import World
    at = G.resolve_names(G.Exe(exe), G.load_name_pins(OBJS))["sites"]["SET_CAN_EDIT"]
    w = World(exe, dlls[1])
    w.e.write(at + 0x45, bytes([w.e.read(at + 0x45, 1)[0] ^ 0x5A]))
    status, writes = w.plan(1)
    assert status == 1 and len(writes) == 10
    out = w.e.alloc(4 * 32)
    w.e.call(w.e.dll_export("B200Unicode_TestNames"), (out,))
    assert w.e.r32(out) == 0
