"""Translations: sites in the B200 Virtual Families 2 executable (core variant).

Single source of truth for every place the companion DLL vf2tr_b200.dll touches or relies on. Every pin is the exact
bytes of the B200 link output (`Virtual Families 2 - B200.exe`, core variant, built by
work/patch_mobile_furniture_pack.py); the DLL, the generator and the tests refuse an executable that is not that
build at these places.

The B200 image is relocated (DYNAMICBASE, .reloc) and each of the 32 matrix variants links to different addresses, so
the DLL holds no game address. It searches the live image for each pinned run (relocated fields and call/jmp
displacements are wildcards) and derives every address from where the runs were found.
runtime/tools/gen_b200_translations_sites.py proves the derivation on the core variant and on every other executable
it is given.

How the game holds its text, and what the DLL changes
-----------------------------------------------------

Every line of the game is a static record {id, key*, text*, override*} (16 bytes) of one table in .data
(`stringTable`, theStringManager's). theStringManager's constructor (string_table_scan) indexes the records by id:
`index[id]` = the first record with that id (ids 1..MAX_ID-1). The game's own lookup, theStringManager::GetString(id)
(get_string, stdcall, one argument), and its template filler GetStringFromNameGenderTemplate (fill_template, stdcall,
fills `{name}` `{name2}` `{award}` and the person choice `{he/she}` into a caller's buffer of a given size and never
writes past it), both return the record's OVERRIDE (+0Ch) when it is not 0, else its text (+08h): the game's own
localisation hook, fed by an `sm.xml` the game does not ship. The DLL sets the override of each translated line. No
code of the lookup is changed.

Two things have to be right for that:

* The constructor's last loop clears every override that does not hold what `sm.xml` would give. It runs once, when
  the string manager is first built (string_manager_get builds it on first use). The DLL calls string_manager_get
  itself first, so the manager exists before it sets any override.
* A translation can be longer than the English. The game copies lines into fixed spaces with the C runtime's strncpy,
  strncat and sprintf, and with a few inline byte loops. The DLL replaces the entry of strncpy and sprintf with a
  guard (a 5- or 6-byte jmp; the stolen instructions are position independent and run from a trampoline that is
  made executable before the jmp is written): a translated line that strncpy would leave without its NUL (it is the
  count n or longer, its English is shorter than n) is cut at n - 1, and a sprintf that is handed a translated format
  or argument gives at most the text the English gives. strncat takes its caller's count and is not guarded (its pin
  is only for the room scan). The ids whose copy is an inline loop, or is a sprintf / strncat the scan resolved, are
  listed in b200tr_limits.h (English length); the others are at most MAX_LINE bytes.
"""
from __future__ import annotations

IMAGE_BASE = 0x400000
B200_EXE_NAME = "Virtual Families 2 - B200.exe"

PATCHER_FOLDER = "Virtual Families 2 Patcher Files"
DLL_NAME = "vf2tr_b200.dll"
INI_NAME = "vf2tr.ini"
INI_KEY = "Translations"
LOG_NAME = "Translations.log"
CHOICE_NAME = "Translation.ini"
COPY_NAME = "Translation.txt"
STARTUP = "B200Tr_Startup"
SETTING = "translations"
FLAG_SECTION = ".vf2trns"
FLAG_SYMBOL = "_gVF2Translations"
STATUS_MAGIC = 0x52543254          # 'T2TR' little-endian: T, 2, T, R

# ---- layout (the same in every variant; compiled into the DLL)
RECORD_SIZE = 0x10                 # {id, key*, text*, override*}
RECORD_ID = 0x00
RECORD_KEY = 0x04
RECORD_TEXT = 0x08
RECORD_OVERRIDE = 0x0C
MAX_LINE = 1000                    # no line is longer than this many UTF-8 bytes (the dialogs copy at most 3FFh)
GAME_TITLE = "Virtual Families 2"
UNICODE_DLLS = ("vf2unicode_b200.dll", "vf2unicodefont_b200.dll")
UNICODE_ACTIVE_EXPORT = "B200Unicode_UnicodeTextActive"


class Pin:
    """One exact run of the executable (whole instructions of the core variant).

    fields: {name: (offset in the run, kind)}; kind "abs" = a relocated 32-bit address, "u32" = a constant.
    wild:   (offset, length) spans that differ between variants and are not relocated (a table's size).
    steal:  for a function entry the DLL hooks: how many bytes of whole instructions are stolen (>= 5).
    A relocated 32-bit field and the 32-bit displacement of every call / jmp rel32 are wildcards when the run is
    looked for in another variant.
    """

    def __init__(self, name, va, hexbytes, note, fields=None, wild=(), steal=0):
        self.name = name
        self.va = va
        self.bytes = bytes.fromhex(hexbytes)
        self.note = note
        self.fields = fields or {}
        self.wild = tuple(wild)
        self.steal = steal


