"""Up to 28 Children: every site in the B200 Virtual Families 2 executable (core variant).

Single source of truth for every address the companion DLL vf2kids_b200.dll touches or relies on.
Each pin is the exact bytes of the B200 link output (`Virtual Families 2 - B200.exe`, core variant,
built by work/patch_mobile_furniture_pack.py) of one WHOLE game function (or the whole head of one,
where only the head matters), so the DLL, the prover and the tests all refuse an executable that is
not that build at these places.

The image is relocated (DYNAMICBASE + .reloc) and every matrix variant links to different
addresses, so the DLL holds no address: it searches the live image for each pinned run (relocated
32-bit fields and call/jmp rel32 displacements are wildcards), and derives every address from where
the runs were found. runtime/tools/gen_b200_kids_sites.py proves every pin and derivation on the core
variant with capstone + pefile and renders the C header the DLL is built from.

Every function here is a stock Virtual Families 2 function: each pin was located by searching the
B200 core executable for the desktop object file's own bytes (work/patched_mobile_furniture_pack_objs,
relocated fields masked), exactly one hit each. The object names are given in the notes.

Native layout the DLL relies on (all proved by the pins below, see the cross-checks in the prover):

* CFamilyTree (global FAMILY_TREE): +0 flag, +4 generation count (1-based; 0 = no family),
  +8 the first of 30 SFamilyRecord of 0x6C8 bytes. The current family is
  tree + count * 0x6C8 - 0x6C0 and is valid only when its first byte is set
  (CFamilyTree::GetCurrentFamily).
* SFamilyRecord: +0 valid, +1 "can start the next generation", +2 notify, +4 parent 1 SPeepRecord,
  +0xDC parent 2, +0x1B4 child count, +0x1B8 the child SPeepRecords, 0xD8 bytes each: exactly SIX
  fit before the next record (0x1B8 + 6 * 0xD8 = 0x6C8). A seventh would overwrite the next
  generation's record; that is why the stock AddOffspring refuses count 6.
* SPeepRecord: +0 name (25), +0x1A valid, +0x1C gender, +0x20 head, +0x24 body, +0x28 villager slot
  (-1 once dead: CFamilyTree::ReportDeath), +0x2C link to the parent's child index.
* CVillagerManager (global VILLAGER_MANAGER): +0x1CC70 the villager array, 0x1CC0C bytes each; slots
  0..29 are the household (GetVillager, FindEmptySlot, SaveState all stop at 30). A slot never moves.
* CVillager: +0x1BB48 own slot index, +0x1BB84 active, +0x1BB88 left home, +0x6A54 age (internal
  units), +0x6A58 gender, +0x6A64 name (25 bytes), +0x6A80 head, +0x6A84 body.
* theGameState: +0x25AB0/+0x25AB4/+0x25AB8 the slots reserved for the babies of the pregnancy in
  progress (FindEmptySlot skips them; the birth activates them and clears them to -1).
"""
from __future__ import annotations

IMAGE_BASE = 0x400000
B200_EXE_NAME = "Virtual Families 2 - B200.exe"

PATCHER_FOLDER = "Virtual Families 2 Patcher Files"
DLL_NAME = "vf2kids_b200.dll"
INI_NAME = "vf2kids.ini"
INI_KEY = "UpTo28Children"
STARTUP_EXPORT = "B200Kids_Startup"
# The executable's shared table (generated code reads it; the DLL writes it). Found through the PE
# section table by name.
TABLE_SECTION = ".vf2kidt"
TABLE_MAGIC = 0x544B3256                # 'V2KT'
TABLE_VERSION = 1

# The sidecar: one file per save file, beside the saves.
DATA_FOLDER = "Virtual Families 2 Patcher Data"
DATA_KIND_FOLDER = "Children"
SIDECAR_MAGIC = b"VF2KIDS\0"
SIDECAR_VERSION = 1
SIDECAR_GAME_TAG = b"VF2B200\0"

# The owner's numbers.
MAX_CHILDREN = 28                       # children per generation (2 parents + 28 = the 30 household slots)
TREE_CHILDREN = 6                       # what the stock Family Tree record holds (and shows)
MAX_EXTRA_CHILDREN = MAX_CHILDREN - TREE_CHILDREN   # 22, kept in the sidecar

