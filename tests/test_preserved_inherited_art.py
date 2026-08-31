"""The tracked inherited-art store, and the build step that consumes it.

Some runtime images existed in neither the repository nor the vanilla payload,
so they reached a build only by being copied out of the previous build's
output.  Every release therefore depended on an unbroken chain of prior
artifacts, and a build from a clean clone was impossible.  The files are
tracked under patcher_assets/inherited_runtime_images; these tests cover the
store's integrity and the build step that fills in whatever is still missing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STORE = REPO / "patcher_assets" / "inherited_runtime_images"
INDEX = REPO / "data" / "vf2" / "inherited-only-images.json"


def _wanted() -> list[str]:
    return json.loads(INDEX.read_text(encoding="utf-8"))["files"]


def _digests() -> dict[str, str]:
    return json.loads((STORE / "SHA256SUMS.json").read_text(encoding="utf-8"))["files"]


def test_store_covers_every_inheritance_only_image():
    wanted = _wanted()
    missing = [rel for rel in wanted if not (STORE / rel).is_file()]
    assert not missing, f"{len(missing)} inheritance-only images are not preserved: {missing[:5]}"


def test_every_preserved_file_matches_its_recorded_digest():
    digests = _digests()
    wrong = []
    for rel in _wanted():
        path = STORE / rel
        if not path.is_file():
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != digests.get(rel):
            wrong.append(rel)
    assert not wrong, f"preserved art does not match SHA256SUMS.json: {wrong[:5]}"


def test_digest_manifest_has_no_entries_the_index_does_not_name():
    extra = sorted(set(_digests()) - set(_wanted()))
    assert not extra, f"SHA256SUMS.json records files the index does not list: {extra[:5]}"


def test_build_consumes_the_store_and_never_overwrites_generated_art():
    """The step must fill gaps only.

    An image a generator rebuilt from tracked source art is authoritative;
    restoring over it would silently replace regenerated output with an older
    copy and reintroduce the dependency this store exists to remove.
    """
    source = (REPO / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    start = source.index("def restore_preserved_inherited_art")
    block = source[start : source.index("\ndef ", start + 5)]

    # Present files are recorded and skipped before anything is written.
    assert "if target.is_file():" in block
    assert "already_present.append(rel)" in block
    assert "continue" in block

    # Everything written is digest-checked, and a mismatch stops the build.
    assert "hashlib.sha256(payload).hexdigest() != expected" in block
    assert "raise SystemExit" in block

    # It runs after the generators rather than before them.  Search past the
    # end of the function itself: its own def line contains the same text.
    body_end = source.index(chr(10) + "def ", start + 5)
    call = source.index("    restore_preserved_inherited_art(manifest)", body_end)
    # Compare call sites, not definitions: every one of these names also
    # appears earlier in the file as a "def" line.
    assert source.index("        sync_holiday_body_runtime_frames(manifest)") < call
    assert source.index("    validate_clean_package(manifest)", body_end) > call
