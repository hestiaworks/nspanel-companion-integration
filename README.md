# NSPanel Companion — Home Assistant integration

Home Assistant integration for [NSPanel Companion](https://github.com/hestiaworks/nspanel-companion-app),
a native Android dashboard for the Sonoff NSPanel Pro.

It registers paired panels, publishes their layouts, serves a sidebar panel for
managing them, and exposes the WebSocket API the panels talk to.

## What it provides

- UI config flow and a **NSPanel Companion** sidebar panel
- Panel pairing with expiring approval codes and hashed panel tokens
- Versioned layout schema with validation and per-panel revisions
- Live entity snapshots, doorbell events, and layout-scoped service calls
- Diagnostics and administrator commands (token rotation, revoke, remove)

## Requirements

- Home Assistant 2025.6.0 or newer
- One or more NSPanel Pro devices running the companion app

## Installation

Add this repository to HACS as a custom repository of type **Integration**,
install it, restart Home Assistant, then add **NSPanel Companion** from
*Settings → Devices & services*.

## Local test harness

`tools/ha-test-server.js` is a dependency-free stand-in for Home Assistant used to
develop and test panels without a live instance. `tools/test-panel-sync.js` and
`tools/test-panel-websocket.js` exercise this integration's HTTP and WebSocket APIs.

```bash
node tools/ha-test-server.js
```

It listens on port 8124. From an Android emulator the host is reachable at
`10.0.2.2`, so pair the panel against `http://10.0.2.2:8124`.

## Related repositories

| Repository | Purpose |
| --- | --- |
| [nspanel-companion-app](https://github.com/hestiaworks/nspanel-companion-app) | Android panel application |
| [addons](https://github.com/hestiaworks/addons) | Home Assistant add-ons: panel updates over ADB, and low-latency doorbell talkback |
| [nspanel-companion-scrypted](https://github.com/hestiaworks/nspanel-companion-scrypted) | Scrypted plugin: doorbell video for panels, and talkback as a fallback |

## Doorbell talkback

A panel speaks to a Reolink doorbell over the camera's own protocol, which is
seconds faster than the ONVIF path a bridge would use. Install the **NSPanel
Companion Talkback** add-on and the integration pairs with it by itself, then
writes its address into every panel layout as it is published.

Two fields carry it, `talk_url` and `talk_key`, separate from `talkback_url`
on purpose: the talkback endpoint is also where a panel fetches a current
video URL, so pointing it elsewhere would break the picture. The add-on takes
only the audio.

Both are filled in automatically wherever a camera is configured — and left
empty when no add-on is paired, which is what makes a panel keep talking
through the bridge rather than not at all. **Republish a panel's layout** to
move it onto the faster path, and again after re-pairing, since a panel
carries the key it was last given.

A panel whose add-on stops answering falls back on its own.

## Status

Beta. The layout schema is versioned and migrated, but interfaces may still
change between releases.
