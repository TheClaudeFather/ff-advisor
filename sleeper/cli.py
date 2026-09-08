"""sleeper - multi-league fantasy football advisor. ADVISE ONLY: never writes."""
from __future__ import annotations

import argparse
import json as jsonlib
import sys
import time

from . import (api, cache, config, draft as draft_mod, env,
               league as league_mod, match, players, projections, render,
               scoring, season)
from .advice import digest as digest_mod
from .advice import accuracy, inseason, lineup_advice, planner, survival, wire
from .advice import board as board_mod
from .advice import draft_advice


def _lg(args, cfg):
    lid = config.resolve_league(cfg, getattr(args, "league", None))
    # --refresh has to reach here: rosters are cached for an hour, which
    # in-season is the difference between advising on a player you still have
    # and one you dropped this morning.
    return league_mod.load(lid, user_id=cfg.get("user_id"),
                           offline=args.offline,
                           refresh=getattr(args, "refresh", False))


def _slot(args, cfg):
    """Draft slot from --slot, else the value stored in config for this league.

    Storing it removes a draft-day failure mode: Sleeper may not publish
    draft_order until the draft starts, and a wrong slot silently breaks all
    pick math.
    """
    if getattr(args, "slot", None):
        return args.slot
    alias = config.resolve_alias(cfg, getattr(args, "league", None))
    return (cfg.get("slots") or {}).get(alias)


def league_rows(leagues, cfg):
    """(rows, aliases) for a list of league objects from the API.

    Each row carries a description of the league's shape, so that a person can
    name a league by what it is rather than by a generated alias.
    """
    rows, aliases = [], dict(cfg.get("aliases") or {})
    slots = cfg.get("slots") or {}
    known = {str(lid): a for a, lid in aliases.items()}
    for l in leagues:
        # An existing alias wins. Generating a second one for a league that is
        # already aliased made every phrase match two aliases of one league.
        alias = known.get(str(l["league_id"])) or \
            "".join(c for c in l["name"].lower() if c.isalnum())[:12]
        aliases[alias] = l["league_id"]
        desc = match.describe(l, alias, slot=slots.get(alias))
        rows.append({"alias": alias, "name": l["name"], "summary": desc["summary"],
                     "status": l.get("status"), "slot": desc["slot"],
                     "league_id": l["league_id"]})
    return rows, aliases


def cmd_leagues(args, cfg):
    username = config.require_username(cfg)
    if not cfg.get("user_id"):
        cfg["user_id"] = api.user(username)["user_id"]
    season = args.season or api.state()["season"]
    cfg["season"] = season
    ls = api.leagues(cfg["user_id"], season, refresh=args.refresh)
    rows, aliases = league_rows(ls, cfg)
    cfg["aliases"] = aliases
    if not cfg.get("default_league") and rows:
        cfg["default_league"] = rows[0]["alias"]
    config.save(cfg)
    if args.json:
        return rows
    print(render.banner())
    print(render.table(
        [[r["alias"], r["name"], r["summary"], r["status"], r["league_id"]]
         for r in rows],
        ["alias", "name", "shape", "status", "league_id"]))
    print(f"\ndefault league: {cfg['default_league']}  (saved to {config.path()})")
    print("Name a league by any of it: alias, name, team count, or format.")


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
    shapes = {d["alias"]: d["summary"] for d in match.load_descriptors(cfg)}
    for alias, lid in sorted(aliases.items()):
        slot = f"   slot {slots[alias]}" if alias in slots else ""
        shape = shapes.get(alias, "(not cached yet)")
        print(f"  {alias:<14} {shape}{slot}")
        print(f"  {'':<14} {lid}")


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


def _roster(args, cfg, lg):
    """The team being advised on, or a clear exit explaining why not."""
    roster_id = getattr(args, "roster_id", None) or lg.my_roster_id
    if roster_id is None:
        raise SystemExit(
            f"I do not know which team is yours in {lg.name}.\n"
            "  Run: sleeper leagues   (it stores your user id)\n"
            "  or pass --roster-id N")
    roster = league_mod.roster_of(lg.league_id, roster_id,
                                  offline=args.offline, refresh=args.refresh)
    if roster is None:
        raise SystemExit(f"no roster {roster_id} in {lg.name}")
    return roster


