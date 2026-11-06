"""Does knowing who sat out improve our season-average team-score formula? (owner 11/5: model numbers should react to injury news)
Formula (sheet 'AUTO - Market Team Points' col H): 0.65 x team pts/game to date + 0.35 x opponent pts allowed/game to date.
Absence features (computed from games played to date; "out" = had a stat row in >= 60% of the team's prior games, none this game):
  qb_out   the team's main passer to date (most attempts, >= 60% of team attempts) did not play
  tgt_out  sum of prior target share of absent pass catchers;  car_out  sum of prior carry share of absent backs
  opp_*    the same for the opponent (their absences should lift our score only via their offense - kept to test)
Fit OLS of (actual - formula) on the features with 2023-2025 regular season (team-week >= week 4), test 2026 weeks 4+.
Usage: python3 -I research/injury_team_pts.py /home/claude/data
"""
import sys, os, numpy as np, pandas as pd
D = sys.argv[1]
G = pd.read_csv(os.path.join(D, "games.csv")); G = G[(G.game_type == "REG") & G.home_score.notna() & G.season.between(2023, 2026)]
rows = []
for _, g in G.iterrows():
    rows.append((g.season, g.week, g.home_team, g.away_team, g.home_score, g.away_score))
    rows.append((g.season, g.week, g.away_team, g.home_team, g.away_score, g.home_score))
T = pd.DataFrame(rows, columns=["season", "week", "team", "opp", "pf", "pa"]).sort_values(["season", "week"])
P = pd.concat([pd.read_csv(os.path.join(D, f"stats_player_week_{y}.csv"), low_memory=False) for y in range(2023, 2027)])
P = P[P.season_type == "REG"][["season", "week", "team", "player_id", "attempts", "targets", "carries"]].fillna(0)
TW = P.groupby(["season", "team", "week"])[["attempts", "targets", "carries"]].sum().rename(columns=lambda c: "t_" + c).reset_index()
P = P.merge(TW, on=["season", "team", "week"])
feat = {}
for (s, t), grp in P.groupby(["season", "team"]):
    weeks = sorted(grp.week.unique())
    for i, w in enumerate(weeks):
        prior = grp[grp.week < w]; pw = sorted(prior.week.unique())
        if len(pw) < 3: continue
        ag = prior.groupby("player_id").agg(n=("week", "nunique"), att=("attempts", "sum"), tg=("targets", "sum"), ca=("carries", "sum"))
        tot = prior.drop_duplicates("week")[["t_attempts", "t_targets", "t_carries"]].sum()
        reg = ag[ag.n >= 0.6 * len(pw)]
        here = set(grp[grp.week == w].player_id)
        out = reg[~reg.index.isin(here)]
        qb = ag.att.idxmax() if len(ag) else None
        qb_out = int(qb is not None and ag.loc[qb, "att"] >= 0.6 * tot.t_attempts and qb not in here)
        feat[(s, t, w)] = (qb_out, out.tg.sum() / max(tot.t_targets, 1), out.ca.sum() / max(tot.t_carries, 1))
X = []
for (s), grp in T.groupby("season"):
    for _, r in grp.iterrows():
        pr = grp[(grp.week < r.week)]
        a = pr[pr.team == r.team]; b = pr[pr.team == r.opp]
        if len(a) < 3 or len(b) < 3: continue
        f = 0.65 * a.pf.mean() + 0.35 * b.pa.mean()
        fa = feat.get((s, r.team, r.week)); fo = feat.get((s, r.opp, r.week))
        if fa is None or fo is None: continue
        X.append([s, r.week, r.team, r.pf, f, *fa, *fo])
X = pd.DataFrame(X, columns=["season", "week", "team", "pf", "form", "qb_out", "tgt_out", "car_out", "oqb_out", "otgt_out", "ocar_out"])
X["res"] = X.pf - X.form
for hold in (2023, 2024, 2025, 2026):
  tr, te = X[X.season != hold], X[X.season == hold]
  print(f"--- hold out {hold}: train {len(tr)}, test {len(te)}; qb_out rate test {te.qb_out.mean():.3f}")
  for cols in (["qb_out"], ["qb_out", "tgt_out", "car_out"], ["qb_out", "tgt_out", "car_out", "oqb_out", "otgt_out", "ocar_out"]):
      A = np.c_[np.ones(len(tr)), tr[cols].values]; beta = np.linalg.lstsq(A, tr.res.values, rcond=None)[0]
      At = np.c_[np.ones(len(te)), te[cols].values]
      base = np.abs(te.res - beta[0]).mean(); adj = np.abs(te.res - At @ beta).mean()
      sub = te[(te[cols[:3] if len(cols) >= 3 else cols] != 0).any(axis=1)]
      Asub = np.c_[np.ones(len(sub)), sub[cols].values]
      print(f"{'+'.join(cols)}: beta {np.round(beta, 2).tolist()} | 2026 MAE {base:.3f} -> {adj:.3f} ({adj - base:+.3f}) | affected rows {len(sub)}: {np.abs(sub.res - beta[0]).mean():.3f} -> {np.abs(sub.res - Asub @ beta).mean():.3f}")
