"""The Picture Maker's effects and animations, animals and insects, furniture and objects and food pictures for
Virtual Families 2, assembled as the game draws them, and whether the game ever draws each picture and cell (see
vf2_game_pictures for the catalogue they join).

Where the rules come from (the B200 desktop objects, work/desktop_obj_files, which keep the game's symbols;
tests/test_art_misc.py runs the drawing code in Unicorn through tests/vf2_misc_emu.py):

* The effects: CFloatingAnim::m_sAnim is a table of 64 effects (16 bytes each: image, frames, random first frame;
  `ANIM_TABLE`). CFloatingAnim::LoadAssets turns each image into a picture grid. AddAnim(effect, place, delay, loop,
  motion, priority, centred) starts one (effects 0xC and 0x10 take a fixed cell instead of a motion and fade it).
  CFloatingAnim::Update moves every effect on every 7th call, one frame each `delay` moves, to its last frame, then
  loops or ends. CFloatingAnim::Draw(index) draws cell `frame` of the grid through CSceneManager::Draw at alpha 1,
  or, for the fading two, the fixed cell at alpha max(0, 1 - frame x 0.1f); effects of priority 0xA are drawn on top
  through ldwGameWindow::Draw instead.
* Who adds which effect (`ADDED`): every call to CFloatingAnim::AddAnim and to the villagers' and pets'
  PlanToSpawnAnim* (plan steps the plans later hand to AddAnim) with the effect it passes; CRain::Update (0x12 on
  water, 0 on the other wet ground); the furniture's animations (sFurnitureInfo, below). CSmoke's emitters are
  never switched on: CSmoke::Add, the only code that sets an emitter's on byte, is never called (CSmoke::Reset only
  clears them).
* The furniture: sFurnitureInfo itemInfo (252 entries of 0x6C bytes; `LookupFurnitureInfo`): the item, its image,
  and per orientation an animation effect with its offset, and the animation's delay. CFurnitureManager::Draw(index)
  draws a placed item's cell `orientation` at its place through CSceneManager::Draw (the snapping offsets at +0x58
  are off for every item). CFurnitureManager::SetOnState / RestoreAnims start the item's animation for its
  orientation at the item's place plus the offset (delay, loop, priority 5).
* The pets: CPetAnimManager::LoadAssets reads Assets\\petanimpts.dat into a link table of 76 frames; CPetManager::
  DrawPet draws peep_shadow1.png scaled at the pet's feet, then pet_grid.png row = kind, column = frame where
  GetScaledLinkToNextPt puts it (`PET_LINKS`, made by running DrawPet).
* The birds: CBird::Draw (bird.png and bird_shadow.png; `BIRD_POSES`); the ball: CBall::Draw (ball_shadow.png and
  InventoryItems.png cell 5).
* Not assembled here (their files are listed whole and cut by vf2_art_sheets): the butterflies, the pet bowls'
  own pictures, CBubbles, CDecal's food, work and upgrade props, the fridge, the lights and the air purifier.
"""
from __future__ import annotations

import re
import struct

import vf2_game_pictures as gp

TITLE = "Effects, animals, furniture and food"
CHECKED = "Checked against the game's own drawing code ({code}) run in Unicorn."
EFFECT_CHECK = CHECKED.format(code="CFloatingAnim::AddAnim, CFloatingAnim::Update and CFloatingAnim::Draw")
FURNITURE_CHECK = CHECKED.format(code="CFurnitureManager::Draw")
FURNITURE_ON_CHECK = CHECKED.format(code="CFurnitureManager::Draw, CFurnitureManager::SetOnState and "
                                         "CFloatingAnim's AddAnim, Update and Draw")
STEPS_PER_MOVE = 7                       # CFloatingAnim::Update moves the effects on every 7th call
FADE_STEP = 0.10000000149011612          # __real@3dcccccd (0.1f)
FADE_FRAMES = 11                         # frames 0..10: from frame 10 on the fading cell is invisible
ALPHA_NOTE = ("The faded pixels are the game's own: ldwGameWindowImpl::BlitRectWithAlpha at an opacity blends each "
              "pixel as if its alpha were alpha x opacity rounded to the nearest (a half rounds down); checked on "
              "two screens in Unicorn.")


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def game_alpha(a: int, opacity: float) -> int:
    """The alpha ldwGameWindowImpl::BlitRectWithAlpha (full size) blends a pixel of alpha `a` with at `opacity`:
    a x opacity (a float) to the nearest whole number, a half rounding down. With the game's blend
    (colour x a + 127 + under x (255 - a)) >> 8 this is every screen pixel the game makes."""
    import math
    return max(0, math.ceil(a * f32(opacity) - 0.5))


def game_faded(files, name: str, rect: tuple, opacity: float):
    """A cell as BlitRectWithAlpha draws it at `opacity` (full size): its colours, each alpha game_alpha'd."""
    left, top, right, bottom = rect
    out = files.image(name).sub(left, top, right - left, bottom - top).copy()
    d = out.data
    for i in range(3, len(d), 4):
        d[i] = game_alpha(d[i], opacity)
    return out


# CFloatingAnim::m_sAnim: effect -> (image id, frames, random first frame).
ANIM_TABLE = {
    0x00: (465, 10, 0), 0x01: (274, 9, 0), 0x02: (466, 10, 0), 0x03: (467, 10, 0), 0x04: (468, 10, 0),
    0x05: (469, 9, 0), 0x06: (470, 16, 0), 0x07: (471, 10, 0), 0x08: (472, 10, 0), 0x09: (475, 9, 1),
    0x0A: (476, 36, 0), 0x0B: (477, 8, 1), 0x0C: (478, 39, 0), 0x0D: (480, 12, 1), 0x0E: (481, 10, 0),
    0x0F: (492, 10, 0), 0x10: (493, 54, 0), 0x11: (494, 15, 0), 0x12: (495, 3, 0), 0x13: (496, 12, 0),
    0x14: (502, 30, 0), 0x15: (503, 40, 0), 0x16: (504, 50, 0), 0x17: (505, 28, 1), 0x18: (506, 9, 0),
    0x19: (507, 18, 1), 0x1A: (508, 18, 1), 0x1B: (521, 12, 1), 0x1C: (522, 12, 1), 0x1D: (482, 2, 0),
    0x1E: (483, 2, 0), 0x1F: (484, 10, 0), 0x20: (485, 10, 0), 0x21: (486, 10, 0), 0x22: (487, 10, 0),
    0x23: (488, 10, 0), 0x24: (489, 10, 0), 0x25: (490, 10, 0), 0x26: (491, 10, 0), 0x27: (523, 12, 1),
    0x28: (524, 12, 1), 0x29: (525, 18, 1), 0x2A: (526, 18, 1), 0x2B: (496, 12, 0), 0x2C: (498, 12, 0),
    0x2D: (499, 6, 0), 0x2E: (500, 6, 0), 0x2F: (509, 12, 0), 0x30: (510, 12, 0), 0x31: (511, 8, 0),
    0x32: (512, 8, 0), 0x33: (513, 12, 0), 0x34: (514, 12, 0), 0x35: (515, 12, 0), 0x36: (516, 12, 0),
    0x37: (517, 10, 0), 0x38: (518, 10, 0), 0x39: (519, 14, 0), 0x3A: (520, 14, 0), 0x3B: (285, 2, 0),
    0x3C: (286, 4, 0), 0x3D: (287, 4, 0), 0x3E: (204, 1, 0), 0x3F: (205, 1, 0),
}
FADING = (0x0C, 0x10)                    # AddAnim makes the motion argument their fixed cell

