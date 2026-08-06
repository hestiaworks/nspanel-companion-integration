"""Persistent Home Assistant-owned schedules for panel controls."""

from __future__ import annotations

from datetime import timedelta
import re
import uuid
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

STORAGE_VERSION = 1
STORAGE_KEY = "nspanel_companion.schedules"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
DIRECT_ACTIONS = {
    "light": {"turn_on", "turn_off", "toggle"},
    "switch": {"turn_on", "turn_off", "toggle"},
    "input_boolean": {"turn_on", "turn_off", "toggle"},
    "fan": {"turn_on", "turn_off", "toggle"},
    "cover": {"open", "close", "set_position", "gradual_open", "gradual_close"},
}


class ScheduleManager:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._items: dict[str, dict[str, Any]] = {}
        self._last_run: dict[str, str] = {}
        self._unsubscribe = None

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self._items = {str(item["id"]): item for item in data.get("schedules", []) if isinstance(item, dict) and item.get("id")}
        self._unsubscribe = async_track_time_change(self.hass, self._tick, second=0)

    async def async_unload(self) -> None:
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    def list_for(self, entity_ids: set[str]) -> list[dict[str, Any]]:
        return [self._public(item) for item in self._items.values() if item["entity_id"] in entity_ids]

    async def async_upsert(self, value: dict[str, Any], entity_ids: set[str]) -> dict[str, Any]:
        item = self._validate(value, entity_ids)
        schedule_id = str(value.get("id") or uuid.uuid4().hex)
        existing = self._items.get(schedule_id)
        if existing and existing["entity_id"] not in entity_ids:
            raise ValueError("Schedule is not available to this panel")
        item["id"] = schedule_id
        item["created_at"] = existing.get("created_at") if existing else dt_util.utcnow().isoformat()
        self._items[schedule_id] = item
        await self._save()
        return self._public(item)

    async def async_delete(self, schedule_id: str, entity_ids: set[str]) -> None:
        item = self._items.get(schedule_id)
        if not item or item["entity_id"] not in entity_ids:
            raise ValueError("Schedule not found")
        self._items.pop(schedule_id)
        self._last_run.pop(schedule_id, None)
        await self._save()

    @callback
    def _tick(self, now) -> None:
        local = dt_util.as_local(now)
        weekday = WEEKDAYS[local.weekday()]
        clock = local.strftime("%H:%M")
        run_key = local.strftime("%Y-%m-%dT%H:%M")
        for item in self._items.values():
            if not item["enabled"] or item["time"] != clock or weekday not in item["weekdays"]:
                continue
            if self._last_run.get(item["id"]) == run_key:
                continue
            self._last_run[item["id"]] = run_key
            self.hass.async_create_task(self._execute(item))

    async def _execute(self, item: dict[str, Any]) -> None:
        entity_id = item["entity_id"]
        action = item["action"]
        if action.startswith("gradual_"):
            script = item.get("script_entity_id")
            if script:
                await self.hass.services.async_call("script", "turn_on", {"entity_id": script}, blocking=False)
            return
        domain = entity_id.split(".", 1)[0]
        service = {"open": "open_cover", "close": "close_cover", "set_position": "set_cover_position"}.get(action, action)
        data: dict[str, Any] = {"entity_id": entity_id}
        if action == "set_position":
            data["position"] = item["position"]
        await self.hass.services.async_call(domain, service, data, blocking=False)

    def _validate(self, value: dict[str, Any], entity_ids: set[str]) -> dict[str, Any]:
        entity_id = str(value.get("entity_id", ""))
        if entity_id not in entity_ids:
            raise ValueError("Entity is not available to this panel")
        domain = entity_id.split(".", 1)[0]
        action = str(value.get("action", ""))
        if action not in DIRECT_ACTIONS.get(domain, set()):
            raise ValueError("Unsupported schedule action")
        clock = str(value.get("time", ""))
        if not TIME_RE.fullmatch(clock):
            raise ValueError("Time must use HH:MM")
        weekdays = list(dict.fromkeys(str(day) for day in value.get("weekdays", [])))
        if not weekdays or any(day not in WEEKDAYS for day in weekdays):
            raise ValueError("Select at least one valid weekday")
        position = int(value.get("position", 100))
        if not 0 <= position <= 100:
            raise ValueError("Position must be between 0 and 100")
        script = str(value.get("script_entity_id", "")) or None
        if action.startswith("gradual_") and (not script or not script.startswith("script.") or script not in entity_ids):
            raise ValueError("Gradual movement requires a script")
        return {"entity_id": entity_id, "time": clock, "weekdays": weekdays, "action": action,
                "position": position, "script_entity_id": script, "enabled": bool(value.get("enabled", True))}

    def _public(self, item: dict[str, Any]) -> dict[str, Any]:
        result = dict(item)
        result["next_run"] = self._next_run(item)
        return result

    def _next_run(self, item: dict[str, Any]) -> str | None:
        if not item["enabled"]:
            return None
        now = dt_util.now()
        hour, minute = map(int, item["time"].split(":"))
        for offset in range(8):
            candidate = (now + timedelta(days=offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if WEEKDAYS[candidate.weekday()] in item["weekdays"] and candidate > now:
                return candidate.isoformat()
        return None

    async def _save(self) -> None:
        await self._store.async_save({"schedules": list(self._items.values())})
