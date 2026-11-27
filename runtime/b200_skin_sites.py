"""Skin Tones: every site in the B209 Virtual Families 2 executable (core variant) the companion DLL relies on.

Single source of truth for every address vf2skin_b200.dll (runtime/native/b200skin) touches or reads. Each pin is
the exact bytes of the B209 core variant (`Virtual Families 2 - B209.exe`, built by
work/patch_mobile_furniture_pack.py) of one game function, or of the run of a function around a call the DLL
retargets. The image is relocated (DYNAMICBASE + .reloc) and the 32 matrix variants link to different addresses,
so the DLL holds no address: it searches the live image for each pinned run (relocated 32-bit fields and call/jmp
rel32 displacements are wildcards) and derives every address from where the runs were found.
runtime/tools/gen_b200_skin_sites.py proves every pin and derivation on the core variant with capstone + pefile,
resolves every other executable it is given (the 32 B209 matrix variants) and renders the C header.

The executable's own loader (the dormant .vf2skin byte, B210 on) loads the DLL right after the Family History DLL, so
every companion loaded before it has written its hooks already:

* Up to 28 Children writes a 5-byte jmp at the entry of CFamilyTree::ChangeName and theGameState::Save / Load:
  those pins mark their first five bytes as wildcards (`skip`), and this DLL never writes them.
* Family History writes a 5-byte jmp at the entry of CVillager::Impregnate (`skip` here too) and retargets the two
  theVillagerScene ChangeName calls; Time Controls, Family History and Up to 28 Children chain theGameState's Load
  and Save vtable slots. This DLL chains each of those: a retargeted call or a vtable slot may hold the stock
  function or another companion's handler (an address outside the executable), never anything else.

The DLLs loaded after it by the executable's loader (Store Refresh, Outfit Pictures, Title Box, Unicode Text,
Translations) must still resolve with this DLL's writes in place: tests/test_b200_skin_tones.py runs each of their
resolvers on an image with every write of this DLL applied.

How each person draw is seen (every caller traced in the core executable):

* the house and the menu's family: CVillagerManager::DrawVillager(slot, alpha), its only caller CSceneManager::
  EndScene; entry hook (6 bytes stolen). The person is the slot argument.
* the held baby: the two calls of CVillagerManager::DrawCarriedItems inside DrawVillager; the babies a mother
  holds are carrying.png cell 3, drawn once for each baby she carries (+6B1Ch).
* Details, Adoption, the marriage proposal (the big head and big body): CVillager::DrawDetailVillager, entry
  hook; its three callers (CAdoptionScene, CDatingScene, theVillagerScene ::DrawScene) pass a household villager
  (CVillagerManager::GetVillager(slot)).
* an event pop-up's portrait and the main screen's portrait: CVillager::DrawEventVillager, entry hook
  (CIslandEventDialog::DrawNoFadeScene, theMainScene::DrawUI).
* the Family Tree: CFamilyTreeScene::DrawParent and DrawChild, entry hooks; the person is told by the return
  address: DrawFamily's two DrawParent calls (the generation's record in ebx, parent 1 at +4, parent 2 at +DCh)
  and its DrawChild call (the record at [ebp+10h], the child at +1B8h + edi). Any other caller (Revive's
  revived family members, drawn under the current spouse) is matched by sex, head and body against
  B200Revive_Members.
* every one of those ends in ldwGameWindowImpl::BlitRectWithAlpha (entry hook, 9 bytes stolen) through
  ldwGameWindow::DrawScaled / CSceneManager::DrawScaled; the Holiday outfits (bodies 50 to 53) are drawn by the
  patcher's generated body helpers (VF2DrawSceneVillagerBodyFrame from DrawVillager, VF2DrawVillagerBodyFrame from
  the portraits) from their own one-cell pictures: their image ids are read from the helpers' own tables.
* conception: theMainScene's try-for-a-baby call of CVillager::Impregnate and CVillagerPlans::ProcessCurrentPlan's
  (through a jmp thunk in some variants): both retargeted; after the call the babies wait hidden in the reserved
  slots (theGameState +25AB0h, three dwords).
* renames: theVillagerScene's two ChangeName calls (the entry follows the name).
* load and save: theGameState's vtable slots 13 and 14.
"""
from __future__ import annotations

IMAGE_BASE = 0x400000
B209_EXE_NAME = "Virtual Families 2 - B209.exe"

PATCHER_FOLDER = "Virtual Families 2 Patcher Files"
DLL_NAME = "vf2skin_b200.dll"
INI_NAME = "vf2skin.ini"
INI_KEY = "SkinTones"
STARTUP_EXPORT = "B200Skin_Startup"
STATUS_EXPORT = "B200Skin_Status"
STATUS_MAGIC = 0x4E4B5332                # '2SKN'
MASK_FOLDER = "Skin Masks"               # beside the DLL
DATA_FOLDER = "Virtual Families 2 Patcher Data"
TONES_FOLDER = "Skin Tones"              # <save folder>\<DATA_FOLDER>\<TONES_FOLDER>\<save file>.dat

