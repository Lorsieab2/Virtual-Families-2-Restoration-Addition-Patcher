"""A release ships the accepted translations of the repository's public translations/ folder, never a "(TEST)" one.

The bundle exporter (work/export_offline_patch_bundle.py, shipped_translation_files / write_bundle_runner_files) copies
every usable .tsv into "<Patcher Files>/translations/vf2/", where the Translations window lists it as one that came with
the patcher. A test file (its language name or its credit starts with "(TEST)", or its file name says so), a file the
format refuses (an email address anywhere, another game) and anything that is not a .tsv directly in the folder stay
in the repository.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "work"))

import export_offline_patch_bundle as X  # noqa: E402
import vf2_translation_format as tfmt  # noqa: E402

ENTRIES = [tfmt.Entry(tfmt.make_key("strings", "113", "Try Again"), "Try Again")]


def tsv(folder: Path, name: str, language="Français", code="fr", translator="Ann Lee", text="Réessayer") -> Path:
    f = tfmt.new_file("vf2", ENTRIES, language, code, translator)
    f.rows[0].translation = text
    path = folder / name
    path.write_bytes(tfmt.to_bytes(f))
    return path


def test_only_accepted_translations_are_shipped(tmp_path):
    tsv(tmp_path, "fr.tsv")
    tsv(tmp_path, "de.tsv", "Deutsch", "de", "Bob", "Nochmal")
    tsv(tmp_path, "es.tsv", "(TEST) - Español", "es", "Someone")                    # the language says test
    tsv(tmp_path, "it.tsv", "Italiano", "it", "(TEST) AI translation")                   # the credit says test
    tsv(tmp_path, "pt-(TEST).tsv", "Português", "pt", "Cy")                          # the file name says test
    tsv(tmp_path, "nl.tsv", "Nederlands", "nl", "Dee", "Probeer opnieuw me@example.com")  # an email address anywhere
    (tmp_path / "broken.tsv").write_bytes(b"not a translation")
    (tmp_path / "notes.txt").write_text("not a .tsv", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Translations", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    tsv(tmp_path / "sub", "ja.tsv", "日本語", "ja", "Eve")                    # not directly in the folder
    assert [p.name for p in X.shipped_translation_files(tmp_path)] == ["de.tsv", "fr.tsv"]


def test_the_repositorys_own_translations_folder_ships_no_test_file():
    for path in X.shipped_translation_files():
        parsed = tfmt.parse_bytes(path.read_bytes(), "vf2")
        assert not tfmt.is_test_file(parsed) and "(test)" not in path.name.casefold(), path


def test_a_missing_folder_ships_nothing(tmp_path):
    assert X.shipped_translation_files(tmp_path / "nowhere") == []


def test_the_bundle_gets_the_accepted_ones_and_never_a_test_one(tmp_path, monkeypatch):
    source = tmp_path / "translations"
    source.mkdir()
    tsv(source, "fr.tsv")
    tsv(source, "xx.tsv", "(TEST) - Test", "xx", "(TEST) AI translation")
    monkeypatch.setattr(X, "TRANSLATIONS_SOURCE_DIR", source)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    files = X.write_bundle_runner_files(bundle, "B208")
    assert f"{X.PATCHER_FILES_FOLDER}/translations/vf2/fr.tsv" in files
    assert not any("xx.tsv" in name for name in files)
    shipped = bundle / X.PATCHER_FILES_FOLDER / "translations" / "vf2"
    assert [p.name for p in shipped.iterdir()] == ["fr.tsv"]
    assert (shipped / "fr.tsv").read_bytes() == (source / "fr.tsv").read_bytes()
    # exporting again over the bundle clears them first (a withdrawn translation does not linger)
    X.clear_generated_runner_files(bundle)
    assert not shipped.exists() and not (bundle / X.PATCHER_FILES_FOLDER / "translations").exists()
