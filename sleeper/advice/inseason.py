"""In-season value: what a player is worth against what the wire can give you.

Draft replacement is "the Nth best player in the NFL", derived from
roster_positions times the number of teams. Once the season starts that is the
wrong yardstick. Nobody drafts a replacement mid-season: they add the best free
agent at the position, so that player is the true replacement level, and the
gap to him is what a roster spot is actually worth.
"""
from __future__ import annotations


def free_agent_ids(points: dict, rostered) -> set:
    """Every projected player nobody in the league rosters."""
    return {pid for pid in points if pid not in set(rostered)}


def best_available(points: dict, pos_of: dict, free_ids) -> dict:
    """{position: (player_id, points)} for the top free agent at each position.

    Depth one, not the Nth best: the alternative to a roster spot is the single
    best player you can add for nothing.
    """
    best = {}
    for pid in free_ids:
        pos = pos_of.get(pid)
        if not pos:
            continue
        value = points.get(pid, 0.0)
        if pos not in best or value > best[pos][1]:
            best[pos] = (pid, value)
    return best


def replaceability(player_id: str, points: dict, pos_of: dict,
                   best: dict) -> float:
    """How much a player beats the best free agent at his position.

    Negative means the wire can beat him. With nobody available at all he is
    worth all of himself, not zero.
    """
    pos = pos_of.get(player_id)
    mine = points.get(player_id, 0.0)
    replacement = best.get(pos, (None, 0.0))[1]
    return round(mine - replacement, 2)
