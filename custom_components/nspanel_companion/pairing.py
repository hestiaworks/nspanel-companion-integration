"""Short-code panel pairing lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import secrets
import time
from typing import Callable
import re

from .const import PAIRING_TTL_SECONDS

PANEL_ID = re.compile(r"^panel-[0-9a-f]{32}$")


@dataclass
class PendingPairing:
    request_id: str
    device_id: str
    name: str
    code: str
    claim_hash: str
    created_at: float
    expires_at: float
    approved_token: str | None = None


class PairingManager:
    """Keep short-lived pairing requests in memory only."""

    def __init__(self, now: Callable[[], float] = time.time) -> None:
        self._now = now
        self._pending: dict[str, PendingPairing] = {}

    def start(self, device_id: str, name: str) -> tuple[dict, str]:
        self.prune()
        if not PANEL_ID.fullmatch(device_id):
            raise ValueError("Invalid panel device ID")
        # A restarted unpaired panel replaces its own stale request. This keeps
        # discovery unambiguous while issuing a fresh private claim secret.
        for existing_id in [
            key for key, item in self._pending.items() if item.device_id == device_id
        ]:
            self._pending.pop(existing_id, None)
        if len(self._pending) >= 20:
            raise ValueError("Too many pending pairing requests")
        request_id = secrets.token_urlsafe(18)
        claim = secrets.token_urlsafe(32)
        created = self._now()
        item = PendingPairing(
            request_id=request_id,
            device_id=device_id,
            name=name.strip()[:64] or "NSPanel Pro",
            code=f"{secrets.randbelow(1_000_000):06d}",
            claim_hash=self._hash(claim),
            created_at=created,
            expires_at=created + PAIRING_TTL_SECONDS,
        )
        self._pending[request_id] = item
        return self._panel_public(item), claim

    def list_public(self) -> list[dict]:
        self.prune()
        return [self._admin_public(item) for item in self._pending.values()]

    def get(self, request_id: str) -> PendingPairing:
        self.prune()
        try:
            return self._pending[request_id]
        except KeyError as err:
            raise ValueError("Pairing request expired or unknown") from err

    def find_device_public(self, device_id: str) -> dict | None:
        self.prune()
        item = next((item for item in self._pending.values() if item.device_id == device_id), None)
        return self._admin_public(item) if item else None

    def validate_code(self, request_id: str, code: str) -> PendingPairing:
        """Validate the code displayed only on the physical panel."""
        item = self.get(request_id)
        supplied = str(code).strip()
        if len(supplied) != 6 or not secrets.compare_digest(item.code, supplied):
            raise ValueError("Incorrect pairing code")
        return item

    def approve(self, request_id: str, code: str, token: str) -> dict:
        """Approve only after the administrator supplies the panel code."""
        item = self.validate_code(request_id, code)
        item.approved_token = token
        return self._admin_public(item)

    def claim(self, request_id: str, claim: str) -> dict:
        item = self.get(request_id)
        if not secrets.compare_digest(item.claim_hash, self._hash(claim)):
            raise ValueError("Invalid pairing claim")
        if item.approved_token is None:
            return {"status": "pending", "expires_in": max(0, int(item.expires_at - self._now()))}
        self._pending.pop(request_id, None)
        return {
            "status": "approved",
            "panel_id": item.device_id,
            "token": item.approved_token,
        }

    def prune(self) -> None:
        now = self._now()
        for request_id in [key for key, item in self._pending.items() if item.expires_at <= now]:
            self._pending.pop(request_id, None)

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def _common_public(self, item: PendingPairing) -> dict:
        return {
            "request_id": item.request_id,
            "device_id": item.device_id,
            "name": item.name,
            "created_at": item.created_at,
            "expires_in": max(0, int(item.expires_at - self._now())),
            "status": "approved" if item.approved_token else "pending",
        }

    def _panel_public(self, item: PendingPairing) -> dict:
        return {**self._common_public(item), "code": item.code}

    def _admin_public(self, item: PendingPairing) -> dict:
        return self._common_public(item)
