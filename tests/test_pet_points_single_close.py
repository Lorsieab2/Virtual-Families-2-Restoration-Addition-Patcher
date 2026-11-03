"""petanimpts.dat is closed twice (part of Fix Vanilla Game Bugs, owner-approved 2026-11-02).

The stock bug: at every start CPetAnimManager::LoadAssets opens petanimpts.dat, reads its 4-byte size and, when
the size fits (<= 0x8AF0, as the shipped file's 0x8AF0 does), reads the pet link points and calls fclose at
+0x31C, then falls through to the fclose at +0x325 (where the too-big path jumps) and closes the same FILE*
again. The fix (patch_pet_points_single_close, behind the .vf2bugs byte): the fit branch's call goes to a stub
that, with the byte 1, returns 0 without closing, so +0x325 closes the file exactly once on both paths; with the
byte 0 it jumps to the stock fclose.

Run here under unicorn on the desktop object (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR), stock and patched,
with the real petanimpts.dat (work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR, else a made-up one):
fclose's calls and their FILE*, and every byte of the pet animation manager afterwards. With VF2_CORE_EXE (a
shipped core executable) the stock function is found in it byte for byte (relocations aside).
"""
from __future__ import annotations

import faulthandler
import glob
import os
import re
import shutil
import struct
import sys
from pathlib import Path

import pytest

faulthandler.disable()

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or WORK / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or WORK / "vanilla_runtime_payload")
CORE_EXE = os.environ.get("VF2_CORE_EXE")
FN = "?LoadAssets@CPetAnimManager@@QAEXXZ"
GLOBAL = "?PetAnimManager@@3VCPetAnimManager@@A"
FLAG = "_gVF2FixVanillaGameBugs"
FILE = 0x00F11E00        # the FILE* fopen hands back
SIZE = 0x14F80           # the manager's bytes compared (past its points block, +0xC6F8 + 0x8AF0)


def _require():
    if not (OBJ_DIR / "PetAnimManager.obj").is_file():
        pytest.skip("the desktop object files (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) are not present")
    pytest.importorskip("unicorn")
    sys.path.insert(0, str(ROOT / "tests"))
    import vf2_people_emu
    return vf2_people_emu


def _points_file() -> bytes:
    path = GAME_DIR / "Assets" / "petanimpts.dat"
    if path.is_file():
        return path.read_bytes()
    body = bytes((k * 7 + 3) & 0xFF for k in range(0x8AF0))
    return struct.pack("<I", len(body)) + body


@pytest.fixture(scope="module")
def patched(tmp_path_factory):
    _require()
    pytest.importorskip("capstone")
    sys.path.insert(0, str(WORK))
    import patch_mobile_furniture_pack as patcher
    out = tmp_path_factory.mktemp("pet_points")
    old = patcher.PATCHED, patcher.SRC_OBJS
    try:
        patcher.PATCHED, patcher.SRC_OBJS = out, OBJ_DIR
        shutil.copy2(OBJ_DIR / "PetAnimManager.obj", out / "PetAnimManager.obj")
        manifest = {}
        patcher.patch_pet_points_single_close(manifest)
    finally:
        patcher.PATCHED, patcher.SRC_OBJS = old
    return out, manifest


def _run(obj_dir, flag, data):
    em = _require()
    e = em.Emu(obj_dir, ["PetAnimManager"])
    grid, state = e.alloc(0x100), e.alloc(0x100)
    e.seam("?Get@theGraphicsManager@@SAPAV1@XZ", lambda e: (grid, 0))
    e.seam("?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z", lambda e: (grid, 4))
    e.seam("?GetCellRect@ldwImageGrid@@QAEXHHAAUldwRect@@@Z",
           lambda e: (e.write(e.arg(2), struct.pack("<4i", 0, 0, 64, 48)), (0, 12))[1])
    e.seam("?Get@ldwGameState@@SAPAV1@XZ", lambda e: (state, 0))
    path = e.string("petanimpts.dat")
    e.seam("vf2_test_full_path", lambda e: (path, 4))
    vtable = e.alloc(0x40)
    e.w32(vtable + 8, e.thunk_of["vf2_test_full_path"])
    e.w32(state, vtable)
    pos = [0]
    calls = []

    def fopen(e):
        calls.append(("fopen", e.cstr(e.arg(0)), e.cstr(e.arg(1))))
        return FILE, 0

    def fread(e):
        buf, size, count, f = e.arg(0), e.arg(1), e.arg(2), e.arg(3)
        assert f == FILE
        chunk = data[pos[0]:pos[0] + size * count]
        pos[0] += len(chunk)
        e.write(buf, chunk)
        calls.append(("fread", size, count))
        return len(chunk) // max(1, size), 0

    def fclose(e):
        calls.append(("fclose", e.arg(0)))
        return 0, 0
    e.seam("_fopen", fopen)
    e.seam("_fread", fread)
    e.seam("_fclose", fclose)
    if FLAG in e.data_stubs or FLAG in e.globals:
        e.write(e.addr(FLAG), bytes([flag]))
    this = e.addr(GLOBAL)
    e.call(FN, (), ecx=this)
    return calls, e.read(this, SIZE)


