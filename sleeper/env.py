"""Environment configuration: a .env file, read and written without a dependency.

Every user-specific value lives here. Nothing in this package hardcodes a
username, a league id, or a draft slot.

Lookup order for a key, first hit wins:
  1. the real process environment
  2. the file named by SLEEPER_ENV_FILE
  3. $SLEEPER_HOME/.env          (default ~/.sleeper/.env)
  4. .env next to the package    (development checkout)
"""
from __future__ import annotations

import os
from pathlib import Path

PREFIX = "SLEEPER_"
_cache: dict | None = None


def _parse(text: str) -> dict:
    """KEY=VALUE lines. Supports 'export ', # comments, single or double quotes."""
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.split(" #", 1)[0].strip() if not val.strip().startswith(("'", '"')) else val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        if key:
            out[key] = val
    return out


def home() -> Path:
    """Directory for the cache, the .env file, and personal notes."""
    return Path(os.environ.get("SLEEPER_HOME") or Path.home() / ".sleeper").expanduser()


def candidates() -> list:
    """Every .env path that is consulted, in priority order."""
    paths = []
    explicit = os.environ.get("SLEEPER_ENV_FILE")
    if explicit:
        paths.append(Path(explicit).expanduser())
    paths.append(home() / ".env")
    paths.append(Path(__file__).resolve().parent.parent / ".env")
    seen, out = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def source() -> Path:
    """The .env file that is read, or the one that would be written."""
    for p in candidates():
        if p.exists():
            return p
    explicit = os.environ.get("SLEEPER_ENV_FILE")
    return Path(explicit).expanduser() if explicit else home() / ".env"


def values(*, reload: bool = False) -> dict:
    """All SLEEPER_* values, process environment winning over the file."""
    global _cache
    if _cache is not None and not reload:
        return _cache
    merged = {}
    for path in reversed(candidates()):
        if path.exists():
            merged.update({k: v for k, v in _parse(path.read_text()).items()
                           if k.startswith(PREFIX)})
    merged.update({k: v for k, v in os.environ.items() if k.startswith(PREFIX)})
    _cache = merged
    return merged


def get(key: str, default=None):
    val = values().get(key if key.startswith(PREFIX) else PREFIX + key)
    return default if val in (None, "") else val


def write(updates: dict, path: Path | None = None) -> Path:
    """Update keys in the .env file in place. Comments and other keys survive.

    Keys whose value is None are removed. The file is written with 0600
    permissions, because it names the account this tool reads.
    """
    path = path or source()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text().splitlines() if path.exists() else []
    done = set()
    out = []
    for raw in lines:
        stripped = raw.strip()
        body = stripped[7:].lstrip() if stripped.startswith("export ") else stripped
        key = body.partition("=")[0].strip()
        if key in updates and "=" in body and not stripped.startswith("#"):
            if updates[key] is not None:
                out.append(f"{key}={updates[key]}")
            done.add(key)
        else:
            out.append(raw)
    for key, val in updates.items():
        if key not in done and val is not None:
            out.append(f"{key}={val}")
    text = "\n".join(out).rstrip("\n") + "\n"
    path.write_text(text)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    values(reload=True)
    return path


def parse_pairs(raw: str | None) -> dict:
    """'a:1,b:2' -> {'a': '1', 'b': '2'}. Tolerates '=' and whitespace."""
    out = {}
    for chunk in (raw or "").replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        key, sep, val = chunk.partition(":")
        if not sep:
            key, sep, val = chunk.partition("=")
        if sep and key.strip() and val.strip():
            out[key.strip()] = val.strip()
    return out


def format_pairs(mapping: dict) -> str:
    return ",".join(f"{k}:{v}" for k, v in mapping.items() if v not in (None, ""))
