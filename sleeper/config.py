"""User configuration, read from and written to a .env file.

There is no account information in this source tree. Everything personal
(username, league ids, draft slots) comes from the environment. See env.py for
where the .env file is looked up, and .env.example for the keys.
"""
from __future__ import annotations

from pathlib import Path

from . import env, match

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


def resolve_alias(cfg: dict, alias: str | None, *, descriptors=None) -> str | None:
    """The configured alias that a name or a phrase refers to.

    Returns None when the caller passed a raw league_id, which has no alias.
    Draft slots are stored per alias, so a phrase must land on the same alias
    that `sleeper leagues` created, or a draft started from "my 10-team league"
    would silently lose the stored slot.
    """
    aliases = cfg.get("aliases") or {}
    name = alias if alias is not None else cfg.get("default_league")
    if name is None:
        raise SystemExit("No league given and no default set. Run: sleeper leagues")
    if name in aliases:
        return name
    if str(name).isdigit():
        return None

    hits = match.find(load_descriptors(cfg) if descriptors is None else descriptors,
                      name)
    # Several aliases may name one league. That is one candidate, not ambiguity.
    ids = {aliases.get(h["alias"], h["league_id"]) for h in hits}
    if len(ids) == 1:
        return hits[0]["alias"]
    if hits:
        listed = "; ".join(f"{h['alias']} ({h['summary']})" for h in hits)
        raise SystemExit(
            f"'{name}' matches more than one league: {listed}. Name one.")
    known = ", ".join(sorted(aliases)) or "(none)"
    raise SystemExit(
        f"Unknown league '{name}'. Known: {known}. Run: sleeper leagues")


def resolve_league(cfg: dict, alias: str | None, *, descriptors=None) -> str:
    """alias -> league_id. Accepts a raw league_id, or a phrase describing it.

    The phrase path is what lets someone say "my 10-team league" or "the
    superflex one" instead of an alias that a command generated for them.
    """
    aliases = cfg.get("aliases") or {}
    name = alias if alias is not None else cfg.get("default_league")
    resolved = resolve_alias(cfg, alias, descriptors=descriptors)
    if resolved is None:
        return str(name)
    if resolved not in aliases:
        known = ", ".join(sorted(aliases)) or "(none)"
        raise SystemExit(
            f"Unknown league '{resolved}'. Known: {known}. Run: sleeper leagues")
    return aliases[resolved]


def load_descriptors(cfg: dict) -> list:
    return match.load_descriptors(cfg)
