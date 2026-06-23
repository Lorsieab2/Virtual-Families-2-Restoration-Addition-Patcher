# VF2 Desktop EXE Candidate Comparison

New file supplied:

`C:\Users\Owner\Downloads\Base Virtual Families 2 - Copy\Virtual Families 2.exe`

Copied as:

`work/desktop_exe_candidates/Virtual Families 2 - Base Copy.exe`

## Result

The supplied EXE is byte-identical to:

`work/vf2_windows_test/Virtual Families 2 - Copy Official.exe`

Shared properties:

- Size: `1,881,088` bytes
- SHA-256 prefix: `67e8cf073be89b96`
- Embedded `Furniture/...png` paths: `239`
- Unique embedded furniture paths: `239`

## Mobile Furniture Check

The EXE does not contain these mobile/event furniture strings:

- `Chaise`
- `Furniture/Chaise`
- `Patio_brick`
- `Furniture/Patio`
- `Picnic_table`
- `Furniture/Picnic`
- `Birthday_cake`
- `Furniture/Birthday`
- `ChristmasTree1`
- `Furniture/Christmas`

## Meaning

This is the same useful desktop candidate already analyzed: it is the larger official/copy build and likely the best patch target, but its hardcoded furniture table still lacks the mobile/event furniture entries.

The table order begins with:

1. `Furniture/bbq pair.png`
2. `Furniture/bbq pair red.png`
3. `Furniture/Rendered BedPair 1.png`
4. `Furniture/AntiqueRadioStd.png`
5. `Furniture/AqauriumStd.png`

and ends with:

235. `Furniture/SingleBedBlue.png`
236. `Furniture/SingleBedGreen.png`
237. `Furniture/SingleBedOrange.png`
238. `Furniture/SingleBedPink.png`
239. `Furniture/SingleBedRed.png`

