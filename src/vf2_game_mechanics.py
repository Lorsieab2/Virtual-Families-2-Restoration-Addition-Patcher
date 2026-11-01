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

Every store item (2026-10-27, the owner's rule "Elaborate on what every store item and upgrade and research and
everything does"): the groups from "The store: prices and buying" to "Clothing and Hairstyles" give each item the
store sells its own entry: price (stock first, then the patcher's where it differs), uses, the exact effect with its
numbers and odds, who it acts on, how long it lasts and what unlocks it.  The store tabs, prices and locks were run as
linked in both executables; the effects were read from the purchase and use code (docs/game-mechanics/spec.md
section 23; tests/test_game_mechanics_store.py).  Corrections made on the way: the Time Warp, the Lotto Ticket, the
Health Plan, the Food Club's prices, the On Sale price, Boarding School and the medicines were UNCONFIRMED and are now
read from the purchase path (HandleMouse -> HandlePurchaseItem -> HandleUpgrade); Bottled Tropical Sunshine sets the
weather to type 0 and Bottled Tropical Rain to Stormy (type 3).  Weather uses the owner's names: Normal (the plain
sky, the code's type 0 eWeather_Sunny), Sunny (the grey tint with sun beams, type 1 eWeather_Cloudy), Raining,
Stormy, Foggy, Snowing.

Hidden keys, clicks and cheats (2026-10-27, the owner's rules "PUT IMPORTANT STUFF LIKE HIDDEN KEY COMBOS AND CHEAT
CODES IN GAME MECHANICS", "places you can click for random tips and hidden cheats", "beware of making false claims
over verified dead developer code"): every key handler, typed-character table, click spot, tip and code path was read
by symbol from the B200 desktop objects (work/desktop_obj_files), each with its caller chain from a live screen;
code with no caller is given as "Dead code, never a player action".  VF2's store has no key that redraws its
specials (Virtual Families 1's store page has one): the store reads Esc only.  Where a live report and the code
disagree, both are written, each labelled (the owner's rule "for cases where the code contradicts live observation
write both cases down"; the Bottled Tropical Sunshine is the one such case).  tests/test_game_mechanics_hidden_keys.py.

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
HIDDEN = "Hidden keys, clicks and cheats"
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
STORE = "The store: prices and buying"
FOOD = "Food and Medicine"
FLEA = "Flea Market"
UPGRADES = "Special Upgrades"
SERVICES = "Services"
RENOVATION = "Home Renovation"
CAREER_UPGRADES = "Career upgrades"
FURNITURE = "Furniture and Accessories"
PETS = "Pets"
CLOTHING = "Clothing and Hairstyles"
ACTIONS = "Actions"
INDEX = "Chance and timer index"
STORE_GROUPS = (STORE, FOOD, FLEA, UPGRADES, SERVICES, RENOVATION, CAREER_UPGRADES, FURNITURE, PETS, CLOTHING, ACTIONS)
GROUPS = (TIME, HIDDEN, NEEDS, HEALTH, OLD_AGE, PREGNANCY, CAREERS_GROUP, MONEY, LEAVING, DATING, EVENTS, WEATHER, MESSES,
          COLLECTIBLES) + STORE_GROUPS + (INDEX,)

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
    """A career's pay per hour of game time: salary / 4 every 3 age units (spec section 2, 0x4C452E)."""
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
                f"{name}: {_per_hour(salaries[0])} per hour of game time as a Beginner, "
                f"{_per_hour(salaries[7])} as a Master (levels: "
                + ", ".join(_per_hour(s).lstrip("$") for s in salaries) + ")."), C,
                "careers.tsv", sub=True))
    return lines


# The random tips (theStringManager eRandomTip1.. , string ids 0x9E3..0xA1E), in the game's order, in short: the
# page gives what each says, not the game's own wording.
RANDOM_TIPS = (
    "praise behaviours selectively", "punishing too many behaviours can depress a family member",
    "family members have minds of their own", "work without play makes a dull life", "living alone is hard",
    "the house and its improvements pass down the generations", "a compatible spouse makes a family member happiest",
    "two people working in the same room share its resources", "jobs are not all equal",
    "careers have different pay curves", "life is full of drama", "money can buy a little happiness",
    "family members sometimes leave appliances running", "repairing the house helps the generations to come",
    "an untidy house wears down anyone's cheer", "the weeds in the yard never stop",
    "different illnesses need different treatments", "the family lives in your time zone",
    "family members like your affection", "couples who want children are less happy without them",
    "couples who do not want children may still have them", "couples differ in how easily they have children",
    "career room upgrades make promotions come faster", "you live and you learn",
    "a very sad family member may need food", "getting ahead at work is a great joy",
    "a large family brings joy, and loose socks", "they still do not like the red glove",
    "children move out at a certain age", "it is nice to stay indoors when it rains",
    "repeated illness may mean an infection", "praising a behaviour reinforces it", "who made this house?",
    "working family members are paid hourly too", "save for interest, or spend on new things",
    "encourage meals and discourage snacking", "there is more to life than money",
    "learn from yesterday, live for today, hope for tomorrow", "someone sick a lot should see a doctor",
    "furniture placed outside the gates is sold at once", "medical treatment is expensive",
    "it is never too late for a happy childhood", "random events can be good or bad",
    "waiting for the perfect match, but for how long?", "the ability to have children falls with age",
    "marriage proposals come less often with age", "older family members slow down",
    "older family members change what they find fun", "more babies in a large family can cause friction",
    "difficult children can be sent to boarding school", "psychotherapy helps fears and depression",
    "the Flea Market changes its goods several times a day (of real time)","the Flea Market has real bargains",
    "fixing up the house is satisfying", "rare fossils need special training", "tired of weeding? hire a Gardener",
    "tired of tidying? hire a Maid", "socks piling up? a washer and dryer helps", "couples can choose to adopt",
    "it is evening in their world when it is evening in yours")

# The house's click spots (theMainScene::MapClickFeedback, the hotspot under a left click that does not pick up a
# family member, a pet, a tool or a furniture piece): (hotspot, what the click does, evidence).
CLICK_SPOTS = (
    ("The fridge", "opens it and shows \"Food available:\" with the food the family has", "hotspot 0x16: SetProp(3), "
     "Say(eSayFoodLevel 0x734, CFoodStore+0x78)"),
    ("The kitchen trash", "shows \"Trash:\" with the trash count (full at 20) and plays a sound", "hotspot 0xD: "
     "Say(eSayTrashLevel 0x7AE, gs+0x28), sound 0x84"),
    ("The router", "shows \"Router error!\" while the router is offline (a malfunction or the Power Failure event), "
     "else \"Status: online\", with a sound", "hotspot 0x1E: prop 0x17 -> eString_RouterError 0xDA, else eSayRouter "
     "0x7AC; sound 0xA3"),
    ("The collection cabinet", "shows \"Collectibles Found: N / 60\", N counted over the 5 collections",
     "hotspot 4: CollectionCount(0x67, 0x4F, 0x5B, 0x86, 0x92) summed, eString_CollectiblesFound 0x241 + \" / 60\""),
    ("The sock pile", "shows \"There are N socks here\" (\"There is 1 sock here\"); with no socks, nothing",
     "hotspot 0x49: gs+0x148 > 0, strings 0x242..0x245"),
    ("The TV", "turns it on; clicked while on, turns it off and everyone watching it starts Objecting",
     "hotspot 0xF: prop 0x32; off -> ChangeAllBehavior(0x3E..0x45 -> 0xBE Objecting)"),
    ("The computers", "turns both off if on (clicking never turns them on)", "hotspot 0x12: ClearProp 0x24, 0x25"),
    ("The bathroom sink", "turns its running water on, or off when it is running", "hotspot 0xA: props 1 and 2 "
     "both set -> both cleared, else both set"),
    ("The shower", "turns it on, or off when it is running", "hotspot 0xB: prop 0x29 toggled"),
    ("The kitchen sink", "turns it on, or off when it is running", "hotspot 0x1A: prop 0x10 toggled"),
    ("The toilet", "plays a sound, toggles the toilet and says \"This is the toilet\", or \"The toilet is broken!\" "
     "while it is broken", "hotspot 9: sound 0x83, prop 0x3B toggled, prop 0x1A -> eString_ToiletBroken 0xDB, else "
     "eString_ThisIsToilet 0xDC"),
    ("With the 2nd Bathroom: the north bathroom's toilet", "the same, while the renovation is not under construction "
     "(\"The toilet is broken!\" while the north toilet is broken)", "hotspot 0x3F: HaveUpgrade(0xE6), prop 0x43 "
     "clear, sound 0x83, prop 0x3C toggled, prop 0x48 -> 0xDB else 0xDC"),
    ("With the 2nd Bathroom: the north shower", "turns it on, or off when it is running", "hotspot 0x4B: "
     "HaveUpgrade(0xE6), prop 0x47 toggled"),
    ("With the 2nd Bathroom: the north sink", "turns it on; it then never turns off by a click, because the code turns "
     "on the main bathroom sink's second prop instead of the north sink's (a stock slip)", "hotspot 3: "
     "HaveUpgrade(0xE6); both 0x4B and 0x4C set -> both cleared, else SetProp(0x4B) and SetProp(2), never 0x4C"),
    ("With the Pinball Machine, the MP3 Player and Speakers, the Paper Shredder, the Pro Blender and Electric Mixer or "
     "the Pro Food Processor and Slicers: that piece", "plays its sound only", "hotspots 0x17 / 0x18 / 0x1D / 0x1B / "
     "0x1C: HaveUpgrade(0x20B / 0x207 / 0xF2 / 0xFA / 0xF9), sounds 0xE6 / 0xE7 / 0xA8 / 0xC1 / 0xA2"),
    ("A room that needs renovating", "shows \"Ew! This room is full of bugs!\" (infested), \"Ew! This room is "
     "contaminated!\", \"Ugh! This room is filthy and broken!\" (the broken dining room, living room and master "
     "bedroom) or \"Hmm...just a foundation here!\" (the broken laundry room, the unfinished bathroom and kids' room, "
     "the front and back porches)", "hotspots 0x34 / 0x35 / 0x36, 0x38, 0x39 / 0x37, 0x3A, 0x3B, 0x3D, 0x3E: strings "
     "0x831 / 0x832 / 0x834 / 0x833"),
)


def _hidden_lines() -> list[Fact]:
    """Every hidden key, click spot, code and tip (the B200 desktop objects work/desktop_obj_files, by symbol)."""
    g = HIDDEN
    out = [
        _f(g, "How keys reach the game: letters, digits and punctuation arrive only as typed characters (so Shift, Caps "
              "Lock and the number pad with Num Lock on give the same keys as typing them), and only these keys arrive "
              "as keys: Esc, Tab, Enter, Backspace (as the typed character 8), Delete, Insert, Home, End, Page Up, "
              "Page Down, the four arrows and F1 to F10. F11, F12, Print Screen, Scroll Lock, Pause and Shift, Ctrl or "
              "Alt on their own never reach any screen, and no screen reads Shift, Ctrl or Alt together with a key or "
              "a click. Only the left mouse button is read: the right and middle buttons do nothing anywhere.", C,
           "ldwGameWindowImpl::CheckForEvents: SDL_TEXTINPUT (0x303) of one byte -> HandleKey(5, char, 0); "
           "SDL_KEYDOWN/UP (0x300/0x301) -> HandleKey(6/7, code, sym) through tables $LN76/$LN80/$LN81: Esc 0x3E8, "
           "Tab 0x3EA, Enter 0x3EB, Left 0x3EC, Right 0x3ED, Up 0x3EE, Down 0x3EF, PgUp 0x3F0, PgDn 0x3F1, Home 0x3F2, "
           "End 0x3F3, Insert 0x3F4, Delete 0x3F5, F1..F10 0x3FA..0x403, Backspace -> HandleKey(5, 8, 8); mouse "
           "events only for button 1 (motion 1, down 2, up 3); ldwEventManager::HandleKey dispatches to the active "
           "screen (ldwScene::SetActive subscribes with flags 0xF)"),
        _f(g, "Alt+F4 closes the game window the same way as the window's close button (the same quit flag). F4 "
              "without Alt does nothing on any screen.", C,
           "CheckForEvents $LN17: F4 with KMOD_ALT (mod & 0x300) sets the window's closed flag +0x1D, as SDL_QUIT "
           "(0x100) does; otherwise code 0x3FD, which no live screen handler compares"),
        _f(g, "There is no cheat code, no typed password and no setting, registry key or command-line switch that "
              "turns on a hidden key. ldw.ini's [ldw] section is read for FullScreen, ForceFullScreen, ForceWindowed, "
              "ForceStaticSplash (a still picture instead of the opening movie) and Distributor (the name after "
              "\"Version 1.2.4,\" on the title screen) only.", C,
           "every GetConfigValue / GetConfigString caller: theGameState::InitGameInfo / Load, theOptionsDialog, "
           "theSplashScene::Activate, theMenuScene ctor; no GetCommandLine / __argv / registry read in the game's "
           "own code (the ATL CRegKey code belongs to the Flash player)"),
        # ---- the house
        _f(g, "In the house (the typed keys are the same in the unpatched game):", C,
           "theMainScene::HandleKey 0x0: type 5 -> HandleKeyCharacter (table $LN67/$LN69, chars 0x20..0x77), type 6 "
           "-> HandleKeyDown; stock exe sha256 1582d9e8 has the same character handler at 0x43BA30 (tables "
           "0x43BCEC / 0x43BCA0)"),
        _f(g, "Space: pauses the game, or unpauses it at the speed it had (Slow, Fast, 5x and 10x from the patcher's "
              "Time Controls are kept); unpausing also clears the message line.", C,
           "HandleKeyCharacter $LN43: speed field gs+0x25B18 >= 999 -> SetSpeed(field - 999), field = that or 10 when "
           "it was 0, CDealerSay::Reset; else SetSpeed(999) and field + 999", sub=True),
        _f(g, "1 to 9: move the view to one of 9 fixed places, laid out like the number pad: 7, 8, 9 the top of the "
              "house map, 4, 5, 6 the middle, 1, 2, 3 the bottom; 1, 4 and 7 the left side, 3, 6 and 9 the right. "
              "Unless a family member is being carried, the selection is cleared too.", C,
           "HandleKeyCharacter $LN12..$LN28: CWorldView::ScrollTo (-40,1410) (520,1410) (1250,1410) / (-40,827) "
           "(520,827) (1250,827) / (-40,50) (540,50) (1240,50); SetNoFocus when +0x60 == -1", sub=True),
        _f(g, "S: opens the store at its menu. D: does what the Details button does (the selected family member's "
              "Details screen; with the hired Maid or Gardener selected it asks whether to fire them). C: the "
              "Collections screen. F: the Family screen (the family tree). T: the Goals screen. Esc: the game menu. "
              "Both cases work (s or S).", C,
           "HandleKeyCharacter -> HandleMessage(8, n): S 3 -> SetStoreCategory(0x17) + ChangeScene(0xF); D 1 -> "
           "HandleVillagerDetailsButton (focus 0x23/0x24 -> the fire message box); C 4 -> scene 0xB; F 7 -> scene 8; "
           "T 8 -> scene 0xA; HandleKeyDown 0x3E8 -> HandleMessage(8, 0) -> theGameMenuDialog", sub=True),
        _f(g, "M and P are taken and do nothing. Every other key does nothing in the house.", C,
           "HandleKeyCharacter $LN31 (M, P, m, p) returns true with no action; $LN2 / $LN47 the rest", sub=True),
        _f(g, "Dead code, never a player action: F then W moves a hidden counter from 1 to 2, and any other key sets it "
              "back to 0, but nothing in the game ever reads that counter.", C,
           "HandleKeyCharacter $LN36 / $LN40 / $LN47 write theMainScene+0x50; the constructor writes 0; no other "
           "read of +0x50 in theMainScene.obj", sub=True),
        # ---- other screens
        _f(g, "On the other screens: Esc does what the screen's first button does, and on two screens that button does "
              "more than leave:", C,
           "each scene's HandleKey: type 6 and code 0x3E8 -> HandleMessage(8, 1) (CCollectionScene 8, 0)"),
        _f(g, "The store, the Family screen, the Goals screen and the Collections screen: Esc goes back to the house. "
              "On the Collections screen F1 does the same.", C,
           "CScrollingStoreScene / CFamilyTreeScene / CAchievementsScene HandleMessage(8, 1) -> scene 0; "
           "CCollectionScene::HandleKey 0x3E8 or 0x3FA -> HandleMessage(8, 0) -> scene 0", sub=True),
        _f(g, "The Details screen: Esc is its Done button (a name typed there is kept).", C,
           "theVillagerScene::HandleKey 0x3E8 -> HandleMessage(8, +0xE4 = 1): GetText -> CFamilyTree::ChangeName, "
           "scene 0", sub=True),
        _f(g, "The adoption screen: Esc adopts the person shown, exactly as the Adopt button does (the button that "
              "shows the next person is message 2).", C,
           "CAdoptionScene::HandleKey 0x3E8 -> HandleMessage(8, 1): the candidate joins (StartFamilyTree / "
           "StartNextGeneration), scene 0; message 2 -> GeneratePeepCandidate", sub=True),
        _f(g, "The dating screen: Esc accepts, as the accept button does: the chosen suitor marries in (the marriage "
              "goals, money and happiness changes all happen) and everyone starts Celebrating marriage; with no "
              "suitor chosen, everyone celebrates and the game returns to the house with no marriage. The decline "
              "button is message 2 (Shaking head). Whether a suitor is already chosen when the screen opens is "
              "not traced.", C,
           "CDatingScene::HandleKey 0x3E8 -> HandleMessage(8, 1): +0x10 != -1 -> NewBehavior 0x63, achievements, "
           "CMoney::Adjust, UpdateParents, happiness; then MakeAllVillagersDoIt(0x7A); message 2 -> 0x175", sub=True),
        _f(g, "Help (from the game menu): F1 goes back to the house; nothing else.", C,
           "theHelpScene::HandleKey 0x3FA -> scene 0; reached from theGameMenuDialog::HandleMessage -> ChangeScene(0xD)",
           sub=True),
        _f(g, "The title screen and the loading screen take no keys.", C,
           "theMenuScene::HandleKey and theLoadingScene::HandleKey return false", sub=True),
        _f(g, "The opening movie: a typed key skips to the next opening picture, then to the loading screen. F1 skips "
              "straight to the house, before the loading screen has loaded the art and the family; what the game "
              "then shows has not been traced (never run).", C,
           "theSplashScene::HandleKey: type 5 -> CMoviePlayer::Stop, next page (+0x14 < +0x2C) or scene 0xC; "
           "0x3FA -> SetActive(false), scene 0; theGame::GameUpdate runs the 7 loading steps only in scene 0xC",
           sub=True),
        _f(g, "Dialog boxes: in a Yes/No or OK box Enter is Yes/OK and Esc is No/Cancel. In the store's buy box Enter "
              "and Esc both cancel; only its Buy and more-money buttons do otherwise. In the new-player name box, the "
              "family-tree card and the Redeem Credit box Enter is OK and Esc is Cancel. The bank and the doctor's "
              "diagnosis close on Enter or Esc. In the change-player box both press its first button; what that does "
              "there has not been decoded.", C,
           "theMessageBoxDlg: 0x3EB -> message 1 -> result 0, 0x3E8 -> message 2 -> result -1; thePurchaseDialog::"
           "HandleMessage: messages 3 / 4 -> results 0 / 1, others -1; theCreateNickNameDlg, CFamilyTreeInfoDlg, "
           "RedeemCreditDlg: 0x3EB -> 1, 0x3E8 -> 2; CBankingDlg, theDiagnosisDialog, theChangePlayerDlg: 0x3E8 or "
           "0x3EB -> 1", sub=True),
        _f(g, "Typing in a name box: Backspace deletes the last letter, Enter or Tab finish; any character from space "
              "up is taken (a number box takes digits, and a minus sign first).", C,
           "ldwTextControlImpl::HandleKey: char 8 deletes, 0x0D / 9 -> EndEdit, 0x20..0xFF (digits, '-' at 0 for "
           "a numeric box)", sub=True),
        # ---- click spots
        _f(g, "The store's hidden Redeem Credit corner: press and hold the left mouse button in the top-right corner of "
              "the store (x 972 to 1,024 and y 0 to 51) without moving out of it. After more "
              "than 5 seconds of game time (5 to 6 seconds of real time at Normal speed; never while paused) a Redeem "
              "Credit box opens to type a code. The same in the unpatched game.", C,
           "CScrollingStoreScene::HandleMouse type 2 in gCreditTriggerRect {972, 0, 1024, 51} -> +0x164 = 1, +0x168 = "
           "CGameTime::Seconds() + 5; type 1 outside or type 3 -> 0; UpdateScene: Seconds() > +0x168 -> "
           "RedeemCreditDlg; stock exe: the same rect at file offset 0x134834"),
        _f(g, "The code is sent to LDW's server (ldwsoftware.com/game_backend/promocode.php, game VF2); no code is "
              "kept in the game. A reply of coins adds that many dollars (\"N coins have been added to your "
              "balance.\"); a brokerage reply adds 2 points of interest per point (0.02 each), though its message says "
              "N%; \"invalid\" says the code is not valid; no reply says there was a problem. LDW's server no longer "
              "runs its scripts (see LDW's server at startup below), so in practice there is no real reply. (This "
              "page said earlier that whether it still answers had not been traced; it now has been, from the "
              "owner's crash dumps.)", C,
           "HandleRedeemCredit -> CPromoCode::Submit(\"promocode.php?code=%s&game=%s\", \"VF2\") -> CWebClient "
           "(ldwsoftware.com, /game_backend/) -> PromoCodeCallback: \"coins\" -> CMoney::Adjust(value); "
           "\"brokerage\" -> CMoney+8 += 0.02 x value; \"invalid\"", sub=True),
        _f(g, "LDW's server at startup: at every start the game asks ldwsoftware.com/game_backend/login.php to log "
              "in (and later message.php for news and poll.php for polls), without showing anything. A real answer "
              "is JSON: a login stores a session id; messages go to the news; polls to the polls. Every answer is "
              "read by one reader, once, into room for 2,048 bytes.", C,
           "theGame 0x4982C6 -> CLogIn::Begin 0x4816C0 (\"login.php?id=%s&platform=%s&game=%s\") -> CWebClient::Request "
           "-> WebClientCallback (B204 0x4D46D0; retail 0x4C3360), status 100: InternetReadFile(h, buf[0x800], "
           "0x800, &n); buf[n] = 0 -> the handler (CLogIn::Callback 0x481740, CRetrieveMessage, CPoll, CVote, "
           "CPromoCode, CMicroTransaction), each of which treats NULL as no reply and parses JSON (CJSON::Parse "
           "accepts only '{' first)"),
        _f(g, WITH_PATCHER + "the reader takes at most 2,047 bytes, so it never writes past its room, and an "
              "answer that filled the room (cut short) or begins with \"<\" (a script or web page, not the server's "
              "answer) is treated as no answer, as when the server does not reply: nothing is logged in, shown or "
              "changed. A short real answer is handled exactly as before (part of Fix Vanilla Game Bugs).", C,
           "patch_server_reply_guard: WebClientCallback +0x20 push 800h -> 7FFh; +0x51 the reply -> NULL when "
           "n == 7FFh or its first non-blank byte is '<'; both behind .vf2bugs; emulated in "
           "tests/test_server_reply_guard.py (3,125-byte PHP reply: no fast-fail, NULL; short JSON: unchanged)",
           sub=True),
        _f(g, UNPATCHED + "an answer of 2,048 bytes or more fills the room and the reader writes its end marker one "
              "byte past it, and the game closes itself (error 0xC0000409, no message).", C,
           "stock exe sha256 1582d9e8: push 800h at 0x4C3388, mov byte [esp+eax+4],0 at 0x4C33A4 overwrites the "
           "/GS cookie at esp+804h -> __security_check_cookie 0x4C3BCE fast-fails; rebuilt executables: "
           "cmp eax,800h; jae ___report_rangecheckfailure (int 29h, code 8)", sub=True),
        _f(g, "The code against live, both written: the code alone only says a long answer would crash it. Live, "
              "LDW's server now answers every one of these requests with the PHP script's own source text "
              "(about 3 KB), so the unpatched game closes itself about 20 seconds of real time after it starts, "
              "whenever that "
              "answer arrives (the owner's crash dumps hold it in the reader's room, 2,048 bytes read).", C,
           "the owner's dumps \"VF2 Copy Test.exe.*.dmp\" (2026-10-31): the read buffer starts \"<?php\", n = 0x800, "
           "0xC0000409 on a WinINet thread; the server was not contacted for this page", sub=True),
        _f(g, WITH_PATCHER + "when a real answer carries an error, its error text is cut to fit the 256 "
              "characters the game keeps for its \"Server error\" note, so a long one cannot crash the game; a "
              "short one gives exactly the note it gave before (part of Fix Vanilla Game Bugs).", C,
           "patch_server_error_text_bounded: the \"Server error: %s\" sprintf of CLogIn, CRetrieveMessage, CPoll, "
           "CVote, CPromoCode and CMicroTransaction ::Callback -> a stub: __stdio_common_vsprintf(options | 2, "
           "buf, 0x100, ...) behind .vf2bugs; run in tests/test_server_error_text.py (1,000-character error: inside "
           "the buffer; short: the stock text)", sub=True),
        _f(g, UNPATCHED + "an error text longer than about 220 characters runs past those 256 characters and the "
              "game closes itself (error 0xC0000409, no message). LDW's server sends no such answer today.", C,
           "stock exe sha256 1582d9e8: e.g. CPoll 0x4C2BF4 and CPromoCode 0x4C2E55 call sprintf 0x4C3C07 with "
           "\"[...] (Callback) Server error: %s\\n\" into the 0x100 bytes below the /GS cookie of a sub esp,104h "
           "frame (CPoll 0x4C2BA0: cookie at [esp+100h])", sub=True),
        _f(g, "The store scenes handle no hidden keys. The store menu, the furniture and accessory tabs, the Flea "
              "Market, On Sale, the Special Upgrades, the Services, the renovations, the career upgrades, the pets "
              "and the outfits are all pages of one store screen, and its only key is Esc (back to the house). No "
              "key or key combination redraws the On Sale items or the Flea Market's goods, as Virtual Families 1's "
              "store page has: they are picked again only when a page is listed, by the clock (see Flea Market and "
              "On Sale). The patcher's R is listed below, with the patcher's keys.", C,
           "every HandleKey in the objects: the store's is CScrollingStoreScene::HandleKey (type 6, 0x3E8 only); the "
           "pages are SetStoreCategory categories; MaybeUpdateSaleItems / MaybeUpdateRotatingItems / "
           "MaybeUpdateOutfits are called only from CInventoryManager::GetCategoryItemCount (from SetStoreCategory), "
           "CInventoryManager::Update (no caller) and Reset (a new family)", sub=True),
        _f(g, "Dead code, never a player action: the Settings box's own Redeem Credit route; the Settings box never "
              "makes that button.", C,
           "theOptionsDialog::HandleMessage id +0x78 = 3 -> RedeemCreditDlg; the constructor builds buttons 2 and 4 "
           "only", sub=True),
        _f(g, "In the house, clicking these spots (a left click that does not pick up a family member, a pet, a tool "
              "or a furniture piece). Each message shows on the message line for 5 to 6 seconds of real time:", C,
           "theMainScene::HandleMouseDown -> HandleMapClick -> MapClickFeedback (hotspot table $LN73/$LN88, base 3); "
           "CDealerSay::Say: shown until GetSecondsFromGameStart + 5"),
    ]
    for spot, does, evidence in CLICK_SPOTS:
        out.append(_f(g, f"{spot}: {does}.", C, evidence, sub=True))
    out += [
        _f(g, "Two of the house map's ground kinds (types 4 and 5) give a click sound and a little animation where "
              "clicked, not while paused. Which ground those two are has not been decoded.", C,
           "HandleMapClick: CContentMap::GetMaterial 4 or 5, not IsPaused -> sound 0x56, CFloatingAnim 0", sub=True),
        _f(g, "Dragging a family member over a spot names what they would do there, on the message line.", C,
           "theMainScene::HandleMouseMove -> SayCurrentContent while +0x60 (the carried member) != -1", sub=True),
        _f(g, "The Details screen: letting go of the left button in its top-left corner (x 0 to 90, y 0 to 90) opens the "
              "store's Services list for that family member: the children's list when they have no career, the "
              "adults' list when they have one.", C,
           "theVillagerScene::HandleMouse type 3, x in +0x90 (0) .. +0x5A, y <= 0x5A: SetStoreCategory(0x13 when "
           "CareerType() == 0, else 0x12), scene 0xF"),
        _f(g, "The Collections screen: pointing at a collectible shows \"N of 4 (common, uncommon or rare) (bugs, "
              "leaves & nuts, fossil pieces or bottle caps) found.\"; a click in the left margin (x under 70) or the "
              "right margin (x over 950) turns to the previous or the next of its 5 pages, wrapping round.", C,
           "CCollectionScene::HandleMouse type 1 -> CollectionCount, strings 0x748..0x753, CDealerSay::Say; type 2: "
           "x < +0x10 + 0x46 -> page - 1 (0 -> 4), x > +0x10 + 0x3B6 -> page + 1 (5 -> 0)"),
        _f(g, "The title screen: a click or a drag changes how the butterflies fly and hands them the mouse point; 7 "
              "seconds of real time after the last click they change back. That they fly to the point is not decoded.", C,
           "theMenuScene::HandleMouse types 1 (button held) and 2: ChangeButterflyStates(0), the point to "
           "UpdateButterflies, +0x20 = GetSecondsFromGameStart + 7; UpdateScene resets the state after it"),
        # ---- tips
        _f(g, "Random tips: the loading screen shows one of the first 30 random tips, chosen when the game starts "
              "(once per run), each 1 in 30 (tips 1 to 8 a hair likelier: 1,093 against 1,092 in 32,768). In "
              "short, the 30 are:", C,
           "theLoadingScene ctor (theGame::Init): GetString(0x9E3 + GetRandom(30)); GetRandom = rand() % n; 32,768 "
           "% 30 = 8"),
    ]
    def tip_line(n, tip):
        return _f(g, f"Tip {n}: {tip}{'' if tip.endswith('?') else '.'}", C, f"string {0x9E2 + n:#x}", sub=True)
    out += [tip_line(n, tip) for n, tip in enumerate(RANDOM_TIPS[:30], 1)]
    out += [
        _f(g, "Dead code, never a player action: tips 31 to 60 are shown only by a click spot left over from an 800 x "
              "600 screen. It sits at x 171 to 221, y 488 to 584, but the code takes it only for a click outside the "
              "house view, and at the game's 1,024 x 768 the view covers x 64 to 1,024, y 0 to 730, so no click can "
              "reach it. Tips 31 to 60, in short:", C,
           "HandleMouseDown 0x1132: reached only when the click is outside CWorldView::scm_sRect (CWorldView::Reset: "
           "{64, 0, width 1,024, height 768 - 38}); rect +0x98..+0xA4 = {0xAB, 0x1E8, 0xDD, 0x248} (+0xA8 = 0); "
           "then sound 0xBD and Say(0x9E3 + GetRandom(60)); SetToWideScreen has no caller"),
    ]
    out += [tip_line(n, tip) for n, tip in enumerate(RANDOM_TIPS[30:], 31)]
    out += [
        _f(g, "The tutorial and its one-time tips are not random: each shows once, when its moment comes, and is then "
              "marked as shown and saved. The Last Tip button shows the last one again. Where each comes from:", C,
           "CTutorialTip::Queue / ConfigureTip / WasDisplayed / SetDisplayed / SaveState; theMainScene::HandleMessage "
           "6 -> HandleLastTipButton -> RepeatLastTip"),
        _f(g, "The first family's tutorial, in steps: welcome and moving about the house, selecting, dragging and "
              "dropping a family member (the bathroom sink, a wrapper to throw away, groceries), praise and scolding, "
              "the Details screen, work, the store, e-mail and a marriage proposal, the first furniture and making a "
              "baby.", C,
           "eTTipInstruct1..eTTipInfo28 (0x845..0x860): CTutorialTip::Reset, CAdoptionScene, theMainScene::"
           "UpdateScene / HandleMouseDown / InvokeReward, CHotSpot::BathroomSink, CBehavior::ThrowAwayWrapper, "
           "CEnvironment::SetPropGroceries, theVillagerScene, CScrollingStoreScene, CDatingScene, "
           "CFurnitureManager::HavePeepsAdmireFurniture, CBehavior::GoInHouse", sub=True),
        _f(g, "One-time tips: the first visit to the Collections, Family and Goals screens; a drag that misses; waiting "
              "for and failing at work; a couple not in the mood; the first pregnancy; that the game runs in real "
              "time; a confused family member; children and nursing mothers not working; a death that starts a new "
              "generation; college; the Flea Market, the furniture sale, the game store and the Special Upgrades the "
              "first time they open; a room that needs renovating; something in the way; the family lost with the "
              "Family Tree full.", C,
           "0x861..0x86D, 0x870..0x879: CCollectionScene / CFamilyTreeScene / CAchievementsScene::UpdateScene, "
           "CBehavior work / Confused / RunAwayFrom*, CVillager::StartEmbrace, CVillagerAI::AdvanceState, "
           "CVillagerState::ChanceOfPregnancy, CScrollingStoreScene::UpdateScene, CVillagerPlans::PlanToGo", sub=True),
        _f(g, "The Flea Market's tip says its goods change 3 times a day, and random tip 52 says several times a day. "
              "The code: in the unpatched game they change every 6 hours of real time (4 times a day); with the "
              "patcher's \"All 36 Flea Market goods\" option on (the default) every good is always on sale (see Flea Market).", C,
           "eTipFleaMarket 0x873 (CScrollingStoreScene::UpdateScene, category 0xF); stock MaybeUpdateRotatingItems "
           "0x4BA710 (spec 22)", sub=True),
        # ---- developer code
        _f(g, "Dead code, never a player action: the developers' debugger and editors. F5 (show the debugger), Up "
              "and Down (its pages), F6 (the waypoint editor: W, S), F7 (the light editor: + and -, L, D, S) and F4 "
              "(leave) are read only by code that nothing calls; the screen that lines up the people's pictures "
              "(the arrows, Esc and letter commands) is built but never opened; a test box for the day and night cycle "
              "and an end-of-game screen (any key) are never built. The patcher's own debugger test build (2026-07) was never shipped.", C,
           "CDebugger::HandleKeyDown / HandleKeyCharacter / Register: no caller; CWaypointEditor / CLightSourceEditor "
           "only through CDebugger; theMainScene::Debug is a bare ret; theAlignVillagerScene built at loading step 5 "
           "(theGame::GameUpdate) but no code sets scene 4; CDayNightCycleTestDlg, theGamewinScene, "
           "theAlignPetsScene: no constructor call; ENABLE_DEBUGGER_FEATURES off in every release (docs/discoveries.md "
           "2026-07-13)"),
        # ---- the patcher
        _f(g, "The patcher adds one key, R in the store, and no hidden click. Its Time Controls (every B201 and "
              "later build, when the Time Controls option is on) is a button on the Settings screen that opens its "
              "own window, where Enter or Esc close it. The Up to 28 Children, Family History and outfit picture "
              "additions add no input.", C,
           "runtime/native/b200time: button id 9 at x 30 (theOptionsDialog), dialog IDOK / IDCANCEL -> EndDialog; no "
           "key handling in runtime/native/b200time, b200kids, b200history or b200outfits; the key: "
           "runtime/native/b200refresh"),
        _f(g, f"R (a patcher key, option \"{OPTION_REFRESH}\", a cheat, on by default; after B204): in the store, "
              "R or Shift+R picks the store's random items again, the game's own way. On the Clothing and "
              "Hairstyles page: the 6 stock outfits (see Clothing and Hairstyles). On the Flea Market page: 5 new "
              "goods, always; with \"All 36 Flea Market goods\" on you won't see a change in the list (see the "
              "store). Nothing on any other page "
              "or screen, never On Sale, and nothing while a box (the buy box, the bank, a message, Redeem "
              "Credit) is open: each store box takes the keys first. The store has no text box, so typing never "
              "triggers it. Every other key, Esc included, is the game's own.", E,
           "vf2refresh_b200.dll replaces only CScrollingStoreScene's vtable slot 2 (HandleKey, found through RTTI: "
           "the function is shared by 5 scenes); typed characters reach it as HandleKey(5, char, 0); page = "
           "[scene+0D4h]; every store box: ldwDialog::DoModal(scene, false) -> SetModal, and "
           "ldwEventManager::HandleKey stops at a modal handler; all emulated (tests/test_b200_store_refresh.py)",
           sub=True),
    ]
    return out


def facts() -> list[Fact]:
    """Every line of the page, in GROUPS order."""
    out: list[Fact] = []
    add = out.append

    # ------------------------------------------------------------------ Time and ageing (spec section 1, 5)
    add(_f(TIME, "Clocks. Real time is your PC's clock: the game's speed does not change it, and it runs while the "
                 "game is paused and while it is closed. Game time runs with the game's speed and stops while the "
                 "game is paused: an hour of game time is 1 hour of real time at Normal speed, 2 hours at Slow, 30 "
                 "minutes at Fast, 12 minutes at 5x and 6 minutes at 10x. The game itself only ever sets Normal or "
                 "Pause; Slow, Fast, 5x and 10x come from the patcher's Time Controls.", C,
           "CGameTime::Seconds 0x468B00 = banked + (GetSecondsFromGameStart - anchor) / (speed / 10), run as linked: "
           "10,000 real s -> 10,000 game s at speed 10, 20,000 at 5, 5,000 at 20, 0 at 0; the age unit is "
           "60 x speed real s (AllVillagersTimeflowUpkeep 0x4C4DE3); speed values Slow 20, Normal 10, Fast 5, 5x 2, "
           "10x 1 (runtime/native/b200time/b200time_time.inc); GetSecondsFromGameStart 0x475830 = _time64 minus the "
           "save's start time"))
    add(_f(TIME, "Game time is kept by two clocks. The age clock counts age units, 10 minutes of game time each: "
                 "ageing and every need, health, salary and pregnancy rule run on it, and for the time the game was "
                 "closed it makes up only the capped catch-up (see time away). The game clock runs Random Events, "
                 "messes, the weather, interest, the Food Club, On Sale, the Maid and the Gardener, the dating and "
                 "college e-mails and the outfit restock; on loading it moves on by the whole time the game was "
                 "closed, at the speed the family was saved at (not at all when it was saved paused).", C,
           "CGameTime::SaveState 0x468AC0 / LoadState 0x468A20 keep the speed (+0x20), the anchor (+0x28) and the "
           "banked seconds (+0x2C) and nothing re-anchors them at load, so Seconds() counts the time closed; the "
           "age clock's catch-up caps at 0x4C4D29..0x4C4D8F"))
    add(_f(TIME, "Real time while the game runs: the 2-second upkeep step (it also runs while paused; house "
                 "malfunctions and the autosave ride on it) and the collectible rolls, 30 a second (not while "
                 "paused). Neither runs while the game is closed.", C,
           "theMainScene::UpdateScene 0x4A266E: ldwEventManager::GetSeconds 0x474600 + 2; CCollectableItem::Update "
           "per frame"))
    add(_f(TIME, "Pause stops the game clock completely: the clock keeps the time it had when paused, however long "
                 "the pause lasts, and carries on from there when unpaused.", E,
           "SetSpeed(999) 0x468B80 stores speed 0 and banks Seconds(); Seconds() 0x468B00 returns the banked "
           "value at any later real time (tests/test_game_mechanics_b200_exe.py)"))
    add(_f(TIME, "While paused nobody ages and none of the family's upkeep (hunger, health, salary, birthdays) is "
                 "processed, and the paused game time is never made up later. Food groups, symptoms, the baby "
                 "waiting time and collectibles on the floor keep counting down in real time while paused.", C,
           "spec 1: option >= 999 zeroes the accumulator every step (0x4C4D99)"))
    add(_f(TIME, "Ageing: a family member gains one age unit every 10 minutes of game time; 20 units make a year, "
                 "so a year takes 3 hours 20 minutes of game time (3 hours 20 minutes of real time at Normal speed, "
                 "20 minutes at 10x). It also carries on for the time the game is closed, up to the catch-up caps "
                 "(see time away).", C,
           "AllVillagersTimeflowUpkeep 0x4C4C30: units = real seconds / 60 / speed option (0x4C4DCF..0x4C4DE3)"))
    add(_f(TIME, "Time away (the game closed, not paused) is made up the next time the game runs; at Normal speed, in "
                 "real time away:", E,
           "AllVillagersTimeflowUpkeep 0x4C4D29..0x4C4D8F run as linked: 30,000 / 50,000 / 86,400 / 200,000 s "
           "away credit 30,000 / 31,000 / 31,000 / 86,400 s"))
    add(_f(TIME, "up to 31,000 seconds (8 hours 36 minutes 40 seconds) of real time away is made up in full;", E,
           sub=True))
    add(_f(TIME, "from 31,000 seconds up to and including 24 hours of real time away, 31,000 seconds are made up: 51 "
                 "age units, about 2.55 years;", E, sub=True))
    add(_f(TIME, "more than 24 hours of real time away, exactly 24 hours are made up: 144 age units, 7.2 years. The "
                 "rest of the time away is lost.", E, sub=True))
    add(_f(TIME, "At the other speeds (an age unit is 60 seconds of real time x the speed value): at Fast, up to "
                 "38,200 seconds of real time away is made up in full (up to 127 age units) and more than that "
                 "makes up 31,000 seconds (103 age units); at Slow, up to 23,800 seconds in full (19 age units) "
                 "and more than that 31,000 seconds (25 age units); at 5x and 10x, up to 31,000 seconds in full "
                 "(258 and 516 age units). At every speed more than 24 hours of real time away makes up 24 hours: "
                 "288 age units at Fast, 72 at Slow, 720 at 5x and 1,440 at 10x.", E,
           "0x4C4D58..0x4C4D8F run as linked at options 5, 20, 2, 1 (tests/test_game_mechanics_b200_exe.py): the "
           "trigger is 38,200 (0x9538) / 23,800 (0x5CF8) / 31,000, the value set is always 31,000 (0x7918); over "
           "86,400 -> 86,400; units = seconds / 60 / option", sub=True))
    add(_f(TIME, "A family saved paused makes up nothing.", E, "option 1009: accumulator 0 (emulated)", sub=True))
    add(_f(TIME, "Every age unit made up is then lived one by one, with its meals, health, salary and birthdays, as "
                 "if the game had been open.", E,
           "spec 2: AllVillagersRealtimePhysiologyAndProductivityUpkeep 0x4C4410 repeats until nobody is behind"))
    add(_f(TIME, "Day and night follow your PC's own clock.", C, "spec 1: CNight::GetTimeOfDay 0x482A30"))
    add(_f(TIME, "Ages: a baby until 5 years (the diaper events), a child until 14, then a teen or adult; a "
                 "partner for a baby from 18 until 55; old from 55.", C, "spec 5"))
    add(_f(TIME, "There is no maximum age in the code: old age (below) ends every life by 65 years plus the food "
                 f"groups counted, unless the \"{OPTION_MORTALITY}\" option is on.", E, "spec 4, 5"))
    add(_f(TIME, "A new baby is created at 2 years of age (40 age units).", C,
           "Impregnate 0x4BB920 -> SpawnSpecificPeep, age argument 0x28 (40 units, 20 per year)"))
    add(_f(TIME, "The store's Time Warp (Special Upgrades, $2,000) makes up 61 age units (10 hours 10 minutes of game "
                 "time) at once, all of it, at any speed, and caps the money it brings at $750. It moves every "
                 "real-time count on by 3,660 seconds x the speed value: 10 hours 10 minutes of real time at "
                 "Normal speed (the food groups, symptoms and the baby waiting time), 1 hour 1 minute at 10x.", C,
           "HandleUpgrade 0x48C2E0 case 0x112 on the purchase path HandleMouse -> HandlePurchaseItem: start time moved "
           "back 3,660 x option s, AllVillagersTimeflowUpkeep(true) (86,400 cap only), money capped at +750"))

    # ------------------------------------------------------------------ Hidden keys, clicks and cheats
    out.extend(_hidden_lines())

    # ------------------------------------------------------------------ Needs and upkeep (spec 2, 14)
    add(_f(NEEDS, "The family's needs are worked out once per age unit (every 10 minutes of game time) for everyone alive "
                  "and at home.", E, "spec 2"))
    add(_f(NEEDS, "Hunger rises by 5 every 4 age units (40 minutes of game time).", E, "spec 2: UpdateHungerState 0x4CC6A0"))
    add(_f(NEEDS, "Eating: every age unit (10 minutes of game time), a hungry family member (hunger over 50) eats 3 food and loses 3 hunger "
                  "when the house has food; with 50 food or less in the house a meal is missed half the time.", E,
           "spec 2: 0x4C4575"))
    add(_f(NEEDS, "A missed meal or an empty house: a 30% chance (30.03%) of losing 1 health (starvation).", E,
           "spec 2"))
    add(_f(NEEDS, "No food at all: 1 health lost each age unit (76% chance, sure every 6th unit, once an hour of game time); at 20 health or less a 31% chance "
                  "of 1 back every other unit.", E, "spec 2: 0x4C463C"))
    add(_f(NEEDS, "Waste: with 1,000 food or more, a hungry family member has a 76% chance of using 3 more food.",
           E, "spec 2: 0x4C460F"))
    add(_f(NEEDS, "The toilet: when the need reaches 90 it resets to 25-49.", E, "spec 2: 0x4C455A"))
    add(_f(NEEDS, "Energy changes every 2 age units (20 minutes of game time): -4 at night (8 PM to 5 AM by your PC's clock) with 10 or "
                  "more energy, +8 in the day (5:06 AM to 5 PM) with 70 or less; -1 each for happiness 10 or less, "
                  "health 25 or less, health 10 or less and hunger 90 or more; -3 when sick (at most -6 or +10).", C,
           "spec 2: UpdateEnergyState 0x4CBDC0"))
    add(_f(NEEDS, "Energy is only worked out for the last 12 units of a catch-up.", E, "spec 2: 0x4C450F"))
    add(_f(NEEDS, "Happiness moves every 3 age units (30 minutes of game time) by up to 5 points, towards a mood made of: food groups, "
                  "money (worse below $1,000 and $100, better above $8,000, $50,000 and $100,000), food in the "
                  "house (worse at 250 and 50 or less), sickness, messes on the floor (better with none, worse at 10 "
                  "and 20), house renovations, placed furniture (up to 30), owned items the person likes, the "
                  "family's size, hunger 90 or more and health 10 or less.", C,
           "spec 2: UpdateHappinessState 0x4CBE90"))
    add(_f(NEEDS, "Food groups: Grains, Dairy, Meats and Fruits and Veggies. A grocery bag put in the kitchen, or a "
                  "Food Club delivery, gives that group to everyone at home for 24 hours of real time (it runs out while "
                  "paused and while the game is closed too).", C,
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
    add(_f(HEALTH, "Recovery: every age unit (10 minutes of game time), a fed family member who is not sick has a 50% chance of 1 health "
                   "back (10% from age 55), up to 100.", E, "spec 2: 0x4C470A"))
    add(_f(HEALTH, "Every 3 age units (30 minutes of game time) health also moves by up to 5: -1 for happiness 10 or less, -1 for hunger 90 or "
                   "more and another at 100, -1 with exactly 1 food group, +1 with exactly 4, and when sick -1 with "
                   "a 15% chance (40% with an infection).", C, "spec 2: UpdateHealthState 0x4CC5F0"))
    add(_f(HEALTH, "Being sick: every age unit (10 minutes of game time) a 61% chance of losing 1 health; no recovery, less energy and "
                   "happiness, and less career progress.", E, "spec 2: 0x4C46D0; spec 3"))
    add(_f(HEALTH, "Catching something: every 3 age units (30 minutes of game time) a healthy family member is checked:", E,
           "spec 3: UpdateDisease 0x4CBBE0 (t_dis)"))
    add(_f(HEALTH, "1.007% in all (a symptom 0.906%, a mild infection 0.071%, a serious one 0.030%);", E, sub=True))
    add(_f(HEALTH, "2.518% when someone at home has a catching symptom;", E, sub=True))
    add(_f(HEALTH, "0.806% with exactly 3 food groups counted, and 0.503% with 5 (a family member without a career "
                   "who has all four).", E, "0x4CBD2E: base 10, -2 at 3 groups, -5 at 5", sub=True))
    add(_f(HEALTH, "Symptoms: hiccups, sore throat, stomach, headache, cough, skin rash and runny nose. Each lasts "
                   "6 to 17 hours of real time (it runs out while paused and while the game is closed too).", E,
           "spec 3: SetSymptom 0x4CBBA0, expiry = GetSecondsFromGameStart + 6..17 h"))
    add(_f(HEALTH, "A mild infection adds a symptom half the time when there is none and ends with a 3% chance per "
                   "check; a serious one adds symptoms (up to 2) and ends with a 1.2% chance per check.", E, "spec 3"))
    add(_f(HEALTH, "The medicines (see Food and Medicine): six each cure one symptom, Penicillin ends the mild "
                   "infection and Vancomycin both; Baby Boost raises fertility and cures nothing; the Doctor "
                   "Consultation (the stethoscope) only opens the Diagnosis window and cures nothing.", C,
           "HandleMouseDown 0x49EE90 cases 0x18..0x21"))
    add(_f(HEALTH, "Deaths from illness (health reaching 0 while sick) and from starvation (health reaching 0 from "
                   "missed meals).", C, "spec 4"))
    add(_f(HEALTH, "Deaths by work accident or act of nature never happen: the game has the two causes (3 and 4), "
                   "but the only code that sets them is never called and is left out of the game, and every other "
                   "health change names cause 0, 1 or 2.", C,
           "cause enum 3 / 4; MakeRandomVillagersInjured / MakeRandomVillagersDead have no callers and are not linked into B200; all 20 AdjustHealth / SetHealth call sites pass cause -1, 0, 1 or 2"))
    add(_f(HEALTH, "A family member who has died stays in the house for 240 age units after their last upkeep (40 hours "
                   "of game time; this count is not capped, so the time the game is closed counts in full, at "
                   "the speed the family was saved at), then is "
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
                      "50 down to 0.1% from 69: the formula below without the mother-over-50 cutoff, capped by the "
                      "older parent's age at 10% at 50, 1 point less each year to 1% at 59, 0.9% at 60, 0.1 point "
                      "less each year to 0.1% at 68 and 0.1% from 69, and never under 0.1%. A failed try the spouses "
                      "start themselves sets no waiting time for such a couple.", C,
           "work/patch_mobile_furniture_pack.py: ChanceOfPregnancy hook -> VF2RollOlderPregnancy (GetRandom(1000) < chance in tenths), VF2OlderPregnancyCapTenths, VF2StockPregnancyChanceWithoutCutoff; VF2StoreTryForBabyCooldownMaybe at ProcessCurrentPlan+0xA45"))
    add(_f(PREGNANCY, "Twins and triplets: twins 5.25%, triplets 1.75%, one baby 93%; each parent's fertility over 85 "
                      "adds its excess, in points, to both rolls. Twins need 2 free child places, triplets 3.", C,
           "spec 6: Impregnate 0x4BB920"))
    add(_f(PREGNANCY, "A family has room for 6 children per generation.", C, "spec 10: AddOffspring"))
    add(_f(PREGNANCY, "A pregnancy lasts 21 age units: 3 hours 30 minutes of game time (3 hours 30 minutes of real time at "
                      "Normal speed).", C, "spec 6: 0x4C47D8"))
    add(_f(PREGNANCY, "The baby waiting time, as you play it: however long it is, dropping one spouse on the other "
                      "while more than 1 hour of it is left cuts it to 55 minutes from that moment, so once you try "
                      "you never wait more than 55 minutes. It is real time on your PC's clock: it runs while the game "
                      "is paused or closed, the game's speed does not change it, and the Time Warp moves it on by its "
                      "10 hours 10 minutes.", C,
           "HandleDropOnVillager 0x49E773..0x49E78E: wait > now + 3,600 -> wait = now + 3,300; now = "
           "ldwGameState::GetSecondsFromGameStart 0x475830 (_time64 minus the save's start time) at every writer and "
           "the reader"))
    add(_f(PREGNANCY, "After a birth the game sets a waiting time of 10 minutes (both parents' desire 80 or more) to "
                      "4 hours 10 minutes (desire 0) of real time before the next try.", C,
           "spec 6: gs+0x25AE0 writer 0x4C4886, now + 600 x product"))
    add(_f(PREGNANCY, "What that waiting time holds back: dropping one spouse on the other. While it runs, the "
                      "spouse shakes their head with \"It is too soon to try to make a baby again.\" (and the wait is "
                      "cut as above). When it is over, the drop starts a try.", C,
           "the only reader of gs+0x25AE0 is theMainScene::HandleDropOnVillager 0x49E726 / 0x49E778"))
    add(_f(PREGNANCY, "A try from that drop: a success sets no wait, everyone celebrates and each spouse gets 300 "
                      "mood points and happiness +5 for every 20 points of their desire; a failure sets a wait of "
                      "(5 - mother's desire / 20) x (5 - father's desire / 20) x 30 minutes of real time (30 "
                      "minutes with both 80 or more, up to 12 hours 30 minutes with both under 20, cut to 55 minutes "
                      "by the next drop), with 50 mood points and 3 happiness off each spouse. A failed try the "
                      "spouses start themselves sets 20 minutes of real time.",
           C, "theMainScene::TryToMakeBaby 0x4A23C0: ChanceOfPregnancy, Impregnate, wait = now + product x 0x708; "
              "ProcessCurrentPlan+0xA45 writes now + 0x4B0"))

    # ------------------------------------------------------------------ Careers (spec 7)
    add(_f(CAREERS_GROUP, "A career is picked at random from 132 (38 in the kitchen, 57 in the office, 37 in the "
                          "workshop) and starts at level 0.", C, "spec 7: CVillagerSkills::Reset 0x4CB410"))
    add(_f(CAREERS_GROUP, "Levels: " + ", ".join(LEVELS) + ".", C, "spec 7"))
    add(_f(CAREERS_GROUP, "Salary: paid every 3 age units (30 minutes of game time), a quarter of the career's salary each "
                          "time (half the salary per hour of game time), whether or not the person is at work.", E, "spec 2, 7: 0x4C452E"))
    add(_f(CAREERS_GROUP, "Each piece of work succeeds with a chance of 56.25% for a Beginner rising to 100% for a "
                          "Master; a success pays 6% of the salary and adds progress (more in better-equipped rooms, "
                          "less at higher levels). 3,000 progress is a promotion: a new salary and a celebration.", C,
           "spec 7: AdvanceCareer"))
    add(_f(CAREERS_GROUP, "Choosing to work: each time a family member picks what to do next, the pick is a weighted "
                          "draw among everything they can do then, and the office, kitchen and workshop work are "
                          "among them only by day and in the evening. Their starting weights are 469 (office), "
                          "553 (kitchen) and 478 (workshop), each kept between 50 and 45,000; a weight counts 3 "
                          "times when a need calls for it or its like is held (the Likes text names them "
                          "\"carbs\", \"cooking\" and \"computers\") and a quarter when that like is a "
                          "dislike.", C,
           "CVillagerAI::DecideWhatToDo (GetRandom(total weight)); InitAI run as linked: behaviours 0x2C / 0x47 / 0x4B weights 469 / 553 / 478, min 50, max 45,000, likes 82 / 39 / 81"))
    add(_f(CAREERS_GROUP, "During a catch-up, for each age unit made up (10 minutes of game time) while a family member is "
                          "more than 2 age units behind, a family member with a career who is not sick and not pregnant gets one "
                          "try for every 400 of their work weight (1 at the starting weights, 112 at 45,000), each "
                          "a 1 in 6 chance (16.67%) of a piece of work: its progress and its pay, as above, with no "
                          "success roll.", C,
           "AllVillagersRealtimePhysiologyAndProductivityUpkeep 0x4C4A8F..0x4C4AD6 -> RealtimeWorkDone 0x4C3DB0: weight / 400, GetRandom(6) == 0 -> AdvanceCareer(villager, pay true, promote false)"))
    add(_f(CAREERS_GROUP, "Every career's pay, per hour of game time (per real hour at Normal speed), at each level from "
                          "Beginner to Master:", C,
           "careers.tsv"))
    out.extend(_career_lines())

    # ------------------------------------------------------------------ Money and interest (spec 8)
    add(_f(MONEY, "A new family starts with $50 to $189.", C, "spec 10: theGameState init rand(140)"))
    add(_f(MONEY, "Money never goes below $0 or above $4,000,000,000.", C, "spec 8: CMoney::Adjust 0x4818B0"))
    add(_f(MONEY, "Interest: 10% of the money (the starting rate) each game day (24 hours of game time on the game clock). After a gap only 2 "
                  "days are paid, however many have passed; the rest are skipped.", E,
           "UpdateInterest 0x481D80 run as linked: 1,000 at 0.10 gains 100 after 1 day and 200 after 2, 3 or 10"))
    add(_f(MONEY, "Interest is paid when it is next checked: every 3 age units (30 minutes of game time, the happiness check), when the "
                  "bank window opens, when the store is clicked, at the Time Warp, at the daily e-mail, when a new "
                  "family's first adult is made, and when 15 of the Random Events look at the money.", C,
           "callers of UpdateInterest 0x481D80: UpdateHappinessState, CBankingDlg, CScrollingStoreScene::HandleMouse, "
           "HandleUpgrade, CDailyEmail::Show, CAdoptionScene::GeneratePeepCandidate and 15 event CanFire / CalcAward"))
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
    add(_f(MONEY, WITH_PATCHER + "Brokerage Account: buying it raises interest to 11% a game day (24 hours of game time). Buying it again sets "
                  "interest to 1%; each purchase after that adds 2 points (3%, 5%, 7%, 9%) until 11% again.", E,
           "HandlePurchaseItem 0x48C110 -> 0x4B8B50 run as linked from 0.10: 0.11, 0.01, 0.03, 0.05, 0.07, 0.09, "
           "0.11"))
    add(_f(MONEY, "Food Club, Health Plan, Lucky Rock and Lotto Ticket: see Special Upgrades.", C,
           "HandleUpgrade / 0x4B8B50"))

    # ------------------------------------------------------------------ Leaving home (spec 9)
    add(_f(LEAVING, "College: a family member without a career leaves for college on turning 19. Children born in "
                    "the house have no career, so every child not chosen as the heir leaves at 19.", C,
           "spec 9: 0x4C4DF4"))
    add(_f(LEAVING, "The Talent Scout (a Popup Event, a child at home): yes, the child leaves and the family gets "
                    "$500; no, nothing happens.", E, "spec 9: event 83"))
    add(_f(LEAVING, "Boarding School (a Service, $1,500): the chosen child leaves home at once, with the message "
                    "\"... has been sent away to school!\".", C,
           "HandleUpgrade 0x48C2E0 case 0x10B: SetLeftHome on gs+0x25CC4, message 0x4C8"))
    add(_f(LEAVING, "The college e-mails come from those who left; they count one year away for every 12,000 "
                    "game seconds (3 hours 20 minutes of game time on the game clock).", C, "spec 9: YearsAwayFromHome"))

    # ------------------------------------------------------------------ Dating, marriage, next generation (spec 10)
    add(_f(DATING, "The dating e-mail first comes 3 minutes of game time into a new game or a new generation. After a date "
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
    add(_f(DATING, "The heir is chosen from every child of the current generation still listed in the family tree, "
                   "each shown as an adult. A child is taken off that list only by their death, so a child who "
                   "has left home is still offered.", C,
           "CAdoptionScene::CreateNextGenerationCandidates 0x4034A0: every offspring id != -1 -> ClonePeepAsAdult; CFamilyTree::ReportDeath 0x457A50 is the only writer of -1 to an offspring id"))
    add(_f(DATING, f"Patcher option \"{OPTION_PREGNANCIES}\", on: the next generation is also offered when the "
                   "oldest family member reaches 60 with a child alive. Off: only as above.", C,
           "spec 10: VF2CanStartNextGenerationAtOlderAge"))
    add(_f(DATING, "The Little Visitor (a Popup Event, with room for a child): yes, a 3-year-old boy or girl joins "
                   "the family.", E, "spec 10: events 64 / 65"))

    # ------------------------------------------------------------------ Random Events (spec 11)
    add(_f(EVENTS, "Every hour of game time (1 hour of real time at Normal speed; the game clock stops while paused), when "
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
    add(_f(EVENTS, "The money each \"money check\" event needs before it can happen (the family's money at the "
                   "time):", C, "CanFire of each event"))
    for text, label in (
            ("the Scratch-Off Lottery Ticket: more than $21;", E),
            ("the EPA Visit: $1,312 or more;", E),
            ("Oh So Clever, Office Collection, Overdue Book and the Professional Association Fee: $750 or more;", E),
            ("the Infringement Complaint and the Tax Audit fee: $750 or more, and then half the time (49.95%);", E),
            ("the Aesthetic Society, the Neighborhood Children's Association and the Community Association: "
             "$750 or more;", C),
            ("Professional Career Training: more than $255; the Trainer: more than $5;", C),
            ("the Tax Audit gift: no money check;", E),
            ("the Electric Bill Correction: no money check.", C)):
        add(_f(EVENTS, text, label, "CanFire run as linked (E) or read (C)", sub=True))

    # ------------------------------------------------------------------ Weather (spec 12)
    add(_f(WEATHER, "Weather names (the code's type number and enum name): Normal 0 eWeather_Sunny, Sunny 1 "
                    "eWeather_Cloudy, Raining 2 eWeather_Raining, Stormy 3 eWeather_Stormy, Foggy 4 "
                    "eWeather_Foggy, Snowing 5 eWeather_Snowing.", C, "CodeView enum EWeather, Weather.obj"))
    add(_f(WEATHER, "Kinds: Normal (the plain sky: nothing is drawn over the house), Sunny (a grey tint by day, with sun beams), "
                    "Raining, Stormy (rain and lightning), Foggy and Snowing.", C,
           "spec 12: CWeather::Draw (type 0 draws nothing; type 1 tint 0.2 by day and CSunBeam)"))
    add(_f(WEATHER, "After a spell the weather always returns to Normal; after Normal the next kind is picked "
                    "evenly from the other five (never Sunny at night). The weather stands still while paused.", C,
           "spec 12: CWeather::Update 0x4CD110"))
    add(_f(WEATHER, "Normal weather lasts 15 to 40 minutes of game time; any other kind, Sunny too, 6 to 12.", C,
           "spec 12: SetCurrent 0x4CCF20"))
    add(_f(WEATHER, "Heavy rain or a storm sends everyone outside to take cover.", C, "spec 12"))
    add(_f(WEATHER, "The collectibles of the rain-only spawn areas appear only in Raining or Stormy weather.", C,
           "spec 12, 15"))
    add(_f(WEATHER, "When the game starts (a new family, a change of player, loading a family or starting over) the "
                    "weather is Normal; the weather is not saved. With a 20% chance (20.02%) a change follows 30 "
                    "seconds of game time later, to the kind your PC clock's minute gives (its remainder after "
                    "dividing by 6, in the order of the names above): a 4 or 5 moves on one kind half the time "
                    "(50.05%; after Snowing comes Normal), and a Normal result moves on to Sunny.", C,
           "CWeather::Reset, called only by theGameState::Init; CWeather::Random(previous)"))

    # ------------------------------------------------------------------ Messes and malfunctions (spec 13)
    add(_f(MESSES, "Messes appear every 5 hours of game time (2.5 hours with 4 or more in the family), not "
                   "while paused, one roll each: under 30 a weed, under 55 a sock, under 80 a candy wrapper, "
                   "else a dirt smudge; with no cobwebs about, a roll under 20 makes nothing. A Gardener stops the "
                   "weeds and a Maid the rest; with both, no messes.", C,
           "spec 13: CCollectableItem::Update 0x44DE90"))
    add(_f(MESSES, "Messes on the floor change the family's happiness (see Needs and upkeep).", C, "spec 13"))
    add(_f(MESSES, "House malfunctions: every 2 seconds of real time a 1 in 800 chance (about every 27 minutes of real "
                   "time, at any speed), from 6 minutes of real time after the family was started and only while no other malfunction is out. They roll "
                   "while the game is paused too.", E,
           "UpdateScene 2-second step 0x4A266E..0x4A28F9 run as linked at speed option 10 and 1009: both reach "
           "GetRandom(800) and the pick GetRandom(14); the step's clock is the wall clock (0x474600)"))
    add(_f(MESSES, "Which one: one of 14, evenly: a router offline, a dryer lint fire (needs a dryer), leaks in the "
                   "north bathroom's shower, toilet and sink (need that renovation), ants (3 of the 14), and six "
                   "other breakdowns. A permanent fix stops its own kind; a pick the house cannot have makes "
                   "nothing.", C, "spec 13: 0x4A28F4"))
    add(_f(MESSES, "The six other breakdowns: the toilet, the two bathroom sinks, the kitchen sink, the stove and "
                   "the shower. When the kitchen trash holds more than 5 (it is full at 20) the pick is one of 17 "
                   "instead, and the 3 added picks are ants too (6 of the 17).", C,
           "spec 13: picks 0 toilet, 1 / 2 bathroom sinks, 3 router, 4 kitchen sink, 5 stove, 6 shower, 7 dryer lint fire, 8..10 north bathroom 0x49 / 0x48 / 0x4A, 11..13 ants; GetRandom(17) with gs+0x28 > 5, 14..16 ants"))

    # ------------------------------------------------------------------ Collectibles (spec 15)
    add(_f(COLLECTIBLES, "The game rolls for a collectible 30 times a second of real time while it runs (not paused, and at "
                         "any speed): about one every 73 seconds of real time, every 37 with the Lucky Rock.", C,
           "spec 15: CCollectableItem::Update, 3 in 6,600 (3 in 3,300)"))
    add(_f(COLLECTIBLES, "Rarity: rare 4%, uncommon 13%, common 83%; with the Lucky Rock 8%, 26% and 66%. The same "
                         "item never appears twice at once.", C, "spec 15: CCollectableItem::Add 0x44CA10"))
    add(_f(COLLECTIBLES, "A collectible lasts 120 seconds of real time from when it appears (the game clock's speed and "
                         "pausing do not change that), then vanishes unless a family member has picked it up. At most "
                         "2 are out at once.", C,
           "CCollectableItem::Add: expiry +0x354 = GetSecondsFromGameStart + 0x78; Update: items outside the mess ids "
           "0x73..0x85 past their expiry -> Remove; Add looks for a free slot among 2 (+0x34C, stride 0x1C)"))
    add(_f(COLLECTIBLES, "Where: the game picks one of its collectible spawn areas evenly, then a free spot in it, then "
                         "one of that area's collection's 4 items of the rarity rolled. The insects' area is taken only "
                         "in Raining or Stormy weather (the roll is made again otherwise). An event that makes a "
                         "collectible appear never picks a fossil area without the Rock Hound Certificate, and always "
                         "gives a rare item.", C,
           "CCollectableItem::Add: GetRandom(area count +0x5DC); area base 0x4F only with CWeather 2 or 3; forced "
           "(bool argument) and base 0x67 / 0x86 without HaveUpgrade(0x10A) -> re-roll; forced -> +8 (rare); "
           "base + GetRandom(4) (+4 uncommon, +8 rare); up to 1,000 IsValidSpawnPos tries"))
    add(_f(COLLECTIBLES, "The 5 collections, 12 items each (4 common, 4 uncommon, 4 rare), 60 in all, as the Collections "
                         "screen's 5 pages and the collection cabinet count them: insects, leaves and nuts, the Raptor "
                         "skeleton's fossil pieces, the Pterodactyl skeleton's fossil pieces and bottle caps.", C,
           "items 0x4F..0x72 and 0x86..0x9D (CCollectionScene::HandleMouse: page item < 0x24 -> 0x4F + i, else "
           "0x62 + i; strings eSayCommonInsects..eSayRareBottleCaps 0x748..0x753)"))
    add(_f(COLLECTIBLES, "A full collection completes its goal: insects, nuts and twigs, Raptor hunter, Pterodactyl "
                         "hunter and bottle caps; all five complete Master collector. Selling collectibles online counts "
                         "towards six more goals (5 and 15 of each rarity). The coins each goal awards have not been "
                         "traced.", C,
           "goal strings eString_AchievementInsectsDesc 0x323 .. eString_AchievementSuperDuperSellerDesc 0x339; "
           "eString_GoalAward 0x14 \"You have been awarded %d coins!\""))
    add(_f(COLLECTIBLES, "The Lucky Rock doubles the roll (about one every 37 seconds of real time) and the rare and "
                         "uncommon odds; The Mysterious Collector event buys the whole collection back (see Random "
                         "Events).", C, "CCollectableItem::Update GetRandom(3,300 / 6,600) < 3 with +0x8A8"))

    # ------------------------------------------------------------------ The store (spec 16, 23)
    out.extend(_store_lines())

    # ------------------------------------------------------------------ Chance and timer index (spec 17, 18)
    add(_f(INDEX, "Every chance on this page is exact: the game rolls rand(N) and every value is counted, so "
                  "\"30% (30.03%)\" means 9,840 of the game's 32,768 equally likely values.", C, "spec header"))
    add(_f(INDEX, "Chances, all shown above:", C, "spec 18"))
    for text in ("a malfunction 1 in 800 every 2 seconds of real time, then 1 of 14;",
                 "a Random Event's kind: Email Event 66%, Popup Event 34%, then 1 among those that can happen;",
                 "a missed meal 50% (50 food or less), starvation 30.03%, waste 76%, no food 76%;",
                 "illness per check 1.007% (2.518% with a catching housemate), losing health while sick 61%, "
                 "recovery 50% (10% from 55);",
                 "an infection ending 3% (mild) or 1.2% (serious) per check, a symptom lasting 6 to 17 hours of real time;",
                 "old age 10% per year over, pregnancy by the table, twins 5.25%, triplets 1.75%;",
                 "work success 56.25% to 100%, a career from 132;",
                 "weather: the next kind 1 in 5, Normal 15 to 40 minutes of game time, Sunny and the others 6 to 12;",
                 "a collectible 3 in 6,600 per frame (3 in 3,300 with the Lucky Rock), rare 4%, uncommon 13%;",
                 "a mess: under 30 of 100 a weed, under 55 a sock, under 80 a wrapper, else a smudge;",
                 "the Lotto Ticket: $50,000 4 in 32,768, $25,000 8, $5,000 80, $1,000 800, $750 2,000, a grocery bag "
                 "18.40% (with a free tray place);",
                 "the Imported Candy 1 of 5 and the Dirty Candy 1 of 4, evenly; the Energy Drink, Chamomile Drink and "
                 "Sleeping Pills 15% / 85%, the Mega Chamomile Extract 75% / 25%."):
        add(_f(INDEX, text, C, sub=True))
    add(_f(INDEX, "The other rolls the game makes change no need: how long each step of an action lasts, which way "
                  "it faces, its animation, pose and sound, e-mail wording, names and looks. What each action "
                  "gives is in the Actions group.", C,
           "spec 18: 4,431 behaviour sites; every conditional branch of the 63 listed actions read"))
    add(_f(INDEX, "Timers, each with its clock (game time stops while paused and is real time at Normal speed; "
                  "real time runs while paused and while the game is closed; the game clock also moves on by the "
                  "time the game was closed, the age clock only by the capped catch-up):", C,
           "spec 17, 25"))
    for text, label in (
            ("upkeep: every 2 seconds of real time, also while paused;", C),
            ("one age unit: 10 minutes of game time (the age clock; paused time is discarded);", C),
            ("a pregnancy: 3 hours 30 minutes of game time (21 age units);", C),
            ("a symptom: 6 to 17 hours of real time;", C),
            ("a food group: 24 hours of real time;", C),
            ("interest and the Food Club: each game day (24 hours of game time), interest at most 2 days at once;", E),
            ("a Random Event: every hour of game time;", C),
            ("the dating e-mail: 3 minutes of game time, then 5 minutes per date plus 10 per year over 26;", C),
            ("the Maid and the Gardener: every hour of game time, in the day by your PC's clock;", C),
            ("messes: every 5 hours of game time, 2.5 with 4 or more in the family;", C),
            ("a collectible: about every 73 seconds of real time (37 with the Lucky Rock), not while paused;", C),
            ("a house malfunction: about every 27 minutes of real time, also while paused;", E),
            ("the autosave: every 2 minutes (real time), also while paused, to the same save file a quit "
             "writes; the same in the unpatched game;", E),
            ("a weather spell: Normal 15 to 40 minutes of game time before the next spell, Sunny and the others 6 to 12;", C),
            ("On Sale: every 24 hours of game time;", C),
            ("the Flea Market, with the patcher: never changes (with its option \"All 36 Flea Market goods\" off, as in the unpatched game);", E),
            ("the Flea Market, unpatched game: every 6 hours of real time;", E),
            ("a body removed: 240 age units after death (40 hours of game time), the time closed counted in full;", C),
            ("the baby waiting time: 10 minutes to 12 hours 30 minutes of real time, cut to 55 minutes by a drop;", C),
            ("time away made up: at most 31,000 seconds of real time at Normal speed, or 24 hours when more than 24 "
             "hours away.", E)):
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
    ("My Weather Machine (Email Event, Normal or Sunny weather): rain, snow or fog, a third each.", E),
    ("An extra hammock (Email Event): everyone runs to the yard (the spot x 750 to 834, y 184 to 240); nothing else "
     "happens.", C),
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
    ("Small Package, Medium Brown Box, Sealed Green Bag (Popup Events, someone at home and room in the tray): yes, the "
     "Small Package one of the 6 medicines (Throat Lozenges, Peptic Syrup, Analgesic/Anti-inflammatory, Antitussive "
     "Syrup, Cortisone Cream, Antihistamine), 1 in 6 each; the Medium Brown Box one of the 4 groceries, 25% each; "
     "the Sealed Green Bag one of the 4 organics, 25% each.", C),
    ("A Tiny White Box (Popup Event): yes, a third of the food is lost.", E),
    ("Scratch-Off Lottery Ticket (Popup Event): yes, -$20 and a 33% chance of winning $0 to $90 (in $10 steps).", E),
    ("The Wrong Address (Popup Event): yes, -$100 and a Blue Children's Bed (50.05%) or a Pink Children's Bed "
     "(49.95%), into storage.", C),
    ("The Delivery Truck (Popup Event): yes, a Wall Painting into storage: the $4,150 one 33.03%, the $350 one 33.03%, "
     "the $450 one 33.94%; no, +$0 to +$140 (in $20 steps).", C),
    ("Talent Scout (Popup Event, a child): yes, the child leaves home and the family gets $500.", E),
    ("Beauty Contest (Popup Event, a child): yes, -$10 and a 33% chance of winning $100.", E),
    ("Landscaping -$20, the weeds gone; Housekeeping -$20, the socks, wrappers and smudges gone; Total House Care "
     "-$50, all of them gone (Popup Events).", E),
    ("The Mysterious Collector (Popup Event, someone at home and an item collected on either of two of the "
     "collection pages): yes, every collectible collected is sold, +$20 for each common, +$30 for each uncommon "
     "and +$100 for each rare across all five pages, and the collections and the collection goals start again "
     "from nothing.", C),
    ("Water Pressure Surge (Popup Event): no brings five leaks.", E),
    ("Professional Career Training (Popup Event): yes, -$250 and a promotion.", E),
    ("The Trainer (Popup Event): yes, -$5 and all the food is lost.", E),
    ("The Cooking Class (Popup Event): yes, a cooking mess in the kitchen.", E),
    ("The Power Failure (Popup Event): the power goes out. Throw out the food: the food store is reset. Take a chance: no one ill "
     "70.8%, one family member with a stomach upset 20.8%, two 8.3%.", E),
    ("Career Change Counselor (Popup Event): yes, a new random career at level 0.", E),
    ("The Rare Bird (Popup Event): yes, -$15 to -$85 (in $10 steps); everyone runs to the yard (the spot x 174 to 240, "
     "y 269 to 309) and celebrates.", C),
    ("School Fund-raiser (Popup Event): yes, -$25 and +100 food.", E),
)


# Every furniture item of the store's furniture tabs, B200 core (catalog run as linked: GetCategoryItemCount 0x46B6D0 /
# GetCategoryItem 0x46B210, GetPrice 0x46B9F0, GetLockGenerationLevel; names from the item's short description).
# (id, name, price, generation lock, store tabs, added by the patcher).  An item on several tabs is listed once, under
# its first tab in the store menu's order; "added" = not on any furniture tab of the stock exe (sha256 1582d9e8).
FURNITURE_ITEMS = (
    (0x1f2, 'Classic TV', 150, 0, ('General Appliances', 'Living Room'), False),
    (0x1ae, 'Basic Charcoal Grill', 175, 0, ('General Appliances', 'Outdoors'), False),
    (0x1ea, 'Bathroom Scale', 130, 0, ('General Appliances', 'Accessories'), False),
    (0x1cf, 'Drying rack', 80, 0, ('General Appliances', 'Accessories'), False),
    (0x200, 'Desk Lamp', 150, 0, ('General Appliances', 'Accessories'), False),
    (0x1ad, 'Outdoor Grill', 650, 2, ('General Appliances', 'Outdoors'), False),
    (0x1f4, 'Antique Radio', 850, 2, ('General Appliances', 'Accessories'), False),
    (0x203, 'Floor Lamp', 450, 2, ('General Appliances', 'Accessories'), False),
    (0x207, 'MP3 Player and Speakers', 350, 2, ('General Appliances', 'Accessories'), False),
    (0x1df, 'Automatic Clothes Washer', 950, 3, ('General Appliances', 'Accessories'), False),
    (0x1cb, 'Laundry Dryer', 650, 3, ('General Appliances', 'Accessories'), False),
    (0x1f3, 'Flat Screen TV', 5000, 3, ('General Appliances', 'Living Room'), False),
    (0x1b0, 'Basic Gas Grill', 750, 3, ('General Appliances', 'Outdoors'), False),
    (0x1cd, 'Ironing Set', 250, 3, ('General Appliances', 'Accessories'), False),
    (0x1af, 'Deluxe Gas Grill', 4500, 5, ('General Appliances', 'Outdoors'), False),
    (0x324, 'Large Flat Screen TV', 6500, 12, ('General Appliances',), True),
    (0x325, 'Small Flat Screen TV', 4250, 12, ('General Appliances',), True),
    (0x326, "Father's Favorite TV", 5250, 12, ('General Appliances',), True),
    (0x1c3, 'Used Couch', 45, 0, ('Living Room',), False),
    (0x1c4, 'Used Couch', 75, 0, ('Living Room',), False),
    (0x1c5, 'Used Couch', 55, 0, ('Living Room',), False),
    (0x1c2, 'Usable Couch', 45, 0, ('Living Room',), False),
    (0x1d6, 'Second Hand Loveseat', 99, 0, ('Living Room',), False),
    (0x30d, 'Invisible 3-Seater Couch', 45, 0, ('Living Room',), True),
    (0x30e, 'Invisible 2-Seater Loveseat', 99, 0, ('Living Room',), True),
    (0x30f, 'Invisible Single Couch', 1415, 0, ('Living Room',), True),
    (0x310, 'Invisible Beanbag Chair', 250, 0, ('Living Room',), True),
    (0x311, 'Invisible Large Bookshelf', 2450, 0, ('Living Room',), True),
    (0x312, 'Invisible Thin Bookshelf', 450, 0, ('Living Room',), True),
    (0x313, 'Invisible Small Square Bookshelf', 1250, 0, ('Living Room',), True),
    (0x1fa, 'Blue Beanbag Chair', 250, 2, ('Living Room',), False),
    (0x1fb, 'Brown Beanbag Chair', 250, 2, ('Living Room',), False),
    (0x1fc, 'Green Beanbag Chair', 250, 2, ('Living Room',), False),
    (0x1fd, 'Orange Beanbag Chair', 350, 2, ('Living Room',), False),
    (0x1fe, 'Red Beanbag Chair', 300, 2, ('Living Room',), False),
    (0x1f7, 'Small Birch Book Case', 450, 2, ('Living Room',), False),
    (0x226, 'House Plant', 165, 2, ('Living Room', 'Accessories'), False),
    (0x22c, 'House Plant', 90, 2, ('Living Room', 'Accessories'), False),
    (0x233, 'House Plant', 280, 2, ('Living Room', 'Accessories'), False),
    (0x237, 'House Plant', 75, 2, ('Living Room', 'Accessories'), False),
    (0x238, 'House Plant', 180, 2, ('Living Room', 'Accessories'), False),
    (0x270, 'Orange Couch', 1525, 3, ('Living Room',), False),
    (0x275, 'Orange Sofa', 980, 3, ('Living Room',), False),
    (0x27a, 'Orange Bookshelf', 1095, 3, ('Living Room', 'Dining Room', 'Bedroom'), False),
    (0x27f, 'Orange Coffee Table', 450, 3, ('Living Room',), False),
    (0x28d, 'Orange Credenza', 2115, 3, ('Living Room', 'Dining Room'), False),
    (0x29c, 'Modern Orange Rug', 895, 3, ('Living Room', 'Dining Room', 'Bedroom'), False),
    (0x1bd, 'Large Quality Couch', 750, 3, ('Living Room',), False),
    (0x1be, 'Large Quality Couch', 700, 3, ('Living Room',), False),
    (0x1bf, 'Large Quality Couch', 1800, 3, ('Living Room',), False),
    (0x1c0, 'Large Sturdy Couch', 850, 3, ('Living Room',), False),
    (0x1c1, 'Large Quality Couch', 225, 3, ('Living Room',), False),
    (0x1d4, 'Tan Loveseat', 750, 3, ('Living Room',), False),
    (0x1d3, 'White Loveseat', 1150, 3, ('Living Room',), False),
    (0x1d5, 'Brown Loveseat', 750, 3, ('Living Room',), False),
    (0x1d2, "Kids' Sofa", 2150, 3, ('Living Room',), False),
    (0x1c7, 'Wide Cabinet', 450, 3, ('Living Room', 'Dining Room', 'Bedroom'), False),
    (0x1e6, 'Small Sepia Oval Rug', 1550, 3, ('Living Room',), False),
    (0x1e7, 'Small Lapis Oval Rug', 750, 3, ('Living Room',), False),
    (0x1e8, 'Small Brown Oval Rug', 850, 3, ('Living Room',), False),
    (0x1e9, 'Small Green Oval Rug', 750, 3, ('Living Room',), False),
    (0x271, 'Pink Couch', 1780, 4, ('Living Room',), False),
    (0x276, 'Pink Sofa', 1150, 4, ('Living Room',), False),
    (0x27b, 'Pink Bookshelf', 1295, 4, ('Living Room', 'Dining Room', 'Bedroom'), False),
    (0x280, 'Pink Coffee Table', 525, 4, ('Living Room',), False),
    (0x28e, 'Pink Credenza', 2550, 4, ('Living Room', 'Dining Room'), False),
    (0x29d, 'Modern Pink Rug', 1050, 4, ('Living Room', 'Dining Room', 'Bedroom'), False),
    (0x1f8, 'Large Birch Book Case', 2450, 4, ('Living Room',), False),
    (0x253, 'Square Birch Bookshelf', 1250, 4, ('Living Room',), False),
    (0x219, 'Wall Painting', 450, 4, ('Living Room',), False),
    (0x21a, 'Wall Painting', 350, 4, ('Living Room',), False),
    (0x21b, 'Wall Painting', 4150, 4, ('Living Room',), False),
    (0x21c, 'Wall Painting', 13150, 4, ('Living Room',), False),
    (0x26f, 'Green Couch', 1950, 5, ('Living Room',), False),
    (0x274, 'Green Sofa', 1250, 5, ('Living Room',), False),
    (0x279, 'Green Bookshelf', 1425, 5, ('Living Room', 'Dining Room', 'Bedroom'), False),
    (0x27e, 'Green Coffee Table', 580, 5, ('Living Room',), False),
    (0x28c, 'Green Credenza', 2795, 5, ('Living Room', 'Dining Room'), False),
    (0x29b, 'Modern Green Rug', 1175, 5, ('Living Room', 'Dining Room', 'Bedroom'), False),
    (0x211, 'Antique Oriental Rug', 14500, 5, ('Living Room',), False),
    (0x212, 'Quality Oriental Rug', 8800, 5, ('Living Room',), False),
    (0x213, 'Intricate Oriental Rug', 7600, 5, ('Living Room',), False),
    (0x214, 'Modern Oriental Rug', 4500, 5, ('Living Room',), False),
    (0x26e, 'Blue Couch', 2210, 7, ('Living Room',), False),
    (0x273, 'Blue Sofa', 1415, 7, ('Living Room',), False),
    (0x278, 'Blue Bookshelf', 1595, 7, ('Living Room', 'Dining Room', 'Bedroom'), False),
    (0x27d, 'Blue Coffee Table', 650, 7, ('Living Room',), False),
    (0x28b, 'Blue Credenza', 3145, 7, ('Living Room', 'Dining Room'), False),
    (0x29a, 'Modern Blue Rug', 1315, 7, ('Living Room', 'Dining Room', 'Bedroom'), False),
    (0x261, 'Elegant Flowery Sofa', 1825, 7, ('Living Room',), False),
    (0x262, 'Elegant Striped Sofa', 1745, 7, ('Living Room',), False),
    (0x263, 'A Modern White Couch', 2695, 7, ('Living Room',), False),
    (0x260, 'Dramatic Gothic Couch', 3395, 7, ('Living Room',), False),
    (0x25d, 'Modern White Coffee Table', 795, 7, ('Living Room',), False),
    (0x24b, 'Gothic Coffee Table', 2150, 7, ('Living Room',), False),
    (0x25c, 'Modern White Bookshelf', 1950, 7, ('Living Room',), False),
    (0x24a, 'Black Bookshelf', 3125, 7, ('Living Room',), False),
    (0x258, 'Animal Rug', 1250, 7, ('Living Room',), False),
    (0x259, 'Modern White Rug', 2750, 7, ('Living Room',), False),
    (0x25a, 'Modern Dark Rug', 3125, 7, ('Living Room',), False),
    (0x25b, 'Modern Red Rug', 1610, 7, ('Living Room',), False),
    (0x22d, 'Large Modern Painting', 3875, 7, ('Living Room',), False),
    (0x22e, 'Large Modern Painting', 2450, 7, ('Living Room',), False),
    (0x22f, 'Large Modern Painting', 2975, 7, ('Living Room',), False),
    (0x230, 'Large Modern Painting', 2795, 7, ('Living Room',), False),
    (0x231, 'Huge Landscape Painting', 12995, 7, ('Living Room',), False),
    (0x272, 'Red Couch', 2450, 9, ('Living Room',), False),
    (0x277, 'Red Sofa', 1575, 9, ('Living Room',), False),
    (0x27c, 'Red Bookshelf', 1775, 9, ('Living Room', 'Dining Room', 'Bedroom'), False),
    (0x281, 'Red Coffee Table', 725, 9, ('Living Room',), False),
    (0x28f, 'Red Credenza', 3495, 9, ('Living Room', 'Dining Room'), False),
    (0x2f6, 'Plaid Loveseat', 725, 12, ('Living Room',), True),
    (0x2f7, 'Plaid Couch', 950, 13, ('Living Room',), True),
    (0x2fa, 'Striped Loveseat', 725, 13, ('Living Room',), True),
    (0x2f8, 'Flowered Couch', 1250, 14, ('Living Room',), True),
    (0x2f9, 'Striped Couch', 1050, 14, ('Living Room',), True),
    (0x2fb, 'Flowered Loveseat', 825, 14, ('Living Room',), True),
    (0x2f0, 'Vibrant Brown Couch', 700, 17, ('Living Room',), True),
    (0x2f1, 'Vibrant Gold Couch', 1800, 17, ('Living Room',), True),
    (0x2f4, 'Vibrant Violet Couch', 900, 17, ('Living Room',), True),
    (0x2f5, 'Vibrant Lime Couch', 750, 17, ('Living Room',), True),
    (0x2ef, 'Vibrant Purple Couch', 750, 19, ('Living Room',), True),
    (0x2f2, 'Vibrant Aqua Couch', 750, 19, ('Living Room',), True),
    (0x2f3, 'Vibrant Pink Couch', 750, 19, ('Living Room',), True),
    (0x321, 'Invisible Kids Table with Chairs', 950, 0, ('Dining Room',), True),
    (0x1d9, 'Second Hand Round Table', 150, 3, ('Dining Room',), False),
    (0x1dc, 'Second Hand Round Table', 275, 3, ('Dining Room',), False),
    (0x1d7, 'White Rectangular Table', 550, 3, ('Dining Room',), False),
    (0x1d8, 'White Circular Table', 625, 3, ('Dining Room',), False),
    (0x1ce, "Children's Chairs", 950, 3, ('Dining Room',), False),
    (0x1da, 'White Rectangular Table', 975, 4, ('Dining Room',), False),
    (0x1db, 'White Circular Table', 1050, 4, ('Dining Room',), False),
    (0x1c6, 'Large Credenza', 2200, 4, ('Dining Room',), False),
    (0x1ff, 'Cocktail Credenza', 4290, 5, ('Dining Room',), False),
    (0x25e, 'Modern White Credenza', 3850, 7, ('Dining Room',), False),
    (0x24d, 'Gothic Credenza', 5195, 7, ('Dining Room',), False),
    (0x1b1, 'Standard Adult Bed', 850, 0, ('Bedroom',), False),
    (0x1b6, 'Standard Adult Bed', 850, 0, ('Bedroom',), False),
    (0x1b7, 'Standard Adult Bed', 850, 0, ('Bedroom',), False),
    (0x1b8, 'Standard Adult Bed', 850, 0, ('Bedroom',), False),
    (0x1b9, 'Standard Adult Bed', 850, 0, ('Bedroom',), False),
    (0x1ba, 'Standard Adult Bed', 850, 0, ('Bedroom',), False),
    (0x1bb, 'Standard Adult Bed', 1350, 0, ('Bedroom',), False),
    (0x1b4, "Pink Children's Bed", 550, 0, ('Bedroom',), False),
    (0x1b5, "Blue Children's Bed", 550, 0, ('Bedroom',), False),
    (0x1ca, 'Standard Dresser', 250, 0, ('Bedroom',), False),
    (0x20d, 'Landscape Poster', 35, 0, ('Bedroom',), False),
    (0x20e, 'Farm Poster', 35, 0, ('Bedroom',), False),
    (0x20f, 'Rose Poster', 55, 0, ('Bedroom',), False),
    (0x210, 'Art Poster', 75, 0, ('Bedroom',), False),
    (0x314, 'Invisible Adult Double Bed', 850, 0, ('Bedroom',), True),
    (0x327, 'Invisible Heart-Shaped Bed', 2750, 0, ('Bedroom',), True),
    (0x315, 'Invisible Child Single Bed', 550, 0, ('Bedroom',), True),
    (0x316, 'Invisible Double Bed', 3875, 0, ('Bedroom',), True),
    (0x317, 'Invisible Single Bed', 2195, 0, ('Bedroom',), True),
    (0x320, 'Invisible Dresser', 250, 0, ('Bedroom',), True),
    (0x225, 'Hearts Poster', 55, 2, ('Bedroom',), False),
    (0x252, 'Heart Shaped Bed', 2750, 3, ('Bedroom',), False),
    (0x292, 'Orange Double Bed', 1695, 3, ('Bedroom',), False),
    (0x297, 'Orange Dresser', 995, 3, ('Bedroom',), False),
    (0x283, 'Small Orange Bookshelf', 425, 3, ('Bedroom',), False),
    (0x286, 'Narrow Orange Dresser', 675, 3, ('Bedroom',), False),
    (0x289, 'Orange Nightstand', 520, 3, ('Bedroom',), False),
    (0x2a1, 'Large Orange Nightstand', 375, 3, ('Bedroom',), False),
    (0x2a6, 'Orange Single Bed', 955, 3, ('Bedroom',), False),
    (0x1b2, 'Boat Shaped Bed', 750, 4, ('Bedroom',), False),
    (0x1b3, 'Car Shaped Bed', 950, 4, ('Bedroom',), False),
    (0x293, 'Pink Double Bed', 1995, 4, ('Bedroom',), False),
    (0x298, 'Pink Dresser', 1175, 4, ('Bedroom',), False),
    (0x284, 'Small Pink Bookshelf', 495, 4, ('Bedroom',), False),
    (0x287, 'Narrow Pink Dresser', 795, 4, ('Bedroom',), False),
    (0x28a, 'Pink Nightstand', 600, 4, ('Bedroom',), False),
    (0x2a2, 'Large Pink Nightstand', 445, 4, ('Bedroom',), False),
    (0x2a7, 'Pink Single Bed', 1125, 4, ('Bedroom',), False),
    (0x291, 'Green Double Bed', 2175, 5, ('Bedroom',), False),
    (0x296, 'Green Dresser', 1295, 5, ('Bedroom',), False),
    (0x2a0, 'Large Green Nightstand', 485, 5, ('Bedroom',), False),
    (0x2a5, 'Green Single Bed', 1225, 5, ('Bedroom',), False),
    (0x254, 'Modern Double Bed in Blue', 2650, 7, ('Bedroom',), False),
    (0x255, 'Modern Double Bed in Red', 2650, 7, ('Bedroom',), False),
    (0x267, 'Modern Double Bed in Blue', 2995, 7, ('Bedroom',), False),
    (0x268, 'Modern Double Bed in Red', 2995, 7, ('Bedroom',), False),
    (0x26b, 'Fancy Single Bed, Airplanes', 1695, 7, ('Bedroom',), False),
    (0x26c, 'Fancy Single Bed, Princess', 1695, 7, ('Bedroom',), False),
    (0x24e, 'Gothic Double Bed in Blue', 3850, 7, ('Bedroom',), False),
    (0x24f, 'Gothic Double Bed in Red', 3850, 7, ('Bedroom',), False),
    (0x264, 'Gothic Double Bed in Blue', 3875, 7, ('Bedroom',), False),
    (0x265, 'Gothic Double Bed in Green', 3875, 7, ('Bedroom',), False),
    (0x266, 'Gothic Double Bed in Red', 3875, 7, ('Bedroom',), False),
    (0x250, 'Gothic Single Bed in Blue', 2195, 7, ('Bedroom',), False),
    (0x251, 'Gothic Single Bed in Red', 2195, 7, ('Bedroom',), False),
    (0x269, 'Gothic Single Bed in Blue', 2150, 7, ('Bedroom',), False),
    (0x26a, 'Gothic Single Bed in Red', 2150, 7, ('Bedroom',), False),
    (0x25f, 'Modern White Nightstand', 495, 7, ('Bedroom',), False),
    (0x24c, 'Gothic Nightstand', 995, 7, ('Bedroom',), False),
    (0x290, 'Blue Double Bed', 2450, 7, ('Bedroom',), False),
    (0x295, 'Blue Dresser', 1465, 7, ('Bedroom',), False),
    (0x282, 'Small Blue Bookshelf', 615, 7, ('Bedroom',), False),
    (0x285, 'Narrow Blue Dresser', 980, 7, ('Bedroom',), False),
    (0x288, 'Blue Nightstand', 750, 7, ('Bedroom',), False),
    (0x29f, 'Large Blue Nightstand', 550, 7, ('Bedroom',), False),
    (0x2a4, 'Blue Single Bed', 1395, 7, ('Bedroom',), False),
    (0x294, 'Red Double Bed', 2725, 9, ('Bedroom',), False),
    (0x299, 'Red Dresser', 1625, 9, ('Bedroom',), False),
    (0x2a3, 'Large Red Nightstand', 595, 9, ('Bedroom',), False),
    (0x2a8, 'Single Red Bed', 1545, 9, ('Bedroom',), False),
    (0x2eb, 'Last Day of Work Poster', 35, 25, ('Bedroom',), True),
    (0x2ec, 'Casino Game Posters and Wall Calendar', 35, 25, ('Bedroom',), True),
    (0x2ed, 'Virtual Families and Tycoon Games Posters', 55, 25, ('Bedroom',), True),
    (0x2ee, 'Virtual Town and Cook Off Posters', 75, 25, ('Bedroom',), True),
    (0x30a, 'Invisible Kiddie Pool', 250, 0, ('Outdoors',), True),
    (0x30b, 'Invisible Full-Size Pool', 14150, 0, ('Outdoors',), True),
    (0x328, 'Invisible Picnic Table', 450, 0, ('Outdoors',), True),
    (0x329, 'Invisible Patio Table', 850, 0, ('Outdoors',), True),
    (0x32a, 'Invisible Yoga Equipment', 150, 0, ('Outdoors',), True),
    (0x32b, 'Invisible Lounger', 250, 0, ('Outdoors',), True),
    (0x32f, 'Invisible Spa Lounger', 250, 0, ('Outdoors',), True),
    (0x331, 'Invisible Ping-Pong Table', 12000, 0, ('Outdoors',), True),
    (0x30c, 'Invisible Hammock', 450, 0, ('Outdoors',), True),
    (0x31a, 'Invisible Sandbox', 695, 0, ('Outdoors',), True),
    (0x31b, 'Invisible Playhouse', 18000, 0, ('Outdoors',), True),
    (0x31c, 'Invisible Train Table', 950, 0, ('Outdoors',), True),
    (0x323, 'Invisible Trampoline', 2695, 0, ('Outdoors',), True),
    (0x1e0, 'Bubble Maker', 75, 2, ('Outdoors', 'Toys'), False),
    (0x1e2, 'Toy Pirate Ship', 150, 2, ('Outdoors', 'Toys'), False),
    (0x1e1, 'Hammock', 450, 3, ('Outdoors',), False),
    (0x2e2, 'Black Floor Lamp', 175, 3, ('Outdoors',), True),
    (0x2e3, 'Chrome Floor Lamp', 175, 3, ('Outdoors',), True),
    (0x235, 'Sandbox', 695, 4, ('Outdoors',), False),
    (0x1e4, 'Kiddie Pool', 250, 4, ('Outdoors', 'Toys'), False),
    (0x1e5, 'Full Size Pool', 14150, 4, ('Outdoors',), False),
    (0x2de, 'Blue Lounge Chair', 250, 4, ('Outdoors',), True),
    (0x2df, 'Brown Lounge Chair', 250, 4, ('Outdoors',), True),
    (0x2e0, 'Green Lounge Chair', 250, 4, ('Outdoors',), True),
    (0x2e1, 'Red Lounge Chair', 250, 4, ('Outdoors',), True),
    (0x2e4, 'Brick Patio', 4500, 4, ('Outdoors',), True),
    (0x2e5, 'Cobblestone Patio', 5500, 4, ('Outdoors',), True),
    (0x2e6, 'Patio Table', 850, 4, ('Outdoors',), True),
    (0x2e7, 'Patio Umbrella', 125, 4, ('Outdoors',), True),
    (0x2e8, 'Picnic Table', 450, 4, ('Outdoors',), True),
    (0x32e, 'Ping-Pong Table', 12000, 4, ('Outdoors',), True),
    (0x1e3, 'Play Structure', 18000, 5, ('Outdoors', 'Toys'), False),
    (0x23a, 'Trampoline', 1695, 6, ('Outdoors',), False),
    (0x330, 'Spa Lounger', 250, 12, ('Outdoors',), True),
    (0x1d0, "Children's Night Light", 20, 0, ('Accessories',), False),
    (0x1eb, 'Blue Designer Soap', 45, 0, ('Accessories',), False),
    (0x1ee, 'Dental Care Set', 10, 0, ('Accessories',), False),
    (0x1f0, 'Blue Towel Set', 150, 0, ('Accessories',), False),
    (0x202, 'Fish Bowl', 150, 0, ('Accessories',), False),
    (0x206, 'Acoustic Guitar', 1700, 0, ('Accessories',), False),
    (0x21d, 'Door Mat', 150, 0, ('Accessories',), False),
    (0x21e, 'Welcome Mat', 250, 0, ('Accessories',), False),
    (0x26d, 'Food and Water Bowls', 35, 0, ('Accessories',), False),
    (0x318, 'Invisible Mantle Fireplace', 9150, 0, ('Accessories',), True),
    (0x319, 'Invisible MP3 Player', 350, 0, ('Accessories',), True),
    (0x31d, 'Invisible Bathroom Scale', 130, 0, ('Accessories',), True),
    (0x31e, 'Invisible Drying Rack', 80, 0, ('Accessories',), True),
    (0x31f, 'Invisible Grandfather Clock', 8500, 0, ('Accessories',), True),
    (0x322, 'Invisible Ironing Board', 250, 0, ('Accessories',), True),
    (0x1bc, 'Cleaning Supplies', 75, 2, ('Accessories',), False),
    (0x1ec, 'Brown Designer Soap', 45, 2, ('Accessories',), False),
    (0x1ed, 'Pink Designer Soap', 55, 2, ('Accessories',), False),
    (0x1ef, 'Black Towel Set', 250, 2, ('Accessories',), False),
    (0x1f1, 'Green Towel Set', 150, 2, ('Accessories',), False),
    (0x1f5, 'Fish Aquarium', 850, 2, ('Accessories',), False),
    (0x204, 'Foosball Table', 1250, 2, ('Accessories',), False),
    (0x218, 'Wall Clock', 250, 2, ('Accessories',), False),
    (0x220, 'Yoga Equipment', 150, 2, ('Accessories',), False),
    (0x2ae, 'Lighted Christmas Tree', 350, 2, ('Accessories',), True),
    (0x2bb, 'Gold Ornament', 6, 2, ('Accessories',), True),
    (0x2bc, 'Elegant Ornament', 6, 2, ('Accessories',), True),
    (0x2bd, 'Penguin Decoration', 50, 2, ('Accessories',), True),
    (0x2c0, 'Polar Bear Decoration', 75, 2, ('Accessories',), True),
    (0x2c2, 'Reindeer Decoration', 75, 2, ('Accessories',), True),
    (0x2c3, 'Santa Decoration', 75, 2, ('Accessories',), True),
    (0x2c5, 'Snowman', 75, 2, ('Accessories',), True),
    (0x2c8, 'Holiday Garland', 50, 2, ('Accessories',), True),
    (0x2c9, 'Lighted Garland', 50, 2, ('Accessories',), True),
    (0x2d3, 'Holiday Welcome Mat', 150, 2, ('Accessories',), True),
    (0x2d4, 'Lighted Wreath', 125, 2, ('Accessories',), True),
    (0x2d5, 'Holiday Wreath', 100, 2, ('Accessories',), True),
    (0x1d1, 'Sewing Kit', 30, 3, ('Accessories',), False),
    (0x208, 'Pachinko Machine', 2200, 3, ('Accessories',), False),
    (0x20a, 'Upright Piano', 11100, 3, ('Accessories',), False),
    (0x215, 'Slot Machine', 2250, 3, ('Accessories',), False),
    (0x216, 'Telescope', 950, 3, ('Accessories',), False),
    (0x20b, 'Pinball Machine', 3550, 4, ('Accessories',), False),
    (0x217, 'Treadmill', 3150, 4, ('Accessories',), False),
    (0x32c, 'Exercise Bike', 3150, 4, ('Accessories',), True),
    (0x32d, 'Home Gym System', 3150, 4, ('Accessories',), True),
    (0x201, 'Hearth', 9150, 5, ('Accessories',), False),
    (0x205, 'Grandfather Clock', 8500, 5, ('Accessories',), False),
    (0x209, 'Grand Piano', 19590, 5, ('Accessories',), False),
    (0x20c, 'Pool Table', 12000, 5, ('Accessories',), False),
    (0x21f, 'Wood Pile', 175, 5, ('Accessories',), False),
    (0x1f9, 'Carousel', 450, 5, ('Accessories', 'Toys'), False),
    (0x256, 'Black Framed Modern Mirror', 425, 7, ('Accessories',), False),
    (0x257, 'Silver Framed Modern Mirror', 425, 7, ('Accessories',), False),
    (0x2b3, 'Lumwinkle', 50, 10, ('Accessories',), True),
    (0x2cd, 'Green Beans', 5, 10, ('Accessories',), True),
    (0x2d8, 'Brown Towel Set', 150, 10, ('Accessories',), True),
    (0x2aa, 'Holiday Candles', 30, 12, ('Accessories',), True),
    (0x2af, 'Dreidel', 15, 12, ('Accessories',), True),
    (0x2cc, 'Gravy', 5, 12, ('Accessories',), True),
    (0x2ca, 'Cranberry Sauce', 5, 13, ('Accessories',), True),
    (0x2ce, 'Holiday Ham', 35, 13, ('Accessories',), True),
    (0x2cf, 'Mashed Potatoes', 5, 13, ('Accessories',), True),
    (0x2ad, 'Christmas Tree', 250, 15, ('Accessories',), True),
    (0x2b8, 'Menorah', 25, 15, ('Accessories',), True),
    (0x2cb, 'Dressing', 5, 15, ('Accessories',), True),
    (0x2ac, 'Christmas Cookie', 5, 17, ('Accessories',), True),
    (0x2b2, 'Pilwinkle', 50, 17, ('Accessories',), True),
    (0x2db, 'Birthday Banner', 15, 17, ('Accessories',), True),
    (0x2b4, 'Bimpni', 50, 18, ('Accessories',), True),
    (0x2ba, 'Striped Ornament', 5, 18, ('Accessories',), True),
    (0x2d1, 'Holiday Souffle', 10, 18, ('Accessories',), True),
    (0x2b1, 'Nacklebell', 50, 20, ('Accessories',), True),
    (0x2c4, 'Santa Wall Decoration', 35, 20, ('Accessories',), True),
    (0x2d9, 'Pink Towel Set', 150, 20, ('Accessories',), True),
    (0x2b9, 'Red Ornament', 5, 22, ('Accessories',), True),
    (0x2bf, 'Poinsettia', 20, 22, ('Accessories',), True),
    (0x2c1, 'Red Bow', 10, 22, ('Accessories',), True),
    (0x2be, 'A Plate of Cookies', 10, 23, ('Accessories',), True),
    (0x2d7, 'Green Designer Soap', 45, 23, ('Accessories',), True),
    (0x2dc, 'Birthday Cake', 25, 23, ('Accessories',), True),
    (0x2b6, 'Large Angel', 25, 25, ('Accessories',), True),
    (0x2c7, 'Small Stocking', 10, 25, ('Accessories',), True),
    (0x2dd, 'Birthday Presents', 50, 25, ('Accessories',), True),
    (0x2d0, 'Pumpkin Pie', 10, 27, ('Accessories',), True),
    (0x2d2, 'Holiday Turkey', 25, 27, ('Accessories',), True),
    (0x2da, 'Birthday Balloons!', 10, 27, ('Accessories',), True),
    (0x2ab, 'Candy Canes', 5, 28, ('Accessories',), True),
    (0x2b0, 'Glass of Eggnog', 5, 28, ('Accessories',), True),
    (0x2b7, 'Large Star', 15, 28, ('Accessories',), True),
    (0x2b5, 'Minnimalkin', 50, 30, ('Accessories',), True),
    (0x2c6, 'Large Stocking', 15, 30, ('Accessories',), True),
    (0x2d6, 'Black Designer Soap', 45, 30, ('Accessories',), True),
    (0x2e9, 'Virtual Villagers Painting', 2795, 30, ('Accessories',), True),
    (0x2ea, 'Painting of Isola', 12995, 30, ('Accessories',), True),
    (0x1c8, 'Hippo Doll', 25, 0, ('Toys',), False),
    (0x1c9, 'Pink Doll', 30, 0, ('Toys',), False),
    (0x1dd, 'Teddy Bear', 65, 0, ('Toys',), False),
    (0x249, 'Plush Elephant', 55, 0, ('Toys',), False),
    (0x1f6, 'Balloons!', 150, 0, ('Toys',), False),
    (0x228, 'Plush Giraffe', 55, 2, ('Toys',), False),
    (0x229, 'Plush Horse', 55, 2, ('Toys',), False),
    (0x232, 'Plush Monkey', 55, 2, ('Toys',), False),
    (0x234, 'Plush Pig', 55, 2, ('Toys',), False),
    (0x1cc, "Artist's Easel", 75, 2, ('Toys',), False),
    (0x227, 'Toy Drum', 35, 2, ('Toys',), False),
    (0x1de, 'Toy Assortment', 220, 3, ('Toys',), False),
    (0x22a, 'Giant Plush Bear', 450, 4, ('Toys',), False),
    (0x22b, 'Play Car', 475, 5, ('Toys',), False),
    (0x236, 'Play Kitchen', 750, 5, ('Toys',), False),
    (0x239, 'Toy Train Table', 950, 7, ('Toys',), False),
)
# The Pets tab (category 0x15): (id, name, price, generation lock, added by the patcher).  The Food and Water Bowls
# (0x26D) are on this tab too and are listed with the Accessories.
PET_ITEMS = (
    (0x23b, 'Kitten', 350, 0, False),
    (0x243, 'Longhair Puppy', 375, 0, False),
    (0x247, 'Hamster', 150, 0, True),
    (0x23d, 'Tabby', 550, 2, False),
    (0x241, 'Yellow Lab', 750, 2, False),
    (0x242, 'Black Lab', 750, 2, False),
    (0x23c, 'Snow White', 850, 3, False),
    (0x240, 'Beagle', 800, 3, False),
    (0x23f, 'Fluffy Grey Cat', 3500, 4, False),
    (0x245, 'Turtle', 900, 4, True),
    (0x23e, 'Hairless Cat', 11000, 5, False),
    (0x244, 'A Chihuahua', 3250, 5, False),
    (0x246, 'Lizard', 4650, 6, False),
    (0x248, 'Tarantula', 15000, 7, False),
)

# ---------------------------------------------------------------------------------------------------------------------
# Everything the store sells (2026-10-27, the owner's rule: every store item, upgrade and service gets its own entry).
# Sources, all in the B200 core exe (sha256 5cad4050) unless the line says otherwise, the stock exe (sha256 1582d9e8) for
# every "Unpatched game:" line:
#   * the store tabs, prices and generation locks: CInventoryManager::GetCategoryItemCount 0x46B6D0 / GetCategoryItem
#     0x46B210 / GetPrice 0x46B9F0 / GetLockGenerationLevel run as linked for every category of the store menu (table
#     0x574744: Food and Medicine 0xE, Flea Market 0xF, Career 0x1, Home Renovation 0x11, Clothing and Hairstyles 0xD,
#     Special Upgrades 0x14, Pets 0x15, On Sale 0x3, Living Room 0x4, Dining Room 0x5, Bedroom 0x6, General Appliances
#     0x0, Outdoors 0x7, Accessories 0xA, Toys 0x8), and the same in the stock exe (0x4BB0A0 / 0x4BAA50 after Reset
#     0x4BA8F0).  Every stock item has the same price and lock in both exes (inventory table 0x56FE70 / stock 0x553278,
#     furniture table 0x564F48 / stock 0x54C87C, compared row by row);
#   * buying: CScrollingStoreScene::HandleMouse -> HandlePurchaseItem 0x48BF20 -> CalcPrice 0x48ACB0, then the tray
#     (items below 0xE1), HandleUpgrade 0x48C2E0 (0xE1..0x1AC) or the furniture storage (0x1AD..0x331);
#   * using a tray item: theMainScene::HandleMouseDown 0x49EE90 (groceries, medicine, outfits) and
#     theMainScene::DispatchRotatingSundry 0x49CB90 (the Flea Market goods; its case table 0x49DD64 / 0x49DCF4), whose
#     code is the desktop object's byte for byte (coffmap placement);
#   * the patcher's rows: its helper code in the exe (VF2GetVisibleSpecialUpgradePrice 0x4B9F60, 0x4B8B50,
#     VF2GetOutfitStorePrice 0x4B9E80) and, for the Cheat Upgrades and room-renovation executables, the generator
#     source that builds them (work/patch_mobile_furniture_pack.py: VF2ApplyVisibleSpecialUpgrade, CHEAT_UPGRADE_ITEMS,
#     MOBILE_RENOVATION_STYLE_CATALOG, AI_BATHROOM2_STYLE_CATALOG).
# ---------------------------------------------------------------------------------------------------------------------
OPTION_CHEATS = "Cheat Upgrades"
HEALTH_PLAN_FLEA = frozenset(("Sweet Mango", "Perfect Bananas", "Virtuoso Fragrance for Men", "Virtuosa Perfume for Women",
                              "Multivitamins", "Antibacterial hand gel", "Sunscreen", "Towelette", "Natural Fruit Candy",
                              "Licorice Candy", "Mint Candy", "Cinnamon Candy", "Anti-spam Software",
                              "Kitchen Profession Magazine", "Office Profession Magazine",
                              "Workshop Profession Magazine"))
OPTION_RENOVATIONS = "Add mobile room renovations"
OPTION_BATHROOM2 = "2nd Bathroom Mobile-Style Renovations (AI-Generated Art Warning)"
OPTION_FLEA = "All 36 Flea Market goods"
OPTION_REFRESH = "R Refreshes the Store"
STORE_OPTION_NAMES = (OPTION_CHEATS, OPTION_RENOVATIONS, OPTION_BATHROOM2, OPTION_FLEA, OPTION_REFRESH)

# The game's Likes text (string 0x7AF), comma-separated, the n-th name for like n (CLikeList::GetListAsString).
LIKE_NAMES = {2: "resting", 25: "fish", 28: "swimming", 39: "cooking", 45: "quiet", 57: "strolling", 65: "shaving",
              75: "Internet", 81: "computers", 82: "carbs", 87: "burgers", 88: "pizza", 100: "trains", 108: "music",
              109: "art", 110: "gophers"}


def _likes(*ids: int) -> str:
    names = [f'"{LIKE_NAMES[i]}"' for i in ids]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]


# Owned or placed items that add mood points for a family member with a matching like (UpdateHappinessState
# 0x4CBE90, desktop offsets 0x2ED..0x55F): item -> (mood points, the likes, the condition).
FURNITURE_BONUS_GROUPS = {0x1AD: "4 grills", 0x1B0: "4 grills", 0x1AE: "4 grills", 0x1AF: "4 grills",
                          0x1E4: "2 pools", 0x1E5: "2 pools"}
FURNITURE_LIKE_BONUS = {
    0x1F3: (15, (75,)), 0x219: (3, (110,)), 0x1F5: (15, (25,)), 0x217: (15, (57,)), 0x207: (15, (109,)),
    0x20B: (45, (108,)), 0x208: (15, (108,)), 0x1E4: (35, (28,)), 0x1E5: (35, (28,)), 0x1E1: (15, (100, 45, 2)),
    0x1AD: (25, (87, 88)), 0x1B0: (25, (87, 88)), 0x1AE: (25, (87, 88)), 0x1AF: (25, (87, 88)),
}

# Food and Medicine (category 0xE): id -> (name, price, effect).  Prices from GetPrice run as linked.
GROCERY_ITEMS = (
    (0x04, "Groceries: Grains", 20, "Grains", False), (0x05, "Groceries: Dairy", 30, "Dairy", False),
    (0x06, "Groceries: Meats", 70, "Meats", False), (0x07, "Groceries: Fruits and Veggies", 40, "Fruits and Veggies", False),
    (0x08, "Organics: Grains", 40, "Grains", True), (0x09, "Organics: Dairy", 70, "Dairy", True),
    (0x0A, "Organics: Meats", 150, "Meats", True), (0x0B, "Organics: Fruits and Veggies", 90, "Fruits and Veggies", True),
)
MEDICINE_ITEMS = (
    ("Throat Lozenges", 25, "a sore throat: cured, with 3 hunger off and 10 mood points as part of the cure; without a "
                            "sore throat nothing is cured and the dose is used up"),
    ("Peptic Syrup", 35, "a stomach upset: cured, with 25 on the toilet need and 10 hunger off as part of the cure; "
                         "without one, 70 on the toilet need and 10 energy off at once, and the dose is used up"),
    ("Analgesic/Anti-inflammatory", 25, "a headache: cured; without one nothing is cured and the dose is used up"),
    ("Antitussive Syrup", 65, "a cough: cured, with 15 energy off as part of the cure; without one, 20 energy off at "
                              "once and the dose is used up"),
    ("Cortisone Cream", 40, "a skin rash: cured; without one nothing is cured and the dose is used up"),
    ("Antihistamine", 50, "a runny nose: cured, with 5 energy as part of the cure; without one nothing is cured "
                          "(the planned 5 energy is dropped) and the dose is used up"),
    ("Penicillin", 145, "the mild infection ends (whether or not there was one); energy is set to 15, the toilet need "
                        "rises by 30 and, with more than 10 health, 3 health is lost"),
    ("Vancomycin", 275, "both infections end; energy is set to 5, the toilet need is set to 80 and, with more than 12 "
                        "health, 10 health is lost"),
    ("Baby Boost", 2500, "only for a family member with a career (anyone else: nothing, and it stays in the tray): "
                         "fertility rises by a quarter of what it lacks of 102 (rounded towards zero), every time it is "
                         "used"),
    ("Doctor Consultation", 495, "opens the Diagnosis window for that family member, and is used up"),
)

# The Flea Market's 36 goods (gGoodiesList 0x56F5BC, in the store's order): (name, price, effect, label).
FLEA_ITEMS = (
    ("Multivitamins", 15, "health +3 to +7 and 35 mood points as part of the action, happiness +1 to +3 at once", C),
    ("Chamomile Drink", 10, "energy -10 to -29 at once, then Sleeping (adults) (15%) or Taking a nap (85%)",
     C),
    ("Energy Drink", 25, "hunger -4 and energy +40 to +89 at once, 5 jumps, then Doing Kung Fu (15%) or Exercising "
                         "outdoors (85%)", C),
    ("Mega Chamomile Extract", 10, "hunger -7 at once and energy -30 to -59 as part of the action, then Sleeping "
                                   "(adults) (75%) or Taking a nap (25%)", C),
    ("Delicious Candy", 7, "hunger -2 and happiness +2 to +3 at once, then 3 rewards for what the family member was "
                           "doing (see Rewards and scolding)", C),
    ("Salty Candy", 10, "3 scoldings for what the family member was doing (see Rewards and scolding); no need changes", C),
    ("Blood Orange", 10, "hunger -3, health +2 to +6, happiness +2 to +4 and energy +2 to +6 at once, then 3 rewards", C),
    ("Sweet Mango", 10, "health +2 to +6, happiness +2 to +6, energy +2 to +6 and hunger -3 at once, then 3 rewards", C),
    ("Perfect Bananas", 10, "health +2 to +6, hunger -3, happiness +2 to +6 and energy +2 to +6 at once, then 3 "
                            "rewards", C),
    ("Natural Fruit Candy", 10, "hunger -2 and happiness +2 to +4 at once, then 3 rewards", C),
    ("Licorice Candy", 10, "hunger -2 and happiness +2 to +4 at once, then 3 rewards", C),
    ("Mint Candy", 10, "hunger -2 and happiness +2 to +4 at once, then 3 rewards", C),
    ("Cinnamon Candy", 10, "hunger -2 and happiness +2 to +4 at once, then 3 rewards", C),
    ("Imported Candy", 25, "one of five, 20% each: happiness +5 to +12; happiness -5 with the toilet need set to 90 and "
                           "Using the toilet; happiness -5 and Running away; a skin rash; or health +20 with every "
                           "symptom but a runny nose and both infections cured", C),
    ("Virtuoso Fragrance for Men", 25, "on a family member without a career (every child born in the house): Running "
                                       "away and nothing else. On anyone else, whichever sex: that family member and "
                                       "the head of the family of the other sex (the matriarch for a man, the "
                                       "patriarch for a woman) both start Celebrating marriage, and the wearer gets "
                                       "35 mood points and happiness +1 to +3", C),
    ("Virtuosa Perfume for Women", 25, "the same code as the Virtuoso Fragrance for Men, with no check of the wearer's "
                                       "sex", C),
    ("Antibacterial hand gel", 12, "health +10 and 35 mood points as part of the action, happiness +1 to +3 at once", C),
    ("Sunscreen", 12, "25 mood points as part of the action, happiness +1 to +3 at once, then Exercising outdoors", C),
    ("Towelette", 10, "dirtiness -15 as part of the action, happiness +1 to +3 at once, then dancing and 3 jumps", C),
    ("Kitchen Profession Magazine", 300, "for a family member who works in the kitchen: 10 rounds of career progress "
                                         "(each one piece of successful work, unpaid; see Career upgrades), so it can "
                                         "bring a promotion, and happiness +8 to +15. Anyone else: Confused, and the "
                                         "magazine is used up", C),
    ("Office Profession Magazine", 300, "the same, for a family member who works in the office", C),
    ("Workshop Profession Magazine", 300, "the same, for a family member who works in the workshop", C),
    ("Fog In a Bottle", 50, "the weather becomes Foggy (see Bottled weather)", C),
    ("Snow in a Bottle", 50, "the weather becomes Snowing (see Bottled weather)", C),
    ("Sleeping Pills", 10, "the same code as the Chamomile Drink: energy -10 to -29 at once, then Sleeping (adults) "
                           "(15%) or Taking a nap (85%)", C),
    ("Dirty Candy", 25, "one of four, 25% each: energy +2 to +6 with 2 jumps and a wave; energy -30 to -59 as part of "
                        "the action; the family member's career progress is multiplied by 4 (nothing without a "
                        "career; 3,000 progress is a promotion at the next piece of work); or a stomach upset", C),
    ("Weed Bomb", 75, "dropped outdoors, on the ground the code checks for: every weed in the yard is removed. Anywhere "
                      "else: \"You can't use this here!\" and it stays in the tray", C),
    ("Turtle Adventures", 20, "a movie: everyone at home starts Watching TV; with a TV next to the family member it is "
                              "dropped on it is used up, otherwise it goes back to the tray", C),
    ("Little Man Under the Sea", 20, "a movie, the same as Turtle Adventures", C),
    ("Pluto, the Loneliest Planet", 20, "a movie, the same as Turtle Adventures", C),
    ("Anti-spam Software", 125, "dropped on the computer: installed for good, so the 5 spam e-mails (see Random Events) "
                                "never come again, and everyone at home starts Celebrating the office upgrade. "
                                "Anywhere else: \"You can't use this here!\" and it stays in the tray", C),
    ("Bottled Tropical Rain", 50, "the weather becomes Stormy, rain with lightning (see Bottled weather)", C),
    ("Bottled Tropical Sunshine", 50, "seen live, the owner's report in play: gives Sunny weather (when it was seen "
                                      "and how it was tested were not recorded; not re-tested against the code "
                                      "reading below)", U),
    ("Encyclopedia", 75, "happiness +1 to +3; one like, picked from the first 100 of the 121, is added if it is not "
                         "already a like and one of the 3 like places is free, and that like is taken off the "
                         "dislikes either way; then Studying", C),
    ("Magic Barker and the Loose Screw", 15, "a children's book. Dropped on a family member 14 or older, that member "
                                             "reads it; dropped on a child (under 14), the game picks the reader at "
                                             "random among those 55 or older and those 14 or older with a career who "
                                             "are not pregnant (nobody reads if none qualifies). The reader gets "
                                             "happiness +4 to +5 and starts Telling a story; every child at home gets "
                                             "happiness +5 and starts Listening to a story", C),
    ("Rockhound Certificate", 1500, "kept for good once bought: the collectible spawn areas that need it become "
                                    "active (its description: the fossils)", C),
)

# Special Upgrades (category 0x14), stock rows: (name, price, effect, label)
SPECIAL_ITEMS = (
    ("Roll the Dice (Random Event)", 2000, "a Random Event at once, picked evenly among those that can happen", C),
    ("Time Warp", 2000, "the family lives 61 age units at once (10 hours 10 minutes of game time; 36,600 seconds of "
                        "real time at Normal speed), "
                        "with their meals, health, salary and birthdays); the money it brings is capped at $750; a "
                        "paused game stays paused", C),
    ("Adoption Services", 4000, "a 3-year-old (60 age units) of either sex, equally likely, joins the house and is "
                                "added to the family tree as a child", C),
    ("On Call Maid Service", 1000, "kept for good: the Maid comes every hour of game time in the day by your PC's clock (the first "
                                   "visit 1 hour of game time after buying) and no socks, candy wrappers or dirt "
                                   "smudges appear (see Messes and malfunctions)", C),
    ("On Call Gardening Service", 1000, "kept for good: the Gardener comes every hour of game time in the day by your PC's clock "
                                        "(the first visit 1 hour of game time after buying) and no weeds appear", C),
)

# Services (the family member selected when the store opened, gs+0x25CC4): (name, price, effect, ages)
SERVICE_ITEMS = (
    ("Boarding School", 1500, "the family member leaves home, as a child going to college does (see Leaving home), "
                              "with the message \"... has been sent away to school!\"", "children"),
    ("Systematic Desensitization", 2500, "every dislike is removed", "children and adults"),
    ("Psychotherapy", 1750, "happiness below 25 becomes 30 to 49; from 25 to 49 it becomes 55 to 74; from 50 it rises "
                            "by 5 to 24 (at most 100)", "children and adults"),
    ("Higher Learning Classes", 1000, "one new like, picked at random from the 121 likes not already liked, if one of "
                                      "the 3 like places is free; that like is taken off the dislikes",
     "children and adults"),
    ("Advanced Career Training", 1100, "a promotion to the next career level, with its new salary (nothing at Master). "
                                       "The price is $1,100 times (the career level + 1): $1,100 for a Beginner up to "
                                       "$8,800 for a Master", "adults"),
    ("Career Change", 1200, "a new career picked at random from the 132, at level 0 (Beginner)", "adults"),
)

# Home Renovation (category 0x11), in the store's order: (id, name, price, lock, extra)
RENOVATION_ITEMS = (
    (0xE3, "West Room Renovation", 650, 0, ""), (0xE4, "Bedroom 1", 1750, 0, ""),
    (0xE1, "Deck Expansion", 1500, 2, ""), (0xEA, "Rear Deck Expansion", 475, 2, ""),
    (0xE2, "West Auxiliary Room", 6000, 3, ""), (0xE8, "Large Central Room", 9500, 3, ""),
    (0xE5, "Bedroom 2", 9500, 4, ""),
    (0xE6, "2nd Bathroom", 15000, 4, " It also makes the north bathroom's shower, toilet and sink leaks possible (3 of "
                                     "the 14 malfunction picks), and gives 10 mood points every 30 minutes of game time to each "
                                     "family member whose Likes show \"shaving\"."),
    (0xE7, "Small Central Room", 35000, 5, ""), (0xE9, "Large North Room", 45000, 5, ""),
)

# Career upgrades (category 0x1): (id, name, price, lock, workplace)
CAREER_UPGRADE_ITEMS = (
    (0xF0, "Designer Waste Basket", 150, 0, 2), (0xF2, "Paper Shredder", 350, 0, 2), (0xED, "Air Purifier", 950, 2, 2),
    (0xF3, "Surround Sound System", 1450, 2, 2), (0xEF, "Phone System and Fax Machine", 3800, 3, 2),
    (0xF1, "Printer Upgrade", 3920, 3, 2), (0xEE, "High Capacity Battery Backup", 4500, 4, 2),
    (0xF5, "Digitizing White Board", 4800, 4, 2), (0xEB, "Pro Computer (left)", 8000, 5, 2),
    (0xEC, "Pro Computer (right)", 8000, 5, 2), (0xF4, "Business Broadband", 8500, 5, 2),
    (0xFC, "Spice Rack with Imported Spices", 150, 0, 1), (0xF7, "Professional Coffee Maker", 400, 0, 1),
    (0xFD, "Fresh Herb and Spice Grinders", 825, 2, 1), (0xFE, "Waffle Iron and Panini Press", 1675, 2, 1),
    (0xFA, "Pro Blender and Electric Mixer", 3939, 3, 1), (0xF6, "Commercial Microwave Oven", 4400, 3, 1),
    (0xFB, "Professional Cutlery", 4800, 4, 1), (0xF8, "Espresso Machine", 6700, 4, 1),
    (0xF9, "Pro Food Processor and Slicers", 8895, 5, 1), (0xFF, "Super Fridge", 13000, 5, 1),
    (0x109, "Starter Tool Box", 175, 0, 3), (0x106, "Big Red Tool Box", 475, 0, 3),
    (0x107, "Industrial Shop Vacuum", 895, 2, 3), (0x105, "Parts Box and Assorted Hardware", 1250, 2, 3),
    (0x101, "Workshop Ventilation System", 2200, 3, 3), (0x102, "Furnace", 5200, 3, 3),
    (0x103, "Power Tool Set", 5750, 4, 3), (0x108, "Tool Wall", 6980, 4, 3),
    (0x100, "Industrial Drill and Drill Press", 10500, 5, 3), (0x104, "Lathe", 12500, 5, 3),
)

# The patcher's room remodels ("Add mobile room renovations"): MOBILE_RENOVATION_STYLE_CATALOG, (name, price, lock)
MOBILE_RENOVATION_ITEMS = (
    ("Bathroom 1 Remodel in Black", 2200, 4), ("Bathroom 1 Remodel in Blue", 1000, 0),
    ("Bathroom 1 Remodel in Beige", 2200, 4), ("Bathroom 1 Remodel in Green", 2200, 4),
    ("Bathroom 1 Remodel in Pink", 2200, 4), ("Kitchen Remodel in Beige", 2200, 4),
    ("Wood Paneled Workshop Remodel", 2100, 3), ("Office Remodel in Red", 2750, 3),
    ("Kitchen Remodel in Yellow", 3500, 3), ("Country Kitchen Remodel", 1850, 3), ("Dark Office Remodel", 2100, 3),
    ("Office Remodel in Green", 2800, 3), ("Modern Office Remodel", 2100, 3), ("Office Remodel in Blue", 2450, 3),
    ("Checkered Workshop Remodel", 1900, 3),
)
BATHROOM2_REMODEL_ITEMS = (("Bathroom 2 Remodel in Black", 2200), ("Bathroom 2 Remodel in Blue", 1000),
                           ("Bathroom 2 Remodel in Beige", 2200), ("Bathroom 2 Remodel in Green", 2200),
                           ("Bathroom 2 Remodel in Pink", 2200))

# The Cheat Upgrades rows (CHEAT_UPGRADE_ITEMS, every one $0), each with what VF2ApplyVisibleSpecialUpgrade's case does.
CHEAT_ITEMS = (
    ("No Money", "money is set to $0"),
    ("Add 100 coins", "+$100"),
    ("Add 10 thousand coins", "+$10,000"),
    ("Add max amount of coins", "money is set to $4,000,000,000, the most the game holds"),
    ("No Food", "the house's food is set to 0"),
    ("Add 100 food", "+100 food"),
    ("Add 10 thousand food", "+10,000 food"),
    ("Add max amount of food", "food is set to 2,147,483,647"),
    ("Unlock everything in the store", "every generation lock in the store is lifted, saved with the game; bought "
                                       "again ($0) the locks are back"),
    ("Reset Achievements", "every goal and its progress is reset; kept: the lifetime generation count, the armed "
                           "pregnancy rows below, the Health Plan and the remodels"),
    ("Complete all Achievements", 'its description: "Completes every currently enabled achievement and awards its '
                                  'normal coin reward."'),
    ("Reset Ants", 'its description: "Resets the ants puzzle so it can be completed again."'),
    ("Reset all collections", 'its description: "Removes every collected item and resets collection progress."'),
    ("Complete all collections", 'its description: "Completes every collection and its related achievements."'),
    ("2x Prices", "every store price is doubled after the store's own discounts; the three multiplier rows exclude "
                  "one another, and buying the active one again ($0) switches it off"),
    ("5x Prices", "every store price is multiplied by 5, as above"),
    ("100x Prices", "every store price is multiplied by 100, as above"),
    ("Reset Price Multiplier", "the multiplier in force is switched off"),
    ("Trigger all house malfunctions", "the router goes offline and the 6 other breakdowns of the malfunction pick "
                                       "happen at once; the dryer lint fire too when a dryer is placed, and "
                                       "the north bathroom's 3 leaks when the 2nd Bathroom is owned; the ants are not "
                                       "touched"),
    ("Fix all house malfunctions", "those 11 malfunctions are all cleared, so the router is back online; the ants "
                                   "are not touched"),
    ("Fill available house slots with trash", 'its description: "Spawns 15: 5 dirt smudges, 5 socks, 5 wrappers. Will '
                                              'not work if Maid is active."'),
    ("Clean House", 'its description: "Removes the same four indoor mess categories as the stock Housekeeping '
                    'Services event. Yard weeds and the laundry-room sock pile are preserved."'),
    ("Fill available yard slots with weeds", 'its description: "Spawns 15 weeds, all 4 types (4/4/4/3, rotates). Will '
                                             'not work if Gardener is active."'),
    ("Clean Garden", "every weed in the yard is removed, as the Weed Bomb does"),
    ("Max out sock pile", 'its description: "Sets only the laundry-room sock pile to 1,000,000 socks."'),
    ("No sock pile", 'its description: "Clears the laundry-room sock pile without awarding sock-laundering '
                     'progress."'),
    ("Force Marriage Email", "the dating e-mail is sent now, with the game's own rules for the date (nothing while it "
                             "cannot be sent)"),
    ("Enable Same-Sex Marriage", "a switch, saved with the game: dates of the same sex become possible; bought again it "
                                 "is off"),
    ("Divorce Spouse", 'its description: "WARNING: Permanently removes spouse from the Family Tree and House!"'),
    ("Allow Reroll of Marriage Candidates", "a switch, saved with the game: No on a date brings a new date, until "
                                            "Yes; bought again it is off"),
    ("Force Successful Pregnancy", "a one-shot, saved with the game: the next try for a baby succeeds; it stays armed "
                                   "until a birth; bought again it is disarmed"),
    ("Next Babies Male", "a one-shot: every baby of the next birth is a boy; it replaces Next Babies Female and is "
                         "cleared by the birth"),
    ("Next Babies Female", "a one-shot: every baby of the next birth is a girl; it replaces Next Babies Male"),
    ("Next Pregnancy Singleton", "a one-shot: the next birth is one baby; it replaces the twins and triplets rows"),
    ("Next Pregnancy Twins", "a one-shot: the next birth is twins when 2 child places are free; it replaces the other "
                             "two"),
    ("Next Pregnancy Triplets", "a one-shot: the next birth is triplets when 3 child places are free; it replaces the "
                                "other two"),
    ("Clear All Illnesses", "for everyone alive at home: every symptom and both infections are cured, clearing only "
                            "the fields the game's own cures clear (each symptom and its timer, the mild and serious "
                            "infection); the food groups and everything else are kept. Before the 27 October 2026 "
                            "B204 update the same code also cleared all four food groups (their flags and 24-hour "
                            "timers). The unpatched game has no such row"),
    ("Max out Happiness Bar", 'its description: "Fills the Happiness bar for everyone currently in the house."'),
    ("Max out Energy Bar", 'its description: "Fills the Energy bar for everyone currently in the house."'),
    ("Max out Fed Bar", 'its description: "Fills the Fed bar for everyone currently in the house, so nobody is '
                        'hungry."'),
    ("Max out Health Bar", 'its description: "Fills the Health bar for everyone currently in the house. Does not '
                           'revive anyone who has already died."'),
    ("Anti-Spam Software Ownership", "a switch: the Anti-spam Software is installed without a computer, or "
                                     "uninstalled"),
    ("Rockhound Certificate Ownership", "a switch: the Rockhound Certificate is given, or taken away"),
    ("Set Age to 18", "the family member whose details are open becomes exactly 18 years old (360 age units); offered "
                      "from that member's details only"),
    ("Add Running Like", "the family member whose details are open gets like 29, which the Likes text names "
                         "\"running\", if a like place is free; offered from that member's details only"),
)


# The branches of an action that change its need changes (beyond a missing or unreachable piece), read from each
# handler: Reading 0x33 (LinkPeepToFurniture 0x5A fails -> PlanToShakeHead, PlanToDecHappinessTrend(1)), Using the
# toilet 0x62 (gs+0x25C80 / +0x25CA8 occupants; both taken -> the wait path to 0x208 skips PlanToDecPoo), Barbecuing
# 0xDA (CFoodStore+0x78 > 10), Needs to sit down 0x189 (state energy +0x34 > 35 -> +3, else +10), Jumping on the bed
# 0x55 (FindFurniture 0x12 / 0x60).
ACTION_BRANCHES = {
    0x033: "-1 with no reachable seat (and a head shake), +1 when seated",
    0x062: "all three with a free toilet (the north bathroom's too, with that renovation); with every toilet taken, "
           "the have-to-pee dance and no need changes",
    0x0DA: "with 10 food or less, a refusal and no need changes",
    0x055: "with no bed, no need changes",
}

# Actions (CBehavior handlers, registered by id in CBehavior::CBehavior): id -> (name, the need changes its code
# plans, whether a change appears on more than one of its branches).  Need changes extracted from each handler's
# PlanToInc* / PlanToDec* calls and their arguments (rand ranges resolved); names from the action's own label.
ACTION_ITEMS = {
    0x012: ('Doing laundry', ('energy -3', 'dirtiness +5', 'mood points +2'), False),
    0x013: ('Doing Kung Fu', (), False),
    0x021: ('Playing with toys', (), False),
    0x024: ('Relaxing in the hammock', ('dirtiness +4', 'mood points +1', 'energy +2'), False),
    0x033: ('Reading', ('mood points -1', 'mood points +1'), False),
    0x035: ('Sleeping (adults)', ('energy +10', 'dirtiness +2'), False),
    0x037: ('Sleeping (children)', ('energy +10', 'happiness +5'), False),
    0x03e: ('Watching TV', (), False),
    0x046: ('Checking weight', (), False),
    0x049: ('Walking on the treadmill', ('dirtiness +8', 'mood points +4'), False),
    0x055: ('Jumping on the bed', ('energy -6 (-2 three times)', 'mood points +3'), True),
    0x056: ('Studying', ('energy -3', 'mood points +2', 'hunger +2'), False),
    0x059: ('Exercising outdoors', ('health +2', 'energy -5', 'mood points +3'), False),
    0x062: ('Using the toilet', ('dirtiness +40', 'toilet need -40', 'dirtiness -30'), True),
    0x064: ('Celebrating', ('mood points +50', 'energy -3', 'toilet need +2', 'dirtiness +2'), False),
    0x067: ('Making the bed', ('energy -3', 'mood points +10', 'dirtiness +2'), False),
    0x06c: ('Putting away groceries', ('mood points +10 to 24', 'energy -2', 'mood points +4', 'dirtiness +2'), False),
    0x07a: ('Celebrating marriage', (), False),
    0x07e: ('Celebrating the office upgrade', (), False),
    0x07f: ('Celebrating the kitchen upgrade', (), False),
    0x080: ('Celebrating the workshop upgrade', (), False),
    0x083: ('Taking a nap', ('energy +7 to 11', 'dirtiness +2'), False),
    0x08d: ('Mending a button', ('energy -1', 'mood points +3'), False),
    0x091: ('Swimming in the pool', ('dirtiness +5', 'energy -2', 'mood points +3'), False),
    0x094: ('Having a cocktail', (), False),
    0x095: ('Watching the fire', (), False),
    0x096: ('Playing foosball', (), False),
    0x097: ('Playing guitar', (), False),
    0x098: ('Playing piano', (), False),
    0x099: ('Playing pool', (), False),
    0x09a: ('Checking out new clothes', (), False),
    0x0da: ('Barbecuing!', ('hunger -7', 'dirtiness +4', 'toilet need +4', 'mood points +4'), False),
    0x0dd: ('Playing pinball', ('mood points +5', 'dirtiness +1', 'energy -3'), False),
    0x0de: ('Playing the slot machine', ('mood points +5', 'dirtiness +1', 'energy -3'), False),
    0x0df: ('Playing pachinko', ('mood points +5', 'dirtiness +1', 'energy -3'), False),
    0x0e0: ('Running on the treadmill', ('dirtiness +6', 'mood points +2', 'energy -8'), False),
    0x0e1: ('Feeding the fish', ('mood points +4',), False),
    0x0e3: ('Bothering the fish', (), False),
    0x0e4: ('Admiring the Magic Fish', (), False),
    0x0ed: ('Dancing to the radio', ('energy -4', 'mood points +2', 'dirtiness +2'), False),
    0x0f3: ('Using the drying rack', (), False),
    0x0f4: ('Ironing', (), False),
    0x0f5: ('Listening to the radio', ('mood points +4',), False),
    0x10e: ('Telling a story', ('energy -5', 'hunger +2'), False),
    0x10f: ('Listening to a story', ('energy -3', 'mood points +3'), False),
    0x118: ('Drawing', ('mood points +2', 'dirtiness +5'), False),
    0x11d: ('Trying to find stars', (), False),
    0x11e: ('Playing on the play structure', (), False),
    0x130: ('Playing quietly', (), False),
    0x169: ('Running away', (), False),
    0x16d: ('Dancing to the bubbles', (), False),
    0x171: ('Confused', (), False),
    0x175: ('Shaking head', (), False),
    0x176: ('Shaking head', (), False),
    0x189: ('Needs to sit down', ('energy +3 (energy over 35) or +10 (energy 35 or less)',), True),
    0x193: ('Playing drums', ('mood points +1', 'energy -2'), False),
    0x194: ('Hugging the bear', ('mood points +3', 'energy +1'), False),
    0x195: ('Driving like a grownup', ('mood points +3', 'energy -2'), False),
    0x196: ('Making sandcastles', ('mood points +5', 'energy -5', 'dirtiness +8', 'hunger +3'), False),
    0x197: ('Cooking like a grownup', ('mood points +3', 'energy -3', 'dirtiness +4', 'hunger +3'), False),
    0x198: ('Playing with trains', ('mood points +3', 'energy -3', 'hunger +3'), False),
    0x199: ('Jumping', ('mood points +3', 'energy -6', 'dirtiness +4', 'hunger +3'), False),
    0x19a: ('Petting the pet', (), False),
}
# Hot spots (a map cell's (cell >> 18) & 0x7F) -> (CHotSpot handler, the actions its code can start).
HOTSPOT_ACTIONS = {
    1: ('FirePlace', (0x095, )),
    5: ('Hammock', (0x024, )),
    7: ('Laundry', (0x012, )),
    8: ('Treadmill', (0x049, 0x0e0, )),
    15: ('TV', (0x03e, )),
    16: ('PlayInPlace', (0x021, )),
    20: ('Pool', (0x091, )),
    23: ('Pinball', (0x0dd, )),
    24: ('Radio', (0x0f5, 0x0ed, )),
    32: ('Bbq', (0x0da, 0x176, )),
    33: ('IroningBoard', (0x0f4, )),
    34: ('AdultBed', (0x055, 0x067, 0x037, 0x035, )),
    35: ('KidsBeds', (0x055, 0x067, 0x037, )),
    36: ('Toys', (0x021, )),
    40: ('KidsTable', (0x130, )),
    43: ('DryingRack', (0x0f3, )),
    44: ('BubbleMaker', (0x16d, )),
    45: ('PlayStructure', (0x11e, )),
    46: ('BathroomScale', (0x046, )),
    47: ('Aquarium', (0x0e4, 0x0e1, 0x0e3, )),
    51: ('SewingKit', (0x08d, )),
    60: ('BookCase', (0x033, )),
    64: ('Pachinko', (0x0df, )),
    65: ('Piano', (0x098, )),
    66: ('Couch', (0x189, 0x03e, )),
    68: ('Bar', (0x094, )),
    69: ('Foosball', (0x096, )),
    70: ('PoolTable', (0x099, )),
    71: ('SlotMachine', (0x0de, )),
    72: ('Telescope', (0x11d, )),
    83: ('Easel', (0x118, )),
    84: ('Guitar', (0x097, )),
    85: ('KidsKitchen', (0x197, )),
    86: ('TrainTable', (0x198, )),
    87: ('GiantBear', (0x194, )),
    88: ('Trampoline', (0x199, )),
    89: ('SandBox', (0x196, )),
    90: ('Drum', (0x193, )),
    91: ('PlayCar', (0x195, )),
}
# Each furniture piece's hot spots, read from its shipped placement map (*.png.fmap, B204 final_all_enabled).
FURNITURE_HOTSPOTS = {
    0x1ad: (32,),
    0x1ae: (32,),
    0x1af: (32,),
    0x1b0: (32,),
    0x1b1: (34,),
    0x1b2: (35,),
    0x1b3: (35,),
    0x1b4: (35,),
    0x1b5: (35,),
    0x1b6: (34,),
    0x1b7: (34,),
    0x1b8: (34,),
    0x1b9: (34,),
    0x1ba: (34,),
    0x1bb: (34,),
    0x1bd: (66,),
    0x1be: (66,),
    0x1bf: (66,),
    0x1c0: (66,),
    0x1c1: (66,),
    0x1c2: (66,),
    0x1c3: (66,),
    0x1c4: (66,),
    0x1c5: (66,),
    0x1c8: (16,),
    0x1c9: (16,),
    0x1cb: (7,),
    0x1cc: (83,),
    0x1cd: (33,),
    0x1ce: (40,),
    0x1cf: (43,),
    0x1d1: (51,),
    0x1d2: (66,),
    0x1d3: (66,),
    0x1d4: (66,),
    0x1d5: (66,),
    0x1d6: (66,),
    0x1dd: (16,),
    0x1de: (36,),
    0x1df: (7,),
    0x1e0: (44,),
    0x1e1: (5,),
    0x1e2: (16,),
    0x1e3: (45,),
    0x1e4: (20,),
    0x1e5: (20,),
    0x1ea: (46,),
    0x1f2: (15,),
    0x1f3: (15,),
    0x1f4: (24,),
    0x1f5: (47,),
    0x1f6: (36,),
    0x1f7: (60,),
    0x1f8: (60,),
    0x1fa: (66,),
    0x1fb: (66,),
    0x1fc: (66,),
    0x1fd: (66,),
    0x1fe: (66,),
    0x1ff: (68,),
    0x201: (1,),
    0x202: (47,),
    0x204: (69,),
    0x206: (84,),
    0x207: (24,),
    0x208: (64,),
    0x209: (65,),
    0x20a: (65,),
    0x20b: (23,),
    0x20c: (70,),
    0x215: (71,),
    0x216: (71, 72),
    0x217: (8,),
    0x227: (90,),
    0x228: (36,),
    0x229: (36,),
    0x22a: (87,),
    0x22b: (91,),
    0x232: (36,),
    0x235: (89,),
    0x236: (85,),
    0x239: (86,),
    0x23a: (88,),
    0x249: (36,),
    0x24a: (60,),
    0x24e: (34,),
    0x24f: (34,),
    0x250: (34,),
    0x251: (34,),
    0x252: (34,),
    0x253: (60,),
    0x254: (34,),
    0x255: (34,),
    0x25c: (60,),
    0x260: (34, 66),
    0x261: (66,),
    0x262: (66,),
    0x263: (66,),
    0x264: (34,),
    0x265: (34,),
    0x266: (34,),
    0x267: (34,),
    0x268: (34,),
    0x269: (34,),
    0x26a: (34,),
    0x26b: (35,),
    0x26c: (35,),
    0x26e: (66,),
    0x26f: (66,),
    0x270: (66,),
    0x271: (66,),
    0x272: (66,),
    0x273: (66,),
    0x274: (66,),
    0x275: (66,),
    0x276: (66,),
    0x277: (66,),
    0x278: (60,),
    0x279: (60,),
    0x27a: (60,),
    0x27b: (60,),
    0x27c: (60,),
    0x282: (60,),
    0x283: (60,),
    0x284: (60,),
    0x290: (34,),
    0x291: (34,),
    0x292: (34,),
    0x293: (34,),
    0x294: (34,),
    0x2a4: (35,),
    0x2a5: (35,),
    0x2a6: (35,),
    0x2a7: (35,),
    0x2a8: (35,),
    0x2ef: (66,),
    0x2f0: (66,),
    0x2f1: (66,),
    0x2f2: (66,),
    0x2f3: (66,),
    0x2f4: (66,),
    0x2f5: (66,),
    0x2f6: (66,),
    0x2f7: (66,),
    0x2f8: (66,),
    0x2f9: (66,),
    0x2fa: (66,),
    0x2fb: (66,),
    0x30a: (20,),
    0x30b: (20,),
    0x30c: (5,),
    0x30d: (66,),
    0x30e: (66,),
    0x30f: (66,),
    0x310: (66,),
    0x311: (60,),
    0x312: (60,),
    0x313: (60,),
    0x314: (34,),
    0x315: (35,),
    0x316: (34,),
    0x317: (34,),
    0x318: (1,),
    0x319: (24,),
    0x31a: (89,),
    0x31b: (45,),
    0x31c: (86,),
    0x31d: (46,),
    0x31e: (43,),
    0x321: (40,),
    0x322: (33,),
    0x323: (88,),
    0x324: (15,),
    0x325: (15,),
    0x326: (15,),
    0x327: (34,),
    0x32c: (8,),
    0x32e: (70,),
    0x331: (70,),
}

# The patcher's own drop routes (theMainScene::VF2HandleDropOnMobileFurniture, generator source), run before the
# hot spots: item -> (when, what the route starts).
PATCHER_DROP_ROUTES = {
    0x220: ('with "Behavior Patches" on', 'Doing yoga'),
    0x2aa: ('with "Add mobile furniture behaviors" on', 'Playing with holiday candles'),
    0x2ad: ('with "Add mobile furniture behaviors" on', 'the Christmas tree for the family'),
    0x2ae: ('with "Add mobile furniture behaviors" on', 'the Christmas tree for the family'),
    0x2af: ('with "Add mobile furniture behaviors" on', 'the dreidel game for the family'),
    0x2b0: ('with "Add mobile furniture behaviors" on', 'Stealing egg nog'),
    0x2b1: ('with "Add mobile furniture behaviors" on', 'Enjoying the figurines'),
    0x2b2: ('with "Add mobile furniture behaviors" on', 'Enjoying the figurines'),
    0x2b3: ('with "Add mobile furniture behaviors" on', 'Enjoying the figurines'),
    0x2b4: ('with "Add mobile furniture behaviors" on', 'Enjoying the figurines'),
    0x2b5: ('with "Add mobile furniture behaviors" on', 'Enjoying the figurines'),
    0x2b8: ('with "Add mobile furniture behaviors" on', 'the menorah for the family'),
    0x2bd: ('with "Add mobile furniture behaviors" on', 'Enjoying the figurines'),
    0x2be: ('with "Add mobile furniture behaviors" on', "the Santa's cookies route"),
    0x2c0: ('with "Add mobile furniture behaviors" on', 'Enjoying the figurines'),
    0x2c1: ('with "Add mobile furniture behaviors" on', 'Checking the decorations'),
    0x2c2: ('with "Add mobile furniture behaviors" on', 'Enjoying the figurines'),
    0x2c3: ('with "Add mobile furniture behaviors" on', 'Enjoying the figurines'),
    0x2c4: ('with "Add mobile furniture behaviors" on', 'Checking the decorations'),
    0x2c5: ('with "Add mobile furniture behaviors" on', 'Enjoying the figurines'),
    0x2c6: ('with "Add mobile furniture behaviors" on', 'Checking for stocking stuffers'),
    0x2c7: ('with "Add mobile furniture behaviors" on', 'Checking for stocking stuffers'),
    0x2c8: ('with "Add mobile furniture behaviors" on', 'Checking the decorations'),
    0x2c9: ('with "Add mobile furniture behaviors" on', 'Checking the decorations'),
    0x2da: ('with "Add mobile furniture behaviors" on', 'the balloons'),
    0x2db: ('with "Add mobile furniture behaviors" on', 'a birthday celebration for the family'),
    0x2dc: ('with "Add mobile furniture behaviors" on', 'Poking cake'),
    0x2dd: ('with "Add mobile furniture behaviors" on', 'Checking out the presents'),
    0x2de: ('with "Add mobile furniture behaviors" on', 'the lounger route (relaxing, reading, studying, sitting, a nap or sleep; refused in bad weather)'),
    0x2df: ('with "Add mobile furniture behaviors" on', 'the lounger route (relaxing, reading, studying, sitting, a nap or sleep; refused in bad weather)'),
    0x2e0: ('with "Add mobile furniture behaviors" on', 'the lounger route (relaxing, reading, studying, sitting, a nap or sleep; refused in bad weather)'),
    0x2e1: ('with "Add mobile furniture behaviors" on', 'the lounger route (relaxing, reading, studying, sitting, a nap or sleep; refused in bad weather)'),
    0x2e6: ('with "Add mobile furniture behaviors" on', 'the patio table route (preparing drinks, or drinking them while ready; refused for a child or with little food)'),
    0x2e7: ('with "Add mobile furniture behaviors" on', 'Adjusting umbrella'),
    0x2e8: ('with "Add mobile furniture behaviors" on', 'the picnic table route (preparing a picnic, or eating it while ready; refused for a child or with little food)'),
    0x328: ('with "Add mobile furniture behaviors" on', 'the picnic table route (preparing a picnic, or eating it while ready; refused for a child or with little food)'),
    0x329: ('with "Add mobile furniture behaviors" on', 'the patio table route (preparing drinks, or drinking them while ready; refused for a child or with little food)'),
    0x32a: ('with "Behavior Patches" on', 'Doing yoga'),
    0x32b: ('with "Add mobile furniture behaviors" on', 'the lounger route (relaxing, reading, studying, sitting, a nap or sleep; refused in bad weather)'),
    0x32c: ('with "Behavior Patches" on', 'the exercise bike (walking or running, 50% each)'),
    0x32d: ('with "Behavior Patches" on', 'the home gym workout'),
    0x32e: ('with "Behavior Patches" on', 'ping-pong'),
    0x32f: ('with the patcher', 'the spa treatments (giving or receiving one)'),
    0x330: ('with the patcher', 'the spa treatments (giving or receiving one)'),
    0x331: ('with "Behavior Patches" on', 'ping-pong'),
}


def _action(bid: int) -> str:
    return ACTION_ITEMS[bid][0]


def _money(value: int) -> str:
    return f"${value:,}"


def _generation(lock: int) -> str:
    return "from the start" if lock <= 0 else f"from generation {lock}"


def _store_lines() -> list[Fact]:
    """Every store row, in the store's groups (spec section 23)."""
    out: list[Fact] = []
    add = out.append
    cat = ("GetCategoryItemCount 0x46B6D0 / GetCategoryItem 0x46B210 / GetPrice 0x46B9F0 / GetLockGenerationLevel run "
           "as linked")

    # ------------------------------------------------------------------ The store: prices and buying
    add(_f(STORE, "Prices are in coins ($). The store's own discounts, from the price code: On Sale furniture costs "
                  "half (rounded down); groceries and organics cost half with the Food Club; Advanced Career Training "
                  "costs its price times (the selected family member's career level + 1).", C,
           "CalcPrice 0x48ACB0: category 3 halves; items 4..0xB halve with HaveFoodClub; item 0x10F x (level + 1)"))
    add(_f(STORE, WITH_PATCHER + "with the Health Plan, items 0x18 to 0x36 cost a quarter (price x 25 / 100, rounded "
                  "down): the 10 medicines and 17 of the Flea Market's goods, the Sweet Mango, Perfect Bananas, both "
                  "perfumes, Multivitamins, hand gel, Sunscreen, Towelette, the 4 fruit, licorice, mint and cinnamon "
                  "candies, the Anti-spam Software and the 3 Profession Magazines.", C,
           "B200 GetPrice 0x46BA3B: lea eax,[ecx-0x18]; cmp eax,0x1E; gs+0x25B1D; imul 0x19, / 100"))
    add(_f(STORE, UNPATCHED + "the Health Plan's quarter price covers only the 10 medicines (items 0x18 to 0x21), and "
                  "the Special Upgrades page does not sell the Health Plan.", C,
           "stock exe sha256 1582d9e8: GetPrice 0x4B9DE0 lea edx,[eax-0x18]; cmp edx,9"))
    add(_f(STORE, f"Patcher option \"{OPTION_CHEATS}\", on: the 2x, 5x and 100x Prices rows multiply every price after "
                  "those discounts. Off (and in the unpatched game): no multiplier.", C,
           "VF2ApplyPriceMultiplier on the CalcPrice return (discoveries.md B150; generator source)"))
    add(_f(STORE, "Buying: food, medicine, Flea Market goods and outfits go to the tray, one use each; furniture and "
                  "pets go to storage and the house opens in decorate mode; upgrades, renovations and services act at "
                  "once. Upgrades, renovations and the Rockhound Certificate are kept for good. The game saves after "
                  "every purchase.", C, "HandlePurchaseItem 0x48BF20: AddItem 0x4AB330 / HandleUpgrade 0x48C2E0 / "
                                        "AddToStorageAndAward 0x4B6A30; TakeOne owned flag for rows whose field +4 is 1; "
                                        "SaveCurrentGame"))
    add(_f(STORE, "\"From generation N\": the store keeps the item locked until the family tree counts N generations. "
                  "Lock 0 is from the start.", C, "CInventoryManager::IsLocked / CFurnitureManager::IsLocked: lock > "
                                                  "CFamilyTree::NumGenerations"))
    add(_f(STORE, "Mood points: every 3 age units (30 minutes of game time) the game adds up each family member's mood points (the list in "
                  "Needs and upkeep, and the items below), moves happiness by a hundredth of the total, at most 5 "
                  "points, then halves the total.", C, "UpdateHappinessState 0x4CBE90: trend / 100 clamped to -5..5, "
                                                       "then trend / 2"))
    add(_f(STORE, "Needs change in steps, each capped from 1 to 100: an energy loss when energy is below 10, or a gain "
                  "above 80, is halved; the same for hunger; a health loss below 15, or a gain above 90, is halved.", C,
           "CVillagerState::AdjustEnergy / AdjustHunger / AdjustHealth / AdjustHappiness"))
    add(_f(STORE, "Rewards and scolding: a reward raises the likelihood of what the family member is doing by a "
                  "twentieth of the way to its highest (at least 1 step); a scolding lowers it by a fifteenth of the "
                  "way to its lowest (at least 1). The candies use these.", C,
           "theMainScene::InvokeReward / InvokeScolding: weight +max(1,(max-w)/20) / -max(1,(w-min)/15)"))
    add(_f(STORE, "Actions: what an item makes a family member do is named in its entry, and what each action itself "
                  "changes is in the Actions group. \"As part of the action\" changes are planned steps of the "
                  "action: each applies once, when its step plays.", C,
           "CVillagerPlans::ProcessCurrentPlan: each planned change calls the matching Adjust once and marks the step done"))
    add(_f(STORE, WITH_PATCHER + "the Flea Market shows all 36 of its goods at all times; it never changes (the "
                  "game's tip still says three times a day; there is no Flea Market clock in real time or game time). "
                  f"This is the option \"{OPTION_FLEA}\", on by default; with it off the Flea Market is the "
                  "unpatched game's, below.", E,
           "GetCategoryItemCount 0x46B6D0 / GetCategoryItem 0x46B210 call VF2GetExpandedFleaMarketCount / Item "
           "0x4B9A90 / 0x4B9AB0 first (36 for category 15); the stock rotation 0x46BEB0 is never reached; after B204 "
           "both return -1 unless the .vf2flea byte is 1 (generator source; tests/test_b200_store_refresh.py runs "
           "both states of a build from feat/r-refreshes-store)"))
    add(_f(STORE, UNPATCHED + "the Flea Market shows 5 of its 36 goods, picked at random, and changes them every 6 "
                  "hours of real time: the first time it is opened more than 6 real hours after the last change it picks 5 "
                  "new ones (the time counts while paused and while the game is closed). The game's tip says three "
                  "times a day.", E,
           "stock exe sha256 1582d9e8: the store menu's Flea Market row (table 0x5346E0 row 1, category 15) -> "
           "SetStoreCategory 0x432050(15) -> GetCategoryItemCount 0x4BB0A0 -> MaybeUpdateRotatingItems 0x4BA710, "
           "run as linked after Reset 0x4BA8F0: 5 goods at real s T, the same 5 at T + 21,600, 5 new at "
           "T + 21,601 and at T + 86,400; next change = real s + 21,600"))
    add(_f(STORE, f"Patcher option \"{OPTION_FLEA}\" (on by default; every patched build before it always "
                  "listed the 36): with it on, all 36 goods are always in stock, even a good the unpatched "
                  "game's Flea Market sold out (with the option off, or in a save first played unpatched) and the "
                  "3 the game stocks only one of (the Towelette, the Anti-spam Software, the Rockhound "
                  "Certificate; earlier patched builds sold those once). A repeat purchase is the game's own: "
                  "the Towelette and the Anti-spam Software go to the tray again (nothing with a full tray, as "
                  "for any good), the Rockhound Certificate stays owned, and no goal counts any of them. An owned "
                  "Anti-spam Software or certificate keeps its checkmark. The save's own stock counts are not "
                  "changed and count again when the option is off.", E,
           "CInventoryManager::Reset: stock count = itemInfo field 4 (-1 for 33 goods, 1 for 0x29, 0x33, 0x10A); "
           "the unpatched pick sets each pooled good's count to 1; TakeOne lowers a count above 0; "
           "GetNumAvailable 0 -> \"sold out\" (DrawVisibleStoreItem image 0x27A, HandleMouse string 0x6C1); "
           "the patcher's GetNumAvailable hook answers 1 for the 36 while .vf2flea is 1; HandlePurchaseItem: "
           "items below E1h TakeOne + ToolTray.AddItem, 0x10A TakeOne (owned byte) + HandleUpgrade (no case), "
           "IncrementProgress only for items 4..0xB; VF2StoreDrawNumAvailable 0 for an owned one-off "
           "(HaveUpgrade); each emulated in a branch build, 4 repeat purchases each "
           "(tests/test_b200_store_refresh.py)"))
    add(_f(STORE, f"Patcher option \"{OPTION_REFRESH}\" (a cheat, on by default), on the Flea Market page: "
                  "R or Shift+R always makes the unpatched game's own pick happen now: 5 goods shuffled the "
                  "game's way, each set to one in stock, and the next pick 6 hours of real time later. "
                  f"R always redraws; with \"{OPTION_FLEA}\" on you won't see a change in the Flea Market list: "
                  "all 36 stay listed, and every one still reads as in stock whatever count the pick set.", E,
           "vf2refresh_b200.dll: next-pick time InventoryManager+4A0h = 0, then MaybeUpdateRotatingItems called "
           "directly (the old time is put back if the real clock is 0), then the store's own "
           "SetStoreCategory(0Fh); the .vf2flea byte only decides the listing (36, or the pick's 5); emulated "
           "with .vf2flea 0 and 1, including 2 purchases of each of the 36 after R (tests/test_b200_store_refresh.py)"))
    add(_f(STORE, "On Sale: 3 furniture items, changed every game day (24 hours of game time, 24 real hours at Normal speed; the clock "
                  "stops while paused), at half price. Buying one takes it off the list.", C,
           "spec 16: MaybeUpdateSaleItems 0x46C000; CalcPrice category 3; HandlePurchaseItem TakeOne"))

    # ------------------------------------------------------------------ Food and Medicine
    add(_f(FOOD, "The Food and Medicine tab: 18 items, the same with and without the patcher.", E,
           cat + "; stock 0x4BB0A0 category 0xE: the same 18"))
    add(_f(FOOD, "Groceries are placed on the kitchen table (anywhere else: \"Groceries must be placed in the "
                 "kitchen.\" and the bag stays in the tray). Each bag gives its food group to everyone at home for "
                 "24 hours of real time (see Needs and upkeep) and everyone at home starts Putting away "
                 "groceries. With the Food Club each costs half.", C, "HandleMouseDown 0x49EE90: kitchenTableRect1, UpdateNutritionAllVillagers "
                                        "0x4C74E0 (expiry real s + 86,400), MakeAllVillagersDoIt"))
    for _iid, name, price, group, organic in GROCERY_ITEMS:
        food = 250 if organic else 150
        extra = ""
        if organic and group != "Grains":
            extra = (" Each family member at home also gets 5 to 14 mood points and happiness +0 to +2.")
        elif organic:
            extra = (" Unlike the other organics it gives no mood points or happiness: the code passes the organic "
                     "flag only for Dairy, Meats and Fruits and Veggies.")
        add(_f(FOOD, f"{name}: {_money(price)} ({_money(price // 2)} with the Food Club): +{food} food and the "
                     f"{group} food group.{extra}", C,
               "HandleMouseDown grocery cases (case table 0x4A003E), FoodStore Adjust 150 / 250", sub=True))
    add(_f(FOOD, "Medicines are given to the family member they are dropped on, and each is used up when given. "
                 "Hiccups have no medicine; they wear off (6 to 17 hours of real time). With the Health Plan each costs a "
                 "quarter.", C, "HandleMouseDown 0x49EE90 cases 0x18..0x21; symptoms state+0x5C..0x62"))
    for name, price, effect in MEDICINE_ITEMS:
        add(_f(FOOD, f"{name}: {_money(price)} ({_money(price * 25 // 100)} with the Health Plan): {effect}.", C,
               "HandleMouseDown cases 0x18..0x21", sub=True))

    # ------------------------------------------------------------------ Flea Market
    add(_f(FLEA, "The Flea Market's goods are given to the family member they are dropped on (the Weed Bomb, the "
                 "Anti-spam Software and the movies say where they go) and are used up when given.", C,
           "DispatchRotatingSundry 0x49CB90 -> UseTool"))
    add(_f(FLEA, "Bottled weather: the family member \"Deploying Bottled Weather\" gets happiness +1 to +3, walks to "
                 "one fixed spot of the house map (x 1,539, y 208), bends, waits, and then the weather changes. Stormy, Foggy and Snowing last "
                 "6 to 12 minutes of game time; Normal 15 to 40; then the weather carries on as in Weather.", C,
           "DispatchRotatingSundry cases 0x3B / 0x3C / 0x41 / 0x42: PlanToChangeWeather(3 / 0 / 4 / 5) -> "
           "CWeather::SetCurrent 0x4CCF20 (0 Normal, 1 Sunny, 2 Raining, 3 Stormy, 4 Foggy, 5 Snowing)"))
    for name, price, effect, label in FLEA_ITEMS:
        hp = f" ({_money(price * 25 // 100)} with the Health Plan)" if name in HEALTH_PLAN_FLEA else ""
        add(_f(FLEA, f"{name}: {_money(price)}{hp}: {effect}.", label,
               "DispatchRotatingSundry 0x49CB90 (case table 0x49DD64 / 0x49DCF4)", sub=True))
        if name == "Bottled Tropical Sunshine":
            add(_f(FLEA, "The code reading, which contradicts the live report above, so both are given: the bottle "
                         "sets type 0, the plain sky "
                         "the owner calls Normal, and makes it daytime for 180 seconds of game time (B200 "
                         "0x49D890: push 0 before PlanToChangeWeather; the plan step calls OverrideNight(180) at 0x4CAFDC).", C,
                   "B200 0x49CB90+0xD00; every B204 variant pushes 0; SetCurrent case 1 = CSunBeam::Reset", sub=True))

    # ------------------------------------------------------------------ Special Upgrades
    add(_f(UPGRADES, "The Special Upgrades act on the whole family at once.", C, "HandleUpgrade 0x48C2E0 cases "
                                                                                    "0x111..0x116"))
    for name, price, effect, label in SPECIAL_ITEMS:
        add(_f(UPGRADES, f"{name}: {_money(price)}: {effect}.", label, "HandleUpgrade 0x48C2E0", sub=True))
    add(_f(UPGRADES, "Lotto Ticket: $100. The game rolls 1 of 10,000 as rand() mod 10,000 (each of 0 to 2,767 comes "
                     "4 times in the 32,768 values, each other value 3 times): $50,000 at 4 in 32,768 (0.012%); $25,000 at 8 (0.024%); $5,000 at 80 "
                     "(0.244%); $1,000 at 800 (2.441%); $750 at 2,000 (6.104%); a free grocery bag (Grains, Dairy, "
                     "Meats or Fruits and Veggies, a quarter each) at 12,044 in 32,768 times 50.05% (18.40% in all) when "
                     "a tray place is free; otherwise nothing.", C,
           "HandleUpgrade 0x48C2E0 case 0x114 (desktop $LN50): GetRandom(10000) < 1 / 3 / 23 / 223 / 723, else < 4056 "
           "with rand(100) < 50 and IsSlotAvailable -> AddItem(4 + rand(4))", sub=True))
    add(_f(UPGRADES, "The four rows the patcher adds (not in the unpatched game; see Money and interest): each costs "
                     "its price while the family does not have it; while it does, its price is $0 and buying it "
                     "removes it.", C,
           "VF2GetVisibleSpecialUpgradePrice 0x4B9F60 returns 0 while owned; 0x4B8B50 toggles cases 0x117..0x11A"))
    add(_f(UPGRADES, "Brokerage Account: $10,000 (with the patcher): interest 11% a game day (24 hours of game time) instead of 10%; bought "
                     "again ($0) it sets interest to 1%; each later purchase ($10,000) adds 2 points, 3%, 5%, 7%, 9% "
                     "and back to 11% (see Money and interest).", E,
           "0x4B8B50 case 0x117 run as linked from 0.10: 0.11, 0.01, 0.03, 0.05, 0.07, 0.09, 0.11", sub=True))
    add(_f(UPGRADES, "Food Club: $10,000 (with the patcher): 500 food and all four food groups each game day (24 hours of game time), every "
                     "missed day delivered; 60 food whenever a family member finds less than 60; groceries at half "
                     "price. Bought again ($0) the deliveries stop.", C,
           "JoinFoodClub; CFoodStore::Update 0x464F70; CalcPrice; 0x4B8B50 case 0x118 clears the flag", sub=True))
    add(_f(UPGRADES, "Health Plan: $10,000 (with the patcher): the quarter prices above, kept in the save. Bought again "
                     "($0) prices are back to full.", C, "0x4B8B50 case 0x119: gs+0x25B1D and record 0xA8 bit 0",
           sub=True))
    add(_f(UPGRADES, "Lucky Rock: $77,777 (with the patcher): a collectible about every 37 seconds of real time instead of 73, "
                     "rare 8% and uncommon 26% instead of 4% and 13% (see Collectibles). Bought again ($0) it is "
                     "gone.", C, "0x4B8B50 case 0x11A: CCollectableItem+0x8A8", sub=True))
    add(_f(UPGRADES, f"Patcher option \"{OPTION_CHEATS}\", on: 45 more rows, every one $0 (43 on this page, 2 offered "
                     "from a family member's details). Off, and in the unpatched game: none of them.", C,
           "work/patch_mobile_furniture_pack.py CHEAT_UPGRADE_ITEMS (45 rows, 2 details_only); "
           "VF2ApplyVisibleSpecialUpgrade cases 0x11B..0x15B"))
    for name, effect in CHEAT_ITEMS:
        end = "" if effect.endswith('"') else "."
        add(_f(UPGRADES, f"{name}: {effect}{end}", C, "VF2ApplyVisibleSpecialUpgrade (generator source)", sub=True))

    # ------------------------------------------------------------------ Services
    add(_f(SERVICES, "Services act on the family member selected when the store was opened. The children's list has "
                     "Boarding School, Systematic Desensitization, Psychotherapy and Higher Learning Classes; the "
                     "adults' list has the last three and Advanced Career Training and Career Change. The same in the "
                     "unpatched game.", E, cat + ": categories 0x13 (4) and 0x12 (5); stock the same"))
    for name, price, effect, ages in SERVICE_ITEMS:
        add(_f(SERVICES, f"{name}: {_money(price)} ({ages}): {effect}.", C,
               "HandleUpgrade 0x48C2E0, selected member gs+0x25CC4 (desktop $LN10..$LN18)", sub=True))

    # ------------------------------------------------------------------ Home Renovation
    add(_f(RENOVATION, "The Home Renovation tab: 10 renovations, the same prices with and without the patcher. "
                       "Buying one: everyone at home starts the same action, workers come and build it, and the "
                       "room opens for good. Each one owned gives every family member 5 mood points every 30 "
                       "minutes of game time.", C,
           cat + "; HandleUpgrade cases 0xE1..0xEA (ActivateCondemnedArea, SetProp); UpdateHappinessState +5 per "
                 "renovation 0xE1..0xEA"))
    for _iid, name, price, lock, extra in RENOVATION_ITEMS:
        add(_f(RENOVATION, f"{name}: {_money(price)}, {_generation(lock)}.{extra}", E if not extra else C,
               cat + "; UpdateHappinessState like 65 (0x41) with item 0xE6" if extra else cat, sub=True))
    add(_f(RENOVATION, f"Patcher option \"{OPTION_RENOVATIONS}\", on: 15 room remodels are added to this tab; each "
                       "redraws its room with the remodel's picture, and none is among the 10 renovations that give "
                       "mood points. Off, and in the unpatched game: "
                       "none of them.", C,
           "MOBILE_RENOVATION_STYLE_CATALOG (generator source); UpdateHappinessState counts only 0xE1..0xEA"))
    for name, price, lock in MOBILE_RENOVATION_ITEMS:
        add(_f(RENOVATION, f"{name}: {_money(price)}, {_generation(lock)}.", C,
               "MOBILE_RENOVATION_STYLE_CATALOG", sub=True))
    add(_f(RENOVATION, f"Patcher option \"{OPTION_BATHROOM2}\", on: 5 remodels of the 2nd Bathroom, only after the 2nd "
                       "Bathroom renovation (before it the price is refunded with \"Bathroom 2 must be renovated "
                       "first before this can be bought.\"). One is shown at a time: buying one replaces the one "
                       "shown, and buying the shown one again ($0) removes it. Off, and in the unpatched game: none.", C,
           "AI_BATHROOM2_STYLE_CATALOG; VF2ApplyAIBathroom2Style / VF2GetAIBathroom2Price (generator source)"))
    for name, price in BATHROOM2_REMODEL_ITEMS:
        add(_f(RENOVATION, f"{name}: {_money(price)}.", C, "AI_BATHROOM2_STYLE_CATALOG", sub=True))

    # ------------------------------------------------------------------ Career upgrades
    add(_f(CAREER_UPGRADES, "The store's Career tab: 31 upgrades for the three workplaces, the same with and without "
                            "the patcher. Each one owned adds 1 to its workplace's equipment level (the office has 11, "
                            "the kitchen 10, the workshop 10). Buying one: everyone at home starts the same action.", C,
           cat + "; CTech::Level counts the owned upgrades (at most 12); HandleUpgrade cases 0xEB..0x109"))
    add(_f(CAREER_UPGRADES, "Each piece of successful work adds (20 + 4 x the workplace's equipment level) / (career "
                            "level + 1) progress, rounded down, then times 7 for a Beginner, 3 for a Novice, 2 for an "
                            "Apprentice; a Master adds none. 3,000 progress is a promotion. A family member without a "
                            "career counts equipment level 1.", C,
           "CVillagerSkills::AdvanceCareer: (4 x Tech + 20) / (level + 1), x7 / x3 / x2 at levels 0 / 1 / 2, none from 7"))
    add(_f(CAREER_UPGRADES, "Equipment and likes: a family member whose Likes show \"cooking\" gets 500 x (the kitchen's "
                            "level - 1) mood points every 30 minutes of game time, so -500 with no kitchen upgrade and 0 with "
                            "1; \"carbs\" the same with the office's level, and \"computers\" with the workshop's.", C,
           "UpdateHappinessState: likes 0x27 / 0x52 / 0x51 with CTech::Level 0 / 1 / 2: (25 x level - 25) x 20"))
    for workplace in (2, 1, 3):
        for _iid, name, price, lock, wp in CAREER_UPGRADE_ITEMS:
            if wp != workplace:
                continue
            extra = ""
            if _iid == 0x108:
                extra = (" It also gives 10 mood points every 30 minutes of game time to each family member whose Likes show "
                         "\"computers\".")
            add(_f(CAREER_UPGRADES, f"{name} ({WORKPLACES[wp]}): {_money(price)}, {_generation(lock)}.{extra}",
                   C if extra else E, cat + ("; UpdateHappinessState like 0x51 with 0x108" if extra else ""),
                   sub=True))

    # ------------------------------------------------------------------ Furniture and Accessories
    tabs = (("General Appliances", 18, 15), ("Living Room", 108, 88), ("Dining Room", 27, 26), ("Bedroom", 84, 74),
            ("Outdoors", 38, 12), ("Accessories", 109, 47), ("Toys", 21, 21))
    add(_f(FURNITURE, WITH_PATCHER + "the furniture tabs list " + ", ".join(f"{t} {p}" for t, p, _s in tabs)
           + " items, with the patcher's furniture (marked \"added by the patcher\" below).", E,
           cat + ": categories 0, 4, 5, 6, 7, 0xA, 8"))
    add(_f(FURNITURE, UNPATCHED + "the same tabs list " + ", ".join(f"{t} {s}" for t, _p, s in tabs)
           + " items; every one of them has the same price and generation as with the patcher.", E,
           "stock exe sha256 1582d9e8: GetCategoryItemCount 0x4BB0A0 / GetCategoryItem 0x4BAA50 run as linked; "
           "furniture table 0x54C87C = B200 0x564F48 for 0x1AD..0x2A8 (price, lock, name)"))
    add(_f(FURNITURE, "Every piece placed in the house, of any kind, gives every family member 1 mood point every 30 "
                      "minutes of game time, up to 30 pieces. Pieces in storage count for nothing.", C,
           "UpdateHappinessState: min(CFurnitureManager::NumberOfItemsPlaced, 30)"))
    add(_f(FURNITURE, "The pieces below that name a like also give mood points every 30 minutes of game time, while placed, "
                      "to each family member whose Likes show it. The Fish Bowl gives its 15 to everyone, like or not "
                      "(the code skips the like check for it).", C,
           "UpdateHappinessState 0x2ED..0x55F: HaveUpgrade -> CFurnitureManager::IsInWorld; 0x202 jumps past the "
           "Contains(0x19) check"))
    add(_f(FURNITURE, "Dropping a family member on a piece starts one of the actions of the hot spots on its placement "
                      "map; each entry below names them (the hot spot's code picks one by its own checks, which are "
                      "not listed). What each action changes is in the Actions group. The patcher changes no stock piece's hot "
                      "spots; it runs its own drop routes first for the pieces that say so, and a piece with neither "
                      "has no drop action.", C,
           "theMainScene::HandleDropOnHotSpot -> CContentMap::GetHotSpot ((cell >> 18) & 0x7F) -> CHotSpot::Dispatch "
           "(handlers set in CHotSpot::CHotSpot) -> NewBehavior; the *.png.fmap of each piece (GetFmapName: ImageList "
           "0x579E48), stock and B204 maps compared"))
    add(_f(FURNITURE, "The need changes of the patcher's own drop routes (the pieces that name one):", C,
           "work/patch_mobile_furniture_pack.py: VF2HandleMobileChaise; VF2RunMobilePreparingDrinks / DrinkAtPatioChair / PreparingPicnic / EatAtPicnicTable; VF2ExerciseBikeWalk / Run (CBehavior::WorkoutTreadmill / RunningOnTreadmill); VF2GymDonorBehaviors (WorkingOut -4 energy +5 dirt; QuickWorkout -7 energy +7 dirt +5 trend; GetRandom(2)); VF2PingPongPlay (PlayingPooltable); VF2PlanSpaTreatment; the umbrella, birthday and holiday helpers plan no PlanToInc / PlanToDec"))
    for text in (
            "the lounger route: one roll of 80, plus 70 minus energy below 70 energy, plus 3 x (45 minus energy) "
            "below 45 energy: under 20 relaxing (dirtiness +4, mood points +1, energy +2), under 40 reading (no "
            "need changes), under 60 studying (mood points +1), under 80 sitting (energy +3), then a nap "
            "(dirtiness +2, energy +7 to 11) or, in the last part, sleep (dirtiness +2, energy +10); refused in "
            "Raining, Stormy, Foggy or Snowing weather;",
            "the patio table and picnic table routes: preparing (energy -7, dirtiness +7, mood points +5, hunger "
            "+7); drinking (hunger -10, dirtiness +4, toilet need +6) or the picnic (hunger -40, dirtiness +4, "
            "toilet need +6); refused in Raining, Stormy, Foggy or Snowing weather, for a child under 14 or with "
            "under 31 food;",
            "the exercise bike: walking as Walking on the treadmill (dirtiness +8, mood points +4) or running as "
            "Running on the treadmill (dirtiness +6, mood points +2, energy -8), 50% each;",
            "the home gym and Doing yoga: working out (energy -4, dirtiness +5) or a quick workout (energy -7, "
            "dirtiness +7, mood points +5), 50% each;",
            "ping-pong: as Playing pool, no need changes;",
            "the spa treatments: receiving one, dirtiness +2 and energy +7 to 11; giving one, no need changes;",
            "the umbrella, birthday and holiday routes: no need changes."):
        add(_f(FURNITURE, text, C, "work/patch_mobile_furniture_pack.py: the route's helper"))
    listed = set()
    for tab, _p, _s in tabs:
        add(_f(FURNITURE, f"{tab}:", E, cat, sub=False))
        for iid, name, price, lock, item_tabs, added in FURNITURE_ITEMS:
            if item_tabs[0] != tab or iid in listed:
                continue
            listed.add(iid)
            parts = [f"{name}: {_money(price)}, {_generation(lock)}"]
            if len(item_tabs) > 1:
                parts.append("also on the " + " and ".join(t for t in item_tabs[1:]) + " tab")
            if added:
                parts.append("added by the patcher")
            text = "; ".join(parts) + "."
            label, evidence = E, cat
            drops = []
            for spot in FURNITURE_HOTSPOTS.get(iid, ()):
                for bid in HOTSPOT_ACTIONS[spot][1]:
                    if _action(bid) not in drops:
                        drops.append(_action(bid))
            if iid in PATCHER_DROP_ROUTES:
                when, what = PATCHER_DROP_ROUTES[iid]
                text += f" Dropped on, {when}: the patcher's own route, {what}"
                text += ("; otherwise: " + ", ".join(drops) + "." if drops else ".")
                label, evidence = C, cat + "; VF2HandleDropOnMobileFurniture"
            elif drops:
                text += " Dropped on: " + ", ".join(drops) + "."
                label, evidence = C, cat + "; its map's hot spots"
            if iid == 0x202:
                text += " 15 mood points to everyone, while placed."
                label, evidence = C, cat + "; UpdateHappinessState 0x202"
            elif iid in FURNITURE_LIKE_BONUS:
                points, likes = FURNITURE_LIKE_BONUS[iid]
                text += f" {points} mood points for a liking of {_likes(*likes)}, while placed"
                group = FURNITURE_BONUS_GROUPS.get(iid)
                text += f" (once, however many of the {group} are placed)." if group else "."
                label, evidence = C, cat + "; UpdateHappinessState like bonus"
            add(_f(FURNITURE, text, label, evidence, sub=True))

    # ------------------------------------------------------------------ Pets
    add(_f(PETS, WITH_PATCHER + "the Pets tab lists 14 pets and the Food and Water Bowls (listed with the "
                 "Accessories); the Turtle and the Hamster are the patcher's (\"Add unused pets\").", E,
           cat + ": category 0x15, 15 items"))
    add(_f(PETS, UNPATCHED + "the Pets tab lists 12 pets and the bowls, without the Turtle and the Hamster.", E,
           "stock exe sha256 1582d9e8: category 0x15 run as linked, 13 items"))
    add(_f(PETS, "A pet goes to storage when bought and is placed like furniture: placed, it counts as one placed "
                 "piece (1 mood point for everyone every 30 minutes of game time, within the 30-piece limit) and walks about, "
                 "following family members. No pet code changes any need. Dropping a family member on a pet starts "
                 "Petting the pet (no need changes), and the pet walks to the family member and waits.", C,
           "CFurnitureManager::DropFurniture -> CPetManager::SpawnPet, placed flag counted by NumberOfItemsPlaced; "
           "no Pet*/PetAI/PetBehavior/PetPlans function calls an Adjust* or PlanToInc*/Dec*; HandleDropOnPet: "
           "behaviour 0x19A Petting"))
    for _iid, name, price, lock, added in PET_ITEMS:
        tail = "; added by the patcher" if added else ""
        add(_f(PETS, f"{name}: {_money(price)}, {_generation(lock)}{tail}.", E, cat, sub=True))

    # ------------------------------------------------------------------ Clothing and Hairstyles
    add(_f(CLOTHING, WITH_PATCHER + "the tab lists 214 items: the 6 outfits below and the patcher's Outfit store, 54 "
                     "outfit bodies and 50 hairstyles for each sex.", E, cat + ": category 0xD"))
    add(_f(CLOTHING, UNPATCHED + "the tab lists the 6 outfits only.", E,
           "stock exe sha256 1582d9e8: category 0xD run as linked, 6 items"))
    add(_f(CLOTHING, "An outfit goes to the tray and is dropped on a family member of its sex: it changes that "
                     "member's outfit and the member starts Checking out new clothes. On the other sex: \"This outfit is for a male!\" (or female) and it stays in "
                     "the tray.", C, "HandleMouseDown 0x49EE90 cases 0x49 / 0x4A: gender +0x6A58, outfit +0x6A84"))
    add(_f(CLOTHING, "Which outfit a stock row gives: the store holds one body value per row and hands it over when "
                     "bought. Discount Store rows hold a body from 0 to 31, Department Store rows 32 to 43, Designer "
                     "rows 44 to 49, each picked evenly; the store picks new ones when the Clothing tab is next checked "
                     "4 hours of game time (14,400 game seconds) after the last pick.", C,
           "CInventoryManager::MaybeUpdateOutfits: GenCommonBodyType rand(32), GenUncommonBodyType 32 + rand(12), "
           "GenRareBodyType 44 + rand(6), next pick game s + 0x3840; TakeOne copies +0x408 + id x 4"))
    add(_f(CLOTHING, f"Patcher option \"{OPTION_REFRESH}\" (a cheat, on by default): on this tab R or Shift+R "
                     "picks the 6 stock outfits again at once, with the same odds (Discount 0 to 31, Department "
                     "32 to 43, Designer 44 to 49), and the next timed pick is 4 hours of game time later, as after "
                     "any pick. The hairstyles are not picked at random, so they stay; an outfit already bought "
                     "keeps its own. Unpatched (and with the option off) no key does this.", E,
           "vf2refresh_b200.dll: CInventoryManager::MaybeUpdateOutfits(true), the forced pick Reset makes; "
           "emulated: GetRandom bounds 20h, 20h, 0Ch, 0Ch, 6, 6, only +450h..+464h and +470h written "
           "(tests/test_b200_store_refresh.py)"))
    add(_f(CLOTHING, WITH_PATCHER + "each outfit in the tray keeps the outfit it was bought with: the tray shows "
                     "each one's own picture, and dropping it on a family member gives that one (part of Fix Vanilla "
                     "Game Bugs). The pictures are kept beside the save, so they stay after loading it; an outfit "
                     "bought before the fix shows and gives what the unpatched game does.", C,
           "vf2outfits_b200.dll: the buy's AddItem (HandlePurchaseItem), both SwapSlots calls, the DrawItem calls "
           "of CToolTray::Draw / DrawToolInHand and both GetOutfit calls of HandleMouseDown 0x49EE90; run on the "
           "B200 code in tests/b200_outfits_scenarios.py, not yet seen in a running game"))
    add(_f(CLOTHING, UNPATCHED + "every outfit of a sex in the tray shows, and puts on, the last one bought: two "
                     "male outfits bought with different pictures both show the second, and the first one dropped "
                     "on a family member gives the second.", C,
           "stock exe sha256 1582d9e8: TakeOne 0x4BA0FE copies the row's body into +0x468 (rows 0x12..0x14) / "
           "+0x46C (0x15..0x17); GetOutfit 0x4BA6E0 and DrawItem 0x4BA24C / 0x4BA25D read 0x49 from +0x468 and "
           "0x4A from +0x46C; the apply 0x442C8E / 0x442D14 writes it to +0x6A84; a tray place holds only "
           "(item, uses)"))
    for name, price, lock in (("Discount Store Male Outfit", 75, 0), ("Discount Store Female Outfit", 75, 0),
                              ("Department Store Male Outfit", 200, 2), ("Department Store Female Outfit", 200, 2),
                              ("Designer Male Outfit", 1500, 4), ("Designer Female Outfit", 1500, 4)):
        add(_f(CLOTHING, f"{name}: {_money(price)}, {_generation(lock)}.", E, cat, sub=True))
    add(_f(CLOTHING, "The patcher's Outfit store: no generation lock; outfit bodies 0 to 49 cost $75 and the Holiday "
                     "bodies 50 to 53 cost $500; every hairstyle costs $75. Each goes to the tray when bought.", E,
           cat + "; VF2GetOutfitStorePrice 0x4B9E80; VF2GetOutfitStoreLockGeneration 0x4B9D40 (0); "
                 "VF2PurchaseOutfitStoreItem 0x4BA100 -> AddItem"))
    add(_f(CLOTHING, "In hand, an Outfit-store row is treated as the stock outfit tool of its sex, with its own body "
                     "value (or hairstyle) as the one to give: dropped on a family member of that sex it gives that "
                     "body value (or hairstyle) and the member starts Checking out new clothes; on the other sex it "
                     "says \"This outfit is for a male!\" (or female) and stays in the tray.", C,
           "VF2NormalizeOutfitToolInHand 0x4BA000 (generator source): CToolTray::GetToolInHand / GetToolInUse return "
           "0x49 / 0x4A and set the stock outfit body or the selected head; HandleMouseDown cases 0x49 / 0x4A"))
    for sex, base in (("Female", 0), ("Male", 1)):
        for body in range(54):
            holiday = " Holiday" if body >= 50 else ""
            price = 500 if body >= 50 else 75
            add(_f(CLOTHING, f"{sex}{holiday} Outfit Body {body:02d}: {_money(price)}; outfit body {body}.", E,
                   f"item {0x400 + 0x40 * base + body:#x}; name string {0xBED + 2 * (54 * base + body):#x}", sub=True))
    for sex, base in (("Female", 0), ("Male", 1)):
        for style in range(50):
            add(_f(CLOTHING, f"{sex} Hairstyle {style:02d}: $75; hairstyle {style}.", E,
                   f"item {0x480 + 0x40 * base + style:#x}; name string {0xF2B + 2 * (50 * base + style):#x}",
                   sub=True))

    # ------------------------------------------------------------------ Actions
    add(_f(ACTIONS, "Every action an item or a furniture piece starts, with every need change its code plans, across "
                    "all of its branches. Each planned change applies once, when its step plays. No action's need "
                    "changes depend on age, time of day or weather, and its rolls pick only its steps, poses and "
                    "sounds. An action whose piece is missing, taken or out of reach plans no need changes; the "
                    "other branches that change them are given with their action. \"No need changes\": the "
                    "action's code plans none (it moves, animates or speaks only).", C,
           "CBehavior handlers (ids from CBehavior::CBehavior SetMacro): PlanToInc* / PlanToDec* calls and arguments"))
    for bid, (name, changes, branched) in ACTION_ITEMS.items():
        what = ", ".join(changes) if changes else "no need changes"
        tail = ACTION_BRANCHES.get(bid, "")
        tail = f"; {tail}" if tail else ""
        add(_f(ACTIONS, f"{name}: {what}{tail}.", C, f"behaviour {bid:#x}", sub=True))
    return out


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
