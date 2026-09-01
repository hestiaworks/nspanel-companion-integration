// What the panel carries. Adding one here means adding the file to the app
// as well: the panel can only play a sound it was built with.
const RING_SOUNDS = [
  { value: "off", label: "No sound" },
  { value: "chime_1", label: "Chime 1" },
  { value: "chime_2", label: "Chime 2" },
  { value: "chime_3", label: "Chime 3" },
];

const SOUND_BASE = "/nspanel_companion/frontend/sounds";

/**
 * A sound picker with the sound attached.
 *
 * The preview plays the same file the panel does, served from this
 * integration, at the volume beside it — so what you hear is what the panel
 * will play, allowing for its speaker. Choosing a doorbell chime by name
 * alone means walking to the panel to find out.
 */
const soundField = (label, name, value, volumeName, volume) => `
  <label>${label}<span class="sound-row">
    <select name="${name}" data-sound-select>${RING_SOUNDS.map((sound) => `<option value="${sound.value}" ${(value || "off") === sound.value ? "selected" : ""}>${sound.label}</option>`).join("")}</select>
    <button type="button" class="sound-play" data-sound-play title="Play this sound">&#9654;</button>
  </span></label>
  <label>${label} volume<input name="${volumeName}" type="number" min="0" max="100" value="${Number(volume ?? 70)}" data-sound-volume></label>`;

const DEFAULT_LAYOUT = (revision) => ({
  schema_version: 1,
  revision,
  default_page_id: "climate",
  default_page_return_seconds: 60,
  weather_cache_max_age_minutes: 360,
  keep_screen_on: false,
  show_clock: true,
  show_mic_indicator: true,
  mic_indicator_linger_seconds: 15,
  nav_bar_mode: "listener",
  hide_accessibility_button: false,
  wake_on_approach: false,
  wake_sensitivity: "medium",
  intercom: { enabled: false },
  pages: [
    { id: "climate", title: "Thermostat", widgets: [{ type: "thermostat" }] },
    { id: "weather", title: "Weather", widgets: [{ type: "weather" }] },
    { id: "controls", title: "Controls", widgets: [{ type: "controls" }] },
  ],
});

const CONTROL_ICONS = [
  ["auto", "Auto", "◇", "all"],
  ["light", "Light", "✦", "lighting"], ["ceiling-light", "Ceiling light", "◓", "lighting"], ["floor-lamp", "Floor lamp", "♧", "lighting"],
  ["table-lamp", "Table lamp", "♧", "lighting"], ["wall-light", "Wall light", "◖", "lighting"], ["led-strip", "LED strip", "⋯", "lighting"],
  ["spotlight", "Spotlight", "◒", "lighting"], ["chandelier", "Chandelier", "✣", "lighting"], ["pendant-light", "Pendant light", "◉", "lighting"],
  ["outdoor-light", "Outdoor light", "☼", "lighting"], ["night-light", "Night light", "☾", "lighting"], ["desk-lamp", "Desk lamp", "⌁", "lighting"],
  ["fan", "Fan", "⌁", "air"], ["ceiling-fan", "Ceiling fan", "✣", "air"], ["desk-fan", "Desk fan", "⊛", "air"],
  ["ventilation", "Ventilation", "≋", "air"], ["air-purifier", "Air purifier", "≋", "air"], ["humidifier", "Humidifier", "♨", "air"],
  ["dehumidifier", "Dehumidifier", "♨", "air"], ["extractor-fan", "Extractor fan", "⊛", "air"],
  ["power", "Power", "⏻", "power"], ["switch", "Switch", "◉", "power"], ["plug", "Plug", "⌑", "power"], ["socket", "Socket", "⊙", "power"],
  ["power-strip", "Power strip", "▭", "power"], ["battery", "Battery", "▯", "power"], ["solar", "Solar", "☼", "power"],
  ["energy", "Energy", "ϟ", "power"], ["meter", "Meter", "◴", "power"], ["ups", "UPS", "▣", "power"],
  ["curtains", "Curtains", "▥", "covers"], ["cover", "Cover (legacy)", "▥", "covers"], ["blinds", "Blinds", "▤", "covers"],
  ["shutter", "Shutter", "▦", "covers"], ["garage", "Garage", "▣", "covers"], ["awning", "Awning", "◩", "covers"],
  ["window", "Window", "▢", "covers"], ["door", "Door", "▯", "covers"], ["skylight", "Skylight", "◇", "covers"],
  ["radiator", "Radiator", "▥", "climate"], ["air-conditioner", "Air conditioner", "▭", "climate"], ["fireplace", "Fireplace", "♨", "climate"],
  ["thermostat", "Thermostat", "◉", "climate"], ["heater", "Heater", "♨", "climate"], ["boiler", "Boiler", "◍", "climate"],
  ["temperature", "Temperature", "♨", "climate"], ["snowflake", "Cooling", "❄", "climate"],
  ["lock", "Lock", "▱", "security"], ["unlock", "Unlock", "▱", "security"], ["gate", "Gate", "╫", "security"],
  ["alarm", "Alarm", "△", "security"], ["shield", "Security", "◇", "security"], ["camera", "Camera", "◉", "security"],
  ["motion", "Motion", "◌", "security"], ["presence", "Presence", "●", "security"], ["bell", "Doorbell", "♢", "security"],
  ["kitchen", "Kitchen", "⌂", "appliances"], ["oven", "Oven", "▣", "appliances"], ["microwave", "Microwave", "▣", "appliances"],
  ["fridge", "Refrigerator", "▯", "appliances"], ["dishwasher", "Dishwasher", "▤", "appliances"], ["washing-machine", "Washing machine", "◉", "appliances"],
  ["dryer", "Dryer", "◉", "appliances"], ["coffee", "Coffee maker", "♨", "appliances"], ["kettle", "Kettle", "♨", "appliances"],
  ["vacuum", "Vacuum", "◉", "cleaning"], ["robot-vacuum", "Robot vacuum", "◉", "cleaning"], ["broom", "Broom", "╱", "cleaning"],
  ["pump", "Pump", "⊕", "water"], ["water", "Water", "●", "water"], ["faucet", "Faucet", "⌐", "water"],
  ["sprinkler", "Sprinkler", "✣", "water"], ["pool", "Pool", "≈", "water"], ["shower", "Shower", "⋰", "water"],
  ["speaker", "Speaker", "◖", "media"], ["television", "Television", "▣", "media"], ["music", "Music", "♪", "media"],
  ["radio", "Radio", "▤", "media"], ["gamepad", "Game console", "✣", "media"], ["projector", "Projector", "◉", "media"],
  ["bedroom", "Bedroom", "▰", "rooms"], ["bathroom", "Bathroom", "▱", "rooms"], ["office", "Office", "▣", "rooms"],
  ["garden", "Garden", "♧", "rooms"], ["balcony", "Balcony", "▥", "rooms"], ["stairs", "Stairs", "▟", "rooms"],
];

class NSPanelCompanionPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.panels = [];
    this.pairings = [];
    this.panelFinderOpen = false;
    this.pairingSelection = null;
    this.discoveredPanels = [];
    this.passivePanelDiscovery = false;
    this.scrypted = { discovered: [], paired: [] };
    this.updater = { paired: null };
    this._autopairTried = false;
    this.adbDevices = [];
    this.updaterMessage = "";
    this.scryptedDoorbells = [];
    this.loading = true;
    this.busy = false;
    this.error = "";
    this.token = null;
    this.editor = null;
    this.workspaceTab = "general";
    this.routeHandler = () => this.restoreWorkspaceRoute();
    this.outsidePickerHandler = (event) => {
      const activePicker = event.composedPath().find((node) => node?.classList?.contains("entity-picker"));
      this.shadowRoot.querySelectorAll(".entity-results:not([hidden])").forEach((results) => {
        if (!activePicker || results.closest(".entity-picker") !== activePicker) results.hidden = true;
      });
    };
  }

  set hass(value) {
    this._hass = value;
    if (this.isConnected && !this.loaded) this.loadPanels();
  }

  set narrow(value) { this.toggleAttribute("narrow", Boolean(value)); }
  set panel(value) { this._panel = value; }

  connectedCallback() {
    window.addEventListener("hashchange", this.routeHandler);
    window.addEventListener("popstate", this.routeHandler);
    document.addEventListener("pointerdown", this.outsidePickerHandler, true);
    this.render();
    if (this._hass && !this.loaded) this.loadPanels();
    this.refreshTimer = setInterval(() => {
      const dialogOpen = this.editor || this.token || this.panelFinderOpen;
      if (!this.loading && !this.busy && !dialogOpen) this.loadPanels();
    }, 15000);
  }

  disconnectedCallback() {
    window.removeEventListener("hashchange", this.routeHandler);
    window.removeEventListener("popstate", this.routeHandler);
    document.removeEventListener("pointerdown", this.outsidePickerHandler, true);
    clearInterval(this.refreshTimer); clearInterval(this.finderTimer);
  }

  workspaceRoute(panelId, tab = "general", pageId = null) {
    const base = `#panel/${encodeURIComponent(panelId)}/${encodeURIComponent(tab)}`;
    return pageId ? `${base}/${encodeURIComponent(pageId)}` : base;
  }

  parsedWorkspaceRoute() {
    const match = window.location.hash.match(/^#panel\/([^/]+)(?:\/([^/]+))?(?:\/([^/]+))?$/);
    if (!match) return null;
    const tabs = new Set(["general", "pages", "doorbell", "diagnostics", "advanced"]);
    const tab = decodeURIComponent(match[2] || "general");
    return { panelId: decodeURIComponent(match[1]), tab: tabs.has(tab) ? tab : "general", pageId: match[3] ? decodeURIComponent(match[3]) : null };
  }

  async restoreWorkspaceRoute() {
    const route = this.parsedWorkspaceRoute();
    if (!route) {
      if (this.editor) { this.editor = null; this.render(); }
      return;
    }
    if (!this.loaded) return;
    if (this.editor?.panel.panel_id === route.panelId) {
      this.editor.activePageId = route.tab === "pages" ? route.pageId : null;
      this.selectWorkspaceTab(route.tab, false);
      this.render();
      return;
    }
    if (this.panels.some((panel) => panel.panel_id === route.panelId)) {
      await this.editPanel(route.panelId, route.tab, false, route.pageId);
    } else {
      history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    }
  }

  selectWorkspaceTab(tab, updateRoute = true) {
    this.workspaceTab = tab;
    this.shadowRoot.querySelectorAll("[data-workspace-tab]").forEach((button) =>
      button.classList.toggle("active", button.dataset.workspaceTab === tab));
    this.shadowRoot.querySelectorAll("[data-workspace-panel]").forEach((panel) =>
      panel.toggleAttribute("hidden", panel.dataset.workspacePanel !== tab));
    if (updateRoute && this.editor) history.pushState(null, "", this.workspaceRoute(this.editor.panel.panel_id, tab));
  }

  closeWorkspace() {
    this.editor = null;
    history.pushState(null, "", `${window.location.pathname}${window.location.search}`);
    this.render();
  }

  async call(message) {
    if (!this._hass) throw new Error("Home Assistant is not ready");
    return this._hass.connection.sendMessagePromise(message);
  }

  async loadPanels() {
    this.loading = true;
    this.error = "";
    this.render();
    try {
      [this.panels, this.scrypted, this.updater] = await Promise.all([
        this.call({ type: "nspanel_companion/panels/list" }),
        this.call({ type: "nspanel_companion/scrypted/list" }),
        this.call({ type: "nspanel_companion/updater/status" }),
      ]);
      this.loaded = true;
      await this.autopairUpdater();
    } catch (error) {
      this.error = error?.message || "Unable to load panels";
    } finally {
      this.loading = false;
      this.render();
      await this.restoreWorkspaceRoute();
    }
  }

  async openPanelFinder() {
    this.panelFinderOpen = true;
    this.pairingSelection = null;
    this.discoveredPanels = [];
    this.render();
    await this.scanPanels();
  }

  closePanelFinder() {
    this.panelFinderOpen = false;
    this.pairingSelection = null;
    this.discoveredPanels = [];
    this.render();
  }

  async loadPairings() {
    if (!this.panelFinderOpen) return;
    try {
      this.pairings = await this.call({ type: "nspanel_companion/pairings/list" });
      if (this.pairingSelection) {
        this.pairingSelection = this.pairings.find((item) => item.request_id === this.pairingSelection.request_id) || null;
      }
      this.error = "";
    } catch (error) { this.error = error?.message || "Unable to find panels"; }
    this.render();
  }

  async scanPanels() {
    this.busy = true; this.error = ""; this.render();
    try {
      const result = await this.call({ type: "nspanel_companion/panels/discovery/scan" });
      this.discoveredPanels = result.panels || [];
      this.passivePanelDiscovery = Boolean(result.passive);
    } catch (error) { this.error = error?.message || "Unable to scan for panels"; }
    finally { this.busy = false; this.render(); }
  }

  async connectDiscoveredPanel(panel) {
    this.busy = true; this.error = ""; this.render();
    try {
      this.pairingSelection = await this.call({
        type: "nspanel_companion/panels/discovery/connect",
        device_id: panel.id,
        base_url: panel.base_url,
      });
    } catch (error) { this.error = error?.message || "Unable to contact panel"; }
    finally { this.busy = false; this.render(); }
  }

  async setPassivePanelDiscovery(enabled) {
    this.busy = true; this.render();
    try {
      const result = await this.call({ type: "nspanel_companion/panels/discovery/settings", passive: enabled });
      this.passivePanelDiscovery = Boolean(result.passive);
    } catch (error) { this.error = error?.message || "Unable to update discovery setting"; }
    finally { this.busy = false; this.render(); }
  }

  async registerPanel(form) {
    const values = new FormData(form);
    this.busy = true;
    this.error = "";
    this.render();
    try {
      const result = await this.call({
        type: "nspanel_companion/panels/register",
        name: String(values.get("name") || "").trim(),
        device_id: String(values.get("device_id") || "").trim(),
      });
      this.token = { panel: result.panel, value: result.token, title: "Panel registered" };
      await this.loadPanels();
    } catch (error) {
      this.error = error?.message || "Unable to register panel";
    } finally {
      this.busy = false;
      this.render();
    }
  }

  async approvePairing(form) {
    const values = new FormData(form);
    const requestId = String(values.get("request_id") || "");
    this.busy = true;
    this.error = "";
    this.render();
    try {
      await this.call({
        type: "nspanel_companion/pairings/approve",
        request_id: requestId,
        code: String(values.get("code") || ""),
      });
      this.panelFinderOpen = false;
      this.pairingSelection = null;
      this.discoveredPanels = [];
      await this.loadPanels();
    } catch (error) {
      this.error = error?.message || "Unable to approve pairing";
    } finally {
      this.busy = false;
      this.render();
    }
  }

  async revokePanel(panelId) {
    if (!confirm("Remove and unpair this panel? It will erase its saved pairing and return to the setup screen.")) return;
    this.busy = true; this.error = ""; this.render();
    try {
      await this.call({ type: "nspanel_companion/panels/revoke", panel_id: panelId });
      this.editor = null;
      await this.loadPanels();
    } catch (error) { this.error = error?.message || "Unable to revoke token"; }
    finally { this.busy = false; this.render(); }
  }

  async editPanel(panelId, tab = "general", updateRoute = true, pageId = null) {
    this.busy = true; this.error = ""; this.render();
    try {
      const panel = this.panels.find((item) => item.panel_id === panelId);
      const layout = await this.call({ type: "nspanel_companion/layout/get", panel_id: panelId });
      const discoveredDoorbells = [];
      for (const bridge of this.scrypted.paired || []) {
        const items = await this.call({ type: "nspanel_companion/scrypted/doorbells", bridge_id: bridge.id });
        discoveredDoorbells.push(...items.map((item) => ({ ...item, bridge_id: bridge.id })));
      }
      this.scryptedDoorbells = [...new Map(discoveredDoorbells.map((item) => [`${item.bridge_id}|${item.id}`, item])).values()];
      this.workspaceTab = tab;
      const fallback = DEFAULT_LAYOUT(`panel-${Date.now()}`);
      this.editor = {
        panel,
        layout: layout || fallback,
        hasPublishedLayout: Boolean(layout),
        draftPages: structuredClone(layout?.pages || []),
        draftThemeMode: layout ? (layout.theme_mode || "light") : "inherit",
        activePageId: pageId,
      };
      if (updateRoute) history.pushState(null, "", this.workspaceRoute(panelId, tab));
    } catch (error) { this.error = error?.message || "Unable to open editor"; }
    finally { this.busy = false; this.render(); }
  }

  async renamePanel(form) {
    const values = new FormData(form);
    const name = String(values.get("panel_name") || "").trim();
    const themeMode = String(values.get("theme_mode") || "light");
    const generalSettings = {
      default_page_return_seconds: Number(values.get("return_seconds") ?? 60),
      keep_screen_on: values.get("keep_screen_on") === "on",
      show_clock: values.get("show_clock") === "on",
      show_mic_indicator: values.get("show_mic_indicator") === "on",
      mic_indicator_linger_seconds: Number(values.get("mic_indicator_linger_seconds") ?? 15),
      nav_bar_mode: String(values.get("nav_bar_mode") || "listener"),
      hide_accessibility_button: values.get("hide_accessibility_button") === "on",
      wake_on_approach: values.get("wake_on_approach") === "on",
      wake_sensitivity: String(values.get("wake_sensitivity") || "medium"),
      intercom: {
        enabled: values.get("intercom_enabled") === "on",
        ring: String(values.get("intercom_ring") || "off"),
        ring_volume: Number(values.get("intercom_ring_volume") ?? 70),
        noise_suppression: values.get("intercom_noise_suppression") === "on",
        auto_gain: values.get("intercom_auto_gain") === "on",
      },
    };
    if (!name || !this.editor) return;
    this.busy = true; this.error = "";
    try {
      const panel = await this.call({
        type: "nspanel_companion/panels/rename",
        panel_id: this.editor.panel.panel_id,
        name,
      });
      this.editor.panel = panel;
      this.panels = this.panels.map((item) => item.panel_id === panel.panel_id ? panel : item);
      this.editor.draftThemeMode = themeMode;
      if (this.editor.hasPublishedLayout) {
        const themeLayout = {
          ...structuredClone(this.editor.layout),
          ...generalSettings,
          revision: `general-${Date.now()}`,
          theme_mode: themeMode,
          theme_dark: themeMode === "dark" || themeMode === "inherit" && Boolean(this._hass?.themes?.darkMode),
        };
        await this.call({ type: "nspanel_companion/layout/set", panel_id: panel.panel_id, layout: themeLayout });
        this.editor.layout = themeLayout;
      } else {
        this.editor.layout = { ...this.editor.layout, ...generalSettings, theme_mode: themeMode };
      }
      this.render();
    } catch (error) {
      this.error = error?.message || "Unable to rename panel";
      this.render();
    } finally { this.busy = false; this.render(); }
  }

  /**
   * Play the chosen sound, as the panel would.
   *
   * One at a time: pressing play on the doorbell while the intercom's ring
   * is still going would tell you nothing about either. The volume beside
   * the picker is applied, so this is the panel's setting rather than a
   * generic preview — allowing for the panel's own speaker, which is smaller
   * than anything this is being auditioned on.
   */
  previewSound(button) {
    const row = button.closest("label")?.parentElement || button.parentElement;
    const select = row?.querySelector("[data-sound-select]")
      || button.closest(".sound-row")?.querySelector("[data-sound-select]");
    const sound = select?.value;
    this.soundPreview?.pause();
    if (!sound || sound === "off") return;
    const volume = Number(
      button.closest("label")?.nextElementSibling?.querySelector("[data-sound-volume]")?.value ?? 70,
    );
    const audio = new Audio(`${SOUND_BASE}/${sound}.mp3`);
    audio.volume = Math.min(1, Math.max(0, volume / 100));
    this.soundPreview = audio;
    audio.play().catch(() => { this.error = "The browser would not play the sound."; this.render(); });
  }

  async restartPanel(device = false) {
    if (!this.editor) return;
    if (device && !confirm("Reboot the panel? It will be unavailable for about a minute.")) return;
    this.busy = true; this.error = "";
    try {
      const result = await this.call({
        type: "nspanel_companion/panels/restart",
        panel_id: this.editor.panel.panel_id,
        // The updater knows the panel by address; without one it can only
        // be reached down its own socket.
        address: String(this.editor.panel.address || ""),
        device,
      });
      this.error = device
        ? "Rebooting the panel; it will be back in about a minute."
        : result?.via === "updater"
          ? "Restarted over ADB; the panel was not connected."
          : "Restart sent to the panel.";
    } catch (error) {
      this.error = error?.message || "Unable to restart the panel";
    } finally { this.busy = false; this.render(); }
  }

  syncPageDraftFromDom() {
    if (!this.editor) return;
    this.shadowRoot.querySelectorAll("[data-page-title]").forEach((input) => {
      const index = Number(input.dataset.pageTitle);
      if (this.editor.draftPages[index]) this.editor.draftPages[index].title = input.value.trim();
    });
    // Mode checkboxes are a group rather than a field: the widget records
    // the ticked ones as a list, so the list is cleared once per group and
    // then filled, instead of each box overwriting the last.
    const startedGroups = new Set();
    this.shadowRoot.querySelectorAll("[data-mode-value]").forEach((input) => {
      const page = this.editor.draftPages.find((item) => item.id === input.dataset.pageId);
      const widget = page?.widgets?.[Number(input.dataset.widgetIndex)];
      if (!widget) return;
      const field = input.dataset.widgetField;
      const key = `${input.dataset.pageId}|${input.dataset.widgetIndex}|${field}`;
      if (!startedGroups.has(key)) { widget[field] = []; startedGroups.add(key); }
      if (input.checked) widget[field].push(input.dataset.modeValue);
    });
    this.shadowRoot.querySelectorAll("[data-widget-field]").forEach((input) => {
      if (input.type === "radio" && !input.checked) return;
      if (input.dataset.modeValue !== undefined) return;
      const page = this.editor.draftPages.find((item) => item.id === input.dataset.pageId);
      const widget = page?.widgets?.[Number(input.dataset.widgetIndex)];
      if (!widget) return;
      const field = input.dataset.widgetField;
      const value = input.type === "checkbox" ? input.checked : input.value.trim();
      if (field === "scrypted_source") {
        const [bridgeId, ...cameraParts] = String(value).split("|");
        widget.scrypted_bridge_id = value ? bridgeId : "";
        widget.scrypted_camera_id = value ? cameraParts.join("|") : "";
        return;
      }
      if (field === "timer_presets") {
        widget.timer_presets = String(value).split(",").map((item) => Number(item.trim())).filter((item) => Number.isFinite(item) && item > 0).slice(0, 4);
        return;
      }
      if (input.type === "checkbox") widget[field] = value;
      else if (value) widget[field] = field === "forecast_days" ? Number(value) : value;
      else delete widget[field];
    });
  }

  refreshPagePreview() {
    this.syncPageDraftFromDom();
    const page = this.editor?.draftPages.find((item) => item.id === this.editor.activePageId);
    const host = this.shadowRoot.querySelector(".panel-preview-host");
    if (page && host) host.innerHTML = this.pagePreview(page);
  }

  pageIdFor(title) {
    const base = title.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "").slice(0, 28) || "page";
    const used = new Set(this.editor.draftPages.map((page) => page.id));
    if (!used.has(base)) return base;
    for (let number = 2; number < 100; number += 1) {
      const candidate = `${base.slice(0, 29)}-${number}`;
      if (!used.has(candidate)) return candidate;
    }
    return `page-${Date.now().toString(36)}`.slice(0, 32);
  }

  addDraftPage() {
    if (!this.editor || this.editor.draftPages.length >= 8) return;
    this.syncPageDraftFromDom();
    const input = this.shadowRoot.querySelector("#new-page-title");
    const title = String(input?.value || "").trim();
    if (!title) { input?.focus(); return; }
    const page = { id: this.pageIdFor(title), title: title.slice(0, 48), widgets: [] };
    this.editor.draftPages.push(page);
    this.editor.activePageId = page.id;
    history.pushState(null, "", this.workspaceRoute(this.editor.panel.panel_id, "pages", page.id));
    this.error = "";
    this.render();
  }

  updateDraftPage(index, action) {
    if (!this.editor?.draftPages[index]) return;
    this.syncPageDraftFromDom();
    const pages = this.editor.draftPages;
    const current = pages[index];
    if (action === "up" && index > 0) [pages[index - 1], pages[index]] = [pages[index], pages[index - 1]];
    if (action === "down" && index < pages.length - 1) [pages[index + 1], pages[index]] = [pages[index], pages[index + 1]];
    if (action === "duplicate" && pages.length < 8) {
      const copy = structuredClone(current);
      copy.id = this.pageIdFor(`${current.title} copy`);
      copy.title = `${current.title} copy`.slice(0, 48);
      pages.splice(index + 1, 0, copy);
      this.editor.activePageId = copy.id;
      history.pushState(null, "", this.workspaceRoute(this.editor.panel.panel_id, "pages", copy.id));
    }
    if (action === "delete") {
      pages.splice(index, 1);
      if (this.editor.activePageId === current.id) this.editor.activePageId = pages[index]?.id || pages[index - 1]?.id || null;
    }
    this.render();
  }

  selectDraftPage(pageId) {
    this.syncPageDraftFromDom();
    this.editor.activePageId = pageId;
    history.pushState(null, "", this.workspaceRoute(this.editor.panel.panel_id, "pages", pageId));
    this.render();
  }

  widgetTemplate(type) {
    if (type === "weather") return { type, forecast_days: 5, show_hourly: true };
    if (type === "entity_button") return { type, icon: "auto", show_timer: true, show_schedule: true, timer_presets: [5, 15, 30, 60], card_tap: false, show_fan_speed: false };
    if (type === "camera") return { type, incoming_audio: false, show_intercom: false };
    if (type === "history") return { type, history_range: "24h" };
    return { type };
  }

  addDraftWidget(pageId, type) {
    this.syncPageDraftFromDom();
    const page = this.editor?.draftPages.find((item) => item.id === pageId);
    if (!page || !type || page.widgets.length >= 12) return;
    if (type === "entity_button" && page.widgets.length >= 4) {
      this.error = "A controls page supports at most four controls.";
      this.render();
      return;
    }
    const isFullScreen = ["thermostat", "weather", "camera"].includes(type);
    if ((isFullScreen && page.widgets.length) || (!isFullScreen && page.widgets.some((item) => ["thermostat", "weather", "camera"].includes(item.type)))) {
      this.error = "Thermostat, weather, and camera use the full panel screen. Put each on its own page.";
      this.render();
      return;
    }
    page.widgets.push(this.widgetTemplate(type));
    this.error = "";
    this.render();
  }

  updateDraftWidget(pageId, index, action) {
    this.syncPageDraftFromDom();
    const page = this.editor?.draftPages.find((item) => item.id === pageId);
    if (!page?.widgets?.[index]) return;
    if (action === "delete") page.widgets.splice(index, 1);
    this.render();
  }

  moveDraftWidget(pageId, from, to) {
    if (from === to || from < 0 || to < 0) return;
    this.syncPageDraftFromDom();
    const widgets = this.editor?.draftPages.find((item) => item.id === pageId)?.widgets;
    if (!widgets?.[from] || !widgets?.[to]) return;
    const [widget] = widgets.splice(from, 1);
    widgets.splice(to, 0, widget);
    this.render();
  }

  moveDraftPage(from, to) {
    if (!this.editor || from === to || from < 0 || to < 0) return;
    this.syncPageDraftFromDom();
    const pages = this.editor.draftPages;
    const [page] = pages.splice(from, 1);
    pages.splice(to, 0, page);
    this.render();
  }

  async saveEditor(form) {
    this.syncPageDraftFromDom();
    const values = new FormData(form);
    const scryptedDoorbell = String(values.get("scrypted_doorbell") || "");
    const [scryptedBridgeId, ...scryptedDeviceParts] = scryptedDoorbell.split("|");
    const scryptedDoorbellId = scryptedDoorbell ? scryptedDeviceParts.join("|") : "";
    const pages = structuredClone(this.editor.draftPages);
    if (!pages.length) {
      this.error = "Create at least one page before publishing.";
      this.render();
      this.selectWorkspaceTab("pages", false);
      return;
    }
    if (pages.some((page) => !page.title || !(page.widgets || []).length)) {
      this.error = "Every page needs a name and at least one component before publishing.";
      this.render();
      this.selectWorkspaceTab("pages", false);
      return;
    }
    if (pages.some((page) => page.widgets.some((widget) => ["controls", "entity_button"].includes(widget.type)) && page.widgets.length > 4)) {
      this.error = "A controls page supports at most four controls.";
      this.render();
      this.selectWorkspaceTab("pages", false);
      return;
    }
    if (pages.some((page) => page.widgets.some((widget) => ["entity_button", "sensor", "thermostat", "weather"].includes(widget.type) && !widget.entity_id))) {
      this.error = "Select a Home Assistant entity for every component before publishing.";
      this.render();
      this.selectWorkspaceTab("pages", false);
      return;
    }
    if (pages.some((page) => page.widgets.some((widget) => widget.type === "camera" && (!widget.scrypted_bridge_id || !widget.scrypted_camera_id)))) {
      this.error = "Select a Scrypted camera for every camera page before publishing.";
      this.render();
      this.selectWorkspaceTab("pages", false);
      return;
    }
    const defaultPageId = pages[0].id;
    const layout = {
      schema_version: 1,
      revision: `ui-${Date.now()}`,
      default_page_id: defaultPageId,
      default_page_return_seconds: Number(this.editor.layout.default_page_return_seconds ?? 60),
      weather_cache_max_age_minutes: 360,
      keep_screen_on: Boolean(this.editor.layout.keep_screen_on),
      show_clock: this.editor.layout.show_clock !== false,
      show_mic_indicator: this.editor.layout.show_mic_indicator !== false,
      mic_indicator_linger_seconds: Number(this.editor.layout.mic_indicator_linger_seconds ?? 15),
      nav_bar_mode: String(this.editor.layout.nav_bar_mode || "listener"),
      hide_accessibility_button: Boolean(this.editor.layout.hide_accessibility_button),
      wake_on_approach: Boolean(this.editor.layout.wake_on_approach),
      wake_sensitivity: String(this.editor.layout.wake_sensitivity || "medium"),
      intercom: { enabled: Boolean(this.editor.layout.intercom?.enabled) },
      theme_mode: this.editor.draftThemeMode,
      theme_dark: this.editor.draftThemeMode === "dark" || this.editor.draftThemeMode === "inherit" && Boolean(this._hass?.themes?.darkMode),
      pages,
      doorbell: {
        enabled: values.get("doorbell_enabled") === "on",
        trigger_entity_id: String(values.get("doorbell_trigger") || ""),
        stream_base_url: String(values.get("stream_base_url") || "").trim(),
        stream_name: String(values.get("stream_name") || "").trim(),
        talkback_url: String(values.get("talkback_url") || "").trim(),
        talkback_key: String(values.get("talkback_key") || "").trim(),
        scrypted_bridge_id: scryptedDoorbell ? scryptedBridgeId : "",
        scrypted_doorbell_id: scryptedDoorbellId,
        quiet_mode: values.get("quiet_mode") === "on",
        chime: String(values.get("chime") || "off"),
        chime_volume: Number(values.get("chime_volume") ?? 70),
        talkback_gain: Number(values.get("talkback_gain") ?? 100),
        auto_close_ms: Number(values.get("auto_close_seconds") || 60) * 1000,
        talk_extend_enabled: values.get("talk_extend_enabled") === "on",
        talk_extend_ms: Number(values.get("talk_extend_seconds") || 15) * 1000,
      },
    };
    this.busy = true; this.error = "";
    const saveButtons = [...form.querySelectorAll("button")];
    saveButtons.forEach((button) => { button.disabled = true; });
    try {
      await this.call({ type: "nspanel_companion/layout/set", panel_id: this.editor.panel.panel_id, layout });
      if (scryptedDoorbell) {
        await this.call({
          type: "nspanel_companion/scrypted/assign",
          panel_id: this.editor.panel.panel_id,
          bridge_id: scryptedBridgeId,
          doorbell_id: scryptedDoorbellId,
        });
      }
      this.editor = null;
      await this.loadPanels();
    } catch (error) {
      this.editor.layout = layout;
      this.error = error?.message || "Unable to publish layout";
      alert(this.error);
    }
    finally {
      this.busy = false;
      saveButtons.forEach((button) => { button.disabled = false; });
      if (!this.editor) this.render();
    }
  }

  async pairScrypted(form) {
    const values = new FormData(form);
    this.busy = true; this.error = ""; this.render();
    try {
      await this.call({
        type: "nspanel_companion/scrypted/pair",
        base_url: String(values.get("base_url") || ""),
        code: String(values.get("code") || ""),
      });
      await this.loadPanels();
    } catch (error) { this.error = error?.message || "Unable to pair Scrypted"; }
    finally { this.busy = false; this.render(); }
  }

  async unpairScrypted(bridgeId, clearAssignments) {
    const message = clearAssignments
      ? "Unpair Scrypted and remove its video/talkback configuration from every panel?"
      : "Unpair Scrypted? Existing published panel doorbell settings will be preserved.";
    if (!confirm(message)) return;
    this.busy = true; this.error = ""; this.render();
    try {
      const result = await this.call({
        type: "nspanel_companion/scrypted/unpair",
        bridge_id: bridgeId,
        clear_assignments: clearAssignments,
      });
      await this.loadPanels();
      // The bridge is removed here even when Scrypted cannot be reached, so say
      // what is left behind rather than reporting a plain success.
      if (result?.warning) this.error = result.warning;
    } catch (error) { this.error = error?.message || "Unable to unpair Scrypted"; }
    finally { this.busy = false; this.render(); }
  }

  async pairUpdater(form) {
    const values = new FormData(form);
    this.busy = true; this.error = ""; this.render();
    try {
      await this.call({
        type: "nspanel_companion/updater/pair",
        base_url: String(values.get("base_url") || "").trim(),
        code: String(values.get("code") || "").trim(),
      });
      this.updater = await this.call({ type: "nspanel_companion/updater/status" });
    } catch (error) { this.error = error?.message || "Unable to pair updater"; }
    finally { this.busy = false; this.render(); }
  }

  async autopairUpdater() {
    // Installing the add-on is the request; connecting to it does not need a
    // second confirmation. Attempted once per session, and quietly: no add-on
    // installed is the normal case, not an error worth showing.
    if (this._autopairTried || this.updater?.paired) return;
    this._autopairTried = true;
    try {
      await this.call({ type: "nspanel_companion/updater/autopair" });
      this.updater = await this.call({ type: "nspanel_companion/updater/status" });
    } catch (error) {
      /* No updater on this host. The manual path stays available. */
    }
  }

  async unpairUpdater() {
    if (!confirm("Unpair the ADB updater service? No panel apps will be changed.")) return;
    this.busy = true; this.error = ""; this.render();
    try {
      await this.call({ type: "nspanel_companion/updater/unpair" });
      this.updater = { paired: null }; this.adbDevices = [];
    } catch (error) { this.error = error?.message || "Unable to unpair updater"; }
    finally { this.busy = false; this.render(); }
  }

  async discoverAdbPanels(form) {
    const values = new FormData(form);
    this.busy = true; this.error = ""; this.updaterMessage = "Scanning for ADB-enabled panels…"; this.render();
    try {
      const result = await this.call({
        type: "nspanel_companion/updater/discover",
        subnet: String(values.get("subnet") || "").trim(),
      });
      this.adbDevices = (result.devices || []).filter((device) =>
        ["nspanel-companion", "probable-nspanel"].includes(device.classification));
      this.updaterMessage = this.adbDevices.length ? `Found ${this.adbDevices.length} ADB device${this.adbDevices.length === 1 ? "" : "s"}.` : "No ADB-enabled devices found.";
    } catch (error) { this.error = error?.message || "Unable to scan for ADB panels"; this.updaterMessage = ""; }
    finally { this.busy = false; this.render(); }
  }

  async updateAdbPanel(address, source = "github", migrateDebug = false) {
    const device = this.adbDevices.find((item) => item.address === address);
    if (!device) return;
    const action = device.app_version ? "Update" : "Install";
    const warning = source === "local" && migrateDebug
      ? `Migrate ${device.address} to the locally staged signed release? The existing debug app will be uninstalled, its local pairing/configuration will be erased, and the panel must be paired again.`
      : `${action} NSPanel Companion on ${device.address}? The panel app will restart.`;
    if (!confirm(warning)) return;
    this.busy = true; this.error = ""; this.updaterMessage = `${action} in progress. Keep power connected…`; this.render();
    try {
      const result = await this.call({
        type: "nspanel_companion/updater/update", address: device.address,
        classification: device.classification, source, migrate_debug: migrateDebug,
      });
      this.updaterMessage = result.message || "Update completed.";
      const subnet = this.shadowRoot.querySelector("#adb-subnet")?.value || "192.168.0.0/24";
      const refreshed = await this.call({ type: "nspanel_companion/updater/discover", subnet });
      this.adbDevices = (refreshed.devices || []).filter((item) =>
        ["nspanel-companion", "probable-nspanel"].includes(item.classification));
    } catch (error) { this.error = error?.message || "Unable to update panel"; this.updaterMessage = ""; }
    finally { this.busy = false; this.render(); }
  }

  async testDoorbell(panelId) {
    if (this.busy) return;
    this.busy = true;
    this.error = "";
    const buttons = [...this.shadowRoot.querySelectorAll("[data-test-doorbell]")];
    buttons.forEach((button) => { button.disabled = true; });
    try {
      await this.call({ type: "nspanel_companion/doorbell/test", panel_id: panelId });
    } catch (error) { this.error = error?.message || "Unable to test doorbell"; }
    finally {
      this.busy = false;
      buttons.forEach((button) => { button.disabled = false; });
      if (this.error) alert(this.error);
    }
  }

  async downloadDiagnostics(panelId) {
    if (this.busy) return;
    this.busy = true; this.error = "";
    const buttons = [...this.shadowRoot.querySelectorAll("[data-diagnostics]")];
    buttons.forEach((button) => { button.disabled = true; });
    try {
      const result = await this.call({ type: "nspanel_companion/panels/diagnostics", panel_id: panelId });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([result.report || "No diagnostic report received yet."], { type: "text/plain" }));
      link.download = `${panelId}-diagnostics.txt`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (error) { this.error = error?.message || "Unable to download diagnostics"; }
    finally {
      this.busy = false;
      buttons.forEach((button) => { button.disabled = false; });
      if (this.error) alert(this.error);
    }
  }

  copyToken() {
    if (!this.token) return;
    navigator.clipboard.writeText(this.token.value);
  }

  downloadToken() {
    if (!this.token) return;
    const data = JSON.stringify({
      panel_id: this.token.panel.panel_id,
      device_id: this.token.panel.device_id,
      token: this.token.value,
    }, null, 2);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([data], { type: "application/json" }));
    link.download = `${this.token.panel.panel_id}-credentials.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  bind() {
    this.shadowRoot.querySelector("#register")?.addEventListener("submit", (event) => {
      event.preventDefault();
      this.registerPanel(event.currentTarget);
    });
    this.shadowRoot.querySelectorAll("[data-scrypted-pair]").forEach((form) =>
      form.addEventListener("submit", (event) => { event.preventDefault(); this.pairScrypted(event.currentTarget); }));
    this.shadowRoot.querySelectorAll("[data-scrypted-unpair]").forEach((button) =>
      button.addEventListener("click", () => this.unpairScrypted(button.dataset.scryptedUnpair, false)));
    this.shadowRoot.querySelectorAll("[data-scrypted-clear]").forEach((button) =>
      button.addEventListener("click", () => this.unpairScrypted(button.dataset.scryptedClear, true)));
    this.shadowRoot.querySelector("#updater-pair")?.addEventListener("submit", (event) => {
      event.preventDefault(); this.pairUpdater(event.currentTarget);
    });
    this.shadowRoot.querySelector("#updater-unpair")?.addEventListener("click", () => this.unpairUpdater());
    this.shadowRoot.querySelectorAll("[data-sound-play]").forEach((button) =>
      button.addEventListener("click", () => this.previewSound(button)));
    this.shadowRoot.querySelector("[data-restart-panel]")?.addEventListener("click", () => this.restartPanel(false));
    this.shadowRoot.querySelector("[data-reboot-panel]")?.addEventListener("click", () => this.restartPanel(true));
    this.shadowRoot.querySelector("#adb-discovery")?.addEventListener("submit", (event) => {
      event.preventDefault(); this.discoverAdbPanels(event.currentTarget);
    });
    this.shadowRoot.querySelectorAll("[data-adb-update]").forEach((button) =>
      button.addEventListener("click", () => this.updateAdbPanel(button.dataset.adbUpdate)));
    this.shadowRoot.querySelectorAll("[data-adb-local]").forEach((button) =>
      button.addEventListener("click", () => this.updateAdbPanel(button.dataset.adbLocal, "local", button.dataset.migrateDebug === "true")));
    this.shadowRoot.querySelector("#refresh")?.addEventListener("click", () => this.loadPanels());
    this.shadowRoot.querySelector("#find-panels-empty")?.addEventListener("click", () => this.openPanelFinder());
    this.shadowRoot.querySelector("#find-panels")?.addEventListener("click", () => this.openPanelFinder());
    this.shadowRoot.querySelector("#close-panel-finder")?.addEventListener("click", () => this.closePanelFinder());
    this.shadowRoot.querySelector("#refresh-panel-finder")?.addEventListener("click", () => this.scanPanels());
    this.shadowRoot.querySelector("#passive-discovery")?.addEventListener("change", (event) => this.setPassivePanelDiscovery(event.currentTarget.checked));
    this.shadowRoot.querySelectorAll("[data-select-panel]").forEach((button) =>
      button.addEventListener("click", () => {
        const panel = this.discoveredPanels.find((item) => item.id === button.dataset.selectPanel);
        if (panel) this.connectDiscoveredPanel(panel);
      }));
    this.shadowRoot.querySelector("#back-to-panels")?.addEventListener("click", () => { this.pairingSelection = null; this.render(); });
    this.shadowRoot.querySelector("#copy-token")?.addEventListener("click", () => this.copyToken());
    this.shadowRoot.querySelector("#download-token")?.addEventListener("click", () => this.downloadToken());
    this.shadowRoot.querySelector("#close-token")?.addEventListener("click", () => { this.token = null; this.render(); });
    this.shadowRoot.querySelectorAll("[data-close-editor]").forEach((button) =>
      button.addEventListener("click", () => this.closeWorkspace()));
    this.shadowRoot.querySelectorAll("[data-workspace-tab]").forEach((button) =>
      button.addEventListener("click", () => this.selectWorkspaceTab(button.dataset.workspaceTab)));
    this.shadowRoot.querySelector("#panel-general")?.addEventListener("submit", (event) => {
      event.preventDefault(); this.renamePanel(event.currentTarget);
    });
    this.shadowRoot.querySelector("#layout-editor")?.addEventListener("submit", (event) => {
      event.preventDefault(); this.saveEditor(event.currentTarget);
    });
    this.shadowRoot.querySelector("#add-page")?.addEventListener("click", () => this.addDraftPage());
    this.shadowRoot.querySelector("#new-page-title")?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); this.addDraftPage(); }
    });
    this.shadowRoot.querySelectorAll("[data-page-action]").forEach((button) =>
      button.addEventListener("click", () => this.updateDraftPage(Number(button.dataset.pageIndex), button.dataset.pageAction)));
    this.shadowRoot.querySelectorAll("[data-edit-page]").forEach((button) =>
      button.addEventListener("click", () => this.selectDraftPage(button.dataset.editPage)));
    this.shadowRoot.querySelector("[data-close-page-components]")?.addEventListener("click", () => {
      this.syncPageDraftFromDom(); this.editor.activePageId = null;
      history.pushState(null, "", this.workspaceRoute(this.editor.panel.panel_id, "pages"));
      this.render();
    });
    this.shadowRoot.querySelector("#add-widget")?.addEventListener("click", (event) =>
      this.addDraftWidget(event.currentTarget.dataset.widgetPage, this.shadowRoot.querySelector("#new-widget-type")?.value));
    this.shadowRoot.querySelectorAll("[data-widget-action]").forEach((button) =>
      button.addEventListener("click", () => this.updateDraftWidget(button.dataset.widgetPage, Number(button.dataset.widgetIndex), button.dataset.widgetAction)));
    this.shadowRoot.querySelectorAll("[data-widget-field]").forEach((input) => {
      input.addEventListener("input", () => this.refreshPagePreview());
      input.addEventListener("change", () => {
        if (input.type === "radio" && input.dataset.widgetField === "icon") {
          const name = CONTROL_ICONS.find(([id]) => id === input.value)?.[1] || "Auto";
          const selected = input.closest(".icon-picker")?.querySelector("summary b");
          if (selected) selected.textContent = name;
        }
        this.refreshPagePreview();
      });
    });
    this.shadowRoot.querySelectorAll("[data-icon-search]").forEach((input) => {
      const picker = input.closest(".icon-picker");
      const filter = () => {
        const query = input.value.trim().toLowerCase();
        const category = picker?.dataset.iconCategory || "all";
        picker?.querySelectorAll("[data-icon-name]").forEach((option) => {
          const categoryMatch = category === "all" || option.dataset.iconCategoryOption === category || option.querySelector("input")?.value === "auto";
          option.toggleAttribute("hidden", !categoryMatch || Boolean(query) && !option.dataset.iconName.includes(query));
        });
      };
      input.addEventListener("input", filter);
      picker?.querySelectorAll("[data-icon-category-button]").forEach((button) => button.addEventListener("click", () => {
        picker.dataset.iconCategory = button.dataset.iconCategoryButton;
        picker.querySelectorAll("[data-icon-category-button]").forEach((item) => item.classList.toggle("active", item === button));
        filter();
      }));
    });
    this.shadowRoot.querySelectorAll("[data-entity-search]").forEach((input) => {
      const picker = input.closest(".entity-picker");
      const results = picker?.querySelector(".entity-results");
      const filter = () => {
        const query = input.value.trim().toLowerCase();
        let shown = 0;
        results?.querySelectorAll("[data-entity-option]").forEach((option) => {
          const visible = (!query || option.dataset.entityTerms.includes(query)) && shown < 60;
          option.toggleAttribute("hidden", !visible);
          if (visible) shown += 1;
        });
        if (results) results.hidden = false;
      };
      input.addEventListener("focus", filter);
      input.addEventListener("input", () => {
        const hidden = picker?.querySelector("input[type='hidden'][data-widget-field]");
        if (hidden) hidden.value = "";
        filter();
      });
      results?.querySelectorAll("[data-entity-option]").forEach((option) => option.addEventListener("click", () => {
        const hidden = picker.querySelector("input[type='hidden'][data-widget-field]");
        hidden.value = option.dataset.entityOption;
        input.value = option.dataset.entityLabel;
        results.hidden = true;
        this.refreshPagePreview();
      }));
      input.addEventListener("keydown", (event) => { if (event.key === "Escape" && results) results.hidden = true; });
    });
    this.shadowRoot.querySelectorAll("[data-widget-drag]").forEach((handle) => {
      handle.addEventListener("dragstart", (event) => {
        event.stopPropagation();
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("application/x-nspanel-widget", JSON.stringify({ pageId: handle.dataset.widgetPage, index: Number(handle.dataset.widgetDrag) }));
        handle.closest(".widget-card")?.classList.add("dragging");
      });
      handle.addEventListener("dragend", () => this.shadowRoot.querySelectorAll(".widget-card").forEach((card) => card.classList.remove("dragging", "drag-over")));
    });
    this.shadowRoot.querySelectorAll("[data-widget-drop]").forEach((card) => {
      card.addEventListener("dragover", (event) => {
        if (!event.dataTransfer.types.includes("application/x-nspanel-widget")) return;
        event.preventDefault(); event.stopPropagation(); card.classList.add("drag-over");
      });
      card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
      card.addEventListener("drop", (event) => {
        const raw = event.dataTransfer.getData("application/x-nspanel-widget");
        if (!raw) return;
        event.preventDefault(); event.stopPropagation();
        const source = JSON.parse(raw);
        if (source.pageId === card.dataset.widgetPage) this.moveDraftWidget(source.pageId, Number(source.index), Number(card.dataset.widgetDrop));
      });
    });
    this.shadowRoot.querySelectorAll("[data-page-drag]").forEach((handle) => {
      handle.addEventListener("dragstart", (event) => {
        this.draggedPageIndex = Number(handle.dataset.pageDrag);
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", String(this.draggedPageIndex));
        handle.closest(".page-card")?.classList.add("dragging");
      });
      handle.addEventListener("dragend", () => {
        this.draggedPageIndex = null;
        this.shadowRoot.querySelectorAll(".page-card").forEach((card) => card.classList.remove("dragging", "drag-over"));
      });
    });
    this.shadowRoot.querySelectorAll("[data-page-drop]").forEach((card) => {
      card.addEventListener("dragover", (event) => { event.preventDefault(); card.classList.add("drag-over"); });
      card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
      card.addEventListener("drop", (event) => {
        event.preventDefault();
        const from = Number(event.dataTransfer.getData("text/plain"));
        const to = Number(card.dataset.pageDrop);
        this.moveDraftPage(from, to);
      });
    });
    this.shadowRoot.querySelectorAll("[data-edit]").forEach((button) =>
      button.addEventListener("click", () => this.editPanel(button.dataset.edit, "general")));
    this.shadowRoot.querySelectorAll("[data-test-doorbell]").forEach((button) =>
      button.addEventListener("click", () => this.testDoorbell(button.dataset.testDoorbell)));
    this.shadowRoot.querySelectorAll("[data-open-diagnostics]").forEach((button) =>
      button.addEventListener("click", () => this.editPanel(button.dataset.openDiagnostics, "diagnostics")));
    this.shadowRoot.querySelectorAll("[data-diagnostics]").forEach((button) =>
      button.addEventListener("click", () => this.downloadDiagnostics(button.dataset.diagnostics)));
    this.shadowRoot.querySelectorAll("[data-panel-pair]").forEach((form) =>
      form.addEventListener("submit", (event) => { event.preventDefault(); this.approvePairing(event.currentTarget); }));
    this.shadowRoot.querySelectorAll("[data-revoke]").forEach((button) =>
      button.addEventListener("click", () => this.revokePanel(button.dataset.revoke)));
  }

  /**
   * What used to be two cards, as one row.
   *
   * Scrypted and the updater are paired once and then forgotten; §6 moves
   * them off home entirely because two half-empty cards for services most
   * installs never touch pushed the panels themselves below the fold.
   */
  integrationStrip() {
    const bridges = (this.scrypted?.paired || []).length;
    const updater = this.updater?.paired;
    return `<div class="integration-strip">
      <div><span class="dot ${bridges ? "on" : "off"}"></span><span class="name">Scrypted intercom</span>
        <span class="state">${bridges ? `connected · ${bridges} bridge${bridges === 1 ? "" : "s"}` : "not set up"}</span></div>
      <div><span class="dot ${updater ? "on" : "off"}"></span><span class="name">Installation &amp; updates</span>
        <span class="state">${updater ? "connected" : "not set up"}</span></div>
      <div class="go muted">Integrations →</div>
    </div>`;
  }

  panelCard(panel) {
    const online = !panel.revoked && panel.last_seen && Date.now() - new Date(panel.last_seen).getTime() < 45000;
    const layout = panel.layout;
    const configured = Boolean(layout?.pages?.length);
    const state = panel.revoked ? "revoked" : !configured ? "unconfigured" : online ? "online" : "offline";
    const tone = panel.revoked ? "error" : online && configured ? "online" : configured ? "offline" : "waiting";
    // The metrics row is what makes a wall of tiles readable at a glance:
    // the same three facts, in the same place, at the same height.
    const metrics = `<div class="metrics">
      <div><span class="t-label">Pages</span><b>${layout?.pages?.length ?? "—"}</b></div>
      <div><span class="t-label">Revision</span><b>${layout?.revision ?? "—"}</b></div>
      <div><span class="t-label">Last seen</span><b>${panel.last_seen ? escapeHtml(sinceLabel(panel.last_seen)) : "—"}</b></div>
    </div>`;
    return `<article class="panel-card">
      <div class="identity">
        <span class="device-icon ${online ? "active" : ""}">▣</span>
        <div class="grow"><div class="t-sub truncate">${escapeHtml(panel.name)}</div>
          <div class="id truncate" title="${escapeHtml(panel.device_id)}">${escapeHtml(panel.device_id)}</div></div>
        <span class="status ${tone}">${state}</span>
      </div>
      ${configured ? metrics : `<div class="warn-strip">No layout published yet. This panel shows the setup screen until you assign pages.</div>`}
      <div class="actions">
        <button class="primary" data-edit="${escapeHtml(panel.panel_id)}" ${this.busy ? "disabled" : ""}>${configured ? "Configure" : "Set up pages"}</button>
        <button data-open-diagnostics="${escapeHtml(panel.panel_id)}" ${this.busy ? "disabled" : ""}>Diagnostics</button>
      </div>
    </article>`;
  }

  render() {
    if (!this.shadowRoot) return;
    if (this.editor) {
      this.shadowRoot.innerHTML = `<style>${STYLES}</style>${this.editorDialog()}${this.token ? this.tokenDialog() : ""}${this.panelFinderOpen ? this.panelFinderDialog() : ""}`;
      this.bind();
      return;
    }
    this.shadowRoot.innerHTML = `<style>${STYLES}</style>
      <div class="app-bar"><span class="mark"></span><span class="t-control">NSPanel Companion</span><span class="spacer"></span>
        <button id="refresh" class="quiet small" type="button" ${this.loading ? "disabled" : ""}>↻ Refresh</button></div>
      <main>
        ${this.error ? `<div class="notice error">${escapeHtml(this.error)}</div>` : ""}
        ${this.integrationStrip()}
        <div class="page-head"><div><h1 class="t-page">Panels</h1><p>Native dashboards connected to this Home Assistant.</p></div><span class="spacer"></span>
          <button id="find-panels" class="primary" type="button" ${this.busy ? "disabled" : ""}>Find panels</button></div>
        ${this.loading
          ? `<div class="empty"><span class="glyph">▣</span><b class="t-sub">Loading panels…</b></div>`
          : this.panels.length
            ? `<div class="panel-grid">${this.panels.map((p) => this.panelCard(p)).join("")}</div>`
            : `<div class="empty"><span class="glyph">▣</span><b class="t-sub">No panels yet</b><p>Open the companion app on an NSPanel Pro, leave the pairing screen visible, then search this network.</p><button id="find-panels-empty" class="primary" type="button" ${this.busy ? "disabled" : ""}>Find panels</button></div>`}
      </main>
      ${this.token ? this.tokenDialog() : ""}
      ${this.panelFinderOpen ? this.panelFinderDialog() : ""}`;
    this.bind();
  }

  panelFinderDialog() {
    const selected = this.pairingSelection;
    if (selected) return `<div class="scrim"><section class="dialog pairing-dialog"><div class="pairing-dialog-head"><button id="back-to-panels" type="button">← Back</button><span class="eyebrow">Pair panel</span></div><div class="pairing-dialog-body"><h2>${escapeHtml(selected.name)}</h2><p class="device-id">${escapeHtml(selected.device_id)}</p><p class="pairing-help">Enter the six-digit code displayed on this panel.</p><form class="pairing-form" data-panel-pair><input type="hidden" name="request_id" value="${escapeHtml(selected.request_id)}"><input class="pair-code pairing-entry" name="code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="one-time-code" autofocus required placeholder="000000" aria-label="Pairing code"><div class="actions pairing-actions"><button id="close-panel-finder" type="button">Cancel</button><button class="primary" ${this.busy ? "disabled" : ""}>Pair panel</button></div></form></div></section></div>`;
    return `<div class="scrim"><section class="dialog"><div class="editor-head"><div><span class="eyebrow">Local discovery</span><h2>Find panels</h2><p>${this.busy ? "Scanning the local network…" : "Unpaired panels available on this network."}</p></div><button id="close-panel-finder">Close</button></div>${this.discoveredPanels.length ? `<div class="finder-list">${this.discoveredPanels.map((item) => `<button class="finder-panel" data-select-panel="${escapeHtml(item.id)}" ${this.busy ? "disabled" : ""}><span class="device-icon">▣</span><span><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.id)}</small></span><span>›</span></button>`).join("")}</div>` : `<div class="empty"><b>${this.busy ? "Searching for panels…" : "No unpaired panels found"}</b><span>Keep the pairing screen open on the NSPanel and try again.</span></div>`}<label class="check discovery-option"><input id="passive-discovery" type="checkbox" ${this.passivePanelDiscovery ? "checked" : ""} ${this.busy ? "disabled" : ""}> Keep panel discovery running in the background</label><small>Off by default. When disabled, HA scans only after you press Find panels or Search again.</small><div class="actions"><button id="refresh-panel-finder" ${this.busy ? "disabled" : ""}>Search again</button></div></section></div>`;
  }

  scryptedSection() {
    const pairedIds = new Set((this.scrypted.paired || []).map((item) => item.id));
    const available = (this.scrypted.discovered || []).filter((item) => !pairedIds.has(item.id));
    if (!available.length && !(this.scrypted.paired || []).length) {
      return `<section class="bridge"><div><h2>Scrypted intercom</h2><p>Install and enable NSPanel Talkback in Scrypted. It will appear here automatically.</p></div><span class="status waiting">Searching…</span></section>`;
    }
    return `<section class="bridge"><div><h2>Scrypted intercom</h2><p>Pair once to configure video and two-way audio without URLs or access keys.</p></div>
      <div class="bridge-list">
        ${(this.scrypted.paired || []).map((item) => `<div class="bridge-row"><div><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.base_url)}</small></div><span class="status online">Paired</span><button data-scrypted-unpair="${escapeHtml(item.id)}" ${this.busy ? "disabled" : ""}>Unpair</button><button class="danger" data-scrypted-clear="${escapeHtml(item.id)}" ${this.busy ? "disabled" : ""}>Unpair + clear doorbells</button></div>`).join("")}
        ${available.map((item) => `<form class="bridge-row" data-scrypted-pair><input type="hidden" name="base_url" value="${escapeHtml(item.base_url)}"><div><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.base_url)} · v${escapeHtml(item.version)}</small></div><input class="pair-code" name="code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required placeholder="6-digit code"><button class="primary" ${this.busy ? "disabled" : ""}>Pair</button></form>`).join("")}
      </div></section>`;
  }

  updaterSection() {
    const paired = this.updater?.paired;
    if (!paired) return `<section class="updater-section"><div class="updater-head"><div><h2>Panel installation & updates</h2><p>Optional: pair the NSPanel Updater add-on to discover ADB-enabled panels and install signed releases.</p></div></div><small>Install and start the NSPanel Companion Updater add-on and it will connect here on its own.</small><details class="updater-manual"><summary>The updater runs on another host</summary><form id="updater-pair" class="updater-pair"><label>Updater URL<input name="base_url" type="url" value="http://${escapeHtml(location.hostname)}:8098" required></label><label>Pairing code<input name="code" class="pair-code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" placeholder="000000" required></label><button ${this.busy ? "disabled" : ""}>Pair manually</button></form><small>Copy the six-digit code from the add-on log.</small></details></section>`;
    return `<section class="updater-section"><div class="updater-head"><div><h2>Panel installation & updates</h2><p>Scan only when requested. Updates require confirmation and restore the app as Home.</p></div><div class="updater-status"><span class="status online">Updater add-on connected</span>${this.updater?.paired?.source === "manual" ? `<button id="updater-unpair" ${this.busy ? "disabled" : ""}>Unpair</button>` : ""}</div></div><form id="adb-discovery" class="adb-scan"><label>Private subnet<input id="adb-subnet" name="subnet" value="192.168.0.0/24" pattern="[0-9./]+" required></label><button class="primary" ${this.busy ? "disabled" : ""}>${this.busy ? "Working…" : "Discover ADB panels"}</button></form>${this.updaterMessage ? `<div class="notice">${escapeHtml(this.updaterMessage)}</div>` : ""}${this.adbDevices.length ? `<div class="adb-devices">${this.adbDevices.map((device) => this.adbDeviceCard(device)).join("")}</div>` : ""}</section>`;
  }

  adbDeviceCard(device) {
    const safe = ["nspanel-companion", "probable-nspanel"].includes(device.classification) && device.adb_state === "device";
    const title = [device.manufacturer, device.model].filter(Boolean).join(" ") || device.address;
    const version = device.app_version ? `Installed ${device.app_version} (${device.app_version_code ?? "?"})` : "App not installed";
    const action = device.app_version ? "Check & update" : "Install app";
    const localAction = device.app_version ? "Migrate local test" : "Install local test";
    return `<article class="adb-device"><span class="device-icon">▣</span><div><h3>${escapeHtml(title)}</h3><p>${escapeHtml(device.address)} · ${escapeHtml(device.screen_size || "screen unknown")}</p><small>${escapeHtml(version)} · ${escapeHtml(device.classification || "unknown")}</small></div><span class="status ${safe ? "online" : "waiting"}">${escapeHtml(device.adb_state)}</span><div class="adb-actions"><button data-adb-local="${escapeHtml(device.address)}" data-migrate-debug="${device.app_version ? "true" : "false"}" ${!safe || this.busy ? "disabled" : ""}>${localAction}</button><button class="primary" data-adb-update="${escapeHtml(device.address)}" ${!safe || this.busy ? "disabled" : ""}>${action}</button></div></article>`;
  }

  tokenDialog() {
    return `<div class="scrim"><section class="dialog"><span class="success-mark">✓</span><h2>${escapeHtml(this.token.title)}</h2>
      <p>Save this token now. Home Assistant will not display it again.</p>
      <label>Panel token<div class="token"><code>${escapeHtml(this.token.value)}</code><button id="copy-token">Copy</button></div></label>
      <div class="actions"><button id="download-token">Download credentials</button><button id="close-token" class="primary">I saved it</button></div></section></div>`;
  }

  entityOptions(domains, selected, emptyLabel) {
    const states = Object.values(this._hass?.states || {}).filter((item) => domains.includes(item.entity_id.split(".")[0]));
    states.sort((a, b) => this.entityLabel(a).localeCompare(this.entityLabel(b)));
    return `<option value="">${escapeHtml(emptyLabel)}</option>` + states.map((item) =>
      `<option value="${escapeHtml(item.entity_id)}" ${item.entity_id === selected ? "selected" : ""}>${escapeHtml(this.entityLabel(item))}</option>`
    ).join("");
  }

  entityLabel(state) {
    return `${state.attributes?.friendly_name || state.entity_id} · ${state.entity_id}`;
  }

  entityPicker(domains, selected, placeholder, field, key, fieldName = "entity_id") {
    const states = Object.values(this._hass?.states || {}).filter((item) => domains.includes(item.entity_id.split(".")[0]));
    states.sort((a, b) => this.entityLabel(a).localeCompare(this.entityLabel(b)));
    const selectedState = states.find((item) => item.entity_id === selected);
    const display = selectedState ? this.entityLabel(selectedState) : selected;
    return `<div class="entity-picker" data-entity-picker="${escapeHtml(key)}"><input type="hidden" ${field(fieldName)} value="${escapeHtml(selected || "")}"><input class="entity-search" data-entity-search="${escapeHtml(key)}" type="search" value="${escapeHtml(display || "")}" placeholder="${escapeHtml(placeholder)}" autocomplete="off" aria-label="${escapeHtml(placeholder)}"><div class="entity-results" data-entity-results="${escapeHtml(key)}" hidden>${states.map((state) => { const label = this.entityLabel(state); return `<button type="button" data-entity-option="${escapeHtml(state.entity_id)}" data-entity-label="${escapeHtml(label)}" data-entity-terms="${escapeHtml(label.toLowerCase())}"><b>${escapeHtml(state.attributes?.friendly_name || state.entity_id)}</b><small>${escapeHtml(state.entity_id)}</small></button>`; }).join("")}</div></div>`;
  }

  widgetName(widget) {
    if (widget.type === "entity_button") return "Home control";
    if (widget.type === "sensor") return "Sensor";
    if (widget.type === "history") return "History";
    if (widget.type === "intercom") return "Intercom";
    if (widget.type === "thermostat") return "Thermostat";
    if (widget.type === "weather") return "Weather";
    if (widget.type === "camera") return "Camera";
    return "Legacy automatic controls";
  }

  iconPicker(page, widget, index, field) {
    const selected = widget.icon || "auto";
    const selectedName = CONTROL_ICONS.find(([id]) => id === selected)?.[1] || "Auto";
    const categories = [["all", "All"], ["lighting", "Lights"], ["air", "Air"], ["power", "Power"], ["covers", "Covers"], ["climate", "Climate"], ["security", "Security"], ["appliances", "Appliances"], ["cleaning", "Cleaning"], ["water", "Water"], ["media", "Media"], ["rooms", "Rooms"]];
    return `<details class="icon-picker" data-icon-category="all"><summary>Icon <b>${escapeHtml(selectedName)}</b></summary><input class="icon-search" data-icon-search="${escapeHtml(page.id)}-${index}" type="search" placeholder="Search icons…" aria-label="Search icons"><div class="icon-categories">${categories.map(([id, name]) => `<button type="button" data-icon-category-button="${id}" class="${id === "all" ? "active" : ""}">${name}</button>`).join("")}</div><div class="icon-grid" data-icon-grid="${escapeHtml(page.id)}-${index}">${CONTROL_ICONS.map(([id, name, glyph, category]) => `<label title="${escapeHtml(name)}" data-icon-name="${escapeHtml(`${name} ${id}`.toLowerCase())}" data-icon-category-option="${escapeHtml(category)}"><input type="radio" name="icon-${escapeHtml(page.id)}-${index}" value="${escapeHtml(id)}" ${field("icon")} ${selected === id ? "checked" : ""}><span>${glyph}</span><small>${escapeHtml(name)}</small></label>`).join("")}</div></details>`;
  }

  /**
   * Which of an entity's fan or swing modes the panel offers.
   *
   * The entity is asked what it has; this only narrows it. Nothing ticked
   * means the panel shows them all, which is what a thermostat nobody has
   * configured already does — so an existing panel is unchanged until
   * someone makes a choice here.
   *
   * Worth narrowing because some units report a dozen swing positions, and
   * the sheet listing them is two per row on a 480 pixel screen.
   */
  modeChoices(widget, entityId, attribute, title, field) {
    const reported = this._hass?.states?.[entityId]?.attributes?.[attribute];
    if (!Array.isArray(reported) || reported.length < 2) return "";
    const chosen = Array.isArray(widget[attribute]) ? widget[attribute] : [];
    const tooMany = reported.length > 8;
    return `<details class="mode-choices" ${tooMany && !chosen.length ? "open" : ""}><summary>${title} <b>${chosen.length ? `${chosen.length} of ${reported.length}` : `all ${reported.length}`}</b></summary>
      <div class="inline-checks">${reported.map((mode) => `<label class="check"><input type="checkbox" ${field(attribute)} data-mode-value="${escapeHtml(String(mode))}" ${chosen.includes(mode) ? "checked" : ""}> ${escapeHtml(String(mode))}</label>`).join("")}</div>
      <small>${tooMany ? `This unit reports ${reported.length} of them, which is more than the panel's sheet can show at once. ` : ""}Tick the ones worth having on a wall. None ticked shows every one the entity reports, and at most 8 can be chosen.</small></details>`;
  }

  widgetEditor(page, widget, index) {
    const field = (name) => `data-widget-field="${name}" data-page-id="${escapeHtml(page.id)}" data-widget-index="${index}"`;
    const entity = widget.entity_id || "";
    let configuration = "";
    const pickerKey = `${page.id}-${index}`;
    if (widget.type === "thermostat") configuration = `<label>Climate entity${this.entityPicker(["climate"], entity, "Search thermostats…", field, pickerKey)}</label><small>Heat, cool, auto, dry, and dual set points follow the capabilities reported by this entity.</small>${this.modeChoices(widget, entity, "fan_modes", "Fan speeds", field)}${this.modeChoices(widget, entity, "swing_modes", "Swing positions", field)}`;
    if (widget.type === "weather") configuration = `<div class="widget-fields"><label>Weather entity${this.entityPicker(["weather"], entity, "Search weather entities…", field, pickerKey)}</label><label>Daily forecast<select ${field("forecast_days")}><option value="1" ${Number(widget.forecast_days ?? 5) === 1 ? "selected" : ""}>1 day</option><option value="3" ${Number(widget.forecast_days ?? 5) === 3 ? "selected" : ""}>3 days</option><option value="5" ${Number(widget.forecast_days ?? 5) === 5 ? "selected" : ""}>5 days</option></select></label></div><label class="check"><input type="checkbox" ${field("show_hourly")} ${widget.show_hourly !== false ? "checked" : ""}> Show next-hours forecast</label>`;
    if (widget.type === "entity_button") configuration = `<label>Control entity${this.entityPicker(["light", "fan", "switch", "input_boolean", "cover"], entity, "Search lights, fans, switches, and covers…", field, pickerKey)}</label><small>The panel automatically uses the correct native control for this entity's capabilities.</small>${this.iconPicker(page, widget, index, field)}<div class="control-checks inline-checks"><label class="check"><input type="checkbox" ${field("show_timer")} ${widget.show_timer !== false ? "checked" : ""}> Show timer</label><label class="check"><input type="checkbox" ${field("show_schedule")} ${widget.show_schedule !== false ? "checked" : ""}> Show schedule</label><label class="check"><input type="checkbox" ${field("card_tap")} ${widget.card_tap === true ? "checked" : ""}> Use whole card as button</label><label class="check"><input type="checkbox" ${field("show_fan_speed")} ${widget.show_fan_speed === true ? "checked" : ""}> Show fan speed control</label></div><label>Timer presets in minutes<input ${field("timer_presets")} value="${escapeHtml((widget.timer_presets || [5, 15, 30, 60]).join(", "))}" placeholder="5, 15, 30, 60"><small>Up to four touch-friendly choices.</small></label>${entity.startsWith("cover.") ? `<div class="widget-fields"><label>Gradual open script (optional)${this.entityPicker(["script"], widget.gradual_open_script || widget.gradual_cover_script || null, "Search script entities…", field, `${pickerKey}-gradual-open`, "gradual_open_script")}</label><label>Gradual close script (optional)${this.entityPicker(["script"], widget.gradual_close_script || null, "Search script entities…", field, `${pickerKey}-gradual-close`, "gradual_close_script")}</label></div><small>Each configured script adds its matching action to curtain controls and schedules.</small>` : ""}`;
    if (widget.type === "sensor") configuration = `<label>Sensor entity${this.entityPicker(["sensor", "binary_sensor"], entity, "Search sensors…", field, pickerKey)}</label>`;
    if (widget.type === "intercom") configuration = this.editor?.layout?.intercom?.enabled
      ? `<small>Lists your other panels. Nothing to configure &mdash; the panel decides who it can call from who else is connected.</small>`
      : `<small>Intercom is switched off for this panel, so this page is not sent to it. Switch it on in general settings and the page returns &mdash; nothing here is lost.</small>`;
    if (widget.type === "history") configuration = `<label>Entity${this.entityPicker(["sensor", "binary_sensor", "climate", "number"], entity, "Search entities…", field, pickerKey)}</label><label>Span<select ${field("history_range")}><option value="6h" ${String(widget.history_range || "24h") === "6h" ? "selected" : ""}>6 hours</option><option value="24h" ${String(widget.history_range || "24h") === "24h" ? "selected" : ""}>24 hours</option><option value="7d" ${String(widget.history_range || "24h") === "7d" ? "selected" : ""}>7 days</option><option value="30d" ${String(widget.history_range || "24h") === "30d" ? "selected" : ""}>30 days</option></select><small>The span the page opens on. The panel remembers whichever you last picked on it. Needs the recorder; entities without long-term statistics fall back to raw history, which only reaches as far as your purge window.</small></label>`;
    if (widget.type === "camera") {
      const selectedCamera = widget.scrypted_bridge_id && widget.scrypted_camera_id ? `${widget.scrypted_bridge_id}|${widget.scrypted_camera_id}` : "";
      configuration = `<label>Scrypted camera<select data-camera-source ${field("scrypted_source")} required><option value="">Select camera</option>${this.scryptedDoorbells.map((item) => { const value = `${item.bridge_id}|${item.id}`; return `<option value="${escapeHtml(value)}" ${selectedCamera === value ? "selected" : ""}>${escapeHtml(item.name)}</option>`; }).join("")}</select></label><div class="inline-checks"><label class="check"><input type="checkbox" ${field("incoming_audio")} ${widget.incoming_audio ? "checked" : ""}> Play incoming audio</label></div><label class="check"><input type="checkbox" ${field("show_intercom")} ${widget.show_intercom || widget.tap_action === "intercom" ? "checked" : ""}> Show intercom button</label><small>Adds a hold-to-talk button under the picture. The page is already full-screen, so tapping it does nothing.</small></label><small>The stream starts only while this page is visible and stops immediately after swiping away.</small>`;
    }
    if (widget.type === "controls") configuration = `<div class="notice draft-note">Legacy component: it automatically selects the first four supported controls. Replace it with explicit Home control components for predictable layouts.</div>`;
    return `<article class="widget-card" data-widget-drop="${index}" data-widget-page="${escapeHtml(page.id)}"><div class="widget-drag" draggable="true" data-widget-drag="${index}" data-widget-page="${escapeHtml(page.id)}" title="Drag to reorder">⠿</div><div class="widget-body"><div class="widget-title"><div><span class="eyebrow">Component ${index + 1}</span><h4>${escapeHtml(this.widgetName(widget))}</h4></div><button class="danger" type="button" data-widget-action="delete" data-widget-index="${index}" data-widget-page="${escapeHtml(page.id)}">Remove</button></div>${configuration}<label>Custom label <span class="optional">Optional</span><input ${field("label")} maxlength="48" value="${escapeHtml(widget.label || "")}" placeholder="Use the Home Assistant name"></label></div></article>`;
  }

  pageComponentEditor(page) {
    if (!page) return "";
    const hasFullScreen = page.widgets.some((widget) => ["thermostat", "weather", "camera"].includes(widget.type));
    const controlLimitReached = page.widgets.some((widget) => ["controls", "entity_button"].includes(widget.type)) && page.widgets.length >= 4;
    const addDisabled = hasFullScreen || page.widgets.length >= 12 || controlLimitReached;
    return `<div class="scrim page-editor-scrim"><section class="dialog page-editor"><div class="component-head"><div><span class="eyebrow">Edit page</span><h2>${escapeHtml(page.title || "Untitled page")}</h2><p>Configure the native components and see an approximate panel preview.</p></div><button type="button" data-close-page-components>Done</button></div><div class="page-editor-grid"><section class="component-editor">${page.widgets.length ? `<div class="widget-list">${page.widgets.map((widget, index) => this.widgetEditor(page, widget, index)).join("")}</div>` : `<div class="empty compact"><b>This page is empty</b><span>Add its first native component below.</span></div>`}<div class="add-widget"><label>Component type<select id="new-widget-type" ${addDisabled ? "disabled" : ""}><option value="entity_button">Home control</option><option value="sensor">Sensor</option><option value="thermostat">Thermostat</option><option value="weather">Weather</option><option value="camera">Camera</option><option value="history">History</option>${this.editor?.layout?.intercom?.enabled ? '<option value="intercom">Intercom</option>' : ""}</select></label><button id="add-widget" data-widget-page="${escapeHtml(page.id)}" class="primary" type="button" ${addDisabled ? "disabled" : ""}>Add component</button></div>${hasFullScreen ? `<small>This full-screen component must remain the only component on this page.</small>` : controlLimitReached ? `<small>Controls pages support at most four controls for reliable touch targets.</small>` : ""}</section><aside class="preview-column"><span class="eyebrow">Panel preview</span><div class="panel-preview-host">${this.pagePreview(page, true)}</div><small>Approximate preview at the NSPanel Pro aspect ratio. The Android app remains the rendering authority.</small></aside></div></section></div>`;
  }

  previewEntity(widget) {
    return this._hass?.states?.[widget.entity_id] || null;
  }

  weatherGlyph(condition) {
    return ({ "clear-night": "☾", sunny: "☀", partlycloudy: "◑", cloudy: "☁", rainy: "☂", pouring: "☔", lightning: "ϟ", "lightning-rainy": "ϟ", snowy: "❄", "snowy-rainy": "❄", fog: "≋", windy: "≈", hail: "◆" })[condition] || "◌";
  }

  miniaturePagePreview(page, dark) {
    const widgets = page.widgets || [];
    const panel = (body, kind) => `<div class="panel-preview ${dark ? "dark" : "light"} miniature summary-preview"><div class="preview-page-title">${escapeHtml(page.title || "Untitled")}</div><div class="summary-body ${kind}">${body}</div><div class="preview-dots">● ○ ○</div></div>`;
    if (!widgets.length) return panel(`<div class="summary-empty">No components configured</div>`, "empty");
    const weather = widgets.find((widget) => widget.type === "weather");
    if (weather) {
      const entity = this.previewEntity(weather);
      const condition = entity?.state || "partlycloudy";
      const label = condition.replaceAll("-", " ").replace("partlycloudy", "Partly cloudy");
      const temperature = entity?.attributes?.temperature ?? "24";
      const apparent = entity?.attributes?.apparent_temperature ?? temperature;
      return panel(`<div class="summary-weather-main"><i>${this.weatherGlyph(condition)}</i><div><strong>${escapeHtml(temperature)}°</strong><b>${escapeHtml(label)}</b><small>Feels like ${escapeHtml(apparent)}°</small></div></div><div class="summary-tags"><span>${weather.show_hourly !== false ? "Hourly forecast" : "No hourly forecast"}</span><span>${Number(weather.forecast_days ?? 5)}-day forecast</span></div>`, "weather");
    }
    const thermostat = widgets.find((widget) => widget.type === "thermostat");
    if (thermostat) {
      const entity = this.previewEntity(thermostat);
      const current = entity?.attributes?.current_temperature ?? "21.5";
      const heat = entity?.attributes?.target_temp_low ?? entity?.attributes?.temperature ?? "20";
      const cool = entity?.attributes?.target_temp_high ?? entity?.attributes?.temperature ?? "24";
      return panel(`<div class="summary-climate-current"><small>Current</small><strong>${escapeHtml(current)}°</strong></div><div class="summary-climate-targets"><span><small>Heat below</small><b>${escapeHtml(heat)}°</b></span><span><small>Cool above</small><b>${escapeHtml(cool)}°</b></span></div><div class="summary-tags"><span>Heat</span><span>Cool</span><span>Auto</span><span>Dry</span></div>`, "climate");
    }
    const camera = widgets.find((widget) => widget.type === "camera");
    if (camera) {
      const entity = this.previewEntity(camera);
      const name = camera.label || entity?.attributes?.friendly_name || "Camera";
      return panel(`<div class="summary-camera"><i>▶</i><strong>${escapeHtml(name)}</strong><small>Full-page camera</small></div><div class="summary-tags"><span>${camera.incoming_audio ? "Audio on" : "Muted"}</span><span>${camera.show_intercom ? "Intercom" : "View only"}</span></div>`, "camera");
    }
    const rows = widgets.slice(0, 4).map((widget) => {
      const entity = this.previewEntity(widget);
      const name = widget.label || entity?.attributes?.friendly_name || this.widgetName(widget);
      const automatic = entity?.entity_id?.startsWith("fan.") ? "fan" : entity?.entity_id?.startsWith("cover.") ? "curtains" : entity?.entity_id?.startsWith("switch.") ? "power" : "light";
      const iconId = (widget.icon || "auto") === "auto" ? automatic : widget.icon;
      const glyph = CONTROL_ICONS.find(([id]) => id === iconId)?.[2] || "✦";
      const type = automatic === "power" ? "Switch" : automatic === "curtains" ? "Curtains" : automatic.charAt(0).toUpperCase() + automatic.slice(1);
      const capabilities = [widget.show_timer !== false && automatic !== "curtains" ? "Timer" : "", widget.show_fan_speed === true && automatic === "fan" ? "Speed" : "", automatic === "curtains" ? "Position" : ""].filter(Boolean).join(" · ");
      return `<div class="summary-control-row"><i>${glyph}</i><div><b title="${escapeHtml(name)}">${escapeHtml(name)}</b><small>${escapeHtml(type)}${capabilities ? ` · ${escapeHtml(capabilities)}` : ""}</small></div><span>${escapeHtml(entity?.state || "—")}</span></div>`;
    }).join("");
    return panel(`${rows}${widgets.length > 4 ? `<small class="summary-more">+${widgets.length - 4} more components</small>` : ""}`, "controls");
  }

  pagePreview(page, miniature = false) {
    const dark = this.editor?.draftThemeMode === "dark" || this.editor?.draftThemeMode === "inherit" && Boolean(this._hass?.themes?.darkMode);
    if (miniature) return this.miniaturePagePreview(page, dark);
    const widgets = page.widgets || [];
    const denseControls = widgets.filter((widget) => widget.type === "entity_button").length > 2;
    const widgetMarkup = widgets.length ? widgets.map((widget) => {
      const entity = this.previewEntity(widget);
      const name = widget.label || entity?.attributes?.friendly_name || this.widgetName(widget);
      if (widget.type === "thermostat") {
        const actual = entity?.attributes?.current_temperature ?? "21.5";
        const heat = entity?.attributes?.target_temp_low ?? entity?.attributes?.temperature ?? "20";
        const cool = entity?.attributes?.target_temp_high ?? entity?.attributes?.temperature ?? "24";
        return `<div class="preview-climate dual"><div class="climate-ring"><svg class="climate-dial" viewBox="0 0 200 200" aria-hidden="true"><path class="dial-track" d="M 44.85 155.15 A 78 78 0 1 1 155.15 155.15"/><path class="dial-heat" d="M 44.85 155.15 A 78 78 0 0 1 44.85 44.85"/><path class="dial-cool" d="M 155.15 44.85 A 78 78 0 0 1 155.15 155.15"/><circle class="dial-handle heat" cx="44.85" cy="44.85" r="6"/><circle class="dial-handle cool" cx="155.15" cy="44.85" r="6"/></svg><small>CURRENT</small><strong>${escapeHtml(actual)}°</strong><div class="ring-target heat">${escapeHtml(heat)}°</div><div class="ring-target cool">${escapeHtml(cool)}°</div></div><div class="target-picker"><button class="selected" type="button"><small>HEAT BELOW</small><b>${escapeHtml(heat)}°</b></button><button type="button"><small>COOL ABOVE</small><b>${escapeHtml(cool)}°</b></button></div><div class="target-stepper"><button type="button">−</button><span>Adjust heat target</span><button type="button">＋</button></div><div class="preview-modes"><b>Heat</b><b>Cool</b><b class="active">Auto</b><b>Fan</b><b>Dry</b><b>Off</b></div></div>`;
      }
      if (widget.type === "weather") {
        const condition = entity?.state || "partlycloudy";
        const temperature = entity?.attributes?.temperature ?? "24";
        const conditionLabel = condition.replaceAll("-", " ").replace("partlycloudy", "Partly cloudy");
        const hourly = ["Now", "15", "16", "17", "18"].map((hour, index) => `<span><small>${hour}</small><i>${this.weatherGlyph(index > 2 ? "partlycloudy" : condition)}</i><b>${Number(temperature) - (index > 3 ? 1 : 0)}°</b></span>`).join("");
        const dailyConditions = [condition, "sunny", "partlycloudy", "rainy", "cloudy"];
        const daily = Array.from({ length: Number(widget.forecast_days ?? 5) }, (_, index) => `<span><small>${index ? ["Sat", "Sun", "Mon", "Tue"][index - 1] : "Today"}</small><i>${this.weatherGlyph(dailyConditions[index])}</i><em>${18 + index}°</em><b>${24 - index}°</b></span>`).join("");
        return `<div class="preview-weather native-weather"><div class="native-weather-main"><div class="weather-now"><i>${this.weatherGlyph(condition)}</i><strong>${escapeHtml(temperature)}°</strong><b>${escapeHtml(conditionLabel)}</b><small>Feels like ${escapeHtml(entity?.attributes?.apparent_temperature ?? temperature)}° · ${escapeHtml(entity?.attributes?.humidity ?? "48")}%</small></div><div class="daily-forecast">${daily}</div></div>${widget.show_hourly !== false ? `<div class="hourly-forecast"><p>${escapeHtml(conditionLabel)} conditions continue.</p><div>${hourly}</div></div>` : ""}</div>`;
      }
      if (widget.type === "camera") return `<div class="preview-camera"><span>▶</span><b>${escapeHtml(name)}</b><small>${widget.incoming_audio ? "Audio on" : "Muted"} · ${widget.show_intercom ? "Intercom" : "View only"}</small></div>`;
      if (widget.type === "sensor") return `<div class="preview-tile sensor"><small>${escapeHtml(name)}</small><strong>${escapeHtml(entity?.state ?? "—")}</strong></div>`;
      const automatic = entity?.entity_id?.startsWith("fan.") ? "fan" : entity?.entity_id?.startsWith("cover.") ? "curtains" : entity?.entity_id?.startsWith("switch.") ? "power" : "light";
      const iconId = (widget.icon || "auto") === "auto" ? automatic : widget.icon;
      const glyph = CONTROL_ICONS.find(([id]) => id === iconId)?.[2] || "✦";
      const isCover = automatic === "curtains";
      const fanSpeed = automatic === "fan" && widget.show_fan_speed === true;
      const typeLabel = automatic === "power" ? "Switch" : automatic === "fan" ? "Fan" : automatic;
      const detail = isCover ? `Position · ${escapeHtml(entity?.attributes?.current_position ?? "100")}%` : fanSpeed ? `Speed · ${escapeHtml(entity?.attributes?.percentage ?? "0")}%` : escapeHtml(entity?.state || "Off");
      const primaryAction = isCover ? "Control curtains" : fanSpeed ? "Adjust speed" : "";
      const timerAction = widget.show_timer !== false && !isCover ? `<div class="control-action">◷&nbsp; Set timer</div>` : "";
      return `<div class="preview-tile control revised native-control ${denseControls ? "dense" : ""} ${widget.card_tap ? "whole-card" : ""}"><div class="control-head"><i>${glyph}</i>${isCover ? "" : `<button type="button" aria-label="Toggle"><b>${escapeHtml((entity?.state || "off").toUpperCase())}</b></button>`}</div><strong class="control-name ${name.length > 22 ? "long-name" : ""}" title="${escapeHtml(name)}">${escapeHtml(name)}</strong><small>${escapeHtml(typeLabel)}</small><div class="control-detail">${detail}</div>${primaryAction ? `<div class="control-action">${primaryAction}</div>` : timerAction}</div>`;
    }).join("") : `<div class="preview-empty">Empty page</div>`;
    return `<div class="panel-preview ${dark ? "dark" : "light"} ${miniature ? "miniature" : ""}"><div class="preview-page-title">${escapeHtml(page.title || "Untitled")}</div><div class="preview-widgets ${widgets.some((widget) => ["thermostat", "weather"].includes(widget.type)) ? "fullscreen" : ""}">${widgetMarkup}</div><div class="preview-dots">● ○ ○</div></div>`;
  }

  editorDialog() {
    const { panel, layout } = this.editor;
    const doorbell = layout.doorbell || {};
    const selectedScrypted = doorbell.scrypted_bridge_id && doorbell.scrypted_doorbell_id
      ? `${doorbell.scrypted_bridge_id}|${doorbell.scrypted_doorbell_id}` : "";
    const online = !panel.revoked && panel.last_seen && Date.now() - new Date(panel.last_seen).getTime() < 45000;
    const tab = this.workspaceTab;
    return `<main class="workspace-page"><section class="workspace"><div class="editor-head"><div><button class="workspace-back" data-close-editor>← All panels</button><span class="eyebrow">Panel workspace</span><div class="workspace-title"><h2>${escapeHtml(panel.name)}</h2><span class="status ${online ? "online" : "waiting"}">${panel.revoked ? "Revoked" : online ? "Online" : "Offline"}</span></div><p class="device-id">${escapeHtml(panel.device_id)}</p></div></div>${this.error ? `<div class="notice error">${escapeHtml(this.error)}</div>` : ""}
      <nav class="workspace-tabs" aria-label="Panel configuration">
        ${[["general","General"],["pages","Pages"],["doorbell","Doorbell"],["diagnostics","Diagnostics"],["advanced","Advanced"]].map(([id,label]) => `<button type="button" data-workspace-tab="${id}" class="${tab === id ? "active" : ""}">${label}</button>`).join("")}
      </nav>
      <section class="workspace-panel" data-workspace-panel="general" ${tab === "general" ? "" : "hidden"}>
        <div class="workspace-intro"><h3>Panel identity</h3><p>Give this panel a name that describes its room or purpose. Its stable device ID never changes.</p></div>
        <form id="panel-general" class="settings-card">
          <label>Panel name<input name="panel_name" maxlength="64" required value="${escapeHtml(panel.name)}" placeholder="Living room"></label>
          <label>Panel theme<select name="theme_mode"><option value="inherit" ${this.editor.draftThemeMode === "inherit" ? "selected" : ""}>Auto · inherit Home Assistant</option><option value="light" ${this.editor.draftThemeMode === "light" ? "selected" : ""}>Light</option><option value="dark" ${this.editor.draftThemeMode === "dark" ? "selected" : ""}>Dark</option></select><small>Auto resolves the active Home Assistant light/dark appearance when the dashboard is published. Explicit Light or Dark stays fixed.</small></label>
          <fieldset class="dashboard-behavior"><legend>Dashboard behavior</legend><label>Return to first page after<input name="return_seconds" type="number" min="0" max="3600" value="${Number(layout.default_page_return_seconds ?? 60)}"><small>Seconds; use 0 to disable automatic return.</small></label><label class="check"><input name="keep_screen_on" type="checkbox" ${layout.keep_screen_on ? "checked" : ""}> Keep display on while dashboard is open</label><small>When disabled, the panel follows its Android display timeout.</small><label class="check"><input name="wake_on_approach" type="checkbox" ${layout.wake_on_approach ? "checked" : ""}> Wake the display when someone approaches</label><small>Uses the panel's proximity sensor. Ignored while the display is set to stay on.</small><label>Wake sensitivity<select name="wake_sensitivity"><option value="high" ${String(layout.wake_sensitivity || "medium") === "high" ? "selected" : ""}>High &middot; from across the room</option><option value="medium" ${String(layout.wake_sensitivity || "medium") === "medium" ? "selected" : ""}>Medium</option><option value="low" ${String(layout.wake_sensitivity || "medium") === "low" ? "selected" : ""}>Low &middot; only up close</option></select><small>The sensor measures reflected light, so a lighter wall or a shelf in front of the panel reads closer. Lower the sensitivity if it wakes on its own.</small></label><label class="check"><input name="show_clock" type="checkbox" ${layout.show_clock !== false ? "checked" : ""}> Show Home Assistant time</label><label class="check"><input name="show_mic_indicator" type="checkbox" ${layout.show_mic_indicator !== false ? "checked" : ""}> Show microphone privacy indicator</label><label>Keep microphone indicator green after use<input name="mic_indicator_linger_seconds" type="number" min="0" max="60" value="${Number(layout.mic_indicator_linger_seconds ?? 15)}"><small>Seconds; use 0 to show green only during active capture.</small></label></fieldset>
          <fieldset class="system-ui"><legend>Android system UI</legend><label>Navigation bar<select name="nav_bar_mode"><option value="listener" ${String(layout.nav_bar_mode || "listener") === "listener" ? "selected" : ""}>Hide, and re-hide when Android shows it</option><option value="immersive" ${String(layout.nav_bar_mode || "listener") === "immersive" ? "selected" : ""}>Suppress entirely (recommended)</option><option value="visible" ${String(layout.nav_bar_mode || "listener") === "visible" ? "selected" : ""}>Leave visible</option></select><small>Re-hiding lets the bar appear for a moment whenever a long press or an edge swipe summons it. Suppressing it stops Android summoning it at all.</small></label><label class="check"><input name="hide_accessibility_button" type="checkbox" ${layout.hide_accessibility_button ? "checked" : ""}> Hide the panel's floating back button</label><small>Suppressing the navigation bar and hiding the back button both need a system permission the updater add-on grants when it installs the app. If the panel has not been updated since this setting appeared, update it once and these will take effect.</small></fieldset>
          <fieldset class="system-ui"><legend>Intercom</legend><label class="check"><input name="intercom_enabled" type="checkbox" ${layout.intercom?.enabled ? "checked" : ""}> Take part in the panel intercom</label><small>Two-way audio with your other panels, no camera. A panel with this off is not listed on other panels, cannot be called, and will not ring &mdash; and its intercom pages are not sent to it.</small>
            ${soundField("Ring sound", "intercom_ring", layout.intercom?.ring, "intercom_ring_volume", layout.intercom?.ring_volume)}
            <label class="check"><input name="intercom_noise_suppression" type="checkbox" ${layout.intercom?.noise_suppression !== false ? "checked" : ""}> Noise suppression</label>
            <label class="check"><input name="intercom_auto_gain" type="checkbox" ${layout.intercom?.auto_gain !== false ? "checked" : ""}> Automatic gain</label>
            <small>This panel has no audio effects of its own, so both are done in software by WebRTC. Turning them off is worth trying only if a call sounds processed or the far end cuts in and out.</small></fieldset>
          <label>Stable device ID<input value="${escapeHtml(panel.device_id)}" readonly></label>
          <dl><div><dt>Connection</dt><dd>${panel.revoked ? "Revoked" : online ? "Online" : "Offline"}</dd></div><div><dt>Registered</dt><dd>${formatDate(panel.created_at)}</dd></div><div><dt>App version</dt><dd>${escapeHtml(panel.app_version || "—")}</dd></div></dl>
          <div class="actions"><button class="primary" type="submit" ${this.busy ? "disabled" : ""}>Save general settings</button><button type="button" data-restart-panel ${this.busy ? "disabled" : ""}>Restart app</button><button type="button" data-reboot-panel ${this.busy ? "disabled" : ""}>Reboot panel</button></div>
        </form>
      </section>
      <form id="layout-editor" class="workspace-layout-form">
        <section class="workspace-panel" data-workspace-panel="pages" ${tab === "pages" ? "" : "hidden"}>
          <div class="workspace-intro"><h3>Pages</h3><p>Create and arrange the screens people reach by swiping on this panel. Changes stay in this workspace until you publish.</p></div>
          ${this.editor.draftPages.length ? `<div class="page-list visual-page-list">${this.editor.draftPages.map((page, index) => {
            const components = (page.widgets || []).map((widget) => widget.type.replace("entity_button", "control"));
            return `<article class="page-card visual-page-card ${this.editor.activePageId === page.id ? "active" : ""}" data-page-drop="${index}"><div class="page-card-top"><div class="page-order" data-page-drag="${index}" draggable="true" title="Drag to reorder" aria-label="Drag ${escapeHtml(page.title)} to reorder"><span>⠿</span><small>${index + 1}</small></div><div class="page-heading"><b>${escapeHtml(page.title)}</b><small>${index === 0 ? "First screen" : `Screen ${index + 1}`}</small></div></div>${this.pagePreview(page, true)}<label>Page name<input data-page-title="${index}" maxlength="48" required value="${escapeHtml(page.title)}"></label><div class="page-meta"><span>${components.length ? `${components.length} component${components.length === 1 ? "" : "s"}: ${escapeHtml([...new Set(components)].join(", "))}` : "No components yet"}</span></div><div class="page-actions"><button class="primary" type="button" data-edit-page="${escapeHtml(page.id)}">Edit page</button><button type="button" data-page-action="duplicate" data-page-index="${index}" ${this.editor.draftPages.length >= 8 ? "disabled" : ""}>Duplicate</button><button class="danger" type="button" data-page-action="delete" data-page-index="${index}">Delete</button></div></article>`;
          }).join("")}</div>` : `<div class="unconfigured-notice"><span class="device-icon">＋</span><div><h3>No pages configured</h3><p>This panel is showing its native setup screen. Create its first page below.</p></div></div>`}
          ${this.pageComponentEditor(this.editor.draftPages.find((page) => page.id === this.editor.activePageId))}
          <div class="add-page"><label>New page name<input id="new-page-title" maxlength="48" placeholder="For example: Climate or Lights" ${this.editor.draftPages.length >= 8 ? "disabled" : ""}></label><button id="add-page" type="button" class="primary" ${this.editor.draftPages.length >= 8 ? "disabled" : ""}>Add page</button></div>
          ${this.editor.draftPages.some((page) => !(page.widgets || []).length) ? `<div class="notice draft-note">Pages without components remain drafts and cannot be published yet.</div>` : ""}
          <div class="actions"><button data-close-editor type="button">Cancel</button><button class="primary" type="submit" ${this.busy ? "disabled" : ""}>Publish to panel</button></div>
        </section>
        <section class="workspace-panel" data-workspace-panel="doorbell" ${tab === "doorbell" ? "" : "hidden"}>
          <div class="workspace-intro"><h3>Doorbell</h3><p>Choose the visitor trigger, video source, and intercom behavior for this panel.</p></div>
          <fieldset><legend>Doorbell configuration</legend>
            <label class="check"><input name="doorbell_enabled" type="checkbox" ${doorbell.enabled ? "checked" : ""}> Open this panel on visitor event</label>
            <label>Visitor/button entity<select name="doorbell_trigger">${this.entityOptions(["binary_sensor"], doorbell.trigger_entity_id || "", "Select trigger entity")}</select></label>
            ${(this.scrypted.paired || []).length ? `<label>Scrypted doorbell<select name="scrypted_doorbell"><option value="">Manual configuration</option>${this.scryptedDoorbells.map((item) => { const value = `${item.bridge_id}|${item.id}`; return `<option value="${escapeHtml(value)}" ${value === selectedScrypted ? "selected" : ""}>${escapeHtml(item.name)}${item.intercom ? " · intercom" : ""}</option>`; }).join("")}</select><small>Selecting a device fills video and talkback credentials securely when you publish.</small></label>` : ""}
            <details><summary>Advanced manual media settings</summary>
            <label>Media URL<input name="stream_base_url" type="text" inputmode="url" value="${escapeHtml(doorbell.stream_base_url || "rtsp://192.0.2.76:46211/0123456789abcdef")}" placeholder="rtsp://scrypted-host:port/stream"><small>Use the complete Scrypted rebroadcast RTSP URL, including the rtsp:// scheme.</small></label>
            <label>Stream name<input name="stream_name" pattern="[A-Za-z0-9_-]+" value="${escapeHtml(doorbell.stream_name || "doorbell_sub")}"><small>Used only when Media URL points to go2rtc rather than a complete RTSP URL.</small></label>
            <label>Talkback URL<input name="talkback_url" type="text" inputmode="url" value="${escapeHtml(doorbell.talkback_url || "")}" placeholder="http://scrypted-host:11081/talk/device-id"><small>Copy the streaming endpoint from the NSPanel Talkback Scrypted extension. Do not use this as the Media URL.</small></label>
            <label>Talkback access key<input name="talkback_key" type="text" value="${escapeHtml(doorbell.talkback_key || "")}" autocomplete="off"><small>Copy the access key from the Scrypted extension.</small></label>
            </details>
            <label>Close after<input name="auto_close_seconds" type="number" min="10" max="300" value="${Number(doorbell.auto_close_ms || 60000) / 1000}"><small>10–300 seconds.</small></label>
            <label class="check"><input name="talk_extend_enabled" type="checkbox" ${doorbell.talk_extend_enabled !== false ? "checked" : ""}> Extend timeout after hold-to-talk</label>
            <label>Talk extension<input name="talk_extend_seconds" type="number" min="5" max="60" value="${Number(doorbell.talk_extend_ms || 15000) / 1000}"><small>Add 5–60 seconds to the remaining time after each completed hold-to-talk interaction.</small></label>
            <label class="check"><input name="quiet_mode" type="checkbox" ${doorbell.quiet_mode ? "checked" : ""}> Start with incoming audio muted</label>
            ${soundField("Chime", "chime", doorbell.chime, "chime_volume", doorbell.chime_volume)}
            <small>The chime does not play while incoming audio is muted above.</small>
            <label>Talkback microphone gain<input name="talkback_gain" type="number" min="50" max="300" value="${Number(doorbell.talkback_gain ?? 100)}"> %</label>
            <small>Android does not let an app set the microphone's gain, so this scales the captured sound instead. Above about 200% a raised voice will clip.</small>
          </fieldset>
          <div class="actions"><button data-test-doorbell="${escapeHtml(panel.panel_id)}" type="button" ${this.busy || panel.revoked ? "disabled" : ""}>Test doorbell</button><button data-close-editor type="button">Cancel</button><button class="primary" type="submit" ${this.busy ? "disabled" : ""}>Publish to panel</button></div>
        </section>
      </form>
      <section class="workspace-panel" data-workspace-panel="diagnostics" ${tab === "diagnostics" ? "" : "hidden"}>
        <div class="workspace-intro"><h3>Diagnostics</h3><p>Download the latest bounded, sanitized health report uploaded by this panel.</p></div>
        <div class="settings-card"><dl><div><dt>Last seen</dt><dd>${formatDate(panel.last_seen)}</dd></div><div><dt>Reported layout</dt><dd>${escapeHtml(panel.reported_layout_revision || "—")}</dd></div></dl><div class="actions left"><button data-diagnostics="${escapeHtml(panel.panel_id)}" type="button" ${this.busy || panel.revoked ? "disabled" : ""}>Download diagnostics</button></div></div>
      </section>
      <section class="workspace-panel" data-workspace-panel="advanced" ${tab === "advanced" ? "" : "hidden"}>
        <div class="workspace-intro"><h3>Advanced</h3><p>Destructive panel management actions live here to keep everyday configuration safe.</p></div>
        <div class="settings-card danger-zone"><h3>Remove this panel</h3><p>Unpairs the app, erases its saved HA credentials, and removes this panel from Home Assistant.</p><div class="actions left"><button class="danger" data-revoke="${escapeHtml(panel.panel_id)}" type="button" ${this.busy || panel.revoked ? "disabled" : ""}>Remove & unpair</button></div></div>
      </section>
    </section></main>`;
  }
}

