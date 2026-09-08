"""Grading the projections after the week is played.

The point is to learn how much to trust the numbers, so the report has to be
honest about the direction of the error, not only its size. A tool that is
consistently 3 points high on tight ends is telling you something you can act
on; a mean absolute error alone hides it.
"""
import pytest

from sleeper.advice.accuracy import grade

POS = {"a": "RB", "b": "RB", "c": "WR", "d": "TE"}


def test_a_perfect_week_has_no_error():
    projected = {"a": 10.0, "b": 5.0}
    out = grade(projected, dict(projected), POS)
    assert out["overall"]["mae"] == 0.0
    assert out["overall"]["bias"] == 0.0


def test_bias_is_positive_when_the_projections_were_too_high():
    out = grade({"a": 12.0}, {"a": 8.0}, POS)
    assert out["overall"]["bias"] == 4.0
    assert out["overall"]["mae"] == 4.0


def test_bias_is_negative_when_the_projections_were_too_low():
    out = grade({"a": 8.0}, {"a": 12.0}, POS)
    assert out["overall"]["bias"] == -4.0
    assert out["overall"]["mae"] == 4.0


def test_errors_in_both_directions_cancel_in_bias_but_not_in_error():
    out = grade({"a": 12.0, "b": 8.0}, {"a": 8.0, "b": 12.0}, POS)
    assert out["overall"]["bias"] == 0.0
    assert out["overall"]["mae"] == 4.0


def test_each_position_is_graded_on_its_own():
    out = grade({"a": 10.0, "c": 10.0}, {"a": 10.0, "c": 2.0}, POS)
    assert out["by_pos"]["RB"]["mae"] == 0.0
    assert out["by_pos"]["WR"]["mae"] == 8.0


def test_a_player_who_did_not_play_scored_nothing():
    """Absence from the stats feed is a zero, and a real miss if he was
    projected to play."""
    out = grade({"a": 14.0}, {}, POS)
    assert out["overall"]["mae"] == 14.0
    assert out["n_no_actual"] == 1


def test_the_worst_misses_are_named_biggest_first():
    out = grade({"a": 20.0, "b": 5.0, "c": 10.0},
                {"a": 18.0, "b": 25.0, "c": 4.0}, POS)
    assert [w["player_id"] for w in out["worst"][:2]] == ["b", "c"]
    assert out["worst"][0]["error"] == -20.0


def test_grading_nothing_is_not_an_error():
    out = grade({}, {}, POS)
    assert out["overall"]["n"] == 0
    assert out["overall"]["mae"] == 0.0


def test_a_player_with_no_position_is_still_counted_overall():
    out = grade({"z": 10.0}, {"z": 4.0}, POS)
    assert out["overall"]["n"] == 1
    assert "UNKNOWN" in out["by_pos"]


def test_the_report_says_which_week_it_graded():
    out = grade({"a": 1.0}, {"a": 1.0}, POS, week=6)
    assert out["week"] == 6


def test_a_week_that_has_not_been_played_is_not_a_grade():
    """Sleeper publishes a stats feed for a future week with every value at
    zero, so grading it reports every projection as wildly too high. That is
    not a measurement of anything."""
    out = grade({"a": 20.0, "b": 15.0}, {"a": 0.0, "b": 0.0}, POS, week=1)
    assert out["played"] is False


def test_a_week_with_real_results_is_a_grade():
    out = grade({"a": 20.0, "b": 15.0}, {"a": 18.0, "b": 0.0}, POS, week=1)
    assert out["played"] is True


def test_an_empty_grade_is_not_called_played():
    assert grade({}, {}, POS)["played"] is False
