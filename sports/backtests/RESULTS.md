# Walk-forward results

Every projection below was made from earlier games only. Weights were chosen on one season and scored on the next, which they never saw.
Lower is better for every error number. Nothing here has been compared with FanDuel's prices yet: no NBA, EPL or college prices are stored.

## NBA (data through 2026-11-14)

Checked on 2,877 player-games of 2026-27 (rotation players), weights chosen on 2025-26.

| Stat | Season average | Model | Better by |
|---|---|---|---|
| Points | 5.13 | 4.78 | 6.9% |
| Rebounds | 2.04 | 1.89 | 7.2% |
| Assists | 1.53 | 1.41 | 7.6% |
| Threes | 1.01 | 0.96 | 4.7% |
| Pts + reb + ast | 6.54 | 6.12 | 6.5% |
| Minutes | 4.67 | 4.32 | 7.4% |

Average miss per player per game. The minutes line uses the players who actually played, so it is the projection once the night's inactives are known.

Hit chances for 'X+' lines, 2026-27 (Brier score: 0 is perfect; 'own hit rate' is the 'cleared it in 7 of 10' number on a prop page):

| Market | Model | Own hit rate |
|---|---|---|
| Points 10+ to 30+ | 0.1027 | 0.1154 |
| Rebounds 4+ to 12+ | 0.1028 | 0.1167 |
| Assists 2+ to 10+ | 0.0927 | 0.1062 |
| Threes 1+ to 5+ | 0.1266 | 0.1359 |

What moved the number most on 2025-26 (the tuning log is in nba.json): fitting the active players' minutes to the team's 240 (minutes miss 4.68 -> 4.37), then the team-total step; the defense-vs-position matchup moved points by about 0.003.

## Premier League (data through 2026-11-08)

| | Matches | Model | Last season's rates | Elo only |
|---|---|---|---|---|
| Home / draw / away, 2025-26 (weights chosen here) | 380 | 1.0323 | 1.0840 | 1.0309 |
| Home / draw / away, 2026-27 (never seen) | 100 | 1.0199 | 1.0812 | not on file |

Log loss. The grid is level with an Elo-only model. Over 2.5 goals and both-teams-to-score were no better than last season's flat rate in 2025-26 (0.2541 vs 0.2479 on over 2.5), so totals are not a strength of this version.

Players, 2026-27: 1,595 starts by outfield players with 450+ minutes on record.

| Market | Legs | Model | Benchmark |
|---|---|---|---|
| Anytime goalscorer (Brier) | 716 | 0.0916 | 0.1070 (own scoring rate) |
| Shots 1+ (Brier) | 716 | 0.1918 | 0.2181 (own hit rate) |
| Shots 2+ (Brier) | 716 | 0.1672 | 0.1870 (own hit rate) |
| Shots on target 1+ (Brier) | 716 | 0.1812 | 0.1934 (own hit rate) |
| Shots on target 2+ (Brier) | 716 | 0.0678 | 0.0794 (own hit rate) |
| Shots per start (average miss) | | 0.873 | 0.956 (per-game average) |

One hundred matches is a small sample; read 2026-27 as a direction.

## College football (data through 2026-11-15)

Game lines against DraftKings' spread and total (the only prices on file).

| | Games | Model | Book |
|---|---|---|---|
| Margin, average miss, 2025 (weights chosen here) | 947 | 12.59 | 11.90 |
| Margin, average miss, 2026 (never seen) | 751 | 13.29 | 11.89 |
| Total, average miss, 2026 | 751 | 12.87 | 12.25 |
| Winner picked, 2026 | 751 | 74.3% | 78.3% |

Against the spread in 2026, taking the model's side every game: 352-389 (47.5%). Only when the model and the book are 5+ points apart: 125-154 (44.8%); the same rule was 169-142 (54.3%) on 2025, the season the weights were fitted to. 52.4% is break-even at -110.
Weight the 2026 results put on the model when it disagrees with the book: -0.13 for margins, -0.10 for totals (0 = the book's number already holds everything this grid knows).

Player layer, 2026 (not bettable in Tennessee):

| Stat | Player-games | Season average | With matchup | Better by |
|---|---|---|---|---|
| Passing yards | 792 | 66.52 | 65.86 | 1.0% |
| Rushing yards | 1,737 | 33.54 | 33.16 | 1.1% |
| Receiving yards | 3,023 | 27.74 | 27.70 | 0.1% |
| Receptions | 3,294 | 1.69 | 1.69 | 0.2% |
