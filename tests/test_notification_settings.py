"""One settings block for every sound the panel makes.

The doorbell and the intercom used to carry their own chime and volume.
They still do, for a release, so a panel on the previous app is not left
silent — but the block below is what is read from now on, and it is what
an old layout is migrated into wherever one is validated.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from integration_module import load  # noqa: E402

notifications = load("notifications")


class Defaults(unittest.TestCase):
    def test_a_layout_with_no_block_gets_sensible_defaults(self):
        block = notifications.normalize_notifications({}, {}, {})
        self.assertEqual("ring", block["doorbell"]["dnd"])
        self.assertEqual("silent", block["normal"]["dnd"])
        self.assertFalse(block["dnd"]["enabled"])

    def test_rings_stay_silent_until_chosen(self):
        # As they always were: an update must not make a quiet panel ring.
        block = notifications.normalize_notifications({}, {}, {})
        self.assertEqual("off", block["doorbell"]["sound"])
        self.assertEqual("off", block["intercom"]["sound"])

    def test_important_has_no_dnd_setting_at_all(self):
        # It always rings. A setting that cannot be changed should not
        # exist in the data, only in the interface that explains it.
        block = notifications.normalize_notifications({}, {}, {})
        self.assertNotIn("dnd", block["important"])


class Migration(unittest.TestCase):
    """The old fields keep working until a layout is republished."""

    def test_the_doorbell_chime_moves_across(self):
        block = notifications.normalize_notifications(
            {}, {"chime": "chime_3", "chime_volume": 40}, {})
        self.assertEqual("chime_3", block["doorbell"]["sound"])
        self.assertEqual(40, block["doorbell"]["volume"])

    def test_the_intercom_ring_moves_across(self):
        block = notifications.normalize_notifications(
            {}, {}, {"ring": "chime_2", "ring_volume": 55})
        self.assertEqual("chime_2", block["intercom"]["sound"])
        self.assertEqual(55, block["intercom"]["volume"])

    def test_an_explicit_block_wins_over_the_old_fields(self):
        block = notifications.normalize_notifications(
            {"doorbell": {"sound": "chime_1", "volume": 90}},
            {"chime": "chime_3", "chime_volume": 40}, {})
        self.assertEqual("chime_1", block["doorbell"]["sound"])
        self.assertEqual(90, block["doorbell"]["volume"])


class Validation(unittest.TestCase):
    def test_a_doorbell_sound_is_refused_for_a_notification(self):
        # The categories are different shapes of sound: one loops.
        with self.assertRaises(ValueError):
            notifications.normalize_notifications({"normal": {"sound": "chime_1"}}, {}, {})

    def test_a_notification_sound_is_refused_for_the_doorbell(self):
        with self.assertRaises(ValueError):
            notifications.normalize_notifications({"doorbell": {"sound": "notify_soft"}}, {}, {})

    def test_an_unknown_behaviour_is_refused(self):
        with self.assertRaises(ValueError):
            notifications.normalize_notifications({"doorbell": {"dnd": "maybe"}}, {}, {})

    def test_volume_must_be_a_percentage(self):
        with self.assertRaises(ValueError):
            notifications.normalize_notifications({"doorbell": {"volume": 300}}, {}, {})

    def test_a_window_may_cross_midnight(self):
        block = notifications.normalize_notifications(
            {"dnd": {"enabled": True, "from": "22:00", "to": "07:00"}}, {}, {})
        self.assertTrue(block["dnd"]["enabled"])

    def test_a_retired_sound_becomes_silence_rather_than_an_error(self):
        # Matches how RETIRED_SOUNDS is already handled in layout.py: a
        # sound that no longer ships is not a reason to refuse a layout.
        block = notifications.normalize_notifications({"doorbell": {"sound": "bell"}}, {}, {})
        self.assertEqual("off", block["doorbell"]["sound"])



class Timing(unittest.TestCase):
    """How long a banner stays, and whether an important one rings again."""

    def test_a_banner_stays_six_seconds_unless_told(self):
        # The approved design's figure, kept as the default.
        self.assertEqual(6, notifications.normalize_notifications({}, {}, {})["normal"]["duration"])

    def test_a_banner_may_stay_three_to_thirty_seconds(self):
        block = notifications.normalize_notifications({"normal": {"duration": 20}}, {}, {})
        self.assertEqual(20, block["normal"]["duration"])
        for wrong in (2, 31, "long"):
            with self.subTest(duration=wrong), self.assertRaises(ValueError):
                notifications.normalize_notifications({"normal": {"duration": wrong}}, {}, {})

    def test_an_important_one_does_not_repeat_unless_told(self):
        block = notifications.normalize_notifications({}, {}, {})
        self.assertEqual(0, block["important"]["repeat_every"])
        self.assertEqual(3, block["important"]["repeat_times"])

    def test_repeats_are_chosen_from_a_short_list(self):
        block = notifications.normalize_notifications(
            {"important": {"repeat_every": 60, "repeat_times": 0}}, {}, {})
        self.assertEqual((60, 0), (block["important"]["repeat_every"], block["important"]["repeat_times"]))
        for field, wrong in (("repeat_every", 45), ("repeat_times", 7)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                notifications.normalize_notifications({"important": {field: wrong}}, {}, {})


class NormalRepeats(unittest.TestCase):
    def test_a_regular_notification_does_not_repeat_unless_told(self):
        block = notifications.normalize_notifications({}, {}, {})
        self.assertEqual((0, 3), (block["normal"]["repeat_every"], block["normal"]["repeat_times"]))

    def test_it_takes_the_same_choices_as_an_important_one(self):
        block = notifications.normalize_notifications(
            {"normal": {"repeat_every": 300, "repeat_times": 0}}, {}, {})
        self.assertEqual((300, 0), (block["normal"]["repeat_every"], block["normal"]["repeat_times"]))
        with self.assertRaises(ValueError):
            notifications.normalize_notifications({"normal": {"repeat_every": 45}}, {}, {})

class Layout(unittest.TestCase):
    """Wherever a layout is validated, the block is there."""

    layout = load("layout")

    def test_a_validated_layout_carries_the_block(self):
        normalized = self.layout.validate_layout({
            "schema_version": 1, "revision": "n-1",
            "pages": [{"id": "home", "widgets": [{"type": "weather"}]}],
            "intercom": {"ring": "chime_2", "ring_volume": 55},
        })
        self.assertEqual("chime_2", normalized["notifications"]["intercom"]["sound"])

    def test_the_old_fields_follow_the_block_for_older_panels(self):
        # A panel on the previous app still reads intercom.ring; it must
        # hear what the block now says, not what was set before.
        normalized = self.layout.validate_layout({
            "schema_version": 1, "revision": "n-1",
            "pages": [{"id": "home", "widgets": [{"type": "weather"}]}],
            "intercom": {"ring": "chime_2", "ring_volume": 55},
            "notifications": {"intercom": {"sound": "chime_3", "volume": 20}},
        })
        self.assertEqual("chime_3", normalized["intercom"]["ring"])
        self.assertEqual(20, normalized["intercom"]["ring_volume"])


if __name__ == "__main__":
    unittest.main()
