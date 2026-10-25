"""Game Speed: set a Virtual Families 2 family's saved game speed to Paused or Normal, in a closed game's saves.

Ported from the Virtual Families 1 patcher's Game Speed. Every address below is in the stock "Virtual Families 2.exe"
(SHA-256 1582d9e8...73c3), traced with capstone; the patched game is relinked from the desktop objects
(work/desktop_obj_files), and the functions named here are found in it by their object code (B202: SetSpeed 0x468BD0,
Seconds 0x468B50, LoadState 0x468A70, SaveState 0x468B10, AllVillagersTimeflowUpkeep 0x4CBD50).

Where the speed lives (VERIFIED)
    * gs+0x25B18, int, the speed option: InitOptions 10 (0x429733); the game counts >= 999 as paused (0x499843,
      0x440173, 0x440D1D, 0x49643D). It is the last field of the family save (file offset 0x25B20).
    * CGameTime (global 0x568088), saved at gs+0x163FC by SaveState 0x4278C0 and copied back word for word by
      LoadState 0x4279F0 (theGameState::Load 0x42A673; nothing after it re-derives the speed): +0 speed, +4 previous
      speed, +8 GetSecondsFromGameStart at the last speed change, +0xC game seconds banked then, +0x10
      GetSecondsFromGameStart when saved. GetSecondsFromGameStart 0x403FF0 = difftime(now, the header's start time).
    * Seconds() 0x427920: multiplier = speed / 10.0 as a float (0x427900); 0 returns +0xC unchanged, otherwise
      +0xC + trunc((now - +8) / multiplier), now < +8 clamped.

What the game's own Pause and Unpause do (VERIFIED)
    * Options "Pause Game: Yes": UpdateAll (0x42ACB0); CGameTime::SetSpeed(999) 0x42269B; gs+0x25B18 += 999
      (0x4226A6); UpdateAll. The Space bar 0x43BC71..0x43BC83 does the same without UpdateAll.
    * Options "No": UpdateAll; SetSpeed(10) 0x4226EA; gs+0x25B18 = 10 (0x4226F5); UpdateAll. The Space bar unpause
      (0x43BC3D..0x43BC5A) passes option - 999 and stores it (10 when that is 0).
    * SetSpeed 0x427A50: nothing when the new speed equals +0x20; otherwise +0xC = Seconds(), +8 = now, +4 = old
      +0x20, +0x20 = new, except 999 stores 0 (`xor ebp, ebp` 0x427A6F, stored at 0x427B74). Real saves: every
      paused family holds 1009 / clock speed 0 / previous 10.
    * Seconds() at speed 10 in the stock exe divides by exactly 1.0 (x87 at the CRT's 53-bit default,
      _controlfp_s(0, _PC_53, _MCW_PC) at 0x4C8CB5 from 0x4C3737; SDL2 2.0.3 creates its Direct3D 9 device with
      D3DCREATE_FPU_PRESERVE). The patched game's Seconds() is the SSE build of the object code: the elapsed seconds
      are rounded to a float first, which is exact only below 2^24 s (194 days). A Pause whose last speed change
      is longer ago than that, and not a whole float, would be worked out differently by the two games, so it is
      refused (no real save comes near it).
    * While paused the two-second update keeps running UpdateAll -> AllVillagersTimeflowUpkeep 0x499700: each
      active, at-home, living villager with a stamp gets now - stamp added (0x4997E9), zeroed because paused
      (0x49984F) and stamp = now (0x499872); a dead body is removed once (now - stamp) / 60 / option reaches 240
      (0x49973A..0x49978F). UpdateAll also writes gs+0x25AF4 (0x42ACF7), which nothing reads. The other pause
      checks only skip work (0x415511, 0x440BFC, 0x440D1D, 0x440DDF, 0x4412E4, 0x49643D); the stamp the paused
      main scene refreshes, gs+0x25CD4 (0x440186), is outside the save.

What this tool writes, in the slot save "Virtual Families 2<N>.ldw" only (the game never loads N+20)
    * Paused, from Normal (option 10, clock speed 10), as if paused just before the game saved (now = clock +0x10):
      clock +0xC = Seconds(), +8 = +0x10, +4 = 10, +0 = 0; option 1009.
    * Normal, from Paused (option >= 999, clock speed 0), as if the paused family were loaded now, unpaused and saved
      at once (now = this PC's clock minus the header's start time): clock +0xC unchanged, +8 = now, +4 = 0, +0 = 10,
      +0x10 = now; option 10 (Options "No"); each villager the paused update would touch gets banked seconds 0 and
      stamp = now, so the paused time is never aged in. Refused when a dead body would have been removed meanwhile,
      or this PC's clock is earlier than the save.
    Nothing else changes. Any other combination is shown with its raw values and refused.

The patcher's own Time Controls speeds, and why they are not offered here (VERIFIED)
    Source runtime/native/b200time (b200time_time.inc, b200time.cpp; constants and pins in b200time_sites.h, proved
    by runtime/tools/gen_b200_time_sites.py), exercised as the compiled vf2time_b200.dll on the real B200 code under
    emulation by tests/test_b200_time_controls.py (scenario_save_normalises_the_speed among them).
    * Time Controls (the optional time_controls setting; Settings button, id 9) sets Slow 20, Normal 10, Fast 5,
      5x 2 and 10x 1 (B200TC_SPEED_*) with the game's own CGameTime::SetSpeed (B200 0x468B80) and the same value in
      gs+0x25B18 (ChooseSpeed). Paused, it only changes the part below 999 (999 + speed). Pause / Resume are the
      Space bar's: SetSpeed(999) and += 999; resume passes option - 999 (10 when that is 0) and stores it.
    * SetSpeed for these speeds is the same as for 10: +0xC = Seconds(), +8 = now, +4 = old, +0x20 = the speed, so
      Seconds() then counts (now - +8) / (speed / 10.0). The upkeep's catch-up cap (stock 0x49980F) is 0x9538 s
      for option 5, 0x5CF8 for 20 and 0x7918 for 10 and every other value (2 and 1 included); ageing ticks are
      banked / 60 / option (0x49988D), and a dead body goes once (now - stamp) / 60 / option reaches 240 (0x49973A..0x49978F).
    * NONE OF THEM IS EVER SAVED. theGameState::Save (vtable slot 14) is wrapped from the module's first commit
      (289ef7e): any option but 10 / 1009 is saved as 10 (after SetSpeed(10)) or 1009 when paused, and the live
      speed is put back after the save; Load (slot 13) turns any such value into 10 (with SetSpeed(10)) or 1009.
    So no installed game can produce a Time Controls speed in a save, and one written there would be turned back to
    Normal at the next load by a game with Time Controls: this tool offers only Paused and Normal. A save holding
    one with a matching clock (no known build writes it) is named in words and refused. A paused save holding 999 +
    one of them is Paused; a game with Time Controls loads it as 1009, so Normal is what its unpause gives.

Safety: the game must be closed; the save folder is backed up first ("(before speed change)"); the save is written
atomically, read back, checked field by field (every other byte unchanged) and put back on any failure. No log and
no data file is written. Nothing here touches Tk.
"""
from __future__ import annotations

