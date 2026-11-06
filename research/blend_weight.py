"""research/blend_weight.py (owner 11/6 "start from FanDuel's number"): graded frozen legs (legsnaps, Latest Snapshot, HIT/MISS) -
Brier and log loss of p = w*raw + (1-w)*book (book de-vigged at 1.045 for one-sided rungs) for w = 0..1, per market and pooled,
plus leave-one-week-out choice of w. Usage: python3 research/blend_weight.py <legsnaps.json>"""
import json, sys, math, collections
v = json.load(open(sys.argv[1]))["values"]; H = {c: i for i, c in enumerate(v[0])}
R = collections.defaultdict(list)
for r in v[1:]:
    r = r + [""] * (len(v[0]) - len(r))
    if str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS"): continue
    try: raw = float(r[H["Raw model %"]]); bk = float(r[H["Book implied %"]]); wk = int(float(r[0]))
    except Exception: continue
    if raw > 1: raw /= 100
    if bk > 1: bk /= 100
    R[r[H["Market"]]].append((wk, raw, min(0.97, bk / 1.045), 1 if r[H["Result"]] == "HIT" else 0))
WS = [i / 10 for i in range(11)]
def score(xs, w):
    b = ll = 0
    for _, raw, bk, y in xs:
        p = min(0.98, max(0.02, w * raw + (1 - w) * bk)); b += (p - y) ** 2; ll -= math.log(p if y else 1 - p)
    return b / len(xs), ll / len(xs)
allx = [x for xs in R.values() for x in xs]
for m, xs in [("ALL", allx)] + sorted(R.items(), key=lambda kv: -len(kv[1])):
    if len(xs) < 150: continue
    sc = {w: score(xs, w) for w in WS}; best = min(WS, key=lambda w: sc[w][1])
    weeks = sorted({x[0] for x in xs}); lowo = []
    for wk in weeks:
        tr = [x for x in xs if x[0] != wk]; te = [x for x in xs if x[0] == wk]
        if not te or not tr: continue
        bw = min(WS, key=lambda w: score(tr, w)[1]); lowo.append((wk, bw, score(te, bw)[1], score(te, 0.5)[1], score(te, 0.0)[1]))
    print(f"{m:20s} n={len(xs):5d} best w={best:.1f}  logloss w=0 {sc[0.0][1]:.4f} | w=.3 {sc[0.3][1]:.4f} | w=.5 {sc[0.5][1]:.4f} | w=1 {sc[1.0][1]:.4f}")
    for wk, bw, a, b5, b0 in lowo: print(f"      held-out wk {wk}: picked w={bw:.1f} -> {a:.4f}  (w=.5 {b5:.4f}, book only {b0:.4f})")
