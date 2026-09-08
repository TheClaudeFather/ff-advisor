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
    """The fraction of the season still to be played, counting this week.

    Used only when a player's team is unknown. Prefer remaining_share, which
    counts games rather than weeks.
    """
    return max(0.0, (LAST_WEEK - current_week + 1) / LAST_WEEK)


def remaining_share(games, current_week: int, *, last_week=LAST_WEEK) -> dict:
    """{team: fraction of its games still to play}.

    Weeks and games are not the same thing once byes start. A player whose bye
    has passed has more football left than one whose bye is ahead, and a flat
    weekly scale credits them equally.
    """
    played, left = {}, {}
    for g in games:
        week = g.get("week")
        if week is None or week > last_week:
            continue
        for team in {g.get("home"), g.get("away")} - {None}:
            played[team] = played.get(team, 0) + 1
            if week >= current_week:
                left[team] = left.get(team, 0) + 1
    return {team: (left.get(team, 0) / total if total else 0.0)
            for team, total in played.items()}


def scale_to_remaining(season_points: dict, team_of: dict, games,
                       current_week: int, *, last_week=LAST_WEEK) -> dict:
    """Season points -> what is left, team by team.

    A player whose team is not in the schedule falls back to the flat weekly
    share, which is wrong by a few percent rather than wrong by a whole season.
    """
    share = remaining_share(games, current_week, last_week=last_week)
    flat = max(0.0, (last_week - current_week + 1) / last_week)
    return {pid: value * share.get(team_of.get(pid), flat)
            for pid, value in season_points.items()}


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
        records = raw(lg.season, "season", current_week=current_week, **kw)
        idx = _index(records)
        season_pts = {pid: scoring.score_player(stats, sc, pos)
                      for pid, (stats, pos, _o) in idx.items()}
        team_of = {r.get("player_id"): (r.get("player") or {}).get("team")
                   for r in records}
        try:
            games = api.schedule(lg.season, **kw)
        except Exception:  # noqa: BLE001 - a flat scale beats no answer
            games = []
        if not games:
            share = ros_share(current_week)
            return {p: v * share for p, v in season_pts.items()}, {}
        return scale_to_remaining(season_pts, team_of, games, current_week), {}

    idx = _index(raw(lg.season, horizon, current_week=current_week, **kw))
    pts = {pid: scoring.score_player(stats, sc, pos) for pid, (stats, pos, _o) in idx.items()}
    opp = {pid: o for pid, (_s, _p, o) in idx.items()}
    return pts, opp


def diagnostics(lg, records) -> dict:
    """Scoring keys this league uses that we cannot compute. Printed, not hidden."""
    return scoring.unscored_keys(lg.scoring, stat_keys(records))
