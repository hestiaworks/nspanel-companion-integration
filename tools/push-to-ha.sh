#!/usr/bin/env bash
# Copy the integration into a running Home Assistant over the mounted Samba
# share, for the development loop where cutting a release per change is absurd.
#
#   tools/push-to-ha.sh            # the frontend file only — no restart needed
#   tools/push-to-ha.sh --all      # every Python file too — needs a restart
#
# HACS will show the integration as modified afterwards. That is expected;
# redownloading the release in HACS puts it back.
set -euo pipefail

share="${NSPANEL_HA_CONFIG:-/Volumes/config}"
target="$share/custom_components/nspanel_companion"
here="$(cd "$(dirname "$0")/.." && pwd)"
source_dir="$here/custom_components/nspanel_companion"

if [ ! -d "$share" ]; then
  echo "Not mounted: $share" >&2
  echo "In Finder: Go → Connect to Server → smb://192.168.0.76 → the 'config' share." >&2
  echo "Mounted somewhere else? Set NSPANEL_HA_CONFIG to that path." >&2
  exit 2
fi
if [ ! -d "$target" ]; then
  echo "No integration at $target — is this the Home Assistant config share?" >&2
  exit 2
fi

if [ "${1:-}" = "--all" ]; then
  # --delete would take files this checkout does not carry, so it is not used:
  # a stray file is recoverable, someone's live integration is not.
  rsync -rlD --inplace --no-times --exclude "__pycache__" "$source_dir/" "$target/"
  echo "Copied the whole integration. Restart Home Assistant for the Python to take."
else
  rsync -rlD --inplace --no-times "$source_dir/frontend/" "$target/frontend/"
  echo "Copied the frontend. Hard-refresh the browser (⌘⇧R) — no restart needed."
fi
