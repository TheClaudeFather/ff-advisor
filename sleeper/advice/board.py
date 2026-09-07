"""Ranked draft board: league-scored points -> VOR -> tiers."""
from __future__ import annotations

from .. import players, projections, valuation


def build(lg, *, horizon="season", current_week=1, offline=False):
    """-> (rows, meta). rows: list of dicts sorted by VOR desc.

    horizon is "season", "week:N", or "ros". Points come from the horizon;
    average draft position and the blind-spot report always come from the
    season feed, because weekly feeds carry no ADP and "ros" has no single
    feed to read either from.
    """
    db = players.load(offline=offline)
    pos_of = {p: d.get("position") for p, d in db.items()}

    raw = projections.raw(lg.season, "season", offline=offline)
    pts, _opp = projections.points(lg, horizon, current_week=current_week,
                                   offline=offline)
    # Sleeper publishes a separate average draft position for two-quarterback
    # formats. In a SUPER_FLEX league every team wants two quarterbacks, so
    # quarterbacks go far earlier than the one-quarterback number implies, and
    # everyone else goes slightly later. Use the market number for the format
    # instead of estimating the shift.
    adp_key = "adp_2qb" if "SUPER_FLEX" in lg.starter_slots else "adp_ppr"
    adp = {}
    for r in raw:
        s = r.get("stats") or {}
        if s.get(adp_key) is not None:
            adp[r["player_id"]] = s[adp_key]

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
            "adp_source": adp_key,
            "notes": notes,
            "unscored": projections.diagnostics(lg, raw)}
    return rows, meta
