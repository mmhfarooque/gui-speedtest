#!/usr/bin/env bash
# Build a distributable DMG from the release .app.
# Usage: ./scripts/build-dmg.sh
set -euo pipefail

cd "$(dirname "$0")/.."

APP_NAME="Speed Test"
APP_PATH="build/macos/Build/Products/Release/${APP_NAME}.app"
VERSION=$(grep -E '^version:' pubspec.yaml | sed -E 's/version:[[:space:]]*([^+]+).*/\1/')
DMG_NAME="speedtest-mobile-${VERSION}-macos"
DMG_PATH="dist/${DMG_NAME}.dmg"

if [[ ! -d "$APP_PATH" ]]; then
  echo ">>> No release build found. Building now..."
  flutter build macos --release
fi

mkdir -p dist
rm -f "$DMG_PATH"

create-dmg \
  --volname "$APP_NAME" \
  --window-size 540 360 \
  --icon-size 96 \
  --icon "${APP_NAME}.app" 140 160 \
  --app-drop-link 400 160 \
  --hide-extension "${APP_NAME}.app" \
  "$DMG_PATH" \
  "$APP_PATH"

echo ""
echo ">>> DMG written: $DMG_PATH"
ls -lh "$DMG_PATH"
