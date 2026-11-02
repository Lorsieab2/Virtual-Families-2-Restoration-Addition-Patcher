"""Game Mechanics: the "Hidden keys, clicks and cheats" group, pinned to the game's own code.

The page tests always run.  The code tests read the B200 desktop object files (work/desktop_obj_files, gitignored,
or VF2_DESKTOP_OBJ_DIR; they keep their symbols) and the stock executable (work/vanilla_runtime_payload, or
VF2_STOCK_EXE, sha256 1582d9e8...); each is skipped when its input is absent.  Nothing starts the game and nothing
on disk is written.
"""
from __future__ import annotations

import hashlib
import os
import re
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vf2_game_mechanics as gm  # noqa: E402

FACTS = gm.facts()
TEXT = gm.render(FACTS)
HIDDEN = [f for f in FACTS if f.group == gm.HIDDEN]
OBJ_DIR = Path(os.environ.get("VF2_DESKTOP_OBJ_DIR") or ROOT / "work" / "desktop_obj_files")
STOCK_EXE = Path(os.environ.get("VF2_STOCK_EXE") or ROOT / "work" / "vanilla_runtime_payload" / "Virtual Families 2.exe")


def _line(start):
    found = [f for f in HIDDEN if f.text.startswith(start)]
    assert len(found) == 1, (start, len(found))
    return found[0]


# ---------------------------------------------------------------------------------------------------------- the page
def test_the_group_comes_right_after_time_and_ageing():
    assert gm.GROUPS[:2] == (gm.TIME, gm.HIDDEN) and gm.HIDDEN == "Hidden keys, clicks and cheats"
    assert FACTS[0].text.startswith("Clocks.")       # the clocks the durations below name stay first


def test_every_house_key_is_given():
    for needle in ("Space: pauses the game", "1 to 9: move the view to one of 9 fixed places",
                   "S: opens the store at its menu", "D: does what the Details button does", "C: the Collections",
                   "F: the Family screen", "T: the Goals screen", "Esc: the game menu", "M and P are taken and do nothing"):
        assert needle in TEXT, needle


def test_the_screens_where_esc_does_more_than_leave():
    assert "Esc adopts the person shown, exactly as the Adopt button does" in _line("The adoption screen").text
    assert "Esc accepts, as the accept button does" in _line("The dating screen").text
    assert "Enter and Esc both cancel" in _line("Dialog boxes").text


def test_the_store_corner_and_the_codes():
    corner = _line("The store's hidden Redeem Credit corner")
    for needle in ("x 972 to 1,024 and y 0 to 51", "more than 5 seconds of game time", "never while paused"):
        assert needle in corner.text
    codes = _line("The code is sent to LDW's server")
    # LDW's server now answers with its scripts' source (the owner's crash dumps, 2026-10-31), so the page no
    # longer says it was not traced; tests/test_server_reply_guard.py covers the startup lines.
    assert "no code is kept in the game" in codes.text and "no longer runs its scripts" in codes.text
    none = _line("The store scenes handle no hidden keys.")      # VF2's store has no redraw key (only Esc)
    assert "No key or key combination redraws the On Sale items or the Flea Market's goods" in none.text


def test_dead_code_is_marked_and_never_a_player_action():
    dead = [f for f in HIDDEN if f.text.startswith("Dead code, never a player action")]
    assert len(dead) == 4
    joined = " ".join(f.text for f in dead)
    for needle in ("F then W", "tips 31 to 60", "Settings box's own Redeem Credit", "F5 (show the debugger)"):
        assert needle in joined


def test_every_random_tip_is_listed_once_and_in_short():
    assert len(gm.RANDOM_TIPS) == 60
    tips = [f for f in HIDDEN if re.match(r"Tip \d+: ", f.text)]
    assert [int(f.text.split()[1].rstrip(":")) for f in tips] == list(range(1, 61))
    assert "each 1 in 30" in _line("Random tips: the loading screen").text


def test_the_house_click_spots():
    for spot, _does, _evidence in gm.CLICK_SPOTS:
        assert any(f.text.startswith(spot + ": ") for f in HIDDEN), spot
    assert len(gm.CLICK_SPOTS) == 16


