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
import { execFileSync, spawn } from "node:child_process";

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
/** Phone emulation: a real viewport width plus touch, not just a narrow window. */
const mobile = args.includes("--mobile");
const settle = Number(opt("settle", 900));
// Some states are reached by clicking, not by a URL — a selected slot most
// of all. This drives the element the way a person would.
const select = opt("select", null);
/**
 * Click something after mount, for states that are behind a button.
 *
 * Repeatable, and clicked in order: reaching a state often takes two — open
 * the picker, then choose from it. A single --click silently ignoring the
 * second one made a broken flow look like a working one.
 */
const clicks = args.flatMap((arg, i) => (arg === "--click" ? [args[i + 1]] : []));

const work = mkdtempSync(join(tmpdir(), "nspanel-preview-"));
writeFileSync(join(work, "panel.js"), `${execFileSync("cat", [PANEL])}`);
writeFileSync(join(work, "fixture.js"), `${execFileSync("cat", [join(HERE, "fixture.js")])}`);
writeFileSync(join(work, "harness.html"), `<!doctype html>
<meta charset="utf-8">
<!-- Home Assistant's own document carries this; without it phone emulation
     lays the page out at 980px and scales it down, which looks like a design
     that ignores the breakpoints rather than a harness that never hit them. -->
<meta name="viewport" content="width=device-width, initial-scale=1">
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
  ${clicks.map((selector) => `
  await new Promise((done) => setTimeout(done, 400));
  {
    const target = el.shadowRoot.querySelector(${JSON.stringify(selector)});
    if (!target) failures.push("no element matches " + ${JSON.stringify(selector)});
    target?.click();
  }`).join("")}
  ${select === null ? "" : `
  await new Promise((done) => setTimeout(done, 400));
  const slot = el.shadowRoot.querySelector('[data-select-widget="${select}"]');
  if (slot) slot.click();
  await new Promise((done) => setTimeout(done, 300));`}
  ${opt("open", null) === null ? "" : `
  el.shadowRoot.querySelector(${JSON.stringify(opt("open", ""))})?.setAttribute("open", "");
  await new Promise((done) => setTimeout(done, 300));`}
  await new Promise((done) => setTimeout(done, 250));
  ${!args.includes("--audit") ? "" : `
  // Which elements stick out of the viewport, innermost blamed on their
  // nearest named ancestor. Reading a layout bug off a screenshot guesses;
  // this measures.
  {
    const edge = document.documentElement.clientWidth;
    const seen = new Map();
    el.shadowRoot.querySelectorAll("*").forEach((node) => {
      const box = node.getBoundingClientRect();
      if (!box.width || (box.right <= edge + 1 && box.left >= -1)) return;
      // Something inside a deliberate horizontal scroller (the tab bar) is
      // not a page that overflows; it is a scroller doing its job.
      for (let parent = node.parentElement; parent; parent = parent.parentElement) {
        const overflow = getComputedStyle(parent).overflowX;
        if (overflow === "auto" || overflow === "scroll") return;
      }
      const name = node.tagName.toLowerCase()
        + (node.className ? "." + String(node.className).split(" ").slice(0, 2).join(".") : "");
      if (!seen.has(name)) seen.set(name, Math.round(box.left) + "→" + Math.round(box.right));
    });
    const style = getComputedStyle(el);
    const context = ["--page-inset", "--inspector", "--rail", "--content-max"]
      .map((token) => token + "=" + style.getPropertyValue(token).trim());
    [":host", "main", ".workspace-grid", ".editor", ".stage", ".app-bar", "nav.tabs"].forEach((selector) => {
      const node = selector === ":host" ? el : el.shadowRoot.querySelector(selector);
      if (node) context.push(selector + "=" + Math.round(node.getBoundingClientRect().width));
    });
    const lines = context.concat("", ...[...seen].slice(0, 14).map(([name, span]) => name + "  " + span));
    document.body.innerHTML = '<pre style="color:#F2F5F7;font:12px/1.6 monospace;padding:10px;white-space:pre-wrap">'
      + \`viewport \${edge}px · \${seen.size ? seen.size + " overflowing" : "nothing overflows"}\n\n\`
      + lines.join(String.fromCharCode(10)) + '</pre>';
    document.title = "AUDIT";
  }`}
  // The page is drawn in Barlow or it is not the page. A fallback face
  // changes every measurement on it, so say so rather than photograph it.
  // A face is only fetched when something on the page uses it, so ask for it
  // rather than checking: a tab with no monospace text on it is not a
  // missing font.
  for (const face of ["600 14px Barlow", "500 12px 'Roboto Mono'"]) {
    await document.fonts.load(face, "Aa1");
    if (!document.fonts.check(face)) failures.push(face + " did not load");
  }
  await document.fonts.ready;
  if (window.__published) {
    const layout = window.__published.layout || {};
    document.title = "PUBLISHED " + (layout.pages || []).length + " pages, doorbell trigger="
      + JSON.stringify(layout.doorbell?.trigger_entity_id ?? null);
  }
  if (failures.length || (document.title !== "AUDIT" && !el.shadowRoot?.querySelector("main, .editor"))) {
    document.body.innerHTML =
      '<pre style="color:#D24A3F;font:14px monospace;padding:24px;white-space:pre-wrap">'
      + (failures.join("\\n") || "nothing rendered") + '</pre>';
    document.title = "RENDER FAILED";
  }
</script>`);

// Served over http rather than opened as a file: Chrome refuses ES module
// scripts from file:// on CORS grounds, and the panel is loaded as a module.
const TYPES = { js: "text/javascript", woff2: "font/woff2", html: "text/html" };
const server = createServer((request, response) => {
  const path = (request.url || "/").split("?")[0];
  const name = path.replace(/^\//, "") || "harness.html";
  try {
    // The panel asks for its fonts at the path Home Assistant serves them
    // from. Without them the preview renders in a fallback face and every
    // screenshot lies about the typography.
    const body = path.startsWith("/nspanel_companion/frontend/")
      ? readFileSync(resolve(HERE, "../../custom_components/nspanel_companion", path.replace("/nspanel_companion/", "")))
      : readFileSync(join(work, name));
    response.writeHead(200, {
      "content-type": TYPES[name.split(".").pop()] || "application/octet-stream",
    });
    response.end(body);
  } catch {
    response.writeHead(404).end("not found");
  }
});
// The harness is generated code, and a stray escape in the generator has
// twice produced a page that failed to parse and photographed as a blank
// rectangle. Parse it here, where the error has a line number.
{
  const script = readFileSync(join(work, "harness.html"), "utf8")
    .split('<script type="module">')[1].split("</scr" + "ipt>")[0];
  const probe = join(work, "harness-check.mjs");
  writeFileSync(probe, script);
  try {
    execFileSync(process.execPath, ["--check", probe], { stdio: "pipe" });
  } catch (error) {
    console.error(`${error.stderr || error}`);
    throw new Error("the generated harness does not parse — fix preview.mjs, not the panel");
  }
}

// The generated harness, for when the harness itself is what is broken.
if (opt("keep", null)) writeFileSync(resolve(opt("keep", "")), readFileSync(join(work, "harness.html")));
await new Promise((ready) => server.listen(0, "127.0.0.1", ready));
const { port } = server.address();

/**
 * Drive Chrome over the DevTools protocol rather than with --screenshot.
 *
 * --window-size will not go below roughly 500px on macOS: asking for a 390px
 * phone gave a 500px page cropped to 390, so the media queries under test
 * never fired and the picture looked like a bug in the CSS. Overriding the
 * device metrics sets the viewport the page actually sees.
 */
const cdp = async (chromePort, run) => {
  const target = await (await fetch(`http://127.0.0.1:${chromePort}/json/new?about:blank`, { method: "PUT" })).json();
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  const pending = new Map();
  let nextId = 0;
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      message.error ? reject(new Error(message.error.message)) : resolve(message.result);
    }
  });
  await new Promise((open, fail) => {
    socket.addEventListener("open", open, { once: true });
    socket.addEventListener("error", () => fail(new Error("cannot reach Chrome")), { once: true });
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = (nextId += 1);
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
  try {
    return await run(send);
  } finally {
    socket.close();
    await fetch(`http://127.0.0.1:${chromePort}/json/close/${target.id}`).catch(() => {});
  }
};

const profile = mkdtempSync(join(tmpdir(), "nspanel-preview-profile-"));
const chrome = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
  "--force-device-scale-factor=1", "--remote-debugging-port=0",
  `--user-data-dir=${profile}`, "about:blank",
], { stdio: ["ignore", "ignore", "pipe"] });

