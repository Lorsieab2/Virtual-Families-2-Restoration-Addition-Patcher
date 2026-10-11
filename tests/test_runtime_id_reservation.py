"""ID-reservation experiment: can a feature's added table entries (achievement
rows, the Achievements-screen order, string ids) live in DLL-owned storage,
installed at runtime into the VANILLA Virtual Families 2 executable, with the
same ids and the same saved game as B200's link-time append?

Proved feature: B200's Holiday Ornaments achievement "Ornamentologist" (id
0x5F), module `ornament_achievement`, on the shared registry module
`id_registry`; plus `achievement_records` (B200's LoadState change, which is
what lets a save written with the feature on load with it off).

Layers (the same as the Stage 1 tests):

* always: the sites are in the sites module, with the registry's values being
  B200's own (read from the generator source and, for the ids, computed by
  importing the generator in a subprocess);
* with the vanilla game (VF2_VANILLA_RUNTIME_DIR): every pin and the
  completeness of the reader lists are proved by gen_sites (see the Stage 1
  tests), and the reservation sweep shows which B200 ids move with the
  toggles;
* with the vanilla game AND Visual Studio x86: the real DLL and the real
  stock functions run in runtime/tests/idres_harness.cpp.
"""
from __future__ import annotations

import itertools
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "tools"))

import vf2_runtime_sites as S  # noqa: E402
import vf2_runtime_patcher as P  # noqa: E402
import gen_sites  # noqa: E402

VANILLA_DIR = os.environ.get("VF2_VANILLA_RUNTIME_DIR")
VCVARS = os.environ.get(
    "VF2_VCVARS32",
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat",
)
GENERATOR = ROOT / "work" / "patch_mobile_furniture_pack.py"
DLL_SOURCE = RUNTIME / "native" / "vf2fun" / "vf2fun.cpp"
HARNESS_SOURCE = RUNTIME / "tests" / "idres_harness.cpp"

ORNAMENT_ID = 0x5F
STOCK_ORDER = [*range(0x4D), 0x5D, 0x5E, *range(0x4D, 0x5D)]


def vanilla_bytes() -> bytes:
    if not VANILLA_DIR:
        pytest.skip("VF2_VANILLA_RUNTIME_DIR is not set")
    exe = Path(VANILLA_DIR) / S.VANILLA_EXE_NAME
    if not exe.is_file():
        pytest.skip(f"{exe} not found")
    return exe.read_bytes()


def vanilla_image() -> gen_sites.Image:
    return gen_sites.Image(vanilla_bytes())


# ------------------------------------------------------------ B200 values
def _b200_values() -> dict:
    """The generator's own numbers for the Ornamentologist row, computed by
    importing it in a subprocess (it reads its settings from the environment
    at import time; all features on, as in the default build)."""
    script = (
        "import json, sys\n"
        "sys.path.insert(0, %r)\n"
        "import patch_mobile_furniture_pack as g\n"
        "print(json.dumps({\n"
        "  'id': g.HOLIDAY_ORNAMENT_ACHIEVEMENT_ID, 'target': g.HOLIDAY_ORNAMENT_ACHIEVEMENT_TARGET,\n"
        "  'icon': g.CUSTOM_ACHIEVEMENT_ICON_ID,\n"
        "  'title_id': g.holiday_ornament_achievement_title_string_id(),\n"
        "  'desc_id': g.holiday_ornament_achievement_desc_string_id(),\n"
        "  'stock_string_max_plus_1': g.ORIG_STRING_ONE_PAST_MAX,\n"
        "  'last_custom_id': g.CUSTOM_ACHIEVEMENT_LAST_ID,\n"
        "  'record_scratch': g.MOBILE_RENOVATION_PERSISTENT_RECORD_ID,\n"
        "  'reserved_first': g.CUSTOM_ACHIEVEMENT_RESERVED_FIRST_ID,\n"
        "  'rows': [g.ACHIEVEMENT_ROW_SIZE],\n"
        "}))\n" % str(ROOT / "work")
    )
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("VF2_ENABLE_"):
            del env[k]
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env,
                       cwd=str(ROOT / "work"), timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def b200():
    if not GENERATOR.is_file():
        pytest.skip("B200 generator not present")
    return _b200_values()


