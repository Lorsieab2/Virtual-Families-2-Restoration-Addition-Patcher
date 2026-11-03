"""Emulate the store's Special Upgrades, House Renovations and Clothing pages on executables.

usage: emulate_store_pages.py <checkout> <exe> [<exe> ...]
Each exe needs patch-manifest.json beside it. Uses the Exe emulator from tests/test_store_page_gates_exe.py
(the game's own GetCategoryItemCount / GetCategoryItem). Prints one line per exe.
"""
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "tests"))
sys.path.insert(0, str(root / "work"))
from test_store_page_gates_exe import CLOTHING, HOUSE_RENOVATIONS, SPECIAL_UPGRADES, Exe  # noqa: E402

import shutil  # noqa: E402
import tempfile  # noqa: E402

for p in sys.argv[2:]:
    if (Path(p).parent / "patch-manifest.json").is_file():
        exe = Exe(p)
    else:  # an applied game folder: the emulator only needs some manifest beside the exe
        tmp = Path(tempfile.mkdtemp(prefix="vf2emu-"))
        shutil.copy2(p, tmp / Path(p).name)
        (tmp / "patch-manifest.json").write_text("{}", encoding="utf-8")
        exe = Exe(str(tmp / Path(p).name))
    special = len(exe.page(SPECIAL_UPGRADES))
    renov = len(exe.page(HOUSE_RENOVATIONS))
    cloth = len(exe.page(CLOTHING))
    print(f"special_upgrades={special:3d} house_renovations={renov:3d} clothing={cloth:3d}  {Path(p).parent.name}")
