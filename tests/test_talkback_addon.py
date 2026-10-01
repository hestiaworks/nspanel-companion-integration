"""Where a panel is told to send its microphone audio.

The talkback add-on carries audio to the doorbell over the camera's own
protocol, which is the difference between two to three seconds of delay and
well under one. It is optional: without it a panel keeps talking through
Scrypted, slower but working, and that fallback is the thing these tests
mostly guard.
"""

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
import sys
sys.path.insert(0, str(Path(__file__).parent))
from integration_module import load  # noqa: E402

# _talk_endpoint asks Home Assistant where it lives, so panels are given an
# address they can actually reach. Stubbed here rather than in test_registry
# because this is the only suite that exercises it.
network = types.ModuleType("homeassistant.helpers.network")
network.get_url = lambda *_a, **_k: "http://192.0.2.76:8123"
sys.modules.setdefault("homeassistant.helpers.network", network)
sys.modules["homeassistant.helpers"].network = network

registry_module = sys.modules["nspanel_companion.registry"]
PanelRegistry = registry_module.PanelRegistry
panel_talk_base_url = registry_module.panel_talk_base_url

layout_module = load("layout")
validate_layout = layout_module.validate_layout


class TalkEndpoint(unittest.TestCase):
    def registry(self, talkback=None):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._talkback = talkback
        registry._hass = None
        return registry

    def test_no_add_on_means_no_talk_endpoint(self):
        # Empty, not absent: the panel reads this as "keep using Scrypted".
        self.assertEqual(("", ""), self.registry()._talk_endpoint())

    def test_a_paired_add_on_supplies_url_and_key(self):
        registry = self.registry({
            "base_url": "http://192.0.2.5:8099", "source": "manual",
            "token": "a-token-of-real-length",
        })
        url, key = registry._talk_endpoint()
        self.assertEqual("http://192.0.2.5:8099/api/talk", url)
        self.assertEqual("a-token-of-real-length", key)

    def test_an_autopaired_add_on_is_published_at_the_home_assistant_host(self):
        """What the panel is told, when pairing went over loopback."""
        registry = self.registry({
            "base_url": "http://127.0.0.1:8099", "source": "local",
            "token": "a-token-of-real-length",
        })
        url, _key = registry._talk_endpoint()
        self.assertEqual("http://192.0.2.76:8099/api/talk", url)


class PanelReachableUrl(unittest.TestCase):
    """A panel is a different machine from Home Assistant.

    Autopairing goes over loopback, because answering there is what proves
    the add-on is the local one. Publishing that same address to a panel
    would point it at itself — the exact trap the Scrypted plugin's README
    warns about, and silent, because the POST simply goes nowhere.
    """

    def test_a_loopback_pairing_is_rewritten_to_the_home_assistant_host(self):
        self.assertEqual(
            "http://192.0.2.76:8099",
            panel_talk_base_url("http://127.0.0.1:8099", "local", "http://192.0.2.76:8123"),
        )

    def test_the_paired_port_is_kept_not_the_home_assistant_one(self):
        self.assertEqual(
            "http://192.0.2.76:9001",
            panel_talk_base_url("http://127.0.0.1:9001", "local", "http://192.0.2.76:8123"),
        )

    def test_it_stays_http_even_behind_tls(self):
        # The add-on serves plain HTTP wherever Home Assistant sits.
        self.assertEqual(
            "http://ha.example.com:8099",
            panel_talk_base_url("http://127.0.0.1:8099", "local", "https://ha.example.com"),
        )

    def test_localhost_is_rewritten_too(self):
        self.assertEqual(
            "http://192.0.2.76:8099",
            panel_talk_base_url("http://localhost:8099", "local", "http://192.0.2.76:8123"),
        )

    def test_an_add_on_paired_by_hand_is_left_alone(self):
        # Already a real address; nobody typed 127.0.0.1 by accident.
        self.assertEqual(
            "http://192.0.2.50:8099",
            panel_talk_base_url("http://192.0.2.50:8099", "manual", "http://192.0.2.76:8123"),
        )

    def test_an_unusable_home_assistant_url_leaves_the_original(self):
        # Better the loopback address than an empty one: at least the
        # failure is visible rather than a malformed URL.
        self.assertEqual(
            "http://127.0.0.1:8099",
            panel_talk_base_url("http://127.0.0.1:8099", "local", "not-a-url"),
        )


class Injection(unittest.IsolatedAsyncioTestCase):
    """Nobody should copy a URL or a key by hand."""

    def registry(self, talkback=None):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._talkback = talkback
        registry._hass = None
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
            "base_url": "http://192.0.2.5:8099", "source": "manual",
            "token": "a-token-of-real-length",
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
            "base_url": "http://192.0.2.5:8099", "source": "manual",
            "token": "a-token-of-real-length",
        })
        hydrated = await registry._hydrate_camera_widgets(self.layout(), {})
        widget = hydrated["pages"][0]["widgets"][0]
        self.assertEqual("http://192.0.2.9:11081/talk/44", widget["talkback_url"])
        self.assertEqual("scrypted-key-44", widget["talkback_key"])

    async def test_camera_widgets_are_given_the_microphone_gain(self):
        """The gain is a panel property, so every camera page gets it.

        It reached the ring screen from the doorbell config and had no route
        to a camera page opened from the dashboard, which therefore used 100
        whatever was configured.
        """
        registry = self.registry(None)
        hydrated = await registry._hydrate_camera_widgets(
            self.layout(), {"talkback_gain": 70},
        )
        self.assertEqual(70, hydrated["pages"][0]["widgets"][0]["talkback_gain"])

    async def test_a_doorbell_without_a_gain_sends_audio_as_heard(self):
        registry = self.registry(None)
        hydrated = await registry._hydrate_camera_widgets(self.layout(), {})
        self.assertEqual(100, hydrated["pages"][0]["widgets"][0]["talkback_gain"])

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


