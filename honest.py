"""The honest chance of a leg (owner 11/15: "Yes build all of that" - FanDuel's price as the chance, the model as a small nudge).

Why: on 6,519 graded FanDuel legs (Weeks 6-9) the model's own chance was a worse forecast than the price on every slice, and worst where
it was most confident - legs it had at 70-80% hit 65%, 80-90% hit 56%. What legs at a given price in a given market ACTUALLY hit
("the band rate") was the best single forecast and stayed calibrated from 25% to 68% when each week was scored on the other weeks.

    chance = band rate                                   what graded legs at this price in this market have hit
             - 0.25 x (band - model)   if the model is lower      (a full veto made it too pessimistic: said 64%, hit 67%)
             + 0.20 x (model - band)   if the model is higher AND the leg is priced longer than -200
                                       (the model's likes were worthless on floor legs: -12.6% a leg; about break-even to +14% on
                                        mid, even and plus-money legs it had 8+ points over the price)

Band rate = FanDuel's no-vig chance (implied / 1.045) x hits-per-expected-hit in the leg's price band: the band's ratio over all markets
(shrunk toward 1.0 with 40 phantom legs), then the market's own ratio in that band shrunk toward it with 40 more. Capped at 68%. Markets with no graded legs (unders, game
lines, new markets) use the no-vig chance itself. The table rebuilds from in/legsnaps.json on every run, so it follows the grades.

    python3 honest.py            leave-one-week-out check on the graded legs (prints forecast error against the model and the price)
"""
import json, os

VIG = 1.045; K = 40; MIN_MARKET = 120; VETO = 0.25; NUDGE = 0.20; FLOOR_ODDS = -200; CAP = 0.68
BANDS = [(-99999, -250), (-249, -180), (-179, -130), (-129, 100), (101, 200), (201, 400), (401, 99999)]

def implied(o):
    o = float(o); return (-o / (-o + 100.0)) if o < 0 else 100.0 / (o + 100.0)

def _band(o): return next((i for i, (lo, hi) in enumerate(BANDS) if lo <= o <= hi), len(BANDS) - 1)

def _num(x):
    try: return float(str(x).replace("%", "").replace("+", ""))
    except Exception: return None

def graded(IN="in"):
    """[(week, market, odds, hit, model chance or None)] from the sheet's leg snapshots: latest snapshot of each leg, HIT or MISS only."""
    try: v = json.load(open(os.path.join(IN, "legsnaps.json")))["values"]
    except Exception: return []
    H = {c: i for i, c in enumerate(v[0])}; out = []
    for r in v[1:]:
        r = list(r) + [""] * (len(v[0]) - len(r))
        if r[H["Latest Snapshot"]] != "TRUE" or r[H["Result"]] not in ("HIT", "MISS"): continue
        o = _num(r[H["FanDuel odds"]]); w = _num(r[0])
        if not o or w is None: continue
        mp = _num(r[H["Model % (hist-adj)"]]) if "Model % (hist-adj)" in H else None
        out.append((int(w), r[H["Market"]], o, r[H["Result"]] == "HIT", (mp / 100 if mp is not None and mp > 1 else mp)))
    return out

