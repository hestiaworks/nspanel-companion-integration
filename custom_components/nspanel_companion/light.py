"""The panel's own display, as a light."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import PanelEntity, async_setup_panel_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    await async_setup_panel_platform(
        hass, entry, async_add_entities,
        lambda registry, panel_id: (PanelDisplay(registry, panel_id),),
    )


class PanelDisplay(PanelEntity, LightEntity):
    """The screen, so that "everything off in here" reaches the panels too.

    A light rather than a switch because the panel already has a brightness
    and hiding it would mean a second entity to set it.
    """

    _attr_translation_key = "display"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_entity_registry_enabled_default = False

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_display"

    @property
    def is_on(self) -> bool | None:
        return self._state.screen_on

    @property
    def brightness(self) -> int | None:
        """Home Assistant counts brightness 0-255; the panel counts percent."""
        if self._state.brightness is None:
            return None
        return round(self._state.brightness * 255 / 100)

    async def async_turn_on(self, **kwargs: Any) -> None:
        fields: dict[str, Any] = {"on": True}
        if (level := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            fields["brightness"] = round(level * 100 / 255)
        await self._registry.async_command(self._panel_id, "set_screen", **fields)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._registry.async_command(self._panel_id, "set_screen", on=False)