// Chrome writes the port it chose into the profile once it is listening.
const chromePort = await (async () => {
  const file = join(profile, "DevToolsActivePort");
  for (let attempt = 0; attempt < 200; attempt += 1) {
    try {
      const [line] = readFileSync(file, "utf8").split("\n");
      if (line) return Number(line);
    } catch { /* not written yet */ }
    await new Promise((wait) => setTimeout(wait, 50));
  }
  throw new Error("Chrome never reported a debugging port");
})();

try {
  await cdp(chromePort, async (send) => {
    await send("Emulation.setDeviceMetricsOverride", {
      width, height, deviceScaleFactor: 1, mobile,
      screenWidth: width, screenHeight: height,
    });
    if (mobile) await send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 });
    await send("Page.enable");
    await send("Page.navigate", { url: `http://127.0.0.1:${port}/harness.html` });
    // The harness drives itself with real timers, so this is wall-clock.
    await new Promise((wait) => setTimeout(wait, settle + clicks.length * 450 + (select === null ? 0 : 700) + 600));
    const shot = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(out, Buffer.from(shot.data, "base64"));
    // An audit is a list of names and numbers: worth having in the terminal,
    // where it can be diffed and looped over, not only in a picture.
    if (args.includes("--audit")) {
      const report = await send("Runtime.evaluate", {
        expression: "document.querySelector('pre')?.textContent || 'no report'",
        returnByValue: true,
      });
      console.log(`--- ${route || "#home"} @ ${width}px\n${report.result.value}`);
    }
  });
} finally {
  chrome.kill();
  server.close();
  rmSync(work, { recursive: true, force: true });
  // Chrome is still flushing its profile as we kill it; retry rather than
  // fail a run whose picture is already on disk.
  rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
console.log(`${out} (${width}×${height}${light ? ", light" : ""}${route ? `, ${route}` : ""})`);
