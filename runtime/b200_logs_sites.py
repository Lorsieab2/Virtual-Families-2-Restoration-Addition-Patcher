"""Family Logs: every site in the B200 Virtual Families 2 executable (core variant).

Single source of truth for every address the companion DLL vf2logs_b200.dll touches or relies on. It
is the Virtual Families 1 Family Logs DLL (vf1logs.dll) ported to Virtual Families 2: plain-text family
logs written when the game makes each event, in the same files, folders, headers and line formats.

Each pin is the exact bytes of the B200 link output (`Virtual Families 2 - B200.exe`, core variant,
built by work/patch_mobile_furniture_pack.py) of one game function or of the run of a function around
the call the DLL retargets. The image is relocated (DYNAMICBASE + .reloc) and every matrix variant
links to different addresses, so the DLL holds no address: it searches the live image for each pinned
run (relocated 32-bit fields and call/jmp rel32 displacements are wildcards) and derives every address
from where the runs were found. runtime/tools/gen_b200_logs_sites.py proves every pin and derivation on
the core variant with capstone + pefile and renders the C header the DLL is built from.

The other two companion DLLs are loaded first by the same loader (Time Controls, then Up to 28
Children) and both have written their hooks before this DLL resolves anything:

* Up to 28 Children writes a 5-byte jmp at the entry of AddOffspring, ReportDeath, StartNextGeneration,
  Reset and theGameState::Save / Load (and others this DLL does not use). Pins of those functions mark
  their first five bytes as wildcards (`skip`), and this DLL never writes them: it retargets the CALLS
  that reach them, and the call then goes through Up to 28 Children's hook as before.
* Time Controls replaces theGameState's Save and Load vtable slots (13 and 14) and retargets the
  IncrementAge call in AllVillagersTimeflowUpkeep (a call displacement: a wildcard here). This DLL
  finds the vtable from theGameState's constructor and chains to whatever the slots hold.

How each event is seen (every call path traced in the core executable; see docs/FAMILY_LOGS.md):

* conception: CVillager::Impregnate (entry hook). Its two callers (theMainScene's try-for-a-baby and
  CVillagerPlans::ProcessCurrentPlan, through a jmp) both pass (1, "Joey", father's head, father's body,
  0) with the mother as `this`; it returns al = 1 and pops 14h.
* birth: the one call of AllVillagersRealtimePhysiologyAndProductivityUpkeep (theRealtimeManager::
  UpdateAll). The only delivery is inside it: the reserved baby slots become active and are set to -1,
  and the mother's pregnancy field (+6B18h) is written 0 there once.
* death: the two calls of CFamilyTree::ReportDeath (AllVillagersTimeflowUpkeep, CVillagerPlans::
  StartNewBehavior); both deactivate the villager right after it, so each death is reported once.
* marriage: the one call of CFamilyTree::UpdateParents (CDatingScene).
* a family begins / Next Generation: CAdoptionScene::HandleMessage's StartFamilyTree call (a new
  family, or the first one after Evict Family) and its Next Generation call.
* a child joins: the AddOffspring calls of The Little Visitor (1 and 2) and Adoption Services.
* leaving home: the three calls of CVillager::SetLeftHome (college in AllVillagersTimeflowUpkeep,
  Boarding School in the store, The Talent Scout).
* Evict Family: theOptionsDialog::EvictFamily's call of CFamilyTree::EvictFamily (before the household
  is removed).
* Start Over: the theGameState::Init call of the title menu's confirmed Start Over (B200's Fix Vanilla
  Game Bugs stub, the only Start Over the game has).
* save / load: theGameState's vtable slots 14 / 13.
"""
from __future__ import annotations

IMAGE_BASE = 0x400000
B200_EXE_NAME = "Virtual Families 2 - B200.exe"

PATCHER_FOLDER = "Virtual Families 2 Patcher Files"
DLL_NAME = "vf2logs_b200.dll"
INI_NAME = "vf2logs.ini"
INI_KEY = "FamilyLogs"
STARTUP_EXPORT = "B200Logs_Startup"
STATUS_EXPORT = "B200Logs_Status"
STATUS_MAGIC = 0x474C3242               # 'B2LG'
LOGS_FOLDER = "Virtual Families 2 Patcher"   # <save folder>\Virtual Families 2 Patcher\Save <N>\...

