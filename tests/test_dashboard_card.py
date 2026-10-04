"""The panel's dashboard card.

The card's decisions — which entity is which, what a wifi reading is called,
which history points count — are pure functions exported from the module,
and are run here under Node against the real file. The element itself is
checked by the preview harness, where a browser is.
"""

import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).parents[1] / "custom_components/nspanel_companion"
CARD = ROOT / "frontend/nspanel-companion-card.js"
NODE = shutil.which("node")


def run(expression: str):
    """Evaluate one expression against the module; return its JSON value."""
    script = (
        f"const card = await import({json.dumps(CARD.as_uri())});\n"
        f"process.stdout.write(JSON.stringify({expression}));"
    )
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


@unittest.skipUnless(NODE, "node is not installed")
class WifiBand(unittest.TestCase):
    def test_the_bands_are_the_admin_lists(self):
        self.assertEqual(
            ["Strong", "Good", "Weak", "Poor"],
            run("[-48, -60, -70, -80].map((d) => card.wifiBand(d).word)"),
        )

    def test_the_edges_belong_to_the_better_band(self):
        self.assertEqual(
            ["Strong", "Good", "Weak"],
            run("[-55, -67, -73].map((d) => card.wifiBand(d).word)"),
        )

    def test_no_reading_has_no_word(self):
        self.assertIsNone(run("card.wifiBand(Number.NaN)"))


ENTITIES = {
    "sensor.lr_wifi": {"entity_id": "sensor.lr_wifi", "device_id": "dev-lr",
                       "platform": "nspanel_companion", "translation_key": "wifi_signal"},
    "light.lr_display": {"entity_id": "light.lr_display", "device_id": "dev-lr",
                         "platform": "nspanel_companion", "translation_key": "display"},
    "sensor.office_wifi": {"entity_id": "sensor.office_wifi", "device_id": "dev-office",
                           "platform": "nspanel_companion", "translation_key": "wifi_signal"},
    "light.lamp": {"entity_id": "light.lamp", "device_id": "dev-lr",
                   "platform": "hue", "translation_key": "display"},
}


@unittest.skipUnless(NODE, "node is not installed")
class PanelEntities(unittest.TestCase):
    def roles(self, device):
        return run(f"card.panelEntities({json.dumps(ENTITIES)}, {json.dumps(device)})")

    def test_by_role_not_by_name(self):
        # The owner may rename an entity; its translation key does not move.
        self.assertEqual(
            {"wifi_signal": "sensor.lr_wifi", "display": "light.lr_display"},
            self.roles("dev-lr"),
        )

    def test_another_integrations_entity_on_the_same_device_is_ignored(self):
        self.assertNotIn("light.lamp", self.roles("dev-lr").values())

    def test_an_unknown_device_has_no_entities(self):
        # The card then says the panel was not found instead of throwing.
        self.assertEqual({}, self.roles("dev-gone"))


@unittest.skipUnless(NODE, "node is not installed")
class History(unittest.TestCase):
    def test_compressed_rows_become_points(self):
        rows = [{"s": "-50", "lu": 1000}, {"s": "-52", "lu": 1060}]
        self.assertEqual(
            [{"t": 1000000, "v": -50}, {"t": 1060000, "v": -52}],
            run(f"card.historyPoints({json.dumps(rows)})"),
        )

    def test_unavailable_and_empty_states_are_skipped_not_zero(self):
        rows = [{"s": "-50", "lu": 1000}, {"s": "unavailable", "lu": 1030},
                {"s": "", "lu": 1040}, {"s": "unknown", "lu": 1050}, {"s": "-52", "lu": 1060}]
        self.assertEqual([-50, -52], run(f"card.historyPoints({json.dumps(rows)}).map((p) => p.v)"))

    def test_extremes_carry_their_times(self):
        points = [{"t": 1, "v": 5}, {"t": 2, "v": 9}, {"t": 3, "v": 1}]
        self.assertEqual(
            {"min": {"t": 3, "v": 1}, "max": {"t": 2, "v": 9}},
            run(f"card.extremes({json.dumps(points)})"),
        )

    def test_no_points_no_extremes(self):
        self.assertIsNone(run("card.extremes([])"))


