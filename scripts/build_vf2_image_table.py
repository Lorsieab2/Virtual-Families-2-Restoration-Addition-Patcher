"""Make src/vf2_game_pictures.json: every picture Virtual Families 2 has, and how it reaches the screen.

1. theGraphicsManager's image table (ImageList, 0x30 bytes an entry, read from the B200 desktop object
   theGraphicsManager.obj): +0 the image id (EImage), +4 the file (a string, through a relocation), +8 columns,
   +0Ch rows, +10h the second part of the file name, +14h files across, +18h files down.
   theGraphicsManagerImpl::GetImage / GetImageStrip / GetImageGrid make from it: rows > 0 an ldwImageGrid of
   columns x rows cells (one file, or the files <file><x><y><file2> side by side); rows 0 and columns > 0 an
   ldwImageStrip, one row of `columns` cells; both 0 one ldwImage, the whole file.
2. Every other file of a clean install's Images folder (data/vf2/clean-base-game-assets.json): named in the
   objects' code (searched for its name, or a printf pattern that makes it, such as MapX%dY%d.jpg) -- with the
   objects that name it -- or named nowhere: unused.
3. The clean install's Images files with their sizes and SHA-256, so the Picture Maker can tell the patcher's
   pictures (new or changed files) from the game's.

Numbers and names only, no picture. tests/test_game_pictures.py checks it against the objects again.

    python scripts/build_vf2_image_table.py [--objects work/desktop_obj_files]
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))

OUTPUTS = (REPO / "src" / "vf2_game_pictures.json", REPO / "work" / "vf2_game_pictures.json")
CLEAN = REPO / "data" / "vf2" / "clean-base-game-assets.json"
IMAGE_LIST = "?ImageList@@3PAUImageDescriptor@@A"
ENTRY = 0x30
NOT_PICTURES = (".db", ".jbf", ".css")


def _string(obj, sym_index: int, addend: int) -> str:
    _name, value, sect, _cls = obj.symbols[sym_index]
    sec = obj.sections[sect - 1]
    data = obj.data[sec["ptr"]:sec["ptr"] + sec["size"]]
    at = value + addend
    return data[at:data.index(b"\0", at)].decode("latin-1")


def image_table(objects: Path) -> list:
    from vf2_people_emu import CoffObject
    obj = CoffObject(Path(objects) / "theGraphicsManager.obj")
    _name, base, sect = next((n, v, s) for n, v, s, _c in obj.symbols.values() if n == IMAGE_LIST)
    sec = obj.sections[sect - 1]
    raw = obj.data[sec["ptr"]:sec["ptr"] + sec["size"]]
    relocs = {va: si for va, si, _t in sec["relocs"]}
    out = []
    at = base
    while at + ENTRY <= len(raw):
        fields = struct.unpack_from("<12I", raw, at)
        path = _string(obj, relocs[at + 4], fields[1]) if at + 4 in relocs else None
        if path is None and out:
            break                                           # past the table's last entry
        path2 = _string(obj, relocs[at + 0x10], fields[4]) if at + 0x10 in relocs else None
        out.append({"id": fields[0], "file": path, "file2": path2, "cols": fields[2], "rows": fields[3],
                    "across": fields[5], "down": fields[6]})
        at += ENTRY
    return out


def table_files(table: list) -> set:
    """The Images files the table names, lower case."""
    names = set()
    for e in table:
        if e["across"] * e["down"] > 1:
            names |= {f"{e['file']}{x}{y}{e['file2']}".lower() for x in range(e["across"]) for y in range(e["down"])}
        else:
            names.add(e["file"].lower())
    return names


def _strings(objects: Path) -> dict:
    """Every printable string (4+ characters) of every object, lower case -> the objects it is in."""
    found: dict = {}
    for path in sorted(Path(objects).glob("*.obj")):
        for m in re.finditer(rb"[\x20-\x7e]{4,}", path.read_bytes()):
            found.setdefault(m.group().decode("latin-1").lower(), set()).add(path.stem)
    return found


def build(objects: Path) -> dict:
    table = image_table(objects)
    clean = json.loads(CLEAN.read_text(encoding="utf-8"))["files"]
    stock = {k[len("Images/"):]: [v["size"], v["sha256"]] for k, v in sorted(clean.items()) if k.startswith("Images/")}
    named = table_files(table)
    strings = _strings(objects)
    patterns = []                                           # printf patterns that make file names
    for text in strings:
        if "%" in text and "." in text:
            last = re.split(r"[\\/]", text)[-1]
            rx = "^" + re.sub(r"%0?\d*d", r"\\d+", re.escape(last).replace("%s", ".*")) + "$"
            patterns.append((re.compile(rx), text))
    in_code, unused = {}, []
    for name in stock:
        if name.lower() in named or name.lower().endswith(NOT_PICTURES):
            continue
        base = name.split("/")[-1].lower()
        stem = base.rsplit(".", 1)[0]
        where = set()
        for text, objs in strings.items():
            if text.endswith(base) or text.endswith(stem) and len(stem) >= 5:
                where |= objs
        for rx, text in patterns:
            if rx.search(base):
                where |= strings[text]
        if where:
            in_code[name] = sorted(where)
        else:
            unused.append(name)
    return {"made_by": "scripts/build_vf2_image_table.py: theGraphicsManager's ImageList and the strings of the "
                       "B200 desktop objects; the stock files from data/vf2/clean-base-game-assets.json",
            "table": table, "named_in_code": in_code, "unused": unused, "stock": stock}


def render(data: dict) -> str:
    lines = ["{", f'  "made_by": {json.dumps(data["made_by"])},', '  "table": [']
    for k, entry in enumerate(data["table"]):
        lines.append("    " + json.dumps(entry) + ("," if k < len(data["table"]) - 1 else ""))
    lines.append("  ],")
    lines.append(f'  "named_in_code": {json.dumps(data["named_in_code"], indent=None)},')
    lines.append(f'  "unused": {json.dumps(data["unused"])},')
    lines.append('  "stock": {')
    keys = list(data["stock"])
    for k, key in enumerate(keys):
        lines.append(f"    {json.dumps(key)}: {json.dumps(data['stock'][key])}" + ("," if k < len(keys) - 1 else ""))
    lines += ["  }", "}"]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--objects", default=str(REPO / "work" / "desktop_obj_files"))
    args = parser.parse_args(argv)
    text = render(build(Path(args.objects)))
    for path in OUTPUTS:
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {path} ({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
