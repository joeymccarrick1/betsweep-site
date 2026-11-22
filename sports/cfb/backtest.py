"""Walk-forward test of the college football baseline.

  python -m sports.cfb.backtest [--tune]      (BS_SPORTS_DATA = folder holding cfb_schedule_<year>.csv and cfb_pbp_<year>.csv)

Game lines are graded against DraftKings' spread and total stored in the play-by-play (FanDuel's are not stored anywhere yet).
Weights are chosen on 2025 and scored on 2026 to date. The honest question for a game-line model is not 'is it close to the score'
but 'does it add anything to the book's number', so the test reports both.
"""
import copy, json, os, sys
import numpy as np
import pandas as pd
from . import data as CD, model as CM
from ..core import metrics as M

TUNE, HOLD = 2025, 2026
HIST = [2022, 2023, 2024, 2025, 2026]


def with_lines(wf, lines):
    x = wf.merge(lines[["game_id", "spread", "over_under", "home_team_pregame_elo", "away_team_pregame_elo"]], on="game_id", how="left")
    x["book_margin"] = -x["spread"]
    return x


def ats(x, thr, kind="side"):
    """Record when the model disagrees with the book by at least `thr` points. Pushes dropped. 52.4% is break-even at -110."""
    if kind == "side":
        diff, res = x["model_margin"] - x["book_margin"], x["margin"] - x["book_margin"]
    else:
        diff, res = x["model_total"] - x["over_under"], x["total"] - x["over_under"]
    pick = np.sign(diff.where(diff.abs() >= thr))
    ok = pick.notna() & (res != 0) & res.notna()
    wins = int(((pick[ok] * np.sign(res[ok])) > 0).sum())
    n = int(ok.sum())
    return {"min_gap": thr, "bets": n, "wins": wins, "win_pct": (wins / n if n else None)}


def line_scores(x):
    y = x[x["spread"].notna() & x["over_under"].notna()]
    out = {"games_with_a_line": int(len(y)),
           "margin_mae": {"model": M.mae(y["margin"], y["model_margin"]), "book": M.mae(y["margin"], y["book_margin"])},
           "total_mae": {"model": M.mae(y["total"], y["model_total"]), "book": M.mae(y["total"], y["over_under"])},
           "winner_picked": {"model": float(((y["model_margin"] > 0) == (y["margin"] > 0)).mean()), "book": float(((y["book_margin"] > 0) == (y["margin"] > 0))[y["book_margin"] != 0].mean())},
           "against_the_spread": [ats(y, t) for t in (0.0, 3.0, 5.0, 7.0, 10.0)], "totals": [ats(y, t, "total") for t in (0.0, 3.0, 5.0, 7.0)]}
    # does the model add anything to the book? regress the book's miss on the model's disagreement
    d = (y["model_margin"] - y["book_margin"]).values
    r = (y["margin"] - y["book_margin"]).values
    out["weight_on_model_vs_book"] = {"margin": float((d * r).sum() / (d * d).sum())}
    d2 = (y["model_total"] - y["over_under"]).values
    r2 = (y["total"] - y["over_under"]).values
    out["weight_on_model_vs_book"]["total"] = float((d2 * r2).sum() / (d2 * d2).sum())
    f = y[y["fbs_both"]]
    out["fbs_vs_fbs"] = {"games": int(len(f)), "margin_mae_model": M.mae(f["margin"], f["model_margin"]), "margin_mae_book": M.mae(f["margin"], f["book_margin"])}
    e = y.dropna(subset=["home_team_pregame_elo", "away_team_pregame_elo"])
    if len(e) > 50:
        out["elo_games"] = int(len(e))
        out["_elo"] = (e["home_team_pregame_elo"] - e["away_team_pregame_elo"]).values.tolist(), e["margin"].values.tolist()
    return out


def tune(g, lines, log):
    P = copy.deepcopy(CM.PARAMS)
    for name, values in (("half_life", [150.0, 300.0, 500.0, 900.0]), ("k_games", [1.0, 2.0, 4.0, 8.0]), ("cap", [49.0, 56.0, 63.0, 80.0])):
        best, best_v = None, None
        for v in values:
            q = dict(P); q[name] = v
            x = with_lines(CM.walk_forward(g, [TUNE], q), lines)
            y = x[x["spread"].notna()]
            e = M.mae(y["margin"], y["model_margin"])
            log.append({"knob": name, "value": v, "margin_mae": round(e, 4)})
            if best is None or e < best - 1e-9:
                best, best_v = e, v
        P[name] = best_v
    x = CM.walk_forward(g, [TUNE], P)
    P["sd_margin"] = float(np.std(x["margin"] - x["model_margin"]))
    return P


