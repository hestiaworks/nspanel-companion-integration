"""On-demand discovery of unpaired NSPanel Companion devices."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components import zeroconf
from homeassistant.core import HomeAssistant, callback
from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser

SERVICE_TYPE = "_nspanel-companion._tcp.local."


class PanelDiscovery:
    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._aiozc = None
        self._browser: AsyncServiceBrowser | None = None
        self._services: dict[str, dict[str, str]] = {}
        self._passive = False

    @property
    def passive(self) -> bool:
        return self._passive

    async def async_set_passive(self, enabled: bool) -> None:
        self._passive = enabled
        if enabled:
            await self._start_browser(clear=False)
        else:
            await self._stop_browser()

    async def async_scan(self, seconds: float = 4.0) -> list[dict[str, str]]:
        self._services.clear()
        await self._start_browser(clear=False)
        await asyncio.sleep(seconds)
        if not self._passive:
            await self._stop_browser()
        return self.list_public()

    def list_public(self) -> list[dict[str, str]]:
        return sorted(self._services.values(), key=lambda item: item["name"].lower())

    async def _start_browser(self, clear: bool) -> None:
        if clear:
            self._services.clear()
        if self._browser:
            return
        self._aiozc = await zeroconf.async_get_instance(self._hass)
        self._browser = AsyncServiceBrowser(self._aiozc, SERVICE_TYPE, handlers=[self._changed])

    async def _stop_browser(self) -> None:
        if self._browser:
            await self._browser.async_cancel()
            self._browser = None

    @callback
    def _changed(self, zeroconf, service_type, name, state_change) -> None:
        if state_change is ServiceStateChange.Removed:
            self._services.pop(name, None)
            return
        self._hass.async_create_task(self._resolve(service_type, name))

    async def _resolve(self, service_type: str, name: str) -> None:
        if not self._aiozc:
            return
        info = await self._aiozc.async_get_service_info(service_type, name, 3000)
        if not info:
            return
        addresses = info.parsed_scoped_addresses()
        if not addresses:
            return
        props: dict[str, Any] = {
            key.decode(errors="replace"): value.decode(errors="replace")
            for key, value in info.properties.items()
        }
        address = next((item for item in addresses if "." in item), addresses[0])
        self._services[name] = {
            "id": str(props.get("id") or name),
            "name": name.removesuffix(f".{SERVICE_TYPE}"),
            "base_url": f"http://{address}:{info.port}",
            "version": str(props.get("version", "")),
        }
