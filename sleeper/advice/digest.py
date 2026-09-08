"""The weekly routine in one command.

Everything here comes from a function tested on its own. What this owns is
deciding which sections apply to a league, and recording what was projected so
that the projections can be graded later.

Two horizons on purpose: the lineup question is about this Sunday, while adds
and drops are about the rest of the season, because one week is too noisy to
justify a roster move.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import lineup_advice, survival, wire


def build(lg, roster, *, week, week_pts, ros_pts, pos_of, db, free_ids,
          rosters=None, elimination=False, cut=1, top=5) -> dict:
    lineup = lineup_advice.advise(lg, roster, week_pts, pos_of, db, week=week)
    targets = wire.waiver_targets(lg, roster, ros_pts, pos_of, free_ids, top=top)
    drops = wire.drop_ranking(lg, roster, ros_pts, pos_of, free_ids)[:top]

    cut_line = None
    if elimination and rosters:
        teams = [survival.project_team(lg, r, week_pts, pos_of) for r in rosters]
        cut_line = survival.cut_margin(teams, roster.roster_id, cut=cut)

    return {
        "league": lg.name,
        "league_id": lg.league_id,
        "week": week,
        "lineup": lineup,
        "waivers": targets,
        "drops": drops,
        "survival": cut_line,
    }


def snapshot(home: Path, league_id: str, week: int, points: dict, *,
             set_ids=None, recommended_ids=None) -> Path:
    """Record what was projected and both lineups, before the week is played.

    No cache preserves any of it. A weekly feed is overwritten as it is
    revised, the lineup that was set is replaced the moment it is changed, and
    once the games are done the projection is gone. Grading the projections
    later needs what the tool believed; grading the advice needs what was set
    against what was recommended.
    """
    directory = Path(home) / "snapshots"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{league_id}_week{week}.json"
    path.write_text(json.dumps({
        "league_id": str(league_id),
        "week": week,
        "taken_at": time.time(),
        "points": {p: round(v, 3) for p, v in points.items()},
        "set": list(set_ids) if set_ids is not None else None,
        "recommended": list(recommended_ids) if recommended_ids is not None
        else None,
    }))
    return path
