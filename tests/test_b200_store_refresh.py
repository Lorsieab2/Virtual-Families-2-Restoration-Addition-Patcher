"""R Refreshes the Store and All 36 Flea Market goods for the B200 executable (companion DLL vf2refresh_b200.dll).

Layers (nothing here starts the game; there is no live test):

* always: the sites module, the DLL source, the generator and the exporter agree on the names, the folder,
  the ini, the loader and the two runtime bytes (.vf2rfsh, .vf2flea); the DLL source holds no game address;
  both settings are normal Optional rows, on by default;
* with the B200 core executable (VF2_B200_CORE_EXE): capstone + pefile prove every pin and the RTTI search,
  the header is a fresh render, a damaged executable and wrong constants are refused, and every other
  executable given resolves (VF2_B200_MATRIX_GLOB, VF2_B201_CORE_EXE, VF2_KIDS_EXE, VF2_HISTORY_EXE,
  VF2_REFRESH_EXE);
* with Visual Studio as well (VF2_VCVARS32): the DLL builds with /W4 /WX, and the REAL compiled DLL runs
  inside unicorn with the REAL game code (tests/b200_refresh_scenarios.py), at the link address and
  relocated, with source mutations that each scenario must catch;
* with an executable built from this branch (VF2_REFRESH_EXE: it has the .vf2rfsh loader and the .vf2flea
  byte): the stock Flea Market (byte 0) and the 36 goods (byte 1) through the executable's own hooks, the
  executable's own loader end to end, and the exporter's records driving it.
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
SRC = RUNTIME / "native" / "b200refresh"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import b200_refresh_sites as S  # noqa: E402
import gen_b200_refresh_sites as G  # noqa: E402

CORE_EXE = os.environ.get("VF2_B200_CORE_EXE")
REFRESH_EXE = os.environ.get("VF2_REFRESH_EXE")
VCVARS = os.environ.get("VF2_VCVARS32")
DELTAS = (0, 0x1A0000)


def core_exe_bytes() -> bytes:
    if not CORE_EXE or not Path(CORE_EXE).is_file():
        pytest.skip("VF2_B200_CORE_EXE is not set to the B200 core executable")
    return Path(CORE_EXE).read_bytes()


def refresh_exe() -> str:
    if not REFRESH_EXE or not Path(REFRESH_EXE).is_file():
        pytest.skip("VF2_REFRESH_EXE is not set to an executable built from this branch (.vf2rfsh / .vf2flea)")
    return REFRESH_EXE


def _gen_text():
    return (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")


# ===================================================================== always
def test_header_is_the_sites_module():
    header = (SRC / "b200refresh_sites.h").read_text()
    for pin in (p for p in S.PINS if p.dll):
        m = re.search(r"static const unsigned char rpin_%s\[\] = \{ ([^}]*) \};" % re.escape(pin.name), header)
        assert m, pin.name
        assert bytes(int(x, 16) for x in m.group(1).split(", ")) == pin.bytes, pin.name
    for pin in (p for p in S.PINS if not p.dll):
        assert "rpin_%s[]" % pin.name not in header, "a test-only pin reached the DLL"
    for key in ("STORE_CATEGORY_FIELD", "CLOTHING_CATEGORY", "FLEA_MARKET_CATEGORY", "KEY_R_LOWER", "KEY_R_UPPER",
                "KEY_TYPE_CHARACTER", "HANDLE_KEY_VSLOT", "FLEA_NEXT_PICK_FIELD", "STATUS_MAGIC"):
        assert "#define RFSH_%s 0x%Xu" % (key, getattr(S, key)) in header, key
    assert '#define RFSH_STORE_TYPE_NAME ".?AVCScrollingStoreScene@@"' in header
    assert '#define RFSH_FLEA_FLAG_SECTION ".vf2flea"' in header
    for key in S.CORE_ONLY_CONSTANTS:
        assert "RFSH_%s " % key not in header, key
    assert re.findall(r"(?m)^    RFSH_SITE_(\w+),$", header) == list(S.ADDRESS_CONSTANTS)


def test_the_source_has_no_hard_coded_game_address():
    text = (SRC / "b200refresh.cpp").read_text()
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    found = [x for x in re.findall(r"0x[0-9A-Fa-f]{5,8}\b", text) if int(x, 16) >= 0x400000]
    assert not found, f"literal addresses in the module source: {found}"


def test_names_agree_everywhere():
    cpp = (SRC / "b200refresh.cpp").read_text()
    for needle in ('L"vf2refresh.ini"', 'L"RefreshKey"', "B200Refresh_Startup", 'L"vf2refresh.log"',
                   "MaybeUpdateOutfitsFn)SITE(MAYBE_UPDATE_OUTFITS))((void *)SITE(INVENTORY_MANAGER), true)"):
        assert needle in cpp, needle
    gen = _gen_text()
    for needle in ('STORE_REFRESH_FLAG_SECTION = ".vf2rfsh"', 'STORE_REFRESH_DLL_NAME = "vf2refresh_b200.dll"',
                   'STORE_REFRESH_INI_NAME = "vf2refresh.ini"', 'GetProcAddress(module, "B200Refresh_Startup")',
                   "if (gVF2StoreRefresh == 1) VF2LoadStoreRefreshDll();",
                   '#pragma section(".vf2rfsh", read, write)', "volatile unsigned char gVF2StoreRefresh = 0;",
                   '"__VF2_STORE_REFRESH_RELATIVE_PATH__"', "patch_store_refresh_manifest(manifest)",
                   'EXPANDED_FLEA_MARKET_FLAG_SECTION = ".vf2flea"', '#pragma section(".vf2flea", read, write)',
                   "volatile unsigned char gVF2ExpandedFleaMarket = 0;",
                   "patch_expanded_flea_market_manifest(manifest)"):
        assert needle in gen, needle
    # loaded after every other companion DLL, in the same wrapper
    assert gen.index("if (gVF2FamilyHistory == 1) VF2LoadFamilyHistoryDll();") < \
        gen.index("if (gVF2StoreRefresh == 1) VF2LoadStoreRefreshDll();")
    # the R byte is read only by the loader; the Flea Market byte only by the two expansion hooks (each count
    # includes the symbol constant and the declaration)
    assert gen.count("gVF2StoreRefresh") == 3 and gen.count("gVF2StoreRefresh ==") == 1
    assert gen.count("gVF2ExpandedFleaMarket") == 6 and gen.count("if (gVF2ExpandedFleaMarket != 1) return -1;") == 2
    assert gen.count("if (gVF2ExpandedFleaMarket != 1) return false;") == 2     # in stock, and the owned mark
    assert S.DLL_NAME == "vf2refresh_b200.dll" and S.INI_KEY == "RefreshKey" and S.INI_NAME == "vf2refresh.ini"
    assert S.PATCHER_FOLDER == "Virtual Families 2 Patcher Files" and S.FLEA_FLAG_SECTION == ".vf2flea"


def test_the_expansion_hooks_fall_through_unless_the_byte_is_1():
    gen = _gen_text()
    for fn in ("VF2GetExpandedFleaMarketCount", "VF2GetExpandedFleaMarketItem"):
        body = gen[gen.index(f'extern "C" int __cdecl {fn}('):]
        body = body[:body.index("\n}}\n")]
        assert body.index("if (category != kVF2FleaMarketCategory) return -1;") < \
            body.index("if (gVF2ExpandedFleaMarket != 1) return -1;"), fn
        # The Special Upgrades and Clothing pages are answered first, each behind its own byte.
        assert body.index("if (category == kVF2SpecialUpgradesCategory) {{") < \
            body.index("if (category != kVF2FleaMarketCategory) return -1;"), fn
        assert "if (gVF2AllOutfitsForSale == 1) return -1;" in body, fn


def test_all_36_goods_are_always_in_stock_and_owned_one_offs_keep_their_mark():
    """Owner, 2026-10-27: "Make all 36 always in stock." The GetNumAvailable hook answers 1 for all 36 goods,
    first thing and only while the byte is 1; the draw site alone asks whether a one-off is owned, for its mark."""
    sys.path.insert(0, str(ROOT / "work"))
    import patch_mobile_furniture_pack as P
    if not (P.SRC_OBJS / "InventoryManager.obj").is_file():
        pytest.skip("the desktop object files are not present")
    unlimited, one_off = P.flea_market_unlimited_goods()
    assert len(unlimited) == 33 and sorted(one_off) == [0x29, 0x33, 0x10A]
    gen = _gen_text()
    body = gen[gen.index('extern "C" int __cdecl VF2GetOutfitStoreNumAvailable(int itemId) {{'):]
    assert body.index("if (VF2FleaMarketGoodAlwaysInStock(itemId)) return 1;") < body.index("VF2MarriageEmailUnavailable")
    rule = gen[gen.index("static bool VF2FleaMarketGoodAlwaysInStock(int itemId) {{"):]
    rule = rule[:rule.index("}}\n}}") + 4]
    assert "if (gVF2ExpandedFleaMarket != 1) return false;" in rule and "{flea_goods_cases} return true;" in rule
    assert "InventoryManager" not in rule.split("{{", 1)[1], "the rule must not write or read a count"
    owned = gen[gen.index("static bool VF2FleaMarketOneOffOwned(int itemId) {{"):]
    owned = owned[:owned.index("}}\n}}") + 4]
    assert "{flea_one_off_cases} return InventoryManager.HaveUpgrade((EInventoryItem)itemId);" in owned
    draw = gen[gen.index('extern "C" int __fastcall VF2StoreDrawNumAvailable('):]
    draw = draw[:draw.index("\n}}\n")]
    assert "if (VF2FleaMarketOneOffOwned(itemId)) return 0;" in draw
    assert gen.count("VF2FleaMarketOneOffOwned(itemId)") == 1, "only the draw asks (the click keeps buying)"
    assert "if len(flea_goods) != FLEA_MARKET_GOODIES_COUNT:" in gen


def test_the_generator_manifest_contracts(monkeypatch):
    sys.path.insert(0, str(ROOT / "work"))
    import patch_mobile_furniture_pack as P
    monkeypatch.setattr(P, "flea_market_unlimited_goods", lambda: ([0x26] * 33, [0x29, 0x33, 0x10A]))   # CI has no objects
    manifest = {"TimeControls": {}}
    P.patch_store_refresh_manifest(manifest)
    c = manifest["StoreRefresh"]
    assert c["runtime_flag"]["source_section"] == ".vf2rfsh" and c["runtime_flag"]["default"] == "00"
    assert c["runtime_flag"]["enabled"] == "01" and c["runtime_flag"]["size"] == 1
    assert c["companion_dll"] == S.DLL_NAME and c["companion_ini"] == S.INI_NAME
    assert c["category"] == "optional" and c["default"] is True and c["startup_export"] == S.STARTUP
    with pytest.raises(RuntimeError):
        P.patch_store_refresh_manifest({})
    manifest = {"InventoryManager": {"expanded_flea_market": {"hooks": [{"function": "x"}]}}}
    P.patch_expanded_flea_market_manifest(manifest)
    f = manifest["ExpandedFleaMarket"]
    assert f["runtime_flag"]["source_section"] == ".vf2flea" and f["runtime_flag"]["default"] == "00"
    assert f["runtime_flag"]["enabled"] == "01" and f["default"] is False and f["category"] == "optional"
    with pytest.raises(RuntimeError):
        P.patch_expanded_flea_market_manifest({"InventoryManager": {}})


def test_exporter_settings():
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    rows = {s["id"]: s for s in X.SETTINGS}
    r, f = rows["r_refreshes_store"], rows["expanded_flea_market"]
    assert r["default"] is True and r["category"] == "optional" and r["label"] == "R Refreshes the Store"
    assert f["default"] is False and f["category"] == "optional" and f["label"] == "All 36 Flea Market goods"
    for needle in ("press R", "Shift+R", "Clothing and Hairstyles", "hairstyles", "already bought",
                   "Flea Market", "All 36 Flea Market goods", "On Sale", "outside the store", "box",
                   "Virtual Families 2 Patcher Files"):
        assert needle.lower() in r["description"].lower(), needle
    for needle in ("all 36", "5 of the 36", "6 hours of real time", "always in stock", "Towelette", "Anti-spam Software",
                   "Rockhound Certificate", "checkmark"):
        assert needle.lower() in f["description"].lower(), needle
    for sid, sec in (("r_refreshes_store", ".vf2rfsh"), ("expanded_flea_market", ".vf2flea")):
        assert X.RUNTIME_FLAG_SECTION_BY_SETTING[sid] == sec
        assert sid in X.SOURCE_BACKED_OPTIONAL_SETTINGS
    # The release profile turns on only what the table turns on (All 36 is off by default since B206).
    assert "r_refreshes_store" in X.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS
    assert "expanded_flea_market" not in X.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS
    assert X.STORE_REFRESH_INI_TEXT == "[Patches]\r\nRefreshKey=1\r\n"
    assert X.STORE_REFRESH_DLL_NAME == S.DLL_NAME and X.STORE_REFRESH_INI_NAME == S.INI_NAME


def test_a_build_without_the_new_bytes_gets_no_records(tmp_path):
    """B204 and earlier have neither contract: the exporter emits nothing for either setting there."""
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    assert X.store_refresh_asset_patches(tmp_path / "b", None, {}) == []
    assert X.store_refresh_post_asset_patches([], output_exe_name="Out.exe", build_manifest_data={}) == []
    assert X.expanded_flea_market_post_asset_patches([], output_exe_name="Out.exe", build_manifest_data={}) == []
    with pytest.raises(ValueError):
        X.store_refresh_asset_patches(tmp_path / "c", None, {"StoreRefresh": {
            "companion_dll": S.DLL_NAME, "companion_ini": S.INI_NAME}})
    with pytest.raises(ValueError):
        X.store_refresh_asset_patches(tmp_path / "d", None, {"StoreRefresh": {
            "companion_dll": "other.dll", "companion_ini": S.INI_NAME}})


def test_docs_describe_both_settings():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    log = (ROOT / "Transparency Log.txt").read_text(encoding="utf-8")
    howto = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
    for text in (readme, log, howto):
        assert "R Refreshes the Store" in text and "All 36 Flea Market goods" in text
    for text in (readme, log):
        assert "vf2refresh_b200.dll" in text and ".vf2flea" in text


# ===================================================================== with the core exe
def test_every_site_is_proved_against_the_b200_executable():
    G.validate(core_exe_bytes())


def test_committed_header_is_a_fresh_render():
    assert (SRC / "b200refresh_sites.h").read_text() == G.render_header(G.validate(core_exe_bytes()))


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


def test_a_second_store_type_name_is_refused():
    exe = bytearray(core_exe_bytes())
    name = b".?AVCScrollingStoreScene@@\0"
    i = exe.find(name)
    j = exe.find(b".?AVCFamilyTreeScene@@\0")
    assert i > 0 and j > 0
    exe[j:j + len(name)] = name                    # a second descriptor with the store's name
    with pytest.raises(G.SiteError):
        G.store_vtable(G.Exe(bytes(exe)))


def test_wrong_constants_are_refused(monkeypatch):
    exe = core_exe_bytes()
    for name, value in (("STORE_CATEGORY_FIELD", 0xD8), ("CLOTHING_CATEGORY", 0x0E), ("FLEA_MARKET_CATEGORY", 0x0E),
                        ("OUTFIT_REPICK_DELAY", 0x3841), ("FLEA_NEXT_PICK_FIELD", 0x49C), ("HANDLE_KEY_VSLOT", 3),
                        ("KEY_ESC", 0x3E9), ("FLEA_REPICK_DELAY", 0x5461)):
        with monkeypatch.context() as mp:
            mp.setattr(S, name, value)
            if name == "HANDLE_KEY_VSLOT":
                mp.setattr(S, "STORE_SLOT_HANDLE_KEY", S.STORE_VTABLE + 4 * value)
            with pytest.raises(G.SiteError):
                G.validate(exe)


def _other_exes():
    out = []
    pattern = os.environ.get("VF2_B200_MATRIX_GLOB")
    if pattern:
        out += sorted(glob.glob(pattern))
    for env in ("VF2_B201_CORE_EXE", "VF2_KIDS_EXE", "VF2_HISTORY_EXE", "VF2_REFRESH_EXE"):
        if os.environ.get(env) and Path(os.environ[env]).is_file():
            out.append(os.environ[env])
    return out


def test_every_other_executable_resolves():
    others = _other_exes()
    if not others:
        pytest.skip("no other executable given (VF2_B200_MATRIX_GLOB, VF2_B201_CORE_EXE, VF2_KIDS_EXE, "
                    "VF2_HISTORY_EXE, VF2_REFRESH_EXE)")
    model = G.validate(core_exe_bytes())
    for path in others:
        got = G.validate_variant(Path(path).read_bytes(), model)
        assert set(S.ADDRESS_CONSTANTS) <= set(got), path


# ===================================================================== the DLL under emulation
def _build(kind: str, out_dir: Path) -> Path:
    if not VCVARS or not Path(VCVARS).is_file():
        pytest.skip("VF2_VCVARS32 is not set to vcvars32.bat")
    target = RUNTIME / "build" / ("vf2refresh_b200_test.dll" if kind == "test" else "vf2refresh_b200.dll")
    r = subprocess.run(["cmd.exe", "/c", str(RUNTIME / "native" / "build_b200refresh.bat")] + ([kind] if kind else []),
                       capture_output=True, text=True, env=dict(os.environ))
    assert r.returncode == 0, r.stdout + r.stderr
    assert target.is_file()
    copy = out_dir / target.name
    shutil.copyfile(target, copy)
    return copy


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    core_exe_bytes()
    out = tmp_path_factory.mktemp("refresh")
    return {"test": _build("test", out), "release": _build("", out)}


def _scen():
    import b200_refresh_scenarios as scen
    return scen


def _exes():
    """The executables the installed scenarios run in: the B200 core, and this branch's build when given."""
    out = [("core", lambda: CORE_EXE)]
    out.append(("branch", refresh_exe))
    return out


