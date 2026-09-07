"""Which NFL week are we in?

Nothing wired this before: projections.raw and projections.points both default
current_week to 1, so every weekly feed cached for 6 hours instead of forever
and the rest-of-season horizon summed weeks 1 to 18 rather than the weeks left.
"""
import pytest

from sleeper.season import resolve_week


def test_the_live_week_comes_from_the_state_payload():
    assert resolve_week({"season": "2026", "week": 3, "display_week": 3}) == 3


def test_display_week_wins_because_it_is_what_sleeper_shows():
    """Between games Sleeper advances week before display_week. The lineup a
    person is setting is the one on their screen."""
    assert resolve_week({"week": 4, "display_week": 3}) == 3


def test_an_override_beats_the_state():
    assert resolve_week({"week": 3, "display_week": 3}, 7) == 7


def test_the_offseason_floor_is_week_one():
    assert resolve_week({"week": 0, "display_week": 0}) == 1


def test_a_week_past_the_regular_season_is_clamped():
    assert resolve_week({"week": 22, "display_week": 22}) == 18


def test_a_state_payload_with_nothing_usable_falls_back_to_week_one():
    assert resolve_week({}) == 1


@pytest.mark.parametrize("bad", ["", None, "three"])
def test_junk_in_the_payload_does_not_crash(bad):
    assert resolve_week({"week": bad, "display_week": bad}) == 1


# --- the week being played is not the week you are setting a lineup for ------

def test_the_live_week_is_the_one_being_played():
    """Only weeks strictly before this one are finished, so only those are safe
    to cache forever. Advice week and live week are different questions."""
    from sleeper.season import live_week

    assert live_week({"week": 5, "display_week": 6}) == 5


def test_the_live_week_ignores_the_display_week():
    from sleeper.season import live_week

    assert live_week({"week": 5, "display_week": 9}) == 5


def test_on_tuesday_you_advise_on_next_week_while_last_week_is_still_live():
    """Sleeper advances display_week first. Collapsing the two would mark a week
    that is still being played as complete and cache it forever."""
    from sleeper.season import live_week

    state = {"week": 5, "display_week": 6}
    assert resolve_week(state) == 6
    assert live_week(state) == 5
