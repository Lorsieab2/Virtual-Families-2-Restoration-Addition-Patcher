"""Make src/vf2_game_pictures.json: every picture Virtual Families 2 has, and how it reaches the screen.

1. theGraphicsManager's image table (ImageList, 0x30 bytes an entry, read from the B200 desktop object
   theGraphicsManager.obj): +0 the image id (EImage), +4 the file (a string, through a relocation), +8 columns,
   +0Ch rows, +10h the second part of the file name, +14h files across, +18h files down.
   theGraphicsManagerImpl::GetImage / GetImageStrip / GetImageGrid make from it: rows > 0 an ldwImageGrid of
   columns x rows cells (one file, or the files <file><x><y><file2> side by side); rows 0 and columns > 0 an
   ldwImageStrip, one row of `columns` cells; both 0 one ldwImage, the whole file.
2. Every other file of a clean install's Images folder (data/vf2/clean-base-game-assets.json): named in the
   objects' code (searched for its name, or a printf pattern that makes it, such as MapX%dY%d.jpg) -- with the
   objects that name it -- or named nowhere: unused.
3. The clean install's Images files with their sizes and SHA-256, so the Picture Maker can tell the patcher's
   pictures (new or changed files) from the game's.
4. "usage": for every table id, whether code reached from WinMain asks theGraphicsManager for it, and which code
   (see image_usage below; "cell_unused" / "cell_labels" are single-cell facts, none proven here yet). It reads the
   game's Assetsnimpts.dat and petanimpts.dat (work/vanilla_runtime_payload or VF2_VANILLA_GAME_DIR), which the
   animation managers' records come from. tests/test_picture_usage.py recomputes it.

Numbers and names only, no picture. tests/test_game_pictures.py checks it against the objects again.

    python scripts/build_vf2_image_table.py [--objects work/desktop_obj_files]
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

import capstone
from capstone import x86

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))

OUTPUTS = (REPO / "src" / "vf2_game_pictures.json", REPO / "work" / "vf2_game_pictures.json")
CLEAN = REPO / "data" / "vf2" / "clean-base-game-assets.json"
IMAGE_LIST = "?ImageList@@3PAUImageDescriptor@@A"
ENTRY = 0x30
NOT_PICTURES = (".db", ".jbf", ".css")


def _string(obj, sym_index: int, addend: int) -> str:
    _name, value, sect, _cls = obj.symbols[sym_index]
    sec = obj.sections[sect - 1]
    data = obj.data[sec["ptr"]:sec["ptr"] + sec["size"]]
    at = value + addend
    return data[at:data.index(b"\0", at)].decode("latin-1")


def image_table(objects: Path) -> list:
    from vf2_people_emu import CoffObject
    obj = CoffObject(Path(objects) / "theGraphicsManager.obj")
    _name, base, sect = next((n, v, s) for n, v, s, _c in obj.symbols.values() if n == IMAGE_LIST)
    sec = obj.sections[sect - 1]
    raw = obj.data[sec["ptr"]:sec["ptr"] + sec["size"]]
    relocs = {va: si for va, si, _t in sec["relocs"]}
    out = []
    at = base
    while at + ENTRY <= len(raw):
        fields = struct.unpack_from("<12I", raw, at)
        path = _string(obj, relocs[at + 4], fields[1]) if at + 4 in relocs else None
        if path is None and out:
            break                                           # past the table's last entry
        path2 = _string(obj, relocs[at + 0x10], fields[4]) if at + 0x10 in relocs else None
        out.append({"id": fields[0], "file": path, "file2": path2, "cols": fields[2], "rows": fields[3],
                    "across": fields[5], "down": fields[6]})
        at += ENTRY
    return out


def table_files(table: list) -> set:
    """The Images files the table names, lower case."""
    names = set()
    for e in table:
        if e["across"] * e["down"] > 1:
            names |= {f"{e['file']}{x}{y}{e['file2']}".lower() for x in range(e["across"]) for y in range(e["down"])}
        else:
            names.add(e["file"].lower())
    return names


def _strings(objects: Path) -> dict:
    """Every printable string (4+ characters) of every object, lower case -> the objects it is in."""
    found: dict = {}
    for path in sorted(Path(objects).glob("*.obj")):
        for m in re.finditer(rb"[\x20-\x7e]{4,}", path.read_bytes()):
            found.setdefault(m.group().decode("latin-1").lower(), set()).add(path.stem)
    return found


# ====================================================================== which pictures the game's code asks for
# "usage" {id: [used, why]}: an image is used when code reached from WinMain asks theGraphicsManager for it (GetImage,
# GetImageStrip, GetImageGrid, Draw, DrawCell, DrawCentered, GetCellCount), unused only when no such code can.
#
# Reachability (over-approximated): the objects' relocations make the graph. Every function or data item (a symbol's
# span of its section) links to everything its bytes relocate to, so a function reaches what it calls or names, a
# vtable reaches its methods, a table of function pointers its functions. Roots: _WinMain@16 and every static
# initializer / terminator section (.CRT$XC*, .CRT$XI*, .CRT$XP*, .CRT$XT*). A constructed scene is reachable even when
# nothing ever switches to it.
#
# The id at each call: a small abstract interpreter walks every path of the calling function (jump tables included)
# tracking constants in registers and the pushed arguments, so `push 0x15f`, `lea eax, [esi + 0x24e]` in a counted
# loop, `setne cl; add ecx, 0x1d9` and the like give their exact ids. An id passed in as the function's own argument
# is followed to every caller of that function (theMessageBoxDlg::Init <- the constructors <- ShowMessageBox <- its
# callers; CStory::AddImage stores ids CStory::Draw draws). The ~50 calls whose id comes from data are resolved by
# SITE_RULES below from the tables they read (with their relocations); a reachable call that is neither constant nor
# covered by a rule stops the build.
IMAGE_CALL = re.compile(r"^\?(GetImage|GetImageStrip|GetImageGrid|Draw|DrawCell|DrawCentered|GetCellCount)"
                        r"@theGraphicsManager@@QAE")
GM_GET = "?Get@theGraphicsManager@@SAPAV1@XZ"
# Functions that take an EImage and hand it on (argument index of the EImage). Every function of the objects whose
# signature has an EImage argument is here (checked by _check_wrappers).
WRAPPERS = {
    "?AddImage@CStory@@QAE?BHW4EImage@@HHH@Z": 0,
    "??0theMessageBoxDlg@@QAE@PBDW4EImage@@0H@Z": 1,
    "??0theMessageBoxDlg@@QAE@W4StringId@@W4EImage@@0H@Z": 1,
    "?Init@theMessageBoxDlg@@IAEXPBDW4EImage@@0H@Z": 1,
    "?ShowMessageBox@@YAHPAVldwScene@@PBDW4EImage@@1H@Z": 2,
    "?ShowMessageBox@@YAHPAVldwScene@@W4StringId@@W4EImage@@1H@Z": 2,
}
ROOTS = ("_WinMain@16",)
ROOT_SECTIONS = (".CRT$XC", ".CRT$XI", ".CRT$XP", ".CRT$XT")
_FURNITURE = ("table", "FurnitureManager", "?itemInfo@@3PAUsFurnitureInfo@@A", 0x6C, 4,
              "the furniture table (itemInfo, through LookupFurnitureInfo)")
# (function, call address) -> how the id is found. Kinds:
#   ("table", object, symbol, stride, field, words): the dword at +field of every entry of the symbol's array (its
#       extent: up to the next symbol of its section);
#   ("pointers", object, symbol, stride, pointer field, count field, words): every entry's pointer to an EImage array of
#       `count` ids;
#   ("locals", [xmm constants...], [extra immediates], words): a local array the function fills from 16-byte
#       constants (and the listed `mov dword ptr [ebp - x], id` stores, which must be in the function);
#   ("callers", wrapper): the ids every reachable caller passes to that wrapper;
#   ("anim", manager, base, ((stride, count), ...)): the EImage fields of CAnimManager / CPetAnimManager's animation
#       records, as their LoadAssets leaves them after reading the game's animpts.dat / petanimpts.dat (emulated):
#       base + i*stride1 + j*stride2. The counts are the records' layout as the code indexes them: CAnimManager's
#       32 frames of 0xCA4 bytes (0x76F0..0x20B70, the block animpts.dat fills) x part + 2*gender (0..3, 0x328 apart);
#       its 30 head records of 0x328 bytes (15*gender + direction; the 0x5EB0 bytes read at 0x34774);
#       CPetAnimManager's 76 frames of 0x1D4 bytes (the 0x8AF0 bytes of petanimpts.dat) x 2 parts (0xE8 apart);
#   ("anim-any", manager): an EImage the editor reads at a computed offset of the manager: any table id the manager
#       object holds after LoadAssets (only bounds the unused claims; it proves no id used).
SITE_RULES = {
    ("?DrawScene@CCollectionScene@@MAEXXZ", 0xF1):
        ("table", "CollectionScene", "?gCollectionFrame@@3PAUSCollectable@CCollectionScene@@A", 12, 0,
         "its gCollectionFrame table"),
    ("?DrawScene@CCollectionScene@@MAEXXZ", 0x121):
        ("table", "CollectionScene", "?gCollectionLabel@@3PAUSCollectable@CCollectionScene@@A", 12, 0,
         "its gCollectionLabel table"),
    ("?DrawScene@CCollectionScene@@MAEXXZ", 0x27F):
        ("table", "CollectionScene", "?sm_sCollectable@CCollectionScene@@0PAUSCollectable@1@A", 12, 0,
         "its sm_sCollectable table"),
    ("?DrawScene@CCollectionScene@@MAEXXZ", 0x2B0):
        ("table", "CollectionScene", "?gInsectPin@@3PAUSCollectable@CCollectionScene@@A", 12, 0,
         "its gInsectPin table"),
    ("?HandleMouse@CCollectionScene@@UAE_NHUldwPoint@@@Z", 0xE5):
        ("table", "CollectionScene", "?sm_sCollectable@CCollectionScene@@0PAUSCollectable@1@A", 12, 0,
         "the sm_sCollectable table"),
    ("?LoadAssets@CFloatingAnim@@QAEXXZ", 0xF):
        ("table", "FloatingAnim", "?m_sAnim@CFloatingAnim@@0PAUSAnim@1@A", 16, 0, "its m_sAnim table"),
    ("?DrawVisibleStoreItem@CScrollingStoreScene@@AAEXHHH@Z", 0xA7):
        ("table", "ScrollingStoreScene", "?gIAPItem@@3PAUsIAPItem@@A", 12, 0, "its gIAPItem table"),
    ("?DrawVisibleStoreItem@CScrollingStoreScene@@AAEXHHH@Z", 0x225):
        ("table", "ScrollingStoreScene", "?gMenuItem@@3PAUsMenuItem@@A", 16, 0, "its gMenuItem table"),
    ("?DrawVisibleStoreItem@CScrollingStoreScene@@AAEXHHH@Z", 0x268):
        ("table", "ScrollingStoreScene", "?gFurnitureMenuItem@@3PAUsMenuItem@@A", 16, 0,
         "its gFurnitureMenuItem table"),
    **{("?DrawNoFadeScene@theGameMenuDialog@@MAEXXZ", a):
       ("table", "theGameMenuDialog", "?gMenuList@@3PAUsMenuItem@@A", 12, 4, "its gMenuList table")
       for a in (0x85, 0xD5, 0x125, 0x175, 0x1C5, 0x219, 0x26D, 0x2C1)},
    **{(f, a): _FURNITURE for f, a in (
        ("?Draw@CFurnitureManager@@QAEXH@Z", 0x2D), ("?Draw@CFurnitureManager@@QAEXH@Z", 0xD6),
        ("?DrawInStorage@CFurnitureManager@@QAEXHUldwPoint@@_N@Z", 0x2F),
        ("?DrawItem@CFurnitureManager@@QAEXW4EInventoryItem@@UldwRect@@H_NM@Z", 0x22),
        ("?DrawStorage@CFurnitureManager@@QAEXXZ", 0x24B), ("?DropFurniture@CFurnitureManager@@QAEX_N@Z", 0x3B1),
        ("?HandleMouseDown@CFurnitureManager@@QAE_NUldwPoint@@@Z", 0x1E5),
        ("?HavePeepsAdmireFurniture@CFurnitureManager@@AAEXAAUsFurnitureState@1@@Z", 0xAD),
        ("?IsLegalSpot@CFurnitureManager@@AAE_NUldwPoint@@@Z", 0x52),
        ("?LoadFmap@CFurnitureManager@@AAEXW4EInventoryItem@@_N@Z", 0xB5),
        ("?PtOnFurniture@CFurnitureManager@@AAEHUldwPoint@@@Z", 0x46),
        ("?SelectFurniture@CFurnitureManager@@QAEXXZ", 0x4F),
        ("?GetImageGrid@CFurnitureManager@@QAEPAVldwImageGrid@@W4EInventoryItem@@@Z", 0x18),
        ("?HasOrientation@CFurnitureManager@@AAE_NW4EInventoryItem@@H@Z", 0x18))},
    ("?DrawItem@CInventoryManager@@QAEXUldwPoint@@W4EInventoryItem@@W4EInventoryItemState@@W4EInventoryItemPosition@@_N@Z",
     0x13A): ("locals", ["__xmm@0000014e000001510000014b00000149", "__xmm@000001530000014d000001520000014a",
                         "__xmm@0000014c000001500000014f00000148"], [], "its table of service icons"),
    ("?SetupLightSource@CNight@@AAEXPAUSLightSource@1@@Z", 0x93):
        ("locals", ["__xmm@0000025a000002590000025700000256", "__xmm@0000025e0000025d0000025c0000025b"],
         [("mov    dword ptr [ebp - 0x14], 0x25f", 0x25F)], "its table of light masks"),
    ("?Draw@CStory@@QAEXXZ", 0x8A): ("callers", "?AddImage@CStory@@QAE?BHW4EImage@@HHH@Z"),
    ("?Show@CLifeEvent@@SAXPAVldwScene@@W4ELifeEventId@@PBD2@Z", 0x116):
        ("pointers", "LifeEvents", "?lifeEvents@@3PAUsLifeEventTableEntry@@A", 0x18, 0x10, 0x14,
         "its lifeEvents table"),
    ("?GetScaledLinkToNextPt@CAnimManager@@QAE?AUldwPoint@@W4EAnimFrame@@W4EAnimPart@@W4EAnimGender@@HMPAPAVldwImageGrid@@PAH@Z",
     0x33): ("anim", "AnimManager", 0x76F4, ((0xCA4, 32), (0x328, 4))),
    ("?GetScaledLinkToNextPt@CAnimManager@@QAE?AUldwPoint@@W4EHeadDirection@@W4EAnimGender@@HMPAPAVldwImageGrid@@PAH@Z",
     0x2D): ("anim", "AnimManager", 0x34774, ((0x328, 30),)),
    ("?GetScaledLinkToNextPt@CPetAnimManager@@QAE?AUldwPoint@@W4EPetAnimFrame@@W4EPetAnimPart@@HMPAPAVldwImageGrid@@PAH@Z",
     0x2B): ("anim", "PetAnimManager", 0xC6FC, ((0x1D4, 76), (0xE8, 2))),
    **{("?DrawSceneEditAnimation@theAlignVillagerScene@@AAEXXZ", a): ("anim", "AnimManager", off, ())
       for a, off in ((0xA4, 0x76F4), (0xC5, 0x20B74), (0xE6, 0x2C910))},
    **{("?SetupAnimation@theAlignVillagerScene@@AAEXXZ", a): ("anim", "AnimManager", off, ())
       for a, off in ((0x11C, 0x76F4), (0x18F, 0x20B74), (0x1B4, 0x2C910), (0x48C, 0x76F4), (0x4B2, 0x7A1C))},
    **{(f, a): ("anim-any", "AnimManager") for f, a in (
        ("?DrawSceneEditAnimation@theAlignVillagerScene@@AAEXXZ", 0xD2A),
        ("?DrawSceneEditAnimation@theAlignVillagerScene@@AAEXXZ", 0xE17),
        ("?SetupAnimation@theAlignVillagerScene@@AAEXXZ", 0x7CD),
        ("?SetupAnimation@theAlignVillagerScene@@AAEXXZ", 0x80B))},
}
# The animation managers: the global object, its loader and the data files it reads (from the game's Assets).
ANIM_MANAGERS = {"AnimManager": ("?AnimManager@@3VCAnimManager@@A", "?LoadAssets@CAnimManager@@QAEXXZ"),
                 "PetAnimManager": ("?PetAnimManager@@3VCPetAnimManager@@A", "?LoadAssets@CPetAnimManager@@QAEXXZ")}


def _spans(obj, oname: str) -> dict:
    """{section number: [(start, end, [keys])]}: each symbol's span of its section; the bytes before the first symbol
    are the section's own span."""
    per: dict = {}
    for n, v, s, c in obj.symbols.values():
        if s <= 0 or c not in (2, 3):
            continue
        sec = obj.sections[s - 1]
        if n == sec["name"] or (n.startswith(".") and v == 0) or n.startswith("$LN"):
            continue
        per.setdefault(s, {}).setdefault(v, []).append(n if c == 2 else f"{oname}!{n}")
    out = {}
    for s, sec in enumerate(obj.sections, 1):
        if sec["name"].startswith((".debug", ".drectve", ".chks64")):
            continue
        starts = sorted(per.get(s, {}))
        lst = []
        if not starts or starts[0] > 0:
            lst.append((0, starts[0] if starts else sec["size"], [f"{oname}!#{s}"]))
        for k, v in enumerate(starts):
            lst.append((v, starts[k + 1] if k + 1 < len(starts) else sec["size"], per[s][v]))
        out[s] = lst
    return out


