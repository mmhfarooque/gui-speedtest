"""OVH speed test backend.

Download-only. Uses OVH's public file server at proof.ovh.net (Gravelines, FR).
Best for European users; distant users will see latency-bound throughput.

No upload endpoint is available — test_upload raises BackendError.
"""
from __future__ import annotations

import json
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
    measure_latency,
    run_chunks,
    safe_decode,
)

FILE_URL = "https://proof.ovh.net/files/{}"
IPIFY_URL = "https://api.ipify.org?format=json"
IPWHO_URL = "https://ipwho.is/"

DOWN_FILES = [
    ("1Mb.dat", "1 MB"),
    ("10Mb.dat", "10 MB"),
]


class OvhBackend(SpeedTestBackend):
    name = "ovh"
    display_name = "OVH (download-only)"

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

        return ConnectionInfo(
            ip=ip,
            isp=isp,
            city=city,
            region=region,
            country=country,
            server="OVH Gravelines (FR)",
        )

    def test_latency(
        self, samples: int = 10, callback: ProgressCallback = None
    ) -> LatencyResult:
        url = FILE_URL.format(DOWN_FILES[0][0])

        def factory() -> urllib.request.Request:
            return urllib.request.Request(
                url, headers={"User-Agent": BROWSER_UA}, method="HEAD"
            )

        return measure_latency(factory, samples, callback, backend=self)

    def test_download(self, callback: ProgressCallback = None) -> SpeedResult:
        def make(fragment: str) -> urllib.request.Request:
            return urllib.request.Request(
                FILE_URL.format(fragment), headers={"User-Agent": BROWSER_UA}
            )

        chunks = [
            Chunk(request_factory=lambda f=f: make(f), label=label)
            for f, label in DOWN_FILES
        ]
        return run_chunks(chunks, "download_chunk", callback, timeout=60, backend=self)

    def test_upload(self, callback: ProgressCallback = None) -> SpeedResult:
        raise BackendError("OVH does not offer an upload endpoint")
