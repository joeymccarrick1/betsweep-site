#!/usr/bin/env python3
"""hrswap.py - price a slip leg at the nearest DraftKings / Hard Rock line when that book does not post the FanDuel rung we show.

Why: Hard Rock's alternate ladders are sparse (e.g. receiving yards 40 / 50 / main / 65 / 80 / 100 where FanDuel and DraftKings run
every 10). The betslips send a leg to a book only when that book prices the exact rung, so most Hard Rock prop legs went grey.
This gives each such leg an `hra` (Hard Rock alternative): the closest Hard Rock rung, Hard Rock's price and selection id, and
the model's probability AT THAT LINE - read off the player's own ladder of raw model probabilities (probit-linear fit of the
rungs, interpolated or gently extrapolated), then blended toward Hard Rock's implied price exactly as calib.py does for the shown
Model % of every other leg. The page offers it as an explicit "use Hard Rock's line" swap; nothing is swapped silently.

Limits: no alternative for TD / First TD / game lines (no ladder), when the nearest rung is farther than MAX_GAP[market] from ours,
or when there is no ladder and no projection to price from.

    attach(slip_legs, ladders, bookodds)
      slip_legs: dicts with pl, m, ln, bks (as built by build_builder.py / build_boards.py)
      ladders:   {(normname(player), market): [(line, raw_model_p), ...]}
      bookodds:  {key 'normname|market|line': {book: {'o': odds, 's': selection id}}} - the AUTO - Book Odds join
    returns the number of legs given an hra.
"""
import re
from statistics import NormalDist
import calib as CALIB
_Z = NormalDist()
MAX_GAP = {"Passing Yards": 50, "Rushing Yards": 30, "Receiving Yards": 30, "Rush + Rec Yards": 30, "Receptions": 2, "Longest Reception": 15}   # owner 10/21: grey as little as possible - the note on the slip discloses every substitution
SIG = {"Passing Yards": 0.30, "Rushing Yards": 0.50, "Receiving Yards": 0.60, "Rush + Rec Yards": 0.45, "Receptions": 0.45, "Longest Reception": 0.50}   # fallback spread as a share of the projection when a ladder has one usable rung

def normname(x):
    x = re.sub(r"\.", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()

def _dec(o): return 1 + o / 100 if o > 0 else 1 + 100 / -o

def fit(ladder):
    """Probit-linear fit z = a + b*line over the usable rungs; returns (a, b, lo, hi, spacing) or None."""
    pts = sorted({(float(ln), float(p)) for ln, p in ladder if p is not None and 0.02 < p < 0.98})
    if len(pts) < 2: return None
    xs = [x for x, _ in pts]; zs = [_Z.inv_cdf(1 - p) for _, p in pts]
    n = len(xs); mx = sum(xs) / n; mz = sum(zs) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0: return None
    b = sum((x - mx) * (z - mz) for x, z in zip(xs, zs)) / sxx
    if b <= 0: return None   # probability must fall as the line rises
    a = mz - b * mx
    sp = min(xs[i + 1] - xs[i] for i in range(n - 1)) if n > 1 else 0
    return a, b, xs[0], xs[-1], sp

def p_at(f, line, ladder=None):
    """Model probability at `line`: inside the ladder, interpolate z between the two neighbouring rungs (exact at every rung the model
    priced, so the swap never contradicts the ladder); outside it, extend the probit-linear fit."""
    a, b, lo, hi, sp = f
    pts = sorted({(float(ln), float(p)) for ln, p in (ladder or []) if p is not None and 0.02 < p < 0.98})
    for (x0, p0), (x1, p1) in zip(pts, pts[1:]):
        if x0 <= line <= x1 and x1 > x0:
            z0, z1 = _Z.inv_cdf(1 - p0), _Z.inv_cdf(1 - p1); z = z0 + (z1 - z0) * (line - x0) / (x1 - x0)
            return max(0.01, min(0.99, 1 - _Z.cdf(z)))
    return max(0.01, min(0.99, 1 - _Z.cdf(a + b * line)))

def hr_rungs(bookodds, name, market):
    out = []
    pre = f"{name}|{market}|"
    for k, v in bookodds.items():
        if k.startswith(pre) and "hardrockbet" in v and v["hardrockbet"].get("o") is not None:
            try: out.append((float(k[len(pre):]), v["hardrockbet"]))
            except ValueError: pass
    return out

BOOKS = {"draftkings": "dk", "hardrockbet": "hr"}

def fit_one(ladder, proj, market):
    """One usable rung (or none) - a normal around the projection; spread from the rung when it is informative, else SIG x projection."""
    if proj is None or proj <= 0: return None
    pts = [(float(ln), float(p)) for ln, p in ladder if p is not None and 0.02 < p < 0.98]
    sd = None
    if pts:
        ln, p = pts[0]; z = _Z.inv_cdf(1 - p)
        if abs(z) > 0.15 and (ln - proj) / z > 0: sd = (ln - proj) / z
    if sd is None: sd = SIG.get(market, 0.5) * max(proj, 1.0)
    return (-proj / sd, 1 / sd, min([x for x, _ in pts] + [proj]), max([x for x, _ in pts] + [proj]), 0)

def attach(slip_legs, ladders, bookodds):
    """Gives each prop leg l["ba"] = {book: nearest-line alternative} for every book (dk, hr) that does not price the leg's own rung.
    The nearest rung within MAX_GAP wins; the model's probability at that line comes from the player's ladder (probit interpolation,
    extrapolated with the probit fit past the ends) or, with one rung, from a normal around the projection. Returns the count attached."""
    n = 0
    idx = {}
    for k, v in bookodds.items():
        parts = k.rsplit("|", 2)
        if len(parts) != 3: continue
        for book, short in BOOKS.items():
            if book in v and v[book].get("o") is not None:
                try: idx.setdefault((parts[0], parts[1], short), []).append((float(parts[2]), v[book]))
                except ValueError: pass
    for l in slip_legs:
        m = l.get("m")
        if m not in MAX_GAP: continue
        name = normname(l["pl"]); f = None; ln = float(l["ln"] or 0); rp = l.get("raw_p"); lad = ladders.get((name, m)) or []
        for short in ("dk", "hr"):
            if (l.get("bks") or {}).get(short): continue
            rungs = idx.get((name, m, short))
            if not rungs: continue
            if f is None:
                f = fit(lad) or fit_one(lad, l.get("proj"), m)
                if not f: break
            hl, hv = sorted(rungs, key=lambda r: (abs(r[0] - ln), r[0]))[0]
            if abs(hl - ln) > MAX_GAP[m] or abs(hl - ln) < 1e-9: continue
            raw = p_at(f, hl, lad)
            if rp is not None: raw = min(raw, rp) if hl > ln else max(raw, rp)   # a higher line can never be likelier than ours, nor a lower one less likely
            bk = round(1 / _dec(hv["o"]), 4); p = round(CALIB.shown(raw, bk, m), 4)
            l.setdefault("ba", {})[short] = {"ln": int(hl) if float(hl).is_integer() else hl, "o": int(hv["o"]), "s": hv["s"], "p": p, "bk": bk, "e": round(p - bk, 4), "raw": round(raw, 4)}
            n += 1
    return n
