"""Revive (src/vf2_revive.py): the snapshot file, the backfill for people who died before the patch (its sources in the
owner's order, the exact / inferred / unknown marks, idempotence, the running game, rollback, a damaged file set
aside), the age rule (18 and older come back at 18, 17 and younger at their age), the refusal of anyone not dead,
and the slot tools re-keying the file like the Children file.  Synthetic saves laid out as the game writes them
(docs/vf2-save-format.md) and the real-save fixtures, all in tmp_path; nothing outside it is read or written."""
from __future__ import annotations

import gzip
import shutil
import struct
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_copy_slot as copy_slot  # noqa: E402
import vf2_family_history as history  # noqa: E402
import vf2_revive as rv  # noqa: E402
import vf2_save_reader as r  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "vf2_saves"
NOW = datetime(2026, 11, 26, 12, 0, 0)
FAY = "Fay Whole-Name-Longer-Than-The-Field"
FAY_SHORT = "Fay Whole-Name-..."   # vf2_names.short_form(FAY, 18, {})


# ---------------------------------------------------------------- building saves
def blank_save(nickname: str = "Testfamily") -> bytearray:
    b = bytearray(r.GAME_FILE_SIZE)
    b[0:4] = b"ldwg"
    struct.pack_into("<qI", b, 4, 1_700_000_000, r.GAME_DATA_SIZE)
    struct.pack_into("<3i", b, r.gs_to_file(r.GS_PENDING_BABIES), -1, -1, -1)
    put_str(b, r.gs_to_file(r.GS_NICKNAME), nickname, 20)
    return b


def put_str(b: bytearray, off: int, text: str, size: int) -> None:
    raw = text.encode("cp1252")[:size - 1]
    b[off:off + size] = raw + b"\0" * (size - len(raw))


def villager(b: bytearray, slot: int, name: str, sex: int = 0, age: int = 600, head: int = 1, body: int = 1,
             active: int = 1, left: int = 0, health: int = 90, cause: int = -1, career: int = -1, level: int = 0,
             fertility: int = 50, desire: int = 40, likes: bytes = b"\x01\0\0\0\x02\0\0\0\x03\0\0\0") -> None:
    v = r.gs_to_file(r.GS_VILLAGERS) + slot * r.VILLAGER_RECORD_SIZE
    b[v], b[v + 1] = active, left
    struct.pack_into("<iii", b, v + 8, age, sex, 7)
    put_str(b, v + 8 + 0x10, name, 25)
    struct.pack_into("<ii", b, v + 8 + 0x2C, head, body)
    put_str(b, v + 8 + 0x34, "Joey", 25)
    put_str(b, v + 8 + 0x4E, "Mum", 25)
    struct.pack_into("<ii", b, v + 0xA8 + 0x0C, health, cause)
    struct.pack_into("<ii", b, v + 0xA8 + 0x4C, fertility, desire)
    struct.pack_into("<ii", b, v + 0x140, career, level)
    b[v + 0x150:v + 0x15C] = likes
    struct.pack_into("<I", b, v + 0x7B8, 0x19B)


def peep(b: bytearray, record: int, place: int, name: str, sex: int = 0, head: int = 1, body: int = 1,
         slot: int = 0, present: int = 1, likes: str = "", career: int = -1) -> None:
    rec = r.gs_to_file(r.GS_FAMILY_TREE) + 4 + record * r.FAMILY_RECORD_SIZE
    b[rec] = 1
    at = rec + (0x04, 0xDC)[place] if place < 2 else rec + 0x1B8 + (place - 2) * r.PEEP_RECORD_SIZE
    put_str(b, at, name, 25)
    b[at + 0x1A] = present
    struct.pack_into("<iiiiii", b, at + 0x1C, sex, head, body, slot, -1, career)
    put_str(b, at + 0x34, likes, 0x28)
    if place >= 2:
        count = struct.unpack_from("<i", b, rec + 0x1B4)[0]
        struct.pack_into("<i", b, rec + 0x1B4, max(count, place - 1))


