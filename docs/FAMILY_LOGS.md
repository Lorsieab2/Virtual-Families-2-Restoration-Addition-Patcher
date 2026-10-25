# Family Logs (from save comparisons): what is written, where, and how each event is seen

The Virtual Families 1 patcher's Family Logs (VF1 `docs/FAMILY_LOGS.md`, `native/vf1logs/vf1logs.cpp`), in the same
files and line formats, for Virtual Families 2. **No game code is hooked or patched**: `src/vf2_family_logs.py`
reads the slot's save with the read-only `src/vf2_save_reader.py`, compares it with the snapshot it kept of the
save it last logged, and appends what changed. Only fields `docs/vf2-save-format.md` marks VERIFIED drive a line.

## Files (per save slot N, beside the save)

    <save folder>\Virtual Families 2 Patcher\Save <N>\Logs\
        Family History\Family History <k>.txt                          every event, one line
        Births and Conceptions\Virtual Families 2 Births and Conceptions Log <k>.txt
        Deaths\Virtual Families 2 Deaths Log <k>.txt
        Events\Virtual Families 2 Events Log <k>.txt                   Evict Family
        Family Population\Family Population - Save <N>.txt             rewritten at every update
        Family Statistics\Family Statistics - Save <N>.txt             rewritten at every update
    <save folder>\Virtual Families 2 Patcher\Save <N>\Data\
        Unaccounted Villagers\Virtual Families 2 Family Members at Last Save - Save <N>.dat   the snapshot
        Log Checks\Virtual Families 2 Backfill - Save <N>.dat                              the backfill marker

Those two data files are all the logs keep: the snapshot (`VF2LOGS MEMBERS 1`: the save's real time and game
clock, the Family Tree, every household member, the deaths counted and the generations the 30-record tree has
dropped) and the once-only backfill marker (`VF2LOGS BACKFILL 1`). Both are text, written atomically.

Every log opens with `Family: <name> (Save <N>)`. VF2 has no family-name field, so `<name>` is the save's player
nickname (gs+0x25ABC, VERIFIED), else the slot's player name in the settings file, else `(no name)`. Records are
numbered per slot across files (`Conception <n>`, `Birth <n>`, `Death <n>`, `Event <n>`); a file rolls to the next
number after 256 records (the Family History after 2,000 lines). Text is the game's cp1252, lines end CRLF.

## Dates

Each line is stamped `[YYYY-MM-DD HH:MM:SS, game time Y years] `: the real time the save was written (header start
time + GetSecondsFromGameStart at the save) and its game clock (CGameTime::Seconds, 12,000 game seconds a year).
**An event is dated by the save it first appears in**; something that starts and ends between two saves (a baby
conceived and born, a member who joins and leaves) cannot be seen. The game keeps the save before the last one
(`Virtual Families 2<N+20>.ldw`); when it is newer than the snapshot it is compared first, so a change one save back
is still dated by its own save.

## How each event is seen

| Line | Seen when (snapshot -> newer save) |
|---|---|
| Conception | a member's pregnancy field becomes nonzero; `Babies expected` is its baby count. The father is not in the save (the game passes the literal "Joey"), so `Father: not recorded in the save` |
| Birth (Single birth / Twins / Triplets) | a pending-baby slot (gs+0x25AB0) is now in the family; the mother is the child's recorded mother |
| Joined | a new member who was not a pending baby and is not the generation's new parent: `joined the family as a child` (in the tree's children) or `(not in the Family Tree)`; the recorded mother is added when the save has one. Adoption, Little Visitor and a birth not seen pending all look alike, so the reason is not given |
| Marriage | the generation's second parent appears |
| Generation | a new tree record: `Generation 1 began: ... was adopted and started the family`, else `New Generation: generation g began: ... inherited the house`. Numbering continues past the 30-record window (MakeRoomInTree) |
| Left home | the left-home flag is set, with the game time the save records; the reason (college, Boarding School, Talent Scout) is not in the save |
| Death | health 0 in the save (`Age at death`), or the tree's slot of a member turning -1 (ReportDeath; `Age when last seen`). The cause number's meaning is UNCONFIRMED, so every death says `cause not recorded` (the Deaths record also prints the number). Logged once per member |
| Gone | a member no longer in the save with no death the tree records: `is no longer in the family; the save does not say why` |
| Evict Family | the tree's eviction flag is set (Events log); the next founder is `Generation 1 began after the eviction` |
| Older save | the save's real time is earlier than the snapshot's (a restored backup or copy): one line says so and logging continues from it |

## First run, Start Over, a new family

- **First run on an existing family**: the logs are created and the Family Tree is written once as
  `[backfilled, no date] ...` (VF1's lines, plus members away or dead in the save), then the marker. Never twice: a
  marker, or a Family History that already has lines, stops it.
- **Start Over, a new player, other founders** (the tree's first parents differ; a rename keeps the gender, head and
  body, so it is not a new family): the slot's `Logs` and `Data` move to `Save <N>\Backups\Logs before new family
  <date>` (nothing is deleted; an existing `Backups` folder is kept) and fresh logs begin.

## When it runs

When the Tools tab opens (quietly; the status line reports) and from **Update Family Logs**, for the stock
`Virtual Families 2` save folder and every `Virtual Families 2 - Modded ...` folder (copies the player made are left
alone). A folder whose game is running is refused: the game saves only when it quits. Save files are only read.
A one-slot restore (Restore Saves) restores that slot's `Virtual Families 2 Patcher\Save <N>` too.

Not yet: Family Logs in a Check/Repair tool.