@unittest.skipUnless(NODE, "node is not installed")
class Sparkline(unittest.TestCase):
    def test_a_flat_reading_is_a_line_through_the_middle(self):
        # A dark room reads the same all day; no division by zero.
        path = run("card.sparkPath([{t: 0, v: 7}, {t: 10, v: 7}], 100, 40)")
        self.assertEqual("M0.0 20.0 L100.0 20.0", path)

    def test_low_values_sit_low(self):
        path = run("card.sparkPath([{t: 0, v: 0}, {t: 10, v: 10}], 100, 40)")
        self.assertEqual("M0.0 38.0 L100.0 2.0", path)

    def test_fewer_than_two_points_draw_nothing(self):
        self.assertEqual("", run("card.sparkPath([{t: 0, v: 1}], 100, 40)"))


@unittest.skipUnless(NODE, "node is not installed")
class Ago(unittest.TestCase):
    def test_wording(self):
        self.assertEqual(
            ["just now", "12 min ago", "3 h ago"],
            run("[30e3, 12 * 60e3, 3 * 3600e3].map((d) => card.agoText(1e9 - d, 1e9))"),
        )


class Registration(unittest.TestCase):
    def test_the_module_is_loaded_for_every_user(self):
        const = (ROOT / "const.py").read_text()
        frontend = (ROOT / "frontend.py").read_text()
        self.assertIn('CARD_MODULE_URL = "/nspanel_companion/frontend/nspanel-companion-card.js?v=', const)
        self.assertIn("add_extra_js_url(hass, CARD_MODULE_URL)", frontend)

    def test_the_roles_it_reads_are_the_integrations_translation_keys(self):
        keys = {key for platform in json.loads((ROOT / "translations/en.json").read_text())["entity"].values()
                for key in platform}
        roles = set(run("card.ROLES")) if NODE else set()
        if roles:
            self.assertEqual(set(), roles - keys)


class CardContract(unittest.TestCase):
    """What the element must do that only a browser could show, pinned in source."""

    source = CARD.read_text() if CARD.exists() else ""

    def test_it_defines_the_element_once(self):
        self.assertIn('customElements.define("nspanel-companion-card"', self.source)
        self.assertIn('customElements.get("nspanel-companion-card")', self.source)

    def test_it_calls_only_the_services_the_entities_offer(self):
        for call in ('"light", "turn_on"', '"light", "turn_off"',
                     '"select", "select_option"', '"button", "press"'):
            with self.subTest(call=call):
                self.assertIn(call, self.source)

    def test_restart_confirms_inside_the_card(self):
        self.assertIn("Tap again to restart", self.source)
        self.assertNotIn("confirm(", self.source)

    def test_brightness_is_sent_on_release_not_while_dragging(self):
        self.assertIn('addEventListener("change"', self.source)
        self.assertIn('this._hold("drag")', self.source)

    def test_an_unknown_panel_is_said_not_thrown(self):
        self.assertIn("This panel was not found", self.source)

    def test_colours_come_from_the_theme(self):
        import re
        body = self.source.split("const STYLE = `", 1)[1].split("`;", 1)[0]
        literals = re.findall(r"#[0-9a-fA-F]{3,8}\b", body)
        self.assertEqual([], literals, "colours must come from Home Assistant's theme variables")
    def test_it_is_offered_in_the_card_picker(self):
        self.assertIn("window.customCards", self.source)
        self.assertIn('type: "nspanel-companion-card"', self.source)
        self.assertIn('name: "NSPanel Companion"', self.source)

    def test_the_editor_picks_a_device_of_this_integration(self):
        self.assertIn('customElements.define("nspanel-companion-card-editor"', self.source)
        self.assertIn('device: { integration: "nspanel_companion" }', self.source)
        self.assertIn('"config-changed"', self.source)

@unittest.skipUnless(NODE, "node is not installed")
class RealHistory(unittest.TestCase):
    """What Home Assistant actually sends: only changes, never a closing row."""

    def test_a_reading_that_never_moved_is_a_flat_line_across_the_day(self):
        # One row: the state at the start of the window, unchanged since.
        path = run(
            "card.sparkPath(card.anchored([{t: 0, v: 7}], 7, 100), 100, 40, 0, 100)")
        self.assertEqual("M0.0 20.0 L100.0 20.0", path)

    def test_the_line_runs_to_now_not_to_the_last_change(self):
        # Last change at a quarter of the window: the line still reaches the end.
        path = run(
            "card.sparkPath(card.anchored([{t: 0, v: 0}, {t: 25, v: 10}], 10, 100), 100, 40, 0, 100)")
        self.assertTrue(path.endswith("L100.0 2.0"), path)
        self.assertIn("L25.0 2.0", path)

    def test_an_unreadable_live_value_does_not_extend_the_line(self):
        self.assertEqual(
            [{"t": 0, "v": 1}],
            run("card.anchored([{t: 0, v: 1}], Number.NaN, 100)"),
        )


