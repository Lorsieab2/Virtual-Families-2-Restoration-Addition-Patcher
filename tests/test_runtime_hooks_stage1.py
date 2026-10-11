"""Stage 1 runtime-hook module (Allow Older Pregnancies on the VANILLA game).

Three layers:

* Always: the committed site header matches vf2_runtime_sites.py, the loader
  stub decodes to exactly the intended code, and the DLL's port of the B200
  helpers is textually identical to B200's helper source.
* With the vanilla game (VF2_VANILLA_RUNTIME_DIR = the read-only vanilla
  folder): every pin is proved by capstone (gen_sites.validate), and the
  patched executable differs from vanilla only in the PE header fields, the
  two new section headers, the Init vtable slot and the appended sections, and
  its checksum is what Windows computes.
* With the vanilla game AND Visual Studio (VF2_VCVARS32, default VS 18 path):
  the DLL and a 32-bit harness are built, and the harness runs the real stub
  and DLL against an in-memory copy of the patched image (the game is never
  started; see runtime/tests/stage1_harness.cpp). Installed bytes,
  trampoline, page protections, the young-couple path against the unhooked
  stock body, the late-age roll against a model of B200's helper, the
  cooldown store and the next-generation wrapper are all checked.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "tools"))

import vf2_runtime_sites as S  # noqa: E402
import vf2_runtime_patcher as P  # noqa: E402
import gen_sites  # noqa: E402
import build_stub  # noqa: E402

capstone = pytest.importorskip("capstone")
from capstone import CS_ARCH_X86, CS_MODE_32, Cs  # noqa: E402
from capstone.x86 import X86_OP_IMM, X86_OP_MEM  # noqa: E402

VANILLA_DIR = os.environ.get("VF2_VANILLA_RUNTIME_DIR")
VCVARS = os.environ.get(
    "VF2_VCVARS32",
    r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat",
)
GENERATOR = ROOT / "work" / "patch_mobile_furniture_pack.py"
DLL_SOURCE = RUNTIME / "native" / "vf2fun" / "vf2fun.cpp"


def _md() -> Cs:
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    return md


def vanilla_bytes() -> bytes:
    if not VANILLA_DIR:
        pytest.skip("VF2_VANILLA_RUNTIME_DIR is not set")
    exe = Path(VANILLA_DIR) / S.VANILLA_EXE_NAME
    if not exe.is_file():
        pytest.skip(f"vanilla executable not found: {exe}")
    return exe.read_bytes()


# --------------------------------------------------------------- always
def test_site_header_is_generated_from_the_sites_module():
    header = (RUNTIME / "native" / "vf2fun" / "vf2fun_sites.h").read_text()
    assert header == gen_sites.render_header()


def test_committed_stub_matches_the_stub_builder():
    assert json.loads((RUNTIME / "stub.json").read_text()) == build_stub.build()


def test_overwritten_pins_do_not_overlap_each_other():
    # A "field" pin writes only its displacement/immediate; "data" and "context" pins write nothing.
    spans = sorted((p.field_va, p.field_va + p.field[1], p.name) if p.role == "field" else (p.va, p.end, p.name)
                   for p in S.PINS if p.role not in ("context", "data"))
    for (a_lo, a_hi, a), (b_lo, b_hi, b) in zip(spans, spans[1:]):
        assert a_hi <= b_lo, f"{a} overlaps {b}"
    assert {p.role for p in S.PINS} == {"detour", "replace", "retarget", "context", "data", "field", "vtable_slot"}
    assert len([p for p in S.PINS if p.role == "retarget" and p.module == "older_pregnancies"]) == 4
    assert {p.module for p in S.PINS} <= {S.CORE} | set(S.MODULE_BY_KEY)


def _stub_instructions():
    stub = json.loads((RUNTIME / "stub.json").read_text())
    code = bytes.fromhex(stub["code"])
    code_va = int(stub["code_va"], 16)
    n = stub["code_length"]
    insns = list(_md().disasm(code[:n], code_va))
    assert sum(i.size for i in insns) == n, "stub code does not decode cleanly"
    return stub, code, code_va, insns


def test_stub_decodes_to_the_intended_loader():
    stub, code, code_va, insns = _stub_instructions()
    data_lo = int(stub["data_va"], 16)
    data_hi = data_lo + stub["data_size"]
    text = [f"{i.mnemonic} {i.op_str}".strip() for i in insns]
    # Entry: save everything, load, call startup, restore everything, go to Init.
    assert insns[0].address == int(stub["init_entry"], 16)
    assert text[:2] == ["pushfd", "pushal"] and insns[2].mnemonic == "call"
    loader = next(i for i in insns if i.address == insns[2].operands[0].imm)
    assert f"{loader.mnemonic} {loader.op_str}" == f"cmp dword ptr [{data_lo:#x}], 0"
    entry_jmp = next(i for i in insns if i.mnemonic == "jmp" and i.operands[0].type == X86_OP_IMM)
    assert entry_jmp.operands[0].imm == S.INIT_SLOT_EXPECTED
    before = insns[insns.index(entry_jmp) - 2: insns.index(entry_jmp)]
    assert [i.mnemonic for i in before] == ["popal", "popfd"]
    stub_end = code_va + stub["code_length"]
    for i in insns:
        if i.mnemonic in ("call", "jmp") or i.mnemonic.startswith("j"):
            op = i.operands[0]
            if op.type == X86_OP_IMM:
                assert code_va <= op.imm < stub_end or op.imm == S.INIT_SLOT_EXPECTED, text
            elif op.type == X86_OP_MEM:
                assert op.mem.base == 0 and op.mem.index == 0
                assert op.mem.disp in (S.IAT_GET_MODULE_HANDLE_A, S.IAT_GET_PROC_ADDRESS), f"{i.mnemonic} {i.op_str}"
            else:
                assert i.reg_name(op.reg) == "eax"  # resolved GetModuleFileNameW/LoadLibraryW/startup
        # Every absolute memory write lands in the read-write data section.
        if i.mnemonic in ("mov",) and i.operands[0].type == X86_OP_MEM:
            m = i.operands[0].mem
            if m.base == 0 and m.index == 0:
                assert data_lo <= m.disp < data_hi, f"{i.mnemonic} {i.op_str}"
    strings = code[int(stub["strings_va"], 16) - code_va:]
    assert (S.PATCHER_FOLDER + "\\" + S.DLL_NAME).encode("utf-16-le") + b"\0\0" in strings
    assert b"LoadLibraryW\0" in strings and b"GetModuleFileNameW\0" in strings
    assert b"LoadLibraryA" not in strings and b"VF2Fun_Startup\0" in strings


def _c_function(text: str, signature_regex: str) -> str:
    m = re.search(signature_regex, text)
    assert m, signature_regex
    start = text.index("{", m.end() - 1)
    depth = 0
    for k in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[k], 0)
        if depth == 0:
            return text[start:k + 1]
    raise AssertionError("unbalanced braces")


def _python_function(text: str, name: str) -> str:
    """Source of one top-level `def name(` in the B200 generator."""
    start = text.index(f"\ndef {name}(")
    end = text.find("\ndef ", start + 1)
    return text[start:end if end > 0 else len(text)]


def _normalise(body: str) -> str:
    body = re.sub(r"//[^\n]*", "", body)
    body = body.replace("VF2", "").replace("ldwGameState::GetRandom", "GetRandom")
    return re.sub(r"\s+", "", body)


@pytest.mark.parametrize("name", ["PregnancyAgeYears", "OlderPregnancyCapTenths",
                                  "StockPregnancyChanceWithoutCutoff"])
def test_dll_port_of_pure_b200_helpers_is_identical(name):
    b200 = GENERATOR.read_text(encoding="utf-8")
    dll = DLL_SOURCE.read_text(encoding="utf-8")
    original = _c_function(b200, rf"static int VF2{name}\(")
    port = _c_function(dll, rf"static int {name}\(")
    assert _normalise(original) == _normalise(port)


def test_dll_port_of_the_late_age_roll_matches_b200():
    b200 = _normalise(_c_function(GENERATOR.read_text(encoding="utf-8"),
                                  r'extern "C" int __cdecl VF2RollOlderPregnancy\('))
    port = _normalise(_c_function(DLL_SOURCE.read_text(encoding="utf-8"), r"static int RollOlderPregnancy\("))
    port = port.replace("TutorialQueue(TutorialTip,eStringPregnancyTutorial,eGameSceneNone,false);",
                        "TutorialTip.Queue(eStringPregnancyTutorial,eGameSceneNone,false);")
    assert b200 == port


# --------------------------------------------------------------- vanilla
def test_every_site_is_proved_against_the_vanilla_executable():
    facts = gen_sites.validate(vanilla_bytes())
    assert any("no direct branch lands in 0x4a0811-0x4a0817" in f for f in facts)
    assert any("direct callers of 0x48ff70: 0x430681, 0x430db8, 0x43c0bd, 0x4407dc" in f for f in facts)


def test_validation_refuses_a_shifted_or_relative_steal():
    md = _md()
    # A steal that would split an instruction or include a relative call is refused.
    with pytest.raises(gen_sites.SiteError):
        gen_sites.steal_length(md, bytes.fromhex("E800000000909090"), 0x1000)
    with pytest.raises(gen_sites.SiteError):
        gen_sites.decode_run(md, bytes.fromhex("8B5424"), 0x1000)
    assert gen_sites.steal_length(md, bytes.fromhex("535556578B5424149090"), 0x1000) == 8
    bad = bytearray(vanilla_bytes())
    off = P.PE(bytes(bad)).offset(S.COOLDOWN_STORE)
    bad[off] ^= 0xFF
    with pytest.raises(gen_sites.SiteError):
        gen_sites.validate(bytes(bad))


def test_patched_executable_differs_only_where_intended():
    vanilla = vanilla_bytes()
    patched = P.patch_executable(vanilla)
    pe = P.PE(vanilla)
    allowed = set()
    allowed.update(range(pe.nsec_off, pe.nsec_off + 2))          # NumberOfSections
    allowed.update(range(pe.opt + 56, pe.opt + 60))              # SizeOfImage
    allowed.update(range(pe.opt + 64, pe.opt + 68))              # CheckSum
    table_end = pe.opt + pe.optsz + pe.nsec * 40
    allowed.update(range(table_end, table_end + 80))             # two new section headers
    slot = pe.offset(S.INIT_SLOT)
    allowed.update(range(slot, slot + 4))                        # Init vtable slot
    diffs = {i for i in range(len(vanilla)) if vanilla[i] != patched[i]}
    assert diffs, "nothing was patched"
    assert diffs <= allowed, sorted(hex(d) for d in diffs - allowed)[:20]
    assert struct.unpack_from("<I", patched, slot)[0] == S.STUB_CODE_VA

    new = P.PE(patched)
    names = [s[0] for s in new.sections()]
    assert names[:-2] == [s[0] for s in pe.sections()]
    assert new.sections()[:-2] == pe.sections(), "an existing section header changed"
    code, data = new.sections()[-2:]
    assert code[0] == ".vf2fun" and code[5] == P.CODE_CHARACTERISTICS
    assert data[0] == ".vf2fud" and data[5] == P.DATA_CHARACTERISTICS
    assert code[5] & 0x80000000 == 0, "stub section must not be writable"
    assert data[5] & 0x20000000 == 0, "data section must not be executable"
    stub = json.loads((RUNTIME / "stub.json").read_text())
    payload = bytes.fromhex(stub["code"])
    assert patched[code[3]:code[3] + len(payload)] == payload
    assert not any(patched[data[3]:data[3] + data[4]])
    assert pe.base + code[1] == S.STUB_CODE_VA and pe.base + data[1] == S.STUB_DATA_VA
    # The appended region is exactly the two sections.
    assert len(patched) == data[3] + data[4]
    assert patched[len(vanilla):code[3]] == bytes(code[3] - len(vanilla))


def test_checksum_is_recomputed_and_matches_windows(tmp_path):
    vanilla = vanilla_bytes()
    pe = P.PE(vanilla)
    assert P.pe_checksum(vanilla, pe.opt + 64) == struct.unpack_from("<I", vanilla, pe.opt + 64)[0]
    patched = P.patch_executable(vanilla)
    stored = struct.unpack_from("<I", patched, pe.opt + 64)[0]
    assert stored == P.pe_checksum(patched, pe.opt + 64)
    if sys.platform == "win32":
        target = tmp_path / "patched.exe"
        target.write_bytes(patched)
        header, computed = ctypes.c_uint32(), ctypes.c_uint32()
        rc = ctypes.WinDLL("imagehlp").MapFileAndCheckSumW(str(target), ctypes.byref(header), ctypes.byref(computed))
        assert rc == 0
        assert header.value == computed.value == stored


def test_patcher_refuses_anything_but_vanilla():
    vanilla = vanilla_bytes()
    with pytest.raises(P.PatchError):
        P.patch_executable(vanilla[:-1] + b"\1")
    with pytest.raises(P.PatchError):
        P.patch_executable(P.patch_executable(vanilla))


def test_apply_writes_a_new_folder_and_leaves_the_source_alone(tmp_path):
    vanilla_bytes()
    game = Path(VANILLA_DIR)
    before = {p: p.stat().st_mtime_ns for p in game.rglob("*") if p.is_file()}
    fake_dll = tmp_path / "vf2fun.dll"
    fake_dll.write_bytes(b"MZ test")
    out = tmp_path / "out"
    exe = P.apply(game, out, fake_dll, {"AllowOlderPregnancies": True}, "VF2 Runtime Test.exe")
    assert exe.name == "VF2 Runtime Test.exe" and not (out / S.VANILLA_EXE_NAME).exists()
    assert (out / S.PATCHER_FOLDER / S.DLL_NAME).read_bytes() == b"MZ test"
    ini = (out / S.PATCHER_FOLDER / S.INI_NAME).read_text(encoding="utf-16")
    assert "AllowOlderPregnancies=1" in ini
    for m in S.MODULES:  # every key written explicitly; the others at the B200 default
        if not m.internal and m.ini_key != "AllowOlderPregnancies":
            assert f"{m.ini_key}={1 if m.b200_default else 0}" in ini
    assert {p: p.stat().st_mtime_ns for p in game.rglob("*") if p.is_file()} == before
    with pytest.raises(P.PatchError):
        P.apply(game, out, fake_dll, True)  # not empty
    with pytest.raises(P.PatchError):
        P.apply(game, game / "inside", fake_dll, True)


# --------------------------------------------------------------- harness
def _have_msvc() -> bool:
    return sys.platform == "win32" and Path(VCVARS).is_file()


def _run_bat(lines: list[str], cwd: Path) -> None:
    bat = cwd / "build.bat"
    bat.write_text("@echo off\r\n" + "\r\n".join(lines) + "\r\n")
    r = subprocess.run(["cmd", "/c", str(bat)], capture_output=True, text=True, cwd=cwd)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    vanilla = vanilla_bytes()
    if not _have_msvc():
        pytest.skip("Visual Studio x86 toolchain not found (set VF2_VCVARS32)")
    work = tmp_path_factory.mktemp("stage1")
    dll_src = DLL_SOURCE
    (work / "release").mkdir()
    _run_bat([
        f'call "{VCVARS}" >nul || exit /b 1',
        # Test build: the per-call counters the harness reads.
        f'cl /nologo /O2 /MT /EHsc /W4 /WX /LD /GS /DVF2FUN_TEST_COUNTERS "{dll_src}" /Fo"{work}\\\\" '
        f'/Fe"{work}\\vf2fun.dll" /link kernel32.lib /DYNAMICBASE /NXCOMPAT /MANIFEST:EMBED || exit /b 1',
        # Release build, exactly as native/build.bat makes it.
        f'cl /nologo /O2 /MT /EHsc /W4 /WX /LD /GS "{dll_src}" /Fo"{work}\\release\\\\" '
        f'/Fe"{work}\\release\\vf2fun.dll" /link kernel32.lib /DYNAMICBASE /NXCOMPAT /MANIFEST:EMBED || exit /b 1',
        f'cl /nologo /O1 /MT /W3 "{RUNTIME / "tests" / "stage1_harness.cpp"}" /Fo"{work}\\\\" '
        f'/Fe"{work}\\stage1_harness.exe" /link /BASE:0x30000000 /FIXED /DYNAMICBASE:NO kernel32.lib || exit /b 1',
    ], work)
    assert (work / "vf2fun.dll").is_file() and (work / "stage1_harness.exe").is_file()
    (work / "patched.exe").write_bytes(P.patch_executable(vanilla))
    return work


ALL_ON = {m.ini_key: True for m in S.MODULES if not m.internal}
ALL_OFF = {m.ini_key: False for m in S.MODULES if not m.internal}
SETTINGS = {"on": ALL_ON, "off": ALL_OFF}


def _harness(built: Path, setting, with_dll: bool = True, dll: Path | None = None, tag: str = "") -> list[dict]:
    """setting: "on" (every module), "off" (none), None (no ini) or a dict."""
    name = setting if isinstance(setting, (str, type(None))) else "custom"
    run = built / f"run-{name}-{with_dll}{tag}"
    if run.exists():
        shutil.rmtree(run)
    run.mkdir()
    shutil.copy2(built / "stage1_harness.exe", run)
    files = run / S.PATCHER_FOLDER
    files.mkdir()
    if with_dll:
        shutil.copy2(dll or built / "vf2fun.dll", files / S.DLL_NAME)
    if setting is not None:
        P.write_settings(files / S.INI_NAME, SETTINGS.get(setting, setting) if isinstance(setting, str) else setting)
    r = subprocess.run([str(run / "stage1_harness.exe"), str(built / "patched.exe")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr
    rows = [json.loads(line) for line in r.stdout.splitlines() if line.strip()]
    assert "fatal" not in rows[-1]
    return rows


@pytest.fixture(scope="module")
def on(built):
    return _harness(built, "on")


@pytest.fixture(scope="module")
def off(built):
    return _harness(built, "off")


def _one(rows, key):
    found = [r for r in rows if key in r]
    assert len(found) == 1, key
    return found[0][key] if not isinstance(found[0][key], (int, str)) else found[0]


def test_missing_dll_is_the_stock_game(built):
    rows = _harness(built, None, with_dll=False)
    boot = _one(rows, "bootstrap")
    assert boot["dll_loaded"] == 0 and boot["stub_state"] == 2
    assert boot["init_calls"] == 1 and boot["init_this_ok"] == 1 and boot["init_result"] == 1


def test_bootstrap_loads_the_dll_by_full_path_then_runs_init(on):
    boot = _one(on, "bootstrap")
    assert boot["slot"] == S.STUB_CODE_VA
    assert boot["stub_state"] == 1 and boot["dll_loaded"] == 1
    assert boot["dll_path"].endswith(f"/{S.PATCHER_FOLDER}/{S.DLL_NAME}")
    assert boot["init_calls"] == 1 and boot["init_this_ok"] == 1 and boot["init_result"] == 1


def _expected_protect(va):
    """Game code is read-execute; a vtable (data) page is read-only. Never writable."""
    return "R" if any(p.va == va and p.role == "vtable_slot" for p in S.PINS) else "RX"


def _sites(rows):
    return {r["site"]: r for r in rows if "site" in r and "bytes" in r}


ALL_MODULES_MASK = (1 << len(S.MODULES)) - 1


def test_setting_off_writes_nothing(off):
    status = _one(off, "status")
    assert status["magic"] == 0x53324656 and status["version"] == 2 and status["modules"] == len(S.MODULES)
    assert status["requested"] == 0 and status["installed"] == 0 and status["trampoline"] == 0
    assert not any(status["write_masks"])
    for va, row in _sites(off).items():
        pin = next(p for p in S.PINS if p.va == va and p.role not in ("context", "data"))
        assert bytes.fromhex(row["bytes"]) == pin.expected
        assert row["protect"] == _expected_protect(va)
    assert _one(off, "wx_regions")["wx_regions"] == 0


def test_installed_bytes_trampoline_and_protections(on):
    status = _one(on, "status")
    assert status["requested"] == status["pins_ok"] == status["installed"] == ALL_MODULES_MASK
    assert status["refused"] == 0
    assert status["write_masks"][0] == 0b111111  # older_pregnancies: 6 writes
    lo, hi = status["dll_lo"], status["dll_hi"]
    sites = _sites(on)
    md = _md()

    def decoded(va):
        b = bytes.fromhex(sites[va]["bytes"])
        return list(md.disasm(b, va)), b

    insns, raw = decoded(S.CHANCE_OF_PREGNANCY)
    assert insns[0].mnemonic == "jmp" and lo <= insns[0].operands[0].imm < hi
    assert raw[5:] == b"\x90\x90\x90"
    insns, raw = decoded(S.COOLDOWN_STORE)
    assert insns[0].mnemonic == "jmp" and lo <= insns[0].operands[0].imm < hi
    assert raw[5:] == b"\x90"
    targets = set()
    for site in S.NEXT_GENERATION_CALLSITES:
        insns, raw = decoded(site)
        assert len(insns) == 1 and insns[0].mnemonic == "call"
        targets.add(insns[0].operands[0].imm)
    assert len(targets) == 1 and lo <= targets.pop() < hi
    for va, row in sites.items():
        assert row["protect"] == _expected_protect(va), "game code left writable"

    tramp = _one(on, "trampoline")
    t = tramp["trampoline"]
    assert t == status["trampoline"] and not (lo <= t < hi)
    assert tramp["protect"] == "RX"
    code = list(md.disasm(bytes.fromhex(tramp["bytes"])[:13], t))
    assert bytes.fromhex(tramp["bytes"])[:8] == S.PIN_BY_NAME["chance_entry"].expected
    assert [i.mnemonic for i in code] == ["push", "push", "push", "push", "mov", "jmp"]
    assert code[-1].operands[0].imm == S.CHANCE_OF_PREGNANCY + S.CHANCE_OF_PREGNANCY_STEAL
    assert _one(on, "wx_regions")["wx_regions"] == 0


def _chance_rows(rows):
    return {tuple(r["chance"]): r for r in rows if "chance" in r}


def b200_older_roll(mother_age, father_age, mother_fert, father_fert, rnd):
    """B200's VF2RollOlderPregnancy (work/patch_mobile_furniture_pack.py)."""
    my, fy = mother_age // 20, father_age // 20
    older = max(my, fy)
    if older < 50:
        return 0, False
    chance = 105 - (100 - mother_fert) // 3 - (100 - father_fert) // 3
    if fy >= 41:
        chance -= (fy - 40) // 5
    if my > 30:
        chance -= 2 * (my - 20)
    tenths = chance * 10
    cap = (60 - older) * 10 if older <= 59 else (69 - older if older <= 68 else 1)
    tenths = max(1, min(tenths, cap))
    return (1 if rnd < tenths else 0), True