def family(bob_record: bool = True, bob_alive: bool = False) -> bytes:
    """One generation: Ann (the heir, alive), Bob (her spouse, died at 45 of old age), Cal (at home), Dee (away:
    college), Fay (died at 3 of disease), Gil (divorced: no longer in the tree or the house)."""
    b = blank_save()
    villager(b, 0, "Ann", sex=1, head=1, body=1, age=900)
    if bob_record:
        villager(b, 1, "Bob", head=2, body=2, age=900, active=int(bob_alive), health=80 if bob_alive else 0,
                 cause=-1 if bob_alive else 2, career=12, level=3, fertility=61, desire=77)
    villager(b, 2, "Cal", head=4, body=4, age=200)
    villager(b, 3, "Dee", sex=1, head=5, body=5, age=400, left=1)
    villager(b, 4, FAY_SHORT, sex=1, head=9, body=9, age=60, active=0, health=0, cause=0)
    peep(b, 0, 0, "Ann", sex=1, head=1, body=1, slot=0)
    peep(b, 0, 1, "Bob", head=2, body=2, slot=-1, likes="reading, running", career=12)
    peep(b, 0, 2, "Cal", head=4, body=4, slot=2)
    peep(b, 0, 3, "Dee", sex=1, head=5, body=5, slot=3)
    peep(b, 0, 4, FAY_SHORT, sex=1, head=9, body=9, slot=-1)
    return bytes(b)


LOG = """Family: Testfamily (Save 1)

[2026-11-01 10:00:00] Death 1
  Name: Fay Whole-Name-Longer-Than-The-Field
  Age at death: 3
  Sex: Female
  Cause of death: Disease
  Head: 9
  Body: 9
  Family role: Child
  Generation: 1

[2026-11-02 10:00:00] Death 2
  Name: Bob
  Age at death: 45
  Sex: Male
  Cause of death: Old age
  Head: 2
  Body: 2
  Family role: Parent (married in)
  Generation: 1

[2026-11-03 10:00:00] Divorce 1
  Family member: Ann
  Divorced: Gil
    Sex: Male
    Age: 30
  How: Divorce Spouse
  Generation: 1

"""


def make_folder(tmp_path: Path, save: bytes, previous: bytes | None = None, log: str | None = LOG,
                names: bool = True) -> Path:
    folder = tmp_path / "Virtual Families 2"
    folder.mkdir()
    (folder / "Virtual Families 21.ldw").write_bytes(save)
    if previous is not None:
        (folder / "Virtual Families 221.ldw").write_bytes(previous)
    if log is not None:
        logs = folder / "Virtual Families 2 Patcher" / "Save 1" / "Logs" / "Family History"
        logs.mkdir(parents=True)
        (logs / "Family History 1.txt").write_bytes(log.replace("\n", "\r\n").encode("utf-8"))
    if names:
        import vf2_names
        path = vf2_names.names_path(folder, 1)
        path.parent.mkdir(parents=True)
        vf2_names.write(path, [vf2_names.Entry(FAY_SHORT, 18, FAY)])
    return folder


class Processes:
    def __init__(self, running: bool = False):
        self.running = running

    def find_game(self, _name):
        return [(1234, "Virtual Families 2.exe")] if self.running else []


def snapshots(folder: Path, number: int = 1) -> dict:
    f = rv.read_file(rv.sidecar_path(folder, number).read_bytes())
    assert f is not None
    return {s.name_text: s for s in f.entries}


def tree_files(folder: Path) -> dict:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------- the age rule
@pytest.mark.parametrize("died, back", [(0, 0), (60, 60), (340, 340), (359, 359), (360, 360), (380, 380),
                                        (399, 399), (400, 400), (401, 400), (900, 400), (2000, 400), (None, 400),
                                        (-1, 400)])
def test_twenty_and_older_come_back_at_twenty_younger_at_their_age(died, back):
    assert rv.ADULT_RETURN_UNITS == 20 * r.AGE_UNITS_PER_YEAR == 400
    assert rv.revival_age_units(died) == back


