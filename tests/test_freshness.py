"""Cache keys must identify what they hold, and --refresh must reach the data.

Two defects with the same shape: something that looks fresh is not. The
trending cache keyed on everything except the limit, so a second call with a
different limit was served the first one's answer. And --refresh reached only
`sleeper leagues`, so no in-season command could get past a roster cached an
hour ago, which in-season is the difference between advising on a player you
still have and one you already dropped.
"""
import pytest

from sleeper import api, league as league_mod


@pytest.fixture
def calls(monkeypatch):
    """Record what goes into the cache layer instead of fetching."""
    seen = []

    league_payload = {"name": "Test", "roster_positions": ["QB", "BN"],
                      "settings": {"num_teams": 10}, "season": "2026",
                      "scoring_settings": {"rec": 1.0}}

    def fake(ns, key, url, ttl, **kw):
        seen.append({"ns": ns, "key": key, "url": url, **kw})
        return [] if key.endswith("_rosters") or ns != "league" else league_payload

    monkeypatch.setattr(api.cache, "get_json", fake)
    return seen


def test_a_different_trending_limit_is_a_different_cache_entry(calls):
    api.trending(limit=50)
    api.trending(limit=200)
    assert calls[0]["key"] != calls[1]["key"]


def test_the_trending_key_still_separates_adds_from_drops(calls):
    api.trending(kind="add")
    api.trending(kind="drop")
    assert calls[0]["key"] != calls[1]["key"]


def test_refresh_reaches_the_roster_fetch(calls):
    """api.rosters is cached for an hour, which is too stale to advise on."""
    league_mod.all_rosters("111", refresh=True)
    assert calls[0]["refresh"] is True


def test_refresh_reaches_the_league_load(calls):
    league_mod.load("111", refresh=True)
    assert all(c.get("refresh") is True for c in calls)


def test_without_refresh_nothing_is_forced(calls):
    league_mod.all_rosters("111")
    assert calls[0].get("refresh", False) is False


def test_the_league_helper_passes_refresh_to_every_fetch(calls):
    """This is where the flag was actually being dropped: the CLI helper that
    every command uses to load a league did not forward it."""
    from argparse import Namespace

    from sleeper.cli import _lg

    args = Namespace(league="111", offline=False, refresh=True)
    _lg(args, {"aliases": {}, "user_id": "u1"})
    assert calls and all(c.get("refresh") is True for c in calls)


def test_the_league_helper_does_not_force_a_fetch_by_default(calls):
    from argparse import Namespace

    from sleeper.cli import _lg

    args = Namespace(league="111", offline=False, refresh=False)
    _lg(args, {"aliases": {}, "user_id": "u1"})
    assert all(c.get("refresh", False) is False for c in calls)
