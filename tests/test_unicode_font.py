"""Use Unicode Font (overrides in-game fonts): the font picker and the drawing, as VF1 v1.7's (its PR #55).

* the size: each game font's size in the chosen face is fitted so a reference line is as wide as the game font draws
  it (60% to 130% of the fitted Segoe UI size), every face on the game font's baseline; every letter, ASCII too, is
  drawn by Windows; a face Windows lacks keeps the size;
* the tool (src/vf2_unicode_font.py): the choice is written into the modded folder's
  "Virtual Families 2 Patcher Files\\Unicode Font\\Unicode Font.ini" (UTF-16, so any font name, read back by Windows'
  own GetPrivateProfileStringW); a font file is copied beside it and named by its family; refused before the folder
  is patched; the window lists the installed fonts, previews the four game fonts and saves;
* Game Font Text previews Use Unicode Font;
* the patcher keeps the "Unicode Font" folder when it refreshes the same modded folder;
* the DLL (Visual Studio + an executable built from this repo): the DLL reads the choice the tool wrote, loads a font
  file for the game only, and its DrawString and GetWidth with real GDI under unicorn give every place, width and
  pixel the patcher's preview gives, in all four fonts, for Segoe UI, Comic Sans MS and Arial loaded from a file.
"""
from __future__ import annotations

import ctypes
import os
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(ROOT / "tests"))

import vf2_game_text as T  # noqa: E402
import vf2_glyph_render as R  # noqa: E402
import vf2_unicode_font as uf  # noqa: E402

WINDOWS = R.available()
needs_windows = pytest.mark.skipif(not WINDOWS, reason="needs Windows' GDI")
FONTS_DIR = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"
ARIAL = FONTS_DIR / "arial.ttf"


