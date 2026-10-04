"""Two things Home Assistant's log pointed at.

A panel connection that is closing must not raise out of a background send
(every restart logged one per panel), and a panel's device is found among
this integration's own devices, the way Home Assistant now requires.
"""

import asyncio
from pathlib import Path
import sys
import types
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from integration_module import load  # noqa: E402
import test_registry  # noqa: E402,F401 - installs the Home Assistant stubs

intercom = load("intercom")
registry_module = sys.modules["nspanel_companion.registry"]
COMPONENT = Path(__file__).parents[1] / "custom_components/nspanel_companion"


class Socket:
    def __init__(self, closed=False, fails=None):
        self.closed = closed
        self.fails = fails
        self.sent = []

    async def send_json(self, value):
        if self.fails:
            raise self.fails
        self.sent.append(value)


class SendQuietly(unittest.TestCase):
    def send(self, socket):
        return asyncio.run(intercom.send_quietly(socket, {"type": "intercom_roster"}))

    def test_an_open_socket_is_sent_to(self):
        socket = Socket()
        self.assertTrue(self.send(socket))
        self.assertEqual([{"type": "intercom_roster"}], socket.sent)

    def test_a_socket_closing_mid_send_is_not_an_error(self):
        # aiohttp's ClientConnectionResetError is a ConnectionResetError.
        self.assertFalse(self.send(Socket(fails=ConnectionResetError("Cannot write to closing transport"))))

    def test_a_closed_or_missing_socket_is_skipped(self):
        self.assertFalse(self.send(Socket(closed=True)))
        self.assertFalse(self.send(None))


class SocketCleanup(unittest.TestCase):
    """The panel socket uses it wherever it writes to another panel."""

    http = (COMPONENT / "http.py").read_text()

    def test_the_roster_goes_out_quietly_and_not_while_stopping(self):
        body = self.http[self.http.index("async def send_roster_to_all"):self.http.index("async def tell(")]
        self.assertIn("send_quietly(", body)
        self.assertIn("is_stopping", body)
        self.assertNotIn("await target.send_json", body)

    def test_a_stranded_call_is_ended_quietly(self):
        cleanup = self.http[self.http.index("for stranded in book.drop_panel"):]
        self.assertIn("send_quietly(", cleanup.split("return socket")[0])


class DeviceLookup(unittest.TestCase):
    def registry(self):
        registry = registry_module.PanelRegistry.__new__(registry_module.PanelRegistry)
        registry._config_entry_id = "entry-1"
        registry._hass = None
        return registry

    def test_the_new_lookup_is_scoped_to_this_entry(self):
        calls = []
        devices = types.SimpleNamespace(
            async_get_device_by_identifier=lambda identifier, entry: calls.append((identifier, entry)) or "device",
            async_get_device=lambda **_: self.fail("deprecated lookup used"),
        )
        self.assertEqual("device", self.registry()._panel_device(devices, "panel-a"))
        self.assertEqual([(("nspanel_companion", "panel-a"), "entry-1")], calls)

    def test_older_home_assistant_falls_back(self):
        # The integration supports Home Assistant from 2025.6; the new call
        # arrived after 2026.6.
        devices = types.SimpleNamespace(async_get_device=lambda identifiers: ("old", identifiers))
        self.assertEqual(
            ("old", {("nspanel_companion", "panel-a")}),
            self.registry()._panel_device(devices, "panel-a"),
        )

    def test_no_caller_uses_the_deprecated_lookup_directly(self):
        source = (COMPONENT / "registry.py").read_text()
        uses = source.count(".async_get_device(identifiers=")
        self.assertEqual(1, uses, "only the fallback inside _panel_device may call it")


if __name__ == "__main__":
    unittest.main()
