"""Intercom auto-answer: three settings, validated, and kept when published."""

from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from integration_module import load  # noqa: E402

layout = load("layout")
PANEL = (Path(__file__).parents[1] / "custom_components/nspanel_companion/frontend/nspanel-companion-panel.js").read_text()


def validated(**intercom):
    return layout.validate_layout({
        "schema_version": 1, "revision": "aa-1",
        "pages": [{"id": "home", "widgets": [{"type": "weather"}]}],
        "intercom": intercom,
    })["intercom"]


class Settings(unittest.TestCase):
    def test_off_by_default(self):
        # A panel on a wall for weeks must not start opening calls on update.
        value = validated(enabled=True)
        self.assertFalse(value["auto_answer"])
        self.assertEqual(10, value["auto_answer_linger_seconds"])
        self.assertEqual(60, value["auto_answer_max_seconds"])

    def test_the_chosen_values_are_kept(self):
        value = validated(enabled=True, auto_answer=True,
                          auto_answer_linger_seconds=0, auto_answer_max_seconds=300)
        self.assertEqual((True, 0, 300), (value["auto_answer"],
                         value["auto_answer_linger_seconds"], value["auto_answer_max_seconds"]))

    def test_out_of_range_values_are_refused(self):
        for field, wrong in (("auto_answer_linger_seconds", 61),
                             ("auto_answer_linger_seconds", -1),
                             ("auto_answer_max_seconds", 45)):
            with self.subTest(field=field, value=wrong), self.assertRaises(ValueError):
                validated(enabled=True, **{field: wrong})


class Editor(unittest.TestCase):
    def test_the_intercom_tab_offers_the_three_settings(self):
        for name in ("intercom_auto_answer", "intercom_auto_answer_linger", "intercom_auto_answer_max"):
            with self.subTest(name=name):
                self.assertIn(f'name="{name}"', PANEL)
                self.assertIn(f'values.get("{name}")', PANEL)

    def test_publishing_keeps_the_whole_intercom_block(self):
        # It used to send { enabled } only, after the general save had written
        # the full block, so every other intercom setting reverted on save.
        self.assertIn("intercom: structuredClone(this.editor.layout.intercom", PANEL)
        self.assertNotIn("intercom: { enabled: Boolean(this.editor.layout.intercom?.enabled) },", PANEL)


if __name__ == "__main__":
    unittest.main()
