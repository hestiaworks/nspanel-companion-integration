"""The notification settings block: every sound a panel makes, in one place.

Pure, so the layout validator and the tests can both call it. The doorbell
and the intercom used to carry their own chime and volume; those fields are
read here once, as the starting point for a layout that has no block yet.
"""

from __future__ import annotations

import re
from typing import Any

# Rings: they loop until answered, so they are written to.
DOORBELL_SOUNDS = {"off", "chime_1", "chime_2", "chime_3"}
# Notifications: played once, and short.
NOTIFICATION_SOUNDS = {"off", "notify_soft", "notify_chime", "notify_alert", "notify_ping"}

# The three sounds the first audio build shipped, since replaced. A layout
# still naming one is normalised to silence rather than refused: the sound is
# gone either way, and refusing would leave a panel unable to publish
# anything at all until someone found the field that named it.
RETIRED_SOUNDS = {"chime", "bell", "ping"}

# What a type does inside the do-not-disturb window: ring as usual, show
# without a sound, or not show at all.
DND_BEHAVIOURS = {"ring", "silent", "suppress"}

DEFAULTS: dict[str, dict[str, Any]] = {
    # Silent until chosen, as they always were: a panel that has been
    # quietly on a wall for weeks must not start ringing because it updated.
    "doorbell": {"sound": "off", "volume": 70, "dnd": "ring"},
    "intercom": {"sound": "off", "volume": 70, "dnd": "ring"},
    "normal": {"sound": "notify_soft", "volume": 60, "dnd": "silent"},
    # No dnd: an important notification always rings. That is the point of
    # it, so it is not a setting.
    "important": {"sound": "notify_alert", "volume": 80},
}
DND_DEFAULT = {"enabled": False, "from": "22:00", "to": "07:00"}

_SOUNDS_FOR = {
    "doorbell": DOORBELL_SOUNDS,
    "intercom": DOORBELL_SOUNDS,
    "normal": NOTIFICATION_SOUNDS,
    "important": NOTIFICATION_SOUNDS,
}
_LABELS = {
    "doorbell": "Doorbell",
    "intercom": "Intercom",
    "normal": "Notification",
    "important": "Important notification",
}


def clock(value: Any, what: str) -> str:
    """A time of day as "HH:MM", or a refusal.

    Accepts a single-digit hour because a text field invites one, and writes
    it back padded: the panel parses one shape and a layout it cannot read
    would leave the screen behaving as though nothing had been set.
    """
    text = str(value).strip()
    match = re.fullmatch(r"(\d{1,2}):([0-5]\d)", text)
    if not match or int(match.group(1)) > 23:
        raise ValueError(f"The {what} must be a time of day, for example 07:00")
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def sound(value: Any, allowed: set[str], what: str) -> str:
    name = str(value).strip() or "off"
    if name in RETIRED_SOUNDS:
        return "off"
    if name not in allowed:
        raise ValueError(f"Invalid {what} sound")
    return name


def _volume(value: Any, what: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} volume must be a whole number") from None
    if not 0 <= number <= 100:
        raise ValueError(f"{what} volume must be 0–100")
    return number


def _legacy(doorbell: dict[str, Any], intercom: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """What the old per-feature fields said, where they said anything."""
    legacy: dict[str, dict[str, Any]] = {"doorbell": {}, "intercom": {}}
    if "chime" in doorbell:
        legacy["doorbell"]["sound"] = doorbell["chime"]
    if "chime_volume" in doorbell:
        legacy["doorbell"]["volume"] = doorbell["chime_volume"]
    if "ring" in intercom:
        legacy["intercom"]["sound"] = intercom["ring"]
    if "ring_volume" in intercom:
        legacy["intercom"]["volume"] = intercom["ring_volume"]
    return legacy


def normalize_notifications(
    raw: Any, doorbell: dict[str, Any] | None, intercom: dict[str, Any] | None,
) -> dict[str, Any]:
    """The block, validated, with defaults and the old fields folded in.

    An explicit value in the block wins; otherwise the old field; otherwise
    the default.
    """
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("Notification settings must be an object")
    legacy = _legacy(doorbell or {}, intercom or {})
    block: dict[str, Any] = {}
    for kind, default in DEFAULTS.items():
        given = raw.get(kind) or {}
        if not isinstance(given, dict):
            raise ValueError(f"{_LABELS[kind]} settings must be an object")
        merged = {**default, **legacy.get(kind, {}), **given}
        entry: dict[str, Any] = {
            "sound": sound(merged["sound"], _SOUNDS_FOR[kind], _LABELS[kind].lower()),
            "volume": _volume(merged["volume"], _LABELS[kind]),
        }
        if "dnd" in default:
            behaviour = str(merged["dnd"])
            if behaviour not in DND_BEHAVIOURS:
                raise ValueError(f"Invalid do-not-disturb behaviour for {_LABELS[kind].lower()}")
            entry["dnd"] = behaviour
        block[kind] = entry
    dnd = raw.get("dnd") or {}
    if not isinstance(dnd, dict):
        raise ValueError("Do-not-disturb settings must be an object")
    dnd = {**DND_DEFAULT, **dnd}
    # A window may cross midnight, and usually does.
    block["dnd"] = {
        "enabled": bool(dnd["enabled"]),
        "from": clock(dnd["from"], "do-not-disturb start"),
        "to": clock(dnd["to"], "do-not-disturb end"),
    }
    return block
