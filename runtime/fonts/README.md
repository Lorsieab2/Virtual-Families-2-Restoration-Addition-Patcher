# Bundled fonts

The open fonts the Unicode text DLL (`runtime/native/b200unicode/b200unicode.cpp`, `kBundledFonts`) loads for the
game only (`AddFontResourceExW` with `FR_PRIVATE`: never installed in Windows), as the last steps of the fallback
chain (`docs/UNICODE_TEXT.md`), and the patcher's Game Text preview loads the same way (`src/vf2_glyph_render.py`,
`load_bundled_fonts`). They ship in `Unicode Text\Fonts\` (Render Unicode with In-Game Fonts) and
`Unicode Font Text\Fonts\` (Use Unicode Font) beside the DLL, each setting removing only its own copies.

Every file is the published release byte for byte (`tests/test_bundled_fonts.py` checks each SHA-256 and size; git
never changes them: `.gitattributes`). How each was verified on 2026-11-03:

* Unifont: downloaded from `https://ftp.gnu.org/gnu/unifont/unifont-18.0.01/` with its `.sig`; GnuPG verified each
  signature against the GNU keyring (`https://ftp.gnu.org/gnu/gnu-keyring.gpg`): "Good signature from Paul Hardy
  <unifoundry@unifoundry.com>", key `95D2 E9AB 8740 D804 6387 FD15 1A09 227B 1F43 5A33`. The licence files are from
  the signed `unifont-18.0.01.tar.gz` of the same folder.
* Last Resort High-Efficiency: `https://github.com/unicode-org/last-resort-font/releases/tag/18.000`; the SHA-256 is
  the one GitHub publishes for the release asset (`digest`). Its `LICENSE` is the OFL.
* Noto Serif Tangut: `https://github.com/notofonts/tangut/releases/tag/NotoSerifTangut-v2.170`, the asset
  `NotoSerifTangut-v2.170.zip` (GitHub digest `741ef7bca66790c51c5f2efea3c291f5a82cc2e3992d9413a020aec26dbd75b1`);
  the font is its `unhinted/otf` build.
* Noto Sans Cuneiform: `https://github.com/notofonts/cuneiform/releases/tag/NotoSansCuneiform-v2.001`, the asset
  `NotoSansCuneiform-v2.001.zip` (GitHub publishes no digest for it; the zip's `googlefonts/ttf` build is byte for
  byte the file google/fonts ships, blob `e5b3b879d9439ead2df6a675419f91abc73c7a7f`); the font is its `unhinted/otf`
  build.
* The Unicode Character Database the tables are made from (`runtime/tools/gen_b200_unicode_tables.py`):
  `https://www.unicode.org/Public/18.0.0/ucd/UnicodeData.txt`, SHA-256
  `0736451de439ae7baf1425136617da495e09ee5afbe6e394374db7009ea08950`, under `UNICODE-LICENSE.txt`
  (`https://www.unicode.org/license.txt`).

| File | What | Version | Size | SHA-256 | Licence |
| --- | --- | --- | --- | --- | --- |
| `NotoSansCuneiform-Regular.otf` | Noto Sans Cuneiform | 2.001 | 433,748 | `ac997e70013545b311a1703eacd3d8dea080b7b9e17924a69391a6f568b9c023` | `NotoSansCuneiform-OFL.txt` |
| `NotoSerifTangut-Regular.otf` | Noto Serif Tangut | 2.170 | 1,914,772 | `ca10571246bdce735fac2698e875d86ed73354c76c650bb92c4d7cb43973aed6` | `NotoSerifTangut-OFL.txt` |
| `unifont-18.0.01.otf` | GNU Unifont (U+0000..U+FFFF) | 18.0.01 | 5,320,148 | `88d0a14d4aa9a96419720b39ba5da921a59560d76d4ec7d523acc06ed85cd3c2` | `Unifont-OFL-1.1.txt`, `Unifont-COPYING.txt` |
| `unifont_upper-18.0.01.otf` | GNU Unifont Upper (above U+FFFF) | 18.0.01 | 5,954,156 | `472201e45a050bff4c7658208b8c73e34ebce3764b287a5a46c7774038ef9391` | `Unifont-OFL-1.1.txt`, `Unifont-COPYING.txt` |
| `LastResortHE-Regular.ttf` | Last Resort High-Efficiency | 18.000 | 587,864 | `cb7c2262cb86a33e7bdfabd0a51746e738b0dd10924126c4530c414c5fc7e4b6` | `LastResort-OFL.txt` |
| `NotoSansCuneiform-OFL.txt` | SIL Open Font License 1.1 (Noto Sans Cuneiform) | | 4,385 | `83e16aed35737ea80911a82938ad4bfe762fde24928010c2c80d21ece07bec14` | |
| `NotoSerifTangut-OFL.txt` | SIL Open Font License 1.1 (Noto Serif Tangut) | | 4,382 | `bd8b32c064be2225d55f878a689063c6f169ccd9e2792d7051f0d74cf4816f1b` | |
| `Unifont-OFL-1.1.txt` | SIL Open Font License 1.1 (Unifont) | | 4,340 | `869692af094c57fb7258c57fe26820c759319603321d0ffeb278de3651763ded` | |
| `Unifont-COPYING.txt` | GNU GPL 2 or later with the font embedding exception (Unifont) | | 48,441 | `cd2785c2b8e0a01d203560265b2d2d47cdb1401d2707d25918ac5531bcdba947` | |
| `LastResort-OFL.txt` | SIL Open Font License 1.1 (Last Resort) | | 4,335 | `fc8fc512b27846bdb0d6645bed8069ac87ea599548b58a8d04bc3b0ea705a9c4` | |
| `UNICODE-LICENSE.txt` | Unicode License v3 (the Unicode Character Database tables) | | 1,995 | `e7a93b009565cfce55919a381437ac4db883e9da2126fa28b91d12732bc53d96` | |

Unifont is dual-licensed (OFL 1.1, or GPL 2+ with the GNU font embedding exception); both texts ship. Unifont and
Last Resort have a glyph for every code point (Unifont a hexadecimal box, Last Resort a block symbol), so the DLL and
the patcher only let them draw assigned code points that are not controls or surrogates (`UT_ASSIGNED` /
`vf2_unicode_tables.ASSIGNED`); the rest keep the missing-glyph box.
