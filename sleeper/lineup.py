"""Optimal lineup + marginal value.

marginal_value is the unifying primitive for in-season decisions:
  add    = optimal(roster + candidate) - optimal(roster)
  drop   = optimal(roster) - optimal(roster - player)
Both automatically respect roster construction, so a WR3-quality free agent
is worth ~0 if you already start four good WRs, but a lot if your TE slot is
a hole. Start/sit is just optimal(roster) read out directly.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Lineup:
    starters: list          # [(slot, player_id, points)]
    bench: list             # [(player_id, points)]
    total: float
    unfilled: list          # slots with nobody eligible


def is_laminar(slots, elig) -> bool:
    """Greedy most-restrictive-first is optimal iff eligibility sets are laminar
    (every pair nested or disjoint). True for standard and SUPER_FLEX leagues."""
    sets = {frozenset(elig(s)) for s in slots}
    for a in sets:
        for b in sets:
            if a is b:
                continue
            inter = a & b
            if inter and inter != a and inter != b:
                return False
    return True


def optimal_lineup(player_ids, points, pos_of, slots, elig) -> Lineup:
    """Fill `slots` to maximise total projected points.

    Assigns most-restrictive slots first, which is optimal for laminar
    eligibility families (checked by is_laminar).
    """
    avail = sorted(
        (pid for pid in player_ids if pos_of.get(pid)),
        key=lambda p: -points.get(p, 0.0),
    )
    used, starters, unfilled = set(), [], []

    order = sorted(range(len(slots)), key=lambda i: len(elig(slots[i])) or 99)
    filled = {}
    for i in order:
        slot = slots[i]
        ok = elig(slot)
        pick = next((p for p in avail
                     if p not in used and pos_of.get(p) in ok), None)
        if pick is None:
            unfilled.append(slot)
        else:
            used.add(pick)
            filled[i] = (slot, pick, points.get(pick, 0.0))

    for i in range(len(slots)):
        if i in filled:
            starters.append(filled[i])

    bench = [(p, points.get(p, 0.0)) for p in avail if p not in used]
    return Lineup(starters, bench, round(sum(s[2] for s in starters), 2), unfilled)


def marginal_value(roster_ids, candidate, points, pos_of, slots, elig) -> float:
    """How much adding `candidate` improves the optimal starting lineup."""
    base = optimal_lineup(roster_ids, points, pos_of, slots, elig).total
    with_c = optimal_lineup(set(roster_ids) | {candidate}, points, pos_of, slots, elig).total
    return round(with_c - base, 2)


def drop_cost(roster_ids, player, points, pos_of, slots, elig) -> float:
    """How much removing `player` costs the optimal lineup. Lower = safer drop."""
    base = optimal_lineup(roster_ids, points, pos_of, slots, elig).total
    without = optimal_lineup(set(roster_ids) - {player}, points, pos_of, slots, elig).total
    return round(base - without, 2)


def marginal_over_replacement(roster_ids, candidate, points, pos_of, lg, repl) -> float:
    """Value a candidate adds to a roster whose empty slots hold replacement players.

    Plain VOR compares players across positions but does not know the roster is
    already full at a position. A fifth tight end still shows a high VOR even
    though only one can start. Padding the empty starting slots with
    replacement-level players fixes both cases at once:

      empty roster  -> adding a player displaces a replacement, so the gain
                       equals his VOR, which is the correct draft-day ranking.
      saturated pos -> he displaces nobody, so the gain falls to about zero.
    """
    pts = dict(points)
    pos = dict(pos_of)
    ids = set(roster_ids)
    slots = lg.starter_slots

    for p, value in repl.items():
        count = sum(1 for s in slots if p in lg.slot_positions(s))
        for i in range(count):
            sid = f"__repl_{p}_{i}"
            pts[sid] = value
            pos[sid] = p
            ids.add(sid)

    base = optimal_lineup(ids, pts, pos, slots, lg.slot_positions).total
    with_c = optimal_lineup(ids | {candidate}, pts, pos, slots, lg.slot_positions).total
    return round(with_c - base, 2)
