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


class Controls(unittest.TestCase):
    """Commands reach a listening panel, or nowhere at all."""

    REGISTRY = (COMPONENT / "registry.py").read_text()
    LIGHT = (COMPONENT / "light.py").read_text()
    SELECT = (COMPONENT / "select.py").read_text()
    BUTTON = (COMPONENT / "button.py").read_text()

    def test_a_command_is_not_queued_for_an_absent_panel(self):
        # A command held for an absent panel arrives whenever it next
        # connects, which for a screen is a light coming on in an empty room.
        command = re.search(r"async def async_command.*?\n        return True",
                            self.REGISTRY, re.S).group(0)
        self.assertIn("if socket is None or socket.closed:", command)
        self.assertIn("return False", command)

    def test_every_control_is_disabled_by_default(self):
        for source, names in (
            (self.LIGHT, ["PanelDisplay"]),
            (self.BUTTON, ["PanelRestart", "PanelReloadLayout"]),
            (self.SELECT, ["PanelPage"]),
        ):
            for name in names:
                self.assertIn(
                    "_attr_entity_registry_enabled_default = False", block(source, name),
                    f"{name} would appear without anyone asking for it",
                )

    def test_brightness_is_converted_between_the_two_scales(self):
        # Home Assistant counts 0-255, the panel counts percent. Sending one
        # as the other makes 100% arrive as 39%.
        body = block(self.LIGHT, "PanelDisplay")
        self.assertIn("255 / 100", body)
        self.assertIn("100 / 255", body)

    def test_the_page_select_offers_only_pages_that_exist(self):
        body = block(self.SELECT, "PanelPage")
        self.assertIn("layout.get(\"pages\"", body)

    def test_a_page_the_layout_lost_is_not_reported_as_current(self):
        # Home Assistant logs an invalid option on every state write.
        self.assertIn("page if page in self.options else None",
                      block(self.SELECT, "PanelPage"))


class Translations(unittest.TestCase):
    def test_every_translation_key_has_a_name(self):
        import json
        names = json.loads(
            (COMPONENT / "translations/en.json").read_text())["entity"]
        keys = set()
        for path in COMPONENT.glob("*.py"):
            keys |= set(re.findall(r'_attr_translation_key = "(\w+)"', path.read_text()))
        declared = {key for platform in names.values() for key in platform}
        self.assertEqual(
            set(), keys - declared,
            "entities whose name would show as a raw translation key",
        )
