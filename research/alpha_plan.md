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

## Next, in this order
1. ~~Social - never empty, finished~~ (done 11/16, see above). Was: **Social - never empty, finished.** Cashed tab (finished slips where every leg hit, this week from ESPN finals, earlier weeks from
   data/box-w<W>.json); stop hiding finished slips, sort them under Cashed / Busted; live grading on the pinned house slips so they can
   stay through the games; last week's winners when nothing is open; empty state with an action.
1b. ~~Game cards keep their pre-kickoff best parlay~~ DONE 11/16 (RUNBOOK). Also done 11/16: busted promos / social slips move to Lost at once, winners to Winners. Was: **Game cards keep their pre-kickoff best parlay.** Since 11/16 a card shows no best parlay once its game kicks off (a rebuild used
   to invent a game-line one for a finished game). Better: publish `data/best-parlays-w<week>.json`, keep each game's record from the
   last build before its kickoff, show it on the card through the game and grade it when the game is final. Before Thursday's kickoff.
2. **Social - people.** SQL for the owner to run (same way as gen/social.sql): profiles (handle, avatar color), follows, tails, reactions,
   and graded results per post (result, units) written by a scheduled job. Then: avatar + handle + record in units on every post, a
   profile view with graded history, Following tab, "this week's sharps" strip.
3. **Social - post from a screenshot** (reuse slipimport.py's reader, then the existing post form).
4. **Social - reasons to return.** Push when someone tails you / a slip you tailed cashes (push/slip-alerts.ts pattern; owner deploys),
   share card when a posted slip wins (promo story PNG pattern), tail counts, one-tap reactions (no comments).
5. **Social elsewhere.** "Top on Social" strip on Today; "N slips posted" on game cards.
6. **Player pages and leg details lead with a last-10-games picture against the line** (bars, line marker, hit count).
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
