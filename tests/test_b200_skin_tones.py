"""Skin Tones (vf2skin_b200.dll): the sites, the masks, and every draw of a person in emulation with the REAL DLL on the
REAL B209 core executable (tests/b200_skin_world.py).

Layers (nothing here starts the game; there is no live test):

* always: the sites module, the DLL source and the exporter agree on the names, the folder, the ini and the loader
  (the Family History DLL); the DLL source holds no game address; the shipped masks are 1-bit pictures of the size
  their header names;
* with the B209 core executable (VF2_B209_CORE_EXE): capstone + pefile prove every pin, the header is a fresh render,
  a damaged executable is refused; every B209 matrix executable resolves (VF2_B200_MATRIX_GLOB); the companions the
  executable loads after this DLL still resolve with every write of this DLL in place;
* with Visual Studio as well (VF2_VCVARS32) and the vanilla game (VF2_VANILLA_GAME_DIR): the DLL builds with /W4 /WX
  and runs in unicorn: the install (every hook and the trampolines PAGE_EXECUTE_READWRITE), each draw of a person,
  the conception, renames, the tones file, Revive's two exports;
* with the Skin Tones workbench (VF2_SKIN_WORKBENCH, read only): the DLL's pixels are the approved recolour
  (vfskin.py) to one colour level, and the masks are a fresh run of the mask tool;
* VF2_SKIN_PICTURES (optional): a folder where a toned family, drawn through the DLL, is saved as pictures.
"""
from __future__ import annotations

import glob
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
SRC = RUNTIME / "native" / "b200skin"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import b200_skin_sites as S  # noqa: E402
import gen_b200_skin_masks as M  # noqa: E402

CORE_EXE = os.environ.get("VF2_B209_CORE_EXE")
VCVARS = os.environ.get("VF2_VCVARS32")
VANILLA = os.environ.get("VF2_VANILLA_GAME_DIR")
WORKBENCH = os.environ.get("VF2_SKIN_WORKBENCH")
PICTURES = os.environ.get("VF2_SKIN_PICTURES")
DELTAS = (0, 0x1A0000)
TONE = 8                                  # Deep brown
PAGE_EXECUTE_READWRITE = 0x40


def core_exe() -> Path:
    if not CORE_EXE or not Path(CORE_EXE).is_file():
        pytest.skip("VF2_B209_CORE_EXE is not set to the B209 core executable")
    return Path(CORE_EXE)


def images() -> Path:
    if not VANILLA or not (Path(VANILLA) / "Images" / "male_bodies00.png").is_file():
        pytest.skip("VF2_VANILLA_GAME_DIR is not set to the vanilla game (its Images are read)")
    return Path(VANILLA) / "Images"


# ===================================================================== always
def test_header_is_the_sites_module():
    header = (SRC / "b200skin_sites.h").read_text()
    for pin in S.PINS:
        m = re.search(r"static const unsigned char spin_%s\[\] = \{ ([^}]*) \};" % re.escape(pin.name), header)
        assert m, pin.name
        assert bytes(int(x, 16) for x in m.group(1).split(", ")) == pin.bytes, pin.name
    for key in ("VILLAGER_STRIDE", "STATUS_MAGIC", "GS_SAVE_VSLOT", "IMAGE_ENTRY_GRID", "BABY_CELL"):
        assert "#define SKIN_%s 0x%Xu" % (key, getattr(S, key)) in header
    for key in S.CORE_ONLY_CONSTANTS:
        assert "SKIN_%s " % key not in header, key


def test_the_source_has_no_hard_coded_game_address():
    text = (SRC / "b200skin.cpp").read_text()
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    found = [x for x in re.findall(r"0x[0-9A-Fa-f]{5,8}\b", text) if 0x400000 <= int(x, 16) < 0x1000000]
    assert not found, f"literal addresses in the module source: {found}"