# Layout constants (each proved by an operand of the pinned code, see the prover's cross-checks).
TREE_EVICTED = 0x00                     # CFamilyTree+0: 1 after Evict Family (EvictFamily: Reset, then 1)
TREE_GENERATIONS_FIELD = 0x04           # CFamilyTree+4: records in use (1-based; 0 = no family)
FAMILY_RECORD_SIZE = 0x6C8
FAMILY_RECORD_BASE = 0x6C0              # record of generation g = tree + g * 0x6C8 - 0x6C0
TREE_GENERATIONS = 30
RECORD_PARENT1 = 0x04
RECORD_PARENT2 = 0xDC
RECORD_CHILD_COUNT = 0x1B4
RECORD_CHILDREN = 0x1B8
TREE_CHILDREN = 6
PEEP_RECORD_SIZE = 0xD8
PEEP_VALID = 0x1A
PEEP_GENDER = 0x1C
PEEP_HEAD = 0x20
PEEP_BODY = 0x24
PEEP_SLOT = 0x28                        # -1 once dead (ReportDeath)
VILLAGER_ARRAY_OFFSET = 0x1CC70
VILLAGER_STRIDE = 0x1CC0C
HOUSEHOLD_SLOTS = 30
VILLAGER_SLOT = 0x1BB48
VILLAGER_ACTIVE = 0x1BB84
VILLAGER_LEFT_HOME = 0x1BB88
VILLAGER_AGE = 0x6A54
VILLAGER_GENDER = 0x6A58
VILLAGER_NAME = 0x6A64
VILLAGER_NAME_LEN = 25
VILLAGER_HEAD = 0x6A80
VILLAGER_BODY = 0x6A84
VILLAGER_HEALTH = 0x6B00                # CVillagerState+0Ch, 0 = dead
VILLAGER_CAUSE = 0x6B04                 # CVillagerState+10h, ECauseOfDeath
VILLAGER_PREGNANT = 0x6B18              # CVillagerState+24h, nonzero while pregnant
VILLAGER_CARRIED = 0x6B1C               # CVillagerState+28h, babies expected
GAME_STATE_RESERVED_BABY = 0x25AB0      # three dwords: the slots of the babies on the way
GAME_STATE_NICKNAME = 0x25ABC           # char[20]: the player's name (the save slot's name)
GAME_STATE_NICKNAME_LEN = 20
GAME_STATE_SLOT = 0x25B20               # the current save slot (1..5), set after a successful load
LDW_PATH_VSLOT = 0x0C                   # vtable +0Ch: MakeGameStatePath(slot)
GS_LOAD_VSLOT = 0x34                    # theGameState vtable slot 13
GS_SAVE_VSLOT = 0x38                    # theGameState vtable slot 14
FOOD_OFFSET = 0x78                      # CFoodStore+78h: food (FoodStore::SaveState saves it, >= 0)
UNITS_PER_YEAR = 20                     # theVillagerScene shows age / 20 (docs/vf2-save-format.md)
PHYSIOLOGY_SPAN = 0x7E2                 # the physiology pass: the delivery lies inside its first 7E2h bytes

# The executable's own words (theStringManager::GetString ids). The prover checks each id's enum name
# and text in the executable's string table.
STRINGS = {
    "STR_MALE": (0x7B8, "eSayMale", "Male"),
    "STR_FEMALE": (0x7B9, "eSayFemale", "Female"),
    "STR_NURSING": (0xA22, "ePregnant", "Nursing"),
    "STR_CAUSE_UNKNOWN": (0x87B, "eStringCauseOfDeathUnknown", "Unknown causes"),
    "STR_CAUSE_DISEASE": (0x87C, "eStringCauseOfDeathDisease", "Disease"),
    "STR_CAUSE_STARVATION": (0x87D, "eStringCauseOfDeathStarvation", "Starvation"),
    "STR_CAUSE_OLD_AGE": (0x87E, "eStringCauseOfDeathOldAge", "Old age"),
    "STR_CAUSE_WORK": (0x87F, "eStringCauseOfDeathVocationalInjury", "Work accident"),
    "STR_CAUSE_LAST": (0x880, "eStringCauseOfDeathActOfNature", "Act of Nature"),
    "STR_NEW_GENERATION": (0x28A, "eString_NewGeneration", "New Generation"),
    "STR_COLLEGE_TITLE": (0x6F6, "eString_CollegeTitle", "{name} is going to college!"),
    "STR_BOARDING_SCHOOL": (0x4AE, "eString_BoardingSchoolShortDesc", "Boarding School"),
    "STR_BOARDING_SENT": (0x4C8, "eString_BoardingSchoolCompleted", "%s has been sent away to school!"),
    "STR_ADOPTION": (0x4C0, "eString_AdoptionShortDesc", "Adoption Services"),
    "STR_LITTLE_VISITOR": (0x900, "eEventTheLittleVisitor1Title", "The Little Visitor"),
    "STR_TALENT_SCOUT": (0x97B, "eEventTheTalentScoutTitle", "The Talent Scout"),
}
# ECauseOfDeath: -1 unknown, 0 disease, 1 starvation, 2 old age, 3 work accident, 4 act of nature; the
# string is STR_CAUSE_UNKNOWN + 1 + cause (the game's own callers: AdjustHealth(-1, 0) after IsSick,
# (-1, 1) on hunger, SetHealth(0, 2) on the old-age roll).


class Pin:
    """One exact run of the core executable.

    how:  "search"        found by searching the executable sections (must match exactly once);
          ("call", p, o)  the target of the call rel32 whose E8 byte is at offset o of pin p (then
                          byte-verified).
    skip: leading bytes that are wildcards because another companion DLL may have written its 5-byte
          jmp there (this DLL never writes them).
    """

    def __init__(self, name, va, hexbytes, how, note, skip=0):
        self.name = name
        self.va = va
        self.bytes = bytes.fromhex(hexbytes)
        self.how = how
        self.note = note
        self.skip = skip


