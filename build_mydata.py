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
# ---- owner 11/5 ("your CLV + one leg away"): closing prices per leg key and the build prices, so /me/ can show your price vs the close ----
# in/closing.json = 'V2 - Closing Lines' (ClosingLines.gs: the last FanDuel price pulled before kickoff; one row per week + line key).
# out/data/close-w<W>.json: {"week": W, "close": {"Player|Market|Line": {"o": -118, "imp": 0.541, "at": "..."}}, "build": {key: {"o": build price, "p": model chance}}}
import math
def slipkey(pl, m, ln):
    try: ln = float(ln)
    except Exception: ln = 1.0
    return f"{pl}|{m}|{int(math.floor((ln or 1) + 0.5))}"
def imp(o):
    try: o = float(o)
    except Exception: return None
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)
closes = defaultdict(dict)
try:
    cl = vals("closing.json"); C = {c: i for i, c in enumerate(cl[0])}
    for r in cl[1:]:
        if len(r) <= C["Close odds"] or not r[0]: continue
        try: w = int(float(r[0])); o = float(r[C["Close odds"]])
        except Exception: continue
        k = slipkey(r[C["Player"]], r[C["Market"]], r[C["Line (X+)"]])
        closes[w][k] = {"o": o, "imp": round(imp(o), 4), "at": r[C["Pulled at (CT)"]] if C.get("Pulled at (CT)") is not None and len(r) > C["Pulled at (CT)"] else ""}
except Exception as e: print("note: no closing lines:", e)
builds = {}
try:
    bd = json.load(open(os.path.join(HERE, "out", "builder_data.json"))); bw = int(bd.get("week") or 0)
    for l in bd.get("legs", []):
        if l.get("o") is None: continue
        builds[slipkey(l.get("pl") or l.get("player", ""), l.get("m") or l.get("market", ""), l.get("ln", 1))] = {"o": l["o"], "p": l.get("p")}
    if bw: json.dump({"week": bw, "close": closes.get(bw, {}), "build": builds}, open(os.path.join(OUT, f"close-w{bw}.json"), "w"), separators=(",", ":"))
    for w in sorted(closes):
        if w != bw: json.dump({"week": w, "close": closes[w], "build": {}}, open(os.path.join(OUT, f"close-w{w}.json"), "w"), separators=(",", ":"))
    print(f"wrote out/data/close-w*.json: " + ", ".join(f"wk {w} {len(closes[w])} closes" for w in sorted(closes)) + (f"; wk {bw} {len(builds)} build prices" if bw else ""))
except Exception as e: print("note: close-w*.json not written:", e)
# ---- 11/5 (Beat the model): out/data/graded-w<W>.json {"week": W, "legs": {"Player|Market|Line": "hit" | "miss" | "push"}, "actual": {key: actual}} from
# 'V2 - Boards Results Feed' (in/results_legs.json) - the Edge Function's grade mode scores everyone's five picks against it on Tuesday.
try:
    lf = vals("results_legs.json"); LH = {c: i for i, c in enumerate(lf[0])}
    graded = defaultdict(dict); actual = defaultdict(dict)
    for r in lf[1:]:
        if len(r) <= LH.get("Result", 0) or not r or not str(r[0]).strip().isdigit(): continue
        res = str(r[LH["Result"]]).strip().upper()
        if res not in ("HIT", "MISS", "PUSH", "VOID"): continue
        w = int(r[0]); k = slipkey(r[LH["Player"]], r[LH["Market"]], r[LH["Line (X+)"]])
        graded[w][k] = res.lower(); actual[w][k] = r[LH["Actual"]] if "Actual" in LH and len(r) > LH["Actual"] else ""
    for w in graded: json.dump({"week": w, "legs": graded[w], "actual": actual[w]}, open(os.path.join(OUT, f"graded-w{w}.json"), "w"), separators=(",", ":"))
    print("wrote out/data/graded-w*.json: " + (", ".join(f"wk {w} {len(graded[w])} legs" for w in sorted(graded)) or "no graded legs in the feed"))
except Exception as e: print("note: graded-w*.json not written:", e)
weeks = sorted(box)
for w in weeks:
    json.dump({"week": w, "box": box[w], "games": games.get(w, {}), "final": True}, open(os.path.join(OUT, f"box-w{w}.json"), "w"), separators=(",", ":"))
json.dump({"weeks": weeks}, open(os.path.join(OUT, "weeks.json"), "w"))
print(f"wrote out/data/box-w{{{','.join(str(w) for w in weeks)}}}.json: " + ", ".join(f"wk {w} {len(box[w])} players / {len(games.get(w, {}))} finals" for w in weeks))
