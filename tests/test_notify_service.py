"""Putting a notification on a panel from an automation.

Targets resolve the way every Home Assistant action's do: a device, an
area, or an entity belonging to a panel. That is the reason Part A came
first — a panel is a device with an area, so nothing here invents a
scheme of its own.
"""

from pathlib import Path
import sys
import types
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from integration_module import load  # noqa: E402 - registers the package
import test_registry  # noqa: E402,F401 - installs the Home Assistant stubs

# What this module needs beyond what test_registry provides.
sys.modules["homeassistant.core"].ServiceCall = object
entity_registry = sys.modules.setdefault(
    "homeassistant.helpers.entity_registry",
    types.ModuleType("homeassistant.helpers.entity_registry"),
)
sys.modules["homeassistant.helpers"].entity_registry = entity_registry

notify_service = load("notify_service")
vol = notify_service.vol

DOMAIN = "nspanel_companion"


def device(device_id, panel_id, area_id=None):
    return types.SimpleNamespace(
        id=device_id, area_id=area_id, identifiers={(DOMAIN, panel_id)},
    )


DEVICES = [
    device("dev-living", "living-room", "ground-floor"),
    device("dev-hall", "hall", "ground-floor"),
    device("dev-bedroom", "bedroom", "upstairs"),
    # Not ours: a lamp in the same area must not become a panel.
    types.SimpleNamespace(id="dev-lamp", area_id="ground-floor", identifiers={("hue", "x")}),
]
ENTITY_DEVICES = {"sensor.bedroom_panel_wifi_signal": "dev-bedroom"}


def resolve(target):
    return notify_service.resolve_panels(DEVICES, ENTITY_DEVICES, target)


class Targets(unittest.TestCase):
    def test_a_device_target_resolves_to_its_panel(self):
        self.assertEqual(["living-room"], resolve({"device_id": ["dev-living"]}))

    def test_an_area_target_resolves_to_every_panel_in_it(self):
        self.assertEqual({"living-room", "hall"}, set(resolve({"area_id": ["ground-floor"]})))

    def test_an_entity_target_resolves_to_its_panel(self):
        self.assertEqual(
            ["bedroom"], resolve({"entity_id": ["sensor.bedroom_panel_wifi_signal"]}))

    def test_a_target_naming_no_panel_resolves_to_nothing(self):
        self.assertEqual([], resolve({"area_id": ["garden"]}))
        self.assertEqual([], resolve({"device_id": ["dev-lamp"]}))

    def test_duplicates_are_collapsed(self):
        # A device and its area both named: one notification, not two.
        panels = resolve({"device_id": ["dev-living"], "area_id": ["ground-floor"]})
        self.assertEqual(len(panels), len(set(panels)))

    def test_a_single_string_is_accepted(self):
        # YAML lets an automation write one id without a list.
        self.assertEqual(["living-room"], resolve({"device_id": "dev-living"}))


class Payload(unittest.TestCase):
    def test_importance_defaults_to_normal(self):
        self.assertEqual("normal", notify_service.payload({"message": "hello"})["importance"])

    def test_an_unknown_importance_is_refused(self):
        with self.assertRaises(vol.Invalid):
            notify_service.payload({"message": "hello", "importance": "urgent"})

    def test_a_message_is_required(self):
        with self.assertRaises(vol.Invalid):
            notify_service.payload({"title": "no body"})

    def test_a_title_is_optional(self):
        self.assertEqual("", notify_service.payload({"message": "hello"})["title"])

    def test_a_doorbell_sound_is_refused(self):
        with self.assertRaises(vol.Invalid):
            notify_service.payload({"message": "hello", "sound": "chime_1"})

    def test_each_notification_has_its_own_id(self):
        first = notify_service.payload({"message": "a"})
        second = notify_service.payload({"message": "a"})
        self.assertNotEqual(first["id"], second["id"])


class FakeSocket:
    def __init__(self, closed=False):
        self.closed = closed
        self.sent = []

    async def send_json(self, value):
        self.sent.append(value)


class Deliver(unittest.IsolatedAsyncioTestCase):
    def hass(self, sockets):
        return types.SimpleNamespace(data={DOMAIN: {"panel_sockets": sockets}})

    async def test_an_absent_panel_is_not_an_error(self):
        # The automation did its part. A panel that was unplugged missed it,
        # like a phone that was off. Nothing is queued and nothing raises.
        delivered = await notify_service.deliver(self.hass({}), ["not-connected"], {"message": "x"})
        self.assertEqual(0, delivered)

    async def test_each_connected_panel_gets_one_message(self):
        living, hall = FakeSocket(), FakeSocket(closed=True)
        delivered = await notify_service.deliver(
            self.hass({"living-room": living, "hall": hall}),
            ["living-room", "hall"], {"message": "x"},
        )
        self.assertEqual(1, delivered)
        self.assertEqual([{"type": "notification", "data": {"message": "x"}}], living.sent)
        self.assertEqual([], hall.sent)


if __name__ == "__main__":
    unittest.main()
