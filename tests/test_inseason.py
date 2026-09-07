"""In-season replacement level.

Draft replacement is "the Nth best player in the NFL", derived from
roster_positions times the number of teams. That is the wrong yardstick once
the season starts: what a rostered player is really worth is measured against
the best player you could add for nothing, which is the top free agent at his
position. In a 17-team league those are very different numbers.
"""
from sleeper.advice.inseason import (best_available, free_agent_ids,
                                     replaceability)

PTS = {"stud": 300.0, "mid": 200.0, "fa_rb1": 120.0, "fa_rb2": 90.0,
       "fa_te1": 60.0, "no_proj": 0.0}
POS = {"stud": "RB", "mid": "RB", "fa_rb1": "RB", "fa_rb2": "RB",
       "fa_te1": "TE", "no_proj": "WR"}
ROSTERED = {"stud", "mid"}


def test_free_agents_are_everyone_nobody_rosters():
    assert free_agent_ids(PTS, ROSTERED) == {"fa_rb1", "fa_rb2", "fa_te1",
                                             "no_proj"}


def test_the_best_free_agent_at_each_position_is_the_replacement():
    best = best_available(PTS, POS, free_agent_ids(PTS, ROSTERED))
    assert best["RB"] == ("fa_rb1", 120.0)
    assert best["TE"] == ("fa_te1", 60.0)


def test_a_position_with_nobody_available_has_no_replacement():
    best = best_available(PTS, POS, {"fa_te1"})
    assert "RB" not in best


def test_replaceability_measures_the_gap_to_the_wire():
    """The starter is worth 180 more than a free pickup; the bench back is 80."""
    best = best_available(PTS, POS, free_agent_ids(PTS, ROSTERED))
    assert replaceability("stud", PTS, POS, best) == 180.0
    assert replaceability("mid", PTS, POS, best) == 80.0


def test_a_player_the_wire_can_beat_is_negative():
    best = best_available(PTS, POS, {"fa_rb1"})
    assert replaceability("mid", {**PTS, "mid": 100.0}, POS, best) == -20.0


def test_a_position_with_no_free_agent_falls_back_to_the_players_own_points():
    """Nothing to compare against means he is worth all of himself, not zero."""
    assert replaceability("fa_te1", PTS, POS, {}) == 60.0
