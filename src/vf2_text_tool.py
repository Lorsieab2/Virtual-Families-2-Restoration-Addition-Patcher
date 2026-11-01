"""Game Font Text (Tools tab -> "Game Font Text..."): type anything and see it drawn in Virtual Families 2's own
fonts, exactly as the game draws text, then save it as a PNG with a clear background.

* The text box takes any character Windows can type or paste: accents, other alphabets, symbols, emoji. A letter
  the game's font has is drawn from the game's own picture of it; one it lacks is a patcher-made letter in the
  font's style (src/vf2_glyph_maker.py), or drawn from a Windows font in the game font's style
  (src/vf2_glyph_render.py), or, failing both, the missing-letter box. The status line counts each kind.
* The text is turned into the form a save stores it in (vf2_game_text.encode) and drawn from that, with the
  game's own text functions (vf2_game_text.render: DrawString, and GetNextJustifiedLine when a wrap width is
  given), tinted the game's way (every sheet pixel AND the colour).
* Accents: buttons for the accented letters of the common Latin-script languages. Any character: find one by
  its Unicode name or code (U+2603, 2603, U+12000) and insert it.
* PNGs: as the Picture Maker saves them (vf2_picture_image.save_png): clear, cut to the drawn pixels with a small
  margin (or none), at the game's size, 2x or 4x (crisp) or any width and height (smooth).

The letters come from the game folder chosen in the window (its Images: Segoe24.png and the others). Nothing is
ever written but the PNGs the player saves.
"""
from __future__ import annotations

import contextlib
import unicodedata
from functools import lru_cache
from pathlib import Path
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

import vf2_game_text as T
import vf2_picture_image as pi

TITLE = "Game Font Text"
WIDTH, HEIGHT = 1180, 780
MIN_WIDTH, MIN_HEIGHT = 820, 560
DEBOUNCE_MS = 250
SEARCH_LIMIT = 200
ZOOMS = (1, 2, 4)
CHECKER = 8                         # the checkerboard's square, in screen pixels

# The colours offered. White draws the font's own sheet; every other colour is ANDed into each pixel as the game
# tints its text. Brown is the colour the game's own code gives text on one of its canvases
# (theGraphicsManager::GetTextColorForCanvas: 0xFF804C05, alpha FF, red 80h, green 4Ch, blue 05h).
COLOURS = (
    ("White", (255, 255, 255)),
    ("Black", (0, 0, 0)),
    ("Brown", (0x80, 0x4C, 0x05)),
)
CUSTOM = "Custom..."
BACKGROUNDS = (("Clear (checkerboard)", None), ("Dark", "#202020"), ("Light", "#f4f4f4"))


# ====================================================================== accents


def _vietnamese() -> str:
    """Every Vietnamese letter with a mark: the vowels with each tone, and d with stroke; lower case, then
    capitals."""
    vowels = "aăâeêioôơuưy"
    tones = ("̀", "́", "̉", "̃", "̣")     # huyền, sắc, hỏi, ngã, nặng
    lower = "ăâêôơưđ" + "".join(unicodedata.normalize("NFC", v + t) for v in vowels for t in tones)
    return lower + lower.upper()


def _both(lower: str) -> str:
    return lower + lower.upper()


ACCENTS = {
    "French": _both("àâæçéèêëîïôœùûüÿ"),
    "German": "äöüßÄÖÜẞ",
    "Spanish": _both("áéíóúüñ") + "¿¡",
    "Portuguese": _both("áâãàçéêíóôõú"),
    "Italian": _both("àèéìíîòóùú"),
    "Turkish": "çÇğĞıIiİöÖşŞüÜ",
    "Polish": _both("ąćęłńóśźż"),
    "Czech": _both("áčďéěíňóřšťúůýž"),
    "Hungarian": _both("áéíóöőúüű"),
    "Romanian": "ăĂâÂîÎșȘțȚ",
    "Vietnamese": _vietnamese(),
    "Nordic (Danish, Norwegian, Swedish, Finnish, Icelandic)": _both("åæøäöáðéíóúýþ"),
}


# ====================================================================== the text


