"""research/floor_depth.py (owner 11/18 "strengthening our probabilities when choosing legs"): how well the shown % holds up by how
deep a yardage line sits under the player's projection (line / projection), on the graded frozen legs (legsnaps, Latest Snapshot, HIT/MISS).

Prints, each run:
  1. the live rule against FanDuel alone, week by week, per market (the two-straight-weeks check calib.py's weights move on);
  2. shown % minus hit rate by depth band, per market (where the shown number runs hot or cold);
  3. the receiving-yards floor cut, leave-one-week-out: half the bias measured on the other weeks, scored on the held-out week;
  4. WATCH items that did not pass and are re-tested here every Tuesday: a heavier model weight on deep receiving lines, and
     the deep line + big model lead cell (one rung per player-week, at FanDuel's price).

  5. FanDuel's shortest prices: hit rate by price, the half-strength reading of a price above calib.PRICE_KNOT scored leave-one-week-out,
     and the short-priced tier with and without its shortest prices, week by week (build_builder's price cap on that tier).

Adopt only what is better in every held-out week (calib.py). Usage: python3 research/floor_depth.py <legsnaps.json>"""
import json, sys, math, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import calib as C

v = json.load(open(sys.argv[1]))["values"]; H = {c: i for i, c in enumerate(v[0])}
def num(x):
    try: return float(str(x).replace("%", "").replace(",", "").replace("+", ""))
    except Exception: return None
L = []
for r in v[1:]:
    r = r + [""] * (len(v[0]) - len(r))
    if str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS"): continue
    raw, bk, wk = num(r[H["Raw model %"]]), num(r[H["Book implied %"]]), num(r[0])
    if raw is None or bk is None or wk is None: continue
    if raw > 1: raw /= 100
    if bk > 1: bk /= 100
    ln, pj, od = num(r[H["Line (X+)"]]), num(r[H["Projection"]]), num(r[H["FanDuel odds"]])
    m = r[H["Market"]]
    L.append({"w": int(wk), "m": m, "raw": raw, "bk": bk, "ln": ln, "pj": pj, "o": od, "pl": r[H["Player"]], "y": 1 if r[H["Result"]] == "HIT" else 0,
              "r": (ln / pj) if (ln is not None and pj and m != "Anytime TD") else None})
WK = sorted({x["w"] for x in L})
SEEN = 10   # the watch cells in section 4 were found on Weeks 6-10 (11/18); later weeks are out of sample for them
cl = lambda p: min(0.99, max(0.01, p))
def ll(xs, f): return sum(-(math.log(cl(f(x))) if x["y"] else math.log(1 - cl(f(x)))) for x in xs) / max(1, len(xs))
base = lambda x: C.shown(x["raw"], x["bk"], x["m"])                      # the live rule with no depth step
live = lambda x: C.shown(x["raw"], x["bk"], x["m"], line=x["ln"], proj=x["pj"])   # the live rule as the site prices it
book = lambda x: x["bk"]
print(f"{len(L)} graded legs, weeks {WK[0]}-{WK[-1]}")

print("\n1. live rule vs FanDuel alone, log loss by week (minus = the live rule was better that week)")
for m in sorted({x["m"] for x in L}, key=lambda m: -sum(1 for x in L if x["m"] == m)):
    xs = [x for x in L if x["m"] == m]
    if len(xs) < 150: continue
    d = [(w, ll([x for x in xs if x["w"] == w], live) - ll([x for x in xs if x["w"] == w], book)) for w in WK if any(x["w"] == w for x in xs)]
    streak = 0
    for _, g in reversed(d):
        if g > 0: streak += 1
        else: break
    print(f"  {m:20s} n={len(xs):5d}  " + "  ".join(f"wk{w} {g:+.4f}" for w, g in d) + (f"   <- lost {streak} straight" if streak >= 2 else ""))

