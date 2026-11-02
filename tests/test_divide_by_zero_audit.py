"""Every integer division in Virtual Families 2's code, audited for a divide-by-zero crash (owner's order after
Virtual Families 1's bank crash: "Make sure the bank crash bug isn't in any game!!!", 2026-11-01).

Virtual Families 1's bank dialog divides its 7-day chart by int(v / 5 + v) with no guard, so $0 crashes it. In
Virtual Families 2 the bank dialog (CBankingDlg::DrawNoFadeScene) scales its chart in floating point (no fault),
and its objects BankDialog.obj and Money.obj hold no integer division at all. This file pins all 185 integer
div/idiv instructions of the 164 desktop object files the patcher builds the game from (work/desktop_obj_files or
VF2_DESKTOP_OBJ_DIR) and, for each, why it cannot fault, or that it could and is fixed:

* the inventory: every div/idiv, by object, function and offset, is in AUDIT with a verdict; a new or moved
  division fails the test until it is audited;
* "can fault" is shown by running the game's own instructions under unicorn with the triggering values; "cannot"
  by the guard or the constant or the data, each checked here (immediate divisors, GetRandom's own n <= 0 test,
  the achievement targets, the villager and pet animation frame counts, the furniture maps, the image table, the
  game-speed field's writers, the store and scene scroll ranges);
* the one reachable crash found, a zero-length rain streak in ldwGameWindowImpl::DrawLine (colour overload), is
  fixed under Fix Vanilla Game Bugs (.vf2bugs, patch_zero_length_line_guard): the stock instructions divide by
  zero, the patched ones with the byte 1 draw the line's one pixel, with the byte 0 they are the stock ones, and
  every other line gives the stock pixels exactly;
* with VF2_CORE_EXE (a shipped core executable, e.g. B205's "Virtual Families 2 - Modded B205.exe") the functions
  run here are found byte for byte (relocations aside) in it, so the objects' behaviour is the shipped game's.

Nothing here starts the game or writes outside pytest's temporary folders.
"""
from __future__ import annotations

import faulthandler
import glob
import os
import re
import shutil
import struct
import sys
from collections import defaultdict
from pathlib import Path

import pytest

faulthandler.disable()   # unicorn's first-chance access violations (tests/b200_time_emu.py does the same)

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work"
OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or WORK / "desktop_obj_files")
GAME_DIR = Path(os.environ.get("VF2_VANILLA_GAME_DIR") or WORK / "vanilla_runtime_payload")
CORE_EXE = os.environ.get("VF2_CORE_EXE")

FLAG = "_gVF2FixVanillaGameBugs"
LINE = "?DrawLine@ldwGameWindowImpl@@QAEXHHHHUldwColor@@MM@Z"

