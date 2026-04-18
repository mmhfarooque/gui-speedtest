"""Speed test backend registry.

Backends are stored by dotted module path + class name and imported lazily on
first use. This keeps startup cheap as more backends are added, and lets
expensive availability checks (e.g. DNS, subprocess probes) happen only when
the user actually targets that backend.
"""
from __future__ import annotations

import importlib
import logging

from .base import BackendError, SpeedTestBackend

logger = logging.getLogger("gui_speedtest")

# Ordered — first entry is the default.
REGISTRY: dict[str, str] = {
    "cloudflare": "backends.cloudflare:CloudflareBackend",
    "ookla": "backends.ookla:OoklaBackend",
    "mlab": "backends.mlab:MLabBackend",
    "librespeed": "backends.librespeed:LibreSpeedBackend",
    "ovh": "backends.ovh:OvhBackend",
}


def _import_class(dotted: str) -> type[SpeedTestBackend]:
    module_path, class_name = dotted.split(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _class_for(name: str) -> type[SpeedTestBackend]:
    if name not in REGISTRY:
        raise KeyError(f"unknown backend: {name}")
    return _import_class(REGISTRY[name])


def available_backends() -> list[str]:
    """Names of backends that can run on this system — preserves registry order.

    Catches Exception broadly so a single broken backend module (syntax error
    in a future contribution, missing transitive import, etc.) cannot blank
    the entire picker. Each failure is logged at debug level so verbose mode
    surfaces it for diagnosis.
    """
    out: list[str] = []
    for name in REGISTRY:
        try:
            if _class_for(name).available():
                out.append(name)
        except Exception as e:
            logger.debug("Backend %s unavailable (%s: %s)", name, type(e).__name__, e)
    return out


def get_backend(name: str) -> SpeedTestBackend:
    """Instantiate a backend by name. Raises KeyError if unknown."""
    return _class_for(name)()


def display_name_for(name: str) -> str:
    """Read display_name as a class attribute — no instantiation, so safe to
    call for backends whose __init__ would raise (e.g. LibreSpeed without
    a configured URL). Falls back to the registry key on lookup failure."""
    try:
        return _class_for(name).display_name
    except (KeyError, ImportError, AttributeError):
        return name


__all__ = [
    "SpeedTestBackend",
    "BackendError",
    "REGISTRY",
    "available_backends",
    "display_name_for",
    "get_backend",
]
