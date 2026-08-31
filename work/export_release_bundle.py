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
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_offline_patch_bundle as exporter  # noqa: E402  (needs ROOT/sys.path first)

def declared_variants() -> list[str]:
    """Variant names the matrix config declares, so none can be quietly skipped."""
    config = json.loads(
        (ROOT / "data" / "vf2" / "build-matrix-toggles.json").read_text(encoding="utf-8-sig")
    )
    return [v["name"] for v in config["variants"]]


def write_variant_identities(matrix_prefix: str, release: str) -> Path:
    """Emit the independent identity file for this release's variants."""
    sys.path.insert(0, str(ROOT / "work"))
    import export_release_variant_identities as identities

    records = identities.collect(matrix_prefix)
    payload = {
        "note": (
            "Compiled identity of every executable variant, read from the "
            "matrix build outputs rather than from the bundle that is being "
            "verified. Feed to verify_offline_bundle_zip.py --identities."
        ),
        "release": release,
        "matrix_prefix": matrix_prefix,
        "variants": records,
    }
    out = ROOT / "data" / "vf2" / f"release-identities-{release}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    return out


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
        # Named to match the archive stem: verify_offline_bundle_zip.py
        # requires the ZIP root to equal the archive name, so a
        # "-Release-Bundle" directory had to be renamed by hand before
        # packaging B173 and B174.
        else outputs / f"VF2-{args.release}-Release"
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

    return verify(
        out_dir,
        outputs / (prefix + 'final_all_enabled'),
        args.matrix_prefix,
        args.release,
    )


def verify(out_dir: Path, build_dir: Path, matrix_prefix: str, release: str) -> int:
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

    # Coverage is decided by CONTENT, not by path. Matching on paths alone
    # would call a stock file "covered" by the clean install even when the
    # build modified it and the bundle omitted the patch -- the installed
    # game would silently keep the vanilla bytes and this gate would report
    # success, which is exactly the kind of miss it exists to prevent.
    supplied: dict[str, set[str]] = {}
    # Invisible Furniture installs in two deliberate stages: the VISIBLE
    # graphic ships first so the item can be placed at all, and the fully
    # transparent version is an opt-in swap behind a second setting. Those
    # paths therefore differ from the build on purpose until the player
    # enables the swap, and the bundle does carry a patch for each.
    staged: set[str] = set()
    for patch in manifest.get("asset_patches", []):
        target = (patch.get("output_file_path") or patch.get("file_path") or "")
        target = target.replace("\\", "/")
        if not target.startswith(("Images/", "Assets/")):
            continue
        digest = patch.get("source_sha256")
        if digest:
            supplied.setdefault(target, set()).add(digest)
        if "invisible_furniture_visible_graphics" in (patch.get("requires") or ()):
            staged.add(target)

    produced_files = [
        p
        for root in ("Images", "Assets")
        for p in (build_dir / root).rglob("*")
        if p.is_file()
        and not exporter.is_non_runtime_source_path(p.relative_to(build_dir))
    ]
    produced = {p.relative_to(build_dir).as_posix() for p in produced_files}

    missing = []
    for path in produced_files:
        rel = path.relative_to(build_dir).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in supplied.get(rel, ()):
            continue                      # the bundle writes these exact bytes
        entry = clean_index.get(rel)
        if entry is not None and entry["sha256"] == digest:
            continue                      # already present, unmodified
        if rel in staged:
            continue                      # visible-first Invisible Furniture stage
        missing.append(rel)
    missing.sort()

    by_root = {}
    for rel in missing:
        by_root[rel.split("/")[0]] = by_root.get(rel.split("/")[0], 0) + 1

    print(f"\nverify: asset_mode={summary['asset_mode']} "
          f"asset_patches={summary['asset_patch_count']}")
    print(f"        build produces {len(produced)} Images/Assets files; "
          f"a clean install + this bundle reproduces {len(produced) - len(missing)} "
          "of them byte-for-byte")

    if missing:
        print("BUNDLE REJECTED: the install would be missing files the build "
              f"produced ({by_root}):", file=sys.stderr)
        for rel in missing[:20]:
            print("  - " + rel, file=sys.stderr)
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more", file=sys.stderr)
        return 1

    # Record what each feature combination actually compiled to, read from the
    # matrix outputs rather than from the bundle. verify_offline_bundle_zip.py
    # cannot authenticate the executables from manifest.json alone: this
    # exporter writes both the payload and the hashes describing it, so one
    # checked against the other only proves the bundle agrees with itself.
    # Emitting it here means every release has an independent identity source
    # without anyone having to remember a separate command.
    identities_path = write_variant_identities(matrix_prefix, release)
    print(f"recorded independent variant identities -> {identities_path}")

    print("bundle reproduces the build on a clean install")
    print(
        "gate the packaged ZIP with:" + chr(10) +
        f"  python work/verify_offline_bundle_zip.py <zip> "
        f"--identities {identities_path} --require-identities"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
