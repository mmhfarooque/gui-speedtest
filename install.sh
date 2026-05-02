#!/usr/bin/env bash
# ============================================================================
# gui-speedtest — One-Command Installer
# ============================================================================
# Auto-detects your distro, downloads the right package from the latest
# GitHub release, installs it. Supports:
#   - Debian / Ubuntu / Mint / Pop!_OS / Kali  → .deb via apt
#   - Fedora / RHEL / CentOS / Rocky / Alma    → .rpm via dnf
#   - openSUSE                                  → .rpm via zypper
#   - Arch / Manjaro / EndeavourOS             → AUR instructions (or AppImage)
#   - Any other glibc distro                    → AppImage (portable, no root)
#
# Usage (one-liner):
#   curl -fsSL https://raw.githubusercontent.com/mmhfarooque/gui-speedtest/main/install.sh | bash
#
# Usage (git clone):
#   git clone https://github.com/mmhfarooque/gui-speedtest.git
#   cd gui-speedtest && bash install.sh
#
# Options:
#   --appimage     Force AppImage install regardless of distro
#   --flatpak      Force Flatpak install (requires flatpak + flathub)
#   --snap         Force Snap install (requires snapd)
#   --uninstall    Remove gui-speedtest + Ookla CLI (if installed via our helper)
#   --keep-ookla   When used with --uninstall, keep the Ookla Speedtest CLI
#                  in place (for users who use it from other tools).
#   --version VER  Install a specific tag (default: latest)
# ============================================================================

set -e

REPO="mmhfarooque/gui-speedtest"
APP_ID="io.github.mmhfarooque.GuiSpeedTest"
PKG="gui-speedtest"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}[OK]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
info() { echo -e "  ${BLUE}[..]${NC} $1"; }

FORCE_FORMAT=""
UNINSTALL=0
KEEP_OOKLA=0
# Don't use the name VERSION here — `. /etc/os-release` below sets its own
# VERSION variable ("26.04 (Resolute Raccoon)" on Ubuntu 26.04) and would
# clobber ours. Rename to REQUESTED_TAG.
REQUESTED_TAG="latest"

while [ $# -gt 0 ]; do
    case "$1" in
        --appimage) FORCE_FORMAT="appimage"; shift ;;
        --flatpak)  FORCE_FORMAT="flatpak"; shift ;;
        --snap)     FORCE_FORMAT="snap"; shift ;;
        --uninstall) UNINSTALL=1; shift ;;
        --keep-ookla) KEEP_OOKLA=1; shift ;;
        --version)  REQUESTED_TAG="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,30p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) fail "Unknown option: $1"; exit 1 ;;
    esac
done

if [ "$(id -u)" -eq 0 ]; then
    fail "Do not run as root. The script uses sudo when needed."
    exit 1
fi

echo
echo "============================================"
echo "  GUI Speed Test for Linux — Installer"
echo "============================================"
echo

# ----------------------------------------------------------------------------
# Distro detection
# ----------------------------------------------------------------------------
DISTRO_ID=""
DISTRO_FAMILY=""
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    DISTRO_ID="${ID:-unknown}"
    DISTRO_ID_LIKE="${ID_LIKE:-}"
    case "$DISTRO_ID $DISTRO_ID_LIKE" in
        *debian*|*ubuntu*) DISTRO_FAMILY="debian" ;;
        *fedora*|*rhel*|*centos*|*rocky*|*alma*) DISTRO_FAMILY="fedora" ;;
        *suse*|*opensuse*) DISTRO_FAMILY="suse" ;;
        *arch*|*manjaro*) DISTRO_FAMILY="arch" ;;
        *) DISTRO_FAMILY="unknown" ;;
    esac
fi
info "Detected distro: ${DISTRO_ID:-unknown} (family: ${DISTRO_FAMILY:-unknown})"

