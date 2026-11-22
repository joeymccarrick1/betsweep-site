"""Walk-forward test of the Premier League baseline.

  python -m sports.epl.backtest [--tune]      (BS_SPORTS_DATA = folder holding the fplei clone)

Team weights are chosen on 2025-26 and scored on 2026-27 to date (100 matches: a small sample, read it as a direction, not a verdict).
Benchmarks are the ones available without bookmaker prices: last season's home/draw/away rates, an Elo-only model (2025-26 only: the
2026-27 file has no Elo yet), and for players the plain per-appearance average and the 'scored in x of n' hit rate.
Nothing here is compared with FanDuel yet: there are no stored EPL prices to grade against.
"""
import copy, json, os, sys, warnings
import numpy as np
import pandas as pd
from . import data as ED, model as EM
from ..core import metrics as M, dist as D

warnings.simplefilter("ignore", pd.errors.PerformanceWarning)
TUNE, HOLD = 2026, 2027


def result(df):
    return np.where(df["home_score"] > df["away_score"], "H", np.where(df["home_score"] == df["away_score"], "D", "A"))


def team_eval(m, tg, P, seasons):
    wf = EM.add_markets(EM.walk_forward(m, tg, seasons, P), P["rho"])
    fin = m[m["finished"]].set_index("match_id")
    wf = wf.join(fin[["home_score", "away_score", "home_team_elo", "away_team_elo"]], on="match_id", how="inner")
    wf["res"] = result(wf)
    return wf


def elo_benchmark(m, season):
    """Home/draw/away from the Elo gap alone, fitted on the season before."""
    from sklearn.linear_model import LogisticRegression
    fin = m[m["finished"]].copy()
    tr, te = fin[fin["season"] == season - 1], fin[fin["season"] == season]
    if tr["home_team_elo"].isna().mean() > 0.05 or te["home_team_elo"].isna().mean() > 0.05:
        return None
    tr = tr.dropna(subset=["home_team_elo", "away_team_elo"])
    te = te.dropna(subset=["home_team_elo", "away_team_elo"])
    lr = LogisticRegression(C=10.0, max_iter=500).fit(((tr["home_team_elo"] - tr["away_team_elo"]) / 100.0).values.reshape(-1, 1), result(tr))
    pr = lr.predict_proba(((te["home_team_elo"] - te["away_team_elo"]) / 100.0).values.reshape(-1, 1))
    k = {c: i for i, c in enumerate(lr.classes_)}
    r = result(te)
    return {"matches": int(len(te)), "logloss": M.logloss_1x2(pr[:, k["H"]], pr[:, k["D"]], pr[:, k["A"]], r), "rps": M.rps_1x2(pr[:, k["H"]], pr[:, k["D"]], pr[:, k["A"]], r)}


def team_scores(wf, m, season):
    x = wf[wf["season"] == season]
    prev = m[m["finished"] & (m["season"] == season - 1)]
    pr = result(prev)
    b = [float((pr == k).mean()) for k in "HDA"]
    n = len(x)
    tot = x["home_score"] + x["away_score"]
    ptot = prev["home_score"] + prev["away_score"]
    both = ((x["home_score"] > 0) & (x["away_score"] > 0)).astype(float)
    pboth = float(((prev["home_score"] > 0) & (prev["away_score"] > 0)).mean())
    return {"matches": int(n),
            "h_d_a": {"logloss_model": M.logloss_1x2(x["home"], x["draw"], x["away"], x["res"]),
                      "logloss_last_season_rates": M.logloss_1x2(np.full(n, b[0]), np.full(n, b[1]), np.full(n, b[2]), x["res"]),
                      "rps_model": M.rps_1x2(x["home"], x["draw"], x["away"], x["res"]),
                      "rps_last_season_rates": M.rps_1x2(np.full(n, b[0]), np.full(n, b[1]), np.full(n, b[2]), x["res"]),
                      "said": {k: float(x[c].mean()) for k, c in (("H", "home"), ("D", "draw"), ("A", "away"))},
                      "happened": {k: float((x["res"] == k).mean()) for k in "HDA"},
                      "model_pick_home_or_away_won": float((np.where(x["home"] >= x["away"], "H", "A") == x["res"]).mean())},
            "goals_mae": {"model": (M.mae(x["home_score"], x["lam_home"]) + M.mae(x["away_score"], x["lam_away"])) / 2.0,
                          "league_average": (M.mae(x["home_score"], np.full(n, prev["home_score"].mean())) + M.mae(x["away_score"], np.full(n, prev["away_score"].mean()))) / 2.0},
            "over_2_5": {"brier_model": M.brier((tot >= 3).astype(float), x["over25"]), "brier_last_season_rate": M.brier((tot >= 3).astype(float), np.full(n, float((ptot >= 3).mean()))),
                         "said": float(x["over25"].mean()), "happened": float((tot >= 3).mean())},
            "both_score": {"brier_model": M.brier(both, x["btts"]), "brier_last_season_rate": M.brier(both, np.full(n, pboth)), "said": float(x["btts"].mean()), "happened": float(both.mean())}}


