# VF2 B194 release notes

**The patcher bundle.** Prerelease for testing. Built from `main` at
`3551bd9` (PRs #366, #367), seeded from the B193 matrix.

B194 ships two owner-requested changes. Everything else is B193.

## 1. Spa Lounger drop degrade documented (no behaviour change)

A villager dropped on a Spa Lounger (visible 0x330 or Invisible 0x32F)
sometimes performs an ordinary chaise "Relaxing on lounger" relax instead of
the spa treatment, at either orientation. Both spa loungers share the stock
eObjectChaise object with every ordinary chaise, and LinkPeepToFurniture
searches from the villager's feet and reserves the nearest free peep slot, so a
drop can link a different chaise: a nearer ordinary one, the other spa lounger,
or this lounger skipped because an ordinary relaxer the spa occupancy check
cannot see holds its slot.

That degrade is deliberate: LinkPeepToFurniture is the reservation, takes no
anchor point, and has no unlink API, so a wrong link cannot be given back.
Re-resolving the dropped-on lounger afterwards splits the reservation from the
villager and was rejected across earlier review rounds. B194 records why the
obvious fix is absent -- a comment on the fallback and a characterization test
-- and changes no runtime behaviour. Issue #365, PR #366.

## 2. Achiever Extraordinaire always draws as the last Goals row

Requested: move the goal "Achiever Extraordinaire" so it is always at the bottom
of the list regardless of patches enabled, and confirm it autocompletes when
every goal is complete in any patch combo.

The custom meta-goal (0x92) was last only when Holiday Furniture was off: the 19
holiday goals (0x6D-0x7F) sit after it in achievementOrder so the drawn window
stays contiguous when the runtime byte is zero (B193 audit), which drew the
meta-goal about twenty rows from the bottom when holiday was on. B194 leaves that
physical order -- correct for the position-independent completion scan -- and
changes only the draw: the Goals loop now walks a display copy,
achievementDisplayOrder, that is the same visible window with 0x92 pulled to the
end, rebuilt each draw for the current runtime holiday state. Its length equals
the visible count, so the scroll offset, content height and order-end bound are
unchanged. The completion scan and the Complete all achievements cheat still read
the real achievementOrder, so autocomplete, which already worked in every patch
combo, is untouched.

Verified against the emitted achievement object in both runtime states: the
display copy ends on 0x92 with the window length preserved (152 rows holiday off,
171 on with all 19 holiday rows before the meta-goal). PR #367. The bottom-row
placement with Holiday Furniture on is a cosmetic property for in-game playtest.
