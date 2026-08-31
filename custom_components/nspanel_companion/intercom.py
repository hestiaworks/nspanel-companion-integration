"""What a panel is shown, and who it may call.

Intercom is off unless a panel is opted in, and off means it does not take
part at all: absent from other panels' lists, uncallable, and silent. A
panel that rings but cannot call back is a device that can be shouted at
and cannot answer on its own terms.
"""

from __future__ import annotations

from copy import deepcopy
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
