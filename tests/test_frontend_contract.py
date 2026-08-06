"""Static contract tests for the dependency-free Home Assistant panel."""

from pathlib import Path
import json
import unittest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "custom_components/nspanel_companion/frontend/nspanel-companion-panel.js"


class FrontendContractTest(unittest.TestCase):
    def test_frontend_uses_registered_websocket_commands(self):
        source = SCRIPT.read_text()
        for command in (
            "nspanel_companion/panels/list",
            "nspanel_companion/panels/register",
            "nspanel_companion/layout/get",
            "nspanel_companion/layout/set",
            "nspanel_companion/doorbell/test",
            "nspanel_companion/pairings/list",
            "nspanel_companion/pairings/approve",
            "nspanel_companion/panels/revoke",
            "nspanel_companion/panels/diagnostics",
            "nspanel_companion/scrypted/list",
            "nspanel_companion/scrypted/pair",
            "nspanel_companion/scrypted/unpair",
            "nspanel_companion/scrypted/doorbells",
            "nspanel_companion/scrypted/assign",
            "nspanel_companion/panels/discovery/scan",
            "nspanel_companion/panels/discovery/settings",
            "nspanel_companion/panels/discovery/connect",
        ):
            self.assertIn(command, source)
        self.assertIn("escapeHtml", source)
        self.assertIn("!dialogOpen", source)
        self.assertNotIn("Publish default", source)
        self.assertNotIn("Rotate token", source)
        self.assertNotIn("<dt>Layout</dt>", source)
        self.assertIn("<legend>Panel tools</legend>", source)
        self.assertIn('customElements.define("ha-panel-nspanel-companion-panel"', source)
        self.assertIn("customElements.define", source)

    def test_manifest_loads_frontend_dependencies(self):
        manifest = json.loads((ROOT / "custom_components/nspanel_companion/manifest.json").read_text())
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(["frontend", "http", "zeroconf"], manifest["dependencies"])

    def test_admin_websocket_commands_use_current_ha_decorator(self):
        source = (ROOT / "custom_components/nspanel_companion/websocket.py").read_text()
        self.assertEqual(18, source.count("@websocket_api.require_admin"))
        self.assertNotIn("connection.require_admin()", source)


if __name__ == "__main__":
    unittest.main()