# Layout constants (proved by the cross-checks in the prover).
FAMILY_RECORD_SIZE = 0x6C8
FAMILY_RECORD_BASE = 0x6C0              # current family = tree + count * 0x6C8 - 0x6C0
TREE_GENERATIONS = 30
RECORD_CHILD_COUNT = 0x1B4
RECORD_CHILDREN = 0x1B8
PEEP_RECORD_SIZE = 0xD8
PEEP_VALID = 0x1A
PEEP_GENDER = 0x1C
PEEP_SLOT = 0x28
RECORD_PARENT1 = 0x04
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
GAME_STATE_RESERVED_BABY = 0x25AB0      # three dwords
ADOPTION_MODE = 0x1C                    # 1 = Next Generation
ADOPTION_CANDIDATE = 0x10               # the villager slot on show
ADOPTION_CLONES = 0x20                  # six dwords: clone slots
ADOPTION_SOURCES = 0x38                 # six dwords: the child slot each clone was made from
ADOPTION_COUNT = 0x50
ADOPTION_CURSOR = 0x54
LDW_PATH_VSLOT = 0x0C                   # ldwGameState vtable +0Ch: the save file path for a slot
SAVE_BACKUP_OFFSET = 0x14               # ldwGameState::Save keeps the previous save at slot + 20


class Pin:
    """One exact run of the core executable.

    how: "search"        found by searching the executable sections (must match exactly once);
         ("call", p, o)  the target of the call rel32 whose E8 byte is at offset o of pin p (then
                         byte-verified).
    The bytes are the core variant's; relocated 32-bit fields and call/jmp rel32 displacements are
    wildcards in other variants.
    """

    def __init__(self, name, va, hexbytes, how, note):
        self.name = name
        self.va = va
        self.bytes = bytes.fromhex(hexbytes)
        self.how = how
        self.note = note


SEARCH = "search"