def tune_team(m, tg, log):
    P = copy.deepcopy(EM.PARAMS)
    for name, values in (("xg_blend", [0.0, 0.5, 0.7, 0.85, 1.0]), ("half_life", [120.0, 240.0, 365.0, 730.0]), ("k_games", [1.0, 2.0, 4.0, 8.0]),
                         ("rho", [0.0, -0.04, -0.08, -0.12])):
        best, best_v = None, None
        for v in values:
            q = dict(P); q[name] = v
            wf = team_eval(m, tg, q, [TUNE])
            ll = M.logloss_1x2(wf["home"], wf["draw"], wf["away"], wf["res"])
            log.append({"knob": name, "value": v, "logloss_1x2": round(ll, 5)})
            if best is None or ll < best - 1e-9:
                best, best_v = ll, v
        P[name] = best_v
    return P


def player_frame(m, tg, pm, P):
    wf_g = EM.walk_forward(m, tg, [TUNE, HOLD], P, "goals")
    wf_s = EM.walk_forward(m, tg, [TUNE, HOLD], P, "shots")
    p = EM.player_projections(pm, wf_g, wf_s, P)
    hist = p["prev_min"].fillna(0) + (p.groupby(["player_code", "season"], sort=False)["min"].cumsum() - p["min"])
    p["elig"] = p["started"].astype(bool) & (p["position"] != "Goalkeeper") & (hist >= 450) & p["env_goals"].notna()
    return p


def own_rate(p, col, line):
    h = (p[col] >= line).astype(float)
    hits = h.groupby([p["player_code"], p["season"]], sort=False).cumsum() - h
    return ((hits + 1.0) / (p["n_app"] + 2.0)).where(p["n_app"] >= 5)


def tune_player(m, tg, pm, P, log):
    for name, values in (("k_rate_min", [300.0, 600.0, 1200.0, 2400.0]), ("w_env", [0.0, 0.5, 1.0]), ("start_min_k", [1.0, 3.0, 6.0])):
        best, best_v = None, None
        for v in values:
            q = dict(P); q[name] = v
            p = player_frame(m, tg, pm, q)
            e = p[(p["season"] == TUNE) & p["elig"]]
            ll = M.logloss((e["goals"] >= 1).astype(float), e["p_goal"]) + 0.02 * M.mae(e["shots"], e["proj_shots"])
            log.append({"knob": name, "value": v, "goal_logloss_plus_shots": round(ll, 5)})
            if best is None or ll < best - 1e-9:
                best, best_v = ll, v
        P[name] = best_v
    return P


def player_scores(p, season, phis):
    e = p[(p["season"] == season) & p["elig"]]
    hit = (e["goals"] >= 1).astype(float)
    ob = own_rate(p, "goals", 1).loc[e.index]
    ok = ob.notna().values
    out = {"starts": int(len(e)), "anytime_scorer": {
        "legs_with_5_games": int(ok.sum()), "scored_rate": float(hit.mean()), "said": float(e["p_goal"].mean()),
        "brier_model": M.brier(hit[ok], e["p_goal"][ok]), "brier_no_matchup": M.brier(hit[ok], (1 - np.exp(-e["base_xg"]))[ok]), "brier_own_scoring_rate": M.brier(hit[ok], ob[ok]),
        "logloss_model": M.logloss(hit[ok], e["p_goal"][ok]), "logloss_own_scoring_rate": M.logloss(hit[ok], ob[ok]),
        "calibration": M.calibration(hit, e["p_goal"], bins=(0, .05, .1, .15, .2, .3, .4, .5, 1.0001)).round(4).to_dict("records")}}
    e1 = e[e["n_app"] >= 1]
    for s in ("shots", "sot"):
        out[s] = {"mae_model": M.mae(e1[s], e1["proj_" + s]), "mae_per_appearance_avg": M.mae(e1[s], e1["avg_" + s]), "phi": phis[s], "lines": []}
        for L in (1, 2, 3):
            pm_ = D.p_at_least(L, e["proj_" + s].values, "qp", phi=phis[s])
            ob = own_rate(p, s, L).loc[e.index]
            ok = ob.notna().values
            h = (e[s] >= L).astype(float).values
            out[s]["lines"].append({"line": f"{L}+", "legs": int(ok.sum()), "hit_rate": float(h[ok].mean()), "brier_model": M.brier(h[ok], pm_[ok]), "brier_own_hit_rate": M.brier(h[ok], ob.values[ok])})
    return out


