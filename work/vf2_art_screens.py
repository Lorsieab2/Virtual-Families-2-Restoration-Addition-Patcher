"""The screens the game draws whole (each scene's background with the fixed pictures its DrawScene always draws on
it), the family tree's frames, the collection pages and the store's boxes, as Virtual Families 2's own code places
them (the B200 desktop objects; tests/test_art_screens.py runs each drawing function in Unicorn and requires every
draw here to be the game's: file, cell, place, clipping).

What these pictures leave out, and why: the text (names, prices, descriptions, the dealer's words) is drawn by the
fonts; the family members (the Details, Adoption and Dating screens' person, the family tree's portraits) are people
(see the people pictures); the buttons and dialogs the scenes add as controls are drawn by the controls themselves
(see Buttons and controls). The meters drawn on a screen are in Meters and bars.

The window: theGameState's constructor sets the game window to 1024 x 768 (GetGameWindowWidth 400h,
GetGameWindowHeight 300h; ldwGame::Run creates the window from them) and the wide-screen flag off; SetToWideScreen,
which would make it 1366 wide, is called by no code, so theGameState::GetWideScreenOffsetX ((width - 1024) / 2) is
always 0 and every screen here is drawn as the game starts: 1024 x 768, nothing offset. Whatever the window cuts off
(ldwGameWindowImpl::ClipRect) is cut off here too.
"""
from __future__ import annotations

import re

import vf2_game_pictures as gp

TITLE = "Screens, family tree, collections and store"
WINDOW = (0, 0, 1024, 768)                     # the game window (clipping rectangle when none is set)
CHECKED = ("Checked against the game's own drawing code ({code}) run in Unicorn: every draw (file, cell, place and "
           "clipping) is the game's.")
SCREENS = "Screens and backgrounds/Screens"
NO_TEXT = "Text, family members and the scene's buttons are not part of this picture."

# image ids (theGraphicsManager's EImage)
BOXSHOT, LOADING, LOADBAR, VD_BG, UPGRADE_ME, ADOPT_BG, DATING_BG, AWARDS_BG = 374, 366, 267, 462, 463, 464, 382, 365
ACH_BOX, ACH_DONE, ACH_PROGRESS, NO_COMM = 625, 626, 627, 628
HELP, TREE_BG, PARENT_FRAME, CHILD_FRAME = 373, 615, 616, 617
COLLECTION_BG, ARROW_LEFT, ARROW_RIGHT, DASH, COMM = 383, 384, 385, 386, 387
STORE_BOX, STORE_SHADOW, BANK_LABEL, CHECKMARK = 630, 631, 300, 634


# ------------------------------------------------------------------ drawing helpers
def clip(rect, x, y, area=WINDOW):
    """ldwGameWindowImpl::ClipRect: the part of the cell inside the clipping rectangle (left, top, right, bottom),
    moved by what is cut off its left and top; None when nothing is inside."""
    l, t, r, b = rect
    w, h = r - l, b - t
    cl, ct, cr, cb = area
    if x < cl:
        l, w, x = l + cl - x, w - (cl - x), cl
    if y < ct:
        t, h, y = t + ct - y, h - (ct - y), ct
    w = min(w, cr - x)
    h = min(h, cb - y)
    if w <= 0 or h <= 0:
        return None
    return (l, t, l + w, t + h), x, y


def draw(files, image, x, y, cell=0, area=WINDOW):
    """theGraphicsManager::Draw / DrawCell of an image-table picture at 100%, cut by the clipping rectangle."""
    name, rect = gp.cell_of(files, image, cell)
    cut = clip(rect, x, y, area)
    if cut is None:
        return None
    rect, x, y = cut
    return gp.Draw(name, rect, x, y)


def named(files, name, x, y, area=WINDOW):
    """ldwGameWindow::Draw of a picture the code loads by name (ldwImage(name))."""
    w, h = files.size(name)
    cut = clip((0, 0, w, h), x, y, area)
    if cut is None:
        return None
    rect, x, y = cut
    return gp.Draw(files.relative(name.lower()), rect, x, y)


