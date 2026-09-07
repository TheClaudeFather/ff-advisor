"""Start/sit: the difference between the lineup you set and the best one.

The hard part is not finding the best lineup, which lineup.optimal_lineup
already does. It is describing the change in a way a person can act on: pairing
each promoted player with the one he replaces, at the slot where it happens.
Pairing them by order instead of by slot produces advice like "bench your
quarterback, start your tight end".
"""
import pytest

from sleeper.advice.lineup_advice import advise, swaps
from sleeper.league import League, Roster

PPR = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0, "rush_yd": 0.1, "rush_td": 6.0,
       "pass_yd": 0.04, "pass_td": 4.0}
SLOTS = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN", "BN"]


def _league(slots=None, teams=10):
    return League("1", "Test League", PPR, slots or SLOTS, teams, "2026")


def _roster(players, starters, reserve=None):
    """`starters` is slot-aligned, the way Sleeper stores it."""
    return Roster(roster_id=1, owner_id="u1", players=players,
                  starters=[p for p in starters if p and p != "0"],
                  slots=list(starters), reserve=reserve or [], taxi=[])


POS = {"qb1": "QB", "rb1": "RB", "rb2": "RB", "rb3": "RB",
       "wr1": "WR", "wr2": "WR", "wr3": "WR", "te1": "TE", "te2": "TE"}
PTS = {"qb1": 20.0, "rb1": 15.0, "rb2": 9.0, "rb3": 4.0,
       "wr1": 14.0, "wr2": 11.0, "wr3": 3.0, "te1": 5.0, "te2": 12.0}


def test_a_lineup_that_is_already_best_needs_no_changes():
    lg = _league()
    roster = _roster(["qb1", "rb1", "rb2", "wr1", "wr2", "te2", "rb3"],
                     ["qb1", "rb1", "rb2", "wr1", "wr2", "te2", "rb3"])
    out = advise(lg, roster, PTS, POS, {}, week=1)
    assert out["swaps"] == []
    assert out["gain"] == 0.0


# Two upgrades at once, arranged so that pairing by order gets both wrong: the
# cheapest player leaving sits in the FLEX, but the biggest upgrade lands in TE.
TWO = {"qb1": 20.0, "rb1": 15.0, "wr1": 14.0,
       "te1": 9.0, "rb2": 5.0, "te2": 12.0, "wr2": 11.0}
TWO_POS = {"qb1": "QB", "rb1": "RB", "wr1": "WR", "te1": "TE", "rb2": "RB",
           "te2": "TE", "wr2": "WR"}
TWO_SLOTS = ["QB", "RB", "WR", "TE", "FLEX", "BN", "BN"]


def test_each_promoted_player_is_paired_with_the_one_he_replaces():
    """Pairing the promoted players against the benched ones in point order
    would report starting the tight end in place of the running back, and the
    receiver in place of the tight end. Both slots would be wrong."""
    lg = _league(slots=TWO_SLOTS)
    roster = _roster(players=list(TWO),
                     starters=["qb1", "rb1", "wr1", "te1", "rb2"])
    out = advise(lg, roster, TWO, TWO_POS, {}, week=1)

    by_slot = {s["slot"]: s for s in out["swaps"]}
    assert by_slot["TE"]["out"] == "te1" and by_slot["TE"]["in"] == "te2"
    assert by_slot["FLEX"]["out"] == "rb2" and by_slot["FLEX"]["in"] == "wr2"


def test_a_player_who_only_moves_slots_is_not_the_one_replaced():
    """The tight end keeps his place by sliding into the flex, so the player
    actually leaving the lineup is the back, and that is who the advice names."""
    lg = _league()
    roster = _roster(
        players=["qb1", "rb1", "rb2", "wr1", "wr2", "te1", "rb3", "te2"],
        starters=["qb1", "rb1", "rb2", "wr1", "wr2", "te1", "rb3"])
    out = advise(lg, roster, PTS, POS, {}, week=1)
    assert [(s["slot"], s["out"], s["in"]) for s in out["swaps"]] == [
        ("TE", "rb3", "te2")]


def test_the_gain_is_what_the_changes_are_worth():
    lg = _league()
    roster = _roster(
        players=["qb1", "rb1", "rb2", "wr1", "wr2", "te1", "rb3", "te2", "wr3"],
        starters=["qb1", "rb1", "rb2", "wr1", "wr2", "te1", "rb3"])
    out = advise(lg, roster, PTS, POS, {}, week=1)
    # te1 5.0 -> te2 12.0, rb3 4.0 -> wr3 3.0 is not an upgrade, so the flex
    # keeps rb3 and only the tight end changes.
    assert out["gain"] == pytest.approx(out["optimal_total"] - out["current_total"])
    assert out["gain"] > 0


