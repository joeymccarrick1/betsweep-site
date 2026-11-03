#!/usr/bin/env python3
"""rztd.py - red-zone / opportunity anytime-TD model (owner 11/1 study, shipped 11/3).

Per player: expected TDs lambda = exp(b . x), x = [1, log(red-zone opportunity share), log(goal-line share), log(team implied points),
log(opportunities per game + 1), log(team red-zone trips per game)], P(anytime TD) = 1 - exp(-lambda). Features are recency-weighted
(0.85/game) from this season's games before WEEK with last season's totals as a ~3-game prior; the coefficients are refit every run on
2025 weeks 4-18 + 2026 weeks < WEEK (Poisson regression, 5 s). Team implied points for WEEK come from in/games.csv (nflverse schedule:
spread_line = home margin, total_line) - the same closing-line source as the game-line backtest.

Validation (gen/research/rztd_study.txt, 11/3): on the 344 graded FanDuel anytime-TD legs of Weeks 6-8, log loss rz 0.6057 vs raw
model 0.6124 vs FanDuel 0.6191; the 50/50 average of rz and raw (what the builder now uses for Anytime TD) 0.6057 / Brier 0.2089 (best),
better than raw in Weeks 6 and 7, 0.002 worse in Week 8; bootstrap P(avg beats raw) = 0.94; calibration by decile within 3-9 pts.
Revert rule: if the raw model beats the average two graded weeks running (calib_market.py prints both), drop RZ_W to 0.

Inputs: in/pbp_2025.csv.gz, in/pbp_2026.csv.gz (downloaded from nflverse if missing), in/games.csv.
Output: out/rztd.json = {"week": W, "coef": [...], "players": {"J.Jacobs|GB": {"p": 0.46, "lam": 0.62, "name": "J.Jacobs", "team": "GB",
         "rz_share": 0.31, "gl_share": 0.40, "opp_pg": 19.4, "impl": 24.5, "g": 7.2}}}
Usage: python3 rztd.py <WEEK>
"""
import gzip, csv, json, math, os, sys, re, subprocess
from collections import defaultdict
import numpy as np
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
TEAMFIX = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
RZ_W = 0.5   # weight of the rz model in the builder's anytime-TD probability (rest = the projection model's Poisson lambda)
DECAY = 0.85

def fetch(season):
    p = os.path.join(IN, f"pbp_{season}.csv.gz")
    if not os.path.exists(p) or os.path.getsize(p) < 1_000_000:
        subprocess.run(["curl", "-sSLf", "-o", p, f"https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz"], check=True)
    return p

def load(season):
    pg = defaultdict(lambda: {"car": 0, "tgt": 0, "rz": 0, "gl": 0, "td": 0, "team": None, "name": None})
    tg = defaultdict(lambda: {"rzp": 0, "trips": set(), "impl": None, "plays": 0})
    with gzip.open(fetch(season), "rt") as f:
        for r in csv.DictReader(f):
            if r["season_type"] != "REG" or r["play_type"] not in ("run", "pass"): continue
            w = int(r["week"]); t = TEAMFIX.get(r["posteam"], r["posteam"])
            if not t: continue
            try: yl = float(r["yardline_100"])
            except Exception: continue
            T = tg[(w, t)]; T["plays"] += 1
            if T["impl"] is None:
                try:
                    tot = float(r["total_line"]); sp = float(r["spread_line"]); home = r["home_team"] == r["posteam"]
                    T["impl"] = tot / 2 + (sp / 2 if home else -sp / 2)
                except Exception: pass
            if yl <= 20: T["rzp"] += 1; T["trips"].add(r["fixed_drive"])
            who = kind = None
            if r["play_type"] == "run" and r["rusher_player_id"]: who, kind = (r["rusher_player_id"], r["rusher_player_name"]), "car"
            elif r["play_type"] == "pass" and r["receiver_player_id"]: who, kind = (r["receiver_player_id"], r["receiver_player_name"]), "tgt"
            if not who: continue
            P = pg[(w, who[0])]; P[kind] += 1; P["team"] = t; P["name"] = who[1]
            if yl <= 20: P["rz"] += 1
            if yl <= 5: P["gl"] += 1
            if (r["rush_touchdown"] == "1" and kind == "car") or (r["pass_touchdown"] == "1" and kind == "tgt"): P["td"] += 1
    return pg, tg

def season_prior(pg, tg):
    pr = defaultdict(lambda: {"rz": 0, "gl": 0, "opp": 0, "g": 0, "rzp": 0, "plays": 0})
    for (w, p), P in pg.items():
        T = tg.get((w, P["team"]))
        if not T: continue
        q = pr[p]; q["rz"] += P["rz"]; q["gl"] += P["gl"]; q["opp"] += P["car"] + P["tgt"]; q["g"] += 1; q["rzp"] += T["rzp"]; q["plays"] += T["plays"]
    return pr