def _weeks(args, cfg):
    """(advice week, live week). They differ on the days that matter."""
    try:
        state = api.state(offline=args.offline)
    except Exception:  # noqa: BLE001
        state = {}
    return (season.resolve_week(state, getattr(args, "week", None)),
            season.live_week(state))


def cmd_lineup(args, cfg):
    lg = _lg(args, cfg)
    roster = _roster(args, cfg, lg)
    week, live = _weeks(args, cfg)
    db = players.load(offline=args.offline)
    pos_of = {p: d.get("position") for p, d in db.items()}
    try:
        pts, opp = projections.points(lg, f"week:{week}", current_week=live,
                                      offline=args.offline)
    except RuntimeError as e:
        raise SystemExit(f"{e}\n  Run: sleeper refresh projections")

    out = lineup_advice.advise(lg, roster, pts, pos_of, db, week=week)
    if args.json:
        return out

    name = out["names"].get
    print(render.banner())
    print(f"{lg.name}  |  week {week}  |  "
          f"projected {out['optimal_total']}  "
          f"(now {out['current_total']}, {out['gain']:+} available)\n")
    joining = {s["in"] for s in out["swaps"]}
    print(render.table(
        [[slot, name(pid, pid), (db.get(pid) or {}).get("position", ""),
          (db.get(pid) or {}).get("team", ""), opp.get(pid, "") or "",
          round(value, 1), "START" if pid in joining else "",
          (db.get(pid) or {}).get("injury_status") or ""]
         for slot, pid, value in out["optimal"]["starters"]],
        ["slot", "player", "pos", "tm", "opp", "pts", "", "inj"]))

    if out["swaps"]:
        print("\nchanges:")
        for s in out["swaps"]:
            leaving = f"OUT {name(s['out'], s['out'])}" if s["out"] else "empty slot"
            print(f"  {s['slot']:<11} {leaving:<28} "
                  f"IN {name(s['in'], s['in'])}  {s['gain']:+}")
    else:
        print("\nno changes: this is already the best lineup available.")

    if out["optimal"]["unfilled"]:
        print(f"\n! no eligible player for: {', '.join(out['optimal']['unfilled'])}")
    for w in out["warnings"]:
        print(f"! {w['code']} {name(w['player_id'], w['player_id'])}: {w['note']}")


def _inseason(args, cfg, *, default_horizon):
    """Everything the in-season commands share: team, week, points, wire."""
    lg = _lg(args, cfg)
    roster = _roster(args, cfg, lg)
    week, live = _weeks(args, cfg)
    horizon = getattr(args, "horizon", None) or default_horizon
    if horizon == "week":
        horizon = f"week:{week}"
    db = players.load(offline=args.offline)
    pos_of = {p: d.get("position") for p, d in db.items()}
    try:
        pts, opp = projections.points(lg, horizon, current_week=live,
                                      offline=args.offline)
    except RuntimeError as e:
        raise SystemExit(f"{e}\n  Run: sleeper refresh projections")
    rostered = league_mod.rostered_players(lg.league_id, offline=args.offline,
                                           refresh=args.refresh)
    free = {p for p in pts if p not in rostered and pos_of.get(p)}
    return lg, roster, week, horizon, db, pos_of, pts, opp, free


def cmd_waivers(args, cfg):
    lg, roster, week, horizon, db, pos_of, pts, _opp, free = _inseason(
        args, cfg, default_horizon="ros")
    rows = wire.waiver_targets(lg, roster, pts, pos_of, free, top=args.top)
    if args.pos:
        rows = [r for r in rows if r["pos"] == args.pos.upper()]
    name = lambda pid: (db.get(pid) or {}).get("name", pid)  # noqa: E731

    if args.json:
        return {"league": lg.name, "week": week, "horizon": horizon,
                "targets": [{**r, "name": name(r["player_id"]),
                             "drop_name": (name(r["drop"]["player_id"])
                                           if r["drop"]["player_id"] else None)}
                            for r in rows]}
    print(render.banner())
    print(f"{lg.name}  |  week {week}  |  horizon {horizon}  |  "
          f"{len(free)} free agents\n")
    if not rows:
        print("nobody on the wire is projected to score in this league.")
        return
    if all(r["marginal"] == 0.0 for r in rows):
        print("nobody on the wire improves your starting lineup. The best")
        print("available at each position, in case of an injury:\n")
        best = inseason.best_available(pts, pos_of, free)
        print(render.table(
            [[pos, name(pid), round(value, 1)]
             for pos, (pid, value) in sorted(best.items())],
            ["pos", "best free agent", "pts"]))
        return
    print(render.table(
        [[i, name(r["player_id"]), r["pos"],
          (db.get(r["player_id"]) or {}).get("team", ""), r["pts"],
          f"{r['marginal']:+}", f"{r['over_wire']:+}",
          name(r["drop"]["player_id"]) if r["drop"]["player_id"] else "-",
          f"{r['net']:+}",
          (db.get(r["player_id"]) or {}).get("injury_status") or ""]
         for i, r in enumerate(rows, 1)],
        ["#", "player", "pos", "tm", "pts", "adds", "vs wire", "drop", "net",
         "inj"]))
    print("\nadds = what he would add to your best lineup. vs wire = how far")
    print("he is above the best free agent at his position. net = adds - drop.")