class Honest:
    def __init__(self, rows):
        self.n = len(rows); self.pool = {}; self.mk = {}
        for w, m, o, hit, _ in rows:
            f = implied(o) / VIG; b = _band(o)
            for d, k in ((self.pool, b), (self.mk, (m, b))):
                x = d.setdefault(k, [0, 0, 0.0]); x[0] += 1; x[1] += hit; x[2] += f

    def ratio(self, market, odds):
        """(hits per expected hit in the band, graded legs behind it, 'market' | 'all' | 'none'). The band's own ratio is shrunk toward 1.0
        with K phantom legs; the market's ratio in that band is shrunk toward the band's with K more, so a thin market-band (rushing
        yards at -250 or shorter: under 120 legs) leans on its own record without being ruled by it."""
        if market is None or str(market).startswith("Under") or market in ("Total", "Spread", "Moneyline") or not any(k[0] == market for k in self.mk): return 1.0, 0, "none"
        b = _band(float(odds)); n, h, f = self.pool.get(b, (0, 0, 0.0))
        if not n: return 1.0, 0, "none"
        avg = f / n; rp = (h + K * avg) / (f + K * avg)
        nm, hm, fm = self.mk.get((market, b), (0, 0, 0.0))
        if not nm: return rp, n, "all"
        am = fm / nm
        return (hm + K * am * rp) / (fm + K * am), nm, ("market" if nm >= MIN_MARKET else "all")

    def band(self, market, odds):
        """What legs at this price in this market have actually hit (None without a price). Graded markets top out at CAP: no price band
        in any graded market has hit more than about two times in three (legs this formula put at 70%+ hit 63%)."""
        if odds is None: return None
        r, _, src = self.ratio(market, odds); x = implied(odds) / VIG * r
        return max(0.01, min(0.97 if src == "none" else CAP, x))

    def chance(self, market, odds, model=None):
        b = self.band(market, odds)
        if b is None: return model
        if model is None: return b
        if model < b: return b - VETO * (b - model)
        if float(odds) > FLOOR_ODDS: return min(0.97 if self.ratio(market, odds)[2] == "none" else CAP, b + NUDGE * (model - b))
        return b

    def work(self, market, odds, model=None, own=None):
        """The plain numbers behind a leg, for 'show the work': own = (times he cleared it, games)."""
        _, n, src = self.ratio(market, odds)
        return {"fd": implied(odds), "band": self.band(market, odds), "n": n, "src": src, "model": model, "hp": self.chance(market, odds, model),
                "own": (list(own) if own and own[1] else None)}

def load(IN="in"):
    return Honest(graded(IN))

if __name__ == "__main__":
    rows = [r for r in graded(os.path.join(os.path.dirname(os.path.abspath(__file__)), "in")) if r[4] is not None]
    weeks = sorted({r[0] for r in rows}); pred = []
    for w in weeks:
        H = Honest([r for r in rows if r[0] != w])          # each week is scored with a table built from the other weeks
        pred += [(r, implied(r[2]) / VIG, H.band(r[1], r[2]), H.chance(r[1], r[2], r[4])) for r in rows if r[0] == w]
    br = lambda f: sum((f(x) - x[0][3]) ** 2 for x in pred) / len(pred)
    print(f"graded legs {len(pred)} (weeks {weeks}); forecast error, lower is better:")
    print(f"  model {br(lambda x: x[0][4]):.4f} | FanDuel no-vig {br(lambda x: x[1]):.4f} | band rate {br(lambda x: x[2]):.4f} | honest chance {br(lambda x: x[3]):.4f}")
    for lo, hi in ((0, .3), (.3, .4), (.4, .5), (.5, .6), (.6, .7), (.7, 1.01)):
        x = [p for p in pred if lo <= p[3] < hi]
        if x: print(f"  honest chance said {sum(p[3] for p in x) / len(x):.1%} -> hit {sum(p[0][3] for p in x) / len(x):.1%}  ({len(x)} legs); the model said {sum(p[0][4] for p in x) / len(x):.1%} on the same legs")
    top = [p for p in pred if p[0][4] >= 0.70]
    print(f"  legs the model had at 70%+ ({len(top)}): model said {sum(p[0][4] for p in top) / len(top):.1%}, honest chance {sum(p[3] for p in top) / len(top):.1%}, hit {sum(p[0][3] for p in top) / len(top):.1%}")
    H = load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "in"))
    for m, o, mp in (("Receptions", -260, 0.736), ("Receiving Yards", -110, 0.61), ("Rushing Yards", -300, 0.80), ("Anytime TD", 150, 0.45), ("Under Receptions", -114, 0.60), ("Total", -110, 0.52)):
        print(f"  example {m} {o:+d}, model {mp:.0%}: band {H.band(m, o):.1%}, honest {H.chance(m, o, mp):.1%}, source {H.ratio(m, o)[2]} ({H.ratio(m, o)[1]} legs)")
