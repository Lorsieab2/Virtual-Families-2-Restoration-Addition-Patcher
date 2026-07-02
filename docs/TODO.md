# TODO

## Highest Priority

- Refactor the mod so releases stop distributing modified executables. Build an
  offline vanilla-to-modded VF2 PC patcher that takes a user-provided original
  VF2 executable, verifies the original EXE hash/version before patching,
  creates a backup, applies clean patch records from a JSON patch manifest, and
  writes a patch log. Initial byte-patch/restore scaffold exists in
  `work/offline_vf2_patcher.py`, including manifest-declared toggleable
  settings and a Tkinter GUI wrapper; next step is converting current VF2 build
  changes into release manifests and asset/table patch records.
- Define the JSON patch manifest contract: each patch record must include file
  path, offset, expected original bytes, replacement bytes, and note. The
  patcher must refuse to patch when expected bytes do not match, and it must
  provide a restore option that can put the backed-up original files back.
- Keep the offline patcher simple and trust-friendly: avoid runtime injection,
  process memory editing, obfuscation, packers, and admin requirements. Prefer
  data, asset, and table patches over executable patches whenever possible.
- Make antivirus false-positive reduction the top packaging priority. Prefer
  transparent patching and reproducible build artifacts over packed/obfuscated
  executables, preserve normal PE metadata where possible, sign the patcher and
  produced executable with a valid code-signing certificate, publish hashes, and
  maintain a McAfee/SmartScreen/AV vendor false-positive submission process for
  release builds.

## Research Leads

- Implement the mobile VF2 Holiday Ornaments collectible set in the PC build:
  add a dedicated Collections screen page, add associated Goals screen entries,
  wire goal-completion triggers, and port the correct ornament spawning logic
  with mobile-version data parity.
- Add an optional setting for mobile-exclusive furniture behavior support on
  added mobile-exclusive furniture in the PC build, then implement the correct
  villager behavior routes for those furniture items.
- Implement the correct outcomes for added mobile-exclusive Island Events.
  Current added events can fire but do not yet perform their mobile outcomes.
- Allow the second bathroom to have water leaks like the first bathroom; the
  current first-bathroom-only leak behavior is an inconsistency.
- Allow the Kitchen, Workshop, and Office to be renovated with their exclusive
  mobile renovation variants.
- Make all house renovations and upgrades removable and purchasable again after
  removal.
- Continue B63 in-game validation after the confirmed save-load crash fix:
  click normal gameplay/furniture UI, open General Appliances, place the VF3
  TVs, and verify base TV behavior is unchanged.
- Rebuild debugger support as an isolated opt-in/dev-only path. Do not patch
  main-scene mouse handlers in normal builds; first prove a key/display-only
  debugger path can load saves and run without crashes.
- Audit other category list count patches for small/common desktop counts before
  adding more furniture entries.
- Verify the three VF3 TV appliances are visible in General Appliances and keep
  base TV click/animation behavior untouched.
