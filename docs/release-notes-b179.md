# VF2 B179 release notes

**The patcher bundle.** Prerelease for testing.

Marked prerelease: every automated gate passes and every feature below was
confirmed present in a linked build, but **nothing here has been played.**

## New this release

**100 hairstyles in the store.** The Clothing and Hairstyles section gains 50
hairstyles for each gender, at 75 coins each — the same price as an outfit.
They ride the outfit tool, because the game has no hairstyle tool of its own:
pick one from the tray and drop it on a villager the way you would an outfit,
and it changes their head and leaves their body alone.

Every icon is cut from the game's own head artwork — the front-facing frame of
that hairstyle's row — so what the store shows is the hairstyle you get.

This mechanism was added in B178 but was never reachable: the value it selected
was read in two places and written in none, so applying a hairstyle could only
ever do nothing. That is what this release fixes.

**The Ping-Pong Table gets its own action.** Villagers using it are now
"Playing ping-pong" or "Rallying back and forth" instead of "Playing pool".

The table borrows the Pool Table's behaviour, which is what gives it any
interaction at all, and both answer to the same object type — so the label is
chosen by looking at which table the villager actually walked to. A stock Pool
Table is untouched and keeps its own label.

## Fixes

**The Ping-Pong Table is buyable again.** It was removed from the store by
mistake between B178 and this release. The item, its price of 12,000 (the Pool
Table's own), its artwork and its footprint are all back.

**Details no longer says "Married" for a proposal that never happened.** A
spawned proposal candidate counted as one of the two resident adults, so the
Details screen could describe a marriage before it was accepted — or after the
proposal was abandoned. It now waits for the family tree to actually record the
marriage.

**A grown child living at home is no longer mistaken for a spouse.** The
marriage-pair fallback counted any two qualifying adults, and an employed adult
child passes every one of those tests. Recorded children are now excluded, and
the family record is checked for validity before its child list is read.

**Bathroom 2 fixtures no longer stay broken when the remodel is switched off.**
A save written by a build that had the remodel carried a flag that made its
shower, toilet and sink unusable. Clearing it only ever ran when the remodel
was *enabled* — the opposite of when it was needed. It now runs either way.

**Both Order goals count.** "Bubble Bass's Order" and "Kirk Strayer's Order"
are awarded and counted toward completion, and the Goals screen can read as
fully complete again.

**A startup crash.** Growing a code section left every relative branch that
spanned the insertion pointing at the wrong place — in one case one byte into
the middle of an instruction — so some builds crashed on launch. Branches are
now re-aimed when a section grows.

**Yoga gets an even split** as a Quick workout variation.

**The launchers reach their Python fallback**, and refuse politely on anything
older than Python 3.9 instead of failing deep inside the build.

**Five Invisible Spa Lounger fixes** and **the invisible tables get their own
footprints**, so they no longer borrow a neighbour's.

## Under the hood

A latent bug found while adding the hairstyles: the store's Clothing category
bounds check was patched as an 8-bit compare whose immediate the processor
sign-extends. With 114 rows it still fit. With 214 it would have inverted the
guard entirely and let the store read past the end of its own list. It is now a
real 32-bit compare.

The Same-Sex Marriage runtime-flag check used to treat a *missing*
`source_section` key as "this flag lives in the save payload, nothing to
verify" — so a misspelled or half-written contract looked exactly like the
legitimate case and passed. It now fails closed.

A ping-pong helper was written with f-string syntax inside a raw-string
template, so the generated C carried a literal placeholder and would not
compile in any build with Behaviour Patches enabled. Caught by the matrix
build; the tests now assert the emitted C rather than the Python that emits it.

The build also declares Pillow alongside capstone, so a clean machine that
follows the documented install can actually build.
