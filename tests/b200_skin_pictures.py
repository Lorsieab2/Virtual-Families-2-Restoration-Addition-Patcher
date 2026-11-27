"""Pictures of a toned family drawn through the REAL Skin Tones DLL (tests/b200_skin_world.py), for the owner.

Each person is drawn by the game's own draw code in emulation (the house, the Details portrait, the Family Tree); the
rows the DLL hands the game's blitter (its kept, recoloured copies) are then laid out where the game puts each cell,
with the Picture Maker's plans (src/vf2_people_pictures.py: the game's own link points from Assets\\anims.dat), next
to the same person in the game's own skin. Nothing here is the game's own art in a file: the pictures are written
only where the caller asks (VF2_SKIN_PICTURES), never into the repository.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import b200_skin_world as W  # noqa: E402

WIDTH_OF = {0x240: 672, 0x244: 672, 0x241: 2912, 0x245: 2912, 0x242: 1365, 0x246: 1365, 0x243: 819, 0x247: 819,
            0x15: 594, 0x16: 328, 0x1DE: 728}


def _image(surf_pixels):
    from PIL import Image
    w, h, px = surf_pixels
    return Image.frombytes("RGBA", (w, h), px, "raw", "BGRA")


def toned_rows(world, slot, frame_image, frame, turn):
    """{(image id, file part): the DLL's recoloured row} for the person in `slot`, from a house draw and a Details draw."""
    rows = {}
    for blits in (world.house(slot, body_grid=frame_image, cell=frame, turn=turn), world.detail(slot)):
        for b in blits:
            if b["surface"] not in world.made:
                continue
            w, _h = world.made[b["surface"]]
            for image, width in WIDTH_OF.items():
                if width == w:
                    rows.setdefault(width, _image(world.pixels(b["surface"])))
    return rows


def render(world, person, slot, plan, rows, own: bool):
    """The plan's layers composed: each people cell cropped from the DLL's toned row (or, `own`, the game's own
    sheet row), scaled as the game scales it."""
    import vf2_people_pictures as P
    from PIL import Image
    layers = []
    for layer in plan:
        if layer.image is None:
            continue
        name, cols, nrows, across = W.GRID_SHAPES[layer.image]
        tile = 0
        col = layer.col
        if across == 2:
            per = cols // 2
            tile, col = divmod(layer.col, per)
            name = f"{name}{tile}0.png"
        sheet_w, sheet_h, _px = W.png_pixels(world.fs.images / name)
        cw, ch = sheet_w // (cols // across), sheet_h // nrows
        if own:
            src = _image(W.png_pixels(world.fs.images / name)).crop((col * cw, layer.row * ch, col * cw + cw,
                                                                    layer.row * ch + ch))
        else:
            row = rows.get(sheet_w)
            if row is None or row.height != ch:
                continue
            src = row.crop((col * cw, 0, col * cw + cw, ch))
        if layer.percent != 100:
            src = src.resize((max(1, cw * layer.percent // 100), max(1, ch * layer.percent // 100)), Image.NEAREST)
        layers.append((src, layer.x, layer.y))
    if not layers:
        return Image.new("RGBA", (1, 1))
    x0 = min(x for _s, x, _y in layers)
    y0 = min(y for _s, _x, y in layers)
    x1 = max(x + s.width for s, x, _y in layers)
    y1 = max(y + s.height for s, _x, y in layers)
    out = Image.new("RGBA", (x1 - x0, y1 - y0))
    for src, x, y in layers:
        out.alpha_composite(src, (x - x0, y - y0))
    del P, person, slot
    return out


def family_sheet(world, people, out_dir: Path) -> list[Path]:
    """people: [(slot, name, sex, head, body, age, tone)] already in the world with their tones. Writes three
    pictures (the house, the portraits, the Family Tree), each person toned above and in the game's own skin below."""
    import vf2_people_pictures as P
    from PIL import Image, ImageDraw
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for kind in ("house", "portraits", "tree"):
        cells = []
        for slot, name, sex, head, body, age, tone in people:
            person = P.Person(sex, head, body, age)
            if kind == "house":
                plan = P.house_plan(person, 3, 1, shadow=False)
            elif kind == "portraits":
                plan = P.details_plan(person, 1)
            else:
                plan = P.tree_plan(person)
            body_layer = next(l for l in plan if l.what == "body" and l.image is not None)
            head_layer = next(l for l in plan if l.what == "head")
            if kind == "tree":           # the tree always draws the young head (tree_plan): draw them young
                world.e.w32(world.villager(slot) + W.S.VILLAGER_AGE, 600)
            rows = toned_rows(world, slot, body_layer.image if kind == "house" else (0x245 if sex == 0 else 0x241),
                              body_layer.col if kind == "house" else 0, head_layer.col % 12)
            world.e.w32(world.villager(slot) + W.S.VILLAGER_AGE, age)
            toned = render(world, person, slot, plan, rows, False)
            own = render(world, person, slot, plan, rows, True)
            scale = 2 if kind != "portraits" else 1
            cells.append((name, tone, toned.resize((toned.width * scale, toned.height * scale), Image.NEAREST),
                          own.resize((own.width * scale, own.height * scale), Image.NEAREST)))
        cw = max(max(t.width, o.width) for _n, _t, t, o in cells) + 20
        ch = max(max(t.height, o.height) for _n, _t, t, o in cells)
        canvas = Image.new("RGBA", (cw * len(cells) + 20, 2 * ch + 90), (64, 104, 150, 255))
        draw = ImageDraw.Draw(canvas)
        names = {i: n for i, n in enumerate(("Porcelain", "Fair", "Light golden", "Light olive", "Copper", "Warm brown",
                                             "Medium brown", "Deep brown", "Dark", "Ebony"), 1)}
        for k, (name, tone, toned, own) in enumerate(cells):
            x = 20 + k * cw
            canvas.alpha_composite(toned, (x, 30 + ch - toned.height))
            canvas.alpha_composite(own, (x, 60 + 2 * ch - own.height))
            draw.text((x, 8), f"{name}: S{tone} {names.get(tone, '')}", fill=(255, 255, 255, 255))
            draw.text((x, 40 + ch), "Game's own", fill=(255, 255, 255, 255))
        path = out_dir / f"skin_tones_family_{kind}.png"
        canvas.convert("RGB").save(path)
        written.append(path)
    return written
