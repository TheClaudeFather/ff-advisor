"""Replacement level, VOR, and tiers - derived from league shape, never hardcoded.

No magic numbers like "RB24". Replacement level falls out of roster_positions x
n_teams, so a 17-team SUPER_FLEX league and a 10-team 1-QB league both get
correct answers from the same code.
"""
from __future__ import annotations

from collections import Counter

CORE = ("QB", "RB", "WR", "TE")


def replacement_points(points, pos_of, lg) -> tuple[dict, dict]:
    """-> ({pos: replacement_points}, {pos: confidence_note})

    1. base[pos]  = n_teams * dedicated starting slots at pos
    2. flex       = pool everyone below their base cutoff, take the top
                    n_teams * flex_slots, count by position, add to base
    3. replacement = points of the player at that index
    """
    n = lg.n_teams
    slots = lg.starter_slots
    dedicated = Counter(s for s in slots if s in CORE or s in ("K", "DEF"))
    flex_slots = [s for s in slots if s not in CORE and s not in ("K", "DEF")]

    by_pos = {}
    for pid, p in points.items():
        pos = pos_of.get(pid)
        if pos:
            by_pos.setdefault(pos, []).append(p)
    for v in by_pos.values():
        v.sort(reverse=True)

    base = {pos: n * dedicated.get(pos, 0) for pos in by_pos}

    # Flex allocation: who actually wins the flex spots.
    # Each flex TYPE is allocated separately against only the positions it
    # accepts. Pooling them is wrong: a quarterback can fill SUPER_FLEX but not
    # FLEX, so lumping the two lets quarterbacks win slots they cannot occupy.
    leftovers = []
    for pos, vals in by_pos.items():
        if pos in ("K", "DEF"):
            continue
        leftovers += [(v, pos) for v in vals[base.get(pos, 0):]]
    leftovers.sort(reverse=True)

    by_type = Counter(flex_slots)
    # Most restrictive first, so narrow slots claim their players before the
    # permissive ones take the pool.
    for slot in sorted(by_type, key=lambda s: len(lg.slot_positions(s))):
        capacity = by_type[slot] * n
        ok = lg.slot_positions(slot)
        picked, rest = [], []
        for v, pos in leftovers:
            if len(picked) < capacity and pos in ok:
                picked.append((v, pos))
            else:
                rest.append((v, pos))
        for _v, pos in picked:
            base[pos] = base.get(pos, 0) + 1
        leftovers = rest

    repl, notes = {}, {}
    for pos, vals in by_pos.items():
        idx = base.get(pos, 0)
        if not vals:
            repl[pos], notes[pos] = 0.0, "no projections"
            continue
        if idx >= len(vals):
            # League starts more of this position than the projected pool holds.
            # Clamp rather than emit garbage, and say so.
            idx = max(0, int(len(vals) * 0.9) - 1)
            notes[pos] = (f"low confidence: league starts ~{base.get(pos,0)} {pos} "
                          f"but only {len(vals)} are projected")
        repl[pos] = vals[min(idx, len(vals) - 1)]
    return repl, notes


def _flex_eligible(lg, flex_slots) -> set:
    out = set()
    for s in flex_slots:
        out |= lg.slot_positions(s)
    return out


def vor(points, pos_of, repl) -> dict:
    return {pid: round(p - repl.get(pos_of.get(pid), 0.0), 2)
            for pid, p in points.items() if pos_of.get(pid)}


def tiers(ranked, gap_factor=1.0) -> list:
    """Assign tier numbers by finding drop-offs larger than the mean gap."""
    if len(ranked) < 3:
        return [1] * len(ranked)
    vals = [v for _p, v in ranked]
    gaps = [vals[i] - vals[i + 1] for i in range(len(vals) - 1)]
    mean_gap = sum(gaps) / len(gaps)
    threshold = mean_gap * (1 + gap_factor)
    out, t = [1], 1
    for g in gaps:
        if g > threshold:
            t += 1
        out.append(t)
    return out
