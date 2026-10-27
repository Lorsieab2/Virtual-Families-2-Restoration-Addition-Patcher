"""Outfit Pictures for the B200 executable (companion DLL vf2outfits_b200.dll, part of Fix Vanilla Game Bugs).

The stock bug: every Male Outfit and every Female Outfit in the tool tray shows, and puts on, the picture of
the last one bought (runtime/b200_outfits_sites.py proves every step). The DLL keeps each tray place's own
picture, and a sidecar beside each save.

Layers (nothing here starts the game; there is no live test):

* always: the sites module, the DLL source, the generator and the exporter agree on the names, the folder,
  the ini and the loader; the DLL source holds no game address; the fix rides Fix Vanilla Game Bugs;
* with the B200 core executable (VF2_B200_CORE_EXE): capstone + pefile prove every pin, the header is a
  fresh render, a damaged executable and wrong constants are refused, and every other executable given
  resolves (VF2_B200_MATRIX_GLOB, VF2_B201_CORE_EXE, VF2_KIDS_EXE, VF2_HISTORY_EXE, VF2_OUTFITS_EXE);
* with Visual Studio as well (VF2_VCVARS32): the DLL builds with /W4 /WX, and the REAL compiled DLL runs
  inside unicorn with the REAL game code reaching every hook from its live caller
  (tests/b200_outfits_scenarios.py), at the link address and relocated: the stock bug without the DLL, each
  outfit's own picture with it (draw, the outfit in the hand, both swaps, putting it on, save, load, an old
  save, a damaged, a foreign, a locked and a briefly locked sidecar, the backup slot, a tool-edited save, the
  patcher's own expansion outfits), with source mutations that each scenario must catch;
* with an executable built from this branch (VF2_OUTFITS_EXE: it has the loader): the executable's own
  loader end to end, and the exporter's records driving it.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
SRC = RUNTIME / "native" / "b200outfits"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import b200_outfits_sites as S  # noqa: E402
import gen_b200_outfits_sites as G  # noqa: E402

CORE_EXE = os.environ.get("VF2_B200_CORE_EXE")
OUTFITS_EXE = os.environ.get("VF2_OUTFITS_EXE")
VCVARS = os.environ.get("VF2_VCVARS32")
DELTAS = (0, 0x1A0000)


def core_exe_bytes() -> bytes:
    if not CORE_EXE or not Path(CORE_EXE).is_file():
        pytest.skip("VF2_B200_CORE_EXE is not set to the B200 core executable")
    return Path(CORE_EXE).read_bytes()


def outfits_exe() -> str:
    if not OUTFITS_EXE or not Path(OUTFITS_EXE).is_file():
        pytest.skip("VF2_OUTFITS_EXE is not set to an executable built from this branch (it has the loader)")
    return OUTFITS_EXE


# ===================================================================== always
def test_header_is_the_sites_module():
    header = (SRC / "b200outfits_sites.h").read_text()
    for pin in S.PINS:
        m = re.search(r"static const unsigned char opin_%s\[\] = \{ ([^}]*) \};" % re.escape(pin.name), header)
        assert m, pin.name
        assert bytes(int(x, 16) for x in m.group(1).split(", ")) == pin.bytes, pin.name
    for key in ("TRAY_HELD", "INV_MALE_PICTURE", "INV_FEMALE_PICTURE", "TRAY_ITEM_LIMIT", "STATUS_MAGIC",
                "SIDECAR_VERSION", "PICTURE_LIMIT"):
        assert "#define OUTF_%s 0x%Xu" % (key, getattr(S, key)) in header
    for key in S.CORE_ONLY_CONSTANTS:
        assert "OUTF_%s " % key not in header, key


def test_the_source_has_no_hard_coded_game_address():
    text = (SRC / "b200outfits.cpp").read_text()
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    found = [x for x in re.findall(r"0x[0-9A-Fa-f]{5,8}\b", text) if int(x, 16) >= 0x400000]
    assert not found, f"literal addresses in the module source: {found}"


def test_names_agree_everywhere():
    cpp = (SRC / "b200outfits.cpp").read_text()
    for needle in ('L"vf2outfits.ini"', 'L"OutfitPictures"', "B200Outfits_Startup", 'L"vf2outfits.log"',
                   '"Virtual Families 2 Patcher Data\\\\Outfits\\\\"', '"VF2OUTFT"', "'V', 'F', '2', 'O', 'U', 'T', 'F', 'T'"):
        assert needle in cpp, needle
    gen = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    for needle in ('OUTFIT_PICTURES_DLL_NAME = "vf2outfits_b200.dll"', 'OUTFIT_PICTURES_INI_NAME = "vf2outfits.ini"',
                   "OUTFIT_PICTURES_FLAG_SECTION = VANILLA_BUGS_FLAG_SECTION",
                   'GetProcAddress(module, "B200Outfits_Startup")',
                   "if (gVF2FixVanillaGameBugs == 1) VF2LoadOutfitPicturesDll();",
                   '"__VF2_OUTFIT_PICTURES_RELATIVE_PATH__"', "patch_outfit_pictures_manifest(manifest)"):
        assert needle in gen, needle
    # loaded last, in the same wrapper, after every other companion DLL
    for other in ("if (gVF2TimeControls == 1) VF2LoadTimeControlsDll();",
                  "if (gVF2UpTo28Children == 1) VF2LoadUpTo28ChildrenDll();",
                  "if (gVF2FamilyHistory == 1) VF2LoadFamilyHistoryDll();"):
        assert gen.index(other) < gen.index("if (gVF2FixVanillaGameBugs == 1) VF2LoadOutfitPicturesDll();")
    assert gen.index("    patch_fix_vanilla_game_bugs(manifest)\n") < gen.index("    patch_outfit_pictures_manifest(manifest)\n")
    assert gen.index("    patch_family_history_manifest(manifest)\n") < gen.index("    patch_outfit_pictures_manifest(manifest)\n")
    assert gen.count("VF2LoadOutfitPicturesDll") == 2
    assert S.DLL_NAME == "vf2outfits_b200.dll" and S.INI_KEY == "OutfitPictures" and S.INI_NAME == "vf2outfits.ini"
    assert S.PATCHER_FOLDER == "Virtual Families 2 Patcher Files" and S.DATA_FOLDER == "Virtual Families 2 Patcher Data"
    bat = (RUNTIME / "native" / "build_b200outfits.bat").read_text()
    assert "/W4 /WX" in bat and "/DB200OUTFITS_TEST" in bat and "vf2outfits_b200" in bat


def test_the_generator_manifest_contract():
    sys.path.insert(0, str(ROOT / "work"))
    import patch_mobile_furniture_pack as P
    manifest = {"TimeControls": {}, "FixVanillaGameBugs": {"fixes": ["TitleMenuRefresh"]}}
    P.patch_outfit_pictures_manifest(manifest)
    c = manifest["OutfitPictures"]
    assert c["runtime_flag"]["source_section"] == ".vf2bugs" and c["offline_patcher_setting"] == "fix_vanilla_game_bugs"
    assert c["companion_dll"] == S.DLL_NAME and c["companion_ini"] == S.INI_NAME
    assert c["category"] == "main" and c["default"] is True and c["save_format"] == "unchanged"
    assert manifest["FixVanillaGameBugs"]["fixes"] == ["TitleMenuRefresh"], "the menu fixes' list is left alone"
    with pytest.raises(RuntimeError):
        P.patch_outfit_pictures_manifest({"TimeControls": {}})
    with pytest.raises(RuntimeError):
        P.patch_outfit_pictures_manifest({"FixVanillaGameBugs": {}})


def test_exporter_setting():
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    rows = [s for s in X.SETTINGS if s["id"] == "fix_vanilla_game_bugs"]
    assert len(rows) == 1
    s = rows[0]
    assert s["default"] is True and s["category"] == "main" and s["label"] == "Fix Vanilla Game Bugs"
    for needle in ("Male Outfit and Female Outfit", "last one bought", "Virtual Families 2 Patcher Data\\Outfits",
                   "save file itself is not changed", "vf2outfits_b200.dll", "Virtual Families 2 Patcher Files"):
        assert needle in s["description"], needle
    assert X.RUNTIME_FLAG_SECTION_BY_SETTING["fix_vanilla_game_bugs"] == ".vf2bugs"
    assert "outfit" not in " ".join(X.RUNTIME_FLAG_SECTION_BY_SETTING), "no setting of its own"
    assert X.OUTFIT_PICTURES_INI_TEXT == "[Patches]\r\nOutfitPictures=1\r\n"
    assert X.OUTFIT_PICTURES_DLL_NAME == S.DLL_NAME and X.OUTFIT_PICTURES_INI_NAME == S.INI_NAME


def test_a_build_without_the_loader_gets_no_records(tmp_path):
    """The B204 executables first published (and earlier) have no OutfitPictures contract."""
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    assert X.outfit_pictures_asset_patches(tmp_path / "b", None, {}) == []
    good = {"companion_dll": S.DLL_NAME, "companion_ini": S.INI_NAME, "offline_patcher_setting": "fix_vanilla_game_bugs",
            "runtime_flag": {"source_section": ".vf2bugs"}}
    with pytest.raises(ValueError):
        X.outfit_pictures_asset_patches(tmp_path / "c", None, {"OutfitPictures": good})
    for bad in ({**good, "companion_dll": "other.dll"}, {**good, "runtime_flag": {"source_section": ".vf2outf"}},
                {**good, "offline_patcher_setting": "time_controls"}):
        with pytest.raises(ValueError):
            X.outfit_pictures_asset_patches(tmp_path / "d", tmp_path / S.DLL_NAME, {"OutfitPictures": bad})


def test_docs_describe_the_fix():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    log = (ROOT / "Transparency Log.txt").read_text(encoding="utf-8")
    dlog = (ROOT / "docs" / "Transparency Log.txt").read_text(encoding="utf-8")
    for text in (readme, log, dlog):
        assert "vf2outfits_b200.dll" in text and "Outfits" in text


# ===================================================================== with the core exe
def test_every_site_is_proved_against_the_b200_executable():
    G.validate(core_exe_bytes())


def test_committed_header_is_a_fresh_render():
    assert (SRC / "b200outfits_sites.h").read_text() == G.render_header(G.validate(core_exe_bytes()))


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
    for name, value in (("TRAY_HELD", 0xA4), ("INV_MALE_PICTURE", 0x500), ("INV_FEMALE_PICTURE", 0x470),
                        ("TRAY_ITEM_LIMIT", 0xE0), ("TRAY_PLACES", 10), ("MALE_OUTFIT", 0x48),
                        ("DRAW_CASE_MALE", 0x34), ("DRAW_CASE_FEMALE", 0x1D), ("INV_BIND_FIRST", 0x44C),
                        ("TRAY_FIRST_FREE", 1), ("VILLAGER_BODY", 0x6A80), ("GS_SAVE_VSLOT", 0x3C),
                        ("TRAY_TOP", 0x84), ("TRAY_DRAW_OFFSET", 7)):
        with monkeypatch.context() as mp:
            mp.setattr(S, name, value)
            with pytest.raises(G.SiteError):
                G.validate(exe)


def test_a_second_caller_is_refused(monkeypatch):
    """SwapSlots and GetOutfit must have no caller the DLL does not hook."""
    exe = core_exe_bytes()
    model = G.validate(exe)
    parsed = G.Exe(exe)
    real = G.calls_to
    with monkeypatch.context() as mp:
        mp.setattr(G, "calls_to", lambda e, t: real(e, t) + [0x401000])
        with pytest.raises(G.SiteError):
            G.resolve(parsed, model)


def _other_exes():
    out = []
    pattern = os.environ.get("VF2_B200_MATRIX_GLOB")
    if pattern:
        out += sorted(p for p in glob.glob(pattern) if "logs" not in Path(p).parent.name)
    for env in ("VF2_B201_CORE_EXE", "VF2_KIDS_EXE", "VF2_HISTORY_EXE", "VF2_OUTFITS_EXE"):
        if os.environ.get(env) and Path(os.environ[env]).is_file():
            out.append(os.environ[env])
    return out


def test_every_other_executable_resolves():
    others = _other_exes()
    if not others:
        pytest.skip("no other executable given (VF2_B200_MATRIX_GLOB, VF2_B201_CORE_EXE, VF2_KIDS_EXE, "
                    "VF2_HISTORY_EXE, VF2_OUTFITS_EXE)")
    model = G.validate(core_exe_bytes())
    for path in others:
        got = G.validate_variant(Path(path).read_bytes(), model)
        assert set(got) == set(S.ADDRESS_CONSTANTS), path


# ===================================================================== the DLL under emulation
def _build(kind: str, out_dir: Path) -> Path:
    if not VCVARS or not Path(VCVARS).is_file():
        pytest.skip("VF2_VCVARS32 is not set to vcvars32.bat")
    target = RUNTIME / "build" / ("vf2outfits_b200_test.dll" if kind == "test" else "vf2outfits_b200.dll")
    r = subprocess.run(["cmd.exe", "/c", str(RUNTIME / "native" / "build_b200outfits.bat")] + ([kind] if kind else []),
                       capture_output=True, text=True, env=dict(os.environ))
    assert r.returncode == 0, r.stdout + r.stderr
    assert target.is_file()
    copy = out_dir / target.name
    shutil.copyfile(target, copy)
    return copy


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    core_exe_bytes()
    out = tmp_path_factory.mktemp("outfits")
    return {"test": _build("test", out), "release": _build("", out)}


def _scen():
    import b200_outfits_scenarios as scen
    return scen


def test_the_shipped_dll_has_no_test_entry_points(built):
    data = built["release"].read_bytes()
    assert b"B200Outfits_Startup" in data and b"B200Outfits_TestPlan" not in data
    assert b"B200Outfits_TestPlan" in built["test"].read_bytes()


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
def test_the_plan(built, delta):
    scen = _scen()
    w = scen.OutfitWorld(CORE_EXE, built["test"], delta, install=False)
    status, writes = w.test_plan(True)
    assert status == 1 and len(writes) == len(S.CALL_HOOKS) + 2
    assert {va for va, raw, data in writes if not data} == {w.s(name) for name in S.CALL_HOOKS}
    assert all(raw[0] == 0xE8 for va, raw, data in writes if not data)
    assert sorted(va for va, raw, data in writes if data) == sorted(
        [w.s("GS_VTABLE") + S.GS_LOAD_VSLOT, w.s("GS_VTABLE") + S.GS_SAVE_VSLOT])
    status, writes = w.test_plan(False)
    assert (status, writes) == (0, [])


SCENARIOS = [f.__name__ for f in __import__("b200_outfits_scenarios").ALL]
STOCK = [f.__name__ for f in __import__("b200_outfits_scenarios").STOCK]
OFF = [f.__name__ for f in __import__("b200_outfits_scenarios").OFF]
FACTORY = [f.__name__ for f in __import__("b200_outfits_scenarios").FACTORY]


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", STOCK)
def test_the_stock_bug(built, name, delta):
    scen = _scen()
    getattr(scen, name)(scen.OutfitWorld(CORE_EXE, built["test"], delta, install=False))


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", SCENARIOS)
def test_installed_scenarios(built, name, delta):
    scen = _scen()
    getattr(scen, name)(scen.OutfitWorld(CORE_EXE, built["test"], delta))


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", FACTORY)
def test_against_the_stock_game(built, name, delta):
    scen = _scen()
    getattr(scen, name)(lambda install: scen.OutfitWorld(CORE_EXE, built["test"], delta, install=install))


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", OFF)
def test_startup(built, name, delta):
    scen = _scen()
    getattr(scen, name)(scen.OutfitWorld(CORE_EXE, built["test"], delta, install=False))


def test_resolver_scans_under_the_emulator(built):
    """The real byte-by-byte ScanPattern (not the native stand-in) finds every pin."""
    scen = _scen()
    w = scen.OutfitWorld.bare(CORE_EXE, built["test"], 0x1A0000, native_scan=False)
    status, writes = w.test_plan(True)
    assert status == 1 and len(writes) == len(S.CALL_HOOKS) + 2


@pytest.mark.parametrize("pin", ["st_buy", "tt_draw", "tt_swap", "ms_apply", "inv_draw_outfits", "tt_load_state"])
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
    w = scen.OutfitWorld.bare(damaged, built["test"], 0)
    status, writes = w.test_plan(True)
    assert status == -1 and writes == []


def test_a_draw_table_that_moved_is_refused(built, tmp_path):
    """DrawItem's switch no longer sending 49h to the +468h case: nothing is planned."""
    scen = _scen()
    exe = bytearray(core_exe_bytes())
    parsed = G.Exe(bytes(exe))
    table = S.CORE_VALUES["DRAW_CASE_BYTES"] + S.MALE_OUTFIT - S.DRAW_FIRST_CASE
    off = parsed.pe.get_offset_from_rva(table - parsed.base)
    exe[off] = exe[off + 1]                                # 49h now takes 4Ah's case
    damaged = tmp_path / "table.exe"
    damaged.write_bytes(bytes(exe))
    with pytest.raises(G.SiteError):
        G.validate(bytes(exe))
    w = scen.OutfitWorld.bare(damaged, built["test"], 0)
    status, writes = w.test_plan(True)
    assert status == -1 and writes == []


