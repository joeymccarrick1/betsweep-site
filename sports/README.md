# BetSweep beyond the NFL: groundwork for NBA, Premier League and college football

Started 2026-11-15 on the owner's word: "start laying the groundwork for adding college football, nba, and soccer (EPL first and then we
can move on to other divisions). Use the same idea for projections and base line that we've created to NFL." and "Don't change anything
for the betsweep site right now."

**This folder is not part of the site.** It lives on the `multisport` branch. The site build reads `main` and `gen-overrides` only, and no
workflow runs on a push, so nothing here can reach betsweep.co until it is merged on purpose.

## The NFL method, as it actually runs

Read from the sheet's `AUTO - Settings`, the projection tabs and `how_body.html`:

1. **Baseline.** A player's own season average, a weight on his recent games (`Last-4 weight`), and an early-season pull toward a prior
   (TD regression, efficiency confidence). It began as the offense-average / defense-allowed grid on the QBs / RBs / WRs / TEs tabs.
2. **Role and who is out.** Depth roles, availability overrides, and vacated targets and carries shared out among the players who are
   active (`Team Vacated Targets`, `RB Missing-Starter Carry Transfer 0.5`).
3. **The literal matchup.** What this opponent allows at the position against the league (`Matchup Weight`, the defense ranks tab).
4. **Game environment.** FanDuel's spread and total turned into team points and four game scripts. The book's number is used because it
   beat our own formula.
5. **Hit chance for every line.** Projection -> chance of each X+ rung, fitted on past errors (`probit.json`), then blended with the
   price because the raw model ran overconfident where it disagreed with FanDuel (`calib.py`).
6. **Proof.** Legs are frozen before kickoff and graded against the box score; a change goes live only if it wins on past weeks
   (`2025 WALK-FORWARD VALIDATED` / `REJECTED` in the settings).

## The same method, sport-neutral (`core/`)

| NFL piece | Here | What it does |
|---|---|---|
| season + last-4 + priors | `core/baseline.py` | averages built only from earlier games, recency blend, pull toward a prior |
| vacated targets / carries | `core/budget.py` | a team has a fixed budget (240 NBA minutes); active players' baselines are fitted to it |
| offense-vs-defense grid, SOS adjust | `core/ratings.py` | the grid solved for uneven schedules: league x home x OFFENSE[team] x DEFENSE-ALLOWED[opp] |
| probit curves | `core/dist.py` | projection -> chance of an X+ line; soccer scorelines |
| calib.py, fair odds, edge | `core/odds.py` | American odds, implied %, model blended with the book (starts 50/50) |
| V2 - Leg Board | `core/legboard.py` | the same 18 columns, so boards / builder / Live can read any sport |
| FanDuelOdds.gs | `core/oddsapi.py`, `snapshot_prices.py` | the same Odds API calls and betslip ids, in Python (draft, never run live) |
| receipts, Brier, calibration | `core/metrics.py`, `*/backtest.py` | walk-forward grading |

## Where each sport stands

Numbers are in `backtests/RESULTS.md` (regenerate with `python -m sports.report`). Weights were chosen on one season and scored on the
next. Nothing has been compared with FanDuel's prices: none are stored for these sports yet.

### NBA - the strongest start

- **Built:** minutes (season + last 5) x per-minute rates, fitted to the team's 240 minutes among the players who are active, x what the
  opponent allows to guards / forwards / centers, moved toward the team's expected total; chance of every X+ rung; tonight's board in the
  leg-board columns (`nba/slate.py`).
- **Checked on 2026-27 to date (2,877 player-games):** 6.9% closer than the season average on points, 7.2% rebounds, 7.6% assists,
  4.7% threes; hit chances beat the "cleared it in 7 of 10" number at every rung tested.
- **What the test says about the method:** in the NBA the lead signal is minutes and who is out, not the matchup. Fitting minutes to the
  team budget was the biggest single gain; the defense-vs-position matchup moved the points error by about 0.003. BetSweep's
  matchup-first habit from the NFL should not be carried over as is.
- **Missing:** the injury report (who is active is still typed in or assumed), FanDuel prices, rest / back-to-backs, blowout risk from the
  spread, the market total in place of our own team total.

### Premier League - workable

- **Built:** the grid on a 50/50 blend of expected goals and goals -> each side's goal rate -> every scoreline -> home / draw / away,
  totals, both teams to score. Players: minutes when starting x per-90 rates x the opponent/home factor -> anytime goalscorer, shots,
  shots on target.
- **Checked:** home / draw / away is level with an Elo-only model on 2025-26 (log loss 1.0323 vs 1.0309) and well ahead of flat rates.
  Totals were no better than last season's flat rate in 2025-26 and only slightly better in 2026-27. Anytime goalscorer and shots beat
  the player's own hit rate on 2026-27, but that is 100 matches.
- **Missing:** confirmed line-ups (they land about an hour before kickoff and decide everything for props), FanDuel prices, cards and
  corners, a check against bookmaker prices. Promoted clubs start from the average of earlier promoted clubs.
