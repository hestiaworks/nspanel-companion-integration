"""The integration half of the shared layout contract.

The panel parses the same fixture in DashboardLayoutFixtureTest. Testing both
sides against identical bytes is what keeps the Python validator and the Kotlin
parser from drifting apart, which co-location used to hide rather than prevent.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).parents[1]
FIXTURE = Path(__file__).parent / "fixtures/layout-fixture.json"

# Recorded so a one-sided edit fails here instead of silently diverging from the
# panel. Update it with nspanel-companion/schema/sync.sh, which rewrites both.
LAYOUT_FIXTURE_SHA256 = "136f9aa3ce9b31ff60d8d2bc25d3dae93cc414ae1c03717efba244827dbb2a6c"

spec = spec_from_file_location("layout", ROOT / "custom_components/nspanel_companion/layout.py")
layout = module_from_spec(spec)
spec.loader.exec_module(layout)

CASES = json.loads(FIXTURE.read_text())


class LayoutFixtureTest(unittest.TestCase):
    def test_fixture_matches_the_shared_copy(self):
        digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        self.assertEqual(
            LAYOUT_FIXTURE_SHA256,
            digest,
            "The layout fixture changed. Run nspanel-companion/schema/sync.sh so the "
            "panel gets the same bytes, and update this digest in both repositories.",
        )

    def test_fixture_targets_the_supported_schema(self):
        self.assertEqual(1, CASES["schema_version"])

    def test_accepts_every_valid_layout(self):
        for case in CASES["valid"]:
            with self.subTest(case["name"]):
                layout.validate_layout(case["layout"])

    def test_rejects_every_invalid_layout(self):
        for case in CASES["invalid"]:
            with self.subTest(case["name"]):
                with self.assertRaises(ValueError):
                    layout.validate_layout(case["layout"])

    def test_rejects_what_only_the_publisher_guards(self):
        """Home Assistant is the gatekeeper, so it may reject more than the panel."""
        for case in CASES["publisher_only_invalid"]:
            with self.subTest(case["name"]):
                with self.assertRaises(ValueError):
                    layout.validate_layout(case["layout"])


if __name__ == "__main__":
    unittest.main()
