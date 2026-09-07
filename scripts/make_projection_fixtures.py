"""Regenerate the trimmed projection fixtures used by the in-season tests.

The live feeds are far too big to commit: a single week is 3304 records and
2.3MB, and the season feed is larger. These fixtures keep only records that
project points, only the stat keys the scorer reads, and only the top N by
projected points, which lands each file around 40KB.

Usage: python3 scripts/make_projection_fixtures.py [season] [week]
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sleeper import api  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parents[1] / "tests" / "fixtures"

# Everything scoring.score_line can use, plus the draft board's ADP keys and the
# precomputed totals the K/DEF fallback reads.
KEEP = {
    "pass_yd", "pass_td", "pass_int", "pass_2pt",
    "rush_yd", "rush_td", "rush_att", "rush_2pt",
    "rec", "rec_yd", "rec_td", "rec_2pt",
    "fum_lost", "fum", "bonus_rec_te",
    "pts_ppr", "pts_std", "pts_half_ppr",
    "adp_ppr", "adp_2qb", "adp_std", "adp_half_ppr",
    "gp", "gms_active",
}


def trim(records, limit):
    out = []
    for r in records:
        stats = r.get("stats") or {}
        if not stats.get("pts_ppr"):
            continue
        player = r.get("player") or {}
        out.append({
            "player_id": r.get("player_id"),
            "week": r.get("week"),
            "opponent": r.get("opponent"),
            "player": {k: player.get(k) for k in
                       ("first_name", "last_name", "position", "team")},
            "stats": {k: v for k, v in stats.items() if k in KEEP},
        })
    out.sort(key=lambda r: -r["stats"]["pts_ppr"])
    return out[:limit]


def main():
    season = sys.argv[1] if len(sys.argv) > 1 else "2026"
    week = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    pairs = [
        (f"projections_season_{season}_top.json",
         trim(api.projections_season(season), 220)),
        (f"projections_week{week}_{season}_top.json",
         trim(api.projections_week(season, week), 160)),
    ]
    for name, records in pairs:
        path = OUT / name
        path.write_text(json.dumps(records, separators=(",", ":")))
        print(f"{name}: {len(records)} records, {path.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main()
