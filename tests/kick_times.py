"""Kickoff times (11/22): the schedule file had two Sunday games in each other's windows; kickfix.py takes a kickoff from FanDuel when
the two disagree. This runs kickfix's own checks, then reads the build: every game on the builder's board must kick off when FanDuel's
game-lines tab says it does.     python3 tests/kick_times.py"""
import datetime, json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
r = subprocess.run([sys.executable, os.path.join(HERE, "kickfix.py"), "--selftest"], capture_output=True, text=True)
out = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
for l in out:
    if l.startswith(("PASS ", "FAIL ")): ok[0 if l.startswith("PASS ") else 1] += 1; print(l)
check(r.returncode == 0 and any(l.startswith("PASS ") for l in out), "kickfix.py --selftest ran and passed")
import kickfix as KF
IN = os.path.join(HERE, "in"); bd = json.load(open(os.path.join(HERE, "out", "builder_data.json"))); fd = KF.fanduel(IN)
CT = datetime.timezone(datetime.timedelta(hours=-6)); bad = []; seen = 0
import csv
home = {}
for g in csv.DictReader(open(os.path.join(IN, "games.csv"), newline="")):
    if g["season"] == "2026" and g["week"] == str(bd.get("week") or ""): home[frozenset((g["away_team"], g["home_team"]))] = (g["away_team"], g["home_team"])
for g in bd["games"]:
    ah = home.get(frozenset((g["a"], g["b"]))); e = fd.get(ah) if ah else None
    if not e or e["n"] < KF.MIN_ROWS or len(e["kicks"]) != 1 or not g.get("ko") or g.get("fin"): continue
    mine = datetime.datetime.fromtimestamp(g["ko"] / 1000, datetime.timezone.utc); theirs = KF._fd_time(next(iter(e["kicks"])), mine.astimezone(KF.ET).date())
    if theirs is None: continue
    seen += 1
    if abs((theirs - mine).total_seconds()) >= KF.MIN_GAP_MIN * 60: bad.append((g["gid"], g["kick"], next(iter(e["kicks"]))))
check(seen >= 1 and not bad, f"every game on the board kicks off when FanDuel says it does ({seen} games compared; off: {bad})")
try: rep = json.load(open(os.path.join(HERE, "out", "kickfix.json")))
except Exception: rep = None
check(rep is not None and all(x.get("now") or x.get("why") for x in rep["games"]), "the build wrote what it changed: " + (", ".join(f"{x['game']} {x['was'][11:]} -> {(x['now'] or 'held')[11:]} ET" for x in rep["games"]) if rep and rep["games"] else "nothing to change"))
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
