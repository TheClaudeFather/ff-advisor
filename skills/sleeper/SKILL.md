---
name: sleeper
description: Use when the user asks about fantasy football, their Sleeper leagues, draft picks, who to draft, start/sit decisions, lineup choices, waiver wire pickups, free agents, or who to drop. Works with any Sleeper league the user configures.
---

# Sleeper fantasy football advisor

## HARD CONSTRAINT, read first

ADVISE ONLY. This tool never writes to Sleeper. There is no public write API.

- Never claim that a pick, lineup change, waiver claim, or drop was submitted.
- Never use browser automation to act on Sleeper.
- Always phrase output as a recommendation that the user then executes.

## Invocation

Run the launcher in this skill directory. It works from any working directory:

```
<skill-dir>/bin/sleeper <command>
```

`<skill-dir>` is the base directory printed when this skill loads. Add `--json`
to any command when you want to compute over the result instead of reading it.

## Setup

Run `sleeper env` first. It prints the .env file in use and the configured
leagues. If the username is unset, the user must add `SLEEPER_USERNAME` to that
file. See `.env.example` at the plugin root for every key.

After the username is set, run `sleeper leagues`. It discovers the user's
leagues for the current season, assigns a short alias to each one, and saves the
aliases back to the .env file. Nothing personal is stored in the plugin itself.

If a draft slot is known before the draft, store it as `SLEEPER_SLOTS=<alias>:<n>`.
Sleeper does not publish `draft_order` until the draft starts, and a wrong slot
silently breaks all pick math.

## Personal notes

`sleeper env` prints a notes path, which defaults to `$SLEEPER_HOME/notes.md`.
If that file exists, read it before advising. It holds the user's own
league-specific notes, such as league culture, keeper rules, or a planned
strategy. This file lives outside the plugin and is never published.

## Command routing

| The user asks | Run |
|---|---|
| who should I draft, or I am on the clock | `draft advise <league> --wait 90` |
| show me the board, or best available | `board <league> --top 40 [--pos RB]` |
| what is the draft status | `draft status <league>` |
| how good is a player in my league | `player "<name>" --league <league>` |
| what are my league settings | `show <league>` |
| before a draft, once | `draft prep <league> [--slot N]` |
| which leagues am I in | `leagues` (alias, name, and shape of each) |
| who do I start, or should I bench X | `lineup <league> [--week N]` |
| who should I pick up | `waivers <league> [--top 10] [--pos RB]` |
| who should I drop | `drops <league>` |
| am I getting cut this week | `survival <league>` (elimination leagues only) |
| what should I do this week | `digest <league>` (all of the above, one report) |
| what is coming up, byes, injuries | `byes <league> [--weeks 4]` |

## Naming a league

Every `<league>` argument accepts the user's own words, not only an alias. Pass
through what they said, in quotes: `board "my 10-team league"`,
`draft advise "the superflex one"`, `show guillotine`. The tool matches on the
alias, the league name, the team count, the format (SUPER_FLEX, 2QB, 1QB), and
the scoring, and it reads the cache only, so this costs nothing.

If more than one league fits, the tool exits with the candidates and a short
description of each. Show those to the user and ask which one. Never guess, and
never carry a number from one league into another, because values differ
enormously between formats. A quarterback is around rank 11 by VOR in a
one-quarterback league and rank 1 in a SUPER_FLEX league.

If the user names no league at all, the default from `SLEEPER_DEFAULT_LEAGUE` is
used. Run `sleeper leagues` to see every league with its shape.

## In-season protocol

`lineup` compares the lineup the user has set against the best one their roster
can field, and names each change by slot. Read it before answering any start or
sit question, and never invent a player who is not in the output.

Three things to say out loud when they appear:

- A `NO_PROJ` warning means Sleeper published no projection for that player
  this week. That usually means a bye, but it can also mean the feed is late.
  Never present it as a zero.
- An `UNKNOWN_PLAYER` warning means the player database is stale. Tell the user
  to run `refresh players`.
- An `unfilled` slot means no player on the roster can fill it, so they must
  add someone.

`waivers` and `drops` default to the rest-of-season horizon, because a single
week is too noisy to justify a roster move. Pass `--horizon week` when the
question really is about this Sunday. The `adds` column is what a player would
add to the user's own starting lineup, not his raw points, so a good player at
a position they are already full at correctly shows zero. When every candidate
shows zero, the command lists the best free agent at each position instead,
which is the honest answer to "who should I pick up" when nobody helps.

