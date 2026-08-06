# Dashboard layout schema

Schema version 1 is the contract between the Android panel and the future Home
Assistant integration. A layout is validated completely before it replaces the
active cached revision.

```json
{
  "schema_version": 1,
  "revision": "living-room-12",
  "default_page_id": "room",
  "default_page_return_seconds": 60,
  "weather_cache_max_age_minutes": 360,
  "pages": [
    {
      "id": "room",
      "title": "Living room",
      "widgets": [
        { "type": "entity_button", "entity_id": "light.ceiling", "label": "Ceiling" },
        { "type": "sensor", "entity_id": "sensor.room_temperature", "label": "Temperature" }
      ]
    },
    {
      "id": "climate",
      "title": "Climate",
      "widgets": [
        { "type": "thermostat", "entity_id": "climate.living_room" }
      ]
    }
  ]
}
```

Supported version 1 widget types are `thermostat`, `weather`, `controls`,
`entity_button`, and `sensor`. An omitted thermostat or weather entity selects
the first matching HA entity for backward compatibility. An entity-free
`controls` widget selects up to four supported entities and chooses a native
card from each entity's domain and attributes: binary toggle, dimmable light,
percentage fan, or position cover.

Limits:

- 1–8 pages.
- Unique page IDs containing letters, numbers, `_`, or `-`.
- Up to 12 widgets per page.
- Entity IDs must use the normal `domain.object_id` form.
- `default_page_return_seconds` accepts 0–3600; `0` disables automatic return.
- `weather_cache_max_age_minutes` accepts 0–10080 and defaults to 360 (six
  hours); `0` disables cached weather restore.
- Unknown schema versions and widget types are rejected.

The active revision is stored as `dashboard-layout.json` in Android internal
storage. Updates are written to a temporary file and atomically renamed. A
missing or invalid cache falls back to the built-in thermostat, weather, and
controls layout.

Only `weather.*` entities are stored in `weather-cache.json`. Expired entries
are ignored, and cached values are marked with their age while Home Assistant
is offline.

During local development, `POST /api/layout` on the test harness publishes an
`nspanel_layout` event. The Android client validates, stores, and activates it.
The future custom integration will replace this temporary event publisher.
