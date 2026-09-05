#!/usr/bin/env python3
"""The stock drop path cannot identify an added item -- and a parser trap.

Seven added items were left out of the mobile drop dispatcher on the argument
that they borrow stock furniture, so theMainScene::HandleDropOnHotSpot reaches
them natively. The owner reported that the Home Gym System does nothing.

ONE finding disproves the argument, and it is about the executable:
HandleDropOnHotSpot never reads a furniture item id.

A SECOND claim -- that the donor maps carry identical vocabularies and so
cannot tell items apart -- was WRONG, and these tests pin the reason, because
the mistake is repeatable by anyone who opens the obvious directory.

Two containers share these filenames:

    work/assets/TextAsset/                  FMP4   828 bytes  15x13   mobile
    .../Original Virtual Families 2 Assets/ QAMF   312 bytes  11x6    desktop

The desktop QAMF map is what the patched game loads. Parsing the mobile FMP4
bytes with the desktop field extraction still RETURNS numbers -- they are just
meaningless -- and it produced a uniform, tidy result across hundreds of
heterogeneous files, which is evidence of a parser reading the wrong thing
rather than evidence of uniformity in the data.

So the fmap tests here refuse any file failing the QAMF magic check, and the
decoder is validated against this patcher's own pinned constants before being
trusted for anything.

The desktop maps come from the player's own game install and live under
work/vanilla_runtime_payload, which .gitignore excludes. A fresh clone does
not have them, so every test that reads one SKIPS when the payload is absent
rather than failing. The finding that matters -- that the stock drop path
cannot see an item id -- reads a tracked object file and always runs.
"""
import pathlib
import struct
import unittest

ROOT = pathlib.Path(__file__).resolve().parent
PAYLOAD = ROOT / "vanilla_runtime_payload"


def _desktop_assets():
    """Whichever payload layout this machine happens to have.

    Two layouts are in circulation and each exists on some machines and not
    others, so hardcoding either makes the tests pass for one person and raise
    FileNotFoundError for the next. Resolve it instead, and return None when
    neither is present so the caller can skip rather than crash.
    """
    for candidate in (
        PAYLOAD / "Assets",
        PAYLOAD / "Original Virtual Families 2 Assets" / "Assets",
    ):
        if (candidate / "YogaGearStd.png.fmap").is_file():
            return candidate
    return None


DESKTOP = _desktop_assets()
MOBILE = ROOT / "assets" / "TextAsset"
SCENE = ROOT / "desktop_obj_files" / "theMainScene.obj"

QAMF = b"QAMF"

# Recorded in this patcher independently of any fmap parsing.
PINNED_CELLS = {0x2000B000: 0x96, 0x2000B800: 0x97, 0x2000C000: 0x98}

# Desktop donors and the object each carries, read from the QAMF maps.
# The object each donor map must carry. HammockStd is included because the
# transparency log documents it alongside the other three; leaving it out
# meant the donor the log names as distinguishable was never checked.
DONOR_OBJECTS = {
    "YogaGearStd": 0x75,
    "TreadmillStd": 0x04,
    "PoolTableStd": 0x36,
    "HammockStd": 0x13,
}


def object_of(cell):
    return ((cell >> 11) & 0x7F) | ((cell >> 22) & 0x80)


def require_desktop_payload(case):
    """Skip unless the gitignored game payload is present in this checkout."""
    if DESKTOP is None:
        case.skipTest("vanilla_runtime_payload is a gitignored build input")


def require_desktop_objects(case):
    """Skip unless the gitignored game object files are in this checkout.

    work/desktop_obj_files is .gitignore'd too -- it is extracted from the
    player's own installation, not committed -- so a fresh clone has no
    theMainScene.obj to read.
    """
    if not SCENE.is_file():
        case.skipTest("desktop_obj_files is a gitignored build input")


def desktop_objects(name, directory=None):
    """Objects in a DESKTOP map, refusing anything that is not QAMF.

    `directory` exists so the rejection test can push a real mobile file
    through THIS function rather than re-implementing the magic check in
    the test. A test that raises its own AssertionError proves nothing
    about the parser and would keep passing if this guard were deleted.
    """
    path = (directory or DESKTOP) / f"{name}.png.fmap"
    blob = path.read_bytes()
    if blob[:4] != QAMF:
        raise AssertionError(
            f"{path} is {blob[:4]!r}, not QAMF; refusing to parse it with the "
            "desktop decoder"
        )
    w, h = struct.unpack_from("<ii", blob, 24)
    objects = set()
    for i in range(w * h):
        cell = struct.unpack_from("<I", blob, 32 + i * 4)[0]
        if cell:
            objects.add(object_of(cell))
    return objects


