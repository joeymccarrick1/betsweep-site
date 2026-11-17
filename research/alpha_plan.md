# BetSweep to "alpha" - the build plan (owner 11/16: "Do a thorough addition of all of this ... make upgrades to each page just like you did with social")

Everything ships from gen-overrides with the next rebuild that passes the publish gates. Check each step on a phone-sized screen
(Playwright, 390x844, light AND dark - the owner uses dark) and re-run the 41-page sweep (no JS errors, no sideways scroll) before committing.
Read this file first when the work is picked up again.

## Found while starting (correct earlier statements)
- A dark theme already exists (`bs_theme` in localStorage -> `data-theme`; colors are CSS variables: --bg --card --ink --mute --line --red
  --display --good --bad). The header stays cream in dark. New CSS must use the variables, never hex.
- The menu is already grouped (Games, Betting, Play, Players, Fantasy, Results) with one-line descriptions - item 3 is mostly done; what is
  left is naming and making sure Social / My BetSweep are easy to reach.
- Page weight after compression: Boards 1,683 KB -> 285 KB, builder data 1,601 KB -> 187 KB, home 292 -> 57. Transfer is fine; the cost
  is the size of the Boards page on screen (every game card rendered at once).

## Done
- 11/15: tab bar Today / Boards / Builder / Live / Me; graded chance on pick cards; DFS small text.
- 11/16: tab bar Today / Boards / Builder / Live / Social (owner: Social prominent, Fantasy in the menu).
- 11/16 Social step 1 (part): house slips pinned above the feed before kickoff (`social.house_html`, from out/promos.json, no database
  change; long slips fold after four legs); one-line intro with "how it works" moved to the foot; loading placeholders instead of
  "Loading..."; touch feedback on buttons and tabs. Mockup markup: research/social_mock_block.html.

- 11/16 Social step 1 DONE (gen e7309c5d, live 16:16Z): every post of the week is loaded and graded on the page; Cashed tab (winners,
  busted folded under), last week's winners + a post button when nothing is open, pinned house slips graded live through their game
  (`window.__BS_HOUSE`, HOUSE_HOURS = 12), TD double-count fixed, a player missing from the live box is never called a miss.
  tests/social_feed.py (20 checks, light + dark). Not done from step 1: nothing - "last week's winners" needs data/box-w<W-1>.json,
  which the Tuesday session writes.

- 11/16 step 2 page side DONE (v3 people features live; own username + avatar, sql/social_v4.sql sent to the owner). Left from step 2:
  the grading job that calls `feed_grade` (needs the grading secret as a repo secret - the owner adds it) and the "this week's sharps" strip.
- 11/16 step 5 DONE: "Top on Social" on Today (`social.strip_html`), "N slips on Social" / "Post a slip for this game" on Boards game
  cards (`social.cards_js`), and Social opens on one game from those links (`/social/#g=BAL-LAC`). tests/social_elsewhere.py (19 checks).
- 11/16 step 6 DONE: last-games picture on player pages and in the builder's leg details.
- 11/16 Builder (first items of the step 9 page pass): played games fold under "N games already played" (Monday page 11,900px ->
  1,900px), chip row leads with games still to come, played chips dimmed by the clock. tests/builder_fold.py (24 checks).
- 11/16 step 2 grading job BUILT: social_grade.py + the `social-grade` workflow (RUNBOOK). It runs dry until the owner adds the repo
  secret FEED_GRADE_SECRET. Left from step 2: the "this week's sharps" strip (needs graded records to exist first).
- 11/16 4:06 PM CT: a game's Social link lists every slip on that game (settled too); the Today strip reads kickoff times as text.

## Pick up here (written 11/16 4:10 PM CT)
What the real database showed (workflow `social-grade`, mode probe): both Social scripts are in, 24 posts over three weeks, ONE profile,
1 reaction, 0 tails, 0 follows. So Social has almost no audience yet - more Social features help nobody today. The pages everyone
opens are where the alpha gap is. Order for the next stretch:
1. (DONE 11/16 evening - fold live; content-visibility was already on since 11/4) **Boards (steps 9 + 11).** Same treatment the builder got: played games fold under "N games already played"; `content-visibility`
   on game cards so a phone only lays out what is near the screen; check the first screen (slate, then the next game to kick off).
2. (DONE 11/16 evening for the promo note; other intro paragraphs still to do, page by page) **Today (step 9).** The paragraph under the promos ("The other slips we post on X and Instagram ...", seven lines of small text)
   becomes one line with the rest behind an info button; the same pass on the other intro paragraphs.
