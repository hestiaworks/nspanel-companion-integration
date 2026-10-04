"""Static contract tests for the dependency-free Home Assistant panel."""

from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "custom_components/nspanel_companion/frontend/nspanel-companion-panel.js"


class FrontendContractTest(unittest.TestCase):
    def test_home_assistant_state_is_read_through_the_property_that_exists(self):
        """`this.hass` is undefined here; the panel stores it as `_hass`.

        Optional chaining makes the mistake silent: `this.hass?.states` is
        simply undefined, so a control that depends on it renders as an empty
        string and the setting appears not to exist. That is exactly how the
        climate mode picker shipped in v0.44.0 doing nothing at all.
        """
        source = SCRIPT.read_text()
        wrong = re.findall(r"this\.hass\b", source)
        self.assertEqual([], wrong, "read Home Assistant state through this._hass")

    def test_frontend_uses_registered_websocket_commands(self):
        source = SCRIPT.read_text()
        for command in (
            "nspanel_companion/panels/list",
            "nspanel_companion/panels/register",
            "nspanel_companion/panels/rename",
            "nspanel_companion/layout/get",
            "nspanel_companion/layout/set",
            "nspanel_companion/doorbell/test",
            "nspanel_companion/pairings/list",
            "nspanel_companion/pairings/approve",
            "nspanel_companion/panels/revoke",
            "nspanel_companion/panels/diagnostics",
            "nspanel_companion/scrypted/list",
            "nspanel_companion/scrypted/pair",
            "nspanel_companion/scrypted/unpair",
            "nspanel_companion/scrypted/doorbells",
            "nspanel_companion/panels/discovery/scan",
            "nspanel_companion/panels/discovery/settings",
            "nspanel_companion/panels/discovery/connect",
            "nspanel_companion/updater/status",
            "nspanel_companion/updater/pair",
            "nspanel_companion/updater/autopair",
            "nspanel_companion/updater/unpair",
            "nspanel_companion/updater/discover",
            "nspanel_companion/updater/update",
        ):
            self.assertIn(command, source)
        self.assertIn("escapeHtml", source)
        self.assertIn("!dialogOpen", source)
        self.assertNotIn("Publish default", source)
        self.assertNotIn("Rotate token", source)
        # Publishing is one call. A second command that rewrote the layout it
        # had just saved is what made the doorbell form's talkback fields
        # accept a value and then discard it.
        self.assertNotIn("scrypted/assign", source)
        self.assertNotIn("<dt>Layout</dt>", source)
        self.assertRegex(source, r'\["general",\s*"General"\]')
        self.assertIn('data-workspace-panel="diagnostics"', source)
        self.assertIn("workspaceRoute", source)
        self.assertIn("No pages configured", source)
        self.assertIn("hasPublishedLayout: Boolean(layout)", source)
        self.assertIn("draftPages", source)
        self.assertIn("addDraftPage", source)
        self.assertIn('data-page-action="duplicate"', source)
        self.assertIn('data-page-drag=', source)
        self.assertNotIn('name="default_page"', source)
        self.assertIn('name="theme_mode"', source)
        self.assertIn('customElements.define("ha-panel-nspanel-companion-panel"', source)
        self.assertIn("customElements.define", source)
        self.assertIn('["nspanel-companion", "probable-nspanel"].includes(device.classification)', source)

    def test_updater_pairs_itself_and_hides_the_pairing_controls(self):
        """Installing the add-on is the intent; a pair button re-asks for it."""
        source = SCRIPT.read_text()
        self.assertIn("Updater add-on connected", source)
        self.assertIn("_autopairTried", source)
        # Unpair is offered only where the panel cannot simply pair again.
        self.assertIn('source === "manual"', source)
        self.assertNotIn(">Pair updater<", source)

    def test_removing_a_panel_clears_a_stale_error(self):
        """Otherwise an earlier failure looks like the removal failing."""
        source = SCRIPT.read_text()
        start = source.index("async revokePanel(")
        body = source[start:source.index("async ", start + 10)]
        self.assertIn('this.error = ""', body)

    def test_unpairing_surfaces_what_could_not_be_revoked(self):
        """The bridge is removed locally even when Scrypted is unreachable."""
        source = SCRIPT.read_text()
        start = source.index("async unpairScrypted(")
        body = source[start:source.index("async ", start + 10)]
        self.assertIn("warning", body)

    def test_manifest_loads_frontend_dependencies(self):
        manifest = json.loads((ROOT / "custom_components/nspanel_companion/manifest.json").read_text())
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(["frontend", "http", "zeroconf"], manifest["dependencies"])

    def test_manifest_carries_the_keys_hassfest_requires(self):
        """hassfest rejects a manifest without these, and HACS surfaces both links."""
        manifest = json.loads((ROOT / "custom_components/nspanel_companion/manifest.json").read_text())
        repository = "https://github.com/hestiaworks/nspanel-companion-integration"
        self.assertEqual(repository, manifest["documentation"])
        self.assertEqual(f"{repository}/issues", manifest["issue_tracker"])
        self.assertIn("requirements", manifest)

    def test_manifest_keys_are_ordered_the_way_hassfest_demands(self):
        """domain and name first, everything else alphabetical.

        hassfest fails the build on this, so catching it here turns a CI round
        trip into an immediate local failure.
        """
        keys = list(json.loads((ROOT / "custom_components/nspanel_companion/manifest.json").read_text()))
        self.assertEqual(["domain", "name"], keys[:2])
        self.assertEqual(sorted(keys[2:]), keys[2:])

    def test_admin_websocket_commands_use_current_ha_decorator(self):
        source = (ROOT / "custom_components/nspanel_companion/websocket.py").read_text()
        # 30: the 25 that remained after scrypted/assign went — publishing a
        # layout is one command, and the doorbell's Scrypted credentials are
        # filled in as it saves — plus five for the talkback add-on: paired,
        # unpaired and asked about exactly like the updater, and a test that
        # plays a tone at the door — plus two for notifications: a test of
        # each kind on a real panel, and a sound played on its speaker.
        self.assertEqual(32, source.count("@websocket_api.require_admin"))
        self.assertNotIn("connection.require_admin()", source)
        self.assertIn('{"nspanel-companion", "probable-nspanel"}', source)
        self.assertIn('device.get("adb_state") == "device"', source)

    def test_panel_sync_includes_human_readable_name(self):
        source = (ROOT / "custom_components/nspanel_companion/http.py").read_text()
        self.assertIn('"panel_name": record.get("name")', source)

    def test_panel_asset_version_matches_the_manifest(self):
        """A stale query string serves the cached panel after a HACS update.

        HACS offers the update from the manifest version, so if the asset URL
        does not move with it the browser keeps the old panel and the upgrade
        looks like it silently did nothing.
        """
        manifest = json.loads((ROOT / "custom_components/nspanel_companion/manifest.json").read_text())
        const_source = (ROOT / "custom_components/nspanel_companion/const.py").read_text()
        self.assertIn(f"?v={manifest['version']}\"", const_source)


    def test_the_release_badge_does_not_claim_a_panel_is_older(self):
        """`behind_release` means "not this version", not "older than it".

        Deciding what is newer needs the version code, which Home Assistant
        never sees — it has only the name a panel reported, and names do not
        sort. The installer does that comparison over ADB and refuses a
        downgrade; the badge answers the smaller question of who is not on
        what has been published.

        Saying "an earlier version" claims the comparison was made. It was
        not, and it was wrong in practice: after v1.3.1 shipped, three panels
        already running it were told they were on an earlier version, because
        the published version the badge still held was 1.3.0.
        """
        source = SCRIPT.read_text()
        self.assertNotIn("earlier version", source)


    def test_the_panel_socket_revisits_its_entity_set_when_entities_appear(self):
        """A set computed once per socket goes stale the moment one is added.

        `allowed_entity_ids` is the panel's whole permission boundary: the
        initial snapshot, history, schedules, service calls and the
        state_changed filter all consult it. Computed once at connect and never
        again, an entity that appears later is invisible *and* uncontrollable
        until the socket is reopened.

        Home Assistant restarting is exactly when this bites, because the panel
        reconnects while integrations are still loading.
        """
        source = (ROOT / "custom_components/nspanel_companion/http.py").read_text()
        self.assertIn("nonlocal entities", source,
                      "the state listener must be able to update the allowed set")
        self.assertGreaterEqual(
            source.count("allowed_entity_ids("), 2,
            "the allowed set has to be recomputed, not only built at connect",
        )


    def test_a_panel_can_report_a_problem_into_its_own_event_list(self):
        """A panel that finds something wrong needs somewhere to say so.

        The app's health journal only reaches Home Assistant inside the
        diagnostics blob, which nobody reads. The panel record already keeps
        an event list, and that is what the UI shows — so the panel is given
        a way to write into it.

        Added for the WiFi reconnect watchdog, which gives up after five
        attempts and has to explain why rather than reconnecting for ever.
        Deliberately generic: the next panel-side problem should not need its
        own plumbing.
        """
        source = (ROOT / "custom_components/nspanel_companion/http.py").read_text()
        self.assertIn('"panel_event"', source)
        self.assertIn("record_event", source)