# ------------------------------------------------------------------------------------------------ the audit
# Verdicts. CONSTANT: an immediate divisor. GUARDED: the code tests the divisor (or forces it nonzero) first.
# DATA: a count from the game's own tables or shipped files, all >= 1 (checked below). GEOMETRY: a fixed screen
# size or a scroll range set when the scene is built, divided only while a drag that needs it > 0 is running.
# STATE: a game-state field every writer keeps nonzero. NOT SHOWN: built at load, never put on screen. DEAD: no
# caller chain from WinMain. LATENT: faults only with values the running game cannot produce. FIXED: see above.
AUDIT = {
    "Achievement|?PercentCompleted@CAchievement@@AAEHW4EAchievement@@@Z": (
        (0x2F,), "DATA", "achievementList target, 1..100000 for all 95 entries (test_achievement_targets)"),
    "AchievementsScene|?HandleMouse@CAchievementsScene@@UAE_NHUldwPoint@@@Z": (
        (0x9A, 0x13A), "GEOMETRY", "thumb track and range [+6Ch] = 0x189A + fixed view size, set in the constructor"),
    "AchievementsScene|?DrawScene@CAchievementsScene@@MAEXXZ": ((0x93,), "CONSTANT", "0x42"),
    "AchievementsScene|?UpdateScene@CAchievementsScene@@MAEXXZ": (
        (0x92,), "GEOMETRY", "range [+6Ch], constant (above); only while the fling speed is nonzero"),
    "AnimManager|?GetFrame@CAnimManager@@QBEXW4EAnim@@H_N1AAW4EAnimFrame@@AAW4EHeadDirection@@AAW4EDirection@@@Z": (
        (0x3B, 0x4F, 0x5F), "DATA", "frame count: 29 built-in and anims.dat's 104 animations all >= 1"),
    "Behavior|?HavingAMealDispatch@CBehavior@@CAXAAVCVillager@@@Z": ((0x1E,), "CONSTANT", "5"),
    "Behavior|?LookingForSnacksDispatch@CBehavior@@CAXAAVCVillager@@@Z": ((0x1E,), "CONSTANT", "5"),
    "Behavior|?BrushTeeth@CBehavior@@CAXAAVCVillager@@@Z": ((0x3C,), "GUARDED", "2 or 4 (upgrade bit * 2 + 2)"),
    "Behavior|?WashingInBathroomSink@CBehavior@@CAXAAVCVillager@@@Z": ((0x38,), "GUARDED", "2 or 4"),
    "Behavior|?BathroomGroomingGeneral@CBehavior@@CAXAAVCVillager@@@Z": ((0x37,), "GUARDED", "2 or 4"),
    "Behavior|?Flossing@CBehavior@@CAXAAVCVillager@@@Z": ((0x3F,), "GUARDED", "2 or 4"),
    "Behavior|?BrushingHair@CBehavior@@CAXAAVCVillager@@@Z": ((0x3F,), "GUARDED", "2 or 4"),
    "Behavior|?WashingHair@CBehavior@@CAXAAVCVillager@@@Z": ((0x3F,), "GUARDED", "2 or 4"),
    "Behavior|?BathroomGroomingShaveMakeup@CBehavior@@CAXAAVCVillager@@@Z": ((0x41,), "GUARDED", "2 or 4"),
    "Behavior|?Gargle@CBehavior@@CAXAAVCVillager@@@Z": ((0x3F,), "GUARDED", "2 or 4"),
    "Behavior|?PuttingEyedrops@CBehavior@@CAXAAVCVillager@@@Z": ((0x3F,), "GUARDED", "2 or 4"),
    "Behavior|?PoppingPimple@CBehavior@@CAXAAVCVillager@@@Z": ((0x3F,), "GUARDED", "2 or 4"),
    "Behavior|?AdmiringSelf@CBehavior@@CAXAAVCVillager@@@Z": ((0x3F,), "GUARDED", "2 or 4"),
    "Behavior|?ApplyingDeo@CBehavior@@CAXAAVCVillager@@@Z": ((0x3F,), "GUARDED", "2 or 4"),
    "Behavior|?BathroomDrinkWater@CBehavior@@CAXAAVCVillager@@@Z": ((0x3C,), "GUARDED", "2 or 4"),
    "Behavior|?PlayingBoardGame@CBehavior@@CAXAAVCVillager@@@Z": ((0x6F,), "CONSTANT", "3"),
    "Behavior|?GenericSlowWander@CBehavior@@CAXAAVCVillager@@@Z": ((0x34, 0x4F), "CONSTANT", "0x6E"),
    "CollectableItem|?Update@CCollectableItem@@QAEXXZ": (
        (0x2C8, 0x2CF), "GUARDED", "1, 2 or 3 by population, then 300 / that = 300, 150 or 100"),
    "CommunityEventDialog|??0CCommunityEventDialog@@QAE@HHHHHH@Z": (
        (0x1F4,), "LATENT", "a poll result's totalVotes from LDW's server; polls are asked only once logged in, "
                            "which LDW's server can no longer do (test_poll_result_needs_a_login)"),
    "ContentMap|?FindObject@CContentMap@@QAE?AUldwPoint@@PAUsContentBlock@@W4EObject@1@@Z": (
        (0xB3, 0xC1), "DATA", "a furniture map's width, >= 1 in every shipped .fmap (test_furniture_map_widths)"),
    "ContentMap|?Draw@CContentMap@@IAEX_N0000MPBUSContent@1@@Z": ((0x1FC,), "CONSTANT", "1000 (and DEAD)"),
    "ContentMap|?Read@CContentMap@@AAEXHH@Z": (
        (0x35, 0x41), "DATA", "the applied furniture map's width (above); a NULL overlay returns first"),
    "Credentials|?RandBits@CCredentials@@AAEIH@Z": ((0x2B,), "GUARDED", "bits of RAND_MAX 0x7FFF = 15"),
    "DayNightCycleTestDlg|?HandleMessage@CDayNightCycleTestDlg@@UAE_NHJ@Z": (
        (0x289, 0x2A3), "DEAD", "debug dialog; 0x5A and 0x168 anyway"),
    "FamilyTreeScene|?HandleMouse@CFamilyTreeScene@@UAE_NHUldwPoint@@@Z": (
        (0xB0, 0x150), "GEOMETRY", "range [+60h] (generations x row height); a drag starts only when it is > 0"),
    "FamilyTreeScene|?DrawScene@CFamilyTreeScene@@MAEXXZ": (
        (0x89, 0xF6), "GEOMETRY", "row height [+94h] = 2 x frame height + 0x20, set in the constructor"),
    "FamilyTreeScene|?UpdateScene@CFamilyTreeScene@@MAEXXZ": (
        (0x139,), "GEOMETRY", "range [+60h]; only while the fling speed (set by that drag) is nonzero"),
    "FamilyTreeScene|?CheckForPeepHit@CFamilyTreeScene@@AAE_NUldwPoint@@@Z": (
        (0x14,), "GEOMETRY", "row height [+94h] (above)"),
    "FlashPlayer|?get_Font@CAxHostWindow@ATL@@UAGJPAPAUIFontDisp@@@Z": (
        (0x1A2,), "GUARDED", "ATL: GetDeviceCaps(LOGPIXELSY) of the desktop, never 0 on a display"),
    "FloatingAnim|?Draw@CFloatingAnim@@QBEXXZ": ((0x3B, 0x47), "DATA", "the grid's row count (image table) and 1 or 2"),
    "FloatingAnim|?Draw@CFloatingAnim@@QBEXH@Z": ((0x49, 0x6C), "DATA", "the grid's row and column counts"),
    "FurnitureManager|?DrawStorage@CFurnitureManager@@QAEXXZ": ((0x15B,), "CONSTANT", "0x6A"),
    "FurnitureManager|?WhichStorageCube@CFurnitureManager@@AAEHUldwPoint@@_N@Z": ((0x64,), "CONSTANT", "0x6A"),
    "FurnitureManager|?FindPeepSlot@CFurnitureManager@@AAEHHPAVCVillager@@@Z": (
        (0xBA,), "GUARDED", "a count of slots; test ebx, je before the division"),
    "HummingbirdClass|?UpdateHummingbirds@theHummingbirdClass@@QAEXUldwPoint@@@Z": ((0x4B0, 0x4CA), "DEAD", ""),
    "HummingbirdClass|?DrawHummingbirds@theHummingbirdClass@@QAEXXZ": ((0x9D, 0xD8), "DEAD", ""),
    "ldwDropDown|?Draw@ldwDropDown@@QAEXUldwPoint@@HUldwColor@@PAVldwFont@@@Z": (
        (0x17A, 0x2A0, 0x408), "NOT SHOWN", "the only drop-down is theAlignVillagerScene's (below)"),
    "ldwDropDown|?HandleMouse@ldwDropDown@@UAE_NHUldwPoint@@@Z": ((0xED, 0x118, 0x215), "NOT SHOWN", "as above"),
    "ldwDropDown|?HandleKey@ldwDropDown@@UAE_NHHH@Z": ((0x4A, 0xF6), "NOT SHOWN", "as above"),
    "ldwGameState|?GetRandom@ldwGameState@@SAHH@Z": (
        (0x19,), "GUARDED", "n == 0 and n < 0 return 0 before rand() % n (test_get_random_guards_zero)"),
    "ldwGameWindow|?SetFrameRate@ldwGameWindow@@QAEXH@Z": ((0xF,), "CONSTANT", "ldwGame's frame rate argument"),
    "ldwGameWindow|?Draw@ldwGameWindow@@QAEXPAVldwImageGrid@@HHH@Z": ((0x25, 0x35), "DATA", "grid column count"),
    "ldwGameWindow|?DrawAdditive@ldwGameWindow@@QAEXPAVldwImageGrid@@HHH@Z": ((0x25, 0x35), "DEAD", ""),
    "ldwGameWindow|?DrawScaled@ldwGameWindow@@QAEXPAVldwImageGrid@@HHHH_N@Z": ((0x37, 0x47), "DATA", "column count"),
    "ldwGameWindow|?DrawScaled@ldwGameWindow@@QAEXPAVldwImageGrid@@HHHMM_N@Z": ((0x37, 0x47), "DATA", "column count"),
    "ldwGameWindow|?DrawStringJustified@ldwGameWindow@@QAEHPBDHHHUldwColor@@PAVldwFont@@_N3H@Z": (
        (0x399,), "GUARDED", "gaps between words; test edx, je"),
    "ldwGameWindow|?Draw@ldwGameWindowImpl@@QAEXPAVldwImageGrid@@HHHM@Z": ((0x25, 0x35), "DATA", "column count"),
    "ldwGameWindow|?DrawScaled@ldwGameWindowImpl@@QAEXPAVldwImageGrid@@HHHMH_N@Z": ((0x25, 0x35), "DATA", "columns"),
    "ldwGameWindow|" + LINE: (
        (0x19E, 0x1A3), "FIXED", "2 x max(|dx|, |dy|): 0 for a zero-length rain streak; patch_zero_length_line_guard"),
    "ldwGameWindow|?BlitRectWithAlpha@ldwGameWindowImpl@@AAEXPAUSDL_Surface@@HHHHHHMM_N@Z": (
        (0x4B6, 0x4CA, 0x4D7, 0x4E3, 0x577, 0x58A, 0x599, 0x5A5, 0x643, 0x64C, 0x65F, 0x698, 0x141E, 0x1440,
         0x144D, 0x1459, 0x14EA, 0x150A, 0x1516, 0x1522, 0x15C9, 0x15D6, 0x15EE, 0x1696),
        "GUARDED", "box-filter pixel counts (do-while trip counts, >= 1) and alpha sums + 0x7F"),
    "ldwGameWindow|?BlitRectWithAlphaTinted@ldwGameWindowImpl@@AAEXPAUSDL_Surface@@HHHHHHMMUldwColor@@@Z": (
        (0x495, 0x4A9, 0x4BF, 0x4DB, 0x508, 0x51E, 0x537, 0x553, 0x57D, 0x586, 0x598, 0x5BA, 0xF7C, 0xF9D, 0xFB3,
         0xFCF, 0xFFC, 0x1010, 0x1037, 0x1053, 0x108D, 0x109A, 0x10B6, 0x112C),
        "GUARDED", "box-filter pixel counts (as above)"),
    "ldwImage|??0ldwImageGrid@@QAE@PBDHH@Z": ((0x5A, 0x69), "DATA", "image-table columns and rows, >= 1"),
    "ldwImage|??0ldwImageGrid@@QAE@PBD0HHHH@Z": ((0x173, 0x188, 0x194, 0x19F), "DATA", "columns, rows, cell sizes"),
    "ldwImage|?GetCellRect@ldwImageGrid@@QAEXHAAUldwRect@@@Z": ((0x17, 0x25), "DATA", "columns and rows"),
    "ldwImage|?GetCellRect@ldwImageGrid@@QAEXHHAAUldwRect@@@Z": ((0x14, 0x20, 0x3C), "DATA", "cell sizes"),
    "ldwImage|?PixelIsVisible@ldwImageGrid@@QAE_NHHUldwPoint@@@Z": ((0x14, 0x20, 0x3C), "DATA", "cell sizes"),
    "ldwImage|?PixelIsVisible@ldwImageGrid@@QAE_NHUldwPoint@@@Z": ((0x7,), "DATA", "columns"),
    "ldwTiledBackground|?SetInteriorSize@ldwTiledBackground@@UAEXHH@Z": ((0x1E, 0x3C), "DATA", "tile width/height"),
    "PetAnimManager|?GetFrame@CPetAnimManager@@QBEXW4EPetAnim@@H_N1AAW4EPetAnimFrame@@AAW4EHeadDirection@@AAW4EDirection@@@Z": (
        (0x3B, 0x4F, 0x5F), "DATA", "frame count: all 19 pet animations >= 1 (built by the constructor)"),
    "PetAnimManager|?LoadAssets@CPetAnimManager@@QAEXXZ": ((0x138, 0x144, 0x1D7, 0x1E3), "DATA", "cell sizes"),
    "ScrollingStoreScene|?HandleMouse@CScrollingStoreScene@@UAE_NHUldwPoint@@@Z": (
        (0x659, 0x727), "GEOMETRY", "range [+154h] (0 for a short page); a drag starts only when it is > 0, and every "
                                    "mouse-up ends it (B205 moves these two by 0x12, same divisors)"),
    "ScrollingStoreScene|?HandleMessage@CScrollingStoreScene@@UAE_NHJ@Z": ((0x13C,), "GUARDED", "test ebx; jle"),
    "ScrollingStoreScene|?DrawScene@CScrollingStoreScene@@MAEXXZ": ((0x97,), "CONSTANT", "0x72"),
    "ScrollingStoreScene|?UpdateScene@CScrollingStoreScene@@MAEXXZ": (
        (0x1E1,), "GEOMETRY", "range [+154h]; only while the fling speed is nonzero, which SetStoreCategory clears"),
    "Smoke|?Update@CSmoke@@QAEXXZ": ((0x43, 0x56), "GUARDED", "test ecx; je"),
    "theAlignVillagerScene|?HandleMouse@theAlignVillagerScene@@UAE_NHUldwPoint@@@Z": (
        (0x1BE, 0x1C6, 0x462, 0x4AC, 0x4EB, 0x4FC, 0x5BD, 0x5C8), "NOT SHOWN",
        "scene 4: no code sets the scene id to 4 (test_the_alignment_editor_is_never_shown)"),
    "theAlignVillagerScene|?DrawSceneAlignment@theAlignVillagerScene@@AAEXXZ": ((0xA9,), "CONSTANT", "10"),
    "theAlignVillagerScene|?DrawSceneEditAnimation@theAlignVillagerScene@@AAEXXZ": ((0x265,), "CONSTANT", "10"),
    "theAlignVillagerScene|?SetupAnimation@theAlignVillagerScene@@AAEXXZ": (
        (0x44F, 0x588), "DATA", "fixed image sizes; runs in the constructor at every start"),
    "theGamewinScene|?UpdateScene@theGamewinScene@@MAEXXZ": ((0x71,), "DEAD", "1 or 2 anyway"),
    "theHelpScene|?HandleMouse@theHelpScene@@UAE_NHUldwPoint@@@Z": ((0x92, 0x132), "GEOMETRY", "fixed help range"),
    "theHelpScene|?UpdateScene@theHelpScene@@MAEXXZ": ((0x72,), "GEOMETRY", "fixed help range, while flung"),
    "theTipDialog|?Init@theTipDialog@@IAEXPBDW4ArrowDirection@@HH_N@Z": (
        (0x106,), "DATA", "the tip font's line height (ldwFont::GetHeight(NULL))"),
    "ToolTray|?PointToSlot@CToolTray@@AAEHUldwPoint@@@Z": ((0xD,), "GEOMETRY", "slot height [+78h] = 0x49"),
    "unzip|?inflate@@YAHPAUz_stream_s@@H@Z": ((0xE2,), "CONSTANT", "31 (the zlib header check)"),
    "unzip|?lufread@@YAIPAXIIPAULUFILE@@@Z": ((0x38, 0x68), "GUARDED", "every caller tests the size first"),
    "VillagerManager|?AllVillagersTimeflowUpkeep@CVillagerManager@@QAEX_N@Z": (
        (0x67, 0x1B3), "STATE", "the game speed [state+25B18h]: 1, 2, 5, 10, 20 or + 999 paused; never 0"),
    "VillagerSkills|?AdvanceCareer@CVillagerSkills@@QAEXAAVCVillager@@_N1@Z": (
        (0x4D,), "GUARDED", "level + 1, or 1 when that is 0 (cmovne)"),
    "Weather|?Random@CWeather@@QBE?BW4EWeather@@W42@@Z": ((0x29, 0x5F), "CONSTANT", "6"),
}


