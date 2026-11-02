"""Read-only reader for Virtual Families 2 save files ("Virtual Families 2<N>.ldw").

Every offset here comes from the game's own save writer and loader (the desktop object files the
patcher relinks: ldwGameState.obj, theGameState.obj, VillagerManager.obj, Villager.obj,
VillagerBio.obj, VillagerState.obj, VillagerSkills.obj, FamilyTree.obj, GameTime.obj, Money.obj,
FoodStore.obj, GameStats.obj) and was checked against real saves. docs/vf2-save-format.md lists every
field with its evidence and marks what is VERIFIED and what is UNCONFIRMED. Fields whose meaning is
not established are returned raw under a name that says so (``unconfirmed_*``); nothing is inferred.

The module never writes, renames or locks a file: it reads bytes. Use it on copies of saves.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path

import vf2_game_text as game_text

# --- the file: ldwGameState::Save / Load ----------------------------------------------------------

MAGIC = b"ldwg"
HEADER_SIZE = 16                 # gameStateHeaderBlock: magic, int64 start time, uint32 payload size
LEGACY_HEADER_SIZE = 12          # the older header Load also accepts: magic, int32 time, uint32 size
GAME_DATA_SIZE = 0x25B18         # theGameState::Save/Load(slot > 0): theGameData, 154,392 bytes
SETTINGS_DATA_SIZE = 0x90        # theGameState::Save/Load(0): the settings block, 144 bytes
GAME_FILE_SIZE = HEADER_SIZE + GAME_DATA_SIZE        # 154,408
SETTINGS_FILE_SIZE = HEADER_SIZE + SETTINGS_DATA_SIZE  # 160

GAME_NAME = "Virtual Families 2"  # theGameState::GetGameName
FAMILY_SLOTS = range(1, 6)        # theGameState::LoadCurrentGame tries slots 1..5
PREVIOUS_SAVE_OFFSET = 20         # ldwGameState::Save: remove slot+20, rename slot -> slot+20

# theGameData is theGameState+8 .. theGameState+0x25B20; a theGameState offset is file offset - 8.
GS_TO_FILE = HEADER_SIZE - 8

# theGameState::Save / Load(int) component offsets (theGameState-relative)
GS_FAMILY_TREE = 0x1840
GS_FOOD_STORE = 0xE3B4
GS_GAME_STATS = 0x163C8
GS_GAME_TIME = 0x163FC
GS_MONEY = 0x168B4
GS_VILLAGERS = 0x172A8
GS_PENDING_BABIES = 0x25AB0      # three slots written by CVillager::Impregnate, -1 = none
GS_NICKNAME = 0x25ABC            # theCreateNickNameDlg: GetText(gs+0x25ABC, 0x14)
GS_SAVE_VERSION = 0x25AD8        # theGameState::Save writes 0x3E9 (1001)
GS_SPEED_OPTION = 0x25B18        # theGameState::InitOptions writes 10

VILLAGER_SLOTS = 30
VILLAGER_RECORD_SIZE = 0x7BC
FAMILY_RECORDS = 30
FAMILY_RECORD_SIZE = 0x6C8
PEEP_RECORD_SIZE = 0xD8
FAMILY_CHILD_SLOTS = 6

AGE_UNITS_PER_YEAR = 20          # theVillagerScene::UpdateScene prints age / 20
GAME_SECONDS_PER_YEAR = 12000    # CVillager::YearsAwayFromHome divides game seconds by 12000
COLLEGE_AGE_UNITS = 0x17C        # AllVillagersTimeflowUpkeep / GetRandomCollegeKid: 380
OLD_AGE_UNITS = 0x44C            # CVillagerBio::IsOld: 1100
NO_CAREER_AGE_UNITS = 0x154      # CVillager::Init: SetNoCareer below 340

GENDER_NAMES = {0: "male", 1: "female"}   # CVillagerBio::Reset / SetRandomName (1 = female names)


class SaveFormatError(ValueError):
    """The bytes are not a Virtual Families 2 save the game itself would load."""


def gs_to_file(gs_offset: int) -> int:
    """File offset of a theGameState field (the payload starts at theGameState+8)."""
    return gs_offset + GS_TO_FILE


def _cstr(raw: bytes) -> str:
    """A text field's text: the patcher's one rule (vf2_game_text.decode: UTF-8 when the bytes are UTF-8, else one
    character per byte)."""
    return game_text.decode(raw)


def _i32(b: bytes, off: int) -> int:
    return struct.unpack_from("<i", b, off)[0]


def _u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def _c_div(a: int, b: int) -> int:
    """C integer division (truncates toward zero), as the game's code does."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