def cmd_drops(args, cfg):
    lg, roster, week, horizon, db, pos_of, pts, _opp, free = _inseason(
        args, cfg, default_horizon="ros")
    rows = wire.drop_ranking(lg, roster, pts, pos_of, free)[: args.top]
    name = lambda pid: (db.get(pid) or {}).get("name", pid)  # noqa: E731

    if args.json:
        return {"league": lg.name, "week": week, "horizon": horizon,
                "candidates": [{**r, "name": name(r["player_id"])}
                               for r in rows]}
    print(render.banner())
    print(f"{lg.name}  |  week {week}  |  horizon {horizon}  |  "
          f"safest to drop first\n")
    print(render.table(
        [[i, name(r["player_id"]), r["pos"],
          (db.get(r["player_id"]) or {}).get("team", ""), r["pts"], r["cost"],
          f"{r['vs_wire']:+}",
          "BREAKS LINEUP" if r["breaks_lineup"] else
          ("starter" if r["starting"] else ("IR" if r["reserve"] else "safe")),
          (db.get(r["player_id"]) or {}).get("injury_status") or ""]
         for i, r in enumerate(rows, 1)],
        ["#", "player", "pos", "tm", "pts", "costs", "vs wire", "note", "inj"]))
    print("\ncosts = points your best lineup loses without him. vs wire = how")
    print("far he is above the best free agent at his position.")


def cmd_survival(args, cfg):
    lg = _lg(args, cfg)
    alias = config.resolve_alias(cfg, args.league)
    elimination = config.elimination_leagues()
    if alias not in elimination and not args.force:
        raise SystemExit(
            f"{lg.name} is not marked as an elimination league.\n"
            f"  Add SLEEPER_ELIMINATION={alias} to {config.path()}\n"
            "  or pass --force to see the table anyway.")

    week, live = _weeks(args, cfg)
    db = players.load(offline=args.offline)
    pos_of = {p: d.get("position") for p, d in db.items()}
    try:
        pts, _opp = projections.points(lg, f"week:{week}", current_week=live,
                                       offline=args.offline)
    except RuntimeError as e:
        raise SystemExit(f"{e}\n  Run: sleeper refresh projections")

    rosters = league_mod.all_rosters(lg.league_id, offline=args.offline,
                                     refresh=args.refresh)
    teams = [survival.project_team(lg, r, pts, pos_of) for r in rosters]
    out = survival.cut_margin(teams, lg.my_roster_id, cut=args.cut)

    names = {}
    try:
        for u in api.league_users(lg.league_id, offline=args.offline):
            names[str(u.get("user_id"))] = (u.get("display_name")
                                            or u.get("username") or "")
    except Exception:  # noqa: BLE001 - names are a nicety, not the answer
        pass

    def team_name(t):
        return names.get(str(t["owner_id"]), f"roster {t['roster_id']}")

    if args.json:
        return {"league": lg.name, "week": week, "teams": len(teams),
                "cut": out["cut"], "my_rank": out["my_rank"],
                "margin": out["margin"], "at_risk": out["at_risk"],
                "ranked": [{**t, "name": team_name(t)} for t in out["ranked"]]}

    print(render.banner())
    cut_note = f"{args.cut} team is cut" if args.cut == 1 else f"{args.cut} teams are cut"
    print(f"{lg.name}  |  week {week}  |  {len(teams)} teams  |  {cut_note}\n")
    print(render.table(
        [[i, "YOU" if t["roster_id"] == lg.my_roster_id else team_name(t),
          round(t["projected"], 1), t["rule"],
          f"{t['bench_left']:+}" if t["bench_left"] else "",
          "CUT" if t["roster_id"] in out["cut"] else ""]
         for i, t in enumerate(out["ranked"], 1)],
        ["#", "team", "proj", "from", "on bench", ""]))

    if out["my_rank"] is None:
        print("\n! I do not know which team is yours, so there is no margin.")
    elif out["at_risk"]:
        print(f"\nyou are projected to be cut, {out['gap_to_safety']} points "
              "below safety.")
    else:
        print(f"\nyou are {out['margin']} points above the cut line.")
    print("! this is a projection, not odds. Expected points is the right goal")
    print("  while you are comfortable; on the line you want variance, which")
    print("  this does not model.")