def test_the_price_is_one_constant():
    assert rv.REVIVE_PRICE == 25_000


# ---------------------------------------------------------------- the backfill
def test_backfill_from_their_own_records_is_exact(tmp_path):
    folder = make_folder(tmp_path, family())
    result = rv.backfill(folder, Processes(), NOW)
    assert result.error is None
    assert [t.status for t in result.targets] == ["written"]
    people = snapshots(folder)
    assert set(people) == {"Bob", "Fay Whole-Name-Longer-Than-The-Field"}   # never Ann, Cal, Dee or Gil
    bob = people["Bob"]
    assert bob.source == rv.THIS_SAVE
    assert all(bob.mark(f) == rv.EXACT for f in rv.FIELDS), {f: bob.mark(f) for f in rv.FIELDS}
    assert (bob.age_at_death, bob.cause, bob.career, bob.career_level) == (900, 2, 12, 3)
    assert (bob.fertility, bob.procreation_desire) == (61, 77)
    assert bob.likes == b"\x01\0\0\0\x02\0\0\0\x03\0\0\0" and bob.likes_text == b"reading, running"
    at = r.gs_to_file(r.GS_VILLAGERS) + 1 * r.VILLAGER_RECORD_SIZE
    assert bob.record == family()[at:at + r.VILLAGER_RECORD_SIZE]
    assert bob.role == rv.ROLE_SPOUSE and bob.generation == 1
    assert bob.revival_age() == (400, rv.EXACT)
    fay = people["Fay Whole-Name-Longer-Than-The-Field"]
    assert fay.name == FAY_SHORT.encode() and fay.full_name == FAY.encode()
    assert fay.revival_age() == (60, rv.EXACT)
    assert fay.role == rv.ROLE_CHILD + 2


def test_backfill_from_the_previous_save_marks_what_may_have_changed(tmp_path):
    """Bob's record was reused (gone from the save) but the game's previous save holds him alive: who he is is
    exact, the rest is as when saved (inferred), and his age at death is the log's whole years (inferred), which
    still makes his revival age exactly 18."""
    folder = make_folder(tmp_path, family(bob_record=False), previous=family(bob_alive=True))
    rv.backfill(folder, Processes(), NOW)
    bob = snapshots(folder)["Bob"]
    assert bob.source == rv.OTHER_SAVE
    for f in ("name", "sex", "head", "body", "parents", "first_name", "role", "generation", "cause", "career"):
        assert bob.mark(f) == rv.EXACT, f          # the career: the Family Tree's, kept while he lived
    for f in ("career_level", "fertility", "procreation_desire", "likes", "dislikes", "record", "age_at_death"):
        assert bob.mark(f) == rv.INFERRED, f
    assert bob.age_at_death == 45 * 20
    assert bob.revival_age() == (400, rv.EXACT)


def test_backfill_from_the_tree_alone_leaves_the_rest_unknown(tmp_path):
    folder = make_folder(tmp_path, family(bob_record=False), log=None, names=False)
    rv.backfill(folder, Processes(), NOW)
    bob = snapshots(folder)["Bob"]
    assert bob.source == rv.TREE
    assert {f for f in rv.FIELDS if bob.mark(f) == rv.EXACT} == {
        "name", "full_name", "sex", "head", "body", "likes_text", "dislikes_text", "career", "role", "generation"}
    assert bob.mark("age_at_death") == rv.UNKNOWN and bob.revival_age() == (400, rv.EXACT)   # unknown: back at 20
    assert bob.record == b""


def test_a_child_who_died_young_comes_back_at_the_logs_age_inferred(tmp_path):
    save = bytearray(family())
    v = r.gs_to_file(r.GS_VILLAGERS) + 4 * r.VILLAGER_RECORD_SIZE
    save[v:v + r.VILLAGER_RECORD_SIZE] = bytes(r.VILLAGER_RECORD_SIZE)       # Fay's record reused
    folder = make_folder(tmp_path, bytes(save))
    rv.backfill(folder, Processes(), NOW)
    fay = snapshots(folder)["Fay Whole-Name-Longer-Than-The-Field"]
    assert fay.revival_age() == (60, rv.INFERRED)


