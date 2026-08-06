"""Validation for the Android dashboard layout contract."""

from __future__ import annotations

import re
from typing import Any

SUPPORTED_WIDGETS = {"thermostat", "weather", "controls", "entity_button", "sensor"}
PAGE_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
ENTITY_ID = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
STREAM_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_layout(value: Any) -> dict[str, Any]:
    """Return a normalized layout or raise ValueError."""
    if not isinstance(value, dict):
        raise ValueError("Layout must be an object")
    if value.get("schema_version") != 1:
        raise ValueError("Unsupported layout schema")
    revision = str(value.get("revision", "")).strip()
    if not revision or len(revision) > 64:
        raise ValueError("Invalid layout revision")
    pages = value.get("pages")
    if not isinstance(pages, list) or not 1 <= len(pages) <= 8:
        raise ValueError("Layout must contain 1–8 pages")
    ids: list[str] = []
    for page in pages:
        if not isinstance(page, dict) or not PAGE_ID.fullmatch(str(page.get("id", ""))):
            raise ValueError("Invalid page ID")
        page_id = str(page["id"])
        ids.append(page_id)
        widgets = page.get("widgets", [])
        if not isinstance(widgets, list) or len(widgets) > 12:
            raise ValueError("A page may contain at most 12 widgets")
        for widget in widgets:
            if not isinstance(widget, dict) or widget.get("type") not in SUPPORTED_WIDGETS:
                raise ValueError("Unsupported widget")
            entity_id = widget.get("entity_id")
            if entity_id is not None and not ENTITY_ID.fullmatch(str(entity_id)):
                raise ValueError("Invalid entity ID")
            if widget.get("type") == "weather":
                forecast_days = int(widget.get("forecast_days", 5))
                if forecast_days not in {1, 3, 5}:
                    raise ValueError("Weather forecast must show 1, 3, or 5 days")
    if len(set(ids)) != len(ids):
        raise ValueError("Page IDs must be unique")
    default_page = str(value.get("default_page_id") or ids[0])
    if default_page not in ids:
        raise ValueError("Default page does not exist")
    return_seconds = int(value.get("default_page_return_seconds", 60))
    cache_minutes = int(value.get("weather_cache_max_age_minutes", 360))
    if not 0 <= return_seconds <= 3600:
        raise ValueError("Invalid default-page return timeout")
    if not 0 <= cache_minutes <= 10080:
        raise ValueError("Invalid weather cache age")
    normalized = dict(value)
    doorbell = value.get("doorbell")
    if doorbell is not None:
        if not isinstance(doorbell, dict):
            raise ValueError("Doorbell configuration must be an object")
        trigger_entity_id = str(doorbell.get("trigger_entity_id", "")).strip()
        stream_base_url = str(doorbell.get("stream_base_url", "")).strip().rstrip("/")
        stream_name = str(doorbell.get("stream_name", "")).strip()
        talkback_url = str(doorbell.get("talkback_url", "")).strip().rstrip("/")
        talkback_key = str(doorbell.get("talkback_key", "")).strip()
        scrypted_bridge_id = str(doorbell.get("scrypted_bridge_id", "")).strip()
        scrypted_doorbell_id = str(doorbell.get("scrypted_doorbell_id", "")).strip()
        if trigger_entity_id and not ENTITY_ID.fullmatch(trigger_entity_id):
            raise ValueError("Invalid doorbell trigger entity")
        if stream_base_url and not stream_base_url.startswith(("http://", "https://", "rtsp://")):
            raise ValueError("Doorbell stream URL must use HTTP, HTTPS, or RTSP")
        if stream_name and not STREAM_NAME.fullmatch(stream_name):
            raise ValueError("Invalid doorbell stream name")
        if talkback_url and not talkback_url.startswith(("http://", "https://")):
            raise ValueError("Doorbell talkback URL must use HTTP or HTTPS")
        if talkback_key and len(talkback_key) < 16:
            raise ValueError("Doorbell talkback key must contain at least 16 characters")
        auto_close_ms = int(doorbell.get("auto_close_ms", 60000))
        if not 10000 <= auto_close_ms <= 300000:
            raise ValueError("Doorbell timeout must be 10–300 seconds")
        normalized["doorbell"] = {
            "enabled": bool(doorbell.get("enabled", True)),
            "trigger_entity_id": trigger_entity_id,
            "stream_base_url": stream_base_url,
            "stream_name": stream_name,
            "talkback_url": talkback_url,
            "talkback_key": talkback_key,
            "scrypted_bridge_id": scrypted_bridge_id,
            "scrypted_doorbell_id": scrypted_doorbell_id,
            "quiet_mode": bool(doorbell.get("quiet_mode", False)),
            "auto_close_ms": auto_close_ms,
        }
    normalized["default_page_id"] = default_page
    normalized["default_page_return_seconds"] = return_seconds
    normalized["weather_cache_max_age_minutes"] = cache_minutes
    normalized["keep_screen_on"] = bool(value.get("keep_screen_on", False))
    theme_mode = str(value.get("theme_mode", "light"))
    if theme_mode not in {"light", "dark", "inherit"}:
        raise ValueError("Invalid panel theme")
    normalized["theme_mode"] = theme_mode
    normalized["theme_dark"] = bool(value.get("theme_dark", False))
    return normalized