# --- header -----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Header:
    magic: bytes
    start_time: int          # gameStateHeader+4: the time64 GetSecondsFromGameStart counts from
    payload_size: int
    header_size: int         # 16, or 12 for the legacy header

    @property
    def legacy(self) -> bool:
        return self.header_size == LEGACY_HEADER_SIZE


def parse_header(data: bytes) -> Header:
    """The header exactly as ldwGameState::Load reads it (the 16-byte form, else the 12-byte form)."""
    if len(data) >= HEADER_SIZE and data[:4] == MAGIC:
        size = _u32(data, 12)
        if size and len(data) == HEADER_SIZE + size:
            return Header(MAGIC, struct.unpack_from("<q", data, 4)[0], size, HEADER_SIZE)
    if len(data) >= LEGACY_HEADER_SIZE and data[:4] == MAGIC:
        size = _u32(data, 8)
        if len(data) == LEGACY_HEADER_SIZE + size:
            return Header(MAGIC, _i32(data, 4), size, LEGACY_HEADER_SIZE)
    if data[:4] != MAGIC:
        raise SaveFormatError("not an ldw save file (no 'ldwg' magic)")
    raise SaveFormatError("the header's payload size does not match the file size")


# --- villagers: CVillagerManager::SaveState -> CVillager::SaveState (0x7BC each) -----------------

@dataclass(frozen=True)
class Villager:
    slot: int                      # record index = CVillagerManager slot (30 records, slot order)
    active: bool                   # +0x000 byte  CVillager+0x1BB84
    left_home: bool                # +0x001 byte  CVillager+0x1BB88 (SetLeftHome)
    left_home_game_seconds: int    # +0x004 u32   CVillager+0x1BB8C (CGameTime::Seconds at SetLeftHome)
    # CVillagerBio (+0x008, 0xA0 bytes, CVillager+0x6A54)
    age_units: int                 # bio+0x00
    gender: int                    # bio+0x04
    first_name_index: int          # bio+0x08 (SetRandomName: comma index into the name list)
    unconfirmed_bio_0c: int        # bio+0x0C (SetRandomName arg; passed from mother to child)
    name: str                      # bio+0x10 char[25]
    head: int                      # bio+0x2C
    body: int                      # bio+0x30
    father_name: str               # bio+0x34 char[25] (Init arg 4)
    mother_name: str               # bio+0x4E char[25] (Init arg 5)
    father_head: int               # bio+0x68
    father_body: int               # bio+0x6C
    mother_head: int               # bio+0x70
    mother_body: int               # bio+0x74
    pregnancy_father_bio_0c: int   # bio+0x78 (Impregnate arg 1)
    pregnancy_father_name: str     # bio+0x7C char[24] (Impregnate arg 2)
    pregnancy_father_body: int     # bio+0x98 (Impregnate arg 4)
    pregnancy_father_head: int     # bio+0x9C (Impregnate arg 3)
    # CVillagerState (+0x0A8, 0x98 bytes, CVillager+0x6AF4)
    unconfirmed_state_00: int      # state+0x00 real seconds accumulated toward the next age step
    unconfirmed_state_04: int      # state+0x04 GetSecondsFromGameStart stamp of the last age step
    unconfirmed_state_08: int      # state+0x08 Reset(age) value; compared with state+0x24 for birth
    health: int                    # state+0x0C 0..100 (SetHealth/AdjustHealth clamp; 0 = dead)
    cause_of_death: int            # state+0x10 ECauseOfDeath, -1 while health > 0
    energy: int                    # state+0x34
    happiness: int                 # state+0x38
    happiness_trend: int           # state+0x3C (-500..500)
    hunger: int                    # state+0x40
    dirtiness: int                 # state+0x44
    poo: int                       # state+0x48 (SetPoo)
    fertility: int                 # state+0x4C
    procreation_desire: int        # state+0x50 (1..99)
    pregnancy_mark: int            # state+0x24 nonzero while pregnant (Impregnate copies state+0x08)
    babies_expected: int           # state+0x28 1/2/3 written by Impregnate
    symptoms: tuple                # state+0x5C 7 bytes (IsSick: any nonzero)
    # CVillagerSkills (+0x140, 0x10 bytes, CVillager+0x6B8C)
    career_id: int                 # skills+0x00 (-1 = no career)
    career_level: int              # skills+0x04
    unconfirmed_skills_08: int     # skills+0x08
    salary: int                    # skills+0x0C (UpdateSalary)
    likes_raw: bytes               # +0x150 12 bytes CLikeList (CVillager+0x1BC34)
    dislikes_raw: bytes            # +0x15C 12 bytes CDislikeList (CVillager+0x1BC40)
    ai_values: tuple               # +0x168 u16 x count (SaveAI); count at +0x7B8 (0x19B)

    @property
    def age_years(self) -> int:
        return _c_div(self.age_units, AGE_UNITS_PER_YEAR)

    @property
    def gender_name(self) -> str:
        return GENDER_NAMES.get(self.gender, f"unknown({self.gender})")

    @property
    def dead(self) -> bool:
        """Health 0 is death (SetHealth/AdjustHealth store the cause only then)."""
        return self.active and self.health <= 0

    @property
    def career_type(self) -> int:
        """CVillagerSkills::CareerType: 0 none, 1 if id <= 0x25, 2 if <= 0x5E, else 3."""
        if self.career_id == -1:
            return 0
        if self.career_id <= 0x25:
            return 1
        return 3 if self.career_id > 0x5E else 2

    @property
    def is_old(self) -> bool:
        return self.age_units >= OLD_AGE_UNITS


