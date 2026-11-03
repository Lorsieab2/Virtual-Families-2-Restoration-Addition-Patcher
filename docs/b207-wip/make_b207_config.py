"""Write data/vf2/build-matrix-release-b207.json from B206's, in the given checkout.

usage: make_b207_config.py <checkout> <out.json> [<built_from sha> <tree> <pr>]
Without a sha, built_from is left out (draft for -PlanOnly).
"""
import json
import sys
from collections import OrderedDict

root, out = sys.argv[1], sys.argv[2]
with open(f"{root}/data/vf2/build-matrix-release-b206.json", encoding="utf-8") as fh:
    b206 = json.load(fh, object_pairs_hook=OrderedDict)

note_contents = (
    "B207 adds: Unicode text (#474: Render Unicode with In-Game Fonts, on by default; Use Unicode Font, off by "
    "default; the Game Font Text tool); Patch Selection Settings refuses both Unicode text settings at once (#476); "
    "the Tools tab font picker for Use Unicode Font (#477); Owner's Defaults ticks Render Unicode with In-Game "
    "Fonts (#478); surrogate-pair typing, names never cut by viewing, wide scripts, and Copy and Paste in Text "
    "Boxes, on by default (#480); the divide-by-zero and weather crash audits and the zero-length rain streak fix "
    "(#481, #482); Every picture in the Picture Maker (#483); names up to 300 characters with a Names file (#484); "
    "petanimpts.dat closed once (#485); Family History logs whole names and a paste into a name box is cut at 300 "
    "characters (#486); and the Title Screen Player Name Box setting{title_pr}."
)

cfg = OrderedDict()
cfg["release_name"] = "B207"
cfg["output_prefix"] = "VF2-B207-matrix"
cfg["exe_name"] = "Virtual Families 2 - B207.exe"
cfg["seed_set"] = "VF2-B206-matrix"
if len(sys.argv) > 3:
    sha, tree, pr = sys.argv[3], sys.argv[4], sys.argv[5]
    cfg["note"] = (
        f"Patcher matrix for B207, built on {sys.argv[6] if len(sys.argv) > 6 else '<date>'} from main at {sha[:7]} "
        f"(the merge of PR #{pr}), seeded from the B206 matrix, in 4 parallel parts. "
        + note_contents.format(title_pr=f" (#{pr})")
        + " All 32 executables are rebuilt. The 32 variants are the same feature combinations as B206. "
        "No live test of the new features has been done."
    )
    cfg["built_from"] = OrderedDict([
        ("revision", sha[:7]),
        ("ref", "main"),
        ("pull_request", int(pr)),
        ("how_to_verify", f"git rev-parse {sha[:7]}^{{tree}} must print {tree}. That single object id covers "
                          "the whole tree and resolves from the published repository alone."),
        ("tree", tree),
    ])
else:
    cfg["note"] = "DRAFT (no built_from yet). " + note_contents.format(title_pr="")
cfg["seeds"] = OrderedDict(
    (name, path.replace("VF2-B205-matrix-", "VF2-B206-matrix-")) for name, path in b206["seeds"].items()
)
assert len(cfg["seeds"]) == 32, len(cfg["seeds"])
with open(out, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(cfg, fh, indent=2, ensure_ascii=False)
    fh.write("\n")
print(f"wrote {out}: {len(cfg['seeds'])} seeds")
