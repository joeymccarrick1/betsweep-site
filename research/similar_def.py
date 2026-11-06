"""research/similar_def.py (owner 11/6, "Meyers stood out vs similar defenses"): does a player's production against the 3 past opponents most
like this week's defense (the Game preview split: same profile and distance as build_dossier.py, built only from earlier weeks) predict his
game - beyond his season average and beyond the plain matchup (opponent's yards allowed)? Walk-forward 2024-2026, weeks 5+.
Part 2: graded FanDuel legs 2026 (legsnaps) - hit rate vs price by the similar-defense split.
Usage: python3 research/similar_def.py <dir: team_Y.csv (nflverse stats_team_week), stats_player_week_Y.csv> <legsnaps.json>"""
import csv, sys, os, math, json, collections, statistics as st
import numpy as np
D = sys.argv[1]
def f(x):
    try: return float(x or 0)
    except Exception: return 0.0
KEYS = ("pyd", "ryd", "ypp", "sk", "to"); WT = {"pyd": 1.0, "ryd": 1.0, "ypp": 0.8, "sk": 0.6, "to": 0.4}
STAT = {"QB": "passing_yards", "RB": "rushing_yards", "WR": "receiving_yards", "TE": "receiving_yards"}
rows = []; legsx = {}
for y in (2024, 2025, 2026):
    tf = os.path.join(D, f"team_{y}.csv") if os.path.exists(os.path.join(D, f"team_{y}.csv")) else os.path.join(D, f"stats_team_week_{y}.csv")
    OFF = {}
    for r in csv.DictReader(open(tf)):
        if r.get("season_type", "REG") != "REG": continue
        OFF[(r["team"], int(r["week"]))] = {"opp": r["opponent_team"], "pyd": f(r["passing_yards"]) - f(r.get("sack_yards_lost")), "ryd": f(r["rushing_yards"]),
            "plays": f(r["attempts"]) + f(r["carries"]) + f(r["sacks_suffered"]), "sk": f(r["sacks_suffered"]),
            "to": f(r["passing_interceptions"]) + f(r.get("sack_fumbles_lost")) + f(r.get("rushing_fumbles_lost")) + f(r.get("receiving_fumbles_lost"))}
    PG = collections.defaultdict(list)
    for r in csv.DictReader(open(os.path.join(D, f"stats_player_week_{y}.csv"))):
        if r.get("season_type") != "REG" or r.get("position") not in STAT: continue
        PG[(r["player_display_name"], r["team"])].append((int(r["week"]), r["opponent_team"], f(r[STAT[r["position"]]]), r["position"]))
    weeks = sorted({w for _, w in OFF})
    for W in weeks:
        if W < 5: continue
        DEFG = collections.defaultdict(list)
        for (t, w), l in OFF.items():
            if w < W: DEFG[l["opp"]].append(l)
        PROF = {d: {"pyd": st.mean(x["pyd"] for x in ls), "ryd": st.mean(x["ryd"] for x in ls), "ypp": sum(x["pyd"] + x["ryd"] for x in ls) / max(1, sum(x["plays"] for x in ls)),
                    "sk": st.mean(x["sk"] for x in ls), "to": st.mean(x["to"] for x in ls)} for d, ls in DEFG.items() if len(ls) >= 3}
        if len(PROF) < 20: continue
        MU = {k: st.mean(PROF[d][k] for d in PROF) for k in KEYS}; SD = {k: st.pstdev([PROF[d][k] for d in PROF]) or 1 for k in KEYS}
        Z = {d: {k: (PROF[d][k] - MU[k]) / SD[k] for k in KEYS} for d in PROF}
        dist = lambda a, b: math.sqrt(sum(WT[k] * (Z[a][k] - Z[b][k]) ** 2 for k in KEYS))
        for (pl, tm), gs in PG.items():
            cur = [g for g in gs if g[0] == W]; prev = [g for g in gs if g[0] < W]
            if not cur or len(prev) < 4: continue
            opp = cur[0][1]; pos = cur[0][3]
            if opp not in Z: continue
            s = st.mean(g[2] for g in prev)
            if s < (150 if pos == "QB" else 25): continue
            past = [g for g in prev if g[1] in Z and g[1] != opp]
            if len(past) < 3: continue
            near = sorted(past, key=lambda g: dist(opp, g[1]))[:3]
            v = st.mean(g[2] for g in near)
            mk = "pyd" if pos in ("QB", "WR", "TE") else "ryd"
            rows.append((y, pos, (v - s) / s, Z[opp][mk], (cur[0][2] - s) / s))
            legsx[(y, W, pl)] = ((v - s) / s, Z[opp][mk])
print("player-games", len(rows))
for y in (2025, 2026):
    tr = [r for r in rows if r[0] < y]; te = [r for r in rows if r[0] == y]
    for lab, cols in (("matchup only", [3]), ("similar-defense only", [2]), ("both", [2, 3])):
        X = np.array([[1] + [r[c] for c in cols] for r in tr]); b, *_ = np.linalg.lstsq(X, np.array([r[4] for r in tr]), rcond=None)
        Xt = np.array([[1] + [r[c] for c in cols] for r in te]); yt = np.array([r[4] for r in te])
        print(f"test {y} {lab:22s} coef {np.round(b[1:], 3).tolist()}  MAE {np.mean(np.abs(Xt @ b - yt)):.4f} (season-avg only {np.mean(np.abs(yt - np.mean([r[4] for r in tr]))):.4f}, n={len(te)})")
# part 2: graded 2026 FanDuel legs by the split
v = json.load(open(sys.argv[2]))["values"]; H = {c: i for i, c in enumerate(v[0])}
MK = {"QB": "Passing Yards", "RB": "Rushing Yards", "WR": "Receiving Yards", "TE": "Receiving Yards"}
stt = collections.defaultdict(lambda: [0, 0, 0.0, 0.0])
for r in v[1:]:
    r = r + [""] * (len(v[0]) - len(r))
    if str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS") or r[H["Market"]] not in ("Receiving Yards", "Rushing Yards", "Passing Yards", "Receptions"): continue
    x = legsx.get((2026, int(float(r[0])), r[H["Player"]]))
    if not x: continue
    b = "similar-def +20% or more" if x[0] >= 0.2 else "similar-def -20% or worse" if x[0] <= -0.2 else "in between"
    o = f(r[H["FanDuel odds"]]); dec = 1 + o / 100 if o > 0 else 1 + 100 / -o; hit = r[H["Result"]] == "HIT"
    for k in ((b, "all"), (b, r[H["Market"]])):
        s_ = stt[k]; s_[0] += 1; s_[1] += hit; s_[2] += f(r[H["Book implied %"]]); s_[3] += (dec - 1) if hit else -1
for k in sorted(stt):
    n, h, bk, u = stt[k]
    if n >= 30: print(f"{k[0]:26s} {k[1]:16s} n={n:4d} hit {h / n:.1%} vs price {bk / n:.1%} ROI {u / n:+.1%}")
