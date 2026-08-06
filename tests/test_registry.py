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
