"""Ookla Speedtest backend.

Wraps the official `speedtest` CLI binary from Ookla. Download it from
https://www.speedtest.net/apps/cli — they publish .deb, .rpm, and tarballs.

Unlike HTTP-based backends, Ookla runs ping + download + upload in a single
CLI invocation. We launch the CLI once with `--progress=yes --format=json`
and stream newline-delimited JSON events from stdout in a background
reader thread. Each event carries the current phase (testStart / ping /
download / upload / result) plus live bandwidth/latency numbers, so the
GUI gets continuous feedback the same way the HTTP backends do.

First run needs licence acceptance — passed automatically via
`--accept-license --accept-gdpr`.

Supports cancellation: `cancel()` terminates the in-flight subprocess.
The GUI calls this from the window-close handler so we don't orphan the
child.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading

from .base import (
    BackendError,
    ConnectionInfo,
    LatencyResult,
    ProgressCallback,
    SpeedResult,
    SpeedTestBackend,
    logger,
)

BINARY = "speedtest"
TIMEOUT_S = 180


class OoklaBackend(SpeedTestBackend):
    name = "ookla"
    display_name = "Ookla Speedtest"

    def __init__(self) -> None:
        self._cache: dict | None = None  # final "result" event payload
        self._start_data: dict | None = None  # "testStart" event payload
        self._error: str | None = None
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        # One Event per phase so per-phase methods can block until their
        # slice of the CLI run has finished.
        self._phase_events: dict[str, threading.Event] = {
            "start": threading.Event(),
            "ping": threading.Event(),
            "download": threading.Event(),
            "upload": threading.Event(),
        }
        # Callbacks registered by test_latency/test_download/test_upload.
        # Buffered events replay on registration so a caller who registers
        # late still gets every sample in order.
        self._phase_callbacks: dict[str, ProgressCallback] = {}
        self._phase_buffered: dict[str, list[dict]] = {
            "ping": [],
            "download": [],
            "upload": [],
        }
        # The most recent event per phase. Ookla's jsonl events carry
        # running aggregates (latency/jitter for ping, cumulative bandwidth
        # for download/upload) that converge to the final value by the time
        # the phase ends — so the last event seen before the next phase
        # starts is the phase's final aggregate. We use these as the data
        # source for test_latency/test_download, which unblock before the
        # terminal "result" event has arrived.
        self._latest_ev: dict[str, dict | None] = {
            "ping": None,
            "download": None,
            "upload": None,
        }
        self._ping_counter = 0

    @classmethod
    def available(cls) -> bool:
        """True only if the `speedtest` binary on PATH is Ookla's official one.

        Ubuntu/Debian ship a separate `speedtest-cli` package (sivel/speedtest-cli,
        a Python wrapper) that is sometimes symlinked as `speedtest` and
        accepts completely different arguments. Running our Ookla argv against
        it produces empty JSON + confused error messages. Verify the identity
        by parsing `--version` output for the "Ookla" string.
        """
        if not shutil.which(BINARY):
            return False
        try:
            out = subprocess.run(
                [BINARY, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return "Ookla" in (out.stdout + out.stderr)
        except (OSError, subprocess.TimeoutExpired):
            return False

    def cancel(self) -> None:
        """Terminate any running speedtest subprocess. Safe to call repeatedly."""
        with self._lock:
            proc = self._proc
        if proc and proc.poll() is None:
            logger.info("Cancelling Ookla subprocess (pid=%s)", proc.pid)
            try:
                proc.terminate()
            except OSError as e:
                logger.debug("Ookla terminate failed: %s", e)

    def _ensure_started(self) -> None:
        """Spawn the CLI + reader thread. Resets per-run state on subsequent
        calls so Run Again triggers a fresh speedtest — the other backends
        are naturally re-runnable because each phase method spins up a new
        HTTP/WS connection, but the Ookla CLI bundles all phases into one
        invocation and we have to reset the cache ourselves."""
        with self._lock:
            in_flight = (
                self._thread is not None
                and self._thread.is_alive()
                and self._cache is None
                and self._error is None
            )
            if in_flight:
                return
            # Fresh start: clear everything from any previous run.
            self._cache = None
            self._start_data = None
            self._error = None
            self._proc = None
            self._ping_counter = 0
            self._phase_callbacks = {}
            self._phase_buffered = {"ping": [], "download": [], "upload": []}
            self._latest_ev = {"ping": None, "download": None, "upload": None}
            for ev in self._phase_events.values():
                ev.clear()
            self._thread = threading.Thread(
                target=self._run_streaming, daemon=True, name="ookla-reader"
            )
            self._thread.start()

    def _run_streaming(self) -> None:
        """Spawn `speedtest` with JSON progress streaming and dispatch events
        to per-phase callbacks as they arrive. Runs in a daemon thread."""
        try:
            proc = subprocess.Popen(
                [
                    BINARY,
                    # jsonl (JSON Lines) emits one complete JSON object per
                    # line throughout the run — testStart, many ping events,
                    # many download events, many upload events, then result.
                    # Plain --format=json would emit a single blob only at
                    # the end, which is exactly what caused the "silent then
                    # sudden result" behaviour we're fixing here.
                    "--format=jsonl",
                    "--progress=yes",
                    "--accept-license",
                    "--accept-gdpr",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # line-buffered so we get events as they flow
            )
        except FileNotFoundError as e:
            self._error = f"speedtest binary not found: {e}"
            self._signal_all()
            return

        with self._lock:
            self._proc = proc

        stderr_tail = ""
        try:
            # Drain stdout line-by-line; each line is a complete JSON event.
            for raw in proc.stdout:  # type: ignore[union-attr]
                line = raw.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    # Some lines (log messages, warnings) aren't JSON — skip.
                    logger.debug("Ookla: non-JSON line: %s", line[:200])
                    continue
                self._dispatch(ev)

            # stdout closed — drain stderr for an error hint if we failed.
            try:
                stderr_tail = (proc.stderr.read() or "")[-400:]  # type: ignore[union-attr]
            except OSError:
                stderr_tail = ""
        finally:
            try:
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                pass
            with self._lock:
                self._proc = None
            rc = proc.returncode
            # If we never got a "result" event, something went wrong — capture
            # a descriptive error so waiting callers see it instead of hanging.
            if self._cache is None and self._error is None:
                if rc is not None and rc < 0:
                    self._error = f"Ookla CLI was cancelled (signal {-rc})"
                elif rc and rc != 0:
                    self._error = (
                        f"Ookla CLI failed (exit {rc}): {stderr_tail.strip()[:300]}"
                    )
                else:
                    self._error = "Ookla CLI ended without a result"
            self._signal_all()

    def _signal_all(self) -> None:
        """Release every phase waiter. Called on completion, error, or cancel."""
        for ev in self._phase_events.values():
            ev.set()

    def _dispatch(self, ev: dict) -> None:
        ev_type = ev.get("type")
        logger.debug("ookla event: type=%s", ev_type)
        if ev_type == "testStart":
            self._start_data = ev
            self._phase_events["start"].set()
        elif ev_type == "ping":
            self._handle_phase_event("ping", ev)
        elif ev_type == "download":
            # Ping phase is finished as soon as download events start.
            if not self._phase_events["ping"].is_set():
                self._phase_events["ping"].set()
            self._handle_phase_event("download", ev)
        elif ev_type == "upload":
            if not self._phase_events["download"].is_set():
                self._phase_events["download"].set()
            self._handle_phase_event("upload", ev)
        elif ev_type == "result":
            self._cache = ev
            # All three phase events set — result is terminal.
            self._phase_events["ping"].set()
            self._phase_events["download"].set()
            self._phase_events["upload"].set()
        # log / unknown types: ignore silently.

    def _handle_phase_event(self, phase: str, ev: dict) -> None:
        """Fire registered callback or buffer if none yet registered.

        Also records this as the latest event for the phase so when the
        corresponding test_* method unblocks, it has the running-aggregate
        numbers ready — even if the terminal "result" event hasn't arrived.

        Holding the lock only long enough to snapshot the callback + flush
        state keeps the reader thread from blocking if the GUI callback is
        slow to schedule an idle_add."""
        self._latest_ev[phase] = ev
        with self._lock:
            cb = self._phase_callbacks.get(phase)
            if cb is None:
                self._phase_buffered.setdefault(phase, []).append(ev)
                return
        self._emit_phase_event(cb, phase, ev)

    def _emit_phase_event(
        self, callback: ProgressCallback, phase: str, ev: dict
    ) -> None:
        """Translate an Ookla JSON event into the SpeedTestBackend callback
        contract used by the GUI (latency_sample / download_chunk_progress /
        upload_chunk_progress)."""
        data = ev.get(phase, {}) or {}
        if phase == "ping":
            latency = float(data.get("latency", 0.0) or 0.0)
            if latency <= 0:
                return
            self._ping_counter += 1
            progress = float(data.get("progress", 0.0) or 0.0)
            # Ookla doesn't expose per-sample count — synthesise a
            # "N/M" indicator from the progress fraction so the GUI status
            # text ("Latency 3/10: 5 ms") still makes sense.
            total = 10
            current = max(1, min(total, int(round(progress * total)) or self._ping_counter))
            callback(
                "latency_sample",
                {"current": current, "total": total, "value_ms": latency},
            )
        else:
            bw = float(data.get("bandwidth", 0) or 0)
            speed = (bw * 8) / 1_000_000 if bw else 0.0
            if speed <= 0:
                return
            callback(
                f"{phase}_chunk_progress",
                {
                    "label": "ookla",
                    "speed_mbps": speed,
                    "current": 1,
                    "total": 1,
                },
            )

    def _register_and_replay(
        self, phase: str, callback: ProgressCallback
    ) -> None:
        """Register a callback for a phase and replay any buffered events."""
        with self._lock:
            buffered = list(self._phase_buffered.get(phase, []))
            self._phase_buffered[phase] = []
            self._phase_callbacks[phase] = callback
        for ev in buffered:
            self._emit_phase_event(callback, phase, ev)

    def _wait_for(self, phase: str) -> None:
        self._phase_events[phase].wait(timeout=TIMEOUT_S)
        if not self._phase_events[phase].is_set():
            raise BackendError(f"Ookla CLI timed out waiting for {phase} phase")
        if self._error:
            raise BackendError(self._error)

    def connection_info(self) -> ConnectionInfo:
        self._ensure_started()
        self._phase_events["start"].wait(timeout=TIMEOUT_S)
        if not self._phase_events["start"].is_set():
            raise BackendError("Ookla CLI timed out before emitting testStart")
        if self._error:
            raise BackendError(self._error)
        data = self._start_data or {}
        iface = data.get("interface", {}) or {}
        server = data.get("server", {}) or {}
        return ConnectionInfo(
            ip=iface.get("externalIp", "Unknown"),
            isp=data.get("isp", "Unknown"),
            city=server.get("location", ""),
            country=server.get("country", ""),
            server=f"{server.get('name', 'Ookla')} ({server.get('host', '')})".strip(),
        )

    def test_latency(
        self, samples: int = 10, callback: ProgressCallback = None
    ) -> LatencyResult:
        if callback:
            self._register_and_replay("ping", callback)
        self._wait_for("ping")
        # Prefer the terminal "result" event (has low/high quartiles) but
        # fall back to the last streaming ping event (which carries the
        # final running averages for latency + jitter).
        ev = self._cache if self._cache else self._latest_ev.get("ping")
        ping = (ev or {}).get("ping", {}) or {}
        if not ping or float(ping.get("latency", 0.0) or 0.0) <= 0:
            return LatencyResult(failed=True)
        return LatencyResult(
            avg=ping.get("latency", 0.0),
            min=ping.get("low", 0.0),
            max=ping.get("high", 0.0),
            jitter=ping.get("jitter", 0.0),
            # Ookla CLI aggregates ping samples internally and only exposes
            # the rolled-up stats above — the per-sample count isn't in the
            # JSON. Reporting 0 is "opaque", not "no samples were taken".
            samples=0,
        )

    def test_download(self, callback: ProgressCallback = None) -> SpeedResult:
        if callback:
            self._register_and_replay("download", callback)
        self._wait_for("download")
        ev = self._cache if self._cache else self._latest_ev.get("download")
        bw = ((ev or {}).get("download") or {}).get("bandwidth", 0)
        speed = (bw * 8) / 1_000_000
        if speed <= 0:
            raise BackendError("Ookla reported no download bandwidth")
        if callback:
            callback(
                "download_chunk",
                {"label": "ookla", "speed_mbps": speed, "current": 1, "total": 1},
            )
        return SpeedResult(speed_mbps=speed, samples=[speed])

    def test_upload(self, callback: ProgressCallback = None) -> SpeedResult:
        if callback:
            self._register_and_replay("upload", callback)
        self._wait_for("upload")
        ev = self._cache if self._cache else self._latest_ev.get("upload")
        bw = ((ev or {}).get("upload") or {}).get("bandwidth", 0)
        speed = (bw * 8) / 1_000_000
        if speed <= 0:
            raise BackendError("Ookla reported no upload bandwidth")
        if callback:
            callback(
                "upload_chunk",
                {"label": "ookla", "speed_mbps": speed, "current": 1, "total": 1},
            )
        return SpeedResult(speed_mbps=speed, samples=[speed])
