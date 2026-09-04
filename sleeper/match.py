"""Resolve a league from the words a person actually says.

Aliases are generated from league names, so they are not what anyone types.
This module describes each configured league by its shape, then scores a free
text phrase against those descriptions. Everything here is a pure function over
data, and the cached league JSON is the only input, so matching never touches
the network.
"""
from __future__ import annotations

import re

_SPLIT = re.compile(r"[^a-z0-9]+")

# Words that appear in almost every league name or question, so they carry no
# signal about which league is meant.
STOPWORDS = frozenset({
    "league", "leagues", "team", "teams", "the", "my", "our", "one", "a", "an",
    "of", "in", "for", "fantasy", "ff", "football", "nfl", "draft", "this",
})

WEIGHT_ALIAS = 10
WEIGHT_TEAMS = 4
WEIGHT_FORMAT = 4
WEIGHT_NAME = 3
WEIGHT_SCORING = 1


def tokens(text: str) -> set:
    return {t for t in _SPLIT.split((text or "").lower()) if t}


def squash(text: str) -> str:
    return _SPLIT.sub("", (text or "").lower())


def _ppr_signals(ppr: float) -> tuple:
    if ppr >= 1:
        return ("ppr", "fullppr")
    if ppr > 0:
        return ("halfppr", "half")
    return ("standard", "nonppr", "noppr")


def describe(league_json: dict, alias: str, *, slot=None) -> dict:
    """Everything about a league that someone might name it by."""
    rp = league_json.get("roster_positions") or []
    teams = int(league_json["settings"]["num_teams"])
    superflex = "SUPER_FLEX" in rp
    ppr = float((league_json.get("scoring_settings") or {}).get("rec") or 0)
    name = league_json.get("name") or ""

    if superflex:
        fmt, fmt_signals = "SUPER_FLEX", ("superflex", "2qb", "sf", "twoqb")
    else:
        fmt, fmt_signals = "1QB", ("1qb", "oneqb", "singleqb")

    ppr_signals = _ppr_signals(ppr)
    scoring_label = {"ppr": "full PPR", "halfppr": "half PPR"}.get(
        ppr_signals[0], "standard scoring")

    signals = {alias.lower(): WEIGHT_ALIAS}
    signals[str(teams)] = WEIGHT_TEAMS
    signals[f"{teams}team"] = WEIGHT_TEAMS
    for sig in fmt_signals:
        signals[sig] = WEIGHT_FORMAT
    for sig in ppr_signals:
        signals.setdefault(sig, WEIGHT_SCORING)
    for word in tokens(name) - STOPWORDS:
        signals.setdefault(word, WEIGHT_NAME)

    return {
        "alias": alias,
        "league_id": str(league_json.get("league_id") or ""),
        "name": name,
        "teams": teams,
        "superflex": superflex,
        "ppr": ppr,
        "slot": slot,
        "summary": f"{teams}-team, {fmt}, {scoring_label}",
        "signals": signals,
    }


def score(descriptor: dict, phrase: str) -> int:
    """How strongly a phrase points at this league. Zero means no signal."""
    words = tokens(phrase)
    flat = squash(phrase)
    total = 0
    for signal, weight in descriptor["signals"].items():
        if signal in words or (len(signal) > 2 and signal in flat):
            total += weight
    return total


def find(descriptors: list, phrase: str) -> list:
    """Every league the phrase points at equally well. Empty when none do.

    More than one result is a real answer, not a failure: the caller must ask
    rather than guess, because picking the wrong league silently is worse than
    one extra question.
    """
    scored = [(score(d, phrase), d) for d in descriptors]
    best = max((s for s, _ in scored), default=0)
    if best <= 0:
        return []
    return [d for s, d in scored if s == best]


def load_descriptors(cfg: dict) -> list:
    """Describe every configured league that is already cached.

    Uncached leagues are skipped rather than fetched. Matching must stay
    instant and offline, because it runs while a pick clock is going.
    """
    from . import cache

    slots = cfg.get("slots") or {}
    out = []
    for alias, league_id in sorted((cfg.get("aliases") or {}).items()):
        raw = cache.peek("league", str(league_id))
        if isinstance(raw, dict) and raw.get("settings"):
            try:
                out.append(describe(raw, alias, slot=slots.get(alias)))
            except (KeyError, TypeError, ValueError):
                continue
    return out
