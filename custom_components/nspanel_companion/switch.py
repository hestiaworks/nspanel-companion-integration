"""The panel's screen, on or off."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import PanelEntity, async_setup_panel_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    await async_setup_panel_platform(
        hass, entry, async_add_entities,
        lambda registry, panel_id: (PanelScreen(registry, panel_id),),
    )


class PanelScreen(PanelEntity, SwitchEntity):
    """The screen.

    A switch rather than a light: Home Assistant's area page lifts every
    light into its Lights section and counts it among the room's lamps, so
    turning a room's lights off would also blank its panel. As a switch it
    stays under the panel's own heading with everything else the panel has.
    """

    _attr_translation_key = "screen"
    _attr_entity_registry_enabled_default = False

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_screen"

    @property
    def is_on(self) -> bool | None:
        return self._state.screen_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._registry.async_command(self._panel_id, "set_screen", on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._registry.async_command(self._panel_id, "set_screen", on=False)
