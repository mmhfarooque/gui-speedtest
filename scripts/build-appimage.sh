#!/usr/bin/env bash
# Build an AppImage for gui-speedtest.
#
# Strategy (GTK4 Python apps need careful runtime bundling):
#   1. Build the wheel via `python -m build`
#   2. Generate a starter AppImage with python-appimage (CPython + our wheel)
#   3. Extract it into an AppDir
#   4. Layer the GTK4 + libadwaita runtime via linuxdeploy-plugin-gtk
#   5. Repackage into the final AppImage via linuxdeploy
#
# Prerequisites (install once):
#   pip install --user python-appimage build
#   wget -O ~/.local/bin/linuxdeploy https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
#   wget -O ~/.local/bin/linuxdeploy-plugin-gtk https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/master/linuxdeploy-plugin-gtk.sh
#   chmod +x ~/.local/bin/linuxdeploy*
#   sudo apt install -y libgtk-4-dev libadwaita-1-dev gir1.2-gtk-4.0 gir1.2-adw-1
#
# Run from repo root: ./scripts/build-appimage.sh

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
DIST_DIR="$REPO_ROOT/dist"
BUILD_DIR="$REPO_ROOT/build/appimage"
APPDIR="$BUILD_DIR/AppDir"

# Clean build tree — AppImages are non-incremental.
rm -rf "$BUILD_DIR"
mkdir -p "$DIST_DIR" "$BUILD_DIR"

echo "==> Building wheel"
python3 -m build --wheel --outdir "$DIST_DIR"

echo "==> Starter AppImage via python-appimage (CPython + our wheel)"
cd "$BUILD_DIR"
python3 -m python_appimage build app \
    --linux-tag manylinux2014_x86_64 \
    --python-version 3.12 \
    --name gui-speedtest \
    --entrypoint "gui-speedtest --gui" \
    "$REPO_ROOT/pyproject.toml"

STARTER=$(ls -t ./*.AppImage | head -1)
if [ -z "$STARTER" ]; then
    echo "ERROR: python-appimage did not produce an AppImage" >&2
    exit 1
fi

echo "==> Extracting $STARTER to AppDir"
"./$STARTER" --appimage-extract >/dev/null
mv squashfs-root "$APPDIR"

echo "==> Installing desktop + icon + metainfo into AppDir"
# linuxdeploy-plugin-gtk looks up the .desktop/icon at these canonical paths.
install -Dm644 "$REPO_ROOT/data/io.github.mmhfarooque.GuiSpeedTest.desktop" \
    "$APPDIR/usr/share/applications/io.github.mmhfarooque.GuiSpeedTest.desktop"
install -Dm644 "$REPO_ROOT/data/icons/io.github.mmhfarooque.GuiSpeedTest.svg" \
    "$APPDIR/usr/share/icons/hicolor/scalable/apps/io.github.mmhfarooque.GuiSpeedTest.svg"
install -Dm644 "$REPO_ROOT/data/io.github.mmhfarooque.GuiSpeedTest.metainfo.xml" \
    "$APPDIR/usr/share/metainfo/io.github.mmhfarooque.GuiSpeedTest.metainfo.xml"
# linuxdeploy convention: top-level .desktop and icon symlinks.
ln -sf "usr/share/applications/io.github.mmhfarooque.GuiSpeedTest.desktop" \
    "$APPDIR/io.github.mmhfarooque.GuiSpeedTest.desktop"
ln -sf "usr/share/icons/hicolor/scalable/apps/io.github.mmhfarooque.GuiSpeedTest.svg" \
    "$APPDIR/io.github.mmhfarooque.GuiSpeedTest.svg"

echo "==> Layering GTK4 runtime via linuxdeploy-plugin-gtk"
# DEPLOY_GTK_VERSION=4 → bundle GTK 4 (not 3) modules, loaders, settings
export DEPLOY_GTK_VERSION=4
# Suppress noisy warnings about missing icon themes we don't use.
export APPIMAGE_EXTRACT_AND_RUN=1
linuxdeploy --appdir "$APPDIR" --plugin gtk \
    --desktop-file "$APPDIR/io.github.mmhfarooque.GuiSpeedTest.desktop" \
    --icon-file "$APPDIR/io.github.mmhfarooque.GuiSpeedTest.svg" \
    --output appimage

echo "==> Moving result to dist/"
mv ./gui-speedtest*.AppImage "$DIST_DIR/" 2>/dev/null || mv ./*-x86_64.AppImage "$DIST_DIR/" 2>/dev/null || true

echo "Done. Artifacts in: $DIST_DIR"
ls -la "$DIST_DIR"/*.AppImage 2>/dev/null || echo "(no AppImage produced — check logs above)"