def _target(obj, oname, spans, sect, va, sym_index) -> list:
    n, v, s, c = obj.symbols[sym_index]
    if s <= 0:
        return [n]
    tsec = obj.sections[s - 1]
    if c == 3 and v == 0 and (n == tsec["name"] or n.startswith(".")):
        sec = obj.sections[sect - 1]
        addend = struct.unpack_from("<I", obj.data, sec["ptr"] + va)[0]
        hits = [keys for a, e, keys in spans.get(s, []) if a <= addend < e]
        return [k for keys in (hits or [keys for _a, _e, keys in spans.get(s, [])]) for k in keys]
    if n.startswith("$LN"):
        return [k for a, e, keys in spans.get(s, []) if a <= v < e for k in keys]
    return [n if c == 2 else f"{oname}!{n}"]


def call_graph(objs: dict):
    """(functions {key: [(object, section, start, end)]}, edges {key: set}, roots)."""
    funcs, edges, roots = {}, {}, set(ROOTS)
    for oname, obj in objs.items():
        spans = _spans(obj, oname)
        for s, lst in spans.items():
            sec = obj.sections[s - 1]
            code = bool(sec["chars"] & 0x20)
            for a, e, keys in lst:
                for k in keys:
                    if code:
                        funcs.setdefault(k, []).append((oname, s, a, e))
                    if sec["name"].startswith(ROOT_SECTIONS):
                        roots.add(k)
            for va, si, _t in sec["relocs"]:
                src = [keys for a, e, keys in lst if a <= va < e]
                tgt = _target(obj, oname, spans, s, va, si)
                for keys in src:
                    for k in keys:
                        edges.setdefault(k, set()).update(tgt)
    return funcs, edges, roots


