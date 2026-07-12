# B151 release notes

B151 focuses its third workstream on completing the Holiday Ornaments collection and repairing the B150 crash-prone implementation. The expanded-map concept and the proposed new goals remain deferred; neither is implemented in B151.

## Holiday Ornaments

- Restores the twelve mobile 1.7.16 Holiday Ornament collectibles (`0x9E` through `0xA9`) as a sixth collection page, increasing the Collections Chest display from 60 to 72 collectibles.
- Uses the three mobile spawn rectangles, for 19 registered collectible spawn areas in total. Common, uncommon, and rare ornaments occupy exact four-item ranges: `0x9E`-`0xA1`, `0xA2`-`0xA5`, and `0xA6`-`0xA9`.
- Retains stock exact-match `Find`, `WasItemSpawned`, and `Add` behavior, including the stock Lucky Rock thresholds. The unsafe B150 Holiday-family matching detours are not used.
- Places the twelve ornaments in mobile order using positions scaled by `1.28` for the PC fallback descriptors. Collections Chest drawing and tooltips use fixed detours and isolated code caves rather than overwriting adjacent scene state.
- Keeps collection counts compatible with the stock `0xAF`-entry reset, save, and load spans.
- Corrects the collection achievement targets: Master Collector (`0x4D`) requires six completed collections, Goal Collector (`0x54`) requires thirteen contributing achievements, and Ornamentologist (`0x5F`) requires twelve unique ornaments. The achievement notification queue covers `0x60` entries.
- Includes Holiday counts in the Collector's common, uncommon, and rare offer calculations through relocation-only insertions. Selling the Holiday collection uses the stock single-achievement reset helper; the Collector's stock Keep and event-availability behavior remains unchanged.
- Uses thirteen canonical PNGs: one collection background and twelve ornament images. Disabled Holiday builds clean their Holiday art instead of leaving inactive collection assets installed.

## Build coverage and testing status

All sixteen B151 matrix executables compile. The 129 source/exporter tests pass, and independent linked validation passes all sixteen executables: eight Holiday-enabled and eight Holiday-disabled builds with unique hashes. Static checks cover native registrations, collection UI tables and caves, persistence spans, achievements, Collector integration, canonical artwork, cleanup, and matrix separation.

Manual in-game testing is still required before calling the feature runtime-proven. The remaining cycle is: launch and idle through collectible spawning; open and navigate the Collections Chest; pick up unique and duplicate ornaments across all rarities; save and reload; exercise the Collector's Keep and Sell choices; and verify Reset All Collections and Complete All Collections. Static validation does not replace that gameplay test.
