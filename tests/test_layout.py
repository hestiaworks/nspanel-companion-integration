"""Tests for the shared layout contract without requiring Home Assistant."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

PATH = Path(__file__).parents[1] / "custom_components/nspanel_companion/layout.py"
SPEC = spec_from_file_location("nspanel_layout", PATH)
layout_module = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(layout_module)


class LayoutValidationTest(unittest.TestCase):
    def test_normalizes_defaults(self):
        value = layout_module.validate_layout({
            "schema_version": 1,
            "revision": "room-1",
            "pages": [{"id": "room", "widgets": [{"type": "weather"}]}],
        })
        self.assertEqual("room", value["default_page_id"])
        self.assertEqual(60, value["default_page_return_seconds"])
        self.assertEqual(360, value["weather_cache_max_age_minutes"])
        self.assertFalse(value["keep_screen_on"])
        self.assertEqual("light", value["theme_mode"])
        self.assertFalse(value["theme_dark"])

    def test_validates_weather_forecast_length(self):
        layout = {
            "schema_version": 1,
            "revision": "forecast",
            "pages": [{"id": "weather", "widgets": [{"type": "weather", "forecast_days": 3}]}],
        }
        layout_module.validate_layout(layout)
        layout["pages"][0]["widgets"][0]["forecast_days"] = 4
        with self.assertRaises(ValueError):
            layout_module.validate_layout(layout)

    def test_normalizes_and_validates_panel_theme(self):
        value = layout_module.validate_layout({
            "schema_version": 1,
            "revision": "dark-room",
            "theme_mode": "inherit",
            "theme_dark": True,
            "pages": [{"id": "room", "widgets": []}],
        })
        self.assertEqual("inherit", value["theme_mode"])
        self.assertTrue(value["theme_dark"])
        with self.assertRaisesRegex(ValueError, "theme"):
            layout_module.validate_layout({
                "schema_version": 1,
                "revision": "bad-theme",
                "theme_mode": "purple",
                "pages": [{"id": "room", "widgets": []}],
            })

    def test_normalizes_keep_screen_on(self):
        value = layout_module.validate_layout({
            "schema_version": 1,
            "revision": "always-on",
            "keep_screen_on": True,
            "pages": [{"id": "room", "widgets": []}],
        })
        self.assertTrue(value["keep_screen_on"])

    def test_rejects_invalid_layout(self):
        with self.assertRaises(ValueError):
            layout_module.validate_layout({
                "schema_version": 1,
                "revision": "bad",
                "pages": [{"id": "room", "widgets": [{"type": "webview"}]}],
            })

    def test_normalizes_doorbell_settings(self):
        value = layout_module.validate_layout({
            "schema_version": 1,
            "revision": "doorbell-1",
            "pages": [{"id": "room", "widgets": [{"type": "sensor"}]}],
            "doorbell": {
                "enabled": True,
                "trigger_entity_id": "binary_sensor.front_door_visitor",
                "stream_base_url": "http://192.0.2.76:1984/",
                "stream_name": "doorbell_sub",
                "talkback_url": "http://192.0.2.76:11081/talk/44/",
                "talkback_key": "0123456789abcdef",
                "auto_close_ms": 45000,
            },
        })
        self.assertEqual("http://192.0.2.76:1984", value["doorbell"]["stream_base_url"])
        self.assertEqual(45000, value["doorbell"]["auto_close_ms"])
        self.assertEqual("http://192.0.2.76:11081/talk/44", value["doorbell"]["talkback_url"])
        self.assertEqual("0123456789abcdef", value["doorbell"]["talkback_key"])
        self.assertFalse(value["doorbell"]["quiet_mode"])

    def test_rejects_unsafe_doorbell_settings(self):
        for doorbell in (
            {"stream_base_url": "file:///camera/stream"},
            {"stream_name": "../../secret"},
            {"trigger_entity_id": "not-an-entity"},
            {"auto_close_ms": 5000},
            {"talkback_url": "rtsp://192.0.2.76/talk"},
            {"talkback_key": "too-short"},
        ):
            with self.subTest(doorbell=doorbell), self.assertRaises(ValueError):
                layout_module.validate_layout({
                    "schema_version": 1,
                    "revision": "bad-doorbell",
                    "pages": [{"id": "room", "widgets": [{"type": "sensor"}]}],
                    "doorbell": doorbell,
                })

    def test_accepts_native_rtsp_doorbell_stream(self):
        value = layout_module.validate_layout({
            "schema_version": 1,
            "revision": "rtsp-doorbell",
            "pages": [{"id": "room", "widgets": [{"type": "sensor"}]}],
            "doorbell": {"stream_base_url": "rtsp://192.0.2.76:46211/stream"},
        })
        self.assertEqual(
            "rtsp://192.0.2.76:46211/stream",
            value["doorbell"]["stream_base_url"],
        )


if __name__ == "__main__":
    unittest.main()
