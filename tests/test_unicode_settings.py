"""The two Unicode text settings: "Render Unicode with In-Game Fonts" (on by default) and "Use Unicode Font
(overrides in-game fonts)" (off by default) cannot be on together, everywhere a selection is made:

* the patcher (offline_vf2_patcher.resolve_enabled_settings): defaults keep the default one; --enable of one drops the
  other; --enable of both is refused; Enable All keeps the default one;
* the GUI: ticking one unticks the other; a bulk tick (Select All) keeps the default one;
* the exporter: the settings rows (exact names, "excludes" both ways), the runtime-flag sections, and the files: the
  companion DLL under its own name per setting, each setting's ini, and the patcher-made letters only with Render
  Unicode with In-Game Fonts; neither selection leaves two records on one file;
* the generator's manifest contract.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import offline_vf2_patcher as patcher  # noqa: E402

TEXT, FONT = "render_unicode_in_game_fonts", "use_unicode_font"


def _exporter():
    spec = importlib.util.spec_from_file_location("vf2_exporter_unicode", ROOT / "work" / "export_offline_patch_bundle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def exporter():
    return _exporter()


def _manifest():
    return {"settings": [
        {"id": "core_executable", "label": "Patch game executable", "default": True},
        {"id": TEXT, "label": "Render Unicode with In-Game Fonts", "default": True, "excludes": [FONT]},
        {"id": FONT, "label": "Use Unicode Font (overrides in-game fonts)", "default": False},
        {"id": "other", "label": "Other", "default": True},
    ]}


def _args(**kw):
    base = dict(enable=[], disable=[], enable_all=False, disable_all=False, final_playtest_all_enabled=False)
    base.update(kw)
    return argparse.Namespace(**base)


def test_excludes_work_both_ways():
    s = patcher.manifest_settings(_manifest())
    assert s[TEXT].excludes == (FONT,) and s[FONT].excludes == (TEXT,)
    assert s["other"].excludes == ()


@pytest.mark.parametrize("kw,expect", [
    ({}, {TEXT}),
    ({"enable": [FONT]}, {FONT}),
    ({"enable": [TEXT]}, {TEXT}),
    ({"enable_all": True}, {TEXT}),
    ({"enable": [FONT], "disable": [TEXT]}, {FONT}),
    ({"disable": [TEXT]}, set()),
])
def test_the_patcher_never_turns_both_on(kw, expect):
    _s, enabled = patcher.resolve_enabled_settings(_manifest(), _args(**kw))
    assert enabled & {TEXT, FONT} == expect
    assert "other" in enabled or kw.get("disable_all")


def test_asking_for_both_is_refused():
    with pytest.raises(patcher.PatchError, match="cannot be on together"):
        patcher.resolve_enabled_settings(_manifest(), _args(enable=[TEXT, FONT]))


class _Var:
    def __init__(self, v=False):
        self.v = v

    def get(self):
        return self.v

    def set(self, v):
        self.v = v


def _gui():
    gui = pytest.importorskip("offline_vf2_patcher_gui")
    c = object.__new__(gui.VF2PatcherGUI)
    c.settings = patcher.manifest_settings(_manifest())
    c.setting_vars = {k: _Var(v.default) for k, v in c.settings.items()}
    c.setting_prerequisites = {}
    c.informational_settings = {}
    return gui, c


def test_the_gui_unticks_the_other():
    gui, c = _gui()
    c.setting_vars[FONT].set(True)
    gui.VF2PatcherGUI._on_setting_toggled(c, FONT)
    assert c.setting_vars[FONT].get() and not c.setting_vars[TEXT].get()
    c.setting_vars[TEXT].set(True)
    gui.VF2PatcherGUI._on_setting_toggled(c, TEXT)
    assert c.setting_vars[TEXT].get() and not c.setting_vars[FONT].get()


def test_a_bulk_tick_keeps_the_default_one():
    gui, c = _gui()
    for v in c.setting_vars.values():
        v.set(True)
    gui.VF2PatcherGUI._normalize_setting_selection(c)
    assert c.setting_vars[TEXT].get() and not c.setting_vars[FONT].get()


def test_the_exporter_rows(exporter):
    rows = {r["id"]: r for r in exporter.SETTINGS}
    assert rows[TEXT]["label"] == "Render Unicode with In-Game Fonts" and rows[TEXT]["default"] is True
    assert rows[FONT]["label"] == "Use Unicode Font (overrides in-game fonts)" and rows[FONT]["default"] is False
    assert rows[TEXT]["excludes"] == [FONT] and rows[FONT]["excludes"] == [TEXT]
    assert exporter.RUNTIME_FLAG_SECTION_BY_SETTING[TEXT] == ".vf2utxt"
    assert exporter.RUNTIME_FLAG_SECTION_BY_SETTING[FONT] == ".vf2ufnt"
    for sid in (TEXT, FONT):
        assert "Cannot be on together with" in rows[sid]["description"]


def _contract(setting, dll, ini):
    return {"offline_patcher_setting": setting, "companion_dll": dll, "companion_ini": ini,
            "runtime_flag": {"source_section": ".vf2utxt" if setting == TEXT else ".vf2ufnt"}}


def test_the_exporter_files(exporter, tmp_path):
    images = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload") / "Images"
    dll = ROOT / "runtime" / "build" / "vf2unicode_b200.dll"
    if not (images / "Segoe24.png").is_file() or not dll.is_file():
        pytest.skip("needs the original game folder and runtime/build/vf2unicode_b200.dll")
    pytest.importorskip("vf2_glyph_render")
    import vf2_glyph_render
    if not vf2_glyph_render.available():
        pytest.skip("the patcher-made letters are drawn with Windows' GDI")
    build = {"UnicodeText": _contract(TEXT, "vf2unicode_b200.dll", "vf2unicode.ini"),
             "UnicodeFont": _contract(FONT, "vf2unicodefont_b200.dll", "vf2unicodefont.ini")}
    records = exporter.unicode_text_asset_patches(tmp_path, dll, build, images)
    by = {}
    for r in records:
        by.setdefault(r["requires"][1], []).append(r["file_path"])
        assert r["remove_when_disabled"] and r["requires"][0] == "core_executable"
    folder = "Virtual Families 2 Patcher Files"
    assert sorted(by[FONT]) == [f"{folder}/vf2unicodefont.ini", f"{folder}/vf2unicodefont_b200.dll"]
    assert f"{folder}/vf2unicode_b200.dll" in by[TEXT] and f"{folder}/vf2unicode.ini" in by[TEXT]
    sheets = sorted(p for p in by[TEXT] if "/Unicode Text/" in p)
    assert sheets == sorted(f"{folder}/Unicode Text/{n}.{e}" for n in
                            ("Segoe24", "Segoe24Bold", "Segoe32Bold", "Segoe36Bold") for e in ("png", "txt"))
    assert not set(by[TEXT]) & set(by[FONT])                   # no file is shared, so none is removed by the other
    ini = (tmp_path / "payload" / "UnicodeFont" / "vf2unicodefont.ini").read_bytes()
    assert b"Mode=2" in ini and b"Face=Segoe UI" in ini
    assert b"Mode=1" in (tmp_path / "payload" / "UnicodeText" / "vf2unicode.ini").read_bytes()
    assert exporter.unicode_text_asset_patches(tmp_path, dll, {}, images) == []


def test_the_generator_contract():
    gen = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    start = gen.index("def patch_unicode_text_manifest(manifest):")
    body = gen[start:gen.index("\ndef ", start + 10)]
    ns = {"TIME_CONTROLS_PATCHER_FOLDER": "Virtual Families 2 Patcher Files"}
    for line in gen.splitlines():
        if line.startswith(("UNICODE_TEXT_", "UNICODE_FONT_")):
            exec(line, ns)
    exec(body, ns)
    manifest = {"TimeControls": {}}
    ns["patch_unicode_text_manifest"](manifest)
    assert manifest["UnicodeText"]["runtime_flag"]["source_section"] == ".vf2utxt"
    assert manifest["UnicodeFont"]["runtime_flag"]["source_section"] == ".vf2ufnt"
    assert manifest["UnicodeText"]["default"] is True and manifest["UnicodeFont"]["default"] is False
    assert manifest["UnicodeText"]["companion_dll"] == "vf2unicode_b200.dll"
    assert manifest["UnicodeFont"]["companion_dll"] == "vf2unicodefont_b200.dll"
