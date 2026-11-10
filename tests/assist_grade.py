#!/usr/bin/env python3
"""tests/assist_grade.py - grade_assist.py / slipgrade.py against the Week 9 slips that were graded by hand (tests/fixtures/assist_log_w9.json).

Needs in/gamelog.json and in/games.csv with Week 9 in them (any later week's inputs still carry it). Run from the generator folder:
python3 tests/assist_grade.py
"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(HERE); sys.path.insert(0, HERE)
import slipgrade as SG
FIX = os.path.join("tests", "fixtures", "assist_log_w9.json"); fails = []
def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok: fails.append(what)
def run(*a):
    r = subprocess.run([sys.executable, "grade_assist.py", *a], capture_output=True, text=True); return r.returncode, r.stdout + r.stderr

G = SG.Grader("in", 9)
if not G.ready: print("skip: Week 9 is not in in/gamelog.json"); sys.exit(0)
tmp = tempfile.mkdtemp(); out = os.path.join(tmp, "grades.json")
# 1) the grader against the hand grades
code, txt = run("9", "--check", f"--file={FIX}", f"--out={out}")
check(code == 0 and "agrees on 5, disagrees on 0" in txt, "check mode: agrees with all five hand grades it can read, disagrees with none")
# 2) the same slips with the results blanked
v = json.load(open(FIX)); blank = json.loads(json.dumps(v))
for r in blank["values"][1:]: r[8] = ""
blank["values"][3][8] = "WON"   # sheet row 4 already graded by hand: must not be touched
f2 = os.path.join(tmp, "blank.json"); json.dump(blank, open(f2, "w"))
code, txt = run("9", f"--file={f2}", f"--out={out}"); g = json.load(open(out)); up = {u["range"]: u["values"][0] for u in g["updates"]}
check(code == 0 and g["week"] == 9 and sorted(up) == ["'ASSIST - Slip Log'!I2:J2", "'ASSIST - Slip Log'!I3:J3", "'ASSIST - Slip Log'!I6:J6", "'ASSIST - Slip Log'!I8:J8"], f"grades rows 2, 3, 6 and 8 only {sorted(up)}")
check(up.get("'ASSIST - Slip Log'!I2:J2", [""])[0] == "WON" and up.get("'ASSIST - Slip Log'!I3:J3", [""])[0] == "LOST" and up.get("'ASSIST - Slip Log'!I6:J6", [""])[0] == "LOST" and up.get("'ASSIST - Slip Log'!I8:J8", [""])[0] == "WON", "won / lost / lost / won")
n2 = up.get("'ASSIST - Slip Log'!I2:J2", ["", ""])[1]; n6 = up.get("'ASSIST - Slip Log'!I6:J6", ["", ""])[1]
check(n2.startswith("Owner confirmed 5:55 PM. | Auto-graded: 4/4 legs") and "Justin Herbert 193" in n2, "the note that was there is kept and the leg-by-leg line follows it")
check("Carson Wentz 81 (missed 175+ pass yds)" in n6 and "Aaron Jones 1 (missed 2+ rec)" in n6 and "2/4 legs" in n6, "a lost slip names the legs that missed with the real numbers")
check(len(g["pending"]) == 2 and "row 5" in g["pending"][0] and "row 7" in g["pending"][1], "the two slips that cannot be read are left open and named")
check("row 4" not in txt and "2 won, 2 lost" in g["summary"] and "(+5.25u" in g["summary"] and "2 left open" in g["summary"], f"row 4 (already graded) untouched; summary: {g['summary']}")
# 3) a leg that plainly missed settles a slip even when another leg cannot be read; an unread leg alone keeps it open
check(G.slip("Carson Wentz 175+ pass yds | Some Mystery Leg")["result"] == "LOST", "one plain miss: lost, whatever the unread leg did")
check(G.slip("James Cook 70+ rush yds | Some Mystery Leg")["result"] == "PENDING", "a hit plus an unread leg: stays open")
check(G.slip("James Cook 70+ rush yds\nBills ML")["result"] == "WON" and G.slip("James Cook | Rushing Yards 70+")["result"] == "WON", "line breaks and the PROMO tab's own leg form both read")
check(G.leg("Allen 200+ pass yds")[0] == "PENDING" and "full name" in G.leg("Allen 200+ pass yds")[1], "a last name shared by several players is never guessed")
check(G.leg("Under 49.5", "BUF-MIN")[0] == "HIT" and G.leg("Under 49.5", "BUF-MIN, CHI-TB")[0] == "PENDING" and G.leg("Under 49.5 (BUF-MIN)", "")[0] == "HIT", "a total takes the row's game only when the row names exactly one")
check(G.leg("Bijan Robinson or Chase Brown TD")[0] == "HIT" and G.leg("Josh Allen U237.5 pass yds")[0] == "HIT" and G.leg("Vikings ML")[0] == "MISS", "either-or touchdowns, unders and moneylines")
# 4) a tab it cannot read, a week with no game log
bad = json.loads(json.dumps(v)); bad["values"][0][4] = "The legs"; f3 = os.path.join(tmp, "bad.json"); json.dump(bad, open(f3, "w"))
code, txt = run("9", f"--file={f3}", f"--out={out}"); check(code != 0 and "header" in txt, "a tab with other columns is refused, not guessed at")
fut = json.loads(json.dumps(blank)); 
for r in fut["values"][1:]: r[1] = "30"
f4 = os.path.join(tmp, "fut.json"); json.dump(fut, open(f4, "w"))
code, txt = run(f"--file={f4}", f"--out={out}"); g = json.load(open(out)); check(code == 0 and g["updates"] == [] and "nothing to grade" in txt, "a week that has not been played: nothing is written")
# 5) the same grader against the PROMO tab's own results (written by grade_promos.py / the owner), every graded week in the game log
try:
    pv = json.load(open(os.path.join("in", "promos.json")))["values"]; PH = {c.strip().split(" (")[0]: i for i, c in enumerate(pv[0])}
except Exception: pv = None
if pv:
    agree = dis = openn = 0; bad = []; GS = {}
    for i, r in enumerate(pv[1:], start=2):
        r = list(r) + [""] * (14 - len(r)); had = str(r[PH["Result"]]).strip().lower()
        want = "WON" if had in ("hit", "cashed", "won") else "LOST" if had in ("missed", "lost") else None
        try: w = int(float(r[PH["Week"]]))
        except Exception: continue
        if not want: continue
        if w not in GS: GS[w] = SG.Grader("in", w)
        if not GS[w].ready: continue
        res = GS[w].slip(r[PH["Legs"]])["result"]
        if res == "PENDING": openn += 1
        elif res == want: agree += 1
        else: dis += 1; bad.append(f"row {i}: sheet {had}, grader {res}")
    check(dis == 0 and agree > 0, f"PROMO tab cross-check: agrees with {agree} graded promos, disagrees with {dis}, cannot read {openn} {bad[:3]}")
print("assist grade:", "all checks passed" if not fails else f"{len(fails)} FAILED"); sys.exit(1 if fails else 0)
