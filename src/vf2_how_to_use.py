"""The patcher window's "?" guides (vf2_how_to_use.json).

One short, plain guide for every button, tool and setting in the patcher window: what it does, how to
use it, and what to watch out for.  The guides are data, kept in one file that ships with the patcher,
keyed by a control key (``back_up_saves``, ``dry_run``, ...).  They are presentation text only and never
change what a patch does.  tests/test_how_to_use.py refuses a control the window shows without a guide,
and a guide that is too long.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

GUIDES_PATH = Path(__file__).resolve().parent / "vf2_how_to_use.json"

# Guides stay short: brief and simple to understand.
MAX_LINES = 8
MAX_LINE_CHARS = 200
MAX_GUIDE_CHARS = 1000


@dataclass(frozen=True)
class Guide:
    title: str
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(self.lines)


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(GUIDES_PATH.read_text(encoding="utf-8"))


def keys() -> list[str]:
    """Every guide key, in the order the guide window lists them."""
    return list(_load()["controls"])


def control_title(key: str) -> str:
    return _load()["controls"][key]["title"]


def section(key: str) -> str:
    return _load()["controls"][key]["section"]


def guide(key: str, title: str | None = None) -> Guide:
    """The guide for ``key``; KeyError when there is none."""
    entry = _load()["controls"][key]
    return Guide(title=title or entry["title"], lines=tuple(entry["guide"]))
