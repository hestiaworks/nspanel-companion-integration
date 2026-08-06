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

  workspaceRoute(panelId, tab = "general") {
    return `#panel/${encodeURIComponent(panelId)}/${encodeURIComponent(tab)}`;
  }

  parsedWorkspaceRoute() {
    const match = window.location.hash.match(/^#panel\/([^/]+)(?:\/([^/]+))?$/);
    if (!match) return null;
    const tabs = new Set(["general", "pages", "doorbell", "diagnostics", "advanced"]);
    const tab = decodeURIComponent(match[2] || "general");
    return { panelId: decodeURIComponent(match[1]), tab: tabs.has(tab) ? tab : "general" };
  }

  async restoreWorkspaceRoute() {
    const route = this.parsedWorkspaceRoute();
    if (!route) {
      if (this.editor) { this.editor = null; this.render(); }
      return;
    }
    if (!this.loaded) return;
    if (this.editor?.panel.panel_id === route.panelId) {
      this.selectWorkspaceTab(route.tab, false);
      return;
    }
    if (this.panels.some((panel) => panel.panel_id === route.panelId)) {
      await this.editPanel(route.panelId, route.tab, false);
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

  async editPanel(panelId, tab = "general", updateRoute = true) {
    this.busy = true; this.error = ""; this.render();
    try {
      const panel = this.panels.find((item) => item.panel_id === panelId);
      const layout = await this.call({ type: "nspanel_companion/layout/get", panel_id: panelId });
      this.scryptedDoorbells = [];
      for (const bridge of this.scrypted.paired || []) {
        const items = await this.call({ type: "nspanel_companion/scrypted/doorbells", bridge_id: bridge.id });
        this.scryptedDoorbells.push(...items.map((item) => ({ ...item, bridge_id: bridge.id })));
      }
      this.workspaceTab = tab;
      this.editor = { panel, layout: layout || DEFAULT_LAYOUT(`panel-${Date.now()}`) };
      if (updateRoute) history.pushState(null, "", this.workspaceRoute(panelId, tab));
    } catch (error) { this.error = error?.message || "Unable to open editor"; }
    finally { this.busy = false; this.render(); }
  }

  async renamePanel(form) {
    const name = String(new FormData(form).get("panel_name") || "").trim();
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
      this.render();
    } catch (error) {
      this.error = error?.message || "Unable to rename panel";
      this.render();
    } finally { this.busy = false; this.render(); }
  }

  async saveEditor(form) {
    const values = new FormData(form);
    const controls = [...form.querySelectorAll('[name="control_entity"]:checked')].map((item) => item.value);
    const climate = String(values.get("climate_entity") || "");
    const weather = String(values.get("weather_entity") || "");
    const scryptedDoorbell = String(values.get("scrypted_doorbell") || "");
    const [scryptedBridgeId, ...scryptedDeviceParts] = scryptedDoorbell.split("|");
    const scryptedDoorbellId = scryptedDoorbell ? scryptedDeviceParts.join("|") : "";
    const selectedPages = [
      ...(climate ? [{ id: "climate", title: "Thermostat", widgets: [{ type: "thermostat", entity_id: climate }] }] : []),
      ...(weather ? [{ id: "weather", title: "Weather", widgets: [{ type: "weather", entity_id: weather }] }] : []),
      ...(controls.length ? [{ id: "controls", title: "Controls", widgets: controls.slice(0, 12).map((entity_id) => ({ type: "entity_button", entity_id })) }] : []),
    ];
    const pages = selectedPages.length
      ? selectedPages
      : (this.editor.layout.pages || []).length
        ? this.editor.layout.pages
        : DEFAULT_LAYOUT(`fallback-${Date.now()}`).pages;
    const requestedDefault = climate ? "climate" : weather ? "weather" : controls.length ? "controls" : this.editor.layout.default_page_id;
    const defaultPageId = pages.some((page) => page.id === requestedDefault) ? requestedDefault : pages[0].id;
    const layout = {
      schema_version: 1,
      revision: `ui-${Date.now()}`,
      default_page_id: defaultPageId,
      default_page_return_seconds: Number(values.get("return_seconds") || 60),
      weather_cache_max_age_minutes: 360,
      keep_screen_on: values.get("keep_screen_on") === "on",
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
      ${this.editor ? this.editorDialog() : ""}
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

  editorDialog() {
    const { panel, layout } = this.editor;
    const widgets = (layout.pages || []).flatMap((page) => page.widgets || []);
    const climate = widgets.find((item) => item.type === "thermostat")?.entity_id || "";
    const weather = widgets.find((item) => item.type === "weather")?.entity_id || "";
    const selectedControls = new Set(widgets.filter((item) => item.type === "entity_button").map((item) => item.entity_id));
    const controlStates = Object.values(this._hass?.states || {}).filter((item) =>
      ["light", "switch", "fan", "cover", "input_boolean"].includes(item.entity_id.split(".")[0])
    ).sort((a, b) => this.entityLabel(a).localeCompare(this.entityLabel(b)));
    const doorbell = layout.doorbell || {};
    const selectedScrypted = doorbell.scrypted_bridge_id && doorbell.scrypted_doorbell_id
      ? `${doorbell.scrypted_bridge_id}|${doorbell.scrypted_doorbell_id}` : "";
    const online = !panel.revoked && panel.last_seen && Date.now() - new Date(panel.last_seen).getTime() < 45000;
    const tab = this.workspaceTab;
    return `<div class="scrim"><section class="dialog editor workspace"><div class="editor-head"><div><span class="eyebrow">Panel workspace</span><div class="workspace-title"><h2>${escapeHtml(panel.name)}</h2><span class="status ${online ? "online" : "waiting"}">${panel.revoked ? "Revoked" : online ? "Online" : "Offline"}</span></div><p class="device-id">${escapeHtml(panel.device_id)}</p></div><button data-close-editor>Close</button></div>${this.error ? `<div class="notice error">${escapeHtml(this.error)}</div>` : ""}
      <nav class="workspace-tabs" aria-label="Panel configuration">
        ${[["general","General"],["pages","Pages"],["doorbell","Doorbell"],["diagnostics","Diagnostics"],["advanced","Advanced"]].map(([id,label]) => `<button type="button" data-workspace-tab="${id}" class="${tab === id ? "active" : ""}">${label}</button>`).join("")}
      </nav>
      <section class="workspace-panel" data-workspace-panel="general" ${tab === "general" ? "" : "hidden"}>
        <div class="workspace-intro"><h3>Panel identity</h3><p>Give this panel a name that describes its room or purpose. Its stable device ID never changes.</p></div>
        <form id="panel-general" class="settings-card">
          <label>Panel name<input name="panel_name" maxlength="64" required value="${escapeHtml(panel.name)}" placeholder="Living room"></label>
          <label>Stable device ID<input value="${escapeHtml(panel.device_id)}" readonly></label>
          <dl><div><dt>Connection</dt><dd>${panel.revoked ? "Revoked" : online ? "Online" : "Offline"}</dd></div><div><dt>Registered</dt><dd>${formatDate(panel.created_at)}</dd></div><div><dt>App version</dt><dd>${escapeHtml(panel.app_version || "—")}</dd></div></dl>
          <div class="actions"><button class="primary" type="submit" ${this.busy ? "disabled" : ""}>Save name</button></div>
        </form>
      </section>
      <form id="layout-editor" class="workspace-layout-form">
        <section class="workspace-panel" data-workspace-panel="pages" ${tab === "pages" ? "" : "hidden"}>
          <div class="workspace-intro"><h3>Pages</h3><p>Configure the current native dashboard. The full visual page builder will replace these MVP selectors next.</p></div>
          <fieldset><legend>Dashboard</legend>
            <label>Climate entity<select name="climate_entity">${this.entityOptions(["climate"], climate, "No thermostat page")}</select></label>
            <label>Weather entity<select name="weather_entity">${this.entityOptions(["weather"], weather, "No weather page")}</select></label>
            <label>Return to first page after<input name="return_seconds" type="number" min="0" max="3600" value="${Number(layout.default_page_return_seconds ?? 60)}"><small>Seconds; use 0 to disable automatic return.</small></label>
            <label class="check"><input name="keep_screen_on" type="checkbox" ${layout.keep_screen_on ? "checked" : ""}> Keep display on while dashboard is open</label>
            <small>Off by default. When disabled, the panel follows its Android display timeout and automatic brightness settings.</small>
          </fieldset>
          <fieldset><legend>Controls <small>Select up to 12 entities</small></legend><div class="entity-list">
            ${controlStates.map((item) => `<label class="entity-check"><input type="checkbox" name="control_entity" value="${escapeHtml(item.entity_id)}" ${selectedControls.has(item.entity_id) ? "checked" : ""}><span><b>${escapeHtml(item.attributes?.friendly_name || item.entity_id)}</b><small>${escapeHtml(item.entity_id)}</small></span></label>`).join("") || `<p>No compatible controls found.</p>`}
          </div></fieldset>
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
    </section></div>`;
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
  .workspace{padding:0;overflow:hidden}.workspace .editor-head{grid-template-columns:minmax(0,1fr) auto;padding:24px 26px 18px;margin:0}.workspace-title{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.workspace-title h2{margin:0}.workspace-tabs{display:flex;gap:4px;padding:0 26px;border-bottom:1px solid var(--divider-color,#ddd);overflow-x:auto}.workspace-tabs button{border:0;border-bottom:3px solid transparent;border-radius:0;background:transparent;color:var(--secondary-text-color,#777);padding:13px 15px;white-space:nowrap}.workspace-tabs button.active{color:var(--primary-text-color,#171916);border-bottom-color:#f36d21}.workspace-panel{padding:24px 26px;max-height:calc(90vh - 165px);overflow:auto}.workspace-panel[hidden]{display:none}.workspace-intro{margin-bottom:18px}.workspace-intro h3{font-size:20px}.workspace-layout-form{margin:0}.settings-card{max-width:680px;border:1px solid var(--divider-color,#ddd);border-radius:16px;padding:18px;margin:0}.settings-card input[readonly]{font-family:monospace;color:var(--secondary-text-color,#777)}.danger-zone{border-color:#d79a95;background:color-mix(in srgb,var(--card-background-color,#fff) 92%,#b3261e)}.left{justify-content:flex-start}
  :host([narrow]) main{padding:18px}:host([narrow]) .cards{grid-template-columns:1fr}@media(max-width:720px){main{padding:18px}.editor-grid{grid-template-columns:1fr}.entity-list{grid-template-columns:1fr}.cards{grid-template-columns:1fr}.section-title{align-items:flex-start}.panel-card{min-height:175px}.panel-card>.actions{justify-content:stretch}.panel-card>.actions button{width:100%}.panel-head{grid-template-columns:42px minmax(0,1fr) auto}.device-icon{width:42px;height:42px}.editor-head{grid-template-columns:1fr auto}.editor-head .status{grid-column:1}.pairing{grid-template-columns:1fr auto}.pairing .expires{grid-column:1}.pairing button{grid-column:2;grid-row:2}.workspace .editor-head{padding:20px}.workspace-tabs{padding:0 12px}.workspace-panel{padding:20px}.workspace-tabs button{padding:12px 11px}}
`;

if (!customElements.get("ha-panel-nspanel-companion-panel")) {
  customElements.define("ha-panel-nspanel-companion-panel", NSPanelCompanionPanel);
}
if (!customElements.get("nspanel-companion-panel")) {
  customElements.define("nspanel-companion-panel", class extends NSPanelCompanionPanel {});
}
