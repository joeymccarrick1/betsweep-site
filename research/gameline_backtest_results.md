# Game-line backtest: adjustments to the closing line

Scored out of sample 2024 W7 - 2026 W6 (REG season, 545 games; 2024 W1-6 warm-up, training only). Betas refit every week on all prior games (no intercept; ridge lambda=1.0 for the combined model). Team strength = current season to date blended with prior season final (w=n/(n+4)), z-scored league-wide per week.

## Closing-market baseline

- margin MAE vs result: 9.495
- Brier (moneyline, vig removed): 0.2056; Brier (spread via normal, sigma walk-forward): 0.2066
- totals MAE: 10.205; market favourite SU win rate 0.680; home cover rate 0.507

## Candidates

| candidate | target | games | MAE adj | MAE close | delta (p) | CLV rate (hits/n, binomial p vs 50%) | Brier adj | Brier mkt (ML) | ML record when disagreeing (adj-mkt, n) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| a1 EPA diff (z) | margin | 545 | 9.675 | 9.495 | +0.179 (p=0.02) | 0.485 (191/394, p=0.55) | 0.2051 | 0.2056 | 1-0 (n=1) |
| a2 EPA minus record (z) | margin | 545 | 9.488 | 9.495 | -0.007 (p=0.59) | 0.544 (31/57, p=0.51) | 0.2065 | 0.2056 | 0-0 (n=0) |
| b  TO-margin regression | margin | 545 | 9.503 | 9.495 | +0.007 (p=0.85) | 0.510 (149/292, p=0.73) | 0.2061 | 0.2056 | 1-0 (n=1) |
| c1 rest diff (days) | margin | 545 | 9.565 | 9.495 | +0.070 (p=0.05) | 0.493 (33/67, p=0.90) | 0.2080 | 0.2056 | 4-4 (n=8) |
| c2 away short rest (<=5d) | margin | 545 | 9.528 | 9.495 | +0.032 (p=0.13) | 0.462 (18/39, p=0.63) | 0.2077 | 0.2056 | 0-2 (n=2) |
| c3 rest diff + short flags + div | margin | 545 | 9.639 | 9.495 | +0.144 (p=0.01) | 0.481 (111/231, p=0.55) | 0.2104 | 0.2056 | 5-7 (n=12) |
| e  bodies out diff (QB x3) | margin | 545 | 9.554 | 9.495 | +0.058 (p=0.60) | 0.521 (208/399, p=0.39) | 0.2082 | 0.2056 | 11-14 (n=25) |
| f  combined ridge (all margin feats) | margin | 545 | 9.743 | 9.495 | +0.248 (p=0.08) | 0.517 (238/460, p=0.46) | 0.2084 | 0.2056 | 12-15 (n=27) |
| d1 totals: wind>=15 outdoor | total | 333 | 10.415 | 10.356 | +0.059 (p=0.25) | 0.524 (11/21, p=0.83) | - | - | - |
| d2 totals: temp<=32 outdoor | total | 333 | 10.442 | 10.356 | +0.086 (p=0.25) | 0.640 (16/25, p=0.16) | - | - | - |
| d3 totals: wind>=15 or temp<=32 | total | 333 | 10.453 | 10.356 | +0.097 (p=0.22) | 0.532 (25/47, p=0.66) | - | - | - |
| d4 totals: wind>=15 and temp<=32 | total | 333 | 10.362 | 10.356 | +0.006 (p=0.43) | 0.500 (1/2, p=1.00) | - | - | - |

CLV rate = share of games where the adjusted line moved >= 0.5 pt off the close AND the side it moved toward covered the close (pushes dropped). ML record = games where sign(adjusted margin) != sign(closing spread): adjusted-pick wins vs market-favourite wins (ties dropped). Break-even ATS at -110 is 52.4%.

Notes: f_home_short and f_away_short are collinear (Thursday games put both teams on <=5 days rest), so c2 is effectively a 'Thursday game' flag and the ridge splits the weight equally between the two. 2026 W5-W6 rows have no wind/temp yet, so outdoor games there are excluded from the totals tests. Weather flags fire rarely (counts below), so d1-d4 are low-power.

## Coverage / caveats

- games_total: 637
- games_scored: 545
- score_range: 2024 W7 - 2026 W6
- games_2026: 93
- weather_known_outdoor_scored: 333
- weather_missing_2026: 22
- injury_rows_teamweeks: 856
- games_with_any_bodies_out: 499
- games_with_qb_out: 89
- wx_flag_counts: {'f_wx_wind': 30, 'f_wx_cold': 28, 'f_wx_either': 54, 'f_wx_both': 4}

## Final-week betas

- a1 EPA diff (z): [0.6079427743109711]
- a2 EPA minus record (z): [-0.65118676651545]
- b  TO-margin regression: [-0.7193289594599918]
- c1 rest diff (days): [0.19289185905224787]
- c2 away short rest (<=5d): [-1.8295454545454546]
- c3 rest diff + short flags + div: [0.19243705826273041, -1.131094255101599, -1.1310942551015895, 0.7133911302063982]
- e  bodies out diff (QB x3): [-0.59467680608365]
- f  combined ridge (all margin feats): [0.6206974526647756, -0.8521884825474983, -0.12442656177269641, 0.13889100822773892, -1.0536722065486885, -1.0536722065486919, 0.7924623492295805, -0.5179183536283015]
- d1 totals: wind>=15 outdoor: [-0.014705882352941478]
- d2 totals: temp<=32 outdoor: [1.8749999999999996]
- d3 totals: wind>=15 or temp<=32: [0.9999999999999997]
- d4 totals: wind>=15 and temp<=32: [-1.5]
