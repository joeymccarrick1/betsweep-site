# BetSweep Promo Desk - instructions for the scheduled promo drafts (owner 11/1)

The owner posts promos on X / Instagram on a weekly calendar. Each scheduled run drafts the promos for ONE slot and the post copy,
then stops. The owner reviews, adjusts in FanDuel, places the bets and adds the rows to 'PROMO - Promoted Bets' himself.
Owner-facing playbook (calendar, rules, templates, video ideas): the Claude Doc "BetSweep Weekly Promo Playbook"
(https://claude.ai/artifact/PaUnWPDt2ixt63hGhKANmg).

## Hard rules
- Draft only. NEVER write to the Google Sheet (no PROMO rows, no logs), never push to main or gen-overrides, never post anywhere. The only write
  allowed is the `promo-drafts` branch (see Weekly flow).
- Never invent a number. Every probability, price, average or rank comes from the data below; if something is missing, say so.
- Nobody is watching: no questions; make the call and say what you assumed in one line.
- The final message is read on a phone: short headed sections, each promo as a copy-ready block.

## Owner rules (11/7-11/9) - these override anything below where they conflict
The owner set these in chat after Week 9 and wants every promo, draft and check to follow them. Where a later section disagrees
(e.g. "Market mix" says no floor legs), follow the owner rule and add one line noting the audit fact, so he sees both.
1. LOW-RISK LEGS ONLY. Compute each leg's builder risk score exactly like the builder: sum over the leg's `fh` flags plus `D.pf[pl]`
   flags of bad = 3, watch = 1, good = -1, floored at 0. Score 4+ = "High risk", 2-3 = "Some risk". Leave out every High / Some risk
   leg (owner 11/7: "We need low risk").
2. FORM VS MATCHUP: if a leg fails rule 1 mainly on matchup (a tough-defense flag) but the player's recent form or role is strong
   (e.g. Bucky Irving vs CHI, "playing like a top 3-5 back"), do not drop it silently - list it under "Your call" with both sides.
3. SHORT FAVORITE SLIPS ARE THE CORE: about 4 legs at roughly -300 to -200, landing near +300 (the Week 9 shape that won three times).
   Bigger slips are small-stake extras. Pick legs by matchup, projection and game script, not by edge alone.
   (Owner 11/10, after the site audit pointed out that /how/ said the opposite: "I want the -300/200 slips." The /how/ page now
   describes this format. Keep the one-line audit fact in the draft, as the paragraph above these rules says; do not argue the format or swap it for plus-money legs.)
3a. THE DAILY SWEEP (owner 11/10: "I'd love for us to start 1-3"): ONE house slip per game day is the flagship - the short favorite
   slip of rule 3, posted on the site before the day's first kickoff with its own public record (home page hero; gen/sweep.py).
   Why: the receipts showed 0-37 on the slips we posted in Weeks 6-9 (34 of them +477 or longer) while the short slips that won in
   Week 9 were built in chat and never went on the record. Everything else we post is "side action" on the site, and a slip at +2000
   or longer is tagged "Long shot". Recipe: the **sweep** slot below.
4. OVERS BY DEFAULT, UNDERS WHEN THE CARD SAYS SO: no unders normally, BUT when the game card's "Sweep says" verdict calls for unders
   (e.g. "Unders crowd, assemble", close-and-low script), build that game's slip with unders (owner 11/9: "insist on unders").
5. BACKUP QBs: a backup / spot-start QB for an offense that was already struggling gets no passing overs, and his receivers get no
   yardage or catch overs (owner 11/9 after Carson Wentz's MNF start). Play the other team, the run game or unders instead.
6. EITHER-OR TDs: judge a pair as a pair (team TD outlook + the pair's share of targets / carries), not by each player's own TD history.
   If you like a team's top two targets for yards, one of them scoring is a natural add (e.g. Odunze or Burden).
7. UPSET SLIP: when the public is likely heavy on a favorite, also draft one underdog / shootout slip, ranking legs by the model's
   per-ending chances (`sc`: [a by 10+, close-low, shootout, b by 10+]) instead of the overall %.
8. PREDICTABLE PLAYERS FIRST: prefer players whose projections have landed close and whose props have hit at or above their price.
9. LINK CHECK: screen unders on the FULL market name (`m`, e.g. "Under Receptions"), never the short label, and read every leg back
   from the link by marketId + selectionId before writing it down (11/8: a Golden UNDER slipped into an "overs" slip).
10. SAME-NAME PLAYERS: match injuries / inactives on name + team, never name alone (11/9: a Browns "Justin Jefferson" inactive marked
   the Vikings' Jefferson OUT).

### Judgment checks (owner 11/10: "do all 6") - run on every slip before it goes in the draft
11. ARGUE AGAINST IT: write the strongest case that the slip loses - the one thing that kills it and whether every leg depends on one
   player or one script (Monday 11/9: every slip needed Carson Wentz to play well). If that case has no answer, change the slip.
12. CONSISTENCY: the slip, the card's Sweep says and the model's endings (`sc`, game `probs`) must tell the same story. If they
   disagree, say so in the draft and follow Sweep says (owner 11/10: "I'd roll with sweep says more often").
13. RESPECT LOW CONFIDENCE: model total within 1 point of the line, no ending above ~35%, a backup QB, or a key player questionable =
   a low-confidence game. Shrink the slip (fewer legs) or skip the game; never force the usual +300 out of it.
14. GRADE OUR OWN PICKS: every slip drafted here or built in chat is logged to the sheet tab 'ASSIST - Slip Log' (by the session that
   can write the sheet; draft runs list them in their output) and graded on Tuesday - so we see whether our calls on top of the model
   (form-vs-matchup "your call" legs, script picks) help or hurt.
   Since 11/10 the Tuesday rebuild grades the tab itself (grade_assist.py, RUNBOOK Step 5 0c), so write the Legs cell so it can be read:
   one leg per " | ", FULL player names, the number and the stat every time - "Justin Herbert 175+ pass yds | Trey McBride 6+ rec |
   James Cook 70+ rush yds | Bills ML". Also read: "40+ rec yds", "2+ pass TDs", "90+ rush + rec yds", "Player ATD", "A or B TD",
   "Player U237.5 pass yds", "BUF -7.5", "Over 44.5 (BUF-MIN)". Columns: Date | Week | Game(s) | Slip | Legs | Price | Type | Built by |
   Result | Notes - leave Result EMPTY (the grader only fills empty ones) and put the price as a bare number (305, -120). One row per
   slip: "Same 4 legs + Bears ML" or "Herbert 175+" cannot be graded and stays open for a hand grade.
15. NEWS FIRST: before building, read feeds:news.json, injuries.json and inactives.json for BOTH teams (name + team match) - QB changes,
   coach's decisions and role news move faster than the model.
16. Rules 1-10 every time - no exceptions without saying so in the draft.

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

## Game dossier first (owner 11/5: "how does this team play against similar defenses ... key matchups, injuries on both sides, game script, weather, who's heating up or in the news")
Before drafting any slot, read the game's dossier: `https://betsweep.co/b/dossier.json` (or the clone's out/dossier.json after Step 3), games[<gid>]. For every leg you keep, the draft's "why" must agree with it or say why not:
- similar: how this offense did against its 3 nearest past opponents by defense profile (points, pass, rush vs its season average); prefer players who produced in those games.
- leak: what this defense allows to each role (WR1 / WR2 / TE1 / RB1 / QB1) against those players' own averages; a leg on a role this defense shuts down (vs_own <= 0.9) needs a stated reason.
- flags: weather, defensive injuries, news on both sides. spots: only "lean" spots are tested edges (2006-2025, both decades); "no edge" spots are folklore - never sell a promo on one.
In the owner-facing notes, add one line per game: "Preview: <the one fact that drove the pick>" (owner 11/5: the site calls the dossier "Game preview").

## Leg filter (every promo)
A leg is usable only if ALL hold:
- its game kicks off at least 30 minutes after this run (`ko`), and the player is not Out / Doubtful / Inactive in injuries.json or
  inactives.json, not OUT / HURT / LIMITED in risk-notes.json, and not marked CONFIRMED OUT in `gd`;
- no 'bad' flag on THIS leg (`w` empty; `w` already carries the leg's market-specific matchup and hit-rate flags) and no player-level 'bad'
  flag from `D.pf[pl]` other than matchup ones ('Tough matchup' / 'Matchup' tags describe his headline stat, not every market - a QB's
  'Tough matchup' on passing does not rule out his rushing line); no 'Blowout rest risk', 'Market disagrees' or 'Playing through it' tag;
- every SGP should have at least one leg from each team unless no clean leg exists on one side - say so if it doesn't;
- not Longest Reception; never Rushing Yards (11/4: -19% at every depth, both sides);
- odds +120 or longer for core legs (floors lose: see Market mix); a -130..-200 leg only inside an SGP where the script needs it, never more than one;
- yardage / reception legs: choose the rung where `proj / ln - 1` is between 0.10 and 0.25 (best `e` among them); if none, the rung
  closest to -150;
- weather: no passing / receiving legs in a game whose weather.json row is HIGH risk.

## Building a parlay
- Market mix (owner 11/3 + the 11/4 audit of 4,929 graded legs, Weeks 6-8): FanDuel's heavy favorites are the vig-heaviest legs on the board -
  "floor" legs at -130..-400 hit 5-9 points UNDER their implied chance and lost 9-12% at a unit each, in every market; rushing-yard overs
  lost 19% at every depth and are OFF every promo. The only cut that paid all three weeks: plus-money legs (+150 or longer) where the raw
  model (`pm`) is 5+ points over FanDuel's implied % (`bk`) in receptions, receiving yards, anytime TD or passing yards - 41% hit vs 32%
  implied, +31% at 1u on 150 legs (the builder tags them Model's Best · plus-money edge, `tier: "plus"`). Longer-priced TD scorers paid
  (+8% at +151 and up), TD favorites did not. Passing-yard lines ABOVE the projection hit 63% (+19%); passing floors lost.
  So: core slips are 2-3 legs, built from `tier: "plus"` legs and TD legs at +120 or longer, each leg from a different game unless it is an
  SGP; no floor legs, no rushing yards, no -200-or-shorter anything. A 2-leg slip of two +200 edges prices near +800 and hits ~17% - say
  so; that is the honest "+500" product. Lottery slips (+2000 and up) keep their recipes, built from the same leg pool.
- Singles (new, every slate): the day's 3-5 best `tier: "plus"` legs posted as single plays with the model % and FanDuel's implied %, one
  line of why each. Write them as `singles-<thu|sun|snf|mnf>.json` ([{pl, m, ln, o, p, bk, why}]) on `promo-drafts`, then render the post:
  `python3 desk/singles_poster.py singles-thu.json singles-thu --title "Thursday singles" --week <W> --record "<W-L · units>"` (the record
  comes from the season page's Model's Best "Plus-money edge" row; "new this week" until it has one) and commit the -square.png, -story.png
  and .txt caption next to the JSON. The owner lays his art over the square; the caption is ready to paste. Singles are the product with the record worth posting ("4 of 10 cashed at +190 average"); parlays of 50-60% legs
  cannot build one (the promos went 0-28 in Weeks 6-8).
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

## Weekly flow (owner 11/1: "move schedule to start Wednesday night ... get legs and everything Wednesday so I can start making graphics. If
## Thursday's injuries or anything comes up we can flag it before I post anything")
- **weekly** (Wednesday night): draft EVERY promo for the coming week in one run - a **sweep** (the Daily Sweep, rule 3a) for every game
  day of the week FIRST, then thursday, saturday (Model's Best + SGP of the week), sunday_main, snf, mnf (+500 and Piss Missile Monday) -
  using the slot recipes below. Leg filter applies, except the "kicks off 30+ minutes after
  this run" check is simply "not started". If a game's props are not in the data yet, say "props not posted yet" for that slot (the Saturday
  check fills it). Save the drafts: write `week<W>.md` (the full owner-facing drafts) and `week<W>.json` (per promo: slot, name, legs with
  pl / m / ln / o / p / fd ids, the FanDuel link, price, plus `type` ("+500" / "lottery" / ...), `game` ("CHI-SEA" for SGPs), a ready
  `caption` for the post, and `"post": false`) to the branch `promo-drafts` of joeymccarrick1/betsweep-site
  (`git fetch origin promo-drafts || git checkout --orphan promo-drafts`; only those two files; commit "Promo drafts week W"; push that branch only -
  NEVER main or gen-overrides). This is the ONLY write any promo run may make.
- **Approving a draft** (owner 11/3): the owner flips a draft's `"post"` to `true` (GitHub edit of week<W>.json, or tells a Claude session
  "approve week 9 <name>" - that session may set `post`, and `odds` / `link` to the FanDuel SGP price and shareCode link the owner got,
  on `promo-drafts` only). The next site rebuild runs gen/promo_approve.py, which appends every approved draft not yet on
  'PROMO - Promoted Bets' as a LIVE row (next free slot, legs in the tab's "who | Market N+ | odds" format, caption, notes), so the home
  page, /b/w<W>-<slot> short link and posters appear without retyping. check runs: a draft with `post: true` counts as posted - check it,
  never redraft it. A promo run never sets `post` itself.
- **check_<slot>** runs (check_thursday, check_weekend, check_sunday, check_mnf): read `week<W>.json` from the `promo-drafts` branch (newest W), and
  for every leg of that slot's promos re-run the leg filter against the CURRENT data (injury report, inactives, weather, owner notes, flags,
  started games) and compare the FanDuel price now vs drafted. PRICE DRIFT (owner 11/3): for each leg compute implied % now minus implied %
  when drafted (from `week<W>.json`; `bk` in builder_data.json / `AUTO - Book Odds` is the current FanDuel price). A leg whose price moved
  AGAINST us by 3+ implied points (the market got longer on our side, e.g. -150 -> -115) is a FLAG even with no injury: the market has
  moved away from the leg - swap it for the best clean leg in the same game, or if the whole slip's multiplied price rose 15%+ say so and
  offer the re-priced slip. A leg that moved our way (shorter) is "OK - market came our way" and is a reason to lead the post with it.
  Output per promo: OK, or FLAG with the reason and a ready swap (same game, same script, rung rules) and the new link/price. A slot with no draft (props were not posted on Wednesday): draft it now with its recipe and add it to
  the same files on `promo-drafts`. check_weekend covers saturday + sunday_main + snf + mnf; check_sunday covers sunday_main + snf (inactives);
  check_mnf covers mnf.
- If the owner has already posted a promo (it is in `site/b/promos.json` with Status LIVE), check it the same way but never redraft it - the
  "Promo at risk" push also covers it.

## Slots
Every recipe below is subject to the Market mix rule above (11/4): where a recipe says floor legs, rungs 10-25% under projection, or -250-or-better prices, use `tier: "plus"` legs and +120-or-longer TD legs instead, and keep core slips to 2-3 legs. The recipes still decide WHICH games and WHAT kind of slip.
- **sweep** (THE DAILY SWEEP, rule 3a; `"type": "sweep"`, `"slot": "sweep_thu"` / `"sweep_sun"` / `"sweep_mon"` / `"sweep_sat"` ...): exactly ONE
  per game day (the CT date of the kickoffs: Thursday, Sunday, Monday, plus Saturday / Friday / holiday games when the week has them). It is
  NOT subject to the Market mix rule or the "2-3 legs" line above - the owner rules decide it:
  - Shape (changed 11/10 evening, owner "Get to all of this" on the deep-dive list: "a public record led by the Daily Sweep and 2-3 leg
    slips"): 3 legs by default, each priced about -300 to -200 (a leg at -350 or -180 is fine), FanDuel price about +130 to +250. Why:
    graded over Weeks 6-9, legs in that band hit 65%, so three land together about 27% of the time and four about 18% - the record the
    public sees should be the one that wins more often. Go to 4 legs (+250 to +400, the owner's Week 9 shape) only when all four are legs
    the site shows AT OR ABOVE FanDuel's break-even; drop to 2 on a thin one-game board. Say in the draft which shape it is and why. On a one-game day it is a same-game slip: use FanDuel's own SGP price,
    never the legs multiplied; if it cannot be read, write "price on FanDuel" and give the multiplied figure labelled as an estimate - the
    owner types the real price in `odds` when he approves. On a multi-game day take the day's four best legs, at most two from one game.
  - Every leg: builder risk score 0-1 (rule 1 - no "Some risk", no "High risk"), passes the Leg filter, an over unless that game's
    Sweep says calls for unders (rule 4), no backup-QB dependency (rule 5), agrees with the game's most likely endings and its Sweep says
    (rule 12), predictable players first (rule 8). No two legs that need the same team to win big, and no more than two legs on one team.
    Skip a low-confidence game (rule 13) rather than force it - on a one-game day with a low-confidence game, shrink to 3 legs and say so.
  - Run judgment checks 11-16 and put the "argue against it" line in the draft.
  - Name: "Daily Sweep: <short name>". The name after the colon is the owner's to change; the words "Daily Sweep" must stay at the start of
    the title - the site, the record and the receipt find the slip by them (promo_approve.py adds them to a `type: "sweep"` draft that lacks them).
  - Caption: two or three plain sentences, one reason per leg. No "lock", no "free money".
  - The record is the record: once a Sweep is on 'PROMO - Promoted Bets' it is never edited, re-priced, renamed or replaced, and none is
    ever added after its first kickoff. Before it is posted, a check run that flags a leg swaps it in the draft; after it is posted, the
    check run reports the flag to the owner and leaves the row alone. Never draft a second Sweep for a day that already has one (in the
    drafts with `post: true`, or on the tab). If a game day has no clean four legs, draft none and say why - a day without a Sweep is
    better than a forced one.
  - Getting it on the site: an approved draft goes up with the next site rebuild (Thu 7:40 AM / 3:40 PM, Sat 7:40 AM, Sun 7:40 / 9:52 AM /
    12:40 PM CT). There is no Monday rebuild: Monday's Sweep has to be approved before Sunday's last rebuild, or the owner posts it in chat.
- **thursday** (TNF): (a) single best bet: the one leg with the highest `e` among legs at -150..+150 with `p >= 0.5`; (b) +500 (target
  +400..+650, 3-4 legs, highest chance); (c) +5000 lottery, titled **Thursday Night Thievery** (owner 11/10; the Thursday twin of Piss Missile Monday) (+3500..+7000, a story-driven same-game build - TDs + overs that need the same
  game script; 4-6 legs, label LOTTERY).
- **friday** (fantasy, no bets): 3 flex calls from players in this week's Sunday games - pairs at the same position within 2 points of
  projection where one is clearly better on matchup rank, volume trend or flags; write each as "Start A over B: reason", using the logic of
  /team/compare/ (site/team/compare/data.json has projections, last-4 games, flags). Plus a "weekend watch" line: any HIGH weather game and
  notable Questionable players.
- **saturday** (early Sunday card): "Model's Best" 3 legs from 3 different Sunday games using legs with a `tier`, a themed name; plus the SGP of the week (below).
- **sunday_main** (posted ~10:30 AM after inactives): (1) Favorite TDs: 3-4 Anytime TD legs, different games, `p >= 0.40`, price +200 or
  shorter, highest `p`; (2) Either/Or TDs: 5-6 of the most confident games, for each the two likeliest scorers (FanDuel's "Either TD"
  market is not in the data - list the pairs and say to build it in FanDuel's Either-player market); (3) Sweep: best single leg from the 5
  games with the most usable legs at `p >= 0.62`; (4) Best legs: 3-4 legs with the highest `p` at -200 or longer. Then mark which one to boost.
- **sunday_late**: one 3-4 leg parlay from the 3:05 / 3:25 PM games only.
- **snf**: the night game's +500 (3-4 legs) and +5000 lottery as on Thursday.
- **mnf**: the +500 (3-4 legs) and **PISS MISSILE MONDAY** - always that name, BetSweep's most popular bet. Model it on the one that hit
  (Bills @ Rams, 10-leg SGP, +6781 base / +10174 with a 50% profit boost: James Cook 60+ rush yds, Davante Adams 50+ rec yds, Josh Allen 200+
  pass yds, Josh Allen ATD, Kyren Williams ATD, Puka Nacua ATD, Josh Allen 25+ rush yds, Puka Nacua 100+ rec yds, Matthew Stafford 300+ pass yds,
  James Cook ATD). The story is a shootout where BOTH offenses go off: both QBs' passing yards, a mobile QB's rushing line, each RB1's rushing yards,
  each WR1's receiving yards, and anytime TDs for the stars. 7-10 legs, target +5000 to +10000 before any boost; every leg must fit the same
  shootout script (no unders, no leg that needs a blowout). That slip only cashed because the game went to overtime - so prefer the lower rungs of
  each ladder (rungs 10-25% under projection) and the likeliest TD scorers, and keep the final price nearer +5000 than +10000 when it's close. Still
  apply the leg filter (injuries, weather, flags). Suggest the 50% profit boost on it if one is available. This is a lottery promo: it is exempt from
  the 3-5 leg rule and counts in the lottery record. Script check: `D.games[gid].probs` = model chances of [away by 10+, close & low-scoring,
  shootout, home by 10+]. Build the both-offenses shootout version when shootout >= 20% or the total `tot` >= 48; otherwise build it around the
  model's most likely ending (`most`), e.g. "SEA by 10+": the leading team's QB yards + WR1 yards and TD + RB1 rushing yards and TD, plus the
  trailing QB's rushing - and say which script the slip needs in the post.
- **SGP of the week** (in the saturday run, owner 11/1): one lottery same-game parlay from the Sunday game with the highest scoring potential -
  rank Sunday games by shootout chance (`probs[2]`) then total (`tot`); take the top game. 6-8 legs that all need the same script (the shootout, or
  that game's most likely ending if shootout < 20%), target +3000 to +10000 (FanDuel's SGP price will be lower than the legs multiplied - say so),
  leg filter applies, rungs 10-25% under projection, likeliest TD scorers. Name it, label LOTTERY, give the script in one line and the model's
  chance (product of BetSweep % = the independent floor; same-game correlation makes it higher).
- **tuesday** (receipt): no bets. Read `site/receipts/` (newest week page) and the promo grades it shows, plus `site/b/promos.json`; write
  the receipt post (core record vs lottery record, best hit, toughest miss with its "why it lost" line if the receipt shows one) and a
  60-second video script. If last week is not graded yet, say so and stop.

## Output (final message)
For each promo: `NAME - price (chance %)`, the legs (player, line, odds, BetSweep %), one-line why per leg, the FanDuel link, then an X
post and an Instagram caption from the templates in the playbook (end with "21+ | gamble responsibly"). Thursday / Sunday main / prime-time
runs add a 4-line Reel/TikTok script (hook, the slip, the one stat, the call to action). Finish with "Assumed:" (one line) and
"Skipped:" (legs dropped for injury / weather / flags, one line).


## Similar defenses (owner 11/6)
Every builder leg on a player's main stat carries `sd` = [split vs his 3 most similar past opponents, avg in those games, season avg, opponents, games above average]. When choosing a best bet or the legs of a promo, among legs that already pass this desk's leg filter and parlay rules, prefer the leg with the higher split (and 3/3 consistency); say the split in the write-up ("averaged 62 rec yds against defenses like Baltimore's"). Never use it to let in a leg the filter rejects.
