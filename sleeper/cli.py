"""sleeper - multi-league fantasy football advisor. ADVISE ONLY: never writes."""
from __future__ import annotations

import argparse
import json as jsonlib
import sys
import time

from . import api, cache, config, draft as draft_mod, league as league_mod, players, render
from .advice import board as board_mod
from .advice import draft_advice


def _lg(args, cfg):
    lid = config.resolve_league(cfg, getattr(args, "league", None))
    return league_mod.load(lid, user_id=cfg.get("user_id"), offline=args.offline)


def _slot(args, cfg):
    """Draft slot from --slot, else the value stored in config for this league.

    Storing it removes a draft-day failure mode: Sleeper may not publish
    draft_order until the draft starts, and a wrong slot silently breaks all
    pick math.
    """
    if getattr(args, "slot", None):
        return args.slot
    alias = getattr(args, "league", None) or cfg.get("default_league")
    return (cfg.get("slots") or {}).get(alias)


def cmd_leagues(args, cfg):
    username = config.require_username(cfg)
    if not cfg.get("user_id"):
        cfg["user_id"] = api.user(username)["user_id"]
    season = args.season or api.state()["season"]
    cfg["season"] = season
    ls = api.leagues(cfg["user_id"], season, refresh=args.refresh)
    rows, aliases = [], dict(cfg.get("aliases") or {})
    for l in ls:
        alias = "".join(c for c in l["name"].lower() if c.isalnum())[:12]
        aliases[alias] = l["league_id"]
        rows.append([alias, l["name"], l["settings"]["num_teams"],
                     l.get("status"), l["league_id"]])
    cfg["aliases"] = aliases
    if not cfg.get("default_league") and rows:
        cfg["default_league"] = rows[0][0]
    config.save(cfg)
    if args.json:
        return rows
    print(render.banner())
    print(render.table(rows, ["alias", "name", "teams", "status", "league_id"]))
    print(f"\ndefault league: {cfg['default_league']}  (saved to {config.path()})")


def cmd_env(args, cfg):
    """Show the resolved configuration and where it comes from."""
    from . import env as env_mod
    data = {"env_file": str(config.path()), "home": str(env_mod.home()),
            "notes": str(config.notes_path()), **cfg}
    if args.json:
        return data
    print(render.banner())
    print(f"env file: {config.path()}"
          f"{'' if config.path().exists() else '   (not created yet)'}")
    print(f"home:     {env_mod.home()}")
    notes = config.notes_path()
    print(f"notes:    {notes}{'' if notes.exists() else '   (none)'}")
    print(f"username: {cfg.get('username') or '(unset)'}")
    print(f"user_id:  {cfg.get('user_id') or '(unset)'}")
    print(f"season:   {cfg.get('season') or '(from Sleeper state)'}")
    print(f"default:  {cfg.get('default_league') or '(unset)'}")
    aliases = cfg.get("aliases") or {}
    slots = cfg.get("slots") or {}
    if not aliases:
        print("leagues:  (none - run: sleeper leagues)")
    for alias, lid in sorted(aliases.items()):
        slot = f"   slot {slots[alias]}" if alias in slots else ""
        print(f"  {alias:<14} {lid}{slot}")


def cmd_league_show(args, cfg):
    lg = _lg(args, cfg)
    rows, meta = board_mod.build(lg, offline=args.offline)
    if args.json:
        return {"name": lg.name, "teams": lg.n_teams, "slots": lg.starter_slots,
                "replacement": meta["replacement"], "unscored": meta["unscored"]}
    print(render.banner())
    print(f"{lg.name}  |  {lg.n_teams} teams  |  season {lg.season}")
    print(f"starters: {' '.join(lg.starter_slots)}   bench: {lg.bench_count}")
    print(f"replacement level: {meta['replacement']}")
    for k, m in meta["notes"].items():
        print(f"  ! {k}: {m}")
    if lg.unknown_slots:
        print(f"  ! unknown slots treated as bench: {lg.unknown_slots}")
    un = meta["unscored"]
    if un:
        print(f"\n  blind spots - {len(un)} scoring keys cannot be computed from "
              f"mean projections (mostly K/DST tiers + threshold bonuses):")
        print("   ", ", ".join(sorted(un)[:18]) + (" ..." if len(un) > 18 else ""))