PINS = [
    Pin("ft_add_offspring", 0x457600, (
        "558BEC538BD98B430485C0747C69C0C80600008B9418F4FAFFFF8D0C1883FA067467568B750869C2D8000000578DB9F8"
        "FAFFFF6A1903F88D42018981F4FAFFFF8D86646A00005057E8E3950200C6471A0183C40C8B86586A00008BCB89471C8B"
        "86846A00008947248B86806A00008947208B8648BB010057894728E8E01206005F5EB0015B5DC2040032C05B5DC20400"
    ), SEARCH, "CFamilyTree::AddOffspring(CVillager const &), FamilyTree.obj. Refuses count 6 (cmp edx,6)."),
    Pin("ft_change_name", 0x457700, (
        "558BEC51538B5D0856538BF1E86F01000085C00F849A0000006A19FF750C50E80C9502008B460483C40C83F8010F8E80"
        "00000069C0C80600005733FF8B8C302CF4FFFF894D0885C97E688D8B646A000081C630F4FFFF8B5D0803F0894DFC6690"
        "8BC18BCE8A113A10751A84D274128A51013A5001750E83C10283C00284D275E433C0EB051BC083C80185C074178B4DFC"
        "4781C6D80000003BFB7CC55F5E5B8BE55DC208006A19FF750C56E88194020083C40C5F5E5B8BE55DC20800"
    ), SEARCH, "CFamilyTree::ChangeName(CVillager &, char const *): the rename the Details screen makes."),
    Pin("ft_count_surviving", 0x4577C0, (
        "558BEC518B4104565785C0745F69F8C806000033F603F980BF40F9FFFF00744C5333DB399FF4FAFFFF7E388D8720FBFF"
        "FF8945FCFF30B9906F7000E810E706008D4E0180B884BB0100008B45FC0F44CE4305D80000008BF18945FC3B9FF4FAFF"
        "FF7CD15B5F8BC65E8BE55DC35F33C05E8BE55DC3"
    ), SEARCH, "CFamilyTree::CountSurvivingChildren(): recorded children whose villager is active."),
    Pin("ft_empty_offspring", 0x457840, (
        "8BD18B420485C07506B806000000C369C8C8060000B8060000002B8411F4FAFFFFC3"
    ), SEARCH, "CFamilyTree::EmptyOffspringSlots(): 6 - count. Every birth path asks it first."),
    Pin("ft_get_current_family", 0x457910, (
        "8B410485C0741269C0C80600000540F9FFFF03C1803800750233C0C3"
    ), SEARCH, "CFamilyTree::GetCurrentFamily(): proves the current-record arithmetic."),
    Pin("ft_report_death", 0x457A50, (
        "558BEC568BF18B460485C00F84530100005369D8C80600008B450803DE8B9048BB01008B8BF4FAFFFF39936CF9FFFF75"
        "7B85C97554388B36FAFFFF741C578DB31CFAFFFFB9360000008DBB44F9FFFFF3A5C68336FAFFFF005F833D0C3066001E"
        "0F85F50000006A00B9906F7000E85EEF060083F8FF0F85E0000000B001888342F9FFFF5B5E5DC2040080BB41F9FFFF00"
        "C7836CF9FFFFFFFFFFFF754EC68342F9FFFF01C68341F9FFFF01EB77399344FAFFFF753F85C97518388B5EF9FFFF0F84"
        "9F000000888B36FAFFFF5B5E5DC2040080BB41F9FFFF00C78344FAFFFFFFFFFFFF7507C68342F9FFFF01C68341F9FFFF"
        "01EB3033C085C97E2A33C90F1F44000039941920FBFFFF750BC7841920FBFFFFFFFFFFFF4081C1D80000003B83F4FAFF"
        "FF7CDD8BCEE846FCFFFF85C07535888341F9FFFF833D0C3066001E751E50B9906F7000E888EE060083F8FF750EB00188"
        "8342F9FFFF5B5E5DC2040032C0888342F9FFFF5B5E5DC20400"
    ), SEARCH, "CFamilyTree::ReportDeath(CVillager &): both death paths call it; it recounts survivors."),
    Pin("ft_reset", 0x457BC0, (
        "568BF16870CB00006A008D460850E84D8A070083C40CC7460400000000C706000000005EC3"
    ), SEARCH, "CFamilyTree::Reset(): LoadState, EvictFamily and the constructor."),
    Pin("ft_start_next_gen", 0x457C70, (
        "558BEC83EC08538BD9895DF88B430483F81E7508E837FDFFFF8B430483F81D0F87BB00000056578BCBE8C20000008B55"
        "0CC745FCFFFFFFFF83FAFF7434694304C806000033C98BB418F4FAFFFF85F67E200520FBFFFF03C38078F20074043910"
        "740C4105D80000003BCE7CECEB03894DFCFF4304694304C806000081C340F9FFFF8B75086A1903D88D86646A0000508D"
        "7B0457E8288F02008B4DF883C40CC6431E018B86586A00008943208B86846A00008943288B86806A00008943248B8648"
        "BB010089432C8B45FC57894330C60301E81B0C06005F5EB0015B8BE55DC2080032C05B8BE55DC20800"
    ), SEARCH, "CFamilyTree::StartNextGeneration(CVillager &, int): StartFamilyTree and the heir's accept."),
    Pin("ad_activate", 0x403420, (
        "558BEC807D0800568BF17459837E1C01C74610FFFFFFFF752CB908306600E87D43050083F8017E0AFF76588BCEE81EB8"
        "07008BCEE8470000008BCEE8000200005E5DC20400B9906F7000E8612E0C00FF76588BCEE8F7B707008BCEE8E0010000"
        "5E5DC20400FF7658E843B907005E5DC20400"
    ), SEARCH, "CAdoptionScene::Activate(bool): Next Generation mode counts survivors, builds candidates."),
    Pin("ad_create_candidates", 0x4034A0, (
        "558BEC83EC08568BF1B908306600C7465000000000C74654FFFFFFFFE84F4405008945F885C00F84A20000008B88B401"
        "000085C90F84940000005333DB5785C97E5B05E00100008945FC660F1F4400008B0883F9FF743251B9906F7000E80E2A"
        "0C008BF8B9906F700057E8A11C0C008B4E5089448E208B4E508B8748BB010089448E38FF46508B45FC8B4DF84305D800"
        "00008945FC3B99B40100007CB333FF397E507E288D5E20660F1F840000000000FF33B9906F7000E8B4290C00478D5B04"
        "C68084BB0100003B7E507CE45F5B5E8BE55DC3"
    ), SEARCH, "CAdoptionScene::CreateNextGenerationCandidates(): clones every recorded child as an adult."),
    Pin("ad_generate", 0x403660, (
        "558BEC81EC08010000A100C6590033C58945FC5356578BF9837F1C01C6470801744D8B471083F8FF741250B9906F7000"
        "E87B280C00C68084BB0100006A02E81D2107006A068BF0E81421070083C01883C4088D0C8033C0C1E10285F6510F94C0"
        "B9906F7000506AFFE883380C00EB05E82C02000050B9906F7000894710E82E280C008BD88D8B646A0000518B4F60E80D"
        "CC0700E8A8500A008BF0B867666666F7AB546A00008D85FCFEFFFF89B5F8FEFFFFC1FA038BCAC1E91F03CA516894484F"
        "0050E879E9FFFF8B4F648D85FCFEFFFF83C40C50E8C7CB070033C08BCE3983586A00000F95C005B807000050E8EF510A"
        "008B4F6850E8A6CB0700C685FCFEFFFF008D8B8C6B00008BB3906B0000E81E7C0C0050B998484F0083FE01B8A4484F00"
        "0F4CC1508D85FCFEFFFF50E810E9FFFF8B4F6C8D85FCFEFFFF83C40C50E85ECB0700837F1C00752168F0000000E80E20"
        "070083C4040596000000660F6EC0F30FE6C0F20F114714EB17B98C656800E8ADE50700F20F10058C656800F20F114714"
        "8B83986B00008D344003F6E840B40C008B8DF8FEFFFF50566A76E841510A00508D85FCFEFFFF50E894E8FFFF8B4F708D"
        "85FCFEFFFF83C41050E8E2CA07008D8BF46A0000E8878E0C008B4F7450E8CECA07008D8B34BC0100E8A3DC07008B4F78"
        "50E8BACA07008D8B40BC0100E8CF2105008B4F7C50E8A6CA07008B4DFC5F5EC68384BB01000033CD5BE832B30C008BE5"
        "5DC3"
    ), SEARCH, "CAdoptionScene::GeneratePeepCandidate(): mode 1 shows GetNextCandidate()'s villager, inactive."),
    Pin("ad_get_next", 0x403900, (
        "834154018B415478053B41507C09C741540000000033C08B448120C3"
    ), SEARCH, "CAdoptionScene::GetNextCandidate(): cycles the six-dword clone array by +50h."),
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
    ), SEARCH, "CAdoptionScene::HandleMessage(int, long): Accept makes [+10h] the heir with source [+54h]."),
    Pin("vm_find_empty", 0x4C5B40, (
        "568BF1E8D83AFDFF8BC833C081C6F4870300803E0075183B81B05A020074103B81B45A020074083B81B85A0200750C40"
        "81C60CCC010083F81E7CD783C9FF83F81E5E0F4DC1C3"
    ), SEARCH, "CVillagerManager::FindEmptySlot(): the first inactive household slot not reserved for a baby."),
    Pin("vm_get_villager", 0x4C5F10, (
        "558BEC8B450885C0781683F81E7D1669C00CCC01000570CC010003C15DC2040083F81E7C0583F8257CE58D41645DC204"
        "00"
    ), SEARCH, "CVillagerManager::GetVillager(int)."),
    Pin("vm_clone_peep", 0x4C51B0, (
        "558BEC56578BF9E8840900008BF085F67818FF750869C60CCC01008D8F70CC010003C8E8985FFFFF8BC65F5E5DC20400"
    ), ("call", "ad_create_candidates", 0x6A),
        "CVillagerManager::ClonePeepAsAdult(CVillager &): FindEmptySlot then CloneAsAdult. Another function "
        "has the same bytes, so it is found as the call target in CreateNextGenerationCandidates."),
    Pin("v_clone_as_adult", 0x4BB170, (
        "558BEC5356578BF9E8536D00008BCFE85C0F00006A4EC68784BB010001E82EA6FBFF05A90100006A42898754BB0100E8"
        "1CA6FBFF83C408C7875CBB01007D0000000578050000C78760BB01007D0000008D8F8C6B0000898758BB0100C78764BB"
        "010000000000C78768BB010000000000E82B0201008B4D08F30F7E8134BC0100660FD68734BC01008B813CBC01008987"
        "3CBC0100F30F7E8140BC0100660FD68740BC01008B8148BC0100898748BC01008D81546A0000508D8F546A0000E82E8E"
        "00006A05E887A5FBFF83C0178D8FF46A000083C4048D0480C1E002508987546A0000E8C90601008D8F9C6B0000C78770"
        "BB010000000000E8048AF4FF6A64E84DA5FBFF83C40433D283F832B9020000000F4ECA516A028BCFE843E700006A64E8"
        "2CA5FBFF83C40483F8087D158D8F8C6B0000C787906B000001000000E8BF010100C7879CBB0100FFFFFFFF5F5E5B5DC2"
        "0400"
    ), ("call", "vm_clone_peep", 0x23),
        "CVillager::CloneAsAdult(CVillager &): Reset(this) first, then copies from the argument; it never "
        "writes the slot index +1BB48h. The argument must not be this villager."),
    Pin("v_impregnate", 0x4BB920, (
        "558BEC515356578BF933F6B908306600E80BBFF9FF8BD885DB0F8EAD020000B9906F7000E897A20000B9906F70008945"
        "FCE88AA300008B4DFC85C9740E8B89406B000083F9557E038D71AB85C074108B80406B000083F8557E0583C6AB03F08B"
        "87FC6A00008987186B00008B45088987CC6A00008B45148987EC6A00008B45106A18FF750C8987F06A00008D87D06A00"
        "0050E889BE01006A64C7871C6B000001000000E8F89DFBFF8D4E0783C4103BC17D3183FB017E2C6A64E8E29DFBFF8D4E"
        "1983C4043BC17D1183FB027E0CC7871C6B000003000000EB0AC7871C6B000002000000E9EF010000"
    ), SEARCH,
        "CVillager::Impregnate (B200, head through the twin/triplet decision). ebx = EmptyOffspringSlots(); "
        "none = no pregnancy; twins need ebx > 1, triplets ebx > 2; B200's forced-count cheat (the jmp) "
        "clamps to ebx too. Not written: it proves the birth count is clamped by EmptyOffspringSlots alone."),
    Pin("gs_save", 0x49AA00, (
        "558BEC837D0800568BF175208BD68D86205B0200F7DA6A001BD2689000000023D052E8D9B5FDFF5E5DC204008D866801"
        "0000B9B8F4590050E8C373F6FF8D86240F0000B9A0F05D0050E8B231FBFF8D868C170000B9F0FA650050E86170FBFF8D"
        "8640180000B90830660050E890D1FBFF8D86B4E30000B91098670050E88FA4FCFF8D86C4E30000B9A898670050E89ED8"
        "FCFF8D86C8630100B9C82F680050E8DDDEFCFF8D86FC630100B93830680050E80CE0FCFF8D8610640100B9C052680050"
        "E8FB17FDFF8D86B4680100B98C65680050E82A72FEFF8D86C0680100B978E26F0050E8A94FFFFF8D86CC680100B90040"
        "700050E8980F01008D8614690100B9B040700050E8271901008D86D86F0100B9D0C0690050E866DFFEFF8D86A8720100"
        "B9906F700050E8F5BD0200FF75088D4608C786D85A0200E903000068185B0200508BCEE8B8B4FDFF5E5DC20400"
    ), SEARCH, "theGameState::Save(int slot): slot 0 is the 90h-byte settings file; 1..5 write the family."),
    Pin("gs_load", 0x499DC0, (
        "558BECB8AC5B0200E823500300A100C6590033C58945FC53568B75088BD985F60F85A10000005668900000008D856CFF"
        "FFFF50E8B8BAFDFF84C00F849B050000578BFB8D83205B0200F7DF8DB56CFFFFFF68A8C54F001BFFB92400000023F86A"
        "00F3A568B0C54F00E8B3B8FDFF83C40C5F85C0741B5EC683295B020001B0015B8B4DFC33CDE8564D03008BE55DC20400"
        "68A8C54F006A0068C0C54F00E87FB8FDFF83C40C85C00F841B0500005EC683295B020000B0015B8B4DFC33CDE81F4D03"
        "008BE55DC204008D8D54A4FDFFE80EF4FFFF5668185B02008D8554A4FDFF8BCB50E80ABAFDFF84C0"
    ), SEARCH, "theGameState::Load(int slot), head: slot 0 is the settings file, 1..5 read the family."),
    Pin("ldw_save", 0x476000, (
        "558BEC81EC08020000A100C6590033C58945FC8B4508538B5D108985F8FDFFFF56578BF985DB7E3E8D731456E8AFFFFF"
        "FF8B078BCF68FD01000056FF500C508D85FCFDFFFF50E8F517060083C40C8D85FCFDFFFF8BCF508B0753FF500C50E814"
        "7D060083C4088B078BCF68F4494F0053FF500C50E8001B06008BF083C40885F675155F5E32C05B8B4DFC33CDE80F8B05"
        "008BE55DC20C008B7D0C566A016A1068183C5700893D243C5700E8B220060083C41083F8010F94C37518566A0157FFB5"
        "F8FDFFFFE89820060083C41083F8010F94C356E8B41906008B4DFC83C4048AC333CD5F5E5BE8B68A05008BE55DC20C00"
    ), SEARCH,
        "ldwGameState::Save(void *, unsigned, int slot): for slot > 0 it removes slot + 14h, renames the "
        "previous save to slot + 14h, and writes; every path is the virtual +0Ch (MakeGameStatePath)."),
    Pin("gs_get", 0x499620, (
        "558BEC6AFF68022C4F0064A1000000005051A100C6590033C5508D45F464A300000000A1885A680085C0753D68FC6102"
        "00E8EA51030083C4048945F0C745FC0000000085C0741B8BC8E842FDFFFFA3885A68008B4DF464890D00000000598BE5"
        "5DC333C0A3885A68008B4DF464890D00000000598BE55DC3"
    ), ("call", "ad_handle_message", 0x39),
        "theGameState::Get(): the singleton; its instance pointer is read, never created, by the DLL."),
    Pin("ldw_make_path", 0x475B40, (
        "558BEC81EC04010000A100C6590033C58945FC8B01FF7508FF5014508D85FCFEFFFF681C824F0050E833C5F8FF8D85FC"
        "FEFFFF6A0050E8750100008B4DFC83C41833CDE8189005008BE55DC20400"
    ), SEARCH, "ldwGameState::MakeGameStatePath(int): MakePath(sprintf(\"%s%d.ldw\", GetGameName(), slot))."),
]

