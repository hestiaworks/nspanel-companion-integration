"""Tests for the shared layout contract without requiring Home Assistant."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
import unittest

PATH = Path(__file__).parents[1] / "custom_components/nspanel_companion/layout.py"
SPEC = spec_from_file_location("nspanel_layout", PATH)
layout_module = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(layout_module)


class LayoutValidationTest(unittest.TestCase):
    def test_limits_controls_and_normalizes_status_settings(self):
        widgets = [
            {"type": "entity_button", "entity_id": f"switch.room_{index}"}
            for index in range(4)
        ]
        value = layout_module.validate_layout({
            "schema_version": 1,
            "revision": "status",
            "pages": [{"id": "main", "widgets": widgets}],
            "show_clock": False,
            "show_mic_indicator": True,
            "mic_indicator_linger_seconds": 20,
        })
        self.assertFalse(value["show_clock"])
        self.assertTrue(value["show_mic_indicator"])
        self.assertEqual(20, value["mic_indicator_linger_seconds"])
        with self.assertRaises(ValueError):
            layout_module.validate_layout({
                "schema_version": 1,
                "revision": "too-many-controls",
                "pages": [{"id": "main", "widgets": widgets + [
                    {"type": "entity_button", "entity_id": "switch.room_5"},
                ]}],
            })

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

    def test_normalizes_the_screen_on_schedule(self):
        layout = {
            "schema_version": 1, "revision": "screen-hours",
            "pages": [{"id": "p", "widgets": [{"type": "weather", "entity_id": "weather.home"}]}],
            "keep_screen_on": True,
            "screen_schedule_enabled": True,
            "screen_on_from": "7:00",
            "screen_on_to": "22:30",
        }
        normalized = layout_module.validate_layout(layout)
        # Written back in the one shape the panel parses.
        self.assertTrue(normalized["screen_schedule_enabled"])
        self.assertEqual("07:00", normalized["screen_on_from"])
        self.assertEqual("22:30", normalized["screen_on_to"])

    def test_a_layout_without_a_schedule_gets_the_default_window(self):
        layout = {
            "schema_version": 1, "revision": "no-hours",
            "pages": [{"id": "p", "widgets": [{"type": "weather", "entity_id": "weather.home"}]}],
        }
        normalized = layout_module.validate_layout(layout)
        self.assertFalse(normalized["screen_schedule_enabled"])
        self.assertEqual("07:00", normalized["screen_on_from"])
        self.assertEqual("22:00", normalized["screen_on_to"])

    def test_rejects_hours_that_are_not_times(self):
        layout = {
            "schema_version": 1, "revision": "bad-hours",
            "pages": [{"id": "p", "widgets": [{"type": "weather", "entity_id": "weather.home"}]}],
            "screen_schedule_enabled": True,
            "screen_on_from": "half past seven",
            "screen_on_to": "22:00",
        }
        with self.assertRaises(ValueError):
            layout_module.validate_layout(layout)
        layout["screen_on_from"] = "25:00"
        with self.assertRaises(ValueError):
            layout_module.validate_layout(layout)

    def test_the_admins_example_media_url_is_not_a_configured_one(self):
        """The Media URL field shipped its example as the input's value.

        So every save stored a documentation address as the camera's
        fallback, and the code that fills in the real Scrypted URL — which
        only writes when the field is empty — read it as a deliberate
        choice and never ran. The address cannot answer, so a panel that
        falls back to it waits out the player's connect timeout and then
        gives up.
        """
        layout = {
            "schema_version": 1, "revision": "example-url",
            "pages": [{"id": "p", "widgets": [{"type": "weather", "entity_id": "weather.home"}]}],
            "doorbell": {"stream_base_url": layout_module.EXAMPLE_STREAM_URL},
        }
        normalized = layout_module.validate_layout(layout)
        self.assertEqual("", normalized["doorbell"]["stream_base_url"])

    def test_a_real_media_url_is_left_alone(self):
        layout = {
            "schema_version": 1, "revision": "real-url",
            "pages": [{"id": "p", "widgets": [{"type": "weather", "entity_id": "weather.home"}]}],
            "doorbell": {"stream_base_url": "rtsp://192.0.2.10:8554/doorbell"},
        }
        normalized = layout_module.validate_layout(layout)
        self.assertEqual("rtsp://192.0.2.10:8554/doorbell", normalized["doorbell"]["stream_base_url"])

    def test_a_doorbell_is_playable_from_a_url_or_from_scrypted(self):
        """What counts as a doorbell that can show a picture.

        It used to mean "has a media URL", because one was always stored.
        Now that Scrypted's expiring URL is no longer kept, a doorbell
        configured through Scrypted has no URL at all — the panel asks the
        bridge for one when it rings. Judging it by the URL alone called a
        working doorbell unconfigured and refused to test it.
        """
        scrypted = {
            "stream_base_url": "",
            "talkback_url": "http://192.0.2.9:11081/talk/44",
            "talkback_key": "key-44",
        }
        self.assertTrue(layout_module.doorbell_is_playable(scrypted))
        manual = {"stream_base_url": "rtsp://192.0.2.10:8554/door", "talkback_url": "", "talkback_key": ""}
        self.assertTrue(layout_module.doorbell_is_playable(manual))
        # Half a bridge cannot resolve anything, and neither can nothing.
        self.assertFalse(layout_module.doorbell_is_playable(
            {"stream_base_url": "", "talkback_url": "http://192.0.2.9:11081/talk/44", "talkback_key": ""},
        ))
        self.assertFalse(layout_module.doorbell_is_playable({}))

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

    def test_validates_control_presentation_options(self):
        layout = {
            "schema_version": 1,
            "revision": "control-options",
            "pages": [{"id": "controls", "widgets": [{
                "type": "entity_button",
                "entity_id": "light.ceiling",
                "icon": "washing-machine",
                "show_timer": False,
                "show_schedule": False,
                "timer_presets": [5, 15, 30, 60],
                "card_tap": True,
            }]}],
        }
        layout_module.validate_layout(layout)
        layout["pages"][0]["widgets"][0]["icon"] = "javascript"
        with self.assertRaises(ValueError):
            layout_module.validate_layout(layout)

    def test_every_icon_the_admin_offers_is_one_the_layout_accepts(self):
        """The two lists are written by hand in two languages and one file
        has no way to see the other. An icon offered in the picker but
        missing here is refused at save with "Invalid control icon", which
        names neither the icon nor the slot it came from.
        """
        panel = (Path(__file__).parents[1]
                 / "custom_components/nspanel_companion/frontend/nspanel-companion-panel.js").read_text()
        block = panel.split("const CONTROL_ICONS = [", 1)[1].split("\n];", 1)[0]
        offered = set(re.findall(r'\["([a-z0-9-]+)", "', block))
        self.assertTrue(offered, "could not read the admin icon list")
        self.assertEqual(set(), offered - layout_module.CONTROL_ICONS)

    def test_validates_gradual_cover_scripts(self):
        layout = {
            "schema_version": 1,
            "revision": "gradual-cover",
            "pages": [{"id": "controls", "widgets": [{
                "type": "entity_button",
                "entity_id": "cover.bedroom",
                "gradual_open_script": "script.gradually_open_bedroom",
                "gradual_close_script": "script.gradually_close_bedroom",
            }]}],
        }
        layout_module.validate_layout(layout)
        layout["pages"][0]["widgets"][0]["gradual_close_script"] = "switch.not_a_script"
        with self.assertRaisesRegex(ValueError, "script"):
            layout_module.validate_layout(layout)

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
                "talk_extend_enabled": True,
                "talk_extend_ms": 20000,
            },
        })
        self.assertEqual("http://192.0.2.76:1984", value["doorbell"]["stream_base_url"])
        self.assertEqual(45000, value["doorbell"]["auto_close_ms"])
        self.assertTrue(value["doorbell"]["talk_extend_enabled"])
        self.assertEqual(20000, value["doorbell"]["talk_extend_ms"])
        self.assertEqual("http://192.0.2.76:11081/talk/44", value["doorbell"]["talkback_url"])
        self.assertEqual("0123456789abcdef", value["doorbell"]["talkback_key"])
        self.assertFalse(value["doorbell"]["quiet_mode"])

    def test_rejects_unsafe_doorbell_settings(self):
        for doorbell in (
            {"stream_base_url": "file:///camera/stream"},
            {"stream_name": "../../secret"},
            {"trigger_entity_id": "not-an-entity"},
            {"auto_close_ms": 5000},
            {"talk_extend_ms": 4000},
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

    def test_accepts_native_camera_page(self):
        value = layout_module.validate_layout({
            "schema_version": 1,
            "revision": "camera-page",
            "pages": [{"id": "camera", "widgets": [{
                "type": "camera",
                "stream_base_url": "rtsp://192.0.2.76:46211/prebuffer",
                "stream_name": "doorbell_sub",
                "incoming_audio": True,
                "show_intercom": True,
            }]}],
        })
        widget = value["pages"][0]["widgets"][0]
        self.assertEqual("camera", widget["type"])
        self.assertTrue(widget["show_intercom"])

        value["pages"][0]["widgets"][0]["show_intercom"] = "yes"
        with self.assertRaises(ValueError):
            layout_module.validate_layout(value)

    def test_a_camera_page_that_predates_the_checkbox_keeps_its_intercom(self):
        """tap_action offered fullscreen, which a full-bleed page already is.

        The option that survived is the intercom, so a layout written before
        the checkbox existed carries its answer over rather than silently
        losing the talk button.
        """
        def camera(**extra):
            return layout_module.validate_layout({
                "schema_version": 1,
                "revision": "legacy",
                "pages": [{"id": "camera", "widgets": [dict({
                    "type": "camera",
                    "stream_base_url": "rtsp://192.0.2.76:46211/prebuffer",
                    "stream_name": "doorbell_sub",
                }, **extra)]}],
            })["pages"][0]["widgets"][0]

        self.assertTrue(camera(tap_action="intercom")["show_intercom"])
        self.assertFalse(camera(tap_action="fullscreen")["show_intercom"])
        self.assertFalse(camera(tap_action="none")["show_intercom"])
        self.assertFalse(camera()["show_intercom"])
        # The checkbox wins where both are present.
        self.assertTrue(camera(tap_action="none", show_intercom=True)["show_intercom"])

    def test_normalizes_and_validates_system_ui_settings(self):
        """The panel's nav bar is an enum so a fourth mode can be added later.

        `listener` is what the app has always done — re-hide the bars when
        Android brings them back. `immersive` asks the app to write Android's
        own `policy_control`, which suppresses them instead of chasing them.
        """
        value = layout_module.validate_layout({
            "schema_version": 1,
            "revision": "kiosk-ish",
            "nav_bar_mode": "immersive",
            "hide_accessibility_button": True,
            "pages": [{"id": "room", "widgets": []}],
        })
        self.assertEqual("immersive", value["nav_bar_mode"])
        self.assertTrue(value["hide_accessibility_button"])
        with self.assertRaisesRegex(ValueError, "navigation bar"):
            layout_module.validate_layout({
                "schema_version": 1,
                "revision": "bad-mode",
                "nav_bar_mode": "kiosk",
                "pages": [{"id": "room", "widgets": []}],
            })

    def test_normalizes_a_history_widget(self):
        """A history page is one entity over one span of time."""
        def page(**extra):
            return layout_module.validate_layout({
                "schema_version": 1,
                "revision": "history",
                "pages": [{"id": "h", "widgets": [dict({
                    "type": "history",
                    "entity_id": "sensor.bedroom_temp",
                }, **extra)]}],
            })["pages"][0]["widgets"][0]

        self.assertEqual("24h", page()["history_range"])
        self.assertEqual("7d", page(history_range="7d")["history_range"])
        with self.assertRaisesRegex(ValueError, "history range"):
            page(history_range="1y")

    def test_a_history_widget_needs_an_entity(self):
        # There is nothing to draw without one, and an empty page would look
        # like a fault rather than a configuration someone forgot to finish.
        with self.assertRaises(ValueError):
            layout_module.validate_layout({
                "schema_version": 1,
                "revision": "history",
                "pages": [{"id": "h", "widgets": [{"type": "history"}]}],
            })

    def test_normalizes_waking_on_approach(self):
        """The panel has a proximity sensor and it is a wake-up sensor.

        Off by default: a listener costs power on a panel that mostly does
        not care, and a screen that lights when someone walks past is not
        what everyone wants on a bedroom wall.
        """
        def panel(**extra):
            return layout_module.validate_layout({
                "schema_version": 1,
                "revision": "proximity",
                "pages": [{"id": "room", "widgets": []}],
                **extra,
            })

        self.assertFalse(panel()["wake_on_approach"])
        self.assertTrue(panel(wake_on_approach=True)["wake_on_approach"])
        with self.assertRaisesRegex(ValueError, "wake_on_approach"):
            panel(wake_on_approach="yes")

        # How close is close enough. The sensor reports reflectance rather
        # than distance, so this is a margin above the empty-wall reading.
        self.assertEqual("medium", panel()["wake_sensitivity"])
        self.assertEqual("high", panel(wake_sensitivity="high")["wake_sensitivity"])
        with self.assertRaisesRegex(ValueError, "sensitivity"):
            panel(wake_sensitivity="very")

    def test_defaults_leave_system_ui_as_it_has_always_behaved(self):
        value = layout_module.validate_layout({
            "schema_version": 1,
            "revision": "room-1",
            "pages": [{"id": "room", "widgets": []}],
        })
        self.assertEqual("listener", value["nav_bar_mode"])
        self.assertFalse(value["hide_accessibility_button"])

    def test_normalizes_intercom_configuration(self):
        """Intercom is off unless a panel is opted in.

        A panel that has not been configured for it should not appear in
        anyone's list, and should not ring.
        """
        def panel(**extra):
            return layout_module.validate_layout({
                "schema_version": 1,
                "revision": "intercom",
                "pages": [{"id": "p", "widgets": []}],
                **extra,
            })

        self.assertIs(False, panel()["intercom"]["enabled"])
        self.assertTrue(panel(intercom={"enabled": True})["intercom"]["enabled"])
        with self.assertRaisesRegex(ValueError, "Intercom"):
            panel(intercom="yes")

    def test_accepts_an_intercom_page(self):
        value = layout_module.validate_layout({
            "schema_version": 1,
            "revision": "intercom-page",
            "intercom": {"enabled": True},
            "pages": [{"id": "i", "widgets": [{"type": "intercom"}]}],
        })
        self.assertEqual("intercom", value["pages"][0]["widgets"][0]["type"])



class ThermostatModeChoiceTest(unittest.TestCase):
    """Which fan and swing modes a panel offers.

    Some units report a dozen swing positions. All of them belong to the
    entity, but a wall panel is not the place to choose between "Fixed
    upper-middle" and "Fixed middle" — and the sheet that lists them is 480
    pixels tall.
    """

    def panel(self, **widget):
        return layout_module.validate_layout({
            "schema_version": 1, "revision": "modes",
            "pages": [{"id": "p", "widgets": [
                {"type": "thermostat", "entity_id": "climate.x", **widget},
            ]}],
        })["pages"][0]["widgets"][0]

    def test_listing_nothing_offers_everything_the_entity_has(self):
        # The panel reads the entity's own modes, so an empty list is the
        # absence of an opinion rather than an instruction to show none.
        widget = self.panel()
        self.assertEqual([], widget["fan_modes"])
        self.assertEqual([], widget["swing_modes"])

    def test_it_keeps_the_chosen_modes_in_order(self):
        widget = self.panel(swing_modes=["off", "vertical"], fan_modes=["low", "high"])
        self.assertEqual(["off", "vertical"], widget["swing_modes"])
        self.assertEqual(["low", "high"], widget["fan_modes"])

    def test_it_refuses_something_that_is_not_a_list_of_names(self):
        with self.assertRaises(ValueError):
            self.panel(swing_modes="vertical")
        with self.assertRaises(ValueError):
            self.panel(fan_modes=[1, 2])

    def test_it_refuses_more_than_the_sheet_can_show(self):
        # Eight is four rows of two, which is what fits above the fold.
        with self.assertRaises(ValueError):
            self.panel(fan_modes=[f"mode_{n}" for n in range(9)])

if __name__ == "__main__":
    unittest.main()


class AudioSettingsTest(unittest.TestCase):
    """Ring sounds, and the two microphone settings that are real.

    Sound is off by default on both. A panel that has been quietly on a wall
    for weeks must not start making noise because it was updated.
    """

    def base(self, **extra):
        return {"schema_version": 1, "revision": "audio-1",
                "pages": [{"id": "m", "widgets": [{"type": "weather"}]}], **extra}

    def test_a_panel_that_was_never_configured_stays_silent(self):
        value = layout_module.validate_layout(self.base(
            doorbell={"trigger_entity_id": "binary_sensor.bell"},
            intercom={"enabled": True},
        ))
        self.assertEqual("off", value["doorbell"]["chime"])
        self.assertEqual("off", value["intercom"]["ring"])

    def test_it_keeps_the_chosen_sound_and_volume(self):
        value = layout_module.validate_layout(self.base(
            doorbell={"trigger_entity_id": "binary_sensor.bell",
                      "chime": "chime_2", "chime_volume": 40},
            intercom={"enabled": True, "ring": "chime_3", "ring_volume": 90},
        ))
        self.assertEqual(("chime_2", 40), (value["doorbell"]["chime"], value["doorbell"]["chime_volume"]))
        self.assertEqual(("chime_3", 90), (value["intercom"]["ring"], value["intercom"]["ring_volume"]))

    def test_a_sound_that_was_removed_becomes_silence_rather_than_an_error(self):
        # The first three sounds shipped were replaced. A panel still holding
        # one of those names must keep publishing: the sound is gone, so the
        # honest record is that it makes none — not a layout that cannot be
        # saved until someone finds the field.
        value = layout_module.validate_layout(self.base(
            doorbell={"trigger_entity_id": "binary_sensor.bell", "chime": "bell"},
            intercom={"enabled": True, "ring": "ping"},
        ))
        self.assertEqual("off", value["doorbell"]["chime"])
        self.assertEqual("off", value["intercom"]["ring"])

    def test_it_refuses_a_sound_the_panel_does_not_carry(self):
        with self.assertRaises(ValueError):
            layout_module.validate_layout(self.base(
                intercom={"enabled": True, "ring": "foghorn"}))

    def test_it_refuses_a_volume_off_the_scale(self):
        with self.assertRaises(ValueError):
            layout_module.validate_layout(self.base(
                intercom={"enabled": True, "ring_volume": 140}))

    def test_processing_defaults_match_what_webrtc_already_does(self):
        # Both on: these mirror libwebrtc's own defaults, so a layout written
        # before these settings existed behaves exactly as it did.
        value = layout_module.validate_layout(self.base(intercom={"enabled": True}))
        self.assertIs(True, value["intercom"]["noise_suppression"])
        self.assertIs(True, value["intercom"]["auto_gain"])

    def test_talkback_gain_is_a_percentage_within_reason(self):
        value = layout_module.validate_layout(self.base(
            doorbell={"trigger_entity_id": "binary_sensor.bell", "talkback_gain": 180}))
        self.assertEqual(180, value["doorbell"]["talkback_gain"])
        with self.assertRaises(ValueError):
            layout_module.validate_layout(self.base(
                doorbell={"trigger_entity_id": "binary_sensor.bell", "talkback_gain": 900}))