def cmd_refresh(args, cfg):
    what = args.what or "all"
    if what in ("players", "all"):
        n = players.refresh()
        print(f"players: {n} indexed")
    if what in ("projections", "all"):
        season = cfg.get("season") or api.state()["season"]
        api.projections_season(season, refresh=True)
        print(f"season projections {season}: refreshed")
    print(render.banner())


def cmd_player(args, cfg):
    db = players.load(offline=args.offline)
    hits = players.find(db, args.name)
    if not hits:
        raise SystemExit(f"No player matching '{args.name}'")
    if len(hits) > 1 and not args.json:
        print("Multiple matches - be more specific:")
        for pid, p in hits[:12]:
            print("  ", players.label(p))
        return
    pid, p = hits[0]
    lg = _lg(args, cfg)
    rows, _ = board_mod.build(lg, offline=args.offline)
    row = next((r for r in rows if r["player_id"] == pid), None)
    if args.json:
        return row or {"player_id": pid, **p}
    print(render.banner())
    print(players.label(p))
    if row:
        print(f"  in {lg.name}: {row['pts']} pts  VOR {row['vor']}  "
              f"tier {row['tier']}  ADP {row['adp']}")
    else:
        print(f"  NO_PROJ - no projection available in {lg.name}")


def cmd_board(args, cfg):
    lg = _lg(args, cfg)
    rows, meta = board_mod.build(lg, offline=args.offline)
    if args.pos:
        rows = [r for r in rows if r["pos"] == args.pos.upper()]
    rows = rows[: args.top]
    if args.json:
        return {"rows": rows, "meta": meta}
    print(render.banner())
    print(f"{lg.name} - draft board ({lg.n_teams} teams, scored in THIS league)\n")
    print(render.table(
        [[i, r["name"], r["pos"], r["team"], r["pts"], r["vor"], f"T{r['tier']}",
          r["adp"] if r["adp"] is not None else "-", r["injury"] or ""]
         for i, r in enumerate(rows, 1)],
        ["#", "player", "pos", "tm", "pts", "VOR", "tier", "ADP", "inj"]))
    if meta["unscored"]:
        print(f"\n! {len(meta['unscored'])} scoring keys not computable "
              f"(K/DST + bonuses) - K/DEF values are low confidence")


def cmd_draft(args, cfg):
    lg = _lg(args, cfg)
    if args.sub == "prep":
        players.refresh()
        api.projections_season(lg.season, refresh=True)
        rows, meta = board_mod.build(lg)
        path = cache.ROOT / f"frozen_board_{lg.league_id}.json"
        path.write_text(jsonlib.dumps({"rows": rows, "meta": meta}, indent=1))
        print(render.banner())
        print(f"caches warmed. frozen fallback board -> {path}")
        st = draft_mod.load_state(lg.league_id, slot=_slot(args, cfg))
        print(f"draft {st.draft_id}: status={st.status} teams={st.teams} "
              f"rounds={st.rounds} slot={st.slot if st.slot else 'UNKNOWN (pass --slot)'}")
        return

    t0 = time.time()
    st = draft_mod.load_state(lg.league_id, slot=_slot(args, cfg))
    picks_age = time.time() - t0

    if args.sub == "status":
        if args.json:
            return {"status": st.status, "made": st.made, "slot": st.slot,
                    "next_pick": st.next_pick(), "on_clock": st.on_the_clock_overall}
        print(render.banner(picks_age=picks_age))
        print(f"{lg.name}: status={st.status} picks_made={st.made} slot={st.slot}")
        print(f"on the clock: overall {st.on_the_clock_overall} "
              f"(round {st.round_and_slot()[0]})   your next: {st.next_pick()}")
        return

    # advise
    recs, info = draft_advice.advise(lg, st, top=args.top, offline=args.offline)
    if args.json:
        return {"recs": recs, "info": info, "picks_made": st.made,
                "on_clock": st.on_the_clock_overall, "picks_age_s": round(picks_age, 2)}
    print(render.banner(picks_age=picks_age))
    if st.stale:
        print(f"!! STALE: live picks unavailable, using a snapshot "
              f"{st.stale:.0f}s old. Check the Sleeper board before you pick.")
    if st.slot is None:
        print("! draft_order not published yet - pass --slot N for pick math")
    rnd, sl = st.round_and_slot()
    mine = " <<< YOU ARE ON THE CLOCK" if st.is_my_turn() else ""
    print(f"pick {rnd}.{sl:02d} (overall {st.on_the_clock_overall}){mine}")
    if st.next_pick():
        print(f"your next: overall {st.next_pick()} "
              f"({st.picks_until_mine()} away)   then: {st.pick_after_next()}")
    print(f"have: {info['have']}   needs: {info['needs']}\n")
    print(render.table(
        [[i, r["name"], r["pos"], r["team"], r["pts"], r["vor"], f"T{r['tier']}",
          r["adp"] if r["adp"] is not None else "-", f"{r['surv']}%",
          "NEED" if r["need"] else "", r["injury"] or ""]
         for i, r in enumerate(recs, 1)],
        ["#", "player", "pos", "tm", "pts", "VOR", "tier", "ADP", "surv", "", "inj"]))
    print("\nsurv% = crude ADP-based odds he lasts to your next pick. ADP is")
    print("national and a weak prior in a small league. VOR is the real signal.")
    if info.get("superflex"):
        print("SUPER_FLEX: quarterback ADP is shifted earlier, because Sleeper")
        print("publishes 1QB ADP and quarterbacks go much earlier here. Still crude.")


