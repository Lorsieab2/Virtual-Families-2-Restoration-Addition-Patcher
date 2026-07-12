# Virtual Families 2 Restoration/Addition Patcher B150

B150 is based on B149 and concentrates on collection stability, optional
behavior expansion, reversible upgrades, collection and price cheats, and
house-malfunction coverage.

## Highlights

- Replaced the first B150 Holiday Ornaments overlay after a real runtime crash.
  HandleMouse, Find, and WasItemSpawned now use branch-safe code caves; The
  Collector Keep path, incomplete Drop path, and repeated goal completion are
  repaired; the visible collection total is 72 when enabled.
- Added a separately gated Behavior Patches option. It includes the requested
  spontaneous actions, age/weather/nursing/gender gates, web, nap, baby,
  sit-down, and bathroom-sink variations; Petting is no longer spontaneous.
- Fixed the remaining praise reroll by preserving the exact 0x28-byte current
  behavior wording across native ForgetPlans/StartNewBehavior. Intentional
  over-praise RunAway behavior is unchanged.
- Added Reset Ants, Reset All Collections, Complete All Collections, 2x/5x/100x
  Prices, Reset Price Multiplier, Trigger All House Malfunctions, and Fix All
  House Malfunctions cheats, displayed in functional groups without renumbering.
- Trigger All takes the Router offline; Fix All clears all 11 malfunction props
  and brings it online without resetting ants. The native Dryer lint fire
  remains a real Dryer-gated random malfunction with Handyman repair credit.
- Made Maid, Gardener, Rockhound Certificate, and Anti-Spam Upgrade purchases
  reversible when Cheat Upgrades is enabled.
- Added all three north-bathroom leaks to standalone malfunctions and the Water
  Pressure Surge event, gated by the north-bathroom renovation.
- Added the requested save-compatibility, creator, copyright, and Brokerage
  Account interest-rate notices.
- Added a complete 16-variant executable overlay matrix covering Island Events,
  Cheat Upgrades, Holiday Ornaments, and Behavior Patches independently.
- Pruned payload files that are unreachable from every manifest source or
  restore record, cutting package size without removing any selectable patch.

## Verification

- 71 patch-generation and native-contract tests passed.
- 56 exporter, runner, and patcher-GUI tests passed (127 total).
- All 16 executable variants compiled and linked without logged errors and have
  distinct hashes.
- All eight Holiday-enabled linked executables passed direct detour and
  branch-target validation.
- Final package: 1,075 asset patches, 1,112 payload files, and 16 executable
  records.
- Replacement compact ZIP: 86,331,216 bytes, down from the pre-pruning 184,056,834-byte
  package without removing any selectable patch.
- Archive SHA-256:
  `847B8999135290632AD4216E463585EB2E7D3C4BCFEA79AF47A1BCE10CAAEC48`.

The first B150 archive (SHA-256
`5A2EAE1FA89D723CE808FD82EC3FDA182AEF3E02E298F79CD3EEEECE5E7BF1DE`)
is superseded. Runtime Holiday and praise behavior must still be confirmed in a
real B149/B150 installation before treating those reverse-engineered paths as
game-tested.
