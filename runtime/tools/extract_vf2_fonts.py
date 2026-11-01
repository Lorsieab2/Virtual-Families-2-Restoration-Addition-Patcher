#!/usr/bin/env python3
"""Make src/vf2_game_fonts.json: the game's four fonts as the game's own code builds them, plus the GDI fit.

    extract_vf2_fonts.py [--objs work/desktop_obj_files] [--images work/vanilla_runtime_payload/Images] [--write]

* the metrics come from running the four font constructors (tests/vf2_font_emu.py: ldwFont::Load and
  ldwFontImpl::Load run for real over the B200 desktop objects): line height, kerning, the sheet size, every glyph
  rectangle and the 256-entry byte -> glyph map;
* "gdi": the Windows font, pixel height, weight and drawing offset whose characters match the sheet best (every
  printable ASCII glyph compared pixel by pixel), and "alpha": the grey -> alpha table that turns GDI's grey levels
  into the sheet's own 16 alpha levels (for each grey level GDI gives, the sheet level it most often is).

The JSON holds numbers only (no picture of the game). The tests check it against the emulation.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from vf2_font_emu import FONT_CLASSES, FontRig  # noqa: E402
import vf2_glyph_render as R  # noqa: E402
import vf2_picture_image as P  # noqa: E402

OUT = ROOT / "src" / "vf2_game_fonts.json"
WEIGHT = {"Segoe24": R.FW_NORMAL}            # the others are Bold
PX_RANGE = range(10, 40)
TOP_RANGE = range(-10, 4)


def fit(table: dict, sheet: P.Image, weight: int) -> dict:
    widths = {g[0]: g[3] - g[1] for g in table["glyphs"]}
    best = None
    for px in PX_RANGE:
        c = R._Canvas(8, 8, "Segoe UI", px, weight)
        try:
            err = sum(abs(c.extent(chr(ch)) - widths[ch]) for ch in range(33, 127))
        finally:
            c.close()
        if best is None or err < best[0]:
            best = (err, px)
    px = best[1]
    h = table["line_height"]
    scored = []
    for top in TOP_RANGE:
        tot = 0
        for ch, l, t, r, b in table["glyphs"]:
            if not 33 <= ch < 127:
                continue
            _adv, al, w, ox = R.render(chr(ch), "Segoe UI", px, weight, h, top)
            for y in range(h):
                for x in range(r - l):
                    tot += abs(sheet.data[((t + y) * sheet.width + l + x) * 4 + 3] - al[y * w + ox + x])
        scored.append((tot, top))
    top = min(scored)[1]
    joint = collections.defaultdict(collections.Counter)
    for ch, l, t, r, b in table["glyphs"]:
        if not 33 <= ch < 127:
            continue
        _adv, al, w, ox = R.render(chr(ch), "Segoe UI", px, weight, h, top)
        for y in range(h):
            for x in range(r - l):
                a = sheet.data[((t + y) * sheet.width + l + x) * 4 + 3]
                g = al[y * w + ox + x]
                if g and a:
                    joint[g][a] += 1
    levels = sorted(joint)
    known = {g: joint[g].most_common(1)[0][0] for g in levels}
    lut = []
    for g in range(256):
        if g == 0:
            lut.append(0)
            continue
        near = min(levels, key=lambda k: (abs(k - g), k)) if levels else g
        lut.append(known.get(near, g))
    return {"face": "Segoe UI", "px": px, "weight": weight, "top": top, "width_error": best[0], "alpha": lut}


def extract(objs: Path, images: Path) -> dict:
    rig = FontRig(objs, images)
    fonts = {}
    for name in FONT_CLASSES:
        t = rig.table(name)
        sheet = P.load_png(images / t["image"], fast=False)
        t["gdi"] = fit(t, sheet, WEIGHT.get(name, R.FW_BOLD))
        fonts[name] = t
    return {"format": 1, "source": "B200 desktop objects: Segoe24/Segoe24Bold/Segoe32Bold/Segoe36Bold constructors "
                                   "(ldwFont::Load, ldwFontImpl::Load), run by tests/vf2_font_emu.py",
            "fonts": fonts}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--objs", type=Path, default=ROOT / "work" / "desktop_obj_files")
    ap.add_argument("--images", type=Path, default=ROOT / "work" / "vanilla_runtime_payload" / "Images")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    data = extract(a.objs, a.images)
    text = json.dumps(data, indent=1, sort_keys=True) + "\n"
    if a.write:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT}")
    else:
        for n, f in data["fonts"].items():
            print(n, f["line_height"], len(f["glyphs"]), {k: v for k, v in f["gdi"].items() if k != "alpha"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
