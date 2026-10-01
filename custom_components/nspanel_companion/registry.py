"""Persistent panel registration and layout storage."""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
import hashlib
import re
from urllib.parse import urlparse
import secrets
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import DATA_PANEL_SOCKETS, DOMAIN, STORAGE_KEY, STORAGE_VERSION
from .panel_state import (
    SIGNAL_PANEL_ADDED, PanelState, clean_state, signal_for,
)
from .layout import validate_layout, without_example_stream_url

DEVICE_ID = re.compile(r"^[A-Za-z0-9._:-]{4,128}$")
# The add-on discloses its pairing code to this host only, so these are the only
# addresses that can answer. An updater running elsewhere is paired by hand.
LOOPBACK_UPDATER_URLS = ("http://127.0.0.1:8098", "http://localhost:8098")
#: Where a talkback add-on running beside Home Assistant answers. Reaching
#: its pairing code at all is what proves it is the local one.
LOOPBACK_TALKBACK_URLS = ("http://127.0.0.1:8099", "http://localhost:8099")
SENSITIVE_DIAGNOSTIC = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:https?|rtsp|wss?)://\S+|(?:token|password|access[_ -]?key|claim)\s*[:=]\s*\S+)"
)


def behind_release(panels: list[dict[str, Any]], version: str) -> list[dict[str, Any]]:
    """The panels not running the published version.

    "Not the same" rather than "older", on purpose. What Home Assistant has
    is the version name a panel reported, and names do not sort — 1.2.2-rc.10
    comes before 1.2.2-rc.9 as text. Deciding what is newer belongs to the
    installer, which reads the version code off the panel over ADB and
    refuses a downgrade. This answers the smaller question a badge asks: who
    is not on what has been published.

    A panel that has never reported a version is left out. It is paired and
    unheard from, and saying it needs an update would be a guess.
    """
    if not version:
        return []
    return [
        panel for panel in panels
        if panel.get("app_version") and str(panel["app_version"]) != version
    ]


def panel_talk_base_url(base_url: str, source: str, ha_url: str) -> str:
    """Where a *panel* can reach the talkback add-on.

    Autopairing happens over loopback, because answering there is what
    proves an add-on is the local one. But 127.0.0.1 is Home Assistant's
    route to it, not a panel's — on a panel that address means the panel
    itself, and the audio would go nowhere at all.

    The add-on shares the host's network, so it is reachable wherever Home
    Assistant is, on the port it was paired on. An add-on paired by hand at
    a real address is already reachable and is left alone.

    Always http: the add-on serves plain HTTP even where Home Assistant is
    behind TLS.
    """
    if source != "local":
        return base_url
    port = urlparse(base_url).port or 8099
    host = urlparse(ha_url).hostname
    return f"http://{host}:{port}" if host else base_url


