"""Game Font Text (src/vf2_text_tool.py): any text drawn in the game's own fonts and saved as a PNG.

Always run: the accent groups, the character search by name and by code, the status counts, the text encoded
(vf2_game_text.encode) before it is drawn, the export choices (the Picture Maker's own). With the original game's
Images (work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR), else skipped: the letters drawn, the PNG sizes,
and the window built off-screen (skipped without a display).
"""
from __future__ import annotations

import os
import struct
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vf2_game_text as T  # noqa: E402
import vf2_picture_image as pi  # noqa: E402
import vf2_picture_maker as pm  # noqa: E402
import vf2_text_tool as tt  # noqa: E402

GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
HAVE_FONTS = all((GAME_DIR / "Images" / f"{n}.png").is_file() for n in T.FONT_NAMES)
needs_fonts = pytest.mark.skipif(not HAVE_FONTS, reason="no original game folder (work/vanilla_runtime_payload)")


@pytest.fixture(scope="module")
def fonts():
    if not HAVE_FONTS:
        pytest.skip("no original game folder (work/vanilla_runtime_payload)")
    import vf2_glyph_maker
    return vf2_glyph_maker.load_fonts(GAME_DIR / "Images")


def _png_size(path: Path) -> tuple:
    data = path.read_bytes()
    assert data[:8] == pi.PNG_MAGIC
    return struct.unpack(">II", data[16:24])


# ====================================================================== accents
def test_every_accent_is_one_named_character():
    assert len(tt.ACCENTS) == 12
    for language, letters in tt.ACCENTS.items():
        assert letters, language
        assert len(set(letters)) == len(letters), language            # no letter twice in a language
        for ch in letters:
            assert len(ch) == 1, (language, ch)
            assert unicodedata.normalize("NFC", ch) == ch, (language, ch)
            assert unicodedata.name(ch, None), (language, ch)
            assert tt.insertable(ord(ch))


def test_the_languages_asked_for_have_their_letters():
    for language, must in (("Turkish", "ıİğĞşŞ"), ("Romanian", "șțȘȚ"), ("German", "ßẞäÖ"), ("Polish", "łŁąŻ"),
                           ("Czech", "řůŘŮ"), ("Hungarian", "őűŐŰ"), ("French", "œŒçÿŸ"), ("Spanish", "ñÑ¿¡"),
                           ("Portuguese", "ãõÃ"), ("Italian", "ìò")):
        for ch in must:
            assert ch in tt.ACCENTS[language], (language, ch)
    nordic = next(v for k, v in tt.ACCENTS.items() if k.startswith("Nordic"))
    for ch in "åæøðþÅÆØÐÞ":
        assert ch in nordic
    vietnamese = tt.ACCENTS["Vietnamese"]
    assert len(vietnamese) == 2 * (7 + 12 * 5)                       # ă â ê ô ơ ư đ, 12 vowels x 5 tones, both cases
    for ch in "ăâđêôơưệỘửỹẠ":
        assert ch in vietnamese
    assert "ș" in tt.ACCENTS["Romanian"] and "ş" not in tt.ACCENTS["Romanian"]   # comma below, not cedilla


# ====================================================================== any character
def test_codes_are_read_in_every_usual_form():
    assert tt.parse_code("U+2603") == 0x2603
    assert tt.parse_code("u+2603") == 0x2603
    assert tt.parse_code("2603") == 0x2603
    assert tt.parse_code("0x2603") == 0x2603
    assert tt.parse_code("U+12000") == 0x12000
    assert tt.parse_code(" U+1F600 ") == 0x1F600
    assert tt.parse_code("face") is None               # all hex letters, but a word: a name
    assert tt.parse_code("snowman") is None
    assert tt.parse_code("U+110000") is None           # past the last code point
    assert tt.parse_code("D800") is None               # half of a UTF-16 pair: not a character
    assert tt.parse_code("") is None


def test_search_by_name_and_by_code():
    assert tt.search("snowman")[0] == 0x2603
    assert tt.search("U+2603")[0] == 0x2603
    assert tt.search("2603")[0] == 0x2603
    assert tt.search("U+12000")[0] == 0x12000
    assert unicodedata.name(chr(0x12000)) == "CUNEIFORM SIGN A"
    found = tt.search("smiling face")
    assert 0x263A in found and 0x1F642 in found               # white smiling face, slightly smiling face
    assert all("SMILING" in unicodedata.name(chr(c)) and "FACE" in unicodedata.name(chr(c)) for c in found)
    assert tt.search("☃") == [0x2603]                   # a pasted character finds itself
    assert tt.search("𒀀") == [0x12000]
    assert tt.search("a")[0] == ord("a")
    assert len(tt.search("latin")) == tt.SEARCH_LIMIT
    assert tt.search("") == [] and tt.search("   ") == []
    assert tt.search("no such character name at all") == []


