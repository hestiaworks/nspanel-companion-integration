#!/usr/bin/env node

const baseUrl = process.env.HA_TEST_URL || "http://127.0.0.1:8124";
const deviceId = `protocol-test-${Date.now()}`;
const crypto = require("node:crypto");
const http = require("node:http");

async function post(path, body) {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function connectWebSocket(path, token) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, baseUrl);
    const request = http.request({
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      headers: {
        Authorization: `Bearer ${token}`,
        Connection: "Upgrade",
        Upgrade: "websocket",
        "Sec-WebSocket-Key": crypto.randomBytes(16).toString("base64"),
        "Sec-WebSocket-Version": "13",
      },
    });
    request.once("upgrade", (_response, socket, head) => {
      const client = { socket, buffer: Buffer.alloc(0), listeners: new Set() };
      socket.on("data", chunk => parseFrames(client, chunk));
      client.send = value => socket.write(maskedTextFrame(JSON.stringify(value)));
      client.close = () => socket.end();
      resolve(client);
      if (head.length) setImmediate(() => parseFrames(client, head));
    });
    request.once("response", response => reject(new Error(`WebSocket HTTP ${response.statusCode}`)));
    request.once("error", reject);
    request.end();
  });
}

function maskedTextFrame(text) {
  const payload = Buffer.from(text);
  const mask = crypto.randomBytes(4);
  const extendedLength = payload.length >= 126 ? 2 : 0;
  if (payload.length > 0xffff) throw new Error("Test message is unexpectedly large");
  const frame = Buffer.alloc(6 + extendedLength + payload.length);
  frame[0] = 0x81;
  frame[1] = 0x80 | (extendedLength ? 126 : payload.length);
  if (extendedLength) frame.writeUInt16BE(payload.length, 2);
  const maskOffset = 2 + extendedLength;
  mask.copy(frame, maskOffset);
  const payloadOffset = maskOffset + 4;
  for (let index = 0; index < payload.length; index++) {
    frame[payloadOffset + index] = payload[index] ^ mask[index % 4];
  }
  return frame;
}

function parseFrames(client, chunk) {
  client.buffer = Buffer.concat([client.buffer, chunk]);
  while (client.buffer.length >= 2) {
    let length = client.buffer[1] & 0x7f;
    let offset = 2;
    if (length === 126) {
      if (client.buffer.length < 4) return;
      length = client.buffer.readUInt16BE(2);
      offset = 4;
    }
    if (client.buffer.length < offset + length) return;
    const message = JSON.parse(client.buffer.subarray(offset, offset + length).toString("utf8"));
    client.buffer = client.buffer.subarray(offset + length);
    for (const listener of client.listeners) listener(message);
  }
}

function nextMessage(socket, predicate, timeoutMs = 3000) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("Timed out waiting for WebSocket message")), timeoutMs);
    const listener = message => {
      if (!predicate(message)) return;
      clearTimeout(timeout);
      socket.listeners.delete(listener);
      resolve(message);
    };
    socket.listeners.add(listener);
  });
}

async function main() {
  const start = await post("/api/nspanel_companion/pair/start", { device_id: deviceId });
  await post("/api/nspanel_companion/pair/status", { request_id: start.request_id, claim: start.claim });
  const approved = await post("/api/nspanel_companion/pair/status", {
    request_id: start.request_id,
    claim: start.claim,
  });

  const socket = await connectWebSocket(
    `/api/nspanel_companion/panel/ws?panel_id=${encodeURIComponent(deviceId)}`,
    approved.token,
  );
  const initial = await nextMessage(socket, message => message.type === "initial_states");
  if (!initial.states.some(state => state.entity_id === "light.test_ceiling")) {
    throw new Error("Initial states did not contain the test light");
  }

  const changedPromise = nextMessage(
    socket,
    message => message.type === "state_changed" && message.state?.entity_id === "light.test_ceiling",
  );
  const resultPromise = nextMessage(socket, message => message.type === "call_result" && message.id === 1);
  socket.send({
    type: "call_service",
    id: 1,
    domain: "light",
    service: "toggle",
    entity_id: "light.test_ceiling",
    service_data: {},
  });
  const [changed, result] = await Promise.all([changedPromise, resultPromise]);
  if (!result.success || !["on", "off"].includes(changed.state.state)) {
    throw new Error("Scoped service call did not complete");
  }

  const deniedPromise = nextMessage(socket, message => message.type === "call_result" && message.id === 2);
  socket.send({
    type: "call_service",
    id: 2,
    domain: "light",
    service: "delete_everything",
    entity_id: "light.test_ceiling",
    service_data: {},
  });
  const denied = await deniedPromise;
  if (denied.success) throw new Error("Disallowed service call was accepted");

  socket.close();
  console.log("Panel WebSocket test passed: pairing, initial states, live update, allowed and denied services");
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
