import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from coff_patch import CoffObject

ROOT = Path(__file__).parents[1]
TARGETS = {0x201: "FirePlaceRusticStd", 0x205: "GrandfatherClockStd"}

for path in sorted((ROOT / "work" / "desktop_obj_files").glob("*.obj")):
    obj = CoffObject(path)
    for section in obj.sections:
        if not section.raw_ptr:
            continue
        data = obj.buf[section.raw_ptr : section.raw_ptr + section.raw_size]
        for value, name in TARGETS.items():
            needle = struct.pack("<I", value)
            offset = data.find(needle)
            while offset >= 0:
                closest = max(
                    (symbol for symbol in obj.symbols if symbol.section == section.index and symbol.value <= offset),
                    key=lambda symbol: symbol.value,
                    default=None,
                )
                symbol_name = closest.name if closest else "<section data>"
                print(f"{name} {path.name} {section.name}+0x{offset:X} {symbol_name}")
                offset = data.find(needle, offset + 1)