# ===================================================================== the executable's loader
def test_the_branch_executable_has_the_loader():
    exe = Path(outfits_exe())
    data = exe.read_bytes()
    assert "Virtual Families 2 Patcher Files\\vf2outfits_b200.dll".encode("ascii") in data
    assert b"B200Outfits_Startup" in data
    manifest = json.loads((exe.parent / "patch-manifest.json").read_text())
    contract = manifest["OutfitPictures"]
    assert contract["runtime_flag"]["source_section"] == ".vf2bugs" and contract["companion_dll"] == S.DLL_NAME


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
def test_the_loader_end_to_end(built, delta):
    """The branch executable's own loader wrapper, then the DLL it loads, then the installed hooks."""
    scen = _scen()
    scen.scenario_loader_cases(outfits_exe(), str(built["test"]), delta)


def test_exporter_records_drive_the_real_loader(built, tmp_path):
    scen = _scen()
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    exe = outfits_exe()
    manifest = json.loads((Path(exe).parent / "patch-manifest.json").read_text())
    patches = X.fix_vanilla_game_bugs_post_asset_patches([Path(exe)], output_exe_name="Out.exe",
                                                         build_manifest_data=manifest)
    assert len(patches) == 1 and patches[0]["requires"] == ["core_executable", "fix_vanilla_game_bugs"]
    variant = patches[0]["variants"][0]
    data = bytearray(Path(exe).read_bytes())
    offset = int(variant["offset"], 16)
    assert data[offset] == 0 and variant["replacement_bytes"] == "01"
    records = X.outfit_pictures_asset_patches(tmp_path / "bundle", built["release"], manifest)
    assert [r["file_path"] for r in records] == ["Virtual Families 2 Patcher Files/vf2outfits_b200.dll",
                                                 "Virtual Families 2 Patcher Files/vf2outfits.ini"]
    for r in records:
        assert r["requires"] == ["core_executable", "fix_vanilla_game_bugs"] and r["remove_when_disabled"] is True
        staged = tmp_path / "bundle" / r["source_path"]
        assert hashlib.sha256(staged.read_bytes()).hexdigest() == r["source_sha256"]
    assert (tmp_path / "bundle" / records[1]["source_path"]).read_bytes() == b"[Patches]\r\nOutfitPictures=1\r\n"
    with pytest.raises(ValueError):
        X.outfit_pictures_asset_patches(tmp_path / "b2", built["test"], manifest)
    data[offset] = 1
    patched = tmp_path / "Out.exe"
    patched.write_bytes(bytes(data))
    w, _result, log = scen.run_loader(str(patched), str(built["test"]), 0, None, 1)
    assert [x for x in log if x.startswith("exe:LoadLibraryW")] == [f"exe:LoadLibraryW {scen.DLL_PATH}"]
    assert w.status()["installed"] == 1


