#!/usr/bin/env python3
"""The B180 documentation has to keep saying what the build actually does.

These are deliberately not prose checks. Each one ties a documented claim to the
thing that would make it false, so that changing the code without changing the
docs fails here rather than shipping a manual that describes a different build.

The distinction that matters most is between the routed and the unrouted added
furniture. Five items are routed through this patcher's own drop dispatcher;
seven rely on the game's native hotspot path and have NOT been confirmed by a
player. A doc that blurs the two would be claiming something the build cannot
support.
"""
import hashlib
import unittest
from pathlib import Path

import patch_mobile_furniture_pack as patcher

ROOT = Path(__file__).resolve().parents[1]

# The published B180 prerelease asset. A fixed historical fact: it is what was
# uploaded, downloaded back and confirmed byte-for-byte, so it is checkable
# from the repository alone without needing the archive present.
PUBLISHED_SHA256 = (
    "31195169252C441AF2C77EDA3AC660E42F2784049F00FE69D75DBF8C8FCA21B7"
)
README = ROOT / "README.md"
TRANSPARENCY = ROOT / "docs" / "Transparency Log.txt"
LEDGER = ROOT / "docs" / "REQUEST_LEDGER.md"

# The dispatcher is written with __VF2_*__ placeholders that only resolve when
# the C is emitted, so route coverage can only be read off the emitted file.
EMITTED = (
    ROOT / "work" / "patched_mobile_furniture_pack_objs" /
    "vf2_mobile_furniture_behaviors.cpp"
)

ROUTED = {
    "InvisiblePicnicTable",
    "InvisiblePatioTable",
    "InvisibleLounger",
    "InvisibleSpaLounger",
    "SpaLoungerStd",
}
UNROUTED = {
    "InvisibleKiddiePool",
    "InvisibleFullSizePool",
    "InvisibleHammock",
    "InvisibleYogaEquipment",
    "ExerciseBikeStd",
    "HomeGymSystemStd",
    "PingPongTableStd",
}


def _added_items():
    items = {}
    for table in (patcher.NEW_FURNITURE_ITEMS, patcher.INVISIBLE_OUTDOOR_ITEMS):
        for item in table:
            items[item["name"]] = item["item_id"]
    return items


class TestTheRoutedAndUnroutedSplitIsReal(unittest.TestCase):
    def test_the_two_sets_cover_every_added_item_exactly_once(self):
        # If an item is added or renamed, this fails and the docs get revisited
        # rather than quietly going stale.
        self.assertEqual(ROUTED | UNROUTED, set(_added_items()))
        self.assertEqual(ROUTED & UNROUTED, set())

    def test_the_docs_do_not_claim_the_unrouted_seven_are_confirmed(self):
        ledger = LEDGER.read_text(encoding="utf-8")
        row = next(
            line for line in ledger.splitlines()
            if "Stock-donor added furniture" in line
        )
        self.assertIn("Needs player confirmation", row)
        self.assertIn("HandleDropOnHotSpot", row)
        # And every one of the seven is named, so none is quietly dropped from
        # the outstanding list.
        for name, item_id in _added_items().items():
            if name in UNROUTED:
                with self.subTest(item=name):
                    self.assertIn(f"0x{item_id:03X}", row)