def unused_globals(edges: dict) -> dict:
    """The edges with one refinement: a global object that only its own static initializer (and atexit thunk) ever
    names can never have a method called on it, so its constructor's naming of the object's own vtable makes no
    virtual method reachable (the editors' globals: LightSourceEditor, WaypointEditor). The constructor still runs:
    everything else it names stays reachable."""
    named_by: dict = {}
    for k, targets in edges.items():
        for t in targets:
            named_by.setdefault(t, set()).add(k)
    out = dict(edges)
    for init, targets in edges.items():
        if not init.split("!")[-1].startswith("??__E"):
            continue
        objects = [t for t in targets if "@@3" in t and not t.startswith("??__")]
        ctors = [t for t in targets if t.startswith("??0")]
        if len(objects) != 1 or len(ctors) != 1:
            continue
        users = {u for u in named_by.get(objects[0], ()) if not u.split("!")[-1].startswith(("??__E", "??__F"))}
        if users:
            continue
        ctor = ctors[0]
        own_vtable = "??_7" + ctor[3:].split("@@")[0] + "@@6B@"
        out[init] = (targets - {ctor}) | {ctor + "#object never used"}
        out[ctor + "#object never used"] = edges.get(ctor, set()) - {own_vtable}
    return out


def reachable(edges: dict, roots) -> set:
    seen, todo = set(), list(roots)
    while todo:
        n = todo.pop()
        if n not in seen:
            seen.add(n)
            todo.extend(edges.get(n, ()))
    return seen


_MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
_MD.detail = True

REGS = ("eax", "ecx", "edx", "ebx", "esi", "edi")
SUB8 = {"al": "eax", "cl": "ecx", "dl": "edx", "bl": "ebx"}
M32 = 0xFFFFFFFF
CAP = 256
DEPTH = 8


def _s(v):
    return v - (1 << 32) if v & 0x80000000 else v


def cond(m, flags):
    """True/False when the branch condition is known, else None."""
    if flags is None:
        return None
    kind = flags[0]
    if kind == "cmp":
        a, b = flags[1], flags[2]
        if not (isinstance(a, int) and isinstance(b, int)):
            return None
        sa, sb = _s(a), _s(b)
        r = (a - b) & M32
        table = {"je": a == b, "jne": a != b, "jz": a == b, "jnz": a != b, "jl": sa < sb, "jge": sa >= sb,
                 "jg": sa > sb, "jle": sa <= sb, "jb": a < b, "jae": a >= b, "ja": a > b, "jbe": a <= b,
                 "js": bool(r & 0x80000000), "jns": not r & 0x80000000}
    else:                                   # "res": a result compared with zero (test / add / inc / dec / and)
        r = flags[1]
        if not isinstance(r, int):
            return None
        sr = _s(r)
        table = {"je": r == 0, "jne": r != 0, "jz": r == 0, "jnz": r != 0, "js": sr < 0, "jns": sr >= 0,
                 "jl": sr < 0, "jge": sr >= 0, "jg": sr > 0, "jle": sr <= 0}
    key = m
    if m.startswith(("set", "cmov")):
        key = "j" + m[3:] if m.startswith("set") else "j" + m[4:]
    return table.get(key)


