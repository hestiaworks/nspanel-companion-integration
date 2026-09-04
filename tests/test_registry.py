"""Panel credential lifecycle tests without a Home Assistant runtime."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import hashlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).parents[1] / "custom_components/nspanel_companion"

homeassistant = types.ModuleType("homeassistant")
core = types.ModuleType("homeassistant.core")
core.HomeAssistant = object
helpers = types.ModuleType("homeassistant.helpers")
device_registry = types.ModuleType("homeassistant.helpers.device_registry")
storage = types.ModuleType("homeassistant.helpers.storage")
aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
aiohttp_client.async_get_clientsession = lambda _hass: None


class FakeStore:
    def __class_getitem__(cls, _item):
        return cls


storage.Store = FakeStore
helpers.device_registry = device_registry
sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.core", core)
sys.modules.setdefault("homeassistant.helpers", helpers)
sys.modules.setdefault("homeassistant.helpers.device_registry", device_registry)
sys.modules.setdefault("homeassistant.helpers.storage", storage)
sys.modules.setdefault("homeassistant.helpers.aiohttp_client", aiohttp_client)

if "nspanel_companion.registry" not in sys.modules:
    spec = spec_from_file_location("nspanel_companion.registry", ROOT / "registry.py")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)

PanelRegistry = sys.modules["nspanel_companion.registry"].PanelRegistry


class ExampleStreamUrlTest(unittest.IsolatedAsyncioTestCase):
    """Clearing the example Media URL out of layouts already stored.

    Fixing the form stops new saves carrying it, but every panel already
    holds it, and the field is pre-filled from what is stored — so it would
    be shown, saved again, and go on standing in for the real URL. It has to
    be dropped on load, once, from the data as it is.
    """

    EXAMPLE = "rtsp://192.0.2.76:46211/0123456789abcdef"

    def registry(self, panels):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._panels = {p["panel_id"]: p for p in panels}
        registry._scrypted_bridges = {}
        registry._updater = None
        registry._settings = {}
        registry._save = AsyncMock()
        return registry

    async def test_it_is_cleared_from_the_doorbell_and_the_camera_widget(self):
        registry = self.registry([{
            "panel_id": "a", "layout": {
                "doorbell": {"stream_base_url": self.EXAMPLE, "talkback_url": "http://192.0.2.9:11081/talk/1"},
                "pages": [{"id": "p", "widgets": [
                    {"type": "camera", "stream_base_url": self.EXAMPLE},
                ]}],
            },
        }])

        changed = registry._drop_example_stream_urls()

        self.assertTrue(changed)
        layout = registry._panels["a"]["layout"]
        self.assertEqual("", layout["doorbell"]["stream_base_url"])
        self.assertEqual("", layout["pages"][0]["widgets"][0]["stream_base_url"])
        # Only that field: everything else the panel needs is untouched.
        self.assertEqual("http://192.0.2.9:11081/talk/1", layout["doorbell"]["talkback_url"])

    async def test_a_real_url_survives_and_nothing_is_saved(self):
        registry = self.registry([{
            "panel_id": "a", "layout": {"doorbell": {"stream_base_url": "rtsp://192.0.2.10:8554/door"}},
        }])

        self.assertFalse(registry._drop_example_stream_urls())
        self.assertEqual(
            "rtsp://192.0.2.10:8554/door",
            registry._panels["a"]["layout"]["doorbell"]["stream_base_url"],
        )

    async def test_a_panel_with_no_layout_is_not_a_problem(self):
        registry = self.registry([{"panel_id": "a"}, {"panel_id": "b", "layout": {}}])
        self.assertFalse(registry._drop_example_stream_urls())


class StaleFallbackTest(unittest.IsolatedAsyncioTestCase):
    """What is stored as a camera's fallback stream address.

    Scrypted's URLs are session scoped — the plugin's own note says the port
    dies with the session and that callers should ask when they need it — so
    storing one produces a fallback that is dead within minutes. The panel
    only reaches for it when the live ask fails, and then waits out a twelve
    second connect timeout to discover it cannot work. Better to have
    nothing and fail in a second, unless someone has configured a stable
    rebroadcast URL that does not expire.
    """

    def registry(self):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry.async_scrypted_doorbells = AsyncMock(return_value=[{
            "id": "44", "name": "Front door",
            "video_url": "rtsp://192.0.2.9:45541/session-that-dies",
            "talkback_url": "http://192.0.2.9:11081/talk/44",
            "talkback_key": "key-44",
        }])
        return registry

    def layout(self):
        return {"pages": [{"id": "door", "widgets": [{
            "type": "camera", "scrypted_bridge_id": "b", "scrypted_camera_id": "44",
        }]}]}

    async def test_a_minted_session_url_is_not_kept_as_a_fallback(self):
        registry = self.registry()
        hydrated = await registry._hydrate_camera_widgets(self.layout(), {})
        widget = hydrated["pages"][0]["widgets"][0]
        self.assertEqual("", widget["stream_base_url"])
        # What the panel actually resolves with, every time it opens the page.
        self.assertEqual("http://192.0.2.9:11081/talk/44", widget["talkback_url"])
        self.assertEqual("key-44", widget["talkback_key"])

    async def test_a_stable_url_someone_configured_is_kept(self):
        registry = self.registry()
        doorbell = {
            "scrypted_bridge_id": "b", "scrypted_doorbell_id": "44",
            "stream_base_url": "rtsp://192.0.2.10:8554/doorbell",
        }
        hydrated = await registry._hydrate_camera_widgets(self.layout(), doorbell)
        self.assertEqual(
            "rtsp://192.0.2.10:8554/doorbell",
            hydrated["pages"][0]["widgets"][0]["stream_base_url"],
        )


class DoorbellSourceOfTruthTest(unittest.IsolatedAsyncioTestCase):
    """Who owns the doorbell's talkback credentials.

    The admin used to publish the layout and then send a second command that
    re-fetched the device and overwrote the talkback fields — so a value
    typed into those boxes was saved and then replaced on the same save,
    silently, and every publish wrote the layout twice. One rule instead: a
    doorbell that names a Scrypted device takes its credentials from that
    device, and one that does not keeps what was typed.
    """

    DEVICE = {
        "id": "44", "name": "Front door",
        "talkback_url": "http://192.0.2.9:11081/talk/44",
        "talkback_key": "key-from-scrypted",
    }

    def registry(self):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry.async_scrypted_doorbells = AsyncMock(return_value=[self.DEVICE])
        return registry

    async def test_a_scrypted_doorbell_takes_its_credentials_from_scrypted(self):
        registry = self.registry()
        layout = {"pages": [], "doorbell": {
            "scrypted_bridge_id": "b", "scrypted_doorbell_id": "44",
            "talkback_url": "http://typed-by-hand", "talkback_key": "typed-by-hand",
        }}

        hydrated = await registry._hydrate_camera_widgets(layout, {})

        self.assertEqual("http://192.0.2.9:11081/talk/44", hydrated["doorbell"]["talkback_url"])
        self.assertEqual("key-from-scrypted", hydrated["doorbell"]["talkback_key"])

    async def test_a_manual_doorbell_keeps_what_was_typed(self):
        registry = self.registry()
        layout = {"pages": [], "doorbell": {
            "scrypted_bridge_id": "", "scrypted_doorbell_id": "",
            "talkback_url": "http://192.0.2.50:11081/talk/9", "talkback_key": "mine",
        }}

        hydrated = await registry._hydrate_camera_widgets(layout, {})

        self.assertEqual("http://192.0.2.50:11081/talk/9", hydrated["doorbell"]["talkback_url"])
        self.assertEqual("mine", hydrated["doorbell"]["talkback_key"])
        registry.async_scrypted_doorbells.assert_not_awaited()

    async def test_publishing_asks_for_no_stream_urls(self):
        # Resolving one mints a session per camera, and nothing stored here
        # uses it any more.
        registry = self.registry()
        await registry._hydrate_camera_widgets(
            {"pages": [], "doorbell": {"scrypted_bridge_id": "b", "scrypted_doorbell_id": "44"}}, {},
        )
        registry.async_scrypted_doorbells.assert_awaited_once_with("b", include_video=False)

    async def test_a_doorbell_naming_a_device_that_is_gone_is_refused(self):
        registry = self.registry()
        with self.assertRaises(ValueError):
            await registry._hydrate_camera_widgets(
                {"pages": [], "doorbell": {"scrypted_bridge_id": "b", "scrypted_doorbell_id": "99"}}, {},
            )


class PanelRegistryTest(unittest.IsolatedAsyncioTestCase):
    async def test_rename_updates_record_and_device_registry(self):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._hass = object()
        registry._panels = {"panel-abcd": {
            "panel_id": "panel-abcd", "device_id": "panel-abcd", "name": "Old name",
        }}
        registry._save = AsyncMock()
        device = Mock(id="device-1")
        fake_device_registry = Mock()
        fake_device_registry.async_get_device.return_value = device
        device_registry.async_get = Mock(return_value=fake_device_registry)

        public = await registry.async_rename("panel-abcd", "  Living   room  ")

        self.assertEqual("Living room", public["name"])
        fake_device_registry.async_update_device.assert_called_once_with("device-1", name_by_user="Living room")
        registry._save.assert_awaited_once()

    async def test_rename_rejects_empty_name(self):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._panels = {"panel-abcd": {"panel_id": "panel-abcd", "name": "Panel"}}
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            await registry.async_rename("panel-abcd", "   ")

    def test_heartbeat_sanitizes_and_hides_diagnostics_from_panel_list(self):
        registry = PanelRegistry.__new__(PanelRegistry)
        token = "valid-token"
        registry._panels = {"panel-abcd": {
            "panel_id": "panel-abcd", "device_id": "panel-abcd", "name": "Panel",
            "token_hash": hashlib.sha256(token.encode()).hexdigest(), "revoked": False,
        }}
        registry._store = Mock()
        registry._storage_data = {}

        registry.heartbeat("panel-abcd", token, {
            "diagnostics": "failed at http://host/private?token=secret Bearer abc123",
        })

        report = registry.diagnostics("panel-abcd")
        self.assertNotIn("secret", report)
        self.assertNotIn("abc123", report)
        self.assertNotIn("diagnostics", registry.list_public()[0])

    def test_panel_list_summarises_the_layout_without_shipping_it(self):
        """The panel list drives the home screen's tiles.

        The layout itself is withheld — it is large and the list shows many
        panels — but withholding it entirely left the admin UI unable to say
        whether a panel was configured at all, so every panel read as
        unconfigured however many pages it had.
        """
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._panels = {"panel-abcd": {
            "panel_id": "panel-abcd", "device_id": "panel-abcd", "name": "Panel",
            "token_hash": "x", "revoked": False,
            "layout": {"revision": 42, "pages": [{"id": "a"}, {"id": "b"}]},
        }}
        registry._store = Mock()
        registry._storage_data = {}

        record = registry.list_public()[0]

        self.assertNotIn("layout", record)
        self.assertEqual(42, record["layout_revision"])
        self.assertEqual(2, record["page_count"])

    def test_a_panel_with_no_layout_says_so_rather_than_guessing(self):
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._panels = {"panel-abcd": {
            "panel_id": "panel-abcd", "device_id": "panel-abcd", "name": "Panel",
            "token_hash": "x", "revoked": False, "layout": None,
        }}
        registry._store = Mock()
        registry._storage_data = {}

        record = registry.list_public()[0]

        self.assertIsNone(record["layout_revision"])
        self.assertEqual(0, record["page_count"])

    def test_panel_events_are_kept_newest_first_and_bounded(self):
        """The diagnostics tab answers "what happened to this panel lately".

        Bounded on purpose: this rides along with every panel list, and an
        unbounded log on a panel that flaps would grow without limit and be
        read by nobody past the first few lines.
        """
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._panels = {"panel-abcd": {
            "panel_id": "panel-abcd", "device_id": "panel-abcd", "name": "Panel",
            "token_hash": "x", "revoked": False,
        }}
        registry._store = Mock()
        registry._storage_data = {}

        for index in range(PanelRegistry.MAX_EVENTS + 5):
            registry.record_event("panel-abcd", f"event {index}")

        events = registry.list_public()[0]["events"]
        self.assertEqual(PanelRegistry.MAX_EVENTS, len(events))
        self.assertEqual(f"event {PanelRegistry.MAX_EVENTS + 4}", events[0]["message"])
        self.assertIn("at", events[0])

    def test_an_event_for_a_panel_that_is_gone_is_dropped_quietly(self):
        # Sockets close after a panel is removed; that is not an error worth
        # raising into a request that is already finishing.
        registry = PanelRegistry.__new__(PanelRegistry)
        registry._panels = {}
        registry._store = Mock()
        registry._storage_data = {}

        registry.record_event("panel-gone", "anything")

    async def test_pairing_existing_identity_preserves_layout_and_reauthorizes(self):
        registry = PanelRegistry.__new__(PanelRegistry)
        old_token = "old-token"
        layout = {"schema_version": 1, "revision": "living-room-v4", "pages": []}
        registry._panels = {
            "panel-abcd": {
                "panel_id": "panel-abcd",
                "device_id": "panel-abcd",
                "name": "Old name",
                "token_hash": hashlib.sha256(old_token.encode()).hexdigest(),
                "created_at": "2026-01-01T00:00:00+00:00",
                "last_seen": "2026-07-31T12:00:00+00:00",
                "layout": layout,
                "layout_revision": "living-room-v4",
                "revoked": True,
            }
        }
        registry._save = AsyncMock()

        public, new_token = await registry.async_pair("Living room", "PANEL-ABCD")

        self.assertNotEqual(old_token, new_token)
        self.assertTrue(registry.authenticate("panel-abcd", new_token))
        self.assertFalse(registry.authenticate("panel-abcd", old_token))
        self.assertEqual("living-room-v4", public["layout_revision"])
        self.assertIs(layout, registry._panels["panel-abcd"]["layout"])
        self.assertEqual("Living room", public["name"])
        self.assertIsNone(public["last_seen"])
        registry._save.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