def test_registry_constants_are_b200s(b200):
    assert b200["id"] == S.ACH_ORNAMENT_ID == ORNAMENT_ID
    assert b200["target"] == S.ACH_ORNAMENT_TARGET == 12
    assert b200["icon"] == S.ACH_ORNAMENT_ICON == 0x1ED
    assert b200["title_id"] == S.STRING_ORNAMENT_TITLE == 0xE31
    assert b200["desc_id"] == S.STRING_ORNAMENT_DESC == 0xE32
    assert b200["stock_string_max_plus_1"] == S.STRING_STOCK_MAX_ID + 1
    # Rows are materialised through the last custom id; its successor starts B200's reserved tail.
    assert b200["last_custom_id"] + 1 == S.ACH_ROW_CAPACITY
    assert b200["reserved_first"] == S.ACH_RESERVED_FIRST == b200["last_custom_id"] + 1
    assert b200["rows"] == [S.ACH_ROW_SIZE]
    # The scratch record 0xA8 lies inside the preserved rows, as in B200.
    assert S.ACH_STOCK_ROWS <= b200["record_scratch"] < S.ACH_RESERVED_FIRST


def test_registry_texts_and_order_are_b200s():
    src = GENERATOR.read_text(encoding="utf-8")
    assert '"Ornamentologist"' in src
    assert '"You completed the collection of holiday ornaments."' in src
    cpp = (RUNTIME / "native" / "vf2fun" / "vf2fun_ids.inc").read_text(encoding="utf-8")
    assert '"Ornamentologist"' in cpp
    assert '"You completed the collection of holiday ornaments."' in cpp
    # Ornamentologist directly after Bottlologist (0x5E), stock order index 0x4E.
    assert "bottlologist_id = 0x5E" in src and "ornamentologist_index = bottlologist_index + 1" in src
    assert STOCK_ORDER.index(0x5E) == 0x4E == 0x4F - 1
    assert S.ACH_ORDER_ANCHOR_BOTTLOLOGIST == 0x5E
    # B200's row: (id, target, icon, 0, title, desc, coins 0)
    assert "HOLIDAY_ORNAMENT_ACHIEVEMENT_TARGET," in src and "CUSTOM_ACHIEVEMENT_ICON_ID," in src


def test_content_height_formula_is_b200s():
    src = GENERATOR.read_text(encoding="utf-8")
    assert "return VF2AchievementVisibleCountInternal() * 0x42 + 0x1C;" in src
    assert S.ACH_CONTENT_HEIGHT_STOCK == S.ACH_STOCK_ROWS * S.ACH_ROW_PITCH + 0x1C == 0x189A
    assert S.ACH_ROW_PITCH == 0x42


def test_load_state_patch_values_are_b200s():
    """The five LoadState constants B200 writes in patch_custom_achievements."""
    src = GENERATOR.read_text(encoding="utf-8")
    start = src.index("def patch_custom_achievements(")
    body = src[start:src.index("\ndef ", start + 10)]
    assert "reserved_first = CUSTOM_ACHIEVEMENT_RESERVED_FIRST_ID" in body
    assert "reserved_offset = reserved_first * 12" in body
    assert "reserved_count = 0x125 - reserved_first" in body
    assert S.ACH_RECORD_SIZE == 12 and S.ACH_RECORD_COUNT == 0x125
    assert "bytes((0x8D, 0x4E, 0x5F)), bytes((0x8D, 0x4E, 0x00))" in body  # counter start 0


def test_modules_registered_with_the_registry_last():
    keys = [m.key for m in S.MODULES]
    assert keys[-1] == "id_registry"
    m = S.MODULE_BY_KEY["id_registry"]
    assert m.internal and m.ini_key is None
    assert S.MODULE_BY_KEY["ornament_achievement"].requires == ("id_registry",)
    assert not S.MODULE_BY_KEY["ornament_achievement"].b200_default      # experimental: off
    assert S.MODULE_BY_KEY["achievement_records"].b200_default            # unconditional in B200
    # The patcher writes a setting for every public module and none for the internal one.
    assert "OrnamentologistAchievement" in P.default_settings()
    assert None not in P.default_settings()
    assert len(P.default_settings()) == len(S.MODULES) - 1


def test_every_new_site_is_proved_against_the_vanilla_executable():
    facts = gen_sites.validate(vanilla_bytes())
    joined = "\n".join(facts)
    assert "achievementList: exactly 8 references in the whole file, all pinned" in joined
    assert "achievementOrder: exactly 2 references in the whole file, all pinned" in joined
    for pin in S.PINS:
        if pin.role == "field":
            assert f"{pin.name}: field" in joined


def test_field_pins_are_exactly_the_readers_of_the_two_tables():
    # 8 readers of achievementList: PercentCompleted, DrawAchievement x5, IncrementProgress, Update.
    rows = [p for p in S.PINS if p.name.startswith("ach_rows_") and p.role == "field"]
    assert len(rows) == 8 and len(S.ACH_ROW_FIELDS) == 8
    # Every field's current displacement is list + 4 / 0x10 / 0x14 / 0x18: a column of the 28-byte row.
    img = vanilla_image()
    seen = set()
    for p in rows:
        disp = struct.unpack("<I", img.read(p.field_va, 4))[0]
        assert disp - S.ACH_LIST_BASE in (4, 0x10, 0x14, 0x18), p.name
        seen.add(disp - S.ACH_LIST_BASE)
    assert seen == {4, 0x10, 0x14, 0x18}


