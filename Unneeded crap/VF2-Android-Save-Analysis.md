# Virtual Families 2 Android Save Analysis

Source archive: `com.ldw.virtualfamilies2.zip`

## Files

| File | Size | Role |
|---|---:|---|
| `ldwlog.txt` | 0 bytes | Empty log file. |
| `wc.dat` | 232 bytes | Plain JSON ad/session config. Not core game state. |
| `virtual families 20.ldw` | 220 bytes | Binary LDW metadata/index file. Contains player-slot labels. |
| `virtual families 21.ldw` | 154,400 bytes | Binary LDW game-state file. |
| `virtual families 221.ldw` | 154,400 bytes | Binary LDW game-state file, likely backup/snapshot for `21`. |

## `.ldw` Wrapper

All `.ldw` files use the same 12-byte wrapper:

| Offset | Size | Meaning |
|---:|---:|---|
| `0x00` | 4 | ASCII magic `ldwg`. |
| `0x04` | 4 | Constant/version-like value: bytes `00 6f 71 5e`, little-endian integer `1584492288`. |
| `0x08` | 4 | Little-endian payload length. This equals file size minus 12. |

Examples:

| File | Stored payload length | Actual payload length |
|---|---:|---:|
| `virtual families 20.ldw` | 208 | 208 |
| `virtual families 21.ldw` | 154,388 | 154,388 |
| `virtual families 221.ldw` | 154,388 | 154,388 |

## `wc.dat`

This is readable JSON:

```json
{
  "vf2": {
    "interstitials": {
      "exclude_payers": 0,
      "session": 20,
      "video": 600,
      "max_per_day": 3,
      "min": 180,
      "tutorial": 900,
      "first_days": 3,
      "first": 3600
    }
  },
  "session_id": "d62eb06a32692dbe37338cba68ecad0c",
  "id": "034e0ba1-0af3-4646-8d35-7b9c35142ec0"
}
```

This looks like web/config/ad pacing data, not household state.

## `virtual families 20.ldw`

This small file is probably the save-slot index/profile metadata. It contains:

- Header `ldwg`.
- Several small integers.
- Repeated fixed-width player labels, including `NEW PLAYER`.
- Timestamp-like 32-bit values such as `1586724889` and `1586724930`.

Notable early fields:

| Offset | Little-endian value |
|---:|---:|
| `0x0c` | `1` |
| `0x14` | `1` |
| `0x1c` | `1539` |
| `0x20` | `100045` |
| `0x94` | `999` |
| `0x9c` | `1586724889` |
| `0xa0` | `1586724889` |
| `0xbc` | `1586724930` |

## Large Save Layout

The large files are not compressed or fully encrypted. They contain many plain ASCII strings and fixed-width binary records.

Readable strings include generated names and traits/interests:

`Cocoa`, `Bingone`, `loose socks`, `burgers`, `eating`, `shopping`, `playing`, `babies`, `thunder`, `work`, `music`, `vegetables, lightning`, `medicine`, `sweets`, `BBQ, grass`, `spiders`, `outdoors`, `solitude`, `exploring`.

High-level regions found in `virtual families 21.ldw`:

| Region | Offsets | Observation |
|---|---:|---|
| Header/global flags | `0x0000`-`0x16ff` | Mostly zeroes and small integers. |
| Name/template catalogue | `0x1700`-`0x54ff` | Readable generated names, likes/dislikes, fixed records. |
| Unknown middle region | `0x5500`-`0xdfff` | No obvious strings; identical between `21` and `221`. |
| Object/world state | `0xe000`-`0x172af` | Many 4-byte differences between `21` and `221`, mostly aligned to a 64-byte pattern. Likely furniture/room/object positions or timers. |
| Person slots | `0x172b0`-`0x1cf7f` | 12 repeating live/historical person records. |
| Tail data | `0x1cf80`-end | Many differences; likely additional world state, random/event data, checksums, or serialized arrays. |

## Live/Historical Person Records

The clearest structure is a 12-slot person table:

- Table start: `0x172b0`
- Record stride: `0x7bc` bytes, or 1980 decimal
- Primary person name: `record + 0x10`

Extracted slots from `virtual families 21.ldw`:

| Slot | Record offset | Name | Other readable strings in record |
|---:|---:|---|---|
| 0 | `0x172b0` | `Magica` | noise-like strings only |
| 1 | `0x17a6c` | `Franella` | none |
| 2 | `0x18228` | `Trishie` | none |
| 3 | `0x189e4` | `Smiley` | noise-like strings only |
| 4 | `0x191a0` | `Katila` | `Joey` |
| 5 | `0x1995c` | `Sophella` | `Joey`, `Katila` |
| 6 | `0x1a118` | `Pennette` | noise-like strings only |
| 7 | `0x1a8d4` | `Petta` | noise-like strings only |
| 8 | `0x1b090` | `Marcor` | `Joey`, `Soonetta` |
| 9 | `0x1b84c` | `Gepu` | none |
| 10 | `0x1c008` | `Trishina` | `Joey`, `Soonetta` |
| 11 | `0x1c7c4` | `Uffa` | noise-like strings only |

The first few 32-bit integers in each record appear to include IDs, state flags, age/gender/status values, or relationship indices. For example, slot 0 begins:

```text
0x172b0: 156, 1, 84, 1, "Magica", ...
```

and slot 1 begins:

```text
0x17a6c: 136, 1, 99, 1, "Franella", ...
```

## Difference Between `21` and `221`

Both large files:

- Have identical length.
- Have identical wrapper headers.
- Have identical readable template/name region.
- Differ by 3,666 bytes total.

Difference distribution:

| Region | Differing bytes |
|---|---:|
| Header/global first 256 bytes | 0 |
| Template/name region | 0 |
| Unknown middle region | 0 |
| Object/world state | 1,274 |
| Person slots | 24 |
| Tail | 2,368 |

The object/world-state differences are mostly 4-byte chunks at offsets `record + 0x28` through `record + 0x2b` in a repeating 64-byte pattern. This is consistent with serialized numeric state changing between two snapshots.

## Practical Takeaways

- Save editing is plausible because the format is mostly fixed binary records with plain strings.
- A save viewer/parser should start with:
  1. Validate `ldwg`.
  2. Validate payload length at `0x08`.
  3. Parse the 12 person records from `0x172b0` with stride `0x7bc`.
  4. Extract null-terminated ASCII names at `record + 0x10`.
  5. Treat unknown numeric fields conservatively until correlated with multiple saves.
- A robust editor needs multiple controlled saves where exactly one thing changes, such as money, food, a character name, a room action, or elapsed time. One archive is enough to map structure, but not enough to confidently label most numeric fields.