def test_the_shipped_dll_has_no_test_entry_points(built):
    data = built["release"].read_bytes()
    assert b"B200Refresh_Startup" in data and b"B200Refresh_TestPlan" not in data
    assert b"B200Refresh_TestPlan" in built["test"].read_bytes()


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
def test_the_plan(built, delta):
    scen = _scen()
    w = scen.World(CORE_EXE, built["test"], delta, install=False)
    status, writes = w.test_plan(True)
    assert status == 1 and len(writes) == 1
    assert writes[0]["va"] == w.s("STORE_SLOT_HANDLE_KEY") and writes[0]["data"] and writes[0]["len"] == 4
    assert w.test_plan(False) == (0, [])


SCENARIOS = [f.__name__ for f in __import__("b200_refresh_scenarios").ALL]
FLEA_STOCK = [f.__name__ for f in __import__("b200_refresh_scenarios").FLEA_STOCK]
OFF = [f.__name__ for f in __import__("b200_refresh_scenarios").OFF]


@pytest.mark.parametrize("exe", ["core", "branch"])
@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", SCENARIOS)
def test_installed_scenarios(built, name, delta, exe):
    scen = _scen()
    path = CORE_EXE if exe == "core" else refresh_exe()
    getattr(scen, name)(scen.World(path, built["test"], delta))


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", FLEA_STOCK)
def test_the_stock_flea_market(built, name, delta):
    """The branch executable's own .vf2flea gate: byte 0 is the stock Flea Market, and R picks it again."""
    scen = _scen()
    getattr(scen, name)(scen.World(refresh_exe(), built["test"], delta))


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", OFF)
def test_startup(built, name, delta):
    scen = _scen()
    getattr(scen, name)(scen.World(CORE_EXE, built["test"], delta, install=False))


