"""Reading a team as Sleeper actually stores it.

my_players returns only the flat `players` list, which cannot answer "what
should I change" — that needs the `starters` list, which is positional against
roster_positions and uses "0" for a slot nobody is in.
"""
from sleeper.league import Roster, rosters_from

RAW = [
    {"roster_id": 1, "owner_id": "900000000000000001",
     "players": ["a", "b", "c"], "starters": ["a", "0", "c"],
     "reserve": ["c"], "taxi": None},
    {"roster_id": 2, "owner_id": "900000000000000002",
     "players": ["d", "e"], "starters": ["0", "0"],
     "reserve": None, "taxi": None},
    {"roster_id": 3, "owner_id": None, "players": None, "starters": None,
     "reserve": None, "taxi": None},
]


def test_empty_slots_are_not_players():
    r = rosters_from(RAW)[0]
    assert r.starters == ["a", "c"]
    assert r.players == ["a", "b", "c"]


def test_a_team_with_someone_in_a_slot_has_set_its_lineup():
    assert rosters_from(RAW)[0].set_lineup is True


def test_a_team_of_all_empty_slots_has_not_set_its_lineup():
    """Early in the week most of the league looks like this, which is why
    opponent projections fall back to their optimal lineup."""
    assert rosters_from(RAW)[1].set_lineup is False


def test_a_roster_with_nothing_in_it_does_not_crash():
    r = rosters_from(RAW)[2]
    assert r.players == [] and r.starters == [] and r.set_lineup is False


def test_reserve_and_taxi_are_read_as_lists():
    first, second = rosters_from(RAW)[0], rosters_from(RAW)[1]
    assert first.reserve == ["c"]
    assert second.reserve == [] and second.taxi == []


def test_a_roster_is_found_by_id():
    from sleeper.league import pick_roster

    assert pick_roster(rosters_from(RAW), 2).owner_id == "900000000000000002"
    assert pick_roster(rosters_from(RAW), 99) is None


def test_bench_is_everyone_not_starting():
    assert rosters_from(RAW)[0].bench == ["b"]


def test_the_dataclass_is_the_only_shape_callers_see():
    assert isinstance(rosters_from(RAW)[0], Roster)


def test_a_player_on_injured_reserve_is_not_available_to_start():
    """`players` includes reserve and taxi. Feeding that straight to the lineup
    optimizer would happily put an IR player in a starting slot."""
    r = rosters_from(RAW)[0]
    assert "c" in r.players
    assert r.active == ["a", "b"]


def test_a_roster_with_no_reserve_has_everyone_available():
    assert rosters_from(RAW)[1].active == ["d", "e"]


def test_a_co_owner_still_finds_their_team():
    """Sleeper puts only one manager in owner_id. A co-owned team resolved to
    None, and every in-season command would then say it cannot find your team."""
    from sleeper.league import owns

    raw = {"owner_id": "111", "co_owners": ["222"]}
    assert owns(raw, "111") and owns(raw, "222")
    assert not owns(raw, "333")


def test_a_roster_with_no_co_owners_listed_is_still_matched():
    from sleeper.league import owns

    assert owns({"owner_id": "111", "co_owners": None}, "111")
