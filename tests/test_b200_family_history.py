"""Family History log for the B200 executable (companion DLL vf2history_b200.dll).

Layers (nothing here starts the game; there is no live test):

* always: the sites module, the DLL source, the generator and the exporter agree on the names, the folder,
  the ini and the loader; the DLL source holds no game address; the exporter's setting is Experimental;
* with the B200 core executable (VF2_B200_CORE_EXE): capstone + pefile prove every pin, the header is a
  fresh render, a damaged executable and wrong constants are refused, and every other executable given
  resolves (VF2_B200_MATRIX_GLOB, VF2_B201_CORE_EXE, VF2_KIDS_EXE, VF2_HISTORY_EXE);
* with Visual Studio as well (VF2_VCVARS32): the DLL builds with /W4 /WX, and the REAL compiled DLL runs
  inside unicorn with the REAL game code reaching every hook from its live caller
  (tests/b200_history_scenarios.py), at the link address and relocated, with source mutations that each
  scenario must catch;
* with an executable built from this branch (VF2_HISTORY_EXE: it has the .vf2hist byte and the loader):
  the executable's own loader end to end, and the exporter's records driving it.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
SRC = RUNTIME / "native" / "b200history"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import b200_history_sites as S  # noqa: E402
import gen_b200_history_sites as G  # noqa: E402

CORE_EXE = os.environ.get("VF2_B200_CORE_EXE")
HISTORY_EXE = os.environ.get("VF2_HISTORY_EXE")
VCVARS = os.environ.get("VF2_VCVARS32")
DELTAS = (0, 0x1A0000)


def core_exe_bytes() -> bytes:
    if not CORE_EXE or not Path(CORE_EXE).is_file():
        pytest.skip("VF2_B200_CORE_EXE is not set to the B200 core executable")
    return Path(CORE_EXE).read_bytes()


def history_exe() -> str:
    if not HISTORY_EXE or not Path(HISTORY_EXE).is_file():
        pytest.skip("VF2_HISTORY_EXE is not set to an executable built from this branch (it has the .vf2hist loader)")
    return HISTORY_EXE


# ===================================================================== always
def test_header_is_the_sites_module():
    header = (SRC / "b200history_sites.h").read_text()
    for pin in S.PINS:
        m = re.search(r"static const unsigned char hpin_%s\[\] = \{ ([^}]*) \};" % re.escape(pin.name), header)
        assert m, pin.name
        assert bytes(int(x, 16) for x in m.group(1).split(", ")) == pin.bytes, pin.name
    for key in ("VILLAGER_STRIDE", "DIALOG_TITLE", "DIALOG_EVENT", "HISTORY_RECORDS_PER_FILE", "STATUS_MAGIC"):
        assert "#define HIST_%s 0x%Xu" % (key, getattr(S, key)) in header
    for key in S.CORE_ONLY_CONSTANTS:
        assert "HIST_%s " % key not in header, key


def test_the_source_has_no_hard_coded_game_address():
    text = (SRC / "b200history.cpp").read_text()
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    found = [x for x in re.findall(r"0x[0-9A-Fa-f]{5,8}\b", text) if int(x, 16) >= 0x400000]
    assert not found, f"literal addresses in the module source: {found}"


def test_names_agree_everywhere():
    cpp = (SRC / "b200history.cpp").read_text()
    for needle in ('L"vf2history.ini"', 'L"FamilyHistory"', "B200History_Startup", 'L"vf2history.log"',
                   '"Virtual Families 2 Patcher\\\\Save "', '"\\\\Logs\\\\Family History\\\\Family History "',
                   '"[backfilled, no date] "', '"Family: "', '"Random Event"', '"Family Tree"'):
        assert needle in cpp, needle
    gen = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    for needle in ('FAMILY_HISTORY_FLAG_SECTION = ".vf2hist"', 'FAMILY_HISTORY_DLL_NAME = "vf2history_b200.dll"',
                   'FAMILY_HISTORY_INI_NAME = "vf2history.ini"', 'GetProcAddress(module, "B200History_Startup")',
                   "if (gVF2FamilyHistory == 1) VF2LoadFamilyHistoryDll();",
                   '#pragma section(".vf2hist", read, write)', "volatile unsigned char gVF2FamilyHistory = 0;",
                   '"__VF2_FAMILY_HISTORY_RELATIVE_PATH__"', "patch_family_history_manifest(manifest)"):
        assert needle in gen, needle
    # loaded after the Time Controls and Up to 28 Children DLLs, in the same wrapper
    assert gen.index("if (gVF2UpTo28Children == 1) VF2LoadUpTo28ChildrenDll();") < \
        gen.index("if (gVF2FamilyHistory == 1) VF2LoadFamilyHistoryDll();")
    assert gen.index("if (gVF2TimeControls == 1) VF2LoadTimeControlsDll();") < \
        gen.index("if (gVF2FamilyHistory == 1) VF2LoadFamilyHistoryDll();")
    assert gen.index("    patch_up_to_28_children_manifest(manifest)\n") < gen.index("    patch_family_history_manifest(manifest)\n")
    # the symbol's name, its declaration and the loader wrapper's test: no other generated code reads the byte
    assert gen.count("gVF2FamilyHistory") == 3 and gen.count("gVF2FamilyHistory ==") == 1
    assert S.DLL_NAME == "vf2history_b200.dll" and S.INI_KEY == "FamilyHistory" and S.INI_NAME == "vf2history.ini"
    assert S.PATCHER_FOLDER == "Virtual Families 2 Patcher Files" and S.LOGS_FOLDER == "Virtual Families 2 Patcher"


def test_the_generator_manifest_contract():
    sys.path.insert(0, str(ROOT / "work"))
    import patch_mobile_furniture_pack as P
    manifest = {"TimeControls": {}}
    P.patch_family_history_manifest(manifest)
    c = manifest["FamilyHistory"]
    assert c["runtime_flag"]["source_section"] == ".vf2hist" and c["runtime_flag"]["default"] == "00"
    assert c["runtime_flag"]["enabled"] == "01" and c["runtime_flag"]["size"] == 1
    assert c["companion_dll"] == S.DLL_NAME and c["companion_ini"] == S.INI_NAME
    assert c["category"] == "experimental" and c["default"] is False
    with pytest.raises(RuntimeError):
        P.patch_family_history_manifest({})


def test_exporter_setting():
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    rows = [s for s in X.SETTINGS if s["id"] == "family_history"]
    assert len(rows) == 1
    s = rows[0]
    # On by default and a normal Optional row (owner, 2026-10-26); Enable All and the final playtest profile tick it
    assert s["default"] is True and s["category"] == "optional" and s["label"] == "Family History log"
    assert "experimental" not in s["description"].lower()
    for needle in ("Virtual Families 1", "Virtual Villagers", "name, age, sex, head and body", "remarriage",
                   "same-sex", "divorce", "twins and triplets", "cause", "Random Event", "Email Event",
                   "Popup Event", "renames", "Start Over", "Evict Family",
                   "backfilled, no date", "Virtual Families 2 Patcher\\Save N\\Logs\\Family History",
                   "Virtual Families 2 Patcher Files"):
        assert needle.lower() in s["description"].lower(), needle
    assert X.RUNTIME_FLAG_SECTION_BY_SETTING["family_history"] == ".vf2hist"
    assert "family_history" in X.SOURCE_BACKED_OPTIONAL_SETTINGS
    assert "family_history" in X.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS
    assert X.FAMILY_HISTORY_INI_TEXT == "[Patches]\r\nFamilyHistory=1\r\n"
    assert X.FAMILY_HISTORY_DLL_NAME == S.DLL_NAME and X.FAMILY_HISTORY_INI_NAME == S.INI_NAME


def test_a_build_without_the_loader_gets_no_records(tmp_path):
    """B203 and earlier have no FamilyHistory contract: the exporter emits nothing for the setting there."""
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    assert X.family_history_asset_patches(tmp_path / "b", None, {}) == []
    assert X.family_history_post_asset_patches([], output_exe_name="Out.exe", build_manifest_data={}) == []
    with pytest.raises(ValueError):
        X.family_history_asset_patches(tmp_path / "c", None, {"FamilyHistory": {
            "companion_dll": S.DLL_NAME, "companion_ini": S.INI_NAME}})
    with pytest.raises(ValueError):
        X.family_history_asset_patches(tmp_path / "d", None, {"FamilyHistory": {
            "companion_dll": "other.dll", "companion_ini": S.INI_NAME}})


def test_docs_describe_the_log():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    doc = (ROOT / "docs" / "FAMILY_HISTORY.md").read_text(encoding="utf-8")
    for text in (readme, doc):
        assert "Family History" in text and "vf2history_b200.dll" in text
        assert "Experimental" in text
    for needle in ("UNCONFIRMED", "remarri", "divorce", "Twin", "Triplet", "Email Event", "Popup Event",
                   "Random Event 1", "Family Renamed 1", "Choice: A", "Earlier spouse: Bob (died|divorced)",
                   ".vf2hist", "same-sex"):
        assert needle in doc, needle


# ===================================================================== with the core exe
def test_every_site_is_proved_against_the_b200_executable():
    G.validate(core_exe_bytes())


def test_committed_header_is_a_fresh_render():
    assert (SRC / "b200history_sites.h").read_text() == G.render_header(G.validate(core_exe_bytes()))


@pytest.mark.parametrize("pin", S.PINS, ids=[p.name for p in S.PINS])
def test_a_damaged_executable_is_refused(pin):
    exe = bytearray(core_exe_bytes())
    parsed = G.Exe(bytes(exe))
    off = parsed.pe.get_offset_from_rva(pin.va - parsed.base)
    mask = G.pin_mask(pin, parsed)
    k = next(i for i in range(len(pin.bytes)) if not mask[i])
    exe[off + k] ^= 0x01
    with pytest.raises(G.SiteError):
        G.validate(bytes(exe))


def test_wrong_constants_are_refused(monkeypatch):
    exe = core_exe_bytes()
    for name, value in (("VILLAGER_STRIDE", 0x1CC08), ("FAMILY_RECORD_SIZE", 0x6CC), ("DIALOG_TITLE", 0x5C),
                        ("DIALOG_EVENT", 0x5C), ("RECORD_PARENT2", 0xE0), ("GAME_STATE_RESERVED_BABY", 0x25AA0),
                        ("VILLAGER_CARRIED", 0x6B20), ("EVENT_IS_EMAIL_VSLOT", 0x18), ("VILLAGER_NAME", 0x6A68)):
        with monkeypatch.context() as mp:
            mp.setattr(S, name, value)
            with pytest.raises(G.SiteError):
                G.validate(exe)


def _other_exes():
    out = []
    pattern = os.environ.get("VF2_B200_MATRIX_GLOB")
    if pattern:
        out += sorted(glob.glob(pattern))
    for env in ("VF2_B201_CORE_EXE", "VF2_KIDS_EXE", "VF2_HISTORY_EXE"):
        if os.environ.get(env) and Path(os.environ[env]).is_file():
            out.append(os.environ[env])
    return out


def test_every_other_executable_resolves():
    others = _other_exes()
    if not others:
        pytest.skip("no other executable given (VF2_B200_MATRIX_GLOB, VF2_B201_CORE_EXE, VF2_KIDS_EXE, VF2_HISTORY_EXE)")
    model = G.validate(core_exe_bytes())
    for path in others:
        got = G.validate_variant(Path(path).read_bytes(), model)
        assert set(got) == set(S.ADDRESS_CONSTANTS), path


# ===================================================================== the DLL under emulation
def _build(kind: str, out_dir: Path) -> Path:
    if not VCVARS or not Path(VCVARS).is_file():
        pytest.skip("VF2_VCVARS32 is not set to vcvars32.bat")
    target = RUNTIME / "build" / ("vf2history_b200_test.dll" if kind == "test" else "vf2history_b200.dll")
    r = subprocess.run(["cmd.exe", "/c", str(RUNTIME / "native" / "build_b200history.bat")] + ([kind] if kind else []),
                       capture_output=True, text=True, env=dict(os.environ))
    assert r.returncode == 0, r.stdout + r.stderr
    assert target.is_file()
    copy = out_dir / target.name
    shutil.copyfile(target, copy)
    return copy


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    core_exe_bytes()
    out = tmp_path_factory.mktemp("history")
    return {"test": _build("test", out), "release": _build("", out)}


def _scen():
    import b200_history_scenarios as scen
    return scen


def test_the_shipped_dll_has_no_test_entry_points(built):
    data = built["release"].read_bytes()
    assert b"B200History_Startup" in data and b"B200History_TestPlan" not in data
    assert b"B200History_TestPlan" in built["test"].read_bytes()


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
def test_the_plan(built, delta):
    scen = _scen()
    w = scen.HistoryWorld(CORE_EXE, built["test"], delta, install=False)
    status, writes = w.test_plan(True)
    assert status == 1 and len(writes) == len(S.CALL_HOOKS) + len(S.ENTRY_HOOKS) + 1
    calls = {w.s(name) for name in S.CALL_HOOKS}
    assert {va for va, raw, data in writes if not data and raw[0] == 0xE8} == calls
    assert [(va, raw[0]) for va, raw, data in writes if not data and raw[0] == 0xE9] == [(w.s("V_IMPREGNATE"), 0xE9)]
    assert [(va, len(raw)) for va, raw, data in writes if data] == [(w.s("GS_VTABLE") + S.GS_LOAD_VSLOT, 4)]
    status, writes = w.test_plan(False)
    assert (status, writes) == (0, [])


SCENARIOS = [f.__name__ for f in __import__("b200_history_scenarios").ALL]
OFF = [f.__name__ for f in __import__("b200_history_scenarios").OFF]


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", SCENARIOS)
def test_installed_scenarios(built, name, delta):
    scen = _scen()
    getattr(scen, name)(scen.HistoryWorld(CORE_EXE, built["test"], delta))


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", OFF)
def test_startup(built, name, delta):
    scen = _scen()
    getattr(scen, name)(scen.HistoryWorld(CORE_EXE, built["test"], delta, install=False))


def test_resolver_scans_under_the_emulator(built):
    """The real byte-by-byte ScanPattern (not the native stand-in) finds every pin."""
    scen = _scen()
    w = scen.HistoryWorld.bare(CORE_EXE, built["test"], 0x1A0000, native_scan=False)
    status, writes = w.test_plan(True)
    assert status == 1 and len(writes) == len(S.CALL_HOOKS) + len(S.ENTRY_HOOKS) + 1


@pytest.mark.parametrize("pin", ["ie_fire", "dv_divorce", "ds_marry", "v_impregnate"])
def test_an_executable_it_cannot_prove_is_left_alone(built, tmp_path, pin):
    """One pinned byte changed: the DLL plans nothing, so it writes nothing."""
    scen = _scen()
    exe = bytearray(core_exe_bytes())
    parsed = G.Exe(bytes(exe))
    p = next(x for x in S.PINS if x.name == pin)
    mask = G.pin_mask(p, parsed)
    k = next(i for i in range(len(p.bytes)) if not mask[i])
    exe[parsed.pe.get_offset_from_rva(p.va - parsed.base) + k] ^= 0x01
    damaged = tmp_path / "damaged.exe"
    damaged.write_bytes(bytes(exe))
    w = scen.HistoryWorld.bare(damaged, built["test"], 0)
    status, writes = w.test_plan(True)
    assert status == -1 and writes == []


# ===================================================================== the executable's loader
def test_the_branch_executable_has_the_byte():
    import pefile
    pe = pefile.PE(history_exe())
    sections = {s.Name.rstrip(b"\0"): s for s in pe.sections}
    flag = sections[b".vf2hist"]
    assert flag.Misc_VirtualSize == 1 and flag.get_data()[0] == 0 and flag.Characteristics & 0x80000000
    manifest = json.loads((Path(history_exe()).parent / "patch-manifest.json").read_text())
    contract = manifest["FamilyHistory"]
    assert contract["runtime_flag"]["source_section"] == ".vf2hist" and contract["companion_dll"] == S.DLL_NAME


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
def test_the_loader_end_to_end(built, delta):
    """The branch executable's own dormant loader wrapper, then the DLL it loads, then the installed hooks."""
    scen = _scen()
    scen.scenario_loader_cases(history_exe(), str(built["test"]), delta)


