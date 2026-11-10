#!/usr/bin/env python3
"""tests/backup_qb.py - the "Backup QB" flag (owner 11/9: "we shouldn't have had so much trust on a backup QB that's starting for an
offense that was already not performing well").

Part 1 needs nothing but flags.py: backup_qb() on a hand-made game log (who started, who is projected, who is out, where the offense ranks).
Part 2 needs the week's inputs in in/ (it loads the real engine, puts a stand-in on one team that has projected players, and checks which
legs get the flag). Run from the generator folder: python3 tests/backup_qb.py
"""
import os, sys, json
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE); os.chdir(HERE)
import flags as FLAGS
fails = []
def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok: fails.append(what)

def stub(starts, proj, out, rank, plays=True, team="AAA"):
    """starts: {qb: [weeks]}; proj: {qb: projected pass yards}; out: names ruled out; rank: points-per-game rank"""
    e = FLAGS.Engine.__new__(FLAGS.Engine)
    e.GL = {n: [{"w": w, "team": team, "pos": "QB", "Pass Att": 30} for w in ws] for n, ws in starts.items()}
    e.PROJ = {n: {"team": team, "pos": "QB", "Pass Yds": y} for n, y in proj.items()}
    e.OUT = {n: {"team": team, "pos": "QB", "why": "test"} for n in out}
    e.PPG = {team: (18.0, rank)}; e.TOTAL = {frozenset([team, "BBB"]): 41.5} if plays else {}; e._bqb = {}
    return e.backup_qb(team)

r = stub({"Starter": [1, 2, 3, 4, 5, 6, 7, 8], "Standin": [9]}, {"Standin": 190}, {"Starter"}, 27)
check(r and r["qb"] == "Standin" and r["for"] == "Starter" and r["starts"] == 1 and r["rank"] == 27, f"stand-in with one start on the #27 offense: flagged {r}")
check(stub({"Starter": [1, 2, 3, 4, 5, 6, 7, 8], "Standin": [9]}, {"Standin": 190}, {"Starter"}, 20) is None, "same stand-in on the #20 offense: no flag (not a struggling offense)")
check(stub({"Starter": [1, 2, 3, 4, 5, 6, 7, 8], "Standin": [9]}, {"Standin": 190}, {"Starter"}, 21) is not None, "the line is the bottom 12: #21 is flagged")
check(stub({"Starter": [1, 2], "Standin": [3, 4, 5, 6]}, {"Standin": 210}, {"Starter"}, 30) is None, "a quarterback who has started most of the games is the starter now: no flag")
check(stub({"Starter": [1, 2, 3, 4, 5, 6], "Standin": [7, 8, 9, 10]}, {"Standin": 210}, {"Starter"}, 30) is None, "four starts in: the log knows him, no flag")
check(stub({"Starter": [1, 2, 3, 4, 5, 6], "Standin": [7, 8, 9]}, {"Standin": 210}, {"Starter"}, 30) is not None, "three starts: still a stand-in")
check(stub({"Starter": [1, 2, 3, 4, 5, 6, 7, 8], "Standin": [9]}, {"Starter": 240, "Standin": 20}, set(), 30) is None, "the starter is projected again: no flag")
r = stub({"Starter": [1, 2, 3, 4, 5, 6, 7, 8], "Standin": [9]}, {"Newguy": 180}, {"Starter", "Standin"}, 26)
check(r and r["qb"] == "Newguy" and r["starts"] == 0, f"a third quarterback with no starts: flagged as his first start {r}")
r = stub({"Starter": [1, 2, 3, 4, 5, 6, 7, 8], "Standin": [9]}, {}, {"Standin"}, 26)
check(r and r["qb"] is None and r["for"] == "Standin", f"nobody projected and last week's starter out, team plays: unsettled {r}")
check(stub({"Starter": [1, 2, 3, 4, 5, 6, 7, 8], "Standin": [9]}, {}, {"Standin"}, 26, plays=False) is None, "the same on a bye week: nothing to flag")
check(stub({"Starter": [1, 2, 3, 4, 5, 6, 7, 8, 9]}, {"Starter": 250}, set(), 32) is None, "the regular starter on the worst offense: no flag (the rule is about stand-ins)")
check(stub({}, {"Rookie": 200}, set(), 32) is None, "no game log at all: no guess")

