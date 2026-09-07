"""The board must work for a week and for the rest of the season, not only for
a draft.

`build(horizon=...)` was a dead parameter: nothing ever passed it, and passing
"ros" crashed, because build routed through projections.raw, which only knows
"season" and "week:N" while projections.points also knows "ros".
"""
import pytest

from sleeper.advice import board as board_mod


def test_a_season_board_still_builds(seeded_cache, ppr_league):
    rows, meta = board_mod.build(ppr_league, offline=True)
    assert rows and meta["replacement"]
    assert rows[0]["pts"] > 0


def test_a_weekly_board_scores_a_single_week(seeded_cache, ppr_league):
    """Weekly points must be far smaller than season points for the same player."""
    season, _ = board_mod.build(ppr_league, offline=True)
    week, _ = board_mod.build(ppr_league, horizon="week:1", current_week=1,
                              offline=True)
    by_id = {r["player_id"]: r["pts"] for r in season}
    shared = [r for r in week if r["player_id"] in by_id]
    assert shared, "fixtures must overlap"
    assert all(r["pts"] < by_id[r["player_id"]] for r in shared)


def test_a_rest_of_season_board_does_not_crash(seeded_cache, ppr_league):
    """It used to raise ValueError: bad horizon ros."""
    rows, meta = board_mod.build(ppr_league, horizon="ros", current_week=18,
                                 offline=True)
    assert rows
    assert meta["replacement"]


def test_a_weekly_board_still_reports_adp_from_the_season_feed(seeded_cache,
                                                              ppr_league):
    """Weekly feeds carry no ADP. Losing it would zero every survival number and
    silently degrade the draft board if a horizon were ever passed there."""
    rows, meta = board_mod.build(ppr_league, horizon="week:1", current_week=1,
                                 offline=True)
    assert meta["adp_source"] in ("adp_ppr", "adp_2qb")
    assert any(r["adp"] is not None for r in rows)


def test_the_blind_spot_report_survives_a_weekly_board(seeded_cache, ppr_league):
    _rows, meta = board_mod.build(ppr_league, horizon="week:1", current_week=1,
                                  offline=True)
    assert isinstance(meta["unscored"], dict)


def test_an_unknown_horizon_is_still_rejected(seeded_cache, ppr_league):
    with pytest.raises(ValueError):
        board_mod.build(ppr_league, horizon="fortnight", offline=True)
