# VF2 B193 release notes

**The patcher bundle.** Prerelease for testing. Built from `main` at
`4cc8328` (PRs #362, #363), seeded from the B192 matrix.

B193 ships two owner-requested changes. Everything else is B192.

## 1. A new furniture item: the Invisible Ping-Pong Table

Requested: "add another furniture item? Invisible Ping-Pong Table: exactly
the same as the normal one but with transparent graphics."

Item 0x331, the ninth outdoor invisible piece. It carries the visible
Ping-Pong Table's donor (the Pool Table, 0x20C), store list, price and item
type, and ships the same sprite with a fully transparent `.pngORIGINAL`
beside it so the transparency setting can blank it while the visible table
is never blanked. Its borrowed Pool Table map is retargeted to the
Ping-Pong Table's own object 0x9A, so a drop on either table plays
ping-pong rather than resolving to a pool table. The drop dispatch names
both ids and the ping-pong action carries the invisible id as its
alternate, so a placed invisible table is a venue and a villager dropped on
it counts as standing on it. The spontaneous route needed no change: its
candidate is gated on the shared object 0x9A.

Like every invisible item, its generation lock is 0 so it is available from
the first generation. PR #362.

## 2. Achiever Extraordinaire now tracks every goal the Goals screen shows

Audit requested: "audit the goal 'Achiever Extraordinaire' to account for
the newly-added goals." The audit found two defects, both of which made the
meta-goal unawardable and both of which had been getting worse with every
goal added.

First, the 19 Holiday Furniture goals (0x6D-0x7F) were listed in the visible
order array ahead of the meta-goal, but whether they are visible is a
runtime byte. The native Goals screen walks that array contiguously to the
visible count, so in every build without Holiday Furniture the screen ended
on an unearnable holiday goal and never drew Achiever's row; its completion
scan demanded the same unearnable goal. The optional block now follows the
meta-goal, so the drawn window is contiguous in both states.

Second, the "Complete all achievements" cheat enumerated hand-written id
ranges and silently missed 24 visible goals, including the new "No banging
dishes together!" goal. It now derives its list from the visible order
array, so any goal on the Goals screen is completed automatically.

Verified against the emitted achievement object in both runtime states. PR
#363. Not verified in play.