3. (DONE 11/16 night: hub with open slips, record in units, profit by week; the header pill already opens it) **Me hub (step 7).** Open slips, record in units, profit calendar; profile icon in the header. account.py already grades saved
   slips from /data/box-w<W>.json - build on that.
4. **Sharps strip** only once graded records with wins exist (needs FEED_GRADE_SECRET - the owner's step - and a winner).
(DONE 11/16 8:05 PM CT: secret in and accepted; database timer running - RUNBOOK. Check the first graded run Tuesday.) Was waiting on the owner: add the repo secret FEED_GRADE_SECRET (or say "start records at Week 11" first - then add a --from-week
option to social_grade.py before he does; today's dry run would record 24 losses, 0 wins).

- 11/16 late: step 3 DONE - post from a screenshot (Social > "From a screenshot" -> builder post form, price from the picture).
  Still to check on a real phone with a real screenshot.
## Next, in this order
1. ~~Social - never empty, finished~~ (done 11/16, see above). Was: **Social - never empty, finished.** Cashed tab (finished slips where every leg hit, this week from ESPN finals, earlier weeks from
   data/box-w<W>.json); stop hiding finished slips, sort them under Cashed / Busted; live grading on the pinned house slips so they can
   stay through the games; last week's winners when nothing is open; empty state with an action.
1b. ~~Game cards keep their pre-kickoff best parlay~~ DONE 11/16 (RUNBOOK). Also done 11/16: busted promos / social slips move to Lost at once, winners to Winners. Was: **Game cards keep their pre-kickoff best parlay.** Since 11/16 a card shows no best parlay once its game kicks off (a rebuild used
   to invent a game-line one for a finished game). Better: publish `data/best-parlays-w<week>.json`, keep each game's record from the
   last build before its kickoff, show it on the card through the game and grade it when the game is final. Before Thursday's kickoff.
2. (SQL written and tested 11/16: sql/social_v3.sql, sent to the owner to run - WAITING ON THE OWNER; build the page side only after he confirms it ran) **Social - people.** SQL for the owner to run (same way as gen/social.sql): profiles (handle, avatar color), follows, tails, reactions,
   and graded results per post (result, units) written by a scheduled job. Then: avatar + handle + record in units on every post, a
   profile view with graded history, Following tab, "this week's sharps" strip.
3. **Social - post from a screenshot** (reuse slipimport.py's reader, then the existing post form).
4. **Social - reasons to return.** Push when someone tails you / a slip you tailed cashes (push/slip-alerts.ts pattern; owner deploys),
   share card when a posted slip wins (promo story PNG pattern), tail counts, one-tap reactions (no comments).
5. (DONE 11/16) 5. **Social elsewhere.** "Top on Social" strip on Today; "N slips posted" on game cards.
6. (DONE 11/16: player pages and the builder's leg details) **Player pages and leg details lead with a last-10-games picture against the line** (bars, line marker, hit count).
7. **My bets hub on /me/**: open slips, record in units, profit calendar; profile icon in the header that opens it.
8. **Design system**: one button set (primary red, secondary outline, quiet text), one card, one chip, one radius scale; content first
   (intro paragraphs to one line, help behind an info button); placeholders and designed empty / error states everywhere; avatars for people,
   team color bar + initials on legs (no league logos); lighter header, dark header in the dark theme; slide-up sheets, tab transitions.
9. **Page by page** (same treatment Social got - what is it for, what is the first thing on screen, what is the main action, what does
   it look like empty / loading / in dark): Today, Boards, Builder, Live, Player, Me, Model's Best, News, Game previews, Line shop,
   Boost finder, First TD, Either-or TDs, Teasers, Sweep my slip, Beat the model, Survivor, Fantasy (team, trade, DFS), Usage, Benefits,
   Results / Receipts / Season, Guide / How, legal pages.
10. **Other additions**: opt-in alert when the Daily Sweep posts; first-visit setup (book, team, alerts); weekly recap card per user;
    public graded record pages for BetSweep and every poster.
11. **Boards weight**: render the first few game cards, the rest as the reader scrolls.
Later, owner's call: automatic bet sync (paid outside service).

- 11/17 ~2 AM CT: step 9, Live page, first half - the page graded finished games with no numbers (winners dead, losses saved into
  the season record). Fixed with finals from the build (finals.py) and a rule that nothing is settled without real numbers; chips,
  score display, fold labels and the finished-week line fixed on the way (RUNBOOK). Next on Live: totals follow the slip's game map;
  the first screen (tools box and an empty "What changed" push the game down); pregame notes sit above the legs in a live card.