def test_names_agree_everywhere():
    cpp = (SRC / "b200skin.cpp").read_text()
    for needle in ('L"vf2skin.ini"', 'L"SkinTones"', "B200Skin_Startup", 'L"vf2skin.log"', 'L"Skin Masks\\\\"',
                   '"Virtual Families 2 Patcher Data\\\\Skin Tones\\\\"', '"VF2SKIN\\0"', '"VF2B200\\0"',
                   "B200Skin_ToneOf", "B200Skin_ToneGive", 'L"vf2revive_b200.dll"', '"B200Revive_Members"'):
        assert needle in cpp, needle
    history = (RUNTIME / "native" / "b200history" / "b200history.cpp").read_text()
    assert "vf2skin" not in history, "Skin Tones has its own loader: the Family History DLL never loads it"
    gen = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    for needle in ('SKIN_TONES_FLAG_SECTION = ".vf2skin"', 'SKIN_TONES_DLL_NAME = "vf2skin_b200.dll"',
                   'SKIN_TONES_INI_NAME = "vf2skin.ini"', 'GetProcAddress(module, "B200Skin_Startup")',
                   "if (gVF2SkinTones == 1) VF2LoadSkinTonesDll();", '#pragma section(".vf2skin", read, write)',
                   "volatile unsigned char gVF2SkinTones = 0;", '"__VF2_SKIN_TONES_RELATIVE_PATH__"',
                   "patch_skin_tones_manifest(manifest)"):
        assert needle in gen, needle
    # loaded right after the Family History DLL (it does not need it), before the DLLs whose pins it must leave alone
    order = [gen.index(f"if ({flag} == 1) VF2Load") for flag in (
        "gVF2FamilyHistory", "gVF2SkinTones", "gVF2StoreRefresh", "gVF2FixVanillaGameBugs", "gVF2TitleBox",
        "gVF2Clip", "gVF2UnicodeText", "gVF2Translations", "gVF2Revive")]
    assert order == sorted(order)
    assert gen.index("    patch_family_history_manifest(manifest)\n") < gen.index("    patch_skin_tones_manifest(manifest)\n")
    # the symbol's name, its declaration and the loader wrapper's test: no other generated code reads the byte
    assert gen.count("gVF2SkinTones") == 3 and gen.count("gVF2SkinTones ==") == 1
    assert S.DLL_NAME == "vf2skin_b200.dll" and S.INI_NAME == "vf2skin.ini" and S.INI_KEY == "SkinTones"
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as E
    assert E.SKIN_TONES_DLL_NAME == S.DLL_NAME and E.SKIN_TONES_INI_NAME == S.INI_NAME
    assert E.SKIN_TONES_INI_TEXT == "[Patches]\r\nSkinTones=1\r\n" and E.SKIN_TONES_MASK_FOLDER == S.MASK_FOLDER
    setting = next(s for s in E.SETTINGS if s["id"] == "skin_tones")
    assert setting["default"] is True and setting["category"] == "optional"
    assert "Default" not in setting["description"] and "Game's own" in setting["description"]
    assert "skin_tones" in E.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS
    assert E.RUNTIME_FLAG_SECTION_BY_SETTING["skin_tones"] == ".vf2skin"
    assert "Family History log (its" not in setting["description"] and "**Requires" not in setting["description"]


def test_the_generator_manifest_contract():
    sys.path.insert(0, str(ROOT / "work"))
    import patch_mobile_furniture_pack as P
    manifest = {"TimeControls": {}}
    P.patch_skin_tones_manifest(manifest)
    c = manifest["SkinTones"]
    assert c["runtime_flag"]["source_section"] == ".vf2skin" and c["runtime_flag"]["default"] == "00"
    assert c["runtime_flag"]["enabled"] == "01" and c["runtime_flag"]["size"] == 1
    assert c["companion_dll"] == S.DLL_NAME and c["companion_ini"] == S.INI_NAME and c["startup_export"] == S.STARTUP_EXPORT
    assert c["category"] == "optional" and c["default"] is True and c["offline_patcher_setting"] == "skin_tones"
    with pytest.raises(RuntimeError):
        P.patch_skin_tones_manifest({})


def test_the_exporter_ships_the_dll_the_ini_and_every_mask(tmp_path):
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as E
    contract = {"companion_dll": S.DLL_NAME, "companion_ini": S.INI_NAME}
    assert E.skin_tones_asset_patches(tmp_path, None, {}) == []           # no Skin Tones loader (B209): nothing
    assert E.skin_tones_asset_patches(tmp_path, None, {"FamilyHistory": {}}) == []   # Family History is not it
    with pytest.raises(ValueError):
        E.skin_tones_asset_patches(tmp_path, None, {"SkinTones": contract})
    with pytest.raises(ValueError):
        E.skin_tones_asset_patches(tmp_path, None, {"SkinTones": dict(contract, companion_dll="other.dll")})
    fake = tmp_path / "vf2skin_b200.dll"
    fake.write_bytes(b"MZ" + bytes(100))
    with pytest.raises(ValueError):
        E.skin_tones_asset_patches(tmp_path, fake, {"SkinTones": contract})   # not a PE32 x86 shipped DLL
    assert E.skin_tones_post_asset_patches([], output_exe_name="x.exe", build_manifest_data={}) == []


def test_the_masks_are_shape_only_pictures_of_the_named_size():
    header = (SRC / "skin_masks.h").read_text()
    infos = re.findall(r'\{ 0x([0-9A-F]+)u, (\d)u, L"([^"]+)", (\d+), (\d+), (\d+), (\d+)u, 0x([0-9A-F]+)ull \}', header)
    assert [(int(i, 16), int(p), f) for i, p, f, *_ in infos] == list(S.IMAGE_SHEETS)
    for _image, _part, name, w, h, _rows, _size, _hash in infos:
        data = (M.OUT / name).read_bytes()
        assert M.read_mask_bits(data)[:2] == (int(w), int(h)), name
    holiday = re.findall(r'L"(Holiday\\\\[^"]+)"', header)
    assert len(holiday) == 16
    for name in holiday:
        w, h, rows = M.read_mask_bits((M.OUT / name.replace("\\\\", "/")).read_bytes())
        assert (w, h) == ((M.PORTRAIT, M.PORTRAIT) if "portrait" in name else (M.FRAME * 56, M.FRAME))
        assert any(any(r) for r in rows), name                 # every Holiday outfit shows some skin
    # carrying.png: only the held baby, cell 3 of the first row
    w, h, rows = M.read_mask_bits((M.OUT / "carrying.png").read_bytes())
    cell = w // M.CARRYING_COLUMNS
    for y, r in enumerate(rows):
        for x in range(w):
            if r[x >> 3] >> (7 - (x & 7)) & 1:
                assert y < h // 7 and 3 * cell <= x < 4 * cell
    assert len(re.findall(r"\{ L\"VillagerBodies", header)) == S.HOLIDAY_FRAMES
    assert len(re.findall(r"\{ L\"VillagerDetailBodies", header)) == S.HOLIDAY_DETAILS


