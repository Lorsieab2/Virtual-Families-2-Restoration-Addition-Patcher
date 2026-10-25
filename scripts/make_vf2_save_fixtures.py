"""Rebuild tests/fixtures/vf2_saves from COPIES of real Virtual Families 2 saves.

Usage:  python scripts/make_vf2_save_fixtures.py <folder holding copies of the save files>

Never point this at the player's own save folder: copy the files somewhere first (the saves and
installs are read-only). The fixtures are the files gzip-compressed, byte for byte; no path is
stored in them.
"""
from __future__ import annotations

import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "vf2_saves"

# fixture name -> the copied file it is made from (relative to the folder given)
FIXTURES = {
    "one_generation_slot3.ldw.gz": "b202/Virtual Families 23.ldw",
    "ten_generations_slot4.ldw.gz": "jessie/Virtual Families 24.ldw",
    "pending_birth_slot1.ldw.gz": "b171/Virtual Families 21.ldw",
    "settings_slot0.ldw.gz": "b202/Virtual Families 20.ldw",
    "legacy_header_slot5.ldw.gz": "main/virtual families 25.ldw",
}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    src = Path(argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rel in FIXTURES.items():
        data = (src / rel).read_bytes()
        (OUT / name).write_bytes(gzip.compress(data, 9, mtime=0))
        print(f"{name}: {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
