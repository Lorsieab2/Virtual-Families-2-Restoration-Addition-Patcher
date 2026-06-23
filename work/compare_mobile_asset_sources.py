from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / "work" / "vf2_obb" / "assets"
USER = ROOT / "work" / "user_mobile_assets"
OUT = ROOT / "outputs" / "VF2-Mobile-Cpp-Reconstruction"


def sha(path: Path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def index(root: Path):
    data = {}
    for p in root.iterdir():
        if p.is_file():
            data[p.name] = {"size": p.stat().st_size, "sha256": sha(p)}
    return data


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    a = index(EXTRACTED)
    b = index(USER)
    only_extracted = sorted(set(a) - set(b))
    only_user = sorted(set(b) - set(a))
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    same = sorted(k for k in set(a) & set(b) if a[k] == b[k])
    report = {
        "extracted_count": len(a),
        "user_count": len(b),
        "same_count": len(same),
        "changed_count": len(changed),
        "only_extracted": only_extracted,
        "only_user": only_user,
        "changed": [{"name": k, "extracted": a[k], "user": b[k]} for k in changed],
    }
    (OUT / "mobile-asset-source-compare.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = []
    lines.append("# Mobile Asset Source Compare")
    lines.append("")
    lines.append(f"- Extracted XAPK/OBB asset files: {len(a)}")
    lines.append(f"- User-provided assets folder files: {len(b)}")
    lines.append(f"- Identical files: {len(same)}")
    lines.append(f"- Changed same-name files: {len(changed)}")
    lines.append(f"- Only in extracted XAPK/OBB: {len(only_extracted)}")
    lines.append(f"- Only in user-provided folder: {len(only_user)}")
    lines.append("")
    if only_user:
        lines.append("## Only In User Folder")
        lines.extend(f"- `{x}`" for x in only_user[:200])
        lines.append("")
    if changed:
        lines.append("## Changed Same-Name Files")
        for item in changed[:200]:
            lines.append(f"- `{item['name']}`: extracted {item['extracted']['size']} bytes, user {item['user']['size']} bytes")
        lines.append("")
    if only_extracted:
        lines.append("## Only In Extracted XAPK/OBB")
        lines.extend(f"- `{x}`" for x in only_extracted[:200])
        lines.append("")
    (OUT / "MOBILE-ASSET-SOURCE-COMPARE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
