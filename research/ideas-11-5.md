# Out-of-the-box list, 11/5 (owner: "the best app any NFL fan/bettor could use")

Checked against what exists (Today, boards, builder, live "from here", context desk, voice, pushes: brief + kickoff + slip
alerts, league card, waiver wire on the Fantasy page, model-level CLV on the season page, Social posts, receipts).
Effort: S = an evening, M = a weekend, L = a week of evenings. Impact = how much it changes a Sunday for the owner's user.

## For the bettor
1. Your CLV + "one leg away" (M, high). 'V2 - Closing Lines' already keeps the last pre-kickoff FanDuel price per line; My BetSweep
   already grades saved slips. Add per user: your price vs the close on every leg, a beat-the-close rate, and on a lost slip the one leg
   that missed and by how much ("Kelce 3 catches short"). Sunday-night push: "Your Sunday: 2 slips, 0 cashed, beat the close on 7 of 9".
   Sharp bettors judge themselves by CLV; nobody at the consumer end shows it.
2. Line moves on YOUR legs (M, high). data/price-moves.json already tracks the model's best legs hourly. Extend to every leg in a
   subscriber's saved slips: push when a leg moves 10+ cents or the line itself moves, with the model's new edge ("Allen 275+ moved
   +150 -> +120, still +4"). Steam detection for free.
3. Teaser finder (S-M, medium-high). The builder already holds FanDuel alternate spreads/totals and gamelines.py's correlation. Score
   6 / 6.5 / 7-point teasers that cross 3 and 7 against the model's win probability of the teased line; show the few that clear the
   -120 / -130 bar. A classic +EV angle no competitor of this size offers.
4. Beat the model - weekly pick'em (M, high for retention). Each user picks 5 legs from the board; the model's 5 are fixed at
   freeze; graded Tuesday with the receipts; leaderboard among friends (Social accounts exist). Free, social, weekly loop.
5. Inactives for your Sleeper roster (M, high on Sundays). feeds.py has the official inactives ~90 minutes before kickoff; the Fantasy
   page knows the roster. Store the roster server-side (opt-in) and push at 11:35 CT: "X is out - the model says start Y". Pairs with
   the new gameday Action.
6. Discord webhook (S, medium). One webhook URL in the Edge Function: the morning brief, kickoff reminders and promoted bets land in
   the owner's group chat. Bettor groups live in Discord/GroupMe.
7. Listen to the brief (S, fun). A "Listen" button on Today reading today.json's brief with the browser's own speech synthesis -
   no backend, works in the car.
8. Email digest (S-M, reach). Thursday boards + Sunday brief by email (Supabase + Resend) for the half of people who never allow
   push; doubles as the newsletter list.
9. Ask the model (M, differentiating; costs per query). A box on Today / the player page that answers from the week's JSON (projections,
   legs, context desk, closing lines): "Charbonnet 60+ rush yds?" -> the model's number, the flags, the price. Edge Function + an API key;
   natural Plus feature.
10. Public /b/ API + docs page (S). The JSON already exists; documenting it brings in the Discord bot builders and affiliates.

## For the fantasy player
11. Tuesday "buy low / sell high" (S, medium). role_rising + depth charts + SOS + the trade calculator values -> a Tuesday section on
    Today and a social post. The data is all there; it is a page section.
12. Start/sit push Saturday night for the Sleeper roster (S): the Who-should-I-start logic on the user's actual flex decisions.

## Platform / efficiency (shipped 11/5 or next)
- Shipped: shared hashed CSS/JS, self-hosted fonts, lazy html2canvas (-31% site weight, no third-party requests), no pre-rendered PNGs
  (-19 MB of binary churn per rebuild), generators from one git branch (no artifact fetch, no mirrors), RUNBOOK 149 -> 109 KB per run,
  SW network-first for hourly files, gameday Action (replaces the three Sunday Claude sessions once the sheet is shared as Editor).
- Next: squash the site repo's 793 MB history once (owner's call - one command); move the pregame snapshot tasks (Thu/Sat/Sun) to an
  Action the same way (deterministic sheet work, 3 Claude sessions/week); per-game boards and builder data (the UX-audit roadmap).
