"""OVH speed test backend.

Download-only. OVH publishes two HTTP speedtest mirrors:
  - proof.ovh.net (Gravelines, France) — EU
  - proof-bhs.ovh.net (Beauharnois, Canada) — North America

On first use we probe both with a HEAD request and pick the one with
the lowest latency. No Asian mirror exists, so users in AS/OC will
still see high latency — that's OVH's geography, not ours to fix.

No upload endpoint is available — test_upload raises BackendError.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from .base import (
    BROWSER_UA,
    NETWORK_EXCEPTIONS,
    BackendError,
    Chunk,
    ConnectionInfo,
    LatencyResult,
    ProgressCallback,
    SpeedResult,
    SpeedTestBackend,
    http_get,
    logger,
    measure_latency,
    run_chunks,
    safe_decode,
    ssl_context,
)

MIRRORS = [
    # (host, human-readable location)
    ("proof.ovh.net", "Gravelines (FR)"),
    ("proof-bhs.ovh.net", "Beauharnois (CA)"),
]
IPIFY_URL = "https://api.ipify.org?format=json"
IPWHO_URL = "https://ipwho.is/"

DOWN_FILES = [
    ("1Mb.dat", "1 MB"),
    ("10Mb.dat", "10 MB"),
]


def _probe_rtt(host: str, timeout: float = 3.0) -> float:
    """HEAD /files/1Mb.dat and return RTT in seconds. Returns inf on failure."""
    url = f"https://{host}/files/1Mb.dat"
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA}, method="HEAD")
    try:
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
            resp.read()
        return time.perf_counter() - start
    except (*NETWORK_EXCEPTIONS,) as e:
        logger.debug("OVH mirror probe %s failed: %s", host, e)
        return float("inf")


class OvhBackend(SpeedTestBackend):
    name = "ovh"
    display_name = "OVH (download-only)"

    def __init__(self) -> None:
        # Resolved lazily on first connection_info()/latency/download call.
        self._host: str | None = None
        self._location: str = ""

    def _pick_mirror(self) -> tuple[str, str]:
        """Return (host, location) of the fastest mirror, cached after
        first call. Falls back to the first entry if all probes fail."""
        if self._host:
            return self._host, self._location
        best_rtt = float("inf")
        best = MIRRORS[0]
        for host, location in MIRRORS:
            rtt = _probe_rtt(host)
            logger.debug("OVH mirror %s RTT=%.3fs", host, rtt)
            if rtt < best_rtt:
                best_rtt, best = rtt, (host, location)
        self._host, self._location = best
        logger.info("OVH picked mirror: %s (%.0f ms)", self._host, best_rtt * 1000)
        return self._host, self._location

    def _file_url(self, fragment: str) -> str:
        host, _ = self._pick_mirror()
        return f"https://{host}/files/{fragment}"

    def connection_info(self) -> ConnectionInfo:
        try:
            ip = json.loads(safe_decode(http_get(IPIFY_URL, timeout=5))).get("ip", "Unknown")
        except (*NETWORK_EXCEPTIONS, json.JSONDecodeError):
            ip = "Unknown"

        # OVH itself doesn't expose a client-info endpoint, so enrich with
        # ipwho.is — same fallback Cloudflare uses. Without this, the GUI
        # shows "Location: Unknown" for OVH runs even when we know the IP.
        isp, city, region, country = "Unknown", "", "Unknown", ""
        if ip != "Unknown":
            safe_ip = urllib.parse.quote(ip, safe=":")
            try:
                data = json.loads(safe_decode(http_get(IPWHO_URL + safe_ip, timeout=5)))
                if data.get("success", True):
                    conn = data.get("connection", {}) or {}
                    isp = conn.get("isp") or conn.get("org") or "Unknown"
                    city = data.get("city", "")
                    region = data.get("region", "Unknown")
                    country = data.get("country", "")
            except (*NETWORK_EXCEPTIONS, json.JSONDecodeError):
                pass

        _, location = self._pick_mirror()
        return ConnectionInfo(
            ip=ip,
            isp=isp,
            city=city,
            region=region,
            country=country,
            server=f"OVH {location}",
        )

    def test_latency(
        self, samples: int = 10, callback: ProgressCallback = None
    ) -> LatencyResult:
        url = self._file_url(DOWN_FILES[0][0])

        def factory() -> urllib.request.Request:
            return urllib.request.Request(
                url, headers={"User-Agent": BROWSER_UA}, method="HEAD"
            )

        return measure_latency(factory, samples, callback, backend=self)

    def test_download(self, callback: ProgressCallback = None) -> SpeedResult:
        def make(fragment: str) -> urllib.request.Request:
            return urllib.request.Request(
                self._file_url(fragment), headers={"User-Agent": BROWSER_UA}
            )

        chunks = [
            Chunk(request_factory=lambda f=f: make(f), label=label)
            for f, label in DOWN_FILES
        ]
        return run_chunks(chunks, "download_chunk", callback, timeout=60, backend=self)

    def test_upload(self, callback: ProgressCallback = None) -> SpeedResult:
        raise BackendError("OVH does not offer an upload endpoint")