class _Walk:
    """Every path through one function: the values pushed at its image-function and WRAPPERS calls."""

    def __init__(self, obj, sect, start, end):
        self.obj = obj
        sec = obj.sections[sect - 1]
        data = obj.data[sec["ptr"] + start:sec["ptr"] + end]
        self.rmap = {}
        self.jt = set()
        for va, si, typ in sec["relocs"]:
            if start <= va < end:
                n, v, s, c = obj.symbols[si]
                self.rmap[va] = n
                if s == sect and typ == 6 and (c == 6 or n.startswith(("$LN", "."))):
                    t = v + struct.unpack_from("<I", obj.data, sec["ptr"] + va)[0]
                    if start <= t < end:
                        self.jt.add(t)
        self.insns = {}
        self.order = []
        for ins in _MD.disasm(data, start):
            self.insns[ins.address] = ins
            self.order.append(ins.address)
        self.is_image = lambda name: bool(IMAGE_CALL.match(name))
        self.wrapper_arg = WRAPPERS.get
        self.get_name = GM_GET

    def refs(self, ins):
        return [self.rmap[x] for x in range(ins.address, ins.address + ins.size) if x in self.rmap]

    def run(self):
        """{(address, callee): set of values}; values are ints, 'p:k' (the function's k-th argument) or None."""
        sites = defaultdict(set)
        if not self.order:
            return sites
        start = ((), (None,) * 6, None, "p:0")
        seen = defaultdict(set)
        work = [(self.order[0], start)]
        seen[self.order[0]].add(start)
        while work:
            a, st = work.pop()
            ins = self.insns.get(a)
            if ins is None:
                continue
            for tgt, nst in self.step(ins, st, sites):
                if tgt == "TABLE":
                    outs = [(t, nst) for t in self.jt]
                else:
                    outs = [(tgt, nst)]
                for t, s2 in outs:
                    if t not in self.insns:
                        continue
                    if len(seen[t]) >= CAP:
                        s2 = widen(s2)
                    if s2 not in seen[t]:
                        seen[t].add(s2)
                        work.append((t, s2))
        for a in self.order:
            ins = self.insns[a]
            if not seen[a] and ins.mnemonic in ("call", "jmp"):
                r = self.refs(ins)
                if r and (self.is_image(r[0]) or self.wrapper_arg(r[0]) is not None):
                    sites[(a, r[0])].add(None)          # code the walk did not reach: unknown
        return sites

    # ------------------------------------------------------------------
    def val(self, ins, op, regs, refs):
        if op.type == x86.X86_OP_IMM:
            return None if refs else op.imm & M32
        if op.type == x86.X86_OP_REG:
            n = ins.reg_name(op.reg)
            return regs[REGS.index(n)] if n in REGS else None
        if op.type == x86.X86_OP_MEM:
            m = op.mem
            if refs or m.index != 0 or m.segment != 0:
                return None
            if ins.reg_name(m.base) == "ebp" and m.disp >= 8 and m.disp % 4 == 0 and op.size == 4:
                return f"p:{(m.disp - 8) // 4}"
        return None

    def step(self, ins, st, sites):
        stack, regs, flags, slot8 = st
        m = ins.mnemonic
        fall = ins.address + ins.size
        refs = self.refs(ins)
        ops = ins.operands
        regs = list(regs)

        def setreg(name, v):
            if name in REGS:
                regs[REGS.index(name)] = v

        def out(nflags=flags, nstack=None, nslot=None):
            return ((stack if nstack is None else nstack), tuple(regs), nflags, (slot8 if nslot is None else nslot))

        if m == "push":
            v = self.val(ins, ops[0], regs, refs)
            return [(fall, out(nstack=(stack + (v,))[-DEPTH:]))]
        if m == "pop":
            if ops[0].type == x86.X86_OP_REG:
                setreg(ins.reg_name(ops[0].reg), stack[-1] if stack else None)
            return [(fall, out(nstack=stack[:-1]))]
        if m in ("call", "jmp") and refs and ops[0].type == x86.X86_OP_IMM:
            callee = refs[0]
            if callee == self.get_name:
                setreg("eax", None)
                return [(fall, out(nflags=None))]
            k = 0 if self.is_image(callee) else self.wrapper_arg(callee)
            if k is not None:
                if m == "jmp":
                    v = slot8 if k == 0 else None
                else:
                    v = stack[-1 - k] if len(stack) > k else None
                sites[(ins.address, callee)].add(v)
            if m == "jmp":
                return []
            for r in ("eax", "ecx", "edx"):
                setreg(r, None)
            return [(fall, ((), tuple(regs), None, slot8))]
        if m == "call":
            for r in ("eax", "ecx", "edx"):
                setreg(r, None)
            return [(fall, ((), tuple(regs), None, slot8))]
        if m in ("ret", "int3", "ud2"):
            return []
        if m == "jmp":
            if ops[0].type == x86.X86_OP_IMM:
                return [(ops[0].imm, out())]
            return [("TABLE", out())]
        if m.startswith("j") or m.startswith("loop"):
            c = cond(m, flags) if not m.startswith("loop") else None
            if c is True:
                return [(ops[0].imm, out())]
            if c is False:
                return [(fall, out())]
            taken, fell = out(), out()
            if flags and flags[0] == "cmp" and len(flags) > 3 and flags[3] in REGS and isinstance(flags[2], int)                     and m in ("je", "jne"):
                rr = list(regs)
                rr[REGS.index(flags[3])] = flags[2]
                eq = (stack, tuple(rr), flags, slot8)
                if m == "je":
                    taken = eq
                else:
                    fell = eq
            return [(fall, fell), (ops[0].imm, taken)]
        # data instructions
        dst = ops[0] if ops else None
        dreg = ins.reg_name(dst.reg) if dst is not None and dst.type == x86.X86_OP_REG else None
        if m == "mov" and dst is not None and dst.type == x86.X86_OP_MEM:
            mm = dst.mem
            base = ins.reg_name(mm.base) if mm.base else None
            v = self.val(ins, ops[1], regs, refs)
            if base == "esp" and mm.disp == 0 and mm.index == 0 and stack:
                return [(fall, out(nstack=stack[:-1] + (v,)))]
            if base == "ebp" and mm.disp == 8 and mm.index == 0:
                return [(fall, out(nslot=v))]
            return [(fall, out())]
        # everything else: compute what we model, clobber what it writes
        try:
            _r, written = ins.regs_access()
            written = {ins.reg_name(w) for w in written}
        except capstone.CsError:
            written = set(REGS)
        new = {}
        nflags = None if "eflags" in written or "flags" in written else flags
        if m == "mov" and dreg in REGS:
            new[dreg] = self.val(ins, ops[1], regs, refs)
        elif m == "xor" and dreg in REGS and ops[1].type == x86.X86_OP_REG and ins.reg_name(ops[1].reg) == dreg:
            new[dreg] = 0
            nflags = ("res", 0)
        elif m in ("add", "sub", "and", "or", "shl") and dreg in REGS:
            a = regs[REGS.index(dreg)]
            b = self.val(ins, ops[1], regs, refs)
            if isinstance(a, int) and isinstance(b, int):
                r = {"add": a + b, "sub": a - b, "and": a & b, "or": a | b, "shl": a << (b & 31)}[m] & M32
                new[dreg] = r
                nflags = ("cmp", a, b) if m == "sub" else ("res", r)
            else:
                new[dreg] = None
                nflags = None
        elif m in ("inc", "dec", "neg") and dreg in REGS:
            a = regs[REGS.index(dreg)]
            r = ({"inc": a + 1, "dec": a - 1, "neg": -a}[m] & M32) if isinstance(a, int) else None
            new[dreg] = r
            nflags = ("res", r)
        elif m == "lea" and dreg in REGS:
            mm = ops[1].mem
            v = None
            if not refs and mm.segment == 0:
                b = 0 if mm.base == 0 else regs[REGS.index(ins.reg_name(mm.base))] if ins.reg_name(mm.base) in REGS else None
                i = 0 if mm.index == 0 else regs[REGS.index(ins.reg_name(mm.index))] if ins.reg_name(mm.index) in REGS else None
                if isinstance(b, int) and isinstance(i, int):
                    v = (b + i * mm.scale + mm.disp) & M32
            new[dreg] = v
        elif m == "cmp":
            nflags = ("cmp", self.val(ins, ops[0], regs, refs), self.val(ins, ops[1], regs, refs),
                      ins.reg_name(ops[0].reg) if ops[0].type == x86.X86_OP_REG else None)
        elif m == "test":
            a, b = self.val(ins, ops[0], regs, refs), self.val(ins, ops[1], regs, refs)
            nflags = ("res", a & b if isinstance(a, int) and isinstance(b, int) else None)
        elif m.startswith("set") and dst is not None and dst.type == x86.X86_OP_REG:
            full = SUB8.get(ins.reg_name(dst.reg))
            if full and regs[REGS.index(full)] == 0:
                c = cond(m, flags)
                outs = []
                for bit in ((0, 1) if c is None else (int(c),)):
                    rr = list(regs)
                    rr[REGS.index(full)] = bit
                    outs.append((fall, (stack, tuple(rr), flags, slot8)))
                return outs
        elif m.startswith("cmov") and dreg in REGS:
            c = cond(m, flags)
            nv = self.val(ins, ops[1], regs, refs)
            ov = regs[REGS.index(dreg)]
            choices = (ov, nv) if c is None else ((nv,) if c else (ov,))
            outs = []
            for ch in choices:
                rr = list(regs)
                rr[REGS.index(dreg)] = ch
                outs.append((fall, (stack, tuple(rr), flags, slot8)))
            return outs
        for w in written:
            if w in REGS and w not in new:
                regs[REGS.index(w)] = None
            elif w in ("al", "cl", "dl", "bl", "ax", "cx", "dx", "bx", "si", "di", "ah", "ch", "dh", "bh"):
                full = {"a": "eax", "c": "ecx", "d": "edx", "b": "ebx", "s": "esi"}.get(w[0])
                if w in ("si", "di"):
                    full = "e" + w
                if full in REGS and full not in new:
                    regs[REGS.index(full)] = None
        for k, v in new.items():
            regs[REGS.index(k)] = v
        if "esp" in written and m not in ("sub", "add"):
            stack = ()
        return [(fall, (stack, tuple(regs), nflags, slot8))]


