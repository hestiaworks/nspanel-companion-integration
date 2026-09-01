"""Unauthenticated local bootstrap endpoints for physical panel pairing."""

from __future__ import annotations

import time

from aiohttp import WSMsgType, web

from homeassistant.components.http import HomeAssistantView
from homeassistant.util import dt as dt_util
from homeassistant.core import callback

from .pairing import PairingManager
from .history import RANGE_BUCKETS, bucket, bucket_bounds, summarise
from .intercom import CallBook, enabled_for, roster_audience, visible_layout
from .const import DATA_CALL_BOOK, DATA_PANEL_SOCKETS, DATA_PAIRINGS, DATA_WEBSOCKET_REGISTERED, DATA_SCHEDULES, DOMAIN
from .registry import PanelRegistry
from .permissions import allowed_entity_ids, service_allowed
from .schedules import ScheduleManager


class PairingStartView(HomeAssistantView):
    url = "/api/nspanel_companion/pair/start"
    name = "api:nspanel_companion:pair:start"
    requires_auth = False

    def __init__(self, pairings: PairingManager) -> None:
        self._pairings = pairings

    async def post(self, request):
        try:
            data = await request.json()
            pairing, claim = self._pairings.start(str(data.get("device_id", "")), str(data.get("name", "")))
            return web.json_response({**pairing, "claim": claim})
        except (ValueError, TypeError) as err:
            return web.json_response({"error": str(err)}, status=400)


class PairingStatusView(HomeAssistantView):
    url = "/api/nspanel_companion/pair/status"
    name = "api:nspanel_companion:pair:status"
    requires_auth = False

    def __init__(self, pairings: PairingManager) -> None:
        self._pairings = pairings

    async def post(self, request):
        try:
            data = await request.json()
            return web.json_response(self._pairings.claim(str(data.get("request_id", "")), str(data.get("claim", ""))))
        except (ValueError, TypeError) as err:
            return web.json_response({"error": str(err)}, status=400)


class PanelSyncView(HomeAssistantView):
    url = "/api/nspanel_companion/panel/sync"
    name = "api:nspanel_companion:panel:sync"
    requires_auth = False

    def __init__(self, hass) -> None:
        self._hass = hass

    def _registry(self) -> PanelRegistry:
        for key, value in self._hass.data.get(DOMAIN, {}).items():
            if key not in {DATA_PAIRINGS, DATA_WEBSOCKET_REGISTERED} and isinstance(value, PanelRegistry):
                return value
        raise ValueError("NSPanel Companion is not configured")

    async def post(self, request):
        try:
            data = await request.json()
            panel_id = str(data.get("panel_id", ""))
            authorization = request.headers.get("Authorization", "")
            token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
            registry = self._registry()
            record = registry.heartbeat(panel_id, token, data)
            current_revision = str(data.get("layout_revision", ""))
            stored = record.get("layout") if record.get("layout_revision") != current_revision else None
            layout = visible_layout(stored) if stored else None
            return web.json_response({
                "panel_id": panel_id,
                "panel_name": record.get("name"),
                "layout_revision": record.get("layout_revision"),
                "layout": layout,
                "heartbeat_seconds": 15,
            })
        except ValueError as err:
            return web.json_response({"error": str(err)}, status=401)


