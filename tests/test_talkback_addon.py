"""Where a panel is told to send its microphone audio.

The talkback add-on carries audio to the doorbell over the camera's own
protocol, which is the difference between two to three seconds of delay and
well under one. It is optional: without it a panel keeps talking through
Scrypted, slower but working, and that fallback is the thing these tests
mostly guard.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock

# Register the package before importing the shared stubs, so this file also
# runs on its own rather than only when discovery happens to load test_pairing
# first. Same preamble as test_updater_autopair, for the same reason.
ROOT = Path(__file__).parents[1] / "custom_components/nspanel_companion"
package = types.ModuleType("nspanel_companion")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("nspanel_companion", package)
sys.path.insert(0, str(Path(__file__).parent))

import test_registry  # noqa: E402,F401  - installs the Home Assistant stubs

PanelRegistry = sys.modules["nspanel_companion.registry"].PanelRegistry

PATH = Path(__file__).parents[1] / "custom_components/nspanel_companion/layout.py"
SPEC = spec_from_file_location("nspanel_layout_talkback", PATH)
layout_module = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(layout_module)
validate_layout = layout_module.validate_layout


class TalkEndpoint(unittest.TestCase):
    def registry(self, talkback=None):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._talkback = talkback
        return registry

    def test_no_add_on_means_no_talk_endpoint(self):
        # Empty, not absent: the panel reads this as "keep using Scrypted".
        self.assertEqual(("", ""), self.registry()._talk_endpoint())

    def test_a_paired_add_on_supplies_url_and_key(self):
        registry = self.registry({
            "base_url": "http://192.0.2.5:8099", "token": "a-token-of-real-length",
        })
        url, key = registry._talk_endpoint()
        self.assertEqual("http://192.0.2.5:8099/api/talk", url)
        self.assertEqual("a-token-of-real-length", key)


class Injection(unittest.IsolatedAsyncioTestCase):
    """Nobody should copy a URL or a key by hand."""

    def registry(self, talkback=None):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._talkback = talkback
        registry.async_scrypted_doorbells = AsyncMock(return_value=[{
            "id": "44", "name": "Front door",
            "talkback_url": "http://192.0.2.9:11081/talk/44",
            "talkback_key": "scrypted-key-44",
        }])
        return registry

    def layout(self):
        return {"pages": [{"id": "door", "widgets": [{
            "type": "camera", "scrypted_bridge_id": "b", "scrypted_camera_id": "44",
        }]}]}

    async def test_camera_widgets_are_given_the_talk_endpoint(self):
        registry = self.registry({
            "base_url": "http://192.0.2.5:8099", "token": "a-token-of-real-length",
        })
        hydrated = await registry._hydrate_camera_widgets(self.layout(), {})
        widget = hydrated["pages"][0]["widgets"][0]
        self.assertEqual("http://192.0.2.5:8099/api/talk", widget["talk_url"])
        self.assertEqual("a-token-of-real-length", widget["talk_key"])

    async def test_scrypted_credentials_are_left_alone(self):
        """The add-on takes the audio. Video resolution stays with Scrypted.

        This is the whole reason talk_url exists as a separate field: the
        talkback URL is also where the panel fetches a fresh stream URL, and
        pointing it elsewhere breaks video silently.
        """
        registry = self.registry({
            "base_url": "http://192.0.2.5:8099", "token": "a-token-of-real-length",
        })
        hydrated = await registry._hydrate_camera_widgets(self.layout(), {})
        widget = hydrated["pages"][0]["widgets"][0]
        self.assertEqual("http://192.0.2.9:11081/talk/44", widget["talkback_url"])
        self.assertEqual("scrypted-key-44", widget["talkback_key"])

    async def test_without_an_add_on_the_fields_are_empty(self):
        registry = self.registry(None)
        hydrated = await registry._hydrate_camera_widgets(self.layout(), {})
        widget = hydrated["pages"][0]["widgets"][0]
        self.assertEqual("", widget["talk_url"])
        self.assertEqual("", widget["talk_key"])
        # And the Scrypted path is untouched, so talkback still works.
        self.assertEqual("http://192.0.2.9:11081/talk/44", widget["talkback_url"])


class LayoutValidation(unittest.TestCase):
    def layout(self, **doorbell):
        return {
            "schema_version": 1,
            "revision": "talkback-test",
            "pages": [{"id": "home", "title": "Home", "widgets": []}],
            "doorbell": {"trigger_entity_id": "binary_sensor.door", **doorbell},
        }

    def test_talk_fields_survive_normalisation(self):
        result = validate_layout(self.layout(
            talk_url="http://192.0.2.5:8099/api/talk",
            talk_key="a-token-of-real-length",
        ))
        self.assertEqual("http://192.0.2.5:8099/api/talk", result["doorbell"]["talk_url"])
        self.assertEqual("a-token-of-real-length", result["doorbell"]["talk_key"])

    def test_a_layout_without_them_still_normalises(self):
        # Every layout written before this feature existed.
        result = validate_layout(self.layout())
        self.assertEqual("", result["doorbell"]["talk_url"])
        self.assertEqual("", result["doorbell"]["talk_key"])

    def test_a_talk_url_must_be_http(self):
        with self.assertRaises(ValueError):
            validate_layout(self.layout(talk_url="rtsp://192.0.2.5/api/talk"))

    def test_a_short_talk_key_is_refused(self):
        # A bearer token that short is a typo, not a credential.
        with self.assertRaises(ValueError):
            validate_layout(self.layout(
                talk_url="http://192.0.2.5:8099/api/talk", talk_key="short",
            ))


if __name__ == "__main__":
    unittest.main()
