"""Raw projection feeds -> {player_id: points} in a given league's scoring.

Horizons: "season", "week:N", "ros". Draft valuation and in-season waiver
valuation are the same code with a different horizon.
"""
from __future__ import annotations

from . import api, scoring

LAST_WEEK = 18


def _index(records) -> dict:
    """Projection feed -> {player_id: (stats, position, opponent)}."""
    out = {}
    for r in records:
        pid = r.get("player_id")
        if not pid:
            continue
        pos = (r.get("player") or {}).get("position")
        out[pid] = ((r.get("stats") or {}), pos, r.get("opponent"))
    return out


def stat_keys(records, limit=800) -> set:
    keys = set()
    for r in records[:limit]:
        keys |= set((r.get("stats") or {}).keys())
    return keys


def raw(season, horizon, *, current_week=1, **kw):
    if horizon == "season":
        return api.projections_season(season, **kw)
    if horizon.startswith("week:"):
        wk = int(horizon.split(":")[1])
        return api.projections_week(season, wk, completed=wk < current_week, **kw)
    raise ValueError(f"bad horizon {horizon}")


def ros_share(current_week: int) -> float:
    """The fraction of the season still to be played, counting this week."""
    return max(0.0, (LAST_WEEK - current_week + 1) / LAST_WEEK)


def points(lg, horizon, *, current_week=1, **kw) -> tuple[dict, dict]:
    """-> ({player_id: points}, {player_id: opponent})

    "ros" scales the season projection to the weeks that remain.

    The obvious alternative, summing the remaining weekly feeds, is both
    optimistic and unevenly so: measured against the 2026 season feed it came
    out 8% high for a durable quarterback, 15% for a workhorse back, and 30%
    for an injury-prone one. Weekly numbers describe the healthy version of a
    player, while the season number prices his risk, so summing them does not
    merely inflate values, it reorders them. Scaling keeps Sleeper's own view
    of relative risk. It does not know which players still have a bye ahead of
    them, which is the accuracy this trades away.
    """
    sc = lg.scoring
    if horizon == "ros":
        season_pts, _ = points(lg, "season", current_week=current_week, **kw)
        share = ros_share(current_week)
        return {p: v * share for p, v in season_pts.items()}, {}

    idx = _index(raw(lg.season, horizon, current_week=current_week, **kw))
    pts = {pid: scoring.score_player(stats, sc, pos) for pid, (stats, pos, _o) in idx.items()}
    opp = {pid: o for pid, (_s, _p, o) in idx.items()}
    return pts, opp


def diagnostics(lg, records) -> dict:
    """Scoring keys this league uses that we cannot compute. Printed, not hidden."""
    return scoring.unscored_keys(lg.scoring, stat_keys(records))
