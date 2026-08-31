# B175

Point release on top of B174.2.

**Built and published.** `VF2-B175-Playtest-All-Enabled.zip`, artifact SHA-256
`8D53B71451B4D7A743375B9FCF460EBDD9931A467117D89B7C9931D2B0E79682`, executable
SHA-256 `9F768DC9761CBD2AFD0073C440522184B2939D12EFBB98FA2C655862997DCBAB`.
Built from `main` at `31b8f8c` and seeded from B174.3, per the rule that a new
build starts from the most recent previous one.

Verified at the binary and asset level: all five runtime gate sections read
`01`; the RestingBody candidate table is written twice (450, then 2000 from the
mobile enabler that runs last) where B174.3's binary has one such write; 34/34
mobile-furniture behavior maps are byte-identical to `pc_fmaps`; and all 635
inheritance-only images are present, with Images, Assets, Sounds, Original
Virtual Families 2 Assets and OptionalVisualMods each matching B174.3 exactly.

**Mobile sound assets are not in B175.** This artifact was built while
`build_playtest.ps1` still held `VF2_ENABLE_MOBILE_SOUND_ASSETS` at `0`, so it
keeps the stock WAV sound routes. Playtest builds after that change stage all 67
hash-pinned sounds and rewrite the four `.wav` routes to `.ogg`; the matrix
builder deliberately stays at `0` so the patcher can keep applying those routes
as a reversible setting. What B175 does turn on that the GUI leaves off by
default is Allow Older Pregnancies and the Older Villager Mortality curve.

**Nothing here has been seen running in the game.** In-game confirmation is
still required, in particular that villagers autonomously choose RestingBody and
that the four newly enabled gates behave as expected.

## RestingBody is autonomous again, under Behavior Patches

B174.2 fixed the sit-down action by identifying it correctly as
`CBehavior::UseCouch` (`0x189`) -- the behavior a manual couch or chair drop
runs via `CHotSpot::Couch` -- retargeting it to a label-variant wrapper and
enabling it as its own autonomous candidate at weight 450.

The same change removed `EnableAllAgesAutonomousCandidateWithWeight(data, 0x127, 450)`
from `VF2EnableAutonomousCandidates`, on the correct reasoning that RestingBody
could never affect a manual couch drop and that the Mobile Furniture Behaviors
patch already enables `0x127` at weight 2000. B174.2's own release note recorded
that as "RestingBody (0x127) is untouched by Behavior Patches".

The side effect was that `0x127` ended up enabled by **only** the Mobile
Furniture Behaviors patch, which is gated behind the `.vf2beh` runtime byte. So
in any build with Behavior Patches on and Mobile Furniture Behaviors off,
RestingBody and its resting label family (`Resting`, `Resting legs`,
`Resting tired feet`) were never selectable by the AI at all.

**Change:** `0x127` is added back to `VF2EnableAutonomousCandidates` as an
all-ages candidate at weight 450, placed before the
`VF2EnableMobileFurnitureCandidates` call that already runs last. With
`.vf2beh` set, the mobile enabler still overwrites the row with its weight 2000
all-ages entry and the chaise sunbathing and sit-down routes behave exactly as
they did in B174.2. With `.vf2beh` zero, the behavior now falls through to
native RestingBody plus the shared sit-down label pool, which is the intended
non-chaise route.

The behavior-label macro table is untouched, so Behavior Patches still does not
retarget `0x127`; that macro remains owned by Mobile Furniture Behaviors.

**Compiled and verified in the binary, not observed in game.** The shipped
executable writes the RestingBody candidate twice -- weight 450 from
`VF2EnableAutonomousCandidates`, then 2000 from
`VF2EnableMobileFurnitureCandidates`, which is the last call it makes before
returning. B174.3's binary contains one such write. What that does not show is a
villager actually choosing the behavior, which needs a playtest with Behavior
Patches on and Mobile Furniture Behaviors off.

## Playtest builds now set every selected runtime gate

A freshly linked executable has `00` in each one-byte gate section; only the
offline patcher flips one when a player ticks that setting. A playtest build has
no patcher step, and `build_playtest.ps1` only ever set `.vf2beh`.

Reading the section table of the executable inside the shipped
`VF2-B174.3-Playtest-All-Enabled.zip` confirms the consequence:

| section | feature | shipped value |
| --- | --- | --- |
| `.vf2beh` | Mobile Furniture Behaviors | 01 |
| `.vf2goal` | Holiday Furniture goals | 00 |
| `.vf2preg` | Allow Older Pregnancies | 00 |
| `.vf2mort` | Older Villager Mortality curve | 00 |
| `.vf2scrl` | Store Scroll Bar | 00 |

Four features shipped present-but-dormant in an artifact named "All-Enabled".

All five gates are now driven from the existing `enable_runtime_flag.py`, one
parameter each, defaulting to on to match this script's documented "every
optional patch enabled" contract. Pass `-OlderVillagerMortality:$false`,
`-AllowOlderPregnancies:$false` or the equivalent to leave a gate at `00`. The
build prints the state it set for each section, so an artifact's real contents
are visible from the build log instead of needing a hex editor.

Note that this changes what a default all-enabled playtest contains: Older
Villager Mortality and Allow Older Pregnancies are experimental rule changes
that are default-off in the GUI and will now be on unless opted out.

Both were exercised for real. `enable_runtime_flag.py` was run against the
shipped B174.3 executable, where all five sections flip `00` to `01` and read
back `01`; and the `build_playtest.ps1` wiring produced B175, whose five gate
sections all read `01` in the published artifact.

