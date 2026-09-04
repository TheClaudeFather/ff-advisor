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
| who should I draft, or I am on the clock | `draft advise <league> [--slot N]` |
| show me the board, or best available | `board <league> --top 40 [--pos RB]` |
| what is the draft status | `draft status <league>` |
| how good is a player in my league | `player "<name>" --league <league>` |
| what are my league settings | `show <league>` |
| before a draft, once | `draft prep <league> [--slot N]` |
| which leagues am I in | `leagues` |
| start/sit, waivers, drops | not built yet, say so plainly |

If the user has more than one league and does not name one, ask which league.
Values differ enormously between formats. A quarterback is around rank 11 by VOR
in a one-quarterback league and rank 1 in a SUPER_FLEX league. Never carry a
number from one league into another.

## Draft-day protocol

1. Run `draft prep <league>` before the draft. It warms every cache and writes a
   frozen fallback board. Live commands must never trigger a cold 14MB fetch.
2. Tell the user to open a second terminal running `sleeper live <league>`. That
   panel is their safety net and works even if this session is slow. Never run
   `live` yourself, because it blocks forever.
3. When the user is on the clock, run `draft advise <league> --json`, then answer
   in under 20 seconds with one pick, one alternative, and one sentence of why.
   Write no essays on a 120-second clock.
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
