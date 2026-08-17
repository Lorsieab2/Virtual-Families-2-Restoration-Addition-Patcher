# B171

Adoption Services is base-game again. Otherwise identical to B170.

## The crash

Purchasing Adoption Services crashed:

    Exception code:       0xC0000005   (access violation)
    Faulting module name: unknown
    Fault offset:         0x000001d7

"Unknown" module at `0x1D7` means execution left every loaded module and
jumped to a near-null address — a corrupted return address or function
pointer, not a bad data read.

## Cause

`patch_vf3_style_child_adoption_chooser` replaced the stock spawn route at
`CScrollingStoreScene::HandleUpgrade+0x57A` with a helper that put up a
"baby or older child" message box and spawned the adoptee itself. Two
things in it were wrong against the native code, and either could produce
this crash:

- It did not reproduce the stock call. Native is
  `SpawnSpecificPeep(age=1, gender=-1, body=0x3C)`; the helper passed
  `body=-1` with an explicit gender.
- It constructed a `theMessageBoxDlg` in a `0x300`-byte **stack** buffer,
  standing in for a class whose real size is not pinned anywhere. If the
  real object is larger, its constructor writes past that buffer and
  corrupts the return address — exactly an "unknown module" jump to a tiny
  address.

## Fix

Rather than guess which was fatal and ship another maybe-fix, the whole
route is reverted. `HandleUpgrade` is byte-identical to the stock object,
verified by diffing the patched object against `work/desktop_obj_files`:

    HandleUpgrade changed bytes: NONE - byte-identical to stock
    +0x57A: 6a 3c 6a ff 6a   stock: 6a 3c 6a ff 6a

Adoption Services behaves exactly as the base game does. No baby/older-child
prompt exists in any B171 executable.

**Nothing else is disabled** — one hook removed, every other patch intact.

## Also carried forward

Everything from B170, including the Family Tree fix (Bathroom 1's curtain id
no longer points at `familytree_bg.jpg`) and the bundle fixes that make the
installed game complete.