def test_resolver_scans_under_the_emulator(built):
    """The real byte-by-byte ScanPattern and NextDword (not the native stand-ins) find every pin and the vtable."""
    scen = _scen()
    w = scen.World(CORE_EXE, built["test"], 0x1A0000, install=False, native_scan=False)
    status, writes = w.test_plan(True)
    assert status == 1 and len(writes) == 1 and writes[0]["va"] == w.s("STORE_SLOT_HANDLE_KEY")


@pytest.mark.parametrize("pin", [p.name for p in S.PINS if p.dll])
def test_an_executable_it_cannot_prove_is_left_alone(built, tmp_path, pin):
    """One pinned byte changed: the DLL plans nothing, so it writes nothing (R stays the game's own)."""
    scen = _scen()
    exe = bytearray(core_exe_bytes())
    parsed = G.Exe(bytes(exe))
    p = next(x for x in S.PINS if x.name == pin)
    mask = G.pin_mask(p, parsed)
    k = next(i for i in range(len(p.bytes)) if not mask[i])
    exe[parsed.pe.get_offset_from_rva(p.va - parsed.base) + k] ^= 0x01
    damaged = tmp_path / "damaged.exe"
    damaged.write_bytes(bytes(exe))
    w = scen.World.bare(damaged, built["test"], 0)
    status, writes = w.test_plan(True)
    assert status == -1 and writes == []


