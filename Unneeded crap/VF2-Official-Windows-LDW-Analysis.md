# Virtual Families 2 Official Windows Files

These are the files the output should be compatible with:

| File | Size | Notes |
|---|---:|---|
| `Virtual Families 2.exe` | 1,881,088 | Official Windows executable supplied by the user. |
| `Virtual Families 20.ldw` | 160 | Official Windows save/profile index. |
| `Virtual Families 21.ldw` | 154,408 | Official Windows game save. |

## Windows `.ldw` Header

The official Windows `.ldw` format is not the same as the Android `.ldw` wrapper previously analyzed.

Windows header is 16 bytes:

| Offset | Size | Value / Meaning |
|---:|---:|---|
| `0x00` | 4 | ASCII magic `ldwg` |
| `0x04` | 4 | Windows format constant: bytes `36 d8 6b 60`, little-endian `1617680438` |
| `0x08` | 4 | Zero field |
| `0x0c` | 4 | Little-endian payload length, equal to file size minus 16 |

Examples:

| File | Total size | Payload length field |
|---|---:|---:|
| `Virtual Families 20.ldw` | 160 | 144 |
| `Virtual Families 21.ldw` | 154,408 | 154,392 |

## Official Save Record Layout Clue

The main live/historical person table in `Virtual Families 21.ldw` appears to use:

- Table base: `0x17a74`
- Record stride: `0x7bc`
- Primary name: `record + 0x10`

First extracted records:

| Slot | Record offset | Name |
|---:|---:|---|
| 0 | `0x17a74` | `Sampi` |
| 1 | `0x18230` | `Pinki` |
| 2 | `0x189ec` | `Sampi` |
| 3 | `0x191a8` | `Rosie` |
| 4 | `0x19964` | `Purple` |
| 5 | `0x1a120` | `Pepper` |
| 6 | `0x1a8dc` | `Adrania` |
| 7 | `0x1b098` | `Rosie` |
| 8 | `0x1b854` | `Pinky` |
| 9 | `0x1c010` | `Pepper` |
| 10 | `0x1c7cc` | `Adrania` |
| 11 | `0x1cf88` | `Java` |

## Correction

The earlier generated `VF2-Native-Rebuild-Prototype.exe` was a toy prototype and not the intended target.
The correct direction is to work from the official Windows executable and official Windows `.ldw` files.
