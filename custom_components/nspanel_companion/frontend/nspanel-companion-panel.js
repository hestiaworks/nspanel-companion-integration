const DEFAULT_LAYOUT = (revision) => ({
  schema_version: 1,
  revision,
  default_page_id: "climate",
  default_page_return_seconds: 60,
  weather_cache_max_age_minutes: 360,
  keep_screen_on: false,
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
    this.scryptedDoorbells = [];
    this.loading = true;
    this.busy = false;
    this.error = "";
    this.token = null;
    this.editor = null;
    this.workspaceTab = "general";
    this.routeHandler = () => this.restoreWorkspaceRoute();
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
      [this.panels, this.scrypted] = await Promise.all([
        this.call({ type: "nspanel_companion/panels/list" }),
        this.call({ type: "nspanel_companion/scrypted/list" }),
      ]);
      this.loaded = true;
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
    this.busy = true; this.render();
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
      if (this.editor.hasPublishedLayout && themeMode !== (this.editor.layout.theme_mode || "light")) {
        const themeLayout = {
          ...structuredClone(this.editor.layout),
          revision: `theme-${Date.now()}`,
          theme_mode: themeMode,
          theme_dark: themeMode === "dark" || themeMode === "inherit" && Boolean(this._hass?.themes?.darkMode),
        };
        await this.call({ type: "nspanel_companion/layout/set", panel_id: panel.panel_id, layout: themeLayout });
        this.editor.layout = themeLayout;
      }
      this.render();
    } catch (error) {
      this.error = error?.message || "Unable to rename panel";
      this.render();
    } finally { this.busy = false; this.render(); }
  }

  syncPageDraftFromDom() {
    if (!this.editor) return;
    this.shadowRoot.querySelectorAll("[data-page-title]").forEach((input) => {
      const index = Number(input.dataset.pageTitle);
      if (this.editor.draftPages[index]) this.editor.draftPages[index].title = input.value.trim();
    });
    this.shadowRoot.querySelectorAll("[data-widget-field]").forEach((input) => {
      if (input.type === "radio" && !input.checked) return;
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
    if (type === "entity_button") return { type, icon: "auto", show_timer: true, timer_presets: [5, 15, 30, 60], card_tap: false, show_fan_speed: false };
    if (type === "camera") return { type, incoming_audio: false, tap_action: "fullscreen" };
    return { type };
  }

  addDraftWidget(pageId, type) {
    this.syncPageDraftFromDom();
    const page = this.editor?.draftPages.find((item) => item.id === pageId);
    if (!page || !type || page.widgets.length >= 12) return;
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
      default_page_return_seconds: Number(values.get("return_seconds") || 60),
      weather_cache_max_age_minutes: 360,
      keep_screen_on: values.get("keep_screen_on") === "on",
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
      await this.call({
        type: "nspanel_companion/scrypted/unpair",
        bridge_id: bridgeId,
        clear_assignments: clearAssignments,
      });
      await this.loadPanels();
    } catch (error) { this.error = error?.message || "Unable to unpair Scrypted"; }
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
    this.shadowRoot.querySelector("#refresh")?.addEventListener("click", () => this.loadPanels());
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
        const hidden = picker?.querySelector("[data-widget-field='entity_id']");
        if (hidden) hidden.value = "";
        filter();
      });
      results?.querySelectorAll("[data-entity-option]").forEach((option) => option.addEventListener("click", () => {
        const hidden = picker.querySelector("[data-widget-field='entity_id']");
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
    this.shadowRoot.querySelectorAll("[data-diagnostics]").forEach((button) =>
      button.addEventListener("click", () => this.downloadDiagnostics(button.dataset.diagnostics)));
    this.shadowRoot.querySelectorAll("[data-panel-pair]").forEach((form) =>
      form.addEventListener("submit", (event) => { event.preventDefault(); this.approvePairing(event.currentTarget); }));
    this.shadowRoot.querySelectorAll("[data-revoke]").forEach((button) =>
      button.addEventListener("click", () => this.revokePanel(button.dataset.revoke)));
  }

  panelCard(panel) {
    const online = !panel.revoked && panel.last_seen && Date.now() - new Date(panel.last_seen).getTime() < 45000;
    const state = panel.revoked ? "Revoked" : online ? "Online" : "Offline";
    return `<article class="panel-card">
      <div class="panel-head">
        <span class="device-icon">▣</span>
        <div class="panel-identity"><h3>${escapeHtml(panel.name)}</h3><p title="${escapeHtml(panel.device_id)}">${escapeHtml(panel.device_id)}</p></div>
        <span class="status ${online ? "online" : "waiting"}">${state}</span>
      </div>
      <div class="actions">
        <button class="primary" data-edit="${escapeHtml(panel.panel_id)}" ${this.busy ? "disabled" : ""}>Configure</button>
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
      <main>
        <header><div><span class="eyebrow">Home Assistant</span><h1>NSPanel Companion</h1><p>Register room panels and assign their native dashboard.</p></div>
          <button id="refresh" class="icon" title="Refresh" ${this.loading ? "disabled" : ""}>↻</button></header>
        ${this.error ? `<div class="notice error">${escapeHtml(this.error)}</div>` : ""}
        ${this.scryptedSection()}
        <section><div class="section-title"><div><h2>Panels</h2><p>Native dashboards connected to this Home Assistant.</p></div><button id="find-panels" class="primary" type="button" ${this.busy ? "disabled" : ""}>Find panels</button></div>
            ${this.loading ? `<div class="empty">Loading panels…</div>` : this.panels.length ? `<div class="cards">${this.panels.map((p) => this.panelCard(p)).join("")}</div>` : `<div class="empty"><b>No panels yet</b><span>Open the app on a panel, then choose Find panels.</span></div>`}
        </section>
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

  entityPicker(domains, selected, placeholder, field, key) {
    const states = Object.values(this._hass?.states || {}).filter((item) => domains.includes(item.entity_id.split(".")[0]));
    states.sort((a, b) => this.entityLabel(a).localeCompare(this.entityLabel(b)));
    const selectedState = states.find((item) => item.entity_id === selected);
    const display = selectedState ? this.entityLabel(selectedState) : selected;
    return `<div class="entity-picker" data-entity-picker="${escapeHtml(key)}"><input type="hidden" ${field("entity_id")} value="${escapeHtml(selected)}"><input class="entity-search" data-entity-search="${escapeHtml(key)}" type="search" value="${escapeHtml(display)}" placeholder="${escapeHtml(placeholder)}" autocomplete="off" aria-label="${escapeHtml(placeholder)}"><div class="entity-results" data-entity-results="${escapeHtml(key)}" hidden>${states.map((state) => { const label = this.entityLabel(state); return `<button type="button" data-entity-option="${escapeHtml(state.entity_id)}" data-entity-label="${escapeHtml(label)}" data-entity-terms="${escapeHtml(label.toLowerCase())}"><b>${escapeHtml(state.attributes?.friendly_name || state.entity_id)}</b><small>${escapeHtml(state.entity_id)}</small></button>`; }).join("")}</div></div>`;
  }

  widgetName(widget) {
    if (widget.type === "entity_button") return "Home control";
    if (widget.type === "sensor") return "Sensor";
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

  widgetEditor(page, widget, index) {
    const field = (name) => `data-widget-field="${name}" data-page-id="${escapeHtml(page.id)}" data-widget-index="${index}"`;
    const entity = widget.entity_id || "";
    let configuration = "";
    const pickerKey = `${page.id}-${index}`;
    if (widget.type === "thermostat") configuration = `<label>Climate entity${this.entityPicker(["climate"], entity, "Search thermostats…", field, pickerKey)}</label><small>Heat, cool, auto, dry, and dual set points follow the capabilities reported by this entity.</small>`;
    if (widget.type === "weather") configuration = `<div class="widget-fields"><label>Weather entity${this.entityPicker(["weather"], entity, "Search weather entities…", field, pickerKey)}</label><label>Daily forecast<select ${field("forecast_days")}><option value="1" ${Number(widget.forecast_days ?? 5) === 1 ? "selected" : ""}>1 day</option><option value="3" ${Number(widget.forecast_days ?? 5) === 3 ? "selected" : ""}>3 days</option><option value="5" ${Number(widget.forecast_days ?? 5) === 5 ? "selected" : ""}>5 days</option></select></label></div><label class="check"><input type="checkbox" ${field("show_hourly")} ${widget.show_hourly !== false ? "checked" : ""}> Show next-hours forecast</label>`;
    if (widget.type === "entity_button") configuration = `<label>Control entity${this.entityPicker(["light", "fan", "switch", "input_boolean", "cover"], entity, "Search lights, fans, switches, and covers…", field, pickerKey)}</label><small>The panel automatically uses the correct native control for this entity's capabilities.</small>${this.iconPicker(page, widget, index, field)}<div class="control-checks inline-checks"><label class="check"><input type="checkbox" ${field("show_timer")} ${widget.show_timer !== false ? "checked" : ""}> Show timer</label><label class="check"><input type="checkbox" ${field("card_tap")} ${widget.card_tap === true ? "checked" : ""}> Use whole card as button</label><label class="check"><input type="checkbox" ${field("show_fan_speed")} ${widget.show_fan_speed === true ? "checked" : ""}> Show fan speed control</label></div><label>Timer presets in minutes<input ${field("timer_presets")} value="${escapeHtml((widget.timer_presets || [5, 15, 30, 60]).join(", "))}" placeholder="5, 15, 30, 60"><small>Up to four touch-friendly choices.</small></label>`;
    if (widget.type === "sensor") configuration = `<label>Sensor entity${this.entityPicker(["sensor", "binary_sensor"], entity, "Search sensors…", field, pickerKey)}</label>`;
    if (widget.type === "camera") {
      const selectedCamera = widget.scrypted_bridge_id && widget.scrypted_camera_id ? `${widget.scrypted_bridge_id}|${widget.scrypted_camera_id}` : "";
      configuration = `<label>Scrypted camera<select data-camera-source ${field("scrypted_source")} required><option value="">Select camera</option>${this.scryptedDoorbells.map((item) => { const value = `${item.bridge_id}|${item.id}`; return `<option value="${escapeHtml(value)}" ${selectedCamera === value ? "selected" : ""}>${escapeHtml(item.name)}</option>`; }).join("")}</select></label><div class="inline-checks"><label class="check"><input type="checkbox" ${field("incoming_audio")} ${widget.incoming_audio ? "checked" : ""}> Play incoming audio</label></div><label>Tap action<select ${field("tap_action")}><option value="none" ${widget.tap_action === "none" ? "selected" : ""}>None</option><option value="fullscreen" ${widget.tap_action !== "none" && widget.tap_action !== "intercom" ? "selected" : ""}>Open fullscreen</option><option value="intercom" ${widget.tap_action === "intercom" ? "selected" : ""}>Open intercom</option></select></label><small>The stream starts only while this page is visible and stops immediately after swiping away.</small>`;
    }
    if (widget.type === "controls") configuration = `<div class="notice draft-note">Legacy component: it automatically selects the first four supported controls. Replace it with explicit Home control components for predictable layouts.</div>`;
    return `<article class="widget-card" data-widget-drop="${index}" data-widget-page="${escapeHtml(page.id)}"><div class="widget-drag" draggable="true" data-widget-drag="${index}" data-widget-page="${escapeHtml(page.id)}" title="Drag to reorder">⠿</div><div class="widget-body"><div class="widget-title"><div><span class="eyebrow">Component ${index + 1}</span><h4>${escapeHtml(this.widgetName(widget))}</h4></div><button class="danger" type="button" data-widget-action="delete" data-widget-index="${index}" data-widget-page="${escapeHtml(page.id)}">Remove</button></div>${configuration}<label>Custom label <span class="optional">Optional</span><input ${field("label")} maxlength="48" value="${escapeHtml(widget.label || "")}" placeholder="Use the Home Assistant name"></label></div></article>`;
  }

  pageComponentEditor(page) {
    if (!page) return "";
    const hasFullScreen = page.widgets.some((widget) => ["thermostat", "weather", "camera"].includes(widget.type));
    return `<div class="scrim page-editor-scrim"><section class="dialog page-editor"><div class="component-head"><div><span class="eyebrow">Edit page</span><h2>${escapeHtml(page.title || "Untitled page")}</h2><p>Configure the native components and see an approximate panel preview.</p></div><button type="button" data-close-page-components>Done</button></div><div class="page-editor-grid"><section class="component-editor">${page.widgets.length ? `<div class="widget-list">${page.widgets.map((widget, index) => this.widgetEditor(page, widget, index)).join("")}</div>` : `<div class="empty compact"><b>This page is empty</b><span>Add its first native component below.</span></div>`}<div class="add-widget"><label>Component type<select id="new-widget-type" ${hasFullScreen || page.widgets.length >= 12 ? "disabled" : ""}><option value="entity_button">Home control</option><option value="sensor">Sensor</option><option value="thermostat">Thermostat</option><option value="weather">Weather</option><option value="camera">Camera</option></select></label><button id="add-widget" data-widget-page="${escapeHtml(page.id)}" class="primary" type="button" ${hasFullScreen || page.widgets.length >= 12 ? "disabled" : ""}>Add component</button></div>${hasFullScreen ? `<small>This full-screen component must remain the only component on this page.</small>` : ""}</section><aside class="preview-column"><span class="eyebrow">Panel preview</span><div class="panel-preview-host">${this.pagePreview(page)}</div><small>Approximate preview at the NSPanel Pro aspect ratio. The Android app remains the rendering authority.</small></aside></div></section></div>`;
  }

  previewEntity(widget) {
    return this._hass?.states?.[widget.entity_id] || null;
  }

  weatherGlyph(condition) {
    return ({ "clear-night": "☾", sunny: "☀", partlycloudy: "◑", cloudy: "☁", rainy: "☂", pouring: "☔", lightning: "ϟ", "lightning-rainy": "ϟ", snowy: "❄", "snowy-rainy": "❄", fog: "≋", windy: "≈", hail: "◆" })[condition] || "◌";
  }

  pagePreview(page, miniature = false) {
    const dark = this.editor?.draftThemeMode === "dark" || this.editor?.draftThemeMode === "inherit" && Boolean(this._hass?.themes?.darkMode);
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
        const daily = Array.from({ length: Number(widget.forecast_days ?? 5) }, (_, index) => `<span><small>${index ? ["Sat", "Sun", "Mon", "Tue"][index - 1] : "Today"}</small><i>${this.weatherGlyph(dailyConditions[index])}</i><b><em>${18 + index}°</em>${24 - index}°</b></span>`).join("");
        return `<div class="preview-weather detailed"><div class="weather-now"><i>${this.weatherGlyph(condition)}</i><div><strong>${escapeHtml(temperature)}°</strong><b>${escapeHtml(conditionLabel)}</b><small>Feels like ${escapeHtml(entity?.attributes?.apparent_temperature ?? temperature)}° · Humidity ${escapeHtml(entity?.attributes?.humidity ?? "48")}%</small></div></div>${widget.show_hourly !== false ? `<div class="hourly-forecast"><p>Clear conditions continue for the next few hours.</p><div>${hourly}</div></div>` : ""}<div class="daily-forecast">${daily}</div></div>`;
      }
      if (widget.type === "camera") return `<div class="preview-camera"><span>▶</span><b>${escapeHtml(name)}</b><small>${widget.incoming_audio ? "Audio on" : "Muted"} · ${escapeHtml(widget.tap_action || "fullscreen")}</small></div>`;
      if (widget.type === "sensor") return `<div class="preview-tile sensor"><small>${escapeHtml(name)}</small><strong>${escapeHtml(entity?.state ?? "—")}</strong></div>`;
      const automatic = entity?.entity_id?.startsWith("fan.") ? "fan" : entity?.entity_id?.startsWith("cover.") ? "curtains" : entity?.entity_id?.startsWith("switch.") ? "power" : "light";
      const iconId = (widget.icon || "auto") === "auto" ? automatic : widget.icon;
      const glyph = CONTROL_ICONS.find(([id]) => id === iconId)?.[2] || "✦";
      const presets = (widget.timer_presets || [5, 15, 30, 60]).slice(0, 4);
      return `<div class="preview-tile control revised ${denseControls ? "dense" : ""} ${widget.card_tap ? "whole-card" : ""}"><div class="control-head"><i>${glyph}</i><button type="button" aria-label="Toggle"><span></span></button></div>${denseControls ? `<strong class="${name.length > 22 ? "long-name" : ""}" title="${escapeHtml(name)}">${escapeHtml(name)}</strong><small>${escapeHtml(automatic === "power" ? "Switch" : automatic)}</small>` : `<b>${escapeHtml(name)}</b><small>${escapeHtml(automatic === "power" ? "Switch" : automatic)}</small><strong>${escapeHtml(entity?.state || "Off")}</strong>`}${widget.show_timer !== false ? `<div class="control-timer"><em>Timer</em><div class="timer-options">${presets.map((value) => `<span>${value}m</span>`).join("")}</div></div>` : ""}</div>`;
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
          <label>Stable device ID<input value="${escapeHtml(panel.device_id)}" readonly></label>
          <dl><div><dt>Connection</dt><dd>${panel.revoked ? "Revoked" : online ? "Online" : "Offline"}</dd></div><div><dt>Registered</dt><dd>${formatDate(panel.created_at)}</dd></div><div><dt>App version</dt><dd>${escapeHtml(panel.app_version || "—")}</dd></div></dl>
          <div class="actions"><button class="primary" type="submit" ${this.busy ? "disabled" : ""}>Save general settings</button></div>
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
          <fieldset class="dashboard-behavior"><legend>Dashboard behavior</legend><label>Return to first page after<input name="return_seconds" type="number" min="0" max="3600" value="${Number(layout.default_page_return_seconds ?? 60)}"><small>Seconds; use 0 to disable automatic return.</small></label><label class="check"><input name="keep_screen_on" type="checkbox" ${layout.keep_screen_on ? "checked" : ""}> Keep display on while dashboard is open</label><small>Off by default. When disabled, the panel follows its Android display timeout and automatic brightness settings.</small></fieldset>
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

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const formatDate = (value) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";

const STYLES = `
  :host{display:block;min-height:100%;background:var(--primary-background-color,#f4f5f3);color:var(--primary-text-color,#171916);font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif)}
  *{box-sizing:border-box}main{max-width:1180px;margin:auto;padding:32px}header{display:flex;justify-content:space-between;align-items:start;margin-bottom:24px}h1{font-size:32px;margin:4px 0}h2{margin:0 0 6px;font-size:21px}h3{margin:0;font-size:17px}p{color:var(--secondary-text-color,#70746f);margin:4px 0;line-height:1.45}.eyebrow{text-transform:uppercase;letter-spacing:.14em;font-weight:800;font-size:11px;color:#f36d21}
  button{border:1px solid var(--divider-color,#d8dad6);background:var(--card-background-color,#fff);color:inherit;border-radius:12px;padding:11px 15px;font:inherit;font-weight:700;cursor:pointer}button:hover{border-color:#f36d21}button:disabled{opacity:.55;cursor:default}.primary{background:#f36d21;border-color:#f36d21;color:white}.icon{font-size:22px;padding:8px 13px}.wide{width:100%;margin-top:16px}
  .danger{color:#b3261e}
  .pairings{margin-bottom:24px}.pairing{display:grid;grid-template-columns:minmax(180px,1fr) 150px auto auto;align-items:center;gap:18px;background:#fff4ed;border:1px solid #ffc7a8;border-radius:18px;padding:15px 18px;margin-top:10px}.pairing div{display:flex;flex-direction:column}.pairing div span,.expires{font-size:11px;color:var(--secondary-text-color,#777);font-family:monospace}.pairing .pair-code{margin:0;background:var(--card-background-color,#fff)}
  .bridge{display:flex;justify-content:space-between;gap:20px;background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#e1e3df);border-radius:20px;padding:18px;margin-bottom:24px}.bridge-list{min-width:min(540px,60%);display:grid;gap:8px}.bridge-row{display:flex;align-items:center;justify-content:flex-end;gap:10px;margin:0}.bridge-row>div{margin-right:auto}.bridge-row small{margin:2px 0}.pair-code{width:145px;margin:0;font-size:18px;letter-spacing:.12em}details{margin-top:14px;border-top:1px solid var(--divider-color,#ddd);padding-top:12px}summary{cursor:pointer;font-weight:800}
  .section-title{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:12px}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:12px}.panel-card,.empty{background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#e1e3df);border-radius:20px;padding:20px}.panel-card{display:flex;flex-direction:column;min-height:190px}.panel-card>.actions{margin-top:auto}.panel-head{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:13px;align-items:center;min-width:0}.panel-identity{min-width:0}.panel-head p{font-family:monospace;font-size:12px;white-space:normal;overflow-wrap:anywhere}.device-icon{display:grid;place-items:center;width:48px;height:48px;background:#ffebe0;color:#f36d21;border-radius:14px;font-size:24px}.status{font-size:11px;font-weight:800;padding:6px 9px;border-radius:999px}.online{background:#dff7eb;color:#147a4d}.waiting{background:#f1f1ee;color:#71746f}
  dl{display:grid;gap:8px;margin:18px 0}dl div{display:flex;justify-content:space-between;gap:16px;border-top:1px solid var(--divider-color,#e5e6e3);padding-top:8px}dt{color:var(--secondary-text-color,#777);font-size:12px}dd{margin:0;text-align:right;font-size:12px;font-weight:700;overflow-wrap:anywhere}.actions{display:flex;justify-content:flex-end;gap:8px;margin-top:16px;flex-wrap:wrap}
  form{margin-top:18px}label{display:block;font-size:12px;font-weight:800;margin-top:13px}input{width:100%;margin-top:6px;border:1px solid var(--divider-color,#d8dad6);border-radius:11px;background:var(--secondary-background-color,#f7f7f5);color:inherit;padding:12px;font:inherit}input:focus{outline:2px solid #f36d21;border-color:transparent}small{display:block;color:var(--secondary-text-color,#777);margin-top:10px;line-height:1.4}.empty{min-height:180px;display:grid;place-content:center;text-align:center;gap:6px}.empty span{color:var(--secondary-text-color,#777)}.notice{padding:12px 16px;border-radius:12px;margin-bottom:16px}.error{background:#ffe6e3;color:#a12c22}
  .scrim{position:fixed;inset:0;background:#0008;display:grid;place-items:center;padding:20px;z-index:10}.dialog{width:min(560px,100%);max-height:90vh;overflow:auto;background:var(--card-background-color,#fff);border-radius:24px;padding:26px;box-shadow:0 20px 70px #0005}.success-mark{display:grid;place-items:center;width:46px;height:46px;border-radius:50%;background:#dff7eb;color:#147a4d;font-size:25px;margin-bottom:15px}.token{display:flex;gap:8px;margin-top:7px}.token code{flex:1;min-width:0;overflow:auto;background:var(--secondary-background-color,#f4f4f1);padding:13px;border-radius:10px;font-size:12px}.details pre{max-height:260px;overflow:auto;background:var(--secondary-background-color,#f4f4f1);padding:14px;border-radius:12px;font-size:11px}
  .finder-list{display:grid;gap:10px;margin-top:18px}.finder-panel{display:grid;grid-template-columns:42px 1fr auto;align-items:center;text-align:left;gap:12px;width:100%;padding:13px}.finder-panel span:nth-child(2){min-width:0}.finder-panel b,.finder-panel small{display:block}.finder-panel small,.device-id{font-family:monospace;overflow-wrap:anywhere}.pairing-dialog{width:min(620px,100%);padding:30px}.pairing-dialog-head{display:flex;align-items:center;gap:20px;margin-bottom:28px}.pairing-dialog-head .eyebrow{display:block}.pairing-dialog-body h2{font-size:30px;margin:0 0 10px}.pairing-dialog-body .device-id{margin:0 0 18px}.pairing-help{margin:0 0 28px}.pairing-form{margin:0}.pairing-entry{display:block;width:min(100%,380px);font-size:30px;letter-spacing:.18em;text-align:center;margin:0;padding:18px 20px}.pairing-actions{margin-top:34px;gap:12px}.pairing-actions button{min-width:120px;padding:14px 20px}
  .editor{width:min(980px,100%)}.editor-head{display:grid;grid-template-columns:1fr auto auto;gap:14px;align-items:start;margin-bottom:18px}.editor-head .device-id{margin-top:5px}.editor-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}fieldset{border:1px solid var(--divider-color,#ddd);border-radius:16px;padding:16px;margin:0 0 16px}legend{font-size:16px;font-weight:800;padding:0 7px}select{width:100%;margin-top:6px;border:1px solid var(--divider-color,#d8dad6);border-radius:11px;background:var(--secondary-background-color,#f7f7f5);color:inherit;padding:12px;font:inherit}.check{display:flex;gap:9px;align-items:center}.check input,.entity-check input{width:auto;margin:0}.entity-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;max-height:280px;overflow:auto}.entity-check{display:flex;align-items:center;gap:10px;margin:0;padding:10px;border:1px solid var(--divider-color,#ddd);border-radius:11px}.entity-check span{min-width:0}.entity-check b,.entity-check small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.entity-check small{margin:2px 0 0;font-family:monospace}.panel-tools{background:var(--secondary-background-color,#f7f7f5)}.panel-tools .actions{justify-content:flex-start}
  .workspace{padding:0;overflow:hidden}.workspace .editor-head{grid-template-columns:minmax(0,1fr) auto;padding:24px 26px 18px;margin:0}.workspace-title{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.workspace-title h2{margin:0}.workspace-tabs{display:flex;gap:4px;padding:0 26px;border-bottom:1px solid var(--divider-color,#ddd);overflow-x:auto}.workspace-tabs button{border:0;border-bottom:3px solid transparent;border-radius:0;background:transparent;color:var(--secondary-text-color,#777);padding:13px 15px;white-space:nowrap}.workspace-tabs button.active{color:var(--primary-text-color,#171916);border-bottom-color:#f36d21}.workspace-panel{padding:24px 26px;max-height:calc(90vh - 165px);overflow:auto}.workspace-panel[hidden]{display:none}.workspace-intro{margin-bottom:18px}.workspace-intro h3{font-size:20px}.workspace-layout-form{margin:0}.settings-card{max-width:680px;border:1px solid var(--divider-color,#ddd);border-radius:16px;padding:18px;margin:0}.settings-card input[readonly]{font-family:monospace;color:var(--secondary-text-color,#777)}.unconfigured-notice{display:flex;align-items:center;gap:14px;border:1px solid #ffc7a8;background:#fff4ed;color:#171916;border-radius:16px;padding:16px;margin-bottom:18px}.unconfigured-notice h3{margin:0 0 4px}.unconfigured-notice p{margin:0}.danger-zone{border-color:#d79a95;background:color-mix(in srgb,var(--card-background-color,#fff) 92%,#b3261e)}.left{justify-content:flex-start}
  .page-list{display:grid;gap:10px;margin-bottom:18px}.page-card{display:grid;grid-template-columns:42px minmax(0,1fr) auto;align-items:center;gap:14px;border:1px solid var(--divider-color,#ddd);border-radius:16px;padding:14px;background:var(--card-background-color,#fff);transition:border-color .15s,opacity .15s,transform .15s}.page-card.active{border-color:#f36d21}.page-card.dragging{opacity:.45}.page-card.drag-over{border-color:#f36d21;transform:translateY(2px)}.page-order{display:flex;flex-direction:column;align-items:center;justify-content:center;width:38px;height:48px;border-radius:12px;background:#ffebe0;color:#d95713;font-weight:900;cursor:grab;user-select:none}.page-order:active{cursor:grabbing}.page-order span{font-size:20px;line-height:16px}.page-order small{margin:3px 0 0;color:inherit;font-size:10px}.page-content{min-width:0}.page-content label{margin:0}.page-content input{margin-top:5px}.page-meta{display:flex;align-items:center;gap:14px;margin-top:9px;color:var(--secondary-text-color,#777);font-size:12px}.page-actions{display:flex;gap:6px;flex-wrap:wrap}.page-actions button{padding:8px 10px;font-size:12px}.component-editor{border:1px solid color-mix(in srgb,#f36d21 55%,var(--divider-color,#ddd));border-radius:18px;background:color-mix(in srgb,var(--card-background-color,#fff) 96%,#f36d21);padding:18px;margin:0 0 18px}.component-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:14px}.component-head h3{font-size:22px;margin:3px 0 4px}.component-head p{margin:0}.widget-list{display:grid;gap:10px}.widget-card{display:grid;grid-template-columns:38px minmax(0,1fr);gap:12px;border:1px solid var(--divider-color,#ddd);border-radius:14px;padding:12px;background:var(--card-background-color,#fff)}.widget-card.dragging{opacity:.45}.widget-card.drag-over{border-color:#f36d21}.widget-drag{display:grid;place-items:center;min-height:48px;border-radius:10px;background:#ffebe0;color:#d95713;font-size:22px;cursor:grab}.widget-title{display:flex;align-items:start;justify-content:space-between;gap:12px}.widget-title h4{font-size:17px;margin:3px 0 2px}.widget-title button{padding:7px 9px;font-size:11px}.widget-fields{display:grid;grid-template-columns:2fr 1fr;gap:10px}.optional{color:var(--secondary-text-color,#777);font-weight:400}.add-widget,.add-page{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:end;gap:10px;border:1px dashed var(--divider-color,#bbb);border-radius:16px;padding:14px;margin:16px 0}.add-widget label,.add-page label{margin:0}.add-widget button,.add-page button{min-height:44px}.empty.compact{min-height:110px}.draft-note{background:#fff4ed;color:#8a430f}.dashboard-behavior{margin-top:18px}
  .workspace-page{max-width:1380px}.workspace-page>.workspace{border:1px solid var(--divider-color,#ddd);border-radius:24px;background:var(--card-background-color,#fff);overflow:hidden;min-height:calc(100vh - 64px)}.workspace-back{display:block;margin:0 0 16px;padding:8px 11px}.workspace-page .workspace-panel{max-height:none;overflow:visible}.workspace-page .settings-card{max-width:760px}.visual-page-list{grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}.visual-page-card{display:flex;flex-direction:column;align-items:stretch;gap:0;padding:14px}.page-card-top{display:flex;align-items:center;gap:10px;margin-bottom:12px}.page-heading{display:flex;flex-direction:column;min-width:0}.page-heading>b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.page-heading small{margin:2px 0}.visual-page-card>label{margin-top:12px}.visual-page-card .page-actions{margin-top:auto;padding-top:12px}.visual-page-card .page-actions .primary{flex:1}.page-editor{width:min(1220px,96vw);padding:24px}.page-editor-grid{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(360px,.75fr);gap:24px;align-items:start}.page-editor .component-editor{margin:0}.preview-column{position:sticky;top:0;display:grid;gap:10px}.panel-preview-host{display:grid;place-items:center;border-radius:20px;background:#111218;padding:22px}.panel-preview{position:relative;aspect-ratio:1/1;width:min(100%,480px);overflow:hidden;border-radius:4px;padding:7% 7% 6%;font-family:system-ui,sans-serif;container-type:inline-size}.panel-preview.light{background:#efefec;color:#171916}.panel-preview.dark{background:#121716;color:#f2f3ef}.preview-page-title{font-size:7cqw;font-weight:850;line-height:1.05;margin-bottom:5%}.preview-widgets{height:75%;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:1fr;gap:3%;min-height:0}.preview-widgets.fullscreen{display:block}.preview-tile{position:relative;border-radius:14%;padding:10%;display:flex;flex-direction:column;justify-content:space-between;min-width:0;overflow:hidden}.light .preview-tile{background:#fff}.dark .preview-tile{background:#232826}.preview-tile small{margin:0;color:inherit;opacity:.65;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.preview-tile strong{font-size:7cqw;text-transform:capitalize}.preview-tile.control i{font-style:normal;font-size:6cqw;line-height:1}.preview-tile.control em{position:absolute;right:31%;top:10%;font-style:normal;font-size:3cqw;padding:2% 4%;border-radius:999px;background:rgba(127,127,127,.16)}.preview-tile.control span{position:absolute;right:9%;top:10%;width:20%;aspect-ratio:1;border-radius:50%;background:#f36d21}.preview-tile.control.whole-card{outline:2px solid color-mix(in srgb,#f36d21 65%,transparent)}.preview-climate,.preview-weather{height:100%;min-height:0;border-radius:8%;padding:6% 8%;overflow:hidden;display:flex;flex-direction:column;align-items:center;justify-content:space-evenly}.light .preview-climate,.light .preview-weather{background:#f7f7f5}.dark .preview-climate,.dark .preview-weather{background:#232826}.preview-climate small,.preview-climate span{letter-spacing:.12em;margin:0;font-size:4.2cqw;line-height:1}.preview-climate strong{font-size:20cqw;line-height:.9}.preview-climate b{font-size:13cqw;line-height:.9}.preview-modes{margin:0;padding:3% 6%;max-width:96%;border-radius:999px;background:#f36d21;color:#fff;font-size:3.8cqw;line-height:1.2;white-space:nowrap}.preview-weather>span{font-size:13cqw;line-height:1}.preview-weather>strong{font-size:20cqw;line-height:.9}.preview-weather>b{text-transform:capitalize;font-size:5cqw;line-height:1.1}.preview-weather>div{display:flex;gap:4%;align-items:flex-start;justify-content:center;width:96%;margin:0}.preview-weather small{display:flex;flex:1;min-width:0;flex-direction:column;align-items:center;margin:0;font-size:3.4cqw;line-height:1.2;white-space:nowrap}.preview-weather small b{font-size:1.2em}.preview-empty{grid-column:1/-1;display:grid;place-items:center;border:2px dashed currentColor;border-radius:12%;opacity:.35}.preview-dots{position:absolute;left:0;right:0;bottom:2.5%;text-align:center;letter-spacing:.3em;opacity:.5;font-size:2.4cqw}.panel-preview.miniature{width:100%;border-radius:12px;padding:7%}.panel-preview.miniature .preview-page-title{font-size:7cqw}.panel-preview.miniature .preview-widgets{height:72%}.panel-preview.miniature .preview-tile strong{font-size:7cqw}.panel-preview.miniature .preview-climate strong,.panel-preview.miniature .preview-weather>strong{font-size:20cqw}.panel-preview.miniature .preview-climate b{font-size:13cqw}.panel-preview.miniature .preview-modes{font-size:3.8cqw}.panel-preview.miniature .preview-weather>span{font-size:13cqw}.panel-preview.miniature .preview-weather small{font-size:3.4cqw}.panel-preview.miniature .preview-dots{font-size:2.4cqw}.control-options{align-items:end}.control-checks{padding-bottom:3px}.control-checks label{margin-top:10px}
  .icon-picker{border:1px solid var(--divider-color,#ddd);border-radius:12px;padding:0;margin-top:13px}.icon-picker summary{border:0;padding:12px 14px}.icon-picker summary b{float:right;color:#f36d21}.icon-search{width:calc(100% - 24px);margin:0 12px 10px}.icon-categories{display:flex;gap:6px;overflow-x:auto;padding:0 12px 10px}.icon-categories button{padding:6px 9px;border-radius:999px;font-size:10px;white-space:nowrap}.icon-categories button.active{background:#f36d21;border-color:#f36d21;color:#fff}.icon-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;max-height:300px;overflow:auto;padding:0 12px 12px}.icon-grid label{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;min-height:68px;margin:0;padding:8px 4px;border:1px solid var(--divider-color,#ddd);border-radius:10px;cursor:pointer;text-align:center}.icon-grid label:hover{border-color:#f36d21}.icon-grid label:has(input:checked){border-color:#f36d21;background:#ffebe0;color:#8a430f}.icon-grid input{position:absolute;opacity:0;pointer-events:none}.icon-grid span{font-size:22px;line-height:1}.icon-grid small{margin:0;color:inherit;font-size:9px}.icon-grid [hidden]{display:none}.inline-checks{display:flex;gap:22px;flex-wrap:wrap;margin-top:10px}.inline-checks label{margin-top:6px}.entity-picker{position:relative;margin-top:6px}.entity-picker .entity-search{margin:0}.entity-results{position:absolute;z-index:20;left:0;right:0;top:calc(100% + 5px);max-height:280px;overflow:auto;padding:6px;border:1px solid var(--divider-color,#ddd);border-radius:12px;background:var(--card-background-color,#fff);box-shadow:0 12px 35px #0004}.entity-results button{display:block;width:100%;border:0;border-radius:8px;padding:9px 10px;text-align:left;background:transparent}.entity-results button:hover{background:color-mix(in srgb,#f36d21 12%,transparent)}.entity-results b,.entity-results small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.entity-results small{margin:2px 0 0;font-family:monospace}.entity-results [hidden]{display:none}
  :host([narrow]) main{padding:18px}:host([narrow]) .cards{grid-template-columns:1fr}@media(max-width:820px){main{padding:18px}.editor-grid{grid-template-columns:1fr}.entity-list{grid-template-columns:1fr}.cards{grid-template-columns:1fr}.section-title{align-items:flex-start}.panel-card{min-height:175px}.panel-card>.actions{justify-content:stretch}.panel-card>.actions button{width:100%}.panel-head{grid-template-columns:42px minmax(0,1fr) auto}.device-icon{width:42px;height:42px}.editor-head{grid-template-columns:1fr auto}.editor-head .status{grid-column:1}.pairing{grid-template-columns:1fr auto}.pairing .expires{grid-column:1}.pairing button{grid-column:2;grid-row:2}.workspace .editor-head{padding:20px}.workspace-tabs{padding:0 12px}.workspace-panel{padding:20px}.workspace-tabs button{padding:12px 11px}.visual-page-list{grid-template-columns:1fr}.page-meta{align-items:flex-start;flex-direction:column;gap:6px}.add-page,.add-widget{grid-template-columns:1fr}.add-page button,.add-widget button{width:100%}.page-editor-grid{grid-template-columns:1fr}.preview-column{position:static}.widget-fields{grid-template-columns:1fr}.icon-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
  .preview-camera{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4%;border-radius:8%;background:linear-gradient(145deg,#1b2524,#050707);color:#fff}.preview-camera>span{display:grid;place-items:center;width:18%;aspect-ratio:1;border-radius:50%;background:#f36d21;font-size:6cqw}.preview-camera>b{font-size:5cqw}.preview-camera>small{margin:0;color:#bbb;font-size:3cqw}
  .preview-climate.dual{padding:2% 3%;justify-content:space-between;gap:2%;background:transparent}.climate-ring{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;width:48%;aspect-ratio:1;margin:auto;border-radius:50%;background:radial-gradient(circle at center,var(--card-background-color,#232826) 0 68%,transparent 69%)}.climate-dial{position:absolute;inset:-8%;width:116%;height:116%;overflow:visible;fill:none}.climate-dial path{stroke-width:12;stroke-linecap:round}.dial-track{stroke:rgba(127,127,127,.18)}.dial-heat{stroke:#c45d27}.dial-cool{stroke:#2d8bd0}.dial-handle{fill:#fff;stroke-width:4}.dial-handle.heat{stroke:#c45d27}.dial-handle.cool{stroke:#2d8bd0}.climate-ring small{position:relative;font-size:2.8cqw}.climate-ring strong{position:relative;font-size:12cqw;line-height:1}.ring-target{position:absolute;bottom:4%;z-index:2;padding:1% 4%;border-radius:999px;font-size:3.5cqw;font-weight:850;color:#fff}.ring-target.heat{left:-17%;background:#a94f25}.ring-target.cool{right:-17%;background:#2478b4}.target-picker{display:grid;grid-template-columns:1fr 1fr;gap:2%;width:100%}.target-picker button{display:flex;align-items:center;justify-content:space-between;padding:3% 5%;border-radius:12px;background:rgba(127,127,127,.1);font-size:3.4cqw}.target-picker button.selected{border-color:#f36d21;background:color-mix(in srgb,#f36d21 16%,transparent)}.target-picker small{margin:0;font-size:2.5cqw;letter-spacing:.08em}.target-picker b{font-size:5cqw}.target-stepper{display:grid;grid-template-columns:13% 1fr 13%;align-items:center;gap:3%;width:88%}.target-stepper button{padding:0;aspect-ratio:1;border-radius:50%;font-size:5cqw}.target-stepper span{text-align:center;font-size:3cqw;letter-spacing:0}.preview-climate.dual .preview-modes{display:flex;justify-content:space-between;width:100%;max-width:none;padding:1.5%;background:rgba(127,127,127,.1);font-size:2.7cqw}.preview-climate.dual .preview-modes b{padding:2.5% 3%;border-radius:8px;font-size:inherit}.preview-climate.dual .preview-modes .active{background:#f36d21;color:#fff}
  .preview-weather.detailed{padding:2%;align-items:stretch;justify-content:space-between;gap:2%;background:transparent}.weather-now{display:grid;grid-template-columns:24% 1fr;align-items:center;padding:2% 4%;border-radius:14px;background:rgba(127,127,127,.1)}.weather-now>i{font-style:normal;font-size:14cqw;text-align:center}.weather-now>div{display:grid;grid-template-columns:auto 1fr;align-items:end;column-gap:5%}.weather-now strong{font-size:12cqw;line-height:.9}.weather-now b{font-size:4cqw;text-transform:capitalize}.weather-now small{grid-column:1/-1;margin:3% 0 0;font-size:3.2cqw;color:inherit;opacity:.72}.hourly-forecast{padding:2% 3%;border-radius:14px;background:rgba(127,127,127,.1)}.hourly-forecast p{margin:0 0 2%;font-size:2.8cqw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hourly-forecast>div,.daily-forecast{display:flex;justify-content:space-between}.hourly-forecast span,.daily-forecast span{display:flex;flex-direction:column;align-items:center;min-width:0}.hourly-forecast small,.daily-forecast small{margin:0;font-size:2.7cqw;color:inherit}.hourly-forecast i,.daily-forecast i{font-style:normal;font-size:5cqw;line-height:1.25}.hourly-forecast b{font-size:3.4cqw}.daily-forecast{padding:2.5% 3%;border-radius:14px;background:rgba(127,127,127,.1)}.daily-forecast span{flex:1}.daily-forecast b{display:flex;gap:12%;font-size:3.2cqw}.daily-forecast em{font-style:normal;opacity:.55}
  .preview-tile.control.revised{padding:8%;justify-content:flex-start}.control-head{display:flex;align-items:center;justify-content:space-between}.preview-tile.control.revised .control-head>i{font-size:7cqw}.control-head button{position:relative;width:28%;aspect-ratio:1.65;padding:0;border:0;border-radius:999px;background:#f36d21}.preview-tile.control.revised .control-head button span{position:absolute;right:8%;top:14%;width:43%;aspect-ratio:1;border-radius:50%;background:#fff}.preview-tile.control.revised>b{margin-top:8%;font-size:4.4cqw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.preview-tile.control.revised>small{font-size:3.2cqw;opacity:.68;text-transform:capitalize}.preview-tile.control.revised>strong{margin-top:auto;font-size:8cqw}.preview-tile.control.revised.dense>strong{display:-webkit-box;flex:0 0 2.1em;overflow:hidden;margin-top:auto;font-size:4.7cqw;line-height:1.05;overflow-wrap:anywhere;text-transform:none;-webkit-box-orient:vertical;-webkit-line-clamp:2}.preview-tile.control.revised.dense>strong.long-name{font-size:4.15cqw}.preview-tile.control.revised.dense>small{margin-top:2%}.control-timer{display:flex;align-items:center;gap:3%;min-width:0;margin-top:6%;padding-top:5%;border-top:1px solid rgba(127,127,127,.25)}.preview-tile.control .control-timer em{position:static;flex:none;font-style:normal;font-size:3cqw;padding:0;background:none}.timer-options{display:flex;flex:1;min-width:0;gap:3%;overflow-x:auto;overscroll-behavior-x:contain;scroll-snap-type:x proximity;scrollbar-width:none;-webkit-overflow-scrolling:touch}.timer-options::-webkit-scrollbar{display:none}.preview-tile.control .timer-options span{position:static;flex:none;width:auto;aspect-ratio:auto;padding:3% 5%;border-radius:7px;background:rgba(127,127,127,.13);font-size:2.7cqw;scroll-snap-align:start}
  .panel-preview.miniature .preview-climate.dual{gap:1%;padding:1% 3%}.panel-preview.miniature .climate-ring{width:42%;margin:0 auto}.panel-preview.miniature .climate-ring strong{font-size:10cqw}.panel-preview.miniature .ring-target{bottom:1%;font-size:3cqw}.panel-preview.miniature .ring-target.heat{left:-18%}.panel-preview.miniature .ring-target.cool{right:-18%}.panel-preview.miniature .target-picker button{padding:2% 4%}.panel-preview.miniature .target-picker small{font-size:2.1cqw}.panel-preview.miniature .target-picker b{font-size:4.4cqw}.panel-preview.miniature .target-stepper{display:none}.panel-preview.miniature .preview-climate.dual .preview-modes{font-size:2.35cqw;padding:1%}.panel-preview.miniature .preview-climate.dual .preview-modes b{padding:2% 2.5%}.panel-preview.miniature .preview-tile.control.revised{padding:7%}.panel-preview.miniature .preview-tile.control.revised>b{margin-top:6%;font-size:4cqw}.panel-preview.miniature .preview-tile.control.revised>small{font-size:2.7cqw}.panel-preview.miniature .preview-tile.control.revised>strong{font-size:7cqw}.panel-preview.miniature .control-timer{gap:4%;margin-top:5%;padding-top:4%}
`;

if (!customElements.get("ha-panel-nspanel-companion-panel")) {
  customElements.define("ha-panel-nspanel-companion-panel", NSPanelCompanionPanel);
}
if (!customElements.get("nspanel-companion-panel")) {
  customElements.define("nspanel-companion-panel", class extends NSPanelCompanionPanel {});
}