FAKE = r"""
const calls = [];
const fakeHass = (ids) => ({
  devices: { dev: { id: "dev", name: "Panel" }, other: { id: "other", name: "Other" } },
  areas: {},
  entities: Object.fromEntries(ids.map(([id, key, device]) => [id,
    { entity_id: id, device_id: device ?? "dev", platform: "nspanel_companion", translation_key: key }])),
  states: Object.fromEntries(ids.map(([id]) => [id, { state: "-50", last_changed: "2026-10-04T10:00:00Z", attributes: {} }])),
  callWS: (message) => { calls.push(message.entity_ids); return new Promise((done) => { pending.push(done); }); },
  callService: () => {},
});
const pending = [];
const make = () => {
  const el = new card.NSPanelCompanionCard();
  el.renders = 0;
  el.attachShadow = () => { el.shadowRoot = { set innerHTML(v) { el.renders += 1; }, getElementById: () => null }; };
  return el;
};
const settle = () => new Promise((done) => setTimeout(done, 0));
"""


def drive(body: str):
    return run("await (async () => {" + FAKE + body + "})()")


@unittest.skipUnless(NODE, "node is not installed")
class Holding(unittest.TestCase):
    """While someone is using a control, updates wait instead of rebuilding it."""

    def test_an_update_while_held_waits_and_lands_on_release(self):
        result = drive("""
          const el = make();
          el.setConfig({ device_id: "dev" });
          const hass = fakeHass([["sensor.w", "wifi_signal"]]);
          el.hass = hass;
          const before = el.renders;
          el._hold("select");
          el.hass = { ...hass, states: { "sensor.w": { state: "-60", last_changed: "2026-10-04T11:00:00Z", attributes: {} } } };
          const during = el.renders;
          el._release("select");
          return { held: during - before, after: el.renders - during };
        """)
        self.assertEqual({"held": 0, "after": 1}, result)

    def test_a_drag_that_ends_where_it_began_still_lets_go(self):
        # No change event fires for it; pointerup must release on its own.
        source = CARD.read_text()
        for event in ("pointerup", "pointercancel", "blur"):
            with self.subTest(event=event):
                self.assertIn(f'addEventListener("{event}"', source)

    def test_history_arriving_while_held_does_not_redraw(self):
        result = drive("""
          const el = make();
          el.setConfig({ device_id: "dev" });
          el.hass = fakeHass([["sensor.w", "wifi_signal"]]);
          el._hold("drag");
          const before = el.renders;
          pending.shift()([]);
          await settle();
          return el.renders - before;
        """)
        self.assertEqual(0, result)


@unittest.skipUnless(NODE, "node is not installed")
class HistoryFollowsTheEntities(unittest.TestCase):
    def test_enabling_a_reading_fetches_its_history_at_once(self):
        result = drive("""
          const el = make();
          el.setConfig({ device_id: "dev" });
          el.hass = fakeHass([["sensor.w", "wifi_signal"]]);
          pending.shift()({});
          await settle();
          el.hass = fakeHass([["sensor.w", "wifi_signal"], ["sensor.l", "ambient_light"]]);
          return calls;
        """)
        self.assertEqual([["sensor.w"], ["sensor.w", "sensor.l"]], result)

    def test_a_reply_for_the_previous_panel_is_discarded(self):
        result = drive("""
          const el = make();
          el.setConfig({ device_id: "dev" });
          const both = fakeHass([["sensor.w", "wifi_signal"], ["sensor.o", "wifi_signal", "other"]]);
          el.hass = both;
          el.setConfig({ device_id: "other" });
          el.hass = both;
          pending.shift()({ "sensor.w": [{ s: "-50", lu: 1 }, { s: "-51", lu: 2 }] });
          await settle();
          return { kept: Object.keys(el._history), calls };
        """)
        self.assertEqual([], result["kept"])
        self.assertEqual([["sensor.w"], ["sensor.o"]], result["calls"])



if __name__ == "__main__":
    unittest.main()
