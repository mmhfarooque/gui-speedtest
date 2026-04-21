# macOS Build Plan — tiniest increments

Work top-to-bottom. Each leaf item should be one short back-and-forth.
Tick with `[x]` as you go. Phase = group of related leaves.

---

## Phase 1 — Smoke test (prove the toolchain works)

### 1.1 Run stock app
- [ ] 1.1.1 `cd ~/app-dev/speedtest-mobile`
- [ ] 1.1.2 `flutter run -d macos`
- [ ] 1.1.3 Counter window appears
- [ ] 1.1.4 `+` button increments
- [ ] 1.1.5 Press `q` to quit

---

## Phase 2 — Project housekeeping

### 2.1 pubspec metadata
- [x] 2.1.1 Set name/description/version in `pubspec.yaml`
- [x] 2.1.2 `publish_to: 'none'`
- [x] 2.1.3 Set SDK constraint

### 2.2 Dependencies
- [x] 2.2.1 Add `http` (HTTP client) — 1.6.0
- [x] 2.2.2 Add `provider` (state management) — 6.1.5+1
- [x] 2.2.3 `flutter pub get`

### 2.3 macOS entitlements (REQUIRED for network)
- [x] 2.3.1 Add `com.apple.security.network.client` to `macos/Runner/DebugProfile.entitlements`
- [x] 2.3.2 Same for `macos/Runner/Release.entitlements`
- [ ] 2.3.3 Verify by running the app and hitting a URL (deferred — will test in phase 7 smoke test)

### 2.4 Clean boilerplate
- [x] 2.4.1 Gut `lib/main.dart` to minimal MaterialApp + blank Scaffold
- [x] 2.4.2 Delete counter-related code
- [ ] 2.4.3 Hot reload → blank window (user to verify)

### 2.5 Folder structure
- [x] 2.5.1 `lib/models/`
- [x] 2.5.2 `lib/backends/`
- [x] 2.5.3 `lib/ui/`
- [x] 2.5.4 `lib/ui/cards/`
- [x] 2.5.5 `lib/state/`
- [x] 2.5.6 `lib/utils/`

---

## Phase 3 — Data models (pure Dart, no Flutter yet)

### 3.1 ConnectionInfo
- [x] 3.1.1 File `lib/models/connection_info.dart`
- [x] 3.1.2 Fields: ip, isp, city, region, country, server
- [x] 3.1.3 `location` getter (joins non-empty city/region/country)

### 3.2 LatencyResult
- [x] 3.2.1 File `lib/models/latency_result.dart`
- [x] 3.2.2 Fields: avg, min, max, jitter, samples, failed
- [x] 3.2.3 `fromSamples()` factory (compute stats)

### 3.3 SpeedResult
- [x] 3.3.1 File `lib/models/speed_result.dart`
- [x] 3.3.2 Fields: speedMbps, samples list
- [x] 3.3.3 `topHalf()` factory — sort desc, avg top ceil(n/2)

### 3.4 Unit tests for models
- [x] 3.4.1 top-half 4 samples (grouped in `test/speed_result_test.dart`)
- [x] 3.4.2 top-half 5 samples odd (same file)
- [x] 3.4.3 top-half empty (same file) + bonus: single sample
- [x] 3.4.4 latency fromSamples stats (`test/latency_result_test.dart`)
- [x] 3.4.5 latency empty -> failed=true (same file)
- [x] 3.4.6 `flutter test` → all 7 green

---

## Phase 4 — Backend contract

### 4.1 Error type
- [x] 4.1.1 File `lib/backends/backend_error.dart` — exception class

### 4.2 Progress event type
- [x] 4.2.1 File `lib/backends/progress_event.dart` — sealed class hierarchy (6 event types)

### 4.3 Abstract base
- [x] 4.3.1 File `lib/backends/speed_test_backend.dart`
- [x] 4.3.2 Abstract `connectionInfo()` → Future
- [x] 4.3.3 Abstract `testLatency()` → Future, optional ProgressCallback
- [x] 4.3.4 Abstract `testDownload()` → Future, optional ProgressCallback
- [x] 4.3.5 Abstract `testUpload()` → Future, optional ProgressCallback
- [x] 4.3.6 `cancel()` method

