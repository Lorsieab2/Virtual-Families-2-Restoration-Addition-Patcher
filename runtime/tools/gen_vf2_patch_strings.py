#!/usr/bin/env python3
"""Write src/vf2_patch_strings.json: the lines the patcher adds to (or rewrites in) the game's text, and the header of
the ones a companion DLL uses as printf formats.

    gen_vf2_patch_strings.py --vanilla "<original folder>\\Virtual Families 2.exe" --exes <patched exe> ... [--write]

* `table`: a line is the patcher's when its id is in a patched executable's string table and not in the original's;
* `changed`: a stock line is rewritten when EVERY patched executable gives it the same, other words (a translation only
  ever runs in a patched game, so its template uses the patched words); a stock line only some executables rewrite
  (the island events' three) keeps the original words;
* `literals`: the patches' text that is not a table record: every text a companion DLL marks with TRW(L"...") (wide: a
  Windows dialog or message box) or TRA("...", room) (narrow: drawn by the game), and the text of generated
  executable code (LITERALS below). The DLL asks vf2tr_b200.dll for each by its English (B200Tr_TextW / B200Tr_TextA).

The tool reads the tables with src/vf2_translation_strings.read_table, the very reader the Translations window uses.
It also writes runtime/native/b200tr/b200tr_patch_formats.h: the hashes of the texts a DLL fills with %s places (the DLL
writes a plain "%" of their translation as "%%").
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import vf2_translation_format as tf  # noqa: E402
import vf2_translation_strings as ts  # noqa: E402

OUT = ROOT / "src" / "vf2_patch_strings.json"
FORMATS_H = ROOT / "runtime" / "native" / "b200tr" / "b200tr_patch_formats.h"
NATIVE = ROOT / "runtime" / "native"
WIDE_MIN, WIDE_MAX = 80, 600          # vf2tr_b200.dll's patch_room_w: three times the English, at least 80, at most 600

# The companion DLLs that show text, and where it is shown. Every other DLL shows none (the scan in
# tests/test_vf2_translation_strings.py proves it).
DLL_WHERE = {
    "b200time": "Time Controls: the Settings menu button and its dialog",
}
MARK = re.compile(r'\bTR([WA])\(((?:\s*L?"(?:[^"\\\n]|\\.)*"\s*)+)(?:,\s*(\d+))?\)')
PIECE = re.compile(r'L?"((?:[^"\\\n]|\\.)*)"')
ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'"}

# Text the generated executable code shows that is not a table record. {name: (english, where, note, max_length)}.
LITERALS = {
    "exe.private_adult_romantic_time": (
        "Having private adult romantic time",
        "Behavior Patches: the caption under a same-sex couple's villagers while they try for a baby "
        "(VF2PrivateRomanticTimeLabel, strncpy(label, .., 0x27))",
        "the executable's code copies this text itself, so it is not yet read from a translation: it shows in English "
        "until the patch reads it from the string table",
        38,
    ),
}

SOURCES = (
    (r"OutfitBody", "Outfits"), (r"Hairstyle", "Hairstyles"), (r"CheatUpgrade", "Cheat Upgrades"),
    (r"CustomAchievement", "Patcher Achievements"), (r"MobileRenovation", "Mobile Renovations"),
    (r"^eEvent", "Island Events"), (r"Removable", "Special Upgrades"), (r"VF2|Lounger", "Behavior Patches"),
    (r"Gnome|Ornament|Wreath|Christmas|Candle|Candy|Dreidel|Eggnog|Angel|Poster|Painting|Menorah|Snow|Santa|Stocking",
     "Holiday Ornaments and furniture"),
)


def source_of(key: str) -> str:
    for pattern, name in SOURCES:
        if re.search(pattern, key):
            return name
    return "the patcher"


def _unescape(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append(ESCAPES.get(s[i + 1], s[i + 1]))
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _slug(text: str) -> str:
    return "_".join(re.findall(r"[a-z0-9]+", text.lower()))[:40].strip("_") or "text"


def _blank_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
    return re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), text)


def marked_texts() -> list[dict]:
    """Every TRW / TRA text of the companion DLLs' sources."""
    out: list[dict] = []
    names: set[str] = set()
    for src in sorted(NATIVE.rglob("*")):
        if src.suffix not in (".cpp", ".inc", ".c") or src.parent.name not in DLL_WHERE:
            continue
        text = _blank_comments(src.read_text(encoding="utf-8"))
        for m in MARK.finditer(text):
            english = "".join(_unescape(piece) for piece in PIECE.findall(m.group(2)))
            wide = m.group(1) == "W"
            n = len(english.encode("utf-8"))
            room = min(WIDE_MAX, max(WIDE_MIN, 3 * n)) if wide else int(m.group(3))
            same = next((o for o in out if o["english"] == english), None)
            if same is not None:                 # one line, one key: the DLL finds a patch line by its English
                if room < same["max_length"]:
                    same["max_length"] = room
                    same["note"] = same["note"].replace(re.search(r"at most \d+", same["note"]).group(0), f"at most {room}")
                same["wide"] = same["wide"] or wide
                continue
            name = f"{src.parent.name[4:]}.{_slug(english)}"
            while name in names:
                name += "_2"
            names.add(name)
            fmt = "%s" in english or "%%" in english
            note = (f"a dialog's text, at most {room} letters" if wide
                    else f"drawn by the game, at most {room} letters (a button is only so wide)")
            if fmt:
                note += "; the %s places are filled with the words shown"
            out.append({"name": name, "english": english, "wide": wide, "where": DLL_WHERE[src.parent.name],
                        "note": note, "max_length": room, "is_format": True if fmt else None})
    return out


