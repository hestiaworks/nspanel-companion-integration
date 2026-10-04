"""The sounds the editor previews and the sounds the panel plays.

The same files live in two repositories: here, because the preview
button is played by a browser talking to Home Assistant, and in the app,
because the panel can only play what was built into it. Nothing can force
them to hold the same bytes, so each side pins the digests — a preview that
no longer matches what the panel plays is worse than no preview, because it
is confidently wrong.

Update both repositories together when a sound changes.
"""

import hashlib
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from integration_module import load  # noqa: E402

ROOT = Path(__file__).parents[1] / "custom_components/nspanel_companion"
SOUNDS_DIR = ROOT / "frontend/sounds"

layout_module = load("layout")

SOUNDS = {
    "bell_chords.mp3": "84c57b92f09b74632f543bb26d62c07fa77695214c313ee4009f11bb1c4f2a64",
    "chime_1.mp3": "7be18fdde6abebca68cda3f3e5cdc68cd9e4eb7619f3eeefbb5c13a7f1b2a587",
    "chime_2.mp3": "b2e86ccfcb644af8c60c8ada1c159307da2a0a9972c2fed851ac9649ca049bb8",
    "chime_3.mp3": "387ebccda09ce4fd64b7bcdb910aefbc6cd6748e00fc7b05f1d923bd29bf6d4e",
    "ding_dong.mp3": "4f94da321589aca424b18c4b2254664b55b10fb996812f0902068fa151b9556b",
    "kalimba.mp3": "3c4ab2b087c02d5f82cd16c244b4267b100d766c78e3b1557f5ddedee158378b",
    "marimba.mp3": "51554cfa43d4419f96d567dddb4aed91aeb575d852006067a253072f533a10f4",
    "music_box.mp3": "ec3be2007e41144b7d8776a47e4c5de811bdd19c8bf1d19e53164fe94bc12a46",
    "notify_alert.mp3": "aad0df0862dd041186a8f9b25f02f99794d4e18ba7e5c252be8f2bc0a5245d50",
    "notify_bell_chord.mp3": "a59b224ea0c10c409967ac04270392d4d8fe84129d0785677573870a55d57902",
    "notify_bright.mp3": "53d2be026361afcb9f3b1e8c0d5e96fcf5c80967ce37b5eb103e03e9b3e80ec4",
    "notify_chime.mp3": "8b153e0843bc7f3a6f13b6795436596d17138266552edafb64f3094494d2e087",
    "notify_confirm.mp3": "a5e83a9e6cad4fc19445bdd7391f92397905b90e9e8714d4b108dee5e26bd483",
    "notify_confirm_long.mp3": "6d77a5214f6ccea3781e3bf7d25d583151473a798776e8d0f8199e310146ec40",
    "notify_double.mp3": "e0771adb9ecb665e6a2bb2fec07b8fcef868ab1efd66404e1a5dac78e536d63e",
    "notify_drop.mp3": "58f72951b2c9a70b5660723aa878cd0351cde32d1441a4a0db3195d70be5a868",
    "notify_glass.mp3": "0a2285cf9ec921a66c60689d904c62401cea5b5306744517fba7a7c3fa91bac0",
    "notify_kalimba.mp3": "6c18c7330c6b977088673d15e3e54d2a9c6e497d380b45cce72cbb87677f5399",
    "notify_kalimba_run.mp3": "4e6137721322b5274ade1815be8da50773006f46d3241405dbea83d559a122d6",
    "notify_knock.mp3": "1d50dbe2d25bebc432a697ae895c3ed1e711f437d0cef73c762467a22b30e13f",
    "notify_music_box.mp3": "e69aa50c8da0469fdd2686853d3a89118793ae4156e61b6b08df5dbb74f46d95",
    "notify_ping.mp3": "9e584910c3a387e9cc50f70866806a4a3183ce2b5632cc310160e965e65d8788",
    "notify_query.mp3": "a1929f50e4f3255af2bd662c5483e92b53c6fc37e21b84e2e1840f02582d94a8",
    "notify_rise.mp3": "d2e483a43fd5892673627ec2734a6630142c5c4091a43db27ff1863259744859",
    "notify_soft.mp3": "519c0a562197e3bb48d119835015e2a94fc3e33e621eb9ba78b71e4a43df6257",
    "notify_triple.mp3": "acb20e9e7cf27dd6b5cd2f76602eb79a7ee91c651fbffd54b1b76eab79f0c517",
    "notify_vibraphone.mp3": "c74f66e3500c897f1b5e397460cfc8f00a6de93fb2072beb01883e5a6f7a56af",
    "shop_door.mp3": "25d41acd0d318f14b414f4355697c8877c9e19797e34a552ba43bc5435dbbbe5",
    "three_tone.mp3": "3e394fffd358d9c692a084600fa4ed2528fb1cfb0078950df6211814786ffbf8",
    "tubular.mp3": "2c35398e0aff01078f9d4e96c5aa4e10c77d9860658d40cb3ce69da6f0a157c7",
    "vibraphone.mp3": "45ce323da580a0b56a227d343547321c0ce0ea54c096b6a2ad336413298eec67",
    "westminster.mp3": "56e799c0953d987e241466c897a75f798784f1abc696cde53222dcdfb3f28a3b",
}


class SoundAssetTest(unittest.TestCase):
    def test_every_sound_the_schema_allows_can_be_previewed(self):
        # "off" is the absence of a sound and has no file.
        notifications = load("notifications")
        names = notifications.DOORBELL_SOUNDS | notifications.NOTIFICATION_SOUNDS
        expected = {f"{name}.mp3" for name in names if name != "off"}
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