# Each mutation of the DLL source must make the named scenario fail (the scenarios are not vacuous).
MUTATIONS = [
    ("no picture kept at the buy", "        if (IsOutfit(item) && IsPicture(*Field(item))) p.picture = *Field(item);",
     "        (void)item;", "scenario_each_outfit_keeps_its_picture"),
    ("the picture not lent to the draw", "    *field = picture;\n", "    (void)picture;\n",
     "scenario_each_outfit_keeps_its_picture"),
    ("the field not put back", "    *field = kept;\n", "    (void)kept;\n",
     "scenario_a_used_place_forgets_and_a_new_buy_remembers"),
    ("the wrong tray place", "    int place = rel / h;\n", "    int place = rel / h + 1;\n",
     "scenario_each_outfit_keeps_its_picture"),
    ("the outfit in the hand not its own", "    DrawPlace(NextDrawInHand, inventory, I32(Tray(), OUTF_TRAY_HELD),",
     "    DrawPlace(NextDrawInHand, inventory, -1,", "scenario_the_one_in_the_hand_shows_and_puts_on_its_own"),
    ("a swap not followed", "    if (swaps && a < (int)OUTF_TRAY_PLACES", "    if (swaps && a < 0",
     "scenario_a_click_swap_moves_the_pictures"),
    ("a drop swap not followed", "static void __fastcall SwapDrop(void *tray, void *, int a, int b) { SwapPlaces(NextSwapDrop, tray, a, b); }",
     "static void __fastcall SwapDrop(void *tray, void *, int a, int b) { NextSwapDrop(tray, a, b); }",
     "scenario_a_drag_and_drop_moves_the_pictures"),
    ("the stock outfit put on", "        if (picture >= 0) {\n            ++B200Outfits_Status.applied;",
     "        if (picture >= 1000) {\n            ++B200Outfits_Status.applied;",
     "scenario_the_one_in_the_hand_shows_and_puts_on_its_own"),
    ("a spent place not forgotten", "        if (Places[k].picture >= 0 && Places[k].item != TrayItem(k)) {",
     "        if (Places[k].picture >= 0 && Places[k].item != TrayItem(k) && k > 100) {",
     "scenario_a_new_family_forgets"),
    ("no sidecar written", "    if (HashFile(save, &hash, &size) == FILE_OK && WriteSidecar(path, folder, hash, size)) {",
     "    if (HashFile(save, &hash, &size) == FILE_SHUT && WriteSidecar(path, folder, hash, size)) {",
     "scenario_save_and_load_keep_the_pictures"),
    ("the hash not checked", "    if (r == FILE_OK && hashed && Loaded.saveHash == hash && Loaded.saveSize == size && Binds(Loaded)) {",
     "    if (r == FILE_OK && hashed && Binds(Loaded)) {", "scenario_a_tool_edited_save_keeps_the_pictures"),
    ("another tray's pictures taken", "    if (r == FILE_OK && Binds(Loaded)) {", "    if (r == FILE_OK) {",
     "scenario_another_saves_sidecar_is_not_used"),
    ("a damaged sidecar left in place", "        bool moved = MoveAside(path);", "        bool moved = false;",
     "scenario_a_damaged_sidecar_is_moved_aside"),
    ("no checksum", "    if (Get32(FileBuffer + kFileSize - 8) != (unsigned)sum || Get32(FileBuffer + kFileSize - 4) != (unsigned)(sum >> 32))\n        return FILE_DAMAGED;\n",
     "    (void)sum;\n", "scenario_a_damaged_sidecar_is_moved_aside"),
    ("no version check", "    if (Get32(FileBuffer + 8) != OUTF_SIDECAR_VERSION || Get32(FileBuffer + 20) != kFileSize) return FILE_DAMAGED;",
     "    if (Get32(FileBuffer + 20) != kFileSize) return FILE_DAMAGED;", "scenario_a_wrong_version_or_picture_is_damaged"),
    ("a picture on a place that is no outfit", "        if (picture != -1 && (!IsOutfit(item) || !IsPicture(picture))) return FILE_DAMAGED;",
     "        if (picture != -1 && (item < -1000000 || !IsPicture(picture))) return FILE_DAMAGED;",
     "scenario_a_wrong_version_or_picture_is_damaged"),
    ("a locked sidecar replaced", "    if (mine == FILE_SHUT || ShutSlot == slot) {", "    if (mine == FILE_SHUT && ShutSlot == slot && slot > 100) {",
     "scenario_a_locked_sidecar_is_never_replaced"),
    ("the backup's sidecar not rotated", "        if (clear) MoveFileExA(path, backup, 0);", "        (void)clear;",
     "scenario_the_backup_slot_follows_its_save"),
    ("the backup's sidecar not read", "        Adopt(backupFile);", "        (void)backupFile;",
     "scenario_the_backup_slot_follows_its_save"),
    ("a load does not forget", "    Forget();\n    bool loaded = NextLoad(state, slot);", "    bool loaded = NextLoad(state, slot);",
     "scenario_a_failed_load_forgets"),
    ("a settings save rotates", "    if (slot <= 0) return NextSave(state, slot);            // the settings file",
     "    if (slot < 0) return NextSave(state, slot);            // the settings file",
     "scenario_settings_saves_and_loads_are_left_alone"),
    ("installs with the setting off", '    return GetPrivateProfileIntW(L"Patches", L"OutfitPictures", 0, path) == 1;',
     '    return GetPrivateProfileIntW(L"Patches", L"OutfitPictures", 0, path) == 0;', "scenario_setting_off_writes_nothing"),
]


