#!/usr/bin/env python3
"""
BetSweep game-line backtest: can any simple, pre-kickoff adjustment to the
closing market line beat the closing line at predicting NFL margins / winners,
out of sample, 2024 W7 - 2026 W6?

All data comes from nflverse release files (downloaded if missing).
Walk-forward is strict: for a game in (season, week) only games strictly
before that (season, week) are used to fit betas / sigmas, and all team
features are built from prior weeks only.

Usage:  python3 -I gen/gameline_backtest.py [--root DIR]
Writes: out/gameline_backtest_results.md and .json
"""
import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np
import pandas as pd

BASE = "https://github.com/nflverse/nflverse-data/releases/download"
SEASONS = [2024, 2025, 2026]
LAST_2026_WEEK = 6          # week 7 not played as of 2026-10-20
WARMUP = (2024, 6)          # (season, week) <= this is warm-up, never scored
CLV_MOVE = 0.5              # min move vs the close to count a CLV "bet"
RIDGE_LAMBDA = 1.0
SHRINK_K = 4.0              # prior-season blend: w = n / (n + K)

STAT_COLS = {
    "off_epa": ["passing_epa", "rushing_epa"],
    "plays": ["attempts", "sacks_suffered", "carries"],
    "giveaways": ["passing_interceptions", "fumbles_lost_total"],
    "takeaways": ["def_interceptions", "fumble_recovery_opp"],
}
INJ_POS = {"QB": 3.0, "RB": 1.0, "WR": 1.0, "TE": 1.0, "T": 1.0, "G": 1.0, "C": 1.0, "OL": 1.0}
INJ_STATUS = ("Out", "Doubtful")


# --------------------------------------------------------------------------- io
def download(root):
    d = os.path.join(root, "data")
    os.makedirs(d, exist_ok=True)
    files = {"games.csv": f"{BASE}/schedules/games.csv"}
    for y in SEASONS:
        files[f"stats_team_week_{y}.csv"] = f"{BASE}/stats_team/stats_team_week_{y}.csv"
        files[f"injuries_{y}.csv"] = f"{BASE}/injuries/injuries_{y}.csv"
    for name, url in files.items():
        p = os.path.join(d, name)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            print(f"downloading {name}")
            subprocess.run(["curl", "-sSLf", "-o", p, url], check=True)
    return d


def load_games(d):
    g = pd.read_csv(os.path.join(d, "games.csv"))
    g = g[(g.season.isin(SEASONS)) & (g.game_type == "REG")].copy()
    g = g[~((g.season == 2026) & (g.week > LAST_2026_WEEK))]
    g = g[g.home_score.notna() & g.away_score.notna() & g.spread_line.notna()].copy()
    g["result"] = g.home_score - g.away_score
    g["total"] = g.home_score + g.away_score
    g["ord"] = g.season * 100 + g.week
    g = g.sort_values(["ord", "gameday", "game_id"]).reset_index(drop=True)
    return g


def load_stats(d):
    parts = [pd.read_csv(os.path.join(d, f"stats_team_week_{y}.csv")) for y in SEASONS]
    s = pd.concat(parts, ignore_index=True)
    s = s[s.season_type == "REG"].copy()
    need = sum(STAT_COLS.values(), [])
    missing = [c for c in need if c not in s.columns]
    if missing:
        sys.exit(f"stats_team_week missing columns: {missing}")
    for k, cols in STAT_COLS.items():
        s[k] = s[cols].sum(axis=1)
    s = s[["season", "week", "team", "opponent_team", "game_id", "off_epa", "plays", "giveaways", "takeaways"]]
    # defence = what the opponent's offence did in the same game
    opp = s[["game_id", "team", "off_epa", "plays"]].rename(
        columns={"team": "opponent_team", "off_epa": "def_epa_allowed", "plays": "def_plays"})
    s = s.merge(opp, on=["game_id", "opponent_team"], how="left")
    return s


