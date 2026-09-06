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
        # The point is that the row must not present these seven as working.
        # The status wording is allowed to change as the investigation moves
        # on -- it began as "Needs player confirmation" and became "Premise
        # disproved / route needed" once the owner reported the Home Gym does
        # nothing -- so this asserts the CLAIM, not one particular phrasing.
        status = row.split("|")[2].strip()
        self.assertNotEqual(status, "", "the row lost its status column")
        # An ALLOW-LIST, not a blacklist. Enumerating three phrasings let
        # "Verified", "Working / player-confirmed" or "Implemented" through,
        # each of which presents the unrouted items as working -- the exact
        # error this test exists to prevent. The status must instead say
        # plainly that something is unresolved.
        unresolved = (
            "premise disproved", "route needed", "needs", "pending",
            "partial", "not started", "blocked", "outstanding",
            "unrouted", "in progress", "not yet", "deliberately not",
        )
        self.assertTrue(
            any(word in status.lower() for word in unresolved),
            f"the status {status!r} does not say anything is still "
            "unresolved, so it reads as working. The seven items are not "
            "routed through HandleDropOnHotSpot and the owner has reported "
            "the Home Gym System does nothing. If they genuinely now work, "
            "this test is the wrong thing to edit -- the route is.",
        )
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


class TestThePropBlockerIsNamedAccurately(unittest.TestCase):
    """The props row must not blame missing artwork that exists.

    The row previously said the two props "have no desktop art". Images/meal.png
    ships with the base game and sits in the runtime payload, so meal art is
    not what blocks this. The real obstacle is the SetProp dispatch table --
    every case claimed, every jump entry a DIR32 relocation -- plus the absence
    of a drinks sprite.

    That distinction decides what the owner is being asked. "The art does not
    exist" invites them to supply art that would still not render; "the
    dispatch table is full" is the actual question.
    """

    LEDGER = ROOT / "docs" / "REQUEST_LEDGER.md"
    MEAL = ROOT / "work" / "vanilla_runtime_payload" / "Images" / "meal.png"

    def _row(self):
        for line in self.LEDGER.read_text(encoding="utf-8").splitlines():
            if line.startswith("|") and "Picnic and patio table props" in line:
                return line
        self.fail("the picnic/patio props row is gone from the ledger")

    def test_the_row_does_not_claim_the_meal_art_is_missing(self):
        """The phrase may appear only as a quotation of the old claim.

        A blunt "this string is absent" check cannot tell an assertion from a
        correction that quotes what it is correcting -- it failed on the very
        sentence retracting the claim. So the requirement is that wherever the
        phrase appears, the retraction appears too.
        """
        row = self._row()
        if "have no desktop art" in row:
            self.assertIn(
                "previously claimed", row,
                "the row still asserts the props have no desktop art; meal.png "
                "ships with the base game, so that must be a quoted retraction "
                "rather than a live claim",
            )

    def test_the_row_names_the_real_obstacle(self):
        """The row must explain WHY the props did not draw, not just that they did not.

        This originally required the row to name the art that exists and the
        dispatch-table obstacle, because at the time the obstacle was the
        whole story. Four defects were later found and fixed, so the row now
        explains those instead -- but the requirement is unchanged in
        substance: a reader must be able to tell what was actually wrong.
        """
        row = self._row()
        self.assertIn(
            "meal", row.lower(),
            "the row should say which art is involved",
        )
        for cause in ("descriptor", "conditional", "hotspot"):
            self.assertIn(
                cause, row.lower(),
                f"the row does not mention the {cause} defect, so a reader "
                "cannot tell what was actually wrong",
            )

    def test_the_meal_art_really_is_in_the_payload(self):
        """The claim above is only safe while this holds."""
        if not self.MEAL.parent.is_dir():
            self.skipTest("vanilla_runtime_payload is a gitignored build input")
        self.assertTrue(
            self.MEAL.is_file(),
            "the ledger says meal.png is in the payload; it is not",
        )