def _build_variant(source: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "b200outfits.cpp").write_text(source, encoding="utf-8", newline="\n")
    shutil.copyfile(SRC / "b200outfits_sites.h", out_dir / "b200outfits_sites.h")
    (out_dir / "build.bat").write_text(
        "@echo off\r\n"
        f'call "{VCVARS}" >nul || exit /b 1\r\n'
        "cl /nologo /O2 /MT /EHsc /W4 /WX /DB200OUTFITS_TEST /LD /GS b200outfits.cpp /Fevf2outfits_b200_test.dll "
        "/link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1\r\n", encoding="ascii")
    r = subprocess.run(["cmd.exe", "/c", str(out_dir / "build.bat")], cwd=out_dir, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return out_dir / "vf2outfits_b200_test.dll"


@pytest.mark.parametrize("label,old,new,scenario", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_every_mutation_is_caught(built, tmp_path, label, old, new, scenario):
    source = (SRC / "b200outfits.cpp").read_text(encoding="utf-8")
    assert source.count(old) == 1, ("the mutation no longer matches the source", label)
    mutated = source.replace(old, new)
    assert mutated != source
    dll = _build_variant(mutated, tmp_path / "m")
    scen = _scen()
    fn = getattr(scen, scenario)
    with pytest.raises(AssertionError):
        fn(scen.OutfitWorld(CORE_EXE, dll, 0, install=fn not in scen.OFF))
