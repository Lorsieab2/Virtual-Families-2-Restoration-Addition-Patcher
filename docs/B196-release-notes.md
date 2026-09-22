# VF2 B196 release notes

**The patcher bundle.** Prerelease for testing. Built from `main` at
`0a93dc0` (PR #375), seeded from the B195 matrix.

B196 ships one owner-requested change. Everything else is B195.

## Villagers choose ping-pong as often as pool

Requested: *"Raise pingpong weight to same as pool table."*

Ping-pong was **already** something villagers could choose on their own, and
already restricted to houses that actually own a table. What was wrong was how
*often*: the candidate is cloned from the Pool Table's behaviour and was given
a weight of 450, while the Pool Table's own candidate carries 3000. A ping-pong
table was therefore offered roughly a seventh as often as the pool table it was
copied from, which in play looks like villagers ignoring it.

The weight is now 3000, the same as the Pool Table.

Only the weight changes. The rule that decides *whether* the action is offered
at all is untouched: the Ping-Pong Table has its own content-map object, so the
behaviour is available only while a table is placed, and raising the weight
cannot make a villager play ping-pong in a house without one.

**Both tables count**, visible and invisible. Availability is decided by the
object each table's map declares, not by which item it is, and the build's own
assets show both maps declaring the ping-pong object on ten cells each --
with neither still carrying the stock Pool Table's object, which is what kept
the invisible table playing pool in older builds.

Verified against the compiled code rather than the source: the emitted call is
decoded out of the instruction stream and must push 3000, and reverting it to
450 fails that check. The full link of the patched objects succeeds. Not
verified in play.

**Playtest:** with a ping-pong table placed -- try each of the visible and
invisible ones -- leave villagers to their own devices and see whether they
choose to play. In a house with no ping-pong table, they should never do so.

Still open from earlier builds, for the owner's eyes: Achiever Extraordinaire
is the bottom Goals row with Holiday Furniture on; the Invisible Ping-Pong
Table plays ping-pong; Achiever awards in a build without Holiday Furniture.