# ----------------------------------------------------------------------------
# Uninstall path
# ----------------------------------------------------------------------------
if [ "$UNINSTALL" = "1" ]; then
    echo
    info "Uninstalling gui-speedtest (whatever format is installed)..."
    # Try each possible install path — quiet failures, we just want it gone.
    case "$DISTRO_FAMILY" in
        debian) sudo apt-get remove -y "$PKG" 2>/dev/null && ok "Removed .deb" || true ;;
        fedora) sudo dnf remove -y "$PKG" 2>/dev/null && ok "Removed .rpm" || true ;;
        suse)   sudo zypper rm -y "$PKG" 2>/dev/null && ok "Removed .rpm" || true ;;
        arch)   sudo pacman -R --noconfirm "$PKG" 2>/dev/null && ok "Removed Arch pkg" || true ;;
    esac
    if command -v flatpak >/dev/null 2>&1; then
        flatpak uninstall -y "$APP_ID" 2>/dev/null && ok "Removed Flatpak" || true
    fi
    if command -v snap >/dev/null 2>&1; then
        sudo snap remove "$PKG" 2>/dev/null && ok "Removed Snap" || true
    fi
    # AppImage removal
    rm -f "$HOME/.local/bin/$PKG" \
          "$HOME/.local/share/applications/${APP_ID}.desktop" \
          "$HOME/Applications/GUI_Speed_Test_for_Linux-x86_64.AppImage" 2>/dev/null && \
        ok "Removed AppImage" || true
    # User data — the only place the app writes to.
    rm -rf "$HOME/.cache/gui-speedtest" 2>/dev/null && ok "Removed ~/.cache/gui-speedtest/" || true

    # Ookla Speedtest CLI — we installed it for you (via Enable Ookla button
    # or sudo gui-speedtest-install-ookla), so we clean it up by default.
    # Pass --keep-ookla if you use Ookla for other tools.
    if [ "$KEEP_OOKLA" = "1" ]; then
        info "Keeping Ookla Speedtest CLI (--keep-ookla)"
    else
        info "Removing Ookla Speedtest CLI + its apt repo..."
        # apt-installed package (Ookla's own repo at packagecloud.io)
        if dpkg -l speedtest >/dev/null 2>&1; then
            sudo apt-get purge -y speedtest 2>&1 | tail -2
            ok "Removed Ookla apt package"
        fi
        # Ookla's apt repo + signing key (added by install.deb.sh)
        sudo rm -f /etc/apt/sources.list.d/ookla_speedtest-cli.list \
                   /etc/apt/sources.list.d/ookla_speedtest-cli.sources \
                   /usr/share/keyrings/ookla_speedtest-cli-archive-keyring.gpg \
                   /etc/apt/trusted.gpg.d/ookla_speedtest-cli.gpg 2>/dev/null && \
            ok "Removed Ookla apt repo + keyring" || true
        # Tarball fallback install (used when apt repo didn't have the codename)
        sudo rm -f /usr/local/bin/speedtest 2>/dev/null && \
            ok "Removed /usr/local/bin/speedtest" || true
        # RPM-installed (Fedora, via Ookla's rpm repo or our install-ookla script)
        if command -v dnf >/dev/null 2>&1 && rpm -q speedtest >/dev/null 2>&1; then
            sudo dnf remove -y speedtest 2>&1 | tail -2
            ok "Removed Ookla rpm package"
        fi
    fi

    ok "Uninstall complete."
    exit 0
fi

# ----------------------------------------------------------------------------
# Pick a format
# ----------------------------------------------------------------------------
if [ -n "$FORCE_FORMAT" ]; then
    FORMAT="$FORCE_FORMAT"
    info "Format forced: $FORMAT"
else
    case "$DISTRO_FAMILY" in
        debian) FORMAT="deb" ;;
        fedora) FORMAT="rpm" ;;
        suse)   FORMAT="rpm" ;;
        arch)   FORMAT="appimage" ;;  # AUR submission pending; AppImage is safest
        *)      FORMAT="appimage" ;;
    esac
    info "Chosen format for this distro: $FORMAT"
fi

# ----------------------------------------------------------------------------
# Resolve the release tag + download URL
# ----------------------------------------------------------------------------
if [ "$REQUESTED_TAG" = "latest" ]; then
    info "Looking up latest release tag..."
    # NOTE: /releases/latest returns whichever release GitHub flagged as
    # "latest" — which can be the mobile companion app (mobile-v*) since it
    # shares this repo. Filter to desktop tags (vN.N.N) explicitly.
    TAG=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases?per_page=20" \
          | grep -E '"tag_name"' \
          | grep -E '"v[0-9]' \
          | head -1 \
          | sed -E 's/.*"tag_name":[[:space:]]*"([^"]+)".*/\1/')
    [ -n "$TAG" ] || { fail "Could not find a release tag. Check your network."; exit 1; }
else
    TAG="$REQUESTED_TAG"
fi
VER="${TAG#v}"
ok "Installing $TAG"

