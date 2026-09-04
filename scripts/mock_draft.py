"""Mock draft rehearsal: simulate a full snake draft through the REAL advise path.

Opponents pick by ADP with noise. At each of our picks we call the same
draft_advice.advise() the live tool calls, then take its top recommendation.
Asserts the invariants that matter on draft day.
"""
from __future__ import annotations

import random
import sys
import time
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from sleeper import config, league as league_mod, players
from sleeper.advice import board as board_mod
from sleeper.advice import draft_advice
from sleeper.draft import DraftState, my_picks
from sleeper.league import SLOT_ELIGIBILITY, NON_STARTER

ALIAS = sys.argv[1] if len(sys.argv) > 1 else None   # None -> default league
SLOT = int(sys.argv[2]) if len(sys.argv) > 2 else 1
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 7


def run(quiet=False):
    random.seed(SEED)
    cfg = config.load()
    lg = league_mod.load(config.resolve_league(cfg, ALIAS), offline=True)
    rows, _meta = board_mod.build(lg, offline=True)
    db = players.load(offline=True)

    teams = lg.n_teams
    rounds = len(lg.roster_positions)
    mine = set(my_picks(SLOT, teams, rounds))
    total = teams * rounds

    by_adp = sorted([r for r in rows if r["adp"] is not None], key=lambda r: r["adp"])
    pos_of = {r["player_id"]: r["pos"] for r in rows}

    picks, taken = [], set()
    my_roster, timings, recs_log = [], [], []

    for overall in range(1, total + 1):
        if overall in mine:
            st = DraftState("mock", teams, rounds, SLOT, list(picks))
            t0 = time.time()
            recs, info = draft_advice.advise(lg, st, top=5, offline=True)
            timings.append(time.time() - t0)

            assert recs, f"no recommendation at overall {overall}"
            for r in recs:
                assert r["player_id"] not in taken, \
                    f"RECOMMENDED A TAKEN PLAYER at {overall}: {r['name']}"
            assert st.is_my_turn(), f"slot math wrong at {overall}"
            assert st.next_pick() == overall

            choice = recs[0]
            recs_log.append((overall, st.round_and_slot()[0], choice, info["needs"]))
            my_roster.append(choice["player_id"])
            pid = choice["player_id"]
        else:
            pool = [r for r in by_adp if r["player_id"] not in taken][:4]
            if not pool:
                break
            pid = random.choice(pool)["player_id"]

        taken.add(pid)
        picks.append({"pick_no": overall, "player_id": pid,
                      "round": (overall - 1) // teams + 1})

    # ---- invariants ----
    assert len(my_roster) == rounds, f"got {len(my_roster)} picks, expected {rounds}"
    assert len(set(my_roster)) == rounds, "drafted a duplicate player"

    have = Counter(pos_of[p] for p in my_roster)
    starters = [s for s in lg.roster_positions if s not in NON_STARTER]
    remaining = Counter(have)
    unfilled = []
    for slot in sorted(starters, key=lambda s: len(SLOT_ELIGIBILITY.get(s, set())) or 99):
        ok = SLOT_ELIGIBILITY.get(slot, set())
        hit = next((p for p in ok if remaining.get(p, 0) > 0), None)
        if hit:
            remaining[hit] -= 1
        else:
            unfilled.append(slot)

    if quiet:
        return dict(have), unfilled, max(timings)
    print(f"MOCK DRAFT — {lg.name}, slot {SLOT} of {teams}, {rounds} rounds\n")
    print(f"{'pick':<7}{'rd':<4}{'player':<22}{'pos':<5}{'VOR':<8}needs before")
    print("-" * 88)
    for overall, rnd, c, needs in recs_log:
        need_s = " ".join(f"{k}{v}" for k, v in sorted(needs.items())) or "(none)"
        print(f"{overall:<7}{rnd:<4}{c['name']:<22}{c['pos']:<5}{c['vor']:<8}{need_s}")

    print(f"\nfinal roster: {dict(have)}")
    print(f"unfilled starting slots: {unfilled or 'NONE'}")
    print(f"advise() timing: max {max(timings):.2f}s  mean {sum(timings)/len(timings):.2f}s")

    assert not unfilled, f"FAILED: could not field a legal lineup, missing {unfilled}"
    assert max(timings) < 1.5, f"FAILED: too slow on the clock ({max(timings):.2f}s)"
    print("\nALL INVARIANTS PASSED")


if __name__ == "__main__":
    run()
