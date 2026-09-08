"""Rest of season counts games, not weeks.

Scaling the season projection by the share of weeks remaining treats every
player alike, but a bye that has already passed and a bye still ahead are not
the same. At week 10 with nine weeks left, a player whose bye is behind him
plays nine more games and one whose bye is ahead plays eight, while the flat
scale credits both with 9/18 of their season. That understates the first by
about 6% and overstates the second by about 6%, a 12% spread between two
otherwise identical players, which is enough to flip neighbours in a waiver
ranking.
"""
import pytest

from sleeper.projections import remaining_share

# A three-team, four-week season. AAA is off in week 2, BBB in week 3.
GAMES = [
    {"week": 1, "home": "AAA", "away": "BBB"},
    {"week": 2, "home": "BBB", "away": "CCC"},
    {"week": 3, "home": "AAA", "away": "CCC"},
    {"week": 4, "home": "AAA", "away": "BBB"},
]


def test_at_the_start_of_the_year_every_game_remains():
    share = remaining_share(GAMES, 1, last_week=4)
    assert share == {"AAA": 1.0, "BBB": 1.0, "CCC": 1.0}


def test_a_bye_already_behind_you_leaves_a_larger_share():
    """From week 3, AAA plays both remaining weeks and BBB only one."""
    share = remaining_share(GAMES, 3, last_week=4)
    assert share["AAA"] == pytest.approx(2 / 3)
    assert share["BBB"] == pytest.approx(1 / 3)


def test_the_last_week_leaves_only_that_game():
    share = remaining_share(GAMES, 4, last_week=4)
    assert share["CCC"] == 0.0
    assert share["AAA"] == pytest.approx(1 / 3)


def test_a_season_that_is_over_leaves_nothing():
    share = remaining_share(GAMES, 5, last_week=4)
    assert set(share.values()) == {0.0}


def test_a_team_not_in_the_schedule_is_absent_rather_than_zero():
    """Callers fall back to the flat share, which is better than pretending a
    team has no games left."""
    assert "ZZZ" not in remaining_share(GAMES, 2, last_week=4)


def test_rest_of_season_uses_the_team_share(seeded_cache, ppr_league,
                                            monkeypatch):
    from sleeper import api, projections

    monkeypatch.setattr(api, "schedule", lambda season, **kw: GAMES)
    season, _ = projections.points(ppr_league, "season", current_week=1)
    ros, _ = projections.points(ppr_league, "ros", current_week=3)

    # Every fixture player belongs to a real NFL team, none of which are in
    # this toy schedule, so all of them fall back to the flat share.
    assert ros and all(v <= season[p] for p, v in ros.items())


def test_a_player_whose_team_has_a_bye_ahead_scales_lower(seeded_cache,
                                                          ppr_league,
                                                          monkeypatch):
    from sleeper import api, projections

    monkeypatch.setattr(api, "schedule", lambda season, **kw: GAMES)
    season, _ = projections.points(ppr_league, "season", current_week=1)
    pid = max(season, key=season.get)

    scaled = projections.scale_to_remaining(
        {pid: 100.0}, {pid: "AAA"}, GAMES, 3, last_week=4)
    behind = projections.scale_to_remaining(
        {pid: 100.0}, {pid: "BBB"}, GAMES, 3, last_week=4)
    assert scaled[pid] == pytest.approx(66.67, abs=0.01)
    assert behind[pid] == pytest.approx(33.33, abs=0.01)