# Who starts each effect (the function, as the game names it). Furniture: see FURNITURE_ANIMS.
ADDED = {
    0x00: ("CVillager::ProcessDiving", "CVillager::ProcessJumping", "CVillager::ProcessSwimming",
           "CVillager::AddFootprints", "CPet::ProcessJumping", "CPet::AddFootprints", "CVillagerManager::DrawVillager",
           "theMainScene::HandleMapClick", "theMainScene::DropVillager", "CRain::Update"),
    0x01: ("CBehavior::ChildrenPlayWorkman1", "CBehavior::ChildrenPlayWorkman2"),
    0x02: ("CAchievement::Update",),
    0x03: ("CCollectableItem::Update", "CEnvironment::Update", "theMainScene::HandleMouseDown"),
    0x04: ("theMainScene::HandleMouseDown",),
    0x05: ("CVillager::AddDust", "CPet::AddDust", "theMainScene::HandleMouseMove", "theMainScene::DropVillager",
           "CBehavior::PlayInDirt", "CBehavior::ThrowingRocks", "CBehavior::WorkWorkshop"),
    0x06: ("theMainScene::DispatchRotatingSundry",),
    0x07: ("theMainScene::InvokeReward", "theMainScene::DispatchRotatingSundry"),
    0x09: ("CBehavior::RememberingTheDead",),
    0x0A: ("CBehavior::GoInHouse", "CBehavior::GoInHouseKidBed", "CBehavior::GoInHouseSofa",
           "CBehavior::RememberingTheDead", "the beds' animation (CFurnitureManager::SetOnState)"),
    0x0B: ("CEnvironment::Update", "theMainScene::HandleMouseDown", "theMainScene::DispatchRotatingSundry",
           "CBehavior::FixingLaundryFire", "CBehavior::FixingStove", "CBehavior::KillingAnts",
           "CBehavior::SplashingPool", "CBehavior::SwimmingPool"),
    0x0C: ("theMainScene::HandleMouseMove",),
    0x0D: ("theMainScene::InvokeScolding",),
    0x0F: ("CBehavior::WorkWorkshop",),
    0x10: ("theMainScene::HandleMouseMove",),
    0x11: ("CVillager::AddFootprints", "CPet::AddFootprints"),
    0x12: ("CRain::Update",),
    0x13: ("CEnvironment::Update", "CBehavior::OfficeCarreerWork", "CBehavior::WorkKitchen0",
           "CBehavior::WorkWorkshop", "the barbecues' and the dryer's animation (CFurnitureManager::SetOnState)"),
    0x17: ("CEnvironment::Refresh", "CEnvironment::Update"),
    0x1B: ("CEnvironment::SetProp", "CEnvironment::RefreshProps"),
    0x1C: ("CEnvironment::SetProp",),
    0x1D: ("theMainScene::UpdateScene",),
    0x1E: ("theMainScene::UpdateScene",),
    0x1F: ("CEnvironment::Update",),
    0x20: ("CEnvironment::Update",),
    0x22: ("CBehavior::PreparingAMeal", "CBehavior::WorkKitchen0"),
    0x24: ("CEnvironment::Update",),
    0x25: ("CEnvironment::Update",),
    0x26: ("theMainScene::InvokeScolding", "CBehavior::PlayInPool", "CBehavior::SplashingPool",
           "CBehavior::SwimmingPool"),
    0x27: ("CEnvironment::SetProp",),
    0x28: ("CEnvironment::SetProp",),
    0x2B: ("CBehavior::KillingAnts", "CBehavior::Finishing...Expansion (the ten room expansions)"),
    0x2C: ("CEnvironment::Update",),
    0x3B: ("CEnvironment::Update",),
    0x3C: ("CEnvironment::Update",),
    0x3D: ("CEnvironment::Update",),
}
FURNITURE_ANIMS = (0x0A, 0x13, 0x19, 0x1A, 0x29, 0x2A, 0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36,
                   0x37, 0x38, 0x3E, 0x3F)
NEVER_ADDED = (0x08, 0x0E, 0x14, 0x15, 0x16, 0x18, 0x21, 0x23, 0x39, 0x3A)
NEVER_WHY = ("no code reached from WinMain starts effect {effect:#x}: every CFloatingAnim::AddAnim call and every "
             "PlanToSpawnAnim call passes another effect, CRain::Update passes 0x12 or 0, no furniture's animation "
             "is it, and CSmoke's emitters are never switched on (CSmoke::Add is never called).")

# effect -> (key, label, category)
EFFECTS = {
    0x00: ("waves", "Splash rings in the water", "Effects and animations/Water and steam"),
    0x01: ("chopgreens", "Chopping greens", "Food and cooking/Animations"),
    0x02: ("yellowsparkle", "Yellow sparkle", "Effects and animations/Sparkles"),
    0x03: ("sparkle2", "Small sparkle", "Effects and animations/Sparkles"),
    0x04: ("sparkle", "Sparkle", "Effects and animations/Sparkles"),
    0x05: ("dust", "Dust puff", "Effects and animations/Dust and smoke"),
    0x06: ("algae", "Algae", "Effects and animations/Water and steam"),
    0x07: ("rainbow", "Rainbow", "Effects and animations/Rewards and scolding"),
    0x08: ("bubble", "Bubble", "Effects and animations/Water and steam"),
    0x09: ("candle", "Candle flame", "Effects and animations/Fire and light"),
    0x0A: ("petals", "Falling rose petals", "Effects and animations/Petals"),
    0x0B: ("foam", "Foam", "Effects and animations/Water and steam"),
    0x0D: ("redspray", "Red spray", "Effects and animations/Rewards and scolding"),
    0x0E: ("sharpsparkle", "Sharp sparkle", "Effects and animations/Sparkles"),
    0x0F: ("blurrysparkle", "Soft sparkle", "Effects and animations/Sparkles"),
    0x11: ("footprints", "Footprints", "Effects and animations/Dust and smoke"),
    0x12: ("raindrops", "Raindrops splashing on the water", "Effects and animations/Water and steam"),
    0x13: ("smoke", "Smoke", "Effects and animations/Dust and smoke"),
    0x14: ("reeffish1", "Reef fish (first school)", "Animals and insects/Fish"),
    0x15: ("reeffish2", "Reef fish (second school)", "Animals and insects/Fish"),
    0x16: ("reeffish3", "Reef fish (third school)", "Animals and insects/Fish"),
    0x17: ("bees", "Bees", "Animals and insects/Insects"),
    0x18: ("bubblestrip", "Bubbles rising", "Effects and animations/Water and steam"),
    0x1B: ("eastcpu", "Computer screen (east desk)", "Furniture and objects/Computers"),
    0x1C: ("westcpu", "Computer screen (west desk)", "Furniture and objects/Computers"),
    0x1D: ("email", "New email", "Effects and animations/Messages"),
    0x1E: ("emailbig", "New email (big)", "Effects and animations/Messages"),
    0x1F: ("waterspray", "Water spray", "Effects and animations/Water and steam"),
    0x20: ("faucet", "Running tap", "Effects and animations/Water and steam"),
    0x21: ("boiling", "Boiling water", "Food and cooking/Animations"),
    0x22: ("salad", "Tossing a salad", "Food and cooking/Animations"),
    0x23: ("sawdust", "Sawdust", "Effects and animations/Dust and smoke"),
    0x24: ("shower", "Shower water", "Effects and animations/Water and steam"),
    0x25: ("steam", "Steam", "Effects and animations/Water and steam"),
    0x26: ("drips", "Dripping water", "Effects and animations/Water and steam"),
    0x27: ("westcpulg", "Computer screens (west desk, upgraded)", "Furniture and objects/Computers"),
    0x28: ("eastcpulg", "Computer screens (east desk, upgraded)", "Furniture and objects/Computers"),
    0x2B: ("smoke2", "Smoke (room building and ant spray)", "Effects and animations/Dust and smoke"),
    0x2C: ("roaches", "Cockroaches", "Animals and insects/Insects"),
    0x39: ("bbqmeat_se", "Meat on the barbecue (south-east)", "Food and cooking/Animations"),
    0x3A: ("bbqmeat_sw", "Meat on the barbecue (south-west; the table names the south-east strip again)",
           "Food and cooking/Animations"),
    0x3B: ("ants1", "Ants (first infestation)", "Animals and insects/Insects"),
    0x3C: ("ants2", "Ants (second infestation)", "Animals and insects/Insects"),
    0x3D: ("ants3", "Ants (third infestation)", "Animals and insects/Insects"),
}
# The furniture animations' own words (effect -> what it shows), for the furniture pictures and the cells.
FURNITURE_ANIM_WORDS = {
    0x0A: "rose petals", 0x13: "smoke", 0x19: "television picture", 0x1A: "television picture",
    0x29: "television picture", 0x2A: "television picture", 0x2D: "washing machine running",
    0x2E: "washing machine running", 0x2F: "fish swimming", 0x30: "fish swimming", 0x31: "fire", 0x32: "fire",
    0x33: "pinball lights", 0x34: "pinball lights", 0x35: "pachinko lights", 0x36: "pachinko lights",
    0x37: "slot machine reels", 0x38: "slot machine reels", 0x3E: "food in the bowls", 0x3F: "food in the bowls",
}


# ------------------------------------------------------------------ cells and frames
_ENTRIES: dict = {}


def _entry(image: int) -> gp.Entry:
    """gp.entry_by_id, remembered (the table is read once)."""
    if not _ENTRIES:
        for e in gp.table():
            _ENTRIES.setdefault(e.id, e)
    return _ENTRIES[image]


