#!/usr/bin/env bash
# Build an AppImage for gui-speedtest.
#
# GTK4 Python apps need careful runtime bundling. Strategy:
#   1. Build the wheel via `python -m build`
#   2. Start from a python-appimage starter that bundles CPython
#   3. Extract it into an AppDir
#   4. pip-install our wheel + websocket-client INTO the AppDir
#      (so the M-Lab backend works end-to-end — parity with the .deb)
#   5. Install .desktop + icon + metainfo + a GTK4-aware AppRun
#   6. Layer the GTK4 + libadwaita runtime via linuxdeploy-plugin-gtk
#   7. Repackage into the final AppImage via linuxdeploy
#
# Prerequisites (install once):
#   pip install --user python-appimage build
#   wget -O ~/.local/bin/linuxdeploy \
#     https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
#   wget -O ~/.local/bin/linuxdeploy-plugin-gtk \
#     https://raw.githubusercontent.com/linuxdeploy/linuxdeploy-plugin-gtk/master/linuxdeploy-plugin-gtk.sh
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
APP_ID="io.github.mmhfarooque.GuiSpeedTest"

# Clean build tree — AppImages are non-incremental.
rm -rf "$BUILD_DIR"
mkdir -p "$DIST_DIR" "$BUILD_DIR"

echo "==> Building wheel"
python3 -m build --wheel --outdir "$DIST_DIR"
WHEEL=$(ls -t "$DIST_DIR"/gui_speedtest-*.whl | head -1)
[ -n "$WHEEL" ] || { echo "ERROR: no wheel produced" >&2; exit 1; }

echo "==> Starter AppImage: downloading prebuilt CPython 3.12 (manylinux2014)"
cd "$BUILD_DIR"
# niess/python-appimage ships one GitHub Release per CPython patch version.
# As of 2026-04 the latest releases are all 3.13.x, so a single-page API
# query for python3.12.* tags returns nothing. Paginate via `gh api` to
# find the newest 3.12 tag reliably. gh is preinstalled on every GitHub
# Actions runner; locally the script falls back to the GITHUB_TOKEN path
# if gh isn't on PATH.
echo "    Looking up latest python3.12.x release tag (paginated)..."
if command -v gh >/dev/null 2>&1; then
    PY_TAG=$(gh api --paginate 'repos/niess/python-appimage/releases' \
                --jq '.[].tag_name' \
             | grep -E '^python3\.12\.[0-9]+$' \
             | sort -V | tail -1 || true)
else
    # Local fallback: loop through pages manually with curl.
    PY_TAG=""
    for page in 1 2 3 4 5 6 7 8 9 10; do
        TAGS=$(curl -fsSL "https://api.github.com/repos/niess/python-appimage/releases?per_page=100&page=$page" \
               | python3 -c "import sys,json; [print(r['tag_name']) for r in json.load(sys.stdin) if r['tag_name'].startswith('python3.12.')]" 2>/dev/null || true)
        [ -z "$TAGS" ] || { PY_TAG=$(echo "$TAGS" | sort -V | tail -1); break; }
    done
fi
if [ -z "$PY_TAG" ]; then
    echo "ERROR: no python3.12.x release tag found at niess/python-appimage" >&2
    exit 1
fi
echo "    Found: $PY_TAG"
PY_FILE="${PY_TAG}-cp312-cp312-manylinux2014_x86_64.AppImage"
PY_URL="https://github.com/niess/python-appimage/releases/download/${PY_TAG}/${PY_FILE}"
curl -fL -o "./${PY_FILE}" "$PY_URL"
chmod +x "./${PY_FILE}"
STARTER="./${PY_FILE}"

echo "==> Extracting $STARTER to AppDir"
"$STARTER" --appimage-extract >/dev/null
mv squashfs-root "$APPDIR"
rm -f "$STARTER"