def test_a_corrupted_field_pin_or_unpinned_reader_is_refused():
    data = bytearray(vanilla_bytes())
    img = gen_sites.Image(bytes(data))
    # (1) the displacement of one reader is not the list any more.
    pin = S.PIN_BY_NAME["ach_rows_title"]
    raw = None
    for name, rva, vsize, rawptr, rsize in img.sections:
        if name == ".text":
            raw = rawptr + (pin.field_va - img.base - rva)
    bad = bytearray(data)
    bad[raw] ^= 0x01
    with pytest.raises(gen_sites.SiteError):
        gen_sites.validate(bytes(bad))   # not the vanilla file at all
    # (2) an extra reader of the list is found by the raw census (simulated on a copy
    # whose census range is widened by one table row so an existing constant falls in it).
    saved = S.RAW_REFERENCE_CENSUS["achievementList"]
    try:
        S.RAW_REFERENCE_CENSUS["achievementList"] = (saved[0], saved[1], saved[2][:-1])
        with pytest.raises(gen_sites.SiteError, match="differ from the pinned readers"):
            gen_sites.validate(vanilla_bytes())
    finally:
        S.RAW_REFERENCE_CENSUS["achievementList"] = saved


# ------------------------------------------------------------ the reservation sweep
def _anchors(flags: dict) -> dict:
    env = dict(os.environ)
    for k, v in flags.items():
        env["VF2_ENABLE_" + k] = str(v)
    env["VF2_ENABLE_AI_GENERATED_BATHROOM2"] = str(flags["MOBILE_RENOVATIONS"])
    script = (
        "import json, sys\n"
        "sys.path.insert(0, %r)\n"
        "import patch_mobile_furniture_pack as g\n"
        "hd = g.holiday_body_descriptor_count() if g.ENABLE_HOLIDAY_BODY_TYPES else 0\n"
        "print(json.dumps({\n"
        "  'img_renov': g.mobile_renovation_image_base(hd),\n"
        "  'img_ornament_collection': g.holiday_ornament_collection_image_base(hd),\n"
        "  'img_head_icons': g.head_icon_image_base(hd),\n"
        "  'img_prop_art': g.prop_art_image_base(hd),\n"
        "  'str_event0': g.event_string_id_for(0),\n"
        "  'str_cheat0': g.cheat_upgrade_string_ids_for_entry(0)[0],\n"
        "  'str_outfit0': g.outfit_string_ids_for_entry(0)[0],\n"
        "  'str_label0': g.behavior_label_string_id_for(0),\n"
        "  'str_ornament_title': g.holiday_ornament_collection_title_string_id(),\n"
        "  'str_ornament_ach_title': g.holiday_ornament_achievement_title_string_id(),\n"
        "  'str_custom_base': g.custom_achievement_string_base(),\n"
        "  'str_renov0': g.mobile_renovation_string_ids_for(0)[0],\n"
        "}))\n" % str(ROOT / "work")
    )
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env,
                       cwd=str(ROOT / "work"), timeout=300)
    assert r.returncode == 0, r.stderr[-1500:]
    return json.loads(r.stdout.strip().splitlines()[-1])


SWEEP_FLAGS = ("ISLAND_EVENTS", "HOLIDAY_ORNAMENTS", "CHEAT_UPGRADES", "BEHAVIOR_PATCHES", "MOBILE_RENOVATIONS")


def _sweep(combos):
    return {c: _anchors(dict(zip(SWEEP_FLAGS, c))) for c in combos}


def test_string_ids_never_move_with_the_toggles_but_image_ids_do():
    """The cascade map, measured on B200's generator. String ids are reserved
    unconditionally (populated conditionally) and are identical in every
    variant; image ids after the renovation block move with two toggles
    (renovations, holiday ornaments)."""
    if not GENERATOR.is_file():
        pytest.skip("B200 generator not present")
    combos = [(1, 1, 1, 1, 1), (0, 0, 0, 0, 0), (1, 0, 0, 0, 1), (0, 1, 1, 1, 0)]
    if os.environ.get("VF2_FULL_ID_SWEEP") == "1":
        combos = list(itertools.product((0, 1), repeat=len(SWEEP_FLAGS)))
    res = _sweep(combos)
    for key in next(iter(res.values())):
        values = {c: res[c][key] for c in combos}
        if key.startswith("str_"):
            assert len(set(values.values())) == 1, (key, values)
    assert len({res[c]["img_renov"] for c in combos}) == 1            # the cascade's last stable base
    moved = {k for k in next(iter(res.values())) if k.startswith("img_")
             and len({res[c][k] for c in combos}) > 1}
    assert {"img_ornament_collection", "img_head_icons", "img_prop_art"} <= moved
    # ... and the Ornamentologist strings are the reserved ids, wherever the toggles are.
    assert {res[c]["str_ornament_ach_title"] for c in combos} == {S.STRING_ORNAMENT_TITLE}
    # Renovations alone shift the images behind them; ornaments alone shift them again.
    on, off = res[(1, 1, 1, 1, 1)], res[(0, 0, 0, 0, 0)]
    assert on["img_head_icons"] > off["img_head_icons"] and on["img_prop_art"] > off["img_prop_art"]