- **Data caution:** the history comes from a community data set. One season's starter flags were wrong in it (handled in `epl/data.py`).
  Before anything is published the live build should read the official Fantasy Premier League feed and ESPN as well.

### College football - the book wins, and props are off the table in Tennessee

- **Built:** the schedule-adjusted grid on points (lower-division teams pooled) -> margin and total; a thin player layer.
- **Checked against DraftKings' lines, 2026 (751 games):** the book's spread missed by 11.9 points on average, the grid by 13.3. Taking the
  grid's side went 352-389 against the spread. The results put no weight on the grid when it disagrees with the book. This is the NFL
  finding again: the price already holds what a points-only rating knows.
- **Law:** Tennessee does not allow bets on individual college athletes, so only game lines are bettable there.
- **So:** college football should be market-led like the NFL scripts (use the book's spread and total as the environment) and earn its
  edge from what a rating cannot see: a quarterback out, weather, opt-outs. The player layer was about 1% better than the season average.
  The season is in its last regular-season weeks, so this is a build for 2027 unless the owner wants bowl-season game lines.

## Data sources

| Sport | History (used today) | Live (to wire) | Prices |
|---|---|---|---|
| NBA | sportsdataverse ESPN box scores, one CSV a season, refreshed daily | ESPN scoreboard / summary / injuries | The Odds API `basketball_nba`, props and alternates |
| EPL | github.com/olbauday/FPL-Elo-Insights (matches, xG, shots, player match stats) | official FPL API, ESPN `soccer/eng.1` | The Odds API `soccer_epl`: goalscorer, shots, shots on target, assists, cards (US books only) |
| CFB | sportsdataverse ESPN schedules + cfbfastR play-by-play (includes DraftKings' spread and total) | ESPN `football/college-football`, CollegeFootballData API | The Odds API `americanfootball_ncaaf` |

Checked on 2026-11-15: the three history sources download from this workspace (NBA through 11/14, EPL through gameweek 10, college through
week 11); ESPN's NBA scoreboard answers on the same host the NFL feeds use; The Odds API lists the markets above. Not checked today:
ESPN's soccer and college endpoints, and what FanDuel actually posts for EPL player props (needs one test pull).

Known data traps, each handled or flagged in code: the college play-by-play repeats about 2.6% of plays (de-duplicated); its rushing yards
leave out sacks, which the official box score charges to the quarterback; FPL player ids change every season (`player_code` is stable);
NBA all-star exhibition rows sit in the regular-season file (dropped).

## Costs and decisions for the owner

1. **The Odds API plan.** The NFL pulls use about 580 credits a day, about 17,400 of the 20,000 on the $30 plan (`CORE_PER_DAY` in
   FanDuelOdds.gs). Saving NBA and EPL prices three times a day is about 7,100 more a month. That needs the 100,000-credit plan ($59 a
   month, checked 2026-11-15). Without stored prices nothing can be graded against FanDuel, so this is the step everything else waits on.
2. **Order.** NBA first (in season, best numbers), then EPL, then college game lines for 2027.
3. **Where the weights live.** Here they are in code with a tuning log, which is what makes the walk-forward tests repeatable. A read-only
   sheet per sport for looking at them is easy to add; putting them back into sheet formulas is not recommended.
4. **CollegeFootballData key** (free, 1,000 calls a month, commercial use allowed) when college work resumes.

## Build order

- **Step 0 (done):** this folder: shared core, three baselines, walk-forward results, 11 checks including leak tests.
- **Step 1:** switch on price snapshots for NBA and EPL (after the plan change), freeze the model's legs beside them, and grade for two to
  three weeks. Decide the model-vs-book weight per market from those grades, as the NFL build did.
- **Step 2:** injuries and line-ups feed (NBA report, FPL flags, confirmed elevens); rest days and blowout risk; market totals as the
  environment.
- **Step 3:** site pages per sport from the leg board (boards, builder, Live), on a daily clock for the NBA. Only after Step 1 says the
  numbers hold. Nothing on the site changes before then.
- **Step 4:** more soccer leagues (the grid and player code are league-neutral), then the next sport.

## Run it

```
bash sports/fetch_data.sh                                  # about 1.1 GB into sports/_data (not committed)
BS_SPORTS_DATA=sports/_data python -m sports.nba.backtest  # add --tune to re-pick the weights (about ten minutes)
BS_SPORTS_DATA=sports/_data python -m sports.epl.backtest
BS_SPORTS_DATA=sports/_data python -m sports.cfb.backtest
python -m sports.report                                    # backtests/RESULTS.md and the current grids
python -m sports.tests.test_groundwork                     # 11 checks, no data needed
```

## Sources checked 2026-11-15

- The Odds API markets: https://the-odds-api.com/sports-odds-data/betting-markets.html
- The Odds API credit costs: https://the-odds-api.com/liveapi/guides/v4/ ; plans: https://the-odds-api.com/
- CollegeFootballData tiers and terms: https://collegefootballdata.com/api-tiers , https://collegefootballdata.com/terms
- Tennessee college player props: https://www.actionnetwork.com/online-sports-betting/Tennessee/
