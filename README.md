# Virtual Families 2 Restoration/Addition Patcher

Offline patcher and restoration/addition project for the official Windows version of *Virtual Families 2*.

Created with Codex AI in collaboration with Lorsieab2. This is a passion project dedicated to improving the *Virtual Families 2* experience. No copyright infringement is intended; please support the original game creators. :)

## Which copy of the game this supports

**This patcher targets the Windows build of *Virtual Families 2* downloaded from Last Day of Work's own website.** That is the only copy it is developed and tested against.

It has **not** been tested against the Steam release, and whether that build matches has not been established. The patcher validates the installation you point it at and refuses to proceed if it does not recognise it, so an unsupported copy should fail safely rather than be corrupted — but nothing is promised beyond the LDW build.

There is also no practical reason to get the game anywhere else: **all of LDW's PC games are free on their own website.** Download it from there and point the patcher at that installation.

## Download

The [releases page](https://github.com/Lorsieab2/Virtual-Families-2-Restoration-Addition-Patcher/releases) carries two different kinds of asset, and only one of them is the patcher:

- **`VF2-B<version>-Release.zip` is the patcher.** This is what you want. It contains `Launch_GUI.bat` and the manifest the GUI reads, and you point it at your own VF2 installation. Take the newest one.
- **`VF2-B<version>-Playtest-All-Enabled.zip` is not a patcher.** It is a complete pre-patched game folder built for testing a specific change. There is no GUI and nothing to configure. A playtest build has no patcher step, so it bakes in what the patcher would otherwise apply: the mobile sound assets (all 67 staged, and the four hardcoded `.wav` sound routes rewritten to `.ogg`), plus the two experimental rule changes (Allow Older Pregnancies, Older Villager Mortality Curve) that are default-off in the GUI. The patcher bundle instead keeps the stock `.wav` routes in its executables and rewrites them only when you tick **Use mobile sound assets**, which is what keeps that setting reversible. A playtest artifact may be marked "Latest" while the newest patcher bundle is an earlier version, so check the filename rather than the Latest badge.

Release ZIPs and compiled game payloads are intentionally not committed to the source tree.

Vanilla *Virtual Families 2* saves are compatible with the modded version. The patcher creates a separate modded game folder by default and does not overwrite the selected vanilla installation.

Note that VF2 derives its save folder from the executable's own filename: saves live in `Documents\LDW\<exe name>\`, where `<exe name>` is the executable's filename with its extension removed. A modded or playtest EXE with a different filename therefore starts with its own empty save folder rather than continuing an existing family.

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

The game's own save-writing path is left alone. `theGameState::SaveCurrentGame` and the per-class `SaveState` serializers are not modified, and the build asserts their stock byte spans and record counts.

The load path is mostly extended by wrappers that run the native `LoadState` first and then reconcile achievements or re-apply the autonomous behavior table in memory. There is one exception: with custom achievements included, five byte spans inside `CAchievement::LoadState` are rewritten so that the reserved-tail validation and clearing ranges cover the custom achievement IDs instead of the stock ones. That changes which ID range the loader validates and clears, not the layout of the record it reads.

## What's included

The GUI reads its checkboxes from the shipped manifest, so the exact list follows
the release you downloaded. As of B176 it offers 35 settings, grouped the way
the GUI groups them.

Two of the entries below are described for completeness but are **not** offered
by the bundle: **Allow Same-Sex Marriage** (reachable in game through its Cheat
Upgrade row instead, since its toggle moved to a persisted save byte) and
**Transparent Store Bar**. Both have been absent since at least B174.1.

### Main patches (on by default)

- **Patch game executable** - verifies a vanilla `Virtual Families 2.exe` and writes a clearly labeled modded EXE into a separate modded folder.
- **Add mobile Holiday furniture** - mobile Holiday furniture records and generated assets (decorative for now).
- **Add Holiday outfits** - Holiday outfit body values and runtime frames; needed for Holiday rows in the expanded Outfit store.
- **Add expanded Outfit store** - Outfit store rows for body values 0-49, icons, independent tray items, and body-field sync.
- **Add additional mobile-exclusive furniture** - the non-Holiday mobile furniture set.
- **Add unused pets** - restores the unused Turtle and Hamster pets.
- **Add VF3 TV assets and recognition** - VF3 TV furniture, private animation strips, and TV fmap recognition.
- **Behavior Patches** - the behavior-only executable overlay. See [Behavior Patches in detail](#behavior-patches-in-detail).
- **Text fixes** - miscellaneous string corrections.
- **Add visible mobile version purchases** - Brokerage Account, Food Club, Health Plan, and Lucky Rock rows under Special Upgrades.

### Optional patches

Release bundles are exported with the all-enabled release profile, so several of
these arrive **on** when you pick **Defaults** in the GUI — including **Cheat
Upgrades**. Each is marked below. Uncheck anything you do not want and click
**Enable/Disable Patches** to rebuild the modded folder without it.

**Gameplay and content**

- **Add mobile furniture behaviors** (on) - ported actions for genuine mobile furniture: weather-aware loungers, the Patio Umbrella and tables, Picnic Table, Birthday furniture, and the Holiday pieces. Ships 34 behavior maps and is gated by a one-byte `.vf2beh` runtime flag that is zero until the setting is enabled.
- **Use mobile sound assets** (on) - stages the 67 hash-pinned mobile behavior sounds and repoints the four PC WAV routes that must load OGG.
- **Add Holiday Ornaments collection** (on) - 12 yard collectibles, six Collections Chest pages, the Ornamentologist and six-family goals, Lucky Rock rarity odds, and The Collector offer/sell handling.
- **Add mobile-exclusive Island Events** (on) - all 25 authenticated mobile-exclusive Island Event records with their text and choice/result dialogs.
- **Add mobile room renovations** (on) - 20 verified mobile renovation images (5 Bathroom 1, 5 Bathroom 2, 3 kitchen, 5 office, 2 workshop) at their exact room-map positions.
- **2nd Bathroom Mobile-Style Renovations** (on) - AI-generated Bathroom 2 art, hand-edited, based on the Bathroom 1 mobile renovations. Labeled with an art warning in the GUI.
- **Cheat Upgrades** (on) - the cheat-only executable overlay, adding 43 Special Upgrade rows. See [Cheat Upgrades in detail](#cheat-upgrades-in-detail).

**Experimental rule changes** (each is a separate default-off one-byte runtime flag)

- **Allow Older Pregnancies** (`.vf2preg`) - normal fertility below 50, then a chance that tapers from 10% at 50 to a 0.1% floor at 69+; Next Generation also unlocks at 60 with a surviving child.
- **Allow Same-Sex Marriage** (`.vf2same`) - flips only the spawned candidate's gender field when the in-game Special Upgrade is on; same-sex spouses keep native private romantic time and never become pregnant.
- **Older Villager Mortality Curve** (`.vf2mort`) - replaces only the annual old-age death roll with a calibrated curve that accelerates past effective age 110. Active food groups still subtract 0-4 effective years. No hard maximum age.
- **Store Scroll Bar** (`.vf2scrl`) - adds a scroll bar to the store.

**Asset and UI mods**

- **Virtual Families 3 Furniture** - VF3 furniture imports, including the plaid/striped/flowered living-room set.
- **Add Custom Couches and LDW Posters** - custom couch colourways and the LDW poster set.
- **Add Invisible Furniture - Visible Graphics** and **Swap Invisible Furniture Graphics with Transparent Graphics** - the invisible furniture set, with a companion setting that swaps in fully transparent art.
- **Invisible Workspace Upgrades** - invisible variants of the workspace upgrade props.
- **Lorsieab2's Custom Map Images** - replacement map art.
- **Transparent Menu Bar**, **Transparent Store Bar**, **Transparent Decor Tab** - UI chrome transparency.
- **White Birds** - recoloured birds.
- **Glowing Collectibles** - makes collectibles easier to spot.
- **Misc Graphics Fixes** - assorted art corrections.
- **Add loose optional visual mod graphics** - drops the loose optional visual mods into the modded folder.
- **Add optional song mods** - optional music replacements.
- **No AI Icons** - requires Cheat Upgrades; swaps the late Special Upgrade icons for non-AI artwork.

Entries marked **(on)** are enabled by the release profile the bundle ships
with; everything else is off until you tick it. Every optional feature is absent
when its setting is off, and base-game autonomous behavior choices and
likelihoods are left alone except where a patch documents otherwise. Several
features are shipped with in-game QA still outstanding; `docs/REQUEST_LEDGER.md`
records the per-request status and `docs/Transparency Log.txt` records the
disclosures.

## Cheat Upgrades in detail

Enabling **Cheat Upgrades** adds 43 rows under Special Upgrades. All are free
except two: **Enable Same-Sex Marriage** and **Allow Reroll of Marriage
Candidates** each cost 10,000 coins.

The toggle rows and the armed pregnancy one-shots are cancelled by buying them
again: an armed one-shot shows a checkmark, and arming one clears the rows it is
mutually exclusive with. **Divorce Spouse is not one of them.** It takes effect
the moment you buy it and saves immediately, so there is nothing to cancel and
buying it again will not bring the spouse back.

**Money**

| Row | Effect |
| --- | --- |
| No Money | Sets coins to 0. |
| Add 100 coins | Adds 100 coins. |
| Add 10 thousand coins | Adds 10,000 coins. |
| Add max amount of coins | Sets coins to the game's maximum. |

**Food**

| Row | Effect |
| --- | --- |
| No Food | Sets food to 0. |
| Add 100 food | Adds 100 food. |
| Add 10 thousand food | Adds 10,000 food. |
| Add max amount of food | Sets food to the game's maximum signed amount. |

**Store**

| Row | Effect |
| --- | --- |
| Unlock everything in the store | Unlocks every generation-locked store entry across all categories. Buy again to restore the original locks. |
| 2x Prices | Everything in the store costs twice as much. |
| 5x Prices | Everything in the store costs five times as much. |
| 100x Prices | Everything in the store costs an insane amount. |
| Reset Price Multiplier | Restores original calculated prices. |

Price modes affect every purchase routed through the store price calculator.

**Achievements, puzzles, and collections**

| Row | Effect |
| --- | --- |
| Reset Achievements | Resets all goals and progress. |
| Complete all Achievements | Completes every currently enabled achievement and awards its normal coin reward. |
| Reset Ants | Resets the ants puzzle so it can be completed again. |
| Reset all collections | Removes every collected item and resets collection progress. |
| Complete all collections | Completes every collection and its related achievements. |

**House and yard**

| Row | Effect |
| --- | --- |
| Trigger all house malfunctions | Causes all possible malfunctions, including sink/toilet leaks and oven/dryer fires. Useful for the "Handyman" goal. Makes the Router offline. |
| Fix all house malfunctions | Fixes every active malfunction and brings the Router back online; clears all 11 malfunction props without resetting ants. |
| Fill available house slots with trash | Uses native trash, dirt smudge, and sock spawn. Will not work if the Maid is active. |
| Clean House | Removes the same four indoor mess categories as the stock Housekeeping Services event. Yard weeds and the laundry-room sock pile are preserved. |
| Fill available yard slots with weeds | Uses the native weed spawn. Will not work if the Gardener is active. |
| Clean Garden | Removes every weed from the yard without affecting other collectables. |
| Max out sock pile | Sets only the laundry-room sock pile to the maximum signed integer value. |
| No sock pile | Clears the laundry-room sock pile without awarding sock-laundering progress. |

The Dryer lint fire remains a legitimate native random malfunction and requires a Dryer.

**Marriage and family**

| Row | Effect |
| --- | --- |
| Force Marriage Email | Queues a normal base-game marriage proposal with native candidate rules. |
| Enable Same-Sex Marriage | **10,000 coins.** Toggle. Enables same-sex marriage candidates. Requires the Allow Same-Sex Marriage patch. |
| Allow Reroll of Marriage Candidates | **10,000 coins.** Toggle. Lets Reject generate a new candidate until Accept is clicked. |
| Divorce Spouse | One-shot action. **WARNING: permanently removes the spouse from the Family Tree and House.** |

**Pregnancy one-shots**

| Row | Effect |
| --- | --- |
| Force Successful Pregnancy | Makes the next eligible try-for-baby attempt pass its pregnancy roll. Stays armed until the native birth routine succeeds. |
| Next Babies Male | Makes every baby in the next successful birth male. Replaces the Female one-shot. |
| Next Babies Female | Makes every baby in the next successful birth female. Replaces the Male one-shot. |
| Next Pregnancy Singleton | Makes the next successful birth one baby. Replaces Twins/Triplets. |
| Next Pregnancy Twins | Twins when two child slots are available, otherwise safely uses available capacity. |
| Next Pregnancy Triplets | Triplets when three child slots are available, otherwise safely uses available capacity. |

**Wellbeing** (each applies to everyone currently in the house)

| Row | Effect |
| --- | --- |
| Clear All Illnesses | Cures every symptom and infection, clearing the same illness fields the game clears itself. Changes no other part of a villager. |
| Max out Happiness Bar | Fills the Happiness bar. |
| Max out Energy Bar | Fills the Energy bar. |
| Max out Fed Bar | Fills the Fed bar, so nobody is hungry. |
| Max out Health Bar | Fills the Health bar. Does not revive anyone who has already died. |

**Stock Flea Market ownership toggles**

| Row | Effect |
| --- | --- |
| Anti-Spam Software Ownership | Installs or uninstalls the Anti-spam Software without using a computer. Buy again to switch it back. |
| Rockhound Certificate Ownership | Grants or removes the Rockhound Certificate, which lets the family dig for fossils. Buy again to switch it back. |

The two Flea Market rows themselves are untouched base game, and both are independently repurchaseable in every patched executable — including saves where the effect flag is already cleared. Elsewhere, rebuying the Maid or Gardener fires that worker, and rebuying an owned house renovation returns it and rebuilds the native content map so it can be purchased again.

## Behavior Patches in detail

**Behavior Patches** mainly does two things: it adds behaviors to the villager
AI's autonomous candidate table, and it varies the visible action text of
behaviors that already exist. For those two, the candidate keeps its native
object search, walking, animation, sound, and failure handling, and only
selection eligibility and the displayed label change.

Three parts of the patch go further than that, and are described in
**Substantive changes** below: the hammock rest builds its own plan sequence,
six-child private romantic time changes an outcome, and the computer drop gains
a choice it did not have.

**Made autonomously selectable**

- Hammock anchored rest (Sunny/Cloudy weather only), warming hands by and watching the fireplace, pinball / slots / pachinko / pool table / foosball, and random radio or MP3 dancing/listening — all ages.
- Playhouse and playground (daytime only), playing quietly at the kids table, drawing at the easel, the sandbox, the toy train table, and "driving like a grownup" — children only.
- Mending a button and ironing clothes — from displayed age 14. Kitchen, office, and workshop career work — adults only.
- Checking weight, playing video games, browsing the web, watching TV, getting a drink, heating up food, looking for snacks, preparing a meal, bookshelf reading, showers and baths (including the north shower), coffee/tea and the rare grande latte, cocktails, the trampoline, board games, the swimming pool, watering flowers/roses/window boxes, bathroom sink washing and grooming, the telescope, working out, breakfast, teen homework, and teen online exams.
- Teaching first words and the infant-care label family — nursing mothers carrying a baby only.
- **"Needs to sit down" on couches and chairs** (`CBehavior::UseCouch`, `0x189`). This is the behavior a manual drop on a couch or chair runs via `CHotSpot::Couch`, and it is enabled as its own autonomous candidate at weight 450 so the AI picks it too. Native couch and age gates are retained.
- **RestingBody** (`0x127`) and its resting label family. Autonomous for all ages at weight 450. Its native sittable targeting and plans are retained. When **Add mobile furniture behaviors** is also enabled, that patch runs last and raises this candidate to weight 2000, where it additionally carries the chaise sunbathing and sit-down routes.

**Label variations**

Grouped visible-label variants are applied to the native TV, web, video game, radio, reading, petting, mending, ironing, telescope, workout, career, shower/bath, coffee/tea, cocktail, pool, sandbox, toy train, playground, and snow-play routes. The wrappers preserve the original behavior plans and only change the displayed action text.

The sit-down pool is shared: the couch/chair route, the chaise route, and RestingBody's own resting labels (`Resting`, `Resting legs`, `Resting tired feet`) all draw from the same age/career/gender-aware label set. RestingBody's wrapper only substitutes a label when the native behavior actually emitted one of its three stock resting labels, so no other native label is disturbed.

**Substantive changes**

These three do more than change eligibility or wording:

- **Hammock rest** (`0x23`) is retargeted to a helper that builds its own plan sequence rather than reusing the native one. It links to the hammock, picks the getting-in pose and sleep animation strip to match the placed hammock's orientation, then rests for a randomised interval. Only Sunny and Cloudy weather allow it. The manual hammock drop (`0x24`) stays native.
- **Six-child private romantic time.** Stock `theMainScene::HandleDropOnVillager` refuses the drop when the family is full. That refusal is replaced with a jump to the same target every passing gate already uses, so an opposite-sex spouse pair at six children runs the ordinary romantic sequence — stock cooldown included — instead of being turned away. No cave and no reproduced instructions; the seven refusal bytes are simply unreachable, and the age and same-gender gates above are untouched.
- **Manual computer drop.** When a drop on a computer would have produced ordinary web browsing, a coin flip switches it to playing a video game instead. The stock email, repair, career-work and sickness computer routes are reserved before that point and are not affected, and no autonomous candidate weight changes.

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
- `docs/villager-behavior-plans.md` - behavior ID and label-family reference.
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

The `work/` binary-contract tests additionally need the gitignored local build
support directories (`work/desktop_obj_files`, `work/vanilla_runtime_payload`,
`work/generated_import_libs`, `work/desktop_runtime_dlls`); without them those
tests fail on missing inputs rather than on a real regression.

A build still cannot be reproduced from source alone. 635 runtime images -- most
of the VillagerBodies frames, the mobile furniture art, and the upgrade icons --
reach a build only by inheriting from a previous build output. All 635 are now
preserved under `patcher_assets/inherited_runtime_images`, so they can no longer
be lost, but no build consumes them from there yet. Of those, 574 previously
existed in no tracked location at all; the other 61 were already tracked
elsewhere and only their runtime copies arrived by inheritance. `work/build_playtest.ps1` takes that
predecessor with `-PreviousBuildDir` and checks both it and the produced build
against the recorded inventory in `data/vf2/inherited-only-images.json`.
Omitting the flag does not reliably produce an unseeded build: the generator
also scans `outputs/` for an older one, and whichever seed it resolves is
reported after generation. A build that genuinely inherits from nothing is
missing all 635, and says so in red rather than finishing quietly.

The GUI modules need a Python build with `tkinter` available.
