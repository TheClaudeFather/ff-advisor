"""draft_order -> slot resolution, against a real completed draft (anonymized).

This path cannot be exercised before a draft starts, because Sleeper leaves
draft_order null until then. A completed draft has it populated, and the picks
themselves give ground truth, so the mapping can be verified offline.
"""
import json
import pathlib

FIX = pathlib.Path(__file__).parent / "fixtures"
META = json.loads((FIX / "draft_meta_completed.json").read_text())
PICKS = json.loads((FIX / "picks_completed.json").read_text())
USER = "900000000000000004"


def _truth():
    """{user_id: slot} derived from the picks themselves."""
    out = {}
    for p in PICKS:
        if p.get("picked_by"):
            out.setdefault(p["picked_by"], set()).add(p["draft_slot"])
    return {u: s.pop() for u, s in out.items() if len(s) == 1}


def test_draft_order_is_published_for_a_started_draft():
    assert META.get("draft_order"), "completed draft must carry draft_order"
    assert len(META["draft_order"]) == META["settings"]["teams"]


def test_draft_order_matches_who_actually_picked_where():
    order, truth = META["draft_order"], _truth()
    assert truth
    for uid, slot in truth.items():
        assert order.get(uid) == slot, f"{uid}: order={order.get(uid)} actual={slot}"


def test_our_slot_resolves_and_pick_numbers_match_reality():
    from sleeper.draft import my_picks
    slot = META["draft_order"][USER]
    assert slot == _truth()[USER]
    computed = my_picks(slot, META["settings"]["teams"], META["settings"]["rounds"])
    actual = sorted(p["pick_no"] for p in PICKS if p.get("picked_by") == USER)
    assert computed[: len(actual)] == actual


def test_missing_draft_order_is_survivable():
    """Pre-draft, draft_order is null. Slot must come from --slot or config."""
    from sleeper.draft import DraftState
    st = DraftState("d", 10, 15, None, [])
    assert st.slot is None
    assert st.my_pick_numbers() == []
    assert st.next_pick() is None
    st.round_and_slot()          # must not raise
