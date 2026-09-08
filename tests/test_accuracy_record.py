"""Grading the tool, and grading the record rather than a single week.

Two things the per-week projection grade cannot answer. Whether the advice
helped, which is a question about the lineup that was set against the lineup
that was recommended, scored on what actually happened. And whether a bias is
real, which one week of about 300 players cannot establish.
"""
import pytest

from sleeper.advice.accuracy import combine, grade, grade_decision

ACTUAL = {"a": 20.0, "b": 4.0, "c": 15.0, "d": 9.0}


def test_the_recommendation_beat_the_lineup_that_was_set():
    out = grade_decision(["a", "b"], ["a", "c"], ACTUAL)
    assert out["set"] == 24.0
    assert out["recommended"] == 35.0
    assert out["delta"] == 11.0
    assert out["helped"] is True


def test_the_recommendation_was_worse():
    """It happens. A projection is not a result, and the record has to show the
    weeks the advice cost points or it is not a record."""
    out = grade_decision(["a", "c"], ["a", "b"], ACTUAL)
    assert out["delta"] == -11.0
    assert out["helped"] is False


def test_no_change_recommended_is_not_a_win_or_a_loss():
    out = grade_decision(["a", "b"], ["a", "b"], ACTUAL)
    assert out["delta"] == 0.0
    assert out["helped"] is None


def test_a_player_with_no_result_counts_as_nothing():
    out = grade_decision(["a"], ["ghost"], ACTUAL)
    assert out["recommended"] == 0.0
    assert out["delta"] == -20.0


# --- the record across weeks -------------------------------------------------

def test_a_record_averages_by_how_many_players_each_week_graded():
    """A week that graded 300 players should not weigh the same as one that
    graded 30."""
    weeks = [
        {"week": 1, "played": True, "overall": {"n": 300, "mae": 10.0, "bias": 2.0},
         "by_pos": {"RB": {"n": 100, "mae": 8.0, "bias": 1.0}}, "decision": None},
        {"week": 2, "played": True, "overall": {"n": 100, "mae": 6.0, "bias": -2.0},
         "by_pos": {"RB": {"n": 50, "mae": 12.0, "bias": 3.0}}, "decision": None},
    ]
    out = combine(weeks)
    assert out["overall"]["n"] == 400
    assert out["overall"]["mae"] == pytest.approx(9.0)
    assert out["overall"]["bias"] == pytest.approx(1.0)
    assert out["by_pos"]["RB"]["mae"] == pytest.approx(9.33, abs=0.01)


def test_a_record_counts_the_weeks_the_advice_helped():
    weeks = [
        {"week": 1, "played": True, "overall": {"n": 1, "mae": 0.0, "bias": 0.0},
         "by_pos": {}, "decision": {"delta": 11.0, "helped": True}},
        {"week": 2, "played": True, "overall": {"n": 1, "mae": 0.0, "bias": 0.0},
         "by_pos": {}, "decision": {"delta": -3.0, "helped": False}},
        {"week": 3, "played": True, "overall": {"n": 1, "mae": 0.0, "bias": 0.0},
         "by_pos": {}, "decision": {"delta": 0.0, "helped": None}},
    ]
    out = combine(weeks)
    assert out["decisions"] == {"weeks": 2, "helped": 1, "hurt": 1,
                                "total_delta": 8.0}


def test_an_unplayed_week_is_left_out_of_the_record():
    weeks = [
        {"week": 1, "played": False, "overall": {"n": 300, "mae": 9.7, "bias": 9.7},
         "by_pos": {}, "decision": None},
    ]
    out = combine(weeks)
    assert out["weeks"] == []
    assert out["overall"]["n"] == 0


def test_an_empty_record_is_not_an_error():
    out = combine([])
    assert out["overall"] == {"n": 0, "mae": 0.0, "bias": 0.0}


def test_the_record_lists_which_weeks_it_covers():
    weeks = [
        {"week": 4, "played": True, "overall": {"n": 2, "mae": 1.0, "bias": 0.0},
         "by_pos": {}, "decision": None},
        {"week": 6, "played": True, "overall": {"n": 2, "mae": 3.0, "bias": 0.0},
         "by_pos": {}, "decision": None},
    ]
    assert combine(weeks)["weeks"] == [4, 6]


def test_grade_carries_a_decision_when_the_lineups_are_known():
    out = grade({"a": 1.0}, ACTUAL, {"a": "RB"}, week=2,
                set_ids=["a", "b"], recommended_ids=["a", "c"])
    assert out["decision"]["delta"] == 11.0


def test_grade_has_no_decision_when_the_snapshot_predates_lineups():
    out = grade({"a": 1.0}, ACTUAL, {"a": "RB"}, week=1)
    assert out["decision"] is None
