#!/usr/bin/env python3
"""unders_check.py <W>  (Tuesday, Step 5; owner 11/4 "test the unders properly")
Grades week W's frozen FanDuel main lines BOTH ways at the real prices: in/undersnaps.json ('V2 - Unders Snapshots'!A1:L20000, last freeze
per key before kickoff) against in/gamelog.json. Prints hit rate / ROI for unders and overs overall, by market, by price band, and for the
two cuts the 11/4 estimate flagged (rushing-yard unders on juiced overs; unders where the raw model is 5+ pts below the over price).
Writes out/unders_check.json. Promotion rule: a cut that shows positive units in two separate graded weeks with 60+ legs each may become a
Model's Best tier; until then this is tracking only.
"""
import json, os, sys, re, collections
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def num(x):
    try: return float(str(x).replace("+", "").replace(",", ""))
    except Exception: return None
def norm(n): return re.sub(r"[^a-z ]", "", re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", "", str(n).strip().lower())).strip()
W = int(sys.argv[1])
us = vals("undersnaps.json"); UH = {c: i for i, c in enumerate(us[0])}
gl = vals("gamelog.json"); GH = {c: i for i, c in enumerate(gl[0])}
COL = {"Passing Yards": "Pass Yds", "Rushing Yards": "Rush Yds", "Receiving Yards": "Rec Yds", "Receptions": "Receptions"}
act = {}
for r in gl[1:]:
    if len(r) <= GH["Rec Yds"] or str(r[GH["Week"]]).strip() != str(W): continue
    act[norm(r[GH["Player"]])] = {m: num(r[GH[c]]) for m, c in COL.items()}
last = {}
for r in us[1:]:
    r = r + [""] * (len(us[0]) - len(r))
    if str(r[UH["Week"]]).strip() != str(W) or str(r[UH["Frozen at (CT)"]])[:16] >= str(r[UH["Kickoff (CT)"]])[:16]: continue
    last[r[UH["Key"]] or (r[UH["Player"]], r[UH["Market"]], r[UH["Line"]])] = r
def pay(o): return (o / 100) if o > 0 else (100 / -o)
rows = []
for k, r in last.items():
    a = act.get(norm(r[UH["Player"]]))
    if not a: continue
    m = r[UH["Market"]]; v = a.get(m); ln = num(r[UH["Line"]]); uo = num(r[UH["Under odds"]]); oo = num(r[UH["Over odds"]]); ru = num(r[UH["Raw model under %"]])
    if v is None or ln is None or uo is None: continue
    under = v < ln
    rows.append({"m": m, "ln": ln, "uo": uo, "oo": oo, "ru": ru, "under": under, "uu": pay(uo) if under else -1.0, "ou": (pay(oo) if not under else -1.0) if oo is not None else None,
                 "ubk": (100 / (uo + 100)) if uo > 0 else (-uo / (-uo + 100)), "obk": ((100 / (oo + 100)) if oo > 0 else (-oo / (-oo + 100))) if oo is not None else None})
if not rows: print(f"unders check week {W}: no frozen main lines matched the game log"); sys.exit(0)
def line(name, g):
    n = len(g); uh = sum(1 for x in g if x["under"]); uu = sum(x["uu"] for x in g); ou = sum(x["ou"] for x in g if x["ou"] is not None)
    return f"{name:<42} n {n:>4}  under {uh/n*100:5.1f}% (implied {sum(x['ubk'] for x in g)/n*100:4.1f}%) {uu/n*100:+6.1f}%   over {(n-uh)/n*100:5.1f}% {ou/n*100:+6.1f}%"
out = [line("all main lines", rows)]
for m in COL: g = [x for x in rows if x["m"] == m]; out.append(line(m, g)) if len(g) >= 15 else None
for nm, f in (("under favored (under -120 or shorter)", lambda x: x["uo"] <= -120), ("near even (-119..+119)", lambda x: -119 < x["uo"] < 120), ("under plus money (+120 up)", lambda x: x["uo"] >= 120),
              ("CUT: rushing unders, over -200 or shorter", lambda x: x["m"] == "Rushing Yards" and x["oo"] is not None and x["oo"] <= -200),
              ("CUT: rushing unders, main line under 40 yds (11/5: wk6-8 main lines 94-66)", lambda x: x["m"] == "Rushing Yards" and x["ln"] < 40),
              ("CUT: model under % >= under implied + 5", lambda x: x["ru"] is not None and x["ru"] - x["ubk"] >= 0.05),
              ("CUT: model under % <= under implied - 5", lambda x: x["ru"] is not None and x["ru"] - x["ubk"] <= -0.05)):
    g = [x for x in rows if f(x)]
    if len(g) >= 10: out.append(line(nm, g))
txt = "\n".join(out); print(f"unders check week {W}:"); print(txt)
hist = {}
try: hist = json.load(open(os.path.join(OUT, "unders_check.json")))
except Exception: pass
hist[str(W)] = {"n": len(rows), "lines": out}; json.dump(hist, open(os.path.join(OUT, "unders_check.json"), "w"), indent=1)
