"""The notify action: put a notification on one panel, an area's, or several.

Targets are Home Assistant's own — devices, areas, or an entity belonging to
a panel — because a panel is a device with an area. Delivery is to panels
that are connected now. Nothing is queued: a notification that arrives when
a panel next connects, hours later, is news about something already over.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
import uuid

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DATA_PANEL_SOCKETS, DOMAIN
from .notifications import NOTIFICATION_SOUNDS

SERVICE_NOTIFY = "notify"
IMPORTANCE = ("normal", "important")

_PAYLOAD = vol.Schema(
    {
        vol.Required("message"): vol.All(str, vol.Length(min=1, max=1000)),
        vol.Optional("title", default=""): vol.All(str, vol.Length(max=120)),
        vol.Optional("importance", default="normal"): vol.In(IMPORTANCE),
        # Overrides the type's sound for this one notification.
        vol.Optional("sound"): vol.In(NOTIFICATION_SOUNDS),
    },
    extra=vol.REMOVE_EXTRA,
)


def payload(data: dict[str, Any]) -> dict[str, Any]:
    """What a panel receives, validated, with an id and the time it was sent."""
    value = _PAYLOAD(dict(data))
    value["id"] = uuid.uuid4().hex
    value["sent_at"] = datetime.now(UTC).isoformat()
    return value


def _ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def resolve_panels(
    devices: Iterable[Any], entity_devices: dict[str, str | None], target: dict[str, Any],
) -> list[str]:
    """Which panels a target names, each once, in the order first named.

    `devices` are device-registry entries; only those identified by this
    integration are panels. `entity_devices` maps an entity to its device.
    """
    panel_for: dict[str, str] = {}
    area_of: dict[str, str | None] = {}
    for device in devices:
        # Indexed rather than unpacked: Home Assistant does not hold every
        # integration to two-part identifiers, and one of three parts in the
        # house would otherwise fail every notification.
        panel = next(
            (str(ident[1]) for ident in device.identifiers if len(ident) >= 2 and ident[0] == DOMAIN),
            None,
        )
        if panel is not None:
            panel_for[device.id] = panel
            area_of[device.id] = device.area_id
    wanted_devices = _ids(target.get("device_id"))
    wanted_devices += [
        device_id
        for entity in _ids(target.get("entity_id"))
        if (device_id := entity_devices.get(entity))
    ]
    areas = set(_ids(target.get("area_id")))
    wanted_devices += [device_id for device_id, area in area_of.items() if area in areas]
    panels: list[str] = []
    for device_id in wanted_devices:
        panel = panel_for.get(device_id)
        if panel is not None and panel not in panels:
            panels.append(panel)
    return panels


def panels_for_targets(hass: HomeAssistant, target: dict[str, Any]) -> list[str]:
    devices = dr.async_get(hass).devices.values()
    entities = er.async_get(hass)
    entity_devices = {
        entity_id: entry.device_id
        for entity_id in _ids(target.get("entity_id"))
        if (entry := entities.async_get(entity_id)) is not None
    }
    return resolve_panels(devices, entity_devices, target)


async def deliver(hass: HomeAssistant, panels: list[str], data: dict[str, Any]) -> int:
    """Send to each panel that is listening; return how many were."""
    sockets = hass.data.get(DOMAIN, {}).get(DATA_PANEL_SOCKETS, {})
    delivered = 0
    for panel_id in panels:
        socket = sockets.get(panel_id)
        if socket is None or socket.closed:
            continue
        try:
            await socket.send_json({"type": "notification", "data": data})
        except Exception:  # noqa: BLE001 - a panel that went away mid-send
            continue
        delivered += 1
    return delivered


def async_register_services(hass: HomeAssistant) -> None:
    async def notify(call: ServiceCall) -> None:
        data = payload({key: value for key, value in call.data.items()
                        if key not in ("device_id", "area_id", "entity_id")})
        target = {key: call.data.get(key) for key in ("device_id", "area_id", "entity_id")}
        await deliver(hass, panels_for_targets(hass, target), data)

    hass.services.async_register(DOMAIN, SERVICE_NOTIFY, notify)
