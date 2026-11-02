"""src/vf2_jpeg.py shows Virtual Families 2's .jpg pictures exactly as the game decodes them, and
src/vf2_small_formats.py reads the folder's icon.bmp and Images\\DRM\\logo1.gif.

* With the original game (work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR): the game folder's own
  libjpeg-9.dll runs in Unicorn the way SDL2_image's IMG_LoadJPG_RW calls it (tests/vf2_jpeg_emu.py), and
  vf2_jpeg.decode must give the same bytes for every .jpg under Images (Images\\DRM too) and every .jpg the
  patcher ships (patcher_assets/inherited_runtime_images).  The whole sweep takes under a minute, so it always
  runs.  The DLL's own IDCT routines are also checked against the module's kernels on random blocks, and
  pictures Pillow writes in every sampling the module handles (and cut-short or damaged ones) are compared with
  the DLL.  icon.bmp and logo1.gif must decode to Pillow's pixels (both formats are lossless).
* Without the game: Pillow-made pictures decode, exactly where libjpeg-turbo (Pillow) and libjpeg 9 must agree
  (4:4:4 colour, grey, and 4:2:0 with flat colour: same integer IDCT, same colour tables, no upsampling of
  anything that varies) and closely otherwise; broken files raise PictureError.  Pillow-made BMPs and GIFs
  decode to Pillow's own pixels.
"""
from __future__ import annotations

import io
import os
import random
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("UC_IGNORE_REG_BREAK", "1")

import vf2_jpeg  # noqa: E402
import vf2_small_formats  # noqa: E402
from vf2_picture_image import PictureError  # noqa: E402

GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or ROOT / "work" / "vanilla_runtime_payload")
HAVE_GAME = (GAME_DIR / "libjpeg-9.dll").is_file() and (GAME_DIR / "Images").is_dir()
SHIPPED = ROOT / "patcher_assets" / "inherited_runtime_images"

needs_game = pytest.mark.skipif(not HAVE_GAME, reason="no original game folder (work/vanilla_runtime_payload)")


def _pictures() -> list[str]:
    """Every .jpg the sweep covers, as "Images/..." (the game) or "shipped/..." (the patcher's own)."""
    names = []
    if HAVE_GAME:
        names += sorted("Images/" + p.relative_to(GAME_DIR / "Images").as_posix()
                        for p in (GAME_DIR / "Images").rglob("*") if p.suffix.lower() == ".jpg")
    if SHIPPED.is_dir():
        names += sorted("shipped/" + p.relative_to(SHIPPED).as_posix()
                        for p in SHIPPED.rglob("*") if p.suffix.lower() == ".jpg")
    return names


def _path(name: str) -> Path:
    if name.startswith("shipped/"):
        return SHIPPED / name.split("/", 1)[1]
    return GAME_DIR / name


def _rgb(image) -> bytes:
    n = image.width * image.height
    out = bytearray(3 * n)
    out[0::3], out[1::3], out[2::3] = image.data[0::4], image.data[1::4], image.data[2::4]
    return bytes(out)


@pytest.fixture(scope="module")
def emu():
    if not HAVE_GAME:
        pytest.skip("no original game folder (work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR)")
    pytest.importorskip("pefile")
    pytest.importorskip("unicorn")
    import faulthandler

    import vf2_jpeg_emu
    # Unicorn's memory set-up raises access violations it handles itself; pytest's faulthandler would
    # print a stack for them.
    was_on = faulthandler.is_enabled()
    faulthandler.disable()
    try:
        return vf2_jpeg_emu.JpegEmu(GAME_DIR)
    finally:
        if was_on:
            faulthandler.enable()


def _same_as_the_game(emu, data: bytes) -> None:
    width, height, expected = emu.decode(data)
    image = vf2_jpeg.decode(data)
    assert (image.width, image.height) == (width, height)
    assert image.data[3::4] == b"\xFF" * (width * height)
    got = _rgb(image)
    if got != expected:
        wrong = sum(1 for a, b in zip(got, expected) if a != b)
        pytest.fail(f"{wrong} of {len(expected)} bytes differ from libjpeg-9.dll")


# ------------------------------------------------------------------ against the game's DLL


def test_the_sweep_finds_the_games_pictures():
    names = _pictures()
    assert sum(name.startswith("shipped/") for name in names) >= 3
    if HAVE_GAME:
        assert sum(name.startswith("Images/") for name in names) >= 38
        assert "Images/DRM/virtualfamilies_drm.jpg" in names


