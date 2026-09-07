"""Elimination leagues: how close you are to the cut.

In a guillotine league the lowest score each week is removed and that roster
returns to free agency, so the question is not whether you win, it is whether
you clear the floor.

This reports a points margin, not odds. Odds need a distribution of weekly
scores and Sleeper publishes none, so calling a margin a probability would be
inventing precision. It also means expected points is only the right objective
while you are comfortable: a team projected last wants variance, and nothing
here models that.
"""
from __future__ import annotations

from .. import lineup as lineup_mod


def project_team(lg, roster, points, pos_of) -> dict:
    """What a team is expected to score this week.

    A team that has set its lineup is projected on what it set, even when that
    is not its best, because a manager who leaves points on the bench really
    does score less. A team that has set nothing is projected on its best
    available lineup, which is the fair assumption early in the week when most
    of a league has not touched anything.
    """
    best = lineup_mod.optimal_lineup(roster.active, points, pos_of,
                                     lg.starter_slots, lg.slot_positions)
    set_total = round(sum(points.get(p, 0.0) for p in roster.starters), 2)
    used_set = roster.set_lineup
    return {
        "roster_id": roster.roster_id,
        "owner_id": roster.owner_id,
        "rule": "set" if used_set else "optimal",
        "projected": set_total if used_set else best.total,
        "set_total": set_total,
        "optimal_total": best.total,
        "bench_left": round(set_total - best.total, 2) if used_set else 0.0,
        "unfilled": best.unfilled,
    }


def cut_margin(teams: list, my_roster_id, *, cut: int = 1) -> dict:
    """Rank the league and say how far you are from the cut line."""
    ranked = sorted(teams, key=lambda t: -t["projected"])
    # Lowest first: this is a list of who goes, not a continuation of the table.
    doomed = [t["roster_id"] for t in reversed(ranked[len(ranked) - cut:])] \
        if ranked else []

    mine = next((t for t in ranked if t["roster_id"] == my_roster_id), None)
    if mine is None:
        return {"ranked": ranked, "cut": doomed, "my_rank": None,
                "margin": None, "gap_to_safety": None, "at_risk": None}

    rank = ranked.index(mine) + 1
    at_risk = mine["roster_id"] in doomed
    survivors = [t for t in ranked if t["roster_id"] not in doomed]
    if at_risk:
        # How much more you need to climb out of the cut.
        lowest_safe = survivors[-1]["projected"] if survivors else mine["projected"]
        margin = round(mine["projected"] - lowest_safe, 2)
        gap = round(lowest_safe - mine["projected"], 2)
    else:
        highest_cut = max((t["projected"] for t in ranked
                           if t["roster_id"] in doomed), default=0.0)
        margin = round(mine["projected"] - highest_cut, 2)
        gap = 0.0
    return {"ranked": ranked, "cut": doomed, "my_rank": rank,
            "margin": margin, "gap_to_safety": gap, "at_risk": at_risk}