def clean_text(text: str) -> str:
    """The text as Python characters: a pair of UTF-16 halves Tk may hand back is joined, and a lone half (left by
    deleting half an emoji) is dropped."""
    if not any(0xD800 <= ord(c) <= 0xDFFF for c in text):
        return text
    return text.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "ignore")


def stored(text: str) -> bytes:
    """The bytes the game would store the text as (the one text rule): what is drawn and what is counted."""
    return T.encode(clean_text(text))


def render_text(font: T.GameFont, sheet, text: str, rgb=(255, 255, 255), wrap_width: int = 0) -> pi.Image:
    """The text as the game draws it, in `font`, tinted `rgb`, on a clear picture; wrapped at `wrap_width`
    pixels as the game's dialogs wrap (0: each line break starts a new line). Drawn from the stored form."""
    return T.render(font, sheet, stored(text), tuple(rgb), max_width=max(0, int(wrap_width or 0)))


def unit_label(font: T.GameFont, unit: T.Unit) -> str:
    return T.glyph_label(font.glyph(unit))


def char_label(font: T.GameFont, ch: str) -> str:
    """Where `ch` (one character) is drawn from in `font`: "(game font)", "(patcher-made)", ... ."""
    units = T.units(T.encode(ch))
    if not units:
        return ""
    return unit_label(font, units[0])


def counts(font: T.GameFont | None, text: str) -> dict:
    """The status line's numbers: characters (as the game's character limit counts them), the stored size, and
    how many characters are drawn from the game font, made by the patcher, or missing (a box)."""
    text = clean_text(text)
    raw = T.encode(text)
    out = {"characters": T.length(text), "bytes": len(raw), "game": 0, "patcher": 0, "missing": 0}
    if font is None:
        return out
    for u in T.units(raw):
        if u.text in ("\n", "\r", "\r\n"):
            continue
        kind = font.glyph(u).kind
        out["game" if kind == "game" else "missing" if kind == "box" else "patcher"] += 1
    return out


def status_text(c: dict, fonts_loaded: bool = True) -> str:
    words = (f"{c['characters']} character{'' if c['characters'] == 1 else 's'}; "
             f"stored size {c['bytes']} byte{'' if c['bytes'] == 1 else 's'}.")
    if fonts_loaded:
        words += (f" From the game font: {c['game']}. Patcher-made: {c['patcher']}. "
                  f"Missing (drawn as a box): {c['missing']}.")
    return words


# ====================================================================== any character


def parse_code(query: str) -> int | None:
    """A code point from "U+2603", "u+12000", "0x2603" or "2603" (hex with at least one digit, so a word such as
    "face" is a name, not a code); None when it is not one, or not a character (out of range, or half of a
    UTF-16 pair)."""
    q = query.strip().replace(" ", "")
    if not q:
        return None
    low = q.lower()
    if low.startswith(("u+", "0x")):
        digits = q[2:]
    elif any(c.isdigit() for c in q):
        digits = q
    else:
        return None
    if not digits or len(digits) > 6 or any(c not in "0123456789abcdefABCDEF" for c in digits):
        return None
    cp = int(digits, 16)
    if cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
        return None
    return cp


@lru_cache(maxsize=1)
def _names() -> tuple:
    """(code point, name) of every named character (built once, on the first search)."""
    out = []
    for cp in range(0x20, 0x110000):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        name = unicodedata.name(chr(cp), None)
        if name:
            out.append((cp, name))
    return tuple(out)


def char_name(cp: int) -> str:
    name = unicodedata.name(chr(cp), None)
    if name:
        return name.capitalize()
    cat = unicodedata.category(chr(cp))
    return {"Cc": "Control character", "Co": "Private use character", "Cn": "Not a character yet"}.get(
        cat, "Character without a name")


def search(query: str, limit: int = SEARCH_LIMIT) -> list[int]:
    """Code points for a search: the code first (when the query is one), then every character whose Unicode name
    holds all the words of the query (case does not matter), in code order; a single typed or pasted character
    finds itself."""
    query = clean_text(query).strip()
    if not query:
        return []
    found: list[int] = []
    cp = parse_code(query)
    if cp is not None:
        found.append(cp)
    single = len(query) == 1
    if single and ord(query) not in found:
        found.append(ord(query))
    words = query.upper().split()
    if words and not (single and ord(query) > 0x7F):        # a pasted symbol finds itself, not names
        for code, name in _names():
            if len(found) >= limit:
                break
            if code not in found and all(w in name for w in words):
                found.append(code)
    return found[:limit]


