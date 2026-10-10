#!/usr/bin/env python3
"""Read-only live probe for the Stage 1 runtime module.

    probe_stage1.py --exe-name "VF2 Runtime Test.exe" [--watch SECONDS --count N]
    probe_stage1.py --exe-name "VF2 Runtime Test.exe" --set-age INDEX YEARS

Attaches to a running patched game with PROCESS_VM_READ only (no debugger, no
suspension) and prints:

* the loader stub's state and the DLL it loaded (from the .vf2fud section);
* the bytes now at every hook site, decoded (vanilla bytes = not installed);
* the DLL's VF2Fun_Status block (setting, pins, installed mask, trampoline and
  the Stage 1 counters: ChanceOfPregnancy calls, late-age rolls/successes,
  cooldown stores/skips, next-generation calls/older grants);
* every active villager slot (index, gender, internal age, years, health,
  departed), the Family Tree generation, and the try-for-baby deadline
  (theGameState+0x25AE0) as seconds remaining on the game's own clock.

--set-age is the ONLY write: it sets one villager's internal age (years * 20)
so a 50+ couple or a 60-year-old can be produced at once. It refuses unless
the target executable's file name contains "Test", so it can never touch the
owner's own game. The game saves only on a clean quit, so a written age
reaches that test copy's own save folder only if the test quits cleanly.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import struct
import sys
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))
import vf2_runtime_sites as S  # noqa: E402

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
TH32CS_SNAPPROCESS = 0x2
GAME_START_TIME64 = 0x52D268  # GetSecondsFromGameStart = _time64() - [0x52D268]

k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def find_pid(exe_name: str) -> int:
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    pids = []
    ok = k32.Process32FirstW(snap, ctypes.byref(entry))
    while ok:
        if entry.szExeFile.lower() == exe_name.lower():
            pids.append(entry.th32ProcessID)
        ok = k32.Process32NextW(snap, ctypes.byref(entry))
    k32.CloseHandle(snap)
    if len(pids) != 1:
        raise SystemExit(f"expected one running {exe_name!r}, found {len(pids)}")
    return pids[0]


class Process:
    def __init__(self, pid: int, write: bool = False):
        access = PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ
        if write:
            access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        self.h = k32.OpenProcess(access, False, pid)
        if not self.h:
            raise SystemExit(f"OpenProcess failed: {ctypes.get_last_error()}")

    def read(self, va: int, n: int) -> bytes:
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(self.h, ctypes.c_void_p(va), buf, n, ctypes.byref(got)) or got.value != n:
            raise OSError(f"read {va:#x}+{n} failed ({ctypes.get_last_error()})")
        return buf.raw

    def u32(self, va: int) -> int:
        return struct.unpack("<I", self.read(va, 4))[0]

    def i32(self, va: int) -> int:
        return struct.unpack("<i", self.read(va, 4))[0]

    def write(self, va: int, data: bytes) -> None:
        got = ctypes.c_size_t()
        if not k32.WriteProcessMemory(self.h, ctypes.c_void_p(va), data, len(data), ctypes.byref(got)) or got.value != len(data):
            raise OSError(f"write {va:#x} failed ({ctypes.get_last_error()})")


STATUS_FIELDS = ("magic", "version", "allowOlderPregnancies", "pinsMatched", "installedMask", "trampoline",
                 "chanceCalls", "olderRolls", "olderSuccesses", "cooldownStores", "cooldownSkips",
                 "nextGenerationCalls", "nextGenerationOlderGrants", "lastMotherAge", "lastFatherAge")


def export_rva(dll_path: Path, name: str) -> int:
    data = dll_path.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    opt = pe + 24
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    secs = [struct.unpack_from("<IIII", data, opt + optsz + i * 40 + 8) for i in range(nsec)]

    def off(rva):
        for vs, va, rs, raw in secs:
            if va <= rva < va + max(vs, rs):
                return raw + rva - va
        raise KeyError(rva)

    exp_rva = struct.unpack_from("<I", data, opt + 96)[0]
    e = off(exp_rva)
    nnames, funcs, names, ords = struct.unpack_from("<IIII", data, e + 24)
    for i in range(nnames):
        n_rva = struct.unpack_from("<I", data, off(names) + 4 * i)[0]
        s = data[off(n_rva):data.index(b"\0", off(n_rva))].decode()
        if s == name:
            ordinal = struct.unpack_from("<H", data, off(ords) + 2 * i)[0]
            return struct.unpack_from("<I", data, off(funcs) + 4 * ordinal)[0]
    raise KeyError(name)


def snapshot(p: Process) -> dict:
    out = {}
    state, startup, module = p.u32(S.STUB_DATA_VA), p.u32(S.STUB_DATA_VA + 4), p.u32(S.STUB_DATA_VA + 8)
    path = p.read(S.STUB_DATA_VA + 16, 2048).decode("utf-16-le").split("\0")[0]
    out["stub"] = {"state": {0: "not run", 1: "DLL loaded", 2: "failed (stock game)"}.get(state, state),
                   "startup": hex(startup), "module": hex(module), "dll_path": path}
    sites = {}
    for pin in S.PINS:
        if pin.role == "context":
            continue
        live = p.read(pin.va, len(pin.expected))
        if live == pin.expected:
            what = "vanilla (not installed)"
        else:
            rel = struct.unpack_from("<i", live, 1)[0]
            what = f"{'jmp' if live[0] == 0xE9 else 'call' if live[0] == 0xE8 else '??'} {pin.va + 5 + rel:#x}"
        sites[pin.name] = f"{pin.va:#x}: {live.hex()} -> {what}"
    out["sites"] = sites
    if module and path:
        rva = export_rva(Path(path), "VF2Fun_Status")
        raw = p.read(module + rva, 4 * len(STATUS_FIELDS))
        out["status"] = dict(zip(STATUS_FIELDS, struct.unpack(f"<{len(STATUS_FIELDS)}I", raw)))
    villagers = []
    for i in range(30):
        v = S.VILLAGER_MANAGER + S.VILLAGER_ARRAY_OFFSET + i * S.VILLAGER_STRIDE
        active = p.read(v + 0x1BB84, 1)[0]
        if not active:
            continue
        age = p.i32(v + 0x6A54)
        villagers.append({"index": i, "gender": "female" if p.i32(v + 0x6A58) == 1 else "male",
                          "internal_age": age, "years": age // 20, "health": p.i32(v + 0x6B00),
                          # CVillagerState (+6AF4h) fertility at +4Ch: the value
                          # ChanceOfPregnancy reads for the mother and is
                          # passed for the father ([edi+6B40h] at 0x49F5DD).
                          "fertility": p.i32(v + 0x6B40),
                          "departed": p.read(v + 0x1BB88, 1)[0]})
    out["villagers"] = villagers
    out["family_tree_generation"] = p.i32(S.FAMILY_TREE + 4)
    gs = p.u32(S.GAME_STATE_INSTANCE_PTR)
    if gs:
        deadline = p.u32(gs + S.GAME_STATE_TRY_FOR_BABY_DEADLINE)
        start = struct.unpack("<q", p.read(GAME_START_TIME64, 8))[0]
        now = int(time.time()) - start
        out["try_for_baby"] = {"deadline": deadline, "game_seconds_now": now,
                               "seconds_remaining": max(0, deadline - now)}
    return out


def show(snap: dict) -> None:
    print(f"stub: {snap['stub']}")
    for name, line in snap["sites"].items():
        print(f"  {name:32} {line}")
    if "status" in snap:
        s = snap["status"]
        print("status: " + ", ".join(f"{k}={hex(v) if k in ('magic', 'trampoline') else v}" for k, v in s.items()))
    for v in snap["villagers"]:
        print(f"  villager {v['index']:2}: {v['gender']:6} age {v['years']:3} ({v['internal_age']}) "
              f"health {v['health']} fertility {v['fertility']} departed {v['departed']}")
    print(f"family tree generation: {snap['family_tree_generation']}")
    if "try_for_baby" in snap:
        print(f"try-for-baby: {snap['try_for_baby']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe-name", required=True)
    ap.add_argument("--watch", type=float, default=0.0, help="poll every SECONDS")
    ap.add_argument("--count", type=int, default=1, help="number of polls (bounded)")
    ap.add_argument("--set-age", nargs=2, type=int, metavar=("INDEX", "YEARS"))
    args = ap.parse_args()
    pid = find_pid(args.exe_name)
    if args.set_age:
        if "test" not in args.exe_name.lower():
            raise SystemExit("--set-age only works on a test copy (exe name must contain 'Test')")
        index, years = args.set_age
        if not (0 <= index < 30 and 0 <= years <= 200):
            raise SystemExit("index 0-29, years 0-200")
        p = Process(pid, write=True)
        v = S.VILLAGER_MANAGER + S.VILLAGER_ARRAY_OFFSET + index * S.VILLAGER_STRIDE
        if not p.read(v + 0x1BB84, 1)[0]:
            raise SystemExit(f"villager slot {index} is not active")
        p.write(v + 0x6A54, struct.pack("<i", years * 20))
        print(f"villager {index}: internal age set to {years * 20} ({years} years)")
        return 0
    p = Process(pid)
    for n in range(max(1, min(args.count, 1000))):
        if n:
            time.sleep(args.watch)
            print("-" * 60)
        show(snapshot(p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