def test_the_patcher_adds_one_key():
    line = _line("The patcher adds R in the store, the copy and paste keys in text boxes, and no hidden click")
    clip = _line("Ctrl+V, Shift+Insert, Ctrl+C, Ctrl+Insert, Ctrl+X (patcher keys")
    assert clip.sub and clip.label == gm.VERIFIED_E and "Copy and Paste in Text Boxes" in clip.text
    assert "Windows-1252" in clip.text and "never reach the game as letters" in clip.text
    assert "Time Controls" in line.text and "Settings screen" in line.text
    r = _line("R (a patcher key")
    assert r.sub and r.label == gm.VERIFIED_E
    for needle in (gm.OPTION_REFRESH, "on by default", "Shift+R", "Clothing and Hairstyles", "Flea Market",
                   "goods, always; with \"All 36 Flea Market goods\" on you won't see a change", "never On Sale", "while a box",
                   "Esc included, is the game's own"):
        assert needle in r.text, needle
    for needle in ("vtable slot 2", "RTTI", "HandleKey(5, char, 0)", "SetModal"):
        assert needle in r.evidence, needle
    # the stock store line still says the unpatched store has no such key
    assert "The patcher's R is listed below" in _line("The store scenes handle no hidden keys.").text


def test_the_r_key_lines_in_the_store_and_the_clothing_tab():
    clothing = [f for f in FACTS if f.group == gm.CLOTHING and f.text.startswith(f"Patcher option \"{gm.OPTION_REFRESH}\"")]
    assert len(clothing) == 1 and clothing[0].label == gm.VERIFIED_E
    assert "Discount 0 to 31, Department 32 to 43, Designer 44 to 49" in clothing[0].text
    assert "hairstyles are not picked at random" in clothing[0].text and "MaybeUpdateOutfits(true)" in clothing[0].evidence
    store = [f for f in FACTS if f.group == gm.STORE and f.text.startswith(f"Patcher option \"{gm.OPTION_REFRESH}\"")]
    assert len(store) == 1 and "R always redraws" in store[0].text and "+4A0h = 0" in store[0].evidence
    assert "MaybeUpdateRotatingItems called directly" in store[0].evidence and "does nothing there" not in store[0].text
    flea = [f for f in FACTS if f.group == gm.STORE and f.text.startswith(f"Patcher option \"{gm.OPTION_FLEA}\"")]
    assert len(flea) == 1 and "all 36 goods are always in stock" in flea[0].text
    for needle in ("Towelette", "Anti-spam Software", "Rockhound Certificate", "go to the tray again",
                   "stays owned", "no goal counts", "keeps its checkmark"):
        assert needle in flea[0].text, needle
    assert "sold out" not in flea[0].text.split("always in stock")[0], "the old warning came back"


# ------------------------------------------------------------------------------------------------- the object files
class Obj:
    """A COFF object: functions by symbol, their bytes, relocations and labels."""

    def __init__(self, name):
        path = OBJ_DIR / name
        if not path.is_file():
            pytest.skip(f"the desktop object files (work/desktop_obj_files or VF2_DESKTOP_OBJ_DIR) are not present")
        b = self.b = path.read_bytes()
        _m, nsec, _t, symptr, nsym, opt, _c = struct.unpack_from("<HHIIIHH", b, 0)
        self.secs = [struct.unpack_from("<8sIIIIIIHHI", b, 20 + opt + 40 * i) for i in range(nsec)]
        strtab = b[symptr + nsym * 18:]
        self.syms, i = {}, 0
        while i < nsym:
            raw = b[symptr + 18 * i:symptr + 18 * i + 8]
            if raw[:4] == b"\0\0\0\0":
                off = struct.unpack_from("<I", raw, 4)[0]
                name = strtab[off:strtab.index(b"\0", off)].decode("latin-1")
            else:
                name = raw.split(b"\0")[0].decode("latin-1")
            value, sec, _ty, _cl, aux = struct.unpack_from("<IhHBB", b, symptr + 18 * i + 8)
            self.syms[i] = (name, value, sec)
            i += 1 + aux
        self.by_name = {}
        for name, value, sec in self.syms.values():
            self.by_name.setdefault(name, (value, sec))

    def section(self, sec):
        _n, _vs, _va, size, ptr, rptr, _l, nrel, _nl, _ch = self.secs[sec - 1]
        rel = {}
        for k in range(nrel):
            va, si, _typ = struct.unpack_from("<IIH", self.b, rptr + 10 * k)
            rel[va] = self.syms.get(si, ("?", 0, 0))[0]
        return self.b[ptr:ptr + size], rel

    def func(self, prefix):
        hits = [(n, v, s) for n, v, s in self.syms.values() if n.startswith(prefix) and s > 0]
        assert len({(v, s) for _n, v, s in hits}) == 1, (prefix, hits)
        name, value, sec = hits[0]
        data, rel = self.section(sec)
        labels = {n: v for n, v, s in self.syms.values() if s == sec and n.startswith("$LN")}
        return data, value, rel, labels

    def references(self, target):
        """Every relocation in any code section of this object that points at a symbol starting with target."""
        out = []
        for idx, sec in enumerate(self.secs, 1):
            if sec[0].startswith(b".text"):
                out += [n for n in self.section(idx)[1].values() if n.startswith(target)]
        return out