_CELLS: dict = {}


def _cell(files: gp.GameFiles, image: int, index: int, x: int = 0, y: int = 0, alpha: float = 1.0) -> gp.Draw:
    """gp.cell with every image's cells cut once per game folder."""
    key = (id(files), image)
    cells = _CELLS.get(key)
    if cells is None or cells[0] is not files:
        cells = (files, gp.entry_cells(files, _entry(image)))
        _CELLS[key] = cells
    name, rect = cells[1][min(max(index, 0), len(cells[1]) - 1)]
    return gp.Draw(name, rect, x, y, alpha=alpha)


def _shape(image: int) -> tuple[int, int]:
    entry = _entry(image)
    return (entry.cols or 1), max(1, entry.rows)


def frame_cell(image: int, k: int) -> int:
    """The grid cell frame k shows: column k % columns, row k // columns, a row past the last clamped to the last
    (ldwImageGrid::GetCellRect)."""
    cols, rows = _shape(image)
    return (k % cols) + cols * min(k // cols, rows - 1)


def fade_alpha(frame: int) -> float:
    """CFloatingAnim::Draw for a fading effect: max(0, 1.0f - (float)frame * 0.1f)."""
    a = f32(1.0 - f32(f32(frame) * f32(FADE_STEP)))
    return a if a > 0.0 else 0.0


def effect_frames(effect: int) -> list[tuple[int, int, float]]:
    """(image, cell, alpha) of every frame CFloatingAnim::Draw draws for an effect started from frame 0 with no
    motion (the fading ones with their cell 0)."""
    image, frames, _rnd = ANIM_TABLE[effect]
    if effect in FADING:
        return [(image, 0, fade_alpha(k)) for k in range(frames)]
    return [(image, frame_cell(image, k), 1.0) for k in range(frames)]


# ------------------------------------------------------------------ furniture
ORIENTATION_WORDS = {0: "facing south-east", 1: "facing south-west"}


def orientation_words(o: int, count: int) -> str:
    """Orientations 0 and 1 face south-east and south-west (the furniture's animation strips for them are named SE
    and SW); the four-way items have two more."""
    if count <= 2 or o < 2:
        return ORIENTATION_WORDS.get(o, f"orientation {o + 1}")
    return f"orientation {o + 1} of {count}"


_KINDS = (
    ("Beds", ("bed",)), ("Sofas and couches", ("sofa", "couch", "chaise")), ("Chairs", ("chair", "beanbag", "hammock")),
    ("Tables", ("table", "desk")), ("Storage", ("bookcase", "bookshelf", "credenza", "cradenza", "dresser",
                                                "nightstand", "rack")),
    ("Rugs and mats", ("rug", "mat")), ("Pictures and wall things", ("poster", "painting", "mirror", "clock",
                                                                     "stocking", "wreath", "banner", "string")),
    ("Toys and play", ("toy", "doll", "plush", "teddy", "kids", "sandbox", "trampoline", "pirate", "playstructure",
                       "carousel", "pool", "easel", "drum", "train", "kitchenfor", "balloon", "ballon", "bubble")),
    ("Games and music", ("piano", "guitar", "pinball", "pachinko", "slot", "foosball", "radio", "ipod",
                         "telescope", "tv", "television")),
    ("Appliances", ("washer", "dryer", "bbq", "fireplace", "ironing", "treadmill", "scale", "lamp", "light")),
    ("Plants and decorations", ("leaf", "palm", "tiered", "gnome", "poinsettia", "tree", "snowman", "reindeer",
                                "penguin", "polarbear", "santa", "menorah", "dreidel", "candle", "candy", "cookie",
                                "eggnog", "bow", "cake", "present", "patio", "picnic", "woodpile", "fish", "aquar")),
)


def furniture_kind(name: str) -> str:
    low = name.lower()
    for kind, words in _KINDS:
        if any(w in low for w in words):
            return kind
    return "Other things"


def _stem(name: str) -> str:
    base = name.rsplit("/", 1)[-1]
    return base[:-4] if base.lower().endswith(".png") else base


# sFurnitureInfo itemInfo, in its order: (item, image). The 14 pets (items 0x23B..0x248, image 7: pet_grid.png) are
# left out of the furniture pictures: the pet code draws them.
FURNITURE_ITEMS = (
    (0x1f4, 24), (0x1f5, 25), (0x1f6, 27), (0x1ad, 26), (0x1b0, 29), (0x1f7, 40), (0x1f8, 41), (0x1b1, 23),
    (0x1ae, 31), (0x1af, 32), (0x1b6, 34), (0x1b7, 35), (0x1b8, 36), (0x1b9, 37), (0x1ba, 38), (0x1bb, 39),
    (0x1b2, 30), (0x1b3, 33), (0x1b4, 119), (0x1b5, 120), (0x1e0, 43), (0x1f9, 44), (0x1fa, 45), (0x1fb, 46),
    (0x1fc, 47), (0x1fd, 48), (0x1fe, 49), (0x1bc, 50), (0x218, 135), (0x1ff, 51), (0x1bd, 52), (0x1be, 53),
    (0x1bf, 54), (0x1c0, 55), (0x1c1, 56), (0x1c2, 57), (0x1c3, 58), (0x1c4, 59), (0x1c5, 60), (0x1c6, 326),
    (0x1c7, 327), (0x200, 62), (0x1c8, 63), (0x1c9, 64), (0x1ca, 325), (0x1cb, 65), (0x1cc, 67), (0x201, 68),
    (0x202, 69), (0x203, 70), (0x204, 71), (0x205, 72), (0x206, 73), (0x1e1, 74), (0x207, 76), (0x1cd, 75),
    (0x1ce, 78), (0x1cf, 66), (0x1d0, 79), (0x208, 80), (0x209, 81), (0x20a, 82), (0x20b, 84), (0x1e2, 85),
    (0x1e3, 86), (0x1e4, 87), (0x1e5, 88), (0x20c, 89), (0x20d, 90), (0x20e, 91), (0x20f, 92), (0x210, 93),
    (0x1e6, 98), (0x1e7, 99), (0x1e8, 100), (0x1e9, 101), (0x211, 94), (0x212, 95), (0x213, 96), (0x214, 97),
    (0x1ea, 102), (0x1d1, 103), (0x215, 104), (0x1eb, 105), (0x1ec, 106), (0x1ed, 107), (0x1d2, 108), (0x1d3, 109),
    (0x1d4, 110), (0x1d5, 111), (0x1d6, 112), (0x1d7, 113), (0x1d8, 114), (0x1d9, 115), (0x1da, 116), (0x1db, 117),
    (0x1dc, 118), (0x1dd, 121), (0x216, 122), (0x1ee, 123), (0x1ef, 124), (0x1f0, 125), (0x1f1, 126), (0x1de, 127),
    (0x217, 128), (0x1f2, 130), (0x1f3, 129), (0x219, 131), (0x21a, 132), (0x21b, 133), (0x21c, 134), (0x1df, 136),
    (0x21d, 137), (0x21e, 138), (0x21f, 139), (0x220, 140), (0x221, 141), (0x222, 142), (0x223, 143), (0x224, 144),
    (0x225, 145), (0x226, 146), (0x227, 147), (0x228, 149), (0x229, 150), (0x22a, 151), (0x22b, 152), (0x22c, 153),
    (0x22d, 154), (0x22e, 155), (0x22f, 156), (0x230, 157), (0x231, 158), (0x232, 159), (0x233, 160), (0x234, 161),
    (0x235, 162), (0x236, 163), (0x237, 164), (0x238, 165), (0x239, 166), (0x23a, 167), (0x23b, 7), (0x23c, 7),
    (0x23d, 7), (0x23e, 7), (0x23f, 7), (0x240, 7), (0x241, 7), (0x242, 7), (0x243, 7), (0x244, 7), (0x245, 7),
    (0x246, 7), (0x247, 7), (0x248, 7), (0x249, 148), (0x24a, 168), (0x24b, 169), (0x24c, 170), (0x24d, 171),
    (0x24e, 172), (0x24f, 173), (0x250, 174), (0x251, 175), (0x252, 176), (0x253, 177), (0x254, 178), (0x255, 179),
    (0x256, 180), (0x257, 181), (0x258, 182), (0x259, 183), (0x25a, 184), (0x25b, 185), (0x25c, 186), (0x25d, 187),
    (0x25e, 188), (0x25f, 189), (0x260, 190), (0x261, 191), (0x262, 192), (0x263, 193), (0x264, 194), (0x265, 195),
    (0x266, 196), (0x267, 197), (0x268, 198), (0x269, 199), (0x26a, 200), (0x26b, 201), (0x26c, 202), (0x26d, 203),
    (0x26e, 206), (0x26f, 207), (0x270, 208), (0x271, 209), (0x272, 210), (0x273, 211), (0x274, 212), (0x275, 213),
    (0x276, 214), (0x277, 215), (0x278, 216), (0x279, 217), (0x27a, 218), (0x27b, 219), (0x27c, 220), (0x27d, 221),
    (0x27e, 222), (0x27f, 223), (0x280, 224), (0x281, 225), (0x282, 226), (0x283, 227), (0x284, 228), (0x285, 229),
    (0x286, 230), (0x287, 231), (0x288, 232), (0x289, 233), (0x28a, 234), (0x28b, 235), (0x28c, 236), (0x28d, 237),
    (0x28e, 238), (0x28f, 239), (0x290, 240), (0x291, 241), (0x292, 242), (0x293, 243), (0x294, 244), (0x295, 245),
    (0x296, 246), (0x297, 247), (0x298, 248), (0x299, 249), (0x29a, 250), (0x29b, 251), (0x29c, 252), (0x29d, 253),
    (0x29e, 254), (0x29f, 255), (0x2a0, 256), (0x2a1, 257), (0x2a2, 258), (0x2a3, 259), (0x2a4, 260), (0x2a5, 261),
    (0x2a6, 262), (0x2a7, 263), (0x2a8, 264),
)
# item -> (animation effect per orientation, x offsets, y offsets, delay) for the items with an animation.
FURNITURE_ANIM = {
    0x1f5: ((47, 48, 0, 0), (9, 10, 0, 0), (20, 21, 0, 0), 0),
    0x1ad: ((19, 19, 0, 0), (0, 0, 0, 0), (-20, -40, 0, 0), 0),
    0x1b0: ((19, 19, 0, 0), (0, 0, 0, 0), (-40, -40, 0, 0), 0),
    0x1b1: ((10, 10, 0, 0), (50, 0, 0, 0), (10, 0, 0, 0), 0),
    0x1b6: ((10, 10, 0, 0), (50, 0, 0, 0), (10, 0, 0, 0), 0),
    0x1b7: ((10, 10, 0, 0), (50, 0, 0, 0), (10, 0, 0, 0), 0),
    0x1b8: ((10, 10, 0, 0), (50, 0, 0, 0), (10, 0, 0, 0), 0),
    0x1b9: ((10, 10, 0, 0), (50, 0, 0, 0), (10, 0, 0, 0), 0),
    0x1ba: ((10, 10, 0, 0), (50, 0, 0, 0), (10, 0, 0, 0), 0),
    0x1bb: ((10, 10, 0, 0), (50, 0, 0, 0), (10, 0, 0, 0), 0),
    0x1cb: ((19, 19, 0, 0), (36, 24, 0, 0), (1, -28, 0, 0), 0),
    0x201: ((49, 50, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), 0),
    0x208: ((53, 54, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), 0),
    0x20b: ((51, 52, 0, 0), (-28, -20, 0, 0), (-1, -2, 0, 0), 0),
    0x215: ((55, 56, 0, 0), (4, 6, 0, 0), (6, 6, 0, 0), 0),
    0x1f2: ((41, 26, 0, 0), (36, 24, 0, 0), (40, 38, 0, 0), 35),
    0x1f3: ((42, 25, 0, 0), (19, 12, 0, 0), (12, 13, 0, 0), 35),
    0x1df: ((45, 46, 0, 0), (48, 19, 0, 0), (44, 46, 0, 0), 3),
    0x26d: ((62, 63, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), 0),
}


def _furniture() -> list:
    out = []
    for item, image in FURNITURE_ITEMS:
        anim, dx, dy, delay = FURNITURE_ANIM.get(item, ((0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), 0))
        out.append({"item": item, "image": image, "anim": list(anim), "dx": list(dx), "dy": list(dy), "delay": delay})
    return out


def is_pet(item: int) -> bool:
    """CFurnitureManager::IsPet: items 0x23B..0x248."""
    return 0x23B <= item <= 0x248


# ------------------------------------------------------------------ pets, birds and the ball
# Where CPetManager::DrawPet draws each pet's picture (pet_grid.png row = kind, column = frame) for a pet at (0, 0),
# frame by frame (CPetAnimManager::GetScaledLinkToNextPt over the game's Assets\petanimpts.dat, scale 1: CPet::Scale
# is always 1). Made by running DrawPet; tests/test_art_misc.py checks every one.
PET_LINKS = (
    "-19,5 -19,5 -19,5 -19,5 -19,5 -19,5 -19,5 -19,5 -15,6 -15,6 -15,6 -15,6 -15,6 -15,6 -15,6 -15,6 -10,5 -10,5 -10,5 -10,5 -10,5 -10,5 -10,5 -10,5 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -20,5 -20,5 -20,5 -20,5 -20,5 -20,5 -20,5 -20,5 -18,7 -18,7 -18,7 -18,7 -18,7 -18,7 -18,7 -18,7 -16,4 -16,4 -16,4 -16,4 -16,4 -16,4 -16,4 -16,4 -16,16 -16,16 -16,16 -16,16 -16,16 -16,16 -16,16 -16,16 -14,11 -15,12 -20,9 -17,13 -19,1 -19,1 -19,1 -19,1 -15,1 -15,1 -15,1 -15,1",
    "-22,2 -22,2 -22,2 -22,2 -22,2 -22,2 -22,2 -22,2 -16,5 -16,5 -16,5 -16,5 -16,5 -16,5 -16,5 -16,5 -11,3 -11,3 -11,3 -11,3 -11,3 -11,3 -11,3 -11,3 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -22,-2 -22,-2 -22,-2 -22,-2 -22,-2 -22,-2 -22,-2 -22,-2 -16,3 -16,3 -16,3 -16,3 -16,3 -16,3 -16,3 -16,3 -14,3 -14,3 -14,3 -14,3 -14,3 -14,3 -14,3 -14,3 -16,17 -16,17 -16,17 -16,17 -16,17 -16,17 -16,17 -16,17 -17,14 -17,15 -18,14 -17,15 -20,-4 -20,-4 -20,-4 -20,-4 -15,-5 -15,-5 -15,-5 -15,-5",
    "-23,4 -23,4 -23,4 -23,4 -23,4 -23,4 -23,4 -23,4 -15,4 -15,4 -15,4 -15,4 -15,4 -15,4 -15,4 -15,4 -10,4 -10,4 -10,4 -10,4 -10,4 -10,4 -10,4 -10,4 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -21,1 -21,1 -21,1 -21,1 -21,1 -21,1 -21,1 -21,1 -16,5 -16,5 -16,5 -16,5 -16,5 -16,5 -16,5 -16,5 -14,4 -14,4 -14,4 -14,4 -14,4 -14,4 -14,4 -14,4 -16,18 -16,18 -16,18 -16,18 -16,18 -16,18 -16,18 -16,18 -15,10 -19,12 -17,10 -16,13 -19,-3 -19,-3 -19,-3 -19,-3 -15,-4 -15,-4 -15,-4 -15,-4",
    "-19,4 -19,4 -19,4 -19,4 -19,4 -19,4 -19,4 -19,4 -15,6 -15,6 -15,6 -15,6 -15,6 -15,6 -15,6 -15,6 -8,5 -8,5 -8,5 -8,5 -8,5 -8,5 -8,5 -8,5 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -24,1 -24,1 -24,1 -24,1 -24,1 -24,1 -24,1 -24,1 -17,5 -17,5 -17,5 -17,5 -17,5 -17,5 -17,5 -17,5 -12,5 -12,5 -12,5 -12,5 -12,5 -12,5 -12,5 -12,5 -16,18 -16,18 -16,18 -16,18 -16,18 -16,18 -16,18 -16,18 -15,11 -18,12 -19,12 -17,13 -16,-3 -16,-3 -16,-3 -16,-3 -17,-4 -17,-4 -17,-4 -17,-4",
    "-22,4 -22,4 -22,4 -22,4 -22,4 -22,4 -22,4 -22,4 -16,3 -16,3 -16,3 -16,3 -16,3 -16,3 -16,3 -16,3 -10,2 -10,2 -10,2 -10,2 -10,2 -10,2 -10,2 -10,2 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -21,-1 -21,-1 -21,-1 -21,-1 -21,-1 -21,-1 -21,-1 -21,-1 -15,3 -15,3 -15,3 -15,3 -15,3 -15,3 -15,3 -15,3 -13,3 -13,3 -13,3 -13,3 -13,3 -13,3 -13,3 -13,3 -17,19 -17,19 -17,19 -17,19 -17,19 -17,19 -17,19 -17,19 -17,12 -17,14 -17,13 -17,12 -19,-5 -19,-5 -19,-5 -19,-5 -16,-5 -16,-5 -16,-5 -16,-5",
    "-19,6 -19,6 -19,6 -19,6 -19,6 -19,6 -19,6 -19,6 -12,6 -12,6 -12,6 -12,6 -12,6 -12,6 -12,6 -12,6 -9,5 -9,5 -9,5 -9,5 -9,5 -9,5 -9,5 -9,5 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -25,5 -25,5 -25,5 -25,5 -25,5 -25,5 -25,5 -25,5 -22,6 -22,6 -22,6 -22,6 -22,6 -22,6 -22,6 -22,6 -14,4 -14,4 -14,4 -14,4 -14,4 -14,4 -14,4 -14,4 -16,16 -16,16 -16,16 -16,16 -16,16 -16,16 -16,16 -16,16 -17,13 -19,13 -17,13 -18,13 -10,4 -10,4 -10,4 -10,4 -24,3 -24,3 -24,3 -24,3",
    "-18,5 -18,5 -18,5 -18,5 -18,5 -18,5 -18,5 -18,5 -9,4 -9,4 -9,4 -9,4 -9,4 -9,4 -9,4 -9,4 -9,5 -9,5 -9,5 -9,5 -9,5 -9,5 -9,5 -9,5 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -28,5 -28,5 -28,5 -28,5 -28,5 -28,5 -28,5 -28,5 -23,4 -23,4 -23,4 -23,4 -23,4 -23,4 -23,4 -23,4 -15,2 -15,2 -15,2 -15,2 -15,2 -15,2 -15,2 -15,2 -16,18 -16,18 -16,18 -16,18 -16,18 -16,18 -16,18 -16,18 -17,14 -14,18 -13,13 -20,18 -7,4 -7,4 -7,4 -7,4 -25,3 -25,3 -25,3 -25,3",
    "-17,6 -17,6 -17,6 -17,6 -17,6 -17,6 -17,6 -17,6 -10,4 -10,4 -10,4 -10,4 -10,4 -10,4 -10,4 -10,4 -10,2 -10,2 -10,2 -10,2 -10,2 -10,2 -10,2 -10,2 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -27,5 -27,5 -27,5 -27,5 -27,5 -27,5 -27,5 -27,5 -24,4 -24,4 -24,4 -24,4 -24,4 -24,4 -24,4 -24,4 -16,2 -16,2 -16,2 -16,2 -16,2 -16,2 -16,2 -16,2 -17,20 -17,20 -17,20 -17,20 -17,20 -17,20 -17,20 -17,20 -17,2 -20,5 -17,2 -15,6 -8,4 -8,4 -8,4 -8,4 -26,1 -26,1 -26,1 -26,1",
    "-18,7 -18,7 -18,7 -18,7 -18,7 -18,7 -18,7 -18,7 -10,6 -10,6 -10,6 -10,6 -10,6 -10,6 -10,6 -10,6 -11,11 -11,11 -11,11 -11,11 -11,11 -11,11 -11,11 -11,11 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -24,8 -24,8 -24,8 -24,8 -24,8 -24,8 -24,8 -24,8 -21,5 -21,5 -21,5 -21,5 -21,5 -21,5 -21,5 -21,5 -18,7 -18,7 -18,7 -18,7 -18,7 -18,7 -18,7 -18,7 -16,15 -16,15 -16,15 -16,15 -16,15 -16,15 -16,15 -16,15 -17,11 -16,11 -17,12 -18,10 -15,4 -15,4 -15,4 -15,4 -17,5 -17,5 -17,5 -17,5",
    "-17,8 -17,8 -17,8 -17,8 -17,8 -17,8 -17,8 -17,8 -12,7 -12,7 -12,7 -12,7 -12,7 -12,7 -12,7 -12,7 -12,9 -12,9 -12,9 -12,9 -12,9 -12,9 -12,9 -12,9 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -17,12 -22,8 -22,8 -22,8 -22,8 -22,8 -22,8 -22,8 -22,8 -22,5 -22,5 -22,5 -22,5 -22,5 -22,5 -22,5 -22,5 -15,6 -15,6 -15,6 -15,6 -15,6 -15,6 -15,6 -15,6 -16,17 -16,17 -16,17 -16,17 -16,17 -16,17 -16,17 -16,17 -17,8 -19,6 -17,8 -17,5 -21,6 -21,6 -21,6 -21,6 -13,5 -13,5 -13,5 -13,5",
    "-17,14 -17,14 -17,14 -17,14 -17,14 -17,14 -17,14 -17,14 -15,12 -15,12 -15,12 -15,12 -15,12 -15,12 -15,12 -15,12 -20,17 -20,17 -20,17 -20,17 -20,17 -20,17 -20,17 -20,17 -12,16 -12,16 -12,16 -12,16 -12,16 -12,16 -12,16 -12,16 -21,15 -21,15 -21,15 -21,15 -21,15 -21,15 -21,15 -21,15 -20,16 -20,16 -20,16 -20,16 -20,16 -20,16 -20,16 -20,16 -14,15 -14,15 -14,15 -14,15 -14,15 -14,15 -14,15 -14,15 -18,17 -18,17 -18,17 -18,17 -18,17 -18,17 -18,17 -18,17 -16,15 -16,15 -15,14 -16,15 -18,9 -18,9 -18,9 -18,9 -18,9 -18,9 -18,9 -18,9",
    "-43,16 -43,16 -43,16 -43,16 -43,16 -43,16 -43,16 -43,16 -44,9 -44,9 -44,9 -44,9 -44,9 -44,9 -44,9 -44,9 -27,4 -27,4 -27,4 -27,4 -27,4 -27,4 -27,4 -27,4 -18,5 -18,5 -18,5 -18,5 -18,5 -18,5 -18,5 -18,5 -3,7 -3,7 -3,7 -3,7 -3,7 -3,7 -3,7 -3,7 13,14 13,14 13,14 13,14 13,14 13,14 13,14 13,14 0,26 0,26 0,26 0,26 0,26 0,26 0,26 0,26 -15,30 -15,30 -15,30 -15,30 -15,30 -15,30 -15,30 -15,30 -14,18 -26,19 2,8 -10,19 -35,16 -35,16 -35,16 -35,16 -3,14 -3,14 -3,14 -3,14",
    "-22,11 -22,11 -22,11 -22,11 -22,11 -22,11 -22,11 -22,11 -16,10 -16,10 -16,10 -16,10 -16,10 -16,10 -16,10 -16,10 -14,11 -14,11 -14,11 -14,11 -14,11 -14,11 -14,11 -14,11 -17,17 -17,17 -17,17 -17,17 -17,17 -17,17 -17,17 -17,17 -22,12 -22,12 -22,12 -22,12 -22,12 -22,12 -22,12 -22,12 -18,12 -18,12 -18,12 -18,12 -18,12 -18,12 -18,12 -18,12 -11,10 -11,10 -11,10 -11,10 -11,10 -11,10 -11,10 -11,10 -18,15 -18,15 -18,15 -18,15 -18,15 -18,15 -18,15 -18,15 -17,10 -16,11 -17,10 -20,12 -18,9 -18,9 -18,9 -18,9 -15,8 -15,8 -15,8 -15,8",
    "-20,10 -20,10 -20,10 -20,10 -20,10 -20,10 -20,10 -20,10 -17,11 -17,11 -17,11 -17,11 -17,11 -17,11 -17,11 -17,11 -10,12 -10,12 -10,12 -10,12 -10,12 -10,12 -10,12 -10,12 -16,16 -16,16 -16,16 -16,16 -16,16 -16,16 -16,16 -16,16 -25,13 -25,13 -25,13 -25,13 -25,13 -25,13 -25,13 -25,13 -18,12 -18,12 -18,12 -18,12 -18,12 -18,12 -18,12 -18,12 -10,11 -10,11 -10,11 -10,11 -10,11 -10,11 -10,11 -10,11 -17,14 -17,14 -17,14 -17,14 -17,14 -17,14 -17,14 -17,14 -17,14 -17,15 -19,14 -19,15 -4,4 -4,-11 -4,-25 -4,-38 -5,-16 -5,-3 -5,11 -5,26",
)
PET_FRAMES = 76
PET_NAMES = ("Kitten", "Snow White", "Tabby", "Hairless Cat", "Fluffy Grey Cat", "Beagle", "Yellow Lab", "Black Lab",
             "Longhair Puppy", "A Chihuahua", "Turtle", "Lizard", "Hamster", "Tarantula")
PETS_NOT_SOLD = (0x245, 0x247)            # the Turtle and the Hamster: the original store does not sell them
# DrawPet adds a direction's first frame to frames 0..7: direction -> first frame
PET_DIRECTION_FRAMES = (0x00, 0x10, 0x20, 0x30, 0x38, 0x08, 0x18, 0x28)
PET_SHADOW = 584                           # peep_shadow1.png


def pet_shadow(kind: int, frame: int, asleep: bool = False, direction: int = 0):
    """DrawPet's shadow for a pet at (0, 0): (x, y, percent) or None. CPet::FeetPos is (28, 50); the shadow is drawn
    at 80% (60% for kinds 12 and 13) at the feet less (34, 32) times that scale (24 across for directions 1 and 3;
    (34, 2) asleep); the Tarantula has none from frame 68 on."""
    if kind == 13 and frame >= 0x44 and not asleep:
        return None
    scale = f32(0.6) if kind >= 12 else f32(0.8)
    ox = 0x22 if asleep or direction not in (1, 3) else 0x18
    oy = 2 if asleep else 0x20
    return 28 - int(f32(ox * scale)), 50 - int(f32(oy * scale)), 60 if kind >= 12 else 80


def pet_place(kind: int, frame: int) -> tuple[int, int]:
    x, y = PET_LINKS[kind].split()[frame].split(",")
    return int(x), int(y)


def pet_frame_words(frame: int) -> str:
    if frame < 64:
        d = PET_DIRECTION_FRAMES.index(frame - frame % 8)
        return f"direction {d + 1} of 8, step {frame % 8 + 1} of 8"
    return f"picture {frame + 1} of {PET_FRAMES}"


BIRD, BIRD_SHADOW = 593, 594
# CBird::Draw: facing 0 or 3 (left, right); on the ground (state 1 or 2) cell = frame (+2 facing right), the frames
# CBird::Update sets being 0, 1 and 4..7 (6..9 facing right); flying (state 3) cell = frame + 4 (+4 facing right),
# frames 0..3. The shadow is 3 below the bird on the ground, 37 below it in flight.
BIRD_POSES = tuple(
    [("ground", 1, f, fr) for f, frames in ((0, (0, 1, 4, 5, 6, 7)), (3, (0, 1, 6, 7, 8, 9))) for fr in frames]
    + [("flying", 3, f, fr) for f in (0, 3) for fr in range(4)])


def bird_draws(files, state: int, facing: int, frame: int) -> list:
    turn = (2 if state in (1, 2) else 4) if facing == 3 else 0
    if state in (1, 2):
        return [_cell(files, BIRD_SHADOW, 0, -23, -16), _cell(files, BIRD, frame + turn, -23, -19)]
    return [_cell(files, BIRD_SHADOW, 0, -23, 18), _cell(files, BIRD, frame + 4 + turn, -23, -19)]


BALL_SHADOW, BALL_ITEMS, BALL_CELL = 635, 608, 4   # CInventoryManager::ImageIndex(ball, 0) is 4
PET_CHECK = CHECKED.format(code="CPetAnimManager::LoadAssets and CPetManager::DrawPet")
BIRD_CHECK = CHECKED.format(code="CBird::Draw")
BALL_CHECK = CHECKED.format(code="CBall::Draw with CInventoryManager::ImageIndex")
SCALED_NOTE = ("The shadow is drawn scaled; the picture's scaling matches the game's own blitter "
               "(ldwGameWindowImpl::BlitRectWithAlpha) within two levels on each colour.")


def animal_arts(files: gp.GameFiles) -> list[gp.Art]:
    out: list[gp.Art] = []

    def add(key, category, label, layers, used, why, checked):
        layers = tuple(layers)
        if _have(files, layers):
            out.append(gp.Art(key, category, label, layers, used, why, checked))

    if not files.has(_entry(7).file):
        return out
    shadow_name = _entry(PET_SHADOW).file
    for kind, name in enumerate(PET_NAMES):
        item = 0x23B + kind
        note = (" The original store does not sell it (the patcher's \"Add unused pets\" does)."
                if item in PETS_NOT_SOLD else "")
        for frame in range(PET_FRAMES + 1):
            asleep = frame == PET_FRAMES
            f = 0x38 if asleep else frame
            layers = []
            sh = pet_shadow(kind, f, asleep)
            if sh:
                layers.append(gp.Draw(shadow_name, (0, 0, -1, -1), sh[0], sh[1], percent=sh[2]))
            x, y = pet_place(kind, f)
            layers.append(_cell(files, 7, kind * PET_FRAMES + f, x, y))
            words = "asleep" if asleep else pet_frame_words(f)
            add(f"misc/pet/{kind}/{'asleep' if asleep else f}", f"Animals and insects/Pets/{name}",
                f"{name}, {words}", layers, True,
                f"Pet item {item:#x} ({name}, pet_grid.png row {kind + 1}). CPetManager::DrawPet draws its shadow, "
                f"then column {f + 1} of its row where CPetAnimManager's link for that frame puts it"
                + (" (asleep it always shows frame 57 and its shadow sits lower)." if asleep else ".")
                + (f" {SCALED_NOTE}" if sh else "") + note, PET_CHECK)
    for pose, state, facing, frame in BIRD_POSES:
        side = "left" if facing == 0 else "right"
        words = "on the ground" if pose == "ground" else "flying"
        add(f"misc/bird/{pose}/{side}/{frame}", "Animals and insects/Birds",
            f"Bird {words}, facing {side}, frame {frame + 1}", bird_draws(files, state, facing, frame), True,
            "CBird::Draw draws a bird's shadow and then the bird (bird.png) at its scale, which CBird::Create picks "
            "between 80% and 119% (shown here at 100%). The frames are the ones CBird::Update sets.", BIRD_CHECK)
    for height in (0, 30):
        add(f"misc/ball/{height}", "Animals and insects/Pets' toys",
            "Ball in the yard" + (f" ({height} pixels up)" if height else " (on the ground)"),
            [gp.Draw(_entry(BALL_SHADOW).file, (0, 0, -1, -1), -15, -8),
             _cell(files, BALL_ITEMS, BALL_CELL, -35, -35 - height)], True,
            "Once the ball is bought CBall::Draw draws its shadow on the ground and the ball (InventoryItems.png cell "
            "5, CInventoryManager::ImageIndex of the ball) above it by its height.", BALL_CHECK)
    return out

# ------------------------------------------------------------------ the store's item pictures
# CInventoryManager::DrawItem(point, item, state, position, shadow): the picture of every EInventoryItem below 0x1AD
# (the furniture from 0x1AD on goes to CFurnitureManager::DrawItem). The items' names are the game's own enumerators
# (eInventoryItem_..., from the objects' debug constants); 0x4B..0xE0 are the placeholders FutureToolItem1..150.
STORE_ITEM_CODE_NAMES = {
    0x1: "RewardSpray", 0x2: "WhoopAssSpray", 0x3: "Ball", 0x4: "Groceries1", 0x5: "Groceries2", 0x6: "Groceries3",
    0x7: "Groceries4", 0x8: "GoodGroceries1", 0x9: "GoodGroceries2", 0xa: "GoodGroceries3", 0xb: "GoodGroceries4",
    0xc: "ChamomilleSoda", 0xd: "EnergyDrink", 0xe: "MegaChamExtract", 0xf: "Candy", 0x10: "SaltyCandy",
    0x11: "BloodOrange", 0x12: "BoysOutfit1", 0x13: "BoysOutfit2", 0x14: "BoysOutfit3", 0x15: "GirlsOutfit1",
    0x16: "GirlsOutfit2", 0x17: "GirlsOutfit3", 0x18: "Meds1", 0x19: "Meds2", 0x1a: "Meds3", 0x1b: "Meds4",
    0x1c: "Meds5", 0x1d: "Meds6", 0x1e: "Meds7", 0x1f: "Meds8", 0x20: "Meds9", 0x21: "Meds10", 0x22: "Mango",
    0x23: "Banana", 0x24: "ManPerfume", 0x25: "WomanPerfume", 0x26: "Vitamins", 0x27: "Purell", 0x28: "Sunscreen",
    0x29: "Towelette", 0x2a: "FruitCandy", 0x2b: "AniceCandy", 0x2c: "MintCandy", 0x2d: "CinnamonCandy",
    0x2e: "ChairRepairKit", 0x2f: "Spackle", 0x30: "FloorRepairKit", 0x31: "WaterproofTape", 0x32: "FountainPump",
    0x33: "AntiSpamSoftware", 0x34: "KitchenMagazine", 0x35: "OfficeMagazine", 0x36: "WorkroomMagazine",
    0x37: "Movie1", 0x38: "Movie2", 0x39: "Movie3", 0x3a: "ImportedCandy", 0x3b: "TropicalRain",
    0x3c: "TropicalSunshine", 0x3d: "DesensitizationKit", 0x3e: "Encyclopedia", 0x3f: "WeedBomb",
    0x40: "MagicBarker", 0x41: "FogInABottle", 0x42: "SnowInABottle", 0x43: "PepPills", 0x44: "SleepingPills",
    0x45: "DirtyCandy", 0x46: "Cat", 0x47: "Dog", 0x48: "Turtle", 0x49: "PurchasedBoysOutfit",
    0x4a: "PurchasedGirlsOutfit", 0xe1: "ExpansionDeck", 0xe2: "ExpansionLaundry", 0xe3: "ExpansionAux1",
    0xe4: "ExpansionBedroom1", 0xe5: "ExpansionBedroom2", 0xe6: "ExpansionBathroom2", 0xe7: "ExpansionLivingroom2",
    0xe8: "ExpansionDiningroom", 0xe9: "ExpansionLivingroom1", 0xea: "ExpansionReardeck",
    0xeb: "OfficeWestWorkstationMonitor", 0xec: "OfficeEastWorkstationMonitor", 0xed: "OfficeAirPurifier",
    0xee: "OfficeBatteryBackup", 0xef: "OfficeFaxUpgrade", 0xf0: "OfficeCircularFile", 0xf1: "OfficePrinterUpgrade",
    0xf2: "OfficeShredder", 0xf3: "OfficeSpeakerUpgrade", 0xf4: "OfficeRouterUpgrade", 0xf5: "OfficeWhiteboard",
    0xf6: "KitchenMicrowave", 0xf7: "KitchenCoffeeMaker", 0xf8: "KitchenEspressoMachine",
    0xf9: "KitchenFoodProcessor", 0xfa: "KitchenBlender", 0xfb: "KitchenProCutlery", 0xfc: "KitchenSpiceRack",
    0xfd: "KitchenMortarNPestle", 0xfe: "KitchenWaffleIron", 0xff: "KitchenSuperFridge", 0x100: "WorkshopDrillpress",
    0x101: "WorkshopFan", 0x102: "WorkshopFurnace", 0x103: "WorkshopGrinder", 0x104: "WorkshopLathe",
    0x105: "WorkshopPartsbox", 0x106: "WorkshopRedToolbox", 0x107: "WorkshopShopvac", 0x108: "WorkshopToolwall",
    0x109: "WorkshopPortableToolBox", 0x10a: "RockHoundCertificate", 0x10b: "BoardingSchool",
    0x10c: "SystematicDesensitization", 0x10d: "Psychotherapy", 0x10e: "HigherLearningClasses",
    0x10f: "AdvancedCareerTraining", 0x110: "CareerChanges", 0x111: "IslandEvent", 0x112: "TimeWarp",
    0x113: "Adoption", 0x114: "Gambling", 0x115: "MaidService", 0x116: "GardeningService",
}
INVENTORY_ITEMS, HOME_GRID = 608, 609
# items 0x10B..0x116 (the services) are each drawn whole from their own icon (the table DrawItem builds on its stack)
SERVICE_ICONS = (0x149, 0x14B, 0x151, 0x14E, 0x14A, 0x152, 0x14D, 0x153, 0x148, 0x14F, 0x150, 0x14C)
OUTFITS = tuple(range(0x12, 0x18)) + (0x49, 0x4A)    # drawn from the people's action sheets (the people pictures)
STORE_CHECK = CHECKED.format(code="CInventoryManager::DrawItem")


def store_item_name(item: int) -> str:
    """The enumerator's words: 'RewardSpray' -> 'Reward Spray'."""
    code = STORE_ITEM_CODE_NAMES.get(item)
    if code is None:
        return f"FutureToolItem{item - 0x4A}" if 0x4B <= item <= 0xE0 else f"Item {item:#x}"
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])", " ", code)


