#!/usr/bin/env node

/*
 * Dependency-free Home Assistant test double plus embedded control webpage.
 *
 * Run:
 *   node tools/ha-test-server.js
 *
 * Browser:
 *   http://127.0.0.1:8124
 *
 * Android emulator:
 *   http://10.0.2.2:8124
 *   token: test-token
 */

const crypto = require("node:crypto");
const childProcess = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");

const host = process.env.HOST || "0.0.0.0";
const port = Number(process.env.PORT || 8124);
const expectedToken = process.env.TEST_TOKEN || "test-token";
const mediaApiPort = Number(process.env.MEDIA_API_PORT || 1985);
const mediaWebRtcPort = Number(process.env.MEDIA_WEBRTC_PORT || 8556);
const mediaStreamName = process.env.MEDIA_STREAM_NAME || "native_test";
const clients = new Set();
const logEntries = [];
let mediaProcess = null;
let mediaStartedAt = null;
let talkbackRecording = null;
let talkbackUpdatedAt = null;
let talkbackLevel = { active: false, rms: 0, peak: 0 };
const pairingRequests = new Map();
const authorizedPanels = new Map();

const states = new Map([
  ["climate.test_room", {
    entity_id: "climate.test_room",
    state: "heat",
    attributes: {
      friendly_name: "Test Room",
      current_temperature: 21.5,
      temperature: 22,
      min_temp: 7,
      max_temp: 35,
      target_temp_step: 0.5,
      temperature_unit: "°C",
      hvac_modes: ["heat", "cool", "heat_cool", "dry", "off"],
      hvac_action: "heating",
    },
  }],
  ["weather.test_home", {
    entity_id: "weather.test_home",
    state: "sunny",
    attributes: {
      friendly_name: "Test Weather",
      temperature: 24,
      apparent_temperature: 25,
      humidity: 48,
      wind_speed: 6,
      temperature_unit: "°C",
      forecast_summary: "Sunny through the evening. Light wind with no rain expected.",
      forecast_days: 5,
      forecast: [
        { label: "Sat", condition: "sunny", templow: 16, temperature: 24 },
        { label: "Sun", condition: "cloudy", templow: 15, temperature: 21 },
        { label: "Mon", condition: "rainy", templow: 14, temperature: 19 },
        { label: "Tue", condition: "partlycloudy", templow: 16, temperature: 22 },
        { label: "Wed", condition: "sunny", templow: 17, temperature: 25 },
      ],
      hourly_forecast: [
        { label: "Now", condition: "sunny", temperature: 24 },
        { label: "18", condition: "sunny", temperature: 23 },
        { label: "19", condition: "sunny", temperature: 22 },
        { label: "20", condition: "partlycloudy", temperature: 21 },
        { label: "21", condition: "clear-night", temperature: 20 },
        { label: "22", condition: "clear-night", temperature: 19 },
      ],
    },
  }],
  ["light.test_ceiling", {
    entity_id: "light.test_ceiling",
    state: "on",
    attributes: { friendly_name: "Floor Lamp", brightness: 184, supported_color_modes: ["brightness"] },
  }],
  ["switch.test_fan", {
    entity_id: "switch.test_fan",
    state: "off",
    attributes: { friendly_name: "Ceiling Light" },
  }],
  ["fan.test_ceiling", {
    entity_id: "fan.test_ceiling",
    state: "on",
    attributes: { friendly_name: "Ceiling Fan", percentage: 50, percentage_step: 25 },
  }],
  ["cover.test_blinds", {
    entity_id: "cover.test_blinds",
    state: "open",
    attributes: { friendly_name: "Window Blinds", current_position: 65 },
  }],
]);

function addLog(message) {
  const entry = `${new Date().toLocaleTimeString()}  ${message}`;
  logEntries.unshift(entry);
  logEntries.splice(100);
  process.stdout.write(`${entry}\n`);
}

function jsonResponse(response, status, value) {
  const body = JSON.stringify(value);
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
    "Cache-Control": "no-store",
  });
  response.end(body);
}

function readJson(request) {
  return new Promise((resolve, reject) => {
    let body = "";
    request.setEncoding("utf8");
    request.on("data", chunk => {
      body += chunk;
      if (body.length > 64 * 1024) request.destroy();
    });
    request.on("end", () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (error) {
        reject(error);
      }
    });
    request.on("error", reject);
  });
}

