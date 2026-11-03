#!/usr/bin/env python3
"""rz_check.py <W>  (Tuesday, Step 5) - grades the red-zone TD model against the projection model on week W's frozen FanDuel anytime-TD
legs (in/legsnaps.json, Latest Snapshot TRUE, Result HIT/MISS). Rebuilds the week-W red-zone table from play-by-play before week W
(rztd.build), so nothing from week W leaks. Prints log loss / Brier for raw model, rz model, the 50/50 average the builder shows, and
FanDuel, plus the running record by week in out/rz_check.json. Revert rule (rztd.py): raw beats the average two weeks running -> RZ_W = 0.
"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
import rztd as RZ
W = int(sys.argv[1])
table = RZ.build(W)
lf = json.load(open(os.path.join(IN, "legsnaps.json")))["values"]; LH = {c: i for i, c in enumerate(lf[0])}
rows = []
for r in lf[1:]:
    r = r + [""] * (len(lf[0]) - len(r))
    if str(r[LH["Week"]]) != str(W) or r[LH["Market"]] != "Anytime TD" or str(r[LH["Latest Snapshot"]]).upper() != "TRUE" or r[LH["Result"]].upper() not in ("HIT", "MISS"): continue
    v = RZ.lookup(table, r[LH["Player"]], r[LH["Team"]])
    if not v: continue
    try: raw = float(r[LH["Raw model %"]]); bk = float(r[LH["Book implied %"]])
    except Exception: continue
    rows.append({"pl": r[LH["Player"]], "raw": raw, "rz": v["p"], "bk": bk, "hit": 1 if r[LH["Result"]].upper() == "HIT" else 0})
def sc(fn):
    ll = br = 0.0
    for x in rows:
        q = min(max(fn(x), 0.01), 0.99); ll -= math.log(q if x["hit"] else 1 - q); br += (q - x["hit"]) ** 2
    return round(ll / len(rows), 4), round(br / len(rows), 4)
if not rows: print(f"rz check week {W}: no graded anytime-TD legs matched"); sys.exit(0)
res = {"raw": sc(lambda x: x["raw"]), "rz": sc(lambda x: x["rz"]), "avg": sc(lambda x: (1 - RZ.RZ_W) * x["raw"] + RZ.RZ_W * x["rz"]), "book": sc(lambda x: x["bk"]), "n": len(rows)}
hist = {}
try: hist = json.load(open(os.path.join(OUT, "rz_check.json")))
except Exception: pass
hist[str(W)] = res; json.dump(hist, open(os.path.join(OUT, "rz_check.json"), "w"), indent=1)
print(f"rz check week {W}: {len(rows)} graded ATD legs - log loss raw {res['raw'][0]} / rz {res['rz'][0]} / shown avg {res['avg'][0]} / FanDuel {res['book'][0]} (Brier {res['raw'][1]} / {res['rz'][1]} / {res['avg'][1]} / {res['book'][1]})")
lose = [w for w, v in sorted(hist.items(), key=lambda kv: int(kv[0])) if v["raw"][0] < v["avg"][0]]
print("weeks the raw model beat the shown average:", lose or "none", "- REVERT (set RZ_W = 0)" if len(lose) >= 2 and all(str(w) in lose for w in (W - 1, W)) else "")