def test_a_store_vtable_it_cannot_prove_is_left_alone(built, tmp_path):
    """The store's HandleKey slot pointing elsewhere: the DLL refuses to install."""
    scen = _scen()
    exe = bytearray(core_exe_bytes())
    parsed = G.Exe(bytes(exe))
    off = parsed.pe.get_offset_from_rva(S.STORE_SLOT_HANDLE_KEY - parsed.base)
    exe[off:off + 4] = (S.STORE_HANDLE_KEY + 0x10).to_bytes(4, "little")
    damaged = tmp_path / "slot.exe"
    damaged.write_bytes(bytes(exe))
    w = scen.World.bare(damaged, built["test"], 0)
    assert w.test_plan(True) == (-1, [])


# ===================================================================== the executable's loader and bytes
def test_the_branch_executable_has_both_bytes():
    import pefile
    pe = pefile.PE(refresh_exe())
    sections = {s.Name.rstrip(b"\0"): s for s in pe.sections}
    for name in (b".vf2rfsh", b".vf2flea"):
        flag = sections[name]
        assert flag.Misc_VirtualSize == 1 and flag.get_data()[0] == 0 and flag.Characteristics & 0x80000000, name
    manifest = json.loads((Path(refresh_exe()).parent / "patch-manifest.json").read_text())
    assert manifest["StoreRefresh"]["runtime_flag"]["source_section"] == ".vf2rfsh"
    assert manifest["StoreRefresh"]["companion_dll"] == S.DLL_NAME
    assert manifest["ExpandedFleaMarket"]["runtime_flag"]["source_section"] == ".vf2flea"


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
def test_the_loader_end_to_end(built, delta):
    """The branch executable's own dormant loader wrapper, then the DLL it loads, then R."""
    _scen().scenario_loader_cases(refresh_exe(), str(built["test"]), delta)