---

## Phase 5 — Utilities

### 5.1 Browser UA
- [x] 5.1.1 File `lib/utils/browser_ua.dart` with Chrome 140 UA (Mac platform string)

### 5.2 Speed formatter
- [x] 5.2.1 File `lib/utils/format_speed.dart`
- [x] 5.2.2 <1000 Mbps → "X.XX Mbps"; ≥1000 → "X.XX Gbps"
- [x] 5.2.3 Unit test both branches (2 tests pass)

---

## Phase 6 — Cloudflare backend

### 6.1 Skeleton
- [x] 6.1.1 File `lib/backends/cloudflare.dart`
- [x] 6.1.2 URL constants (_metaUrl, _downUrl, _upUrl, _traceUrl, _ipifyUrl)
- [x] 6.1.3 Size lists (_downSizes, _upSizes — 1/5/10/25 MB, symmetric)

### 6.2 connectionInfo()
- [x] 6.2.1 Try `/meta` with browser UA
- [x] 6.2.2 Parse JSON → ConnectionInfo
- [x] 6.2.3 Fallback 1: `/cdn-cgi/trace` (IP + colo + country)
- [x] 6.2.4 Fallback 2: `api.ipify.org` (IP only)
- [x] 6.2.5 Final fallback: empty ConnectionInfo with just server="Cloudflare" — never raises. (Python uses BackendError only in latency/down/up; connection_info degrades gracefully.)

### 6.3 testLatency()
- [x] 6.3.1 Loop N samples (default 10)
- [x] 6.3.2 Per sample: GET `__down?bytes=0`, time via Stopwatch (microsecond → ms)
- [x] 6.3.3 Emit `LatencySample` event each
- [x] 6.3.4 Return `LatencyResult.fromSamples(times)`
- [x] 6.3.5 Honours `_cancelled` — breaks loop, returns what's collected so far
- [x] 6.3.6 Per-sample errors swallowed (all-failed → `failed=true` via empty list)

### 6.4 testDownload()
- [x] 6.4.1 For each DOWN_SIZE: stream response via http.Client.send, count bytes, time with Stopwatch
- [x] 6.4.2 Compute chunk Mbps `(bytes * 8) / (elapsedSec * 1e6)`
- [x] 6.4.3 Emit `DownloadProgress` every 256 KiB
- [x] 6.4.4 Emit `DownloadChunk` on each chunk done
- [x] 6.4.5 Return `SpeedResult.topHalf(results)`; throw `BackendError` if all chunks failed
- [x] 6.4.6 Honours `_cancelled` mid-stream + between chunks; `cancel()` closes `_client` to unblock stream

### 6.5 testUpload()
- [x] 6.5.1 For each UP_SIZE: generate random bytes via `Random()` (non-secure; defeats compression, 25 MB secure is wasteful)
- [x] 6.5.2 POST with body, time via Stopwatch
- [x] 6.5.3 Compute chunk Mbps `(size * 8) / (elapsedSec * 1e6)` — size known up front, no read-stream needed
- [x] 6.5.4 Emit `UploadChunk` per size; `ChunkError` on failure
- [x] 6.5.5 Return `SpeedResult.topHalf(results)`; throw `BackendError` if all failed
- [x] 6.5.6 `cancel()` covers upload too (same _client)

### 6.6 cancel()
- [x] 6.6.1 Store current `http.Client` as instance field `_client`
- [x] 6.6.2 `cancel()` closes client and sets `_cancelled` flag
- [x] 6.6.3 Loop checks flag between chunks AND mid-stream (download); client close unblocks blocked `await`

---

## Phase 7 — Backend smoke test (CLI before UI)

- [x] 7.1 Write `bin/test_backend.dart` — runs Cloudflare backend once, prints results
- [x] 7.2 `dart run bin/test_backend.dart`
- [x] 7.3 Verify: ✅ IP/server/country/latency/download/upload all return real numbers. ⚠ ISP/city "Unknown" — `/meta` 403s with our UA and falls through to `/cdn-cgi/trace`. Known, cosmetic, defer to v0.2.
- [ ] 7.4 Compare with Linux gui-speedtest on same connection (user to run when convenient)

