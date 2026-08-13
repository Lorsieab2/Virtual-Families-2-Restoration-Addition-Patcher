# Virtual Families 24.ldw Desktop Save Check

File analyzed:

`C:\Users\Owner\Downloads\Virtual Families 24.ldw`

## Result

This is a desktop/Windows-format `Virtual Families 2` save.

Key evidence:

- File size: `154,408` bytes.
- Header magic: `ldwg`.
- Windows-style 16-byte header:
  - `0x00`: `ldwg`
  - `0x04`: `ee bd 82 60` (`1619181038` little-endian)
  - `0x08`: `0`
  - `0x0c`: `154392`, which equals file size minus 16.
- This matches the official desktop save shape:
  - `Virtual Families 21.ldw`: `154,408` bytes
  - payload length field at `0x0c`

## Correction To Earlier Assumption

Seeing names like `Alex` in a save is not enough to classify it as synthetic/prototype data.
Desktop saves can naturally contain names like `Alex`, `Joey`, etc.

The reliable format discriminator is the header layout:

| Format | Size | Header layout |
|---|---:|---|
| Desktop/Windows | `154,408` | `ldwg`, version/timestamp-like field, zero, payload length at `0x0c` |
| Android/mobile | `154,400` | `ldwg`, Android constant, payload length at `0x08` |

## Desktop Person Table

This save matches the desktop person-record pattern:

- Person table base: `0x17a74`
- Record stride: `0x7bc`
- Primary name: `record + 0x10`

First extracted records:

| Slot | Offset | Name |
|---:|---:|---|
| 0 | `0x17a74` | `Saphiana` |
| 1 | `0x18230` | `Inch` |
| 2 | `0x189ec` | `Burozo` |
| 3 | `0x191a8` | `Giga` |
| 4 | `0x19964` | `Alex` |
| 5 | `0x1a120` | `Brola` |
| 6 | `0x1a8dc` | `Bengi` |
| 7 | `0x1b098` | `Fabula` |
| 8 | `0x1b854` | `Lina` |
| 9 | `0x1c010` | `Balono` |
| 10 | `0x1c7cc` | `Pod` |
| 11 | `0x1cf88` | `Rosetta` |

