"""Start/sit: the difference between the lineup you set and the best one.

Finding the best lineup is `lineup.optimal_lineup`. The work here is describing
the change in a way a person can act on, and being honest about what the
numbers do not know.
"""
from __future__ import annotations

from .. import league as league_mod
from .. import lineup as lineup_mod


def swaps(current_pairs, optimal, points) -> list:
    """Pair each promoted player with the one he replaces, at his slot.

    `current_pairs` is [(slot, player_id or None)] for the lineup as it stands.

    Only players entering or leaving the lineup count. Moving a player between
    two slots he is eligible for scores the same, so it is not a change worth
    reporting: acting on it does nothing.

    Pairing is by slot. Sorting the promoted players against the benched ones
    and zipping them produces advice like "bench your quarterback, start your
    tight end", which is not what the optimizer said. Whoever holds the slot
    the promoted player lands in is the one he replaces; if that person keeps
    his place elsewhere in the lineup, the cheapest player actually leaving is
    used instead.
    """
    starting = {pid for _s, pid in current_pairs if pid}
    keeping = {pid for _s, pid, _p in optimal.starters}
    by_slot = {}
    for slot, pid in current_pairs:
        by_slot.setdefault(slot, []).append(pid)

    leaving = sorted((p for p in starting if p not in keeping),
                     key=lambda p: points.get(p, 0.0))
    out = []
    for slot, pid, _pts in optimal.starters:
        if pid in starting:
            continue
        replaced = None
        for candidate in by_slot.get(slot, []):
            if candidate in leaving:
                replaced = candidate
                break
        if replaced is None and leaving:
            replaced = leaving[0]
        if replaced is not None:
            leaving.remove(replaced)
        out.append({
            "slot": slot,
            "out": replaced,
            "in": pid,
            "gain": round(points.get(pid, 0.0) - points.get(replaced, 0.0), 2),
        })
    return out


def _warnings(roster, points, pos_of) -> list:
    """Everything the lineup silently swallowed, said out loud.

    optimal_lineup drops any player it has no position for, and scores a player
    with no projection as zero. Both look identical to a person reading the
    output: their player is simply not there.
    """
    out = []
    for pid in roster.players:
        if not pos_of.get(pid):
            out.append({"code": "UNKNOWN_PLAYER", "player_id": pid,
                        "note": "not in the player database; run: sleeper refresh players"})
        elif pid not in points:
            out.append({"code": "NO_PROJ", "player_id": pid,
                        "note": "no projection published for this week"})
    return out


def _as_dict(ln) -> dict:
    return {"starters": [list(s) for s in ln.starters],
            "bench": [list(b) for b in ln.bench],
            "total": ln.total,
            "unfilled": ln.unfilled}


def advise(lg, roster, points, pos_of, db, *, week) -> dict:
    """The whole start/sit answer. Pure: every input is passed in."""
    slots, elig = lg.starter_slots, lg.slot_positions

    optimal = lineup_mod.optimal_lineup(roster.active, points, pos_of, slots, elig)
    current_pairs = league_mod.current_starters(lg, roster)
    current_total = round(
        sum(points.get(p, 0.0) for _s, p in current_pairs if p), 2)

    changes = swaps(current_pairs, optimal, points)
    return {
        "week": week,
        "league": lg.name,
        "league_id": lg.league_id,
        "roster_id": roster.roster_id,
        "current_total": current_total,
        "optimal_total": optimal.total,
        "gain": round(optimal.total - current_total, 2),
        "swaps": changes,
        "optimal": _as_dict(optimal),
        "warnings": _warnings(roster, points, pos_of),
        "names": {pid: (db.get(pid) or {}).get("name", pid)
                  for pid in roster.players},
    }