if __name__ == "__main__":
    unittest.main()


class RevokeTellsThePanelTest(unittest.TestCase):
    """Unpairing was one-sided, and that is the whole point of the fix."""

    def test_revoking_notifies_a_connected_panel(self):
        source = (ROOT / "custom_components/nspanel_companion/registry.py").read_text()
        revoke = source[source.index("async def async_revoke"):source.index("async def async_set_layout")]
        self.assertIn("_async_tell_panel_it_was_revoked", revoke)
        notify = source[source.index("async def _async_tell_panel_it_was_revoked"):]
        self.assertIn('"type": "revoked"', notify)
        # The socket is closed, not merely written to: a panel left holding
        # an open socket to a registration that no longer exists would sit
        # there believing it is still paired.
        self.assertIn("socket.close()", notify)


class IntercomSignallingTest(unittest.TestCase):
    """Home Assistant relays signals; it does not read them."""

    def source(self):
        return (ROOT / "custom_components/nspanel_companion/http.py").read_text()

    def test_every_intercom_message_is_handled(self):
        source = self.source()
        for message in (
            "intercom_call", "intercom_answer", "intercom_decline",
            "intercom_signal", "intercom_end",
        ):
            self.assertIn(f'"{message}"', source, f"{message} is not handled")

    def test_the_roster_and_ring_are_pushed(self):
        source = self.source()
        self.assertIn('"type": "intercom_roster"', source)
        self.assertIn('"type": "intercom_ring"', source)

    def test_a_dropped_socket_ends_the_call_it_was_in(self):
        # The other end must be told rather than left listening to a link
        # that will never carry anything again.
        self.assertIn("drop_panel", self.source())