def player_scores(p, season):
    out = {}
    for stat, (_, floor) in CM.PLAYER_STATS.items():
        e = p[(p["season"] == season) & (p["n"] >= 3) & (p["avg_" + stat] >= floor) & p["proj_" + stat].notna()]
        out[stat] = {"player_games": int(len(e)), "mae_season_avg": M.mae(e[stat], e["avg_" + stat]), "mae_baseline": M.mae(e[stat], e["base_" + stat]),
                     "mae_with_matchup": M.mae(e[stat], e["proj_" + stat])}
        out[stat]["gain_vs_season_avg_pct"] = 100.0 * (1 - out[stat]["mae_with_matchup"] / out[stat]["mae_season_avg"])
    return out


def tune_player(pg, ts, g, P, log):
    for name, values in (("w_recent", [0.0, 0.15, 0.3, 0.5]), ("w_match", [0.0, 0.25, 0.5, 0.75, 1.0])):
        best, best_v = None, None
        for v in values:
            q = dict(P); q[name] = v
            sc = player_scores(CM.player_projections(pg, ts, g, q), TUNE)
            e = float(np.mean([sc[s]["mae_with_matchup"] / sc[s]["mae_season_avg"] for s in sc]))
            log.append({"knob": name, "value": v, "mae_vs_season_avg": round(e, 5)})
            if best is None or e < best - 1e-9:
                best, best_v = e, v
        P[name] = best_v
    return P


def main():
    g = CD.load_games(HIST)
    lines = CD.load_lines([TUNE, HOLD])
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backtests", "cfb.json")
    log = {"lines": [], "player": []}
    P = copy.deepcopy(CM.PARAMS)
    pg, ts = CD.load_player_games([TUNE, HOLD]), CD.load_team_stats([TUNE, HOLD])
    if "--tune" in sys.argv:
        P = tune(g, lines, log["lines"])
        P = tune_player(pg, ts, g, P, log["player"])
    else:
        try: log = json.load(open(out)).get("tuning_log", log)
        except Exception: pass
    x = with_lines(CM.walk_forward(g, [TUNE, HOLD], P), lines)
    res = {"params": P, "tuned_on": "2025", "holdout": "2026 to date", "data_through": str(g["date"].max().date()), "tuning_log": log, "lines": {}}
    elo_fit = None
    for s in (TUNE, HOLD):
        sc = line_scores(x[x["season"] == s])
        if "_elo" in sc:
            de, mg = np.array(sc["_elo"][0]), np.array(sc["_elo"][1])
            if s == TUNE:
                elo_fit = np.polyfit(de, mg, 1)
            if elo_fit is not None:
                sc["margin_mae"]["elo_only"] = float(np.abs(mg - np.polyval(elo_fit, de)).mean())
            del sc["_elo"]
        res["lines"][str(s)] = sc
    p = CM.player_projections(pg, ts, g, P)
    res["player"] = {str(s): player_scores(p, s) for s in (TUNE, HOLD)}
    tab, gr = CM.ratings_table(g, P)
    res["grid_today"] = {"league_points_per_team": gr["L"], "home_edge": gr["H"], "top25": tab.head(25).round(3).to_dict("records")}
    json.dump(res, open(out, "w"), indent=1, default=float)
    print("wrote", out); print(json.dumps(P))
    for s in (TUNE, HOLD):
        r = res["lines"][str(s)]
        print(s, r["games_with_a_line"], "games | margin MAE model %.2f, book %.2f%s | total MAE model %.2f, book %.2f | winner model %.3f, book %.3f | weight on model: margin %.2f total %.2f" % (
            r["margin_mae"]["model"], r["margin_mae"]["book"], (", Elo %.2f" % r["margin_mae"]["elo_only"]) if "elo_only" in r["margin_mae"] else "",
            r["total_mae"]["model"], r["total_mae"]["book"], r["winner_picked"]["model"], r["winner_picked"]["book"], r["weight_on_model_vs_book"]["margin"], r["weight_on_model_vs_book"]["total"]))
        print("    ATS:", " | ".join("gap %g+: %d-%d (%.1f%%)" % (a["min_gap"], a["wins"], a["bets"] - a["wins"], 100 * a["win_pct"]) for a in r["against_the_spread"] if a["bets"]))
        print("    totals:", " | ".join("gap %g+: %d-%d (%.1f%%)" % (a["min_gap"], a["wins"], a["bets"] - a["wins"], 100 * a["win_pct"]) for a in r["totals"] if a["bets"]))
        print("    FBS v FBS %d games: margin MAE model %.2f, book %.2f" % (r["fbs_vs_fbs"]["games"], r["fbs_vs_fbs"]["margin_mae_model"], r["fbs_vs_fbs"]["margin_mae_book"]))
        for k, v in res["player"][str(s)].items():
            print("    %-8s %5d player-games | season avg %.2f | baseline %.2f | with matchup %.2f (%.1f%% better)" % (k, v["player_games"], v["mae_season_avg"], v["mae_baseline"], v["mae_with_matchup"], v["gain_vs_season_avg_pct"]))
    print(tab.head(12).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