def _require_objs():
    if not (OBJ_DIR / "ldwGameWindow.obj").is_file():
        pytest.skip("the desktop object files (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) are not present")


def _emu_mod():
    _require_objs()
    pytest.importorskip("unicorn")
    sys.path.insert(0, str(ROOT / "tests"))
    import vf2_people_emu
    return vf2_people_emu


def _functions(obj):
    """(name, section, start, end) of every named function in an object."""
    per = defaultdict(list)
    for _idx, (n, v, s, c) in obj.symbols.items():
        if s > 0 and c in (2, 3) and not n.startswith((".", "$")) and obj.sections[s - 1]["chars"] & 0x20:
            per[s].append((v, n))
    for s, syms in per.items():
        syms.sort()
        for k, (v, n) in enumerate(syms):
            yield n, s, v, syms[k + 1][0] if k + 1 < len(syms) else obj.sections[s - 1]["size"]


def _inventory():
    capstone = pytest.importorskip("capstone")
    em = _emu_mod()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    found, ins_of = {}, {}
    for path in sorted(OBJ_DIR.glob("*.obj")):
        obj = em.CoffObject(path)
        for name, s, start, end in _functions(obj):
            sec = obj.sections[s - 1]
            code = obj.data[sec["ptr"] + start:sec["ptr"] + end]
            ins = list(md.disasm(code, start))
            sites = tuple(x.address for x in ins if x.mnemonic in ("div", "idiv"))
            if sites:
                found[f"{path.stem}|{name}"] = sites
                ins_of[f"{path.stem}|{name}"] = ins
    return found, ins_of