class TestTheEmittedDispatcherAgreesWithTheDocs(unittest.TestCase):
    """Route coverage is read from the generated C, never from the generator.

    Routes are written as __VF2_*__ placeholders that only resolve at emit
    time, so the Python source cannot answer this. A placeholder that failed to
    substitute would still read correctly in the generator and emit garbage.
    """

    def setUp(self):
        if not EMITTED.is_file():
            self.skipTest(f"{EMITTED.name} has not been generated in this tree")
        text = EMITTED.read_text(encoding="utf-8")
        start = text.index(
            "bool const theMainScene::VF2HandleDropOnMobileFurniture"
        )
        self.dispatcher = text[start:text.index("\n}\n", start)]
        self.text = text

    def test_no_placeholder_survived_into_the_dispatcher(self):
        # The failure this guards against emits the placeholder literally and
        # still passes every test that reads the generator.
        self.assertNotIn("__VF2_", self.dispatcher)

    def test_the_four_directly_routed_items_are_present(self):
        items = _added_items()
        for name in (
            "InvisiblePicnicTable",
            "InvisiblePatioTable",
            "InvisibleSpaLounger",
            "SpaLoungerStd",
        ):
            with self.subTest(item=name):
                self.assertIn(f"{items[name]:#x}".lower(), self.dispatcher.lower())

    def test_the_invisible_lounger_is_routed_through_the_chaise_family(self):
        # It has no `candidate ==` line on purpose: folding it into the chaise
        # test means it picks up chaise behaviours added later too.
        items = _added_items()
        self.assertIn("VF2IsMobileChaise", self.dispatcher)
        start = self.text.index("static bool VF2IsMobileChaise")
        chaise = self.text[start:self.text.index("\n}", start)]
        self.assertIn(f"{items['InvisibleLounger']:#x}".lower(), chaise.lower())

    def test_the_seven_stock_donor_items_have_no_dispatcher_route(self):
        # Not a defect -- they are handled by the native hotspot path. Pinned
        # so that adding a route here without updating the docs fails.
        items = _added_items()
        for name in sorted(UNROUTED):
            with self.subTest(item=name):
                self.assertNotIn(
                    f"candidate == {items[name]:#x}".lower(),
                    self.dispatcher.lower(),
                )


class TestTheStockDonorsAreNotTheChaiseCase(unittest.TestCase):
    """The seven stock-donor items are not affected by the #135 defect.

    #135 fixed borrowers of donors that Mobile Furniture Behaviors implements:
    those donors ship two maps, and the borrower was taking the raw mobile one.
    The seven here borrow stock desktop furniture, which that patch does not
    implement, so no second map exists and there is nothing to translate.
    """

    PC_FMAPS = (
        ROOT / "patcher_assets" / "optional_patches" /
        "mobile_furniture_behaviors" / "pc_fmaps"
    )

    def _donor_fmap(self, name):
        for table in (
            patcher.NEW_FURNITURE_ITEMS, patcher.INVISIBLE_OUTDOOR_ITEMS
        ):
            for item in table:
                if item["name"] == name:
                    return item.get("donor_fmap")
        raise KeyError(name)

    def test_no_stock_donor_has_a_desktop_safe_map_to_take(self):
        # This is the whole reason they are a different case. If one of these
        # donors ever gains a pc_fmaps entry, it joins the #135 family and this
        # test fails rather than letting it ship the wrong map silently.
        if not self.PC_FMAPS.is_dir():
            self.skipTest("pc_fmaps directory is not present in this tree")
        for name in sorted(UNROUTED):
            donor = self._donor_fmap(name)
            with self.subTest(item=name, donor=donor):
                self.assertIsNotNone(donor, f"{name} has no donor_fmap")
                self.assertFalse(
                    (self.PC_FMAPS / donor).is_file(),
                    f"{donor} now ships a desktop-safe map, so {name} must "
                    f"take that instead of the donor's own file -- see #135",
                )

    def test_the_routed_borrowers_do_have_one(self):
        # The mirror image, so the test above cannot pass by the directory
        # simply being empty or misnamed.
        if not self.PC_FMAPS.is_dir():
            self.skipTest("pc_fmaps directory is not present in this tree")
        for name in ("InvisibleLounger", "InvisibleSpaLounger"):
            donor = self._donor_fmap(name)
            with self.subTest(item=name, donor=donor):
                self.assertTrue(
                    (self.PC_FMAPS / donor).is_file(),
                    f"{donor} should ship a desktop-safe map",
                )