### Playtest executable name and save folders

VF2 derives its save folder from the executable's own filename. The linked
executable's path builder calls `GetModuleFileNameA`, takes the basename,
strips the extension, and assembles `Documents\LDW\<name>\` -- the `\LDW`
component comes from a 5-byte literal at `0x4fc234`. `src/offline_vf2_patcher.py`
builds the same path.

A per-build executable name therefore starts an empty family every time. The
default is now the stable `Virtual Families 2 Modded Playtest 2.exe`, and the
build prints the folder the executable will use so a future name change cannot
be silent. The previous default, `Virtual Families 2 - Playtest Build`, has no
folder on the build machine, so nothing is stranded by the rename.

## Generated-source whitespace fix

The chaise sit-down gate template ended with `.strip("\\n")`, a two-character
string of a backslash and a lowercase `n`. `strip` therefore removed backslash
and `n` characters, not the real newlines the template actually begins and ends
with, so the generated helper carried a stray blank line either side of the
emitted `if` block. Whitespace only; the emitted statements and their order are
unchanged.

## README

Rewritten against the current setting list. It was still marked "As of B171"
and described most patches in one lumped paragraph.

- All 36 settings taken from `work/export_offline_patch_bundle.py`'s `SETTINGS`,
  split into Main and Optional as the GUI groups them, with the optional set
  broken out into gameplay/content, the experimental one-byte runtime toggles,
  and the asset/UI mods.
- A new section documenting all 43 Cheat Upgrade rows grouped by function.
- A new section documenting which behaviors Behavior Patches makes autonomously
  selectable, under which gates, and which routes get label variations.

Four accuracy corrections were made during review, all confirmed against the
source before changing anything:

- The save path is `Documents\LDW\<exe name>\`, not `Documents\<exe name>\`.
- Not every cheat row is free. Enable Same-Sex Marriage and Allow Reroll of
  Marriage Candidates each cost 10,000 coins. Divorce Spouse was checked too and
  is genuinely 0.
- **Divorce Spouse cannot be cancelled by buying it again.**
  `VF2ApplyB150Upgrade` case `0x14B` calls `VF2DivorceSpouse` immediately and
  saves; the row is never armed and shows no checkmark. The README previously
  implied every one-shot could be cancelled, which is wrong and dangerous for an
  irreversible action.
- The load path is not extended by wrappers alone.
  `patch_custom_achievements` rewrites five byte spans inside
  `CAchievement::LoadState` so the reserved-tail validation and clearing ranges
  cover the custom achievement IDs. The save-writing path is genuinely
  untouched: `theGameState::SaveCurrentGame` and the per-class `SaveState`
  serializers are not modified, and the build asserts their stock byte spans and
  record counts.
- Behavior Patches does more than change eligibility and labels. The hammock
  rest builds its own anchored plan sequence, six-child private romantic time
  replaces the family-full refusal with a jump to the target the passing gates
  already use, and a manual computer drop can flip ordinary web browsing to
  playing a video game. These are now documented rather than implied away.

## Release-management notes

Two things found while auditing the previous release, recorded rather than
silently corrected:

- **`VF2-B174.2-Playtest-All-Enabled.zip` and `VF2-B174.3-Playtest-All-Enabled.zip`
  are the same file**, SHA-256
  `A6925AE01B94168815972230B341FFD69043EBB136D011FEBDBFBA0E9386F8B9`, containing
  the same executable, SHA-256
  `0A7596943130587869B1802F6D27AB73F196B0A5DC2381D5F7595656B973F047`. The B174.3
  draft's notes describe a reissue built from current main; no rebuild produced
  it, the existing asset was re-uploaded. The binary does contain PR #67's final
  ordering -- verified by disassembly, `StartNewBehavior` at `0x4b25ee` followed
  by the guarded `VF2ApplySitDownLabelVariants` call at `0x4b25ff` -- so the
  content claim happens to hold even though the build claim does not.
- B174.3 has since been published, with its notes corrected to record that the
  asset was re-uploaded rather than rebuilt, and that four of its runtime gates
  were still `00`. The B174.2 draft is left in place as the duplicate it is.

No `data/vf2/build-matrix-release-b175.json` is included. Those configs are for
the 19-variant patcher matrix; B175 is a single all-enabled playtest artifact
built by `build_playtest.ps1`, which takes its seed from `-PreviousBuildDir`
rather than from a matrix config.

## The inherited-art dependency

Producing B175 surfaced the reason a playtest build cannot be reproduced from
source alone. 635 images -- 448 VillagerBodies frames, 93 Furniture images
including the mobile Birthday art whose `.fmap` the same build stages, 61
Upgrades icons, 25 root images and 8 OutfitIcons -- exist in neither the
repository nor `work/vanilla_runtime_payload`. They reach a build only by
inheriting from a previous build output, and `build_playtest.ps1` used to clear
that inheritance unconditionally, so a build from a clean checkout omitted every
one of them while still reporting success.

The measured inventory is now recorded in
`data/vf2/inherited-only-images.json` and the build checks the full list twice:
the seed in preflight, and its own output after generation. A build that
resolved a seed and still came up short fails. A build that resolved no seed is
still allowed -- that is a legitimate thing to ask for -- but it now reports in
red how many of the 635 it is missing and how to inherit them, instead of
finishing quietly. That makes the dependency visible; it does not remove it. Every release still depends on the chain of
prior artifacts, and closing that gap means either committing those 635 files or
regenerating them from their original sources.