def _parse_villager(b: bytes, slot: int) -> Villager:
    v = gs_to_file(GS_VILLAGERS) + slot * VILLAGER_RECORD_SIZE
    bio = v + 0x08
    st = v + 0xA8
    sk = v + 0x140
    count = _u32(b, v + 0x7B8)
    n_ai = count if 0 < count <= 0x19B else 0
    return Villager(
        slot=slot,
        active=b[v] != 0,
        left_home=b[v + 1] != 0,
        left_home_game_seconds=_u32(b, v + 4),
        age_units=_i32(b, bio),
        gender=_i32(b, bio + 0x04),
        first_name_index=_i32(b, bio + 0x08),
        unconfirmed_bio_0c=_i32(b, bio + 0x0C),
        name=_cstr(b[bio + 0x10:bio + 0x10 + 25]),
        head=_i32(b, bio + 0x2C),
        body=_i32(b, bio + 0x30),
        father_name=_cstr(b[bio + 0x34:bio + 0x34 + 25]),
        mother_name=_cstr(b[bio + 0x4E:bio + 0x4E + 25]),
        father_head=_i32(b, bio + 0x68),
        father_body=_i32(b, bio + 0x6C),
        mother_head=_i32(b, bio + 0x70),
        mother_body=_i32(b, bio + 0x74),
        pregnancy_father_bio_0c=_i32(b, bio + 0x78),
        pregnancy_father_name=_cstr(b[bio + 0x7C:bio + 0x7C + 24]),
        pregnancy_father_body=_i32(b, bio + 0x98),
        pregnancy_father_head=_i32(b, bio + 0x9C),
        unconfirmed_state_00=_u32(b, st + 0x00),
        unconfirmed_state_04=_u32(b, st + 0x04),
        unconfirmed_state_08=_i32(b, st + 0x08),
        health=_i32(b, st + 0x0C),
        cause_of_death=_i32(b, st + 0x10),
        energy=_i32(b, st + 0x34),
        happiness=_i32(b, st + 0x38),
        happiness_trend=_i32(b, st + 0x3C),
        hunger=_i32(b, st + 0x40),
        dirtiness=_i32(b, st + 0x44),
        poo=_i32(b, st + 0x48),
        fertility=_i32(b, st + 0x4C),
        procreation_desire=_i32(b, st + 0x50),
        pregnancy_mark=_i32(b, st + 0x24),
        babies_expected=_i32(b, st + 0x28),
        symptoms=tuple(b[st + 0x5C:st + 0x63]),
        career_id=_i32(b, sk),
        career_level=_i32(b, sk + 4),
        unconfirmed_skills_08=_i32(b, sk + 8),
        salary=_i32(b, sk + 0xC),
        likes_raw=bytes(b[v + 0x150:v + 0x15C]),
        dislikes_raw=bytes(b[v + 0x15C:v + 0x168]),
        ai_values=struct.unpack_from("<%dH" % n_ai, b, v + 0x168) if n_ai else (),
    )


# --- the Family Tree: CFamilyTree::SaveState ---------------------------------------------------------

