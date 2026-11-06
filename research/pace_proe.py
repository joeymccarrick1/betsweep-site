"""Pace + pass rate over expected (owner 11/6 "unused data"): do team pace and neutral PROE from nflverse play-by-play improve the projection
of a team's pass attempts in a game (the volume behind completions, passing yards and targets)?
Per team-game (REG): pass attempts (pass == 1, includes sacks / scrambles as dropbacks), offensive plays (pass + rush), neutral PROE = mean
pass_oe on plays with win prob 0.2-0.8 in quarters 1-3. Features are season averages BEFORE the game (3+ games).
Baseline: 0.65 x own dropbacks/g + 0.35 x opponent dropbacks allowed/g (the sheet formula's shape). Model: baseline + OLS on [own neutral PROE,
own plays/g, opp plays allowed/g, opp offense plays/g, opp neutral PROE]; fit 2022-24, test 2025 and 2026.
Usage: python3 -I research/pace_proe.py <dir with pbp_YYYY.csv.gz> [out.json]
"""
import sys, os, json
import numpy as np, pandas as pd
D = sys.argv[1]; rows = []
for y in range(2022, 2027):
    f = os.path.join(D, f"pbp_{y}.csv.gz")
    if not os.path.exists(f): continue
    p = pd.read_csv(f, usecols=["game_id", "season_type", "week", "posteam", "defteam", "pass", "rush", "pass_oe", "wp", "qtr", "play_type"], low_memory=False)
    p = p[(p.season_type == "REG") & p.posteam.notna() & p.play_type.isin(["pass", "run"])]
    neu = p[(p.wp.between(0.2, 0.8)) & (p.qtr <= 3)]
    g = p.groupby(["game_id", "week", "posteam", "defteam"]).agg(db=("pass", "sum"), plays=("pass", "size")).reset_index()
    pr = neu.groupby(["game_id", "posteam"]).pass_oe.mean().rename("proe").reset_index()
    g = g.merge(pr, on=["game_id", "posteam"], how="left"); g["season"] = y; rows.append(g)
G = pd.concat(rows).sort_values(["season", "week"])
feat = []
for (s), gs in G.groupby("season"):
    for _, r in gs.iterrows():
        pr = gs[gs.week < r.week]
        o = pr[pr.posteam == r.posteam]; d = pr[pr.defteam == r.defteam]; oo = pr[pr.posteam == r.defteam]
        if len(o) < 3 or len(d) < 3 or len(oo) < 3: continue
        feat.append(dict(season=s, week=r.week, team=r.posteam, y=r.db, base=0.65 * o.db.mean() + 0.35 * d.db.mean(),
                         proe=o.proe.mean(), plays=o.plays.mean(), dplays=d.plays.mean(), oplays=oo.plays.mean(), oproe=oo.proe.mean()))
X = pd.DataFrame(feat).dropna()
cols = ["proe", "plays", "dplays", "oplays", "oproe"]
tr = X[X.season <= 2024]
A = np.c_[np.ones(len(tr)), tr[cols].values]; beta = np.linalg.lstsq(A, (tr.y - tr.base).values, rcond=None)[0]
out = {"beta": dict(zip(["const"] + cols, [round(float(b), 4) for b in beta])), "test": {}}
for s in (2025, 2026):
    te = X[X.season == s]
    if not len(te): continue
    adj = te.base + np.c_[np.ones(len(te)), te[cols].values] @ beta
    mb, ma = float(np.abs(te.y - te.base).mean()), float(np.abs(te.y - adj).mean())
    b0 = float((tr.y - tr.base).mean()); mb0 = float(np.abs(te.y - te.base - b0).mean())   # baseline + its own average bias (fit on 2022-24), so the gain is the features
    out["test"][str(s)] = {"n": int(len(te)), "mae_base": round(mb0, 3), "mae_pace_proe": round(ma, 3)}
    print(f"{s}: n={len(te)} dropbacks MAE base {mb0:.3f} -> with pace/PROE {ma:.3f} ({ma - mb0:+.3f})")
print("beta", out["beta"])
if len(sys.argv) > 2: json.dump(out, open(sys.argv[2], "w"), indent=1)