def test_the_stock_code_closes_the_file_twice():
    data = _points_file()
    calls, _mem = _run(OBJ_DIR, 0, data)
    assert [c for c in calls if c[0] == "fclose"] == [("fclose", FILE), ("fclose", FILE)]
    assert calls[0] == ("fopen", "petanimpts.dat", "rb")
    assert ("fread", len(data) - 4, 1) in calls


def test_the_fix_closes_it_once_and_loads_the_same_data(patched):
    out, manifest = patched
    assert manifest["PetPointsSingleClose"]["call"] == "0x31c"
    data = _points_file()
    stock_calls, stock_mem = _run(OBJ_DIR, 0, data)
    on_calls, on_mem = _run(out, 1, data)
    off_calls, off_mem = _run(out, 0, data)
    assert [c for c in on_calls if c[0] == "fclose"] == [("fclose", FILE)]
    assert [c for c in on_calls if c[0] != "fclose"] == [c for c in stock_calls if c[0] != "fclose"]
    assert on_mem == stock_mem
    assert off_calls == stock_calls and off_mem == stock_mem


@pytest.mark.parametrize("flag", [0, 1])
def test_a_file_too_big_is_closed_once_either_way(patched, flag):
    out, _manifest = patched
    data = struct.pack("<I", 0x8AF1) + bytes(0x8AF1)
    stock_calls, stock_mem = _run(OBJ_DIR, 0, data)
    calls, mem = _run(out, flag, data)
    assert [c for c in stock_calls if c[0] == "fclose"] == [("fclose", FILE)]
    assert calls == stock_calls and mem == stock_mem


def test_the_patched_bytes(patched):
    out, _manifest = patched
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    em = _require()
    obj = em.CoffObject(out / "PetAnimManager.obj")
    (value, sect), = [(v, s) for n, v, s, c in obj.symbols.values() if n == FN and s > 0]
    sec = obj.sections[sect - 1]
    code = obj.data[sec["ptr"]:sec["ptr"] + sec["size"]]
    assert value == 0 and sec["size"] == 0x367 + 0x10
    relocs = {va: obj.symbols[si][0] for va, si, _t in sec["relocs"]}
    assert relocs[0x31D] == FN and struct.unpack_from("<i", code, 0x31D)[0] == 0x367
    assert relocs[0x326] == "_fclose"
    assert relocs[0x367 + 2] == FLAG and relocs[0x367 + 9] == "_fclose"
    stub = [(x.address - 0x367, x.mnemonic, x.op_str) for x in Cs(CS_ARCH_X86, CS_MODE_32).disasm(code[0x367:], 0x367)]
    assert [(a, m) for a, m, _o in stub] == [(0, "cmp"), (7, "je"), (0xD, "xor"), (0xF, "ret")]
    stock = em.CoffObject(OBJ_DIR / "PetAnimManager.obj")
    ssec = stock.sections[sect - 1]
    assert obj.data[sec["ptr"]:sec["ptr"] + 0x367][:0x31D] == stock.data[ssec["ptr"]:ssec["ptr"] + 0x31D]


def test_the_fix_is_part_of_fix_vanilla_game_bugs():
    source = (WORK / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    body = source.split("\ndef patch_fix_vanilla_game_bugs(manifest):\n", 1)[1].split("\ndef ", 1)[0]
    assert "\n    patch_pet_points_single_close(manifest)\n" in body
    assert '"PetPointsSingleClose",' in body


def test_the_documents_describe_it():
    for name in ("README.md", "Transparency Log.txt", "docs/Transparency Log.txt"):
        assert "petanimpts.dat" in (ROOT / name).read_text(encoding="utf-8"), name


def _pattern(obj_path):
    em = _require()
    obj = em.CoffObject(obj_path)
    (sect,), = [(s,) for n, v, s, c in obj.symbols.values() if n == FN and s > 0]
    sec = obj.sections[sect - 1]
    code = obj.data[sec["ptr"]:sec["ptr"] + sec["size"]]
    masked = {va + k for va, _si, _t in sec["relocs"] for k in range(4)}
    return re.compile(b"".join(b"." if k in masked else re.escape(bytes([b])) for k, b in enumerate(code)), re.S)


def test_a_shipped_executable_holds_the_stock_or_the_patched_function(patched):
    """With VF2_CORE_EXE (path or glob): exactly one of the stock function (a build before this fix) or the
    patched one with its stub (a build with it) is in the executable, never neither."""
    if not CORE_EXE:
        pytest.skip("VF2_CORE_EXE is not set to a shipped core executable")
    pefile = pytest.importorskip("pefile")
    out, _manifest = patched
    stock, fixed = _pattern(OBJ_DIR / "PetAnimManager.obj"), _pattern(out / "PetAnimManager.obj")
    for path in sorted(glob.glob(CORE_EXE)) or [CORE_EXE]:
        pe = pefile.PE(path, fast_load=True)
        text = next(s.get_data() for s in pe.sections if s.Name.rstrip(b"\0") == b".text")
        hits = (len(stock.findall(text)), len(fixed.findall(text)))
        # the stock bytes differ from the patched ones only in the retargeted call's (masked) REL32, so a
        # patched build matches both; a stock build matches only the stock pattern
        assert hits in ((1, 0), (1, 1)), (path, hits)