def build(vanilla: bytes, patched: list[bytes]) -> dict:
    base = ts.read_table(vanilla)
    tables = [ts.read_table(p) for p in patched]
    table = []
    for i in sorted({i for t in tables for i in t if i not in base}):
        seen = {t[i] for t in tables if i in t}
        if len(seen) != 1:
            raise SystemExit(f"id {i} differs between the patched executables: {seen}")
        key, text = next(iter(seen))
        table.append({"id": i, "key": key, "english": text.decode("cp1252"), "source": source_of(key)})
    changed = []
    for i in sorted(base):
        words = {t[i][1] for t in tables if i in t}
        if len(words) == 1 and next(iter(words)) != base[i][1] and all(i in t for t in tables):
            changed.append({"id": i, "english": next(iter(words)).decode("cp1252"), "vanilla": base[i][1].decode("cp1252")})
    literals = marked_texts() + [
        {"name": n, "english": e, "wide": False, "where": w, "note": note, "max_length": m, "is_format": None}
        for n, (e, w, note, m) in LITERALS.items()]
    return {
        "comment": "Written by runtime/tools/gen_vf2_patch_strings.py from the original executable and the patched "
                   "ones; do not edit.",
        "executables": len(patched),
        "original_ids_to": max(base),
        "changed": changed,
        "table": table,
        "literals": sorted(literals, key=lambda r: r["name"]),
    }


def formats_header(data: dict) -> str:
    hashes = sorted(tf.key_hash(r["english"]) for r in data["literals"] if r.get("is_format"))
    rows = "".join(f"    0x{h}u,\n" for h in hashes)
    return (
        "/* Written by runtime/tools/gen_vf2_patch_strings.py; do not edit. */\n#pragma once\n"
        "/* The patches' lines a companion DLL hands a printf-style function as its FORMAT, by the hash in their key: a\n"
        "   plain '%' of their translation is written as \"%%\" (translation_format.runtime_text). */\n"
        f"#define B200TR_PATCH_FORMAT_COUNT {len(hashes)}\n"
        f"static const unsigned int B200TR_PATCH_FORMAT[] = {{\n{rows}    0u\n}};\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vanilla", required=True, type=Path)
    ap.add_argument("--exes", nargs="+", required=True, type=Path)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    data = build(args.vanilla.read_bytes(), [p.read_bytes() for p in args.exes])
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    header = formats_header(data)
    if args.write:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        FORMATS_H.write_text(header, encoding="utf-8", newline="\n")
        print(f"wrote {OUT}: {len(data['table'])} added lines, {len(data['changed'])} rewritten, "
              f"{len(data['literals'])} other texts")
        return 0
    same = OUT.read_text(encoding="utf-8") == text and FORMATS_H.read_text(encoding="utf-8") == header
    print("up to date" if same else "OUT OF DATE")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
