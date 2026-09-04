"""Ranked draft board: league-scored points -> VOR -> tiers."""
from __future__ import annotations

from .. import players, projections, valuation


def build(lg, *, horizon="season", offline=False):
    """-> (rows, meta). rows: list of dicts sorted by VOR desc."""
    db = players.load(offline=offline)
    pos_of = {p: d.get("position") for p, d in db.items()}

    raw = projections.raw(lg.season, horizon, offline=offline)
    pts, _opp = projections.points(lg, horizon, offline=offline)
    adp = {}
    for r in raw:
        s = r.get("stats") or {}
        if s.get("adp_ppr") is not None:
            adp[r["player_id"]] = s["adp_ppr"]

    repl, notes = valuation.replacement_points(pts, pos_of, lg)
    v = valuation.vor(pts, pos_of, repl)
    ranked = sorted(((p, x) for p, x in v.items() if p in db), key=lambda kv: -kv[1])

    by_pos_ranked = {}
    for p, x in ranked:
        by_pos_ranked.setdefault(pos_of[p], []).append((p, x))
    tier_of = {}
    for pos, lst in by_pos_ranked.items():
        for (p, _x), t in zip(lst, valuation.tiers(lst)):
            tier_of[p] = t

    rows = []
    for p, x in ranked:
        d = db[p]
        rows.append({
            "player_id": p, "name": d["name"], "pos": pos_of[p],
            "team": d.get("team") or "FA", "pts": round(pts.get(p, 0.0), 1),
            "vor": x, "tier": tier_of.get(p, 1), "adp": adp.get(p),
            "injury": d.get("injury_status"),
        })
    meta = {"replacement": {k: round(x, 1) for k, x in repl.items()},
            "notes": notes,
            "unscored": projections.diagnostics(lg, raw)}
    return rows, meta
