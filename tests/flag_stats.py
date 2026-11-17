"""The graded numbers quoted inside flags and slip warnings are counted, not typed (11/17).
On Weeks 6-9 alone the main-rushing-line count must return the 11/11 grade (312 lines, overs 42.9% = unders 57.1%); every sentence
names the weeks it covers; with no snapshots the 11/17 numbers stand in; the built legs carry no sentence with an old span.
Needs in/legsnaps.json, in/gamelog.json, in/games.csv (the mirror); the last check needs out/builder_data.json from a build."""
import json, os, re, sys, tempfile
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
import flag_stats as FS
IN = os.environ.get("IN") or os.path.join(HERE, "in"); OUT = os.environ.get("OUT") or os.path.join(HERE, "out")
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)
C = FS.counts(IN); check(bool(C) and C["n"] >= 4929, f"the graded legs are read ({C and C['n']:,})")
L = FS.legs(IN); best = {}
for x in L:
    if x["m"] == "Rushing Yards" and x["w"] in (6, 7, 8, 9):
        k = (x["w"], x["pl"])
        if k not in best or abs(x["o"] + 110) < abs(best[k]["o"] + 110): best[k] = x
m = [x for x in best.values() if -160 <= x["o"] <= 130]; u = 1 - sum(x["hit"] for x in m) / len(m)
check(abs(len(m) - 312) <= 2 and abs(u - 0.571) < 0.006, f"Weeks 6-9, main rushing lines: the 11/11 grade was 312 lines, unders 57.1% ({len(m)}, {100*u:.1f}%)")
check(C["main"]["n"] >= 312 and 0.50 <= C["main"]["under"] <= 0.62, f"every graded week since: {C['main']['n']} lines, unders {100*C['main']['under']:.1f}%")
check(C["near_zero"]["n"] >= 100 and C["near_zero"]["hit"] < C["near_zero"]["imp"], f"near-zero floor legs: {C['near_zero']['n']} at {100*C['near_zero']['hit']:.0f}% against {100*C['near_zero']['imp']:.0f}%")
d, f = C["losing"]["dog"], C["losing"]["fav"]; check(d["n"] >= 100 and f["n"] >= 100, f"yardage floors by closing spread: underdogs of 5.5+ {d['n']} legs at {100*d['hit']:.0f}%, favorites {f['n']} at {100*f['hit']:.0f}%")
check(C["fav"]["all"]["n"] >= 2000 and C["disagree"]["n"] >= 150, f"favorites {C['fav']['all']['n']:,} legs ({100*C['fav']['all']['roi']:+.1f}%), model 10+ over {C['disagree']['n']} legs (said {100*C['disagree']['model']:.0f}%, hit {100*C['disagree']['hit']:.0f}%)")
w = C["walk"]; check(all(w[k]["n"] >= 100 for k in ("team_under", "team_rest", "reliable", "volatile", "rest")), "walk-forward groups (team under its prices, reliable, volatile) each hold 100+ legs: " + ", ".join(f"{k} {v['n']} ({100*v['gap']:+.1f})" for k, v in w.items()))
T = FS.text(IN); check(set(T) == set(FS.DEFAULT), f"every sentence the generators use is produced ({len(T)})")
span = FS._span(C["weeks"]); check(all(re.search(r"Weeks? \d", T[k]) for k in T if k != "rush_under_rate") and span in T["near_zero"] and span in T["losing"] and span in T["fav"], f"each sentence names its weeks ({span})")
check(isinstance(T["rush_under_rate"], float) and 0.50 <= T["rush_under_rate"] <= 0.62, f"the flat rushing-under chance is the counted rate, inside its guard ({T['rush_under_rate']})")
with tempfile.TemporaryDirectory() as t: check(FS.text(t) == FS.DEFAULT, "with no snapshots the 11/17 numbers stand in")
bd = os.path.join(OUT, "builder_data.json")
if os.path.exists(bd):
    D = json.load(open(bd)); txt = " ".join(str(f[2]) for l in D["legs"] for f in (l.get("fh") or []) if isinstance(f, (list, tuple)) and len(f) > 2) + " " + " ".join(str(f[2]) for fs in (D.get("pf") or {}).values() for f in fs if isinstance(f, (list, tuple)) and len(f) > 2)
    # the sentences this module replaced (two study notes in role_rising.py keep their own dated check: they need weekly snap data that is not frozen)
    old = [t for t in ("Weeks 6-9 (312 lines)", "their prices (Weeks 7-9)", "Weeks 6-9 (151 legs", "Weeks 6-9 (439 legs)", "(Weeks 6-7: model", "better than the rest (Weeks 6-9)", "under their prices (Weeks 6-9)") if t in txt]
    check(not old, f"no flag on the built legs still carries a typed number ({old or 'none'})")
    check(T["losing"] in txt or "Losing side" not in txt, "the losing-side flag carries the counted sentence")
    if w["volatile"]["n"]: check(T["volatile"] in txt or "Hard to read" not in txt, "the volatile flag carries the counted sentence")
print(f"{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