def load_injuries(d):
    parts = [pd.read_csv(os.path.join(d, f"injuries_{y}.csv")) for y in SEASONS]
    i = pd.concat(parts, ignore_index=True)
    i = i[i.game_type == "REG"].copy()
    # the file holds one row per player per week (the final report of the week);
    # keep the last row anyway in case of duplicates
    i = i.drop_duplicates(["season", "week", "team", "gsis_id"], keep="last")
    i = i[i.report_status.isin(INJ_STATUS) & i.position.isin(INJ_POS)].copy()
    i["w"] = i.position.map(INJ_POS)
    out = i.groupby(["season", "week", "team"]).agg(bodies=("w", "sum"), qb_out=("w", lambda x: (x == 3).sum())).reset_index()
    return out


# ------------------------------------------------------------------ features
def team_strength_table(games, stats):
    """For every (season, week, team) compute strength features using ONLY
    games played strictly before that week (current season to date, blended
    with the previous season's final values: w = n/(n+K))."""
    # win/loss per team-game from the schedule
    rows = []
    for r in games.itertuples(index=False):
        rows.append((r.season, r.week, r.home_team, 1.0 if r.result > 0 else 0.5 if r.result == 0 else 0.0))
        rows.append((r.season, r.week, r.away_team, 1.0 if r.result < 0 else 0.5 if r.result == 0 else 0.0))
    wl = pd.DataFrame(rows, columns=["season", "week", "team", "win"])
    tg = stats.merge(wl, on=["season", "week", "team"], how="inner")
    tg["net_epa"] = tg.off_epa - tg.def_epa_allowed
    tg["to_margin"] = tg.takeaways - tg.giveaways

    def agg(df):
        n = len(df)
        if n == 0:
            return None
        return dict(n=n,
                    epa_pp=(df.off_epa.sum() / max(df.plays.sum(), 1)) - (df.def_epa_allowed.sum() / max(df.def_plays.sum(), 1)),
                    winpct=df.win.mean(),
                    to_pg=df.to_margin.sum() / n)

    teams = sorted(set(games.home_team) | set(games.away_team))
    # previous-season finals
    prev = {}
    for s in SEASONS:
        for t in teams:
            a = agg(tg[(tg.season == s) & (tg.team == t)])
            if a:
                prev[(s, t)] = a
    out = []
    weeks = games[["season", "week"]].drop_duplicates().sort_values(["season", "week"])
    for s, w in weeks.itertuples(index=False):
        for t in teams:
            cur = agg(tg[(tg.season == s) & (tg.week < w) & (tg.team == t)])
            pr = prev.get((s - 1, t))
            feats = {}
            for k in ("epa_pp", "winpct", "to_pg"):
                c = cur[k] if cur else None
                p = pr[k] if pr else None
                n = cur["n"] if cur else 0
                wt = n / (n + SHRINK_K)
                if c is None and p is None:
                    v = np.nan
                elif p is None:
                    v = c
                elif c is None:
                    v = p
                else:
                    v = wt * c + (1 - wt) * p
                feats[k] = v
            out.append(dict(season=s, week=w, team=t, n_games=(cur["n"] if cur else 0), **feats))
    st = pd.DataFrame(out)
    # z-scores across the league at that season-week
    for k in ("epa_pp", "winpct", "to_pg"):
        grp = st.groupby(["season", "week"])[k]
        st[k + "_z"] = (st[k] - grp.transform("mean")) / grp.transform("std").replace(0, np.nan)
    return st.fillna(0.0)