def test_exporter_records_drive_the_real_loader(built, tmp_path):
    scen = _scen()
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    exe = history_exe()
    manifest = json.loads((Path(exe).parent / "patch-manifest.json").read_text())
    patches = X.family_history_post_asset_patches([Path(exe)], output_exe_name="Out.exe", build_manifest_data=manifest)
    assert len(patches) == 1 and patches[0]["requires"] == ["core_executable", "family_history"]
    variant = patches[0]["variants"][0]
    data = bytearray(Path(exe).read_bytes())
    offset = int(variant["offset"], 16)
    assert data[offset] == int(variant["expected_asset_bytes"], 16) == 0 and variant["replacement_bytes"] == "01"
    import pefile
    pe = pefile.PE(data=bytes(data))
    flag = [s for s in pe.sections if s.Name.rstrip(b"\0") == b".vf2hist"][0]
    assert flag.PointerToRawData == offset
    records = X.family_history_asset_patches(tmp_path / "bundle", built["release"], manifest)
    assert [r["file_path"] for r in records] == ["Virtual Families 2 Patcher Files/vf2history_b200.dll",
                                                 "Virtual Families 2 Patcher Files/vf2history.ini"]
    for r in records:
        assert r["requires"] == ["core_executable", "family_history"] and r["remove_when_disabled"] is True
        staged = tmp_path / "bundle" / r["source_path"]
        assert hashlib.sha256(staged.read_bytes()).hexdigest() == r["source_sha256"]
    assert (tmp_path / "bundle" / records[1]["source_path"]).read_bytes() == b"[Patches]\r\nFamilyHistory=1\r\n"
    with pytest.raises(ValueError):
        X.family_history_asset_patches(tmp_path / "b2", built["test"], manifest)
    data[offset] = 1
    patched = tmp_path / "Out.exe"
    patched.write_bytes(bytes(data))
    w, _result, log = scen.run_loader(str(patched), str(built["test"]), 0, None, 1)
    assert [x for x in log if x.startswith("exe:LoadLibraryW")] == [f"exe:LoadLibraryW {scen.DLL_PATH}"]
    assert w.status()["installed"] == 1


