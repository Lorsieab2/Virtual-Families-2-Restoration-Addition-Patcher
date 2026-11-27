"""Game Mechanics: the Family members group -- every person a chosen Virtual Families 2 save holds, one by one (the
owner approved the port of the Virtual Villagers Fun Patcher's per-villager group, 2026-11-26; the Virtual Families
1 patcher has the same group).

Each family member is one bullet -- their name, sex, age and health -- with sub-bullets for what else the save keeps
for them: symptoms and an infection, the bars the Details screen shows (happiness, Fed, energy) and the hidden needs
(the happiness trend, dirtiness, the toilet need), food groups, career, level, progress and salary, likes and
dislikes, "Wants kids?" and fertility, their place in the save's Family Tree (spouse, parents, children), a pregnancy,
and the whole name from the patcher's Names file.  Family members at home come first (oldest first), then those away
from home (college, Boarding School, the Talent Scout), then anyone who died whose body is still in the house.
Nothing is guessed: every value is a field of the save, read with the patcher's own reader (vf2_save_reader; the
whole names through vf2_names), and the rules each value means are the ones the page's other groups state.

Where each value is in a villager record (docs/vf2-save-format.md section 4, docs/game-mechanics/spec.md sections
2-7; CVillagerState is copied whole at record +0xA8, so a state field +s is record +0xA8 + s):
  +0xB4 health, +0xB8 cause of death, +0xB0 the age units already processed, +0xCC the age unit of conception,
  +0xD0 babies expected, +0xDC energy, +0xE0 happiness, +0xE4 happiness trend (-500..500), +0xE8 hunger, +0xEC
  dirtiness, +0xF0 the toilet need, +0xF4 fertility, +0xF8 "Wants kids?" (SetProcreationDesire keeps it 1..99);
  +0x104..+0x10A the seven symptoms: CVillagerState::IsSick is "any of the seven bytes set" (an infection alone is
  not sick); +0x10C.. each symptom's end, a real-time stamp (SetSymptom: now + (rand(12) + 6) x 3,600);
  +0x128 / +0x129 the mild and the serious infection (state +0x80 / +0x81, spec section 3);
  +0x12C..+0x12F the four food groups' flags (Grains, Dairy, Meats, Fruits and Veggies) and +0x130.. their ends,
  real time: CVillagerState::FoodGroupsActive counts five slots, each while its flag is set and its end is not before
  now (unsigned), clearing an ended one; the fifth slot's flag is the low byte of the Grains end and its end is the
  career id (-1, no career, never ends);
  +0x140 career, +0x144 level, +0x148 progress toward the next promotion (3,000 promotes), +0x14C salary;
  +0x150 / +0x15C the likes and dislikes (CLikeList / CDislikeList, 3 places each, -1 empty), each an index into the
  game's own comma list, string 0x7AF (likes) or 0x7B0 (dislikes) (LIKE_WORDS; the Family Tree's words for the same
  people, which CLikeList::GetListAsString writes, match them: tests/test_game_mechanics_family.py).
A try for a baby that works: CVillagerPlans::ProcessCurrentPlan's try (case 73) and theMainScene's drop both call
CVillager::Impregnate with the father's name as the literal "Joey" (??_C@_04PIDKGECL@Joey) and the father's looks
(bio +0x2C / +0x30) from the Patriarch, so the save keeps "Joey", not the father's own name (only
CVillager::ConceiveChildWith passes the father's own name): the page names him through the save's Family Tree (or,
for a pregnancy, by those looks).
"Wants kids?" is CVillagerState::WantChildrenString: value / 10 picks No Way (0, 1), Not Really (2, 3), Maybe (4, 5),
Would Be Nice (6, 7), Definitely (8, 9, 10) (strings 0x723..0x727).

Read only: the save is read, never written.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import vf2_game_mechanics as gm
import vf2_save_reader as sr

GROUP = gm.FAMILY
C, E, U = gm.VERIFIED_C, gm.VERIFIED_E, gm.UNCONFIRMED
EVIDENCE = "src/vf2_game_mechanics_family.py: the save's villager record (docs/vf2-save-format.md section 4)"

PROCESSED, MILD, SERIOUS = 0xB0, 0x128, 0x129
SYMPTOMS, SYMPTOM_ENDS = 0x104, 0x10C
GROUP_FLAGS, GROUP_ENDS = 0x12C, 0x130
LIKES, DISLIKES = 0x150, 0x15C
FOOD_GROUPS = ("Grains", "Dairy", "Meats", "Fruits and Veggies")
# The diagnosis dialog's names for the seven symptoms (Health and sickness).
SYMPTOM_NAMES = ("hiccups", "a sore throat", "stomach", "a headache", "a cough", "a skin rash", "a runny nose")
# Strings 0x7AF (likes) and 0x7B0 (dislikes): the same list, picked by place (CLikeList::GetListAsString).  "water
# exercising" is one place: the game's list has no comma between "water" and "exercising".
LIKE_WORDS = tuple(w.strip() for w in (
    "ants, crowds, resting, laundry, medicine, turnips, butterflies, flowers, bees, the dark, snakes, wind, rocks, "
    "heights, playing, exploring, blue, green, red, yellow, bushes, sand, sunlight, wood, crab meat, fish, fruit, "
    "flies, swimming, running, studying, dancing, birds, work, lifting, surprises, jokes, sleeping, jumping, cooking, "
    "eating, dreaming, talking, holidays, vegetables, quiet, clouds, dirt, plants, rain, fog, sitting, stories, "
    "thunder, lightning, stars, water exercising, strolling, toys, insects, grass, spiders, roses, crickets, bathing, "
    "shaving, combing hair, makeup, flossing, brushing teeth, cleaning, loose socks, dusting, organizing, TV, "
    "Internet, spam, reading, technology, snacking, tools, computers, carbs, meat, milk, eggs, BBQ, burgers, pizza, "
    "sweets, pasta, soup, chocolate, peanut butter, soda, coffee, rice, bread, chicken, solitude, trains, cars, "
    "airplanes, robots, trash, fixing, shopping, pinball, music, art, gophers, outdoors, gardening, babies, drinking, "
    "piano, guitar, apples, moon, billiards").split(","))
WANTS_KIDS = ("No Way", "No Way", "Not Really", "Not Really", "Maybe", "Maybe", "Would Be Nice", "Would Be Nice",
              "Definitely", "Definitely", "Definitely")
CAREER_BY_ID = {c[0]: c for c in gm.CAREERS}
FATHER_STAND_IN = "Joey"
BABY, CHILD, MATING, OLD = 100, 280, 360, 1100     # spec section 5: < 5, < 14, 18..55, 55+ years
PREGNANCY_UNITS = 21                               # born on the unit after conception + 20 (spec section 6)
PROMOTION = 3000


@dataclass(frozen=True)
class Family:
    """A family save the window offers: its label and file."""
    label: str
    path: Path


def find_families(folders) -> list[Family]:
    """Every slot's save (Virtual Families 21..25.ldw) in the save folders that the patcher can read, in folder then
    slot order.  Only reads."""
    out: list[Family] = []
    for folder in folders:
        for slot in sr.FAMILY_SLOTS:
            path = Path(folder) / sr.save_file_name(slot)
            try:
                save = sr.read_family_save(path)
            except (OSError, ValueError, struct.error):
                continue
            name = _book(Path(folder)).full(slot, save.nickname) if save.nickname else ""
            out.append(Family(f"Save {slot}: {name or '(no name)'} ({Path(folder).name})", path))
    return out


def _book(folder: Path):
    import vf2_names
    return vf2_names.Book(folder)


def _i32(raw: bytes, at: int) -> int:
    return struct.unpack_from("<i", raw, at)[0]


def _u32(raw: bytes, at: int) -> int:
    return struct.unpack_from("<I", raw, at)[0]


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def duration(minutes: int) -> str:
    """'3 hours 10 minutes', '0 minutes'."""
    hours, rest = divmod(minutes, 60)
    parts = [_plural(n, unit) for n, unit in ((hours, "hour"), (rest, "minute")) if n]
    return " ".join(parts) or "0 minutes"


@dataclass
class Person:
    """One villager record with its raw bytes and its whole name."""
    v: sr.Villager
    raw: bytes
    name: str                       # the whole name (the save's own when it is no short form)


def when(save: sr.FamilySave, stamp: int) -> str:
    """A real-time stamp of the save (seconds from the family's start, the header's time) as your PC's local time."""
    moment = datetime.fromtimestamp(save.header.start_time + stamp)
    return f"{moment:%d %B %Y}, {moment:%H:%M}".lstrip("0")


