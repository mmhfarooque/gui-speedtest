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

# Curated list of public LibreSpeed endpoints shipped with the app so
# first-time users get a working picker without hunting down a server URL.
# All entries must point at the ROOT of a LibreSpeed deployment — the app
# appends /backend/garbage.php, /backend/empty.php, /backend/getIP.php to
# this base. Sponsor + location are shown in the dropdown label so users
# can pick one geographically close to them.
#
# Order matters: entry 0 is the default selection when the user hasn't
# configured anything. Update this list when servers rotate (check the
# LibreSpeed community list at https://librespeed.org/servers/ and
# https://github.com/librespeed/speedtest/wiki for current endpoints).
KNOWN_SERVERS: list[dict[str, str]] = [
    {
        "name": "Clouvider (New York, US)",
        "url": "https://nyc.speedtest.clouvider.net",
        "sponsor": "Clouvider",
    },
    {
        "name": "Clouvider (Atlanta, US)",
        "url": "https://atl.speedtest.clouvider.net",
        "sponsor": "Clouvider",
    },
    {
        "name": "Clouvider (Los Angeles, US)",
        "url": "https://la.speedtest.clouvider.net",
        "sponsor": "Clouvider",
    },
]


def list_servers() -> list[dict[str, str]]:
    """Return the public server list plus any custom URL from LIBRESPEED_URL.

    The env-var custom entry is appended at the end (or replaces a match if
    the user set the same URL as a known one). Keeps the dropdown useful
    for both out-of-the-box users and self-hosters.
    """
    out = list(KNOWN_SERVERS)
    raw = os.environ.get(ENV_VAR, "").strip()
    if raw:
        validated = _validate_url(raw)
        if validated and not any(s["url"] == validated for s in out):
            out.append(
                {
                    "name": f"Custom ({validated})",
                    "url": validated,
                    "sponsor": "user-configured",
                }
            )
    return out


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


def _probe_reachable(url: str, timeout: float = 4.0) -> bool:
    """Quick HEAD-style probe of a LibreSpeed root.

    Hits /backend/empty.php (the same endpoint used for latency samples) to
    verify both DNS and that the LibreSpeed deployment actually serves our
    expected path layout. Returns True on HTTP 2xx.
    """
    target = f"{url.rstrip('/')}/backend/empty.php"
    try:
        req = urllib.request.Request(target, headers={"User-Agent": BROWSER_UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (*NETWORK_EXCEPTIONS, OSError):
        return False


def _is_curated(url: str) -> bool:
    """True if `url` matches one of the shipped KNOWN_SERVERS entries.

    Used by the auto-fallback path to decide whether to second-guess the
    server choice. Custom / self-hosted URLs (via $LIBRESPEED_URL or
    --librespeed-url) are left alone — the user explicitly asked for that
    server, so a silent switch would be wrong.
    """
    norm = url.rstrip("/")
    return any(s["url"].rstrip("/") == norm for s in KNOWN_SERVERS)


def _server_url() -> str | None:
    """Resolve the LibreSpeed server URL, preferring env var > baked-in default.

    Order of precedence:
      1. $LIBRESPEED_URL if set AND valid (custom / self-hosted).
      2. First entry of KNOWN_SERVERS (the shipped default).

    Return None only if the env var is set but fails validation AND for
    some reason KNOWN_SERVERS is empty — which would be a bug in our
    shipped config, not a user error.
    """
    raw = os.environ.get(ENV_VAR, "").strip()
    if raw:
        validated = _validate_url(raw)
        if validated:
            return validated
        logger.warning(
            "%s is set to %r but failed validation — falling back to default server",
            ENV_VAR, raw,
        )
    if KNOWN_SERVERS:
        return KNOWN_SERVERS[0]["url"]
    return None


class LibreSpeedBackend(SpeedTestBackend):
    name = "librespeed"
    display_name = "LibreSpeed"

    @classmethod
    def available(cls) -> bool:
        # Always available — we ship a curated KNOWN_SERVERS list so users
        # don't have to hunt down a LibreSpeed endpoint before first use.
        # A custom URL via $LIBRESPEED_URL takes precedence.
        return _server_url() is not None

    def __init__(self, server_url: str | None = None) -> None:
        """Instantiate with an optional explicit server URL.

        The GUI passes the user's pick from the server dropdown via this
        parameter; the CLI / default path resolves via _server_url() which
        honours LIBRESPEED_URL env var first, then falls back to the first
        KNOWN_SERVERS entry.
        """
        self.base = server_url or _server_url()
        if not self.base:
            raise BackendError(
                f"No LibreSpeed server configured (KNOWN_SERVERS empty and "
                f"{ENV_VAR} unset) — this should not happen in a shipped release."
            )
        self._reachability_checked = False
        self.fallback_from: str | None = None

    def _ensure_reachable(self) -> None:
        """Probe self.base; if dead and we're using a curated server, pick the
        next live one from KNOWN_SERVERS.

        Public LibreSpeed servers rotate — domains expire, deployments move,
        operators stop sponsoring. Without this probe, the user picks a server
        in the GUI dropdown, the run starts, every phase fails with cryptic
        DNS errors, and the cards show "all samples failed". With this probe,
        we transparently fall back to a working server and surface the switch
        via ConnectionInfo.server + a log line.

        No-op for custom (self-hosted) URLs: when a user sets LIBRESPEED_URL
        or passes --librespeed-url, they explicitly want that server. Silent
        switching would mask their misconfiguration.
        """
        if self._reachability_checked:
            return
        self._reachability_checked = True

        if not _is_curated(self.base):
            return

        if _probe_reachable(self.base):
            return

        original = self.base
        logger.warning(
            "LibreSpeed server %s unreachable — probing fallbacks", original
        )
        for candidate in KNOWN_SERVERS:
            url = candidate["url"].rstrip("/")
            if url == original.rstrip("/"):
                continue
            if _probe_reachable(url):
                self.base = url
                self.fallback_from = original
                logger.info(
                    "LibreSpeed: switched from %s to %s (%s)",
                    original, url, candidate["name"],
                )
                return
        logger.error(
            "LibreSpeed: no curated server reachable; keeping %s "
            "(phase HTTP errors will surface)", original,
        )

    def _url(self, path: str) -> str:
        return f"{self.base}/{path.lstrip('/')}"

    def connection_info(self) -> ConnectionInfo:
        self._ensure_reachable()
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
        self._ensure_reachable()
        url = self._url("backend/empty.php")

        def factory() -> urllib.request.Request:
            return urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})

        return measure_latency(factory, samples, callback, backend=self)

    def test_download(self, callback: ProgressCallback = None) -> SpeedResult:
        self._ensure_reachable()
        def make(mb: int) -> urllib.request.Request:
            return urllib.request.Request(
                self._url(f"backend/garbage.php?ckSize={mb}"),
                headers={"User-Agent": BROWSER_UA},
            )

        chunks = [
            Chunk(request_factory=lambda m=mb: make(m), label=f"{mb} MB")
            for mb in DOWN_CHUNKS_MB
        ]
        return run_chunks(chunks, "download_chunk", callback, backend=self)

    def test_upload(self, callback: ProgressCallback = None) -> SpeedResult:
        self._ensure_reachable()
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
        return run_chunks(chunks, "upload_chunk", callback, backend=self)
