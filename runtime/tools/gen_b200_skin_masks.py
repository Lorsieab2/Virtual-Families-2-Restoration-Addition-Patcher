#!/usr/bin/env python3
"""Skin Tones for Virtual Families 2: the shape-only mask pictures the patcher ships, and the C header that ties each
one to the game picture it was made from.

    gen_b200_skin_masks.py --workbench "<Skin Tones Workbench>\\VF2" --images "<vanilla game>\\Images"
        --built "<B209 build>\\Images" [--write]

A mask holds NO game pixel: it is a 1-bit black and white PNG, white where the picture has bare skin and black
everywhere else.

* The 14 sheets of people: the workbench's finished "layers\\<sheet>\\Skin mask.png" (solid where it is skin), the
  owner's approved masks. The held baby is the only part of carrying.png that is toned: its mask is cell 3 of the
  first row only, and this tool refuses a workbench mask with skin anywhere else on that sheet.
* The Holiday outfits (bodies 50 to 53, the patcher's own art, one picture per frame: Images\\VillagerBodies\\...
  and the portraits' Images\\VillagerDetailBodies\\...): made here by the workbench's own method (vfskin.skin_mask,
  imported read-only from the workbench), run on the stock sheet with the four Holiday outfits added as rows 50 to
  53, so the colours of skin are learnt from the same 50 stock outfits the approved masks were made from. One
  picture per outfit: its 56 frames side by side (32 walking, 15 actions, 9 sitting; 91 pixels each), and one for
  its portrait body (164 pixels).

The header (runtime/native/b200skin/skin_masks.h) gives vf2skin_b200.dll, for each sheet: the game's image id and
which of its files (heads and big heads are grids of two files), the sheet's width, height and rows, and the size
and FNV-1a 64 of the vanilla file its mask was made from; for each Holiday frame and portrait (in the order of the
generated helpers' id tables): its file and the size and FNV-1a 64 of the built file. The DLL uses a mask only when
the player's file is that very file and the mask picture is its size; otherwise that picture is drawn as the game
draws it. masks.json records the same with each file's SHA-256, for the Transparency Log and the tests.

Without --write it only checks that the committed files are what a fresh run would write.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "runtime"
sys.path.insert(0, str(RUNTIME))
import b200_skin_sites as S  # noqa: E402

OUT = ROOT / "patcher_assets" / "skin_masks"
HEADER = RUNTIME / "native" / "b200skin" / "skin_masks.h"
GAME_TITLE = "VF2"
SHEET_ROWS = {"carrying.png": 7}
CARRYING = "carrying.png"
CARRYING_COLUMNS = 13
FRAME = 91                    # a Holiday frame (the stock body cell)
PORTRAIT = 164                # a Holiday portrait body (highrez_bodies_final2.png's cell)
SEXES = ("Female", "Male")    # the helpers' order: female first
ROLES = ("bodies", "actions", "sit")
ROLE_SHEETS = {"bodies": "bodies00.png", "actions": "actions00.png", "sit": "sit00.png"}


def fnv1a64(data: bytes) -> int:
    h = 0xCBF29CE484222325
    for b in data:
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise SystemExit("not a PNG")
    return struct.unpack(">II", data[16:24])


def mask_png(rows: list[bytes], width: int) -> bytes:
    """A 1-bit greyscale PNG (white = skin), no interlace, filter 0 on every row."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + r for r in rows)
    ihdr = struct.pack(">IIBBBBB", width, len(rows), 1, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def read_mask_bits(data: bytes) -> tuple[int, int, list[bytes]]:
    """(width, height, packed rows) of a mask this tool wrote (for the tests and the check)."""
    w, h = png_size(data)
    if data[24:29] != bytes([1, 0, 0, 0, 0]):
        raise SystemExit("not a 1-bit greyscale non-interlaced PNG")
    pos, idat = 8, b""
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        if data[pos + 4:pos + 8] == b"IDAT":
            idat += data[pos + 8:pos + 8 + n]
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = (w + 7) // 8
    rows = []
    for y in range(h):
        if raw[y * (stride + 1)] != 0:
            raise SystemExit("this tool writes filter 0 only")
        rows.append(bytes(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)]))
    return w, h, rows


