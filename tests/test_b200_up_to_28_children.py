"""Up to 28 Children for the B200 executable (companion DLL vf2kids_b200.dll).

Layers (nothing here starts the game; there is no live test):

* always: the sites module, the DLL source, the generator and the exporter agree on the names, the
  numbers (28 / 6 / 22), the sidecar convention and the owner's description sentence; the DLL source
  holds no game address;
* with the retail executable (VF2_VANILLA_EXE, else work/vanilla_runtime_payload): the retail game has
  the same Family Tree layout, six-child cap, save block and twin / triplet rule;
* with the B200 core executable (VF2_B200_CORE_EXE): capstone + pefile prove every pin, the header
  is a fresh render, a damaged executable is refused, and every other executable given resolves
  (VF2_B200_MATRIX_GLOB, VF2_B201_CORE_EXE, VF2_KIDS_EXE);
* with an executable built from this branch (VF2_KIDS_EXE: it has the .vf2kidt table and the loader)
  AND Visual Studio (VF2_VCVARS32): the DLL builds with /W4 /WX, and the REAL compiled DLL runs inside
  unicorn with the REAL game code (tests/b200_kids_scenarios.py), at the link address and relocated.
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
SRC = RUNTIME / "native" / "b200kids"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import b200_kids_sites as S  # noqa: E402
import gen_b200_kids_sites as G  # noqa: E402

CORE_EXE = os.environ.get("VF2_B200_CORE_EXE")
KIDS_EXE = os.environ.get("VF2_KIDS_EXE")
VCVARS = os.environ.get("VF2_VCVARS32")
DELTAS = (0, 0x1A0000)
OWNER_SENTENCE = ("Virtual Families 2 can natively support up to 30 villagers per generation; any more will "
                  "start overwriting Family Tree entries and glitch the game.")


def core_exe_bytes() -> bytes:
    if not CORE_EXE or not Path(CORE_EXE).is_file():
        pytest.skip("VF2_B200_CORE_EXE is not set to the B200 core executable")
    return Path(CORE_EXE).read_bytes()


def kids_exe() -> str:
    if not KIDS_EXE or not Path(KIDS_EXE).is_file():
        pytest.skip("VF2_KIDS_EXE is not set to an executable built from this branch")
    return KIDS_EXE


def vanilla_exe_bytes() -> bytes:
    path = os.environ.get("VF2_VANILLA_EXE") or str(ROOT / "work" / "vanilla_runtime_payload" / "Virtual Families 2.exe")
    if not Path(path).is_file():
        pytest.skip("no retail Virtual Families 2.exe (VF2_VANILLA_EXE or work/vanilla_runtime_payload)")
    return Path(path).read_bytes()


# ===================================================================== always
def test_the_owners_numbers():
    assert S.MAX_CHILDREN == 28 and S.TREE_CHILDREN == 6 and S.MAX_EXTRA_CHILDREN == 22
    assert S.HOUSEHOLD_SLOTS == 30 and 2 + S.MAX_CHILDREN == S.HOUSEHOLD_SLOTS
    # the stock record: six children end exactly at the next generation's record
    assert S.RECORD_CHILDREN + S.TREE_CHILDREN * S.PEEP_RECORD_SIZE == S.FAMILY_RECORD_SIZE
    assert 4 + S.TREE_GENERATIONS * S.FAMILY_RECORD_SIZE == 0xE3B4 - 0x1840


def test_header_is_the_sites_module():
    header = (SRC / "b200kids_sites.h").read_text()
    for pin in S.PINS:
        m = re.search(r"static const unsigned char kpin_%s\[\] = \{ ([^}]*) \};" % re.escape(pin.name), header)
        assert m, pin.name
        assert bytes(int(x, 16) for x in m.group(1).split(", ")) == pin.bytes, pin.name
    for key in ("MAX_CHILDREN", "MAX_EXTRA_CHILDREN", "VILLAGER_STRIDE", "TABLE_MAGIC", "SIDECAR_VERSION"):
        assert "#define KIDS_%s 0x%Xu" % (key, getattr(S, key)) in header
    for key in S.CORE_ONLY_CONSTANTS:
        assert "KIDS_%s " % key not in header, key


def test_the_source_has_no_hard_coded_game_address():
    text = (SRC / "b200kids.cpp").read_text()
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    found = [x for x in re.findall(r"0x[0-9A-Fa-f]{5,8}\b", text)
             if int(x, 16) >= 0x400000 and x.lower() not in ("0x434b3242u", "0xcbf29ce484222325", "0x100000001b3")]
    assert not found, f"literal addresses in the module source: {found}"


def test_names_agree_everywhere():
    cpp = (SRC / "b200kids.cpp").read_text()
    assert "UpTo28Children" in cpp and "vf2kids.ini" in cpp and "B200Kids_Startup" in cpp
    assert "Virtual Families 2 Patcher Data\\\\Children\\\\" in cpp
    assert "'.', 'v', 'f', '2', 'k', 'i', 'd', 't'" in cpp
    gen = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    for needle in ('UP_TO_28_CHILDREN_FLAG_SECTION = ".vf2kids"', 'UP_TO_28_CHILDREN_TABLE_SECTION = ".vf2kidt"',
                   'UP_TO_28_CHILDREN_DLL_NAME = "vf2kids_b200.dll"', 'UP_TO_28_CHILDREN_INI_NAME = "vf2kids.ini"',
                   'GetProcAddress(module, "B200Kids_Startup")', "0x544B3256u, 1u, 0,",
                   "if (gVF2UpTo28Children == 1) VF2LoadUpTo28ChildrenDll();",
                   "return FamilyTree.EmptyOffspringSlots() <= 0;",
                   "return VF2IsExtraChildSlot(peepId);"):
        assert needle in gen, needle
    # the kids DLL loads after the Time Controls DLL, in the same wrapper
    assert gen.index("if (gVF2TimeControls == 1) VF2LoadTimeControlsDll();") < \
        gen.index("if (gVF2UpTo28Children == 1) VF2LoadUpTo28ChildrenDll();")
    assert S.TABLE_MAGIC == 0x544B3256 and S.DLL_NAME == "vf2kids_b200.dll" and S.INI_KEY == "UpTo28Children"


def test_the_six_child_private_time_test_is_unchanged_with_the_setting_off():
    """B200's Behavior Patches 'six children' test now asks EmptyOffspringSlots; stock that is 6 - the
    same +1B4h count it read before, so with the DLL absent it is the same test."""
    gen = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    body = gen[gen.index("static bool VF2IsBehaviorSixChildPrivateTimeMarriage() {"):]
    body = body[:body.index("\n}\n")]
    assert "FamilyTree.GetCurrentFamily()" in body and "if (!family) return false;" in body
    assert "*(int *)(family + 0x1B4) >= 6" not in body


def test_exporter_setting():
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    setting = [s for s in X.SETTINGS if s["id"] == "up_to_28_children"]
    assert len(setting) == 1
    s = setting[0]
    # on by default: the owner's standing rule in this repository (EveryPatchDefaultsOn)
    assert s["default"] is True and s["category"] == "optional" and s["label"] == "Up to 28 Children"
    assert OWNER_SENTENCE in s["description"]
    for needle in ("only the first 6", "28", "twin", "triplet", "Next Generation", "Virtual Families 2 Patcher Data"):
        assert needle.lower() in s["description"].lower(), needle
    assert X.RUNTIME_FLAG_SECTION_BY_SETTING["up_to_28_children"] == ".vf2kids"
    assert "up_to_28_children" in X.SOURCE_BACKED_OPTIONAL_SETTINGS
    assert "up_to_28_children" in X.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS
    assert X.UP_TO_28_CHILDREN_INI_TEXT == "[Patches]\r\nUpTo28Children=1\r\n"


def test_docs_carry_the_owners_sentence():
    for doc in (ROOT / "README.md", ROOT / "docs" / "Transparency Log.txt", ROOT / "Transparency Log.txt"):
        text = doc.read_text(encoding="utf-8")
        assert OWNER_SENTENCE in re.sub(r"\s+", " ", text), doc


# ===================================================================== the retail game
def test_the_retail_game_has_the_same_layout():
    data = vanilla_exe_bytes()
    assert hashlib.sha256(data).hexdigest() == S.VANILLA_EXE_SHA256
    exe = G.Exe(data)
    md = G._md()
    for va, hexbytes, operands, note in S.VANILLA_EVIDENCE:
        want = bytes.fromhex(hexbytes)
        assert exe.read(va, len(want)) == want, note
        got = set()
        insns = list(md.disasm(want, va))
        assert sum(i.size for i in insns) == len(want), note
        for i in insns:
            for op in i.operands:
                if op.type == 2:     # immediate
                    got.add(op.imm & 0xFFFFFFFF)
                elif op.type == 3:   # memory
                    got.add(op.mem.disp & 0xFFFFFFFF)
        for v in operands:
            assert (v & 0xFFFFFFFF) in got, (note, hex(v))
    # Impregnate's first call is EmptyOffspringSlots, as in B200
    assert G.call_target(exe, S.VANILLA_IMPREGNATE_EMPTY_CALL) == S.VANILLA_EMPTY_OFFSPRING


# ===================================================================== with the core exe
def test_every_site_is_proved_against_the_b200_executable():
    G.validate(core_exe_bytes())


def test_committed_header_is_a_fresh_render():
    assert (SRC / "b200kids_sites.h").read_text() == G.render_header(G.validate(core_exe_bytes()))


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
    for name, value in (("FAMILY_TREE", S.FAMILY_TREE + 4), ("VILLAGER_MANAGER", S.VILLAGER_MANAGER + 4),
                        ("GAME_STATE_INSTANCE", S.GAME_STATE_INSTANCE + 4), ("VILLAGER_STRIDE", 0x1CC08),
                        ("RECORD_CHILD_COUNT", 0x1B0), ("FAMILY_RECORD_SIZE", 0x6CC),
                        ("GAME_STATE_RESERVED_BABY", 0x25AB4)):
        with monkeypatch.context() as mp:
            mp.setattr(S, name, value)
            with pytest.raises(G.SiteError):
                G.validate(exe)


def test_a_branch_into_stolen_bytes_is_refused(monkeypatch):
    exe = core_exe_bytes()
    with monkeypatch.context() as mp:
        hooks = dict(S.HOOKS)
        hooks["AD_GET_NEXT"] = ("wrap", 11)      # would end inside the next instruction
        mp.setattr(S, "HOOKS", hooks)
        with pytest.raises(G.SiteError):
            G.validate(exe)


def _other_exes():
    out = []
    pattern = os.environ.get("VF2_B200_MATRIX_GLOB")
    if pattern:
        out += sorted(glob.glob(pattern))
    for env in ("VF2_B201_CORE_EXE", "VF2_KIDS_EXE"):
        if os.environ.get(env) and Path(os.environ[env]).is_file():
            out.append(os.environ[env])
    return out


def test_every_other_executable_resolves():
    others = _other_exes()
    if not others:
        pytest.skip("no other executable given (VF2_B200_MATRIX_GLOB, VF2_B201_CORE_EXE, VF2_KIDS_EXE)")
    model = G.validate(core_exe_bytes())
    for path in others:
        got = G.validate_variant(Path(path).read_bytes(), model)
        assert set(got) == set(S.ADDRESS_CONSTANTS), path


def test_the_branch_executable_has_the_table_and_the_byte():
    import pefile
    pe = pefile.PE(kids_exe())
    sections = {s.Name.rstrip(b"\0"): s for s in pe.sections}
    flag, table = sections[b".vf2kids"], sections[b".vf2kidt"]
    assert flag.Misc_VirtualSize == 1 and flag.get_data()[0] == 0 and flag.Characteristics & 0x80000000
    raw = table.get_data()
    magic, version, count = struct.unpack_from("<IIi", raw, 0)
    assert (magic, version, count) == (S.TABLE_MAGIC, S.TABLE_VERSION, 0)
    assert struct.unpack_from("<22i", raw, 12) == (-1,) * 22
    assert table.Characteristics & 0x80000000 and table.Misc_VirtualSize >= 12 + 22 * 4
    manifest = json.loads((Path(kids_exe()).parent / "patch-manifest.json").read_text())
    contract = manifest["UpTo28Children"]
    assert contract["runtime_flag"]["source_section"] == ".vf2kids" and contract["default"] is True
    assert contract["companion_dll"] == S.DLL_NAME and contract["children_per_generation"] == 28


# ===================================================================== the DLL under emulation
def _build(kind: str, out_dir: Path) -> Path:
    if not VCVARS or not Path(VCVARS).is_file():
        pytest.skip("VF2_VCVARS32 is not set to vcvars32.bat")
    target = RUNTIME / "build" / ("vf2kids_b200_test.dll" if kind == "test" else "vf2kids_b200.dll")
    env = dict(os.environ)
    r = subprocess.run(["cmd.exe", "/c", str(RUNTIME / "native" / "build_b200kids.bat")] + ([kind] if kind else []),
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert target.is_file()
    copy = out_dir / target.name
    shutil.copyfile(target, copy)
    return copy


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    kids_exe()
    core_exe_bytes()
    out = tmp_path_factory.mktemp("kids")
    return {"test": _build("test", out), "release": _build("", out)}


def _scen():
    import b200_kids_scenarios as scen
    return scen


def test_the_shipped_dll_has_no_test_entry_points(built):
    data = built["release"].read_bytes()
    assert b"B200Kids_Startup" in data and b"B200Kids_TestPlan" not in data
    assert b"B200Kids_TestPlan" in built["test"].read_bytes()


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
def test_the_plan(built, delta):
    scen = _scen()
    w = scen.KidsWorld(kids_exe(), built["test"], delta, install=False)
    status, writes = w.test_plan(True)
    assert status == 1 and len(writes) == len(S.HOOKS)
    entries = {w.s(name) for name in S.HOOKS}
    assert {va for va, _raw in writes} == entries
    assert all(raw[0] == 0xE9 for _va, raw in writes)
    status, writes = w.test_plan(False)
    assert (status, writes) == (0, [])


SCENARIOS = [f.__name__ for f in __import__("b200_kids_scenarios").ALL]
FACTORY = [f.__name__ for f in __import__("b200_kids_scenarios").FACTORY]
OFF = [f.__name__ for f in __import__("b200_kids_scenarios").OFF]


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", SCENARIOS)
def test_installed_scenarios(built, name, delta):
    scen = _scen()
    getattr(scen, name)(scen.KidsWorld(kids_exe(), built["test"], delta))


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", FACTORY)
def test_birth_scenarios(built, name, delta):
    scen = _scen()
    getattr(scen, name)(lambda: scen.KidsWorld(kids_exe(), built["test"], delta))


@pytest.mark.parametrize("name", OFF)
def test_setting_off_is_stock(built, name):
    scen = _scen()
    getattr(scen, name)(scen.KidsWorld(kids_exe(), built["test"], 0x1A0000, install=False))


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
def test_the_loader_end_to_end(built, delta):
    """The branch executable's own dormant loader wrapper, then the DLL it loads, then the installed hooks."""
    scen = _scen()
    scen.scenario_loader_cases(kids_exe(), str(built["test"]), delta)


