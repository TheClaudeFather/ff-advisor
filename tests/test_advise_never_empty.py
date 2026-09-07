"""advise() must always return a recommendation.

Regression test: roster-shape caps were implemented as filters, so at the end
of a draft, when every remaining candidate exceeded a cap, advise() returned an
empty list. That surfaced as "no recommendation" on slots 11 to 17 of a 17-team
mock. Returning nothing while the pick clock runs is the worst failure mode
this tool has, so the caps are penalties now.

This used to skip itself when the projection cache was cold, which meant it
never ran anywhere except a developer machine that happened to have fetched the
feeds. It now runs against the seeded cache like everything else.
"""
import pytest

from sleeper.advice import draft_advice
from sleeper.draft import DraftState, my_picks


def test_cap_penalty_is_a_penalty_not_a_filter():
    assert draft_advice.CAP_PENALTY > 0


@pytest.fixture
def leagues(ppr_league, superflex_league):
    return {"ppr": (ppr_league, 10), "superflex": (superflex_league, 17)}


@pytest.mark.parametrize("shape", ["ppr", "superflex"])
def test_advise_returns_something_at_the_very_last_pick(shape, leagues,
                                                       seeded_cache):
    """Simulate a draft where our roster is already full at every position."""
    lg, teams = leagues[shape]
    rows, _ = draft_advice.board_mod.build(lg, offline=True)

    rounds = len(lg.roster_positions)
    slot = teams  # last slot, whose final pick is the deepest into the pool
    my_picks(slot, teams, rounds)

    # Fill the board: everything drafted except the tail. The fixture pool is
    # smaller than a whole draft, so take what it has and leave one player.
    taken = rows[: max(1, min(len(rows) - 1, teams * rounds - 1))]
    picks = [{"pick_no": i, "player_id": r["player_id"],
              "round": (i - 1) // teams + 1}
             for i, r in enumerate(taken, start=1)]

    st = DraftState("d", teams, rounds, slot, picks)
    recs, _info = draft_advice.advise(lg, st, top=5, offline=True)
    assert recs, "advise returned nothing on the clock"
    assert all(r["player_id"] not in st.taken for r in recs)


def test_advise_never_recommends_a_drafted_player(ppr_league, seeded_cache):
    rows, _ = draft_advice.board_mod.build(ppr_league, offline=True)
    picks = [{"pick_no": i, "player_id": r["player_id"], "round": 1}
             for i, r in enumerate(rows[:20], start=1)]
    st = DraftState("d", 10, 15, 3, picks)
    recs, _ = draft_advice.advise(ppr_league, st, top=8, offline=True)
    assert recs
    assert not ({r["player_id"] for r in recs} & st.taken)
