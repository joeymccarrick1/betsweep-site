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
# 11/17 evening: the losing side by its own definition, on the weeks whose pre-kickoff scripts are on file
SC = FS.scripts(IN); byw = {}
for (_w, _tm) in SC: byw[_w] = byw.get(_w, 0) + 1
check(all(byw.get(_k) == _n for _k, _n in ((8, 28), (9, 30), (10, 28))), f"the model's pre-kickoff read of every Week 8-10 game is on file ({ {_k: byw[_k] // 2 for _k in sorted(byw)} } games)")
lo = C["losing_own"]; w810 = [x for x in FS.legs(IN) if x["w"] in (8, 9, 10) and x["o"] <= -180 and x["m"] in FS.YARDS and (x["w"], x["tm"]) in SC]
l810 = FS._s([x for x in w810 if SC[(x["w"], x["tm"])][0] == f'{x["opp"]} by 10+']); g810 = FS._s([x for x in w810 if SC[(x["w"], x["tm"])][0] == f'{x["tm"]} by 10+'])
check(abs(l810["n"] - 318) <= 3 and abs(l810["hit"] - 0.588) < 0.01 and abs(g810["n"] - 311) <= 3 and abs(g810["hit"] - 0.704) < 0.01, f"Weeks 8-10, yardage floors: the side the model had losing big {l810['n']} legs at {100*l810['hit']:.1f}%, the side it had winning big {g810['n']} at {100*g810['hit']:.1f}% (318 at 58.8% / 311 at 70.4% on 11/17)")
check(lo["lose"]["n"] >= 150 and lo["win"]["n"] >= 150 and lo["lose"]["hit"] < lo["lose"]["imp"] - 0.05 and "losing big" in T["losing"] and "winning big" in T["losing"], f"the flag's sentence is counted on its own definition ({T['losing'][:110]})")
span = FS._span(C["weeks"]); check(all(re.search(r"Weeks? \d", T[k]) for k in T if k != "rush_under_rate") and span in T["near_zero"] and (span in T["losing"] or FS._span(C["losing_own"]["weeks"]) in T["losing"]) and span in T["fav"], f"each sentence names its weeks ({span})")
check(isinstance(T["rush_under_rate"], float) and 0.50 <= T["rush_under_rate"] <= 0.62, f"the flat rushing-under chance is the counted rate, inside its guard ({T['rush_under_rate']})")
with tempfile.TemporaryDirectory() as t: check(FS.text(t) == FS.DEFAULT, "with no snapshots the 11/17 numbers stand in")
bd = os.path.join(OUT, "builder_data.json")
if os.path.exists(bd):
    D = json.load(open(bd)); txt = " ".join(str(f[2]) for l in D["legs"] for f in (l.get("fh") or []) if isinstance(f, (list, tuple)) and len(f) > 2) + " " + " ".join(str(f[2]) for fs in (D.get("pf") or {}).values() for f in fs if isinstance(f, (list, tuple)) and len(f) > 2)
    # the sentences this module replaced (two study notes in role_rising.py keep their own dated check: they need weekly snap data that is not frozen)
    old = [t for t in ("Weeks 6-9 (312 lines)", "their prices (Weeks 7-9)", "Weeks 6-9 (151 legs", "Weeks 6-9 (439 legs)", "(Weeks 6-7: model", "better than the rest (Weeks 6-9)", "under their prices (Weeks 6-9)") if t in txt]
    check(not old, f"no flag on the built legs still carries a typed number ({old or 'none'})")
    check(T["losing"] in txt or "Losing side" not in txt, "the losing-side flag carries the counted sentence")
    wk = int(json.load(open(os.path.join(HERE, "out", "builder_data.json")))["week"]) if os.path.exists(os.path.join(HERE, "out", "builder_data.json")) else None
    scf = os.path.join(HERE, "out", "data", f"scripts-w{wk}.json") if wk else ""
    if scf and os.path.exists(scf):
        sj = json.load(open(scf)); gs = sj.get("games") or {}; bd = json.load(open(os.path.join(HERE, "out", "builder_data.json")))
        up = [g["gid"] for g in bd["games"] if g.get("ko") and g["ko"] > __import__("time").time() * 1000]
        check(sj.get("week") == wk and all(g in gs for g in up) and all(len(v["probs"]) == 4 and abs(sum(v["probs"]) - 100) <= 2 and v.get("most") for v in gs.values()), f"this week's game scripts are filed for every game still to kick off ({len(gs)} on file, {len(up)} upcoming)")
    else: print("SKIP the weekly scripts file (no build here)")
    if w["volatile"]["n"]: check(T["volatile"] in txt or "Hard to read" not in txt, "the volatile flag carries the counted sentence")
print(f"{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
