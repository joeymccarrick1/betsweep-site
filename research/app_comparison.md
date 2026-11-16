# BetSweep against the popular betting companions (11/15, owner: "Compare the app to other popular apps ... bring BetSweep to alpha")

Sources: web search 11/15 (Action Network's own BetSync pages, FantasyLabs / RotoGrinders / VegasInsider app guides, App Store listings
for Outlier, Props.cash and Pikkit, Stat Sniper's Pikkit comparison, marlvel.ai audits). Feature claims below are theirs, not tested by us.

| App | Why people use it | Complaints | BetSweep today | Gap |
|---|---|---|---|---|
| Action Network | Bets import from linked sportsbooks with no typing; alerts when games start, score and settle; odds across books; one tap from a pick to the sportsbook | Free tier crowded with ads and sportsbook sign-up pushes; stability | Live page, screenshot import (Sweep my slip), saved slips, alerts, FanDuel one-tap links | No automatic sync (needs a paid sync provider); no single "my bets" home |
| Pikkit | Auto-sync tracking plus a social layer: follow, copy a bet into your slip, leaderboards, profit calendar in units, line shopping, closing-line value | Aggressive paywall; no manual entry | Share links, Winners, bankroll on My BetSweep | No profit calendar / units view; no following |
| Outlier, Props.cash | "Has he cleared this line?" answered in seconds with a picture; props sorted by value; trending picks to tail | Subscription price; thin sport coverage for the price | Hit rates live in flags and game logs | The hit-rate picture is not the first thing on a player page or a leg |
| OddsJam | Best price and +EV across books; closing-line tracking | Cost puts off casual bettors | Line shop, Boost finder; closing-price grading starts 11/17 | Not the headline |

What they share: four or five tabs, one job per screen, an answer in seconds, tracking that needs no typing, and a visible record.

Done 11/15 (code, ships with the next passing rebuild): phone tab bar is Today / Boards / Builder / Live / Me (was Boards / Builder /
Fantasy / Live / Social; those two stay in the menu and on /all/); pick cards on Today show the graded chance; DFS small text 10.5 -> 12px.
Phone-sized sweep after the change: 41 pages, 0 JS errors, 0 sideways scroll, new tab bar on all 41.

Next, in order: (1) player page and leg detail lead with a last-10-games picture against the line; (2) a "my bets" hub on Me - open
slips, record in units, profit calendar; (3) the 16-item menu folded into the seven groups /all/ already uses, plain names; (4) one line
of "what this page is for" and the main action at the top of every page; (5) weight - Boards is 1.6 MB of HTML, the builder's data 1.6 MB;
(6) automatic bet sync is a paid third-party service - the owner's call.
