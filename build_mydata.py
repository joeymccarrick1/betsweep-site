#!/usr/bin/env python3
"""build_mydata.py - per-week box scores + finals as small JSON files, so the My BetSweep page can grade anyone's saved slips in the browser.

Inputs: in/gamelog.json ('AUTO - Player Game Log'), in/games.csv (nflverse schedule with final scores)
Output: out/data/box-w<W>.json for every week in the game log  {"week": W, "box": {player: [passYds, passTD, int, rushYds, rushTD, rec, recYds, recTD, longRec]},
        "games": {"AWAY-HOME": [away, home]}, "final": true}  plus out/data/weeks.json (the list). build_site.py copies out/data -> site/data.
Slip keys are the builder's 'player|market|line' (game lines: 'Ravens -6.5|Spread|-6', 'Bears ML|Moneyline|1', 'Over 44.5|Total|44').
"""
import json, os, csv
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out", "data"); os.makedirs(OUT, exist_ok=True)
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def num(x):
    try: return float(x)
    except Exception: return 0.0
ALIAS = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
gl = vals("gamelog.json"); H = {c: i for i, c in enumerate(gl[0])}
def g(r, c): return num(r[H[c]]) if c in H and H[c] < len(r) else 0.0
box = defaultdict(dict)
for r in gl[1:]:
    if len(r) < 17 or not r[0] or not r[1]: continue
    try: w = int(float(r[0]))
    except Exception: continue
    box[w][r[1].strip()] = [g(r, "Pass Yds"), g(r, "Pass TD"), g(r, "INT"), g(r, "Rush Yds"), g(r, "Rush TD"), g(r, "Receptions"), g(r, "Rec Yds"), g(r, "Rec TD"), g(r, "Longest Rec")]
games = defaultdict(dict)
with open(os.path.join(IN, "games.csv"), newline="") as f:
    for x in csv.DictReader(f):
        if x["season"] != "2026" or x["game_type"] != "REG" or x.get("home_score") in ("", None, "NA"): continue
        a, h = ALIAS.get(x["away_team"], x["away_team"]), ALIAS.get(x["home_team"], x["home_team"])
        games[int(x["week"])][f"{a}-{h}"] = [float(x["away_score"]), float(x["home_score"])]
weeks = sorted(box)
for w in weeks:
    json.dump({"week": w, "box": box[w], "games": games.get(w, {}), "final": True}, open(os.path.join(OUT, f"box-w{w}.json"), "w"), separators=(",", ":"))
json.dump({"weeks": weeks}, open(os.path.join(OUT, "weeks.json"), "w"))
print(f"wrote out/data/box-w{{{','.join(str(w) for w in weeks)}}}.json: " + ", ".join(f"wk {w} {len(box[w])} players / {len(games.get(w, {}))} finals" for w in weeks))