/** "4m", "2h", "3d" — short enough for a metric cell, exact enough to act on. */
const sinceLabel = (iso) => {
  const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
};

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const formatDate = (value) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";

const STYLES = `
/* ============================================================
   SLAB ADMIN — complete stylesheet for the NSPanel Companion
   Home Assistant add-on UI.

   One file. Paste the whole thing into the STYLES template
   literal in frontend/nspanel-companion-panel.js (shadow DOM),
   or ship it as a stylesheet and adopt it:

     const sheet = new CSSStyleSheet();
     sheet.replaceSync(SLAB_ADMIN_CSS);
     this.shadowRoot.adoptedStyleSheets = [sheet];

   Contents
     1  Tokens — colour, geometry, type
     2  Reset and base
     3  Typography roles
     4  Controls — buttons, fields, toggles, checks
     5  Bands, rows, lists
     6  Status pills and notices
     7  Chrome — app bar, breadcrumb, tabs, save bar
     8  Home — status strip, panel grid, empty state
     9  Integrations route
    10  Workspace — general, doorbell, diagnostics
    11  Page editor — rail, board, inspector
    12  Pickers — entity, icon, add component
    13  Dialogs
    14  Utilities and responsive

   Rules this encodes: separation is a 1px rule, not a gap;
   state is a fill, never an outline colour; identifiers are
   monospace; destructive is red and on the right; every
   interactive element has a visible focus ring.
   ============================================================ */


/* 1 ── TOKENS ─────────────────────────────────────────────── */

:host {
  /* surface */
  --canvas:#0E1012;
  --surface:#14171A;
  --surface-raised:#1D2126;
  --accent-wash:#2A1A11;

  /* ink */
  --ink:#F2F5F7;
  --muted:#8A9299;
  --disabled:#4A5158;
  --line:#23282D;

  /* accent and status */
  --accent:#F36D21;
  --accent-ink:#FF9455;   /* accent as text — never the raw accent on a light field */
  --on-accent:#0E1012;
  --danger:#D24A3F;
  --ok:#34C759;
  --pending:#FF9500;
  --ok-wash:#12301E;
  --danger-wash:#2E1512;

  /* geometry */
  --radius:2px;
  --row:40px;
  --row-tall:56px;
  --control:36px;
  --control-sm:28px;
  --app-bar:56px;
  --tab-bar:44px;
  --pane-inset:20px;
  --page-inset:32px;
  --rail:232px;
  --inspector:340px;
  --content-max:1180px;
  --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:20px; --s6:32px;

  /* type */
  --font:Barlow,system-ui,-apple-system,sans-serif;
  --mono:'Roboto Mono',ui-monospace,SFMono-Regular,monospace;

  display:block;
  min-height:100%;
  background:var(--canvas);
  color:var(--ink);
  font-family:var(--font);
  font-size:14px;
  font-variant-numeric:tabular-nums;
}

:host(.light) {
  --canvas:#F4F5F3;
  --surface:#FFFFFF;
  --surface-raised:#ECEEEA;
  --accent-wash:#FFEBE0;
  --ink:#14171A;
  --muted:#6E7570;
  --disabled:#A8ADA6;
  --line:#D9DCD8;
  --accent-ink:#C9560F;
  --on-accent:#FFFFFF;
  --danger:#C0392B;
  --ok-wash:#DFF7EB;
  --ok:#147A4D;
  --danger-wash:#FDE7E4;
}


/* 2 ── RESET AND BASE ─────────────────────────────────────── */

*, *::before, *::after { box-sizing:border-box; }
h1,h2,h3,h4,p,dl,dd,figure { margin:0; }
a { color:var(--accent-ink); text-decoration:none; }
a:hover { text-decoration:underline; }
code, .mono, .id { font:500 12px/1.4 var(--mono); }
hr { border:0; border-top:1px solid var(--line); margin:0; }
::-webkit-scrollbar { width:10px; height:10px; }
::-webkit-scrollbar-thumb { background:var(--surface-raised); }
::-webkit-scrollbar-track { background:transparent; }

main { max-width:var(--content-max); margin:0 auto; padding:var(--page-inset); }
main.wide { max-width:none; }


/* 3 ── TYPOGRAPHY ROLES ───────────────────────────────────── */

.t-page   { font:700 30px/1.1 var(--font); }
.t-title  { font:700 22px/1.2 var(--font); }
.t-sub    { font:600 17px/1.3 var(--font); }
.t-read   { font:700 20px/1.2 var(--font); }
.t-body   { font:400 14px/1.5 var(--font); }
.t-small  { font:400 13px/1.5 var(--font); color:var(--muted); }
.t-control{ font:600 14px/1 var(--font); }
.t-label  { font:600 11px/1 var(--font); letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }
.t-micro  { font:400 11px/1.4 var(--font); color:var(--muted); }
.t-mono   { font:500 12px/1.4 var(--mono); }

.t-label.accent { color:var(--accent); }
.t-label.danger { color:var(--danger); }
.section-label { font:600 11px/1 var(--font); letter-spacing:.12em; text-transform:uppercase; color:var(--muted); margin-bottom:10px; display:block; }
.section-label + .band { margin-top:0; }
.stack { display:flex; flex-direction:column; gap:26px; }


/* 4 ── CONTROLS ───────────────────────────────────────────── */

button {
  height:var(--control); padding:0 var(--s4);
  display:inline-flex; align-items:center; justify-content:center; gap:var(--s2);
  border:1px solid var(--line); border-radius:var(--radius);
  background:var(--surface-raised); color:var(--ink);
  font:600 14px/1 var(--font); cursor:pointer;
  white-space:nowrap;
}
button:hover { background:var(--line); }
button:active { transform:translateY(1px); }
button.primary { background:var(--accent); border-color:var(--accent); color:var(--on-accent); }
button.primary:hover { filter:brightness(1.08); background:var(--accent); }
button.danger { background:var(--danger); border-color:var(--danger); color:var(--on-accent); font-weight:700; }
button.danger.quiet { background:transparent; border-color:var(--line); color:var(--danger); font-weight:600; }
button.quiet { background:transparent; border-color:transparent; color:var(--muted); }
button.quiet:hover { background:var(--surface-raised); color:var(--ink); }
button.small { height:var(--control-sm); padding:0 var(--s3); font-size:13px; }
button.icon { width:var(--control); padding:0; font-size:16px; }
button:disabled, button[disabled] {
  background:var(--surface); color:var(--disabled); border-color:var(--line);
  cursor:default; transform:none; filter:none;
}

input, select, textarea {
  height:var(--control); width:100%; padding:0 var(--s3);
  border:1px solid var(--line); border-radius:var(--radius);
  background:var(--canvas); color:var(--ink);
  font:400 14px/1 var(--font);
}
textarea { height:auto; padding:10px var(--s3); line-height:1.5; resize:vertical; }
input::placeholder { color:var(--disabled); }
input[readonly] { color:var(--muted); }
input.mono, select.mono, .pair-code { font:500 13px/1 var(--mono); }
.pair-code.entry { height:64px; font-size:30px; letter-spacing:.3em; text-indent:.3em; text-align:center; }
select { appearance:none; padding-right:30px; background-image:linear-gradient(transparent,transparent); }
.select-wrap { position:relative; }
.select-wrap::after { content:'▾'; position:absolute; right:12px; top:50%; transform:translateY(-50%); color:var(--muted); pointer-events:none; }

:is(button,input,select,textarea,a,[tabindex],.slot,.row):focus-visible {
  outline:2px solid var(--accent); outline-offset:1px; border-color:transparent;
}

/* toggle */
.toggle { flex:none; width:36px; height:20px; border:0; padding:0; border-radius:999px; background:var(--line); position:relative; cursor:pointer; }
.toggle::after { content:''; position:absolute; left:2px; top:2px; width:16px; height:16px; border-radius:50%; background:var(--muted); transition:left .12s, background .12s; }
.toggle[aria-checked="true"] { background:var(--accent); }
.toggle[aria-checked="true"]::after { left:18px; background:var(--on-accent); }
.toggle:hover { background:var(--disabled); }
.toggle[aria-checked="true"]:hover { background:var(--accent); filter:brightness(1.08); }

/* check and radio */
.check { display:flex; align-items:center; gap:10px; font:400 14px/1 var(--font); cursor:pointer; }
.check input[type=checkbox], .check input[type=radio] { appearance:none; flex:none; width:16px; height:16px; margin:0; border:1px solid var(--disabled); border-radius:var(--radius); background:transparent; cursor:pointer; }
.check input[type=radio] { border-radius:50%; }
.check input[type=checkbox]:checked { background:var(--accent); border-color:var(--accent); }
.check input[type=checkbox]:checked::after { content:'✓'; display:block; color:var(--on-accent); font:700 12px/14px var(--font); text-align:center; }
.check input[type=radio]:checked { border:4px solid var(--accent); }

/* field group: label above control, hint below */
.field { display:flex; flex-direction:column; gap:6px; }
.field > .label { font:600 12px/1 var(--font); color:var(--muted); }
.field > .hint { font:400 12px/1.5 var(--font); color:var(--muted); }
.field .optional { font-weight:400; color:var(--disabled); }
.preset-row { display:flex; gap:var(--s2); }
.preset-row input { text-align:center; font:500 13px/1 var(--mono); }


/* 5 ── BANDS, ROWS, LISTS ─────────────────────────────────── */

.band { border:1px solid var(--line); background:transparent; }
.band > * + * { border-top:1px solid var(--line); }
.band.flush { border-left:0; border-right:0; }

.row { min-height:var(--row); display:flex; align-items:center; gap:var(--s3); padding:0 var(--s4); }
.row.tall { min-height:var(--row-tall); }
.row.stacked { flex-direction:column; align-items:stretch; justify-content:center; gap:2px; padding-top:10px; padding-bottom:10px; }
.row > .grow { flex:1; min-width:0; }
.row .sub { font:400 13px/1.4 var(--font); color:var(--muted); margin-top:2px; }
.row.interactive { cursor:pointer; }
.row.interactive:hover { background:var(--surface-raised); }
.row.selected { background:var(--accent-wash); box-shadow:inset 3px 0 0 var(--accent); }
.row.selected .index { color:var(--accent); }
.row .index { font:500 12px/1 var(--mono); color:var(--muted); flex:none; }
.row .drag { color:var(--disabled); cursor:grab; font-size:14px; }
.row .drag:active { cursor:grabbing; }
.row.dragging { opacity:.45; }
.row.drop-target { box-shadow:inset 0 -2px 0 var(--accent); }
.row .chev { color:var(--muted); }

/* key/value table */
.kv { border:1px solid var(--line); }
.kv > div { min-height:var(--row); display:flex; align-items:center; gap:var(--s4); padding:0 var(--s4); font-size:14px; }
.kv > div + div { border-top:1px solid var(--line); }
.kv dt, .kv .k { flex:1; color:var(--muted); }
.kv dd, .kv .v { margin:0; text-align:right; overflow-wrap:anywhere; }


/* 6 ── STATUS AND NOTICES ─────────────────────────────────── */

.status { flex:none; padding:5px 10px; border-radius:999px; font:600 11px/1 var(--font); letter-spacing:.12em; text-transform:uppercase; }
.status.online   { background:var(--ok-wash); color:var(--ok); }
.status.waiting  { background:var(--accent-wash); color:var(--pending); }
.status.offline  { background:var(--surface-raised); color:var(--muted); }
.status.error    { background:var(--danger-wash); color:var(--danger); }

.dot { flex:none; width:8px; height:8px; border-radius:50%; background:var(--disabled); }
.dot.on { background:var(--ok); }
.dot.warn { background:var(--pending); }
.dot.off { background:var(--disabled); }

.notice { padding:12px var(--s4); border:1px solid var(--line); background:var(--accent-wash); font:400 13px/1.5 var(--font); }
.notice.error { background:var(--danger-wash); border-color:var(--danger); color:var(--ink); }
.notice.plain { background:var(--surface); }

.empty { border:1px solid var(--line); padding:56px var(--page-inset); display:flex; flex-direction:column; align-items:center; gap:10px; text-align:center; }
.empty .glyph { width:40px; height:40px; display:grid; place-items:center; border-radius:var(--radius); background:var(--accent-wash); color:var(--accent); font-size:20px; }
.empty p { max-width:340px; font:400 14px/1.5 var(--font); color:var(--muted); }

.device-icon { flex:none; width:40px; height:40px; display:grid; place-items:center; border-radius:var(--radius); background:var(--surface-raised); color:var(--muted); font-size:20px; }
.device-icon.active { background:var(--accent-wash); color:var(--accent); }
.device-icon.small { width:32px; height:32px; font-size:16px; }


/* 7 ── CHROME ─────────────────────────────────────────────── */

.app-bar { height:var(--app-bar); display:flex; align-items:center; gap:var(--s3); padding:0 var(--page-inset); border-bottom:1px solid var(--line); }
.app-bar .mark { width:8px; height:8px; background:var(--accent); flex:none; }
.app-bar .spacer, .save-bar .spacer { flex:1; }

.crumbs { display:flex; align-items:center; gap:var(--s2); font:400 13px/1 var(--font); color:var(--muted); }
.crumbs .sep { color:var(--disabled); }
.crumbs .here { font:700 15px/1 var(--font); color:var(--ink); }

.tabs { height:var(--tab-bar); display:flex; padding:0 var(--page-inset); border-bottom:1px solid var(--line); overflow-x:auto; }
.tabs button { height:100%; border:0; border-radius:0; background:transparent; color:var(--muted); padding:0 var(--s4); }
.tabs button:hover { background:transparent; color:var(--ink); }
.tabs button.active { color:var(--ink); box-shadow:inset 0 -2px 0 var(--accent); }

/* the only thing that writes */
.save-state { font:400 13px/1 var(--font); color:var(--muted); }
.save-state.dirty { color:var(--accent-ink); }


/* 8 ── HOME ───────────────────────────────────────────────── */

.integration-strip { display:flex; height:48px; border:1px solid var(--line); margin-bottom:24px; cursor:pointer; }
.integration-strip > div { display:flex; align-items:center; gap:10px; padding:0 var(--s4); flex:1; }
.integration-strip > div + div { border-left:1px solid var(--line); }
.integration-strip .name { font:600 14px/1 var(--font); }
.integration-strip .state { font:400 13px/1 var(--font); color:var(--muted); }
.integration-strip .go { flex:0 0 160px; justify-content:flex-end; font:600 14px/1 var(--font); color:var(--accent-ink); }

.page-head { display:flex; align-items:flex-end; gap:var(--s5); margin-bottom:var(--s5); }
.page-head p { font:400 14px/1.5 var(--font); color:var(--muted); margin-top:4px; }
.page-head .spacer { flex:1; }

.panel-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(420px,1fr)); border:1px solid var(--line); }
.panel-grid > .panel-card { border-left:1px solid var(--line); border-top:1px solid var(--line); margin:-1px 0 0 -1px; }
.panel-card { padding:var(--pane-inset); display:flex; flex-direction:column; gap:var(--s4); min-height:200px; }
.panel-card .identity { display:flex; align-items:flex-start; gap:14px; }
.panel-card .identity .grow { flex:1; min-width:0; }
.panel-card .identity .id { color:var(--muted); margin-top:3px; }
.panel-card .metrics { display:grid; grid-template-columns:repeat(3,1fr); border-top:1px solid var(--line); padding-top:14px; }
.panel-card .metrics b { display:block; font:700 20px/1 var(--font); margin-top:4px; }
.panel-card .actions { display:flex; gap:var(--s2); margin-top:auto; }
.panel-card .warn-strip { margin:0 calc(var(--pane-inset) * -1); padding:14px var(--pane-inset); background:var(--accent-wash); border-top:1px solid var(--line); font:400 14px/1.5 var(--font); }


/* 9 ── INTEGRATIONS ROUTE ─────────────────────────────────── */

.service { border:1px solid var(--line); }
.service + .service { border-top:0; }
.service > * + * { border-top:1px solid var(--line); }
.service .head { min-height:var(--row-tall); display:flex; align-items:center; gap:14px; padding:0 var(--pane-inset); }
.service .head .name { font:600 17px/1 var(--font); }
.service .head .what { font:400 13px/1 var(--font); color:var(--muted); }
.service .head .spacer { flex:1; }
.service.inactive .head .name { color:var(--muted); }
.service .foot { min-height:48px; display:flex; align-items:center; padding:0 var(--pane-inset); font:400 13px/1.5 var(--font); color:var(--muted); }
.service .detail { min-height:var(--row-tall); display:flex; align-items:center; gap:14px; padding:12px var(--pane-inset); }

.adb-row { min-height:64px; display:flex; align-items:center; gap:14px; padding:0 var(--pane-inset); }
.adb-row + .adb-row { border-top:1px solid var(--line); }
.adb-row .grow { flex:1; min-width:0; }
.adb-row .spec { font:500 12px/1.4 var(--mono); color:var(--muted); margin-top:2px; }


/* 10 ── WORKSPACE ─────────────────────────────────────────── */

.workspace-grid { padding:var(--page-inset); display:grid; grid-template-columns:minmax(0,1fr) var(--inspector); gap:var(--page-inset); align-items:start; }
.workspace-grid.single { grid-template-columns:minmax(0,1fr); }
.setting-row { min-height:var(--row-tall); display:flex; align-items:center; gap:var(--s4); padding:10px var(--s4); }
.setting-row .grow { flex:1; min-width:0; }
.setting-row .sub { font:400 13px/1.4 var(--font); color:var(--muted); margin-top:2px; }
.setting-row > input, .setting-row > select, .setting-row > .select-wrap { flex:0 0 220px; }
.setting-row > input.narrow { flex-basis:140px; }
.setting-row.link { min-height:48px; font:400 13px/1 var(--font); color:var(--muted); }
.setting-row.link a { margin-left:auto; font:600 14px/1 var(--font); }

/* doorbell: disclosure for manual media */
.disclosure { min-height:48px; display:flex; align-items:center; gap:10px; padding:0 var(--s4); color:var(--muted); font:600 14px/1 var(--font); cursor:pointer; }
.disclosure .aside { font-weight:400; font-size:13px; color:var(--disabled); }
.disclosure[open] { color:var(--ink); }

/* diagnostics: danger zone is the last band, under a rule */
.danger-zone { margin-top:var(--page-inset); padding-top:26px; border-top:1px solid var(--line); }
.danger-zone .section-label { color:var(--danger); }
.danger-zone .row { min-height:64px; }

.event-log > div { display:flex; gap:var(--s3); padding:12px var(--s4); font:400 13px/1.5 var(--font); }
.event-log > div + div { border-top:1px solid var(--line); }
.event-log time { flex:none; font:500 12px/1.5 var(--mono); color:var(--muted); }
.event-log .warn { color:var(--pending); }


/* 11 ── PAGE EDITOR ───────────────────────────────────────── */

.editor { display:grid; grid-template-columns:var(--rail) minmax(0,1fr) var(--inspector); min-height:calc(100vh - var(--app-bar)); }

.editor > .rail { border-right:1px solid var(--line); display:flex; flex-direction:column; }
.rail .rail-head { height:var(--tab-bar); display:flex; align-items:center; padding:0 var(--s4); border-bottom:1px solid var(--line); }
.rail .page-item { min-height:var(--row-tall); display:flex; align-items:center; gap:var(--s3); padding:0 var(--s4); border-bottom:1px solid var(--line); cursor:pointer; }
.rail .page-item:hover { background:var(--surface-raised); }
.rail .page-item.selected { background:var(--accent-wash); box-shadow:inset 3px 0 0 var(--accent); }
.rail .page-item .grow { flex:1; min-width:0; }
.rail .page-item .name { font:600 14px/1.2 var(--font); }
.rail .page-item .meta { font:400 12px/1.2 var(--font); color:var(--muted); margin-top:2px; }
.rail .page-item.selected .meta { color:var(--accent); }
.rail .add-page { min-height:var(--row-tall); display:flex; align-items:center; gap:10px; padding:0 var(--s4); border-bottom:1px solid var(--line); color:var(--muted); font:600 14px/1 var(--font); cursor:pointer; }
.rail .rail-foot { margin-top:auto; padding:var(--s4); border-top:1px solid var(--line); font:400 12px/1.5 var(--font); color:var(--muted); }

.editor > .stage { background:var(--surface); display:flex; flex-direction:column; align-items:center; padding:28px 24px; overflow:auto; }
.stage .stage-head, .stage .stage-foot { width:520px; display:flex; align-items:center; gap:10px; }
.stage .stage-head { margin-bottom:14px; }
.stage .stage-foot { margin-top:14px; font:400 12px/1.4 var(--font); color:var(--muted); }
.stage .stage-foot .grow { flex:1; }

/* the board is a wireframe, never a render of the panel */
.board { width:520px; height:520px; background:var(--canvas); border:1px solid var(--line); padding:var(--pane-inset); display:flex; flex-direction:column; gap:14px; font-family:var(--mono); }
.board .board-status { display:flex; align-items:center; gap:10px; padding-bottom:12px; border-bottom:1px solid var(--line); font:500 10px/1 var(--mono); letter-spacing:.1em; color:var(--disabled); }
.board .pager { display:flex; gap:4px; margin-left:auto; }
.board .pager i { width:22px; height:3px; background:var(--line); }
.board .pager i.on { background:var(--accent); }
.board .slots { flex:1; display:grid; grid-template-columns:1fr 1fr; grid-auto-rows:1fr; gap:12px; }
.board .slots.full { grid-template-columns:1fr; grid-auto-rows:1fr; }

.slot { position:relative; border:1px solid var(--line); padding:14px; display:flex; flex-direction:column; cursor:pointer; overflow:hidden; }
.slot:hover { border-color:var(--muted); }
.slot .kind { font:400 10px/1 var(--mono); letter-spacing:.1em; color:var(--disabled); }
.slot .name { font:400 13px/1.3 var(--mono); color:var(--ink); margin-top:auto; }
.slot .id { font:400 11px/1.3 var(--mono); color:var(--muted); margin-top:4px; }
.slot .flags { font:400 11px/1.3 var(--mono); color:var(--muted); margin-top:2px; }
.slot.selected { border:2px solid var(--accent); background:var(--accent-wash); padding:13px; }
.slot.selected .kind { color:var(--accent); }
.slot.selected::after { content:'EDITING'; position:absolute; top:-1px; right:-1px; background:var(--accent); color:var(--on-accent); font:700 10px/1 var(--mono); letter-spacing:.1em; padding:3px 7px; }
.slot.empty { border:1px dashed var(--disabled); display:flex; align-items:center; justify-content:center; gap:6px; flex-direction:column; color:var(--muted); }
.slot.empty .plus { font-size:20px; line-height:1; }
.slot.dragging { opacity:.45; }
.slot.drop-target { border-color:var(--accent); }

.editor > .inspector { border-left:1px solid var(--line); display:flex; flex-direction:column; }
.inspector .inspector-head { height:var(--tab-bar); display:flex; align-items:center; gap:10px; padding:0 var(--s4); border-bottom:1px solid var(--line); }
.inspector .inspector-body { padding:var(--s4); display:flex; flex-direction:column; gap:var(--s4); flex:1; overflow:auto; }
.inspector .inspector-body > .push { margin-top:auto; }


/* 12 ── PICKERS ───────────────────────────────────────────── */

.entity-picker { position:relative; }
.entity-results { border:1px solid var(--line); border-top:0; margin-top:-1px; max-height:280px; overflow:auto; background:var(--canvas); }
.entity-results button { display:flex; flex-direction:column; align-items:flex-start; justify-content:center; gap:2px; width:100%; height:52px; border:0; border-radius:0; background:transparent; padding:0 var(--s3); text-align:left; }
.entity-results button + button { border-top:1px solid var(--line); }
.entity-results button:hover, .entity-results button[aria-selected="true"] { background:var(--surface-raised); }
.entity-results b { font:400 14px/1.2 var(--font); }
.entity-results small { font:500 12px/1.3 var(--mono); color:var(--muted); }
.picker-hint { font:400 12px/1.4 var(--font); color:var(--muted); margin-top:10px; }

.icon-sheet { border:1px solid var(--line); background:var(--canvas); }
.icon-sheet > * + * { border-top:1px solid var(--line); }
.icon-sheet .sheet-head { height:var(--tab-bar); display:flex; align-items:center; gap:10px; padding:0 var(--s4); }
.icon-cats { display:flex; flex-wrap:wrap; gap:6px; padding:12px var(--s4); }
.icon-cats button { height:auto; padding:5px 9px; border-radius:999px; background:var(--surface-raised); border-color:transparent; color:var(--muted); font:600 11px/1 var(--font); letter-spacing:.08em; text-transform:uppercase; }
.icon-cats button.active { background:var(--accent); color:var(--on-accent); }
.icon-grid { display:grid; grid-template-columns:repeat(5,1fr); }
.icon-grid label { aspect-ratio:1; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:5px; border-right:1px solid var(--line); border-bottom:1px solid var(--line); cursor:pointer; }
.icon-grid label:nth-child(5n) { border-right:0; }
.icon-grid label:hover { background:var(--surface-raised); }
.icon-grid label span { font-size:19px; line-height:1; }
.icon-grid label small { font:400 9px/1 var(--mono); color:var(--muted); }
.icon-grid input { position:absolute; opacity:0; pointer-events:none; }
.icon-grid label:has(input:checked) { background:var(--accent-wash); box-shadow:inset 0 0 0 2px var(--accent); }
.icon-grid label:has(input:checked) span, .icon-grid label:has(input:checked) small { color:var(--accent); }
.icon-grid [hidden] { display:none; }

.add-grid { display:grid; grid-template-columns:1fr 1fr; }
.add-grid > button { height:auto; display:flex; flex-direction:column; align-items:flex-start; gap:3px; padding:14px var(--s4); border:0; border-right:1px solid var(--line); border-bottom:1px solid var(--line); border-radius:0; background:transparent; text-align:left; white-space:normal; }
.add-grid > button:nth-child(2n) { border-right:0; }
.add-grid > button b { font:600 14px/1 var(--font); }
.add-grid > button small { font:400 12px/1.45 var(--font); color:var(--muted); }
.add-grid > button:hover { background:var(--surface-raised); }
.add-grid > button:disabled { opacity:.45; background:transparent; }


/* 13 ── DIALOGS ───────────────────────────────────────────── */

.scrim { position:fixed; inset:0; background:rgba(14,16,18,.72); display:grid; place-items:center; padding:24px; z-index:10; }
.dialog { width:min(480px,100%); max-height:88vh; overflow:auto; background:var(--canvas); border:1px solid var(--line); border-top:2px solid var(--accent); }
.dialog.ok { border-top-color:var(--ok); }
.dialog > * + * { border-top:1px solid var(--line); }
.dialog .dialog-head { padding:var(--pane-inset); display:flex; align-items:flex-start; gap:var(--s3); }
.dialog .dialog-head .grow { flex:1; }
.dialog .dialog-head h2 { font:700 22px/1.2 var(--font); margin-top:6px; }
.dialog .dialog-head p { font:400 13px/1.5 var(--font); color:var(--muted); margin-top:4px; }
.dialog .dialog-body { padding:var(--pane-inset); }
.dialog .actions { display:flex; justify-content:flex-end; gap:var(--s2); margin-top:var(--s5); }
.dialog .actions.split { justify-content:space-between; }
.token-field { display:flex; gap:var(--s2); margin-top:var(--s4); }
.token-field code { flex:1; min-width:0; height:44px; display:flex; align-items:center; padding:0 var(--s3); background:var(--surface); border:1px solid var(--line); color:var(--muted); overflow:auto; white-space:nowrap; }
.token-field button { height:44px; }


/* 14 ── UTILITIES AND RESPONSIVE ──────────────────────────── */

.grow { flex:1; min-width:0; }
.right { margin-left:auto; }
.muted { color:var(--muted); }
.accent { color:var(--accent-ink); }
.danger-text { color:var(--danger); }
.ok-text { color:var(--ok); }
.nowrap { white-space:nowrap; }
.truncate { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.hstack { display:flex; align-items:center; gap:var(--s2); }
.vstack { display:flex; flex-direction:column; gap:var(--s2); }
[hidden] { display:none !important; }

@media (max-width:1240px) {
  .editor { grid-template-columns:200px minmax(0,1fr) 300px; }
  .board, .stage .stage-head, .stage .stage-foot { width:min(100%,440px); }
  .board { height:auto; aspect-ratio:1; }
}
@media (max-width:980px) {
  :host { --page-inset:18px; }
  .editor { grid-template-columns:1fr; min-height:0; }
  .editor > .rail { border-right:0; border-bottom:1px solid var(--line); }
  .editor > .inspector { border-left:0; border-top:1px solid var(--line); }
  .workspace-grid { grid-template-columns:1fr; }
  .panel-grid { grid-template-columns:1fr; }
  .integration-strip { flex-direction:column; height:auto; }
  .integration-strip > div + div { border-left:0; border-top:1px solid var(--line); }
  .integration-strip .go { flex:none; justify-content:flex-start; padding-top:12px; padding-bottom:12px; }
  .setting-row { flex-wrap:wrap; }
  .setting-row > input, .setting-row > select, .setting-row > .select-wrap { flex-basis:100%; }
  .icon-grid { grid-template-columns:repeat(4,1fr); }
  .icon-grid label:nth-child(5n) { border-right:1px solid var(--line); }
  .icon-grid label:nth-child(4n) { border-right:0; }
  .add-grid { grid-template-columns:1fr; }
  .add-grid > button { border-right:0; }
}
:host([narrow]) main { padding:18px; }
`;

if (!customElements.get("ha-panel-nspanel-companion-panel")) {
  customElements.define("ha-panel-nspanel-companion-panel", NSPanelCompanionPanel);
}
if (!customElements.get("nspanel-companion-panel")) {
  customElements.define("nspanel-companion-panel", class extends NSPanelCompanionPanel {});
}
