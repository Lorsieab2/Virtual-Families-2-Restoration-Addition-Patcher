"""The Family Tree Maker's memory of a save's family: every member the tree has seen in that save, kept in its own
tree file (the owner, 2026-10-24: the tree file per save "may remember every member it has ever seen in that save").

Why: the save keeps only what the game needs now (docs/vf2-save-format.md section 5, and Virtual Families 2's own
code, FamilyTree.obj, traced for this file -- offsets are into each function):

* CFamilyTree::UpdateParents writes the one who marries in over parent 2 whenever parent 1 is present (+0x84), and
  CanMarry allows that only while parent 2 is not present, so an earlier spouse is gone once a new one marries in;
* CFamilyTree::ReportDeath (the current record only): a parent who dies WITH children keeps their place with a
  slot of -1 (+0x90, +0xD7), but parent 1 dying with NO children is overwritten by parent 2 (rep movsd 0x36 dwords,
  +0x4F) and parent 2 dying with no children has only their present byte cleared (+0xC4): kept in the save until a
  new marriage writes over them; a child who dies keeps their place with a slot of -1 (+0x109);
* the patcher's Divorce Spouse (docs/REQUEST_LEDGER.md) zeroes parent 2's whole record and resets their villager:
  the spouse is gone from the save;
* CFamilyTree::MakeRoomInTree drops the oldest generation when a 31st starts;
* a dead member's villager record stays until its slot is reused (never cleared), and the Up to 28 Children file
  holds only the current generation's children 7 to 28.

So each time the tree is opened, what the save shows is compared with what the tree file remembers: a member who
was seen is kept, with when the tree first saw them and when it saw a change (the save's own game clock and the
time the save was written), and the way they left the save -- only as the save proves it.  A member is known by
their place in the save's Family Tree (generation and seat) and, for a spouse, by their villager slot or name and
sex, so new looks or a new name never make two people of one.  Nothing is ever removed by the tree itself.  A new
family in the slot (another founder) starts a fresh memory; the old tree file is kept beside it as a backup.

The file: Virtual Families 2 Patcher\\Save <N>\\Data\\Family Tree\\Virtual Families 2 Family Tree - Save <N>.tree,
the same file Save writes the tree's edits into ("edits"); this module owns its "members" part.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import vf2_genealogy as gen
import vf2_save_reader as reader

FORMAT = "Virtual Families 2 Patcher family tree"
MEMORY_VERSION = 1
TREE_FOLDER = "Family Tree"


def tree_file(folder: Path, slot: int) -> Path:
    return gen.slot_root(folder, slot) / "Data" / TREE_FOLDER / f"Virtual Families 2 Family Tree - Save {slot}.tree"


def read_tree_file(path: Path) -> dict:
    """The tree file's contents ({} when there is none); ValueError when it is not a tree file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{Path(path).name} could not be read: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError(f"{Path(path).name} is not a Family Tree Maker tree file.")
    return data