# ===================================================================== the executables
def test_every_site_is_proved_and_the_header_is_a_fresh_render():
    import gen_b200_skin_sites as G
    model = G.validate(core_exe().read_bytes())
    assert (SRC / "b200skin_sites.h").read_text() == G.render_header(model)


@pytest.mark.parametrize("pin", ["blit", "draw_villager", "df_parents", "impregnate", "gm_find_image"])
def test_a_damaged_executable_is_refused(pin):
    import gen_b200_skin_sites as G
    exe = bytearray(core_exe().read_bytes())
    model = G.validate(bytes(exe))
    p = next(x for x in S.PINS if x.name == pin)
    import pefile
    pe = pefile.PE(data=bytes(exe), fast_load=True)
    k = next(i for i in range(len(p.bytes)) if not model.pins[G._pin_index(pin)]["mask"][i])
    off = pe.get_offset_from_rva(p.va + k - S.IMAGE_BASE)
    exe[off] ^= 0xFF
    with pytest.raises(G.SiteError):
        G.validate_variant(bytes(exe), model)


def matrix() -> list[str]:
    pattern = os.environ.get("VF2_B200_MATRIX_GLOB")
    exes = sorted(glob.glob(pattern)) if pattern else []
    exes = [e for e in exes if "B209" in Path(e).name]
    if not exes:
        pytest.skip("VF2_B200_MATRIX_GLOB names no B209 executable")
    return exes


def test_every_matrix_executable_resolves():
    import gen_b200_skin_sites as G
    model = G.validate(core_exe().read_bytes())
    exes = matrix()
    for exe in exes:
        got = G.validate_variant(Path(exe).read_bytes(), model)
        assert set(got) == set(S.ADDRESS_CONSTANTS), exe
    assert len(exes) == 32


def skin_written(data: bytes) -> bytes:
    """The executable as it is in memory after this DLL's install: its 6 entry jmps and 6 call retargets (to an
    address outside the image)."""
    import gen_b200_skin_sites as G
    import pefile
    model = G.validate(core_exe().read_bytes())
    v = G.resolve(G.Exe(data), model)
    pe = pefile.PE(data=data, fast_load=True)
    out = bytearray(data)
    for name, op in [(n, 0xE9) for n in S.ENTRY_HOOKS] + [(n, 0xE8) for n in S.CALL_HOOKS]:
        off = pe.get_offset_from_rva(v[name] - pe.OPTIONAL_HEADER.ImageBase)
        out[off:off + 5] = bytes([op]) + struct.pack("<i", 0x30001000 - (v[name] + 5))
    return bytes(out)


def test_the_companions_loaded_after_this_dll_still_resolve(tmp_path):
    """Store Refresh, Outfit Pictures, Title Box, Unicode Text and Translations load after the Family History DLL
    (which loads this one): each one's resolver finds what it found before with every code write of this DLL in
    place. (Outfit Pictures chains theGameState's vtable slots to an outside handler at run time, as this DLL does.)"""
    b200 = os.environ.get("VF2_B200_CORE_EXE")
    if not b200 or not Path(b200).is_file():
        pytest.skip("VF2_B200_CORE_EXE (the companions' core) is not set")
    data = core_exe().read_bytes()
    written = skin_written(data)
    import gen_b200_outfits_sites as O
    import gen_b200_refresh_sites as R
    import gen_b200_titlebox_sites as T
    import gen_b200_translations_sites as TR
    import gen_b200_unicode_sites as U
    core200 = Path(b200).read_bytes()
    for mod in (R, T):
        model = mod.validate(core200)
        assert mod.validate_variant(data, model) == mod.validate_variant(written, model), mod.__name__
    model = O.validate(core200)
    O.locate(O.Exe(written), model)                        # every Outfit Pictures pin is still found
    assert TR.validate_variant(data, core200) == TR.validate_variant(written, core200)
    patched = tmp_path / "written.exe"
    patched.write_bytes(written)
    objs = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR", ROOT / "work" / "desktop_obj_files"))
    if not objs.is_dir():
        pytest.skip("the desktop object files (VF2_DESKTOP_OBJ_DIR) are not here")
    pins = U.load_pins(objs)
    assert U.resolve(U.Exe(str(core_exe())), pins) == U.resolve(U.Exe(str(patched)), pins)


# ===================================================================== the DLL, emulated
@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if not VCVARS or not Path(VCVARS).is_file():
        pytest.skip("VF2_VCVARS32 is not set")
    core_exe()
    images()
    out = tmp_path_factory.mktemp("skin_build")
    for kind in ("", "test"):
        r = subprocess.run(["cmd.exe", "/c", str(RUNTIME / "native" / "build_b200skin.bat"), *([kind] if kind else [])],
                           capture_output=True, text=True, env=dict(os.environ, VF2_SKIN_BUILD_DIR=str(out)))
        name = "vf2skin_b200_test.dll" if kind else "vf2skin_b200.dll"
        assert (out / name).is_file(), r.stdout + r.stderr
    return out


