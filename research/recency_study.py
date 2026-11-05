"""Walk-forward test of the per-game baseline itself (nflverse weekly stats, REG season, weeks >= 3, players with 2+ prior games).
Candidates for the baseline a prop line is judged against:
  mean      plain season-to-date mean (what the sheet uses)
  ewma_h2   exponentially weighted, half-life 2 games
  ewma_h3   half-life 3 games
  last3     mean of the last 3 games
  shrink    season mean shrunk toward the position-wide mean with k=2 pseudo-games (k=2) - the short-sample fix
  shrink4   same with k=4
  lvl0.93   rushing-yards level test: season mean x 0.93 (rushing props ran 7 points hot in week 6)
Reports MAE and bias (actual - baseline) by stat, and separately for players with < 5 vs >= 5 prior games.
"""
import csv, sys, statistics as st, collections
files = sys.argv[1:]
POS = ("QB", "RB", "WR", "TE")
STATS = {"QB": [("passing_yards", "attempts"), ("rushing_yards", "carries")], "RB": [("rushing_yards", "carries"), ("receiving_yards", "targets"), ("receptions", "targets")],
         "WR": [("receiving_yards", "targets"), ("receptions", "targets")], "TE": [("receiving_yards", "targets"), ("receptions", "targets")]}
rows = []
for f in files:
    for r in csv.DictReader(open(f)):
        if r.get("season_type") != "REG" or r["position"] not in POS: continue
        try: w = int(r["week"])
        except: continue
        rows.append({"season": r["season"], "week": w, "player": r["player_display_name"], "pos": r["position"],
                     **{k: float(r[k] or 0) for k in ("passing_yards", "attempts", "rushing_yards", "carries", "receiving_yards", "targets", "receptions")}})
def ewma(h, hl):
    ws = [0.5 ** ((len(h) - 1 - i) / hl) for i in range(len(h))]; return sum(w * x for w, x in zip(ws, h)) / sum(ws)
out = collections.defaultdict(list)   # (pos, stat, method, sample) -> (actual, base)
for season in sorted({r["season"] for r in rows}):
    S = [r for r in rows if r["season"] == season]
    for W in sorted({r["week"] for r in S}):
        if W < 3: continue
        prior = [r for r in S if r["week"] < W]; cur = [r for r in S if r["week"] == W]
        for pos in POS:
            for stat, vol in STATS[pos]:
                ph = collections.defaultdict(list)
                for r in sorted(prior, key=lambda r: r["week"]):
                    if r["pos"] == pos and r[vol] > 0: ph[r["player"]].append(r[stat])
                allv = [x for h in ph.values() for x in h]; pm = st.mean(allv) if allv else 0
                for r in cur:
                    if r["pos"] != pos or r[vol] <= 0: continue
                    h = ph.get(r["player"])
                    if not h or len(h) < 2: continue
                    m = st.mean(h)
                    if m < (30 if "yards" in stat else 2): continue
                    n = len(h); samp = "<5g" if n < 5 else ">=5g"
                    cands = {"mean": m, "ewma_h2": ewma(h, 2), "ewma_h3": ewma(h, 3), "last3": st.mean(h[-3:]), "shrink2": (n * m + 2 * pm) / (n + 2), "shrink4": (n * m + 4 * pm) / (n + 4)}
                    if stat == "rushing_yards": cands["lvl0.93"] = 0.93 * m
                    for k, b in cands.items():
                        out[(pos, stat, k, samp)].append((r[stat], b)); out[(pos, stat, k, "all")].append((r[stat], b))
def mae(p): return st.mean(abs(a - b) for a, b in p)
def bias(p): return st.mean(a - b for a, b in p)
print(f"{'pos':3s} {'stat':16s} {'method':8s} | {'all n':>6s} {'MAE':>6s} {'bias':>6s} | {'<5g n':>6s} {'MAE':>6s} {'bias':>6s} | {'>=5g n':>6s} {'MAE':>6s} {'bias':>6s}")
keys = sorted({(p, s, k) for p, s, k, _ in out})
for p, s, k in keys:
    A = out[(p, s, k, "all")]; L = out.get((p, s, k, "<5g"), []); G = out.get((p, s, k, ">=5g"), [])
    f = lambda x: f"{len(x):6d} {mae(x):6.2f} {bias(x):+6.2f}" if x else " " * 20
    print(f"{p:3s} {s:16s} {k:8s} | {f(A)} | {f(L)} | {f(G)}")