import os
import struct
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import vf2_rename_family as rename_family
import vf2_save_backup as save_backup
import vf2_save_reader as reader

SLOTS = tuple(reader.FAMILY_SLOTS)
BACKUP_LABEL = save_backup.BEFORE_SPEED_CHANGE
NORMAL = 10
PAUSE_ADD = 999
CLOCK_PAUSED = 0
BODY_REMOVED_AT = 240       # 0x49975F cmp eax, 0xF0
FLOAT_EXACT = 1 << 24       # the patched game's float elapsed seconds are exact below this
PAUSED = "Paused"
NORMAL_NAME = "Normal"
TARGETS = (PAUSED, NORMAL_NAME)
# The Time Controls dialog's own names for its speed values (b200time_time.inc; see the module notes). Never offered.
TIME_CONTROLS_SPEEDS = {20: "Slow", 5: "Fast", 2: "5x", 1: "10x"}
CLOCK_SIZE = 0x14
_U32 = 0xFFFFFFFF
REC_ACTIVE = 0x0            # villager+0x1BB84
REC_LEFT_HOME = 0x1         # villager+0x1BB88
REC_BANKED = 0xA8           # CVillagerState+0 (villager+0x6AF4)
REC_STAMP = 0xAC            # CVillagerState+4 (villager+0x6AF8)
REC_HEALTH = 0xB4           # CVillagerState+0xC (villager+0x6B00)