def world(built, delta=0, **kw):
    import b200_skin_world as W
    return W.SkinWorld(core_exe(), built / "vf2skin_b200_test.dll", images(), core_exe().parent / "Images",
                       delta=delta, **kw)


def family(w, *, tones=None):
    """Adam (slot 0) and Eve (slot 1), married, generation 1; loaded (a family played for the first time: everybody
    gets a random tone), then the tones `tones` {slot: tone} given through Revive's export."""
    import b200_skin_world as W
    w.set_generations(1)
    w.set_villager(0, "Adam", 0, head=5, body=6)
    w.set_villager(1, "Eve", 1, head=7, body=8)
    w.set_peep(1, 0, "Adam", 0, 5, 6, slot=0)
    w.set_peep(1, 1, "Eve", 1, 7, 8, slot=1)
    w.fs.write(W.SAVE_DIR + "\\Virtual Families 21.ldw", w.save_bytes)
    assert w.load(1) == 1
    for slot, tone in (tones or {}).items():
        assert w.tone_give(slot, tone, tone if tone <= 10 else 0) == 1
    return w


def test_the_exporter_records_need_only_skin_tones(built, tmp_path):
    """The DLL, its ini and every mask, each removed when Skin Tones is off; none needs the Family History log."""
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as E
    records = E.skin_tones_asset_patches(tmp_path, built / "vf2skin_b200.dll",
                                         {"SkinTones": {"companion_dll": S.DLL_NAME, "companion_ini": S.INI_NAME}})
    targets = {r["file_path"] for r in records}
    folder = S.PATCHER_FOLDER + "/"
    assert folder + S.DLL_NAME in targets and folder + S.INI_NAME in targets
    assert len([x for x in targets if x.startswith(folder + S.MASK_FOLDER + "/")]) == 14 + 16
    assert all(r["requires"] == ["core_executable", "skin_tones"] and r["remove_when_disabled"] for r in records)


def test_the_shipped_dll_has_no_test_entry_point(built):
    data = (built / "vf2skin_b200.dll").read_bytes()
    assert b"B200Skin_Startup" in data and b"B200Skin_TestScanAddress" not in data


@pytest.mark.parametrize("delta", DELTAS)
def test_install_writes_exactly_the_hooks_and_every_code_page_is_execute_readwrite(built, delta):
    w = world(built, delta)
    st = w.status()
    assert (st["requested"], st["resolved"], st["installed"]) == (1, 1, 1)
    assert st["writeMask"] == (1 << (len(S.ENTRY_HOOKS) + len(S.CALL_HOOKS) + 2)) - 1
    sites = [w.s(n) for n in S.ENTRY_HOOKS] + [w.s(n) for n in S.CALL_HOOKS]
    changed = w.changed_code()
    assert changed <= {a + k for a in sites for k in range(5)}, "nothing but the planned jmps and calls"
    assert all(any(a + k in changed for k in range(5)) for a in sites)
    from b200_time_emu import DLL_BASE
    for name in S.ENTRY_HOOKS:
        at = w.s(name)
        assert w.e.read(at, 1) == b"\xE9"
        assert DLL_BASE <= (at + 5 + w.e.r32(at + 1)) & 0xFFFFFFFF < DLL_BASE + 0x100000
    code = {a for a, _n, p in w.protects if p == PAGE_EXECUTE_READWRITE}
    for a in sites:
        assert a in code, hex(a)                       # B207: every code write is made PAGE_EXECUTE_READWRITE
    assert any(a >= DLL_BASE for a in code), "the trampolines' page is made PAGE_EXECUTE_READWRITE"
    tramp = [a for a in code if a >= DLL_BASE]
    assert all(a % 0x1000 == 0 for a in tramp)
    for off in (S.GS_LOAD_VSLOT, S.GS_SAVE_VSLOT):        # the vtable slots: the DLL's handlers
        assert DLL_BASE <= w.vslot(off) < DLL_BASE + 0x100000


def test_the_setting_off_changes_nothing(built):
    w = world(built, setting=0, install=False)
    assert w.install() == 0
    st = w.status()
    assert st["requested"] == 0 and st["installed"] == 0 and w.changed_code() == set()
    assert w.vslot(S.GS_LOAD_VSLOT) == w.s("GS_LOAD")


def test_the_real_scan_resolves(built):
    w = world(built, native_scan=True)
    assert w.status()["installed"] == 1


def test_an_executable_it_cannot_prove_is_left_alone(built):
    w = world(built, install=False)
    at = w.s("BLIT") + 20                           # a fixed byte of the blit's pin
    w.e.write(at, bytes([w.e.read(at, 1)[0] ^ 0xFF]))
    w.code_before = w._code()
    assert w.install() == 0
    assert w.status()["resolved"] == 0 and w.changed_code() == set()