class TestTheDecoderIsValidatedBeforeItIsTrusted(unittest.TestCase):
    def test_it_reproduces_the_pinned_constants(self):
        """Three object/cell pairs this patcher recorded independently."""
        for cell, expected in PINNED_CELLS.items():
            with self.subTest(hex(cell)):
                self.assertEqual(object_of(cell), expected)


class TestTheTwoContainersAreNotInterchangeable(unittest.TestCase):
    """The trap that produced a confident wrong finding."""

    def test_the_desktop_map_is_qamf(self):
        require_desktop_payload(self)
        blob = (DESKTOP / "YogaGearStd.png.fmap").read_bytes()
        self.assertEqual(blob[:4], QAMF)

    def test_the_mobile_file_of_the_same_name_is_not(self):
        blob = (MOBILE / "YogaGearStd.png.fmap").read_bytes()
        self.assertNotEqual(
            blob[:4], QAMF,
            "if the mobile assets have become QAMF, the guard below no longer "
            "distinguishes the two containers and this test is why",
        )

    def test_the_desktop_parser_refuses_the_mobile_file(self):
        """Refusing beats returning meaningless numbers.

        Routed through the REAL desktop_objects() parser. This previously
        read the file and raised its own AssertionError, so it never
        touched the parser at all and would have stayed green with the
        magic check removed -- the precise regression it claims to
        prevent. Applying the desktop decoder to FMP4 bytes does not
        fail loudly; it returns tidy, meaningless numbers, which is what
        produced the withdrawn "all donors are identical" finding.
        """
        with self.assertRaises(AssertionError) as caught:
            desktop_objects("YogaGearStd", directory=MOBILE)
        self.assertIn(
            "not QAMF", str(caught.exception),
            "the parser raised for some other reason than the magic "
            "check, so this does not pin the guard",
        )


class TestTheDesktopDonorsAreDistinguishable(unittest.TestCase):
    """The correction. They are NOT identical; the earlier claim was wrong."""

    def test_each_donor_carries_its_own_object(self):
        """Distinguishability is checked from the DECODED maps.

        This previously recorded the hardcoded expected value into `seen`
        and then asserted those were distinct -- which is guaranteed by
        DONOR_OBJECTS having distinct literals, and says nothing about the
        maps. If every donor acquired all four objects the assertion would
        still have passed while the donors became indistinguishable, which
        is the exact conclusion this class exists to pin.

        The decoded object SET is stored instead, so the comparison is
        between what the maps actually contain.
        """
        require_desktop_payload(self)
        signatures = {}
        for name, expected in DONOR_OBJECTS.items():
            with self.subTest(name):
                objects = desktop_objects(name)
                self.assertIn(
                    expected, objects,
                    f"{name} no longer carries object {expected:#x}",
                )
                # Object 0 is the empty cell and appears in every map, so
                # it carries no identifying information.
                signatures[name] = frozenset(objects) - {0}
        self.assertEqual(
            len(set(signatures.values())), len(signatures),
            "two donor maps decode to the SAME object set, so they cannot "
            "be told apart: "
            + repr({k: sorted(hex(o) for o in v)
                    for k, v in signatures.items()}),
        )

    def test_the_yoga_object_is_unique_across_desktop_maps(self):
        """0x75 identifies exactly one map, which is what makes it usable."""
        require_desktop_payload(self)
        carriers = []
        for path in sorted(DESKTOP.glob("*.fmap")):
            blob = path.read_bytes()
            if blob[:4] != QAMF:
                continue
            w, h = struct.unpack_from("<ii", blob, 24)
            if w <= 0 or h <= 0 or 32 + w * h * 4 > len(blob):
                continue
            for i in range(w * h):
                cell = struct.unpack_from("<I", blob, 32 + i * 4)[0]
                if cell and object_of(cell) == 0x75:
                    carriers.append(path.name)
                    break
        self.assertEqual(carriers, ["YogaGearStd.png.fmap"])


