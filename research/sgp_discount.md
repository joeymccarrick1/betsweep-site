# FanDuel's same-game discount (measured)

35 same-game slips with FanDuel's own price, Weeks 7-12: 20 we posted (the promo tab) and 15 the owner priced on his
betslip without posting (screenshots of 11/14). "Share of the multiplied payout" = FanDuel's
payout on $1 divided by what the legs multiplied would pay.

| Legs in one game | Quotes | Share of the multiplied payout (low - median - high) |
|---|---|---|
| 2-3 legs | 3 | 80% - 80% - 103% |
| 4 legs | 18 | 58% - 87% - 118% |
| 5-6 legs | 6 | 59% - 70% - 118% |
| 7+ legs | 8 | 6% - 32% - 61% |

Fit: FanDuel's price for n legs in one game = exp(-0.00343 x (n-1)^2.5) / (FanDuel's implied chances joined with our same-game correlations).
That multiplier by leg count: 2 legs 100%, 3 legs 98%, 4 legs 95%, 5 legs 90%, 6 legs 83%, 7 legs 74%, 8 legs 64%, 9 legs 54%, 10 legs 44%.
Median miss (log price): legs multiplied 0.19; old estimate (0.85 / joint + 0.15) 0.14; new estimate, each slip left out of its own fit 0.07. By length, new estimate: 2-4 legs 0.04 (21 slips); 5+ legs 0.12 (14 slips).

Is there a better formula? Each candidate prices every slip with a fit that never saw it (median, mean, short slips, long slips; lower is better): the legs' count only (in use): 0.068 / 0.117 / 0.039 / 0.118; count + a cut for each long-shot leg: 0.059 / 0.112 / 0.039 / 0.190 (each long-shot leg x0.94). A candidate replaces the formula in use only when it is no worse on all four and better on two.
How far off the estimate has been (four slips in five landed inside): 2-4 legs x/÷ 1.10 (21 slips); 5-6 legs x/÷ 1.27 (6 slips); 7+ legs x/÷ 1.57 (8 slips).
From the site: 0 quotes typed or imported by readers (0 rows dropped as not a possible same-game price).