# Layout constants (each proved by an operand of the pinned code, see the prover's cross-checks).
TREE_GENERATIONS_FIELD = 0x04            # CFamilyTree+4: records in use (1-based; 0 = no family)
FAMILY_RECORD_SIZE = 0x6C8
FAMILY_RECORD_BASE = 0x6C0               # record of generation g = tree + g * 0x6C8 - 0x6C0
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
PEEP_SLOT = 0x28                         # -1 once dead
VILLAGER_ARRAY_OFFSET = 0x1CC70
VILLAGER_STRIDE = 0x1CC0C
HOUSEHOLD_SLOTS = 30
VILLAGER_ACTIVE = 0x1BB84
VILLAGER_AGE = 0x6A54
VILLAGER_GENDER = 0x6A58
VILLAGER_NAME = 0x6A64
VILLAGER_NAME_LEN = 25
VILLAGER_HEAD = 0x6A80
VILLAGER_BODY = 0x6A84
VILLAGER_HEALTH = 0x6B00
VILLAGER_PREGNANT = 0x6B18               # nonzero while she carries the babies (VF2 mothers hold them at once)
VILLAGER_CARRIED = 0x6B1C                # babies she carries (1..3)
GAME_STATE_RESERVED_BABY = 0x25AB0       # three dwords: the slots of the babies she carries
SAVE_BACKUP_OFFSET = 0x14                # ldwGameState::Save keeps the previous save at slot + 20
LDW_PATH_VSLOT = 0x0C                    # theGameState vtable +0Ch: MakeGameStatePath(slot)
GS_LOAD_VSLOT = 0x34                     # vtable slot 13
GS_SAVE_VSLOT = 0x38                     # vtable slot 14
IMAGE_ENTRY_SIZE = 0x30                  # theGraphicsManager's image table: one entry per image
IMAGE_ENTRY_ID = 0x00
IMAGE_ENTRY_GRID = 0x2C                  # the ldwImageGrid GetImageGrid made (0 until then)
GRID_HOLDER = 0x04                       # a one-file grid: its ldwImageImpl (whose +0 is the SDL surface)
GRID_CELL_HEIGHT = 0x14
GRID_TILES = 0x30                        # a grid of several files: their ldwImageImpl, row by row (0 for one file)
GRID_TILES_ACROSS = 0x20
CARRYING_IMAGE = 0x1DE                   # carrying.png
BABY_CELL = 3                            # DrawCarriedItems draws cell 3 once for each baby she carries
HOLIDAY_FIRST_BODY = 50
HOLIDAY_BODIES = 4
HOLIDAY_FRAMES = 448                     # 2 sexes x 4 bodies x (32 walking + 15 actions + 9 sitting)
HOLIDAY_FRAMES_PER_BODY = 56
HOLIDAY_ROLE_OFFSETS = (0, 32, 47)       # the helper's kRoleOffsets: walking, actions, sitting
HOLIDAY_ROLE_FRAMES = (32, 15, 9)        # ... kRoleFrameCounts
HOLIDAY_DETAILS = 8                      # 2 sexes x 4 bodies, highrez_bodies_final2.png's place
# DrawFamily: where each call returns (the person is told by it) and the record the scene keeps
DF_PARENT1_RETURN = 0x13F                # df_parents + 13Fh: the DrawParent of parent 1 (record in ebx, +4)
DF_PARENT2_RETURN = 0x239                # df_parents + 239h: the DrawParent of parent 2 (record in ebx, +DCh)
DF_CHILD_RETURN = 0xFF                   # df_child + FFh: the DrawChild of child edi / D8h ([ebp+10h] + 1B8h + edi)

# The people sheets (image id, which file of the grid's files, the file): theGraphicsManager's table
IMAGE_SHEETS = (
    (0x240, 0, "female_heads00.png"), (0x240, 1, "female_heads10.png"),
    (0x241, 0, "female_bodies00.png"), (0x242, 0, "female_actions00.png"), (0x243, 0, "female_sit00.png"),
    (0x244, 0, "male_heads00.png"), (0x244, 1, "male_heads10.png"),
    (0x245, 0, "male_bodies00.png"), (0x246, 0, "male_actions00.png"), (0x247, 0, "male_sit00.png"),
    (0x15, 0, "bigheads00.png"), (0x15, 1, "bigheads10.png"),
    (0x16, 0, "highrez_bodies_final2.png"),
    (0x1DE, 0, "carrying.png"),
)

