"""The notification settings block: every sound a panel makes, in one place.

Pure, so the layout validator and the tests can both call it. The doorbell
and the intercom used to carry their own chime and volume; those fields are
read here once, as the starting point for a layout that has no block yet.
"""

from __future__ import annotations

import re
from typing import Any
import uuid

# Rings: they loop until answered, so they are written to. The three chimes
# predate the rest; everything else was synthesised for this project, or is
# from Kenney's Interface Sounds (CC0), so the files carry no licence terms.
DOORBELL_SOUNDS = {"off", "chime_1", "chime_2", "chime_3", "ding_dong", "three_tone", "westminster", "marimba", "tubular", "vibraphone", "shop_door", "music_box", "kalimba", "bell_chords"}
# Notifications: played once, and short.
NOTIFICATION_SOUNDS = {
    "off",
    "notify_soft",
    "notify_chime",
    "notify_ping",
    "notify_bright",
    "notify_confirm",
    "notify_query",
    "notify_glass",
    "notify_kalimba",
    "notify_knock",
    "notify_vibraphone",
    "notify_drop",
    "notify_music_box",
    "notify_alert",
    "notify_double",
    "notify_rise",
    "notify_confirm_long",
    "notify_triple",
    "notify_kalimba_run",
    "notify_bell_chord",
}

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
    # Six seconds is the approved design's figure, kept as the default.
    # It may also come back while unread, banner and all.
    "normal": {"sound": "notify_soft", "volume": 60, "dnd": "silent", "duration": 6,
               "repeat_every": 0, "repeat_times": 3},
    # No dnd: an important notification always rings. That is the point of
    # it, so it is not a setting. It rings once unless asked to repeat.
    "important": {"sound": "notify_alert", "volume": 80, "repeat_every": 0, "repeat_times": 3},
}

#: How long a banner may stay, in seconds.
BANNER_SECONDS = (3, 30)
#: How often an unanswered notification comes back; 0 is never.
REPEAT_EVERY = (0, 30, 60, 120, 300)
#: How many times it rings again; 0 is until it is answered.
REPEAT_TIMES = (0, 3, 5, 10)
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


def _whole(value: Any, what: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{what} must be a whole number")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a whole number") from None


def _choice_range(value: Any, bounds: tuple[int, int], what: str) -> int:
    number = _whole(value, what)
    if not bounds[0] <= number <= bounds[1]:
        raise ValueError(f"{what} must be {bounds[0]}–{bounds[1]} seconds")
    return number


def _choice(value: Any, allowed: tuple[int, ...], what: str) -> int:
    number = _whole(value, what)
    if number not in allowed:
        raise ValueError(f"{what} must be one of {', '.join(map(str, allowed))}")
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
        if "duration" in default:
            entry["duration"] = _choice_range(merged["duration"], BANNER_SECONDS, "Banner duration")
        if "repeat_every" in default:
            entry["repeat_every"] = _choice(merged["repeat_every"], REPEAT_EVERY, "Repeat interval")
            entry["repeat_times"] = _choice(merged["repeat_times"], REPEAT_TIMES, "Repeat count")
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


def _minute(text: str) -> int:
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def in_quiet_hours(block: dict[str, Any], minute: int) -> bool:
    """Whether [minute] falls in the block's quiet hours, as the panel reads them.

    Equal ends are no window at all, the reading that cannot silence a
    doorbell by accident.
    """
    dnd = block.get("dnd") or {}
    if not dnd.get("enabled"):
        return False
    start, end = _minute(dnd["from"]), _minute(dnd["to"])
    if start == end:
        return False
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


#: How long a test call rings before the server ends it for nobody.
TEST_CALL_SECONDS = 8


class TestCalls:
    """Intercom calls the editor starts to try a panel's ring.

    Nobody is at the other end, so the server answers for them: an answer or
    a decline ends the call at once, and so does a timeout. Each ends once,
    because the timeout and a tap can race.
    """

    def __init__(self) -> None:
        self._pending: dict[str, str] = {}

    def start(self, panel_id: str) -> str:
        call_id = f"test-{uuid.uuid4().hex[:12]}"
        self._pending[call_id] = panel_id
        return call_id

    def finish(self, call_id: str) -> bool:
        return self._pending.pop(call_id, None) is not None
