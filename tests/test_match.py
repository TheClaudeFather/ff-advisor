"""Resolving a league from the words the user actually says.

The user says "my 10-team league" or "the superflex one", not an alias that a
command generated. These tests pin the matching down to the two league shapes
in the fixtures, plus the ambiguity that must never be guessed away.
"""
import json
import pathlib

import pytest

from sleeper import match

FIX = pathlib.Path(__file__).parent / "fixtures"


def _desc(fixture, alias, name=None, slot=None):
    d = json.loads((FIX / fixture).read_text())
    if name:
        d["name"] = name
    return match.describe(d, alias, slot=slot)


@pytest.fixture
def descriptors():
    return [_desc("league_ppr_10team.json", "ppr10", name="Sunday Money League", slot=9),
            _desc("league_superflex_17team.json", "sf17", name="Guillotine Classic")]


def test_describe_reports_the_shape_of_a_league():
    d = _desc("league_ppr_10team.json", "ppr10", slot=9)
    assert d["teams"] == 10
    assert d["superflex"] is False
    assert d["ppr"] == 1.0
    assert d["slot"] == 9
    assert "10-team" in d["summary"]


def test_describe_flags_a_superflex_league():
    d = _desc("league_superflex_17team.json", "sf17")
    assert d["teams"] == 17
    assert d["superflex"] is True
    assert "SUPER_FLEX" in d["summary"]


def test_team_count_phrase_picks_the_right_league(descriptors):
    assert [d["alias"] for d in match.find(descriptors, "my 10 team league")] == ["ppr10"]
    assert [d["alias"] for d in match.find(descriptors, "the 17-team one")] == ["sf17"]


@pytest.mark.parametrize("phrase", ["superflex", "super flex", "2qb", "SUPER-FLEX!"])
def test_format_phrase_picks_the_superflex_league(descriptors, phrase):
    assert [d["alias"] for d in match.find(descriptors, phrase)] == ["sf17"]


def test_words_from_the_league_name_match(descriptors):
    assert [d["alias"] for d in match.find(descriptors, "guillotine")] == ["sf17"]


def test_an_alias_still_resolves_on_its_own(descriptors):
    assert [d["alias"] for d in match.find(descriptors, "ppr10")] == ["ppr10"]


def test_a_phrase_true_of_both_leagues_returns_both(descriptors):
    """Both fixtures are full PPR. Ambiguity must be reported, never guessed."""
    assert {d["alias"] for d in match.find(descriptors, "my ppr league")} == {"ppr10", "sf17"}


def test_a_phrase_matching_nothing_returns_nothing(descriptors):
    assert match.find(descriptors, "my hockey league") == []


def test_one_quarterback_phrase_excludes_the_superflex_league(descriptors):
    assert [d["alias"] for d in match.find(descriptors, "1qb")] == ["ppr10"]


# --- resolving through config, which is what every command calls -------------

CFG = {"aliases": {"ppr10": "111", "sf17": "222"}, "slots": {"ppr10": 9},
       "default_league": "ppr10"}


def test_a_phrase_resolves_to_a_league_id(descriptors):
    from sleeper import config
    assert config.resolve_league(CFG, "superflex", descriptors=descriptors) == "222"


def test_an_ambiguous_phrase_names_the_candidates(descriptors):
    from sleeper import config
    with pytest.raises(SystemExit) as e:
        config.resolve_league(CFG, "my ppr league", descriptors=descriptors)
    assert "ppr10" in str(e.value) and "sf17" in str(e.value)


def test_an_unmatched_phrase_lists_the_known_leagues(descriptors):
    from sleeper import config
    with pytest.raises(SystemExit) as e:
        config.resolve_league(CFG, "hockey", descriptors=descriptors)
    assert "ppr10" in str(e.value)


def test_an_alias_and_a_raw_id_still_win_without_any_descriptors():
    from sleeper import config
    assert config.resolve_league(CFG, "sf17") == "222"
    assert config.resolve_league(CFG, "999") == "999"


def test_descriptors_skip_leagues_that_are_not_cached(tmp_path, monkeypatch):
    """A cold cache must degrade to alias-only matching, never fetch or raise."""
    from sleeper import cache
    monkeypatch.setattr(cache, "ROOT", tmp_path)
    (tmp_path / "league").mkdir()
    (tmp_path / "league" / "111.json").write_text(
        (FIX / "league_ppr_10team.json").read_text())

    descs = match.load_descriptors(CFG)
    assert [d["alias"] for d in descs] == ["ppr10"]
    assert descs[0]["slot"] == 9


def test_the_leagues_listing_describes_each_league():
    """`sleeper leagues` must show what a league IS, not just its alias."""
    from sleeper.cli import league_rows

    leagues = [json.loads((FIX / "league_ppr_10team.json").read_text()),
               json.loads((FIX / "league_superflex_17team.json").read_text())]
    rows, aliases = league_rows(leagues, {"aliases": {}, "slots": {}})

    assert [r["summary"] for r in rows] == ["10-team, 1QB, full PPR",
                                            "17-team, SUPER_FLEX, full PPR"]
    assert aliases[rows[0]["alias"]] == rows[0]["league_id"]


def test_relisting_leagues_keeps_the_alias_a_league_already_has():
    """Re-running `leagues` must not add a second alias for the same league.

    It did, and every phrase then matched two aliases of one league, so every
    lookup reported ambiguity.
    """
    from sleeper.cli import league_rows

    leagues = [json.loads((FIX / "league_ppr_10team.json").read_text())]
    cfg = {"aliases": {"money": leagues[0]["league_id"]}, "slots": {"money": 9}}
    rows, aliases = league_rows(leagues, cfg)

    assert [r["alias"] for r in rows] == ["money"]
    assert aliases == {"money": leagues[0]["league_id"]}
    assert rows[0]["slot"] == 9


def test_two_aliases_for_one_league_are_not_ambiguous(descriptors):
    from sleeper import config

    cfg = {"aliases": {"sf17": "222", "guillotine": "222"}, "slots": {}}
    descs = descriptors + [dict(descriptors[1], alias="guillotine")]
    assert config.resolve_league(cfg, "superflex", descriptors=descs) == "222"


def test_a_phrase_resolves_to_the_alias_that_holds_the_draft_slot(descriptors):
    """Slots are stored per alias. A phrase must reach the same alias, or a
    draft started from "my 10-team league" would silently lose the slot."""
    from sleeper import config

    cfg = {"aliases": {"ppr10": "111", "sf17": "222"}, "slots": {"ppr10": 9}}
    alias = config.resolve_alias(cfg, "my 10 team league", descriptors=descriptors)
    assert alias == "ppr10"
    assert cfg["slots"][alias] == 9


def test_resolve_alias_returns_nothing_for_a_raw_league_id(descriptors):
    from sleeper import config

    cfg = {"aliases": {"ppr10": "111"}, "slots": {}}
    assert config.resolve_alias(cfg, "999", descriptors=descriptors) is None
