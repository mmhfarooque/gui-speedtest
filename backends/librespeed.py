"""LibreSpeed backend.

Open-source HTML5 speed test. Requires a server URL since public LibreSpeed
servers rotate — list at https://github.com/librespeed/speedtest/wiki.

Configure via the `LIBRESPEED_URL` environment variable or the
`--librespeed-url` CLI flag. Expected form: a full URL with http:// or
https:// scheme pointing at the root of a LibreSpeed deployment (e.g.
`https://speedtest.example.com/`).

URLs are validated to reject non-HTTP schemes. Private/loopback hosts are
allowed (self-hosted deployments are common) but logged so the caller knows
the request is going somewhere internal.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
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
)

ENV_VAR = "LIBRESPEED_URL"

DOWN_CHUNKS_MB = [1, 5, 10, 25]
UP_SIZES = [
    (500_000, "500 KB"),
    (1_000_000, "1 MB"),
    (2_000_000, "2 MB"),
    (5_000_000, "5 MB"),
]


def _validate_url(raw: str) -> str | None:
    """Return a normalised URL or None if rejected.

    Defends against:
    - non-HTTP schemes (file://, javascript:, ftp://, etc.)
    - control characters / CRLF injection (header smuggling vector if a
      malicious URL is set in env and later interpolated into raw HTTP)
    - userinfo (`user:pass@host`) — credentials in URLs are nearly always
      a mistake or attempted exfiltration of the password to logs
    - empty hostname
    """
    # Reject any control character or whitespace anywhere in the string.
    # Includes \r\n (CRLF), \t, NUL, and the rest of the C0 set.
    if any(ord(c) < 0x20 or c == "\x7f" for c in raw):
        return None
    try:
        parsed = urllib.parse.urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    host = parsed.hostname or ""
    if not host:
        return None
    # DNS lookup below is *informational only* — logging if the configured
    # host resolves to a private address so a self-host misconfiguration is
    # visible. It is NOT a security boundary: DNS can rebind between this
    # check and the eventual urllib.request connection (TOCTOU), and only
    # the first A record is inspected. Trust boundary is the user setting
    # LIBRESPEED_URL; we don't treat the value as adversarial input.
    try:
        resolved = socket.gethostbyname(host)
        ip = ipaddress.ip_address(resolved)
        if ip.is_loopback or ip.is_private or ip.is_link_local:
            logger.info(
                "LibreSpeed URL resolves to a non-public address (%s) — "
                "assuming self-hosted deployment",
                resolved,
            )
    except (socket.gaierror, ValueError):
        # DNS failure is not fatal here — user may be on a private network
        # where the host resolves later. Let the HTTP call surface the error.
        pass
    return raw.rstrip("/")


def _server_url() -> str | None:
    raw = os.environ.get(ENV_VAR, "").strip()
    if not raw:
        return None
    return _validate_url(raw)


class LibreSpeedBackend(SpeedTestBackend):
    name = "librespeed"
    display_name = "LibreSpeed"

    @classmethod
    def available(cls) -> bool:
        return _server_url() is not None

    def __init__(self) -> None:
        self.base = _server_url()
        if not self.base:
            raise BackendError(
                f"{ENV_VAR} is not set or invalid (expected http:// or https:// URL)"
            )

    def _url(self, path: str) -> str:
        return f"{self.base}/{path.lstrip('/')}"

    def connection_info(self) -> ConnectionInfo:
        try:
            data = json.loads(safe_decode(http_get(self._url("backend/getIP.php"), timeout=5)))
            parts = data.get("processedString", "").split(" - ", 1)
            ip = parts[0] if parts else "Unknown"
            isp_country = parts[1] if len(parts) > 1 else ""
            isp, _, country = isp_country.partition(", ")
            return ConnectionInfo(
                ip=ip or "Unknown",
                isp=isp.strip() or "Unknown",
                country=country.strip(),
                server=self.base,
            )
        except (*NETWORK_EXCEPTIONS, json.JSONDecodeError):
            return ConnectionInfo(server=self.base)

    def test_latency(
        self, samples: int = 10, callback: ProgressCallback = None
    ) -> LatencyResult:
        url = self._url("backend/empty.php")

        def factory() -> urllib.request.Request:
            return urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})

        return measure_latency(factory, samples, callback)

    def test_download(self, callback: ProgressCallback = None) -> SpeedResult:
        def make(mb: int) -> urllib.request.Request:
            return urllib.request.Request(
                self._url(f"backend/garbage.php?ckSize={mb}"),
                headers={"User-Agent": BROWSER_UA},
            )

        chunks = [
            Chunk(request_factory=lambda m=mb: make(m), label=f"{mb} MB")
            for mb in DOWN_CHUNKS_MB
        ]
        return run_chunks(chunks, "download_chunk", callback)

    def test_upload(self, callback: ProgressCallback = None) -> SpeedResult:
        def make(size: int) -> urllib.request.Request:
            return urllib.request.Request(
                self._url("backend/empty.php"),
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
        return run_chunks(chunks, "upload_chunk", callback)