def test_exporter_records_drive_the_real_loader_and_the_flea_byte(built, tmp_path):
    scen = _scen()
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    exe = refresh_exe()
    manifest = json.loads((Path(exe).parent / "patch-manifest.json").read_text())
    data = bytearray(Path(exe).read_bytes())
    import pefile
    pe = pefile.PE(data=bytes(data))
    offsets = {}
    for fn, sid, sec in ((X.store_refresh_post_asset_patches, "r_refreshes_store", b".vf2rfsh"),
                         (X.expanded_flea_market_post_asset_patches, "expanded_flea_market", b".vf2flea")):
        patches = fn([Path(exe)], output_exe_name="Out.exe", build_manifest_data=manifest)
        assert len(patches) == 1 and patches[0]["requires"] == ["core_executable", sid]
        variant = patches[0]["variants"][0]
        offset = int(variant["offset"], 16)
        assert data[offset] == int(variant["expected_asset_bytes"], 16) == 0 and variant["replacement_bytes"] == "01"
        flag = [s for s in pe.sections if s.Name.rstrip(b"\0") == sec][0]
        assert flag.PointerToRawData == offset
        offsets[sid] = offset
    records = X.store_refresh_asset_patches(tmp_path / "bundle", built["release"], manifest)
    assert [r["file_path"] for r in records] == ["Virtual Families 2 Patcher Files/vf2refresh_b200.dll",
                                                 "Virtual Families 2 Patcher Files/vf2refresh.ini"]
    for r in records:
        assert r["requires"] == ["core_executable", "r_refreshes_store"] and r["remove_when_disabled"] is True
        staged = tmp_path / "bundle" / r["source_path"]
        assert hashlib.sha256(staged.read_bytes()).hexdigest() == r["source_sha256"]
    assert (tmp_path / "bundle" / records[1]["source_path"]).read_bytes() == b"[Patches]\r\nRefreshKey=1\r\n"
    with pytest.raises(ValueError):
        X.store_refresh_asset_patches(tmp_path / "b2", built["test"], manifest)
    # the patcher's defaults: both bytes 1
    data[offsets["r_refreshes_store"]] = 1
    data[offsets["expanded_flea_market"]] = 1
    patched = tmp_path / "Out.exe"
    patched.write_bytes(bytes(data))
    w, _result, _state, log = scen.run_loader(str(patched), str(built["test"]), 0, None, 1)
    assert [x for x in log if x.startswith("exe:LoadLibraryW")] == [f"exe:LoadLibraryW {scen.DLL_PATH}"]
    assert w.status()["installed"] == 1
    w.page(scen.FLEA)
    assert w.item_count() == 36
    w.clear()
    # R always runs the game's own Flea Market pick; the page keeps listing all 36
    assert w.key(scen.TYPE_CHAR, ord("r")) == 1 and w.randoms == [36] * 36 and w.item_count() == 36