@dataclass(frozen=True)
class PeepRecord:
    """CFamilyTree::SPeepRecord (0xD8), written by StartNextGeneration/UpdateParents/AddOffspring."""
    name: str            # +0x00 char[25]
    present: bool        # +0x1A
    gender: int          # +0x1C
    head: int            # +0x20
    body: int            # +0x24
    slot: int            # +0x28 household slot; ReportDeath writes -1
    heir_index: int      # +0x2C parent 1: index of the child of the previous record who started it
    career_id: int       # +0x30 (UpdatePeepRecord copies CVillagerSkills+0)
    likes: str           # +0x34 char[40] (CLikeList::GetListAsString)
    dislikes: str        # +0x5D char[40] (CDislikeList::GetListAsString)


@dataclass(frozen=True)
class FamilyRecord:
    """CFamilyTree::SFamilyRecord (0x6C8): one generation."""
    index: int                         # 0-based position in the 30-record window
    can_start_next_generation: bool    # +0x001
    need_next_generation_notify: bool  # +0x002
    parent1: PeepRecord                # +0x004
    parent2: PeepRecord                # +0x0DC (the spouse: UpdateParents; CanMarry tests its present byte)
    child_count: int                   # +0x1B4 (AddOffspring refuses at 6)
    children: tuple                    # +0x1B8, 6 x 0xD8; only the first child_count are recorded


@dataclass(frozen=True)
class FamilyTree:
    evicted: int                       # block+0: CFamilyTree+0 (EvictFamily writes 1, Reset 0)
    generations: tuple                 # records whose present byte (+0) is set, in stored order

    @property
    def num_generations(self) -> int:
        """CFamilyTree+4 after LoadState: the number of present records."""
        return len(self.generations)

    @property
    def current(self) -> FamilyRecord | None:
        return self.generations[-1] if self.generations else None


def _parse_peep(b: bytes, p: int) -> PeepRecord:
    return PeepRecord(
        name=_cstr(b[p:p + 25]),
        present=b[p + 0x1A] != 0,
        gender=_i32(b, p + 0x1C),
        head=_i32(b, p + 0x20),
        body=_i32(b, p + 0x24),
        slot=_i32(b, p + 0x28),
        heir_index=_i32(b, p + 0x2C),
        career_id=_i32(b, p + 0x30),
        likes=_cstr(b[p + 0x34:p + 0x34 + 0x28]),
        dislikes=_cstr(b[p + 0x5D:p + 0x5D + 0x28]),
    )


def _parse_family_tree(b: bytes) -> FamilyTree:
    base = gs_to_file(GS_FAMILY_TREE)
    gens = []
    for i in range(FAMILY_RECORDS):
        r = base + 4 + i * FAMILY_RECORD_SIZE
        if not b[r]:
            break   # CFamilyTree::LoadState stops at the first record whose present byte is 0
        count = _i32(b, r + 0x1B4)
        kids = tuple(_parse_peep(b, r + 0x1B8 + k * PEEP_RECORD_SIZE)
                     for k in range(max(0, min(count, FAMILY_CHILD_SLOTS))))
        gens.append(FamilyRecord(
            index=i,
            can_start_next_generation=b[r + 1] != 0,
            need_next_generation_notify=b[r + 2] != 0,
            parent1=_parse_peep(b, r + 0x04),
            parent2=_parse_peep(b, r + 0xDC),
            child_count=count,
            children=kids,
        ))
    return FamilyTree(evicted=_i32(b, base), generations=tuple(gens))


# --- clock, money, food, statistics -------------------------------------------------------------------

@dataclass(frozen=True)
class GameClock:
    """CGameTime::SaveState (0x14 bytes)."""
    speed: int                    # +0x00 CGameTime+0x20; SpeedMultiplier = speed / 10; 0 = paused
    previous_speed: int           # +0x04 CGameTime+0x24
    real_reference: int           # +0x08 CGameTime+0x28 (GetSecondsFromGameStart at the last speed change)
    game_seconds_base: int        # +0x0C CGameTime+0x2C (Seconds() at that change)
    real_seconds_at_save: int     # +0x10 GetSecondsFromGameStart when the save was written

    @property
    def game_seconds_at_save(self) -> int:
        """CGameTime::Seconds() evaluated at the save instant, with the game's own float arithmetic."""
        if self.speed == 0:
            return self.game_seconds_base
        mult = struct.unpack("<f", struct.pack("<f", self.speed / 10.0))[0]
        elapsed = self.real_seconds_at_save - self.real_reference if self.real_seconds_at_save > self.real_reference else 0
        elapsed_f = struct.unpack("<f", struct.pack("<f", float(elapsed)))[0]
        q = struct.unpack("<f", struct.pack("<f", elapsed_f / mult))[0]
        return (int(q) + self.game_seconds_base) & 0xFFFFFFFF