def frame_path(sex: str, body: int, role: str, frame: int) -> str:
    return f"VillagerBodies/{sex}/Body_{body:02d}/{role}/Frame{frame:02d}.png"


def portrait_path(sex: str, body: int) -> str:
    return f"VillagerDetailBodies/{sex}/Body_{body:02d}/Frame00.png"


def holiday_bodies():
    return range(S.HOLIDAY_FIRST_BODY, S.HOLIDAY_FIRST_BODY + S.HOLIDAY_BODIES)


def _holiday(workbench: Path, images: Path, built: Path):
    """{(sex, body): (frames mask 5096 x 91, portrait mask 164 x 164)} by the workbench's method."""
    import numpy as np
    from PIL import Image
    sys.path.insert(0, str(workbench))
    import vfskin                          # read only: the workbench's own method
    Image.MAX_IMAGE_PIXELS = None
    out = {}
    stock_check = {}
    for sex in SEXES:
        prefix = sex.lower()
        frames = {b: np.zeros((FRAME, FRAME * S.HOLIDAY_FRAMES_PER_BODY), bool) for b in holiday_bodies()}
        for k, role in enumerate(ROLES):
            name = f"{prefix}_{ROLE_SHEETS[role]}"
            sheet = np.array(Image.open(images / name).convert("RGBA"))
            cols, rows, kind = vfskin.SHEETS[name]
            cell = sheet.shape[1] // cols
            if cell != FRAME or sheet.shape[0] != rows * FRAME:
                raise SystemExit(f"{name}: cells are not {FRAME} pixels")
            extra = np.zeros((S.HOLIDAY_BODIES * FRAME, sheet.shape[1], 4), np.uint8)
            for i, body in enumerate(holiday_bodies()):
                for f in range(S.HOLIDAY_ROLE_FRAMES[k]):
                    pic = np.array(Image.open(built / frame_path(sex, body, role, f)).convert("RGBA"))
                    if pic.shape[:2] != (FRAME, FRAME):
                        raise SystemExit(f"{frame_path(sex, body, role, f)} is not {FRAME} x {FRAME}")
                    extra[i * FRAME:(i + 1) * FRAME, f * FRAME:(f + 1) * FRAME] = pic
            saved = vfskin.SHEETS[name]
            vfskin.SHEETS[name] = (cols, rows + S.HOLIDAY_BODIES, kind)
            try:
                m = vfskin.skin_mask(np.concatenate([sheet, extra]), name, GAME_TITLE)
            finally:
                vfskin.SHEETS[name] = saved
            stock_check[name] = m[:rows * FRAME]
            for i, body in enumerate(holiday_bodies()):
                for f in range(S.HOLIDAY_ROLE_FRAMES[k]):
                    at = (S.HOLIDAY_ROLE_OFFSETS[k] + f) * FRAME
                    frames[body][:, at:at + FRAME] = m[(rows + i) * FRAME:(rows + i + 1) * FRAME,
                                                       f * FRAME:(f + 1) * FRAME]
        for body in holiday_bodies():
            out[(sex, body)] = [frames[body], None]
    name = "highrez_bodies_final2.png"
    sheet = np.array(Image.open(images / name).convert("RGBA"))
    cols, rows, kind = vfskin.SHEETS[name]
    if sheet.shape[1] != cols * PORTRAIT or sheet.shape[0] != rows * PORTRAIT:
        raise SystemExit(f"{name}: cells are not {PORTRAIT} pixels")
    extra = np.zeros((S.HOLIDAY_BODIES * PORTRAIT, sheet.shape[1], 4), np.uint8)
    for i, body in enumerate(holiday_bodies()):
        for sex, column in (("Male", 0), ("Female", 1)):          # the sheet: men left, women right
            pic = np.array(Image.open(built / portrait_path(sex, body)).convert("RGBA"))
            if pic.shape[:2] != (PORTRAIT, PORTRAIT):
                raise SystemExit(f"{portrait_path(sex, body)} is not {PORTRAIT} x {PORTRAIT}")
            extra[i * PORTRAIT:(i + 1) * PORTRAIT, column * PORTRAIT:(column + 1) * PORTRAIT] = pic
    saved = vfskin.SHEETS[name]
    vfskin.SHEETS[name] = (cols, rows + S.HOLIDAY_BODIES, kind)
    try:
        m = vfskin.skin_mask(np.concatenate([sheet, extra]), name, GAME_TITLE)
    finally:
        vfskin.SHEETS[name] = saved
    stock_check[name] = m[:rows * PORTRAIT]
    for i, body in enumerate(holiday_bodies()):
        for sex, column in (("Male", 0), ("Female", 1)):
            out[(sex, body)][1] = m[(rows + i) * PORTRAIT:(rows + i + 1) * PORTRAIT,
                                    column * PORTRAIT:(column + 1) * PORTRAIT]
    return out, stock_check