def line(x1, y1, x2, y2, rgb, area=WINDOW):
    """ldwGameWindow::DrawLine of a straight line: ldwGameWindowImpl::DrawLine fills it (both ends included), cut by
    the clipping rectangle."""
    if x1 == x2:
        l, t, r, b = x1, min(y1, y2), x1 + 1, max(y1, y2) + 1
    else:
        l, t, r, b = min(x1, x2), y1, max(x1, x2) + 1, y1 + 1
    l, t, r, b = max(l, area[0]), max(t, area[1]), min(r, area[2]), min(b, area[3])
    if r <= l or b <= t:
        return None
    return gp.Fill(l, t, r - l, b - t, (*rgb, 255))


def _words(file: str) -> str:
    stem = re.sub(r"(_icon)?\d*\.png$", "", file.split("/")[-1], flags=re.I)
    stem = re.sub(r"^(MenuStore|meunStore)", "", stem)
    stem = stem.replace("_", " ").replace("-", " ")
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem).strip().capitalize()


# ------------------------------------------------------------------ the screens
def _screens(files):
    """(key, label, layers, why, code) of each screen."""
    no_comm = "main_no-comm.png across the bottom"
    out = [
        ("menu", "Main menu", [draw(files, BOXSHOT, 0, 0)],
         "theMenuScene::DrawScene draws vf2_boxshot.jpg's cell centred across the window ((window width - cell "
         "width) / 2 = 0). The distributor's menu logo would go on it, but CDistributor::LoadAssets only loads one "
         "when the game folder has menu_logo.png, and the original game has none.",
         "theMenuScene::DrawScene"),
        ("splash", "Splash screen", [named(files, "SPLASH_BG.JPG", 0, 0)],
         "theSplashScene shows SPLASH_BG.JPG (loaded by name when it exists; SPLASH1_BG to SPLASH3_BG.JPG are "
         "looked for too and the original game has none) at the wide-screen offset, 0, once the opening movie is not "
         "being drawn (theSplashScene::DrawScene draws CMoviePlayer instead while [this+19h] is clear).",
         "theSplashScene's constructor and DrawScene"),
        ("loading", "Loading screen", [draw(files, LOADING, 0, 0), draw(files, LOADBAR, 375, 500)],
         "theLoadingScene::DrawScene draws loading.jpg centred, the loading bar's trough LoadSceneBarBG.png at "
         "(375, 500) and the loading meter in it (theContinuousVariableMeter colour 13, empty here: at 0 its clipping "
         "is 0 wide and nothing is drawn). The distributor's loading logo is only drawn when the folder has "
         "loading_logo.png, and the original game has none.",
         "theLoadingScene::DrawScene with theContinuousVariableMeter::DrawPercentMeter"),
        ("details", "Family member details (Details screen)",
         [draw(files, VD_BG, 0, 0), draw(files, UPGRADE_ME, 0, 0), draw(files, NO_COMM, 0, 722)],
         f"theVillagerScene::DrawScene draws VD_BG_2.jpg, upgradeMeButton.png at its top left and {no_comm} at y "
         "722 (the window cuts it to 46 rows); the family member and the five meters are drawn over it.",
         "theVillagerScene::DrawScene"),
        ("adoption", "Adoption screen", [gp.Fill(0, 0, 1024, 768, (0, 0, 0, 255)), draw(files, ADOPT_BG, 0, 0)],
         "CAdoptionScene::DrawScene fills the window black and draws adoptbg.jpg; the child is drawn over it.",
         "CAdoptionScene::DrawScene"),
        ("dating", "Dating screen", [draw(files, DATING_BG, 0, 0)],
         "CDatingScene::DrawScene draws dating_bg.jpg; the date is drawn over it.", "CDatingScene::DrawScene"),
        ("help", "Help screen (at the top)",
         [draw(files, HELP, 0, 0, area=(0, 0, 1024, 767)), draw(files, HELP, 0, 0, area=(0, 144, 1024, 768)),
          draw(files, NO_COMM, 0, 723)],
         "theHelpScene::DrawScene draws help.jpg (4500 rows) twice: once still, clipped to the window less its last "
         "row (the header above y 144), and once scrolled, clipped to y 144 and below; the help opens scrolled to the "
         f"top, so both show its first rows. Then {no_comm} at y 723.",
         "theHelpScene::DrawScene"),
    ]
    return out


