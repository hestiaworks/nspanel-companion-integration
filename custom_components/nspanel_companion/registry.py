"""Persistent panel registration and layout storage."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import re
import secrets
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION
from .layout import validate_layout

DEVICE_ID = re.compile(r"^[A-Za-z0-9._:-]{4,128}$")
SENSITIVE_DIAGNOSTIC = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:https?|rtsp|wss?)://\S+|(?:token|password|access[_ -]?key|claim)\s*[:=]\s*\S+)"
)


class PanelRegistry:
    """Own panel records for one Home Assistant instance."""

    def __init__(self, hass: HomeAssistant, config_entry_id: str) -> None:
        self._hass = hass
        self._config_entry_id = config_entry_id
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._panels: dict[str, dict[str, Any]] = {}
        self._scrypted_bridges: dict[str, dict[str, Any]] = {}
        self._updater: dict[str, Any] | None = None
        self._settings: dict[str, Any] = {"passive_panel_discovery": False}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self._panels = {item["panel_id"]: item for item in data.get("panels", []) if "panel_id" in item}
        self._scrypted_bridges = {
            item["id"]: item for item in data.get("scrypted_bridges", []) if "id" in item
        }
        updater = data.get("updater")
        self._updater = updater if isinstance(updater, dict) and updater.get("token") else None
        self._settings.update(data.get("settings", {}))

    @property
    def passive_panel_discovery(self) -> bool:
        return bool(self._settings.get("passive_panel_discovery", False))

    async def async_set_passive_panel_discovery(self, enabled: bool) -> None:
        self._settings["passive_panel_discovery"] = bool(enabled)
        await self._save()

    def list_scrypted_bridges(self) -> list[dict[str, Any]]:
        return [self._public_bridge(item) for item in self._scrypted_bridges.values()]

    def updater_public(self) -> dict[str, Any] | None:
        """Return updater metadata without exposing its bearer token."""
        if not self._updater:
            return None
        return {key: value for key, value in self._updater.items() if key != "token"}

    async def async_pair_updater(self, base_url: str, code: str) -> dict[str, Any]:
        base_url = base_url.strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Invalid updater URL")
        if not re.fullmatch(r"\d{6}", code.strip()):
            raise ValueError("Pairing code must contain six digits")
        session = async_get_clientsession(self._hass)
        try:
            async with session.post(
                f"{base_url}/api/pair", json={"code": code.strip()}, timeout=15
            ) as response:
                payload = await response.json()
                if response.status != 200:
                    raise ValueError(payload.get("error", "Updater pairing failed"))
        except ValueError:
            raise
        except Exception as err:
            raise ValueError(f"Unable to reach updater: {err}") from err
        updater_id = str(payload.get("id") or "").strip()
        token = str(payload.get("token") or "").strip()
        if not updater_id or not token:
            raise ValueError("Updater returned an invalid pairing response")
        self._updater = {
            "id": updater_id,
            "name": str(payload.get("name") or "NSPanel Companion Updater")[:64],
            "base_url": base_url,
            "token": token,
            "paired_at": datetime.now(UTC).isoformat(),
        }
        await self._save()
        return self.updater_public() or {}

    async def async_updater_request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._updater:
            raise ValueError("Pair the NSPanel Updater add-on first")
        session = async_get_clientsession(self._hass)
        try:
            async with session.post(
                f"{self._updater['base_url']}{path}",
                headers={"Authorization": f"Bearer {self._updater['token']}"},
                json=payload,
                timeout=330 if path == "/api/update" else 100,
            ) as response:
                result = await response.json()
                if response.status != 200:
                    raise ValueError(result.get("error", "Updater request failed"))
                return result
        except ValueError:
            raise
        except Exception as err:
            raise ValueError(f"Unable to reach updater: {err}") from err

    async def async_unpair_updater(self) -> None:
        if not self._updater:
            return
        try:
            await self.async_updater_request("/api/unpair", {})
        finally:
            self._updater = None
            await self._save()

    async def async_pair_scrypted(self, base_url: str, code: str) -> dict[str, Any]:
        base_url = base_url.strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Invalid Scrypted bridge URL")
        if not re.fullmatch(r"\d{6}", code.strip()):
            raise ValueError("Pairing code must contain six digits")
        session = async_get_clientsession(self._hass)
        try:
            async with session.post(
                f"{base_url}/api/pair", json={"code": code.strip()}, timeout=15
            ) as response:
                payload = await response.json()
                if response.status != 200:
                    raise ValueError(payload.get("error", "Scrypted pairing failed"))
        except ValueError:
            raise
        except Exception as err:
            raise ValueError(f"Unable to reach Scrypted: {err}") from err
        bridge_id = str(payload.get("id") or "").strip()
        token = str(payload.get("token") or "").strip()
        if not bridge_id or not token:
            raise ValueError("Scrypted returned an invalid pairing response")
        record = {
            "id": bridge_id,
            "name": "NSPanel Talkback",
            "base_url": base_url,
            "token": token,
            "paired_at": datetime.now(UTC).isoformat(),
        }
        self._scrypted_bridges[bridge_id] = record
        await self._save()
        return self._public_bridge(record)

    async def async_scrypted_doorbells(self, bridge_id: str) -> list[dict[str, Any]]:
        bridge = self._require_bridge(bridge_id)
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(
                f"{bridge['base_url']}/api/doorbells",
                headers={"Authorization": f"Bearer {bridge['token']}"},
                timeout=20,
            ) as response:
                payload = await response.json()
                if response.status != 200:
                    raise ValueError(payload.get("error", "Unable to load Scrypted doorbells"))
        except ValueError:
            raise
        except Exception as err:
            raise ValueError(f"Unable to reach Scrypted: {err}") from err
        return payload.get("doorbells", [])

    async def async_unpair_scrypted(
        self, bridge_id: str, clear_assignments: bool = False
    ) -> dict[str, Any]:
        """Invalidate a Scrypted bridge credential on both sides."""
        bridge = self._require_bridge(bridge_id)
        session = async_get_clientsession(self._hass)
        try:
            async with session.post(
                f"{bridge['base_url']}/api/unpair",
                headers={"Authorization": f"Bearer {bridge['token']}"},
                timeout=15,
            ) as response:
                payload = await response.json()
                if response.status != 200:
                    raise ValueError(payload.get("error", "Scrypted unpair failed"))
        except ValueError:
            raise
        except Exception as err:
            raise ValueError(f"Unable to reach Scrypted: {err}") from err

        self._scrypted_bridges.pop(bridge_id, None)
        cleared_panels: list[str] = []
        if clear_assignments:
            revision_suffix = int(datetime.now(UTC).timestamp() * 1000)
            for panel_id, record in self._panels.items():
                layout = record.get("layout")
                doorbell = (layout or {}).get("doorbell") or {}
                if doorbell.get("scrypted_bridge_id") != bridge_id:
                    continue
                updated_layout = dict(layout)
                updated_doorbell = dict(doorbell)
                updated_doorbell.update({
                    "enabled": False,
                    "scrypted_bridge_id": "",
                    "scrypted_doorbell_id": "",
                    "stream_base_url": "",
                    "stream_name": "",
                    "talkback_url": "",
                    "talkback_key": "",
                })
                updated_layout["doorbell"] = updated_doorbell
                updated_layout["revision"] = f"scrypted-unpair-{revision_suffix}"
                normalized = validate_layout(updated_layout)
                record["layout"] = normalized
                record["layout_revision"] = normalized["revision"]
                cleared_panels.append(panel_id)
        await self._save()
        return {"unpaired": True, "cleared_panels": cleared_panels}

    async def async_assign_scrypted_doorbell(
        self, panel_id: str, bridge_id: str, doorbell_id: str
    ) -> dict[str, Any]:
        doorbells = await self.async_scrypted_doorbells(bridge_id)
        selected = next((item for item in doorbells if item.get("id") == doorbell_id), None)
        if not selected:
            raise ValueError("Unknown Scrypted doorbell")
        record = self._require(panel_id)
        layout = dict(record.get("layout") or {})
        doorbell = dict(layout.get("doorbell") or {})
        doorbell.update({
            "scrypted_bridge_id": bridge_id,
            "scrypted_doorbell_id": doorbell_id,
            "talkback_url": selected.get("talkback_url", ""),
            "talkback_key": selected.get("talkback_key", ""),
        })
        # Scrypted's standard VideoCamera API may return a short-lived session
        # URL. Preserve an explicitly configured rebroadcast/prebuffer URL;
        # only use the discovered URL when the layout has no media URL yet.
        if not doorbell.get("stream_base_url"):
            doorbell["stream_base_url"] = selected.get("video_url", "")
        layout["doorbell"] = doorbell
        layout["revision"] = f"scrypted-{int(datetime.now(UTC).timestamp() * 1000)}"
        return await self.async_set_layout(panel_id, layout)

    def list_public(self) -> list[dict[str, Any]]:
        return [self._public(item) for item in sorted(self._panels.values(), key=lambda item: item["name"].lower())]

    async def async_register(self, name: str, device_id: str) -> tuple[dict[str, Any], str]:
        panel_id = device_id.strip().lower()
        if not DEVICE_ID.fullmatch(device_id.strip()):
            raise ValueError("Invalid device ID")
        if panel_id in self._panels:
            raise ValueError("Panel is already registered")
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC).isoformat()
        record = {
            "panel_id": panel_id,
            "device_id": device_id.strip(),
            "name": name.strip() or "NSPanel Pro",
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "created_at": now,
            "last_seen": None,
            "layout": None,
            "layout_revision": None,
        }
        self._panels[panel_id] = record
        dr.async_get(self._hass).async_get_or_create(
            config_entry_id=self._config_entry_id,
            identifiers={(DOMAIN, panel_id)},
            manufacturer="Sonoff",
            model="NSPanel Pro",
            name=record["name"],
            configuration_url="homeassistant://nspanel-companion",
        )
        await self._save()
        return self._public(record), token

    async def async_pair(self, name: str, device_id: str) -> tuple[dict[str, Any], str]:
        """Provision a new panel or safely reauthorize its stable identity."""
        normalized_device_id = device_id.strip()
        panel_id = normalized_device_id.lower()
        if not DEVICE_ID.fullmatch(normalized_device_id):
            raise ValueError("Invalid device ID")
        if panel_id not in self._panels:
            return await self.async_register(name, normalized_device_id)

        record = self._panels[panel_id]
        token = secrets.token_urlsafe(32)
        record["token_hash"] = hashlib.sha256(token.encode()).hexdigest()
        record["revoked"] = False
        record["last_seen"] = None
        record["app_version"] = None
        if name.strip():
            record["name"] = name.strip()
        await self._save()
        return self._public(record), token

    def authenticate(self, panel_id: str, token: str) -> bool:
        """Check a panel token without retaining or exposing the plaintext."""
        record = self._panels.get(panel_id)
        if record is None or record.get("revoked", False):
            return False
        supplied = hashlib.sha256(token.encode()).hexdigest()
        return secrets.compare_digest(record["token_hash"], supplied)

    def heartbeat(self, panel_id: str, token: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Authenticate and update lightweight runtime metadata."""
        if not self.authenticate(panel_id, token):
            raise ValueError("Invalid panel credentials")
        record = self._require(panel_id)
        record["last_seen"] = datetime.now(UTC).isoformat()
        record["app_version"] = str(metadata.get("app_version", ""))[:64] or None
        record["reported_layout_revision"] = str(metadata.get("layout_revision", ""))[:64] or None
        report = str(metadata.get("diagnostics", ""))[:16_384]
        record["diagnostics"] = SENSITIVE_DIAGNOSTIC.sub("<redacted>", report) or None
        self._store.async_delay_save(self._storage_data, 60)
        return record

    async def async_rotate_token(self, panel_id: str) -> tuple[dict[str, Any], str]:
        record = self._require(panel_id)
        token = secrets.token_urlsafe(32)
        record["token_hash"] = hashlib.sha256(token.encode()).hexdigest()
        record["revoked"] = False
        await self._save()
        return self._public(record), token

    async def async_rename(self, panel_id: str, name: str) -> dict[str, Any]:
        """Update the human-readable panel name without changing its identity."""
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("Panel name cannot be empty")
        if len(clean_name) > 64:
            raise ValueError("Panel name must be 64 characters or fewer")
        record = self._require(panel_id)
        record["name"] = clean_name
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, panel_id)})
        if device:
            device_registry.async_update_device(device.id, name_by_user=clean_name)
        await self._save()
        return self._public(record)

    async def async_revoke(self, panel_id: str) -> dict[str, Any]:
        record = self._panels.pop(panel_id, None)
        if record is None:
            raise ValueError("Unknown panel")
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, panel_id)})
        if device:
            device_registry.async_remove_device(device.id)
        await self._save()
        return self._public(record)

    async def async_set_layout(self, panel_id: str, layout: dict[str, Any]) -> dict[str, Any]:
        record = self._require(panel_id)
        existing_doorbell = dict((record.get("layout") or {}).get("doorbell") or {})
        layout = await self._hydrate_camera_widgets(layout, existing_doorbell)
        normalized = validate_layout(layout)
        record["layout"] = normalized
        record["layout_revision"] = normalized["revision"]
        await self._save()
        return self._public(record)

    async def _hydrate_camera_widgets(
        self, layout: dict[str, Any], existing_doorbell: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        hydrated = dict(layout)
        doorbell = dict(existing_doorbell or {})
        doorbell.update(layout.get("doorbell") or {})
        pages = [dict(page) for page in layout.get("pages", [])]
        cache: dict[str, list[dict[str, Any]]] = {}
        for page in pages:
            widgets = [dict(widget) for widget in page.get("widgets", [])]
            for widget in widgets:
                if widget.get("type") != "camera":
                    continue
                bridge_id = str(widget.get("scrypted_bridge_id", ""))
                camera_id = str(widget.get("scrypted_camera_id", ""))
                if not bridge_id or not camera_id:
                    raise ValueError("Select a Scrypted camera")
                if bridge_id not in cache:
                    cache[bridge_id] = await self.async_scrypted_doorbells(bridge_id)
                selected = next((item for item in cache[bridge_id] if item.get("id") == camera_id), None)
                if not selected:
                    raise ValueError("Unknown Scrypted camera")
                same_configured_doorbell = (
                    bridge_id == str(doorbell.get("scrypted_bridge_id", ""))
                    and camera_id == str(doorbell.get("scrypted_doorbell_id", ""))
                    and bool(doorbell.get("stream_base_url"))
                )
                widget["stream_base_url"] = (
                    doorbell.get("stream_base_url", "")
                    if same_configured_doorbell else selected.get("video_url", "")
                )
                widget["stream_name"] = (
                    doorbell.get("stream_name", "")
                    if same_configured_doorbell else selected.get("stream_name", "")
                ) or "doorbell_sub"
                widget["talkback_url"] = selected.get("talkback_url", "")
                widget["talkback_key"] = selected.get("talkback_key", "")
            page["widgets"] = widgets
        hydrated["pages"] = pages
        return hydrated

    def layout(self, panel_id: str) -> dict[str, Any] | None:
        return self._require(panel_id).get("layout")

    def _require(self, panel_id: str) -> dict[str, Any]:
        try:
            return self._panels[panel_id]
        except KeyError as err:
            raise ValueError("Unknown panel") from err

    async def _save(self) -> None:
        await self._store.async_save(self._storage_data())

    def _storage_data(self) -> dict[str, Any]:
        return {
            "panels": list(self._panels.values()),
            "scrypted_bridges": list(self._scrypted_bridges.values()),
            "updater": self._updater,
            "settings": self._settings,
        }

    def _require_bridge(self, bridge_id: str) -> dict[str, Any]:
        try:
            return self._scrypted_bridges[bridge_id]
        except KeyError as err:
            raise ValueError("Unknown Scrypted bridge") from err

    @staticmethod
    def _public_bridge(record: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in record.items() if key != "token"}

    @staticmethod
    def _public(record: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in record.items() if key not in {"token_hash", "layout", "diagnostics"}}

    def diagnostics(self, panel_id: str) -> str:
        """Return the latest bounded, panel-supplied sanitized diagnostic report."""
        return str(self._require(panel_id).get("diagnostics") or "No diagnostic report received yet.")
