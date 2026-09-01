"""Constants for NSPanel Companion."""

DOMAIN = "nspanel_companion"
DATA_SCHEDULES = "schedules"
DATA_WEBSOCKET_REGISTERED = "websocket_registered"
DATA_PAIRINGS = "pairings"
# Live panel sockets, keyed by panel id. A panel that holds one can be told
# to restart directly; one that does not is exactly the case the add-on's
# ADB path exists for.
DATA_PANEL_SOCKETS = "panel_sockets"
# One call book for the whole integration: who is in a call with whom.
DATA_CALL_BOOK = "call_book"
DATA_SCRYPTED_DISCOVERY = "scrypted_discovery"
DATA_PANEL_DISCOVERY = "panel_discovery"
STORAGE_KEY = f"{DOMAIN}.panels"
STORAGE_VERSION = 1
LAYOUT_EVENT = "nspanel_layout"
PANEL_COMPONENT = "nspanel-companion-panel"
PANEL_URL_PATH = "nspanel-companion"
# Keep in step with the manifest version: HACS offers updates from the manifest,
# and browsers keep serving the cached panel until this query string changes.
# A drift between the two ships new code that the browser never loads.
PANEL_MODULE_URL = "/nspanel_companion/frontend/nspanel-companion-panel.js?v=0.47.1"
PAIRING_TTL_SECONDS = 300