# Function entries the DLL calls or hooks: name -> pin (the entry is the pin's first byte).
FUNCTIONS = {
    "FT_ADD_OFFSPRING": "ft_add_offspring",
    "FT_CHANGE_NAME": "ft_change_name",
    "FT_COUNT_SURVIVING": "ft_count_surviving",
    "FT_EMPTY_OFFSPRING": "ft_empty_offspring",
    "FT_REPORT_DEATH": "ft_report_death",
    "FT_RESET": "ft_reset",
    "FT_START_NEXT_GEN": "ft_start_next_gen",
    "AD_CREATE_CANDIDATES": "ad_create_candidates",
    "AD_GET_NEXT": "ad_get_next",
    "VM_FIND_EMPTY": "vm_find_empty",
    "VM_GET_VILLAGER": "vm_get_villager",
    "VM_CLONE_PEEP": "vm_clone_peep",
    "V_CLONE_AS_ADULT": "v_clone_as_adult",
    "GS_SAVE": "gs_save",
    "GS_LOAD": "gs_load",
    "GS_GET": "gs_get",
}

# Globals read from a relocated 32-bit field of a pin: name -> (pin, offset of the field).
GLOBALS = {
    "FAMILY_TREE": ("ad_create_candidates", 0x0A),       # mov ecx, offset FamilyTree
    "VILLAGER_MANAGER": ("ad_create_candidates", 0x59),  # mov ecx, offset VillagerManager
    "GAME_STATE_INSTANCE": ("gs_get", 0x24),             # mov eax, theGameState's instance pointer
}
# Every other place the same globals appear (the prover checks each one agrees).
GLOBAL_ALSO = {
    "FAMILY_TREE": (("ad_activate", 0x1A), ("v_impregnate", 0x0C), ("gs_save", 0x66),
                    ("ad_handle_message", 0x13F)),
    "VILLAGER_MANAGER": (("ft_count_surviving", 0x37), ("ad_create_candidates", 0x65),
                         ("ad_create_candidates", 0xB3), ("ad_handle_message", 0x50),
                         ("v_impregnate", 0x20)),
}
# Core-variant values (evidence, checked by the prover; never given to the DLL).
FAMILY_TREE = 0x663008
VILLAGER_MANAGER = 0x706F90
GAME_STATE_GET = 0x499620
GAME_STATE_INSTANCE = 0x685A88

