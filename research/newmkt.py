"""New prop markets (owner 11/5): passing TDs, interceptions, completions, rush attempts. Walk-forward per player-game (2023-26 REG):
mean = player's average to date shrunk toward the league mean (k = 3 games) x opponent factor (opp allowed per game / league, ^ alpha);
TDs / INTs Poisson, completions / rush attempts normal with sd = c x sqrt(mean) fitted on 2023-24. alpha and c fit on 2023-24, tested
on 2025-26: Brier at the common FanDuel thresholds vs the player's plain average (same distribution), plus calibration by bucket.
QBs: 15+ attempts in the game and 2+ prior games; RBs: rush attempts for players averaging 8+ carries to date.
Usage: python3 -I research/newmkt.py <dir with stats_player_week_2023..2026.csv> [out.json]
"""
import sys, os, json, math
import numpy as np, pandas as pd
D = sys.argv[1]
P = pd.concat([pd.read_csv(os.path.join(D, f"stats_player_week_{y}.csv"), low_memory=False) for y in range(2023, 2027)])
P = P[P.season_type == "REG"].fillna(0)
P = P.sort_values(["season", "week"])
MK = {"pass_td": ("passing_tds", "QB", "pois", [0.5, 1.5, 2.5]), "int": ("passing_interceptions", "QB", "pois", [0.5, 1.5]),
      "cmp": ("completions", "QB", "norm", [17.5, 20.5, 23.5]), "rush_att": ("carries", "RB", "norm", [9.5, 12.5, 15.5, 18.5])}
def pois_ge(lam, k):   # P(X >= k) for integer k
    return 1 - sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(int(k)))
def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
OUT = {}
for name, (col, pos, dist, ths) in MK.items():
    X = P[P.position == pos][list(dict.fromkeys(["season", "week", "player_id", "player_display_name", "team", "opponent_team", col, "attempts", "carries"]))].copy()
    if pos == "QB": X = X[X.attempts >= 15]
    rows = []
    for s, g in X.groupby("season"):
        lg = g[col].mean() if pos != "RB" else g.groupby("player_id")[col].mean().pipe(lambda x: x[x >= 8]).mean()   # RBs: shrink toward the mean of 8+ carry backs, not every RB
        opp_all = g.groupby(["opponent_team", "week"])[col].sum().reset_index()
        for w in sorted(g.week.unique()):
            cur = g[g.week == w]; pr = g[g.week < w]
            if pr.week.nunique() < 3: continue
            pav = pr.groupby("player_id")[col].agg(["mean", "count"])
            oa = opp_all[opp_all.week < w].groupby("opponent_team")[col].mean(); lgo = oa.mean()
            for r in cur.itertuples():
                if r.player_id not in pav.index or pav.loc[r.player_id, "count"] < 2: continue
                if pos == "RB" and pr[pr.player_id == r.player_id].carries.mean() < 8: continue
                m, n = pav.loc[r.player_id, "mean"], pav.loc[r.player_id, "count"]
                shr = (m * n + lg * 3) / (n + 3); of = (oa.get(r.opponent_team, lgo) / lgo) if lgo else 1
                rows.append((s, w, r.player_display_name, getattr(r, col), m, shr, of))
    R = pd.DataFrame(rows, columns=["season", "week", "pl", "y", "avg", "shr", "of"])
    tr, te = R[R.season <= 2024], R[R.season >= 2025]
    def probs(df, a, c, use_shr=True, use_opp=True):
        mu = (df.shr if use_shr else df.avg).values * ((df.of.values ** a) if use_opp else 1); mu = np.maximum(mu, 0.05)
        out = {}
        for t in ths:
            if dist == "pois": out[t] = np.array([pois_ge(x, math.ceil(t)) for x in mu])
            else: out[t] = np.array([1 - ncdf((t - x) / (c * math.sqrt(x))) for x in mu])
        return out
    def brier(df, pr): return float(np.mean([np.mean((pr[t] - (df.y.values > t)) ** 2) for t in ths]))
    best = None
    for a in (0, 0.25, 0.5, 0.75, 1.0):
        for c in ((1.0,) if dist == "pois" else (0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.6)):
            b = brier(tr, probs(tr, a, c))
            if not best or b < best[0]: best = (b, a, c)
    _, a, c = best
    if dist == "norm":   # also try the plain-average baseline with its own best c
        cb = min(((brier(tr, probs(tr, 0, cc, False, False)), cc) for cc in (0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.6)))[1]
    else: cb = 1.0
    bm, bb = brier(te, probs(te, a, c)), brier(te, probs(te, 0, cb, False, False))
    pr = probs(te, a, c); cal = []
    allp = np.concatenate([pr[t] for t in ths]); ally = np.concatenate([(te.y.values > t) for t in ths])
    for lo in (0, 0.2, 0.4, 0.6, 0.8):
        msk = (allp >= lo) & (allp < lo + 0.2)
        if msk.sum(): cal.append((f"{lo:.1f}-{lo+0.2:.1f}", int(msk.sum()), round(float(allp[msk].mean()), 3), round(float(ally[msk].mean()), 3)))
    OUT[name] = {"alpha": a, "c": c, "test_n": int(len(te)), "brier_model": round(bm, 4), "brier_plain_avg": round(bb, 4), "cal": cal, "k": 3}
    print(f"{name}: alpha={a} c={c} | 2025-26 n={len(te)} Brier model {bm:.4f} vs plain avg {bb:.4f} ({bm - bb:+.4f}) | calibration {cal}")
if len(sys.argv) > 2: json.dump(OUT, open(sys.argv[2], "w"), indent=1); print("wrote", sys.argv[2])