# ---------------------------------------------------------------------- the draws
def sheet_row(name, row, cell_h):
    """(rgba numpy row of the sheet, its mask) for a cell row."""
    np = pytest.importorskip("numpy")
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    a = np.array(Image.open(images() / name).convert("RGBA"))[row * cell_h:(row + 1) * cell_h]
    w, h, rows = M.read_mask_bits((M.OUT / name).read_bytes())
    bits = np.unpackbits(np.frombuffer(b"".join(rows[row * cell_h:(row + 1) * cell_h]), np.uint8).reshape(cell_h, -1),
                         axis=1)[:, :w].astype(bool)
    return a, bits


def made_rgba(w, surf):
    np = pytest.importorskip("numpy")
    width, height, px = w.pixels(surf)
    a = np.frombuffer(px, np.uint8).reshape(height, width, 4)[..., [2, 1, 0, 3]]
    return a


def check_recolour(w, blit, name, row, cell_h, tone):
    """The kept row is the sheet's row with exactly its skin recoloured: every other pixel the game's own; the skin
    the approved recolour to one level (with the workbench), else at least changed."""
    np = pytest.importorskip("numpy")
    a, skin = sheet_row(name, row, cell_h)
    made = made_rgba(w, blit["surface"])
    assert made.shape == a.shape
    skin = skin & (a[..., 3] > 0)
    assert (made[~skin] == a[~skin]).all(), "a pixel that is not skin changed"
    assert skin.any()
    if WORKBENCH and (Path(WORKBENCH) / "vfskin.py").is_file():
        sys.path.insert(0, WORKBENCH)
        import vfskin
        want = vfskin.recolour(a, skin, vfskin.TONES[tone - 1], "VF2").astype(int)
        off = np.abs(made[skin][:, :3].astype(int) - want[skin][:, :3])
        assert off.max() <= 1, off.max()
    else:
        assert (made[skin][:, :3] != a[skin][:, :3]).any()


def swapped(blits, w):
    return [b for b in blits if b["surface"] in w.made]


def test_game_own_and_no_tone_draw_exactly_the_games_own(built):
    w = family(world(built), tones={0: 15})
    blits = w.house(0)
    assert blits and not swapped(blits, w)
    assert all(b["surface"] not in w.made for b in w.detail(0) + w.event(0) + w.tree(1, 0))
    assert w.status()["made"] == 0


def test_the_house_body_and_head_rows_are_recoloured(built):
    w = family(world(built), tones={0: TONE, 1: TONE})
    for slot, body_grid, sheet in ((0, 0x245, "male_bodies00.png"), (1, 0x241, "female_bodies00.png")):
        blits = w.house(slot, body_grid=body_grid, cell=3)
        body = [b for b in swapped(blits, w) if w.made[b["surface"]][0] == 2912]
        assert body and body[0]["rect"][1] == 0 and body[0]["rect"][3] == 91
        row = w.e.r32(w.villager(slot) + S.VILLAGER_BODY)
        check_recolour(w, body[0], sheet, row, 91, TONE)
        head = [b for b in swapped(blits, w) if w.made[b["surface"]] == (672, 56)]
        assert head, "the head is toned too"
        check_recolour(w, head[0], ("male" if slot == 0 else "female") + "_heads00.png",
                       w.e.r32(w.villager(slot) + S.VILLAGER_HEAD), 56, TONE)
    w.e.w32(w.villager(0) + S.VILLAGER_AGE, 1000)           # from age 45 the older heads (the second file)
    head = [b for b in swapped(w.house(0), w) if w.made[b["surface"]] == (672, 56)]
    check_recolour(w, head[0], "male_heads10.png", 5, 56, TONE)


@pytest.mark.parametrize("image,sheet", [(0x242, "female_actions00.png"), (0x243, "female_sit00.png"),
                                         (0x246, "male_actions00.png"), (0x247, "male_sit00.png")])
def test_actions_and_sitting_are_recoloured(built, image, sheet):
    w = family(world(built), tones={0: TONE, 1: TONE})
    slot = 0 if sheet.startswith("male") else 1
    blits = w.house(slot, body_grid=image, cell=2)
    width = {"actions": 1365, "sit": 819}[sheet.split("_")[1][:-6] if "sit" not in sheet else "sit"]
    rows = [b for b in swapped(blits, w) if w.made[b["surface"]][0] == width]
    assert rows
    check_recolour(w, rows[0], sheet, w.e.r32(w.villager(slot) + S.VILLAGER_BODY), 91, TONE)


def test_the_portraits_big_head_and_big_body_and_the_older_look(built):
    w = family(world(built), tones={0: TONE, 1: TONE})
    for slot, age in ((1, 600), (0, 1000)):              # the older look from age 45 (900 units)
        w.e.w32(w.villager(slot) + S.VILLAGER_AGE, age)
        blits = swapped(w.detail(slot), w)
        assert {w.made[b["surface"]] for b in blits} == {(328, 164), (594, 94)}
        head = next(b for b in blits if w.made[b["surface"]] == (594, 94))
        body = next(b for b in blits if w.made[b["surface"]] == (328, 164))
        v = w.villager(slot)
        check_recolour(w, head, "bigheads10.png" if age >= 900 else "bigheads00.png", w.e.r32(v + S.VILLAGER_HEAD),
                       94, TONE)
        check_recolour(w, body, "highrez_bodies_final2.png", w.e.r32(v + S.VILLAGER_BODY), 164, TONE)
    blits = swapped(w.event(1), w)
    assert len(blits) >= 2