def test_exporter_records_drive_the_real_loader(built, tmp_path):
    """The exporter's .vf2kids toggle and DLL / ini records, applied to the branch executable, make the real
    loader load and install; the executable as built does not."""
    scen = _scen()
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    exe = kids_exe()
    manifest = json.loads((Path(exe).parent / "patch-manifest.json").read_text())
    patches = X.up_to_28_children_post_asset_patches([Path(exe)], output_exe_name="Out.exe",
                                                       build_manifest_data=manifest)
    assert len(patches) == 1 and patches[0]["requires"] == ["core_executable", "up_to_28_children"]
    variant = patches[0]["variants"][0]
    data = bytearray(Path(exe).read_bytes())
    offset = int(variant["offset"], 16)
    assert data[offset] == int(variant["expected_asset_bytes"], 16) == 0 and variant["replacement_bytes"] == "01"
    import pefile
    pe = pefile.PE(data=bytes(data))
    flag = [s for s in pe.sections if s.Name.rstrip(b"\0") == b".vf2kids"][0]
    assert flag.PointerToRawData == offset
    records = X.up_to_28_children_asset_patches(tmp_path / "bundle", built["release"], manifest)
    assert [r["file_path"] for r in records] == ["Virtual Families 2 Patcher Files/vf2kids_b200.dll",
                                                 "Virtual Families 2 Patcher Files/vf2kids.ini"]
    for r in records:
        assert r["requires"] == ["core_executable", "up_to_28_children"] and r["remove_when_disabled"] is True
        staged = tmp_path / "bundle" / r["source_path"]
        assert hashlib.sha256(staged.read_bytes()).hexdigest() == r["source_sha256"]
    assert (tmp_path / "bundle" / records[1]["source_path"]).read_bytes() == b"[Patches]\r\nUpTo28Children=1\r\n"
    with pytest.raises(ValueError):
        X.up_to_28_children_asset_patches(tmp_path / "b2", built["test"], manifest)
    with pytest.raises(ValueError):
        X.up_to_28_children_asset_patches(tmp_path / "b3", None, manifest)
    assert X.up_to_28_children_asset_patches(tmp_path / "b4", None, {}) == []
    assert X.up_to_28_children_post_asset_patches([Path(exe)], output_exe_name="Out.exe",
                                                  build_manifest_data={}) == []