def _table(data, labels, rel, byte_table, dword_table, count):
    """index -> target label of a two-level MSVC switch (byte index table, then a table of label addresses)."""
    names = {v: n for n, v in labels.items()}
    out = []
    for i in range(count):
        k = data[labels[byte_table] + i] if byte_table else i
        out.append(rel[labels[dword_table] + 4 * k])
    return out, names


def test_the_sdl_key_translation():
    o = Obj("ldwGameWindow.obj")
    data, _start, rel, labels = o.func("?CheckForEvents@ldwGameWindowImpl@@")

    def code(label):            # each case is "mov eax, imm32" -> the scene key code
        at = labels[label]
        assert data[at] == 0xB8, label
        return struct.unpack_from("<I", data, at + 1)[0]
    low, _ = _table(data, labels, rel, "$LN76", "$LN80", 0x78)          # SDL keycodes 8..0x7F
    assert low[0] == "$LN74"                                            # Backspace -> the typed character 8
    assert {0x09: code(low[1]), 0x0D: code(low[5]), 0x1B: code(low[0x13]), 0x7F: code(low[0x77])} == {
        0x09: 0x3EA, 0x0D: 0x3EB, 0x1B: 0x3E8, 0x7F: 0x3F5}
    assert set(low) - {"$LN74", low[1], low[5], low[0x13], low[0x77]} == {"$LN55"}     # every other key: nothing
    high, _ = _table(data, labels, rel, None, "$LN81", 0x18)            # SDL keycodes 0x4000003B..0x40000052
    f2_f10 = [code(high[i]) for i in (0, 1, 3, 4, 5, 6, 7, 8)]          # F2, F3, F5..F10 (F4 is the Alt check)
    assert f2_f10 == [0x3FB, 0x3FC, 0x3FE, 0x3FF, 0x400, 0x401, 0x402, 0x403]
    assert high[9:14] == ["$LN55"] * 5                                  # F11, F12, Print Screen, Scroll Lock, Pause
    assert [code(high[i]) for i in (14, 15, 16, 18, 19, 20, 21, 22, 23)] == [
        0x3F4, 0x3F2, 0x3F0, 0x3F3, 0x3F1, 0x3ED, 0x3EC, 0x3EF, 0x3EE]   # Insert Home PgUp End PgDn Right Left Down Up
    f4 = data[labels[high[2]]:labels[high[2]] + 20]
    assert f4.startswith(bytes.fromhex("f745dc00030000")) and struct.pack("<I", 0x3FD) in f4   # Alt+F4 quits
    assert bytes.fromhex("b8fa030000") in data                          # F1 (SDL 0x4000003A) -> 0x3FA
    assert bytes.fromhex("6a08526a05") in data                          # Backspace -> HandleKey(5, 8, 8)
    assert bytes.fromhex("506a006a05") in data                          # a one-byte text input -> HandleKey(5, c, 0)


