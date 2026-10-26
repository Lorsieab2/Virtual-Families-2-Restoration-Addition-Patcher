"""The Family Tree Maker's family: who descends from whom in a Virtual Families 2 save, each family member's
generation, and what the records say about them.

A port of the Virtual Families 1 Patcher's genealogy (vf1_genealogy.py, itself the Virtual Villagers Fun Patcher's
src/vv_genealogy.py): the same Person and Village model, so the Family Tree Maker's renderer and editor
(vf2_family_tree, vf2_family_tree_window) work on it unchanged; the data comes from Virtual Families 2's own records,
read by vf2_save_reader.  Read only: nothing here writes a file.

Where the family comes from (docs/vf2-save-format.md section 5, docs/family-tree-maker.md; every rule below was
traced in Virtual Families 2's own code, FamilyTree.obj, not carried over from Virtual Families 1):

* the save's own Family Tree (CFamilyTree, VERIFIED): one record per generation, oldest first, at most the latest 30
  (MakeRoomInTree drops the oldest); each with the two parents (parent 1 the heir or founder, parent 2 the one who
  married in, written by UpdateParents) and up to six children in the order they joined (AddOffspring, which a
  baby gets at conception).  Record g+1's parent 1 carries the index of the child of record g it was cloned from
  (StartNextGeneration; -1 for the founder, StartFamilyTree).  ReportDeath (current record only): a parent with
  children, or a child, keeps their place with a slot of -1; parent 1 dying with no children is overwritten by
  parent 2 (rep movsd, ReportDeath+0x4F) and parent 2's present byte cleared; parent 2 dying with no children has
  only their present byte cleared (+0xC4), the rest of their record kept until a new marriage writes over it.  A
  person is matched to a villager record as the game itself does (slot, sex and head, FindPeepRecord) and by name;
* the save's villager records, for the people the tree's slots still point at: age, health, cause of death, left
  home, pregnancy, and the parents' names in their bio (none for an adopted child: SpawnSpecificPeep(age, sex, ..)
  passes no names, the one Adoption Services and The Little Visitor use);
* the Up to 28 Children sidecar (Virtual Families 2 Patcher Data\\Children\\<save file>.dat, runtime/native/b200kids),
  children 7 to 28 of the current generation, used only when its hash matches the save file;
* the Family History log and the tree file, when there are (vf2_family_history, vf2_tree_memory).

What no record says is left unknown and labelled as such (Person.unknowns), never guessed.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

import vf2_save_reader as reader

UNITS_PER_YEAR = reader.AGE_UNITS_PER_YEAR
GAME = 2                                  # the renderer's game number (one head sheet pair, SHEETS[2])
GAME_TITLE = "Virtual Families 2"

PATCHER_FOLDER = "Virtual Families 2 Patcher"                 # the patcher's folder for each save: ...\Save <N>
CHILDREN_FOLDER = "Virtual Families 2 Patcher Data\\Children"  # b200kids.cpp SidecarPath

SEX_WORDS = {0: "Male", 1: "Female"}      # bio+4: 0 male, 1 female (VERIFIED); the game's words eSayMale / eSayFemale


class GenealogyError(Exception):
    """The family could not be read; the message says why."""


Key = tuple  # (name, head, body)


@dataclass
class Person:
    id: int
    name: str
    head: int | None
    body: int | None
    sex: str | None = None              # "Male" / "Female"
    age: int | None = None              # age units (twentieths of a year): now, or at death
    alive: bool = False
    gone: str = ""                      # "died", "left" (no longer in the house) -- or "" (alive / unknown)
    father: int | None = None
    mother: int | None = None
    litter: int | None = None           # babies born together share one number
    expecting: bool = False             # a living mother-to-be
    runner: bool = False                # likes running (the Family Tree's likes words, is_runner)
    likes: list[str] | None = None      # the words they like, as the Family Tree keeps them; None = not known
    dislikes: list[str] | None = None
    arrived: bool = False               # joined the family from outside: married in or adopted
    how: str = ""                       # "Founder", "Married in", "Adopted"
    first_seen: str | None = None
    upcoming: bool = False              # a baby on the way (conceived, not born yet)
    birth_record: int | None = None     # its place in the family, record by record (birth order)
    generation: int = 1
    number: int | None = None           # its place in the whole tree, oldest first (number_people)
    old_looks: list[tuple[int, int]] = field(default_factory=list)
    former: list[str] = field(default_factory=list)     # names they had before (a rename the tree file saw)
    statuses: list[str] = field(default_factory=list)   # (the renderer's automatic marks: none in Virtual Families)
    # Virtual Families
    seat: str = ""                      # where the save's Family Tree holds them: "g2.p1", "g2.p2", "g2.c3", "house.7"
    event: str = ""                     # "Event names": what brought them in ("Married in", "The Little Visitor"...)
    left_home: bool = False             # alive and left home (the save's left-home flag, VERIFIED)
    left_why: str = ""                  # why they left home, when the Family History log says (the save does not)
    left_how: str = ""                  # the log's own words for it ("Eve is going to college!")
    partner: int | None = None          # the head of the family they married (the log)
    adopted: bool = False               # joined as an adopted child (no parents in their bio)
    heir: bool = False                  # inherited the house: parent 1 of a later generation
    cause: str = ""                     # the cause of death
    career: int | None = None           # ECareer (CVillagerSkills+0): -1 none; see career_words
    career_level: int | None = None     # CVillagerSkills+4 (only from their own villager record)
    event_title: str = ""               # the Random Event that brought them in or took them away (the log)
    event_kind: str = ""                # "Email" or "Popup": the kind of Random Event it is
    divorced: bool = False              # a spouse lost to divorce (the log, or the tree file's memory)
    spouse_number: int | None = None    # their place in their partner's marriages, 1 first (the log, see spouses)
    remarried: bool = False             # the head of the family married again
    slot: int | None = None             # the villager record they are matched to, if any
    unknowns: list[str] = field(default_factory=list)   # what the records do not say (shown, never guessed)
    sources: list[str] = field(default_factory=list)    # where each fact came from

    @property
    def key(self) -> Key:
        return (self.name, self.head, self.body)

    @property
    def years(self) -> int | None:
        return None if self.age is None else self.age // UNITS_PER_YEAR

    def age_text(self) -> str:
        if self.age is None:
            return "age unknown"
        text = f"{self.years} years old"
        return f"died at {text}" if self.gone == "died" else text

    def order_key(self) -> tuple:
        """Oldest first: in the order the family's records hold them (generation by generation, each record's
        parents before its children, the children in the order they joined), then the older."""
        return (self.upcoming, (self.first_seen or "")[:16], self.birth_record if self.birth_record is not None else -1,
                -(self.age or 0), self.name)


# The Family Tree's automatic marks: Virtual Families 2 keeps no special titles.
STATUS_ORDER: tuple = ()
GAME_STATUSES: dict = {GAME: ()}


@dataclass
class Village:
    """The family (the name is the Virtual Villagers model's: the renderer and the editor use it)."""
    game: int
    slot: int
    tribe: str                          # the player name the family slot is shown under (VF2 has no surname)
    people: dict[int, Person]
    notes: list[str] = field(default_factory=list)
    snapshot_dates: list[str] = field(default_factory=list)
    base_generation: dict[int, int] = field(default_factory=dict)
    relooked: dict[Key, Key] = field(default_factory=dict)
    full_names: dict[Key, str] = field(default_factory=dict)
    rename_questions: list = field(default_factory=list)
    identity_questions: list = field(default_factory=list)
    generations: int = 0                # the save's Family Tree records
    couples: dict = field(default_factory=dict)          # generation -> its parents' ids (as the save holds them)
    history_events: list = field(default_factory=list)   # the log's Random Events ("<when>: Popup Event: <title>")
    sources: list[str] = field(default_factory=list)     # the files read

    def living(self) -> list[Person]:
        return [p for p in self.people.values() if p.alive]

    def known(self) -> list[Person]:
        """Every family member the records name (the babies on the way are not born yet)."""
        return [p for p in self.people.values() if not p.upcoming]

    def children_of(self, pid: int) -> list[Person]:
        return [p for p in self.people.values() if pid in (p.father, p.mother)]


def without_heathens(village: Village) -> Village:
    """(Virtual Villagers' "Hide unconverted Heathens": Virtual Families has none.)"""
    return village


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def save_path(folder: Path, slot: int) -> Path:
    return Path(folder) / reader.save_file_name(slot)


def slot_root(folder: Path, slot: int) -> Path:
    """<save folder>\\Virtual Families 2 Patcher\\Save <N> (the patcher's own folder for the slot)."""
    return Path(folder) / PATCHER_FOLDER / f"Save {slot}"


def children_sidecar_path(folder: Path, slot: int) -> Path:
    return Path(folder) / CHILDREN_FOLDER / reader.children_sidecar_name(slot)


# ---- the Up to 28 Children sidecar (b200kids.cpp, "the sidecar") ----

KIDS_MAGIC = b"VF2KIDS\0"
KIDS_TAG = b"VF2B200\0"
KIDS_VERSION = 1
KIDS_HEADER = 52
KIDS_ENTRY = 64
KIDS_MAX = 22                           # KIDS_MAX_EXTRA_CHILDREN: children 7 to 28
KIDS_STATES = {1: "alive", 2: "dead", 3: "gone"}
_FNV_BASIS = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3


def fnv1a64(data: bytes) -> int:
    h = _FNV_BASIS
    for b in data:
        h = ((h ^ b) * _FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return h


@dataclass
class ExtraChild:
    slot: int
    sex: int
    state: str                          # "alive", "dead", "gone"
    head: int
    body: int
    age: int
    name: str


@dataclass
class ChildrenSidecar:
    save_hash: int
    save_size: int
    generations: int
    parent_slot: int
    parent_sex: int
    children: list[ExtraChild]


def read_children_sidecar(data: bytes) -> ChildrenSidecar | None:
    """The sidecar as b200kids reads it; None for anything it would refuse (wrong tags, size or checksum)."""
    if len(data) < KIDS_HEADER + 8 or data[:8] != KIDS_MAGIC or data[12:20] != KIDS_TAG:
        return None
    if struct.unpack_from("<I", data, 8)[0] != KIDS_VERSION or struct.unpack_from("<I", data, 20)[0] != len(data):
        return None
    count = struct.unpack_from("<I", data, 48)[0]
    if count > KIDS_MAX or len(data) != KIDS_HEADER + count * KIDS_ENTRY + 8:
        return None
    if struct.unpack_from("<Q", data, len(data) - 8)[0] != fnv1a64(data[:-8]):
        return None
    save_hash, save_size, gens, pslot, psex = struct.unpack_from("<QIiii", data, 24)
    kids = []
    for i in range(count):
        at = KIDS_HEADER + i * KIDS_ENTRY
        slot, sex, state, head, body, age = struct.unpack_from("<6i", data, at)
        if not 0 <= slot < reader.VILLAGER_SLOTS or state not in KIDS_STATES:
            return None
        name = data[at + 24:at + 24 + 28].split(b"\0", 1)[0].decode("cp1252", "replace")
        kids.append(ExtraChild(slot, sex, KIDS_STATES[state], head, body, age, name))
    return ChildrenSidecar(save_hash, save_size, gens, pslot, psex, kids)


def make_children_sidecar(save_bytes: bytes, generations: int, parent_slot: int, parent_sex: int,
                          children: list[ExtraChild]) -> bytes:
    """A sidecar in b200kids' format (for tests and synthetic families)."""
    states = {v: k for k, v in KIDS_STATES.items()}
    size = KIDS_HEADER + len(children) * KIDS_ENTRY + 8
    out = bytearray(size)
    out[:8] = KIDS_MAGIC
    struct.pack_into("<I", out, 8, KIDS_VERSION)
    out[12:20] = KIDS_TAG
    struct.pack_into("<I", out, 20, size)
    struct.pack_into("<QIiiiI", out, 24, fnv1a64(save_bytes), len(save_bytes), generations, parent_slot, parent_sex,
                     len(children))
    for i, c in enumerate(children):
        at = KIDS_HEADER + i * KIDS_ENTRY
        struct.pack_into("<6i", out, at, c.slot, c.sex, states[c.state], c.head, c.body, c.age)
        name = c.name.encode("cp1252")[:27]
        out[at + 24:at + 24 + len(name)] = name
    struct.pack_into("<Q", out, size - 8, fnv1a64(bytes(out[:-8])))
    return bytes(out)


# ---------------------------------------------------------------------------
# Reading the family
# ---------------------------------------------------------------------------

RUNNING = "running"                     # a likes word: string 0x7AF eSayLikesList (the game's own list)
NATURAL_BIRTH_FATHER = "Joey"           # Impregnate's father name for every natural birth (docs section 4, bio +0x34)
ADOPTED_EVENTS = ("Adoption Services", "The Little Visitor")   # the only stock adoptions of a child (AddOffspring
                                        # from CScrollingStoreScene::HandleUpgrade, CEventTheLittleVisitor1/2)

# ECauseOfDeath (CVillagerState+0x10) -> the game's words (strings 0x87B..0x880, in the enum's order).  0, 1 and 2
# are VERIFIED by what sets them (CVillagerManager::AllVillagersRealtimePhysiologyAndProductivityUpkeep: AdjustHealth
# with cause 0 after IsSick +0x2F5, cause 1 from hunger +0x1FA / +0x26B, SetHealth(0, 2) on the old-age roll +0x3C3);
# -1 (also passed by theMainScene and CVillagerPlans), 3 and 4 only by the strings' order: UNCONFIRMED.
CAUSES = {0: "Disease", 1: "Starvation", 2: "Old age"}
CAUSES_UNCONFIRMED = {-1: "Unknown causes", 3: "Work accident", 4: "Act of Nature"}


# CVillagerSkills::GetCareerName(ECareer): a table of 0x84 string ids (VillagerSkills.obj, its __static table),
# indexed by career % 0x84 -- strings 0x1A7 + career, in order (VERIFIED: the table and the strings read from the
# desktop objects).  GetCareerLevelName: string 0x281 + (level & 7).  GetJobName shows "<level> <career>".
CAREER_NAMES = (
    "Pastry Designer", "Wine Critic", "BBQ Sauce Creator", "Food Critic", "Cocktail Inventor", "Soup Taster",
    "Caterer", "Cake Designer", "Mustard Bottler", "Coffee Blender", "Personal Cook", "Fresh Pasta Maker",
    "Doughnut Decorator", "Candy Designer", "Food Photographer", "Fruit Examiner", "Salad Packager", "Meat Grader",
    "Mail-order Butcher", "Nut Processor", "Dry Fruit Packager", "Mail-order Baker", "Soup Inventor",
    "Recipe Inventor", "Vitamin Inventor", "Pesto Sauce Creator", "Ketchup Bottler", "Trail Mix Creator",
    "Chewing Gum Designer", "Food Sculptor", "Truffle Critic", "Fish Cleaner", "Pickler", "Coffee Critic",
    "Cupcake Designer", "Sauce Designer", "Jerky Maker", "Spice Mixer", "Engineer", "Architect",
    "Domain Name Seller", "Video Game Designer", "Tech Consultant", "Hacker", "Fiction Writer", "Journalist",
    "Lawyer", "Screenplay Writer", "Envelope Stuffer", "Graphic Designer", "Day Trader", "Poet", "Lyricist",
    "Programmer", "Accountant", "Publicist", "Nonfiction Writer", "Fairy Tale Writer", "Translator", "QA Engineer",
    "Telemarketer", "Talent Agent", "Recruiter", "Video Game Reviewer", "Essay Writer", "Web Designer", "Art Critic",
    "Music Critic", "Book Reviewer", "Online Gold Farmer", "Marketing Agent", "Paralegal", "Census Taker",
    "Digital Photo Editor", "Magazine Editor", "Rocket Scientist", "Lobbyist", "Math Tutor", "History Tutor",
    "English Tutor", "Statistician", "Online Store Operator", "Travel Agent", "Technical Writer",
    "Sustainability Consultant", "Artist", "Online Security", "Video Editor", "Toy Collector", "Comic Collector",
    "Online Poker Pro", "Composer", "Blogger", "Film Critic", "Spammer", "Wood Sculptor", "Dress Maker",
    "Toaster Repairer", "Dress Designer", "Candle Maker", "Jewelry Maker", "Film Processor", "Inventor",
    "Board Game Designer", "Model Builder", "Basket Maker", "Knife Sharpener", "Glue Mixer", "Silverware Polisher",
    "Tool Maker", "Toy Maker", "Box Maker", "Shoe Maker", "Dental Tool Maker", "Lens Crafter", "Key Maker",
    "Picture Framer", "Soap Inventor", "Eyeglass Repairer", "Ceramics Designer", "Denture Maker", "Camera Repairer",
    "Watch Fixer", "Puzzle Maker", "Chair Maker", "Shoe Repairer", "Toy Refurbisher", "Jewelry Cleaner",
    "Jewelry Smelter", "Cosmetics Designer", "Phone Repairer", "Pen Designer")
CAREER_LEVELS = ("Beginner", "Novice", "Apprentice", "Licensed", "Practiced", "Accomplished", "Exceptional", "Master")
# The Random Events that bring a family member in or take one away (the log's own titles), each an Email Event or a
# Popup Event: both are pop-ups (VERIFIED-E, docs/game-mechanics/spec.md section 11: Little Visitor, Talent Scout).
RANDOM_EVENTS = {"The Little Visitor": "Popup", "The Talent Scout": "Popup"}


def event_words(p: "Person") -> str:
    """"Popup Event: The Little Visitor" -- the Random Event that brought them in or took them away, with its kind
    ("Random Event: ..." when no record says which kind)."""
    if not p.event_title:
        return ""
    return f"{p.event_kind or 'Random'} Event: {p.event_title}"


def career_words(p: "Person") -> str:
    """The career as the game words it (GetJobName: "<level> <career>"), or "" when they have none or it is not
    known.  The level only when their own villager record gave it."""
    if p.career is None or not 0 <= p.career < len(CAREER_NAMES):
        return ""
    name = CAREER_NAMES[p.career]
    return f"{CAREER_LEVELS[p.career_level & 7]} {name}" if p.career_level is not None else name


def spouses(village: "Village") -> None:
    """Remarried, from what the save and the tree file prove: a head of the family with two or more spouses known
    in one generation (the save holds one at a time; the tree file keeps those it saw before)."""
    by_gen: dict[int, list] = {}
    for q in village.people.values():
        m = re.fullmatch(r"g(\d+)\.p2(?:#\w+)?", q.seat or "")
        if m:
            by_gen.setdefault(int(m.group(1)), []).append(q)
    for g, wed in by_gen.items():
        couple = village.couples.get(g) or []
        heads = [q for q in couple if village.people[q].seat != f"g{g}.p2"]
        if len(wed) >= 2 and heads:
            village.people[heads[0]].remarried = True


def is_runner(likes: list[str] | None) -> bool:
    """Likes running: the word in the likes the save's Family Tree keeps for them (SPeepRecord +0x34, written by
    UpdatePeepRecord from CLikeList::GetListAsString, the villager's own likes; VERIFIED)."""
    return any(w.strip().lower() == RUNNING for w in likes or [])


def _words(text: str) -> list[str] | None:
    words = [w.strip() for w in re.split(r"[,\n]", text or "") if w.strip()]
    return words or None


def _peep_person(pid: int, peep: reader.PeepRecord) -> Person:
    p = Person(pid, peep.name, peep.head, peep.body, sex=SEX_WORDS.get(peep.gender))
    p.likes = _words(peep.likes)
    p.dislikes = _words(peep.dislikes)
    p.runner = is_runner(p.likes)
    return p


def _peep(name: str, sex: int, head: int, body: int, slot: int) -> reader.PeepRecord:
    return reader.PeepRecord(name, True, sex, head, body, slot, -1, -1, "", "")


def matching_villager(save: reader.FamilySave, peep: reader.PeepRecord) -> reader.Villager | None:
    """The villager record a Family Tree entry is, if its slot still holds them: the slot, sex and head as the
    game's own FindPeepRecord matches them, and the name.  Older records' slots are stale (reused)."""
    if not 0 <= peep.slot < reader.VILLAGER_SLOTS:
        return None
    v = save.villagers[peep.slot]
    if v.gender == peep.gender and v.head == peep.head and v.name == peep.name:
        return v
    return None


def _dead_record(save: reader.FamilySave, peep: reader.PeepRecord) -> reader.Villager | None:
    """A dead member's own villager record, when the save still holds it (a record is never cleared, only reused):
    the one record with their name, sex, head and body and health 0.  None when there is not exactly one (reused,
    or two alike: never a guess)."""
    hits = [v for v in save.villagers if v.health <= 0 and v.name == peep.name and v.gender == peep.gender
            and v.head == peep.head and v.body == peep.body]
    return hits[0] if len(hits) == 1 else None


def cause_words(cause: int) -> str:
    if cause in CAUSES:
        return CAUSES[cause]
    word = CAUSES_UNCONFIRMED.get(cause)
    if word:
        return f"{word} (UNCONFIRMED: the save's cause number {cause}; no game code was found that sets it)" \
            if cause != -1 else f"{word} (UNCONFIRMED: the save's cause number -1, the game's \"no cause\")"
    return ""


def _apply_villager(p: Person, v: reader.Villager, unborn: set[int]) -> None:
    p.slot = v.slot
    p.age = v.age_units
    if v.career_id >= 0:                    # CVillagerSkills+0 / +4, their own record (VERIFIED)
        p.career, p.career_level = v.career_id, v.career_level
    if v.slot in unborn and not v.active:
        p.upcoming = True
        p.alive = False
        return
    if v.active and v.health > 0:
        p.alive = True
        p.gone = ""
        p.left_home = v.left_home
        p.expecting = v.pregnancy_mark != 0
    elif v.health <= 0:
        p.alive = False
        p.gone = "died"
        p.cause = p.cause or cause_words(v.cause_of_death)
    elif v.left_home:
        # Left home (SetLeftHome: college, Boarding School or The Talent Scout) and their record no longer in use.
        p.alive = False
        p.gone = "left"
        p.left_home = True
        p.unknowns.append("Left home (the save's left-home flag) and is no longer in the house; the save does not "
                          "say why they left or what became of them.")
    else:
        p.alive = False
        p.gone = "left"
        p.unknowns.append("Not in the house now: their villager record is no longer in use, and the save does not "
                          "say why.")


def load_village(folder: Path, game: int = GAME, slot: int = 1, full_names: bool = True,
                 rename_answers: dict | None = None, identity_answers: dict | None = None,
                 save_file: Path | None = None, remember: bool = False) -> Village:
    """The slot's family: every person the save's Family Tree and the Children sidecar name, filled in from the
    Family History log when there is one (vf2_family_history), and -- with `remember` -- from and into the Family
    Tree Maker's own tree file, which keeps every member it has seen in this save (vf2_tree_memory).  The save and
    the logs are only read.  `save_file` reads another file than Virtual Families 2<slot>.ldw (a backup copy)."""
    import vf2_family_history
    import vf2_tree_memory
    folder = Path(folder)
    path = Path(save_file) if save_file is not None else save_path(folder, slot)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise GenealogyError(f"The save {path} could not be read: {exc}") from exc
    try:
        save = reader.parse_family_save(data)
    except (reader.SaveFormatError, ValueError, IndexError, struct.error) as exc:
        raise GenealogyError(f"{path.name} is not a Virtual Families 2 save the patcher can read: {exc}") from exc
    first = vf2_tree_memory.first_generation(folder, slot, save) if remember else 1
    family = build_family(save, slot, data=data, sidecar=_sidecar(folder, slot), first_generation=first)
    family.sources.insert(0, str(path))
    if remember:
        vf2_tree_memory.remember(folder, slot, save, family)
    history = vf2_family_history.read(folder, slot)
    if history is not None:
        vf2_family_history.apply(family, history)
    finish(family)
    return family


def _sidecar(folder: Path, slot: int) -> ChildrenSidecar | None:
    try:
        raw = children_sidecar_path(folder, slot).read_bytes()
    except OSError:
        return None
    return read_children_sidecar(raw)


def _same_peep(a: reader.PeepRecord, b: reader.PeepRecord) -> bool:
    return (a.name, a.gender, a.head, a.body, a.slot) == (b.name, b.gender, b.head, b.body, b.slot)


def build_family(save: reader.FamilySave, slot: int, data: bytes | None = None,
                 sidecar: ChildrenSidecar | None = None, first_generation: int = 1) -> Village:
    """The family from a parsed save (and, when given, the Children sidecar of that very save file).
    `first_generation`: the generation of the save's oldest record (1 unless the tree file saw MakeRoomInTree drop
    older ones)."""
    people: dict[int, Person] = {}
    notes: list[str] = []
    unborn = {s for s in save.pending_baby_slots if 0 <= s < reader.VILLAGER_SLOTS}
    order = 0
    couple_of: dict[int, list[int]] = {}           # generation -> its parents' ids
    by_seat: dict[str, int] = {}
    tree_slots: set[int] = set()                   # every villager record a Family Tree entry is
    offset = max(0, first_generation - 1)

    def new(peep: reader.PeepRecord, seat: str) -> Person:
        nonlocal order
        pid = len(people)
        p = _peep_person(pid, peep)
        p.birth_record = order
        p.seat = seat
        order += 1
        people[pid] = p
        by_seat[seat] = pid
        return p

    def settle(p: Person, peep: reader.PeepRecord) -> None:
        """Alive, dead or gone, from the tree's slot and the villager record (a later record of the same person,
        the heir's, is newer than their entry among the children)."""
        p.unknowns = [u for u in p.unknowns if not u.startswith("Not in the house now")]
        if peep.slot == -1:
            # ReportDeath sets the slot of a parent with children, or of a child, to -1 (the current record
            # only): a death.
            p.alive, p.gone = False, "died"
            p.sources.append("The Family Tree records the death (its slot is -1).")
            dead = _dead_record(save, peep)
            if dead is not None:
                p.age = dead.age_units
                p.cause = p.cause or cause_words(dead.cause_of_death)
            return
        v = matching_villager(save, peep)
        if v is not None:
            tree_slots.add(v.slot)              # an heir's entry among the children names their own record too
            _apply_villager(p, v, unborn)
            return
        p.alive, p.gone = False, "left"
        p.unknowns.append("Not in the house now: the save no longer holds them, and does not say whether they "
                          "died or moved away.")

    def bio_event(c: Person, peep: reader.PeepRecord) -> None:
        """How a child joined, from their own bio (read only when their entry matched their own villager record:
        slot, sex, head and name): no parents' names -- adopted (Adoption Services or The Little Visitor, the only
        callers of SpawnSpecificPeep(age, sex, ..), which passes none)."""
        if c.slot is None or c.slot != peep.slot or c.upcoming or not 0 <= peep.slot < reader.VILLAGER_SLOTS:
            return
        v = save.villagers[peep.slot]
        if not v.father_name and not v.mother_name:
            c.adopted, c.arrived, c.how = True, True, "Adopted"
            c.event = "Adopted"
            c.unknowns.append("Adopted: Adoption Services or The Little Visitor -- the save does not say which.")

    def dead_spouse(peep: reader.PeepRecord, g: int) -> None:
        """Parent 2 who died with no children: ReportDeath cleared only their present byte (VERIFIED), so the
        record still names them until a new marriage writes over it."""
        q = new(peep, f"g{g}.p2")
        q.arrived, q.how, q.event = True, "Married in", "Married in"
        q.alive, q.gone = False, "died"
        q.sources.append("The Family Tree still names them as the spouse, marked no longer present: the game does "
                         "that only when a spouse dies with no children.")
        dead = _dead_record(save, peep)
        if dead is not None:
            q.age = dead.age_units
            q.cause = cause_words(dead.cause_of_death)

    records = save.family_tree.generations
    for rec in records:
        g = rec.index + 1 + offset
        shifted = rec.parent1.present and _same_peep(rec.parent1, rec.parent2) and not rec.parent2.present
        # Parent 1: the heir (a child of the generation before), or the founder.
        p1 = None
        if rec.parent1.present:
            idx = rec.parent1.heir_index
            prev = by_seat.get(f"g{g - 1}.c{idx}") if g > 1 and idx >= 0 else None
            if prev is not None and not shifted and people[prev].sex == SEX_WORDS.get(rec.parent1.gender):
                p1 = people[prev]
                p1.heir = True
                if p1.name != rec.parent1.name:
                    p1.former.append(p1.name)
                    p1.name = rec.parent1.name
                by_seat[f"g{g}.p1"] = p1.id
            else:
                p1 = new(rec.parent1, f"g{g}.p1")
                if shifted:
                    p1.arrived, p1.how, p1.event = True, "Married in", "Married in"
                    p1.unknowns.append("Married in: the one they married died with no children, and the game's Family "
                                       "Tree put them in that place (the save no longer names who that was).")
                elif g == 1 or (rec.index == 0 and offset == 0):
                    p1.how = "Founder"
                elif rec.index == 0:
                    p1.heir = True
                    p1.unknowns.append("The save's Family Tree holds only the latest 30 generations; the older ones "
                                       "the tree file did not see are not known.")
                elif idx >= 0:
                    p1.heir = True
                    p1.unknowns.append(f"Child number {idx + 1} of generation {g - 1}, but the save no longer "
                                       "holds that child's entry.")
                else:
                    p1.unknowns.append(
                        f"Not linked to a child of generation {g - 1} in the save's Family Tree: either the heir was "
                        "child 7 or later (Up to 28 Children), or they married in and took the place of a parent who "
                        "died with no children -- the save does not say which.")
            fresh = _peep_person(-1, rec.parent1)
            p1.likes, p1.dislikes = fresh.likes or p1.likes, fresh.dislikes or p1.dislikes
            # A parent's career as the tree record keeps it (UpdatePeepRecord, written while they exist; a
            # child's entry may never have been written, so a child's comes only from their villager record).
            if rec.parent1.career_id >= 0 and p1.career is None:
                p1.career = rec.parent1.career_id
            p1.runner = is_runner(p1.likes)
            settle(p1, rec.parent1)
        p2 = None
        if rec.parent2.present:
            p2 = new(rec.parent2, f"g{g}.p2")
            p2.arrived, p2.how, p2.event = True, "Married in", "Married in"
            settle(p2, rec.parent2)
            if rec.parent2.career_id >= 0 and p2.career is None:
                p2.career = rec.parent2.career_id
        elif rec.parent2.name and not shifted:
            dead_spouse(rec.parent2, g)
        couple = [p.id for p in (p1, p2) if p is not None]
        couple_of[g] = couple
        for k, peep in enumerate(rec.children):
            if not peep.present:
                continue
            c = new(peep, f"g{g}.c{k}")
            c.father, c.mother = _parents_by_sex(people, couple)
            settle(c, peep)
            bio_event(c, peep)                  # only when their own villager record matched (c.slot)
    generations = len(records)
    last = generations + offset

    # Children 7 to 28 of the current generation (b200kids), only from the sidecar of this very save file.
    if sidecar is not None and data is not None and generations:
        if sidecar.save_hash != fnv1a64(data) or sidecar.save_size != len(data):
            notes.append("The Up to 28 Children file belongs to another save file (an older or newer save), so "
                         "children 7 to 28 are not shown.")
        elif sidecar.generations != generations:
            notes.append("The Up to 28 Children file is for another generation, so it was not used.")
        else:
            couple = couple_of.get(last, [])
            for k, extra in enumerate(sidecar.children, start=6):
                peep = _peep(extra.name, extra.sex, extra.head, extra.body, extra.slot)
                c = new(peep, f"g{last}.c{k}")
                c.father, c.mother = _parents_by_sex(people, couple)
                c.sources.append("Children 7 to 28: the Up to 28 Children file.")
                if extra.state == "alive":
                    v = matching_villager(save, peep)
                    if v is not None:
                        _apply_villager(c, v, unborn)
                        bio_event(c, peep)
                    else:
                        c.alive = True
                        c.age = extra.age
                elif extra.state == "dead":
                    c.alive, c.gone, c.age = False, "died", extra.age
                else:
                    c.alive, c.gone, c.age = False, "left", extra.age

    # Anyone in the house the tree does not hold (alive, active): shown, with no family recorded.
    held = {p.slot for p in people.values() if p.slot is not None} | tree_slots
    for v in save.villagers:
        if v.active and v.health > 0 and v.slot not in held and v.name:
            peep = _peep(v.name, v.gender, v.head, v.body, v.slot)
            p = new(peep, f"house.{v.slot}")
            _apply_villager(p, v, unborn)
            p.unknowns.append("In the house, but the save's Family Tree does not record them, so their family is "
                              "not known.")

    # The babies of one pregnancy (gs+0x25AB0..0x25AB8, up to three, VERIFIED): twins or triplets on the way.
    coming = [q for q in people.values() if q.upcoming]
    if len(coming) > 1:
        for q in coming:
            q.litter = 1

    village = Village(GAME, slot, save.nickname, people, notes, generations=generations)
    village.couples = couple_of
    if generations >= reader.FAMILY_RECORDS:
        village.notes.append("The save's Family Tree is full (30 generations): the game drops the oldest generation "
                             "each time a new one starts.")
    village.notes.append("The save keeps no history: twins and triplets once born, a spouse before a new marriage, a "
                         "divorced spouse, and causes of death beyond a dead member's own record are not in it.")
    return village


def finish(village: Village) -> None:
    """Each member's generation and number (after the Family History and the tree file added what they know)."""
    spouses(village)
    _generations(village)
    number_people(village)


def _parents_by_sex(people: dict[int, Person], couple: list[int]) -> tuple[int | None, int | None]:
    """(father, mother) from a generation's two parents; a same-sex couple (Same-Sex Marriage) fills both in the
    tree's order (the order the tree holds them)."""
    father = mother = None
    for q in couple:
        if people[q].sex == "Female" and mother is None:
            mother = q
        elif people[q].sex == "Male" and father is None:
            father = q
        elif father is None:
            father = q
        elif mother is None:
            mother = q
    return father, mother


def seat_row(seat: str) -> int | None:
    """The tree row a Family Tree seat is drawn in: generation g's parents in row g, its children in row g + 1."""
    m = re.fullmatch(r"g(\d+)\.(p1(?:#\w+)?|p2(?:#\w+)?|c\d+)", seat or "")
    if not m:
        return None
    return int(m.group(1)) + (1 if m.group(2).startswith("c") else 0)


def _generations(village: Village) -> None:
    """Row g holds generation g's parents (the game's generation g); their children are in row g + 1, where
    the heir among them is generation g + 1's parent 1 and is joined by the one who married them."""
    people = village.people
    base: dict[int, int] = {}
    for pid, p in sorted(people.items(), key=lambda kv: kv[1].birth_record if kv[1].birth_record is not None else 0):
        row = seat_row(p.seat)
        if row is not None:
            base.setdefault(pid, row)
    # Anyone else: below the later of their parents, else beside their partner, else generation 1.
    for _round in range(4):
        for pid, p in people.items():
            if pid in base:
                continue
            parents = [q for q in (p.father, p.mother) if q is not None and q in base]
            if parents:
                base[pid] = 1 + max(base[q] for q in parents)
                continue
            partners = {k.father if k.mother == pid else k.mother for k in village.children_of(pid)} - {None}
            rows = [base[q] for q in partners if q in base]
            if rows:
                base[pid] = max(rows)
    for pid, p in people.items():
        p.generation = base.get(pid, 1)
    village.base_generation = {pid: p.generation for pid, p in people.items()}


# ---------------------------------------------------------------------------
# Numbering and names (the Virtual Villagers Family Tree Maker's, unchanged)
# ---------------------------------------------------------------------------

SORTS = {
    "appearance": "By appearance in the family",
    "age": "By age (oldest first)",
    "family": "By family (brothers and sisters together)",
    "name": "By name",
}


def number_people(village: Village, sort: str = "appearance") -> None:
    """Every family member's number: generation by generation, in the chosen order, never restarting.  A baby
    on the way has none yet, and comes last in its row."""
    n = 0
    people = village.people
    for g in sorted({p.generation for p in village.known()}):
        row = [p for p in village.known() if p.generation == g]
        if sort == "age":
            row.sort(key=lambda q: (-(q.age or 0), q.order_key()))
        elif sort == "name":
            row.sort(key=lambda q: (q.name.casefold(), q.order_key()))
        elif sort == "family":
            def family_key(q: Person) -> tuple:
                parents = sorted(people[r].number or 0 for r in (q.mother, q.father) if r is not None)
                return (tuple(parents) or (0,), q.order_key())
            row.sort(key=family_key)
        else:
            row.sort(key=lambda q: q.order_key())
        for p in row:
            n += 1
            p.number = n


def snapshot_dates(village: Village) -> list[str]:
    return list(village.snapshot_dates)


def is_arrival(p: Person, first_snapshot: str | None = None) -> bool:
    """Someone with no recorded parent who joined the family from outside: married in or adopted."""
    if p.father is not None or p.mother is not None or p.upcoming:
        return False
    return bool(p.arrived and p.how and p.how != "Founder")


ROMAN = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
         (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))


def roman(n: int) -> str:
    out = ""
    for value, letters in ROMAN:
        count, n = divmod(n, value)
        out += letters * count
    return out


NUMBER_ORDERS = {
    "oldest": "By age now, oldest first",
    "youngest": "By age now, youngest first",
    "appearance": "Oldest first (order of appearance)",
}


def duplicate_names(village: Village, order: str = "appearance", reserved: set[str] = frozenset(),
                    leave: set[int] = frozenset(), weight: dict[int, int] | None = None,
                    blocks: dict[int, list[str]] | None = None) -> dict[int, str]:
    """Each family member who shares a name with another, numbered ("Happi I", "Happi II"), the dead too, in
    the NUMBER_ORDERS order.  A number already carried is kept; a new namesake gets the next number never
    used.  (The tree's names only: nothing is written to the save.)"""
    keys = {
        "oldest": lambda p: (p.age is None, -(p.age or 0), p.order_key()),
        "youngest": lambda p: (p.age is None, p.age or 0, p.order_key()),
        "appearance": Person.order_key,
    }
    holders: dict[str, list[Person]] = {}
    for p in sorted(village.known(), key=keys[order]):
        if p.id not in leave:
            holders.setdefault(unnumbered(p.name), []).append(p)
    used: dict[str, set[int]] = {}
    for p in village.known():
        base, value = unnumbered(p.name), roman_value(p.name.rsplit(" ", 1)[-1])
        if base != p.name and value:
            used.setdefault(base, set()).add(value)
    for taken_name in reserved:
        base, value = unnumbered(taken_name), roman_value(taken_name.rsplit(" ", 1)[-1])
        if base != taken_name and value:
            used.setdefault(base, set()).add(value)
    out = {}
    for name, ps in holders.items():
        if sum((weight or {}).get(p.id, 1) for p in ps) < 2:
            continue
        numbers = used.setdefault(name, set())
        seen: set[str] = set()
        before = 0
        for p in ps:
            value = roman_value(p.name.rsplit(" ", 1)[-1]) if p.name != name else 0
            given = []
            if value and p.name not in seen:
                seen.add(p.name)
                before = max(before, value)
                given.append(p.name)
            for _ in range((weight or {}).get(p.id, 1) - len(given)):
                n = before + 1
                while n in numbers:
                    n += 1
                numbers.add(n)
                before = n
                given.append(f"{name} {roman(n)}")
            if given[0] != p.name:
                out[p.id] = given[0]
            if blocks is not None and len(given) > 1:
                blocks[p.id] = given
    return out


_ROMAN_VALUES: dict[str, int] = {}


def roman_value(word: str) -> int:
    if not _ROMAN_VALUES:
        _ROMAN_VALUES.update({roman(n): n for n in range(1, 4000)})
    return _ROMAN_VALUES.get(word, 0)


def unnumbered(name: str) -> str:
    words = name.split(" ")
    if len(words) > 1 and re.fullmatch(r"[IVXLCDM]+", words[-1]):
        return " ".join(words[:-1])
    return name


def numbered(p: Person) -> str:
    return f"#{p.number} {p.name}" if p.number is not None else p.name


def status_words(p: Person) -> str:
    """"(deceased)", "(no longer in the house)" or "" for the living."""
    if p.alive or p.upcoming:
        return ""
    return "(deceased)" if p.gone == "died" else "(no longer in the house)"


def describe_person(village: Village, p: Person) -> str:
    if p.upcoming:
        return f"{p.name} (on the way)"
    bits = [p.name, p.sex or "sex unknown", p.age_text()]
    if not p.alive:
        bits.append("dead" if p.gone == "died" else "no longer in the house")
        if p.cause:
            bits.append(f"cause: {p.cause}")
    elif p.left_home:
        bits.append("left home")
    if p.how and p.how != "Founder":
        bits.append(p.how.lower())
    for words in (event_words(p), career_words(p)):
        if words:
            bits.append(words)
    return ", ".join(bits)


def report(village: Village, game_title: str = GAME_TITLE) -> str:
    """The family's genealogy as text: every generation, who descends from whom."""
    people = village.people
    lines = [f"{game_title} -- Family Tree",
             f"Family: {village.tribe} (Save {village.slot})" if village.tribe else f"Save {village.slot}",
             "",
             "Generation I is the family's founder and the one who married them; each generation below holds the "
             "children of the one above, the heir who inherited the house and the one who married them.  Only "
             "what the save records is shown; what they do not say is marked unknown.",
             ""]
    for note in village.notes:
        lines.append(f"Note: {note}")
    if village.notes:
        lines.append("")
    by_gen: dict[int, list[Person]] = {}
    for p in people.values():
        by_gen.setdefault(p.generation, []).append(p)
    lines.append("== Generations ==")
    for g in sorted(by_gen):
        group = sorted(by_gen[g], key=lambda q: q.order_key())
        born = [p for p in group if not p.upcoming]
        coming = len(group) - len(born)
        lines.append(f"Generation {roman(g)}: {len(born)} family members ({sum(p.alive for p in born)} living)"
                     + (f", {coming} on the way" if coming else ""))
        for p in group:
            parents = [people[q].name for q in (p.father, p.mother) if q is not None]
            lines.append(f"  {describe_person(village, p)}"
                         + (f" -- child of {' and '.join(parents)}" if parents else ""))
            kids = village.children_of(p.id)
            if kids:
                lines.append(f"    children: {', '.join(k.name for k in sorted(kids, key=lambda q: q.order_key()))}")
            for unknown in p.unknowns:
                lines.append(f"    unknown: {unknown}")
        lines.append("")
    return "\n".join(lines)
