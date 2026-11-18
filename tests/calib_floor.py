"""calib.py's receiving-yards floor cut and touchdown weight (11/18, research/floor_depth.py).
The number every page shows must be the calibrated one, the cut must never jump on a one-yard move or turn a player's ladder upside
down, and the under must stay the other side of the same line. Unit checks need nothing; the page checks need a built out/ and site/."""
import collections, json, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
import calib as C
OUT = os.environ.get("OUT") or os.path.join(HERE, "out"); SITE = os.environ.get("SITE") or os.path.join(HERE, "site")
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)
RY = "Receiving Yards"; cut = C.FLOOR_CUT[RY]; a, b, hi, d = C.FLOOR_BAND
plain = C.shown(0.8, 0.7, RY)
check(abs(plain - C.shrink(0.8, 0.7, C.W_MARKET[RY])) < 1e-12, f"with no line or projection the number is the plain blend ({plain:.4f})")
check(0 < cut <= 0.03 and a < b < hi < d < 1, f"the cut is small ({cut * 100:.2f} points) and its band sits under the projection ({b:.0%}-{hi:.0%})")
check(abs(C.shown(0.8, 0.7, RY, line=42, proj=60) - (plain - cut)) < 1e-12, "a line at 70% of the projection loses the whole cut")
check(all(C.shown(0.8, 0.7, RY, line=x, proj=60) == plain for x in (10, 24, 30, 54, 60, 75, 120)), "a deep floor, a line at the projection and a line over it are untouched")
step = max(abs(C.floor_cut(RY, r / 10, 100) - C.floor_cut(RY, (r + 1) / 10, 100)) for r in range(0, 1500))
check(step <= cut / ((b - a) * 1000) + 1e-9 and C.floor_cut(RY, 52.5, 100) == cut / 2, f"no jump anywhere along the band (largest move per 0.1% of projection {step * 100:.3f} points)")
o = C.shown(0.62, 0.55, RY, line=42, proj=60); u = C.shown(0.38, 0.45, "Under " + RY, line=42, proj=60)
check(abs(o + u - 1) < 1e-12 and u > C.shown(0.38, 0.45, "Under " + RY), f"the under is the other side of the same number ({o:.4f} + {u:.4f})")
check(all(C.shown(0.8, 0.7, m, line=42, proj=60) == C.shown(0.8, 0.7, m) for m in ("Receptions", "Passing Yards", "Anytime TD", "Rushing Yards", "Longest Reception", "Rush + Rec Yards")),
      "no other market is cut (receptions passed 4 of 5 held-out weeks, not all - re-tested on Tuesdays)")
check(all(C.shown(0.8, 0.7, RY, line=l, proj=p) == plain for l, p in (("x", 60), (42, 0), (42, None), (None, 60), (42, "")))
      and C.shown(None, 0.7, RY, line=42, proj=60) is None and C.shown(0.8, None, RY, line=42, proj=60) == 0.8, "a missing or broken line / projection / price falls back cleanly")
check(0.99 >= C.shown(0.999, 0.999, RY, line=42, proj=60) and C.shown(0.011, 0.011, RY, line=42, proj=60) >= 0.01, "the number stays inside 1-99%")
k, sl = C.PRICE_KNOT, C.PRICE_SLOPE
check(C.squeezed("Receptions", k) == k and C.squeezed("Receptions", 0.5) == 0.5 and abs(C.squeezed("Receptions", 0.78) - (k + sl * (0.78 - k))) < 1e-12 and 0 < sl < 1,
      f"a price above {k:.0%} is read at part strength ({sl}), and nothing changes at or below it")
check(all(C.squeezed(m, 0.8) == 0.8 for m in ("Rushing Yards", "Longest Reception", "Anytime TD", "Rush + Rec Yards")) and abs(C.shown(0.3, 0.8, "Under Receptions") - C.shrink(0.3, 0.8, C.W_MARKET["Receptions"])) < 1e-12,
      "only the over side of the three blend markets is squeezed")
agree = C.shown(0.78, 0.78, "Receptions")
check(abs(agree - (C.W_MARKET["Receptions"] * 0.78 + (1 - C.W_MARKET["Receptions"]) * (k + sl * 0.08))) < 1e-12 and agree < 0.78, f"a leg the model merely agrees with at -355 shows under its price ({agree:.3f} against 0.780)")
steps = [C.shown(0.7, (b + 1) / 1000, RY) - C.shown(0.7, b / 1000, RY) for b in range(500, 900)]
check(min(steps) > 0 and max(steps) <= (1 - C.W_MARKET[RY]) / 1000 + 1e-12, "a shorter price never lowers the number, and there is no jump at the knot")
wt = C.W_MARKET["Anytime TD"]
check(wt == 0.3 and abs(C.shown(0.40, 0.30, "Anytime TD") - (0.30 + wt * 0.10)) < 1e-12, f"touchdowns: the model moves the price by {wt:.0%} of its lead (11/18, two straight weeks FanDuel alone graded better)")

