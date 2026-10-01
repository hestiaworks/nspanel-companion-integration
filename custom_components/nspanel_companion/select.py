"""Which page a panel is showing."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import PanelEntity, async_setup_panel_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    await async_setup_panel_platform(
        hass, entry, async_add_entities,
        lambda registry, panel_id: (PanelPage(registry, panel_id),),
    )


class PanelPage(PanelEntity, SelectEntity):
    """The page on screen.

    Options come from this panel's own layout, so a page that was deleted
    stops being offered rather than failing when someone selects it.
    """

    _attr_translation_key = "page"
    _attr_entity_registry_enabled_default = False

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_page"

    @property
    def options(self) -> list[str]:
        layout = self._registry.layout(self._panel_id) or {}
        return [
            str(page["id"])
            for page in layout.get("pages", [])
            if isinstance(page, dict) and page.get("id")
        ]

    @property
    def current_option(self) -> str | None:
        # A page the layout no longer has would be an invalid option, and
        # Home Assistant logs that on every state write.
        page = self._state.page_id
        return page if page in self.options else None

    async def async_select_option(self, option: str) -> None:
        await self._registry.async_command(self._panel_id, "show_page", page_id=option)