BANDS = ((0, 0.40), (0.40, 0.55), (0.55, 0.70), (0.70, 0.85), (0.85, 1.00), (1.00, 1.25), (1.25, 9))
print("\n2. shown % minus hit rate, in points, by line / projection (n) [weeks the shown number ran high]")
for m in ("Receiving Yards", "Receptions", "Rushing Yards", "Passing Yards", "Longest Reception"):
    out = []
    for lo, hi in BANDS:
        xs = [x for x in L if x["m"] == m and x["r"] is not None and lo < x["r"] <= hi]
        if len(xs) < 40: out.append(f"{'-':>18s}"); continue
        hot = sum(1 for w in WK if [x for x in xs if x["w"] == w] and sum(live(x) - x["y"] for x in xs if x["w"] == w) > 0)
        out.append(f"{(sum(live(x) for x in xs) - sum(x['y'] for x in xs)) / len(xs) * 100:+5.1f} ({len(xs):4d}) [{hot}/{len(WK)}]".rjust(18))
    print(f"  {m:18s}" + "".join(out))
print("  " + " " * 18 + "".join(f"{(str(int(lo*100)) + '-' + (str(int(hi*100)) if hi < 9 else 'up') + '%'):>18s}" for lo, hi in BANDS))

def tent(r, a=0.50, b=0.55, c=0.85, d=0.90):
    if r is None or r <= a or r >= d: return 0.0
    return (r - a) / (b - a) if r < b else (1.0 if r <= c else (d - r) / (d - c))
RY = [x for x in L if x["m"] == "Receiving Yards" and x["r"] is not None]
print("\n3. receiving-yards floor cut (line at 55-85% of the projection), leave-one-week-out: cut = half the bias measured on the other weeks")
tot = [0, 0, 0]; wins = 0
for w in WK:
    tr = [x for x in RY if x["w"] != w and 0.55 <= x["r"] <= 0.85]; te = [x for x in RY if x["w"] == w and tent(x["r"]) > 0]
    if not tr or not te: continue
    cut = 0.5 * sum(base(x) - x["y"] for x in tr) / len(tr)
    a, b = ll(te, base), ll(te, lambda x: base(x) - cut * tent(x["r"]))
    wins += b < a; tot[0] += a * len(te); tot[1] += b * len(te); tot[2] += len(te)
    print(f"  held-out wk {w}: cut {cut*100:4.2f} pts  log loss {a:.4f} -> {b:.4f}  ({'better' if b < a else 'WORSE'}, n={len(te)})")
if tot[2]: print(f"  pooled {tot[0]/tot[2]:.4f} -> {tot[1]/tot[2]:.4f} on {tot[2]} legs; better in {wins} of {len(WK)} weeks")
xs = [x for x in RY if 0.55 <= x["r"] <= 0.85]
if xs: print(f"  all weeks: shown runs {sum(base(x) - x['y'] for x in xs) / len(xs) * 100:+.2f} pts high on {len(xs)} legs before the cut; live cut = {getattr(C, 'FLOOR_CUT', {}).get('Receiving Yards', 0) * 100:.2f} pts")
for m in ("Receptions", "Rushing Yards", "Passing Yards"):   # the same band, tapers and half-size cut as it would be applied
    ys = [x for x in L if x["m"] == m and x["r"] is not None]; res = []
    for w in WK:
        tr = [x for x in ys if x["w"] != w and 0.55 <= x["r"] <= 0.85]; te = [x for x in ys if x["w"] == w and tent(x["r"]) > 0]
        if len(tr) < 30 or not te: continue
        cut = 0.5 * sum(base(x) - x["y"] for x in tr) / len(tr); res.append(ll(te, base) - ll(te, lambda x: base(x) - cut * tent(x["r"])))
    if res: print(f"  same test, {m}: gain by week " + " ".join(f"{g:+.4f}" for g in res) + f"  better in {sum(1 for g in res if g > 0)} of {len(res)} weeks" + ("" if all(g > 0 for g in res) else "  (not adopted unless all)"))

print("\n4a. WATCH - a heavier model weight on deep receiving lines (weight fitted on the other weeks)")
for cutoff in (0.45, 0.50, 0.55, 0.60):
    seg = [x for x in RY if x["r"] <= cutoff]; res = []
    for w in WK:
        tr = [x for x in seg if x["w"] != w]; te = [x for x in seg if x["w"] == w]
        if not tr or not te: continue
        bw = min((ll(tr, lambda x, ww=ww: ww * x["raw"] + (1 - ww) * x["bk"]), ww) for ww in [i / 20 for i in range(21)])[1]
        res.append((bw, ll(te, base) - ll(te, lambda x: bw * x["raw"] + (1 - bw) * x["bk"])))
    print(f"  line <= {int(cutoff*100)}% of projection (n={len(seg)}): picked {[r[0] for r in res]}  gain by week " + " ".join(f"{g:+.4f}" for _, g in res) + f"  better in {sum(1 for _, g in res if g > 0)} of {len(res)}")

