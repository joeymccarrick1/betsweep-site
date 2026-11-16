# Why the slips miss, and what the replay says (11/15, after Week 10 Sunday)

Owner: "We're so close with some of these bets. Just a few legs off. There's gotta be a way." Everything below is graded from the sheet's
FanDuel leg snapshots (Weeks 6-9, 6,519 graded legs, real prices and results), the PROMO tab, the game cards and the game log.
"Priced" = the chance FanDuel's odds imply. Scripts: /tmp/an (replay.py, tables.py, more.py, td.py) - rebuild from this file if needed.

## 1. "One leg off" is what a 4-leg slip does
Random slips from every FanDuel floor leg (-320 to -180), one leg per game, 40,000 slips a week:

| shape | cashes | misses by one | avg price | return per $1 |
|---|---|---|---|---|
| 4 floor legs | 16.6% | 38% | +319 | -30% |
| 3 floor legs | 26.0% | 45% | +193 | -24% |
| 2 floor legs | 41.0% | 46% | +105 | -16% |
| 6 floor legs | 6.6% | 23% | +757 | -44% |
| 2 near-even legs (-125 to +110) | 22.9% | 50% | +262 | -17% |
| 2 plus-money legs (+101 to +200) | 16.5% | 48% | +469 | -7% (swings by week) |
| 4 floor, round robin by 3s | - | - | - | -24% |

No filter made floor parlays profitable: near-zero filter -28% (4 legs) / -22% (3); favorites of 3+ only -24% / -20% (0%, -45%, -33%, -1%
by week); underdogs of 3+ only -31% (3 legs); no rushing yards -26%.

## 2. Floor legs are FanDuel's most overpriced product
| price band (overs) | legs | hit | priced | return per leg |
|---|---|---|---|---|
| -399 to -250 | 630 | 65.6% | 74.5% | -12.0% |
| -249 to -180 | 791 | 63.3% | 67.7% | -6.3% |
| -179 to -130 | 775 | 53.8% | 60.0% | -10.3% |
| -129 to +100 | 1,552 | 47.2% | 53.0% | -10.9% |
| +101 to +200 | 910 | 40.2% | 42.5% | -4.9% |
| +201 to +400 | 181 | 26.5% | 28.8% | -8.8% |

Floor legs by market: rushing yards 59.9% vs 70.2% priced (-14.7% a leg), receptions 65.6% vs 71.5%, receiving yards 64.9% vs 70.2%,
passing yards 67.2% vs 71.2%. Our own picks: PROMO legs at -180 or shorter hit 59.3% vs 72.1% priced (113 legs); the site's "safer" tier in
Model's Best, Weeks 8-9: 59.0% vs 68.6% (-14.0% a pick, 144 picks) while the even-money tier lost 2.5% (586), plus-money 4.6% (113), TDs 1.1% (23).

## 3. PROMO record, Weeks 6-9
0 for 37. Posted prices implied about 3.7 wins. Only 2 multi-leg slips missed by exactly one leg (SNF Same Game 7, SNF Prime Time);
most missed by 2 to 4. Game-card best parlays: 15 of 55 (27.3%) against 39.7% priced.

## 4. What the model can and cannot do
Raw model vs fair price: legs the model had 10+ pts BELOW the price hit 7.1 pts under it (t -3.1, 349 player-weeks) - the model is good at
naming bad legs. Legs it had 10+ above were about fair (-0.1 pts). The sheet's STRONG VALUE verdict returned +0.1% a leg (632 legs);
VALUE -10.9%, FAIR -5.0%, PASS -11.2%. Among floor legs the model's ranking did not help.
Totals: lean record 29-28 (unders 11-11, overs 18-17); the model's P(over) sat at 49-51% on every Week 10 card. Script label right 23 of 57.

## 5. Overs vs unders at the main line
Over hit 47.1% on 1,360 main lines (rushing 43.0%, receptions 45.0%, receiving yards 49.0%, passing 52.7%). So unders at about -114 were
roughly break-even overall (52.9%), rushing unders 57.0% (+6.9% per $1, 42-45% over rate in every week), receptions unders 55.0% (+3.2%).
Week 9 at FanDuel's real under prices: receptions +3.9% (138), passing +5.3% (41), receiving -0.9% (178), rushing -5.2% (93).

## 6. Which side of the game
Floor legs on the team the model's most likely ending has losing by 10+: 61.0% vs 70.7% priced (439 legs, t -2.4); rushing 55.2%, receiving
yards 59.9%, passing 54.3%, receptions 69.2%. Projected big winner: 67.9%. FanDuel spread: favorites by 7+ 69.4%, 3-6.5 66.8%, within 2.5
64.4%, underdogs 3-6.5 61.1%, 7+ 61.1%. Underdog floors were under their price in all four weeks (57-66%); favorites beat them in three.
Now a hard `bad` flag, "Losing side" (yardage overs only).

## 7. Two-touchdown games
30 in Weeks 6-9 (16 RB, 7 TE, 7 WR). By anytime-TD price: -150 or shorter scored twice 16% of the time (5 of 31, fair about +520),
+101 to +200 8% (11 of 134, fair about +1100), longer than +200 about 1%. Week 10 Sunday (box scores): McCaffrey 3, Pickens 3, Gibbs 2,
St. Brown 2, Josh Allen 2, Hubbard 2, Kamara 2, Deebo Samuel 2, Emmett Johnson 2. On Sunday morning's 2+ TD list (200 legs by model chance)
they ranked 2, 54, 1, 31, 16, 8, 36, not listed, 97. Seven of nine played for a team projected at 25.5+ (SF 30, BUF 29, DET 26.5, KC 25.5, DAL 25.5).

## Week 10 notes
ATL 13-35 KC (model's most likely ending: KC by 10+, 33%). MIN 30-10 GB (FanDuel GB -2.5; our GB -8.5 came from the similar-defense number).
Totals unders this week so far: 2 of 6 (GB-MIN 40, NYG-WAS 45 hit; CLE-HOU 51, IND-MIA 46, ARI-LA 40, DAL-SF 86 missed).