def build_features(games, st, inj):
    g = games.copy()
    h = st.add_prefix("h_").rename(columns={"h_season": "season", "h_week": "week", "h_team": "home_team"})
    a = st.add_prefix("a_").rename(columns={"a_season": "season", "a_week": "week", "a_team": "away_team"})
    g = g.merge(h, on=["season", "week", "home_team"], how="left").merge(a, on=["season", "week", "away_team"], how="left")
    ih = inj.rename(columns={"team": "home_team", "bodies": "h_bodies", "qb_out": "h_qb_out"})
    ia = inj.rename(columns={"team": "away_team", "bodies": "a_bodies", "qb_out": "a_qb_out"})
    g = g.merge(ih, on=["season", "week", "home_team"], how="left").merge(ia, on=["season", "week", "away_team"], how="left")
    for c in ("h_bodies", "a_bodies", "h_qb_out", "a_qb_out"):
        g[c] = g[c].fillna(0.0)

    g["f_epa_diff"] = g.h_epa_pp_z - g.a_epa_pp_z
    g["f_epa_vs_record"] = (g.h_epa_pp_z - g.a_epa_pp_z) - (g.h_winpct_z - g.a_winpct_z)
    g["f_to_regress"] = -(g.h_to_pg - g.a_to_pg)
    g["f_rest_diff"] = (g.home_rest - g.away_rest).fillna(0.0)
    g["f_away_short"] = (g.away_rest <= 5).astype(float)
    g["f_home_short"] = (g.home_rest <= 5).astype(float)
    g["f_div"] = g.div_game.fillna(0).astype(float)
    g["f_bodies_diff"] = g.h_bodies - g.a_bodies
    outdoor = g.roof.isin(["outdoors", "open"])
    g["f_wx_wind"] = (outdoor & (g.wind >= 15)).astype(float)
    g["f_wx_cold"] = (outdoor & (g.temp <= 32)).astype(float)
    g["f_wx_either"] = (outdoor & ((g.wind >= 15) | (g.temp <= 32))).astype(float)
    g["f_wx_both"] = (outdoor & (g.wind >= 15) & (g.temp <= 32)).astype(float)
    g["wx_known"] = outdoor & g.wind.notna() & g.temp.notna()

    # market win probability from moneylines, vig removed
    def imp(ml):
        ml = np.asarray(ml, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(ml < 0, -ml / (-ml + 100.0), 100.0 / (ml + 100.0))
    ph, pa = imp(g.home_moneyline), imp(g.away_moneyline)
    g["mkt_p_home"] = ph / (ph + pa)
    return g


# --------------------------------------------------------------------- model
def fit_beta(X, y, lam=0.0):
    """No-intercept least squares (ridge if lam>0) of residual y on X."""
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    y = np.asarray(y, dtype=float)
    if lam > 0:
        return np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)   # zero column (flag never fired yet) -> beta 0
    return beta


def norm_cdf(x):
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(x, dtype=float) / math.sqrt(2.0)))


CANDIDATES = {
    # name: (feature columns, target)   target: 'margin' or 'total'
    "a1 EPA diff (z)": (["f_epa_diff"], "margin"),
    "a2 EPA minus record (z)": (["f_epa_vs_record"], "margin"),
    "b  TO-margin regression": (["f_to_regress"], "margin"),
    "c1 rest diff (days)": (["f_rest_diff"], "margin"),
    "c2 away short rest (<=5d)": (["f_away_short"], "margin"),
    "c3 rest diff + short flags + div": (["f_rest_diff", "f_away_short", "f_home_short", "f_div"], "margin"),
    "e  bodies out diff (QB x3)": (["f_bodies_diff"], "margin"),
    "f  combined ridge (all margin feats)": (["f_epa_diff", "f_epa_vs_record", "f_to_regress", "f_rest_diff",
                                             "f_away_short", "f_home_short", "f_div", "f_bodies_diff"], "margin"),
    "d1 totals: wind>=15 outdoor": (["f_wx_wind"], "total"),
    "d2 totals: temp<=32 outdoor": (["f_wx_cold"], "total"),
    "d3 totals: wind>=15 or temp<=32": (["f_wx_either"], "total"),
    "d4 totals: wind>=15 and temp<=32": (["f_wx_both"], "total"),
}