@pytest.fixture(scope="module")
def inventory():
    return _inventory()


def test_every_division_is_audited(inventory):
    found, _ins = inventory
    assert sum(len(v) for v in found.values()) == 185
    assert {k: tuple(v) for k, v in found.items()} == {k: v[0] for k, v in AUDIT.items()}
    assert {v[1] for v in AUDIT.values()} <= {"CONSTANT", "GUARDED", "DATA", "GEOMETRY", "STATE", "NOT SHOWN",
                                               "DEAD", "LATENT", "FIXED"}
    assert [k for k, v in AUDIT.items() if v[1] == "FIXED"] == ["ldwGameWindow|" + LINE]
    counts = defaultdict(int)
    for sites, verdict, _why in AUDIT.values():
        counts[verdict] += len(sites)
    # the numbers docs/Transparency Log.txt gives
    assert dict(counts) == {"CONSTANT": 16, "GUARDED": 74, "DATA": 49, "GEOMETRY": 16, "STATE": 2, "NOT SHOWN": 16,
                            "DEAD": 9, "LATENT": 1, "FIXED": 2}


def test_bank_and_money_hold_no_integer_division(inventory):
    found, _ins = inventory
    assert not [k for k in found if k.startswith(("BankDialog|", "Money|"))]


def test_constant_divisors_are_nonzero_immediates(inventory):
    """Every CONSTANT site's divisor register was last loaded with a nonzero immediate in the same function."""
    _found, ins_of = inventory
    from capstone import x86
    checked = 0
    for key, (sites, verdict, _why) in AUDIT.items():
        if verdict != "CONSTANT" or key.startswith(("ldwGameWindow|?SetFrameRate", "unzip|")):
            continue
        ins = ins_of[key]
        for i, x in enumerate(ins):
            if x.address not in sites:
                continue
            reg = x.reg_name(x.operands[0].reg)
            for k, y in reversed(list(enumerate(ins[:i]))):
                if y.mnemonic == "pop" and any(z.mnemonic == "ret" for z in ins[k:i]):
                    continue        # a return path in between (CWeather::Random's pop edi; ret before +0x5B)
                if reg in {y.reg_name(r) for r in y.regs_access()[1]}:
                    assert y.mnemonic == "mov" and y.operands[1].type == x86.X86_OP_IMM, (key, hex(x.address))
                    assert y.operands[1].imm != 0, (key, hex(x.address))
                    checked += 1
                    break
            else:
                raise AssertionError((key, hex(x.address)))
    assert checked == sum(len(v[0]) for k, v in AUDIT.items() if v[1] == "CONSTANT"
                          and not k.startswith(("ldwGameWindow|?SetFrameRate", "unzip|")))


def test_inflate_and_frame_rate_divisors_are_fixed_numbers(inventory):
    _found, ins_of = inventory
    inflate = {x.address: (x.mnemonic, x.op_str) for x in ins_of["unzip|?inflate@@YAHPAUz_stream_s@@H@Z"]}
    assert inflate[0x41] == ("mov", "dword ptr [ebp + 8], 0x1f") and inflate[0xE2] == ("div", "dword ptr [ebp + 8]")
    # ldwGame's constructor is SetFrameRate's only caller; the rate is the game's own fixed number
    em = _emu_mod()
    obj = em.CoffObject(OBJ_DIR / "ldwGame.obj")
    names = {obj.symbols[si][0] for s in obj.sections for _va, si, _t in s["relocs"]}
    assert "?SetFrameRate@ldwGameWindow@@QAEXH@Z" in names


# --------------------------------------------------------------------------------------- the data behind DATA

def test_achievement_targets():
    em = _emu_mod()
    obj = em.CoffObject(OBJ_DIR / "Achievement.obj")
    (value, sect), = [(v, s) for n, v, s, c in obj.symbols.values()
                      if n == "?achievementList@@3PAUsAchievementListEntry@@A" and s > 0]
    sec = obj.sections[sect - 1]
    raw = obj.data[sec["ptr"] + value:sec["ptr"] + sec["size"]]
    rows = [struct.unpack_from("<7i", raw, k) for k in range(0, len(raw) - 0x1B, 0x1C)]
    assert len(rows) == 95 and [r[0] for r in rows] == list(range(95))
    assert min(r[1] for r in rows) == 1


def _strcopy(e):
    dst, src, n = e.arg(0), e.arg(1), e.arg(2)
    e.write(dst, e.cstr(src).encode("latin-1")[:max(0, n - 1)] + b"\0")


@pytest.mark.parametrize("name, ctor, stride, frames, mode, count, expected", [
    ("AnimManager", "??0CAnimManager@@QAE@XZ", 0xEC, 0xE0, 0xE8, 0x76EC, 29),
    ("PetAnimManager", "??0CPetAnimManager@@QAE@XZ", 0x1AC, 0x1A0, 0x1A8, 0xC6F4, 19),
])
def test_built_in_animations_have_frames(name, ctor, stride, frames, mode, count, expected):
    em = _emu_mod()
    e = em.Emu(OBJ_DIR, [name])
    e.seam("?ldwStrCopy@@YAXPADPBDH@Z", lambda e: (_strcopy(e), (0, 0))[1])
    this = e.alloc(0x80000)
    e.call(ctor, (), ecx=this)
    n = e.s32(this + count)
    assert n == expected
    rows = [(e.s32(this + k * stride + frames), e.s32(this + k * stride + mode)) for k in range(n)]
    assert min(f for f, _m in rows) >= 1 and {m for _f, m in rows} <= {0, 1, 2}


