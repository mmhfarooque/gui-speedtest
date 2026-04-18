"""Ookla Speedtest backend.

Wraps the official `speedtest` CLI binary from Ookla. Download it from
https://www.speedtest.net/apps/cli — they publish .deb, .rpm, and tarballs.

Unlike HTTP-based backends, Ookla runs ping + download + upload in a single
CLI invocation. We cache the parsed JSON result so subsequent calls across
connection_info/test_latency/test_download/test_upload all return from the
same run.

First run needs licence acceptance — passed automatically via
`--accept-license --accept-gdpr`.

Supports cancellation: `cancel()` terminates an in-flight subprocess. The
GUI calls this from the window-close handler so we don't orphan the child.
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
        self._cache: dict | None = None
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    @classmethod
    def available(cls) -> bool:
        return shutil.which(BINARY) is not None

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

    def _run_once(self) -> dict:
        if self._cache is not None:
            return self._cache

        # Hold the lock only across Popen + self._proc assignment so cancel()
        # has a definite handle to terminate. communicate() runs unlocked so
        # cancel() can grab the lock and signal the child mid-test.
        try:
            proc = subprocess.Popen(
                [
                    BINARY,
                    "--format=json",
                    "--accept-license",
                    "--accept-gdpr",
                    "--progress=no",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as e:
            raise BackendError(f"speedtest binary not found: {e}") from e

        with self._lock:
            self._proc = proc

        stdout = ""
        stderr = ""
        try:
            try:
                stdout, stderr = proc.communicate(timeout=TIMEOUT_S)
            except subprocess.TimeoutExpired as e:
                proc.kill()
                # Drain pipes so the OS can reap the child — communicate()
                # post-kill is the supported pattern; ignore its output.
                try:
                    proc.communicate(timeout=5)
                except (subprocess.TimeoutExpired, OSError):
                    pass
                raise BackendError(f"Ookla CLI timed out after {TIMEOUT_S}s") from e
        finally:
            with self._lock:
                self._proc = None

        rc = proc.returncode
        if rc is None:
            raise BackendError("Ookla CLI was cancelled")
        # SIGTERM from cancel() yields a negative returncode (-15 on POSIX).
        if rc < 0:
            raise BackendError(f"Ookla CLI was cancelled (signal {-rc})")
        if rc != 0:
            raise BackendError(
                f"Ookla CLI failed (exit {rc}): {(stderr or '').strip()[:300]}"
            )
        try:
            self._cache = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise BackendError(f"Could not parse Ookla JSON output: {e}") from e
        return self._cache

    def connection_info(self) -> ConnectionInfo:
        data = self._run_once()
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
        data = self._run_once()
        ping = data.get("ping", {}) or {}
        if not ping:
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

    def _emit(
        self, callback: ProgressCallback, event: str, speed: float
    ) -> None:
        if callback:
            callback(
                event,
                {"label": "ookla", "speed_mbps": speed, "current": 1, "total": 1},
            )

    def test_download(self, callback: ProgressCallback = None) -> SpeedResult:
        data = self._run_once()
        bw = (data.get("download") or {}).get("bandwidth", 0)
        speed = (bw * 8) / 1_000_000
        if speed <= 0:
            raise BackendError("Ookla reported no download bandwidth")
        self._emit(callback, "download_chunk", speed)
        return SpeedResult(speed_mbps=speed, samples=[speed])

    def test_upload(self, callback: ProgressCallback = None) -> SpeedResult:
        data = self._run_once()
        bw = (data.get("upload") or {}).get("bandwidth", 0)
        speed = (bw * 8) / 1_000_000
        if speed <= 0:
            raise BackendError("Ookla reported no upload bandwidth")
        self._emit(callback, "upload_chunk", speed)
        return SpeedResult(speed_mbps=speed, samples=[speed])