def ages(units: int, alive: bool = True) -> str:
    """'41 years (827 age units; 13 more to the next birthday)'; for someone who died, no next birthday."""
    years = units // sr.AGE_UNITS_PER_YEAR
    if not alive:
        return f"{_plural(years, 'year')} ({units:,} age units)"
    left = sr.AGE_UNITS_PER_YEAR - units % sr.AGE_UNITS_PER_YEAR
    return f"{_plural(years, 'year')} ({units:,} age units; {left} more to the next birthday)"


def stage(units: int) -> str:
    """The ages the game's own rules turn on (spec section 5)."""
    if units < BABY:
        return "a baby (under 5)"
    if units < CHILD:
        return "a child (under 14)"
    if units < MATING:
        return "a teen (14 to 17): under 18, the age from which the game lets a family member have a baby"
    if units < OLD:
        return "a grown-up (18 or older)"
    return "55 or older: old age is rolled on every birthday and recovery is slower (see Old age, Health and sickness)"


def places(raw: bytes, at: int) -> tuple[int, int, int]:
    return struct.unpack_from("<3i", raw, at)


def like_text(where) -> str:
    words = [LIKE_WORDS[i] if 0 <= i < len(LIKE_WORDS) else f"(item {i}, not in the game's list)"
             for i in where if i != -1]
    return ", ".join(words) if words else "none"