def test_moving_a_player_between_slots_he_is_eligible_for_is_not_a_change():
    """The same eleven players in different slots score the same. Reporting it
    as a swap would send someone to Sleeper to do nothing."""
    lg = _league()
    same = ["qb1", "rb1", "rb2", "wr1", "wr2", "te2", "rb3"]
    roster = _roster(players=same, starters=same)
    out = advise(lg, roster, PTS, POS, {}, week=1)
    assert out["swaps"] == []


def test_a_team_that_has_set_no_lineup_gets_the_whole_lineup_as_changes():
    lg = _league()
    roster = _roster(players=["qb1", "rb1", "rb2", "wr1", "wr2", "te2", "rb3"],
                     starters=[])
    out = advise(lg, roster, PTS, POS, {}, week=1)
    assert out["current_total"] == 0.0
    assert len(out["swaps"]) == len(out["optimal"]["starters"])
    assert all(s["out"] is None for s in out["swaps"])


def test_a_player_on_injured_reserve_is_never_started():
    lg = _league()
    roster = _roster(players=["qb1", "rb1", "rb2", "wr1", "wr2", "te1", "te2"],
                     starters=["qb1", "rb1", "rb2", "wr1", "wr2", "te1"],
                     reserve=["te2"])
    out = advise(lg, roster, PTS, POS, {}, week=1)
    started = {s[1] for s in out["optimal"]["starters"]}
    assert "te2" not in started


def test_a_player_with_no_projection_is_named_not_silently_zeroed():
    lg = _league()
    roster = _roster(players=["qb1", "rb1", "rb2", "wr1", "wr2", "te2", "ghost"],
                     starters=["qb1", "rb1", "rb2", "wr1", "wr2", "te2", "ghost"])
    out = advise(lg, roster, PTS, {**POS, "ghost": "RB"}, {}, week=1)
    assert any(w["code"] == "NO_PROJ" and w["player_id"] == "ghost"
               for w in out["warnings"])


def test_a_real_zero_is_not_reported_as_a_missing_projection():
    lg = _league()
    roster = _roster(players=["qb1", "rb1", "rb2", "wr1", "wr2", "te2", "hurt"],
                     starters=["qb1", "rb1", "rb2", "wr1", "wr2", "te2", "hurt"])
    out = advise(lg, roster, {**PTS, "hurt": 0.0}, {**POS, "hurt": "RB"}, {},
                 week=1)
    assert not any(w["player_id"] == "hurt" for w in out["warnings"])


def test_a_rostered_player_the_database_does_not_know_is_reported():
    """optimal_lineup drops anyone missing a position, silently. On a real
    roster that means a player vanishes from the advice with no explanation."""
    lg = _league()
    roster = _roster(players=["qb1", "rb1", "rb2", "wr1", "wr2", "te2", "7712"],
                     starters=["qb1", "rb1", "rb2", "wr1", "wr2", "te2"])
    out = advise(lg, roster, PTS, POS, {}, week=1)
    assert any(w["code"] == "UNKNOWN_PLAYER" and w["player_id"] == "7712"
               for w in out["warnings"])


def test_a_slot_nobody_can_fill_is_reported():
    lg = _league(slots=["QB", "RB", "TE", "BN"])
    roster = _roster(players=["qb1", "rb1"], starters=["qb1", "rb1"])
    out = advise(lg, roster, PTS, POS, {}, week=1)
    assert "TE" in out["optimal"]["unfilled"]


def test_superflex_promotes_a_second_quarterback_into_the_flex():
    lg = _league(slots=["QB", "RB", "WR", "SUPER_FLEX", "BN"], teams=17)
    pts = {**PTS, "qb2": 18.0}
    pos = {**POS, "qb2": "QB"}
    roster = _roster(players=["qb1", "rb1", "wr1", "qb2", "rb2"],
                     starters=["qb1", "rb1", "wr1", "rb2"])
    out = advise(lg, roster, pts, pos, {}, week=1)
    assert [s["in"] for s in out["swaps"]] == ["qb2"]


def test_swaps_is_pure_and_takes_no_league_state():
    """The pairing rule is the unit under test; everything else is plumbing."""
    lg = _league()
    from sleeper.lineup import optimal_lineup

    lg = _league(slots=TWO_SLOTS)
    best = optimal_lineup(list(TWO), TWO, TWO_POS, lg.starter_slots,
                          lg.slot_positions)
    current = list(zip(lg.starter_slots,
                       ["qb1", "rb1", "wr1", "te1", "rb2"]))
    out = swaps(current, best, TWO)
    assert [(s["slot"], s["out"], s["in"]) for s in out] == [
        ("TE", "te1", "te2"), ("FLEX", "rb2", "wr2")]
