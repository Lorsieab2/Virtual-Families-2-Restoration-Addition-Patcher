"""Translations for the B200 executable (companion DLL vf2tr_b200.dll).

Layers (nothing here starts the game; there is no live test):

* always: the sites module, the header, the DLL source and the limits agree; the DLL source holds no game address;
  every trampoline is made executable before an entry is written (a trampoline in a data section crashed B207 on the
  real game under DEP even though emulation passed); the Unicode contract is the one the spec names;
* with the B200 core executable (VF2_B200_CORE_EXE): capstone + pefile prove every pin, the header is a fresh render,
  a damaged executable is refused, and every other executable given resolves (VF2_UNICODE_EXE, VF2_B207_MATRIX_GLOB);
* with Visual Studio as well (VF2_VCVARS32): the DLL builds with /W4 /WX, and the REAL compiled DLL runs inside
  unicorn with the REAL game code (the lookup, the template filler, strncpy, sprintf) at the link address and
  relocated: the overrides, the choices by person, the room of every kind of line, the guards on strncpy and sprintf,
  the order of the writes (every trampoline executable before any entry is written), Windows-1252 and UTF-8 text, the
  percent rule, and a file that is no use leaving the game exactly as it was.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
SRC = RUNTIME / "native" / "b200tr"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "tools"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "work"))

import b200_translations_sites as S  # noqa: E402
import vf2_translation_format as tf  # noqa: E402

CORE_EXE = os.environ.get("VF2_B200_CORE_EXE")
OTHER_EXE = os.environ.get("VF2_UNICODE_EXE")
VCVARS = os.environ.get("VF2_VCVARS32")
DELTAS = (0, 0x01230000)
LIMITS = json.loads((ROOT / "src" / "vf2_translation_limits.json").read_text(encoding="utf-8"))
SETTING = "translations"
RETRY = "Réessayer"                      # French for Try Again (line 113)


def core_exe() -> str:
    if not CORE_EXE or not Path(CORE_EXE).is_file():
        pytest.skip("VF2_B200_CORE_EXE is not set to the B200 core executable")
    pytest.importorskip("pefile")
    pytest.importorskip("capstone")
    return CORE_EXE


# ===================================================================== always
def test_header_is_the_sites_module():
    header = (SRC / "b200tr_sites.h").read_text()
    for pin in S.PINS:
        m = re.search(r"static const unsigned char tpin_%s\[\] = \{ ([^}]*) \};" % re.escape(pin.name), header)
        assert m, pin.name
        assert bytes(int(x, 16) for x in m.group(1).split(", ")) == pin.bytes, pin.name
    for key in ("RECORD_SIZE", "RECORD_OVERRIDE", "MAX_LINE", "STATUS_MAGIC"):
        assert "#define TR_%s 0x%Xu" % (key, getattr(S, key)) in header, key
    assert re.findall(r"(?m)^    TR_PIN_(\w+),$", header) == [p.name.upper() for p in S.PINS]
    assert '#define TR_GAME_TITLE_TEXT "Virtual Families 2"' in header
    steal = re.search(r"TR_STEAL\[TR_PIN_COUNT\] = \{ ([^}]*) \}", header).group(1)
    assert steal == ", ".join(f"{p.steal}u" for p in S.PINS)


def test_the_source_has_no_hard_coded_game_address():
    text = (SRC / "b200tr.c").read_text(encoding="utf-8-sig")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)
    found = [x for x in re.findall(r"0x[0-9A-Fa-f]{5,8}\b", text) if 0x400000 <= int(x, 16) < 0x10000000]
    assert not found, f"literal addresses in the module source: {found}"


def test_every_trampoline_is_made_executable_before_an_entry_is_written():
    """A trampoline in a data section crashed B207 under DEP although the emulation passed: the test reads the
    source. Every `static unsigned char XTrampoline[..]` is passed to make_trampoline, which VirtualProtects it
    PAGE_EXECUTE_READWRITE before it copies a byte; and every trampoline is made before any entry is written."""
    text = (SRC / "b200tr.c").read_text(encoding="utf-8-sig")
    declared = set(re.findall(r"static\s+unsigned\s+char\s+(\w*Trampoline)\s*\[", text))
    assert declared == {"StrncpyTrampoline", "SprintfTrampoline"}, declared
    body = text[text.index("static int make_trampoline("):]
    body = body[:body.index("\n}\n")]
    assert "VirtualProtect(tramp, 16, PAGE_EXECUTE_READWRITE" in body
    assert body.index("VirtualProtect(tramp, 16, PAGE_EXECUTE_READWRITE") < body.index("tramp[k] = original[k]")
    install = text[text.index("static int install_guards(void)"):]
    install = install[:install.index("\n}\n")]
    for name in declared:
        assert name in install, name
    assert install.index("make_trampoline(") < install.index("write_code(hook_entry[k], jmp, 5)")
    # nothing else in the source copies code bytes into a Trampoline array or jumps into a static array
    code = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    assert len(re.findall(r"PAGE_EXECUTE_READWRITE", code)) == 2         # make_trampoline and write_code


def test_the_unicode_contract():
    text = (SRC / "b200tr.c").read_text(encoding="utf-8-sig")
    assert S.UNICODE_ACTIVE_EXPORT == "B200Unicode_UnicodeTextActive"
    assert '"B200Unicode_UnicodeTextActive"' in text and '"_B200Unicode_UnicodeTextActive@0"' in text
    assert 'L"vf2unicode_b200.dll"' in text and 'L"vf2unicodefont_b200.dll"' in text
    assert "text_mode = unicode_text_active();" in text
    # UTF-8 only when the DLL says its hooks are installed; the status block's installed flag is the fallback
    assert "st[4] != 0" in text and "UNI_STATUS_MAGIC" in text


def test_the_limits_are_a_table_of_the_games_copies():
    assert LIMITS["executables"] >= 1 and LIMITS["get_string_calls"] > 600
    assert LIMITS["never"] == {"36": "the decimal point (eString_Decimal): numbers are written with it"}
    assert all(1 <= int(i) <= 0xFF4 for i in LIMITS["strncpy_room"]) and all(v > 0 for v in LIMITS["strncpy_room"].values())
    assert LIMITS["strncpy_room"]["4083"] == 38          # the Behavior Patches caption (B209): strncpy(.., 0x27)
    header = (SRC / "b200tr_limits.h").read_text()
    for k, v in LIMITS["strncpy_room"].items():
        assert "{ %d, %d }," % (int(k), v) in header
    assert "B200TR_NEVER[] = { 36, 0 }" in header


def _gen_text():
    return (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")


def test_names_agree_everywhere():
    c = (SRC / "b200tr.c").read_text(encoding="utf-8-sig")
    for needle in ('L"vf2tr.ini"', 'L"Translations"', "B200Tr_Startup", 'L"Translations.log"', 'L"Translation.ini"',
                   'L"Translation.txt"', "TR_GAME_TITLE_TEXT"):
        assert needle in c, needle
    gen = _gen_text()
    for needle in ('TRANSLATIONS_FLAG_SECTION = ".vf2trns"', 'TRANSLATIONS_DLL_NAME = "vf2tr_b200.dll"',
                   'TRANSLATIONS_INI_NAME = "vf2tr.ini"', 'GetProcAddress(module, "B200Tr_Startup")',
                   "if (gVF2Translations == 1) VF2LoadTranslationsDll();", '#pragma section(".vf2trns", read, write)',
                   "volatile unsigned char gVF2Translations = 0;", '"__VF2_TRANSLATIONS_RELATIVE_PATH__"',
                   "patch_translations_manifest(manifest)", f'TRANSLATIONS_SETTING = "{SETTING}"'):
        assert needle in gen, needle
    # loaded LAST: after the Unicode text DLLs it asks whether they draw UTF-8
    at = gen.index("if (gVF2Translations == 1) VF2LoadTranslationsDll();")
    assert gen.index('else if (gVF2UnicodeFont == 1) VF2LoadUnicodeDll("__VF2_UNICODE_FONT_RELATIVE_PATH__");') < at
    assert gen.count("gVF2Translations") == 3 and gen.count("gVF2Translations ==") == 1
    assert S.DLL_NAME == "vf2tr_b200.dll" and S.INI_KEY == "Translations" and S.INI_NAME == "vf2tr.ini"
    assert S.PATCHER_FOLDER == "Virtual Families 2 Patcher Files" and S.FLAG_SECTION == ".vf2trns"
    assert S.CHOICE_NAME == "Translation.ini" and S.COPY_NAME == "Translation.txt" and S.LOG_NAME == "Translations.log"
    bat = (RUNTIME / "native" / "build_b200tr.bat").read_text()
    assert "/W4 /WX" in bat and "b200tr.c" in bat and "/DB200TR_TEST" in bat
    assert "build_b200tr.bat" in (ROOT / "work" / "release_parallel.ps1").read_text(encoding="utf-8")
    rel = (ROOT / "work" / "export_release_bundle.py").read_text(encoding="utf-8")
    assert '("--translations-dll", args.translations_dll)' in rel and "vf2tr_b200.dll" in rel


def test_the_setting_row_is_optional_and_on_by_default():
    import export_offline_patch_bundle as X
    rows = {r["id"]: r for r in X.SETTINGS}
    row = rows[SETTING]
    assert row["label"] == "Translations"
    assert row["default"] is True and row["category"] == "optional"
    for needle in ("Translations window", "next game start", "stays in English", "Render Unicode with In-Game Fonts",
                   "Use Unicode Font", "English (original)", "companion DLL", "Virtual Families 2 Patcher Files"):
        assert needle in row["description"], needle
    assert SETTING in X.FINAL_PLAYTEST_DEFAULT_ON_SETTINGS and SETTING in X.SOURCE_BACKED_OPTIONAL_SETTINGS
    assert X.RUNTIME_FLAG_SECTION_BY_SETTING[SETTING] == ".vf2trns"
    sys.path.insert(0, str(ROOT / "src"))
    import offline_vf2_patcher_gui as gui
    assert SETTING not in gui.OWNERS_DEFAULT_OFF_SETTING_IDS          # Owner's Defaults ticks it


def test_the_exporter_ships_the_dll_and_ini_behind_the_setting(tmp_path):
    import export_offline_patch_bundle as X
    assert X.translations_asset_patches(tmp_path, None, {}) == []     # a build without the loader: nothing
    contract = {"Translations": {"companion_dll": X.TRANSLATIONS_DLL_NAME, "companion_ini": X.TRANSLATIONS_INI_NAME,
                                 "runtime_flag": {"source_section": ".vf2trns"}}}
    with pytest.raises(ValueError, match="--translations-dll"):
        X.translations_asset_patches(tmp_path, None, contract)
    wrong = tmp_path / "other.dll"
    wrong.write_bytes(b"MZ")
    with pytest.raises(ValueError):
        X.translations_asset_patches(tmp_path, wrong, contract)


def test_the_exporter_records(tmp_path, monkeypatch):
    import export_offline_patch_bundle as X
    dll = tmp_path / "in" / X.TRANSLATIONS_DLL_NAME
    dll.parent.mkdir()
    dll.write_bytes(b"MZ shipped B200Tr_Startup")
    monkeypatch.setattr(X, "require_vf2_pe32_x86", lambda path, label: None)
    contract = {"Translations": {"companion_dll": X.TRANSLATIONS_DLL_NAME, "companion_ini": X.TRANSLATIONS_INI_NAME}}
    out = tmp_path / "bundle"
    records = X.translations_asset_patches(out, dll, contract)
    assert [r["file_path"] for r in records] == ["Virtual Families 2 Patcher Files/vf2tr_b200.dll",
                                                 "Virtual Families 2 Patcher Files/vf2tr.ini"]
    for r in records:
        assert r["requires"] == ["core_executable", SETTING] and r["remove_when_disabled"] is True
    assert (out / "payload" / "Translations" / X.TRANSLATIONS_INI_NAME).read_bytes() == b"[Patches]\r\nTranslations=1\r\n"
    test_build = tmp_path / "t" / X.TRANSLATIONS_DLL_NAME
    test_build.parent.mkdir()
    test_build.write_bytes(b"MZ B200Tr_Startup B200Tr_TestInstall")
    with pytest.raises(ValueError, match="shipped build"):
        X.translations_asset_patches(out, test_build, contract)


# ===================================================================== with the executable
def test_a_damaged_executable_is_refused():
    """A check that cannot fail is not a check: a pin that is not the executable's bytes is refused."""
    gen = pytest.importorskip("gen_b200_translations_sites")
    exe = core_exe()
    data = bytearray(Path(exe).read_bytes())
    at = data.find(S.PINS[1].bytes[:16])
    assert at >= 0
    data[at + 2] ^= 0xFF
    with pytest.raises(Exception, match="differ"):
        gen.validate(bytes(data))


