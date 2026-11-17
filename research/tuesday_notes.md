# Notes for the Tuesday run (written 11/16 after the Monday rebuild)

- **Closing lines, Week 10 - gap in the sheet.** 'AUTO - Closing Lines' has no Week 10 rows for the Sunday noon games or DET-NE
  (Munich, 8:30 AM CT). Week 9 had 652 rows for the noon kickoffs. It does hold 107 BAL/LAC rows "captured" Sunday 9 AM (pulled 6 AM)
  for Monday night's 7:15 PM game. So Week 10 closing-price grading covers TNF (128 rows), the 3:05 / 3:25 window (224 + 98), SNF (120)
  and whatever is captured for MNF - not the nine early games. Look at the capture script before grading; say so in the report.
- **Leg Board in the sheet** shows Thursday's game (Colts @ Texans, Week 11) with Week 10 projections until the week rolls. The site
  drops those rows since 11/16 (weekgate.py); the sheet tab itself still shows them.
- **Game-card best parlay**: tonight's (BAL-LAC) is two game lines (Under 38.5 + Chargers ML, EV -3%): under the new rules no slip with a
  player leg beat it. Check the full Week 11 cards: player legs or fallbacks? If most are fallbacks the bar is
  too tight for a card that is supposed to have a pick, or the card should say "nothing clears the bar" instead.
- Shadow list after the gate: 1 single (Herbert 225+ pass yds +158), 0 pairs for MNF. The 14:13Z copy of data/learned-w10-1116.json
  had three wrong-week singles (Jones, Schultz, Stroud) - overwritten at 14:27Z; do not grade those.
- **Freeze the pre-kickoff best parlay**: done 11/16 (RUNBOOK); on Tuesday check that Week 10's frozen cards graded themselves.
- **Stale status flags.** Monday's BAL-LAC card carried "Justin Herbert is questionable" as a risk flag, dated Nov 7, though he had been
  off the injury report since Nov 12. That one flag fed the card's Low confidence and the risk tag on his legs. Find where the status
  comes from, how old a status may be before it is dropped, and whether a later "full participant / removed from the report" row
  clears it. Until then read the flag's date before trusting it.
- **Best-rung star: which chance?** The builder's "best rung +N% EV" star uses the model's shown chance. On the graded chance (how
  often legs like it have really hit this season) almost no rung is +EV. Decide which one the star should use; if graded, most ladders
  lose the star, which may be the honest answer. (Separate from the 11/16 bug where every leg wore a wrong star - fixed.)
- **Today promo cards say "PREGAME"** as fixed text when live scores cannot load; after kickoff with no data they still say it. Small.
- **Finished cards in the builder's fold are still tall** (full projection block each). If people open the fold, shorten them.
- **Scheduled jobs barely ran (see RUNBOOK, 11/16).** GitHub started 3 of about 22 inactive checks on Sunday 11/15. When grading
  Week 10, check whether any posted leg was on a player ruled out Sunday morning whose status reached the sheet late: compare
  'AUTO - Game Day Status' write times with the 11:30 AM / 2:30 PM CT inactive lists. If the owner has run sql/github_timers.sql,
  confirm on Tuesday that the mirror, rebuild and price-moves runs now arrive on time (Actions > each workflow > run list).
- **First Social grading run (Tue 9:40 AM CT, started by the database timer).** Check Actions > social-grade: it should say
  "wrote N of N result(s)" with about 24 lost. Then open Social: profiles should show a record. If it did not run, dispatch it by
  hand (mode grade). Then build the "this week's sharps" strip only if a graded win exists.
- **Timer check.** Confirm the run lists show the mirror at :05/:35, price moves at :12/:42 and the rebuild at :20 arriving by
  dispatch since Monday 8 PM CT.
- **My BetSweep hub:** after Week 10's box file is written, open /me/ with real saved slips and check that the Week 10 bar and the
  record match the slips list underneath.
- (DONE 11/17 12:40 AM CT) The Today filing test runs again, on made-up slips (tests/home_filing.py, 36 checks, any week), and
  tests/social_feed.py takes its week from the built page. After the roll just run them; nothing to rework.
- **Slip log, Week 10 Monday:** row 57 Daily Sweep "Herbo Fully Loaded" +259 LOST (Herbert 129 passing yards vs 175+, 0 passing
  TDs vs 1+); row 60 Piss Missile Monday +4174 LOST, 6 of 8 (Herbert 225+ and 1+ passing TD missed). Tag: wrong script (a Chargers
  ground-game win - Hampton 105, Herbert 51 rushing and the rushing TD) with a late scratch on top (McConkey out at 5:52 PM CT,
  flagged to the owner at 6:17 PM). Every leg in both slips that did not need Herbert's arm hit.



## Added 11/17 ~2 AM CT (Live page: finished games were graded without numbers)
- Fixed and tested (RUNBOOK, same date). Check after the Week 11 roll: the Live page shows every game as not started, the game
  chips open their cards, and "Final" does not appear.
