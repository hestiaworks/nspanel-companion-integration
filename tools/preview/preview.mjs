#!/usr/bin/env node
/**
 * Render the admin panel and take its picture.
 *
 * The panel only exists inside Home Assistant, which makes every visual
 * change a matter of publishing and asking someone to look. This mounts the
 * real element against a stand-in Home Assistant (fixture.js) in headless
 * Chrome instead, so a layout can be checked in seconds.
 *
 *   node tools/preview/preview.mjs --out home.png
 *   node tools/preview/preview.mjs --route "#integrations" --light --out int.png
 *
 * It proves the panel renders and how it looks. It cannot prove the websocket
 * calls are right — the stand-in answers them from a fixture, and that
 * fixture is only as true as the last person to update it.
 */
import { mkdtempSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync, execFile } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const PANEL = resolve(HERE, "../../custom_components/nspanel_companion/frontend/nspanel-companion-panel.js");
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i === -1 ? fallback : args[i + 1];
};
const out = resolve(opt("out", "preview.png"));
const route = opt("route", "");
const width = Number(opt("width", 1440));
const height = Number(opt("height", 900));
const light = args.includes("--light");
const settle = Number(opt("settle", 900));
// Some states are reached by clicking, not by a URL — a selected slot most
// of all. This drives the element the way a person would.
const select = opt("select", null);
/** Click something by id after mount, for states that are behind a button. */
const click = opt("click", null);

const work = mkdtempSync(join(tmpdir(), "nspanel-preview-"));
writeFileSync(join(work, "panel.js"), `${execFileSync("cat", [PANEL])}`);
writeFileSync(join(work, "fixture.js"), `${execFileSync("cat", [join(HERE, "fixture.js")])}`);
writeFileSync(join(work, "harness.html"), `<!doctype html>
<meta charset="utf-8">
<title>NSPanel Companion admin</title>
<style>html,body{margin:0;padding:0;background:${light ? "#F4F5F3" : "#0E1012"}}</style>
<div id="host"></div>
<script type="module">
  import { fakeHass } from "./fixture.js";
  await import("./panel.js");
  location.hash = ${JSON.stringify(route)};
  const el = document.createElement("nspanel-companion-panel");
  ${light ? 'el.classList.add("light");' : ""}
  document.getElementById("host").appendChild(el);
  const failures = [];
  window.addEventListener("error", (event) => failures.push(event.message));
  window.addEventListener("unhandledrejection", (event) => failures.push(String(event.reason)));
  el.hass = fakeHass();
  ${click === null ? "" : `
  await new Promise((done) => setTimeout(done, 400));
  el.shadowRoot.querySelector(${JSON.stringify(click)})?.click();`}
  ${select === null ? "" : `
  await new Promise((done) => setTimeout(done, 400));
  const slot = el.shadowRoot.querySelector('[data-select-widget="${select}"]');
  if (slot) slot.click();
  await new Promise((done) => setTimeout(done, 300));`}
  ${opt("open", null) === null ? "" : `
  el.shadowRoot.querySelector(${JSON.stringify(opt("open", ""))})?.setAttribute("open", "");
  await new Promise((done) => setTimeout(done, 300));`}
  await new Promise((done) => setTimeout(done, 250));
  if (window.__published) {
    const layout = window.__published.layout || {};
    document.title = "PUBLISHED " + (layout.pages || []).length + " pages, doorbell trigger="
      + JSON.stringify(layout.doorbell?.trigger_entity_id ?? null);
  }
  if (failures.length || !el.shadowRoot?.querySelector("main, .editor")) {
    document.body.innerHTML =
      '<pre style="color:#D24A3F;font:14px monospace;padding:24px;white-space:pre-wrap">'
      + (failures.join("\\n") || "nothing rendered") + '</pre>';
    document.title = "RENDER FAILED";
  }
</script>`);

// Served over http rather than opened as a file: Chrome refuses ES module
// scripts from file:// on CORS grounds, and the panel is loaded as a module.
const server = createServer((request, response) => {
  const name = (request.url || "/").split("?")[0].replace(/^\//, "") || "harness.html";
  try {
    const body = readFileSync(join(work, name));
    response.writeHead(200, {
      "content-type": name.endsWith(".js") ? "text/javascript" : "text/html",
    });
    response.end(body);
  } catch {
    response.writeHead(404).end("not found");
  }
});
await new Promise((ready) => server.listen(0, "127.0.0.1", ready));
const { port } = server.address();

try {
  await new Promise((done, fail) => {
    execFile(CHROME, [
      "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
      "--force-device-scale-factor=1",
      `--virtual-time-budget=${settle}`,
      `--screenshot=${out}`, `--window-size=${width},${height}`,
      `http://127.0.0.1:${port}/harness.html`,
    ], (error) => (error ? fail(error) : done()));
  });
} finally {
  server.close();
  rmSync(work, { recursive: true, force: true });
}
console.log(`${out} (${width}×${height}${light ? ", light" : ""}${route ? `, ${route}` : ""})`);
