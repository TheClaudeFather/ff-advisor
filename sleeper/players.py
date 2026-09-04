"""Player DB. The raw feed is ~14MB / 12k players; we keep a ~1MB slim index.

All commands load the slim file. Only `refresh players` touches the raw one.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import api, cache

SLIM = cache.ROOT / "players" / "slim.json"

_KEEP = ("position", "team", "status", "injury_status", "age",
         "years_exp", "depth_chart_order", "search_rank")


def _build_slim(raw: dict) -> dict:
    out = {}
    for pid, p in raw.items():
        pos = p.get("position")
        if pos not in api.POSITIONS:
            continue
        name = p.get("full_name") or " ".join(
            filter(None, [p.get("first_name"), p.get("last_name")])) or pid
        rec = {"name": name}
        for k in _KEEP:
            v = p.get(k)
            if v is not None:
                rec[k] = v
        out[pid] = rec
    return out


def refresh(**kw) -> int:
    raw = api.players_raw(refresh=True, **kw)
    slim = _build_slim(raw)
    SLIM.parent.mkdir(parents=True, exist_ok=True)
    SLIM.write_text(json.dumps(slim))
    return len(slim)


def load(*, offline=False) -> dict:
    """{player_id: {name, position, team, status, injury_status, ...}}"""
    if SLIM.exists():
        return json.loads(SLIM.read_text())
    if offline:
        raise RuntimeError("player DB not cached and --offline set; run: sleeper refresh players")
    refresh()
    return json.loads(SLIM.read_text())


def age_seconds():
    return cache.age("players", "nfl")


def find(db: dict, query: str) -> list[tuple[str, dict]]:
    """Fuzzy-ish name lookup. Returns all plausible matches; never guesses."""
    q = query.lower().strip()
    exact = [(i, p) for i, p in db.items() if p["name"].lower() == q]
    if exact:
        return exact
    starts = [(i, p) for i, p in db.items() if p["name"].lower().startswith(q)]
    if starts:
        return starts
    return [(i, p) for i, p in db.items() if q in p["name"].lower()]


def label(p: dict) -> str:
    inj = p.get("injury_status")
    tag = f" [{inj}]" if inj else ""
    return f"{p['name']} ({p.get('position','?')}-{p.get('team') or 'FA'}){tag}"
