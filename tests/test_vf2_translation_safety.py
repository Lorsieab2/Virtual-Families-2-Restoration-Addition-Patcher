"""The translation-safety rules of the Translations window and its files (ported from the Virtual Families 1 Fun
Patcher's tests/test_translation_safety.py; the pull request checks that file also tests are this repository's
tests/test_translations_folder.py):

1. Names: a player's file never takes the name of one that came with the patcher or from GitHub, the Edit... copy is the
   player's own (never the bare shipped name), Download from GitHub... never takes another translator's file's place,
   and a remembered choice is its source plus its name.
2. Adding (or downloading) a translation replaces an installed one only when the language, @code AND @translator match;
   otherwise both are kept. The replaced one goes to the Recycle Bin (mocked here): nothing is ever deleted for good.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vf2_translation_format as tfmt  # noqa: E402
import vf2_translations as tr  # noqa: E402
import vf2_translations_github as gh  # noqa: E402

REPO = "Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher"
HEAD = "a" * 40
ENTRIES = [tfmt.Entry(tfmt.make_key("strings", "1050", "Done"), "Done")]

def translation(language="Français", code="fr", translator="Ann Lee", text="Terminé") -> bytes:
    f = tfmt.new_file("vf2", ENTRIES, language, code, translator)
    f.rows[0].translation = text
    return tfmt.to_bytes(f)


def write(path: Path, **kw) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(translation(**kw))
    return path


class FakeRecycleBin:
    """tr.recycle stand-in: moves the files into a folder of its own (as the Recycle Bin would)."""

    def __init__(self) -> None:
        self.bin = Path(tempfile.mkdtemp())
        self.calls: list[list[Path]] = []

    def __call__(self, paths, operation=None):
        paths = [Path(p).resolve() for p in paths]
        self.calls.append(paths)
        for n, path in enumerate(paths):
            os.rename(path, self.bin / f"{n}-{path.name}")


@pytest.fixture
def no_plain_delete():
    """Every plain delete patched; the test fails if one is called."""
    with mock.patch.object(Path, "unlink") as unlink, mock.patch("os.remove") as remove, \
            mock.patch("os.unlink") as os_unlink, mock.patch("shutil.rmtree") as rmtree:
        yield
        for plain in (unlink, remove, os_unlink, rmtree):
            plain.assert_not_called()


# ---------------------------------------------------------------------------------------------- 1. workflows



def test_taken_names_include_shipped_and_downloaded_files(tmp_path):
    write(tmp_path / "vf2" / "fr.tsv")
    write(tmp_path / "Virtual Families 2 - Español.txt", language="Español", code="es")
    assert tr.taken_names(tmp_path) == {"vf2", "fr.tsv", "virtual families 2 - español.txt"}
    assert tr.free_name("a.txt", {"b.txt"}) == "a.txt"
    assert tr.free_name("A.txt", {"a.txt", "a (2).txt"}) == "A (3).txt"


def test_an_added_file_never_takes_a_shipped_name(tmp_path):
    shipped = write(tmp_path / "vf2" / "Virtual Families 2 - Français.txt", translator="Old")      # older layout
    source = write(tmp_path / "in" / "mine.txt", translator="Ann")
    target, _report = tr.install_file(source, "vf2", ENTRIES, tmp_path)
    assert target == tmp_path / "Virtual Families 2 - Français (2).txt"
    assert tfmt.parse_bytes(shipped.read_bytes()).translator == "Old"


def test_the_edit_copy_is_the_players_own_and_never_the_bare_shipped_name(tmp_path):
    item = tr.read_info(write(tmp_path / "vf2" / "fr.tsv"), "vf2")
    copy = tr.own_copy_path(item, tmp_path)
    assert copy == tmp_path / "Virtual Families 2 - fr (own copy).txt"
    copy.write_bytes(item.path.read_bytes())
    assert tr.own_copy_path(item, tmp_path) == copy                                    # Edit... again reopens it
    assert copy in [i.path for i in tr.installed("vf2", tmp_path) if not i.shipped]    # listed with the player's
    copy.write_bytes(b"not a translation")
    assert tr.own_copy_path(item, tmp_path) == tmp_path / "Virtual Families 2 - fr (own copy) (2).txt"


@pytest.fixture(scope="module")
def root():
    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"no Tk: {exc}")
    r.withdraw()
    yield r
    r.destroy()


def test_the_window_edits_its_own_copy(root, tmp_path):
    import vf2_translations_window as tw
    shipped = write(tmp_path / "vf2" / "fr.tsv")
    window = tw.TranslationsWindow(root, "vf2", {"vf2": []}, folder=tmp_path, choices_path=tmp_path / "c.json")
    window.entries_cache["vf2"] = ENTRIES
    index = next(n for n, i in enumerate(window.items) if i.path == shipped)
    window.listbox.selection_clear(0, "end")
    window.listbox.selection_set(index + 1)                    # row 0 is English (original)
    with mock.patch.object(tw.messagebox, "askyesno", return_value=True), \
            mock.patch.object(window, "open_editor") as open_editor:
        window.edit()
    opened = open_editor.call_args[0][0]
    assert opened == tmp_path / "Virtual Families 2 - fr (own copy).txt"
    assert opened.read_bytes() == shipped.read_bytes()
    window.close()


def test_the_remembered_choice_is_source_and_name(tmp_path):
    shipped = write(tmp_path / "vf2" / "fr.tsv", translator="Ann")
    mine = write(tmp_path / "fr.tsv", translator="Me")                                # the same bare name
    choices = tmp_path / "choice.json"
    tr.apply_choice("vf2", shipped, [], choices, tmp_path)
    assert tr.load_choices(choices)["vf2"] == "vf2/fr.tsv"
    assert tr.chosen_path("vf2", tr.load_choices(choices), tmp_path) == shipped
    tr.apply_choice("vf2", mine, [], choices, tmp_path)
    assert tr.load_choices(choices)["vf2"] == "fr.tsv"
    assert tr.chosen_path("vf2", tr.load_choices(choices), tmp_path) == mine
    outside = write(tmp_path.parent / (tmp_path.name + "-elsewhere") / "fr.tsv")
    assert tr.relative_name(outside, tmp_path) == str(outside.resolve())
    assert tr.chosen_path("vf2", {"vf2": tr.relative_name(outside, tmp_path)}, tmp_path) == outside.resolve()


def remote(data: bytes, name="fr.tsv") -> gh.Remote:
    language, code, translator = gh.read_remote(name, data, gh.git_blob_sha(data))
    return gh.Remote(name, gh.git_blob_sha(data), len(data), "https://example.invalid/unused", "main",
                     language, code, translator, data=data)


def test_a_download_never_takes_another_translators_file(tmp_path):
    old = write(tmp_path / "vf2" / "fr.tsv", translator="Someone")                  # came with an older patcher
    old_bytes = old.read_bytes()
    choices = tmp_path / "c.json"
    tr.apply_choice("vf2", old, [], choices, tmp_path)
    new = remote(translation(translator="Ann Lee"))
    bin_ = FakeRecycleBin()
    with mock.patch.object(tr, "recycle", bin_):
        [(_r, saved, problem)] = gh.install([new], tmp_path, http=None)
    assert problem == "" and saved == tmp_path / "vf2" / "fr-ann-lee.tsv"
    assert old.read_bytes() == old_bytes and bin_.calls == []
    assert gh.installed_status(new.name, new.sha, tmp_path) == gh.INSTALLED
    with mock.patch.object(tr, "recycle", bin_):
        [(_r, again, _p)] = gh.install([new], tmp_path, http=None)
    assert again == saved                                                             # nothing new
    assert tr.chosen_path("vf2", tr.load_choices(choices), tmp_path) == old          # still Someone's
    assert sorted(p.name for p in (tmp_path / "vf2").iterdir()) == ["fr-ann-lee.tsv", "fr.tsv"]


def test_a_downloaded_name_skips_the_players_names_too(tmp_path):
    write(tmp_path / "vf2" / "fr.tsv", translator="Someone")
    write(tmp_path / "fr-ann-lee.tsv", translator="Me")                              # the player's flat folder
    with mock.patch.object(tr, "recycle", FakeRecycleBin()):
        [(_r, saved, _p)] = gh.install([remote(translation(translator="Ann Lee"))], tmp_path, http=None)
    assert saved.name == "fr-ann-lee-2.tsv"


def test_the_same_translators_download_update_recycles_the_old_version(tmp_path, no_plain_delete):
    old = write(tmp_path / "vf2" / "fr.tsv", translator="Ann Lee", text="Vieux")
    old_bytes = old.read_bytes()
    new = translation(translator="Ann Lee", text="Neuf")
    bin_ = FakeRecycleBin()
    with mock.patch.object(tr, "recycle", bin_):
        [(_r, saved, problem)] = gh.install([remote(new)], tmp_path, http=None)
    assert problem == "" and saved == old and saved.read_bytes() == new
    assert bin_.calls == [[old.resolve()]]
    assert [p.read_bytes() for p in bin_.bin.iterdir()] == [old_bytes]


def test_a_failing_recycle_bin_replaces_nothing_on_download(tmp_path):
    old = write(tmp_path / "vf2" / "fr.tsv", translator="Ann Lee", text="Vieux")
    old_bytes = old.read_bytes()
    with mock.patch.object(tr, "recycle", side_effect=OSError("no bin")):
        [(_r, saved, problem)] = gh.install([remote(translation(translator="Ann Lee"))], tmp_path, http=None)
    assert saved is None and "nothing was replaced" in problem
    assert old.read_bytes() == old_bytes
    assert [p.name for p in (tmp_path / "vf2").iterdir()] == ["fr.tsv"]             # no .download left


# ---------------------------------------------------------------------------------------------- 3. adding


@pytest.fixture
def old(tmp_path):
    return write(tmp_path / "Virtual Families 2 - Français.txt", translator="Ann", text="Vieux")


def add(source: Path, folder: Path):
    bin_ = FakeRecycleBin()
    with mock.patch.object(tr, "recycle", bin_), mock.patch.object(Path, "unlink") as unlink, \
            mock.patch("os.remove") as remove, mock.patch("os.unlink") as os_unlink, \
            mock.patch("shutil.rmtree") as rmtree:
        target, _report = tr.install_file(source, "vf2", ENTRIES, folder)
    for plain in (unlink, remove, os_unlink, rmtree):
        plain.assert_not_called()                                   # nothing is ever deleted for good
    return target, bin_


def test_same_language_code_and_translator_is_an_update(tmp_path, old):
    old_bytes = old.read_bytes()
    source = write(tmp_path / "in" / "new.txt", translator=" ann ", text="Neuf")
    target, bin_ = add(source, tmp_path)
    assert target == old and target.read_bytes() == source.read_bytes()
    assert bin_.calls == [[old.resolve()]]                         # the old one: Recycle Bin
    assert [p.read_bytes() for p in bin_.bin.iterdir()] == [old_bytes]


def test_another_translator_keeps_both(tmp_path, old):
    old_bytes = old.read_bytes()
    target, bin_ = add(write(tmp_path / "in" / "new.txt", translator="Zoe", text="Neuf"), tmp_path)
    assert target == tmp_path / "Virtual Families 2 - Français (by Zoe).txt"
    assert old.read_bytes() == old_bytes and bin_.calls == []
    assert len(tr.installed("vf2", tmp_path)) == 2


def test_another_code_keeps_both(tmp_path, old):
    old_bytes = old.read_bytes()
    target, bin_ = add(write(tmp_path / "in" / "new.txt", code="fr-CA", translator="Ann", text="Neuf"), tmp_path)
    assert target != old and old.read_bytes() == old_bytes and bin_.calls == []


def test_uncredited_files_are_nobodys_update(tmp_path):
    old = write(tmp_path / "Virtual Families 2 - Français.txt", translator="", text="Vieux")
    old_bytes = old.read_bytes()
    target, bin_ = add(write(tmp_path / "in" / "new.txt", translator="", text="Neuf"), tmp_path)
    assert target == tmp_path / "Virtual Families 2 - Français (2).txt"
    assert old.read_bytes() == old_bytes and bin_.calls == []


def test_the_same_bytes_again_change_nothing(tmp_path, old):
    (tmp_path / "in").mkdir()
    source = tmp_path / "in" / "same.txt"
    shutil.copyfile(old, source)
    target, bin_ = add(source, tmp_path)
    assert (target, bin_.calls) == (old, [])
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == ["Virtual Families 2 - Français.txt"]


def test_a_failing_recycle_bin_replaces_nothing(tmp_path, old):
    old_bytes = old.read_bytes()
    source = write(tmp_path / "in" / "new.txt", translator="Ann", text="Neuf")
    with mock.patch.object(tr, "recycle", side_effect=OSError("no bin")), pytest.raises(tr.TranslationProblem):
        tr.install_file(source, "vf2", ENTRIES, tmp_path)
    assert old.read_bytes() == old_bytes