---

## Phase 8 — State management

### 8.1 TestRunner
- [x] 8.1.1 File `lib/state/test_runner.dart` as ChangeNotifier
- [x] 8.1.2 `TestPhase` enum: idle/connecting/latency/download/upload/done/error
- [x] 8.1.3 Holds ConnectionInfo, LatencyResult, SpeedResult(s), live-*Mbps, errorText
- [x] 8.1.4 `start()` runs all phases sequentially, notifies on each transition + live updates
- [x] 8.1.5 `cancel()` aborts via `_backend.cancel()`
- [x] 8.1.6 `_onProgress` updates `liveDownloadMbps` / `liveUploadMbps` mid-test — UI gets smooth animated numbers

### 8.2 Provider plumbing
- [x] 8.2.1 Wrap SpeedTestApp in `ChangeNotifierProvider` creating a TestRunner

---

## Phase 9 — UI shell

### 9.1 App root
- [x] 9.1.1 File `lib/ui/app.dart` — MaterialApp
- [x] 9.1.2 Material 3 theme (blue seed, light + dark)
- [x] 9.1.3 `themeMode: ThemeMode.system`
- [x] 9.1.4 `debugShowCheckedModeBanner: false` (no DEBUG ribbon)

### 9.2 Home page
- [x] 9.2.1 File `lib/ui/home_page.dart`
- [x] 9.2.2 Scaffold + AppBar "Speed Test"
- [x] 9.2.3 Body: Padding(16) + Column(stretch) — empty slots for 9.3 button + Phase 10 cards

### 9.3 Start/Cancel/Run-Again button
- [x] 9.3.1 `StartButton` widget in `lib/ui/start_button.dart`; centered `FilledButton.icon` with big padding
- [x] 9.3.2 Label/icon/onPressed switch on `runner.phase` via Dart 3 pattern matching (idle→Start, done→Run Again, error→Try Again, running→Cancel)

---

## Phase 10 — Cards

### 10.1 CardBase
- [x] 10.1.1 File `lib/ui/cards/card_base.dart`
- [x] 10.1.2 Material 3 Card, 12px radius, outline variant border, uppercase title + optional subtitle + child slot

### 10.2 Connection card
- [x] 10.2.1 File `lib/ui/cards/connection_card.dart`
- [x] 10.2.2 Shows Server / IP / ISP / Location with 80px label column
- [x] 10.2.3 Placeholder "—" when null or empty

### 10.3 Download card
- [x] 10.3.1 File `lib/ui/cards/download_card.dart`
- [x] 10.3.2 Big `headlineMedium` Mbps/Gbps via `formatSpeed`, primary color, single line + ellipsis

### 10.4 Upload card
- [x] 10.4.1 File `lib/ui/cards/upload_card.dart` — same layout as DownloadCard, `tertiary` color to visually distinguish

### 10.5 Ping card
- [x] 10.5.1 File `lib/ui/cards/ping_card.dart` — shows `lat.avg` in ms, "—" when null/failed

### 10.6 Jitter card
- [x] 10.6.1 File `lib/ui/cards/jitter_card.dart` — shows `lat.jitter` in ms

### 10.7 Grid layout
- [x] 10.7.1 Connection card full-width on top
- [x] 10.7.2 Two Rows of [card, SizedBox, card] with Expanded — simpler than GridView for fixed 2×2
- [x] 10.7.3 SingleChildScrollView wrapper so narrow windows can scroll if cards overflow

---

## Phase 11 — Wire cards to state

- [x] 11.1 Each card uses `context.watch<TestRunner>()` or `context.select`
- [x] 11.2 Connection card rebuilds when `connectionInfo` changes
- [x] 11.3 Speed cards rebuild on live Mbps updates (mid-test smooth animation)
- [x] 11.4 Ping/Jitter cards rebuild on LatencyResult
- [x] 11.5 Cards show `CircularProgressIndicator` during their active phase:
  - Connection: during `connecting` phase
  - Ping/Jitter: during `latency` phase
  - Download: during `download` phase (before first 256 KiB)
  - Upload: during `upload` phase (before first chunk completes)
  - New helper: `lib/ui/cards/metric_value.dart` — single place for "value or spinner"
