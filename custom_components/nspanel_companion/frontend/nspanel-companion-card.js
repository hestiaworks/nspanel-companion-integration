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
