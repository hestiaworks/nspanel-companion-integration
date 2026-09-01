"""The sounds the editor previews and the sounds the panel plays.

The same three files live in two repositories: here, because the preview
button is played by a browser talking to Home Assistant, and in the app,
because the panel can only play what was built into it. Nothing can force
them to hold the same bytes, so each side pins the digests — a preview that
no longer matches what the panel plays is worse than no preview, because it
is confidently wrong.

Update both repositories together when a sound changes.
"""

import hashlib
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components/nspanel_companion"
SOUNDS_DIR = ROOT / "frontend/sounds"

SPEC = spec_from_file_location("nspanel_layout", ROOT / "layout.py")
layout_module = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(layout_module)

SOUNDS = {
    "chime_1.mp3": "bc2d599a1cab6611d9284ee4bc5a7181897aea3e25b6d2e60758c7a82b76d14e",
    "chime_2.mp3": "44a15db0bfe89657fc9a77b0e581befe2b8db973390c5220a347e362e69cc4cb",
    "chime_3.mp3": "58636839c8198c51ca89e8c3f8f205dc7f53c6eabee7a5b6aaee33fa3683b02c",
}


class SoundAssetTest(unittest.TestCase):
    def test_every_sound_the_schema_allows_can_be_previewed(self):
        # "off" is the absence of a sound and has no file.
        expected = {f"{name}.mp3" for name in layout_module.RING_SOUNDS if name != "off"}
        self.assertEqual(expected, {path.name for path in SOUNDS_DIR.glob("*.mp3")})

    def test_each_sound_is_the_file_the_panel_plays(self):
        for name, digest in SOUNDS.items():
            with self.subTest(sound=name):
                self.assertEqual(
                    digest, hashlib.sha256((SOUNDS_DIR / name).read_bytes()).hexdigest(),
                )

    def test_a_retired_sound_has_no_file_left_behind(self):
        for name in layout_module.RETIRED_SOUNDS:
            with self.subTest(sound=name):
                self.assertFalse((SOUNDS_DIR / f"{name}.mp3").exists())


if __name__ == "__main__":
    unittest.main()