# ---- core-variant addresses (the DLL derives these in every variant)
STRING_TABLE = 0x58C0B8             # the first record: {1, key, text, 0}
STRING_COUNT = 0xDE8                # records in the core variant (a variant with more strings has more)
STRING_INDEX = 0x700018             # index[id] -> record (index[0] is the 4 bytes below it, never used)
STRING_MAX_ID = 0xFF3               # ids 1 .. MAX_ID - 1
STRING_MANAGER_INSTANCE = 0x700010  # theStringManager::mInstance
GET_STRING = 0x4A8940               # theStringManager::GetString(id) stdcall, ret 4
FILL_TEMPLATE = 0x4A8990            # GetStringFromNameGenderTemplate(dst, size, id, name, sex, award, name2, sex2) ret 20h
STRING_MANAGER_GET = 0x4A87A0       # theStringManager::Get() static
STRNCPY = 0x4D7840                  # strncpy(dst, src, n) cdecl
STRNCAT = 0x4D82A0                  # strncat(dst, src, n) cdecl
SPRINTF = 0x4020A0                  # sprintf(dst, format, ...) cdecl

PINS = [
    Pin(
        "string_table_scan", 0x4A84C0,
        "B8B8C0580033C93910740E4183C01081F9E80D000072F033C0890495180070004281FAF30F00007CD7",
        "theStringManager's constructor, the loop that indexes the table: for each id from 1, scan the records "
        "[TABLE, TABLE + COUNT * 10h) for the first whose id is it and store its address at INDEX + 4 * id (or 0), "
        "for ids below MAX_ID. The DLL reads TABLE, COUNT, INDEX and MAX_ID from it.",
        fields={"TABLE": (1, "abs"), "COUNT": (17, "u32"), "INDEX": (28, "abs"), "MAX_ID": (35, "u32")},
        wild=((17, 4), (35, 4)),
    ),
    Pin(
        "get_string", 0x4A8940,
        "558BEC8B4D0885C97509B8E0534F005DC204008D41FF3DF10F000077238B048D1800700085C07418390875148B480C85C974068B"
        "C15DC204008B40085DC20400B8A0EA52005DC20400CC",
        "Whole theStringManager::GetString(id) stdcall, ret 4: id 0 gives the empty line; an id above MAX_ID - 2 or "
        "with no record, or a record whose id differs, gives \"Unknown String Id!!!!\"; else the record's OVERRIDE "
        "[record+0Ch] when it is not 0, else its text [record+08h].",
        fields={"INDEX": (32, "abs")},
        wild=((23, 4),),
    ),
    Pin(
        "fill_template", 0x4A8990,
        "558BEC81EC80000000A100C6590033C58945FC8B45148B4D1089458C8B452089458853568B750889758085C97507BBE0534F00EB2A"
        "8D41FF3DF10F0000771B8B048D1800700085C074103908750C8B580C85DB750A8B5808EB05BBA0EA5200",
        "The head of GetStringFromNameGenderTemplate (stdcall, ret 20h): the line is chosen exactly as GetString "
        "chooses it (the record's OVERRIDE [record+0Ch] when it is not 0, else its text), then filled into the "
        "caller's buffer of the given size.",
        fields={"INDEX": (66, "abs")},
        wild=((57, 4),),
    ),
    Pin(
        "string_manager_get", 0x4A87A0,
        "558BEC6AFF689F334F0064A1000000005051A100C6590033C5508D45F464A300000000A11000700085C0753A6A24E86D60020083"
        "C4048945F0C745FC0000000085C0741B8BC8E815FCFFFFA3100070008B4DF464890D00000000598BE55DC333C0A3100070008B4D"
        "F464890D00000000598BE55DC3",
        "Whole theStringManager::Get(): the first call builds the manager (new, then the constructor that indexes "
        "the table and reads sm.xml) and stores it at INSTANCE. The DLL calls it first so that the manager's last "
        "loop (which clears every override sm.xml did not give) has run before the DLL sets an override.",
        fields={"INSTANCE": (36, "abs")},
    ),
    Pin(
        "strncpy", 0x4D7840,
        "8B4C240C5785C90F849200000056538BD98B742414F7C603000000",
        "The entry of the C runtime's strncpy(dst, src, n) cdecl: ecx = n, push edi, test ecx; the first 5 bytes "
        "(mov ecx, [esp+0Ch]; push edi) are stolen.",
        steal=5, wild=((9, 4),),
    ),
    Pin(
        "strncat", 0x4D82A0,
        "8B4C240C5785C90F84B70000008B7C240856F7C703000000537411",
        "The entry of the C runtime's strncat(dst, src, n) cdecl (not hooked: the room scan tells a copy by its "
        "address).",
        wild=((9, 4),),
    ),
    Pin(
        "sprintf", 0x4020A0,
        "558BEC8D4510506A00FF750C6AFFFF7508E8DAFFFFFF8B08FF700483C90151E8B6560D0083C9FF83C41C85C00F48C15D",
        "The entry of sprintf(dst, format, ...) cdecl (the CRT's __stdio_common_vsprintf behind a stack frame): "
        "the first 6 bytes (push ebp; mov ebp, esp; lea eax, [ebp+10h]) are stolen.",
        steal=6,
    ),
]

# What the generator proves about the fields (the constants of the core variant).
CORE_EXPECTED = {
    "TABLE": STRING_TABLE, "COUNT": STRING_COUNT, "INDEX": STRING_INDEX, "MAX_ID": STRING_MAX_ID,
    "INSTANCE": STRING_MANAGER_INSTANCE,
}
# Pin names the DLL derives an address for, in the header's enum order.
HOOKS = ("strncpy", "sprintf")
