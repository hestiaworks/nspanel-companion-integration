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


class CallBookTest(unittest.TestCase):
    def setUp(self):
        self.book = intercom.CallBook()

    def panels(self):
        return [
            {"panel_id": "panel-a", "name": "Kitchen", "enabled": True, "connected": True},
            {"panel_id": "panel-b", "name": "Hallway", "enabled": True, "connected": True},
            {"panel_id": "panel-c", "name": "Shed", "enabled": False, "connected": True},
            {"panel_id": "panel-d", "name": "Attic", "enabled": True, "connected": False},
        ]

    def test_the_roster_lists_only_panels_that_can_be_called(self):
        roster = self.book.roster(self.panels(), viewer="panel-a")
        ids = [entry["panel_id"] for entry in roster]
        # Not itself, not a panel with intercom off, not one that is offline.
        self.assertEqual(["panel-b"], ids)
        self.assertEqual("Hallway", roster[0]["name"])
        self.assertFalse(roster[0]["busy"])

    def test_a_panel_in_a_call_is_listed_busy(self):
        self.book.open("panel-b", "panel-d")
        roster = self.book.roster(self.panels(), viewer="panel-a")
        self.assertTrue(roster[0]["busy"])

    def test_a_call_knows_who_is_at_the_other_end(self):
        call_id = self.book.open("panel-a", "panel-b")
        self.assertEqual("panel-b", self.book.partner(call_id, "panel-a"))
        self.assertEqual("panel-a", self.book.partner(call_id, "panel-b"))
        self.assertIsNone(self.book.partner(call_id, "panel-c"))
        self.assertIsNone(self.book.partner("no-such-call", "panel-a"))

    def test_closing_a_call_frees_both_ends(self):
        call_id = self.book.open("panel-a", "panel-b")
        self.assertEqual({"panel-a", "panel-b"}, set(self.book.close(call_id)))
        self.assertFalse(self.book.busy("panel-a"))
        self.assertEqual([], self.book.close(call_id))

    def test_a_panel_that_drops_ends_the_call_it_was_in(self):
        # Its socket went away: the other end must be told rather than left
        # listening to a link that will never carry anything again.
        self.book.open("panel-a", "panel-b")
        self.assertEqual(["panel-b"], self.book.drop_panel("panel-a"))
        self.assertFalse(self.book.busy("panel-b"))

    def test_the_second_of_two_simultaneous_calls_is_refused(self):
        # The design proposed "the lower id wins" to settle a race. There is
        # no race to settle: one call book serves every panel and Home
        # Assistant handles socket messages one at a time, so whichever call
        # is opened first simply wins and the other finds both ends busy.
        # A tie-break rule would be dead code dressed as caution.
        first = self.book.open("panel-b", "panel-a")
        self.assertIsNotNone(first)
        self.assertIsNone(self.book.open("panel-a", "panel-b"))

    def test_a_panel_already_in_a_call_cannot_be_rung(self):
        self.book.open("panel-a", "panel-b")
        self.assertIsNone(self.book.open("panel-c", "panel-b"))


if __name__ == "__main__":
    unittest.main()


class RosterAudienceTest(unittest.TestCase):
    """Who has to be re-told after a panel arrives or leaves.

    A roster sent only to the panel that just connected leaves everyone
    already online holding the list from before it existed — which is how
    one panel could see the other and not be seen back.
    """

    PANELS = [
        {"panel_id": "a", "enabled": True, "connected": True},
        {"panel_id": "b", "enabled": True, "connected": True},
        {"panel_id": "off", "enabled": False, "connected": True},
        {"panel_id": "away", "enabled": True, "connected": False},
    ]

    def test_everyone_online_and_opted_in_is_re_told(self):
        self.assertEqual(["a", "b"], intercom.roster_audience(self.PANELS))

    def test_a_departing_panel_is_not_told_about_its_own_departure(self):
        self.assertEqual(["a"], intercom.roster_audience(self.PANELS, departed="b"))
