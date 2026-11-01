"""The LDW server reply crash (part of Fix Vanilla Game Bugs, owner-approved 2026-10-31).

The stock bug: at every start the game asks ldwsoftware.com/game_backend/login.php (and later message.php and
poll.php) through one WinINet status callback, WebClientCallback. On status 100 it reads once,
InternetReadFile(h, buf, 0x800, &n), into a 0x800-byte stack buffer and writes buf[n] = 0. A reply of 2,048
bytes or more puts the terminator one past the buffer: 0xC0000409 (the stock /GS cookie, or the rebuilt
executable's range check). LDW's server now answers with the PHP script's own source (about 3 KB), so the game
dies about 20 seconds in. The fix (patch_server_reply_guard, behind the .vf2bugs byte): read at most 0x7FF
bytes; a reply that filled the buffer or starts with '<' is handed on as no reply (NULL), the path every handler
already takes when the server does not answer.

Layers (nothing here starts the game or contacts the server):

* always: the generator installs the fix inside Fix Vanilla Game Bugs; the setting text, How to Use, Game
  Mechanics and both Transparency Logs say so;
* with the desktop object files (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR): the patched object's exact
  bytes and relocations, and the patched callback itself run under unicorn: a 3,125-byte PHP reply never
  fast-fails and reaches the handler as NULL; a short genuine reply reaches it unchanged; with the byte 0 the
  stock crash is still there (so the gate is real), and every reply handler's NULL test is pinned;
* with the retail executable (VF2_VANILLA_EXE, else work/vanilla_runtime_payload): the stock crash, emulated;
* with executables built from this branch (VF2_SERVER_REPLY_EXE: a path or a glob, e.g. the new matrix): the
  linked callback in each, emulated the same way with the byte read from the code and checked to be in
  .vf2bugs.
"""
from __future__ import annotations

import faulthandler
import glob
import hashlib
import json
import os
import shutil
import struct
import sys
from pathlib import Path

import pytest

faulthandler.disable()   # unicorn's first-chance access violations (tests/b200_time_emu.py does the same)

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or WORK / "desktop_obj_files")
VANILLA_SHA256 = "1582d9e84e1c32f51475be17335c5137c592cebf809748d401ccef99a32b73c3"

FAST_FAIL_STACK_COOKIE = 2
FAST_FAIL_RANGE_CHECK = 8

# A reply shaped like LDW's server's present answer: a PHP script's source, 3,125 bytes (text/plain).
PHP_REPLY = (b"<?php\r\n\r\nrequire_once(\"config.php\");\r\n\r\n$isNewPlayer = false;\r\n\r\n"
             + b"// padding\r\n" * 400)[:3125]
# A short reply shaped like the backend's own JSON (CLogIn::Callback reads session_id).
GENUINE_REPLY = b'{"session_id":"0123456789abcdef","error":null}\n'
INVALID_TEXT_REPLY = b"invalid"   # CPromoCode::Callback's strstr path for a reply that is not JSON


def _require_objs():
    if not (OBJ_DIR / "WebClientPlatform.obj").is_file():
        pytest.skip("the desktop object files (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) are not present")


def _patcher():
    sys.path.insert(0, str(WORK))
    import patch_mobile_furniture_pack as patcher
    return patcher


@pytest.fixture(scope="module")
def patched_obj(tmp_path_factory):
    _require_objs()
    pytest.importorskip("capstone")
    patcher = _patcher()
    out = tmp_path_factory.mktemp("server_reply_guard")
    old = patcher.PATCHED, patcher.SRC_OBJS
    try:
        patcher.PATCHED, patcher.SRC_OBJS = out, OBJ_DIR
        shutil.copy2(OBJ_DIR / "WebClientPlatform.obj", out / "WebClientPlatform.obj")
        manifest = {}
        patcher.patch_server_reply_guard(manifest)
    finally:
        patcher.PATCHED, patcher.SRC_OBJS = old
    return out / "WebClientPlatform.obj", manifest


# --------------------------------------------------------------------------------------------- the emulator

class _Run:
    def __init__(self):
        self.requested = None      # InternetReadFile's length argument
        self.reads = 0
        self.handler = "not called"
        self.fast_fail = None