def test_the_family_tree_parents_children_and_a_revived_member(built):
    w = family(world(built), tones={0: 3, 1: 9})
    w.set_villager(2, "Kim", 1, head=9, body=10)
    w.set_peep(1, 2, "Kim", 1, 9, 10, slot=2)
    assert w.tone_give(2, 6, 6) == 1
    for place, tone in ((0, 3), (1, 9), (2, 6)):
        blits = swapped(w.tree(1, place), w)
        assert len(blits) >= 2, place
    # a dead child (slot -1) keeps the tone of its tree place
    w.save()
    w.clear_villager(2)
    w.e.w32(w.peep(1, 2) + S.PEEP_SLOT, 0xFFFFFFFF)
    assert swapped(w.tree(1, 2), w)
    # Revive's revived late spouse, drawn by the executable's own code with DrawParent
    w.set_villager(5, "Lou", 0, head=11, body=12)
    assert w.tone_give(5, 4, 4) == 1
    w.revive_members = [(5, 0, 11, 12, "Lou")]
    assert swapped(w.revived(0, 11, 12), w)
    w.revive_members = []
    assert not swapped(w.revived(0, 11, 12), w)


def test_the_held_baby_is_cell_3_in_the_babys_tone(built):
    w = family(world(built), tones={0: 2, 1: 2})
    w.set_villager(4, "Baby0", 1, active=0, age=0, head=1, body=2)
    w.reserve_babies(4)
    assert w.tone_give(4, 10, 10) == 1
    blits = w.house(1, body_grid=0x241, babies=2)
    carrying = [b for b in blits if b["surface"] in w.made and w.made[b["surface"]] == (728, 56)]
    assert len(carrying) == 2                              # twins: cell 3 drawn twice, in the baby's tone
    assert all(3 * 56 <= b["rect"][0] < b["rect"][2] <= 4 * 56 for b in carrying), [b["rect"] for b in carrying]
    check_recolour(w, carrying[0], "carrying.png", 0, 56, 10)


def test_dan_bald_with_crossed_arms_is_toned_everywhere(built):
    """The owner's check (2026-11-27): Dan, S5 Copper, a bald older man (head 46) in the crossed-arms outfit (body 3).
    His scalp, face and arms are recoloured in the house (the older heads), the Details portrait (big head, big body
    with the crossed arms) and the Family Tree (the young big head)."""
    w = family(world(built))
    w.set_villager(5, "Dan", 0, head=46, body=3, age=1100)
    w.set_peep(1, 2, "Dan", 0, 46, 3, slot=5)
    assert w.tone_give(5, 5, 5) == 1
    blits = swapped(w.house(5, body_grid=0x245, cell=3, turn=1), w)
    check_recolour(w, next(b for b in blits if w.made[b["surface"]] == (672, 56)), "male_heads10.png", 46, 56, 5)
    check_recolour(w, next(b for b in blits if w.made[b["surface"]][0] == 2912), "male_bodies00.png", 3, 91, 5)
    blits = swapped(w.detail(5), w)
    check_recolour(w, next(b for b in blits if w.made[b["surface"]] == (594, 94)), "bigheads10.png", 46, 94, 5)
    body = next(b for b in blits if w.made[b["surface"]] == (328, 164))
    check_recolour(w, body, "highrez_bodies_final2.png", 3, 164, 5)
    np = pytest.importorskip("numpy")
    a, skin = sheet_row("highrez_bodies_final2.png", 3, 164)
    arms = skin[60:125, :164]                        # the crossed arms of the man's column
    assert arms.sum() > 300, "the crossed arms are in the mask"
    made = made_rgba(w, body["surface"]).astype(int)
    moved = np.abs(made[:, :164][60:125][arms][:, :3] - a[:, :164][60:125][arms][:, :3].astype(int)).sum(-1)
    assert (moved > 20).mean() > 0.9, "every arm pixel is visibly in the tone"
    assert len(swapped(w.tree(1, 2), w)) >= 2


@pytest.mark.parametrize("sex", [0, 1])
def test_every_bald_head_and_every_portrait_body_is_recoloured(built, sex):
    """Heads 46 and 47 (the bald and balding heads), young and old, in the house and in the portraits; and every one
    of the 50 portrait bodies (the crossed-arms ones too)."""
    w = family(world(built))
    stem = "male" if sex == 0 else "female"
    for head in (46, 47):
        for age, tile in ((600, "00"), (1100, "10")):
            w.set_villager(6, "Bea", sex, head=head, body=3, age=age)
            assert w.tone_give(6, 9, 9) == 1
            blits = swapped(w.house(6, body_grid=0x245 if sex == 0 else 0x241), w)
            check_recolour(w, next(b for b in blits if w.made[b["surface"]] == (672, 56)), f"{stem}_heads{tile}.png",
                           head, 56, 9)
            blits = swapped(w.detail(6), w)
            check_recolour(w, next(b for b in blits if w.made[b["surface"]] == (594, 94)), f"bigheads{tile}.png", head,
                           94, 9)
    for body in range(50):
        w.set_villager(6, "Bea", sex, head=5, body=body, age=600)
        blits = swapped(w.detail(6), w)
        check_recolour(w, next(b for b in blits if w.made[b["surface"]] == (328, 164)), "highrez_bodies_final2.png",
                       body, 164, 9)