print("\n4b. WATCH - deep receiving line and the model well above the price: hit minus price, points (n) [weeks at or above price]")
leads = (0.05, 0.10, 0.15)
for dep in (0.40, 0.50, 0.55, 0.70, 9):
    out = []
    for ld in leads:
        xs = [x for x in RY if x["r"] <= dep and x["raw"] - x["bk"] >= ld]
        if len(xs) < 15: out.append(f"{'-':>24s}"); continue
        up = sum(1 for w in WK if [x for x in xs if x["w"] == w] and sum(x["y"] - x["bk"] for x in xs if x["w"] == w) >= 0)
        out.append(f"lead>={int(ld*100):2d}: {sum(x['y'] - x['bk'] for x in xs) / len(xs) * 100:+5.1f} ({len(xs):3d}) [{up}/{len(WK)}]".rjust(30))
    print(f"  line <= {('any' if dep == 9 else str(int(dep*100)) + '%'):4s}" + "".join(out))
dec = lambda o: 1 + o / 100 if o > 0 else 1 + 100 / -o
pick = {}
for x in RY:
    if x["r"] <= 0.55 and x["raw"] - x["bk"] >= 0.10 and x["o"]:
        k = (x["w"], x["pl"])
        if k not in pick or x["raw"] - x["bk"] > pick[k]["raw"] - pick[k]["bk"]: pick[k] = x
b = list(pick.values())
if b:
    u = sum((dec(x["o"]) - 1) if x["y"] else -1 for x in b); n = len(b); p0 = sum(x["bk"] for x in b) / n; h = sum(x["y"] for x in b)
    z = (h - n * p0) / math.sqrt(n * p0 * (1 - p0))
    print(f"  one rung per player-week (line <= 55%, lead >= 10): {h}/{n} = {h/n:.1%} vs price {p0:.1%}, {u/n:+.3f} units a leg, z = {z:.2f}; by week " +
          " ".join(f"wk{w} {sum(x['y'] for x in b if x['w'] == w)}/{sum(1 for x in b if x['w'] == w)}" for w in WK))
    print("  (z under 2 with a cell picked after looking is not proof: tracked, not a lead)")
    new = [x for x in b if x["w"] > SEEN]   # the only honest test of a cell picked after looking: the weeks graded after it was picked
    if new:
        n2 = len(new); h2 = sum(x["y"] for x in new); p2 = sum(x["bk"] for x in new) / n2; u2 = sum((dec(x["o"]) - 1) if x["y"] else -1 for x in new)
        print(f"  SINCE IT WAS PICKED (Week {SEEN + 1} on): {h2}/{n2} = {h2/n2:.1%} vs price {p2:.1%}, {u2/n2:+.3f} units a leg  <- this line decides whether it becomes a tier")
    else: print(f"  nothing graded since it was picked (through Week {SEEN}); Week {SEEN + 1} is its first real test")

# ---- 5. short prices (11/18 morning) ----
BL = C.PRICE_MARKETS; B5 = [x for x in L if x["m"] in BL and x["o"]]
def with_price(knot, slope, f):
    """Run f with calib's reading of a short price set to (knot, slope); slope 1.0 = the price taken at face value."""
    k0, s0 = C.PRICE_KNOT, C.PRICE_SLOPE; C.PRICE_KNOT, C.PRICE_SLOPE = knot, slope
    try: return f()
    finally: C.PRICE_KNOT, C.PRICE_SLOPE = k0, s0
print(f"\n5a. hit rate by FanDuel price, {', '.join(m.lower() for m in BL)} (live knot {C.PRICE_KNOT:.0%}, slope {C.PRICE_SLOPE})")
for lo, hi in ((.50, .58), (.58, .64), (.64, .68), (.68, .72), (.72, .76), (.76, .82)):
    xs = [x for x in B5 if lo <= x["bk"] < hi]; n = len(xs)
    if n < 30: continue
    u = sum((dec(x["o"]) - 1) if x["y"] else -1 for x in xs) / n
    print(f"  price {lo:.0%}-{hi:.0%} ({-round(100*lo/(1-lo))} to {-round(100*hi/(1-hi))}): n={n:4d}  price {sum(x['bk'] for x in xs)/n:5.1%}  shown {sum(live(x) for x in xs)/n:5.1%}  hit {sum(x['y'] for x in xs)/n:5.1%}  {u:+.3f} a leg   hit by week " +
          " ".join(f"{sum(x['y'] for x in xs if x['w'] == w) / max(1, sum(1 for x in xs if x['w'] == w)):4.0%}" for w in WK))