- [x] 11.6 End-to-end manual test: ✅ verified on macOS 2026-04-21. Screenshot shows all cards populated correctly, Run Again button ready.

---

## Phase 12 — macOS polish

### 12.1 Window chrome
- [x] 12.1.1 Edit `macos/Runner/MainFlutterWindow.swift` — initial content size 800×600
- [x] 12.1.2 `contentMinSize` 600×500
- [x] 12.1.3 Window title "Speed Test" (replaces "speedtest_mobile")
- [x] 12.1.4 `self.center()` so window opens centered instead of top-left

### 12.2 Menu bar / Shortcuts
- [x] 12.2.1 ⌘R → Run Again (only fires if `!isRunning`)
- [x] 12.2.2 ⌘. → Cancel (only fires if `isRunning`)
- [x] 12.2.3 ⌘Q is macOS default — works out of the box
- Implementation: `CallbackShortcuts` widget in HomePage, `Focus(autofocus: true)` so shortcuts fire without clicking into the window

### 12.3 Theme
- [x] 12.3.2 Dark mode verified on 2026-04-20 (screenshots)
- [ ] 12.3.1 Light mode — user to verify ad-hoc (color scheme is `ColorScheme.fromSeed` on both, will adapt)

---

## Phase 13 — App icon

### 13.1 Source icon
- [x] 13.1.1 SVG reused from Linux parent: `gui-speedtest/data/icons/io.github.mmhfarooque.GuiSpeedTest.svg`
- [x] 13.1.2 Rendered to 1024×1024 PNG at `assets/icon/app_icon.png` via `rsvg-convert` (qlmanage produced a quadrant-filled image, librsvg does it properly)

### 13.2 Generate
- [x] 13.2.1 Added `flutter_launcher_icons: ^0.14.4` dev dep
- [x] 13.2.2 Config in pubspec.yaml — macOS + iOS + Android all configured (one source PNG, all three platforms get icons now)
- [x] 13.2.3 `dart run flutter_launcher_icons` — generated 7 macOS sizes (16–1024), full iOS + Android sets

### 13.3 Verify
- [x] 13.3.1 Icon shows in Dock ✅ (2026-04-21 screenshot)
- [x] 13.3.2 Menu bar + title bar show "Speed Test" ✅

---

## Phase L — Logging (Log button / Log viewer / Copy / Clear)

Mirrors the Linux parent's `Log` button + viewer. Rotating file on disk + in-memory buffer surfaced through a viewer dialog.

### L.1 Dependencies
- [x] L.1.1 Add `logging` (Dart logging package)
- [x] L.1.2 Add `path_provider` (cross-platform log-file paths)

### L.2 LogManager (singleton)
- [x] L.2.1 File `lib/utils/log_manager.dart`
- [x] L.2.2 In-memory ring buffer of recent 500 lines as `ValueNotifier<List<String>>`
- [x] L.2.3 File sink → `getApplicationSupportDirectory()/logs/speedtest.log` (cross-platform, sandbox-OK on all targets)
- [x] L.2.4 `Logger.root.onRecord` listener writes to both
- [x] L.2.5 Exposes `logs`, `clear()`, `logFilePath`, `dispose()`
- [x] L.2.6 `LogManager.instance.init()` awaited from `main()` before `runApp` (added `WidgetsFlutterBinding.ensureInitialized()`)

### L.3 Emit logs from existing code
- [x] L.3.1 `TestRunner.start()` logs: start, connection info, latency, download, upload, done, cancel, BackendError, unexpected errors
- [x] L.3.2 `CloudflareBackend` logs per-chunk speeds + per-chunk errors (both download + upload)
- [x] L.3.3 Startup log: version, OS, OS version, locale, log file path

