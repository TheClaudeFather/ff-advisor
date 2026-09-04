"""Run the mock draft across every slot and several opponent behaviours."""
import io, sys, contextlib, pathlib, random
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import mock_draft as md

ALIAS = sys.argv[1] if len(sys.argv) > 1 else None   # None -> default league
SLOTS = range(1, int(sys.argv[2]) + 1) if len(sys.argv) > 2 else range(1, 11)
md.ALIAS = ALIAS

fails, rows = [], []
for slot in SLOTS:
    for seed in (1, 7, 42):
        md.SLOT, md.SEED = slot, seed
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                have, unfilled, worst = md.run(quiet=True)
            status = "ok" if not unfilled else f"UNFILLED {unfilled}"
            if unfilled or worst >= 1.5:
                fails.append((slot, seed, status, worst))
            rows.append((slot, seed, status, round(worst, 2),
                         "".join(f"{k}{v}" for k, v in sorted(have.items()))))
        except Exception as e:
            fails.append((slot, seed, f"EXCEPTION {type(e).__name__}: {e}", None))

print(f"{'slot':<6}{'seed':<6}{'status':<12}{'worst_s':<9}roster")
for r in rows:
    print(f"{r[0]:<6}{r[1]:<6}{r[2]:<12}{r[3]:<9}{r[4]}")
print(f"\n{len(rows)} drafts simulated, {len(fails)} failures")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
