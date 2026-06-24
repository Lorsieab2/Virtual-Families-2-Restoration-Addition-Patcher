# Additive Island Event Extension

## B55 design

The desktop `CIslandEvents` table is the source of truth. B55 preserves every
stock entry in slots `0x01` through `0x60` and appends mobile-only entries from
`work/mobile_event_shell_mapping.csv` beginning at slot `0x61`.

The native table is represented by `CIslandEvents::mEventList`; its companion
`mEventHasFired` array is moved forward when the pointer table grows. Known
stock scan bounds, destructor bounds, and `ForceEvent` range checks are widened
to the new exclusive end value. No existing event pointer is replaced.

## Compatibility requirements

`CIslandEvent` has a fixed base prefix: virtual-table pointer, target villager,
second target villager, and award amount. The added event object preserves that
prefix before storing text IDs. Target selection happens in `CanFire()` using
the same stock `GetRandomVillager(2, -1, 0)` shape used by `CEventBoring`.
This avoids dereferencing uninitialized villager state during the global event
table constructor.

The generated helper includes compile-time offset checks for the target/award
prefix (`+0x04`, `+0x08`, and `+0x0C`). A compiler/layout change therefore
fails the build instead of creating an incompatible event object.

Email-marked mobile records override `IsEmailEvent()` so the stock
`FireEmailEvent` path can select them. Non-email records remain available to
the normal event path. Mobile text and choices are rendered through the added
string IDs; B55 deliberately leaves gameplay rewards/effects at their stock
base-class no-op behavior until individual effects can be mapped safely.

The classifier explicitly recognizes every source class beginning with
`CEventEmail`, in addition to known mail shells and `Subject:`-headed records.
Those entries are inserted into the same appended table range as other mobile
events, but report `IsEmailEvent() == true` when the stock manager evaluates
them.

## Files changed

- `work/patch_mobile_furniture_pack.py`: fixes the appended event object
  layout/lifetime while retaining the additive table growth implementation.
- `work/BUILD_HISTORY.md`: records B55.
- `docs/island-event-extension-notes.md`: documents the table and compatibility
  contract.