def widen(st):
    stack, regs, flags, slot8 = st
    w = lambda v: v if isinstance(v, str) else None
    return (tuple(w(v) for v in stack), tuple(w(v) for v in regs), None, w(slot8))


def call_sites(objs: dict, funcs: dict) -> list:
    """[(function key, call address, callee, {values})] for every call of an image function or a WRAPPERS function."""
    out, done = [], set()
    for key, places in sorted(funcs.items()):
        for oname, s, a, e in places:
            obj = objs[oname]
            sec = obj.sections[s - 1]
            names = {obj.symbols[si][0] for va, si, _t in sec["relocs"] if a <= va < e}
            if (oname, s, a) in done or not any(IMAGE_CALL.match(n) or n in WRAPPERS for n in names):
                continue
            done.add((oname, s, a))
            walk = _Walk(obj, s, a, e)
            for (addr, callee), vals in sorted(walk.run().items()):
                out.append((key, addr, callee, vals))
    return out


def _check_wrappers(objs: dict) -> None:
    takes = {n for obj in objs.values() for n, _v, s, c in obj.symbols.values()
             if s > 0 and c == 2 and "W4EImage@@" in n and not n.startswith(("__", "?Get@", "?$"))
             and "@theGraphicsManager@@" not in n and obj.sections[s - 1]["chars"] & 0x20}
    if takes != set(WRAPPERS):
        raise SystemExit(f"functions taking an EImage changed: {sorted(takes ^ set(WRAPPERS))}")


def _symbol_bytes(obj, name: str):
    """(bytes from the symbol to the next symbol of its section, {offset: relocated symbol name})."""
    for n, v, s, c in obj.symbols.values():
        if n == name and s > 0:
            sec = obj.sections[s - 1]
            nxt = min([v2 for n2, v2, s2, c2 in obj.symbols.values() if s2 == s and v2 > v and c2 in (2, 3)
                       and not n2.startswith("$")] + [sec["size"]])
            relocs = {va - v: obj.symbols[si][0] for va, si, _t in sec["relocs"] if v <= va < nxt}
            return obj.data[sec["ptr"] + v:sec["ptr"] + nxt], relocs
    raise SystemExit(f"no symbol {name}")


def _xmm(name: str) -> list:
    hexs = name.split("@")[1]
    return [int(hexs[k:k + 8], 16) for k in range(24, -1, -8)]


def _emulate_manager(objects: Path, game: Path, which: str):
    """The animation manager object after its LoadAssets has read the game's data files: (bytes, ids it passed)."""
    from vf2_people_emu import CoffObject, Emu
    symbol, loader = ANIM_MANAGERS[which]
    obj = CoffObject(Path(objects) / f"{which}.obj")
    size = next(obj.sections[s - 1]["size"] - v for n, v, s, c in obj.symbols.values() if n == symbol)
    e = Emu(Path(objects), [which])
    asked, files = [], {}

    def fopen(em):
        files[len(files) + 1] = [(game / "Assets" / em.cstr(em.arg(0))).read_bytes(), 0]
        return len(files), 0

    def fread(em):
        buf, size_, count, h = em.arg(0), em.arg(1), em.arg(2), em.arg(3)
        data, at = files[h]
        chunk = data[at:at + size_ * count]
        files[h][1] += len(chunk)
        em.write(buf, chunk)
        return len(chunk) // max(size_, 1), 0

    def grid(em):
        asked.append(em.arg(0))
        return em.alloc(16), 4

    state, vtable = e.alloc(16), e.alloc(16)
    e.w32(state, vtable)
    e.w32(vtable + 8, e._external("?FullPath@ldwGameState@@virtual", 0x14))   # the path of an Assets file
    e.seam("?FullPath@ldwGameState@@virtual", lambda em: (em.arg(0), 4))
    e.seam("?Get@ldwGameState@@SAPAV1@XZ", lambda em: (state, 0))
    e.seam(GM_GET, lambda em: (0x7000, 0))
    e.seam("?GetImageGrid@theGraphicsManager@@QAEPAVldwImageGrid@@W4EImage@@@Z", grid)
    e.seam("?GetCellRect@ldwImageGrid@@QAEXHHAAUldwRect@@@Z",    # any non-empty cell (sizes only scale points)
           lambda em: (em.write(em.arg(2), struct.pack("<4i", 0, 0, 100, 100)), (0, 12))[1])
    e.seam("_fopen", fopen)
    e.seam("_fread", fread)
    e.seam("_fclose", lambda em: (0, 0))
    this = e.addr(symbol)                                   # the loader also writes the global by name
    e.call(loader, ecx=this)
    if len(files) == 0:
        raise SystemExit(f"{loader} read no data file")
    return e.read(this, size), asked


