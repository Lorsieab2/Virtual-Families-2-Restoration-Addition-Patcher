# Virtual Families 2 Restoration/Addition Patcher B150

B150 is based on B149 and concentrates on collection stability, optional
behavior expansion, reversible upgrades, collection and price cheats, and
house-malfunction coverage.

## Highlights

- Fixed the Holiday Ornaments Collections Chest crash and expanded the visible
  collection total from 60 to 72 when Holiday Ornaments is enabled.
- Added a separately gated Behavior Patches option. It includes the requested
  spontaneous actions, age/weather/nursing/gender gates, web, nap, baby,
  sit-down, and bathroom-sink variations; Petting is no longer spontaneous.
- Fixed praise restarts so the current behavior wording remains stable,
  including native and radio behavior labels.
- Added Reset Ants, Reset All Collections, Complete All Collections, 2x/5x/100x
  Prices, Reset Price Multiplier, and Trigger All House Malfunctions cheats.
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

- 69 patch-generation and native-contract tests passed.
- 30 exporter and patcher-GUI tests passed.
- All 16 executable variants compiled and linked without logged errors and have
  distinct hashes.
- Final package: 1,075 asset patches, 1,112 payload files, and 16 executable
  records.
- Compact ZIP: 86,326,515 bytes, down from the pre-pruning 184,056,834-byte
  package without removing any selectable patch.
- Archive SHA-256:
  `5A2EAE1FA89D723CE808FD82EC3FDA182AEF3E02E298F79CD3EEEECE5E7BF1DE`.

The archive was structurally and automatically verified. Runtime behavior must
still be confirmed in a real B149 installation before treating every reverse-
engineered path as game-tested.
