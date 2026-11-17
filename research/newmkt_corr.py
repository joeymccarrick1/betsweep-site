#!/usr/bin/env python3
"""research/newmkt_corr.py - same-game correlations for the four markets added 11/5 (Passing TDs, Completions, Interceptions, Rush
Attempts), which had no correlation code: a quarterback's 2+ passing TDs and his 225+ yards were priced as unrelated legs (owner 11/17:
"Fix the 2 open things").

Data: in/stats_player_week_<season>.csv (nflverse, regular season) and in/games.csv (scores), seasons 2024 and 2025 - the two the
sheet's own table quotes. One quarterback per team-game (most attempts, 15+), backs with 8+ carries, wide receivers with 4+ targets,
tight ends with 3+.

Latent correlation of two stats = 2 sin(pi/6 x Spearman's rank correlation) - the Gaussian-copula link, so no line has to be chosen.
A touchdown leg is a yes / no, so pairs with one use the tetrachoric correlation (stat above its median vs scored).
Same player: the mean of the two seasons. Teammates and opponents: the mean x 0.9. (The sheet's older rows use x 0.75 after a 2025
lift test of their own; for these pairs the unshrunk number reproduces the real joint hit rates at typical lines - QB 2+ TDs with
225+ yards: real 30.9%, independent 22.1%, rho 0.50 gives 30.4%; QB 2+ TDs with a receiver's TD: real 22.2%, rho 0.55 gives 22.1%;
back 15+ carries with 60+ yards: real 33.3%, rho 0.74 gives 32.9% - so only a light shrink is kept against two-season noise.)
Pairs under 0.05 either way are left out (they price as unrelated, which is what a missing row means).
Stat vs own-team margin / game total (glcorr.json): plain mean, as that file does.

    python3 research/newmkt_corr.py            prints the check rows (pairs the sheet already has) and the new rows
    python3 research/newmkt_corr.py --write    also writes research/newmkt_corr.json: {"rows": [[key, rho, evidence]], "gl": {code: {...}}}
"""
import csv, json, math, os, sys
import numpy as np
from scipy import stats as SS
from scipy.stats import multivariate_normal, norm
from scipy.optimize import brentq
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); IN = os.path.join(HERE, "in")
SEASONS = (2024, 2025)

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0

def load(season):
    """{(week, team): {"qb": row, "rb": [rows], "wr": [rows], "te": [rows], "opp": team, "margin": pts, "total": pts}}"""
    G = {}
    for r in csv.DictReader(open(os.path.join(IN, "games.csv"), encoding="utf-8")):
        if int(r["season"]) != season or r["game_type"] != "REG" or r["result"] in ("", "NA"): continue
        hs, as_ = num(r["home_score"]), num(r["away_score"]); w = int(r["week"])
        G[(w, r["home_team"])] = {"opp": r["away_team"], "margin": hs - as_, "total": hs + as_, "qb": None, "rb": [], "wr": [], "te": []}
        G[(w, r["away_team"])] = {"opp": r["home_team"], "margin": as_ - hs, "total": hs + as_, "qb": None, "rb": [], "wr": [], "te": []}
    for r in csv.DictReader(open(os.path.join(IN, f"stats_player_week_{season}.csv"), encoding="utf-8")):
        if r.get("season_type") != "REG": continue
        k = (int(r["week"]), r["team"]); g = G.get(k)
        if not g: continue
        x = {"n": r["player_display_name"], "PASS": num(r["passing_yards"]), "PTD": num(r["passing_tds"]), "CMP": num(r["completions"]), "INT": num(r["passing_interceptions"]),
             "att": num(r["attempts"]), "ATT": num(r["carries"]), "RUSH": num(r["rushing_yards"]), "TD": 1.0 if num(r["rushing_tds"]) + num(r["receiving_tds"]) > 0 else 0.0,
             "REC": num(r["receptions"]), "RECYDS": num(r["receiving_yards"]), "tg": num(r["targets"])}
        p = r["position"]
        if p == "QB" and x["att"] >= 15 and (g["qb"] is None or x["att"] > g["qb"]["att"]): g["qb"] = x
        elif p == "RB" and x["ATT"] >= 8: g["rb"].append(x)
        elif p == "WR" and x["tg"] >= 4: g["wr"].append(x)
        elif p == "TE" and x["tg"] >= 3: g["te"].append(x)
    return G

