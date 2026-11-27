"""Revive in the game (companion DLL vf2revive_b200.dll, the executable's Revive row and death capture).

Layers (nothing here starts the game; there is no live test):

* always: the DLL source holds no game address, allocates no executable memory and writes only the two
  theGameState vtable slots (data, PAGE_READWRITE, the old protection put back); its file layout is
  src/vf2_revive.py's; the generator's constants (the row 0x15C, $25,000, the .vf2rviv byte, the loader, the
  death caves) agree with the DLL and the patcher;
* with Visual Studio (VF2_VCVARS32): the REAL DLL is built (/W4 /WX) and driven by its harness (a stand-in for the
  executable's host table, runtime/native/b200revive/revive_harness.cpp): the snapshot at each death, its file
  beside the save rotating with the game's own N -> N+20, the load, a damaged file set aside, only the dead of the
  current generation offered, the age rule, the "Arrived" record in the Family History log, and a host it cannot
  trust refused (nothing installed, the vtable untouched). Every file it writes is read back by vf2_revive;
* with an executable built from this branch (VF2_REVIVE_EXE): the executable's own CVillagerState::SetHealth and
  AdjustHealth run in unicorn (at the link address and relocated) and reach VF2ReviveOnDeath only on the path that
  stores a cause of death, with the stock result; the helper itself does nothing while the Revive byte is 0; the
  row's record holds $25,000; every other companion DLL's pins still resolve;
* with the real B209 executables (VF2_B200_MATRIX_GLOB, and VF2_REVIVE_EXE): the game's own
  CFamilyTree::ReportDeath and CountSurvivingChildren agree with the revival's re-pointing of a dead child's entry.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "runtime" / "native" / "b200revive"
BUILD = ROOT / "runtime" / "build"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "runtime" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vf2_revive as rv  # noqa: E402

VCVARS = os.environ.get("VF2_VCVARS32")
REVIVE_EXE = os.environ.get("VF2_REVIVE_EXE")
MATRIX_GLOB = os.environ.get("VF2_B200_MATRIX_GLOB")
B200_CORE = os.environ.get("VF2_B200_CORE_EXE")
GEN = ROOT / "work" / "patch_mobile_furniture_pack.py"


def source() -> str:
    return (SRC / "b200revive.cpp").read_text(encoding="utf-8")


def code_only(text: str) -> str:
    text = re.sub(r"//[^\n]*", "", text)
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)


# ===================================================================== always
def test_the_dll_holds_no_game_address_and_runs_no_buffer_of_its_own():
    text = code_only(source())
    found = [x for x in re.findall(r"0x[0-9A-Fa-f]{5,8}\b", text) if int(x, 16) >= 0x400000]
    assert not found, found
    for word in ("VirtualAlloc", "HeapAlloc", "PAGE_EXECUTE", "FlushInstructionCache", "0xE9", "0xE8"):
        assert word not in text, word
    # the only VirtualProtect: the two vtable slots, PAGE_READWRITE, then the old protection
    assert text.count("VirtualProtect(") == 2
    assert "VirtualProtect(slot, 4, PAGE_READWRITE, &old)" in text and "VirtualProtect(slot, 4, old, &ignored)" in text
    assert text.count("WriteSlot(vt + kLoadSlot") == 2 and text.count("WriteSlot(vt + kSaveSlot") == 1


def test_the_dll_file_layout_is_vf2_revives():
    text = source()
    assert f"kHeader = {rv.HEADER}, kEntry = {rv.ENTRY_SIZE}, kMaxEntries = {rv.MAX_ENTRIES}" in text
    offsets = dict((attr, off) for off, _fmt, attr in rv._ENTRY)
    offsets.update((attr, off) for off, _size, attr in rv._BYTES)
    for c, attr in (("E_SOURCE", "source"), ("E_GENERATION", "generation"), ("E_ROLE", "role"), ("E_AGE", "age_at_death"),
                    ("E_CAUSE", "cause"), ("E_SEX", "sex"), ("E_HEAD", "head"), ("E_BODY", "body"),
                    ("E_CAREER", "career"), ("E_LEVEL", "career_level"), ("E_FERTILITY", "fertility"),
                    ("E_DESIRE", "procreation_desire"), ("E_FIRST", "first_name_index"), ("E_BIO0C", "bio_0c"),
                    ("E_HEIR_SEX", "heir_sex"), ("E_NAME", "name"), ("E_HEIR_NAME", "heir_name"),
                    ("E_FATHER", "father"), ("E_MOTHER", "mother"), ("E_LIKES", "likes"), ("E_DISLIKES", "dislikes"),
                    ("E_LIKES_TEXT", "likes_text"), ("E_DISLIKES_TEXT", "dislikes_text"), ("E_MARKS", "marks"),
                    ("E_RECORD", "record"), ("E_FULL", "full_name")):
        assert re.search(rf"\b{c} = {offsets[attr]}\b", text), c
    order = re.search(r"enum \{ (F_NAME[^}]*)\};", text).group(1)
    names = [n.strip() for n in order.replace("\n", " ").split(",") if n.strip() and n.strip() != "F_COUNT"]
    assert len(names) == len(rv.FIELDS)


def test_the_generator_wires_the_row_the_byte_the_loader_and_the_death_capture():
    text = GEN.read_text(encoding="utf-8")
    for needle in ('REVIVE_ITEM_ID = 0x15C', 'REVIVE_PRICE = 25000', 'REVIVE_FLAG_SECTION = ".vf2rviv"',
                   'REVIVE_DLL_NAME = "vf2revive_b200.dll"', 'REVIVE_INI_NAME = "vf2revive.ini"',
                   'if (gVF2Revive == 1) VF2LoadReviveDll();', 'GetProcAddress(module, "B200Revive_Startup")',
                   '"B200Revive_OnDeath"', '"B200Revive_Candidates"', '"B200Revive_Done"', '"B200Revive_Status"',
                   'patch_revive_death_capture(manifest)', 'patch_revive_manifest(manifest)',
                   '/alternatename:_VF2ReviveStockLoadSymbol=?Load@theGameState@@UAE_NH@Z',
                   '/alternatename:_VF2ReviveStockSaveSymbol=?Save@theGameState@@UAE_NH@Z',
                   'return gVF2FreeGuaranteedCheats == 1 ? 0 : -1;', 'VF2PurchaseRevive();',
                   'Money.Adjust((float)paid, false)'):
        assert needle in text, needle
    # the 3-argument SpawnSpecificPeep is (name seed, gender, AGE), as the store's Adoption Services calls it
    assert "VillagerManager.SpawnSpecificPeep(1, (EGender)c.sex, c.ageUnits)" in text
    assert "int const SpawnSpecificPeep(int nameSeed, EGender gender, int age);" in text
    # a spouse whose partner remarried takes no child place: no AddOffspring for them, the tree is left as it is
    assert re.search(r"if \(p\[0x1A\]\) return 3;\s+// the partner remarried", text)
    # the host table the executable fills is the one the DLL reads, field for field
    host = re.search(r"struct VF2ReviveHost \{(.*?)\};", text, re.S).group(1)
    dll = re.search(r"struct VF2ReviveHost \{(.*?)\};", source(), re.S).group(1)
    norm = lambda body: re.sub(r"\s+", " ", re.sub(r"//[^\n]*", "", body)).strip()  # noqa: E731
    assert norm(host) == norm(dll)


def test_the_price_the_patcher_and_the_executable_agree():
    text = GEN.read_text(encoding="utf-8")
    price = int(re.search(r"^REVIVE_PRICE = (\d+)", text, re.M).group(1))
    assert price == 25_000 == rv.REVIVE_PRICE


# ===================================================================== the real DLL in its harness
@pytest.fixture(scope="module")
def built():
    if not VCVARS or not Path(VCVARS).is_file():
        pytest.skip("VF2_VCVARS32 is not set to Visual Studio's vcvars32.bat")
    run = subprocess.run(["cmd.exe", "/c", str(ROOT / "runtime" / "native" / "build_b200revive.bat"), "test"],
                         capture_output=True, text=True, env={**os.environ, "VF2_VCVARS32": VCVARS})
    assert run.returncode == 0, run.stdout + run.stderr
    assert (BUILD / "vf2revive_b200.dll").is_file() and (BUILD / "vf2revive_harness.exe").is_file()
    return BUILD


class Game:
    def __init__(self, built: Path, tmp: Path, setting: bool = True):
        self.bin = tmp / "bin"
        self.saves = tmp / "saves"
        self.bin.mkdir(parents=True)
        self.saves.mkdir(parents=True)
        for name in ("vf2revive_b200.dll", "vf2revive_harness.exe"):
            shutil.copy2(built / name, self.bin / name)
        shutil.copy2(built / "vf2skin_standin.dll", self.bin / "vf2skin_b200.dll")    # loaded only by "skin"
        (self.bin / "vf2revive.ini").write_bytes(b"[Patches]\r\nRevive=%d\r\n" % (1 if setting else 0))

    def run(self, *commands: str) -> list[str]:
        out = subprocess.run([str(self.bin / "vf2revive_harness.exe"), str(self.saves), *commands],
                             capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stdout + out.stderr
        return out.stdout.splitlines()

    def snapshots(self, number: int = 1):
        f = rv.read_file(rv.sidecar_path(self.saves, number).read_bytes())
        assert f is not None
        return f

    def describes(self, number: int) -> bool:
        return rv.describes(rv.sidecar_path(self.saves, number).read_bytes(),
                            (self.saves / f"Virtual Families 2{number}.ldw").read_bytes())


def cands(lines):
    return [line.split()[1:] for line in lines if line.startswith("cand ")]


def test_a_death_is_captured_exactly_and_kept_beside_the_save(built, tmp_path):
    g = Game(built, tmp_path)
    out = g.run("family", "save", "1", "load", "1", "age", "3", "120", "kill", "1", "2", "kill", "3", "0", "save", "1",
                "status")
    assert "installed 1" in out
    f = g.snapshots(1)
    assert g.describes(1)
    people = {s.name_text: s for s in f.entries}
    assert set(people) == {"Bob", "Fay"}
    bob, fay = people["Bob"], people["Fay"]
    assert bob.source == rv.CAPTURED and bob.role == rv.ROLE_SPOUSE and bob.cause == 2
    assert all(bob.mark(k) == rv.EXACT for k in ("name", "sex", "head", "body", "likes", "career", "career_level",
                                                    "fertility", "procreation_desire", "age_at_death", "record"))
    assert (bob.fertility, bob.procreation_desire, bob.career, bob.career_level) == (44, 55, 7, 2)
    assert bob.revival_age() == (400, rv.EXACT)                  # died at 47: returns at 20
    assert fay.revival_age() == (120, rv.EXACT)                  # died at 6: returns at 6
    assert fay.role == rv.ROLE_CHILD + 1


def test_the_file_goes_with_the_save_the_game_moves_to_n_plus_20(built, tmp_path):
    g = Game(built, tmp_path)
    g.run("family", "save", "1", "load", "1", "kill", "1", "2", "save", "1", "save", "1")
    assert g.describes(1) and g.describes(21)
    assert {s.name_text for s in g.snapshots(21).entries} == {"Bob"}


def test_a_load_reads_the_file_and_a_damaged_one_is_set_aside(built, tmp_path):
    g = Game(built, tmp_path)
    g.run("family", "save", "1", "load", "1", "kill", "1", "2", "save", "1")
    out = g.run("load", "1", "cands")
    assert "cands 1" in out and cands(out)[0][1] == "Bob"
    path = rv.sidecar_path(g.saves, 1)
    path.write_bytes(b"VF2REVIV broken")
    out = g.run("load", "1", "status")
    assert (path.parent / "Virtual Families 21.ldw.unreadable-1.dat").read_bytes() == b"VF2REVIV broken"
    assert any("load 3" in line for line in out)


def test_only_the_dead_of_this_generation_are_offered_with_the_age_rule(built, tmp_path):
    g = Game(built, tmp_path)
    out = g.run("family", "save", "1", "load", "1", "age", "3", "399", "kill", "3", "0", "age", "2", "400",
                "kill", "2", "1", "cands")
    got = {c[1]: c for c in cands(out)}
    assert set(got) == {"Fay", "Cal"}                           # Ann and Bob live: never offered
    assert got["Fay"][5] == "399" and got["Cal"][5] == "400"     # 19 years 19 units: as they died; 20: 20
    out = g.run("family", "save", "1", "load", "1", "age", "2", "2000", "kill", "2", "1", "cands")
    assert {c[1]: c[5] for c in cands(out)} == {"Cal": "400"}   # 100 years: back at 20
    # someone alive again under the same identity is not offered (a namesake of the dead in the house)
    out = g.run("family", "save", "1", "load", "1", "kill", "3", "0", "reuse", "3", "cands")
    assert "cands 1" in out
    out = g.run("load", "1", "family", "cands")
    assert "cands 0" in out                                      # Fay is alive in this house


def test_a_revival_leaves_the_list_and_is_logged_in_the_family_history(built, tmp_path):
    g = Game(built, tmp_path)
    logs = g.saves / "Virtual Families 2 Patcher" / "Save 1" / "Logs" / "Family History"
    logs.mkdir(parents=True)
    (logs / "Family History 1.txt").write_bytes(b"Family: Test (Save 1)\r\n\r\n[2026-11-01 10:00:00] Arrived 3\r\n"
                                                b"  Name: Ivy\r\n\r\n[2026-11-02 10:00:00] Death 1\r\n  Name: Bob\r\n\r\n")
    out = g.run("family", "save", "1", "load", "1", "kill", "1", "2", "done", "0", "5", "Parent (married in)",
                "cands", "status")
    assert "cands 0" in out and any("revived 1" in line for line in out)
    text = (logs / "Family History 1.txt").read_text(encoding="utf-8")
    import vf2_family_history as fh
    last = fh.entries(text)[-1]
    assert (last.kind, last.number) == ("Arrived", 4)
    assert last.get("Name") == "Bob" and last.get("How") == "Revived (Revive a Family Member)"
    assert last.get("Age at arrival") == "20" and last.get("Family role") == "Parent (married in)"
    assert last.get("Generation") == "1"


def test_no_log_is_started_for_a_slot_without_one(built, tmp_path):
    g = Game(built, tmp_path)
    g.run("family", "save", "1", "load", "1", "kill", "1", "2", "done", "0", "5", "Child")
    assert not (g.saves / "Virtual Families 2 Patcher").exists()


def test_a_host_it_cannot_trust_or_the_setting_off_installs_nothing(built, tmp_path):
    g = Game(built, tmp_path / "a")
    out = g.run("hostbad", "vtable", "family", "kill", "1", "2", "cands")
    assert out[0] == "installed 0" and "vtable 0 0" in out and "cands 0" in out
    off = Game(built, tmp_path / "b", setting=False)
    out = off.run("vtable", "family", "save", "1", "kill", "1", "2", "save", "1")
    assert out[0] == "installed 0" and "vtable 0 0" in out
    assert not (off.saves / "Virtual Families 2 Patcher Data").exists()
    on = Game(built, tmp_path / "c")
    assert "vtable 1 1" in on.run("vtable")


# ===================================================================== the executable built from this branch
def revive_exe() -> Path:
    if not REVIVE_EXE or not Path(REVIVE_EXE).is_file():
        pytest.skip("VF2_REVIVE_EXE is not set to an executable built from this branch")
    return Path(REVIVE_EXE)


def find_once(data: bytes, pattern: bytes) -> int:
    hits = [m.start() for m in re.finditer(re.escape(pattern), data)]
    assert len(hits) == 1, (pattern.hex(), len(hits))
    return hits[0]


def file_to_va(pe, offset: int) -> int:
    for s in pe.sections:
        if s.PointerToRawData <= offset < s.PointerToRawData + s.SizeOfRawData:
            return pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress + offset - s.PointerToRawData
    raise AssertionError(hex(offset))


SET_HEALTH = bytes.fromhex("558bec8b4508894 10c85c07f118b450cc7410c00000000e9".replace(" ", ""))
ADJUST_HEALTH_TAIL = bytes.fromhex("7f138b450cc7460c00000000e9")


@pytest.mark.parametrize("delta", (0, 0x1A0000))
def test_the_executables_own_health_setters_reach_the_capture_only_at_a_death(built, delta):
    import pefile
    from b200_time_emu import Emu
    exe = revive_exe()
    data = exe.read_bytes()
    pe = pefile.PE(data=data, fast_load=True)
    set_health = file_to_va(pe, find_once(data, SET_HEALTH))
    adjust_tail = file_to_va(pe, find_once(data, ADJUST_HEALTH_TAIL))
    e = Emu(exe, built / "vf2revive_b200.dll", delta)
    set_health += delta
    # the cave: the jmp at +17h, then the cave's call of the helper
    jmp = set_health + 0x17
    assert e.read(jmp, 1) == b"\xE9"
    cave = (jmp + 5 + e.r32(jmp + 1)) & 0xFFFFFFFF
    assert e.read(cave, 6) == bytes.fromhex("89411060" "51" "e8")[:6]
    helper = (cave + 5 + 5 + e.r32(cave + 6)) & 0xFFFFFFFF
    calls = []
    e.seam_live(helper, lambda emu: (calls.append(emu.arg(0)), (0, 0))[1])
    state = e.alloc(0x100)
    e.w32(state + 0x0C, 80)
    e.w32(state + 0x10, 0xFFFFFFFF)
    e.call(set_health, (50, 2), ecx=state)
    assert (e.rs32(state + 0x0C), e.rs32(state + 0x10), calls) == (50, -1, [])
    e.call(set_health, (0, 2), ecx=state)
    assert (e.rs32(state + 0x0C), e.rs32(state + 0x10), calls) == (0, 2, [state])
    # AdjustHealth: the function starts 49h before its death-path tail (the jg at +49h)
    adjust = adjust_tail + delta - 0x49
    assert e.read(adjust, 3) == b"\x55\x8b\xec"
    calls.clear()
    e.w32(state + 0x0C, 50)
    e.w32(state + 0x10, 0xFFFFFFFF)
    e.call(adjust, (4, 1), ecx=state)
    assert e.rs32(state + 0x0C) == 54 and e.rs32(state + 0x10) == -1 and calls == []
    e.w32(state + 0x0C, 3)
    e.call(adjust, (-40, 1), ecx=state)
    assert (e.rs32(state + 0x0C), e.rs32(state + 0x10), calls) == (0, 1, [state])


def test_the_capture_helper_does_nothing_while_the_byte_is_0(built):
    import pefile
    from b200_time_emu import Emu
    exe = revive_exe()
    data = exe.read_bytes()
    pe = pefile.PE(data=data, fast_load=True)
    names = [s.Name.rstrip(b"\0") for s in pe.sections]
    assert b".vf2rviv" in names
    flag = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".vf2rviv")
    assert data[flag.PointerToRawData] == 0
    set_health = file_to_va(pe, find_once(data, SET_HEALTH))
    e = Emu(exe, built / "vf2revive_b200.dll")
    jmp = set_health + 0x17
    cave = (jmp + 5 + e.r32(jmp + 1)) & 0xFFFFFFFF
    helper = (cave + 5 + 5 + e.r32(cave + 6)) & 0xFFFFFFFF
    state = e.alloc(0x100)
    e.call(helper, (state,), limit=200)          # returns at once: no DLL, nothing read or written outside


def test_the_rows_record_holds_its_price_and_the_other_dlls_still_resolve():
    exe = revive_exe()
    data = exe.read_bytes()
    record = struct.pack("<I", 0x15C)
    hits = [m.start() for m in re.finditer(re.escape(record), data)
            if struct.unpack_from("<9I", data, m.start())[2:4] == (1, 25000)]
    assert len(hits) == 1
    title_id, description_id = struct.unpack_from("<9I", data, hits[0])[5:7]
    import vf2_translation_strings as ts
    table = ts.read_table(data)
    assert table[title_id] == ("eString_ReviveTitle", b"Revive a Family Member")
    assert table[description_id][0] == "eString_ReviveDescription"
    for key in ("eString_ReviveQuestion", "eString_ReviveButton", "eString_ReviveNextButton", "eString_ReviveNone",
                "eString_ReviveNoRoom", "eString_ReviveDone", "eString_ReviveAge"):
        assert key in {k for k, _text in table.values()}, key
    if not B200_CORE or not Path(B200_CORE).is_file():
        pytest.skip("VF2_B200_CORE_EXE is not set (the other DLLs' pins are proved from it)")
    import importlib
    core = Path(B200_CORE).read_bytes()
    for name in ("history", "kids", "outfits", "refresh", "time", "titlebox"):
        G = importlib.import_module(f"gen_b200_{name}_sites")
        assert G.validate_variant(data, G.validate(core)), name
    import gen_b200_translations_sites as T
    assert T.validate_variant(data, core)


# ===================================================================== the game's own tree code agrees
def tree_exes() -> list[Path]:
    found = sorted(Path(p) for p in glob.glob(MATRIX_GLOB)) if MATRIX_GLOB else []
    if REVIVE_EXE and Path(REVIVE_EXE).is_file():
        found.append(Path(REVIVE_EXE))
    if not found or not B200_CORE or not Path(B200_CORE).is_file():
        pytest.skip("VF2_B200_MATRIX_GLOB / VF2_REVIVE_EXE and VF2_B200_CORE_EXE are not set")
    return found


def test_a_revived_childs_entry_agrees_with_the_games_own_tree_code(built):
    import b200_history_sites as S
    import gen_b200_history_sites as G
    from b200_time_emu import Emu
    model = G.validate(Path(B200_CORE).read_bytes()) if B200_CORE and Path(B200_CORE).is_file() else None
    for exe in tree_exes():
        sites = G.validate_variant(exe.read_bytes(), model)
        e = Emu(exe, built / "vf2revive_b200.dll")
        tree, manager = sites["FAMILY_TREE"], sites["VILLAGER_MANAGER"]
        report = sites["FT_REPORT_DEATH"]
        assert e.read(report + 0x125, 1) == b"\xE8"
        count_surviving = (report + 0x12A + e.r32(report + 0x126)) & 0xFFFFFFFF
        villager = lambda slot: manager + S.VILLAGER_ARRAY_OFFSET + slot * S.VILLAGER_STRIDE  # noqa: E731
        e.w32(tree + 4, 1)                                        # one generation
        rec = tree + 1 * S.FAMILY_RECORD_SIZE - S.FAMILY_RECORD_BASE
        e.write(rec, bytes(S.FAMILY_RECORD_SIZE))
        e.write(rec, b"\x01")
        for place, (name, slot) in enumerate((("Ann", 0), ("Bob", 1), ("Cal", 2))):
            p = rec + (S.RECORD_PARENT1 if place == 0 else S.RECORD_PARENT2 if place == 1 else S.RECORD_CHILDREN)
            e.write(p, name.encode().ljust(25, b"\0"))
            e.write(p + S.PEEP_VALID, b"\x01")
            e.w32(p + S.PEEP_SLOT, slot)
            v = villager(slot)
            e.w32(v + S.VILLAGER_SLOT, slot)
            e.write(v + S.VILLAGER_ACTIVE, b"\x01")
        e.w32(rec + S.RECORD_CHILD_COUNT, 1)
        child = rec + S.RECORD_CHILDREN
        assert e.call(count_surviving, (), ecx=tree) == 1
        # the child dies: the game's own ReportDeath, then it is deactivated (as both callers do)
        e.write(villager(2) + S.VILLAGER_ACTIVE, b"\x00")
        e.call(report, (villager(2),), ecx=tree)
        assert e.rs32(child + S.PEEP_SLOT) == -1
        assert e.call(count_surviving, (), ecx=tree) == 0
        # the revival: a new villager in a free slot, the dead child's own entry pointed at it
        v = villager(7)
        e.w32(v + S.VILLAGER_SLOT, 7)
        e.write(v + S.VILLAGER_ACTIVE, b"\x01")
        e.w32(child + S.PEEP_SLOT, 7)
        assert e.call(count_surviving, (), ecx=tree) == 1, exe
        assert e.rs32(rec + S.RECORD_CHILD_COUNT) == 1                 # no second entry: the six are not used up
        # and the game's own ReportDeath finds them again by that slot when they die again
        e.write(v + S.VILLAGER_ACTIVE, b"\x00")
        e.call(report, (v,), ecx=tree)
        assert e.rs32(child + S.PEEP_SLOT) == -1 and e.call(count_surviving, (), ecx=tree) == 0


# ===================================================================== a remarried partner's late spouse; Skin Tones
def test_a_remarried_partners_late_spouse_lives_outside_the_tree_and_is_listed_to_draw(built, tmp_path):
    g = Game(built, tmp_path)
    out = g.run("family", "save", "1", "load", "1", "kill", "1", "2", "gone", "1", "remarry", "cands")
    bob = next(c for c in cands(out) if c[1] == "Bob")
    out = g.run("family", "save", "1", "load", "1", "kill", "1", "2", "gone", "1", "remarry",
                "done", bob[0], "5", "Family member", "members", "cands", "save", "1", "load", "1", "members")
    members = [line for line in out if line.startswith("member ")]
    assert members == ["member Bob slot 5 sex 0 head 2 body 2"] * 2        # before and after a save and a load
    assert "cands 0" in out and not [c for c in cands(out) if c[1] == "Bob"]
    f = g.snapshots(1)
    kept = [s for s in f.entries if s.name_text == "Bob"]
    assert len(kept) == 1 and kept[0].source == rv.MEMBER and kept[0].spare[2] == 5
    assert rv.refusal(r_parse(g), kept[0]) is not None                    # alive: never offered again


def r_parse(g):
    """The harness's save is not a game save: a FamilySave-like view of who is alive, for vf2_revive.refusal."""
    import vf2_save_reader as r
    data = (g.saves / "Virtual Families 21.ldw").read_bytes()
    villagers = []
    for slot in range(30):
        b = data[slot * 0x7BC:(slot + 1) * 0x7BC]
        villagers.append(type("V", (), {
            "active": b[0] != 0, "left_home": b[1] != 0, "health": struct.unpack_from("<i", b, 0xB4)[0],
            "name": b[0x18:0x18 + 25].split(b"\0")[0].decode(), "gender": struct.unpack_from("<i", b, 0x0C)[0],
            "head": struct.unpack_from("<i", b, 0x34)[0], "body": struct.unpack_from("<i", b, 0x38)[0]})())
    return type("S", (), {"villagers": villagers, "family_tree": type("T", (), {"current": None,
                                                                                 "num_generations": 1})()})()


