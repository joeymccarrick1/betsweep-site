"""When our own formula disagrees with the closing spread / total, who wins? (owner 11/5 "our own record on game lines")
Formula per team (walk-forward, games before this week only, 3+ games): 0.65 x pts/game + 0.35 x opponent pts allowed/game, then the
11/5 injury adjustment from actual absences (own main passer absent -2.6; absent regular pass catchers -2.4 x target share).
Closing line = nflverse games.csv spread_line (home minus away, + = home favoured) and total_line.
Lean = side / total our margin / total points to by 1.5+ pts vs the line. Graded ATS (pushes dropped).
Usage: python3 -I research/gl_disagree.py <dir with games.csv + stats_player_week_YYYY.csv> [out.json]
"""
import sys, os, json, numpy as np, pandas as pd
D = sys.argv[1]
G = pd.read_csv(os.path.join(D, "games.csv")); G = G[(G.game_type == "REG") & G.season.between(2023, 2026)]
P = pd.concat([pd.read_csv(os.path.join(D, f"stats_player_week_{y}.csv"), low_memory=False) for y in range(2023, 2027)])
P = P[P.season_type == "REG"][["season", "week", "team", "player_id", "attempts", "targets"]].fillna(0)
def team_rows(g):
    return [(g.season, g.week, g.home_team, g.away_team, g.home_score, g.away_score), (g.season, g.week, g.away_team, g.home_team, g.away_score, g.home_score)]
T = pd.DataFrame([x for _, g in G[G.home_score.notna()].iterrows() for x in team_rows(g)], columns=["season", "week", "team", "opp", "pf", "pa"])
def inj(s, t, w):
    grp = P[(P.season == s) & (P.team == t)]; prior = grp[grp.week < w]; pw = prior.week.nunique()
    if pw < 3: return 0.0
    here = set(grp[grp.week == w].player_id)
    if not here: return 0.0   # game not played yet -> no absence info in the stats (live weeks use the availability tab instead)
    ag = prior.groupby("player_id").agg(n=("week", "nunique"), att=("attempts", "sum"), tg=("targets", "sum"))
    tt = prior.groupby("week").targets.sum().sum(); ta = prior.groupby("week").attempts.sum().sum()
    adj = 0.0; qb = ag.att.idxmax()
    if ag.loc[qb, "att"] >= 0.6 * ta and qb not in here: adj -= 2.6
    reg = ag[(ag.n >= 0.6 * pw) & ~ag.index.isin(here)]
    return adj - 2.4 * reg.tg.sum() / max(tt, 1)
rows = []
for _, g in G.iterrows():
    if pd.isna(g.home_score) or pd.isna(g.spread_line): continue
    pr = T[(T.season == g.season) & (T.week < g.week)]
    h = pr[pr.team == g.home_team]; a = pr[pr.team == g.away_team]
    if len(h) < 3 or len(a) < 3: continue
    fh = 0.65 * h.pf.mean() + 0.35 * a.pa.mean() + inj(g.season, g.home_team, g.week)
    fa = 0.65 * a.pf.mean() + 0.35 * h.pa.mean() + inj(g.season, g.away_team, g.week)
    rows.append(dict(season=int(g.season), week=int(g.week), home=g.home_team, away=g.away_team, mm=fh - fa, mt=fh + fa, sp=g.spread_line, tl=g.total_line, am=g.home_score - g.away_score, atot=g.home_score + g.away_score))
X = pd.DataFrame(rows)
def grade(df, gap):
    side = df[(df.mm - df.sp).abs() >= gap].copy()
    side["pick_home"] = side.mm > side.sp; cov = side.am - side.sp; side = side[cov != 0]
    sw = int(((cov[side.index] > 0) == side.pick_home).sum()); sn = len(side)
    tot = df[(df.mt - df.tl).abs() >= gap].copy(); d = tot.atot - tot.tl; tot = tot[d != 0]
    tw = int(((tot.atot > tot.tl) == (tot.mt > tot.tl)).sum()); tn = len(tot)
    return {"side": [sw, sn], "total": [tw, tn]}
out = {"by_season": {}, "by_gap": {}}
for gap in (1.5, 3, 5):
    out["by_gap"][str(gap)] = grade(X, gap)
for s in sorted(X.season.unique()):
    out["by_season"][str(s)] = {str(gap): grade(X[X.season == s], gap) for gap in (1.5, 3, 5)}
cur = X[X.season == 2026]
out["2026_weeks"] = {str(w): grade(cur[cur.week == w], 3) for w in sorted(cur.week.unique())}
out["2026_weeks5"] = {str(w): grade(cur[cur.week == w], 5) for w in sorted(cur.week.unique())}   # paper bet: fade our total when 5+ off
pc = lambda a: f"{a[0]}-{a[1]-a[0]} ({a[0]/a[1]*100:.1f}%)" if a[1] else "-"
for gap, r in out["by_gap"].items(): print(f"all 2023-26, gap >= {gap}: side {pc(r['side'])}, total {pc(r['total'])}")
for s, d in out["by_season"].items(): print(s, {g: (pc(r['side']), pc(r['total'])) for g, r in d.items()})
print("2026 by week (gap>=3):", {w: (pc(r['side']), pc(r['total'])) for w, r in out["2026_weeks"].items()})
if len(sys.argv) > 2: json.dump(out, open(sys.argv[2], "w")); print("wrote", sys.argv[2])