function publicStatus() {
  return {
    connectedPanels: [...clients].filter(client => client.authenticated).length,
    socketCount: clients.size,
    states: [...states.values()],
    logs: logEntries.slice(0, 40),
    serverUrl: `http://127.0.0.1:${port}`,
    emulatorUrl: `http://10.0.2.2:${port}`,
    token: expectedToken,
    media: {
      available: Boolean(findGo2rtc()),
      running: Boolean(mediaProcess),
      pid: mediaProcess?.pid || null,
      streamName: mediaStreamName,
      emulatorUrl: `http://10.0.2.2:${mediaApiPort}`,
      startedAt: mediaStartedAt,
    },
    talkback: {
      ...talkbackLevel,
      hasRecording: Boolean(talkbackRecording),
      bytes: talkbackRecording?.length || 0,
      updatedAt: talkbackUpdatedAt,
    },
  };
}

function broadcastEvent(eventType, data = {}) {
  let sent = 0;
  for (const client of clients) {
    if (client.mode === "panel") {
      if (eventType === "nspanel_doorbell") {
        sendJson(client.socket, { type: "doorbell", data });
        sent++;
      }
      continue;
    }
    if (!client.authenticated) continue;
    const subscriptionId = client.subscriptions.get(eventType);
    if (subscriptionId === undefined) continue;
    sendJson(client.socket, {
      id: subscriptionId,
      type: "event",
      event: {
        event_type: eventType,
        data,
        origin: "LOCAL",
        time_fired: new Date().toISOString(),
        context: { id: crypto.randomUUID().replaceAll("-", "") },
      },
    });
    sent++;
  }
  addLog(`Event ${eventType} sent to ${sent} panel(s)`);
  return sent;
}

function broadcastState(entity) {
  broadcastEvent("state_changed", {
    entity_id: entity.entity_id,
    old_state: null,
    new_state: entity,
  });
  for (const client of clients) {
    if (client.mode === "panel") sendJson(client.socket, { type: "state_changed", state: entity });
  }
}

