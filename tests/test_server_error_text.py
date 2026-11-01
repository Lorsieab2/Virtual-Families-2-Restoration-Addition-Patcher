"""The server's error text overflows a reply handler's stack buffer (part of Fix Vanilla Game Bugs, owner-approved
for B205 on 2026-10-31).

The stock bug: each of the six LDW server reply handlers (CLogIn, CRetrieveMessage, CPoll, CVote, CPromoCode,
CMicroTransaction ::Callback), when the reply's JSON carries an "error" string, formats
"[<Name>] (Callback) Server error: %s\\n" with it into a 0x100-byte stack buffer ([ebp-104h]; the /GS cookie is
at [ebp-4]) through the object's unbounded _sprintf. An error longer than about 220 characters runs over the
cookie and the game ends with 0xC0000409. The fix (patch_server_error_text_bounded, behind the .vf2bugs byte)
sends that one call to a stub that formats the same text through __stdio_common_vsprintf with a 0x100-byte count
and the C99 snprintf behaviour (truncate, always terminate); with the byte 0 the stub jumps to the stock _sprintf.

Layers (nothing starts the game):

* always: the generator installs it inside Fix Vanilla Game Bugs and the documents say so;
* with the desktop object files (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR): each patched object's bytes,
  and each handler linked by hand from its whole object and run under unicorn from its entry with a JSON reply
  whose "error" is 1,000 characters (stays inside the buffer with the byte 1; runs over the cookie with the byte
  0 and in the stock object) and short (the same message, byte for byte, as the stock object). The UCRT's
  __stdio_common_vsprintf (a DLL import, not in the objects) is modelled by its documented options: count -1
  unbounded, LEGACY_VSPRINTF_NULL_TERMINATION (1), STANDARD_SNPRINTF_BEHAVIOR (2);
* with executables built from this branch (VF2_SERVER_REPLY_EXE: a path or a glob): every handler's call in the
  linked executable reaches the stub, decoded.
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

faulthandler.disable()   # unicorn's first-chance access violations (tests/b200_time_emu.py does the same)

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or WORK / "desktop_obj_files")

HANDLERS = (
    ("LogIn.obj", "?Callback@CLogIn@@CAXPBD@Z", "[LogIn]"),
    ("RetrieveMessage.obj", "?Callback@CRetrieveMessage@@CAXPBD@Z", "[RetrieveMessage]"),
    ("Poll.obj", "?Callback@CPoll@@CAXPBD@Z", "[Poll]"),
    ("Vote.obj", "?Callback@CVote@@CAXPBD@Z", "[Vote]"),
    ("PromoCode.obj", "?Callback@CPromoCode@@CAXPBD@Z", "[PromoCode]"),
    ("MicroTransaction.obj", "?Callback@CMicroTransaction@@CAXPBD@Z", "[MicroTransaction]"),
)
LONG_ERROR = bytes((ord("a") + i % 26) for i in range(1000))
SHORT_ERROR = b"invalid session"
FAST_FAIL_STACK_COOKIE = 2
FAST_FAIL_INVALID_PARAMETER = 5

sys.path.insert(0, str(WORK))


def _require_objs():
    if not all((OBJ_DIR / name).is_file() for name, _h, _p in HANDLERS):
        pytest.skip("the desktop object files (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) are not present")


@pytest.fixture(scope="module")
def patched(tmp_path_factory):
    _require_objs()
    pytest.importorskip("capstone")
    import patch_mobile_furniture_pack as patcher
    out = tmp_path_factory.mktemp("server_error_text")
    old = patcher.PATCHED, patcher.SRC_OBJS
    try:
        patcher.PATCHED, patcher.SRC_OBJS = out, OBJ_DIR
        for name, _h, _p in HANDLERS:
            shutil.copy2(OBJ_DIR / name, out / name)
        manifest = {}
        patcher.patch_server_error_text_bounded(manifest)
    finally:
        patcher.PATCHED, patcher.SRC_OBJS = old
    return out, manifest


# --------------------------------------------------------------------------------------- a small linker

SKIP_SECTION = 0x00000800 | 0x00000200          # IMAGE_SCN_LNK_REMOVE | IMAGE_SCN_LNK_INFO
UNINITIALIZED = 0x00000080


def _vsprintf(fmt: bytes, args: list[bytes]) -> bytes:
    out, i, n = b"", 0, 0
    while i < len(fmt):
        if fmt[i : i + 2] == b"%s":
            out, i, n = out + args[n], i + 2, n + 1
        elif fmt[i : i + 2] == b"%%":
            out, i = out + b"%", i + 2
        else:
            assert fmt[i] != 0x25, fmt     # only %s reaches these formats
            out, i = out + fmt[i : i + 1], i + 1
    return out


class _Run:
    fast_fail = None
    message = None        # what the vsprintf wrote (up to its terminator)
    written = None        # every byte it wrote, terminator included
    buffer = None
    frame_ebp = None


def _run_handler(obj_path: Path, handler: str, flag: int, error: bytes) -> _Run:
    """Link the handler's whole object by hand and run it from its entry with a JSON reply carrying `error`."""
    pytest.importorskip("unicorn")
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_INTR, UcError
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP
    from coff_patch import CoffObject

    obj = CoffObject(obj_path)
    image, base = bytearray(), 0x10000000
    section_at = {}
    for sec in obj.sections:
        chars = struct.unpack_from("<I", obj.buf, sec.header_off + 36)[0]
        if chars & SKIP_SECTION or sec.name.startswith(".debug") or sec.name in (".drectve", ".chks64"):
            continue
        image += b"\0" * (-len(image) % 16)
        section_at[sec.index] = base + len(image)
        image += (b"\0" * sec.raw_size) if (chars & UNINITIALIZED or not sec.raw_ptr) else \
            bytes(obj.buf[sec.raw_ptr : sec.raw_ptr + sec.raw_size])
    data, hooks_page = 0x20000000, 0x30000000
    data_at, hook_at, named = {}, {}, {}

    def address(sym, rtype):
        if sym.section > 0 and sym.section in section_at:
            return section_at[sym.section] + sym.value
        table = hook_at if rtype == 20 else data_at
        if sym.name not in table:
            table[sym.name] = (hooks_page + 0x10 * len(hook_at)) if rtype == 20 else (data + 0x100 * len(data_at))
        return table[sym.name]

    for sec in obj.sections:
        if sec.index not in section_at:
            continue
        for i in range(sec.nreloc):
            vaddr, si, rtype = struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + i * 10)
            sym = obj.symbol_by_index[si]
            at = section_at[sec.index] - base + vaddr
            field = struct.unpack_from("<i", image, at)[0]
            if rtype == 6:
                struct.pack_into("<I", image, at, (address(sym, 6) + field) & 0xFFFFFFFF)
            elif rtype == 20:
                struct.pack_into("<i", image, at, address(sym, 20) + field - (section_at[sec.index] + vaddr + 4))
            elif rtype in (7, 11):     # DIR32NB / SECREL in data nobody runs
                continue
            else:  # pragma: no cover
                raise AssertionError(f"relocation type {rtype} to {sym.name}")
    for s in obj.symbols:
        if s.section > 0 and s.section in section_at:
            named[s.name] = section_at[s.section] + s.value

    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (len(image) + 0xFFFF) & ~0xFFF)
    mu.mem_write(base, bytes(image))
    mu.mem_map(data, 0x100000)
    mu.mem_map(hooks_page, 0x10000)
    mu.mem_map(0x40000000, 0x10000)
    stack, ret = 0x7E000000, 0x7F000000
    mu.mem_map(stack, 0x20000)
    mu.mem_map(ret, 0x1000)
    mu.mem_write(ret, b"\xF4")
    cookie = 0xBB40E64E
    mu.mem_write(data_at.get("___security_cookie", data + 0xFFF00), struct.pack("<I", cookie))
    if "_gVF2FixVanillaGameBugs" in data_at:
        mu.mem_write(data_at["_gVF2FixVanillaGameBugs"], bytes([flag]))
    else:
        assert flag == 0, "a stock object has no byte"
    reply, error_at, json_obj = 0x40000000, 0x40001000, 0x40003000
    mu.mem_write(reply, b'{"error":"..."}\0')
    mu.mem_write(error_at, error + b"\0")
    for name, at in hook_at.items():
        mu.mem_write(at, b"\xCC")      # every hook is handled in Python before it executes
    run = _Run()

    def cstring(uc, at, limit=0x2000):
        return bytes(uc.mem_read(at, limit)).split(b"\0", 1)[0]

    def ret_to(uc, pop):
        esp = uc.reg_read(UC_X86_REG_ESP)
        back = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        uc.reg_write(UC_X86_REG_EIP, back)

    by_address = {at: name for name, at in hook_at.items()}
    printf = named.get("_printf")

    def code(uc, addr, size, _):
        if addr == printf:
            uc.reg_write(UC_X86_REG_EAX, 0)
            return ret_to(uc, 0)
        name = by_address.get(addr)
        if name is None:
            return
        esp = uc.reg_read(UC_X86_REG_ESP)
        arg = lambda n: struct.unpack("<I", uc.mem_read(esp + 4 * n, 4))[0]
        if name == "?Parse@CJSON@@QAEPBUSJSONObject@@PBD@Z":
            assert cstring(uc, arg(1)).startswith(b"{")
            uc.reg_write(UC_X86_REG_EAX, json_obj)
            return ret_to(uc, 4)
        if name == "?GetString@SJSONObject@@QBEPBDPBD@Z":
            uc.reg_write(UC_X86_REG_EAX, error_at if cstring(uc, arg(1)) == b"error" else 0)
            return ret_to(uc, 4)
        if name == "??1SJSONObject@@QAE@XZ":
            return ret_to(uc, 0)
        if name == "??3@YAXPAXI@Z":
            return ret_to(uc, 0)
        if name == "@__security_check_cookie@4":
            if uc.reg_read(UC_X86_REG_ECX) != cookie:
                run.fast_fail = FAST_FAIL_STACK_COOKIE
                uc.emu_stop()
                return
            return ret_to(uc, 0)
        if name == "___stdio_common_vsprintf":
            options, _hi, buf, count, fmt, _locale, va = (arg(n) for n in range(1, 8))
            fmt_text = cstring(uc, fmt)
            args = [cstring(uc, struct.unpack("<I", uc.mem_read(va + 4 * k, 4))[0])
                    for k in range(fmt_text.count(b"%s"))]
            text = _vsprintf(fmt_text, args)
            if count == 0xFFFFFFFF or len(text) < count:
                written, result = text + b"\0", len(text)
            elif options & 2:
                written, result = text[: count - 1] + b"\0", len(text)
            elif options & 1:
                written, result = text[:count], 0xFFFFFFFF
            else:          # the UCRT's invalid-parameter path
                run.fast_fail = FAST_FAIL_INVALID_PARAMETER
                uc.emu_stop()
                return
            uc.mem_write(buf, written)
            run.message, run.written, run.buffer = written.split(b"\0", 1)[0], written, buf
            run.frame_ebp = struct.unpack("<I", uc.mem_read(uc.reg_read(UC_X86_REG_EBP), 4))[0]  # the handler's
            uc.reg_write(UC_X86_REG_EAX, result)
            return ret_to(uc, 0)
        raise AssertionError(f"{handler} reached {name}, which this reply never reaches")

    def interrupt(uc, number, _):
        run.fast_fail = ("interrupt", number, hex(uc.reg_read(UC_X86_REG_EIP)))
        uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, code)
    mu.hook_add(UC_HOOK_INTR, interrupt)
    sp = stack + 0x1F000
    mu.mem_write(sp, struct.pack("<II", ret, reply))
    mu.reg_write(UC_X86_REG_ESP, sp)
    mu.reg_write(UC_X86_REG_EBP, 0x0BADF00D)
    try:
        mu.emu_start(named[handler], ret, count=500000)
    except UcError as error_:  # pragma: no cover
        run.fast_fail = ("error", str(error_), hex(mu.reg_read(UC_X86_REG_EIP)))
    if run.fast_fail is None:
        assert mu.reg_read(UC_X86_REG_EIP) == ret and mu.reg_read(UC_X86_REG_ESP) == sp + 4
    return run


