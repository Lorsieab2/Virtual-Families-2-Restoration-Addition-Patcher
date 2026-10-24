"""Release-only tests (scripts/release_only.py): skipped unless `pytest --release` or VF2_RELEASE=1."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "vf2_release_only", Path(__file__).resolve().parents[1] / "scripts" / "release_only.py")
_release_only = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_release_only)

pytest_addoption = _release_only.pytest_addoption
pytest_collection_modifyitems = _release_only.pytest_collection_modifyitems
