"""Returning starters with no 2026 game log (CeeDee Lamb / Christian Watson type).

The projection tabs only know players with a 2026 game log, so a starter coming back from a long absence has no model row and
the builder shows nothing for him even though FanDuel prices him. Owner's rule (2026-10-19): project him as LAST YEAR'S SHARE x
THIS TEAM'S CURRENT VOLUME, flagged and treated as a short-sample player.

Prior: gen/prior2025.json (nflverse 2025 weekly stats, REG; players with 6+ games and 40+ targets or 60+ carries): target share
of team targets, carry share, yards per target, catch rate, yards per carry, TDs per touch, position means for shrinkage.
Team volume: this team's 2026 targets/g and carries/g from the sheet's game log (sum of its players, by week).
Discount for the first games back: receiving x0.75, rushing x0.65. Evidence (returning_study.py, scratch): 2024 shares x 2025 volume on
69 players who had missed 2+ team games (weeks <= 16) - raw MAE 26.7 rec yds / bias -12; x0.70 MAE 22.2 / bias 0; the 2025-share x
2026-volume check on the 12 cases so far ran +2 at x0.9, so 0.75 splits the two samples. RB rushing ran -22 yds raw (n=14) -> 0.65.
Pricing: receiving / rushing yards normal with the builder's ladder-implied spread for the position (fallback CV), receptions Poisson,
anytime TD = 1 - exp(-(TDs per touch x projected touches)). Every leg carries a 'Returning' watch flag and the sample note; Top Plays
and Floor legs skip them, the builder shows them with the flag.
"""
import json, os, math, re
from statistics import NormalDist, median
N = NormalDist()
REC_DISCOUNT, RUSH_DISCOUNT = 0.75, 0.65

def _num(x):
    try: return float(str(x).replace(",", ""))
    except Exception: return None
def normname(s): return re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", str(s).strip().replace(".", "").lower()).strip()

def load_prior(HERE):
    try: return json.load(open(os.path.join(HERE, "prior2025.json")))
    except Exception: return {"players": {}, "pos_means": {}}

def team_volume(IN, week):
    """{team: {"tgt": targets/g, "car": carries/g, "g": games}} from the sheet's game log (weeks before `week`)."""
    out = {}
    try: v = json.load(open(os.path.join(IN, "gamelog.json")))["values"]
    except Exception: return out
    H = {c: i for i, c in enumerate(v[0])}
    by = {}
    for r in v[1:]:
        try: w = int(float(r[0]))
        except Exception: continue
        if w >= week or len(r) <= H["Rec Yds"]: continue
        k = (r[H["Team"]], w); d = by.setdefault(k, {"tgt": 0.0, "car": 0.0})
        d["tgt"] += _num(r[H["Targets"]]) or 0; d["car"] += _num(r[H["Rush Att"]]) or 0
    for (t, w), d in by.items():
        o = out.setdefault(t, {"tgt": 0.0, "car": 0.0, "g": 0}); o["tgt"] += d["tgt"]; o["car"] += d["car"]; o["g"] += 1
    for t, o in out.items():
        if o["g"]: o["tgt"] /= o["g"]; o["car"] /= o["g"]
    return out

def project(name, team, pos, prior, vol):
    """-> {tgt, rec, recy, car, rushy, lam_td, note} or None"""
    p = prior["players"].get(name) or next((v for k, v in prior["players"].items() if normname(k) == normname(name)), None)
    tv = vol.get(team)
    if not p or not tv or tv["g"] < 2: return None
    PM = prior["pos_means"]; pos = pos or p["pos"]
    n_t, n_c = p["tgt"], p["car"]
    ypt = ((p["ypt"] or 0) * n_t + PM["ypt"].get(pos, 7.0) * 40) / (n_t + 40) if n_t else PM["ypt"].get(pos, 7.0)
    cr = ((p["cr"] or 0) * n_t + PM["cr"].get(pos, 0.65) * 40) / (n_t + 40) if n_t else PM["cr"].get(pos, 0.65)
    ypc = ((p["ypc"] or 0) * n_c + PM["ypc"].get(pos, 4.3) * 60) / (n_c + 60) if n_c else PM["ypc"].get(pos, 4.3)
    tg = p["ts"] * tv["tgt"] * REC_DISCOUNT; ca = p["cs"] * tv["car"] * RUSH_DISCOUNT
    lam = p["tdpt"] * (tg + ca)
    note = (f"Returning starter: no 2026 game log, so this is last year's share x {team}'s volume this season - {p['ts']*100:.0f}% of targets "
            f"x {tv['tgt']:.0f} team targets/g" + (f", {p['cs']*100:.0f}% of carries x {tv['car']:.0f} carries/g" if p["cs"] >= 0.05 else "")
            + f", discounted x{REC_DISCOUNT:g} receiving" + (f" / x{RUSH_DISCOUNT:g} rushing" if p["cs"] >= 0.05 else "")
            + f" for the first games back ({p['g']} games, {int(n_t)} targets in 2025" + (f", then with {'/'.join(p['teams'])}" if team not in p["teams"] else "") + "). Treat as a short-sample player.")
    return {"tgt": tg, "rec": tg * cr, "recy": tg * ypt, "car": ca, "rushy": ca * ypc, "lam_td": lam, "note": note, "prior": p, "team_change": team not in p["teams"]}

def ladder_cv(LEGS):
    """Median spread / projection by market from the builder's own ladders (probit fit per player), fallback CVs."""
    out = {"Receiving Yards": 0.62, "Rushing Yards": 0.5, "Passing Yards": 0.3}
    by = {}
    for l in LEGS:
        if l["m"] not in out or l.get("alt") or not l.get("proj") or not (0.08 < l["p"] < 0.92): continue
        z = N.inv_cdf(1 - l["p"])
        if abs(z) < 0.15: continue
        s = (float(l["ln"]) - float(l["proj"])) / z
        if s > 0: by.setdefault(l["m"], []).append(s / float(l["proj"]))
    for m, v in by.items():
        if len(v) >= 20: out[m] = median(v)
    return out

def prob(pr, market, line, cv):
    """P(market >= line) under the returning projection."""
    m = market
    if m == "Anytime TD": return min(0.95, max(0.02, 1 - math.exp(-pr["lam_td"]))) if pr["lam_td"] > 0 else None
    if m == "Receptions":
        lam = pr["rec"]
        if lam <= 0: return None
        k = int(math.ceil(line)); cdf = sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k))
        return min(0.97, max(0.03, 1 - cdf))
    mu = {"Receiving Yards": pr["recy"], "Rushing Yards": pr["rushy"], "Rush + Rec Yards": pr["recy"] + pr["rushy"]}.get(m)
    if mu is None or mu <= 0: return None
    sd = (cv.get(m) or cv.get("Receiving Yards")) * mu
    if m == "Rush + Rec Yards": sd = ((cv["Receiving Yards"] * pr["recy"]) ** 2 + (cv["Rushing Yards"] * pr["rushy"]) ** 2) ** 0.5
    return min(0.97, max(0.03, 1 - N.cdf((line - 0.5 - mu) / max(sd, 1.0))))
