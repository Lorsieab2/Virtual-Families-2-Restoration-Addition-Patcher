"""Every line a Virtual Families 2 translation can replace, with its room: the Translations window's "Make a
translation" template (ported from the Virtual Families 1 Fun Patcher's patcher/vf1_translation_strings.py).

THE GAME'S LINES.  Every line of the game is a static record {id, key*, text*, override*} (16 bytes) of one table in
the executable's data (theStringManager's `stringTable`). read_table() finds that table in ANY build of the game, the
original or a patched one, by its shape (the game's text is never shipped: it is read from the player's own
executable). The key of a template line is `strings/<id>~<first 8 hex digits of the SHA-256 of the English>`.

THE PATCHES' LINES.  The patcher adds lines of its own (items, island events, upgrades, outfits, hairstyles,
behaviour captions...): they are records of the same table in a patched executable, with ids no stock line uses, and
the patcher's own words (src/vf2_patch_strings.json, written by runtime/tools/gen_vf2_patch_strings.py from the 32
matrix executables). A template made from the original game gets them from that file, so every line a patch adds is in
every template, whatever executable it was made from. A stock line a patch rewrites ("{name} sees pet." ->
"{name} sees their adorable pet.") is in the template with the patched words: a translation only ever runs in a
patched game. Text a patch's DLL or executable code shows that is NOT a table record is a `patch/<name>` line (the
same file's "literals"); the companion DLLs of this patcher show no text of their own.

ROOM.  src/vf2_translation_limits.json (runtime/tools/gen_b200_translations_sites.py, from the code of the matrix
executables): a line the game strncpy's into a fixed field gets that field less its NUL; a line it sprintf's,
strncat's or copies byte by byte may not be longer than the English; every line at most MAX_LINE bytes. The numbers
are the ones vf2tr_b200.dll applies (runtime/native/b200tr/b200tr.c, room()). The line the game parses (the decimal
point) is never translated.

This module is pure Python with no GUI imports.
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path

import vf2_translation_format as tf

HERE = Path(__file__).resolve().parent
LIMITS_JSON = HERE / "vf2_translation_limits.json"
PATCH_JSON = HERE / "vf2_patch_strings.json"
MAX_LINE = 1000
MIN_TABLE = 500
GAME_EXE_NAME = "Virtual Families 2.exe"
PATCHED_EXE_PREFIX = "Virtual Families 2 - B"


class StringsError(RuntimeError):
    pass


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


_LIMITS: dict | None = None
_PATCH: dict | None = None


def limits() -> dict:
    global _LIMITS
    if _LIMITS is None:
        _LIMITS = _json(LIMITS_JSON)
    return _LIMITS


def patch_data() -> dict:
    global _PATCH
    if _PATCH is None:
        _PATCH = _json(PATCH_JSON)
    return _PATCH


# ============================================================================ reading the executable
@dataclass(frozen=True)
class _Section:
    name: str
    va: int
    raw: bytes
    executable: bool


class _Image:
    """The sections of a 32-bit PE executable (headers parsed by hand: no third-party library)."""

    def __init__(self, exe: bytes):
        if len(exe) < 0x200 or exe[:2] != b"MZ":
            raise StringsError("not a Windows executable")
        pe = struct.unpack_from("<I", exe, 0x3C)[0]
        if pe + 0x18 > len(exe) or exe[pe:pe + 4] != b"PE\0\0":
            raise StringsError("not a Windows executable")
        count = struct.unpack_from("<H", exe, pe + 6)[0]
        opt_size = struct.unpack_from("<H", exe, pe + 20)[0]
        if struct.unpack_from("<H", exe, pe + 24)[0] != 0x10B:
            raise StringsError("not a 32-bit executable")
        self.base = struct.unpack_from("<I", exe, pe + 24 + 28)[0]
        self.size = struct.unpack_from("<I", exe, pe + 24 + 56)[0]
        self.sections: list[_Section] = []
        at = pe + 24 + opt_size
        for i in range(count):
            h = exe[at + 40 * i: at + 40 * i + 40]
            if len(h) < 40:
                raise StringsError("damaged executable")
            name = h[:8].rstrip(b"\0").decode("latin-1")
            vsize, va, rawsize, rawptr, _r, _l, _n, _nl, ch = struct.unpack_from("<IIIIIIHHI", h, 8)
            size = min(rawsize, vsize) if vsize else rawsize
            self.sections.append(_Section(name, self.base + va, exe[rawptr:rawptr + size], bool(ch & 0x20000000)))

    def find(self, va: int):
        for s in self.sections:
            if s.va <= va < s.va + len(s.raw):
                return s
        return None

    def cstr(self, va: int, limit: int = 4000) -> bytes | None:
        s = self.find(va)
        if s is None:
            return None
        start = va - s.va
        end = s.raw.find(b"\0", start, start + limit)
        return None if end < 0 else s.raw[start:end]


def _key_ok(key: bytes | None) -> bool:
    """A record's name: it starts with 'e' and is printable ASCII (three stock names end in a comma or a tab)."""
    return bool(key) and len(key) >= 2 and key[:1] == b"e" and all(0x20 <= c < 0x7F or c == 9 for c in key)


