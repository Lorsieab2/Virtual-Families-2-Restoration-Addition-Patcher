from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "VF2-Mobile-Cpp-Reconstruction"
EXE = ROOT / "outputs" / "Virtual Families 2.exe"

inv = json.loads((OUT / "mobile-native-inventory.json").read_text(encoding="utf-8"))
exe = EXE.read_bytes()

class_hits = []
method_hits = []

for item in inv["top_classes"]:
    cls = item["class"]
    if cls.encode("ascii", "ignore") in exe:
        class_hits.append(cls)
    for method in item["sample_methods"]:
        if method.encode("ascii", "ignore") in exe:
            method_hits.append({"class": cls, "method": method})

report = {
    "desktop_exe": str(EXE),
    "desktop_size": len(exe),
    "mobile_class_count": inv["class_count"],
    "desktop_class_hits": class_hits,
    "desktop_method_hits": method_hits,
}

(OUT / "desktop-mobile-symbol-overlap.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

lines = []
lines.append("# Desktop/Mobile Symbol Overlap")
lines.append("")
lines.append("The Windows desktop EXE still contains many of the same internal class and method names recovered from the mobile native C++ library.")
lines.append("This strongly suggests the Android and desktop builds are sibling ports of the same LDW C++ engine/game codebase.")
lines.append("")
lines.append(f"- Mobile recovered class count: {inv['class_count']}")
lines.append(f"- Desktop class-name hits among ranked mobile classes: {len(class_hits)}")
lines.append(f"- Desktop method-name hits among sampled mobile methods: {len(method_hits)}")
lines.append("")
lines.append("## Sample Shared Classes")
lines.append("")
for cls in class_hits[:80]:
    lines.append(f"- `{cls}`")
lines.append("")
lines.append("## Sample Shared Methods")
lines.append("")
for hit in method_hits[:120]:
    lines.append(f"- `{hit['class']}::{hit['method']}`")

(OUT / "DESKTOP-MOBILE-SYMBOL-OVERLAP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
