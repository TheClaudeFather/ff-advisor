"""Text output + staleness banner. All commands print the banner first."""
from __future__ import annotations

from . import cache, players


def banner(*, picks_age=None) -> str:
    bits = [f"players {cache.human_age(players.age_seconds())}"]
    for ns, key, label in [("proj", None, "proj")]:
        pass
    import glob, os
    pdir = cache.ROOT / "proj"
    if pdir.exists():
        newest = None
        for f in glob.glob(str(pdir / "*.meta.json")):
            k = os.path.basename(f)[:-10]
            a = cache.age("proj", k)
            if a is not None and (newest is None or a < newest):
                newest = a
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