def read_table(exe: bytes) -> dict[int, tuple[str, bytes]]:
    """{id: (key, text)} of the game's string table in any build: the longest run of 16-byte records
    {id, key*, text*, 0} whose key is a name starting with 'e' and whose text is a string of the image. The first
    record with an id is the one the game's own lookup finds."""
    image = _Image(exe)
    best: list[tuple[int, int, int, int]] = []
    for section in image.sections:
        if section.executable or len(section.raw) < 16 * MIN_TABLE:
            continue
        raw = section.raw
        n = len(raw) // 4
        words = struct.unpack_from(f"<{n}I", raw, 0)
        seen = set()
        for w in range(n - 4):
            if w in seen or not 1 <= words[w] <= 0x2000 or words[w + 3] != 0:
                continue
            run = []
            k = w
            while k + 4 <= n and 1 <= words[k] <= 0x2000 and words[k + 3] == 0:
                key = image.cstr(words[k + 1], 200)
                if not _key_ok(key) or image.cstr(words[k + 2]) is None:
                    break
                run.append((words[k], words[k + 1], words[k + 2], 0))
                seen.add(k)
                k += 4
            if len(run) > len(best):
                best = run
    if len(best) < MIN_TABLE:
        raise StringsError("this is not a Virtual Families 2 executable (its line table was not found)")
    out: dict[int, tuple[str, bytes]] = {}
    for id_, key, text, _o in best:
        out.setdefault(id_, (image.cstr(key).decode("ascii").strip(" ,\t"), image.cstr(text)))
    return out


def find_game_exe(folders) -> Path | None:
    """The original `Virtual Families 2.exe`, else a patched `Virtual Families 2 - B...exe`, in the first folder that
    has one."""
    for folder in folders:
        p = Path(folder)
        if (p / GAME_EXE_NAME).is_file():
            return p / GAME_EXE_NAME
    for folder in folders:
        found = sorted(Path(folder).glob(PATCHED_EXE_PREFIX + "*.exe")) if Path(folder).is_dir() else []
        if found:
            return found[-1]
    return None


# ============================================================================ the room of a line
def room(string_id: int, english: str) -> int:
    """The most a line may hold, in UTF-8 bytes (vf2tr_b200.dll's room())."""
    lim = limits()
    n = len(english.encode("utf-8"))
    best = MAX_LINE
    r = lim["strncpy_room"].get(str(string_id))
    if r is not None:
        best = min(best, max(r, n))
    if string_id in lim["english_length"]:
        best = min(best, n)
    return best


def is_format_key(key: str) -> bool | None:
    """Whether the program hands the line to sprintf as its FORMAT (a plain "%" is then written "%%"); None: not known
    (no table entry for it)."""
    parts = tf.split_key(key)
    if parts is None or parts[0] != "strings":
        return None
    try:
        return True if int(parts[1]) in set(limits()["format"]) else None
    except ValueError:
        return None


tf.set_format_lookup(is_format_key)

FILLED = ("{name}", "{name2}", "{award}")
PERSON_WORDS = ("{he/she}", "{He/She}", "{him/her}", "{his/her}", "{him/2/her}", "{his/2/her}")


def _notes(key_name: str, english: str, max_length: int, byte_len: int, why: str = "") -> str:
    parts = [key_name]
    fills = [f for f in FILLED if f in english]
    if fills:
        parts.append("the game fills " + " ".join(fills))
    if "{" in english and not fills:
        parts.append("the game chooses by the person's sex: keep {he/she}-style words, or write {name: m=.. | f=..}")
    if max_length < tf_limit_cap():
        letters = f"at most {max_length} letters" if max_length >= byte_len else f"at most {byte_len} letters"
        parts.append(f"{letters} (an accented letter counts 2, a non-Latin one 2 or 3)" + (f"; {why}" if why else ""))
    return "; ".join(parts)


def tf_limit_cap() -> int:
    return MAX_LINE


# ============================================================================ the template
def entries_for(exe: bytes | None, *, patches: bool = True) -> list[tf.Entry]:
    """The lines of a template: the executable's own table (in id order, the never-translated line left out), then
    the patcher's lines that are not in it (src/vf2_patch_strings.json), then the `patch/` lines."""
    lim = limits()
    patch = patch_data()
    changed = {int(r["id"]): r["english"] for r in patch.get("changed", [])}
    rows = read_table(exe) if exe is not None else {}
    never = {int(k) for k in lim["never"]}
    out: list[tf.Entry] = []
    have: set[int] = set()
    for id_ in sorted(rows):
        if id_ in never:
            continue
        key_name, text = rows[id_]
        english = text.decode("cp1252")
        if id_ in changed and id_ <= int(patch["original_ids_to"]):
            english = changed[id_]                  # the patched words: a translation only ever runs in a patched game
        have.add(id_)
        if english.strip():                         # a line with no words has nothing to translate
            out.append(_entry(id_, key_name, english))
    if patches:
        for r in patch["table"]:
            id_ = int(r["id"])
            if id_ in have or id_ in never:
                continue
            have.add(id_)
            if r["english"].strip():
                out.append(_entry(id_, r["key"], r["english"], why="added by " + r["source"]))
        out.extend(patch_entries())
    return out


def _entry(id_: int, key_name: str, english: str, why: str = "") -> tf.Entry:
    n = len(english.encode("utf-8"))
    r = room(id_, english)
    fmt = id_ in set(limits()["format"])
    return tf.Entry(tf.make_key("strings", str(id_), english), english, _notes(key_name, english, r, n, why),
                    max_length=r, is_format=True if fmt else None)


def patch_entries() -> list[tf.Entry]:
    """The `patch/` lines: text a patch's DLL or executable code shows that is not a table record."""
    out = []
    for r in patch_data()["literals"]:
        english = r["english"]
        out.append(tf.Entry(tf.make_key("patch", r["name"], english), english,
                            f"{r['where']}; {r['note']}", max_length=int(r["max_length"]),
                            is_format=r.get("is_format")))
    return out


def new_template(exe: bytes | None, language: str, code: str, translator: str = "") -> bytes:
    """The English template as the file's bytes (UTF-8 with a BOM)."""
    entries = entries_for(exe)
    return tf.to_bytes(tf.new_file(tf.GAME, entries, language, code, translator))
