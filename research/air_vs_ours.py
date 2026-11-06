"""research/air_vs_ours.py: does last-3-game air-yards info explain OUR receiving-yards projection's misses (legsnaps Weeks 6-8, one row per
player-week)? Regress (actual - our projection) on (L3 air yards - L3 rec yds) and L3 air-yards share; leave-one-week-out MAE vs ours."""
import csv, json, sys, collections, statistics as st
import numpy as np
v = json.load(open("/tmp/legsnaps.json"))["values"]; H = {c: i for i, c in enumerate(v[0])}
seen = {}; rows = []
for r in v[1:]:
    r = r + [""] * (len(v[0]) - len(r))
    if r[H["Market"]] != "Receiving Yards" or r[H["Latest Snapshot"]].upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS"): continue
    k = (r[0], r[H["Player"]])
    if k in seen: continue
    try: seen[k] = (int(r[0]), r[H["Player"]], float(r[H["Projection"]]), float(r[H["Actual"]]))
    except Exception: pass
g = collections.defaultdict(list)
for r in csv.DictReader(open("/tmp/gt9/in/stats_player_week_2026.csv")):
    if r.get("season_type") != "REG": continue
    g[r["player_display_name"]].append((int(r["week"]), float(r["receiving_yards"] or 0), float(r["receiving_air_yards"] or 0), float(r["air_yards_share"] or 0)))
for wk, pl, proj, act in seen.values():
    prev = sorted(x for x in g.get(pl, []) if x[0] < wk)[-3:]
    if len(prev) < 2: continue
    rows.append((wk, act - proj, st.mean(x[2] for x in prev) - st.mean(x[1] for x in prev), st.mean(x[3] for x in prev), proj, act))
print("player-weeks", len(rows))
for hold in (6, 7, 8):
    tr = [r for r in rows if r[0] != hold]; te = [r for r in rows if r[0] == hold]
    A = np.array([[1, r[2], r[3]] for r in tr]); b, *_ = np.linalg.lstsq(A, np.array([r[1] for r in tr]), rcond=None)
    ours = np.mean([abs(r[5] - r[4]) for r in te]); adj = np.mean([abs(r[5] - (r[4] + b[0] + b[1] * r[2] + b[2] * r[3])) for r in te])
    print(f"held-out wk {hold}: our MAE {ours:.2f} -> with air-yards term {adj:.2f} (n={len(te)}, coef {np.round(b, 3).tolist()})")