const page = String.raw`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HA Companion Test Harness</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; }
    body { margin: 0; background: #101416; color: #eef4f5; }
    main { max-width: 900px; margin: auto; padding: 24px; }
    h1 { margin-bottom: 6px; }
    .muted { color: #9eabad; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(260px,1fr)); gap: 16px; }
    .card { background: #1b2224; border: 1px solid #344145; border-radius: 12px; padding: 18px; }
    button { border: 0; border-radius: 9px; padding: 12px 16px; margin: 4px 4px 4px 0;
      background: #27a6a1; color: white; font-weight: 700; cursor: pointer; }
    button.danger { background: #b44b55; }
    button.secondary { background: #46565b; }
    input, select { width: 100%; box-sizing: border-box; margin: 5px 0 10px; padding: 10px;
      color: white; background: #101416; border: 1px solid #526266; border-radius: 7px; }
    code { color: #9be0db; user-select: all; }
    #status { font-size: 1.15rem; font-weight: 700; }
    #log { min-height: 180px; max-height: 350px; overflow: auto; white-space: pre-wrap;
      font: 12px ui-monospace, monospace; }
    .meter { height: 18px; overflow: hidden; background: #101416; border-radius: 9px; }
    #micLevel { width: 0; height: 100%; background: #27a6a1; transition: width .15s linear; }
  </style>
</head>
<body><main>
  <h1>HA Companion Test Harness</h1>
  <p class="muted">A tiny Home Assistant WebSocket test double for the Android panel.</p>
  <div class="grid">
    <section class="card">
      <h2>Panel connection</h2>
      <div id="status">Loading…</div>
      <p>Emulator URL: <code id="emulatorUrl"></code></p>
      <p>Token: <code id="token"></code></p>
      <button class="danger" onclick="post('/api/disconnect')">Disconnect panels</button>
    </section>
    <section class="card">
      <h2>Doorbell</h2>
      <p>Emulates the HA event and includes the synthetic stream coordinates.</p>
      <label>Auto-close seconds</label>
      <input id="autoClose" type="number" min="10" max="300" value="60">
      <button onclick="ring(1, false)">Ring doorbell</button>
      <button class="secondary" onclick="ring(1, true)">Quiet ring</button>
      <button class="secondary" onclick="ring(3, false)">Ring 3× quickly</button>
    </section>
    <section class="card">
      <h2>Synthetic media</h2>
      <div id="mediaStatus">Loading…</div>
      <p class="muted">Stop and restart it while the doorbell is visible to test reconnect.</p>
      <button onclick="post('/api/media/start')">Start / recover stream</button>
      <button class="danger" onclick="post('/api/media/stop')">Stop stream</button>
    </section>
    <section class="card">
      <h2>Talkback microphone</h2>
      <div class="meter"><div id="micLevel"></div></div>
      <p id="micStatus" class="muted">Waiting for push-to-talk…</p>
      <audio id="talkbackAudio" controls></audio>
      <p><button class="secondary" onclick="playTalkback()">Play last recording</button></p>
    </section>
    <section class="card">
      <h2>Entity state</h2>
      <label>Entity</label>
      <select id="entity">
        <option>light.test_ceiling</option>
        <option>switch.test_fan</option>
        <option>fan.test_ceiling</option>
        <option>cover.test_blinds</option>
        <option>climate.test_room</option>
        <option>weather.test_home</option>
      </select>
      <label>State</label>
      <input id="state" value="on">
      <button onclick="sendState()">Send state_changed</button>
      <p><button class="secondary" onclick="post('/api/climate-mode', {mode:'single'})">Single target</button>
      <button class="secondary" onclick="post('/api/climate-mode', {mode:'dual'})">Heat + cool</button></p>
    </section>
    <section class="card">
      <h2>Dashboard layout</h2>
      <p class="muted">Publishes a validated layout revision through the same HA event path planned for the integration.</p>
      <button onclick="post('/api/layout', {preset:'room'})">Publish room layout</button>
      <button class="secondary" onclick="post('/api/layout', {preset:'default'})">Restore default layout</button>
    </section>
    <section class="card">
      <h2>Server log</h2>
      <div id="log"></div>
    </section>
  </div>
  <script>
    async function post(path, value = {}) {
      await fetch(path, {method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify(value)});
      await refresh();
    }
    function sendState() {
      return post('/api/state', {
        entity_id: document.querySelector('#entity').value,
        state: document.querySelector('#state').value,
      });
    }
    function ring(count, quiet_mode) {
      const auto_close_ms = Number(document.querySelector('#autoClose').value) * 1000;
      return post('/api/doorbell', {count, quiet_mode, auto_close_ms});
    }
    function playTalkback() {
      const audio = document.querySelector('#talkbackAudio');
      audio.src = '/api/talkback.wav?t=' + Date.now();
      audio.play();
    }
    async function refresh() {
      const status = await fetch('/api/status', {cache:'no-store'}).then(r => r.json());
      document.querySelector('#status').textContent =
        status.connectedPanels + ' authenticated panel(s) connected';
      document.querySelector('#emulatorUrl').textContent = status.emulatorUrl;
      document.querySelector('#token').textContent = status.token;
      document.querySelector('#mediaStatus').textContent = status.media.running
        ? 'Running · ' + status.media.streamName + ' · PID ' + status.media.pid
        : (status.media.available ? 'Stopped' : 'go2rtc binary not found');
      const level = Math.min(100, Math.round(status.talkback.rms * 400));
      document.querySelector('#micLevel').style.width = level + '%';
      document.querySelector('#micStatus').textContent = status.talkback.active
        ? 'Recording · RMS ' + status.talkback.rms.toFixed(3) + ' · peak ' + status.talkback.peak.toFixed(3)
        : (status.talkback.hasRecording
          ? 'Last recording: ' + status.talkback.bytes + ' bytes'
          : 'Waiting for push-to-talk…');
      document.querySelector('#log').textContent = status.logs.join('\n');
    }
    refresh();
    setInterval(refresh, 1000);
  </script>
</main></body></html>`;

