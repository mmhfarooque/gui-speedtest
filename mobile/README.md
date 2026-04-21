# Speed Test — Mobile & Desktop (Flutter)

[![License: GPL v3+](https://img.shields.io/badge/License-GPLv3%2B-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Flutter + Dart port of `gui-speedtest`, targeting **macOS, iOS, Android** (Windows later). Lives alongside the Linux Python/GTK4 version in the parent repo — see [../README.md](../README.md) for the platform hub.

One Dart codebase, native binaries on each platform. No browser, no tracking, no ads.

![Screenshot](docs/screenshots/macos-dark.png)

---

## Install

### macOS

1. Download the latest **`.dmg`** from the [Releases page](https://github.com/mmhfarooque/gui-speedtest/releases/latest).
2. Open the DMG, drag **Speed Test** to Applications.
3. First launch: right-click the app → **Open** → confirm (Gatekeeper bypass; the app isn't signed with an Apple Developer account yet).

### iOS / Android

Coming in v0.2. TestFlight + Google Play listings will land here.

### Linux

Not this folder — go up one level to the root of this repo for the Linux GTK4 build.

---

## How it works

- **Backend:** Cloudflare (global anycast — hits your nearest PoP). LibreSpeed + M-Lab NDT7 coming in v0.2.
- **Metrics:** download + upload Mbps (top-half average of 4 chunks: 1/5/10/25 MB), latency + jitter over 10 samples.
- **Connection detection:** tries Cloudflare `/meta` first; falls back to `/cdn-cgi/trace` + `ipwho.is` enrichment when `/meta` 403s.
- **No network data leaves your device** except to the speed test endpoint itself.

---

## Develop

```sh
git clone https://github.com/mmhfarooque/gui-speedtest
cd gui-speedtest/mobile
flutter pub get

# Run on macOS
flutter run -d macos

# Unit tests (7 pass)
flutter test

# Backend CLI smoke test (no UI)
dart run bin/test_backend.dart

# Build release .app
flutter build macos --release

# Build distributable .dmg
./scripts/build-dmg.sh
```

Requires Flutter 3.41+, Xcode 26+, CocoaPods. `flutter doctor` should be all-green.

---

## Status

| Platform | Status |
|---|---|
| macOS | ✅ v0.1.0 — Cloudflare backend only |
| iOS | 🚧 Planned v0.2 |
| Android | 🚧 Planned v0.2 |
| Windows | 🚧 Planned v0.3 (build on Windows dual-boot + VS2022) |
| Linux | Use the parent repo (native GTK4) |

---

## License

GPL-3.0-or-later. See [../LICENSE](../LICENSE).

---

## Links

- **Repo root (platform hub):** https://github.com/mmhfarooque/gui-speedtest
- **Releases:** https://github.com/mmhfarooque/gui-speedtest/releases
- **Linux source (root of repo):** https://github.com/mmhfarooque/gui-speedtest/tree/main