`digest` is the weekly routine in one command and is the right first call on a
Tuesday or a Sunday morning. It also writes a snapshot of what was projected
for every rostered player, which is what makes grading the projections possible
later, so prefer it over running the commands separately.

`byes` looks ahead and reports two different problems. A slot listed under
"nobody eligible" has no player on the roster who can fill it, so one must be
added. A slot listed under "slot filled by a bye" is worse in practice: it looks
filled and scores zero, because the only eligible player is not playing that
week. Byes are derived rather than read, because Sleeper publishes no usable
bye week field, so a team is treated as on bye when its whole roster projects
under a point that week.

`survival` ranks every team in an elimination league by projected points and
reports the distance to the cut line. It is a margin, not odds: Sleeper
publishes no distribution of weekly scores, so never call it a probability.
Say the caveat it prints, which is that maximizing expected points is the right
goal while comfortable and the wrong one when on the line, where variance helps
and this tool does not model it. The command only runs for leagues named in
`SLEEPER_ELIMINATION`.

Before you recommend adding or starting anyone, search the web for news on that
player. Projections lag injuries, suspensions, and depth chart changes by days.

## Draft-day protocol

1. Run `draft prep <league>` before the draft. It warms every cache and writes a
   frozen fallback board. Live commands must never trigger a cold 14MB fetch.
2. Tell the user to open a second terminal running `sleeper live <league>`. That
   panel is their safety net and works even if this session is slow. Never run
   `live` yourself, because it blocks forever.
3. When the user says they are on the clock, run
   `draft advise <league> --wait 90 --after <their last pick number> --json`.
   Pass `--after` whenever they have already made a pick, because Sleeper takes
   seconds to publish it and the board still shows that pick on the clock until
   it does. The `--wait` flag polls until the
   board says it is actually their turn, which matters: advising while the pick
   before theirs is still running recommends players who are about to be taken,
   and that happened live. Then answer in under 20 seconds with one pick, one
   alternative, and one sentence of why. Write no essays on a 60-second clock.
   If the output carries the "still not your turn" warning, say so, because the
   board is then that many picks ahead of what they see.
4. Before you finalize any pick, search the web for breaking injury news about
   the top candidate. Projections lag real events. Report anything that
   overrides the math. If there is nothing, stay quiet and go with the numbers.

## Reading the numbers

- `pts` is projected points in that league's own scoring, computed from raw stat
  components. This is the edge over the Sleeper interface, which shows generic
  PPR points only.
- `VOR` is value over replacement, where replacement comes from
  `roster_positions × n_teams`. This is the real signal for draft decisions.
- `tier` marks a drop-off in value within a position. A tier cliff is often a
  better reason to pick than a small VOR edge.
- `ADP` is national average draft position. It is a weak prior in a small
  friends league. If ADP and rank disagree strongly, mention it to the user
  instead of trusting it.
- `surv%` is the crude logistic odds that the player lasts to the user's next
  pick. It is labelled crude because it is.
- `NEED` means the player fills an empty starting slot.

The first row is not automatically the answer. Weigh tier cliffs, positional
need, bye stacking, `injury_status`, and whether the position is flagged as low
confidence.

## Guardrails

- Every command prints a staleness banner first, such as `players 3h · proj 5h`.
  If the player data is older than 24h, run `refresh players` before you advise.
- Kicker and defense values are low confidence. Their scoring uses tiered
  points-allowed bands and field goal distance bands, which cannot be computed
  from mean projections. Say "take any K or DEF in the last two rounds" instead
  of defending a specific ranking.
- Threshold bonuses, such as `bonus_rec_yd_100`, first downs, and IDP scoring,
  are excluded on purpose. Multiplying a mean by a threshold bonus is wrong.
  Position premiums are different and ARE scored: `bonus_rec_te` in a tight end
  premium league is paid on every reception, so it is worth 0.5 times a tight
  end's projected catches. Say so when a league has one, because it moves tight
  ends a long way up the board.
  `show <league>` lists exactly what cannot be computed. Leagues with many such
  bonuses have understated point totals, so say so when you advise there.
- If a player shows `NO_PROJ`, say so. Never present a silent zero.
- Never name a player or a point total that is not in the command output.
- If a command fails, report stderr word for word. Do not guess.
- If `draft_order` is null before a draft, `--slot N` is required for pick math.
- In an elimination format, such as a guillotine league, point estimates stay
  valid but steady-state strategy claims do not. Advise on points and scarcity.

## How the recommendation is built

`references/methodology.md` explains the valuation, the roster-aware score, and
the simulation results behind them. Read it when the user asks why a
recommendation looks odd, or when you need to defend a number.