def test_anims_dat_frame_counts():
    path = GAME_DIR / "Assets" / "anims.dat"
    if not path.is_file():
        pytest.skip("work/vanilla_runtime_payload (or VF2_VANILLA_GAME_DIR) is not present")
    data = path.read_bytes()
    size, count = struct.unpack_from("<ii", data, 0)
    assert size == count * 0xEC == len(data) - 8 and count == 104
    for k in range(count):
        frames, mode = struct.unpack_from("<i4xi", data, 8 + k * 0xEC + 0xE0)
        assert frames >= 1 and mode in (0, 1, 2), k


def test_furniture_map_widths():
    maps = sorted(GAME_DIR.rglob("*.fmap")) + sorted(ROOT.glob("patcher_assets/**/*.fmap"))
    if not maps:
        pytest.skip("no furniture maps (work/vanilla_runtime_payload) are present")
    for path in maps:
        data = path.read_bytes()
        assert data[:4] in (b"PAMF", b"QAMF"), path
        block = struct.unpack_from("<i", data, 8)[0]
        width, height = struct.unpack_from("<ii", data, block + 8)
        assert width >= 1 and height >= 1, path


def test_image_table_counts():
    sys.path.insert(0, str(ROOT / "src"))
    import vf2_game_pictures as gp
    table = gp.table()
    assert all(e.cols >= 1 and e.rows >= 1 for e in table if e.kind == "grid")
    assert all(e.cols >= 1 for e in table if e.kind == "strip")
    assert not [e for e in table if e.cols < 0 or e.rows < 0]


def test_game_speed_writers_never_store_zero():
    """Every write to the speed field [theGameState+25B18h] in the objects stores 10 or adds 999, and Time
    Controls only ever stores 1, 2, 5, 10, 20 (or those + 999); the Space key's resume makes 0 into 10."""
    capstone = pytest.importorskip("capstone")
    em = _emu_mod()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    writes = set()
    for path in sorted(OBJ_DIR.glob("*.obj")):
        obj = em.CoffObject(path)
        for name, s, start, end in _functions(obj):
            sec = obj.sections[s - 1]
            for x in md.disasm(obj.data[sec["ptr"] + start:sec["ptr"] + end], start):
                if "+ 0x25b18]" in x.op_str and x.op_str.startswith("dword ptr") and x.mnemonic not in ("cmp", "div"):
                    writes.add((path.stem, x.mnemonic, x.op_str.split(", ")[-1]))
    # theMainScene::HandleKeyCharacter (Space): resume stores field - 999, or 10 when that is 0 (cmove), pause
    # adds 999; CScrollingStoreScene::HandleUpgrade stores field - 999 only when field > 999, then puts the old
    # value back
    assert writes == {("theCreateNickNameDlg", "mov", "0xa"), ("theGameState", "mov", "0xa"),
                      ("theOptionsDialog", "add", "0x3e7"), ("theOptionsDialog", "mov", "0xa"),
                      ("theChangePlayerDlg", "mov", "0xa"), ("theMainScene", "add", "0x3e7"),
                      ("theMainScene", "mov", "esi"), ("ScrollingStoreScene", "mov", "eax"),
                      ("ScrollingStoreScene", "mov", "esi")}
    key, _r = _code_of("theMainScene", "?HandleKeyCharacter@theMainScene@@IAE?B_ND@Z")
    assert key[0x223:0x228] == bytes.fromhex("8BF0" "0F44F1")              # esi = field - 999; if 0: esi = 10
    assert bytes.fromhex("B90A000000") in key[0x200:0x223]                 # (ecx = 10)
    upgrade, _r = _code_of("ScrollingStoreScene", "?HandleUpgrade@CScrollingStoreScene@@AAEXXZ")
    assert upgrade[0x4FF:0x519] == bytes.fromhex("8BB7185B0200" "81FEE7030000" "7E0C" "8D8619FCFFFF"
                                                 "8987185B0200")
    header = (ROOT / "runtime" / "native" / "b200time" / "b200time_time.inc").read_text(encoding="utf-8")
    assert "if (speed <= 0) speed = B200TC_SPEED_NORMAL;" in header


def test_get_random_guards_zero():
    em = _emu_mod()
    e = em.Emu(OBJ_DIR, ["ldwGameState"])
    e.seam("_rand", lambda e: (12345, 0))
    fn = "?GetRandom@ldwGameState@@SAHH@Z"
    assert [e.call(fn, (n,)) for n in (0, -1, -7, 1)] == [0, 0, 0, 0]
    assert e.call(fn, (7,)) == 12345 % 7 and e.call(fn, (100,)) == 45


# ----------------------------------------------------------------------------------- LATENT and NOT SHOWN

def _code_of(obj_name, fn):
    em = _emu_mod()
    obj = em.CoffObject(OBJ_DIR / f"{obj_name}.obj")
    for name, s, start, end in _functions(obj):
        if name == fn:
            sec = obj.sections[s - 1]
            relocs = {va: obj.symbols[si][0] for va, si, _t in sec["relocs"] if start <= va < end}
            return obj.data[sec["ptr"] + start:sec["ptr"] + end], relocs
    raise KeyError(fn)


def _divide_error(e, target, run):
    """Run, and return the address of a #DE (interrupt 0) or None."""
    from unicorn import UC_HOOK_INTR
    from unicorn.x86_const import UC_X86_REG_EIP
    hit = []

    def intr(uc, intno, _user):
        hit.append((intno, uc.reg_read(UC_X86_REG_EIP)))
        uc.emu_stop()
    h = e.uc.hook_add(UC_HOOK_INTR, intr)
    try:
        run()
    except Exception:
        if not hit:
            raise
    finally:
        e.uc.hook_del(h)
    if not hit:
        return None
    # unicorn reports #DE as interrupt 0, or 8 when it cannot deliver it (no IDT here); either way the
    # instruction at EIP must be the div/idiv itself (F7 /6 or /7)
    intno, eip = hit[0]
    modrm = e.read(eip, 2)
    assert intno in (0, 8) and modrm[0] == 0xF7 and (modrm[1] >> 3) & 7 in (6, 7), hit
    return eip - target


def test_poll_result_division_faults_on_zero_total_votes():
    """The dialog's own instructions +0x1E5..+0x1F7: percent = votes1 * 100 / totalVotes."""
    em = _emu_mod()          # skips without the objects or unicorn, before unicorn is imported
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX
    e = em.Emu(OBJ_DIR, ["CommunityEventDialog"])
    entry = e.addr("??0CCommunityEventDialog@@QAE@HHHHHH@Z")
    frame, this = e.alloc(0x100), e.alloc(0x1000)

    def run(total, votes1):
        e.w32(frame + 0x14, total)
        e.w32(frame + 0x18, votes1)
        e.uc.reg_write(UC_X86_REG_EBP, frame)
        e.uc.reg_write(UC_X86_REG_EBX, this)
        return _divide_error(e, entry, lambda: e.uc.emu_start(entry + 0x1E5, entry + 0x1F7))
    assert run(0, 5) == 0x1F4
    assert run(40, 10) is None and e.uc.reg_read(UC_X86_REG_EAX) == 25


