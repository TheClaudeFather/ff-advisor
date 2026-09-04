"""One-shot draft recommendation. Must be fast: no cold fetches on this path."""
from __future__ import annotations

import math
from collections import Counter

from .. import draft as draft_mod
from .. import lineup as lineup_mod
from . import board as board_mod

# How hard positional need pushes, as the roster fills. Early rounds are
# effectively pure VOR; later rounds must cover empty starting slots.
NEED_RAMP = 0.55

# Positions that are streamable week to week and not worth an early pick or a
# backup. Standard practice is to take exactly one of each in the last rounds.
STREAMABLE = frozenset({"K", "DEF"})
LATE_ROUNDS = 2

# How much raw value over replacement counts once the starting lineup is full.
BENCH_WEIGHT = 0.35

# Each extra player at a position beyond what the roster can start multiplies
# that player's bench value by this. Without it the tool stacks the position
# with the lowest replacement level, because raw VOR rewards scarcity even
# when only one of them can ever start.
SATURATION_DECAY = 0.3

# Late bench picks are injury and bye insurance. Their value is not value over
# replacement, which is often negative, but raw points at a position where the
# roster is thin. Without this every late pick scores zero and the tool falls
# back to raw VOR, which stacks the scarcest position.
INSURANCE_WEIGHT = 0.02

# Subtracted from a candidate the roster has no room for. Large enough that a
# capped player never outranks a usable one, small enough that one still gets
# recommended when every remaining player is capped.
CAP_PENALTY = 10_000.0

# Sleeper publishes national one-quarterback ADP. In a SUPER_FLEX league every
# team wants two quarterbacks, so they go far earlier than that ADP implies and
# the survival estimate is optimistic to the point of being misleading.
SUPERFLEX_QB_ADP_SHIFT = 0.55

# Minimum odds a player must have of lasting until a pick for us to treat him
# as "available then" when estimating what we can still get later.
SURVIVAL_FLOOR = 0.5

# How many of our own turns ahead to look when asking "what can I still get
# later". Looking one pick ahead is too myopic: every turn concludes the
# position can wait, then concludes it again next turn, until the position is
# gone. That myopia cost about 105 projected lineup points in a simulated
# 17-team draft.
#
# This value is measured, not chosen: see scripts/tune_lookahead.py. Across
# four slots of a 17-team superflex league and three of a 10-team PPR league,
# 10 was best or tied everywhere.
#   17-team superflex: look 2 -> 2125.5,  needs-based -> 2156.7,  look 10 -> 2167.2
#   10-team PPR:      look 2 -> 2136.6,  needs-based -> 2156.0,  look 10 -> 2166.2
# Looking all the way to the last pick ties in the superflex league but is 12
# points worse in the PPR league, so it is not a free simplification.
#
# Caveat: the simulator's opponents draft by ADP, which drains scarce positions
# more predictably than real drafters, so treat 10 as a reasonable prior rather
# than an optimum.
import os
LOOKAHEAD_TURNS = int(os.environ.get("SLEEPER_LOOKAHEAD", "10"))


