"""The two gates that overrode the numbers during a live draft.

1. Kicker and defense were suppressed by rounds remaining alone, so at pick
   236 the tool ranked running backs at -62 VOR above a kicker worth +5, when
   every alternative was already below replacement.
2. The roster-shape cap buried capped players so far down that they vanished
   from the list. A fifth receiver at -37.6 VOR was hidden while -63 running
   backs were shown, with nothing saying why.
"""
from sleeper.advice.draft_advice import streamable_suppressed, with_best_capped


def _row(pid, vor, capped=False):
    return {"player_id": pid, "vor": vor, "capped": capped, "score": vor}


# --- 1. streamable gate -----------------------------------------------------

def test_kickers_are_suppressed_early_when_real_players_remain():
    assert streamable_suppressed(rounds_left=10, best_alternative_vor=50.0)


def test_kickers_are_free_in_the_last_rounds():
    assert not streamable_suppressed(rounds_left=2, best_alternative_vor=50.0)


def test_kickers_are_free_once_every_alternative_is_below_replacement():
    """The live case: -62 VOR backs are not worth more than a +5 kicker."""
    assert not streamable_suppressed(rounds_left=6, best_alternative_vor=-62.7)


def test_a_replacement_level_alternative_does_not_hold_the_gate():
    assert not streamable_suppressed(rounds_left=6, best_alternative_vor=0.0)


# --- 2. capped players stay visible ----------------------------------------

def test_the_best_capped_player_is_shown_when_he_beats_what_is_listed():
    shown = [_row("rb1", -63.0), _row("rb2", -72.0)]
    scored = shown + [_row("wr5", -37.6, capped=True)]
    out = with_best_capped(shown, scored)
    assert [r["player_id"] for r in out] == ["rb1", "rb2", "wr5"]
    assert out[-1]["capped"]


def test_a_capped_player_worse_than_the_list_stays_out():
    shown = [_row("rb1", -20.0)]
    scored = shown + [_row("wr5", -80.0, capped=True)]
    assert with_best_capped(shown, scored) == shown


def test_nothing_is_appended_when_a_capped_player_is_already_shown():
    shown = [_row("wr5", -37.6, capped=True), _row("rb1", -63.0)]
    scored = shown + [_row("wr6", -40.0, capped=True)]
    assert with_best_capped(shown, scored) == shown


def test_an_uncapped_board_is_unchanged():
    shown = [_row("rb1", -20.0)]
    assert with_best_capped(shown, shown) == shown


# --- 3. what counts as an "alternative" ------------------------------------

def test_a_capped_position_does_not_hold_the_kicker_gate_open():
    """Replaying pick 236: a fourth tight end at +14.4 VOR kept a +5 kicker
    suppressed, even though the roster could never start him."""
    from sleeper.advice.draft_advice import best_usable_vor

    avail = [{"pos": "TE", "vor": 14.4}, {"pos": "RB", "vor": -62.7},
             {"pos": "K", "vor": 5.0}]
    assert best_usable_vor(avail, capped_positions={"TE"}) == -62.7


def test_kickers_never_count_as_their_own_alternative():
    from sleeper.advice.draft_advice import best_usable_vor

    avail = [{"pos": "K", "vor": 16.0}, {"pos": "DEF", "vor": 22.0},
             {"pos": "WR", "vor": -5.0}]
    assert best_usable_vor(avail, capped_positions=set()) == -5.0


def test_an_empty_board_scores_zero():
    from sleeper.advice.draft_advice import best_usable_vor

    assert best_usable_vor([], capped_positions=set()) == 0.0