def features(pg, tg, w, pid, team, impl, prior=None):
    num = {"rz": 0.0, "gl": 0.0, "opp": 0.0, "g": 0.0}; den = 0.0
    for (ww, p), P in pg.items():
        if p != pid or ww >= w: continue
        T = tg.get((ww, P["team"]))
        if not T: continue
        wt = DECAY ** (w - 1 - ww)
        num["rz"] += wt * P["rz"]; num["gl"] += wt * P["gl"]; num["opp"] += wt * (P["car"] + P["tgt"]); num["g"] += wt; den += wt * T["rzp"]
    if prior and prior["g"]:
        k = 3.0 / prior["g"]; num["rz"] += k * prior["rz"]; num["gl"] += k * prior["gl"]; num["opp"] += k * prior["opp"]; num["g"] += 3.0; den += k * prior["rzp"]
    if num["g"] <= 0: return None
    trips = np.mean([len(T["trips"]) for (ww, t), T in tg.items() if t == team and ww < w] or [3.0])
    return {"rz_share": num["rz"] / max(den, 1), "gl_share": num["gl"] / max(den * 0.35, 1), "opp_pg": num["opp"] / num["g"], "impl": impl if impl else 21.0, "trips": float(trips), "g": num["g"]}

def X(f): return np.array([1.0, math.log(f["rz_share"] + 0.01), math.log(f["gl_share"] + 0.01), math.log(f["impl"]), math.log(f["opp_pg"] + 1), math.log(f["trips"] + 0.5)])
def fit(Xs, ys):
    Xs = np.array(Xs); ys = np.array(ys, float)
    def nll(b): lam = np.exp(Xs @ b); return np.sum(lam - ys * np.log(lam + 1e-12)) + 0.01 * np.sum(b[1:] ** 2)
    return minimize(nll, np.zeros(Xs.shape[1]), method="L-BFGS-B").x

def dataset(pg, tg, weeks, prior):
    rows = []
    for (w, p), P in pg.items():
        if w not in weeks or P["car"] + P["tgt"] < 1: continue
        T = tg.get((w, P["team"])); f = features(pg, tg, w, p, P["team"], T["impl"] if T else None, prior.get(p))
        if f is None or f["g"] < 2: continue
        rows.append((X(f), min(P["td"], 3)))
    return rows

def build(week):
    pg25, tg25 = load(2025); pg26, tg26 = load(2026); prior = season_prior(pg25, tg25)
    train = dataset(pg25, tg25, set(range(4, 19)), {}) + dataset(pg26, tg26, set(range(1, week)), prior)
    b = fit([x for x, _ in train], [y for _, y in train])
    # this week's implied team points from the schedule
    impl = {}
    try:
        for g in csv.DictReader(open(os.path.join(IN, "games.csv"))):
            if g["season"] == "2026" and str(g["week"]) == str(week) and g.get("total_line") not in ("", "NA", None):
                tot = float(g["total_line"]); sp = float(g["spread_line"]); h, a = TEAMFIX.get(g["home_team"], g["home_team"]), TEAMFIX.get(g["away_team"], g["away_team"])
                impl[h] = tot / 2 + sp / 2; impl[a] = tot / 2 - sp / 2
    except Exception as e: print("warn: no schedule lines:", e)
    seen = {}
    for (w, p), P in pg26.items():
        if w >= week: continue
        if p not in seen or w > seen[p][0]: seen[p] = (w, P["team"], P["name"])
    out = {}
    for p, (w, team, name) in seen.items():
        f = features(pg26, tg26, week, p, team, impl.get(team), prior.get(p))
        if f is None or f["g"] < 2 or f["opp_pg"] < 2: continue
        lam = float(math.exp(X(f) @ b)); out[f"{name}|{team}"] = {"p": round(1 - math.exp(-lam), 4), "lam": round(lam, 3), "name": name, "team": team,
            "rz_share": round(f["rz_share"], 3), "gl_share": round(f["gl_share"], 3), "opp_pg": round(f["opp_pg"], 1), "impl": round(f["impl"], 1), "g": round(f["g"], 1)}
    json.dump({"week": week, "coef": [round(float(x), 4) for x in b], "rz_w": RZ_W, "players": out}, open(os.path.join(OUT, "rztd.json"), "w"))
    print(f"wrote out/rztd.json: {len(out)} players for week {week}; coef {np.round(b, 3).tolist()}; train n {len(train)}; implied pts for {len(impl)} teams")
    return out

def lookup(table, name, team):
    """Match a model-spelled name ('Jaxon Smith-Njigba') to the pbp spelling ('J.Smith-Njigba') on the same team."""
    def nn(x): return re.sub(r"[^a-z]", "", re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", "", str(x).strip().lower()))
    parts = str(name).split()
    if not parts: return None
    fi, ln = parts[0][:1].lower(), nn(" ".join(parts[1:]))
    tm = TEAMFIX.get(team, team)
    for k, v in table.items():
        if v["team"] != tm: continue
        m = str(v["name"]).split(".", 1)
        if len(m) == 2 and m[0][:1].lower() == fi and nn(m[1]) == ln: return v
    return None

if __name__ == "__main__":
    build(int(sys.argv[1]))