def cmd_digest(args, cfg):
    """The weekly routine: lineup, adds, drops, and the cut line."""
    lg = _lg(args, cfg)
    roster = _roster(args, cfg, lg)
    alias = config.resolve_alias(cfg, args.league)
    elimination = alias in config.elimination_leagues()
    week, live = _weeks(args, cfg)
    db = players.load(offline=args.offline)
    pos_of = {p: d.get("position") for p, d in db.items()}
    try:
        week_pts, opp = projections.points(lg, f"week:{week}", current_week=live,
                                           offline=args.offline)
        ros_pts, _ = projections.points(lg, "ros", current_week=live,
                                        offline=args.offline)
    except RuntimeError as e:
        raise SystemExit(f"{e}\n  Run: sleeper refresh projections")

    rostered = league_mod.rostered_players(lg.league_id, offline=args.offline,
                                           refresh=args.refresh)
    free = {p for p in ros_pts if p not in rostered and pos_of.get(p)}
    rosters = (league_mod.all_rosters(lg.league_id, offline=args.offline,
                                      refresh=args.refresh)
               if elimination else None)

    out = digest_mod.build(lg, roster, week=week, week_pts=week_pts,
                           ros_pts=ros_pts, pos_of=pos_of, db=db,
                           free_ids=free, rosters=rosters,
                           elimination=elimination, cut=args.cut, top=args.top)

    if not args.no_snapshot:
        out["snapshot"] = str(digest_mod.snapshot(
            env.home(), lg.league_id, week,
            {p: week_pts.get(p, 0.0) for p in rostered},
            set_ids=[p for _slot, p in league_mod.current_starters(lg, roster)
                     if p],
            recommended_ids=[pid for _slot, pid, _v
                             in out["lineup"]["optimal"]["starters"]]))

    if args.json:
        return out

    name = lambda pid: (db.get(pid) or {}).get("name", pid)  # noqa: E731
    ln = out["lineup"]
    print(render.banner())
    print(f"{lg.name}  |  week {week}\n")

    print(f"LINEUP   projected {ln['optimal_total']}  "
          f"(now {ln['current_total']}, {ln['gain']:+} available)")
    if ln["swaps"]:
        for sw in ln["swaps"]:
            leaving = f"OUT {name(sw['out'])}" if sw["out"] else "empty slot"
            print(f"  {sw['slot']:<11} {leaving:<26} IN {name(sw['in'])}  "
                  f"{sw['gain']:+}")
    else:
        print("  no changes: this is already the best lineup available.")
    if ln["optimal"]["unfilled"]:
        print(f"  ! no eligible player for: {', '.join(ln['optimal']['unfilled'])}")

    print("\nADDS     rest of season, by what they add to your lineup")
    if all(t["marginal"] == 0.0 for t in out["waivers"]):
        print("  nobody on the wire improves your starting lineup.")
    else:
        for t in out["waivers"]:
            if t["marginal"] > 0:
                print(f"  {name(t['player_id'])[:24]:<24} {t['pos']:<4} "
                      f"adds {t['marginal']:+}   drop {name(t['drop']['player_id'])}")

    print("\nDROPS    safest first")
    for d in out["drops"]:
        note = ("BREAKS LINEUP" if d["breaks_lineup"] else
                ("starter" if d["starting"] else "safe"))
        print(f"  {name(d['player_id'])[:24]:<24} {d['pos']:<4} "
              f"costs {d['cost']:<6} {note}")

    if out["survival"]:
        sv = out["survival"]
        where = (f"projected to be cut, {sv['gap_to_safety']} below safety"
                 if sv["at_risk"] else
                 f"{sv['margin']} points above the cut line")
        print(f"\nCUT LINE rank {sv['my_rank']} of {len(sv['ranked'])}, {where}")

    for w in ln["warnings"]:
        print(f"! {w['code']} {name(w['player_id'])}: {w['note']}")