# --------------------------------------------------------------------------- the size and the drawing
@needs_windows
def test_the_size_is_fitted_to_the_games_width():
    for name in T.FONT_NAMES:
        f = T.load_font(name)
        px = f.gdi["px"]
        game = T.get_width(f, T.FIT_REFERENCE.encode())
        for face in ("Segoe UI", "Arial", "Comic Sans MS", "Courier New"):
            o = T.with_unicode_font(f, face)
            chosen, em, base = o.override
            assert chosen == face and px * 6 // 10 <= em <= px * 13 // 10
            assert base == f.gdi["top"] + R.ascent("Segoe UI", px, f.gdi["weight"])
            if px * 6 // 10 < em < px * 13 // 10:
                drawn = R.extent(face, em, f.gdi["weight"], T.FIT_REFERENCE)
                assert abs(drawn - game) <= max(8, game // 15), (name, face, drawn, game)
            kinds = {o.glyph(u).kind for u in T.units(T.encode("Hello Zo\u00eb \u65e5"))}
            assert kinds == {"windows"}                               # the game's own letters too
            assert o.glyph(T.units(b"H")[0]).source == face
        assert T.with_unicode_font(f, "No Such Font Anywhere").override[1] == px
        assert T.with_unicode_font(f, "").override[0] == "Segoe UI"
        # the original font object is untouched
        assert f.override is None and T.load_font(name).glyph(T.units(b"H")[0]).kind == "game"


@needs_windows
def test_a_letter_the_face_lacks_comes_from_the_chain():
    o = T.with_unicode_font(T.load_font("Segoe24"), "Courier New")
    assert o.glyph(T.units(T.encode("\u65e5"))[0]).source != "Courier New"
    assert o.glyph(T.units(T.encode("A"))[0]).source == "Courier New"
    assert T.glyph_label(o.glyph(T.units(b"A")[0])) == "(drawn by Windows: Courier New)"


def test_the_family_name_of_a_font_file():
    assert R.font_file_family(b"not a font") is None
    assert R.font_file_family(b"") is None
    if ARIAL.is_file():
        assert R.font_file_family(ARIAL.read_bytes()) == "Arial"


# --------------------------------------------------------------------------- the tool
def _modded(tmp_path: Path, on: bool = True) -> Path:
    folder = tmp_path / "VF2-Modded"
    (folder / uf.PATCHER_FOLDER).mkdir(parents=True)
    if on:
        (folder / uf.PATCHER_FOLDER / uf.SWITCH_INI).write_bytes(b"[Patches]\r\nMode=2\r\n[Font]\r\nFace=Segoe UI\r\n")
    return folder


def test_the_choice_is_written_beside_the_patcher_files(tmp_path):
    with pytest.raises(uf.FontChoiceError, match="not been patched yet"):
        uf.write_choice(tmp_path, "Arial")
    folder = _modded(tmp_path)
    assert uf.read_choice(folder) == ("Segoe UI", "") and uf.is_on(folder)
    with pytest.raises(uf.FontChoiceError, match="Choose a font"):
        uf.write_choice(folder, "  ")
    ini = uf.write_choice(folder, "Arial")
    assert ini == folder / uf.PATCHER_FOLDER / "Unicode Font" / "Unicode Font.ini"
    assert ini.read_bytes()[:2] == b"\xff\xfe"
    assert uf.read_choice(folder) == ("Arial", "")
    uf.write_choice(folder, "\u5fae\u8f6f\u96c5\u9ed1")                    # any name: the ini is UTF-16
    assert uf.read_choice(folder) == ("\u5fae\u8f6f\u96c5\u9ed1", "")
    # Use Unicode Font's own ini is never touched
    assert (folder / uf.PATCHER_FOLDER / uf.SWITCH_INI).read_bytes().startswith(b"[Patches]\r\nMode=2")
    assert not uf.is_on(_modded(tmp_path / "off", on=False))


@pytest.mark.skipif(os.name != "nt", reason="Windows' own ini reader")
def test_windows_reads_the_choice_back(tmp_path):
    """GetPrivateProfileStringW (what the DLL calls) reads the tool's UTF-16 ini, any name included."""
    folder = _modded(tmp_path)
    k = ctypes.WinDLL("kernel32")
    k.GetPrivateProfileStringW.argtypes = [ctypes.c_wchar_p] * 4 + [ctypes.c_uint32, ctypes.c_wchar_p]
    for face, file in (("Comic Sans MS", ""), ("\u5fae\u8f6f\u96c5\u9ed1 \u00e9", "my font.ttf")):
        ini = uf.choice_path(folder)
        ini.parent.mkdir(parents=True, exist_ok=True)
        ini.write_bytes(uf.choice_bytes(face, file))
        got = []
        for key in ("Face", "File"):
            buf = ctypes.create_unicode_buffer(260)
            k.GetPrivateProfileStringW("UnicodeFont", key, "", buf, 260, str(ini))
            got.append(buf.value)
        assert got == [face, file]


def test_a_font_file_is_copied_and_named(tmp_path):
    if not ARIAL.is_file():
        pytest.skip("needs Windows' Arial")
    folder = _modded(tmp_path)
    uf.write_choice(folder, "ignored", ARIAL)
    assert uf.read_choice(folder) == ("Arial", "arial.ttf")
    assert (uf.font_folder(folder) / "arial.ttf").read_bytes() == ARIAL.read_bytes()
    with pytest.raises(uf.FontChoiceError, match=r"\.ttf, \.otf or \.ttc"):
        uf.write_choice(folder, "x", uf.choice_path(folder))
    junk = tmp_path / "junk.ttf"
    junk.write_bytes(b"not a font")
    with pytest.raises(uf.FontChoiceError, match="not a font file Windows can use"):
        uf.write_choice(folder, "x", junk)
    assert uf.read_choice(folder) == ("Arial", "arial.ttf")           # a refused choice changes nothing


@needs_windows
def test_the_preview_is_the_games_drawing():
    rows = uf.preview("Arial")
    assert [label.split(":")[0] for label, _p in rows] == list(T.FONT_NAMES)
    for (label, picture), name in zip(rows, T.FONT_NAMES):
        o = T.with_unicode_font(T.load_font(name), "Arial")
        assert label == f"{name}: Arial at {o.override[1]} px"
        assert picture == T.render(o, None, T.encode(uf.SAMPLE))


def test_the_patcher_keeps_the_font_folder_when_it_refreshes(tmp_path):
    import argparse
    import offline_vf2_patcher as patcher
    game = tmp_path / "game"
    game.mkdir()
    (game / "Virtual Families 2.exe").write_bytes(b"MZ")
    out = tmp_path / "VF2-B206-Modded"
    (out / patcher.DEFAULT_BACKUP_ROOT).mkdir(parents=True)
    files = out / uf.PATCHER_FOLDER
    (files / "Unicode Font").mkdir(parents=True)
    (files / "Unicode Font" / "Unicode Font.ini").write_bytes(uf.choice_bytes("Arial", ""))
    (files / "vf2unicodefont.ini").write_bytes(b"old")
    (out / "stale.txt").write_bytes(b"old")
    args = argparse.Namespace(json=False, quiet=True)
    patcher.prepare_output_dir(game, out, set(), args)
    assert uf.read_choice(out) == ("Arial", "")
    assert not (files / "vf2unicodefont.ini").exists() and not (out / "stale.txt").exists()
    assert (out / "Virtual Families 2.exe").read_bytes() == b"MZ"
    # without a choice the patcher files go as before
    other = tmp_path / "VF2-B207-Modded"
    (other / patcher.DEFAULT_BACKUP_ROOT).mkdir(parents=True)
    (other / uf.PATCHER_FOLDER).mkdir()
    (other / uf.PATCHER_FOLDER / "x.dll").write_bytes(b"x")
    patcher.prepare_output_dir(game, other, set(), args)
    assert not (other / uf.PATCHER_FOLDER).exists()


# --------------------------------------------------------------------------- the windows
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


@needs_windows
def test_the_unicode_font_window(tk_root, tmp_path):
    folder = _modded(tmp_path)
    window = uf.open_window(tk_root, game_folders=[folder, tmp_path / "not patched"])
    try:
        window.quiet = True
        assert window.window.title() == "Unicode Font"
        assert list(window.game_box.cget("values")) == [str(folder)]
        assert "Use Unicode Font is on in this folder." in window.status_var.get()
        assert "Chosen now: Segoe UI." in window.status_var.get() and window.face == "Segoe UI"
        assert len(window._photos) == 4
        assert "Arial" in window.faces and not any(f.startswith("@") for f in window.faces)
        window.search_var.set("aria")
        assert "Arial" in window.shown_faces and all("aria" in f.casefold() for f in window.shown_faces)
        window.face_list.selection_set(window.shown_faces.index("Arial"))
        window.face_picked()
        assert window.face == "Arial"
        assert window.save() is not None and uf.read_choice(folder) == ("Arial", "")
        assert window.status_var.get() == "Saved: the game uses Arial from its next start."
        window.choose_file(str(tmp_path / "x.txt"))
        assert window.last_message == "Choose a .ttf, .otf or .ttc font file."
        if ARIAL.is_file():
            window.choose_file(str(ARIAL))
            assert window.face == "Arial" and window.font_file == ARIAL
            window.save()
            assert uf.read_choice(folder) == ("Arial", "arial.ttf")
            window.folder_changed()
            assert "Chosen now: Arial (from arial.ttf)." in window.status_var.get()
        assert uf.open_window(tk_root) is window                              # one at a time
        window.game_var.set("")
        assert window.save() is None and window.last_message == "Choose the modded game folder first."
    finally:
        window.close()
    off = _modded(tmp_path / "off", on=False)
    window = uf.open_window(tk_root, game_folders=[off])
    try:
        assert window.status_var.get().startswith("Use Unicode Font is off in this folder: tick it on the Patches "
                                                  "tab and patch, or the game keeps its own letters.")
    finally:
        window.close()


def test_the_tools_tab_opens_it(tk_root, tmp_path, monkeypatch):
    import offline_vf2_patcher_gui as gui
    import vf2_save_backup as sb
    monkeypatch.setattr(sb, "documents_folder", lambda: tmp_path / "Documents")
    app = gui.VF2PatcherGUI(tk_root)
    folder = _modded(tmp_path)
    app.output_dir_var.set(str(folder))
    window = app.unicode_font()
    assert window.window.title() == "Unicode Font" and "unicode_font" in app.help_keys
    assert window.game_var.get() == str(folder)
    assert app.unicode_font() is window
    window.close()


GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
HAVE_FONTS = all((GAME_DIR / "Images" / f"{n}.png").is_file() for n in T.FONT_NAMES)


@needs_windows
@pytest.mark.skipif(not HAVE_FONTS, reason="no original game folder (work/vanilla_runtime_payload)")
def test_game_font_text_previews_use_unicode_font(tk_root):
    import vf2_text_tool as tt
    tool = tt.TextTool(tk_root, str(GAME_DIR))
    try:
        tool.quiet = True
        tool.set_text("Hi Zoë")
        assert tool.current_font()[0].override is None
        tool.unicode_var.set(True)
        tool.unicode_face_var.set("Comic Sans MS")
        font, sheet = tool.current_font()
        assert font.override[0] == "Comic Sans MS"
        tool.refresh()
        assert tool.image == T.render(font, sheet, T.encode("Hi Zoë"))
        px = font.override[1]
        assert (f"As Use Unicode Font draws it: Comic Sans MS at {px} px. Drawn by Windows: 6. "
                "Missing (drawn as a box): 0.") in tool.status_var.get()
        assert "(drawn by Windows: Comic Sans MS)" in tool.describe("A")
        tool.unicode_var.set(False)
        tool.refresh()
        assert "From the game font: 6." in tool.status_var.get()
    finally:
        tool.close()


# --------------------------------------------------------------------------- the DLL, under emulation, real GDI
class RealGdi:
    """The DLL's GDI calls carried out by this machine's real GDI: every call's arguments are read from the emulated
    memory, the real call is made and its results written back (a DIB's pixels are copied in and out around
    ExtTextOutW). As VF1's tests/text_emu.py RealGdi, for the calls this DLL makes."""

    def __init__(self, e, font_files: dict):
        self.e = e
        self.font_files = font_files            # a path the DLL asks AddFontResourceExW for -> this machine's file
        self.handles: dict[int, int] = {}
        self.reverse: dict[int, int] = {}
        self.dibs: dict[int, tuple] = {}        # emulated bitmap -> (real bits, emulated bits, size)
        self.selected: dict[int, int] = {}      # emulated dc -> emulated bitmap selected
        self.next = 0x9000
        self.calls: list[str] = []
        self.gdi = R._api()
        g = self.gdi
        vp = ctypes.c_void_p
        g.GetCharABCWidthsI.argtypes = [vp, ctypes.c_uint, ctypes.c_uint, vp, ctypes.POINTER(R._ABC)]
        self.bind()

    def _id(self, real) -> int:
        if not real:
            return 0
        if real in self.reverse:
            return self.reverse[real]
        self.next += 4
        self.handles[self.next] = real
        self.reverse[real] = self.next
        return self.next

    def _real(self, fake):
        return self.handles.get(fake)

    def bind(self):
        e, gdi, c = self.e, self.gdi, ctypes

        def log(name, fn):
            def wrapped(em):
                self.calls.append(name)
                return fn(em)
            return wrapped

        def signed(v):
            return v - 0x100000000 if v >= 0x80000000 else v

        def create_dc(em):
            return self._id(gdi.CreateCompatibleDC(None) or 0), 4

        def create_font(em):
            a = [em.arg(i) for i in range(13)]
            real = gdi.CreateFontW(*[signed(v) for v in a[:5]], *a[5:13], em.wstr(em.arg(13)))
            return self._id(real or 0), 56

        def select(em):
            dc, obj = em.arg(0), em.arg(1)
            prev = gdi.SelectObject(self._real(dc), self._real(obj)) if self._real(dc) and self._real(obj) else 0
            if obj in self.dibs:
                self.selected[dc] = obj
            return self._id(prev or 0), 8

        def text_face(em):
            n, buf = em.arg(1), em.arg(2)
            out = c.create_unicode_buffer(max(1, n))
            got = gdi.GetTextFaceW(self._real(em.arg(0)), n, out)
            em.write(buf, (out.value + "\0").encode("utf-16-le")[:n * 2])
            return got, 12

        def font_data(em):
            dc, table, offset, buf, size = (em.arg(i) for i in range(5))
            if not buf:
                return gdi.GetFontData(self._real(dc), table, offset, None, 0), 20
            data = c.create_string_buffer(size)
            got = gdi.GetFontData(self._real(dc), table, offset, data, size)
            if got not in (0, 0xFFFFFFFF):
                em.write(buf, data.raw[:got])
            return got, 20

        def extent(em):
            dc, s, n, size = (em.arg(i) for i in range(4))
            text = em.read(s, n * 2).decode("utf-16-le", "surrogatepass")
            sz = R._SIZE()
            ok = gdi.GetTextExtentPoint32W(self._real(dc), text, n, c.byref(sz))
            em.write(size, struct.pack("<ii", sz.cx, sz.cy))
            return ok, 16

        def metrics(em):
            tm = R._TEXTMETRICW()
            ok = gdi.GetTextMetricsW(self._real(em.arg(0)), c.byref(tm))
            em.write(em.arg(1), c.string_at(c.addressof(tm), c.sizeof(tm)))
            return ok, 8

        def abc(em):
            dc, first, count, pgi, out = (em.arg(i) for i in range(5))
            assert count == 1 and pgi == 0
            v = R._ABC()
            ok = gdi.GetCharABCWidthsI(self._real(dc), first, 1, None, c.byref(v))
            em.write(out, struct.pack("<iIi", v.abcA, v.abcB, v.abcC))
            return ok, 20

        def dib(em):
            dc, info, usage, ppv = (em.arg(i) for i in range(4))
            head = em.read(info, 40)
            _size, width, height = struct.unpack_from("<Iii", head, 0)
            bits = c.c_void_p()
            real = gdi.CreateDIBSection(self._real(dc), c.create_string_buffer(head, 44), usage, c.byref(bits),
                                        None, 0)
            n = abs(width) * abs(height) * 4
            fake_bits = em.alloc(n + 16)
            em.w32(ppv, fake_bits)
            fake = self._id(real or 0)
            self.dibs[fake] = (bits.value, fake_bits, n)
            return fake, 24

        def text_out(em):
            dc, x, y, options, rect, s, n, dx = (em.arg(i) for i in range(8))
            assert options == R.ETO_GLYPH_INDEX and rect == 0 and dx == 0
            glyphs = (c.c_uint16 * n)(*struct.unpack(f"<{n}H", em.read(s, 2 * n)))
            real_bits, fake_bits, size = self.dibs[self.selected[dc]]
            c.memmove(real_bits, em.read(fake_bits, size), size)
            ok = gdi.ExtTextOutW(self._real(dc), signed(x), signed(y), options, None, glyphs, n, None)
            gdi.GdiFlush()
            em.write(fake_bits, c.string_at(real_bits, size))
            return ok, 32

        def add_font(em):
            path = em.wstr(em.arg(0))
            local = self.font_files.get(path)
            if local is None:
                return 0, 12
            return (1 if R.add_private_font(local) else 0), 12

        def delete(em):
            real = self.handles.pop(em.arg(0), None)
            if real:
                self.reverse.pop(real, None)
                gdi.DeleteObject(real)
            self.dibs.pop(em.arg(0), None)
            return 1, 4

        def delete_dc(em):
            real = self.handles.pop(em.arg(0), None)
            if real:
                self.reverse.pop(real, None)
                gdi.DeleteDC(real)
            self.selected.pop(em.arg(0), None)
            return 1, 4

        def plain(name, n, fn):
            return log(name, lambda em: (fn(em), 4 * n))

        e.imports.update({
            "CreateCompatibleDC": log("CreateCompatibleDC", create_dc), "CreateFontW": log("CreateFontW", create_font),
            "SelectObject": log("SelectObject", select), "GetTextFaceW": log("GetTextFaceW", text_face),
            "GetFontData": log("GetFontData", font_data),
            "GetTextExtentPoint32W": log("GetTextExtentPoint32W", extent),
            "GetTextMetricsW": log("GetTextMetricsW", metrics), "CreateDIBSection": log("CreateDIBSection", dib),
            "GetCharABCWidthsI": log("GetCharABCWidthsI", abc), "ExtTextOutW": log("ExtTextOutW", text_out),
            "AddFontResourceExW": log("AddFontResourceExW", add_font),
            "DeleteObject": log("DeleteObject", delete), "DeleteDC": log("DeleteDC", delete_dc),
            "SetBkMode": plain("SetBkMode", 2, lambda em: gdi.SetBkMode(self._real(em.arg(0)), em.arg(1))),
            "SetBkColor": plain("SetBkColor", 2, lambda em: gdi.SetBkColor(self._real(em.arg(0)), em.arg(1))),
            "SetTextColor": plain("SetTextColor", 2, lambda em: gdi.SetTextColor(self._real(em.arg(0)), em.arg(1))),
            "SetTextAlign": plain("SetTextAlign", 2, lambda em: gdi.SetTextAlign(self._real(em.arg(0)), em.arg(1))),
            "GdiFlush": log("GdiFlush", lambda em: (gdi.GdiFlush(), 0)),
        })


def _kernel_seams(e):
    """The DLL's ini, string and font-file calls on this machine's real files (the settings folder is real)."""
    k = ctypes.WinDLL("kernel32")
    k.GetPrivateProfileIntW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_wchar_p]
    k.GetPrivateProfileStringW.argtypes = [ctypes.c_wchar_p] * 4 + [ctypes.c_uint32, ctypes.c_wchar_p]

    def profile_int(em):
        return k.GetPrivateProfileIntW(em.wstr(em.arg(0)), em.wstr(em.arg(1)), em.arg(2), em.wstr(em.arg(3))), 16

    def profile_string(em):
        section, key, default, buf, size, path = (em.arg(i) for i in range(6))
        out = ctypes.create_unicode_buffer(max(1, size))
        n = k.GetPrivateProfileStringW(em.wstr(section), em.wstr(key), em.wstr(default) if default else "", out,
                                       size, em.wstr(path))
        em.write(buf, (out.value[:n] + "\0").encode("utf-16-le"))
        return n, 24

    def lstrlen(em):
        return len(em.wstr(em.arg(0)).encode("utf-16-le")) // 2, 4

    def lstrcmpi(em):
        a, b = em.wstr(em.arg(0)).casefold(), em.wstr(em.arg(1)).casefold()
        return (0 if a == b else (-1 if a < b else 1)) & 0xFFFFFFFF, 8

    e.imports.update({"GetPrivateProfileIntW": profile_int, "GetPrivateProfileStringW": profile_string,
                      "lstrlenW": lstrlen, "lstrcmpiW": lstrcmpi})


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    from test_b200_unicode_dll import RUNTIME, _exe, _vcvars
    import subprocess
    if not WINDOWS or not _vcvars() or _exe() is None or not HAVE_FONTS:
        pytest.skip("needs Windows, VF2_VCVARS32, an executable built from this repo (VF2_UNICODE_EXE) and the "
                    "original game folder")
    pytest.importorskip("unicorn")
    pytest.importorskip("pefile")
    out = tmp_path_factory.mktemp("unicode_font_build")            # its own copy: another test may hold one open
    r = subprocess.run(["cmd.exe", "/c", str(RUNTIME / "native" / "build_b200unicode.bat"), "test"],
                       capture_output=True, text=True, env=dict(os.environ, VF2_UNICODE_BUILD_DIR=str(out)))
    assert r.returncode == 0, r.stdout + r.stderr
    return _exe(), out / "vf2unicode_b200_test.dll"


