"""Game Mechanics (the Tools tab's window, src/vf2_game_mechanics_window.py): Virtual Families 2's hidden rules.

For the curious, and read-only: every line is a rule of the game as the B200 core executable runs it, in plain
words and real time, grouped as GROUPS.  Nothing here reads or writes a save, an install, a log or a data file.

Where each line comes from (docs/game-mechanics/spec.md, the research spec of the B200 core executable
`Virtual Families 2 - B200.exe`, sha256 5cad4050..., in which every patcher option byte is 0):
    VERIFIED_E   "VERIFIED-E": the game's own routine was run as linked (emulated) with the game's inputs and
                 every outcome counted over the game's own rand().
    VERIFIED_C   "VERIFIED-C": read from the game's own code on a call path traced from the running game.
    UNCONFIRMED  anything else (a purchase or other player-input path not traced, a meaning the code does not
                 show).  Never inferred: such a line says so in capitals beside it.
Each Fact keeps its evidence (spec section and addresses) for scripts/export_game_mechanics_claims.py; the
window shows the label, never the addresses.

Corrections made while building the window (2026-10-25, each run as linked on the B200 core exe; the spec rows
were corrected in place):
  * Time away: up to 31,000 s is credited in full, 31,000 s to 24 h credits 31,000 s, more than 24 h credits
    24 h (AllVillagersTimeflowUpkeep 0x4C4D29..0x4C4D8F; tests/test_game_mechanics_b200_exe.py).
  * A paused clock stops: SetSpeed(999) 0x468B80 stores speed 0; Seconds() 0x468B00 returns the banked value.
  * The owner's four questions: the fifth food-group slot (true, but it follows the Grains slot, not any group),
    interest pays at most 2 missed days and a second Brokerage purchase sets 1% (true), malfunctions roll while
    paused (true), the Flea Market changes every 6 real hours (true only for the unpatched game: with the patcher
    the expanded Flea Market lists all 36 goods and the stock rotation is never reached; both are shown).

The unpatched game (2026-10-25): every routine the page rests on was diffed between the stock executable
`Virtual Families 2.exe` (sha256 1582d9e8..., the patcher's vanilla payload) and the B200 core, and the patcher's
always-on changes that touch them were listed.  Two differ, and each is shown both ways, a "With the patcher:"
line and an "Unpatched game:" line, each with its own label and evidence (WITH_PATCHER / UNPATCHED below;
docs/game-mechanics/spec.md section 22; tests/test_game_mechanics_stock_exe.py):
  * the Flea Market: the stock rotation 0x4BA710 shows 5 of the 36 goods and re-picks them after 6 real hours;
  * the Special Upgrades page: the stock list 0x556E3C has 6 items, without the Brokerage Account, Food Club,
    Health Plan and Lucky Rock that the patcher's always-on Special Upgrades rows add.
Everything else on the page is the same in the stock executable, and adds nothing.

Wording: family members, never the code's own word for them.  A patcher option (0 in the core executable) is
shown as an option, both ways where the spec gives both.  The window describes the game; it fixes nothing.
"""
from __future__ import annotations

from dataclasses import dataclass

TITLE = "Game Mechanics"

VERIFIED_E = "VERIFIED-E"
VERIFIED_C = "VERIFIED-C"
UNCONFIRMED = "UNCONFIRMED"
LABELS = (VERIFIED_E, VERIFIED_C, UNCONFIRMED)

INTRO = ("For the curious: Virtual Families 2's hidden rules, as the game's own code runs them. Every time is a "
         "real time at the game's normal speed. It only reads: nothing is changed, so the game may be running. "
         "The page describes the game with the patcher applied, and gives the unpatched game's behaviour "
         "wherever it differs.")
WITH_PATCHER = "With the patcher: "
UNPATCHED = "Unpatched game: "
LABEL_NOTE = ("VERIFIED-E: the game's own code was run with the game's own inputs and every outcome counted. "
              "VERIFIED-C: read from the game's own code on a path the running game takes. "
              "UNCONFIRMED: not yet shown either way.")

TIME = "Time and ageing"
NEEDS = "Needs and upkeep"
HEALTH = "Health and sickness"
OLD_AGE = "Old age"
PREGNANCY = "Pregnancy and babies"
CAREERS_GROUP = "Careers"
MONEY = "Money and interest"
LEAVING = "Leaving home"
DATING = "Dating, marriage and the next generation"
EVENTS = "Random Events"
WEATHER = "Weather"
MESSES = "Messes and malfunctions"
COLLECTIBLES = "Collectibles"
STORE = "Flea Market and On Sale"
INDEX = "Chance and timer index"
GROUPS = (TIME, NEEDS, HEALTH, OLD_AGE, PREGNANCY, CAREERS_GROUP, MONEY, LEAVING, DATING, EVENTS, WEATHER, MESSES,
          COLLECTIBLES, STORE, INDEX)

BULLET, SUB_BULLET = "• ", "    – "

# The patcher options the window names (their names as the Patches tab shows them).
OPTION_MORTALITY = "Older Villager Mortality Curve"
OPTION_PREGNANCIES = "Allow Older Pregnancies"
OPTION_NAMES = (OPTION_MORTALITY, OPTION_PREGNANCIES)


@dataclass(frozen=True)
class Fact:
    """One line of the page: its group, its words, its label (LABELS) and where it comes from."""
    group: str
    text: str
    label: str
    evidence: str = ""
    sub: bool = False


E, C, U = VERIFIED_E, VERIFIED_C, UNCONFIRMED


def _f(group, text, label, evidence="", sub=False) -> Fact:
    return Fact(group, text, label, evidence, sub)