def _resolve(rule, objs, objects, game, managers, wrapper_values, table_ids, code_text):
    """(exact ids, bound ids, how) for one SITE_RULES entry."""
    kind = rule[0]
    if kind == "table":
        _k, oname, sym, stride, field, words = rule
        data, _rel = _symbol_bytes(objs[oname], sym)
        ids = {struct.unpack_from("<I", data, at + field)[0] for at in range(0, len(data) - stride + 1, stride)}
        ids &= table_ids
        return ids, ids, words
    if kind == "pointers":
        _k, oname, sym, stride, pfield, cfield, words = rule
        obj = objs[oname]
        data, rel = _symbol_bytes(obj, sym)
        ids = set()
        for at in range(0, len(data) - stride + 1, stride):
            count = struct.unpack_from("<I", data, at + cfield)[0]
            arr, _r = _symbol_bytes(obj, rel[at + pfield])
            ids |= set(struct.unpack_from(f"<{count}I", arr, struct.unpack_from("<I", data, at + pfield)[0]))
        ids &= table_ids
        return ids, ids, words
    if kind == "locals":
        _k, xmms, extra, words = rule
        ids = {v for x in xmms for v in _xmm(x)}
        for text, value in extra:
            if text not in code_text:
                raise SystemExit(f"the code no longer stores {value:#x}: {text}")
            ids.add(value)
        ids &= table_ids
        return ids, ids, words
    if kind == "callers":
        ids = wrapper_values[rule[1]] & table_ids
        return ids, ids, "the pictures given to " + _pretty(rule[1])
    if kind == "anim":
        _k, which, base, strides = rule
        mem, _asked = managers[which]
        offsets = {base}
        for stride, count in strides:
            offsets = {o + k * stride for o in offsets for k in range(count)}
        ids = {struct.unpack_from("<I", mem, o)[0] for o in offsets if o + 4 <= len(mem)} & table_ids
        return ids, ids, f"the animation records {_pretty(ANIM_MANAGERS[which][1]).split('::')[0]}::LoadAssets " \
                         "loads from the game's data files"
    if kind == "anim-any":
        mem, _asked = managers[rule[1]]
        ids = set(struct.unpack_from(f"<{len(mem) // 4}I", mem)) & table_ids
        return set(), ids, "any id the animation records hold"
    raise SystemExit(f"unknown rule {rule}")


def _pretty(name: str) -> str:
    """Class::Method from a mangled name."""
    name = name.split("!")[-1]
    if name.startswith(("??0", "??1")):
        cls = name[3:].split("@@")[0].split("@")[0]
        return f"{cls}::{'~' if name[2] == '1' else ''}{cls}"
    if name.startswith("?"):
        parts = name[1:].split("@@")[0].split("@")
        return "::".join(reversed(parts[1:])) + ("::" if len(parts) > 1 else "") + parts[0]
    return name.lstrip("_").split("@")[0]


def _names(fns) -> str:
    names = sorted({_pretty(f) for f in fns})
    if len(names) > 4:
        names = names[:4] + [f"{len(names) - 4} more"]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def image_usage(objects: Path, table: list, game: Path | None = None):
    """({id: [used, why]}, {"id:cell": why unused}, {"id:cell": label})."""
    from vf2_people_emu import CoffObject
    game = Path(game or __import__("os").environ.get("VF2_VANILLA_GAME_DIR") or REPO / "work" / "vanilla_runtime_payload")
    objs = {p.stem: CoffObject(p) for p in sorted(Path(objects).glob("*.obj"))}
    _check_wrappers(objs)
    table_ids = {e["id"] for e in table if e["id"] != 0}         # 0: "No Graphic", the empty slot
    funcs, edges, roots = call_graph(objs)
    live = reachable(unused_globals(edges), roots)
    sites = call_sites(objs, funcs)
    managers = {w: _emulate_manager(objects, game, w) for w in ANIM_MANAGERS}
    # the arguments a function receives: every reachable call's values (after following its own arguments)
    calls = {}
    for fn, addr, callee, vals in sites:
        if fn in live and callee in WRAPPERS:
            calls.setdefault(callee, []).append((fn, addr, vals))
    matched = set()

    def resolve(fn, addr):
        matched.add((fn, addr))
        return _resolve(SITE_RULES[(fn, addr)], objs, objects, game, managers, wrapper_values, table_ids,
                        _code_text(objs, funcs, fn))

    def passed(fn, k, seen=()):
        """{id: {(asker, through)}} a function's k-th argument can be, from its reachable callers."""
        out = {}
        if fn not in WRAPPERS or WRAPPERS[fn] != k or fn in seen:
            raise SystemExit(f"{fn}: argument {k} is not an EImage it hands on")
        for caller, addr, vals in calls.get(fn, []):
            for v in vals:
                if isinstance(v, int):
                    out.setdefault(v, set()).add((caller, fn))
                elif isinstance(v, str) and caller in WRAPPERS:
                    for i, who in passed(caller, int(v[2:]), seen + (fn,)).items():
                        out.setdefault(i, set()).update(who)
                elif (caller, addr) in SITE_RULES:
                    for i in resolve(caller, addr)[0]:
                        out.setdefault(i, set()).add((caller, fn))
                else:
                    raise SystemExit(f"{caller} at {addr:#x}: the id it gives {fn} is not resolved")
        return out

    wrapper_values = {}
    wrapper_values.update({w: set(passed(w, k)) for w, k in WRAPPERS.items()})
    asked, bound, dead_askers = {}, set(), {}
    for fn, addr, callee, vals in sites:
        if callee in WRAPPERS and not IMAGE_CALL.match(callee):
            continue                                    # counted where the wrapper hands the id on
        rule = SITE_RULES.get((fn, addr))
        exact = {v for v in vals if isinstance(v, int)} & table_ids
        via = {}
        for v in vals:
            if isinstance(v, str) and fn in WRAPPERS:
                via.update(passed(fn, int(v[2:])))
        loose = set()
        if rule:
            r_exact, r_bound, how = resolve(fn, addr)
            for i in r_exact:
                asked.setdefault(i, set()).add((fn, how))
            loose = r_bound
        elif any(not isinstance(v, int) and not (isinstance(v, str) and fn in WRAPPERS) for v in vals) \
                and fn in live:
            raise SystemExit(f"{fn} at {addr:#x}: the id it passes {callee} is not resolved (add a SITE_RULES entry)")
        if fn not in live:
            for i in exact | loose:
                dead_askers.setdefault(i, set()).add(fn)
            continue
        for i in exact:
            asked.setdefault(i, set()).add((fn, None))
        for i, who in via.items():
            for caller, wrapper in who:
                asked.setdefault(i, set()).add((caller, "through " + _pretty(wrapper)))
        bound |= exact | loose | set(via)
    missing = set(SITE_RULES) - matched
    if missing:
        raise SystemExit(f"SITE_RULES entries that match no call: {sorted(missing)}")
    usage = {}
    for i in sorted(table_ids):
        if i in asked:
            groups = {}
            for f, how in asked[i]:
                groups.setdefault(how, set()).add(f)
            bits = []
            for how in sorted(groups, key=lambda h: (h is not None, h or "")):
                lead = "Asked for by" if not bits else "Also by"
                if how is None:
                    bits.append(f"{lead} {_names(groups[how])}.")
                elif how.startswith("through "):
                    bits.append(f"{lead} {_names(groups[how])}, {how}.")
                else:
                    bits.append(f"{lead} {_names(groups[how])}, from {how}.")
            usage[str(i)] = [True, " ".join(bits)]
        elif i not in bound:
            if i in dead_askers:
                who = _names(dead_askers[i])
                usage[str(i)] = [False, f"Only {who} asks for it, and no code reached from WinMain calls "
                                        f"{'it' if len(dead_askers[i]) == 1 else 'them'}."]
            else:
                usage[str(i)] = [False, "No code asks theGraphicsManager for it: no call passes its id, and no table "
                                        "or computed id the code reads can be it."]
    return usage, *cell_facts(table, usage)


