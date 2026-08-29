# B174.1

Point release on top of B174. Otherwise identical.

## The bug: Force Marriage Email could report "already married" with no spouse at all

`VF2MarriagePair` (the shared "who is the current married pair" lookup used by
Force Marriage Email, Divorce Spouse, and the same-sex marriage/private-time
routes) had a fallback path for when the native family-tree marriage record
isn't populated yet. That fallback scanned all 30 villager slots and paired
up the first two "active, employed resident adult" matches it found -- with
no check that the two were actually married to each other. A second
qualifying adult in the house for any reason (a grown, employed adult child,
for example) was silently treated as the player's spouse. That fed straight
into `VF2MarriageEmailUnavailable()`, which hides Force Marriage Email's
purchase entirely once it thinks a pair exists -- so the row could report
already-purchased/unavailable for a player with no spouse in the house.

The fallback exists for exactly one real gap: native Accept finalization
requires `CVillagerManager::GetMatriarch()` **and** `GetPatriarch()` to both
succeed, which is impossible for a same-sex pair, so the family-tree record
is never written for a same-sex marriage. Opposite-sex marriages always
populate that record via native code and never needed this fallback at all.

**Fix:** the fallback now only runs when Same-Sex Marriage is toggled on, and
only pairs two people when the household has *exactly* two qualifying
adults -- not just "the first two found."

**What this does not fix.** The exact-two rule removes the guess only when a
*third* qualifying adult is present. It still does not establish that the two
candidates are married to each other, so the specific case named above -- an
unmarried player plus one grown, employed adult child, and nobody else --
still counts exactly two and still pairs them. Force Marriage Email remains
unavailable in that household. Closing that gap needs a real relationship
test, which this fallback cannot use: it exists precisely because the
family-tree marriage record is unpopulated for a same-sex pair. Left as-is
rather than guessed at, and recorded here instead of being claimed fixed.

## Missing cheat-row art

`cheat_antispam_disk.png` and `cheat_rockhound_certificate.png` were
referenced by the Special Upgrades icon table with a documented source (the
exact sprite-sheet, cell index, and visual description was already written
in a comment), but the files themselves were never actually committed,
despite B174's own release notes claiming zero missing base-game files.
Extracted both from the real vanilla sprite sheets at the documented
coordinates (`InventoryItems.png` cell 92, `home_grid.png` cell 41) and
visually confirmed each crop matches its documented description before
committing -- this is base-game art, not new art.

## Also in this release

- Removed 452 lines of dead legacy same-sex-marriage code (explicitly marked
  "retained for source archaeology only," zero live callers, and its own
  test was already marked obsolete).
- Verified the "needs to sit down" (RestingBody, 0x127) behavior variation
  end to end on request: byte-verified the label-variant hook against real
  `Behavior.obj`, confirmed all 6 label pools are populated, confirmed a full
  compile+link with Behavior Patches enabled succeeds. Nothing was broken;
  added the regression coverage that was missing (nothing had named this
  behavior specifically before).
- `EXPECTED_CHEAT_IDS` in the release-parity test suite updated to include
  the 7 cheat items added since it was last touched (the 5 wellbeing rows
  plus the two ownership rows above).

## Verification

- Full `work/test_patch_mobile_furniture_pack.py` +
  `work/test_special_upgrades_release_parity.py` suite: 296 passed, 1
  skipped, 113 subtests passed, 0 failures.
- All 19 matrix variants built, linked, and are byte-distinct.
- `work/gate_release_zip.py --release B174.1`: **RELEASE GATE PASSED**,
  `variant_identities_authenticated: true`, 19 executable variants
  authenticated against independently recorded identities, 7368 files,
  ~178.9 MB.
