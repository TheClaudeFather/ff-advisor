"""Looking ahead: the weeks where a slot has nobody to fill it.

Byes have to be derived. Sleeper's player payload carries no usable bye_week,
and the weekly projection feed lists every team in every week, so a bye cannot
be found by a team going missing from the feed. What does identify one is the
whole team projecting nothing: in week 6 of 2026 exactly three teams total
under a point while the rest total 80 to 110.
"""
from __future__ import annotations

from collections import defaultdict

from .. import lineup as lineup_mod

# A whole team's projected points below this means nobody is playing. It is not
# zero because a player who changed teams mid-season leaves a trace on his old
# one: Minnesota totalled 0.2 in its 2026 bye week.
BYE_THRESHOLD = 1.0


def teams_on_bye(records, *, threshold=BYE_THRESHOLD) -> set:
    """Which teams are not playing, from one week's projection feed."""
    totals = defaultdict(float)
    for r in records:
        team = (r.get("player") or {}).get("team")
        if team:
            totals[team] += (r.get("stats") or {}).get("pts_ppr") or 0.0
    return {team for team, pts in totals.items() if pts < threshold}


def outlook(lg, roster, weekly_points: dict, pos_of: dict, byes: dict,
            team_of: dict) -> list:
    """Week by week: the best lineup available, and what is missing from it.

    `weekly_points` is {week: {player_id: points}} and `byes` is
    {week: {team}}, both already fetched, so this stays a pure function.
    """
    rows = []
    for week in sorted(weekly_points):
        points = weekly_points[week]
        out = byes.get(week, set())
        best = lineup_mod.optimal_lineup(roster.active, points, pos_of,
                                         lg.starter_slots, lg.slot_positions)
        rows.append({
            "week": week,
            "total": best.total,
            # No eligible player at all. Rare, and it means you must add one.
            "unfilled": best.unfilled,
            # Worse than empty in practice: the slot looks filled and scores
            # nothing, because the only player eligible for it is on a bye.
            "hollow": [[slot, pid] for slot, pid, value in best.starters
                       if value <= 0.0],
            "on_bye": [p for p in roster.active
                       if team_of.get(p) and team_of[p] in out],
            "starters": [list(s) for s in best.starters],
        })
    return rows
