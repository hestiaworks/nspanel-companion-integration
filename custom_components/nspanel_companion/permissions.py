"""Panel-scoped entity and service permissions."""

from __future__ import annotations

from typing import Any, Iterable

CONTROL_DOMAINS = {"light", "switch", "input_boolean", "fan", "cover"}
SERVICES = {
    "climate": {"set_temperature", "set_hvac_mode"},
    "light": {"toggle", "turn_on", "turn_off"},
    "switch": {"toggle", "turn_on", "turn_off"},
    "input_boolean": {"toggle", "turn_on", "turn_off"},
    "fan": {"toggle", "turn_on", "turn_off", "set_percentage"},
    "cover": {"open_cover", "close_cover", "stop_cover", "set_cover_position"},
    "script": {"turn_on", "turn_off"},
}


def allowed_entity_ids(layout: dict[str, Any] | None, available: Iterable[str]) -> set[str]:
    """Resolve the bounded entity set visible to one panel layout."""
    if not layout:
        return set()
    available_ids = list(available)
    allowed: set[str] = set()
    for page in layout.get("pages", []):
        for widget in page.get("widgets", []):
            if entity_id := widget.get("entity_id"):
                if entity_id in available_ids:
                    allowed.add(entity_id)
                for script_field in ("gradual_cover_script", "gradual_open_script", "gradual_close_script"):
                    gradual_script = widget.get(script_field)
                    if gradual_script in available_ids:
                        allowed.add(gradual_script)
                continue
            widget_type = widget.get("type")
            if widget_type == "thermostat":
                allowed.update(_first(available_ids, {"climate"}, 1))
            elif widget_type == "weather":
                allowed.update(_first(available_ids, {"weather"}, 1))
            elif widget_type == "controls":
                allowed.update(_first(available_ids, CONTROL_DOMAINS, 4))
    return allowed


def service_allowed(entity_id: str, domain: str, service: str, entities: set[str]) -> bool:
    """Authorize a service against both entity visibility and a strict whitelist."""
    return entity_id in entities and entity_id.partition(".")[0] == domain and service in SERVICES.get(domain, set())


def _first(values: list[str], domains: set[str], limit: int) -> list[str]:
    return [value for value in values if value.partition(".")[0] in domains][:limit]
