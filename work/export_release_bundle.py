"""Export a release-ready offline patcher bundle from a finished matrix build.

Exists because a bundle that cannot produce a complete install looks
perfectly healthy until somebody actually installs it.

B169 shipped with 1263 asset patches where the build makes 6650 additions,
because `additive` used to export only the assets the manifest happened to
name. Installing it left the patched EXE indexing thousands of images that
were not in the folder: the family tree rendered with no background,
sprites drew in the wrong places and cursor art trailed across the screen.
Additive now means every asset the build adds to or changes in the base
game, and this script refuses to hand over a bundle that falls short.

`additive` is the right mode for a release: it carries every addition while
skipping files byte-identical to the clean payload, which the player already
has. `full` also works and additionally redistributes the untouched base
game, which makes the download far larger for no benefit.

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

def declared_variants() -> list[str]:
    """Variant names the matrix config declares, so none can be quietly skipped."""
    config = json.loads(
        (ROOT / "data" / "vf2" / "build-matrix-toggles.json").read_text(encoding="utf-8-sig")
    )
    return [v["name"] for v in config["variants"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, help="Release name, e.g. B169")
    parser.add_argument("--matrix-prefix", required=True,
                        help="Matrix output prefix, e.g. VF2-B169-matrix-20260817")
    parser.add_argument("--out-dir", help="Bundle output directory")
    parser.add_argument("--asset-mode", default="additive", choices=["additive", "all", "full"],
                        help="additive (default) ships every addition; full also "
                             "redistributes the untouched base game")
    args = parser.parse_args()

    outputs = ROOT / "outputs"
    prefix = args.matrix_prefix + "-"
    exe = f"Virtual Families 2 - {args.release}.exe"
    # Resolved once, absolutely: the exporter runs with cwd=ROOT while
    # verify() runs in the caller's directory, so a relative --out-dir would
    # be exported to one place and verified in another.
    out_dir = (
        Path(args.out_dir).resolve()
        if args.out_dir
        else outputs / f"VF2-{args.release}-Release-Bundle"
    )

    variants = sorted(
        d.name[len(prefix):] for d in outputs.glob(prefix + "*")
        if d.is_dir() and "logs" not in d.name
    )
    # Every variant the matrix declares must be present. Checking only
    # core/final_all_enabled would let a bundle ship whose image counts
    # verify fine off the all-enabled build, while
    # select_exact_executable_overlays() rejects the user-selectable setting
    # combination whose overlay never made it in.
    declared = declared_variants()
    absent = sorted(set(declared) - set(variants))
    if absent:
        detail = "\n  ".join(absent)
        print(f"matrix output incomplete: {len(absent)} of {len(declared)} declared "
              f"variants missing:\n  {detail}", file=sys.stderr)
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
    unwired = []
    for v in variants:
        if v in ("core", "final_all_enabled"):
            continue
        flag = "--" + v.replace("_", "-") + "-exe"
        if flag in flags:
            argv += [flag, exe_for(v)]
        else:
            unwired.append(v)
    if unwired:
        detail = "\n  ".join(unwired)
        print(f"exporter has no flag for {len(unwired)} built variant(s); their "
              f"overlays would be silently absent:\n  {detail}", file=sys.stderr)
        return 1

    missing = [a for a in argv if a.endswith(".exe") and not Path(a).is_file()]
    if missing:
        detail = "\n  ".join(missing)
        print(f"missing exe inputs:\n  {detail}", file=sys.stderr)
        return 1

    print(f"exporting {args.release} from {len(variants)} variants, "
          f"asset-mode={args.asset_mode}")
    result = subprocess.run([sys.executable, str(exporter)] + argv, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    return verify(out_dir, outputs / (prefix + 'final_all_enabled'))


def verify(out_dir: Path, build_dir: Path) -> int:
    """Refuse a bundle that cannot reproduce the build on a clean install.

    Count thresholds alone are not enough and have already let two broken
    releases through. The first shipped 1263 asset patches and installed a
    game missing 5700 images. The second shipped 6963 -- comfortably past
    any count floor -- while only 121 of its 646 Assets additions came
    along, so the fixtures and collision data were missing instead.

    So this simulates the install rather than trusting totals: clean base
    game plus everything the manifest writes must cover every Images and
    Assets file the build produced. Anything the build has and the install
    would not is listed by name.
    """
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8-sig"))
    summary = manifest["export_summary"]

    clean_index = json.loads(
        (ROOT / "data" / "vf2" / "clean-base-game-assets.json").read_text(encoding="utf-8-sig")
    )["files"]
    installed = {k for k in clean_index if k.startswith(("Images/", "Assets/"))}
    for patch in manifest.get("asset_patches", []):
        target = (patch.get("output_file_path") or patch.get("file_path") or "")
        target = target.replace("\\", "/")
        if target.startswith(("Images/", "Assets/")):
            installed.add(target)

    produced = {
        p.relative_to(build_dir).as_posix()
        for root in ("Images", "Assets")
        for p in (build_dir / root).rglob("*")
        if p.is_file() and p.suffix.lower() != ".bak"
    }
    missing = sorted(produced - installed)

    by_root = {}
    for rel in missing:
        by_root[rel.split("/")[0]] = by_root.get(rel.split("/")[0], 0) + 1

    print(f"\nverify: asset_mode={summary['asset_mode']} "
          f"asset_patches={summary['asset_patch_count']}")
    print(f"        build produces {len(produced)} Images/Assets files; "
          f"a clean install + this bundle yields {len(installed & produced)} of them")

    if missing:
        print("BUNDLE REJECTED: the install would be missing files the build "
              f"produced ({by_root}):", file=sys.stderr)
        for rel in missing[:20]:
            print("  - " + rel, file=sys.stderr)
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more", file=sys.stderr)
        return 1

    print("bundle reproduces the build on a clean install")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
