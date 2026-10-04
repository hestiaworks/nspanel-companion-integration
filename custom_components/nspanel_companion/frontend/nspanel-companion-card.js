// The panel's dashboard card: one panel's readings as 24-hour graphs, and its
// controls, drawing only the entities that are enabled.
//
// Loaded for every user (the admin panel is not), so it stays small and has
// no dependencies. The helpers below are exported so the integration's test
// suite can run them under Node against this very file.

/** The panel's entities, by translation key. Renaming an entity moves none of these. */
export const ROLES = [
  "wifi_signal", "ambient_light", "approach", "connected",
  "display", "page", "restart_app", "reload_layout",
];

const DOMAIN = "nspanel_companion";
export const HISTORY_HOURS = 24;
export const HISTORY_REFRESH_MS = 10 * 60 * 1000;

/** The admin list's bands, so the two never call one reading different things. */
export function wifiBand(dbm) {
  if (typeof dbm !== "number" || !Number.isFinite(dbm)) return null;
  if (dbm >= -55) return { word: "Strong", tone: "good" };
  if (dbm >= -67) return { word: "Good", tone: "good" };
  if (dbm >= -73) return { word: "Weak", tone: "warn" };
  return { word: "Poor", tone: "bad" };
}

/** This device's panel entities, by role. Disabled ones are not in `entities` at all. */
export function panelEntities(entities, deviceId) {
  const roles = {};
  for (const entry of Object.values(entities || {})) {
    if (entry.device_id !== deviceId || entry.platform !== DOMAIN) continue;
    if (ROLES.includes(entry.translation_key)) roles[entry.translation_key] = entry.entity_id;
  }
  return roles;
}

/**
 * History rows as numeric points.
 *
 * Accepts the compressed form Home Assistant sends with minimal_response
 * (`s`, `lu` in seconds) and the long form. A state that is not a number —
 * unavailable while the panel was off, unknown after a restart, empty — is
 * skipped rather than drawn as zero, which would look like a collapse.
 */
export function historyPoints(rows) {
  const points = [];
  for (const row of rows || []) {
    const text = row.s ?? row.state;
    if (text === "" || text === null || text === undefined) continue;
    const value = Number(text);
    if (!Number.isFinite(value)) continue;
    const seconds = row.lu ?? row.lc;
    const time = seconds !== undefined ? seconds * 1000 : Date.parse(row.last_updated ?? row.last_changed ?? "");
    if (!Number.isFinite(time)) continue;
    points.push({ t: time, v: value });
  }
  return points;
}

/** The lowest and highest point, each with when it happened. */
export function extremes(points) {
  if (!points.length) return null;
  let min = points[0];
  let max = points[0];
  for (const point of points) {
    if (point.v < min.v) min = point;
    if (point.v > max.v) max = point;
  }
  return { min: { t: min.t, v: min.v }, max: { t: max.t, v: max.v } };
}

/**
 * An SVG path through the points, inside a 2 px vertical inset.
 *
 * A reading that never moved draws through the middle: a dark room reads the
 * same all day, and dividing by its zero range would draw nothing.
 */
export function sparkPath(points, width, height) {
  if (points.length < 2) return "";
  const inset = 2;
  const t0 = points[0].t;
  const span = points[points.length - 1].t - t0 || 1;
  const values = points.map((point) => point.v);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const y = (value) => high === low
    ? height / 2
    : inset + (height - 2 * inset) * (1 - (value - low) / (high - low));
  return points
    .map((point, index) => `${index ? "L" : "M"}${((point.t - t0) / span * width).toFixed(1)} ${y(point.v).toFixed(1)}`)
    .join(" ");
}

