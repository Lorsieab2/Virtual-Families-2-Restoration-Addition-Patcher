"""Time Controls for the B200 executable (companion DLL vf2time_b200.dll).

Layers (nothing here starts the game; there is no live test):

* always: the committed site header is the sites module, every pin is whole
  bytes, the layout constants are the decided ones;
* with the B200 core executable (VF2_B200_CORE_EXE = `Virtual Families 2 - B200.exe`
  of the core variant): capstone + pefile prove every pin (gen_b200_time_sites),
  the header is a fresh render, and a damaged executable is refused;
* with the core executable AND Visual Studio (VF2_VCVARS32): the DLL builds with
  /W4 /WX, and the REAL compiled DLL runs inside unicorn together with the REAL
  B200 code (tests/b200_time_emu.py, tests/b200_time_scenarios.py), once at the
  link address and once relocated, and every mutation of the module source makes
  those scenarios fail.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
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
NATIVE = RUNTIME / "native"
SRC = NATIVE / "b200time"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import b200_time_sites as S  # noqa: E402
import gen_b200_time_sites as G  # noqa: E402

CORE_EXE = os.environ.get("VF2_B200_CORE_EXE")
VCVARS = os.environ.get("VF2_VCVARS32")
DELTAS = (0, 0x1A0000)


def core_exe_bytes() -> bytes:
    if not CORE_EXE or not Path(CORE_EXE).is_file():
        pytest.skip("VF2_B200_CORE_EXE is not set to the B200 core executable")
    return Path(CORE_EXE).read_bytes()


def need_vs():
    if not VCVARS or not Path(VCVARS).is_file():
        pytest.skip("VF2_VCVARS32 is not set to vcvars32.bat")
    core_exe_bytes()


# ===================================================================== always
def test_header_pins_are_the_sites_module():
    header = (SRC / "b200time_sites.h").read_text()
    for pin in S.PINS:
        m = re.search(r"static const unsigned char pin_%s\[\] = \{ ([^}]*) \};" % re.escape(pin.name), header)
        assert m, pin.name
        got = bytes(int(x, 16) for x in m.group(1).split(", "))
        assert got == pin.bytes, pin.name
        assert re.search(r'\{ "%s", 0x%Xu, %du, pin_%s,' % (re.escape(pin.name), pin.va, len(pin.bytes), pin.name),
                         header), pin.name
    for key in ("TIME_BUTTON_ID", "OPTIONS_TIME_X", "SET_SPEED", "GAME_TIME", "OPTIONS_CTOR_LAST_CALL",
                "TIMEFLOW_INCREMENT_AGE_CALL", "OPTIONS_SLOT_HANDLE_MESSAGE"):
        assert "#define B200TC_%s 0x%Xu" % (key, getattr(S, key)) in header


def test_layout_decision_constants():
    # docs/b200-time-controls-pins.md: button at (30, 434), id 9, Evict x = 0x1D2, ctor 0x4A5D00..0x4A6247
    assert S.OPTIONS_TIME_X == 30 and S.TIME_BUTTON_ID == 9
    assert S.OPTIONS_BUTTON_BOTTOM_MARGIN == 0x1E
    assert 0x1F2 - S.OPTIONS_BUTTON_BOTTOM_MARGIN - 34 == 434
    assert S.OPTIONS_DIALOG_VTABLE == 0x5006D8 and S.OPTIONS_HANDLE_MESSAGE == 0x4A6940
    assert S.OPTIONS_SLOT_HANDLE_MESSAGE == 0x5006E4
    assert S.CONTROL_SET_CHECKED == 0x47EA50 and S.OPTIONS_CTOR_LAST_CALL == 0x4A621B
    assert S.TIMEFLOW_INCREMENT_AGE_CALL == 0x4C4DEF and S.INCREMENT_AGE == 0x4C4080
    assert S.GAME_STATE_LOAD == 0x499DC0 and S.GAME_STATE_SAVE == 0x49AA00
    assert 0x4A5D00 <= S.OPTIONS_CTOR_LAST_CALL < 0x4A6247


def test_all_ids_the_dialog_uses_are_free():
    # the dialog's own controls are 2 (Done), 3, 4 (Evict) and the check boxes 5..8
    assert S.TIME_BUTTON_ID not in (2, 3, 4, 5, 6, 7, 8)


def test_the_source_has_no_hard_coded_game_address():
    # every game address must go through A() so the relocated image works
    text = (SRC / "b200time_time.inc").read_text() + (SRC / "b200time.cpp").read_text()
    text = re.sub(r"//[^\n]*", "", text)                    # comments may quote addresses
    text = re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)           # so may log formats
    found = re.findall(r"0x[0-9A-Fa-f]{5,6}\b", text)
    assert not found, f"literal addresses in the module source: {found}"


# ===================================================================== with the core exe
def test_every_site_is_proved_against_the_b200_executable():
    G.validate(core_exe_bytes())


def test_committed_header_is_a_fresh_render():
    assert (SRC / "b200time_sites.h").read_text() == G.render_header(core_exe_bytes())


def test_the_image_really_is_relocated():
    import pefile
    pe = pefile.PE(data=core_exe_bytes(), fast_load=True)
    assert pe.OPTIONAL_HEADER.DllCharacteristics & 0x40, "DYNAMICBASE"
    assert G.relocated_fields(core_exe_bytes()), "has a .reloc table"
    # and the sites module is aware: its relocated fields include a vtable slot and absolute immediates
    fields = G.relocated_fields(core_exe_bytes())
    assert S.OPTIONS_SLOT_HANDLE_MESSAGE in fields and S.GAME_STATE_SLOT_SAVE in fields
    assert any(f in fields for f in range(0x4A5F32, 0x4A6068))


@pytest.mark.parametrize("pin", S.PINS, ids=[p.name for p in S.PINS])
def test_a_damaged_executable_is_refused(pin):
    exe = bytearray(core_exe_bytes())
    img = G.gen_sites.Image(bytes(exe))
    rva = pin.va - img.base
    sec = next(s for s in img.sections if s[1] <= rva < s[1] + s[2])
    off = sec[3] + rva - sec[1]
    exe[off] ^= 0x01
    with pytest.raises(G.SiteError):
        G.validate(bytes(exe))


def test_wrong_constants_are_refused(monkeypatch):
    exe = core_exe_bytes()
    for name, value in (("SET_SPEED", S.SET_SPEED + 0x10), ("GAME_TIME", S.GAME_TIME + 4),
                        ("VILLAGER_MANAGER", S.VILLAGER_MANAGER + 4), ("GAME_STATE_INSTANCE_PTR", 0x685A8C),
                        ("OPTIONS_TEXT_COLOUR", S.OPTIONS_TEXT_COLOUR + 4), ("VILLAGER_STRIDE", S.VILLAGER_STRIDE + 4),
                        ("GAME_STATE_SPEED_FIELD", 0x25B1C), ("BUTTON_CTOR", S.BUTTON_CTOR + 0x10)):
        original = getattr(S, name)
        monkeypatch.setattr(S, name, value)
        # CROSS_CHECKS captured the constants at import; rebuild them for the changed one
        import importlib
        try:
            importlib.reload(G)
            with pytest.raises(G.SiteError):
                G.validate(exe)
        finally:
            monkeypatch.setattr(S, name, original)
            importlib.reload(G)


# ===================================================================== build
def _cl(src_dir: Path, out_dir: Path, name: str, defs: str, warn: str = "/W4 /WX") -> subprocess.CompletedProcess:
    out_dir.mkdir(parents=True, exist_ok=True)
    bat = out_dir / f"{name}.bat"
    bat.write_text(
        "@echo off\r\n"
        f'call "{VCVARS}" >nul || exit /b 1\r\n'
        f'cl /nologo /O2 /MT /EHsc {warn} {defs} /LD /GS "{src_dir / "b200time.cpp"}" '
        f'/Fo"{out_dir}\\{name}.obj" /Fe"{out_dir}\\{name}.dll" '
        "/link kernel32.lib /DYNAMICBASE /NXCOMPAT /SAFESEH:NO /MANIFEST:EMBED\r\n"
        "exit /b %ERRORLEVEL%\r\n")
    return subprocess.run(["cmd", "/c", str(bat)], capture_output=True, text=True, cwd=str(out_dir))


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    """The shipped build script's two outputs (runtime/build is git-ignored)."""
    need_vs()
    env = dict(os.environ, VF2_VCVARS32=VCVARS)
    outs = {}
    for variant, dll in (("", "vf2time_b200.dll"), ("test", "vf2time_b200_test.dll")):
        target = RUNTIME / "build" / dll
        if target.exists():
            target.unlink()
        r = subprocess.run(["cmd", "/c", str(NATIVE / "build_b200time.bat"), variant], env=env,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert target.is_file()
        outs[variant or "release"] = target
    return outs


def test_the_dll_builds_clean_with_w4_wx(built):
    import pefile
    pe = pefile.PE(str(built["release"]))
    exports = {e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols}
    assert exports == {"B200Time_Startup", "B200Time_Status"}, "no test entry point may ship"
    imports = {d.dll.decode().lower() for d in pe.DIRECTORY_ENTRY_IMPORT}
    assert imports == {"kernel32.dll", "user32.dll"}
    assert pe.OPTIONAL_HEADER.DllCharacteristics & 0x40, "ASLR"
    test_pe = pefile.PE(str(built["test"]))
    test_exports = {e.name.decode() for e in test_pe.DIRECTORY_ENTRY_EXPORT.symbols}
    assert {"B200Time_TestPlan", "B200Time_TestTime"} <= test_exports


# ===================================================================== under unicorn
def _scen():
    pytest.importorskip("unicorn")
    pytest.importorskip("pefile")
    import b200_time_scenarios as scen
    return scen


def _run(scen, dll, delta, fn, installed):
    w = scen.World(CORE_EXE, str(dll), delta, install=installed)
    if not installed:
        w.test_plan(False)
    fn(w)


def _names(group):
    try:
        import b200_time_scenarios as scen
    except ImportError:          # unicorn / pefile missing: the tests below skip
        return []
    return [f.__name__ for f in getattr(scen, group)]


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", [n for n in _names("ALL")])
def test_installed_scenarios(built, name, delta):
    scen = _scen()
    _run(scen, built["test"], delta, getattr(scen, name), True)


@pytest.mark.parametrize("delta", DELTAS, ids=["at_link_address", "relocated"])
@pytest.mark.parametrize("name", [n for n in _names("STOCK") + _names("OFF")])
def test_setting_off_is_stock(built, name, delta):
    scen = _scen()
    _run(scen, built["test"], delta, getattr(scen, name), False)


def test_the_plan_is_five_writes_and_off_is_none(built):
    scen = _scen()
    w = scen.World(CORE_EXE, str(built["test"]), 0, install=False)
    status, writes = w.test_plan(False)
    assert (status, writes) == (0, [])
    status, writes = w.test_plan(True)
    assert status == 1 and len(writes) == 5
    assert sorted(x["len"] for x in writes) == [4, 4, 4, 5, 5]


# ===================================================================== mutations
# Each entry: (name, file, old text, new text). The module source is copied, the one change is made
# (it must match exactly once), the harness DLL is rebuilt from the copy, and the scenarios must FAIL.
MUTATIONS = [
    ("button x", "b200time_time.inc", "{ (int)B200TC_OPTIONS_TIME_X,", "{ (int)B200TC_OPTIONS_TIME_X + 1,"),
    ("button y margin", "b200time_time.inc", "- (int)B200TC_OPTIONS_BUTTON_BOTTOM_MARGIN };",
     "- (int)B200TC_OPTIONS_BUTTON_BOTTOM_MARGIN - 1 };"),
    ("button id", "b200time_time.inc", "static const int kTimeButtonId = B200TC_TIME_BUTTON_ID;",
     "static const int kTimeButtonId = B200TC_TIME_BUTTON_ID + 1;"),
    ("button art", "b200time_time.inc", "GetImageGrid(GraphicsGet(), B200TC_OPTIONS_BUTTON_IMAGE)",
     "GetImageGrid(GraphicsGet(), B200TC_OPTIONS_BUTTON_IMAGE + 1)"),
    ("button text colour", "b200time_time.inc", "ButtonSetText(button, kTimeButtonText, colour, colour, colour, font);",
     "ButtonSetText(button, kTimeButtonText, colour, colour, 0, font);"),
    ("button font from the wrong field", "b200time_time.inc",
     "GetEvictFont(*(void **)(dialog + B200TC_OPTIONS_STRING_MANAGER_FIELD))",
     "GetEvictFont(*(void **)(dialog + B200TC_OPTIONS_STRING_MANAGER_FIELD + 4))"),
    ("button not added", "b200time_time.inc", "    AddControl(dialog, button);\n}", "}"),
    ("ctor stub forgets SetChecked", "b200time_time.inc", "        call dword ptr [NativeSetChecked]\n", ""),
    ("ctor stub wrong dialog register", "b200time_time.inc", "        push ebx\n        call AddTimeButton",
     "        push esi\n        call AddTimeButton"),
    ("ctor stub leaks stack", "b200time_time.inc", "        add esp, 4\n        ret 4", "        ret 4"),
    ("handler: wrong message", "b200time_time.inc", "message == B200TC_MESSAGE_BUTTON_CLICKED && param == kTimeButtonId",
     "message >= B200TC_MESSAGE_BUTTON_CLICKED && param == kTimeButtonId"),
    ("handler: any id opens it", "b200time_time.inc", "&& param == kTimeButtonId) {", "&& param >= 2) {"),
    ("handler: never forwards", "b200time_time.inc", "    return NativeOptionsHandleMessage(dialog, message, param);",
     "    return false;"),
    ("handler: opens without owner", "b200time_time.inc", "ShowTimeControls(GetActiveWindow());", "ShowTimeControls(0);"),
    ("plan: no constructor retarget", "b200time_time.inc",
     "    plan.Retarget(B200TC_OPTIONS_CTOR_LAST_CALL, (const void *)&OptionsCtorLastCall);\n", ""),
    ("plan: no HandleMessage slot", "b200time_time.inc",
     "    plan.Slot(B200TC_OPTIONS_SLOT_HANDLE_MESSAGE, (const void *)&OptionsHandleMessage);\n", ""),
    ("plan: no aging retarget", "b200time_time.inc",
     "    plan.Retarget(B200TC_TIMEFLOW_INCREMENT_AGE_CALL, (const void *)&IncrementAgeWithWarp);\n", ""),
    ("plan: Save and Load swapped", "b200time_time.inc",
     "plan.Slot(B200TC_GAME_STATE_SLOT_SAVE, (const void *)&GameStateSaveSlot);",
     "plan.Slot(B200TC_GAME_STATE_SLOT_SAVE, (const void *)&GameStateLoadSlot);"),
    ("plan: Load slot missing", "b200time_time.inc",
     "    plan.Slot(B200TC_GAME_STATE_SLOT_LOAD, (const void *)&GameStateLoadSlot);\n", ""),
    ("warp: ticks not added", "b200time_time.inc", "    return ticks + warp;", "    return ticks;"),
    ("warp: ticks added twice", "b200time_time.inc", "    return ticks + warp;", "    return ticks + 2 * warp;"),
    ("warp: villager never marked done", "b200time_time.inc", "    WarpPending &= ~bit;\n    int warp",
     "    int warp"),
    ("warp: wrong length", "b200time_time.inc", "3 * B200TC_TICKS_PER_YEAR", "2 * B200TC_TICKS_PER_YEAR"),
    ("warp: left-home villagers eligible", "b200time_time.inc", "!v[B200TC_VILLAGER_LEFT_HOME_OFFSET] &&", ""),
    ("warp: dead villagers eligible", "b200time_time.inc",
     " &&\n           *(const int *)(v + B200TC_VILLAGER_HEALTH_OFFSET) > 0;", ";"),
    ("warp: wrong age offset", "b200time_time.inc", "B200TC_VILLAGER_ARRAY_OFFSET + B200TC_VILLAGER_AGE_OFFSET;",
     "B200TC_VILLAGER_ARRAY_OFFSET + B200TC_VILLAGER_AGE_OFFSET + 4;"),
    ("warp: aging wrapper ignores the warp", "b200time_time.inc", "NativeIncrementAge(age, WarpTicksFor(age, ticks));",
     "NativeIncrementAge(age, ticks);"),
    ("warp: load keeps the queue", "b200time_time.inc", "    WarpPending = 0;\n    WarpTicks = 0;\n    int *field = (int *)",
     "    int *field = (int *)"),
    ("pause: does not pause the clock", "b200time_time.inc", "    SetSpeed(GameTime, B200TC_PAUSED_OFFSET);\n    *field +=",
     "    *field +="),
    ("pause: wrong offset", "b200time_time.inc", "    *field += B200TC_PAUSED_OFFSET;", "    *field += B200TC_PAUSED_OFFSET - 1;"),
    ("resume: zero speed not normalised", "b200time_time.inc", "    if (speed <= 0) speed = B200TC_SPEED_NORMAL;\n    SetSpeed",
     "    SetSpeed"),
    ("resume: clock not restarted", "b200time_time.inc", "    SetSpeed(GameTime, speed);\n    *field = speed;\n}\n\nstatic void ChooseSpeed",
     "    *field = speed;\n}\n\nstatic void ChooseSpeed"),
    ("speed: paused choice runs the clock", "b200time_time.inc",
     "        *field = (int)B200TC_PAUSED_OFFSET + speed;  // stays paused; Resume restores this speed\n        return;",
     "        SetSpeed(GameTime, speed);\n        *field = speed;\n        return;"),
    ("speed: field not stored", "b200time_time.inc", "    SetSpeed(GameTime, speed);\n    *field = speed;\n}\n\n// -----",
     "    SetSpeed(GameTime, speed);\n}\n\n// -----"),
    ("speed: Fast is Slow", "b200time_time.inc", "case ID_TC_FAST: ChooseSpeed(B200TC_SPEED_FAST);",
     "case ID_TC_FAST: ChooseSpeed(B200TC_SPEED_SLOW);"),
    ("speed: 10x is 5x", "b200time_time.inc", "case ID_TC_X10: ChooseSpeed(B200TC_SPEED_10X);",
     "case ID_TC_X10: ChooseSpeed(B200TC_SPEED_5X);"),
    ("dialog: warp without asking", "b200time_time.inc", "== IDYES)\n                StartTimeWarp(kWarpTicks);",
     "== IDYES || true)\n                StartTimeWarp(kWarpTicks);"),
    ("dialog: status shows the wrong speed", "b200time_time.inc", 'speed == (int)B200TC_SPEED_FAST ? L"fast"',
     'speed == (int)B200TC_SPEED_FAST ? L"slow"'),
    ("save: clock not rebased", "b200time_time.inc", "    if (running) SetSpeed(GameTime, B200TC_SPEED_NORMAL);\n", ""),
    ("save: speed not put back", "b200time_time.inc", "    *field = live;\n    return ok;", "    return ok;"),
    ("save: clock not put back", "b200time_time.inc", "    if (running) SetSpeed(GameTime, live);\n", ""),
    ("save: slot 0 touched", "b200time_time.inc", "int *field = state && slot ?", "int *field = state ?"),
    ("save: stock speed rewritten", "b200time_time.inc", "if (!field || StockSpeedValue(live)) return",
     "if (!field) return"),
    ("save: paused saved running", "b200time_time.inc",
     "*field = paused ? (int)(B200TC_PAUSED_OFFSET + B200TC_SPEED_NORMAL) : (int)B200TC_SPEED_NORMAL;",
     "*field = B200TC_SPEED_NORMAL;"),
    ("load: clock not rebased", "b200time_time.inc", "        *field = B200TC_SPEED_NORMAL;\n        SetSpeed(GameTime, B200TC_SPEED_NORMAL);",
     "        *field = B200TC_SPEED_NORMAL;"),
    ("load: paused loaded running", "b200time_time.inc",
     "        *field = (int)(B200TC_PAUSED_OFFSET + B200TC_SPEED_NORMAL);  // stays paused; Resume runs at normal",
     "        *field = B200TC_SPEED_NORMAL;"),
    ("load: failed load still changes", "b200time_time.inc", "    if (!ok || !slot || !state) return ok;",
     "    if (!slot || !state) return ok;"),
    ("load: stock value rewritten", "b200time_time.inc", "    if (StockSpeedValue(*field)) return ok;\n    if (*field >=",
     "    if (*field >="),
    ("pins: no comparison", "b200time.cpp", "            if (tmp[i] != pin.bytes[i]) {", "            if (false) {"),
    ("pins: relocation ignored", "b200time.cpp", "            v -= Delta;\n", ""),
    ("pins: only the first is checked", "b200time.cpp", "    for (size_t p = 0; p < sizeof(B200_PINS) / sizeof(B200_PINS[0]); ++p) {",
     "    for (size_t p = 0; p < 1; ++p) {"),
    ("setting off still plans", "b200time.cpp", "    if (!enabled) return 0;\n", ""),
    ("abi: wrong delta for calls", "b200time_time.inc", "SetSpeed = (SetSpeedFn)A(B200TC_SET_SPEED);",
     "SetSpeed = (SetSpeedFn)B200TC_SET_SPEED;"),
]


def _mutant_dll(work: Path, name: str, rel: str, old: str, new: str) -> Path:
    src = work / "src"
    shutil.copytree(SRC, src)
    path = src / rel
    text = path.read_text()
    assert text.count(old) == 1, f"mutation {name!r}: the original text matches {text.count(old)} times"
    path.write_text(text.replace(old, new))
    r = _cl(src, work / "out", "mutant", "/DB200TIME_TEST", warn="/W1")
    assert r.returncode == 0, f"mutation {name!r} does not compile:\n{r.stdout}\n{r.stderr}"
    return work / "out" / "mutant.dll"


def _scenarios_fail(dll: Path) -> str | None:
    """Run every scenario at both deltas; return the first failure's text, or None if all passed."""
    scen = _scen()
    for delta in DELTAS:
        for fn in scen.ALL:
            try:
                _run(scen, dll, delta, fn, True)
            except BaseException as e:  # noqa: BLE001  (an assertion or an emulator error both count)
                return f"{fn.__name__} @ {delta:#x}: {type(e).__name__}"
        for fn in scen.STOCK + scen.OFF:
            try:
                _run(scen, dll, delta, fn, False)
            except BaseException as e:  # noqa: BLE001
                return f"{fn.__name__} @ {delta:#x}: {type(e).__name__}"
    return None


def test_the_unmutated_module_passes_the_same_check(built):
    # the mutation harness must be able to say "all passed"
    assert _scenarios_fail(built["test"]) is None


def test_every_mutation_is_caught(built, tmp_path):
    need_vs()
    _scen()
    # build all mutants in parallel, then judge each one
    def build(i_m):
        i, (name, rel, old, new) = i_m
        return name, _mutant_dll(tmp_path / f"m{i:02d}", name, rel, old, new)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        dlls = list(pool.map(build, enumerate(MUTATIONS)))
    survivors = []
    for name, dll in dlls:
        verdict = _scenarios_fail(dll)
        if verdict is None:
            survivors.append(name)
    assert not survivors, "mutations the scenarios did not catch: " + ", ".join(survivors)