def test_the_house_keys():
    o = Obj("theMainScene.obj")
    data, start, rel, labels = o.func("?HandleKeyCharacter@theMainScene@@")
    chars, _ = _table(data, labels, rel, "$LN67", "$LN69", 0x58)
    by = {}
    for i, label in enumerate(chars):
        by.setdefault(label, []).append(chr(0x20 + i))
    groups = {"".join(v) for k, v in by.items() if len(v) < 20}
    assert {" ", "1", "2", "3", "4", "5", "6", "7", "8", "9", "Cc", "Dd", "Ff", "MPmp", "Ss", "Tt", "Ww"} <= groups

    def body(ch):
        label = chars[ord(ch) - 0x20]
        ends = sorted(v for v in labels.values() if v > labels[label])
        return data[labels[label]:ends[0] if ends else len(data)]
    scroll = {"1": (-40, 0x582), "2": (0x208, 0x582), "3": (0x4E2, 0x582), "4": (-40, 0x33B), "5": (0x208, 0x33B),
              "6": (0x4E2, 0x33B), "7": (-40, 0x32), "8": (0x21C, 0x32), "9": (0x4D8, 0x32)}
    for ch, (x, y) in scroll.items():
        push_y = (b"\x6a" + struct.pack("<b", y)) if -128 <= y < 128 else b"\x68" + struct.pack("<i", y)
        push_x = (b"\x6a" + struct.pack("<b", x)) if -128 <= x < 128 else b"\x68" + struct.pack("<i", x)
        assert push_y + push_x in body(ch), ch
    for ch, msg in {"S": 3, "D": 1, "C": 4, "F": 7, "T": 8}.items():
        assert bytes([0x6A, msg, 0x6A, 0x08, 0xFF, 0x50, 0x0C]) in body(ch), ch
    assert body("M").startswith(b"\xb0\x01")                            # M / P: mov al, 1 and nothing else
    space = body(" ")
    assert struct.pack("<I", 0x25B18) in space and struct.pack("<I", 0x3E7) in space
    down, *_ = o.func("?HandleKeyDown@theMainScene@@")
    assert bytes.fromhex("817d08e8030000") in down and bytes.fromhex("6a006a08ff500c") in down   # Esc -> message 0
    # the F/W counter +0x50: F sets it 0 <-> 1, W 1 -> 2, the other keys 0 (it is read nowhere else)
    assert bytes.fromhex("394750") in body("F") and bytes.fromhex("894750") in body("F")
    assert bytes.fromhex("837f5001") in body("W")
    assert bytes.fromhex("c7475000000000") in body("!")


def test_the_house_key_messages_open_the_screens():
    o = Obj("theMainScene.obj")
    data, start, rel, labels = o.func("?HandleMessage@theMainScene@@")
    cases, _ = _table(data, labels, rel, None, "$LN23", 10)
    calls = {}
    for i, label in enumerate(cases):
        at = labels[label]
        calls[i] = [n for off, n in rel.items() if at <= off < at + 0x40 and n.startswith("?")]
    assert any(n.startswith("??0theGameMenuDialog") for n in calls[0])
    assert any(n.startswith("?HandleVillagerDetailsButton") for n in calls[1])
    assert any(n.startswith("?SetStoreCategory") for n in calls[3])


def test_esc_on_the_adoption_and_dating_screens_is_their_first_button():
    for obj, cls in (("AdoptionScene.obj", "CAdoptionScene"), ("DatingScene.obj", "CDatingScene"),
                     ("ScrollingStoreScene.obj", "CScrollingStoreScene"), ("FamilyTreeScene.obj", "CFamilyTreeScene"),
                     ("AchievementsScene.obj", "CAchievementsScene")):
        data, start, _rel, _l = Obj(obj).func(f"?HandleKey@{cls}@@")
        body = data[start:start + 0x30]
        assert bytes.fromhex("817d0ce8030000") in body and bytes.fromhex("6a016a08ff500c") in body, cls
    data, start, _rel, _l = Obj("CollectionScene.obj").func("?HandleKey@CCollectionScene@@")
    assert bytes.fromhex("2de8030000") in data[start:start + 0x20] and bytes.fromhex("83e812") in data[start:start + 0x20]


