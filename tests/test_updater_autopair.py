"""Pairing the updater without a human copying a code out of the add-on log."""

from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock

# Register the package before importing the shared stubs, so this file also runs
# on its own rather than only when discovery happens to load test_pairing first.
ROOT = Path(__file__).parents[1] / "custom_components/nspanel_companion"
package = types.ModuleType("nspanel_companion")
package.__path__ = [str(ROOT)]
sys.modules.setdefault("nspanel_companion", package)
sys.path.insert(0, str(Path(__file__).parent))

import test_registry  # noqa: E402,F401  - installs the Home Assistant stubs

registry_module = sys.modules["nspanel_companion.registry"]
PanelRegistry = registry_module.PanelRegistry


class FakeResponse:
    def __init__(self, status: int, payload: dict) -> None:
        self.status = status
        self._payload = payload

    async def json(self) -> dict:
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False


class FakeSession:
    """Answers the two calls pairing makes, and records what was asked for."""

    def __init__(self, get_responses: dict, post_response: FakeResponse) -> None:
        self._get_responses = get_responses
        self._post_response = post_response
        self.gets: list[str] = []
        self.posts: list[tuple[str, dict]] = []

    def get(self, url: str, **_kwargs):
        self.gets.append(url)
        if url not in self._get_responses:
            raise OSError("Connection refused")
        return self._get_responses[url]

    def post(self, url: str, json: dict, **_kwargs):
        self.posts.append((url, json))
        return self._post_response


def make_registry(session: FakeSession) -> PanelRegistry:
    registry = PanelRegistry.__new__(PanelRegistry)
    registry._hass = object()
    registry._updater = None
    registry._save = AsyncMock()
    registry_module.async_get_clientsession = lambda _hass: session
    return registry


class UpdaterAutopairTest(unittest.IsolatedAsyncioTestCase):
    async def test_pairs_using_the_code_read_from_the_local_host(self):
        session = FakeSession(
            {"http://127.0.0.1:8098/api/pair-code": FakeResponse(200, {
                "id": "updater-1", "name": "NSPanel Companion Updater", "code": "123456",
            })},
            FakeResponse(200, {"id": "updater-1", "name": "Updater", "token": "tok"}),
        )
        registry = make_registry(session)

        public = await registry.async_autopair_updater()

        self.assertEqual("updater-1", public["id"])
        self.assertEqual(
            [("http://127.0.0.1:8098/api/pair", {"code": "123456"})], session.posts
        )
        self.assertNotIn("token", public)
        self.assertEqual("local", public["source"])

    async def test_manual_pairing_is_recorded_as_manual(self):
        """The UI offers unpair only for updaters it cannot re-pair by itself."""
        session = FakeSession(
            {}, FakeResponse(200, {"id": "updater-9", "name": "Updater", "token": "tok"})
        )
        registry = make_registry(session)

        public = await registry.async_pair_updater("http://192.0.2.10:8098", "654321")

        self.assertEqual("manual", public["source"])

    async def test_reports_clearly_when_the_add_on_is_not_on_this_host(self):
        session = FakeSession({}, FakeResponse(200, {}))
        registry = make_registry(session)

        with self.assertRaises(ValueError) as caught:
            await registry.async_autopair_updater()

        self.assertIn("could not be reached", str(caught.exception).lower())
        self.assertEqual([], session.posts)


if __name__ == "__main__":
    unittest.main()