def walk_forward(g):
    """Returns g with per-candidate adjusted lines + per-week sigmas."""
    g = g.copy()
    weeks = sorted(g.ord.unique())
    score_weeks = [w for w in weeks if w > WARMUP[0] * 100 + WARMUP[1]]
    g["sig_mkt"] = np.nan
    for name, (cols, tgt) in CANDIDATES.items():
        g["adj_" + name] = np.nan
        g["sig_" + name] = np.nan
        g["beta_" + name] = np.nan
    betas_log = {name: [] for name in CANDIDATES}
    for w in score_weeks:
        tr = g[g.ord < w]
        te_idx = g.index[g.ord == w]
        g.loc[te_idx, "sig_mkt"] = (tr.result - tr.spread_line).std(ddof=1)
        for name, (cols, tgt) in CANDIDATES.items():
            if tgt == "margin":
                line, truth = "spread_line", "result"
                trn = tr
            else:
                line, truth = "total_line", "total"
                trn = tr[tr.total_line.notna() & tr.wx_known]
            resid = trn[truth] - trn[line]
            lam = RIDGE_LAMBDA if len(cols) > 1 else 0.0
            beta = fit_beta(trn[cols].values, resid.values, lam)
            betas_log[name].append((int(w), [float(b) for b in beta]))
            adj_tr = trn[line] + trn[cols].values @ beta
            sig = (trn[truth] - adj_tr).std(ddof=1)
            g.loc[te_idx, "adj_" + name] = g.loc[te_idx, line] + g.loc[te_idx, cols].values @ beta
            g.loc[te_idx, "sig_" + name] = sig
            g.loc[te_idx, "beta_" + name] = beta[0] if len(beta) == 1 else np.nan
    return g, betas_log


# ------------------------------------------------------------------- scoring
def paired_pvalue(d):
    """Two-sided paired t-test (normal approx) on mean of d."""
    d = np.asarray(d, dtype=float)
    n = len(d)
    if n < 3 or d.std(ddof=1) == 0:
        return float("nan")
    t = d.mean() / (d.std(ddof=1) / math.sqrt(n))
    return float(2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2)))))