# 132 careers (docs/game-mechanics/careers.tsv, from the career table the game's CVillagerSkills::Reset 0x4CB410
# reads): (id, workplace, name, salary at each of the 8 levels).  Workplace 1 kitchen, 2 office, 3 workshop.
CAREERS = (
    (0, 1, 'Pastry Designer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (1, 1, 'Wine Critic', (20, 25, 30, 38, 48, 60, 75, 95)),
    (2, 1, 'BBQ Sauce Creator', (5, 10, 18, 36, 58, 90, 150, 230)),
    (3, 1, 'Food Critic', (22, 25, 32, 38, 48, 60, 75, 95)),
    (4, 1, 'Cocktail Inventor', (14, 18, 22, 30, 35, 42, 80, 110)),
    (5, 1, 'Soup Taster', (15, 18, 22, 27, 33, 40, 50, 70)),
    (6, 1, 'Caterer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (7, 1, 'Cake Designer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (8, 1, 'Mustard Bottler', (20, 25, 30, 38, 48, 60, 75, 95)),
    (9, 1, 'Coffee Blender', (20, 25, 30, 38, 48, 60, 75, 95)),
    (10, 1, 'Personal Cook', (35, 45, 58, 68, 80, 94, 115, 140)),
    (11, 1, 'Fresh Pasta Maker', (20, 25, 30, 38, 48, 60, 75, 95)),
    (12, 1, 'Doughnut Decorator', (20, 25, 30, 38, 48, 60, 75, 95)),
    (13, 1, 'Candy Designer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (14, 1, 'Food Photographer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (15, 1, 'Fruit Examiner', (20, 25, 30, 38, 48, 60, 75, 95)),
    (16, 1, 'Salad Packager', (15, 18, 22, 27, 33, 40, 50, 70)),
    (17, 1, 'Meat Grader', (30, 35, 43, 48, 56, 65, 78, 100)),
    (18, 1, 'Mail-order Butcher', (20, 25, 30, 38, 48, 60, 75, 95)),
    (19, 1, 'Nut Processor', (15, 18, 22, 27, 33, 40, 50, 70)),
    (20, 1, 'Dry Fruit Packager', (20, 25, 30, 38, 48, 60, 75, 95)),
    (21, 1, 'Mail-order Baker', (20, 25, 30, 38, 48, 60, 75, 95)),
    (22, 1, 'Soup Inventor', (20, 25, 30, 38, 48, 60, 75, 95)),
    (23, 1, 'Recipe Inventor', (5, 10, 18, 36, 58, 90, 150, 230)),
    (24, 1, 'Vitamin Inventor', (5, 10, 18, 36, 58, 90, 150, 230)),
    (25, 1, 'Pesto Sauce Creator', (5, 10, 18, 36, 58, 90, 150, 230)),
    (26, 1, 'Ketchup Bottler', (15, 18, 22, 27, 33, 40, 50, 70)),
    (27, 1, 'Trail Mix Creator', (20, 25, 30, 38, 48, 60, 75, 95)),
    (28, 1, 'Chewing Gum Designer', (5, 10, 18, 36, 58, 90, 150, 230)),
    (29, 1, 'Food Sculptor', (20, 25, 30, 38, 48, 60, 75, 95)),
    (30, 1, 'Truffle Critic', (35, 45, 58, 68, 80, 94, 115, 140)),
    (31, 1, 'Fish Cleaner', (15, 18, 22, 27, 33, 40, 50, 70)),
    (32, 1, 'Pickler', (20, 25, 30, 38, 48, 60, 75, 95)),
    (33, 1, 'Coffee Critic', (20, 25, 30, 38, 48, 60, 75, 95)),
    (34, 1, 'Cupcake Designer', (5, 10, 18, 36, 58, 90, 150, 230)),
    (35, 1, 'Sauce Designer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (36, 1, 'Jerky Maker', (20, 25, 30, 38, 48, 60, 75, 95)),
    (37, 1, 'Spice Mixer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (38, 2, 'Engineer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (39, 2, 'Architect', (30, 35, 43, 48, 56, 65, 78, 100)),
    (40, 2, 'Domain Name Seller', (15, 20, 25, 32, 40, 55, 70, 90)),
    (41, 2, 'Video Game Designer', (5, 10, 18, 36, 58, 90, 150, 230)),
    (42, 2, 'Tech Consultant', (15, 20, 25, 32, 40, 55, 70, 90)),
    (43, 2, 'Hacker', (15, 20, 25, 32, 40, 55, 70, 90)),
    (44, 2, 'Fiction Writer', (20, 25, 30, 38, 48, 60, 75, 130)),
    (45, 2, 'Journalist', (15, 20, 25, 32, 40, 55, 70, 90)),
    (46, 2, 'Lawyer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (47, 2, 'Screenplay Writer', (12, 18, 22, 27, 53, 80, 150, 170)),
    (48, 2, 'Envelope Stuffer', (15, 18, 22, 27, 33, 40, 50, 70)),
    (49, 2, 'Graphic Designer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (50, 2, 'Day Trader', (35, 20, 28, 55, 40, 32, 170, 80)),
    (51, 2, 'Poet', (15, 18, 22, 27, 33, 40, 120, 170)),
    (52, 2, 'Lyricist', (15, 20, 25, 32, 40, 55, 70, 90)),
    (53, 2, 'Programmer', (35, 45, 58, 68, 80, 94, 115, 140)),
    (54, 2, 'Accountant', (20, 25, 30, 38, 48, 60, 75, 95)),
    (55, 2, 'Publicist', (15, 20, 25, 32, 40, 55, 70, 90)),
    (56, 2, 'Nonfiction Writer', (12, 15, 19, 24, 29, 55, 75, 130)),
    (57, 2, 'Fairy Tale Writer', (20, 25, 30, 38, 48, 60, 75, 95)),
    (58, 2, 'Translator', (30, 35, 43, 48, 56, 65, 78, 100)),
    (59, 2, 'QA Engineer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (60, 2, 'Telemarketer', (18, 22, 25, 32, 40, 55, 70, 80)),
    (61, 2, 'Talent Agent', (5, 10, 18, 36, 58, 90, 150, 230)),
    (62, 2, 'Recruiter', (30, 35, 43, 48, 56, 65, 78, 100)),
    (63, 2, 'Video Game Reviewer', (20, 25, 30, 38, 48, 60, 75, 95)),
    (64, 2, 'Essay Writer', (15, 18, 22, 27, 33, 40, 50, 70)),
    (65, 2, 'Web Designer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (66, 2, 'Art Critic', (20, 25, 30, 38, 48, 60, 75, 95)),
    (67, 2, 'Music Critic', (20, 25, 30, 38, 48, 60, 75, 95)),
    (68, 2, 'Book Reviewer', (20, 25, 30, 38, 48, 60, 75, 95)),
    (69, 2, 'Online Gold Farmer', (15, 18, 22, 27, 33, 40, 50, 70)),
    (70, 2, 'Marketing Agent', (30, 35, 43, 48, 56, 65, 78, 100)),
    (71, 2, 'Paralegal', (20, 25, 30, 38, 48, 60, 75, 95)),
    (72, 2, 'Census Taker', (15, 18, 22, 27, 33, 40, 50, 70)),
    (73, 2, 'Digital Photo Editor', (20, 25, 30, 38, 48, 60, 75, 95)),
    (74, 2, 'Magazine Editor', (20, 25, 30, 38, 48, 60, 75, 95)),
    (75, 2, 'Rocket Scientist', (30, 35, 43, 48, 56, 65, 78, 100)),
    (76, 2, 'Lobbyist', (35, 45, 58, 68, 80, 94, 115, 140)),
    (77, 2, 'Math Tutor', (15, 18, 22, 27, 33, 40, 50, 70)),
    (78, 2, 'History Tutor', (15, 18, 22, 27, 33, 40, 50, 70)),
    (79, 2, 'English Tutor', (15, 18, 22, 27, 33, 40, 50, 70)),
    (80, 2, 'Statistician', (20, 25, 30, 38, 48, 60, 75, 95)),
    (81, 2, 'Online Store Operator', (5, 10, 18, 36, 58, 90, 150, 230)),
    (82, 2, 'Travel Agent', (20, 25, 30, 38, 48, 60, 75, 95)),
    (83, 2, 'Technical Writer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (84, 2, 'Sustainability Consultant', (30, 35, 43, 48, 56, 65, 78, 100)),
    (85, 2, 'Artist', (20, 25, 30, 38, 48, 60, 75, 95)),
    (86, 2, 'Online Security', (35, 45, 58, 68, 80, 94, 115, 140)),
    (87, 2, 'Video Editor', (20, 25, 30, 38, 48, 60, 75, 95)),
    (88, 2, 'Toy Collector', (30, 35, 43, 48, 56, 65, 78, 100)),
    (89, 2, 'Comic Collector', (5, 10, 18, 36, 58, 90, 150, 230)),
    (90, 2, 'Online Poker Pro', (25, 20, 28, 55, 40, 32, 170, 80)),
    (91, 2, 'Composer', (20, 25, 30, 38, 48, 60, 75, 95)),
    (92, 2, 'Blogger', (20, 25, 30, 38, 48, 60, 75, 95)),
    (93, 2, 'Film Critic', (15, 18, 22, 27, 33, 40, 50, 70)),
    (94, 2, 'Spammer', (20, 25, 30, 38, 48, 60, 75, 95)),
    (95, 3, 'Wood Sculptor', (20, 25, 30, 38, 48, 60, 75, 130)),
    (96, 3, 'Dress Maker', (20, 25, 30, 38, 48, 60, 75, 95)),
    (97, 3, 'Toaster Repairer', (15, 18, 22, 27, 33, 40, 50, 70)),
    (98, 3, 'Dress Designer', (35, 45, 58, 68, 80, 94, 115, 140)),
    (99, 3, 'Candle Maker', (30, 35, 43, 48, 56, 65, 78, 100)),
    (100, 3, 'Jewelry Maker', (5, 10, 18, 36, 58, 90, 150, 230)),
    (101, 3, 'Film Processor', (15, 18, 22, 27, 33, 40, 50, 70)),
    (102, 3, 'Inventor', (15, 20, 25, 32, 40, 55, 70, 90)),
    (103, 3, 'Board Game Designer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (104, 3, 'Model Builder', (20, 25, 30, 38, 48, 60, 75, 95)),
    (105, 3, 'Basket Maker', (15, 20, 25, 32, 40, 55, 70, 90)),
    (106, 3, 'Knife Sharpener', (15, 18, 22, 27, 33, 40, 50, 70)),
    (107, 3, 'Glue Mixer', (15, 18, 22, 27, 33, 40, 50, 70)),
    (108, 3, 'Silverware Polisher', (20, 25, 30, 38, 48, 60, 75, 95)),
    (109, 3, 'Tool Maker', (20, 25, 30, 38, 48, 60, 75, 95)),
    (110, 3, 'Toy Maker', (20, 25, 30, 38, 48, 60, 75, 95)),
    (111, 3, 'Box Maker', (15, 18, 22, 27, 33, 40, 50, 70)),
    (112, 3, 'Shoe Maker', (5, 10, 18, 36, 58, 90, 150, 230)),
    (113, 3, 'Dental Tool Maker', (35, 45, 58, 68, 80, 94, 115, 140)),
    (114, 3, 'Lens Crafter', (30, 35, 43, 48, 56, 65, 78, 100)),
    (115, 3, 'Key Maker', (15, 18, 22, 27, 33, 40, 50, 70)),
    (116, 3, 'Picture Framer', (20, 25, 30, 38, 48, 60, 75, 95)),
    (117, 3, 'Soap Inventor', (5, 10, 18, 36, 58, 90, 150, 230)),
    (118, 3, 'Eyeglass Repairer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (119, 3, 'Ceramics Designer', (20, 25, 30, 38, 48, 60, 75, 95)),
    (120, 3, 'Denture Maker', (20, 25, 30, 38, 48, 60, 75, 95)),
    (121, 3, 'Camera Repairer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (122, 3, 'Watch Fixer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (123, 3, 'Puzzle Maker', (20, 25, 30, 38, 48, 60, 75, 95)),
    (124, 3, 'Chair Maker', (20, 25, 30, 38, 48, 60, 75, 95)),
    (125, 3, 'Shoe Repairer', (15, 18, 22, 27, 33, 40, 50, 70)),
    (126, 3, 'Toy Refurbisher', (20, 25, 30, 38, 48, 60, 75, 95)),
    (127, 3, 'Jewelry Cleaner', (20, 25, 30, 38, 48, 60, 75, 95)),
    (128, 3, 'Jewelry Smelter', (35, 45, 58, 68, 80, 94, 115, 140)),
    (129, 3, 'Cosmetics Designer', (5, 10, 18, 36, 58, 90, 150, 230)),
    (130, 3, 'Phone Repairer', (30, 35, 43, 48, 56, 65, 78, 100)),
    (131, 3, 'Pen Designer', (5, 10, 18, 36, 58, 90, 150, 230)),
)
WORKPLACES = {1: "kitchen", 2: "office", 3: "workshop"}
LEVELS = ("Beginner", "Novice", "Apprentice", "Licensed", "Practiced", "Accomplished", "Exceptional", "Master")


def _per_hour(salary: int) -> str:
    """A career's pay per real hour: salary / 4 every 30 real minutes (spec section 2, 0x4C452E)."""
    pay = salary / 2
    return f"${pay:g}"


def _career_lines() -> list[Fact]:
    lines = []
    for workplace in (1, 2, 3):
        rows = [c for c in CAREERS if c[1] == workplace]
        lines.append(_f(CAREERS_GROUP, f"Works in the {WORKPLACES[workplace]} ({len(rows)} careers):", C,
                        "careers.tsv; CVillagerSkills::Reset 0x4CB410", sub=True))
        for _cid, _wp, name, salaries in rows:
            lines.append(_f(CAREERS_GROUP, (
                f"{name}: {_per_hour(salaries[0])} per real hour as a Beginner, "
                f"{_per_hour(salaries[7])} as a Master (levels: "
                + ", ".join(_per_hour(s).lstrip("$") for s in salaries) + ")."), C,
                "careers.tsv", sub=True))
    return lines


def facts() -> list[Fact]:
    """Every line of the page, in GROUPS order."""
    out: list[Fact] = []
    add = out.append

    # ------------------------------------------------------------------ Time and ageing (spec section 1, 5)
    add(_f(TIME, "The game clock: at the game's normal speed one game second is one real second. The game itself "
                 "only ever sets the normal speed or Pause.", C,
           "spec 1: speed option gs+0x25B18, every writer listed"))
    add(_f(TIME, "Pause stops the game clock completely: the clock keeps the time it had when paused, however long "
                 "the pause lasts, and carries on from there when unpaused.", E,
           "SetSpeed(999) 0x468B80 stores speed 0 and banks Seconds(); Seconds() 0x468B00 returns the banked "
           "value at any later real time (tests/test_game_mechanics_b200_exe.py)"))
    add(_f(TIME, "While paused nobody ages and none of the family's upkeep (hunger, health, salary, birthdays) is "
                 "processed, and the paused time is never made up later. Food groups, symptoms, the baby waiting "
                 "time and collectibles keep counting down in real time while paused.", C,
           "spec 1: option >= 999 zeroes the accumulator every step (0x4C4D99)"))
    add(_f(TIME, "Ageing: a family member gains one age unit every 10 real minutes; 20 units make a year, so a "
                 "year takes 3 hours 20 minutes of real time. Ageing counts real time, so it carries on while the "
                 "game is closed (see time away).", C, "spec 1: AllVillagersTimeflowUpkeep 0x4C4C30"))
    add(_f(TIME, "Time away (the game closed, not paused) is made up the next time the game runs:", E,
           "AllVillagersTimeflowUpkeep 0x4C4D29..0x4C4D8F run as linked: 30,000 / 50,000 / 86,400 / 200,000 s "
           "away credit 30,000 / 31,000 / 31,000 / 86,400 s"))
    add(_f(TIME, "up to 31,000 seconds (8 hours 36 minutes 40 seconds) away is made up in full;", E, sub=True))
    add(_f(TIME, "from 31,000 seconds up to and including 24 hours away, 31,000 seconds are made up: 51 age units, "
                 "about 2.55 years;", E, sub=True))
    add(_f(TIME, "more than 24 hours away, exactly 24 hours are made up: 144 age units, 7.2 years. The rest of the "
                 "time away is lost.", E, sub=True))
    add(_f(TIME, "A family saved paused makes up nothing.", E, "option 1009: accumulator 0 (emulated)", sub=True))
    add(_f(TIME, "Every age unit made up is then lived one by one, with its meals, health, salary and birthdays, as "
                 "if the game had been open.", E,
           "spec 2: AllVillagersRealtimePhysiologyAndProductivityUpkeep 0x4C4410 repeats until nobody is behind"))
    add(_f(TIME, "Day and night follow your PC's own clock.", C, "spec 1: CNight::GetTimeOfDay 0x482A30"))
    add(_f(TIME, "Ages: a baby until 5 years (the diaper events), a child until 14, then a teen or adult; a "
                 "partner for a baby from 18 until 55; old from 55.", C, "spec 5"))
    add(_f(TIME, "There is no maximum age in the code: old age (below) ends every life by 65 years plus the food "
                 f"groups counted, unless the \"{OPTION_MORTALITY}\" option is on.", E, "spec 4, 5"))
    add(_f(TIME, "A new baby is created at 2 years of age (40 age units).", U,
           "spec 5 text: Impregnate passes 0x28; not labelled there"))
    add(_f(TIME, "The store's time-skip item ages the family by up to 61 age units (10 hours 10 minutes) at once "
                 "and caps the money it brings at $750.", U, "spec 1: purchase path not traced"))

    # ------------------------------------------------------------------ Needs and upkeep (spec 2, 14)
    add(_f(NEEDS, "The family's needs are worked out once per age unit, every 10 real minutes, for everyone alive "
                  "and at home.", E, "spec 2"))
    add(_f(NEEDS, "Hunger rises by 5 every 40 real minutes.", E, "spec 2: UpdateHungerState 0x4CC6A0"))
    add(_f(NEEDS, "Eating: every 10 minutes, a hungry family member (hunger over 50) eats 3 food and loses 3 hunger "
                  "when the house has food; with 50 food or less in the house a meal is missed half the time.", E,
           "spec 2: 0x4C4575"))
    add(_f(NEEDS, "A missed meal or an empty house: a 30% chance (30.03%) of losing 1 health (starvation).", E,
           "spec 2"))
    add(_f(NEEDS, "No food at all: 1 health lost (76% chance, sure every hour); at 20 health or less a 31% chance "
                  "of 1 back every other unit.", E, "spec 2: 0x4C463C"))
    add(_f(NEEDS, "Waste: with 1,000 food or more, a hungry family member has a 76% chance of using 3 more food.",
           E, "spec 2: 0x4C460F"))
    add(_f(NEEDS, "The toilet: when the need reaches 90 it resets to 25-49.", E, "spec 2: 0x4C455A"))
    add(_f(NEEDS, "Energy changes every 20 real minutes: -4 at night (8 PM to 5 AM by your PC's clock) with 10 or "
                  "more energy, +8 in the day (5:06 AM to 5 PM) with 70 or less; -1 each for happiness 10 or less, "
                  "health 25 or less, health 10 or less and hunger 90 or more; -3 when sick (at most -6 or +10).", C,
           "spec 2: UpdateEnergyState 0x4CBDC0"))
    add(_f(NEEDS, "Energy is only worked out for the last 12 units of a catch-up.", E, "spec 2: 0x4C450F"))
    add(_f(NEEDS, "Happiness moves every 30 real minutes by up to 5 points, towards a mood made of: food groups, "
                  "money (worse below $1,000 and $100, better above $8,000, $50,000 and $100,000), food in the "
                  "house (worse at 250 and 50 or less), sickness, messes on the floor (better with none, worse at 10 "
                  "and 20), house renovations, placed furniture (up to 30), owned items the person likes, the "
                  "family's size, hunger 90 or more and health 10 or less.", C,
           "spec 2: UpdateHappinessState 0x4CBE90"))
    add(_f(NEEDS, "Food groups: Grains, Dairy, Meats and Fruits and Veggies. A grocery bag put in the kitchen, or a "
                  "Food Club delivery, gives that group to everyone at home for 24 real hours.", C,
           "spec 2, 14: UpdateNutritionAllVillagers 0x4C74E0; groups by item: 0x49F998.."))
    add(_f(NEEDS, "Family members without a career (every child born in the house starts without one) count one "
                  "extra food group whenever they have had Grains, even after the Grains has run out: Grains and "
                  "Dairy count as 3 groups, all four as 5, Dairy alone as 1, and an old Grains with nothing else as "
                  "1. (Once in 256 times a Grains bag gives no extra.) The count is used for old age, catching "
                  "an illness and the health and happiness checks.", E,
           "FoodGroupsActive 0x4CB870 counts 5 slots; the fifth reads the Grains expiry's low byte as its flag and "
           "the career id (record +0x140) as its expiry; emulated (tests/test_game_mechanics_b200_exe.py); callers "
           "0x4B8548 (old age), 0x4CBD29 (illness), 0x4CC616 (health), 0x4CBF00 (happiness)"))
    add(_f(NEEDS, "The food store never goes below 0.", C, "spec 14"))

    # ------------------------------------------------------------------ Health and sickness (spec 2, 3, 4)
    add(_f(HEALTH, "Recovery: every 10 minutes, a fed family member who is not sick has a 50% chance of 1 health "
                   "back (10% from age 55), up to 100.", E, "spec 2: 0x4C470A"))
    add(_f(HEALTH, "Every 30 minutes health also moves by up to 5: -1 for happiness 10 or less, -1 for hunger 90 or "
                   "more and another at 100, -1 with exactly 1 food group, +1 with exactly 4, and when sick -1 with "
                   "a 15% chance (40% with an infection).", C, "spec 2: UpdateHealthState 0x4CC5F0"))
    add(_f(HEALTH, "Being sick: every 10 minutes a 61% chance of losing 1 health; no recovery, less energy and "
                   "happiness, and less career progress.", E, "spec 2: 0x4C46D0; spec 3"))
    add(_f(HEALTH, "Catching something: every 30 real minutes a healthy family member is checked:", E,
           "spec 3: UpdateDisease 0x4CBBE0 (t_dis)"))
    add(_f(HEALTH, "1.007% in all (a symptom 0.906%, a mild infection 0.071%, a serious one 0.030%);", E, sub=True))
    add(_f(HEALTH, "2.518% when someone at home has a catching symptom;", E, sub=True))
    add(_f(HEALTH, "0.806% with exactly 3 food groups counted, and 0.503% with 5 (a family member without a career "
                   "who has all four).", E, "0x4CBD2E: base 10, -2 at 3 groups, -5 at 5", sub=True))
    add(_f(HEALTH, "Symptoms: hiccups, sore throat, stomach, headache, cough, skin rash and runny nose. Each lasts "
                   "6 to 17 real hours.", E, "spec 3: SetSymptom 0x4CBBA0"))
    add(_f(HEALTH, "A mild infection adds a symptom half the time when there is none and ends with a 3% chance per "
                   "check; a serious one adds symptoms (up to 2) and ends with a 1.2% chance per check.", E, "spec 3"))
    add(_f(HEALTH, "Medicines and the stethoscope.", U, "spec 3: player actions"))
    add(_f(HEALTH, "Deaths from illness (health reaching 0 while sick) and from starvation (health reaching 0 from "
                   "missed meals).", C, "spec 4"))
    add(_f(HEALTH, "Deaths by work accident or act of nature: the causes exist; what brings them is not traced.", U,
           "spec 4"))
    add(_f(HEALTH, "A family member who has died stays in the house for 40 real hours (240 age units), then is "
                   "taken from the family tree's slot.", C, "spec 4: 0x4C4C9D"))

    # ------------------------------------------------------------------ Old age (spec 4)
    add(_f(OLD_AGE, "Old age: at each birthday past 55 years plus N, the food groups counted (0 to 4, and one more "
                    "for a family member without a career who has had Grains), the chance of dying is 10% for each year "
                    "over: 10% at 56 + N, 20% at 57 + N, ... 100% at 65 + N.", E,
           "spec 4; physiology upkeep run as linked, site 0x4C47A8 (tests/test_game_mechanics_b200_exe.py)"))
    add(_f(OLD_AGE, "With no food groups: 10% at 56, 50% at 60, 100% at 65. With all four (and a career): 10% at "
                    "60, 50% at 64, 100% at 69.", E, "emulated, site 0x4C47A8"))
    add(_f(OLD_AGE, f"Patcher option \"{OPTION_MORTALITY}\", off (the game as shipped): the rule above.", E,
           ".vf2mort = 0: 0x4C4BFB jumps to the stock block"))
    add(_f(OLD_AGE, f"Patcher option \"{OPTION_MORTALITY}\", on: the same birthday check uses a curve instead. "
                    "Effective age = years minus the food groups counted (0 to 4). Chance of dying at each "
                    "birthday by effective age: 55: 0%, 60: 1.81%, 65: 3.59%, 70: 5.33%, 75: 7.04%, 80: 8.72%, "
                    "90: 11.99%, 100: 15.15%, 110: 18.19%, 115: 40.49%, 120: 56.71%, 125: 68.51%, 150: 93.59%, "
                    "200: 99.73%. No age limit.", E, "spec 4: VF2RollOlderVillagerMortality 0x4BA410"))

    # ------------------------------------------------------------------ Pregnancy and babies (spec 6)
    add(_f(PREGNANCY, "Only the married couple has babies: the wife with her husband.", C, "spec 6: ProcessCurrentPlan case 73, TryToMakeBaby, ConceiveChildWith"))
    add(_f(PREGNANCY, "Chance a try succeeds, by the mother's age and both parents' fertility F (father under 41):",
           E, "spec 6: ChanceOfPregnancy 0x4CB6C0 (t_preg)"))
    for row in ("mother 18-30: F 0 39%, F 25 55%, F 50 73%, F 75 89%, F 100 100%;",
                "mother 31: 17%, 33%, 51%, 67%, 83%;",
                "mother 35: 9%, 25%, 43%, 59%, 75%;",
                "mother 40: 0%, 15%, 33%, 49%, 65%;",
                "mother 45: 0%, 5%, 23%, 39%, 55%;",
                "mother 50: 0%, 0%, 13%, 29%, 45%;",
                "mother over 50: 0%."):
        add(_f(PREGNANCY, row, E, sub=True))
    add(_f(PREGNANCY, "In full: 105 minus a third of each parent's missing fertility (100 - F); fathers over 40 lose "
                      "(years - 40) / 5; mothers 31-50 lose 2 x (years - 20). Until the game has shown its pregnancy "
                      "tip, a try always succeeds (mother under 50).", E, "spec 6"))
    add(_f(PREGNANCY, f"Patcher option \"{OPTION_PREGNANCIES}\", off: the table above (no babies for mothers over "
                      "50).", E, "spec 6"))
    add(_f(PREGNANCY, f"Patcher option \"{OPTION_PREGNANCIES}\", on: with a parent 50 or older, a chance from 10% at "
                      "50 down to 0.1% from 69.", U, "spec 6: VF2RollOlderPregnancy, from discoveries.md"))
    add(_f(PREGNANCY, "Twins and triplets: twins 5.25%, triplets 1.75%, one baby 93%; each parent's fertility over 85 "
                      "adds its excess, in points, to both rolls. Twins need 2 free child places, triplets 3.", C,
           "spec 6: Impregnate 0x4BB920"))
    add(_f(PREGNANCY, "A family has room for 6 children per generation.", C, "spec 10: AddOffspring"))
    add(_f(PREGNANCY, "A pregnancy lasts 21 age units: 3 hours 30 minutes of real time.", C, "spec 6: 0x4C47D8"))
    add(_f(PREGNANCY, "After a birth the game sets a waiting time of 10 minutes (both parents' desire 80 or more) to "
                      "4 hours 10 minutes (desire 0) before the next try.", C, "spec 6: gs+0x25AE0 writer"))
    add(_f(PREGNANCY, "What that waiting time holds back.", U, "spec 6: reader of gs+0x25AE0 not found"))

    # ------------------------------------------------------------------ Careers (spec 7)
    add(_f(CAREERS_GROUP, "A career is picked at random from 132 (38 in the kitchen, 57 in the office, 37 in the "
                          "workshop) and starts at level 0.", C, "spec 7: CVillagerSkills::Reset 0x4CB410"))
    add(_f(CAREERS_GROUP, "Levels: " + ", ".join(LEVELS) + ".", C, "spec 7"))
    add(_f(CAREERS_GROUP, "Salary: paid every 30 real minutes, a quarter of the career's salary each time (half the "
                          "salary per real hour), whether or not the person is at work.", E, "spec 2, 7: 0x4C452E"))
    add(_f(CAREERS_GROUP, "Each piece of work succeeds with a chance of 56.25% for a Beginner rising to 100% for a "
                          "Master; a success pays 6% of the salary and adds progress (more in better-equipped rooms, "
                          "less at higher levels). 3,000 progress is a promotion: a new salary and a celebration.", C,
           "spec 7: AdvanceCareer"))
    add(_f(CAREERS_GROUP, "How often family members choose to work.", U, "spec 7: behaviour entry"))
    add(_f(CAREERS_GROUP, "During a catch-up, work done while nobody watched adds career progress (unpaid), less "
                          "when sick and none when pregnant.", U, "spec 7: RealtimeWorkDone 0x4C3DB0"))
    add(_f(CAREERS_GROUP, "Every career's pay, per real hour, at each level from Beginner to Master:", C,
           "careers.tsv"))
    out.extend(_career_lines())

    # ------------------------------------------------------------------ Money and interest (spec 8)
    add(_f(MONEY, "A new family starts with $50 to $189.", C, "spec 10: theGameState init rand(140)"))
    add(_f(MONEY, "Money never goes below $0 or above $4,000,000,000.", C, "spec 8: CMoney::Adjust 0x4818B0"))
    add(_f(MONEY, "Interest: 10% of the money (the starting rate) each game day (24 real hours at normal speed). After a gap only 2 "
                  "days are paid, however many have passed; the rest are skipped.", E,
           "UpdateInterest 0x481D80 run as linked: 1,000 at 0.10 gains 100 after 1 day and 200 after 2, 3 or 10"))
    add(_f(MONEY, "Interest is paid when it is next checked: every 30 real minutes, and when the bank or some "
                  "events look at the money.", C, "spec 8: callers of UpdateInterest"))
    add(_f(MONEY, WITH_PATCHER + "the store's Special Upgrades page also sells the Brokerage Account, the Food Club, "
                  "the Health Plan and the Lucky Rock (10 items in all).", E,
           "B200 core: GetCategoryItemCount 0x46B6D0 / GetCategoryItem 0x46B210, category 0x14, run as linked: 10 "
           "items, gServicesList 0x56F100 = 0x111..0x116 then 0x117..0x11A (the patcher's always-on Special "
           "Upgrades rows, patch_visible_special_upgrades)"))
    add(_f(MONEY, UNPATCHED + "the Special Upgrades page has 6 items and sells none of the Brokerage Account, the "
                  "Food Club, the Health Plan or the Lucky Rock.", E,
           "stock exe sha256 1582d9e8: GetCategoryItemCount 0x4BB0A0 / GetCategoryItem 0x4BAA50, category 0x14 (the "
           "store menu's Special Upgrades row, table 0x5346E0), run as linked: 6 items, list 0x556E3C = 0x111, "
           "0x112, 0x113, 0x115, 0x116, 0x114"))
    add(_f(MONEY, WITH_PATCHER + "Brokerage Account: buying it raises interest to 11% a day. Buying it again sets "
                  "interest to 1%; each purchase after that adds 2 points (3%, 5%, 7%, 9%) until 11% again.", E,
           "HandlePurchaseItem 0x48C110 -> 0x4B8B50 run as linked from 0.10: 0.11, 0.01, 0.03, 0.05, 0.07, 0.09, "
           "0.11"))
    add(_f(MONEY, "Food Club: 500 food and all four food groups each game day, every missed day delivered; and 60 "
                  "food whenever the food runs below 60. Removing it stops the deliveries.", C,
           "spec 8: JoinFoodClub, CFoodStore::Update 0x464F70"))
    add(_f(MONEY, "Food Club prices (its description promises 50% off food).", U, "spec 14: price path"))
    add(_f(MONEY, "Health Plan: medicine at a quarter of the price.", U, "spec 8: price path is player input"))
    add(_f(MONEY, "Lotto Ticket: 1 in 10,000 for $50,000; 2 in 10,000 for $25,000; 20 for $5,000; 200 for "
                  "$1,000; 500 for $750; otherwise a 50% chance of a grocery bag (when there is room in the "
                  "tray) or nothing.", U, "spec 8: purchase path"))

    # ------------------------------------------------------------------ Leaving home (spec 9)
    add(_f(LEAVING, "College: a family member without a career leaves for college on turning 19. Children born in "
                    "the house have no career, so every child not chosen as the heir leaves at 19.", C,
           "spec 9: 0x4C4DF4"))
    add(_f(LEAVING, "The Talent Scout (a Popup Event, a child at home): yes, the child leaves and the family gets "
                    "$500; no, nothing happens.", E, "spec 9: event 83"))
    add(_f(LEAVING, "Boarding School (the store): the chosen child is sent away.", U, "spec 9: purchase path"))
    add(_f(LEAVING, "The college e-mails come from those who left; they count one year away for every 12,000 "
                    "game seconds (3 hours 20 minutes).", C, "spec 9: YearsAwayFromHome"))

    # ------------------------------------------------------------------ Dating, marriage, next generation (spec 10)
    add(_f(DATING, "The dating e-mail first comes 3 minutes into a new game or a new generation. After a date "
                   "without a match it comes 5 minutes x the dates so far later, plus 10 minutes for each year the "
                   "single head of the family is over 26.", C, "spec 10: gs+0x25AE4 writers"))
    add(_f(DATING, "Each date is of the other sex and 3 years younger to 2 years older (equally likely).", C,
           "spec 10: CDatingScene::GeneratePeepCandidate 0x452D80"))
    add(_f(DATING, "Saying yes marries them: the date joins the family as the spouse.", C, "spec 10"))
    add(_f(DATING, "The first adult of a new game is 24 to 29 years old, a man or a woman equally likely.", C,
           "spec 10: CAdoptionScene::GeneratePeepCandidate 0x403660"))
    add(_f(DATING, "Next generation: when a parent dies while a child is alive, the game offers the next "
                   "generation. Choosing an heir starts it, and everyone else leaves the house.", C,
           "spec 10: ReportDeath, StartNextGeneration"))
    add(_f(DATING, "Which child may be chosen as the heir.", U, "spec 10: player input"))
    add(_f(DATING, f"Patcher option \"{OPTION_PREGNANCIES}\", on: the next generation is also offered when the "
                   "oldest family member reaches 60 with a child alive. Off: only as above.", C,
           "spec 10: VF2CanStartNextGenerationAtOlderAge"))
    add(_f(DATING, "The Little Visitor (a Popup Event, with room for a child): yes, a 3-year-old boy or girl joins "
                   "the family.", E, "spec 10: events 64 / 65"))

    # ------------------------------------------------------------------ Random Events (spec 11)
    add(_f(EVENTS, "Every hour of game time (1 real hour at normal speed; the clock stops while paused), when "
                   "someone is at home: a 66% "
                   "chance of an Email Event, otherwise a Popup Event now. Opening the e-mail starts the hour "
                   "again.", C, "spec 11: UpdateScene 0x4A2E17"))
    add(_f(EVENTS, "The event is picked evenly among those that can happen at the time, so each one's chance is 1 "
                   "in the number that can.", C, "spec 11: CIslandEvents::FireEvent 0x46F330"))
    add(_f(EVENTS, "The events of the game as shipped (the patcher's \"Add mobile-exclusive Random Events\" option adds to them, not shown "
                   "here). Money: + gain, - cost; \"yes\" and \"no\" are the two answers:", E,
           "spec 11: CalcAward and ImpactGame run as linked (t_events)"))
    for text, label in _EVENT_LINES:
        add(_f(EVENTS, text, label, "spec 11 table", sub=True))
    add(_f(EVENTS, "The money each \"money check\" event needs before it can happen.", U, "spec 11: events_dump"))

    # ------------------------------------------------------------------ Weather (spec 12)
    add(_f(WEATHER, "Kinds: normal, sunny, raining, stormy (rain and lightning), foggy and snowing.", C, "spec 12"))
    add(_f(WEATHER, "After a spell the weather always returns to normal; after normal the next kind is picked "
                    "evenly from the other five (never sunny at night). The weather stands still while paused.", C,
           "spec 12: CWeather::Update 0x4CD110"))
    add(_f(WEATHER, "Normal weather lasts 15 to 40 real minutes; any other kind 6 to 12.", C,
           "spec 12: SetCurrent 0x4CCF20"))
    add(_f(WEATHER, "Heavy rain or a storm sends everyone outside to take cover.", C, "spec 12"))
    add(_f(WEATHER, "Some collectibles only appear in rain or storms.", C, "spec 12, 15"))
    add(_f(WEATHER, "The weather when the game starts.", U, "spec 12: when CWeather::Reset runs"))

    # ------------------------------------------------------------------ Messes and malfunctions (spec 13)
    add(_f(MESSES, "Messes appear every 5 real hours of game time (2.5 hours with 4 or more in the family), not "
                   "while paused, one roll each: under 30 a weed, under 55 a sock, under 80 a candy wrapper, "
                   "else a dirt smudge; with no cobwebs about, a roll under 20 makes nothing. A Gardener stops the "
                   "weeds and a Maid the rest; with both, no messes.", C,
           "spec 13: CCollectableItem::Update 0x44DE90"))
    add(_f(MESSES, "Messes on the floor change the family's happiness (see Needs and upkeep).", C, "spec 13"))
    add(_f(MESSES, "House malfunctions: every 2 seconds a 1 in 800 chance (about every 27 real minutes), from 6 "
                   "minutes after the family was started and only while no other malfunction is out. They roll "
                   "while the game is paused too.", E,
           "UpdateScene 2-second step 0x4A266E..0x4A28F9 run as linked at speed option 10 and 1009: both reach "
           "GetRandom(800) and the pick GetRandom(14); the step's clock is the wall clock (0x474600)"))
    add(_f(MESSES, "Which one: one of 14, evenly: a router offline, a dryer lint fire (needs a dryer), leaks in the "
                   "north bathroom's shower, toilet and sink (need that renovation), ants (3 of the 14), and six "
                   "other breakdowns. A permanent fix stops its own kind; a pick the house cannot have makes "
                   "nothing.", C, "spec 13: 0x4A28F4"))
    add(_f(MESSES, "The names of the other breakdowns, and when a 17-way pick is used instead.", U, "spec 13"))

    # ------------------------------------------------------------------ Collectibles (spec 15)
    add(_f(COLLECTIBLES, "The game rolls for a collectible 30 times a second while it runs (not paused): about one "
                         "every 73 real seconds, every 37 with the Lucky Rock.", C,
           "spec 15: CCollectableItem::Update, 3 in 6,600 (3 in 3,300)"))
    add(_f(COLLECTIBLES, "Rarity: rare 4%, uncommon 13%, common 83%; with the Lucky Rock 8%, 26% and 66%. The same "
                         "item never appears twice at once.", C, "spec 15: CCollectableItem::Add 0x44CA10"))
    add(_f(COLLECTIBLES, "Collectibles vanish again after a while, in real time.", C, "spec 15"))

    # ------------------------------------------------------------------ Flea Market and On Sale (spec 16)
    add(_f(STORE, WITH_PATCHER + "the Flea Market shows all 36 of its goods at all times; it never changes (the "
                  "game's tip still says three times a day).", E,
           "GetCategoryItemCount 0x46B6D0 / GetCategoryItem 0x46B210 call VF2GetExpandedFleaMarketCount / Item "
           "0x4B9A90 / 0x4B9AB0 first (36 for category 15); the stock rotation 0x46BEB0 is never reached"))
    add(_f(STORE, UNPATCHED + "the Flea Market shows 5 of its 36 goods, picked at random, and changes them every 6 "
                  "real hours: the first time it is opened more than 6 real hours after the last change it picks 5 "
                  "new ones (the time counts while paused and while the game is closed). The game's tip says three "
                  "times a day.", E,
           "stock exe sha256 1582d9e8: the store menu's Flea Market row (table 0x5346E0 row 1, category 15) -> "
           "SetStoreCategory 0x432050(15) -> GetCategoryItemCount 0x4BB0A0 -> MaybeUpdateRotatingItems 0x4BA710, "
           "run as linked after Reset 0x4BA8F0: 5 goods at real s T, the same 5 at T + 21,600, 5 new at "
           "T + 21,601 and at T + 86,400; next change = real s + 21,600"))
    add(_f(STORE, "On Sale: 3 furniture items, changed every game day (24 real hours at normal speed; the clock "
                  "stops while paused).", C, "spec 16: MaybeUpdateSaleItems 0x46C000"))
    add(_f(STORE, "How much the On Sale price is reduced.", U, "spec 16: price path"))
    add(_f(STORE, "Each of the 10 house renovations adds to the family's happiness every 30 minutes.", C, "spec 16"))

    # ------------------------------------------------------------------ Chance and timer index (spec 17, 18)
    add(_f(INDEX, "Every chance on this page is exact: the game rolls rand(N) and every value is counted, so "
                  "\"30% (30.03%)\" means 9,840 of the game's 32,768 equally likely values.", C, "spec header"))
    add(_f(INDEX, "Chances, all shown above:", C, "spec 18"))
    for text in ("a malfunction 1 in 800 every 2 seconds, then 1 of 14;",
                 "a Random Event's kind: Email Event 66%, Popup Event 34%, then 1 among those that can happen;",
                 "a missed meal 50% (50 food or less), starvation 30.03%, waste 76%, no food 76%;",
                 "illness per check 1.007% (2.518% with a catching housemate), losing health while sick 61%, "
                 "recovery 50% (10% from 55);",
                 "an infection ending 3% (mild) or 1.2% (serious) per check, a symptom lasting 6 to 17 hours;",
                 "old age 10% per year over, pregnancy by the table, twins 5.25%, triplets 1.75%;",
                 "work success 56.25% to 100%, a career from 132;",
                 "weather: the next kind 1 in 5, normal 15 to 40 minutes, others 6 to 12;",
                 "a collectible 3 in 6,600 per frame (3 in 3,300 with the Lucky Rock), rare 4%, uncommon 13%;",
                 "a mess: under 30 of 100 a weed, under 55 a sock, under 80 a wrapper, else a smudge."):
        add(_f(INDEX, text, C, sub=True))
    add(_f(INDEX, "The other rolls the game makes: how long actions last and which way they are done, animations, "
                  "e-mail wording, names and looks. What actions give the family is not decoded yet.", U,
           "spec 18: 4,431 behaviour sites"))
    add(_f(INDEX, "Timers, in real time at normal speed (game-clock timers stop while paused; real-time ones run "
                  "while paused and while the game is closed):", C, "spec 17"))
    for text, label in (
            ("upkeep: every 2 seconds, also while paused;", C),
            ("one age unit: 10 minutes (real time; paused time is discarded);", C),
            ("a pregnancy: 3 hours 30 minutes;", C),
            ("a symptom: 6 to 17 hours (real time);", C),
            ("a food group: 24 hours (real time);", C),
            ("interest and the Food Club: each game day (24 hours), interest at most 2 days at once;", E),
            ("a Random Event: every hour (game clock);", C),
            ("the dating e-mail: 3 minutes, then 5 minutes per date plus 10 per year over 26 (game clock);", C),
            ("the Maid and the Gardener: every hour in the day by your PC's clock (game clock);", C),
            ("messes: every 5 hours, 2.5 with 4 or more in the family (game clock);", C),
            ("a collectible: about every 73 seconds (37 with the Lucky Rock);", C),
            ("a house malfunction: about every 27 minutes, also while paused;", E),
            ("the autosave: every 2 minutes (real time), also while paused, to the same save file a quit "
             "writes; the same in the unpatched game;", E),
            ("a weather spell: normal 15 to 40 minutes, others 6 to 12 (game clock);", C),
            ("On Sale: every 24 hours (game clock);", C),
            ("the Flea Market, with the patcher: never changes;", E),
            ("the Flea Market, unpatched game: every 6 hours (real time);", E),
            ("a body removed: 40 hours after death (real time);", C),
            ("the baby waiting time: 10 minutes to 4 hours 10 minutes (real time);", C),
            ("time away made up: at most 31,000 seconds, or 24 hours when more than 24 hours away.", E)):
        add(_f(INDEX, text, label, "spec 17", sub=True))
    return out


# Random Events of the core build (spec 11 table), in family words.  Each line's label: VERIFIED-E (run as linked)
# unless the spec marks part of it UNCONFIRMED or the event could not be shown to happen.
_EVENT_LINES = (
    ("A Secret Admirer (Email Event, someone living alone): nothing else happens.", E),
    ("I Ate Soup, I am on a BOAT, So Many Babies, Status: Single, I Lost My Pants, Boring, Likes (Email Events, a teen or "
     "adult at home): happiness only; I am on a BOAT and So Many Babies -10, Status: Single and I Lost My "
     "Pants +10, Boring -20 energy.", E),
    ("Oh So Clever (Email Event): -10 happiness and a 15% chance of a stomach upset.", E),
    ("Electric Bill Correction (Email Event): -$5 to -$24, or +$5 to +$24.", E),
    ("Spam e-mails (Funny, Bigger Brain, Nigerian Lottery, Car Insurance, What's What): only without the Anti-Spam "
     "Software; nothing happens.", E),
    ("Professional Association Fee (Email Event): -$5, -$8 or -$11.", E),
    ("Professional Association Rebate (Email Event, someone working): +$5 to +$32.", E),
    ("Professional Network (Email Event, someone working): 20 pieces of unpaid career progress.", E),
    ("Professional Association Award (Email Event): a promotion.", E),
    ("Infringement Complaint (Email Event): nothing happens.", E),
    ("Tax Audit (Email Events): a fee of -$40 to -$114, or a gift of +$500.", E),
    ("Old Friend (Email Events, three kinds): nothing happens.", E),
    ("Oh! A collectible! (Email Event): a collectible appears.", E),
    ("My Weather Machine (Email Event, normal or sunny weather): rain, snow or fog, a third each.", E),
    ("An extra hammock (Email Event): everyone runs to the yard.", U),
    ("Birthday present +$10 to +$50; Preferred Customer +$5 to +$79; Craft Fair +$35 to +$45; Rebate +$50; Helpful "
     "Child +$5 to +$54; Bad Cookies -$5 to -$100 (Email Events).", E),
    ("Office Collection -$4 to -$40 or -$5 to -$50; Overdue Book -$5 to -$50; Bake Sale -$6 to -$60 (Email Events).", E),
    ("Best Landscape Award (Email Event, 5 weeds or fewer): +$10 for each weed fewer than 6.", E),
    ("Kite Contest +$8 to +$80; Hot Dog Contest +$5 to +$50 (Email Events).", E),
    ("Neighborhood Children's Association (Popup Event, a child at home): -$10 per child.", E),
    ("Angry Note, Sad Note, Room Specification, RSVP, Funeral Book, Adoption Response, The Deed, Earthquake "
     "(Popup Events): nothing else happens.", E),
    ("Aesthetic Society (Popup Event, weeds in the yard): -$5 per weed.", E),
    ("Birdwatcher Society (Popup Event): +$25, +$50, +$75 or +$100.", E),
    ("Allergy Season (Popup Event): 3 random family members get a runny nose.", E),
    ("Adoption Day (Popup Event): everyone celebrates.", E),
    ("TV Night, BBQ Party (Popup Events, with a TV or a grill): everyone joins in.", E),
    ("The Broken Window (Popup Event): +$1 to +$30.", E),
    ("Photo Contest (Popup Event, 2 or more people) +$25 to +$125; Community Association -$20 to -$100.", E),
    ("Blowing Trash (Popup Event): 5 to 12 pieces of trash in the house. Free Lawn Service: 5 to 12 weeds in the yard.",
     E),
    ("Little Visitor (Popup Event, room for a child): yes, a 3-year-old boy or girl joins the family.", E),
    ("EPA Visit (Popup Event): yes, pay three quarters of an upgrade's price and get it built; no, a 75% chance of a skin "
     "rash for everyone at home.", E),
    ("Chemical Manifest (Popup Event): yes, pay for and get an item, then the 75% skin-rash chance; no, the skin-rash "
     "chance.", E),
    ("Boy Selling Cupcakes (Popup Event): yes, -$10 and a 50% chance of a stomach upset; no, -$45.", E),
    ("Girl Selling Magazines (Popup Event, room in the tray): yes, -$20 and one of three items.", E),
    ("Ran Out Of Diapers (Popup Event, a baby): yes, -$60. Diaper Rash: yes, pay for an item; no, everyone -10 energy. "
     "Lost Binky: yes, everyone +15 happiness.", E),
    ("Bug Whisperer (Popup Event): yes, -$75 and two random bug collectibles.", E),
    ("Collecting Contest (Popup Event): yes, +$10 with fewer than 10 collectibles, +$50 with 10 to 20, +$100 with 21 or "
     "more.", E),
    ("Adult-proof (Popup Event, 2 or more children): yes, -$50.", E),
    ("Small Package, Medium Brown Box, Sealed Green Bag (Popup Events, room in the tray): yes, a random item.", U),
    ("A Tiny White Box (Popup Event): yes, a third of the food is lost.", E),
    ("Scratch-Off Lottery Ticket (Popup Event): yes, -$20 and a 33% chance of winning $0 to $90 (in $10 steps).", E),
    ("The Wrong Address (Popup Event): yes, -$100 and one of two pieces of furniture.", U),
    ("The Delivery Truck (Popup Event): yes, a piece of furniture; no, an amount of $0 to $140 (in $20 steps).", U),
    ("Talent Scout (Popup Event, a child): yes, the child leaves home and the family gets $500.", E),
    ("Beauty Contest (Popup Event, a child): yes, -$10 and a 33% chance of winning $100.", E),
    ("Landscaping -$20, the weeds gone; Housekeeping -$20, the socks, wrappers and smudges gone; Total House Care "
     "-$50, all of them gone (Popup Events).", E),
    ("The Mysterious Collector (Popup Event): buys collectibles.", U),
    ("Water Pressure Surge (Popup Event): no brings five leaks.", E),
    ("Professional Career Training (Popup Event): yes, -$250 and a promotion.", E),
    ("The Trainer (Popup Event): yes, -$5 and all the food is lost.", E),
    ("The Cooking Class (Popup Event): yes, a cooking mess in the kitchen.", E),
    ("The Power Failure (Popup Event): the power goes out. Throw out the food: the food store is reset. Take a chance: no one ill "
     "70.8%, one family member with a stomach upset 20.8%, two 8.3%.", E),
    ("Career Change Counselor (Popup Event): yes, a new random career at level 0.", E),
    ("The Rare Bird (Popup Event): everyone runs to the yard.", U),
    ("School Fund-raiser (Popup Event): yes, -$25 and +100 food.", E),
)


def render_lines(items: list[Fact] | None = None) -> list[tuple[str, str | None, str]]:
    """The page as lines: ("heading", None, group) or ("line", label, text with its bullet)."""
    items = facts() if items is None else items
    out: list[tuple[str, str | None, str]] = []
    group = None
    for fact in items:
        if fact.group != group:
            out.append(("heading", None, fact.group))
            group = fact.group
        out.append(("line", fact.label, (SUB_BULLET if fact.sub else BULLET) + fact.text))
    return out


def render(items: list[Fact] | None = None) -> str:
    """The page as plain text: each group's heading, then its lines, each with its label right after the bullet."""
    lines = []
    for kind, label, text in render_lines(items):
        if kind == "heading":
            if lines:
                lines.append("")
            lines.append(text)
        else:
            mark = SUB_BULLET if text.startswith(SUB_BULLET) else BULLET
            lines.append(f"{mark}{label}  {text[len(mark):]}")
    return "\n".join(lines)
