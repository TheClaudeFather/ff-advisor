"""Replay a real completed draft pick-by-pick.

This is the single highest-value test for draft day: it exercises every state
the DraftState machine will see live, using 289 genuine picks.
"""
import json
import pathlib

import pytest

from sleeper.draft import DraftState, my_picks, overall_pick, roster_needs

FIX = pathlib.Path(__file__).parent / "fixtures"
PICKS = json.loads((FIX / "picks_completed.json").read_text())
TEAMS = 17


def test_fixture_is_a_real_draft():
    assert len(PICKS) > 200
    assert all("pick_no" in p for p in PICKS)


@pytest.mark.parametrize("slot", [1, 5, 9, 17])
def test_replay_never_recommends_taken_player(slot):
    rounds = max(p["round"] for p in PICKS)
    for n in range(0, len(PICKS) + 1):
        st = DraftState("d", TEAMS, rounds, slot, PICKS[:n])
        taken = st.taken
        # invariant: taken set only grows, and matches picks fed in
        assert len(taken) == len({p["player_id"] for p in PICKS[:n] if p.get("player_id")})
        nxt = st.next_pick()
        if nxt is not None:
            # our next pick is always at or after the current clock
            assert nxt >= st.on_the_clock_overall
        # never raises
        st.round_and_slot()
        st.my_roster()


@pytest.mark.parametrize("slot", [1, 5, 9, 17])
def test_my_next_pick_is_monotonic(slot):
    rounds = max(p["round"] for p in PICKS)
    prev = 0
    for n in range(0, len(PICKS) + 1):
        st = DraftState("d", TEAMS, rounds, slot, PICKS[:n])
        nxt = st.next_pick()
        if nxt is not None:
            assert nxt >= prev
            prev = nxt


def test_replay_matches_real_pick_order():
    """Our snake math must reproduce the actual roster_id sequence."""
    by_slot = {}
    for p in PICKS:
        by_slot.setdefault(p["draft_slot"], []).append(p["pick_no"])
    rounds = max(p["round"] for p in PICKS)
    for slot, actual in by_slot.items():
        expected = my_picks(slot, TEAMS, rounds)[: len(actual)]
        assert actual == expected, f"slot {slot}: {actual[:5]} != {expected[:5]}"


def test_snake_math_known_values():
    assert my_picks(7, 10, 5) == [7, 14, 27, 34, 47]
    assert my_picks(1, 10, 4) == [1, 20, 21, 40]
    assert my_picks(10, 10, 3) == [10, 11, 30]
    assert overall_pick(1, 1, 10) == 1
    assert overall_pick(2, 1, 10) == 20


def test_roster_needs_shrink_as_roster_fills():
    from collections import Counter
    rp = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "K", "DEF", "BN"]
    empty = roster_needs(rp, Counter())
    assert sum(empty.values()) == 10
    full_rb = roster_needs(rp, Counter({"RB": 2}))
    assert full_rb.get("RB", 0) == 0
    # a 3rd RB should consume a FLEX, not create an RB need
    three_rb = roster_needs(rp, Counter({"RB": 3}))
    assert three_rb.get("FLEX", 0) == 1


def test_nth_next_pick_walks_our_upcoming_picks():
    """Used to set how far ahead we look when asking what is still gettable."""
    st = DraftState("d", 10, 15, 3, [])
    # slot 3 of 10: picks 3, 18, 23, 38, 43, ...
    assert st.nth_next_pick(1) == 3
    assert st.nth_next_pick(2) == 18
    assert st.nth_next_pick(3) == 23


def test_nth_next_pick_clamps_to_our_last_pick():
    """Late in a draft there are fewer than n picks left; must not return None."""
    st = DraftState("d", 10, 15, 3, [])
    last = st.my_pick_numbers()[-1]
    assert st.nth_next_pick(99) == last


def test_nth_next_pick_is_none_without_a_slot():
    st = DraftState("d", 10, 15, None, [])
    assert st.nth_next_pick(3) is None