def latent(a, b):
    """latent (Gaussian copula) correlation of two samples; tetrachoric when either side is a yes / no"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 80: return None
    bin_a, bin_b = set(np.unique(a)) <= {0.0, 1.0}, set(np.unique(b)) <= {0.0, 1.0}
    if not (bin_a or bin_b):
        rs = SS.spearmanr(a, b)[0]; return float(2 * math.sin(math.pi * rs / 6))
    A = a > 0 if bin_a else a > np.median(a); B = b > 0 if bin_b else b > np.median(b)
    pa, pb, pab = A.mean(), B.mean(), (A & B).mean()
    if min(pa, pb, 1 - pa, 1 - pb) < 0.02: return None
    h, k = norm.ppf(pa), norm.ppf(pb)
    f = lambda r: multivariate_normal.cdf([h, k], mean=[0, 0], cov=[[1, r], [r, 1]]) - pab
    try: return float(brentq(f, -0.95, 0.95, xtol=1e-4))
    except ValueError: return None

def pairs(G, rel, pa, sa, pb, sb):
    """the two samples for <rel>|<pa>_<sa>|<pb>_<sb>; pa / pb in qb rb wr te"""
    A, B = [], []
    def people(g, p): return ([g["qb"]] if g["qb"] else []) if p == "qb" else g[p]
    for (w, tm), g in G.items():
        if rel == "SP":
            for x in people(g, pa): A.append(x[sa]); B.append(x[sb])
        elif rel == "TM":
            for x in people(g, pa):
                for y in people(g, pb):
                    if x is not y: A.append(x[sa]); B.append(y[sb])
        else:
            o = G.get((w, g["opp"]))
            if not o: continue
            for x in people(g, pa):
                for y in people(o, pb): A.append(x[sa]); B.append(y[sb])
    return A, B

def est(rel, pa, sa, pb, sb):
    out = []
    for s in SEASONS:
        a, b = pairs(DATA[s], rel, pa, sa, pb, sb); out.append((latent(a, b), len(a)))
    return out

DATA = {s: load(s) for s in SEASONS}
def key(rel, pa, sa, pb, sb):
    c = sorted([f"{pa.upper()}_{sa}", f"{pb.upper()}_{sb}"]); return f"{rel}|{c[0]}|{c[1]}"
def row(rel, pa, sa, pb, sb, shrink=None):
    e = est(rel, pa, sa, pb, sb); vals = [v for v, n in e if v is not None]
    if not vals: return None
    shrink = (1.0 if rel == "SP" else 0.9) if shrink is None else shrink; m = sum(vals) / len(vals)
    return [key(rel, pa, sa, pb, sb), round(m * shrink, 2), "/".join(f"{v:.2f}" if v is not None else "n/a" for v, n in e) + (f" x{shrink:g}" if shrink != 1 else "") + f", nflverse 2024/2025 ({'/'.join(str(n) for v, n in e)} pairs; added 2026-11-17)"]

if __name__ == "__main__":
    print("CHECK against rows the sheet already has (its evidence in brackets):")
    for args, have in ((("TM", "qb", "PASS", "wr", "RECYDS"), "0.43/0.40"), (("TM", "qb", "PASS", "te", "RECYDS"), "0.27/0.37"), (("TM", "qb", "PASS", "rb", "RUSH"), "-0.08/-0.09"),
                       (("OPP", "qb", "PASS", "qb", "PASS"), "0.13/0.18"), (("SP", "qb", "RUSH", "qb", "TD"), "0.30/0.21 tetrachoric"), (("TM", "qb", "PASS", "wr", "TD"), "0.13/0.17")):
        e = est(*args); print("  %-26s %s   [%s]" % (key(*args), " / ".join("%.2f" % v if v is not None else "n/a" for v, n in e), have))
    NEW = []
    for sb in ("PASS", "CMP", "INT", "RUSH", "TD"): NEW.append(("SP", "qb", "PTD", "qb", sb))
    for sb in ("PASS", "INT", "RUSH"): NEW.append(("SP", "qb", "CMP", "qb", sb))
    NEW.append(("SP", "qb", "INT", "qb", "PASS"))
    for sb in ("RUSH", "TD", "REC", "RECYDS"): NEW.append(("SP", "rb", "ATT", "rb", sb))
    for st in ("PTD", "CMP", "INT"):
        for p, ss in (("wr", ("RECYDS", "REC", "TD")), ("te", ("RECYDS", "REC", "TD")), ("rb", ("RUSH", "RECYDS", "REC", "TD", "ATT"))):
            for sb in ss: NEW.append(("TM", "qb", st, p, sb))
    NEW.append(("TM", "qb", "PASS", "rb", "ATT"))
    for a, b in (("PTD", "PTD"), ("PTD", "PASS"), ("CMP", "CMP"), ("CMP", "PASS"), ("PTD", "CMP")): NEW.append(("OPP", "qb", a, "qb", b))
    rows = [r for r in (row(*a) for a in NEW) if r and abs(r[1]) >= 0.05]
    print("NEW ROWS:")
    for r in rows: print("  %-26s %5.2f   %s" % (r[0], r[1], r[2][:60]))
    gl = {}
    for code, (p, st) in (("QB_PTD", ("qb", "PTD")), ("QB_CMP", ("qb", "CMP")), ("QB_INT", ("qb", "INT")), ("RB_ATT", ("rb", "ATT")), ("QB_PASS", ("qb", "PASS")), ("RB_RUSH", ("rb", "RUSH"))):
        ms, ts, n = [], [], 0
        for s in SEASONS:
            a, mg, tt = [], [], []
            for g in DATA[s].values():
                for x in (([g["qb"]] if g["qb"] else []) if p == "qb" else g[p]): a.append(x[st]); mg.append(g["margin"]); tt.append(g["total"])
            ms.append(latent(a, mg)); ts.append(latent(a, tt)); n += len(a)
        gl[code] = {"n": n, "margin": round(sum(ms) / len(ms), 3), "total": round(sum(ts) / len(ts), 3)}
    print("STAT vs OWN MARGIN / GAME TOTAL (the last two are checks: glcorr.json has QB_PASS 0.253 / 0.398, RB_RUSH 0.217 / 0.053):")
    for c, v in gl.items(): print("  %-8s %s" % (c, v))
    if "--write" in sys.argv:
        json.dump({"built": "2026-11-17", "seasons": list(SEASONS), "rows": rows, "gl": {c: v for c, v in gl.items() if c not in ("QB_PASS", "RB_RUSH")}}, open(os.path.join(HERE, "research", "newmkt_corr.json"), "w"), indent=1)
        print("wrote research/newmkt_corr.json:", len(rows), "rows")
