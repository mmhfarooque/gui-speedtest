# GUI Speed Test for Linux

[![Release](https://img.shields.io/github/v/release/mmhfarooque/gui-speedtest)](https://github.com/mmhfarooque/gui-speedtest/releases/latest)
[![License: GPL v3+](https://img.shields.io/badge/License-GPLv3%2B-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![CI](https://github.com/mmhfarooque/gui-speedtest/actions/workflows/ci.yml/badge.svg)](https://github.com/mmhfarooque/gui-speedtest/actions/workflows/ci.yml)

A fast, native GTK4 + libadwaita internet speed test for Linux. Multiple backends behind one clean interface — run against whichever server you trust.

Follows your system's light/dark theme. No browser, no tracking, no ads.

---

## What's new

- **LibreSpeed works out of the box** (1.7.0) — the backend now ships with six public LibreSpeed endpoints baked in (LibreSpeed project official, Clouvider London/NYC/Atlanta/LA, Hostkey Singapore). The GUI shows a "LibreSpeed Server" sub-picker under the Backend dropdown — choose one close to you and click Start. No more "set `LIBRESPEED_URL` env var and restart" dance. Self-hosted URLs still work via `--librespeed-url` or the env var.
- **One-command installer** (1.6.16+) — auto-detects your distro and installs the best format. No more "download the .deb then apt install" two-step.
- **Ships in 7 formats** (1.6.15+) — `.deb`, `.rpm`, AppImage, Snap, Flatpak, PyPI wheel, source tarball. All with full backend parity (Cloudflare / Ookla / M-Lab / LibreSpeed).
- **Ookla backend live progress** (1.6.0+) — sparklines and ping bars animate in real time during the run instead of sitting silent until the end.
- **Run Again works on Ookla** (1.6.0+) — fresh CLI invocation every click.
- **Backend errors wrap inside the card** (1.6.0+) — long error messages (M-Lab 401 with headers etc.) no longer push the window wider than your screen.
- **Ookla installer can't hang** (1.6.0+) — forces IPv4 + hard timeouts on curl + wget.

See [CHANGELOG / releases](https://github.com/mmhfarooque/gui-speedtest/releases) for the full history.

---

## Quick install (one command, any distro)

```sh
curl -fsSL https://raw.githubusercontent.com/mmhfarooque/gui-speedtest/main/install.sh | bash
```

The installer auto-detects your distro and installs the best-matching package (`.deb` on Ubuntu/Debian/Mint, `.rpm` on Fedora/RHEL/openSUSE, AppImage on everything else). No manual download, no two-step dance.

Alternative one-liner if you'd rather clone the repo first:

```sh
git clone https://github.com/mmhfarooque/gui-speedtest.git && cd gui-speedtest && bash install.sh
```

To remove later:

```sh
curl -fsSL https://raw.githubusercontent.com/mmhfarooque/gui-speedtest/main/install.sh | bash -s -- --uninstall
```

---

## Manual install — pick a format

If you prefer to download the package directly:

| Format | Distros | Command |
|---|---|---|
| `.deb` | Debian, Ubuntu, Mint, Pop!_OS | [See below](#debian--ubuntu--mint) |
| `.rpm` | Fedora, RHEL, openSUSE | [See below](#fedora--rhel--opensuse) |
| AppImage | Any glibc-based distro, portable | [See below](#appimage-any-distro-portable) |
| Snap | Any distro with `snapd` | [See below](#snap) |
| Flatpak | Any distro with `flatpak` | [See below](#flatpak) |
| AUR | Arch, Manjaro, EndeavourOS | [See below](#arch--manjaro--aur) |
| PyPI | Any distro with Python 3.10+ | [See below](#pypi-any-distro-fallback) |

### Debian / Ubuntu / Mint

```sh
# Download the latest .deb from the Releases page:
curl -LO https://github.com/mmhfarooque/gui-speedtest/releases/latest/download/gui-speedtest_1.6.0-1_all.deb

# Install (apt pulls in GTK4 + libadwaita + python-gi automatically):
sudo apt install ./gui-speedtest_1.6.0-1_all.deb
```

Built on Ubuntu 24.04, works on 22.04+, Debian 12+, and all derivatives.

### Fedora / RHEL / openSUSE

```sh
# Copr repository (coming soon — v1.6.x):
sudo dnf copr enable mmhfarooque/gui-speedtest
sudo dnf install gui-speedtest
```

Or grab the `.rpm` directly from the [Releases page](https://github.com/mmhfarooque/gui-speedtest/releases/latest).

### AppImage (any distro, portable)

```sh
curl -LO https://github.com/mmhfarooque/gui-speedtest/releases/latest/download/gui-speedtest-1.6.0-x86_64.AppImage
chmod +x gui-speedtest-1.6.0-x86_64.AppImage
./gui-speedtest-1.6.0-x86_64.AppImage
```

No install, no root. Bundles GTK4 + libadwaita.

### Snap

```sh
sudo snap install gui-speedtest
```

*(Snap Store publishing is in review — check [snapcraft.io/gui-speedtest](https://snapcraft.io/gui-speedtest) for status.)*

### Flatpak

```sh
flatpak install flathub io.github.mmhfarooque.GuiSpeedTest
flatpak run io.github.mmhfarooque.GuiSpeedTest
```

*(Flathub submission pending — track it on [the Flathub repo](https://github.com/flathub/io.github.mmhfarooque.GuiSpeedTest).)*

### Arch / Manjaro (AUR)

```sh
# Using any AUR helper:
yay -S gui-speedtest
# Or paru, trizen, etc.
```

### PyPI (any distro, fallback)

```sh
# System GTK4 + libadwaita must be present first:
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1   # Debian/Ubuntu
sudo dnf install python3-gobject python3-cairo gtk4 libadwaita              # Fedora
sudo pacman -S python-gobject python-cairo gtk4 libadwaita                  # Arch

pip install --user gui-speedtest
# For M-Lab NDT7 backend:
pip install --user "gui-speedtest[all]"
```

No `.desktop` registration — launch from a terminal with `gui-speedtest --gui`.

---

## Uninstall

### One-command uninstall (any format)

The same `install.sh` knows how to remove whichever format is installed — it tries every path quietly and reports what it found. **It also removes the Ookla Speedtest CLI by default** (since we installed it for you via the in-app "Enable Ookla" button or the `gui-speedtest-install-ookla` helper) along with Ookla's apt repo + signing key.

```sh
curl -fsSL https://raw.githubusercontent.com/mmhfarooque/gui-speedtest/main/install.sh | bash -s -- --uninstall
```

If you use Ookla from other tools and want to **keep the `speedtest` CLI installed**, add `--keep-ookla`:

```sh
curl -fsSL https://raw.githubusercontent.com/mmhfarooque/gui-speedtest/main/install.sh | bash -s -- --uninstall --keep-ookla
```

Or if you still have the repo cloned:

```sh
cd gui-speedtest && bash install.sh --uninstall
# (equivalent shortcut:  bash uninstall.sh)
```

### Manual uninstall — pick the format you installed

If you'd rather not re-download the installer:

**Debian / Ubuntu / Mint / Pop!_OS:**
```sh
sudo apt remove gui-speedtest
# Or wipe config/cache as well:
sudo apt purge gui-speedtest
```

**Fedora / RHEL / Rocky / Alma:**
```sh
sudo dnf remove gui-speedtest
```

**openSUSE:**
```sh
sudo zypper rm gui-speedtest
```

**Arch / Manjaro (AUR):**
```sh
yay -R gui-speedtest          # or: sudo pacman -R gui-speedtest
```

**AppImage:**
```sh
rm ~/.local/bin/gui-speedtest
rm ~/.local/share/applications/io.github.mmhfarooque.GuiSpeedTest.desktop
# If you dropped it somewhere else (e.g. ~/Applications/), rm it from there.
```

**Flatpak:**
```sh
flatpak uninstall io.github.mmhfarooque.GuiSpeedTest
```

**Snap:**
```sh
sudo snap remove gui-speedtest
```

**PyPI (pip):**
```sh
pip uninstall gui-speedtest
# If you installed with --user:  pip uninstall --user gui-speedtest
```

### Clean up user data

The app only writes to one place by default:

```sh
rm -rf ~/.cache/gui-speedtest/     # removes the rotating log file
```

There's no config directory, no keyring entries, no crontabs, no systemd units — uninstall is complete once the package is gone and the cache dir is cleared.

### Reinstall (after updates or system upgrades)

The repo ships `reinstall.sh` which does a clean uninstall-then-install in one step:

```sh
cd gui-speedtest && bash reinstall.sh
```

Or one-line equivalent (downloads the script fresh each time):

```sh
curl -fsSL https://raw.githubusercontent.com/mmhfarooque/gui-speedtest/main/install.sh | bash -s -- --uninstall && \
  curl -fsSL https://raw.githubusercontent.com/mmhfarooque/gui-speedtest/main/install.sh | bash
```

---

## Quick start

Launch the GUI:

```sh
gui-speedtest --gui
```

Click **Start Speed Test**. Cloudflare is the default — it's global anycast so it works from anywhere with no setup. The four cards (Download, Upload, Ping, Jitter) animate in real time with sparklines and histograms as the test runs. When it finishes, click **Run Again** to repeat.

To switch backends, use the **Backend** dropdown in the Connection panel.

---

## Backends

| Backend | Default | Notes |
|---|---|---|
| **Cloudflare** | ✓ | Global anycast, hits your nearest PoP. No setup. Works out of the box. |
| **Ookla Speedtest** | | Wraps the official `speedtest` CLI. Install with the in-app **Enable Ookla** button or `sudo gui-speedtest-install-ookla`. |
| **M-Lab NDT7** | | Academic/research-backed. Non-commercial. Needs `websocket-client` — `pip install 'gui-speedtest[mlab]'` or `sudo apt install python3-websocket`. |
| **LibreSpeed** | ✓ (v1.7+) | **Works out of the box.** Ships with a curated list of public LibreSpeed servers (LibreSpeed project, Clouvider in London/NYC/Atlanta/LA, Hostkey Singapore). The GUI shows a server picker under the Backend dropdown — switch between endpoints instantly, no restart. Point at a self-hosted server via `--librespeed-url` or `$LIBRESPEED_URL` if you prefer. |

The dropdown only shows backends whose prerequisites are met. If one's missing, the **Log** button in the header shows an actionable hint.

---

## Command-line usage

```sh
gui-speedtest                          # Terminal run, default backend
gui-speedtest --gui                    # Launch the GTK window
gui-speedtest --backend ookla          # Specific backend
gui-speedtest --json                   # Machine-readable output
gui-speedtest --list-backends          # Show what's available on your system
gui-speedtest --backend librespeed     # Uses first built-in LibreSpeed server
gui-speedtest --librespeed-list-servers # List the built-in LibreSpeed servers
gui-speedtest --backend librespeed --librespeed-url https://speedtest.example.com/  # Self-hosted
gui-speedtest --version
gui-speedtest --help
```

JSON output is a single object with `connection`, `latency`, `download`, `upload`, `app` keys — pipe it to `jq` or append to a log file for trend tracking.

---

## Troubleshooting

**Ookla backend doesn't appear in the dropdown.**
Click the Log button. If you see `A different 'speedtest' binary is on PATH (likely sivel/speedtest-cli …)`, that's a different tool with incompatible arguments. Install Ookla's official CLI via the in-app **Enable Ookla** button.

**Slow or hanging speed test on one ISP.**
Some ISPs in South Asia and Africa advertise IPv6 records that don't have working transit. The app's HTTP-based backends force IPv4 to dodge that (v1.5.3+). If Ookla still hangs during the run itself (not install), pick a different backend or a different Ookla server.

**`ModuleNotFoundError: No module named 'websocket'` when selecting M-Lab.**
Install the optional dep: `pip install --user 'gui-speedtest[mlab]'` or `sudo apt install python3-websocket`.

**Charts blank, text-only cards.**
Missing the cairo–GI glue: `sudo apt install python3-gi-cairo` on Debian/Ubuntu, `sudo pacman -S python-cairo` on Arch.

**Logs for reporting a bug.**
`~/.cache/gui-speedtest/gui-speedtest.log` — or click the **Log** button in the app and use **Copy All**.

---

## Build from source

```sh
git clone https://github.com/mmhfarooque/gui-speedtest
cd gui-speedtest
python3 -m build            # sdist + wheel in dist/
./scripts/build-deb.sh      # .deb in parent dir
./scripts/build-appimage.sh # AppImage in dist/
snapcraft                   # Snap in project root
```

Local dev loop:

```sh
python3 gui_speedtest.py --gui
```

Lint with `ruff check .`. CI runs on every push (see `.github/workflows/ci.yml`).

---

## Why another speed test?

- `speedtest-cli` (Python) is effectively dead — speedtest.net returns 403 for it.
- Official Ookla CLI ships without a GUI and isn't packaged for every distro.
- Fast.com / nperf / etc. require a browser and phone-home telemetry.
- Existing GTK speed tests are either unmaintained or built for GNOME 3 and look out of place in modern desktops.

This app is deliberately small: stdlib-only at runtime (plus `websocket-client` for M-Lab), no JavaScript, no ads, no account, no tracking. Open source under GPL-3.0-or-later.

---

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

---

## Links

- **Releases:** https://github.com/mmhfarooque/gui-speedtest/releases
- **Issues:** https://github.com/mmhfarooque/gui-speedtest/issues
- **Source:** https://github.com/mmhfarooque/gui-speedtest
