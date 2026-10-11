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

--set-age is a write: it sets one villager's internal age (years * 20)
so a 50+ couple or a 60-year-old can be produced at once. --set-achievement
(ID FLAG PROGRESS) writes one achievement record and --queue-achievement ID
puts an id in the notify queue so the game shows that goal's popup (ID 0x5F is
the experimental Ornamentologist row). All writes refuse unless the target
executable's file name contains "Test", so they can never touch the owner's own
game. The game saves only on a clean quit, so a written value reaches that test
copy's own save folder only if the test quits cleanly.
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


# vf2fun.cpp's VF2Fun_Status block, layout version 2 (then writeMasks[16]).
STATUS_FIELDS = ("magic", "version", "moduleCount", "requestedMask", "pinsOkMask", "installedMask",
                 "refusedMask", "trampolinePage")
# VF2Fun_TestCounters: exported by TEST builds only (VF2FUN_TEST_COUNTERS).
COUNTER_FIELDS = ("magic", "chanceCalls", "olderRolls", "olderSuccesses", "cooldownStores", "cooldownSkips",
                  "nextGenerationCalls", "nextGenerationOlderGrants", "lastMotherAge", "lastFatherAge",
                  "sceneActiveWrites", "sceneNullSkips", "timeButtonsAdded", "timeDialogOpens", "timeWarpsApplied")


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
        if pin.role in ("context", "data"):
            continue
        live = p.read(pin.va, len(pin.expected))
        if live == pin.expected:
            what = "vanilla (not installed)"
        elif pin.role == "field":
            # Only the displacement/immediate is rewritten, in place.
            off, size = pin.field
            what = f"field retargeted to {int.from_bytes(live[off:off + size], 'little'):#x}"
        else:
            rel = struct.unpack_from("<i", live, 1)[0]
            what = f"{'jmp' if live[0] == 0xE9 else 'call' if live[0] == 0xE8 else '??'} {pin.va + 5 + rel:#x}"
        sites[pin.name] = f"{pin.va:#x}: {live.hex()} -> {what}"
    out["sites"] = sites
    if module and path:
        rva = export_rva(Path(path), "VF2Fun_Status")
        raw = p.read(module + rva, 4 * (len(STATUS_FIELDS) + 16))
        values = struct.unpack(f"<{len(STATUS_FIELDS) + 16}I", raw)
        status = dict(zip(STATUS_FIELDS, values))
        status["writeMasks"] = list(values[len(STATUS_FIELDS):len(STATUS_FIELDS) + len(S.MODULES)])
        modules = {}
        for i, m in enumerate(S.MODULES):
            bit = 1 << i
            modules[m.key] = ("installed" if status["installedMask"] & bit else
                              "REFUSED" if status["refusedMask"] & bit else
                              "off" if not status["requestedMask"] & bit else "?")
        status["modules"] = modules
        out["status"] = status
        try:
            crva = export_rva(Path(path), "VF2Fun_TestCounters")
        except KeyError:
            pass  # a release build: no counters
        else:
            raw = p.read(module + crva, 4 * len(COUNTER_FIELDS))
            out["counters"] = dict(zip(COUNTER_FIELDS, struct.unpack(f"<{len(COUNTER_FIELDS)}I", raw)))
    # Achievement table state: where the stock readers point now, the records, the notify queue.
    ach = S.ACHIEVEMENT_OBJECT
    rows_base = p.u32(S.PIN_BY_NAME["ach_rows_target_div"].field_va) - 4
    order_base = p.u32(S.PIN_BY_NAME["scene_draw_order_base"].field_va)
    count = p.read(S.PIN_BY_NAME["scene_draw_count"].field_va, 1)[0]
    order = [p.u32(order_base + 4 * i) for i in range(min(count, 0xC0))]
    out["achievements"] = {
        "rows_base": hex(rows_base), "rows_moved": rows_base != S.ACH_LIST_BASE,
        "order_base": hex(order_base), "order_count": count,
        "order_around_0x5E": order[0x4C:0x52],
        "records": {hex(i): {"flag": p.read(ach + i * 12, 1)[0], "progress": p.i32(ach + i * 12 + 4),
                             "stamp": p.i32(ach + i * 12 + 8)} for i in (0x5D, 0x5E, 0x5F, 0x60)},
        "notify_queue": [p.i32(ach + 0xDBC + 4 * i) for i in range(3)],
        "row_0x5F": p.read(rows_base + 0x5F * S.ACH_ROW_SIZE, S.ACH_ROW_SIZE).hex() if rows_base != S.ACH_LIST_BASE else None,
    }
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
        # Time Controls: the speed field in theGameState (>= 999 = paused, else
        # 10 normal / 5 = 2x / 2 = 5x / 1 = 10x) and CGameTime's own (0 = paused).
        out["speed"] = {"field": p.i32(gs + S.PAUSE_FIELD), "game_time": p.i32(S.GAME_TIME + 0x20)}
    return out


