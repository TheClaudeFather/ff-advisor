"""Elimination leagues: how close you are to the cut.

In a guillotine league the lowest score each week is removed, so the question
is not whether you win, it is whether you clear the floor. This reports a
points margin, not odds: odds need a distribution, and Sleeper publishes none.
"""
import pytest

from sleeper.advice.survival import cut_margin, project_team
from sleeper.league import League, Roster

PPR = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0}
SLOTS = ["QB", "RB", "WR", "BN", "BN"]
POS = {"qb1": "QB", "qb2": "QB", "rb1": "RB", "rb2": "RB",
       "wr1": "WR", "wr2": "WR"}
PTS = {"qb1": 20.0, "qb2": 12.0, "rb1": 15.0, "rb2": 5.0,
       "wr1": 14.0, "wr2": 4.0}


def _league():
    return League("1", "Test", PPR, SLOTS, 3, "2026")


def _roster(rid, players, slots, owner=None):
    return Roster(roster_id=rid, owner_id=owner or f"u{rid}",
                  players=list(players),
                  starters=[p for p in slots if p and p != "0"],
                  slots=list(slots), reserve=[], taxi=[])


def test_a_team_that_set_its_lineup_is_projected_on_what_it_set():
    """Even when that is not their best: a manager who leaves points on the
    bench really will score less."""
    roster = _roster(1, ["qb1", "rb1", "wr1", "qb2"], ["qb2", "rb1", "wr1"])
    out = project_team(_league(), roster, PTS, POS)
    assert out["rule"] == "set"
    assert out["projected"] == 41.0
    assert out["optimal_total"] == 49.0


def test_a_team_that_set_nothing_is_projected_on_its_best_lineup():
    """Early in the week most of a league looks like this. Scoring them at zero
    would make everyone else look safe."""
    roster = _roster(2, ["qb1", "rb1", "wr1"], ["0", "0", "0"])
    out = project_team(_league(), roster, PTS, POS)
    assert out["rule"] == "optimal"
    assert out["projected"] == 49.0


def test_points_left_on_the_bench_are_reported():
    roster = _roster(1, ["qb1", "rb1", "wr1", "qb2"], ["qb2", "rb1", "wr1"])
    assert project_team(_league(), roster, PTS, POS)["bench_left"] == -8.0


def test_an_emptied_roster_does_not_crash_the_ranking():
    """A cut team's roster returns to free agency, so it projects to nothing."""
    out = project_team(_league(), _roster(3, [], []), PTS, POS)
    assert out["projected"] == 0.0
    assert out["unfilled"]


def test_the_cut_line_is_the_lowest_team():
    teams = [{"roster_id": 1, "projected": 100.0},
             {"roster_id": 2, "projected": 80.0},
             {"roster_id": 3, "projected": 90.0}]
    out = cut_margin(teams, my_roster_id=3)
    assert out["ranked"][0]["roster_id"] == 1
    assert out["cut"] == [2]
    assert out["my_rank"] == 2


def test_the_margin_is_the_distance_to_the_team_being_cut():
    teams = [{"roster_id": 1, "projected": 100.0},
             {"roster_id": 2, "projected": 80.0},
             {"roster_id": 3, "projected": 90.0}]
    out = cut_margin(teams, my_roster_id=3)
    assert out["margin"] == 10.0
    assert out["at_risk"] is False


def test_being_the_lowest_team_reports_the_gap_to_safety():
    teams = [{"roster_id": 1, "projected": 100.0},
             {"roster_id": 2, "projected": 80.0},
             {"roster_id": 3, "projected": 90.0}]
    out = cut_margin(teams, my_roster_id=2)
    assert out["at_risk"] is True
    assert out["margin"] == pytest.approx(-10.0)
    assert out["gap_to_safety"] == 10.0


def test_more_than_one_team_can_be_cut():
    teams = [{"roster_id": i, "projected": float(100 - i)} for i in range(1, 6)]
    out = cut_margin(teams, my_roster_id=1, cut=2)
    assert out["cut"] == [5, 4]


def test_elimination_leagues_are_named_in_configuration():
    """Nothing in a Sleeper payload reliably says "this league cuts a team every
    week", so it is configured rather than guessed."""
    from sleeper.config import parse_alias_list

    assert parse_alias_list("guillotine") == {"guillotine"}
    assert parse_alias_list("a, b ,c") == {"a", "b", "c"}


def test_no_configuration_means_no_elimination_leagues():
    from sleeper.config import parse_alias_list

    assert parse_alias_list(None) == set()
    assert parse_alias_list("") == set()


def test_a_team_that_is_not_mine_still_ranks():
    teams = [{"roster_id": 1, "projected": 100.0},
             {"roster_id": 2, "projected": 80.0}]
    out = cut_margin(teams, my_roster_id=None)
    assert out["my_rank"] is None
    assert out["margin"] is None