def score(g):
    sc = g[g.ord > WARMUP[0] * 100 + WARMUP[1]].copy()
    results = []
    # market baseline
    mk = sc[sc.result != 0]
    base = dict(
        games=int(len(sc)),
        margin_mae_close=float((sc.result - sc.spread_line).abs().mean()),
        brier_moneyline=float(((mk.mkt_p_home - (mk.result > 0)) ** 2).mean()),
        brier_spread_normal=float(((norm_cdf(mk.spread_line / mk.sig_mkt) - (mk.result > 0)) ** 2).mean()),
        total_mae_close=float((sc.total - sc.total_line).abs().mean()),
        fav_win_rate=float(((mk.spread_line > 0) == (mk.result > 0))[mk.spread_line != 0].mean()),
        home_cover_rate=float((sc.result > sc.spread_line)[sc.result != sc.spread_line].mean()),
    )
    for name, (cols, tgt) in CANDIDATES.items():
        adj = "adj_" + name
        if tgt == "margin":
            d = sc[sc[adj].notna()].copy()
            line, truth = "spread_line", "result"
        else:
            d = sc[sc[adj].notna() & sc.total_line.notna() & sc.wx_known].copy()
            line, truth = "total_line", "total"
        err_adj = (d[truth] - d[adj]).abs()
        err_cl = (d[truth] - d[line]).abs()
        move = d[adj] - d[line]
        bet = d[move.abs() >= CLV_MOVE]
        cover = np.sign(bet[truth] - bet[line])
        side = np.sign(bet[adj] - bet[line])
        decided = bet[cover != 0]
        hits = int((np.sign(decided[adj] - decided[line]) == np.sign(decided[truth] - decided[line])).sum())
        n_bet = int(len(decided))
        row = dict(
            candidate=name, target=tgt, games=int(len(d)),
            mae_adj=float(err_adj.mean()), mae_close=float(err_cl.mean()),
            mae_delta=float(err_adj.mean() - err_cl.mean()),
            mae_p=paired_pvalue(err_adj.values - err_cl.values),
            n_moved=int(len(bet)), clv_hits=hits, clv_n=n_bet,
            clv_rate=(hits / n_bet if n_bet else float("nan")),
            clv_p_vs_50=(float(2 * (1 - 0.5 * (1 + math.erf(abs(hits - n_bet / 2) / math.sqrt(n_bet / 4) / math.sqrt(2))))) if n_bet else float("nan")),
            mean_abs_move=float(move.abs().mean()),
            beta_last=(float(d["beta_" + name].iloc[-1]) if len(cols) == 1 else None),
        )
        if tgt == "margin":
            m = d[d.result != 0]
            p_adj = norm_cdf(m[adj] / m["sig_" + name])
            y = (m.result > 0).astype(float)
            row["brier_adj"] = float(((p_adj - y) ** 2).mean())
            row["brier_mkt"] = float(((m.mkt_p_home - y) ** 2).mean())
            row["brier_delta"] = row["brier_adj"] - row["brier_mkt"]
            row["brier_spread_normal"] = float(((norm_cdf(m.spread_line / m.sig_mkt) - y) ** 2).mean())
            # moneyline record when adjusted pick disagrees with market favourite
            fav = np.sign(m.spread_line)
            pick = np.sign(m[adj])
            dis = m[(fav != 0) & (pick != 0) & (fav != pick)]
            row["disagree_n"] = int(len(dis))
            row["disagree_adj_wins"] = int((np.sign(dis[adj]) == np.sign(dis.result)).sum())
            row["disagree_mkt_wins"] = int((np.sign(dis.spread_line) == np.sign(dis.result)).sum())
        results.append(row)
    return base, results


