"""Write every claim the Game Mechanics window shows, with its label and evidence, for the owner to check.

    python scripts/export_game_mechanics_claims.py <output folder>

Writes one UTF-8 text file, "Virtual Families 2 - Game Mechanics Claims.txt": the window's lines grouped as the
window groups them, each with its label (VERIFIED-E, VERIFIED-C or UNCONFIRMED), what the label means, and the
evidence the line rests on (docs/game-mechanics/spec.md section and B200 core addresses; the emulation pins are
tests/test_game_mechanics_b200_exe.py).  A sub-line with no evidence of its own rests on the line above it.
Read-only: it writes only into the output folder.  Not shipped to players.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vf2_game_mechanics as gm  # noqa: E402

FILE_NAME = "Virtual Families 2 - Game Mechanics Claims.txt"
MEANING = {
    gm.VERIFIED_E: "the game's own code was run (emulated) with the game's inputs and every outcome counted",
    gm.VERIFIED_C: "read from the game's own code on a path the running game takes",
    gm.UNCONFIRMED: "not yet shown either way",
}


def claims_text() -> str:
    facts = gm.facts()
    counts = {label: sum(1 for f in facts if f.label == label) for label in gm.LABELS}
    out = [f"Virtual Families 2 - {gm.TITLE} claims ({len(facts)} lines: "
           + ", ".join(f"{counts[label]} {label}" for label in gm.LABELS) + ")",
           "Source: docs/game-mechanics/spec.md, the B200 core executable (every patcher option off).", ""]
    for label in gm.LABELS:
        out.append(f"{label}: {MEANING[label]}.")
    group = None
    for fact in facts:
        if fact.group != group:
            out += ["", fact.group, "-" * len(fact.group)]
            group = fact.group
        indent = "    " if fact.sub else ""
        out.append(f"{indent}[{fact.label}] {fact.text}")
        if fact.evidence:
            out.append(f"{indent}    evidence: {fact.evidence}")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    folder = Path(argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / FILE_NAME
    target.write_text(claims_text(), encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