# Calls the DLL relies on: (pin, offset of the E8 byte, the function it must call).
CALLS = (
    ("ft_count_surviving", 0x3B, "VM_GET_VILLAGER"),
    ("ft_report_death", 0x125, "FT_COUNT_SURVIVING"),
    ("ft_change_name", 0x0C, None),                      # FindPeepRecord (private, not used)
    ("ad_activate", 0x1E, "FT_COUNT_SURVIVING"),
    ("ad_activate", 0x34, "AD_CREATE_CANDIDATES"),
    ("ad_create_candidates", 0x5D, "VM_GET_VILLAGER"),
    ("ad_create_candidates", 0x6A, "VM_CLONE_PEEP"),
    ("ad_generate", 0x6F, "AD_GET_NEXT"),
    ("ad_generate", 0x7D, "VM_GET_VILLAGER"),
    ("ad_handle_message", 0x54, "VM_GET_VILLAGER"),
    ("vm_clone_peep", 0x07, "VM_FIND_EMPTY"),
    ("vm_clone_peep", 0x23, "V_CLONE_AS_ADULT"),
    ("v_impregnate", 0x10, "FT_EMPTY_OFFSPRING"),
    ("ft_start_next_gen", 0x14, None),                   # MakeRoomInTree
    ("ad_handle_message", 0x39, "GS_GET"),
)

