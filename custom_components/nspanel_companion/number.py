"""The panel's screen brightness, as a percentage."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import PanelEntity, async_setup_panel_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    await async_setup_panel_platform(
        hass, entry, async_add_entities,
        lambda registry, panel_id: (PanelBrightness(registry, panel_id),),
    )


class PanelBrightness(PanelEntity, NumberEntity):
    """How bright the screen is held, in the panel's own per cent.

    Unknown while the panel leaves brightness to Android, because then it
    does not know. Setting a value lights the screen at that level: someone
    choosing a brightness wants to see it. It holds until the screen next
    goes dark, and then the panel's own brightness settings take over again.
    """

    _attr_translation_key = "brightness"
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_entity_registry_enabled_default = False

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_brightness"

    @property
    def native_value(self) -> int | None:
        return self._state.brightness

    async def async_set_native_value(self, value: float) -> None:
        await self._registry.async_command(
            self._panel_id, "set_screen", on=True, brightness=round(value),
        )
