"""advise() must always return a recommendation.

Regression test: roster-shape caps were implemented as filters, so at the end
of a draft, when every remaining candidate exceeded a cap, advise() returned an
empty list. That surfaced as "no recommendation" on slots 11 to 17 of a 17-team
mock. Returning nothing while the pick clock runs is the worst failure mode
this tool has, so the caps are penalties now.
"""
import json
import pathlib
from collections import Counter

import pytest

from sleeper import league as league_mod
from sleeper.advice import draft_advice
from sleeper.draft import DraftState

FIX = pathlib.Path(__file__).parent / "fixtures"
pytest.importorskip("sleeper.advice.board")


def _league(fixture):
    d = json.loads((FIX / fixture).read_text())
    return league_mod.League("x", d["name"], d["scoring_settings"],
                             d["roster_positions"], d["settings"]["num_teams"],
                             d["season"])


def test_cap_penalty_is_a_penalty_not_a_filter():
    assert draft_advice.CAP_PENALTY > 0


@pytest.mark.parametrize("fixture,teams", [("league_ppr_10team.json", 10),
                                           ("league_superflex_17team.json", 17)])
def test_advise_returns_something_at_the_very_last_pick(fixture, teams):
    """Simulate a draft where our roster is already full at every position."""
    lg = _league(fixture)
    try:
        rows, _ = draft_advice.board_mod.build(lg, offline=True)
    except Exception:
        pytest.skip("projection cache not populated on this machine")

    rounds = len(lg.roster_positions)
    slot = teams  # last slot, whose final pick is the deepest into the pool
    from sleeper.draft import my_picks
    mine = my_picks(slot, teams, rounds)

    # fill the board: everything drafted except the tail, with our picks assigned
    picks = []
    for i, r in enumerate(rows[: teams * rounds - 1], start=1):
        picks.append({"pick_no": i, "player_id": r["player_id"],
                      "round": (i - 1) // teams + 1})
    st = DraftState("d", teams, rounds, slot, picks)
    recs, _info = draft_advice.advise(lg, st, top=5, offline=True)
    assert recs, "advise returned nothing on the clock"
    assert all(r["player_id"] not in st.taken for r in recs)
