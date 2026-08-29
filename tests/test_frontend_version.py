"""The panel module URL is the frontend's only cache key."""

import json
import re
from pathlib import Path
import unittest

COMPONENT = Path(__file__).parents[1] / "custom_components/nspanel_companion"


class PanelModuleVersionTest(unittest.TestCase):
    def test_the_module_url_is_busted_by_the_integration_version(self):
        """A frontend change nobody can see is a frontend change that did not ship.

        Home Assistant and the browser both cache the panel module by URL, so
        editing the JavaScript without moving `?v=` leaves every existing
        install on the old file indefinitely.
        """
        version = json.loads((COMPONENT / "manifest.json").read_text())["version"]
        const = (COMPONENT / "const.py").read_text()
        url = re.search(r'PANEL_MODULE_URL = "([^"]+)"', const).group(1)
        self.assertTrue(
            url.endswith(f"?v={version}"),
            f"Panel module URL {url!r} does not carry version {version!r}",
        )


if __name__ == "__main__":
    unittest.main()
