"""Flex slots must be allocated only to positions that can actually fill them.

Regression test for a bug that inflated RB and WR replacement levels in the
10-team league: the flex allocation pooled every leftover player, quarterbacks
included, took the top N, then discarded the ones that were not flex eligible.
Because quarterbacks outscore other positions in raw points they occupied 17 of
the 20 slots and were thrown away, so only 3 of 20 flex spots were allocated.
"""
import json
import pathlib

from sleeper.league import League
from sleeper.valuation import replacement_points

FIX = pathlib.Path(__file__).parent / "fixtures"
PPR = json.loads((FIX / "league_ppr_10team.json").read_text())["scoring_settings"]


def _pool():
    """Quarterbacks score highest, which is what triggered the bug."""
    pos, pts = {}, {}
    for i in range(60):
        pos[f"qb{i}"] = "QB"; pts[f"qb{i}"] = 400 - i * 2
        pos[f"rb{i}"] = "RB"; pts[f"rb{i}"] = 250 - i * 3
        pos[f"wr{i}"] = "WR"; pts[f"wr{i}"] = 240 - i * 3
        pos[f"te{i}"] = "TE"; pts[f"te{i}"] = 180 - i * 3
    return pos, pts


def _lg(slots, teams=10):
    return League("x", "x", PPR, slots, teams, "2026")


def test_qbs_do_not_consume_plain_flex_slots():
    pos, pts = _pool()
    lg = _lg(["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX"])
    repl, _ = replacement_points(pts, pos, lg)

    # 10 teams x 1 QB = 10 QBs start. The flex slots cannot hold a QB, so the
    # QB replacement index must stay at 10, not be pushed deeper.
    qb_sorted = sorted((v for k, v in pts.items() if pos[k] == "QB"), reverse=True)
    assert repl["QB"] == qb_sorted[10]


def test_flex_slots_are_actually_allocated():
    """20 flex slots must move RB/WR/TE replacement well past the dedicated cutoff."""
    pos, pts = _pool()
    lg = _lg(["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX"])
    repl, _ = replacement_points(pts, pos, lg)

    rb = sorted((v for k, v in pts.items() if pos[k] == "RB"), reverse=True)
    wr = sorted((v for k, v in pts.items() if pos[k] == "WR"), reverse=True)
    te = sorted((v for k, v in pts.items() if pos[k] == "TE"), reverse=True)
    # dedicated cutoffs are RB 20, WR 20, TE 10; flex must push at least one deeper
    deeper = ((repl["RB"] < rb[20]) + (repl["WR"] < wr[20]) + (repl["TE"] < te[10]))
    assert deeper >= 1, "flex slots were not allocated to anyone"

    # and the total extra depth allocated must equal the 20 flex slots
    extra = (rb.index(repl["RB"]) - 20) + (wr.index(repl["WR"]) - 20) + (te.index(repl["TE"]) - 10)
    assert extra == 20, f"allocated {extra} flex slots, expected 20"


def test_superflex_slots_do_go_to_qbs():
    pos, pts = _pool()
    lg = _lg(["QB", "SUPER_FLEX", "RB", "RB", "WR", "WR", "TE", "FLEX"], teams=10)
    repl, _ = replacement_points(pts, pos, lg)
    qb = sorted((v for k, v in pts.items() if pos[k] == "QB"), reverse=True)
    # QBs win the 10 SUPER_FLEX slots on points, so replacement moves past 10
    assert repl["QB"] < qb[10], "SUPER_FLEX did not deepen the QB pool"


def test_superflex_league_values_qbs_above_a_1qb_league():
    pos, pts = _pool()
    one = _lg(["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX"])
    sf = _lg(["QB", "SUPER_FLEX", "RB", "RB", "WR", "WR", "TE", "FLEX"])
    assert replacement_points(pts, pos, sf)[0]["QB"] < replacement_points(pts, pos, one)[0]["QB"]