class PanelWebSocketView(HomeAssistantView):
    url = "/api/nspanel_companion/panel/ws"
    name = "api:nspanel_companion:panel:ws"
    requires_auth = False

    def __init__(self, hass) -> None:
        self._hass = hass

    def _registry(self) -> PanelRegistry:
        for key, value in self._hass.data.get(DOMAIN, {}).items():
            if key not in {DATA_PAIRINGS, DATA_WEBSOCKET_REGISTERED} and isinstance(value, PanelRegistry):
                return value
        raise ValueError("NSPanel Companion is not configured")

    async def get(self, request):
        panel_id = request.query.get("panel_id", "")
        authorization = request.headers.get("Authorization", "")
        token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
        registry = self._registry()
        if not registry.authenticate(panel_id, token):
            return web.json_response({"error": "Invalid panel credentials"}, status=401)
        layout = visible_layout(registry.layout(panel_id) or {})
        entities = allowed_entity_ids(layout, self._hass.states.async_entity_ids())
        doorbell_config = layout.get("doorbell") or {}
        socket = web.WebSocketResponse(heartbeat=20)
        await socket.prepare(request)

        def state_json(state):
            return {"entity_id": state.entity_id, "state": state.state, "attributes": dict(state.attributes)}

        await socket.send_json({
            "type": "initial_states",
            "server_time_ms": int(time.time() * 1000),
            "server_timezone": self._hass.config.time_zone,
            "states": [state_json(state) for entity_id in entities if (state := self._hass.states.get(entity_id))],
        })
        schedules: ScheduleManager = self._hass.data[DOMAIN][DATA_SCHEDULES]
        await socket.send_json({"type": "schedules", "schedules": schedules.list_for(entities)})

        weather_entities = [entity_id for entity_id in entities if entity_id.startswith("weather.")]

        async def send_forecast(entity_ids, forecast_type: str) -> None:
            if socket.closed or not entity_ids:
                return
            try:
                response = await self._hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": entity_ids, "type": forecast_type},
                    blocking=True,
                    return_response=True,
                )
                for entity_id, value in (response or {}).items():
                    forecast = value.get("forecast") if isinstance(value, dict) else None
                    if isinstance(forecast, list) and not socket.closed:
                        await socket.send_json({
                            "type": "weather_forecast",
                            "entity_id": entity_id,
                            "forecast_type": forecast_type,
                            "forecast": forecast,
                        })
            except Exception:  # Forecast support differs between weather providers.
                return

        await send_forecast(weather_entities, "daily")
        await send_forecast(weather_entities, "hourly")

        async def history_samples(entity_id: str, span: str) -> list[tuple[float, float]]:
            """Timestamped readings for a span, from whichever source has them.

            Long-term statistics first: the recorder already keeps hourly
            means and an hourly mean is a bucket. A sensor without a
            state_class has none, so its raw states are read instead — more
            expensive, and only as far back as the purge window reaches.
            """
            from homeassistant.components.recorder import get_instance, history as rec_history
            from homeassistant.components.recorder.statistics import statistics_during_period

            start, end, _ = bucket_bounds(span, time.time())
            began = dt_util.utc_from_timestamp(start)
            ended = dt_util.utc_from_timestamp(end)
            period = "5minute" if span in {"6h", "24h"} else ("hour" if span == "7d" else "day")
            recorder = get_instance(self._hass)

            stats = await recorder.async_add_executor_job(
                lambda: statistics_during_period(
                    self._hass, began, ended, {entity_id}, period,
                    None, {"mean", "min", "max"},
                ),
            )
            rows = (stats or {}).get(entity_id) or []
            samples = [
                (float(row["start"]), float(row["mean"]))
                for row in rows
                if row.get("mean") is not None
            ]
            if samples:
                return samples

            states = await recorder.async_add_executor_job(
                lambda: rec_history.state_changes_during_period(
                    self._hass, began, ended, entity_id, include_start_time_state=True,
                ),
            )
            samples = []
            for state in (states or {}).get(entity_id, []):
                try:
                    samples.append((state.last_updated.timestamp(), float(state.state)))
                except (TypeError, ValueError):
                    continue  # unavailable, unknown, or simply not a number
            return samples

        async def send_history(entity_id: str, span: str) -> None:
            if socket.closed or entity_id not in entities or span not in RANGE_BUCKETS:
                return
            try:
                samples = await history_samples(entity_id, span)
            except Exception:  # a recorder that is absent, purged or busy
                return
            # One "now" for both the bucketing and the bounds sent with it,
            # so the panel labels the bars the server actually drew rather
            # than the window it would have drawn a moment later.
            now = time.time()
            buckets = bucket(samples, span, now)
            start, _end, width = bucket_bounds(span, now)
            state = self._hass.states.get(entity_id)
            if socket.closed:
                return
            await socket.send_json({
                "type": "history",
                "entity_id": entity_id,
                "range": span,
                "buckets": buckets,
                # When the row begins and how wide one bar is. Without these
                # the panel can only count backwards from its own clock, and
                # its axis said "-6h, -4h, -2h" because that is all it knew.
                "start_ms": int(start * 1000),
                "bucket_ms": int(width * 1000),
                "summary": summarise(buckets),
                "unit": (state.attributes.get("unit_of_measurement") if state else None) or "",
            })

        # Whatever the layout configures, sent once so the page has something
        # to draw before anyone touches a range button.
        for page in layout.get("pages") or []:
            for widget in page.get("widgets") or []:
                if widget.get("type") == "history":
                    await send_history(
                        str(widget.get("entity_id", "")),
                        str(widget.get("history_range", "24h")),
                    )

        @callback
        def state_changed(event) -> None:
            state = event.data.get("new_state")
            if state is not None and state.entity_id in entities and not socket.closed:
                self._hass.async_create_task(socket.send_json({"type": "state_changed", "state": state_json(state)}))
                if state.entity_id.startswith("weather."):
                    self._hass.async_create_task(send_forecast([state.entity_id], "daily"))
                    self._hass.async_create_task(send_forecast([state.entity_id], "hourly"))
            old_state = event.data.get("old_state")
            if (
                not socket.closed
                and doorbell_config.get("enabled", False)
                and state is not None
                and state.entity_id == doorbell_config.get("trigger_entity_id")
                and state.state == "on"
                and (old_state is None or old_state.state != "on")
            ):
                self._hass.async_create_task(socket.send_json({
                    "type": "doorbell",
                    "data": {
                        "stream_base_url": doorbell_config.get("stream_base_url", ""),
                        "stream_name": doorbell_config.get("stream_name", ""),
                        "talkback_url": doorbell_config.get("talkback_url", ""),
                        "talkback_key": doorbell_config.get("talkback_key", ""),
                        "quiet_mode": doorbell_config.get("quiet_mode", False),
                        "chime": doorbell_config.get("chime", "off"),
                        "chime_volume": doorbell_config.get("chime_volume", 70),
                        "talkback_gain": doorbell_config.get("talkback_gain", 100),
                        "auto_close_ms": doorbell_config.get("auto_close_ms", 60000),
                        "talk_extend_ms": doorbell_config.get("talk_extend_ms", 15000) if doorbell_config.get("talk_extend_enabled", True) else 0,
                    },
                }))

        @callback
        def doorbell(event) -> None:
            targets = event.data.get("panel_ids")
            target = event.data.get("panel_id")
            if (
                not socket.closed
                and (target is None or target == panel_id)
                and (not isinstance(targets, list) or panel_id in targets)
            ):
                self._hass.async_create_task(socket.send_json({"type": "doorbell", "data": dict(event.data)}))

        unsub_state = self._hass.bus.async_listen("state_changed", state_changed)
        unsub_doorbell = self._hass.bus.async_listen("nspanel_doorbell", doorbell)
        sockets = self._hass.data.setdefault(DOMAIN, {}).setdefault(DATA_PANEL_SOCKETS, {})
        sockets[panel_id] = socket
        book: CallBook = self._hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_CALL_BOOK, CallBook(),
        )

        def intercom_known() -> list[dict]:
            """Every registered panel, with whether it is opted in and online."""
            known = []
            for record in registry.list_public():
                other_id = record["panel_id"]
                known.append({
                    "panel_id": other_id,
                    "name": record.get("name"),
                    "enabled": enabled_for(registry.layout(other_id) or {}),
                    "connected": other_id in sockets,
                })
            return known

        async def send_roster_to_all(departed: str | None = None) -> None:
            """Re-send every online panel its own view of who it may call.

            A panel arriving or leaving changes the list every other panel
            holds, so all of them are told, not just the one whose socket
            moved. Each gets its own roster because the list excludes its
            own entry.
            """
            known = intercom_known()
            for viewer in roster_audience(known, departed):
                target = sockets.get(viewer)
                if target is None or target.closed:
                    continue
                await target.send_json({
                    "type": "intercom_roster",
                    "panels": book.roster(known, viewer=viewer),
                })

        async def tell(target: str, payload: dict) -> None:
            other = sockets.get(target)
            if other is not None and not other.closed:
                await other.send_json(payload)

        await send_roster_to_all()
        try:
            async for message in socket:
                if message.type != WSMsgType.TEXT:
                    continue
                data = {}
                try:
                    data = message.json()
                    if data.get("type") == "intercom_call":
                        callee = str(data.get("panel_id", ""))
                        call_id = book.open(panel_id, callee) if enabled_for(layout) else None
                        if call_id is None:
                            await socket.send_json({"type": "intercom_busy"})
                            continue
                        caller_name = next(
                            (r.get("name") for r in registry.list_public()
                             if r["panel_id"] == panel_id),
                            panel_id,
                        )
                        callee_intercom = (registry.layout(callee) or {}).get("intercom") or {}
                        await tell(callee, {
                            "type": "intercom_ring",
                            "call_id": call_id,
                            "panel_id": panel_id,
                            "name": caller_name or panel_id,
                            "ring": callee_intercom.get("ring", "off"),
                            "ring_volume": callee_intercom.get("ring_volume", 70),
                        })
                        await socket.send_json({"type": "intercom_calling", "call_id": call_id})
                        continue
                    if data.get("type") in {"intercom_answer", "intercom_decline"}:
                        call_id = str(data.get("call_id", ""))
                        other = book.partner(call_id, panel_id)
                        if other is None:
                            continue
                        if data["type"] == "intercom_decline":
                            book.close(call_id)
                            await tell(other, {"type": "intercom_end", "call_id": call_id})
                        else:
                            await tell(other, {"type": "intercom_answer", "call_id": call_id})
                        continue
                    if data.get("type") == "intercom_signal":
                        # Relayed without being read: the SDP and ICE are the
                        # panels' business, and Home Assistant holding an
                        # opinion about them is a third thing to keep in step.
                        call_id = str(data.get("call_id", ""))
                        other = book.partner(call_id, panel_id)
                        if other is not None:
                            await tell(other, {
                                "type": "intercom_signal",
                                "call_id": call_id,
                                "signal": data.get("signal"),
                            })
                        continue
                    if data.get("type") == "intercom_end":
                        call_id = str(data.get("call_id", ""))
                        for other in book.close(call_id):
                            if other != panel_id:
                                await tell(other, {"type": "intercom_end", "call_id": call_id})
                        continue
                    if data.get("type") == "history_request":
                        await send_history(
                            str(data.get("entity_id", "")), str(data.get("range", "24h")),
                        )
                        continue
                    if data.get("type") == "schedule_upsert":
                        await schedules.async_upsert(dict(data.get("schedule") or {}), entities)
                        await socket.send_json({"type": "schedules", "schedules": schedules.list_for(entities)})
                        continue
                    if data.get("type") == "schedule_delete":
                        await schedules.async_delete(str(data.get("schedule_id", "")), entities)
                        await socket.send_json({"type": "schedules", "schedules": schedules.list_for(entities)})
                        continue
                    if data.get("type") != "call_service":
                        raise ValueError("Unsupported panel message")
                    entity_id = str(data.get("entity_id", ""))
                    domain = str(data.get("domain", ""))
                    service = str(data.get("service", ""))
                    if not service_allowed(entity_id, domain, service, entities):
                        raise ValueError("Service is not allowed for this panel")
                    service_data = dict(data.get("service_data") or {})
                    service_data["entity_id"] = entity_id
                    await self._hass.services.async_call(domain, service, service_data, blocking=False)
                    await socket.send_json({"type": "call_result", "id": data.get("id"), "success": True})
                except (ValueError, TypeError) as err:
                    await socket.send_json({"type": "call_result", "id": data.get("id") if isinstance(data, dict) else None, "success": False, "error": str(err)})
        finally:
            unsub_state()
            unsub_doorbell()
            # Only clear the entry if it is still this connection: a panel
            # that reconnected before this one unwound has already replaced
            # it, and dropping that would lose the live socket.
            if sockets.get(panel_id) is socket:
                sockets.pop(panel_id, None)
            # A panel whose socket went away leaves whatever call it was in,
            # and the other end is told rather than left listening to a link
            # that will never carry anything again.
            for stranded in book.drop_panel(panel_id):
                other = sockets.get(stranded)
                if other is not None and not other.closed:
                    self._hass.async_create_task(
                        other.send_json({"type": "intercom_end", "call_id": ""}),
                    )
            # And everyone still online is told it has gone, so a panel that
            # is no longer there stops being offered as something to call.
            self._hass.async_create_task(send_roster_to_all(departed=panel_id))
        return socket


def register_pairing_views(hass, pairings: PairingManager) -> None:
    hass.http.register_view(PairingStartView(pairings))
    hass.http.register_view(PairingStatusView(pairings))
    hass.http.register_view(PanelSyncView(hass))
    hass.http.register_view(PanelWebSocketView(hass))