ACHIEVEMENT_ROWS = 11                 # rows 85 + 66k inside the list's clipping (40, 85, 984, 768)
ACHIEVEMENT_GOALS = (100, 1000, 10000, 100000, 10, 50, 1, 1, 1, 1, 1)   # achievementList: the first rows' goals


def _achievements(files, earned: bool):
    area = (40, 85, 984, 768)
    layers = [draw(files, AWARDS_BG, 0, 0)]
    for k in range(ACHIEVEMENT_ROWS):
        y = 85 + 66 * k
        layers.append(draw(files, ACH_DONE if earned else ACH_BOX, 48, y, area=area))
        if not earned and ACHIEVEMENT_GOALS[k] > 1:
            layers.append(draw(files, ACH_PROGRESS, 720, y + 14, area=area))
    layers.append(draw(files, NO_COMM, 0, 709))
    return layers


def _store_screen(files):
    return [draw(files, AWARDS_BG, 0, 0), draw(files, STORE_SHADOW, 50, 85), draw(files, NO_COMM, 0, 710),
            draw(files, BANK_LABEL, 838, 736)]


# ------------------------------------------------------------------ the family tree
TREE_VIEW = (93, 187, 960, 768)       # CFamilyTreeScene's view (+0Ch..+18h), the clipping of the tree
TREE_PARENTS = ((85, 195), (85, 265), (85, 363), (85, 433))
TREE_CHILDREN = ((539, 189), (646, 189), (753, 189), (539, 357), (646, 357), (753, 357), (860, 357), (539, 437))
GREY, BLACK = (100, 100, 100), (0, 0, 0)
def _tree_lines():
    """The line from the first family's second child down to the second family's first parent: three lines side by
    side, grey (FF646464h), black, grey."""
    out = []
    for d, colour in ((0, GREY), (1, BLACK), (2, GREY)):
        out.append((693 - d, 196, 693 - d, 190 + d, colour))
    for d, colour in ((0, GREY), (1, BLACK), (2, GREY)):
        out.append((520 + d, 190 + d, 693 - d, 190 + d, colour))
    for d, colour in ((0, GREY), (1, BLACK), (2, GREY)):
        out.append((520 + d, 190 + d, 520 + d, 351 + d, colour))
    for d, colour in ((0, GREY), (1, BLACK), (2, GREY)):
        out.append((148 + d, 351 + d, 520 + d, 351 + d, colour))
    for d, colour in ((0, GREY), (1, BLACK), (2, GREY)):
        out.append((148 + d, 351 + d, 148 + d, 368, colour))
    return out


def _family_tree(files):
    layers = [draw(files, TREE_BG, 0, 0)]
    first = [(PARENT_FRAME, p) for p in TREE_PARENTS[:2]] + [(CHILD_FRAME, c) for c in TREE_CHILDREN[:3]]
    second = [(PARENT_FRAME, p) for p in TREE_PARENTS[2:]] + [(CHILD_FRAME, c) for c in TREE_CHILDREN[3:]]
    for image, (x, y) in first + second:
        layers.append(draw(files, image, x, y, area=TREE_VIEW))
    for x1, y1, x2, y2, colour in _tree_lines():
        layers.append(line(x1, y1, x2, y2, colour, TREE_VIEW))
    layers.append(draw(files, NO_COMM, 0, 722))
    return layers


