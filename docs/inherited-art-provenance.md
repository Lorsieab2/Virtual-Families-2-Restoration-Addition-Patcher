# Inherited-only runtime art provenance

The holiday body source is now self-contained in the repository. The tracked
archive is `data/vf2/source_assets/Holiday Outfits.zip` (488 PNG members,
SHA-256 `958BA1C6659417C32B3D9B4E028D75BFD65348239C8A6C54FE53235F5509D6A5`).
It was copied from the Codex workspace's extracted mobile source:

`2026-06-01/virtual-families-2-has-a-lot/work/holiday_graphics_extract/Holiday Outfits/`

The archive preserves the original `Female Outfits` and `Male Outfits`
directories and filenames. The generator consumes the 448 members in source
sets 51--54 to produce Body_50--Body_53 action, body, and sit frames. The
remaining 40 archive members are retained because they are part of the same
verified source extraction and keep the source set complete.

`work/patch_mobile_furniture_pack.py` points only to this repository-local
archive. Holiday frame generation no longer searches the output directory,
previous builds, or generated runtime folders. Its template lookup is limited
to the local vanilla runtime payload, and a missing archive fails before any
fallback can be reported as generated.

The other inherited-only categories remain unresolved and are intentionally
not papered over:

| category | count | current evidence |
| --- | ---: | --- |
| Furniture | 93 | only the preserved B175/B176 runtime copies are present; no independent tracked source identified |
| Upgrades | 61 | preserved copies include 30 `.xcf` editing sources and 30 `original images`; runtime-vs-backup classification remains open |
| root Images | 25 | preserved copies only; no independent tracked source identified |
| OutfitIcons | 8 | preserved copies only; no independent tracked source identified |

Therefore `data/vf2/inherited-only-images.json` and its build validation must
remain until those 187 files have an independent source or an evidence-backed
decision removes them from the shipped runtime set.
