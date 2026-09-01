// A Home Assistant stand-in, so the admin panel can be rendered and looked at
// without one. The shapes here mirror what the websocket commands in
// websocket.py actually return; when one of those changes, change it here too.
export const PANELS = [
  {
    panel_id: "8f2a-c401-19bd", device_id: "8f2a-c401-19bd", name: "Living room",
    revoked: false, layout_revision: "ui-1788259412773", page_count: 4, connected: true,
    app_version: "1.1.0 (1010099)", reported_layout_revision: "ui-1788259412773",
    events: [
      { at: new Date(Date.now() - 60_000).toISOString(), message: "Layout revision 42 acknowledged", level: "info" },
      { at: new Date(Date.now() - 120_000).toISOString(), message: "Layout revision 42 published", level: "info" },
      { at: new Date(Date.now() - 3_600_000).toISOString(), message: "Websocket connected", level: "info" },
      { at: new Date(Date.now() - 3_660_000).toISOString(), message: "Websocket dropped", level: "warn" },
    ],
    layout: { revision: "ui-1788259412773", pages: [
      { id: "climate", title: "Thermostat", widgets: [{ type: "thermostat", entity_id: "climate.living_room" }] },
      { id: "weather", title: "Weather", widgets: [{ type: "weather", entity_id: "weather.home" }] },
      { id: "controls", title: "Controls", widgets: [
        { type: "entity_button", entity_id: "light.kitchen_ceiling", label: "Kitchen ceiling", icon: "ceiling-light", show_timer: true, show_schedule: true },
        { type: "entity_button", entity_id: "light.desk_lamp", label: "Desk lamp", icon: "floor-lamp", show_timer: true },
        { type: "entity_button", entity_id: "cover.living_blinds", label: "Living room blinds", icon: "cover" },
        { type: "entity_button", entity_id: "switch.desk_monitor", label: "Desk monitor", icon: "plug" },
      ] },
      { id: "door", title: "Front door", widgets: [{ type: "camera", stream_name: "doorbell", scrypted_bridge_id: "front-door", scrypted_camera_id: "front-door-cam" }] },
    ],
      doorbell: { enabled: true, trigger_entity_id: "binary_sensor.front_door_visitor",
        scrypted_bridge_id: "front-door", scrypted_doorbell_id: "front-door-cam",
        auto_close_ms: 60000, chime: "chime_1", chime_volume: 70 } },
    last_seen: new Date(Date.now() - 12_000).toISOString(),
  },
  {
    panel_id: "e274-afd5-af63", device_id: "e274-afd5-af63", name: "NSPanel 79F2",
    revoked: false, layout_revision: "ui-1788282949347", page_count: 2, connected: true,
    app_version: "1.1.0 (1010099)", reported_layout_revision: "ui-1788282949347", events: [],
    layout: { revision: "ui-1788282949347", pages: [{ id: "a", title: "A", widgets: [] }] },
    last_seen: new Date(Date.now() - 11_000).toISOString(),
  },
  {
    panel_id: "31c7-08ae-4f52", device_id: "31c7-08ae-4f52", name: "Hallway",
    revoked: false, layout: null, layout_revision: null, page_count: 1, connected: true,
    last_seen: new Date(Date.now() - 15_000).toISOString(),
  },
];

export const STATES = {
  "climate.living_room": { entity_id: "climate.living_room", state: "heat",
    attributes: { friendly_name: "Living room", fan_modes: ["auto", "low", "high"],
      swing_modes: ["off", "full", "fixed_upper", "fixed_middle", "fixed_lower",
                    "swing_upper", "swing_middle", "swing_lower", "fixed_upper_middle", "swing_upper_middle"] } },
  "weather.home": { entity_id: "weather.home", state: "cloudy", attributes: { friendly_name: "Home" } },
  "light.kitchen_ceiling": { entity_id: "light.kitchen_ceiling", state: "on", attributes: { friendly_name: "Kitchen ceiling" } },
  "light.desk_lamp": { entity_id: "light.desk_lamp", state: "off", attributes: { friendly_name: "Desk lamp" } },
  "cover.living_blinds": { entity_id: "cover.living_blinds", state: "open", attributes: { friendly_name: "Living room blinds" } },
  "switch.desk_monitor": { entity_id: "switch.desk_monitor", state: "off", attributes: { friendly_name: "Desk monitor" } },
  "sensor.bedroom_temp": { entity_id: "sensor.bedroom_temp", state: "21.0", attributes: { friendly_name: "Bedroom temp", unit_of_measurement: "°C", device_class: "temperature" } },
  "fan.desk": { entity_id: "fan.desk", state: "off", attributes: { friendly_name: "Desk fan" } },
};

const RESPONSES = {
  "nspanel_companion/panels/list": PANELS,
  "nspanel_companion/scrypted/list": {
    paired: [
      { id: "front-door", name: "Front door bridge", base_url: "http://192.0.2.24:11080", version: "0.9.4" },
    ],
    discovered: [
      { id: "garage", name: "Garage bridge", base_url: "http://192.0.2.31:11080", version: "0.9.4" },
    ],
  },
  "nspanel_companion/updater/status": { paired: { base_url: "http://192.0.2.10:8098" } },
  "nspanel_companion/panels/discovery/scan": { panels: [
    { id: "31c7-08ae-4f52", name: "NSPanel Pro (hallway)", request_id: "req-1" },
    { id: "a4d0-77b2-0e13", name: "NSPanel Pro (kitchen)", request_id: "req-2" },
  ] },
  "nspanel_companion/panels/discovery/settings": { passive: false },
  "nspanel_companion/scrypted/doorbells": [
    { id: "front-door-cam", name: "Front door", bridge_id: "front-door" },
  ],
};

/** Install the stand-in on window, the way Home Assistant hands it to a panel. */
export function fakeHass() {
  return {
    states: STATES,
    themes: {},
    connection: {
      sendMessagePromise: async (message) => {
        if (message.type === "nspanel_companion/layout/set") {
          window.__published = message;
          return { ok: true };
        }
        if (message.type === "nspanel_companion/panels/rename") return { panel: {} };
        if (message.type === "nspanel_companion/layout/get") {
          const panel = PANELS.find((item) => item.panel_id === message.panel_id);
          return panel?.layout ?? { schema_version: 1, revision: 0, pages: [] };
        }
        if (message.type in RESPONSES) return RESPONSES[message.type];
        return {};
      },
      subscribeEvents: async () => () => {},
    },
  };
}