xs = [x for x in L if x["bk"] >= 0.76 and x["o"]]
if xs: print(f"  every market at -317 or shorter: {len(xs)} legs, hit {sum(x['y'] for x in xs)/len(xs):.1%} against {sum(x['bk'] for x in xs)/len(xs):.1%}; units a leg by week " +
             " ".join(f"{sum((dec(x['o']) - 1) if x['y'] else -1 for x in xs if x['w'] == w) / max(1, sum(1 for x in xs if x['w'] == w)):+.2f}" for w in WK))
print("\n5b. reading a short price at part strength (slope fitted on the other weeks; HALF of that squeeze is what calib.py may adopt), gain by held-out week")
for knot in (0.68, 0.70, 0.72):
    full = []; half = []; picks = []
    for w in WK:
        tr = [x for x in B5 if x["w"] != w and x["bk"] > knot]; te = [x for x in B5 if x["w"] == w and x["bk"] > knot]
        if len(tr) < 50 or not te: continue
        g = min([i / 10 for i in range(11)], key=lambda g: with_price(knot, g, lambda: ll(tr, live))); picks.append(g)
        a = with_price(knot, 1.0, lambda: ll(te, live))
        full.append(a - with_price(knot, g, lambda: ll(te, live))); half.append(a - with_price(knot, (1 + g) / 2, lambda: ll(te, live)))
    print(f"  knot {knot:.0%}{' (live)' if abs(knot - C.PRICE_KNOT) < 1e-9 else '       '}: fitted slopes {picks}  full " + " ".join(f"{v:+.4f}" for v in full) + f" ({sum(1 for v in full if v > 0)}/{len(full)})   half " +
          " ".join(f"{v:+.5f}" for v in half) + f" ({sum(1 for v in half if v > 0)}/{len(half)})")
print("\n5c. the short-priced tier (shown 65%+, raw model at or over the price, best rung per player and market) by price cap")
SAFE_FLOOR = -200   # build_builder._SAFE_FLOOR: the tier takes no leg at this price or shorter
def tier5(omin):
    best = {}
    for x in B5:
        if live(x) >= 0.65 and x["raw"] >= x["bk"] and x["o"] > omin:
            k = (x["w"], x["pl"], x["m"])
            if k not in best or x["raw"] - x["bk"] > best[k]["raw"] - best[k]["bk"]: best[k] = x
    return list(best.values())
def line5(xs, tag):
    n = len(xs)
    if not n: print(f"  {tag}: none"); return
    u = sum((dec(x["o"]) - 1) if x["y"] else -1 for x in xs)
    print(f"  {tag:44s} n={n:3d}  hit {sum(x['y'] for x in xs)/n:5.1%}  price {sum(x['bk'] for x in xs)/n:5.1%}  {u:+6.1f} units ({u/n:+.3f} a leg)  by week " +
          "  ".join(f"{sum(x['y'] for x in xs if x['w'] == w)}/{sum(1 for x in xs if x['w'] == w)} {sum((dec(x['o']) - 1) if x['y'] else -1 for x in xs if x['w'] == w):+.1f}" for w in WK))
T5 = tier5(-10 ** 6)
line5(T5, "no price cap (the rule through Week 10)")
line5([x for x in T5 if x["o"] <= SAFE_FLOOR], f"  its picks at {SAFE_FLOOR} or shorter (now left out)")
for om in (-285, -257, -233, -213, -200, -180): line5(tier5(om), f"only longer than {om}" + (" (live)" if om == SAFE_FLOOR else ""))
new5 = [x for x in tier5(SAFE_FLOOR) if x["w"] > SEEN]; out5 = [x for x in T5 if x["o"] <= SAFE_FLOOR and x["w"] > SEEN]
if new5 or out5:
    print(f"  SINCE THE CAP (Week {SEEN + 1} on):"); line5(new5, "    kept"); line5(out5, "    left out")
else: print(f"  nothing graded since the cap went in (through Week {SEEN}); if the left-out legs start beating their price, lift it")
