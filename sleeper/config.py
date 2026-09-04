"""User configuration, read from and written to a .env file.

There is no account information in this source tree. Everything personal
(username, league ids, draft slots) comes from the environment. See env.py for
where the .env file is looked up, and .env.example for the keys.
"""
from __future__ import annotations

from pathlib import Path

from . import env

KEYS = {
    "username": "SLEEPER_USERNAME",
    "user_id": "SLEEPER_USER_ID",
    "season": "SLEEPER_SEASON",
    "default_league": "SLEEPER_DEFAULT_LEAGUE",
}
PAIR_KEYS = {"aliases": "SLEEPER_LEAGUES", "slots": "SLEEPER_SLOTS"}

SETUP_HINT = (
    "No Sleeper username configured.\n"
    f"  Add SLEEPER_USERNAME=<your sleeper handle> to {{path}}\n"
    "  then run: sleeper leagues"
)


def path() -> Path:
    """The .env file in use, or the one that will be created."""
    return env.source()


def load() -> dict:
    cfg = {name: env.get(key) for name, key in KEYS.items()}
    cfg["aliases"] = env.parse_pairs(env.get(PAIR_KEYS["aliases"]))
    cfg["slots"] = {k: int(v) for k, v in
                    env.parse_pairs(env.get(PAIR_KEYS["slots"])).items() if v.isdigit()}
    return cfg


def save(cfg: dict) -> Path:
    updates = {key: cfg.get(name) for name, key in KEYS.items()}
    for name, key in PAIR_KEYS.items():
        updates[key] = env.format_pairs(cfg.get(name) or {}) or None
    return env.write({k: v for k, v in updates.items()})


def require_username(cfg: dict) -> str:
    name = cfg.get("username")
    if not name:
        raise SystemExit(SETUP_HINT.format(path=path()))
    return name


def notes_path() -> Path:
    """Optional file of personal, league-specific notes. Never in this repo."""
    raw = env.get("SLEEPER_NOTES")
    return Path(raw).expanduser() if raw else env.home() / "notes.md"


def resolve_league(cfg: dict, alias: str | None) -> str:
    """alias -> league_id. Accepts a raw league_id too."""
    aliases = cfg.get("aliases") or {}
    if alias is None:
        alias = cfg.get("default_league")
        if alias is None:
            raise SystemExit(
                "No league given and no default set. Run: sleeper leagues")
    if alias in aliases:
        return aliases[alias]
    if alias.isdigit():
        return alias
    raise SystemExit(
        f"Unknown league '{alias}'. Known: {', '.join(sorted(aliases)) or '(none)'}. "
        "Run: sleeper leagues")
