# B175

Point release on top of B174.2.

**This release is source-only until it is rebuilt.** Two of the three changes
below only take effect in a freshly compiled executable, so the existing
B174.2/B174.3 artifact does not contain them. Nothing here has been seen
running in the game.

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

**Not verified in game.** The binary-contract tests covering this helper need
the gitignored `work/desktop_obj_files`, so the new candidate row has not been
compiled or observed. Confirming it needs a playtest build with Behavior
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

`enable_runtime_flag.py` was exercised against the actual shipped B174.3
executable: all five sections flip `00` to `01` and read back `01`. The
`build_playtest.ps1` wiring itself has not been run, since a build needs MSVC
plus the four gitignored support directories.

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
- Both are still drafts. The published "Latest" release remains B174.1.

No `data/vf2/build-matrix-release-b175.json` is included. Those configs record
absolute seed paths to the previous build's output directories on the build
machine, which cannot be known from the repository, and inventing them would
record a build that never happened. Write it at build time from the real B174.2
output directories, per the no-regression rule that a new build seeds from the
most recent previous build.
