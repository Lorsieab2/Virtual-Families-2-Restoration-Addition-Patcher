# Email To Player System

## Computer Action

The visible action label `Sending email to player` is string id `0x0721`
(`eString_SendingEmail`) from `theStringManager.obj`.
`CBehavior::BrowsingWeb2` dispatches that id to
`CVillagerPlans::PlanToWriteToPlayer`, which creates action/plan type `0x41`.
The related read-email route uses string id `0x0720`
(`eString_ReadingEmail`) and `CVillagerPlans::PlanToReadEmail`, plan type
`0x40`.

Both routes use the computer chair orientation, choosing `Sit In Chair NW` or
`Sit In Chair NE` from the computer furniture orientation.

Generated string dumps:

- `outputs/vf2-email-to-player-strings/sending-email-to-player-strings.md`
- `outputs/vf2-email-to-player-strings/sending-email-to-player-strings.json`

## Email Queue

`theMainScene` pops queued email messages and routes them by numeric type:

| Queue value | Meaning | Route |
| --- | --- | --- |
| `1` | Island/email event | `CIslandEvents::FireEmailEvent(scene)` |
| `2` | Marriage proposal email | scene `7` |
| `3` | College kid email | `CCollegeKidEmail::Show(scene)` |

The random island/email event cadence uses cooldown field
`theGameState+0x25ADC`. When it expires, the game requires a nonzero
population, a random living villager who is idle, and no pending message type
`1`. It then queues the email event on `GetRandom(100) < 0x42` (66%).
Otherwise it fires a normal island event and resets the same `0xE10` second
cooldown.

`theGameState::MaybeSendCollegeKidEmail` queues message type `3` when
`theGameState+0x25AF0` has expired and
`CVillagerManager::GetRandomCollegeKid()` returns a villager. The next timer is
set by `UpdateCollegeKidEmailTimer()` to now plus
`(GetRandom(0x10) + 0x14) * 0xE10` seconds.

## Daily Email Composition

`CDailyEmail::Show(ldwScene*, int)` builds player mail in this order:

1. `eString_EmailHeader`
2. one random greeting (`GetRandom(5)`)
3. optional first-adoption comment
4. optional return-after-save comment
5. one primary status comment
6. optional life-event comment
7. optional general remark
8. one ending
9. one salutation plus sender name

The one-time adoption branch uses `theGameState+0x25B05`: if false, it sets the
flag true and chooses one of three adoption comments.

Return-after-save comments require `CDailyEmail+0xB4`, a derived day counter
greater than `0x17`, and a random 50/50 branch. The chosen string id is one of
`0x034C..0x034F`, split by singular/plural household wording.

## Status Priority

`CDailyEmail::Show` chooses only one primary status comment. The current
priority order is:

| Priority | Trigger | String pool |
| --- | --- | --- |
| 1 | selected villager `CVillagerState::IsSick()` | `sickMessages` |
| 2 | `CVillagerManager::Population() == 1` | `lonelyMessages` |
| 3 | `FoodStore+0x78 <= 100` | `hungryMessages` |
| 4 | `CVillagerState::FoodGroupsActive(false) < 2` | `eString_EmailNeedFoodVariety` |
| 5 | money after `CMoney::UpdateInterest` is below `300.0` | `moneyMessages` |
| 6 | copied selected-villager state field at stack `-0x16854 < 0x1E` | `depressedMessages` |
| 7 | `theGameState+0x2C != 0` | `eString_EmailTrashFull` |
| 8 | collectible/trash counters at offsets `0x8AC..0x8B8` sum to more than `10` | `eString_EmailMessyHouse` |
| 9 | population is `2` and want-baby/age gates pass | `eString_EmailWantBaby` |
| 10 | fewer than `20` owned upgrades in item range `0xE1..0x1AC` | `eString_EmailWantNewStuff` |
| 11 | copied selected-villager state field at stack `-0x16858 < 0x14` | `eString_EmailSoTired` |
| fallback | none of the above | `eString_EmailLifeIsGood` |

`eString_EmailRepairHouse` exists in the string table, but no direct branch to
it has been observed in the current `CDailyEmail::Show` desktop object.

## Life Events

Daily email stores five life-event slots, each `0x24` bytes.
`FindLifeEventToReport` favors event id `2`, then id `1`, then the oldest
remaining event. Entries older than `0x8CA0` seconds are cleared.

Observed life-event ids:

| Event id | Meaning | Notes |
| --- | --- | --- |
| `1` | wedding | `weddingMessages`, `GetRandom(3)` |
| `2` | baby | `babyMessages`, with twins/triplets overrides from `theGameState+0x25AB4/0x25AB8` |
| `3` | promotion | own-promotion or partner-promotion pool depending on sender id |
| `4` | death | `deathMessages`, `GetRandom(4)` |
| `5` | not observed in daily email body | likely handled outside `CDailyEmail::Show` |
| `6` | home renovation | `homeRenovationMessages`, `GetRandom(3)` |

`theGameState::PopLifeEventPending` suppresses the immediate life-event popup
for id `6`, but still records it for daily email.

## College Kid Email

`CCollegeKidEmail::Show` uses the same header but has its own greetings,
remarks, year-away comments, endings, and salutations. It chooses the
`collegeRemarks` pool when `CVillager::YearsAwayFromHome() - 1 <= 3`, and the
`remarks2` pool for five-plus years away.

If a villager currently doing behavior `0x5D` is found, that villager name is
copied into the `name2` header slot; otherwise the header uses an empty sender
name.

## Open Questions

- Name the copied selected-villager state fields seen at stack offsets
  `-0x16854`, `-0x16858`, `-0x1683C`, and `-0x1692C` from the surrounding
  `CVillagerState` layout.
- Confirm whether `eString_EmailRepairHouse` is unused, triggered through a
  different object, or reserved for a removed/disabled branch.
