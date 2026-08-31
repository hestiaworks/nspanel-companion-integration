"""History for a panel: a span of time reduced to a row of bars.

Section 7 draws 24 to 48 flat rectangles and nothing else — no axes, no
curve fitting. That shape decides the whole design: the panel is handed
buckets and never raw states, because a month of a sensor's history is
thousands of rows and the page has room for thirty.

Long-term statistics are read first, since the recorder already keeps
hourly means and an hourly mean *is* a bucket. A sensor without a
state_class has no statistics to read, so its raw states are bucketed
here instead — which costs more and stops at the recorder's purge window,
but is the difference between a page that works and one that is blank.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

RANGE_SECONDS = {"6h": 6 * 3600, "24h": 24 * 3600, "7d": 7 * 86400, "30d": 30 * 86400}
# One bar per day at 7d, which is what the design draws: seven wide bars
# labelled by weekday, not twenty-eight thin ones nobody can point at. The
# shorter spans keep the dense row the prose describes.
RANGE_BUCKETS = {"6h": 24, "24h": 48, "7d": 7, "30d": 30}


def bucket_bounds(span: str, now: float) -> tuple[float, float, float]:
    """Where the window starts and ends, and how wide one bucket is."""
    seconds = RANGE_SECONDS[span]
    return now - seconds, now, seconds / RANGE_BUCKETS[span]


def bucket(samples: list[tuple[float, float]], span: str, now: float) -> list[dict[str, float] | None]:
    """Reduce timestamped samples to one entry per bucket.

    A bucket with nothing in it is None rather than zero: a gap in the
    recording is not a reading of nought, and drawing it as one would put a
    bar at the floor that never happened.
    """
    start, end, width = bucket_bounds(span, now)
    count = RANGE_BUCKETS[span]
    collected: list[list[float]] = [[] for _ in range(count)]
    for at, value in samples:
        if at < start or at > end:
            continue
        index = min(int((at - start) / width), count - 1)
        collected[index].append(value)
    return [
        None if not values else {
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
        }
        for values in collected
    ]


def summarise(buckets: list[dict[str, float] | None]) -> dict[str, float] | None:
    """The high and low across everything drawn, for the line under the hero."""
    present = [b for b in buckets if b]
    if not present:
        return None
    return {
        "min": min(b["min"] for b in present),
        "max": max(b["max"] for b in present),
    }