@pytest.mark.parametrize("face,file", [("Segoe UI", None), ("Comic Sans MS", None), ("Arial", "arial.ttf")])
def test_the_dll_draws_every_letter_with_the_chosen_font(built, tmp_path, face, file):
    """The DLL reads the tool's choice (Use Unicode Font's ini says Mode=2), loads a chosen font file for the game
    only, and its DrawString and GetWidth over the real executable, with real GDI, give every place, width and alpha
    the patcher's preview (vf2_game_text.with_unicode_font) gives, in all four fonts."""
    import vf2_glyph_maker as M
    from test_b200_unicode_dll import DrawWorld
    if file and not ARIAL.is_file():
        pytest.skip("needs Windows' Arial")
    exe, dll = built
    folder = _modded(tmp_path)
    if file:
        uf.write_choice(folder, "ignored", ARIAL)
    else:
        uf.write_choice(folder, face)
    glyphs = tmp_path / "glyphs"
    glyphs.mkdir()
    w = DrawWorld(exe, dll, glyphs)
    patcher_files = folder / uf.PATCHER_FOLDER
    gdi = RealGdi(w.e, {str(patcher_files / "Unicode Font" / "arial.ttf"): ARIAL})
    _kernel_seams(w.e)
    folder_text = w.e.alloc(1024)
    w.e.write(folder_text, (str(patcher_files) + "\\\0").encode("utf-16-le"))
    assert w.e.call(w.e.dll_export("B200Unicode_TestReadSettings"), (folder_text,)) == 2
    if file:
        assert "AddFontResourceExW" in gdi.calls
    fonts = M.load_fonts(GAME_DIR / "Images")
    sizes = []
    for name in T.FONT_NAMES:
        base, sheet = fonts[name]
        mine_font = T.with_unicode_font(base, face)
        sizes.append(mine_font.override[1] - base.gdi["px"])
        for text in ["The Smith Family", "Zoë İlkay Łukasz 日本", "Line 1\nLine 2!"]:
            raw = T.encode(text)
            game = w.draw(name, raw)
            mine = []
            for p in T.draw_string(mine_font, raw, 3, 5):
                assert p.glyph.kind == "windows"
                gw, gh, data = T.glyph_pixels(mine_font, p.glyph, sheet)
                mine.append((p.x, p.y, gw, gh, data))
            assert game and any(any(b[4][3::4]) for b in game), (name, face, text)       # really drawn
            assert [b[:4] for b in game] == [m[:4] for m in mine], (name, face, text)
            for (x, _y, _w, _h, a), (_x, _yy, _ww, _hh, b) in zip(game, mine):
                assert a[3::4] == b[3::4], (name, face, text, x)
            assert w.width(name, raw) == T.get_width(mine_font, raw), (name, face, text)
    assert "ExtTextOutW" in gdi.calls and "GetTextExtentPoint32W" in gdi.calls
    if face != "Segoe UI":
        assert any(sizes), "a face other than Segoe UI is drawn at a fitted size"


