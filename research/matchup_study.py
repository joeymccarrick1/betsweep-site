"""Walk-forward test of a per-stat opponent multiplier on nflverse weekly stats.
For each (season, week W >= 3): baseline = player's mean of weeks < W; opponent factor f = (opp allowed per game to that position,
weeks < W) / (league per game to that position, weeks < W); candidate = baseline * (1 + w*(f_shrunk-1)).
Reports MAE and, more importantly for props, BIAS (actual - projection) by opponent bucket (tough = f in bottom 6, soft = top 6).
"""
import csv, sys, statistics as st, collections, math
files = sys.argv[1:]
POS = ("QB", "RB", "WR", "TE")
STATS = {"QB": [("passing_yards", "attempts"), ("rushing_yards", "carries")],
         "RB": [("rushing_yards", "carries"), ("receiving_yards", "targets"), ("receptions", "targets")],
         "WR": [("receiving_yards", "targets"), ("receptions", "targets")],
         "TE": [("receiving_yards", "targets"), ("receptions", "targets")]}
rows = []
for f in files:
    for r in csv.DictReader(open(f)):
        if r.get("season_type") != "REG" or r["position"] not in POS: continue
        try: w = int(r["week"])
        except: continue
        rows.append({"season": r["season"], "week": w, "player": r["player_display_name"], "pos": r["position"], "team": r["team"], "opp": r["opponent_team"],
                     **{k: float(r[k] or 0) for k in ("passing_yards", "attempts", "rushing_yards", "carries", "receiving_yards", "targets", "receptions")}})
seasons = sorted({r["season"] for r in rows})
out = collections.defaultdict(lambda: collections.defaultdict(list))   # (pos,stat,w) -> bucket -> (actual, proj)
for season in seasons:
    S = [r for r in rows if r["season"] == season]
    weeks = sorted({r["week"] for r in S})
    for W in weeks:
        if W < 3: continue
        prior = [r for r in S if r["week"] < W]; cur = [r for r in S if r["week"] == W]
        for pos in POS:
            for stat, vol in STATS[pos]:
                # opponent allowed per game (team-pos-stat total per game) and league average
                tg = collections.defaultdict(float); tgames = collections.defaultdict(set)
                for r in prior:
                    if r["pos"] == pos: tg[r["opp"]] += r[stat]; tgames[r["opp"]].add(r["week"])
                allowed = {t: tg[t] / len(tgames[t]) for t in tg if tgames[t]}
                if len(allowed) < 20: continue
                lg = st.mean(allowed.values())
                ngames = {t: len(tgames[t]) for t in tg}
                order = sorted(allowed, key=lambda t: allowed[t])   # low allowed = tough
                tough = set(order[:6]); soft = set(order[-6:])
                # player baselines
                ph = collections.defaultdict(list)
                for r in prior:
                    if r["pos"] == pos and r[vol] > 0: ph[r["player"]].append(r[stat])
                for r in cur:
                    if r["pos"] != pos or r[vol] <= 0: continue
                    h = ph.get(r["player"])
                    if not h or len(h) < 2: continue
                    base = st.mean(h)
                    if base < (30 if "yards" in stat else 2): continue   # meaningful props only
                    f = allowed.get(r["opp"])
                    if f is None: continue
                    fr = f / lg; n = ngames[r["opp"]]
                    fsh = (n * fr + 4 * 1.0) / (n + 4)
                    b = "tough" if r["opp"] in tough else "soft" if r["opp"] in soft else "mid"
                    for w in (0.0, 0.5, 1.0):
                        proj = base * (1 + w * (fsh - 1))
                        out[(pos, stat, f"sym{w:.1f}")][b].append((r[stat], proj)); out[(pos, stat, f"sym{w:.1f}")]["all"].append((r[stat], proj))
                    for w in (0.5, 0.75, 1.0):   # one-sided: only a tough defense moves the number
                        proj = base * (1 + w * min(0.0, fsh - 1))
                        out[(pos, stat, f"dn{w:.2f}")][b].append((r[stat], proj)); out[(pos, stat, f"dn{w:.2f}")]["all"].append((r[stat], proj))
def mae(p): return st.mean(abs(a - b) for a, b in p)
def bias(p): return st.mean(a - b for a, b in p)
def ratio(p): return sum(a for a, _ in p) / sum(b for _, b in p)
print(f"seasons {seasons}; weeks >= 3; players with 2+ prior games")
print(f"{'pos':3s} {'stat':16s} {'w':>7s} | {'n':>5s} {'MAE':>6s} {'bias':>6s} | tough n {'bias':>6s} {'act/proj':>8s} | soft n {'bias':>6s} {'act/proj':>8s}")
for (pos, stat, w), B in sorted(out.items()):
    A = B["all"]; T = B["tough"]; Sf = B["soft"]
    print(f"{pos:3s} {stat:16s} {w:>7s} | {len(A):5d} {mae(A):6.2f} {bias(A):+6.2f} | {len(T):5d} {bias(T):+6.2f} {ratio(T):8.3f} | {len(Sf):5d} {bias(Sf):+6.2f} {ratio(Sf):8.3f}")