DOWNLOAD_BASE="https://github.com/${REPO}/releases/download/${TAG}"

# ----------------------------------------------------------------------------
# Install by format
# ----------------------------------------------------------------------------
case "$FORMAT" in
    deb)
        ASSET="${PKG}_${VER}-1_all.deb"
        TMP="/tmp/${ASSET}"
        info "Downloading $ASSET..."
        curl -fL -o "$TMP" "${DOWNLOAD_BASE}/${ASSET}"
        info "Installing (apt will pull in GTK4 + libadwaita + python-gi)..."
        sudo apt-get install -y "$TMP"
        rm -f "$TMP"
        ok "Installed. Launch: gui-speedtest --gui"
        ;;

    rpm)
        ASSET="${PKG}-${VER}-1.fc41.noarch.rpm"
        TMP="/tmp/${ASSET}"
        info "Downloading $ASSET..."
        curl -fL -o "$TMP" "${DOWNLOAD_BASE}/${ASSET}" || {
            fail "Download failed — this RPM is built against Fedora 41 macros."
            fail "On RHEL/openSUSE the filename may differ. Try --appimage instead."
            exit 1
        }
        info "Installing..."
        if command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y "$TMP"
        elif command -v zypper >/dev/null 2>&1; then
            sudo zypper install -y --allow-unsigned-rpm "$TMP"
        else
            sudo rpm -Uvh "$TMP"
        fi
        rm -f "$TMP"
        ok "Installed. Launch: gui-speedtest --gui"
        ;;

    appimage)
        ASSET="GUI_Speed_Test_for_Linux-x86_64.AppImage"
        mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
        TARGET="$HOME/.local/bin/${PKG}"
        info "Downloading $ASSET to $TARGET..."
        curl -fL -o "$TARGET" "${DOWNLOAD_BASE}/${ASSET}"
        chmod +x "$TARGET"
        # Create a .desktop entry so it shows up in GNOME/KDE app menus.
        DESKTOP="$HOME/.local/share/applications/${APP_ID}.desktop"
        cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=GUI Speed Test for Linux
Comment=Multi-backend internet speed test
Exec=${TARGET} --gui
Icon=${APP_ID}
Terminal=false
Categories=Network;Utility;
StartupWMClass=${APP_ID}
EOF
        # Add ~/.local/bin to PATH if not already there.
        case ":$PATH:" in
            *":$HOME/.local/bin:"*) : ;;
            *) warn "$HOME/.local/bin not in PATH. Add to your shell rc:"
               warn "  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
        esac
        ok "Installed. Launch: ${TARGET} --gui  (or from your app menu)"
        ;;

    flatpak)
        if ! command -v flatpak >/dev/null 2>&1; then
            fail "flatpak is not installed. Install it first:"
            fail "  sudo apt install flatpak   # or your distro's equivalent"
            exit 1
        fi
        ASSET="gui-speedtest.flatpak"
        TMP="/tmp/${ASSET}"
        info "Downloading $ASSET..."
        curl -fL -o "$TMP" "${DOWNLOAD_BASE}/${ASSET}"
        info "Installing (will pull in org.gnome.Platform/47 if missing)..."
        flatpak install --user -y --bundle "$TMP"
        rm -f "$TMP"
        ok "Installed. Launch: flatpak run ${APP_ID}"
        ;;

    snap)
        if ! command -v snap >/dev/null 2>&1; then
            fail "snapd is not installed. Install it first:"
            fail "  sudo apt install snapd   # or your distro's equivalent"
            exit 1
        fi
        ASSET="${PKG}_${VER}_amd64.snap"
        TMP="/tmp/${ASSET}"
        info "Downloading $ASSET..."
        curl -fL -o "$TMP" "${DOWNLOAD_BASE}/${ASSET}"
        info "Installing (dangerous mode — bundle isn't Store-signed yet)..."
        sudo snap install --dangerous "$TMP"
        rm -f "$TMP"
        ok "Installed. Launch: snap run ${PKG}"
        ;;

    *)
        fail "Unknown format: $FORMAT"
        exit 1
        ;;
esac

echo
echo "============================================"
ok "gui-speedtest $TAG is installed."
echo "============================================"
echo
echo "  Launch the GUI:   gui-speedtest --gui"
echo "  Or the CLI:       gui-speedtest"
echo "  Uninstall:        bash install.sh --uninstall"
echo