# ------------------------------------------------------------ the harness
def _have_msvc() -> bool:
    return sys.platform == "win32" and Path(VCVARS).is_file()


def _run_bat(lines: list[str], cwd: Path) -> None:
    bat = cwd / "build.bat"
    bat.write_text("@echo off\r\n" + "\r\n".join(lines) + "\r\n")
    r = subprocess.run(["cmd", "/c", str(bat)], capture_output=True, text=True, cwd=cwd)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    vanilla = vanilla_bytes()
    if not _have_msvc():
        pytest.skip("Visual Studio x86 toolchain not found (set VF2_VCVARS32)")
    work = tmp_path_factory.mktemp("idres")
    _run_bat([
        f'call "{VCVARS}" >nul || exit /b 1',
        # The release DLL, exactly as native/build.bat makes it.
        f'cl /nologo /O2 /MT /EHsc /W4 /WX /LD /GS "{DLL_SOURCE}" /Fo"{work}\\\\" '
        f'/Fe"{work}\\vf2fun.dll" /link kernel32.lib /DYNAMICBASE /NXCOMPAT /MANIFEST:EMBED || exit /b 1',
        f'cl /nologo /O1 /MT /W3 "{HARNESS_SOURCE}" /Fo"{work}\\\\" '
        f'/Fe"{work}\\idres_harness.exe" /link /BASE:0x30000000 /FIXED /DYNAMICBASE:NO kernel32.lib || exit /b 1',
    ], work)
    assert (work / "vf2fun.dll").is_file() and (work / "idres_harness.exe").is_file()
    (work / "patched.exe").write_bytes(P.patch_executable(vanilla))
    return work


PUBLIC = [m for m in S.MODULES if not m.internal]
OFF = {m.ini_key: False for m in PUBLIC}
RECORDS = {**OFF, "AchievementReservedRecords": True}
FEATURE = {**RECORDS, "OrnamentologistAchievement": True}
ORNAMENT_ONLY = {**OFF, "OrnamentologistAchievement": True}
ALL_ON = {m.ini_key: True for m in PUBLIC}