def test_a_skin_tone_kept_at_the_death_is_given_back(built, tmp_path):
    g = Game(built, tmp_path)
    out = g.run("skin", "family", "save", "1", "load", "1", "kill", "3", "0", "kill", "1", "2", "cands")
    assert "skin 1" in out
    fay = next(c for c in cands(out) if c[1] == "Fay")
    bob = next(c for c in cands(out) if c[1] == "Bob")
    out = g.run("skin", "family", "save", "1", "load", "1", "kill", "3", "0", "kill", "1", "2", "save", "1",
                "done", fay[0], "8", "Child", "given")
    assert "given 1 slot 8 tone 6 birth 7" in out                       # slot 3: tone 3 + 3, birth tone 7
    snaps = {s.name_text: s for s in g.snapshots(1).entries}
    assert snaps["Fay"].spare[0:2] == b"\x06\x07" and snaps["Fay"].spare[3] & 1
    assert snaps["Bob"].spare[3] & 1 == 0                               # the stand-in gave Bob no tone
    out = g.run("skin", "load", "1", "done", bob[0], "8", "Child", "given")
    assert "given 0 slot -1 tone -1 birth -1" in out                    # no tone kept: nothing given


def test_the_file_keeps_the_spare_bytes():
    s = rv.Snapshot(source=rv.MEMBER, generation=1, sex=0, head=2, body=2, name=b"Bob", spare=b"\x06\x07\x05\x01",
                    marks={"name": rv.EXACT})
    f = rv.read_file(rv.make_file(b"save", [s]))
    assert f.entries[0].spare == b"\x06\x07\x05\x01" and f.entries[0].source == rv.MEMBER