def advise(lg, state, *, top=8, offline=False):
    rows, meta = board_mod.build(lg, offline=offline)
    taken = state.taken
    avail = [r for r in rows if r["player_id"] not in taken]

    mine = state.my_roster()
    pos_of = {r["player_id"]: r["pos"] for r in rows}
    have = Counter(pos_of.get(p) for p in mine if pos_of.get(p))
    needs = draft_mod.roster_needs(lg.roster_positions, have)

    # positions that still fill an empty starting slot
    needed_pos = set()
    for slot in needs:
        needed_pos |= lg.slot_positions(slot) or {slot}

    rnd, _ = state.round_and_slot()
    progress = min(1.0, (rnd - 1) / max(1, state.rounds - 1))
    need_weight = NEED_RAMP * progress

    nxt = state.pick_after_next() or state.next_pick()
    best_by_pos = {}
    for r in avail:
        best_by_pos.setdefault(r["pos"], r)

    # Marginal value against a roster padded with replacement players. This is
    # what stops the tool stacking a position it can only start one of: plain
    # VOR does not know the roster is already full at that position.
    pts_by_id = {r["player_id"]: r["pts"] for r in rows}
    mine_set = set(mine)
    superflex = "SUPER_FLEX" in lg.starter_slots

    # Pick-aware replacement. The league-wide replacement level is what the
    # Nth best player at a position scores, but it is not what WE can still
    # get: sixteen other teams pick between our turns. In this league running
    # backs fall below the league-wide level well before our last six picks,
    # so padding empty slots with it assumes a player who will not exist, and
    # the scarce position gets undervalued. Pad with the best we can actually
    # expect to still be there instead, and never above the league-wide level.
    global_repl = meta["replacement"]
    # How far ahead to look when asking "what can I still get later". One pick
    # ahead is too myopic: every pick says the position can wait, and it says
    # so again next turn, until the position is gone. LOOKAHEAD_TURNS is set
    # from measurement, not taste - see scripts/mock_variant.py.
    horizon = LOOKAHEAD_TURNS
    later = state.nth_next_pick(horizon) or state.next_pick()
    repl = dict(global_repl)
    if later:
        best_left = {}
        for r in avail:
            a = r["adp"]
            if not a:
                continue
            if superflex and r["pos"] == "QB":
                a *= SUPERFLEX_QB_ADP_SHIFT
            if draft_mod.survival_prob(a, later) >= SURVIVAL_FLOOR:
                best_left[r["pos"]] = max(best_left.get(r["pos"], 0.0), r["pts"])
        for pos_key, value in best_left.items():
            if pos_key in repl:
                repl[pos_key] = min(repl[pos_key], value)

    rounds_left = state.rounds - rnd + 1
    starting_count = Counter(s for s in lg.starter_slots)

    # How many of each position the roster can realistically start. Flex slots
    # are shared, so each contributes a fraction to every eligible position.
    startable = {p: float(starting_count.get(p, 0)) for p in
                 ("QB", "RB", "WR", "TE", "K", "DEF")}
    for slot in lg.starter_slots:
        elig = lg.slot_positions(slot)
        if len(elig) > 1:
            for p in elig:
                startable[p] = startable.get(p, 0.0) + 1.0 / len(elig)

    scored = []
    spread = max(1.0, avail[0]["vor"] - avail[min(len(avail) - 1, 40)]["vor"])
    for r in avail[: max(120, top * 10)]:
        pos = r["pos"]
        mv = lineup_mod.marginal_over_replacement(
            mine_set, r["player_id"], pts_by_id, pos_of, lg, repl)
        adp = r["adp"]
        if superflex and pos == "QB" and adp:
            adp *= SUPERFLEX_QB_ADP_SHIFT
        surv = draft_mod.survival_prob(adp, nxt)
        urgency = (1 - surv) * 0.25 * spread if pos in needed_pos else 0.0

        # Bench value. Once every starting slot is filled, marginal value is
        # about zero for everyone, so without this the tool prefers a slightly
        # better kicker to a high-upside running back. VOR breaks that tie.
        excess = max(0.0, have.get(pos, 0) - startable.get(pos, 1.0))
        decay = SATURATION_DECAY ** excess
        if pos in STREAMABLE:
            bench = 0.0
        else:
            bench = (BENCH_WEIGHT * max(0.0, r["vor"]) * decay
                     + INSURANCE_WEIGHT * max(0.0, r["pts"]) * decay)

        score = mv + need_weight * urgency + bench

        # Kickers and defenses are streamable and high variance. Never carry a
        # backup, and do not spend a pick on one until the last rounds.
        # Roster-shape caps. These are penalties, not filters: at the end of a
        # draft every candidate can be capped, and returning no recommendation
        # while the clock runs is worse than returning a capped one.
        capped = False
        if pos in STREAMABLE:
            if have.get(pos, 0) >= starting_count.get(pos, 1):
                capped = True
            elif rounds_left > LATE_ROUNDS:
                score *= 0.02
        elif have.get(pos, 0) >= math.ceil(startable.get(pos, 1.0)) + 1:
            # Never carry more backups than the roster can use. A third
            # quarterback in a one-quarterback league wastes a bench spot that
            # a running back or receiver would fill better.
            capped = True
        if capped:
            score -= CAP_PENALTY

        scored.append({**r, "mv": round(mv, 1), "capped": capped,
                       "score": round(score, 1),
                       "need": pos in needed_pos,
                       "surv": round(surv * 100)})
    scored.sort(key=lambda r: -r["score"])
    return scored[:top], {"needs": needs, "have": dict(have), "meta": meta,
                          "superflex": superflex,
                          "next_pick": state.next_pick(),
                          "pick_after": state.pick_after_next(),
                          "round": rnd}