# ------------------------------------------------------------------------------------------------- always

def test_the_fix_is_part_of_fix_vanilla_game_bugs():
    source = (WORK / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    body = source.split("\ndef patch_fix_vanilla_game_bugs(manifest):\n", 1)[1].split("\ndef ", 1)[0]
    assert "\n    patch_server_error_text_bounded(manifest)\n" in body
    assert '"ServerErrorTextBounded",' in body


def test_the_documents_describe_it():
    for name in ("README.md", "Transparency Log.txt", "docs/Transparency Log.txt"):
        assert "error text" in (ROOT / name).read_text(encoding="utf-8"), name
    sys.path.insert(0, str(ROOT / "src"))
    import vf2_game_mechanics as gm
    texts = [f.text for f in gm.facts()]
    assert any(t.startswith(gm.WITH_PATCHER) and "error text" in t for t in texts)
    assert any(t.startswith(gm.UNPATCHED) and "error text" in t for t in texts)


# ------------------------------------------------------------------------------------- the patched objects

def test_each_handler_calls_the_stub(patched):
    out, manifest = patched
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    from coff_patch import CoffObject
    import patch_mobile_furniture_pack as patcher
    assert set(manifest["ServerErrorTextBounded"]["sites"]) == {h for _o, h, _p in HANDLERS}
    for name, handler, _prefix in HANDLERS:
        obj = CoffObject(out / name)
        stock = CoffObject(OBJ_DIR / name)
        sec, stock_sec = obj.section(obj.symbol(handler).section), stock.section(stock.symbol(handler).section)
        code = bytes(obj.buf[sec.raw_ptr : sec.raw_ptr + sec.raw_size])
        stock_code = bytes(stock.buf[stock_sec.raw_ptr : stock_sec.raw_ptr + stock_sec.raw_size])
        stub = stock_sec.raw_size
        assert len(code) == stub + patcher.SERVER_ERROR_STUB_SIZE
        relocs = patcher._function_relocations(obj, sec)
        stock_relocs = patcher._function_relocations(stock, stock_sec)
        call = next(v for v, (n, _t) in stock_relocs.items() if n == "_sprintf")
        # the only change to the handler's own bytes: the call's addend is the stub's offset, against itself
        assert struct.unpack_from("<i", code, call)[0] == stub
        assert code[:call] + code[call + 4 : stub] == stock_code[:call] + stock_code[call + 4 :]
        assert relocs[call] == (handler, 20)
        assert {v: t for v, t in relocs.items() if v != call and v < stub} == \
            {v: t for v, t in stock_relocs.items() if v != call}
        assert {v - stub: t for v, t in relocs.items() if v >= stub} == {
            0x02: (patcher.VANILLA_BUGS_FLAG_SYMBOL, 6), 0x09: ("_sprintf", 20),
            0x22: ("___local_stdio_printf_options", 20), 0x30: ("___stdio_common_vsprintf", 20),
        }
        decoded = [(i.address - stub, i.mnemonic, i.op_str)
                   for i in Cs(CS_ARCH_X86, CS_MODE_32).disasm(code[stub:], stub)]
        assert (0x19, "push", "0x100") in decoded and (0x2B, "or", "ecx, 2") in decoded
        assert decoded[-1] == (0x38, "ret", "")


@pytest.mark.parametrize("name,handler,prefix", HANDLERS, ids=[h[2] for h in HANDLERS])
def test_a_long_error_text_stays_inside_the_buffer(patched, name, handler, prefix):
    out, _ = patched
    on = _run_handler(out / name, handler, 1, LONG_ERROR)
    assert on.fast_fail is None
    assert on.buffer == on.frame_ebp - 0x104
    assert len(on.written) == 0x100 and on.written.endswith(b"\0")     # [ebp-104h] .. [ebp-5], cookie untouched
    assert on.message.startswith(prefix.encode() + b" (Callback) Server error: abcdefghij")
    assert len(on.message) == 0xFF
    for path, flag in ((out / name, 0), (OBJ_DIR / name, 0)):
        off = _run_handler(path, handler, flag, LONG_ERROR)
        assert off.fast_fail == FAST_FAIL_STACK_COOKIE, path
        assert len(off.written) > 0x100


@pytest.mark.parametrize("name,handler,prefix", HANDLERS, ids=[h[2] for h in HANDLERS])
def test_a_short_error_text_is_the_stock_message(patched, name, handler, prefix):
    out, _ = patched
    stock = _run_handler(OBJ_DIR / name, handler, 0, SHORT_ERROR)
    on = _run_handler(out / name, handler, 1, SHORT_ERROR)
    off = _run_handler(out / name, handler, 0, SHORT_ERROR)
    assert stock.fast_fail is on.fast_fail is off.fast_fail is None
    assert on.written == off.written == stock.written
    assert stock.message.startswith(prefix.encode() + b" (Callback) Server error: invalid session")
    # the longest error that fits gives the stock text too
    fits = b"x" * (0xFF - len(stock.message) + len(SHORT_ERROR))
    assert _run_handler(out / name, handler, 1, fits).written == _run_handler(OBJ_DIR / name, handler, 0, fits).written


# --------------------------------------------------------------------------------------- the executables

def test_executables_built_with_the_fix():
    value = os.environ.get("VF2_SERVER_REPLY_EXE", "")
    paths = sorted(glob.glob(value)) if any(c in value for c in "*?[") else ([value] if value else [])
    if not paths:
        pytest.skip("VF2_SERVER_REPLY_EXE (an executable built with the fix, or a glob) is not set")
    pefile = pytest.importorskip("pefile")
    for path in paths:
        pe = pefile.PE(path)
        image, base = pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase
        bugs = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".vf2bugs")
        flag = base + bugs.VirtualAddress
        # the stub's body after its flag test and je: push ebp ... push 100h ... or ecx,2 ... ret
        tail = bytes.fromhex("558BEC8D4510506A00FF750C6800010000FF7508E8")
        stubs = []
        at = image.find(tail)
        while at >= 0:
            stubs.append(at - 0x0D)
            at = image.find(tail, at + 1)
        assert len(stubs) == 6, (path, len(stubs))
        calls = {}
        for match in re.finditer(b"\xE8", image):
            i = match.start()
            if i + 5 <= len(image):
                calls.setdefault(i + 5 + struct.unpack_from("<i", image, i + 1)[0], []).append(i)
        callers = 0
        for stub in stubs:
            assert image[stub : stub + 2] == b"\x80\x3D"
            assert bugs.VirtualAddress <= struct.unpack_from("<I", image, stub + 2)[0] - base < \
                bugs.VirtualAddress + bugs.Misc_VirtualSize, path
            assert image[stub + 0x2B : stub + 0x2E] == b"\x83\xC9\x02"
            # exactly one call (from its handler, after the format push) reaches each stub
            found = calls.get(stub, [])

            assert len(found) == 1, (path, hex(base + stub), found)
            assert image[found[0] - 13 : found[0] - 6] == bytes.fromhex("508D85FCFEFFFF")
            callers += 1
        assert callers == 6 and flag
