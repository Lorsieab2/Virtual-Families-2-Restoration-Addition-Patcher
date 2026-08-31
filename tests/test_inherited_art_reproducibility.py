from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile


REPO = Path(__file__).resolve().parents[1]
SOURCE_ARCHIVE = REPO / "data" / "vf2" / "source_assets" / "Holiday Outfits.zip"


def test_holiday_source_archive_is_complete_and_self_contained():
    assert SOURCE_ARCHIVE.is_file()
    with ZipFile(SOURCE_ARCHIVE) as archive:
        names = set(archive.namelist())
    assert len(names) == 488
    for name in (
        "Holiday Outfits/Female Outfits/FemaleBodies_051_0058.png",
        "Holiday Outfits/Female Outfits/FemaleBodies_052_0057.png",
        "Holiday Outfits/Male Outfits/MaleBodies_0051_0058.png",
        "Holiday Outfits/Male Outfits/MaleBodies_0054_0056.png",
    ):
        assert name in names


def test_holiday_generator_has_no_output_or_previous_build_source_fallback():
    source = (REPO / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    roots_block = source[source.index("def _image_source_roots"):source.index("def _find_source_image")]
    assert "OUT / \"Images\"" not in roots_block
    assert "PREVIOUS_BUILD_OUTPUT_GLOBS" not in roots_block
    assert "FALLBACK_HOLIDAY_BODY_BUILD" not in roots_block
    runtime_block = source[source.index("def sync_holiday_body_runtime_frames"):source.index("def _normalize_holiday_detail_body_frame")]
    assert "existing_runtime_frame" not in runtime_block
    assert "expanded_sheet:" not in runtime_block


def test_holiday_generators_fail_when_tracked_source_is_missing():
    source = (REPO / "work" / "patch_mobile_furniture_pack.py").read_text(encoding="utf-8")
    for function_name in ("def sync_holiday_body_types", "def sync_holiday_body_runtime_frames"):
        block_start = source.index(function_name)
        block = source[block_start : source.index("\ndef ", block_start + 5)]
        assert "if not HOLIDAY_OUTFIT_ARCHIVE.is_file():" in block
        assert "raise FileNotFoundError" in block
