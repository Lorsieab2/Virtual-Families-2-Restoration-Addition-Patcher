# B156 mobile renovation overlays

These 15 curated PNGs are the exact mobile room overlays recovered from the
user-supplied Virtual Families 2 1.7.16 Android package. The bulk APK extraction
remains ignored under `work/vf2_apk_extract/`; these game-ready inputs are
tracked so B156 does not depend on an outside path.

The Android atlas extraction produced the overlays upside down for the desktop
renderer. On 2026-07-18, each image was corrected by reversing its decoded RGBA
rows from top to bottom. Nothing was rescaled, cropped, redrawn, generated, or
color-adjusted. The untouched extracted PNGs remain the comparison source.

`work/flip_mobile_renovations_upright.js` performs the allowlisted conversion
and verifies every output row against its reversed source row before replacing
the curated set. It writes a native-size contact sheet and per-file SHA-256 QA
manifest to the ignored `outputs/` folder.

Bathroom 1 uses the five bathroom variants in this directory. The optional
Bathroom 2 patch must reuse these same corrected Bathroom 1 graphics.
