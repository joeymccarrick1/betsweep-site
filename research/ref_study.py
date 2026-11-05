#!/usr/bin/env python3
"""Referee crew study (owner 11/4, item 7). nflverse pbp 2023-2025 + games.csv (referee, closing total, scores).
Per game: penalties, defensive pass interference calls, offensive holding, total plays, points, points vs the closing total.
Per crew (referee): per-game averages. Out of sample: rank crews by 2023-24 DPI + penalty rate, then look at 2025 points vs closing total,
over rate and passing yards by crew tercile. If the top tercile runs hot in 2025 as well, the crew note on the card gets a direction.
"""
import pandas as pd, numpy as np, csv, io, subprocess
G = pd.read_csv("/tmp/games.csv", low_memory=False); G = G[(G.game_type == "REG") & (G.season.isin([2023, 2024, 2025, 2026]))]
rows = []
for y in (2023, 2024, 2025, 2026):
    p = pd.read_csv(f"pbp_{y}.csv.gz", low_memory=False, usecols=["game_id", "play_type", "penalty", "penalty_type", "penalty_team", "posteam", "pass_attempt", "passing_yards", "yards_gained", "epa", "play_id"])
    p = p[p.play_type.notna()]
    g = p.groupby("game_id").agg(plays=("play_id", "count"), pen=("penalty", "sum"), pass_att=("pass_attempt", "sum"), pass_yds=("passing_yards", "sum")).reset_index()
    dpi = p[p.penalty_type.fillna("").str.contains("Defensive Pass Interference")].groupby("game_id").size().rename("dpi")
    hold = p[p.penalty_type.fillna("").str.contains("Offensive Holding")].groupby("game_id").size().rename("hold")
    dh = p[p.penalty_type.fillna("").str.contains("Defensive Holding|Illegal Contact")].groupby("game_id").size().rename("dhold")
    g = g.merge(dpi, on="game_id", how="left").merge(hold, on="game_id", how="left").merge(dh, on="game_id", how="left").fillna(0)
    g["season"] = y; rows.append(g)
P = pd.concat(rows)
D = G.merge(P, on=["game_id", "season"], how="inner")
D["tot"] = D.away_score + D.home_score; D["vs_line"] = D.tot - D.total_line; D["over"] = (D.tot > D.total_line).astype(float)
D = D[D.referee.notna() & (D.referee != "")]
print(f"games with referee + pbp: {len(D)} ({D.groupby('season').size().to_dict()})")
lg = D.groupby("season").agg(pen=("pen", "mean"), dpi=("dpi", "mean"), plays=("plays", "mean"), tot=("tot", "mean"), vs_line=("vs_line", "mean"), over=("over", "mean"))
print("league per game by season:\n", lg.round(2))
crew = D.groupby("referee").agg(n=("game_id", "count"), pen=("pen", "mean"), dpi=("dpi", "mean"), dhold=("dhold", "mean"), hold=("hold", "mean"), plays=("plays", "mean"), tot=("tot", "mean"), vs_line=("vs_line", "mean"), over=("over", "mean"), pass_yds=("pass_yds", "mean"))
crew = crew[crew.n >= 20].sort_values("dpi", ascending=False)
print("\ncrews (n>=20, 2023-25), sorted by DPI per game:\n", crew.round(2).to_string())
# out of sample: rank on 2023-24, evaluate 2025
A = D[D.season.isin([2023, 2024])].groupby("referee").agg(n=("game_id", "count"), pen=("pen", "mean"), dpi=("dpi", "mean"), vs_line=("vs_line", "mean"), tot=("tot", "mean"))
A = A[A.n >= 15]
B = D[D.season == 2025]
for metric in ("dpi", "pen", "vs_line", "tot"):
    q = A[metric].quantile([1/3, 2/3]).values
    A["ter"] = np.where(A[metric] >= q[1], "high", np.where(A[metric] <= q[0], "low", "mid"))
    M = B.merge(A[["ter"]], left_on="referee", right_index=True, how="inner")
    r = M.groupby("ter").agg(n=("game_id", "count"), vs_line=("vs_line", "mean"), over=("over", "mean"), tot=("tot", "mean"), pen=("pen", "mean"), dpi=("dpi", "mean"), pass_yds=("pass_yds", "mean"))
    print(f"\n2025 by crew tercile of 2023-24 {metric}:\n", r.round(2).loc[[x for x in ("high", "mid", "low") if x in r.index]].to_string())
# persistence of the crew traits themselves (is a crew's penalty rate a trait?)
X = D[D.season.isin([2023, 2024])].groupby("referee").agg(pen=("pen", "mean"), dpi=("dpi", "mean"), n=("game_id", "count")); X = X[X.n >= 15]
Y = D[D.season == 2025].groupby("referee").agg(pen=("pen", "mean"), dpi=("dpi", "mean"), n=("game_id", "count")); Y = Y[Y.n >= 8]
J = X.join(Y, lsuffix="_prev", rsuffix="_2025", how="inner")
print(f"\ncrew trait persistence (n={len(J)} crews): corr penalties/game 2023-24 vs 2025 = {J.pen_prev.corr(J.pen_2025):.2f}; DPI/game = {J.dpi_prev.corr(J.dpi_2025):.2f}")
crew.round(3).to_json("ref_crews.json", orient="index")
