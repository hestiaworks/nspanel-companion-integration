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

    def test_no_entity_is_filed_away_as_diagnostic_or_config(self):
        # Home Assistant's area page shows only uncategorised entities, and
        # the owner wants every panel entity they enable under the panel's
        # own heading there.
        for name in ("sensor.py", "binary_sensor.py", "button.py", "select.py", "switch.py", "number.py"):
            with self.subTest(module=name):
                self.assertNotIn("EntityCategory", (COMPONENT / name).read_text())

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
    SWITCH = (COMPONENT / "switch.py").read_text() if (COMPONENT / "switch.py").exists() else ""
    NUMBER = (COMPONENT / "number.py").read_text() if (COMPONENT / "number.py").exists() else ""
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
            (self.SWITCH, ["PanelScreen"]),
            (self.NUMBER, ["PanelBrightness"]),
            (self.BUTTON, ["PanelRestart", "PanelReloadLayout"]),
            (self.SELECT, ["PanelPage"]),
        ):
            for name in names:
                self.assertIn(
                    "_attr_entity_registry_enabled_default = False", block(source, name),
                    f"{name} would appear without anyone asking for it",
                )

    def test_the_screen_is_a_switch_not_a_light(self):
        # A light is pulled into the area page's Lights section and counted
        # among the room's lamps; turning the room off would blank the panel.
        self.assertFalse((COMPONENT / "light.py").exists())
        self.assertNotIn("Platform.LIGHT", (COMPONENT / "__init__.py").read_text())
        body = block(self.SWITCH, "PanelScreen")
        self.assertIn('"set_screen", on=True', body)
        self.assertIn('"set_screen", on=False', body)

    def test_brightness_is_a_percent_slider(self):
        body = block(self.NUMBER, "PanelBrightness")
        self.assertIn("_attr_native_min_value = 1", body)
        self.assertIn("_attr_native_max_value = 100", body)
        self.assertIn("NumberMode.SLIDER", body)
        self.assertIn("PERCENTAGE", body)

    def test_the_old_display_light_is_cleared_away(self):
        # Testers who enabled it would otherwise keep a dead entity.
        source = (COMPONENT / "__init__.py").read_text()
        self.assertIn("async_entries_for_config_entry", source)
        self.assertIn('entity.domain == "light"', source)

    def test_the_page_select_offers_only_pages_that_exist(self):
        body = block(self.SELECT, "PanelPage")
        self.assertIn("layout.get(\"pages\"", body)

    def test_a_page_the_layout_lost_is_not_reported_as_current(self):
        # Home Assistant logs an invalid option on every state write.
        self.assertIn("page if page in self.options else None",
                      block(self.SELECT, "PanelPage"))


class NotifyTargets(unittest.TestCase):
    """Panels as notify entities, so blueprints can pick them beside a phone.

    notify.send_message carries a title and a message only, so the entity is
    how a sender chooses importance: one entity for each.
    """

    def source(self):
        path = COMPONENT / "notify.py"
        self.assertTrue(path.exists(), "no notify platform")
        return path.read_text()

    def test_one_entity_per_importance(self):
        source = self.source()
        self.assertIn('importance="normal"', block(source, "PanelNotifications"))
        self.assertIn('importance="important"', block(source, "PanelImportantNotifications"))

    def test_they_deliver_the_way_the_action_does(self):
        # Same payload, same delivery: quiet hours, sounds and the panel's
        # list behave exactly as for nspanel_companion.notify.
        source = self.source()
        self.assertIn("from .notify_service import deliver, payload", source)
        self.assertIn("await deliver(", source)

    def test_long_text_is_cut_to_fit_rather_than_refused(self):
        source = self.source()
        self.assertIn("[:1000]", source)
        self.assertIn("[:120]", source)

    def test_they_are_on_by_default(self):
        # Nothing is sent until something sends; a blueprint should find
        # them without a trip to the device page first.
        self.assertNotIn("_attr_entity_registry_enabled_default = False", self.source())

    def test_the_platform_is_loaded(self):
        self.assertIn("Platform.NOTIFY", (COMPONENT / "__init__.py").read_text())


class Icons(unittest.TestCase):
    def test_every_entity_has_an_icon(self):
        # Without one, the light level shows Home Assistant's generic eye.
        import json
        icons = json.loads((COMPONENT / "icons.json").read_text())["entity"]
        declared = {key for platform in icons.values() for key in platform}
        keys = set()
        for path in COMPONENT.glob("*.py"):
            keys |= set(re.findall(r'_attr_translation_key = "(\w+)"', path.read_text()))
        self.assertEqual(set(), keys - declared)


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
