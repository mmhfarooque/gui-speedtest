#!/usr/bin/env bash
# Build an AppImage for gui-speedtest.
#
# Strategy:
#   1. python-appimage bundles CPython + our wheel into a base AppDir
#   2. linuxdeploy + linuxdeploy-plugin-gtk adds the GTK4/libadwaita runtime
#   3. appimagetool produces the final .AppImage
#
# Prerequisites (install once):
#   pip install --user python-appimage build
#   wget -O ~/.local/bin/linuxdeploy https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
#   wget -O ~/.local/bin/linuxdeploy-plugin-gtk https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/master/linuxdeploy-plugin-gtk.sh
#   chmod +x ~/.local/bin/linuxdeploy*
#
# Run from repo root: ./scripts/build-appimage.sh

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
DIST_DIR="$REPO_ROOT/dist"
BUILD_DIR="$REPO_ROOT/build/appimage"

mkdir -p "$DIST_DIR" "$BUILD_DIR"

echo "==> Building wheel"
python3 -m build --wheel --outdir "$DIST_DIR"

echo "==> Creating Python+app AppDir via python-appimage"
# Generates AppDir with the wheel installed into a bundled CPython.
python3 -m python_appimage build app \
    --linux-tag manylinux2014_x86_64 \
    --python-version 3.11 \
    --name gui-speedtest \
    --entrypoint "gui-speedtest --gui" \
    "$REPO_ROOT/pyproject.toml"

echo "==> Layering GTK4 runtime via linuxdeploy-plugin-gtk"
# TODO: wire up linuxdeploy with the plugin-gtk step. See
# https://github.com/linuxdeploy/linuxdeploy-plugin-gtk for env vars
# (DEPLOY_GTK_VERSION=4, icons, schemas, etc.)

echo "==> Moving result to dist/"
mv ./*.AppImage "$DIST_DIR/" 2>/dev/null || true

echo "Done. Artifacts in: $DIST_DIR"
