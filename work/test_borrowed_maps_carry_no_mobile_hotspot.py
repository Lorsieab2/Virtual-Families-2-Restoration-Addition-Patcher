#!/usr/bin/env python3
"""No shipped map may carry a hotspot id the desktop drop dispatcher cannot hold.

Issue #378: a drop on the Invisible Patio Table crashed with EIP=0x244. The
stock theMainScene::HandleDropOnHotSpot reads the hotspot under the villager's
feet and, when it is non-zero, calls CHotSpot::Dispatch, which indexes its
handler table with no upper bound. The desktop table has handlers for
0x01-0x5B. The borrower maps built by borrowed_fmap_bytes carried the mobile
donor's hotspot ids (0x6B-0x6D) across on every cell the desktop-safe map did
not rewrite, so the index ran off the table into a store cache that holds pet
item ids once the Pets tab has been drawn -- 0x244 is one of them.

The second path to the same fault was the restore record for the 34 behaviour
maps: unticking Mobile Furniture Behaviors on an Enable/Disable run restored
the RAW mobile map instead of the sanitised one Mobile Furniture installs.
"""
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

import export_offline_patch_bundle as exporter
import patch_mobile_furniture_pack as pack

ROOT = Path(__file__).resolve().parents[1]
BEHAVIOR_DIR = ROOT / "patcher_assets" / "optional_patches" / "mobile_furniture_behaviors"
MOBILE_DIR = BEHAVIOR_DIR / "mobile_fmaps"
SAFE_DIR = BEHAVIOR_DIR / "pc_fmaps"


def _cells(data):
    width, height = struct.unpack_from("<II", data, 24)
    return struct.unpack_from("<%dI" % (width * height), data, 32)


def _pairs():
    return [
        (path.name, path.read_bytes(), (SAFE_DIR / path.name).read_bytes())
        for path in sorted(MOBILE_DIR.glob("*.fmap"))
        if (SAFE_DIR / path.name).is_file()
    ]


class TheDecodedBoundary(unittest.TestCase):
    def test_the_field_is_the_one_contentmap_read_decodes(self):
        # CContentMap::Read: shr eax,12h / and eax,7Fh / mov [esi+0Ch],eax
        self.assertEqual(pack.FMAP_HOTSPOT_SHIFT, 0x12)
        self.assertEqual(pack.FMAP_HOTSPOT_MASK, 0x7F << 0x12)
        self.assertEqual(pack.DESKTOP_MAX_HOTSPOT, 0x5B)

    def test_a_mobile_id_is_cleared_and_nothing_else_moves(self):
        other_bits = 0x2000400E  # collision/object bits outside the field
        cell = other_bits | (0x6D << 18)
        self.assertEqual(pack.without_mobile_hotspot(cell), other_bits)

    def test_a_desktop_id_is_kept(self):
        for hotspot in (0x01, 0x2A, 0x5B):
            with self.subTest(hotspot=hex(hotspot)):
                cell = 0x4000 | (hotspot << 18)
                self.assertEqual(pack.without_mobile_hotspot(cell), cell)


class EveryRealBorrowerMap(unittest.TestCase):
    """Run the real merge over every donor that has a desktop-safe map."""

    def test_there_are_donors_to_check(self):
        # A glob that matched nothing would make the checks below vacuous.
        self.assertGreaterEqual(len(_pairs()), 34)

    def test_the_real_donors_do_carry_mobile_ids(self):
        # Proves the check below can fail: the raw donors are exactly what
        # would leak through without the clearing step.
        leaking = [
            name for name, donor, _ in _pairs()
            if any(pack.fmap_cell_hotspot(c) > pack.DESKTOP_MAX_HOTSPOT for c in _cells(donor))
        ]
        self.assertIn("Patio_table.png.fmap", leaking)

    def test_no_merged_cell_carries_a_mobile_hotspot(self):
        for name, donor, safe in _pairs():
            merged = pack.borrowed_fmap_bytes(donor, safe)
            if merged is None:
                continue
            with self.subTest(name):
                bad = [
                    hex(pack.fmap_cell_hotspot(c)) for c in _cells(merged)
                    if pack.fmap_cell_hotspot(c) > pack.DESKTOP_MAX_HOTSPOT
                ]
                self.assertEqual(bad, [], f"{name} carries mobile hotspot ids")

    def test_the_borrower_keeps_the_donors_geometry(self):
        """Clearing the hotspot must not cost the footprint the B180 fix restored."""
        for name, donor, safe in _pairs():
            merged = pack.borrowed_fmap_bytes(donor, safe)
            if merged is None:
                continue
            with self.subTest(name):
                for d, s, m in zip(_cells(donor), _cells(safe), _cells(merged)):
                    if s and s != d:
                        self.assertEqual(m, s)
                    else:
                        self.assertEqual(
                            m & ~pack.FMAP_HOTSPOT_MASK, d & ~pack.FMAP_HOTSPOT_MASK
                        )


class TheBehaviorMapRestore(unittest.TestCase):
    def test_disabling_restores_the_map_mobile_furniture_installs(self):
        names = [path.name for path in sorted(SAFE_DIR.glob("*.fmap"))]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            base = root / "base"
            (base / "Assets").mkdir(parents=True)
            sanitised_dir = bundle / "payload" / "Assets"
            sanitised_dir.mkdir(parents=True)
            installed = []
            for name in names:
                raw = MOBILE_DIR / name
                (base / "Assets" / name).write_bytes(raw.read_bytes())
                # Stand-in for the sanitised map: distinct bytes, no mobile ids.
                sanitised = bytearray(raw.read_bytes())
                grid = _cells(bytes(sanitised))
                struct.pack_into(
                    "<%dI" % len(grid), sanitised, 32,
                    *[pack.without_mobile_hotspot(c) for c in grid],
                )
                (sanitised_dir / name).write_bytes(bytes(sanitised))
                installed.append({
                    "file_path": f"Assets/{name}",
                    "source_path": f"payload/Assets/{name}",
                    "requires": ["mobile_furniture"],
                })
            records = exporter.mobile_furniture_behavior_asset_patches(bundle, base, installed)
            self.assertEqual(len(records), len(names))
            for record in records:
                name = Path(record["file_path"]).name
                with self.subTest(name):
                    restored = (bundle / record["restore_source_path"]).read_bytes()
                    self.assertEqual(restored, (sanitised_dir / name).read_bytes())
                    self.assertEqual(
                        record["restore_source_sha256"], hashlib.sha256(restored).hexdigest()
                    )
                    self.assertFalse(any(
                        pack.fmap_cell_hotspot(c) > pack.DESKTOP_MAX_HOTSPOT
                        for c in _cells(restored)
                    ))

    def test_the_export_passes_the_installed_records(self):
        source = Path(exporter.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "mobile_furniture_behavior_asset_patches(bundle_dir, base_payload, asset_patches)",
            source,
        )


if __name__ == "__main__":
    unittest.main()
