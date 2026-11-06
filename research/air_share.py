"""research/air_share.py (owner 11/6 idea 3): do air-yards signals lead receiving production beyond targets? WR/TE, REG, previous-3-game
averages -> next game's receiving yards and receptions. A: rec yds + targets + receptions (last 3). B: A + receiving air yards + air-yards
share + WOPR. Ordinary least squares fit on 2024, scored on 2025 and 2026 (MAE). Usage: python3 research/air_share.py <dir with stats_player_week_Y.csv>"""
import csv, sys, os, collections, statistics as st
import numpy as np
D = sys.argv[1]; data = collections.defaultdict(list)
def f(r, k):
    try: return float(r.get(k) or 0)
    except Exception: return 0.0
for y in (2024, 2025, 2026):
    for r in csv.DictReader(open(os.path.join(D, f"stats_player_week_{y}.csv"))):
        if r.get("season_type") != "REG" or r.get("position") not in ("WR", "TE"): continue
        data[(y, r["player_id"])].append((int(r["week"]), f(r, "receiving_yards"), f(r, "targets"), f(r, "receptions"), f(r, "receiving_air_yards"), f(r, "air_yards_share"), f(r, "wopr")))
X = collections.defaultdict(list)
for (y, pid), g in data.items():
    g.sort()
    for i in range(3, len(g)):
        prev = g[i - 3:i]; m = [st.mean(x[j] for x in prev) for j in range(1, 7)]
        if m[1] < 2: continue
        X[y].append((m, g[i][1], g[i][3]))
def design(rows, full): return np.array([[1, m[0], m[1], m[2]] + ([m[3], m[4], m[5]] if full else []) for m, _, _ in rows])
for tgt, ti in (("rec yds", 1), ("receptions", 2)):
    ytr = np.array([r[ti] for r in X[2024]])
    for full in (False, True):
        b, *_ = np.linalg.lstsq(design(X[2024], full), ytr, rcond=None)
        s = []
        for y in (2025, 2026):
            pr = design(X[y], full) @ b; yt = np.array([r[ti] for r in X[y]]); s.append(f"{y} MAE {np.mean(np.abs(pr - yt)):.3f} (n={len(yt)})")
        print(f"{tgt:10s} {'+ air yards' if full else 'baseline  '}: " + " | ".join(s))
