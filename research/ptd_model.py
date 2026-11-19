"""Passing TDs: does the market's implied team total price a QB's TD ladder better than his shrunk season average?
Walk-forward 2023-26 REG, QB games with 15+ attempts and 2+ prior such games. Fit on 2023-24, test on 2025-26.
Candidates for the mean:  A = shrunk season average (k games toward the league mean);  B = Poisson regression on log(implied team points)
and log(A).  Distribution: Poisson, or Binomial(n, mu/n) (TD counts are under-dispersed: variance < mean).
Then the same fit on quarterbacks with 0-1 qualifying games this season (new and backup starters): it over-rates them badly, so newmkt.py
keeps its "2+ games" rule and offers no passing-TD leg on them.
Usage: python3 -I research/ptd_model.py <dir with stats_player_week_2023..2026.csv> in/games.csv [out.json]"""
import sys, os, math, json
import numpy as np, pandas as pd
from scipy.optimize import minimize
D, GAMES = sys.argv[1], sys.argv[2]
P = pd.concat([pd.read_csv(os.path.join(D, f"stats_player_week_{y}.csv"), low_memory=False) for y in range(2023, 2027)])
P = P[P.season_type == "REG"].fillna(0).sort_values(["season", "week"])
G = pd.read_csv(GAMES, low_memory=False); G = G[(G.game_type == "REG") & G.spread_line.notna() & G.total_line.notna()]
imp = {}
for r in G.itertuples():
    h = r.total_line / 2 + r.spread_line / 2; a = r.total_line / 2 - r.spread_line / 2
    imp[(r.season, r.week, r.home_team)] = h; imp[(r.season, r.week, r.away_team)] = a
X = P[(P.position == "QB") & (P.attempts >= 15)][["season", "week", "player_id", "player_display_name", "team", "opponent_team", "passing_tds", "attempts"]]
def build(k):
    rows = []
    for s, g in X.groupby("season"):
        lg = g.passing_tds.mean()
        for w in sorted(g.week.unique()):
            cur = g[g.week == w]; pr = g[g.week < w]
            if pr.week.nunique() < 3: continue
            pav = pr.groupby("player_id").passing_tds.agg(["mean", "count"])
            for r in cur.itertuples():
                if r.player_id not in pav.index or pav.loc[r.player_id, "count"] < 2: continue
                ip = imp.get((s, w, r.team))
                if ip is None or ip <= 0: continue
                m, n = pav.loc[r.player_id, "mean"], pav.loc[r.player_id, "count"]
                rows.append((s, w, r.passing_tds, max(0.05, (m * n + lg * k) / (n + k)), ip, lg))
    return pd.DataFrame(rows, columns=["season", "week", "y", "shr", "ip", "lg"])
def pmf(mu, dist, n):
    ks = np.arange(0, 9)
    if dist == "pois": p = np.array([math.exp(-mu) * mu ** i / math.factorial(i) for i in ks])
    else:
        q = min(0.999, mu / n); p = np.array([math.comb(n, i) * q ** i * (1 - q) ** (n - i) if i <= n else 0.0 for i in ks])
    return p / p.sum()
def score(df, mu, dist="pois", n=12):
    ll = 0.0; out = {}
    pm = np.array([pmf(m, dist, n) for m in mu]); y = df.y.values.astype(int).clip(0, 8)
    ll = float(np.mean(-np.log(np.maximum(1e-9, pm[np.arange(len(y)), y]))))
    for k in (1, 2, 3, 4):
        p = pm[:, k:].sum(axis=1); hit = (df.y.values >= k)
        out[k] = (float(p.mean()), float(hit.mean()), float(np.mean((p - hit) ** 2)), float(np.mean((hit.mean() - hit) ** 2)), p)
    return ll, out
def show(tag, df, mu, dist="pois", n=12):
    ll, o = score(df, mu, dist, n)
    print(f"  {tag:<44} logloss {ll:.4f} | " + " | ".join(f"{k}+ {o[k][0]:.3f}/{o[k][1]:.3f} B {o[k][2]:.4f} ({o[k][2] - o[k][3]:+.4f})" for k in (1, 2, 3, 4)))
    return ll, o
best = None
for k in (3, 6, 10, 15, 25):
    R = build(k); tr, te = R[R.season <= 2024], R[R.season >= 2025]
    ll, _ = score(tr, tr.shr.values)
    print(f"k={k}: train n={len(tr)} test n={len(te)}  train logloss (shrunk avg, Poisson) {ll:.4f}")
    if best is None or ll < best[0]: best = (ll, k)
