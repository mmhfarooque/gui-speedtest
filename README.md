# GUI Speed Test for Linux

Fast, no-nonsense internet speed test for Linux with a native GTK4 + libadwaita interface that follows your system light/dark theme.

Multiple backends behind one clean interface — run the test against whichever server you trust most.

## Backends

| Backend | Default | Download | Upload | Latency | Notes |
|---|---|---|---|---|---|
| Cloudflare | ✓ | ✓ | ✓ | ✓ | Global anycast, no auth |
| Ookla | | ✓ | ✓ | ✓ | Requires `speedtest` CLI from speedtest.net/apps/cli |
| M-Lab NDT7 | | ✓ | ✓ | ✓ | Academic-backed, requires `websocket-client` |
| LibreSpeed | | ✓ | ✓ | ✓ | Needs `--librespeed-url` or `LIBRESPEED_URL` |
| OVH | | ✓ | — | ✓ | EU-based, download-only |

## Install

### From PyPI (any distro with Python 3.10+)
```sh
pip install gui-speedtest
# For M-Lab NDT7 support:
pip install "gui-speedtest[all]"
```

### Native packages (coming soon)
- `.deb` for Debian/Ubuntu
- `.rpm` for Fedora
- AUR for Arch
- AppImage portable
- Flatpak via Flathub

### System dependencies for the GUI
```sh
# Debian/Ubuntu
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
# Fedora
sudo dnf install python3-gobject gtk4 libadwaita
# Arch
sudo pacman -S python-gobject gtk4 libadwaita
```

## Usage

```sh
# Terminal
gui-speedtest

# Graphical
gui-speedtest --gui

# Different backend
gui-speedtest --backend ookla

# JSON output for scripts
gui-speedtest --json

# List what's available on your system
gui-speedtest --list-backends

# LibreSpeed with a specific server
gui-speedtest --backend librespeed --librespeed-url https://speedtest.example.com/
```

## Why another speed test?

- `speedtest-cli` (Python) is dead — speedtest.net returns 403
- Official Ookla CLI has no GUI and doesn't ship for every distro
- Fast.com, Nperf etc. require a browser
- Existing GTK speed tests are unmaintained or look out of place in modern GNOME/KDE

## License

GPL-3.0-or-later
