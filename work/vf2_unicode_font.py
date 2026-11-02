"""Unicode Font (Tools tab -> "Unicode Font..."): pick the font Use Unicode Font (overrides in-game fonts) draws all of
Virtual Families 2's text with. As the Virtual Families 1 patcher's Unicode Font window (v1.7): the same layout,
labels and messages, with this game's folders.

Any font installed in Windows, or a .ttf / .otf / .ttc file. The choice is written into the modded game folder's
"Virtual Families 2 Patcher Files\\Unicode Font\\Unicode Font.ini", section [UnicodeFont]:

    Face=<the font's name, as Windows knows it>
    File=<a font file copied into "Virtual Families 2 Patcher Files\\Unicode Font", or empty>

(UTF-16 with a byte order mark, so any font name can be written), which the Unicode text DLL reads when the game
starts (runtime/native/b200unicode ReadSettings: a file is loaded for the game only, never installed in Windows).
No choice means Segoe UI. Each of the game's four fonts keeps its line height, baseline and weight, and its size is
fitted so a line is as wide as the game's own (vf2_game_text.fit_unicode_font); the preview here is drawn exactly as
the game will draw it (vf2_game_text.with_unicode_font, the same calls as the DLL). The patcher keeps the "Unicode
Font" folder when it patches the same modded folder again. Nothing but that ini and the copied font file is written;
the game's own files and the saves are not touched.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import vf2_game_text as T
import vf2_glyph_render as R

TITLE = "Unicode Font"
SECTION = "UnicodeFont"
PATCHER_FOLDER = "Virtual Families 2 Patcher Files"
FONT_FOLDER = "Unicode Font"
CHOICE_INI = "Unicode Font.ini"
SWITCH_INI = "vf2unicodefont.ini"          # Use Unicode Font's own ini (Mode=2), installed by the patch
DEFAULT_FACE = T.DEFAULT_UNICODE_FACE
SAMPLE = "The Smith Family – Zoë, İlkay, Łukasz 日本 \U0001f44d"
FONT_FILES = (("Font files", "*.ttf *.otf *.ttc"), ("All files", "*.*"))
FONT_SUFFIXES = (".ttf", ".otf", ".ttc")


class FontChoiceError(Exception):
    """A choice that cannot be written, with a reason a player can read."""


def font_folder(game_dir: Path) -> Path:
    return Path(game_dir) / PATCHER_FOLDER / FONT_FOLDER


def choice_path(game_dir: Path) -> Path:
    return font_folder(game_dir) / CHOICE_INI


def _ini_text(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def read_ini_section(data: bytes | None, section: str) -> dict[str, str]:
    """{key: value} of one [section] (keys as written; the first of a repeated key, as Windows reads it)."""
    out: dict[str, str] = {}
    if not data:
        return out
    inside = False
    for line in _ini_text(data).splitlines():
        s = line.strip()
        if s.startswith("[") and "]" in s:
            inside = s[1:s.index("]")].strip().casefold() == section.casefold()
            continue
        if inside and "=" in s and not s.startswith(";"):
            key, value = s.split("=", 1)
            out.setdefault(key.strip(), value.strip())
    return out


def read_choice(game_dir: Path) -> tuple[str, str]:
    """(face, file) from the folder's Unicode Font.ini; (Segoe UI, "") when nothing was chosen."""
    path = choice_path(game_dir)
    try:
        data = path.read_bytes() if path.is_file() else None
    except OSError:
        data = None
    values = read_ini_section(data, SECTION)
    return values.get("Face") or DEFAULT_FACE, values.get("File", "")


def is_on(game_dir: Path) -> bool:
    """Use Unicode Font is patched into this folder (its ini says Mode=2)."""
    path = Path(game_dir) / PATCHER_FOLDER / SWITCH_INI
    try:
        data = path.read_bytes() if path.is_file() else None
    except OSError:
        return False
    return read_ini_section(data, "Patches").get("Mode") == "2"


def choice_bytes(face: str, file_name: str) -> bytes:
    lines = [f"[{SECTION}]",
             "; Written by the Virtual Families 2 patcher's Unicode Font tool (Use Unicode Font).",
             f"Face={face}", f"File={file_name}"]
    return ("\r\n".join(lines) + "\r\n").encode("utf-16")       # with its byte order mark: any name reads back


