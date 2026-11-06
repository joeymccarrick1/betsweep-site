"""research/clv_fit.py (owner 11/6 "train on how the price moves"): how much of the model's disagreement with FanDuel does the market adopt?
For every builder leg this week: FanDuel's price at the build (bk), the raw model (raw_p), and FanDuel's current / closing price (mirror links).
Per market, least squares on the logit scale:  logit(now) - logit(bk) = w * (logit(raw) - logit(bk)) + c.
w = the share of our disagreement the market moved toward (0 = no information, 1 = the market fully adopts the model). Bootstrap CI.
Usage: python3 research/clv_fit.py <builder data-*.js> <links.json> [out.json]"""
import json, math, sys, random, collections
def lg(p): p = min(0.98, max(0.02, p)); return math.log(p / (1 - p))
def imp(o): o = float(o); return 100 / (o + 100) if o > 0 else -o / (-o + 100)
b = open(sys.argv[1]).read(); D = json.loads(b[b.index('{'):b.rstrip().rfind(';')])
L = json.load(open(sys.argv[2]))["values"]; H = {c: i for i, c in enumerate(L[0])}
now = {}
for r in L[1:]:
    try: now[str(r[0]).lower()] = float(r[H["FanDuel odds"]])
    except Exception: pass
rows = collections.defaultdict(list)
for l in D["legs"]:
    if l.get("gl") or l.get("raw_p") is None or l.get("o") is None or str(l.get("m", "")).startswith("Under "): continue
    ln = l["ln"]; lns = str(int(ln)) if float(ln) == int(ln) else str(ln)
    o2 = now.get(f"{l['pl']}|{l['m']}|{lns}".lower())
    if o2 is None or o2 == l["o"] and False: continue
    x = lg(l["raw_p"]) - lg(imp(l["o"])); y = lg(imp(o2)) - lg(imp(l["o"]))
    rows[l["m"]].append((x, y)); rows["ALL"].append((x, y))
def fit(xy):
    n = len(xy); mx = sum(x for x, _ in xy) / n; my = sum(y for _, y in xy) / n
    sxx = sum((x - mx) ** 2 for x, _ in xy); sxy = sum((x - mx) * (y - my) for x, y in xy)
    return sxy / sxx if sxx else 0.0
out = {}
random.seed(1)
for m, xy in sorted(rows.items(), key=lambda kv: -len(kv[1])):
    if len(xy) < 40: continue
    w = fit(xy); bs = sorted(fit([random.choice(xy) for _ in xy]) for _ in range(300))
    moved = sum(1 for x, y in xy if abs(y) > 0.05); agree = sum(1 for x, y in xy if abs(y) > 0.05 and x * y > 0)
    out[m] = {"n": len(xy), "w": round(w, 3), "ci": [round(bs[7], 3), round(bs[292], 3)], "moved": moved, "agree": agree}
    print(f"{m:22s} n={len(xy):5d} w={w:+.3f} 95% [{bs[7]:+.3f}, {bs[292]:+.3f}]  moved {moved}, toward the model {agree} ({agree / max(1, moved):.0%})")
if len(sys.argv) > 3: json.dump(out, open(sys.argv[3], "w"), indent=1)