def test_backfill_is_idempotent(tmp_path):
    folder = make_folder(tmp_path, family(), previous=family(bob_alive=True))
    first = rv.backfill(folder, Processes(), NOW)
    assert sorted(t.status for t in first.targets) == ["written", "written"]
    before = tree_files(folder)
    again = rv.backfill(folder, Processes(), NOW)
    assert [t.status for t in again.targets] == ["unchanged", "unchanged"]
    assert tree_files(folder) == before


def test_a_capture_always_wins(tmp_path):
    folder = make_folder(tmp_path, family())
    rv.backfill(folder, Processes(), NOW)
    path = rv.sidecar_path(folder, 1)
    f = rv.read_file(path.read_bytes())
    captured = [rv.replace(s, source=rv.CAPTURED, career=99, record=b"", marks={**s.marks, "record": rv.UNKNOWN})
                if s.name == b"Bob" else s for s in f.entries]
    path.write_bytes(rv.make_file(family(), captured))
    rv.backfill(folder, Processes(), NOW)
    bob = snapshots(folder)["Bob"]
    assert (bob.source, bob.career, bob.mark("record"), bob.record) == (rv.CAPTURED, 99, rv.UNKNOWN, b"")


def test_the_saves_logs_and_names_are_only_read(tmp_path):
    folder = make_folder(tmp_path, family(), previous=family(bob_alive=True))
    before = {k: v for k, v in tree_files(folder).items() if "Revive" not in k}
    rv.backfill(folder, Processes(), NOW)
    after = {k: v for k, v in tree_files(folder).items() if "Revive" not in k}
    assert after == before


def test_backups_are_repaired_while_the_game_runs_and_the_live_saves_wait(tmp_path):
    folder = make_folder(tmp_path, family())
    backup = folder / "Backups" / "Backup 2026-11-20 10-00-00"
    shutil.copytree(folder, backup, ignore=shutil.ignore_patterns("Backups"))
    result = rv.backfill(folder, Processes(running=True), NOW)
    by_place = {(t.in_backup, t.number): t.status for t in result.targets}
    assert by_place == {(False, 1): "waits: the game is running", (True, 1): "written"}
    assert not rv.sidecar_path(folder, 1).exists()
    assert set(snapshots(backup)) == {"Bob", "Fay Whole-Name-Longer-Than-The-Field"}
    # once the game is closed, the live save gets its file and the backup's stays as it is
    kept = rv.sidecar_path(backup, 1).read_bytes()
    result = rv.backfill(folder, Processes(running=False), NOW)
    assert {(t.in_backup, t.number): t.status for t in result.targets} == {(False, 1): "written",
                                                                           (True, 1): "unchanged"}
    assert rv.sidecar_path(backup, 1).read_bytes() == kept


def test_not_knowing_whether_the_game_runs_waits(tmp_path):
    class Broken:
        def find_game(self, _name):
            raise OSError("no process list")
    assert rv.game_running(tmp_path, Broken()) is True


def test_a_failed_write_rolls_the_whole_run_back(tmp_path, monkeypatch):
    folder = make_folder(tmp_path, family(), previous=family(bob_alive=True))
    rv.backfill(folder, Processes(), NOW)
    # the game saved again (N moved to N+20, a new N): the next run rewrites both files; the second write fails
    newer = bytearray(family())
    newer[100] ^= 1
    (folder / "Virtual Families 221.ldw").write_bytes(family())
    (folder / "Virtual Families 21.ldw").write_bytes(bytes(newer))
    before = tree_files(folder)
    real = rv._swap_in
    calls = []

    def failing(path, data):
        calls.append(path)
        if len(calls) == 2:
            raise OSError("disk full")
        real(path, data)
    monkeypatch.setattr(rv, "_swap_in", failing)
    result = rv.backfill(folder, Processes(), NOW)
    assert result.error == "disk full"
    monkeypatch.setattr(rv, "_swap_in", real)
    after = {k: v for k, v in tree_files(folder).items() if "Before backfill" not in k}
    assert after == before