class TestTheDropPathClaimRunsOnAFreshClone(unittest.TestCase):
    """The same contract, read from a TRACKED file so it never skips.

    The object-file test below is the stronger check -- it reads the real
    COFF relocations -- but work/desktop_obj_files is gitignored, so on a fresh
    clone it skips and the central claim of this module goes unverified. A
    suite that reports success without ever checking its own headline claim is
    worse than one that fails.

    work/theMainScene_disasm.txt IS tracked and carries the full body of
    HandleDropOnHotSpot, so the claim can be checked everywhere:

        push ebp / mov ebp,esp / sub esp,8
        call ?FeetPos@CVillager@@...
        mov  ecx, offset ?ContentMap@@...
        call ?GetHotSpot@CContentMap@@...
        test eax,eax / je
        call ?Dispatch@CHotSpot@@...
        ret 4

    FeetPos, GetHotSpot, Dispatch. No furniture manager, no item id.
    """

    DISASM = ROOT / "theMainScene_disasm.txt"

    def _body(self):
        self.assertTrue(
            self.DISASM.is_file(),
            f"{self.DISASM} is tracked and must exist; without it this "
            "module's central claim is unverifiable on a fresh clone",
        )
        text = self.DISASM.read_text(encoding="utf-8", errors="replace")
        marker = "?HandleDropOnHotSpot@theMainScene@@IAE?B_NAAVCVillager@@@Z ("
        start = text.index(marker)
        # The next function heading ends this one. Headings are the only lines
        # that start at column 0 with a decorated name.
        rest = text[start + len(marker):]
        end = rest.index(chr(10) + "?")
        return rest[:end]

    def test_the_body_calls_only_feetpos_gethotspot_and_dispatch(self):
        body = self._body()
        for required in ("FeetPos", "GetHotSpot", "Dispatch"):
            with self.subTest(required):
                self.assertIn(required, body)

    def test_the_body_never_touches_furniture(self):
        """This is the claim the stock-donor argument rests on."""
        body = self._body()
        for forbidden in (
            "FindFurniture", "FurnitureManager", "ItemAtPoint",
            "PtOnFurniture", "LinkPeepToFurniture",
        ):
            with self.subTest(forbidden):
                self.assertNotIn(
                    forbidden, body,
                    "HandleDropOnHotSpot references " + forbidden + ", so it "
                    "could identify an added item after all and the "
                    "stock-donor argument needs revisiting",
                )

    def test_the_body_is_short_enough_to_be_the_whole_function(self):
        """Guards against the extraction silently grabbing nothing."""
        body = self._body()
        self.assertIn("ret", body, "the extracted body has no return")
        self.assertGreater(
            body.count(":"), 10,
            "the extracted body is too short to be the real function; the "
            "heading format probably changed",
        )


class TestTheStockDropPathNeverReadsAnItemId(unittest.TestCase):
    """The finding that stands. About the executable, not the maps."""

    def _function_section(self):
        require_desktop_objects(self)
        buf = SCENE.read_bytes()
        symptr, nsym = struct.unpack_from("<II", buf, 8)
        strtab = symptr + nsym * 18

        def name(i):
            b = symptr + i * 18
            raw = buf[b:b + 8]
            if raw[:4] == b"\x00\x00\x00\x00":
                off = struct.unpack_from("<I", raw, 4)[0]
                end = buf.index(b"\x00", strtab + off)
                return buf[strtab + off:end].decode("latin1")
            return raw.rstrip(b"\x00").decode("latin1")

        found = []
        i = 0
        while i < nsym:
            b = symptr + i * 18
            secnum = struct.unpack_from("<h", buf, b + 12)[0]
            if secnum > 0 and "HandleDropOnHotSpot" in name(i):
                found.append(secnum)
            i += 1 + buf[b + 17]
        self.assertEqual(
            len(found), 1,
            f"expected exactly one defining symbol, found {len(found)}; "
            "refusing to guess which",
        )
        return buf, name, found[0]

    def test_it_calls_only_gethotspot_and_dispatch(self):
        buf, name, secnum = self._function_section()
        optlen = struct.unpack_from("<H", buf, 16)[0]
        base = 20 + optlen + (secnum - 1) * 40
        relptr = struct.unpack_from("<I", buf, base + 24)[0]
        nrel = struct.unpack_from("<H", buf, base + 32)[0]

        targets = {
            name(struct.unpack_from("<I", buf, relptr + r * 10 + 4)[0])
            for r in range(nrel)
        }
        joined = " ".join(targets)
        self.assertIn("GetHotSpot", joined)
        self.assertIn("Dispatch", joined)
        for forbidden in ("FindFurniture", "FurnitureManager", "ItemAtPoint"):
            with self.subTest(forbidden):
                self.assertNotIn(
                    forbidden, joined,
                    "the stock drop path would be able to identify an added "
                    f"item if it referenced {forbidden}; if that changes, the "
                    "stock-donor argument may be revisited",
                )


if __name__ == "__main__":
    unittest.main()