# Entry hooks. "wrap": a 5-byte jmp to the DLL and a trampoline of the first `steal` bytes (whole,
# position-independent instructions) that continues at entry + steal. "replace": a 5-byte jmp, no
# trampoline needed by the replacement; a trampoline is still built where the DLL hands the call back
# to the stock function (stock behaviour with no extra child).
HOOKS = {
    "FT_ADD_OFFSPRING": ("wrap", 6),        # push ebp / mov ebp,esp / push ebx / mov ebx,ecx
    "FT_CHANGE_NAME": ("wrap", 8),          # push ebp / mov ebp,esp / push ecx / push ebx / mov ebx,[ebp+8]
    "FT_COUNT_SURVIVING": ("wrap", 7),      # push ebp / mov ebp,esp / push ecx / mov eax,[ecx+4]
    "FT_EMPTY_OFFSPRING": ("replace", 7),   # mov edx,ecx / mov eax,[edx+4] / test eax,eax
    "FT_REPORT_DEATH": ("wrap", 6),         # push ebp / mov ebp,esp / push esi / mov esi,ecx
    "FT_RESET": ("wrap", 8),                # push esi / mov esi,ecx / push 0CB70h
    "FT_START_NEXT_GEN": ("wrap", 6),       # push ebp / mov ebp,esp / sub esp,8
    "AD_CREATE_CANDIDATES": ("wrap", 7),    # push ebp / mov ebp,esp / sub esp,8 / push esi
    "AD_GET_NEXT": ("wrap", 7),             # add dword [ecx+54h],1 / mov eax,[ecx+54h]
    "GS_SAVE": ("wrap", 7),                 # push ebp / mov ebp,esp / cmp dword [ebp+8],0
    "GS_LOAD": ("wrap", 8),                 # push ebp / mov ebp,esp / mov eax,25BACh
}