class TestTransparencyLogMatchesTheBuild(unittest.TestCase):
    def test_it_records_the_b180_sections(self):
        text = TRANSPARENCY.read_text(encoding="utf-8")
        for heading in (
            "B180 added furniture drop routing",
            "B180 added-furniture action labels",
            "B180 store checkmarks from live state",
            "B180 hairstyle store icons",
            "B180 Spa Lounger",
            "B180 picnic and patio props not shipped",
            "B180 verification method",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, text)

    def test_the_props_entry_states_the_real_engine_bound(self):
        # The bound is why the props are absent. If someone later raises it,
        # this sentence has to change with it.
        text = TRANSPARENCY.read_text(encoding="utf-8")
        self.assertIn("0x00 through 0x54 only", text)
        self.assertIn("0x55", text)
        self.assertIn("0x56", text)

    def test_the_unbuilt_claim_is_kept_and_marked_superseded(self):
        """The log said no bundle was packaged. That was true when written.

        B180 is published, so that sentence is now false, and a transparency
        log asserting something untrue about its own release is worse than one
        that says nothing. The original line is KEPT -- deleting it would erase
        what was said at the time, which is the opposite of what the log is
        for, and the same principle as keeping the original ZIP when a
        corrected one is added -- and must carry the correction beside it.

        Deliberately NOT conditional on the archive existing. An earlier
        version required the correction only when outputs/ held a build, so it
        passed on this machine and would have failed on a clean checkout. A
        check that only runs where the artifact happens to live is not a
        check; B180 being published is a fixed historical fact, readable from
        the repository alone.
        """
        text = TRANSPARENCY.read_text(encoding="utf-8")
        claim = "No B180 bundle is linked, packaged, or published"
        self.assertIn(claim, text, "the original claim must be kept for the record")

        # Scope every remaining assertion to the passage that follows the
        # claim. Checking the whole file would accept a SUPERSEDED marker or a
        # digest sitting in an unrelated entry -- the correction would then be
        # satisfied by text that says nothing about it, which is the same
        # wrong-authority mistake as reading a count off the exporter instead
        # of the bundle.
        correction = text.split(claim, 1)[1].split(chr(10) + "B180 ", 1)[0]
        self.assertIn("SUPERSEDED", correction,
                      "the claim is false now and must carry its correction beside it")
        # The correction must be CHECKABLE, not a bare admission that the
        # earlier line was wrong. Naming the published SHA-256 is what lets a
        # reader confirm WHICH artifact it is about.
        self.assertIn(PUBLISHED_SHA256, correction,
                      "the correction must identify the published artifact by digest")
        self.assertIn("B180 shipped artifact", text)

    def test_the_shipped_digest_matches_the_archive_on_disk(self):
        """A digest typed into a doc is a claim; check it against the file."""
        archive = ROOT / "outputs" / "VF2-B180-Release.zip"
        if not archive.is_file():
            self.skipTest("no B180 archive in this tree")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest().upper()
        self.assertIn(digest, TRANSPARENCY.read_text(encoding="utf-8"))


