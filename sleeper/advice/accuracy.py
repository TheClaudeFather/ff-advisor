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


def grade(projected: dict, actual: dict, pos_of: dict, *, week=None) -> dict:
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
        "worst": sorted(rows, key=lambda r: -abs(r["error"])),
    }
