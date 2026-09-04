"""Compare forced-position picks against the tool's own choice.

Runs the same simulated draft repeatedly with the same opponents and seed,
forcing a position at chosen picks, and reports the cost in projected starting
lineup points, which is what actually matters, not the sum of VOR drafted.
"""
from __future__ import annotations

import random
import sys
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from sleeper import config, league as league_mod, players
from sleeper.advice import board as board_mod
from sleeper.advice import draft_advice
from sleeper.draft import DraftState, my_picks
from sleeper.lineup import optimal_lineup

ALIAS = sys.argv[1] if len(sys.argv) > 1 else None   # None -> default league
SLOT = int(sys.argv[2]) if len(sys.argv) > 2 else 1
SEED = int(sys.argv[3]) if len(sys.argv) > 3 else 7


def run(force: dict, lg, rows, db):
    """force: {pick_no: 'RB'} -> take the best available of that position."""
    random.seed(SEED)
    teams, rounds = lg.n_teams, len(lg.roster_positions)
    mine = set(my_picks(SLOT, teams, rounds))
    by_adp = sorted([r for r in rows if r["adp"] is not None], key=lambda r: r["adp"])
    pos_of = {r["player_id"]: r["pos"] for r in rows}
    pts_of = {r["player_id"]: r["pts"] for r in rows}

    picks, taken, my_roster, log = [], set(), [], []
    for overall in range(1, teams * rounds + 1):
        if overall in mine:
            st = DraftState("m", teams, rounds, SLOT, list(picks))
            recs, _ = draft_advice.advise(lg, st, top=40, offline=True)
            want = force.get(overall)
            choice = None
            if want:
                choice = next((r for r in recs if r["pos"] == want), None)
            if choice is None:
                choice = recs[0]
            log.append((overall, choice))
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

    lu = optimal_lineup(set(my_roster), pts_of, pos_of, lg.starter_slots, lg.slot_positions)
    return my_roster, lu, log, pos_of, pts_of


def main():
    cfg = config.load()
    lg = league_mod.load(config.resolve_league(cfg, ALIAS), offline=True)
    rows, _ = board_mod.build(lg, offline=True)
    db = players.load(offline=True)
    name = {r["player_id"]: r["name"] for r in rows}

    variants = {
        "baseline (tool's own picks)": {},
        "force RB at 37": {37: "RB"},
        "force RB at 66": {66: "RB"},
        "force RB at 37 and 66": {37: "RB", 66: "RB"},
        "force RB at 32 (instead of QB2)": {32: "RB"},
    }

    base_total = None
    print(f"{lg.name} — slot {SLOT} of {lg.n_teams}, projected STARTING LINEUP points\n")
    for label, force in variants.items():
        roster, lu, log, pos_of, pts_of = run(force, lg, rows, db)
        if base_total is None:
            base_total = lu.total
        delta = lu.total - base_total
        shape = "".join(f"{k}{v}" for k, v in sorted(Counter(pos_of[p] for p in roster).items()))
        print(f"{label:<34} lineup {lu.total:>7.1f}  ({delta:+6.1f})  {shape}")
        changed = [(o, c) for o, c in log if o in force]
        for o, c in changed:
            print(f"    pick {o}: took {c['name']} ({c['pos']}, {c['pts']} pts)")
        rbs = sorted([(pts_of[p], name[p]) for p in roster if pos_of[p] == "RB"], reverse=True)
        print(f"    starting-calibre RBs: {', '.join(f'{n} {v:.0f}' for v, n in rbs[:2])}")
        print()


if __name__ == "__main__":
    main()