def test_a_damaged_file_is_set_aside_never_overwritten(tmp_path):
    folder = make_folder(tmp_path, family())
    path = rv.sidecar_path(folder, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"VF2REVIV damaged")
    result = rv.backfill(folder, Processes(), NOW)
    assert [t.status for t in result.targets] == ["set aside and written"]
    assert (path.parent / "Virtual Families 21.ldw.unreadable-1.dat").read_bytes() == b"VF2REVIV damaged"
    assert set(snapshots(folder)) == {"Bob", "Fay Whole-Name-Longer-Than-The-Field"}


def test_a_replaced_file_is_copied_aside_first(tmp_path):
    folder = make_folder(tmp_path, family())
    rv.backfill(folder, Processes(), NOW)
    old = rv.sidecar_path(folder, 1).read_bytes()
    newer = bytearray(family())
    newer[100] ^= 1
    (folder / "Virtual Families 21.ldw").write_bytes(bytes(newer))
    rv.backfill(folder, Processes(), NOW)
    copy = rv.sidecar_path(folder, 1).parent / rv.BEFORE_BACKFILL / "2026-11-26 12-00-00" / "Virtual Families 21.ldw.dat"
    assert copy.read_bytes() == old
    assert rv.describes(rv.sidecar_path(folder, 1).read_bytes(), bytes(newer))


def test_the_file_round_trips_and_rejects_damage():
    s = rv.Snapshot(source=rv.THIS_SAVE, generation=2, role=3, age_at_death=120, cause=0, sex=1, head=4, body=5,
                    name=b"Zed", full_name="Zed été".encode("utf-8"), likes=b"\1" * 12,
                    record=bytes(range(256)) * 7 + bytes(r.VILLAGER_RECORD_SIZE - 1792),
                    marks={"name": rv.EXACT, "likes": rv.INFERRED, "record": rv.EXACT})
    save = family()
    data = rv.make_file(save, [s])
    f = rv.read_file(data)
    s = rv.replace(s, marks={k: s.mark(k) for k in rv.FIELDS})
    assert f is not None and f.entries == [s] and rv.describes(data, save)
    assert rv.make_file(save, f.entries) == data
    for broken in (data[:-1], data[:30] + b"x" + data[31:], b"VF2KIDS\0" + data[8:]):
        assert rv.read_file(broken) is None


# ---------------------------------------------------------------- who may be revived
def snapshot_of(folder: Path, name: str) -> rv.Snapshot:
    return snapshots(folder)[name]


def test_only_the_dead_of_this_generation_and_family_may_be_revived(tmp_path):
    save = family()
    folder = make_folder(tmp_path, save)
    rv.backfill(folder, Processes(), NOW)
    parsed = r.parse_family_save(save)
    h = history.read(folder, 1)
    bob = snapshot_of(folder, "Bob")
    assert rv.refusal(parsed, bob, h) is None
    alive = rv.replace(bob, name=b"Cal", head=4, body=4)
    assert "not dead" in rv.refusal(parsed, alive, h) and "at home" in rv.refusal(parsed, alive, h)
    away = rv.replace(bob, name=b"Dee", sex=1, head=5, body=5)
    assert "away from home" in rv.refusal(parsed, away, h)
    gil = rv.replace(bob, name=b"Gil", head=3, body=3)
    assert "divorced" in rv.refusal(parsed, gil, h)
    earlier = rv.replace(bob, generation=0)
    assert "current generation" in rv.refusal(parsed, earlier, h)
    other_family = rv.replace(bob, heir_name=b"Zoe")         # an evicted or earlier family's member
    assert "current generation" in rv.refusal(parsed, other_family, h)
    unsure = rv.replace(bob, marks={**bob.marks, "head": rv.INFERRED})
    assert "not known exactly" in rv.refusal(parsed, unsure, h)


