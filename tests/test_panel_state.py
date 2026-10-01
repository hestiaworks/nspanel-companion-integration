"""What a panel says about itself, cleaned before anything trusts it.

This arrives from a panel over a websocket, so every value is checked
rather than believed. A driver that reports -999 dBm, or a lux-like number
that is actually a vendor scale, must not reach an entity.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).parents[1] / "custom_components/nspanel_companion/panel_state.py"
SPEC = spec_from_file_location("nspanel_panel_state", PATH)
panel_state = module_from_spec(SPEC)
assert SPEC and SPEC.loader
# Registered before executing: @dataclass resolves its annotations through
# sys.modules, and a module that is not there fails with an AttributeError
# that says nothing about dataclasses.
sys.modules[SPEC.name] = panel_state
SPEC.loader.exec_module(panel_state)


class CleanState(unittest.TestCase):
    def test_a_full_report_survives(self):
        state = panel_state.clean_state({
            "rssi": -47, "ambient_light": 3120, "approach": True,
            "screen_on": True, "brightness": 60, "page_id": "home",
            "app_version": "1.6.0",
        })
        self.assertEqual(-47, state.rssi)
        self.assertEqual(3120, state.ambient_light)
        self.assertTrue(state.approach)
        self.assertEqual(60, state.brightness)
        self.assertEqual("home", state.page_id)

    def test_an_empty_report_is_all_none(self):
        state = panel_state.clean_state({})
        self.assertIsNone(state.rssi)
        self.assertIsNone(state.ambient_light)
        self.assertIsNone(state.approach)

    def test_an_impossible_signal_is_refused(self):
        # Below -100 or above 0 is a driver saying it does not know.
        self.assertIsNone(panel_state.clean_state({"rssi": -999}).rssi)
        self.assertIsNone(panel_state.clean_state({"rssi": 12}).rssi)

    def test_brightness_is_a_percentage(self):
        self.assertEqual(100, panel_state.clean_state({"brightness": 400}).brightness)
        self.assertEqual(0, panel_state.clean_state({"brightness": -5}).brightness)

    def test_a_negative_light_level_is_refused(self):
        self.assertIsNone(panel_state.clean_state({"ambient_light": -1}).ambient_light)

    def test_a_boolean_is_not_a_number(self):
        # True would otherwise read as 1 and become a signal strength.
        self.assertIsNone(panel_state.clean_state({"rssi": True}).rssi)

    def test_text_is_bounded(self):
        state = panel_state.clean_state({"page_id": "x" * 500, "app_version": "y" * 500})
        self.assertLessEqual(len(state.page_id), 64)
        self.assertLessEqual(len(state.app_version), 32)

    def test_the_signal_name_is_per_panel(self):
        self.assertNotEqual(
            panel_state.signal_for("panel-a"), panel_state.signal_for("panel-b"))
        self.assertIn("panel-a", panel_state.signal_for("panel-a"))


if __name__ == "__main__":
    unittest.main()
