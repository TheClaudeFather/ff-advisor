"""Waiver adds and drops.

One primitive answers both: how much the optimal lineup changes. An add is what
a player would improve it by, a drop is what removing him would cost. Ranking
free agents by raw points instead keeps recommending a fourth receiver to a
roster that already starts three, which is exactly the failure the draft tool
had before its score became roster-aware.
"""
from __future__ import annotations

from .. import lineup as lineup_mod
from .inseason import best_available


def prefilter(points: dict, pos_of: dict, free_ids, *, per_pos=25) -> list:
    """The top free agents at each position, best first.

    marginal_value re-solves the lineup for every candidate, so running it over
    a couple of thousand free agents is wasted work. Within a position, value
    is monotone in points, so the tail cannot win.
    """
    by_pos = {}
    for pid in free_ids:
        pos = pos_of.get(pid)
        if pos:
            by_pos.setdefault(pos, []).append(pid)
    kept = []
    for pos, ids in by_pos.items():
        ids.sort(key=lambda p: -points.get(p, 0.0))
        kept.extend(ids[:per_pos])
    kept.sort(key=lambda p: -points.get(p, 0.0))
    return kept


def _cheapest_drop(lg, active, points, pos_of, protect=()) -> dict:
    """The player whose loss the lineup would miss least."""
    best = None
    for pid in active:
        if pid in protect:
            continue
        cost = lineup_mod.drop_cost(active, pid, points, pos_of,
                                    lg.starter_slots, lg.slot_positions)
        if best is None or cost < best["cost"]:
            best = {"player_id": pid, "cost": cost}
    return best or {"player_id": None, "cost": 0.0}


def waiver_targets(lg, roster, points, pos_of, free_ids, *, top=10,
                   per_pos=25) -> list:
    """Free agents ranked by what they would add to this lineup."""
    active = roster.active
    wire = best_available(points, pos_of, free_ids)
    drop = _cheapest_drop(lg, active, points, pos_of)

    rows = []
    for pid in prefilter(points, pos_of, free_ids, per_pos=per_pos):
        marginal = lineup_mod.marginal_value(active, pid, points, pos_of,
                                             lg.starter_slots, lg.slot_positions)
        pos = pos_of.get(pid)
        over_wire = round(points.get(pid, 0.0)
                          - wire.get(pos, (None, 0.0))[1], 2)
        rows.append({
            "player_id": pid,
            "pos": pos,
            "pts": round(points.get(pid, 0.0), 2),
            "marginal": marginal,
            "over_wire": over_wire,
            "drop": drop,
            "net": round(marginal - drop["cost"], 2),
        })

    # A full roster makes almost every candidate worth zero, so the second key
    # decides the order people actually read. It cannot be raw points: a
    # kicker's season total is not comparable to a tight end's, and sorting by
    # it put four kickers at the top of a real league's list. Distance above
    # the best free agent at the same position is comparable.
    rows.sort(key=lambda r: (-r["marginal"], -r["over_wire"]))
    return rows[:top]


def drop_ranking(lg, roster, points, pos_of, free_ids) -> list:
    """Every rostered player, safest to drop first."""
    active = roster.active
    starting = set(roster.starters)
    reserve = set(roster.reserve) | set(roster.taxi)
    wire = best_available(points, pos_of, free_ids)

    rows = []
    for pid in roster.players:
        cost = lineup_mod.drop_cost(active, pid, points, pos_of,
                                    lg.starter_slots, lg.slot_positions)
        without = lineup_mod.optimal_lineup(
            [p for p in active if p != pid], points, pos_of,
            lg.starter_slots, lg.slot_positions)
        pos = pos_of.get(pid)
        rows.append({
            "player_id": pid,
            "pos": pos,
            "pts": round(points.get(pid, 0.0), 2),
            "cost": cost,
            # Dropping him would leave a slot nobody on the roster can fill.
            "breaks_lineup": bool(without.unfilled),
            "starting": pid in starting,
            "reserve": pid in reserve,
            "vs_wire": round(points.get(pid, 0.0)
                             - wire.get(pos, (None, 0.0))[1], 2),
        })

    rows.sort(key=lambda r: (r["breaks_lineup"], r["starting"], r["cost"],
                             r["vs_wire"]))
    return rows