SEARCH = "search"
KIDS_HOOKED = 5          # Up to 28 Children's entry jmp

PINS = [
    Pin("v_impregnate", 0x4BB920, (
        "558BEC515356578BF933F6B908306600E80BBFF9FF8BD885DB0F8EAD020000B9906F7000E897A20000B9906F70008945"
        "FCE88AA300008B4DFC85C9740E8B89406B000083F9557E038D71AB85C074108B80406B000083F8557E0583C6AB03F08B"
        "87FC6A00008987186B00008B45088987CC6A00008B45148987EC6A00008B45106A18FF750C8987F06A00008D87D06A00"
        "0050E889BE01006A64C7871C6B000001000000E8F89DFBFF8D4E0783C4103BC17D3183FB017E2C6A64E8E29DFBFF8D4E"
        "1983C4043BC17D1183FB027E0CC7871C6B000003000000EB0AC7871C6B000002000000E9EF010000"
    ), SEARCH, "CVillager::Impregnate(int, char const *, int head, int body, bool), head through the twin / "
               "triplet decision. this = the mother; [ebp+10h] / [ebp+14h] are the father's head and body "
               "(both callers push [father+6A80h], [father+6A84h]). Entry hook (6 bytes stolen)."),
    Pin("v_impregnate_babies", 0x4BBA72, (
        "8BF0C783B45A0200FFFFFFFF89750889B3B05A0200C783B85A0200FFFFFFFF83FEFF7421"
    ), SEARCH, "Impregnate: the first baby's slot into gs+25AB0h, the second and third reset to -1 "
               "(AddOffspring follows for each baby)."),
    Pin("v_impregnate_tail", 0x4BBBD5, (
        "8B871C6B00000105D02F6800B0015F5E5B8BE55DC21400"
    ), SEARCH, "Impregnate's success exit: GameStats babies += the babies expected (+6B1Ch); al = 1; ret 14h."),
    Pin("rm_update_all", 0x4A7CF0, (
        "56578BF9B9906F70006A00E830CF0100B9906F7000E806C701008B35E02F6800B9906F7000E876EB01003BC67E0FB990"
        "6F7000E868EB0100A3E02F68008B0FE8FCDAFCFF8B0F5F5E8981F45A0200C3"
    ), SEARCH, "theRealtimeManager::UpdateAll(): Timeflow, then the physiology pass (+15h, its only call)."),
    Pin("vm_physiology", 0x4C4410, (
        "558BEC81ECA0000000A100C6590033C58945FC5356578BF989BD74FFFFFFE8ED51FDFF33DB89857CFFFFFF8D8F643702"
        "00899D68FFFFFF898D60FFFFFF0F1F00"
    ), ("call", "rm_update_all", 0x15),
        "CVillagerManager::AllVillagersRealtimePhysiologyAndProductivityUpkeep() head: thiscall, no "
        "argument, plain ret. Every villager's state from manager+23764h (array 1CC70h + state 6AF4h)."),
    Pin("vm_birth", 0x4C4886, (
        "8981E05A02008B81B05A0200C781B05A0200FFFFFFFF83F8FF0F848700000069D80CCC01006A40C68433F487030001"
    ), SEARCH, "The delivery of the first baby: slot = gs+25AB0h, gs+25AB0h = -1, that villager active "
               "(manager + slot * 1CC0Ch + 387F4h = array 1CC70h + active 1BB84h) = 1."),
    Pin("vm_birth_end", 0x4C4A74, (
        "6AFF8D8B0C95FFFFC7432400000000E838D9FFFFC7432800000000"
    ), SEARCH, "After the delivery: the mother's pregnancy (+24h) and babies expected (+28h) written 0 "
               "(the only write of 0 to +24h in the pass)."),
    Pin("vm_timeflow", 0x4C4C30, (
        "558BEC83EC145356578BF9897DF4E8DD49FDFF8BD88DB7F4870300B80C78FCFF895DFC2BC78945F0B81E0000008945F8"
        "803E000F843C020000807E0400756583BE7CAFFEFF007F5C8BBE74AFFEFF8BCBE8AB0BFBFF8BC8B8898888882BCFF7E1"
        "C1EA058BC233D2F7B3185B02003DF0000000722D807E01007413C6460100E86D49FDFFC780C45C0200FFFFFFFF8D867C"
        "44FEFFC6060050B908306600E87F2DF9FF8B45F8803E000F84C8010000807E04000F85BE0100008BBE74AFFEFF85FF0F"
        "84B001000083BE7CAFFEFF000F8EA30100008BCBE8270BFBFF3BF8760D8BCBE81C0BFBFF898674AFFEFF8BBE74AFFEFF"
        "8BCBE8090BFBFF2BC7018670AFFEFF81BE70AFFEFF80510100760CC78670AFFEFF80510100EB52807D0800754C8B45F0"
        "8B8B185B020003C683F90574228B55F48B84106437020083F90A740583F91474073D18790000EB153DF85C0000EB0E8B"
        "4DF481BC086437020038950000760AC78670AFFEFF1879000081BB185B0200E70300007C0AC78670AFFEFF000000008B"
        "CBE87A0AFBFF8B9ED0AEFEFF8BBE70AFFEFF898674AFFEFFE85348FDFF8BC8B889888888F7E78DBED0AEFEFFC1EA058B"
        "C233D2F7B1185B02008BCF508945ECE88CF2FFFF81FB7C0100007D4D813F7C0100007C458D8E08B0FEFFE88164000085"
        "C075368DBE7C44FEFF50578BCFE8EE2900008BCFE837D6FFFF8B5DFC8BCB6AFFFF76C46A05E81659FDFF8BCBE85F5DFD"
        "FF8DBED0AEFEFFEB038B5DFCA1E82F68008B0F8D0480C1E0023BC87E16B867666666F7E9C1FA038BC2C1E81F03C2A3E8"
        "2F6800E8A847FDFF8B80185B02000FAF45EC8BD0C1E2042BD08B8670AFFEFF8BC8C1E2022BCA3BD01BC023C1898670AF"
        "FEFF8B45F881C60CCC010083E8018945F80F85A9FDFFFF5F5E5B8BE55DC20400"
    ), SEARCH, "CVillagerManager::AllVillagersTimeflowUpkeep(bool): a dead villager (health <= 0) still "
               "active is deactivated and reported (+9Ch, ReportDeath); a villager reaching age 17Ch with no "
               "career leaves for college (+1F4h, SetLeftHome); the oldest-age record [GameStats+20h]."),
    Pin("vp_death", 0x4CAD70, (
        "8D04316AFF894738FFB348BB01006A04E89BE8FCFF8BC8E8C4F9FCFF53B908306600E8B9CCF8FF80BB85BB010000740A"
        "B9906F7000E8A6BDFFFF8B834CBB010083F8FF741250B9906F7000E850B1FFFFC68084BB0100005F5EC68384BB010000"
        "5B8BE55DC20400"
    ), SEARCH, "CVillagerPlans::StartNewBehavior, the death behaviour: life event 4, ReportDeath (+22h), "
               "then the villager (and the one it carries) deactivated."),
    Pin("ad_handle_message", 0x403920, (
        "558BEC83EC20A100C6590033C58945FC837D0808578BF90F85E80100008B450C83F8010F85D201000056688A000000B9"
        "90C46F00E8D7A40800E8C25C09008B4F108945E083F9FF0F844C0100005351B9906F7000E897250C008BD86A00538BCB"
        "C68384BB010001E8843E0C008D45E78BCB506A63E8C7D30B008BB348BB0100C68385BB010001E8755C09006A1389B0C8"
        "5C02008B45E089B0C45C02008D45E88B4F6050E8C8C30700807DE80074156A198D45E8508D83646A000050E8603E0D00"
        "83C40C8D8B8C6B0000E8A2780C0083E801743E83E801741F83E801755D6863050000688A0200006A01689F0600006877"
        "0400006A03EB32680D03000068970400006A01680804000068030600006A03EB1868DA030000682C0300006A01687204"
        "000068190500006A016A016857080000B9B0407000E8A6820A00837F1C01B908306600741F53E8E5410500F20F104714"
        "83EC08B98C656800F20F110424E8BE4B0B00EB348B4754FF74873853E87F4D0B0033F63B7710741256B9906F7000E86D"
        "240C00C68084BB0100004683FE1E7CE38B4DE0E8A86E09005B6A0DB9B8F45900E81BE3FFFF6A0CB9B8F45900E80FE3FF"
        "FFB938306800E8255006008DB0B4000000E83A5B090089B0E45A0200E82F5B09005E5F8B88B85C02008988BC5C0200C7"
        "80B85C02000000000032C08B4DFC33CDE88BB00C008BE55DC2080083F8027505E83BFBFFFF8B4DFC32C033CD5FE86EB0"
        "0C008BE55DC20800"
    ), SEARCH, "CAdoptionScene::HandleMessage(int, long): Accept names the villager on show, then a new "
               "family (mode != 1) StartFamilyTree(villager) at +146h, or Next Generation (mode 1) "
               "StartNextGeneration(villager, source) through B200's generation counter at +16Ch."),
    Pin("ft_start_family_tree", 0x457C50, (
        "558BEC6AFFFF7508E8B30B06005DC20400"
    ), ("call", "ad_handle_message", 0x146),
        "CFamilyTree::StartFamilyTree(CVillager &): StartNextGeneration(villager, -1); ret 4."),
    Pin("gen_next_generation", 0x4B8810, (
        "8B4104568B359CFC5900C1EE0885F6750585C00F4FF0FF74240CFF74240CE83DF4F9FF84C075045EC208000FB6059CFC"
        "59008D4E0181FEFFFFFF000F43CEC1E1080BC1A39CFC5900B0015EC20800"
    ), ("call", "ad_handle_message", 0x16C),
        "B200's Next Generation call (thiscall tree, villager, source; ret 8): StartNextGeneration, then "
        "the lifetime generation counter."),
    Pin("ds_marry", 0x4531B6, (
        "8B868C6B00003B878C6B0000750E6A016A08B9B8F45900E82EEAFAFF660F6E43080F5BC06A0051B98C656800F30F1104"
        "24E8F45306005756B908306600E8B84B00008DBEF46A0000682C0100008BCFE866830700"
    ), SEARCH, "CDatingScene: the accepted marriage: UpdateParents(esi, edi) at +3Dh, its only call."),
    Pin("ft_update_parents", 0x457DB0, (
        "558BEC538BD956578B730485F6750CC7430401000000BE010000008B7D0857E8ACFAFFFF85C06A190F457D0C69C6C806"
        "00008DB340F9FFFF8D8F646A00005103F0807E1E00753D8D460450894508E82D8E0200C6461E018B87586A0000894620"
        "8B87846A00008946288B87806A00008946248B8748BB010089462CC74630FFFFFFFFEB508D86DC00000050894508E8ED"
        "8D0200C686F6000000018B87586A00008986F80000008B87846A00008986000100008B87806A00008986FC0000008B87"
        "48BB0100898604010000C78608010000FFFFFFFF83C40C8BCBFF7508E8CF0A06005FC60601B0015E5B5DC20800"
    ), ("call", "ds_marry", 0x3D),
        "CFamilyTree::UpdateParents(CVillager &, CVillager &): the one not yet in the tree becomes parent 1 "
        "or parent 2 (the spouse); ret 8."),
    Pin("ev_little_visitor1", 0x471910, (
        "558BEC837D080075426A3C6A006A01B9906F7000E82756050050B9906F7000E8DC45050050B908306600E8C15CFEFF6A"
        "016A0CB9B8F45900E8B302F9FF6A016A0DB9B8F45900E8A502F9FF5DC20400"
    ), SEARCH, "CEventTheLittleVisitor1::ImpactGame(int): choice A spawns a boy (age 3Ch) and AddOffspring "
               "(+2Ah)."),
    Pin("ev_little_visitor2", 0x471960, (
        "558BEC837D080075426A3C6A016A01B9906F7000E8D755050050B9906F7000E88C45050050B908306600E8715CFEFF6A"
        "016A0CB9B8F45900E86302F9FF6A016A0DB9B8F45900E85502F9FF5DC20400"
    ), SEARCH, "CEventTheLittleVisitor2::ImpactGame(int): the same with a girl."),
    Pin("ft_add_offspring", 0x457600, (
        "558BEC538BD98B430485C0747C69C0C80600008B9418F4FAFFFF8D0C1883FA067467568B750869C2D8000000578DB9F8"
        "FAFFFF6A1903F88D42018981F4FAFFFF8D86646A00005057E8E3950200C6471A0183C40C8B86586A00008BCB89471C8B"
        "86846A00008947248B86806A00008947208B8648BB010057894728E8E01206005F5EB0015B5DC2040032C05B5DC20400"
    ), ("call", "ev_little_visitor1", 0x2A),
        "CFamilyTree::AddOffspring(CVillager const &): returns al, ret 4. Up to 28 Children hooks its entry.",
        skip=KIDS_HOOKED),
    Pin("st_adoption", 0x48C85A, (
        "6A3C6AFF6A01B9906F7000E8E6A6030050B9906F7000E89B96030050B908306600E880ADFCFF6A016A0CB9B8F45900E8"
        "7253F7FF6A016A0DB9B8F45900E86453F7FFBECE040000E943010000"
    ), SEARCH, "CScrollingStoreScene::HandleUpgrade, Adoption Services: spawn a child (age 3Ch), "
               "AddOffspring (+21h), \"Adoption completed!\" (4CEh)."),
    Pin("st_boarding", 0x48CA07, (
        "8B87C45C020083F8FF0F844601000050B9906F7000E8EF9403008B8B600100008BF081C1F5FEFFFF83F9050F87E30000"
        "00FF248DF8CB48008BCEE81A5A03008D86646A00005068C8040000"
    ), SEARCH, "CScrollingStoreScene::HandleUpgrade, Boarding School: the villager in focus SetLeftHome "
               "(+3Ah), then \"%s has been sent away to school!\" (4C8h)."),
    Pin("ev_talent_scout", 0x471F40, (
        "558BEC837D0800568BF1752D8B4E046A0051E8B95805008B4E04E801050500660F6E460C0F5BC06A0151B98C656800F3"
        "0F110424E8676604005E5DC20400"
    ), SEARCH, "CEventTheTalentScout::ImpactGame(int): choice A, the chosen child SetLeftHome (+1Ah)."),
    Pin("v_set_left_home", 0x4C2460, (
        "568BF1B938306800C68688BB010001E88C66FAFF89868CBB01005EC3"
    ), ("call", "ev_talent_scout", 0x1A),
        "CVillager::SetLeftHome(): left home (+1BB88h) = 1, the game time it happened; plain ret."),
    Pin("od_evict", 0x4A68E0, (
        "568BF1B908306600E8830FFBFFB9906F7000E8D9FF0100E854D2F5FFC7401C02000000E8182DFFFF8B88B85C0200"
    ), SEARCH, "theOptionsDialog::EvictFamily(): CFamilyTree::EvictFamily (+8h), then the household is "
               "removed (CVillagerManager::Reset) and the adoption scene opens."),
    Pin("ft_evict", 0x457870, (
        "568BF1E848030000C706010000005EC3"
    ), ("call", "od_evict", 0x8), "CFamilyTree::EvictFamily(): Reset, then the evicted flag (+0) = 1."),
    Pin("mn_start_over", 0x4A42A0, (
        "8B770C81BE185B0200E70300007C0AC786185B02000A000000FFB6D05A0200FFB6CC5A0200FFB6C85A0200FFB6C45A02"
        "00FFB6C05A0200FFB6BC5A02008BCEE84C54FFFF8F86BC5A02008F86C05A02008F86C45A02008F86C85A02008F86CC5A"
        "02008F86D05A02008BCEE84168FFFF"
    ), SEARCH, "The title menu's confirmed Start Over (B200's patch_title_menu_start_over_confirms stub, "
               "reached only after Yes): the player's name kept around theGameState::Init (+3Fh), then "
               "SaveCurrentGame."),
    Pin("gs_init", 0x499730, (
        "568BF1B938306800C686CC5C020001C686BC5A020000C786D45A020000000000"
    ), ("call", "mn_start_over", 0x3F), "theGameState::Init() head: thiscall, no argument."),
    Pin("gs_ctor", 0x4993B0, (
        "558BEC6AFF68C82B4F0064A100000000505156A100C6590033C5508D45F464A3000000008BF18975F08D4E08E8BFFEFF"
        "FF8BCEE808C1FDFFC70654C54F00B9E8C0B600C786D85C020000040000C786DC5C020000030000C686E05C020000"
        "C786C05C020000000000C786B85C020002000000C745FC00000000C705E8C0B600F4010000C705ECC0B600F4010000"
        "E87E4E0300B9E8C0B600E8F4500300C786C45C0200FFFFFFFFE8A5B1FDFF83C0788BCE8986E45C0200E8C50600006A00"
        "8BCEE84C09000084C075078BCEE8D10500008BC68B4DF464890D00000000595E8BE55DC3"
    ), SEARCH, "theGameState::theGameState(): stores the vtable (+3Ah) and loads the settings file "
               "directly, Load(0) (+BFh)."),
    Pin("gs_load", 0x499DC0, (
        "558BECB8AC5B0200E823500300A100C6590033C58945FC53568B75088BD985F60F85A10000005668900000008D856CFF"
        "FFFF50E8B8BAFDFF84C00F849B050000578BFB8D83205B0200F7DF8DB56CFFFFFF68A8C54F001BFFB92400000023F86A"
        "00F3A568B0C54F00E8B3B8FDFF83C40C5F85C0741B5EC683295B020001B0015B8B4DFC33CDE8564D03008BE55DC20400"
        "68A8C54F006A0068C0C54F00E87FB8FDFF83C40C85C00F841B0500005EC683295B020000B0015B8B4DFC33CDE81F4D03"
        "008BE55DC204008D8D54A4FDFFE80EF4FFFF5668185B02008D8554A4FDFF8BCB50E80ABAFDFF84C0"
    ), SEARCH, "theGameState::Load(int slot), head: 0 = the settings file, 1..5 a family; ret 4.",
        skip=KIDS_HOOKED),
    Pin("gs_save", 0x49AA00, (
        "558BEC837D0800568BF175208BD68D86205B0200F7DA6A001BD2689000000023D052E8D9B5FDFF5E5DC204008D866801"
        "0000B9B8F4590050E8C373F6FF8D86240F0000B9A0F05D0050E8B231FBFF8D868C170000B9F0FA650050E86170FBFF8D"
        "8640180000B90830660050E890D1FBFF8D86B4E30000B91098670050E88FA4FCFF8D86C4E30000B9A898670050E89ED8"
        "FCFF8D86C8630100B9C82F680050E8DDDEFCFF8D86FC630100B93830680050E80CE0FCFF8D8610640100B9C052680050"
        "E8FB17FDFF8D86B4680100B98C65680050E82A72FEFF8D86C0680100B978E26F0050E8A94FFFFF8D86CC680100B90040"
        "700050E8980F01008D8614690100B9B040700050E8271901008D86D86F0100B9D0C0690050E866DFFEFF8D86A8720100"
        "B9906F700050E8F5BD0200FF75088D4608C786D85A0200E903000068185B0200508BCEE8B8B4FDFF5E5DC20400"
    ), SEARCH, "theGameState::Save(int slot): every component, CFoodStore (+77h) and CMoney (+CCh) among "
               "them; ret 4.", skip=KIDS_HOOKED),
    Pin("gs_get", 0x499620, (
        "558BEC6AFF68022C4F0064A1000000005051A100C6590033C5508D45F464A300000000A1885A680085C0753D68FC6102"
        "00E8EA51030083C4048945F0C745FC0000000085C0741B8BC8E842FDFFFFA3885A68008B4DF464890D00000000598BE5"
        "5DC333C0A3885A68008B4DF464890D00000000598BE55DC3"
    ), ("call", "ad_handle_message", 0x39),
        "theGameState::Get(): the singleton; its instance pointer is read, never created, by the DLL."),
    Pin("ft_report_death", 0x457A50, (
        "558BEC568BF18B460485C00F84530100005369D8C80600008B450803DE8B9048BB01008B8BF4FAFFFF39936CF9FFFF75"
        "7B85C97554388B36FAFFFF741C578DB31CFAFFFFB9360000008DBB44F9FFFFF3A5C68336FAFFFF005F833D0C3066001E"
        "0F85F50000006A00B9906F7000E85EEF060083F8FF0F85E0000000B001888342F9FFFF5B5E5DC2040080BB41F9FFFF00"
        "C7836CF9FFFFFFFFFFFF754EC68342F9FFFF01C68341F9FFFF01EB77399344FAFFFF753F85C97518388B5EF9FFFF0F84"
        "9F000000888B36FAFFFF5B5E5DC2040080BB41F9FFFF00C78344FAFFFFFFFFFFFF7507C68342F9FFFF01C68341F9FFFF"
        "01EB3033C085C97E2A33C90F1F44000039941920FBFFFF750BC7841920FBFFFFFFFFFFFF4081C1D80000003B83F4FAFF"
        "FF7CDD8BCEE846FCFFFF85C07535888341F9FFFF833D0C3066001E751E50B9906F7000E888EE060083F8FF750EB00188"
        "8342F9FFFF5B5E5DC2040032C0888342F9FFFF5B5E5DC20400"
    ), ("call", "vm_timeflow", 0x9C),
        "CFamilyTree::ReportDeath(CVillager &): the slot of the villager's tree record becomes -1; ret 4. "
        "Up to 28 Children hooks its entry.", skip=KIDS_HOOKED),
    Pin("sm_get", 0x4A87A0, (
        "558BEC6AFF689F334F0064A1000000005051A100C6590033C5508D45F464A300000000A11000700085C0753A6A24E86D"
        "60020083C4048945F0C745FC00000000"
    ), SEARCH, "theStringManager::Get() head: builds the string manager on its first call (cdecl, returns it)."),
    Pin("sm_get_string", 0x4A8940, (
        "558BEC8B4D0885C97509B8E0534F005DC204008D41FF3DF10F000077238B048D1800700085C07418390875148B480C85"
        "C974068BC15DC204008B40085DC20400B8A0EA52005DC20400"
    ), SEARCH, "theStringManager::GetString(id): static, stdcall (ret 4); the override text, else the "
               "text; a missing id returns the fixed fallback string at +41h."),
    Pin("cm_save_state", 0x481D00, (
        "558BEC56578BF9F20F1007F20F580568824F00E818CF04008B75088906F30F104708F30F5805B84D4F00F30F5905E04D"
        "4F00E8A9CE04000D0000807F8946048B470C894608B0015F5E5DC20400"
    ), SEARCH, "CMoney::SaveState: the balance is the double at CMoney+0 (saved as balance + 0.5, truncated)."),
    Pin("fs_save_state", 0x464F10, (
        "558BEC8B417833D285C00F4EC28B5508890233C038417C0F95C08942048B81800000008942080FB6818400000088420C"
        "0FB6818500000088420D0FB6818600000088420E0FB6818700000088420FB0015DC20400"
    ), SEARCH, "CFoodStore::SaveState: food is CFoodStore+78h, saved clamped to >= 0."),
]

