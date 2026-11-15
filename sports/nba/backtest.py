"""Walk-forward test of the NBA baseline.

  python -m sports.nba.backtest            (BS_SPORTS_DATA = folder holding nba_player_box_<season>.csv)

Weights are chosen on 2025-26 only, then frozen and scored on 2026-27 to date, which they never saw. Every projection uses only
earlier games. One caveat that the numbers carry: the minutes budget uses the players who actually took the floor, so it grades the
projection as it would stand once the night's inactives are known, not the morning number.
"""
import copy, json, os, sys
import numpy as np
import pandas as pd
from . import data as ND, model as NM
from ..core import metrics as M, dist as D

TUNE, HOLD = 2026, 2027
MAIN = ["pts", "reb", "ast", "fg3"]


def eligible(p):
    """Rotation players (the ones books hang props on), by a rule that does not depend on the weights being tested."""
    role = p["season_min"].where(p["n"] >= 3, p["prev_min"])
    return p["has_base"] & (role >= 15)


def score(p, season):
    e = p[(p["season"] == season) & eligible(p)]
    out = {"rows": int(len(e)), "min": M.mae(e["min"], e["proj_min"])}
    for s in NM.STATS:
        out[s] = M.mae(e[s], e["proj_" + s])
    return out


def tune(d, log):
    P = copy.deepcopy(NM.PARAMS)

    def run(**kw):
        q = copy.deepcopy(P)
        for k, v in kw.items():
            if isinstance(v, tuple):
                q[k] = dict(q[k]); q[k][v[0]] = v[1]
            else:
                q[k] = v
        return score(NM.project(d[d["season"] <= TUNE], q), TUNE)

    def pick(name, values, metric, sub=None):
        best, best_v = None, None
        for v in values:
            r = run(**{name: (sub, v) if sub else v})[metric]
            log.append({"knob": name + (":" + sub if sub else ""), "value": v, "metric": metric, "mae": round(r, 4)})
            if best is None or r < best - 1e-9:
                best, best_v = r, v
        if sub:
            P[name] = dict(P[name]); P[name][sub] = best_v
        else:
            P[name] = best_v
        return best_v

    pick("w_recent_min", [0.0, 0.25, 0.5, 0.75, 1.0], "min")
    pick("k_min", [0.0, 1.0, 3.0, 6.0], "min")
    pick("c_budget", [0.0, 0.5, 0.75, 1.0], "min")
    pick("cap_min", [38.0, 40.0, 42.0], "min")
    pick("k_rate", [150.0, 400.0, 800.0, 1500.0], "pts")
    pick("w_recent_rate", [0.0, 0.15, 0.3], "pts")
    pick("k_def", [200.0, 400.0, 1000.0], "pts")
    for s in NM.STATS:
        pick("w_match", [0.0, 0.25, 0.5, 0.75, 1.0], s, sub=s)
    for s in NM.STATS:
        pick("u_total", [0.0, 0.25, 0.5, 0.75, 1.0], s, sub=s)
    return P


def hit_rate_benchmark(p, stat, line):
    """What a bettor sees on a prop page: how often he has cleared this line so far this season (needs 5 games; smoothed (h+1)/(n+2))."""
    h = (p[stat] >= line).astype(float)
    g = [p["athlete_id"], p["season"]]
    hits = h.groupby(g, sort=False).cumsum() - h
    return ((hits + 1.0) / (p["n"] + 2.0)).where(p["n"] >= 5)


