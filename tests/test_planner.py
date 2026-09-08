"""Looking ahead: byes and injuries that leave a slot you cannot fill.

Sleeper's player payload has no usable bye_week field, and the weekly
projection feed lists every team in every week, so a bye cannot be found by a
team going missing. What does identify it is the whole team projecting nothing:
in week 6 of 2026 exactly three teams total under a point.
"""
from sleeper.advice.planner import bye_weeks, outlook
from sleeper.league import League, Roster

PPR = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0}
SLOTS = ["QB", "RB", "TE", "BN", "BN"]
POS = {"qb1": "QB", "qb2": "QB", "rb1": "RB", "rb2": "RB", "te1": "TE"}


def _league():
    return League("1", "Test", PPR, SLOTS, 10, "2026")


def _roster(players, slots=None):
    slots = slots if slots is not None else players[:3]
    return Roster(roster_id=1, owner_id="u1", players=list(players),
                  starters=[p for p in slots if p and p != "0"],
                  slots=list(slots), reserve=[], taxi=[])


GAMES = [
    {"week": 1, "home": "CAR", "away": "CHI"},
    {"week": 1, "home": "DET", "away": "CIN"},
    {"week": 2, "home": "CHI", "away": "DET"},
]


def test_a_team_with_no_game_that_week_is_on_bye():
    assert bye_weeks(GAMES)[2] == {"CAR", "CIN"}


def test_nobody_is_on_bye_when_everyone_plays():
    assert bye_weeks(GAMES)[1] == set()


def test_every_week_in_the_schedule_is_covered():
    assert sorted(bye_weeks(GAMES)) == [1, 2]


def test_a_missing_side_of_a_game_does_not_invent_a_team():
    games = GAMES + [{"week": 2, "home": "SEA", "away": None}]
    assert None not in bye_weeks(games)[2]


# --- the outlook -------------------------------------------------------------

WEEKS = {
    5: {"qb1": 20.0, "rb1": 15.0, "te1": 8.0, "qb2": 6.0, "rb2": 5.0},
    6: {"qb1": 0.0, "rb1": 15.0, "te1": 8.0, "qb2": 6.0, "rb2": 5.0},
    7: {"qb1": 20.0, "rb1": 15.0, "te1": 0.0, "qb2": 6.0, "rb2": 0.0},
}
BYES = {5: set(), 6: {"BUF"}, 7: {"KC"}}
TEAM_OF = {"qb1": "BUF", "qb2": "SF", "rb1": "SF", "rb2": "KC", "te1": "KC"}


def test_the_outlook_covers_every_week_asked_for():
    rows = outlook(_league(), _roster(["qb1", "rb1", "te1", "qb2", "rb2"]),
                   WEEKS, POS, BYES, TEAM_OF)
    assert [r["week"] for r in rows] == [5, 6, 7]


def test_a_starter_on_bye_is_named():
    rows = outlook(_league(), _roster(["qb1", "rb1", "te1", "qb2", "rb2"]),
                   WEEKS, POS, BYES, TEAM_OF)
    week6 = next(r for r in rows if r["week"] == 6)
    assert week6["on_bye"] == ["qb1"]


def test_the_backup_covers_the_bye_so_nothing_is_unfillable():
    rows = outlook(_league(), _roster(["qb1", "rb1", "te1", "qb2", "rb2"]),
                   WEEKS, POS, BYES, TEAM_OF)
    week6 = next(r for r in rows if r["week"] == 6)
    assert week6["unfilled"] == []
    assert week6["total"] < next(r for r in rows if r["week"] == 5)["total"]


def test_a_slot_filled_by_somebody_projecting_nothing_is_flagged():
    """The only tight end is on bye. The optimizer still puts him in the slot,
    because he is the only one eligible, so the slot is not empty. It is worse
    than empty: it looks filled and scores zero. That is what to report."""
    rows = outlook(_league(), _roster(["qb1", "rb1", "te1", "qb2", "rb2"]),
                   WEEKS, POS, BYES, TEAM_OF)
    week7 = next(r for r in rows if r["week"] == 7)
    assert week7["hollow"] == [["TE", "te1"]]
    assert week7["unfilled"] == []


def test_a_slot_with_no_eligible_player_at_all_is_still_unfilled():
    rows = outlook(_league(), _roster(["qb1", "rb1"]), WEEKS, POS, BYES,
                   TEAM_OF)
    assert all("TE" in r["unfilled"] for r in rows)


def test_a_healthy_week_has_no_hollow_slots():
    rows = outlook(_league(), _roster(["qb1", "rb1", "te1", "qb2", "rb2"]),
                   WEEKS, POS, BYES, TEAM_OF)
    assert next(r for r in rows if r["week"] == 5)["hollow"] == []


def test_a_player_whose_team_is_not_known_is_not_called_a_bye():
    rows = outlook(_league(), _roster(["qb1", "rb1", "te1"]), WEEKS, POS, BYES,
                   {})
    assert all(r["on_bye"] == [] for r in rows)