# Each mutation of the DLL source must make the named scenario fail (the scenarios are not vacuous).
MUTATIONS = [
    ("free-slot cap dropped", "    return room < free ? room : free;\n}", "    (void)free;\n    return room;\n}",
     "scenario_free_slots_cap"),
    ("28 becomes 29", "    int room = (int)KIDS_MAX_CHILDREN - born;", "    int room = (int)KIDS_MAX_CHILDREN + 1 - born;",
     "scenario_limit_counts_lifetime_births"),
    ("no reused-slot invalidation",
     "        if (Extras[i].slot == slot && Extras[i].state == STATE_ALIVE) Extras[i].state = STATE_GONE;",
     "        if (Extras[i].slot == slot && Extras[i].state == 99) Extras[i].state = STATE_GONE;",
     "scenario_rename_and_reused_slot"),
    ("no restore of the swapped child", "    if (v) Copy(v, ChildImage, KIDS_VILLAGER_STRIDE);\n    Next.swapped = -1;",
     "    (void)v;\n    Next.swapped = -1;", "scenario_full_house"),
    ("the save sees the clone", "        Copy(v, ChildImage, KIDS_VILLAGER_STRIDE);\n    }\n    bool saved",
     "    }\n    bool saved", "scenario_full_house"),
    ("no backup sidecar", "    if (hashed && SidecarPath(state, slot + (int)KIDS_SAVE_BACKUP_OFFSET",
     "    if (false && hashed && SidecarPath(state, slot + (int)KIDS_SAVE_BACKUP_OFFSET", "scenario_sidecar_follows_backup"),
    ("deaths not recorded", "                Extras[i].state = STATE_DEAD;", "                (void)0;",
     "scenario_deaths_count_toward_28"),
    ("no sweep", "        if (Extras[i].state == STATE_ALIVE && !Matches(Extras[i])) {",
     "        if (Extras[i].state == 99 && !Matches(Extras[i])) {", "scenario_rename_and_reused_slot"),
    ("unreadable overwritten", "        MoveAside(path);\n        B200Kids_Status.lastLoad = 5;",
     "        (void)&MoveAside;\n        B200Kids_Status.lastLoad = 5;", "scenario_unreadable_sidecar_is_kept_aside"),
    ("extras never candidates",
     "        if (Extras[i].state == STATE_ALIVE && Matches(Extras[i])) Next.sources[n++] = Extras[i].slot;",
     "        if (Extras[i].state == 99) Next.sources[n++] = Extras[i].slot;", "scenario_next_generation_candidates"),
    ("a clone into the child's own slot by the stock route", "    if (free >= 0 && free != source)",
     "    if (free >= 0 || free != source)", "scenario_full_house"),
    ("extras survive a new generation", "    if (started) ClearExtras();", "    (void)started;",
     "scenario_next_generation_candidates"),
    ("rename not followed", "            CopyName(e.name, name);", "            (void)name;", "scenario_rename_and_reused_slot"),
    ("dead entries dropped on an exact load", "        if (!exact && e.state != STATE_ALIVE) continue;",
     "        if (e.state != STATE_ALIVE) continue;", "scenario_sidecar_round_trip"),
]


