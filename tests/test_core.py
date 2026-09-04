"""Unit tests for the scoring / lineup / valuation core. No network."""
import json
import pathlib
from collections import Counter

from sleeper import scoring
from sleeper.league import League
from sleeper.lineup import is_laminar, marginal_value, optimal_lineup, drop_cost
from sleeper.valuation import replacement_points, tiers

FIX = pathlib.Path(__file__).parent / "fixtures"
PPR = json.loads((FIX / "league_ppr_10team.json").read_text())["scoring_settings"]


def test_score_line_hand_computed():
    # 100 rush yds, 1 rush TD, 5 rec, 50 rec yds  in the 10-team PPR fixture scoring
    stats = {"rush_yd": 100, "rush_td": 1, "rec": 5, "rec_yd": 50}
    # 100*.1 + 1*6 + 5*1 + 50*.1 = 10 + 6 + 5 + 5 = 26
    assert scoring.score_line(stats, scoring.scoreable(PPR)) == 26.0


def test_score_line_ignores_unknown_keys():
    assert scoring.score_line({"not_a_stat": 999}, scoring.scoreable(PPR)) == 0.0


def test_bonus_keys_excluded():
    """Threshold bonuses must not be multiplied by a projected mean."""
    sc = {"rec_yd": 0.1, "bonus_rec_yd_100": 3.0}
    assert "bonus_rec_yd_100" not in scoring.scoreable(sc)
    assert scoring.score_line({"rec_yd": 70, "bonus_rec_yd_100": 0.4},
                              scoring.scoreable(sc)) == 7.0


def test_k_def_use_pts_ppr_fallback():
    assert scoring.score_player({"pts_ppr": 8.5}, PPR, "K") == 8.5
    assert scoring.score_player({"pts_ppr": 9.0}, PPR, "DEF") == 9.0


def _lg(slots, teams=10):
    return League("x", "x", PPR, slots, teams, "2026")


def test_optimal_lineup_fills_flex_with_best_leftover():
    lg = _lg(["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN"])
    pos = {"q": "QB", "r1": "RB", "r2": "RB", "r3": "RB",
           "w1": "WR", "w2": "WR", "t": "TE"}
    pts = {"q": 20, "r1": 15, "r2": 12, "r3": 14, "w1": 11, "w2": 10, "t": 9}
    lu = optimal_lineup(set(pos), pts, pos, lg.starter_slots, lg.slot_positions)
    # Which RB is labelled FLEX vs RB is arbitrary and fungible; what must be
    # true is that the three best RBs all start and the total is maximal.
    started = {s[1] for s in lu.starters}
    assert {"r1", "r2", "r3"} <= started
    assert [s[0] for s in lu.starters].count("FLEX") == 1
    assert lu.total == 20 + 15 + 14 + 12 + 11 + 10 + 9


def test_optimal_lineup_flex_prefers_higher_scorer_across_positions():
    """When flex candidates differ by position, the best one must start."""
    lg = _lg(["RB", "WR", "FLEX"])
    pos = {"r1": "RB", "r2": "RB", "w1": "WR", "te1": "TE"}
    pts = {"r1": 20, "r2": 8, "w1": 15, "te1": 12}
    lu = optimal_lineup(set(pos), pts, pos, lg.starter_slots, lg.slot_positions)
    flex = [s for s in lu.starters if s[0] == "FLEX"][0]
    assert flex[1] == "te1"          # 12 > r2's 8
    assert lu.total == 20 + 15 + 12


def test_superflex_puts_qb_in_flex():
    lg = _lg(["QB", "SUPER_FLEX", "RB"])
    pos = {"q1": "QB", "q2": "QB", "r1": "RB"}
    pts = {"q1": 25, "q2": 22, "r1": 10}
    lu = optimal_lineup(set(pos), pts, pos, lg.starter_slots, lg.slot_positions)
    assert {s[1] for s in lu.starters} == {"q1", "q2", "r1"}


def test_unfilled_slot_reported():
    lg = _lg(["QB", "TE"])
    lu = optimal_lineup({"q"}, {"q": 10}, {"q": "QB"}, lg.starter_slots, lg.slot_positions)
    assert lu.unfilled == ["TE"]


def test_marginal_value_reflects_roster_construction():
    """A WR is worth ~0 if WR slots are stacked, but a lot if TE is empty."""
    lg = _lg(["WR", "WR", "TE"])
    pos = {"w1": "WR", "w2": "WR", "w3": "WR", "cand_wr": "WR", "cand_te": "TE"}
    pts = {"w1": 20, "w2": 19, "w3": 18, "cand_wr": 17, "cand_te": 8}
    roster = {"w1", "w2", "w3"}
    wr_gain = marginal_value(roster, "cand_wr", pts, pos, lg.starter_slots, lg.slot_positions)
    te_gain = marginal_value(roster, "cand_te", pts, pos, lg.starter_slots, lg.slot_positions)
    assert wr_gain == 0.0          # already start the two best WRs
    assert te_gain == 8.0          # fills an empty slot
    assert te_gain > wr_gain


def test_drop_cost_prefers_redundant_player():
    lg = _lg(["WR", "TE"])
    pos = {"w1": "WR", "w2": "WR", "t": "TE"}
    pts = {"w1": 20, "w2": 5, "t": 9}
    roster = set(pos)
    assert drop_cost(roster, "w2", pts, pos, lg.starter_slots, lg.slot_positions) == 0.0
    assert drop_cost(roster, "t", pts, pos, lg.starter_slots, lg.slot_positions) == 9.0


def test_laminar_holds_for_both_real_leagues():
    for f in ("league_ppr_10team.json", "league_superflex_17team.json"):
        d = json.loads((FIX / f).read_text())
        lg = League("x", d["name"], d["scoring_settings"], d["roster_positions"],
                    d["settings"]["num_teams"], d["season"])
        assert is_laminar(lg.starter_slots, lg.slot_positions), f


def test_replacement_level_superflex_lifts_qb():
    """The regression that would prove hardcoding crept in."""
    pos = {}
    pts = {}
    for i in range(60):
        pos[f"qb{i}"] = "QB"; pts[f"qb{i}"] = 300 - i * 4
        pos[f"rb{i}"] = "RB"; pts[f"rb{i}"] = 280 - i * 4
        pos[f"wr{i}"] = "WR"; pts[f"wr{i}"] = 270 - i * 3
        pos[f"te{i}"] = "TE"; pts[f"te{i}"] = 200 - i * 5
    one_qb = _lg(["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX"])
    sflex = _lg(["QB", "SUPER_FLEX", "RB", "RB", "WR", "WR", "TE", "FLEX"])
    r1, _ = replacement_points(pts, pos, one_qb)
    r2, _ = replacement_points(pts, pos, sflex)
    # superflex consumes far more QBs -> replacement QB is much worse -> QB VOR higher
    assert r2["QB"] < r1["QB"], (r1["QB"], r2["QB"])


def test_replacement_flags_low_confidence_when_pool_too_thin():
    pos = {f"qb{i}": "QB" for i in range(5)}
    pts = {f"qb{i}": 100 - i for i in range(5)}
    lg = _lg(["QB", "SUPER_FLEX"], teams=17)
    _r, notes = replacement_points(pts, pos, lg)
    assert "QB" in notes and "low confidence" in notes["QB"]


def test_tiers_increase_monotonically():
    ranked = [("a", 100), ("b", 98), ("c", 60), ("d", 58)]
    t = tiers(ranked)
    assert t[0] == 1 and t[-1] >= t[0]
    assert all(t[i] <= t[i + 1] for i in range(len(t) - 1))