# ===================================================================== the executable: the tree screen, the parents
def links(e, pe, delta):
    sec = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".vf2rvlk")
    at = pe.OPTIONAL_HEADER.ImageBase + sec.VirtualAddress + delta
    assert e.r32(at) == 0x4B4C5652, "the RVLK block"
    flag = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".vf2rviv")
    return at, pe.OPTIONAL_HEADER.ImageBase + flag.VirtualAddress + delta


def installed(e, pe, delta, members):
    """The byte 1, a status block that says installed, and a members export that answers `members`."""
    at, flag = links(e, pe, delta)
    e.write(flag, b"\x01")
    status = e.alloc(0x40)
    e.w32(status, 0x56525632)
    e.w32(status + 12, 1)
    e.w32(at + 4, status)
    stub = e.alloc(0x10, fill=0xC3)

    def answer(emu):
        out, cap = emu.arg(0), emu.arg(1)
        for i, (slot, sex, head, body, name) in enumerate(members[:cap]):
            emu.write(out + i * 48, struct.pack("<4i", slot, sex, head, body) + name.encode().ljust(28, b"\0")
                      + b"\0" * 4)
        return min(len(members), cap), 0
    e.seam_live(stub, answer)
    e.w32(at + 8, stub)


DRAW_FAMILY = bytes.fromhex("558bec83ec4853568bd957895de4e8")
DRAW_FAMILY_CALLS = ("window", "graphics", "strings", "GetFont", "GetFamilyRecord", "SetClipping", "Draw",
                     "DrawString", "DrawParent", "SetClipping", "GetImage", "DrawTinted", "SetClipping", "Draw",
                     "DrawString", "DrawParent", "SetClipping", "GetImage", "DrawTinted", "SetClipping", "Draw",
                     "DrawStringCentered", "DrawChild", "SetClipping", "GetImage", "DrawTinted")