def _atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def write_choice(game_dir: Path, face: str, font_file: Path | None = None) -> Path:
    """Write the choice into the modded folder; a font file is copied into its Unicode Font folder first."""
    game_dir = Path(game_dir)
    if not (game_dir / PATCHER_FOLDER).is_dir():
        raise FontChoiceError("This folder has not been patched yet: patch it first, then choose the font.")
    face = (face or "").strip()
    if not face:
        raise FontChoiceError("Choose a font.")
    if any(c in face for c in "\r\n\0"):
        raise FontChoiceError("This font's name cannot be written for the game; choose the font's file instead.")
    folder = font_folder(game_dir)
    file_name = ""
    if font_file is not None:
        font_file = Path(font_file)
        if font_file.suffix.lower() not in FONT_SUFFIXES:
            raise FontChoiceError("Choose a .ttf, .otf or .ttc font file.")
        family = R.font_file_family(font_file.read_bytes())
        if not family:
            raise FontChoiceError(f"{font_file.name} is not a font file Windows can use.")
        face = family
        folder.mkdir(parents=True, exist_ok=True)
        file_name = font_file.name
        if any(c in file_name for c in "\r\n\0;=[]"):
            file_name = f"font-{uuid.uuid4().hex[:8]}{font_file.suffix.lower()}"
        target = folder / file_name
        if not target.exists() or target.resolve() != font_file.resolve():
            temp = target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.tmp")
            shutil.copyfile(font_file, temp)
            os.replace(temp, target)
    folder.mkdir(parents=True, exist_ok=True)
    ini = choice_path(game_dir)
    _atomic_write(ini, choice_bytes(face, file_name))
    return ini


def installed_faces() -> list[str]:
    """Every font family Windows has, as Tk lists them (vertical "@" faces left out)."""
    import tkinter.font as tkfont
    names = {name for name in tkfont.families() if name and not name.startswith("@")}
    return sorted(names, key=str.casefold)


def preview(face: str, font_file: Path | None = None, text: str = SAMPLE):
    """[(label, picture)] for the game's four fonts drawn with the chosen font, as the Unicode text DLL will draw
    them (vf2_game_text.with_unicode_font)."""
    if font_file is not None:
        R.add_private_font(font_file)
    out = []
    for name in T.FONT_NAMES:
        f = T.with_unicode_font(T.load_font(name), face)
        out.append((f"{name}: {f.override[0]} at {f.override[1]} px", T.render(f, None, T.encode(text))))
    return out


# --------------------------------------------------------------------------- the window
def open_window(parent, *, game_folders=(), hold=None, show_help=None) -> "UnicodeFontWindow":
    """Open (or raise) the window over `parent` (the patcher window, or any Tk widget). One at a time."""
    existing = getattr(parent, "_unicode_font_window", None)
    if existing is not None:
        with contextlib.suppress(tk.TclError):
            if existing.window.winfo_exists():
                existing.window.deiconify()
                existing.window.lift()
                return existing
    window = UnicodeFontWindow(getattr(parent, "root", parent), game_folders=game_folders, hold=hold,
                               show_help=show_help)
    with contextlib.suppress(AttributeError, TypeError):
        parent._unicode_font_window = window
    return window


