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

