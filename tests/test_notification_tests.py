"""Trying each kind of alert on a real panel from the editor."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from integration_module import load  # noqa: E402

notifications = load("notifications")


class QuietHours(unittest.TestCase):
    """The editor says when a test will be quiet, so nobody thinks it broke."""

    def block(self, enabled=True, start="22:00", end="07:00"):
        return notifications.normalize_notifications(
            {"dnd": {"enabled": enabled, "from": start, "to": end}}, {}, {})

    def test_inside_a_window_that_crosses_midnight(self):
        self.assertTrue(notifications.in_quiet_hours(self.block(), 2 * 60))

    def test_outside_it(self):
        self.assertFalse(notifications.in_quiet_hours(self.block(), 15 * 60))

    def test_a_disabled_window_is_never_quiet(self):
        self.assertFalse(notifications.in_quiet_hours(self.block(enabled=False), 2 * 60))

    def test_equal_ends_are_no_window(self):
        # The panel reads them the same way: the reading that cannot silence
        # a doorbell by accident.
        self.assertFalse(notifications.in_quiet_hours(self.block(start="09:00", end="09:00"), 9 * 60))

    def test_a_window_within_one_day(self):
        block = self.block(start="13:00", end="15:00")
        self.assertTrue(notifications.in_quiet_hours(block, 14 * 60))
        self.assertFalse(notifications.in_quiet_hours(block, 16 * 60))


class TestCallBook(unittest.TestCase):
    """A test call has nobody at the other end, so the server answers for it."""

    def setUp(self):
        self.book = notifications.TestCalls()

    def test_a_started_call_is_known(self):
        call_id = self.book.start("living-room")
        self.assertTrue(call_id.startswith("test-"))
        self.assertTrue(self.book.finish(call_id))

    def test_it_finishes_once(self):
        # The timeout and an answer can race; only one of them ends it.
        call_id = self.book.start("living-room")
        self.book.finish(call_id)
        self.assertFalse(self.book.finish(call_id))

    def test_a_real_call_is_not_a_test(self):
        self.assertFalse(self.book.finish("a1b2c3"))


class Contract(unittest.TestCase):
    ROOT = Path(__file__).parents[1] / "custom_components/nspanel_companion"

    def test_the_commands_exist_and_the_editor_calls_them(self):
        backend = (self.ROOT / "websocket.py").read_text()
        panel = (self.ROOT / "frontend/nspanel-companion-panel.js").read_text()
        for command in ("nspanel_companion/notifications/test", "nspanel_companion/notifications/play"):
            with self.subTest(command=command):
                self.assertIn(f'"{command}"', backend)
                self.assertIn(f'type: "{command}"', panel)

    def test_an_answered_test_call_is_ended_by_the_server(self):
        # Otherwise answering leaves the panel connecting to nobody.
        http = (self.ROOT / "http.py").read_text()
        self.assertIn("test_calls.finish(", http)


if __name__ == "__main__":
    unittest.main()
