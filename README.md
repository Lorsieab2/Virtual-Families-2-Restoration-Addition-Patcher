# Virtual Families 2 Restoration/Addition Patcher

Offline patcher and restoration/addition project for the official Windows version of *Virtual Families 2*.

Created with Codex AI in collaboration with Lorsieab2. This is a passion project dedicated to improving the *Virtual Families 2* experience. No copyright infringement is intended; please support the original game creators. :)

## Download

Download the newest patcher ZIP from the [official releases page](https://github.com/Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher/releases). Release ZIPs and compiled game payloads are intentionally not committed to the source tree.

Vanilla *Virtual Families 2* saves are compatible with the modded version. The patcher creates a separate modded game folder by default and does not overwrite the selected vanilla installation.

## What the patcher does

- Validates a user-selected official VF2 installation before changing files.
- Applies only the patches selected in the manifest-driven GUI.
- Creates or refreshes a clearly named modded copy of the game.
- Supports dry-run validation, backups, restore, and machine-readable logs.
- Uses offline file patching; it does not inject into a running process.

After extracting a release, run `Launch_GUI.bat`. The exported bundle also contains `How to Use.txt` with player-facing instructions.
Release bundles include the instruction-only `vf2_crash_capture.py` helper and
an unfilled exact-build manifest template for optional crash QA. Neither the
patcher nor that helper changes the registry or launches VF2; any generated WER
instructions must be reviewed and run manually by the player.

## What's included

The GUI reads its checkboxes from the shipped manifest, so the exact list follows
the release you downloaded. As of B171 it offers these, grouped the way the GUI
groups them.

**Main patches** (on by default):

- **Patch game executable** - verifies a vanilla `Virtual Families 2.exe` and writes a clearly labeled modded EXE into a separate modded folder.
- **Add mobile Holiday furniture** - mobile Holiday furniture records and generated assets (decorative for now).
- **Add Holiday outfits** - Holiday outfit body values and runtime frames; needed for Holiday rows in the expanded Outfit store.
- **Add expanded Outfit store** - Outfit store rows for body values 0-49, icons, independent tray items, and body-field sync.
- **Add additional mobile-exclusive furniture** - the non-Holiday mobile furniture set.
- **Add unused pets** - restores the unused Turtle and Hamster pets.
- **Add VF3 TV assets and recognition** - VF3 TV furniture, private animation strips, and TV fmap recognition.
- **Behavior Patches** - the behavior-only executable overlay: spontaneous sitting, mending, ironing, weight checks, and nursing-mother lessons; registered web, nap, sink/grooming, snow, shower, meal, career, and play routes with their native age/object/weather/gender gates intact; and native private romantic time for six-child opposite-sex spouse pairs, with no pregnancy and no argument.
- **Text fixes** - miscellaneous string corrections.
- **Add visible mobile version purchases** - Brokerage Account, Food Club, Health Plan, and Lucky Rock rows under Special Upgrades.

**Optional patches** (off by default unless noted):

- **Add mobile furniture behaviors** (on) - ported actions for genuine mobile furniture: weather-aware loungers, the Patio Umbrella and tables, Picnic Table, Birthday furniture, and the Holiday pieces.
- **Use mobile sound assets** (on) - stages the 67 hash-pinned mobile behavior sounds and repoints the four PC WAV routes that must load OGG.
- **Add Holiday Ornaments collection** - 12 yard collectibles, six Collections Chest pages, the Ornamentologist and six-family goals, Lucky Rock rarity odds, and The Collector offer/sell handling.
- **Add mobile-exclusive Island Events** - all 25 authenticated mobile-exclusive Island Event records with their text and choice/result dialogs.
- **Add mobile room renovations** - 20 verified mobile renovation images (5 Bathroom 1, 5 Bathroom 2, 3 kitchen, 5 office, 2 workshop) at their exact room-map positions.
- **2nd Bathroom Mobile-Style Renovations** - AI-generated Bathroom 2 art, hand-edited, based on the Bathroom 1 mobile renovations. Labeled with an art warning in the GUI.
- **Allow Older Pregnancies** - normal fertility below 50, then a chance that tapers from 10% at 50 to a 0.1% floor at 69+; Next Generation also unlocks at 60 with a surviving child.
- **Allow Same-Sex Marriage** - flips only the spawned candidate's gender field when the in-game Special Upgrade is on; same-sex spouses keep native private romantic time and never become pregnant.
- **Older Villager Mortality Curve** - replaces only the annual old-age death roll with a calibrated curve that accelerates past effective age 110. No hard maximum age.
- **Cheat Upgrades** - the cheat-only executable overlay: money, food, achievement/puzzle/collection, price, and malfunction rows, including Trigger and Fix all house malfunctions.
- **No AI Icons** - requires Cheat Upgrades; swaps the late Special Upgrade icons for non-AI artwork.
- **Virtual Families 3 Furniture**, **Add Custom Couches and LDW Posters**, **Add Invisible Furniture - Visible Graphics** and its **Transparent Graphics** companion, **Invisible Workspace Upgrades**, **Lorsieab2's Custom Map Images**, **Transparent Menu Bar**, **Transparent Store Bar**, **Transparent Decor Tab**, **White Birds**, **Store Scroll Bar**, **Glowing Collectibles**, **Misc Graphics Fixes**, **Add loose optional visual mod graphics**, and **Add optional song mods** - asset and UI mods. Unchecking one and clicking **Enable/Disable Patches** rebuilds the modded folder without it.

Every optional feature is absent when its setting is off, and base-game
autonomous behavior choices and likelihoods are left alone. Several features are
shipped with in-game QA still outstanding; `docs/REQUEST_LEDGER.md` records the
per-request status and `docs/Transparency Log.txt` records the disclosures.

## Source layout

- `src/offline_vf2_patcher.py` - command-line patcher and validation/apply/restore engine.
- `src/offline_vf2_patcher_gui.py` - Tkinter GUI, plus its icon assets under `src/assets/`.
- `tests/` - the patcher, exporter, and GUI test modules that run against `src/`.
- `work/` - the reverse-engineering and build tree: disassembly dumps, analysis and
  export scripts, and the full test suite the shipped tools are synced from.
  `work/export_offline_patch_bundle.py` is the self-contained release-bundle exporter
  and the source of truth for the GUI's setting list; `work/vf2_crash_capture.py` is the
  exact-build dump/log validation and IDA handoff helper; `work/patch_mobile_furniture_pack.py`
  is the native VF2 build/patch pipeline; `work/test_*.py` holds the source, binary-contract,
  exporter, runner, and GUI tests.
- `work/assets/holiday_collectibles/` - curated Holiday Ornament source art and reproducible runtime assets.
- `patcher_assets/optional_patches/` - checked-in source art and audio for the optional asset patches.
- `data/vf2/` - target-identity records, build matrices, furniture/image tables, and the native contracts the tests pin.
- `docs/offline-patcher.md` - technical patcher documentation.
- `docs/Transparency Log.txt` - implementation and verification disclosures.
- `docs/REQUEST_LEDGER.md` - durable shipped/partial/unverified/deferred request
  inventory and release-completeness gate.
- `docs/discoveries.md` and `docs/TODO.md` - reverse-engineering evidence and remaining manual checks.

## Development

The project is designed to be self-contained. Do not add dependencies on Downloads, Desktop, OneDrive, or another private repository. Build outputs, extracted payloads, executables, caches, and archives stay out of Git and are distributed only through the latest GitHub Release.

Run the Python test modules from the repository root with a compatible Python 3 interpreter, for example:

```powershell
python -m unittest tests.test_offline_vf2_patcher tests.test_export_offline_patch_bundle tests.test_offline_vf2_patcher_gui
```

The `work/` tree keeps the wider suite, including the native build pipeline and
binary-contract tests:

```powershell
python -m unittest work.test_offline_vf2_patcher work.test_export_offline_patch_bundle work.test_offline_vf2_patcher_gui work.test_patch_mobile_furniture_pack
```

The GUI modules need a Python build with `tkinter` available.
