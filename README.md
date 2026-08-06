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
See `docs/LOCAL_TEST_HARNESS.md`.

## Related repositories

| Repository | Purpose |
| --- | --- |
| [nspanel-companion-app](https://github.com/hestiaworks/nspanel-companion-app) | Android panel application |
| [addons](https://github.com/hestiaworks/addons) | Home Assistant add-on that updates panels over ADB |
| [nspanel-companion-scrypted](https://github.com/hestiaworks/nspanel-companion-scrypted) | Scrypted plugin for doorbell talkback |

## Status

Beta. The layout schema is versioned and migrated, but interfaces may still
change between releases.
