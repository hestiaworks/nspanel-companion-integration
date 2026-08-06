"""Diagnostics for NSPanel Companion."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .registry import PanelRegistry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    """Return data safe for a diagnostics download."""
    registry = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    panels = registry.list_public() if isinstance(registry, PanelRegistry) else []
    return {
        "entry": {"entry_id": entry.entry_id, "version": entry.version},
        "panel_count": len(panels),
        "panels": panels,
    }

