#!/usr/bin/env python3
"""avail_check.py - does every row of 'AUTO - Weekly Availability' actually reach the model?

The sheet's four projection tabs read a player's status with week + NAME + TEAM + POSITION (checked 11/10: QB!AD, RB!AB, WR!Z, TE!X all
MATCH on the four together), which is what keeps two players who share a name apart. The price of that: a row whose team or position
is not what the projection tab has for the player - a trade the game log has not caught up with, "LAR" for "LA", a TE entered as WR -
matches nothing and is silently ignored, and the player projects as healthy. This prints those rows so they get fixed in the tab.

Reads in/avail.json, in/proj_qb.json / proj_rb.json / proj_wr.json / proj_te.json, in/settings.json. Changes nothing.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in")
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def check(avail, proj, week):
    """avail: tab rows (header first); proj: {name: [(pos, team), ...]}; -> (matched, ignored [(name, team, pos, status, tab has)], off_tab [(name, team, pos, status)])"""
    ok, ignored, off = 0, [], []
    for r in avail[1:]:
        r = list(r) + [""] * (5 - len(r))
        if str(r[0]).strip() != str(week): continue
        n, t, p, st = (str(x).strip() for x in r[1:5])
        if p not in ("QB", "RB", "WR", "TE") or not n: continue
        c = proj.get(n)
        if not c: off.append((n, t, p, st))
        elif (p, t) in c: ok += 1
        else: ignored.append((n, t, p, st, ", ".join(f"{pp} {tt}" for pp, tt in c)))
    return ok, ignored, off
def main():
    try: week = int(float(next(r[1] for r in vals("settings.json") if r and str(r[0]).strip().lower() == "projection week")))
    except Exception: raise SystemExit("availability check: week unknown (in/settings.json)")
    proj = {}
    for pos, f in (("QB", "proj_qb.json"), ("RB", "proj_rb.json"), ("WR", "proj_wr.json"), ("TE", "proj_te.json")):
        for r in vals(f)[1:]:
            if r and str(r[0]).strip(): proj.setdefault(str(r[0]).strip(), []).append((pos, str(r[1]).strip() if len(r) > 1 else ""))
    ok, ignored, off = check(vals("avail.json"), proj, week)
    for n, t, p, st, has in ignored: print(f"IGNORED BY THE SHEET: {n} ({t} {p}) {st} - the projection tab has him as {has}; fix the team / position in 'AUTO - Weekly Availability' or the status does nothing")
    if off: print("not on a projection tab (no effect on projections; fine for players who have not played this season): " + "; ".join(f"{n} {t} {p} {st}" for n, t, p, st in off))
    print(f"availability check, week {week}: {ok} rows reach the model by name + team + position, {len(ignored)} ignored, {len(off)} not on a projection tab")
    return 1 if ignored else 0
def selftest():
    av = [["Projection Week", "Player", "Team", "Pos", "Availability"], ["10", "Josh Allen", "BUF", "QB", "OUT"], ["10", "Josh Allen", "JAX", "LB", "OUT"], ["10", "Traded Guy", "ARI", "QB", "OUT"],
          ["10", "Wrong Pos", "KC", "WR", "QUESTIONABLE"], ["10", "Rams Guy", "LAR", "WR", "OUT"], ["10", "Rookie", "NYG", "RB", "OUT"], ["9", "Old Week", "SF", "WR", "OUT"], ["10", "Fine", "DET", "TE", "DOUBTFUL"]]
    proj = {"Josh Allen": [("QB", "BUF")], "Traded Guy": [("QB", "BAL")], "Wrong Pos": [("TE", "KC")], "Rams Guy": [("WR", "LA")], "Fine": [("TE", "DET")], "Old Week": [("WR", "DAL")]}
    ok, ig, off = check(av, proj, 10); bad = 0
    for c, what in ((ok == 2, "two rows reach the model (the quarterback, not the linebacker who shares his name)"), ([x[0] for x in ig] == ["Traded Guy", "Wrong Pos", "Rams Guy"], "a traded player, a wrong position and LAR-for-LA are named as ignored"),
                    ([x[0] for x in off] == ["Rookie"], "a player on no projection tab is listed apart"), (all(x[0] != "Old Week" for x in ig + off), "other weeks are left alone")):
        print(("ok   " if c else "FAIL ") + what); bad += 0 if c else 1
    print("availability check selftest:", "ok" if not bad else f"{bad} FAILED"); return bad
if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