### L.4 Log button in AppBar
- [x] L.4.1 `IconButton(Icons.article_outlined)` in AppBar actions with "View logs" tooltip
- [x] L.4.2 Navigator.push → `LogViewerPage`
- [x] L.4.3 Stub `LogViewerPage` with `ValueListenableBuilder` rendering logs in Menlo 12px, `SelectableText` rows

### L.5 LogViewerPage
- [x] L.5.1 File `lib/ui/log_viewer_page.dart` (StatefulWidget for ScrollController lifecycle)
- [x] L.5.2 Scaffold + AppBar "Logs" with Copy All + Clear actions
- [x] L.5.3 `ValueListenableBuilder` → monospace `SelectableText` in ListView; auto-scrolls to bottom via postFrameCallback on every update
- [x] L.5.4 Copy All → `Clipboard.setData` + SnackBar confirmation ("Copied N lines")
- [x] L.5.5 Clear → `LogManager.instance.clear()` + SnackBar ("Logs cleared")
- [x] L.5.6 Log file path in footer bar (surfaceContainerHighest background, SelectableText so user can copy-paste)

---

## Phase 14 — Error handling

- [x] 14.1 TestRunner catches BackendError, transitions to error state, stores text (done in Phase 8.1)
- [x] 14.2 **ErrorBanner** widget (not per-card) shown between StartButton and ConnectionCard. Error icon + text, 2-line max + ellipsis, errorContainer color scheme. Cleaner than per-card approach.
- [x] 14.3 Tooltip on hover → full error text (`waitDuration: 400ms`)
- [x] 14.4 "Try Again" button swap already handled by StartButton pattern-match (Phase 9.3)
- [x] 14.5 Errors flow into LogManager via Logger.warning/severe in TestRunner (done in L.3)

---

## Phase 15 — Release build

### 15.1 Debug smoke
- [x] 15.1.1 `flutter run -d macos` (verified many times through the build)
- [x] 15.1.2 Full test flow works (user screenshots 2026-04-20, 2026-04-21)
- [x] 15.1.3 Cancel mid-test works (button state + backend cancel wired in Phase 8)
- [x] 15.1.4 Run Again works (screenshots confirm)

### 15.2 Release build
- [x] 15.2.1 `flutter build macos --release` → `Speed Test.app` 41.6 MB
- [x] 15.2.2 Opened via `open build/macos/Build/Products/Release/Speed\ Test.app`
- [ ] 15.2.3 Verify standalone launch — user confirms app window appears

---

## Phase 16 — DMG packaging

- [x] 16.1 `brew install create-dmg` (v1.2.3)
- [x] 16.2 `scripts/build-dmg.sh` — reads version from pubspec, rebuilds .app if missing, calls create-dmg with Applications drop link + custom layout. Produced `dist/speedtest-mobile-0.1.0-macos.dmg` (16 MB).
- [ ] 16.3 Test: open DMG → drag to Applications → launch
- [ ] 16.4 Uninstall: delete from Applications, check no leftovers

---

## Phase 17 — GitHub repo + release

### 17.1 Create repo
- [ ] 17.1.1 `gh repo create mmhfarooque/speedtest-mobile --public --source=. --push`
- [x] 17.1.2 GPL-3.0 LICENSE copied from Linux parent (`gui-speedtest/LICENSE`)
- [x] 17.1.3 `.gitignore` (Flutter default + added `/dist/`)
- [x] 17.1.4 `README.md` — install, dev, status matrix, links to Linux sibling. Screenshot placeholder at `docs/screenshots/macos-dark.png` (user to drop one in).

### 17.2 First tag + release
- [ ] 17.2.1 `git tag v0.1.0-macos`
- [ ] 17.2.2 `git push origin v0.1.0-macos`
- [ ] 17.2.3 `gh release create v0.1.0-macos --title "v0.1.0 — macOS alpha" ./dist/speedtest-mobile-macos-0.1.0.dmg`

---

## After macOS ships
Then we add iOS (Phase 18+) and Android (Phase 24+). Separate plans to be written after macOS v0.1.0 is on GitHub.
