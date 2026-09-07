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
            if owns(r, user_id):
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


EMPTY_SLOT = "0"


@dataclass
class Roster:
    """A team as Sleeper stores it.

    `starters` is positional against roster_positions and uses "0" for a slot
    nobody is in, so it is filtered here rather than at every call site.
    """
    roster_id: int
    owner_id: str | None
    players: list
    starters: list
    reserve: list
    taxi: list

    @property
    def set_lineup(self) -> bool:
        """Has this team actually put anyone in a slot?

        Early in the week most of a league has not, which is why opponent
        projections fall back to the best lineup a team could field.
        """
        return bool(self.starters)

    @property
    def bench(self) -> list:
        return [p for p in self.players if p not in set(self.starters)]

    @property
    def active(self) -> list:
        """Everyone who may be put in a starting slot.

        `players` includes injured reserve and taxi. Handing that list to the
        lineup optimizer would happily start a player on IR.
        """
        out = set(self.reserve) | set(self.taxi)
        return [p for p in self.players if p not in out]


def owns(raw_roster: dict, user_id) -> bool:
    """Does this user manage this team?

    Sleeper names only one manager in owner_id, so a co-owned team resolved to
    no roster at all and every command would report that it cannot find your
    team.
    """
    if not user_id:
        return False
    uid = str(user_id)
    if str(raw_roster.get("owner_id")) == uid:
        return True
    return uid in {str(c) for c in (raw_roster.get("co_owners") or [])}


def _roster(raw: dict) -> Roster:
    return Roster(
        roster_id=raw.get("roster_id"),
        owner_id=raw.get("owner_id"),
        players=list(raw.get("players") or []),
        starters=[p for p in (raw.get("starters") or []) if p and p != EMPTY_SLOT],
        reserve=list(raw.get("reserve") or []),
        taxi=list(raw.get("taxi") or []),
    )


def rosters_from(raw_rosters) -> list:
    """Parse the rosters payload. Pure, so it tests without the network."""
    return [_roster(r) for r in (raw_rosters or [])]


def pick_roster(rosters, roster_id):
    return next((r for r in rosters if r.roster_id == roster_id), None)


def all_rosters(league_id, **kw) -> list:
    return rosters_from(api.rosters(league_id, **kw))


def roster_of(league_id, roster_id, **kw):
    """One team, or None when the roster_id is unknown."""
    if roster_id is None:
        return None
    return pick_roster(all_rosters(league_id, **kw), roster_id)
