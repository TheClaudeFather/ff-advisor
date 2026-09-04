"""The ONLY module that knows Sleeper URLs. Everything else goes through here.

Keeping URLs in one place is what makes the advice/* modules pure functions
over data, and therefore testable offline against fixtures.
"""
from __future__ import annotations

from . import cache

BASE = "https://api.sleeper.app"
HOUR = 3600
DAY = 24 * HOUR

POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
_POS_Q = "&".join(f"position%5B%5D={p}" for p in POSITIONS)


def state(**kw):
    return cache.get_json("meta", "state", f"{BASE}/v1/state/nfl", HOUR, **kw)


def user(username):
    return cache.get_json("meta", f"user_{username}", f"{BASE}/v1/user/{username}", 7 * DAY)


def leagues(user_id, season, **kw):
    return cache.get_json("meta", f"leagues_{user_id}_{season}",
                          f"{BASE}/v1/user/{user_id}/leagues/nfl/{season}", DAY, **kw)


def league(league_id, **kw):
    return cache.get_json("league", f"{league_id}", f"{BASE}/v1/league/{league_id}", 7 * DAY, **kw)


def rosters(league_id, **kw):
    return cache.get_json("league", f"{league_id}_rosters",
                          f"{BASE}/v1/league/{league_id}/rosters", HOUR, **kw)


def league_users(league_id, **kw):
    return cache.get_json("league", f"{league_id}_users",
                          f"{BASE}/v1/league/{league_id}/users", DAY, **kw)


def matchups(league_id, week, **kw):
    return cache.get_json("league", f"{league_id}_matchups_{week}",
                          f"{BASE}/v1/league/{league_id}/matchups/{week}", HOUR, **kw)


def transactions(league_id, week, **kw):
    return cache.get_json("league", f"{league_id}_tx_{week}",
                          f"{BASE}/v1/league/{league_id}/transactions/{week}", HOUR, **kw)


def league_drafts(league_id, **kw):
    return cache.get_json("draft", f"{league_id}_drafts",
                          f"{BASE}/v1/league/{league_id}/drafts", HOUR, **kw)


def draft(draft_id, **kw):
    return cache.get_json("draft", f"{draft_id}", f"{BASE}/v1/draft/{draft_id}", 60, **kw)


def draft_picks(draft_id):
    """Always fetched live. This is the hot path during a draft.

    A snapshot is kept only as a fallback: if the request fails while the pick
    clock is running, stale picks are far better than a crash. The caller is
    told how old the snapshot is so it can warn.
    """
    import json
    import time

    from .http import FetchError, fetch_json

    snap = cache.ROOT / "draft" / f"{draft_id}_picks_snapshot.json"
    try:
        picks = fetch_json(f"{BASE}/v1/draft/{draft_id}/picks")
    except (FetchError, Exception) as e:  # noqa: BLE001
        if snap.exists():
            d = json.loads(snap.read_text())
            age = time.time() - d["at"]
            return d["picks"], age
        raise
    snap.parent.mkdir(parents=True, exist_ok=True)
    tmp = snap.with_suffix(".tmp")
    tmp.write_text(json.dumps({"at": time.time(), "picks": picks}))
    import os
    os.replace(tmp, snap)
    return picks, 0.0


def players_raw(**kw):
    """~14MB. Callers should use players.load() which reads the slim file."""
    return cache.get_json("players", "nfl", f"{BASE}/v1/players/nfl", DAY, **kw)


def projections_season(season, **kw):
    return cache.get_json("proj", f"season_{season}",
                          f"{BASE}/projections/nfl/{season}?season_type=regular&{_POS_Q}",
                          12 * HOUR, **kw)


def projections_week(season, week, *, completed=False, **kw):
    """Completed weeks are immutable -> cached forever."""
    ttl = cache.FOREVER if completed else 6 * HOUR
    return cache.get_json("proj", f"week_{season}_{week}",
                          f"{BASE}/projections/nfl/{season}/{week}?season_type=regular&{_POS_Q}",
                          ttl, **kw)


def stats_week(season, week, **kw):
    return cache.get_json("stats", f"{season}_{week}",
                          f"{BASE}/stats/nfl/{season}/{week}?season_type=regular&{_POS_Q}",
                          cache.FOREVER, **kw)


def trending(kind="add", hours=24, limit=50, **kw):
    return cache.get_json("meta", f"trending_{kind}_{hours}",
                          f"{BASE}/v1/players/nfl/trending/{kind}"
                          f"?lookback_hours={hours}&limit={limit}", 1800, **kw)