class PanelRegistry:
    """Own panel records for one Home Assistant instance."""

    #: How much of a panel's recent history is kept. It rides along with
    #: every panel list, and a panel that flaps would otherwise grow a log
    #: without limit that nobody reads past the first few lines.
    MAX_EVENTS = 8

    def __init__(self, hass: HomeAssistant, config_entry_id: str) -> None:
        self._hass = hass
        self._config_entry_id = config_entry_id
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._panels: dict[str, dict[str, Any]] = {}
        self._scrypted_bridges: dict[str, dict[str, Any]] = {}
        self._updater: dict[str, Any] | None = None
        #: The talkback add-on, which carries panel microphone audio to a
        #: doorbell over the camera's own protocol. Optional: without it the
        #: panel keeps talking through Scrypted, slower but working.
        self._talkback: dict[str, Any] | None = None
        #: What the updater add-on last said is published, and when. Held in
        #: memory rather than stored: it is a cache of somebody else's fact,
        #: and a restart is the right moment to ask again.
        self._release: dict[str, Any] = {"latest": None, "checked_at": None, "error": ""}
        #: When a look was last attempted, successful or not, so a paired
        #: updater that has never answered can be asked again without the
        #: admin page turning into a retry loop against a stopped add-on.
        self._release_attempt = 0.0
        self._settings: dict[str, Any] = {"passive_panel_discovery": False}
        #: The last wifi reading each panel reported, in memory only. It is a
        #: live fact about a radio link, so a value that outlived a restart
        #: would be worse than none — and writing it to storage every half
        #: minute would churn the disk for nothing.
        self._links: dict[str, dict[str, Any]] = {}
        #: The last full report from each panel, in memory for the same
        #: reason the link reading is: these are live facts about a radio
        #: and a room, and one that outlived a restart would be worse than
        #: none at all.
        self._states: dict[str, PanelState] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self._panels = {item["panel_id"]: item for item in data.get("panels", []) if "panel_id" in item}
        self._scrypted_bridges = {
            item["id"]: item for item in data.get("scrypted_bridges", []) if "id" in item
        }
        updater = data.get("updater")
        self._updater = updater if isinstance(updater, dict) and updater.get("token") else None
        talkback = data.get("talkback")
        self._talkback = talkback if isinstance(talkback, dict) and talkback.get("token") else None
        self._settings.update(data.get("settings", {}))
        if self._drop_example_stream_urls():
            await self._save()

    def _drop_example_stream_urls(self) -> bool:
        """Clear the Media URL example out of the layouts already stored.

        The field shipped its example as the input's value, so it was saved
        as though someone had typed it. It is a documentation address that
        can never answer, and while it is there the code that fills in the
        real Scrypted URL — which only writes into an empty field — leaves
        it alone. Panels are given the stored layout directly, so it has to
        go from the data rather than only from the next save.
        """
        changed = False
        for record in self._panels.values():
            layout = record.get("layout") or {}
            blocks = [layout.get("doorbell") or {}]
            blocks += [
                widget for page in layout.get("pages") or []
                for widget in page.get("widgets") or []
                if widget.get("type") == "camera"
            ]
            for block in blocks:
                if not without_example_stream_url(str(block.get("stream_base_url", ""))):
                    if block.get("stream_base_url"):
                        block["stream_base_url"] = ""
                        changed = True
        return changed

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

    async def async_pair_updater(
        self, base_url: str, code: str, source: str = "manual"
    ) -> dict[str, Any]:
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
            # Recorded so the UI can tell an add-on it can re-pair by itself from
            # one a person entered by hand and would have to re-enter.
            "source": "local" if source == "local" else "manual",
            "paired_at": datetime.now(UTC).isoformat(),
        }
        await self._save()
        return self.updater_public() or {}

    async def async_autopair_updater(self) -> dict[str, Any]:
        """Pair with an updater add-on running alongside Home Assistant.

        The code is readable only from this host, so reaching it at all is what
        establishes that the add-on is the local one.
        """
        session = async_get_clientsession(self._hass)
        for base_url in LOOPBACK_UPDATER_URLS:
            try:
                async with session.get(f"{base_url}/api/pair-code", timeout=10) as response:
                    if response.status != 200:
                        continue
                    payload = await response.json()
            except Exception:  # noqa: BLE001 - any failure means try the next address
                continue
            code = str(payload.get("code") or "").strip()
            if code:
                return await self.async_pair_updater(base_url, code, source="local")
        raise ValueError(
            "The updater add-on could not be reached on this host. If it runs "
            "elsewhere, pair it manually with its address and pairing code."
        )

    def talkback_public(self) -> dict[str, Any] | None:
        """Talkback add-on metadata, without its bearer token."""
        if not self._talkback:
            return None
        return {key: value for key, value in self._talkback.items() if key != "token"}

    async def async_pair_talkback(
        self, base_url: str, code: str, source: str = "manual"
    ) -> dict[str, Any]:
        base_url = base_url.strip().rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Invalid talkback URL")
        if not re.fullmatch(r"\d{6}", code.strip()):
            raise ValueError("Pairing code must contain six digits")
        session = async_get_clientsession(self._hass)
        try:
            async with session.post(
                f"{base_url}/api/pair", json={"code": code.strip()}, timeout=15
            ) as response:
                payload = await response.json()
                if response.status != 200:
                    raise ValueError(payload.get("error", "Talkback pairing failed"))
        except ValueError:
            raise
        except Exception as err:  # noqa: BLE001 - surfaced to the admin page
            raise ValueError(f"Unable to reach talkback add-on: {err}") from err
        talkback_id = str(payload.get("id") or "").strip()
        token = str(payload.get("token") or "").strip()
        if not talkback_id or not token:
            raise ValueError("Talkback add-on returned an invalid pairing response")
        self._talkback = {
            "id": talkback_id,
            "name": str(payload.get("name") or "NSPanel Companion Talkback")[:64],
            "base_url": base_url,
            "token": token,
            "source": "local" if source == "local" else "manual",
            "paired_at": datetime.now(UTC).isoformat(),
        }
        await self._save()
        return self.talkback_public() or {}

    async def async_talkback_is_live(self) -> bool:
        """Whether the add-on still recognises the pairing we hold.

        An add-on keeps its own copy of the token in /data, so reinstalling
        it — from a local folder to the repository, say — issues a new
        identity and forgets ours. Home Assistant goes on believing it is
        paired, panels go on presenting a credential nothing recognises, and
        talkback fails with a 401 nobody sees.
        """
        if not self._talkback:
            return False
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(f"{self._talkback['base_url']}/api/info", timeout=10) as response:
                if response.status != 200:
                    return True          # reachable but unhappy: not our call
                payload = await response.json()
        except Exception:  # noqa: BLE001 - a stopped add-on is not a stale pairing
            return True
        return (
            bool(payload.get("paired"))
            and str(payload.get("id") or "") == str(self._talkback.get("id") or "")
        )

    async def async_talkback_health(self) -> dict[str, Any]:
        """Whether the add-on is reachable, ours, and able to reach the camera.

        "Paired" alone was a poor signal: the card said connected all evening
        while the add-on had been reinstalled and forgotten us. Three
        separate questions, answered separately, because each fails on its
        own and each needs a different fix.
        """
        health: dict[str, Any] = {
            "reachable": False, "recognises_us": False, "camera": False, "detail": "",
        }
        if not self._talkback:
            health["detail"] = "No talkback add-on is paired."
            return health
        session = async_get_clientsession(self._hass)
        base = self._talkback["base_url"]
        try:
            async with session.get(f"{base}/api/info", timeout=10) as response:
                info = await response.json()
            health["reachable"] = True
        except Exception as err:  # noqa: BLE001 - shown to a person, not raised
            health["detail"] = f"The add-on did not answer: {err}"
            return health
        health["recognises_us"] = (
            bool(info.get("paired"))
            and str(info.get("id") or "") == str(self._talkback.get("id") or "")
        )
        if not health["recognises_us"]:
            health["detail"] = (
                "The add-on has been reinstalled and no longer recognises this "
                "pairing. Publishing a panel's layout will pair again."
            )
            return health
        try:
            async with session.get(
                f"{base}/api/ability",
                headers={"Authorization": f"Bearer {self._talkback['token']}"},
                timeout=25,
            ) as response:
                ability = await response.json()
            health["camera"] = response.status == 200 and bool(ability.get("audio_type"))
            if not health["camera"]:
                health["detail"] = str(ability.get("error") or "The camera did not answer.")
        except Exception as err:  # noqa: BLE001
            health["detail"] = f"The add-on could not reach the camera: {err}"
        return health

    async def async_talkback_test_tone(self) -> dict[str, Any]:
        """Play a tone at the door, so "does it work" is one click.

        Synthetic, and with no microphone involved, so silence points at the
        path rather than at capture, gain, or a quiet room.
        """
        if not self._talkback:
            raise ValueError("No talkback add-on is paired")
        session = async_get_clientsession(self._hass)
        try:
            async with session.post(
                f"{self._talkback['base_url']}/api/test-tone",
                headers={"Authorization": f"Bearer {self._talkback['token']}"},
                timeout=60,
            ) as response:
                payload = await response.json()
                if response.status != 200:
                    raise ValueError(payload.get("error", "The add-on refused the test"))
                return payload
        except ValueError:
            raise
        except Exception as err:  # noqa: BLE001
            raise ValueError(f"Unable to reach the talkback add-on: {err}") from err

    async def async_autopair_talkback(self) -> dict[str, Any]:
        """Pair with a talkback add-on running alongside Home Assistant.

        Safe to call when already paired: it re-pairs only when the add-on
        no longer recognises what we hold.
        """
        if self._talkback and await self.async_talkback_is_live():
            return self.talkback_public() or {}
        session = async_get_clientsession(self._hass)
        for base_url in LOOPBACK_TALKBACK_URLS:
            try:
                async with session.get(f"{base_url}/api/pair-code", timeout=10) as response:
                    if response.status != 200:
                        continue
                    payload = await response.json()
            except Exception:  # noqa: BLE001 - any failure means try the next address
                continue
            code = str(payload.get("code") or "").strip()
            if code:
                return await self.async_pair_talkback(base_url, code, source="local")
        raise ValueError(
            "The talkback add-on could not be reached on this host. If it runs "
            "elsewhere, pair it manually with its address and pairing code."
        )

    async def async_unpair_talkback(self) -> None:
        """Forget the add-on. Panels fall back to talking through Scrypted."""
        self._talkback = None
        await self._save()

    def _talk_endpoint(self) -> "tuple[str, str]":
        """The URL and key a panel should post microphone audio to.

        Empty when no add-on is paired, which is what makes the panel fall
        back to the Scrypted path rather than losing talkback altogether.
        """
        if not self._talkback:
            return "", ""
        from homeassistant.helpers.network import get_url

        ha_url = get_url(self._hass, allow_internal=True, prefer_external=False)
        base = panel_talk_base_url(
            str(self._talkback["base_url"]), str(self._talkback.get("source", "")), ha_url,
        )
        return f"{base}/api/talk", str(self._talkback["token"])

    def release_public(self) -> dict[str, Any]:
        """The published release as last reported, and who is not on it."""
        latest = self._release.get("latest") or {}
        return {
            **self._release,
            "behind": [
                {"panel_id": panel["panel_id"], "name": panel.get("name")}
                for panel in behind_release(self.list_public(), str(latest.get("version", "")))
            ],
        }

    def release_check_is_overdue(self, retry_after: float = 300.0) -> bool:
        """Whether asking again is worth it right now.

        Only when nothing has ever been learned: an add-on that was stopped,
        or one updated since Home Assistant started, leaves the check with
        no answer and six hours before the next timer. Opening the page is a
        reasonable moment to try again — but not every fifteen seconds while
        it sits open, which is how often the page asks for its status.
        """
        return (
            self._updater is not None
            and not self._release.get("latest")
            and time.monotonic() - self._release_attempt > retry_after
        )

    async def async_check_release(self) -> dict[str, Any]:
        """Ask the updater add-on what is published.

        Never raises. This runs on a timer, and a house with no internet, a
        paused add-on or a rate-limited GitHub must not turn into an error
        someone has to dismiss — the last answer stands and the reason sits
        beside it.
        """
        if not self._updater:
            return self._release
        self._release_attempt = time.monotonic()
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(
                f"{self._updater['base_url']}/api/latest",
                headers={"Authorization": f"Bearer {self._updater['token']}"},
                timeout=60,
            ) as response:
                result = await response.json()
                if response.status != 200:
                    raise ValueError(result.get("error", "Update check failed"))
        except Exception as err:  # noqa: BLE001 - a check is never fatal
            self._release = {**self._release, "error": str(err)}
            return self._release
        if result.get("latest"):
            self._release = {
                "latest": result["latest"],
                "checked_at": result.get("checked_at"),
                "error": result.get("error", ""),
            }
        else:
            self._release = {**self._release, "error": result.get("error", "")}
        return self._release

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

    async def async_scrypted_doorbells(
        self, bridge_id: str, *, include_video: bool = True
    ) -> list[dict[str, Any]]:
        """The cameras a bridge offers.

        Asking for the stream URLs is not free: Scrypted mints a session per
        camera per request, and the session outlives the request whether or
        not anything plays it. A caller that only needs names — the camera
        picker — passes include_video=False and costs nothing. An older
        bridge ignores the parameter and answers as it always did.
        """
        bridge = self._require_bridge(bridge_id)
        session = async_get_clientsession(self._hass)
        try:
            async with session.get(
                f"{bridge['base_url']}/api/doorbells" + ("" if include_video else "?video=0"),
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
        # Revoking on the Scrypted side is best effort. Refusing to unpair
        # locally when Scrypted cannot be reached leaves a bridge at a stale
        # address that can never be removed, which is worse than a credential
        # the user can also clear by removing the plugin.
        warning = ""
        try:
            async with session.post(
                f"{bridge['base_url']}/api/unpair",
                headers={"Authorization": f"Bearer {bridge['token']}"},
                timeout=15,
            ) as response:
                payload = await response.json()
                if response.status != 200:
                    warning = str(payload.get("error") or "Scrypted refused the unpair request")
        except Exception as err:  # noqa: BLE001 - the local record is removed regardless
            warning = f"Scrypted could not be reached ({err})"
        if warning:
            warning = (
                f"{warning}. The bridge was removed here, but its access key may still "
                "exist in Scrypted until the plugin is unpaired or removed there."
            )

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
        return {"unpaired": True, "cleared_panels": cleared_panels, "warning": warning}

    def list_public(self) -> list[dict[str, Any]]:
        return [
            {**self._public(item), "link": self._links.get(item["panel_id"])}
            for item in sorted(self._panels.values(), key=lambda item: item["name"].lower())
        ]

    def record_state(self, panel_id: str, raw: dict[str, Any]) -> None:
        """Note what a panel says about itself, and wake its entities."""
        if panel_id not in self._panels:
            return
        state = clean_state(raw)
        self._states[panel_id] = state
        if state.app_version:
            self._note_app_version(panel_id, state.app_version)
        async_dispatcher_send(self._hass, signal_for(panel_id), state)

    def panel_state(self, panel_id: str) -> PanelState:
        """The last report, or an empty one from a panel that has said nothing."""
        return self._states.get(panel_id, PanelState())

    def _note_app_version(self, panel_id: str, version: str) -> None:
        """Keep the device's sw_version current.

        A panel left on an old build was previously invisible without ADB.
        """
        registry = dr.async_get(self._hass)
        device = registry.async_get_device(identifiers={(DOMAIN, panel_id)})
        if device is not None and device.sw_version != version:
            registry.async_update_device(device.id, sw_version=version)

    def record_link(self, panel_id: str, reading: dict[str, Any]) -> None:
        """Note what a panel says about its wifi.

        Worth showing because a weak link does not present as a weak link: it
        presents as video that takes sixteen seconds, talkback that arrives
        four seconds late, and timeouts against a service that is plainly up.
        One panel at -79 beside two at -40 is the whole diagnosis, and it is
        invisible unless something reports it.
        """
        if panel_id not in self._panels:
            return
        rssi = reading.get("rssi")
        self._links[panel_id] = {
            # Below -100 or above 0 is not a reading, it is a driver saying
            # it does not know.
            "rssi": int(rssi) if isinstance(rssi, (int, float)) and -100 <= rssi <= 0 else None,
            "bssid": str(reading.get("bssid") or "")[:32],
            "ssid": str(reading.get("ssid") or "")[:64],
            "link_speed_mbps": int(reading.get("link_speed_mbps") or 0),
            "frequency_mhz": int(reading.get("frequency_mhz") or 0),
            "at": datetime.now(UTC).isoformat(),
        }

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
        # Entity platforms build from the panel list at setup, so a panel
        # paired afterwards would have no entities until the next restart.
        async_dispatcher_send(self._hass, SIGNAL_PANEL_ADDED, panel_id)
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
        # What the panel's light sensor reads, so the thresholds that decide
        # bright from dark can be chosen by looking at the number rather than
        # by guessing at units the sensor does not document.
        ambient = metadata.get("ambient_light")
        record["ambient_light"] = (
            round(float(ambient), 1) if isinstance(ambient, (int, float)) else None
        )
        reported = str(metadata.get("layout_revision", ""))[:64] or None
        if reported and reported != record.get("reported_layout_revision"):
            self.record_event(panel_id, f"Layout revision {reported} acknowledged")
        record["reported_layout_revision"] = reported
        report = str(metadata.get("diagnostics", ""))[:16_384]
        record["diagnostics"] = SENSITIVE_DIAGNOSTIC.sub("<redacted>", report) or None
        self._store.async_delay_save(self._storage_data, 60)
        return record

    async def async_rotate_token(self, panel_id: str) -> tuple[dict[str, Any], str]:
        record = self._require(panel_id)
        token = secrets.token_urlsafe(32)
        record["token_hash"] = hashlib.sha256(token.encode()).hexdigest()
        record["revoked"] = False
        self.record_event(panel_id, "Panel token rotated", "warn")
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
        await self._async_tell_panel_it_was_revoked(panel_id)
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, panel_id)})
        if device:
            device_registry.async_remove_device(device.id)
        await self._save()
        return self._public(record)

    async def _async_tell_panel_it_was_revoked(self, panel_id: str) -> None:
        """Tell a panel it has been unpaired, while it is still listening.

        Unpairing was one-sided: Home Assistant forgot the panel and the
        panel carried on showing a dashboard it was no longer entitled to,
        until something made it reconnect and be refused. A panel holding a
        socket can be told now, and it clears its credentials and offers
        itself for pairing again.

        Best effort by nature — a panel that is not connected finds out the
        old way, on its next attempt.
        """
        sockets = self._hass.data.get(DOMAIN, {}).get(DATA_PANEL_SOCKETS, {})
        socket = sockets.pop(panel_id, None)
        if socket is None or socket.closed:
            return
        with suppress(Exception):
            await socket.send_json({"type": "revoked"})
            await socket.close()

    async def async_ensure_talkback(self) -> None:
        """Re-pair before handing a panel a credential, if ours is dead.

        Relying on the admin page to notice meant a stale pairing survived
        for as long as nobody loaded that page with a fresh browser cache,
        and the panel went on presenting a token nothing recognised. The
        moment a layout is published is the moment the credential matters,
        so it is checked here instead.
        """
        if not self._talkback:
            return
        if await self.async_talkback_is_live():
            return
        with suppress(ValueError):
            await self.async_autopair_talkback()

    async def async_set_layout(self, panel_id: str, layout: dict[str, Any]) -> dict[str, Any]:
        await self.async_ensure_talkback()
        record = self._require(panel_id)
        existing_doorbell = dict((record.get("layout") or {}).get("doorbell") or {})
        layout = await self._hydrate_camera_widgets(layout, existing_doorbell)
        normalized = validate_layout(layout)
        record["layout"] = normalized
        self.record_event(panel_id, f"Layout revision {normalized.get('revision', '?')} published")
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

        async def device(bridge_id: str, device_id: str) -> dict[str, Any]:
            """One camera as the bridge describes it, asked for once.

            Without the stream URL: resolving one mints a session per camera
            and nothing stored here uses it. What is wanted are the talkback
            credentials, which do not expire.
            """
            if bridge_id not in cache:
                cache[bridge_id] = await self.async_scrypted_doorbells(bridge_id, include_video=False)
            found = next((item for item in cache[bridge_id] if item.get("id") == device_id), None)
            if not found:
                raise ValueError("Unknown Scrypted camera")
            return found

        # A doorbell that names a Scrypted device takes its credentials from
        # that device — one rule, applied where the layout is written, rather
        # than a second command that overwrote the layout just published.
        doorbell_bridge = str(doorbell.get("scrypted_bridge_id", ""))
        doorbell_device = str(doorbell.get("scrypted_doorbell_id", ""))
        # Where the microphone goes, if a talkback add-on is paired. Written
        # everywhere a camera is configured, so nobody copies a URL or a key
        # by hand — and left empty when none is paired, which is what makes a
        # panel fall back to talking through Scrypted rather than not at all.
        talk_url, talk_key = self._talk_endpoint()
        if doorbell_bridge and doorbell_device:
            selected = await device(doorbell_bridge, doorbell_device)
            doorbell["talkback_url"] = selected.get("talkback_url", "")
            doorbell["talkback_key"] = selected.get("talkback_key", "")
            doorbell["talk_url"] = talk_url
            doorbell["talk_key"] = talk_key
            hydrated["doorbell"] = doorbell
        for page in pages:
            widgets = [dict(widget) for widget in page.get("widgets", [])]
            for widget in widgets:
                if widget.get("type") != "camera":
                    continue
                bridge_id = str(widget.get("scrypted_bridge_id", ""))
                camera_id = str(widget.get("scrypted_camera_id", ""))
                if not bridge_id or not camera_id:
                    raise ValueError("Select a Scrypted camera")
                selected = await device(bridge_id, camera_id)
                same_configured_doorbell = (
                    bridge_id == str(doorbell.get("scrypted_bridge_id", ""))
                    and camera_id == str(doorbell.get("scrypted_doorbell_id", ""))
                    and bool(doorbell.get("stream_base_url"))
                )
                # Only a stable URL is worth storing. Scrypted's own is
                # session scoped — its plugin says the port dies with the
                # session — so keeping one leaves the panel a fallback that
                # is dead within minutes, and it spends the player's connect
                # timeout finding that out. With nothing here it resolves
                # live, which is what it does first in any case.
                widget["stream_base_url"] = (
                    doorbell.get("stream_base_url", "") if same_configured_doorbell else ""
                )
                widget["stream_name"] = (
                    doorbell.get("stream_name", "")
                    if same_configured_doorbell else selected.get("stream_name", "")
                ) or "doorbell_sub"
                widget["talkback_url"] = selected.get("talkback_url", "")
                widget["talkback_key"] = selected.get("talkback_key", "")
                widget["talk_url"] = talk_url
                widget["talk_key"] = talk_key
                # The microphone gain is a property of the panel, not of one
                # camera, so every camera page gets the doorbell's. Without
                # it the setting applied to a ring and was silently 100 on
                # the same camera opened from the dashboard.
                widget["talkback_gain"] = int(doorbell.get("talkback_gain", 100) or 100)
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
            "talkback": self._talkback,
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
        """A panel record as the admin UI may see it.

        The layout is withheld — it is large, and the list carries every
        panel — but two facts about it are summarised, because withholding it
        entirely left the UI unable to say whether a panel was configured and
        every panel read as unconfigured however many pages it had.
        """
        public = {key: value for key, value in record.items() if key not in {"token_hash", "layout", "diagnostics"}}
        layout = record.get("layout") or {}
        public.setdefault("layout_revision", layout.get("revision"))
        public["page_count"] = len(layout.get("pages") or [])
        public["events"] = record.get("events") or []
        return public

    def record_event(self, panel_id: str, message: str, level: str = "info") -> None:
        """Note something that happened to a panel, newest first.

        A panel that is gone is not an error: sockets close after a panel is
        removed, and that is not worth raising into a request that is already
        finishing.
        """
        record = self._panels.get(panel_id)
        if not record:
            return
        events = [
            {"at": datetime.now(UTC).isoformat(), "message": str(message)[:160], "level": level},
            *record.get("events", []),
        ]
        record["events"] = events[: self.MAX_EVENTS]

    def diagnostics(self, panel_id: str) -> str:
        """Return the latest bounded, panel-supplied sanitized diagnostic report."""
        return str(self._require(panel_id).get("diagnostics") or "No diagnostic report received yet.")
