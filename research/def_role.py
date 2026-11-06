"""Defense vs role (owner 11/5): "did they let the WR1 of the opposite team hit their prop line ... percentage-wise ... considered in
our projections and suggested parlays".
Roles per team-week from games BEFORE that week: QB1 (most pass attempts), RB1 (most carries, RB), WR1 / WR2 (targets rank among WR),
TE1 (most targets, TE). A role player who did not play that week is skipped (we grade the player who held the role).
Two measures per defense x role x market:
  own-avg  season: did the role player beat his own average to date (>= 2 prior games)? (prop lines sit near the typical output)
  FD line  weeks with frozen FanDuel ladders (legsnaps): the main line = rung priced closest to -110 (within -170..+150); HIT/MISS.
Test (does a defense's rate to date predict next week's main-line result beyond the model's own %?): every main-line leg in a week W,
feature = defense's own-avg over-rate for that role+market from weeks < W, shrunk to the league rate with k games of prior; compare
log loss of logit(p_model) vs logit(p_model) + b * (shrunk rate - league rate), b fit on the other weeks (leave-one-week-out).
Usage: python3 -I research/def_role.py <stats_player_week_2026.csv> <legsnaps.json> [out.json]
"""
import sys, json, math, collections
import pandas as pd, numpy as np
P = pd.read_csv(sys.argv[1], low_memory=False); P = P[P.season_type == "REG"].fillna({"targets": 0, "carries": 0, "attempts": 0, "receptions": 0, "receiving_yards": 0, "rushing_yards": 0, "passing_yards": 0})
MK = {"WR1": ["Receiving Yards", "Receptions"], "WR2": ["Receiving Yards", "Receptions"], "TE1": ["Receiving Yards", "Receptions"], "RB1": ["Rushing Yards"], "QB1": ["Passing Yards"]}
COL = {"Receiving Yards": "receiving_yards", "Receptions": "receptions", "Rushing Yards": "rushing_yards", "Passing Yards": "passing_yards"}
def roles(team, w):
    pr = P[(P.team == team) & (P.week < w)]
    if pr.week.nunique() < 2: return {}
    ag = pr.groupby(["player_display_name", "position"]).agg(att=("attempts", "sum"), car=("carries", "sum"), tg=("targets", "sum")).reset_index()
    out = {}
    q = ag[ag.position == "QB"].sort_values("att", ascending=False)
    if len(q): out["QB1"] = q.iloc[0].player_display_name
    r = ag[ag.position == "RB"].sort_values("car", ascending=False)
    if len(r): out["RB1"] = r.iloc[0].player_display_name
    wr = ag[ag.position == "WR"].sort_values("tg", ascending=False)
    if len(wr): out["WR1"] = wr.iloc[0].player_display_name
    if len(wr) > 1: out["WR2"] = wr.iloc[1].player_display_name
    te = ag[ag.position == "TE"].sort_values("tg", ascending=False)
    if len(te): out["TE1"] = te.iloc[0].player_display_name
    return out
# own-average events
EV = []   # (week, defense, role, market, player, over(0/1), actual, avg)
for (team, w), g in P.groupby(["team", "week"]):
    rl = roles(team, w)
    if not rl: continue
    opp = g.opponent_team.iloc[0]
    for role, pl in rl.items():
        me = g[g.player_display_name == pl]
        if not len(me): continue
        hist = P[(P.player_display_name == pl) & (P.week < w)]
        if hist.week.nunique() < 2: continue
        for m in MK[role]:
            c = COL[m]; avg = hist[c].mean(); act = float(me[c].iloc[0])
            if act == avg: continue
            EV.append((int(w), opp, role, m, pl, int(act > avg), act, round(avg, 1)))
E = pd.DataFrame(EV, columns=["week", "def", "role", "m", "pl", "over", "act", "avg"])
# FanDuel main-line events
v = json.load(open(sys.argv[2]))["values"]; H = {c: i for i, c in enumerate(v[0])}
def imp(o):
    o = float(o); return 100 / (o + 100) if o > 0 else -o / (-o + 100)
best = {}
for r in v[1:]:
    r = r + [""] * (len(v[0]) - len(r))
    if str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS"): continue
    try: o = float(r[H["FanDuel odds"]]); pm = float(r[H["Raw model %"]]); w = int(float(r[0]))
    except Exception: continue
    if not (-170 <= o <= 150) or (o > 0 and o < 100): continue
    k = (w, r[H["Player"]], r[H["Market"]]); d = abs(imp(o) - 0.5238)
    if k not in best or d < best[k][0]: best[k] = (d, r[H["Opp"]], r[H["Result"]] == "HIT", pm, imp(o), r[H["Line (X+)"]])