- Friday morning (the first window the old bug would have hit): open /live/ with Thursday's game final and confirm the score shows,
  slips grade, and the page made one scoreboard call and no box score call (the build's finals carry it).
- Done 2:30 AM: totals in slips follow the slip's game map on the Live page (RUNBOOK).
- Done 3 AM: earlier weeks' saved records are re-graded once from /data/box-w<W>.json (RUNBOOK). After the Week 11 roll, check
  that /data/box-w10.json exists and that a Week 10 record saved by the bug is corrected on the first visit to Live.
- Still to do: (3) count return touchdowns for anytime-TD legs in both graders;
  (4) show an inactive player's legs as void as soon as the inactives are out (the "What changed" feed has them), not only after
  the snap counts publish.
- tests/deepdive_pages.py (older, needs a server on 8802): its "boost 25% x3: a slip is shown" check fails on a finished week
  (nothing left to boost) - 31 of 32 on 11/17 2:30 AM; make it week-independent like the others. The Social page's own grader calls
  a First TD leg dead when a finished game's box score did not load - require the box before settling it.

## Added 11/17 ~3:15 AM CT
- Live: an inactive player's leg is void from the inactives list (RUNBOOK). Thursday night: about 75 minutes before kickoff, open
  /live/ with a slip that holds a leg on someone from the inactives list and confirm it reads Void; confirm ESPN's kick/punt return
  tables carry a touchdown key the page reads (phone network log, or the first return touchdown).
- After Tuesday's grading: Today, Season and Receipts must show the same Daily Sweep record (Season still shows last Tuesday's
  "1-1 · Wk 9 1-1"; the tab says 1-0 with Sunday's and Monday's Sweeps ungraded - both lost).
- The pre-publish set is longer now (RUNBOOK "the local page crawl had been opening nothing"): run tests/local_gate.py, not
  site_crawl.py on its own.
- Next with the inactives feed: the builder / Today / boards should not offer a leg on a player who is on the inactives list.

## Added 11/17, 7-8:30 AM CT (before the roll went out; RUNBOOK has each item)
- DONE: availfix.py (the official report outranks a desk Questionable); the ruled-out-player pass over every page
  (tests/inactive_block.py, with a correction of the 3:15 AM note); the news desk's other-man / mid-game misreads; the Model's
  Best first screen; the builder's chip order follows the clock.
- **Waiting on the owner - the ESPN mirror timer.** `sql/github_timers.sql` has a twelfth job (feeds.yml every ten minutes); he
  has to run the file again. Until then the mirror is hours old outside game windows (Mon 11/16: nothing 10:57 AM - 5:00 PM CT).
  A workflow-file route was written and not pushed (the session may not push workflow changes to main unasked).
- **Waiting on the owner - the game-card "Best parlay".** Week 11 Tuesday: 12 of 13 cards are two game lines at about -6% EV;
  only BUF-MIA has a player leg. The 11/15 rule (model 8+ over the price, nothing at -200 or shorter) leaves 9 legs from 2
  players on the whole board (Thursday's game: 0 of 181 priced legs; 13 more legs from 6 players sit 4-8 points over).
  Proposed: when no slip with a player leg clears the bar the card says so instead of showing a losing pair of game lines.
- **Waiting on the owner - long-shot touchdowns in Model's Best.** The plus-money tier's second pick on Week 11 is DJ Giddens
  anytime TD +3300 (model 11%, price 3%; he plays 7% of snaps). Graded from the picks archive, Weeks 9-10: plus-tier TD legs
  longer than +600 went 2 for 41 where the model said about 1 in 6; other plus-money legs at +150 to +300 hit 36% against 33%
  priced (111 legs). Another 50 of 259 archived plus-tier legs had no stat line at all. Proposed: touchdowns longer than +600
  leave the tier unless the player has a real role (25%+ of snaps).
- gameday.yml failed once Monday 6:10 PM CT on a read timeout (the next run, 36 minutes later, was fine): give its fetch a retry.
- Thursday: watch the first availfix corrections (IND / HOU final report is Wednesday); the session's Step 2a-ii now runs it.
- The health check's "ARI QB0" all of Week 10: Minshew was OUT and Carson Beck, a rookie with no game log, never got the
  replacement-starter row Step 2a asks for. He is on the QB tab now (one game). Check Week 11's health check for ARI.

## State at 8:50 AM CT, 11/17 (after the roll)
- Roll out and checked: main 782668e3 (the morning run, 8:16 AM), then 43dad045 (my publish, 8:32 AM, gen 1c0428ee). The whole
  test set passes on the published copy; page gate 525 pages, 0 problems. Daily Sweep 1-2, +1.0u on Today, Season and the
  Week 10 receipt. Promos Week 10: 1 hit, 8 missed. data/box-w10.json in.
- reprice.live_data fixed (it would have skipped every scheduled rebuild after the roll) - **check the 9:20 AM CT run did not
  end with exit 3** (Actions > reprice > the 15:20Z run; "skipped (exit 3)" in the Build step would mean it did).
- **9:40 AM CT: first real Social grading run** - Actions > social-grade: "wrote 24 of 24" expected (24 lost).
- Slip log Week 10 done (rows 9-60): 7 won, 45 lost. Why-it-lost tags are in a new column K: wrong script 20, thin role 14,
  bad luck 11. Six rows the grader left open were hand-graded LOST (19, 35, 37, 43, 49, 59).
- grade_promos.py cannot grade "Passing TDs 1+" ("not gradable here" on both Monday slips; they were Missed on other legs
  anyway). Add the market to slipgrade.py before it decides a grade.
- Still to do from the 11/15 check-in list: flag_grade / honest / learned with Week 10 (the morning run did the flag report
  card, context grade and live grade - research/*_w10.txt); the 10 flags that moved the most players; closing-price share for
  Week 10; the FanDuel same-game discount table; tap targets on /benefits and /usage.

