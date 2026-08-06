"""NSPanel Companion integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_PAIRINGS, DATA_PANEL_DISCOVERY, DATA_SCRYPTED_DISCOVERY, DATA_WEBSOCKET_REGISTERED, DOMAIN
from .frontend import async_register_panel, async_setup_frontend_assets, async_unregister_panel
from .http import register_pairing_views
from .pairing import PairingManager
from .panel_discovery import PanelDiscovery
from .registry import PanelRegistry
from .scrypted import ScryptedDiscovery
from .websocket import async_register_websocket_commands


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration-level APIs once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get(DATA_WEBSOCKET_REGISTERED):
        pairings = domain_data[DATA_PAIRINGS] = PairingManager()
        register_pairing_views(hass, pairings)
        async_register_websocket_commands(hass)
        await async_setup_frontend_assets(hass)
        discovery = domain_data[DATA_SCRYPTED_DISCOVERY] = ScryptedDiscovery(hass)
        await discovery.async_start()
        domain_data[DATA_PANEL_DISCOVERY] = PanelDiscovery(hass)
        domain_data[DATA_WEBSOCKET_REGISTERED] = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Load the persistent panel registry."""
    registry = PanelRegistry(hass, entry.entry_id)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = registry
    discovery = hass.data[DOMAIN].get(DATA_PANEL_DISCOVERY)
    if isinstance(discovery, PanelDiscovery):
        await discovery.async_set_passive(registry.passive_panel_discovery)
    async_register_panel(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one config entry."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    async_unregister_panel(hass)
    return True