def test_young_couples_get_the_untouched_stock_answer(on, off):
    a, b = _chance_rows(on), _chance_rows(off)
    young = [k for k in b if k[0] < 1000 and k[1] < 1000]
    assert len(young) > 100
    for k in young:
        for field in ("result", "random_calls", "random_limit", "queue_calls", "queue"):
            assert a[k][field] == b[k][field], (k, field, a[k], b[k])
        assert b[k]["random_limit"] == 100  # the stock body ran
    # Both stock outcomes occur: a failed roll after the pregnancy tutorial was
    # already shown (the last key field) refuses; before that stock forces a
    # success and queues the tutorial.
    shown = [k for k in young if k[5] == 1]
    assert any(b[k]["result"] for k in shown) and not all(b[k]["result"] for k in shown)
    assert all(b[k]["result"] == 1 for k in young if k[5] == 0)


def test_older_couples_follow_the_b200_late_age_roll(on, off):
    a, b = _chance_rows(on), _chance_rows(off)
    older = [k for k in a if k[0] >= 1000 or k[1] >= 1000]
    assert len(older) > 1000
    successes = 0
    for k in older:
        expected, rolled = b200_older_roll(*k[:5])
        assert rolled
        row = a[k]
        assert row["result"] == expected, (k, row)
        assert row["random_calls"] == 1 and row["random_limit"] == 1000
        if expected:
            successes += 1
            assert row["queue_calls"] == 1 and row["queue"] == [0x868, 0, 0]
            assert row["queue_this"] == S.TUTORIAL_TIP
        else:
            assert row["queue_calls"] == 0
    assert 0 < successes < len(older)
    # And the feature really changes something: stock refuses a mother of 50+.
    assert any(a[k]["result"] != b[k]["result"] for k in older)


def test_cooldown_store_matches_b200(on, off):
    deadline = 0x12345678
    on_rows = {tuple(r["cooldown"]): r for r in on if "cooldown" in r}
    off_rows = {tuple(r["cooldown"]): r for r in off if "cooldown" in r}
    assert len(on_rows) == len(off_rows) == 5
    for ages, row in on_rows.items():
        older = ages[0] >= 1000 or ages[1] >= 1000
        assert row["deadline"] == (0xDDDDDDDD if older else deadline), (ages, row)
        assert row["regs_same"] == row["flags_same"] == row["esp_same"] == 1
        assert off_rows[ages]["deadline"] == deadline  # stock always writes it
        assert off_rows[ages]["regs_same"] == 1


