"""The weekly fit of FanDuel's same-game discount and what the pages do with it (owner 11/25: better math, a range on long slips, every
typed price kept). research/sgp_discount.py site_quotes + the candidate formula; sgp.py load / price / spread.
  python3 tests/sgp_fit.py"""
import json, math, os, shutil, sys, tempfile
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "research"))
import sgp
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
S = sgp.load(); O = json.load(open(os.path.join(HERE, "research", "sgp_discount.json")))
check(0 <= S["c"] <= 0.05 and 1.5 <= S["p"] <= 3.5 and 0 <= S["dog"] <= 0.5 and 0.3 <= S["dog_under"] <= 0.5 and S["quotes"] >= 30, f"the fit loads inside its bounds (c {S['c']}, p {S['p']}, long-shot cut {S['dog']}, {S['quotes']} quotes)")
V = O.get("variants") or []
check(len(V) == 2 and sum(1 for v in V if "(in use)" in v["formula"]) == 1 and all(set(("median", "mean", "2-4 legs", "5+ legs")) <= set(v) for v in V), "the fit records the formula in use beside the candidate, each priced with every slip left out of its own fit")
now, cand = V[0], V[1]; keys = ("median", "mean", "2-4 legs", "5+ legs")
better = all(cand[k] <= now[k] + 1e-9 for k in keys) and sum(1 for k in keys if cand[k] < now[k] * 0.98) >= 2 and cand.get("per_long_shot", 0) > 0 and O["quotes"] >= 30
check(("(in use)" in cand["formula"]) == better and (O["dog"] > 0) == better, f"the candidate is in use only if it is no worse on all four measures and better on two (candidate {[cand[k] for k in keys]} vs {[now[k] for k in keys]}; in use: {O['dog'] > 0})")
sp = O.get("spread") or {}
check(set(sp) == {"2-4", "5-6", "7+"} and all(v["quotes"] >= 0 for v in sp.values()) and sum(v["quotes"] for v in sp.values()) == O["quotes"], f"how far off the estimate has been is measured for every length ({ {k: v['miss80'] for k, v in sp.items()} })")
# price / spread
T = {"c": 0.004, "p": 2.5, "dog": 0.0, "dog_under": 0.45, "spread": {"2-4": 0.09, "5-6": 0.24, "7+": 0.45}}
check(abs(sgp.price(4, 0.25, T) - math.exp(-0.004 * 3 ** 2.5) / 0.25) < 1e-9 and sgp.price(4, 0.25, T, [0.3, 0.4, 0.6, 0.7]) == sgp.price(4, 0.25, T), "with no long-shot cut in use the price is the count formula, whatever the legs are")
T2 = dict(T, dog=0.06)
check(abs(sgp.price(4, 0.25, T2, [0.3, 0.4, 0.6, 0.7]) - sgp.price(4, 0.25, T) * math.exp(-0.12)) < 1e-9 and sgp.price(4, 0.25, T2, [0.5, 0.6, 0.6, 0.7]) == sgp.price(4, 0.25, T) and sgp.dogs([0.44, 0.45, None, 0.2], T) == 2,
      "once it is in use, each leg FanDuel prices under 45% takes its cut and the others do not")
check(sgp.spread(3, T) is None and sgp.spread(4, T) is None and sgp.spread(5, T) is not None and abs(sgp.spread(8, T)[0] - math.exp(-0.45)) < 1e-9 and abs(sgp.spread(8, T)[1] - math.exp(0.45)) < 1e-9 and sgp.spread(8, {"spread": {}}) is None,
      "a range is given only where the estimate has missed by 20% or more four times in five: not at 2-4 legs, yes at 5-6 and 7+ on these numbers")
# site quotes: what is kept
import sgp_discount as SD
d = tempfile.mkdtemp(); real = SD.HERE
try:
    SD.HERE = d
    leg = lambda pl, o, g="AAA-BBB", m="Receiving Yards", ln=50: {"pl": pl, "m": m, "ln": ln, "o": o, "tm": g.split("-")[0], "g": g, "c": "WR_RECYDS", "p": 0.9}
    good = {"id": 1, "at": "2026-11-25T10:00:00Z", "week": 12, "fanduel": 240, "est": 255, "src": "typed", "legs": [leg("A", -150), leg("B", -150)]}        # multiplied +178... a same-game price near it
    rows = [good, dict(good, id=2, at="2026-11-25T11:00:00Z", fanduel=230),                                   # the same slip typed again: the newest stands
            dict(good, id=3, legs=[leg("A", -150), leg("B", -150, g="CCC-DDD")]),                               # no two legs in one game
            dict(good, id=4, fanduel=178),                                                                      # just the legs multiplied
            dict(good, id=5, fanduel=90000),                                                                    # not a possible price for this slip
            dict(good, id=6, legs=[leg("A", -150)]), dict(good, id=7, legs=[leg("A", 50), leg("B", -150)]), dict(good, id=8, week=99), {"id": 9}, "x",
            dict(good, id=10, legs=[leg("C", -120), leg("D", 110), leg("E", -200)], fanduel=600)]
    os.makedirs(os.path.join(d, "in")); json.dump({"quotes": rows}, open(os.path.join(d, "in", "fd_quotes.json"), "w"))
    out, bad = SD.site_quotes(os.path.join(d, "in"))
    check(sorted(q["id"] for q in out) == [2, 10] and bad == 8 and all("p" not in l for q in out for l in q["legs"]) and out[0]["title"].startswith("Site quote 2026-11-25"),
          f"of eleven rows from the site two are kept: a real same-game price (its newest typing) and a three-leg one; a typo, the legs multiplied, one game per leg, a bad price or week are dropped ({[q['id'] for q in out]}, {bad} dropped)")
    os.makedirs(os.path.join(d, "none")); out2, _ = SD.site_quotes(os.path.join(d, "none"))
    check([q["id"] for q in out2] == [q["id"] for q in out] and os.path.exists(os.path.join(d, "sgp_quotes_site.json")), "kept quotes are saved with the research files, so a run without the mirror still has them")
finally:
    SD.HERE = real
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