def _emulate(mu, callback, read_iat, reply, read_ok, status, check_cookie, cookie_addr, handler_stub):
    """Call WebClientCallback(hInternet, context, status, info, len) the way WinINet does (stdcall)."""
    from unicorn import UC_HOOK_CODE, UC_HOOK_INTR, UcError
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

    stubs, ret = 0x7F000000, 0x7F000F00
    mu.mem_map(stubs, 0x1000)
    mu.mem_map(0x7E000000, 0x20000)
    read_stub, handler = stubs + 0x00, stubs + 0x10
    mu.mem_write(read_stub, b"\xC2\x10\x00")      # ret 10h (InternetReadFile, stdcall)
    mu.mem_write(handler, b"\xC3")                # the reply handler (cdecl)
    mu.mem_write(ret, b"\xF4")
    mu.mem_write(read_iat, struct.pack("<I", read_stub))
    handler_stub(mu, handler)
    run = _Run()
    sp = 0x7E01F000
    mu.mem_write(sp, struct.pack("<6I", ret, 0xCC0001, 0, status, 0, 0))
    mu.reg_write(UC_X86_REG_ESP, sp)

    def code(uc, addr, size, _):
        if addr == read_stub:
            esp = uc.reg_read(UC_X86_REG_ESP)
            _r, _h, buf, length, pread = struct.unpack("<5I", uc.mem_read(esp, 20))
            run.requested, run.reads = length, run.reads + 1
            got = reply[:length]
            uc.mem_write(buf, got)
            uc.mem_write(pread, struct.pack("<I", len(got) if read_ok else 0))
            uc.reg_write(UC_X86_REG_EAX, 1 if read_ok else 0)
        elif addr == handler:
            esp = uc.reg_read(UC_X86_REG_ESP)
            arg = struct.unpack("<I", uc.mem_read(esp + 4, 4))[0]
            run.handler = None if arg == 0 else bytes(uc.mem_read(arg, 0x800)).split(b"\0", 1)[0]
        elif addr == check_cookie:
            ecx = uc.reg_read(UC_X86_REG_ECX)
            if ecx != struct.unpack("<I", uc.mem_read(cookie_addr, 4))[0]:
                run.fast_fail = FAST_FAIL_STACK_COOKIE
                uc.emu_stop()

    def interrupt(uc, number, _):
        if number == 0x29:
            run.fast_fail = uc.reg_read(UC_X86_REG_ECX)
        else:
            run.fast_fail = ("interrupt", number, hex(uc.reg_read(UC_X86_REG_EIP)))
        uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, code)
    mu.hook_add(UC_HOOK_INTR, interrupt)
    try:
        mu.emu_start(callback, ret, count=200000)
    except UcError as error:  # pragma: no cover - reported as a failure below
        run.fast_fail = ("error", str(error), hex(mu.reg_read(UC_X86_REG_EIP)))
    if run.fast_fail is None:
        assert mu.reg_read(UC_X86_REG_EIP) == ret, "the callback did not return"
        assert mu.reg_read(UC_X86_REG_ESP) == sp + 0x18, "the callback did not pop its 5 arguments"
    return run


