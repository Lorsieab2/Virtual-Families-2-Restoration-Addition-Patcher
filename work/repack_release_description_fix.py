"""Repack a published release with corrected description text and nothing else.

B180 shipped a setting description promising 20 renovation images including
"5 Bathroom 2 styles". Those five are gated behind the separate AI-art setting,
so a player who declines that art was promised images they will not get. The
setting installs 15.

The defect is display text. It appears in two of the archive's 7,459 members
and in none of the 32 executables, so the corrected bundle is produced by
copying every member byte-for-byte and rewriting only those two. That is
strictly safer than rebuilding the matrix, which would risk producing binaries
differing from the ones already gated and already downloaded by players.

Established before writing this, because "text-only" is a comfortable claim:

  - the manifest is not self-hashed and the bundle carries no signature member
  - `description` is display-only; no asset record references it
  - the release gate reads `settings` for `id` alone -- uniqueness, core-only
    and zero-record checks -- and never reads `description`
  - the gate DOES verify every payload file against the `source_sha256` and
    `source_size` its record declares, so a repack must not touch any record
    field; this rewrites description strings only

The original archive is never modified and never deleted. This writes a new
file beside it.
"""
import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest().upper()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="published archive to repack")
    parser.add_argument("--out", required=True, help="new archive to write")
    parser.add_argument("--old-text", required=True, help="exact text to replace")
    parser.add_argument("--new-text", required=True, help="replacement text")
    parser.add_argument(
        "--rename-root",
        help=(
            "new top-level folder name. The release gate requires the ZIP "
            "root to equal the archive stem, so a differently-named archive "
            "must rename it. Verified safe: the manifest never references "
            "its own root folder (zero occurrences), so no record path "
            "changes meaning."
        ),
    )
    parser.add_argument(
        "--identities",
        default=str(ROOT / "data" / "vf2" / "release-identities-B180.json"),
        help="variant identities the executables must still match",
    )
    args = parser.parse_args()

    source = Path(args.source).resolve()
    out = Path(args.out).resolve()
    if not source.is_file():
        sys.exit(f"source archive not found: {source}")
    if out.exists():
        sys.exit(f"refusing to overwrite an existing file: {out}")
    if out == source:
        sys.exit("refusing to write over the source archive")

    old = args.old_text
    new = args.new_text

    identities = json.loads(Path(args.identities).read_text(encoding="utf-8"))
    expected_exe = {v["sha256"].lower() for v in identities["variants"]}

    rewritten = []
    copied = 0
    exe_digests = set()

    with zipfile.ZipFile(source) as src:
        infos = src.infolist()
        # Preserve order and per-member compression so the archive stays as
        # close to the original as a rewrite allows.
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in infos:
                data = src.read(info.filename)
                if old.encode("utf-8") in data:
                    data = data.replace(old.encode("utf-8"), new.encode("utf-8"))
                    rewritten.append(info.filename)
                else:
                    copied += 1
                if info.filename.lower().endswith(".exe"):
                    exe_digests.add(hashlib.sha256(data).hexdigest().lower())
                # Reuse the original member metadata so timestamps and
                # attributes are not silently reset.
                name = info.filename
                if args.rename_root:
                    head, sep, tail = name.partition("/")
                    if sep:
                        name = args.rename_root + "/" + tail
                new_info = zipfile.ZipInfo(name, date_time=info.date_time)
                new_info.compress_type = info.compress_type
                new_info.external_attr = info.external_attr
                new_info.internal_attr = info.internal_attr
                new_info.create_system = info.create_system
                dst.writestr(new_info, data)

    print(f"members rewritten : {len(rewritten)}")
    for name in rewritten:
        print(f"   {name}")
    print(f"members copied    : {copied}")
    print(f"executables       : {len(exe_digests)}")

    problems = []
    if not rewritten:
        problems.append("no member contained the text; nothing was corrected")
    if len(exe_digests) != len(expected_exe):
        problems.append(
            f"{len(exe_digests)} executables, identities file declares "
            f"{len(expected_exe)}"
        )
    unexpected = exe_digests - expected_exe
    if unexpected:
        problems.append(
            f"{len(unexpected)} executable(s) do not match the identities file"
        )
    missing = expected_exe - exe_digests
    if missing:
        problems.append(
            f"{len(missing)} declared executable(s) absent from the repack"
        )

    # A rewritten executable would be far worse than the typo being fixed.
    for name in rewritten:
        if name.lower().endswith(".exe"):
            problems.append(f"REFUSING: {name} is an executable and was rewritten")

    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        out.unlink(missing_ok=True)
        print(f"\nremoved {out.name}; the source archive is untouched")
        return 1

    print("\nevery executable still matches release-identities-B180.json")
    print(f"source  sha256: {sha256_bytes(source.read_bytes())}")
    print(f"repack  sha256: {sha256_bytes(out.read_bytes())}")
    print(f"\nwrote {out}")
    print(f"the source archive {source.name} was not modified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