def main():
    m = ED.load_matches()
    tg = ED.team_games(m)
    pm = ED.load_player_matches(m)
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backtests", "epl.json")
    log = {"team": [], "player": []}
    P = copy.deepcopy(EM.PARAMS)
    if "--tune" in sys.argv:
        P = tune_team(m, tg, log["team"])
        P = tune_player(m, tg, pm, P, log["player"])
    else:
        try: log = json.load(open(out)).get("tuning_log", log)
        except Exception: pass
    wf = team_eval(m, tg, P, [TUNE, HOLD])
    res = {"params": P, "tuned_on": "2025-26", "holdout": "2026-27 to date", "data_through": str(m.loc[m["finished"], "date"].max().date()), "tuning_log": log,
           "team": {str(s): team_scores(wf, m, s) for s in (TUNE, HOLD)}, "elo_only_benchmark": {str(s): elo_benchmark(m, s) for s in (TUNE, HOLD)}}
    p = player_frame(m, tg, pm, P)
    tr = p[(p["season"] == TUNE) & p["elig"]]
    phis = {s: D.fit_phi(tr[s], tr["proj_" + s]) for s in ("shots", "sot")}
    res["player"] = {str(s): player_scores(p, s, phis) for s in (TUNE, HOLD)}
    teams = ED.load_teams()
    tab, g = EM.ratings_table(m, tg, P)
    tab.insert(0, "club", tab["team"].map(lambda c: teams[c]["name"]))
    res["grid_today"] = {"league_goals_per_team": g["L"], "home_edge": g["H"], "clubs": tab.round(3).to_dict("records")}
    json.dump(res, open(out, "w"), indent=1, default=float)
    print("wrote", out); print(json.dumps(P))
    for s in (TUNE, HOLD):
        t = res["team"][str(s)]; e = res["elo_only_benchmark"][str(s)]
        print(s, t["matches"], "matches | H/D/A log loss: model %.4f, last season's rates %.4f%s | model's home-or-away pick won %.3f" % (t["h_d_a"]["logloss_model"], t["h_d_a"]["logloss_last_season_rates"], (", Elo only %.4f" % e["logloss"]) if e else "", t["h_d_a"]["model_pick_home_or_away_won"]))
        print("    goals MAE %.3f (league avg %.3f) | over 2.5 Brier %.4f (rate %.4f) | both score Brier %.4f (rate %.4f)" % (t["goals_mae"]["model"], t["goals_mae"]["league_average"], t["over_2_5"]["brier_model"], t["over_2_5"]["brier_last_season_rate"], t["both_score"]["brier_model"], t["both_score"]["brier_last_season_rate"]))
        pl = res["player"][str(s)]; a = pl["anytime_scorer"]
        print("    players: %d starts | scorer Brier model %.4f, no matchup %.4f, own rate %.4f (legs %d; said %.3f, scored %.3f)" % (pl["starts"], a["brier_model"], a["brier_no_matchup"], a["brier_own_scoring_rate"], a["legs_with_5_games"], a["said"], a["scored_rate"]))
        for k in ("shots", "sot"):
            print("    %s MAE model %.3f vs average %.3f | " % (k, pl[k]["mae_model"], pl[k]["mae_per_appearance_avg"]) + " ".join("%s %.4f/%.4f" % (r["line"], r["brier_model"], r["brier_own_hit_rate"]) for r in pl[k]["lines"]))


if __name__ == "__main__":
    main()
