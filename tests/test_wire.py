"""Waiver adds and drops.

Both questions are answered by the same primitive: how much the optimal lineup
changes. An add is what a player would improve it by, a drop is what removing
one would cost. Ranking free agents by raw points instead would keep
recommending a fourth receiver to a roster that already starts three.
"""
import pytest

from sleeper.advice.wire import drop_ranking, prefilter, waiver_targets
from sleeper.league import League, Roster

PPR = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0}
SLOTS = ["QB", "RB", "WR", "TE", "FLEX", "BN", "BN"]

POS = {"qb1": "QB", "rb1": "RB", "rb2": "RB", "wr1": "WR", "wr2": "WR",
       "te1": "TE", "fa_wr": "WR", "fa_te": "TE", "fa_rb": "RB", "fa_qb": "QB"}
PTS = {"qb1": 20.0, "rb1": 15.0, "rb2": 8.0, "wr1": 14.0, "wr2": 12.0,
       "te1": 4.0, "fa_wr": 11.0, "fa_te": 9.0, "fa_rb": 3.0, "fa_qb": 5.0}

MINE = ["qb1", "rb1", "rb2", "wr1", "wr2", "te1"]
# The lineup as set: five slots, so one of the six is on the bench.
SET = ["qb1", "rb1", "wr1", "te1", "rb2"]
FREE = {"fa_wr", "fa_te", "fa_rb", "fa_qb"}


def _league(slots=None):
    return League("1", "Test", PPR, slots or SLOTS, 10, "2026")


def _roster(players, starters=None, reserve=None):
    starters = starters if starters is not None else players
    return Roster(roster_id=1, owner_id="u1", players=list(players),
                  starters=[p for p in starters if p and p != "0"],
                  slots=list(starters), reserve=reserve or [], taxi=[])


# --- adds -------------------------------------------------------------------

def test_a_hole_at_tight_end_beats_a_better_receiver():
    """The receiver scores more but cannot start. This is the whole reason the
    ranking is not a points list."""
    rows = waiver_targets(_league(), _roster(MINE), PTS, POS, FREE, top=5)
    assert rows[0]["player_id"] == "fa_te"
    assert rows[0]["marginal"] > 0
    assert PTS["fa_wr"] > PTS["fa_te"]


def test_a_free_agent_who_cannot_crack_the_lineup_adds_nothing():
    rows = waiver_targets(_league(), _roster(MINE), PTS, POS, FREE, top=5)
    by_id = {r["player_id"]: r for r in rows}
    assert by_id["fa_rb"]["marginal"] == 0.0


def test_a_rostered_player_is_never_a_target():
    rows = waiver_targets(_league(), _roster(MINE), PTS, POS, FREE, top=9)
    assert not ({r["player_id"] for r in rows} & set(MINE))


def test_every_target_carries_the_cheapest_drop_and_the_net():
    rows = waiver_targets(_league(), _roster(MINE), PTS, POS, FREE, top=3)
    top = rows[0]
    assert top["drop"]["player_id"] in MINE
    assert top["net"] == pytest.approx(top["marginal"] - top["drop"]["cost"])


def test_ties_at_zero_are_broken_by_how_far_above_the_wire_a_player_is():
    """On a full roster almost everyone adds nothing, so without a second key
    the list is arbitrary. Raw points cannot be that key: a kicker's 103 points
    over a season is not comparable to a tight end's 101, and sorting by them
    put four kickers at the top of a real league's list. Distance above the
    best free agent at the same position is comparable."""
    rows = waiver_targets(_league(), _roster(MINE), PTS, POS, FREE, top=9)
    zeros = [r for r in rows if r["marginal"] == 0.0]
    assert [r["over_wire"] for r in zeros] == sorted(
        (r["over_wire"] for r in zeros), reverse=True)


def test_the_prefilter_keeps_the_best_of_each_position():
    pts = {f"wr{i}": float(50 - i) for i in range(40)}
    pos = {p: "WR" for p in pts}
    kept = prefilter(pts, pos, set(pts), per_pos=5)
    assert len(kept) == 5
    assert kept[0] == "wr0"


def test_the_prefilter_does_not_change_the_top_of_the_list():
    full = waiver_targets(_league(), _roster(MINE), PTS, POS, FREE, top=3,
                          per_pos=99)
    trimmed = waiver_targets(_league(), _roster(MINE), PTS, POS, FREE, top=3,
                             per_pos=1)
    assert full[0]["player_id"] == trimmed[0]["player_id"]


# --- drops ------------------------------------------------------------------

def test_the_safest_drop_is_the_player_the_lineup_does_not_miss():
    rows = drop_ranking(_league(), _roster(MINE + ["fa_rb"], starters=SET),
                        PTS, POS, FREE)
    assert rows[0]["player_id"] == "fa_rb"
    assert rows[0]["cost"] == 0.0


def test_dropping_the_only_quarterback_is_flagged_and_sunk():
    rows = drop_ranking(_league(), _roster(MINE), PTS, POS, FREE)
    qb = next(r for r in rows if r["player_id"] == "qb1")
    assert qb["breaks_lineup"] is True
    assert rows[0]["player_id"] != "qb1"


def test_a_starter_is_never_the_first_suggestion():
    rows = drop_ranking(_league(), _roster(MINE + ["fa_rb"], starters=SET),
                        PTS, POS, FREE)
    assert rows[0]["starting"] is False


def test_a_player_the_wire_can_replace_is_shown_as_such():
    """te1 scores 4.0 and the best free tight end scores 9.0, so keeping him
    costs points."""
    rows = drop_ranking(_league(), _roster(MINE), PTS, POS, FREE)
    te = next(r for r in rows if r["player_id"] == "te1")
    assert te["vs_wire"] == -5.0


def test_an_injured_reserve_player_is_labelled_not_hidden():
    roster = _roster(MINE + ["fa_rb"], starters=MINE, reserve=["fa_rb"])
    rows = drop_ranking(_league(), roster, PTS, POS, FREE)
    hurt = next(r for r in rows if r["player_id"] == "fa_rb")
    assert hurt["reserve"] is True
