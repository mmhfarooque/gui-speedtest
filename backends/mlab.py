"""M-Lab NDT7 backend.

Measurement Lab — free, academic-backed speed test platform. Protocol is
ndt7 over WebSocket (spec: https://github.com/m-lab/ndt-server).

Workflow:
  1. Query locate.measurementlab.net for the nearest M-Lab server (returns
     signed URLs for download + upload).
  2. Connect WebSocket with subprotocol `net.measurementlab.ndt.v7`.
  3. Download: server streams binary frames for ~10s — count received bytes.
  4. Upload: client streams binary frames for ~10s — count sent bytes.

**Caveat on upload measurement:** our counter is incremented when bytes are
handed to the socket send buffer, not when they are ACK'd on the wire. This
can overshoot real throughput by 1-2 seconds of socket buffer at the tail of
the test. The ndt7 spec has the client read the server's measurement frames
for the authoritative number; that's a v1.1 improvement. For typical
residential links the discrepancy is small.

Requires the `websocket-client` package:
  Debian/Ubuntu:  apt install python3-websocket
  Fedora:         dnf install python3-websocket-client
  pip:            pip install websocket-client
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

from .base import (
    BROWSER_UA,
    NETWORK_EXCEPTIONS,
    BackendError,
    ConnectionInfo,
    LatencyResult,
    ProgressCallback,
    SpeedResult,
    SpeedTestBackend,
    http_get,
    logger,
    measure_latency,
    safe_decode,
    ssl_context,
)

try:
    import websocket  # type: ignore

    _HAS_WS = True
except ImportError:
    _HAS_WS = False

LOCATE_URL = "https://locate.measurementlab.net/v2/nearest/ndt/ndt7"
SUBPROTOCOL = "net.measurementlab.ndt.v7"
TEST_DURATION_S = 10
CHUNK_SIZE = 8192  # 8 KiB per send — matches the ndt7 reference client default
# Throttle progress callbacks during upload — emit roughly once per MiB so the
# GUI doesn't drown in updates on a fast link (60 Mbps ≈ 7 MB/s ≈ 7 calls/s).
PROGRESS_EVERY_BYTES = CHUNK_SIZE * 128
# Cap WebSocket frame payload at 16 MiB — ndt7 servers send small chunks
# (8-64 KiB typical). A per-frame limit prevents a malicious or misbehaving
# server from driving the process OOM with a single enormous frame.
MAX_FRAME_BYTES = 16 * 1024 * 1024

DOWNLOAD_KEY = "wss:///ndt/v7/download"
UPLOAD_KEY = "wss:///ndt/v7/upload"


class MLabBackend(SpeedTestBackend):
    name = "mlab"
    display_name = "M-Lab NDT7"

    def __init__(self) -> None:
        self._locate: dict | None = None

    @classmethod
    def available(cls) -> bool:
        return _HAS_WS

    def _locate_server(self) -> dict:
        if self._locate is not None:
            return self._locate
        try:
            data = json.loads(safe_decode(http_get(LOCATE_URL, timeout=10)))
        except (*NETWORK_EXCEPTIONS, json.JSONDecodeError) as e:
            raise BackendError(f"M-Lab locate service unreachable: {e}") from e

        results = data.get("results") or []
        if not results:
            raise BackendError("M-Lab returned no nearby servers")
        self._locate = results[0]
        return self._locate

    def _ws_url(self, key: str) -> str:
        """Return a validated wss:// URL for the requested ndt7 key.

        The locate service is HTTPS and signed, but the URLs come back as
        plain strings. Refusing anything other than wss:// keeps a
        compromised/proxied locate response from downgrading us to plain
        ws:// (where token + payload would travel in the clear)."""
        server = self._locate_server()
        url = (server.get("urls") or {}).get(key, "")
        if not url:
            raise BackendError(f"M-Lab locate response missing URL for {key}")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "wss" or not parsed.netloc:
            raise BackendError(
                f"M-Lab returned non-wss URL for {key}: {parsed.scheme!r}"
            )
        return url

    def connection_info(self) -> ConnectionInfo:
        try:
            server = self._locate_server()
        except BackendError:
            return ConnectionInfo(server="M-Lab (locate failed)")
        machine = server.get("machine", "unknown")
        location = server.get("location", {}) or {}
        return ConnectionInfo(
            city=location.get("city", ""),
            country=location.get("country", ""),
            server=f"M-Lab {machine}",
        )

    def test_latency(
        self, samples: int = 10, callback: ProgressCallback = None
    ) -> LatencyResult:
        """HTTPS HEAD to the M-Lab host as a proxy for RTT."""
        try:
            ws_url = self._ws_url(DOWNLOAD_KEY)
        except BackendError:
            return LatencyResult(failed=True)
        https_url = ws_url.replace("wss://", "https://", 1)

        def factory() -> urllib.request.Request:
            return urllib.request.Request(
                https_url, headers={"User-Agent": BROWSER_UA}, method="HEAD"
            )

        return measure_latency(factory, samples, callback)

    def _open_ws(self, url: str) -> "websocket.WebSocket":
        """Open a WebSocket connection or raise BackendError. Centralises
        the error contract so callers don't need to think about the
        websocket library's exception hierarchy."""
        try:
            return websocket.create_connection(
                url,
                subprotocols=[SUBPROTOCOL],
                header=[f"User-Agent: {BROWSER_UA}"],
                timeout=TEST_DURATION_S + 5,
                sslopt={"context": ssl_context()},
                max_size=MAX_FRAME_BYTES,
            )
        except (websocket.WebSocketException, OSError) as e:
            raise BackendError(f"M-Lab WebSocket connection failed: {e}") from e

    def test_download(self, callback: ProgressCallback = None) -> SpeedResult:
        if not _HAS_WS:
            raise BackendError("websocket-client package required for M-Lab")
        url = self._ws_url(DOWNLOAD_KEY)
        ws = self._open_ws(url)
        total_bytes = 0
        elapsed = 0.0
        try:
            start = time.perf_counter()
            while (elapsed := time.perf_counter() - start) < TEST_DURATION_S:
                try:
                    _opcode, frame = ws.recv_data(control_frame=False)
                except (websocket.WebSocketException, OSError) as e:
                    # Connection closed mid-stream is normal at end of test;
                    # other socket errors are still recoverable as long as
                    # we received some data — drop out of the loop and
                    # report on what we got.
                    logger.debug("M-Lab download ws recv ended: %s", e)
                    break
                total_bytes += len(frame)
                if callback and elapsed > 0:
                    speed = (total_bytes * 8) / (elapsed * 1_000_000)
                    callback(
                        "download_chunk",
                        {
                            "label": f"{elapsed:.1f}s",
                            "speed_mbps": speed,
                            "current": min(int(elapsed), TEST_DURATION_S),
                            "total": TEST_DURATION_S,
                        },
                    )
        finally:
            try:
                ws.close()
            except (websocket.WebSocketException, OSError) as e:
                logger.debug("M-Lab download ws close failed: %s", e)

        if elapsed <= 0 or total_bytes == 0:
            raise BackendError("M-Lab download received no data")
        speed_mbps = (total_bytes * 8) / (elapsed * 1_000_000)
        return SpeedResult(speed_mbps=speed_mbps, samples=[speed_mbps])

    def test_upload(self, callback: ProgressCallback = None) -> SpeedResult:
        if not _HAS_WS:
            raise BackendError("websocket-client package required for M-Lab")
        url = self._ws_url(UPLOAD_KEY)
        ws = self._open_ws(url)
        total_bytes = 0
        elapsed = 0.0
        payload = os.urandom(CHUNK_SIZE)
        try:
            start = time.perf_counter()
            while (elapsed := time.perf_counter() - start) < TEST_DURATION_S:
                try:
                    ws.send_binary(payload)
                except (websocket.WebSocketException, OSError) as e:
                    logger.debug("M-Lab upload ws send ended: %s", e)
                    break
                total_bytes += CHUNK_SIZE
                if callback and total_bytes % PROGRESS_EVERY_BYTES == 0 and elapsed > 0:
                    speed = (total_bytes * 8) / (elapsed * 1_000_000)
                    callback(
                        "upload_chunk",
                        {
                            "label": f"{elapsed:.1f}s",
                            "speed_mbps": speed,
                            "current": min(int(elapsed), TEST_DURATION_S),
                            "total": TEST_DURATION_S,
                        },
                    )
        finally:
            try:
                ws.close()
            except (websocket.WebSocketException, OSError) as e:
                logger.debug("M-Lab upload ws close failed: %s", e)

        if elapsed <= 0 or total_bytes == 0:
            raise BackendError("M-Lab upload sent no data")
        speed_mbps = (total_bytes * 8) / (elapsed * 1_000_000)
        return SpeedResult(speed_mbps=speed_mbps, samples=[speed_mbps])