class TemplateScopeTest(unittest.TestCase):
    """A template referencing a variable its method does not have.

    The editor is one big class of methods returning template literals. A
    method that interpolates `layout.` without a local `layout` throws a
    ReferenceError at render time and takes the whole editor down with it —
    which is how adding a page stopped working, from a one-word mistake no
    syntax check could see.
    """

    METHOD = re.compile(r"^  (?:async )?([a-zA-Z][a-zA-Z0-9]*)\s*\(")

    def test_no_method_interpolates_a_layout_it_does_not_have(self):
        source = (
            ROOT / "custom_components/nspanel_companion/frontend/nspanel-companion-panel.js"
        ).read_text().splitlines()
        current, has_local, offenders = None, False, []
        for number, line in enumerate(source, 1):
            match = self.METHOD.match(line)
            if match:
                current = match.group(1)
                # A method handed a layout has one as surely as a method that
                # declares one. Reading only declarations flagged
                # roomLightExplainer(layout), which is exactly what the rule
                # is meant to permit.
                has_local = bool(re.search(r"\(([^)]*\b)?layout\b", line))
            # A local layout, however it was introduced — including by
            # destructuring, which is how editorDialog gets one.
            if re.search(r"\b(const|let|var)\s+layout\b", line) or re.search(
                r"\b(const|let|var)\s*\{[^}]*\blayout\b[^}]*\}\s*=", line,
            ):
                has_local = True
            # `this.editor.layout` and `page.layout` carry their own subject;
            # a bare `layout.` needs one in scope.
            if re.search(r"(?<![.\w])layout\.", line) and not has_local:
                offenders.append(f"{current}() line {number}")
        self.assertEqual([], offenders, "bare layout. with no local layout")