# ------------------------------------------------------------------ the collections
# CCollectionScene's tables: the page's frame and title (gCollectionFrame, gCollectionLabel: image, x, y), the 60
# collectibles' pictures (sm_sCollectable, 12 a page) and the ECarrying value each one is (gCollectable).
PAGES = ("Insects", "Leaves and nuts", "Raptor fossils", "Pterodactyl fossils", "Bottle caps")
FRAMES = ((389, 104, 13), (407, 80, 0), (421, 86, 0), (421, 86, 0), (447, 0, 0))
LABELS = ((390, 355, 566), (408, 340, 95), (422, 173, 607), (422, 173, 607), (408, 340, 95))
PINS = ((391, 197, 140), (394, 312, 134), (394, 435, 167), (394, 543, 148), (394, 648, 139), (394, 752, 125),
        (391, 357, 303), (391, 471, 323), (394, 618, 282), (392, 253, 485), (393, 487, 472), (394, 689, 485))
ITEMS = (
    (395, 182, 119), (396, 291, 119), (397, 419, 125), (398, 545, 119), (399, 645, 124), (400, 758, 135),
    (401, 321, 304), (402, 406, 289), (403, 557, 284), (404, 201, 418), (405, 394, 413), (406, 673, 440),
    (409, 205, 216), (410, 371, 197), (411, 549, 205), (412, 711, 195), (413, 190, 357), (414, 382, 368),
    (415, 545, 370), (416, 728, 370), (417, 215, 545), (418, 376, 531), (419, 543, 539), (420, 732, 545),
    (423, 285, 203), (424, 466, 222), (425, 605, 230), (426, 630, 345), (427, 567, 386), (428, 599, 406),
    (429, 525, 412), (430, 465, 425), (431, 493, 447), (432, 438, 361), (433, 326, 324), (434, 341, 279),
    (435, 205, 149), (436, 229, 195), (437, 328, 523), (438, 264, 395), (439, 562, 413), (440, 607, 349),
    (441, 467, 330), (442, 691, 181), (443, 575, 140), (444, 544, 139), (445, 377, 286), (446, 278, 295),
    (448, 180, 182), (449, 353, 182), (450, 531, 182), (451, 708, 182), (452, 193, 346), (453, 353, 346),
    (454, 531, 346), (455, 708, 346), (456, 180, 515), (457, 353, 515), (458, 531, 515), (459, 708, 515),
)
VALUES = tuple(range(79, 115)) + tuple(range(134, 158))     # gCollectable: the ECarrying value of each
ITEM_NAMES = (
    "Fly", "Pincher bug", "Scorpion", "Red bug", "Grey beetle", "Ladybug", "Butterfly", "Cricket", "Dragonfly",
    "Leaf bug", "Spider", "Green bug",
    *(f"Leaf {n}" for n in (6, 1, 7, 8, 10, 5, 11, 2, 4, 12, 3, 9)),
    *(f"Raptor fossil piece {n}" for n in range(1, 13)),
    *(f"Pterodactyl fossil piece {n}" for n in range(1, 13)),
    "A&UU bottle cap", "Grape Soda bottle cap", "Krona bottle cap", "Mom's bottle cap", "Mountain Brew bottle cap",
    "Mr. Didd bottle cap", "Mr. Pepps bottle cap", "Popsi bottle cap", "Soda Cola bottle cap",
    "Suddmeister bottle cap", "Sun Zest bottle cap", "Swiller bottle cap",
)


def _collection(files, page: int, have: bool):
    layers = []
    if page != 4:
        layers.append(draw(files, COLLECTION_BG, 0, 0))
    for image, x, y in (FRAMES[page], LABELS[page]):
        layers.append(draw(files, image, x, y))
    layers += [draw(files, ARROW_LEFT, 23, 336), draw(files, ARROW_RIGHT, 958, 336)]
    if have:
        for k in range(12 * page, 12 * page + 12):
            image, x, y = ITEMS[k]
            layers.append(draw(files, image, x, y))
            if page == 0:
                image, x, y = PINS[k]
                layers.append(draw(files, image, x, y))
    layers += [draw(files, COMM, 252, 716), draw(files, DASH, 0, 720)]
    return layers


