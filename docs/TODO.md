# TODO

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
- Confirm B61 in-game after the save-load crash fix: load the affected save,
  open General Appliances,
  place the VF3 TVs, and verify base TV behavior is unchanged.
- Decide whether the debug editor needs a safer mouse-move forwarding strategy
  that cannot early-return from `theMainScene::HandleMouseMove`.
- Audit other category list count patches for small/common desktop counts before
  adding more furniture entries.
- Verify the three VF3 TV appliances are visible in General Appliances and keep
  base TV click/animation behavior untouched.
