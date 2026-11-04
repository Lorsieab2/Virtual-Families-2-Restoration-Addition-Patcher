"""The shared ICU 77-1 word lists (runtime/word-lists) are the coordinator's folder copied unchanged: every file's
SHA-256 and size are the ones its README lists, nothing is added or missing, and the licence is there."""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "runtime" / "word-lists"


def _table():
    rows = {}
    for m in re.finditer(r"^\| `([^`]+)` \| [^|]+ \| ([\d,]+) \| `([0-9a-f]{64})` \|", (FOLDER / "README.md").read_text(encoding="utf-8"), re.M):
        rows[m.group(1)] = (int(m.group(2).replace(",", "")), m.group(3))
    return rows


def test_every_list_is_byte_for_byte_the_shared_one():
    rows = _table()
    assert set(rows) == {"thaidict.txt", "laodict.txt", "khmerdict.txt", "burmesedict.txt", "cjdict.txt",
                         "ICU-LICENSE.txt"}
    for name, (size, sha) in rows.items():
        data = (FOLDER / name).read_bytes()
        assert len(data) == size and hashlib.sha256(data).hexdigest() == sha, name
    assert {p.name for p in FOLDER.iterdir()} == set(rows) | {"README.md"}


def test_the_lists_are_never_changed_by_git():
    assert "runtime/word-lists/** -text" in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()


def test_the_python_and_the_dll_know_the_same_four_lists():
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    import vf2_line_break as LB
    words = (ROOT / "runtime" / "native" / "b200unicode" / "b200words.h").read_text(encoding="utf-8")
    for name in LB.WORD_LIST_FILES:
        assert f'L"{name}"' in words
    for cp, which in ((0x0E01, 0), (0x0E81, 1), (0x1780, 2), (0x19E0, 2), (0x1000, 3), (0xA9E0, 3), (0xAA60, 3),
                      (0x0041, -1), (0x4E00, -1)):
        assert LB.word_list_of(cp) == which