# The pinned bytes (the B209 core variant's), one run each.
HEX_blit = (
    "558BEC81EC98000000A180D6590033C58945FCF30F1045240F57D20F2FD08B4508894DB48945B00F83121B0000F30F10"
    "4D280F2FD10F83041B00008B551C"
)
HEX_draw_villager = (
    "558BEC83EC6053566975080CCC01008BD9578975B88B841EC48703008D8E70CC01008BBC1EC887030003CB80BC1EC087"
    "030000894DB08945F07440F30F2C841E10380200F30F100D34D44F00660F6EC00F5BC00F2FC1760A0F57C0F30F11450C"
    "EB19F30F5EC1F30F100D1C664F00F30F59C1F30F5CC8F30F114D0C8D45A850E88C63FFFF8B45A8BA0C0000002B45F08B"
    "8C1EE08703008945C48B45AC2BC7894DE02BBC1EE88703008945BC33C039841EC8360200897DD00F95C08945E48B841E"
    "F43602008945E833C081BC1EC4360200840300000F4DC28945B483F907770D8B841E008803008D0CC1894DE08D8E70CC"
    "0100C745D40000000003CBC745DC00000000E8A9CDFFFF8B841EC4360200F30F1005C4554F00F30F1145D8D95DF43D18"
    "0100007D24660F6EC00F5BC0F30F5E05B0E15400F30F5805B8E15400F30F5E05F05D4F00F30F1145D86A008D45D45051"
    "F30F1104248D45A0FFB41EF0360200B9A8145A00FF75E4FFB41E0488030050E84CEEF3FFFF75ACB9B8D0B400C6450B00"
    "FF75A8E8E883000084C07417FF75ACB9E00A5E00FF75A8E8F4ACF8FF83F8050F94450B80BC1EC0870300000F85DC0000"
    "0083BC1E08880300060F84CE00000083BC1EE8870300000F8CC00000008A841EF6870300F30F1045F48845FF0F28C884"
    "C07408F30F590D44584F008B55A80F28C1F30F5905B4E154008BCA83C2DE8955C8F30F2CC00F28C1F30F5905A0A04F00"
    "2BC8894DCC8B4DAC894DF883C1E0F30F2CC0894DEC2945F8807DFF008B45F8740983C01483C114894DEC807D0B00752C"
    "F30F10450CB9D0806F006A0083EC08F30F11442404F30F110C2450FF75CCFF7304E86A46FCFF8B4DEC8B55C880BC1EF5"
    "87030000741751C704240000803F5152FF7320B9D0806F00E87345FCFF8B841E008803008945CC85C0740A83F8037405"
    "83F80475758A4D0B84C975718D8E70CC010003CBE8F7CBFFFFF30F1015DCB06F008BCF0F28C28B55F0F30F5905F4EA54"
    "00F30F5915F8EA5400F30F2CC0D95DC8660F6EC00F5BC0F30F5945C8F30F2CC02BD0F30F2CC2660F6EC00F5BC0F30F59"
    "45C8F30F2CC02BC88D8670CC0100515203C38BCB50E896FBFFFF8A4D0B8B7DC48B45D0037DF00345BC80BC1EF6870300"
    "00897DEC8945F80F85BA00000084C90F84B200000083BC1EE0870300360F84A40000008B3D90D1B6008B3594D1B60051"
    "C70424CDCCCC3EE86436FDFF8BC8E86DF7FAFF8B4B3483E003508B45F82BC68B75EC83E820508BC62BC783E82050FF73"
    "2CE84A3BFBFF6A64E8D3F6FAFF83C40483F8057D4AB9B8406800E8F128FAFF84C0753C6A07E8B6F6FAFF8B75F883C6E0"
    "6A0703F0E8A7F6FAFF8B7DEC83C40883C7E0B9700C670003C76A006A016AFF6A006A0156506A00E864E2F9FF8B75EC8B"
    "4DF8E98E000000F30F1045F48D45BC508D45DC5051F30F1104248D45C0FF75E8B9A8145A00FF75E46A00FF75E050E8ED"
    "EAF3FFF30F10450C83EC088B75F8B9D0806F002B70042B38F30F11442404F30F1045F4F30F110424FF75BCFF75E85657"
    "FF75DCE8A850FFFFF30F1045F48D45C051F30F110424B9A8145A00FF75E8FF75E46A00FF75E050E8F4EBF3FF8B480403"
    "CE8B3003F78B55B883EC08F30F10450C2B4DA42B75A08B841A048803000345B4F30F11442404F30F1045D8F30F110424"
    "50FFB41AF03602005156FF75D4B9D0806F00E88944FCFF8B45CC83F801741483F802740F83F806740A83F805740583F8"
    "07756A807D0B0075648B75B08BCEE8BDC9FFFFF30F1015DCB06F000F28C28B55F0F30F5905F4EA54008B4DD0F30F5915"
    "F8EA5400F30F2CC0D95D0C660F6EC00F5BC0F30F59450CF30F2CC02BD0F30F2CC2660F6EC00F5BC0F30F59450CF30F2C"
    "C02BC85152568BCBE863F9FFFF5F5E5B8BE55DC20800"
)
HEX_draw_carried = (
    "558BEC5356578B7D088BD98B8798BB01008BB79CBB010083F809741C83F802741783F811741283F812740D8B551083F8"
    "17750E83C214EB068B551083C20A89551083BF186B000000747F8B4D0C8D42F683C1F651C704240000803F6A035051FF"
    "7324B9D0806F00E84449FCFF83BF1C6B0000017E518B4D0C8B451083C1F151C704240000803F83C0FB6A035051FF7324"
    "B9D0806F00E81649FCFF83BF1C6B00000375238B4D0C8B451083C1F651C704240000803F486A035051FF7324B9D0806F"
    "00E8EA48FCFF8B551083FEFF744F83FE03744A83FE4F7C2451C704240000803F8D46B15052FF750CB9D0806F00FF7328"
    "E8BB48FCFF5F5E5B5DC20C008B4D0C8D42F683C1F651C704240000803F565051FF7324B9D0806F00E89348FCFF5F5E5B"
    "5DC20C00"
)
HEX_hol_scene_thunk = (
    "8BC4FF701CFF7018FF7014FF7010FF700CFF7008FF700451E81300000083C420C21C00CCCCCC"
)
HEX_hol_scene_impl = (
    "83EC1853555657E844FEFDFF8B5C24308BF885FF743F85DB743B0F280580E1540033F60F11442410C744242046020000"
    "C7442424470200000F1F840000000000FF74B4108BCFE80500FEFF3BD874094683FE067CEB83CEFF8B4C242C8B6C243C"
    "85C90F84E800000085FF0F84E000000085F60F88D80000008D45CE83F8030F87CC000000B856555555F7EE8BCAC1E91F"
    "03CA8B5424408D04492BF085D20F88A30000003B14B50CCC54000F8D960000008D45CE8D04888D0CC5000000002BC88B"
    "04B500CC54008D34C803F281FEBF0100007773FF34B518CC54008BCFE86FFFFDFF"
)
HEX_detail = (
    "558BEC83EC34807D10005356578BF9897DD874146A03E8959AFBFF83C4043B053CB1590074EEEB1C68E8030000E87E9A"
    "FBFF83C40483F8147F0F6A03E86F9AFBFF83C404A33CB159008BCFE8A06E00008B87546A0000F30F100DF05D4F00D95D"
    "103D180100007D1D660F6EC00F5BC0F30F5E05B0E15400F30F5805B8E15400F30F5EC1EB08F30F1005C4554F008B8780"
    "6A000033DB399F586A00008BB7846A0000F30F1145EC0F95C3F30F59C18945E8C745F000000000C745F400000000F30F"
    "2CC0895DE4F30F1045108945D48D45FC508D45F05051F30F1104248D45DC56536A006A3850B9A8145A00E8618EF4FFF3"
    "0F104510F30F5905F05D4F008B4D082B088B550C2B5004F30F2CC06A00894DF88955E050FF75FC565251FF75F08B8FFC"
    "CB0100E8E8F5FFFFF30F1045108D45CC51F30F110424B9A8145A0056536A006A3850E8698FF4FF8B353CB15900F30F10"
    "45EC8B388B58048D45FC508D45F450B856555555F7EE518BC2F30F110424FF75E8C1E81FFF75E403C2BA040000002BD0"
    "8D045603C2508D45CC50B9A8145A00E86C8EF4FF8B4DF88B75D82B0803CF8B7DE02B780403FB894DF881BE546A000084"
    "0300007C118B4DF4E89336F9FF992BC28BC8D1F9EB0233C98B45FC6A00FF75D403C18B8EFCCB010050FF75E857FF75F8"
    "FF75F4E8B8EDFBFF5F5E5B8BE55DC20C00"
)
HEX_hol_detail_thunk = (
    "8BC4FF701CFF7018FF7014FF7010FF700CFF7008FF700451E81300000083C420C21C00CCCCCC"
)
HEX_hol_detail_impl = (
    "83EC2053555657E874FCFDFF8B5C24388BF885FF742A85DB74266A168BCFE85DFEFDFF3BD875198B44244833C983F801"
    "741185C00F94C18D0C4DFFFFFFFFEB0383C9FF837C2434008B6C24440F849500000085FF0F84CB00000085C90F888500"
    "00008D45CE83F803777D8D45CE8D04888944241083F807776EFF348518D35400"
)
HEX_event = (
    "558BEC83EC38807D1800B802000000538BD9B905000000560F45C18BCB57A33CB15900E8C86C0000D84D148B83546A00"
    "00F30F1015F05D4F00D95DFC3D180100007D22660F6EC00F5BC0F30F5E05B0E15400F30F5805B8E15400F30F5EC2F30F"
    "594514EB05F30F104514F30F104DFC8B5508F30F1145140F28C1F30F5905B4E154008B4D0C6A006A00F30F2CC00F28C1"
    "F30F5905A0A04F002BD0F30F2CC00F28C1F30F59C22BC8F30F2CF857518B8BFCCB010052FF353C807000E8F1EAFBFF8B"
    "83806A0000BA0C000000F30F104514F30F5905F05D4F008945F033C03983586A00008BB3846A00000F95C0C745F80000"
    "000033C98945F481BB546A000084030000C745EC000000000F4DCA894DD8F30F2CC8F30F1045FC894DDC8D4DE8518D4D"
    "F85151F30F110424B9A8145A0056506A006A2E8D45C850E8148CF4FFF30F1045FC8D45D051F30F110424B9A8145A0056"
    "FF75F46A006A2E50E8538DF4FF807D18008D4DC88B550C8D45D00F44C18B4D086A0057FF75E82B082B5004894DFC8955"
    "E4565251FF75F88B8BFCCB0100E87EF3FFFF807D180074088B75088B7D0CEB0E8B75FC8B7DD40375D08B4DE403F9F30F"
    "1045148D45EC6A005051F30F1104248D45E0FF75F0B9A8145A00FF75F4FF353CB1590050E8278CF4FF8B8BFCCB01006A"
    "00FF75DC2B302B7804A13CB159000345D850FF75F05756FF75ECE8A1EBFBFF5F5E5B8BE55DC21400"
)
HEX_draw_parent = (
    "558BEC83EC185356578BF9E8D02C02008BD80F57C08D45E8895DFC5083EC108BCC0F1145E80F10470C0F11018B4D08E8"
    "9C0600000F1045E883EC108BCB8BC40F1100E8D92F0200F30F1045206A0051F30F1104248BCFFF751CFF7518FF7514FF"
    "7510FF750CE8E60000008B550833F68B1A8B4A088B04B54C5856002BC803D8894DF88B42042BC6894DF08B4F10895DE8"
    "8945F48D50FF8955EC3BC17E3F3B57187D3A0F1045E88B4DFC83EC108BC40F1100E86A2F0200F30F1045206A0051F30F"
    "1104248BCFFF751CFF7518FF7514FF7510FF750CE8770000008B4F108B45088B500C03D68955EC8D42018945F43BD17C"
    "3C3B57187D370F1045E88B4DFC83EC108BC40F1100E8162F0200F30F1045206A0051F30F1104248BCFFF751CFF7518FF"
    "7514FF7510FF750CE8230000008B4DF8468B550883FE060F8C37FFFFFF5F5E5B8BE55DC21C00"
)
HEX_draw_child = (
    "558BEC83EC2053568BD957895DFCE85D3502008BF00F57C08D45E08975F85083EC108BCC0F1145E00F10430C0F11018B"
    "4D08E8290F00000F1045E083EC108BCE8BC40F1100E866380200F30F1045206A0051F30F1104248BCBFF751CFF7518FF"
    "7514FF7510FF750CE8730900008B550833DB8B3A8B7208660F1F8400000000008B049D645856008BCB2BF0D1E903F889"
    "4DF48B42042BC1897DE08B4DFC8975F08975E88D50FF8945EC8955E43B41107E403B51187D3B0F1045E08B4DF883EC10"
    "8BC40F1100E8E6370200F30F1045206A00518B4DFCF30F110424FF751CFF7518FF7514FF7510FF750CE8F20800008B4D"
    "FC8B45088B55F48B400C03D08955E48D42018945EC8B049D6858560085C074588B349D645856002BFE2BF003F80375F0"
    "897DE08975E83B51107C3D3B51187D380F1045E08B4DF883EC108BC40F1100E86C370200F30F1045206A00518B4DFCF3"
    "0F110424FF751CFF7518FF7514FF7510FF750CE8780800008B550883C30283FB080F8C09FFFFFF5F5E5B8BE55DC21C00"
)
HEX_draw_peep = (
    "558BEC83EC14E8852B0200807D20008945F4740AF30F100544584F00EB08F30F1005C4554F00F30F104D1C8D45FC5356"
    "8B7518578B7D10508D45F8F30F1145205051F30F110C248D45EC56570F28C1B9A8145A00F30F5905F05D4F006A006A38"
    "50F30F2CD8E806B3FAFF8D45EC51B9A8145A00F30F10451CF30F11042456576A006A3850E847B4FAFF8B4D0CF30F1045"
    "208B55082B48042B106A005351F30F110424FF75FC56518B4DF452FF75F8E8FD130200F30F10451C8D45FC8B7514508D"
    "45F85051F30F1104248D45EC56576A0D50B9A8145A00E845B3FAFF8B55088B4D0CF30F1045202B102B48046A005351F3"
    "0F110424FF75FC56518B4DF452FF75F8E8AB1302005F5E5B8BE55DC21C00"
)
HEX_df_parents = (
    "558BEC83EC4853568BD957895DE4E81D3102008945FCE8651D04006A018945F8E82BF504008BC8E8A4F50400FF7510B9"
    "884066008945E8E8A4E5FFFF89451085C00F84F20300000F104B748B4DFC83EC100F28C1660F7ECF660F73D804660F7E"
    "C60F28C1660F73D80C660F7EC00F10430C03450C8945F08BC40F114DC80F1100E8EB3302008B5D0C8B45086A6483C0F8"
    "8D4BFE03C703CE8945EC51C704240000803F5150894DE08B4DF86868020000E8EC1904000F1045C88B4D08FF75E8660F"
    "73D80883C104FF35FC575600660F7EC003C88D431D8B5D1003C65051894DDC8B4DFC8D430450E8851D02008B55088B4D"
    "0C51C704240000803FFF73288D4219FF732403C7FF73208945C88D425703C783C2378945D003D78D410D8955D803C689"
    "45CC8D414003C68945D48D413C03C68B75E450528D45C88BCE50E811030000837B2CFF8B7DFC754C0F10460C83EC108B"
    "CF8BC40F1100E8153302008B4DF86A0083EC08C745F480808080C74424040000803FC704249A99993EFF75F4FF75E0FF"
    "75EC6868020000E8741C0400508BCFE88C26020080BBF6000000000F84ED0000000F10460C83EC108BCF8BC40F1100E8"
    "BC3202006A64518B4DF8C704240000803FFF75F0FF75EC6868020000E8CF180400FF75E88B45F08BCFFF35FC57560083"
    "C01F50FF75DC8D83DC00000050E87E1C02008B4DF08B45C8518945C88B45D0C704240000803FFFB3000100008945D08D"
    "410FFFB3FC0000008945CC8D4142FFB3F80000008945D48D413E50FF75D88D45C88BCE50E81702000083BB04010000FF"
    "754C0F10460C83EC108BCF8BC40F1100E81B3202008B4DF86A0083EC08C745F480808080C74424040000803FC704249A"
    "99993EFF75F4FF75F0FF75EC6868020000E87A1B0400508BCFE892250200"
)
HEX_df_child = (
    "8B4D0C33FF897DF00F1145B8660F7EC3660F73D804660F7EC0035D0803C189450C8B45C403C18945EC8B868C0000002B"
    "868400000083C02A8945DC8B451039B8B40100000F8E5A010000900F10460C8B4DFC83EC108BC40F1100E87C3102008B"
    "450C8D4BF26A645183C0F8C704240000803F50518B4DF868690200008945D8E887170400FF75E88B45EC8D7320FF35FC"
    "5756008B4DFC83C005508B451069FFD800000005B80100005603C750E8FA1C02008B4D0C8D430D8945C88D43338945D0"
    "518D4104C704249A99193F8945CC8D41278945D48D41228B4D10FFB40FDC010000FFB40FD8010000FFB40FD401000050"
    "568B75E48D45C8508BCEE82CF8FFFF8B4D1083BC0FE0010000FF75520F10460C8B4DFC83EC108BC40F1100E8BB300200"
    "8B4DF88D43F26A0083EC08C7450880808080C74424040000803F"
)
HEX_ms_conceive = (
    "8DBEF46A00008BCF897DF8FFB3406B0000FFB3546A0000FFB6546A0000E8FA9A020084C00F84C60000008B45FC8BCE6A"
    "008B4014C780E05A020000000000FFB3846A0000FFB3806A0000680C1650006A01E8069D010084C00F8417010000"
)
HEX_vp_conceive = (
    "0F84CC0000006A00FFB3846A00008BCFFFB3806A0000680C1650006A01E842D9FEFF84C00F8495000000"
)
HEX_impregnate = (
    "558BEC515356578BF933F6B988406600E8FBB5F9FF8BD885DB0F8EAD020000B938807000E8B7A20000B938807000"
)
HEX_ad_draw = (
    "FF760C68D0010000E8E37709008B461083F8FF742A50B938807000E820320C000FB64E088B560C5181C2EB0000008BC8"
    "689A01000052E8D5860B00C6460800"
)
HEX_gm_find_image = (
    "558BEC8B4D0881F9E505000077578B048D58F76F0085C0754E8D0449C1E004398848AE57008D8048AE5700742D33D2B8"
    "48AE57003908741683C030423D68C958007CF18B048D58F76F005DC204008D0452C1E0048D8048AE570089048D58F76F"
    "005DC2040033C05DC20400"
)
HEX_vs_rename_message = (
    "807DE80074248D45E8B9884066005057E879CBFAFF6A198D45E8508D87646A000050E867D60200"
)
HEX_vs_rename_selection = (
    "807DE80074248D45E8B9884066005056E8FEC3FAFF6A198D45E8508D86646A000050E8ECCE0200"
)
HEX_ft_change_name = (
    "558BEC51538B5D0856538BF1E86F01000085C00F849A0000006A19FF750C50E81C950200"
)
HEX_gs_ctor = (
    "558BEC6AFF6888354F0064A100000000505156A180D6590033C5508D45F464A3000000008BF18975F08D4E08E8BFFEFF"
    "FF8BCEE808C0FDFFC70664D54F00B990D1B600C786D85C020000040000C786DC5C020000030000C686E05C020000C786"
    "C05C020000000000C786B85C020002000000C745FC00000000C70590D1B600F4010000C70594D1B600F4010000E83E57"
    "0300B990D1B600E8B4590300C786C45C0200FFFFFFFFE8A5B0FDFF83C0788BCE8986E45C0200E8C50600006A008BCEE8"
    "4C09000084C075078BCEE8D10500008BC68B4DF464890D00000000595E8BE55DC3"
)
HEX_gs_get = (
    "558BEC6AFF68C2354F0064A1000000005051A180D6590033C5508D45F464A300000000A1086B680085C0753D68FC6102"
    "00E8AA5A030083C4048945F0C745FC0000000085C0741B8BC8E842FDFFFFA3086B68008B4DF464890D00000000598BE5"
    "5DC333C0A3086B68008B4DF464890D00000000598BE55DC3"
)
HEX_gs_load = (
    "558BECB8AC5B0200E8E3580300A180D6590033C58945FC53568B75088BD985F60F85A10000005668900000008D856CFF"
    "FFFF50E8B8B9FDFF84C00F849B050000"
)
HEX_gs_save = (
    "558BEC837D0800568BF175208BD68D86205B0200F7DA6A001BD2689000000023D052E8D9B4FDFF5E5DC204008D866801"
    "0000B938055A0050E8C372F6FF"
)