POPS = {"window": 0, "graphics": 0, "strings": 0, "GetFont": 4, "GetFamilyRecord": 4, "SetClipping": 16, "Draw": 20,
        "DrawString": 20, "DrawParent": 28, "GetImage": 4, "DrawTinted": 28, "DrawStringCentered": 20, "DrawChild": 28}


def draw_family_world(built, delta, members):
    import pefile
    import b200_history_sites as S
    import gen_b200_history_sites as G
    from b200_time_emu import Emu
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    exe = revive_exe()
    data = exe.read_bytes()
    pe = pefile.PE(data=data, fast_load=True)
    sites = G.validate_variant(data, G.validate(Path(B200_CORE).read_bytes()))
    e = Emu(exe, built / "vf2revive_b200.dll", delta)
    draw = file_to_va(pe, find_once(data, DRAW_FAMILY)) + delta
    code = e.read(draw, 0x440)
    targets = [int(ins.op_str, 16) for ins in Cs(CS_ARCH_X86, CS_MODE_32).disasm(code, draw)
               if ins.mnemonic == "call" and ins.op_str.startswith("0x")]
    assert len(targets) == len(DRAW_FAMILY_CALLS), len(targets)
    names = {}
    for name, target in zip(DRAW_FAMILY_CALLS, targets):
        assert names.setdefault(target, name) == name, (hex(target), name)
    tree = sites["FAMILY_TREE"] + delta
    e.w32(tree + 4, 2)                                                    # two generations: record 1 is current
    records = [tree + (g + 1) * S.FAMILY_RECORD_SIZE - S.FAMILY_RECORD_BASE for g in range(2)]
    for rec in records:
        e.write(rec, bytes(S.FAMILY_RECORD_SIZE))
        e.write(rec, b"\x01")
        for place, (name, slot) in enumerate((("Ann", 0), ("Hal", 9))):
            p = rec + (S.RECORD_PARENT1 if place == 0 else S.RECORD_PARENT2)
            e.write(p, name.encode().ljust(25, b"\0"))
            e.write(p + S.PEEP_VALID, b"\x01")
            e.w32(p + S.PEEP_GENDER, place)
            e.w32(p + S.PEEP_SLOT, slot)
    scene = e.alloc(0x100)
    for off, v in ((0x0C, 0), (0x10, 0), (0x14, 800), (0x18, 600), (0x74, 10), (0x78, 20), (0x7C, 200), (0x80, 110),
                   (0x84, 300), (0x88, 40)):
        e.w32(scene + off, v)
    objects = {n: e.alloc(0x40) for n in ("window", "graphics", "strings", "font", "image")}
    calls = []

    def seam(name):
        def fn(emu):
            args = [emu.r32(emu.reg(__import__("unicorn").x86_const.UC_X86_REG_ESP) + 4 + 4 * k) for k in range(7)]
            calls.append((name, args))
            if name in ("window", "graphics", "strings"):
                return objects[name], 0
            if name == "GetFont":
                return objects["font"], 4
            if name == "GetImage":
                return objects["image"], 4
            if name == "GetFamilyRecord":
                return records[args[0]], 4
            return 0, POPS[name]
        return fn
    for target, name in names.items():
        e.seam_live(target, seam(name))
    if members is not None:
        installed(e, pe, delta, members)
    return e, draw, scene, records, calls