def main():
    d = ND.load([2025, 2026, 2027])
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backtests", "nba.json")
    log = []
    if "--tune" in sys.argv:                      # about ten minutes; the result is then written into model.PARAMS by hand
        P = tune(d, log)
    else:
        P = copy.deepcopy(NM.PARAMS)
        try: log = json.load(open(out)).get("tuning_log", [])
        except Exception: log = []
    p = NM.project(d, P)
    res = {"params": P, "tuned_on": "2025-26", "holdout": "2026-27 to date", "data_through": str(d["date"].max().date()), "tuning_log": log, "seasons": {}}
    for season, label in ((TUNE, "2025-26 (weights chosen here)"), (HOLD, "2026-27 to date (never seen by the weights)")):
        e = p[(p["season"] == season) & eligible(p)]
        e1 = e[e["n"] >= 1]
        r = {"label": label, "player_games": int(len(e1)), "minutes": {
            "season_avg": M.mae(e1["min"], e1["season_min"]), "baseline": M.mae(e1["min"], e1["base_min"]), "with_budget": M.mae(e1["min"], e1["proj_min"])}}
        for s in NM.STATS + ["pra"]:
            if s == "pra":
                avg = e1["avg_pts"] + e1["avg_reb"] + e1["avg_ast"]; l10 = e1["l10_pts"] + e1["l10_reb"] + e1["l10_ast"]; b = e1["base_pts"] + e1["base_reb"] + e1["base_ast"]
            else:
                avg, l10, b = e1["avg_" + s], e1["l10_" + s], e1["base_" + s]
            r[s] = {"season_avg": M.mae(e1[s], avg), "last10": M.mae(e1[s], l10), "baseline_only": M.mae(e1[s], b), "model": M.mae(e1[s], e1["proj_" + s]),
                    "bias": M.bias(e1[s], e1["proj_" + s])}
            r[s]["gain_vs_season_avg_pct"] = 100.0 * (1.0 - r[s]["model"] / r[s]["season_avg"])
        res["seasons"][str(season)] = r
    # hit chances: spread fitted on 2025-26 errors, graded on 2026-27
    tr = p[(p["season"] == TUNE) & eligible(p) & p["proj_pts"].notna()]
    ho = p[(p["season"] == HOLD) & eligible(p) & p["proj_pts"].notna()]
    res["hit_chances"] = {}
    for s in MAIN:
        phi = D.fit_phi(tr[s], tr["proj_" + s])
        rows = []
        for L in NM.LADDERS[s]:
            pm = D.p_at_least(L, ho["proj_" + s].values, "qp", phi=phi)
            pp = D.p_at_least(L, ho["proj_" + s].values, "poisson")
            hb = hit_rate_benchmark(p, s, L).loc[ho.index]
            ok = hb.notna().values
            hit = (ho[s] >= L).astype(float).values
            rows.append({"line": f"{L}+", "legs": int(ok.sum()), "hit_rate": float(hit[ok].mean()),
                         "brier_model": M.brier(hit[ok], pm[ok]), "brier_poisson": M.brier(hit[ok], pp[ok]), "brier_own_hit_rate": M.brier(hit[ok], hb.values[ok]),
                         "logloss_model": M.logloss(hit[ok], pm[ok]), "logloss_own_hit_rate": M.logloss(hit[ok], hb.values[ok])})
        allp = np.concatenate([D.p_at_least(L, ho["proj_" + s].values, "qp", phi=phi) for L in NM.LADDERS[s]])
        allh = np.concatenate([(ho[s] >= L).astype(float).values for L in NM.LADDERS[s]])
        res["hit_chances"][s] = {"phi": phi, "lines": rows, "calibration": M.calibration(allh, allp).round(4).to_dict("records"),
                                 "brier_all_lines": {"model": float(np.mean([r["brier_model"] for r in rows])), "own_hit_rate": float(np.mean([r["brier_own_hit_rate"] for r in rows]))}}
    json.dump(res, open(out, "w"), indent=1, default=float)
    print("wrote", out)
    print(json.dumps({k: v for k, v in P.items()}, default=float))
    for season, r in res["seasons"].items():
        print(season, r["label"], r["player_games"], "player-games")
        print("  minutes  season avg %.3f | baseline %.3f | with budget %.3f" % (r["minutes"]["season_avg"], r["minutes"]["baseline"], r["minutes"]["with_budget"]))
        for s in NM.STATS + ["pra"]:
            x = r[s]; print("  %-4s season avg %.3f | last10 %.3f | baseline %.3f | model %.3f  (%.1f%% better than season avg, bias %+.2f)" % (s, x["season_avg"], x["last10"], x["baseline_only"], x["model"], x["gain_vs_season_avg_pct"], x["bias"]))
    for s in MAIN:
        h = res["hit_chances"][s]; print(s, "phi %.2f" % h["phi"])
        for row in h["lines"]:
            print("   %-4s legs %5d hit %.3f | Brier model %.4f  poisson %.4f  own hit rate %.4f" % (row["line"], row["legs"], row["hit_rate"], row["brier_model"], row["brier_poisson"], row["brier_own_hit_rate"]))


if __name__ == "__main__":
    main()