role_of = {}
for (team, w), g in P.groupby(["team", "week"]):
    for role, pl in roles(team, w).items(): role_of[(int(w), pl)] = role
FD = []
for (w, pl, m), (d, opp, hit, pm, bi, ln) in best.items():
    role = role_of.get((w, pl))
    if role and m in MK[role]: FD.append((w, opp, role, m, pl, int(hit), pm, bi, ln))
F = pd.DataFrame(FD, columns=["week", "def", "role", "m", "pl", "hit", "pm", "bi", "ln"])
print(f"own-avg events {len(E)} (weeks {E.week.min()}-{E.week.max()}), FD main-line events {len(F)} (weeks {sorted(F.week.unique())})")
lg = E.groupby(["role", "m"]).over.mean(); lgF = F.groupby(["role", "m"]).hit.mean()
print("league over-own-avg rate:", {f"{a}/{b}": round(x, 3) for (a, b), x in lg.items()})
print("league FD main-line hit rate:", {f"{a}/{b}": round(x, 3) for (a, b), x in lgF.items()})
# predictive test
K = 4
def shr(df, w, d, role, m, k=K):
    pr = df[(df.week < w) & (df["def"] == d) & (df.role == role) & (df.m == m)]
    base = df[(df.week < w) & (df.role == role) & (df.m == m)].over.mean()
    if np.isnan(base): return None, None
    return (pr.over.sum() + k * base) / (len(pr) + k), base
F["x"] = [ (lambda s, b: (s - b) if s is not None else 0.0)(*shr(E, r.week, r["def"], r.role, r.m)) for _, r in F.iterrows()]
lgt = lambda p: math.log(max(min(p, 0.999), 0.001) / (1 - max(min(p, 0.999), 0.001)))
F["z"] = F.pm.map(lgt)
def ll(y, p): p = np.clip(p, 1e-4, 1 - 1e-4); return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
res = []
for w in sorted(F.week.unique()):
    tr, te = F[F.week != w], F[F.week == w]
    best_b, best_l = 0.0, 9
    for b in np.arange(-3, 6.01, 0.25):
        l = ll(tr.hit.values, 1 / (1 + np.exp(-(tr.z + b * tr.x)))); 
        if l < best_l: best_l, best_b = l, b
    base = ll(te.hit.values, 1 / (1 + np.exp(-te.z))); adj = ll(te.hit.values, 1 / (1 + np.exp(-(te.z + best_b * te.x))))
    res.append((int(w), len(te), round(best_b, 2), round(base, 4), round(adj, 4)))
    print(f"week {w}: n={len(te)} b={best_b:+.2f} model LL {base:.4f} -> with defense {adj:.4f} ({adj - base:+.4f})")
# same test with the book's price instead of the model %
F["zb"] = F.bi.map(lgt)
for w in sorted(F.week.unique()):
    tr, te = F[F.week != w], F[F.week == w]
    best_b, best_l = 0.0, 9
    for b in np.arange(-3, 6.01, 0.25):
        l = ll(tr.hit.values, 1 / (1 + np.exp(-(tr.zb + b * tr.x))))
        if l < best_l: best_l, best_b = l, b
    base = ll(te.hit.values, 1 / (1 + np.exp(-te.zb))); adj = ll(te.hit.values, 1 / (1 + np.exp(-(te.zb + best_b * te.x))))
    print(f"  vs book price, week {w}: b={best_b:+.2f} book LL {base:.4f} -> {adj:.4f} ({adj - base:+.4f})")
# per-defense table for the site
tab = {}
for (d, role, m), g in E.groupby(["def", "role", "m"]):
    f = F[(F["def"] == d) & (F.role == role) & (F.m == m)]
    tab.setdefault(d, {}).setdefault(role, {})[m] = {"n": int(len(g)), "over": int(g.over.sum()), "lg": round(float(lg[(role, m)]), 3),
        "fn": int(len(f)), "fh": int(f.hit.sum()), "flg": round(float(lgF.get((role, m), float("nan"))), 3) if (role, m) in lgF else None,
        "games": [[int(x.week), x.pl, x.act, x.avg] for x in g.sort_values("week").itertuples()]}
if len(sys.argv) > 3:
    json.dump({"weeks": [int(E.week.min()), int(E.week.max())], "fd_weeks": sorted(int(x) for x in F.week.unique()), "k": K, "test": res, "def": tab}, open(sys.argv[3], "w"))
    print("wrote", sys.argv[3])