def test_poll_result_needs_a_login():
    """Polls are asked for only once CLogIn says logged in; without a result (-1) the dialog never divides."""
    update, relocs = _code_of("CommunityEvent", "?Update@CCommunityEvent@@QAEXXZ")
    calls = [relocs[va] for va in sorted(relocs) if relocs[va].startswith("?")]
    assert calls.index("?IsLoggedIn@CLogIn@@QAE?B_NXZ") < calls.index(
        "?Begin@CPoll@@QAE?B_NP6AXHHPAX@ZP6AXHHHHHH0@Z0@Z")
    assert update[0x22:0x26] == bytes.fromhex("84C07415")             # test al,al; je (not logged in: no poll)
    poll, _r = _code_of("CommunityEvent", "?PollCallback@CCommunityEvent@@CAXHHPAX@Z")
    assert bytes.fromhex("C704CD0C000000FFFFFFFF") in poll           # a poll without a result: result -1
    ctor, _r = _code_of("CommunityEventDialog", "??0CCommunityEventDialog@@QAE@HHHHHH@Z")
    assert ctor[0x19B:0x1A3] == bytes.fromhex("85C00F8EA8000000")    # result <= 0: no division


def test_the_alignment_editor_is_never_shown(inventory):
    """theGame::ActivateCurrentScene shows theAlignVillagerScene for scene id 4; nothing stores 4."""
    capstone = pytest.importorskip("capstone")
    em = _emu_mod()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    stored, change_scene = set(), set()
    for path in sorted(OBJ_DIR.glob("*.obj")):
        obj = em.CoffObject(path)
        for name, s, start, end in _functions(obj):
            sec = obj.sections[s - 1]
            relocs = {va: obj.symbols[si][0] for va, si, _t in sec["relocs"]}
            pushes = []
            for x in md.disasm(obj.data[sec["ptr"] + start:sec["ptr"] + end], start):
                if x.mnemonic == "mov" and x.op_str.startswith("dword ptr [") and "+ 0x25cb8]" in x.op_str:
                    stored.add(x.op_str.split(", ")[-1])
                if x.mnemonic == "push":
                    pushes.append(x.op_str)
                elif x.mnemonic == "call":
                    target = next((relocs[a] for a in range(x.address, x.address + 5) if a in relocs), "")
                    if "?ChangeScene@" in target and target != name:
                        change_scene.add(pushes[-1])           # the scene id is the first argument
                    pushes = []
    assert "4" not in stored and "0x4" not in stored
    assert stored - {"eax", "ecx"} == {"0", "1", "2", "5", "6", "9", "0xc", "0xf"}
    assert "4" not in change_scene and change_scene <= {"1", "7", "8", "0xa", "0xb", "0xd", "0xf"}
    obj = em.CoffObject(OBJ_DIR / "ldwDropDown.obj")
    users = set()
    for path in sorted(OBJ_DIR.glob("*.obj")):
        o = em.CoffObject(path)
        if any(o.symbols[si][0] == "??0ldwDropDown@@QAE@PAPBDHH@Z" for s in o.sections for _v, si, _t in s["relocs"]):
            users.add(path.stem)
    assert users - {"ldwDropDown"} == {"theAlignVillagerScene"} and obj


# ------------------------------------------------------------------------------------------ the bank dialog

def _bank_rig(money, history):
    em = _emu_mod()          # skips without the objects or unicorn, before unicorn is imported
    from unicorn.x86_const import UC_X86_REG_XMM0
    e = em.Emu(OBJ_DIR, ["BankDialog"])
    window, rects = e.alloc(0x100), []
    e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda e: (window, 0))
    e.seam("?FillRect@ldwGameWindow@@QAEXAAUldwRect@@UldwColor@@@Z",
           lambda e: (rects.append(struct.unpack("<4i", e.read(e.arg(0), 16))), (0, 8))[1])
    for name, pop in (("?FrameRect@ldwGameWindow@@QAEXAAUldwRect@@UldwColor@@@Z", 8),
                      ("?DrawLine@ldwGameWindow@@QAEXHHHHUldwColor@@@Z", 0x14),
                      ("?DrawStringRight@ldwGameWindow@@QAEXPBDHHUldwColor@@PAVldwFont@@@Z", 0x14),
                      ("?DrawString@ldwGameWindow@@QAEXPBDHHUldwColor@@PAVldwFont@@@Z", 0x14),
                      ("?DrawStringCentered@ldwGameWindow@@QAEXPBDHHUldwColor@@PAVldwFont@@@Z", 0x14),
                      ("?MoneyAsString@CMoney@@SAXNPADH_N@Z", 0),
                      ("?GetString@theStringManager@@QAEPADW4StringId@@@Z", 4)):
        e.seam(name, lambda e, pop=pop: (0, pop))
    e.seam("?Get@theStringManager@@SAPAV1@XZ", lambda e: (window, 0))

    def dtoui3(e):     # the CRT's double -> unsigned: xmm0 in, eax out
        v = struct.unpack("<d", (e.uc.reg_read(UC_X86_REG_XMM0) & (2 ** 64 - 1)).to_bytes(8, "little"))[0]
        return int(v) & 0xFFFFFFFF, 0
    e.seam("__dtoui3", dtoui3)
    this = e.alloc(0x200)
    for k, v in enumerate(history):
        e.write(this + 0x54 + 8 * k, struct.pack("<d", v))
    e.write(this + 0x84, struct.pack("<d", money))
    e.w32(this + 0x8C, 300)
    e.w32(this + 0x90, 100)
    e.call("?DrawNoFadeScene@CBankingDlg@@MAEXXZ", (), ecx=this)
    return rects


def test_bank_dialog_has_no_integer_division_and_zero_money_does_not_fault():
    """VF1's crash is here in VF2 only as floating point: $0 (or under $0.83) makes the chart's top 0.0, each bar
    is x / 0.0 (infinity or NaN) and cvttsd2si gives 0x80000000: the bars run off the top of the panel (clipped),
    but nothing faults. A normal balance draws normal bars."""
    rects = _bank_rig(0.0, [0.0] * 6)
    bars = [r for r in rects if r[2] - r[0] == 0x1E]
    assert len(bars) == 7 and all(r[1] < -2_000_000_000 for r in bars)
    rects = _bank_rig(1200.0, [100.0, 200.0, 300.0, 600.0, 900.0, 1000.0])
    bars = [r for r in rects if r[2] - r[0] == 0x1E]
    assert len(bars) == 7 and all(-1000 < r[1] <= r[3] for r in bars)


# --------------------------------------------------------------------------------------- the FIXED site

@pytest.fixture(scope="module")
def patched_line(tmp_path_factory):
    _require_objs()
    pytest.importorskip("capstone")
    sys.path.insert(0, str(WORK))
    import patch_mobile_furniture_pack as patcher
    out = tmp_path_factory.mktemp("zero_line")
    old = patcher.PATCHED, patcher.SRC_OBJS
    try:
        patcher.PATCHED, patcher.SRC_OBJS = out, OBJ_DIR
        shutil.copy2(OBJ_DIR / "ldwGameWindow.obj", out / "ldwGameWindow.obj")
        manifest = {}
        patcher.patch_zero_length_line_guard(manifest)
    finally:
        patcher.PATCHED, patcher.SRC_OBJS = old
    return out, manifest


