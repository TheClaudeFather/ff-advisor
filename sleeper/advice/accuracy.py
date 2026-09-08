"""Grading the projections against what actually happened.

The point is to learn how much to trust the numbers, so direction matters as
much as size. A tool that runs three points high on tight ends every week is
telling you something you can act on, and a mean absolute error alone hides it.

Both sides are scored in the league's own settings, so this measures the
projection rather than the difference between two scoring systems.
"""
from __future__ import annotations

UNKNOWN = "UNKNOWN"


def _summary(errors) -> dict:
    if not errors:
        return {"n": 0, "mae": 0.0, "bias": 0.0}
    return {
        "n": len(errors),
        "mae": round(sum(abs(e) for e in errors) / len(errors), 2),
        # Positive means the projection was too high.
        "bias": round(sum(errors) / len(errors), 2),
    }


def grade_decision(set_ids, recommended_ids, actual: dict) -> dict:
    """Did the advice help, measured on what actually happened.

    This grades the tool rather than the projections. A player with no result
    scored nothing, which is the honest way to charge a recommendation that
    started someone who did not play.
    """
    def total(ids):
        return round(sum(actual.get(p, 0.0) for p in ids or []), 2)

    was, could = total(set_ids), total(recommended_ids)
    delta = round(could - was, 2)
    return {"set": was, "recommended": could, "delta": delta,
            # None when no change was recommended: neither a win nor a loss.
            "helped": None if delta == 0 else delta > 0}


def combine(weeks) -> dict:
    """One record out of many weeks.

    Averages are weighted by how many players each week graded, because a week
    that graded 300 should not count the same as one that graded 30. Weeks that
    were never played are left out entirely.
    """
    played = [w for w in weeks if w.get("played")]
    totals, by_pos = {"n": 0, "abs": 0.0, "sum": 0.0}, {}
    decisions = {"weeks": 0, "helped": 0, "hurt": 0, "total_delta": 0.0}

    for w in played:
        o = w["overall"]
        totals["n"] += o["n"]
        totals["abs"] += o["mae"] * o["n"]
        totals["sum"] += o["bias"] * o["n"]
        for pos, v in (w.get("by_pos") or {}).items():
            acc = by_pos.setdefault(pos, {"n": 0, "abs": 0.0, "sum": 0.0})
            acc["n"] += v["n"]
            acc["abs"] += v["mae"] * v["n"]
            acc["sum"] += v["bias"] * v["n"]
        d = w.get("decision")
        if d and d.get("helped") is not None:
            decisions["weeks"] += 1
            decisions["helped"] += 1 if d["helped"] else 0
            decisions["hurt"] += 0 if d["helped"] else 1
            decisions["total_delta"] = round(
                decisions["total_delta"] + d["delta"], 2)

    def summarise(acc):
        if not acc["n"]:
            return {"n": 0, "mae": 0.0, "bias": 0.0}
        return {"n": acc["n"],
                "mae": round(acc["abs"] / acc["n"], 2),
                "bias": round(acc["sum"] / acc["n"], 2)}

    return {"weeks": [w["week"] for w in played],
            "overall": summarise(totals),
            "by_pos": {pos: summarise(acc) for pos, acc in sorted(by_pos.items())},
            "decisions": decisions}


def grade(projected: dict, actual: dict, pos_of: dict, *, week=None,
          set_ids=None, recommended_ids=None) -> dict:
    """Compare a week's projection against its result.

    A player missing from the stats feed did not score, which is a real miss if
    he was projected to play, so he is graded as a zero and counted separately.
    """
    rows, by_pos, missing = [], {}, 0
    for pid, expected in projected.items():
        if pid not in actual:
            missing += 1
        scored = actual.get(pid, 0.0)
        error = round(expected - scored, 2)
        rows.append({"player_id": pid, "pos": pos_of.get(pid) or UNKNOWN,
                     "projected": round(expected, 2), "actual": round(scored, 2),
                     "error": error})
        by_pos.setdefault(pos_of.get(pid) or UNKNOWN, []).append(error)

    return {
        "week": week,
        # Sleeper publishes a stats feed for a week that has not happened, with
        # every value at zero. Grading that reports every projection as wildly
        # too high, which measures nothing.
        "played": any(r["actual"] for r in rows),
        "overall": _summary([r["error"] for r in rows]),
        "by_pos": {pos: _summary(errors) for pos, errors in sorted(by_pos.items())},
        "n_no_actual": missing,
        # Absent from snapshots written before lineups were recorded.
        "decision": (grade_decision(set_ids, recommended_ids, actual)
                     if set_ids is not None and recommended_ids is not None
                     else None),
        "worst": sorted(rows, key=lambda r: -abs(r["error"])),
    }
