"""NSPanel Companion integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers import config_validation as cv

from .const import DATA_PAIRINGS, DATA_PANEL_DISCOVERY, DATA_SCRYPTED_DISCOVERY, DATA_WEBSOCKET_REGISTERED, DATA_SCHEDULES, DOMAIN
from .frontend import async_register_panel, async_setup_frontend_assets, async_unregister_panel
from .http import register_pairing_views
from .pairing import PairingManager
from .panel_discovery import PanelDiscovery
from .registry import PanelRegistry
from .scrypted import ScryptedDiscovery
from .schedules import ScheduleManager
from .websocket import async_register_websocket_commands


# There is no YAML configuration: panels are added from the UI config flow, and
# async_setup only registers the APIs the panels and the frontend talk to.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


#: How often to ask what is published. Rarely: a release is a thing that
#: happens a few times a month, and the add-on holds its own hour-long cache
#: behind this, so the interval is about how soon a badge appears rather than
#: about load.
RELEASE_CHECK_INTERVAL = timedelta(hours=6)

#: The panel's own entities. Everything but the wifi signal and the ambient
#: light level ships disabled, so enabling one is a decision someone made on
#: the device page rather than a list nobody asked for.
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.SELECT,
    Platform.SENSOR,
]


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
        schedules = domain_data[DATA_SCHEDULES] = ScheduleManager(hass)
        await schedules.async_load()
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

    # Look for a published release now and every few hours after. The answer
    # is only shown, never acted on: someone still chooses to update a panel.
    # The add-on caches its own lookup, so this costs a request to a
    # neighbouring container rather than one to GitHub.
    async def check_release(_now=None) -> None:
        await registry.async_check_release()

    entry.async_on_unload(
        async_track_time_interval(hass, check_release, RELEASE_CHECK_INTERVAL)
    )
    entry.async_create_background_task(hass, check_release(), "nspanel_release_check")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    async_unregister_panel(hass)
    return True
