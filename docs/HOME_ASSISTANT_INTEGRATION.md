# Home Assistant integration

The first integration foundation lives in
`custom_components/nspanel_companion`. It currently provides:

- a single-instance UI Config Flow;
- persistent panel records in Home Assistant storage;
- one-time panel token generation with only a SHA-256 hash retained;
- sanitized config-entry diagnostics;
- administrator-only WebSocket commands for panel registration and layout
  retrieval/assignment;
- schema validation matching Android layout version 1;
- a panel-authenticated WebSocket for scoped entity state, service calls, and
  doorbell events;
- targeted layout synchronization and heartbeats;
- an administrator-only **NSPanel Companion** sidebar manager.
- mDNS discovery and six-digit pairing with the NSPanel Talkback Scrypted
  plugin, without copying endpoints or credentials.

## Manual development installation

Copy `custom_components/nspanel_companion` into the Home Assistant
configuration directory, restart Home Assistant, then add **NSPanel
Companion** from **Settings → Devices & services → Add integration**.

The sidebar manager uses the API directly. Authenticated administrator
WebSocket clients can also use:

- `nspanel_companion/panels/list`
- `nspanel_companion/panels/register` with `name` and `device_id`
- `nspanel_companion/layout/get` with `panel_id`
- `nspanel_companion/layout/set` with `panel_id` and a version 1 `layout`

The register response includes a token exactly once. Home Assistant never
returns its stored hash; an administrator can rotate or revoke it.

## Panel identity

On first launch, Android generates an installation UUID in the canonical form
`panel-<32 lowercase hex characters>` and persists it separately from HA
connection settings. Home Assistant uses `(nspanel_companion, device_id)` as
the Device Registry identifier. Panel names, areas, IP addresses, and pairing
codes are deliberately not identities and may change safely.

Clearing only the HA connection does not change the panel identity. Clearing
all application data or reinstalling the app creates a new identity and
requires pairing again.

## Local pairing flow

1. An unpaired panel advertises `_nspanel-companion._tcp.local.` and waits; it
   does not browse for HA or create a request in the background.
2. The administrator presses **Find panels** in HA. HA browses only for the
   duration of that explicit scan and lists available panel names and IDs.
3. Selecting a panel sends HA's local URL to that panel. Manual URL entry on
   the panel remains available when mDNS cannot cross network boundaries.
4. The selected panel starts a five-minute request through
   `/api/nspanel_companion/pair/start` and displays the returned six-digit code.
5. The HA sidebar does not show requests passively. An administrator selects
   **Find panels**, chooses the panel by its stable friendly name and ID, then
   enters the six-digit code shown on that panel. HA approves the request only
   when it matches.
6. Android polls `/api/nspanel_companion/pair/status` using a separate random
   claim secret. The permanent token is returned once and the request is
   removed immediately.
7. Android stores the token with AES-GCM using a non-exportable Android
   Keystore key.

An optional **Keep panel discovery running in the background** setting enables
continuous HA browsing. It is disabled by default and does not change the
six-digit confirmation requirement.

Pending requests exist only in memory, are capped, and expire after five
minutes. Local HTTPS is preferred where available; plain HTTP pairing assumes
a trusted home LAN. QR-assisted launch remains a fallback enhancement.

## Authenticated panel synchronization

Paired clients call `/api/nspanel_companion/panel/sync` with their stable
`panel_id` and Bearer panel token. Home Assistant compares the stored token
hash in constant time, updates `last_seen`, app version, and reported layout
revision, then returns only that panel's assigned layout when needed.

Android synchronizes every 15 seconds, retries transient network failures,
validates the normal layout schema, and activates updates through its atomic
layout store. A revoked or rotated token receives HTTP 401 and stops syncing.
The sidebar treats heartbeats newer than 45 seconds as online and refreshes
automatically. Administrators can revoke or rotate tokens; replacement tokens
are displayed once.

## Panel runtime connection

After pairing, Android connects to
`/api/nspanel_companion/panel/ws?panel_id=<panel_id>` using the same Bearer
panel credential. The integration sends an initial state snapshot followed by
live state and doorbell messages. Android sends service calls through this
socket, so it does not need a Home Assistant user token.

Entity access is limited to entities referenced by the assigned layout (with
a small bounded fallback while the layout is still generic). Service calls
must target an allowed entity and match a domain-specific whitelist. Arbitrary
Home Assistant services are rejected. Pairing clears any development
long-lived token previously stored by the app.

## Sidebar manager

The integration automatically serves and registers its dependency-free
JavaScript module. The first manager screen supports:

- viewing registered panels and layout revisions;
- discovering unpaired panels in an on-demand **Find panels** dialog;
- copying or downloading the one-time token;
- publishing the built-in thermostat/weather/controls layout;
- inspecting sanitized panel details and assigned layout JSON.

The **Configure** action provides the first graphical editor. It can select a
climate entity, weather entity, up to 12 light/switch/fan/cover/input-boolean
controls, default-page return time, and per-panel doorbell settings. Publishing
creates a validated revision and the online panel activates it through its
normal synchronization channel.

Doorbell configuration includes an enabled flag, visitor binary sensor,
Scrypted doorbell selector, quiet mode, and 10–300 second timeout. Selecting a
Scrypted doorbell securely materializes its video and talkback configuration
server-side. Advanced manual URL/key fields remain available as a fallback. A
transition of the selected sensor to `on` sends the event only to that panel.
Manually fired `nspanel_doorbell` events may target one panel with `panel_id`
or several with `panel_ids`; events without a target retain broadcast behavior.

Paired Scrypted bridges provide two coordinated removal actions. **Unpair**
invalidates the bridge credential in Scrypted and deletes HA's stored copy while
preserving layouts already published to panels. **Unpair + clear doorbells**
also disables and removes Scrypted-derived video/talkback fields from every
affected panel layout. Both actions rotate Scrypted's six-digit pairing code.

For frontend-only development, run `node tools/ha-test-server.js` and open
`http://127.0.0.1:8124/ha-panel-preview`. The preview supplies a fake Home
Assistant WebSocket connection and does not modify a real installation.

## Current boundary

Manual URL/token configuration remains available only as a pre-pairing debug
fallback. The production runtime uses the panel credential for synchronization,
entity state, service calls, and doorbell events. QR-assisted onboarding is
deferred to a later app version.
