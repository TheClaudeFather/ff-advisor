"""The core scoring function: a stat line scored by a league's own settings.

This is the whole value-add over Sleeper's UI, which only ever shows generic
PPR. Verified during design: recomputing Puka Nacua's season projection from
raw components using a full-PPR league's scoring_settings reproduced Sleeper's own
published pts_ppr exactly (312.5).
"""
from __future__ import annotations

# Scoring keys that are conditional on a distribution, not a mean. Multiplying
# a projected mean by these is simply wrong (a player averaging 70 rec yds does
# not earn 0.7 of a 100-yard bonus), so they are excluded and reported instead.
_BONUS_PREFIXES = ("bonus_",)

# Positions with no usable raw components in Sleeper's projections. For these
# we fall back to the precomputed pts_ppr rather than summing components.
FALLBACK_POSITIONS = frozenset({"K", "DEF"})


def scoreable(scoring: dict) -> dict:
    """Scoring keys we can legitimately apply to mean projections."""
    return {k: v for k, v in scoring.items()
            if v and not k.startswith(_BONUS_PREFIXES)}


def score_line(stats: dict, scoring: dict) -> float:
    """Dot product over the intersection of keys. THE function."""
    if not stats:
        return 0.0
    return sum(w * stats[k] for k, w in scoring.items() if k in stats and w)


def score_player(stats: dict, scoring: dict, position: str) -> float:
    """Score a player, falling back to pts_ppr for K/DEF."""
    if position in FALLBACK_POSITIONS:
        return float(stats.get("pts_ppr") or 0.0)
    return score_line(stats, scoreable(scoring))


def unscored_keys(scoring: dict, available_stat_keys: set) -> dict:
    """Non-zero scoring keys we cannot compute. The honest blind-spot report.

    Returns {key: weight}. Mostly K/DST tier scoring and threshold bonuses.
    """
    return {k: v for k, v in scoring.items()
            if v and (k not in available_stat_keys or k.startswith(_BONUS_PREFIXES))}
