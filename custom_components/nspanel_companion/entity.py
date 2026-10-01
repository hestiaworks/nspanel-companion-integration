"""What every panel entity has in common.

All of them hang off the device the registry already creates, listen on one
dispatcher signal per panel, and go unavailable while that panel's websocket
is closed — a lux reading from a panel unplugged an hour ago is worse than
no reading.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_PANEL_SOCKETS, DOMAIN
from .panel_state import SIGNAL_PANEL_ADDED, PanelState, signal_for


class PanelEntity(Entity):
    """One entity belonging to one panel."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, registry, panel_id: str) -> None:
        self._registry = registry
        self._panel_id = panel_id
        self._state: PanelState = registry.panel_state(panel_id)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, panel_id)})

    @property
    def _socket_open(self) -> bool:
        sockets = self.hass.data.get(DOMAIN, {}).get(DATA_PANEL_SOCKETS, {})
        socket = sockets.get(self._panel_id)
        return socket is not None and not socket.closed

    @property
    def available(self) -> bool:
        return self._socket_open

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_for(self._panel_id), self._state_reported,
            )
        )

    @callback
    def _state_reported(self, state: PanelState) -> None:
        self._state = state
        self.async_write_ha_state()


async def async_setup_panel_platform(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    build: Callable[[object, str], Iterable[PanelEntity]],
) -> None:
    """Add one platform's entities for every panel, now and later.

    Building only from the panel list at setup would leave a panel paired
    afterwards with no entities until Home Assistant next started, which is
    a poor thing to discover on the day you hang a new panel.
    """
    registry = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        entity
        for panel in registry.list_public()
        for entity in build(registry, panel["panel_id"])
    )

    @callback
    def panel_added(panel_id: str) -> None:
        async_add_entities(build(registry, panel_id))

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_PANEL_ADDED, panel_added)
    )