K = best[1]; print("best k on 2023-24:", K)
for k in sorted({3, K}):
    R = build(k); tr, te = R[R.season <= 2024], R[R.season >= 2025]
    print(f"--- k={k}  (test 2025-26, n={len(te)}; base rates in the second number of each pair)")
    show("A shrunk avg, Poisson", te, te.shr.values)
    # B: log mu = b0 + b1 log(ip) + b2 log(shr)
    def nll(b, df=tr):
        mu = np.exp(b[0] + b[1] * np.log(df.ip.values) + b[2] * np.log(df.shr.values)); return float(np.mean(mu - df.y.values * np.log(mu)))
    b = minimize(nll, [0.0, 1.0, 0.5], method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-9, "maxiter": 4000}).x
    muB = lambda df: np.exp(b[0] + b[1] * np.log(df.ip.values) + b[2] * np.log(df.shr.values))
    print(f"   B coefficients: b0={b[0]:.3f} implied-points exponent={b[1]:.3f} QB-average exponent={b[2]:.3f}")
    show("B implied points + shrunk avg, Poisson", te, muB(te))
    # C: implied points only
    def nllc(c, df=tr):
        mu = np.exp(c[0] + c[1] * np.log(df.ip.values)); return float(np.mean(mu - df.y.values * np.log(mu)))
    c = minimize(nllc, [0.0, 1.0], method="Nelder-Mead").x
    show("C implied points only, Poisson", te, np.exp(c[0] + c[1] * np.log(te.ip.values)))
    # distribution: binomial n fitted on train for model B
    bestn = min(((score(tr, muB(tr), "bin", n)[0], n) for n in (6, 8, 10, 12, 15, 20, 30)))
    print(f"   binomial n fitted on 2023-24: n={bestn[1]} (train logloss {bestn[0]:.4f} vs Poisson {score(tr, muB(tr))[0]:.4f})")
    ll, o = show(f"B + Binomial(n={bestn[1]})", te, muB(te), "bin", bestn[1])
    show("A + Binomial(n=%d)" % bestn[1], te, te.shr.values, "bin", bestn[1])
    # calibration of the chosen model by thirds, each rung
    for kk in (1, 2, 3, 4):
        p = o[kk][4]; hit = (te.y.values >= kk); q = np.quantile(p, [1 / 3, 2 / 3]); parts = []
        for lo, hi in ((-1, q[0]), (q[0], q[1]), (q[1], 2)):
            msk = (p > lo) & (p <= hi); parts.append(f"{p[msk].mean():.3f}/{hit[msk].mean():.3f} (n={int(msk.sum())})")
        print(f"      {kk}+ thirds model/actual: " + "   ".join(parts))
    if k == K:
        FIT = {"k": int(K), "b": [round(float(x), 4) for x in b], "n": int(bestn[1]), "test_n": int(len(te)), "logloss": round(ll, 4),
               "brier_vs_base": {str(kk): round(o[kk][2] - o[kk][3], 4) for kk in (1, 2, 3, 4)}}
        print("   chosen:", FIT)

# ---- thin history: QBs with 0-1 qualifying games before this one (shrunk average = the league mean) ----
fit = FIT; k = fit["k"]; b = fit["b"]; n8 = fit["n"]
rows = []
for s_, g in X.groupby("season"):
    lg = g.passing_tds.mean()
    for w in sorted(g.week.unique()):
        cur = g[g.week == w]; pr = g[g.week < w]
        if pr.week.nunique() < 3: continue
        pav = pr.groupby("player_id").passing_tds.agg(["mean", "count"])
        for r in cur.itertuples():
            ip = imp.get((s_, w, r.team))
            if ip is None or ip <= 0: continue
            if r.player_id in pav.index: m, n = pav.loc[r.player_id, "mean"], pav.loc[r.player_id, "count"]
            else: m, n = 0.0, 0
            rows.append((s_, w, r.passing_tds, max(0.05, (m * n + lg * k) / (n + k)), ip, lg, n))
R = pd.DataFrame(rows, columns=["season", "week", "y", "shr", "ip", "lg", "n"])
mu = lambda df: np.exp(b[0] + b[1] * np.log(df.ip.values) + b[2] * np.log(df.shr.values))
for tag, df in (("0-1 prior games, all seasons", R[R.n < 2]), ("0-1 prior games, 2025-26", R[(R.n < 2) & (R.season >= 2025)]), ("2-4 prior games, 2025-26", R[(R.n >= 2) & (R.n <= 4) & (R.season >= 2025)]), ("5+ prior games, 2025-26", R[(R.n >= 5) & (R.season >= 2025)])):
    print(tag, "n =", len(df), "mean implied pts", round(df.ip.mean(), 1), "mean TDs", round(df.y.mean(), 2))
    show("  B + Binomial", df, mu(df), "bin", n8)
# league-average implied points (fallback when a game has no line yet)
print("mean implied team points, QB games 2023-24:", round(R[R.season <= 2024].ip.mean(), 2), " all:", round(R.ip.mean(), 2))

FIT["league_implied_pts"] = round(float(R[R.season <= 2024].ip.mean()), 2)
if len(sys.argv) > 3: json.dump(FIT, open(sys.argv[3], "w"), indent=1); print("wrote", sys.argv[3])