# Each mutation of the DLL source must make the named scenario fail (the scenarios are not vacuous).
MUTATIONS = [
    ("no lower-case r", "(code == (int)RFSH_KEY_R_LOWER || code == (int)RFSH_KEY_R_UPPER)",
     "(code == (int)RFSH_KEY_R_UPPER)", "scenario_r_redraws_the_clothing_page"),
    ("no Shift+R", "(code == (int)RFSH_KEY_R_LOWER || code == (int)RFSH_KEY_R_UPPER)",
     "(code == (int)RFSH_KEY_R_LOWER)", "scenario_shift_r_is_the_same"),
    ("the draw not forced", "((void *)SITE(INVENTORY_MANAGER), true);", "((void *)SITE(INVENTORY_MANAGER), false);",
     "scenario_r_redraws_the_clothing_page"),
    ("every page redraws the outfits", "if (category == (int)RFSH_CLOTHING_CATEGORY) {",
     "if (category != (int)RFSH_FLEA_MARKET_CATEGORY) {", "scenario_other_pages_are_left_alone"),
    ("a key press read as R", "if (type == (int)RFSH_KEY_TYPE_CHARACTER &&", "if (type != 7 &&",
     "scenario_other_keys_are_the_games"),
    ("the game's own handler skipped", "    return ((HandleKeyFn)SITE(STORE_HANDLE_KEY))(scene, type, code, sym);",
     "    return sym == 0x7FFFFFFF;", "scenario_other_keys_are_the_games"),
    ("the wrong slot", "    StoreSlot = vt + 4 * RFSH_HANDLE_KEY_VSLOT;", "    StoreSlot = vt + 4 * (RFSH_HANDLE_KEY_VSLOT + 1);",
     "scenario_only_the_store_slot_is_written"),
    ("installs with the setting off", '    return GetPrivateProfileIntW(L"Patches", L"RefreshKey", 0, path) == 1;',
     '    return GetPrivateProfileIntW(L"Patches", L"RefreshKey", 0, path) == 0;', "scenario_setting_off_writes_nothing"),
    ("R left alone with all 36 on (the old rule)", "    if (!FleaFlag) return false;",
     "    if (!FleaFlag || *FleaFlag != 0) return false;", "scenario_all_36_r_then_every_good_stays_buyable"),
    ("R left alone with all 36 on, the byte flipped", "    if (!FleaFlag) return false;",
     "    if (!FleaFlag || *FleaFlag != 0) return false;", "scenario_byte_one_lists_all_36_again"),
    ("R redraws without the byte", "    if (!FleaFlag) return false;", "    if (!SITE(INVENTORY_MANAGER)) return false;",
     "scenario_flea_market_r_with_all_36_listed"),
    ("the pick not called (all 36 on)",
     "    ((MaybeUpdateRotatingItemsFn)SITE(MAYBE_UPDATE_ROTATING))((void *)SITE(INVENTORY_MANAGER));\n", "",
     "scenario_all_36_r_then_every_good_stays_buyable"),
    ("the pick not called (the byte 1 on the stock exe test)",
     "    ((MaybeUpdateRotatingItemsFn)SITE(MAYBE_UPDATE_ROTATING))((void *)SITE(INVENTORY_MANAGER));\n", "",
     "scenario_byte_one_lists_all_36_again"),
    ("the page not listed again", "    ((SetStoreCategoryFn)SITE(SET_STORE_CATEGORY))(scene, (int)RFSH_FLEA_MARKET_CATEGORY);\n",
     "    (void)scene;\n", "scenario_stock_flea_market_r_picks_five_new_goods"),
    ("the stock pick not made due", "    *next = 0;\n", "    *next = *next;\n",
     "scenario_stock_flea_market_r_picks_five_new_goods"),
    ("the pick not made due with all 36 on", "    *next = 0;\n", "    *next = *next;\n",
     "scenario_all_36_r_then_every_good_stays_buyable"),
    ("the old clock not put back", "    if (*next == 0) *next = saved;", "    (void)saved;",
     "scenario_stock_flea_market_clock_at_zero_changes_nothing"),
    ("the Flea Market page never redraws", "if (category == (int)RFSH_FLEA_MARKET_CATEGORY && RedrawFleaMarket(scene))",
     "if (category == (int)RFSH_CLOTHING_CATEGORY && RedrawFleaMarket(scene))",
     "scenario_stock_flea_market_r_picks_five_new_goods"),
    ("the clothing draw skipped with all 36 on", "        if (category == (int)RFSH_CLOTHING_CATEGORY) {",
     "        if (category == (int)RFSH_CLOTHING_CATEGORY && !(FleaFlag && *FleaFlag == 1)) {",
     "scenario_stock_flea_market_clothing_r_is_unchanged"),
]