def test_only_real_characters_are_inserted():
    assert tt.insertable(0x2603) and tt.insertable(0x12000) and tt.insertable(0x1F600) and tt.insertable(0x09)
    assert not tt.insertable(0xD800) and not tt.insertable(0x0378) and not tt.insertable(0x07)
    assert tt.char_name(0x2603) == "Snowman"
    assert tt.char_name(0x0378) == "Not a character yet"
    assert tt.code_text(0x41) == "U+0041" and tt.code_text(0x12000) == "U+12000"


def test_halves_of_utf16_pairs_are_joined_or_dropped():
    assert tt.clean_text("a😀b") == "a\U0001F600b"
    assert tt.clean_text("a\ud83db") == "ab"
    assert tt.clean_text("plain é") == "plain é"


# ====================================================================== the text: encoded, counted
def test_the_text_is_encoded_before_it_is_drawn(monkeypatch):
    seen = []

    def fake_render(font, sheet, raw, rgb=(255, 255, 255), *, max_width=0, background=None):
        seen.append((raw, rgb, max_width))
        return pi.Image(1, 1)

    monkeypatch.setattr(T, "render", fake_render)
    tt.render_text(None, None, "café", (1, 2, 3), 0)
    tt.render_text(None, None, "Łódź ☃", (255, 255, 255), 120)
    tt.render_text(None, None, "a😀", (0, 0, 0), -5)
    assert seen[0] == (b"caf\xe9", (1, 2, 3), 0)                       # Latin-1 stays one byte, as a save keeps it
    assert seen[1] == ("Łódź ☃".encode("utf-8"), (255, 255, 255), 120)
    assert seen[2] == ("a\U0001F600".encode("utf-8"), (0, 0, 0), 0)
    assert seen[0][0] == T.encode("café") and seen[1][0] == T.encode("Łódź ☃")


def test_counts_without_a_game_folder():
    c = tt.counts(None, "Zoë 👩🏽‍💻\nhi")
    assert c["characters"] == T.length("Zoë 👩🏽‍💻\nhi") == 8
    assert c["bytes"] == len(T.encode("Zoë 👩🏽‍💻\nhi"))
    assert (c["game"], c["patcher"], c["missing"]) == (0, 0, 0)
    assert tt.status_text(c, False) == f"8 characters; stored size {c['bytes']} bytes."


@needs_fonts
def test_counts_say_where_each_letter_comes_from(fonts):
    font, _sheet = fonts["Segoe24"]
    text = "Ab é\nŁ☃𒀀\U0010FFFD"
    c = tt.counts(font, text)
    assert c["characters"] == T.length(text) == 9          # the line break is a character too
    assert c["bytes"] == len(T.encode(text))
    assert c["game"] == 4                                  # A b space é
    assert c["patcher"] == 3                               # Ł (patcher-made), ☃ (patcher-made), 𒀀 (Windows font)
    assert c["missing"] == 1                               # a private-use character no font draws
    said = tt.status_text(c)
    assert "From the game font: 4. Patcher-made: 3. Missing (drawn as a box): 1." in said
    assert tt.char_label(font, "é") == "(game font)"
    assert tt.char_label(font, "Ł") == "(patcher-made)"
    assert tt.char_label(font, "\U0010FFFD") == "(missing: box)"


@needs_fonts
def test_drawn_text_is_the_games_render(fonts):
    font, sheet = fonts["Segoe32Bold"]
    image = tt.render_text(font, sheet, "Hello ☃\nwörld", (0x80, 0x4C, 0x05))
    assert image == T.render(font, sheet, T.encode("Hello ☃\nwörld"), (0x80, 0x4C, 0x05))
    assert image.height == 2 * font.line_height
    colours = {bytes(image.data[i:i + 3]) for i in range(0, len(image.data), 4) if image.data[i + 3]}
    assert colours and all(c[0] <= 0x80 and c[1] <= 0x4C and c[2] <= 0x05 for c in colours)   # tinted by AND
    wrapped = tt.render_text(font, sheet, "one two three four five six", wrap_width=60)
    assert wrapped.height > font.line_height and wrapped.width <= 60 + font.line_height


# ====================================================================== export
def test_export_choices_are_the_picture_makers():
    for args in (("1x",), ("2x",), ("4x",), ("custom", "300", ""), ("custom", "", "40", False)):
        assert tt.export_options(*args) == pm.export_options(*args)
    with pytest.raises(pi.PictureError):
        tt.export_options("custom", "abc", "")


def test_file_names():
    assert tt.file_name("Hello: world?\nsecond", "Segoe24") == "Hello- world- - Segoe24"
    assert tt.file_name("\n\n", "Segoe24Bold") == "Game font text - Segoe24Bold"
    assert tt.file_name("x" * 100, "Segoe24") == "x" * 40 + " - Segoe24"


@needs_fonts
def test_png_sizes(fonts, tmp_path):
    font, sheet = fonts["Segoe24"]
    image = tt.render_text(font, sheet, "Size ☃")
    base = image.cropped(pi.MARGIN)
    for size, factor in (("1x", 1), ("2x", 2), ("4x", 4)):
        path = pi.save_png(image, tmp_path / f"{size}.png", **tt.export_options(size))
        assert _png_size(path) == (base.width * factor, base.height * factor)
    path = pi.save_png(image, tmp_path / "custom.png", **tt.export_options("custom", "500", ""))
    assert _png_size(path)[0] == 500
    path = pi.save_png(image, tmp_path / "bare.png", **tt.export_options("1x", margin=False))
    assert _png_size(path) == (base.width - 2 * pi.MARGIN, base.height - 2 * pi.MARGIN)
    corner = pi.load_png(tmp_path / "1x.png", fast=False).pixel(0, 0)
    assert corner[3] == 0                                                  # a clear background