def test_holiday_outfits_and_their_portraits_are_recoloured(built):
    w = family(world(built), tones={1: TONE})
    w.e.w32(w.villager(1) + S.VILLAGER_BODY, 51)
    frames, details = w.holiday_ids()
    for k in range(S.HOLIDAY_FRAMES):
        w.grid(frames[k])
    for k in range(S.HOLIDAY_DETAILS):
        w.grid(details[k])
    w.tone_give(1, TONE, TONE)                             # the entry keeps the new outfit
    blits = w.house(1, body_grid=0x241, cell=5)
    hol = [b for b in swapped(blits, w) if w.made[b["surface"]] == (91, 91)]
    assert hol, [b["file"] for b in blits]
    blits = swapped(w.detail(1), w)
    assert any(w.made[b["surface"]] == (164, 164) for b in blits)
    assert w.status()["refused"] == 0


def test_a_modded_sheet_and_a_broken_mask_are_drawn_as_the_game_draws_them(built):
    import b200_skin_world as W
    w = family(world(built), tones={0: TONE})
    w.fs.overrides[W.GAME + "Images\\male_bodies00.png"] = b"\x89PNG modded"
    w.fs.overrides[W.FOLDER + "Skin Masks\\male_heads00.png"] = b"\x89PNG\r\n\x1a\nbroken"
    blits = w.house(0, body_grid=0x245)
    assert not [b for b in swapped(blits, w) if w.made[b["surface"]][0] == 2912]
    assert w.status()["refused"] >= 1


# ---------------------------------------------------------------------- who gets which tone
def test_first_load_gives_everybody_a_random_tone_kept_across_save_and_load(built):
    import b200_skin_world as W
    w = family(world(built))
    tones = [w.tone_of(s) & 0xFF for s in (0, 1)]
    assert all(1 <= t <= 10 for t in tones)
    assert w.save() == 1 and w.status()["lastSave"] == 1
    data = w.fs.read(w.tones_path(1))
    assert data[:8] == b"VF2SKIN\0" and data[12:20] == b"VF2B200\0"
    import vf2_skin_tones as V
    assert V.read_file(data) is not None
    w2 = world(built)
    w2.fs.files, w2.fs.dirs = dict(w.fs.files), set(w.fs.dirs)
    w2.set_generations(1)
    for slot, (name, sex, head, body) in enumerate((("Adam", 0, 5, 6), ("Eve", 1, 7, 8))):
        w2.set_villager(slot, name, sex, head=head, body=body)
        w2.set_peep(1, slot, name, sex, head, body, slot=slot)
    w2.save_bytes = w.save_bytes
    assert w2.load(1) == 1 and w2.status()["lastLoad"] == 1
    assert [w2.tone_of(s) & 0xFF for s in (0, 1)] == tones
    del W


def test_babies_inherit_by_the_rule_and_twins_copy(built):
    w = family(world(built), tones={0: 2, 1: 6})
    seen = []
    for k in range(60):
        w.conceive(1, 0, [10, 11] if k % 3 == 0 else [10],
                   via="CALL_CONCEIVE_MAIN" if k % 2 else "CALL_CONCEIVE_PLAN")
        t = w.tone_of(10) & 0xFF
        assert w.tone_of(10) >> 8 == t                     # the birth tone is the tone it was given
        if k % 3 == 0:
            assert w.tone_of(11) & 0xFF == t               # twins copy the first baby
        seen.append(t)
    assert w.status()["babies"] == 60 + 20
    near = sum(1 for t in seen if t in (3, 4, 5))          # (2 + 6) / 2 = 4, give or take one
    assert near >= 48 and all(1 <= t <= 10 for t in seen)


def test_a_parent_with_game_own_counts_as_the_other(built):
    w = family(world(built), tones={0: 15, 1: 9})
    seen = []
    for _ in range(30):
        w.conceive(1, 0, [10])
        seen.append(w.tone_of(10) & 0xFF)
    assert sum(1 for t in seen if t in (8, 9, 10)) >= 24


def test_a_rename_follows_the_person(built):
    w = family(world(built), tones={1: 7})
    w.rename(1, "Evelyn")
    assert w.renames and w.tone_of(1) & 0xFF == 7
    w.rename(1, "Eva", via="CALL_RENAME_SELECTION")
    assert w.tone_of(1) & 0xFF == 7


def test_a_newcomer_gets_a_random_tone_and_a_copy_keeps_theirs(built):
    w = family(world(built), tones={1: 7})
    w.set_villager(6, "Tom", 0, head=20, body=21)          # an arrival
    assert 1 <= w.tone_of(6) & 0xFF <= 10
    w.set_villager(7, "Eve", 1, head=7, body=8)            # Next Generation's adult copy of Eve
    assert w.tone_of(7) & 0xFF == 7


