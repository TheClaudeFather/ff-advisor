"""Draft state: snake math, taken players, roster needs, pick urgency."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from . import api
from .league import NON_STARTER


def overall_pick(round_no, slot, teams, reversal_round=0) -> int:
    """1-indexed overall pick number for (round, slot) in a snake draft."""
    snake = round_no % 2 == 0
    if reversal_round and round_no >= reversal_round:
        snake = not snake
    pos = (teams - slot + 1) if snake else slot
    return (round_no - 1) * teams + pos


def my_picks(slot, teams, rounds, reversal_round=0) -> list:
    return [overall_pick(r, slot, teams, reversal_round) for r in range(1, rounds + 1)]


@dataclass
class DraftState:
    draft_id: str
    teams: int
    rounds: int
    slot: int | None
    picks: list
    reversal_round: int = 0
    status: str = "pre_draft"
    stale: float = 0.0   # seconds old if served from the fallback snapshot

    @property
    def made(self) -> int:
        return len(self.picks)

    @property
    def taken(self) -> set:
        return {p["player_id"] for p in self.picks if p.get("player_id")}

    @property
    def on_the_clock_overall(self) -> int:
        return self.made + 1

    def my_pick_numbers(self) -> list:
        if self.slot is None:
            return []
        return my_picks(self.slot, self.teams, self.rounds, self.reversal_round)

    def next_pick(self) -> int | None:
        nxt = [p for p in self.my_pick_numbers() if p >= self.on_the_clock_overall]
        return nxt[0] if nxt else None

    def pick_after_next(self) -> int | None:
        nxt = [p for p in self.my_pick_numbers() if p >= self.on_the_clock_overall]
        return nxt[1] if len(nxt) > 1 else None

    def nth_next_pick(self, n) -> int | None:
        """Our n-th upcoming pick (1 = the one on the clock now)."""
        nxt = [p for p in self.my_pick_numbers() if p >= self.on_the_clock_overall]
        return nxt[n - 1] if len(nxt) >= n else (nxt[-1] if nxt else None)

    def is_my_turn(self) -> bool:
        return self.next_pick() == self.on_the_clock_overall

    def picks_until_mine(self) -> int | None:
        n = self.next_pick()
        return None if n is None else n - self.on_the_clock_overall

    def round_and_slot(self, overall=None):
        o = overall or self.on_the_clock_overall
        rnd = (o - 1) // self.teams + 1
        idx = (o - 1) % self.teams + 1
        s = (self.teams - idx + 1) if rnd % 2 == 0 else idx
        return rnd, s

    def my_roster(self) -> list:
        if self.slot is None:
            return []
        mine = set(self.my_pick_numbers())
        return [p["player_id"] for p in self.picks
                if p.get("pick_no") in mine and p.get("player_id")]


def load_state(league_id, *, slot=None, draft_id=None, live=True) -> DraftState:
    if draft_id is None:
        drafts = api.league_drafts(league_id)
        if not drafts:
            raise SystemExit("No draft found for this league.")
        active = [d for d in drafts if d.get("status") != "complete"]
        pool = active or drafts
        pool.sort(key=lambda d: d.get("start_time") or 0, reverse=True)
        draft_id = pool[0]["draft_id"]

    meta = api.draft(draft_id)
    st = meta.get("settings", {})
    teams = st.get("teams") or 10
    rounds = st.get("rounds") or 15

    if slot is None:
        order = meta.get("draft_order") or {}
        from . import config
        uid = config.load().get("user_id")
        if uid and str(uid) in order:
            slot = order[str(uid)]

    stale = 0.0
    if live:
        picks, stale = api.draft_picks(draft_id)
    else:
        picks = []
    return DraftState(draft_id=str(draft_id), teams=teams, rounds=rounds, slot=slot,
                      picks=picks, reversal_round=st.get("reversal_round") or 0,
                      status=meta.get("status", "pre_draft"), stale=stale)


def roster_needs(roster_positions, have_positions: Counter) -> dict:
    """Remaining starting slots by position, after filling with what we have."""
    from .league import SLOT_ELIGIBILITY
    remaining = Counter(have_positions)
    needs = Counter()
    slots = [s for s in roster_positions if s not in NON_STARTER]
    for slot in sorted(slots, key=lambda s: len(SLOT_ELIGIBILITY.get(s, set())) or 99):
        ok = SLOT_ELIGIBILITY.get(slot, set())
        hit = next((p for p in ok if remaining.get(p, 0) > 0), None)
        if hit:
            remaining[hit] -= 1
        else:
            needs[slot] += 1
    return dict(needs)


def survival_prob(adp, next_pick) -> float:
    """Crude logistic estimate that a player with this ADP lasts until next_pick.

    Deliberately crude and labelled as such in output. ADP is a national
    number and a weak prior in a 10-person friends league.
    """
    if adp is None or adp <= 0 or next_pick is None:
        return 0.0
    import math
    scale = 8 + 0.15 * adp
    return 1 / (1 + math.exp((next_pick - adp) / scale))
