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
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
# Fedora
sudo dnf install python3-gobject python3-cairo gtk4 libadwaita
# Arch
sudo pacman -S python-gobject python-cairo gtk4 libadwaita
```

### Enable optional backends
The Cloudflare and M-Lab backends work out of the box with the `.deb`. Two more are available if you install their prerequisites:

```sh
# Ookla Speedtest CLI (auto-detects apt repo support, falls back to tarball)
sudo gui-speedtest-install-ookla

# LibreSpeed — point the app at any LibreSpeed server (your own or a public one)
echo 'export LIBRESPEED_URL="https://your-librespeed-server/"' >> ~/.bashrc
source ~/.bashrc
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