def fmt_table(base, results):
    lines = []
    lines.append("| candidate | target | games | MAE adj | MAE close | delta (p) | CLV rate (hits/n, binomial p vs 50%) | Brier adj | Brier mkt (ML) | ML record when disagreeing (adj-mkt, n) |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in results:
        clv = f"{r['clv_rate']:.3f} ({r['clv_hits']}/{r['clv_n']}, p={r['clv_p_vs_50']:.2f})" if r["clv_n"] else "n/a (0)"
        if r["target"] == "margin":
            br = f"{r['brier_adj']:.4f}"
            bm = f"{r['brier_mkt']:.4f}"
            rec = f"{r['disagree_adj_wins']}-{r['disagree_mkt_wins']} (n={r['disagree_n']})"
        else:
            br, bm, rec = "-", "-", "-"
        lines.append(f"| {r['candidate']} | {r['target']} | {r['games']} | {r['mae_adj']:.3f} | {r['mae_close']:.3f} | "
                     f"{r['mae_delta']:+.3f} (p={r['mae_p']:.2f}) | {clv} | {br} | {bm} | {rec} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    d = download(args.root)
    games = load_games(d)
    stats = load_stats(d)
    inj = load_injuries(d)
    print("columns used:")
    print("  games.csv:", "season game_type week gameday away_team home_team away_score home_score spread_line total_line "
          "away_moneyline home_moneyline away_rest home_rest roof temp wind div_game")
    print("  stats_team_week:", "season week team opponent_team game_id season_type +", STAT_COLS)
    print("  injuries:", "season game_type week team gsis_id position report_status; statuses", INJ_STATUS, "positions", INJ_POS)
    st = team_strength_table(games, stats)
    g = build_features(games, st, inj)
    g, betas = walk_forward(g)
    base, results = score(g)

    sc = g[g.ord > WARMUP[0] * 100 + WARMUP[1]]
    cov = dict(
        games_total=int(len(games)), games_scored=int(len(sc)),
        score_range=f"{sc.season.min()} W{sc[sc.season == sc.season.min()].week.min()} - {sc.season.max()} W{sc[sc.season == sc.season.max()].week.max()}",
        games_2026=int((games.season == 2026).sum()),
        weather_known_outdoor_scored=int(sc.wx_known.sum()),
        weather_missing_2026=int(((sc.season == 2026) & sc.roof.isin(["outdoors", "open"]) & sc.wind.isna()).sum()),
        injury_rows_teamweeks=int(len(inj)),
        games_with_any_bodies_out=int(((sc.h_bodies > 0) | (sc.a_bodies > 0)).sum()),
        games_with_qb_out=int(((sc.h_qb_out > 0) | (sc.a_qb_out > 0)).sum()),
        wx_flag_counts={k: int(sc[k].sum()) for k in ("f_wx_wind", "f_wx_cold", "f_wx_either", "f_wx_both")},
    )
    table = fmt_table(base, results)
    print("\nBASELINE (closing market), scored games:", base)
    print("\nCOVERAGE:", cov)
    print("\n" + table)
    print("\nfinal betas (last week fit):", {k: v[-1][1] for k, v in betas.items()})

    out = os.path.join(args.root, "out")
    os.makedirs(out, exist_ok=True)
    md = ["# Game-line backtest: adjustments to the closing line", "",
          f"Scored out of sample {cov['score_range']} (REG season, {cov['games_scored']} games; 2024 W1-6 warm-up, training only). "
          f"Betas refit every week on all prior games (no intercept; ridge lambda={RIDGE_LAMBDA} for the combined model). "
          f"Team strength = current season to date blended with prior season final (w=n/(n+{SHRINK_K:g})), z-scored league-wide per week.", "",
          "## Closing-market baseline", "",
          f"- margin MAE vs result: {base['margin_mae_close']:.3f}",
          f"- Brier (moneyline, vig removed): {base['brier_moneyline']:.4f}; Brier (spread via normal, sigma walk-forward): {base['brier_spread_normal']:.4f}",
          f"- totals MAE: {base['total_mae_close']:.3f}; market favourite SU win rate {base['fav_win_rate']:.3f}; home cover rate {base['home_cover_rate']:.3f}", "",
          "## Candidates", "", table, "",
          "CLV rate = share of games where the adjusted line moved >= 0.5 pt off the close AND the side it moved toward covered the close (pushes dropped). "
          "ML record = games where sign(adjusted margin) != sign(closing spread): adjusted-pick wins vs market-favourite wins (ties dropped). "
          "Break-even ATS at -110 is 52.4%.", "",
          "Notes: f_home_short and f_away_short are collinear (Thursday games put both teams on <=5 days rest), so c2 is effectively a 'Thursday game' flag "
          "and the ridge splits the weight equally between the two. 2026 W5-W6 rows have no wind/temp yet, so outdoor games there are excluded from the totals tests. "
          "Weather flags fire rarely (counts below), so d1-d4 are low-power.", "",
          "## Coverage / caveats", ""] + [f"- {k}: {v}" for k, v in cov.items()] + [
          "", "## Final-week betas", ""] + [f"- {k}: {v[-1][1]}" for k, v in betas.items()]
    with open(os.path.join(out, "gameline_backtest_results.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(out, "gameline_backtest_results.json"), "w") as f:
        json.dump(dict(baseline=base, candidates=results, coverage=cov,
                       betas={k: v for k, v in betas.items()},
                       settings=dict(warmup_through=WARMUP, clv_move=CLV_MOVE, ridge_lambda=RIDGE_LAMBDA, shrink_k=SHRINK_K,
                                     stat_cols=STAT_COLS, inj_pos=INJ_POS, inj_status=list(INJ_STATUS))),
                  f, indent=1, default=float)
    print(f"\nwrote {out}/gameline_backtest_results.md and .json")


if __name__ == "__main__":
    main()
