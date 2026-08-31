"""What a panel is shown, and who it may call.

Intercom is off unless a panel is opted in, and off means it does not take
part at all: absent from other panels' lists, uncallable, and silent. A
panel that rings but cannot call back is a device that can be shouted at
and cannot answer on its own terms.
"""

from __future__ import annotations

from copy import deepcopy
import secrets
from typing import Any


def enabled_for(layout: dict[str, Any] | None) -> bool:
    return bool(((layout or {}).get("intercom") or {}).get("enabled", False))


def visible_layout(layout: dict[str, Any]) -> dict[str, Any]:
    """The layout as a panel should see it.

    Intercom widgets are withheld rather than deleted: the stored layout
    keeps them, so switching intercom back on restores the page without
    anyone reconfiguring it. Filtering here rather than at rest also means
    the panel never learns the page existed, so page indices, the default
    page and swiping need no special case for a gap in the middle.
    """
    if "intercom" not in layout or enabled_for(layout):
        return layout
    visible = deepcopy(layout)
    pages = []
    for page in visible.get("pages") or []:
        original = page.get("widgets") or []
        widgets = [w for w in original if w.get("type") != "intercom"]
        # A page whose only reason to exist has gone goes with it; a page
        # that merely mentioned intercom keeps everything else.
        if original and not widgets:
            continue
        page["widgets"] = widgets
        pages.append(page)
    visible["pages"] = pages
    ids = {page.get("id") for page in pages}
    if visible.get("default_page_id") not in ids and pages:
        visible["default_page_id"] = pages[0].get("id")
    return visible


class CallBook:
    """Who may be called, and who is in a call with whom.

    Home Assistant holds no audio and no media state — only which calls are
    open and who is in them, which is the least it can know and still route
    a signal to the right panel.
    """

    def __init__(self) -> None:
        self._calls: dict[str, tuple[str, str]] = {}

    def busy(self, panel_id: str) -> bool:
        return any(panel_id in pair for pair in self._calls.values())

    def roster(self, panels: list[dict[str, Any]], viewer: str) -> list[dict[str, Any]]:
        """Everyone the viewer could call, and whether they are free.

        A panel is absent unless it is someone else, opted in, and holding a
        socket. Being absent is how "disabled means it does not take part"
        is enforced: there is nothing to choose.
        """
        return [
            {
                "panel_id": panel["panel_id"],
                "name": panel.get("name") or panel["panel_id"],
                "busy": self.busy(panel["panel_id"]),
            }
            for panel in panels
            if panel["panel_id"] != viewer
            and panel.get("enabled")
            and panel.get("connected")
        ]

    def open(self, caller: str, callee: str) -> str | None:
        """Start a call, or refuse because one end is already in one.

        Two panels dialling each other at the same moment is the case worth
        naming: the lower id wins. Arbitrary, but the same answer on both
        sides, which is what stops each ringing the other forever.
        """
        if caller == callee or self.busy(caller) or self.busy(callee):
            return None
        call_id = secrets.token_urlsafe(12)
        self._calls[call_id] = (caller, callee)
        return call_id

    def partner(self, call_id: str, panel_id: str) -> str | None:
        pair = self._calls.get(call_id)
        if not pair or panel_id not in pair:
            return None
        return pair[1] if pair[0] == panel_id else pair[0]

    def close(self, call_id: str) -> list[str]:
        pair = self._calls.pop(call_id, None)
        return list(pair) if pair else []

    def drop_panel(self, panel_id: str) -> list[str]:
        """End whatever this panel was in, and say who else needs telling."""
        told: list[str] = []
        for call_id, pair in list(self._calls.items()):
            if panel_id in pair:
                self._calls.pop(call_id, None)
                told.extend(other for other in pair if other != panel_id)
        return told