@pytest.mark.parametrize("name", _pictures() or ["(none)"])
def test_every_game_picture_matches_libjpeg9(emu, name):
    path = _path(name)
    if not path.is_file():
        pytest.skip(f"{name} is not here")
    _same_as_the_game(emu, path.read_bytes())


@pytest.mark.parametrize("routine, cols, rows", [
    ("jpeg_idct_islow", 8, 8), ("jpeg_idct_16x16", 16, 16),
    ("jpeg_idct_16x8", 16, 8), ("jpeg_idct_8x16", 8, 16),
])
def test_idct_kernels_match_the_dll(emu, routine, cols, rows):
    rnd = random.Random(routine)
    for _ in range(60):
        coefficients = [0] * 64
        for _ in range(rnd.choice((1, 3, 12, 64))):
            coefficients[rnd.randrange(64)] = rnd.randint(-2000, 2000) if rnd.random() < 0.3 \
                else rnd.randint(-300, 300)
        quant = [rnd.randint(1, 8) for _ in range(64)]
        expected = emu.idct(routine, coefficients, quant, rows, cols)
        got = bytes(vf2_jpeg.idct([c * q for c, q in zip(coefficients, quant)], cols, rows))
        assert got == expected, (coefficients, quant)


def _pattern(width: int, height: int, mode: str = "RGB", seed: int = 1):
    Image = pytest.importorskip("PIL.Image")
    rnd = random.Random(seed)
    image = Image.new("RGB", (width, height))
    px = image.load()
    for y in range(height):
        for x in range(width):
            px[x, y] = ((x * 7 + y * 3) % 256,
                        (x * x + y * 5) % 256 if rnd.random() < 0.9 else rnd.randrange(256),
                        (y * 11 ^ x * 2) % 256)
    return image.convert(mode)


def _jpeg(image, **options) -> bytes:
    out = io.BytesIO()
    image.save(out, "JPEG", **options)
    return out.getvalue()


SAMPLINGS = ("4:4:4", "4:2:2", "4:2:0", "4:1:1")


@pytest.mark.parametrize("sampling", SAMPLINGS)
@pytest.mark.parametrize("progressive", (False, True), ids=("sequential", "progressive"))
def test_pillow_pictures_match_libjpeg9(emu, sampling, progressive):
    for size in ((37, 23), (1, 1), (130, 17)):
        data = _jpeg(_pattern(*size), quality=80, subsampling=sampling, progressive=progressive)
        _same_as_the_game(emu, data)


def test_grey_restart_and_colour_markers_match_libjpeg9(emu):
    _same_as_the_game(emu, _jpeg(_pattern(45, 33, "L")))
    _same_as_the_game(emu, _jpeg(_pattern(45, 33, "L"), progressive=True))
    _same_as_the_game(emu, _jpeg(_pattern(70, 50), subsampling="4:2:0", restart_marker_rows=1))
    base = _jpeg(_pattern(20, 20), subsampling="4:4:4")
    no_jfif = _without_jfif(base)
    # libjpeg 9: JFIF means YCbCr, then the Adobe transform, then the component ids
    _same_as_the_game(emu, _with_ids(base, b"RGB"))                   # JFIF wins: YCbCr
    _same_as_the_game(emu, _with_ids(no_jfif, b"RGB"))                # ids: RGB
    _same_as_the_game(emu, _with_adobe(no_jfif, 0))                   # Adobe 0: RGB despite ids 1 2 3
    _same_as_the_game(emu, _with_adobe(no_jfif, 1))
    _same_as_the_game(emu, _with_ids(no_jfif, b"\x04\x05\x06"))


