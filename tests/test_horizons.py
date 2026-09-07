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


# --- rest of season is the season projection, scaled -------------------------

def test_the_remaining_share_of_the_season():
    from sleeper.projections import ros_share

    assert ros_share(1) == 1.0
    assert ros_share(10) == pytest.approx(9 / 18)
    assert ros_share(18) == pytest.approx(1 / 18)


def test_a_week_past_the_end_leaves_nothing():
    from sleeper.projections import ros_share

    assert ros_share(19) == 0.0


def test_rest_of_season_never_exceeds_the_full_season(seeded_cache, ppr_league):
    """Summing the weekly feeds beat the season projection by 8% for a durable
    quarterback and 30% for an injury-prone back, because weekly numbers assume
    everyone suits up while Sleeper's season number prices the risk. Scaling
    the season number keeps that view intact."""
    from sleeper import projections

    season, _ = projections.points(ppr_league, "season", current_week=1)
    ros, _ = projections.points(ppr_league, "ros", current_week=1)
    assert ros and season
    assert all(ros[p] <= season[p] + 0.01 for p in ros)


def test_at_week_one_rest_of_season_is_the_whole_season(seeded_cache,
                                                        ppr_league):
    from sleeper import projections

    season, _ = projections.points(ppr_league, "season", current_week=1)
    ros, _ = projections.points(ppr_league, "ros", current_week=1)
    assert ros == pytest.approx(season)


def test_halfway_through_the_year_half_the_points_remain(seeded_cache,
                                                         ppr_league):
    from sleeper import projections

    season, _ = projections.points(ppr_league, "season", current_week=1)
    ros, _ = projections.points(ppr_league, "ros", current_week=10)
    top = max(season, key=season.get)
    assert ros[top] == pytest.approx(season[top] * 9 / 18)


def test_rest_of_season_does_not_read_a_single_weekly_feed(seeded_cache,
                                                           ppr_league):
    """It used to fetch every remaining week. That is 18 requests for a number
    the season feed already carries, and the network guard would fire on a
    machine whose cache lacks them."""
    from sleeper import projections

    calls = []
    original = projections.raw

    def watched(season, horizon, **kw):
        calls.append(horizon)
        return original(season, horizon, **kw)

    projections.raw = watched
    try:
        projections.points(ppr_league, "ros", current_week=3)
    finally:
        projections.raw = original
    assert calls == ["season"]
