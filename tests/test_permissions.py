"""Tests for layout-scoped panel permissions."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

PATH = Path(__file__).parents[1] / "custom_components/nspanel_companion/permissions.py"
SPEC = spec_from_file_location("nspanel_permissions", PATH)
module = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module)


class PanelPermissionsTest(unittest.TestCase):
    def test_resolves_explicit_and_bounded_fallback_entities(self):
        layout = {"pages": [{"widgets": [
            {"type": "thermostat"}, {"type": "weather"}, {"type": "controls"},
            {"type": "sensor", "entity_id": "sensor.room"},
        ]}]}
        available = ["climate.room", "climate.other", "weather.home", "light.one", "fan.one", "cover.one", "switch.one", "light.five", "sensor.room", "sensor.secret"]
        allowed = module.allowed_entity_ids(layout, available)
        self.assertEqual({"climate.room", "weather.home", "light.one", "fan.one", "cover.one", "switch.one", "sensor.room"}, allowed)
        self.assertNotIn("sensor.secret", allowed)

    def test_rejects_wrong_entity_domain_and_service(self):
        entities = {"light.room"}
        self.assertTrue(module.service_allowed("light.room", "light", "turn_on", entities))
        self.assertFalse(module.service_allowed("light.secret", "light", "turn_on", entities))
        self.assertFalse(module.service_allowed("light.room", "switch", "turn_on", entities))
        self.assertFalse(module.service_allowed("light.room", "light", "remove_config_entry", entities))


if __name__ == "__main__":
    unittest.main()
