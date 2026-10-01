"""Holding what a panel reports, and telling its entities."""

from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).parents[1] / "custom_components/nspanel_companion"
package = types.ModuleType("nspanel_companion")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("nspanel_companion", package)
sys.path.insert(0, str(Path(__file__).parent))

import test_registry  # noqa: E402 - installs the Home Assistant stubs

SENT = test_registry.DISPATCHED

registry_module = sys.modules["nspanel_companion.registry"]
PanelRegistry = registry_module.PanelRegistry
panel_state = sys.modules["nspanel_companion.panel_state"]


class RecordState(unittest.TestCase):
    def registry(self):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._panels = {"a": {"panel_id": "a", "name": "Living Room"}}
        registry._links = {}
        registry._states = {}
        registry._talkback = None
        registry._hass = None
        return registry

    def test_a_report_is_kept_for_that_panel(self):
        registry = self.registry()
        registry.record_state("a", {"rssi": -47, "ambient_light": 3120})
        self.assertEqual(-47, registry.panel_state("a").rssi)
        self.assertEqual(3120, registry.panel_state("a").ambient_light)

    def test_an_unknown_panel_is_ignored(self):
        registry = self.registry()
        registry.record_state("nobody", {"rssi": -47})
        self.assertEqual(panel_state.PanelState(), registry.panel_state("nobody"))

    def test_a_panel_that_has_said_nothing_has_an_empty_state(self):
        self.assertEqual(panel_state.PanelState(), self.registry().panel_state("a"))

    def test_a_later_report_replaces_an_earlier_one(self):
        registry = self.registry()
        registry.record_state("a", {"rssi": -47})
        registry.record_state("a", {"rssi": -80})
        self.assertEqual(-80, registry.panel_state("a").rssi)

    def test_entities_are_told(self):
        registry = self.registry()
        SENT.clear()
        registry.record_state("a", {"rssi": -47})
        self.assertIn(panel_state.signal_for("a"), [signal for signal, _ in SENT])


if __name__ == "__main__":
    unittest.main()
