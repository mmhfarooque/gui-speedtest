"""Abstract base class + shared helpers for speed test backends.

Provides:
- Dataclasses: ConnectionInfo, LatencyResult, SpeedResult
- SpeedTestBackend ABC
- http_get / run_chunks / measure_latency — shared HTTP machinery every
  HTTP-based backend would otherwise duplicate
- BROWSER_UA — single source of truth for the spoofed user agent
"""
from __future__ import annotations

import logging
import ssl
import statistics
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

ProgressCallback = Optional[Callable[[str, dict], None]]

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Single source of truth for "this is a recoverable network failure" — used
# in every backend's HTTP except clauses so SSL handshake errors and connection
# resets don't bypass our BackendError contract.
NETWORK_EXCEPTIONS: tuple[type[BaseException], ...] = (
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,
    ssl.SSLError,
)

logger = logging.getLogger("gui_speedtest")


def safe_decode(data: bytes) -> str:
    """Decode bytes to UTF-8 text, replacing un-decodable bytes instead of
    raising. Used for response bodies where a stray malformed byte
    shouldn't take down the whole speed test."""
    return data.decode("utf-8", errors="replace")


def format_speed(mbps: float) -> str:
    """Render a Mbps value with the right unit (Mbps under 1 Gbps, Gbps
    above). Single source of truth so CLI + GUI agree on rounding."""
    if mbps >= 1000:
        return f"{mbps / 1000:.2f} Gbps"
    return f"{mbps:.2f} Mbps"


class BackendError(Exception):
    """Raised when a backend cannot complete a test."""


@dataclass
class ConnectionInfo:
    ip: str = "Unknown"
    isp: str = "Unknown"
    city: str = ""
    region: str = "Unknown"
    country: str = ""
    server: str = ""

    @property
    def location(self) -> str:
        parts = [p for p in (self.city, self.region, self.country) if p and p != "Unknown"]
        return ", ".join(parts) if parts else "Unknown"


@dataclass
class LatencyResult:
    avg: float = 0.0
    min: float = 0.0
    max: float = 0.0
    jitter: float = 0.0
    samples: int = 0
    failed: bool = False

    @classmethod
    def from_samples(cls, times: list[float]) -> "LatencyResult":
        if not times:
            return cls(failed=True)
        return cls(
            avg=statistics.mean(times),
            min=min(times),
            max=max(times),
            jitter=statistics.stdev(times) if len(times) > 1 else 0.0,
            samples=len(times),
        )


@dataclass
class SpeedResult:
    speed_mbps: float = 0.0
    samples: list[float] = field(default_factory=list)

    @classmethod
    def top_half(cls, results: list[float]) -> "SpeedResult":
        """Average the *top half* of samples, discarding slow warmups.

        For 4 samples this averages the top 2. An odd count rounds up so
        e.g. 5 samples averages the top 3.
        """
        if not results:
            return cls()
        sorted_desc = sorted(results, reverse=True)
        cut = max(1, (len(sorted_desc) + 1) // 2)
        return cls(speed_mbps=statistics.mean(sorted_desc[:cut]), samples=results)


def ssl_context() -> ssl.SSLContext:
    """Return Python's default-hardened SSL context. Centralised so every
    backend uses the same trust store + protocol policy — auditing TLS
    behaviour is one grep instead of one per backend."""
    return ssl.create_default_context()


def http_get(url: str, timeout: int = 10, headers: dict | None = None) -> bytes:
    """GET a URL with the browser UA. Raises on HTTP/network error."""
    merged = {"User-Agent": BROWSER_UA}
    if headers:
        merged.update(headers)
    req = urllib.request.Request(url, headers=merged)
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
        return resp.read()


# --- Shared latency + chunk loop -------------------------------------------

RequestFactory = Callable[[], urllib.request.Request]


def measure_latency(
    req_factory: RequestFactory,
    samples: int,
    callback: ProgressCallback = None,
    timeout: int = 5,
) -> LatencyResult:
    """Round-trip time measurement — one request per sample, read to EOF."""
    times: list[float] = []
    for i in range(samples):
        try:
            req = req_factory()
            start = time.perf_counter()
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
                resp.read()
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            if callback:
                callback(
                    "latency_sample",
                    {"current": i + 1, "total": samples, "value_ms": elapsed},
                )
        except NETWORK_EXCEPTIONS as e:
            logger.debug("Latency sample %d failed: %s", i + 1, e)
    return LatencyResult.from_samples(times)


@dataclass
class Chunk:
    """One transfer unit. request_factory returns a fresh Request (so
    upload bodies can be regenerated on retry). size_bytes is the
    authoritative byte count for upload; for downloads leave at 0 and
    we'll use len(response body)."""
    request_factory: RequestFactory
    label: str
    size_bytes: int = 0


def run_chunks(
    chunks: Iterable[Chunk],
    event_name: str,
    callback: ProgressCallback = None,
    timeout: int = 30,
) -> SpeedResult:
    """Run each chunk, measure throughput, aggregate via top_half.

    Raises BackendError if no chunk succeeded — the standardised error
    contract for download/upload test methods.
    """
    chunks_list = list(chunks)
    results: list[float] = []
    for i, chunk in enumerate(chunks_list, 1):
        try:
            req = chunk.request_factory()
            start = time.perf_counter()
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
                body = resp.read()
            elapsed = time.perf_counter() - start
            if elapsed <= 0:
                continue
            n = chunk.size_bytes if chunk.size_bytes > 0 else len(body)
            speed = (n * 8) / (elapsed * 1_000_000)
            results.append(speed)
            if callback:
                callback(
                    event_name,
                    {
                        "label": chunk.label,
                        "speed_mbps": speed,
                        "current": i,
                        "total": len(chunks_list),
                    },
                )
        except NETWORK_EXCEPTIONS as e:
            logger.debug("%s chunk %r failed: %s", event_name, chunk.label, e)
            if callback:
                callback(event_name + "_error", {"label": chunk.label, "error": str(e)})
    if not results:
        raise BackendError(f"all {event_name.replace('_chunk', '')} attempts failed")
    return SpeedResult.top_half(results)


class SpeedTestBackend(ABC):
    """Contract for speed test providers. Each concrete backend implements
    connection_info + latency/download/upload. Download/upload MUST raise
    BackendError when they cannot produce a number (never return 0.0)."""

    name: str = "base"
    display_name: str = "Base"

    @classmethod
    def available(cls) -> bool:
        """Return True if this backend can run on this system."""
        return True

    @abstractmethod
    def connection_info(self) -> ConnectionInfo:
        """Detect client IP, ISP, location, and which server we'll hit."""

    @abstractmethod
    def test_latency(
        self, samples: int = 10, callback: ProgressCallback = None
    ) -> LatencyResult:
        """Measure round-trip latency."""

    @abstractmethod
    def test_download(self, callback: ProgressCallback = None) -> SpeedResult:
        """Measure download throughput. Raises BackendError on total failure."""

    @abstractmethod
    def test_upload(self, callback: ProgressCallback = None) -> SpeedResult:
        """Measure upload throughput. Raises BackendError on total failure."""

    def cancel(self) -> None:
        """Abort any in-flight test. Default is a no-op; backends with
        cancellable subprocesses or long-lived sockets override this."""
        return None