def cmd_byes(args, cfg):
    """The weeks ahead where a starting slot has nobody who plays."""
    lg = _lg(args, cfg)
    roster = _roster(args, cfg, lg)
    week, live = _weeks(args, cfg)
    db = players.load(offline=args.offline)
    pos_of = {p: d.get("position") for p, d in db.items()}
    team_of = {p: d.get("team") for p, d in db.items()}

    byes = planner.bye_weeks(api.schedule(lg.season, offline=args.offline))
    weekly = {}
    last = min(season.LAST_WEEK, week + args.weeks - 1)
    for wk in range(week, last + 1):
        try:
            pts, _opp = projections.points(lg, f"week:{wk}", current_week=live,
                                           offline=args.offline)
        except RuntimeError:
            continue  # that week is not published or not cached
        weekly[wk] = pts

    if not weekly:
        raise SystemExit("no weekly projections available for those weeks.")

    rows = planner.outlook(lg, roster, weekly, pos_of, byes, team_of)
    name = lambda pid: (db.get(pid) or {}).get("name", pid)  # noqa: E731

    if args.json:
        return {"league": lg.name, "from_week": week,
                "weeks": [{**r, "on_bye_names": [name(p) for p in r["on_bye"]]}
                          for r in rows]}

    print(render.banner())
    print(f"{lg.name}  |  weeks {min(weekly)} to {max(weekly)}\n")
    print(render.table(
        [[r["week"], r["total"],
          ", ".join(f"{slot}: {name(pid)}" for slot, pid in r["hollow"]) or "",
          ", ".join(r["unfilled"]) or "",
          ", ".join(name(p) for p in r["on_bye"]) or ""]
         for r in rows],
        ["week", "proj", "slot filled by a bye", "nobody eligible", "on bye"]))

    hurt = [p for p in roster.players
            if (db.get(p) or {}).get("injury_status")]
    if hurt:
        print("\ninjuries on this roster:")
        for pid in hurt:
            print(f"  {name(pid):<24} {(db.get(pid) or {}).get('injury_status')}")
    print("\nA slot filled by a bye scores zero. Cover it before the week it")
    print("lands, not during it.")


def _grade_week(lg, week, pos_of, *, offline=False):
    """One week graded, or None when there is no snapshot of it."""
    path = env.home() / "snapshots" / f"{lg.league_id}_week{week}.json"
    if not path.exists():
        return None
    saved = jsonlib.loads(path.read_text())
    records = api.stats_week(lg.season, week, offline=offline)

    actual = {}
    for r in records:
        pid = r.get("player_id")
        pos = (r.get("player") or {}).get("position") or pos_of.get(pid)
        if pid and pos:
            actual[pid] = scoring.score_player(r.get("stats") or {},
                                               lg.scoring, pos)
    return accuracy.grade(saved["points"], actual, pos_of, week=week,
                          set_ids=saved.get("set"),
                          recommended_ids=saved.get("recommended"))