def test_the_pins_are_proved_and_the_header_is_fresh():
    gen = pytest.importorskip("gen_b200_translations_sites")
    exe = core_exe()
    got = gen.validate(Path(exe).read_bytes())
    assert got["GET_STRING"] == S.GET_STRING and got["COUNT"] == S.STRING_COUNT
    assert gen.render_header(gen.Exe(Path(exe).read_bytes())) == (SRC / "b200tr_sites.h").read_text()


def test_the_pins_resolve_in_every_other_executable():
    gen = pytest.importorskip("gen_b200_translations_sites")
    core = core_exe()
    exes = [OTHER_EXE] if OTHER_EXE and Path(OTHER_EXE).is_file() else []
    pattern = os.environ.get("VF2_B207_MATRIX_GLOB")
    if pattern:
        exes += glob.glob(pattern)
    if not exes:
        pytest.skip("no other executable (VF2_UNICODE_EXE, VF2_B207_MATRIX_GLOB)")
    for other in exes:
        got = gen.validate_variant(Path(other).read_bytes(), Path(core).read_bytes())
        assert got["TABLE"] > 0x400000 and got["COUNT"] >= 0xDE8, other


def test_the_committed_limits_cover_the_executables_scan():
    gen = pytest.importorskip("gen_b200_translations_sites")
    core = core_exe()
    exe = OTHER_EXE if OTHER_EXE and Path(OTHER_EXE).is_file() else core
    scan = gen.scan_limits(Path(exe).read_bytes(), Path(core).read_bytes())
    for k, v in scan["strncpy_room"].items():
        assert LIMITS["strncpy_room"][str(k)] <= v, k
    assert set(scan["english_length"]) <= set(LIMITS["english_length"])
    assert set(scan["format"]) <= set(LIMITS["format"])