@dataclass(frozen=True)
class Money:
    """CMoney::SaveState (0xC bytes)."""
    amount: int                   # +0 u32: the double balance rounded (+0.5, truncated)
    interest_raw: int             # +4 (CMoney+8 * 100) | 0x7F800000; LoadState decodes low 16 bits / 100
    last_interest_game_seconds: int  # +8 CMoney+0xC (UpdateInterest: game seconds of the last payment)

    @property
    def interest_rate(self) -> float | None:
        """CMoney+8 as LoadState rebuilds it: the fraction UpdateInterest pays per 86,400 game seconds."""
        if self.interest_raw & 0x7F800000 == 0x7F800000:
            return (self.interest_raw & 0xFFFF) / 100.0
        return None   # the legacy float form LoadState also accepts; not decoded here


@dataclass(frozen=True)
class FoodStore:
    """CFoodStore::SaveState (0x10 bytes)."""
    food: int                     # +0 CFoodStore+0x78 (the daily email's low-food test: <= 100)
    unconfirmed_flag_04: int      # +4 bool CFoodStore+0x7C
    unconfirmed_08: int           # +8 CFoodStore+0x80
    unconfirmed_bytes_0c: tuple   # +C..+F CFoodStore+0x84..0x87


@dataclass(frozen=True)
class GameStats:
    """CGameStats::SaveState (0x34 bytes, a copy of CGameStats+0..0x33)."""
    raw: tuple                    # 13 dwords
    @property
    def real_start_stamp(self) -> int:
        return self.raw[0]        # GetStatRealGameHoursThisGame: (now - stats+0) / 3600
    @property
    def babies_born(self) -> int:
        return self.raw[2]        # CVillager::Impregnate adds the baby count to GameStats+8
    @property
    def oldest_age_years(self) -> int:
        return self.raw[8]        # AllVillagersTimeflowUpkeep raises GameStats+0x20 to age / 20


# --- the whole family save ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FamilySave:
    header: Header
    villagers: tuple
    family_tree: FamilyTree
    clock: GameClock
    money: Money
    food: FoodStore
    stats: GameStats
    pending_baby_slots: tuple     # gs+0x25AB0/4/8
    nickname: str                 # gs+0x25ABC char[20]
    save_version: int             # gs+0x25AD8 (1001)
    speed_option: int             # gs+0x25B18 (InitOptions 10; >= 999 stops aging)

    def villager(self, slot: int) -> Villager:
        return self.villagers[slot]

    def household(self) -> list:
        """Villagers living in the house: active, not left home, health above 0 (VillagerExists + alive)."""
        return [v for v in self.villagers if v.active and not v.left_home and v.health > 0]

    def away(self) -> list:
        """Active villagers with the left-home flag (college, boarding school, talent scout)."""
        return [v for v in self.villagers if v.active and v.left_home]

    def unborn(self) -> list:
        """Slots CVillager::Impregnate reserved for babies on the way (inactive until birth)."""
        return [self.villagers[s] for s in self.pending_baby_slots if 0 <= s < VILLAGER_SLOTS]


def parse_family_save(data: bytes) -> FamilySave:
    header = parse_header(data)
    if header.legacy or header.payload_size != GAME_DATA_SIZE:
        raise SaveFormatError(
            "payload is %d bytes; theGameState::Load accepts only %d" % (header.payload_size, GAME_DATA_SIZE))
    b = data
    t = gs_to_file(GS_GAME_TIME)
    m = gs_to_file(GS_MONEY)
    f = gs_to_file(GS_FOOD_STORE)
    g = gs_to_file(GS_GAME_STATS)
    p = gs_to_file(GS_PENDING_BABIES)
    return FamilySave(
        header=header,
        villagers=tuple(_parse_villager(b, i) for i in range(VILLAGER_SLOTS)),
        family_tree=_parse_family_tree(b),
        clock=GameClock(_i32(b, t), _i32(b, t + 4), _u32(b, t + 8), _u32(b, t + 12), _u32(b, t + 16)),
        money=Money(_u32(b, m), _u32(b, m + 4), _i32(b, m + 8)),
        food=FoodStore(_i32(b, f), _i32(b, f + 4), _i32(b, f + 8), tuple(b[f + 12:f + 16])),
        stats=GameStats(struct.unpack_from("<13i", b, g)),
        pending_baby_slots=struct.unpack_from("<3i", b, p),
        nickname=_cstr(b[gs_to_file(GS_NICKNAME):gs_to_file(GS_NICKNAME) + 20]),
        save_version=_i32(b, gs_to_file(GS_SAVE_VERSION)),
        speed_option=_i32(b, gs_to_file(GS_SPEED_OPTION)),
    )


