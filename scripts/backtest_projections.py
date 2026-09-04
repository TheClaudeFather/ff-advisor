"""Backtest Sleeper/Rotowire preseason projections against actual results.

Usage: python3 scripts/backtest_projections.py [season]
Answers "how much is a VOR gap worth" empirically rather than by assertion.
"""
import json, math, random, subprocess, sys

SEASON = sys.argv[1] if len(sys.argv) > 1 else "2025"
POS = "&".join(f"position%5B%5D={p}" for p in ("QB", "RB", "WR", "TE"))


def get(url):
    r = subprocess.run(["curl", "-sS", url], capture_output=True, text=True)
    return json.loads(r.stdout)


def main():
    proj = get(f"https://api.sleeper.app/projections/nfl/{SEASON}?season_type=regular&{POS}")
    act = get(f"https://api.sleeper.app/stats/nfl/{SEASON}?season_type=regular&{POS}")
    a = {r["player_id"]: (r.get("stats") or {}).get("pts_ppr") for r in act}

    pairs = [(r["player_id"], (r.get("stats") or {}).get("pts_ppr"),
              a.get(r["player_id"])) for r in proj]
    pairs = [(p, x, y) for p, x, y in pairs if x and y is not None]
    pairs.sort(key=lambda t: -t[1])
    top = pairs[:200]

    def pearson(u, v):
        n = len(u); mu = sum(u) / n; mv = sum(v) / n
        num = sum((x - mu) * (y - mv) for x, y in zip(u, v))
        du = math.sqrt(sum((x - mu) ** 2 for x in u))
        dv = math.sqrt(sum((y - mv) ** 2 for y in v))
        return num / (du * dv)

    P = [x for _, x, _ in top]; A = [y for _, _, y in top]
    rp = {v: i for i, v in enumerate(sorted(P))}
    ra = {v: i for i, v in enumerate(sorted(A))}
    print(f"season {SEASON}, top {len(top)} by projection")
    print(f"  Pearson  {pearson(P, A):.3f}")
    print(f"  Spearman {pearson([rp[x] for x in P], [ra[y] for y in A]):.3f}")
    print(f"  mean abs error {sum(abs(x - y) for x, y in zip(P, A)) / len(P):.1f} pts")

    random.seed(0)
    print("\n  reliability by projected gap:")
    for lo, hi in [(0, 25), (25, 50), (50, 100), (100, 10 ** 9)]:
        w = t = 0
        for _ in range(120000):
            (_, x1, y1), (_, x2, y2) = random.sample(top, 2)
            if not (lo <= abs(x1 - x2) < hi) or y1 == y2:
                continue
            t += 1
            w += (x1 > x2) == (y1 > y2)
        if t > 200:
            lbl = f"{lo}-{hi}" if hi < 10 ** 9 else f"{lo}+"
            print(f"    gap {lbl:<10} {100 * w / t:.1f}% correct (n={t})")


if __name__ == "__main__":
    main()