class _LineRig:
    """ldwGameWindowImpl with an 800 x 600 32-bit surface; DrawLine's SDL calls answered here."""
    W, H = 800, 600

    def __init__(self, obj_dir, flag):
        em = _emu_mod()
        self.e = e = em.Emu(obj_dir, ["ldwGameWindow"])
        for name in ("_SDL_MapRGB", "_SDL_LockSurface", "_SDL_UnlockSurface"):
            e.seam(name, lambda e: (0, 0))
        e.seam("_SDL_MapRGBA", lambda e: (0x000000FF, 0))     # alpha in the low byte, as the game's surfaces
        self.pixels = e.alloc(self.W * self.H * 4)
        surface, fmt = e.alloc(0x40), e.alloc(0x40)
        e.w32(surface + 4, fmt)
        e.w32(surface + 0x10, self.W * 4)
        e.w32(surface + 0x14, self.pixels)
        self.this = e.alloc(0x100)
        e.w32(self.this + 0x30, surface)
        for off, v in ((0x60, 0), (0x64, 0), (0x68, self.W - 1), (0x6C, self.H - 1)):
            e.w32(self.this + off, v)
        if FLAG in e.data_stubs or FLAG in e.globals:
            e.write(e.addr(FLAG), bytes([flag]))
        self.entry = e.addr(LINE)

    def draw(self, x1, y1, x2, y2, colour=0x00336699, a1=0.75, a2=0.25):
        e = self.e
        e.write(self.pixels, b"\x10\x20\x30\x40" * (self.W * self.H))
        fault = _divide_error(e, self.entry, lambda: e.call(LINE, (x1, y1, x2, y2, colour, a1, a2), ecx=self.this))
        return fault, None if fault is not None else e.read(self.pixels, self.W * self.H * 4)


LINES = [(10, 10, 200, 40), (200, 40, 10, 10), (5, 5, 5, 300), (5, 300, 5, 5), (0, 0, 799, 0), (3, 7, 4, 7),
         (100, 100, 101, 101), (700, 20, 30, 590), (30, 590, 700, 20), (400, 300, 400, 301), (0, 599, 799, 0)]


def test_the_stock_line_divides_by_zero_for_one_point():
    rig = _LineRig(OBJ_DIR, 0)
    fault, _ = rig.draw(0, 0, 0, 0)
    assert fault == 0x1A3                                    # idiv ebx: 2 x max(|dx|, |dy|) = 0
    assert rig.draw(250, 120, 250, 120)[0] == 0x1A3
    assert rig.draw(10, 10, 200, 40)[0] is None