class TestBothPropBoundsAreReal(unittest.TestCase):
    """Two independent limits agree on 85 props. Both are pinned.

    The docs used to name only SetProp's `cmp edi,54h`. CEnvironment::Update
    ends its loop with `cmp edi,55h` / `jl`, walking the same 0x00-0x54 range.
    Recording only one of them understates what raising the bound costs: the
    two agree today, and changing either alone desynchronises the array from
    the code that iterates it.

    The 0x55 is also the exact value most likely to be misread as a free slot
    for ePropPicnicReady. It is a loop terminator, not an index. This test
    exists partly so that misreading fails here rather than propagating into
    a change that walks off the end of the array.
    """

    OBJ = ROOT / "work" / "desktop_obj_files" / "Environment.obj"
    SETPROP_CMP = bytes((0x83, 0xFF, 0x54))   # cmp edi, 54h
    UPDATE_CMP = bytes((0x83, 0xFF, 0x55))    # cmp edi, 55h
    JA = bytes((0x0F, 0x87))                  # reject above
    JL = bytes((0x0F, 0x8C))                  # loop back while below

    def _obj(self):
        # Presence is decided by the DIRECTORY, not by one file inside it.
        if not self.OBJ.parent.is_dir():
            self.skipTest("desktop_obj_files is a gitignored build input")
        if not self.OBJ.is_file():
            self.fail(
                "desktop_obj_files exists but Environment.obj is missing "
                "from it. That is a damaged build input, not an absent one."
            )
        return self.OBJ.read_bytes()

    def _sole(self, data, pattern, label):
        hits = [
            i for i in range(len(data) - len(pattern) + 1)
            if data[i:i + len(pattern)] == pattern
        ]
        self.assertEqual(
            len(hits), 1,
            f"expected exactly one {label}, found {len(hits)}; a checker that "
            "picks the first of several is guessing",
        )
        return hits[0]

    def test_setprop_still_rejects_above_0x54(self):
        data = self._obj()
        at = self._sole(data, self.SETPROP_CMP, "SetProp bound")
        self.assertEqual(
            data[at + 3:at + 5], self.JA,
            "SetProp must still REJECT ids above the bound",
        )

    def test_update_still_iterates_to_0x55_exclusive(self):
        data = self._obj()
        at = self._sole(data, self.UPDATE_CMP, "Update bound")
        self.assertEqual(
            data[at + 3:at + 5], self.JL,
            "Update's 0x55 must remain an EXCLUSIVE loop limit; if this ever "
            "reads as an index there is one more prop slot than the docs say",
        )

    def test_the_two_bounds_describe_the_same_array(self):
        """SetProp admits <= 0x54, Update walks < 0x55: the same 85 entries.

        If a future build makes these disagree, both the documentation and the
        interception in VF2PatioSetPropAndTrack are reasoning about an array
        that no longer exists in that shape.
        """
        data = self._obj()
        self._sole(data, self.SETPROP_CMP, "SetProp bound")
        self._sole(data, self.UPDATE_CMP, "Update bound")

    def test_the_log_records_both_bounds(self):
        text = TRANSPARENCY.read_text(encoding="utf-8")
        self.assertIn("the prop bound is TWO limits", text)
        self.assertIn(
            "0xce4f", text,
            "the Update bound's address belongs in the record; without it the "
            "second limit cannot be re-checked",
        )


class TestTheReadmeIsHonestAboutTheProps(unittest.TestCase):
    """A player enabling the tables must not be promised props that do not draw.

    The behaviours ship and work; the meal and drinks sprites do not appear.
    Saying only the former in the place a player reads before enabling the
    setting is the kind of half-true that reads as a bug report waiting to
    happen.

    This is tied to the ledger rather than to a fixed sentence, so that when
    rendering does land, whichever of the two is updated first fails until the
    other follows.
    """

    WARNING = "do not yet appear"

    def _rendering_pending(self):
        ledger = LEDGER.read_text(encoding="utf-8")
        row = next(
            line for line in ledger.splitlines()
            if line.startswith("| Picnic and patio table props")
        )
        return "rendering pending" in row.lower()

    def test_the_readme_warns_while_rendering_is_pending(self):
        """Conditional, so the transition is not blocked forever.

        An unconditional requirement for the warning phrase would keep this
        suite failing on the day rendering lands and both documents are
        correctly updated together -- turning the guard into an obstacle to
        the very change it is meant to shepherd. It applies only while the
        ledger says rendering is still pending.
        """
        if not self._rendering_pending():
            self.skipTest("the ledger says rendering has landed")
        self.assertIn(self.WARNING, README.read_text(encoding="utf-8"))

    def test_the_shipped_setting_description_warns_too(self):
        """The README is not what a player reads before enabling the setting.

        Someone who downloads the release and runs Launch_GUI.bat never opens
        this repository. The GUI renders the manifest description generated
        from export_offline_patch_bundle, and that text names the Patio and
        Picnic Tables. Warning only in the repo README leaves the packaged
        flow -- the normal one -- still misleading.
        """
        import sys

        sys.path.insert(0, str(ROOT / "work"))
        import export_offline_patch_bundle as exporter

        description = next(
            row["description"] for row in exporter.SETTINGS
            if row["id"] == "mobile_furniture_behaviors"
        )
        # Compared, not skipped. Skipping once the ledger flips would leave
        # the GUI still telling players drawing is "in progress and not in
        # this release" while the ledger and README both said it had landed --
        # green suite, three documents disagreeing, and the one a player reads
        # being the wrong one.
        # Checked against EVERY pending-state phrase, not one substring.
        # Using "stays bare" alone as the proxy meant the description could
        # drop that phrase while still telling players the props "do not
        # appear" and that drawing was "not in this release" -- the check
        # would go green with two stale claims still shipping in the text a
        # player actually reads.
        pending_phrases = (
            "stays bare", "do not appear", "does not appear",
            "not in this release", "in progress and is not",
        )
        still_claims_pending = [
            phrase for phrase in pending_phrases if phrase in description
        ]
        self.assertEqual(
            self._rendering_pending(),
            bool(still_claims_pending),
            "the shipped setting description and the ledger disagree about "
            "whether the props draw; update both together. The description "
            f"still carries {still_claims_pending!r} while the ledger says "
            f"rendering pending is {self._rendering_pending()}",
        )

    def test_the_readme_and_the_ledger_agree(self):
        self.assertEqual(
            self._rendering_pending(),
            self.WARNING in README.read_text(encoding="utf-8"),
            "the ledger and the README disagree about whether the props "
            "render; update both together",
        )


if __name__ == "__main__":
    unittest.main()