# ---- part 2: which legs carry it (real engine, one injected situation) ----
try:
    WEEK = int(float(next(r[1] for r in json.load(open(os.path.join("in", "settings.json")))["values"] if r and str(r[0]).strip().lower() == "projection week")))
    FE = FLAGS.Engine("in", WEEK)
except Exception as e:
    FE = None; print("skip part 2 (no inputs in in/):", str(e)[:80])
if FE:
    by = {}
    for n, v in FE.PROJ.items():
        if v.get("team") and v.get("pos") in ("QB", "RB", "WR", "TE") and FE.games(n): by.setdefault(v["team"], {}).setdefault(v["pos"], []).append(n)
    team = next((t for t, d in sorted(by.items()) if all(d.get(p) for p in ("QB", "RB", "WR", "TE"))), None)
    if not team: print("skip part 2: no team with a projected QB, RB, WR and TE")
    else:
        d = by[team]; qb = d["QB"][0]; opp = FE.PROJ[d["WR"][0]].get("opp")
        FE._bqb[team] = {"qb": qb, "for": "The Starter", "starts": 1, "ppg": 17.0, "rank": 28}
        def has(pl, m): return any(f["tag"] == "Backup QB" and f["k"] == "bad" for f in FE.leg({"player": pl, "market": m, "line": 1, "team": team, "opp": opp}))
        check(has(qb, "Passing Yards") and has(qb, "Passing TDs"), f"{team}: the stand-in's own passing legs are flagged")
        check(not has(qb, "Rushing Yards") and not has(qb, "Anytime TD"), "his rushing and touchdown legs are not")
        check(all(has(d["WR"][0], m) for m in ("Receiving Yards", "Receptions", "Longest Reception", "Anytime TD", "First TD")), "a receiver: catches, yards and touchdowns are flagged")
        check(all(has(d["TE"][0], m) for m in ("Receiving Yards", "Receptions", "Anytime TD")), "a tight end: the same")
        check(has(d["RB"][0], "Receptions") and has(d["RB"][0], "Receiving Yards"), "a running back's catches and receiving yards are flagged")
        check(not has(d["RB"][0], "Rushing Yards") and not has(d["RB"][0], "Anytime TD") and not has(d["RB"][0], "Rush + Rec Yards"), "his rushing, combined-yards and touchdown legs are not")
        check(not has(d["WR"][0], "Interceptions"), "a market outside the passing game's overs is not")
        other = next((t for t in sorted(by) if t != team and FE.backup_qb(t) is None and by[t].get("WR")), None)
        if other: check(not any(f["tag"] == "Backup QB" for f in FE.leg({"player": by[other]["WR"][0], "market": "Receiving Yards", "line": 1, "team": other, "opp": FE.PROJ[by[other]["WR"][0]].get("opp")})), f"{other} (no stand-in): nothing flagged")
        txt = next(f["txt"] for f in FE.leg({"player": d["WR"][0], "market": "Receiving Yards", "line": 1, "team": team, "opp": opp}) if f["tag"] == "Backup QB")
        check(qb in txt and "#28 of 32" in txt and "House rule" in txt, "the note names the quarterback, the rank and the rule")
        FE._bqb.pop(team, None)
        now = {t: FE.backup_qb(t) for t in sorted(FE.PPG)}
        print("this week:", "; ".join(f"{t} {(v['qb'] or 'unsettled')} for {v['for']} (#{v['rank']})" for t, v in now.items() if v) or "no stand-in on a bottom-12 offense")
print("backup qb:", "all checks passed" if not fails else f"{len(fails)} FAILED"); sys.exit(1 if fails else 0)