def cmd_live(args, cfg):
    lg = _lg(args, cfg)
    print("live draft panel - Ctrl-C to quit.  ADVISE ONLY: nothing is submitted.")
    last = -1
    try:
        while True:
            t0 = time.time()
            try:
                st = draft_mod.load_state(lg.league_id, slot=_slot(args, cfg))
                recs, info = draft_advice.advise(lg, st, top=args.top, offline=True)
                if st.made != last:
                    last = st.made
                    print("\033[2J\033[H", end="")
                    rnd, sl = st.round_and_slot()
                    mine = "  <<<< YOUR PICK" if st.is_my_turn() else ""
                    print(f"{lg.name}   pick {rnd}.{sl:02d} "
                          f"(overall {st.on_the_clock_overall}){mine}")
                    print(f"your next: {st.next_pick()} "
                          f"({st.picks_until_mine()} away)   needs: {info['needs']}\n")
                    print(render.table(
                        [[i, r["name"], r["pos"], r["team"], r["vor"], f"T{r['tier']}",
                          "NEED" if r["need"] else ""] for i, r in enumerate(recs, 1)],
                        ["#", "player", "pos", "tm", "VOR", "tier", ""]))
                    print(f"\nupdated {time.strftime('%H:%M:%S')} "
                          f"({time.time()-t0:.1f}s)")
            except Exception as e:  # noqa: BLE001 - never die on the clock
                print(f"  [transient] {e}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nbye")


def main(argv=None):
    # Global flags live on a parent parser so they work either before or after
    # the subcommand ("sleeper --offline board" and "sleeper board --offline").
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true")
    common.add_argument("--offline", action="store_true", help="cache only, never fetch")
    common.add_argument("--refresh", action="store_true")
    common.add_argument("--season")

    ap = argparse.ArgumentParser(prog="sleeper", description=__doc__, parents=[common])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("leagues", parents=[common])
    sub.add_parser("env", parents=[common])
    s = sub.add_parser("show", parents=[common]); s.add_argument("league", nargs="?")
    s = sub.add_parser("refresh", parents=[common])
    s.add_argument("what", nargs="?", choices=["players", "projections", "all"])
    s = sub.add_parser("player", parents=[common])
    s.add_argument("name"); s.add_argument("--league")
    s = sub.add_parser("board", parents=[common])
    s.add_argument("league", nargs="?"); s.add_argument("--pos")
    s.add_argument("--top", type=int, default=40)
    s = sub.add_parser("draft", parents=[common])
    s.add_argument("sub", choices=["prep", "status", "advise"])
    s.add_argument("league", nargs="?"); s.add_argument("--slot", type=int)
    s.add_argument("--top", type=int, default=8)
    s = sub.add_parser("live", parents=[common])
    s.add_argument("league", nargs="?"); s.add_argument("--slot", type=int)
    s.add_argument("--top", type=int, default=10)
    s.add_argument("--interval", type=float, default=4.0)

    args = ap.parse_args(argv)
    cfg = config.load()
    fn = {"leagues": cmd_leagues, "env": cmd_env,
          "show": cmd_league_show, "refresh": cmd_refresh,
          "player": cmd_player, "board": cmd_board, "draft": cmd_draft,
          "live": cmd_live}[args.cmd]
    out = fn(args, cfg)
    if args.json and out is not None:
        print(jsonlib.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
