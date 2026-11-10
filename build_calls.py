#!/usr/bin/env python3
"""build_calls.py - freeze the model's per-game calls for the week into rows for 'AUTO - Model Calls Archive'.

One row per game that has NOT kicked off yet (plus, with --include-played, games already played - used once to back-fill
a game whose pre-kickoff numbers are still what the sheet holds). Reads in/scripts.json (model score + script odds),
in/games.csv (kickoffs), in/gamelines.json via gamelines.py (FanDuel lines and the model's shrunk chances as the site shows them),
out/best_parlays.json (written by build_boards.py). Writes out/calls_rows.json = {"range": "...!A{r}", "values": rows} is NOT
known here (the sheet's next free row is), so it writes {"values": rows, "header": [...]}; the runbook appends the rows.

Columns (A..AC): Week | Frozen at (CT) | Game | A | B | Kickoff (CT) | Model A pts | Model B pts | Model margin (A-B) | Model total |
P(A by 10+) | P(close, low) | P(shootout) | P(B by 10+) | Most likely | FD spread (A) | FD spread odds (A) | FD total | FD over odds |
FD ML A | FD ML B | Model P(A win) as shown | Model P(A covers) as shown | Model P(over) as shown | Line source |
Best parlay legs | Best parlay price | Best parlay model % | Built for
Grades (AD..AN) are filled by build_calls_results.py after the games.
"""
import json, os, sys, csv, datetime
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE); import gamelines as GLM
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def num(x):
    try: return float(str(x).replace("%", "").replace(",", ""))
    except Exception: return None
try: WEEK = int(float(next(r[1] for r in vals("settings.json") if r and str(r[0]).strip().lower() == "projection week")))
except Exception: WEEK = None
scripts = vals("scripts.json")
S = [r for r in scripts[1:] if len(r) >= 11 and r[0]]
if WEEK is None: raise SystemExit("week unknown (in/settings.json)")
sched = GLM.load_sched(IN, WEEK); fd = GLM.load_fd(IN)
try: BP = {b["gid"]: b for b in json.load(open(os.path.join(OUT, "best_parlays.json")))}
except Exception: BP = {}
# owner 11/10 ("I'd roll with sweep says more often"): build_boards.py keeps the best parlay from fighting the game's Sweep says lean and
# writes what the lean changed to out/sweep_leans.json. The "Built for" cell carries it - the lean, and the slip the same run would have
# printed without it - so the two can be graded side by side later. No new column: AD onward belongs to the grades.
try:
    _SL = json.load(open(os.path.join(OUT, "sweep_leans.json")))
    LEANS = {x["gid"]: x for x in _SL.get("games", [])} if int(_SL.get("week") or 0) == int(WEEK) else {}
except Exception: LEANS = {}
def _am(d): return f"+{round((d - 1) * 100)}" if d >= 2 else f"-{round(100 / (d - 1))}"
def built_for(gid, bp):
    x = LEANS.get(gid); fit = bp["fit"] if bp else ""
    if not x: return fit
    out = [fit] if fit else ["no slip agrees with Sweep says"]
    out.append("Sweep says: " + x["text"])
    if x.get("changed") and x.get("free"):
        out.append("without it: " + " ; ".join(f"{p}|{m}|{ln if m in ('Spread', 'Total') else int(ln or 1)}|{int(o)}" for (p, m, ln, o) in x["free"]) + " @ " + _am(x["free_dec"]))
    return " | ".join(out)
include_played = "--include-played" in sys.argv
CT = ZoneInfo("America/Chicago"); now = datetime.datetime.now(CT); stamp = now.strftime("%Y-%m-%d %H:%M")
HEADER = ["Week", "Frozen at (CT)", "Game", "A", "B", "Kickoff (CT)", "Model A pts", "Model B pts", "Model margin (A-B)", "Model total",
          "P(A by 10+)", "P(close, low)", "P(shootout)", "P(B by 10+)", "Most likely", "FD spread (A)", "FD spread odds (A)", "FD total", "FD over odds",
          "FD ML A", "FD ML B", "Model P(A win) as shown", "Model P(A covers) as shown", "Model P(over) as shown", "Line source",
          "Best parlay legs", "Best parlay price", "Best parlay model %", "Built for"]
rows = []; skipped = []
for r in S:
    a, b = r[0], r[1]; pa, pb = num(r[2]), num(r[3]); probs = [num(r[6]), num(r[7]), num(r[8]), num(r[9])]
    g = sched.get(frozenset([a, b]))
    if not g: skipped.append(f"{a}-{b}: not on the schedule"); continue
    ko = datetime.datetime.fromisoformat(g["gameday"] + "T" + g["gametime"]).replace(tzinfo=ZoneInfo("America/New_York"))
    played = now >= ko.astimezone(CT)
    if played and not include_played: skipped.append(f"{a}-{b}: kicked off"); continue
    legs = GLM.game_legs(a, b, pa or 0, pb or 0, probs, sched, fd)
    main = [x for x in legs if not x.get("alt")]
    def pick(m, side): return next((x for x in main if x["m"] == m and x["side"] == side), None)
    mlA, spA, ov = pick("Moneyline", a), pick("Spread", a), pick("Total", "OVER"); mlB = pick("Moneyline", b)
    src = "FanDuel" if (spA and spA["src"] == "fd") else "consensus"
    bp = BP.get(f"{a}-{b}")
    bpl = " | ".join(f"{p}|{m}|{int(ln or 1) if m != 'Spread' and m != 'Total' else ln}|{int(o)}" for (p, m, ln, o, pr, e) in bp["legs"]) if bp else ""
    rows.append([WEEK, stamp + (" (retro: numbers unchanged since the pre-kickoff build)" if played else ""), f"{a}-{b}", a, b, ko.astimezone(CT).strftime("%a %m/%d %H:%M"),
                 pa, pb, round((pa or 0) - (pb or 0), 2), round((pa or 0) + (pb or 0), 2), probs[0], probs[1], probs[2], probs[3], r[10],
                 spA["ln"] if spA else "", spA["o"] if spA else "", ov["ln"] if ov else "", ov["o"] if ov else "", mlA["o"] if mlA else "", mlB["o"] if mlB else "",
                 round(mlA["p"], 4) if mlA else "", round(spA["p"], 4) if spA else "", round(ov["p"], 4) if ov else "", src,
                 bpl, (round((bp["dec"] - 1) * 100) if bp["dec"] >= 2 else -round(100 / (bp["dec"] - 1))) if bp else "", round(bp["pj"], 4) if bp else "", built_for(f"{a}-{b}", bp)])
json.dump({"header": HEADER, "values": rows}, open(os.path.join(OUT, "calls_rows.json"), "w"), indent=0)
if LEANS: print(f"sweep leans on record for {len(LEANS)} games ({sum(1 for x in LEANS.values() if x.get('changed'))} changed the best parlay) - noted in the Built for column")
print(f"wrote out/calls_rows.json: {len(rows)} games frozen for week {WEEK} at {stamp} CT" + (f"; skipped {len(skipped)}: " + "; ".join(skipped) if skipped else ""))
