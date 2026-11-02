"""Run: python -m unittest scripts.test_queue_member_pick"""

import unittest

from core.queue_member_pick import QueueMemberPickError, pick_queue_member_choice

LOUD, MICK, OTHER = "111111111111111111", "222222222222222222", "333333333333333333"
QUEUE = [
    {"user_id": LOUD, "display_name": "ALittleLoud"},
    {"user_id": MICK, "display_name": "mick"},
    {"user_id": OTHER, "display_name": "Max"},
]


def pick(choices, uid, name=""):
    return pick_queue_member_choice(choices, uid, name, QUEUE)["value"]


class PickTests(unittest.TestCase):
    def test_mutual_with_display_labels(self):
        choices = [
            {"name": "3: mick -- with @ALittleLoud", "value": "u-mick"},
            {"name": "2: ALittleLoud -- with mick together", "value": "u-loud"},
        ]
        self.assertEqual(pick(choices, LOUD, "ALittleLoud"), "u-loud")
        self.assertEqual(pick(choices, MICK, "mick"), "u-mick")

    def test_mention_labels(self):
        choices = [
            {"name": f"3: <@{MICK}> -- with <@{LOUD}>", "value": "u-mick"},
            {"name": f"2: <@{LOUD}> -- with <@{MICK}> together", "value": "u-loud"},
        ]
        self.assertEqual(pick(choices, LOUD), "u-loud")
        self.assertEqual(pick(choices, MICK), "u-mick")

    def test_unknown_own_name_falls_back_to_leftover(self):
        # Bot shows a different name than the API: partner line is still excluded.
        choices = [
            {"name": "3: mick -- with @Loud", "value": "u-mick"},
            {"name": "2: Loudy -- with mick", "value": "u-loud"},
        ]
        self.assertEqual(pick(choices, LOUD, "ALittleLoud"), "u-loud")

    def test_refuses_when_ambiguous(self):
        choices = [
            {"name": "3: Foo -- with @Bar", "value": "a"},
            {"name": "2: Bar -- with Foo", "value": "b"},
        ]
        with self.assertRaises(QueueMemberPickError):
            pick(choices, LOUD, "ALittleLoud")

    def test_refuses_partner_only(self):
        with self.assertRaises(QueueMemberPickError):
            pick([{"name": "3: mick -- with @ALittleLoud", "value": "u-mick"}], LOUD)

    def test_single_line(self):
        self.assertEqual(pick([{"name": "1: Max -- Anything", "value": "x"}], OTHER), "x")

    def test_prefix_names(self):
        queue = QUEUE + [{"user_id": "444444444444444444", "display_name": "Max2"}]
        choices = [
            {"name": "1: Max -- with Max2", "value": "max"},
            {"name": "2: Max2 -- with Max", "value": "max2"},
        ]
        self.assertEqual(
            pick_queue_member_choice(choices, OTHER, "Max", queue)["value"], "max"
        )
        self.assertEqual(
            pick_queue_member_choice(choices, "444444444444444444", "Max2", queue)["value"],
            "max2",
        )


if __name__ == "__main__":
    unittest.main()