def test_the_store_corner_and_the_promo_code_url():
    o = Obj("ScrollingStoreScene.obj")
    value, sec = o.by_name["?gCreditTriggerRect@@3UldwRect@@A"]
    data, _rel = o.section(sec)
    assert struct.unpack_from("<4i", data, value) == (972, 0, 1024, 51)
    mouse, start, rel, _l = o.func("?HandleMouse@CScrollingStoreScene@@")
    assert "?gCreditTriggerRect@@3UldwRect@@A" in rel.values()
    assert bytes.fromhex("83c005c687640100000189876801") in mouse      # Seconds() + 5; +0x164 = 1; +0x168 = it
    update, start, rel, _l = o.func("?UpdateScene@CScrollingStoreScene@@")
    assert "??0RedeemCreditDlg@@QAE@XZ" in rel.values() and "?Seconds@CGameTime@@QAE?BIXZ" in rel.values()
    # the store reads one key, Esc: no key redraws its specials (as Virtual Families 1's store page has)
    key, start, _rel, _l = o.func("?HandleKey@CScrollingStoreScene@@")
    body = key[start:start + 0x27]
    assert body.count(b"\x81\x7d\x0c") == 1 and bytes.fromhex("817d0ce8030000") in body and body.endswith(b"\xc2\x0c\x00")
    # the On Sale, Flea Market and outfit picks are refreshed only by the inventory itself, never from a key handler
    objs = {p.name: Obj(p.name) for p in sorted(OBJ_DIR.glob("*.obj"))}
    for target in ("?MaybeUpdateSaleItems@", "?MaybeUpdateRotatingItems@", "?MaybeUpdateOutfits@"):
        assert [n for n, ob in objs.items() if ob.references(target)] == ["InventoryManager.obj"], target
    for caller in ("?GetCategoryItemCount@CInventoryManager@@", "?Update@CInventoryManager@@QAEXXZ"):
        _d, _s, rel, _l = objs["InventoryManager.obj"].func(caller)
        assert any(n.startswith("?MaybeUpdateSaleItems@") for n in rel.values()), caller
    assert [n for n, ob in objs.items() if ob.references("?GetCategoryItemCount@CInventoryManager@@")] == [
        "ScrollingStoreScene.obj"]
    assert not [n for n, ob in objs.items() if ob.references("?Update@CInventoryManager@@QAEXXZ")]
    keyed = [n for n, ob in objs.items() for name, _v, s in ob.syms.values()
             if s > 0 and name.startswith("?HandleKey@") and "Store" in name]
    assert keyed == ["ScrollingStoreScene.obj"]
    promo = Obj("PromoCode.obj")
    assert b"promocode.php?code=%s&game=%s" in promo.b
    store = o.b
    for word in (b"coins", b"brokerage", b"invalid", b"ldwsoftware.com", b"/game_backend/"):
        assert word in store or word in promo.b or word in Obj("WebClient.obj").b, word


def test_the_random_tips():
    loading, start, rel, _l = Obj("theLoadingScene.obj").func("??0theLoadingScene@@QAE@XZ")
    assert bytes.fromhex("6a1e") in loading and bytes.fromhex("05e3090000") in loading       # 0x9E3 + GetRandom(30)
    assert "?GetRandom@ldwGameState@@SAHH@Z" in rel.values()
    main = Obj("theMainScene.obj")
    down, start, rel, _l = main.func("?HandleMouseDown@theMainScene@@")
    assert bytes.fromhex("6a3c") in down and bytes.fromhex("05e3090000") in down             # 0x9E3 + GetRandom(60)
    ctor, *_ = main.func("??0theMainScene@@AAE@XZ")
    assert bytes.fromhex("c7879c000000e8010000") in ctor and bytes.fromhex("c787a400000048020000") in ctor
    reset, *_ = Obj("WorldView.obj").func("?Reset@CWorldView@@")
    assert bytes.fromhex("83e826") in reset                                                  # bottom = height - 38
    state, *_ = Obj("theGameState.obj").func("??0theGameState@@IAE@XZ")
    assert struct.pack("<I", 0x400) in state and struct.pack("<I", 0x300) in state
    names = Obj("theStringManager.obj").b
    assert b"eRandomTip1\0" in names and b"eRandomTip49\0" in names