# ====================================================================== the window
@pytest.fixture
def tk_root():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except Exception as exc:
        pytest.skip(f"no display available for Tk ({exc})")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_tk_keeps_every_character(tk_root):
    """Tk 8.6 holds characters past U+FFFF (Python hands them over as UTF-16 pairs and gets them back whole)."""
    import tkinter as tk
    box = tk.Text(tk_root)
    text = "a\U0001F600b\U00012000 👩🏽‍💻 é́"
    box.insert("1.0", text)
    assert tt.clean_text(box.get("1.0", "end-1c")) == text


def test_the_tools_tab_opens_one_text_tool(tk_root, tmp_path, monkeypatch):
    import offline_vf2_patcher_gui as gui
    import vf2_save_backup as sb
    monkeypatch.setattr(sb, "documents_folder", lambda: tmp_path / "Documents")
    app = gui.VF2PatcherGUI(tk_root)
    tool = app.game_font_text()
    assert tool.window.title() == "Game Font Text" and "game_font_text" in app.help_keys
    assert app.game_font_text() is tool                                 # one at a time
    assert [tool.picker.tab(t, "text") for t in tool.picker.tabs()] == ["Accents", "Any character"]
    assert list(tool.font_box.cget("values")) == [T.FONT_TITLES[n] for n in T.FONT_NAMES]
    assert tool.window.resizable() == (True, True)
    tool.show_help().destroy()
    tool.close()


def test_without_a_game_folder_the_window_says_so(tk_root, tmp_path):
    tool = tt.TextTool(tk_root, str(tmp_path))
    tool.quiet = True
    tool.set_text("Hi")
    assert tool.image is None
    assert "not a Virtual Families 2 game folder" in tool.folder_status_var.get()
    assert tool.status_var.get().startswith("2 characters; stored size 2 bytes.")
    assert tool.save_png(str(tmp_path / "x.png")) is None and "Type some text first" in tool.last_message
    tool.close()


@needs_fonts
def test_the_window_draws_picks_and_saves(tk_root, tmp_path):
    tool = tt.TextTool(tk_root, str(GAME_DIR))
    tool.quiet = True
    assert set(tool.fonts) == set(T.FONT_NAMES)
    tool.set_text("Hello")
    assert tool.image == T.render(*tool.current_font(), T.encode("Hello"), (255, 255, 255))
    assert tool.status_var.get() == ("5 characters; stored size 5 bytes. From the game font: 5. Patcher-made: 0. "
                                     "Missing (drawn as a box): 0.")
    # accents: a button inserts its letter at the cursor
    tool.language_box.set("Turkish")
    tool._fill_accents()
    tool.text.mark_set("insert", "end")
    tool.accent_buttons["ş"].invoke()
    assert tool.get_text() == "Helloş"
    assert "(patcher-made)" in tool.describe("ş")
    # any character: by code, then inserted
    tool.search_var.set("U+12000")
    assert tool.run_search()[0] == 0x12000
    assert tool.results.set(tool.results.selection()[0], "from").startswith("(patcher-made")
    assert tool.insert_found() == "\U00012000"
    tool.refresh()
    assert tool.get_text() == "Helloş\U00012000"
    assert "Patcher-made: 2." in tool.status_var.get()
    # font, colour, zoom, background
    tool.font_box.current(3)
    tool._font_changed()
    assert tool.image.height == T.load_font("Segoe36Bold").line_height
    tool.colour_var.set(tt.CUSTOM)
    tool._colour_picked(chosen=(255, 0, 0))
    reds = {bytes(tool.image.data[i:i + 3]) for i in range(0, len(tool.image.data), 4) if tool.image.data[i + 3]}
    assert reds and all(c[1] == 0 and c[2] == 0 for c in reds)
    for zoom in tt.ZOOMS:
        tool.zoom_var.set(zoom)
        for name, _colour in tt.BACKGROUNDS:
            tool.background_var.set(name)
            tool._show()
    assert tool.canvas.bbox("all") is not None
    # wrap
    tool.wrap_var.set("abc")
    tool.refresh()
    assert tool.image is None and "whole number of pixels" in tool.status_var.get()
    tool.wrap_var.set("0")
    # saving: the Picture Maker's sizes
    tool.size_var.set("2x")
    saved = tool.save_png(str(tmp_path / "text.png"))
    assert saved is not None
    base = tool.image.cropped(pi.MARGIN)
    assert _png_size(saved) == (2 * base.width, 2 * base.height)
    tool.size_var.set("custom")
    tool.width_var.set("x")
    assert tool.save_png(str(tmp_path / "bad.png")) is None and "whole number" in tool.last_message
    tool.close()