def write_tree_file(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(temp, path)


def clock(save: reader.FamilySave) -> dict:
    """The save's own time: CGameTime seconds at saving, and the real time the save was written (the header's start
    time, which GetSecondsFromGameStart counts from, plus CGameTime+0x10, GetSecondsFromGameStart at saving)."""
    when = datetime.fromtimestamp(save.header.start_time + save.clock.real_seconds_at_save, tz=timezone.utc)
    return {"game_seconds": save.clock.game_seconds_at_save, "saved_at": when.strftime("%Y-%m-%d %H:%M:%S UTC")}


def family_id(save: reader.FamilySave) -> dict:
    """What tells one family from the next in the slot: the oldest generation's record (a new family, or Evict
    Family, writes a new one).  Parent 2 may be promoted over a founder who died childless, so the first children
    too."""
    if not save.family_tree.generations:
        return {}
    rec = save.family_tree.generations[0]
    return {"founder": [rec.parent1.name, rec.parent1.gender, rec.parent1.head, rec.parent1.body],
            "spouse": [rec.parent2.name, rec.parent2.gender] if rec.parent2.present else None,
            "children": [[c.name, c.gender] for c in rec.children]}


def _dropped_to(members: list, save: reader.FamilySave) -> int | None:
    """When MakeRoomInTree has dropped older generations: the generation the save's oldest record is, from the
    remembered parent 1 of that generation (the same name, sex, head and body); None when none is remembered."""
    if not save.family_tree.generations:
        return None
    first = save.family_tree.generations[0].parent1
    want = [first.name, gen.SEX_WORDS.get(first.gender), first.head, first.body]
    for m in members:
        seat = m.get("seat", "")
        if m.get("displaced") or [m.get("name"), m.get("sex"), m.get("head"), m.get("body")] != want:
            continue
        if seat.endswith(".p1"):
            return int(seat[1:].split(".")[0])
        if m.get("heir") and ".c" in seat:          # an heir is remembered by their place among the children
            return int(seat[1:].split(".")[0]) + 1
    return None


def _heir_member(members: list, seat: str, p: gen.Person) -> dict | None:
    """Parent 1 of generation g, remembered as a child of generation g - 1 who inherited the house (their record
    of generation g - 1 may have been dropped by MakeRoomInTree since)."""
    g = int(seat[1:].split(".")[0])
    want = [p.name, p.sex, p.head, p.body]
    return next((m for m in members if m.get("heir") and not m.get("displaced")
                 and m.get("seat", "").startswith(f"g{g - 1}.c")
                 and [m.get("name"), m.get("sex"), m.get("head"), m.get("body")] == want), None)


def first_generation(folder: Path, slot: int, save: reader.FamilySave) -> int:
    """The generation of the save's oldest record: 1, unless the tree file remembers that record's parent 1 as a
    later generation's (the game's Family Tree keeps only the latest 30 generations)."""
    try:
        memory = read_tree_file(tree_file(folder, slot)).get("members")
    except ValueError:
        return 1
    if not isinstance(memory, dict):
        return 1
    return _dropped_to(memory.get("list") or [], save) or 1


def same_family(old: dict, new: dict) -> bool:
    if not old or not new:
        return not old
    if old.get("founder") == new.get("founder"):
        return True
    if old.get("spouse") and new.get("founder") and old["spouse"] == new["founder"][:2]:
        return True                      # the founder died childless; the spouse took their place (ReportDeath)
    a, b = old.get("children") or [], new.get("children") or []
    return bool(a) and a == b[:len(a)]


def _same(member: dict, p: gen.Person) -> bool:
    """One member: the same living villager slot and sex, or the same name and sex."""
    sex = p.sex
    if member.get("sex") != sex:
        return False
    if p.alive and p.slot is not None and member.get("slot") == p.slot and member.get("state") == "alive":
        return True
    return member.get("name") == p.name


def _state(p: gen.Person) -> str:
    if p.upcoming:
        return "upcoming"
    if p.alive:
        return "alive"
    return "died" if p.gone == "died" else "left"


def _record(member: dict, p: gen.Person, now: dict) -> None:
    changed = any(member.get(k) != v for k, v in (("state", _state(p)), ("name", p.name), ("head", p.head),
                                                  ("body", p.body), ("left_home", p.left_home)))
    if member.get("name") and member["name"] != p.name and member["name"] not in member.setdefault("former", []):
        member["former"].append(member["name"])
    member.update(name=p.name, sex=p.sex, head=p.head, body=p.body, state=_state(p), age=p.age, cause=p.cause,
                  slot=p.slot, left_home=p.left_home, heir=p.heir, how=p.how, event=p.event, runner=p.runner,
                  likes=p.likes, dislikes=p.dislikes, adopted=p.adopted)
    member["last_seen"] = now
    if changed:
        member["changed"] = now


def _leaving(save: reader.FamilySave, member: dict) -> tuple[str, str]:
    """How a spouse left the save's tree, as far as the save proves it: (state, words).  Only a death is proved (their
    own villager record, health 0); Divorce Spouse resets the villager, so the save cannot show a divorce."""
    if member.get("state") == "died":
        return "died", member.get("left") or "Died."
    slot = member.get("slot")
    if isinstance(slot, int) and 0 <= slot < reader.VILLAGER_SLOTS:
        v = save.villagers[slot]
        if v.name == member.get("name") and gen.SEX_WORDS.get(v.gender) == member.get("sex") and v.health <= 0:
            return "died", "Died (their own villager record says so)."
    return "left", ("No longer in the save's Family Tree; the save does not say why (they may have died, or been "
                    "divorced).")


def remember(folder: Path, slot: int, save: reader.FamilySave, village: gen.Village) -> list[str]:
    """Compare the family the save shows with the tree file's memory, write the memory back, and add to `village`
    every remembered member the save no longer holds (and the parents the tree saw for each child).  Returns notes
    (also added to village.notes).  The save is only read."""
    path = tree_file(folder, slot)
    notes: list[str] = []
    try:
        data = read_tree_file(path)
    except ValueError as exc:
        village.notes.append(f"The tree file could not be read, so no earlier members are added ({exc}); it is left "
                             "as it is.")
        return []
    memory = data.get("members") if isinstance(data.get("members"), dict) else {}
    now = clock(save)
    fid = family_id(save)
    if memory.get("list") and not same_family(memory.get("family") or {}, fid) and \
            _dropped_to(memory["list"], save) is None:
        # Another family in this slot (a new family, or Start Over): a fresh memory; the old file is kept.
        stamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        backup = path.with_name(f"{path.stem} (earlier family, kept {stamp}){path.suffix}")
        path.replace(backup)
        edits = path.parent / f"Virtual Families 2 Family Tree Edits - Save {slot}.json"
        if edits.is_file():
            edits.replace(edits.with_name(f"{edits.stem} (earlier family, kept {stamp}){edits.suffix}"))
        notes.append(f"This save holds a new family, so the tree starts afresh; the earlier family's tree file is "
                     f"kept as {backup.name}.")
        data, memory = {}, {}
    members: list[dict] = memory.setdefault("list", [])
    memory.setdefault("next", 1)
    memory["family"] = fid
    memory["version"] = MEMORY_VERSION

    def active(seat: str) -> dict | None:
        return next((m for m in members if m.get("seat") == seat and not m.get("displaced")), None)

    def create(p: gen.Person, seat: str) -> dict:
        m = {"mid": memory["next"], "seat": seat, "first_seen": now}
        memory["next"] += 1
        members.append(m)
        _record(m, p, now)
        return m

    def displace(m: dict, state: str, words: str) -> None:
        g = m["seat"].split(".")[0]
        k = 1 + sum(1 for x in members if x.get("seat", "").startswith(f"{g}.p2#"))
        m.update(displaced=True, seat=f"{g}.p2#{k}", state=state if m.get("state") != "died" else "died",
                 left=words, left_seen=now)

    mid_of: dict[int, int] = {}                  # person id -> member id
    people = sorted(village.people.values(), key=lambda q: (q.birth_record if q.birth_record is not None else 0))
    for p in people:
        seat = p.seat
        if not seat:
            continue
        m = active(seat)
        if m is None and seat.endswith(".p1") and not seat.startswith("g1."):
            m = _heir_member(members, seat, p)
        if seat.endswith(".p1") and m is not None and not _same(m, p):
            spouse = active(seat[:-1] + "2")
            if spouse is not None and _same(spouse, p):
                # ReportDeath: parent 1 died with no children and parent 2 took their place.
                m.update(displaced=True, seat=seat + "#dead", state="died", left_seen=now,
                         left="Died with no children: the game put the one they married in their place in its "
                              "Family Tree.")
                spouse["seat"] = seat
                m = spouse
        if m is not None and not _same(m, p) and ".p2" in seat:
            state, words = _leaving(save, m)
            displace(m, state, words)
            m = None
        if m is None:
            m = create(p, seat)
            if p.father is not None or p.mother is not None:
                m["parents"] = [mid_of[q] for q in (p.father, p.mother) if q in mid_of]
        else:
            _record(m, p, now)
        mid_of[p.id] = m["mid"]

    # A spouse the save's tree no longer holds at all (parent 2 zeroed: Divorce Spouse).
    shown = {p.seat for p in village.people.values() if p.seat}
    current = len(save.family_tree.generations) + first_generation(folder, slot, save) - 1
    for m in members:
        if m.get("displaced") or m.get("seat") in shown:
            continue
        if ".p2" in m.get("seat", "") and int(m["seat"][1:].split(".")[0]) == current:
            state, words = _leaving(save, m)
            displace(m, state, words)

    _add_remembered(village, members, mid_of, now)
    data.update(format=FORMAT, game=gen.GAME, slot=slot, family=village.tribe, members=memory)
    try:
        write_tree_file(path, data)
    except OSError as exc:
        notes.append(f"The tree file could not be written ({exc}): members seen now are not remembered.")
    village.notes.extend(notes)
    return notes


def _add_remembered(village: gen.Village, members: list[dict], mid_of: dict[int, int], now: dict) -> None:
    """Every remembered member the save no longer shows, as a Person; and each child's remembered parents."""
    people = village.people
    person_of = {mid: pid for pid, mid in mid_of.items()}
    order = max((q.birth_record or 0 for q in people.values()), default=0)
    for m in members:
        if m["mid"] in person_of:
            continue
        order += 1
        pid = max(people, default=-1) + 1
        p = gen.Person(pid, m.get("name") or "(no name)", m.get("head"), m.get("body"), sex=m.get("sex"))
        p.seat = m.get("seat", "")
        p.age, p.cause, p.how, p.event = m.get("age"), m.get("cause") or "", m.get("how") or "", m.get("event") or ""
        p.heir, p.adopted, p.runner = bool(m.get("heir")), bool(m.get("adopted")), bool(m.get("runner"))
        p.likes, p.dislikes = m.get("likes"), m.get("dislikes")
        p.arrived = p.how in ("Married in", "Adopted", "Adopt New Person")
        p.former = list(m.get("former") or [])
        p.birth_record = order
        state = m.get("state")
        p.alive = False
        p.gone = "died" if state == "died" else "left"
        if m.get("left"):
            p.unknowns.append(m["left"])
            if m["left"].startswith("Divorced"):
                p.event = "Divorce Spouse"
        elif state != "died":
            p.unknowns.append(f"No longer in the save (last seen in the save of {m['last_seen']['saved_at']}); the "
                              "save does not say what became of them.")
        p.sources.append(f"Remembered by the tree file: first seen in the save of {m['first_seen']['saved_at']}.")
        people[pid] = p
        person_of[m["mid"]] = pid
    # Each child's parents as the tree saw them when the child first appeared (a first spouse, say).
    for m in members:
        parents = [person_of[q] for q in m.get("parents") or [] if q in person_of]
        if not parents or m["mid"] not in person_of:
            continue
        child = people[person_of[m["mid"]]]
        father, mother = gen._parents_by_sex(people, parents)
        if len(parents) == 2 or child.father is None and child.mother is None:
            child.father, child.mother = father, mother
    # A remembered spouse of the current record's first parent: their partner for the tree's lines.
    for m in members:
        if m.get("displaced") and m["mid"] in person_of and ".p2#" in m.get("seat", ""):
            people[person_of[m["mid"]]].arrived = True
