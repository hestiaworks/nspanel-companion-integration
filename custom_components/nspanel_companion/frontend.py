"""Serve and register the NSPanel Companion sidebar manager."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import PANEL_COMPONENT, PANEL_MODULE_URL, PANEL_URL_PATH


async def async_setup_frontend_assets(hass: HomeAssistant) -> None:
    """Serve frontend assets once during integration setup."""
    static_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths([
        StaticPathConfig("/nspanel_companion/frontend", str(static_dir), True),
    ])
    frontend.add_extra_js_url(hass, PANEL_MODULE_URL)


def async_register_panel(hass: HomeAssistant) -> None:
    """Attach the administrator sidebar panel for a loaded config entry."""
    frontend.async_register_built_in_panel(
        hass,
        PANEL_COMPONENT,
        sidebar_title="NSPanel Companion",
        sidebar_icon="mdi:tablet-dashboard",
        frontend_url_path=PANEL_URL_PATH,
        require_admin=True,
    )


def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar entry while leaving the static route intact."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
