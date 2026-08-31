"""Tests for what a panel is shown when intercom is off."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

PATH = Path(__file__).parents[1] / "custom_components/nspanel_companion/intercom.py"
SPEC = spec_from_file_location("nspanel_intercom", PATH)
intercom = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(intercom)


def layout(enabled, *pages):
    return {"intercom": {"enabled": enabled}, "pages": list(pages)}


PAGE_INTERCOM = {"id": "i", "widgets": [{"type": "intercom"}]}
PAGE_WEATHER = {"id": "w", "widgets": [{"type": "weather"}]}


class VisibleLayoutTest(unittest.TestCase):
    def test_an_intercom_page_is_withheld_when_intercom_is_off(self):
        visible = intercom.visible_layout(layout(False, PAGE_WEATHER, PAGE_INTERCOM))
        self.assertEqual(["w"], [page["id"] for page in visible["pages"]])

    def test_it_is_sent_when_intercom_is_on(self):
        visible = intercom.visible_layout(layout(True, PAGE_WEATHER, PAGE_INTERCOM))
        self.assertEqual(["w", "i"], [page["id"] for page in visible["pages"]])

    def test_the_stored_layout_is_not_modified(self):
        stored = layout(False, PAGE_INTERCOM)
        intercom.visible_layout(stored)
        # Withheld, not deleted: re-enabling must bring the page back without
        # anyone reconfiguring it.
        self.assertEqual(1, len(stored["pages"]))

    def test_a_page_that_only_partly_mentions_intercom_is_kept(self):
        mixed = {"id": "m", "widgets": [{"type": "weather"}, {"type": "intercom"}]}
        visible = intercom.visible_layout(layout(False, mixed))
        # Dropping a page because one widget on it is unavailable would take
        # the weather away too.
        self.assertEqual(["m"], [page["id"] for page in visible["pages"]])
        self.assertEqual(
            ["weather"], [w["type"] for w in visible["pages"][0]["widgets"]],
        )

    def test_a_layout_without_an_intercom_key_is_returned_unchanged(self):
        plain = {"pages": [PAGE_WEATHER]}
        self.assertEqual(plain, intercom.visible_layout(plain))

    def test_a_default_page_pointing_at_a_withheld_page_is_moved(self):
        stored = layout(False, PAGE_INTERCOM, PAGE_WEATHER)
        stored["default_page_id"] = "i"
        visible = intercom.visible_layout(stored)
        # Otherwise the panel opens on a page it was never sent.
        self.assertEqual("w", visible["default_page_id"])


if __name__ == "__main__":
    unittest.main()