class Pin:
    """One exact run of the core executable.

    how:  "search"        found by searching the executable sections (must match exactly once);
          ("call", p, o)  the target of the call rel32 whose E8 byte is at offset o of pin p (then byte-verified).
    skip: leading bytes that are wildcards because another companion DLL writes its 5-byte jmp there (this DLL
          never writes them).
    wild: (offset, length) runs that are wildcards because the patch build changes them.
    """

    def __init__(self, name, va, hexbytes, how, note, skip=0, wild=()):
        self.name = name
        self.va = va
        self.bytes = bytes.fromhex("".join(hexbytes) if isinstance(hexbytes, tuple) else hexbytes)
        self.how = how
        self.note = note
        self.skip = skip
        self.wild = wild


SEARCH = "search"
COMPANION_HOOKED = 5          # another companion's entry jmp (Up to 28 Children, Family History)

PINS = [
    Pin("blit", 0x476520, HEX_blit, SEARCH,
        "ldwGameWindowImpl::BlitRectWithAlpha(SDL_Surface *, x, y, left, top, right, bottom, float, float, bool): "
        "every scaled or see-through cell draw ends here; thiscall, ret 28h. Entry hook (9 bytes: push ebp; "
        "mov ebp, esp; sub esp, 98h)."),
    Pin("draw_villager", 0x4C5D50, HEX_draw_villager, SEARCH,
        "CVillagerManager::DrawVillager(int slot, float alpha) whole: the villager at manager + 1CC70h + slot * "
        "1CC0Ch; DrawCarriedItems at +315h and +548h; the body through the Holiday helper at +453h. Entry hook "
        "(6 bytes)."),
    Pin("draw_carried", 0x4C5C00, HEX_draw_carried, ("call", "draw_villager", 0x315),
        "CVillagerManager::DrawCarriedItems(CVillager const &, ldwPoint) whole: while she carries (+6B18h) cell 3 of "
        "the carrying grid (+24h) once for each baby (+6B1Ch); thiscall, ret 0Ch."),
    Pin("hol_scene_thunk", 0x4BB250, HEX_hol_scene_thunk, ("call", "draw_villager", 0x453),
        "B209's VF2DrawSceneVillagerBodyFrame (generated): the house's body draw, the arguments passed on to its "
        "implementation (+18h); ret 1Ch."),
    Pin("hol_scene_impl", 0x4BB280, HEX_hol_scene_impl, ("call", "hol_scene_thunk", 0x18),
        "VF2DrawSceneVillagerBodyFrameImpl head (generated): a body 50..53 drawn from one picture each, "
        "kImageIds[gender * 4 * 56 + body * 56 + kRoleOffsets[role] + frame] (+D6h), frame < kRoleFrameCounts[role] "
        "(+A6h), kRoleOffsets (+C2h), the index at most 1BFh."),
    Pin("detail", 0x4BBD10, HEX_detail, SEARCH,
        "CVillager::DrawDetailVillager(ldwPoint, bool) whole: the big head (bigheads, the older look from age "
        "384h) and the big body through the Holiday helper (+123h). Entry hook (6 bytes)."),
    Pin("hol_detail_thunk", 0x4BB420, HEX_hol_detail_thunk, ("call", "detail", 0x123),
        "B209's VF2DrawVillagerBodyFrame (generated): the portraits' body draw; implementation at +18h."),
    Pin("hol_detail_impl", 0x4BB450, HEX_hol_detail_impl, ("call", "hol_detail_thunk", 0x18),
        "VF2DrawVillagerBodyFrameImpl head (generated): a portrait body 50..53 from kDetailImageIds[sex * 4 + body] "
        "(+7Ch; female first)."),
    Pin("event", 0x4BBF10, HEX_event, SEARCH,
        "CVillager::DrawEventVillager(int, int, EBodyPosition, float, bool) whole: an event pop-up's portrait and the "
        "main screen's; the body through the Holiday helper (+18Dh). Entry hook (6 bytes)."),
    Pin("draw_parent", 0x4597A0, HEX_draw_parent, SEARCH,
        "CFamilyTreeScene::DrawParent(ldwRect &, ldwPoint, int sex, int head, int body, float) whole; DrawPeep at "
        "+65h; ret 1Ch. Entry hook (6 bytes)."),
    Pin("draw_child", 0x458F10, HEX_draw_child, SEARCH,
        "CFamilyTreeScene::DrawChild(ldwRect &, ldwPoint, int sex, int head, int body, float) whole; DrawPeep at "
        "+68h; ret 1Ch. Entry hook (6 bytes)."),
    Pin("draw_peep", 0x4598F0, HEX_draw_peep, ("call", "draw_parent", 0x65),
        "CFamilyTreeScene::DrawPeep(ldwPoint, int, int, int, float, bool) whole: two DrawScaled calls."),
    Pin("df_parents", 0x459350, HEX_df_parents, SEARCH,
        "CFamilyTreeScene::DrawFamily(int, int, int) up to +28Eh (Revive's B210 cave replaces the 7 bytes there): "
        "the record from GetFamilyRecord in ebx, parent 1's DrawParent (+13Ah, the sex at [ebx+20h]) and parent "
        "2's (+234h, [ebx+0F8h])."),
    Pin("df_child", 0x4595E5, HEX_df_child, SEARCH,
        "DrawFamily from +295h: the children's loop, edi = k * 0D8h, the record at [ebp+10h], DrawChild (+0FAh) "
        "with the sex at [edi + record + 1D4h]."),
    Pin("ms_conceive", 0x4A24D4, HEX_ms_conceive, SEARCH,
        "theMainScene's try-for-a-baby: CVillager::Impregnate(1, \"Joey\", father's head, father's body, 0) on the "
        "mother (+51h)."),
    Pin("vp_conceive", 0x4CAEEC, HEX_vp_conceive, SEARCH,
        "CVillagerPlans::ProcessCurrentPlan's Impregnate (+1Dh): the same arguments, through a jmp thunk in some "
        "variants."),
    Pin("impregnate", 0x4BC230, HEX_impregnate, SEARCH,
        "CVillager::Impregnate head (thiscall, ret 14h). Family History hooks its entry.", skip=COMPANION_HOOKED),
    Pin("ad_draw", 0x403600, HEX_ad_draw, SEARCH,
        "CAdoptionScene::DrawScene: GetVillager(slot) on the villager manager (+17h), then DrawDetailVillager "
        "(+36h)."),
    Pin("gm_find_image", 0x49B260, HEX_gm_find_image, SEARCH,
        "theGraphicsManager's image lookup (stdcall, id; ret 4): the table of 30h-byte entries (+21h, +27h, +30h) up "
        "to its end (+3Dh). The largest id (+8h) grows with the patcher's own images: a wildcard.",
        wild=((0x8, 4),)),
    Pin("vs_rename_message", 0x4AAB72, HEX_vs_rename_message, SEARCH,
        "theVillagerScene::HandleMessage: a name typed in the Details box goes to CFamilyTree::ChangeName "
        "(villager edi, text) at +10h. Family History retargets this call."),
    Pin("vs_rename_selection", 0x4AB2ED, HEX_vs_rename_selection, SEARCH,
        "theVillagerScene::UpdateSelection: the same at +10h (villager esi). Family History retargets this call."),
    Pin("ft_change_name", 0x457700, HEX_ft_change_name, SEARCH,
        "CFamilyTree::ChangeName(CVillager &, char const *) head; thiscall, ret 8. Up to 28 Children hooks its "
        "entry.", skip=COMPANION_HOOKED),
    Pin("gs_ctor", 0x4994B0, HEX_gs_ctor, SEARCH, "theGameState::theGameState(): stores the vtable (+3Ah)."),
    Pin("gs_get", 0x499720, HEX_gs_get, SEARCH, "theGameState::Get(): the singleton's instance pointer (+24h)."),
    Pin("gs_load", 0x499EC0, HEX_gs_load, SEARCH,
        "theGameState::Load(int slot) head: 0 = the settings file, 1..5 a family; ret 4. Up to 28 Children hooks "
        "its entry.", skip=COMPANION_HOOKED),
    Pin("gs_save", 0x49AB00, HEX_gs_save, SEARCH,
        "theGameState::Save(int slot) head; ret 4. Up to 28 Children hooks its entry.", skip=COMPANION_HOOKED),
]