@needs_windows
def test_the_dll_without_a_choice_uses_its_own_ini(built, tmp_path):
    from test_b200_unicode_dll import DrawWorld
    exe, dll = built
    folder = _modded(tmp_path)
    (folder / uf.PATCHER_FOLDER / uf.SWITCH_INI).write_bytes(b"[Patches]\r\nMode=2\r\n[Font]\r\nFace=Courier New\r\n")
    glyphs = tmp_path / "glyphs"
    glyphs.mkdir()
    w = DrawWorld(exe, dll, glyphs)
    RealGdi(w.e, {})
    _kernel_seams(w.e)
    text = w.e.alloc(1024)
    w.e.write(text, (str(folder / uf.PATCHER_FOLDER) + "\\\0").encode("utf-16-le"))
    assert w.e.call(w.e.dll_export("B200Unicode_TestReadSettings"), (text,)) == 2
    raw = b"Hello"
    mine = T.with_unicode_font(T.load_font("Segoe24"), "Courier New")
    assert w.width("Segoe24", raw) == T.get_width(mine, raw)
    # Use Unicode Font's ini gone: the DLL is off
    (folder / uf.PATCHER_FOLDER / uf.SWITCH_INI).unlink()
    assert w.e.call(w.e.dll_export("B200Unicode_TestReadSettings"), (text,)) == 0
