import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "patch_mobile_furniture_pack.py"


def _source():
    return SOURCE.read_text(encoding="utf-8")


def _function_body(source, name):
    match = re.search(
        rf'extern "C" void __cdecl {name}\(CVillager &villager\)\n\{{(?P<body>.*?)\n\}}',
        source,
        re.S,
    )
    if not match:
        raise AssertionError(f"missing generated handler {name}")
    return match.group("body")


class ExerciseBikeLocalizationTests(unittest.TestCase):
    def test_bike_handlers_use_placement_identity_not_global_presence(self):
        source = _source()
        for name in ("VF2ExerciseBikeWalk", "VF2ExerciseBikeRun"):
            with self.subTest(name=name):
                body = _function_body(source, name)
                self.assertIn("VF2LinkedFurnitureItemIs", body)
                self.assertIn("0x04", body)
                self.assertNotIn("VF2AddedFurnitureInWorld", body)

    def test_identity_probe_is_handle_based_and_uses_shared_treadmill_object(self):
        source = _source()
        helper = source[source.index("static bool VF2LinkedFurnitureItemIs"):source.index("// ---- Added furniture")]
        self.assertIn("FindFurniture(", helper)
        self.assertIn("info.unknown0", helper)
        self.assertIn("record + 0x04", helper)
        self.assertIn("return *(int *)record == itemId", helper)
        self.assertIn("object", helper)

    def test_stock_treadmill_label_wrappers_keep_shared_object_and_stock_fallback(self):
        source = _source()
        for name in ("VF2RandomTreadmillWalkLabel", "VF2RandomTreadmillRunLabel"):
            with self.subTest(name=name):
                body = _function_body(source, name)
                self.assertIn("VF2LinkedFurnitureItemIs", body)
                self.assertIn("0x04", body)
                self.assertIn("if (!bike) return;", body)


if __name__ == "__main__":
    unittest.main()
