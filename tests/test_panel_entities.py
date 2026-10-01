"""Which entities appear, and which wait to be asked for.

The owner asked for the wifi signal and the ambient light on, and everything
else available but off. Enabling something nobody asked for is a privacy
question when one of them is a presence sensor, not a cosmetic one — so the
defaults are asserted rather than trusted to review.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components/nspanel_companion"


def block(source: str, name: str) -> str:
    match = re.search(rf"class {name}\b.*?(?=\nclass |\Z)", source, re.S)
    assert match, f"{name} not found"
    return match.group(0)


class EntityDefaults(unittest.TestCase):
    SENSOR = (COMPONENT / "sensor.py").read_text()
    BINARY = (COMPONENT / "binary_sensor.py").read_text()

    def test_wifi_and_ambient_light_are_enabled(self):
        for name in ("PanelWifiSignal", "PanelAmbientLight"):
            self.assertNotIn(
                "entity_registry_enabled_default = False", block(self.SENSOR, name),
                f"{name} would not appear without being enabled by hand",
            )

    def test_connected_and_approach_are_disabled_by_default(self):
        for name in ("PanelConnected", "PanelApproach"):
            self.assertIn(
                "_attr_entity_registry_enabled_default = False", block(self.BINARY, name),
                f"{name} would appear without anyone asking for it",
            )

    def test_ambient_light_claims_no_unit(self):
        # These panels report a vendor scale, not lux. A unit would make it
        # look comparable with real illuminance sensors.
        body = block(self.SENSOR, "PanelAmbientLight")
        self.assertNotIn("LIGHT_LUX", body)
        self.assertNotIn("ILLUMINANCE", body)
        self.assertNotIn("native_unit_of_measurement", body)

    def test_wifi_signal_is_diagnostic(self):
        self.assertIn("EntityCategory.DIAGNOSTIC", block(self.SENSOR, "PanelWifiSignal"))

    def test_the_connectivity_sensor_answers_while_the_panel_is_away(self):
        # Every other entity goes unavailable with the panel. This one must
        # not: saying the panel is gone is its entire purpose.
        self.assertIn("def available", block(self.BINARY, "PanelConnected"))

    def test_every_entity_has_a_stable_unique_id(self):
        for source in (self.SENSOR, self.BINARY):
            for name in re.findall(r"^class (Panel\w+)\(", source, re.M):
                self.assertIn(
                    "_attr_unique_id", block(source, name),
                    f"{name} without a unique_id cannot be renamed or disabled",
                )


class DeviceIdentity(unittest.TestCase):
    """Entities must land on the device the registry already created.

    A mismatched identifier makes a second, empty device beside the real one,
    and the area assigned to the first stops meaning anything.
    """

    ENTITY = (COMPONENT / "entity.py").read_text()

    def test_identifiers_match_the_registered_device(self):
        self.assertIn("identifiers={(DOMAIN, panel_id)}", self.ENTITY)

    def test_a_panel_added_later_still_gets_entities(self):
        self.assertIn("SIGNAL_PANEL_ADDED", self.ENTITY)


class Platforms(unittest.TestCase):
    INIT = (COMPONENT / "__init__.py").read_text()

    def test_every_declared_platform_has_a_module(self):
        # Forwarding to a platform with no module fails at setup, taking the
        # whole integration with it. The list and the files must agree.
        declared = re.findall(r"Platform\.([A-Z_]+)", self.INIT)
        for platform in declared:
            path = COMPONENT / f"{platform.lower()}.py"
            self.assertTrue(path.exists(), f"Platform.{platform} declared with no {path.name}")
        self.assertIn("async_forward_entry_setups", self.INIT)

    def test_platforms_are_unloaded_again(self):
        # Without this, reloading the integration leaves orphaned entities.
        self.assertIn("async_unload_platforms", self.INIT)


if __name__ == "__main__":
    unittest.main()
