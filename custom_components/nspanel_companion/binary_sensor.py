"""Whether the panel is reachable, and whether anyone is standing at it."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import PanelEntity, async_setup_panel_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    await async_setup_panel_platform(
        hass, entry, async_add_entities,
        lambda registry, panel_id: (
            PanelConnected(registry, panel_id),
            PanelApproach(registry, panel_id),
        ),
    )


class PanelConnected(PanelEntity, BinarySensorEntity):
    """Whether the panel is talking to Home Assistant at all."""

    _attr_translation_key = "connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_connected"

    @property
    def available(self) -> bool:
        # The one entity that must answer while the panel is away: saying so
        # is its whole job, and an unavailable connectivity sensor tells you
        # nothing you could not already see.
        return True

    @property
    def is_on(self) -> bool:
        return self._socket_open


class PanelApproach(PanelEntity, BinarySensorEntity):
    """Someone is standing at this panel.

    Every panel has a proximity sensor, it already drives wake-on-approach,
    and until now it told Home Assistant nothing. With an area assigned it is
    a presence signal in every room that has a panel, on hardware already
    bought and mounted.

    Off by default all the same: a presence sensor nobody asked for is a
    privacy question, not a convenience.
    """

    _attr_translation_key = "approach"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_entity_registry_enabled_default = False

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_approach"

    @property
    def is_on(self) -> bool | None:
        return self._state.approach