# Function entries the DLL calls or relies on: name -> pin (the entry is the pin's first byte).
FUNCTIONS = {
    "V_IMPREGNATE": "v_impregnate",
    "VM_PHYSIOLOGY": "vm_physiology",
    "FT_START_FAMILY_TREE": "ft_start_family_tree",
    "GEN_NEXT_GENERATION": "gen_next_generation",
    "FT_UPDATE_PARENTS": "ft_update_parents",
    "FT_ADD_OFFSPRING": "ft_add_offspring",
    "V_SET_LEFT_HOME": "v_set_left_home",
    "FT_EVICT": "ft_evict",
    "GS_INIT": "gs_init",
    "GS_LOAD": "gs_load",
    "GS_SAVE": "gs_save",
    "GS_GET": "gs_get",
    "FT_REPORT_DEATH": "ft_report_death",
    "SM_GET": "sm_get",
    "SM_GET_STRING": "sm_get_string",
    "VM_BIRTH": "vm_birth",
    "VM_BIRTH_END": "vm_birth_end",
}

# Globals read from a relocated 32-bit field of a pin: name -> (pin, offset of the field).
GLOBALS = {
    "FAMILY_TREE": ("ad_handle_message", 0x13F),
    "VILLAGER_MANAGER": ("ad_handle_message", 0x50),
    "GAME_STATE_INSTANCE": ("gs_get", 0x24),
    "GS_VTABLE": ("gs_ctor", 0x3A),
    "GAME_STATS_BABIES": ("v_impregnate_tail", 0x08),
    "GAME_STATS_OLDEST": ("vm_timeflow", 0x21D),
    "MONEY": ("gs_save", 0xCC),
    "FOOD_STORE": ("gs_save", 0x77),
    "STRING_MISSING": ("sm_get_string", 0x41),
}
# Every other place the same globals appear (the prover and the DLL check each one agrees).
GLOBAL_ALSO = {
    "FAMILY_TREE": (("vm_timeflow", 0x98), ("vp_death", 0x1E), ("ds_marry", 0x39), ("ev_little_visitor1", 0x26),
                    ("ev_little_visitor2", 0x26), ("st_adoption", 0x1D), ("od_evict", 0x04),
                    ("v_impregnate", 0x0C)),
    "VILLAGER_MANAGER": (("rm_update_all", 0x05), ("rm_update_all", 0x11), ("ev_little_visitor1", 0x10),
                         ("st_adoption", 0x07), ("st_boarding", 0x11), ("od_evict", 0x0E),
                         ("v_impregnate", 0x20)),
    "MONEY": (("ds_marry", 0x28), ("ev_talent_scout", 0x2B)),
}
# Core-variant values (evidence, checked by the prover; never given to the DLL).
CORE_VALUES = {
    "FAMILY_TREE": 0x663008,
    "VILLAGER_MANAGER": 0x706F90,
    "GAME_STATE_INSTANCE": 0x685A88,
    "GS_VTABLE": 0x4FC554,
    "GAME_STATS_BABIES": 0x682FD0,
    "GAME_STATS_OLDEST": 0x682FE8,
    "MONEY": 0x68658C,
    "FOOD_STORE": 0x679810,
    "STRING_MISSING": 0x52EAA0,
}
CORE_MAKE_GAME_STATE_PATH = 0x475B40