def _code_text(objs, funcs, fn) -> str:
    out = []
    for oname, s, a, e in funcs.get(fn, []):
        obj = objs[oname]
        sec = obj.sections[s - 1]
        for ins in _MD.disasm(obj.data[sec["ptr"] + a:sec["ptr"] + e], a):
            out.append(f"{ins.mnemonic:6} {ins.op_str}")
    return "\n".join(out)


def cell_facts(table: list, usage: dict):
    """Single cells no code draws, and what cells show, where the code says so (CELL_FACTS)."""
    unused, labels = {}, {}
    for (i, cell), text in CELL_UNUSED.items():
        unused[f"{i}:{cell}"] = text
    for (i, cell), text in CELL_LABELS.items():
        labels[f"{i}:{cell}"] = text
    return unused, labels


CELL_UNUSED: dict = {}
CELL_LABELS: dict = {}


def build(objects: Path) -> dict:
    table = image_table(objects)
    clean = json.loads(CLEAN.read_text(encoding="utf-8"))["files"]
    stock = {k[len("Images/"):]: [v["size"], v["sha256"]] for k, v in sorted(clean.items()) if k.startswith("Images/")}
    named = table_files(table)
    strings = _strings(objects)
    patterns = []                                           # printf patterns that make file names
    for text in strings:
        if "%" in text and "." in text:
            last = re.split(r"[\\/]", text)[-1]
            rx = "^" + re.sub(r"%0?\d*d", r"\\d+", re.escape(last).replace("%s", ".*")) + "$"
            patterns.append((re.compile(rx), text))
    in_code, unused = {}, []
    for name in stock:
        if name.lower() in named or name.lower().endswith(NOT_PICTURES):
            continue
        base = name.split("/")[-1].lower()
        stem = base.rsplit(".", 1)[0]
        where = set()
        for text, objs in strings.items():
            if text.endswith(base) or text.endswith(stem) and len(stem) >= 5:
                where |= objs
        for rx, text in patterns:
            if rx.search(base):
                where |= strings[text]
        if where:
            in_code[name] = sorted(where)
        else:
            unused.append(name)
    usage, cell_unused, cell_labels = image_usage(objects, table)
    return {"made_by": "scripts/build_vf2_image_table.py: theGraphicsManager's ImageList and the strings of the "
                       "B200 desktop objects; the stock files from data/vf2/clean-base-game-assets.json",
            "table": table, "named_in_code": in_code, "unused": unused, "usage": usage,
            "cell_unused": cell_unused, "cell_labels": cell_labels, "stock": stock}


def render(data: dict) -> str:
    lines = ["{", f'  "made_by": {json.dumps(data["made_by"])},', '  "table": [']
    for k, entry in enumerate(data["table"]):
        lines.append("    " + json.dumps(entry) + ("," if k < len(data["table"]) - 1 else ""))
    lines.append("  ],")
    lines.append(f'  "named_in_code": {json.dumps(data["named_in_code"], indent=None)},')
    lines.append(f'  "unused": {json.dumps(data["unused"])},')
    for name in ("usage", "cell_unused", "cell_labels"):
        items = list(data[name].items())
        lines.append(f'  "{name}": {{')
        for k, (key, value) in enumerate(items):
            lines.append(f"    {json.dumps(key)}: {json.dumps(value)}" + ("," if k < len(items) - 1 else ""))
        lines.append("  },")
    lines.append('  "stock": {')
    keys = list(data["stock"])
    for k, key in enumerate(keys):
        lines.append(f"    {json.dumps(key)}: {json.dumps(data['stock'][key])}" + ("," if k < len(keys) - 1 else ""))
    lines += ["  }", "}"]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--objects", default=str(REPO / "work" / "desktop_obj_files"))
    args = parser.parse_args(argv)
    text = render(build(Path(args.objects)))
    for path in OUTPUTS:
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {path} ({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