const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);
    if (request.method === "GET" && url.pathname === "/") {
      response.writeHead(200, {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
      });
      response.end(page);
      return;
    }
    if (request.method === "GET" && url.pathname === "/roadmap") {
      const roadmap = fs.readFileSync(path.join(__dirname, "../docs/roadmap.html"));
      response.writeHead(200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Length": roadmap.length,
        "Cache-Control": "no-store",
      });
      response.end(roadmap);
      return;
    }
    if (request.method === "GET" && url.pathname === "/design") {
      const design = fs.readFileSync(path.join(__dirname, "../docs/design-playground.html"));
      response.writeHead(200, {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Length": design.length,
        "Cache-Control": "no-store",
      });
      response.end(design);
      return;
    }
    if (request.method === "GET" && url.pathname === "/ha-panel-preview") {
      const preview = fs.readFileSync(path.join(__dirname, "ha-panel-preview.html"));
      response.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Content-Length": preview.length });
      response.end(preview);
      return;
    }
    if (request.method === "GET" && url.pathname === "/nspanel-companion-panel.js") {
      const panel = fs.readFileSync(path.join(__dirname, "../custom_components/nspanel_companion/frontend/nspanel-companion-panel.js"));
      response.writeHead(200, { "Content-Type": "text/javascript; charset=utf-8", "Content-Length": panel.length, "Cache-Control": "no-store" });
      response.end(panel);
      return;
    }
    if (request.method === "GET" && url.pathname === "/api/status") {
      jsonResponse(response, 200, publicStatus());
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/nspanel_companion/pair/start") {
      const body = await readJson(request);
      const requestId = crypto.randomBytes(12).toString("hex");
      const claim = crypto.randomBytes(24).toString("base64url");
      pairingRequests.set(requestId, { deviceId: body.device_id, claim, polls: 0 });
      jsonResponse(response, 200, { request_id: requestId, device_id: body.device_id, code: "482731", claim, expires_in: 300, status: "pending" });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/nspanel_companion/pair/status") {
      const body = await readJson(request);
      const pairing = pairingRequests.get(body.request_id);
      if (!pairing || pairing.claim !== body.claim) {
        jsonResponse(response, 400, { error: "Unknown pairing request" });
        return;
      }
      pairing.polls += 1;
      if (pairing.polls < 2) jsonResponse(response, 200, { status: "pending", expires_in: 295 });
      else {
        pairingRequests.delete(body.request_id);
        const token = crypto.randomBytes(32).toString("base64url");
        authorizedPanels.set(pairing.deviceId, { token, lastSeen: null, layout: {
          schema_version: 1, revision: `target-${pairing.deviceId.slice(-6)}`, default_page_id: "climate",
          default_page_return_seconds: 60, weather_cache_max_age_minutes: 360,
          pages: [
            { id: "climate", title: "Thermostat", widgets: [{ type: "thermostat" }] },
            { id: "weather", title: "Weather", widgets: [{ type: "weather" }] },
            { id: "controls", title: "Controls", widgets: [{ type: "controls" }] },
          ],
        }});
        jsonResponse(response, 200, { status: "approved", panel_id: pairing.deviceId, token });
      }
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/nspanel_companion/panel/sync") {
      const body = await readJson(request);
      const panel = authorizedPanels.get(body.panel_id);
      const token = String(request.headers.authorization || "").replace(/^Bearer /, "");
      if (!panel || token !== panel.token) {
        jsonResponse(response, 401, { error: "Invalid panel credentials" });
        return;
      }
      panel.lastSeen = new Date().toISOString();
      jsonResponse(response, 200, {
        panel_id: body.panel_id,
        layout_revision: panel.layout.revision,
        layout: body.layout_revision === panel.layout.revision ? null : panel.layout,
        heartbeat_seconds: 15,
      });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/doorbell") {
      const body = await readJson(request);
      const count = Math.max(1, Math.min(10, Number(body.count || 1)));
      let sent = 0;
      for (let index = 0; index < count; index++) {
        sent += broadcastEvent("nspanel_doorbell", {
          source: "test_harness",
          stream_base_url: `http://10.0.2.2:${mediaApiPort}`,
          stream_name: mediaStreamName,
          talkback_test_url: `http://10.0.2.2:${port}/api/talkback`,
          quiet_mode: Boolean(body.quiet_mode),
          auto_close_ms: Math.max(10_000, Math.min(300_000, Number(body.auto_close_ms || 60_000))),
        });
      }
      jsonResponse(response, 200, { ok: true, sent, count });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/media/start") {
      const result = startMedia();
      jsonResponse(response, result.ok ? 200 : 503, result);
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/media/stop") {
      stopMedia();
      jsonResponse(response, 200, { ok: true });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/talkback/level") {
      const body = await readJson(request);
      talkbackLevel = {
        active: Boolean(body.active),
        rms: Math.max(0, Math.min(1, Number(body.rms) || 0)),
        peak: Math.max(0, Math.min(1, Number(body.peak) || 0)),
      };
      jsonResponse(response, 200, { ok: true });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/talkback") {
      const chunks = [];
      let size = 0;
      for await (const chunk of request) {
        size += chunk.length;
        if (size > 10 * 1024 * 1024) throw new Error("Talkback recording is too large");
        chunks.push(chunk);
      }
      talkbackRecording = Buffer.concat(chunks);
      talkbackUpdatedAt = new Date().toISOString();
      talkbackLevel = { active: false, rms: 0, peak: 0 };
      addLog(`Talkback recording received (${talkbackRecording.length} bytes)`);
      jsonResponse(response, 200, { ok: true, bytes: talkbackRecording.length });
      return;
    }
    if (request.method === "GET" && url.pathname === "/api/talkback.wav") {
      if (!talkbackRecording) {
        jsonResponse(response, 404, { error: "No talkback recording yet" });
        return;
      }
      response.writeHead(200, {
        "Content-Type": "audio/wav",
        "Content-Length": talkbackRecording.length,
        "Cache-Control": "no-store",
      });
      response.end(talkbackRecording);
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/state") {
      const body = await readJson(request);
      const current = states.get(body.entity_id);
      if (!current) {
        jsonResponse(response, 404, { ok: false, error: "Unknown entity" });
        return;
      }
      const updated = { ...current, state: String(body.state), last_updated: new Date().toISOString() };
      states.set(updated.entity_id, updated);
      broadcastState(updated);
      jsonResponse(response, 200, { ok: true, state: updated });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/climate-mode") {
      const body = await readJson(request);
      const current = states.get("climate.test_room");
      const attributes = { ...current.attributes };
      if (body.mode === "dual") {
        delete attributes.temperature;
        attributes.target_temp_low = 20;
        attributes.target_temp_high = 24;
        attributes.hvac_action = "idle";
        states.set(current.entity_id, { ...current, state: "heat_cool", attributes });
      } else {
        delete attributes.target_temp_low;
        delete attributes.target_temp_high;
        attributes.temperature = 22;
        attributes.hvac_action = "heating";
        states.set(current.entity_id, { ...current, state: "heat", attributes });
      }
      broadcastState(states.get(current.entity_id));
      jsonResponse(response, 200, { ok: true, mode: body.mode });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/layout") {
      const body = await readJson(request);
      const roomLayout = {
        schema_version: 1,
        revision: `test-room-${Date.now()}`,
        default_page_id: "room",
        default_page_return_seconds: Number(body.return_seconds ?? 60),
        weather_cache_max_age_minutes: Number(body.weather_cache_minutes ?? 360),
        pages: [
          { id: "room", title: "Room controls", widgets: [
            { type: "entity_button", entity_id: "light.test_ceiling", label: "Ceiling" },
            { type: "entity_button", entity_id: "switch.test_fan", label: "Fan" },
            { type: "sensor", entity_id: "weather.test_home", label: "Outside" },
          ]},
          { id: "temperature", title: "Climate", widgets: [
            { type: "thermostat", entity_id: "climate.test_room", label: "Test room" },
          ]},
        ],
      };
      const defaultLayout = {
        schema_version: 1, revision: `test-default-${Date.now()}`, default_page_id: "climate",
        default_page_return_seconds: Number(body.return_seconds ?? 60),
        weather_cache_max_age_minutes: Number(body.weather_cache_minutes ?? 360),
        pages: [
          { id: "climate", title: "Thermostat", widgets: [{ type: "thermostat" }] },
          { id: "weather", title: "Weather", widgets: [{ type: "weather" }] },
          { id: "controls", title: "Controls", widgets: [{ type: "controls" }] },
        ],
      };
      const layout = body.preset === "default" ? defaultLayout : roomLayout;
      const sent = broadcastEvent("nspanel_layout", { layout });
      jsonResponse(response, 200, { ok: true, sent, revision: layout.revision });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/disconnect") {
      for (const client of clients) client.socket.destroy();
      addLog("All panel sockets disconnected");
      jsonResponse(response, 200, { ok: true });
      return;
    }
    jsonResponse(response, 404, { error: "Not found" });
  } catch (error) {
    jsonResponse(response, 500, { error: error.message });
  }
});