def show(snap: dict) -> None:
    print(f"stub: {snap['stub']}")
    for name, line in snap["sites"].items():
        print(f"  {name:32} {line}")
    if "status" in snap:
        s = snap["status"]
        print("status: " + ", ".join(f"{k}={hex(v) if k in ('magic', 'trampolinePage') else v}"
                                     for k, v in s.items() if k != "modules"))
        for key, state in s["modules"].items():
            print(f"  module {key:24} {state}")
    if "counters" in snap:
        print("test counters: " + ", ".join(f"{k}={v}" for k, v in snap["counters"].items() if k != "magic"))
    for v in snap["villagers"]:
        print(f"  villager {v['index']:2}: {v['gender']:6} age {v['years']:3} ({v['internal_age']}) "
              f"health {v['health']} fertility {v['fertility']} departed {v['departed']}")
    print(f"family tree generation: {snap['family_tree_generation']}")
    if "try_for_baby" in snap:
        print(f"try-for-baby: {snap['try_for_baby']}")
    if "speed" in snap:
        print(f"speed: {snap['speed']}")
    if "achievements" in snap:
        print(f"achievements: {snap['achievements']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe-name", required=True)
    ap.add_argument("--watch", type=float, default=0.0, help="poll every SECONDS")
    ap.add_argument("--count", type=int, default=1, help="number of polls (bounded)")
    ap.add_argument("--set-age", nargs=2, type=int, metavar=("INDEX", "YEARS"))
    ap.add_argument("--set-achievement", nargs=3, type=lambda v: int(v, 0), metavar=("ID", "FLAG", "PROGRESS"))
    ap.add_argument("--queue-achievement", type=lambda v: int(v, 0), metavar="ID")
    args = ap.parse_args()
    pid = find_pid(args.exe_name)
    if args.set_achievement or args.queue_achievement is not None:
        if "test" not in args.exe_name.lower():
            raise SystemExit("achievement writes only work on a test copy (exe name must contain 'Test')")
        p = Process(pid, write=True)
        if args.set_achievement:
            ident, flag, progress = args.set_achievement
            if not (0 <= ident < S.ACH_RECORD_COUNT and flag in (0, 1) and 0 <= progress <= 100000):
                raise SystemExit("id 0-0x124, flag 0 or 1, progress 0-100000")
            rec = S.ACHIEVEMENT_OBJECT + ident * S.ACH_RECORD_SIZE
            p.write(rec, bytes([flag]))
            p.write(rec + 4, struct.pack("<i", progress))
            print(f"achievement {ident:#x}: flag {flag}, progress {progress}")
        if args.queue_achievement is not None:
            ident = args.queue_achievement
            if not (0 <= ident < S.ACH_RECORD_COUNT):
                raise SystemExit("id 0-0x124")
            queue = S.ACHIEVEMENT_OBJECT + 0xDBC
            for slot in range(0x5F):
                if p.i32(queue + 4 * slot) == -1:
                    p.write(queue + 4 * slot, struct.pack("<i", ident))
                    print(f"achievement {ident:#x} queued for the popup in slot {slot}")
                    break
            else:
                raise SystemExit("the notify queue is full")
        return 0
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
