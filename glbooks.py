#!/usr/bin/env python3
"""glbooks.py - DraftKings / Hard Rock prices and selection ids for GAME-LINE legs (moneyline, spread, total), from the
'gl|<Away @ Home>|<Market>|<Side>|<Point>' rows FanDuelOdds.gs (v2026-10-21) writes to 'AUTO - Book Odds'.

For every game-line leg (l["gl"] = {"k": "M"/"T", "side": team abbr or OVER/UNDER}, l["m"], l["ln"], l["g"] = "A-B"):
  - the book posts the same number (spread -6.5 / total 44.5 / moneyline)  -> l["bks"][book] = {"o", "s"}   (exact, like a prop rung)
  - the book hangs a different number within MAX_GAP                       -> l["ba"][book] = {"ln", "o", "s", "p", "bk", "e"}
    where p is the model's chance at the book's number: the leg's own shown chance moved by the ratio of the plain model normal
    (gamelines.py margin / total normals, same SD) at the two numbers, (the leg's chance is already anchored
    halfway to the market in gamelines.py, so no second blend). Moneylines never substitute (there is no number to move).
  - otherwise nothing, and the slip says the book does not price that leg.

    attach(legs, bookodds_rows, mt)   mt = {gid: (model margin a-b, model total)} with gid "A-B" and a = the first team
    returns (exact, alternatives) counts.
"""
import gamelines as GLM
BOOKS = {"draftkings": "dk", "hardrockbet": "hr"}
MAX_GAP = {"Spread": 3.5, "Total": 4.5, "Moneyline": 0}

def _num(x):
    try: return float(x)
    except Exception: return None

def _dec(o): return 1 + o / 100 if o > 0 else 1 + 100 / -o

def index(rows):
    """Book Odds rows -> {(book, gid, market, side abbr/OVER/UNDER): [(point, odds, sid)]}. gid is 'A-B' in the away-home order of the row's Game."""
    idx = {}
    for r in rows:
        if len(r) < 9 or not str(r[1]).startswith("gl|"): continue
        parts = str(r[1]).split("|")
        if len(parts) != 5: continue
        _, game, market, side, pt = parts
        away, _, home = game.partition(" @ "); ga, gh = GLM.TEAM_FULL.get(away.strip()), GLM.TEAM_FULL.get(home.strip())
        if not (ga and gh): continue
        book = BOOKS.get(r[0]);  o = _num(r[5]); p = _num(pt)
        if not book or o is None or p is None: continue
        s_ = GLM.TEAM_FULL.get(side.strip(), side.strip().upper())
        idx.setdefault((book, frozenset([ga, gh]), market, s_), []).append((p, int(o), str(r[8])))
    return idx

def _ev(leg, point, a):
    """Threshold interval for the leg's side at `point`: spread covers if side's margin + point > 0; total over/under."""
    side = leg["gl"]["side"]; m = leg["m"]
    if m == "Total": return (point, None) if side == "OVER" else (None, point)
    if m == "Moneyline": return (0, None) if side == a else (None, 0)
    return (-point, None) if side == a else (None, point)

def attach(legs, rows, mt):
    idx = index(rows); n_ex = n_alt = 0
    for l in legs:
        if not l.get("gl") or not l.get("g"): continue
        a, _, b = l["g"].partition("-"); gk = frozenset([a, b]); m = l["m"]; ln = float(l.get("ln") or 0)
        for book in ("dk", "hr"):
            rungs = idx.get((book, gk, m, l["gl"]["side"]))
            if not rungs: continue
            exact = [r for r in rungs if abs(r[0] - ln) < 1e-9]
            if exact:
                l.setdefault("bks", {})[book] = {"o": exact[0][1], "s": exact[0][2]}; n_ex += 1; continue
            if m == "Moneyline" or MAX_GAP.get(m, 0) <= 0: continue
            pt, o, sid = sorted(rungs, key=lambda r: (abs(r[0] - ln), r[0]))[0]
            if abs(pt - ln) > MAX_GAP[m]: continue
            mu_t = mt.get(l["g"])
            if not mu_t: continue
            marg, tot = mu_t
            mu, sd = (tot, GLM.SD_TOTAL) if m == "Total" else (marg, GLM.SD_MARGIN)
            lo0, hi0 = _ev(l, ln, a); lo1, hi1 = _ev(l, pt, a)
            pm0 = GLM._pint(lo0, hi0, mu, sd); pm1 = GLM._pint(lo1, hi1, mu, sd)
            p0 = float(l.get("p") or 0)
            raw = max(0.01, min(0.99, p0 * pm1 / pm0)) if pm0 > 1e-6 and p0 > 0 else pm1
            bk = round(1 / _dec(o), 4); p = round(raw, 4)   # game lines are already anchored to the market in gamelines.py; no second blend
            l.setdefault("ba", {})[book] = {"ln": pt, "o": o, "s": sid, "p": p, "bk": bk, "e": round(p - bk, 4), "raw": round(raw, 4)}; n_alt += 1
    return n_ex, n_alt
