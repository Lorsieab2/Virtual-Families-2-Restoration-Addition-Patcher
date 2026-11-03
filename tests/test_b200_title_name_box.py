"""Title Screen Player Name Box for the B200 executable (companion DLL vf2titlebox_b200.dll).

Layers (nothing here starts the game; there is no live test):

* always: the sites module, the DLL source, the generator and the exporter agree on the names, the folder, the
  ini, the loader and the runtime byte (.vf2tbox); the DLL source holds no game address; the setting is a normal
  Optional row, on by default, in the final playtest profile and in Owner's Defaults;
* with the B200 core executable (VF2_B200_CORE_EXE): capstone + pefile prove every pin and the RTTI search, the
  header is a fresh render, a damaged executable is refused, and every other executable given resolves
  (VF2_B200_MATRIX_GLOB, VF2_B201_CORE_EXE, VF2_KIDS_EXE, VF2_REFRESH_EXE, VF2_UNICODE_EXE, VF2_TITLEBOX_EXE);
* with Visual Studio as well (VF2_VCVARS32): the DLL builds with /W4 /WX, and the REAL compiled DLL runs inside
  unicorn with the REAL game code drawing a title screen frame (tests/b200_titlebox_scenarios.py), at the link
  address and relocated: the plan is the one vtable slot; the pixels behind the name are blended at exactly the
  game's 20% white and no other pixel changes; the name is drawn after the box, unchanged; the box follows the
  name's width from the game's own GetWidth (long names, Unicode names, a width hook as the Unicode text DLLs
  install); with the setting off, or no name on the screen, the frame is the stock frame.
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
SRC = RUNTIME / "native" / "b200titlebox"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "work"))

import b200_titlebox_sites as S  # noqa: E402

CORE_EXE = os.environ.get("VF2_B200_CORE_EXE")
VCVARS = os.environ.get("VF2_VCVARS32")
DELTAS = (0, 0x01230000)
SETTING = "title_screen_player_name_box"


def core_exe() -> str:
    if not CORE_EXE or not Path(CORE_EXE).is_file():
        pytest.skip("VF2_B200_CORE_EXE is not set to the B200 core executable")
    pytest.importorskip("pefile")
    pytest.importorskip("capstone")
    return CORE_EXE


def _gen_text():
    return (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")


# ===================================================================== always
def test_header_is_the_sites_module():
    header = (SRC / "b200titlebox_sites.h").read_text()
    for pin in (p for p in S.PINS if p.dll):
        m = re.search(r"static const unsigned char tpin_%s\[\] = \{ ([^}]*) \};" % re.escape(pin.name), header)
        assert m, pin.name
        assert bytes(int(x, 16) for x in m.group(1).split(", ")) == pin.bytes, pin.name
    for pin in (p for p in S.PINS if not p.dll):
        assert "tpin_%s[]" % pin.name not in header, "a test-only pin reached the DLL"
    for key in ("BOX_COLOR", "BOX_PADDING", "NAME_CONTROL_FIELD", "DRAW_SCENE_VSLOT", "TEXT_SHOWN", "TEXT_STRING",
                "TEXT_SCALE", "TEXT_JUSTIFY", "STATUS_MAGIC"):
        assert "#define TBOX_%s 0x%Xu" % (key, getattr(S, key)) in header, key
    assert '#define TBOX_MENU_TYPE_NAME ".?AVtheMenuScene@@"' in header
    for key in S.CORE_ONLY_CONSTANTS:
        assert "TBOX_%s " % key not in header, key
    assert re.findall(r"(?m)^    TBOX_SITE_(\w+),$", header) == list(S.ADDRESS_CONSTANTS)


def test_the_box_is_white_at_20_percent_with_the_hint_boxes_padding():
    assert S.BOX_COLOR == 0x33FFFFFF and S.BOX_ALPHA == 0x33 and round(S.BOX_ALPHA / 255, 6) == 0.2
    assert S.BOX_PADDING == S.HINT_BOX_MARGIN == 8


def test_the_source_has_no_hard_coded_game_address():
    text = (SRC / "b200titlebox.cpp").read_text()
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    found = [x for x in re.findall(r"0x[0-9A-Fa-f]{5,8}\b", text) if int(x, 16) >= 0x400000]
    assert not found, f"literal addresses in the module source: {found}"


def test_the_dll_writes_only_the_one_slot():
    cpp = (SRC / "b200titlebox.cpp").read_text()
    assert cpp.count("plan.Slot(") == 1 and "PlanJump" not in cpp
    assert "((FillRectFn)SITE(FILL_RECT))(window, &box, TBOX_BOX_COLOR)" in cpp
    assert "((DrawSceneFn)SITE(MENU_DRAW_SCENE))(scene);" in cpp
    # the stock DrawScene first, the box after it
    body = cpp[cpp.index("static void __fastcall TitleDrawScene"):]
    assert body.index("SITE(MENU_DRAW_SCENE)") < body.index("SITE(FILL_RECT)")


def test_names_agree_everywhere():
    cpp = (SRC / "b200titlebox.cpp").read_text()
    for needle in ('L"vf2titlebox.ini"', 'L"NameBox"', "B200TitleBox_Startup", 'L"vf2titlebox.log"'):
        assert needle in cpp, needle
    gen = _gen_text()
    for needle in ('TITLE_BOX_FLAG_SECTION = ".vf2tbox"', 'TITLE_BOX_DLL_NAME = "vf2titlebox_b200.dll"',
                   'TITLE_BOX_INI_NAME = "vf2titlebox.ini"', 'GetProcAddress(module, "B200TitleBox_Startup")',
                   "if (gVF2TitleBox == 1) VF2LoadTitleBoxDll();", '#pragma section(".vf2tbox", read, write)',
                   "volatile unsigned char gVF2TitleBox = 0;", '"__VF2_TITLE_BOX_RELATIVE_PATH__"',
                   "patch_title_box_manifest(manifest)", f'TITLE_BOX_SETTING = "{SETTING}"'):
        assert needle in gen, needle
    # loaded after the other companion DLLs and before the clip and Unicode text DLLs, in the same wrapper
    at = gen.index("if (gVF2TitleBox == 1) VF2LoadTitleBoxDll();")
    assert gen.index("if (gVF2FixVanillaGameBugs == 1) VF2LoadOutfitPicturesDll();") < at
    assert at < gen.index('if (gVF2Clip == 1) VF2LoadUnicodeDll("__VF2_CLIP_RELATIVE_PATH__");')
    assert gen.count("gVF2TitleBox") == 3 and gen.count("gVF2TitleBox ==") == 1
    assert S.DLL_NAME == "vf2titlebox_b200.dll" and S.INI_KEY == "NameBox" and S.INI_NAME == "vf2titlebox.ini"
    assert S.PATCHER_FOLDER == "Virtual Families 2 Patcher Files"
    bat = (RUNTIME / "native" / "build_b200titlebox.bat").read_text()
    assert "/W4 /WX" in bat and "b200titlebox.cpp" in bat and "/DB200TITLEBOX_TEST" in bat
    assert "build_b200titlebox.bat" in (ROOT / "work" / "release_parallel.ps1").read_text(encoding="utf-8")
    rel = (ROOT / "work" / "export_release_bundle.py").read_text(encoding="utf-8")
    assert '("--title-box-dll", args.title_box_dll)' in rel and "vf2titlebox_b200.dll" in rel


def test_the_setting_row_is_optional_and_on_by_default():
    import export_offline_patch_bundle as X
    rows = {r["id"]: r for r in X.SETTINGS}
    row = rows[SETTING]
    assert row["label"] == "Title Screen Player Name Box"
    assert row["default"] is True and row["category"] == "optional"
    for needle in ("20% opacity", "8 pixels on every side", "Render Unicode with In-Game Fonts",
                   "Use Unicode Font", "nothing is saved", "companion DLL", "Virtual Families 2 Patcher Files"):
        assert needle in row["description"], needle
    assert SETTING in X.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS and SETTING in X.SOURCE_BACKED_OPTIONAL_SETTINGS
    assert X.RUNTIME_FLAG_SECTION_BY_SETTING[SETTING] == ".vf2tbox"
    sys.path.insert(0, str(ROOT / "src"))
    import offline_vf2_patcher_gui as gui
    assert SETTING not in gui.OWNERS_DEFAULT_OFF_SETTING_IDS          # Owner's Defaults ticks it


def test_the_exporter_ships_the_dll_and_ini_behind_the_setting(tmp_path):
    import export_offline_patch_bundle as X
    assert X.title_box_asset_patches(tmp_path, None, {}) == []          # a build without the loader: nothing
    contract = {"TitleBox": {"companion_dll": X.TITLE_BOX_DLL_NAME, "companion_ini": X.TITLE_BOX_INI_NAME,
                             "runtime_flag": {"source_section": ".vf2tbox"}}}
    with pytest.raises(ValueError, match="--title-box-dll"):
        X.title_box_asset_patches(tmp_path, None, contract)
    wrong = tmp_path / "other.dll"
    wrong.write_bytes(b"MZ")
    with pytest.raises(ValueError):
        X.title_box_asset_patches(tmp_path, wrong, contract)


def test_the_exporter_records(tmp_path, monkeypatch):
    import export_offline_patch_bundle as X
    dll = tmp_path / "in" / X.TITLE_BOX_DLL_NAME
    dll.parent.mkdir()
    dll.write_bytes(b"MZ shipped B200TitleBox_Startup")
    monkeypatch.setattr(X, "require_vf2_pe32_x86", lambda path, label: None)
    contract = {"TitleBox": {"companion_dll": X.TITLE_BOX_DLL_NAME, "companion_ini": X.TITLE_BOX_INI_NAME}}
    out = tmp_path / "bundle"
    records = X.title_box_asset_patches(out, dll, contract)
    assert [r["file_path"] for r in records] == ["Virtual Families 2 Patcher Files/vf2titlebox_b200.dll",
                                                 "Virtual Families 2 Patcher Files/vf2titlebox.ini"]
    for r in records:
        assert r["requires"] == ["core_executable", SETTING] and r["remove_when_disabled"] is True
    assert (out / "payload" / "TitleBox" / X.TITLE_BOX_INI_NAME).read_bytes() == b"[Patches]\r\nNameBox=1\r\n"
    test_build = tmp_path / "t" / X.TITLE_BOX_DLL_NAME
    test_build.parent.mkdir()
    test_build.write_bytes(b"MZ B200TitleBox_Startup B200TitleBox_TestPlan")
    with pytest.raises(ValueError, match="shipped build"):
        X.title_box_asset_patches(out, test_build, contract)


# ===================================================================== the core executable
@pytest.fixture(scope="module")
def model():
    import gen_b200_titlebox_sites as G
    return G.validate(Path(core_exe()).read_bytes())


def test_the_generator_proves_the_core_and_the_header_is_fresh(model):
    import gen_b200_titlebox_sites as G
    assert G.render_header(model) == (SRC / "b200titlebox_sites.h").read_text()


def test_a_damaged_executable_is_refused(model):
    import gen_b200_titlebox_sites as G
    data = bytearray(Path(core_exe()).read_bytes())
    exe = G.Exe(bytes(data))
    off = S.MENU_DRAW_SCENE - exe.base
    for s in exe.pe.sections:
        if s.VirtualAddress <= off < s.VirtualAddress + s.SizeOfRawData:
            data[s.PointerToRawData + off - s.VirtualAddress + 0x40] ^= 0x5A
    with pytest.raises(G.SiteError):
        G.validate(bytes(data))
    with pytest.raises(G.SiteError):
        G.validate_variant(bytes(data), model)


def test_the_unicode_text_dlls_hook_the_same_get_width_entry_the_box_calls():
    """Both Unicode text settings install an entry jump at ldwFont::GetWidth (their plan's GET_WIDTH site,
    tests/test_b200_unicode_dll.py), and ldwTextControlImpl::Draw measures the name there: that entry is the
    FONT_GET_WIDTH this DLL calls, so the box is measured by the same code as the text it sits behind. The text
    box's Draw itself is replaced at its first 7 bytes for long names (BOX_DRAW), which the box's pin skips."""
    objs = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
    if not (objs / "ldwFont.obj").is_file():
        pytest.skip("no B200 desktop object files")
    import gen_b200_unicode_sites as U
    proved = U.resolve(U.Exe(Path(core_exe())), U.load_pins(objs))
    assert proved["sites"]["GET_WIDTH"] == S.FONT_GET_WIDTH
    names = (RUNTIME / "native" / "b200unicode" / "b200names.inc").read_text(encoding="utf-8")
    assert "UNI_BOX_DRAW_STEAL" in names
    assert re.search(r"#define UNI_BOX_DRAW_STEAL 7u?\b", (RUNTIME / "native" / "b200unicode" /
                                                           "b200unicode_sites.h").read_text(encoding="utf-8"))
    assert S.PINS[1].name == "text_draw_body" and S.PINS[1].va == S.TEXT_DRAW + 7


def _variants():
    out = []
    pattern = os.environ.get("VF2_B200_MATRIX_GLOB")
    if pattern:
        out += sorted(glob.glob(pattern))
    for key in ("VF2_B201_CORE_EXE", "VF2_KIDS_EXE", "VF2_REFRESH_EXE", "VF2_UNICODE_EXE", "VF2_TITLEBOX_EXE",
                "VF2_B206_CORE_EXE"):
        v = os.environ.get(key)
        if v and Path(v).is_file():
            out.append(v)
    return out


def test_every_other_executable_given_resolves(model):
    import gen_b200_titlebox_sites as G
    others = _variants()
    if not others:
        pytest.skip("no other executable given (VF2_B200_MATRIX_GLOB, VF2_B206_CORE_EXE, ...)")
    for path in others:
        got = G.validate_variant(Path(path).read_bytes(), model)
        exe = G.Exe(Path(path).read_bytes())
        assert exe.u32(got["MENU_SLOT_DRAW_SCENE"]) == got["MENU_DRAW_SCENE"], path


# ===================================================================== the real DLL under emulation
@pytest.fixture(scope="module")
def dlls(tmp_path_factory):
    if not VCVARS or not Path(VCVARS).is_file():
        pytest.skip("VF2_VCVARS32 is not set")
    core_exe()
    pytest.importorskip("unicorn")
    out = tmp_path_factory.mktemp("titlebox_build")
    bat = RUNTIME / "native" / "build_b200titlebox.bat"
    for kind in ("", "test"):
        r = subprocess.run(["cmd.exe", "/c", str(bat)] + ([kind] if kind else []), capture_output=True, text=True,
                           env=dict(os.environ, VF2_TITLEBOX_BUILD_DIR=str(out)))
        assert r.returncode == 0, r.stdout + r.stderr
    return out / "vf2titlebox_b200.dll", out / "vf2titlebox_b200_test.dll"


def test_the_shipped_dll_has_no_test_entry_points(dlls):
    shipped, test = dlls
    data = shipped.read_bytes()
    assert b"B200TitleBox_Startup" in data and b"B200TitleBox_Status" in data and b"B200TitleBox_Test" not in data
    assert b"B200TitleBox_TestPlan" in test.read_bytes()


@pytest.mark.parametrize("delta", DELTAS)
def test_the_plan_is_the_menu_scenes_draw_scene_slot(dlls, delta):
    import b200_titlebox_scenarios as B
    f = B.Frame(core_exe(), dlls[1], delta=delta, install=False)
    status, writes = f.test_plan(True)
    assert status == 1 and len(writes) == 1
    w = writes[0]
    assert w["data"] and w["len"] == 4 and w["va"] == S.MENU_SLOT_DRAW_SCENE + delta
    assert struct.unpack("<I", w["bytes"])[0] == f.hook_address()
    assert f.e.r32(w["va"]) == S.MENU_DRAW_SCENE + delta          # the stock pointer until the plan is applied
    assert f.test_plan(False) == (0, [])


def test_a_changed_pinned_byte_installs_nothing(dlls):
    import b200_titlebox_scenarios as B
    f = B.Frame(core_exe(), dlls[1], install=False)
    site = f.s("MENU_DRAW_SCENE")
    f.e.write(site + 0x40, bytes([f.e.read(site + 0x40, 1)[0] ^ 0x5A]))
    assert f.test_plan(True) == (-1, [])


def _frames(dlls, delta=0, **kw):
    import b200_titlebox_scenarios as B
    stock = B.Frame(core_exe(), dlls[1], delta=delta, install=False, **kw)
    boxed = B.Frame(core_exe(), dlls[1], delta=delta, **kw)
    return stock, stock.draw(), boxed, boxed.draw()


def _check_box(stock, before, boxed, after, width=None):
    """The box is exactly the name's rectangle plus 8, every pixel in it the game's 20% white blend of the stock
    pixel, every other pixel unchanged; the name is drawn after the box, the same as without it."""
    import b200_titlebox_scenarios as B
    kinds = [ev[0] for ev in boxed.events]
    assert kinds == ["background", "fill", "text", "final"], kinds
    assert [ev for ev in stock.events if ev[0] != "fill"] == [ev for ev in boxed.events if ev[0] != "fill"]
    _t, text, x, y, colour, font = boxed.text_rect()
    assert colour == S.NAME_COLOR and font == "Segoe32Bold"
    (rect, color), = [ev[1] for ev in boxed.events if ev[0] == "fill"]
    assert color == S.BOX_COLOR
    if width is None:
        width = boxed.width_of(text)
    height = boxed.line_height("Segoe32Bold")
    p = S.BOX_PADDING
    assert rect == (x - p, y - p, x + width + p, y + height + p), (rect, x, y, width, height)
    diff = set(B.pixel_diff(before, after))
    left, top, right, bottom = (max(rect[0], 0), max(rect[1], 0), min(rect[2], B.SCREEN_W), min(rect[3], B.SCREEN_H))
    inside = {(px, py) for px in range(left, right) for py in range(top, bottom)}
    assert diff <= inside
    for py in range(top, bottom):
        for px in range(left, right):
            o = (py * B.SCREEN_W + px) * 4
            want = bytes([B.blend(before[o]), B.blend(before[o + 1]), B.blend(before[o + 2]), before[o + 3]])
            assert after[o:o + 4] == want, (px, py, before[o:o + 4].hex(), after[o:o + 4].hex())
    st = boxed.status()
    assert (st["frames"], st["boxes"]) == (1, 1)
    assert (st["lastLeft"], st["lastTop"], st["lastRight"], st["lastBottom"]) == rect
    return rect


@pytest.mark.parametrize("delta", DELTAS)
def test_the_pixels_behind_the_name_are_20_percent_white_and_nothing_else_changes(dlls, delta):
    stock, before, boxed, after = _frames(dlls, delta)
    assert boxed.e.r32(boxed.slot) == boxed.hook_address()
    rect = _check_box(stock, before, boxed, after)
    # the game's own blend: a = int(0.2 * 255 + 0.5) = 51, each byte (old * 204 >> 8) + 50
    import b200_titlebox_scenarios as B
    assert [B.blend(v) for v in (0, 128, 255)] == [50, 152, 253]
    assert rect[2] - rect[0] > 2 * S.BOX_PADDING


def test_the_setting_off_is_the_stock_frame(dlls):
    import b200_titlebox_scenarios as B
    stock = B.Frame(core_exe(), dlls[1], install=False)
    before = stock.draw()
    off = B.Frame(core_exe(), dlls[1], enabled=False)
    assert off.plan == (0, []) and off.e.r32(off.slot) == off.stock_slot_value
    assert off.draw() == before and [ev[0] for ev in off.events] == ["background", "text", "final"]


def test_no_name_on_the_screen_no_box(dlls):
    import b200_titlebox_scenarios as B
    stock = B.Frame(core_exe(), dlls[1], install=False, name=None)
    boxed = B.Frame(core_exe(), dlls[1], name=None)
    assert boxed.draw() == stock.draw()
    assert [ev[0] for ev in boxed.events] == ["background", "final"]
    assert boxed.status()["frames"] == 1 and boxed.status()["boxes"] == 0
    # and a name that was shown, then removed (UpdateShowPlayer with no player): no box either
    shown = B.Frame(core_exe(), dlls[1])
    shown.draw()
    shown.remove_name()
    assert shown.draw() == stock.draw() and shown.status()["boxes"] == 1


@pytest.mark.parametrize("name", [b"Al", b"Lorsieab2", b"MMMMMMMMMMMMMMMMMMM", b"Ren\xe9e \xc5sa"])
def test_the_box_fits_each_name_with_the_games_own_width(dlls, name):
    """Stock fonts (neither Unicode setting): the width is the game's own GetWidth on the game's Segoe32Bold, for
    a short name, a 19-letter name of the widest letter (wider than the control's placeholder bounds) and
    Windows-1252 letters."""
    stock, before, boxed, after = _frames(dlls, name=name)
    assert boxed.text_rect()[1] == name
    _check_box(stock, before, boxed, after)


@pytest.mark.parametrize("name", ["Zoë İlkay Şimşek", "山田花子",
                                  "\U0001F600 " + "W" * 40, "x" * 300],
                         ids=["turkish", "japanese", "emoji-and-40-W", "300-letters"])
def test_the_box_follows_a_width_hook_as_the_unicode_text_dlls_install(dlls, name):
    """Render Unicode with In-Game Fonts and Use Unicode Font replace the entry of ldwFont::GetWidth with their own
    measure (tests/test_b200_unicode_dll.py: the GET_WIDTH entry jump). Here that entry is a hook returning a
    width of its own for the UTF-8 name (a long name, other scripts, an emoji, 300 letters): the stock Draw places
    the text with it and the box is that same width, wherever it lands, even past the screen's edge."""
    raw = name.encode("utf-8")
    measure = lambda text: 23 * len(text.decode("utf-8")) + 5  # noqa: E731
    stock, before, boxed, after = _frames(dlls, name=raw, width_seam=measure)
    assert boxed.text_rect()[1] == raw
    _check_box(stock, before, boxed, after, width=measure(raw))
