"""Race three draft rankings on the outcome that matters: the lineup you field.

Our VOR is compared against the two things Sleeper actually provides, ADP and
the raw projection. The measure is projected starting lineup points, which is
not defined by our own replacement-level function, so it avoids the circularity
in comparing rankings against a realized VOR we computed ourselves.

Each ranker is run twice. "pure" takes the best available player by that metric.
"need-aware" restricts to positions that still fill an empty starting slot,
which is the minimum roster sense any real drafter applies.
"""
from __future__ import annotations

import random
import sys
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from sleeper import config, league as league_mod
from sleeper.advice import board as board_mod
from sleeper.advice import draft_advice
from sleeper.draft import DraftState, my_picks, roster_needs
from sleeper.lineup import optimal_lineup

SEED = 7


def draft(lg, rows, slot, ranker, need_aware):
    random.seed(SEED)
    teams, rounds = lg.n_teams, len(lg.roster_positions)
    mine = set(my_picks(slot, teams, rounds))
    by_adp = sorted([r for r in rows if r["adp"] is not None], key=lambda r: r["adp"])
    pos_of = {r["player_id"]: r["pos"] for r in rows}
    pts_of = {r["player_id"]: r["pts"] for r in rows}

    picks, taken, roster = [], set(), []
    for overall in range(1, teams * rounds + 1):
        if overall in mine:
            if ranker == "tool":
                st = DraftState("m", teams, rounds, slot, list(picks))
                recs, _ = draft_advice.advise(lg, st, top=1, offline=True)
                pid = recs[0]["player_id"]
            else:
                avail = [r for r in rows if r["player_id"] not in taken]
                if ranker == "adp":
                    avail = sorted([r for r in avail if r["adp"] is not None],
                                   key=lambda r: r["adp"])
                else:                                   # raw projection
                    avail = sorted(avail, key=lambda r: -r["pts"])
                if need_aware:
                    have = Counter(pos_of[p] for p in roster)
                    needs = roster_needs(lg.roster_positions, have)
                    want = set()
                    for slot_name in needs:
                        want |= lg.slot_positions(slot_name) or {slot_name}
                    if want:
                        avail = [r for r in avail if r["pos"] in want] or avail
                pid = avail[0]["player_id"]
            roster.append(pid)
        else:
            pool = [r for r in by_adp if r["player_id"] not in taken][:4]
            if not pool:
                break
            pid = random.choice(pool)["player_id"]
        taken.add(pid)
        picks.append({"pick_no": overall, "player_id": pid,
                      "round": (overall - 1) // teams + 1})

    lu = optimal_lineup(set(roster), pts_of, pos_of, lg.starter_slots, lg.slot_positions)
    shape = "".join(f"{k}{v}" for k, v in sorted(Counter(pos_of[p] for p in roster).items()))
    return lu.total, len(lu.unfilled), shape


def main():
    alias = sys.argv[1] if len(sys.argv) > 1 else "ffl1"
    slots = [int(x) for x in (sys.argv[2].split(",") if len(sys.argv) > 2 else ["1", "5", "9"])]
    cfg = config.load()
    lg = league_mod.load(config.resolve_league(cfg, alias), offline=True)
    rows, _ = board_mod.build(lg, offline=True)

    setups = [("our VOR (tool)", "tool", True),
              ("ADP, need-aware", "adp", True),
              ("raw proj, need-aware", "proj", True),
              ("ADP, pure", "adp", False),
              ("raw proj, pure", "proj", False)]

    print(f"{lg.name}: projected starting lineup points, higher is better\n")
    print(f"{'ranker':<24}" + "".join(f"slot {s:<7}" for s in slots) + "mean")
    base = {}
    for label, ranker, need in setups:
        totals = []
        line = f"{label:<24}"
        for s in slots:
            total, unfilled, _shape = draft(lg, rows, s, ranker, need)
            totals.append(total)
            mark = "*" if unfilled else " "
            line += f"{total:.1f}{mark}".ljust(11)
            base.setdefault(label, []).append((total, unfilled))
        line += f"{sum(totals)/len(totals):.1f}"
        print(line)
    print("\n(* = could not field a legal lineup at some slot)")
    for label, res in base.items():
        bad = sum(1 for _t, u in res if u)
        if bad:
            print(f"  {label}: illegal lineup at {bad} of {len(res)} slots")


if __name__ == "__main__":
    main()