class TestTheDocumentedPropBoundIsReal(unittest.TestCase):
    """The prop bound is asserted against Environment.obj, not from memory."""

    OBJ = ROOT / "work" / "desktop_obj_files" / "Environment.obj"

    def test_setprop_still_rejects_the_two_props_we_need(self):
        if not self.OBJ.is_file():
            self.skipTest(
                "Environment.obj is a gitignored build input; not present here"
            )
        data = self.OBJ.read_bytes()
        # cmp edi, 54h -- the bound the docs quote.
        pattern = b"\x83\xff\x54"
        hits = [
            i for i in range(len(data) - len(pattern) + 1)
            if data[i:i + len(pattern)] == pattern
        ]
        # Refuse to guess. A checker that picks the first of several matches is
        # worse than no checker.
        self.assertEqual(
            len(hits), 1,
            f"expected exactly one `cmp edi,54h`, found {len(hits)}",
        )
        # Followed by a JA -- short (77) or near (0F 87). Reading a fixed
        # offset would be wrong if the encoding changed, so accept either.
        after = data[hits[0] + len(pattern):hits[0] + len(pattern) + 2]
        self.assertTrue(
            after[:1] == b"\x77" or after[:2] == b"\x0f\x87",
            f"expected a JA after the compare, found {after.hex()}",
        )
        # And the two props really do fall outside it.
        self.assertGreater(0x55, 0x54, "ePropPicnicReady is out of range")
        self.assertGreater(0x56, 0x54, "ePropPatioDrinks is out of range")

    def test_the_docs_quote_the_bound_that_is_actually_there(self):
        ledger = LEDGER.read_text(encoding="utf-8")
        transparency = TRANSPARENCY.read_text(encoding="utf-8")
        for name, text in (("ledger", ledger), ("transparency", transparency)):
            with self.subTest(doc=name):
                self.assertIn("0x55", text)
                self.assertIn("0x56", text)
                self.assertIn("54h", text)


class TestReadmeMatchesTheBuild(unittest.TestCase):
    def test_it_describes_the_added_furniture_counts(self):
        text = README.read_text(encoding="utf-8")
        invisible = len(patcher.INVISIBLE_OUTDOOR_ITEMS)
        visible = len(patcher.NEW_FURNITURE_ITEMS)
        self.assertIn(f"Eight outdoor pieces", text)
        self.assertEqual(invisible, 8, "README says eight invisible pieces")
        self.assertIn("Four new visible furniture items", text)
        self.assertEqual(visible, 4, "README says four new visible items")

    def test_it_lists_the_labels_that_actually_ship(self):
        text = README.read_text(encoding="utf-8")
        for label in (
            "Playing ping-pong",
            "Using the exercise bike",
            "Doing high-intensity cycling",
        ):
            with self.subTest(label=label):
                self.assertIn(label, text)

    def test_the_removed_label_is_gone_from_docs_and_source(self):
        # Removed at the owner's request. A doc still advertising it would be
        # describing a build that no longer exists.
        source = (ROOT / "work" / "patch_mobile_furniture_pack.py").read_text(
            encoding="utf-8"
        )
        for name, text in (
            ("README", README.read_text(encoding="utf-8")),
            ("patch source", source),
        ):
            with self.subTest(where=name):
                self.assertNotIn("Rallying back and forth", text)

    def test_the_checkmark_section_names_the_reversible_rows(self):
        text = README.read_text(encoding="utf-8")
        self.assertIn("Which store rows show a checkmark", text)
        # The point of the section is that drawing and clicking disagree on
        # purpose; losing that sentence loses the reason.
        self.assertIn("still reads the real answer", text)


class TestHairstyleIconDocsMatchTheConstants(unittest.TestCase):
    def test_the_documented_frame_is_the_one_the_build_cuts(self):
        text = TRANSPARENCY.read_text(encoding="utf-8")
        frame = patcher.HEAD_STORE_ICON_FRAME
        count = patcher.HEAD_STORE_ICON_FRAME_COUNT
        width, height = patcher.HEAD_STORE_ICON_CELL_SIZE
        self.assertIn(f"frame {frame} of {count}", text)
        self.assertIn(f"{width}x{height}", text)

    def test_the_engine_cell_is_still_documented_as_retained(self):
        # It stays correct for indexing even though it is wrong for cutting,
        # which is exactly the confusion that caused the sliced icons.
        text = TRANSPARENCY.read_text(encoding="utf-8")
        cell_w, cell_h = patcher.HEAD_STORE_CELL_SIZE
        self.assertIn(f"{cell_w}x{cell_h}", text)
        self.assertNotEqual(
            patcher.HEAD_STORE_CELL_SIZE, patcher.HEAD_STORE_ICON_CELL_SIZE
        )


if __name__ == "__main__":
    unittest.main()
