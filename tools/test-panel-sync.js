#!/usr/bin/env node

const base = process.env.HA_TEST_URL || "http://127.0.0.1:8124";
const panelId = "panel-11111111111111111111111111111111";

async function post(path, body, token) {
  const response = await fetch(`${base}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  });
  return { status: response.status, body: await response.json() };
}

const started = await post("/api/nspanel_companion/pair/start", { device_id: panelId, name: "Isolation test" });
const claim = { request_id: started.body.request_id, claim: started.body.claim };
await post("/api/nspanel_companion/pair/status", claim);
const approved = await post("/api/nspanel_companion/pair/status", claim);
const own = await post("/api/nspanel_companion/panel/sync", { panel_id: panelId, app_version: "test", layout_revision: "" }, approved.body.token);
const foreign = await post("/api/nspanel_companion/panel/sync", { panel_id: "panel-22222222222222222222222222222222", app_version: "test", layout_revision: "" }, approved.body.token);

if (own.status !== 200 || own.body.panel_id !== panelId || !own.body.layout) throw new Error("Own layout sync failed");
if (foreign.status !== 401) throw new Error("Foreign panel accepted another panel's token");
process.stdout.write(`own=${own.status} revision=${own.body.layout_revision} foreign=${foreign.status}\n`);
