"""Release-only tests (scripts/release_only.py): skipped unless `pytest --release` or VF2_RELEASE=1."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "vf2_release_only", Path(__file__).resolve().parents[1] / "scripts" / "release_only.py")
_release_only = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_release_only)

pytest_addoption = _release_only.pytest_addoption
pytest_collection_modifyitems = _release_only.pytest_collection_modifyitems


def pytest_configure(config):
    """The player's saves are read-only: no test may write Family Logs outside a temp folder."""
    import sys
    import tempfile
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    try:
        import vf2_family_logs
    except ImportError:
        return
    temp = Path(tempfile.gettempdir()).resolve()

    def guarded(function):
        def call(folder, *args, **kwargs):
            if folder is not None and temp not in Path(folder).resolve().parents:
                raise RuntimeError(f"a test tried to write Family Logs outside the temp folder: {folder}")
            return function(folder, *args, **kwargs)
        return call

    vf2_family_logs.update_all = guarded(vf2_family_logs.update_all)
    vf2_family_logs.update_save_folder = guarded(vf2_family_logs.update_save_folder)
    vf2_family_logs.update_slot = guarded(vf2_family_logs.update_slot)