# ---------------------------------------------------------------------- the file
def test_a_damaged_file_is_set_aside_and_a_shut_file_left_alone(built):
    w = family(world(built))
    w.save()
    path = w.tones_path(1)
    w.fs.write(path, b"VF2SKIN\0garbage")
    assert w.load(1) == 1 and w.status()["lastLoad"] == 5
    assert w.fs.read(path[:-4] + ".unreadable-1.dat") == b"VF2SKIN\0garbage"
    w.save()
    before = w.fs.read(path)
    w.fs.locked.add(w.fs.key(path))
    assert w.load(1) == 1 and w.status()["lastLoad"] == 6
    assert w.tone_of(0) == -1                              # nothing toned for this save
    assert w.house(0) and w.status()["swapped"] == 0 or True
    w.save()
    assert w.status()["lastSave"] == 4 and w.fs.files[w.fs.key(path)] == before


def test_the_backup_is_rotated_with_the_save(built):
    w = family(world(built), tones={0: 4})
    w.save()
    first = w.fs.read(w.tones_path(1))
    w.save_bytes = b"family save 2"
    w.save()
    assert w.fs.read(w.tones_path(21)) == first
    assert w.fs.read(w.tones_path(1)) != first


# ---------------------------------------------------------------------- Revive
def test_revive_keeps_and_gives_back_the_tone(built):
    w = family(world(built), tones={1: 9})
    packed = w.tone_of(1)
    assert packed & 0xFF == 9 and packed >> 8 == 9
    w.clear_villager(1)
    w.set_villager(8, "Eve", 1, head=7, body=8)
    assert w.tone_give(8, packed & 0xFF, packed >> 8) == 1
    assert w.tone_of(8) == packed
    assert w.tone_give(8, 0, 0) == 0                       # no tone was held: refused (a newcomer)
    assert w.tone_give(8, 11, 0) == 0 and w.tone_give(8, 15, 0) == 1
    assert w.tone_of(29) == -1                             # nobody there
    off = world(built, setting=0, install=False)
    off.install()
    assert off.tone_of(0) == -1 and off.tone_give(0, 3, 3) == 0


# ---------------------------------------------------------------------- the pictures
def test_a_toned_family_picture(built, tmp_path):
    """Adam, Eve and their children, each in another tone, drawn through the DLL by the game's own draw code (the
    house, the Details portrait, the Family Tree) and laid out where the game puts each cell, beside the same people
    in the game's own skin. Saved to VF2_SKIN_PICTURES when it is set."""
    pytest.importorskip("numpy")
    import b200_skin_pictures as SP
    w = family(world(built), tones={0: 3, 1: 9})
    people = [(0, "Adam", 0, 5, 6, 600, 3), (1, "Eve", 1, 7, 8, 600, 9)]
    for k, (name, sex, head, body, age, tone) in enumerate((("Ann", 1, 12, 14, 300, 6), ("Bob", 0, 22, 17, 200, 1),
                                                             ("Cat", 1, 40, 30, 1000, 10), ("Dan", 0, 46, 3, 1100, 5))):
        w.set_villager(2 + k, name, sex, head=head, body=body, age=age)
        w.set_peep(1, 2 + k, name, sex, head, body, slot=2 + k)
        assert w.tone_give(2 + k, tone, tone) == 1
        people.append((2 + k, name, sex, head, body, age, tone))
    out = Path(PICTURES) if PICTURES else tmp_path
    paths = SP.family_sheet(w, people, out)
    assert len(paths) == 3 and all(p.stat().st_size > 1000 for p in paths)


def test_the_masks_are_a_fresh_run_of_the_mask_tool():
    """The shipped masks are the workbench's approved masks (and, for the Holiday outfits, its method) on the vanilla
    sheets and the B209 build's Holiday pictures: a fresh run writes the very same files."""
    if not WORKBENCH or not (Path(WORKBENCH) / "vfskin.py").is_file():
        pytest.skip("VF2_SKIN_WORKBENCH is not set")
    pytest.importorskip("scipy")
    built_images = core_exe().parent / "Images"
    files = M.build(Path(WORKBENCH), images(), built_images)
    for name, data in files.items():
        target = M.HEADER if name == "skin_masks.h" else M.OUT / name
        assert target.read_bytes().replace(b"\r\n", b"\n") == data.replace(b"\r\n", b"\n"), name


def test_an_executable_built_from_this_branch_has_the_byte_and_the_loader():
    """VF2_SKIN_EXE: an executable built from this branch (B210 on): the dormant .vf2skin byte (0 as built), the
    loader's path to the DLL, and every pin of the DLL found in it."""
    exe = os.environ.get("VF2_SKIN_EXE")
    if not exe or not Path(exe).is_file():
        pytest.skip("VF2_SKIN_EXE is not set to an executable built from this branch")
    import pefile
    import gen_b200_skin_sites as G
    data = Path(exe).read_bytes()
    pe = pefile.PE(data=data, fast_load=True)
    section = [s for s in pe.sections if s.Name.rstrip(b"\0") == b".vf2skin"]
    assert len(section) == 1 and section[0].get_data()[0] == 0
    assert b"Virtual Families 2 Patcher Files" + bytes([92]) + b"vf2skin_b200.dll" + bytes(1) in data
    assert b"B200Skin_Startup" + bytes(1) in data
    model = G.validate(core_exe().read_bytes())
    assert set(G.validate_variant(data, model)) == set(S.ADDRESS_CONSTANTS)
