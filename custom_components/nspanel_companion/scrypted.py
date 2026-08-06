"""Local discovery for the companion Scrypted plugin."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components import zeroconf
from homeassistant.core import HomeAssistant, callback
from zeroconf import ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser

SERVICE_TYPE = "_nspanel-talkback._tcp.local."


@dataclass
class DiscoveredScrypted:
    """One currently advertised Scrypted bridge."""

    instance_id: str
    name: str
    base_url: str
    version: str

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.instance_id,
            "name": self.name,
            "base_url": self.base_url,
            "version": self.version,
        }


class ScryptedDiscovery:
    """Browse the LAN for NSPanel Talkback plugins."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._browser: AsyncServiceBrowser | None = None
        self._aiozc = None
        self._services: dict[str, DiscoveredScrypted] = {}

    async def async_start(self) -> None:
        aiozc = self._aiozc = await zeroconf.async_get_instance(self._hass)
        self._browser = AsyncServiceBrowser(
            aiozc,
            SERVICE_TYPE,
            handlers=[self._service_changed],
        )

    async def async_stop(self) -> None:
        if self._browser:
            await self._browser.async_cancel()
            self._browser = None

    def list_public(self) -> list[dict[str, str]]:
        return [item.as_dict() for item in self._services.values()]

    @callback
    def _service_changed(self, zeroconf, service_type, name, state_change) -> None:
        if state_change is ServiceStateChange.Removed:
            self._services.pop(name, None)
            return
        self._hass.async_create_task(self._async_resolve(service_type, name))

    async def _async_resolve(self, service_type: str, name: str) -> None:
        if not self._aiozc:
            return
        info = await self._aiozc.async_get_service_info(service_type, name, 3000)
        if not info:
            return
        addresses = info.parsed_scoped_addresses()
        if not addresses:
            return
        properties: dict[str, Any] = {
            key.decode(errors="replace"): value.decode(errors="replace")
            for key, value in info.properties.items()
        }
        instance_id = properties.get("id") or name
        self._services[name] = DiscoveredScrypted(
            instance_id=instance_id,
            name=name.removesuffix(f".{SERVICE_TYPE}"),
            base_url=f"http://{addresses[0]}:{info.port}",
            version=properties.get("version", ""),
        )
