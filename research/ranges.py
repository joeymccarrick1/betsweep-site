"""Real outcome ranges (owner 11/6): price a line from the player's own game-to-game shape instead of the model's bell curve.
For each graded frozen leg (legsnaps, Weeks 6+): the player's earlier games this season give ratios x_i / his mean; they are mixed with the
position-market pool of ratios (weight n / (n + K)), scaled to the model's projection; P(X >= line) = weighted share of scaled outcomes at or
above the line (kernel-smoothed with a +-0.5 jitter). Compared with the raw model % on log loss, per market, leave-nothing-out (it only uses
games before the leg's week). Usage: python3 -I research/ranges.py <legsnaps.json> <gamelog.json> [out.json]
"""
import sys, json, math, collections
L = json.load(open(sys.argv[1]))["values"]; H = {c: i for i, c in enumerate(L[0])}
G = json.load(open(sys.argv[2]))["values"]; GH = {c: i for i, c in enumerate(G[0])}
COL = {"Rushing Yards": "Rush Yds", "Receiving Yards": "Rec Yds", "Receptions": "Receptions", "Passing Yards": "Pass Yds", "Longest Reception": "Longest Rec"}
def f(x):
    try: return float(x)
    except Exception: return None
games = collections.defaultdict(list)   # (player, market) -> [(week, value)]
pos_of = {}
for r in G[1:]:
    w = f(r[0])
    if w is None: continue
    pos_of[r[1]] = r[GH["Pos"]]
    for m, c in COL.items():
        v = f(r[GH[c]]) if GH[c] < len(r) else None
        if v is not None: games[(r[1], m)].append((int(w), v))
def ratios(xs):
    mu = sum(xs) / len(xs)
    return [x / mu for x in xs] if mu > 0 else []
def prob(pl, m, proj, ln, w, K):
    mine = [v for (ww, v) in games.get((pl, m), []) if ww < w]
    pool = []
    pos = pos_of.get(pl)
    for (p2, m2), xs in games.items():
        if m2 != m or pos_of.get(p2) != pos: continue
        xs2 = [v for (ww, v) in xs if ww < w]
        if len(xs2) >= 4 and sum(xs2) / len(xs2) >= (0.3 * proj): pool += ratios(xs2)
    if not pool or proj <= 0: return None
    rm = ratios(mine) if len(mine) >= 3 else []
    wm = len(rm) / (len(rm) + K) if rm else 0.0
    def share(rs):
        if not rs: return 0.0
        c = 0.0
        for r_ in rs:
            x = proj * r_
            c += min(1.0, max(0.0, (x - (ln - 1.0)) / 1.0)) if m in ("Receptions",) else (1.0 if x >= ln - 0.5 else 0.0)
        return c / len(rs)
    p = wm * share(rm) + (1 - wm) * share(pool)
    return min(0.97, max(0.03, p))
def ll(p, y): p = min(max(p, 1e-4), 1 - 1e-4); return -(y * math.log(p) + (1 - y) * math.log(1 - p))
legs = []
for r in L[1:]:
    r = r + [""] * (len(L[0]) - len(r))
    if str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS") or r[H["Market"]] not in COL: continue
    w, rp, pj, ln = f(r[0]), f(r[H["Raw model %"]]), f(r[H["Projection"]]), f(r[H["Line (X+)"]])
    bk = f(r[H["Book implied %"]])
    if None in (w, rp, pj, ln, bk): continue
    legs.append((int(w), r[H["Player"]], r[H["Market"]], pj, ln, rp, bk, int(r[H["Result"]] == "HIT")))
out = {}
for K in (4, 8):
    res = collections.defaultdict(lambda: [0, 0.0, 0.0, 0.0])
    for (w, pl, m, pj, ln, rp, bk, y) in legs:
        p = prob(pl, m, pj, ln, w, K)
        if p is None: continue
        c = res[m]; c[0] += 1; c[1] += ll(rp, y); c[2] += ll(p, y); c[3] += ll(0.5 * p + 0.5 * bk, y)
    print(f"K={K}")
    for m, (n, a, b2, cb) in sorted(res.items()):
        print(f"  {m:18s} n={n:4d} log loss: model {a/n:.4f} | ranges {b2/n:.4f} ({(b2-a)/n:+.4f}) | ranges blended 50/50 with book {cb/n:.4f}")
        out[f"{K}|{m}"] = {"n": n, "model": round(a / n, 4), "ranges": round(b2 / n, 4), "ranges_book": round(cb / n, 4)}
if len(sys.argv) > 3: json.dump(out, open(sys.argv[3], "w"), indent=1)
