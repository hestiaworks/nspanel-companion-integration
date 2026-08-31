"""Authenticated administrator WebSocket API."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url

from .const import DATA_PANEL_SOCKETS, DATA_PAIRINGS, DATA_PANEL_DISCOVERY, DATA_SCRYPTED_DISCOVERY, DATA_WEBSOCKET_REGISTERED, DOMAIN
from .pairing import PairingManager
from .panel_discovery import PanelDiscovery
from .registry import PanelRegistry
from .scrypted import ScryptedDiscovery


def _registry(hass: HomeAssistant) -> PanelRegistry:
    for key, value in hass.data.get(DOMAIN, {}).items():
        if key != DATA_WEBSOCKET_REGISTERED and isinstance(value, PanelRegistry):
            return value
    raise ValueError("NSPanel Companion is not configured")


def _pairings(hass: HomeAssistant) -> PairingManager:
    value = hass.data.get(DOMAIN, {}).get(DATA_PAIRINGS)
    if not isinstance(value, PairingManager):
        raise ValueError("Pairing is not available")
    return value


def _scrypted_discovery(hass: HomeAssistant) -> ScryptedDiscovery:
    value = hass.data.get(DOMAIN, {}).get(DATA_SCRYPTED_DISCOVERY)
    if not isinstance(value, ScryptedDiscovery):
        raise ValueError("Scrypted discovery is not available")
    return value


def _panel_discovery(hass: HomeAssistant) -> PanelDiscovery:
    value = hass.data.get(DOMAIN, {}).get(DATA_PANEL_DISCOVERY)
    if not isinstance(value, PanelDiscovery):
        raise ValueError("Panel discovery is not available")
    return value


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "nspanel_companion/panels/discovery/scan"})
async def ws_scan_panels(hass, connection, msg) -> None:
    connection.send_result(msg["id"], {
        "panels": await _panel_discovery(hass).async_scan(),
        "passive": _registry(hass).passive_panel_discovery,
    })


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/panels/discovery/settings",
    vol.Required("passive"): bool,
})
async def ws_set_panel_discovery(hass, connection, msg) -> None:
    registry = _registry(hass)
    await registry.async_set_passive_panel_discovery(msg["passive"])
    await _panel_discovery(hass).async_set_passive(msg["passive"])
    connection.send_result(msg["id"], {"passive": registry.passive_panel_discovery})


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/panels/discovery/connect",
    vol.Required("device_id"): str,
    vol.Required("base_url"): str,
})
async def ws_connect_discovered_panel(hass, connection, msg) -> None:
    discovered = next(
        (item for item in _panel_discovery(hass).list_public()
         if item["id"] == msg["device_id"] and item["base_url"] == msg["base_url"]),
        None,
    )
    if not discovered:
        connection.send_error(msg["id"], "panel_not_discovered", "Panel is no longer available")
        return
    try:
        session = async_get_clientsession(hass)
        async with session.post(
            f"{discovered['base_url']}/pair",
            json={"ha_url": get_url(hass, allow_internal=True, prefer_external=False)},
            timeout=10,
        ) as response:
            if response.status != 200:
                raise ValueError("Panel rejected the pairing request")
        pairing = None
        for _ in range(20):
            pairing = _pairings(hass).find_device_public(msg["device_id"])
            if pairing:
                break
            await asyncio.sleep(0.25)
        if not pairing:
            raise ValueError("Panel did not create a pairing request")
        connection.send_result(msg["id"], pairing)
    except Exception as err:
        connection.send_error(msg["id"], "panel_connect_failed", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "nspanel_companion/scrypted/list"})
async def ws_list_scrypted(hass, connection, msg) -> None:
    registry = _registry(hass)
    connection.send_result(msg["id"], {
        "discovered": _scrypted_discovery(hass).list_public(),
        "paired": registry.list_scrypted_bridges(),
    })


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/scrypted/pair",
    vol.Required("base_url"): str,
    vol.Required("code"): str,
})
async def ws_pair_scrypted(hass, connection, msg) -> None:
    try:
        result = await _registry(hass).async_pair_scrypted(msg["base_url"], msg["code"])
        connection.send_result(msg["id"], result)
    except ValueError as err:
        connection.send_error(msg["id"], "scrypted_pairing_failed", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/scrypted/unpair",
    vol.Required("bridge_id"): str,
    vol.Optional("clear_assignments", default=False): bool,
})
async def ws_unpair_scrypted(hass, connection, msg) -> None:
    try:
        result = await _registry(hass).async_unpair_scrypted(
            msg["bridge_id"], msg["clear_assignments"]
        )
        connection.send_result(msg["id"], result)
    except ValueError as err:
        connection.send_error(msg["id"], "scrypted_unpair_failed", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "nspanel_companion/updater/status"})
async def ws_updater_status(hass, connection, msg) -> None:
    connection.send_result(msg["id"], {"paired": _registry(hass).updater_public()})


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/updater/pair",
    vol.Required("base_url"): str,
    vol.Required("code"): str,
})
async def ws_pair_updater(hass, connection, msg) -> None:
    try:
        connection.send_result(msg["id"], await _registry(hass).async_pair_updater(msg["base_url"], msg["code"]))
    except ValueError as err:
        connection.send_error(msg["id"], "updater_pairing_failed", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "nspanel_companion/updater/autopair"})
async def ws_autopair_updater(hass, connection, msg) -> None:
    """Pair an updater add-on running on this host, without a copied code."""
    try:
        connection.send_result(msg["id"], await _registry(hass).async_autopair_updater())
    except ValueError as err:
        connection.send_error(msg["id"], "updater_pairing_failed", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "nspanel_companion/updater/unpair"})
async def ws_unpair_updater(hass, connection, msg) -> None:
    try:
        await _registry(hass).async_unpair_updater()
        connection.send_result(msg["id"], {"unpaired": True})
    except ValueError as err:
        connection.send_error(msg["id"], "updater_unpair_failed", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/updater/discover",
    vol.Required("subnet"): str,
})
async def ws_updater_discover(hass, connection, msg) -> None:
    try:
        result = await _registry(hass).async_updater_request(
            "/api/discover", {"subnet": msg["subnet"]}
        )
        devices = result.get("devices", [])
        result["devices"] = [
            device for device in devices
            if device.get("adb_state") == "device"
            and device.get("classification") in {"nspanel-companion", "probable-nspanel"}
        ]
        connection.send_result(msg["id"], result)
    except ValueError as err:
        connection.send_error(msg["id"], "updater_discovery_failed", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/updater/update",
    vol.Required("address"): str,
    vol.Required("classification"): vol.In(["nspanel-companion", "probable-nspanel"]),
    vol.Optional("source", default="github"): vol.In(["github", "local"]),
    vol.Optional("migrate_debug", default=False): bool,
})
async def ws_updater_update(hass, connection, msg) -> None:
    try:
        connection.send_result(msg["id"], await _registry(hass).async_updater_request("/api/update", {
            "address": msg["address"], "classification": msg["classification"],
            "source": msg["source"], "migrate_debug": msg["migrate_debug"],
        }))
    except ValueError as err:
        connection.send_error(msg["id"], "updater_update_failed", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/panels/restart",
    vol.Required("panel_id"): str,
    vol.Optional("address", default=""): str,
    vol.Optional("device", default=False): bool,
})
async def ws_restart_panel(hass, connection, msg) -> None:
    """Restart a panel's app, down its own socket where there is one.

    A panel holding a live socket can be told directly and does it itself.
    A panel that is not holding one is the case worth having a second route
    for at all — it is why anyone reaches for this — so that falls to the
    add-on, which drives ADB and does not need the app to be answering.

    `device` reboots Android instead of relaunching the app. That can only
    go over ADB: an app cannot restart the device it is running on.
    """
    # Rebooting the panel is not something its app can do to the device it
    # runs on, so that never goes down the socket.
    socket = hass.data.get(DOMAIN, {}).get(DATA_PANEL_SOCKETS, {}).get(msg["panel_id"])
    if not msg["device"] and socket is not None and not socket.closed:
        try:
            await socket.send_json({"type": "restart"})
            connection.send_result(msg["id"], {"restarted": True, "via": "panel"})
            return
        except Exception:  # noqa: BLE001 - a dead socket falls through to ADB
            pass
    address = msg["address"]
    if not address:
        connection.send_error(
            msg["id"], "panel_restart_failed",
            "The panel is not connected, and no address was given to reach it over ADB",
        )
        return
    try:
        result = await _registry(hass).async_updater_request(
            "/api/restart", {"address": address, "device": msg["device"]},
        )
        connection.send_result(msg["id"], {"restarted": True, "via": "updater", **result})
    except ValueError as err:
        connection.send_error(msg["id"], "panel_restart_failed", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/scrypted/doorbells",
    vol.Required("bridge_id"): str,
})
async def ws_list_scrypted_doorbells(hass, connection, msg) -> None:
    try:
        doorbells = await _registry(hass).async_scrypted_doorbells(msg["bridge_id"])
        connection.send_result(msg["id"], [
            {key: value for key, value in item.items() if key != "talkback_key"}
            for item in doorbells
        ])
    except ValueError as err:
        connection.send_error(msg["id"], "scrypted_unavailable", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/scrypted/assign",
    vol.Required("panel_id"): str,
    vol.Required("bridge_id"): str,
    vol.Required("doorbell_id"): str,
})
async def ws_assign_scrypted_doorbell(hass, connection, msg) -> None:
    try:
        panel = await _registry(hass).async_assign_scrypted_doorbell(
            msg["panel_id"], msg["bridge_id"], msg["doorbell_id"]
        )
        connection.send_result(msg["id"], panel)
    except ValueError as err:
        connection.send_error(msg["id"], "scrypted_assignment_failed", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "nspanel_companion/panels/list"})
async def ws_list_panels(hass, connection, msg) -> None:
    """List sanitized panel records."""
    try:
        connection.send_result(msg["id"], _registry(hass).list_public())
    except ValueError as err:
        connection.send_error(msg["id"], "not_configured", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/panels/register",
    vol.Required("name"): str,
    vol.Required("device_id"): str,
})
async def ws_register_panel(hass, connection, msg) -> None:
    """Register a panel and reveal its token once."""
    try:
        panel, token = await _registry(hass).async_register(msg["name"], msg["device_id"])
        connection.send_result(msg["id"], {"panel": panel, "token": token})
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_panel", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/panels/rename",
    vol.Required("panel_id"): str,
    vol.Required("name"): str,
})
async def ws_rename_panel(hass, connection, msg) -> None:
    """Update a panel's human-readable name."""
    try:
        panel = await _registry(hass).async_rename(msg["panel_id"], msg["name"])
        connection.send_result(msg["id"], panel)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_panel_name", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/layout/get",
    vol.Required("panel_id"): str,
})
async def ws_get_layout(hass, connection, msg) -> None:
    """Return the assigned layout."""
    try:
        connection.send_result(msg["id"], _registry(hass).layout(msg["panel_id"]))
    except ValueError as err:
        connection.send_error(msg["id"], "unknown_panel", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/panels/diagnostics",
    vol.Required("panel_id"): str,
})
async def ws_get_panel_diagnostics(hass, connection, msg) -> None:
    """Return the latest bounded and sanitized report uploaded by a panel."""
    try:
        connection.send_result(msg["id"], {
            "panel_id": msg["panel_id"],
            "report": _registry(hass).diagnostics(msg["panel_id"]),
        })
    except ValueError as err:
        connection.send_error(msg["id"], "unknown_panel", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/layout/set",
    vol.Required("panel_id"): str,
    vol.Required("layout"): dict,
})
async def ws_set_layout(hass, connection, msg) -> None:
    """Validate, store, and publish a panel layout."""
    try:
        registry = _registry(hass)
        panel = await registry.async_set_layout(msg["panel_id"], msg["layout"])
        connection.send_result(msg["id"], panel)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_layout", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/doorbell/test",
    vol.Required("panel_id"): str,
})
async def ws_test_doorbell(hass, connection, msg) -> None:
    """Send the saved doorbell payload to one panel without a physical ring."""
    try:
        panel_id = msg["panel_id"]
        layout = _registry(hass).layout(panel_id) or {}
        doorbell = layout.get("doorbell") or {}
        if not doorbell.get("stream_base_url"):
            raise ValueError("Configure and publish a doorbell media URL first")
        hass.bus.async_fire("nspanel_doorbell", {
            "panel_id": panel_id,
            "stream_base_url": doorbell.get("stream_base_url", ""),
            "stream_name": doorbell.get("stream_name", ""),
            "talkback_url": doorbell.get("talkback_url", ""),
            "talkback_key": doorbell.get("talkback_key", ""),
            "quiet_mode": doorbell.get("quiet_mode", False),
            "chime": doorbell.get("chime", "off"),
            "chime_volume": doorbell.get("chime_volume", 70),
            "talkback_gain": doorbell.get("talkback_gain", 100),
            "auto_close_ms": doorbell.get("auto_close_ms", 60000),
            "talk_extend_ms": doorbell.get("talk_extend_ms", 15000) if doorbell.get("talk_extend_enabled", True) else 0,
            "test": True,
        })
        connection.send_result(msg["id"], {"sent": True, "panel_id": panel_id})
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_doorbell", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({vol.Required("type"): "nspanel_companion/pairings/list"})
async def ws_list_pairings(hass, connection, msg) -> None:
    """List unexpired requests awaiting physical confirmation."""
    connection.send_result(msg["id"], _pairings(hass).list_public())


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/pairings/approve",
    vol.Required("request_id"): str,
    vol.Required("code"): str,
})
async def ws_approve_pairing(hass, connection, msg) -> None:
    """Approve the code visible on one physical panel."""
    try:
        pairings = _pairings(hass)
        request = pairings.validate_code(msg["request_id"], msg["code"])
        panel, token = await _registry(hass).async_pair(request.name, request.device_id)
        pairing = pairings.approve(request.request_id, msg["code"], token)
        connection.send_result(msg["id"], {"panel": panel, "pairing": pairing})
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_pairing", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/panels/rotate_token",
    vol.Required("panel_id"): str,
})
async def ws_rotate_token(hass, connection, msg) -> None:
    try:
        panel, token = await _registry(hass).async_rotate_token(msg["panel_id"])
        connection.send_result(msg["id"], {"panel": panel, "token": token})
    except ValueError as err:
        connection.send_error(msg["id"], "unknown_panel", str(err))


