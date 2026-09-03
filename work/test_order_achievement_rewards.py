#!/usr/bin/env python3
"""The two "Order" goals are named as asked and pay 100 coins.

CAchievement::Update reads the last field of the achievementList row and pays
25 when it is zero, which is what every custom goal did before this. These two
carry an explicit 100.
"""
import unittest

import patch_mobile_furniture_pack as patcher

KIRK = 0xA8
BUBBLE = 0xA9


def _spec(achievement_id):
    for row in patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS:
        if row[0] == achievement_id:
            return row
    raise AssertionError(f"no achievement {achievement_id:#x}")


class TestOrderAchievements(unittest.TestCase):
    def test_titles_are_the_requested_possessive_form(self):
        self.assertEqual(_spec(KIRK)[2], "Kirk Strayer's Order")
        self.assertEqual(_spec(BUBBLE)[2], "Bubble Bass's Order")

    def test_both_pay_one_hundred_coins(self):
        self.assertEqual(patcher.CUSTOM_ACHIEVEMENT_COIN_REWARDS.get(KIRK), 100)
        self.assertEqual(patcher.CUSTOM_ACHIEVEMENT_COIN_REWARDS.get(BUBBLE), 100)

    def test_no_other_custom_goal_declares_a_reward(self):
        # Everything else is meant to keep the stock 25-coin default, which the
        # game applies when the field is zero.
        self.assertEqual(
            set(patcher.CUSTOM_ACHIEVEMENT_COIN_REWARDS), {KIRK, BUBBLE},
            "an unintended goal picked up a custom reward",
        )

    def test_rewards_are_positive_whole_coins(self):
        for achievement_id, reward in patcher.CUSTOM_ACHIEVEMENT_COIN_REWARDS.items():
            self.assertIsInstance(reward, int)
            self.assertGreater(
                reward, 0,
                f"{achievement_id:#x} must not declare 0: that means "
                "'use the 25-coin default', not 'pay nothing'",
            )

    def test_every_rewarded_goal_actually_exists(self):
        defined = {row[0] for row in patcher.CUSTOM_ACHIEVEMENT_ROW_SPECS}
        for achievement_id in patcher.CUSTOM_ACHIEVEMENT_COIN_REWARDS:
            self.assertIn(achievement_id, defined)


if __name__ == "__main__":
    unittest.main()
