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
- Still to do: (2) past weeks' saved records (bs_log_w<W>) may hold losses the bug wrote on a Monday night or a
  Tuesday morning - re-grade them once from /data/box-w<W>.json; (3) count return touchdowns for anytime-TD legs in both graders;
  (4) show an inactive player's legs as void as soon as the inactives are out (the "What changed" feed has them), not only after
  the snap counts publish.
- tests/deepdive_pages.py (older, needs a server on 8802): its "boost 25% x3: a slip is shown" check fails on a finished week
  (nothing left to boost) - 31 of 32 on 11/17 2:30 AM; make it week-independent like the others. The Social page's own grader calls
  a First TD leg dead when a finished game's box score did not load - require the box before settling it.