@websocket_api.require_admin
@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required("type"): "nspanel_companion/panels/revoke",
    vol.Required("panel_id"): str,
})
async def ws_revoke_panel(hass, connection, msg) -> None:
    try:
        connection.send_result(msg["id"], await _registry(hass).async_revoke(msg["panel_id"]))
    except ValueError as err:
        connection.send_error(msg["id"], "unknown_panel", str(err))


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register integration commands."""
    websocket_api.async_register_command(hass, ws_list_panels)
    websocket_api.async_register_command(hass, ws_register_panel)
    websocket_api.async_register_command(hass, ws_rename_panel)
    websocket_api.async_register_command(hass, ws_get_layout)
    websocket_api.async_register_command(hass, ws_get_panel_diagnostics)
    websocket_api.async_register_command(hass, ws_set_layout)
    websocket_api.async_register_command(hass, ws_test_doorbell)
    websocket_api.async_register_command(hass, ws_list_pairings)
    websocket_api.async_register_command(hass, ws_approve_pairing)
    websocket_api.async_register_command(hass, ws_rotate_token)
    websocket_api.async_register_command(hass, ws_revoke_panel)
    websocket_api.async_register_command(hass, ws_list_scrypted)
    websocket_api.async_register_command(hass, ws_pair_scrypted)
    websocket_api.async_register_command(hass, ws_unpair_scrypted)
    websocket_api.async_register_command(hass, ws_list_scrypted_doorbells)
    websocket_api.async_register_command(hass, ws_assign_scrypted_doorbell)
    websocket_api.async_register_command(hass, ws_scan_panels)
    websocket_api.async_register_command(hass, ws_set_panel_discovery)
    websocket_api.async_register_command(hass, ws_connect_discovered_panel)
    websocket_api.async_register_command(hass, ws_updater_status)
    websocket_api.async_register_command(hass, ws_autopair_updater)
    websocket_api.async_register_command(hass, ws_pair_updater)
    websocket_api.async_register_command(hass, ws_unpair_updater)
    websocket_api.async_register_command(hass, ws_updater_discover)
    websocket_api.async_register_command(hass, ws_updater_update)
    websocket_api.async_register_command(hass, ws_restart_panel)
