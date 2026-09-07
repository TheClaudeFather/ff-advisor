"""Advice must describe the board at OUR pick, not one pick before it.

During a live draft the tool was asked for advice while the pick before ours
was still on the clock. It recommended a quarterback who was taken by that very
pick. Waiting for our turn is a correctness fix, not a convenience.
"""
from sleeper.draft import DraftState, wait_for_turn


def _state(on_clock_offset, slot=3, teams=17):
    """A state whose clock sits `on_clock_offset` picks before ours."""
    made = slot - 1 - on_clock_offset
    picks = [{"pick_no": i, "player_id": str(i), "round": 1}
             for i in range(1, made + 1)]
    return DraftState("d", teams, 17, slot, picks)


def test_it_returns_at_once_when_it_is_already_our_turn():
    calls = []

    def load():
        calls.append(1)
        return _state(0)

    st = wait_for_turn(load, timeout=10, interval=0, sleep=lambda s: None)
    assert st.is_my_turn()
    assert len(calls) == 1


def test_it_keeps_polling_until_our_turn_arrives():
    states = [_state(2), _state(1), _state(0)]
    slept = []

    st = wait_for_turn(lambda: states.pop(0), timeout=10, interval=2,
                       sleep=slept.append, now=lambda: 0.0)
    assert st.is_my_turn()
    assert slept == [2, 2]


def test_it_gives_up_at_the_timeout_and_returns_the_last_board():
    """A missed turn must still produce advice, not silence on a pick clock."""
    clock = iter([0.0, 1.0, 99.0])

    st = wait_for_turn(lambda: _state(2), timeout=10, interval=1,
                       sleep=lambda s: None, now=lambda: next(clock))
    assert not st.is_my_turn()
