"""Export a release-ready offline patcher bundle from a finished matrix build.

Exists because the exporter's default asset mode is wrong for a release and
the mistake is invisible until someone installs the result.

`--asset-mode additive` exports only the assets the manifest references and
sets `allow_missing_target`, so the bundle carries the patcher's *additions*
and nothing else. Applied to a clean install that produces a game whose EXE
indexes thousands of images the folder does not contain: the family tree
renders with no background, sprites appear in the wrong places, and cursor
art trails across the screen. B169 shipped that way -- 1263 asset patches
where the complete build needs 6906 -- and it looked fine in every check
that did not actually install it.

Release bundles therefore use `--asset-mode full`, and this script asserts
the result really can produce a complete install before it is packaged.

Usage:
    python work/export_release_bundle.py --release B169 \
        --matrix-prefix VF2-B169-matrix-20260817
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A complete build carries roughly this much art. The additive bundle
# carried 1607 images once applied, against 7305 for a correct install, so
# a floor well above the additive figure catches the regression without
# being brittle about exact counts.
MIN_PAYLOAD_IMAGES = 5000
MIN_ASSET_PATCHES = 5000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, help="Release name, e.g. B169")
    parser.add_argument("--matrix-prefix", required=True,
                        help="Matrix output prefix, e.g. VF2-B169-matrix-20260817")
    parser.add_argument("--out-dir", help="Bundle output directory")
    parser.add_argument("--asset-mode", default="full", choices=["additive", "all", "full"],
                        help="Defaults to full; anything else is rejected for a release")
    args = parser.parse_args()

    if args.asset_mode != "full":
        print(f"refusing to build a release bundle with --asset-mode {args.asset_mode}: "
              "only 'full' carries the base game's art", file=sys.stderr)
        return 2

    outputs = ROOT / "outputs"
    prefix = args.matrix_prefix + "-"
    exe = f"Virtual Families 2 - {args.release}.exe"
    out_dir = Path(args.out_dir) if args.out_dir else outputs / f"VF2-{args.release}-Release-Bundle"

    variants = sorted(
        d.name[len(prefix):] for d in outputs.glob(prefix + "*")
        if d.is_dir() and "logs" not in d.name
    )
    if "final_all_enabled" not in variants or "core" not in variants:
        print(f"matrix output incomplete: found {len(variants)} variants", file=sys.stderr)
        return 1

    exporter = ROOT / "work" / "export_offline_patch_bundle.py"
    help_text = subprocess.run([sys.executable, str(exporter), "--help"],
                               capture_output=True, text=True, cwd=ROOT).stdout
    flags = {t for t in help_text.replace("[", " ").replace("]", " ").split()
             if t.startswith("--")}

    def exe_for(name: str) -> str:
        return str(outputs / (prefix + name) / exe)

    argv = [
        "--build-dir", str(outputs / (prefix + "final_all_enabled")),
        "--out-dir", str(out_dir),
        "--patched-exe", exe_for("core"),
        "--final-playtest-native-exe", exe_for("final_all_enabled"),
        "--final-playtest-all-enabled",
        "--include-patcher-scripts",
        "--include-exe-replacement",
        "--asset-mode", args.asset_mode,
        "--mobile-sound-assets-dir",
        str(ROOT / "patcher_assets" / "optional_patches" / "mobile_sound_assets"),
        # The shipped identity manifest has PE structure metadata but no exact
        # SHA-256 for the vanilla EXE, so the EXE itself supplies the identity.
        "--vanilla-exe", str(ROOT / "work" / "vanilla_runtime_payload" / "Virtual Families 2.exe"),
        "--name", args.release,
        "--force",
    ]
    for v in variants:
        if v in ("core", "final_all_enabled"):
            continue
        flag = "--" + v.replace("_", "-") + "-exe"
        if flag in flags:
            argv += [flag, exe_for(v)]

    missing = [a for a in argv if a.endswith(".exe") and not Path(a).is_file()]
    if missing:
        print("missing exe inputs:\n  " + "\n  ".join(missing), file=sys.stderr)
        return 1

    print(f"exporting {args.release} from {len(variants)} variants, asset-mode={args.asset_mode}")
    result = subprocess.run([sys.executable, str(exporter)] + argv, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    return verify(out_dir)


def verify(out_dir: Path) -> int:
    """Fail loudly if the bundle cannot produce a complete install."""
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    summary = manifest["export_summary"]
    payload_images = sum(
        1 for p in (out_dir / "payload").rglob("*")
        if p.is_file() and "Images" in p.parts
    )
    asset_patches = summary["asset_patch_count"]

    problems = []
    if summary["asset_mode"] != "full":
        problems.append(f"asset_mode is {summary['asset_mode']!r}, not 'full'")
    if asset_patches < MIN_ASSET_PATCHES:
        problems.append(
            f"only {asset_patches} asset patches; a complete build needs "
            f"at least {MIN_ASSET_PATCHES}. An additive export produces about "
            "1263, which installs a game missing most of its art."
        )
    if payload_images < MIN_PAYLOAD_IMAGES:
        problems.append(
            f"only {payload_images} payload images; expected at least "
            f"{MIN_PAYLOAD_IMAGES}"
        )

    print(f"\nverify: asset_mode={summary['asset_mode']} "
          f"asset_patches={asset_patches} payload_images={payload_images}")
    if problems:
        print("BUNDLE REJECTED:", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 1
    print("bundle looks complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
