"""Edge map (owner 11/6 "set us apart"): where the model's edges have actually paid. From graded frozen legs ('V2 - FanDuel Leg Snapshots',
Latest Snapshot TRUE, weeks before this one) - a leg is a model edge when the raw model % is 5+ pts above FanDuel's implied %. For each market x
price band: edge legs, hits, units at the real price. A leg's zone = its market x band ROI shrunk toward the band's ROI (K = 30 legs), which is
itself shrunk toward 0: green ("proven") at +4% or better, red ("losing") at -4% or worse. Weeks 6-8: edges at +120..+399 paid (+11% / +53%),
-200 or shorter lost (-16%), rushing yards lost at every price. Recomputed every build, so the zones move as weeks are graded.
Usage: import edgemap; E = edgemap.load(IN, WEEK); z = E.zone(market, odds, raw_p) -> None | {"z": "g"|"r"|"n", "roi", "n", "band", "txt"}
"""
import json, os
BANDS = [(-100000, -200, "-200 or shorter"), (-199, -120, "-199 to -120"), (-119, 119, "-119 to +119"), (120, 199, "+120 to +199"), (200, 399, "+200 to +399"), (400, 100000, "+400 and longer")]
EDGE, K, ZONE, MIN_CELL, MIN_BAND = 0.05, 30, 0.04, 15, 30
def imp(o): return 100 / (o + 100) if o > 0 else -o / (-o + 100)
def pay(o): return o / 100 if o > 0 else 100 / -o
def band(o):
    for lo, hi, lab in BANDS:
        if lo <= o <= hi: return lab
    return None
class _E:
    def __init__(self, IN, WEEK):
        self.cell = {}; self.W = int(WEEK)
        try: v = json.load(open(os.path.join(IN, "legsnaps.json")))["values"]
        except Exception: return
        H = {c: i for i, c in enumerate(v[0])}
        for r in v[1:]:
            r = r + [""] * (len(v[0]) - len(r))
            if str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS"): continue
            try: o = float(r[H["FanDuel odds"]]); rp = float(r[H["Raw model %"]]); w = int(float(r[0]))
            except Exception: continue
            if w >= self.W or rp - imp(o) < EDGE: continue
            b = band(o); y = r[H["Result"]] == "HIT"; u = pay(o) if y else -1.0
            for key in ((r[H["Market"]], b), ("ALL", b)):
                c = self.cell.setdefault(key, [0, 0, 0.0]); c[0] += 1; c[1] += int(y); c[2] += u
    def zone(self, market, odds, raw_p):
        if odds is None or raw_p is None or str(market).startswith("Under ") or raw_p - imp(odds) < EDGE: return None
        b = band(odds); cb = self.cell.get(("ALL", b)); cm = self.cell.get((market, b))
        if not cb: return None
        rb = cb[2] / (cb[0] + K)                                   # band ROI shrunk toward 0
        n_m, u_m = (cm[0], cm[2]) if cm else (0, 0.0)
        roi = (u_m + K * rb) / (n_m + K)                          # market x band shrunk toward the band
        z = ("g" if roi >= ZONE else "r" if roi <= -ZONE else "n") if cb[0] >= MIN_BAND else "n"   # too few graded edges at this price to call it
        n_show, roi_raw = (cm[0], cm[2] / cm[0]) if cm and cm[0] >= MIN_CELL else (cb[0], cb[2] / cb[0])
        scope = market if cm and cm[0] >= MIN_CELL else "all markets"
        txt = (f"Model edges in {scope} at {b}: {roi_raw*100:+.0f}% ROI over {n_show} graded legs" + (" - a proven zone" if z == "g" else " - a losing zone, skip" if z == "r" else ""))
        return {"z": z, "roi": round(roi, 3), "n": n_show, "band": b, "txt": txt}
def load(IN, WEEK): return _E(IN, WEEK)