class UnicodeFontWindow:
    def __init__(self, parent: tk.Misc, *, game_folders=(), hold=None, show_help=None) -> None:
        self.window = tk.Toplevel(parent)
        self.window.title(TITLE)
        self.window.geometry("900x640")
        self.window.bind("<Escape>", lambda _e: self.close())
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.show_help = show_help
        self.game_folders = [Path(f) for f in game_folders if f]
        self.game_var = tk.StringVar(master=self.window)
        self.search_var = tk.StringVar(master=self.window)
        self.status_var = tk.StringVar(master=self.window)
        self.face = DEFAULT_FACE
        self.font_file: Path | None = None
        self.quiet = False
        self.last_message = ""
        self._photos = []
        self.faces = installed_faces()
        self._build()
        values = [str(g) for g in self.game_folders if (g / PATCHER_FOLDER).is_dir()]
        self.game_box.configure(values=values)
        if values:
            self.game_var.set(values[0])
        self.folder_changed()
        if hold is not None:
            hold(self.window)

    def _build(self) -> None:
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer)
        top.pack(fill="x")
        ttk.Label(top, text="Modded game folder:").grid(row=0, column=0, sticky="w")
        self.game_box = ttk.Combobox(top, textvariable=self.game_var, width=70)
        self.game_box.grid(row=0, column=1, sticky="w", padx=4)
        self.game_box.bind("<<ComboboxSelected>>", lambda _e: self.folder_changed())
        self.game_box.bind("<Return>", lambda _e: self.folder_changed())
        ttk.Button(top, text="Choose...", command=self.choose_folder).grid(row=0, column=2)
        ttk.Button(top, text="?", width=2, command=self._help).grid(row=0, column=3, padx=(12, 0))
        ttk.Label(outer, textvariable=self.status_var, foreground="#245a9a", wraplength=860,
                  justify="left").pack(anchor="w", pady=(6, 0))
        bottom = ttk.Frame(outer)                     # before the middle: it never gives way
        bottom.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(bottom, text="Save", command=self.save).pack(side="right")
        ttk.Button(bottom, text="Close", command=self.close).pack(side="right", padx=(0, 8))
        middle = ttk.Frame(outer)
        middle.pack(fill="both", expand=True, pady=(8, 0))
        left = ttk.Frame(middle)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Installed fonts (search):").pack(anchor="w")
        entry = ttk.Entry(left, textvariable=self.search_var, width=34)
        entry.pack(anchor="w", fill="x")
        self.search_var.trace_add("write", lambda *_a: self.fill_faces())
        ttk.Button(left, text="Segoe UI (the default)", command=lambda: self.set_face(DEFAULT_FACE)).pack(
            side="bottom", anchor="w", pady=(4, 0))
        ttk.Button(left, text="Choose a font file...", command=self.choose_file).pack(side="bottom", anchor="w",
                                                                                      pady=(6, 0))
        box = ttk.Frame(left)
        box.pack(fill="y", expand=True, pady=(4, 0))
        self.face_list = tk.Listbox(box, width=34, height=20, exportselection=False)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.face_list.yview)
        self.face_list.configure(yscrollcommand=sb.set)
        self.face_list.pack(side="left", fill="y")
        sb.pack(side="left", fill="y")
        self.face_list.bind("<<ListboxSelect>>", lambda _e: self.face_picked())
        right = ttk.Frame(middle)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ttk.Label(right, text="How the game's four fonts will look (drawn as the game will draw them):").pack(
            anchor="w")
        self.canvas = tk.Canvas(right, background="#28407a", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, pady=(4, 0))
        self.fill_faces()

    def fill_faces(self) -> None:
        term = self.search_var.get().strip().casefold()
        self.shown_faces = [f for f in self.faces if term in f.casefold()]
        self.face_list.delete(0, "end")
        for f in self.shown_faces:
            self.face_list.insert("end", f)

    def face_picked(self) -> None:
        picked = self.face_list.curselection()
        if picked:
            self.set_face(self.shown_faces[picked[0]])

    def set_face(self, face: str, font_file: Path | None = None) -> None:
        self.face = face
        self.font_file = font_file
        self.refresh()

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self.window, title="Choose the modded Virtual Families 2 folder")
        if folder:
            self.game_var.set(folder)
            self.folder_changed()

    def choose_file(self, path: str | None = None) -> None:
        if path is None:
            path = filedialog.askopenfilename(parent=self.window, title="Choose a font file", filetypes=FONT_FILES)
            if not path:
                return
        if Path(path).suffix.lower() not in FONT_SUFFIXES:
            self._message("error", "Choose a .ttf, .otf or .ttc font file.")
            return
        try:
            family = R.font_file_family(Path(path).read_bytes())
        except OSError as exc:
            self._message("error", str(exc))
            return
        if not family:
            self._message("error", f"{Path(path).name} is not a font file Windows can use.")
            return
        self.set_face(family, Path(path))

    def folder(self) -> Path | None:
        text = self.game_var.get().strip()
        return Path(text) if text else None

    def folder_changed(self) -> None:
        folder = self.folder()
        if folder is None:
            self.status_var.set("Choose the modded game folder (the one the patcher made).")
            self.set_face(DEFAULT_FACE)
            return
        face, file_name = read_choice(folder)
        font_file = font_folder(folder) / file_name if file_name else None
        on = is_on(folder)
        self.status_var.set(
            ("Use Unicode Font is on in this folder. " if on else
             "Use Unicode Font is off in this folder: tick it on the Patches tab and patch, or the game keeps its "
             "own letters. ") + f"Chosen now: {face}" + (f" (from {file_name})" if file_name else "") + ".")
        self.set_face(face, font_file if font_file and font_file.is_file() else None)

    def refresh(self) -> None:
        self.canvas.delete("all")
        self._photos = []
        try:
            rows = preview(self.face, self.font_file)
        except (OSError, ValueError, R.GlyphRenderError) as exc:
            self.status_var.set(str(exc))
            return
        y = 8
        for label, picture in rows:
            self.canvas.create_text(8, y, text=label, anchor="nw", fill="#ffffff")
            y += 18
            photo = picture.photo(tk, self.window)
            self._photos.append(photo)
            self.canvas.create_image(8, y, image=photo, anchor="nw")
            y += picture.height + 12

    def save(self) -> Path | None:
        folder = self.folder()
        if folder is None:
            self._message("error", "Choose the modded game folder first.")
            return None
        try:
            path = write_choice(folder, self.face, self.font_file)
        except (FontChoiceError, OSError) as exc:
            self._message("error", str(exc))
            return None
        self.status_var.set(f"Saved: the game uses {self.face} from its next start.")
        return path

    def _message(self, kind: str, text: str) -> None:
        self.last_message = text
        if self.quiet:
            return
        (messagebox.showerror if kind == "error" else messagebox.showinfo)(TITLE, text, parent=self.window)

    def _help(self) -> None:
        if self.show_help is not None:
            self.show_help()

    def close(self) -> None:
        with contextlib.suppress(tk.TclError):
            self.window.grab_release()
        with contextlib.suppress(tk.TclError):
            if self.window.winfo_exists():
                self.window.destroy()
