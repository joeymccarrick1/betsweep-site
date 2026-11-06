"""Per-market recalibration of the shown % (owner 11/6 "real outcome ranges"): shown = sigmoid(c + a*logit(raw model) + b*logit(FanDuel implied)).
The intercept c carries the skew a bell curve misses (rushing / passing yards: a typical game lands below the average, so X+ overs near the
projection miss more than half the time). Fit leave-one-week-out on graded frozen legs (Weeks 6+) vs today's 50/50 blend.
Usage: python3 -I research/recal.py <legsnaps.json> [out.json]
"""
import sys, json, math, collections
L = json.load(open(sys.argv[1]))["values"]; H = {c: i for i, c in enumerate(L[0])}
def f(x):
    try: return float(x)
    except Exception: return None
def ll(p, y): p = min(max(p, 1e-4), 1 - 1e-4); return -(y * math.log(p) + (1 - y) * math.log(1 - p))
lg = lambda p: math.log(min(max(p, 1e-4), 1 - 1e-4) / (1 - min(max(p, 1e-4), 1 - 1e-4))); sg = lambda z: 1 / (1 + math.exp(-z))
rows = collections.defaultdict(list)
for r in L[1:]:
    r = r + [""] * (len(L[0]) - len(r))
    if str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS"): continue
    rp, bk, w = f(r[H["Raw model %"]]), f(r[H["Book implied %"]]), f(r[0])
    if None in (rp, bk, w): continue
    rows[r[H["Market"]]].append((int(w), lg(rp), lg(bk), int(r[H["Result"]] == "HIT"), rp, bk))
GA = [i / 10 for i in range(0, 9)]; GB = [i / 10 for i in range(0, 13)]; GC = [i / 20 for i in range(-10, 5)]
def fit(xs):
    best = None
    for a in GA:
        for b in GB:
            for c in GC:
                l = sum(ll(sg(c + a * za + b * zb), y) for _, za, zb, y, _, _ in xs) / len(xs)
                if best is None or l < best[0]: best = (l, a, b, c)
    return best[1:]
out = {}
for m, xs in rows.items():
    base = sum(ll(0.5 * rp + 0.5 * bk, y) for _, _, _, y, rp, bk in xs) / len(xs); tot = 0.0; per = []
    for wk in sorted({x[0] for x in xs}):
        tr = [x for x in xs if x[0] != wk]; te = [x for x in xs if x[0] == wk]; a, b, c = fit(tr); per.append((wk, a, b, c))
        tot += sum(ll(sg(c + a * za + b * zb), y) for _, za, zb, y, _, _ in te)
    a, b, c = fit(xs)
    out[m] = {"n": len(xs), "today": round(base, 4), "recal_lowo": round(tot / len(xs), 4), "a": a, "b": b, "c": c, "per_week": per}
    print(f"{m:18s} n={len(xs):5d} today {base:.4f} -> recal (held out) {tot/len(xs):.4f} ({tot/len(xs)-base:+.4f}); all-weeks fit a={a} b={b} c={c}; per held-out week {per}")
if len(sys.argv) > 2: json.dump(out, open(sys.argv[2], "w"), indent=1)
