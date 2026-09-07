"""Shared fixtures.

The in-season commands read the projection feeds and the player index through
the cache, so testing them needs a cache rather than a mock of our own code.
`seeded_cache` builds a real one in a temp directory from the trimmed fixtures,
which keeps every test offline and deterministic.
"""
from __future__ import annotations

import json
import pathlib
import time

import pytest

FIX = pathlib.Path(__file__).parent / "fixtures"
SEASON = "2026"
WEEK = 1


def _load(name):
    return json.loads((FIX / name).read_text())


def _write_cached(root, ns, key, value):
    directory = root / ns
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{key}.json").write_text(json.dumps(value))
    (directory / f"{key}.meta.json").write_text(
        json.dumps({"fetched_at": time.time(), "url": f"fixture:{ns}/{key}"}))


def _slim_from(records):
    """The player index the commands read, built from the same fixtures."""
    out = {}
    for r in records:
        player = r.get("player") or {}
        pid = r["player_id"]
        name = " ".join(filter(None, [player.get("first_name"),
                                      player.get("last_name")])) or pid
        out[pid] = {"name": name, "position": player.get("position"),
                    "team": player.get("team")}
    return out


@pytest.fixture
def seeded_cache(tmp_path, monkeypatch):
    """A cache holding one season feed, one weekly feed, and a player index."""
    from sleeper import cache, players

    season_feed = _load(f"projections_season_{SEASON}_top.json")
    week_feed = _load(f"projections_week{WEEK}_{SEASON}_top.json")

    monkeypatch.setattr(cache, "ROOT", tmp_path)

    _write_cached(tmp_path, "proj", f"season_{SEASON}", season_feed)
    _write_cached(tmp_path, "proj", f"week_{SEASON}_{WEEK}", week_feed)
    _write_cached(tmp_path, "meta", "state",
                  {"season": SEASON, "week": WEEK, "display_week": WEEK})

    slim = _slim_from(season_feed)
    slim.update(_slim_from(week_feed))
    path = players.slim_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(slim))

    return tmp_path


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test may reach Sleeper.

    A cold cache used to mean a silent skip or a real HTTP call, which made a
    test's result depend on whose machine it ran on. Now it fails loudly.
    """
    from sleeper import cache, http

    def blocked(url):
        raise AssertionError(f"test reached the network: {url}")

    # cache.py did `from .http import fetch_json`, so it holds its own binding.
    # Patching only http would leave every cached fetch free to call out.
    monkeypatch.setattr(http, "fetch_json", blocked)
    monkeypatch.setattr(cache, "fetch_json", blocked)


@pytest.fixture
def ppr_league():
    from sleeper.league import League

    d = _load("league_ppr_10team.json")
    return League("111", d["name"], d["scoring_settings"], d["roster_positions"],
                  d["settings"]["num_teams"], SEASON)


@pytest.fixture
def superflex_league():
    from sleeper.league import League

    d = _load("league_superflex_17team.json")
    return League("222", d["name"], d["scoring_settings"], d["roster_positions"],
                  d["settings"]["num_teams"], SEASON)
