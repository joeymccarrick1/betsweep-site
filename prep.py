#!/usr/bin/env python3
"""prep.py <get_spreadsheet_result.json>
Turns ONE Google Sheets get_spreadsheet result (includeGridData, fields sheets.properties.title + sheets.data.rowData.values.formattedValue,
ranges in the order listed in build_boards.py) into the in/*.json dumps, and downloads the nflverse schedule if missing.
The result may contain the ranges in any order: files are assigned by sheet title."""
import json, sys, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); os.makedirs(IN, exist_ok=True)
BY_TITLE = {"2026 Matchup Boards": "boards.json", "AUTO - Defensive Stat Matchup Ranks": "ranks.json", "AUTO - Game Weather": "weather.json",
            "AUTO - Weekly Availability": "avail.json", "V2 - Game Scripts": "scripts.json", "V2 - Leg Board": "legboard.json", "V2 - Best Legs": "bestlegs.json", "AUTO - Script Multipliers": "mult.json", "AUTO - Boards Archive": "archive.json", "V2 - Boards Results Feed": "results.json", "V2 - Weekly Scorecard": "scorecard.json", "V2 - FanDuel Leg Snapshots": "legsnaps.json", "AUTO - SGP Correlations": "corr.json", "AUTO - Game Day Status": "gameday.json", "AUTO - FanDuel Links": "links.json", "AUTO - FanDuel Game Lines": "gamelines.json", "AUTO - Model Calls Archive": "calls.json", "AUTO - Player Game Log": "gamelog.json", "AUTO - QB Projections": "proj_qb.json", "AUTO - RB Projections": "proj_rb.json", "AUTO - WR Projections": "proj_wr.json", "AUTO - TE Projections": "proj_te.json", "AUTO - Kicker Projections": "proj_k.json", "AUTO - DST Projections": "proj_dst.json", "V1 - Eligible Fantasy Projections": "eligible.json", "AUTO - Snap Trends": "snaps.json", "V2 - First TD Board": "firsttd.json", "AUTO - First TD Odds": "ftdodds.json", "AUTO - Settings": "settings.json", "PROMO - Promoted Bets": "promos.json", "AUTO - Market Values": "market.json", "AUTO - Book Odds": "bookodds.json", "AUTO - WR CB Matchups": "wrcb.json", "AUTO - DK Salaries": "dksal.json", "AUTO - Confidence Archive": "confarc.json", "AUTO - Market Team Points": "teammkt.json", "V2 - Closing Lines": "closing.json", "AUTO - FanDuel Unders": "unders.json", "V2 - Model Best Picks": "bestpicks.json", "V2 - Unders Snapshots": "undersnaps.json"}
d = json.load(open(sys.argv[1]))
for sh in d["sheets"]:
    title = sh["properties"]["title"]; name = BY_TITLE.get(title)
    if not name: continue
    for data in (sh.get("data") or [{}]):
        rows = [[c.get("formattedValue", "") for c in r.get("values", [])] for r in data.get("rowData", [])]
        fname = name
        if title == "V2 - Boards Results Feed":      # two ranges on one tab: projections (col A) and legs (col AJ)
            fname = "results_legs.json" if data.get("startColumn", 0) >= 30 else "results.json"
        json.dump({"values": rows}, open(os.path.join(IN, fname), "w"))
        print(f"{fname}: {len(rows)} rows")
games = os.path.join(IN, "games.csv")
if not os.path.exists(games):
    subprocess.run(["curl", "-sSLf", "-o", games, "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"], check=True)
    print("downloaded games.csv")
