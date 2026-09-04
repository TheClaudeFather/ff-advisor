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


def points(lg, horizon, *, current_week=1, **kw) -> tuple[dict, dict]:
    """-> ({player_id: points}, {player_id: opponent})

    "ros" sums remaining weeks; falls back to a season pro-rate if the weekly
    feeds are not published yet (flagged by the caller via `estimated`).
    """
    sc = lg.scoring
    if horizon == "ros":
        total, opp = {}, {}
        got = 0
        for wk in range(current_week, LAST_WEEK + 1):
            try:
                idx = _index(raw(lg.season, f"week:{wk}", current_week=current_week, **kw))
            except Exception:  # noqa: BLE001
                continue
            if not any(s for s, _, _ in idx.values()):
                continue
            got += 1
            for pid, (stats, pos, _o) in idx.items():
                total[pid] = total.get(pid, 0.0) + scoring.score_player(stats, sc, pos)
        if got:
            return total, opp
        # fallback: pro-rate the season projection
        season_pts, _ = points(lg, "season", current_week=current_week, **kw)
        frac = max(0.0, (LAST_WEEK - current_week + 1) / LAST_WEEK)
        return {p: v * frac for p, v in season_pts.items()}, {}

    idx = _index(raw(lg.season, horizon, current_week=current_week, **kw))
    pts = {pid: scoring.score_player(stats, sc, pos) for pid, (stats, pos, _o) in idx.items()}
    opp = {pid: o for pid, (_s, _p, o) in idx.items()}
    return pts, opp


def diagnostics(lg, records) -> dict:
    """Scoring keys this league uses that we cannot compute. Printed, not hidden."""
    return scoring.unscored_keys(lg.scoring, stat_keys(records))
