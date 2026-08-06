# Local Home Assistant test harness

Run the dependency-free server:

```bash
node tools/ha-test-server.js
```

Open `http://127.0.0.1:8124` in a desktop browser.

Configure the Android emulator with:

```text
URL:   http://10.0.2.2:8124
Token: test-token
```

That manual token is the legacy debug path. To test production onboarding, use
**Pair panel with Home Assistant**, enter `http://10.0.2.2:8124` when discovery
is unavailable, and approve code `482731` (the harness auto-approves on the
second status poll).

Run the scoped runtime protocol check with:

```bash
node tools/test-panel-websocket.js
```

The page can ring the simulated doorbell normally, quietly, or three times;
choose its auto-close timeout; emit state changes for the included
climate/weather/light/switch entities; disconnect panels to exercise HA
reconnect behavior; and show a live protocol log.

When go2rtc is available, the same Node process starts and manages a synthetic
H.264 test stream named `native_test`. The ring event includes its emulator URL
and stream name, so one click exercises the complete path:

```text
web page → fake HA WebSocket → nspanel_doorbell event → native WebRTC → video
```

Use **Stop stream** and **Start / recover stream** while the Android doorbell
view is open to test WebRTC failure and automatic recovery. The harness looks
for go2rtc at `GO2RTC_BIN`, `/tmp/go2rtc-nspanel/go2rtc`, or
`/private/tmp/go2rtc-nspanel/go2rtc`. Set `NO_MEDIA=1` to run only the fake HA
server. Media ports default to API `1985` and WebRTC `8556` and can be changed
with `MEDIA_API_PORT` and `MEDIA_WEBRTC_PORT`.

The server accepts only `test-token` by default. Override the bind address,
port, or token with `HOST`, `PORT`, and `TEST_TOKEN`. It implements only the
Home Assistant WebSocket messages used by this project and is not intended for
production or exposure outside a trusted development machine. The generated
go2rtc configuration is written to the operating system's temporary directory
and removed when its child process exits.

## Testing push-to-talk

The debug harness records the exact PCM samples supplied by Android's native
libwebrtc microphone capture. Trigger a doorbell event, hold **Hold to talk**
on the emulator, speak, and release. The browser page shows a live RMS/peak
meter and enables **Play last recording** after the WAV upload completes.

For real voice input, open the emulator's **Extended controls → Microphone**
and enable **Virtual microphone uses host audio input**. macOS may also request
microphone permission for the emulator. With host input disabled, the pipeline
still produces a valid recording, but it will contain near-silence.

The fake HA event supplies the test-only `talkback_test_url`; production events
should omit it. The recording is kept only in memory and is replaced by the
next push-to-talk session.
