"""Two things worth asking a panel to do."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import PanelEntity, async_setup_panel_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    await async_setup_panel_platform(
        hass, entry, async_add_entities,
        lambda registry, panel_id: (
            PanelRestart(registry, panel_id),
            PanelReloadLayout(registry, panel_id),
        ),
    )


class PanelRestart(PanelEntity, ButtonEntity):
    """Restart the panel app, without ADB and without a ladder."""

    _attr_translation_key = "restart_app"
    _attr_entity_registry_enabled_default = False

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_restart_app"

    async def async_press(self) -> None:
        await self._registry.async_command(self._panel_id, "restart")


class PanelReloadLayout(PanelEntity, ButtonEntity):
    """Fetch the layout again, for a panel that missed a publish."""

    _attr_translation_key = "reload_layout"
    _attr_entity_registry_enabled_default = False

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_reload_layout"

    async def async_press(self) -> None:
        await self._registry.async_command(self._panel_id, "reload_layout")
