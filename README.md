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
- Notifications on panels, from automations or any blueprint that picks notify targets
- Each panel as a device, with its readings and controls as entities
- A dashboard card for one panel: its wifi and light over the last day, and its controls
- Panel-to-panel intercom, with an option to answer calls automatically: the caller
  is heard like a voice message, and the receiving panel's microphone stays off
  until someone there taps Talk

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

## Notifications

Send to panels with the **NSPanel Companion: Notify panels** action, targeting
panels, their areas or any of their entities:

```yaml
action: nspanel_companion.notify
target:
  area_id: living_room
data:
  title: Washing machine
  message: Cycle finished
  importance: normal        # or: important
```

A **normal** notification is a banner that closes itself; an **important** one
dims the page and waits for GOT IT or LATER. Both land in the panel's list,
opened from the badge in its status strip. Optional fields override the panel's
settings for one notification: `sound`, `duration` (seconds a banner stays) and
`repeat_every` / `repeat_times`.

Each panel also has two notify entities, *Notifications* and *Important
notifications*, so anything that sends with `notify.send_message` — including
blueprints that ask for notify targets — can reach a panel. Choosing the entity
chooses the importance.

A panel that is offline when a notification is sent does not receive it later:
nothing is queued.

The panel editor's **Notifications** tab sets, per panel, each kind's sound and
volume (doorbell, intercom, notification, important notification), how long a
banner stays, whether an unread or unanswered one repeats, and quiet hours —
when doorbell, intercom and normal notifications can be set to ring, show
silently or go straight to the list. Important notifications always ring. Its
**Test on this panel** buttons send each kind to the real panel, and **On panel**
plays a sound on the panel's own speaker.

## The panel as a device

Each paired panel is a device with these entities. The wifi signal and the
ambient light level are on by default; enable the rest on the device page.

| Entity | What it is |
| --- | --- |
| Wifi signal | The panel's signal strength, in dBm |
| Ambient light level | The panel's light sensor, on its own scale (not lux) |
| Approach | Someone at the panel, from its proximity sensor; holds for 30 seconds |
| Connected | Whether the panel is connected to Home Assistant |
| Screen, Brightness | Turn the screen on or off, and set its brightness |
| Page | The page on screen; choosing one switches the panel to it |
| Restart app, Reload layout | Buttons |
| Notifications, Important notifications | Notify targets, see above |

None is categorised, so on Home Assistant's area page everything a panel offers
appears under the panel's own heading. Turning the screen off takes a few
seconds: Android lets an app shorten the display timeout but not switch the
screen off directly.

## Dashboard card

Add **NSPanel Companion** from a dashboard's card picker and choose a panel. The
card shows the panel's wifi signal and light level over the last 24 hours, with
their lows and highs, then its approach state and controls. Only entities that
are enabled appear; a panel that is offline says since when.

```yaml
type: custom:nspanel-companion-card
device_id: <the panel's device id>
```

## Status

Beta. The layout schema is versioned and migrated, but interfaces may still
change between releases.