def test_cut_short_and_damaged_pictures_match_libjpeg9(emu):
    data = _jpeg(_pattern(200, 120), subsampling="4:2:0", quality=90)
    for fraction in (0.3, 0.6, 0.99):
        _same_as_the_game(emu, data[:int(len(data) * fraction)])
    restarts = _jpeg(_pattern(200, 120), subsampling="4:2:0", quality=90, restart_marker_rows=1)
    _same_as_the_game(emu, restarts[:len(restarts) // 2])
    scan = restarts.find(b"\xFF\xDA") + 14
    for seed in range(4):
        rnd = random.Random(seed)
        damaged = bytearray(restarts)
        for _ in range(3):
            damaged[rnd.randrange(scan, len(restarts) - 2)] = rnd.randrange(256)
        _same_as_the_game(emu, bytes(damaged))


def _without_jfif(data: bytes) -> bytes:
    assert data[2:4] == b"\xFF\xE0"
    return data[:2] + data[4 + ((data[4] << 8) | data[5]):]


def _with_adobe(data: bytes, transform: int) -> bytes:
    return data[:2] + b"\xFF\xEE\x00\x0EAdobe\x00\x64\x00\x00\x00\x00" + bytes([transform]) + data[2:]


def _with_ids(data: bytes, ids: bytes) -> bytes:
    out = bytearray(data)
    sof = data.find(b"\xFF\xC0")
    sos = data.find(b"\xFF\xDA")
    for k, value in enumerate(ids):
        out[sof + 10 + 3 * k] = value
        out[sos + 5 + 2 * k] = value
    return bytes(out)


# ------------------------------------------------------------------ without the game


def _pillow_rgb(data: bytes) -> bytes:
    Image = pytest.importorskip("PIL.Image")
    return Image.open(io.BytesIO(data)).convert("RGB").tobytes()


@pytest.mark.parametrize("progressive", (False, True), ids=("sequential", "progressive"))
def test_444_and_grey_equal_pillow(progressive):
    """No upsampling: libjpeg-turbo's islow IDCT and colour tables are libjpeg 9's, bit for bit."""
    for mode in ("RGB", "L"):
        data = _jpeg(_pattern(41, 29, mode), quality=85, subsampling="4:4:4", progressive=progressive)
        image = vf2_jpeg.decode(data)
        assert (image.width, image.height) == (41, 29)
        assert _rgb(image) == _pillow_rgb(data)
        assert image.data[3::4] == b"\xFF" * (41 * 29)


def test_420_of_a_grey_picture_equals_pillow():
    """4:2:0 whose colour planes are flat: how the colour is brought up to size cannot matter."""
    grey = _pattern(53, 35, "L").convert("RGB")
    data = _jpeg(grey, quality=90, subsampling="4:2:0")
    assert _rgb(vf2_jpeg.decode(data)) == _pillow_rgb(data)


@pytest.mark.parametrize("sampling", ("4:2:0", "4:2:2"))
def test_subsampled_colour_is_close_to_pillow(sampling):
    """libjpeg 9 brings half-size colour up through a 16-point IDCT, Pillow's libjpeg-turbo with a
    triangle filter: on smooth colour the two agree within a few levels (on sharp colour edges they
    can differ by much more -- up to 67 levels on the game's 4:2:0 map tiles -- which is why Pillow is no
    reference for the game's pictures)."""
    Image = pytest.importorskip("PIL.Image")
    image = Image.new("RGB", (64, 48))
    px = image.load()
    for y in range(48):
        for x in range(64):
            px[x, y] = (x * 4, y * 5, (x + y) * 2)
    data = _jpeg(image, quality=90, subsampling=sampling)
    got, ref = _rgb(vf2_jpeg.decode(data)), _pillow_rgb(data)
    diffs = [abs(a - b) for a, b in zip(got, ref)]
    assert sum(diffs) / len(diffs) < 1
    assert max(diffs) <= 8


@pytest.mark.parametrize("data", [
    b"",
    b"not a picture",
    b"\xFF\xD8",
    b"\xFF\xD8\xFF\xD9",
    b"\x89PNG\r\n\x1a\n" + bytes(40),
], ids=("empty", "text", "only-start", "no-picture", "png"))
def test_broken_files_raise_picture_error(data):
    with pytest.raises(PictureError):
        vf2_jpeg.decode(data)


def test_damaged_headers_raise_picture_error():
    data = _jpeg(_pattern(20, 20), subsampling="4:4:4")
    with pytest.raises(PictureError):
        vf2_jpeg.decode(data[:30])                                   # cut inside the headers
    sof = data.find(b"\xFF\xC0")
    with pytest.raises(PictureError):                                 # lossless (SOF3)
        vf2_jpeg.decode(data[:sof + 1] + b"\xC3" + data[sof + 2:])
    with pytest.raises(PictureError):                                 # 12-bit samples
        vf2_jpeg.decode(data[:sof + 4] + b"\x0C" + data[sof + 5:])
    dht = data.find(b"\xFF\xC4")
    with pytest.raises(PictureError):                                 # no Huffman tables
        vf2_jpeg.decode(data[:dht] + _skip_all(data[dht:], 0xC4))


def _skip_all(data: bytes, marker: int) -> bytes:
    """data with every marker segment of one kind removed (up to the first scan)."""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xFF and data[i + 1] == marker:
            i += 2 + ((data[i + 2] << 8) | data[i + 3])
            continue
        if data[i] == 0xFF and data[i + 1] == 0xDA:
            out += data[i:]
            break
        length = (data[i + 2] << 8) | data[i + 3]
        out += data[i:i + 2 + length]
        i += 2 + length
    return bytes(out)


# ------------------------------------------------------------------ icon.bmp and logo1.gif


def _pillow_rgba(data: bytes) -> bytes:
    Image = pytest.importorskip("PIL.Image")
    return Image.open(io.BytesIO(data)).convert("RGBA").tobytes()


def _opaque(rgba: bytes) -> bytes:
    out = bytearray(rgba)
    out[3::4] = b"\xFF" * (len(out) // 4)
    return bytes(out)


@needs_game
def test_the_games_icon_bmp_is_pillows():
    data = (GAME_DIR / "icon.bmp").read_bytes()
    image = vf2_small_formats.decode_bmp(data)
    assert (image.width, image.height) == (32, 32)
    assert bytes(image.data) == _pillow_rgba(data)


@needs_game
def test_the_games_logo1_gif_is_pillows():
    data = (GAME_DIR / "Images" / "DRM" / "logo1.gif").read_bytes()
    image = vf2_small_formats.decode_gif(data)
    assert (image.width, image.height) == (98, 80)
    assert bytes(image.data) == _pillow_rgba(data)


@pytest.mark.parametrize("mode", ("1", "P", "RGB", "RGBA"))
def test_pillow_bmps_decode_to_pillows_pixels(mode):
    """1-, 8-, 24- and 32-bit BMPs; SDL_LoadBMP_RW's icon is drawn opaque, so 32-bit alpha is not used."""
    picture = _pattern(19, 7, "RGB")
    if mode == "P":
        picture = picture.quantize(colors=200)
    elif mode != "RGB":
        picture = picture.convert(mode)
    out = io.BytesIO()
    picture.save(out, "BMP")
    data = out.getvalue()
    image = vf2_small_formats.decode_bmp(data)
    assert (image.width, image.height) == (19, 7)
    assert bytes(image.data) == _opaque(_pillow_rgba(data))


def test_a_top_down_bmp_is_read_the_right_way_up():
    picture = _pattern(5, 4, "RGB")
    out = io.BytesIO()
    picture.save(out, "BMP")
    data = bytearray(out.getvalue())
    height = struct.unpack_from("<i", data, 22)[0]
    stride = ((5 * 24 + 31) // 32) * 4
    offset = struct.unpack_from("<I", data, 10)[0]
    rows = [data[offset + r * stride:offset + (r + 1) * stride] for r in range(height)]
    data[offset:offset + height * stride] = b"".join(reversed(rows))
    struct.pack_into("<i", data, 22, -height)
    assert bytes(vf2_small_formats.decode_bmp(bytes(data)).data) == _opaque(_pillow_rgba(out.getvalue()))


@pytest.mark.parametrize("interlace", (False, True), ids=("plain", "interlaced"))
def test_pillow_gifs_decode_to_pillows_pixels(interlace):
    picture = _pattern(23, 17, "RGB").quantize(colors=64)
    out = io.BytesIO()
    picture.save(out, "GIF", transparency=3, interlace=interlace)
    data = out.getvalue()
    image = vf2_small_formats.decode_gif(data)
    assert (image.width, image.height) == (23, 17)
    expected = bytearray(_pillow_rgba(data))
    assert 0 in expected[3::4]                                        # the transparent colour is used
    for k in range(0, len(expected), 4):                              # see-through pixels: clear black
        if expected[k + 3] == 0:
            expected[k:k + 4] = bytes(4)
    assert bytes(image.data) == bytes(expected)


@pytest.mark.parametrize("data", [b"", b"BM" + bytes(10), b"GIF89a" + bytes(4), b"not a picture"],
                         ids=("empty", "short-bmp", "short-gif", "text"))
def test_broken_bmps_and_gifs_raise_picture_error(data):
    with pytest.raises(PictureError):
        vf2_small_formats.decode_bmp(data)
    with pytest.raises(PictureError):
        vf2_small_formats.decode_gif(data)
