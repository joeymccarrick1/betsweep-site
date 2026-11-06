"""Questionable translator (owner 11/6): what a game status + the final practice of the week mean for a skill player who normally plays
(30%+ of offensive snaps over his previous 4 games). nflverse injuries 2024-25 (report_status, practice_status = the last practice listed)
joined to nflverse snap counts. Output: P(plays), and when he plays: his snap share vs normal and P(under 75% of normal).
Usage: python3 -I research/q_translator.py <dir with injuries_YYYY.csv + snap_counts_YYYY.csv> [out.json]
"""
import sys, os, json
import pandas as pd
D = sys.argv[1]; rows = []
def nm(s): return s.str.lower().str.replace(r"[^a-z ]", "", regex=True).str.replace(r"\s+(jr|sr|ii|iii|iv|v)$", "", regex=True).str.strip()
for y in (2024, 2025):
    inj = pd.read_csv(os.path.join(D, f"injuries_{y}.csv"), low_memory=False)
    inj = inj[(inj.game_type == "REG") & inj.position.isin(["QB", "RB", "WR", "TE"]) & inj.report_status.isin(["Questionable", "Doubtful"])].copy()
    sc = pd.read_csv(os.path.join(D, f"snap_counts_{y}.csv"), low_memory=False); sc = sc[sc.game_type == "REG"].copy()
    sc["nm"] = nm(sc.player); inj["nm"] = nm(inj.full_name)
    g = {k: v.sort_values("week") for k, v in sc.groupby(["nm", "team"])}
    for r in inj.itertuples():
        me = g.get((r.nm, r.team))
        if me is None: continue
        prior = me[me.week < r.week].tail(4)
        if len(prior) < 2 or prior.offense_pct.mean() < 0.3: continue
        cur = me[me.week == r.week]; played = int(len(cur) > 0 and cur.offense_snaps.iloc[0] > 0)
        ratio = float(cur.offense_pct.iloc[0] / prior.offense_pct.mean()) if played else 0.0
        ps = str(r.practice_status); ps = "DNP" if "Did Not" in ps else "Limited" if "Limited" in ps else "Full" if "Full" in ps else "none"
        rows.append((y, "QB" if r.position == "QB" else "skill", r.report_status, ps, played, ratio))
X = pd.DataFrame(rows, columns=["y", "grp", "st", "ps", "played", "ratio"])
out = {}
for (st, ps), g in X.groupby(["st", "ps"]):
    pl = g[g.played == 1]
    out[f"{st}|{ps}"] = {"n": int(len(g)), "play": round(float(g.played.mean()), 3), "snap": round(float(pl.ratio.mean()), 3) if len(pl) else None,
                         "low": round(float((pl.ratio < 0.75).mean()), 3) if len(pl) else None, "by_season": {str(s): round(float(x.played.mean()), 3) for s, x in g.groupby("y")}}
for k, v in sorted(out.items()): print(k, v)
qb = X[X.grp == "QB"]; print("QB only:", qb.groupby(["st", "ps"]).played.agg(["size", "mean"]).round(3).to_dict("index"))
if len(sys.argv) > 2: json.dump(out, open(sys.argv[2], "w"), indent=1)
