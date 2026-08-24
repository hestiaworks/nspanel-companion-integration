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
            "nspanel_companion/panels/rename",
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
            "nspanel_companion/updater/status",
            "nspanel_companion/updater/pair",
            "nspanel_companion/updater/autopair",
            "nspanel_companion/updater/unpair",
            "nspanel_companion/updater/discover",
            "nspanel_companion/updater/update",
        ):
            self.assertIn(command, source)
        self.assertIn("escapeHtml", source)
        self.assertIn("!dialogOpen", source)
        self.assertNotIn("Publish default", source)
        self.assertNotIn("Rotate token", source)
        self.assertNotIn("<dt>Layout</dt>", source)
        self.assertIn('["general","General"]', source)
        self.assertIn('data-workspace-panel="diagnostics"', source)
        self.assertIn("workspaceRoute", source)
        self.assertIn("No pages configured", source)
        self.assertIn("hasPublishedLayout: Boolean(layout)", source)
        self.assertIn("draftPages", source)
        self.assertIn("addDraftPage", source)
        self.assertIn('data-page-action="duplicate"', source)
        self.assertIn('data-page-drag=', source)
        self.assertNotIn('name="default_page"', source)
        self.assertIn('name="theme_mode"', source)
        self.assertIn('customElements.define("ha-panel-nspanel-companion-panel"', source)
        self.assertIn("customElements.define", source)
        self.assertIn('["nspanel-companion", "probable-nspanel"].includes(device.classification)', source)

    def test_manifest_loads_frontend_dependencies(self):
        manifest = json.loads((ROOT / "custom_components/nspanel_companion/manifest.json").read_text())
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(["frontend", "http", "zeroconf"], manifest["dependencies"])

    def test_manifest_carries_the_keys_hassfest_requires(self):
        """hassfest rejects a manifest without these, and HACS surfaces both links."""
        manifest = json.loads((ROOT / "custom_components/nspanel_companion/manifest.json").read_text())
        repository = "https://github.com/hestiaworks/nspanel-companion-integration"
        self.assertEqual(repository, manifest["documentation"])
        self.assertEqual(f"{repository}/issues", manifest["issue_tracker"])
        self.assertIn("requirements", manifest)

    def test_manifest_keys_are_ordered_the_way_hassfest_demands(self):
        """domain and name first, everything else alphabetical.

        hassfest fails the build on this, so catching it here turns a CI round
        trip into an immediate local failure.
        """
        keys = list(json.loads((ROOT / "custom_components/nspanel_companion/manifest.json").read_text()))
        self.assertEqual(["domain", "name"], keys[:2])
        self.assertEqual(sorted(keys[2:]), keys[2:])

    def test_admin_websocket_commands_use_current_ha_decorator(self):
        source = (ROOT / "custom_components/nspanel_companion/websocket.py").read_text()
        self.assertEqual(25, source.count("@websocket_api.require_admin"))
        self.assertNotIn("connection.require_admin()", source)
        self.assertIn('{"nspanel-companion", "probable-nspanel"}', source)
        self.assertIn('device.get("adb_state") == "device"', source)

    def test_panel_sync_includes_human_readable_name(self):
        source = (ROOT / "custom_components/nspanel_companion/http.py").read_text()
        self.assertIn('"panel_name": record.get("name")', source)

    def test_panel_asset_version_matches_the_manifest(self):
        """A stale query string serves the cached panel after a HACS update.

        HACS offers the update from the manifest version, so if the asset URL
        does not move with it the browser keeps the old panel and the upgrade
        looks like it silently did nothing.
        """
        manifest = json.loads((ROOT / "custom_components/nspanel_companion/manifest.json").read_text())
        const_source = (ROOT / "custom_components/nspanel_companion/const.py").read_text()
        self.assertIn(f"?v={manifest['version']}\"", const_source)


if __name__ == "__main__":
    unittest.main()