def _emulate_obj(obj_path, flag, reply, read_ok=True, status=100):
    """Run the object's WebClientCallback, linked by hand: every relocation of its section is resolved here."""
    pytest.importorskip("unicorn")
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    sys.path.insert(0, str(WORK))
    from coff_patch import CoffObject

    obj = CoffObject(Path(obj_path))
    sym = obj.symbol("?WebClientCallback@@YGXPAXKK0K@Z")
    sec = obj.section(sym.section)
    code = bytearray(obj.buf[sec.raw_ptr : sec.raw_ptr + sec.raw_size])
    base, data, rt = 0x10000000, 0x20000000, 0x30000000
    cookie_value = 0xBB40E64E
    data_at = {
        "___security_cookie": data + 0x00,
        "_gVF2FixVanillaGameBugs": data + 0x10,
        "?WebClient_hRequestHandle@@3PAXA": data + 0x20,
        "__imp__InternetReadFile@16": data + 0x30,
        "?WebClientPlatform@@3VCWebClientPlatform@@A": data + 0x40,
    }
    code_at = {
        "?Callback@CWebClientPlatform@@QAEXPBD@Z": rt + 0x00,
        "@__security_check_cookie@4": rt + 0x40,
        "___report_rangecheckfailure": rt + 0x80,
    }
    for index in range(sec.nreloc):
        vaddr, symbol_index, rtype = struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + index * 10)
        name = obj.symbol_by_index[symbol_index].name
        addend = struct.unpack_from("<i", code, vaddr)[0]
        if rtype == 6:
            struct.pack_into("<I", code, vaddr, data_at.get(name, code_at.get(name, 0)) + addend)
            assert name in data_at or name in code_at, name
        elif rtype == 20:
            assert name in code_at, name
            struct.pack_into("<i", code, vaddr, code_at[name] + addend - (base + vaddr + 4))
        else:  # pragma: no cover
            raise AssertionError(f"relocation type {rtype} for {name}")
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    for page in (base, data, rt):
        mu.mem_map(page, 0x1000)
    mu.mem_write(base, bytes(code))
    mu.mem_write(data_at["___security_cookie"], struct.pack("<I", cookie_value))
    mu.mem_write(data_at["_gVF2FixVanillaGameBugs"], bytes([flag]))
    mu.mem_write(data_at["?WebClient_hRequestHandle@@3PAXA"], struct.pack("<I", 0x1234))
    # CWebClientPlatform::Callback (thiscall, ret 4) as linked: if ([ecx]) [ecx](reply)
    mu.mem_write(code_at["?Callback@CWebClientPlatform@@QAEXPBD@Z"],
                 bytes.fromhex("558BEC8B0185C07408FF7508FFD083C4045DC20400"))
    # __security_check_cookie: cmp ecx,[cookie]; jne fail; ret; fail: mov ecx,2; int 29h
    mu.mem_write(code_at["@__security_check_cookie@4"],
                 b"\x3B\x0D" + struct.pack("<I", data_at["___security_cookie"]) + b"\x75\x01\xC3"
                 + b"\xB9\x02\x00\x00\x00\xCD\x29")
    mu.mem_write(code_at["___report_rangecheckfailure"], b"\xB9\x08\x00\x00\x00\xCD\x29")

    def handler_stub(uc, handler):
        uc.mem_write(data_at["?WebClientPlatform@@3VCWebClientPlatform@@A"], struct.pack("<I", handler))

    return _emulate(mu, base + sym.value, data_at["__imp__InternetReadFile@16"], reply, read_ok, status,
                    check_cookie=-1, cookie_addr=data_at["___security_cookie"], handler_stub=handler_stub)


# The callback as the linker lays it out from the desktop object (B204: 0x4D46D0).
EXE_SIGNATURE = bytes.fromhex("558BEC81EC08080000A1")
EXE_SIGNATURE_TAIL = bytes.fromhex("33C58945FC837D1064754D")


def _load_exe(path):
    pefile = pytest.importorskip("pefile")
    pytest.importorskip("unicorn")
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    pe = pefile.PE(str(path))
    image = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (len(image) + 0xFFF) & ~0xFFF)
    mu.mem_write(base, image)
    return pe, image, base, mu


def _find_linked_callback(image, base):
    hits = []
    at = image.find(EXE_SIGNATURE)
    while at >= 0:
        if image[at + 14 : at + 14 + len(EXE_SIGNATURE_TAIL)] == EXE_SIGNATURE_TAIL:
            hits.append(at)
        at = image.find(EXE_SIGNATURE, at + 1)
    assert len(hits) == 1, f"WebClientCallback found {len(hits)} times"
    return hits[0]


def _emulate_exe(path, flag, reply, read_ok=True, status=100):
    pe, image, base, mu = _load_exe(path)
    at = _find_linked_callback(image, base)
    u32 = lambda off: struct.unpack_from("<I", image, off)[0]
    cookie = u32(at + 0x0A)
    read_iat = u32(at + 0x34)
    platform = u32(at + 0x5D)
    check_cookie = at + 0x6B + 5 + struct.unpack_from("<i", image, at + 0x6C)[0] + base
    assert image[at + 0x20] == 0xE9, "the read-length detour is missing: not built with the fix"
    read_stub = at + 0x25 + struct.unpack_from("<i", image, at + 0x21)[0]
    assert image[read_stub : read_stub + 2] == b"\x80\x3D"
    flag_va = u32(read_stub + 2)
    reply_stub = at + 0x56 + struct.unpack_from("<i", image, at + 0x52)[0]
    assert image[at + 0x51] == 0xE9 and u32(reply_stub + 8) == flag_va
    sections = {s.Name.rstrip(b"\0").decode(): s for s in pe.sections}
    vf2bugs = sections[".vf2bugs"]
    assert vf2bugs.VirtualAddress <= flag_va - base < vf2bugs.VirtualAddress + vf2bugs.Misc_VirtualSize
    assert image[flag_va - base] == 0, "the byte is 0 in the built executable; the patcher sets it"
    mu.mem_write(flag_va, bytes([flag]))

    def handler_stub(uc, handler):
        uc.mem_write(platform, struct.pack("<I", handler))

    return _emulate(mu, base + at, read_iat, reply, read_ok, status, check_cookie, cookie, handler_stub)