def _run(built: Path, setting, tag: str, exe: Path | None = None, with_dll: bool = True) -> list[dict]:
    run = built / f"run-{tag}"
    if run.exists():
        shutil.rmtree(run)
    run.mkdir()
    shutil.copy2(built / "idres_harness.exe", run)
    files = run / S.PATCHER_FOLDER
    files.mkdir()
    if with_dll:
        shutil.copy2(built / "vf2fun.dll", files / S.DLL_NAME)
        if setting is not None:
            P.write_settings(files / S.INI_NAME, setting)
    r = subprocess.run([str(run / "idres_harness.exe"), str(exe or built / "patched.exe")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr
    rows = [json.loads(line) for line in r.stdout.splitlines() if line.strip()]
    assert "fatal" not in rows[-1] and rows[-1] == {"done": 1}, rows[-1]
    return rows


@pytest.fixture(scope="module")
def vanilla_run(built):
    return _run(built, None, "vanilla", with_dll=False)


@pytest.fixture(scope="module")
def off_run(built):
    return _run(built, OFF, "off")


@pytest.fixture(scope="module")
def records_run(built):
    return _run(built, RECORDS, "records")


@pytest.fixture(scope="module")
def feature_run(built):
    return _run(built, FEATURE, "feature")


@pytest.fixture(scope="module")
def ornament_only_run(built):
    return _run(built, ORNAMENT_ONLY, "ornament-only")


def _get(rows, key, value=None):
    found = [r for r in rows if key in r and (value is None or r[key] == value)]
    assert len(found) == 1, (key, value, len(found))
    return found[0]


def _bit(key: str) -> int:
    return 1 << [m.key for m in S.MODULES].index(key)


def _sites(rows):
    return {r["site"]: r for r in rows if "site" in r}


# ------------------------------------------------------------ the oracle: B200's rules
def b200_expected_order(ornament: bool) -> list[int]:
    order = list(STOCK_ORDER)
    if ornament:
        order.insert(order.index(0x5E) + 1, ORNAMENT_ID)
    return order


def b200_content_height(count: int) -> int:
    return count * 0x42 + 0x1C


def stock_rows() -> bytes:
    return vanilla_image().read(S.ACH_LIST_BASE, S.ACH_STOCK_ROWS * S.ACH_ROW_SIZE)


def b200_ornament_row() -> bytes:
    return struct.pack("<7I", ORNAMENT_ID, 12, 0x1ED, 0, 0xE31, 0xE32, 0)


def _stock_strings() -> dict[int, bytes]:
    img = vanilla_image()
    out = {}
    for i in range(0xA5D):
        entry = img.read(0x53DCC0 + i * 0x10, 16)
        ident, _key, text, _alt = struct.unpack("<4I", entry)
        # Text pointer -> bytes up to NUL. (A few stock entries hold no usable text pointer.)
        if not 0x400000 <= text < 0xB00000:
            continue
        data = bytearray()
        va = text
        while True:
            b = img.read(va, 1)
            if b == b"\0":
                break
            data += b
            va += 1
        out[ident] = bytes(data)
    return out


# ------------------------------------------------------------ bootstrap and status
def test_missing_dll_is_the_stock_game(vanilla_run):
    boot = _get(vanilla_run, "bootstrap")["bootstrap"]
    assert boot["dll_loaded"] == 0 and boot["init_calls"] == 1


def test_off_and_vanilla_runs_are_identical(vanilla_run, off_run):
    """Everything the scenarios observe is the same with no DLL and with every module off."""
    skip = {"bootstrap", "status", "dll_range", "wx_regions"}
    strip = lambda rows: [r for r in rows if not (set(r) & skip)]  # noqa: E731
    assert strip(vanilla_run) == strip(off_run)
    assert _get(off_run, "status")["status"]["installed"] == 0


def test_stock_is_what_the_scenarios_measure(vanilla_run):
    """The oracle's stock side agrees with the unpatched game: the table, the order,
    the bounds, the content height and the load rule."""
    rows = _get(vanilla_run, "rows_base")
    assert rows["rows_base"] == S.ACH_LIST_BASE and rows["rows"] == S.ACH_STOCK_ROWS
    assert bytes.fromhex(rows["hex"]) == stock_rows()
    order = _get(vanilla_run, "order_base")
    assert order["order_base"] == S.ACH_ORDER_BASE
    assert struct.unpack(f"<{order['order_count']}I", bytes.fromhex(order["hex"])) == tuple(STOCK_ORDER)
    for row in (r for r in vanilla_run if "draw_bound" in r):
        assert row["row_drawn"] == (row["draw_bound"] < S.ACH_STOCK_ROWS)
        assert row["complete_flag_read"] == (1 if row["draw_bound"] < S.ACH_STOCK_ROWS else 0)
    s = _sites(vanilla_run)
    img = vanilla_image()
    for va, row in s.items():
        assert bytes.fromhex(row["bytes"]) == img.read(va, len(bytes.fromhex(row["bytes"]))), hex(va)


def test_feature_installs_with_its_registry_and_no_wx_page(feature_run):
    status = _get(feature_run, "status")["status"]
    want = _bit("achievement_records") | _bit("ornament_achievement") | _bit("id_registry")
    assert status["requested"] == status["installed"] == want and status["refused"] == 0
    assert _get(feature_run, "wx_regions")["wx_regions"] == 0
    # The registry's writes: 8 row fields + 2 bounds + 5 scene fields + 2 string stubs.
    reg = [m.key for m in S.MODULES].index("id_registry")
    assert bin(status["write_masks"][reg]).count("1") == 17
    rec = [m.key for m in S.MODULES].index("achievement_records")
    assert status["write_masks"][rec] == 0b11111
    orn = [m.key for m in S.MODULES].index("ornament_achievement")
    assert status["write_masks"][orn] == 0   # registers only; writes nothing itself


def test_registry_alone_is_never_requested_without_a_consumer(records_run, off_run):
    for rows in (records_run, off_run):
        st = _get(rows, "status")["status"]
        assert not st["installed"] & _bit("id_registry")
        assert not st["requested"] & _bit("id_registry")


def test_ornament_without_records_still_installs_the_registry(ornament_only_run):
    st = _get(ornament_only_run, "status")["status"]
    assert st["installed"] == _bit("ornament_achievement") | _bit("id_registry")


# ------------------------------------------------------------ tables and sites
def test_feature_rows_are_stock_rows_plus_the_b200_row(feature_run):
    rows = _get(feature_run, "rows_base")
    assert rows["rows_base"] != S.ACH_LIST_BASE and rows["rows"] == S.ACH_STOCK_ROWS + 1
    dll = _get(feature_run, "dll_range")["dll_range"]
    assert dll[0] <= rows["rows_base"] < dll[1]                       # DLL-owned storage
    data = bytes.fromhex(rows["hex"])
    assert data[:S.ACH_STOCK_ROWS * S.ACH_ROW_SIZE] == stock_rows()
    assert data[S.ACH_STOCK_ROWS * S.ACH_ROW_SIZE:] == b200_ornament_row()


def test_every_row_reader_points_into_the_new_table_at_its_own_column(feature_run):
    s = _sites(feature_run)
    base = _get(feature_run, "rows_base")["rows_base"]
    img = vanilla_image()
    for p in (p for p in S.PINS if p.name.startswith("ach_rows_") and p.role == "field"):
        old = struct.unpack("<I", img.read(p.field_va, 4))[0]
        new = struct.unpack("<I", bytes.fromhex(s[p.field_va]["bytes"]))[0]
        assert new == base + (old - S.ACH_LIST_BASE), p.name


def test_order_is_b200s_with_ornamentologist_after_bottlologist(feature_run, off_run):
    order = _get(feature_run, "order_base")
    dll = _get(feature_run, "dll_range")["dll_range"]
    assert dll[0] <= order["order_base"] < dll[1]
    got = list(struct.unpack(f"<{order['order_count']}I", bytes.fromhex(order["hex"])))
    assert got == b200_expected_order(True)
    assert got[0x4E] == 0x5E and got[0x4F] == ORNAMENT_ID and len(got) == S.ACH_STOCK_ROWS + 1
    off = _get(off_run, "order_base")
    assert list(struct.unpack(f"<{off['order_count']}I", bytes.fromhex(off["hex"]))) == STOCK_ORDER


def test_scene_fields_follow_the_row_count_like_b200(feature_run, off_run):
    n = S.ACH_STOCK_ROWS + 1
    s = _sites(feature_run)
    assert struct.unpack("<I", bytes.fromhex(s[0x42CADF]["bytes"]))[0] == b200_content_height(n) == 0x18DC
    assert struct.unpack("<I", bytes.fromhex(s[0x42CAEA]["bytes"]))[0] == b200_content_height(n)
    assert s[0x42CD34]["bytes"] == f"{n:02x}"
    assert s[0x4B4E07]["bytes"] == s[0x4B4EF6]["bytes"] == "60"          # draw bound = highest id + 1
    order = _get(feature_run, "order_base")
    end = struct.unpack("<I", bytes.fromhex(s[0x42CD68]["bytes"]))[0]
    assert end == order["order_base"] + 4 * n
    so = _sites(off_run)
    assert struct.unpack("<I", bytes.fromhex(so[0x42CADF]["bytes"]))[0] == b200_content_height(S.ACH_STOCK_ROWS)
    assert so[0x42CD34]["bytes"] == "5f" and so[0x4B4E07]["bytes"] == "5f"


def test_draw_bounds_let_the_new_row_read_its_saved_flag_and_draw(feature_run, off_run):
    on = {r["draw_bound"]: r for r in feature_run if "draw_bound" in r}
    assert on[0x5E] == {"draw_bound": 0x5E, "complete_flag_read": 1, "row_drawn": 1}
    assert on[0x5F] == {"draw_bound": 0x5F, "complete_flag_read": 1, "row_drawn": 1}
    assert on[0x60]["complete_flag_read"] == 0 and on[0x60]["row_drawn"] == 0
    off = {r["draw_bound"]: r for r in off_run if "draw_bound" in r}
    assert off[0x5E]["row_drawn"] == 1 and off[0x5F]["row_drawn"] == 0 and off[0x5F]["complete_flag_read"] == 0


def _scene_rows(rows):
    return {r["scene_index"]: r["ids"] for r in rows if "scene_index" in r}


def model_scene(order: list[int], idx: int) -> list[int]:
    scroll = idx * 0x42 + (idx % 5) * 3
    i, y, ids = scroll // 0x42, 0x55 - scroll % 0x42, []
    if i >= len(order):
        return ids
    while True:
        ids.append(order[i])
        y += 0x42
        if y >= 0x300:
            break
        i += 1
        if i >= len(order):
            break
    return ids


def test_the_real_draw_scene_draws_b200s_rows_at_every_scroll_position(feature_run, off_run):
    for rows, order in ((feature_run, b200_expected_order(True)), (off_run, STOCK_ORDER)):
        got = _scene_rows(rows)
        assert len(got) == 0x62
        for idx, ids in got.items():
            assert ids == model_scene(order, idx), idx
    drawn = _scene_rows(feature_run)
    assert ORNAMENT_ID in drawn[0x4F] and ORNAMENT_ID in drawn[0x4D]
    assert all(ORNAMENT_ID not in ids for ids in _scene_rows(off_run).values())
    assert drawn[0x5F] == [0x5C] and drawn[0x60] == [] and drawn[0x61] == []   # the last row; nothing past it


# ------------------------------------------------------------ strings
def _string_texts(rows):
    out = {}
    for r in rows:
        if "string" in r:
            kind, _, ident = r["string"].partition("_")
            out[(kind, int(ident))] = bytes.fromhex(r["hex"])
    return out


UNKNOWN = b"Unknown String Id!!!!"


@pytest.mark.parametrize("which", ["vanilla_run", "off_run", "records_run", "feature_run", "ornament_only_run"])
def test_stock_strings_and_gaps_are_unchanged_in_every_build(which, request):
    rows = request.getfixturevalue(which)
    stock = _stock_strings()
    got = _string_texts(rows)
    for (kind, ident), text in got.items():
        if ident in stock:
            assert text == stock[ident][:96], (kind, ident)
        elif ident not in (0xE31, 0xE32):
            assert text == UNKNOWN[:96] or text == b"", (kind, ident, text)   # id 0 is the empty string
    assert got[("get", 0)] == b"" and got[("inline", 0)] == b""


def test_registered_strings_answer_through_both_readers(feature_run, off_run):
    got = _string_texts(feature_run)
    assert got[("get", 0xE31)] == b"Ornamentologist" == got[("inline", 0xE31)]
    desc = b"You completed the collection of holiday ornaments."
    assert got[("get", 0xE32)] == desc == got[("inline", 0xE32)]
    for ident in (0xE30, 0xE33, 0x1000, 0xA69):
        assert got[("get", ident)] == UNKNOWN == got[("inline", ident)], hex(ident)
    off = _string_texts(off_run)
    assert off[("get", 0xE31)] == UNKNOWN == off[("inline", 0xE31)]


def test_the_inline_stub_keeps_every_register_the_stock_code_needs(feature_run):
    for r in (r for r in feature_run if "inline_regs" in r):
        assert (r["edx"], r["ebx"], r["esi"], r["edi"], r["ebp"]) == (1, 1, 1, 1, 1), r


# ------------------------------------------------------------ progress and the save
def test_ornamentologist_completes_through_the_real_stock_code(feature_run):
    assert _get(feature_run, "orn_start")["orn_start"]["percent"] == 0
    o = _get(feature_run, "orn")["orn"]
    assert o == {"half_percent": 50, "half_complete": 0, "percent": 100, "complete": 1,
                 "progress": 12, "stamp": 1000, "queue0": ORNAMENT_ID, "queue1": -1}
    stock = _get(feature_run, "stock_row1")["stock_row1"]
    assert stock == {"percent": 50, "complete": 0, "progress": 500}


def test_stock_rows_progress_identically_with_the_feature_off(feature_run, off_run, vanilla_run):
    assert _get(feature_run, "stock_row1") == _get(off_run, "stock_row1") == _get(vanilla_run, "stock_row1")


def test_a_completed_record_survives_save_and_load_byte_for_byte(feature_run):
    rt = _get(feature_run, "orn_roundtrip")["orn_roundtrip"]
    assert rt == {"equal": 1, "flag": 1, "progress": 12, "stamp": 1000}


def make_records(case: str) -> list[list[int]]:
    recs = [[0, 0, 0] for _ in range(S.ACH_RECORD_COUNT)]
    for i in range(S.ACH_STOCK_ROWS):
        recs[i] = [int(i % 3 == 0), i * 7, i * 100]
    if case in ("ornament_saved", "other_features", "reserved_tail"):
        recs[0x5F] = [1, 12, 5000]
    if case in ("other_features", "reserved_tail"):
        recs[0x60] = [1, 1, 6000]
        recs[0x7F] = [0, 3, 0]
        recs[0xAB] = [1, 1, 7000]
    if case == "reserved_tail":
        recs[0xAC] = [0, 5, 0]
        recs[0xB0] = [0, 0, 9999]
        recs[0x124] = [1, 0, 0]
    return recs


def stock_load(recs):
    """CAchievement::LoadState as vanilla compiles it: if any record from 0x5F is non-empty,
    clear 200 records from 0x5D (byte 0 and dword +4 only)."""
    out = [r[:] for r in recs]
    if any(r[0] != 0 or r[1] != 0 for r in out[0x5F:]):
        for i in range(0x5D, 0x5D + 200):
            out[i][0] = 0
            out[i][1] = 0
    return out


def b200_load(recs):
    """The same function after patch_custom_achievements: validate and clear only the
    reserved tail, records 0xAC..0x124."""
    out = [r[:] for r in recs]
    first = S.ACH_RESERVED_FIRST
    if any(r[0] != 0 or r[1] != 0 for r in out[first:]):
        for i in range(first, S.ACH_RECORD_COUNT):
            out[i][0] = 0
            out[i][1] = 0
    return out


def _loaded(rows, case):
    raw = bytes.fromhex(_get(rows, "records", case)["hex"])
    return [[raw[i * 12], *struct.unpack_from("<ii", raw, i * 12 + 4)] for i in range(S.ACH_RECORD_COUNT)]


CASES = ["vanilla_format", "ornament_saved", "other_features", "reserved_tail"]


@pytest.mark.parametrize("case", CASES)
def test_save_state_writes_exactly_the_records(case, feature_run, vanilla_run):
    assert _get(feature_run, "save_case", case)["saved_ok"] == 1
    assert _get(vanilla_run, "save_case", case)["saved_ok"] == 1


@pytest.mark.parametrize("which", ["records_run", "feature_run"])
@pytest.mark.parametrize("case", CASES)
def test_with_the_records_module_a_load_is_b200s(which, case, request):
    rows = request.getfixturevalue(which)
    assert _loaded(rows, case) == b200_load(make_records(case))


@pytest.mark.parametrize("which", ["vanilla_run", "off_run", "ornament_only_run"])
@pytest.mark.parametrize("case", CASES)
def test_without_the_records_module_a_load_is_vanillas(which, case, request):
    rows = request.getfixturevalue(which)
    assert _loaded(rows, case) == stock_load(make_records(case))


@pytest.mark.parametrize("which", ["vanilla_run", "off_run", "records_run", "feature_run", "ornament_only_run"])
def test_a_vanilla_format_save_loads_unchanged_in_every_build(which, request):
    rows = request.getfixturevalue(which)
    assert _loaded(rows, "vanilla_format") == make_records("vanilla_format")


def test_a_save_written_with_the_feature_on_loads_with_it_off_and_keeps_its_record(records_run):
    """The ornament record (and the other defined rows) survive a load by a build that has the
    feature OFF but B200's LoadState: B200 with Holiday Ornaments off behaves the same."""
    recs = _loaded(records_run, "other_features")
    assert recs[0x5F] == [1, 12, 5000] and recs[0x60] == [1, 1, 6000] and recs[0xAB] == [1, 1, 7000]
    assert recs[0x5D] == make_records("other_features")[0x5D] and recs[0x5E] == make_records("other_features")[0x5E]


def test_vanilla_loses_the_feature_record_and_bottlologist_which_is_why_the_records_module_exists(vanilla_run):
    recs = _loaded(vanilla_run, "ornament_saved")
    assert recs[0x5F][:2] == [0, 0]
    saved = make_records("ornament_saved")
    assert saved[0x5D][:2] != [0, 0] or saved[0x5E][:2] != [0, 0]    # the case does store them ...
    assert recs[0x5D][:2] == [0, 0] and recs[0x5E][:2] == [0, 0]     # ... and stock clears from record 0x5D


def test_a_save_written_with_the_feature_off_loads_with_it_on(feature_run):
    """Vice versa: the vanilla-format save has record 0x5F empty, so the new row starts at 0/12."""
    recs = _loaded(feature_run, "vanilla_format")
    assert recs[0x5F] == [0, 0, 0]


def test_the_record_array_and_its_size_in_the_save_never_change():
    # 0x125 records * 12 bytes; the notify queue follows at +0xDBC in the object, outside the save.
    assert S.ACH_RECORD_COUNT * S.ACH_RECORD_SIZE == 0xDBC


# ------------------------------------------------------------ fail-closed
def test_corrupted_registry_pin_refuses_the_registry_and_its_consumer_but_not_the_records(built):
    vanilla = vanilla_bytes()
    patched = bytearray(P.patch_executable(vanilla))
    pe = P.PE(bytes(patched))
    # One byte of the stock achievementOrder (a context pin of the registry): not a written byte.
    patched[pe.offset(S.ACH_ORDER_BASE + 8)] ^= 0x01
    exe = built / "corrupt-order.exe"
    exe.write_bytes(bytes(patched))
    rows = _run(built, FEATURE, "corrupt", exe=exe)
    st = _get(rows, "status")["status"]
    assert st["installed"] == _bit("achievement_records")
    assert st["refused"] == _bit("ornament_achievement") | _bit("id_registry")
    s = _sites(rows)
    img = vanilla_image()
    for p in (p for p in S.PINS if p.module in ("id_registry", "ornament_achievement") and p.role == "field"):
        assert bytes.fromhex(s[p.field_va]["bytes"]) == img.read(p.field_va, p.field[1]), p.name
    assert _get(rows, "rows_base")["rows_base"] == S.ACH_LIST_BASE


def test_the_release_dll_exports_only_the_status_block(built):
    data = (built / "vf2fun.dll").read_bytes()
    assert b"VF2Fun_Status" in data and b"VF2Fun_Startup" in data
    assert b"VF2Fun_TestCounters" not in data
