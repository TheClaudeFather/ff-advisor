"""One command for the weekly routine.

The digest is composition: every number in it comes from a function that is
already tested on its own. What it owns is deciding which sections apply, and
recording what was projected so that accuracy can be measured later.
"""
import json

from sleeper.advice.digest import build, snapshot
from sleeper.league import League, Roster

PPR = {"rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0}
SLOTS = ["QB", "RB", "WR", "BN"]
POS = {"qb1": "QB", "rb1": "RB", "rb2": "RB", "wr1": "WR", "fa_wr": "WR"}
PTS = {"qb1": 20.0, "rb1": 15.0, "rb2": 6.0, "wr1": 5.0, "fa_wr": 12.0}


def _league():
    return League("77", "Test", PPR, SLOTS, 10, "2026")


def _roster(rid=1, players=None, slots=None):
    players = players or ["qb1", "rb1", "rb2", "wr1"]
    slots = slots if slots is not None else ["qb1", "rb1", "wr1"]
    return Roster(roster_id=rid, owner_id=f"u{rid}", players=players,
                  starters=[p for p in slots if p and p != "0"],
                  slots=slots, reserve=[], taxi=[])


def _build(**kw):
    args = dict(week=3, week_pts=PTS, ros_pts=PTS, pos_of=POS, db={},
                free_ids={"fa_wr"}, rosters=None, elimination=False)
    args.update(kw)
    return build(_league(), _roster(), **args)


def test_the_digest_carries_every_weekly_decision():
    out = _build()
    assert set(out) >= {"week", "league", "lineup", "waivers", "drops"}


def test_a_head_to_head_league_has_no_cut_line():
    assert _build()["survival"] is None


def test_an_elimination_league_ranks_the_field():
    out = _build(elimination=True, rosters=[_roster(1), _roster(2)])
    assert out["survival"]["my_rank"] == 1


def test_the_lineup_section_is_the_same_answer_the_lineup_command_gives():
    from sleeper.advice.lineup_advice import advise

    direct = advise(_league(), _roster(), PTS, POS, {}, week=3)
    assert _build()["lineup"]["swaps"] == direct["swaps"]


def test_the_waiver_section_respects_the_roster_it_is_given():
    """fa_wr outscores the receiver being started, so he is a real upgrade."""
    out = _build()
    assert out["waivers"][0]["player_id"] == "fa_wr"
    assert out["waivers"][0]["marginal"] > 0


def test_a_snapshot_records_what_was_projected(tmp_path):
    """Accuracy tracking later needs to know what the tool believed at the time,
    which no cache preserves once the week is played."""
    path = snapshot(tmp_path, "77", 3, {"qb1": 20.0, "rb1": 15.0})
    assert path.exists()
    saved = json.loads(path.read_text())
    assert saved["league_id"] == "77" and saved["week"] == 3
    assert saved["points"]["qb1"] == 20.0


def test_a_second_snapshot_for_the_same_week_replaces_the_first(tmp_path):
    snapshot(tmp_path, "77", 3, {"qb1": 20.0})
    path = snapshot(tmp_path, "77", 3, {"qb1": 21.0})
    assert json.loads(path.read_text())["points"]["qb1"] == 21.0


def test_snapshots_of_different_weeks_do_not_collide(tmp_path):
    a = snapshot(tmp_path, "77", 3, {"qb1": 20.0})
    b = snapshot(tmp_path, "77", 4, {"qb1": 18.0})
    assert a != b and a.exists() and b.exists()
