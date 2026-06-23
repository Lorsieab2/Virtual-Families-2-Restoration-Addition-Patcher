from pathlib import Path
import json
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "VF2-Desktop-Object-Analysis"
MOBILE_ASSETS = ROOT / "work" / "vf2_obb" / "assets"
MOBILE_IMAGES = ROOT / "outputs" / "VF2-Mobile-Furniture-Modded" / "Images"

KEYS = [
    "Birthday",
    "Christmas",
    "Gnome",
    "Snowman",
    "Wreath",
    "Chaise",
    "Patio",
    "Collection",
    "Collectable",
    "body",
    "Body",
    "head",
    "Head",
    "hair",
    "Hair",
    "villager",
    "Villager",
    "Outfit",
    "outfit",
]


def group(files):
    buckets = defaultdict(list)
    for p in files:
        n = p.name
        for k in KEYS:
            if k in n:
                buckets[k.lower()].append({"path": str(p), "name": n, "size": p.stat().st_size})
                break
    return dict(sorted(buckets.items()))


def main():
    assets = list(MOBILE_ASSETS.rglob("*")) if MOBILE_ASSETS.exists() else []
    images = list(MOBILE_IMAGES.rglob("*")) if MOBILE_IMAGES.exists() else []
    assets = [p for p in assets if p.is_file()]
    images = [p for p in images if p.is_file()]
    report = {
        "mobile_assets_by_keyword": group(assets),
        "mobile_images_by_keyword": group(images),
    }
    (OUT / "mobile-asset-family-inventory.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Mobile Asset Family Inventory", ""]
    for label, buckets in [("Assets", report["mobile_assets_by_keyword"]), ("Images", report["mobile_images_by_keyword"])]:
        lines.append(f"## {label}")
        lines.append("")
        for key, items in buckets.items():
            lines.append(f"### {key} ({len(items)})")
            for item in items[:80]:
                lines.append(f"- `{item['name']}` ({item['size']} bytes)")
            if len(items) > 80:
                lines.append(f"- ... {len(items) - 80} more")
            lines.append("")
    (OUT / "MOBILE-ASSET-FAMILY-INVENTORY.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