class SpeedError(Exception):
    """A speed change that was refused or failed, with a reason a player can read."""


class GameRunning(SpeedError):
    """The game that uses this save folder is running."""


@dataclass(frozen=True)
class SpeedState:
    option: int
    clock_speed: int
    clock_previous: int
    changed_at: int
    banked: int
    saved_at: int

    @property
    def kind(self) -> str:
        if self.option >= PAUSE_ADD and self.clock_speed == CLOCK_PAUSED:
            return "paused"
        if self.option == NORMAL and self.clock_speed == NORMAL:
            return "normal"
        return "other"

    @property
    def label(self) -> str:
        if self.kind == "paused":
            return PAUSED
        if self.kind == "normal":
            return NORMAL_NAME
        if self.time_controls:
            return f"{TIME_CONTROLS_SPEEDS[self.option]} (a Time Controls speed)"
        return f"other (speed value {self.option}, clock speed {self.clock_speed})"

    @property
    def time_controls(self) -> bool:
        """True for a running save at one of Time Controls' speeds (which Time Controls itself never saves)."""
        return self.option in TIME_CONTROLS_SPEEDS and self.clock_speed == self.option


def _start_time(data: bytes) -> int | None:
    """The header's start time when ``data`` is a family save the game loads, else None."""
    try:
        header = reader.parse_header(data)
    except reader.SaveFormatError:
        return None
    if header.legacy or header.payload_size != reader.GAME_DATA_SIZE:
        return None
    return header.start_time


CLOCK_AT = reader.gs_to_file(reader.GS_GAME_TIME)
OPTION_AT = reader.gs_to_file(reader.GS_SPEED_OPTION)
VILLAGERS_AT = reader.gs_to_file(reader.GS_VILLAGERS)


def read_state(data: bytes) -> SpeedState | None:
    if _start_time(data) is None:
        return None
    speed, previous, changed, banked, saved = struct.unpack_from("<iiIII", data, CLOCK_AT)
    return SpeedState(struct.unpack_from("<i", data, OPTION_AT)[0], speed, previous, changed, banked, saved)


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def seconds_at(state: SpeedState, now: int) -> int:
    """CGameTime::Seconds() at ``now`` for a stopped clock or one at speed 10, the same in both games or refused."""
    if state.clock_speed == CLOCK_PAUSED:
        return state.banked
    if state.clock_speed != NORMAL:
        raise SpeedError(f"The clock runs at speed {state.clock_speed}, which this tool does not change.")
    elapsed = (now - state.changed_at) & _U32 if now > state.changed_at else 0
    if elapsed >= FLOAT_EXACT and _f32(float(elapsed)) != elapsed:
        raise SpeedError("This family has run without a pause for more than 194 days, and the original and the "
                         "patched game would work its clock out a few seconds apart. Pause it in the game instead.")
    return (state.banked + elapsed) & _U32


