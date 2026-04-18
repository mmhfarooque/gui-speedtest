#!/usr/bin/env python3
"""GUI Speed Test for Linux — CLI/JSON dispatcher.

GUI lives in gui_window.py. This module owns argparse + CLI + JSON output +
--list-backends.
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path

from backends import available_backends, get_backend
from backends.base import BackendError, format_speed

APP_NAME = "GUI Speed Test for Linux"
APP_ID = "io.github.mmhfarooque.GuiSpeedTest"
APP_VERSION = "1.2.2"
DEFAULT_BACKEND = "cloudflare"
LATENCY_SAMPLES = 10

# CR + ANSI clear-to-end-of-line. Without the CSI sequence, replacing
# "Detecting connection..." with shorter text like "IP: 1.2.3.4" leaves
# the tail "...nection..." dangling on screen. tput-style escape works
# in any VT100-compatible terminal (i.e. effectively all of them).
CR_CLEAR = "\r\033[K"


def _log_path() -> Path:
    """XDG-compliant log file location. Falls back to ~/.cache/ when
    XDG_CACHE_HOME isn't set. Dir is created lazily on first open."""
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "gui-speedtest" / "gui-speedtest.log"


def _setup_logging(verbose: bool) -> None:
    """Console handler (WARNING or DEBUG) + always-on rotating file
    handler (DEBUG). The file is the canonical place to look when
    something behaves oddly — users can paste it without re-running
    with a --verbose flag."""
    root = logging.getLogger("gui_speedtest")
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(console)

    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # 5 files * 1 MiB = 5 MiB cap total
        file_handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=1_048_576, backupCount=4, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        root.addHandler(file_handler)
        root.info("=== %s v%s starting (pid=%s) ===", APP_NAME, APP_VERSION, os.getpid())
        root.debug("Log file: %s", path)
    except OSError as e:
        # Not fatal — just means we'll only have console output.
        root.warning("Could not open log file (%s); file logging disabled", e)


def _run_cli_latency(backend) -> str:
    """Return a single human-readable latency summary line for the CLI."""
    try:
        lat = backend.test_latency(samples=LATENCY_SAMPLES)
    except BackendError as e:
        return f"N/A ({e})"
    if lat.failed:
        return "N/A (all samples failed)"
    return (
        f"{lat.avg:.1f} ms "
        f"(min {lat.min:.1f}, max {lat.max:.1f}, jitter {lat.jitter:.1f})"
    )


def run_cli(backend_name: str) -> None:
    backend = get_backend(backend_name)
    print(f"\n  {APP_NAME} v{APP_VERSION}")
    print(f"  Backend: {backend.display_name}")
    print("  " + "=" * 44)

    print("\n  Detecting connection...", end="", flush=True)
    try:
        info = backend.connection_info()
    except BackendError as e:
        print(f"{CR_CLEAR}  Connection: N/A ({e})")
        info = None
    if info:
        print(f"{CR_CLEAR}  IP:       {info.ip}")
        print(f"  ISP:      {info.isp}")
        print(f"  Location: {info.location}")
        if info.server:
            print(f"  Server:   {info.server}")

    print(f"\n  Testing latency ({LATENCY_SAMPLES} samples)...", end="", flush=True)
    lat_text = _run_cli_latency(backend)
    print(f"{CR_CLEAR}  Latency:  {lat_text}")

    print("\n  Testing download speed...")

    def dl_cb(event: str, data: dict) -> None:
        if event == "download_chunk":
            bar = "█" * data["current"] + "░" * (data["total"] - data["current"])
            print(f"    {bar} {data['label']}: {format_speed(data['speed_mbps'])}")

    try:
        download = backend.test_download(callback=dl_cb)
        download_str = format_speed(download.speed_mbps)
    except BackendError as e:
        download = None
        download_str = f"N/A ({e})"
    print(f"  Download: {download_str}")

    print("\n  Testing upload speed...")

    def ul_cb(event: str, data: dict) -> None:
        if event == "upload_chunk":
            bar = "█" * data["current"] + "░" * (data["total"] - data["current"])
            print(f"    {bar} {data['label']}: {format_speed(data['speed_mbps'])}")

    try:
        upload = backend.test_upload(callback=ul_cb)
        upload_str = format_speed(upload.speed_mbps)
    except BackendError as e:
        upload = None
        upload_str = f"N/A ({e})"
    print(f"  Upload:   {upload_str}")

    print("\n  " + "=" * 44)
    print(f"  Download: {download_str}")
    print(f"  Upload:   {upload_str}")
    print(f"  Latency:  {lat_text}")
    print()


def _safe_call(fn, *args, **kwargs):
    """Call fn; return (result, error_str_or_None). Normalises BackendError
    into a structured result for JSON output."""
    try:
        return fn(*args, **kwargs), None
    except BackendError as e:
        return None, str(e)


def run_json(backend_name: str) -> None:
    backend = get_backend(backend_name)
    info, info_err = _safe_call(backend.connection_info)
    lat, lat_err = _safe_call(backend.test_latency, samples=LATENCY_SAMPLES)
    download, dl_err = _safe_call(backend.test_download)
    upload, ul_err = _safe_call(backend.test_upload)

    result: dict = {
        "app": {"name": APP_NAME, "version": APP_VERSION},
        "backend": backend.name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if info:
        result["server"] = {"name": info.server}
        result["client"] = {
            "ip": info.ip,
            "isp": info.isp,
            "city": info.city,
            "region": info.region,
            "country": info.country,
        }
    else:
        result["connection_error"] = info_err

    if lat is not None and not lat.failed:
        result["latency"] = {
            "avg_ms": round(lat.avg, 2),
            "min_ms": round(lat.min, 2),
            "max_ms": round(lat.max, 2),
            "jitter_ms": round(lat.jitter, 2),
            "samples": lat.samples,
        }
    elif lat is not None:
        result["latency"] = {"error": "all samples failed"}
    else:
        result["latency"] = {"error": lat_err}

    def _speed(r, err):
        if r is None:
            return {"error": err}
        return {
            "speed_mbps": round(r.speed_mbps, 2),
            "samples_mbps": [round(s, 2) for s in r.samples],
        }

    result["download"] = _speed(download, dl_err)
    result["upload"] = _speed(upload, ul_err)

    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION} — test your internet speed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--gui", action="store_true", help="Launch GTK4 graphical interface")
    parser.add_argument("--json", action="store_true", help="Output CLI results as JSON")
    parser.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        help=f"Speed test backend (default: {DEFAULT_BACKEND})",
    )
    parser.add_argument(
        "--list-backends",
        action="store_true",
        help="List available backends and exit",
    )
    parser.add_argument(
        "--librespeed-url",
        metavar="URL",
        help="LibreSpeed server URL (sets LIBRESPEED_URL env var for this run)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging (prints per-sample failures)",
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    if args.librespeed_url:
        os.environ["LIBRESPEED_URL"] = args.librespeed_url

    if args.list_backends:
        for name in available_backends():
            print(name)
        return

    if args.backend not in available_backends():
        sys.stderr.write(
            f"error: backend '{args.backend}' not available. "
            f"Choose from: {', '.join(available_backends())}\n"
        )
        sys.exit(2)

    if args.gui:
        from gui_window import run_gui

        run_gui(args.backend, APP_NAME, APP_ID, APP_VERSION, LATENCY_SAMPLES)
    elif args.json:
        run_json(args.backend)
    else:
        run_cli(args.backend)


if __name__ == "__main__":
    main()