echo "==> pip-installing gui-speedtest + websocket-client into AppDir"
# Use the bundled CPython so the install lands where AppRun can find it.
APPDIR_PYTHON=$(find "$APPDIR" -name 'python3.*' -type f -executable | head -1)
[ -n "$APPDIR_PYTHON" ] || { echo "ERROR: bundled Python not found in AppDir" >&2; exit 1; }
echo "    Using bundled Python: $APPDIR_PYTHON"

"$APPDIR_PYTHON" -m pip install --no-deps --prefix "$APPDIR/usr" "$WHEEL"
"$APPDIR_PYTHON" -m pip install --prefix "$APPDIR/usr" "websocket-client>=1.8,<3"

echo "==> Installing desktop + icon + metainfo into AppDir"
install -Dm644 "$REPO_ROOT/data/${APP_ID}.desktop" \
    "$APPDIR/usr/share/applications/${APP_ID}.desktop"
install -Dm644 "$REPO_ROOT/data/icons/${APP_ID}.svg" \
    "$APPDIR/usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg"
install -Dm644 "$REPO_ROOT/data/${APP_ID}.metainfo.xml" \
    "$APPDIR/usr/share/metainfo/${APP_ID}.metainfo.xml"
# linuxdeploy convention: top-level .desktop + icon.
ln -sf "usr/share/applications/${APP_ID}.desktop" "$APPDIR/${APP_ID}.desktop"
ln -sf "usr/share/icons/hicolor/scalable/apps/${APP_ID}.svg" "$APPDIR/${APP_ID}.svg"
# AppImage convention demands a top-level DirIcon (can be a symlink).
ln -sf "${APP_ID}.svg" "$APPDIR/.DirIcon"

echo "==> Writing AppRun that invokes gui-speedtest --gui"
cat > "$APPDIR/AppRun" <<'APPRUN_EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "$0")")"
export PATH="$HERE/usr/bin:$HERE/opt/python3.12/bin:$PATH"
# Python needs to find the bundled interpreter + our installed wheel.
# PYTHONHOME points at the extracted CPython; the wheel installed its
# `gui-speedtest` entrypoint into usr/bin which shebangs that interpreter.
export PYTHONHOME="$HERE/opt/python3.12"
export LD_LIBRARY_PATH="$HERE/usr/lib:$HERE/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
# GObject introspection typelibs for the bundled GTK4 + libadwaita.
export GI_TYPELIB_PATH="$HERE/usr/lib/x86_64-linux-gnu/girepository-1.0:$HERE/usr/lib/girepository-1.0:${GI_TYPELIB_PATH:-}"
export XDG_DATA_DIRS="$HERE/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
exec "$HERE/usr/bin/gui-speedtest" "$@"
APPRUN_EOF
chmod +x "$APPDIR/AppRun"

echo "==> Layering GTK4 runtime via linuxdeploy-plugin-gtk"
# DEPLOY_GTK_VERSION=4 → bundle GTK 4 (not 3) modules, loaders, settings.
export DEPLOY_GTK_VERSION=4
export APPIMAGE_EXTRACT_AND_RUN=1
# --custom-apprun keeps our Python/GI env wiring (linuxdeploy's default
# AppRun doesn't know about the bundled CPython).
linuxdeploy --appdir "$APPDIR" --plugin gtk \
    --desktop-file "$APPDIR/${APP_ID}.desktop" \
    --icon-file "$APPDIR/${APP_ID}.svg" \
    --custom-apprun "$APPDIR/AppRun" \
    --output appimage

echo "==> Moving result to dist/"
mv ./GUI_Speed_Test*.AppImage "$DIST_DIR/" 2>/dev/null || \
  mv ./*-x86_64.AppImage "$DIST_DIR/" 2>/dev/null || true

echo "Done. Artifacts in: $DIST_DIR"
ls -la "$DIST_DIR"/*.AppImage 2>/dev/null || echo "(no AppImage produced — check logs above)"
