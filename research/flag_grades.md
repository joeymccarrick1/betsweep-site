# Do the risk flags work? (first grade, 11/15)

Boards graded: the last build before Sunday kickoff in Weeks 8 and 9 (3,148 over legs, 430 player-weeks), plus FanDuel's graded legs
for Weeks 6-9 from the sheet (4,839 legs). "Diff" is hit rate minus the fair rate the price implied (implied / 1.045); each player
counts once a week.

## What held up
- **Floor legs cost money as a group.** Legs at -180 or shorter hit 63.8% against about 67.6% priced (1,289 legs, Weeks 6-9, t -2.4).
- **Near-zero rate.** Floor legs on players who had finished under half the line in a third or more of their games: 57.6%, 8.8 under
  the price, under in all four weeks (151 legs). Now a `bad` flag, "Near-zero risk".
- **"Cleared it 90%+" does not help**: those floor legs hit 7.6 under (123 legs).
- **Soft matchup** (shown as good): 8.7 under, both weeks, 136 player-weeks. Weight set to 0 in sweep.TAG_W.
- **Back from absence** (watch): 10.6 under, both weeks, 30 player-weeks. Already a watch.

## What did not
- **The risk score itself did not separate winners from losers in these two weeks.** Score 0: -3.3; score 1: -1.3; 2-3: -3.8; 4+: -1.3.
  Among floor legs, low-risk -4.1, high-risk +4.3 (t 1.3). None of it is statistically solid, but there is no sign yet that "low risk" legs
  beat their prices.
- **Good flags as a group**: more good flags did not mean better results (three or more: -4.6).
- **Losing zone**: one week graded (Week 9), +3.0 on 37 player-weeks. No evidence yet either way; the hard block stays on the owner's call.
- **Projection error as "reliability"**: players and teams whose projections landed closest hit 7-8 pts UNDER their prices. Not used.

## Leans (right direction, small samples)
- Price drift before kickoff, Week 9: drifted 3+ pts against the leg -6.4 (71 legs), shortened 3+ +7.1 (67 legs).
- Team-market record against prices, walk-forward Weeks 7-9: worst group -5.2 (254 player-weeks), best -1.9.
- Cold L3 (bad) +5.5 and Role Down (bad) positive: FanDuel appears to price a falling trend already.

Re-run on Tuesdays: `python3 flag_grade.py <boards folder> research/flag_grades_<weeks>.json`.
