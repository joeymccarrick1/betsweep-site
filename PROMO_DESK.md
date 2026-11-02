# BetSweep Promo Desk - instructions for the scheduled promo drafts (owner 11/1)

The owner posts promos on X / Instagram on a weekly calendar. Each scheduled run drafts the promos for ONE slot and the post copy,
then stops. The owner reviews, adjusts in FanDuel, places the bets and adds the rows to 'PROMO - Promoted Bets' himself.
Owner-facing playbook (calendar, rules, templates, video ideas): the Claude Doc "BetSweep Weekly Promo Playbook"
(https://claude.ai/artifact/PaUnWPDt2ixt63hGhKANmg).

## Hard rules
- Draft only. NEVER write to the Google Sheet (no PROMO rows, no logs), never push to the site repo, never post anywhere.
- Never invent a number. Every probability, price, average or rank comes from the data below; if something is missing, say so.
- Nobody is watching: no questions; make the call and say what you assumed in one line.
- The final message is read on a phone: short headed sections, each promo as a copy-ready block.

## Data (all public, read-only)
1. Clone the site: `git clone -q --depth 1 https://github.com/joeymccarrick1/betsweep-site.git site` (if the repo is already attached,
   use it and `git pull`). Then `git -C site fetch -q origin feeds:feeds` for the ESPN mirror.
2. Builder data: `site/build/data-*.js` = `window.__X = {...};` JSON after the first `=`. `D.week`, `D.games` (gid, a, b, ko ms UTC,
   kickoff text), `D.legs`: one per FanDuel line - `pl` player, `pos`, `tm`, `opp`, `g` gid, `m` market, `ln` line (X+), `o` FanDuel
   American odds, `p` BetSweep % (model blended with the market for yardage legs; model for TDs), `pm` model-only %, `bk` FanDuel
   implied %, `e` edge = p - bk, `proj` projection, `avg` season average, `n` games, `w` risk text (non-empty = a 'bad' flag),
   `fh` line flags `[kind, tag, text]`, `fd` = {m: marketId, s: selectionId, u: single-leg link}, `bks` DraftKings / Hard Rock prices,
   `tier` Model's Best tier (even / td / safe), `gl` set on game lines (moneyline / spread / total), `gd` game-day status text.
   `D.pf[player]` = the player's flags `[kind, tag, text]` (kinds: bad / watch / good / info).
3. Live risk: `git -C site show feeds:injuries.json` (ESPN injury report), `feeds:inactives.json` (game-day outs), `feeds:weather.json`
   (kickoff forecast per game), and `site/data/risk-notes.json` (the owner's player notes: HURT / LIMITED / OUT = avoid).
4. Already-posted promos this week: `site/b/promos.json` (don't repeat the same legs in a new promo the same day).
5. The site is the source of truth; the Sheets connector is not needed.

## Leg filter (every promo)
A leg is usable only if ALL hold:
- its game kicks off at least 30 minutes after this run (`ko`), and the player is not Out / Doubtful / Inactive in injuries.json or
  inactives.json, not OUT / HURT / LIMITED in risk-notes.json, and not marked CONFIRMED OUT in `gd`;
- no 'bad' flag (`w` empty and no `bad` in `D.pf[pl]`), and no 'Blowout rest risk', 'Market disagrees' or 'Playing through it' tag;
- not Longest Reception; Rushing Yards only when `pm - bk >= 0.05`;
- odds better than -250, unless `p >= bk` (both model and market rate it above the price);
- yardage / reception legs: choose the rung where `proj / ln - 1` is between 0.10 and 0.25 (best `e` among them); if none, the rung
  closest to -150;
- weather: no passing / receiving legs in a game whose weather.json row is HIGH risk.

## Building a parlay
- Core promos: 3-5 legs. Reach a target price by moving ONE leg up a rung (or swapping in a TD) before adding a leg.
- Parlay chance = product of `p` for legs in different games. Same-game legs are correlated: say "same-game - check FanDuel's
  SGP price" and estimate the price as 0.85 / (product of bk) (FanDuel's ~15% SGP hold) - never present that estimate as FanDuel's quote.
- Multi-game price = product of decimal odds. Show American odds.
- FanDuel link (exact format, do not change): one leg -> `fd.u`; several ->
  `https://sportsbook.fanduel.com/addToBetslip?marketId[0]=<m>&selectionId[0]=<s>&marketId[1]=...` (index from 0). Legs without `fd`
  ids: list them as "add by hand".
- Name every promo (fun, short, on-theme: holidays, rivalries, the player). Give one line of why per leg with a real number
  (average, hit rate, matchup rank from flags/pf, projection).
- Profit boost suggestion: name the promo with the highest chance as the one to boost.

## Slots
- **thursday** (TNF): (a) single best bet: the one leg with the highest `e` among legs at -150..+150 with `p >= 0.5`; (b) +500 (target
  +400..+650, 3-4 legs, highest chance); (c) +5000 lottery (+3500..+7000, a story-driven same-game build - TDs + overs that need the same
  game script; 4-6 legs, label LOTTERY).
- **friday** (fantasy, no bets): 3 flex calls from players in this week's Sunday games - pairs at the same position within 2 points of
  projection where one is clearly better on matchup rank, volume trend or flags; write each as "Start A over B: reason", using the logic of
  /team/compare/ (site/team/compare/data.json has projections, last-4 games, flags). Plus a "weekend watch" line: any HIGH weather game and
  notable Questionable players.
- **saturday** (early Sunday card): "Model's Best" 3 legs from 3 different Sunday games using legs with a `tier`, a themed name.
- **sunday_main** (posted ~10:30 AM after inactives): (1) Favorite TDs: 3-4 Anytime TD legs, different games, `p >= 0.40`, price +200 or
  shorter, highest `p`; (2) Either/Or TDs: 5-6 of the most confident games, for each the two likeliest scorers (FanDuel's "Either TD"
  market is not in the data - list the pairs and say to build it in FanDuel's Either-player market); (3) Sweep: best single leg from the 5
  games with the most usable legs at `p >= 0.62`; (4) Best legs: 3-4 legs with the highest `p` at -200 or longer. Then mark which one to boost.
- **sunday_late**: one 3-4 leg parlay from the 3:05 / 3:25 PM games only.
- **snf** / **mnf**: the night game's +500 (3-4 legs) and +5000 lottery as on Thursday.
- **tuesday** (receipt): no bets. Read `site/receipts/` (newest week page) and the promo grades it shows, plus `site/b/promos.json`; write
  the receipt post (core record vs lottery record, best hit, toughest miss with its "why it lost" line if the receipt shows one) and a
  60-second video script. If last week is not graded yet, say so and stop.

## Output (final message)
For each promo: `NAME - price (chance %)`, the legs (player, line, odds, BetSweep %), one-line why per leg, the FanDuel link, then an X
post and an Instagram caption from the templates in the playbook (end with "21+ | gamble responsibly"). Thursday / Sunday main / prime-time
runs add a 4-line Reel/TikTok script (hook, the slip, the one stat, the call to action). Finish with "Assumed:" (one line) and
"Skipped:" (legs dropped for injury / weather / flags, one line).