def frames(calls):
    return [a[2] for n, a in calls if n == "Draw" and a[0] == 0x268]


@pytest.mark.parametrize("delta", (0, 0x1A0000))
def test_the_late_spouse_is_drawn_under_the_current_spouse_with_the_games_own_calls(built, delta):
    member = (5, 0, 2, 2, "Bob")
    e, draw, scene, records, calls = draw_family_world(built, delta, [member])
    before = [e.read(r, 0x6C8) for r in records]
    e.call(draw, (100, 50, 1), ecx=scene)
    ys = frames(calls)
    parent1, spouse = 50 - 2 + 20, 50 + 110
    assert ys == [parent1, spouse, spouse + (spouse - parent1)]           # one parent step under the spouse
    parents = [a for n, a in calls if n == "DrawParent"]
    assert len(parents) == 3 and parents[2][3:6] == [0, 2, 2]              # Bob's sex, head and body
    rect = parents[2][0]
    assert e.rs32(rect + 4) == spouse + (spouse - parent1) + 0x0F and e.rs32(rect + 12) == spouse + (spouse - parent1) + 0x42
    names = [e.read(a[0], 4) for n, a in calls if n == "DrawString"]
    assert names[-1] == b"Bob\0"
    assert not [n for n, _a in calls if n == "DrawChild"]                  # no child place: no child frame
    assert [e.read(r, 0x6C8) for r in records] == before                   # the tree's data untouched