class SettingsAreActuallySaved(unittest.TestCase):
    """Every control in the settings form must be read back and published.

    Three settings shipped in 0.61.0 with an input, a default and backend
    validation, but no line in either the form collector or the publish
    payload. They rendered, they accepted a value, and the value went
    nowhere — the toggle simply sprang back. Nothing failed, because
    nothing ran.
    """

    PANEL = ROOT / "custom_components/nspanel_companion/frontend/nspanel-companion-panel.js"

    def _block(self, css_class: str) -> str:
        """Every fieldset of this class, joined: a tab may split one into groups."""
        source = self.PANEL.read_text()
        parts, at = [], 0
        while (start := source.find(f'<fieldset class="{css_class}"', at)) != -1:
            end = source.index("</fieldset>", start)
            parts.append(source[start:end])
            at = end
        assert parts, f"no {css_class} fieldset"
        return "\n".join(parts)

    def _names_in(self, css_class: str) -> set:
        block = self._block(css_class)
        # Sliders render their own input, so take their key as the name too.
        names = set(re.findall(r'name="([a-z0-9_]+)"', block))
        names |= set(re.findall(r'brightnessSlider\("([a-z0-9_]+)"', block))
        # And the dropdowns built by the notification tab's choice() helper.
        names |= set(re.findall(r'choice\("[^"]*", "([a-z0-9_]+)"', block))
        # And sound pickers: a select and a volume each.
        for sound, volume in re.findall(r'soundField\("[^"]*", "([a-z0-9_]+)", [^,]+, "([a-z0-9_]+)"', block):
            names |= {sound, volume}
        return names

    def test_every_display_control_is_collected_and_published(self):
        source = self.PANEL.read_text()
        missing = []
        for name in sorted(self._names_in("display")):
            if f'values.get("{name}")' not in source:
                missing.append(f"{name}: never read from the form")
            elif f"this.editor.layout.{name}" not in source:
                missing.append(f"{name}: read but never published")
        self.assertEqual([], missing, "settings that would silently not save")

    def test_every_network_control_is_collected_and_published(self):
        source = self.PANEL.read_text()
        missing = []
        for name in sorted(self._names_in("network")):
            if f'values.get("{name}")' not in source:
                missing.append(f"{name}: never read from the form")
            elif f"this.editor.layout.{name}" not in source:
                missing.append(f"{name}: read but never published")
        self.assertEqual([], missing, "settings that would silently not save")

    def test_every_notification_control_is_collected_and_published(self):
        # Nested under one block, so "published" means the block is: every
        # control must be read into it, and the block must be in the payload.
        source = self.PANEL.read_text()
        names = self._names_in("notifications")
        self.assertTrue(names, "found no notification controls — the fieldset has moved")
        missing = [f"{name}: never read from the form"
                   for name in sorted(names) if f'values.get("{name}")' not in source]
        self.assertEqual([], missing, "settings that would silently not save")
        self.assertIn("notifications: structuredClone(this.editor.layout.notifications", source)

    def test_a_sound_picker_offers_only_its_own_category(self):
        block = self._block("notifications")
        for kind, sounds in (("doorbell", "RING_SOUNDS"), ("intercom", "RING_SOUNDS"),
                             ("normal", "NOTIFICATION_SOUNDS"),
                             ("important", "NOTIFICATION_SOUNDS")):
            with self.subTest(kind=kind):
                self.assertRegex(block, rf'soundField\([^)]*"notify_{kind}_sound"[^)]*\b{sounds}\b[^)]*\)')

    def test_a_sound_button_reads_its_own_row(self):
        # Every row's buttons once played the first picker in the section.
        source = self.PANEL.read_text()
        start = source.index("  soundBeside(button) {")
        body = source[start:source.index("\n  }\n", start)]
        self.assertIn('button.closest(".sound-row")', body)
        self.assertNotIn("parentElement", body)
        self.assertIn("this.soundBeside(button)", source[source.index("  previewSound(button) {"):])

    def test_each_kind_has_its_own_group(self):
        # One long list blended four kinds of alert into one config.
        block = self._block("notifications")
        for kind in ("Doorbell", "Intercom", "Notification", "Important notification", "Quiet hours"):
            with self.subTest(kind=kind):
                self.assertIn(f'aria-label="{kind}"', block)

    def test_every_volume_is_a_slider(self):
        source = self.PANEL.read_text()
        start = source.index("const soundField")
        helper = source[start:source.index("`;", start)]
        self.assertIn('type="range"', helper)
        self.assertIn("data-sound-volume", helper)
        self.assertNotIn('type="number"', helper)

    def test_both_repeats_read_the_same(self):
        # A regular and an important notification repeat the same way; the
        # editor says so with the same words.
        block = self._block("notifications")
        self.assertEqual(2, block.count('choice("Repeat", '))
        self.assertNotIn("Show again", block)
        self.assertNotIn("Repeat sound", block)

    def test_dimmed_rows_do_not_trap_their_open_lists(self):
        # Opacity (or a filter or transform) makes a row its own layer: the
        # open list inside it turned see-through, and the rows below were
        # drawn over it. Dim the text and the field instead.
        import re
        source = self.PANEL.read_text()
        rules = re.findall(r"\.quiet-behaviour[^{]*\{([^}]*)\}", source)
        self.assertTrue(rules, "no quiet-behaviour rules found")
        for body in rules:
            for trap in ("opacity", "filter", "transform", "isolation", "z-index"):
                with self.subTest(trap=trap):
                    self.assertNotIn(trap, body)

    def test_the_old_sound_controls_are_gone(self):
        # One place for every sound: a second picker for the same setting
        # would publish whichever was read last.
        source = self.PANEL.read_text()
        for old in ('soundField("Chime", "chime"', '"intercom_ring"'):
            with self.subTest(control=old):
                self.assertNotIn(old, source)


