"""Panels as notify entities, so anything that picks notify targets can pick them."""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import PanelEntity, async_setup_panel_platform
from .notify_service import deliver, payload


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    await async_setup_panel_platform(
        hass, entry, async_add_entities,
        lambda registry, panel_id: (
            PanelNotifications(registry, panel_id),
            PanelImportantNotifications(registry, panel_id),
        ),
    )


class _PanelNotify(PanelEntity, NotifyEntity):
    """One panel as a notify target.

    notify.send_message carries a title and a message and nothing else, so
    which entity is chosen is how a sender chooses importance. Delivery is
    the notify action's own: the panel's sounds, quiet hours and list all
    apply, and a panel that is offline does not receive it later.
    """

    async def _deliver(self, message: str, title: str | None, *, importance: str) -> None:
        # Cut to the action's limits rather than failing: a blueprint's long
        # title should not stop the automation that sent it.
        await deliver(self.hass, [self._panel_id], payload({
            "message": (message or " ")[:1000],
            "title": (title or "")[:120],
            "importance": importance,
        }))


class PanelNotifications(_PanelNotify):
    """A banner that closes itself, following quiet hours."""

    _attr_translation_key = "notifications"

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_notifications"

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        await self._deliver(message, title, importance="normal")


class PanelImportantNotifications(_PanelNotify):
    """A sheet that waits for an answer, and rings even in quiet hours."""

    _attr_translation_key = "important_notifications"

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_important_notifications"

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        await self._deliver(message, title, importance="important")
