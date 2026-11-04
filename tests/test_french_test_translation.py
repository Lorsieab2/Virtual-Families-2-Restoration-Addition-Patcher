"""translations/fr.tsv: "(TEST) - French AI Translation" (credit "(TEST) AI translation"), an AI translation of every line the
game and the patches show, for trying the system out.

It is in the repository's public translations/ folder only: a release never ships a "(TEST)" file. Here: it reads with no
error, covers every line of the template of the original game, keeps every placeholder, fits every room, uses French
typography (no-break space before ; : ! ? % and inside the guillemets), and (with the executables and Visual Studio) the
REAL compiled DLL installs it in unicorn on the real game code and refuses no line.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "work"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vf2_translation_format as tf  # noqa: E402
import vf2_translation_strings as ts  # noqa: E402

FR = ROOT / "translations" / "fr.tsv"
VANILLA = os.environ.get("VF2_VANILLA_EXE") or str(ROOT.parent / "vf2" / "work" / "vanilla_runtime_payload" / "Virtual Families 2.exe")
CORE = os.environ.get("VF2_B200_CORE_EXE")
OTHER = os.environ.get("VF2_FINAL_EXE")      # the all-enabled executable: it has every line the patches add
VCVARS = os.environ.get("VF2_VCVARS32")


@pytest.fixture(scope="module")
def parsed():
    return tf.parse_bytes(FR.read_bytes(), "vf2")


def test_the_file_is_named_and_credited_as_a_test(parsed):
    assert parsed.fatal == "" and parsed.language == "(TEST) - French AI Translation"
    assert parsed.code == "fr" and parsed.translator == "(TEST) AI translation"
    assert tf.is_test_file(parsed) and not tf.contains_email(FR.read_text(encoding="utf-8"))


def test_it_reads_with_no_error_and_no_untranslated_line(parsed):
    rows = parsed.rows
    assert len(rows) >= 4000
    assert not [p for p in parsed.problems if p.severity == "error"]
    assert all(r.translation for r in rows), [r.key for r in rows if not r.translation][:5]


def test_it_is_never_shipped():
    sys.path.insert(0, str(ROOT / "work"))
    import export_offline_patch_bundle as X
    assert FR not in X.shipped_translation_files()
    assert all(not tf.is_test_file(tf.parse_bytes(p.read_bytes(), "vf2")) for p in X.shipped_translation_files())


def test_french_typography_everywhere(parsed):
    bad = []
    for r in parsed.rows:
        plain = re.sub(r"\{[^{}]*\}", "", r.translation)
        if re.search(r" [;:!?\u00bb]|\d %|\u00ab ", plain) or '"' in plain or "\u2019" in plain or "\u2026" in plain:
            bad.append(r.key)
    assert not bad, bad[:5]


def test_it_covers_the_template_and_fits_every_room(parsed):
    exe = Path(VANILLA)
    if not exe.is_file():
        pytest.skip("VF2_VANILLA_EXE is not set to the original Virtual Families 2.exe")
    entries = ts.entries_for(exe.read_bytes())
    report = tf.validate(parsed, entries)
    assert report.total == len(entries) and report.translated == len(entries)
    assert not report.errors and not report.warnings and not report.unknown


def test_the_real_dll_installs_every_line(parsed, tmp_path):
    import subprocess
    if not (CORE and OTHER and VCVARS and Path(CORE).is_file() and Path(OTHER).is_file() and Path(VANILLA).is_file()):
        pytest.skip("needs VF2_B200_CORE_EXE, VF2_FINAL_EXE, VF2_VANILLA_EXE and VF2_VCVARS32")
    pytest.importorskip("unicorn")
    env = dict(os.environ, VF2_TR_BUILD_DIR=str(tmp_path))
    r = subprocess.run(["cmd.exe", "/d", "/c", str(ROOT / "runtime" / "native" / "build_b200tr.bat"), "test"], env=env,
                       capture_output=True, text=True)
    dll = tmp_path / "vf2tr_b200_test.dll"
    assert dll.is_file(), r.stdout + r.stderr
    import b200_translations_scenarios as T
    data = FR.read_bytes()
    # the only lines the DLL may refuse: a line this executable has not (an executable built before the line was
    # added: every line is in a template, whatever executable it was made from), or one whose words it rewrote.
    # Since B209 no executable rewrites a stock line of its own (Island Events' spoiled-food result is a record of its
    # own, strings/4084), so on an all-enabled B209 executable nothing is refused.
    table = ts.read_table(Path(OTHER).read_bytes())
    expect_refused = 0
    for row in parsed.rows:
        parts = tf.split_key(row.key)
        if parts and parts[0] == "strings":
            record = table.get(int(parts[1]))
            if record is None or record[1].decode("cp1252") != row.english:
                expect_refused += 1
    for unicode_active in (True, False):
        world = T.World(OTHER, dll, core=CORE)
        assert world.install(data, unicode_active=unicode_active) == 1
        st = world.status()
        assert st["refused"] == expect_refused, world.log()
        assert st["used"] + st["refused"] == len(parsed.rows), st
        assert st["used"] >= 4060, st
        got = world.get_string(113)
        assert got and got != b"Try Again"
