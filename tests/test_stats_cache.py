"""A week's results are immutable only after it is played.

stats_week cached forever unconditionally. Fetching week 1 before kickoff
therefore stored a feed of zeros permanently, and every later grade of that
week read those zeros back and reported it as unplayed. The same trap that
projections_week already avoids with its `completed` flag.
"""
from sleeper import api, cache


def _calls(monkeypatch):
    seen = []

    def fake(ns, key, url, ttl, **kw):
        seen.append({"key": key, "ttl": ttl, **kw})
        return []

    monkeypatch.setattr(api.cache, "get_json", fake)
    return seen


def test_a_finished_week_is_cached_forever(monkeypatch):
    calls = _calls(monkeypatch)
    api.stats_week("2026", 3, completed=True)
    assert calls[0]["ttl"] is cache.FOREVER


def test_a_week_still_in_progress_expires(monkeypatch):
    calls = _calls(monkeypatch)
    api.stats_week("2026", 3, completed=False)
    assert calls[0]["ttl"] is not cache.FOREVER
    assert calls[0]["ttl"] > 0


def test_the_default_does_not_freeze_an_unplayed_week(monkeypatch):
    """The default has to be the safe one: a caller that forgets the flag
    should get a short cache, not a permanent record of zeros."""
    calls = _calls(monkeypatch)
    api.stats_week("2026", 3)
    assert calls[0]["ttl"] is not cache.FOREVER
