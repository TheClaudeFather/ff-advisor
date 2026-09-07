"""Which NFL week we are in.

Every in-season number depends on this. Nothing wired it before, so
projections.raw and projections.points both fell back to week 1: weekly feeds
cached for 6 hours instead of forever, and the rest-of-season horizon summed
weeks 1 to 18 rather than the weeks that remain.
"""
from __future__ import annotations

FIRST_WEEK = 1
LAST_WEEK = 18


def _as_week(value):
    try:
        week = int(value)
    except (TypeError, ValueError):
        return None
    return week if week else None


def resolve_week(state: dict, override=None) -> int:
    """The week to advise on, from Sleeper's state payload.

    `display_week` wins over `week`, because between games Sleeper advances
    `week` first and the lineup a person is setting is the one their screen
    shows. Anything unusable falls back to week 1, and the result is clamped to
    the regular season.
    """
    week = (_as_week(override)
            or _as_week((state or {}).get("display_week"))
            or _as_week((state or {}).get("week"))
            or FIRST_WEEK)
    return max(FIRST_WEEK, min(LAST_WEEK, week))


def live_week(state: dict) -> int:
    """The week currently being played.

    Not the same question as `resolve_week`. On a Tuesday Sleeper advances
    `display_week` to the week you are setting a lineup for while `week` is
    still the one just played. Only weeks strictly before this one are
    finished, so this is the boundary that decides which weekly feeds are
    immutable and can be cached forever.
    """
    week = _as_week((state or {}).get("week")) or FIRST_WEEK
    return max(FIRST_WEEK, min(LAST_WEEK, week))


def week_of(override=None, *, offline=False) -> int:
    """The live week, fetched. Cheap: api.state is cached for an hour."""
    from . import api

    try:
        state = api.state(offline=offline)
    except Exception:  # noqa: BLE001 - never fail a lineup call over the clock
        state = {}
    return resolve_week(state, override)