/** "just now", "12 min ago", "3 h ago". */
export function agoText(at, now) {
  const minutes = Math.floor((now - at) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  return `${Math.floor(minutes / 60)} h ago`;
}

const STYLE = `
  :host { display:block; }
  ha-card { overflow:hidden; }
  .head { display:flex; align-items:flex-start; gap:12px; padding:16px 16px 12px; }
  .who { flex:1; min-width:0; }
  .name { font-size:20px; font-weight:500; color:var(--primary-text-color);
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .sub { font-size:14px; color:var(--secondary-text-color); margin-top:2px;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .link { flex:none; display:flex; align-items:center; gap:6px; font-size:14px; color:var(--secondary-text-color); white-space:nowrap; }
  .dot { width:8px; height:8px; border-radius:50%; background:var(--success-color); }
  .offline .dot { background:var(--error-color); }
  /* Side by side on a dashboard column, stacked on a phone. The 1 px gap on
     a divider-coloured ground draws the rule between them either way. */
  .readings { display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:1px;
    background:var(--divider-color); border-top:1px solid var(--divider-color); }
  .reading { padding:12px 16px; min-width:0; background:var(--ha-card-background, var(--card-background-color)); }
  .label { font-size:14px; color:var(--secondary-text-color); }
  .value { font-size:28px; color:var(--primary-text-color); font-variant-numeric:tabular-nums; margin-top:2px; }
  .value small { font-size:14px; color:var(--secondary-text-color); margin-left:4px; }
  .word { font-size:13px; font-weight:500; }
  .word.good { color:var(--success-color); } .word.warn { color:var(--warning-color); } .word.bad { color:var(--error-color); }
  svg { display:block; width:100%; height:40px; margin:8px 0 6px; }
  svg path.line { fill:none; stroke:var(--primary-color); stroke-width:2; vector-effect:non-scaling-stroke; }
  svg path.area { fill:var(--primary-color); opacity:.12; stroke:none; }
  .extremes { display:flex; justify-content:space-between; font-size:12px; color:var(--secondary-text-color); font-variant-numeric:tabular-nums; }
  .extremes div:last-child { text-align:right; }
  .empty { font-size:12px; color:var(--secondary-text-color); margin:20px 0; }
  .row { display:flex; align-items:center; gap:12px; padding:10px 16px; border-top:1px solid var(--divider-color); min-height:40px; }
  .row .label { flex:none; width:80px; }
  .row .grow { flex:1; min-width:0; color:var(--primary-text-color); font-size:14px; }
  input[type=range] { flex:1; min-width:0; accent-color:var(--primary-color); }
  input[type=checkbox] { accent-color:var(--primary-color); width:18px; height:18px; }
  .pct { flex:none; width:44px; text-align:right; font-variant-numeric:tabular-nums; color:var(--primary-text-color); font-size:14px; }
  select { flex:1; min-width:0; height:36px; padding:0 8px; background:var(--card-background-color); color:var(--primary-text-color);
    border:1px solid var(--divider-color); border-radius:4px; font:inherit; }
  .actions { display:flex; gap:8px; padding:10px 16px 16px; border-top:1px solid var(--divider-color); }
  .actions button { flex:1; height:36px; border-radius:4px; border:1px solid var(--divider-color);
    background:transparent; color:var(--primary-color); font:inherit; font-weight:500; cursor:pointer; }
  .actions button.armed { background:var(--error-color); border-color:var(--error-color); color:var(--text-primary-color, white); }
  .offline .controls { opacity:.5; pointer-events:none; }
  .missing { padding:16px; color:var(--secondary-text-color); }
  button:focus-visible, select:focus-visible, input:focus-visible { outline:2px solid var(--primary-color); outline-offset:1px; }
`;

const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const clock = (ms) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

const Base = globalThis.HTMLElement ?? class {};

class NSPanelCompanionCard extends Base {
  setConfig(config) {
    if (!config || !config.device_id) throw new Error("Choose a panel");
    this._config = config;
    this._history = {};
    this._fetchedAt = 0;
    this._signature = "";
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._dragging) return;
    const signature = this._signatureOf(hass);
    if (signature !== this._signature) {
      this._signature = signature;
      this._render();
    }
    this._fetchHistory();
  }

  getCardSize() {
    return 6;
  }

  static getConfigElement() {
    return document.createElement("nspanel-companion-card-editor");
  }

  static getStubConfig(hass) {
    const device = Object.values(hass?.devices || {}).find((entry) =>
      (entry.identifiers || []).some(([domain]) => domain === DOMAIN));
    return { device_id: device?.id ?? "" };
  }

  _roles() {
    return panelEntities(this._hass?.entities, this._config?.device_id);
  }

  /** What the card draws from; a redraw happens only when this changes. */
  _signatureOf(hass) {
    const device = hass?.devices?.[this._config?.device_id];
    const states = Object.values(this._roles()).map((id) => {
      const state = hass?.states?.[id];
      return [id, state?.state, state?.last_changed, state?.attributes?.brightness, (state?.attributes?.options || []).join("|")];
    });
    return JSON.stringify([device?.name_by_user, device?.name, device?.area_id, device?.sw_version, states]);
  }

  async _fetchHistory() {
    const roles = this._roles();
    const ids = [roles.wifi_signal, roles.ambient_light].filter(Boolean);
    if (!ids.length || !this._hass?.callWS || this._fetching) return;
    if (Date.now() - this._fetchedAt < HISTORY_REFRESH_MS) return;
    this._fetching = true;
    try {
      const end = new Date();
      const start = new Date(end.getTime() - HISTORY_HOURS * 3600 * 1000);
      const result = await this._hass.callWS({
        type: "history/history_during_period",
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        entity_ids: ids,
        minimal_response: true,
        no_attributes: true,
      });
      this._history = Object.fromEntries(ids.map((id) => [id, historyPoints(result?.[id])]));
      this._fetchedAt = Date.now();
      this._render();
    } catch (error) {
      // A card that cannot read history still shows the live values.
      this._fetchedAt = Date.now();
    } finally {
      this._fetching = false;
    }
  }

  _state(id) {
    return id ? this._hass?.states?.[id] : undefined;
  }

  /** Offline when the connected entity says so, or the readings have gone unavailable. */
  _offline(roles) {
    const connected = this._state(roles.connected);
    if (connected) return connected.state !== "on" ? connected : null;
    const reading = this._state(roles.wifi_signal) || this._state(roles.ambient_light);
    return reading && reading.state === "unavailable" ? reading : null;
  }

  _call(domain, service, data) {
    this._hass?.callService(domain, service, data);
  }

  _render() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    if (!this._config || !this._hass) return;
    const roles = this._roles();
    const device = this._hass.devices?.[this._config.device_id];
    if (!device || !Object.keys(roles).length) {
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="missing">This panel was not found. Choose another panel in the card's settings.</div></ha-card>`;
      return;
    }
    const offline = this._offline(roles);
    const name = device.name_by_user || device.name || "Panel";
    const area = this._hass.areas?.[device.area_id]?.name;
    const sub = [area, device.sw_version].filter(Boolean).join(" · ");
    const link = offline
      ? `<div class="link"><span class="dot"></span>Offline since ${escapeHtml(clock(Date.parse(offline.last_changed)))}</div>`
      : roles.connected ? `<div class="link"><span class="dot"></span>Connected</div>` : "";

    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card class="${offline ? "offline" : ""}">
        <div class="head"><div class="who"><div class="name">${escapeHtml(name)}</div>${sub ? `<div class="sub">${escapeHtml(sub)}</div>` : ""}</div>${link}</div>
        ${this._readings(roles)}
        ${this._approach(roles)}
        <div class="controls">${this._display(roles)}${this._page(roles)}${this._actions(roles)}</div>
      </ha-card>`;
    this._bind(roles);
  }

  _graph(id, unit, describe) {
    const state = this._state(id);
    const live = Number(state?.state);
    const points = this._history[id] || [];
    const path = sparkPath(points, 100, 40);
    const range = extremes(points);
    const value = Number.isFinite(live) ? live.toLocaleString() : "—";
    const word = describe?.(live);
    return `<div class="reading">
      <div class="label">${unit === "dBm" ? "Wifi" : "Light"}</div>
      <div class="value">${escapeHtml(value)}${unit && Number.isFinite(live) ? `<small>${unit}</small>` : ""}</div>
      ${word ? `<div class="word ${word.tone}">${word.word}</div>` : ""}
      ${path ? `<svg viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true"><path class="area" d="${path} L100 40 L0 40 Z"></path><path class="line" d="${path}"></path></svg>`
        : `<div class="empty">No history yet</div>`}
      ${range ? `<div class="extremes"><div>Min ${escapeHtml(range.min.v.toLocaleString())}<br>${clock(range.min.t)}</div><div>Max ${escapeHtml(range.max.v.toLocaleString())}<br>${clock(range.max.t)}</div></div>` : ""}
    </div>`;
  }

  _readings(roles) {
    const graphs = [];
    if (roles.wifi_signal) graphs.push(this._graph(roles.wifi_signal, "dBm", wifiBand));
    if (roles.ambient_light) graphs.push(this._graph(roles.ambient_light, "", null));
    return graphs.length ? `<div class="readings">${graphs.join("")}</div>` : "";
  }

  _approach(roles) {
    const state = this._state(roles.approach);
    if (!state) return "";
    const near = state.state === "on";
    return `<div class="row"><div class="label">Approach</div><div class="grow">${near ? "Someone nearby" : "Nobody nearby"} · ${agoText(Date.parse(state.last_changed), Date.now())}</div></div>`;
  }

  _display(roles) {
    const state = this._state(roles.display);
    if (!state) return "";
    const on = state.state === "on";
    const percent = Math.round((state.attributes?.brightness ?? 0) / 2.55);
    return `<div class="row"><div class="label">Display</div>
      <input type="checkbox" id="display-on" aria-label="Display on" ${on ? "checked" : ""}>
      <input type="range" id="display-level" min="1" max="100" value="${percent || 1}" aria-label="Brightness">
      <div class="pct" id="display-pct">${on && percent ? `${percent}%` : "—"}</div></div>`;
  }

  _page(roles) {
    const state = this._state(roles.page);
    if (!state) return "";
    const options = state.attributes?.options || [];
    return `<div class="row"><div class="label">Page</div><select id="page" aria-label="Page">${options
      .map((option) => `<option value="${escapeHtml(option)}" ${option === state.state ? "selected" : ""}>${escapeHtml(option)}</option>`)
      .join("")}</select></div>`;
  }

  _actions(roles) {
    const buttons = [];
    if (roles.reload_layout) buttons.push(`<button type="button" id="reload">Reload layout</button>`);
    if (roles.restart_app) buttons.push(`<button type="button" id="restart">Restart app</button>`);
    return buttons.length ? `<div class="actions">${buttons.join("")}</div>` : "";
  }

  _bind(roles) {
    const root = this.shadowRoot;
    root.getElementById("display-on")?.addEventListener("change", (event) => {
      if (event.target.checked) this._call("light", "turn_on", { entity_id: roles.display });
      else this._call("light", "turn_off", { entity_id: roles.display });
    });
    const level = root.getElementById("display-level");
    if (level) {
      // While a finger is on the slider, state updates would redraw the card
      // and yank it back; the value is sent once, on release.
      level.addEventListener("input", () => {
        this._dragging = true;
        root.getElementById("display-pct").textContent = `${level.value}%`;
      });
      level.addEventListener("change", () => {
        this._dragging = false;
        this._call("light", "turn_on", { entity_id: roles.display, brightness_pct: Number(level.value) });
      });
    }
    root.getElementById("page")?.addEventListener("change", (event) =>
      this._call("select", "select_option", { entity_id: roles.page, option: event.target.value }));
    root.getElementById("reload")?.addEventListener("click", () =>
      this._call("button", "press", { entity_id: roles.reload_layout }));
    const restart = root.getElementById("restart");
    restart?.addEventListener("click", () => {
      // Two taps: a restart blanks the panel for a few seconds, and a
      // dashboard is easy to brush. No browser dialog: the card owns the question.
      if (!restart.classList.contains("armed")) {
        restart.classList.add("armed");
        restart.textContent = "Tap again to restart";
        setTimeout(() => {
          restart.classList.remove("armed");
          restart.textContent = "Restart app";
        }, 4000);
        return;
      }
      this._call("button", "press", { entity_id: roles.restart_app });
      restart.classList.remove("armed");
      restart.textContent = "Restart app";
    });
  }
}

if (globalThis.customElements && !customElements.get("nspanel-companion-card")) {
  customElements.define("nspanel-companion-card", NSPanelCompanionCard);
}