| Wk | Slip | From | Legs | FanDuel | Legs multiplied | Share | Old estimate | New estimate (left out of its own fit) |
|---|---|---|---|---|---|---|---|---|
| 7 | TNF SGP | posted | 4 | +595 | +679 | 88% | +506 | +559 |
| 7 | Thursday Night Lotto | posted | 4 | +5337 | +8850 | 60% | +4831 | +5383 |
| 7 | Sunday Night Lotto | posted | 7 | +7352 | +25155 | 29% | +12997 | +11549 |
| 7 | MNF Piss Missile | posted | 8 | +11825 | +188249 | 6% | +23510 | +18652 |
| 7 | MNF SGP | posted | 5 | +492 | +828 | 59% | +486 | +502 |
| 8 | Thursday's Little Geemer | posted | 8 | +21954 | +36182 | 61% | +16941 | +11861 |
| 8 | SNF Prime Time | posted | 4 | +777 | +890 | 87% | +757 | +839 |
| 8 | Commander-in-Diggs | posted | 5 | +4147 | +5647 | 73% | +3511 | +3688 |
| 8 | Piss Missile Monday | posted | 9 | +6168 | +22480 | 27% | +9862 | +6196 |
| 9 | Crossfire | posted | 3 | +690 | +857 | 80% | +728 | +839 |
| 9 | Run It, Chase It | posted | 5 | +4700 | +5702 | 82% | +4847 | +5102 |
| 9 | Piss Missile Monday | posted | 7 | +4613 | +11325 | 41% | +7082 | +6230 |
| 10 | Daily Sweep: Wet Work | posted | 4 | +302 | +256 | 118% | +243 | +266 |
| 10 | Thursday Night Thievery | posted | 5 | +2467 | +3916 | 63% | +2583 | +2714 |
| 10 | Daily Sweep: Herbo Fully Loaded | posted | 4 | +259 | +447 | 58% | +312 | +343 |
| 10 | Piss Missile Monday | posted | 8 | +4174 | +17313 | 24% | +5808 | +4367 |
| 11 | Thursday Night Thievery | posted | 6 | +3731 | +5604 | 67% | +3047 | +2926 |
| 11 | Daily Sweep: Low Bar | posted | 5 | +484 | +411 | 118% | +351 | +358 |
| 11 | Daily Sweep: Dig a Burrow | posted | 3 | +224 | +279 | 80% | +213 | +244 |
| 11 | Piss Missile Monday | posted | 8 | +3400 | +8722 | 39% | +4084 | +3000 |
| 10 | Test sweep: DET-NE | owner's betslip | 4 | +270 | +377 | 72% | +251 | +274 |
| 10 | Test sweep: DET-NE (Over 44.5) | owner's betslip | 4 | +238 | +317 | 75% | +218 | +238 |
| 10 | Test sweep: ATL-KC | owner's betslip | 4 | +266 | +331 | 80% | +244 | +267 |
| 10 | Test sweep: ATL-KC (Penix 175+) | owner's betslip | 4 | +216 | +258 | 84% | +192 | +209 |
| 10 | Test sweep: BUF-NYJ | owner's betslip | 4 | +393 | +346 | 114% | +307 | +337 |
| 10 | Test sweep: CAR-NO | owner's betslip | 4 | +280 | +320 | 87% | +243 | +266 |
| 10 | Test sweep: CLE-HOU | owner's betslip | 4 | +321 | +283 | 114% | +265 | +290 |
| 10 | Test sweep: JAX-TEN | owner's betslip | 4 | +289 | +305 | 95% | +227 | +248 |
| 10 | Test sweep: ARI-LA | owner's betslip | 3 | +172 | +167 | 103% | +138 | +157 |
| 10 | Test sweep: LV-SEA | owner's betslip | 4 | +274 | +279 | 98% | +237 | +260 |
| 10 | Test sweep: DAL-SF | owner's betslip | 4 | +262 | +355 | 74% | +234 | +256 |
| 10 | Test sweep: DAL-SF (Over 47.5) | owner's betslip | 4 | +233 | +293 | 80% | +206 | +225 |
| 10 | Test sweep: CIN-PIT | owner's betslip | 4 | +308 | +353 | 87% | +278 | +305 |
| 10 | Test sweep: CIN-PIT (Warren 20+) | owner's betslip | 4 | +255 | +286 | 89% | +224 | +244 |
| 12 | Owner's boards slip: GB-LA 8 legs (11/24 11:38 PM; the boards showed +8204, the legs multiplied) | owner's betslip | 8 | +2924 | +8204 | 36% | +3544 | +2602 |

Same-game slips whose tab price is just the legs multiplied (not a quote, left out): Wk 6 MNF Floor 6; Wk 6 Piss Missile Monday.

Skipped: Wk 6 SNF Same Game 7 - a leg has no price (MarShawn Lloyd); Wk 7 Thursday's Little Geemer - a leg has no price (D'Andre Swift or A.J. Brown); Wk 7 Sunday Night +500 - a leg has no price (Kenneth Walker III or Travis K); Wk 8 777s - a leg has no price (Chuba Hubbard or Tetairoa McMi); Wk 8 Piss Missile Monday - a leg has no price (D'Andre Swift or Colston Lovel); Wk 8 Bear Down - a leg has no price (Jaxon Smith-Njigba); Wk 9 Buffalo Wings - a leg has no price (James Cook); Wk 11 Favorite 6 - a leg has no price (Justice Hill); Wk 5 Piss Missile Monday - a leg has no price (James Cook); Wk 5 The Piss Missile - a leg has no price (CeeDee Lamb); Wk 5 TNF 3-Leg SGP - a leg has no price (Cade Otton); Wk 5 TNF 6-Leg Sweep - a leg has no price (CeeDee Lamb); Wk 5 The Teaser - a leg has no price (LV +8 (LV-NE)); Wk 5 Keon Control - a leg has no price (Keon Coleman); Wk 5 Monday Night SGP - a leg has no price (Kyren Williams or James Cook).