server.on("upgrade", (request, socket) => {
  const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);
  const isHaSocket = url.pathname === "/api/websocket";
  const isPanelSocket = url.pathname === "/api/nspanel_companion/panel/ws";
  if ((!isHaSocket && !isPanelSocket) || request.headers.upgrade?.toLowerCase() !== "websocket") {
    socket.end("HTTP/1.1 404 Not Found\r\n\r\n");
    return;
  }
  let panelId = null;
  if (isPanelSocket) {
    panelId = url.searchParams.get("panel_id");
    const panel = authorizedPanels.get(panelId);
    const token = String(request.headers.authorization || "").replace(/^Bearer /, "");
    if (!panel || token !== panel.token) {
      socket.end("HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n");
      return;
    }
  }
  const key = request.headers["sec-websocket-key"];
  if (!key) {
    socket.end("HTTP/1.1 400 Bad Request\r\n\r\n");
    return;
  }
  const accept = crypto
    .createHash("sha1")
    .update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`)
    .digest("base64");
  socket.write([
    "HTTP/1.1 101 Switching Protocols",
    "Upgrade: websocket",
    "Connection: Upgrade",
    `Sec-WebSocket-Accept: ${accept}`,
    "\r\n",
  ].join("\r\n"));

  const client = {
    socket,
    mode: isPanelSocket ? "panel" : "ha",
    panelId,
    authenticated: isPanelSocket,
    subscriptions: new Map(),
    buffer: Buffer.alloc(0),
  };
  clients.add(client);
  addLog(`${isPanelSocket ? `Scoped panel ${panelId}` : "HA panel"} socket opened from ${socket.remoteAddress}`);
  if (isPanelSocket) {
    authorizedPanels.get(panelId).lastSeen = new Date().toISOString();
    sendJson(socket, { type: "initial_states", states: [...states.values()] });
  } else {
    sendJson(socket, { type: "auth_required", ha_version: "2026.7.0-test" });
  }

  socket.on("data", chunk => {
    client.buffer = Buffer.concat([client.buffer, chunk]);
    parseFrames(client);
  });
  socket.on("close", () => {
    clients.delete(client);
    addLog("Panel socket closed");
  });
  socket.on("error", error => addLog(`Panel socket error: ${error.message}`));
});

function parseFrames(client) {
  while (client.buffer.length >= 2) {
    const first = client.buffer[0];
    const second = client.buffer[1];
    const opcode = first & 0x0f;
    const masked = Boolean(second & 0x80);
    let length = second & 0x7f;
    let offset = 2;
    if (length === 126) {
      if (client.buffer.length < 4) return;
      length = client.buffer.readUInt16BE(2);
      offset = 4;
    } else if (length === 127) {
      if (client.buffer.length < 10) return;
      const value = client.buffer.readBigUInt64BE(2);
      if (value > BigInt(Number.MAX_SAFE_INTEGER)) return client.socket.destroy();
      length = Number(value);
      offset = 10;
    }
    const maskLength = masked ? 4 : 0;
    if (client.buffer.length < offset + maskLength + length) return;
    const mask = masked ? client.buffer.subarray(offset, offset + 4) : null;
    offset += maskLength;
    const payload = Buffer.from(client.buffer.subarray(offset, offset + length));
    client.buffer = client.buffer.subarray(offset + length);
    if (mask) {
      for (let index = 0; index < payload.length; index++) payload[index] ^= mask[index % 4];
    }
    if (opcode === 0x8) {
      sendFrame(client.socket, 0x8, payload);
      client.socket.end();
    } else if (opcode === 0x9) {
      sendFrame(client.socket, 0xA, payload);
    } else if (opcode === 0x1) {
      handlePanelMessage(client, payload.toString("utf8"));
    }
  }
}

function handlePanelMessage(client, text) {
  let message;
  try {
    message = JSON.parse(text);
  } catch {
    return;
  }
  if (client.mode === "panel") {
    if (message.type !== "call_service" || !Number.isInteger(message.id)) return;
    const current = states.get(message.entity_id);
    if (!current || !scopedServiceAllowed(message, current)) {
      sendJson(client.socket, { type: "call_result", id: message.id, success: false, error: "not_allowed" });
      return;
    }
    applyServiceCall({ ...message, target: { entity_id: message.entity_id } });
    sendJson(client.socket, { type: "call_result", id: message.id, success: true });
    return;
  }
  if (message.type === "auth") {
    if (message.access_token !== expectedToken) {
      sendJson(client.socket, { type: "auth_invalid", message: "Invalid test token" });
      return client.socket.end();
    }
    client.authenticated = true;
    sendJson(client.socket, { type: "auth_ok", ha_version: "2026.7.0-test" });
    addLog("Panel authenticated");
    return;
  }
  if (!client.authenticated || !Number.isInteger(message.id)) return;
  if (message.type === "subscribe_events") {
    client.subscriptions.set(message.event_type, message.id);
    sendJson(client.socket, { id: message.id, type: "result", success: true, result: null });
    addLog(`Panel subscribed to ${message.event_type}`);
  } else if (message.type === "get_states") {
    sendJson(client.socket, {
      id: message.id,
      type: "result",
      success: true,
      result: [...states.values()],
    });
  } else if (message.type === "call_service") {
    applyServiceCall(message);
    sendJson(client.socket, { id: message.id, type: "result", success: true, result: null });
  }
}

function scopedServiceAllowed(message, current) {
  const domain = current.entity_id.split(".")[0];
  if (message.domain !== domain) return false;
  const allowed = {
    climate: ["set_temperature", "set_hvac_mode"],
    light: ["toggle", "turn_on", "turn_off"],
    switch: ["toggle", "turn_on", "turn_off"],
    input_boolean: ["toggle", "turn_on", "turn_off"],
    fan: ["toggle", "turn_on", "turn_off", "set_percentage"],
    cover: ["open_cover", "close_cover", "stop_cover", "set_cover_position"],
  };
  return allowed[domain]?.includes(message.service) === true;
}

function applyServiceCall(message) {
  const entityId = message.target?.entity_id;
  const current = states.get(entityId);
  if (!current) return;
  let updated = { ...current, attributes: { ...current.attributes } };
  if (message.domain === "climate" && message.service === "set_temperature") {
    if (message.service_data?.temperature != null) {
      updated.attributes.temperature = Number(message.service_data.temperature);
    }
    if (message.service_data?.target_temp_low != null) {
      updated.attributes.target_temp_low = Number(message.service_data.target_temp_low);
    }
    if (message.service_data?.target_temp_high != null) {
      updated.attributes.target_temp_high = Number(message.service_data.target_temp_high);
    }
  } else if (message.domain === "climate" && message.service === "set_hvac_mode") {
    updated.state = String(message.service_data?.hvac_mode || current.state);
    updated.attributes.hvac_action = updated.state === "off" ? "off" : "idle";
  } else if (message.domain === "light" && message.service === "turn_on") {
    updated.state = "on";
    if (message.service_data?.brightness_pct != null) {
      updated.attributes.brightness = Math.round(Number(message.service_data.brightness_pct) * 2.55);
    }
  } else if (message.domain === "fan" && message.service === "set_percentage") {
    updated.attributes.percentage = Number(message.service_data?.percentage || 0);
    updated.state = updated.attributes.percentage > 0 ? "on" : "off";
  } else if (message.domain === "cover" && message.service === "set_cover_position") {
    updated.attributes.current_position = Number(message.service_data?.position || 0);
    updated.state = updated.attributes.current_position > 0 ? "open" : "closed";
  } else if (message.domain === "cover" && message.service === "open_cover") {
    updated.attributes.current_position = 100;
    updated.state = "open";
  } else if (message.domain === "cover" && message.service === "close_cover") {
    updated.attributes.current_position = 0;
    updated.state = "closed";
  } else if (message.domain === "cover" && message.service === "stop_cover") {
    updated.state = updated.attributes.current_position > 0 ? "open" : "closed";
  } else if (message.service === "toggle") {
    updated.state = current.state === "on" ? "off" : "on";
  } else if (message.service === "turn_on") {
    updated.state = "on";
  } else if (message.service === "turn_off") {
    updated.state = "off";
  }
  states.set(entityId, updated);
  broadcastState(updated);
  addLog(`Service ${message.domain}.${message.service} → ${entityId}`);
}

function sendJson(socket, value) {
  sendFrame(socket, 0x1, Buffer.from(JSON.stringify(value)));
}

function sendFrame(socket, opcode, payload) {
  if (socket.destroyed) return;
  let header;
  if (payload.length < 126) {
    header = Buffer.from([0x80 | opcode, payload.length]);
  } else if (payload.length <= 0xffff) {
    header = Buffer.alloc(4);
    header[0] = 0x80 | opcode;
    header[1] = 126;
    header.writeUInt16BE(payload.length, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x80 | opcode;
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(payload.length), 2);
  }
  socket.write(Buffer.concat([header, payload]));
}

server.listen(port, host, () => {
  addLog(`HA test harness listening on http://127.0.0.1:${port}`);
  addLog(`Emulator HA URL: http://10.0.2.2:${port} · token: ${expectedToken}`);
  if (process.env.NO_MEDIA !== "1") startMedia();
});

