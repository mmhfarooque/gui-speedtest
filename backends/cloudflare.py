"""Cloudflare speed test backend.

Uses the public speed.cloudflare.com endpoints (no auth). Global anycast, so
the test automatically hits the nearest Cloudflare PoP.

Connection info uses a graceful fallback chain because /meta started rejecting
plain Python user agents with HTTP 403:
  1. /meta with a real browser UA — full info: IP, ISP, city, colo
  2. /cdn-cgi/trace → IP, colo, ISO-2 country; enriched via ipwho.is for ISP+city
  3. /cdn-cgi/trace alone — IP, colo, country (no ISP)
  4. api.ipify.org — IP only

The "country" field in the fallback path is an ISO-2 code (e.g. "BD") whereas
/meta gives the two-letter code too; both are consistent ISO-2 for this backend.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from .base import (
    BROWSER_UA,
    NETWORK_EXCEPTIONS,
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

DOWN_URL = "https://speed.cloudflare.com/__down?bytes={}"
UP_URL = "https://speed.cloudflare.com/__up"
META_URL = "https://speed.cloudflare.com/meta"
TRACE_URL = "https://www.cloudflare.com/cdn-cgi/trace"
IPIFY_URL = "https://api.ipify.org?format=json"
IPWHO_URL = "https://ipwho.is/"

DOWN_SIZES = [
    (1_000_000, "1 MB"),
    (5_000_000, "5 MB"),
    (10_000_000, "10 MB"),
    (25_000_000, "25 MB"),
]
# Upload sizes symmetric with DOWN_SIZES so TCP has time to ramp up and
# saturate before the sample ends. With the old 500K-5M range, the top
# samples often measured warmup slope rather than steady-state throughput
# and reported ~30% low on fast links.
UP_SIZES = [
    (1_000_000, "1 MB"),
    (5_000_000, "5 MB"),
    (10_000_000, "10 MB"),
    (25_000_000, "25 MB"),
]


def _parse_trace(body: str) -> dict:
    out: dict = {}
    for line in body.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _ipwho_lookup(ip: str = "") -> dict | None:
    """Look up ISP/city via ipwho.is. Returns None on any failure.
    Empty IP lets the service auto-detect our public IP."""
    # quote() defends against malformed IPs from upstream — e.g. an IPv6
    # with a zone suffix or junk that sneaks past trace parsing. The empty
    # string passes through unchanged, preserving auto-detect behaviour.
    safe_ip = urllib.parse.quote(ip, safe=":")
    try:
        data = json.loads(safe_decode(http_get(IPWHO_URL + safe_ip, timeout=5)))
        if not data.get("success", True):
            return None
        connection = data.get("connection", {}) or {}
        return {
            "ip": data.get("ip", ""),
            "isp": connection.get("isp") or connection.get("org") or "Unknown",
            "city": data.get("city", ""),
            "region": data.get("region", ""),
            "country_code": data.get("country_code", ""),
        }
    except (*NETWORK_EXCEPTIONS, json.JSONDecodeError):
        return None


class CloudflareBackend(SpeedTestBackend):
    name = "cloudflare"
    display_name = "Cloudflare"

    def connection_info(self) -> ConnectionInfo:
        try:
            data = json.loads(safe_decode(http_get(META_URL, timeout=5)))
            return ConnectionInfo(
                ip=data.get("clientIp", "Unknown"),
                isp=data.get("asOrganization", "Unknown"),
                city=data.get("city", ""),
                region=data.get("region", "Unknown"),
                country=data.get("country", ""),
                server=f"Cloudflare {data.get('colo', '')}".strip(),
            )
        except (*NETWORK_EXCEPTIONS, json.JSONDecodeError):
            pass

        trace: dict = {}
        try:
            trace = _parse_trace(safe_decode(http_get(TRACE_URL, timeout=5)))
        except NETWORK_EXCEPTIONS:
            pass

        ip = trace.get("ip", "")
        colo = trace.get("colo", "")
        country = trace.get("loc", "")

        enriched = _ipwho_lookup(ip)
        if enriched:
            return ConnectionInfo(
                ip=ip or enriched.get("ip", "Unknown"),
                isp=enriched.get("isp", "Unknown"),
                city=enriched.get("city", ""),
                region=enriched.get("region", "Unknown"),
                country=country or enriched.get("country_code", ""),
                server=f"Cloudflare {colo}".strip() if colo else "Cloudflare",
            )

        if ip:
            return ConnectionInfo(
                ip=ip,
                country=country,
                server=f"Cloudflare {colo}".strip() if colo else "Cloudflare",
            )

        try:
            data = json.loads(safe_decode(http_get(IPIFY_URL, timeout=5)))
            return ConnectionInfo(ip=data.get("ip", "Unknown"), server="Cloudflare")
        except (*NETWORK_EXCEPTIONS, json.JSONDecodeError):
            return ConnectionInfo(server="Cloudflare")

    def test_latency(
        self, samples: int = 10, callback: ProgressCallback = None
    ) -> LatencyResult:
        def factory() -> urllib.request.Request:
            return urllib.request.Request(
                DOWN_URL.format(0), headers={"User-Agent": BROWSER_UA}
            )

        return measure_latency(factory, samples, callback, backend=self)

    def test_download(self, callback: ProgressCallback = None) -> SpeedResult:
        def make(size: int) -> urllib.request.Request:
            return urllib.request.Request(
                DOWN_URL.format(size), headers={"User-Agent": BROWSER_UA}
            )

        chunks = [
            Chunk(request_factory=lambda s=s: make(s), label=label)
            for s, label in DOWN_SIZES
        ]
        return run_chunks(chunks, "download_chunk", callback, backend=self)

    def test_upload(self, callback: ProgressCallback = None) -> SpeedResult:
        def make(size: int) -> urllib.request.Request:
            return urllib.request.Request(
                UP_URL,
                data=os.urandom(size),
                headers={
                    "User-Agent": BROWSER_UA,
                    "Content-Type": "application/octet-stream",
                },
                method="POST",
            )

        chunks = [
            Chunk(request_factory=lambda s=s: make(s), label=label, size_bytes=s)
            for s, label in UP_SIZES
        ]
        return run_chunks(chunks, "upload_chunk", callback, backend=self)
