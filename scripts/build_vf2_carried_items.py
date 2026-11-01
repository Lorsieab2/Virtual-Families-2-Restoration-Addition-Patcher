"""Make src/vf2_carried_items.json: which item values the game's code ever puts in a family member's hands.

A family member carries one value (CVillager+1BB9Ch, ECarrying). Everything that sets it to an item is a
CVillagerPlans::PlanToCarry step, so this reads every PlanToCarry call in the B200 desktop object files and works
out its argument (tests/vf2_carry_scan.py says how), and writes, for each value, the actions (CBehavior handlers)
that carry it, plus the actions that carry whatever they pick up (a collectible or a piece of mess). Numbers and
code names only: the Picture Maker (src/vf2_people_pictures.py) gives the items and actions their words.
tests/test_picture_maker.py checks the file against the same scan.

    python scripts/build_vf2_carried_items.py [--objects work/desktop_obj_files]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))

OUTPUT = REPO / "src" / "vf2_carried_items.json"


def build(objects: Path) -> dict:
    import vf2_carry_scan as scan
    found = scan.scan(Path(objects))
    if found["unresolved"]:
        raise SystemExit("PlanToCarry calls whose item could not be worked out:\n" + "\n".join(found["unresolved"]))
    return {"made_by": "scripts/build_vf2_carried_items.py: every CVillagerPlans::PlanToCarry call in the B200 "
                       "desktop objects (tests/vf2_carry_scan.py)",
            "values": {str(v): names for v, names in found["values"].items()},
            "pickup": found["pickup"], "random_food": found["random_food"]}


def render(data: dict) -> str:
    lines = ["{", f'  "made_by": {json.dumps(data["made_by"])},',
             f'  "pickup": {json.dumps(data["pickup"])},',
             f'  "random_food": {json.dumps(data["random_food"])},', '  "values": {']
    keys = list(data["values"])
    for k, key in enumerate(keys):
        lines.append(f'    "{key}": {json.dumps(data["values"][key])}' + ("," if k < len(keys) - 1 else ""))
    lines += ["  }", "}"]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--objects", default=str(REPO / "work" / "desktop_obj_files"))
    args = parser.parse_args(argv)
    text = render(build(Path(args.objects)))
    OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT} ({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
