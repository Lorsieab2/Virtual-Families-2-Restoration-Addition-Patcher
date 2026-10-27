"""Game Mechanics: every store item's entry (src/vf2_game_mechanics.py, the groups from "The store: prices and
buying" to "Clothing and Hairstyles"), pinned to its source.

The page tests always run.  The executable tests re-run the store's own code as linked (unicorn) and are skipped
without the executables: VF2_B200_CORE_EXE = the matrix build's core `Virtual Families 2 - B200.exe` (sha256
5cad4050...) and the patcher's vanilla payload (or VF2_STOCK_EXE, sha256 1582d9e8...).  Nothing starts the game and
nothing on disk is written.
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
import vf2_game_mechanics as gm  # noqa: E402

FACTS = gm.facts()
TEXT = gm.render(FACTS)


def _lines(group):
    return [f for f in FACTS if f.group == group]


def _entry(group, start):
    found = [f for f in _lines(group) if f.text.startswith(start)]
    assert len(found) == 1, (group, start, len(found))
    return found[0]


# ---------------------------------------------------------------------------------------------------------- the page
def test_the_store_groups_follow_collectibles_in_the_store_menus_order():
    index = gm.GROUPS.index(gm.COLLECTIBLES)
    assert gm.GROUPS[index + 1:index + 1 + len(gm.STORE_GROUPS)] == gm.STORE_GROUPS
    assert gm.GROUPS[-1] == gm.INDEX


def test_every_store_item_has_its_own_entry():
    furniture = [f.text for f in _lines(gm.FURNITURE) if f.sub]
    assert len(furniture) == len(gm.FURNITURE_ITEMS) == 355
    for iid, name, price, lock, tabs, added in gm.FURNITURE_ITEMS:
        hits = [t for t in furniture if t.startswith(f"{name}: ${price:,}, ")]
        assert len(hits) >= 1, name
        assert ("added by the patcher" in hits[0]) == added, name
    assert len([f for f in _lines(gm.PETS) if f.sub]) == len(gm.PET_ITEMS) == 14
    assert len([f for f in _lines(gm.FLEA) if f.sub]) == len(gm.FLEA_ITEMS) == 36
    assert len([f for f in _lines(gm.FOOD) if f.sub]) == len(gm.GROCERY_ITEMS) + len(gm.MEDICINE_ITEMS) == 18
    assert len([f for f in _lines(gm.CAREER_UPGRADES) if f.sub]) == len(gm.CAREER_UPGRADE_ITEMS) == 31
    assert len([f for f in _lines(gm.SERVICES) if f.sub]) == 6
    # 6 stock rows, the Lotto Ticket, the patcher's 4 and the 45 Cheat Upgrades rows
    assert len([f for f in _lines(gm.UPGRADES) if f.sub]) == 5 + 1 + 4 + 45
    assert len([f for f in _lines(gm.RENOVATION) if f.sub]) == 10 + 15 + 5
    # the 6 stock outfits and the Outfit store: 54 bodies and 50 hairstyles for each sex
    assert len([f for f in _lines(gm.CLOTHING) if f.sub]) == 6 + 2 * 54 + 2 * 50


def test_no_vague_words_and_no_cloudy():
    assert not re.search(r"\b(some|etc\.|a bit)\b", TEXT, re.I), re.search(r".{40}\b(some|etc\.|a bit)\b.{40}", TEXT,
                                                                             re.I)
    assert "Cloudy" not in TEXT and "cloudy" not in TEXT


def test_the_weather_bottles_use_the_owners_weather_names():
    assert "Bottled Tropical Sunshine: $50: the weather becomes Normal, type 0" in TEXT
    assert "Bottled Tropical Rain: $50: the weather becomes Stormy, rain with lightning" in TEXT
    assert "Fog In a Bottle: $50: the weather becomes Foggy" in TEXT
    assert "Snow in a Bottle: $50: the weather becomes Snowing" in TEXT
    assert "Sunny (type 1, the grey tint with sun beams) is never set by a bottle" in TEXT


def test_health_plan_and_food_club_prices_are_the_price_codes_arithmetic():
    for name, price, _effect in gm.MEDICINE_ITEMS:
        assert f"{name}: ${price:,} (${price * 25 // 100:,} with the Health Plan)" in TEXT, name
    for _iid, name, price, _group, _organic in gm.GROCERY_ITEMS:
        assert f"{name}: ${price} (${price // 2} with the Food Club)" in TEXT, name
    # the Flea Market goods inside the patched range 0x18..0x36 show their quarter price, the others none
    assert "Sweet Mango: $10 ($2 with the Health Plan)" in TEXT
    assert "Kitchen Profession Magazine: $300 ($75 with the Health Plan)" in TEXT
    assert "Blood Orange: $10: " in TEXT and "Imported Candy: $25: " in TEXT


def test_the_lotto_odds_are_rand_mod_10000_counted():
    counts = [0] * 10000
    for raw in range(32768):
        counts[raw % 10000] += 1

    def odds(lo, hi):
        return sum(counts[lo:hi])
    assert (odds(0, 1), odds(1, 3), odds(3, 23), odds(23, 223), odds(223, 723), odds(723, 4056)) == (
        4, 8, 80, 800, 2000, 12044)
    half = sum(1 for raw in range(32768) if raw % 100 < 50) / 32768
    assert f"{100 * half:.2f}%" == "50.05%"
    assert f"{100 * 12044 / 32768 * half:.2f}%" == "18.40%"
    line = _entry(gm.UPGRADES, "Lotto Ticket: $100.")
    for needle in ("$50,000 at 4 in 32,768", "$25,000 at 8", "$5,000 at 80", "$1,000 at 800", "$750 at 2,000",
                   "12,044 in 32,768 times 50.05% (18.40% in all)"):
        assert needle in line.text
    assert line.label == gm.VERIFIED_C


def test_the_formerly_unconfirmed_purchases_are_read_from_the_purchase_path():
    for group, start in ((gm.TIME, "The store's Time Warp"), (gm.HEALTH, "The medicines (see Food and Medicine)"),
                         (gm.LEAVING, "Boarding School (a Service, $1,500)"), (gm.UPGRADES, "Time Warp: $2,000"),
                         (gm.UPGRADES, "Health Plan: $10,000"), (gm.STORE, "On Sale: 3 furniture items")):
        assert _entry(group, start).label == gm.VERIFIED_C, start


def test_every_unconfirmed_store_line_says_what_is_unknown():
    for fact in FACTS:
        if fact.group in gm.STORE_GROUPS and fact.label == gm.UNCONFIRMED:
            assert re.search(r"not decoded|not traced|has not decoded", fact.text), fact.text


def test_like_bonuses_name_the_likes_the_game_shows():
    likes = [s.strip() for s in ("ants, crowds, resting, laundry, medicine, turnips, butterflies, flowers, bees, the "
                                 "dark, snakes, wind, rocks, heights, playing, exploring, blue, green, red, yellow, "
                                 "bushes, sand, sunlight, wood, crab meat, fish, fruit, flies, swimming, running, "
                                 "studying, dancing, birds, work, lifting, surprises, jokes, sleeping, jumping, "
                                 "cooking, eating, dreaming, talking, holidays, vegetables, quiet, clouds, dirt, "
                                 "plants, rain, fog, sitting, stories, thunder, lightning, stars, water exercising, "
                                 "strolling, toys, insects, grass, spiders, roses, crickets, bathing, shaving, combing "
                                 "hair, makeup, flossing, brushing teeth, cleaning, loose socks, dusting, organizing, "
                                 "TV, Internet, spam, reading, technology, snacking, tools, computers, carbs, meat, "
                                 "milk, eggs, BBQ, burgers, pizza, sweets, pasta, soup, chocolate, peanut butter, "
                                 "soda, coffee, rice, bread, chicken, solitude, trains, cars, airplanes, robots, "
                                 "trash, fixing, shopping, pinball, music, art, gophers").split(",")]
    for number, name in gm.LIKE_NAMES.items():   # string 0x7AF, split on commas as CLikeList::GetListAsString does
        assert likes[number] == name, number
    assert "Flat Screen TV: $5,000, from generation 3; also on the Living Room tab. Dropped on: Watching TV. 15 mood " \
           "points for a liking of \"Internet\", while placed." in TEXT
    assert "Pinball Machine: $3,550, from generation 4. Dropped on: Playing pinball. 45 mood points for a liking of " \
           "\"music\"" in TEXT
    assert "(once, however many of the 4 grills are placed)" in TEXT


def test_the_career_progress_formula():
    line = _entry(gm.CAREER_UPGRADES, "Each piece of successful work adds")
    assert "(20 + 4 x the workplace's equipment level) / (career level + 1)" in line.text
    assert "times 7 for a Beginner, 3 for a Novice, 2 for an Apprentice" in line.text


# ----------------------------------------------------------------------------------------- the B200 core executable
# The executable tests' harnesses are imported inside their fixtures: importing them here would skip this whole
# module (the page tests above too) wherever pefile or unicorn is not installed.
b200 = None

RESET, NUM_GENERATIONS, GET_PRICE, GET_LOCK = 0x46C130, 0x457A20, 0x46B9F0, 0x46B870
DISPATCH, SET_CURRENT, HANDLE_UPGRADE = 0x49CB90, 0x4CCF20, 0x48C2E0
TABS = {"General Appliances": 0, "Living Room": 4, "Dining Room": 5, "Bedroom": 6, "Outdoors": 7, "Accessories": 0xA,
        "Toys": 8}


@pytest.fixture(scope="module")
def core():
    global b200
    import test_game_mechanics_b200_exe as b200
    exe = b200.core_exe()
    e = b200.Emu(exe)
    e.stubs[NUM_GENERATIONS] = (lambda: 1, 0)
    e.call(RESET, (), ecx=b200.INVENTORY)
    e.image = exe.read_bytes()
    import pefile
    e.pe = pefile.PE(str(exe), fast_load=True)
    return e


def _items(e, category):
    return [e.call(b200.CATEGORY_ITEM, (category, k), ecx=b200.INVENTORY)
            for k in range(e.call(b200.CATEGORY_COUNT, (category,), ecx=b200.INVENTORY))]


def _bytes(e, va, n):
    return e.pe.get_data(va - 0x400000, n)


def test_the_furniture_tabs_prices_and_locks_are_the_exes(core):
    seen = {}
    for tab, category in TABS.items():
        for iid in _items(core, category):
            seen.setdefault(iid, []).append(tab)
    page = {row[0]: row for row in gm.FURNITURE_ITEMS}
    assert set(page) == set(seen)
    for iid, (_iid, _name, price, lock, tabs, _added) in page.items():
        assert core.call(GET_PRICE, (iid,), ecx=b200.INVENTORY) == price, hex(iid)
        assert core.call(GET_LOCK, (iid,), ecx=b200.INVENTORY) == lock, hex(iid)
        assert tuple(seen[iid]) == tabs, hex(iid)


def test_pets_career_renovations_food_and_flea_market_prices_are_the_exes(core):
    pets = [i for i in _items(core, 0x15) if i != 0x26D]
    assert pets == [row[0] for row in gm.PET_ITEMS]
    for iid, _name, price, lock, _added in gm.PET_ITEMS:
        assert (core.call(GET_PRICE, (iid,), ecx=b200.INVENTORY), core.call(GET_LOCK, (iid,), ecx=b200.INVENTORY)) \
            == (price, lock)
    career = _items(core, 0x1)
    assert sorted(career) == sorted(row[0] for row in gm.CAREER_UPGRADE_ITEMS)
    for iid, _name, price, lock, _wp in gm.CAREER_UPGRADE_ITEMS + tuple(r[:4] + (0,) for r in gm.RENOVATION_ITEMS):
        assert (core.call(GET_PRICE, (iid,), ecx=b200.INVENTORY), core.call(GET_LOCK, (iid,), ecx=b200.INVENTORY)) \
            == (price, lock), hex(iid)
    assert _items(core, 0x11) == [row[0] for row in gm.RENOVATION_ITEMS]
    food = _items(core, 0xE)
    assert food == [row[0] for row in gm.GROCERY_ITEMS] + list(range(0x18, 0x22))
    prices = [core.call(GET_PRICE, (iid,), ecx=b200.INVENTORY) for iid in food]
    assert prices == [row[2] for row in gm.GROCERY_ITEMS] + [row[1] for row in gm.MEDICINE_ITEMS]
    flea = _items(core, b200.FLEA_MARKET)
    assert [core.call(GET_PRICE, (iid,), ecx=b200.INVENTORY) for iid in flea] == [row[1] for row in gm.FLEA_ITEMS]


def test_the_bottles_weather_types(core):
    # DispatchRotatingSundry pushes the EWeather for PlanToChangeWeather: Rain 3, Sunshine 0, Fog 4, Snow 5
    for offset, kind in ((0xC32, 3), (0xD00, 0), (0xEF2, 4), (0xFC0, 5)):
        assert _bytes(core, DISPATCH + offset, 2) == bytes([0x6A, kind]), hex(offset)
    # CWeather::SetCurrent's switch: case 1 is the sun beams' reset, case 0 the plain Normal weather
    table = struct.unpack("<I", _bytes(core, SET_CURRENT + 0x34, 4))[0]
    cases = [struct.unpack("<I", _bytes(core, table + 4 * k, 4))[0] - SET_CURRENT for k in range(6)]
    assert cases == [0x38, 0x41, 0x59, 0x4D, 0x78, 0x84]


def test_the_health_plan_range_and_the_store_discounts(core):
    assert _bytes(core, 0x46BA3B, 6) == bytes.fromhex("8d41e883f81e")          # lea eax,[ecx-0x18]; cmp eax,0x1E
    calc = _bytes(core, 0x48ACB0, 0x8A)
    assert bytes.fromhex("83bed400000003") in calc                              # category 3: On Sale halves
    assert bytes.fromhex("8d4bfc83f907") in calc                                # items 4..0xB with the Food Club
    assert bytes.fromhex("81fb0f010000") in calc                                # 0x10F x (level + 1)


def test_the_lotto_thresholds(core):
    body = _bytes(core, HANDLE_UPGRADE + 0x635, 0xA4)
    assert body.startswith(bytes.fromhex("6810270000"))                         # GetRandom(10000)
    for needle in ("83fe01", "83fe03", "83fe17", "81fedf000000", "81fed3020000", "81fed80f0000", "be50c30000",
                   "bea8610000", "be88130000", "bee8030000", "beee020000"):
        assert bytes.fromhex(needle) in body, needle


# ---------------------------------------------------------------------------------------------- the stock executable
stock = None


@pytest.fixture(scope="module")
def stock_emu():
    global stock
    import test_game_mechanics_stock_exe as stock
    e = stock.Emu(stock.stock_exe())
    e.call(stock.RESET, (), ecx=stock.INVENTORY)
    return e


def test_the_unpatched_tabs(stock_emu):
    def count(category):
        return stock_emu.call(stock.CATEGORY_COUNT, (category,), ecx=stock.INVENTORY)
    unpatched = _entry(gm.FURNITURE, gm.UNPATCHED).text
    for tab, category in TABS.items():
        assert f"{tab} {count(category)}" in unpatched, tab
    assert count(0x15) == 13 and count(0xD) == 6 and count(0xE) == 18 and count(0x11) == 10 and count(0x1) == 31
    assert stock_emu.file_bytes(0x4B9DE0, 6) == bytes.fromhex("8d50e883fa09")     # lea edx,[eax-0x18]; cmp edx,9


def test_every_named_action_is_in_the_actions_group():
    names = {name for name, _changes, _branched in gm.ACTION_ITEMS.values()}
    for _handler, actions in gm.HOTSPOT_ACTIONS.values():
        for bid in actions:
            assert bid in gm.ACTION_ITEMS, hex(bid)
    for spots in gm.FURNITURE_HOTSPOTS.values():
        for spot in spots:
            assert spot in gm.HOTSPOT_ACTIONS, spot
    for needle in ("Sleeping (adults)", "Taking a nap", "Doing Kung Fu", "Exercising outdoors", "Celebrating marriage",
                   "Watching TV", "Studying", "Telling a story", "Listening to a story", "Putting away groceries",
                   "Checking out new clothes", "Petting the pet", "Running away", "Using the toilet"):
        assert needle in names, needle
        assert needle in TEXT
    actions = {f.text.split(":")[0]: f.text for f in _lines(gm.ACTIONS) if f.sub}
    assert actions["Sleeping (adults)"] == "Sleeping (adults): energy +10, dirtiness +2."
    assert actions["Barbecuing!"] == "Barbecuing!: hunger -7, dirtiness +4, toilet need +4, mood points +4."
    assert actions["Doing Kung Fu"] == "Doing Kung Fu: no need changes."
    # the hammock's hot spot (5) starts Relaxing in the hammock (behaviour 0x24); the Hammock piece carries it
    assert gm.HOTSPOT_ACTIONS[5] == ("Hammock", (0x24,)) and 5 in gm.FURNITURE_HOTSPOTS[0x1E1]
    left = [f.text for f in FACTS if f.group in gm.STORE_GROUPS and f.label == gm.UNCONFIRMED]
    assert len(left) == 1 and "patcher's own drop routes" in left[0], left
    assert "Dropped on, with the patcher: the patcher's own route, the spa treatments" in TEXT


def test_the_cure_row_says_what_its_code_clears():
    # VF2ClearIllnesses (work/patch_mobile_furniture_pack.py): symptoms state+0x5C..0x62 and their expiries and both
    # infections (+0x80 word), what the game's own cures write.  Since the 27 October 2026 B204 update it no longer
    # zeroes +0x84..+0x97, the four food-group flags and expiries (UpdateNutritionAllVillagers); emulated on the built
    # executables in tests/test_cure_keeps_food_groups_exe.py.
    line = _entry(gm.UPGRADES, "Clear All Illnesses: ")
    assert "every symptom and both infections are cured" in line.text
    assert "the food groups and everything else are kept" in line.text
    assert "Before the 27 October 2026 B204 update the same code also cleared all four food groups" in line.text


def test_the_imported_candy_cure_skips_a_runny_nose():
    # theMainScene::DispatchRotatingSundry's health +20 branch: word state+0x80 = 0, then ClearSymptom 2, 5, 3, 1,
    # 4, 0 -- never 6, the runny nose (B200 desktop object theMainScene.obj)
    assert "health +20 with every symptom but a runny nose and both infections cured" in TEXT