def _build_variant(source: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "b200kids.cpp").write_text(source, encoding="utf-8", newline="\n")
    shutil.copyfile(SRC / "b200kids_sites.h", out_dir / "b200kids_sites.h")
    (out_dir / "build.bat").write_text(
        "@echo off\r\n"
        f'call "{VCVARS}" >nul || exit /b 1\r\n'
        "cl /nologo /O2 /MT /EHsc /W4 /WX /DB200KIDS_TEST /LD /GS b200kids.cpp /Fevf2kids_b200_test.dll "
        "/link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1\r\n", encoding="ascii")
    r = subprocess.run(["cmd.exe", "/c", str(out_dir / "build.bat")], cwd=out_dir, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return out_dir / "vf2kids_b200_test.dll"


@pytest.mark.parametrize("label,old,new,scenario", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_every_mutation_is_caught(built, tmp_path, label, old, new, scenario):
    source = (SRC / "b200kids.cpp").read_text(encoding="utf-8")
    assert source.count(old) == 1, ("the mutation no longer matches the source", label)
    mutated = source.replace(old, new)
    assert mutated != source
    dll = _build_variant(mutated, tmp_path / "m")
    scen = _scen()
    fn = getattr(scen, scenario)
    with pytest.raises(AssertionError):
        if fn in scen.FACTORY:
            fn(lambda: scen.KidsWorld(kids_exe(), dll, 0))
        else:
            fn(scen.KidsWorld(kids_exe(), dll, 0))


def test_the_dll_refuses_an_executable_without_the_table(built):
    """The B200 core executable has the functions but not the .vf2kidt table: nothing is planned."""
    scen = _scen()
    w = scen.KidsWorld.__new__(scen.KidsWorld)
    from b200_time_emu import Emu
    w.e = Emu(CORE_EXE, built["test"], 0)
    w.delta = 0
    w.model, w.sites, w.pin_locs = scen.proved(CORE_EXE)
    w._native_scan()
    status, writes = w.test_plan(True)
    assert status == -1 and writes == []


def test_resolver_scans_under_the_emulator(built):
    """The real byte-by-byte ScanPattern (not the native stand-in) finds every pin."""
    scen = _scen()
    w = scen.KidsWorld.__new__(scen.KidsWorld)
    from b200_time_emu import Emu
    w.e = Emu(kids_exe(), built["test"], 0x1A0000)
    w.delta = 0x1A0000
    status, writes = w.test_plan(True)
    assert status == 1 and len(writes) == len(S.HOOKS)
