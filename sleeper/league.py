"""League model: config, scoring, roster shape, my roster."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import api

# Slots that hold players but are not part of the starting lineup.
NON_STARTER = frozenset({"BN", "IR", "TAXI"})

# Which positions may fill which slot. Unknown slots are treated as bench.
SLOT_ELIGIBILITY = {
    "QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"},
    "K": {"K"}, "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"},
    "WRRB_FLEX": {"RB", "WR"},
    "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
}


@dataclass
class League:
    league_id: str
    name: str
    scoring: dict
    roster_positions: list
    n_teams: int
    season: str
    settings: dict = field(default_factory=dict)
    my_roster_id: int | None = None
    unknown_slots: list = field(default_factory=list)

    @property
    def starter_slots(self) -> list:
        """Ordered starting slots (excludes bench/IR/taxi)."""
        return [s for s in self.roster_positions if s not in NON_STARTER]

    @property
    def bench_count(self) -> int:
        return sum(1 for s in self.roster_positions if s == "BN")

    def slot_positions(self, slot: str) -> set:
        return SLOT_ELIGIBILITY.get(slot, set())


def load(league_id, *, user_id=None, **kw) -> League:
    d = api.league(league_id, **kw)
    rp = d.get("roster_positions") or []
    unknown = sorted({s for s in rp if s not in NON_STARTER and s not in SLOT_ELIGIBILITY})

    lg = League(
        league_id=str(league_id), name=d["name"], scoring=d["scoring_settings"],
        roster_positions=rp, n_teams=d["settings"]["num_teams"],
        season=d["season"], settings=d["settings"], unknown_slots=unknown,
    )
    if user_id:
        for r in api.rosters(league_id, **kw):
            if r.get("owner_id") == str(user_id):
                lg.my_roster_id = r["roster_id"]
                break
    return lg


def my_players(league_id, roster_id, **kw) -> list:
    for r in api.rosters(league_id, **kw):
        if r["roster_id"] == roster_id:
            return list(r.get("players") or [])
    return []


def rostered_players(league_id, **kw) -> set:
    out = set()
    for r in api.rosters(league_id, **kw):
        out |= set(r.get("players") or [])
    return out