# Function entries the DLL hooks, calls or relies on: name -> pin (the entry is the pin's first byte).
FUNCTIONS = {
    "BLIT": "blit",
    "DRAW_VILLAGER": "draw_villager",
    "DRAW_CARRIED": "draw_carried",
    "HOL_SCENE_THUNK": "hol_scene_thunk",
    "HOL_SCENE_IMPL": "hol_scene_impl",
    "DETAIL": "detail",
    "HOL_DETAIL_THUNK": "hol_detail_thunk",
    "HOL_DETAIL_IMPL": "hol_detail_impl",
    "EVENT": "event",
    "DRAW_PARENT": "draw_parent",
    "DRAW_CHILD": "draw_child",
    "DRAW_PEEP": "draw_peep",
    "IMPREGNATE": "impregnate",
    "FT_CHANGE_NAME": "ft_change_name",
    "GS_LOAD": "gs_load",
    "GS_SAVE": "gs_save",
}

# Places the DLL compares a return address with: name -> (pin, offset).
RETURNS = {
    "RET_PARENT1": ("df_parents", DF_PARENT1_RETURN),
    "RET_PARENT2": ("df_parents", DF_PARENT2_RETURN),
    "RET_CHILD": ("df_child", DF_CHILD_RETURN),
}

# Globals read from a relocated 32-bit field of a pin: name -> (pin, offset of the field).
GLOBALS = {
    "FAMILY_TREE": ("df_parents", 0x30),
    "VILLAGER_MANAGER": ("impregnate", 0x20),
    "GAME_STATE_INSTANCE": ("gs_get", 0x24),
    "GS_VTABLE": ("gs_ctor", 0x3A),
    "IMAGE_TABLE": ("gm_find_image", 0x30),
    "IMAGE_TABLE_END": ("gm_find_image", 0x3D),
    "HOL_FRAME_IDS": ("hol_scene_impl", 0xD6),
    "HOL_ROLE_FRAMES": ("hol_scene_impl", 0xA6),
    "HOL_ROLE_OFFSETS": ("hol_scene_impl", 0xC2),
    "HOL_DETAIL_IDS": ("hol_detail_impl", 0x7C),
}
# Every other place the same globals appear (the prover and the DLL check each one agrees).
GLOBAL_ALSO = {
    "FAMILY_TREE": (("impregnate", 0x0C), ("vs_rename_message", 0x0A), ("vs_rename_selection", 0x0A)),
    "VILLAGER_MANAGER": (("ad_draw", 0x17),),
    "IMAGE_TABLE": (("gm_find_image", 0x21), ("gm_find_image", 0x27)),
}
# Core-variant values (evidence, checked by the prover; never given to the DLL).
CORE_VALUES = {
    "FAMILY_TREE": 0x664088,
    "VILLAGER_MANAGER": 0x708038,
    "GAME_STATE_INSTANCE": 0x686B08,
    "GS_VTABLE": 0x4FD564,
    "IMAGE_TABLE": 0x57AE48,
    "IMAGE_TABLE_END": 0x58C968,
    "HOL_FRAME_IDS": 0x54CC18,
    "HOL_ROLE_FRAMES": 0x54CC0C,
    "HOL_ROLE_OFFSETS": 0x54CC00,
    "HOL_DETAIL_IDS": 0x54D318,
}
CORE_MAKE_GAME_STATE_PATH = 0x475B40