def _server_reply_exes():
    value = os.environ.get("VF2_SERVER_REPLY_EXE", "")
    paths = sorted(glob.glob(value)) if any(c in value for c in "*?[") else ([value] if value else [])
    if not paths:
        pytest.skip("VF2_SERVER_REPLY_EXE (an executable built with the fix, or a glob) is not set")
    return paths


# ------------------------------------------------------------------------------------------------- always

def test_the_fix_is_part_of_fix_vanilla_game_bugs():
    source = (WORK / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    body = source.split("\ndef patch_fix_vanilla_game_bugs(manifest):\n", 1)[1].split("\ndef ", 1)[0]
    assert "\n    patch_server_reply_guard(manifest)\n" in body
    assert '"ServerReplyGuard",' in body
    main = source.split("\ndef main():\n", 1)[1].split("\ndef ", 1)[0]
    assert "\n    patch_fix_vanilla_game_bugs(manifest)\n" in main


def test_the_setting_and_the_documents_describe_it():
    sys.path.insert(0, str(WORK))
    import export_offline_patch_bundle as exporter
    row = [s for s in exporter.SETTINGS if s["id"] == "fix_vanilla_game_bugs"]
    assert len(row) == 1 and row[0]["default"] is True
    assert "LDW's server" in row[0]["description"]
    for guide in (ROOT / "src" / "vf2_how_to_use.json", WORK / "vf2_how_to_use.json"):
        controls = json.loads(guide.read_text(encoding="utf-8"))["controls"]
        text = " ".join(controls["fix_vanilla_game_bugs"]["guide"])
        assert "LDW's server" in text, guide
    assert (ROOT / "src" / "vf2_how_to_use.json").read_bytes() == (WORK / "vf2_how_to_use.json").read_bytes()
    for name in ("README.md", "How to Use.txt", "Transparency Log.txt", "docs/Transparency Log.txt"):
        assert "login.php" in (ROOT / name).read_text(encoding="utf-8"), name
    sys.path.insert(0, str(ROOT / "src"))
    import vf2_game_mechanics as gm
    texts = [f.text for f in gm.facts()]
    start = next(i for i, t in enumerate(texts) if t.startswith("LDW's server at startup"))
    assert "login.php" in texts[start] and "2,048 bytes" in texts[start]
    assert texts[start + 1].startswith(gm.WITH_PATCHER) and "2,047 bytes" in texts[start + 1]
    assert texts[start + 2].startswith(gm.UNPATCHED) and "0xC0000409" in texts[start + 2]
    assert texts[start + 3].startswith("The code against live, both written") and "PHP" in texts[start + 3]


# ------------------------------------------------------------------------------------- the patched object

def test_the_object_holds_both_detours_exactly(patched_obj):
    obj_path, manifest = patched_obj
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    sys.path.insert(0, str(WORK))
    from coff_patch import CoffObject
    patcher = _patcher()

    def section(path):
        obj = CoffObject(Path(path))
        sec = obj.section(obj.symbol(patcher.WEB_CALLBACK_FUNCTION).section)
        relocations = {}
        for index in range(sec.nreloc):
            vaddr, si, rtype = struct.unpack_from("<IIH", obj.buf, sec.reloc_ptr + index * 10)
            relocations[vaddr] = (obj.symbol_by_index[si].name, rtype)
        return bytes(obj.buf[sec.raw_ptr : sec.raw_ptr + sec.raw_size]), relocations

    code, relocations = section(obj_path)
    stock, stock_relocations = section(OBJ_DIR / "WebClientPlatform.obj")
    read_stub, reply_stub = 0x7C, 0x7C + patcher.WEB_READ_STUB_SIZE
    assert len(stock) == 0x7C and len(code) == reply_stub + patcher.WEB_REPLY_STUB_SIZE
    # The stock read length and the stock reply push are what the detours displace.
    assert stock[0x20:0x25] == bytes.fromhex("6800080000")
    assert stock[0x51:0x58] == bytes.fromhex("8D85FCF7FFFF50")
    assert code[0x20] == 0xE9 and 0x25 + struct.unpack_from("<i", code, 0x21)[0] == read_stub
    assert code[0x51] == 0xE9 and 0x56 + struct.unpack_from("<i", code, 0x52)[0] == reply_stub
    assert code[0x56:0x58] == b"\x90\x90"
    assert code[:0x20] + code[0x25:0x51] + code[0x58:0x7C] == stock[:0x20] + stock[0x25:0x51] + stock[0x58:]
    for vaddr, target in stock_relocations.items():
        assert relocations[vaddr] == target
    flag = (patcher.VANILLA_BUGS_FLAG_SYMBOL, 6)
    assert {v: t for v, t in relocations.items() if v >= 0x7C} == {read_stub + 2: flag, reply_stub + 8: flag}
    decoded = [(i.address, i.mnemonic, i.op_str) for i in Cs(CS_ARCH_X86, CS_MODE_32).disasm(code[0x7C:], 0x7C)]
    assert decoded[:5] == [
        (0x7C, "cmp", "byte ptr [0], 0"), (0x83, "jne", "0x8f"), (0x85, "push", "0x800"),
        (0x8A, "jmp", "0x25"), (0x8F, "push", "0x7ff"),
    ]
    assert decoded[6:10] == [
        (0x99, "lea", "eax, [ebp - 0x804]"), (0xA0 - 1, "cmp", "byte ptr [0], 0"),
        (0xA6, "je", "0xd4"), (0xA8, "cmp", "dword ptr [ebp - 0x808], 0x7ff"),
    ]
    assert decoded[-4:] == [(0xD0, "jne", "0xd4"), (0xD2, "xor", "eax, eax"), (0xD4, "push", "eax"),
                            (0xD5, "jmp", "0x5c")]
    contract = manifest["ServerReplyGuard"]
    assert contract["offline_patcher_setting"] == "fix_vanilla_game_bugs" and contract["status"] == "installed"
    assert len(contract["reply_check"]["handlers"]) == 6


def test_every_reply_handler_treats_null_as_no_reply():
    """The guard hands a bad reply on as NULL; each handler's first test is that NULL (its no-reply path)."""
    _require_objs()
    sys.path.insert(0, str(WORK))
    from coff_patch import CoffObject
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    for obj_name, handler in (
        ("LogIn.obj", "?Callback@CLogIn@@CAXPBD@Z"),
        ("RetrieveMessage.obj", "?Callback@CRetrieveMessage@@CAXPBD@Z"),
        ("Poll.obj", "?Callback@CPoll@@CAXPBD@Z"),
        ("Vote.obj", "?Callback@CVote@@CAXPBD@Z"),
        ("PromoCode.obj", "?Callback@CPromoCode@@CAXPBD@Z"),
        ("MicroTransaction.obj", "?Callback@CMicroTransaction@@CAXPBD@Z"),
    ):
        obj = CoffObject(OBJ_DIR / obj_name)
        sec = obj.section(obj.symbol(handler).section)
        code = bytes(obj.buf[sec.raw_ptr : sec.raw_ptr + sec.raw_size])
        decoded = [(i.mnemonic, i.op_str) for i in Cs(CS_ARCH_X86, CS_MODE_32).disasm(code[:0x20], 0)]
        loads = [i for i, d in enumerate(decoded) if d[0] == "mov" and d[1].endswith("dword ptr [ebp + 8]")]
        assert loads, handler
        reg = decoded[loads[0]][1].split(",")[0]
        tests = [i for i, d in enumerate(decoded) if d == ("test", f"{reg}, {reg}")]
        assert tests and decoded[tests[0] + 1][0] == "je", handler


def test_a_long_php_reply_no_longer_crashes_and_is_ignored(patched_obj):
    obj_path, _ = patched_obj
    assert len(PHP_REPLY) == 3125
    run = _emulate_obj(obj_path, 1, PHP_REPLY)
    assert run.fast_fail is None
    assert run.requested == 0x7FF and run.reads == 1
    assert run.handler is None                       # handed on as no reply


def test_the_stock_crash_is_still_there_with_the_byte_off(patched_obj):
    """Two-way: with .vf2bugs 0 the patched object behaves as stock, and stock dies on a 2,048-byte read."""
    obj_path, _ = patched_obj
    for path in (obj_path, OBJ_DIR / "WebClientPlatform.obj"):
        run = _emulate_obj(path, 0, PHP_REPLY)
        assert run.requested == 0x800
        assert run.fast_fail == FAST_FAIL_RANGE_CHECK, path
        run = _emulate_obj(path, 0, PHP_REPLY[:2047])
        assert run.fast_fail is None and run.handler == PHP_REPLY[:2047]


@pytest.mark.parametrize("reply", [GENUINE_REPLY, INVALID_TEXT_REPLY, b"", b"  \r\n" + GENUINE_REPLY,
                                   b"{" + b"x" * 2044 + b"}"])
def test_a_genuine_reply_is_handed_on_unchanged(patched_obj, reply):
    obj_path, _ = patched_obj
    fixed = _emulate_obj(obj_path, 1, reply)
    stock = _emulate_obj(obj_path, 0, reply)
    original = _emulate_obj(OBJ_DIR / "WebClientPlatform.obj", 1, reply)
    assert fixed.fast_fail is stock.fast_fail is original.fast_fail is None
    assert fixed.handler == stock.handler == original.handler == reply


@pytest.mark.parametrize("reply", [PHP_REPLY[:600], b"\r\n\t <html><body>404</body></html>",
                                   b"{" + b"x" * 2100 + b"}", PHP_REPLY[:2047], b"{" + b"x" * 2045 + b"}"])
def test_a_reply_that_is_not_backend_output_is_ignored(patched_obj, reply):
    obj_path, _ = patched_obj
    run = _emulate_obj(obj_path, 1, reply)
    assert run.fast_fail is None and run.handler is None


def test_a_failed_read_and_other_statuses_are_stock(patched_obj):
    obj_path, _ = patched_obj
    for flag in (0, 1):
        run = _emulate_obj(obj_path, flag, GENUINE_REPLY, read_ok=False)
        assert run.fast_fail is None and run.handler is None
        run = _emulate_obj(obj_path, flag, GENUINE_REPLY, status=21)
        assert run.fast_fail is None and run.reads == 0 and run.handler == "not called"


# --------------------------------------------------------------------------------------- the executables

def test_the_retail_executable_dies_on_a_long_reply():
    path = os.environ.get("VF2_VANILLA_EXE") or str(WORK / "vanilla_runtime_payload" / "Virtual Families 2.exe")
    if not Path(path).is_file():
        pytest.skip("no retail Virtual Families 2.exe (VF2_VANILLA_EXE or work/vanilla_runtime_payload)")
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != VANILLA_SHA256:
        pytest.skip("not the retail executable this test pins")
    pe, image, base, mu = _load_exe(path)
    callback = 0x4C3360
    assert image[0x4C3388 - base : 0x4C338D - base] == bytes.fromhex("6800080000")   # push 800h
    assert image[0x4C33A4 - base : 0x4C33A9 - base] == bytes.fromhex("C644040400")   # buf[n] = 0
    cookie = 0x557A44

    def handler_stub(uc, handler):
        uc.mem_write(0xB20E28, struct.pack("<I", handler))

    run = _emulate(mu, callback, 0x4DE3D4, PHP_REPLY, True, 100, 0x4C3BCE, cookie, handler_stub)
    assert run.requested == 0x800 and run.fast_fail == FAST_FAIL_STACK_COOKIE
    _pe, _image, _base, mu = _load_exe(path)
    run = _emulate(mu, callback, 0x4DE3D4, GENUINE_REPLY, True, 100, 0x4C3BCE, cookie, handler_stub)
    assert run.fast_fail is None and run.handler == GENUINE_REPLY


def test_executables_built_with_the_fix():
    for path in _server_reply_exes():
        on = _emulate_exe(path, 1, PHP_REPLY)
        assert on.fast_fail is None and on.requested == 0x7FF and on.handler is None, path
        off = _emulate_exe(path, 0, PHP_REPLY)
        assert off.requested == 0x800 and off.fast_fail == FAST_FAIL_RANGE_CHECK, path
        for reply in (GENUINE_REPLY, INVALID_TEXT_REPLY):
            on, off = _emulate_exe(path, 1, reply), _emulate_exe(path, 0, reply)
            assert on.fast_fail is off.fast_fail is None, path
            assert on.handler == off.handler == reply, path
        short_php = _emulate_exe(path, 1, PHP_REPLY[:600])
        assert short_php.fast_fail is None and short_php.handler is None, path
