"""Make src/vf2_people_links.json (and its work/ copy): the link points the game joins a body and a head with.

Virtual Families 2 draws a family member as a body cell and a head cell (CVillager::DrawDetailVillager,
CVillagerManager::DrawVillager, CVillager::DrawEventVillager, CFamilyTreeScene::DrawPeep). Where each goes is
given by CAnimManager's link tables: for every body frame, sex and body row a "next" point (where the body is
anchored) and a "prev" point (its neck), and for every head direction, sex and head row the same two points.
CAnimManager::LoadAssets builds the tables from constants in its code and from the game's Assets\\animpts.dat.

This runs LoadAssets itself, from the B200 desktop object files (unicorn; tests/vf2_people_emu.py), over a
game folder, and writes what it built: numbers only, no picture. tests/test_picture_maker.py checks the file
against the same run.

    python scripts/build_vf2_people_links.py [--objects work/desktop_obj_files] [--game work/vanilla_runtime_payload]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))

OUTPUTS = (REPO / "src" / "vf2_people_links.json", REPO / "work" / "vf2_people_links.json")


def _rows(points: list) -> list:
    """50 points, or one when all 50 are the same (most frames anchor every row alike)."""
    return [points[0]] if all(p == points[0] for p in points) else points


def build(objects: Path, game: Path) -> dict:
    import vf2_people_emu as pe
    rig = pe.PeopleRig(objects, game)
    tables = rig.link_tables()
    out = {"made_by": "scripts/build_vf2_people_links.py: CAnimManager::LoadAssets run from the B200 desktop "
                      "objects over the game's Assets\\anims.dat and Assets\\animpts.dat",
           "animpts_sha256": hashlib.sha256((game / "Assets" / "animpts.dat").read_bytes()).hexdigest(),
           "anims_sha256": hashlib.sha256((game / "Assets" / "anims.dat").read_bytes()).hexdigest(),
           "facing": tables["facing"], "body": {}, "head": {}}
    for part in ("body", "head"):
        for key, entry in tables[part].items():
            out[part][key] = {"image": entry["image"], "cell": entry["cell"], "prev": _rows(entry["prev"]),
                              "next": _rows(entry["next"])}
    return out


def render(data: dict) -> str:
    lines = ["{"]
    lines.append(f'  "made_by": {json.dumps(data["made_by"])},')
    lines.append(f'  "animpts_sha256": "{data["animpts_sha256"]}",')
    lines.append(f'  "anims_sha256": "{data["anims_sha256"]}",')
    lines.append(f'  "facing": {json.dumps(data["facing"], separators=(",", ":"))},')
    for n, part in enumerate(("body", "head")):
        lines.append(f'  "{part}": {{')
        keys = list(data[part])
        for k, key in enumerate(keys):
            comma = "," if k < len(keys) - 1 else ""
            lines.append(f'    "{key}": {json.dumps(data[part][key], separators=(",", ":"))}{comma}')
        lines.append("  }" + ("," if n == 0 else ""))
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--objects", default=str(REPO / "work" / "desktop_obj_files"))
    parser.add_argument("--game", default=str(REPO / "work" / "vanilla_runtime_payload"))
    args = parser.parse_args(argv)
    text = render(build(Path(args.objects), Path(args.game)))
    for path in OUTPUTS:
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {path} ({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
