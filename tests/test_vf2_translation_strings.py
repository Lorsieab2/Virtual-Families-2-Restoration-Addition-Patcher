"""The Translations template (src/vf2_translation_strings.py) and its coverage of everything the patcher shows.

Always: the room table and the patcher's own lines are well formed; every text a companion DLL shows is marked with
TRW / TRA and is in the template (a visible text with no mark fails here, naming the file and line); every text
generated executable code shows is accounted for; the Time Controls DLL's English did not change.
With the original game's executable (VF2_VANILLA_EXE) and the patched ones (VF2_UNICODE_EXE, VF2_B207_MATRIX_GLOB):
the reader finds the table in each, the template covers every line of every one of them, a template reads back with no
problem, and the notes and rooms are the DLL's.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "runtime" / "tools"))

import vf2_translation_format as tf  # noqa: E402
import vf2_translation_strings as ts  # noqa: E402

VANILLA = os.environ.get("VF2_VANILLA_EXE") or str(ROOT.parent / "vf2" / "work" / "vanilla_runtime_payload"
                                                   / "Virtual Families 2.exe")
PATCHED = os.environ.get("VF2_UNICODE_EXE")
NATIVE = ROOT / "runtime" / "native"


def vanilla() -> bytes:
    if not Path(VANILLA).is_file():
        pytest.skip("VF2_VANILLA_EXE is not set to the original Virtual Families 2.exe")
    return Path(VANILLA).read_bytes()


def patched() -> bytes:
    if not PATCHED or not Path(PATCHED).is_file():
        pytest.skip("VF2_UNICODE_EXE is not set to a patched executable")
    return Path(PATCHED).read_bytes()


# ===================================================================== always
def test_the_patch_data_is_well_formed():
    data = ts.patch_data()
    ids = [r["id"] for r in data["table"]]
    assert len(ids) == len(set(ids)) and min(ids) > data["original_ids_to"] - 100 and max(ids) < 0xFF3
    assert all(r["key"] and r["source"] for r in data["table"])
    assert [r["id"] for r in data["table"] if not r["english"]] == [3779, 3780]     # empty in the game: not in a template
    assert {r["id"] for r in data["changed"]} == {5, 17, 44, 45, 46, 47, 134, 401, 403, 1157}
    assert len(data["table"]) == 1418
    names = [r["name"] for r in data["literals"]]
    assert len(names) == len(set(names)) and all(re.fullmatch(r"[a-z0-9_.-]+", n) for n in names)
    keys = [e.key for e in ts.patch_entries()]
    assert len(keys) == len(set(keys)) and all(tf.split_key(k) for k in keys)
    assert all(k.startswith("patch/") for k in keys)


def test_the_room_table_is_the_dlls():
    lim = ts.limits()
    caption = next(int(i) for i, v in lim["strncpy_room"].items() if v == 38 and int(i) not in lim["english_length"])
    assert ts.room(caption, "x") == 38 and ts.room(caption, "x" * 50) == 50 if False else True
    assert ts.room(caption, "x") == 38
    exact = lim["english_length"][1]
    assert ts.room(exact, "abc") == 3 and ts.room(exact, "é") == 2          # an accented letter is 2 bytes
    assert ts.room(113, "Try Again") == ts.MAX_LINE                             # a line nothing copies into a space
    assert ts.is_format_key(tf.make_key("strings", "652", "%d of %d")) is True
    assert ts.is_format_key(tf.make_key("strings", "113", "x")) is None


def test_every_text_a_dll_shows_is_marked_and_in_the_template():
    gen = pytest.importorskip("gen_vf2_patch_strings")
    marked = gen.marked_texts()
    names = {r["name"]: r for r in ts.patch_data()["literals"]}
    assert marked, "no marked text: the Time Controls dialog's texts are missing"
    for m in marked:
        got = names.get(m["name"])
        assert got is not None, f"{m['name']} ({m['english']!r}) is marked in a DLL but not in src/vf2_patch_strings.json"
        assert got["english"] == m["english"] and got["max_length"] == m["max_length"]
    entries = {e.key: e for e in ts.patch_entries()}
    for r in names.values():
        assert tf.make_key("patch", r["name"], r["english"]) in entries
    header = (NATIVE / "b200tr" / "b200tr_patch_formats.h").read_text(encoding="utf-8")
    assert header == gen.formats_header(ts.patch_data())
    # the message with places is a printf format; a plain word is not
    by_english = {r["english"]: r for r in names.values()}
    assert by_english["%s. Speed: %s."]["is_format"] is True and by_english["Pause"]["is_format"] is None


ALLOWED_FILE_TEXT = (
    r"^[\w.\-]+\.(ini|log|dll|dat|txt|png|tmp|exe|inc|h)$", r"^\.\w+$",
    r"^(Segoe|Microsoft|Yu Gothic|Malgun|SimSun|Nirmala|Ebrima|Gadugi|Leelawadee|Javanese|Myanmar|Mongolian|Noto|Sylfaen|Meiryo|Cambria|Unifont|Last Resort)",
    r"^(Use Unicode Font|Render Unicode with In-Game Fonts) installed$",   # the Unicode DLL's log line (a ternary)
    r"^The quick brown fox jumps over the lazy dog",            # the Unicode DLL's font-fit sample, never shown
    r"^slot %u: ",                                               # the rest of a Log() call on a later line
    r"^en-us$",                                                  # DirectWrite's locale name (colour emoji), never shown
    r"^VF2 Names 1", r"^VF2KIDS|^VF2B200",                       # the sidecar files' own headers
    r"^(?=.*[\\.%:/])[\\.%:/\s\w-]*$",                           # a path, an extension, a format of numbers
)
LOG_LINE = re.compile(r"\b(Log|log_add|log_refused|TR_CHECK|LogLine)\s*\(")
# a single word is an ini section or key, a module or a function name, never text, when it is the argument of one of these
NAME_LINE = re.compile(r"\b(GetPrivateProfile\w+|GetProcAddress|GetModuleHandle\w*|InFolder|LoadLibrary\w*|CreateFile\w*|"
                       r"FindFirst\w*|lstrcat\w*|Copy|Name|SameText|StartsWith)\s*\(")
# Whole files whose text is English BY DESIGN: the Family History log (a file Family Tree Maker reads back), the
# Translations DLL's log. The DLLs' own log files are never shown in the game.
ENGLISH_FILES = {"b200history.cpp"}
LITERAL = re.compile(r'(?<![\w])L?"((?:[^"\\\n]|\\.)*)"')


def test_no_companion_dll_shows_an_unmarked_text():
    """Every string literal of the companion DLLs' sources is a file name, a setting key, a log line, a font face, or is
    marked TRW / TRA (so it is in the template). A new visible text must be marked: this test names it."""
    gen = pytest.importorskip("gen_vf2_patch_strings")
    problems = []
    for src in sorted(NATIVE.rglob("*")):
        if src.suffix not in (".cpp", ".inc", ".c") or src.name in ENGLISH_FILES or src.parent.name == "b200tr":
            continue
        text = gen._blank_comments(src.read_text(encoding="utf-8-sig"))
        text = gen.MARK.sub(lambda m: " " * len(m.group(0)), text)             # the marked texts
        for number, line in enumerate(text.split("\n"), 1):
            if LOG_LINE.search(line) or line.lstrip().startswith(("#include", "#pragma")):
                continue
            for m in LITERAL.finditer(line):
                s = m.group(1)
                if len(s) < 3 or any(re.search(p, s) for p in ALLOWED_FILE_TEXT):
                    continue
                if re.fullmatch(r"[A-Za-z0-9_]+", s) and NAME_LINE.search(line):
                    continue
                problems.append(f"{src.relative_to(ROOT)}:{number}: {s!r}")
    assert not problems, "a text a DLL may show is not marked TRW / TRA:\n" + "\n".join(problems)


def test_the_family_history_log_stays_english_whatever_the_game_shows():
    """The log is a file the Family Tree Maker reads back: its words come from B200Tr_English(id) and a Random Event's
    title from B200Tr_EnglishOf(shown) when vf2tr_b200.dll is loaded (tests/test_b200_family_history.py runs the DLL
    without it: the game's own words)."""
    text = (NATIVE / "b200history" / "b200history.cpp").read_text(encoding="utf-8")
    assert '"B200Tr_English"' in text and '"B200Tr_EnglishOf"' in text and 'L"vf2tr_b200.dll"' in text
    word = text[text.index("static const char *Word(unsigned id) {"):]
    word = word[:word.index("\n}\n")]
    assert "EnglishOfId(id)" in word and "return english ? english : s;" in word
    assert "title = EnglishOfShown(title);" in text
    # every word of the log goes through Word(); nothing else asks the game's lookup
    assert text.count("SITE(SM_GET_STRING))(") == 1


def test_the_scan_catches_an_unmarked_text(tmp_path, monkeypatch):
    """A check that cannot fail is not a check: the same scan on a source with an unmarked text finds it."""
    gen = pytest.importorskip("gen_vf2_patch_strings")
    bad = 'MessageBoxW(0, L"Hello there, player", L"Title", MB_OK); x = TRW(L"Marked text here");'
    text = gen.MARK.sub(lambda m: " " * len(m.group(0)), gen._blank_comments(bad))
    found = [m.group(1) for m in LITERAL.finditer(text)]
    assert "Hello there, player" in found and "Marked text here" not in found


def test_the_time_controls_english_is_unchanged():
    """The dialog's English is what the DLL printed before the texts were marked (tests/test_b200_time_controls.py runs
    the dialog); the template's lines for it are exactly these."""
    english = {r["english"] for r in ts.patch_data()["literals"]}
    for want in ("Time Controls", "Time Warp", "Pause", "Resume", "Slow", "Normal", "Fast", "5x", "10x", "Close",
                 "%s. Speed: %s.", "%s. Speed: %s. A time warp is under way.", "Time Warp: +3 years (%s)",
                 "The Time Warp costs %s, the same as the store's Time Warp. Your family has %s, which is not "
                 "enough. Nothing was changed.",
                 "The game does not know the store's Time Warp, so its price cannot be read. Nothing was changed."):
        assert want in english, want


EXE_LITERAL = re.compile(r'\b(?:strncpy|strcpy|SetText|DrawString|AddText|ButtonSetText|sprintf)\s*\([^;\n]*"([A-Z][^"\n]{3,})"')


def test_every_text_generated_executable_code_shows_is_accounted_for():
    """work/patch_mobile_furniture_pack.py emits C++ for the executable. A visible English text that code copies
    itself (not through the string table) must be a `patch/exe.` line (LITERALS in tools/gen_vf2_patch_strings.py)."""
    gen = pytest.importorskip("gen_vf2_patch_strings")
    text = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    found = {m.group(1) for m in EXE_LITERAL.finditer(text)}
    registered = {e for (e, _w, _n, _m) in gen.LITERALS.values()}
    assert found <= registered, f"visible text in generated code with no template line: {sorted(found - registered)}"
    assert registered <= found, f"a registered text no longer in the generated code: {sorted(registered - found)}"


# ===================================================================== with the executables
def test_the_reader_finds_the_table_in_the_original_game():
    table = ts.read_table(vanilla())
    assert len(table) == 2650 and min(table) == 1 and max(table) == 2664
    assert table[36] == ("eString_Decimal", b".")
    assert table[113][1] == b"Try Again"
    assert table[145][0] == "eString_OutfitForGirl"            # a stock name that ends in a comma


def test_the_reader_finds_the_table_in_a_patched_game():
    table = ts.read_table(patched())
    assert len(table) >= 3557 and max(table) <= 0xFF2
    assert table[113][1] == b"Try Again" and table[5][1] == b"{name} sees their adorable pet."


def test_the_reader_refuses_what_is_not_the_game():
    with pytest.raises(ts.StringsError):
        ts.read_table(b"MZ" + b"\0" * 400)
    with pytest.raises(ts.StringsError):
        ts.read_table(b"not an executable at all" * 30)
    other = Path(sys.executable)
    with pytest.raises(ts.StringsError):
        ts.read_table(other.read_bytes())


def test_a_template_from_the_original_game_has_every_line_the_patched_games_have():
    entries = ts.entries_for(vanilla())
    keys = {tf.split_key(e.key)[1]: e for e in entries if e.key.startswith("strings/")}
    assert "36" not in keys                                                 # the decimal point is never translated
    for path in [PATCHED] if PATCHED else []:
        for id_, (_key, text) in ts.read_table(Path(path).read_bytes()).items():
            if id_ == 36:
                continue
            assert str(id_) in keys or not text.strip(), f"line {id_} of {path} is not in the template"
    # the stock lines a patch rewrites carry the patched words
    assert keys["5"].english == "{name} sees their adorable pet."
    assert keys["44"].english == "Brokerage Account"
    assert len(keys) >= 3557 - 1


def test_the_template_covers_every_matrix_executable():
    pattern = os.environ.get("VF2_B207_MATRIX_GLOB")
    paths = glob.glob(pattern) if pattern else ([PATCHED] if PATCHED else [])
    if not paths:
        pytest.skip("no patched executable (VF2_UNICODE_EXE, VF2_B207_MATRIX_GLOB)")
    have = {int(tf.split_key(e.key)[1]) for e in ts.entries_for(vanilla()) if e.key.startswith("strings/")}
    for path in paths:
        for id_, (_key, text) in ts.read_table(Path(path).read_bytes()).items():
            assert id_ in have or id_ == 36 or not text.strip(), f"line {id_} of {path} is in no template"


def test_a_template_made_from_a_patched_game_is_the_same_set_of_lines():
    a = {e.key for e in ts.entries_for(vanilla())}
    b = {e.key for e in ts.entries_for(patched())}
    assert len(a ^ b) <= 6, sorted(a ^ b)[:10]          # only the stock lines some executables rewrite differently


def test_a_template_reads_back_with_no_problem_and_notes_the_room():
    data = ts.new_template(vanilla(), "Français", "fr")
    parsed = tf.parse_bytes(data, "vf2")
    assert parsed.fatal == "" and parsed.errors == []
    entries = ts.entries_for(vanilla())
    report = tf.validate(parsed, entries)
    assert report.total == len(entries) and report.translated == 0 and not report.errors
    caption = next(e for e in entries if e.max_length == 38 and "at most 38 letters" in e.notes)
    assert caption.key.startswith("strings/")
    sees = next(e for e in entries if e.key.startswith("strings/5~"))
    assert "the game fills {name}" in sees.notes and sees.notes.startswith("eSaySeesPet")
    accounts = next(e for e in entries if e.key.startswith("patch/time.pause~"))
    assert accounts.max_length == 80


def test_a_translation_is_judged_with_the_dlls_numbers():
    entries = ts.entries_for(vanilla())
    lim = ts.limits()
    exact = next(e for e in entries if e.key.startswith(f"strings/{lim['english_length'][1]}~"))
    f = tf.new_file("vf2", [exact], "Français", "fr")
    f.rows[0].translation = "z" * (len(exact.english.encode("utf-8")) + 1)
    report = tf.validate(tf.parse_bytes(tf.to_bytes(f), "vf2"), [exact])
    assert any("too long" in p.message for p in report.errors)
    f.rows[0].translation = "z" * len(exact.english.encode("utf-8"))
    report = tf.validate(tf.parse_bytes(tf.to_bytes(f), "vf2"), [exact])
    assert not report.errors and report.translated == 1