class FrontendCallsCommandsThatExist(unittest.TestCase):
    """Every websocket command the panel calls must be registered.

    A mistyped command name fails only when a person clicks the thing, with
    an error that names the type rather than the mistake.
    """

    def test_no_command_is_called_that_the_backend_does_not_serve(self):
        panel = (ROOT / "custom_components/nspanel_companion/frontend/nspanel-companion-panel.js").read_text()
        backend = (ROOT / "custom_components/nspanel_companion/websocket.py").read_text()
        called = set(re.findall(r'type: "(nspanel_companion/[a-z_/]+)"', panel))
        served = set(re.findall(r'"(nspanel_companion/[a-z_/]+)"', backend))
        self.assertTrue(called, "found no commands in the panel — the regex has drifted")
        self.assertEqual(set(), called - served,
                         "the panel calls commands the backend does not register")

    def test_the_talkback_commands_are_wired_end_to_end(self):
        panel = (ROOT / "custom_components/nspanel_companion/frontend/nspanel-companion-panel.js").read_text()
        backend = (ROOT / "custom_components/nspanel_companion/websocket.py").read_text()
        for verb in ("status", "pair", "autopair", "unpair"):
            command = f"nspanel_companion/talkback/{verb}"
            self.assertIn(command, panel, f"{command} is never called by the panel")
            self.assertIn(command, backend, f"{command} is not registered")

    def test_every_registered_command_has_its_handler_registered(self):
        backend = (ROOT / "custom_components/nspanel_companion/websocket.py").read_text()
        defined = set(re.findall(r"^async def (ws_[a-z_]+)\(", backend, re.M))
        registered = set(re.findall(r"async_register_command\(hass, (ws_[a-z_]+)\)", backend))
        self.assertEqual(set(), defined - registered,
                         "handlers that exist but are never registered would never be callable")