def store_picture(item: int, state: int = 0):
    """(image, cell) DrawItem draws for an item that is not an outfit: the cell before ldwImageGrid clamps its row
    (GetCellRect); None for no item."""
    if item <= 0 or item >= 0x1AD or item in OUTFITS:
        return None
    if item in (0x46, 0x47, 0x48):                       # Cat, Dog, Turtle: pet_grid.png column 64 of rows 0..2
        return 7, {0x46: 0x40, 0x47: 0x8C, 0x48: 0xD8}[item]
    if 0x10B <= item <= 0x116:
        return SERVICE_ICONS[item - 0x10B], 0
    if item >= 0xE1:
        return HOME_GRID, item - 0xE1
    index = item if item < 0x18 else item - 4
    return INVENTORY_ITEMS, state - 2 + 2 * index


def store_arts(files: gp.GameFiles) -> list[gp.Art]:
    out: list[gp.Art] = []
    for item in sorted(STORE_ITEM_CODE_NAMES):
        if item in OUTFITS:
            continue
        name = store_item_name(item)
        for state in (0, 1):
            image, cell = store_picture(item, state)
            if state and image != INVENTORY_ITEMS:
                continue                                  # the state changes only InventoryItems.png's cell
            entry = _entry(image)
            if not all(files.has(n) for n in entry.files):
                continue
            c = frame_cell(image, cell) if entry.kind != "image" else 0
            base = _cell(files, image, c, 0, 0)
            w, h = base.rect[2] - base.rect[0], base.rect[3] - base.rect[1]
            if entry.kind == "image":
                w, h = files.size(entry.file)
                base = gp.Draw(entry.file, (0, 0, w, h), 0, 0)
            layer = gp.Draw(base.file, base.rect, -(w // 2), -(h // 2))
            words = " (in use)" if state else ""
            sub = "Store/Item pictures" if item < 0xE1 else "Store/Home and career upgrades and services"
            out.append(gp.Art(f"misc/store/{item}/{state}", sub, f"{name}{words}", (layer,), True,
                              f"Item {item:#x} (eInventoryItem_{STORE_ITEM_CODE_NAMES[item]}): CInventoryManager::"
                              f"DrawItem draws {entry.file}" + (f" cell {c + 1}" if entry.kind != "image" else "")
                              + " centred on its place, at full size.", STORE_CHECK))
    return out


def _store_cells() -> tuple[dict, dict]:
    labels: dict = {}
    reached: dict = {INVENTORY_ITEMS: set(), HOME_GRID: set()}
    for item in range(1, 0x1AD):
        for state in (0, 1):
            pic = store_picture(item, state)
            if pic is None or pic[0] not in reached:
                continue
            c = frame_cell(pic[0], pic[1])
            reached[pic[0]].add(c)
            if c == pic[1] and item in STORE_ITEM_CODE_NAMES:
                words = " (in use)" if state and pic[0] == INVENTORY_ITEMS else ""
                labels.setdefault((pic[0], c), f"{store_item_name(item)}{words}")
    unused = {}
    for c in range(140):
        if c not in reached[INVENTORY_ITEMS]:
            unused[(INVENTORY_ITEMS, c)] = (
                "No item reaches this cell: CInventoryManager::DrawItem numbers the items from 0x18 on four places "
                "back (cell 2 x (item - 4) - 2 + state), so these four cells of items 0x12 to 0x15 are skipped; the "
                "boys' and girls' outfits (0x12 to 0x17) are drawn from the people's action sheets instead.")
    for c in range(55):
        if c not in reached[HOME_GRID]:
            unused[(HOME_GRID, c)] = (
                "No item reaches this cell: items 0x10B to 0x116 (the services) would have cells 42 to 53, but "
                "CInventoryManager::DrawItem draws each service from its own icon instead (cells 50 to 53 are still "
                "reached by the unnamed items from 0x117 on, whose cells past the sheet's last row are clamped "
                "onto it).")
    for c in range(130, 140):
        labels.setdefault((INVENTORY_ITEMS, c), "Reached only by the placeholder items FutureToolItem1..150 "
                                                "(0x4B..0xE0), whose cells past the last row are clamped onto it")
    return labels, unused

# ------------------------------------------------------------------ the catalogue
def _have(files: gp.GameFiles, layers) -> bool:
    return all(isinstance(layer, gp.Fill) or layer.make is not None or files.has(layer.file) for layer in layers)


def _effect_why(effect: int) -> str:
    image, frames, rnd = ANIM_TABLE[effect]
    start = "from a random frame" if rnd else "from the first frame"
    if effect in NEVER_ADDED:
        return f"Effect {effect:#x} of CFloatingAnim's table, but {NEVER_WHY.format(effect=effect)}"
    who = list(ADDED.get(effect, ()))
    if effect in FURNITURE_ANIMS and not any("Furniture" in w for w in who):
        who.append("a piece of furniture's animation (CFurnitureManager::SetOnState, RestoreAnims)")
    return (f"Effect {effect:#x}, started by {', '.join(who)}. It plays its {frames} frames {start}, one each time "
            f"CFloatingAnim::Update moves it (every {STEPS_PER_MOVE} calls times its delay), drawn by "
            "CFloatingAnim::Draw.")


def arts(files: gp.GameFiles) -> list[gp.Art]:
    out: list[gp.Art] = []

    def add(key, category, label, layers, used, why, checked):
        layers = tuple(layers)
        if _have(files, layers):
            out.append(gp.Art(key, category, label, layers, used, why, checked))

    # every effect CFloatingAnim draws by itself, frame by frame
    for effect, (key, label, category) in EFFECTS.items():
        image, frames, _rnd = ANIM_TABLE[effect]
        entry = _entry(image)
        if not all(files.has(n) for n in entry.files):
            continue
        used = effect not in NEVER_ADDED
        why = _effect_why(effect)
        for k, (img, c, alpha) in enumerate(effect_frames(effect)):
            add(f"misc/effect/{key}/{k}", category, f"{label}, frame {k + 1} of {frames}",
                [_cell(files, img, c, 0, 0)], used, why, EFFECT_CHECK)

    # the two fading effects: a sample cell faded over the frames it can be seen in
    for effect, key, label, cell_ in ((0x0C, "fade_carried", "A carried thing fading away (carrying.png cell 1)", 0),
                                      (0x10, "fade_collectable",
                                       "A collectable fading away (collectables_small.png cell 1)", 0)):
        image, frames, _rnd = ANIM_TABLE[effect]
        if not files.has(_entry(image).file):
            continue
        for k in range(FADE_FRAMES):
            a = fade_alpha(k)
            base = _cell(files, image, cell_, 0, 0, alpha=a)
            layer = gp.Draw(base.file, base.rect, 0, 0, alpha=a,
                            make=lambda fs, n=base.file, r=base.rect, o=a: game_faded(fs, n, r, o))
            add(f"misc/effect/{key}/{k}", "Effects and animations/Fading", f"{label}, frame {k + 1} of {frames}",
                [layer], True,
                f"{_effect_why(effect)} The motion argument is the cell to fade; it is drawn at alpha "
                f"max(0, 1 - frame x 0.1) ({a:.1f} here), so from frame 11 on nothing shows. {ALPHA_NOTE}",
                EFFECT_CHECK)

    # every piece of furniture in every orientation, and with its animation running
    for info in _furniture():
        item, image = info["item"], info["image"]
        if is_pet(item):
            continue
        entry = _entry(image)
        if not files.has(entry.file):
            continue
        count = entry.cells
        stem = _stem(entry.file)
        kind = furniture_kind(stem)
        for o in range(count):
            base = _cell(files, image, o, 0, 0)
            words = orientation_words(o, count)
            add(f"misc/furniture/{item}/{o}", f"Furniture and objects/{kind}", f"{stem}, {words}", [base], True,
                f"Furniture item {item} (sFurnitureInfo), image {image}: placed in the house it is drawn by "
                f"CFurnitureManager::Draw as cell {o} of its strip, the cell of its orientation.", FURNITURE_CHECK)
            effect = info["anim"][o] if o < 4 else 0
            if not effect:
                continue
            anim_image, frames, _rnd = ANIM_TABLE[effect]
            if not files.has(_entry(anim_image).file):
                continue
            dx, dy = info["dx"][o], info["dy"][o]
            what = FURNITURE_ANIM_WORDS.get(effect, "animation")
            for k in range(frames):
                add(f"misc/furniture/{item}/{o}/on/{k}", f"Furniture and objects/{kind} in use",
                    f"{stem}, {words}, {what}, frame {k + 1} of {frames}",
                    [base, _cell(files, anim_image, frame_cell(anim_image, k), dx, dy)], True,
                    f"When it is switched on CFurnitureManager::SetOnState (and RestoreAnims after a load) starts "
                    f"effect {effect:#x} ({_entry(anim_image).file}) {dx}, {dy} from the item's place, "
                    f"looping; CFloatingAnim::Draw draws its frames over the item.", FURNITURE_ON_CHECK)
    out += animal_arts(files)
    out += store_arts(files)
    return out


# ------------------------------------------------------------------ usage of every picture in this area
def _usage() -> dict:
    usage: dict = {}
    furn_images = {}
    for info in _furniture():
        furn_images.setdefault(info["image"], []).append(info["item"])
    for effect, (image, _frames, _rnd) in ANIM_TABLE.items():
        if effect in FADING:
            continue
        used = effect not in NEVER_ADDED
        prev = usage.get(image)
        if prev and prev[0]:
            continue
        usage[image] = (used, _effect_why(effect))
    for image, items in furn_images.items():
        if image == 7:
            continue
        usage[image] = (True, f"Furniture (item{'s' if len(items) > 1 else ''} "
                              f"{', '.join(map(str, items))}): drawn by CFurnitureManager::Draw, cell = orientation.")
    usage[7] = (True, "The pets: CPetAnimManager::LoadAssets loads it, CPetManager::DrawPet draws row = the pet's kind, "
                      "column = its frame; CFurnitureManager draws a pet in the storage tray from its row "
                      "(GetPetDrawFrame: column 57 or 65).")
    usage[593] = (True, "The birds, drawn by CBird::Draw (loaded by CBird::LoadAssets).")
    usage[594] = (True, "The birds' shadow, drawn by CBird::Draw (loaded by CBird::LoadAssets).")
    usage[635] = (True, "The ball's shadow, drawn by CBall::Draw (and CBall::DrawShadow).")
    usage[596] = (True, "The butterflies: theButterflyClass's and CMiniButterflyClass's constructors load it and "
                        "their DrawButterflies / Draw draw it. Not assembled here.")
    usage[595] = (False, "No code asks theGraphicsManager for image 595 (no getter call names it), so the dragonflies "
                         "are never drawn.")
    usage[597] = (False, "Only theHummingbirdClass's constructor asks for image 597, and no code reached from WinMain "
                         "(or a static initializer) ever makes a theHummingbirdClass (theHummingbirdClass::Get is "
                         "never called), so the hummingbird is never drawn.")
    usage[77] = (False,"Furniture/LaundryBasketStd.png: no entry of the furniture table sFurnitureInfo has image 77 "
                        "and no code asks theGraphicsManager for 77 by number, so the laundry basket is never drawn.")
    return usage


def _cell_labels() -> dict:
    out: dict = {}
    for effect, (image, frames, _rnd) in ANIM_TABLE.items():
        if effect in FADING:
            continue
        words = EFFECTS[effect][1] if effect in EFFECTS else FURNITURE_ANIM_WORDS.get(effect, "Animation").capitalize()
        for k in range(frames):
            out.setdefault((image, frame_cell(image, k)), f"{words}, frame {k + 1}")
    for info in _furniture():
        image = info["image"]
        if image == 7:
            continue
        entry = _entry(image)
        for o in range(entry.cells):
            out[(image, o)] = orientation_words(o, entry.cells).capitalize()
    for kind, name in enumerate(PET_NAMES):
        for frame in range(PET_FRAMES):
            out[(7, kind * PET_FRAMES + frame)] = f"{name}, {pet_frame_words(frame)}"
    for c in range(12):
        side = "left" if c in (0, 1, 4, 5, 6, 7) else "right"
        pose = "standing" if c in (0, 1, 2, 3) else "wings out"
        out[(BIRD, c)] = f"Bird {pose}, facing {side}"
    return out


USAGE = _usage()
CELL_LABELS = _cell_labels()
CELL_LABELS.update(_store_cells()[0])
CELL_UNUSED: dict = dict(_store_cells()[1])