class StalePairing(unittest.IsolatedAsyncioTestCase):
    """An add-on reinstalled elsewhere forgets us, and says nothing.

    It keeps its own copy of the token in /data. Reinstalling it — from a
    local folder to the repository, say — issues a new identity. Home
    Assistant goes on believing it is paired, panels go on presenting a
    credential nothing recognises, and talkback fails with a 401 that
    surfaces nowhere.
    """

    def registry(self, talkback, info):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._talkback = talkback
        registry._links = {}
        registry._states = {}
        registry._hass = None

        class Response:
            status = 200
            async def json(self_inner):
                return info
            async def __aenter__(self_inner):
                return self_inner
            async def __aexit__(self_inner, *_exc):
                return False

        class Session:
            def get(self_inner, *_a, **_k):
                return Response()

        import sys
        sys.modules["nspanel_companion.registry"].async_get_clientsession = lambda _h: Session()
        return registry

    PAIRED = {"id": "abc123", "base_url": "http://127.0.0.1:8099", "token": "t" * 32}

    async def test_a_matching_identity_is_left_alone(self):
        registry = self.registry(self.PAIRED, {"id": "abc123", "paired": True})
        self.assertTrue(await registry.async_talkback_is_live())

    async def test_a_new_identity_is_a_stale_pairing(self):
        # Reinstalled: same address, different add-on.
        registry = self.registry(self.PAIRED, {"id": "different", "paired": True})
        self.assertFalse(await registry.async_talkback_is_live())

    async def test_an_add_on_that_forgot_us_is_a_stale_pairing(self):
        registry = self.registry(self.PAIRED, {"id": "abc123", "paired": False})
        self.assertFalse(await registry.async_talkback_is_live())

    async def test_nothing_paired_is_not_live(self):
        registry = self.registry(None, {})
        self.assertFalse(await registry.async_talkback_is_live())


class PublishRepairsAStalePairing(unittest.IsolatedAsyncioTestCase):
    """Saving a layout is what a person tries when talkback stops.

    Leaving the re-pair to the admin page meant a stale pairing survived for
    as long as nobody loaded that page with a fresh browser cache — and the
    panel went on being handed a token the add-on had never seen.
    """

    async def test_a_live_pairing_is_not_disturbed(self):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._talkback = {"id": "abc", "base_url": "http://127.0.0.1:8099", "token": "t" * 32}
        calls = []
        async def live():
            calls.append("checked")
            return True
        async def autopair():
            calls.append("re-paired")
            return {}
        registry.async_talkback_is_live = live
        registry.async_autopair_talkback = autopair
        await registry.async_ensure_talkback()
        self.assertEqual(["checked"], calls)

    async def test_a_dead_pairing_is_renewed(self):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._talkback = {"id": "abc", "base_url": "http://127.0.0.1:8099", "token": "t" * 32}
        calls = []
        async def live():
            calls.append("checked")
            return False
        async def autopair():
            calls.append("re-paired")
            return {}
        registry.async_talkback_is_live = live
        registry.async_autopair_talkback = autopair
        await registry.async_ensure_talkback()
        self.assertEqual(["checked", "re-paired"], calls)

    async def test_nothing_paired_needs_no_check(self):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._talkback = None
        await registry.async_ensure_talkback()   # must not raise


class BothRingsCarryTheCredentials(unittest.TestCase):
    """A ring means the same thing however it was triggered.

    There were two paths. A ring from the doorbell's trigger entity carried
    the talkback credentials; a ring fired as an nspanel_doorbell event
    passed its own data straight through without them. The panel then had no
    add-on endpoint for that ring and used the slower path — on the same
    doorbell, from the same panel, for no reason visible to anyone.
    """

    SOURCE = (Path(__file__).parents[1]
              / "custom_components/nspanel_companion/http.py").read_text()

    def test_the_payload_is_built_in_one_place(self):
        self.assertEqual(1, self.SOURCE.count("def doorbell_payload"))

    def test_the_event_path_no_longer_forwards_raw_event_data(self):
        self.assertNotIn('"data": dict(event.data)', self.SOURCE,
                         "the event path bypasses the payload builder again")

    def test_both_paths_use_the_builder(self):
        # Once for the definition, twice for the two ways a ring arrives.
        self.assertGreaterEqual(self.SOURCE.count("doorbell_payload("), 3)

    def test_the_builder_carries_the_talk_endpoint(self):
        start = self.SOURCE.index("def doorbell_payload")
        body = self.SOURCE[start:start + 2000]
        for key in ("talk_url", "talk_key", "talkback_url", "talkback_key"):
            self.assertIn(key, body, f"a ring would arrive without {key}")

    def test_the_event_may_still_override_what_it_knows(self):
        # Quiet mode, a chime, a different stream: the caller's to decide.
        self.assertIn("payload.update(", self.SOURCE)