@pytest.mark.parametrize("members, gen", [([], 1), ([(5, 0, 2, 2, "Bob")], 0), (None, 1)])
def test_without_a_member_or_on_an_older_row_or_with_revive_off_the_row_is_the_games(built, members, gen):
    e, draw, scene, records, calls = draw_family_world(built, 0, members)
    e.call(draw, (100, 50, gen), ecx=scene)
    assert len(frames(calls)) == 2 and len([n for n, _a in calls if n == "DrawParent"]) == 2


PARENT_SEARCH = bytes.fromhex("53565733ff8db1f4870300")


@pytest.mark.parametrize("age, career, parent, revive, father", [
    (400, -1, True, 1, True), (2000, -1, True, 1, True), (399, -1, True, 1, False), (400, -1, False, 1, False),
    (400, -1, True, 0, False), (400, 5, False, 0, True)])
def test_a_revived_grown_up_with_no_career_can_be_the_father(built, age, career, parent, revive, father):
    import pefile
    import b200_history_sites as S
    import gen_b200_history_sites as G
    from b200_time_emu import Emu
    exe = revive_exe()
    data = exe.read_bytes()
    pe = pefile.PE(data=data, fast_load=True)
    sites = G.validate_variant(data, G.validate(Path(B200_CORE).read_bytes()))
    e = Emu(exe, built / "vf2revive_b200.dll")
    found = [m.start() for m in re.finditer(re.escape(PARENT_SEARCH), data)]
    assert len(found) == 2
    by_sex = {}
    for off in found:
        va = file_to_va(pe, off)
        by_sex[e.read(va + 0x33, 7)[-1]] = va                               # cmp dword [esi-1512Ch], 0 / 1
    patriarch = by_sex[0]
    manager, tree = sites["VILLAGER_MANAGER"], sites["FAMILY_TREE"]
    _at, flag = links(e, pe, 0)
    e.write(flag, bytes([revive]))
    v = manager + S.VILLAGER_ARRAY_OFFSET + 3 * S.VILLAGER_STRIDE
    e.write(v + S.VILLAGER_ACTIVE, b"\x01")
    e.write(v + S.VILLAGER_LEFT_HOME, b"\x00")
    e.w32(v + S.VILLAGER_HEALTH, 80)
    e.w32(v + S.VILLAGER_GENDER, 0)
    e.w32(v + S.VILLAGER_AGE, age)
    e.w32(v + 0x6B8C, career & 0xFFFFFFFF)
    e.w32(tree + 4, 1)
    rec = tree + S.FAMILY_RECORD_SIZE - S.FAMILY_RECORD_BASE
    e.write(rec, bytes(S.FAMILY_RECORD_SIZE))
    e.write(rec, b"\x01")
    p2 = rec + S.RECORD_PARENT2
    e.write(p2 + S.PEEP_VALID, b"\x01")
    e.w32(p2 + S.PEEP_SLOT, 3 if parent else 7)
    got = e.call(patriarch, (), ecx=manager)
    assert (got == v) is father, (hex(got), hex(v))