NEXT_GENERATION_EXPECTED_ON = {
    "stock_yes": 1, "no_children": 0, "dead_child": 0, "oldest_59": 0, "oldest_60": 1,
    "oldest_60_left_home": 0, "oldest_60_dead": 0, "oldest_60_force": 1,
}


def test_next_generation_wrapper_matches_b200(on, off):
    on_rows = [r for r in on if "next_generation" in r]
    off_rows = [r for r in off if "next_generation" in r]
    assert len(on_rows) == len(off_rows) == 32
    for r in on_rows:
        assert r["result"] == NEXT_GENERATION_EXPECTED_ON[r["next_generation"]], r
        assert r["target"] != S.CAN_START_NEXT_GENERATION
    for r in off_rows:
        assert r["target"] == S.CAN_START_NEXT_GENERATION
        assert r["result"] == (1 if r["next_generation"] == "stock_yes" else 0), r


def test_live_probe_reads_a_running_patched_image(built, on):
    """The read-only probe the live test uses, run against a held harness."""
    sys.path.insert(0, str(RUNTIME / "tools"))
    import probe_stage1

    run = built / "run-probe"
    if run.exists():
        shutil.rmtree(run)
    run.mkdir()
    shutil.copy2(built / "stage1_harness.exe", run)
    files = run / S.PATCHER_FOLDER
    files.mkdir()
    shutil.copy2(built / "vf2fun.dll", files / S.DLL_NAME)
    P.write_settings(files / S.INI_NAME, ALL_ON)
    proc = subprocess.Popen([str(run / "stage1_harness.exe"), str(built / "patched.exe"), "--hold"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        rows = []
        for line in proc.stdout:
            rows.append(json.loads(line))
            if "holding" in rows[-1] or "fatal" in rows[-1]:
                break
        assert "holding" in rows[-1], rows[-1]
        snap = probe_stage1.snapshot(probe_stage1.Process(rows[-1]["holding"]))
    finally:
        proc.stdin.close()
        proc.wait(timeout=60)
        proc.stdout.close()
    status_row = next(r["status"] for r in rows if "status" in r)
    counters = next(r["counters"] for r in rows if "counters" in r)
    assert snap["stub"]["state"] == "DLL loaded"
    assert snap["stub"]["dll_path"].endswith("\\" + S.PATCHER_FOLDER + "\\" + S.DLL_NAME)
    assert int(snap["stub"]["module"], 16) == status_row["dll_lo"]
    assert probe_stage1.export_rva(Path(snap["stub"]["dll_path"]), "VF2Fun_Status") == \
        status_row["status_va"] - status_row["dll_lo"]
    status = snap["status"]
    assert status["magic"] == 0x53324656 and status["version"] == 2
    assert status["installedMask"] == ALL_MODULES_MASK and status["trampolinePage"] == status_row["trampoline"]
    assert status["modules"] == {m.key: "installed" for m in S.MODULES}
    tc = snap["counters"]
    assert tc["chanceCalls"] == counters["chance"] and tc["olderRolls"] == counters["older_rolls"]
    assert tc["cooldownSkips"] == counters["cooldown_skips"] == 3
    assert tc["sceneNullSkips"] == counters["scene_null_skips"] == 2
    assert all("vanilla" not in line for line in snap["sites"].values())
    assert snap["family_tree_generation"] == 3
    elder = next(v for v in snap["villagers"] if v["index"] == 0)
    assert {k: elder[k] for k in ("gender", "internal_age", "years", "health", "departed")} == \
        {"gender": "male", "internal_age": 1200, "years": 60, "health": 1, "departed": 0}
    assert elder["fertility"] == 0  # the harness never set villager 0's fertility
    assert "try_for_baby" not in snap  # the harness has no theGameState


# =============================================================== S0: host registry
def _module_bit(key: str) -> int:
    return 1 << [m.key for m in S.MODULES].index(key)


def test_release_build_has_the_status_block_but_no_test_counters(built):
    release = built / "release" / "vf2fun.dll"
    sys.path.insert(0, str(RUNTIME / "tools"))
    import probe_stage1
    assert probe_stage1.export_rva(release, "VF2Fun_Status")
    with pytest.raises(KeyError):
        probe_stage1.export_rva(release, "VF2Fun_TestCounters")
    assert probe_stage1.export_rva(built / "vf2fun.dll", "VF2Fun_TestCounters")
    # native/build.bat (the release build) never defines the test flag.
    assert "VF2FUN_TEST_COUNTERS" not in (RUNTIME / "native" / "build.bat").read_text()
    # The release DLL still installs and runs: the harness reads its status
    # block (counters are reported as absent).
    rows = _harness(built, "on", dll=release, tag="-release")
    status = _one(rows, "status")
    assert status["installed"] == ALL_MODULES_MASK and status["refused"] == 0


def test_every_counter_use_is_compiled_out_of_release_builds():
    src = DLL_SOURCE.read_text(encoding="utf-8")
    # The only references to the counters export are inside #ifdef VF2FUN_TEST_COUNTERS.
    depth, inside = 0, False
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("#ifdef VF2FUN_TEST_COUNTERS"):
            inside, depth = True, 1
            continue
        if inside and s.startswith("#if"):
            depth += 1
        elif inside and s.startswith("#endif"):
            depth -= 1
            if depth == 0:
                inside = False
            continue
        elif inside and s.startswith("#else") and depth == 1:
            inside = False
            continue
        if not inside:
            assert "VF2Fun_TestCounters" not in line, line


def test_modules_install_independently(built):
    """Each module alone installs only its own writes; the others stay vanilla."""
    for m in S.MODULES:
        if m.internal:
            continue  # shared infrastructure: it installs with the modules that require it
        rows = _harness(built, {k.ini_key: k is m for k in S.MODULES if not k.internal}, tag=f"-{m.key}")
        status = _one(rows, "status")
        bit = _module_bit(m.key) | sum(_module_bit(r) for r in m.requires)
        assert status["requested"] == status["installed"] == bit, (m.key, status)
        sites = _sites(rows)
        for pin in S.PINS:
            if pin.role in ("context", "data") or pin.va not in sites:
                continue
            live = bytes.fromhex(sites[pin.va]["bytes"])
            assert (live != pin.expected) == (pin.module == m.key or pin.module in m.requires), (m.key, pin.name)
        assert _one(rows, "wx_regions")["wx_regions"] == 0


def test_corrupted_module_pin_refuses_only_that_module(built, tmp_path):
    """Per-module all-or-nothing: a patched image whose scene_null_guard
    context pin is off by one byte installs every other module, and leaves
    every scene_null_guard site vanilla."""
    vanilla = vanilla_bytes()
    patched = bytearray(P.patch_executable(vanilla))
    pe = P.PE(bytes(patched))
    # One byte inside the pinned SetActive body that is NOT written by the
    # module (the trailing `ret 4` immediate), so only the pin check differs.
    off = pe.offset(S.SCENE_SET_ACTIVE + len(S.PIN_BY_NAME["scene_set_active"].expected) - 2)
    patched[off] ^= 0x01
    work = built / "corrupt"
    work.mkdir(exist_ok=True)
    (work / "patched.exe").write_bytes(bytes(patched))
    shutil.copy2(built / "stage1_harness.exe", work)
    shutil.copy2(built / "vf2fun.dll", work)
    run = work / "run"
    if run.exists():
        shutil.rmtree(run)
    run.mkdir()
    shutil.copy2(built / "stage1_harness.exe", run)
    (run / S.PATCHER_FOLDER).mkdir()
    shutil.copy2(built / "vf2fun.dll", run / S.PATCHER_FOLDER / S.DLL_NAME)
    P.write_settings(run / S.PATCHER_FOLDER / S.INI_NAME, ALL_ON)
    r = subprocess.run([str(run / "stage1_harness.exe"), str(work / "patched.exe"), "--status-only"],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr
    rows = [json.loads(line) for line in r.stdout.splitlines() if line.strip()]
    status = _one(rows, "status")
    bit = _module_bit("scene_null_guard")
    assert status["refused"] == bit and status["pins_ok"] & bit == 0
    assert status["installed"] == ALL_MODULES_MASK & ~bit
    sites = _sites(rows)
    assert bytes.fromhex(sites[S.SCENE_ACTIVE_WRITE]["bytes"]) == S.PIN_BY_NAME["scene_active_write"].expected
    assert bytes.fromhex(sites[S.CHANCE_OF_PREGNANCY]["bytes"]) != S.PIN_BY_NAME["chance_entry"].expected


# =============================================================== scene_null_guard
def _set_active_rows(rows):
    return {tuple(r["set_active"]): r for r in rows if "set_active" in r}


def test_scene_null_guard_site_is_the_b200_hook():
    """B200 hooks `mov eax,[esi+4]; mov [eax],bl` in ldwScene::SetActive; the
    vanilla pin is those same two instructions."""
    b200 = GENERATOR.read_text(encoding="utf-8")
    body = _python_function(b200, "patch_ldwscene_setactive_null_guard")
    assert 'bytes.fromhex("8B4604 8818"' in body
    assert S.PIN_BY_NAME["scene_active_write"].expected == bytes.fromhex("8B46048818")
    assert body.count("pop esi; pop ebx; ret 4") or "\\x5E\\x5B\\x5D\\xC2\\x04\\x00" in body


def test_scene_null_guard_bound_scenes_are_unchanged(on, off):
    a, b = _set_active_rows(on), _set_active_rows(off)
    assert len(a) == len(b) == 4
    for arg in (1, 0):
        k = (1, arg)
        for field in ("crashed", "flag", "subscribe", "unsubscribe", "handler_ok", "manager_ok",
                      "activate_controls", "activate_arg", "virtual", "virtual_arg", "last_cleared",
                      "esp_delta"):
            assert a[k][field] == b[k][field], (k, field, a[k], b[k])
        assert b[k]["crashed"] == 0 and b[k]["flag"] == arg and b[k]["esp_delta"] == 0
        assert b[k]["activate_controls"] == b[k]["virtual"] == 1
        assert b[k]["activate_arg"] == b[k]["virtual_arg"] == arg
    # Stock branch on the argument still taken correctly (the stub keeps flags).
    assert a[(1, 1)]["subscribe"] == 1 and a[(1, 1)]["unsubscribe"] == 0
    assert a[(1, 0)]["subscribe"] == 0 and a[(1, 0)]["unsubscribe"] == 1
    assert a[(1, 0)]["last_cleared"] == 1 and a[(1, 1)]["last_cleared"] == 0


def test_scene_null_guard_null_flag_returns_instead_of_crashing(on, off):
    a, b = _set_active_rows(on), _set_active_rows(off)
    for arg in (1, 0):
        k = (0, arg)
        assert b[k]["crashed"] == 1  # stock: access violation on the null write
        row = a[k]
        assert row["crashed"] == 0 and row["esp_delta"] == 0
        # B200: return through the function's own epilogue, nothing else runs.
        assert row["subscribe"] == row["unsubscribe"] == row["activate_controls"] == row["virtual"] == 0
        assert row["last_cleared"] == 0
    counters = _one(on, "counters")
    assert counters["scene_null_skips"] == 2 and counters["scene_writes"] == 2


# =============================================================== fix_vanilla_bugs
def _b200_constant(name: str) -> int:
    m = re.search(rf"^{name}\s*=\s*(0x[0-9A-Fa-f]+|\d+)", GENERATOR.read_text(encoding="utf-8"), re.M)
    assert m, name
    return int(m.group(1), 0)


def test_pause_yes_rule_is_b200s():
    """B200's stub: cmp [eax+25B18h],3E7h; jge resume; add [eax+25B18h],3E7h."""
    body = _python_function(GENERATOR.read_text(encoding="utf-8"), "patch_options_pause_yes_idempotent")
    assert '"\\x81\\xB8\\x18\\x5B\\x02\\x00\\xE7\\x03\\x00\\x00"' in body  # cmp [eax+25B18h],3E7h
    assert '"\\x0F\\x8D" + disp(0x13, 6, PAUSE_YES_RESUME_OFFSET)' in body  # jge (signed) past the add
    assert '"\\x81\\x80\\x18\\x5B\\x02\\x00\\xE7\\x03\\x00\\x00"' in body  # add [eax+25B18h],3E7h
    src = DLL_SOURCE.read_text(encoding="utf-8")
    stub = src[src.index("static __declspec(naked) void PauseYesStub()"):]
    stub = stub[:stub.index("}\n}") + 3]
    assert "cmp dword ptr [esi + 0x25B18], 0x3E7" in stub and "jge already_paused" in stub
    assert "add dword ptr [esi + 0x25B18], 0x3E7" in stub


def test_pause_yes_adds_999_only_when_not_paused(on, off):
    a = {r["pause_yes"]: r for r in on if "pause_yes" in r}
    b = {r["pause_yes"]: r for r in off if "pause_yes" in r}
    assert len(a) == len(b) == 8
    for value in a:
        assert b[value]["after"] == value + 999                     # stock: always adds
        expected = value if value >= 999 else value + 999          # B200 rule (signed)
        assert a[value]["after"] == expected, (value, a[value])
        assert a[value]["regs_same"] == a[value]["esp_same"] == 1
    assert a[2008]["after"] == 2008 and b[1009]["after"] == 2008  # the reported defect


def test_title_hotspot_rect_is_empty_like_b200(on, off):
    assert _b200_constant("TITLE_HOTSPOT_STOCK_TOP") == S.TITLE_HOTSPOT_STOCK_TOP
    assert _b200_constant("TITLE_HOTSPOT_BOTTOM") == S.TITLE_HOTSPOT_BOTTOM
    a = next(r for r in on if "title_hotspot" in r)
    b = next(r for r in off if "title_hotspot" in r)
    assert b["top"] == S.TITLE_HOTSPOT_STOCK_TOP and b["inside"] > 0
    assert (b["first_y"], b["last_y"]) == (S.TITLE_HOTSPOT_STOCK_TOP, S.TITLE_HOTSPOT_BOTTOM)
    assert a["top"] == S.TITLE_HOTSPOT_BOTTOM + 1 and a["inside"] == 0  # B200's empty rect
    for row in (a, b):
        assert row["regs_same"] == row["flags_same"] == row["esp_same"] == 1


# =============================================================== career_room_goals
# The stock CTech::Level (Tech.obj, which B200 links): per tech, the
# upgrade items it counts and the goal it rebuilds.
TECH_ITEMS = {0: (range(0xF6, 0x100), 0x36), 1: (range(0xEB, 0xF6), 0x37), 2: (range(0x100, 0x10A), 0x38)}


def _owned(case: int) -> set[int]:
    items = range(0xEB, 0x10A)
    return {
        0: set(),
        1: set(items),
        2: {0xF6},
        3: {i for i in items if i <= 0xEE or 0x100 <= i <= 0x105},
        4: {i for i in items if (i * 7 + 3) % 5 < 2},
        5: set(items),
    }[case]


def b200_reconcile_events(owned: set[int]) -> list[list]:
    """B200 VF2ReconcileCareerRoomGoals: Level(kitchen), Level(office),
    Level(workshop), each the stock routine's achievement calls."""
    out = []
    for tech in (0, 1, 2):  # eTechKitchen, eTechOffice, eTechWorkshop
        items, goal = TECH_ITEMS[tech]
        count = sum(1 for i in items if i in owned)
        out.append(["reset", goal, 1])
        out.append(["increment", goal, min(count, 10)])
        if count:
            out.append(["increment", 0x35, 1])
    return out


def test_career_room_wrapper_is_b200s():
    b200 = GENERATOR.read_text(encoding="utf-8")
    src = DLL_SOURCE.read_text(encoding="utf-8")
    original = _normalise(_c_function(b200, r"static void VF2ReconcileCareerRoomGoals\("))
    mine = _normalise(_c_function(src, r"static void ReconcileCareerRoomGoals\("))
    assert mine.replace("TechLevel(Tech,", "Tech.Level(") == original
    original = _normalise(_c_function(b200, r'extern "C" bool __fastcall VF2TechLoadStateAndReconcile\('))
    mine = _normalise(_c_function(src, r"static bool __fastcall TechLoadStateAndReconcile\("))
    assert mine.replace("NativeTechLoadState(tech,state)", "tech->LoadState(state)") == original


def test_career_room_goals_rebuilt_on_load_like_b200(on, off):
    a = {r["tech_load"]: r for r in on if "tech_load" in r}
    b = {r["tech_load"]: r for r in off if "tech_load" in r}
    assert len(a) == len(b) == 6
    for case in range(6):
        assert b[case]["target"] == S.TECH_LOAD_STATE and b[case]["events"] == []  # stock: load only
        assert a[case]["target"] != S.TECH_LOAD_STATE
        assert a[case]["loaded"] == b[case]["loaded"] == (0 if case == 5 else 1)
        expected = [] if case == 5 else b200_reconcile_events(_owned(case))
        assert a[case]["events"] == expected, (case, a[case]["events"])
    # The office of the future case from the owner's report: everything owned
    # completes all three goals (10 = the goal's target).
    assert [e for e in a[1]["events"] if e[0] == "increment" and e[1] != 0x35] == \
        [["increment", 0x36, 10], ["increment", 0x37, 10], ["increment", 0x38, 10]]


# =============================================================== time_controls
# NEW in the runtime build: the Virtual Families 1 patcher's Time Controls
# dialog, opened from a button on the store screen. There is no B200 code to
# compare with; the references are the vanilla game's own code (decoded from
# the pinned bytes) and the stock functions the harness runs.
TIME_DIALOG_CONTROLS = [[561, "Pause"], [562, "Resume"], [563, "Normal"], [564, "2x"], [565, "5x"],
                        [566, "10x"], [567, "Time Warp: +3 years"], [1, "Close"]]
TIME_WARP_QUESTION = ("Everyone at home ages at once, with every normal rule: birthdays, leaving home, "
                      "and old age. Continue?")


def _calls(insns):
    return [i.operands[0].imm for i in insns if i.mnemonic == "call" and i.operands[0].type == X86_OP_IMM]


def _decode_pin(name: str):
    pin = S.PIN_BY_NAME[name]
    return list(_md().disasm(pin.expected, pin.va))


def _insn_text(insns) -> str:
    return "\n".join(f"{i.mnemonic} {i.op_str}" for i in insns)


def test_time_controls_module_is_registered_and_off_by_default():
    m = S.MODULE_BY_KEY["time_controls"]
    assert m.ini_key == "TimeControls" and m.b200_default is False
    written = {p.name for p in S.PINS if p.role in ("detour", "replace", "retarget") and p.module == "time_controls"}
    assert written == {"store_ctor_category_call", "store_handle_message_entry", "timeflow_ticks_site"}


def test_time_controls_sites_are_proved_against_the_vanilla_game():
    facts = gen_sites.validate(vanilla_bytes())
    assert any("store_handle_message_entry: no direct branch lands in 0x4322b1-0x4322b6" in f for f in facts)
    assert any("timeflow_ticks_site: no direct branch lands in 0x499894-0x499897" in f for f in facts)
    assert any("store_ctor_category_call: no direct branch lands in 0x4332a6-0x4332a9" in f for f in facts)


def test_time_controls_game_functions_are_the_ones_the_stores_constructor_calls():
    """Every game function the module calls is called, with the same argument
    shapes, by the stock constructor it copies the Done / Back buttons from."""
    vanilla_bytes()
    insns = _decode_pin("store_ctor")
    calls = set(_calls(insns))
    for name in ("GAME_NEW", "GRAPHICS_GET", "GRAPHICS_GET_IMAGE_GRID", "STRING_GET", "STRING_GET_LARGE_FONT",
                 "BUTTON_CTOR", "BUTTON_SET_TEXT", "SCENE_ADD_CONTROL", "STORE_SET_CATEGORY"):
        assert getattr(S, name) in calls, name
    pushes = [i.operands[0].imm for i in insns if i.mnemonic == "push" and i.operands[0].type == X86_OP_IMM]
    assert pushes.count(S.BUTTON_IMAGE) == 2                       # Done and Back use btn_orange.png
    # Done (id 1) and Back (id 3) sit at widescreenOffset + 0x10 / + 0xBA, y 0x2DD.
    text = _insn_text(insns)
    assert "add eax, 0x10" in text and "add eax, 0xba" in text and "mov ecx, 0x2dd" in text
    assert S.STORE_TIME_BUTTON_X == 0xBA + 0xAA and S.STORE_TIME_BUTTON_Y == 0x2DD
    # The widescreen offset the scene keeps at +0xE0.
    assert f"mov dword ptr [esi + {S.STORE_WIDESCREEN_OFFSET_FIELD:#x}], eax" in text
    # The button id is not one the stock handler knows (it compares with 1, 2 and 3).
    assert 0x5646 not in pushes
    # Only the constructor's final call is retargeted: `push 2; ...; call SetStoreCategory`.
    call = next(i for i in insns if i.address == S.STORE_CTOR_SET_CATEGORY_CALL)
    assert call.mnemonic == "call" and call.operands[0].imm == S.STORE_SET_CATEGORY
    k = insns.index(call)
    assert (insns[k - 5].mnemonic, insns[k - 5].op_str) == ("push", "2") and insns[k - 4].op_str == "ecx, esi"
    assert insns[k + 1].op_str == "eax, esi" and insns[-1].mnemonic == "ret"  # then returns `this`


def test_time_controls_store_handler_is_vtable_slot_3_and_takes_message_8():
    vanilla = vanilla_bytes()
    pe = P.PE(vanilla)
    slot = struct.unpack_from("<I", vanilla, pe.offset(S.STORE_VTABLE + 3 * 4))[0]
    assert slot == S.STORE_HANDLE_MESSAGE
    # RTTI: the complete object locator's type descriptor names CScrollingStoreScene.
    col = struct.unpack_from("<I", vanilla, pe.offset(S.STORE_VTABLE - 4))[0]
    td = struct.unpack_from("<I", vanilla, pe.offset(col + 12))[0]
    name_at = pe.offset(td + 8)
    assert vanilla[name_at:name_at + 27] == b".?AVCScrollingStoreScene@@\0"
    text = _insn_text(_decode_pin("store_handle_message"))
    assert "cmp dword ptr [esp + 0xb8], 8" in text and "cmp eax, 1" in text
    assert S.MESSAGE_BUTTON_CLICKED == 8


def test_time_controls_speed_model_is_the_space_keys():
    """The Space handler's own instructions, decoded from the vanilla bytes."""
    insns = _decode_pin("space_pause_toggle")
    text = _insn_text(insns)
    assert f"mov eax, dword ptr [eax + {S.PAUSE_FIELD:#x}]" in text and "cmp eax, 0x3e7" in text
    assert "add eax, 0xfffffc19" in text                      # field - 999
    assert text.count(f"mov ecx, {S.GAME_TIME:#x}") == 2
    assert f"add dword ptr [esi + {S.PAUSE_FIELD:#x}], 0x3e7" in text
    assert _calls(insns).count(S.SET_SPEED) == 2 and len(_calls(insns)) == 3  # + the pause-overlay refresh
    assert S.PAUSE_FIELD == S.GAME_STATE_SPEED_FIELD and S.PAUSED_OFFSET == 999 and S.SPEED_NORMAL == 10


def test_time_controls_warp_site_feeds_the_games_own_increment_age():
    insns = _decode_pin("timeflow_ticks")
    text = _insn_text(insns)
    assert f"div dword ptr [ecx + {S.PAUSE_FIELD:#x}]" in text        # ticks = ... / speed
    assert next(i for i in insns if i.address == S.WARP_SITE).mnemonic == "mov"
    last = insns[-1]
    assert last.address == S.WARP_RESUME and last.mnemonic == "call" and last.operands[0].imm == S.INCREMENT_AGE
    assert S.PIN_BY_NAME["timeflow_ticks_site"].expected == bytes.fromhex("8BCF8BD853")  # mov ecx,edi; mov ebx,eax; push ebx
    assert [f"{i.mnemonic} {i.op_str}" for i in _decode_pin("increment_age")] == \
        ["mov eax, dword ptr [esp + 4]", "add dword ptr [ecx], eax", "ret 4"]
    assert S.TICKS_PER_YEAR == 20 and 380 // S.TICKS_PER_YEAR == 19


def test_time_controls_release_build_has_no_test_exports(built):
    sys.path.insert(0, str(RUNTIME / "tools"))
    import probe_stage1
    for name in ("VF2Fun_TestTime", "VF2Fun_TestShowTime"):
        assert probe_stage1.export_rva(built / "vf2fun.dll", name)
        with pytest.raises(KeyError):
            probe_stage1.export_rva(built / "release" / "vf2fun.dll", name)


def test_time_controls_writes_exactly_its_three_sites(built):
    rows = _harness(built, {k.ini_key: k.key == "time_controls" for k in S.MODULES if not k.internal}, tag="-time")
    status = _one(rows, "status")
    bit = _module_bit("time_controls")
    assert status["installed"] == bit
    assert status["write_masks"][[m.key for m in S.MODULES].index("time_controls")] == 0b111
    sites = _sites(rows)
    md = _md()
    lo, hi = status["dll_lo"], status["dll_hi"]
    entry = bytes.fromhex(sites[S.STORE_HANDLE_MESSAGE]["bytes"])
    jmp = next(md.disasm(entry, S.STORE_HANDLE_MESSAGE))
    assert jmp.mnemonic == "jmp" and lo <= jmp.operands[0].imm < hi and entry[5:] == b"\x90\x90"
    call = next(md.disasm(bytes.fromhex(sites[S.STORE_CTOR_SET_CATEGORY_CALL]["bytes"]),
                          S.STORE_CTOR_SET_CATEGORY_CALL))
    assert call.mnemonic == "call" and lo <= call.operands[0].imm < hi
    warp = next(md.disasm(bytes.fromhex(sites[S.WARP_SITE]["bytes"]), S.WARP_SITE))
    assert warp.mnemonic == "jmp" and warp.size == 5 and lo <= warp.operands[0].imm < hi
    for va, row in sites.items():
        assert row["protect"] == _expected_protect(va)
    # The trampoline the handler's stolen prologue runs through.
    tramp = _one(rows, "trampoline")
    code = list(md.disasm(bytes.fromhex(tramp["bytes"])[:12], tramp["trampoline"]))
    assert [f"{i.mnemonic} {i.op_str}" for i in code[:2]] == ["push -1", "push 0x4dbc8b"]
    assert code[2].mnemonic == "jmp" and code[2].operands[0].imm == S.STORE_HANDLE_MESSAGE + 7
    assert _one(rows, "wx_regions")["wx_regions"] == 0


def _model_speed_rows():
    """Stock behaviour: CGameTime::SetSpeed(999) stores 0 (paused), any other
    value stores itself, and an unchanged speed returns early; Space-style
    pause and resume on the field in theGameState."""
    f, g = 10, 10

    def set_speed(s):
        nonlocal g
        if s == g:
            return
        g = 0 if s == 999 else s

    rows = []
    script = [(1, 0), (1, 0), (2, 0), (2, 0), (3, 5), (1, 0), (3, 2), (2, 0), (3, 1), (1, 0), (3, 10), (2, 0),
              (3, 1), (3, 10)]
    for op, arg in script:
        if op == 1 and f < 999:
            set_speed(999)
            f += 999
        elif op == 2 and f >= 999:
            s = f - 999 or 10
            set_speed(s)
            f = s
        elif op == 3:
            if f >= 999:
                f = 999 + arg
            else:
                set_speed(arg)
                f = arg
        rows.append([op, arg, f, g])
    rows.append([2, -1, 10, 10])  # the exactly-999 edge (stock Space would SetSpeed(0))
    return rows


def test_time_controls_pause_and_speed_follow_the_stock_rules(on):
    assert _one(on, "time_speed") == _model_speed_rows()


def _ages_after_warp(case: int, installed: bool):
    """Stock aging for the harness villagers: ticks = accumulator / 60 / speed."""
    native = 1300 // 60 // 10                                  # 2 native ticks for villager 0
    base = [400 + native, 100, 500, 0, 300, 0]
    warp = 60 if installed else 0
    if case == 1:
        base[0] += warp                                        # B died after the warp was queued
    if case == 2:
        base[0] += warp
        base[1] += warp
        base[5] = 350 + warp
    return base


@pytest.mark.parametrize("case", [0, 1, 2])
def test_time_controls_warp_adds_ticks_through_the_games_own_aging(on, off, case):
    for rows, installed in ((on, True), (off, False)):
        row = next(r for r in rows if r.get("time_warp") == case)
        expected = _ages_after_warp(case, installed)
        assert row["ages1"] == expected, (case, installed, row)
        assert row["ages2"] == expected                          # the ticks are given once
        # The accumulator remainder uses the NATIVE ticks, never the warped ones.
        assert row["remainder"] == [100, 100]
        assert row["oldest"] == expected[0] // 20
        if installed and case:
            assert row["pending_after"] == [0, 0]
    if case == 2:
        on_row = next(r for r in on if r.get("time_warp") == 2)
        off_row = next(r for r in off if r.get("time_warp") == 2)
        # Villager 5 turns 19 only with the warp: leaving home still runs.
        assert (on_row["left_home_calls"], on_row["left_home_ok"], on_row["forget"], on_row["queued"],
                on_row["college"]) == (1, 1, 1, 1, 1)
        assert off_row["left_home_calls"] == 0 and off_row["pending_after"] == [3, 3]  # queued, never used
        assert _one(on, "time_warp_nobody")["time_warp_nobody"] == 0
        assert _one(on, "counters")["time_warps"] == 1 + 3 + 2  # case 1, case 2, the dialog script's Yes


def test_time_controls_store_button_is_the_stores_own_art_next_to_back(on, off):
    row = _one(on, "store_ctor")
    assert row["category_calls"] == 1 and row["category"] == 2 and row["category_scene_ok"] == 1
    assert row["buttons"] == 1 and row["id"] == 0x5646 and row["image"] == S.BUTTON_IMAGE
    assert (row["x"], row["y"]) == (0x70 + 0x164, 0x2DD) and row["flag"] == 0 and row["scene_ok"] == 1
    assert row["new_size"] == 0x14 and row["text"] == "Time" and row["colours_ok"] == row["font_ok"] == 1
    assert row["graphics_ok"] == row["added"] == row["added_ok"] == row["text_this_ok"] == 1
    assert row["target"] != S.STORE_SET_CATEGORY
    stock = _one(off, "store_ctor")
    assert stock["target"] == S.STORE_SET_CATEGORY and stock["category_calls"] == 1
    assert stock["buttons"] == stock["added"] == 0


def test_time_controls_click_opens_the_dialog_and_other_messages_go_to_the_game(on, off):
    a = {r["store_message"]: r for r in on if "store_message" in r}
    b = {r["store_message"]: r for r in off if "store_message" in r}
    for name in ("other_message", "unknown_button"):
        for rows in (a, b):
            assert rows[name]["result"] == 1 and rows[name]["stock_ran"] == 1 and rows[name]["dialog"] == {}
    click = a["time_button"]
    assert click["result"] == 1 and click["stock_ran"] == 0
    assert click["dialog"]["title"] == "Time Controls"
    assert click["dialog"]["status"] == "Running. Speed: normal."
    assert click["dialog"]["controls"] == TIME_DIALOG_CONTROLS
    assert b["time_button"]["stock_ran"] == 1 and b["time_button"]["dialog"] == {}  # off: the stock handler
    counters = _one(on, "counters")
    assert counters["time_dialogs"] == 1 and counters["time_buttons"] == 1


def test_time_controls_dialog_buttons_do_what_they_say(on):
    row = next(r for r in on if "time_dialog_script" in r)
    script = row["time_dialog_script"]
    assert script["title"] == "Time Controls" and script["controls"] == TIME_DIALOG_CONTROLS
    assert script["steps"] == ["Paused. Speed: normal.", "Paused. Speed: 2x.", "Running. Speed: 2x.",
                               "Running. Speed: 5x.", "Running. Speed: 10x.", "Running. Speed: normal."]
    no, yes = script["warp"]
    assert no == {"text": TIME_WARP_QUESTION, "status": "Running. Speed: normal."}
    assert yes == {"text": TIME_WARP_QUESTION, "status": "Running. Speed: normal. A time warp is under way."}
    assert (row["speed_field"], row["game_speed"], row["pending"]) == (10, 10, 2)  # No queued nothing; Yes queued 2
    # "+3 years" is 60 ticks (20 a year): the next aging pass gives exactly that, once.
    assert row["ages_after"] == [400 + 60, 100 + 60] and row["pending_after"] == 0


def test_time_controls_off_leaves_the_store_and_aging_stock(off):
    status = _one(off, "status")
    assert status["requested"] == status["installed"] == 0
    counters = _one(off, "counters")
    assert counters["time_buttons"] == counters["time_warps"] == counters["time_dialogs"] == 0


# =============================================================== fix_vanilla_bugs, part 2
# title_menu_start_over_confirms and title_menu_refresh_on_activate: the rest of
# B200's .vf2bugs. The harness runs the copied stock theMenuScene code with
# recorders for the game calls; the models below are written from B200's
# generator (work/patch_mobile_furniture_pack.py), not from the DLL.
def _menu_rows(rows):
    return {r["menu_case"]: r for r in rows if "menu_case" in r}


def test_start_over_stub_is_b200s_sequence():
    """B200's stub, read from the generator: the same literals and call order."""
    body = _python_function(GENERATOR.read_text(encoding="utf-8"), "patch_title_menu_start_over_confirms")
    assert _b200_constant("START_OVER_CONFIRM_STRING_ID") == S.START_OVER_CONFIRM_STRING_ID == 0x744
    assert 'b"\\x68\\xB9\\x00\\x00\\x00"' in body                                   # push 0B9h (click sound)
    assert body.index('"\\x6A\\x01"') < body.index('"\\x6A\\x00"') < body.index("START_OVER_CONFIRM_STRING_ID")
    assert 'b"\\x57"' in body and "call ShowMessageBox" in body                    # push this; call
    assert "\\x81\\xBE\\x18\\x5B\\x02\\x00\\xE7\\x03\\x00\\x00" in body             # cmp [state+25B18h],3E7h
    assert "\\xC7\\x86\\x18\\x5B\\x02\\x00\\x0A\\x00\\x00\\x00" in body             # mov [state+25B18h],10
    assert body.count("(0x25AD0, 0x25ACC, 0x25AC8, 0x25AC4, 0x25AC0, 0x25ABC)") == 1   # push order
    assert body.count("(0x25ABC, 0x25AC0, 0x25AC4, 0x25AC8, 0x25ACC, 0x25AD0)") == 1   # pop order
    assert body.index("call theGameState::Init") < body.index("call SaveCurrentGame")
    assert "jne return true" in body and "jmp +0x128" in body
    assert S.GAME_STATE_NAME_FIRST == 0x25ABC and S.GAME_STATE_NAME_LAST == 0x25AD0
    src = DLL_SOURCE.read_text(encoding="utf-8")
    stub = src[src.index("static __declspec(naked) void StartOverStub()"):]
    stub = stub[:stub.index("\n}\n") + 3]
    assert [l.strip() for l in stub.splitlines() if "push dword ptr [ecx + 0x25A" in l or "push dword ptr [ecx + 0x25AB" in l] == [
        f"push dword ptr [ecx + {o}]" for o in ("0x25AD0", "0x25ACC", "0x25AC8", "0x25AC4", "0x25AC0", "0x25ABC")]
    assert [l.strip() for l in stub.splitlines() if l.strip().startswith("pop dword ptr")] == [
        f"pop dword ptr [ecx + {o}]" for o in ("0x25ABC", "0x25AC0", "0x25AC4", "0x25AC8", "0x25ACC", "0x25AD0")]


def test_title_label_rule_is_b200s():
    body = _python_function(GENERATOR.read_text(encoding="utf-8"), "patch_title_menu_refresh_on_activate")
    assert _b200_constant("TITLE_PLAY_STRING_ID") == S.TITLE_PLAY_STRING_ID == 0x775
    assert _b200_constant("TITLE_CONTINUE_STRING_ID") == S.TITLE_CONTINUE_STRING_ID == 0x280
    assert 'bytes.fromhex("833D0000000000" "742A")' in body  # the constructor's own cmp GameStats[0],0; je
    # Manage Games: GetControl(id [this+0C4h]) then AddControl([this+0E4h]) before the name.
    assert 'b"\\xFF\\xB3\\xC4\\x00\\x00\\x00"' in body and 'b"\\xFF\\xB3\\xE4\\x00\\x00\\x00"' in body
    assert body.index("call GetControl") < body.index("call AddControl")
    assert S.MENU_MANAGE_GAMES_ID_FIELD == 0xC4 and S.MENU_MANAGE_GAMES_BUTTON_FIELD == 0xE4
    assert S.MENU_NAME_BUTTON_FIELD == 0xF0 and S.MENU_PLAY_BUTTON_FIELD == 0xD8


def test_fix_vanilla_bugs_part2_sites_are_proved_against_the_vanilla_game():
    facts = gen_sites.validate(vanilla_bytes())
    for needle in ("start_over_branch: no direct branch lands in 0x443f5d-0x443f61",
                   "show_player_entry: no direct branch lands in 0x443b81-0x443b87",
                   "show_player_add_name: no direct branch lands in 0x443c01-0x443c06",
                   "menu_activate_tail: no direct branch lands in 0x443a08-0x443a0b",
                   "nickname_cancel_dtor: no direct branch lands in 0x444074-0x444077",
                   "direct callers of 0x42c020: 0x443a07",
                   "0x443f08 is inside 'mov eax, dword ptr [0x557a44]' at 0x443f06, not a branch"):
        assert any(needle in f for f in facts), needle


def test_the_branch_scan_waiver_is_checked_not_trusted():
    saved = dict(S.NOT_INSTRUCTION_STARTS)
    try:
        S.NOT_INSTRUCTION_STARTS[0x443F06] = S.MENU_HANDLE_MESSAGE  # an instruction start: must be refused
        with pytest.raises(gen_sites.SiteError):
            gen_sites.validate(vanilla_bytes())
    finally:
        S.NOT_INSTRUCTION_STARTS.clear()
        S.NOT_INSTRUCTION_STARTS.update(saved)


def test_validation_refuses_a_non_conditional_or_wrong_target_jcc_retarget():
    data = bytearray(vanilla_bytes())
    pe = P.PE(bytes(data))
    off = pe.offset(S.START_OVER_BRANCH)
    data[off + 2] ^= 0x01   # the target moves: the pin no longer matches
    with pytest.raises(gen_sites.SiteError):
        gen_sites.validate(bytes(data))


def _start_over_expected(case, on):
    """Model of the click rows. Events are the recorders' log; story slots are
    [state+25CB8h, state+25CBCh] (stock starts at [5, 0x77])."""
    village, slot = case["village"], case["slot"]
    name = (b"Alyssa\0" + bytes(0x41 + i for i in range(7, 0x18))).hex()
    sound = "sound B9"
    box = "msgbox menu 744 0 1"
    if case["id"] == 5:
        return dict(result=0, events=[], story=[5, 0x77], speed=case["speed"], gs0=village)
    if case["id"] == 1 or not on or not village:
        if village:  # the stock rollover: keeps going into the current game
            return dict(result=0, events=[sound], story=[0, 5], speed=case["speed"], gs0=village)
        events = [sound]
        if not slot:
            events += ["nick_ctor 0", "domodal menu 0", "nick_dtor"]
        return dict(result=0, events=events + ["setstory 0"], story=[9, 5], speed=case["speed"], gs0=0)
    if case["answer"] != 0:  # No
        return dict(result=1, events=[sound, box], story=[5, 0x77], speed=case["speed"], gs0=village)
    speed = 10 if case["speed"] >= 999 else case["speed"]
    return dict(result=0, events=[sound, box, f"init state speed={speed}", "save state", "setstory 0"],
                story=[9, 5], speed=speed, gs0=0, name=name)


CLICK_CASES = {
    "start_over_no_village": dict(id=6, village=0, answer=0, speed=10, slot=1),
    "start_over_no_village_no_slot": dict(id=6, village=0, answer=0, speed=10, slot=0),
    "start_over_no": dict(id=6, village=1, answer=-1, speed=10, slot=1),
    "start_over_yes": dict(id=6, village=1, answer=0, speed=10, slot=1),
    "start_over_yes_speed_998": dict(id=6, village=1, answer=0, speed=998, slot=1),
    "start_over_yes_speed_999": dict(id=6, village=1, answer=0, speed=999, slot=1),
    "start_over_yes_speed_1009": dict(id=6, village=1, answer=0, speed=1009, slot=1),
    "play_village": dict(id=1, village=1, answer=-1, speed=10, slot=1),
    "play_no_village": dict(id=1, village=0, answer=-1, speed=10, slot=1),
    "unknown_button": dict(id=5, village=1, answer=-1, speed=10, slot=1),
}
ORIGINAL_NAME = (b"Alyssa\0" + bytes(0x41 + i for i in range(7, 0x18))).hex()


@pytest.mark.parametrize("name", sorted(CLICK_CASES))
def test_start_over_confirms_like_b200(on, off, name):
    case = CLICK_CASES[name]
    a, b = _menu_rows(on)[f"click:{name}"], _menu_rows(off)[f"click:{name}"]
    for row, installed in ((b, False), (a, True)):
        want = _start_over_expected(case, installed)
        assert row["events"] == want["events"], (name, installed, row)
        assert row["result"] == want["result"] and row["story"] == want["story"], (name, installed, row)
        assert row["speed"] == want["speed"] and row["gs0"] == want["gs0"], (name, installed, row)
        assert row["esp_ok"] == 1
        assert row["name"] == ORIGINAL_NAME  # the name is untouched (restored after Init on Yes)
    # The stock game never asks; with a village it silently rolls the story slot over.
    if case["id"] == 6 and case["village"]:
        assert b["events"] == ["sound B9"] and b["story"] == [0, 5] and b["result"] == 0
        assert any("msgbox" in e for e in a["events"])
    else:
        assert a == b, "everything but Start Over with a village is stock"


def test_start_over_yes_keeps_the_player_name_through_init(on):
    row = _menu_rows(on)["click:start_over_yes"]
    assert row["name"] == ORIGINAL_NAME  # the recorder's Init wiped all 24 bytes; the stub put them back


def _label_events(village):
    return ["font strings", f"string {0x280 if village else 0x775:X}",
            f"settext play {'Continue' if village else 'Play'} white font"]


def _show_player_expected(village, slot, name_present, manage_present, on):
    ev = _label_events(village) if on else []
    ev.append("get 7")
    if slot:
        ev.append("name_text name Alyssa")
        if not name_present:
            if on:
                ev.append("get 2")
                if not manage_present:
                    ev.append("add manage")
            ev.append("add name")
    elif name_present:
        ev += ["remove manage", "remove name"]
    return ev


@pytest.mark.parametrize("village", [0, 1])
@pytest.mark.parametrize("slot", [0, 1])
@pytest.mark.parametrize("name_present", [0, 1])
@pytest.mark.parametrize("manage_present", [0, 1])
def test_update_show_player_refreshes_like_b200(on, off, village, slot, name_present, manage_present):
    key = f"update_show_player:village{village}_slot{slot}_name{name_present}_manage{manage_present}"
    for rows, installed in ((off, False), (on, True)):
        row = _menu_rows(rows)[key]
        assert row["events"] == _show_player_expected(village, slot, name_present, manage_present, installed), \
            (key, installed, row)
        assert row["esp_ok"] == 1 and row["gs0"] == village


def test_title_refresh_after_a_cancelled_name_prompt_and_on_activate(on, off):
    # The cancel path: dtor, then the same refresh the Change Player path makes.
    for rows, installed in ((off, False), (on, True)):
        r = _menu_rows(rows)
        cancel = r["nickname:cancel"]
        base = ["sound B9", "nick_ctor 0", "domodal menu 0", "nick_dtor"]
        refresh = _label_events(0) + ["get 7", "remove manage", "remove name"] if installed else []
        assert cancel["events"] == base + refresh and cancel["result"] == 1, (installed, cancel)
        nothing = r["nickname:cancel_nothing_shown"]
        assert nothing["events"] == base + (_label_events(0) + ["get 7"] if installed else []), (installed, nothing)
        ok = r["nickname:ok"]  # the OK path is stock in both
        assert ok["events"] == base[:3] + ["nick_dtor", "setstory 0"] and ok["result"] == 0
        for village in (0, 1):
            true_row = r[f"activate:arg1_village{village}"]
            want = ["butterflies ok", "anim ok"]
            if installed:
                want += _show_player_expected(village, 1, 0, 0, True)
            assert true_row["events"] == want, (installed, village, true_row)
            assert r[f"activate:arg0_village{village}"]["events"] == []  # deactivating: nothing
            assert true_row["esp_ok"] == 1


def test_fix_vanilla_bugs_writes_all_seven_sites(built):
    rows = _harness(built, {k.ini_key: k.key == "fix_vanilla_bugs" for k in S.MODULES if not k.internal}, tag="-fvb")
    status = _one(rows, "status")
    idx = [m.key for m in S.MODULES].index("fix_vanilla_bugs")
    assert status["installed"] == _module_bit("fix_vanilla_bugs") and status["write_masks"][idx] == 0b1111111
    sites = _sites(rows)
    lo, hi = status["dll_lo"], status["dll_hi"]
    md = _md()
    jcc = next(md.disasm(bytes.fromhex(sites[S.START_OVER_BRANCH]["bytes"]), S.START_OVER_BRANCH))
    assert jcc.mnemonic == "je" and jcc.size == 6 and lo <= jcc.operands[0].imm < hi
    for va in (S.UPDATE_SHOW_PLAYER, S.SHOW_PLAYER_ADD_NAME):
        raw = bytes.fromhex(sites[va]["bytes"])
        j = next(md.disasm(raw, va))
        assert j.mnemonic == "jmp" and lo <= j.operands[0].imm < hi
        assert raw[5:] == b"\x90" * (len(raw) - 5)
    for va in (S.MENU_ACTIVATE_TAIL_CALL, S.NICKNAME_CANCEL_DTOR_CALL):
        c = next(md.disasm(bytes.fromhex(sites[va]["bytes"]), va))
        assert c.mnemonic == "call" and lo <= c.operands[0].imm < hi
    tramp = _one(rows, "trampoline")
    raw = bytes.fromhex(tramp["bytes"])
    assert raw[:8] == S.PIN_BY_NAME["show_player_entry"].expected
    assert next(md.disasm(raw[8:13], tramp["trampoline"] + 8)).operands[0].imm == S.UPDATE_SHOW_PLAYER + 8
    assert _one(rows, "wx_regions")["wx_regions"] == 0


# =============================================================== older_villager_mortality
def _b200_hazard_function():
    """B200's older_mortality_hazard_millionths, executed from the generator's own source."""
    import ast
    import math

    text = GENERATOR.read_text(encoding="utf-8")
    tree = ast.parse(text)
    wanted = {"OLDER_MORTALITY_TABLE_FIRST_AGE", "OLDER_MORTALITY_RANDOM_LIMIT", "OLDER_MORTALITY_HAZARD_CAP_MILLIONTHS",
              "OLDER_MORTALITY_BASE_INTENSITY_PER_YEAR", "OLDER_MORTALITY_LATE_INTENSITY_PER_YEAR",
              "OLDER_MORTALITY_LATE_ACCELERATION_EFFECTIVE_AGE"}
    body = [n for n in tree.body
            if (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in wanted for t in n.targets))
            or (isinstance(n, ast.FunctionDef) and n.name == "older_mortality_hazard_millionths")]
    namespace = {"math": math}
    exec(compile(ast.Module(body=body, type_ignores=[]), "b200-hazard", "exec"), namespace)
    return namespace["older_mortality_hazard_millionths"], namespace


def test_mortality_hazard_table_is_b200s_formula():
    hazard, ns = _b200_hazard_function()
    assert ns["OLDER_MORTALITY_TABLE_FIRST_AGE"] == S.OLDER_MORTALITY_TABLE_FIRST_AGE == 55
    assert ns["OLDER_MORTALITY_RANDOM_LIMIT"] == S.OLDER_MORTALITY_RANDOM_LIMIT
    assert ns["OLDER_MORTALITY_HAZARD_CAP_MILLIONTHS"] == S.OLDER_MORTALITY_HAZARD_CAP_MILLIONTHS
    assert _b200_constant("OLDER_MORTALITY_TABLE_LAST_AGE") == S.OLDER_MORTALITY_TABLE_LAST_AGE == 317
    assert S.OLDER_MORTALITY_HAZARDS == tuple(hazard(a) for a in range(55, 318))
    # Beyond the table B200 uses the cap, which is also the first age at the cap.
    assert all(hazard(a) == 999999 for a in range(318, 700))
    assert hazard(317) < 999999 and hazard(54) == 0 and hazard(55) == 0


def test_mortality_decision_is_b200s_helper():
    b200 = _normalise(_c_function(GENERATOR.read_text(encoding="utf-8"),
                                  r'extern "C" int __cdecl VF2RollOlderVillagerMortality\('))
    port = _normalise(_c_function(DLL_SOURCE.read_text(encoding="utf-8"), r"static int __cdecl RollOlderVillagerMortality\("))
    b200 = b200.replace("kOlderMortalityHazardsMillionths", "OLDER_MORTALITY_HAZARDS")
    port = port.replace("_OLDER_MORTALITY_HAZARDS", "OLDER_MORTALITY_HAZARDS")
    assert b200 == port


def test_mortality_stub_is_b200s_trampoline():
    """B200: FoodGroups(0) (observer), then helper(age [state+8], groups); a hit does
    SetHealth(0, OldAge=2); both rejoin after the statement."""
    body = _python_function(GENERATOR.read_text(encoding="utf-8"), "patch_older_villager_mortality")
    order = ["push 0", "call FoodGroupsActive observer", "push eax ; food groups", "push [ebx+8] ; internal age",
             "call mortality helper", "test eax,eax", "push OldAge", "push zero health", "call SetHealth",
             "jmp mortality done"]
    positions = [body.index(f"# {item}") if f"# {item}" in body else body.index(item) for item in order]
    assert positions == sorted(positions)
    assert "0x6A, 0x02,                         # push OldAge" in body
    assert "0x6A, 0x00,                         # push zero health" in body
    src = DLL_SOURCE.read_text(encoding="utf-8")
    stub = src[src.index("static __declspec(naked) void OlderMortalityStub()"):]
    stub = stub[:stub.index("\n}\n") + 3]
    lines = [l.strip() for l in stub.splitlines()]
    assert lines.index("push dword ptr [ebp + 8]") < lines.index("call RollOlderVillagerMortality")
    assert lines.index("push 2") + 1 == lines.index("push 0", lines.index("push 2"))
    assert S.CAUSE_OF_DEATH_OLD_AGE == 2 and S.VILLAGER_STATE_AGE_OFFSET == 8
    assert "OLDER_MORTALITY_FLAG_SYMBOL" in body and S.MODULE_BY_KEY["older_villager_mortality"].b200_default is False


def test_mortality_sites_are_proved_against_the_vanilla_game():
    facts = gen_sites.validate(vanilla_bytes())
    for needle in ("mortality_food_groups: no direct branch lands in 0x49bbbe-0x49bbc5",
                   "older_mortality_statement: 0x49bbc6-0x49bc46 is single-entry, every exit goes to 0x49bc47"):
        assert any(needle in f for f in facts), needle


def test_region_check_refuses_a_wrong_exit_a_misaligned_start_and_a_jump_out():
    saved = S.SINGLE_ENTRY_REGIONS
    try:
        # Every stock exit of the statement is 0x49BC47; claiming another exit must fail.
        S.SINGLE_ENTRY_REGIONS = (("wrong_exit", 0x49BBC6, 0x49BC47, 0x49BC00),)
        with pytest.raises(gen_sites.SiteError, match="exits to"):
            gen_sites.validate(vanilla_bytes())
        # A start that is not a boundary a pinned run established is refused too.
        S.SINGLE_ENTRY_REGIONS = (("split", 0x49BBC7, 0x49BC47, 0x49BC47),)
        with pytest.raises(gen_sites.SiteError):
            gen_sites.validate(vanilla_bytes())
        # A range that runs on past the statement (its next jump leaves) is refused.
        S.SINGLE_ENTRY_REGIONS = (("leaves", 0x49BBC6, 0x49BC47 + 0x12, 0x49BC47),)
        with pytest.raises(gen_sites.SiteError):
            gen_sites.validate(vanilla_bytes())
    finally:
        S.SINGLE_ENTRY_REGIONS = saved
    assert gen_sites.validate(vanilla_bytes())


def _stock_mortality(age, groups):
    """(random calls, random limit, kill threshold) of the unpatched statement."""
    if age % 20 or age <= 1100 + 20 * groups:
        return 0, 0, 0
    return 1, 100, 10 * (age // 20 - (1100 + 20 * groups) // 20)


def _b200_mortality(age, groups):
    if age < 0 or age % 20:
        return 0, 0, 0
    effective = age // 20 - max(0, min(4, groups))
    if effective < 55:
        return 0, 0, 0
    hazard = S.OLDER_MORTALITY_HAZARDS[effective - 55] if effective <= 317 else 999999
    return 1, 1000000, hazard


def _mortality_rows(rows):
    return {r["mortality"]: r["rows"] for r in rows if "mortality" in r}


@pytest.mark.parametrize("groups", range(6))
def test_older_mortality_matches_b200_and_off_is_the_stock_statement(on, off, groups):
    a, b = _mortality_rows(on)[groups], _mortality_rows(off)[groups]
    assert len(a) == len(b) == 338
    ages = [r[0] for r in a]
    assert ages[:332] == [20 * i for i in range(332)] and all(x % 20 for x in ages[332:])
    rolled_on = rolled_off = 0
    for (age, calls, limit, threshold, fga, fga_arg, flags), (age2, c2, l2, t2, fga2, arg2, flags2) in zip(a, b):
        assert age == age2
        # The stock statement always opens with FoodGroupsActive(0); registers and stack are kept.
        assert (fga, fga_arg, fga2, arg2) == (1, 0, 1, 0) and flags == flags2 == 31, (age, a, b)
        assert (c2, l2, t2) == _stock_mortality(age, groups), (age, "off")
        assert (calls, limit, threshold) == _b200_mortality(age, groups), (age, "on")
        rolled_on += calls
        rolled_off += c2
    assert rolled_on > 200 and rolled_off > 200
    # The two curves really differ (B200's is gentler early and certain at the cap).
    assert [r[3] for r in a] != [r[3] for r in b]


def test_older_mortality_clamps_food_groups_at_four_like_b200(on):
    four, five = _mortality_rows(on)[4], _mortality_rows(on)[5]
    assert four == five


def test_older_mortality_writes_one_site_and_is_independent(built):
    rows = _harness(built, {k.ini_key: k.key == "older_villager_mortality" for k in S.MODULES if not k.internal}, tag="-mort")
    status = _one(rows, "status")
    idx = [m.key for m in S.MODULES].index("older_villager_mortality")
    assert status["installed"] == _module_bit("older_villager_mortality") and status["write_masks"][idx] == 1
    sites = _sites(rows)
    raw = bytes.fromhex(sites[S.UPKEEP_FOOD_GROUPS_CALL]["bytes"])
    jmp = next(_md().disasm(raw, S.UPKEEP_FOOD_GROUPS_CALL))
    assert jmp.mnemonic == "jmp" and status["dll_lo"] <= jmp.operands[0].imm < status["dll_hi"]
    assert raw[5:] == b"\x90" * 4
    assert _one(rows, "wx_regions")["wx_regions"] == 0


# =============================================================== event_collectable_slot_replacement
def _collect_rows(rows):
    return [r for r in rows if "collect" in r]


class _CollectModel:
    """B200's VF2EventCollectableAddImpl (work/patch_mobile_furniture_pack.py),
    re-written independently, on top of a model of the native Add. Slots are
    [active, carrying, stamp, x, y, picked]; state persists across calls like
    the DLL's globals do, so rows are replayed in the order the harness made them."""

    def __init__(self):
        self.last_slot, self.last_stamp = -1, 0

    @staticmethod
    def native_add(slots, now, mode, carrying, x, y, force):
        if mode == 2:
            return  # the native random path gave up
        i = 0
        while i < 2 and slots[i][0] and not force:
            i += 1
        if i == 2:
            return  # both busy, not forced: the native Add spawns nothing
        slots[i] = [1, carrying, now + 0x78, x, y, -1]

    def impl(self, slots, now, mode, carrying, x, y, force):
        busy = [bool(slots[0][0]), bool(slots[1][0])]

        def fresh(i):
            if self.last_slot != i or not slots[i][0]:
                return False
            return slots[i][2] == self.last_stamp and slots[i][2] == now + 0x78

        def victim():
            f0, f1 = fresh(0), fresh(1)
            if f0 != f1:
                return 1 if f0 else 0
            p0, p1 = slots[0][5] != -1, slots[1][5] != -1
            if p0 != p1:
                return 1 if p0 else 0
            return 1 if slots[1][2] < slots[0][2] else 0

        def move(src, dst):
            slots[dst] = list(slots[src])
            slots[src][0] = 0

        freed, sacrificed = -1, None
        if force:
            if busy[0] and not busy[1]:
                move(0, 1)
            elif busy[0] and busy[1]:
                v = victim()
                sacrificed = list(slots[v])
                freed = 0
                if v == 1:
                    move(0, 1)
                else:
                    slots[0][0] = 0
        elif busy[0] and busy[1]:
            freed = victim()
            sacrificed = list(slots[freed])
            slots[freed][0] = 0
        landed = 0 if force else (freed if freed >= 0 else (1 if busy[0] else 0))
        self.native_add(slots, now, mode, carrying, x, y, force)
        if slots[landed][0]:
            self.last_slot, self.last_stamp = landed, slots[landed][2]
        elif freed >= 0:
            slots[freed] = sacrificed

    def expected(self, row, installed):
        slots = [list(s) for s in row["in"]]
        kind = row["collect"].split(":")[0]
        a, b, c, d = row["op"]
        if kind in ("add", "prior"):
            ops = [(a, b, c, d)]
        elif kind == "bug_whisperer":
            ops = [(0x4F + a, 0x4BC + a, 0x725 + a, 0)] * 2 if d == 0 else []  # every GetRandom returns `a`
        else:
            ops = [(-1, 0, 0, 1)]  # Neighbor Collectible: random carrying, forced
        for op in ops:
            if installed:
                self.impl(slots, row["clock"], row["mode"], *op)
            else:
                self.native_add(slots, row["clock"], row["mode"], *op)
        return slots


def test_collectable_replay_helpers_are_b200s_text():
    b200 = GENERATOR.read_text(encoding="utf-8")
    dll = DLL_SOURCE.read_text(encoding="utf-8")

    def norm(text):
        text = re.sub(r"reinterpret_cast<([^>]*)>", r"(\1)", text)
        text = re.sub(r"CCollectableItem \*collectables = [^;]*;", "", text)
        text = re.sub(r"collectables->Remove\(", "NativeCollectableRemove(item,", text)
        text = text.replace("ldwPoint point = {x, y};", "")
        text = text.replace("collectables->Add((ECarrying)carrying, point, force != 0);",
                            "NativeCollectableAdd(item, carrying, x, y, force != 0);")
        text = text.replace("kVF2", "k").replace("gVF2", "g").replace("VF2", "")
        return _normalise(text)

    for name, b_sig, d_sig in (
        ("busy", r"static bool VF2EventCollectableSlotBusy\(", r"static bool EventCollectableSlotBusy\("),
        ("picked", r"static bool VF2EventCollectableSlotPicked\(", r"static bool EventCollectableSlotPicked\("),
        ("stamp", r"static unsigned int VF2EventCollectableSlotStamp\(", r"static unsigned int EventCollectableSlotStamp\("),
        ("fresh", r"static bool VF2EventCollectableSlotFreshFromBurst\(", r"static bool EventCollectableSlotFreshFromBurst\("),
        ("victim", r"static int VF2EventCollectableVictim\(", r"static int EventCollectableVictim\("),
        ("move", r"static void VF2MoveEventCollectableSlot\(", r"static void MoveEventCollectableSlot\("),
        ("copy", r"static void VF2CopyEventCollectableSlot\(", r"static void CopyEventCollectableSlot\("),
        ("restore", r"static void VF2RestoreEventCollectableSlot\(", r"static void RestoreEventCollectableSlot\("),
        ("impl", r'extern "C" void __cdecl VF2EventCollectableAddImpl\(', r"static void __cdecl EventCollectableAddImpl\("),
    ):
        assert norm(_c_function(b200, b_sig)) == norm(_c_function(dll, d_sig)), name
    # The slot address and the clock stamp (written with casts in B200).
    slot = _normalise(_c_function(b200, r"static unsigned char \*VF2EventCollectableSlot\("))
    assert "+0x34C+slot*0x1C" in slot
    assert "+0x34C+slot*0x1C" in _normalise(_c_function(dll, r"static unsigned char \*EventCollectableSlot\("))
    now = _normalise(_c_function(b200, r"static unsigned int VF2EventCollectableStampNow\("))
    assert "GetSecondsFromGameStart()+0x78:0" in now
    assert "NativeSecondsFromGameStart(clock)+0x78:0" in _normalise(
        _c_function(dll, r"static unsigned int EventCollectableStampNow\("))
    # The thunk: ecx and the four stack words forwarded, 16 bytes popped.
    b200_thunk = _normalise(_c_function(b200, r'extern "C" __declspec\(naked\) void VF2EventCollectableAdd\(\)'))
    dll_thunk = _normalise(_c_function(dll, r"static __declspec\(naked\) void EventCollectableAddThunk\(\)"))
    assert b200_thunk == dll_thunk
    assert dll_thunk.count("pushdwordptr[esp+16]") == 4


def test_collectable_sites_are_proved_and_the_events_are_the_rtti_named_classes():
    facts = gen_sites.validate(vanilla_bytes())
    assert any("direct callers of 0x415090: 0x41554d, 0x419a2f, 0x41af0e, 0x41af4b" in f for f in facts)
    vanilla = vanilla_bytes()
    pe = P.PE(vanilla)

    def class_of(vtable):
        col = struct.unpack_from("<I", vanilla, pe.offset(vtable - 4))[0]
        td = struct.unpack_from("<I", vanilla, pe.offset(col + 12))[0]
        at = pe.offset(td + 8)
        return vanilla[at:vanilla.index(b"\0", at)]

    def slot(vtable, index):
        return struct.unpack_from("<I", vanilla, pe.offset(vtable + 4 * index))[0]

    assert class_of(0x4E1C6C) == b".?AVCEventTheBugWhisperer@@" and slot(0x4E1C6C, 12) == 0x41AE90
    assert class_of(0x4E0FF4) == b".?AVCEventTheNeighborCollectible@@" and slot(0x4E0FF4, 13) == 0x419A20
    # The three retargeted calls are inside those two ImpactGame bodies; the fourth caller
    # (0x41554D) is CCollectableItem::Update's natural spawn and stays alone, as in B200.
    assert sorted(S.EVENT_COLLECTABLE_ADD_CALLSITES) == [0x419A2F, 0x41AF0E, 0x41AF4B]
    assert S.COLLECTABLE_UPDATE_ADD_CALL not in S.EVENT_COLLECTABLE_ADD_CALLSITES
    b200 = GENERATOR.read_text(encoding="utf-8")
    assert re.search(r'\("\?ImpactGame@CEventTheBugWhisperer@@UAEXH@Z", 0x7D\),\s*\("\?ImpactGame@CEventTheBugWhisperer@@UAEXH@Z", 0xB8\),\s*'
                     r'\("\?ImpactGame@CEventTheNeighborCollectible@@UAEXXZ", 0x0E\)', b200)


def test_collectable_hooks_follow_the_b200_policy(on, off):
    for rows, installed in ((on, True), (off, False)):
        model = _CollectModel()
        table = _collect_rows(rows)
        assert len(table) > 400
        changed = 0
        for row in table:
            assert row["esp_ok"] == 1, row["collect"]
            assert model.expected(row, installed) == row["out"], (installed, row)
            changed += row["out"] != row["in"]
        assert changed > 100
    # Installed, an event spawn with both slots busy replaces something; stock does nothing.
    a = {r["collect"]: r for r in _collect_rows(on)}
    b = {r["collect"]: r for r in _collect_rows(off)}
    both_busy = [k for k in a if k.startswith("add:p0_k") and k.endswith("_f0") and a[k]["in"][0][0] and a[k]["in"][1][0]]
    assert both_busy and all(b[k]["out"] == b[k]["in"] and a[k]["out"] != a[k]["in"] for k in both_busy)
    # Nothing but the three event call sites changed: with a free slot both builds spawn the same.
    free = [k for k in a if k.startswith("add:p0_k") and k.endswith("_f0") and not (a[k]["in"][0][0] and a[k]["in"][1][0])]
    assert free and all(a[k]["out"] == b[k]["out"] for k in free)
    # The Bug Whisperer's second spawn never sacrifices its first (a fresh item is protected).
    bw = a["bug_whisperer:arg0_k22"]  # both busy, unpicked: the event nets two new items
    assert sorted(s[1] for s in bw["out"]) == [0x4F + 3, 0x4F + 3]
    assert b["bug_whisperer:arg0_k22"]["out"] == b["bug_whisperer:arg0_k22"]["in"]  # stock: nothing spawns
    assert a["bug_whisperer:arg1_k22"]["out"] == a["bug_whisperer:arg1_k22"]["in"]  # another event argument: untouched
    # The call-site targets: the DLL's thunk when installed, the native Add when not.
    t_on = _one(on, "collect_targets")
    t_off = _one(off, "collect_targets")
    assert t_off == [S.COLLECTABLE_ADD] * 3 and len(set(t_on)) == 1 and t_on[0] != S.COLLECTABLE_ADD


def test_collectable_sacrificed_record_comes_back_when_the_native_spawn_gives_up(on):
    rows = {r["collect"]: r for r in _collect_rows(on)}
    # Native random path gave up (mode 2), both slots busy, forced: nothing may be lost.
    for k0 in range(6):
        for k1 in range(6):
            r = rows[f"neighbor:m2_k{k0}{k1}"]
            if r["in"][0][0] and r["in"][1][0]:
                assert sorted(map(tuple, r["out"])) == sorted(map(tuple, r["in"])), r
    # And when it activates (mode 1) the new item is in slot 0 with one old record kept.
    r = rows["neighbor:m1_k11"]
    assert r["out"][0][1] == -1 and r["out"][0][0] == 1 and r["out"][1][1] in (0x61, 0x69)


def test_collectable_module_writes_exactly_its_three_calls(built):
    rows = _harness(built, {k.ini_key: k.key == "event_collectable_slot_replacement" for k in S.MODULES if not k.internal}, tag="-coll")
    status = _one(rows, "status")
    idx = [m.key for m in S.MODULES].index("event_collectable_slot_replacement")
    assert status["installed"] == _module_bit("event_collectable_slot_replacement")
    assert status["write_masks"][idx] == 0b111
    sites = _sites(rows)
    md = _md()
    for va in S.EVENT_COLLECTABLE_ADD_CALLSITES:
        c = next(md.disasm(bytes.fromhex(sites[va]["bytes"]), va))
        assert c.mnemonic == "call" and status["dll_lo"] <= c.operands[0].imm < status["dll_hi"]
    assert S.COLLECTABLE_UPDATE_ADD_CALL not in sites  # the natural spawn is never touched
    assert _one(rows, "wx_regions")["wx_regions"] == 0


# =============================================================== power_failure_event
class _PowerModel:
    """B200's VF2PowerFailure* helpers (state: four slots keyed by event, one-shot)."""

    def __init__(self):
        self.states = [[None, 0] for _ in range(4)]
        self.replacement = 0

    def find(self, event, create):
        empty = None
        for st in self.states:
            if st[0] == event:
                return st
            if empty is None and st[0] is None:
                empty = st
        if not create:
            return None
        if empty is not None:
            empty[0], empty[1] = event, 0
            return empty
        st = self.states[self.replacement % 4]
        self.replacement += 1
        st[0], st[1] = event, 0
        return st

    def op(self, slot, ev, choice, rv):
        if slot == 14:
            st = self.find(ev, True)
            st[1] = 1 if (choice != 0 and rv == 0) else 0
            return [], None
        if slot == 11:
            if choice == 0:
                return [], 0x9BC
            st = self.find(ev, False)
            return [], (0x9BE if st and st[1] else 0x9BD)
        events = ["setprop env 17", "reset food 1"] if choice == 0 else []
        if choice != 0:
            st = self.find(ev, False)
            if st and st[1]:
                events = ["giveall villagers 2 15"]
        st = self.find(ev, False)
        if st:
            st[0], st[1] = None, 0
        return events, None


def _stock_power(slot, ev, choice, rv):
    if slot == 14:
        return [], None
    if slot == 11:
        return [], 0x9BC + (1 if choice else 0)
    events = ["setprop env 17"]  # the stock method sets the prop for BOTH choices
    events += ["reset food 1"] if choice == 0 else ["symptom 2 villager 2"] * rv
    return events, None


def _power_rows(rows):
    return [r for r in rows if "power" in r]


def test_power_failure_helpers_are_b200s_text():
    b200 = GENERATOR.read_text(encoding="utf-8")
    dll = DLL_SOURCE.read_text(encoding="utf-8")

    def norm(text):
        text = text.replace("gVF2", "g").replace("VF2", "").replace("ldwGameState::GetRandom", "GetRandom")
        return _normalise(text)

    pairs = (
        (r"static VF2PowerFailureState \*VF2FindPowerFailureState\(", r"static PowerFailureState \*FindPowerFailureState\("),
        (r"static void VF2ClearPowerFailureState\(", r"static void ClearPowerFailureState\("),
    )
    for b_sig, d_sig in pairs:
        # B200's comment in Find explains the history; _normalise strips comments.
        assert norm(_c_function(b200, b_sig)) == norm(_c_function(dll, d_sig)), b_sig
    for b_sig, d_sig in ((r'extern "C" void __cdecl VF2PowerFailureCalcAward\(', r"static void PowerFailureCalcAward\("),
                         (r'extern "C" int __cdecl VF2PowerFailureGetResultDescription\(', r"static int PowerFailureGetResultDescription\(")):
        assert norm(_c_function(b200, b_sig)) == norm(_c_function(dll, d_sig)), b_sig
    # ImpactGame: B200 calls Environment.SetProp / FoodStore.Reset / VillagerManager.GiveAllVillagersSymptom.
    impact_b = norm(_c_function(b200, r'extern "C" void __cdecl VF2PowerFailureImpactGame\('))
    impact_b = (impact_b.replace("Environment.SetProp((EPropEnum)0x17)", "EnvironmentSetProp((void*)_ENVIRONMENT,0x17)")
                .replace("FoodStore.Reset(true)", "FoodStoreReset((void*)_FOOD_STORE,true)")
                .replace("VillagerManager.GiveAllVillagersSymptom((ESymptom)2,15)",
                         "GiveAllVillagersSymptom((void*)_VILLAGER_MANAGER,2,15)"))
    assert impact_b == norm(_c_function(dll, r"static void PowerFailureImpactGame\("))
    assert S.POWER_FAILURE_RESULT_A == 0x9BC and S.POWER_FAILURE_RESULT_B1 == 0x9BD and S.POWER_FAILURE_RESULT_B2 == 0x9BE
    assert '"result_ids": {"a": "0x9BC", "b1": "0x9BD", "b2": "0x9BE"}' in b200
    assert S.MODULE_BY_KEY["power_failure_event"].b200_default is True


def test_power_failure_sites_and_the_b2_string_exist_in_the_vanilla_game():
    facts = gen_sites.validate(vanilla_bytes())
    assert any("slot 14 of .?AVCEventThePowerFailure@@ holds 0x4b58a0" in f for f in facts)
    assert any("direct callers of 0x41c310: " in f for f in facts)
    vanilla = vanilla_bytes()
    pe = P.PE(vanilla)
    # Exactly one pointer to each stock method anywhere in the file: the vtable slot.
    for target in (S.POWER_FAILURE_DESCRIPTION_STOCK, S.POWER_FAILURE_IMPACT_STOCK):
        assert vanilla.count(struct.pack("<I", target)) == 1
    # String 0x9BE has a record in the static table the string manager indexes, with the B2 text.
    rec = {}
    for i in range(S.STRING_TABLE_COUNT):
        at = pe.offset(S.STRING_TABLE_ENTRIES + 16 * i)
        sid, name, text, zero = struct.unpack_from("<IIII", vanilla, at)
        rec[sid] = (name, text)
    assert 0x9BE in rec

    def cstr(va):
        at = pe.offset(va)
        return vanilla[at:vanilla.index(b"\0", at)]

    assert cstr(rec[0x9BE][0]) == b"eEventThePowerFailureResultB2"
    assert cstr(rec[0x9BE][1]) == b"Everyone gets an upset stomach. The food was not ok."
    assert cstr(rec[0x9BD][0]) == b"eEventThePowerFailureResultB1" and cstr(rec[0x9BC][0]) == b"eEventThePowerFailureResultA"


@pytest.mark.parametrize("installed", [False, True])
def test_power_failure_follows_b200_and_off_is_stock(on, off, installed):
    rows = _power_rows(on if installed else off)
    assert len(rows) == 40 + 20
    model = _PowerModel()
    for r in rows:
        slot, ev, choice, rv = r["op"]
        want_events, want_ret = model.op(slot, ev, choice, rv) if installed else _stock_power(slot, ev, choice, rv)
        assert r["events"] == want_events, (installed, r)
        if want_ret is not None:
            assert r["ret"] == want_ret, (installed, r)
        assert r["esp_ok"] == 1


def test_power_failure_installed_differs_from_stock_where_b200_does(on, off):
    a, b = _power_rows(on), _power_rows(off)
    # B200 never sets the spoiled-food prop on "Take a chance" and gives 15% per villager on a bad roll.
    impacts = [(x, y) for x, y in zip(a, b) if x["op"][0] == 12 and x["op"][2] == 1]
    assert impacts and all("setprop env 17" in y["events"] and "setprop env 17" not in x["events"] for x, y in impacts)
    assert any("giveall villagers 2 15" in x["events"] for x, _ in impacts)
    descriptions = {x["ret"] for x, _ in zip(a, b) if x["op"][0] == 11 and x["op"][2] == 1}
    assert descriptions == {0x9BD, 0x9BE}


def test_power_failure_module_writes_exactly_three_vtable_slots(built):
    rows = _harness(built, {k.ini_key: k.key == "power_failure_event" for k in S.MODULES if not k.internal}, tag="-pf")
    status = _one(rows, "status")
    idx = [m.key for m in S.MODULES].index("power_failure_event")
    assert status["installed"] == _module_bit("power_failure_event") and status["write_masks"][idx] == 0b111
    sites = _sites(rows)
    for slot in (S.POWER_FAILURE_SLOT_CALC_AWARD, S.POWER_FAILURE_SLOT_DESCRIPTION, S.POWER_FAILURE_SLOT_IMPACT):
        ptr = struct.unpack("<I", bytes.fromhex(sites[slot]["bytes"]))[0]
        assert status["dll_lo"] <= ptr < status["dll_hi"] and sites[slot]["protect"] == "R"
    assert _one(rows, "wx_regions")["wx_regions"] == 0