def _villagers_paused_until(data: bytearray, option: int, now: int) -> None:
    for k in range(reader.VILLAGER_SLOTS):
        rec = VILLAGERS_AT + k * reader.VILLAGER_RECORD_SIZE
        if not data[rec + REC_ACTIVE] or data[rec + REC_LEFT_HOME]:
            continue
        stamp, = struct.unpack_from("<I", data, rec + REC_STAMP)
        health, = struct.unpack_from("<i", data, rec + REC_HEALTH)
        if health <= 0:
            if ((now - stamp) & _U32) // 60 // option >= BODY_REMOVED_AT:
                raise SpeedError(
                    f"A dead family member (villager slot {k}) would have been taken away during the pause. "
                    "Unpause this family in the game instead (Options, Pause Game: No).")
            continue
        if stamp == 0:
            continue
        struct.pack_into("<II", data, rec + REC_BANKED, 0, now)


def changed_bytes(data: bytes, target: str, unix_now: int | None = None) -> bytes:
    """``data`` with the speed set to ``target`` the way the game's own Pause / Unpause sets it."""
    start = _start_time(data)
    state = read_state(data)
    if start is None or state is None:
        raise SpeedError("This is not a Virtual Families 2 save the game can load.")
    out = bytearray(data)
    if target == PAUSED:
        if state.kind == "paused":
            raise SpeedError("This family is already paused.")
        if state.kind != "normal":
            raise SpeedError(f"This family's speed is {state.label}; only a family at Normal can be paused here.")
        now = state.saved_at
        struct.pack_into("<iiIII", out, CLOCK_AT, CLOCK_PAUSED, state.clock_speed, now, seconds_at(state, now),
                         state.saved_at)
        struct.pack_into("<i", out, OPTION_AT, state.option + PAUSE_ADD)
    elif target == NORMAL_NAME:
        if state.kind == "normal":
            raise SpeedError("This family is already at Normal speed.")
        if state.kind != "paused":
            raise SpeedError(f"This family's speed is {state.label}; only a paused family can be set to Normal here.")
        now = (int(time.time()) if unix_now is None else unix_now) - start
        if now < state.saved_at or now > _U32:
            raise SpeedError("This PC's clock is earlier than the family's last save, so its time cannot be "
                             "worked out. Check the date and time in Windows.")
        _villagers_paused_until(out, state.option, now)
        struct.pack_into("<iiIII", out, CLOCK_AT, NORMAL, state.clock_speed, now, seconds_at(state, now), now)
        struct.pack_into("<i", out, OPTION_AT, NORMAL)
    else:
        raise SpeedError(f"{target!r} is not a speed this tool sets.")
    return bytes(out)


def only_speed_fields_differ(before: bytes, after: bytes) -> bool:
    """True when ``after`` equals ``before`` outside the fields a speed change may write."""
    if len(before) != len(after) or _start_time(before) is None:
        return False
    allowed = bytearray(len(before))
    ranges = [(CLOCK_AT, CLOCK_AT + CLOCK_SIZE), (OPTION_AT, OPTION_AT + 4)]
    for k in range(reader.VILLAGER_SLOTS):
        rec = VILLAGERS_AT + k * reader.VILLAGER_RECORD_SIZE
        ranges.append((rec + REC_BANKED, rec + REC_STAMP + 4))
    for a, b in ranges:
        allowed[a:b] = b"\1" * (b - a)
    return all(x == y or allowed[i] for i, (x, y) in enumerate(zip(before, after)))


@dataclass
class SlotSpeed:
    slot: int
    name: bytes | None
    state: SpeedState | None
    problem: str | None = None

    @property
    def label(self) -> str:
        if self.state is None:
            if self.problem == "This slot has no family.":
                return f"Family slot {self.slot}: (empty)"
            return f"Family slot {self.slot}: (a save the game cannot load)"
        return f"Family slot {self.slot}: {rename_family.shown(self.name)} - {self.state.label}"


