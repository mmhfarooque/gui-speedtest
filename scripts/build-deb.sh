#!/usr/bin/env bash
# Build a .deb package locally for Debian/Ubuntu.
#
# Prerequisites:
#   sudo apt install build-essential debhelper dh-python python3-all python3-setuptools devscripts
#
# Output: ../gui-speedtest_VERSION_all.deb

set -euo pipefail
cd "$(dirname "$0")/.."
dpkg-buildpackage -us -uc -b
echo "Done. Check the parent directory for *.deb files."
