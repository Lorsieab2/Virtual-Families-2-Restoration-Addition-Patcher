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
    spans = sorted((p.va, p.end, p.name) for p in S.PINS if p.role != "context")
    for (a_lo, a_hi, a), (b_lo, b_hi, b) in zip(spans, spans[1:]):
        assert a_hi <= b_lo, f"{a} overlaps {b}"
    assert {p.role for p in S.PINS} == {"detour", "replace", "retarget", "context"}
    assert len([p for p in S.PINS if p.role == "retarget"]) == 4


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
    assert any("CanStartNextGeneration direct callers: 0x430681, 0x430db8, 0x43c0bd, 0x4407dc" in f for f in facts)


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
    exe = P.apply(game, out, fake_dll, True, "VF2 Runtime Test.exe")
    assert exe.name == "VF2 Runtime Test.exe" and not (out / S.VANILLA_EXE_NAME).exists()
    assert (out / S.PATCHER_FOLDER / S.DLL_NAME).read_bytes() == b"MZ test"
    ini = (out / S.PATCHER_FOLDER / S.INI_NAME).read_text(encoding="utf-16")
    assert "AllowOlderPregnancies=1" in ini
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
    _run_bat([
        f'call "{VCVARS}" >nul || exit /b 1',
        f'cl /nologo /O2 /MT /EHsc /W4 /WX /LD /GS "{dll_src}" /Fo"{work}\\\\" /Fe"{work}\\vf2fun.dll" '
        f"/link kernel32.lib /DYNAMICBASE /NXCOMPAT || exit /b 1",
        f'cl /nologo /O1 /MT /W3 "{RUNTIME / "tests" / "stage1_harness.cpp"}" /Fo"{work}\\\\" '
        f'/Fe"{work}\\stage1_harness.exe" /link /BASE:0x30000000 /FIXED /DYNAMICBASE:NO kernel32.lib || exit /b 1',
    ], work)
    assert (work / "vf2fun.dll").is_file() and (work / "stage1_harness.exe").is_file()
    (work / "patched.exe").write_bytes(P.patch_executable(vanilla))
    return work


def _harness(built: Path, setting: str | None, with_dll: bool = True) -> list[dict]:
    run = built / f"run-{setting}-{with_dll}"
    if run.exists():
        shutil.rmtree(run)
    run.mkdir()
    shutil.copy2(built / "stage1_harness.exe", run)
    files = run / S.PATCHER_FOLDER
    files.mkdir()
    if with_dll:
        shutil.copy2(built / "vf2fun.dll", files / S.DLL_NAME)
    if setting is not None:
        P.write_settings(files / S.INI_NAME, setting == "on")
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


def _sites(rows):
    return {r["site"]: r for r in rows if "site" in r and "bytes" in r}


def test_setting_off_writes_nothing(off):
    status = _one(off, "status")
    assert status["allow"] == 0 and status["mask"] == 0 and status["trampoline"] == 0
    for va, row in _sites(off).items():
        pin = next(p for p in S.PINS if p.va == va and p.role != "context")
        assert bytes.fromhex(row["bytes"]) == pin.expected
        assert row["protect"] == "RX"
    assert _one(off, "wx_regions")["wx_regions"] == 0


def test_installed_bytes_trampoline_and_protections(on):
    status = _one(on, "status")
    assert status["allow"] == 1 and status["pins"] == 1 and status["mask"] == 0b111111
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
    for row in sites.values():
        assert row["protect"] == "RX", "game code left writable"

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