# The calls the DLL retargets: name -> (pin, offset of the E8 byte, the function it must call).
CALL_HOOKS = {
    "CALL_PHYSIOLOGY": ("rm_update_all", 0x15, "VM_PHYSIOLOGY"),
    "CALL_DEATH_TIMEFLOW": ("vm_timeflow", 0x9C, "FT_REPORT_DEATH"),
    "CALL_DEATH_BEHAVIOR": ("vp_death", 0x22, "FT_REPORT_DEATH"),
    "CALL_COLLEGE": ("vm_timeflow", 0x1F4, "V_SET_LEFT_HOME"),
    "CALL_BOARDING_SCHOOL": ("st_boarding", 0x3A, "V_SET_LEFT_HOME"),
    "CALL_TALENT_SCOUT": ("ev_talent_scout", 0x1A, "V_SET_LEFT_HOME"),
    "CALL_MARRIAGE": ("ds_marry", 0x3D, "FT_UPDATE_PARENTS"),
    "CALL_NEW_FAMILY": ("ad_handle_message", 0x146, "FT_START_FAMILY_TREE"),
    "CALL_NEXT_GENERATION": ("ad_handle_message", 0x16C, "GEN_NEXT_GENERATION"),
    "CALL_LITTLE_VISITOR1": ("ev_little_visitor1", 0x2A, "FT_ADD_OFFSPRING"),
    "CALL_LITTLE_VISITOR2": ("ev_little_visitor2", 0x2A, "FT_ADD_OFFSPRING"),
    "CALL_ADOPTION": ("st_adoption", 0x21, "FT_ADD_OFFSPRING"),
    "CALL_EVICT": ("od_evict", 0x08, "FT_EVICT"),
    "CALL_START_OVER": ("mn_start_over", 0x3F, "GS_INIT"),
}
# Other calls the DLL relies on (checked, never written): (pin, offset, function).
CALLS = (
    ("ad_handle_message", 0x39, "GS_GET"),
    ("gs_ctor", 0xBF, "GS_LOAD"),
)
# Entry hooks: a 5-byte jmp to the DLL and a trampoline of the first `steal` bytes (whole,
# position-independent instructions) that continues at entry + steal.
ENTRY_HOOKS = {
    "V_IMPREGNATE": 6,       # push ebp / mov ebp,esp / push ecx / push ebx / push esi
}

# Address constants the DLL derives (enum order of the header): functions, globals, then call sites.
ADDRESS_CONSTANTS = tuple(FUNCTIONS) + tuple(GLOBALS) + tuple(CALL_HOOKS)
# Values that only exist for the core variant.
CORE_ONLY_CONSTANTS = ("IMAGE_BASE", "CORE_MAKE_GAME_STATE_PATH", "KIDS_HOOKED")
