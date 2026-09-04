"""File-backed JSON cache with per-entry TTL, under $SLEEPER_HOME/cache."""
from __future__ import annotations

import json
import os
import time

from . import env
from .http import fetch_json

ROOT = env.home() / "cache"

FOREVER = None  # sentinel: never expires


def _paths(ns: str, key: str):
    d = ROOT / ns
    return d / f"{key}.json", d / f"{key}.meta.json"


def age(ns: str, key: str):
    """Seconds since fetched, or None if absent."""
    _, meta = _paths(ns, key)
    if not meta.exists():
        return None
    try:
        return time.time() - json.loads(meta.read_text())["fetched_at"]
    except Exception:  # noqa: BLE001
        return None


def peek(ns: str, key: str):
    """Return cached value without fetching, or None."""
    data, _ = _paths(ns, key)
    if not data.exists():
        return None
    try:
        return json.loads(data.read_text())
    except Exception:  # noqa: BLE001
        return None


def get_json(ns, key, url, ttl, *, refresh=False, offline=False):
    """Cached fetch. ttl in seconds, or FOREVER. offline=True never hits network."""
    data_p, meta_p = _paths(ns, key)
    a = age(ns, key)
    fresh = a is not None and (ttl is FOREVER or a < ttl)

    if not refresh and fresh:
        cached = peek(ns, key)
        if cached is not None:
            return cached

    if offline:
        cached = peek(ns, key)
        if cached is not None:
            return cached
        raise RuntimeError(f"--offline but nothing cached for {ns}/{key}")

    value = fetch_json(url)
    data_p.parent.mkdir(parents=True, exist_ok=True)
    tmp = data_p.with_suffix(".tmp")
    tmp.write_text(json.dumps(value))
    os.replace(tmp, data_p)
    meta_p.write_text(json.dumps({"fetched_at": time.time(), "url": url}))
    return value


def clear(ns: str | None = None):
    import shutil
    target = ROOT / ns if ns else ROOT
    if target.exists():
        shutil.rmtree(target)
        return str(target)
    return None


def human_age(secs) -> str:
    if secs is None:
        return "never"
    if secs < 90:
        return f"{secs:.0f}s"
    if secs < 5400:
        return f"{secs/60:.0f}m"
    if secs < 172800:
        return f"{secs/3600:.0f}h"
    return f"{secs/86400:.0f}d"
