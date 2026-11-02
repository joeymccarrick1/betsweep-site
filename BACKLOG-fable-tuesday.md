# Owner requests queued for Tuesday 11/3 (owner 11/1 8:19 PM: "When I get more fable credits on Tuesday I want a couple things")

1. Live game drill-down. On /live/ (and the live ticker on game cards), tapping a game opens that game's Box Score and Play-by-Play,
   with scoring plays highlighted. Data: ESPN summary (boxscore, drives/plays, scoringPlays) - browser fetch with the ESPN mirror on the
   feeds branch as fallback (add box/<event>.json and pbp to .github/feeds.py if the browser route is blocked). Mark the slip's legs inside
   the box score (who you have, how close).

2. Concept only - DO NOT push to the live site. Explore merging the Parlay Builder and the Matchup Boards into one page that is not
   confusing and is very easy to use. Owner likes the current split, so build it as a separate preview (e.g. /lab/merged/ not linked from the
   menu, or a private artifact) and show it to him for a decision.
