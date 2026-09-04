# Sleeper Fantasy Advisor

A Claude Code plugin that gives fantasy football advice computed in your own
Sleeper league's scoring settings, which the Sleeper interface never shows,
because it displays generic PPR points only.

Read only. This tool never writes to Sleeper. There is no public write API, and
every command produces a recommendation that you execute yourself.

## Install

```
/plugin marketplace add TheClaudeFather/ff-advisor
/plugin install sleeper-fantasy-football-advisor@sleeper-fantasy-football-advisor
```

Then tell Claude your Sleeper username, or configure it by hand:

```
mkdir -p ~/.sleeper
echo "SLEEPER_USERNAME=your_sleeper_handle" >> ~/.sleeper/.env
sleeper leagues
```

`sleeper leagues` discovers your leagues for the current season, gives each one
a short alias, and writes those aliases back to the .env file.

Requirements: Python 3.11 or newer, and either the `requests` package or `curl`
on the path. No other dependency.

## Configuration

Every user-specific value lives in a .env file. Nothing personal is stored in
this repository. See `.env.example` for the full list of keys, and run
`sleeper env` to see which file is in use and what it resolved to.

| Key | Meaning |
|---|---|
| `SLEEPER_USERNAME` | your Sleeper handle, the only value you must set by hand |
| `SLEEPER_USER_ID` | filled in by `sleeper leagues` |
| `SLEEPER_SEASON` | season to use, default comes from Sleeper |
| `SLEEPER_LEAGUES` | `alias:league_id` pairs, comma separated |
| `SLEEPER_DEFAULT_LEAGUE` | alias used when you name no league |
| `SLEEPER_SLOTS` | `alias:slot` pairs, your draft position per league |
| `SLEEPER_HOME` | where the cache, .env, and notes live, default `~/.sleeper` |
| `SLEEPER_NOTES` | private league notes the skill reads, default `$SLEEPER_HOME/notes.md` |

## Usage

The plugin ships a launcher at `skills/sleeper/bin/sleeper`. From a checkout you
can also run `python3 -m sleeper.cli`.

```
sleeper env                             # resolved configuration
sleeper leagues                         # discover and alias your leagues
sleeper show <league>                   # settings and blind spots
sleeper board <league> --top 40         # ranked draft board
sleeper draft prep <league> --slot N     # run before the draft
sleeper draft advise <league> --slot N   # one shot, under 0.5s
sleeper live <league>                   # second terminal panel
```

Global flags: `--json`, `--offline`, `--refresh`, `--season`.

## Why league-specific scoring matters

The Sleeper projection feed carries raw stat components, such as `rush_yd`,
`rec`, and `pass_td`. Each league exposes its own `scoring_settings` with
matching keys. Scoring the components against a specific league reproduces
Sleeper's own number exactly for a standard PPR league, and correctly diverges
for anything else.

The same quarterback, with the same projection, in two leagues:

| League | VOR |
|---|---|
| 10-team, one quarterback, full PPR | 64.96 |
| 17-team SUPER_FLEX | 259.44 |

## Design

- `api.py` is the only module that knows a URL, which is what makes `advice/*`
  pure functions over data and therefore testable offline.
- `scoring.score_line` and `valuation.replacement_points` are the two
  primitives. Draft VOR, start/sit, waivers, and drops are the same math at
  different projection horizons.
- Replacement level is derived from `roster_positions × n_teams`, with no
  hardcoded "RB24", so SUPER_FLEX and 17-team leagues work with no special case.
- `lineup.marginal_value`, which is how much an addition improves the optimal
  lineup, is the primitive for later waiver and drop advice.
- `skills/sleeper/references/methodology.md` explains the roster-aware draft
  score and the simulations behind it.

## Known limits

- Threshold bonuses, such as `bonus_rec_yd_100`, first downs, and IDP scoring,
  are excluded. Multiplying a projected mean by a threshold bonus is wrong.
  `show` lists exactly which keys are affected.
- Kicker and defense values are low confidence, because their scoring cannot be
  computed from mean projections.
- ADP is national and a weak prior in a small friends league.
- Projection quality is the ceiling. This is a scarcity and roster-need engine,
  not an oracle.
- Start/sit, waiver, and drop advice is not built yet.

## Tests

```
python3 -m pytest tests/ -q
```

The suite includes a replay of a real completed 289-pick draft, anonymized,
which asserts that the snake math reproduces the actual pick order.

## License

MIT