def insertable(cp: int) -> bool:
    """A character that can go into the text: not half of a UTF-16 pair, not a control character other than the
    tab, and given a meaning by Unicode (an unassigned code has none)."""
    if cp > 0x10FFFF or 0xD800 <= cp <= 0xDFFF:
        return False
    cat = unicodedata.category(chr(cp))
    return cat != "Cn" and (cat != "Cc" or cp == 0x09)


def code_text(cp: int) -> str:
    return f"U+{cp:04X}"


# ====================================================================== game folder and export


def images_folder(game_folder: str | Path | None) -> Path | None:
    """The game folder's Images when it holds the four font pictures, else None."""
    text = str(game_folder or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.name.lower() != "images":
        path = path / "Images"
    try:
        if all((path / f"{name}.png").is_file() for name in T.FONT_NAMES):
            return path
    except OSError:
        return None
    return None


def export_options(size: str, width: str = "", height: str = "", margin: bool = True) -> dict:
    """The Picture Maker's own export choices (vf2_picture_maker.export_options), so both tools save alike."""
    import vf2_picture_maker
    return vf2_picture_maker.export_options(size, width, height, margin)


def file_name(text: str, font_name: str) -> str:
    """The suggested PNG name: the first line of the text (40 characters at most) and the font."""
    first = next((line.strip() for line in clean_text(text).splitlines() if line.strip()), "")
    first = "".join(T.clusters(first)[:40]).strip()
    return pi.safe_file_name(f"{first or 'Game font text'} - {font_name}")


# ====================================================================== the window


def open_text_tool(app, game_folder: str = "") -> "TextTool":
    """Open (or raise) the Game Font Text window over the patcher window `app` (a VF2PatcherGUI)."""
    existing = getattr(app, "_text_tool", None)
    if existing is not None:
        with contextlib.suppress(tk.TclError):
            if existing.window.winfo_exists():
                existing.window.deiconify()
                existing.window.lift()
                return existing
    tool = TextTool(getattr(app, "root", app), game_folder)
    hold = getattr(app, "_hold", None)
    if hold is not None:
        hold(tool.window, tool.text)
    app._text_tool = tool
    return tool


class TextTool:
    def __init__(self, master: tk.Misc, game_folder: str = "") -> None:
        self.window = tk.Toplevel(master)
        self.window.title(TITLE)
        with contextlib.suppress(tk.TclError):
            self.window.transient(master)
        screen_w, screen_h = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        width, height = min(WIDTH, screen_w - 60), min(HEIGHT, screen_h - 110)
        self.window.geometry(f"{width}x{height}")
        self.window.minsize(min(MIN_WIDTH, width), min(MIN_HEIGHT, height))
        self.window.resizable(True, True)
        self.window.bind("<Escape>", lambda _e: self.close())
        v = self.window
        self.game_var = tk.StringVar(master=v, value=game_folder)
        self.font_var = tk.StringVar(master=v)
        self.colour_var = tk.StringVar(master=v, value=COLOURS[0][0])
        self.wrap_var = tk.StringVar(master=v, value="0")
        self.zoom_var = tk.IntVar(master=v, value=2)
        self.background_var = tk.StringVar(master=v, value=BACKGROUNDS[0][0])
        self.size_var = tk.StringVar(master=v, value="1x")
        self.width_var = tk.StringVar(master=v)
        self.height_var = tk.StringVar(master=v)
        self.margin_var = tk.BooleanVar(master=v, value=True)
        self.search_var = tk.StringVar(master=v)
        self.language_var = tk.StringVar(master=v)
        self.status_var = tk.StringVar(master=v)
        self.folder_status_var = tk.StringVar(master=v)
        self.hover_var = tk.StringVar(master=v)
        self.custom_rgb = (255, 255, 255)
        self.fonts: dict = {}
        self.image: pi.Image | None = None           # the picture shown, at the game's size, clear
        self.found: list[int] = []
        self.quiet = False                            # tests: messages are kept, not shown
        self.last_message = ""
        self._pending = None
        self._photos: list = []
        self._build()
        self.font_box.current(0)
        self.game_var.trace_add("write", lambda *_a: self._game_changed())
        self._game_changed()

    # ---- layout
    def _build(self) -> None:
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)

        game = ttk.Frame(outer)
        game.pack(fill="x")
        ttk.Label(game, text="Game folder (for the letters):").pack(side="left")
        ttk.Entry(game, textvariable=self.game_var, width=60).pack(side="left", padx=(4, 6), fill="x", expand=True)
        ttk.Button(game, text="Choose...", command=self.choose_game).pack(side="left")
        ttk.Button(game, text="?", width=2, command=self.show_help).pack(side="left", padx=(12, 0))
        self.folder_status = ttk.Label(outer, textvariable=self.folder_status_var, foreground="#245a9a",
                                       wraplength=900, justify="left")
        self.folder_status.pack(anchor="w", pady=(6, 0))
        outer.bind("<Configure>", lambda e: self.folder_status.configure(wraplength=max(300, e.width - 30)))

        look = ttk.LabelFrame(outer, text="Look", padding=(10, 4))
        look.pack(fill="x", pady=(6, 0))
        ttk.Label(look, text="Font:").pack(side="left")
        self.font_box = ttk.Combobox(look, textvariable=self.font_var, state="readonly", width=34,
                                     values=[T.FONT_TITLES[n] for n in T.FONT_NAMES])
        self.font_box.pack(side="left", padx=(4, 14))
        self.font_box.bind("<<ComboboxSelected>>", lambda _e: self._font_changed())
        ttk.Label(look, text="Colour:").pack(side="left")
        self.colour_box = ttk.Combobox(look, textvariable=self.colour_var, state="readonly", width=12,
                                       values=[name for name, _rgb in COLOURS] + [CUSTOM])
        self.colour_box.pack(side="left", padx=(4, 4))
        self.colour_box.bind("<<ComboboxSelected>>", lambda _e: self._colour_picked())
        self.swatch = tk.Label(look, width=2, relief="solid", borderwidth=1, background="#ffffff")
        self.swatch.pack(side="left", padx=(0, 14))
        ttk.Label(look, text="Wrap at:").pack(side="left")
        wrap = ttk.Spinbox(look, textvariable=self.wrap_var, from_=0, to=4000, increment=10, width=6,
                           command=self.schedule)
        wrap.pack(side="left", padx=(4, 2))
        wrap.bind("<KeyRelease>", lambda _e: self.schedule())
        ttk.Label(look, text="pixels (0: no wrap)").pack(side="left")

        bottom = ttk.Frame(outer)
        bottom.pack(side="bottom", fill="x", pady=(8, 0))
        save = ttk.LabelFrame(bottom, text="Save PNG", padding=(10, 4))
        save.pack(side="left", fill="x", expand=True)
        ttk.Label(save, text="PNG size:").pack(side="left")
        for label, value in (("Game size", "1x"), ("2x", "2x"), ("4x", "4x"), ("Custom:", "custom")):
            ttk.Radiobutton(save, text=label, value=value, variable=self.size_var).pack(side="left", padx=(4, 0))
        ttk.Entry(save, textvariable=self.width_var, width=6).pack(side="left", padx=(2, 0))
        ttk.Label(save, text="x").pack(side="left", padx=2)
        ttk.Entry(save, textvariable=self.height_var, width=6).pack(side="left")
        ttk.Label(save, text="px").pack(side="left", padx=(2, 12))
        ttk.Checkbutton(save, text="Small margin", variable=self.margin_var).pack(side="left")
        ttk.Button(save, text="Save PNG...", command=self.save_png).pack(side="left", padx=(14, 0))
        ttk.Button(bottom, text="Close", command=self.close).pack(side="right", anchor="s")

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(8, 0))
        left = ttk.Frame(body)
        right = ttk.Frame(body, padding=(10, 0, 0, 0))
        body.add(left, weight=3)
        body.add(right, weight=2)

        ttk.Label(left, text="Your text (type or paste anything; line breaks start new lines):").pack(anchor="w")
        box = ttk.Frame(left)
        box.pack(fill="x")
        self.text = tk.Text(box, height=6, wrap="word", undo=True, font=("Segoe UI", 11))
        bar = ttk.Scrollbar(box, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="x", expand=True)
        self.text.bind("<<Modified>>", self._modified)

        shown = ttk.Frame(left)
        shown.pack(fill="x", pady=(8, 2))
        ttk.Label(shown, text="Preview:").pack(side="left")
        for z in ZOOMS:
            ttk.Radiobutton(shown, text=f"{z}x", value=z, variable=self.zoom_var,
                            command=self._show).pack(side="left", padx=(6, 0))
        ttk.Label(shown, text="Behind it:").pack(side="left", padx=(16, 0))
        back = ttk.Combobox(shown, textvariable=self.background_var, state="readonly", width=20,
                            values=[name for name, _c in BACKGROUNDS])
        back.pack(side="left", padx=(4, 0))
        back.bind("<<ComboboxSelected>>", lambda _e: self._show())
        self.status = ttk.Label(left, textvariable=self.status_var, wraplength=600, justify="left")
        self.status.pack(side="bottom", anchor="w", pady=(6, 0))     # before the preview: it never gives way
        holder = ttk.Frame(left)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, highlightthickness=1, highlightbackground="#c0c0c0", background="#808080")
        ybar = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        xbar = ttk.Scrollbar(holder, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        ybar.pack(side="right", fill="y")
        xbar.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        left.bind("<Configure>", lambda e: self.status.configure(wraplength=max(300, e.width - 10)))

        self.picker = ttk.Notebook(right)
        self.picker.pack(fill="both", expand=True)
        self._build_accents()
        self._build_search()

    def _build_accents(self) -> None:
        tab = ttk.Frame(self.picker, padding=8)
        self.picker.add(tab, text="Accents")
        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Label(row, text="Language:").pack(side="left")
        languages = list(ACCENTS)
        self.language_box = ttk.Combobox(row, textvariable=self.language_var, state="readonly", width=40,
                                         values=languages)
        self.language_box.pack(side="left", padx=(4, 0))
        self.language_box.current(0)
        self.language_box.bind("<<ComboboxSelected>>", lambda _e: self._fill_accents())
        ttk.Label(tab, textvariable=self.hover_var, wraplength=360, justify="left", foreground="#555555").pack(
            anchor="w", side="bottom", pady=(6, 0))
        holder = ttk.Frame(tab)                          # the letters scroll (Vietnamese has 134)
        holder.pack(fill="both", expand=True, pady=(8, 0))
        canvas = tk.Canvas(holder, highlightthickness=0, borderwidth=0,
                           background=ttk.Style(self.window).lookup("TFrame", "background") or "#f0f0f0")
        bar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.accent_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=self.accent_frame, anchor="nw")
        self.accent_frame.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.accent_canvas = canvas
        canvas.bind("<MouseWheel>", self._wheel_accents)
        self.accent_buttons: dict[str, ttk.Button] = {}

    def _wheel_accents(self, event) -> str:
        self.accent_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _fill_accents(self) -> None:
        for child in self.accent_frame.winfo_children():
            child.destroy()
        self.accent_buttons = {}
        letters = ACCENTS.get(self.language_var.get(), "")
        per_row = 8
        for i, ch in enumerate(letters):
            button = ttk.Button(self.accent_frame, text=ch, width=3, command=lambda c=ch: self.insert(c))
            button.grid(row=i // per_row, column=i % per_row, padx=1, pady=1)
            button.bind("<Enter>", lambda _e, c=ch: self.hover_var.set(self.describe(c)))
            button.bind("<FocusIn>", lambda _e, c=ch: self.hover_var.set(self.describe(c)))
            button.bind("<MouseWheel>", self._wheel_accents)
            self.accent_buttons[ch] = button
        self.accent_canvas.yview_moveto(0)
        self.hover_var.set("Point at a letter to see its name and where its picture comes from.")

    def _build_search(self) -> None:
        tab = ttk.Frame(self.picker, padding=8)
        self.picker.add(tab, text="Any character")
        ttk.Label(tab, text="A name (snowman, heart, smiling face) or a code (U+2603):", wraplength=360,
                  justify="left").pack(anchor="w")
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=(4, 6))
        entry = ttk.Entry(row, textvariable=self.search_var, width=18)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _e: self.run_search())
        ttk.Button(row, text="Find", command=self.run_search).pack(side="left", padx=(6, 0))
        under = ttk.Frame(tab)
        under.pack(side="bottom", fill="x", pady=(4, 0))
        ttk.Button(under, text="Insert", command=self.insert_found).pack(side="left", anchor="n")
        self.search_note = ttk.Label(under, text="", wraplength=280, justify="left", foreground="#555555")
        self.search_note.pack(side="left", padx=(8, 0), fill="x")
        holder = ttk.Frame(tab)
        holder.pack(fill="both", expand=True)
        self.style_name = "GameFontText.Treeview"
        self.results = ttk.Treeview(holder, columns=("code", "from", "name"), show="tree headings",
                                    selectmode="browse", style=self.style_name)
        self.results.heading("#0", text="Drawn")
        self.results.heading("code", text="Code")
        self.results.heading("name", text="Name")
        self.results.heading("from", text="Letter picture")
        self.results.column("#0", width=70, stretch=False)
        self.results.column("code", width=80, stretch=False)
        self.results.column("name", width=240)
        self.results.column("from", width=160, stretch=False)
        ybar = ttk.Scrollbar(holder, orient="vertical", command=self.results.yview)
        xbar = ttk.Scrollbar(holder, orient="horizontal", command=self.results.xview)
        self.results.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        ybar.pack(side="right", fill="y")
        xbar.pack(side="bottom", fill="x")
        self.results.pack(side="left", fill="both", expand=True)
        self.results.bind("<Double-1>", lambda _e: self.insert_found())
        self.results.bind("<Return>", lambda _e: self.insert_found())

    def close(self) -> None:
        if self._pending is not None:
            with contextlib.suppress(tk.TclError):
                self.window.after_cancel(self._pending)
            self._pending = None
        with contextlib.suppress(tk.TclError):
            self.window.grab_release()
        with contextlib.suppress(tk.TclError):
            if self.window.winfo_exists():
                self.window.destroy()

    def show_help(self) -> tk.Toplevel:
        import vf2_how_to_use
        guide = vf2_how_to_use.guide("game_font_text")
        window = tk.Toplevel(self.window)
        window.title(f"How to use: {guide.title}")
        window.transient(self.window)
        frame = ttk.Frame(window, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=guide.title, font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))
        for line in guide.lines:
            ttk.Label(frame, text=line, wraplength=480, justify="left").pack(anchor="w", pady=(0, 6))
        ttk.Button(frame, text="Close", command=window.destroy).pack(anchor="e", pady=(8, 0))
        window.bind("<Escape>", lambda _e: window.destroy())
        return window

    # ---- the game folder and the fonts
    def choose_game(self, chosen: str | None = None) -> None:
        if chosen is None:
            chosen = filedialog.askdirectory(parent=self.window, title="The game's folder (the one with Images in it)")
        if chosen:
            self.game_var.set(chosen)

    def _game_changed(self) -> None:
        images = images_folder(self.game_var.get())
        self.fonts = {}
        if images is None:
            text = self.game_var.get().strip()
            self.folder_status_var.set(
                "Choose the game folder: the letters are drawn from its Images." if not text else
                f"{text} is not a Virtual Families 2 game folder the letters can come from (its Images needs "
                "Segoe24.png, Segoe24Bold.png, Segoe32Bold.png and Segoe36Bold.png).")
        else:
            try:
                import vf2_glyph_maker
                self.fonts = vf2_glyph_maker.load_fonts(images)
            except (OSError, pi.PictureError, KeyError, ValueError, IndexError) as exc:
                self.fonts = {}
                self.folder_status_var.set(f"The game's letters could not be read from {images}: {exc}")
            else:
                self.folder_status_var.set(f"Drawn from the game's own letters in {images}.")
        self._font_changed()

    def font_name(self) -> str:
        index = self.font_box.current()
        return T.FONT_NAMES[index] if 0 <= index < len(T.FONT_NAMES) else T.FONT_NAMES[0]

    def current_font(self):
        """(GameFont, sheet) of the chosen font, or (None, None) without a game folder."""
        return self.fonts.get(self.font_name(), (None, None))

    def _font_changed(self) -> None:
        font, _sheet = self.current_font()
        height = (font.line_height if font is not None else 19) + 6
        with contextlib.suppress(tk.TclError):
            ttk.Style(self.window).configure(self.style_name, rowheight=max(22, height))
        self._fill_accents()
        if self.found:
            self._fill_results()
        self.refresh()

    # ---- colour
    def colour(self) -> tuple:
        name = self.colour_var.get()
        for label, rgb in COLOURS:
            if label == name:
                return rgb
        return self.custom_rgb

    def _colour_picked(self, chosen=None) -> None:
        if self.colour_var.get() == CUSTOM:
            if chosen is None:
                with contextlib.suppress(tk.TclError):
                    picked = colorchooser.askcolor(color="#%02x%02x%02x" % self.custom_rgb, parent=self.window,
                                                   title="Text colour")
                    chosen = picked[0] if picked else None
            if chosen:
                self.custom_rgb = tuple(int(round(c)) for c in chosen)[:3]
        self.swatch.configure(background="#%02x%02x%02x" % self.colour())
        self.refresh()

    # ---- the text
    def get_text(self) -> str:
        return clean_text(self.text.get("1.0", "end-1c"))

    def set_text(self, text: str) -> None:
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.refresh()

    def insert(self, ch: str) -> None:
        self.text.insert("insert", ch)
        with contextlib.suppress(tk.TclError):
            self.text.focus_set()
        self.schedule()

    def wrap_width(self) -> int | None:
        """The wrap width in pixels (0: none), or None when the box holds something else."""
        text = self.wrap_var.get().strip()
        if not text:
            return 0
        return int(text) if text.isdigit() else None

    def _modified(self, _event=None) -> None:
        with contextlib.suppress(tk.TclError):
            self.text.edit_modified(False)
        self.schedule()

    def schedule(self) -> None:
        """Redraw a moment after the last change (typing stays smooth)."""
        if self._pending is not None:
            with contextlib.suppress(tk.TclError):
                self.window.after_cancel(self._pending)
        with contextlib.suppress(tk.TclError):
            self._pending = self.window.after(DEBOUNCE_MS, self.refresh)

    def refresh(self) -> None:
        """Draw the text again and say what it holds."""
        self._pending = None
        text = self.get_text()
        font, sheet = self.current_font()
        c = counts(font, text)
        said = status_text(c, font is not None)
        wrap = self.wrap_width()
        self.image = None
        if font is None:
            said += " Choose the game folder to see the text drawn."
        elif wrap is None:
            said += " The wrap width is a whole number of pixels (0: no wrap)."
        elif text:
            try:
                self.image = render_text(font, sheet, text, self.colour(), wrap)
            except (OSError, pi.PictureError, ValueError) as exc:
                said += f" This cannot be drawn: {exc}"
        self.status_var.set(said)
        self._show()

    def _show(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        self._photos = []
        background = dict(BACKGROUNDS).get(self.background_var.get())
        canvas.configure(background=background or "#808080")
        if self.image is None:
            canvas.configure(scrollregion=(0, 0, 1, 1))
            return
        zoom = int(self.zoom_var.get() or 1)
        w, h = self.image.width * zoom, self.image.height * zoom
        pad = 8
        if background is None:
            checker = self._checker(w + 2 * pad, h + 2 * pad)
            canvas.create_image(0, 0, image=checker, anchor="nw")
            self._photos.append(checker)
        photo = self.image.photo(tk, self.window)
        if zoom > 1:
            photo = photo.zoom(zoom)
        canvas.create_image(pad, pad, image=photo, anchor="nw")
        self._photos.append(photo)
        canvas.configure(scrollregion=(0, 0, w + 2 * pad, h + 2 * pad))

    def _checker(self, width: int, height: int):
        """A grey checkerboard (the usual sign of a clear background) of width x height, mid greys so white, black
        and coloured text all show on it."""
        tile = tk.PhotoImage(master=self.window, width=2 * CHECKER, height=2 * CHECKER)
        tile.put("#5c5c5c", to=(0, 0, 2 * CHECKER, 2 * CHECKER))
        tile.put("#7c7c7c", to=(0, 0, CHECKER, CHECKER))
        tile.put("#7c7c7c", to=(CHECKER, CHECKER, 2 * CHECKER, 2 * CHECKER))
        board = tk.PhotoImage(master=self.window, width=max(1, width), height=max(1, height))
        self.window.tk.call(board, "copy", tile, "-to", 0, 0, max(1, width), max(1, height))
        self._photos.append(tile)
        return board

    # ---- the character picker
    def describe(self, ch: str) -> str:
        cp = ord(ch[0]) if len(ch) == 1 else None
        name = char_name(cp) if cp is not None else " + ".join(char_name(ord(c)) for c in ch)
        font, _sheet = self.current_font()
        label = f" {char_label(font, ch)}" if font is not None else ""
        code = code_text(cp) if cp is not None else " ".join(code_text(ord(c)) for c in ch)
        return f"{ch}  {code}  {name}{label}"

    def run_search(self) -> list[int]:
        query = self.search_var.get()
        self.found = [cp for cp in search(query) if insertable(cp)]
        self._fill_results()
        if not query.strip():
            self.search_note.configure(text="Type a name or a code first.")
        elif not self.found:
            self.search_note.configure(text="Nothing found. Try one word of the name, or a code such as U+2603.")
        else:
            more = " (the first ones only: add a word to find fewer)" if len(self.found) >= SEARCH_LIMIT else ""
            self.search_note.configure(text=f"{len(self.found)} found{more}. Double-click one, or pick it and "
                                            "click Insert.")
        return self.found

    def _fill_results(self) -> None:
        tree = self.results
        tree.delete(*tree.get_children())
        self._result_photos = []
        font, sheet = self.current_font()
        for cp in self.found:
            ch = chr(cp)
            label = char_label(font, ch) if font is not None else ""
            photo = ""
            if font is not None:
                with contextlib.suppress(OSError, pi.PictureError, ValueError, tk.TclError):
                    picture = T.render(font, sheet, T.encode(ch), (0, 0, 0))
                    photo = picture.photo(tk, self.window, max_side=64)
                    self._result_photos.append(photo)
            tree.insert("", "end", iid=str(cp), text=f" {ch}" if not photo else "", image=photo,
                        values=(code_text(cp), label, char_name(cp)))
        children = tree.get_children()
        if children:
            tree.selection_set(children[0])
            tree.see(children[0])

    def insert_found(self) -> str | None:
        selection = self.results.selection()
        if not selection:
            self._tell("info", "Find a character and pick it first.")
            return None
        ch = chr(int(selection[0]))
        self.insert(ch)
        return ch

    # ---- saving
    def export_choice(self) -> dict:
        return export_options(self.size_var.get(), self.width_var.get(), self.height_var.get(), self.margin_var.get())

    def save_png(self, path: str | None = None) -> Path | None:
        self.refresh()                                   # what is saved is always the text and choices shown now
        if self.image is None or not self.get_text().strip():
            self._tell("info", "Type some text first (and choose the game folder, so it can be drawn).")
            return None
        try:
            options = self.export_choice()
        except pi.PictureError as exc:
            self._tell("warning", str(exc))
            return None
        if path is None:
            path = filedialog.asksaveasfilename(parent=self.window, title="Save PNG", defaultextension=".png",
                                                initialfile=file_name(self.get_text(), self.font_name()) + ".png",
                                                filetypes=[("PNG picture", "*.png")])
        if not path:
            return None
        try:
            return pi.save_png(self.image, path, **options)
        except (OSError, pi.PictureError) as exc:
            self._tell("warning", f"The picture could not be saved: {exc}")
            return None

    def _tell(self, kind: str, text: str) -> None:
        self.last_message = text
        if not self.quiet:
            (messagebox.showwarning if kind == "warning" else messagebox.showinfo)(TITLE, text, parent=self.window)