# The calls the DLL retargets: name -> (pin, offset of the E8 byte, the function it must reach). On disk the call
# reaches the function itself or a `jmp rel32` thunk to it; live, it may already reach another companion's
# handler (outside the executable), which the DLL then calls.
CALL_HOOKS = {
    "CALL_CARRIED1": ("draw_villager", 0x315, "DRAW_CARRIED"),
    "CALL_CARRIED2": ("draw_villager", 0x548, "DRAW_CARRIED"),
    "CALL_CONCEIVE_MAIN": ("ms_conceive", 0x51, "IMPREGNATE"),
    "CALL_CONCEIVE_PLAN": ("vp_conceive", 0x1D, "IMPREGNATE"),
    "CALL_RENAME_MESSAGE": ("vs_rename_message", 0x10, "FT_CHANGE_NAME"),
    "CALL_RENAME_SELECTION": ("vs_rename_selection", 0x10, "FT_CHANGE_NAME"),
}
# Other calls the DLL relies on (checked, never written): (pin, offset, function).
CALLS = (
    ("hol_scene_thunk", 0x18, "HOL_SCENE_IMPL"),
    ("hol_detail_thunk", 0x18, "HOL_DETAIL_IMPL"),
    ("event", 0x18D, "HOL_DETAIL_THUNK"),
    ("df_parents", 0x13A, "DRAW_PARENT"),
    ("df_parents", 0x234, "DRAW_PARENT"),
    ("df_child", 0xFA, "DRAW_CHILD"),
    ("ad_draw", 0x36, "DETAIL"),
    ("draw_child", 0x68, "DRAW_PEEP"),
)
# Entry hooks: a 5-byte jmp to the DLL and a trampoline of the first `steal` bytes (whole, position-independent
# instructions) that continues at entry + steal.
ENTRY_HOOKS = {
    "BLIT": 9,                 # push ebp; mov ebp, esp; sub esp, 98h
    "DRAW_VILLAGER": 6,        # push ebp; mov ebp, esp; sub esp, 60h
    "DETAIL": 6,               # ... sub esp, 34h
    "EVENT": 6,                # ... sub esp, 38h
    "DRAW_PARENT": 6,          # ... sub esp, 18h
    "DRAW_CHILD": 6,           # ... sub esp, 20h
}

# Address constants the DLL derives (enum order of the header): functions, returns, globals, then call sites.
ADDRESS_CONSTANTS = tuple(FUNCTIONS) + tuple(RETURNS) + tuple(GLOBALS) + tuple(CALL_HOOKS)
# Values that only exist for the core variant.
CORE_ONLY_CONSTANTS = ("IMAGE_BASE", "CORE_MAKE_GAME_STATE_PATH", "COMPANION_HOOKED")
