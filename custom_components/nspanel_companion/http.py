"""Unauthenticated local bootstrap endpoints for physical panel pairing."""

from __future__ import annotations

from aiohttp import WSMsgType, web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import callback

from .pairing import PairingManager
from .const import DATA_PAIRINGS, DATA_WEBSOCKET_REGISTERED, DATA_SCHEDULES, DOMAIN
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
            layout = record.get("layout") if record.get("layout_revision") != current_revision else None
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
        layout = registry.layout(panel_id) or {}
        entities = allowed_entity_ids(layout, self._hass.states.async_entity_ids())
        doorbell_config = layout.get("doorbell") or {}
        socket = web.WebSocketResponse(heartbeat=20)
        await socket.prepare(request)

        def state_json(state):
            return {"entity_id": state.entity_id, "state": state.state, "attributes": dict(state.attributes)}

        await socket.send_json({
            "type": "initial_states",
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
        try:
            async for message in socket:
                if message.type != WSMsgType.TEXT:
                    continue
                data = {}
                try:
                    data = message.json()
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
        return socket


def register_pairing_views(hass, pairings: PairingManager) -> None:
    hass.http.register_view(PairingStartView(pairings))
    hass.http.register_view(PairingStatusView(pairings))
    hass.http.register_view(PanelSyncView(hass))
    hass.http.register_view(PanelWebSocketView(hass))
