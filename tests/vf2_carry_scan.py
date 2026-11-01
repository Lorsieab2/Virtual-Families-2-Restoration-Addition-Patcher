"""Every item the game's code can put in a family member's hands, read from the B200 desktop object files.

A family member carries one value (CVillager+1BB9Ch, ECarrying), set only by CVillager::SetCarrying. Its callers
are CVillagerPlans::ProcessCurrentPlan / AdvanceCurrentPlan (a plan step made by CVillagerPlans::PlanToCarry),
VillagerAI and ForgetPlans (3, the baby, while expecting, or -1, nothing) and the reset paths (-1).
CVillager::ForceCarrying writes it too but nothing calls it. So the values the game ever carries are the
arguments of every PlanToCarry call. This finds each call (capstone) and works out its argument:

* an immediate push, or a register set by ``mov reg, imm`` before it;
* ``GetRandom(n) + k``: k .. k + n - 1;
* ``setcc cl`` then ``lea ecx, [ecx*2 + k]`` (k or k + 2) or ``add ecx, k`` (k or k + 1);
* CBehavior::RandomFoodCarryable(): every value it returns (its ``mov esi, imm``s);
* ``push imm; jmp`` into the call from a jump table's other branches;
* the item a family member picks up (the SPickUpData of PickCollectable, PickupSock, PullingWeeds,
  ThrowAwayWrapper, CleanCobwebs, CleanDirtSmudge, and CCollectable::ProcessNearbyCollectables): a collectible or
  a piece of mess, whatever lies there -- reported as "pickup".

Anything left over is reported, never guessed. tests/test_picture_maker.py checks src/vf2_carried_items.json
against this.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from vf2_people_emu import CoffObject

PLAN_TO_CARRY = "?PlanToCarry@CVillagerPlans@@QAEXW4ECarrying@@@Z"
RANDOM_FOOD = "?RandomFoodCarryable@CBehavior@@CA?AW4ECarrying@@AAVCVillager@@@Z"
GET_RANDOM = "?GetRandom@ldwGameState@@SAHH@Z"
PICKUP = {"PickCollectable", "PickupSock", "PullingWeeds", "ThrowAwayWrapper", "CleanCobwebs", "CleanDirtSmudge",
          "ProcessNearbyCollectables"}
CALLEE_SAVED = ("ebx", "esi", "edi")
_IMM = re.compile(r"^-?(0x[0-9a-f]+|\d+)$")


def _imm(text: str):
    return int(text, 0) if _IMM.match(text) else None


def _signed(v: int) -> int:
    return v - (1 << 32) if v >= 0x80000000 else v


def _functions(obj: CoffObject) -> dict:
    out = {}
    for _k, (name, value, sect, cls) in obj.symbols.items():
        if sect > 0 and cls == 2 and obj.sections[sect - 1]["chars"] & 0x20:
            out.setdefault(sect, []).append((value, name))
    return out


def _disasm(obj: CoffObject, sect: int):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    sec = obj.sections[sect - 1]
    code = obj.data[sec["ptr"]:sec["ptr"] + sec["size"]]
    rel = {va: obj.symbols[sym][0] for va, sym, _t in sec["relocs"]}
    ins = list(md.disasm(code, 0))
    return ins, rel


def _target(x, rel) -> str:
    return next((rel[a] for a in range(x.address, x.address + x.size) if a in rel), "")


def random_food_values(obj_dir: Path) -> set:
    obj = CoffObject(Path(obj_dir) / "Behavior.obj")
    for sect, names in _functions(obj).items():
        if any(n == RANDOM_FOOD for _v, n in names):
            ins, _rel = _disasm(obj, sect)
            return {_imm(x.op_str.split(", ")[1]) for x in ins
                    if x.mnemonic == "mov" and x.op_str.startswith("esi, ") and _imm(x.op_str.split(", ")[1]) is not None}
    raise LookupError("CBehavior::RandomFoodCarryable was not found")


def _register_constant(ins, k: int, reg: str):
    """The constant `reg` holds before ins[k]: the nearest ``mov reg, imm`` above it (None when anything else
    sets it first)."""
    for q in range(k - 1, max(-1, k - 400), -1):
        x = ins[q]
        if x.op_str.startswith(reg + ", ") and not x.mnemonic.startswith(("cmp", "test", "push")):
            src = x.op_str[len(reg) + 2:]
            m = re.match(r"\[(e[a-z]{2}) \+ (0x[0-9a-f]+|\d+)\]$", src)
            if x.mnemonic == "lea" and m:              # lea esi, [ebx + 1Eh] with ebx a constant
                base = _register_constant(ins, q, m.group(1))
                return None if base is None else base + int(m.group(2), 0)
            v = _imm(src)
            return v if x.mnemonic == "mov" else None
        if x.mnemonic == "call" and reg not in CALLEE_SAVED:
            return None
    return None


def _resolve(ins, rel, idx: int, food: set):
    """The argument of the call at ins[idx]: (set of values, how) or (None, why)."""
    j = idx - 1
    while j >= 0 and ins[j].mnemonic != "push":
        j -= 1
    op = ins[j].op_str
    values = set()
    # jump-table branches that push a value and jump straight to the call
    for x in ins:
        if x.mnemonic == "jmp" and _imm(x.op_str) is not None and ins[j].address <= _imm(x.op_str) <= ins[idx].address:
            k = ins.index(x) - 1
            if k >= 0 and ins[k].mnemonic == "push" and _imm(ins[k].op_str) is not None:
                values.add(_signed(_imm(ins[k].op_str) & 0xFFFFFFFF))
    v = _imm(op)
    if v is not None:
        return values | {_signed(v & 0xFFFFFFFF)}, "constant"
    if op.startswith("dword ptr"):
        return None, "pickup"
    reg = op
    add = 0
    k = j - 1
    while k >= 0 and k > j - 40:
        x = ins[k]
        mn, ops = x.mnemonic, x.op_str
        if mn == "call":
            target = _target(x, rel)
            if target == RANDOM_FOOD and reg == "eax":
                return values | {f + add for f in food}, "RandomFoodCarryable"
            if target == GET_RANDOM and reg == "eax":
                p = next((ins[q] for q in range(k - 1, max(-1, k - 4), -1) if ins[q].mnemonic == "push"), None)
                n = _imm(p.op_str) if p is not None else None
                if n is None:
                    return None, "GetRandom of an unknown range"
                return values | set(range(add, add + n)), "random"
            if reg not in CALLEE_SAVED:
                return None, f"{reg} after a call to {target or '?'}"
        if ops.startswith(reg + ", "):
            src = ops[len(reg) + 2:]
            if mn == "mov" and _imm(src) is not None:
                return values | {_imm(src) + add}, "register"
            if mn == "mov" and src.startswith("dword ptr"):
                return None, "pickup"
            if mn == "add" and _imm(src) is not None:
                add += _imm(src)
            elif mn == "lea":
                m = re.match(rf"\[{reg[1:]}?e?{reg[1:]}\*2 \+ (0x[0-9a-f]+|\d+)\]$", src) or \
                    re.match(r"\[(\w+)\*2 \+ (0x[0-9a-f]+|\d+)\]$", src)
                if m and ins[k - 1].mnemonic.startswith("set") or (m and ins[k - 2].mnemonic.startswith("set")):
                    base = int(m.groups()[-1], 0)
                    return values | {base + add, base + 2 + add}, "flag"
                return None, f"lea {src}"
            elif mn == "xor" and src == reg:
                return values | {add}, "register"
            elif mn.startswith("cmov") and src in ("eax", "ebx", "ecx", "edx", "esi", "edi"):
                other = _register_constant(ins, k, src)
                if other is None:
                    return None, f"{mn} {ops}"
                values.add(other + add)
            else:
                return None, f"{mn} {ops}"
        if mn.startswith("set") and ops in ("cl", "al", "dl", "bl") and reg[1] == ops[0]:
            return values | {add, add + 1}, "flag"
        k -= 1
    return None, f"push {op}"


def scan(obj_dir: Path) -> dict:
    """{"values": {value: sorted behaviour names}, "pickup": [...], "unresolved": [...]} over every object."""
    food = random_food_values(obj_dir)
    values: dict = defaultdict(set)
    pickup, unresolved = [], []
    for path in sorted(Path(obj_dir).glob("*.obj")):
        try:
            obj = CoffObject(path)
        except Exception:
            continue
        funcs = _functions(obj)
        for sect, sec in enumerate(obj.sections, 1):
            if not sec["chars"] & 0x20 or sect not in funcs:
                continue
            if not any(obj.symbols[s][0] == PLAN_TO_CARRY for _va, s, _t in sec["relocs"]):
                continue
            ins, rel = _disasm(obj, sect)
            owner = sorted(funcs[sect])[0][1].lstrip("?").split("@")[0]
            for idx, x in enumerate(ins):
                if x.mnemonic != "call" or _target(x, rel) != PLAN_TO_CARRY:
                    continue
                found, how = _resolve(ins, rel, idx, food)
                if found is None and owner in PICKUP:
                    pickup.append(owner)
                elif found is None:
                    unresolved.append(f"{path.stem}:{owner}@{x.address:x}: {how}")
                else:
                    for v in found:
                        values[v].add(owner)
    return {"values": {v: sorted(n) for v, n in sorted(values.items())}, "pickup": sorted(set(pickup)),
            "unresolved": unresolved, "random_food": sorted(food)}