def build(workbench: Path, images: Path, built: Path) -> dict[str, bytes]:
    import numpy as np
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    files: dict[str, bytes] = {}
    table = []
    approved = {}
    for image, part, name in S.IMAGE_SHEETS:
        sheet_bytes = (images / name).read_bytes()
        sw, sh = png_size(sheet_bytes)
        mask = np.array(Image.open(workbench / "layers" / name[:-4] / "Skin mask.png").convert("RGBA"))
        if mask.shape[:2] != (sh, sw):
            raise SystemExit(f"{name}: the workbench mask is {mask.shape[1]} x {mask.shape[0]}, the sheet {sw} x {sh}")
        skin = mask[..., 3] >= 128
        rows = SHEET_ROWS.get(name, 50)
        if name == CARRYING:
            cell = sw // CARRYING_COLUMNS
            keep = np.zeros_like(skin)
            keep[0:sh // rows, S.BABY_CELL * cell:(S.BABY_CELL + 1) * cell] = True
            if (skin & ~keep).any():
                raise SystemExit("carrying.png: the workbench mask has skin outside the held baby (cell 3)")
        approved[name] = skin
        png = mask_png([bytes(r) for r in np.packbits(skin, axis=1)], sw)
        files[name] = png
        table.append({"sheet": name, "image": image, "part": part, "width": sw, "height": sh, "rows": rows,
                      "sheet_size": len(sheet_bytes), "sheet_fnv1a64": f"{fnv1a64(sheet_bytes):016x}",
                      "sheet_sha256": hashlib.sha256(sheet_bytes).hexdigest(),
                      "mask_sha256": hashlib.sha256(png).hexdigest(), "skin_pixels": int(skin.sum())})
    holiday, stock_check = _holiday(workbench, images, built)
    frames, portraits, outfits = [], [], []
    for sex in SEXES:
        for body in holiday_bodies():
            strip, portrait = holiday[(sex, body)]
            for key, bits, what in ((f"Holiday/{sex}_Body_{body:02d}.png", strip, "frames"),
                                    (f"Holiday/{sex}_Body_{body:02d}_portrait.png", portrait, "portrait")):
                png = mask_png([bytes(r) for r in np.packbits(bits, axis=1)], bits.shape[1])
                files[key] = png
                outfits.append({"mask": key, "sex": sex, "body": body, "what": what, "width": int(bits.shape[1]),
                                "height": int(bits.shape[0]), "mask_sha256": hashlib.sha256(png).hexdigest(),
                                "skin_pixels": int(bits.sum())})
            for k, role in enumerate(ROLES):
                for f in range(S.HOLIDAY_ROLE_FRAMES[k]):
                    data = (built / frame_path(sex, body, role, f)).read_bytes()
                    frames.append({"file": frame_path(sex, body, role, f), "size": len(data),
                                   "fnv1a64": f"{fnv1a64(data):016x}", "sha256": hashlib.sha256(data).hexdigest()})
            data = (built / portrait_path(sex, body)).read_bytes()
            portraits.append({"file": portrait_path(sex, body), "size": len(data), "fnv1a64": f"{fnv1a64(data):016x}",
                              "sha256": hashlib.sha256(data).hexdigest()})
    # how far the method run with the Holiday rows added is from the approved stock masks (a measure, not a gate:
    # the approved masks were also hand-finished in the workbench)
    agreement = {}
    for name, m in stock_check.items():
        a = approved[name]
        agreement[name] = round(float((m == a).mean()), 6)
    files["masks.json"] = (json.dumps({"game": GAME_TITLE, "masks": table, "holiday_masks": outfits,
                                       "holiday_frames": frames, "holiday_portraits": portraits,
                                       "method_agreement_with_approved_stock_masks": agreement},
                                      indent=1) + "\n").encode()
    files["skin_masks.h"] = render_header(table, frames, portraits).encode()
    return files


def render_header(table, frames, portraits) -> str:
    out = ["// GENERATED by runtime/tools/gen_b200_skin_masks.py from the Skin Tones workbench's masks, the vanilla",
           "// Images and the B209 build's Holiday outfit pictures. Do not edit. Each picture of people the DLL may",
           "// tone: the game's image id, which file of a grid of two, the sheet's size and rows, and the size and",
           "// FNV-1a 64 of the file its mask was made from; then each Holiday frame and portrait body, in the order",
           "// of the generated helpers' id tables (female first; walking, actions, sitting).",
           "#pragma once", "",
           "struct SkinSheetInfo { unsigned image, part; const wchar_t *file; int width, height, rows;",
           "                       unsigned fileSize; unsigned long long fileHash; };",
           "struct SkinFrameInfo { const wchar_t *file; unsigned fileSize; unsigned long long fileHash; };",
           f"enum {{ SKIN_SHEET_COUNT = {len(table)}, SKIN_CARRYING_COLUMNS = {CARRYING_COLUMNS}, "
           f"SKIN_FRAME = {FRAME}, SKIN_PORTRAIT = {PORTRAIT},",
           f"       SKIN_HOLIDAY_FRAME_COUNT = {len(frames)}, SKIN_HOLIDAY_PORTRAIT_COUNT = {len(portraits)} }};",
           "static const SkinSheetInfo SkinSheetInfos[SKIN_SHEET_COUNT] = {"]
    for t in table:
        out.append(f'    {{ 0x{t["image"]:X}u, {t["part"]}u, L"{t["sheet"]}", {t["width"]}, {t["height"]}, {t["rows"]}, '
                   f'{t["sheet_size"]}u, 0x{t["sheet_fnv1a64"].upper()}ull }},')
    out.append("};")
    names = [f"Holiday/{sex}_Body_{body:02d}{what}.png" for what in ("", "_portrait") for sex in SEXES
             for body in holiday_bodies()]
    out.append("// the Holiday masks in the Skin Masks folder: each outfit's 56 frames (female first), then each portrait body")
    out.append(f"static const wchar_t *const SkinHolidayMaskFiles[{len(names)}] = {{")
    for n in names:
        out.append(f'    L"{n.replace("/", chr(92) * 2)}",')
    out.append("};")
    for name, rows in (("SkinHolidayFrames", frames), ("SkinHolidayPortraits", portraits)):
        out.append(f"static const SkinFrameInfo {name}[] = {{")
        for r in rows:
            out.append(f'    {{ L"{r["file"].replace("/", chr(92) * 2)}", {r["size"]}u, 0x{r["fnv1a64"].upper()}ull }},')
        out.append("};")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbench", required=True, type=Path)
    ap.add_argument("--images", required=True, type=Path, help="the vanilla game's Images folder")
    ap.add_argument("--built", required=True, type=Path, help="a B209 build's Images folder (the Holiday outfits)")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    files = build(args.workbench, args.images, args.built)
    targets = {name: (HEADER if name == "skin_masks.h" else OUT / name) for name in files}
    if args.write:
        for name, data in files.items():
            targets[name].parent.mkdir(parents=True, exist_ok=True)
            targets[name].write_bytes(data)
        print(f"wrote {len(files)} files")
        return 0
    stale = [str(p) for name, p in targets.items() if not p.is_file() or p.read_bytes() != files[name]]
    if stale:
        print("differs from a fresh run: " + ", ".join(stale))
        return 1
    print("the committed masks are a fresh run's")
    return 0


if __name__ == "__main__":
    sys.exit(main())
