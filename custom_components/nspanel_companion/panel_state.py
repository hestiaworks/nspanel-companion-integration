"""What a panel reports about itself.

Pure, and free of Home Assistant imports, so the cleaning rules can be
tested without a running instance — and so an entity never has to wonder
whether a value it was handed is plausible.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelState:
    """Every field optional: a panel reports what it has."""

    rssi: int | None = None
    ambient_light: int | None = None
    approach: bool | None = None
    screen_on: bool | None = None
    brightness: int | None = None
    page_id: str = ""
    app_version: str = ""


def _bounded_int(value, low: int, high: int) -> int | None:
    """An integer inside its range, or nothing at all.

    Clamping a signal strength would invent a reading; this returns None so
    an entity goes unavailable rather than lying.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    number = int(value)
    return number if low <= number <= high else None


def _flag(value) -> bool | None:
    return value if isinstance(value, bool) else None


def clean_state(raw: dict) -> PanelState:
    """One report, with everything implausible dropped."""
    brightness = raw.get("brightness")
    return PanelState(
        # Outside -100..0 is a driver saying it does not know.
        rssi=_bounded_int(raw.get("rssi"), -100, 0),
        # Not lux. These panels report a vendor scale, so it is bounded
        # generously and published without a unit.
        ambient_light=_bounded_int(raw.get("ambient_light"), 0, 1_000_000),
        approach=_flag(raw.get("approach")),
        screen_on=_flag(raw.get("screen_on")),
        # A percentage is clamped rather than dropped: 400 means "as bright
        # as it goes", which is a usable answer.
        brightness=(
            max(0, min(100, int(brightness)))
            if isinstance(brightness, (int, float)) and not isinstance(brightness, bool)
            else None
        ),
        page_id=str(raw.get("page_id") or "")[:64],
        app_version=str(raw.get("app_version") or "")[:32],
    )


def signal_for(panel_id: str) -> str:
    """The dispatcher signal one panel's entities listen on."""
    return f"nspanel_companion_state_{panel_id}"


#: Fired when a panel is registered, so the entity platforms can add its
#: entities without waiting for a restart. A panel paired on a Tuesday
#: should not be invisible until Home Assistant next starts.
SIGNAL_PANEL_ADDED = "nspanel_companion_panel_added"