# Each mutation of the DLL source must make the named scenario fail (the scenarios are not vacuous).
MUTATIONS = [
    ("no birth record", '        Write(slot, "Birth", Body);', "        (void)Body;", "scenario_twins"),
    ("multiples not marked", 'n == 1 ? "Single birth" : n == 2 ? "Twin" : "Triplet"', '"Single birth"',
     "scenario_triplets"),
    ("no conception record", '    Write(slot, "Conception", Body);', "    (void)Body;",
     "scenario_conception_and_birth_single"),
    ("the father lost at birth", "    bool known = Father(m, f);", "    bool known = Father(m, f) && !slot;",
     "scenario_conception_and_birth_single"),
    ("the father's looks not checked after a load",
     "        if (I32(other, HIST_PEEP_HEAD) != I32(m, HIST_VILLAGER_FATHER_HEAD) ||",
     "        if (I32(other, HIST_PEEP_HEAD) != I32(m, HIST_VILLAGER_FATHER_HEAD) &&",
     "scenario_the_father_after_a_load"),
    ("deaths twice", "    return l.valid && l.sex == p.sex && l.age == p.age && SameText(l.name, p.name, 25);",
     "    return l.valid && !l.valid && l.sex == p.sex && l.age == p.age && SameText(l.name, p.name, 25);",
     "scenario_child_dies"),
    ("no cause", '    Field(t, "  ", "Cause of death", CauseWord(cause));',
     '    Field(t, "  ", "Cause of death", CauseWord(cause - cause - 1));', "scenario_child_dies"),
    ("the wrong family role", '    Field(t, "  ", "Family role", RoleText(role));',
     '    Field(t, "  ", "Family role", RoleText(role == 1 ? 0 : role));', "scenario_spouse_dies_and_remarriage"),
    ("no widowed spouse", '    if (widowed[0]) t.S("  Current spouse of ").Name(widowed, 25).S(": (none)").NL();',
     "    (void)widowed;", "scenario_spouse_dies_and_remarriage"),
    ("a death not seen by the remarriage",
     '            } else if (SameText(kind, "Death", 16) && earlier[0] && SameText(a, earlier, 28)) {',
     '            } else if (SameText(kind, "Death", 16) && earlier[0] && SameText(a, earlier, 28) && !slot) {',
     "scenario_spouse_dies_and_remarriage"),
    ("a divorce not seen by the remarriage",
     '            } else if (SameText(kind, "Divorce", 16) && earlier[0] && SameText(b, earlier, 28)) {',
     '            } else if (SameText(kind, "Divorce", 16) && earlier[0] && SameText(b, earlier, 28) && !slot) {',
     "scenario_divorce_and_remarriage"),
    ("no remarriage", '                if (SameText(kind, "Marriage", 16) && gn == gen && (SameText(a, head, 28) || '
     'SameText(b, head, 28))) {',
     '                if (SameText(kind, "Marriage", 16) && gn == gen && !slot) {', "scenario_divorce_and_remarriage"),
    ("the married-in spouse's remarriage missed", "(SameText(a, head, 28) || SameText(b, head, 28))",
     "(SameText(a, head, 28))", "scenario_head_dies_and_the_widow_remarries"),
    ("a loss the log never saw guessed", "                    how[0] = 0;\n",
     "                    Copy(how, \"died\", 5);\n", "scenario_a_loss_the_log_never_saw_is_not_guessed"),
    ("no current spouse", '    t.S("  Current spouse of ").Name(head.name, 25).S(": ").Name(spouse.name, 25).NL();',
     "    (void)0;", "scenario_new_family_and_marriage"),
    ("the married-in side guessed by order",
     "        if (bIn) OnMarriage(pa, pb, Generations()); else OnMarriage(pb, pa, Generations());",
     "        (void)bIn;\n        OnMarriage(pa, pb, Generations());", "scenario_same_sex_marriage"),
    ("no divorce record", '    Write(slot, "Divorce", Body);', "    (void)Body;", "scenario_divorce_and_remarriage"),
    ("e-mail and pop-up swapped", '    gEventKind = email ? "Email Event" : "Popup Event";',
     '    gEventKind = email ? "Popup Event" : "Email Event";', "scenario_random_events"),
    ("choices swapped", '    if (choice >= 0) t.S("  Choice: ").S(choice ? "B" : "A").NL();',
     '    if (choice >= 0) t.S("  Choice: ").S(choice ? "A" : "B").NL();', "scenario_random_events"),
    ("no event title", "t.Name(title, sizeof(gEventTitle) - 1);", 't.S("(no title)");', "scenario_random_events"),
    ("the event's records not after it", "    if (gInEvent && !backfilled && WaitingCount",
     "    if (gInEvent && !backfilled && !slot && WaitingCount", "scenario_children_join_and_leave"),
    ("no arrival record", '    Write(slot, "Arrived", Body);', "    (void)Body;", "scenario_children_join_and_leave"),
    ("no left-home record", "    if (!was && !gInLoad) OnLeftHome((const unsigned char *)villager, why);",
     "    if (!was && !gInLoad && !villager) OnLeftHome((const unsigned char *)villager, why);",
     "scenario_children_join_and_leave"),
    ("no new generation", 'Write(slot, newFamily ? "Generation" : Word(HIST_STR_NEW_GENERATION), Body);',
     'Write(slot, "Generation", Body);', "scenario_next_generation"),
    ("no eviction record", '    Write(slot, "Evict Family", Body);', "    (void)Body;",
     "scenario_evict_then_new_family_keeps_the_log"),
    ("eviction wipes", "    bool afterEviction = Evicted();", "    bool afterEviction = Evicted() && !tree;",
     "scenario_evict_then_new_family_keeps_the_log"),
    ("no wipe for a new family", "        WipeSlot(slot);\n        CreateLog(slot);", "        CreateLog(slot);",
     "scenario_new_family_wipes_the_old_one"),
    ("Start Over keeps the log", "    if (slot) WipeSlot(slot);\n    gStartedOver = 1;",
     "    if (slot && !slot) WipeSlot(slot);\n    gStartedOver = 1;",
     "scenario_start_over_wipes_the_slot"),
    ("no Start Over record", '        if (gStartedOver) Write(slot, "Start Over",',
     '        if (gStartedOver && !slot) Write(slot, "Start Over",', "scenario_start_over_wipes_the_slot"),
    ("Backups wiped", '        if (top && dir && SameNameIgnoringCase(name, "Backups")) continue;',
     '        if (top && dir && SameNameIgnoringCase(name, "Backups") && !dir) continue;',
     "scenario_start_over_wipes_the_slot"),
    ("a rename that changes nothing logged",
     "    if (!gInLoad && name && name[0] && !SameText(p.name, name, 25)) OnRename(p, name);",
     "    if (!gInLoad && name && name[0]) OnRename(p, name);", "scenario_rename_in_the_details_box"),
    ("no rename record", '    Write(slot, "Renamed", Body);', "    (void)Body;", "scenario_rename_in_the_details_box"),
    ("no VV person form", '    t.S(deeper).S("Head: ").I(p.head).NL();', '    t.S(deeper).S("Head ").I(p.head).NL();',
     "scenario_new_family_and_marriage"),
    ("backfilled twice", "CountRecords(ReadBuffer, got)) return;", "CountRecords(ReadBuffer, got) && !slot) return;",
     "scenario_backfill_once"),
    ("no roll", "records >= HIST_HISTORY_RECORDS_PER_FILE ? newest + 1 : newest;",
     "records >= HIST_HISTORY_RECORDS_PER_FILE + 1 ? newest + 1 : newest;",
     "scenario_the_log_rolls_after_2000_records"),
    ("numbers restart in each file", "            if (v > highest && (j >= got",
     "            if (v > highest && slot < 0 && (j >= got", "scenario_numbers_continue_across_files"),
    ("installs with the setting off", '    return GetPrivateProfileIntW(L"Patches", L"FamilyHistory", 0, path) == 1;',
     '    return GetPrivateProfileIntW(L"Patches", L"FamilyHistory", 0, path) == 0;',
     "scenario_setting_off_writes_nothing"),
]