def test_the_collectibles_lifetime_odds_and_places():
    o = Obj("CollectableItem.obj")
    add, start, rel, _l = o.func("?Add@CCollectableItem@@")
    assert bytes.fromhex("83c078") in add                       # expiry = real seconds + 120
    assert bytes.fromhex("83ff02") in add                       # 2 slots
    insects = add.find(bytes.fromhex("83bc83940300004f"))       # the insects' area (base 0x4F) ...
    assert insects > 0 and bytes.fromhex("83f802") in add[insects:insects + 0x20]   # ... only Raining (2)
    assert bytes.fromhex("83f803") in add[insects:insects + 0x20]                   # ... or Stormy (3)
    assert bytes.fromhex("68 0a 01 00 00".replace(" ", "")) in add  # the Rock Hound Certificate for a forced fossil
    upd, start, rel, _l = o.func("?Update@CCollectableItem@@QAEXXZ")
    assert bytes.fromhex("b9c8190000b8e40c0000") in upd          # GetRandom(6,600), 3,300 with the Lucky Rock
    page = [f.text for f in FACTS if f.group == gm.COLLECTIBLES]
    assert any("lasts 120 seconds of real time" in t for t in page)
    assert any("insects, leaves and nuts, the Raptor" in t for t in page)


def test_the_dead_debug_code_has_no_caller():
    callers = []
    for path in sorted(OBJ_DIR.glob("*.obj")) if OBJ_DIR.is_dir() else []:
        o = Obj(path.name)
        for target in ("?HandleKeyDown@CDebugger@@", "?HandleKeyCharacter@CDebugger@@", "?Register@CDebugger@@",
                       "??0theGamewinScene@@", "??0CDayNightCycleTestDlg@@", "??0theAlignPetsScene@@"):
            callers += [(path.name, n) for n in o.references(target)]
    if not OBJ_DIR.is_dir():
        pytest.skip("the desktop object files are not present")
    assert callers == []
    assert Obj("theMainScene.obj").references("?HandleKeyCharacter@theMainScene@@")     # the scan does find callers
    debug, start, _rel, _l = Obj("theMainScene.obj").func("?Debug@theMainScene@@")
    assert data_at(debug, start) == b"\xc3"


def data_at(data, start):
    return data[start:start + 1]


# ------------------------------------------------------------------------------------------- the stock executable
def test_the_stock_house_keys_are_the_same():
    if not STOCK_EXE.is_file():
        pytest.skip("the stock executable is not present")
    raw = STOCK_EXE.read_bytes()
    if not hashlib.sha256(raw).hexdigest().startswith("1582d9e84e1c32f5"):
        pytest.skip("a different stock build")
    pefile = pytest.importorskip("pefile")
    pe = pefile.PE(data=raw, fast_load=True)
    img = pe.get_memory_mapped_image()
    base = pe.OPTIONAL_HEADER.ImageBase

    def at(va, n):
        return img[va - base:va - base + n]
    assert at(0x43BA30, 11) == bytes.fromhex("0fbe44240483c0e083f857")      # movsx; add eax, -0x20; cmp eax, 0x57
    index = at(0x43BCEC, 0x58)
    targets = [struct.unpack_from("<I", at(0x43BCA0, 4 * (k + 1)), 4 * k)[0] for k in index]
    by = {}
    for i, t in enumerate(targets):
        by.setdefault(t, []).append(chr(0x20 + i))
    groups = {"".join(v) for v in by.values() if len(v) < 20}
    assert {" ", "1", "2", "3", "4", "5", "6", "7", "8", "9", "Cc", "Dd", "Ff", "MPmp", "Ss", "Tt", "Ww"} <= groups
    assert raw.find(struct.pack("<4i", 972, 0, 1024, 51)) == 0x134834
    assert b"promocode.php?code=%s&game=%s" in raw