# --- the settings file (slot 0) -----------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """theGameState+0x25B20..+0x25BB0 (InitGameInfo, theChangePlayerDlg, LoadCurrentGame)."""
    header: Header
    current_slot: int             # +0x00 gs+0x25B20: the slot LoadCurrentGame loads (1..5, 0 none)
    unconfirmed_04: int           # +0x04 gs+0x25B24
    unconfirmed_08: int           # +0x08 byte gs+0x25B28
    fullscreen: bool              # +0x09 gs+0x25B29 (FullScreen / ForceFullScreen / ForceWindowed)
    player_names: tuple           # +0x10 5 x char[0x15] gs+0x25B30.. (slot 1..5 nicknames)
    slot_in_use: tuple            # +0x79..+0x7D gs+0x25B99.. (LoadCurrentGame / delete player)
    version: int                  # +0x80 gs+0x25BA0 (1001)
    unconfirmed_84: int           # +0x84 byte gs+0x25BA4
    first_run_time: int           # +0x88 gs+0x25BA8 (_time64 low dword at InitGameInfo)
    unconfirmed_8c: int           # +0x8C gs+0x25BAC


def parse_settings(data: bytes) -> Settings:
    header = parse_header(data)
    if header.legacy or header.payload_size != SETTINGS_DATA_SIZE:
        raise SaveFormatError("not a settings file (slot 0)")
    o = HEADER_SIZE
    return Settings(
        header=header,
        current_slot=_i32(data, o),
        unconfirmed_04=_i32(data, o + 4),
        unconfirmed_08=data[o + 8],
        fullscreen=data[o + 9] != 0,
        player_names=tuple(_cstr(data[o + 0x10 + i * 0x15:o + 0x10 + (i + 1) * 0x15]) for i in range(5)),
        slot_in_use=tuple(data[o + 0x79 + i] != 0 for i in range(5)),
        version=_i32(data, o + 0x80),
        unconfirmed_84=data[o + 0x84],
        first_run_time=_u32(data, o + 0x88),
        unconfirmed_8c=_u32(data, o + 0x8C),
    )


# --- which file is which (ldwGameState::MakeGameStatePath / MakePath / Save) ----------------------

def save_file_name(slot: int) -> str:
    """MakeGameStatePath: "%s%d.ldw" with GetGameName() = "Virtual Families 2"."""
    return f"{GAME_NAME}{slot}.ldw"


def save_folder_name(exe_file_name: str) -> str:
    """MakePath: Documents\\LDW\\<the exe's file name up to its FIRST '.'>."""
    return exe_file_name.split(".", 1)[0]


def children_sidecar_name(slot: int) -> str:
    """The Up to 28 Children DLL's sidecar: <save folder>\\Virtual Families 2 Patcher Data\\Children\\<save file>.dat."""
    return save_file_name(slot) + ".dat"


_GAME_FILE = re.compile(r"^virtual families 2(\d+)\.ldw$", re.I)


def classify_save_file(name: str) -> tuple[str, int] | None:
    """What the game itself uses a file name for, or None when the game never writes that name.

    ("settings", 0), ("family", 1..5), ("previous", 1..5) for slot N + 20. Windows file names are
    case-insensitive, so the match is too. A copy the player made ("... - Copy.ldw", "Families221.ldw")
    is not a name the game reads or writes.
    """
    m = _GAME_FILE.match(name)
    if not m or (len(m.group(1)) > 1 and m.group(1).startswith("0")):
        return None
    n = int(m.group(1))
    if n == 0:
        return ("settings", 0)
    if n in FAMILY_SLOTS:
        return ("family", n)
    if n - PREVIOUS_SAVE_OFFSET in FAMILY_SLOTS:
        return ("previous", n - PREVIOUS_SAVE_OFFSET)
    return None


def read_family_save(path: str | Path) -> FamilySave:
    return parse_family_save(Path(path).read_bytes())


def read_settings(path: str | Path) -> Settings:
    return parse_settings(Path(path).read_bytes())