# ------------------------------------------------------------------ the store
# CScrollingStoreScene::DrawVisibleStoreItem: the box at (x + 8, y), then by the list shown ([this+D4h]): 16h the
# coin packs and services (gIAPItem: image, name, description), 17h the store's own menu and 18h the furniture
# menu (gMenuItem / gFurnitureMenuItem: image, name, description, category), each picture at (x + 30, y + 11).
IAP = ((10, "Coin pack 1"), (11, "Coin pack 2"), (12, "Coin pack 3"), (13, "Coin pack 4"), (14, "Coin pack 5"),
       (15, "Coin pack 6"), (16, "Coin pack 7"), (17, "Brokerage upgrade"), (18, "Food Club"), (19, "Health Plan"),
       (20, "Lucky Rock"))
MENU = (321, 320, 317, 323, 318, 319, 336, 324)
FURNITURE_MENU = (349, 347, 345, 343, 344, 348, 341, 346)
OWNED_CHECK = {7: "the brokerage is bought (CMoney's rate above 0.1)", 8: "the family has the Food Club "
               "(CFoodStore::HaveFoodClub)", 9: "the Health Plan is bought (theGameState+25B1Dh)",
               10: "the Lucky Rock is found (CCollectableItem+8A8h)"}


def store_box(files, image, cell_draw=False, owned=False):
    layers = [draw(files, STORE_BOX, 8, 0), draw(files, image, 30, 11)]
    if owned:
        w, h = files.size("checkmark_red.png")
        # centred in the item's rectangle (x + 10, y + 5) - (x + 98h, y + 6Ch)
        layers.append(draw(files, CHECKMARK, 10 + (0x98 - 10) // 2 - w // 2, 5 + (0x6C - 5) // 2 - h // 2))
    return layers


# ------------------------------------------------------------------ the catalogue
def arts(files: gp.GameFiles) -> list[gp.Art]:
    out: list[gp.Art] = []

    def add(key, category, label, layers, why, code):
        layers = [layer for layer in layers if layer is not None]
        files_needed = {layer.file for layer in layers if isinstance(layer, gp.Draw)}
        if all(files.has(name) for name in files_needed):
            out.append(gp.Art(f"screens/{key}", category, label, tuple(layers), True, why,
                              CHECKED.format(code=code)))

    def safe(fn, *args):
        try:
            return fn(files, *args)
        except Exception:                      # a picture the folder does not have
            return []

    for key, label, layers, why, code in _screens(files) if files.has("main_no-comm.png") else []:
        add(key, SCREENS, label, layers, f"{why} {NO_TEXT}", code)
    for earned in (False, True):
        add(f"achievements/{'earned' if earned else 'none'}", SCREENS,
            f"Achievements screen ({'every achievement earned' if earned else 'nothing earned yet'})",
            safe(_achievements, earned),
            "CAchievementsScene::DrawScene draws awards_bg.jpg, then the list's rows inside (40, 85) - (984, 768) "
            "(CAchievement::DrawAchievement: achievement_box.png, or achievement_complete_box.png once earned, at "
            "(48, 85 + 66 x row); an unearned achievement whose goal is more than 1 also gets its progress box at "
            "(720, row + 14)), then main_no-comm.png at y 709. Shown scrolled to the top, as it opens. " + NO_TEXT,
            "CAchievementsScene::DrawScene with CAchievement::DrawAchievement")
    add("store/screen", SCREENS, "Store screen (no list chosen)", safe(_store_screen),
        "CScrollingStoreScene::DrawScene draws awards_bg.jpg, the list (none here), getMoreCoinsScrollShadow.png "
        "over its top at (50, 85), main_no-comm.png at y 710 and BankButtonLabel.png at (838, 736). " + NO_TEXT,
        "CScrollingStoreScene::DrawScene")

    add("family_tree", "Dialogs and panels/Family tree", "Family tree (two families, empty frames)",
        safe(_family_tree),
        "CFamilyTreeScene::DrawScene with two families: a couple with three children, and the second child's own "
        "family (a couple with five children, four to a row). Each family's parents get familytree_parentframe.png "
        "(drawn 8 pixels left of the tree's view, which cuts that off) and each child familytree_childframe.png; "
        "DrawConnectingLine joins the child to their own family with a grey-black-grey line three pixels wide. "
        "The portraits in the frames (DrawPeep) are people and are left out, so the frames are empty; a missing "
        "person's frame would be darkened over (DrawTinted), not shown here. Then main_no-comm.png at y 722. "
        + NO_TEXT,
        "CFamilyTreeScene::DrawScene, DrawFamily and DrawConnectingLine")

    for page, name in enumerate(PAGES):
        for have in (True, False):
            add(f"collection/{page}/{'all' if have else 'none'}", "Collectibles and collections/Collection pages",
                f"{name} collection page ({'every piece found' if have else 'nothing found yet'})",
                safe(_collection, page, have),
                "CCollectionScene::DrawScene for page " f"{page + 1} of 5: "
                + ("collection_bg.jpg, " if page != 4 else "no collection_bg.jpg (this page's frame is a whole "
                   "background), ")
                + "the page's frame and title, the two arrows, each collectible found (CCollectableItem::Count above "
                "0) at its place" + (" with its pin" if page == 0 else "")
                + ", then collection_comm.png at (252, 716) and collection_dash.png at (0, 720). " + NO_TEXT,
                "CCollectionScene::DrawScene")

    cat = "Store/Store boxes"
    for k, (image, name) in enumerate(IAP):
        add(f"store/iap/{k}", cat, f"{name} (coins and services list)", safe(store_box, image),
            "CScrollingStoreScene::DrawVisibleStoreItem in the coins and services list (16h): "
            "ScrollingStoreItemBox.png, then gIAPItem's picture at (30, 11). " + NO_TEXT,
            "CScrollingStoreScene::DrawVisibleStoreItem")
        if k in OWNED_CHECK:
            add(f"store/iap/{k}/owned", cat, f"{name}, already bought (coins and services list)",
                safe(store_box, image, False, True),
                "As the box above, and when " + OWNED_CHECK[k] + " checkmark_red.png centred on the picture's place. "
                + NO_TEXT, "CScrollingStoreScene::DrawVisibleStoreItem")
    for table, (image_list, what) in enumerate(((MENU, "store menu"), (FURNITURE_MENU, "furniture menu"))):
        for k, image in enumerate(image_list):
            label = _words(gp.entry_by_id(image).file)
            add(f"store/menu/{table}/{k}", cat, f"{label} ({what})", safe(store_box, image),
                f"CScrollingStoreScene::DrawVisibleStoreItem in the {what} ({17 + table:X}h): "
                f"ScrollingStoreItemBox.png, then {'gMenuItem' if table == 0 else 'gFurnitureMenuItem'}'s picture "
                f"(entry {k}, cell 0) at (30, 11). " + NO_TEXT, "CScrollingStoreScene::DrawVisibleStoreItem")
    return out


# ------------------------------------------------------------------ per-cell words
def _cell_labels() -> dict:
    out = {}
    for k, value in enumerate(VALUES):
        out[(493, value - 79)] = (f"{ITEM_NAMES[k]} ({PAGES[k // 12]} collection, piece {k % 12 + 1}; the "
                                  f"collection page shows it as {gp.entry_by_id(ITEMS[k][0]).file})")
    return out


CELL_LABELS = _cell_labels()