def test_the_fixed_line_draws_its_one_pixel(patched_line):
    out, manifest = patched_line
    assert manifest["ZeroLengthLineGuard"]["branch"] == "0x199"
    rig = _LineRig(out, 1)
    fault, pixels = rig.draw(250, 120, 250, 120)
    assert fault is None
    blank = b"\x10\x20\x30\x40" * (rig.W * rig.H)
    changed = [k // 4 for k in range(0, len(pixels), 4) if pixels[k:k + 4] != blank[k:k + 4]]
    assert changed == [120 * rig.W + 250]
    # the pixel is a line's first pixel: the same as a 2-pixel line's first one
    _f, two = rig.draw(250, 120, 251, 120)
    at = (120 * rig.W + 250) * 4
    assert pixels[at:at + 4] == two[at:at + 4]
    assert rig.draw(0, 0, 0, 0)[0] is None


def test_the_fixed_line_with_the_byte_off_is_stock(patched_line):
    out, _manifest = patched_line
    rig = _LineRig(out, 0)
    fault, _ = rig.draw(250, 120, 250, 120)
    assert fault == 0x391                                    # the stub's copy of the stock idiv ebx


@pytest.mark.parametrize("flag", [0, 1])
def test_every_other_line_is_drawn_exactly_as_stock(patched_line, flag):
    out, _manifest = patched_line
    stock, fixed = _LineRig(OBJ_DIR, 0), _LineRig(out, flag)
    for line in LINES:
        for alphas in ((0.75, 0.25), (1.0, 1.0), (0.0, 1.0)):
            a, b = stock.draw(*line, a1=alphas[0], a2=alphas[1]), fixed.draw(*line, a1=alphas[0], a2=alphas[1])
            assert a[0] is None and b[0] is None and a[1] == b[1], (line, alphas)


def test_the_patched_bytes(patched_line):
    out, _manifest = patched_line
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    em = _emu_mod()
    obj = em.CoffObject(out / "ldwGameWindow.obj")
    (name, s, start, end), = [f for f in _functions(obj) if f[0] == LINE]
    sec = obj.sections[s - 1]
    code = obj.data[sec["ptr"]:sec["ptr"] + sec["size"]]
    assert sec["size"] == 0x377 + 0x21
    assert code[0x199:0x1A5] == b"\xE9" + struct.pack("<i", 0x377 - 0x19E) + b"\x90" * 7
    relocs = {va: obj.symbols[si][0] for va, si, _t in sec["relocs"]}
    assert relocs[0x377 + 0x0F] == FLAG
    stub = [(x.address - 0x377, x.mnemonic, x.op_str) for x in Cs(CS_ARCH_X86, CS_MODE_32).disasm(code[0x377:], 0x377)]
    assert stub == [(0x00, "cmp", "edx, ebx"), (0x02, "cdq", ""), (0x03, "jle", "0x384"),
                    (0x05, "idiv", "dword ptr [ebp - 0xc]"), (0x08, "jmp", "0x1a5"),
                    (0x0D, "cmp", "byte ptr [0], 0"), (0x14, "je", "0x391"), (0x16, "test", "ebx, ebx"),
                    (0x18, "je", "0x393"), (0x1A, "idiv", "ebx"), (0x1C, "jmp", "0x1a5")]
    # no branch of the stock function lands inside the replaced 12 bytes but the one the stub reproduces
    stock_code, _r = _code_of("ldwGameWindow", LINE)
    for x in Cs(CS_ARCH_X86, CS_MODE_32).disasm(stock_code, 0):
        if x.mnemonic.startswith("j") and x.op_str.startswith("0x"):
            target = int(x.op_str, 16)
            assert not 0x199 < target < 0x1A5 or (x.address, target) == (0x19C, 0x1A3), hex(x.address)


def test_rain_is_the_only_caller_and_a_new_drop_keeps_its_old_tail():
    """CRain::Draw passes each drop's head and tail to this DrawLine. CRain::Reset gives each drop a random head
    and a speed of 10-11 across and 20-59 down but leaves the tail; CRain::Update moves the tail to the head and
    the head on by the speed. CWeather::Update updates the rain before it may call SetCurrent(rain) (which calls
    CRain::Reset), and the frame's CWeather::Draw comes after: a head that lands on its old tail is a point."""
    em = _emu_mod()
    callers = set()
    for path in sorted(OBJ_DIR.glob("*.obj")):
        o = em.CoffObject(path)
        for name, s, start, end in _functions(o):
            sec = o.sections[s - 1]
            if any(start <= va < end and o.symbols[si][0] == "?DrawLine@ldwGameWindow@@QAEXHHHHUldwColor@@MM@Z"
                   for va, si, _t in sec["relocs"]):
                callers.add(f"{path.stem}|{name}")
    assert callers == {"Rain|?Draw@CRain@@QAEXXZ"}
    wrapper, relocs = _code_of("ldwGameWindow", "?DrawLine@ldwGameWindow@@QAEXHHHHUldwColor@@MM@Z")
    assert set(relocs.values()) == {LINE}

    weather, relocs = _code_of("Weather", "?Update@CWeather@@QAEXXZ")
    order = [relocs[va] for va in sorted(relocs) if relocs[va] in (
        "?Update@CRain@@QAEXXZ", "?SetCurrent@CWeather@@QAEXW4EWeather@@H@Z")]
    assert order[0] == "?Update@CRain@@QAEXXZ" and order.count("?SetCurrent@CWeather@@QAEXW4EWeather@@H@Z") == 2
    _code, relocs = _code_of("Weather", "?SetCurrent@CWeather@@QAEXW4EWeather@@H@Z")
    assert "?Reset@CRain@@QAEX_N@Z" in relocs.values()

    e = em.Emu(OBJ_DIR, ["Rain"])
    window = e.alloc(0x100)
    e.seam("?Get@ldwGameWindow@@SAPAV1@XZ", lambda e: (window, 0))
    e.seam("?GetWidth@ldwGameWindow@@QAEHXZ", lambda e: (800, 0))
    e.seam("?GetHeight@ldwGameWindow@@QAEHXZ", lambda e: (600, 0))
    e.seam("?Play@CSound@@QAEXW4ESound@@_NM@Z", lambda e: (0, 12))
    picks = iter([0, 0, 0, 0] + [7919 * k for k in range(4000)])   # drop 0's head at (0,0): its tail is (0,0)
    e.seam("?GetRandom@ldwGameState@@SAHH@Z", lambda e: (next(picks) % max(1, e.sarg(0)), 0))
    rain = e.alloc(0x4000)
    e.call("??0CRain@@QAE@XZ", (), ecx=rain)
    e.call("?Reset@CRain@@QAEX_N@Z", (0,), ecx=rain)
    drops = [struct.unpack_from("<6i", e.read(rain + 0x18 * k, 0x18)) for k in range(512)]
    assert drops[0][:4] == (0, 0, 0, 0)                      # a point: the stock DrawLine divides by zero
    assert {d[4] for d in drops} <= {10, 11} and min(d[5] for d in drops) >= 20


# --------------------------------------------------------------------------------------- docs and wiring

def test_the_fix_is_part_of_fix_vanilla_game_bugs():
    source = (WORK / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    body = source.split("\ndef patch_fix_vanilla_game_bugs(manifest):\n", 1)[1].split("\ndef ", 1)[0]
    assert "\n    patch_zero_length_line_guard(manifest)\n" in body
    assert '"ZeroLengthLineGuard",' in body


def test_the_documents_describe_it():
    for name in ("README.md", "Transparency Log.txt", "docs/Transparency Log.txt"):
        assert "zero-length" in (ROOT / name).read_text(encoding="utf-8"), name
    sys.path.insert(0, str(ROOT / "src"))
    import vf2_game_mechanics as gm
    texts = [f.text for f in gm.facts()]
    assert any(t.startswith(gm.WITH_PATCHER) and "rain" in t and "zero" in t for t in texts)
    assert any(t.startswith(gm.UNPATCHED) and "rain" in t and "zero" in t for t in texts)


# --------------------------------------------------------------------------------- the shipped executable

def _pattern(obj_name, fn, obj_dir=None):
    """The function's bytes (to its section's end, so a patched function's appended stub too), relocations
    masked."""
    em = _emu_mod()
    obj = em.CoffObject(Path(obj_dir or OBJ_DIR) / f"{obj_name}.obj")
    for name, s, start, end in _functions(obj):
        if name == fn:
            sec = obj.sections[s - 1]
            code = obj.data[sec["ptr"] + start:sec["ptr"] + end]
            masked = set()
            for va, _si, _t in sec["relocs"]:
                if start <= va < end:
                    masked.update(range(va - start, va - start + 4))
            return re.compile(b"".join(b"." if k in masked else re.escape(bytes([b]))
                                       for k, b in enumerate(code)), re.S)
    raise KeyError(fn)


SHIPPED_SAME = [
    ("ldwGameState", "?GetRandom@ldwGameState@@SAHH@Z"),
    ("CommunityEventDialog", "??0CCommunityEventDialog@@QAE@HHHHHH@Z"),
    ("CommunityEvent", "?Update@CCommunityEvent@@QAEXXZ"),
    ("ldwGameWindow", LINE),
    ("Rain", "?Draw@CRain@@QAEXXZ"), ("Rain", "?Reset@CRain@@QAEX_N@Z"), ("Rain", "?Update@CRain@@QAEXXZ"),
    ("BankDialog", "?DrawNoFadeScene@CBankingDlg@@MAEXXZ"),
    ("Achievement", "?PercentCompleted@CAchievement@@AAEHW4EAchievement@@@Z"),
    ("VillagerManager", "?AllVillagersTimeflowUpkeep@CVillagerManager@@QAEX_N@Z"),
    ("ScrollingStoreScene", "?UpdateScene@CScrollingStoreScene@@MAEXXZ"),
]


def test_a_shipped_executable_runs_this_code(patched_line):
    """With VF2_CORE_EXE (path or glob): every function run above is in it exactly once (relocations aside).
    DrawLine is either the stock one (an executable built before this fix) or, exactly once, the patched one:
    its detour, the whole 0x21-byte stub and the .vf2bugs reference (a build with this fix); never neither."""
    if not CORE_EXE:
        pytest.skip("VF2_CORE_EXE is not set to a shipped core executable")
    pefile = pytest.importorskip("pefile")
    out, _manifest = patched_line
    fixed = _pattern("ldwGameWindow", LINE, out)
    paths = sorted(glob.glob(CORE_EXE)) or [CORE_EXE]
    for path in paths:
        pe = pefile.PE(path, fast_load=True)
        text = next(s.get_data() for s in pe.sections if s.Name.rstrip(b"\0") == b".text")
        for obj_name, fn in SHIPPED_SAME:
            hits = len(_pattern(obj_name, fn).findall(text))
            if fn == LINE:
                patched = len(fixed.findall(text))
                assert (hits, patched) in ((1, 0), (0, 1)), (path, hits, patched)
            else:
                assert hits == 1, (path, fn, hits)