def _build_variant(source: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "b200history.cpp").write_text(source, encoding="utf-8", newline="\n")
    shutil.copyfile(SRC / "b200history_sites.h", out_dir / "b200history_sites.h")
    (out_dir / "build.bat").write_text(
        "@echo off\r\n"
        f'call "{VCVARS}" >nul || exit /b 1\r\n'
        "cl /nologo /O2 /MT /EHsc /W4 /WX /DB200HISTORY_TEST /LD /GS b200history.cpp /Fevf2history_b200_test.dll "
        "/link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1\r\n", encoding="ascii")
    r = subprocess.run(["cmd.exe", "/c", str(out_dir / "build.bat")], cwd=out_dir, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return out_dir / "vf2history_b200_test.dll"


@pytest.mark.parametrize("label,old,new,scenario", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_every_mutation_is_caught(built, tmp_path, label, old, new, scenario):
    source = (SRC / "b200history.cpp").read_text(encoding="utf-8")
    assert source.count(old) == 1, ("the mutation no longer matches the source", label)
    mutated = source.replace(old, new)
    assert mutated != source
    dll = _build_variant(mutated, tmp_path / "m")
    scen = _scen()
    fn = getattr(scen, scenario)
    with pytest.raises(AssertionError):
        fn(scen.HistoryWorld(CORE_EXE, dll, 0, install=fn not in scen.OFF))