# The same layout in the retail game. The B200 executable is relinked from the desktop object files,
# which were compiled separately from the retail "Virtual Families 2.exe", so the retail code is not the
# same bytes; these runs of the retail executable (not relocated: exact bytes at fixed addresses) prove
# the record sizes, the six-child cap, the save block and the twin / triplet rule the DLL relies on
# are the retail game's own. (VA, exact bytes, operands that must appear, note)
VANILLA_EXE_SHA256 = "1582d9e84e1c32f51475be17335c5137c592cebf809748d401ccef99a32b73c3"
VANILLA_EVIDENCE = (
    (0x48FEC0, "8B510485D2B806000000740D69D2C80600002B840AF4FAFFFFC3", (6, 0x6C8, -0x50C),
     "CFamilyTree::EmptyOffspringSlots: 6 when there is no family, else 6 - [tree + count * 6C8h - 50Ch]"),
    (0x490370, "69C0C80600008B8C18F4FAFFFF83F9068D841840F9FFFF74E18BD169D2D8000000", (0x6C8, -0x50C, 6, -0x6C0, 0xD8),
     "CFamilyTree::AddOffspring: refuses child count 6; child records are D8h"),
    (0x48FF10, "8B410485C0741769C0C806000080BC0840F9FFFF008D840840F9FFFF750233C0C3", (0x6C8, -0x6C0),
     "CFamilyTree::GetCurrentFamily: tree + count * 6C8h - 6C0h, valid only if its first byte is set"),
    (0x495360, (
        "5355568BF1B9C8CF5A0033DBE84FABFFFF8BE885ED0F8EB102000057B9589F5B00E8BA390000B9589F5B008BF8E81E3A0000"
        "85FF740E8BBF406B000083FF557E038D5FAB85C0740F8B80406B000083F8557E048D5C03AB8B86FC6A00008B4C24148B5424"
        "208986186B00008B44241C898ECC6A00008B4C24186A188986F06A00008D86D06A000051508996EC6A0000E8ACFF02006A64"
        "C7861C6B000001000000E86BEBF6FF8D530783C4103BC27D3183FD017E2C6A64E855EBF6FF83C31983C4043BC37D1183FD02"
        "7E0CC7861C6B000003000000EB0AC7861C6B000002000000"), (1, 2, 3, 7, 0x19, 0x6B1C, 0x55),
     "CVillager::Impregnate: ebp = EmptyOffspringSlots() first (none = no pregnancy); twins only when it is "
     "> 1, triplets only when it is > 2; the chances are GetRandom(100) < 7 + bonus and < 25 + bonus"),
    (0x498EF4, "81C7BC07000081C60CCC010081FF08E80000", (0x7BC, 0x1CC0C, 0xE808),
     "CVillagerManager::SaveState: 30 villager records of 7BCh (E808h), every household slot is saved"),
    (0x42956D, "8D864018000050B9C8CF5A00E8A26C06008D8EB4E30000", (0x1840, 0xE3B4),
     "theGameState::Save: the Family Tree block is +1840h, and the next component starts at +E3B4h: "
     "4 + 30 * 6C8h bytes, no room for a seventh child anywhere"),
)
VANILLA_EMPTY_OFFSPRING = 0x48FEC0
VANILLA_IMPREGNATE_EMPTY_CALL = 0x49536C

# Address constants the DLL derives (enum order of the header).
ADDRESS_CONSTANTS = tuple(FUNCTIONS) + tuple(GLOBALS)
# Values that only exist for the core variant.
CORE_ONLY_CONSTANTS = ("IMAGE_BASE", "FAMILY_TREE", "VILLAGER_MANAGER", "GAME_STATE_GET",
                       "GAME_STATE_INSTANCE", "VANILLA_EMPTY_OFFSPRING", "VANILLA_IMPREGNATE_EMPTY_CALL")
