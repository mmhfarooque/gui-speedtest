#!/usr/bin/env bash
# Convenience wrapper — uninstall then install the latest release.
# Use after system upgrades or when the installed package is misbehaving.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$SCRIPT_DIR/install.sh" --uninstall || true
bash "$SCRIPT_DIR/install.sh" "$@"