def wants_kids(value: int) -> str:
    return WANTS_KIDS[min(10, max(0, value // 10))]


def food_groups(save: sr.FamilySave, raw: bytes) -> tuple[list[str], int, int]:
    """(the four groups' words, how many are running, how many slots FoodGroupsActive counts) when saved."""
    now = save.clock.real_seconds_at_save
    words, counted, live4 = [], 0, 0
    for k in range(5):
        flag = raw[GROUP_FLAGS + k]
        end = _u32(raw, GROUP_ENDS + 4 * k)
        live = bool(flag) and end >= now
        counted += live
        if k < 4:
            live4 += live
            if flag:
                words.append(f"{FOOD_GROUPS[k]} until {when(save, end)}" + ("" if live else " (already over)"))
    return words, live4, counted


def sick_words(save: sr.FamilySave, raw: bytes) -> str | None:
    have = [k for k in range(7) if raw[SYMPTOMS + k]]
    infections = [w for at, w in ((MILD, "a mild infection (Penicillin or Vancomycin ends it)"),
                                  (SERIOUS, "a serious infection (Vancomycin ends it)")) if raw[at]]
    if not have and not infections:
        return None
    parts = []
    if have:
        def one(k: int) -> str:
            end = _u32(raw, SYMPTOM_ENDS + 4 * k)
            over = ", already over when the family was saved" if end < save.clock.real_seconds_at_save else ""
            return f"{SYMPTOM_NAMES[k]} (its time ends {when(save, end)}, real time{over})"
        parts.append("Sick with " + ", ".join(one(k) for k in have))
    else:
        parts.append("Not sick by the game's test (no symptom), but carries " + " and ".join(infections))
    if have and infections:
        parts.append("also " + " and ".join(infections))
    return "; ".join(parts)


class Tree:
    """The save's Family Tree as the game matches a record to a villager (slot, sex and head, and the name)."""

    def __init__(self, save: sr.FamilySave):
        self.save = save
        self.records = save.family_tree.generations
        self.current = save.family_tree.current

    def villager(self, peep) -> sr.Villager | None:
        if not peep.present or not 0 <= peep.slot < sr.VILLAGER_SLOTS:
            return None
        v = self.save.villagers[peep.slot]
        return v if (v.name, v.gender, v.head) == (peep.name, peep.gender, peep.head) else None

    def couple(self) -> tuple:
        if self.current is None:
            return None, None
        return self.villager(self.current.parent1), self.villager(self.current.parent2)

    def spouse_of(self, v) -> sr.Villager | None:
        a, b = self.couple()
        if a is not None and a.slot == v.slot:
            return b
        if b is not None and b.slot == v.slot:
            return a
        return None

    def widowed_by(self, v):
        """The current generation's other parent when ``v`` is one of the two and that one died, else None."""
        rec = self.current
        if rec is None:
            return None
        for mine, theirs in ((rec.parent1, rec.parent2), (rec.parent2, rec.parent1)):
            if self.villager(mine) is v and theirs.present:
                them = self.villager(theirs)
                if theirs.slot == -1 or (them is not None and them.health <= 0):
                    return theirs
        return None

    def seat(self, v):
        """(seat words, (parent1, parent2) names from the Family Tree or None)."""
        rec = self.current
        if rec is None:
            return "", None
        number = len(self.records)
        if self.villager(rec.parent1) is v:
            if number > 1 and rec.parent1.heir_index >= 0:
                prev = self.records[-2]
                if rec.parent1.heir_index < len(prev.children):
                    return (f"the head of the family, generation {number} (the heir)",
                            (prev.parent1.name, prev.parent2.name))
            return f"the head of the family, generation {number}" + (" (the founder)" if number == 1 else ""), None
        if self.villager(rec.parent2) is v:
            return f"married into the family, generation {number}", None
        for child in rec.children:
            if self.villager(child) is v:
                return f"a child of generation {number}", (rec.parent1.name, rec.parent2.name)
        return "", None


def _parents_line(v, tree_parents, whole, married_in: bool = False) -> str:
    own = (whole(v.father_name), whole(v.mother_name))
    if tree_parents is not None:
        tree_parents = tuple(whole(n) for n in tree_parents)
        text = f"Parents: {tree_parents[0]} and {tree_parents[1]} (the save's Family Tree)."
        if own != tree_parents and any(own):
            text += f" Their own record keeps \"{own[0]}\" and \"{own[1]}\"" + (
                f": \"{FATHER_STAND_IN}\" is the name the game writes for the father when a try "
                "for a baby works." if v.father_name == FATHER_STAND_IN else ".")
        return text
    if not any(own):
        if married_in:
            return "Parents: none: married into the family; the save keeps no parents for them."
        return "Parents: none in the save (a founder, an adopted child, or one the game made without parents)."
    text = f"Parents: their own record keeps \"{own[0]}\" and \"{own[1]}\"; the save's Family Tree does not list them."
    if v.father_name == FATHER_STAND_IN:
        text += f" \"{FATHER_STAND_IN}\" is the name the game writes for the father when a try for a baby works."
    return text


def _children_line(save, tree: Tree, v, whole) -> str | None:
    rec = tree.current
    if rec is None or v not in tree.couple():
        return None
    words = []
    for child in rec.children:
        kid = tree.villager(child)
        unborn = 0 <= child.slot < sr.VILLAGER_SLOTS and child.slot in save.pending_baby_slots
        state = ("on the way, not born yet" if unborn else "not in the house" if kid is None or not kid.active
                 else "died" if kid.health <= 0 else "away from home" if kid.left_home else "at home")
        words.append(f"{whole(child.name)} ({state})")
    named = {c.name for c in rec.children}
    more = [whole(k.name) for k in save.household() if k.name not in named and k is not v
            and v.name in (k.father_name, k.mother_name)]
    text = "Children in the save's Family Tree: " + (", ".join(words) if words else "none")
    if more:
        text += "; more in the house that name them as a parent: " + ", ".join(more)
    return text + "."


def _progress_line(v) -> str | None:
    """The career's progress: skills +8, a field the save reader keeps as UNCONFIRMED (vf2_save_reader
    unconfirmed_skills_08), so its line is labelled UNCONFIRMED."""
    if v.career_id == -1 or v.career_id not in CAREER_BY_ID or not 0 <= v.career_level < len(gm.LEVELS):
        return None
    top = v.career_level == len(gm.LEVELS) - 1
    return (f"Career progress: {v.unconfirmed_skills_08:,} of {PROMOTION:,} "
            + ("(top level, no further promotion)." if top else "toward the next promotion."))


def _career_line(v) -> str:
    if v.career_id == -1:
        return "Career: none; no salary."
    career = CAREER_BY_ID.get(v.career_id)
    if career is None or not 0 <= v.career_level < len(gm.LEVELS):
        return (f"Career: number {v.career_id} at level {v.career_level}, not one of the game's "
                f"{len(gm.CAREERS)} careers and 8 levels.")
    _cid, place, name, salaries = career
    level = gm.LEVELS[v.career_level]
    text = (f"Career: {name} (works in the {gm.WORKPLACES[place]}), {level} (level {v.career_level + 1} of 8); "
            f"salary ${v.salary:,}: ${v.salary / 2:,.2f} per hour of game time (1 hour real time at Normal speed)")
    table = salaries[v.career_level]
    if v.salary != table:
        text += (f". The game's own table pays a {level} {name} ${table:,}: the save holds ${v.salary:,}, and the "
                 "save's value is the one paid")
    return text + "."


def _pregnancy_line(save, tree: Tree, p: Person) -> str | None:
    v = p.v
    if not v.pregnancy_mark:
        return None
    babies = {1: "1 baby", 2: "twins", 3: "triplets"}.get(v.babies_expected, f"{v.babies_expected} babies")
    due = v.pregnancy_mark + PREGNANCY_UNITS
    left = max(0, due - _i32(p.raw, PROCESSED))
    spouse = tree.spouse_of(v)
    father = (f"the father's looks are {spouse.name}'s" if spouse is not None and (
              v.pregnancy_father_head, v.pregnancy_father_body) == (spouse.head, spouse.body)
              else f"the father's looks: head {v.pregnancy_father_head}, body {v.pregnancy_father_body}")
    name = (f" (the save keeps the father's name as \"{v.pregnancy_father_name}\", the name the game writes for the "
            "father when a try for a baby works)" if v.pregnancy_father_name == FATHER_STAND_IN else
            f" (the save keeps the father's name as \"{v.pregnancy_father_name}\")")
    span = duration(left * 10)
    return (f"Pregnant with {babies}, conceived at the mother's age unit {v.pregnancy_mark:,}: born at her age "
            f"unit {due:,}, "
            f"{_plural(left, 'age unit')} to go ({span} of game time, {span} of real time at Normal speed); "
            f"{father}{name}.")


def _person(save, tree: Tree, p: Person, whole) -> list[gm.Fact]:
    out: list[gm.Fact] = []

    def add(text: str, label: str = C, sub: bool = True) -> None:
        out.append(gm.Fact(GROUP, text, label, EVIDENCE, sub))

    v, raw = p.v, p.raw
    sex = {0: "Male", 1: "Female"}.get(v.gender, f"sex value {v.gender}")
    if v.health <= 0:
        add(f"{p.name}: {sex}, died at {ages(v.age_units, alive=False)}; health {v.health}. The body is still in the "
            "house (it is taken away 240 age units after their last upkeep; see Health and sickness).", C, False)
        # The save reader marks the ECauseOfDeath values UNCONFIRMED (docs/vf2-save-format.md), so this line is too.
        cause = {-1: "Unknown", 0: "Disease", 1: "Starvation", 2: "Old age", 3: "Work accident",
                 4: "Act of Nature"}.get(v.cause_of_death, f"cause {v.cause_of_death}")
        add(f"The cause the save keeps: {v.cause_of_death}, probably {cause} (the game's cause values are not "
            "confirmed).", U)
        return out
    sick = sick_words(save, raw)
    head = f"{p.name}: {sex}, {ages(v.age_units)}; health {v.health} of 100"
    head += ", sick" if sick and sick.startswith("Sick") else ""
    add(head + ".", C, False)
    seat, tree_parents = tree.seat(v)
    add(("Away from home (college, Boarding School or the Talent Scout): they stay in the save but never age or "
         "update again (see Leaving home); " if v.left_home else "At home; ") + f"{stage(v.age_units)}."
        + (f" In the save's Family Tree: {seat}." if seat else ""))
    if p.name != v.name:
        add(f"Whole name: {p.name}; the save keeps the short form \"{v.name}\" and the patcher's Names file the whole "
            "name (Virtual Families 2 Patcher Data\\Names).")
    add((sick + ". See Health and sickness for what each does.") if sick else "Not sick: no symptom and no infection.")
    add(f"Details screen: Happiness {v.happiness}, Health {v.health}, Fed {100 - v.hunger} (100 less the hunger, "
        f"{v.hunger}), Energy {v.energy}.")
    add(f"Hidden: happiness trend {v.happiness_trend:+,} (-500 to 500; see Needs and upkeep for how it moves "
        f"happiness), dirtiness {v.dirtiness}, toilet need {v.poo} (at 90 it resets to 25 to 49).")
    groups, live, counted = food_groups(save, raw)
    text = ("Food groups when the family was saved (each lasts 24 hours of real time; your PC's clock): "
            + (", ".join(groups) or "none") + f". The game's count is {counted}")
    if counted > live and live:
        text += (f": {live} for the groups above and 1 more, the extra one a family member without a career gets "
                 "once they have had Grains (see Needs and upkeep)")
    elif counted > live:
        text += (" because a family member without a career gets one extra once they have had Grains (see Needs and "
                 "upkeep), even with no group now")
    add(text + ".")
    add(_career_line(v))
    progress = _progress_line(v)
    if progress:
        add(progress, U)
    add(f"Likes: {like_text(places(raw, LIKES))}. Dislikes: {like_text(places(raw, DISLIKES))}.")
    add(f"Wants kids?: {v.procreation_desire} (\"{wants_kids(v.procreation_desire)}\", as the game words it); "
        f"fertility {v.fertility} of 100" + (f" ({v.fertility - 85} over 85, added to the twins and triplets "
                                            "chances)" if v.fertility > 85 else "") + ".")
    spouse = tree.spouse_of(v)
    gone = tree.widowed_by(v)
    if spouse is not None and spouse.health > 0:
        add(f"Spouse: {whole(spouse.name)} (the save's Family Tree, generation {len(tree.records)}).")
    elif gone is not None:
        add(f"Spouse: {whole(gone.name)} (died; the save's Family Tree, generation {len(tree.records)}).")
    add(_parents_line(v, tree_parents, whole, married_in=seat.startswith("married into the family")))
    kids = _children_line(save, tree, v, whole)
    if kids:
        add(kids)
    pregnancy = _pregnancy_line(save, tree, p)
    if pregnancy:
        add(pregnancy)
    return out


def facts_for(data: bytes, whole=lambda name: name) -> list[gm.Fact]:
    """The group for one save's bytes (`whole` turns a stored short form into its whole name)."""
    save = sr.parse_family_save(data)
    tree = Tree(save)
    base = sr.gs_to_file(sr.GS_VILLAGERS)
    people = [Person(v, data[base + v.slot * sr.VILLAGER_RECORD_SIZE:base + (v.slot + 1) * sr.VILLAGER_RECORD_SIZE],
                     whole(v.name)) for v in save.villagers if v.active]
    home = [p for p in people if p.v.health > 0 and not p.v.left_home]
    away = [p for p in people if p.v.health > 0 and p.v.left_home]
    dead = [p for p in people if p.v.health <= 0]
    out = [gm.Fact(GROUP, (
        f"{whole(save.nickname) or '(no name)'}, generation {len(tree.records)}, saved "
        f"{when(save, save.clock.real_seconds_at_save)} (your PC's clock): {len(home)} at home, {len(away)} away from "
        "home" + (f", {len(dead)} died with the body still in the house" if dead else "")
        + ". Every value below is read from the save as it was written; the game moves them on from there. Ages count "
        "in age units (20 make a year; 1 age unit is 10 minutes of game time, 10 minutes of real time at Normal "
        "speed); the times are real time."), C, EVIDENCE)]
    for group in (home, away, dead):
        for p in sorted(group, key=lambda q: (-q.v.age_units, q.v.slot)):
            out += _person(save, tree, p, whole)
    unborn = [s for s in save.pending_baby_slots if 0 <= s < sr.VILLAGER_SLOTS]
    if unborn:
        out.append(gm.Fact(GROUP, f"Babies on the way: {len(unborn)}, kept hidden in the house until they are born "
                                  "(see Pregnancy and babies).", C, EVIDENCE))
    return out


def facts(path) -> list[gm.Fact]:
    """The Family members group for the save file `path` (one line saying why, when it cannot be read)."""
    path = Path(path)
    try:
        data = path.read_bytes()
        kind = sr.classify_save_file(path.name)
        if kind is not None and kind[0] == "family":
            book = _book(path.parent)
            return facts_for(data, lambda name, slot=kind[1]: book.full(slot, name) if name else name)
        return facts_for(data)
    except (OSError, ValueError, struct.error) as exc:
        return [gm.Fact(GROUP, f"This save could not be read: {exc}.", C, EVIDENCE)]
