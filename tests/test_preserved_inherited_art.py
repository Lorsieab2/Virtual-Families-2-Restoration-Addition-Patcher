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


# --- behavioural: exercise the step rather than reading its source ---------
#
# The module runs a full build when executed as a script, so it is compiled
# and exec'd once here with __name__ set to something other than "__main__",
# and the three paths it reads are redirected at a temporary tree.

import hashlib as _hashlib
import json as _json
import tempfile
from pathlib import Path as _Path

import pytest


def _load_step():
    source = (REPO / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    namespace = {
        "__name__": "patch_pack_under_test",
        "__file__": str(REPO / "work" / "patch_mobile_furniture_pack.py"),
    }
    exec(compile(source, "patch_mobile_furniture_pack.py", "exec"), namespace)
    return namespace


@pytest.fixture(scope="module")
def step():
    return _load_step()


def _run(step, store, index, out):
    step["PRESERVED_INHERITED_ART"] = store
    step["INHERITED_ONLY_INDEX"] = index
    step["OUT"] = out
    manifest = {}
    step["restore_preserved_inherited_art"](manifest)
    return manifest["preserved_inherited_art"]


def _tree(tmp_path, files, index_names, digests):
    store = tmp_path / "store"
    store.mkdir()
    for name, payload in files.items():
        target = store / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    (store / "SHA256SUMS.json").write_text(_json.dumps({"files": digests}), encoding="utf-8")
    index = tmp_path / "index.json"
    index.write_text(_json.dumps({"files": index_names}), encoding="utf-8")
    out = tmp_path / "out"
    (out / "Images").mkdir(parents=True)
    return store, index, out


def test_missing_from_store_stops_the_build(step, tmp_path):
    store, index, out = _tree(tmp_path, {}, ["Gone.png"], {})
    with pytest.raises(SystemExit) as caught:
        _run(step, store, index, out)
    assert "absent from both the build and the tracked store" in str(caught.value)


def test_a_file_with_no_recorded_digest_is_never_written(step, tmp_path):
    store, index, out = _tree(tmp_path, {"Thing.png": b"art"}, ["Thing.png"], {})
    with pytest.raises(SystemExit) as caught:
        _run(step, store, index, out)
    assert "no recorded digest" in str(caught.value)
    assert not (out / "Images" / "Thing.png").exists()


def test_a_corrupted_file_is_never_written(step, tmp_path):
    store, index, out = _tree(tmp_path, {"Thing.png": b"art"}, ["Thing.png"], {"Thing.png": "0" * 64})
    with pytest.raises(SystemExit) as caught:
        _run(step, store, index, out)
    assert "does not match its recorded digest" in str(caught.value)
    assert not (out / "Images" / "Thing.png").exists()


def test_a_verified_file_is_restored(step, tmp_path):
    digest = _hashlib.sha256(b"art").hexdigest()
    store, index, out = _tree(tmp_path, {"Thing.png": b"art"}, ["Thing.png"], {"Thing.png": digest})
    record = _run(step, store, index, out)
    assert record["restored"] == 1
    assert (out / "Images" / "Thing.png").read_bytes() == b"art"


def test_generated_art_is_never_overwritten(step, tmp_path):
    digest = _hashlib.sha256(b"art").hexdigest()
    store, index, out = _tree(tmp_path, {"Thing.png": b"art"}, ["Thing.png"], {"Thing.png": digest})
    (out / "Images" / "Thing.png").write_bytes(b"GENERATED FROM SOURCE")
    record = _run(step, store, index, out)
    assert record["restored"] == 0
    assert record["already_present"] == 1
    assert (out / "Images" / "Thing.png").read_bytes() == b"GENERATED FROM SOURCE"


def test_non_runtime_split_matches_the_exporter_classifier():
    """The recorded split must not drift from the exporter's own rule.

    The bundle exporter decides what is editing source rather than runtime
    art; if this list and that rule disagree, a build restores files the
    bundle then refuses to ship, or omits ones it needs.
    """
    import sys

    sys.path.insert(0, str(REPO / "work"))
    from export_offline_patch_bundle import is_non_runtime_source_path

    index = _json.loads(INDEX.read_text(encoding="utf-8"))
    recorded = set(index["non_runtime_files"])
    derived = {
        rel
        for rel in index["files"]
        if is_non_runtime_source_path(_Path("Images") / rel)
    }
    assert recorded == derived
    assert index["runtime_count"] == len(index["files"]) - len(recorded)


def test_non_runtime_sources_are_never_restored(step, tmp_path):
    """.xcf and the Upgrades working folders are ~47 MB of editing sources."""
    payload = b"working file"
    digest = _hashlib.sha256(payload).hexdigest()
    names = ["Map.xcf", "Upgrades/invisible images/Thing.png", "Real.png"]
    store, index, out = _tree(
        tmp_path,
        {name: payload for name in names},
        names,
        {name: digest for name in names},
    )
    index.write_text(
        _json.dumps({"files": names, "non_runtime_files": names[:2]}), encoding="utf-8"
    )
    record = _run(step, store, index, out)
    assert record["restored"] == 1
    assert record["skipped_non_runtime"] == 2
    assert (out / "Images" / "Real.png").is_file()
    assert not (out / "Images" / "Map.xcf").exists()
    assert not (out / "Images" / "Upgrades" / "invisible images" / "Thing.png").exists()


def test_a_broken_checkout_stops_the_build(step, tmp_path):
    store, index, out = _tree(tmp_path, {}, [], {})
    for missing in (store, index):
        with pytest.raises(SystemExit) as caught:
            if missing is store:
                _run(step, tmp_path / "no-store", index, out)
            else:
                _run(step, store, tmp_path / "no-index.json", out)
        assert "missing from this checkout" in str(caught.value)


def test_build_playtest_validates_runtime_art_only():
    """Otherwise it fails every build that correctly omits editing sources."""
    script = (REPO / "work" / "build_playtest.ps1").read_text(encoding="utf-8")
    assert "non_runtime_files" in script
    assert "$nonRuntimeInherited.ContainsKey($_)" in script
