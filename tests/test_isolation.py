"""A test must not read the developer's real data, and must not reach the network.

sleeper/players.py bound its slim-index path at import time, so redirecting
cache.ROOT moved the projection cache but not the player database: any test
touching players.load() silently read ~/.sleeper and passed or failed depending
on whose machine it ran on.
"""
from sleeper import cache, players


def test_redirecting_the_cache_redirects_the_player_database(tmp_path,
                                                             monkeypatch):
    monkeypatch.setattr(cache, "ROOT", tmp_path)
    assert str(tmp_path) in str(players.slim_path())


def test_the_network_is_blocked_during_tests():
    """The autouse guard in conftest turns a cold cache into a loud failure
    instead of a silent skip or a real HTTP call."""
    from sleeper import http

    try:
        http.fetch_json("https://api.sleeper.app/v1/state/nfl")
    except AssertionError as e:
        assert "network" in str(e)
    else:
        raise AssertionError("the network guard did not fire")