def test_a_full_house_refuses(tmp_path):
    b = bytearray(family())
    for slot in range(r.VILLAGER_SLOTS):
        if slot not in (0, 1, 2, 3, 4):
            villager(b, slot, f"K{slot}", head=20 + slot % 20, body=1, age=100)
    v = r.gs_to_file(r.GS_VILLAGERS)
    b[v + 1 * r.VILLAGER_RECORD_SIZE] = 1                     # Bob's record: dead, still active
    b[v + 4 * r.VILLAGER_RECORD_SIZE] = 1                     # Fay's too
    folder = make_folder(tmp_path, bytes(b))
    rv.backfill(folder, Processes(), NOW)
    assert "house is full" in rv.refusal(r.parse_family_save(bytes(b)), snapshot_of(folder, "Bob"))


def test_a_spouse_whose_partner_remarried_returns_as_a_family_member(tmp_path):
    save = family()
    folder = make_folder(tmp_path, save)
    rv.backfill(folder, Processes(), NOW)
    bob = snapshot_of(folder, "Bob")
    assert rv.return_role(r.parse_family_save(save), bob) == "spouse"        # Ann has not remarried
    b = bytearray(save)
    villager(b, 5, "Hal", head=6, body=6)
    peep(b, 0, 1, "Hal", head=6, body=6, slot=5)
    assert rv.return_role(r.parse_family_save(bytes(b)), bob) == "family member"   # in the house, no tree place
    assert rv.return_role(r.parse_family_save(save), snapshot_of(folder, "Fay Whole-Name-Longer-Than-The-Field")) \
        == "child"


# ---------------------------------------------------------------- the slot tools carry it
def test_copy_rename_and_speed_rekey_the_revive_file_like_the_children_file(tmp_path):
    save = family()
    folder = make_folder(tmp_path, save)
    rv.backfill(folder, Processes(), NOW)
    changed = save[:100] + bytes([save[100] ^ 1]) + save[101:]
    found = copy_slot.sidecar_rekeys(folder, 1, [(save, changed)])
    assert [(p.name, kind) for p, kind, _old, _new in found] == [("Virtual Families 21.ldw.dat", "Revive")]
    _path, _kind, old, new = found[0]
    assert rv.describes(new, changed) and rv.read_file(new).entries == rv.read_file(old).entries
    import vf2_save_backup
    assert vf2_save_backup.file_slot(Path("Virtual Families 2 Patcher Data/Revive/Virtual Families 221.ldw.dat")) == 1


# ---------------------------------------------------------------- the real saves
@pytest.mark.parametrize("name, slot", [("one_generation_slot3.ldw.gz", 3), ("ten_generations_slot4.ldw.gz", 4),
                                        ("pending_birth_slot1.ldw.gz", 1)])
def test_real_saves_backfill_without_changing_them(tmp_path, name, slot):
    folder = tmp_path / "Virtual Families 2"
    folder.mkdir()
    data = gzip.decompress((FIX / name).read_bytes())
    (folder / f"Virtual Families 2{slot}.ldw").write_bytes(data)
    result = rv.backfill(folder, Processes(), NOW)
    assert result.error is None
    assert (folder / f"Virtual Families 2{slot}.ldw").read_bytes() == data
    save = r.parse_family_save(data)
    cur = save.family_tree.current
    dead = [p for p in (cur.parent1, cur.parent2, *cur.children) if p.present and p.slot == -1]
    if dead:
        f = rv.read_file(rv.sidecar_path(folder, slot).read_bytes())
        assert sorted(s.name_text for s in f.entries) == sorted(p.name for p in dead)
        for s in f.entries:
            assert rv.refusal(save, s) in (None, "The house is full (30 family members).") or "not known" in \
                rv.refusal(save, s)
    else:
        assert not rv.sidecar_path(folder, slot).exists()
    assert [t.status for t in rv.backfill(folder, Processes(), NOW).targets] == \
        ["unchanged"] * len([t for t in result.targets])