def read_slots(folder: Path) -> list[SlotSpeed]:
    slots: list[SlotSpeed] = []
    for slot in SLOTS:
        path = rename_family.save_path(folder, slot)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            slots.append(SlotSpeed(slot, None, None, "This slot has no family."))
            continue
        except OSError as exc:
            slots.append(SlotSpeed(slot, None, None, f"The save could not be read: {exc}"))
            continue
        state = read_state(data)
        if state is None:
            slots.append(SlotSpeed(slot, None, None, f"{path.name} is not a Virtual Families 2 save the game can load."))
            continue
        info = SlotSpeed(slot, rename_family.save_name(data), state)
        if state.time_controls:
            info.problem = (f"Its speed is {state.label}, which this tool does not change. Time Controls never "
                            "keeps one in a save: with Time Controls installed, the game loads this family at Normal.")
        elif state.kind == "other":
            info.problem = (f"Its speed is {state.label}, which this tool does not change. Change it in the game "
                            "(Options, Pause Game).")
        slots.append(info)
    return slots


def _write_atomically(path: Path, data: bytes) -> None:
    temporary = path.with_name(f"{path.name}.speed-{uuid.uuid4().hex[:12]}.tmp")   # a leftover never blocks the next one
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    if path.read_bytes() != data:
        raise SpeedError(f"{path.name} did not read back as written.")


@dataclass
class SpeedResult:
    folder: Path
    slot: int
    before: str
    after: str
    backup: save_backup.BackupResult
    changed: Path


def _refuse_if_running(folder: Path, processes: save_backup.ProcessController) -> None:
    try:
        running = save_backup.running_games(folder, processes)
    except (OSError, save_backup.BackupError) as exc:
        raise SpeedError(f"Could not check whether the game is running, so nothing was changed ({exc}).") from exc
    if running:
        names = ", ".join(sorted({name for _pid, name in running}))
        raise GameRunning(
            f"{names} is running. Close the game first (quit it normally from its menu): it saves when it quits, "
            "which would put the old speed back. Nothing was changed."
        )


def set_speed(
    folder: Path,
    slot: int,
    target: str,
    processes: save_backup.ProcessController | None = None,
    now: datetime | None = None,
    unix_now: int | None = None,
) -> SpeedResult:
    """Set the saved speed of the family in ``slot`` to ``target`` (Paused or Normal); see the module notes."""
    if slot not in SLOTS:
        raise SpeedError(f"There is no family slot {slot}.")
    if target not in TARGETS:
        raise SpeedError(f"{target!r} is not a speed this tool sets.")
    controller = processes if processes is not None else save_backup.WindowsProcesses()
    when = now or datetime.now()
    _refuse_if_running(folder, controller)
    path = rename_family.save_path(folder, slot)
    try:
        original = path.read_bytes()
    except FileNotFoundError as exc:
        raise SpeedError(f"Family slot {slot} has no family ({path.name} is missing).") from exc
    except OSError as exc:
        raise SpeedError(f"Could not read {path.name}: {exc}") from exc
    updated = changed_bytes(original, target, unix_now)
    before = read_state(original)
    try:
        backup = save_backup.copy_save_folder(folder, when, suffix=BACKUP_LABEL)
    except save_backup.BackupError as exc:
        raise SpeedError(f"The backup before the speed change failed, so nothing was changed. {exc}") from exc
    _refuse_if_running(folder, controller)
    written = False
    try:
        if path.read_bytes() != original:
            raise SpeedError(f"{path.name} changed while its speed was being set.")
        written = True
        _write_atomically(path, updated)
        data = path.read_bytes()
        state = read_state(data)
        if data != updated or state is None or state.label != target or not only_speed_fields_differ(original, data):
            raise SpeedError(f"{path.name} does not hold the new speed.")
    except (OSError, SpeedError) as exc:
        problem = None
        if written:
            try:
                if path.read_bytes() != original:
                    _write_atomically(path, original)
            except (OSError, SpeedError) as undo:
                problem = str(undo)
        if problem:
            raise SpeedError(
                f"The speed change failed ({exc}) and {path.name} could not be put back ({problem}). "
                f"Your backup is in {backup.backup_folder}."
            ) from exc
        raise SpeedError(
            f"The speed change failed ({exc}); the save was put back as it was. A backup is in {backup.backup_folder}."
        ) from exc
    return SpeedResult(folder, slot, before.label if before else "?", target, backup, path)
