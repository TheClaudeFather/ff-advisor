"""Looking ahead: the weeks where a slot has nobody to fill it.

Byes come from the schedule: a team with no game in a week is not playing.
Sleeper's player payload carries no usable bye_week, but the schedule endpoint
gives the whole season in 27KB and answers it exactly.

An earlier version inferred byes from the projection feed instead, treating a
team that projected under a point as idle. That was wrong: for week 6 of 2026
it found Cincinnati, Detroit and Minnesota but missed Miami, whose players
still carried projections while the team was on bye.
"""
from __future__ import annotations

from .. import lineup as lineup_mod


def bye_weeks(games) -> dict:
    """{week: {teams not playing}} from the season schedule."""
    playing, teams = {}, set()
    for g in games:
        week = g.get("week")
        if week is None:
            continue
        sides = {g.get("home"), g.get("away")} - {None}
        playing.setdefault(week, set()).update(sides)
        teams |= sides
    return {week: teams - active for week, active in playing.items()}


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
