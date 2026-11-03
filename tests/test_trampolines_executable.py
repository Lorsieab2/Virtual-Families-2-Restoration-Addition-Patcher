"""Every trampoline the Unicode DLL builds is made executable before the game can call it.

An emulation of the DLL does not enforce DEP, so a trampoline left in a no-execute data page passes every emulated test and
then crashes the real game at its first call (B207's first live start: an access violation at BoxDrawTrampoline, the long
names' draw hook, because only the two older trampolines were VirtualProtect-ed). This test reads the source: every
`static unsigned char XTrampoline[...]` of b200unicode.cpp and its includes must appear in a
`VirtualProtect(XTrampoline, ..., PAGE_EXECUTE_READWRITE, ...)` call.
"""
import re
from pathlib import Path

NATIVE = Path(__file__).resolve().parent.parent / "runtime" / "native" / "b200unicode"


def _sources():
    return {p.name: p.read_text(encoding="utf-8", errors="replace") for p in NATIVE.iterdir() if p.suffix in (".cpp", ".inc", ".h")}


def test_every_trampoline_is_made_executable():
    sources = _sources()
    text = "\n".join(sources.values())
    declared = set(re.findall(r"static\s+unsigned\s+char\s+(\w*Trampoline)\s*\[", text))
    assert {"JustifiedTrampoline", "SetTextTrampoline", "SetCanEditTrampoline", "BoxDrawTrampoline"} <= declared, declared
    protected = set(re.findall(r"VirtualProtect\(\s*(\w*Trampoline)\s*,[^;]*PAGE_EXECUTE_READWRITE", text))
    assert declared <= protected, f"trampolines never made executable: {sorted(declared - protected)}"


def test_the_long_names_trampolines_are_not_protected_in_the_clip_build():
    # the clip DLL (B200UNICODE_CLIP) has no long-names code, so it does not declare them
    cpp = (NATIVE / "b200unicode.cpp").read_text(encoding="utf-8", errors="replace")
    block = cpp[cpp.index("static bool Apply(Plan &plan)"):]
    block = block[:block.index("\n}\n")]
    guarded = re.search(r"#ifndef B200UNICODE_CLIP\s+if \(!VirtualProtect\(SetCanEditTrampoline.*?BoxDrawTrampoline.*?#endif", block, re.S)
    assert guarded, "the two long-names trampolines must be protected inside #ifndef B200UNICODE_CLIP"
