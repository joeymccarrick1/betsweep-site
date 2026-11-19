# BetSweep rebuild runbook

You are rebuilding the BetSweep site and boards for the NFL fantasy/betting model in the Google Sheet "Fantasy Projection Model 2026" (spreadsheet ID 1Tmt5vp--RhvErt6ZGm6vIje7hcrf-aFXovpRrUjENI8). Nobody is watching; work unattended, never invent data, never guess at a missing stat, and verify every write you make. Everything you need is self-contained: the generator bundle lives inside the boards artifact itself (this file is gen/RUNBOOK.md in that bundle).

## OUTPUTS
All exist already; always update in place, never create new ones except the weekly receipt on Tuesdays.
- Public site: https://betsweep.co, deployed by GitHub Pages from the repo joeymccarrick1/betsweep-site (branch main, root). This is the primary output. Pages: / (landing page), /boards/ (matchup boards), /build/ (parlay builder + img/preview.png), /team/ (Fantasy - formerly My Team: Sleeper league import or hand-built roster, graded by the model; /fantasy/ is a redirect to it), /firsttd/ (First Touchdown Scorer: the model's first-TD probability per player, fair odds, FanDuel price and edge), /dfs/ (DFS lineup builder: DraftKings/FanDuel player-list import, classic and single-game MVP/Captain contests, model projections in site scoring, cap optimizer), /receipts/ (index), /receipts/week<W>/, /season/. The repo also holds a posts/ folder the owner uploads pictures into by hand; the landing page shows the newest six. build_site.py generates every page, the site-wide menu, og.png (link preview), wordmark.png / wordmark-ink.png and favicon.png.
- claude.ai artifacts (boards RTTqiN3sdMHGgojimQ9hZv, builder FQVqm3BhG4BfMPd63tRQRa, Fantasy EbpLXvGQWy6MoybbFsjxNY, First TD EKtgfWz91Q8ckuPuxfmak4, DFS W4L5R482imAeJhDxUHDMPF, season A7tt7rCuMgVvwSqBm9A7Pv): archives since 11/5 - not refreshed, not read (Step 7 retired; the generators come from git in Step 1).
- Weekly receipts: built on Tuesdays into /receipts/week<W-1>/ on the site (see step 5) and logged in the sheet tab 'AUTO - Boards Archive' with that URL.
- Sheet tab 'AUTO - Snap Trends' (model input: snap-share trends from nflverse; the projection tabs read its column J). Refreshed every run in step 2b.

## STEP 1 — Get the generators (one git clone; changed 11/5)
`git clone -q --depth 1 --branch gen-overrides https://github.com/joeymccarrick1/betsweep-site.git gen && cd gen` - that folder is your work folder: every generator script, template.html, assets/ (self-hosted fonts + html2canvas), this RUNBOOK, PROMO_DESK.md, push/ (reference copies of the Supabase function and SQL - not run) and research/. Print "generators: gen-overrides <short sha>" (`git rev-parse --short HEAD`). Nothing is fetched from the claude.ai artifact any more: the bundle at https://claude.ai/artifact/RTTqiN3sdMHGgojimQ9hZv is an archive (its gen/ copies stop at 11/5), and Step 1a (overrides on top of the bundle) is gone because the branch is the source. If the clone fails, retry once after 30 seconds; if it still fails, write the dev-log row saying so and stop - do not build from an older copy.

## STEP 2 — Sheets read for all inputs
Mirror first (11/3, owner: "the rebuild is expensive for what changes"): `git clone -q --depth 1 --branch sheet-mirror https://github.com/joeymccarrick1/betsweep-site.git sm` (the site repo's .github/sheets_pull.py pushes the ranges below as in/*.json + games.csv every 30 minutes once the owner's SHEETS_SA_JSON secret exists). If the clone succeeds and sm/in/MIRROR.json's "pulled" stamp is under 25 minutes old: `cp sm/in/*.json sm/in/games.csv in/`, print the stamp in the summary ("inputs from sheet-mirror <stamp>") and SKIP the three connector calls below - go straight to the weather paragraph. Tabs this run writes to and re-reads later (Weekly Availability, Game Weather, Boards Archive, PROMO - Promoted Bets, Snap Trends) are still re-read with get_values after the write as their steps say. If the stamp is stale (GitHub runs the 5,35 schedule only about once an hour under load - the 11/5 morning rebuild found a 77-minute-old pull), refresh it yourself first: in the site clone (Step 6a; the repo is attached, so `gh` is signed in) run `gh workflow run sheet-mirror.yml --ref main`, wait 60 seconds, then poll `gh run list --workflow=sheet-mirror.yml --limit 1` every 30 seconds until it shows "completed success" (normally 2-3 minutes; give up after 6), delete sm/ and clone the branch again - the stamp is now minutes old, so copy and skip the connector calls. Only if the branch is missing, `gh` is refused, or the run does not complete, read through the connector as before and say "mirror stale/missing" in the summary.
Call mcp__Google_Sheets__get_spreadsheet with includeGridData=true, fields=["sheets.properties.title","sheets.data.startRow","sheets.data.startColumn","sheets.data.rowData.values.formattedValue"], and these ranges, split into THREE calls because one call is too large for the connector:
- (call A) 'AUTO - QB Projections'!A1:AS300, 'AUTO - RB Projections'!A1:BD300, 'AUTO - WR Projections'!A1:AV300, 'AUTO - TE Projections'!A1:AR250
- (call B) 'V2 - Leg Board'!A4:R1604, 'AUTO - First TD Odds'!A1:L1200, 'AUTO - FanDuel Links'!A1:J6000, 'AUTO - FanDuel Game Lines'!A1:K8000 (the tab passed 3,500 rows by Week 9 - a 3000-row read dropped the latest pulls; grow this with the tab)
- (call C) '2026 Matchup Boards'!A1:Q560, 'AUTO - Defensive Stat Matchup Ranks'!A1:P68, 'AUTO - Game Weather'!A3:P40, 'AUTO - Weekly Availability'!A1:M300, 'V2 - Game Scripts'!A4:K20, 'V2 - Best Legs'!A6:K60, 'AUTO - Script Multipliers'!A1:H23, 'AUTO - Boards Archive'!A1:F60, 'V2 - Boards Results Feed'!A1:AG1200, 'V2 - Boards Results Feed'!AJ1:BK3000 (the whole tab, 3,000 rows: Week 6 alone had 1,698 graded legs, so a 1500-row read silently truncated the receipt's leg tiles), 'V2 - Weekly Scorecard'!A1:K200, 'V2 - FanDuel Leg Snapshots'!A1:AB20000 (the whole tab - at ~1,700 frozen legs a week a 6000-row read would have silently dropped legs from the season page and home track record from about Week 9; if the snapshot tasks grow the tab past 20,000 rows, grow this range with it, and if the connector says the call is too large give this range its own call), 'AUTO - SGP Correlations'!A1:C80, 'AUTO - Game Day Status'!A1:F200, 'AUTO - Player Game Log'!A1:X6000, 'AUTO - Kicker Projections'!A1:P100, 'AUTO - DST Projections'!A1:M50, 'V1 - Eligible Fantasy Projections'!A1:I650, 'AUTO - Snap Trends'!A1:J700, 'V2 - First TD Board'!A3:P700, 'AUTO - Settings'!A1:B300, 'AUTO - Model Calls Archive'!A1:AQ2000, 'PROMO - Promoted Bets'!A1:N100, 'AUTO - Book Odds'!A1:L15000 (the whole tab - 7,600+ prop rows plus the gl| game-line rows on 10/22, so a 6000-row read would silently drop the later games and the game lines; DraftKings + Hard Rock rungs written by FanDuelOdds.gs v2026-10-22; if missing write in/bookodds.json as {"values": []} and the builder simply shows no other-book prices), 'AUTO - Market Values'!A1:J1000 (FantasyCalc values written by the sheet's MarketValues.gs; if the tab is missing or empty, write in/market.json as {"values": []} and the trade calculator builds unblended), 'AUTO - WR CB Matchups'!A1:AT2500 (Mike Clay / ESPN WR-CB cheatsheet rows the owner loads each week - Week 7 from screenshots on 10/21; flags.py reads the current week's rows for the Coverage flag; if missing write in/wrcb.json as {"values": []} and no coverage flags are produced), 'AUTO - FanDuel Unders'!A1:L1500 (FanDuel main-line unders written by FanDuelOdds.gs v2026-10-27; build_builder.py prices them; if missing write in/unders.json as {"values": []}), 'V2 - Unders Snapshots'!A1:L20000 (in/undersnaps.json; add "V2 - Unders Snapshots": "undersnaps.json" to prep.py's BY_TITLE if the bundle's prep.py lacks it - write the file by hand from the range result; if the tab is empty write {"values": [[]]}), 'V2 - Model Best Picks'!A1:O20000 (in/bestpicks.json via prep.py; columns M-O DK / HR / consensus implied % since 11/3; 7,200+ rows by Week 9 - the tier is frozen before every kickoff, so a 6000-row read silently dropped Week 8's later freezes from the Model's Best grades; grow with the tab), 'V2 - Closing Lines'!A1:J20000 (FanDuel's last pre-kickoff price per week + line, kept by the sheet's ClosingLines.gs every 30 min - copy at gen/ClosingLines.gs.txt; build_season.py's CLV card; if missing write in/closing.json as {"values": []}), 'AUTO - Market Team Points'!A1:Z33 (FanDuel-implied team points that feed 'V2 - Game Scripts'; confidence.py reads the formula column; if missing write in/teammkt.json as {"values": []}), 'AUTO - Confidence Archive'!A1:R3000 (game confidence grades frozen before kickoff, appended in step 2c; graded on the season page; if the tab is empty or missing write in/confarc.json as {"values": []}), 'AUTO - DK Salaries'!A1:L1500 (DraftKings main-slate player list written every 3 hours by the sheet's DKSalaries.gs - copy at gen/DKSalaries.gs.txt; build_dfs.py builds it into the DFS page so DraftKings salaries load with no import; if the tab is missing or empty write in/dksal.json as {"values": []} and the DFS page simply asks for a file as before)

If a call still reports the message is too large, split it further; prep assigns files by sheet title, so order does not matter. Each result is written to a file on disk; note the paths. Run python3 prep.py <file> on each — it writes in/*.json by sheet title (the two Results Feed ranges are split by startColumn) and downloads the nflverse schedule to in/games.csv (https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv; if the download fails, retry once with curl, then stop and report). Confirm prep printed a row count for every range across the three runs; a missing file means a range or tab name is wrong — stop and report rather than building from partial data (links.json, ftdodds.json or gamelines.json having only its header row is fine - the parlay builder then prices moneyline/spread/total legs off the nflverse consensus line instead of FanDuel; rows with Market 'Alt Spread' / 'Alt Total' are FanDuel's alternate lines and feed the builder's 'Alt game lines' panel: it just means FanDuel betslip IDs / first-TD prices have not been pulled this week).

Weather (added 11/1, every run, after prep): the sheet's 'AUTO - Game Weather' rows were pairing last week's venues with this week's matchups (Week 8 read ATL-TB as a roofed game in Atlanta), so flags.py dropped most games' forecasts. In the site clone run `git fetch -q origin feeds`, then `python3 weather_feed.py <clone> <WEEK>`. On "weather feed: N games ..." it has replaced in/weather.json; then mcp__Google_Sheets__batch_clear_values 'AUTO - Game Weather'!A4:P40 and update_values with out/weather_values.json, so the sheet matches. On "kept the sheet's weather" carry on and say so in the summary. Never edit rows 1-3 of that tab.

## STEP 2a — Trades and injuries (every run, before building)
The projection tabs take each player's team from his most recent game log, so a traded player stays on his old team until he plays for the new one. Check for trades every run: download https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_2026.csv, take the rows for the current week with status ACT and position QB/RB/WR/TE, and compare each model player's team (column B of the four projection tabs, in/proj_*.json) with the roster team (LAR = LA). For every ACT player whose roster team differs from the model team, confirm the trade/signing with one web search, then append a row to the sheet tab 'AUTO - Team Overrides' (Player | New Team | Effective Week | Source | Note | Added) — the Team column in all four projection tabs reads that tab first (row must use the model's exact player name). Ignore DEV/practice-squad and CUT rows (they are not model starters). Then refresh injuries: download https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv (current week rows) and the official reports/news; in 'AUTO - Weekly Availability' set E = OUT only for players officially ruled out, on IR/PUP/reserve, or listed Out/Doubtful on the final report; set E = QUESTIONABLE for Questionable designations and for DNP players without a designation yet; name the source and date in K/L and the practice status in M; keep the model's exact player name in B and his model team in C (a row with the wrong team does not match). Never invent a status. A row whose J starts with "OWNER" is the owner's own call - read the OWNER rule in Step 2a-ii before touching it (only an official designation or a completed roster move replaces it, never a report). Replacement starters: when a starting QB is ruled out and the man who will start has NO 2026 game log (he is not on 'AUTO - QB Projections'), add one more Weekly Availability row for him: B his name as FanDuel spells it, C team, D QB, E CLEARED, G = STARTER, H = the ruled-out starter's name, J a one-line reason with the source - the site then shows him on the team's fill-in QB projection, flagged FILL-IN STARTER, and prices his FanDuel lines with a risk flag (fillin.py). If you added overrides or availability rows, wait 30 seconds and re-read the projection tabs, Leg Board, First TD Board and Weekly Availability (prep.py on each) before Step 3.

Availability reach check (11/10): after the injury refresh and the trade check run `python3 avail_check.py` (needs in/avail.json and in/proj_*.json as just read). The four projection tabs read a status with week + NAME + TEAM + POSITION together (QB!AD, RB!AB, WR!Z, TE!X) - that is what keeps two players who share a name apart - so a row whose team or position is not what the projection tab has for the player (a trade the game log has not caught up with, LAR for LA, a tight end entered as WR) matches nothing, and the player projects as healthy with no warning. The script prints "IGNORED BY THE SHEET: <player> (<team> <pos>) <status> - the projection tab has him as ..." for each such row: fix that row in 'AUTO - Weekly Availability' (the team code and position exactly as his projection tab has them), re-read the tab into in/avail.json and run it again until it ends "..., 0 ignored". Players on no projection tab are listed on their own line and need nothing. `python3 avail_check.py --selftest` covers the cases. On 11/10 all 84 Week 10 rows reached the model.

Owner notes (added 11/1): after the injury refresh, read the owner's player-page notes. In the site clone (Step 6a) run `git pull -q origin main`, then `python3 risk_notes.py <clone>/data/risk-notes.json <WEEK>` (prints "risk notes: N this week ..."). It writes in/risk_notes.json (flags.py turns HURT / LIMITED into a 'bad' flag, STARTING / ROLE_UP into a 'good' flag) and out/risk_notes_avail.json: the 'AUTO - Weekly Availability' rows to add. Append each row; if that player already has a row for this week, change only its E (to OUT) and J/K instead of appending. An official Out always stands; a note never clears an official status. If data/risk-notes.json is missing or empty, print "risk notes: none" and carry on. Count these rows in the "wait 30 seconds and re-read" rule above.

## STEP 2a-ii — Context desk (added 11/4, every run, right after the injury refresh and the owner notes, BEFORE Step 2b)
The owner (11/4): "I wish you'd take news into account when making projections" (Emanuel Wilson stayed the model's RB1 after Charbonnet and Price came back). Seven scripts read the public `feeds` branch of the site repo (.github/feeds.py mirrors ESPN/RotoWire/CBS/Yahoo/PFT news, ESPN team injury pages, ESPN depth charts, Sleeper + ESPN projections, in-game box scores) plus nflverse, and write `in/ctx_*.json` (flags.py reads every one: player notes become flags on his legs and player page, game notes go on the game card's collapsible "Context" line) and PROPOSED availability rows. Run them in this order; each prints a one-line summary for the run log. None of them writes to the sheet - you do, with judgment, per the rules below. The sandbox cannot reach raw.githubusercontent.com, so each script falls back to `git fetch origin feeds` in /home/claude/betsweep-site (the Step 6 clone must exist first - clone it before this step if it does not).
1. `python3 news_desk.py <WEEK>` - player news -> flags (News: out / limited / role up / role down / back / trade; Trending), `out/news_rows.json` = proposed 'AUTO - Weekly Availability' rows, `in/trending.json`, `out/trending_w<W>.json`.
2. `python3 depth_check.py <WEEK>` - ESPN depth charts vs the model's roles -> flags (Depth chart: demoted / promoted / starter), `out/depth_rows.json` = proposed Forced Role rows.
3. `python3 def_inj.py <WEEK>` - defenders on the injury report vs Clay's primary corners -> the receiver's Coverage flag becomes "Corner out" (good) / "Corner questionable" (watch); defensive report lines on the game card.
4. `python3 stakes.py <WEEK>` - standings, division game, short week / off a bye, primetime, body clock, neutral site, indoors, referee crew (when nflverse has the assignment) -> game card context; from Week 16 "Resting risk" when a team has clinched.
5. `python3 role_rising.py <WEEK>` - nflverse snap shares: "Role rising" / "Role up" (good) and "Snaps falling" (watch) for RB/WR/TE.
6. `python3 consensus.py <WEEK>` - model vs Sleeper + ESPN projections -> "Model disagrees with consensus" (watch, we are far below) / "Model above consensus" (info); `out/consensus_w<W>.json` kept on the site for the Tuesday grade.
Applying the proposed rows (news_rows.json, depth_rows.json) to 'AUTO - Weekly Availability' (append at the first empty row; same 13 columns; "wait 30 seconds and re-read" rule applies):
- An OFFICIAL status always wins: if the player already has a row this week with E filled, do not touch E. If his row exists with E empty, only fill G (Forced Role) when the proposal is a Forced Role and G is empty.
- (audit 11/10) A row whose reason (J) starts with "NEWS DESK:" is the desk's own earlier read, not an official status. When a later proposal for the same player is MORE severe (QUESTIONABLE -> OUT), overwrite E, J, K, L on that row with the new proposal and say so in the run log - Josh Jacobs sat at QUESTIONABLE ("exits game with hand injury") a day after "needs surgery on fractured finger, out up to 3 weeks"; the old rule ("E filled, do not touch") kept him there. Never downgrade this way (OUT -> QUESTIONABLE needs an official report or the owner), and a row that says the hold is deliberate ("IR not yet official - entered QUESTIONABLE until the team confirms") moves only when the new headline is that confirmation or a stated absence ("will miss several weeks").
- (audit 11/10) What news_desk.py does by itself since 11/10, so you do not have to catch it by eye: weekly statuses and role plans published before the team's last kickoff are dropped (they were about a game already played - on the Tuesday 11/10 morning build "won't play in Week 9" items became 15 proposed rows and 28 flags for Week 10; it prints how many it dropped); an in-game exit from the game just played is a "News: left last game" watch flag, never OUT; ESPN team-report lines use ESPN's own status (an IR player "hopeful to return" is OUT, not "back / practising"); "activated off injured reserve", "attorneys released a statement", "inactive lists released", "released then re-signed" are not absences; "week-to-week" from before the last game proposes QUESTIONABLE, not OUT. `python3 news_desk.py --selftest` runs those wording cases (16/16) - run it after any edit to the buckets. A proposal that still quotes last week's game is a bug: skip the row and put the headline in the run log.
- (owner 11/10: "Jacobs, Puka, Stevenson are all questionable") A row whose reason (J) starts with "OWNER" is the owner's own call. Never change its E, J or K from a news or depth proposal, whatever the headline says; news_desk.py reads these rows, proposes nothing against them, puts the owner's status on the player's news flag and prints "owner status held - <player> stays <status>" - copy those lines into the run log. Only an OFFICIAL status replaces an owner row: the team's own game-status designation on the final injury report (Step 2a's nflverse refresh), the inactives list, or a completed roster move (the player's nflverse roster status for the week is RES / reserve, i.e. he IS on injured reserve - "expected to", "likely to" or "will miss" from a reporter is not official, and neither is ESPN's own Out / Doubtful tag before the final report). Then write the official status, keep the owner's text at the end of J ("was OWNER 11/10: questionable"), and say so in the summary so he sees it. When the owner gives a status in chat, write it this way: E = his status, J = "OWNER <date>: <status>. <what the reports say, with the source>", K = "owner in chat <date time>".
- OUT only from "ruled out / placed on IR / season-ending / suspended" wording (news_desk already restricts it) - read the quoted headline; if it is about LAST week's game ("rest of Sunday's game") or about a different player with the same surname, skip it.
- QUESTIONABLE rows: append when the tab has no row for him; put the practice word in M. These are what Step 2a's nflverse refresh would add on Friday anyway - this just gets them in on Wednesday/Thursday.
- Forced Role rows from depth_check: append when he has no Forced Role and no OUT this week. Never set OUT from a depth chart (the owner's role-loss call is his - 11/4 Wilson is the precedent: healthy but zero role -> OUT with "role loss, not an injury" in J).
- QB1 proposals: confirm the team's current QB1 row is not contradicting it (two QB1s for one team = read the news again; the later-dated item wins).
- Every row you append cites the script's source text (J = "NEWS DESK: <headline>" / "DEPTH CHART: ..."; K = source + link). Count the rows in the summary ("context desk: N news rows, M depth rows, trending top: ...").
- (11/17) The official report beats a desk row. After the rows above are applied and the tab is re-read into in/avail.json, run `python3 availfix.py`. For every "NEWS DESK:" row that still says QUESTIONABLE it reads the team's official report (nflverse injuries) and prints `[availfix] <player> (<team>) QUESTIONABLE -> CLEARED: ...` (no game status on the final report, or not on the report at all) or `-> OUT: ...` (Out / Doubtful on the final report). It corrects in/avail.json itself and writes out/avail_fixes.json: write each item of its "updates" to the sheet with update_values (the range is E:L of that row; the nulls leave F:I and K as they are), re-read the tab, and run it again - it should end "0 corrected". A `held:` line is a player who is off the report but may be on injured reserve (the roster or ESPN says so, or neither could be read): read the news for him and set OUT, or leave the row. It never touches an OWNER row, a row the injury refresh wrote, or an OUT. Put "availfix: N corrected (names), M held" in the summary. The hourly rebuild runs the same correction on its own copy every time, so the site is right even before a session fixes the sheet.
Then re-read 'AUTO - Weekly Availability'!A1:M440 -> prep.py (avail.json) so the builds see the new rows. The summary's Step 2 line gets: "context desk: news X notes / Y rows applied; depth Z rows; corners affected N; consensus below/above a/b".
Tuesday (after grading, with the other Step 5 checks): `python3 context_grade.py <GRADED WEEK>` -> research/context_grade_w<W>.txt: (1) consensus disagreements - who was closer, by side and stat; (2) trending top-20 fade test (hit vs implied). Put the block in the dev-log row. Rules: "Trending" becomes a watch flag + under-side nudge only after two graded weeks of trending legs 3+ pts under implied; "below consensus" losing two weeks running means our under-projections are stale inputs -> look at what the news desk missed, do not change the projection formulas from this.

## STEP 2b — Refresh snap-share trends
The model's snap-decline adjustment reads this tab. Run: python3 build_snaps.py → "wrote out/snaps_values.json: N rows for week W (D SNAPS DOWN, U SNAPS UP); matched to model names: M" (N is normally 350–450; if the nflverse download fails and there is no cached file the script exits with an error — then skip this step, keep the tab as it is, and say so in the summary). Then: (i) mcp__Google_Sheets__batch_clear_values on 'AUTO - Snap Trends'!A2:I700 (ONLY columns A–I; never touch J2, which holds the factor ARRAYFORMULA, nor J:L otherwise); (ii) update_values with the "range" and "values" from out/snaps_values.json, then update_values with the "range" ('AUTO - Snap Trends'!M2:M700) and "values" from out/snaps_return.json (column M = RETURN for first-games-back players; the J factor multiplies them by 'AUTO - Settings'!B278 - write the whole M2:M700 so last week's markers are cleared; the script also prints "first games back (column M = RETURN ...): N players: names" - put N and the names in the summary); (iii) read out/snaps_meta.txt and write K2 = the week number and L2 = the L2 text; (iv) read back 'AUTO - Snap Trends'!A2:J12 and confirm column J shows numbers (1 or a factor below 1), not errors. STRENGTH OF SCHEDULE (2026-10-29, every run, right after the snap tab): python3 build_sos.py -> "sheet one-sided weights found for 5 of 5 stats ..." then "wrote out/sos_values.json: N players for week W; multipliers a-b (mean m); below 0.95: x, above 1.05: y" (N ~ 500, mean 0.97-1.00; if the first line says WARNING the 'AUTO - Settings' matchup-weight labels moved - stop and report, do not write the tab; it needs in/gamelog.json, in/settings.json and the four in/proj_*.json from Step 2, and downloads in/stats_player_week_2025.csv once). Then (v) mcp__Google_Sheets__batch_clear_values on 'AUTO - SOS Adjust'!A2:W700 (never row 1), (vi) update_values with the "range" and "values" from out/sos_values.json (split into two calls of ~250 rows if the connector refuses the size), (vii) read back 'AUTO - SOS Adjust'!A2:I6 and confirm columns F:I are numbers near 1. 'V2 - Leg Board'!H multiplies every yards / receptions / longest-reception projection by the player's column (z_s; Anytime TD untouched), so the Leg Board re-read below picks the new numbers up; build_boards.py applies the same multipliers to the stat chips from out/sos_values.json, which is why build_sos.py must run before Step 3 (if it did not run, the chips simply show the unadjusted numbers and the legs are still right). Wait 30 seconds for the projection tabs to recalculate, then re-read with get_spreadsheet (same fields; split as needed) only these ranges and run python3 prep.py on each result (it overwrites just those inputs): '2026 Matchup Boards'!A1:Q560, 'V2 - Game Scripts'!A4:K20, 'V2 - Leg Board'!A4:R1604, 'V2 - Best Legs'!A6:K60, 'AUTO - QB Projections'!A1:AS300, 'AUTO - RB Projections'!A1:BD300, 'AUTO - WR Projections'!A1:AV300, 'AUTO - TE Projections'!A1:AR250, 'AUTO - Snap Trends'!A1:M700, 'V2 - First TD Board'!A3:P700.

## STEP 3 — Build the pages, in this order
1. python3 build_firsttd.py FIRST ("cross-check vs 'V2 - First TD Board': M matched, max |diff| = X pts" then "wrote .../out/firsttd.html: P players, G games, week W, F with FanDuel prices, B with betslip IDs"; P is normally 230–300; if it prints the WARN line about the site and Sheet disagreeing by more than 0.5 pts, still publish but say so in the summary — it also writes out/firsttd_top.json and out/firsttd_all.json, which the boards, the parlay builder's First TD legs and the DFS page read).
1v. VOICE - "Sweep says" (owner 11/4: personality on the cards). Before build_boards, write out/voice.json yourself (no script writes it): {"week": W, "built": "<iso>", "games": {"<gid>": "<one line>"}, "legs": {"<Player>|<Market>|<Line>": "<one line>"}, "picks": {"<gid>": "<Player>|<Market>|<Line>"}}. PICKS (owner 11/10, Sweep says share cards): for every game line, name the ONE leg that best backs it - LOW RISK (builder risk score under 2), agreeing with the line (an unders call gets an under leg; a backup-QB game never gets that QB's or his receivers' overs), keyed exactly like the builder (Player|Market|Line, e.g. "Josh Allen|Under Passing Yards|237.5"). build_boards.py puts it on the card's "Share this take" button, and since 11/10 evening it puts NOTHING else there (owner, looking at "41.5 is fair - play Skattebo catching passes" shared with "J.J. McCarthy 175+ passing yards": "You're saying play skattebo catching passes and then share a different leg. I like mccarthy passing but that's not what sweep says"). The old fall-back to the game's safest leg is gone: a pick that is missing, is not a leg on that game's board (the boards carry over rungs only - no player unders yet), has no price, belongs to a player who is out or questionable, is not low risk, or is not a player the line itself tells the reader to play, leaves the card with the line alone. So write them together, PICK FIRST: (a) choose the leg - on the board, low risk; (b) write the line around it; (c) the line may tell the reader to play, take, bet or back a player ONLY when that exact leg is the pick. When the leg the model likes is flagged (Skattebo, Week 10: model 73% against FanDuel's 65% on 5+ receiving yards, but snaps down, Singletary rising, Harris back, limited in practice - risk score 9), the line may describe the edge next to its flags; it must not say play it. OWNER OK: voice.json "owner_ok": ["<Player>", ...] lets a named player's leg ride on the card despite its risk score - only for players the owner has cleared in his own words, never for a player who is out or questionable. Week 10: "Cam Skattebo" (owner 11/10: "Skattebo's the unquestioned guy in that room ... He was injured last game but if he's back he'll be full go" - so "play Skattebo catching passes" may stand with Cam Skattebo|Receiving Yards|5 as its pick IF he is active Thursday; drop both if he is ruled out). Clear the list each new week. After Step 2, build_boards.py prints "sweep cards: N lines, K carry their leg, M have no pick" and, for every refused pick, "PICK REFUSED (fix the pick or the line, then run this script again): <gid>: <why>" - fix voice.json for each game it names (another low-risk leg and a line that matches it, or a line that only describes) and run build_boards.py once more; a game left on that list goes in the summary. LEANS (owner 11/10, "I'd roll with sweep says more often" - Sweep says called the under while the same card's best parlay printed the over): next to the lines, write down what each line tells a bettor to do - "leans": {"<gid>": {"total": "under" | "over", "side": "<TEAM>"}} - `total` when the line calls the under or the over, `side` when it backs a team to win or cover (team code as in the gid). Leave out the part a line does not call, and leave the game out when its line describes rather than calls (most lines do; "A 42.5 total might be generous" is an under, "Lions -2.5, 51.5, long flight" is nothing). Never write a lean the line does not say, and keep line, lean and pick in step (an unders line: total under, an under pick). build_boards.py then keeps that card's best parlay from fighting the line and prints "sweep leans: N games with a lean on record; best parlay changed in K ..." (see "Sweep says leads" below). One line per game (every game on the slate; <= 140 characters, plain text, no emoji, no hashtags) and one line for each of the top 5 plus-money looks (the Model's Best plus tier, by edge). Voice: the sharp friend in the group chat - mid-30s, funny, quick, confident, never a hype man. Every line must carry one concrete thing from THIS run's data (the spread/total, the script chance, the model total vs the market, a flag, a news-desk item, a corner, a snap share) so it is a take, not a vibe. Never: a joke about an injury or a player's health, "lock" / "can't lose" / guarantees, profanity, a fact you did not read in the inputs. If you have nothing specific for a game, leave it out (missing = no line printed). Budget: 5 minutes. build_boards.py prints the game line under the Context line; build_today.py prints it on the Today card. Print "voice: G game lines, L leg lines".
2. python3 build_boards.py ("wrote .../out/matchup-boards.html: N games, ... week W"; W must equal 'AUTO - Settings'!B2, N should be 13–16; every card carries a "Best parlay" block under its scoreboard — the 2–4-leg FanDuel slip, priced -110 to +500, most likely to cash per the model, with the best leg starred; it is built from the Leg Board legs the script strips use plus the game's moneyline / spread / total legs (gamelines.py: priced per game script, anchored halfway to the market, FanDuel prices from in/gamelines.json or the nflverse consensus line; legs where model and market disagree by 4+ points are never used), so it needs no extra input).
2c. Confidence archive: build_boards.py (step 2) wrote out/conf_rows.json ("wrote out/conf_rows.json: G games graded for confidence ..."; G = games not kicked off). mcp__Google_Sheets__append_values with range 'AUTO - Confidence Archive'!A1 and values = its "values" list (18 columns A..R; never write the header). Skip if G is 0. One block per run is expected; the season page grades the last row frozen before each kickoff.
2b. python3 build_calls.py ("wrote out/calls_rows.json: G games frozen for week W"; G = games that have not kicked off). Then mcp__Google_Sheets__append_values with range 'AUTO - Model Calls Archive'!A1 and values = the "values" list from out/calls_rows.json (29 columns, A..AC; never write the header again, never touch columns AD onward). This is the model's record of what it called - score, script odds, FanDuel lines, the chances it showed, the best parlay - frozen before kickoff; the Tuesday grading reads it. One block of rows per run is expected (the grader uses the last row frozen before each kickoff). If G is 0 (every game has kicked off) skip the append.
3. FIRST python3 rztd.py <W> (red-zone TD model, 11/3: downloads nflverse play-by-play 2025 + 2026 into in/ if missing, refits, prints "wrote out/rztd.json: N players for week W"; if it fails with "No module named numpy/scipy" run `pip install --break-system-packages numpy scipy` and retry; if it still fails the builder prints "warn: red-zone TD model not applied" and uses the projection model alone - say so in the summary). THEN python3 build_builder.py (prints "red-zone TD model: N anytime-TD legs blended", then "anytime TD: A legs (X added from the FanDuel Links tab beyond the Leg Board)" - A is normally 200+; if X is 0 the Links tab was not read in full - then "wrote .../out/builder.html: L legs, G games, week W, K with FanDuel links, T first-TD legs"; L is normally 1,200–1,800; if it is under 300 the Leg Board is thin for the week — still publish, but say so in the summary; T is 0 until FanDuel first-TD prices are in 'AUTO - First TD Odds').
3b. Game-line freshness: build_builder.py prints either "game lines fresh: newest gl| row <stamp>, N rows, G of G games" or "WARNING: DK/HR game lines stale - ...". If it prints the WARNING, copy that line verbatim into the two-line summary and into the dev-log row (the owner has to run FanDuel odds > Refresh game lines (DK/HR) now in the sheet; the rebuild cannot do it). Do not stop the run for it.
3a. Unders freeze (11/4): build_builder.py prints "wrote out/unders_rows.json: N main-line unders not yet kicked off"; if N > 0, mcp__Google_Sheets__append_values with range 'V2 - Unders Snapshots'!A1 and values = the "values" list from out/unders_rows.json (12 columns A..L; never write the header again). Model's Best freeze: build_builder.py also prints "model's best: E even-odds (overs + unders), T TDs, S safer legs" and "wrote out/best_rows.json: N Model's Best legs not yet kicked off". If N > 0, mcp__Google_Sheets__append_values with range 'V2 - Model Best Picks'!A1 and values = the "values" list from out/best_rows.json (15 columns A..O since 11/3 - M DK implied %, N HR implied %, O consensus implied % for the three-book test; never write the header again). One block per run is expected - the season page grades the LAST row frozen before each kickoff per (week, player, market, line). If N is 0 (everything has kicked off) skip the append.
3b. python3 build_live.py ("wrote .../out/live.html: L legs, G games, week W" - the Live page: tracked legs vs the live ESPN box score; it reads out/builder_data.json and out/best_parlays.json, so it must run after the boards and the builder).
3b2. python3 build_today.py ("wrote out/today.html + today.json: G games over D days, P plus/TD legs, N news notes, voice lines V") - the /today/ page (the installed app opens here; first bottom tab): today's (or the next) games with FanDuel line + model script, the plus-money looks for those games, news-desk notes per game, best parlay, "You today" (slip legs in today's games, Sleeper roster vs the news - in the browser), the rest of the week, the record; and /b/today.json = a ready morning brief per game day for the push function (slip-alerts.ts mode "brief", pg_cron 9:05 am CT; owner deploys). Needs out/builder_data.json, out/best_parlays.json, in/gamelines.json, in/ctx_news.json (Step 2a-ii), out/voice.json (1v, optional). If it fails, say so and carry on - the old /today/ in the clone stays.
3b3. python3 build_teasers.py ("wrote out/teasers.html + teasers.json: N teased legs over G games, week W; K six-point legs cross 3 and 7; best 6-pt pair edge +X pts") - the Teaser finder /teasers/ (11/5): every FanDuel main spread and total teased 6 / 6.5 / 7 points, priced by the game-line model (gamelines.py: margin sd 12.6, total sd 12.9, model centre shrunk 50% to the market), classic pairs that cross 3 and 7, editable two-leg prices. Reads out/builder_data.json + in/gamelines.json + in/games.csv, so it runs after the builder. "0 legs" means every game has kicked off (normal on a Monday run; the page then says so).
3b6. python3 build_survivor.py ("wrote out/survivor.html: week W-18, G games (F FanDuel moneylines, S closing spreads, E estimated), N lines behind the ratings, home field +H, ratings vs last four weeks' lines rmse R") - the Survivor planner /survivor/ (owner 11/10: "I just want betsweep to help me optimize in leagues I'm already in"): for elimination pools (one team a week, never the same team twice) the visitor marks the teams he has used, per pool, and gets the best pick this week and the best team for every week left - an exact weeks x teams assignment done in the browser. This week's win chances are FanDuel's moneylines with the vig removed (in/gamelines.json); later weeks are estimates from team ratings fitted to the season's closing spreads in in/games.csv (ridge, recent weeks weighted, SD 13.5) and marked "est." on the page. Needs out/builder_data.json (the week) and in/games.csv. Put the printed line in the run log; if F is 0 on a week whose lines are posted, say so (the page then shows estimates for this week too). If it fails, say so and carry on - the old /survivor/ in the clone stays.
3b7. python3 build_slipcheck.py ("wrote out/slipcheck.html (Sweep my slip, /sweep/)") - the front door of "Sweep my slip" (owner 11/10): a visitor uploads or pastes a screenshot of any FanDuel slip, import.js (slipimport.py - the same reader /me/ uses; the picture never leaves the phone) matches the legs to this week's board, puts them in the betslip and opens /build/?sweep=1#slip, where build_builder.py's sweepBlock() shows the verdict: the slip's chance (joint()) against its price (the one printed on the screenshot when there is one), how many legs are low risk (riskScore()), the weakest leg, a one-tap swap to a safer line with the new price and chance, and Drop. The same verdict opens from the "Sweep this slip" button in the builder's slip panel. No data of its own; nothing to check beyond the printed line.
3b9. python3 build_pairs.py ("wrote out/pairs.html + pairs.json: N players with an anytime-TD price over G games, week W; best pair A or B P% (fair F, low risk)") - the either-or touchdown pair maker /pairs/ (owner 11/8-11/10: an either-or leg is judged as a pair). Needs out/builder_data.json (after build_builder.py). FanDuel sells "A or B to score" as one leg and its price is in no feed we pull, so the page prices the pair itself (pairs.py: same game = mixed over the four endings with each leg's own per-ending chance, different games = the plain product; risk = the SAFER player's) and the visitor types FanDuel's price to see what he is paying. With no touchdown prices posted yet it prints "0 players ... best pair none yet" and the page says prices usually land by Thursday - not an error. build_site.py places it at /pairs/ and copies /b/pairs.json. build_promo.py prices "A or B | Either TD" promo legs with the same pairs.py (chance and pair risk).
3b10. python3 build_boost.py ("wrote out/boost.html + boost.json: N legs in the pool over G games, S same-game parlays, week W") - the Boost finder /boost/ (owner 11/10 deep dive): the visitor enters a profit boost's rules and the page finds the slip closest to fair before the boost, one leg per game (exact arithmetic), plus a checker for same-game boosts where he types FanDuel's quote. Needs out/builder_data.json and out/best_parlays.json.
3b11. python3 build_shop.py ("wrote out/shop.html + shop.json: B of P legs pay more at another book, N listed at 1.5+ points; widest: ...") - Line shop /shop/ (owner 11/10 deep dive): every leg where DraftKings or Hard Rock pays more than FanDuel at the same line, biggest gap first. Needs out/builder_data.json.
3b12. python3 shadow_slips.py ("shadow slips: house W-L (...), no-screen ..., value ..., under-mix ...; N written or refreshed this run, log M slips") - paper slips (owner 11/10 deep dive): four three-leg recipes per game day built from the same board, logged to the site's data/shadow-slips.json (kept across builds, frozen at kickoff, graded from the game log). Nothing is posted as a pick. Run it any time after build_builder.py and before build_site.py; put its line in the Tuesday log row. build_today.py itself now also prints "under of the day: ..." (under_day.py, data/under-day.json) and "lines to check: ..." (stale_lines.py, /b/stale.json) - copy both lines into the run log.
3b4. python3 build_beat.py ("wrote out/beat.html + beat.json: pool N legs in the -150..+150 band, model's five: ...") - Beat the model /beat/ (11/5): the week's pool of player props priced -150..+150 and the model's five (highest edge, chance >= 50%, one per player and game, at most two unders). The Edge Function's hourly run freezes the first build's five into Supabase beat_model (so the Thursday-morning five stand all week); picks are graded Tuesday by its grade mode from /data/graded-w<W-1>.json (Step 5a0). Runs after the builder.
3b8. python3 badbeats.py <W-1> (owner 11/10, 'Missed by one': prints "wrote out/badbeats.html: week N, X near misses ..."; needs in/legsnaps.json with the previous week graded - if it prints 0 near misses because grading has not landed yet, it still writes the page; build_site.py places it at /badbeats/. The file must be the plain-source format - <title>, description, font link, <style>, body - like build_beat.py; the first version wrote a whole html document and would have been nested inside the site shell. Step 6c: delete the clone's badbeats/ first, copy site/badbeats/).
3c. (Promoted bets are built in step 6b, after the repo clone is located, because their posters use the owner's slip screenshots from the clone's promo-slips/ folder.)
4. python3 build_team.py (prints "SOS applied to N of P players (M moved 0.3+ FP)" first - N is normally 250-350; "note: no SOS multipliers" means Step 2b did not write out/sos_values.json - then "wrote .../out/team.html: P players (A active), week W" — this is the Fantasy page; P is normally 500–600 and A 280–340; if A is under 200 the projection tabs are not populated for the week — still publish the other pages, skip the Fantasy page and the DFS page and say so).
5. python3 build_dfs.py ("wrote .../out/dfs.html: P players (A active), week W"; when in/dksal.json has a fresh DraftKings list the page pre-loads those salaries - a WARN line means it was skipped, still publish; mention it in the summary).
5a0. python3 build_mydata.py ("wrote out/data/box-w{1,..,W-1}.json: wk N players / finals ...") - per-week box scores + finals for the My BetSweep page, which grades anyone's saved slips in the browser; build_site.py copies out/data to site/data. Needs the game log read from Step 2; nothing else. Also writes (11/5) out/data/close-w<W>.json (closing lines per slip key from in/closing.json = 'V2 - Closing Lines', plus this build's prices - the CLV numbers on /me/; "no closing lines" just means the tab was not read this run) and out/data/graded-w<W>.json (hit/miss per slip key from in/results_legs.json - Beat the model grading; "no graded legs in the feed" is normal before Tuesday).
5a. python3 build_trade.py ("wrote .../out/trade.html: P players valued, week W (games through week W-1), ... top PPR ppg: ..."; the trade calculator - rest-of-season values from the game log, availability table (IR "through Week N" / "out for the season" text is parsed into games missed), snap trends and the schedule; superflex / TE premium / scoring / league size are page toggles that recompute every value client-side; also writes out/trade_values.json; values blend 70% ours / 30% FantasyCalc when in/market.json has rows (the sheet's MarketValues.gs fills 'AUTO - Market Values' daily; a copy is gen/MarketValues.gs); priors: the last two nflverse weekly seasons (downloaded if missing); the Dynasty toggle uses gen/dynasty.json (age curves, survival, rookie-pick ppg - research in gen/research/dynasty/) and in/roster_2026.csv for birth dates, which it downloads from the nflverse GitHub release if the file is not in in/ (the print line ends with "ages on file for N of P players" on the page; if N is far below P the roster download failed - rerun once, then publish anyway, the page says who is missing an age). If the printed top-5 ppg names look wrong - a backup on top, or a star missing - the game log read (Step 2) is short; re-read it before publishing. build_site.py places it at /trade/ and the home page has its tile.)
5a3. python3 build_dossier.py ("wrote out/dossier: G game dossiers for week W, L situational leans, defense profiles for 32 teams") - /dossier/ and /dossier/<gid>/ + /b/dossier.json (owner 11/5): per game, each offense against its most similar past defenses, each defense's leaks by role, script, weather, defensive injuries, news, and the situational spots from research/situational_spots.json (re-run research/situational_backtest.py only at season end). Run it BEFORE 5a2 build_teams.py (team pages link to the dossier when it exists) and after build_players.py. Step 6c: delete the clone's dossier/ first, copy site/dossier/.
5a2. python3 build_teams.py ("wrote out/teams: 32 team pages + directory, N game box scores, through week W") - /teams/ and /teams/<abbr>/ (owner 11/5): record, per-game offense / defense with league ranks, ATS and over/under, every game with team stats and a player box score (out/teams/box/<game_id>.json, loaded when a game is opened), season leaders. Runs AFTER build_players.py (it links names to existing player pages); downloads nflverse stats_team_week_2026.csv if missing. Step 6c: delete the clone's teams/ first, copy site/teams/.
5a1. python3 build_targets.py ("wrote out/targets.json: B buy-low, S sell-high for week W (market values on|off); P players screened") - the Trade desk (11/5): buy-low / sell-high fantasy targets from out/trade_values.json (so it runs AFTER build_trade.py), in/ctx_role.json, in/ranks.json and the schedule left. build_today.py renders out/targets.json as the "Trade desk" section of /today/ - so when build_today.py (3b2) has already run, run it AGAIN after this step (`python3 build_today.py`; it is quick) or the section is missing. out/social_targets.txt holds the week's one-line social post (Buy low / Sell high) for the promo desk.
5c. python3 build_players.py ("wrote out/players: N player pages (L with props this week), week W"; N is normally 300-450, L 200-300 - the Players directory /player/ and one page per player /player/<slug>/: his priced legs from out/builder_data.json with the DK / HR prices, hit rate vs each line from the nflverse game log, matchup pill, flags, snap / target share and game log. Needs out/builder_data.json (step 3) and the nflverse files Step 2b downloaded (in/stats_player_week_2026.csv, in/snap_counts_2026.csv, in/injuries_2026.csv - plydata.py downloads any that are missing). If L is 0 the builder data is missing - still publish the rest and say so.)
5d. python3 build_usage.py ("wrote out/usage.html: R risers, F fallers (week W)" and "wrote out/benefits.html: N players newly out/doubtful (M with games missed), K out for a while (week W)") - Usage trends (/usage/) and Who benefits (/benefits/). Statuses come from in/avail.json ('AUTO - Weekly Availability', Step 2 call C) first, then the nflverse weekly report. N = 0 early in the week is normal. Run after 5c (it links names to the player pages).
5e. python3 build_guide.py ("wrote out/guide.html") - How to read BetSweep (/guide/), static.
5b. python3 build_legal.py ("wrote out/legal-terms.html, out/legal-privacy.html, out/legal-responsible.html") - the Terms of Use, Privacy Policy and Responsible Gambling + affiliate-disclosure pages for BetSweep LLC; static text, no inputs. build_site.py places them at /terms/, /privacy/ and /responsible-gambling/ and every footer links to them.

## STEP 4 — Images (changed 11/5: no pre-rendered card PNGs)
(11/13: the owner had both buttons taken off the matchup boards - "We can take copy card as image and story 9:16 off of every matchup board"; the receipts and season pages keep theirs.) The "Copy card as image" / "Story 9:16" buttons render in the reader's browser (html2canvas, loaded on first tap from /s/), so do NOT run render_images.py on the boards and do not commit boards/img/ - 32 PNGs (19 MB) per run were the biggest thing growing the site repo. Still every run, if Playwright is available: `python3 render_images.py out/builder.html out/img-build img` ("rendered preview" - the one 16:9 shot behind the home page's builder tile, ~300 KB; Step 6c replaces build/ wholesale, so it has to be rendered each run or the tile goes blank). If Playwright is unavailable, skip it: the tile falls back to its text.

## STEP 5 — Tuesdays only
- 0d. FLAG REPORT CARD (owner 11/10 deep dive; after the leg snapshots are graded): `python3 research/fetch_snapshots.py <GRADED WEEK>` downloads the board the site published before each kickoff time of that week (GitHub API; files go to research/snapshots/, not committed) and prints a `python3 research/risk_grade.py ...` command - add the earlier weeks' arguments from research/risk_grade_w6-9.txt's header lines if you want the season pooled, run it, save the output as research/risk_grade_w<W>.txt and commit it. Put four facts in the dev-log row: favorites (-350..-140) hit % by risk tier (low / some / high) for the week and pooled, the Short view rule's hit % against its break-even, the "LEGS THE SITE SHOWED AT OR ABOVE THE PRICE" by-market line, and the held-out test's POOLED favorites line. Then `python3 research/two_way.py <GRADED WEEK>` (both sides of every main line) and the `shadow slips:` line. Rule: nothing here changes a flag, a weight or the owner's low-risk rule by itself - a change is proposed to the owner only after the same reading holds in three graded weeks running.
The run after the week's games: build the weekly receipt and refresh the season page BEFORE assembling the site.
- 0) Grade the model calls first: python3 build_calls_results.py (prints "graded week W-1: G games - ML h/n, spread h/n, total h/n, script h/n, best parlay h/n; margin MAE model x vs market y; ..."). Then write the grades back: for each item in out/calls_grades.json "updates", mcp__Google_Sheets__update_values with that item's range (columns AD:AQ of the frozen row) and values. If it exits with "no archived week has final scores yet", skip and say so. It also writes out/calls_week<W-1>.json, which build_results.py turns into the "Calls" card on the receipt.
- 0b) (11/10) Grade the promoted bets BEFORE the receipt: do step e) now (grade_promos.py, write its updates to the sheet, then re-read 'PROMO - Promoted Bets'!A1:N100 into in/promos.json). The receipt's 'What we posted' block only appears when the week's promo rows already have a Result - on 11/10 the Week 9 receipt was built first and went out without the block while the receipts index said "posted slips 0-9" (patched in by hand that afternoon). After step a, check: `grep -c "What we posted" out/results-week<W-1>.html` must be 1 whenever that week has promo rows; if it is 0, re-read in/promos.json and run build_results.py again before going on.
- 0c) (11/10) Grade the chat-built slips: read 'ASSIST - Slip Log'!A1:J500 with mcp__Google_Sheets__get_values and save the reply's values as in/assist.json ({"values": [...]}), then python3 grade_assist.py (prints one line per slip of last week - "row N <slip>: WON|LOST (h/n) +x.xxu at <price>" or "open ... <why>" - and "assist log week W: A won, B lost (+U.UUu at the logged prices), P left open for a hand grade"; writes out/assist_grades.json). Write each item of its "updates" back with mcp__Google_Sheets__update_values (two cells per row: Result in I, the leg-by-leg note in J - the note keeps whatever was there). It only fills rows whose Result is empty, never changes a hand grade, and leaves a slip open when a leg cannot be read or a player has no stat row (unless another leg plainly missed). Put the summary line in the run summary and name the open rows so they get a hand grade. Same grader rules as the PROMO tab (slipgrade.py; grade_promos.py is unchanged). Checks: `python3 tests/assist_grade.py` (the Week 9 slips that were graded by hand: the grader agrees with all five it can read).
- a) python3 build_results.py (its scorecard's 'What we posted' block grades the week's promoted bets from in/promos.json at the posted FanDuel odds - the honest headline next to the 1,700-leg pool; rows need a Result of Hit/Missed, which grade_promos.py writes) → "wrote out/results-week<W-1>.html week W-1: G games, P players, L legs" (the feed follows 'AUTO - Settings'!B2-1 automatically). If it exits with "no snapshot rows in the feed", the week is not graded yet: skip 5b–5d, say so in the summary, do not create an empty receipt.
- b) (changed 11/5) No receipt artifact and no receipt PNGs: the receipt lives at https://betsweep.co/receipts/week<W-1>/ (Step 6 copies site/receipts/week<W-1>/); its image buttons render in the browser like the boards'.
- c) Append one row to 'AUTO - Boards Archive' (Week | Page | URL | Built (CT) | Note): ["<W-1>", "Week <W-1> receipt", "https://betsweep.co/receipts/week<W-1>/", "<YYYY-MM-DD HH:MM CT>", "auto"] - the receipts index lists every week in this tab, so the row matters; the URL is the site's own page (11/5; older rows still carry claude.ai links and build_site.py maps those). One row per week: if that week already has a row, update its URL instead.
- d) Re-read 'AUTO - Boards Archive'!A1:F60 with get_values, overwrite in/archive.json with {"values": rows}, (no boards re-run needed since 11/5 - the site strips the boards' archive nav and the receipts index reads this tab in Step 6), then python3 build_season.py (its calibration card - hit rate vs model % by edge bucket, line depth, warning and matchup (tough / middle / soft, rebuilt leak-free from in/gamelog.json weeks before the leg's week), plus the Brier line: raw model vs FanDuel price vs the number the site shows (calib.py blend) vs the best blend - fills from the graded legsnaps rows; its "Game calls vs the closing line" table (model ML vs FanDuel favourites, where we disagreed, spread, total, margin error and win Brier next to the market, per week + season) fills from in/calls.json + in/games.csv; its summary carries the promoted-bets record (W-L and units at posted odds, by week) from in/promos.json; if a bucket shows the recommended legs hitting 10+ points under the model for a second straight week, say so in the summary and the log row rather than changing formulas mid-run) and python3 render_images.py out/season-receipt.html out/img-season img, and publish out/season-receipt.html to the season artifact URL with its two PNGs as files.
- e) Grade the promoted bets (run as step 0b, before the receipt - listed here for the details): python3 grade_promos.py (prints "week W-1: slot N <title>: Cashed|Missed|PENDING (h/n)" per promo and writes out/promo_grades.json). Write each item in its "updates" back with mcp__Google_Sheets__update_values (Result in column I, the leg-by-leg note in column M; the script only touches rows whose Result is empty). A PENDING slip (a player with no stat row, or a First TD leg) stays empty for the owner to settle; say which in the summary. Re-run step 3c's build_promo.py afterwards (it happens in 6b anyway) so the home page shows Cashed / Missed.
- e2) (11/17) Refit FanDuel's same-game discount once the new week's builder has been built: `python3 research/sgp_discount.py` ("wrote research/sgp_discount.json + .md: N quotes, c = ..."). Commit both files with the research files. It reads in/promos.json (every same-game promo whose column E is FanDuel's own price and whose legs each carry a price) and out/builder_data.json (the correlation tables). The generators read the json at build time (sgp.py); if c moves by more than a third week to week, say so in the dev-log row.
On non-Tuesday runs skip this step entirely (no receipt, no season rebuild).

Unders check (11/4, Tuesdays, after grading): `python3 unders_check.py <GRADED WEEK>` -> the printed block (both sides of every frozen main line at real prices, by market / price band / the two cuts) goes in the dev-log row; nothing changes on the site until a cut is positive two graded weeks running with 60+ legs each. Red-zone TD check (11/3, Tuesdays, after grading): `python3 rz_check.py <GRADED WEEK>` -> one line ("rz check week W: n legs - log loss raw / rz / shown avg / FanDuel") for the summary and the dev-log row; if it prints REVERT, set RZ_W = 0 in rztd.py on gen-overrides and log it. Live 'from here' grade (11/4, Tuesdays, after grading, from Week 9): `python3 live_grade.py` -> research/live_grade_w<W>.txt and a DEVLOG line (Brier from-here vs pregame; anytime-TD live calls hit vs from-here). Inputs are the public `feeds` branch (livelog.json = in-game box scores every 10 min; livelegs_w<W>.json = the live page's tracked legs pinned on the first in-game run) and in/results.json; the sandbox cannot reach raw.githubusercontent.com so it falls back to `git fetch origin feeds` in /home/claude/betsweep-site. If it prints "no pinned legs" the feeds workflow never saw a live game that week - check the Actions log. Three weeks of Q3-Q4 TD calls landing near their from-here chance is the bar before anything is shown as a product (next step then: log FanDuel live TD prices in feeds.py). Calibration scoreboard (added 11/1, Tuesdays, after grading): `python3 calib_market.py <GRADED WEEK>` -> out/calib_market.md / .json and one line ("calib week W: ... drifting: ..."). Put the line in the dev-log row and the run summary, and the DRIFTING list on the receipt. When closing prices exist it also grades line movement (price moved our way / flat / away). Never change a projection from it without the owner.
Loss autopsy (added 11/1, Tuesdays, after grading): `python3 loss_autopsy.py <GRADED WEEK>` -> out/autopsy.json and two lines ("All graded legs: N losses - variance a, role b, ...; k we could have seen coming" and the same for promo legs). Put both lines on the week's receipt under the scorecard (plain text, one line each), in the dev-log row, and in the run summary. Tags and rules are in the script's docstring; one tag per player + market (alt-line ladders are counted once).

## STEP 6 — Assemble and deploy the site (every run)
- a) Locate the repo clone FIRST (the build needs its posts/ folder). The scheduled task should have joeymccarrick1/betsweep-site attached as a repository, so it is normally already cloned in the session's working directory at the start of the run: find it (e.g. `git rev-parse --show-toplevel` in the working directory, or look for a folder containing CNAME and posts/ whose `git remote get-url origin` ends in joeymccarrick1/betsweep-site). Make sure you are on main and up to date: `git checkout main && git pull --ff-only origin main`. Only if no clone exists, try mcp__claude-code-remote__add_repo owner "joeymccarrick1" repo "betsweep-site" access "push" and then `git clone https://github.com/joeymccarrick1/betsweep-site <clone>`. If neither works, skip 6b–6e, say "site push skipped: repo not attached to the scheduled task" in the summary and the log row, and continue to step 7.
- b) FIRST, approved promo drafts (owner 11/3): `git clone -q --depth 1 --branch promo-drafts https://github.com/joeymccarrick1/betsweep-site.git pd` (if the branch does not exist, skip), then python3 promo_approve.py pd → "wrote out/promo_rows.json: N approved drafts to append". If N > 0: append_values with the range and values in that file (one call), re-read 'PROMO - Promoted Bets'!A1:N100 into in/promos.json, and name the new rows in the summary ("approved drafts added: wk9 slot 3 ..."). Drafts with "post": true are the owner's approval - this is the one case where the run adds PROMO rows; it never edits existing rows and never sets "post" itself. THEN python3 build_promo.py <clone>/promo-slips ("wrote out/promos.json: N promoted bets for week W" and "wrote 3N promo posters (feed 4:5, square, story) -> out/promo/" - the slips the owner lists on 'PROMO - Promoted Bets' with Status LIVE, priced by the model leg by leg (Anytime TD, First TD, Either TD pairs, stat lines, game lines; it reads out/builder_data.json and out/firsttd_all.json) and rendered as 1080x1350, 1080x1080 and 1080x1920 posters for X / Instagram, with the owner's FanDuel screenshot from <clone>/promo-slips/<week>-<slot>.png|jpg in the phone frame when present. If the tab has no LIVE rows for week W it writes an empty list and the home page has no Promoted section. Never edit the owner's rows or add promoted bets yourself.) THEN python3 build_site.py betsweep.co <clone>/posts → writes ./site/: index.html (the home page: the sheet's Best Legs as "top plays" with FanDuel links, anytime-TD and game-line radar, the best same-game parlay, the week's slate with live scores, the track record, the page tiles, and the newest six pictures from <clone>/posts in its gallery - all built by home.py from in/bestlegs.json, out/builder_data.json, out/best_parlays.json, in/scorecard.json and in/legsnaps.json, so it must run after the boards, builder and season steps), boards/ (+img/), build/ (+img/), live/, team/ and fantasy/ (the Fantasy page and its redirect; if out/team.html exists), firsttd/ (if out/firsttd.html exists), dfs/ (if out/dfs.html exists), p/ (web copies of the pictures used), receipts/index.html, receipts/week<W-1>/ (only if built this run), season/ (only if built this run), CNAME, .nojekyll, og.png, favicon.png, wordmark.png, wordmark-ink.png, 404.html, plus the installable-app files: manifest.webmanifest, sw.js (service worker, versioned per build so phones pick up the new pages), offline.html, apple-touch-icon.png, app/icon-*.png and app/maskable-*.png.
- c) Copy site/ over the clone WITHOUT deleting older receipts or the owner's posts: delete the clone's boards/ (including boards/img/ - the pre-rendered PNGs are gone as of 11/5), build/, live/, social/, team/, fantasy/, firsttd/, dfs/, trade/, player/, usage/, benefits/, guide/, teasers/, survivor/, sweep/, pairs/, short/, simple/, beat/, api/, teams/, dossier/, p/, promo/, s/ and any legacy top-level img/, then copy site/s/ (11/5: the shared, content-hashed site-*.css / app-*.js / tpl-*.css, the fonts and html2canvas - every page links them), site/index.html, site/boards/, site/build/, site/live/ (if built), site/social/, site/team/ and site/fantasy/ (if built), site/firsttd/ (if built), site/dfs/ (if built), site/trade/ (if built - delete the clone's trade/ first; added 10/30, it was missing from this list so the live Trade page only updated when a run happened to copy it), site/teasers/, site/survivor/, site/sweep/, site/pairs/, site/boost/ and site/shop/ (11/10 evening, if built - delete the clone's copies first), site/short/ and site/simple/ (11/10, if built; simple/ is the one-file redirect to /short/), site/beat/, site/api/ (11/5; delete the clone's copies first), site/player/, site/usage/, site/benefits/, site/guide/ (if built; added 10/30 - delete the clone's copies first, so a player who left the board does not keep a stale page), site/terms/, site/privacy/, site/responsible-gambling/ (delete the clone's copies of those three first), site/p/, site/promo/ (if present; delete the clone's promo/ first), site/sitemap.xml and site/robots.txt (added 10/30), site/b/ (copy OVER the clone's b/ without deleting it - last week's short-link pages must keep working after their promo posters are gone), site/receipts/index.html, site/CNAME, site/.nojekyll, site/og.png, site/favicon.png, site/wordmark.png, site/wordmark-ink.png, site/404.html, and the app files site/manifest.webmanifest, site/sw.js, site/offline.html, site/apple-touch-icon.png and site/app/*.png (copy the PNGs into the clone's app/ folder WITHOUT deleting app/README.md, app/package.json, app/capacitor.config.json or app/www/ - those are the store-wrapper project); copy site/season/ only if it was rebuilt this run; copy site/receipts/week<W-1>/ only if the receipt was built this run. NEVER delete, rename or overwrite anything in the clone's posts/ or promo-slips/ folders (the owner uploads there by hand). Never delete anything under receipts/week*/ that the new build did not produce. (audit 11/10) Also copy site/badbeats/ (when built this run - delete the clone's badbeats/ first) and site/how/ (built every run from the generators' how_body.html since 11/10 - delete the clone's how/ first; the page used to be hand-stitched in the repo with a frozen old header). After everything is copied, run `python3 lab/merged/make.py` from the clone root: it restitches the Game Desk concept page (/lab/merged/, linked from every home game card) from the new build/index.html and prints "wrote lab/merged/index.html for week W" - it showed last week's header for a day because nothing re-ran it. If it fails, say so in the summary and carry on (the old page stays).
- d) `git add -A`, commit with `git -c user.name="BetSweep" -c user.email="support@betsweep.co" commit -m "Week W boards <date>"` (plus " + Week W-1 receipt" on Tuesdays), and push directly to main: `git push origin HEAD:main` (GitHub Pages deploys from main; do NOT open a pull request and do NOT push to a claude/ branch instead). If the push is refused because main moved while you were building (ordinary since 11/4: the price job commits data/price-moves.json to main every half hour, and a retry without a pull can never succeed), run `git pull --rebase -q origin main` and push again - up to three tries, ten seconds apart; never force-push. If it is still refused, record the exact error message from git in the summary and the log row, and continue to step 7.
- e) Verify with WebFetch on https://betsweep.co/boards/ after ~2 minutes that the h1 shows Week W; if it still shows the old week, say so in the summary (Pages deploys can lag a few minutes) — do not push again.

## STEP 7 — Artifact mirrors (retired 11/5)
Nothing to publish. The claude.ai copies of the boards / builder / Fantasy / First TD / DFS pages are no longer refreshed (the site is the product; the nav links to them were rewritten to site paths weeks ago), and the generator bundle in the boards artifact is an archive - the branch in Step 1 is the source. Skip this step.

## STEP 8 — Log
One row to 'MASTER - Model Development Log' (append_values on 'MASTER - Model Development Log'!A1): [today's date, "Boards auto-rebuild: week W, snap trends N rows (D down), first TD P players (F priced, max diff X pts), N games, L builder legs (K with FanDuel links, T first-TD legs), Fantasy page P players (A active), DFS page built <yes|no>, images K/K, site push <ok <commit sha>|refused: <git error>|skipped: <reason>>, <receipt created: url | no receipt (reason)>, boards v<version>", "automated"]. One row per run.

## The Daily Sweep (owner 11/10: "I'd love for us to start 1-3")
One house slip per game day at the top of the home page, with its own public record. Nothing new on the sheet: it is a row of 'PROMO - Promoted Bets' whose Title starts with "Daily Sweep" ("Daily Sweep: Capital Gains"); legs, FanDuel odds, link, Status and Result work as for every promoted bet. gen/sweep.py is the one place that knows the convention (is_sweep, name, record, one_per_day, risk_score) - `python3 sweep.py --selftest`.
- build_promo.py (Step 6b) marks at most one Sweep per game day (CT date of the first kickoff; lowest slot wins) and prints, for the run log: `daily sweep: Thu 11/12 - slot 1 "Daily Sweep: ..." +305, 4 legs`, plus `DAILY SWEEP WARNING - ...` lines when a day has two, a leg is "Some risk" / "High risk", the price is outside +200..+450, the slip is not 3-5 legs, or column E has no price. Copy every warning line into the summary so the owner sees it - the card still goes up; he decides.
- home.py sweep_block() (called from build_today.py, first thing on "/"): the day's card from the moment it is posted until that day's games are over, otherwise a line saying when the next one posts and how the last one did. Which of the two shows is decided in the browser from the clock, so the page is right between rebuilds; a missed Sweep stays up as a miss (the live script never hides a data-keep card). The rest of the promoted bets stay in the grid further down, called "Side action" from the week the first Sweep exists, with "Long shot" on slips at +2000 or longer.
- Record: every Sweep row with a Result, at the posted FanDuel odds, one unit each (grade_promos.py on Tuesday writes the Result like for any promo). Shown on the hero, the receipt's "What we posted" block (first tile) and the season page. A row without a Result is pending and counts for nothing.
- The record is the record: a Sweep goes on the tab BEFORE its first kickoff and is never edited, re-priced, renamed or replaced afterwards, and none is ever added after the fact. This run never creates one - promo_approve.py appends approved `type: "sweep"` drafts (PROMO_DESK.md "sweep" slot), or the owner adds the row in chat. If build_promo prints a Sweep whose first kickoff has already passed and that was not in the previous build's /b/promos.json, say so in the summary.

## Who is at home (audit 11/10)
A game id ("NYG-WAS") and a game's a / b are the two teams in the scripts tab's order - alphabetical in practice - NOT away-home. Labels built from them ("NYG @ WAS") were wrong for 11 of 14 games in Week 10 on the home page slate, the best parlay, the game-line cards, the teaser finder and the Sweep says share cards. build_builder.py now puts `home`, `away` and `nt` (neutral site) on every game from the nflverse schedule (in/games.csv), and every "@" is printed from them: home.py at() / at_gid(), build_teasers.py _at(), build_boards.py sweep_card() via game_for(). A neutral-site game, or one the schedule does not know, prints "A vs B". build_today.py (FanDuel's "Away @ Home" game string), build_live.py, build_firsttd.py, build_dossier.py and build_results.py already read the schedule. When adding a page: never print "@" from a gid.

## Site checks (added in the 11/10 audit) - tests/
Four scripts that load the built site in a headless phone-sized browser against a local server (`cd <site clone> && python3 -m http.server 8801 &`); every request that is not local is blocked, so nothing touches Supabase, ESPN or FanDuel. Run them after a hotfix to a page script and whenever a build feels off - they take about four minutes together.
- `python3 tests/site_crawl.py` then `python3 tests/site_summary.py`: every page (476 on 11/10) - JS errors on load, failed local requests, broken images, sideways overflow, "undefined" / "NaN" in the text, local links with no file behind them, title / description / canonical / h1. A clean run prints "js-error pages 0, bad-response pages 0, broken-img pages 0, overflow pages 0, flag pages 0" (a `hardrock://` deep link is not a page - ignore that one "broken link").
- `python3 tests/site_clicks.py /build/ /boards/ /live/ /team/ /dfs/ /trade/ /social/ /me/ /`: types into every text box and clicks every button, toggle and select it can find, and names the control behind any JS error. A page that loads clean can still be broken behind a tap: this is what found the Parlay Builder's Save slip throwing `byKey is not defined` (nothing had saved since 11/5), the Social "Sharps" tab and the Trade page's click handler.
- `python3 tests/builder_slip_totals.py` (needs out/builder_data.json from the same build): a game total stays on the game it was picked for. A total's key has no game in it - "Over 40.5|Total|41" was the MAIN total of three Week 10 games and an alternate total of most others - and the builder resolved a stored key to the first leg with that number, so a reload or coming back to the tab swapped IND-MIA over 40.5 (-115) for NYG-WAS over 40.5 (-142). Since 11/10 the builder records the game per shared key in `bs_slipg_w<W>` ({key: [gid, ...]}, synced with the account), saved slips carry the same map in `g`, the page slip (template.html) reads it (a key on record for another game shows as "priced in the builder") and records the card a total was tapped on, and build_boards.py writes one slip leg per game for a shared key. NOT done: the Live page and My BetSweep still match a total by key alone (display only - totals are not graded), and the proper fix is a key that names the game for totals everywhere (builder legKey, build_boards.leg_key, home.leg_key, the Edge Function) - that changes stored keys, so do it between seasons or with a migration.
- `python3 news_desk.py --selftest`: the news wording cases (see Step 2a-ii).
- `BASE=http://localhost:8802 python3 tests/survivor_plan.py` (needs a built site): the Survivor planner's road is checked against an exact search for three sets of used teams, plus pools, reload, kicked-off games and the week rolling over.
- `BASE=http://localhost:8802 python3 tests/simple_view.py` (needs a built site plus out/builder_data.json, out/best_parlays.json and out/simple.json from the same build): the Short view (/short/) fits a phone, its one-tap FanDuel links are read back against the builder's ids (the three legs shown, in order, no unders, favorites with no risk flag; the best parlay's own legs), kicked-off games leave, the Short / Full choice is kept and moves only the bare home address, the old /simple/ address lands on /short/, a ruled-out player is struck.
- `python3 pairs.py` (13 arithmetic cases for an either-or pair) and `BASE=http://localhost:8802 python3 tests/pairs_page.py` (needs a built site and out/builder_data.json from the same build): the /pairs/ page computes the same numbers as pairs.py for every pair on the board, prices a picked pair, judges a typed FanDuel price, drops kicked-off games and calls out a ruled-out player.
- `BASE=http://localhost:8802 python3 tests/slip_verdict.py` (needs a built site and out/builder_data.json from the same build): "Sweep my slip" - a clean slip reads clean with the price panel's own numbers, a risky leg is named and the one-tap swap really swaps it, Drop removes it, and a slip handed over by /sweep/ carries its printed price and names the legs that are not on the board (the picture reader itself is stood in for; it needs the tesseract download).
- `BASE=http://localhost:8802 python3 tests/deepdive_pages.py` (needs a built site and out/*.json from the same build; 11/10 evening): the Boost finder (one leg per game, the page's numbers recomputed from /b/boost.json, the FanDuel link's ids read back, the rules honoured, the first card proven the likeliest triple by brute force), Line shop (every row a real better price at the same line, kicked-off games leave), the Short view's "3 favorites" and all-three chance, the home page's new blocks, the Live page's win card, and - with no browser - the Under of the day / Lines to check / shadow-slip rules on made-up boards. `python3 tests/gate.py` after a crawl turns it into ok / HOLD for an unattended publish.
- `python3 sweep.py --selftest`: the Daily Sweep convention and record maths. `BASE=http://localhost:8802 python3 tests/sweep_hero.py` (needs a built site whose week has a Daily Sweep row for its first game day): the hero at four moments of the week with the browser clock faked and ESPN answered from the test - before the game, in play, the morning after a win, the morning after a miss.
The generators that only read in/ and out/ run in seconds in any session that has the mirror (11/10: news_desk, badbeats, build_legal, build_players, build_usage, build_boards 5 s, build_builder 2 s, build_today, build_live, build_dfs, build_trade), so a generator change can be run and its page placed with wrap() / place() and tested here before the scheduled rebuild picks it up - do that instead of trusting a hand-patched copy of the live page. Sweep says share button: build_boards.py writes out/sweepcards.json (the per-game buttons + the share-card script) and build_today.py puts the same button under the line on the home cards, so build_boards must run before build_today (it does: Step 2, then 3b2).
Hand-patching the live site (the hotfix pattern): patch the page on main AND the generator on gen-overrides with the same exact-string replacement (assert the old string occurs once), run the checks above against the patched clone, commit both. /tmp/audit/wraptest.py in the audit session showed how to call build_site.py's wrap() / place() for one page without a full build (exec everything before `made = []`, then the block you need); the last pass of build_site.py turns the inline base64 logo into /logo.png - a page wrapped by hand needs the same replacement or it is 130 KB heavier than its neighbours. Names at the top level of build_site.py are global to the whole script: a new block must not reuse one (the first draft of the /how/ block overwrote `_hl`, the hashlib alias, and every later wrap() would have failed).

## Static assets and page weight (11/5)
build_site.py writes /s/site-<hash>.css (nav + brand layer + @font-face), /s/app-<hash>.js (site-wide script), /s/tpl-<hash>.css (the template CSS every template page shares), /s/fonts/*.woff2 (Barlow italic 800, Barlow Condensed 500/600/700, IBM Plex Sans 400/500/600 - latin subsets, OFL) and /s/html2canvas.min.js (MIT), all from the generator folder's assets/. wrap() replaces the inline copies with links, drops the Google Fonts link and swaps the cdnjs html2canvas tag for a stub that loads the local copy on first use. The service worker serves /data/ files and any cache:'no-store' request network-first (risk notes and price moves change hourly). Result: ~27 KB less HTML per page (65 KB more on template pages), no third-party requests on load, 35.6 -> 24.4 MB per build.

## Out-of-the-box batch (11/5, owner: "Let's do all of your out of the box things ... push a rebuild as soon as you're done")
What shipped, where it lives, and what only the owner can switch on (the rebuild just builds; nothing below needs a step beyond Step 3):
- Weather pushes are unconditional (owner: "I haven't seen anything about weather. Always push weather updates"): the Edge Function's hourly run pushes every game with a HIGH/MODERATE kickoff-hour risk to every subscriber (with the user's own legs in that game named, or "Nothing of yours is in it"), once per game per week (bs_marks), and posts it to Discord. build_today.py leads every morning brief with "Weather: A-B high (wind 18, rain); ..." for the day's games.
- Line moves: .github/price_moves.py on main (every 30 min) now covers every leg in /b/live-legs.json + /b/plus.json (not just the plus tier) and keys each move by the slip key; the hourly run pushes 3+ point moves on legs a user has saved (push_sent key __mv__<key>|<dir>, once per direction).
- CLV + one leg away (/me/): saved slips carry px {key: {o, p}} (price + chance at save time; template.html, build_builder.py, build_live.py); build_mydata.py writes data/close-w<W>.json from 'V2 - Closing Lines'; account.py shows "Closing line: beat it on X of N legs" per slip, per-leg ▲/▼ vs the close, and "One leg away: <leg> N short" on busted slips; the Edge Function's recap mode pushes the same the morning after (cron betsweep-recap Mon/Tue/Fri 05:35 UTC).
- Friend leagues on /beat/ (owner 11/10, "Friend leagues for Beat the model"): build_beat.py LEAGUE_CSS / LEAGUE_JS draw the "Your leagues" card (#btlg) above the leaderboard - start a league, share the invite link betsweep.co/beat/?league=<8 characters> (opening it signed in joins the league and cleans the address; signed out it asks for a sign-in first), one board per league with the model as an unranked row, and a league counts only the weeks graded after it was created so everyone starts level. No elimination or survivor league type here on purpose (owner 11/10: BetSweep helps with the pools he is already in - that is the Survivor planner). Everything goes through seven security-definer functions in sql/betsweep-leagues.sql (beat_league_create / _join / _leave / _rename / _delete / _mine / _board); the two tables (beat_leagues, beat_league_members) have row level security on and no policies, so nothing reads them directly, and the board returns display names and hits only - never a user id or an e-mail. Limits: 10 leagues started and 25 joined per account, 200 people per league. ONE-TIME OWNER STEP: run sql/betsweep-leagues.sql in the Supabase SQL editor (it needs the 11/5 script's beat_picks / beat_model; safe to run twice). Until then the first call comes back PGRST202 and the card hides itself - nothing else on the page changes, so the build never depends on it. Checks: `psql -v sqlfile=sql/betsweep-leagues.sql -f tests/leagues_test.sql` on any scratch Postgres 15+ (it makes and drops its own database, stands in for Supabase's auth schema and roles, and ends "LEAGUES TEST PASSED"); `BASE=http://localhost:8802 python3 tests/beat_leagues.py` for the card (Supabase is stood in for in the page: functions missing, signed out with an invite, start, join by link, board order, leave, bad code, phone and desktop).
- Teaser finder /teasers/ (Step 3b3), Beat the model /beat/ (Step 3b4; Supabase tables beat_picks / beat_model; grade mode Tuesday 16:40 UTC), Trade desk on /today/ (Step 5a1), /api/ (build_site.py writes it; lists every /b and /data JSON and the feeds branch files), Ask the model (/today/ form -> Edge Function mode "ask", user JWT, 20 a day, context = the builder's legs for the surname asked + the top edges; ANTHROPIC_API_KEY on the function), Listen (speechSynthesis reads the day's brief; no server), fantasy roster sync (build_team.py upserts fantasy_rosters when signed in; the inactives mode pushes "X is INACTIVE ... best bench: Y" on game days and the startsit mode the Saturday-night bench-beats-starter note), email digest opt-in on /me/ (email_prefs; email mode via Resend Thu/Sun 15:20 UTC).
- Owner-only switches (nothing works until these are done; say so in the summary if the owner asks why a mode is silent): redeploy gen/push/slip-alerts.ts as the slip-alerts Edge Function; run gen/push/betsweep-11-5.sql in the SQL editor with __CRON_SECRET__ replaced by the real cron secret (the owner's copy lives outside the repo); add secrets DISCORD_WEBHOOK, RESEND_API_KEY + EMAIL_FROM, ANTHROPIC_API_KEY (ASK_MODEL optional, default claude-haiku-5-5). The SQL file's header lists them.
- Game-day Action (.github/workflows/gameday.yml + gameday.py on main, Sundays 13-23 UTC and Mon 0-1 UTC every 30 min, Tue/Fri 00:08/00:38 UTC for TNF/MNF-adjacent posts): joins the feeds branch's inactives with the mirror's projections and writes 'AUTO - Weekly Availability' (E=OUT, J/K/L) and 'AUTO - Game Day Status' rows through the service account (SHEETS_SA_JSON, which must be an editor on the sheet). The LLM "NFL game-day inactives check" task is redundant once this Action is seen writing rows.
- Commit ids before 2026-11-10 22:05Z: that evening main, gen-overrides, gen-patch, gen-patch2, promo-drafts and promo-studio were rewritten to replace a personal e-mail address with support@betsweep.co (author / committer lines, and 63 old versions of RUNBOOK.md and the workflow files). Files, messages, dates and order are unchanged, but every commit id on those branches changed, so an id quoted before then - in the dev log, in this file, in an old chat - is an OLD id that no branch carries any more. commit-map-2026-11-10.json in this folder maps old to new (first 8 characters; "heads" has the branch tips: main 9a65c922 -> 5f6e217f, gen-overrides a4fb7557 -> 5779bce9). Never push a clone made before that moment; re-clone. Commit as BetSweep <support@betsweep.co> only.
- Secrets: nothing in this repo holds a key. The VAPID private key, the cron secret and the service-account JSON live only in the owner's Supabase / GitHub secrets; gen/push/*.sql keep __CRON_SECRET__ / __OWNER_EMAIL__ placeholders. Never commit a file with a real value, and never post one in the summary.

## Rules
- History: dated "shipped / fixed" notes that no step depends on live in CHANGELOG.md (same folder) - read it only when debugging a feature's past; this file keeps the procedure and the mechanisms the steps rely on.
Model-first (odds are only a price); never invent results or fill missing rows with zeros; never create duplicate automations or extra artifacts beyond the Tuesday receipt; if any step fails in a way you cannot fix from the data, stop, log the failure in the dev log row, and leave the previously published site and pages untouched. End with a two-line summary of what was published.

## Calibration (calib.py) and research scripts
- calib.py holds W_MODEL (0.5 since 2026-10-20): every player-prop leg's shown "Model %" on the boards, builder, home page and live/promo pages is W_MODEL x raw hist-adjusted model % + (1 - W_MODEL) x FanDuel implied %, and edge = shown - book. build_boards.py blends at Leg Board ingestion (keeps raw_p), build_builder.py blends every player leg in one pass before the game lines are added (game lines are priced in gamelines.py and are NOT blended), home.py blends the sheet's Best Legs the same way. Ranking is unchanged; hard edge gates were halved to keep the same pools (boards best-legs +2.5, best-parlay pools -1.5/-3, home TD radar +/-2.5, floor legs -2.5, builder quick-slip value +1.5 / anchor -0.5). The sheet's Leg Board, Best Legs and the frozen snapshots keep the RAW number (that is what the calibration card grades), so a sheet edge of +5 is a site edge of +2.5. Move W_MODEL only when the season receipt's Brier line names a different weight as best for a second straight graded week; log the move.
- Game-line harness: gen/gameline_backtest.py (python3 -I gen/gameline_backtest.py; nflverse 2024-26, strict walk-forward, EPA / turnover / rest / bodies-out / weather lenses, CLV; writes out/gameline_backtest_results.md) is THE harness. gen/research/gl_backtest.py in/games.csv [--season S --week W] is the lighter 2020-26 version (univariate upset-flag rates + a one-week post-mortem print) kept for the Tuesday "why did the favourites lose" question; both reached the same answer on 2026-10-20 (no pre-kick public signal beats the closing line). Nothing from either feeds the live pages unless a season-level test beats the close two seasons running.
- Research (not part of the build, kept under gen/research/): matchup_study.py (symmetric vs one-sided opponent multiplier, walk-forward 2025-26: promoted the one-sided factor on 2026-10-20), recency_study.py (EWMA / last-3 / position-mean shrinkage / rushing level vs the plain season mean: recency weighting rejected, shrinkage k=2 queued for a sheet-level test after Week 7). Run with python3 -I <script> nv/stats_player_week_<yr>.csv ... after downloading the nflverse weekly stats.

## Other books on the betslips (DraftKings, Hard Rock) and the Hard Rock line swap (hrswap.py)
- 'AUTO - Book Odds' (FanDuelOdds.gs v2026-10-20) is joined onto every builder leg and every boards slip leg by the normalised key 'player|market|line' (First TD special-cased) in build_builder.py and build_boards.py -> l.bks = {dk:{o,s}, hr:{o,s}}. Send to DraftKings = sportsbook.draftkings.com/?outcomes=<id>+<id> (ids URL-encoded, '+' joined; confirmed for cross-game parlays 10/21). Send to Hard Rock = share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/<id> for ONE leg, hardrock://betslip/<id>,<id> (app scheme; app must be installed) for 2+ legs - the share link only ever carries one selection (owner-tested 10/21). A book button is shown when any leg has that book's price and live only when the book prices every un-started leg.
- DraftKings' and especially Hard Rock's alt ladders are sparser than FanDuel's, so many prop legs have no exact rung at that book. hrswap.py gives such legs l.alt = {dk, hr}: the book's nearest rung (within MAX_GAP per market, inside the model ladder's range +/- one spacing) with its price/id and the model's probability AT THAT LINE (probit interpolation between the two neighbouring rungs of the player's raw ladder; linear probit fit only beyond the ends; clamped monotone; calib.shrink against that book's implied price). Send to DraftKings / Send to Hard Rock use the exact rung when the book posts it and the nearest line otherwise, automatically (owner's call 10/21: one tap, no per-leg swap UI); the note under the send buttons lists every substitution ('Send to DraftKings uses its nearest line where it doesn't post ours: Chase Brown 50+ (-113) for 51+. The prices and model % on this slip are FanDuel's.') and the 'Same slip at each book' row marks a substituted price with ~. The slip, edges, fair odds and grading stay against FanDuel; a substituted line is never a promoted bet.
- Game lines at the other books: FanDuelOdds.gs v2026-10-21 adds h2h/spreads/totals + alternate_spreads/alternate_totals to the per-event call (+5 credits per game) and writes DraftKings' and Hard Rock's as 'gl|<Away @ Home>|<Market>|<Side>|<Point>' rows in AUTO - Book Odds. glbooks.py joins them onto game-line legs in build_builder.py and build_boards.py: same number -> l.bks[book] (exact); different number within 3.5 (spread) / 4.5 (total) -> l.ba[book] with the model's chance at that number (leg chance moved by the ratio of gamelines.py's margin/total normal at the two numbers; no second blend - game lines are already market-anchored); moneylines never substitute. Field names: l.bks = exact book prices, l.ba = book alternatives (NOT 'alt' - on game-line legs l.alt is the FanDuel alternate-spread/total flag the builder's floor and quick-build filters read; a clash there in v216-v220 made quick builds and floor legs skip any leg with a book alternative).
- Before pushing a JS edit to gen-overrides: extract the page's main <script> and run node --check on it (an inline // comment on a one-line template swallowed a brace on 10/21 and shipped a dead builder).

## Injury-shaped games (injweeks.py, owner 10/22) - an injury is not a role change
- Rule from the owner (TreVeyon Henderson / Corey Kiner, Week 7): when a player is hobbled or leaves a game and backups get more snaps, that is NOT the starter losing his role and NOT the backup winning it. Notice the injury.
- injweeks.py reads nflverse snap_counts_<season>.csv and injuries_<season>.csv (build_snaps.py downloads both into in/ in Step 2b, so Step 2b must run before Step 3) plus in/avail.json. A player's game is INJURY-LIMITED when his snap share fell below 75% of his own median in other games (median >= 25%) AND an injury explains it: on that week's report (Questionable / Doubtful, or Limited / DNP with an injury), on the next week's report, or he missed the team's next game. A week he sat out hurt is ABSENT. For a same-position teammate, those weeks are FILL-IN weeks only if his own share rose 8+ points AND the hurt teammate is back this week (on this week's report as anything but Out / Doubtful, or played the team's latest game; anyone OUT on the availability tab - IR, released - is never back).
- build_snaps.py sets those weeks aside before computing season / last-two / trend, so the sheet's snap-decline factor (column J, reads the Trend) no longer cuts a player for a game he played hurt; the Signal column says e.g. 'STABLE (injury wks 5,6 set aside)'.
- flags.py: form, usage, floor, snaps and main-line hit-rate reads use healthy, normal-role games only. New flags: 'Healthy again' (info: recent games were injury-limited, he is off the report or full in practice - not a lost role; the projection may still understate him), 'Playing hurt' (watch: same, but still on this week's report), 'Fill-in fading' (watch, rotational players under 60% snaps only: his bump came while a teammate was hurt and that teammate is back / may return). The sheet's Role Down signal on an injury-limited player and Role Up on a fill-in player are shown as info, not bad / good. 'Rising: X' (next man up) now requires the player's OWN last-two share to be 5+ points under his season share - a teammate gaining time is not him losing it - and never counts a riser whose gain was fill-in for a hurt teammate who is back.

## Target competition (flags.py, 10/21)
- A WR/TE leg gets 'Target competition' when a same-room body is arriving: (a) a returning starter with NO 2026 game log, entered on AUTO - Weekly Availability this week as QUESTIONABLE / CLEARED / ACTIVE with 'returning starter', 'season debut', 'first game back', 'activated' or 'back this week' in the reason (Tank Dell 10/21 - the game-log based teammate-returning check cannot see a player who has not played all year, so Step 2a MUST enter such players on the tab with that wording); (b) a receiver traded in within the last two logged weeks who drew 4+ targets in his first game (Marvin Harrison Jr. to HOU, Week 6). Depth players surfacing in the log are NOT competition (injury symptom). BAD (out of every listed parlay and quick build) when the player's own last-3 targets are below his season rate and he is not the room's primary target; otherwise a watch. Step 2a: when news says a long-absent receiver is set to play, add him to the availability tab with the wording above - that is what arms this flag.

## Coverage (Mike Clay WR-CB cheatsheet) - 'AUTO - WR CB Matchups'
- The owner loads Clay's ESPN WR-CB cheatsheet each week (PDF when he has it, screenshots otherwise - Week 7 was three screenshots transcribed by hand into rows 83-166; the Week 5 PDF load defined the 44-column layout, Week 7 added AS/AT 'Clay Matchup T/R delta' / 'F/R delta'). Primary CB = the corner with the highest alignment exposure (WR LWR% x CB RCB% + Slot x Slot + RWR x LCB%); AI-AR are sheet formulas (sample status, alignment defense rank/score, CB favorability z-scores within the week, signals, flag). Note: from Week 7 the Alignment Def Score is (16.5 - rank)/15.5 so POSITIVE = easier (rank 1 = allows the most FF points, per the ESPN key); the Week 5 rows used the opposite sign.
- flags.py reads the current week's rows (in/wrcb.json) and adds one flag to every WR receiving leg (rec yds, receptions, longest rec, anytime TD, rush+rec): 'Coverage edge' (good) when Clay's deltas are >= +8% targets AND >= +0.15 pts/route; 'Tough coverage' (WATCH, not bad - first week in the pipeline, does not gate parlays) when <= -8% AND <= -0.15; 'Coverage' (watch) when the sheet flag is DIFFICULT; info otherwise. Text names the corner, his exposure, the corner's targets/pts per route allowed and Clay's deltas. build_boards.py cov_strip() puts a 'Coverage' line on every game card: each team's receivers by projected target share with their primary corner and ▲ / ▼ / ·.
- Promote 'Tough coverage' to a bad flag only after a graded week shows flagged legs under-hit (grade Week 7 WR legs by coverage flag on the Tuesday receipt).

## Accounts (optional sign-in)
- gen/account.py holds the Supabase project URL + anon key (public by design), the sign-in dialog, the storage-sync script and the /me/ page. build_site.py imports it: every page gets the header "Sign in" button and loads supabase-js + /account.js (deferred); /me/index.html is written each build. Nothing on the site requires an account; signed in, the bs_* browser-storage keys that hold what a person built (saved slips, builder slip, trade scenarios, hand-built team, Sleeper username/league) are mirrored to the user_state table (gen/account.sql, run once in the Supabase SQL editor; row-level security = own rows only) and merged back on any device. Do not add analytics or write anything else to the account without the owner; the privacy page (build_legal.py) describes exactly what is stored. /me/ grades saved slips from site/data/box-w<W>.json (build_mydata.py); promo cards carry a Tail button (home.py) that saves the promo as a slip {id: promo-<W>-<slot>, keys: the builder keys build_promo.py puts on each leg}; totals and first-TD legs grade as pending for now.
- If the Supabase project changes, edit SUPABASE_URL / SUPABASE_ANON in gen/account.py; set GOOGLE = True only after the Google provider is configured in Supabase (Authentication > Providers) - the button then appears in the dialog.

## Home page: picks skip role-risk players; every bet has DraftKings / Hard Rock buttons (owner 10/22)
- home.py `_flagged()`: a player is never a Top Play / TD play / floor leg / next-man-up pick when the leg has a bad flag, or the player
  has a bad ROLE flag in the builder's `pf` (Target competition, Backfield competition, Rising, Limited, Snaps down, Role Down, Carries
  down, Targets down, Cold L3, Fill-in, Usage falling, Boom/bust). Trail script removes rushing / rush+rec / TD legs only. Context flags
  (Tough matchup, low O/U, main-line hit rate) do not remove a pick. Trigger: Hutchinson (target competition) and Lloyd (Jacobs back,
  Strong ahead) were Top Plays on 10/22 because top_plays() only checked a keyword list.
- flags.py Backfield competition (RBs): a same-team RB returning starter with no 2026 game log on the availability tab -> BAD for every
  other back; the text names any teammate who out-carried him last game.
- booklinks.py builds DK / HR links with the betslip rules (exact rung, else the book's nearest line, ≈ marks a substitution).
  home.py puts DK / HR buttons on play cards, next-man cards, game-line cards, the floor slip and the best parlay; build_promo.py stores
  `books` on each promo (none for First TD / Either TD / estimated rungs - wrong market) and the promo cards show
  "Bet it on DraftKings / Hard Rock".
- build_boards.py best_parlay(): the same ROLE_RISK list keeps a leg out of the board's best parlay entirely (it used to stay in with a
  6% ranking penalty and a ⚠). Context flags still cost 6% each; 3+ still drop the leg. The home page's "Best parlay" reads this file.

## Promo prices: same-game parlays use FanDuel's SGP price, never the legs multiplied (owner 10/22)
- The Week 7 TNF SGP was written as +679 and the lotto as +8850 by multiplying the leg odds; FanDuel priced them +595 and +5337 (SGP
  pricing builds in the correlation - Henderson TD + Henderson 30+ rush yards especially). Column E of 'PROMO - Promoted Bets' for a
  same-game slip must be FanDuel's own SGP price (from the betslip / the owner), and build_promo.py no longer fills a blank E for a
  same-game slip. The model % on a same-game promo multiplies the legs as if independent, so treat its EV as rough.

## First games back: projection haircut + flag (owner OK 10/23, live from the Sat 10/24 rebuild)
- Backtest (nflverse 2019-25, RB/WR/TE): in the first two games after an injury-limited game (snaps < 75% of his median, median 25%+,
  injury on that or the next week's report) players produced 0.937 (train 2019-22) / 0.938 (test 2023-25) of their all-games average
  relative to players without one; vs their healthy-games average 0.83. The projection tabs average all games, so the factor is 0.935
  ('AUTO - Settings'!B278; 1 = off). Test MAE 28.24 -> 27.80 yds. No post-bye bounce either (post-bye -0.8 PPR vs own average, n=809).
- build_snaps.py marks those players RETURN in 'AUTO - Snap Trends' column M (written in Step 2b); J2's ARRAYFORMULA multiplies the snap
  factor by B278 for them. flags.py adds a 'First game back' WATCH flag with the history (it does not remove them from parlays).
- Why: the 10/22 injury-week change (set aside limited games in the snap trend) restored first-games-back players to a healthy baseline,
  which history says overshoots (Henderson 10/22: 9 rushing yards).

## DFS salaries - 'AUTO - DK Salaries' (added 2026-10-25)
- DraftKings: fully automatic. DKSalaries.gs (in the sheet's Apps Script project, separate file from FanDuelOdds.gs, no onOpen) reads DraftKings' public NFL lobby, picks the classic main slate (Featured tag, else most games, else soonest), and writes DraftKings' own player-list CSV (A:I) plus Updated / Draft group / Slate / Start (K1:L4) to 'AUTO - DK Salaries' every 3 hours (trigger made by installDKSalaries). On a failed pull it keeps the last list and writes 'Last error' in K6:L6. build_dfs.py embeds the list unless the slate started 2+ days before the build; the page loads it for DraftKings automatically, and a viewer's own imported file (showdown, other slate) takes precedence until the week changes.
- FanDuel: no public salary feed (it sits behind a login), so viewers import FanDuel's 'Download players list' file: drop it on the salaries box, choose it, or paste it. The page explains how to get the file on a phone (desktop-site mode in Safari / Chrome). Planned for Week 8: the owner drops the FanDuel file into the process each slate so FanDuel loads automatically too.

## Upgrades shipped 2026-10-26 (owner-approved list; nothing here changes a projection)
- Builder matchup chip + "soft matchups only" filter (build_builder.py isSoft): every player leg shows its opponent's rank vs that stat and position (season, L3; #1 allows the most) under the player line; the filter keeps legs ranked top 12 on both (game lines have no rank and drop out). Same definition everywhere the owner asks "does it pass the matchup test".
- "Build me a +N" in the builder's slip panel (build_builder.py genRun): target price, clean / soft / leave-out filters, 3-8 legs; scope = the game picked in the filters (same-game) or the whole slate with one leg per game. Beam search over the most likely open legs, finalists re-priced with joint() (model %) and with FanDuel's implied probabilities through the same correlations; same-game prices shown with ≈ as an estimate (0.85 / book-joint + 0.15, fitted on the owner's 10/25-26 quotes). Top 3 shown, "Load into my slip".
- Promo cards (build_promo.py): the slip's model % is now the builder's correlated joint (Gaussian copula with bd corr / glcorr, 100k draws, seed 7); the old leg product is kept per promo as p_indep. Tuesday (Step 5), after grade_promos.py, score both on every graded same-game promo: Brier of p vs Brier of p_indep against Cashed=1 / Missed=0, and write one dev-log row with both numbers and n. Do not switch methods on fewer than 20 graded same-game promos; report and let the owner decide.
- Promo checks (build_promo.py promo_checks): a card is HELD BACK (not shown on the home page) when a leg's player is in the builder but that market / line is not, when a game-line text matches lines in several games (write totals as 'Over 43.5 (KC-SEA)'), [10/29: when the row has its own FanDuel link / share code in F, only the several-games ambiguity still blocks - an unmatched leg becomes a warning and the card shows with 'Model price not available for every leg' (the 777s row: Jacobs Rush + Rec 70+ is not on FanDuel's current ladder, which only has 81+)] or when a game line comes from a different game than every other leg of a one-game slip. Warnings only for players missing from the build (their game started - the builder drops started games) and legs without a model price. The run prints 'PROMO CHECK FAILED - slot N ...'; put each in the summary and the dev-log row. Never edit the owner's row to make a check pass.
- Live promo grading on the home page (home.py PROMO_LIVE_JS): while a promo's games are on, the page reads ESPN's scoreboard + summaries every 60 s, marks legs ✓ / ✗, labels a card "Busted: <leg>" and hides it once that leg's game is final; all legs hit = "Cashed". A player with no box line stays open (inactive = FanDuel void). Display only; Tuesday grading from the game log is the record.
- My BetSweep exposure card (account.py): for the latest week's saved slips (+ the working builder slip), every player in 2+ slips with the stake and to-win riding on him; a line calls out anyone in more than half of the open slips. Also fixed 10/26: a syntax error ('+bet<small>') that had blanked the /me/ page script (live hot-fix 0d71827).
- Season page "Model vs market" (build_season.py disagreements_block): tally + game-by-game ledger of big game-line disagreements (win % 10+ pts off FanDuel's no-vig, margin or total 3+ pts off the line), 1u on the model's side at FanDuel's price (-110 when the archive has no odds). Display only. Promotion rule: the model's side may feed picks in a market only after 40+ graded disagreements there with positive units AND a model Brier below the market's on those games in both halves of the sample - then ask the owner.

## Game confidence + market's script (shipped 2026-10-27, owner 10/26 "where we're lacking")
- confidence.py, called by build_boards.py for every card. Display only: no projection changes.
- Grade = sum of flag points: market gap (model margin 3+ off FanDuel's main spread = 2, 5+ = 3; total 4+ off = 1), line moved 1+ pt since the first archived model call this week (2), QB change / starter with <=2 starts / QB questionable (2 each), newly-out players who played one of the team's last two games carrying 20%+ of targets or 25%+ of carries (1; 35% / 40% = 2), boom/bust QB vs a top-10-tough pass defense (1). 0-1 HIGH, 2-3 MEDIUM, 4+ LOW (LOW opens by default). Context (rest, bye, division, road) shown, scores 0.
- Market's read: endings from FanDuel's spread + total with the sheet's own formula (SD 13.5, blowout 9.5, shootout 50.5). The best parlay is weighted by the market's endings when a line exists (model endings otherwise) - backtest gbt/results.md (2019-26 nflverse closing lines, train 2019-23 / test 2024-26): market endings log-loss 1.245 vs formula 1.315, margin MAE 9.48 vs 10.27; best blend weight on the market = 1.0. The strips and the model's bar are unchanged.
- "Hit either way": best-parlay candidates with 60%+ chance under all four endings, no risk flags, priced within 3 pts of fair; up to 4, one per player.
- Summary card "Trust least" lists the 5 most-flagged games. Season page "Game confidence, graded" table: our margin miss vs the market's by grade, from 'AUTO - Confidence Archive' (step 2c). Do not re-weight flags until each grade has 30+ graded games; report the table in the Tuesday log row.
- SHIPPED 10/26 (owner: "whatever gets us closer to winning"): 'V2 - Game Scripts'!A5 now reads 'AUTO - Market Team Points' (new tab): per team, FanDuel's main spread + total for this week's game (main = odds closest to -110, game matched on both full team names in 'AUTO - FanDuel Game Lines') -> implied points (total - spread)/2; falls back to 'AUTO - Team Score Projections'!K (our formula) when no line is posted. Team Score Projections itself is unchanged, so player projections, kickers and DSTs are untouched. The scripts now move with the line until kickoff (injury / QB news gets in). Old A5: =IFERROR(LET(t,'AUTO - Team Score Projections'!A2:A33,o,...!B2:B33,pa,...!K2:K33,pb,...!L2:L33,FILTER({t,o,pa,pb},o<>"BYE",o<>"",t<o,ISNUMBER(pa))),"") - restore it to roll back. Consequence: the season page's "Game calls vs the closing line" and "Model vs market" will show little disagreement from Week 8 on; the confidence box shows our formula's read and flags its gap to the line.

## Closing line value (owner 10/27)
- Sheet script ClosingLines.gs (copy: gen/ClosingLines.gs.txt; owner installs once: Extensions > Apps Script > + Script "ClosingLines" > paste > run installClosingLines). Every 30 min it copies FanDuel's current price for every prop line whose game kicks off within 3 hours from 'AUTO - FanDuel Odds' into 'V2 - Closing Lines' (one row per week + line, overwritten until kickoff, so the last pre-kickoff pull stays). Tab created 10/27 with its header.
- 11/5: the Apps Script was never installed, so the tab stayed empty. The price-moves Action (.github/price_moves.py closing(), :12/:42) now keeps, per frozen leg (legsnaps Latest Snapshot TRUE), the newest mirror FanDuel price pulled after the freeze and before kickoff in data/closing-w<W>.json on main; sheets_pull.py merges those rows into in/closing.json in the tab's columns (sheet rows win). Nothing to install. The closing price is only as fresh as the sheet's last FanDuel pull before kickoff ('Pulled at' says when).
- build_season.py clv_block(): joins the frozen legs (Latest Snapshot TRUE) to their closing rows (week + lowercase key) and only counts a closing price pulled after the freeze. Shows, overall and per market (20+ legs): legs the model liked (raw edge >= +5) whose price shortened, their average move in implied points, legs the model faded that shortened, and "Market agreed" = share of legs that moved 1+ pt in the direction the model leaned (|raw edge| >= 2). Weeks 6-7 have no closing prices (nothing captured then) - the card fills from Week 8. Read it every Tuesday: a market below ~50% "agreed" over 300+ legs is a market where the model has no edge - say so in the log row before promoting legs from it.

## Short bet links, 2026-10-27 (shortlinks.py)
- Owner posts bets on X / Instagram; FanDuel's addToBetslip links are 400+ characters. Every promoted bet now has betsweep.co/b/w<week>-<slot>: a landing page (legs, model % per leg, FanDuel price, "Bet it on FanDuel", "Load into the builder", Share on X) with the promo's square poster as its X/OG card (copied to /b/<code>/card.png so it outlives promo/). build_site.py writes them from out/promos.json and prints "short links: ..." - put that line in the run summary so the owner can copy them. The home-page promo card shows the short link with Copy, the Share-on-X caption ends with it, and the posters' footer reads betsweep.co/b/w8-5 instead of betsweep.co.
- Builder slip panel "Short link": stores the slip in Supabase table short_links (no sign-in) and copies betsweep.co/b/?s=<6 chars>; /b/ renders it client-side (query string, not a path, so X's crawler gets a real 200 page with the BetSweep card - GitHub Pages would 404 a path). Visits are counted in link_hits via link_hit() (owner: Supabase > Table editor > link_hits).
- One-time setup by the owner: run gen/shortlinks.sql in the Supabase SQL editor. Until then the builder button says "Short links are still being set up"; the promo pages need nothing.
- posters.py = the promo poster module (was social.py until 10/26; social.py is now the Social page). build_promo imports posters - if a run prints "module 'social' has no attribute 'slip_image'" the bundle is missing posters.py.

## Model's Best tier, 2026-10-27
- Owner's target: picks that hit 65-70%. Built as a tier, tracked honestly. Tier rules live in build_builder.py (the NT block) and build_boards.py best_parlay():
  - even: FanDuel price -135..+115 and the model 8+ pts off the price on that side (unders: model's under chance minus FanDuel's under price; needs 'AUTO - FanDuel Unders' from FanDuelOdds.gs v2026-10-27). Weeks 6-7: unders 59% (n=393), overs 55% (n=104).
  - td: Anytime TD with raw model >= FanDuel implied AND price +200 or shorter (n=18, 10-8, +34% - small). Longer prices dropped: the full Week 6 pool at any price went 9-79 and bigger gaps did worse.
  - safe: CALIBRATED (shown) model % >= 65% ("top end pulled down": raw 80%+ only hit 59%, calibrated 65%+ hit 64-68%), raw >= price, no "Cleared this line in only" warning, best rung per player+market. Out of sample (fit Wk 6, test Wk 7) the 65%+ rule hit 61.6% at heavy juice, -5.5% - it is the "safer" tier, not the money tier.
- Home page "Model's Best" section (home.py model_best) and builder ?best=1 / "Model's Best only" show it; best parlays draw player legs only from the tier.
- Frozen each run to 'V2 - Model Best Picks' (step 3a); build_season.py best_block() grades it from in/gamelog.json at the frozen odds (over: actual >= line; under: actual < line; TD: rush TD + rec TD >= 1; players with no stat row are not graded).
- Revisit after Weeks 8-9: drop any tier whose units are negative two weeks running; do not tune thresholds on the week being graded.

## FanDuel addToBetslip rejecting valid selections, 2026-10-29 afternoon (owner: "Nothing is loading on fanduel from betsweep")
- Every FanDuel link on the site (home, boards, builder, social, promos) failed with the app's "Selection not added ... network issue, or it is no longer available" from ~1 PM CT, while DraftKings and Hard Rock sends worked. Ruled out on our side: the 14:51 odds refresh returned the SAME market/selection ids for the failing legs (Golden ATD 42.619720845/48301335; 2,058 of 3,174 build ids unchanged), FanDuel's own single-leg link format (marketId=..&selectionId=.., no [i]) failed identically, and the owner's third-party tail links from X failed too. Conclusion: FanDuel-side (endpoint or app build). Do NOT change the link format on this evidence; the bracket form marketId[i]/selectionId[i] worked through Week 7. If it recurs: test FanDuel's own link from column E of 'AUTO - FanDuel Links' first, then a desktop browser; if those fail it is FanDuel. The 'Refresh FanDuel links' menu item points at a function that no longer exists (refreshFanDuelLinks) - use 'Refresh now', which writes the Links tab; the dead item is removed in FanDuelOdds.gs v2026-10-29b.

## One betslip look on every page + Post to Social everywhere, 2026-10-30 (owner: "I want the betslip to look the same on all pages. On the matchup boards I can't post to BetSweep social... make it look like on the parlay builder. Make sure there's no bugs")
- template.html page slip (#bslip; boards, live, season, fantasy, DFS, first TD, trade) now has the Parlay Builder's action area: FanDuel / DraftKings / Hard Rock pills, Save / Copy / Clear, the "Post to BetSweep Social" card and "Short link"; "Other books" and "Open in Parlay Builder" moved to small links underneath. It exposes window.bsSlipLegs / window.bsGameKo (from the page's priced legs and their ko) - the same two hooks the builder gives social.py POST_JS and shortlinks.py BTN_JS.
- build_site.py wrap() appends social.POST_CSS / POST_HTML / POST_JS + shortlinks.BTN_JS to any page that has id="postsl" and no id="sdlg" (the builder carries its own, never twice). One copy of the posting code; both modules now fall back to #bslipFlags for messages and to __BSL.week / __BSW for the week.
- Guard: if the slip holds legs this page cannot price (added in the builder, or a page with no slip prices such as Fantasy), Post and Short link stop with "N of these legs are priced in the builder... open the slip in the Parlay Builder" - a post never silently drops legs.
- Tested (local site, stubbed signed-in account): boards and builder produce the identical feed_posts row (week, 3 legs with FanDuel ids, first kickoff, +185) and short_links row; a post opens /social/#p<id>; Fantasy refuses with the guard message; one #sdlg per page; builder page still removes the template slip (no double slip); no page errors.

## Strength of schedule, 2026-10-29 (owner 10/27 "do the others"; build_sos.py, tab 'AUTO - SOS Adjust', Leg Board H z_s)
- Two blind spots in the one-sided matchup factor: a defense's "allowed" numbers depend on who it played, and a player's season average depends on who HE played. build_sos.py fits, per position-stat, team-game totals y ~ L x a[offense] x b[defense] by iterative proportional fitting (pseudo-count K=4 toward 1 + 0.35 x last season's final factor), using the sheet's own game log for weeks < W. Per player: schedule divisor D = (m + 0.5 (S - m)) / m with S = sum of b over the defenses he has faced (D > 1 = soft schedule so far, his average is inflated); opponent factor stays one-sided, 1 + 0.75 x min(0, b[opp] - 1). Multiplier written to the tab = (1/D) x that / the sheet's own factor for the stat (reproduced from the same log with the weights in 'AUTO - Settings' B210:B215), so nothing is double counted; 1 = no change; Anytime TD, pass TD and TDs are untouched.
- Validation (scratchpad sos/: backtest.py, uniform.py, vsprod.py, hybrid.py, validate.py): nflverse 2019-26, parameters chosen on 2019-23, tested 2024-26 against the ACTUAL production factor - MAE lower on all 10 stats, 10 of 10 significant by game-level bootstrap, mean -1.2% (QB pass yds -1.2, QB rush -1.1, RB rush -1.1, RB rec -2.2, RB rec yds -2.5, WR rec -0.8, WR rec yds -0.6, TE rec -1.7, TE rec yds -0.7); Week 6+ only -0.85%. Every setting in the 18-cell grid (rho 0/0.35, divisor 0.3-0.7, factor 0.5-1.0) improved all 10 stats, none significantly worse, so the uniform middle was taken rather than per-stat tuning. Symmetric factors were rejected (QB rush yds, TE rec yds got worse vs one-sided). On the production pipeline itself (frozen Week 6-7 projections from 'V2 - FanDuel Leg Snapshots' x the walk-forward multiplier vs actuals, 836 player-market-weeks): -0.7% pooled MAE, CI [-1.5%, +0.2%]; Receptions -1.5% (significant), Passing Yards -2.1%, Receiving Yards -0.2%, Rushing Yards +0.3% (ns). Week 8 is the first week whose frozen legs carry it: grade it on the season page like any other change.
- Rollback: batch_clear_values 'AUTO - SOS Adjust'!A2:W700 (the Leg Board lookup falls back to 1) and skip the build_sos.py line in Step 2b. Since 10/29 (owner: "whenever you want to get to the SOS") the Fantasy and DFS pages carry it too: build_team.py (whose loader build_dfs.py reuses) multiplies each QB/RB/WR/TE's pass yds / rush yds / receptions / rec yds by out/sos_values.json F:I, moves the full-PPR total by the stat deltas (0.04/pass yd, 0.1/rush or rec yd, 1/rec; TDs untouched), prints "SOS applied to N of P players (M moved 0.3+ FP)", and shows an "SOS +0.7" / "SOS −0.4" chip next to the snaps chip when the move is 0.3+. If out/sos_values.json is missing it prints a note and the pages run unadjusted - so build_sos.py (Step 2b) must run before Steps 3.4 and 3.5. The trade calculator is rest-of-season (season ppg + age curves), not this week's matchup, so it does not take the weekly multiplier. Rollback for the pages: delete out/sos_values.json before Step 3 (or clear the tab as above).
- Caveat: fill-in starters and anyone not on a projection tab have no row (multiplier 1); combined "A / B" legs use the first name's row, like the market multiplier.

## Trade calculator: rookie picks + TE premium (owner 10/28, build_trade.py)
- Picks were priced far below the market (2027 early 1st = 1,221, rank 66). A pick is now priced as the player it becomes, the same way every player is: his first three seasons from the draft year (70% of the expected best-ppg as a rookie, then 100%) above the flex baseline plus a tenth of his points as a floor (players on a roster get a quarter), each season discounted 20% a year from today. FantasyCalc's pick rows ('AUTO - Market Values' Pos = PICK) are now matched to our ten picks (2028 early/mid/late from the 2027 ratios) and blended 30% like players. Check 10/28 vs FantasyCalc on the 0-9,999 scale: 2027 early 1st 4,606 vs 4,034 market (rank 19), mid 2,968 vs 2,656, late 1,933 vs 2,052, 2nd 1,407 vs 1,313; 2028 firsts ~20% above market (we discount less), 3rds below (busts are zero here).
- TE premium used to lower some tight ends (the bonus lifted TE18 too, so a low-catch TE lost ground). Now the replacement level is measured in base scoring (adj0) and each tight end's bonus rides on top: with +1.0 on, 59 of 60 TEs went up, none down (Bowers 5,284 -> 7,563, McBride 4,563 -> 7,098). Test: scratchpad tradetest3.js (serves up/out on :8812, dynasty on -> pick values, then TE filter with the premium off/on).



## Players, Usage trends, Who benefits, How-to guide, slip alerts (owner 10/30: "I love all of these let's try and do them all")
- plydata.py: one per-player season view (nflverse weekly stats + snap counts + injury report, this week's builder legs, statuses from in/avail.json first). Display only - nothing here feeds a projection or a price.
- build_players.py -> /player/ (directory, search + position filter) and /player/<slug>/ (slug = name lowercased, dots and Jr/Sr/II suffix dropped, non-alphanumerics -> "-"; two players with one name get -<team>). Pages share /player/player.css and /player/player.js. "+" writes the shared slip key bs_slipk_w<W> ("player|market|line", line rounded like JS Math.round) so the leg is in the slip on every page; the bar at the bottom opens the builder. The builder's player cards link "player page" with the same slug rule (plSlug in build_builder.py) - change both together. Owner 10/31: the builder's player NAME (list rows and cards, a.pname) links to /player/<slug>/ too, and the boards' icon next to each name (news_icon() in build_boards.py, class .newsl) now opens his player page in the same tab instead of ESPN news - ESPN news stays as the "News (ESPN)" link on the player page. build_boards.py _pslug() is a third copy of the slug rule. A name with no page (deep backup) or a shared name (-<team> pages) hits 404.html, whose script sends /player/<x>/ to /player/?q=<x>. Phone bottom tabs (APP_TABS in build_site.py) are exactly Boards, Builder, Fantasy, Live, Social (owner 10/30). Fantasy: after a Sleeper league is chosen only that league shows, with a "Switch league (N)" button (build_team.py, .leagues.picked). FanDuel screenshot import (owner 11/1, slipimport.py): /me/ has an "Import a FanDuel slip" card; build_site.py writes /import.js. The visitor's browser cleans the picture up (brightest channel, dark themes inverted, x2, threshold), reads it with tesseract.js from jsdelivr, matches each leg to this week's builder data and saves it to bs_slips_w<W> with the builder's own keys (Either TD as 'A or B|Either TD|1'). Drive / quarter props are listed as not imported. The builder's Saved slips header links to it. Weather-turn pushes (owner 11/1): push/slip-alerts.ts checks Open-Meteo for open-air stadiums 6h before kickoff and alerts users whose slips hold passing / receiving overs in that game (one push per game, push_sent player 'wx|<gid>').
- build_usage.py -> /usage/ (last 3 team games vs earlier, RB/WR/TE; injweeks.py tags fill-in bumps and played-hurt dips; Out/Doubtful players are left off) and /benefits/ (newly Out/Doubtful players with a real role: teammates' snaps / targets / carries / PPR with vs without him this season, weeks he left hurt excluded, weeks before his first game not counted as missed; no "without" games -> teammates' last-3 roles, no invented split; out-for-a-while players listed at the bottom).
- build_guide.py -> /guide/ (linked from every footer and a home tile). When colours, grades, tiers or the betslip change, change the matching paragraph in build_guide.py.
- Nav: Players and Usage added to the top menu; home tiles for Players, Who Benefits, Usage Trends and the guide.
- Slip alerts (web push): /me/ card "Slip alerts" (account.py PUSH_JS, public VAPID key in account.py) subscribes the device and saves it to Supabase public.push_subs; the service worker (build_site.py SW) shows the notification. Server: Supabase Edge Function "slip-alerts" (gen/push/slip-alerts.ts, no npm packages - RFC 8291/8292 in WebCrypto, tested 10/30 by decrypting a captured push and verifying the VAPID signature) run every 10 minutes by pg_cron (gen/push/push.sql with the cron secret filled in): reads the live builder data file on betsweep.co, ESPN's injuries feed (Out / IR / Suspension = OUT, Doubtful = DOUBTFUL), every user's bs_slips_w<W> + bs_slipk_w<W>, and sends one alert per user / week / player / status (public.push_sent) for games not yet kicked off, with a same-game swap idea (model edge > 0, 45-75%, healthy, not on his slips). The rebuild does nothing for alerts; the function, its secrets (VAPID_PUBLIC, VAPID_PRIVATE, CRON_SECRET) and the cron job live in Supabase. The VAPID private key and cron secret are NOT in this bundle. Limits: ESPN's feed carries injury rulings, not healthy scratches.

- 10/30 evening (owner: "group like props ... collapsible"; "do 1-4"): player pages group props into collapsible Receiving / Rushing / Passing / Touchdowns (anytime, first, 2+, 3+) / Unders sections - his position's main group opens, the rest show a one-line summary (lines, best edge); a "BetSweep's record on him" section from in/legsnaps.json (latest frozen copy of each graded leg: VALUE / STRONG VALUE W-L and units at the FanDuel price, every-line hit rate vs book %); schema.org ProfilePage data on each page. build_site.py writes site/sitemap.xml (every page this build made, plus receipts weeks; not /me/, /b/, /fantasy/) and site/robots.txt - step 6c copies both. The owner should add betsweep.co to Google Search Console and submit https://betsweep.co/sitemap.xml once.
- Slip alerts, 10/30 evening: the function also sends live updates during games (a leg on a saved slip hits or busts, a slip cashes; ESPN scoreboard + summary box scores, the same grading as the home page's promo cards; one combined note per user per run; push_sent remembers every event) and a Thursday "Model's Best is up" note (pg_cron at 15:00 UTC Thursdays with body {"mode":"weekly"}; legs with a Model's Best tier from the live builder data). Per-device opt-outs: push_subs.live / push_subs.weekly (gen/push/push.sql adds them), toggles on /me/.
- DFS salaries, 10/30 evening (owner: "let's do draft kings and if I can just upload salaries for Fanduel you can save that across the board"): Supabase public.dfs_salaries (site dk|fd, week, slate, csv). DraftKings: the slip-alerts function's mode "dk" (pg_cron every 3 hours, gen/push/dfs.sql) reads DraftKings' public lobby + draftables (the Google Apps Script DKSalaries.gs was blocked with 403s) and stores the main classic slate as DraftKings' own CSV. FanDuel: the owner loads FanDuel's player list on /dfs/ and taps "Share these salaries with everyone" (shown only when bs_is_admin() says the signed-in account is the owner's). The DFS page loads the shared list for this week for every visitor unless they loaded their own; build-time 'AUTO - DK Salaries' embedding still works as a fallback.
- Short-link pages, 10/30 night: Save slip (writes bs_slips_w<W>, so it shows on My BetSweep, syncs, and gets alerts); /b/?p=<id> opens a Social post as a short-link page (tapping a post on /social/ goes there); /b/books.json now also carries this week's FanDuel ids per leg, so every short-link page rebuilds its FanDuel link from current ids (FanDuel re-issues prop ids during the week).
- Home page, 10/30 night (owner: "add players on the home page to my betslip without jumping to the parlay builder"): every "+ Builder" link is a "+ Slip" toggle writing bs_slipk_w<W> (multi-leg cards: "+ Add all to slip"); a bar at the bottom counts the legs and opens the betslip. Cmd/Ctrl-click still opens the builder.
- Injury-limited override, 10/30 night (owner on George Pickens: "He wasn't injured. He just lost blocking snaps to Flournoy"): 'not injury-limited' in a player's reason (column J) on this week's 'AUTO - Weekly Availability' row tells injweeks.py his low-snap games were not the injury - no first-game-back flag or RETURN haircut (build_snaps.py column M), no teammate fill-in tags; his game status is untouched.


## Risk layer: live injury / weather / owner notes on every page (owner 11/1: "Injuries and weather seem to be the biggest challenges for us today")
- Supabase table risk_feed (risk.py SQL; owner ran betsweep-risk.sql): rows `inj|<player>` and `wx|<game>` are written every 10 minutes by the slip-alerts function (ESPN injuries for on-board players before kickoff; Open-Meteo wind 15+/gusts 28+/rain 60%+ in the 24 h before kickoff, with the game's QB/WR/TE list) and expire 25 minutes after their last refresh; `note|<player>` rows come from the owner's panel on player pages (only bs_is_admin() can write them).
- /risk.js (risk.py, script tag in every page head): chips next to player names (Out / Doubtful / Questionable / Weather / BetSweep note), ruled-out players cannot be added (builder toggle + any button[data-k]), a pill when the open betslip holds an at-risk leg with "Remove ruled-out legs", and `window.BSRisk`. Class names are bsr* - the boards already use .rkc for rank chips.
- Builder: quick builds and the generator skip any leg BSRisk.avoid() marks; each betslip leg shows "Some risk" / "High risk" (riskScore: model flags bad 3 / watch 1 / good -1 plus live list out 10 / warn 3), and the slip notes count high-risk legs.
- Promo watch: build_site writes /b/promos.json; slip-alerts pushes the owner "Promo at risk" when a LIVE promo leg is hit by an injury, a weather turn or a note before kickoff (deduped in push_sent as promo|code|player|tag).
- Owner notes reach the rebuild through the GitHub Action .github/workflows/risk-notes.yml (every 30 min -> data/risk-notes.json) and Step 2a's risk_notes.py.
- flags.py (11/1, owner-directed, review in Week 8 grading): steady rain at kickoff (rain with 50%+ or any precip 70%+) is now a 'bad' Rain flag for QB/WR/TE (was a watch note for everyone) and a 'good' Rain = run game flag for RBs, like wind; lighter rain stays a watch. New 'Playing through it' watch flag: on this week's report (not Out, not practising in full) after his last game's snap share fell to 75% or less of his season share (season 45%+), when the injury-limited read has not already flagged him.
- Feeds branch (11/1): .github/workflows/feeds.yml mirrors ESPN (injuries, scoreboard, game-day inactives for games within 3 h) and builds weather.json (ESPN home team/venue + Open-Meteo kickoff hour) every ~10 min to the orphan branch `feeds`. The slip-alerts function falls back to it whenever ESPN blocks Supabase, and Step 2 reads weather.json through weather_feed.py.
- Game-day inactives (11/1): slip-alerts checks each game's summary for players listed Out on game day (inactives post ~90 min before kickoff) for games within 3 hours; they become OUT ("Inactive") in the same run, so slip pushes ("X is INACTIVE tonight"), risk chips and the promo watch all fire.
- Promo swap (11/1): the "Promo at risk" push names the best clean replacement from the same game and market (no model warning, not on the risk list, similar line, model within 8 pts) and opens /build/?new=1&add=... with the swapped slip (new=1 replaces the open betslip).
- Anytime-TD calibration audit (11/1, weeks 6-7 legs + weeks 2-7 projections): overall calibrated (32.5% predicted vs 34.0% hit; Brier .218 vs book .223); WR over by ~6 pts, RB under by ~7-10, 50%+ calls too high (60% -> 47%). No recalibration held up out of sample - re-test logit p' = -0.283 + 0.804*logit(p) once Weeks 8-9 are graded. Model-over-book "value" TD legs (edge 5+ pts) hit 20% (n=25): treat big model-vs-book TD gaps with suspicion.
- Who should I start? (11/1, owner): /team/compare/ (build_startsit.py, called at the end of build_team.py; build_site places out/startsit.html + startsit.json as /team/compare/ + data.json). Search bars with + for more players; full/half/standard scoring and Best bet / Safe floor / Upside modes; the pick = projection adjusted for injury status (live risk list too), flags and the floor/ceiling band from his own game-to-game spread; reasons name the projection gap, matchup ranks, volume, snaps and the top flag. Linked from the Fantasy menu and a banner on /team/.
- Stale eligibility fix (11/1): 'V1 - Eligible Fantasy Projections' still carried Week 6 opponents and marked Saquon Barkley, Stefon Diggs, Caleb Williams, Jordan Mason and 17 others OUT/IR on the Week 8 Fantasy page. build_team.py now counts a V1 designation only when its opponent is this week's opponent, and this week's availability tab (CLEARED / ACTIVE / QUESTIONABLE) overrides it. Live /team/ data was patched 11/1 against ESPN's injury report.

## Picking better legs (owner 11/1 after SNF: "Can we identify when the model's projections are more likely to be wrong and adjust?")
- Study 1 (nflverse 2019-25, fit 2019-24, test 2025 + 2026 wk1-7): the closing spread predicts margin far better than any baseline (MAE 9.7 vs 11.1) and P(favorite wins by 14+) = 17% / 24% / 37% / 48% for spreads 0-3 / 3.5-6.5 / 7-9.5 / 10+. Players lose snaps in ACTUAL blowouts (WRs -7.7 pts of snap share, -12% targets when won by 17+; veterans -10 pts) but the pre-game spread predicts only ~1 pt of it, and a spread-based player multiplier did not hold up out of sample - not promoted. Veteran WRs on 7+ point favorites: -13% rec yds, -15% PPR (2019-24, n=137; 2025 n=24 same direction) -> flags.py WATCH "Blowout rest risk" (FanDuel spread from gamelines.json first, nflverse spread_line second; veteran = 8+ years or age 30+ from in/roster_2026.csv). Big underdogs do NOT get extra pass volume pre-game (team attempts -3%).
- Study 2 (graded legs Weeks 6-7, n=3,298): model 10+ pts above FanDuel said ~65%, hit ~50% (still +6% units - right direction, overstated size); small samples (<=3 games) the book was better; passing-yards legs hit 64% vs model 52% (model low); a 50/50 model-book blend beat the model alone in both weeks out of sample. build_builder.py adds WATCH "Market disagrees" on legs 10+ pts above the book and INFO price-shop notes ("Better price elsewhere" / "Best price: FanDuel", 3+ implied pts vs DraftKings / Hard Rock on the same leg). Re-test the blend on Week 8 before it changes edges.
- Pending study: red-zone share vs TD history for anytime TDs, target/carry-share trends, neutral pace / pass rate, opposing defensive starters out, QB scramble vs pressure (nflverse play-by-play).
- SHIPPED 11/1 (owner: "You have my OK to change whatever you think needs to change ... to get our overall percentage higher"): builder leg % = 50% model + 50% FanDuel implied for yardage / reception / longest-catch legs (Anytime / First / 2+ TD keep the model; game lines unchanged). Weeks 6-7 out of sample: log loss better than the model alone in both weeks; the 200 likeliest legs hit +1 to +2 pts more. Edges are about half their old size (same order); the parlay generator's edge floor moved -0.04 -> -0.02 to match. l.pm = the model's own %. Re-check with calib_market.py every Tuesday; revert if the blend loses to the model two weeks running.
- SHIPPED 11/1 (owner: "Start with 1-4"): (1) listed parlays stay short - boards best parlay is already 2-4 legs, builder quick builds 3/4/5, generator default 4 (the owner can still pick up to 8 by hand); promos the assistant proposes aim for 3-5 legs and climb a rung instead of adding legs. (2) No -250-or-shorter legs in quick builds, the generator or the boards best parlay unless the leg's % is at or above the price (model + market). (3) Builder player cards default to the rung 10-25% under the projection (best edge among those; Longest Reception and TDs keep the -110 rule). (4) Model's Best: Longest Reception dropped, Rushing Yards need raw model 5+ pts over the price; the boards best parlay uses the same rules.
- Returning starters on the boards (11/1, owner: "How come Charbonnet's not on our matchup boards"): build_boards.py adds a row tagged RETURNING STARTER for this week's availability rows (CLEARED / ACTIVE / QUESTIONABLE) whose reason says "no 2026 game log" (RB/WR/TE), projected with returning.py exactly as the builder prices him (last year's share x team volume, first-game discounts). Step 2a must keep writing "no 2026 game log" in J for those players.

## Deep dig (owner 11/4: "how we can become more efficient and successful overall") - 4,929 graded FanDuel legs, Weeks 6-8
- The priced pool loses 8.1% at a unit each (49.1% hit vs 53.8% implied); FanDuel shades favorites: every price band from -130 to -300+ hit 5-9 pts under implied (-9 to -12%), plus-money legs as a whole broke even (+1.2%). "Floor" legs are the worst product, not the safest.
- By market: Rushing Yards -19% at every line depth and on BOTH sides (Model's Best Week 8: rushing overs 24% hit, rushing unders 31%) - actual/projection has a median of 0.75-0.81 with a long right tail, so a symmetric hit % is wrong. Longest Reception -12% (already dropped). Receiving Yards -7%, Receptions -7%. Passing Yards +4%: the projection runs 6-7% low, lines ABOVE the projection hit 63% (+19%), floors lose. Anytime TD +3%: scorers at +151 and up +8% (246 legs), favorites -8%.
- Edge works only at plus money: raw model 10+ pts over the book hit 50% vs 49% implied (+5%) overall, but at +150 or longer the +5-pt-edge legs went 41% vs 32% implied, +31% at 1u (150 legs, positive Weeks 6 and 7, -2% Week 8); at -200 or shorter the same edge lost 21%. Model fades (edge <= -10) lost 12% - the direction has information, the size does not.
- Model's Best Week 8 (245 frozen legs): 45.7% hit, -17% - the even tier was the worst line on the site. SHIPPED 11/4: new tier "plus" (+150 or longer, raw edge >= +5, rec yds / receptions / ATD / passing / longest; overs) leads the home page and the builder tier filter; Rushing Yards out of every tier; the safer tier off the home page; copy rewritten with the Week 6-8 numbers.
- SHIPPED 11/4 (build_builder.py, before calib): Rushing Yards and Passing Yards leg chances come from the empirical actual/projection ratio distribution of the graded legs (one ratio per player-market-week) instead of the model's symmetric number; 3-fold out-of-sample log loss (blended 50/50 with the book) better for rushing in all three folds and passing in two; receiving / receptions were worse with it and keep the model. Revert if raw beats it two graded weeks running (calib_market.py drift table).
- Also 11/4: home-page top plays skip Rushing Yards and anything -200 or shorter; the Floor legs section + floor slip are off the home page; the boards' best parlay skips Rushing Yards entirely.
- Unders (11/4 estimate on the 3,716 frozen over legs, under price = 1.07 - over implied, no real prices): unders overall break-even (-3%); the one cut that looked real was rushing-yard unders where the over is -200 or shorter (+16%, n=154) - consistent with rushing overs being the worst product. Real prices now freeze every run ('V2 - Unders Snapshots'); unders_check.py grades them from Week 9.
- Promos went 0-28 in Weeks 6-8 (all Missed). Parlays of 50-60% legs cannot post a record; PROMO_DESK now builds core slips from 2-3 plus-money edge / TD legs and adds a daily singles post (3-5 plus-tier legs) - the product whose record is worth showing.
- Efficiency (DONE 11/4, owner: "do what you think with the rebuilds"): the rebuild schedule is now 8 runs a week - morning run trig_01VKDuEUicorttyff7XL4a5D at 7:40 AM Tue/Thu/Sat/Sun (the only run that does Step 5 and the Boards Archive), afternoon run trig_011jY6sHm8qJEkssdPhd3MRu at 3:40 PM Tue/Thu, Sunday midday trig_01Gc3ve4rMdcohD7rEYcyZRz at 12:40 PM, plus the 9:52 AM Sunday weather rebuild. The Saturday bet brief (sheet-only, pre-site) is disabled - the Wednesday drafts, the Saturday check run and the boards cover it. Was: 13 Opus rebuilds a week (Tue/Thu/Sat/Sun x3 + Sunday weather) at 35-45 min each; two of yesterday's three failed on a usage limit and the Sunday inactives check has failed the same way. The sheet-mirror branch now removes the three big reads from every run. Recommended cadence (owner to approve): Tue 7:40 + 3:40, Thu 7:40 + 3:40, Sat 7:40, Sun 7:40 + 9:52 (weather) + 12:40 - 8 runs instead of 13 with nothing lost (the 12:40 Tue/Thu/Sat and 3:40 Sat/Sun runs change almost nothing).

## Live "from here" grading + FanDuel affiliate hook (11/4, owner "let's do it all" items 3 and 7)
- feeds.py (site repo, every 10 min on game days) now writes livelog.json (every in-progress game: score, period, clock, possession, red zone, full box score; rolling 10 days) and pins livelegs_w<W>.json the first time a week has a live game, from /b/live-legs.json (written by build_live.py via build_site.py: the tracked player legs with the pregame chance the page showed). Pinned once, never overwritten -> a later rebuild cannot leak in-game information into the replay. live_grade.py (gen) mirrors the page's chanceNow() math in Python; if build_live.py's formulas change, change live_grade.py the same way.
- Affiliate: template.html carries a click hook that reads /b/aff.json ({"fd": ...}); build_site.py writes it from the sheet's 'AUTO - Settings' row **FanDuel affiliate** (col A exactly that, col B the value). Value with `{url}` = tracking template wrapping the URL-encoded deep link; anything else = query params appended. Empty/missing row = {} = nothing changes. The deep links in the markup, the sheet's link formats, copied links and the Supabase shortlinks are untouched; when the owner has a tag, the shortlink redirect (shortlinks.py SQL) and the promo posts are the two places still plain - one change each, with the owner. Footer disclosure ("may earn a commission") already exists on every page.

## Context desk (11/4 evening, owner: "take news into account", "what else can we add... game importance, local news, trending names")
Shipped as RUNBOOK Step 2a-ii. Sources (all mirrored to the `feeds` branch by .github/feeds.py, which the sandbox can read via git): ESPN NFL news API, ESPN team injury pages (one beat line per player - the best role source), RotoWire / CBS / Yahoo / PFT / NFL.com RSS, ESPN core-API depth charts (hourly, with each player's ESPN injury status), Sleeper + ESPN weekly projections (hourly), nflverse injuries / snap counts / schedules (direct). Scripts: news_desk.py, depth_check.py, def_inj.py, stakes.py, role_rising.py, consensus.py, context_grade.py; flags.py reads in/ctx_*.json (CTX player notes -> flags; CTX_G -> build_boards ctx_strip() "Context" line on every game card; CTX_CB -> Corner out / questionable in the Coverage flag). First catch, before the checker was even finished (11/4 9:40 PM): Sam Darnold ruled out (quad) for ARI-SEA, Drew Lock starts; Garrett Wilson in concussion protocol; Brissett traded to BAL - none of it was in the sheet. Not done yet: referee assignments (nflverse has no 2026 referee column yet - stakes.py prints the crew note as soon as it does), Yahoo projections (OAuth), beat-writer X accounts (no API), the "Manual Opportunity Adj" lever (a production formula change - owner + backtest first). Hypotheses to grade before anything changes a number: trending-as-fade (context_grade.py), below-consensus = stale input, one-sided defense multiplier (BUF-MIN / CHI-SEA shape: the Rush/Pass Yds Matchup columns only ever subtract - test a two-sided version on Weeks 6-9 before touching it).

## Items 6 and 7 of the context list (owner 11/4 10:48 PM: "just go ahead and do 6 and 7") - tested, NOT promoted to inputs
- (6) Volume quality / snap-trend direction (research/tprr_study.py, .txt): nflverse 2025 + 2026 weekly stats x snap counts, routes proxied as offense snaps x team dropback rate. On 2025 a snap-trend multiplier (k=0.6) and TPRR x routes both beat the season average for targets (MAE 2.05 -> 2.02 / 1.99). On 2026 neither did (2.15 -> 2.18 / 2.17), and on this model's own frozen Week 6-8 projections the multiplier made rec yds worse (MAE 22.2 -> 22.6) and receptions worse (1.63 -> 1.66): players whose snap share rose 15+ pts delivered 9% UNDER the projection (n=60), those whose share fell 15+ beat it by 11% (n=29). The model's recent-game weighting and the Snap Trends factor already price role changes, if anything too hard. Decision: no multiplier; role_rising.py's flags were flipped to say so ("Role rising" = watch: do not pay extra for the name; "Snaps falling" = info: not a fade). Tuesday follow-up (Nov 10 reminder, item j): re-run with Week 9 graded - if rising-snap players under-deliver and falling-snap players over-deliver two weeks running, propose DAMPENING the role lean (shrink the recent-game weight / the Snap Trends cut), with a 3-fold OOS test first.
- (7) Referee crews (research/ref_study.py, .txt): pbp 2023-2026 + games.csv referee / closing totals, 881 games. Crew penalty and DPI rates do not persist season to season (r = 0.21 / 0.14), and 2023-24 crew rankings did not predict 2025 totals - the high-scoring crews reverted (-0.7 vs the line) while low-penalty crews ran +3.1 (n=97), i.e. noise. Decision: the crew is never an input; stakes.py keeps a one-line info note when nflverse carries the assignment (it does not for 2026 yet) and says so. 2026 penalties are up (15.1/game vs 12.7 in 2025) - league-wide, not crew-specific.

## /today/ + the morning brief (11/4 late, owner: "Sleeper, FanDuel, BetSweep - the few apps on the phone during football season")
- build_today.py (Step 3b2) builds /today/: one scroll for the day. The browser picks "today" from the kickoff stamps in America/Chicago, so one build serves Thu-Mon (a game day stays "today" until ~4 am; with no game today it shows "Next up: Sunday"; after MNF it points at receipts). Cards: FanDuel spread/total (in/gamelines.json: home team's point, Over's point) + model score/script, weather + short-week chips (flags WX / CTX_G), the news desk's notes for the two teams, the 3 best plus/TD-tier legs (home.play_card, so + Slip and the FanDuel / DK / HR buttons work), the best parlay, links to the card / builder / Game Desk / live. With 3+ games the cards collapse their looks behind a "Looks & parlay" toggle and a "Today's looks" grid (top 6 by raw-model-minus-price, cloned from the cards) leads the page. "You today": slip legs in today's games (bs_slipk_w<W> + bs_slips_w<W> vs the leg keys per game embedded in the page), your Sleeper roster vs the news (reads the username / league the Fantasy page saved, Sleeper's public API, marks your players' news red), or a "Connect your Sleeper team" row. Share = html2canvas of the first game card -> Web Share / download. manifest start_url = /today/?source=app; bottom tabs = Today, Boards, Builder, Fantasy, Live (Social moved to the menu); top menu gets Today after Home.
- /b/today.json: {"briefs": {"YYYY-MM-DD": {"title", "body", "url"}}} per game day - the Edge Function's new mode "brief" (owner/slip-alerts.ts; reference copy push/slip-alerts.ts) sends it at 9:05 am CT to every subscriber with the weekly preference on, once per date (push_sent player = __brief__<date>). Owner: deploy the updated function and run owner/betsweep-brief.sql once (secret stays in owner/; never in the bundle).
- Short view /short/ - shipped the afternoon of 11/10 as "Simple view" at /simple/ and renamed that evening (owner: "Let's call Simple view, Short view instead"): every word a visitor sees and the address say Short, /simple/ is a redirect page build_site.py writes, and a phone that stored bs_view=simple is treated as short. The generator files keep their names (build_simple.py, out/simple.html, out/simple.json, tests/simple_view.py). (owner 11/10: casual friends "want to just open up the app and everything they could want is right there and not have to do any extra reading"; "Just make sure that simple mode stays with the same overall aesthetic. Let's just push it to the site"). build_simple.py is NOT a step of its own: build_site.py calls build_simple.build() last, right before it places the page, so the page always shows this run's final promos, Sweep says lines and best parlays; it prints "wrote out/simple.html (Short view, /short/): week W, G games, E easy picks, house slip yes|none posted, Sweep says lines N" (or "note: Short view not built this run: ..." - then say so in the summary). What is on it, top to bottom: the Daily Sweep when one is LIVE and not settled; "3 easy picks" (three favorites priced -350..-140 that the model has at or within two points of FanDuel's price, risk score under 2, overs only, one per player, two per game at most, each with FanDuel ids - fewer than three qualify and the card is left out) behind one "Bet all 3 on FanDuel" link; then every game as one row (the moneyline side the model has higher, its chance, the projected score when it agrees with the pick) that opens to the game's Sweep says line, its best parlay with a Bet link, and a link to the full board. No new modelling: every number is the full site's. Looks: it is a plain page source, so the template gives it the header, fonts, palette, dark / light and the playbook background; inside it uses the brand layer's own pieces - .seg for the Short | Full switch, .bsbtn for buttons, .brush under section titles - and the home page's card and Sweep says shapes. Keep it that way: no colours or fonts of its own. Switch: Full is the default for everyone. The home page head carries a "Short view" pill (build_today.py) and the nav has the entry; tapping the pill, or "Make this my home page" on /short/, stores bs_view=short on the device, after which the bare home address (and the installed app's /?source=app) opens /short/; any other query, any hash and every other page are left alone, and "Full" on /short/ stores bs_view=full. Opening /short/ from a shared link changes nobody's home page. Kicked-off games drop out in the browser (a day with nothing left loses its heading; the easy picks go once one of their games has started), and a player ruled out since the build is struck with the one-tap button removed, because the link still carries him.
- Sweep says leads (owner 11/10: "If we're having sweep says say take the unders but our best parlay for this game says over 45.5 and Vikings ML I feel like there's an issue" / "I'd roll with sweep says more often"). voice.json "leans" (Step 1v) is the only input - the text of a line is never parsed, a game with no line has no lean, a lean naming a team that is not in the game or a total that is not under / over is ignored. With a lean, build_boards.py best_parlay() (a) drops the game line on the other side (the over under an unders call; the other team's moneyline and spread under a side call), (b) drops any leg that is 10+ points likelier in the ending the line fades than in the one it calls (unders: shootout vs close-low; overs: the reverse; a side: the other team winning by 10+ vs this one), and (c) first looks for a slip that carries the line's own game leg (the under itself, the side's moneyline or spread) and takes it when it is within 5 cents of fair, otherwise the best slip left. The chances and EV printed are never tilted by the lean - only which legs may be used changes. The card says "Agrees with Sweep says (the under)" or "Rebuilt to agree with Sweep says (...)" (hover / long-press shows what the run would have printed without it); when nothing in the -110 to +500 window agrees it prints "no build this run: Sweep says leans ..." and the game has no best parlay that run (home card, Live page and archive follow, they read out/best_parlays.json). A game without a lean builds exactly as before (checked 11/10: byte-identical slips for all 14 games). Record: out/sweep_leans.json per run, and build_calls.py writes the lean and the slip the same run would have printed without it into the archive's "Built for" cell ("close, low | Sweep says: the under | without it: Over 39.5|Total|39.5|-115 ; Browns ML|Moneyline|1|194 @ +450") so the two can be graded side by side on a Tuesday before anyone calls this rule a winner. Player unders are still not candidates for the boards' best parlay (the boards carry over ladders only) - an unders call is carried by the game under and by legs that do not need points.
- Backup QB flag (owner 11/9, after Carson Wentz for the Vikings on Monday night: "we shouldn't have had so much trust on a backup QB that's starting for an offense that was already not performing well"). flags.py Engine.backup_qb(team) fires when BOTH hold: (1) this week's quarterback is a stand-in - the projection tab's quarterback for the team (most projected passing yards, not OUT; failing that whoever started the last game) is not the one who has started most of the team's games, and he has three or fewer starts for them (or nobody is projected and last week's starter is out: "unsettled"); (2) the offense was already struggling - bottom 12 of 32 in points per game before this week (in/games.csv scores). Engine.leg() then puts a BAD flag "Backup QB" on the overs of that passing game only: the stand-in's passing yards / TDs / completions, every teammate's receptions / receiving yards / longest reception, and a receiver's or tight end's anytime / first TD. Rushing legs, a running back's TD and all unders are untouched (unders never pass through leg()). Effect: the builder shows the note and counts 3 risk points ("Some risk"; with any other flag "High risk"), the leg is out of Top Plays, Floor legs, the boards' best parlays (ROLE_RISK in build_boards.py and home.py), promo picks and the Daily Sweep. It never changes a projection or a chance. Week 10 at the time of writing: ARI (unsettled), BAL, CLE, MIN and PHI qualify. `python3 tests/backup_qb.py` checks the rule on a hand-made game log (12 cases) and, with in/ filled, which legs carry it; its last line lists this week's teams - read it on Thursdays and say so in the summary when a team on it has a quarterback who is plainly the regular starter (then the projection tab is behind, not the rule).
- Sweep says share card (build_boards.py SWEEPCARD_JS, drawn in the browser on the boards and the home page): since 11/10 evening its footer is the real wordmark (/wordmark.png, the cream letters with the red sweep - owner: "Make this the BetSweep logo when sharing sweep says"), drawn from the image the site header already loads; the word set in red type remains only as the fall-back while the image has not arrived. The take is sized to the room the footer and the leg box leave (58px down to 40px on the square card), so a five-line take with a leg still clears the logo.
- Sweep says (Step 1v): the rebuild session writes out/voice.json; build_boards.py (voice_line) and build_today.py print the game line; missing lines print nothing. Rules are in Step 1v - specific, funny, never about injuries, no guarantees.
- Fantasy page (build_team.py, 11/4 late): after a Sleeper league loads, a "The league, by the model" panel - every roster's best lineup under the league's scoring (power rankings, record, top scorer, the owner's team highlighted) and every matchup this week with a win chance (~5.2 pts of noise per starter) - with a "Share to the chat" button that renders the card to a PNG (Web Share on phones, download elsewhere). Hidden for hand-built rosters and leagues under 3 teams. Verified with a mocked Sleeper API in Playwright (6 teams, 3 matchups).

## Visual system (11/5 overnight, owner: "really think about aesthetic... make it look as good as possible", brand board attached)
Brand board = chalkboard navy with chalk plays, cream paper, one red, heavy italic wordmark + the swoosh, a hand-brushed red stroke.
Working notes with the diagnosis and tokens: research/design_notes.md. What changed (all generators; nothing in the model):
- One page-title style everywhere: a small red WEEK N over the title in the brand italic (build_site.wrap() rewrites "Week N · <b>Title</b>" into <small>+<b>; template.html .mast h1; .uw/.soc/.sp/.gd/.pd h1 for the self-styled pages). Before: three styles (tracked caps 16px in the mast, condensed 30px, italic 28-30px).
- Headings and labels in sentence case; uppercase condensed is reserved for controls (buttons, tabs, chips) and data labels (MODEL / BOOK / EDGE, LIVE / FINAL). Section titles on home, Today and the guide carry the brushed red stroke (--brush, BRAND_CSS .brush / .sec h2.t::after) - the one signature next to the swoosh. Home went from 39% uppercase text nodes to 18%; the fantasy page's seven caps labels became two.
- One control system (BRAND_CSS in build_site.py, loaded after every page's own CSS): primary = red fill, secondary = 1.5px outline, selected = inverted ink; 8px radius on every control and input, 14px on cards, pills only for status (LIVE, FINAL, BEST, confidence); condensed caps face on buttons; 36-44px tall; visible red focus ring; reduced-motion respected. Covers builder tabs, live Picks/Every leg (was unstyled Arial), players filters, refresh, Today share/live/links, slip buttons, FanDuel go buttons (kicked-off state is grey, not red).
- Palette: dark ground moved to the board's teal-navy (--bg #0e1820, --card #152230, --chalk #1c2b3a, --line #2a3b4b) in template.html, LANDING_CSS and player.css (inherits template tokens); light stays the board's cream. --redtxt (#f0594e dark / #b8261d light) for small red text so it clears 4.5:1; fills, swoosh and wordmark keep #d7332a. Contrast checked: ink/mute/good/bad all 4.8:1+ in both themes.
- Boards: Slate summary is one compact row (was a 380px chalk hero for one number); finished games no longer repeat the score under the header pill (live.py .tick.final); view buttons are secondary with an inverted selected state; help button quiet.
- Fantasy: CTA is a card with an inner red bar in the brand italic (was a red-outlined caps box); tabs "From Sleeper / Build it by hand"; form in the system face. Player page: three hero actions (Parlay Builder primary, Matchup board, News), sub line as items so a wrapped line never starts with "·", sentence-case sections. Builder: "Search" tab + a "?" help chip on phones. Home: stats line in body type with condensed figures, tighter lede, book buttons grouped, "+ Slip" as a chip. Receipts index and 404 in the brand voice ("posted slips 0–11").
- Verified (/tmp/gt, Playwright, 18 pages x dark/light x 390/1280): no JS errors, no horizontal overflow, one h1 signature on every page. Before/after composite: research/before-after-11-5.png (sent to the owner).
Rules for new pages: use the tokens (never a new colour), the control classes above, sentence-case headings, caps only on controls/data labels, cards 14px / controls 8px, no drop shadows on the chalkboard, chalk plays only in heroes.

## Efficiency pass (11/5 morning, owner: "weed out any inefficiencies we have throughout everything")
- Generators: one git branch (Step 1). The artifact bundle and Steps 1a / 7 are retired; the branch holds every file the bundle held (verified by sha256 on 11/5) plus assets/.
- Site: build_site.py writes the shared, content-hashed /s/ files (see "Static assets and page weight") - 35.6 -> 24.4 MB per build, 27 KB less HTML on every page, no Google Fonts / cdnjs requests; the service worker no longer pins /data/ files for a whole build (risk notes and price moves are hourly); the Today share button finally had html2canvas to call.
- Repo: no boards/img/ PNGs (Step 4) - they were 19 MB of binary per run, the biggest driver of the site repo's 793 MB history. Still recommended, owner's call: squash main once (`git checkout --orphan fresh && git add -A && git commit -m "squash" && git branch -M main && git push -f origin main` from a clean clone) - Pages only needs the latest tree; the feeds / sheet-mirror / promo-drafts / gen-overrides branches are unaffected. Stray branches gen-patch, gen-patch2, promo-studio can be deleted.
- Scheduled tasks: .github/gameday.py + workflows/gameday.yml write the Sunday game-day inactives (official ESPN lists from the feeds branch x the sheet mirror) to 'AUTO - Weekly Availability' and 'AUTO - Game Day Status' with no Claude session; it also covers Thursday and Monday nights. It needs the service account shared as EDITOR on the sheet; until then it exits with the fix line and the "NFL game-day inactives check" task keeps running (it failed on a usage limit on 11/2). Once a Sunday shows the Action writing rows, disable that task. Same pattern is the next candidate for the Thu/Sat/Sun pregame snapshot tasks.
- This file: dated history moved to CHANGELOG.md (149 -> 109 KB read per run).

## Injury-aware formula team score (owner 11/5)
- confidence.py Conf: after loading 'AUTO - Market Team Points' col H (our season-average formula), each team's score is adjusted for this week's absences: own main passer to date (60%+ of starts) OUT or replaced by a named starter (availability tab Forced Role QB1/STARTER beats the projections QB Role) -2.6 pts; regular pass catchers (played 60%+ of team games) listed OUT -2.4 x their season target share. Fit + every-season holdout: research/injury_team_pts.py (nflverse 2023-26) - both terms cut the formula's MAE in all four held-out seasons; opponent absences and backs' carry share flipped sign and are NOT used. Conf.formula_raw keeps the tab value; Conf.inj = {team: (pts, reasons)}.
- Flows to: confidence flags ("Our formula disagrees with the line"), builder games fa/fb + ia/ib, the Live page Model row ("Model adjusted for injuries" note when 0.5+ pts). The sheet tab itself is unchanged.

## Defense vs role (owner 11/5)
- defrole.py: per defense, the opposing QB1 / RB1 / WR1 / WR2 / TE1 (roles from per-game attempts / carries / targets before that week) - beat his own season average? (stats_player_week_2026.csv, every game) and cleared FanDuel's main line? (legsnaps main rung closest to -110). research/def_role.py is the leave-one-week-out test (Weeks 6-8): adding the defense's shrunk rate (K=4) to the model's % helped Weeks 6-7 slightly and hurt Week 8; vs FanDuel's price ~nothing. So: B = 0.25 logit per unit of rate gap (0-2 pts on a leg).
- Used in: build_builder.py (leg p / e + an info flag "vs WR1s: x/n" + l["dv"]), build_boards.py (shown %, so best parlays and edges see it, + good/watch flag), build_teams.py ("Against each role" section). Re-run research/def_role.py on Tuesdays as weeks are graded; if adding it keeps losing log loss two weeks running, set defrole.B = 0.

## Live page additions (owner 11/5 "do all of these")
- Fair live price: every open leg in a live game shows "fair <American odds>" from the live chance (no live FanDuel feed exists for props; ESPN's pickcenter is DraftKings game lines only and not confirmed live) - the user compares it with FanDuel's live price.
- My season: the Live page saves each week's settled My week legs as localStorage bs_log_w<W> (account.py SYNC includes it, so it syncs per account) and totals them by week / market / price band at 1u each.
- Share my week: html2canvas image card (record, units, cashed legs, still-alive legs) -> native share sheet, download fallback.
- Inactive alerts (push/slip-alerts.ts): swap suggestion prefers a teammate in the same stat, then a teammate, then the game; the push opens /build/?drop=<player>&add=<key>#slip (builder handles ?drop=). OWNER must redeploy the slip-alerts Edge Function for this.

## Our number vs the line (owner 11/5)
- Tuesday (after grading): `python3 -I research/gl_disagree.py <dir with games.csv + stats_player_week_2023..2026.csv> out/gl_disagree.json` (copy to research/gl_disagree.json and commit). build_season.py gl_record_block() shows the walk-forward formula's record vs the closing spread / total when 3+ / 5+ apart, plus the paper-tracked "fade our total when 5+ off" line. Through Week 9: sides 3+ 157-167 (48.5%), 5+ 68-82 - the line wins; fading sides failed the 2026 holdout (2023-25 76-58 -> 2026 6-10). Never promote a side or total because the formula disagrees with the line.

## What changed feed (owner 11/5)
- .github/feeds.py (feeds Action, every 10 min / 3 min in game windows) diffs each run against the previous feeds-branch files and appends to changes.json (7 days, 400 events): injury status changes, game-day inactives, weather tier / rain-chance (20+ pts) / wind (5+ mph) changes, new player-news items. The Live page "What changed" card fetches it from raw.githubusercontent plus /data/price-moves.json (every move on your legs, 8+ implied pts elsewhere), filters to projected skill players (live data "sk") and shows events since the user last closed the card (bs_chg_seen).

## Ask BetSweep + bet sizing (owner 11/5)
- Ask BetSweep (MOVED 11/11: it is in the site menu on every page now, ask.py - see "Early 11/11" at the foot; the builder has no box of its own). As first built: build_builder.py BUILDER_JS askAnswer() - a search box above the builder grid (also /build/?ask=<query>, in the menu). Parses player (legs + game logs + flags; last name / unique first name; ties go to the player who has the asked stat), stat (rec yds, rush, pass, rec, long, TD, rush+rec), line number and "under"; answers with FanDuel price, model %, edge, fair odds, projection, warnings and flags (incl. defense vs role) + Add to slip. "who benefits X out" lists legs whose leg or player flags mention X. No AI call - deterministic, nothing leaves the page.
- Bet sizing: stakeRow() in the builder slip and the shared template slip: quarter Kelly on the model's fair chance vs FanDuel's price, units (1u = 1% bankroll, optional bankroll field, bs_bankroll synced), capped 3u single / 2u two legs / 1u three+.

## New prop markets (owner 11/5): Passing TDs, Interceptions, Completions, Rush Attempts
- FanDuelOdds.gs 2026-11-05 pulls player_pass_tds, player_pass_interceptions, player_pass_completions (+ alternate), player_rush_attempts into 'AUTO - FanDuel Links' only (LINKS_ONLY - never the odds tab / Leg Board), ~5 more Odds API credits per game per refresh. OWNER pastes the new FanDuelOdds.gs into Apps Script once.
- newmkt.py prices them from in/stats_player_week_2026.csv: shrunk season average (k=3) x opponent factor ^ alpha; Poisson (TDs, INTs) / normal sd = c*sqrt(mean) (completions c=1.4, rush attempts c=1.6, shrink RBs toward the 8+ carry mean). research/newmkt.py: 2023-24 fit, 2025-26 test - all four calibrated; Brier vs plain average: pass TD -0.010, INT -0.013, completions -0.009, rush attempts -0.0002 (tie). build_builder.py adds the legs (sk "nm"), blended toward the price by the normal calibration pass; build_live.py tracks them in-game.

## When to fade - tests run 11/5 (owner: "is there a better way of knowing when to fade")
- Situations (research/gl_disagree.py segments, our number 3+ off the closing line, pre-2026 | 2026): no segment holds in both periods with a usable sample. Watch: short-rest games (Thursday) - our side 8-16 | 0-1. QB-change games flipped (32-40 | 2-0); early-season totals flipped (63% | 35%).
- Line movement (research/line_move.py, first vs last freeze in the calls archive): spread moves 1+ bet with the move 4-3, totals 1.5+ 2-1 - too few (Weeks 6-9). Rerun Tuesdays; with data/closing-w*.json the prop version is the season page's CLV card.
- Tested situational spots (2006-25, both decades) now show on each Live game's details strip ("Tested spot") from out/dossier.json.
- Popular players (research/star_unders.py, Weeks 6-8 main lines): no star effect - big-line overs 47.0% vs rest 47.1%. Market-wide main-line overs hit 47%. Rushing-yard unders on main lines under 40 yds went 33-25, 37-20, 37-26 (all three weeks) - unders_check.py now prints this cut at real under prices; same promotion rule (two graded weeks, 60+ legs, positive units).

## 11/6 batch ("do all of it")
- Fresh lists: risk.js stale() - a ruled-out player (risk_feed block: injury report, game-day inactive, owner OUT) hides his single-pick cards (article.play, with a "Hidden since the build" note) and puts a red swap banner on any listed parlay (.bestslip / cards with leg lists) holding him. Live, every page, no rebuild.
- Pace / PROE (research/pace_proe.py, pbp 2022-26): adding pace + neutral pass rate over expected to the dropback projection did NOT help (2025: MAE 6.34 -> 6.54 with all terms, 6.343 with PROE only). Not shipped; season averages already carry it.
- Your CLV: the Live page stores each tracked leg's price per week (bs_clv_w<W>, synced) and My season compares it with data/closing-w<W>.json.
- Value alerts: price_moves.py marks a DRIFTED move value=true when the leg's model % is 4+ pts above the new implied; risk.js chip "better price now +X"; slip-alerts pushes the owner once per key (VALUE). Owner redeploys slip-alerts.
- Track record: build_builder.py D.rec[market][band] from graded legsnaps (shown % band, 10-pt); trk() badge "hit X% of N" on builder rows when 40+ legs. Weeks 6-8: rushing yards shown 60-70% hit 56%, receptions / rec yds within ~3 pts.

## Outcome ranges / recalibration + best rung (owner 11/6)
- research/ranges.py: pricing lines from each player's own game-to-game shape (pooled by position) was LESS accurate than the model in every market - not shipped.
- research/recal.py (Tuesday re-run): shown = sigmoid(c + a*logit(raw) + b*logit(book)) per market, leave-one-week-out. Rushing yards c = -0.4 in every held-out week (X+ overs near the projection miss ~10 pts more than priced at every line size: <40 46% vs 56% implied, 70+ 41% vs 54%, lead backs 49% vs 58%), log loss 0.6954 -> 0.6713; longest reception c = -0.25. calib.shown() applies RECAL (a=0.1 keeps the model's ordering); passing yards improved overall but not Week 8 - re-test with Week 9 before adding. Receiving yards / receptions / TDs keep the 50/50 blend.
- Best rung: build_builder marks l["br"] (EV per unit at the shown %) on the best rung of each graded-market ladder priced -200..+400 when +2% or better and not in a losing zone; builder chip "★ best rung +X% EV".

## Deep-dive features #4-#8 (owner 11/6 "I'll want you to do all of them")
- Bad beat or bad bet? (build_live.py verdictOf): once a game is final, every hit / dead leg gets a chip from the work he got vs his usual (D.vol = targets, carries, pass attempts per game, Weeks < this week, 2+ games; box tgt / patt / ratt). Overs: dead + high work = Bad beat, dead + low work = Bad read, hit on light work = Lucky. Unders mirror it. Also fixed: the Live page never shipped "u", so unders showed and graded as overs - now detected from the "Under ..." market name and "u" is in FIELDS.
- Cash-out advisor + hedge (build_live.py cashBlock): open slip cards with a stake show "Fair cash-out" = live chance x payout; type FanDuel's offer for Take it / Fair / Hold. One leg left: the hedge bet on the other side that returns the same amount either way (H = payout / decimal), at FanDuel's typed price or the fair one, compared with the cash-out. Renders no longer wipe a field being typed in (render(force) + focus guard).
- Fantasy x betting: fdimplied.py adds p.fd (FanDuel ladders -> expected stats: power de-vig, K from the unders tab or 1.09 / 1.10 TDs; sum of P(X >= k), probit interpolation, geometric tail) and p.ins (main-line over on his main stat, FanDuel ids, kickoff). Fantasy page: "FD" under every player, Points switch Model / FanDuel lines / Blend (bs_fp_mode), "Insure against their stars" card (win chance if it hits, from research/insurance_shift.py: over on the main stat = +24% QB / +34% RB / +46% WR / +45% TE of his average, a TD +34 / 61 / 74 / 78%). Who should I start? shows "His FanDuel props add up to" and whether FanDuel agrees.
- Scenario explorer (scenario.py, build_builder.py): l.sc = chance under each ending [a by 10+, close & low, shootout, b by 10+] (probit.json / script multipliers for props, gamelines per-script chances for game lines), one probit shift so the endings mix back to the shown %. Builder slip panel: "What does this slip need?" (slip chance per ending per game, tap to fix an ending: legs of that game show "if shootout: X%", slip reprices, same-game correlation halved under a fixed ending).
- Sharps (social.py): Social's third tab ranks posters by CLV of posted legs vs data/closing-w<W>.json (player props; score = total CLV / (legs + 15); 5+ legs listed); "Sharp" badge for 15+ legs and score > 0.3 (top 5). No SQL change - reads open posts with the public key.

## Better projections / better bets (owner 11/6 "start on those three, then everything else")
- News edge (.github/price_moves.py news_edge on main): every Out / Doubtful / IR / inactive after the build for a player who had props -> his teammates' over legs (WR/TE for a pass catcher, RB for a back): first FanDuel pull after the news and first 3+ pt move logged in data/news-edge.json (the latency study - run it after Sunday: median minutes from news to move); legs FanDuel re-pulled without moving -> price-moves.json "news" -> risk.js chip "⚡ X out · price hasn't moved", owner push in slip-alerts (NEWS; needs a redeploy).
- Off-market: builder chip "🏷 FanDuel best by X pts" when FanDuel is 3+ implied pts longer than BOTH DraftKings and Hard Rock (about 30 legs a week; FanDuel tracks them closely, median gap 0.1), "cheaper at ..." the other way; price_moves logs them in data/offmarket-w<W>.json - grade on Tuesday (hit rate vs FanDuel implied).
- Market adoption (research/clv_fit.py): build Thu -> Fri morning, the market moved toward the raw model on 50% of moved legs (w ~ 0 in every market). Re-run Tuesday with the closing prices: python3 research/clv_fit.py build/data-*.js <mirror links.json>.
- Blend weight (research/blend_weight.py, legsnaps Weeks 6-8, leave-one-week-out): FanDuel alone beats the 50/50 blend pooled (best model weight ~0.1). By market: passing yards, rushing yards, longest reception -> 0 (book only, every held-out week for passing); receptions ~0.3; receiving yards ~0.2-0.3 (noisy); anytime TD ~0.6-0.7 (the model adds real value). NOT applied yet - owner decision; Tuesday re-run with Week 9, then set per-market weights in calib.py.
- Red-zone TD model (rz_check weeks 6/7/8, 345 legs): log loss rz 0.600 vs raw 0.605 vs FanDuel 0.614 (lost week 8 only). Now also on the boards' anytime-TD legs and the builder's 2+/3+ TD (Poisson mean moved with the anytime blend).
- Tested, not shipped: FanDuel ladder internal pricing (no monotone violations; the "outliers" are count-stat curvature); referee crews (research/referee_totals.py - high-over crews went 48.8% then 41.1% over); OL / secondary starters out (research/line_injuries.py: 1 OL starter out -2 rush yds se 2.6, 1 DB out +4 pass yds se 4); air-yards share (research/air_share.py helps a targets-only baseline slightly, research/air_vs_ours.py makes OUR projection worse every held-out week).
- Parlay pricing: graded legs return about -8 to -10% each at every price below +200; model-edge legs pay only at plus money (+9% at +120..+199, +59% at +200..+399) and lose at -130 or shorter (-8% to -23%). Builder slip flag on 2+ favorites. Live: "Same bet, several slips" note.
- Fix: Live "What changed" price moves threw on one-digit-hour pull times ('0:11') and never showed.

## Similar defenses (owner 11/6: "I want us to utilize the similar defenses")
- simdef.py = the Game preview split for every player this week: main stat (QB pass, RB rush, WR/TE rec yds) in the 3 past games against defenses most like this week's opponent vs his season average, plus how many of those 3 beat his average. Builder chip "vs similar D +41% · 3/3"; boards listed-parlay ranking uses it as a tiebreaker (+-3 pts at +-50%). Owner rule for best bets and promos: among legs that already qualify on edge, prefer the higher similar-defense split. It never changes a probability.
- Tested before shipping (research/similar_def.py): 2024-26 it did not predict the next game; graded FanDuel overs 2026: split +20% hit 46.5% vs 56.7% priced, 3 of 3 above average 45.1% vs 56.7%. TNF Week 9: Meyers +41% (65 yds) and Zay -34% (6) right, Rodriguez +28% (19) and Bateman +20% (6) wrong.
- Tuesday: run research/similar_def.py with the new week graded and report to the owner (FanDuel overs by split band and by 3/3 consistency). If the tiebreaker's picks keep losing to the price, tell the owner - his call whether it stays.

## Deep-dive batch (11/10 evening, owner: "Get to all of this")
- STEP 6c AND s/ (11/10 evening): do NOT delete the clone's s/ folder any more. Copy site/s/ over it and remove only the hashed files (site-*.css, app-*.js, tpl-*.css) that no page in the clone links - `python3 -c "import reprice; print(reprice.copy_into_clone('<clone>'))"` does the whole of Step 6c this way and is the preferred way to do it. On 11/10 the 3:56 PM run emptied s/, the template stylesheet had a new name, and /season/ and /receipts/week9/ (built that morning, not rebuilt by an afternoon run) served with no layout until the reprice's browser check caught it.
- AUTO-REPRICE: `.github/workflows/reprice.yml` on main runs `reprice.py` (this bundle) every hour at :20, 6:20 AM - 11:20 PM CT, and on demand (Actions > reprice > Run workflow: publish = all / changed / none). reprice.py is this RUNBOOK's script chain with no session: mirror -> in/, the context desk scripts (flags only - it never writes the Sheet), every Step 3 generator, build_promo.py, build_site.py, its own checks, then Step 6c as code (`copy_into_clone`), a headless-browser crawl gate (tests/gate.py) and the push. It skips itself when the mirror is over 3 hours old or the mirror's week is not the week the site serves (rolling the week, grading, the Sheet archives and the Sweep says lines stay a session's job). It re-uses the last session's Sweep says lines from /b/voice.json - build_site.py now publishes out/voice.json there, so WRITE voice.json AS BEFORE and it travels. A session may use the same code for Step 6c: `python3 -c "import reprice; print(reprice.copy_into_clone('<clone>'))"` after build_site.py copies ./site over the clone by the Step 6c rules (posts/, promo-slips/, lab/, .github/ untouched; b/, data/, receipts/, app/, season/ added to, never emptied).
- What the hourly run can and cannot freshen (measured 11/10 8:40 PM): FanDuel game lines are pulled into the sheet every 6 hours (FanDuelGameLines.gs, 0:59 / 6:59 / 12:59 / 18:59 CT on 11/10 - the first note here said "about hourly", which was wrong: 96 credits were spent between 6:24 AM and 6:59 PM, three 31-credit pulls) and DraftKings / Hard Rock with the props schedule or when the owner runs the menu item. FanDuel PLAYER PROPS ('AUTO - FanDuel Links' column Updated) had one pull that day, 6:24 AM, and the unders tab ('V2 - Unders') had not been pulled since 11/5 - prop prices are only as fresh as the sheet's own pull, which the owner controls in the sheet.
- STALE UNDERS (fixed): build_builder.py joined 'V2 - Unders' rows to the week's ladder by player + market + line only; with the tab still holding Week 9's pull, 15 of last week's under lines sat on the Week 10 board with last week's prices and selection ids (and went into Beat the model, the DET-NE Sweep says line and 15 rows of 'V2 - Unders Snapshots' stamped Week 10 - those 15 rows, 'Pulled (CT)' 2026-11-05, are NOT Week 10 lines: research/two_way.py and unders_check.py must not grade them as such). An under row now counts only when its own kickoff day is the game's day; the builder prints how many it left out. fdimplied.py ignores under rows whose kickoff day has passed. When writing Sweep says, never cite an under unless build_builder.py printed it as priced this run.
- NEWS DESK: an ESPN team-report "Out" whose own line says the player was a full participant / practiced in full / has no designation is last game's label -> QUEST, not OUT (Skattebo 11/10: "Out. ... listed as a full participant in Tuesday's practice" had put "Cam Skattebo out" in Thursday's brief). Selftest 28/28.
- UNDER OF THE DAY (under_day.py, called by build_today.py; card on the home page and the Short view; data/under-day.json): per game day the under shown at 55%+ and at or above break-even with the widest gap, "Market disagrees" legs last, questionable players skipped, no risk screen (the flags describe overs). The entry follows the board until its game kicks off, then freezes; graded from the game log; record on the card and in Track record once it has one. No qualifying under = no card.
- LINES TO CHECK (stale_lines.py, called by build_today.py; home page block, /b/stale.json): a player the news desk has OUT since the last FanDuel props pull, who had props this week or in the last two graded weeks -> his position-room teammates' legs with the note that our price predates the news. It is a list to open in the app, not a claim that FanDuel has not moved.
- THE MORNING BRIEF now leads (after weather) with the Daily Sweep when one is posted for the day, else the day's favorites, then the Under of the day; the plus-money looks no longer lead the push. THE DAILY SWEEP stays at FOUR favorites near +300 (owner 11/10 9:25 PM: "Keep it at 4" - PROMO_DESK.md rule 3a carried a three-leg default for two hours that evening and it was withdrawn). Track record on the home page leads with the Daily Sweep's record.
- SHORT VIEW: "3 easy picks" is "3 favorites" with "All three hit: about N%" (the shown chances multiplied) and a second button when DraftKings or Hard Rock pays more for the same three legs at their exact lines. tests/simple_view.py still reads #sveasy.
- LIVE: a cashed slip gets "Share the win" (a 1080x1350 canvas card, no library). The hedge helper and the cash-out advisor were already there (11/6).
- PAGE COUNTS are built and OFF: account.py PAGE_COUNTS = False. After the owner runs sql/betsweep-pagehits.sql, set PAGE_COUNTS = True and PAGE_COUNTS_SINCE to that date; the same build then adds the anonymous "+1" to the shared script and the three sentences to the privacy page.
- favicon.png is written at 96 px (was the full 96 KB logo); logo.png keeps full size.
- Model port: research/model_port/ (inventory + parity harness). Nothing on the site reads it.
- SURVIVOR PLANNER USES THE MODEL TOO (owner 11/10 9:05 PM: "I want it to be the models projections as well not just going off of fanduels lines"): build_survivor.py gives every game two win chances - FanDuel's (as before) and the model's - and the page plans on their average ("Both", the default) or on either alone; option rows show both numbers. This week the model's number is its formula team scores (builder_data games fa / fb - the projection built from the player tabs and the injury report, NOT pa / pb, which are FanDuel's implied totals) turned into a win chance. Later weeks are not projected by the sheet, so there it is the line-based margin moved by half of each team's running gap between formula points and FanDuel-implied points; those gaps live in data/survivor-model.json on the site (one per team and week, written before kickoff, merged every build - Week 9 was seeded from the 11/8 10:06 AM board). The run-log line now ends "model: N projected this week, M later games nudged by T team gaps from weeks ...": N should equal the week's games. tests/survivor_plan.py checks the road against an exact search under each of the three settings.

## Late evening 11/10 (owner 9:19-9:41 PM)
- ESPN'S STALE "OUT" TAG (owner: "Cam Skattebo says ruled out on betsweep but that's not true ... he was out last week but will be back"). ESPN's injury page keeps LAST game's Out / Doubtful on a player until the new week's report replaces it; the alerts function copies that tag into Supabase risk_feed and risk.js showed "Ruled out" and refused his legs. Three places now know better, with the same three patterns (HOPE = practising / expected to play, LATER = points past this week, FIRM = the note itself says he is out): (1) .github/feeds.py on main writes feeds notout.json every 10 minutes - src "espn" when the line's own note is hopeful (shown as Questionable), src "owner" for the calls in data/risk-clear.json on main (shown as "Good to go"; an entry lapses after its "until" day or as soon as ESPN posts a NEWER Out / Doubtful line that is not itself hopeful); (2) risk.py RISK_JS reads notout.json and never overrides a game-day inactive (detail "Inactive") or an owner Out note; (3) push/slip-alerts.ts espnStatuses() applies the same rule before it pushes "is OUT" or writes risk_feed - THE OWNER MUST REDEPLOY THE FUNCTION for (3); until then the site is right but a push can still say OUT. To clear a player by hand: add him to data/risk-clear.json on main ({"note", "by", "at" (ISO time of the call), "until" (YYYY-MM-DD)}), append a CLEARED row to 'AUTO - Weekly Availability', run the feeds workflow. tests/risk_notout.py drives a built page with both feeds faked (ESPN Out alone, + the owner's call, + ESPN's own note, a game-day inactive, an owner Out note).
- EITHER-OR TDs ARE SAME-GAME ONLY (owner: "you can only bet on 2TDs from the same game"): /pairs/ offers a second player only from the first player's game, the best-pairs list is built per game, an old ?a=&b= link across two games keeps the first player and asks for a same-game second; build_promo.py prints EITHER-OR WARNING when a promoted "A or B" leg pairs two games; PROMO_DESK.md rule 6. tests/pairs_page.py.
- THE DAILY SWEEP STAYS AT FOUR LEGS (owner 9:25 PM: "Keep it at 4").
- THE SHORT HOME PAGE (owner 9:39 PM: "Let's compact the home page a little bit. There's just a lot going on. Maybe some things can move to different or new pages. Slate probably doesn't need to be on the home page. The first section with today's game looks really good though. Just make it better"). "/" was 15,690px on a phone (18 screens); it is about 5,400 on a one-game day and 8,100 on a twelve-game Sunday. Order: head, the Daily Sweep (a slim strip while no slip is posted for the day: home.py SWEEP_JS adds .teasing), today's game cards, posted promos, Model's Best as THREE ROWS (home.best_teaser - the script hides rows already on screen in today's game card and rows that kicked off), the lead parlay, You today, three news notes, Ask the model, Track record, eight doors ("Where to next"), latest posts. The game card: a three-number strip (spread shown from the favorite's side, total, the site's score) instead of the run-on line, a kickoff countdown, one main button (Matchup board), and on a day with three or more games every card folds to head + numbers + the take with "More on this game". landing_merge.merge() composes the page from home.BLOCKS (home.sections() now keeps every block by name) and no longer appends home.py's scripts a second time - THE SECOND COPY UNDID EVERY "+ Slip" TAP ON THE HOME PAGE (two listeners: add, then remove) and put two #hsbar bars in the page.
- WHERE THE REST WENT (build_site.py, right after the home merge; fragments from build_today.py's out/today_parts.json and home.BLOCKS): /best/ Model's Best in full + top plays (left out while there are none) + next man up + the radar + every game's parlay; /slate/ the week's games (home.slate cards, live scores); /news/ every news note grouped out / limited / back with a team filter, and Lines to check; /targets/ the trade desk; /all/ "Every page", written from NAV_GROUPS. /today/ still redirects to "/".
- THE MENU (owner 9:33 PM: "make the organization of the pages more optimized where they are in the menu"): NAV_GROUPS = Today, Short view, Games (6), Betting (8), Play (3), Players (4), Fantasy (5), Results (6) - by what the visitor is doing; Betting had been one list of thirteen. The five bottom tabs are the owner's from 11/5 and did not change.
- WHERE TO NEXT (same message: "more fluid ... moving from one to the next"): build_site.py NEXT maps a path prefix to two or three doors (research -> build -> check -> track -> results); wrap() puts the strip above the disclaimer on every page with an entry (451 pages). A new page needs a NEXT entry and a NAV_GROUPS line - tests/home_compact.py fails without them.
- PHONE PASS (owner 9:41 PM: "Most people will use their phones ... Make sure it looks really good all over"), all in the shared site CSS / app script so every page gets it: (1) text that sits on the page background (titles, introductions, breadcrumbs) is 15px from the edge instead of 5 - BIGGER_CSS keeps the 5px page gutter for cards; (2) an introduction longer than ~190 characters under an h1 folds to three lines with a More button (foldIntro in APP_JS; phones only); (3) .subt notes are sentences, not five lines of tracked capitals; (4) a parlay's book buttons are one full-width FanDuel button and two half-width ones (they were three squeezed columns), a leg card's three books fill one row at 38px; (5) .sech = a section title with one "see all" pill. tests/home_compact.py (31 checks): page height both days, the moved sections, + Slip adds once, menu group sizes, a strip on every content page with live doors, title insets.
- THE SHEET'S ODDS SCRIPT, v2026-11-10 (owner 9:25 PM on more frequent props / unders pulls: "Love it. Do it."). FOUND FIRST: THE 11/5 FILE WAS A REGRESSION. It was edited on FanDuelOdds.gs while FanDuelOdds.gs.txt held the newer 10/29 text, then copied over both - dropping (1) the FanDuel UNDERS tab ('AUTO - FanDuel Unders', v10/27; last pulled 11/5 6:09 PM, which is why no under was priced in Week 10 and Under of the day had no card), (2) the 2+ / 3+ TD prices (v10/28), (3) the rule that an odds refresh keeps the DraftKings / Hard Rock game-line rows (v10/22 - every props refresh wiped them until the next lines run), (4) the game-day menu item installing both jobs (v10/29). The new file is the 10/29 text + the 11/5 markets, and adds: TODAY'S-GAMES PULLS - outside the fixed windows, every hour 9 AM-7 PM CT the trigger refreshes only the games kicking off within 9 hours when that is four or fewer (Thursday and Monday afternoons, Sunday's night game, Saturdays, holidays): about 20 credits a game against about 280 for the slate; every other game's rows stay in all five tabs as last pulled, each with its own stamp (so stale_lines.py now reads the pull time per player, not one stamp for the tab). A CREDIT GUARD - the Script property BS_CREDITS_LEFT is written by every refresh; an extra pull is skipped unless the credits left exceed CORE_PER_DAY (580) x days to the 1st x 1.15 by its cost; rows 7-8 of the odds tab's status block say what the last extra pull did and why. The Odds API resets credits on the 1st; the owner's balance (14,806 on 11/10 6:24 AM, about 560 a day used 11/1-11/10) says the 20K plan, which the fixed schedule nearly fills - the extras are about 500 credits a week and the guard throttles them when the month runs short. 100K is the next plan ($59 against $30).
  THE OWNER PASTES IT (Extensions > Apps Script > FanDuelOdds > replace all > Save, then menu FanDuel odds > Turn on scheduled refresh once). Sent 11/10 as FanDuelOdds-2026-11-10.gs.txt. Until then: no unders, no 2+/3+ TD prices, props once a day.
  BEFORE HANDING OVER ANY NEW FanDuelOdds.gs: `node tests/gs/harness.js` (25 checks). It runs the script in Node against a fake sheet and a fake Odds API with The Odds API's billing, and compares a full refresh tab by tab with the last two installed versions kept in tests/gs/ - add the file being replaced when the script changes again. FanDuelOdds.gs and FanDuelOdds.gs.txt must be the same text (the harness checks); edit one, copy to the other.
- PAGE COUNTS ARE ON (account.PAGE_COUNTS = True, since "November 10, 2026"; owner 9:25 PM on the SQL: "On it"). The request fails quietly until sql/betsweep-pagehits.sql has been run and counts from the moment it has; the session cannot reach Supabase to confirm. Reading the counts: the two queries at the foot of that SQL file.

## Early 11/11 (owner 12:15 AM): Ask BetSweep in the menu, Theme on My BetSweep, Short view on the home page only
Owner: "Can ask betsweep just be on the Menu? I'd want this on the menu of every page. And then it doesn't have to be actually on any page itself it can just be in the menu. Also put theme in My Betsweep rather than the menu. Put short view access just on the home page not in the menu."
- THE MENU IS NOW: the Ask BetSweep box, Today, and the six groups (Games, Betting, Play, Players, Fantasy, Results). build_site.py NAV_GROUPS has no Short view and no "Ask BetSweep" line; sitenav() puts ask.form() first inside .tabs (first thing in the open menu on a phone, the right end of the tab row on a wide screen - CSS order) and no longer writes the Theme group.
- ASK BETSWEEP = ask.py (form(), CSS, JS). CSS rides in the shared stylesheet (NAV_CSS), JS in the shared app script (APP_JS), so every page gets the same one. NO PAGE HAS AN ASK BOX OF ITS OWN: the builder's box (#ask, askAnswer and friends) and the home page's "Ask the model" section (#tdask) are deleted. Do not add one back to a page; change ask.py.
  - What it reads: /b/ask.json (build_site.py writes it right after placing the builder) = {week, src}; src is the Parlay Builder's own data file, read as text and parsed - never loaded as a script, because /team/, /trade/ and /dfs/ keep their own data in window.__BS. On /build/ it uses the board already on the page. Plus /b/players.json, so a player with nothing on the board is still recognised ("FanDuel has no lines for him on the board right now", his page, his game's board). The build stops if it cannot find exactly one builder data file.
  - What it answers: player + stat (+ line, "under"), a player, a last name two players share ("Which one?"), a team (codes only in questions of three words or fewer - "was", "no", "car" are English), "who benefits X out" (only notes about an absence: Fill-in volume and the like; when the only notes are about his RETURN it says he is back and lists who loses work), "best" / "safest" / "plus money" / "best td" (the Model's Best tiers the model assigned, minus ruled-out players - not a new ranking). Legs of games that have kicked off are never offered. The header line of every answer says which board it read ("Week 10 board, built ...").
  - Add to slip stays on the page: it writes bs_slipk_w<week> and dispatches a storage event so the page's own slip buttons and bars repaint (home, boards, player pages, the risk pill all listen). On /build/ it goes through window.bsSlipToggle / bsSlipHas / bsSlipCount (build_builder.py, next to toggle()), and the builder fires a 'bs-slip' event from renderSlip() so the open answer repaints. Same two refusals as the builder: a started game, a player the risk layer has ruled out.
  - The written answer (the old home-page feature: POST {mode:'ask', q} to the slip-alerts function, signed-in, 20 a day) is the link under every board answer, "Ask the model for a written answer". Signed out it asks for a free account and opens the sign-in box. The privacy page says exactly this (build_legal.py, "Ask BetSweep"; date 11/11).
  - ?ask=<question> on ANY page opens the menu with the answer (the builder's old /build/?ask= links still work).
  - The hint under the box ("Try Jahmyr Gibbs 90+ rush yds, Ravens or best td") is picked per build by build_site._ask_example(): the latest-kicking game with props, the rec / rush rung the model likes best among 30-75% chances, full name; the home team of the week's last game. On a wide screen the hint is a small panel that shows while the box has focus.
- THEME: one row under the title on /me/ (account.me_page, .thm.methm; styles in ask.CSS). The app script binds every .thm group on a page. bs_theme stays a per-device setting (it is not in account.py SYNC). Signed-out visitors had no menu path to /me/, so account.js adds a "My BetSweep" line to the menu when nobody is signed in (.mme) and removes it on sign-in (the header pill does that job).
- SHORT VIEW: the only link is the home page's own button (build_today.py #tdsimple). Gone from NAV_GROUPS, from the NEXT doors of /best/, /how/ and /guide/, and from /all/'s "Start here". /short/ itself, its "Make this my home page" switch and the /simple/ forwarder are unchanged.
- EVERY PAGE MEANS EVERY PAGE: rechrome.py. A build only wraps the pages it makes; the weekly receipts (Tuesdays), /season/ (when a week is graded) and earlier weeks' short-link pages kept the menu of the day they were built - on 11/11 that was 26 live pages on three generations of menu (/receipts/week6/ had October's flat ten tabs; /season/ had missed the 11/10 regroup). build_site.py now ends by calling rechrome.refresh(): every page that will be live after the copy and has the site menu but not this build's gets a copy in ./site with the menu block, the shared stylesheet link, the shared script link and the bottom tabs replaced (pages from before 11/5 lose their inline menu styles and inline app script for the shared files) and "Where to next" added when missing. Nothing else in the page changes. Pages in PROTECTED folders are never read; a clone-only page in a folder the build replaces wholesale is not brought back. The build prints "rechrome: N older pages given this build's menu". After the first publish N is 0 until the menu, the shared CSS or the shared script changes again.
- ALSO FIXED ON THE WAY: on a wide screen a signed-in visitor had a ninth tab, "SIGN OUT", next to the header's Out button (the line was added for phones on 11/5) and it wrapped to two lines under 1,320px - hidden above 1,240px now; no tab wraps (white-space:nowrap); the ask field narrows (210px down to 104px) before the row can overflow.
- TEST: tests/menu_ask.py (about 60 checks: every menu has the box once, no Theme or Short view in any menu, one shared script and stylesheet site-wide, the card's numbers equal the board's, add / remove, the builder's slip without a reload, kickoff, ?ask= links, Theme on /me/, 1,241px and 1,366px signed in and out, the older pages). Run it against the scratch copy of the clone - only that has the older pages: BASE=http://127.0.0.1:8803 SITE=/tmp/clonecopy python3 tests/menu_ask.py

## 11/11 8:20 AM: suggested legs on Beat the model (owner: "suggested legs around -110 that we can scroll through to build our five. Include percentage and position ranking in that stat vs defensive matchup in that stat for each leg")
- build_beat.py writes beat.json "sug" = [key, pos, kick, [[stat, offense rank, defense rank], ...]] and the page lists it under the five slots (#btsug): priced -125 to +100, one rung per player + stat + side (nearest -110), model 50%+ only, most likely first. Overs show by default (the model's top of this list is a wall of rushing unders); Unders and QB / RB / WR / TE are chips. Tap adds or removes; the five-leg and one-per-player rules, kickoff and the risk layer's ruled-out players apply.
- The pair is the builder's matchup pill: his team's rank at his position in that stat (offranks.py, 1 = produces the most) vs the opponent's rank against that position (sheet defense tab, 1 = allows the most). Colors flip on an under so green always helps the leg. Rush + Rec shows two pairs (rush, rec); Longest Reception uses rec yds; TD legs use the position's TD column. A leg with no rank column is not suggested.
- NOTE: recomputing the defense tab from the mirrored game log matches the sheet in 331 of 480 cells (max 12 ranks apart): the mirror's game log lacks low-volume players. The page uses the sheet's tab for defense, as the builder does; the offense ranks come from that thinner game log.
- 8:28 AM (owner: "Having this same best legs where you can scroll and add to parlay on the parlay builder page would be cool"): the rules moved to sugmatch.py (shared). build_builder.py puts DATA["sug"] on the board and a sideways strip "Best legs near -110" (#bq) above the grid: same chips, each card adds to or leaves the slip through toggle(), repaints on 'bs-slip'.
- 12:10 PM (owner: "Make it so you can add your 5 legs from beat the model into your betslip"): #btslip under Lock in five writes the picks to bs_slipk_w<week> (the shared slip; the beat key is the slip key), skips games under way and ruled-out players, and shows "Open betslip (n)". Works before or after locking.

- 11/11 1:38 PM, WEEK 10 WR-CB CHART (owner upload NFL26_CS_WRCB_Week_10.pdf; "Add these to receiver face-off and use it to help with what sweep says, and what we're choosing for parlays"). Loaded to 'AUTO - WR CB Matchups' rows 341-424 (84 receivers; CHI, DEN, PHI, TB on bye), read back cell for cell through the mirror. HOW TO LOAD A WEEK: page 1 parses cleanly with pdfplumber words bucketed by x (the Z% sits 1px above its row - attach it to the nearest row); page 2's "Season" rows give AD-AG keyed offense|defense. Primary CB = the listed corner when the row has the S (shadow) mark, else the defense's corner with the highest alignment exposure. From Week 10 the constant and derived columns (A, B, F, G, T, AH, AI-AR) are ONE ARRAYFORMULA each in the block's first row instead of a formula per row (same results; the per-row version is 30 KB a week through the Sheets tool). STANDING RULE: when writing Sweep says lines and choosing slip legs, read the week's chart - name a Coverage edge (Clay +8% targets and +0.15 pts/route or better) or a shadow in the game's line without telling the reader to play anyone who is not the pick, and do not lean on a receiver's overs against a shadow or a Tough coverage row.
- 11/11 3:50 PM, TWO GRADES (owner: "Run em"). (a) MAIN-LINE UNDERS, Weeks 6-9, 1,615 main lines (ladder rung nearest -110, latest freeze, players with a stat line): rushing overs hit 42.9% (n=312; every week 41.6-45.5%), so a rushing under at -114 won 57.1% against a 53.4% break-even. But the model's own rushing number does not sort them: where it had the OVER at 50%+ the under still hit 59% (n=137); its 70%+ unders hit 41% (n=17); with real under prices in Week 9 its 60%+ rushing unders went 13-15. Receptions is where the model is right: unders it gave 60-70% hit 61.5% (n=122), 70%+ hit 69.8% (n=53). Receiving yards unders are overstated (says 64%, hit 54%, n=89). Passing yards: the model has leaned the wrong way (n=112). NOTHING CHANGED on the site from this yet. (b) WR-CB CHART, Weeks 7-9 (research/wrcb_grade.py <run in sm/in>): Clay's matchup delta shows no signal - "Coverage edge" receivers went over their receiving line 54% (n=37), "Tough coverage" 52% (n=23), softest third by delta 45% vs toughest third 51%, and the sign flips week to week. The sheet's own CB Matchup Flag did better (FAVORABLE 56% over, n=25; DIFFICULT 39%, n=36) on a small sample. Shadows: 3 graded, no read. So the chart stays a note, not a projection input, and the boards' arrows should move from Clay's delta to the sheet flag only if two more weeks agree.
- 11/11 4:15 PM (owner, after the two grades: "just do the first 2. I like the coverages" - the coverage sentences and arrows stay as they are). (1) build_builder.py RUSH_UNDER_RATE = 0.57: every "Under Rushing Yards" leg shows the flat graded rate (l["flat"] = 1; the later blend and defense-vs-role passes skip it; raw_p / pm keep the model's number so the Tuesday unders freeze and unders_check.py are unchanged). Its flag says so. RE-FIT THE RATE each Tuesday from the main-line grade (Weeks 6-9: 57.1% of 312); drop the override if the model's rushing number starts sorting them. Effect: rushing unders no longer top the suggested lists on Beat the model and the builder. (2) under_day.py: receptions unders first, rushing second, receiving / passing yards last (then the old order: no "Market disagrees", widest gap).

### Under of the day skips an under the coverage disagrees with (owner 11/11 4:57 PM)
`under_day.soft_draws(in_dir, week)` reads the week's rows of in/wrcb.json and lists every receiver with a soft corner: the boards' green arrow
(Clay T/R delta >= +0.08 and F/R delta >= +0.15) or the sheet's CB Matchup Flag = FAVORABLE. `candidates(bd, soft)` drops Under Receptions and
Under Receiving Yards for those names, so the next-best under takes the day's card. Players not on the chart (tight ends, backs) are untouched.
If the chart has no rows for the week, nothing is skipped and the build prints a note. Same rule when hand-picking slip legs: no receiver
under against a soft draw, no receiver over against a shadow or Tough coverage.

### The home page is built once more after the promos (11/12)
reprice.py ran build_today.py before build_promo.py, and each workflow run starts with an empty out/, so a Sweep added to the PROMO tab never
reached the home page hero (11/12: "Daily Sweep: Wet Work" was in /b/promos.json and at /b/w10-1/ but the hero showed only the teaser). BUILD
now has a "today (with promos)" pass right after "promos". Check after any promo publish: `grep -c "<the slip name>" index.html` must be 1+.

### Winners section on the home page (owner 11/13)
`home.winners_block(IN)` lists every row of the PROMO tab whose Result is a win (sweep.res_kind == "W"), newest first, up to six: name,
FanDuel price from column E, the legs, what $10 won, a link to /b/w<week>-<slot>/. It reads only in/promos.json (all weeks), so a win stays
up after its week ends; a leg's final stat is added from in/gamelog.json when that week's row exists, never guessed. The date line comes from
the Posted column (YYYY-MM-DD) - fill it when grading. The section sits right under the Daily Sweep hero and is absent until there is a win.
First entry: Week 10 "Daily Sweep: Wet Work" +302 (WAS 24, NYG 21; Diggs 83 rec yds, Skattebo 44 rec yds, total 45), graded from ESPN's box 11/13.

### No under on a player whose role is growing (owner 11/13)
Austin Ekeler under 1.5 receptions was the 11/12 Under of the day and the first draft of that day's Daily Sweep; he caught 4. He carried
Fill-in volume, Role Up and Healthy again, with both other Washington backs out, in a rain game. Those are "good" flags, so the risk score
read the under as clean (0) - the score does not know which side of the line a leg is on. `under_day.role_against(l, pf)` now drops an
under when the player's or leg's good flags argue for the over (AGAINST: growing role, hot form, soft matchup, plus Targets up / Trail
script for catches and Carries up / Lead script for rushing). Hand-built slips follow the same rule: before any under, read the player's
flags as if the leg were the over - if they would make us like the over, the under is out, whatever the risk tag says. When the owner
pushes back on a leg, re-check that leg from scratch.

### /slate/ ("This week's games") retired (owner 11/13)
"We already have all that info on other pages." build_site.py no longer builds or links it: out of the menu, the next-door strips
(/survivor/, /teams/, /dfs/ point at the Matchup Boards instead) and the sitemap; the home page's "All N games this week" goes to /boards/.
site/slate/index.html is a noindex forwarding stub to /boards/ so old links and bookmarks still land somewhere. home.slate() still feeds
nothing public; leave it until the next clean-up.

### A still-linked stylesheet is put back automatically (11/14)
The Saturday boards session replaced s/ wholesale (commit 3afd734) and dropped s/tpl-14c6dc7c9d.css while /receipts/week9/ and /season/
still linked it; those two pages lost their styling and the gate held the next publish ("MISSING FILE ... 404 /s/tpl-..."; the owner got
GitHub's "Run failed" email). Fixed by restoring the file on main (2ffd475). reprice.copy_into_clone now restores any hashed s/ file that
a page still links from the clone's git history, so this heals on the next publish. The boards session itself still needs the same care:
it must add to s/, never replace it.

### Traded QB's newer markets follow FanDuel's game (11/14)
Kirk Cousins (LV -> MIN 11/10; Fernando Mendoza starts for LV) had his Passing TDs leg filed under LV-SEA: newmkt.Pricer takes the team from
the player's last game log. The sheet itself was right (projection tabs and availability have him MIN, Mendoza LV QB1). build_builder now
checks the FanDuel row's game name (links column I) and, when the pricer's team is not in that game, takes the team the projection tabs give
him for that game. The Week 10 slips built in chat never used that leg.

### Slip import reads alternate spreads and totals (owner 11/14)
"When I import a slip with alt gamelines, it doesn't import correctly saying game line not on this week's board." FanDuel prints alternate
lines in brackets - "Tennessee Titans (+19.5)" / ALTERNATE SPREAD, "Over (40.5)" / ALTERNATE TOTAL POINTS - and the importer's patterns
wanted the number bare at the end of the line, so every alt line failed (main lines with a unicode minus, "Green Bay Packers (−3)", too).
slipimport.parse now accepts the brackets, a −/–/~ minus or a lost sign (tries both, keeps the one that team has), and matches a total
inside the game header the legs sit under (FanDuel prints "X @ Y" above the legs, so before this a total could land in another game).
Test: `node tests/slipimport_altlines.js <builder data json>` - four screenshot texts from 11/14, every leg must read OK.

### Imported totals load into their own game; totals graded on My BetSweep (owner 11/14, second report)
The owner's imported 12-leg game-line slip loaded with all seven totals in DET-NE. A total's key ("Over 49.5|Total|50") has no game in it;
the builder puts each one back in its game from bs_slipg_w<W> ({key: [gid, ...]}, slip order), but the importer never wrote that map, so
every total resolved to the first game with that number. slipimport now builds the map from the matched legs (gmapOf), writes it when it
loads a slip, and saves it on the slip (g) like the builder's Save slip; My BetSweep's "Load into betslip" passes it too. Every total now
carries its game (builder too), so My BetSweep grades totals from the final score instead of "totals need the game"; totals saved before
11/14 without a game stay ungraded rather than guessed. Test: `node tests/slipimport_load.js <builder data json>` - the owner's slip, all 12
legs must resolve to their own games.

### Every place a slip travels keeps each total's game (owner 11/14, Social post)
"Can this show the games? How do we tell what under it's taking?" - his 12-leg Social post listed "Under 49.5 game total" with no game. Worse,
Social's Tail on FanDuel re-resolved each leg's FanDuel ids by key alone (fdmap), so every total with a shared number would have opened the
first game's market. Fixed together: Social shows "· DET vs NE" on every leg; fdmap also carries key@GAME for game lines and fdIds uses it
(never the bare key for a game line); Social's Load into my slip writes bs_slipg; the single-post page (/b/?p=) shows the game and hands
the builder key@GAME; the builder's ?add= accepts key@GAME; a promo's Tail saves its totals' games (data-g, home._tail_g).

## Phone Parlay Builder: slip sheet covered by header / buttons hidden (11/14)
Owner: "on the parlay builder a lot of times the screen gets weird on the phone where I can't see some of the buttons."
Root cause: phones zoom page content 1.1x (BIGGER_CSS in build_site.py, `body > :not(...)`). The slip (`aside.slipwrap`, a fixed bottom
sheet on phones) sat inside the zoomed `.bld` grid, so its height and bottom offset were scaled 10%: open, it ran ~20px up under the site
header (its own open/close bar hidden behind the header) and stopped short of the tab bar (page content peeking through the gap).
Fix: BIGGER_CSS skips `.slipwrap`; on screens <=900px the builder script moves the slip to <body> (and back above 900px), so its geometry is
real pixels; only `.slipwrap > .panel` gets the 1.1x (1.06 at 761-900). Open sheet tops out just under the header (dvh), the slip bar is
sticky at the top with a "Close" label, the FanDuel/DraftKings/Hard Rock row is sticky at the bottom, the sheet tucks 10px behind the tab
bar. `.bld .panel/h2/[hidden]` rules also apply under `.slipwrap` since the slip may live outside `.bld`.
Check: /tmp/slipchk2.py style Playwright run (open slip with 1 and 10 legs at 390x844, 375x667, 390x600): bar visible at top/middle/end of
the slip scroll, FanDuel never below the sheet, sheet top >= header bottom, Close works mid-scroll. Desktop slip position unchanged.

## Builder reload loop ("freaking out flashing", 11/15)
Owner screen recording: signed in, /build/ flashed between the page and a half-drawn page with "Synced from your account" over and over.
Cause: the builder's save() on load called localStorage.removeItem('bs_slipg_w<W>') whenever the slip had no totals (11/14 game-map change).
The account copy still had that key, so account.js pull() saw it missing locally, restored it, reported "changed" and reloaded the page;
the builder removed it again on load -> endless reload. Reproduced with a stubbed signed-in Supabase (/tmp/loopchk.py): 12 loads in 15s before.
Fix: builder/slipimport never removeItem the game map (write it, '{}' when empty); pull() pushes a local removal instead of restoring when the
local removal is newer; and a sync reload happens at most once per tab per 2 minutes (sessionStorage bs_sync_rl). After: 2 loads (one sync).

## Home order + collapsible Winners (11/15)
Owner: "make winners collapsible ... Daily Sweep, Winners, Promos, Everything else". home.winners_block wraps the cards in
<details id="wfold"> (closed by default, choice remembered in localStorage bs_winners_open). build_today.py leaves <!--bs:promos-->
right after Winners; landing_merge.merge drops the promos block there (falls back to the old spot with the other week blocks if the
marker is missing). Order now: sweep, winners, promo, bsunder, tdlooks, tdday, bestt, parlay, tdyou, news, record.

## Live page blank once a game kicks off (11/15)
Owner screenshot 9:00 AM: /live/ showed the header and chips only (no "updated" line, no cards) after DET-NE kicked off.
Cause: render() threw on a live game's ESPN summary (Gamecast reads drives/plays), and the 10-minute cache (bs_live_cache_w<W>)
brought the same summary back on every reload, so every redraw threw and nothing was ever drawn. Reproduced with a summary whose
drives.previous holds a null: live version blank after reload, fixed version draws all cards.
Fix (build_live.py): render() wraps renderCore(); Gamecast is drawn in its own try (a failure drops only that panel); on a failure
the cache is cleared and the page redraws without summaries; if it still fails, #upd says what broke.
Also: sw.js caches only ok responses (a 404 for a hashed file would otherwise stick until the next build), and reprice.copy_into_clone
keeps the previous build's linked data-<hash>.js in each replaced folder (pages cached a few minutes still find their data).

## Live blank, the real cause: snapshot legs without "ms" (11/15 9:21 AM)
The 9:00 fix put the error on screen: "undefined is not an object (evaluating 'l.ms.toLowerCase')". Once a game kicks off the builder
drops its legs, so Live fills them from in/legsnaps.json (D.extra, snap:1) - and those rows had no "ms" (short market name). Any saved
or starred slip holding such a leg made legText() throw and nothing drew. Fix: snapshot legs get "ms" from the builder's own
market->short map, and legText falls back to l.m. Check: a saved slip with a snapshot leg (e.g. a started game's yardage leg) draws.

## Risk check: real role, one big game, blowout script (11/15)
Owner after Week 10 Sunday (Metchie 5+, Fant 5+, Ridley 10+, Schultz 20+ yards and Kyren Williams 10+ receiving yards all lost on low
lines): "Yes make those changes" + "we have to understand when trends are going down and when there's more crowded rooms".
flags.py (WR/TE, player level): `Fringe role` (bad) = under 4 targets a game over his last four AND not in his team's top three targets;
`Quiet games` (watch) = 30%+ of games with one catch or none; `One big game` (watch) = season target average leans on one game
(max >= 2x median, average without it <= 82% of the average). build_builder.py (leg level): `Blowout script` (bad) on a running back's
receptions / receiving yards / longest reception when the model's likeliest ending is his team by 10+.
Checked on the game log through Week 9: Metchie, Fant and Ridley come out Fringe role, Schultz One big game. Low-risk legs on the
remaining Week 10 board went 118 -> 84. Chat-only rules (not in code): one slip per player per day, flat stakes, three legs when the
goal is cashing more often.

## Risk check, round two (owner 11/15: "Let's do all of it. Prepare 3 and 4 for the next rebuild.")

Five changes after the Week 10 Sunday losses. Code only; it ships with the next rebuild that passes the publish gates.

1. **Hard tags.** `sweep.HARD_RISK` = Losing zone, Fringe role, Blowout script, Target squeeze. A leg carrying any of them scores at least 2
   ("Some risk") whatever good flags it has, in `sweep.risk_score` and the builder's JS `riskScore` (keep the two lists in step). Reason:
   Dalton Schultz 20+ yards sat in a losing price zone and still read low-risk because three good flags cancelled it.
2. **Price gap.** `build_builder.py` adds a `watch` flag to floor legs (-180 or shorter, overs) where the model's own chance is 8+ points
   above FanDuel's no-vig chance. On those legs a big gap is a warning, not an edge. The build prints the count.
3. **Target squeeze.** `flags.py`, returning-teammate block: when the returner averaged 6+ targets in his last three games before going out,
   the receivers already playing get a `bad` flag with a number (last-four targets x 0.76). Backtest, Weeks 4-9 of 2026: 76% of baseline
   with a 6+-target returner (21 player-games), 96% with a 3-6 target returner (56), 94% with none (400). Small sample: re-run it after
   Week 13 before trusting 0.76. A full "share the team's targets" budget was also tested and did NOT beat a plain last-four average
   (miss 2.2397 vs 2.2387 at best, 648 player-games), so it was not built.
4. **Repeated players.** My BetSweep (`account.py`) shows a notice above the slip list when one player is on two or more open slips of the
   current week: the slips he is on and the stake riding on him.
5. **Why it lost.** Not code: the Tuesday slip-log grade adds a tag per losing slip (thin role / wrong script / bad luck).

`ROLE_RISK` in `home.py` and `build_boards.py` now includes Fringe role and Target squeeze.

## Better legs, round three (owner 11/15: "Do all of these")

Code only; ships with the next rebuild that passes the publish gates. Full numbers in `research/flag_grades.md`.

1. **Flags graded** (`flag_grade.py`): grades every flag on published boards against the game log, counting each player once a week.
   First run (Weeks 8-9): the risk score did not separate winners from losers; "Soft matchup" was the one flag clearly failing, so
   `sweep.TAG_W = {"Soft matchup": 0}` (the builder's JS reads the same table from the data file as `D.tw`). Re-run Tuesdays; a tag gets a
   weight only with 100+ player-weeks pointing the same way every week.
2. **Near-zero risk** (`build_builder.py`): floor legs (-180 or shorter) on a player who finished under half the line in a third or more of
   his games get a `bad` flag; fewer get an info line. Leg field `nz` = [games under half, games].
3. **Line moves**: `risk.js` exposes `BSRisk.move(key)`; the builder's risk score adds one watch point when FanDuel's price has drifted 3+
   points against a leg since the build (data/price-moves.json, live, no rebuild needed).
4. **Reliability**: players already had it (flags.py REL). Added team-by-market (`TREL`, 15+ graded legs, 20 phantom legs): -4 pts or worse
   = watch "Team under its prices", +4 or better = info. `data/reliability.json` lists every player and team-market score. Projection
   error was tested and left out (it pointed the wrong way).
5. **Legs that fail together**: the slip notes warn when 3+ legs (or most of a 3+ leg slip) need one team's passing game, and say how many
   separate bets the slip acts like (legs squared over the sum of the correlation matrix). `sweep.dependence(legs)` is the Python twin for
   chat-built slips.
6. **Pre-kickoff re-check**: already built (push/slip-alerts.ts, every 10 minutes: Out / Doubtful / game-day inactives on saved slips, with a
   swap idea; line-move pushes on saved legs). Nothing added. It only watches slips saved to an account, not slips sent in chat.

## Losing side (owner 11/15: "We should've never bet on Atlanta")

`build_builder.py` flags yardage overs (rushing, receiving, passing, rush + rec, longest reception) on the team the model's most likely ending
has losing by 10+ as `bad` "Losing side". Weeks 6-9 floor legs on that side hit 61% against a 71% price (439 legs); receptions held up and
are left alone. "Losing side" and "Near-zero risk" joined `sweep.HARD_RISK` (and the builder's JS list), so no good flags can clear them.
Numbers and the slip-shape replay: `research/slip_shapes.md`.

## Game-card parlay obeys the risk check (owner 11/15: "Why in the world would we have Germie Bernard 4+ receptions as the models best bet")

`build_boards.best_parlay` now drops any player leg whose flags score 2+ on `sweep.risk_score` (the Parlay Builder's Some/High risk tag) and
any floor leg (-180 or shorter) that fails the builder's near-zero rule. Before this the card only blocked `bad` role flags, so a `watch`
like "Fill-in fading" did nothing: Bernard (PIT, 0 catches on SNF) was High risk on the builder and the best parlay on the card.
The build prints how many legs the gate passed over. Numbers behind it (Weeks 6-9):
- game-card parlay player legs: 45 of 77 hit (58.4%) against 67.9% priced; 12 of the 32 misses finished under half the line, 6 at zero.
- by our own tag (Weeks 8-9): low risk 16 hit / 6 missed; Some or High risk 2 / 4.
- the model's chances at the top are not real: legs it had at 70-80% hit 65.2% (310 legs), 80-90% hit 56.4% (55). Legs passing the card's
  "65%+ and at or above the price" test: model 72.6%, FanDuel 66.8%, hit 67.0% (400 legs); at -200 or shorter 65.7% against 72.3% priced.
Open question for the owner: cap the model's chance at FanDuel's no-vig chance for "cash often" picks (the model may lower a leg, never raise it).

## Fill-in games need a teammate with a real role (owner 11/15: "Skowronek had nothing to do with Bernard. sko doesn't play snaps at all really")

`injweeks.fill()` credited a player's snap rise to ANY same-position teammate who was out those weeks and is back now. Ben Skowronek
(0-21% of PIT snaps) was out Weeks 6-8, so Germie Bernard's 91-94% snap weeks - caused by Pittman and Roman Wilson being out - were credited
to him: "Fill-in fading" on the flags, and those weeks set aside from Bernard's snap and usage trends (build_snaps.py, build_usage.py and
flags.py all call fill()). Now the absent teammate's median snap share in the games he played must be `MIN_VACATED_SHARE` (25%) or more.
Week 10 inputs: 124 players with fill-in weeks before, 119 after; the same error had Bucky Irving filling in for Sean Tucker (1% of snaps),
Josh Downs for Anthony Gould (0%), KC Concepcion and Malachi Corley for Tylan Wallace (16%). The flag text now states the hurt teammate's
snap share, so a wrong attribution is visible on its face.

Tested the same night and NOT built (research/slip_shapes.md has the method): a "targets cushion" on receptions floors (median targets
minus the line: under 2 hit 67.7%, 2-3.5 63.0%, 4+ 67.1% - nothing there) and the player's own clear rate against the price (10+ points
over the price hit 59.1%, the worst group - hot streaks are already priced). Forecast error (Brier) on 3,821 graded legs: FanDuel's no-vig
price 0.2402, our model 0.2482, own clear rate 0.2600; on legs the model had at 70%+ the model was worst (0.2821 vs FanDuel 0.2379). The
lowest of the three numbers was the only blend that stayed calibrated at the top (said 64.1%, hit 66.0%; said 72.1%, hit 68.2%).

## Honest chance, best bets off floor legs, show the work, owner veto, shadow list (owner 11/15: "Yes build all of that" ... "do everything you can think of")

Code only; ships with the next rebuild that passes the publish gates. Tests run 11/15: `python3 honest.py`, `python3 learned.py`,
sweep selftest, boards + builder + site build clean, phone-sized browser sweep of 41 pages (no JS errors, no sideways scroll).

- **honest.py** - the honest chance of a leg: what graded FanDuel legs at that price in that market actually hit (rebuilt from
  in/legsnaps.json every run, capped at 68%), minus a quarter of the gap when the model is lower, plus a fifth when the model is higher
  on a leg priced longer than -200. Each week scored on the other weeks: forecast error 0.2344 (model 0.2411, FanDuel no-vig 0.2351);
  it said 64.2% and legs hit 65.8%; legs the model had at 70%+ - model 75.6%, honest 63.0%, hit 63.4%. Tested and NOT used: a full model
  veto (too pessimistic: said 64%, hit 67%) and the player's own clear rate (no gain). Leg fields: `br` (band rate), `hp` (honest chance).
- **Game-card best parlay** (`build_boards.best_parlay`): no leg at -200 or shorter; a player leg needs the model 8+ points over the price
  (to +250), or 65%+ and at/above the price between -199 and -130. Weeks 6-9 (receiving yards, receptions, passing yards): model-liked
  floors -12.6% a leg (161 legs); model 8+ over the price on mid / even / plus legs +5% to +14% a leg (100 / 124 / 136 legs; not proven).
  The card shows the honest chance, fair price and EV ("graded"; the model's own number is in the tooltip) and a "Show the work" line per
  player leg: how often he has done it, FanDuel's implied chance, what legs at that price have hit. A leg he has cleared 15+ points less
  often than the band rate (5+ games) gets no best-bet label. On a thin board the slip falls back to game lines - check Tuesday's cards.
- **Builder**: every leg carries `br` / `hp` and an info flag "Price check"; the slip notes add a "reality check" (the legs' honest
  chances multiplied, next to the model's). Flags that failed the grade (weight 0 in `sweep.TAG_W`) and flags the owner marked wrong are
  dropped from the builder and the boards; the player page keeps everything.
- **Owner veto** (player-page note panel, risk.py): two new choices. "Avoid" -> `bad` flag "Avoid (BetSweep)", a hard tag, live on every
  page at once. "A flag on him is wrong" (name the flag in the note) -> that flag is dropped for him this week at the next rebuild and
  listed in the flag check. No database change: `risk_feed.status` is free text and risk_notes.py ignores the two for availability.
- **data/flag-audit.json** (the Tuesday flag check): the flags that moved the most players out of the low-risk pool, with the text each
  shows; the 20 biggest model-vs-FanDuel gaps (each is a real edge or an input bug - 11/15 top: Jacoby Brissett 200+ pass yds, model 26%
  vs FanDuel 62%, projection 156 vs a 215 average); the players with a flag overruled.
- **learned.py** - results-trained SHADOW list, `data/learned-w<week>-<mmdd>.json` on every build (singles 3+ points over the price, one
  per player; two-leg pairs from different games). Ridge logistic fit on all graded legs starting from FanDuel's price. Leave-one-week-out:
  its picks +6.2% a leg (698 legs) against -4.9% for the model's (1,633); features were chosen on the same weeks, so it grades in the
  shadow first. Drives nothing on the site until the owner says so.
- **"Safer" is gone**: tier labels now read "Short-priced" (results, season, ask, builder, guide); "safer swap" -> "easier swap".

## The board-shrank check compares like with like (owner 11/16: "Can we start a rebuild to get everything going today")

`reprice.board_shrank(bd, live, W)`: within a week it counts only the legs of games that have not kicked off, in the new build and on the
live site, and blocks under 60%. Finished games no longer count, so a Sunday-night or Monday rebuild can publish; a broken pull on a game
still to be played is still blocked. On a new week the board is not compared with last week's - it needs 200 legs. Before this, the
whole-board comparison (added 11/10) blocked every late-week publish (792 legs against 3,912 on 11/15).

## After the 11/16 rebuild: two things the first Monday publish showed

- **No best parlay on a game that has kicked off** (build_boards.py, at the `best_parlay` call). A rebuild after kickoff used to build a
  new "best parlay" for a game already played - the player legs are gone by then, so it fell back to game lines nobody could bet any
  more (DET-NE "Under 50.5 + NE +2.5" the morning after). The card now shows none once kickoff has passed. The pre-kickoff pick is
  still frozen in 'AUTO - Model Calls Archive' (build_calls.py only writes games not yet started), so grading is not affected.
  Open (alpha plan, item 1b): keep the pre-kickoff parlay on the card through the game and grade it there, from a published
  `data/best-parlays-w<week>.json`, instead of hiding it.
- **Renamed labels on pages a reprice does not rebuild** (rechrome.py, `RENAMED`). /season/ (Tuesday session) and the older receipts
  keep the words they were built with; rechrome now swaps the exact old label for today's ("Safer (65%+)" -> "Short-priced (65%+)").
  That is the one content change rechrome makes. Add a pair when a label is renamed; exact strings only.
- Wording: "a safer swap" -> "an easier swap" (slip check, home door), ladder button label "easier line" (builder and template.html).

## Next week's prices stay out of this week's build (weekgate.py, 11/16)

FanDuel posts Thursday's game early. On the Monday of Week 10 the price tabs already held Colts @ Texans (Thu 11/19, Week 11): 122 Leg
Board rows, 285 links, 26 first-TD prices, 20 unders, 222 game-line rows, plus the other books' prices for twelve Week 11 games. The Leg
Board joins price to projection by player, so those rows carried Week 10's projection against Week 10's opponent, and the builders filed
them under the team's (finished) Week 10 game. The first Monday rebuild that could publish put 150 of them on the site for 31 minutes
(13:57Z to 14:28Z: home page Model's Best, Boards, First TD, the shadow list, the flag audit). Until that morning the board-shrank check had
blocked every Monday publish, which is why it had not shown before.

- `weekgate.clean(IN, week)` drops, from legboard / bestlegs / links / bookodds / gamelines / ftdodds / unders in ./in, every row whose
  Game is not a pair on the week's schedule (in/games.csv), or is the right pair but four-plus days from the scheduled date. Rows with
  no readable game are kept. Archives (legsnaps, results_legs, closing) are not touched.
- Called by reprice.py right after the mirror is copied in (log line `[weekgate] ...`, summary field `next_week_rows`), and by
  build_firsttd.py, build_boards.py and build_builder.py as their first step.
- **By hand:** after `cp -r <mirror>/in/. in/`, run `python3 weekgate.py` before any desk step (consensus.py reads bookodds).
  `python3 weekgate.py --check` only reports; `python3 weekgate.py selftest` = 16 checks.
- Thursday's game appears on the site when the week rolls (Tuesday), with its own projections.
- Still open in the SHEET: the Leg Board tab itself shows those rows with the wrong week's projection until the roll.

## Social: settled slips stay (alpha step 1, 11/16)

social.py loads every open-status post of the week (no more "last 4.5 hours") and grades each on the page: open / live under Top and
New; **Cashed** tab = slips with every leg hit, busted ones folded under it; nothing open and nothing cashed -> "Last week's winners"
from `data/box-w<W-1>.json` plus a post button. House slips (`house_html`) carry their legs in `window.__BS_HOUSE` and are graded by the
same code, so they stay pinned through the game and for HOUSE_HOURS (12) after the last kickoff; hidden on the Cashed and Sharps tabs.
Grader changes: TDs are set per read, not added (a re-read doubled them); Passing TDs and Either TD are graded; a player the live box
does not list stays open (never a miss) - such a slip ends as "Final · n graded hits". Test: `python3 tests/social_feed.py [shots_dir]`
(fakes the account client and ESPN; needs ./site built).

## Busted slips leave the page, winners go to Winners (owner 11/16)

"Once one leg kills it, the bet should be off the pages or put into a lost tab. If it wins then it gets put into winners."
- **Home, live** (home.py PROMO_LIVE_JS): the moment a leg dies the card moves into a **Lost** fold (no waiting for the final); a promo
  that cashes moves into Winners and opens it. The Sweep hero is not moved: a busted Sweep is archived (strip: "Last ... Missed") with
  a copy in Lost; a cashed Sweep stays in the hero. "Cashed" now needs every leg of the card graded (a 13-leg slip whose Sunday legs
  had left the board was called Cashed when its one Monday leg hit). Passing-TD legs grade; TDs are set per read, not added.
- **Home, built** (`built_state`, `lost_block`): a promo is graded from the game log - the sheet's, or the nflverse weekly file for a
  week the sheet does not have yet - and one that has lost a leg is left out of the promo grid and listed under Lost with the leg
  that killed it. Unknown players are never a miss. Display only; the record is still the sheet's Result (Tuesday).
- **Social**: a **Lost** tab beside Cashed; a busted house slip comes off the pin.
- Tests: `python3 tests/home_filing.py [shots]` (18 checks), `python3 tests/social_feed.py [shots]` (22).

## Game cards keep their pre-kickoff best parlay (alpha plan 1b, 11/16)

build_boards.py files each game's best parlay on every build BEFORE its kickoff in `BP_FROZEN`, written to
`out/data/best-parlays-w<week>.json` and published as `/data/best-parlays-w<week>.json` (html + record + when it was filed). The next
build reads the published copy from the site clone (BS_SITE), else the last local one. After kickoff the card shows the filed parlay
with a chip - "Locked at kickoff", then "Cashed" or "Missed: <leg>" once `bp_grade` can grade it (player legs from the game log /
nflverse weekly file via home._glog, game lines from the final score) - and its add buttons are hidden. A game with nothing on file
shows no parlay block at all (the old "FanDuel has too few legs priced" line is only for games still to be played).
`BS_NOW_MS=<ms> python3 build_boards.py` builds as if it were that moment (tests only).

## Player pages lead with the last games against the line (alpha plan step 6, 11/16)

build_players.py `last10_block(p)`: under the header, one bar chart per main market for his position (QB pass / rush yds; RB rush yds,
rec yds, catches; WR and TE rec yds, catches): a bar a game, oldest to newest, up to ten (earlier-team games included), this week's
FanDuel rung priced closest to even drawn across as a dashed line, each bar marked over / under by colour and by a tick or dash, and
"Cleared 81+ in 3 of 9" in words. No props on the board this week = the season average is drawn and nothing is called a hit. Plain
HTML and CSS (site variables), no script. (The builder half of step 6 - the same picture inside a leg's details - was built the same day: `l10()`, see "Leg details lead with the picture" below. Nothing is left from step 6.)

## Social v3 database script (alpha plan step 2, 11/16) - the owner runs it

`sql/social_v3.sql` (placeholder `__CRON_SECRET__`, never commit a filled copy): feed_profiles (assigned handle, avatar colour;
`feed_profile_me()` makes it), feed_follows, feed_tails (only before the slip's first kickoff; count on the post), feed_reactions
(one per account per post: fire / lock / fade / rip; counts in `feed_posts.rx`), graded results on the post (`result`, `units`,
`graded_at`) written only through `feed_grade(secret, rows)`, and the view `feed_records` (graded, won, lost, units per account).
Tested 11/16 on a throwaway Postgres 16 with a mock auth schema: installs twice cleanly on top of v1; a user cannot edit a handle,
arrive pre-tailed or pre-graded, follow himself, follow as someone else, tail after kickoff or grade without the secret (the
placeholder itself is refused). Not tested against Supabase. Nothing on the site reads these tables yet.

## Social people, page side (alpha plan step 2, 11/16 - the owner ran sql/social_v3.sql at 11:47 AM CT)

social.py PAGE_JS: every post shows an avatar (colour from feed_profiles, else from the handle), the poster's record from
`feed_records` ("12-8 · +6.4u", only once something is graded), four one-tap reactions with counts (`rx`), a tail count and an
"I'm tailing" button before kickoff (not on your own slip). Tapping a name opens a profile (`#u=<uuid>`): record, units, graded
count, followers, Follow, their slips (older weeks use the stored `result`). New **Following** tab. A signed-in account gets its
profile row through `feed_profile_me()`. If the database lacks the v3 columns the page drops to v2 behaviour (`V3 = false`).
NOT built yet: the grading job that calls `feed_grade` (needs the owner's secret as a repo secret) - until it runs every record
reads as ungraded; "this week's sharps" strip; alerts. Tested with a faked client only (tests/social_feed.py, 34 checks) - this
workspace cannot reach Supabase, so the first real check is the owner tapping a reaction while signed in.

## Own username and avatar (owner 11/16; sql/social_v4.sql - the owner runs it, no secret in it)

`feed_profile_set(handle, color, emoji)`: username 3-20 letters / digits / underscores, clean, not reserved (betsweep, admin, support,
official, moderator, staff, fanduel, draftkings), unique ignoring case, one change every 30 days; avatar = one of eight colours plus
either initials or one of 24 fixed emoji (no uploads - nothing to moderate). Old posts take the new name; new posts carry the profile's
name. Direct edits of feed_profiles are closed. Page: a **My profile** button on Social, **Edit profile** on your own profile.
Until v4 is run the page hides the editor (`V4 = false`). Tested on the throwaway Postgres and with the faked client (42 checks).

## Correction, 11/16 12:05 PM: no Lost section on Today - the week's misses live on /receipts/

Owner: "I don't want the lost promos on the today/home page. Just in receipts somewhere." The Lost fold on Today (added at 10:42 AM)
is gone: a busted promo card is simply hidden the moment a leg dies, a busted Sweep leaves the hero (strip: "Last ... Missed"), and
slips the game log already shows lost are not built into the promo grid. `home.lost_block` now renders "This week's misses" at the
foot of /receipts/ (build_site.py). Winners behave as before; Social keeps its Lost tab.

## 11/16 afternoon: a bogus "best rung +53% EV" chip on every graded leg (fixed), and the picture in a leg's details

- **Bug, live 13:57Z-20:5xZ on 11/16.** The honest-chance block (11/15) wrote the price-band rate to `l["br"]` - the key the page's
  best-rung star (`trk()`) reads as its EV. Every leg with a band rate (302 of 302 player legs that afternoon) wore "best rung +NN% EV"
  with its band rate as NN (Herbert 200+ at -113: "+53% EV" beside "losing zone"). The band rate now rides as `l["bnd"]`
  (build_promo reads that); `br` is the best-rung EV again and nothing else. After the fix 30 ladders have a star, 1 of the 18 default
  cards. Found while testing the chart below. Open question for Tuesday: the star's EV still uses the model's shown chance, not the
  graded one - on the graded chance almost no rung is +EV.
- **Leg details lead with the picture** (alpha plan step 6, builder half): `l10()` in the page script - up to ten games, oldest to
  newest, against THIS leg's line (works for unders and TD legs), tick or dash under each bar, the line's label in a gutter on the
  right. The page's game log keeps ten games now (`GL_KEEP`, was six), so "4 of 8 this season" is the season again (it said "of 6").
  Text fixes: "scored a TD" (was "cleared scored a TD").

## 11/16 late afternoon: played games fold in the builder; Social shows up on Today and on game cards (alpha plan step 5)

- **Builder: "N games already played".** `renderGames()` splits the week into games still to come and finished ones
  (`finished(gid)`: live final, or a final score from the build, or kickoff + 4.5 h). Finished cards go inside
  `<details class="gdone">` at the foot of the list, closed while anything is left to play and open by itself when nothing is. They
  lose their price grid (nothing to bet). `doneOpen` keeps the reader's choice across re-draws; a tap on any `#g-<gid>` link opens the
  fold first so the jump lands. On Monday the page went from about 11,900px to 1,900px on a phone.
- **Chip row**: games still to come first (build time, `_NOW_MS`), played games after them and dimmed (`a.played`). The dimming is
  re-applied on the page by `chipState()` from the clock, so a page built before kickoff is right when opened after it. Order is only
  set at build time.
- **Today: "Top on Social"** (`social.strip_html(week)`, placed after the promos by build_today.py). Reads this week's posts with the
  site's account client, keeps the ones with a game still to be played, shows the three with the most upvotes (title or first leg,
  poster, leg count, tail count, price, upvotes), and links to all of them. Nobody has posted: one line and "Post the first slip".
  No account client (script blocked, offline): the section hides itself after a few seconds. It never writes anything.
- **Boards: a line on each game card** (`social.cards_js(week)`, appended by build_boards.py): "N slips on Social" ->
  `/social/#g=<gid>`, or for a game still to come with none, "Post a slip for this game" -> `/build/#g-<gid>`. A finished game with no
  slips gets nothing.
- **Social: one game at a time.** `/social/#g=BAL-LAC` keeps only slips with a leg in that game (`inGame`), says so in a bar
  (`gfBar`), hides the pinned house slips, and "Show every game" clears it. Works with every tab.
- Tests: `python3 tests/social_elsewhere.py` (19 checks) and `python3 tests/builder_fold.py` (24 checks; it freezes the page clock an
  hour before the week's last kickoff, so it means the same thing on any day). Both run light and dark at 390x844. Neither reads the
  real database - the account client is faked - so what real posts look like there is still to be seen with real posts.
- **Fixed 17 minutes after it went out (live 21:28Z-21:45Z): the Today strip hid every real post.** The database returns
  `first_ko` / `last_ko` as text ("2026-11-17T01:15:00+00:00"); the strip did `+p.last_ko`, which is NaN, so every post failed the
  "game still to come" test and the strip showed "No slips up..." whatever had been posted. It reads them with `Date.parse` now. The
  test passed because its fake database answered with numbers. Both Social tests' fakes now answer with text, as the database does.
  **Rule: a fake of the database must copy the column types in sql/*.sql** (timestamptz -> ISO text, numeric -> number, jsonb -> object).
- Wording under the leg chart: "**0** of his last 3 scored a TD" (was "0 of 3 of his last 3").

## Social grading job (alpha plan step 2, 11/16): social_grade.py + the `social-grade` workflow

- **What it does.** Every morning (9:40 AM Central) the `social-grade` workflow on main checks out gen-overrides, downloads the
  nflverse schedule, weekly player stats and snap counts, reads open ungraded posts whose last game has kicked off (public key, the
  same read any visitor's browser makes) and grades each one. Results go to the database through `feed_grade(secret, rows)` - the
  only way `result` / `units` can be written - and from there to the record on every post and profile (`feed_records`).
- **Certain or nothing.** lost = one leg missed; won = every leg hit (units = profit on one unit at the posted price); push = every
  leg pushed. Anything else is LEFT and reported with its reason, then read again the next morning: a game without a final score,
  stats or snap counts not out yet, a player who did not play (the book voids the leg and re-prices the slip - a price the job does
  not know), a pushed leg beside winners, First TD and longest-reception legs, unknown markets. A player with no stat line counts as
  zero only when the snap counts show him on the field. A player is looked up inside the two teams of his leg's game, so two men
  with one name are never mixed.
- **The secret.** The job writes only when the repo secret `FEED_GRADE_SECRET` holds the value the owner put in the database with
  his copy of sql/social_v3.sql (11/16). Without it every run is a dry run. The value is never printed and is not in this repo.
  Owner, once: GitHub > betsweep-site > Settings > Secrets and variables > Actions > New repository secret > name
  FEED_GRADE_SECRET, value = the long value in his READY file on the `cron_secret` line. A wrong value makes `feed_grade` refuse;
  the run then fails loudly and nothing is written.
- **Run it by hand:** Actions > social-grade > Run workflow > mode `grade` (default), `dry` (read and report, write nothing) or
  `probe` (which Social scripts the database has had and how much is in it - counts and yes/no only, no names).
- **Checked:** tests/social_grade.py (24 checks on made-up finals: rounding like the page, unders, game lines both ways, pushes,
  shared names, did-not-play, the secret never printed). On real Week 10 data it agrees with the promo grader on all nine of the
  week's posted slips (six lost on the same legs, three not final). feed_grade itself was tested on the throwaway Postgres with
  sql/social_v3.sql. NOT checked from the workspace: the live database (out of reach there) - the workflow's own log is the check.
- **Not graded by this job yet:** First TD legs (needs the first scorer from play-by-play) and longest reception (not in the weekly file).
- **First look at the real database (11/16 21:50Z, through the workflow's `probe`, counts only):** both Social scripts are in
  (v3 and v4). 24 open posts (Week 8: 9, Week 9: 7, Week 10: 8), 0 graded, 1 profile, 1 reaction, 0 tails, 0 follows.
  Dry run: 24 read, 24 lost, 0 won, 0 left - every one has at least one leg that missed on the numbers (checked leg by leg with
  `detail`; the nine legs graded as zero each have a zero stat line or snaps on the field). NOTHING WRITTEN - no secret yet. The
  first real run will therefore record 24 losses; the owner was told before adding the secret.
- **A game's Social link shows that game's slips, settled or not** (11/16). `/social/#g=CIN-PIT` used to open on the Top tab, which
  lists open slips only - so a card saying "3 slips on Social" led to "No open slips". With a game asked for, the feed lists every
  slip on it: open, then cashed, then lost.

## 11/16 evening: Boards folds played games; the note under the promos is short (alpha plan step 9)

- **Boards: "N games already played".** `sinkPlayed()` in template.html (runs on every live update) used to sink finished scorecards
  below the rest. Now, while a game is still to come, finished cards live inside `<details class="bdone">` at the foot of `.grid`
  (its cards in `.bdgrid`, same columns as the grid). Closed by default; the reader's open / closed choice holds through refreshes.
  It opens by itself only when the page ARRIVES on a link to a finished game, when a link to one is tapped (chip row, slate), or
  when a card the reader has open goes final. When nothing is left to play there is no fold: every card is in the grid in kickoff
  order. Not used in render mode (`body.render`). Cards are moved only when out of place. Monday on a phone: 13,008px -> 1,783px.
  (The unrendered cards had been counted at their 900px placeholder height - `content-visibility` was already on since 11/4, so
  plan step 11's cheap half was done; the fold removes the length.)
- **`finished` on Boards** comes from live.py: a final from the feed, a final score from the build (`data-final`), or kickoff + 4.5 h.
- **Today, under the promos**: the seven-line note is now what a reader must see (what these slips are; the commission line - a
  disclosure is never tucked behind a tap) plus "How tailing and sharing work", which opens the rest (`home.PNOTE_CSS`, `.pnote`).
- **Screenshot caution:** on a short page, jumping straight to the very end makes the sticky title bar collapse and the page 60px
  shorter in the same frame; a Playwright phone screenshot taken then shows the header 60px low and no tab bar. The DOM positions
  are right (checked). Take end-of-page screenshots a little above the end.
- Tests: `python3 tests/boards_fold.py` (20 checks, clock frozen like builder_fold) and the promo-note check in tests/social_elsewhere.py.
- **Grading secret, 11/16 4:20 PM CT:** the owner said the GitHub secret was done; the workflow's `check` mode (asks the database
  with an EMPTY list, writes nothing) saw no Actions secret named FEED_GRADE_SECRET in three runs, while it could see
  SHEETS_SA_JSON. Told the owner where to look. Never reference a multi-line JSON secret in that job: GitHub then hides every brace
  in the job's log.

## GitHub's own schedule cannot be trusted here; the database timer can (measured 11/16) - sql/github_timers.sql, the owner runs it

- **Measured on Monday 11/16:** scheduled runs GitHub actually started - reprice 3 of 17 due (01:48Z, 09:55Z, 22:14Z; every other
  rebuild that day was a hand dispatch from a session), sheet-mirror 3 of 48, price-moves 3 of 48, risk-notes 3 of 48, and on
  Sunday 11/15 the game-day inactives job 3 of about 22. Nothing was cancelled - the runs simply never started. Meanwhile the
  database timer (pg_cron + pg_net, push/betsweep-live-fast.sql) started feeds.yml 20 times an hour for five hours on Sunday
  night without a miss. So "hourly auto-reprice with no session" (owner 11/10) has in practice been "a few times a day".
- **Fix:** `sql/github_timers.sql` puts every scheduled workflow on the database timer at the times its own file names: sheet
  mirror :05/:35, price moves :12/:42, risk notes every 30 min, reprice (publish = changed) hourly on game days and every three
  hours otherwise, game-day inactives on Sundays and Thursday / Monday evenings, Social grading 9:40 AM Central. No secret in the
  file: it lifts the GitHub token from the existing betsweep-feeds timer jobs inside the database and refuses to run if there is
  none. Safe to run twice. Its last statement lists job names and times only. Stop it:
  `select cron.unschedule(jobname) from cron.job where jobname like 'betsweep-gh-%';`
- Tested on the throwaway Postgres with a stand-in cron / net schema: refuses without a token or with the placeholder, makes 11
  jobs, each job's command posts the right workflow and inputs with the token, second run leaves 11. NOT run on Supabase - the
  owner's step. Until he does, a session must dispatch by hand: gameday.yml, then sheet-mirror.yml, then reprice.yml.
- The rebuild refuses a mirror older than 180 minutes (reprice.py --max-age); with the mirror arriving three times a day that
  limit alone would have skipped most scheduled rebuilds even when they did start.
- **11/17, one job was left out: the ESPN mirror (feeds.yml).** The database starts it every three minutes in game windows
  (betsweep-feeds-*: Sun 10 AM - midnight, Mon / Thu 5 PM - midnight Central), and everywhere else it was still on GitHub's
  schedule. Measured over 11/13 - 11/17: 38 scheduled runs where about 600 were due; gaps of 6 to 7 hours on Saturday, Sunday
  morning and Monday (Mon 11/16: nothing between 10:57 AM and 5:00 PM Central - Ladd McConkey's scratch reached the site with the
  first game-window run at 5:00 PM). What rides on that mirror: the injury list behind the risk chips, the refused adds and the
  "X is OUT" pushes (ESPN blocks the database, so slip-alerts reads the mirror), the Questionable translator, the news desk,
  kickoff weather, the Live page's "What changed".
  `sql/github_timers.sql` now has a twelfth job, `betsweep-gh-feeds` (every ten minutes, all week). Tested on the throwaway
  database (stand-in cron / net schemas): 12 jobs, the three older betsweep-feeds / alerts jobs untouched, a second run leaves
  12, the job's command runs and posts feeds.yml. **The owner has to run the file again** - until he does, the mirror is only
  as fresh as GitHub's schedule outside game windows. (A workflow-file route - risk-notes and price-moves asking for a mirror run
  when the feeds branch is over eight minutes old - was written and not pushed: a session may not push workflow changes to main
  on its own. The patch is in the owner_send folder of the 11/17 session if he prefers that.)

## 11/16, 8:05 PM CT: the grading secret and the database timer are both in (owner's steps, verified)

- **Secret.** GitHub now has the Actions secret FEED_GRADE_SECRET. The first `check` was REFUSED by the database (HTTP 400 "Not
  allowed"): the pasted value carried a stray space or line break. social_grade.py now trims the value (`secret_env()`), and
  `--check` prints its shape only - length, whether stray space was trimmed, and the first six characters of its SHA-256 - so a
  copy can be compared with another without showing either. After the trim: accepted, length 43, same fingerprint as the value in
  the owner's file from the morning. Nothing was written (the check sends an empty list).
- **Timer.** The owner ran sql/github_timers.sql. Seen on GitHub right on the slots, started by dispatch (not by GitHub's schedule
  and not by a session): risk-notes 02:00:01Z, sheet-mirror 02:05:01Z. From here the mirror, the rebuild, price moves, risk notes,
  game-day inactives and Social grading run from the database timer. If runs stop arriving: Supabase > Database > Cron jobs
  (names `betsweep-gh-*`), and check that the GitHub token stored with them has not expired (1 year from 11/5).
- **First graded run:** the timer starts `social-grade` (mode grade) at 9:40 AM Central on 11/17. Expected from tonight's dry
  runs: 24 posts recorded as lost, 0 won; tonight's game adds whatever was posted on it. The owner was told this three times and
  did not ask to start records at Week 11.

## 11/16 night: My BetSweep opens on a hub (alpha plan step 7); the Social block sits below today's game

- **The hub** (`account.py`: `#hub` in `me_page()`, `hubRender()` / `hubGo()` in ME_JS, styles at the top of ME_CSS). Three tiles
  and a chart, filled from the SAME numbers the slips list already works out (nothing is graded twice):
  Open slips (this week's ungraded slips: how many, units at stake, what they pay if all cash) - Record (W-L over every graded
  week, units) - Week N (that week's units once something is graded; "nothing graded yet" instead of a zero). Under them,
  **Profit by week**: a bar per week with saved slips, above the line for a winning week, below it for a losing one, an open
  ring for a week not graded yet; tap a week and its slips open in the list. Weekly, not daily: saved slips are graded from the
  weekly box files (`/data/box-w<W>.json`), so a week is the smallest honest unit. With nothing saved the hub says so.
- **Order on the page:** who line, hub, Your slips (open by default now), Bankroll (folded by default), import, exposure, alerts,
  email, builder, trades, fantasy, then the Theme switch (moved from the top - it is a setting). The two long intro paragraphs
  became one line each with "How ... work" behind a tap (`details.how`). A reader's own folded / open choices are kept
  (`bs_me_fold2`).
- The header already carries the way in: signed in, the "My BetSweep" pill with the account's initial; signed out, "Sign in".
- **Today:** "Top on Social" moved from above today's game to just below it. The 11/11 rule for that page stands: the head, then
  the game, with only the day's own callouts (Daily Sweep, winners, the day's other posted slips, Under of the day) between.
  tests/home_compact.py now names `promo` among those callouts.
- **Tests:** `python3 tests/me_hub.py` (20 checks, made-up slips and box files, light + dark). tests/social_elsewhere.py now freezes
  the page clock two hours before the week's last kickoff and reads the games and the week from the built pages, so it means the
  same thing on any day of any week (it failed after Monday's kickoff until then). tests/builder_fold.py asserts chip ORDER only
  for a page built before the last kickoff. STILL TIED TO WEEK 10: tests/social_feed.py and tests/home_filing.py (hard-coded
  BAL-LAC / week 10) - rework them the same way after Tuesday's roll.

## 11/16 late: post a slip to Social from a FanDuel screenshot (alpha plan step 3)

- **Social > "From a screenshot"** (`social.SHOT_CSS` / `SHOT_JS`, panel `#shot`). The picture is read on the phone by the reader
  My BetSweep already uses (`/import.js`, slipimport.py - tesseract.js from jsdelivr, loaded only then; the picture never leaves
  the device). The panel lists every leg it found: postable ones, and for the rest the reason - "that game has already kicked
  off", "not on this week's board at that exact line", or not a market we price. "Post these N legs" loads exactly those legs
  into the Parlay Builder (`BSLoadSlip`, the 11/1 path) and leaves a single-use note in the tab (`sessionStorage.bs_postnow`:
  the leg keys, the time, and the slip price from the picture - the price only when every leg came along, since a price for seven
  legs is wrong for five).
- **Builder:** arriving on `#slip` with a note less than two minutes old AND with exactly those legs in the slip, it opens its own
  post form by itself. The form (`POST_JS`) fills "FanDuel price you got" from the note only while the slip is exactly those legs
  (up to 30 minutes). Nothing is posted until the reader presses Post; signed out, the usual sign-in opens first.
- `window.BSImport.gmap` is now exported for it (which game a "total" leg belongs to).
- **Tests:** `python3 tests/social_shot.py` (30 checks, light + dark). The picture reader is stubbed there - it cannot load in the
  workspace; its parser has its own checks from 11/1. NOT tested: a real screenshot through the real reader on a phone, and a real
  post to the database (the test's database is a fake whose insert answers like the real one).
- Caught by the test before it shipped: an apostrophe inside a single-quoted string in SHOT_JS ("this week's board") broke the whole
  script. When a JS block is written through a Python patch string, `\'` is eaten - use double quotes for text with apostrophes.
- **The weather step no longer stops every publish between Monday night's final and Tuesday's roll (11/16 late).** The moment the
  last game went final the feed moved to week 11; weather_feed.py answered "week 11 != 10" and, being a `flag` step, failed the
  whole rebuild (exit 6: built, not copied) - reprice 44018775763 at 04:40Z, and it would have failed every hourly rebuild until
  the roll. Weather only flags games still to be played, so: feed exactly one week ahead AND every game of the build's week has
  kicked off (schedule in in/games.csv, Eastern kickoff times; a final score also counts) -> the sheet's weather stays, the step
  says so and passes. Any other mismatch, or a week whose schedule cannot be read, still fails as before. `python3
  tests/weather_gate.py` (7 checks).

## 11/16, near midnight: a posted slip's label follows the clock; a card shows the angle and the reason, not the whole caption

- **Label by the clock** (`home._pst()` at build time, `clock()` in PROMO_LIVE_JS on the page). An ungraded slip said "Pregame"
  for as long as live scores did not load - hours after the game on a page built late or with the score feed blocked. Now: Pregame
  before the first kickoff, In play from it, "Final - grading" 4.5 hours after the last one. Nothing is claimed about the result;
  Busted / Cashed still come only from the box score. `python3 tests/promo_clock.py` (4 checks, score feed blocked; skips itself
  when the build carries no ungraded slip).
- **Caption on a card** (`home._site_cap()`): a caption is written for X / Instagram - title, an angle line, each leg on its own
  line, then "Why: ..." or "Needs: ...". The card already prints the title and the legs and had lost the line breaks, so it read
  as one long paragraph repeating the legs. A caption of that shape now shows as the angle line and the reason; any other caption
  is printed whole with its line breaks (`p.cap.whole`). Share, the graphics, the short-link page and the X post still use the full
  caption.
- **Tests on a build made after the week's last game.** Such a build carries every game's final, and a final beats the clock, so
  the fold tests' "an hour before the last kickoff" saw 14 played games. They now serve the page its own data with the last game's
  final taken out for that phase (builder: `/build/data-*.js`; boards: the page itself, `data-final` on the last card).
  **The site has a service worker that answers page loads itself after the first visit** - a test that patches a page must open
  its browser context with `service_workers="block"` (tests/boards_fold.py does), or the second load is the unpatched page.
- **How the service worker serves a returning visitor (read 11/16):** pages and `/data/` are network-first (always this build's,
  the cached copy only when offline); every other same-site file - `/import.js`, `/account.js`, the hashed data files - is
  cache-first inside a cache named after the build. A new build ships a new `sw.js`, which replaces the cache, but on the ONE visit
  where it is installing the old worker can still hand out the previous build's shared script next to the new page. So new page
  code must tolerate the previous build's shared scripts: guard anything newly exported (the screenshot posting checks
  `BSImport.gmap` before calling it).

## 11/17, 12:40 AM CT: every page test now runs in any week

- **tests/home_filing.py was rebuilt on made-up slips** (36 checks). tests/fixtures/promos_w10_mnf.json holds two built promo
  records (the Sweep and a side slip with a +7.5 leg); the test gives them a kickoff two days ahead, renders them with the current
  `home.sweep_block` / `home.promos_block`, swaps them into the built Today page in place of its own Sweep and promo sections,
  fakes the score feed for BAL / LAC and sets the page clock around the kickoff. Cases: pre, bust, cash, cover, nocover, and
  "herbert" (11/16 as it happened: 129 passing yards, no passing TD). Service workers are blocked in its browser context.
- **tests/social_feed.py** reads the week from the built Social page (was hard-coded to 10 / 9).
- **The full set to run before a publish** (all week-independent now): reprice.py --publish none, then tests/home_filing.py,
  promo_clock.py, social_feed.py, social_elsewhere.py, social_shot.py, builder_fold.py, boards_fold.py, me_hub.py,
  social_grade.py, weather_gate.py, and the crawl - since 3 AM on 11/17 that is `python3 tests/local_gate.py` (the bare site_crawl.py call opened nothing; see that section).


## 11/17, ~2 AM CT: the Live page graded finished games it had no numbers for - winners shown dead, losses saved (fixed)

Found on the page-by-page pass (alpha plan step 9, Live), by opening the page on a finished week with ESPN cut off.

- **What was wrong.** The score feed the pages share (`live.py`, `window.BSLive`) stops asking ESPN once every game that has kicked
  off has a final score in the build - right for the boards and the builder, which only show the score. The Live page also needs a
  box score to grade legs, and its only box score was ESPN's, fetched per game through an ESPN id that only the feed supplies. So
  from the first rebuild after a slate's last game until the next kickoff (Friday to Sunday morning for the Thursday game, Sunday
  night to Monday night, Monday night to the Tuesday roll) the page had no score and no box score, and graded anyway: game lines
  against 0-0, every player leg as "dead - stats not loaded". Five legs that had all won read "5 legs, 0 hit, 5 dead - DEAD",
  My week read 0-5, and those five losses were written into `bs_log_w<week>` (My season, synced to the account). The ↻ button
  forced the feed and put it right until the next visit. In the code since at least 11/4.
- **The rule now (build_live.py `live()`):** a leg is settled only when the game is FINAL and the page holds real numbers for it.
  - no final score -> game-line legs wait ("final score not in yet"); in play with no feed they say "score delayed" (was 0-0 math)
  - no stat line for the player -> the leg waits ("not graded yet"). In play a man missing from a loaded box score still counts
    as 0, as before; after the final he may simply not have played, so he waits
  - did not play (the build's snap counts say so) -> **void**, never a loss. A slip with a void leg can still cash; the card says
    FanDuel voids the leg and pays the rest at a shorter price, and it does not show the full-ticket payout or the win card
  - the end of regulation is not final (a tie going to overtime used to flash every open leg dead for a moment)
  - waiting and void legs are never written to My week / My season; a result saved earlier is kept while its leg waits, so a slow
    box score cannot erase it; a record the bug filled with losses is rewritten the next time the page has real numbers
- **Where the real numbers come from now.**
  1. **The build (new, `finals.py`).** `D.fb` = for every game with a final in in/games.csv: the score, each leg player's stat line
     from the nflverse weekly stats, and who did not play (no stat line and no snaps, for a name those files know from another
     week). A box is only handed over when both teams have rows and the points the file credits to each team's players add up
     to that team's final score (297 of 300 team-games this season do; a mismatch means score only). With these the page needs no
     ESPN call for a finished game. `finals.refresh()` tries for a newer nflverse copy when a final game is missing from the one
     on hand (the hourly build keeps one copy per day).
  2. **The schedule's final-score text** (`g.fin`) when there is no `fb` entry.
  3. **ESPN**, as before, for a game in play, for a final the build has nothing for yet (Sunday evening), and for the two things
     the files lack - first touchdown and longest reception - when the reader holds or opens such a leg. The page now asks the
     feed once (`askScores()`) when a finished game has no ESPN id, so "Box score & plays" works on finished games again, and it
     retries a failed box score after a minute (it used to try once and then treat the game as "loaded, everybody 0").
- **Also fixed on the way:** finished games showed "– – –" instead of the score; a closed game inside the open Final fold said
  "Hide"; the game chips under the title did nothing for a game inside a closed fold (they now open the fold and the card and
  scroll to it, and so does a `/live/#lv-GID` link from search); the line "No game in progress · the watch list below..." was
  shown on a finished week with no watch list below - it now says the week is finished, gives next week's first kickoff from the
  schedule, and links to Receipts and My BetSweep.
- **Tests:** tests/live_finals.py (29 checks, made-up final and box score for one game of whatever week is built: finals in the
  build with ESPN cut off; score only; nothing at all; ESPN answering; a real loss; a void; in play; end of regulation; no feed)
  and tests/finals_build.py (16 checks, no network). Both are in the pre-publish set from now on.
- **Known:** touchdowns on returns are not counted as anytime touchdowns (same as before, and as the Social grader).
  (Correction to the 1:10 AM log row: My BetSweep does NOT grade a did-not-play leg as a loss - `gradeKey()` leaves a player who is
  not in the weekly file ungraded, "no box score (did not play?)".)

## 11/17, ~2:30 AM CT: Live follows a slip's total in the right game; the first screen is the game

- **A game total was matched by its number alone.** "Over 38.5|Total|39" is the main or an alternate total of most games, and the
  Live page took the first game that had it: Monday's Daily Sweep total (BAL-LAC over 38.5, -125) was being tracked against ARI-LA's
  over 38.5 (-108, final 40) - it read "hit" before Monday's game kicked off - and My week counted it once per game. The builder
  has kept a game map for such keys since 11/10 (a saved slip's `g = {key: [gid, ...]}`, the builder slip's `bs_slipg_w<W>`); the
  Live page now reads it (`resolveSlip()`), and with nothing on record uses the one game the slip's other legs are in (a same-game
  slip), else the first game as before. It also WRITES the map: adding a leg with + from a game card, pasting a slip (the team
  named with the total decides the game) and removing a leg with × all keep the record in step, for saved slips and the builder
  slip. "In a slip" marks, My week and pins go by the leg in its game (`legSlips()`, `isStar()`), not the bare key. The builder
  slip's keys are kept as a list (they were de-duplicated on every save from this page).
- **A game with nothing in the picks hid its other legs** ("Nothing tracked for this game in the picks yet." and no "Other legs").
  The list is there now.
- **First screen** (same treatment the other pages got): the tools are one line (status, "Import a slip", ↻; 44px buttons) instead
  of a card; the hub box is not drawn when its only tab would be "What changed - nothing new" (it is back the moment there is
  something new, a slip, or a pinned leg); the status line gives one time ("Live scores as of ..." while a game is on, else
  "Updated ..."); the chips under the title dim finished games, mark the game in play and bring it into view; a jump lands the card
  just under the header and the chip row (the title above the chips scrolls away, so the spot is measured after the move). A game
  in play now starts 228px from the top of a phone screen (was 375).
- **An open card of a game in play or finished** leads with the field / box-score button and the leg lists; its pregame notes
  (home, field, rest, coaches, tested spots, forecast) come last under "Pregame notes", folded. Before kickoff nothing changed.
- **Tests:** tests/live_gamemap.py (13: on record, same-game fallback, My week counts once, the builder slip, + from a card, × in a
  slip, a pasted total) and tests/live_first_screen.py (35: the three states in light and dark, chips, jumps, tools, notes).
- **The full set to run before a publish is now:** reprice.py --publish none, then tests/home_filing.py, promo_clock.py,
  social_feed.py, social_elsewhere.py, social_shot.py, builder_fold.py, boards_fold.py, me_hub.py, social_grade.py, weather_gate.py,
  finals_build.py, live_finals.py, live_gamemap.py, live_first_screen.py, and the crawl - since 3 AM on 11/17 that is `python3 tests/local_gate.py` (the bare site_crawl.py call opened nothing; see that section).
  The live tests take `SITE=<a published copy>` to check what went out.

## 11/17, ~3 AM CT: earlier weeks' saved results are re-graded once; a First TD leg is not busted by a box score that did not load

- **Earlier weeks (`fixSavedWeeks()` in build_live.py).** The week the Live page is on heals itself (above); a week that has rolled
  cannot, and its saved record (`bs_log_w<W>`, what My season adds up) may hold what the bug wrote on a Monday night or a Tuesday
  morning: player legs as losses, UNDERS as wins, game lines graded on 0-0. 3.5 seconds after the page loads, each saved earlier
  week is checked against that week's graded file (/data/box-w<W>.json - the file My BetSweep grades from). Only what the file
  settles is changed, in either direction: a player with a stat line, a moneyline or spread whose team played, a game total when
  that week's saved slips put exactly one game on record for it. Left exactly as saved: any other total (the row does not say which
  game), a first touchdown, a push, a player the file does not list, markets the file has no number for. No row is added or removed.
  My season says how many saved results were corrected on that visit. A week is read again only when its saved text changes
  (`bs_logchk`, kept on the device, not synced), so a stale copy coming back from another device is put right again; a corrected
  week is written once and syncs to the account like any other save.
- **First TD on Today and Social.** Both pages called a First TD leg dead when the game was final and they held no first scorer -
  which is also what a box score that failed to load looks like. A promo card would have shown Busted and left the Today page.
  Both now need that game's box score to have been read (`SUMOK[gid]`) before saying no one on the slip scored first.
- **Tests:** tests/live_regrade.py (22, rows built from the real file of the week before the one the site is on).
  Add it to the pre-publish set.

## 11/17, ~2:30 AM CT: a return touchdown pays an anytime-TD leg in every grader

- Every grader counted rushing and receiving touchdowns only. The book pays an anytime-TD (and 2+ / 3+ TD, either-or) leg on a kick
  or punt return and on a recovered fumble too; in the nflverse files that is about 15 offensive players a season (24 player-games
  over 2025 and 2026 so far - returners such as Parker Washington, Kalif Raymond, Ray Davis). Each was a win we would have graded lost.
- **From the nflverse files** (checked against real rows): `social_grade.Finals` rows carry `xtd` = special-teams + defensive +
  fumble-recovery touchdowns, the Social grading job adds it (`tds()`), and `finals.py` hands it to the Live page as the thirteenth
  number of a stat row (`td = rush TD + rec TD + other`).
- **From ESPN's box score in the browser** (Live, Today's promo cards, Social): the `kickReturns` and `puntReturns` tables are read
  for a touchdown column (any key with "touchdown" in it). **Not checked against a live ESPN answer** - the workspace cannot reach
  ESPN and the feed snapshots on the `feeds` branch keep only processed numbers. If ESPN names those tables differently nothing
  changes (the old behaviour); check it on the first return touchdown, or from a phone's network log on a game day.
- **The weekly box files** (/data/box-w<W>.json, from the sheet's game log) still hold rushing and receiving touchdowns only. So
  the re-grade of earlier weeks may confirm a TD leg but never takes one away, and My BetSweep can still show a return-touchdown
  leg as a miss for a past week. Fixing that means a touchdown column for returns in the game log tab - the owner's sheet.
- Tests: social_grade 28 (a punt-return scorer), finals_build 17, live_finals 31 (a return touchdown from the build and from an
  ESPN-shaped box), live_regrade 23.

## 11/17, ~3 AM CT: a finished week no longer offers bets on games that are over (end-of-week sweep of every page)

Done by opening every main page on a finished week with the score feed cut off (the state the site is in from Monday night to the
Tuesday roll) and reading what a phone shows.

- **First TD** had no idea of time at all: "Most likely to score first" and "Best edges vs FanDuel" listed finished games' players
  all week, and 31 "add to slip" FanDuel links were live on a week with every game over. Each game section and list row now carries
  its kickoff time; by the clock a kicked-off game is marked "Kicked off", loses its FanDuel buttons and has its chip dimmed, its
  players leave the two lists and the next ones move up (60 rows are built, 12 shown), and when nothing is left the lists say so.
- **Best parlay** (Today and Model's Best): a kicked-off game's parlay only dimmed and kept "Add all to FanDuel". It now loses its
  bet buttons and says "kicked off"; Today drops its lead parlay once that game has kicked off; Model's Best, once every game has,
  shows one line ("...none of its parlays can still be bet. Next week's post Tuesday.") instead of the cards.
- **The Daily Sweep record** on Today read "Record 1-0 · +3.0u" above a slip marked Missed: the two Sweeps that had lost were not
  graded yet (grading is Tuesday's). The line now names them: "Record 1-0 · +3.0u · 2 to grade Tuesday".
- **When does next week arrive?** Today said "the next slate lands Thursday morning" (twice), the short page "Next week's picks
  land Tuesday". The roll is Tuesday; Today now says "Graded on Tuesday · next week's board posts the same day" and "...posts
  Tuesday and its prop prices fill in by Thursday".
- **Social's house slips** kept "Tail on FanDuel" on a slip whose game was over whenever the score feed did not answer. By the
  clock the slip now reads "In play" / "Final · grading" and the tail link goes at kickoff.
- **Left as they are (looked at, fine or minor):** Line shop's opening sentence counts legs "right now" beside "Every listed game
  has kicked off"; Usage still links two FanDuel prices for "best-priced leg this week"; Missed by one and Usage are a week behind
  until the roll (they are weekly pages); the Season page's Daily Sweep line is last Tuesday's and is rebuilt at the roll - check
  after grading that Today, Season and Receipts give the same Sweep record.
- **Test:** tests/week_end.py (16: First TD before / during / after the week in light and dark, the parlay block on Today and on
  Model's Best, Today's wording, the record line). Add it to the pre-publish set.

## 11/17, ~3 AM CT: the local page crawl had been opening nothing - use tests/local_gate.py

- `SITE=./site python3 tests/site_crawl.py` only picks the list of pages from SITE; it loads them from a server on port 8801. With
  nothing answering there it still wrote one row per page, printed "pages 488" and exited 0. Every local "488-page crawl ok" on
  11/16 and 11/17 before 3 AM was that: no page had been opened. What did hold: the publish workflow runs the same crawl and
  `gate.py` against the site clone with its own server before it pushes, and every publish passed that.
- Now: `site_crawl.py` stops (exit 2) when nothing answers at its address, after a few retries. **`python3 tests/local_gate.py`**
  serves ./site on a free port, borrows /data/price-moves.json from the clone (the price job writes that file straight to the live
  site, so a fresh build lacks it and every page would report it missing), runs the crawl and the gate, and exits with the gate's
  verdict. `SITE=<clone> python3 tests/local_gate.py` checks a published copy. It takes about three minutes for every page; a regex
  argument limits it (`'^/(live|firsttd)/$'`).
- First real local run (3 AM, the build that went out as main 23853f97): 488 pages, 0 problems; the published copy: 514 pages, 0.
- **The full set to run before a publish:** reprice.py --publish none, then tests/home_filing.py, promo_clock.py, social_feed.py,
  social_elsewhere.py, social_shot.py, builder_fold.py, boards_fold.py, me_hub.py, social_grade.py, weather_gate.py,
  finals_build.py, live_finals.py, live_gamemap.py, live_first_screen.py, live_regrade.py, week_end.py, inactive_block.py, reprice_live.py, sgp_price.py (11/17 noon), how_stats.py (11/17 1:30 PM), flag_stats.py (11/17 2:45 PM), trade_outlook.py (11/17 3 PM) (both added
  11/17 morning), `python3 availfix.py selftest`, `python3 news_desk.py --selftest`, and tests/local_gate.py.

## 11/17, ~3:15 AM CT: a leg on an inactive player is void on the Live page from the inactives list

- The change feed the Live page already reads ("What changed") carries an "inactive" note for every player on a game's inactives
  list, about 90 minutes before kickoff. Ladd McConkey's went out at 5:00 PM CT on Monday, 2 h 15 before kickoff; on the Live page
  his legs still read as open, sat at "0 / line" all game and then (old code) went dead - while the book had voided them.
- Now (`inactive()` in build_live.py): a player with an inactive note for THIS game (his team, noted between 36 hours before and
  6 hours after kickoff) and no stat line has his legs shown as **void** before, during and after the game - same treatment as
  "did not play": the slip can still cash, the payout line and the win card are left out, nothing is saved as a win or a loss.
  If he shows up in the box score after all, the note is ignored (a wrong note cannot void a man who is playing).
- A void leg is left out of a slip's "pregame" chance as well as its chance from here.
- ~~The builder, Today and the boards do not use this yet: a leg on an inactive player can still be picked there until FanDuel pulls
  it.~~ **Wrong - corrected 11/17 7:45 AM (section below).** Those pages have refused a ruled-out player since 11/1 through the
  live injury list (risk.js), which gets the inactives too. What was really open is listed in that section.
- Tests: live_finals.py 35 (inactive before kickoff, in play, a wrong note, a note for another team or another week).


## 11/17, 7 AM CT: a desk "Questionable" no longer outlives the official injury report (availfix.py)

- **What was wrong.** The news desk enters a player as QUESTIONABLE from ESPN's team page early in the week. Nothing took the row
  back when the team's own report came out without him. Justin Herbert ("Questionable (Finger) - avoided a fracture", Mon 11/09)
  was never on the Chargers' Week 10 report; the row said QUESTIONABLE through Monday night, which put a "Questionable" flag on
  every Herbert leg (a point toward "Some risk") and "LAC QB questionable" into the game card's Low confidence.
- **How common.** Week 10 ended with 7 desk Questionable rows. The final reports contradicted 5 (Herbert not listed; Chig Okonkwo,
  Darnell Mooney, Hunter Henry, Keaton Mitchell listed with no game status - the three with snap counts in played 56-71% of
  snaps), agreed with 1 (Amon-Ra St. Brown, officially Questionable), and 1 was on a bye team (Luther Burden).
- **The rule** (`availfix.decide`, only for rows whose reason starts with "NEWS DESK:" and whose status is QUESTIONABLE):
  final report in (someone on his team has a game status) -> Out / Doubtful there = OUT; Questionable there = stays; listed with
  no status = CLEARED; not listed = CLEARED. Practice reports only -> not listed and the note is 3+ days old = CLEARED; else stays.
- **Not listed could mean injured reserve** (reserve players are not on the weekly report), so "not listed" clears only with two
  proofs: the nflverse roster has him ACT (file under 60 hours old) and ESPN's injury page (feeds mirror) lists him as nothing
  worse than Questionable. If either is missing the row stays and the log says `held:` with the reason.
- **Where it runs.** reprice.py, right after weekgate and before the desk (summary fields `avail_fixed`, `avail_held`); a session
  by hand in Step 2a-ii, which also writes the sheet cells from out/avail_fixes.json. It fetches injuries_<season>.csv (older than
  3 h) and roster_<season>.csv (older than 20 h) itself: it runs before the steps that download them, and the first rebuild of a
  UTC day starts with no csv at all.
- **Checks.** `python3 availfix.py selftest` (38). On the real Week 10 rows: 5 corrected, 0 held, St. Brown and Burden untouched;
  same result from a cold start with both nflverse files missing.
- **Not covered.** Rows the injury refresh wrote ("did not practice, no game designation yet") are the refresh's to update. A desk
  OUT is never softened here. The sheet's own tab keeps the old row until a session writes the fix.

## 11/17, 7:45 AM CT: a ruled-out player cannot be bet from any page (tests/inactive_block.py) - with a correction

- **Correction of the 3:15 AM section.** It said the builder, Today and the boards could still offer a leg on an inactive player.
  Not so: since 11/1 every page reads the live injury list (/risk.js <- Supabase risk_feed; the slip-alerts function writes a
  game-day inactive there as OUT, detail "Inactive", for games within three hours). Checked this morning in a browser with that
  list answered by the test: Boards and player pages refuse every add button of his and put a "Ruled out" chip by his name; the
  builder refuses the tap ("... not added") and leaves him out of quick builds; his single-pick cards leave Today and Model's
  Best with a note ("Hidden since the build: ..."); a listed parlay that holds him gets a red banner.
- **What really was open** (found by ruling out, page by page, a player that page offers):
  - First TD: his row kept a live "Add to slip" FanDuel link and he stayed in "Most likely to score first" / "Best edges".
  - Under of the day (Today and the Short view): his under stayed on offer with its FanDuel button. The book voids it.
  - Model's Best teaser on Today: his row stayed, with "+ Builder".
  - Boost finder: he could be one of the three legs, FanDuel link and all (the page never asked the list).
  - Line shop: his rows stayed, with the other book's button.
  - The ready-made parlays on Today and Model's Best (`div.parlay`: Best same-game parlay, the Floor slip): no banner, and
    "Add all to FanDuel" still carried his leg. They get the Boards parlay's red banner now; the three book buttons and
    "Add all to slip" are hidden while it shows and "Open the board" stays.
- **How it works now.** A row can name its player: `data-rk="Player|Market"` on the row and, where the name is not the row's
  `.n`, `data-rkn` on the name element. risk.js then marks the row `bsr-out`, puts the chip after the name and refuses every
  sportsbook link inside it (`a.fdgo`, `a.bsbtn`, FanDuel / DraftKings / Hard Rock addresses - the click handler now stops
  `a.bsrblock` as well as `button.bsrblock`). Page scripts that keep a list listen for the `bs-risk` event the list fires when
  it arrives or changes: First TD re-fills its two lists, Line shop hides the row, the Boost finder searches again without him,
  the Under of the day shows the next day's card (or goes), the teaser moves the next row up.
- **Left as it was.** A leg handed to the builder by link (`?add=`) lands in the slip and is flagged - "High risk" tag, the
  "N legs in your betslip are at risk" pill with "Remove ruled-out legs" - rather than refused (the list is not loaded yet when
  the link is read). A posted promo holding him is the promo watch's job (a push to the owner).
- **The list is only as fresh as the ESPN mirror.** In game windows that is three minutes. Outside them see the timers section
  (11/17): until the owner runs the timers SQL again the mirror can be hours old on a weekday afternoon.
- **Tests.** tests/inactive_block.py, 16 checks, any week (clock a day before the first kickoff, finals stripped): Boards control
  and blocked, a tap adds nothing, builder, player page, First TD rows / lists / tap, Today pick card / teaser / Under of the day,
  Short view, the ready-made parlay, Model's Best, Boost finder, Line shop. It is in the pre-publish set.
- **Found by building Week 11 before the roll went out** (reprice.py --allow-week-change --publish none on the first Week 11
  mirror, 7:20 AM): the build and the page gate were clean (536 pages, 0 problems). Two tests assumed a mid-week build:
  social_elsewhere expected house slips to exist (a Tuesday build has none - fixed in the test), builder_fold expected the chip
  row to lead with games still to come, which was only true for a page built after the earlier games. That one was the page's
  fault: the builder's chip ORDER now follows the clock like its dimming (`chipState`), as Boards already did.

## 11/17, 8:10 AM CT: the news desk read other men's injuries as the player's own (and in-game exits as next week's status)

Found by reading the first screen of the News page on the Week 11 build: the second card under "Out or doubtful" was Carson Beck,
Arizona's STARTING quarterback. All 20 notes in that list were then read one by one; 7 were wrong.

- **Someone else's injury** (`strip_others`, `strip_subject_injury`, the "who ..." rule in `my_clauses`):
  - "Gardner Minshew's season-ending injury opens the door for Beck" made Carson Beck "News: out" (red flag on his legs, a proposed
    OUT row) through Week 10 and into Week 11. "<Other man>'s <injury words>" is the other man's.
  - "Lions star Aidan Hutchinson feared to have suffered season-ending knee injury celebrating sack of Drake Maye" was the source
    shown for Drake Maye's OUT. (Maye IS out - "out indefinitely with potential ankle fracture", Monday - and the note and the
    proposed row now cite that item.) Who suffered it is the last man named before the verb; only verbs whose subject is the injured
    man are read this way (suffered, sustained, underwent, tore, needs surgery), never "ruled out / placed / released".
  - "X replaces Y, who is out for the season": a "who ..." clause belongs to the last man named before it.
- **A status published while the team was on the field is an exit from that game** (`in_game_window`: kickoff to 4.5 hours later),
  whatever its wording, unless it is lasting (injured reserve, surgery, multi-week). "Geno Smith ruled out with ankle injury. Geno
  Smith's day is over", "A.J. Brown ruled out of Lions game", "Brock Bowers was ruled out of Sunday's matchup ... in the opening
  quarter" all stood as "News: out" for Week 11 because no in-game phrase the desk knew was in the clause about the player - and,
  being the most severe note, they hid Monday's real reports (Bowers "day-to-day ... not as bad as we thought", Smith "tests did
  not reveal any major injuries"). Those two now read "limited / questionable" from the Monday report; Brown reads "left last game".
- **Hopeful about this week in other words** (HOPE): ESPN "Out" + "eyeing a return to action Sunday" (Monangai), + "expect him to
  make progress ahead of Sunday's game" (Hockenson) are questionable, as the 11/10 rule intended. A hopeful line about the week
  after a bye stays OUT ("coming out of the Week 11 bye").
- On the Week 11 feed: "Out or doubtful" 20 -> 14; proposed availability rows 23 -> 18 (dropped: OUT for Beck, Brown, Bowers,
  Smith, Monangai, Hockenson; added: Smith QUESTIONABLE). Nothing else changed.
- `python3 news_desk.py --selftest` 54/54 (was 28).
- A session still reads every quoted headline before it writes a row (Step 2a-ii). The flags and the News page have no reader in
  between - that is where these showed.
- Not touched: role proposals read from passing mentions ("former Raiders starting quarterback Kirk Cousins", "could be without
  starting quarterback Baker Mayfield" both propose QB1 - true, for the wrong reason).

## 11/17, 8:15 AM CT: Model's Best - the first pick is on the first screen (page pass, step 9)

- On a phone the title was followed by five lines of introduction and five lines of small print about the plus-money rule; the
  first pick card started at the bottom of the screen (about 740 px of 844). The introduction is one sentence now ("Week N. Where
  the model and FanDuel's price disagree most.") and a rule line (`main.wk .subt`) longer than 110 characters folds to two lines
  with the same "More" button the long page introductions use (`foldIntro` in build_site.py; phones only, nothing removed).
  The first card now starts at about 530 px with its three book buttons in view.
- Player pages and the News page were looked at in the same pass: both already lead with content (last ten games against the
  line; the folded introduction and the team chips). The News page's content was the problem - see the news desk section above.
- Seen on the way, NOT changed (the owner's call, goes with Tuesday's biggest-gaps list): the second "plus-money edge" on
  Week 11 is DJ Giddens anytime TD +3300, model 11% against 3% priced. A model chance nearly four times the book's on a long
  shot is far more likely an input problem than an edge.

## 11/17, 8:25 AM CT: after the roll every scheduled rebuild would have stopped - reprice read the wrong data file (fixed)

- Since 11/15 a publish keeps the previous build's `data-<hash>.js` in /build/ (a page cached for a few minutes still names it).
  `reprice.live_data` took the last data file BY NAME. After this morning's roll the folder held data-02f3... (Week 11, linked by
  the page) and data-4ed8... (Week 10, kept): the old one sorts last, so reprice saw "the site serves Week 10", the mirror said
  11, and it would have ended every run with exit 3 ("rolling the week is a session's job") - a quiet skip, no failure mail -
  until a session published again. Inside a week the same mistake only miscounted "prices moved" against one build back.
- Now it reads the file build/index.html links (newest by time if the page cannot be read). tests/reprice_live.py, 5 checks, is
  in the pre-publish set. Found while checking the 8:16 AM publish, before the first scheduled run of the new week (9:20 AM).
- tests/inactive_block.py read the builder data the same wrong way; it reads the linked file too.

## 11/17, 8:55 AM CT: a late ESPN mirror stopped every publish through the weather step (fixed; the mirror still needs the owner's timer)

- `weather_feed.py` refused a feed more than 6 hours old and returned failure; reprice.py treats that step as a flag step, so
  the run ended with exit 6 ("a flag step failed (weather feed); not copied") and NOTHING was published - prices included. The
  feed comes from the ESPN mirror, which outside game windows runs only when GitHub's own schedule fires (see the timers
  section): today the last mirror was 2:35 AM CT, so every rebuild from 8:36 AM on would have failed. A hand-dispatched
  "changed" run at 8:48 AM did (run 44107059103). The nearest kickoff was 58 hours away.
- Now (`staleness`): up to 6 hours old = used as before; 6 to 24 hours = still used, and the line says "LATE, used anyway";
  more than 24 hours, or the wrong week = the step fails as before. tests/weather_gate.py 10.
- This is the second thing in one morning that rides on that mirror (the first: injury statuses). **Until the owner runs
  sql/github_timers.sql again, a session that finds the mirror old should start it by hand:**
  `gh api repos/joeymccarrick1/betsweep-site/actions/workflows/feeds.yml/dispatches -X POST -f ref=main`.
- Probably not the first time: on Sunday 11/15 the mirror gaps were 6.6 and 6.5 hours (7:18 PM Sat - 1:56 AM, 1:56 - 8:29 AM
  CT), so a rebuild between 7:56 and 8:29 AM that morning would have failed the same way. Not checked run by run.

## 11/17, 9:40 AM CT: owner's two answers - a touchdown pick needs a role; the game-card parlay steps its bar down

- **Owner on DJ Giddens +3300 in Model's Best:** "no shot dj giddens scores. I want players that are actually getting snaps, red
  zone looks, or potential for a long touchdown." `td_role` in build_builder.py: an anytime-TD leg makes a Model's Best tier
  (plus-money or TD) only with real snaps (40%+ projected; not counted for a quarterback, who is on the field every snap),
  red-zone work (15%+ of his team's red-zone chances on 20%+ of snaps), or a long-score record (a 30+ yard catch in two or
  more games this season on 25%+ of snaps). Each TD leg carries `tdr` (which one) and `rzs` (red-zone share). The build prints
  who it kept out. Week 11 Tuesday: Giddens, Tinsley, Ty Johnson, Van Jefferson, Abdullah, Singletary, Theo Johnson, Wright,
  Kaytron Allen, Ray Davis and Kyle McCord (a quarterback at +1200) left; Brian Thomas Jr. +650 stayed. Background: plus-tier
  TD legs longer than +600 went 2 for 41 in Weeks 9-10.
- **Owner on the game-card parlay** (12 of 13 cards were two game lines at about -6%): "I want there to be a best parlay but do
  your best." `best_parlay` now retries when no slip with a player leg comes out: the edge bar steps 8 -> 4 -> 0 -> minus 3
  points (`BP_EDGE_STEPS`); every other gate stays (nothing at -200 or shorter, the risk check, zones, role and trend gates).
  On a stepped-down bar a leg with no script table (passing TDs, rush + rec ...) rides with the same chance in every ending.
  The card says "best available" (title text names the bar) and the record carries `bar`.
  Week 11 Tuesday: 3 cards have a player leg (BUF-MIA, CIN-WAS, JAX-NYG, all priced at or better than fair); 10 are still
  game lines - five of those have no props posted yet, and in Thursday's game 7 of 92 usable legs have the model at or above
  FanDuel's price and 6 of the 7 fail the risk check. `BP_DEBUG=1 python3 build_boards.py` prints the rows per game and bar.

## 11/17, 11 AM CT: Tuesday grades with Week 10 in - one flag gets a weight, a traded starter is no longer a fill-in, promo grader reads passing TDs

- **Flag grade, Weeks 8-10** (`research/flag_grades_w8_w10.txt` / `.json`; boards = the last build before Sunday's first kickoff, pulled
  from a blobless clone of the site repo because the working clone is shallow): 4,688 over legs, 636 player-weeks, all overs 2.6 points
  under their prices. By the standing rule (same direction every week, 100+ player-weeks):
  - **Matchup shifting** (info): 7.7 under, under in all three weeks, 198 player-weeks, t -2.9 -> `sweep.TAG_W["Matchup shifting"] = 1`
    (one watch point; still shown).
  - **Soft matchup** held (6.3 under, under each week). Stays at 0.
  - Not changed: Cold L3 (bad) is OVER its prices all three weeks (+6.0) but on 76 player-weeks - FanDuel seems to price the slump already;
    revisit at 100. Hot L3 (good) is no better than the average leg (0 / 0 / -9). The risk score still does not sort legs: score 0 -3.2,
    score 1 +1.1, 2-3 -6.6, 4+ -1.3; among floor legs "some risk" is the bad group (-10.7, 231 legs).
- **honest.py / learned.py with Week 10** (8,094 graded legs, Weeks 6-10): forecast error model 0.2419, FanDuel no-vig 0.2352, honest
  chance 0.2345, learned 0.2342. Legs the model had at 70%+: model said 75.7%, they hit 62.7% (honest chance said 62.9%). The shadow list
  had no real Week 10 test (first written Sunday night, three singles); Week 11 is its first full week.
- **Sheet fix - a traded starter is not a fill-in.** 'AUTO - QB Projections'!AK ("Fill-in Starter") said YES for any QB1 who had started
  under half of his CURRENT team's games, and the fill-in path projects from that team's attempts per game. Jacoby Brissett (8 starts for
  ARI at 258 yards a game, traded, 340 for BAL in Week 10) was projected 176.8 - the flag check's biggest gap two weeks running. AK2 is
  now one spilled MAP formula (AK3:AK109 cleared - nothing may be typed there): fill-in only if he ALSO has fewer 20+ attempt games this
  season on any team than half his team's games. Brissett 176.8 -> 241.4, Kirk Cousins (MIN) 196.5 -> 218.3; Beck, Lock, Mendoza,
  McCarthy, Milton, McCord and DeVito stay fill-ins. Old per-row formula:
  `=IF(A2="","",IF(AND(AE2="QB1",N(AJ2)>0,N(AI2)<'AUTO - Settings'!$B$161*N(AJ2)),"YES","NO"))`.
- **grade_promos.py** reads Passing TDs, Completions and Rushing Attempts / Carries (both Monday slips had "Passing TDs 1+ - not gradable
  here"). Re-graded Week 10 in a scratch copy: same nine results.
- **Flag check gaps worth a look each Tuesday** (data/flag-audit.json): every one of this week's 20 biggest gaps is the model UNDER
  FanDuel, most on receptions floors (Jefferson 6+ 37% vs 76%, Kittle 5+ 37% vs 69%) - the model treats a 5.0 catch average as a coin flip
  at 6+ and FanDuel does not; the honest-chance layer already discounts the model there.

## 11/17, noon CT: FanDuel's same-game discount, measured and used (owner: "get to the FanDuel same game discount")

- **What was wrong.** Every same-game price the site printed was the legs multiplied. FanDuel prices same-game legs together and keeps
  more on long slips, so the builder's "FanDuel price", its EV, the game-card best parlay and Today's same-game card all overstated the
  payout. Worst case on the Week 11 Tuesday board: JAX-NYG McCarthy 218+ pass yds + Over 46.5 showed +258 and EV +20%; FanDuel's
  price is about +188 and the slip is 3.5 cents under fair.
- **The measurement** (`research/sgp_discount.py`, `.json`, `.md`): 30 same-game slips with FanDuel's own price, Weeks 7-10 - the 16
  we posted (promo tab column E; the two Week 6 slips are the legs multiplied and are left out) and the 14 prices the owner read off
  his betslip on 11/14 for the every-game test sweeps (`research/sgp_quotes_owner.json`: 'ASSIST - Slip Log' rows 14-23 and the
  variants in their notes, with that morning's leg prices from the 10:22 AM site build). FanDuel's payout against the legs multiplied:
  4 legs 58-118% (median 87%, 18 slips), 5-6 legs 59-82% (68%, 4), 7+ legs 6-61% (28%, 6); two 3-leg quotes (80%, 103%), no 2-leg quote.
- **The estimate** (`sgp.py`): price for n legs in one game = exp(-c (n-1)^p) / joint, where joint = FanDuel's implied leg chances joined
  with the builder's own same-game correlations (n = 1 gives the leg's own price). The script fits c for p = 2, 2.5 and 3 and keeps the
  p that misses least when each slip is priced by a fit that never saw it: p = 3, c = 0.00146 (multiplier 99% at 3 legs, 96% at 4,
  91% at 5, 73% at 7, 47% at 9). Median miss: 6% of the price (3% on the twenty 2-4 leg slips, 15% on the ten longer ones), against
  10% for the old constant (0.85 / joint + 0.15) and 19% for the legs multiplied. Long slips still miss by a lot both ways; it is
  always shown with "≈".
- **Where it shows.** Builder: the slip panel's FanDuel price ("≈ +196 · same-game estimate · legs multiply to +252"), EV, edge, payout,
  suggested stake, the slip bar, Sweep this slip, swap / drop previews, "Build me a +N", saved slips (the saved price is the estimate)
  and the share text; a line under the price says why, with the measured numbers (`D.sgp.note`). The target slider keeps working on the
  legs multiplied and says so. Boards: the game-card best parlay is priced and ranked with the estimate (`rec["dec"]`; the legs
  multiplied stay in `rec["dec_mult"]`), so the calls archive, Today's same-game card, the simple view and the Boost checker all carry
  it. Guide: a section with the table. One leg per game is unchanged everywhere.
- **Not covered.** Passing TDs have no correlation code, so a quarterback's passing TDs next to his yards or the over is priced as if
  unrelated (Herbo Fully Loaded: +259 quoted, +326 estimated). Either-or TD legs take the first player's code. Promo cards still need
  FanDuel's own price typed in column E.
- **To sharpen it:** two- and three-leg quotes. Any same-game promo adds one; a handful of price checks from the owner (open the link,
  read the price) would settle the short end.
- Tests: `tests/sgp_price.py` (29: one leg per game is the legs multiplied; two legs in one game carry the mark, match the Python
  fit and sit under the legs multiplied for a quarterback with his receiver; light and dark). Added to the pre-publish set.
- Also fixed on the way: the builder's "Same slip at each book" row ran off the right edge of a phone (a column flex that wrapped).

## 11/17, 12:30 PM CT: Week 11 WR-CB chart loaded; the chart's alignment flag was upside down for Weeks 8-10; Sweep says rewritten

- **Loaded** (owner upload NFL26_CS_WRCB_Week_11.pdf, 2 pages): 'AUTO - WR CB Matchups' rows 425-502, 78 receivers, 26 offenses
  (ATL, CLV, GB, LAR, NE, SEA on bye), no shadows. Read back through the mirror: 0 mismatched cells. Clay coverage edges: Pickens,
  Lamb, St. Brown, Dell, Tyson, Nabers, DeVonta Smith, Evans. Tough coverage: Duvernay, Fehoko, Ja'Kobi Lane, Legette, Iosivas,
  Quentin Johnston, Jennings, Felton, Malachi Fields, Mooney, Brandon X. Smith.
- **The loader is a script now**: `python3 -I wrcb_load.py <pdf> <week> <first empty row>` writes out/wrcb_load.json (the four value
  blocks and the first-row array formulas, each with its range); after the mirror refresh `python3 -I wrcb_load.py <pdf> <week>
  --check in/wrcb.json` must print 0 mismatched cells. It reproduces the Week 10 block exactly.
- The mirror used to stop at row 600 of 'AUTO - WR CB Matchups' (Week 13 would not have fit). FIXED 11/17 1:16 PM: owner "Push the
  chart loading line" - .github/sheets_pull.py on main (1e494eda) and call C above now read A1:AT2500; the mirror ran on it and
  returned all 501 chart rows. (A session still does not push other files under .github on main unasked.)
- **Sign bug, fixed.** Clay's page-2 ranks: 1 = the defense that allows the MOST (the easy matchup) - checked against the cell colours
  (TEN's 1s are green, KC's 32s red) and against WR points actually allowed (correlation 0.99 with our own "allows most" order). The
  Alignment Def Score must be (16.5 - rank) / 15.5. The Week 5, 8, 9 and 10 blocks had (rank - 16.5) / 15.5, so for Weeks 8-10 the
  sheet's CB Matchup Flag was reversed: FAVORABLE meant the tough draw. What that touched: the builder's "Coverage ... Defense ranks
  tough for his alignment" watch sat on receivers with the EASY draw, and Under of the day skipped unders on the wrong receivers.
  Clay's own deltas (the ▲ ▼ arrows, Coverage edge, Tough coverage) were never affected. All four blocks are now one array formula
  each with the right sign (AK2, AK167, AK251, AK341); Week 7 was already right.
- **Regraded with one sign, Weeks 7-10** (`research/wrcb_regrade.py`, `.txt`; 297 receiver-weeks): FAVORABLE went over the receiving
  line 43.5% (46), NEUTRAL 53.2% (190), DIFFICULT 48.7% (39); thirds by alignment rank 51.6 / 48.4 / 52.7%. So the alignment read does
  not beat FanDuel's lines (easy draws do gain about 8 yards on tough ones against season averages - the line already has it). The
  11/11 note that the sheet's flag "graded with signal" (FAVORABLE 56%, DIFFICULT 39%) was the mixed signs. Nothing was demoted:
  the owner keeps the coverage sentences and arrows (11/11); the easy side now gets "Defense ranks soft for his alignment" as
  information. Under of the day keeps its coverage skip (owner: "I'd skip it if coverage disagrees").
- **Sweep says with the chart** (`voice/voice-w11.json`): a session that rewrites lines between rebuilds commits them to the bundle;
  `reprice.ensure_voice` uses that file only while its "built" stamp is newer than both out/voice.json and the published
  /b/voice.json (tests/reprice_live.py, 10 checks). Rewritten: HOU-IND (Dell has the softest matchup), BUF-MIA (Miami stingy in the
  slot; pick Cook anytime TD -185), CIN-WAS (Diggs lives in the slot, Cincinnati allows the 3rd-most to it; pick Diggs 5+ catches
  +110), DAL-TEN (Lamb and Pickens), DET-TB (St. Brown), JAX-NYG (Nabers soft, Fields and Mooney tough), MIN-SF (Minnesota stingy
  by rank, Evans the softest matchup). Two picks ride; the others describe.
- **The share card's risk gate matches the builder's** (`build_boards._risk`): graded tag weights and the hard-risk tags count. Until
  now it added kinds only, so a Losing side or Blowout script leg with three good flags counted as low risk: the morning's picks for
  CIN-WAS (Diggs 43+ yards), JAX-NYG (McCarthy 218+) and MIN-SF (McCaffrey 40+ receiving) all carried one. Board picks must be board
  markets (no Rush + Rec Yards, no Passing TDs).


## 11/17, 1 PM CT: every-page pass (owner: "look over every single page ... optimize it, make it look better") + departed targets
What changed on every page (phones, build_site.py): the title block now scrolls away and only the chip row sticks under the site bar
(`.top{display:contents}`, `.top .nav{position:sticky}`); the old hide-on-the-way-down / show-on-the-way-up title changed the page's
height each time and moved the content ~50px on browsers without scroll anchoring. A chip row with ONE link (a back link: /trade/,
/season/) is not pinned (`.top .nav:not(:has(a + a))`). `landOnHash` adds the pinned row's height.
Page by page (all measured at 390x844, light and dark, /tmp-style audit of 43 page types: no sideways scroll, no script errors):
- /dfs/: the salary instructions fold behind one row ("Load a salary list", opens itself on a message or a dragged file) so the
  player pool is on the first screen. EVERY chip on the page sat 26px low: the page template has its own `.tag` (a section heading)
  and `.dfs .tag` only overrode part of it. Reset there. Same family: /trade/ statuses used the template's `.st` (one-line chip), so
  "IR through Week 10" forced the player column to 218px and pushed the A / B add buttons off a phone for the whole table. They wrap now.
  CLASS NAMES ON TEMPLATE-BUILT PAGES (dfs, trade, season, team) COLLIDE WITH template.html (.tag, .st, .bl ...): reset what you reuse.
- /usage/ and /benefits/: the tables were 725px in a 344px box (three of seven columns showed; the FanDuel leg was two swipes right).
  On phones each player is a block: name, five labelled numbers (td[data-l]), the leg under them (td.lg). No thead on phones.
- /survivor/: pick first, then "Win chances from" (kept visible - owner 11/10), the teams grid (6 across on phones), "Pool settings"
  (plan through / rename / clear / remove) folded, tables last. render() writes the call into #svpick. "drops the whole run from 15%
  to 15%" now shows the decimal or says "about the same". tests/survivor_plan.py passes unchanged.
- /teasers/: REBUILT ON REAL HISTORY. The model's margin IS FanDuel's line, so the smooth curve said 68% for every 6-point leg and
  47% / -9.9 for every pair. build_teasers.history() now grades every teased leg, regular season since 2015, at the closing line in
  in/games.csv, by kind of move (through 3 and 7 / through one / past zero / neither / totals); a leg's chance = its kind's rate,
  shifted by the model's distance from the line. Since 2015 at 6 points: through 3 and 7 74.1% (1,157-405), one key number 70.8%,
  totals 68.2%, past zero 67.9%, neither 66.2%. At -130 a leg needs 75.2%: the page says so in one sentence ("Nothing clears this
  price; ... need about -120 or better") and the sentence follows the price box. A bare number in the box is a minus price (phone
  number pads have no minus key).
- /build/: the slip has a box for FanDuel's own same-game price (#sgq, sign button, Use it / Back to the estimate). SGQ is keyed by the
  exact legs + prices and kept for the visit; slipPrice() returns {quoted, est}. tests/sgp_price.py: 43 checks. Bankroll field styled.
- /beat/: the suggested-legs scroller fades at the bottom instead of slicing a row. /targets/: "wr37" -> "WR37" (str.capitalize()).
- /badbeats/: a promo with no price showed a lone "+". /season/: receipt links were the browser's default blue. /receipts/weekN/:
  six-column tables fit a phone. News desk notes end on a sentence or a word (was a flat [:220]). First TD: no-role players are out of
  the edges strip (projsnaps role check). Game previews: news line cleaned, "FanDuel line: HOU -11.5, total 44.5", weather sentence.
  /me/: empty slips state has two buttons. Today link chips and player-page book buttons are full touch size.
- NOT a bug: the local gate says "MISSING FILE /receipts/week10/ ['404 /s/tpl-<old>.css']" after any template.html change, because the
  kept receipt links the stylesheet it was published with and gp/site only has the new one. The clone keeps it (reprice prunes s/ only
  when no page links a file), so the published site is whole. Check the published copy with SITE=/home/claude/betsweep-site.
- STILL STALE: /how/ quotes "three graded weeks" (Weeks 6-8). Five are graded now; the numbers need a recount before the text changes.

DEPARTED TARGETS (sheet, 11/17 1 PM). Tuesday flag check, 20 biggest model-vs-FanDuel gaps: seven were Colts pass catchers. The Colts
traded Keenan Allen (SF) and Josh Downs (KC) before Week 10 - 115 targets in nine games - and the absence bump only counted teammates
who are OUT this week ON THE SAME TEAM, so nobody inherited a target. FanDuel had Treadwell 3+ catches at -130; the sheet had him at 1.25.
- New tab 'AUTO - Departed Targets' (one formula in A1): every (player, old team) in the game log whose team on the projection tabs is
  now different, with 2+ games and 3.3+ targets a game for the old team (Settings B201, the same "key absentee" bar). Column G =
  his targets for the old team / that team's games so far = the same quantity "Vacated Targets If OUT" produces.
- 'AUTO - WR Projections'!AU2:AU300, 'AUTO - TE Projections'!AQ2:AQ250, 'AUTO - RB Projections'!BB2:BB300 (Absence Target Bump):
  z_vw / z_vt / z_vr each add SUMIFS('AUTO - Departed Targets'!$G$2:$G$100, ...$A = team, ...$B = "WR" / "TE" / "RB"). Written with one
  repeatCell per tab (the row references step by themselves). Nothing else in the formulas moved; the shares are still Settings
  B197:B200. To undo: delete the three "+SUMIFS('AUTO - Departed Targets'...)" terms (repeatCell again) - the tab can stay.
- Checked through the mirror, every row of the three tabs before and after: only Colts changed. Treadwell 14.5 -> 27.8 rec yds and
  1.25 -> 2.39 catches (FanDuel 30.5 / 3+ at -130), Dulin 13.2 -> 32.1, Burks 8.2 -> 18.7 (16.5), Warren 39.2 -> 41.8 (41.5),
  Taylor 2.71 -> 3.05 catches. "Reception Audit Flag: ERROR: RECEPTIONS > TARGETS" on Burks / McGowan is the audit comparing bumped
  catches with un-bumped targets - nine other rows already carried it, nothing on the site reads it.
- The receiving side needs nothing (checked 11/17 1:30 PM): Allen's row (SF) and Downs's (KC) carry their season volume, and their
  first games for the new teams matched it - Allen 7 targets / 5 catches / 61 yards at SF (7.2 a game before), Downs 5 / 4 / 53 at KC
  (6.1). Their new teammates' rows did not move either (Kittle 6.7 targets, Evans 6.8, Rice 7.2).
- TUESDAY FLAG CHECK, the 20 biggest gaps after the fix (data/flag-audit.json built 12:59 PM) - how to read each when writing Sweep says:
  input lag, not an edge: Emari Demercado TD -120 (HOU's RB2 by ESPN's chart, 7 carries last week; the model has 0.2 TD),
  Justin Jefferson 6+ catches -310 (13 targets / 9 catches last week; the model is on his 5.0 season average), Kirk Cousins 5+ rush
  yards (a 1.1-yard projection is read as "never" - low-mean rushing lines are not a market this model prices), Ashton Dulin (the
  bump now OVERshoots FanDuel: 28 yards vs a 16.5 line, two long catches in a six-game log).
  the model's lean, and the owner's own rule agrees - avoid the overs, do not bet the unders: Miami with Kyle McCord (McCord 150+
  pass yards, Douglas and Washington 4+ catches, Gordon 50+ rush yards), Brock Purdy 225+ and George Kittle 5+ catches at MIN (#31
  against the pass - the sheet still has Kittle at 6.7 targets; it is the matchup, not the Keenan Allen trade), Joe Burrow 301+.
  a warning on a player we feature: Dalton Kincaid. FanDuel's receiving line is 25.5; he averages 54. His snaps fell to 46% the last
  two games (Dawson Knox 72%) with 3 targets in each. The model still projects 47 yards and he leads the plus-money list (3+ catches
  +162). Owner 11/15: check whether a pass catcher's trend is going down before using him. Josh Palmer to IR this week helps him;
  the snaps do not. OWNER 11/17 1:15 PM: "Kincaids still good. They were just utilizing different TE sets last week." - so Kincaid
  legs are fine in posted slips; a one-week snap dip from a personnel-package choice is not a falling trend.

## 11/17, 1:30 PM CT: owner's three answers - Kincaid stays, the chart line is pushed, /how/ is recounted and now counts itself
- Kincaid: "Kincaids still good. They were just utilizing different TE sets last week." Kincaid legs are fine in posted slips.
- 'AUTO - WR CB Matchups' mirror range: A1:AT2500 on main (see the 12:30 PM section).
- /how/ ("How BetSweep picks"): how_stats.py counts every number on the page from in/legsnaps.json on each build (how_body.html
  carries {{KEYS}}; build_site.py fills them; with no snapshots the 11/17 count stands in). Same definitions as the 11/4 audit - on
  Weeks 6-8 alone it returns that audit exactly (tests/how_stats.py, 16 checks, in the pre-publish set). Weeks 6-10, 8,094 legs:
  every leg -9% (49.0% hit vs 53.9% priced); favorites -130 to -400 hit 60% vs 67% (-10%, 3,434 legs); rushing overs -17%, negative in
  all four price bands (1,199); +150 or longer with the raw model 5+ points over: 39% vs 31%, +23% (240 legs, ahead in all five weeks;
  by week +30, +16, +55, +9, +9). Two sentences had stopped being true and are now written by the count: touchdown scorers at +151
  or longer are -3% as a group (497 legs; +8% after three weeks) and the plus-money passing sample is three legs. The weights
  sentence reads calib.W_MARKET (about half on touchdowns and receptions since 11/10 - the page still said two thirds on touchdowns).
- The same count feeds the plus tier's line on Model's Best (home.py) and the builder's tier chip (build_builder.py __PLUS_TXT__):
  how_stats.plus_phrase() = the tier's own four markets: "Weeks 6-10: 40% hit against a 30% price, +30% at a unit each (175 legs)".
- Pre-publish list: add `python3 tests/how_stats.py` (no browser, one second).
- 1:50 PM, the other tier lines were stale too (they quoted Weeks 6-7) and are counted now (how_stats.tier_phrases / _tiers, the
  builder's own tier rules; overs only, and without the touchdown role rule, which cannot be rebuilt for past weeks): the builder's
  even / touchdown / safe chips, Model's Best's touchdown and even-money subtitles (the touchdown one still said "longer-priced
  scorers have paid"), and one line on /how/ ("so far those overs have hit 59% against a 53% price (152 legs)").
  Weeks 6-10: even tier overs 59% vs 53% (+11%, 152 legs; by week -9, +20, +17, +23, +16); touchdown tier 38% vs 39% (47 legs; 4 of
  20 in Weeks 9-10); safe tier 64% vs 68% (333 legs).
- A LEAD, NOT A RULE YET: inside the even tier the result is nearly all receiving yards where the raw model is 12+ points over a
  near-even price (-135 to +115): 45 of 65 (69%) against a 53% price, ahead in all five weeks (8-12 points over: 20 of 39, no edge).
  Several lines of one player in one week count separately in that 65, so the real sample is smaller. This week it names two
  players: Dalton Kincaid (25+ / 26+ / 30+ receiving yards) and Ashton Dulin (whose number is the trade bump overshooting). Every
  leg is frozen weekly, so the count keeps itself; look again when it has 100+ legs before building a slip rule on it.
- NOT RECOUNTED (each has its own definition; a Tuesday job): the fixed-span numbers inside flag texts and slip warnings ("Weeks 6-9
  (439 legs)", "graded Weeks 6-8, favorites returned about -9% each"). They name their span, so they are dated, not wrong.
- 2:07 PM, THE BUMP OVERSHOT ON ONE PLAYER AND PUT HIM ON MODEL'S BEST: Ashton Dulin (5 catches in 6 games, two of them 55 and 30
  yards) carried "Adj Yds / Rec" 21.4, so 2.07 inherited targets were worth +20 yards: 32 projected against FanDuel's 16.5-20.5, an
  "even" tier leg on Model's Best. Inherited targets are ordinary targets, not his long ball. 'AUTO - WR Projections'!L2:L300 (Proj
  Rec Yds), the bump term only: when a receiver has fewer than 15 catches (G x D), the bump values a catch at the smaller of his own
  yards per catch and the tab's average (SUMPRODUCT(I, D) / SUMPRODUCT(G, D) = 13.0 today). 15+ catches: unchanged. Was
  ROUND(N($AU)*N($AK)*N($AL),1); now ROUND(N($AU)*N($AK)*IF(N($G)*N($D)<15,MIN(N($AL),<tab average>),N($AL)),1). One repeatCell.
  Through the mirror, all 230 receiver rows before and after: six moved - Dulin 32.1 -> 24.1, five others by under a yard (Virgil,
  T. Burks, Z. Jones, C. Allen, Bryant). On the site Dulin is now within four points of FanDuel at every line and in no tier.

## 11/17, 2:45 PM CT: owner "Fix the 2 open things" - new-market correlations, and the flag numbers count themselves
(1) PASSING TDs HAD NO CORRELATION CODE. The four markets added 11/5 (Passing TDs, Completions, Interceptions, Rush Attempts) were
built with "c": "" - a quarterback's 2+ TDs and his 225+ yards priced as strangers (model chance for the pair too low, same-game
estimate too high). research/newmkt_corr.py measures 37 pairs on nflverse 2024-25 (latent correlation = 2 sin(pi/6 x Spearman);
tetrachoric where one side is a touchdown) and writes research/newmkt_corr.json; build_builder.py gives the legs codes QB_PTD /
QB_CMP / QB_INT / <pos>_ATT and merges the rows into CORR (a row in the sheet's own tab always wins) and the stat-vs-margin / total
rows into GLCORR. Checked two ways: the method returns the sheet's own passing-yard rows (0.37/0.41 vs its 0.43/0.40; 0.13/0.14 vs
0.13/0.18), and the new numbers reproduce real joint hit rates at typical lines - QB 2+ TDs with 225+ yards: real 30.9%,
independent 22.1%, rho 0.50 gives 30.4%; QB 2+ TDs with a receiver's TD: real 22.2%, rho 0.55 gives 22.1%; back 15+ carries with
60+ yards: 33.3% vs 32.9%. Same player: no shrink. Teammates / opponents: x 0.9 (the sheet's older rows use x 0.75; here the
unshrunk number already matches the joint rates). NOTE the sheet's two touchdown rows (QB_PASS-WR_TD 0.14, QB_RUSH-QB_TD 0.25) are
about half what this method gives (0.32, 0.48) - they look like plain correlations of a yes/no, which understate; not changed today.
On the page: Jayden Daniels 2+ pass TDs with 226+ yards = about +169 (legs multiply to +247). tests/sgp_price.py: 49 checks.
Re-run `python3 research/newmkt_corr.py --write` when a season is added to in/.
(2) FLAG NUMBERS. flag_stats.py recounts on every build what the flags quote: the main-rushing-line under rate (now ALSO the flat
chance on a rushing under: RUSH_UNDER_RATE = the counted rate, guarded 0.50-0.62; 389 lines, 56.8% -> still 0.57), near-zero floor
legs (247: 61% vs 70% priced, under in all 5 weeks), yardage floors by closing spread (underdogs of 5.5+: 299 legs, 60% vs 70%;
favorites: 68%) - the "Losing side" sentence now says "underdogs of 5.5 or more" because past endings are not archived -, favorites
(-10% a leg; -6% even with a model edge), the model 10+ over the book (said 66%, hit 51%), and walk-forward what the reliability
flags went on to do: team-markets 4+ under their prices -3.7 points vs -2.9 for the rest; "Reliable" players -2.3 vs -3.4 for the
rest; "Volatile" players -3.2, THE SAME AS THE REST - that flag does not separate anything yet (kept as a watch flag; its sentence
now says so; weigh that next Tuesday). tests/flag_stats.py (14): Weeks 6-9 returns the 11/11 grade (312 lines, 57.1%).
Still typed, on purpose: role_rising.py's two "Week 6-8 check" notes (they need weekly snap shares, which are not frozen) and
build_teams.py's "tested on Weeks 6-8" (it describes a test, not a running number). Today's plus-money line on Today reads the count.

## 11/17, 3 PM CT: buy, hold or sell on the fantasy pages (owner: "suggest whether to tank or buy ... who to trade for ... get rid of vets to get better draft position")
Where: the trade calculator's league view (/trade/#league, card #slOutlook above "Trade ideas for you"), reached from a new
"Buy or sell?" card on the Fantasy page (/team/). With a Sleeper username already on the device the link imports by itself.
Code: fantasy_outlook.py (CSS + JS, window.bsOutlook) included by build_trade.py; nothing is computed at build time.
- Odds: each team's weekly score ~ Normal(mean, 19% of the league's average score; floor 14). Mean = league average + half of (its own
  points per game - average) + half of (its best lineup by the model's adjusted points per game - the average lineup). The weeks left
  (games played + 1 .. playoff_week_start - 1) are read from league/<id>/matchups/<week> and played 3,000 times, wins then points,
  playoff_teams spots, plus the median game when league_average_match is on. Seeded by league id + games played: same standings,
  same odds. Kickers, defenses and IDP slots are ignored (both teams have them; the model does not value them).
- Verdict from the reader's odds: 70%+ Buy; 35-70% Hold ("buy small, sell nothing"); 12-35% long shot; under 12% out. Sell is only
  offered in dynasty (settings.type 2) and keeper (1) leagues; a redraft team that is out is told nothing carries over.
- Who to trade for (Buy / Hold): players on teams at 25% or less who add 1+ point a week to the reader's best lineup, top five by
  gain, each with an offer: one bench player within 20% of his value, else two that add up to it, else the rookie pick nearest his
  value (dynasty values only). Who to sell (dynasty / keeper, long shot or out): the reader's veterans (QB 31+, RB 26+, WR 28+, TE 29+,
  or 70%+ of their value in this season) worth 400+, each matched to the contender (50%+) whose lineup he lifts most, with a player 25
  or younger off that bench at 60-120% of his value to ask for, else the nearest pick. The draft slot the team is tracking for
  (teams expected to finish below it + 1) is stated with "in a reverse-standings rookie draft" - it is advice to SELL POINTS, never to
  bench starters. Load puts the deal on the calculator (data-ol="give;give|get").
- NOT read: which picks each team owns (league/<id>/traded_picks), FAAB, the trade deadline date. A pick suggestion is a price, not
  a claim that the other team has that pick.
- Test: tests/trade_outlook.py (35 checks) mocks Sleeper with a ten-team league drafted from the page's own players: contender in a
  dynasty league (Buy; targets only from teams that are out; odds add up to the spots; same odds twice), the same roster at 1-9
  (Sell; buyers are contenders; draft slot stated), 1-9 in redraft (nothing to sell), and the one-tap arrival. The sandbox cannot
  reach Sleeper, so the real API has NOT been exercised end to end by a session - the calls are the same ones the page already made
  (rosters, users) plus matchups/<week>.

## 11/17, 6:30-8 PM CT: owner "what else needs to be done?" - checks, the card parlay pick, Volatile off slips, fantasy pages for many leagues, market 70%

**State at 6:30 PM.** Nothing failed in the last 25 runs; every Week 10 row of 'ASSIST - Slip Log' (rows 9-60) has a result and every
losing row a why-tag. Week 10 by tag: thin role 14, bad luck 11, wrong script 20 (7 of 52 won). After the 11/15 rules (rows 43-60, 16
losses): 1 thin role, 2 bad luck, 13 wrong script, and 12 of the 16 died on one quarterback's passing night (Rodgers 143 yards needing
200, rows 46 / 48 / 49; Herbert 129, rows 50-57 and 60). Both posted Monday slips (rows 57, 60) needed Herbert's yards and a TD pass.

**The timer note is closed.** The owner ran sql/github_timers.sql again on the morning of 11/17: since 9:20:01 AM CT feeds.yml has been
started by dispatch on every ten-minute slot (56 of 56 through 6:30 PM, none failed). The three notes above that say "until the owner
runs the timers SQL again" no longer apply; the hand dispatch is only for a mirror found old.

**Passing-yard legs, Weeks 6-10 (437 graded).** Favorites (-400 to -131) hit 62.7% against 67.9% priced, -7.6% a leg (209 legs): the
same as receiving yards (-8.6%) and receptions (-9.4%). The market is not the leak; one leg stacked into every slip is. Where the
projection sat 25+ yards over the line: 61.0% against 71.2% (-14.4%, 77 legs) - a wide gap on a passing floor is not safety. By closing
spread: underdogs of 3.5+ 57% against 68% (61 legs, 38 QB-weeks), favorites 64 / 68, within a field goal 65 / 68. Thin; not a rule.

**Game-card Best parlay (bp_pick.py, build_boards.dogml, tests/bp_pick.py 25).** Tuesday 3:50 PM: 10 of 13 cards were two game lines
at -6 to -10 cents (8 of those games had no props posted - their ~100 builder "legs" are all spreads, totals, moneylines; HOU-IND has
props and one player leg reaches the last gate, Nico Collins 6+ catches at +172, which no strip takes; MIN-SF none).
- With nothing within 5 cents of fair the picker took the best EV outright; the first pass prices at 3,000 draws, where a slip's EV
  moves about two cents by simulation alone. Now those candidates are re-priced with the card's own draws, slips within 3 cents of the
  best EV are tied, a slip with a player leg beats two game lines, then the most likely to hit wins.
- A card parlay carries no moneyline the model has under a coin flip, unless Sweep says calls that side. This - not the tie - moved
  PHI-PIT off Eagles ML + Over 38.5 (+423, 18%, -6.8c) under "Model has PIT 21.5-17": the PIT pairs were 3.4 cents behind it.
  (Told the owner at 6:50 PM it was "a fraction of a cent" - true of LAC-NYJ at 3,000 draws, not of PHI-PIT. Corrected in the report.)
- Changed 11/17 evening: PHI-PIT -> PIT -4.5 + Under 38.5 (25%), LAC-NYJ -> LAC -3.5 + Over 41.5 (24%), MIN-SF -> 49ers ML + Over 46.5
  (29%). The five big-spread cards keep "dog + total": the favorite's side is juiced to -115 and fails the 3-point gate.
- Home page: "Built for the game's most likely script" only when it is (bp_pick.fit_note); otherwise "Does best if ... (N% likely)".
- `BP_DEBUG=1 python3 build_boards.py` prints every candidate, its chance per ending, and the rule that picked.

**Volatile is off slips (owner "Sure").** sweep.TAG_W["Volatile"] = 0: no risk point, off the builder and the boards, still on the
player page. Walk-forward Weeks 7-10 it did not separate (3.2 points under the price against 3.4 for the rest). 17 players carried it;
7 legs leave Some / High risk for Low. Re-check on Tuesdays (flag_stats prints it).

**Fantasy page and Trade calculator for a manager with many leagues (fantasy_nav.py, tests/fantasy_nav.py 82, trade_outlook 35).**
Owner: "more intuitive and maybe condensed. It's a lot of scrolling ... I have a ton of sleeper teams". Measured at phone size with a
14-league mock account: Trade calculator 19.6 screens (league buttons 0.6, import box 1.2 screens down, rankings 13.7), Fantasy 8.2.
- `bsLg` (league bar + sheet): the bar shows the league on screen, record, place, and on the Trade calculator the verdict; the sheet
  lists every league with a search box past eight; each row fills in its record (one rosters call per league, three at a time, kept 30
  minutes in sessionStorage) and - Trade calculator only - Buy / Hold / Sell / Out with playoff odds (bsOutlook.quick: the card's own
  odds and 70 / 35 / 12% cut-offs, 1,500 sims, that league's schedule). 14 leagues = 14 + 56 Sleeper requests, once.
- `bsTabs`: one section at a time. Trade: Calculator / My league / Rankings (import or /trade/#league opens My league; any Load button
  opens Calculator). Fantasy: Lineup / Roster / League / Waivers (League goes for a hand-built team). The row stays under the site bar;
  on the Fantasy page the page-links row above it no longer sticks.
- A saved username loads by itself on both pages (before: typing + a button on Fantasy, only /trade/#league on Trade). A hand-built
  team (bs_team_mode = manual) is left alone. The connect form goes once connected; "Use another" in the sheet brings it back.
- Trade: the format toggles fold into one line that follows the league picked; rankings show 30 rows + "Show all N"; the method note
  folds. Fantasy: the two intro cards are two small buttons; "How this works" folds; the waiver list's matchup chip no longer stretches.
- After: Trade calculator 2 screens (Calculator), 3.3 (My league), 3.7 (Rankings); Fantasy 2.5-3.1 per tab.
- NOT done: verdict chips on the Fantasy page's own sheet (they show there only when the Trade calculator computed them in the same
  session); draft-pick ownership (league/<id>/traded_picks).

**Market share of a trade value: 30% -> 70% (build_trade.MKT_W).** Owner, after loading his own leagues: "I think we need to add
keepcuttrades rankings and blend into ours until we can beat it." KeepTradeCut's FAQ: no API, scraping forbidden, and using its full
values in another tool is forbidden by its terms - so its numbers are not used. The market on file is FantasyCalc (real trades, pulled
daily by the sheet's script into 'AUTO - Market Values'; 419 players, stamped 11/17 5:53). Its share went from 30% to 70%; the page
says so in three places. Other market sources with clear permission, if a second one is wanted: Dynasty Dealer's public API (free for
commercial use with a visible "Values by Dynasty Dealer" link; Sleeper ids; daily) and DynastyProcess's open data on GitHub (GPL-3).

## 11/17, 8 PM CT: owner "I want all four" - overlap check, posted-slip alert, pick ownership, the values scoreboard, game scripts recovered

**Values scoreboard (research/value_board.py, value_board.json).** "Blend into ours until we can beat it" needs a check that says when.
Nothing new had to be saved: every Tuesday's Trade calculator is in the site's history, and the page puts both numbers on each player
(`ours`, `mv`). The script opens each week's first build as it was published (Playwright, the old page + its data file), reads both in
redraft 1QB PPR, and compares them with PPR points per game from that week on (nflverse weekly stats). Three builds so far:
| built before | graded on | ours | market | 70% ours | 70% market |
| Week 8 | Weeks 8-10 | .427 | .442 | .438 | .446 |
| Week 9 | Weeks 9-10 | .467 | .495 | .478 | .486 |
| Week 10 | Week 10 | .387 | .446 | .416 | .429 |
(pooled Spearman rank correlation with what followed, players either side had as startable: QB 24, RB 48, WR 60, TE 24.)
- The market ranked the following weeks better in 3 of 3 builds. By position: the market at WR in all three (.47 / .59 / .61 against
  .43 / .49 / .39) and at QB in two; ours at RB in two and at TE in all three. **Our receiver values are where the market beats us.**
- Disagreements of 1,500+ (56 players): by place among their position afterwards, 23 for ours, 21 for the market - a coin flip. The
  first version of this count said 38-18 for ours; it turned a player's finish into a value off the HIGHER of the two numbers, which
  leans toward whichever side is higher on a player. The place count stands.
- Where the two disagreed and the market's own number then moved, it moved toward ours 30 of 46 times in redraft and 20 of 33 in
  dynasty. Suggestive (z about 2.4 against a coin), not proof.
- Working rule for build_trade.MKT_W (0.7 now): ours gets its share back when it out-ranks the market, pooled, in three straight
  weekly builds. Run `python3 research/value_board.py --write` on Tuesdays once the week's stats are in; the Trade calculator's note
  prints the tally from the json.

**Overlap check on posted slips (sweep.shared / share_note, tests/promo_overlap.py 14).** Two open promos (no result, not hidden) that
carry a leg on the same player - or the same game line / the same either-or pair word for word - are one bet posted twice.
build_promo prints `promo check warning - overlap: slots A and B (...) share X` and saves `shares` on each promo; the home page's cards
(home.promo_card) say "Also riding X: <other slip>. If that misses, both slips lose - play one, or size the two as one bet."
/b/promos.json carries `shares` too. An either-or TD leg does not overlap with a plain leg on one of its two players. In chat: the second
slip for a stand-alone game is built for the other script, with no player in common with the first.

**"The Daily Sweep is up" (push/slip-alerts.ts promoUp, sql/push_promo.sql, tests/promo_up.py 16) - BUILT, OFF, two owner steps.**
One push per posted slip to the devices with push_subs.promo = true: LIVE, no result, first kickoff ahead, Posted today or yesterday
(Central); push_sent `__promoup__w<week>-<slot>` / POSTED remembers who was told. /b/promos.json now carries fd, first_ko, result,
posted. The switch on My BetSweep > Slip alerts is behind account.PROMO_ALERTS = False. To turn it on: (1) the owner runs
sql/push_promo.sql (one `alter table ... add column if not exists promo boolean not null default false`, no secret), (2) he redeploys
the slip-alerts function from push/slip-alerts.ts, (3) a session sets PROMO_ALERTS = True and publishes. The test runs the function's
own text under node with the database and push service stubbed (tsc reports the same 21 Deno-only messages as before, no new ones).

**Who holds which rookie picks (fantasy_outlook.ownPicks; tests/trade_outlook.py 43).** league/<id>/traded_picks lists only the picks
that changed hands; every other pick is with its own roster. Next two seasons, rounds 1-3 (what the page prices); a first is early /
mid / late by where its original team is tracking to finish (t.er) for next year and mid for the year after. Dynasty only (the page
prices picks only there). The card lists "Your picks", pays for a target only with a pick the reader holds ("your 2028 1st", "the 2027
2nd you hold from Team 4") and asks a buyer only for a pick he holds; Load puts the priced asset on the calculator. No pick list from
Sleeper = the card says nothing about who holds what.

**Game scripts recovered (research/freeze_scripts.py -> research/scripts_history.json).** The model's read of each game at the last
build before its kickoff, from the site's history: Weeks 8, 9, 10 (14 + 15 + 14 games; the last pre-kickoff build was a median 45 to
112 minutes ahead). Weeks 6-7 had no builder data file in the history. Weekly snap shares never needed saving: in/snap_counts_2026.csv
(nflverse) holds every week.
- **Losing side, by its own definition** (yardage overs on the team the likeliest ending has losing by 10+), floor legs at -180 or
  shorter, Weeks 8-10: 58.8% against 70.3% priced on that side (-11.5 points, 318 legs, 189 player-weeks; -3.8 / -16.3 / -15.6 by
  week); 70.4% against 70.3% on the side it has winning big (311 legs: break-even, each week within a point); 66.5% against 70.3% in
  games with no big-win ending (325). Every price, not just floors: loser side 46.4 / 56.6, winner side 55.7 / 56.9.
  A yardage floor is a fair bet on the projected big winner and a bad one on the projected big loser.
- **Filed from now on** (build_boards.py SC_FROZEN -> data/scripts-w<week>.json): every build before a game's kickoff replaces that
  game's record; after kickoff it stays. flag_stats.scripts() reads the recovered weeks plus these files, and the Losing side
  sentence is now counted on the flag's own definition once 150 legs sit on each side (the closing-spread count stays as the
  fallback and is still printed). tests/flag_stats.py 18.
- MASTER log row 604 (11/17 evening). Rows 603 and 604 are both dated 11/17; 604 is this session's.

## 11/17, 9:25 PM CT: the posted-slip alert is ON (owner: "Ran the sql and slip alerts")

- account.PROMO_ALERTS = True: My BetSweep > Slip alerts shows "When BetSweep posts a slip". The box stays hidden until the device's own
  push_subs.promo is read, so a database without the column shows nothing rather than a dead switch. The session cannot reach the
  database: whether the column and the redeployed function are in is the owner's word plus that behaviour. First real check: the next
  slip posted with a kickoff ahead (Thursday's Daily Sweep) should push to a device with the switch on within one alerts run of the
  publish; the function's summary carries `posted`.
- tests/promo_up.py 17 (the flag line may carry a comment; the built My BetSweep page is checked against the flag).

## 11/17, 9:40-10:30 PM CT: the long pages, shortened (owner 9:23 PM: "Did you finish updating and optimizing every page?")

Same treatment the Fantasy page and the Trade calculator got at 8 PM: tabs, folds and "show all" buttons. No row was removed from any
page; what changed is how much opens at once. Phone lengths (390x844), live copy before -> this build:

| page | before | after | what changed |
|---|---|---|---|
| Players (/player/) | 33.9 | 3.8 | first 30 (props this week first); search and position still look through everyone; "Show all N" |
| First TD | 17.8 | 4.5 | each game folded behind a header naming its three most likely scorers; a chip, a name in the lists or #ftd-<game> opens it; one of the two top lists at a time on a phone; the method folded |
| Line shop | 14.0 | 3.4 | three-line rows with the better price on the button; first 15; an All / DraftKings / Hard Rock switch |
| Usage | 12.8 | 3.3 | first 12 of the list on screen, "Show all N"; Rising / Falling and position re-count |
| Season | 10.4* | 4.4 | on a phone its seven report cards open on their titles (shared script, see below) |
| DFS | 10.3 | 3.9 | Players / Lineup / How it works as tabs on one column (wide screens unchanged); pool opens at 20 rows; with no salaries the best projections lead (it was QBs A to Z) |
| Model's Best | 9.2 | 2.6 | one tab per tier (Plus money / TDs / Near even) and per section (Next up / Radar / Parlays), the count = cards still open to bet; /best/#parlay opens on the parlays |
| News desk | 9.0 | 2.7 | Out / Limited / Back tabs, notes two lines until tapped, the team filter re-counts the tabs and moves to the first group with a note |
| Who benefits | 7.6 | 2.7 | one folded block per injured player; the header says who got the work |
| Teams | 6.9 | 4.9 | Standings / League table tabs |
| Teasers | 6.9 | 3.2 | one teaser size per tab |

- *Measuring.* Pages built from template.html (Boards, Receipts, Season) give every off-screen `.card` a 900px placeholder
  (`content-visibility:auto; contain-intrinsic-size:auto 900px`), so `scrollHeight` at load over-states them. The 9:25 PM table said
  Receipts 27, Boards 15.4, Season 13.3; with every card laid out they are 15.0, 10.9 and 10.4. /tmp-style check: add
  `*{content-visibility:visible!important}` before reading the height. A closed `<details>` also keeps its content's box, so a test's
  "is it on screen" must use `el.checkVisibility()`, not a bounding box (tests/page_fold.py VIS).
- *Tabs.* fantasy_nav.TABS_CSS / TABS_JS are bsTabs alone (no league bar). The script goes inline before the page's own script. The
  host has to be a direct child of something as tall as the page or the row cannot stay pinned (a wrapper the height of the row pins
  nothing). A row wider than the screen scrolls sideways and keeps the chosen tab in view (`keep()`, also after a count changes).
- *Model's Best.* home.py wraps each tier in `<div class="mbgrp" data-tab data-label>` with its own "All kicked off" line; build_site.py
  tags the sections that follow and mounts the tabs (BEST_TABS_JS). B["best"] is used on /best/ only.
- *News.* build_today.py writes the three groups as data (today_parts.json `groups`); build_site.py NEWS_JS.
- *Season.* Built on Tuesdays and kept by a reprice, so its fold is in the shared stylesheet and script (build_site.py: `.card.calib.bsfold`,
  `foldCards()`), which rechrome.py puts on every kept page at each build. A folded card is `content-visibility:visible` so it takes
  its real height. Wide screens are untouched.
- *Local builds.* out/season-receipt.html and out/results-week9.html in this checkout were 11/10 leftovers, so local /season/ was a
  week-old page the publish run never builds. Moved out of out/ (to /tmp/stale_out): a local build now keeps the published Season page
  and receipts the way the workflow does. That kept page links the published copy's own /s/tpl-<hash>.css, which a local ./site
  does not have - it renders unstyled locally and styled once published.
- *Left alone, on purpose.* Boards (10.9 real: one card per game under jump chips), the Parlay Builder (7.7: game cards already folded,
  chips), weekly Receipts (15.0 real: jump chips; its scorecard is also the share image, so tabs there belong in build_results.py with
  next Tuesday's receipt), the Guide (8.3: a reading page with a contents list), legal pages. Not done yet: player pages (6.7),
  game dossiers (6.1), team pages (5.8).
- tests/page_fold.py (86): lengths in both themes, every fold / tab / cap above, deep links, wide screens. tests/week_end.py opens the
  Parlays tab before reading it; tests/inactive_block.py opens Line shop's "Show all" before counting rows.
- Not this change: tests/menu_ask.py fails one check ("Theme near the top of My BetSweep") on the published copy too - it predates the
  hub-box tabs on My BetSweep.
- *The local gate after a shared-script change.* tests/local_gate.py crawls ./site alone. When the shared stylesheet or script
  changes, rechrome.py writes a copy of every kept page (Season, the receipts, old short links: 36 pages on 11/17) into ./site, and
  those link the published copy's /s/tpl-<hash>.css, which ./site does not have: the gate HOLDs on "MISSING FILE" for /season/ and
  the receipts. That is the local crawl, not the build. Check it the way the workflow does - on the build copied into a scratch
  copy of the published site: `mkdir -p /tmp/cc/site && git -C <clone> archive HEAD | tar -x -C /tmp/cc/site`, then
  `python3 -c "import reprice as R; R.copy_into_clone('/tmp/cc/site')"`, then `SITE=/tmp/cc/site python3 tests/local_gate.py`
  (11/17: 540 pages, 0 problems). tests/page_fold.py takes the same SITE.
- Published 10:48 PM CT (gen-overrides c9f847f7, live 8ad63fad, deployment success). Published copy, phone screens: Players 3.8,
  First TD 4.5, Season 4.4, DFS 4.0, Teams 4.9, Usage 3.3, Teasers 3.2, Line shop 3.0, News 2.7, Who benefits 2.7, Model's Best 2.6;
  47 page types, no sideways scroll, no script errors; tests/page_fold.py 86 on the published copy. MASTER log row 605.

## 11/17, 11:30 PM CT: player pages, team pages and game previews under tabs (owner: "Okay keep working")

| page type | before | after | tabs |
|---|---|---|---|
| a player (382 pages) | 6.7 | 2.6 | Props / Last N / Model / Stats - opens on this week's props; with no lines this week it opens on Last N (217 pages on a Tuesday) |
| a team (32) | 5.8 | 3.0 | Stats (at a glance, per-game table, defense against each role) / Games / Leaders |
| a game preview (13) | 6.1 | 2.4 | one column: Game (script, injuries / weather / news, tested spots) / each offense; two columns (901px+) unchanged, no tab row |

- fantasy_nav.panels(host_id, blocks, key, start, weak): the panels are written with the opening one on screen and the rest `.fxoff`, so
  nothing flashes before the script runs; `<noscript>` shows them all; `#<tab id>` in the address opens a tab. These three page types
  pass key=None on purpose: a page reached from everywhere (a name on the boards, the search, a teammate link) always opens the same
  way - a player's props - instead of whatever tab was open on the last player. (Fantasy / Trade / Model's Best / News keep theirs.)
- Player tab ids: props, last, model (What the model sees + BetSweep's record on him), stats (Usage + Game log + Teammates). Team:
  stats, games, leaders. Preview: game, o<team> (e.g. #okc).
- The tab styles ride in /player/player.css (build_players.py writes it; team pages and previews link the same file), so a build that
  skips build_players.py would leave team and preview tabs unstyled - it never does (the step is in reprice.BUILD twice).
- tests/page_fold.py is 104: adds a player with props (every section under a tab, each shown once, + still adds to the slip, the row
  stays pinned, #stats), a player without, a team (box score still loads under Games, #games), a preview (phone tabs, wide unchanged,
  #o<team>).
- Looked at and left: Survivor (4.8 - a tool with a flow, the owner's toggle stays put), Home (5.9 - nine short sections he laid out),
  How (4.8, a reading page).

## 11/18, 12:15 AM CT: receipt scorecards on a phone, and the share pictures that were broken

- *Receipts.* A weekly receipt's scorecard is five groups of tiles and tables - 6 of the page's 15 phone screens. On a phone it shows
  one group at a time (Lines / Posted / Calls / Projections / Games, from the groups the page has) with two tiles to a row:
  Week 10 15.0 -> 10.4 with every card laid out, Week 9 15.3 -> 10.9. Like Season, the receipts are kept by a reprice, so this lives
  in the shared script (`foldScore()`) and stylesheet (SCORE_TABS_CSS) and reaches Weeks 5-10 through rechrome.py. The shared script
  now carries bsTabs itself (`if(!window.bsTabs){...}`), the shared sheet the tab styles. Wide screens: unchanged.
- *The share pictures ("Copy card as image", "Story 9:16").* Found while checking that a folded scorecard still shares whole. On the
  published pages as they were, in the test browser (Chromium 153):
    - the receipt scorecard: "Could not render - Attempting to parse an unsupported color function "color"". html2canvas 1.4.1 cannot
      read the `color(srgb ...)` value a browser reports for `color-mix()`, and `table.sc` has one as its background. Phone and wide.
    - every other card (Season, a receipt's Calls): the picture stopped at 992px. The tool draws an off-screen copy of the page; a
      `.card` is `content-visibility:auto` with a 900px placeholder and is never "on screen" in that copy. template.html has
      `.card.shooting{content-visibility:visible}` for this, but nothing adds `shooting` any more.
  Fix, in the shared script and sheet so it reaches the kept pages: a click on a picture button puts `.bsshoot` on its card before
  the page's own handler runs (capture phase); `.card.bsshoot` is laid out in full, a folded scorecard shows every group and hides
  its tab row, `table.sc` takes plain `var(--chalk)`. The class comes off when the picture lands (a `.shotwrap` is added) or after
  12 seconds. Pictures now: scorecard 760x8072 on a phone and 2466x5510 wide (the whole card), Calls 760x4086, Season 760x3928.
  The Story picture's right edge was cut off as well: its 540px frame is added to <body>, whose children are zoomed 1.1x (1.06x wide),
  so the card inside was 594px. `body > .storyframe{zoom:1 !important}` (shared sheet). Season's Story before / after: cut at
  "FROZE" with the chart's last week missing -> the whole width.
- Why nobody saw it: the buttons say "Could not render" / hand back a picture that looks plausible at a glance. Worth a real-phone
  check by the owner (Safari reports color-mix() the same way, so it very likely failed there too - not verified from here).
- tests/page_fold.py is 126: receipt tabs on Weeks 5-10, the four pictures against their cards' proportions, the Story frame's width. Its server falls back to
  the published copy for a /s/ file a local ./site lacks (CLONE env), the way the publish step's merge does.

## 11/18, 1:00-1:40 AM CT: "how much does this week matter" for every league, and two calibration moves (owner 12:23 AM: "strengthening our probabilities when choosing legs ... like how we're making our sleeper teams better")

**Fantasy: the week's swing.**
- The outlook's simulation already plays the rest of every league's season (fantasy_outlook.py `sim()`, 3,000 seeded runs; `quick()`
  1,500). It now also remembers, per run, who won the NEXT week to be played, so each team gets
  `t.wk = {w, pw, win, lose, opp}`: the week, how often he wins it, and his playoff odds in the runs he won it and in the runs he lost
  it. `swing(t)` is the gap in points. Only set with 200+ runs holding a game that week and 20+ on each side (a 99% favourite has no
  honest "if you lose" number). `opp` is the real opponent when Sleeper's matchups for that week are in.
- Trade page: one line under the playoff odds (`p.olwk`, `weekLine()`): "Week 11 vs Team 12 · you win it about 56% of the time · win and
  you are 51% to make the playoffs, lose and you are 19% · 33-point week · A big one." 25+ points reads "A big one." (red chip),
  10+ "It matters.", under that "A small one." / "You are close to in either way." / "It barely moves your odds."
- League switcher (fantasy_nav.py): every league row shows its swing under the record ("37-pt week", red at 25+), and with three or more
  leagues a two-button row sorts them "Sleeper order" / "Biggest week first" (kept for the visit, `bs_lg_sort`). The bar's small line
  adds "· N-pt week" at 10+. For someone with many leagues this is the answer to "which lineup do I set first".
- Checks: tests/trade_outlook.py 49 (the line sits under the odds, names the real opponent, `lose <= odds <= win`, and
  `pw*win + (1-pw)*lose` returns the playoff odds within a point); tests/fantasy_nav.py 92 (every row shows a swing, a bubble team swings
  more than an 8-2 or 1-9 one, the sort is descending and keeps all 14 leagues, "Sleeper order" puts them back).
- Limit: tested against mocked Sleeper leagues only, like the rest of the Fantasy pages - the owner's real leagues are the real test.

**Calibration (calib.py), from research/floor_depth.py on the 8,094 graded frozen legs, Weeks 6-10.**
- New study, re-run every Tuesday with blend_weight.py and recal.py: `python3 research/floor_depth.py <legsnaps.json>`. Section 1 is the
  live rule against FanDuel alone week by week (it prints "lost N straight" - the two-straight-weeks rule in one glance); 2 is shown %
  minus hit rate by how deep the line sits under the projection; 3 is the floor cut, leave-one-week-out; 4 is the watch list.
- **Anytime TD weight 0.5 -> 0.3.** FanDuel alone beat the 0.5 blend in Week 9 and Week 10 (log loss by 0.012 and 0.0145; best
  single-week weight 0 both times, after 1.0 / 0.7 / 0.5 in Weeks 6-8). Pooled best 0.1, leave-one-week-out picks 0-0.3. A step, not
  the whole way. Where the model had a scorer 8+ points over the price he scored 26.5% against a 26.5% price (34 legs). Effect this week:
  88 touchdown legs moved; a long shot's shown edge shrinks by 40% (Giddens +3300: +8.5 -> +5.1). Tier membership did not change (the
  tiers gate on the raw lead and the 11/17 role rule), the shown edges and every parlay's fair odds did.
- **Receiving-yards floor cut** (`FLOOR_CUT`, `FLOOR_BAND`, `floor_cut()`, `shown(..., line=, proj=)`): where the line is 55-85% of the
  player's projection the shown % ran 4.5 points above the hit rate (1,040 legs; high in all five weeks at 55-70%). Half of the bias
  measured on the other four weeks, taken off the held-out week: better in 5 of 5 (log loss 0.6841 -> 0.6814, 1,328 legs). So 2.25
  points come off inside the band, tapering to nothing over 50-55% and 85-90%; the under on the same line goes up by the same amount.
  Deeper floors (under 55%) and lines at or over the projection were already fine and are untouched.
  Every caller passes the line and the projection so all pages agree: builder (both blends, the unders, the track-record bands),
  boards, home's top plays, the other-book swap (hrswap.py), the face-off ceilings. Without them `shown()` is the plain blend, as before.
  Effect this week: 27 receiving-yards legs down up to 2.25, 6 unders up; two games' best parlays changed (BUF-MIA swapped Shakir 25+
  yards for Shakir 3+ catches; CIN-WAS kept its legs at a lower fair number). build_builder's defense-vs-role step still tilts the
  calibrated number afterwards (up to 1.6 points), as before.
- How BetSweep picks says both in plain words (how_stats.weights_text(): "about a third on touchdowns", and one sentence on the cut,
  written from calib.py's constants).
- tests/calib_floor.py (16): the cut inside / outside the band, no jump along it, the under mirrors, no other market touched, bad input
  falls back, and on the built board every receiving-yards and touchdown leg shows the calibrated number and no player's ladder is
  turned upside down. Added to the pre-publish set.

**Tested and NOT adopted (each is printed by floor_depth.py so Tuesday's run settles it).**
- The same cut on Receptions. The over-statement is bigger there (55-85% of projection: shown 69.5%, price 69.3%, hit 60.6% on 277 legs
  from 269 player-weeks) but the half-cut was better in 4 of 5 held-out weeks, not all (Week 6 lost 0.0022). Precedent: passing yards
  was held back on 11/6 for missing one week. Until it passes: in chat-built slips treat a receptions line sitting a little under the
  projection as over-priced, whatever the shown edge says.
- A heavier model weight on deep receiving lines (line at or under 45-60% of the projection). Fitted off-week it wins 2-3 of 5; Week 7
  carries the pooled gain.
- "Deep line, model well over the price" as a tier: receiving yards, line at or under 55% of the projection, raw model 10+ points over
  FanDuel, one rung per player-week: 32 of 50 against a 52.9% average price (+0.24 units a leg, z 1.57; weeks 5/12, 8/11, 5/7, 7/10,
  7/10). The cell was picked after looking at a grid of them, mostly fringe receivers at 5-20 yard lines (median price -113), which is
  exactly the thin-role floor leg the 11/15 slip rules keep out. Tracked, not a lead: floor_depth.py prints a "SINCE IT WAS PICKED"
  line from Week 11 on, and that line - not the 32 of 50 - decides whether it ever becomes a tier.
- Rushing and passing floors: the cut made them worse (0 of 5, 1 of 5). Rushing already has its RECAL row.
- Still untestable: DraftKings / Hard Rock consensus as "the market" (only 23 graded tier picks carry the other books' prices).

## 11/18, 7:35-9:00 AM CT: short prices (calibration + the short-priced tier) and an all-leagues lineup check (owner 7:34 AM: "Keep working")

**What started it.** A reliability table of the live shown % on the 8,094 graded frozen legs (Weeks 6-10): calibrated within a point from
0 to 70% (overall +0.6), but legs shown at 70-80% hit 65.5% (505 legs from 433 player-weeks, t 3.5, high in all five weeks). It is the
price: in the three blend markets the hit rate climbs with FanDuel's price up to about 70% and then stops (priced 68-72%: 66.3%, 72-76%:
67.7%, 76-80%: 63.4%); across every market a leg at -317 or shorter lost 14.6% a leg, negative in all five weeks. honest.py had found the
same wall on 11/15 for the builder's "honest chance" (capped at 68%); the shown % and the tier had not followed.

**1. calib.py: a price above 70% is read at half strength** (`PRICE_KNOT`, `PRICE_SLOPE`, `squeezed()`; inside `shown()`, over side of
receiving yards / receptions / passing yards). Fitted off-week the best slope above 70% was 0 in every fold; that full squeeze was better
in 4 of 5 held-out weeks and half of it in 5 of 5 (+0.0002 / +0.0062 / +0.0034 / +0.0015 / +0.0028). Knots of 68% and 72% tied their
worst week and won the other four. Effect: -300 reads as 72.5%, -400 as 75%; a leg the model merely agrees with at -300 now shows two to
three points UNDER its price. The edge is still shown against the real price. Still true after it: legs priced 76%+ show 70.9% and hit
63.4% - the squeeze is a step, like the touchdown weight. The receiving floor cut was re-tested on top of it: still 5 of 5.
Not adopted: no model credit above a short price (3 of 5 alone), squeezing the shown number itself above 68% (half size 4 of 5), a flat
cut for legs shown 70%+ (4 of 5; 5 of 5 only at 72%).

**2. build_builder.py: the short-priced tier takes nothing at -200 or shorter, and nothing with one of our red flags.**
- Price. The tier's rule on graded legs (shown 65%+, raw model at or over the price, best rung per player and market): 255 picks, 65.1%,
  -13.4 units. Its picks at -200 or shorter: 112 of 185 (60.5% against a 71.6% price), -28.1 units, losing in all five weeks. Its picks
  priced longer than -200: 54 of 71 (76.1% against 63.7%), +13.7 units, no losing week. The tighter the cap the better (-285: -0.04 a leg,
  -257: +0.03, -233: +0.06, -200: +0.19). -200 is the line the site already draws for a floor leg (honest.FLOOR_ODDS; the best-parlay rule
  of 11/15), and Week 10, graded after that rule, agreed (10 of 16 against 27 of 44). `_SAFE_FLOOR = -200`.
- Red flags. Seven of the twelve tier picks on Wednesday's board carried one (losing side, near-zero risk, backup QB, blowout script,
  tough matchup, cleared 2 of 10) - legs the owner's low-risk rule (11/7) keeps out of every slip. flag_stats.py has the two graded ones
  under their prices in every week counted (near-zero 61% against 70%, 247 legs; yardage floors on the losing side 60% against 70%).
  Judged rung by rung, so a player can still come in at another line. The backtest above cannot apply this half (past flags are not
  archived), so the live tier is narrower than the 71 picks it describes.
- Role. The near-zero rule of 11/15 (four games on record; under half the line in fewer than a third of them) now applies to every tier
  pick (`_safe_role_ok`). The flag itself only looks at legs priced -180 or shorter, and with the cap most of the tier sits at -130 to -179.
- Wednesday's board (TNF plus the first Sunday lines): the tier went from 12 picks to 1. Expect a handful on a full board, not a dozen.
- The model's lead at a short price is not an edge: priced 70%+, legs with the raw model at or over the price hit 60.5% (129) against
  66.3% for the rest (650), in every market with enough legs. This is the 11/15 slip rule ("a big gap on a short-priced floor leg is a
  warning"), now with Week 10 in.
- Words: the tier's tooltip, the Guide and the Season page say "priced longer than -200"; How BetSweep picks gets one sentence on the
  half-strength reading, written from calib.py's constants.

**3. research/floor_depth.py section 5** prints all of it each Tuesday: 5a hit rate by price, 5b the squeeze by held-out week at three
knots, 5c the tier by price cap week by week, with a "SINCE THE CAP" line from Week 11 on (if the left-out legs start beating their price,
lift the cap). tests/calib_floor.py (25): the squeeze (nothing at or under the knot, half above it, overs of the three markets only, never
lowers the number as the price shortens, no jump), every receptions / passing leg on the built board shows the calibrated number, no tier
pick at -200 or shorter, none with a red flag, each with four games on record and few near-zero games.

**4. Fantasy: every league at once** (owner 11/17: "I have a ton of sleeper teams"). Under the league bar, one line: "5 of 13 lineups
need you" and the first league to fix; a tap opens the list in place, a tap on a league opens it on its Lineup tab.
- A league needs you when a starter cannot play (out, IR, bye), a lineup spot is empty, or the model's best lineup from the same roster
  is worth a point or more over the one set in Sleeper (`GAIN_MIN`). Best-ball leagues set themselves and are never listed.
- `lineupCheck(l, pm, rosters)` in build_team.py scores a starter with `mkEntry()` - the Lineup tab's own `entry()`, lifted out of
  `render()` - so the list and the tab cannot disagree. It needs only the rosters call the league bar already makes: Sleeper's `starters`
  is the lineup as set. The other leagues are read after the first one is on screen, three at a time, kept half an hour.
- fantasy_nav.py: chips are now kept per page (`opt.ns`; the Trade page's playoff odds and the Fantasy page's lineup verdict are
  different answers about the same league), `bsLg.scan()` reads every league without opening the sheet, `opt.onUpdate` tells the page,
  `bsLg.state()` hands it the results, and the sheet's second order is worded by the page (`opt.sortLabel`: "Needs you first" here,
  "Biggest week first" on Trade; chip.ord, else chip.sw). The league bar's chip on Fantasy is the lineup verdict ("Fix 2", "+3.4", "Set").
- The fold "Who you start the most" counts each player across the lineups (two or more), with his BYE / OUT / Q tag.
- One download of Sleeper's player list, not two (`PMAPP`): the all-leagues read asks for it while the first league is still loading.
- One line until asked on purpose: opened by default, a 13-league account pushed the league itself a full screen down (the page test
  caught it: tabs at 911px).
- tests/fantasy_nav.py (125): one rosters call per league and one player list; every league starting an injured player names him; the
  best-ball league is off the list; a tap lands on that league's Lineup tab and the tab shows the same points and the same sidelined
  starters; the sheet carries the same verdicts and sorts "Needs you first"; a reload inside the half hour asks for one league only; a
  lineup that already is the model's reads Set (the page's own best lineup is played back as Sleeper's); a one-league account gets no card.
- Limits: mocked Sleeper leagues only. Not yet done: sending every league's roster to the account for Sunday inactive alerts (today only
  leagues the reader has opened are stored), and the same card on the Trade page.

## 11/18, 9:10-10:00 AM CT: the house slip changes shape on the owner's word (a trial), and free agents across leagues

**The slip rule (owner 9:09 AM, asked whether to build from legs the model likes at -130 to -199, three for about +300: "Sure we can try
it and see how it goes").** PROMO_DESK.md rule 3 and the Daily Sweep recipe now say so; sweep.py's header, the home page's teaser line
and two sentences on How BetSweep picks follow (the How page states the record and that it is a trial graded in public).
- What "the model likes it" means, from research/floor_depth.py's legs at -130 to -199 (one rung per player and market, Weeks 6-10):
  a Model's Best short-priced pick (shown 65%+, raw model at or over the price) 52 of 69, 75.4% against 64.0%; raw model 8+ points over
  the price 42 of 60, 70.0% against 61.0%, ahead in all five weeks; either one 66 of 92, ahead in all five weeks, median price -172
  (three pay about +295). The model merely at or over the price with the shown number under 65%: 105 of 185, 56.8% against 59.9% - not
  enough, and the desk rule says so. Every leg in that price range: 57.2% against 61.3%.
- In-sample, three different players drawn from one week's pool all hit 38% of the time (a +300 slip breaks even at 25%). That is the
  optimistic reading: the pool was defined on these same weeks, and the red-flag / role rules cannot be applied to the past.
- It is a TRIAL. Every slip built this way carries "trial 11/18: 3 legs, -130 to -199" in its Notes ('ASSIST - Slip Log' and the promo
  row); Tuesday's grading reports the tally to the owner. The old shape (4 legs at -300 to -200, "Keep it at 4", 11/10) is not to be
  brought back, nor plus-money legs brought in, without him.
- Wednesday's board holds 5 legs in the pool and none of them passes the low-risk rule yet (Sunday's lines are still posting); the one
  Thursday game has none. The recipe's fallback covers it: that game's Sweep says leg or a same-game either-or TD pair in the third
  spot, or two legs, or no Sweep that day - never a -200-or-shorter floor.

**Fantasy: free agents who would start for you** (the second fold in the all-leagues card).
- `lineupCheck()` now also returns `fa`: up to three unowned players in that league whose points this week beat the weakest starter the
  model would play at their position by `PICK_MIN` (2.0) or more - the Waivers tab's own comparison, a spot with nobody in it counted
  as zero. Same rosters call, no extra request. Not computed for best-ball leagues.
- The card groups them by player: "free in 4 leagues", each league a button with the margin ("+4.1"); most widely available first, five
  players at most, three league buttons each ("and N more"). A tap opens that league on its Waivers tab. With every lineup set, the
  folded line says "N free agents who would start for you".
- tests/fantasy_nav.py (129): the fold only names players nobody in that league holds, margins of two points or more, most leagues
  first, and the league's own waiver list shows the same player at the same margin.
- Limits: Sleeper does not say who is on waivers versus a free agent, the comparison is this week's points (a streaming view, not
  dynasty value), and it is tested on mocked leagues only.
- Not built yet: Sunday inactive and Saturday lineup pushes for every league. Saving every league's roster is a one-line client change,
  but slip-alerts.ts sends one push per league under one tag, so a 14-league account would get 14 buzzes for one message. The function
  needs a per-user summary first, and the owner has to redeploy it.

## 11/18, 10:35 AM CT: roster pushes for every league - the function is ready, the switch is OFF until the owner redeploys

**Why.** The Fantasy page saved only the league on screen to `fantasy_rosters`, so Sunday's inactive push and Saturday's lineup check
covered one league of a 14-league account. Saving them all is easy; the function was the problem: `inactives()` and `startsit()` sent
one push per league under one tag, each replacing the last on the phone (or, where a phone ignores tags, fourteen buzzes).

**push/slip-alerts.ts (the owner deploys it; reference copy here, his copy in owner_send/).**
- `inactives()`: one push per player per person. In one lineup: the old message, byte for byte. In several: "Joe Mixon is INACTIVE in 3
  of your lineups" and "Best bench play by the model: <league>: <player> (pts); ...", three leagues at most, then "N more on the Fantasy
  page". Each league is still marked under the old key (`__ina__<league>|<player>`), so a deploy mid-Sunday repeats nothing.
- `startsit()`: one push per person. One league with a call: the old message. Several: "Lineup check: 4 of your lineups" with the first
  call from each of three leagues. A league with no call is not marked, as before.
- tests/fantasy_push.py (17) cuts both functions out of the file and runs them under node with the database, the push service, the
  feed and the projections stubbed - what is checked is what gets deployed. The one-league expectations were also run against the
  function as deployed on 11/17 and pass there, so nothing changes for a one-league reader. tsc reports the same 53 baseline messages
  (Deno globals) before and after. In the pre-publish set.

**build_team.py: `ALL_LEAGUE_ALERTS = False`** (page data `all_alerts`). When True, the all-leagues read saves every league with a
lineup through the same `syncRoster()` the Lineup tab uses (lifted out of `render()`; one row per league, upsert on user and league);
best-ball leagues and leagues with no lineup are skipped. tests/fantasy_nav.py checks both settings with a stand-in account: off, one
row; on, thirteen.

**To switch it on (in this order):**
1. The owner pastes push/slip-alerts.ts over the slip-alerts Edge Function and deploys (Verify JWT stays off), and says so.
2. Set `ALL_LEAGUE_ALERTS = True`, run the pre-publish set, publish.
3. Privacy Policy, "Optional accounts": "your fantasy roster so alerts can cover your players" becomes "your fantasy rosters in that
   Sleeper account's leagues so alerts can cover your players" - ask the owner first; it is his document.
4. First real check: Saturday 7:05 PM CT (one "Lineup check" push naming how many lineups), then Sunday's inactives.

## 11/18, 12:35 PM CT: roster pushes for every league are ON (owner 12:34 PM: "Updated slip alerts. Change private policy.")

- The owner says the slip-alerts function of 11/18 is deployed. That is his word: nothing here can read the deployed function. The first
  real check is **Saturday 11/21, 7:05 PM CT** - ONE push titled "Lineup check: N of your lineups" (or the old single-league wording if
  only one lineup has a call) - and then Sunday's inactives ("X is INACTIVE in N of your lineups"). If several pushes arrive for one
  message, the old function is still live: set `ALL_LEAGUE_ALERTS = False`, publish, and send him the file again.
- build_team.py `ALL_LEAGUE_ALERTS = True`: the all-leagues read now saves every league with a lineup to `fantasy_rosters` for a signed-in
  reader (best-ball leagues and leagues with no lineup are skipped). The card's footnote tells a signed-in reader so: "Signed in: these
  lineups are saved to your account so inactive and lineup alerts cover every league."
- Privacy Policy (build_legal.py), "Optional accounts": "your fantasy roster" is now "your fantasy rosters in that Sleeper account's
  leagues", in the same build - the page promises to change before the site does. "Privacy Policy last updated" reads November 18, 2026;
  the line now shows the LATER of the policy date and the page-count date (it had been showing November 10 since the page counts went on,
  one day behind the 11/11 edit).
- What a saved roster is: the lineup as Sleeper had it the last time the reader had the Fantasy page open (the read is kept half an
  hour). A lineup changed in Sleeper afterwards is not seen until the next visit. To fix that the function would have to read Sleeper
  itself before it sends (league id and Sleeper name are already in the row) - a function change, so another deploy by the owner.
- tests/fantasy_nav.py (133): the built switch matches build_team.py; on, thirteen rows for fourteen leagues (not the best-ball one) and
  the footnote; off, one row and no footnote; a reader who is not signed in never sees the footnote.

## 11/18, 1:35 PM CT: roster pushes read the lineup from Sleeper first (owner 1:30 PM: "Sure that sounds great")

- push/slip-alerts.ts `freshRosters()`: before `inactives()` or `startsit()` builds a push, each saved Sleeper league of a reader a push
  can reach is re-read with one public rosters call (league id only, 4 s limit, six at a time). The roster sharing the most players
  with the saved one is his (at least half of them); starters and bench are re-split by Sleeper id. Players added since the save have
  no name here and are left out. A failure, a hand-built team, a row saved before 11/18 (no ids) or a roster that no longer looks like
  his leaves the saved lineup as it was. Nothing is written back. The reply carries `fresh` (how many were re-read).
- build_team.py: every saved starter / bench entry now carries `id` (the Sleeper player id). Rows refresh the next time the reader
  opens the Fantasy page; until then his rows have no ids and behave as before.
- Privacy Policy, "Sleeper usernames": one sentence added - signed in with alerts on, the alert service asks Sleeper for the current
  lineups in those leagues before a fantasy alert; the request carries the league's ID and nothing about the reader. Published before
  the owner deploys, as the page promises. TELL THE OWNER it was added (done in the 11/18 report).
- tests/fantasy_push.py (21): asked once per Sleeper league of a reachable reader; a starter since benched no longer counts; one since
  moved into the lineup does, with today's bench; Sleeper down or a stranger's roster keeps the saved lineup. tsc baseline unchanged.
- OWNER: paste the file again and deploy. Until he does, the deployed function simply ignores the ids.
- Same publish: build_builder.py marks the house-slip pool (`sp: 1`, chip "Sweep pool", also shown by "Model's Best only"): -130 to
  -199, a short-priced tier pick or the raw model 8+ over (passing only as a tier pick), no red flag, real role, one rung per player
  and market. PROMO_DESK.md rule 3 points the desk at it. Two legs on Wednesday's board. tests/calib_floor.py (26).

## 11/18, 2:20-3:15 PM CT: the pages left alone are tightened, and the Trade page gets its all-leagues line (owner 2:19 PM)

- Owner: "Slip alerts is good to go" - the function with `freshRosters()` is deployed, on his word. First real check stays Saturday 7:05 PM.
- "Tighten all of those you listed", phones only (760px and under), nothing removed, wide screens untouched. Lengths in phone screens,
  measured laid out in full: Boards 11.3 -> 4.9, builder 7.7 -> 5.4, Home 7.5 -> 5.0, Guide 8.3 -> 3.5, How 5.3 -> 2.4, Privacy
  6.9 -> 1.9, Terms 5.4 -> 2.3, Responsible gambling 3.6 -> 2.5, Survivor 4.8 -> 3.9.
  - Shared script (build_site.py APP_JS, so it reaches template pages too): `foldBoards()` - a game card keeps its header and
    confidence line, "Show the game" opens the rest, a #GAME link arrives open, a share picture is drawn opened; `foldDoc()` - Guide,
    How and the legal pages fold under their h2 titles (first section open, except on legal pages where the opening summary stays
    above the titles), "Open all sections", a #section link arrives open; `homeTabs()` - Model's Best / Best parlay / News / Record
    under one tab row on the home page (bsTabs, key bs_tab_home).
  - build_builder.py: on a phone only the next game and an opened game show the price grid; the others show a "Game lines" row
    (`openL`, class `glz`).
  - build_survivor.py: tables over ten rows show eight until "Show all N rows" (`capTables`, kept across re-draws); the long
    footnote sits under "How the win chances are made".
  - tests/page_tight.py (49), in the pre-publish set.
- Trade page, every league on one line (`allTrade()` in build_trade.py): "Push in 5 · hold in 4 · sell in 5" and the biggest week;
  opened, every league with its verdict, odds and swing, biggest week first; a tap opens that league. The read starts once the first
  league is on screen (the same per-league playoff-odds read the league list makes). The card's styles moved to fantasy_nav.py so both
  pages share them. tests/fantasy_nav.py (137).

## 11/18, 4:00-4:45 PM CT: one player in every league - "Find a player" on the Trade page (owner 4:00 PM)

- Owner: "Can we make it so I can look for a player and see who I should attach in a trade for each league? For example I had someone
  reach out that they wanted to trade me Jaxon Smith Ngigba in League of Ordinary Gentleman. I want to be able to see which players I
  could send him easily."
- A fourth tab on /trade/, "Find a player" (`{id:'find'}`; `/trade/#find` opens it, `/trade/#find=Name` opens it on that player; the
  player is kept for the visit in sessionStorage `bs_trade_find`). Type a name (initials work: "jsn") and every league on the account
  is read:
  - `offersFor(l, c, pm, p)` values him in THAT league's format (`inFormat()` sets the toggles, recomputes, reads plain numbers and puts
    the on-screen format back - nothing inside waits), finds the roster holding him, and packages the reader's own valued players
    (plus, in a dynasty league where Sleeper said who holds what, the rookie picks he holds - `bsOutlook.ownPicks`, a first tiered by
    today's standings) into offers: one for one at 90-112% of his value, two for one at 98-125% (centre 110%), three for one at
    106-136% (centre 120%) - `FAIR`. The side getting the best player pays for the roster spot; FantasyCalc's own calculator adds a
    value adjustment for the same reason. In a two- or three-piece offer no piece is worth as much as the player (`CAP`, 97%), and the
    third piece is under 35% of him.
  - Each offer carries both starting lineups before and after (`bsOutlook.lineup`, the model's points a week). Order: the reader's
    lineup change, plus the other lineup's change (weight 0.8 in redraft, 0.3 in dynasty, capped -10..+4), minus distance from the
    centre of its band, minus a little per extra piece, plus a little for a position that roster is thin at. Four at most; no main
    piece in more than two; no two offers sharing two pieces.
  - Leagues where another roster has him are rows (the league on screen opens by itself; a tap opens another); "On your roster in:",
    "Free agent in:" are one line each. "Open in the calculator" switches the page to that league and loads both sides.
  - Sleeper calls: rosters come from the all-leagues read when it has run (`leagueChip` seeds `FP.cache`, ten minutes); names and
    traded picks are asked only for a league where another roster has him.
- The calculator's headline now says who GIVES more ("Side A gives 9% more", then "Side B comes out ahead"). It read "Side A wins by
  9%" when Side A's pile was the bigger one - under the "Side A gives" headings that is the side coming out behind. Told the owner.
- Four tabs on a phone: `#tcTabs .tab` is tighter at 480px and under so the row does not slide (fits 360-390px).
- tests/trade_find.py (95, in the pre-publish set): four mocked leagues (redraft, dynasty superflex TE-premium with traded picks, one
  where the reader has him, one where nobody does), both themes; every value against the calculator's own numbers in that league's
  format, lineup numbers against a lineup worked out in the test, picks held vs traded away, Sleeper calls counted, the on-screen
  format restored, the calculator hand-off, no account, the link, a reload. tests/fantasy_nav.py: four tabs.
- Limits: mocked Sleeper leagues only (the sandbox cannot reach Sleeper). Not built: the reverse ("what could I get for a player I
  have"), offers where the other manager adds a piece back, IDP / kickers / defenses (not valued on the page).
- Asked the same hour: "Did we blend keep cut trade into our trade calculator?" - no: KeepTradeCut's terms forbid it; the blend is
  FantasyCalc at 70% (MKT_W), 353 of 511 players carrying a market value in the 3:05 PM build. Offered to draft a permission request.
- Same publish, found by the pre-publish set: "Lines to check" (stale_lines.py, on the home page and the News desk) had grown to 1.6
  phone screens on Wednesday's injury reports (14-22 teammate lines) and both pages failed their length checks. More than six lines:
  the first two players and two lines each show, and one button shows the rest ("Show all 14 lines (3 players out)" / "Show fewer").
  Home 6.9 -> 6.0 screens, News 5.1 -> 4.2. tests/page_tight.py checks it when the block is long (55 checks on such a day); its home
  length limit is 6.5 now - the block comes and goes with the news.
- The block's own line read "Ruled out since our last FanDuel price pull (Wed 6:34 AM CT)" at 4:40 PM. That is the normal cadence,
  not a fault: FanDuel player props are pulled into the sheet once a day (about 6:30 AM CT; game lines every six hours - see the
  11/10 note "What the hourly run can and cannot freshen"). Midweek practice reports land after it, which is what this block is
  for. Suggested to the owner 11/18: a second props pull mid-afternoon Wednesday to Saturday (his Apps Script trigger, his credits).

## 11/18, 4:45-5:15 PM CT: Boards and the builder on a phone, second pass (owner 3:52 PM)

- Owner, 45 minutes after the 3:08 PM tightening went out: "I don't really like how you have packaged and condensed the parlay builder
  and the matchup boards. I think we can make it make a little more sense."
- What was wrong with the first pass, looking at it on a phone:
  - Boards: a card was its header, the confidence line and one row, "Show the game". That row hid the kickoff, the best parlay and
    the card's own two buttons (Game Script / Projections) behind a third button with a vague name; opened, "Hide the game" sat in
    the middle of the card. The same script had also folded the weekly Receipts' game cards (it matched any card with a kickoff
    line) - not asked for, not noticed until now.
  - Builder: two different openers on one card (a pill inside the header for the player legs, a "Game lines" row under it), and the
    first game behaved differently from the rest (its price grid was open).
- Now (phones, 760px and under; wide screens untouched):
  - Boards (`tidyBoards()` in build_site.py APP_JS, class `bstidy`, board cards only = cards with a `.bestslip`): the scorecard is
    whole again - teams and projected score, the kickoff line, Game Script / Projections, the confidence line, the best parlay with
    its legs. Only fine print folds: the stadium, calm-weather detail and a spread / total that repeats the header leave the kickoff
    line (`.bsx`; back when the board is opened); the best parlay's title row is always title / price / "+ Add" (the title wraps
    inside its own box); the parlay's numbers are one line ending in "Show the work", which opens the full numbers and the leg-by-leg
    reasoning ("Show the work" was a bold label over text that was always showing). A share picture (`.bsshoot`, `.storyframe`) is
    drawn with everything in it, as before. `contain-intrinsic-size:auto 520px` on a tidy card (the template's 900px guess made the
    page look fourteen screens long before the cards rendered).
  - Builder (build_builder.py `one()`): every game card carries the same two buttons under its header, `.gsw` > `.gswb` - "Game
    lines" (`openL`) and "Player legs" (`openG`, same as tapping the header) - in the look of the boards' Game Script / Projections
    pair. Each opens its own part of the card, lines above legs. No first-game exception. A game with no player props posted has
    the one button. The header's pill is hidden on phones.
- Lengths, 13 games, phone screens measured laid out in full: Boards 11.3 (before today) -> 4.9 (first pass) -> 9.5; a card 710px ->
  524px. Builder 7.7 -> 5.4 -> 5.4. The boards gave back most of the first pass's saving on purpose: the stub was short because
  it hid the page. Next lever if the owner wants it shorter: each best parlay's legs on one line until tapped (about 6.5 screens).
- tests/page_tight.py (68): both pages re-written for the second pass; receipts cards are not folded or trimmed.

## 11/18, 5:20-5:45 PM CT: the Promo Studio goes onto the site (owner 4:09 PM: "Can you do the promo studio")

- What it is: the owner's tool at /studio/ for promo graphics - pick one of the week's promos (or type legs by hand) and it puts the
  exact legs and FanDuel prices on a 1080 canvas, either as a slip card dropped onto art he made in ChatGPT ("Slip on my art", drag
  to place) or as a full BetSweep poster (square, 4:5, story); it also writes the ChatGPT prompt. Built 11/3 on the site repo's
  `promo-studio` branch and never published. It lives in the generators now: assets/studio (one page, seven fonts with their
  licences); build_site.py copies it to site/studio. It is `noindex`, out of the sitemap, and not in the menu or on "Every page".
- It reads promos from the home page in the browser (`fetch('/')`, `parsePromos`: `article.promo`, `ul.pl li[data-who][data-mk]`,
  `.o`, `.mp`, `.pf .big`, `.cap`, `.slink code`). home.promo_card still writes exactly that. New: each leg carries `data-at` (the
  game as the schedule has it, "IND @ HOU") - the studio had been drawing a game id ("HOU-IND", alphabetical) as away-at-home.
- Changed before publishing, and why: the slip was drawn as a look-alike of a sportsbook's betslip (white card, blue header, yellow
  "SGP" chip, the book's market names, "TOTAL WAGER / TOTAL PAYOUT"), and the "ChatGPT draws it all" prompt asked for the same. A
  graphic like that reads as a screenshot of a bet placed at that book. It is BetSweep's own card now - cream, navy header with the
  wordmark, red marks; plain leg words; "EXAMPLE STAKE / WOULD PAY"; a last line "BETSWEEP PICK · FANDUEL PRICES WHEN POSTED ·
  PRICES MOVE" - and the prompt asks for that card and says it is not a sportsbook's betslip. Told the owner. (His standing ask from
  October was one BetSweep slip look everywhere; this follows it.)
- tests/studio.py (26, in the pre-publish set): a home page whose promo cards are made by home.promo_card itself (so markup drift
  fails here); every string the canvas paints is recorded and checked (legs, prices, boost arithmetic, game orientation, the example
  and source lines, no sportsbook wording); pixel colours of the card; three poster sizes; the PNG download; the two prompts; a
  multi-game promo; `?p=w11-5`; today's real home page (no promos up: says so, legs by hand still draw); a phone.
- Week 11 has no promos posted yet (Wednesday), so the live page will say "No promoted bets found" until Thursday's are up.

## 11/19, 1:05-1:30 AM CT: a Wednesday rule-out the model did not have until the owner asked (owner 1:06 AM: "Woody marks is out. We need to adjust.")

- What the owner saw: David Montgomery back, Woody Marks ruled out, FanDuel already pricing Montgomery as the lead back - and the
  site still projecting Marks at 44.5 rushing yards with Montgomery behind him at 30.
- Why: the hourly reprice only FLAGS injury news (the news desk, "Lines to check", the OUT chips) and PROPOSES availability rows
  (`out/news_rows.json`, `out/depth_rows.json`). Nothing in the hourly job writes 'AUTO - Weekly Availability'; only a model run
  (Tue/Thu/Sat/Sun) or a session does. The rule-out came in the ESPN team report Wed 11/18 2:51 PM - after Tuesday's run, before
  Thursday's - and the session read that line at about 4:40 PM Wednesday and went on with page work. That second part is the
  session's miss. RULE FROM NOW ON: when a session sees a "ruled out / placed on IR" line for a game inside 48 hours, it writes the
  row (Step 2a rules), re-mirrors and republishes before anything else.
- Sheet writes (Step 2a wording rules; every row read back; `avail_check.py`: 79 rows reach the model, 0 ignored): rows 52 and 66
  upgraded QUESTIONABLE -> OUT (Will Mallory IND TE, Marvin Harrison Jr. HOU WR); new OUT rows for Woody Marks HOU RB (concussion),
  Brevin Jordan HOU TE and Jake Ferguson DAL TE; Jawhar Jordan HOU RB set to Forced Role "DEPTH / CONTEXT" - he is not on ESPN's
  Texans RB chart and the fill-in logic had handed him 38 rushing yards.
- After the projection tabs recalculated: Montgomery RB1 44.4 rush / 16.3 rec yds, 0.31 rush TD; Demercado 22.0 / 8.7; Marks and
  Jordan 0. Builder: Montgomery rushing 45.8 vs FanDuel's 50.5, anytime TD 51% vs 56% implied. Game numbers unchanged (HOU 28-15.5).
  `voice/voice-w11.json` HOU-IND rewritten (pick Dell 30+ receiving yards). Published 1:27 AM (site 45f5152a). MASTER row 615.
- Structural limit this exposed: a back who steps into the lead role gets his carries from season averages and the fill-in share
  ("last-4 carries/targets: diagnostic only"), so the number runs low (consensus had Marks at 66.9 when we had 44.5; FanDuel has
  Montgomery at 50.5 against our 45.8). Tuesday research item, with the consensus-as-market test.
- Not built, waiting on the owner's yes: the hourly job writing official rule-outs into the availability tab itself (ESPN "ruled
  out" / IR wording, game not kicked off, never a downgrade, never an "OWNER" row), then re-mirroring before it reprices. It changes
  the automation on main and writes his sheet, so a session does not do it unasked.
- Left for Thursday's scheduled run on purpose: Jordan Addison (thumb surgery, no stated absence), Sunday's questionables, and the
  stale QB role proposals (Cousins / Mayfield / Milton).

## 11/19, 1:35-2:40 AM CT: passing TDs become a real market - the ladder, a market-anchored price, and why nobody could find them (owner 1:08 AM: "Can we have passing tds and alternate passing tds available as betting options. Honestly any legs we don't currently offer that we could offer would be great to add")

- What was true before. Passing TDs legs had been on the board since 11/5 (19 this week, one rung a quarterback), but:
  (a) the market was on NO list the pages draw from - not the builder's market filter, not a quarterback's "All props" (MORD), not the
  other-markets arrows (MO), not the player pages (MORDER / PGROUPS). They could only be met by search or by sorting the whole board.
  (b) Their leg details read "0 of his last 0", no picture, "No defensive game log": the legs carried "sk": "nm", a key no game log has.
  (c) Only FanDuel's main rung was pulled. (d) The price was no better than a base rate (below).
- What FanDuel sends through The Odds API - facts, from b/books.json as published 11/8, 11/12, 11/13, 11/15 and 11/16 and from the
  11/18 links tab: `player_pass_tds` = the main rung only; `player_pass_interceptions`, `player_pass_completions` (+ alternate) and
  `player_rush_attempts` have NEVER returned one FanDuel row (DraftKings and Hard Rock return them). The main request had paid about
  4 credits a game, every refresh since 11/5, for DraftKings / Hard Rock rows no leg could use. So "more legs" is bounded by the feed,
  and which of the other 50-odd market keys FanDuel posts through it was unknown - hence the one-time check below.
- FanDuelOdds.gs v2026-11-19 (the owner pastes it; nothing to re-install):
  - `player_pass_tds_alternate` joins the main request -> every quarterback's 1+ / 2+ / 3+ / 4+ rungs in 'AUTO - FanDuel Links' (the
    site prices any rung). A 422 from the feed drops the new key for that pull instead of failing every game (FDO_NEW_MAIN_KEYS).
  - The four dead keys leave the main request. Net about 3 credits a game LESS (harness week: 3,160 -> 2,686 credits).
  - EXTRA_MARKETS: those four, their alternates and every other NFL player key in the Odds API list. The keys switched on are asked
    of FanDuel ALONE in a second request (a market FanDuel does not post costs nothing), only for a game inside 40 hours whose extra
    rows are 20+ hours old (5+ on game day); in between the rows stay in the links tab with their own stamp (`keepExtra`). Skipped when
    the credits left would not cover the fixed schedule. A menu refresh always asks.
  - 'AUTO - Market Coverage' (new tab, not mirrored - read it with the Sheets connector): one row a key. Column C "Pull" = Y is the
    switch, so a market can be turned on from the sheet with no new paste - only switch on what the site prices (column D). The first
    refresh with a game inside 12 hours runs a one-time CHECK of every listed key (player and game markets) against FanDuel for that one
    game and writes rows / players / a sample per key (menu: "Check which other FanDuel markets exist"; property BS_MARKET_CHECK). A key
    the API rejects is isolated by halving the request and marked "error 422".
  - CREDITS_PER_GAME 21 -> 18, CORE_PER_DAY 580 -> 520 (re-measure from the credits-left readings after a week).
  - tests/gs/harness.js: the fake feed now answers as FanDuel really does; 49 checks against tests/gs/FanDuelOdds-2026-11-10.gs.txt (the
    file being replaced). RUN IT before handing over any new version.
- The price (research/ptd_model.py -> research/ptd_model.json, read by newmkt.py). Checked rung by rung on 2025-26 (570 QB games),
  the 11/5 number (shrunk season average, Poisson) was no better than the league base rate at 1+, 2+ or 4+, and Poisson was the wrong
  shape: TD counts are under-dispersed (variance 1.36, mean 1.51). Now: mean = exp(-3.614 + 1.253 ln(the market's implied team points)
  + 0.343 ln(his average shrunk k = 10 toward the league)), count ~ Binomial(8, mean / 8). Test seasons, Brier against the base rate:
  -0.005 at 1+, -0.014 at 2+, -0.010 at 3+, -0.001 at 4+; calibrated by thirds at every rung. The team total carries nearly all of it
  (a TDs-per-implied-point term for run-heavy quarterbacks added nothing). Still no leg on a quarterback with fewer than two 15-attempt
  games: on those the fit says 72% for 1+ and 58% happen. The builder passes the game's `pa` / `pb` (FanDuel's implied team points).
  This week the raw number sits a mean 3.9 points from FanDuel's price over the 19 main rungs.
- The site: build_builder.py - NEW_SK / NEW_COL (each newer market reads its own game-log column: ptd, cmp, int for quarterbacks'
  15+ attempt games, att for backs), the same keys in DEF / LG, `rank_col` gives Passing TDs the "QB Pass TD" ranks (matchup pill), MO
  and MORD list the newer markets, #fMarket lists Passing TDs and appends by itself any player market on the board it does not know,
  `lms()` writes "pass TDs" / "INTs" in sentences. build_players.py - the newer markets in MORDER / PGROUPS / `_stat`, counted over
  starts (`_games_for`), a Passing TDs chart for quarterbacks; plydata.py adds "cmp".
- tests/new_markets.py (55, in the pre-publish set): the pricer's formula and rules on a made-up season; the built board; the phone
  builder (light and dark) with a full ladder put on each quarterback - filter, All props, slider, picture, defence block, slip, Search;
  a quarterback's player page.
- Published 2:27 AM CT (site 96dba206; pre-publish set 33 of 33; new_markets, builder_fold and page_tight re-run on the published copy).
  MASTER row 616. The owner's copy of the script: owner_send/FanDuelOdds-2026-11-19.txt (identical to FanDuelOdds.gs). A check-in is set for
  11:05 AM to read 'AUTO - Market Coverage'; if the tab is not there the script has not been pasted yet.
- NEXT, once the coverage check has run (the owner must paste first): price and switch on what FanDuel really posts (candidates: pass
  attempts, longest completion / rush, pass + rush yards, kicking points, tackles + assists). Each needs a tested pricer in newmkt.py,
  a game-log column (NEW_COL), live tracking (build_live statFor) and grading (home.py, social.py, social_grade.py, grade_promos.py)
  before its switch goes to Y. Team totals / first-half lines are game markets: FanDuelGameLines.gs and gamelines.py, another paste.
  Owner decision, not taken: offering completions / interceptions / rush attempts at DraftKings' price (FanDuel's is not in the feed)
  would mean pulling those keys from all three books again, about 600 credits a week.

## 11/19, 9:35-9:45 AM CT: the hourly job now writes official rule-outs itself (owner 9:35 AM: "Yes on the hourly job")

- What runs: `.github/avail_auto.py` on MAIN (beside sheets_pull.py), as a step of the sheet-mirror job (:05 and :35) BEFORE the pull, so
  the mirror that follows holds the recalculated projection tabs and the next reprice prices from them. The reprice job itself still
  never writes the sheet.
- What it writes: OUT in 'AUTO - Weekly Availability' for a player on a projection tab (exact name + team) whose game this week has not
  kicked off, when the feeds' ESPN team report (injuries.json) lists him Injured Reserve / suspended / PUP / NFI, or Out AND the report
  line itself states the absence ("ruled out", "will not play", "won't be available for Sunday's game", "placed on injured reserve").
  ESPN's Out tag alone writes nothing (11/19 dry run left Jordan Addison, Kyler Murray, Josh Jacobs, Sam Darnold, Zachariah Branch to a
  session). Only E, J, K, L change on an existing row; the old status and reason are kept at the end of J. Its rows start
  "AUTO HOURLY:".
- What it never does: touch a row whose J starts "OWNER"; lower a status a person or a model run wrote; delete a row. It lifts only its
  OWN rows (ESPN now Questionable / Doubtful -> QUESTIONABLE, Active -> blank) before kickoff. More than 10 changes in one run, a stale
  or short ESPN feed, or an unexpected header = it writes nothing and says why.
- Where to look: `in/AVAIL_AUTO.json` in the sheet mirror (ran, status, wrote, held, can_write). First real run 9:41 AM: "nothing to
  write", can_write true (an empty update was accepted, so the service account can edit). It can never fail the mirror job.
- Sessions: treat an "AUTO HOURLY:" row like a NEWS DESK row - an official designation or the owner replaces it. Depth-chart demotions
  (the Jawhar Jordan case) and wire-only reports are still proposals for a session. `python3 .github/avail_auto.py --selftest` (11
  cases) before changing its wording rules. To turn it off: remove the step from sheet-mirror.yml.

## 11/19 afternoon: script fix, tonight's two slips, house-slip logos, team avatars
- **FanDuelOdds v2026-11-19b** (sent 10:40 AM): the first paste hit Apps Script's 6-minute limit (stopped after the links tab). Sorts use a
  plain compare (`cmpS_`) instead of localeCompare, and the market coverage check runs last, once, inside a 60 s / 30 call budget. Whether
  19b is installed and whether the coverage check has run are still unconfirmed - read 'AUTO - Market Coverage' after the 6 PM refresh.
- **Slip rules the owner added (11/19):** do not assume a blowout in a prime-time divisional game and include underdog-side legs; know the
  roster changes behind a player's numbers before citing history (Jones passing after Allen and Downs were traded); no slip where
  everything hangs on game lines.
- **Promos:** w11-1 Thursday Night Thievery (six legs, his Montgomery hunch at the core; FanDuel quote for column E still not received) and
  w11-2 Daily Sweep: Low Bar (his own five-leg FanDuel slip, +484; weak leg flagged: Burks 10+ rec yds, 2 of 8). Always poll the mirror
  for the new promo row before dispatching the reprice - a dispatch can lag several minutes.
- **House slips on Social** (owner 2:19 PM): the red "BS" disc is now the circle logo (`/logo.png`) and the name is the wordmark image
  (cream on dark, ink on light, same two selectors as the theme switch). No new image files - both were already shipped.
- **Team avatars** (owner 2:34 PM): the picker has a Team row, one emoji per club (`TEAMS` in social.py), 48 emoji in all. The database
  checks the emoji against a fixed list, so `sql/social_v5.sql` (replaces `feed_profile_set` only; no secret; safe twice) must be run by
  the owner. Until then a team pick answers "Team avatars are being switched on." Tested on a throwaway Postgres: installs twice, all 48
  accepted, an off-list emoji refused. `meBtn()` now also runs the moment the account event fires.
- **Open:** tests/page_tight fails on home (8.4 phone screens against 6.5) on the published site too - two long promo cards today. Not
  caused by these changes; look at folding promo captions on Today.
- **Hunches:** chat-only first pass so far (scratch in /tmp/hunch, not kept). The site feature is not built.

## 11/19 3:25 PM: one identity - the Social profile lives on My BetSweep (owner: "My BetSweep and my profile on the social page need to combine")
- **My BetSweep** opens on a profile card (`#mep`, `MEP_JS` / `_mep_js()` in account.py, styles at the top of ME_CSS): avatar, @username,
  posted record and followers, **Edit profile** (the same username / colour / avatar / team editor) and **My posted slips**
  (`/social/#u=<id>`). The avatar lists are read out of social.py at build time, so the two editors cannot drift.
- **Header pill:** shows the chosen emoji, else the username's initial (account.js `prof()`, `profLoad()`, `bsAccount.setProfile`).
  The profile is remembered per browser in `bs_prof` (not a synced key) and re-read at most every 10 minutes per tab.
- **Social:** the bar button is now **My slips** (opens your posted slips, as before). Editing there still works and updates the header.
- Do not put a `//` comment in the middle of a one-line script statement in social.py - it cut off the rest of the line once today.
- tests/me_profile.py (21 checks; the real account script against a stand-in client) is in the full set (34 tests).

## 11/19 4:45 PM: Waivers tab - rostered players and stale projections (owner screenshot)
- **Kenneth Walker shown as a free agent:** Sleeper carries a second, unsigned "Kenneth Walker"; `modelFor()`'s last fallback matched him
  to the model's back by name alone. Both free-agent lists (Waivers tab and the all-leagues pickup line) now skip a model player some
  roster already holds (`taken`), any Sleeper entry with no team or another position, and a second entry for the same model player.
- **Michael Carter 9.3:** the sheet projected him off one game (Week 7: 3 carries) though Tennessee has played since without him. Week 10
  check: the 13 RB/WR/TE with one or two logged games were projected 6.4 each and scored 2.6; eight never played. build_team.py now adds
  `gn` / `lw` / `idle` from the game log; `stale()` (two games or fewer AND two or more team games missed since) keeps him off the
  waiver lists unless Sleeper managers are adding him today; `thinTag()` marks "last played Wk N" / "N games" wherever he still shows.
  **The projection itself is unchanged** - this is a sheet-model weakness (no recency in LOW SAMPLE projections) to fix at the source.
- tests/waiver_truth.py (5 checks) joins the full set (35 tests).
- **Open:** tests/fantasy_nav fails 4 checks on today's data with or without this change (stand-in league: "L. Burden III (out)" while the
  sheet has him Questionable). Not looked into yet.
