# TODO

## Highest Priority

- Build a vanilla-to-modded VF2 PC patcher that takes a clean/vanilla PC build,
  verifies the expected input version, applies the project patches and added
  data, and produces a reproducible modded build without requiring distribution
  of stale prepatched executables when avoidable.
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
- Confirm B61 in-game after the save-load crash fix: load the affected save,
  open General Appliances,
  place the VF3 TVs, and verify base TV behavior is unchanged.
- Gate debugger selection functions behind a Function-key activation path:
  normal play should ignore debugger selection unless the chosen Function key
  has enabled debugger mode for that session.
- Decide whether the debug editor needs a safer mouse-move forwarding strategy
  that cannot early-return from `theMainScene::HandleMouseMove`.
- Audit other category list count patches for small/common desktop counts before
  adding more furniture entries.
- Verify the three VF3 TV appliances are visible in General Appliances and keep
  base TV click/animation behavior untouched.
