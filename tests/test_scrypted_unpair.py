"""Removing a Scrypted bridge that is no longer reachable."""

from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock

ROOT = Path(__file__).parents[1] / "custom_components/nspanel_companion"
package = types.ModuleType("nspanel_companion")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("nspanel_companion", package)
sys.path.insert(0, str(Path(__file__).parent))

import test_registry  # noqa: E402,F401  - installs the Home Assistant stubs

registry_module = sys.modules["nspanel_companion.registry"]
PanelRegistry = registry_module.PanelRegistry

STALE_BRIDGE = {
    "id": "bridge-1",
    "name": "NSPanel Talkback",
    "base_url": "http://172.30.232.1:11081",
    "token": "bridge-token",
}


class Unreachable:
    def post(self, *_args, **_kwargs):
        raise OSError("Connect call failed ('172.30.232.1', 11081)")


class Reachable:
    class _Response:
        status = 200

        async def json(self):
            return {"unpaired": True}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

    def post(self, *_args, **_kwargs):
        return self._Response()


def make_registry(session) -> PanelRegistry:
    registry = PanelRegistry.__new__(PanelRegistry)
    registry._hass = object()
    registry._panels = {}
    registry._scrypted_bridges = {STALE_BRIDGE["id"]: dict(STALE_BRIDGE)}
    registry._save = AsyncMock()
    registry_module.async_get_clientsession = lambda _hass: session
    return registry


class ScryptedUnpairTest(unittest.IsolatedAsyncioTestCase):
    async def test_unpairs_locally_when_scrypted_cannot_be_reached(self):
        """A bridge at a stale address is otherwise impossible to remove."""
        registry = make_registry(Unreachable())

        result = await registry.async_unpair_scrypted("bridge-1")

        self.assertTrue(result["unpaired"])
        self.assertEqual({}, registry._scrypted_bridges)
        self.assertIn("could not be reached", result["warning"].lower())

    async def test_reaching_scrypted_leaves_no_warning(self):
        registry = make_registry(Reachable())

        result = await registry.async_unpair_scrypted("bridge-1")

        self.assertTrue(result["unpaired"])
        self.assertEqual({}, registry._scrypted_bridges)
        self.assertEqual("", result.get("warning", ""))


if __name__ == "__main__":
    unittest.main()