def _build_variant(source: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "b200refresh.cpp").write_text(source, encoding="utf-8", newline="\n")
    shutil.copyfile(SRC / "b200refresh_sites.h", out_dir / "b200refresh_sites.h")
    (out_dir / "build.bat").write_text(
        "@echo off\r\n"
        f'call "{VCVARS}" >nul || exit /b 1\r\n'
        "cl /nologo /O2 /MT /EHsc /W4 /WX /DB200REFRESH_TEST /LD /GS b200refresh.cpp /Fevf2refresh_b200_test.dll "
        "/link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO || exit /b 1\r\n", encoding="ascii")
    r = subprocess.run(["cmd.exe", "/c", str(out_dir / "build.bat")], cwd=out_dir, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return out_dir / "vf2refresh_b200_test.dll"


@pytest.mark.parametrize("label,old,new,scenario", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_every_mutation_is_caught(built, tmp_path, label, old, new, scenario):
    scen = _scen()
    fn = getattr(scen, scenario)
    exe = refresh_exe() if fn in scen.FLEA_STOCK else CORE_EXE
    source = (SRC / "b200refresh.cpp").read_text(encoding="utf-8")
    assert source.count(old) == 1, ("the mutation no longer matches the source", label)
    mutated = source.replace(old, new)
    assert mutated != source
    dll = _build_variant(mutated, tmp_path / "m")
    with pytest.raises(AssertionError):
        fn(scen.World(exe, dll, 0, install=fn not in scen.OFF))