bd = os.path.join(OUT, "builder_data.json")
if os.path.exists(bd):
    L = [l for l in json.load(open(bd))["legs"] if not l.get("gl") and l.get("raw_p") is not None and l.get("bk") is not None and l.get("p") is not None]
    ry = [l for l in L if l.get("m") == RY]
    # build_builder's defense-vs-role step (defrole.py, l["dv"]) tilts the calibrated number a little afterwards; legs without it must match exactly
    gap = lambda l, mk: abs(l["p"] - C.shown(l["raw_p"], l["bk"], mk, line=l.get("ln"), proj=l.get("proj")))
    off = [l for l in ry if gap(l, RY) > (0.03 if l.get("dv") else 0.00011)]; plain_n = sum(1 for l in ry if not l.get("dv"))
    check(len(ry) > 0 and not off, f"every receiving-yards leg in the builder shows the calibrated number ({plain_n} exactly, {len(ry) - plain_n} within the defense-vs-role tilt" + (f"; first off: {off[0]['pl']} {off[0]['ln']}+ shows {off[0]['p']}" if off else "") + ")")
    band = [l for l in ry if C.floor_cut(RY, l.get("ln"), l.get("proj")) > 0]; bx = [l for l in band if not l.get("dv")]
    check(all(l["p"] < C.shrink(l["raw_p"], l["bk"], C.W_MARKET[RY]) for l in bx) and all(abs(l["e"] - (l["p"] - l["bk"])) < 0.00011 for l in ry),
          f"{len(band)} of them sit in the band ({len(bx)} untilted, each under the plain blend); every edge is shown minus price")
    for m2 in ("Receptions", "Passing Yards"):
        xs = [l for l in L if l.get("m") == m2]; o2 = [l for l in xs if gap(l, m2) > (0.03 if l.get("dv") else 0.00011)]
        sq = sum(1 for l in xs if l["bk"] > C.PRICE_KNOT)
        check(not o2, f"every {m2.lower()} leg shows the calibrated number ({len(xs)} legs, {sq} read at part strength" + (f"; first off: {o2[0]['pl']} {o2[0]['ln']}+ shows {o2[0]['p']}" if o2 else "") + ")")
    safe = [l for l in L if l.get("tier") == "safe"]
    check(all(l["o"] > -200 and l["p"] >= 0.65 and l["raw_p"] >= l["bk"] for l in safe), f"no short-priced tier pick is priced -200 or shorter ({len(safe)} picks" + (", shortest " + str(min(l['o'] for l in safe)) if safe else "") + ")")
    red = [f"{l['pl']} {l['ln']:g}+ ({f[1]})" for l in safe for f in (l.get("fh") or []) if f[0] == "bad"]
    check(not red, "no short-priced tier pick carries one of the builder's red flags" + (f" (first: {red[0]})" if red else ""))
    thin = [f"{l['pl']} {l['ln']:g}+ {l.get('nz')}" for l in safe if not (l.get("nz") and l["nz"][1] >= 4 and l["nz"][0] * 3 < l["nz"][1])]
    check(not thin, "every short-priced tier pick has four games on record and finished under half its line in fewer than a third of them" + (f" (first: {thin[0]})" if thin else ""))
    un = [l for l in L if l.get("m") == "Under " + RY and not l.get("flat")]
    offu = [l for l in un if gap(l, "Under " + RY) > (0.03 if l.get("dv") else 0.00011)]
    check(not offu, f"receiving-yards unders follow the same rule ({len(un)} legs)")
    lad = collections.defaultdict(list)
    for l in ry: lad[l["pl"]].append(l)
    flip = []
    for pl, xs in lad.items():
        xs.sort(key=lambda l: l["ln"])
        for lo, up in zip(xs, xs[1:]):
            p_lo = C.shrink(lo["raw_p"], lo["bk"], C.W_MARKET[RY]); p_up = C.shrink(up["raw_p"], up["bk"], C.W_MARKET[RY])
            if p_lo >= p_up and lo["p"] < up["p"] - 0.00011: flip.append(f"{pl} {lo['ln']:g}+ {lo['p']} under {up['ln']:g}+ {up['p']}")
    check(not flip, f"the cut turns no ladder upside down ({len(lad)} players' ladders" + (f"; {flip[0]}" if flip else "") + ")")
    td = [l for l in L if l.get("m") == "Anytime TD" and " or " not in l["pl"] and "/" not in l["pl"]]
    offt = [l for l in td if abs(l["p"] - C.shown(l["raw_p"], l["bk"], "Anytime TD")) > (0.03 if l.get("dv") else 0.00011)]
    check(not offt, f"touchdown legs carry the new weight ({len(td)} legs" + (f"; first off: {offt[0]['pl']} shows {offt[0]['p']}" if offt else "") + ")")
else: print("note: no built builder data - page checks skipped")
pg = os.path.join(SITE, "how", "index.html")
if os.path.exists(pg):
    t = open(pg, encoding="utf-8").read()
    check(f"{b * 100:.0f} to {hi * 100:.0f} percent of a player's projection" in t and "about a third on touchdowns" in t and "counts at half strength" in t,
          "How BetSweep picks says what the numbers now do (the floor cut, the touchdown share, the short-price reading)")
print(f"{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
