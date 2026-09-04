"""Measure the lookahead horizon across slots and leagues.

Objective: projected starting lineup points from the tool's own picks, higher
is better. Tuning on a single slot of a single seed would overfit a simulator
whose opponents are ADP bots, so this sweeps several slots in more than one league.
"""
import os, sys, io, contextlib, pathlib, importlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

ALIAS = sys.argv[1] if len(sys.argv) > 1 else None   # None -> default league
SLOTS = [int(x) for x in (sys.argv[2].split(",") if len(sys.argv) > 2 else ["1"])]
LOOKS = [int(x) for x in (sys.argv[3].split(",") if len(sys.argv) > 3 else ["2","4"])]

results = {}
for look in LOOKS:
    os.environ["SLEEPER_LOOKAHEAD"] = str(look)
    import sleeper.advice.draft_advice as da
    importlib.reload(da)
    import mock_variant as mv
    importlib.reload(mv)
    mv.draft_advice = da
    mv.ALIAS = ALIAS
    from sleeper import config, league as league_mod, players
    from sleeper.advice import board as board_mod
    cfg = config.load()
    lg = league_mod.load(config.resolve_league(cfg, ALIAS), offline=True)
    rows, _ = board_mod.build(lg, offline=True)
    db = players.load(offline=True)
    for slot in SLOTS:
        mv.SLOT = slot
        with contextlib.redirect_stdout(io.StringIO()):
            _roster, lu, _log, _p, _pt = mv.run({}, lg, rows, db)
        results[(look, slot)] = lu.total

print(f"{ALIAS}: baseline starting-lineup points by lookahead\n")
print(f"{'slot':<6}" + "".join(f"look={l:<8}" for l in LOOKS))
for slot in SLOTS:
    row = f"{slot:<6}"
    for l in LOOKS:
        row += f"{results[(l,slot)]:<13.1f}"
    print(row)
print()
for l in LOOKS:
    avg = sum(results[(l,s)] for s in SLOTS) / len(SLOTS)
    print(f"  lookahead {l}: mean {avg:.1f}")
