#!/usr/bin/env bash
# Convenience wrapper — same as `bash install.sh --uninstall`.
# Removes whichever format of gui-speedtest is installed (.deb, .rpm,
# AppImage, Flatpak, or Snap).

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$SCRIPT_DIR/install.sh" --uninstall
