# How the recommendation is built

## Points

Points come from each league's own scoring settings applied to raw projection
components, not from the generic PPR total that the Sleeper interface shows.
Threshold bonuses are excluded, because multiplying a projected mean by a
threshold bonus is wrong. `show <league>` lists every scoring key that cannot be
computed for that league.

## Value over replacement

VOR subtracts a replacement level derived from `roster_positions` times the
number of teams. Flex slots are allocated only to positions that can fill them.
An earlier version pooled every leftover player, took the top N by raw points,
then discarded those that were not flex eligible. Quarterbacks outscore other
positions in raw points, so they occupied 17 of 20 flex slots and were thrown
away, which left only 3 of 20 slots allocated and inflated the replacement level
for running backs and receivers.

## The draft score

The draft score is not raw VOR. It is the improvement a player makes to a
starting lineup whose empty slots hold the best player still gettable at a later
pick, plus bench value and pick urgency.

This matters because raw VOR does not know that a roster is already full at a
position. A fifth tight end still shows a high VOR even though only one can
start. A mock-draft rehearsal caught exactly that failure, where the tool
drafted five tight ends and no running backs.

Guards that follow from it:

- Kickers and defenses are gated to the last two rounds, one of each, never a
  backup.
- Backups are capped at what the roster can use, so there is no third
  quarterback in a one-quarterback league.
- Bench value decays for each extra player beyond what a position can start.
- Caps are penalties, not filters. A filter returned an empty recommendation at
  the end of a draft, when every remaining candidate exceeded a cap. Returning
  nothing while the pick clock runs is the worst failure this tool can have.

## The lookahead horizon

The "still gettable" horizon is ten of the user's own turns ahead. That value was
measured across seven draft slots in two league formats, not chosen. Looking one
pick ahead makes the tool conclude that every position can wait, and it concludes
that again next turn, until the position is gone. In a simulated 17-team draft
that cost about 105 projected lineup points, because two starting running back
slots ended up filled by replacement-tier players.

Measured means, higher is better:

```
17-team superflex: look 2 -> 2125.5,  needs-based -> 2156.7,  look 10 -> 2167.2
10-team PPR:       look 2 -> 2136.6,  needs-based -> 2156.0,  look 10 -> 2166.2
```

## Survival percentages

`surv%` is a crude logistic function of national ADP against the user's next
pick. In a SUPER_FLEX league, quarterback ADP is shifted earlier, because
Sleeper publishes one-quarterback ADP while quarterbacks go much sooner in that
format. Treat these numbers as direction, not probability.

## Verification

The advice path is verified across 30 simulated drafts, covering every slot and
three opponent behaviours. In all of them the tool produced a legal starting
lineup, never recommended a drafted player, and took at most 0.23s per
recommendation. A replay test runs 289 genuine picks from a completed draft
through the same state machine.
