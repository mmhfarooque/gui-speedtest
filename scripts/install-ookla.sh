#!/usr/bin/env bash
# Install Ookla's official `speedtest` CLI — enables the Ookla backend
# in gui-speedtest. Shipped with the .deb as `gui-speedtest-install-ookla`.
#
# Strategy:
#   1. Try Ookla's apt repo (install.deb.sh). Users get auto-updates via
#      apt upgrade going forward, which is ideal when available.
#   2. If the apt repo doesn't have a build for the current distro
#      codename (happens on brand-new Ubuntu releases before Ookla
#      catches up — e.g. 26.04 resolute returned 404 for months after
#      its release), fall back to Ookla's standalone tarball installed
#      to /usr/local/bin/speedtest. No auto-updates but always works.
#
# Requires sudo (installs binary system-wide).

set -euo pipefail

TARBALL_URL="https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-linux-x86_64.tgz"
APT_INSTALLER="https://install.speedtest.net/app/cli/install.deb.sh"

# -4 forces IPv4 resolution. Some ISPs (e.g. Tuhin Enterprise in Dhaka)
# advertise IPv6 AAAA records that don't actually have working transit;
# wget/curl then sit on the IPv6 connect attempt for many minutes because
# neither implements Happy Eyeballs. --connect-timeout / --max-time give
# a hard ceiling so the installer can't hang forever even if -4 routes
# via a flaky IPv4 path. Python urllib has a separate fix in base.py.
CURL="curl -4 --connect-timeout 15 --max-time 120"
WGET="wget -4 --timeout=30 --tries=2"

say() { echo "==> $*"; }
note() { echo "    $*"; }

# ---------- Skip if a viable binary is already present ----------
if command -v speedtest >/dev/null 2>&1; then
    if speedtest --version 2>&1 | grep -qi "Ookla"; then
        say "Ookla CLI already installed — nothing to do."
        speedtest --version | head -2
        exit 0
    else
        note "A different 'speedtest' binary is on PATH (likely sivel/speedtest-cli"
        note "Python wrapper). gui-speedtest's Ookla backend will still only run when"
        note "Ookla's binary is reachable — the wrapper uses incompatible arguments."
        note "Continuing — this script installs Ookla's binary alongside."
    fi
fi

# ---------- Ensure prerequisites ----------
for tool in curl tar wget; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        say "Installing prerequisite: $tool"
        sudo apt-get install -y "$tool"
    fi
done

# ---------- Try the apt repo first ----------
USE_TARBALL=1
if command -v apt-get >/dev/null 2>&1; then
    CODENAME=$(lsb_release -cs 2>/dev/null || echo unknown)
    say "Detected apt-based system (codename: $CODENAME)"
    note "Attempting Ookla's apt repo install (keeps the CLI up-to-date via apt upgrade)"

    if $CURL -sSL "$APT_INSTALLER" | sudo bash 2>&1 | tail -5; then
        # install.deb.sh exited 0 but that doesn't mean the repo has our codename.
        # Sniff apt update output for a 404 on the packagecloud Ookla repo.
        UPDATE_OUT=$(sudo apt-get update 2>&1 || true)
        if echo "$UPDATE_OUT" | grep -qE "packagecloud\.io/ookla.*404|ookla.*Release.*404"; then
            note "Ookla apt repo has no build for '$CODENAME' yet — falling back to tarball."
            # Remove the broken sources so future apt update doesn't error.
            sudo rm -f /etc/apt/sources.list.d/ookla_speedtest-cli.list \
                       /etc/apt/sources.list.d/ookla_speedtest-cli.sources
            sudo apt-get update 2>&1 >/dev/null || true
        else
            note "Installing speedtest from Ookla's apt repo…"
            if sudo apt-get install -y speedtest; then
                USE_TARBALL=0
                say "Installed via apt — future updates via 'sudo apt upgrade'."
            fi
        fi
    fi
fi

# ---------- Fallback: standalone tarball ----------
if [ "$USE_TARBALL" = "1" ]; then
    say "Installing Ookla CLI from tarball to /usr/local/bin/speedtest"
    TMP=$(mktemp -d)
    trap 'rm -rf "$TMP"' EXIT
    $WGET -q -O "$TMP/ookla.tgz" "$TARBALL_URL"
    tar -xzf "$TMP/ookla.tgz" -C "$TMP" speedtest
    sudo install -m 0755 "$TMP/speedtest" /usr/local/bin/speedtest
fi

# ---------- Verify + remind about licence acceptance ----------
say "Verifying"
if ! command -v speedtest >/dev/null 2>&1; then
    echo "ERROR: 'speedtest' not on PATH after install — check errors above." >&2
    exit 1
fi
which speedtest
speedtest --version | head -2 || true

cat <<'EOF'

==> Done.
Ookla's CLI is now installed. On first run it may ask you to accept
their licence and GDPR notice. gui-speedtest passes --accept-license
and --accept-gdpr automatically, so you don't need to pre-accept in
a terminal — just launch gui-speedtest and pick Ookla from the
backend dropdown.

If Ookla still doesn't appear in the dropdown, restart gui-speedtest
so it re-checks PATH.
EOF