def cmd_accuracy(args, cfg):
    """Grade a week against what happened, or the record so far."""
    lg = _lg(args, cfg)
    _advice_week, live = _weeks(args, cfg)
    db = players.load(offline=args.offline)
    pos_of = {p: d.get("position") for p, d in db.items()}

    if args.through:
        weeks = []
        for wk in range(1, args.through + 1):
            try:
                graded = _grade_week(lg, wk, pos_of, offline=args.offline)
            except RuntimeError:
                continue
            if graded:
                weeks.append(graded)
        record = accuracy.combine(weeks)
        if args.json:
            return {"league": lg.name, **record}
        print(render.banner())
        covered = ", ".join(str(w) for w in record["weeks"]) or "none"
        print(f"{lg.name}  |  weeks graded: {covered}\n")
        if not record["weeks"]:
            print("no played week has a snapshot yet. `sleeper digest` writes")
            print("one before kickoff; without it a week cannot be graded.")
            return
        o = record["overall"]
        print(f"  average miss {o['mae']}   bias {o['bias']:+}   "
              f"{o['n']} player weeks\n")
        print(render.table(
            [[pos, v["n"], v["mae"], f"{v['bias']:+}"]
             for pos, v in record["by_pos"].items()],
            ["pos", "n", "avg miss", "bias"]))
        d = record["decisions"]
        if d["weeks"]:
            print(f"\nadvice: helped {d['helped']} of {d['weeks']} weeks, "
                  f"{d['total_delta']:+} points in total")
        else:
            print("\nadvice: no week yet where a change was recommended.")
        print("\nA single week is noise. Read the record, and remember that a")
        print("lineup edge smaller than the average miss is inside the error.")
        return

    week = args.week or max(1, live - 1)   # default: the week just played
    try:
        out = _grade_week(lg, week, pos_of, offline=args.offline)
    except RuntimeError as e:
        raise SystemExit(str(e))
    if out is None:
        raise SystemExit(
            f"no snapshot of week {week} for {lg.name}.\n"
            "  Snapshots are written by `sleeper digest`, before the week is\n"
            "  played. Nothing else preserves what was projected at the time.")

    if args.json:
        return {"league": lg.name, **out, "worst": out["worst"][: args.top]}

    if not out["played"]:
        raise SystemExit(
            f"week {week} has not been played: every player scored zero.\n"
            "  Sleeper publishes a stats feed for a future week with all its\n"
            "  values at zero, so grading it would measure nothing.")

    def name(pid):
        return (db.get(pid) or {}).get("name", pid)

    print(render.banner())
    o = out["overall"]
    print(f"{lg.name}  |  week {week}  |  {o['n']} rostered players graded\n")
    ran = "projections ran high" if o["bias"] > 0 else "projections ran low"
    print(f"  average miss {o['mae']}   bias {o['bias']:+} ({ran})\n")
    print(render.table(
        [[pos, v["n"], v["mae"], f"{v['bias']:+}"]
         for pos, v in out["by_pos"].items()],
        ["pos", "n", "avg miss", "bias"]))
    print("\nbiggest misses:")
    for r in out["worst"][: args.top]:
        print(f"  {name(r['player_id'])[:24]:<24} {r['pos']:<4} "
              f"projected {r['projected']:>6}  actual {r['actual']:>6}  "
              f"{r['error']:+}")
    d = out.get("decision")
    if d and d["helped"] is not None:
        verdict = "helped" if d["helped"] else "cost you"
        print(f"\nadvice {verdict} {abs(d['delta'])} points: "
              f"you set {d['set']}, the recommended lineup scored "
              f"{d['recommended']}")
    elif d:
        print(f"\nadvice recommended no change; the lineup scored {d['set']}")

    if out["n_no_actual"]:
        print(f"\n! {out['n_no_actual']} players have no result in the stats "
              "feed and were graded as zero.")


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
    slot = _slot(args, cfg)
    if getattr(args, "wait", 0):
        st = draft_mod.wait_for_turn(
            lambda: draft_mod.load_state(lg.league_id, slot=slot),
            after=args.after, timeout=args.wait)
    else:
        st = draft_mod.load_state(lg.league_id, slot=slot)
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
    if getattr(args, "wait", 0) and not st.is_my_turn():
        print(f"! waited {args.wait:.0f}s and it is still not your turn. "
              f"This board is {st.picks_until_mine()} picks before yours.")
    mine = " <<< YOU ARE ON THE CLOCK" if st.is_my_turn() else ""
    print(f"pick {rnd}.{sl:02d} (overall {st.on_the_clock_overall}){mine}")
    if st.next_pick():
        print(f"your next: overall {st.next_pick()} "
              f"({st.picks_until_mine()} away)   then: {st.pick_after_next()}")
    print(f"have: {info['have']}   needs: {info['needs']}\n")
    print(render.table(
        [[i, r["name"], r["pos"], r["team"], r["pts"], r["vor"], f"T{r['tier']}",
          r["adp"] if r["adp"] is not None else "-", f"{r['surv']}%",
          "CAP" if r.get("capped") else ("NEED" if r["need"] else ""),
          r["injury"] or ""]
         for i, r in enumerate(recs, 1)],
        ["#", "player", "pos", "tm", "pts", "VOR", "tier", "ADP", "surv", "", "inj"]))
    if any(r.get("capped") for r in recs):
        print("CAP = your roster cannot start another one. Shown because he is "
              "worth more than the rest of the list, not because he is the pick.")
    print("\nsurv% = crude ADP-based odds he lasts to your next pick. ADP is")
    print("national and a weak prior in a small league. VOR is the real signal.")
    if info.get("superflex"):
        print("SUPER_FLEX: ADP comes from Sleeper's two-quarterback board, not")
        print("the one-quarterback one, so quarterbacks price much earlier here.")


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
    s = sub.add_parser("lineup", parents=[common])
    s.add_argument("league", nargs="?")
    s.add_argument("--week", type=int, help="default: the live week")
    s.add_argument("--roster-id", type=int, dest="roster_id")
    s = sub.add_parser("waivers", parents=[common])
    s.add_argument("league", nargs="?")
    s.add_argument("--week", type=int); s.add_argument("--top", type=int, default=10)
    s.add_argument("--pos"); s.add_argument("--horizon", choices=["ros", "week"])
    s.add_argument("--roster-id", type=int, dest="roster_id")
    s = sub.add_parser("drops", parents=[common])
    s.add_argument("league", nargs="?")
    s.add_argument("--week", type=int); s.add_argument("--top", type=int, default=8)
    s.add_argument("--horizon", choices=["ros", "week"])
    s.add_argument("--roster-id", type=int, dest="roster_id")
    s = sub.add_parser("survival", parents=[common])
    s.add_argument("league", nargs="?")
    s.add_argument("--week", type=int); s.add_argument("--cut", type=int, default=1)
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("digest", parents=[common])
    s.add_argument("league", nargs="?")
    s.add_argument("--week", type=int); s.add_argument("--top", type=int, default=5)
    s.add_argument("--cut", type=int, default=1)
    s.add_argument("--roster-id", type=int, dest="roster_id")
    s.add_argument("--no-snapshot", action="store_true")
    s = sub.add_parser("byes", parents=[common])
    s.add_argument("league", nargs="?")
    s.add_argument("--week", type=int); s.add_argument("--weeks", type=int, default=4)
    s.add_argument("--roster-id", type=int, dest="roster_id")
    s = sub.add_parser("accuracy", parents=[common])
    s.add_argument("league", nargs="?")
    s.add_argument("--week", type=int)
    s.add_argument("--through", type=int, metavar="WEEK",
                   help="grade every week up to this one, as a record")
    s.add_argument("--top", type=int, default=8)
    s = sub.add_parser("board", parents=[common])
    s.add_argument("league", nargs="?"); s.add_argument("--pos")
    s.add_argument("--top", type=int, default=40)
    s = sub.add_parser("draft", parents=[common])
    s.add_argument("sub", choices=["prep", "status", "advise"])
    s.add_argument("league", nargs="?"); s.add_argument("--slot", type=int)
    s.add_argument("--top", type=int, default=8)
    s.add_argument("--wait", type=float, default=0, metavar="SECONDS",
                   help="poll until it is our turn before advising")
    s.add_argument("--after", type=int, default=None, metavar="PICK",
                   help="overall number of the pick we just made, so --wait "
                        "does not fire on a board that has not published it")
    s = sub.add_parser("live", parents=[common])
    s.add_argument("league", nargs="?"); s.add_argument("--slot", type=int)
    s.add_argument("--top", type=int, default=10)
    s.add_argument("--interval", type=float, default=4.0)

    args = ap.parse_args(argv)
    cfg = config.load()
    fn = {"leagues": cmd_leagues, "env": cmd_env, "lineup": cmd_lineup,
          "waivers": cmd_waivers, "drops": cmd_drops, "survival": cmd_survival,
          "digest": cmd_digest, "byes": cmd_byes, "accuracy": cmd_accuracy,
          "show": cmd_league_show, "refresh": cmd_refresh,
          "player": cmd_player, "board": cmd_board, "draft": cmd_draft,
          "live": cmd_live}[args.cmd]
    out = fn(args, cfg)
    if args.json and out is not None:
        print(jsonlib.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
