"""Text output + staleness banner. All commands print the banner first."""
from __future__ import annotations

from . import cache, players


def _newest_projection_age():
    """How old the freshest projection feed is, or None if none is cached."""
    directory = cache.ROOT / "proj"
    if not directory.exists():
        return None
    ages = []
    for meta in directory.glob("*.meta.json"):
        age = cache.age("proj", meta.name[: -len(".meta.json")])
        if age is not None:
            ages.append(age)
    return min(ages) if ages else None


def banner(*, picks_age=None) -> str:
    bits = [f"players {cache.human_age(players.age_seconds())}"]
    newest = _newest_projection_age()
    if newest is not None:
        bits.append(f"proj {cache.human_age(newest)}")
    if picks_age is not None:
        bits.append(f"picks live {picks_age:.1f}s")
    return "· " + " · ".join(bits)


def table(rows, headers):
    if not rows:
        return "(none)"
    cols = len(headers)
    w = [len(str(h)) for h in headers]
    for r in rows:
        for i in range(cols):
            w[i] = max(w[i], len(str(r[i])))
    out = ["  ".join(str(h).ljust(w[i]) for i, h in enumerate(headers))]
    out.append("  ".join("-" * w[i] for i in range(cols)))
    for r in rows:
        out.append("  ".join(str(r[i]).ljust(w[i]) for i in range(cols)))
    return "\n".join(out)