# ===================================================================== the DLL, built and run
@pytest.fixture(scope="module")
def test_dll(tmp_path_factory):
    if not VCVARS or not Path(VCVARS).is_file():
        pytest.skip("VF2_VCVARS32 is not set to Visual Studio's vcvars32.bat")
    core_exe()
    pytest.importorskip("unicorn")
    out = tmp_path_factory.mktemp("b200tr")
    env = dict(os.environ, VF2_TR_BUILD_DIR=str(out))
    r = subprocess.run(["cmd.exe", "/d", "/c", str(RUNTIME / "native" / "build_b200tr.bat"), "test"], env=env,
                       capture_output=True, text=True)
    dll = out / "vf2tr_b200_test.dll"
    assert dll.is_file(), r.stdout + r.stderr
    assert "warning" not in r.stdout.lower(), r.stdout
    return dll


def test_the_shipped_dll_builds_clean(tmp_path):
    if not VCVARS or not Path(VCVARS).is_file():
        pytest.skip("VF2_VCVARS32 is not set to Visual Studio's vcvars32.bat")
    pefile = pytest.importorskip("pefile")
    env = dict(os.environ, VF2_TR_BUILD_DIR=str(tmp_path))
    r = subprocess.run(["cmd.exe", "/d", "/c", str(RUNTIME / "native" / "build_b200tr.bat")], env=env,
                       capture_output=True, text=True)
    dll = tmp_path / "vf2tr_b200.dll"
    assert dll.is_file(), r.stdout + r.stderr
    pe = pefile.PE(str(dll))
    exports = {e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    assert {"B200Tr_Startup", "B200Tr_TextW", "B200Tr_TextA", "B200Tr_English", "B200Tr_EnglishOf"} <= exports
    assert not any(n.startswith("B200Tr_Test") for n in exports), "the harness exports reached the shipped DLL"
    assert pe.OPTIONAL_HEADER.DllCharacteristics & 0x40 and pe.OPTIONAL_HEADER.DllCharacteristics & 0x100   # ASLR, DEP


@pytest.fixture(params=DELTAS, ids=["at_link_address", "relocated"])
def world(request, test_dll):
    import b200_translations_scenarios as T
    exe = OTHER_EXE if OTHER_EXE and Path(OTHER_EXE).is_file() else CORE_EXE
    return T.World(exe, test_dll, delta=request.param, core=CORE_EXE)


def _caption() -> int:
    """A villager's action caption: a line only strncpy(.., 0x27) copies (38 letters of room)."""
    return next(int(i) for i, v in LIMITS["strncpy_room"].items() if v == 38 and int(i) not in LIMITS["english_length"]
                and int(i) not in LIMITS["format"])


def _by_id(world):
    return {r[0]: r for r in world.records()}


def _install(world, translations, unicode=False, **kw):
    import b200_translations_scenarios as T
    return world.install(T.make_file(world, translations, **kw), unicode_active=unicode)


def test_a_translated_line_is_what_the_game_looks_up(world):
    english = _by_id(world)[112][2]
    assert _install(world, {113: RETRY, 5: "{name} voit son adorable animal."}) == 1
    st = world.status()
    assert st["installed"] == 1 and st["used"] == 2 and st["refused"] == 0 and st["guarded"] == 2 and st["resolved"] == 1
    assert world.manager_built == 1
    assert world.get_string(113) == RETRY.encode("cp1252")                  # Windows-1252: one byte for the e acute
    assert world.get_string(5) == b"{name} voit son adorable animal."
    assert world.fill(5, name=b"Zo\xeb") == b"Zo\xeb voit son adorable animal."
    assert world.get_string(112) == english                                  # a line not translated: the English
    assert sum(1 for v in world.table_overrides() if v) == 2


def test_the_games_person_choice_for_both_sexes(world):
    text = {i: r[2].decode("cp1252") for i, r in _by_id(world).items()}
    line = 861                                   # "{name} got that promotion {he/she} was hoping for! "
    assert text[line].startswith("{name} got that promotion {he/she}")
    french = "{name} : {il/elle} est promu !"
    assert len(french) <= len(text[line])
    assert _install(world, {line: french}) == 1
    female = world.fill(line, sex=0, size=1024)           # the game's sex flag: 0 takes the second word
    male = world.fill(line, sex=1, size=1024)
    assert male == b"Zo\xeb : il est promu !" and female == b"Zo\xeb : elle est promu !"


def test_a_translation_longer_than_its_room_shows_english(world):
    table = _by_id(world)
    caption = _caption()     # strncpy(.., 0x27): 38 letters
    exact = next(i for i in LIMITS["english_length"] if i != 36 and 3 <= len(table[i][2]) <= 30 and b"%" not in table[i][2]
                 and b"{" not in table[i][2])
    english = table[exact][2]
    assert _install(world, {caption: "x" * 38, exact: "Z" * (len(english) + 1)}) == 1
    assert world.get_string(caption) == b"x" * 38                              # exactly the room: used
    assert world.get_string(exact) == english                                  # one byte over its English: English
    st = world.status()
    assert st["used"] == 1 and st["refused"] == 1 and "too long for its space" in world.log()


def test_a_line_one_byte_over_the_field_shows_english(world):
    table = _by_id(world)
    caption = _caption()
    assert _install(world, {caption: "x" * 39, 113: RETRY}) == 1
    assert world.get_string(caption) == table[caption][2]
    assert world.status()["used"] == 1 and world.status()["refused"] == 1


@pytest.mark.parametrize("module, export, installed, want", [
    ("vf2unicode_b200.dll", 1, 1, 1),           # the Unicode DLL says its hooks are in: UTF-8
    ("vf2unicodefont_b200.dll", 1, 1, 1),
    ("vf2unicode_b200.dll", 0, 1, 0),           # it says they are not: Windows-1252 (its status block notwithstanding)
    ("vf2unicode_b200.dll", None, 1, 1),        # a DLL without the export: its status block's installed flag
    ("vf2unicode_b200.dll", None, 0, 0),
    (None, None, 0, 0),                         # no Unicode DLL loaded
])
def test_the_translations_dll_asks_unicode_text_active(world, module, export, installed, want):
    """B200Tr's unicode_text_active() in the DLL's own code: GetModuleHandleW of each Unicode DLL, then its
    B200Unicode_UnicodeTextActive() (stdcall, no arguments) or, without it, B200Unicode_Status."""
    import struct
    e = world.e
    handle, calls = 0x7300_0000, []
    fn = e.fake_code(b"\xC3")

    def active(em):
        calls.append(1)
        return export, 0
    e.seam_live(fn, active)
    status = e.alloc(0x40)
    e.write(status, struct.pack("<IIIII", 0x54584E55, 3, 1, 1, installed))      # 'UNXT', version, mode, resolved

    def get_module(em):
        if em.arg(0) == 0:
            return em.base, 4
        return (handle if em.wstr(em.arg(0)).lower() == module else 0), 4

    def get_proc(em):
        assert em.arg(0) == handle
        name = em.cstr(em.arg(1))
        if name in ("B200Unicode_UnicodeTextActive", "_B200Unicode_UnicodeTextActive@0"):
            return (fn if export is not None else 0), 8
        assert name == "B200Unicode_Status", name
        return status, 8
    e.imports.update({"GetModuleHandleW": get_module, "GetProcAddress": get_proc})
    assert e.call(e.dll_export("B200Tr_TestUnicodeActive")) == want
    assert len(calls) == (1 if export is not None else 0)


def test_the_room_of_an_accented_letter_counts_two_in_utf8(world):
    table = _by_id(world)
    caption = _caption()
    # the room counts UTF-8 bytes in either mode: 19 letters with accents are 38 bytes, 20 are 40 (past the field)
    assert _install(world, {caption: "é" * 20, 113: RETRY}, unicode=True) == 1
    assert world.get_string(caption) == table[caption][2]
    assert world.status()["textMode"] == 1 and world.status()["refused"] == 1
    assert world.get_string(113) == RETRY.encode("utf-8")


def test_nineteen_accented_letters_fit_in_either_mode(world):
    caption = _caption()
    assert _install(world, {caption: "é" * 19}, unicode=False) == 1
    assert world.get_string(caption) == b"\xe9" * 19                              # 19 bytes in the game, 38 as counted


def test_the_games_own_letters_when_the_unicode_hooks_are_not_installed(world):
    text = "R\u00e9essayer \u2014 \u20ac \u2713"
    assert _install(world, {113: text}, unicode=False) == 1
    assert world.get_string(113) == b"R\xe9essayer - EUR ?"                       # the sheets have no picture for the
    assert world.status()["textMode"] == 0                                         # dash or the euro; no mapping: "?"


def test_a_character_the_games_sheets_lack_is_never_written_as_a_byte_that_draws_an_exclamation_mark(world):
    """The game's letter sheets (Segoe 24 / 24 Bold / 32 Bold / 36 Bold) have no picture for the bytes 80h to A1h: the
    game draws entry 0, "!", for such a byte. Without the Unicode text DLL a French line is written with the plain
    characters those stand for; the guillemets (AB / BB), the accented letters and the middle dot are in the sheets."""
    text = "Oui\u00a0! C\u0153ur\u2026 \u00ab\u00a0bon\u00a0\u00bb l\u2019\u00e9t\u00e9 \u201cx\u201d 50\u202f% \u00bf\u00a1"
    assert _install(world, {113: text}, unicode=False) == 1
    got = world.get_string(113)
    assert got == b"Oui ! Coeur... \xab bon \xbb l'\xe9t\xe9 \"x\" 50 % \xbf!"
    assert not any(0x80 <= b <= 0xA1 for b in got)


def test_utf8_when_the_unicode_hooks_are_installed(world):
    text = "Réessayer — € ✓ ЖЯ"
    assert _install(world, {113: text}, unicode=True) == 1
    assert world.get_string(113) == text.encode("utf-8")
    assert world.status()["textMode"] == 1


def test_a_file_for_another_game_changes_nothing(world):
    before = world.entry_bytes("strncpy", 16), world.entry_bytes("sprintf", 16)
    assert _install(world, {113: RETRY}, game="Fish Tycoon") == 0
    assert world.status()["installed"] == 0 and world.status()["guarded"] == 0
    assert "another game" in world.log()
    assert (world.entry_bytes("strncpy", 16), world.entry_bytes("sprintf", 16)) == before
    assert not any(world.table_overrides())
    assert world.get_string(113) == b"Try Again"
    assert world.protect_calls == []                                           # no code page was touched


def test_a_file_with_nothing_usable_changes_nothing(world):
    assert _install(world, {113: RETRY + " {name}"}) == 0                      # a placeholder the English lacks
    assert "no translated line could be used" in world.log()
    assert not any(world.table_overrides()) and world.get_string(113) == b"Try Again"
    assert world.protect_calls == []


def test_a_bad_line_shows_english_and_the_others_work(world):
    table = _by_id(world)
    assert _install(world, {113: RETRY, 5: "pas de nom ici", 112: "Retour"}) == 1
    assert world.get_string(113) == RETRY.encode("cp1252")
    assert world.get_string(5) == table[5][2]
    st = world.status()
    assert st["used"] == 2 and st["refused"] == 1 and "placeholders" in world.log()


def test_the_games_decimal_point_is_never_translated(world):
    assert _install(world, {36: ",", 113: RETRY}) == 1
    assert world.get_string(36) == b"."
    assert "never translated" in world.log()


def test_a_changed_english_shows_english(world):
    import b200_translations_scenarios as T
    data = T.make_file(world, {113: RETRY}).replace(b"Try Again", b"Try Again!")
    assert world.install(data) == 0
    assert world.get_string(113) == b"Try Again"
    assert "does not match the key" in world.log()


def test_the_percent_rule_in_a_printf_format_line(world):
    table = _by_id(world)
    fmt = 20                                                                    # "You have been awarded %d coins!"
    assert table[fmt][2] == b"You have been awarded %d coins!" and fmt in LIMITS["format"]
    translation = "50 % : %d pièces"
    assert tf.check_translation(table[fmt][2].decode(), translation, "fr", is_format=True)[0] == []
    assert tf.runtime_text(translation, table[fmt][2].decode(), True) == "50 %% : %d pièces"
    assert _install(world, {fmt: translation}) == 1
    out = world.get_string_ptr(fmt)
    assert world.e.cstr(out).encode("latin-1") == "50 %% : %d pièces".encode("cp1252")
    assert world.sprintf(out, 7) == "50 % : 7 pièces".encode("cp1252")   # printf shows one percent sign


def test_the_percent_rule_in_a_line_that_is_no_format(world):
    table = _by_id(world)
    plain = 112
    assert plain not in LIMITS["format"] and b"%" not in table[plain][2]
    translation = "Retour 50 %"
    assert _install(world, {plain: translation}) == 1
    assert world.e.cstr(world.get_string_ptr(plain)) == translation               # handed on as written


def test_strncpy_ends_a_translated_line_with_its_nul_as_the_english_copy_does(world):
    table = _by_id(world)
    line = "Essayer à nouveau, encore"
    assert _install(world, {113: line}) == 1
    ptr = world.get_string_ptr(113)
    n = len(table[113][2]) + 2                          # the caller's count: more than the English (9), less than the line
    assert len(line) > n
    got = world.strncpy(ptr, n)
    assert got == line.encode("cp1252")[:n - 1] + b"\0"
    # a copy of the start of a line that is longer than the count, in English too (the template filler's), is as before
    got = world.strncpy(ptr, 4)
    assert got == line.encode("cp1252")[:4]
    # a line that fits is copied whole
    got = world.strncpy(ptr, 200, size=300)
    assert got.split(b"\0")[0] == line.encode("cp1252")


def test_a_pointer_that_is_not_a_translated_line_is_copied_as_it_is(world):
    assert _install(world, {113: RETRY}) == 1
    src = world.cstring(b"Not a translated line at all, however long it is")
    assert world.strncpy(src, 10) == b"Not a tran"
    assert world.strncpy(src, 200, size=300).split(b"\0")[0] == b"Not a translated line at all, however long it is"


def test_sprintf_with_a_translated_argument_is_cut_to_the_english_length(world):
    table = _by_id(world)
    assert len(table[6][2]) == 7                                                   # "Petting"
    assert _install(world, {6: "Cajoler"}) == 1                                    # seven letters: the same room
    fmt = world.cstring(b"[%s]")
    assert world.sprintf(fmt, world.get_string_ptr(6)) == b"[Cajoler]"
    assert world.sprintf(fmt, world.cstring(b"anything else")) == b"[anything else]"
    assert world.sprintf(world.cstring(b"%d items"), 5) == b"5 items"              # an ordinary call is untouched


def test_sprintf_with_a_translated_format_is_cut_to_the_english_result(world):
    table = _by_id(world)
    assert 113 not in LIMITS["english_length"] and str(113) not in LIMITS["strncpy_room"]
    line = "Essayer \u00e0 nouveau, encore"
    assert _install(world, {113: line}) == 1
    out = world.get_string_ptr(113)
    assert world.sprintf(out) == line.encode("cp1252")[:len(table[113][2])]        # the English gives 9 bytes
    assert world.sprintf(world.cstring(b"[%s]"), out) == b"[" + line.encode("cp1252")[:9] + b"]"


def test_the_order_of_the_writes_trampolines_first(world):
    assert _install(world, {113: RETRY}) == 1
    calls = world.protect_calls
    tramp = [c for c in calls if c[1] == 16]
    entries = [c for c in calls if c[1] == 5]
    assert len(tramp) == 2 and len(entries) == 4                               # (make writable, restore) x 2
    assert all(c[2] == 0x40 for c in tramp)
    assert max(c[3] for c in tramp) < min(c[3] for c in entries)               # every trampoline before any entry
    # the entries now start with a jmp to a guard in the DLL
    for name in ("strncpy", "sprintf"):
        b = world.entry_bytes(name, 5)
        assert b[0] == 0xE9, name
        target = (world.site(name) + 5 + int.from_bytes(b[1:5], "little", signed=True)) & 0xFFFFFFFF
        assert 0x30000000 <= target < 0x30200000, hex(target)


def test_the_patches_own_text_is_handed_to_the_companion_dlls(world):
    assert _install(world, {"patch/time.pause": "Mettre en pause", "patch/time.time_controls": "Gestion du temps",
                            113: RETRY}) == 1
    assert world.status()["patchLines"] == 2
    assert world.text_w("Pause") == "Mettre en pause"                       # a wide text, by its English
    assert world.text_w("Resume") == "Resume"                               # no translation: the English itself
    assert world.text_a("Time Controls", 24) == b"Gestion du temps"          # a narrow text, within its room
    assert world.text_a("Time Controls", 10) == b"Time Controls"             # too long for the room: English
    assert world.get_string(113) == RETRY.encode("cp1252")                   # the game's own lines are not disturbed


def test_a_patch_text_with_places_is_a_format_and_a_plain_percent_is_doubled(world):
    status = "%s. Speed: %s."
    assert _install(world, {"patch/time.s_speed_s": "%s. Vitesse : %s \u00e0 50 %."}) == 1
    got = world.text_w(status)
    assert got == "%s. Vitesse : %s \u00e0 50 %%."                           # FormatW writes "%%" as one percent sign
    assert tf.runtime_text("%s. Vitesse : %s \u00e0 50 %.", status, True) == got


def test_a_patch_text_that_changes_its_places_shows_english(world):
    assert _install(world, {"patch/time.s_speed_s": "%s. Vitesse."}) == 0           # one place short: refused
    assert "placeholders" in world.log()
    assert world.text_w("%s. Speed: %s.") == "%s. Speed: %s."


def test_a_patch_text_longer_than_its_room_shows_english(world):
    assert _install(world, {"patch/time.pause": "x" * 81, "patch/time.resume": "x" * 80}) == 1
    assert world.text_w("Pause") == "Pause"                                          # 81 bytes: refused, English
    assert world.status()["used"] == 2 and world.status()["refused"] == 0          # both read; the room is checked when handed out
    assert world.text_w("Resume") == "x" * 80