class SignalDisplay(unittest.TestCase):
    """The panel list shows each panel's wifi signal.

    A weak link does not present as a weak link: it presented here as video
    taking sixteen seconds, talkback four seconds late, and timeouts against
    a service that was plainly up. One panel at -79 beside two at -40 was
    the whole diagnosis, and nothing surfaced it.
    """

    PANEL = ROOT / "custom_components/nspanel_companion/frontend/nspanel-companion-panel.js"

    def test_the_card_renders_a_signal(self):
        source = self.PANEL.read_text()
        self.assertIn("signalLabel(", source)
        self.assertIn("panel.link", source)

    def test_signal_colours_use_tokens_the_theme_defines(self):
        # A var() with no definition and no fallback renders as nothing,
        # which reads as "no signal reported" rather than as a styling bug.
        source = self.PANEL.read_text()
        defined = set(re.findall(r"(--[a-z-]+)\s*:\s*#", source))
        used = set(re.findall(r"\.sig-[a-z]+ \{ color:var\((--[a-z-]+)\)", source))
        self.assertTrue(used, "no signal colours found — the rule has drifted")
        self.assertEqual(set(), used - defined,
                         "signal colours reference undefined theme tokens")

    def test_the_backend_accepts_what_the_panel_sends(self):
        http = (ROOT / "custom_components/nspanel_companion/http.py").read_text()
        registry = (ROOT / "custom_components/nspanel_companion/registry.py").read_text()
        self.assertIn('"panel_link"', http)
        self.assertIn("def record_link", registry)


class TalkbackCardStyles(unittest.TestCase):
    """Classes the talkback card uses must be styled, or they render bare."""

    PANEL = ROOT / "custom_components/nspanel_companion/frontend/nspanel-companion-panel.js"

    def test_notice_variants_exist(self):
        source = self.PANEL.read_text()
        used = set(re.findall(r'class="notice \$\{[^}]*\? "([a-z]+)" : "([a-z]+)"', source))
        flat = {v for pair in used for v in pair}
        defined = set(re.findall(r"\.notice\.([a-z]+)", source))
        self.assertTrue(flat, "no conditional notice classes found — the rule has drifted")
        self.assertEqual(set(), flat - defined - {"plain"},
                         "notice variants with no stylesheet rule")

    def test_the_test_button_is_wired_to_a_registered_command(self):
        panel = self.PANEL.read_text()
        backend = (ROOT / "custom_components/nspanel_companion/websocket.py").read_text()
        self.assertIn("talkback-test", panel)
        self.assertIn("nspanel_companion/talkback/test", panel)
        self.assertIn("nspanel_companion/talkback/test", backend)

    def test_health_drives_the_status_chip(self):
        # "Paired" alone said connected all evening while the add-on had
        # been reinstalled and forgotten us.
        source = self.PANEL.read_text()
        self.assertIn("talkback?.health", source)
        self.assertIn("needs attention", source)
