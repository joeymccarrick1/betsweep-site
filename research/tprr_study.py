#!/usr/bin/env python3
"""Volume-quality study (owner 11/4, item 6): does snap-share direction / targets-per-route tell us anything the season average does not?

Data: nflverse weekly stats (targets, receptions, rec yds) + snap counts (offense_pct, offense_snaps) for 2025 and 2026; the model's frozen
leg projections for Weeks 6-8 2026 (dig/L.json: Receptions / Receiving Yards market Proj + Actual).
Routes proxy: offense_snaps x (team dropbacks / team plays) where team plays = max offense_snaps on the team that game, dropbacks = team pass
attempts + sacks.

Tests (all out of sample - features use weeks < w only):
  T1 2025 + 2026: predict this week's targets with (a) season average, (b) season average x snap-trend factor (last-2 snap share / season snap
     share, shrunk toward 1 by k), (c) TPRR_season x routes_proj (routes_proj = last-2 snap share x team's average plays x dropback rate).
     k fitted on 2025, evaluated on 2026 -> MAE.
  T2 the model's own Week 6-8 frozen projections (Receptions, Receiving Yards): proj vs proj x factor(k from 2025) -> MAE, by week.
Decision rule (RUNBOOK): ship a multiplier only if T2 improves MAE in 2 of 3 weeks and overall; otherwise the flag stays and nothing changes.
"""
import pandas as pd, numpy as np, json, re, sys
pd.set_option("display.width", 200)
def nn(x):
    x = re.sub(r"[.'’]", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
def load(year):
    s = pd.read_csv(f"stats_{year}.csv", low_memory=False); s = s[(s.season_type == "REG") & (s.position.isin(["RB", "WR", "TE"]))]
    sn = pd.read_csv(f"snaps_{year}.csv"); sn = sn[(sn.game_type == "REG") & (sn.position.isin(["RB", "WR", "TE", "FB"]))]
    # team plays per game = max offense snaps on the team; dropbacks = team attempts + sacks (from QB rows)
    q = pd.read_csv(f"stats_{year}.csv", low_memory=False); q = q[q.season_type == "REG"]
    tm = q.groupby(["team", "week"]).agg(att=("attempts", "sum"), sk=("sacks_suffered", "sum")).reset_index(); tm["db"] = tm.att + tm.sk
    pl = sn.groupby(["team", "week"]).offense_snaps.max().reset_index().rename(columns={"offense_snaps": "plays"})
    tm = tm.merge(pl, on=["team", "week"], how="inner"); tm["dbrate"] = tm.db / tm.plays
    sn["k"] = sn.player.map(nn); s["k"] = s.player_display_name.map(nn)
    d = s.merge(sn[["k", "team", "week", "offense_pct", "offense_snaps"]], on=["k", "team", "week"], how="inner").merge(tm[["team", "week", "db", "plays", "dbrate"]], on=["team", "week"], how="left")
    d["routes"] = d.offense_snaps * d.dbrate
    d["year"] = year
    return d.sort_values(["k", "week"])
def features(d):
    rows = []
    for k, g in d.groupby("k"):
        g = g.sort_values("week"); W = g.week.values
        for i in range(len(g)):
            if i < 3: continue   # need 3 prior games
            prev = g.iloc[:i]; cur = g.iloc[i]
            last2 = prev.iloc[-2:]
            rows.append({"k": k, "year": cur.year, "week": cur.week, "team": cur.team, "pos": cur.position, "tgt": cur.targets, "rec": cur.receptions, "recy": cur.receiving_yards,
                         "tgt_avg": prev.targets.mean(), "rec_avg": prev.receptions.mean(), "recy_avg": prev.receiving_yards.mean(),
                         "snap_season": prev.offense_pct.mean(), "snap_l2": last2.offense_pct.mean(), "tprr": prev.targets.sum() / max(prev.routes.sum(), 1),
                         "tprr_l2": last2.targets.sum() / max(last2.routes.sum(), 1), "plays_avg": prev.plays.mean(), "dbrate_avg": prev.dbrate.mean(), "n": i})
    return pd.DataFrame(rows)
def factor(f, k):
    r = (f.snap_l2 / f.snap_season.clip(lower=0.05)).clip(0.5, 2.0)
    return 1 + k * (r - 1)
def mae(a, b): return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))
if __name__ == "__main__":
    F25 = features(load(2025)); F26 = features(load(2026))
    F25 = F25[F25.tgt_avg >= 2]; F26 = F26[F26.tgt_avg >= 2]   # players the market prices
    print(f"rows: 2025 {len(F25)}, 2026 {len(F26)}")
    # T1: fit k on 2025
    best = None
    for k in [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]:
        m = mae(F25.tgt, F25.tgt_avg * factor(F25, k))
        print(f"  2025 targets MAE with snap-trend k={k:.1f}: {m:.3f}")
        if best is None or m < best[1]: best = (k, m)
    kbest = best[0]; print(f"best k on 2025: {kbest}")
    for yr, F in (("2025", F25), ("2026", F26)):
        base = mae(F.tgt, F.tgt_avg); adj = mae(F.tgt, F.tgt_avg * factor(F, kbest))
        routes_proj = F.snap_l2 * F.plays_avg * F.dbrate_avg; tp = mae(F.tgt, F.tprr * routes_proj); tp2 = mae(F.tgt, (0.7 * F.tprr + 0.3 * F.tprr_l2) * routes_proj)
        print(f"T1 {yr}: targets MAE  season-avg {base:.3f} | x snap-trend(k={kbest}) {adj:.3f} | TPRR x routes {tp:.3f} | TPRR(70/30 l2) x routes {tp2:.3f}")
        # rising / falling subsets
        r = F.snap_l2 / F.snap_season.clip(lower=0.05)
        for lab, m in (("snaps up 15+", r >= 1.15), ("snaps down 15+", r <= 0.85), ("flat", (r > 0.85) & (r < 1.15))):
            S = F[m]
            if len(S): print(f"     {lab:<16} n={len(S):>5}  actual/avg targets {S.tgt.mean()/S.tgt_avg.mean():.3f}  rec yds {S.recy.mean()/S.recy_avg.mean():.3f}   MAE avg {mae(S.tgt, S.tgt_avg):.3f} -> adj {mae(S.tgt, S.tgt_avg*factor(S,kbest)):.3f}")
    # T2: the model's frozen projections, weeks 6-8 2026
    L = json.load(open("/home/claude/work/dig/L.json"))
    out = []
    for mk, fld in (("Receptions", "rec"), ("Receiving Yards", "recy")):
        seen = set()
        for l in L:
            if l["Market"] != mk or l.get("Actual") in ("", None) or l.get("HasStat") != "TRUE": continue
            key = (l["Week"], l["Player"])
            if key in seen: continue
            seen.add(key)
            try: proj = float(l["Proj"]); act = float(l["Actual"]); w = int(l["Week"])
            except Exception: continue
            f = F26[(F26.k == nn(l["Player"])) & (F26.week == w)]
            if f.empty: continue
            out.append({"market": mk, "week": w, "player": l["Player"], "proj": proj, "act": act, "fac": float(factor(f.iloc[[0]], kbest).iloc[0]), "snap_l2": float(f.snap_l2.iloc[0]), "snap_season": float(f.snap_season.iloc[0])})
    T = pd.DataFrame(out)
    print("\nT2: the model's frozen Week 6-8 projections x snap-trend factor (k fitted on 2025)")
    for mk, g in T.groupby("market"):
        print(f"  {mk}: n={len(g)}  MAE model {mae(g.act, g.proj):.3f} -> adjusted {mae(g.act, g.proj*g.fac):.3f}  (bias model {np.mean(g.proj-g.act):+.3f}, adjusted {np.mean(g.proj*g.fac-g.act):+.3f})")
        for w, gw in g.groupby("week"): print(f"     week {w}: n={len(gw)}  {mae(gw.act, gw.proj):.3f} -> {mae(gw.act, gw.proj*gw.fac):.3f}")
        r = g.snap_l2 / g.snap_season.clip(lower=0.05)
        for lab, m in (("snaps up 15+", r >= 1.15), ("snaps down 15+", r <= 0.85)):
            S = g[m]
            if len(S) >= 8: print(f"     {lab:<14} n={len(S):>4} actual/proj {S.act.mean()/S.proj.mean():.3f}  MAE {mae(S.act,S.proj):.3f} -> {mae(S.act,S.proj*S.fac):.3f}")
    T.to_csv("tprr_t2.csv", index=False)