function findGo2rtc() {
  const candidates = [
    process.env.GO2RTC_BIN,
    "/tmp/go2rtc-nspanel/go2rtc",
    "/private/tmp/go2rtc-nspanel/go2rtc",
  ].filter(Boolean);
  return candidates.find(candidate => fs.existsSync(candidate)) || null;
}

function startMedia() {
  if (mediaProcess) return { ok: true, alreadyRunning: true, pid: mediaProcess.pid };
  const binary = findGo2rtc();
  if (!binary) {
    addLog("Synthetic media unavailable: set GO2RTC_BIN to a go2rtc executable");
    return { ok: false, error: "go2rtc binary not found; set GO2RTC_BIN" };
  }
  const configPath = path.join(os.tmpdir(), `ha-companion-go2rtc-${process.pid}.yaml`);
  const config = [
    "api:",
    `  listen: \":${mediaApiPort}\"`,
    "rtsp:",
    "  listen: \"127.0.0.1:8555\"",
    "webrtc:",
    `  listen: \":${mediaWebRtcPort}\"`,
    "  candidates:",
    `    - \"10.0.2.2:${mediaWebRtcPort}\"`,
    "streams:",
    `  ${mediaStreamName}:`,
    "    - \"ffmpeg:virtual?video=testsrc&audio=sine#video=h264#audio=opus\"",
    "",
  ].join("\n");
  fs.writeFileSync(configPath, config, { mode: 0o600 });
  const child = childProcess.spawn(binary, ["-config", configPath], {
    stdio: ["ignore", "pipe", "pipe"],
  });
  mediaProcess = child;
  mediaStartedAt = new Date().toISOString();
  addLog(`Starting synthetic media ${mediaStreamName} with PID ${child.pid}`);
  for (const output of [child.stdout, child.stderr]) {
    output.setEncoding("utf8");
    output.on("data", data => {
      for (const line of data.trim().split(/\r?\n/).filter(Boolean)) addLog(`go2rtc: ${line}`);
    });
  }
  child.on("error", error => addLog(`go2rtc failed: ${error.message}`));
  child.on("exit", (code, signal) => {
    if (mediaProcess === child) {
      mediaProcess = null;
      mediaStartedAt = null;
    }
    fs.rmSync(configPath, { force: true });
    addLog(`Synthetic media stopped (${signal || code})`);
  });
  return { ok: true, pid: child.pid, streamName: mediaStreamName };
}

function stopMedia() {
  if (!mediaProcess) return;
  addLog("Stopping synthetic media");
  mediaProcess.kill("SIGTERM");
}

function shutdown() {
  for (const client of clients) client.socket.destroy();
  stopMedia();
  server.close(() => process.exit(0));
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
