"""scenario.py - per-ending chances for the Builder's scenario explorer (owner 11/6: "pick a game ending -> legs and slip reprice").

Each leg gets l["sc"] = its chance under each of its game's four endings, in the game's own frame [a by 10+, close & low, shootout,
b by 10+] (a = the game's first team, as in g.probs). Player legs use the boards' tested script tables: probit.json for yardage and
receptions (P' = Phi(alpha + beta * Phi^-1(P)); longest reception rides receiving yards) and the AUTO - Script Multipliers TD rows
(anytime 1 - (1 - P)^m; 2+ / 3+ by scaling the Poisson mean; first TD x m). Role = rank on his team at his position by projected fantasy
points (WR4 reads as WR3, RB3 as RB2, TE2 / QB2 as TE1 / QB1). One probit shift per leg then makes the four endings mix back to the leg's
own shown chance with the game's script odds, so "no scenario" is exactly the page. Game lines come from gamelines.by_script (the
builder passes game_legs' own per-script chances; gl_sc() rebuilds them for a hotfix of an existing build).
"""
import json, math, os
from statistics import NormalDist

_N = NormalDist()
CAP = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}
STAT = {"Passing Yards": "passing_yards", "Rushing Yards": "rushing_yards", "Receiving Yards": "receiving_yards", "Receptions": "receptions", "Longest Reception": "receiving_yards"}
IDX = {"LEAD": 0, "CLOSE_LOW": 1, "SHOOTOUT": 2, "TRAIL": 3}
TDS = ("Anytime TD", "2+ TD", "3+ TD", "First TD")


def _num(x):
    try: return float(str(x).replace("%", "").replace(",", "").strip())
    except Exception: return None


def _vals(IN, n): return json.load(open(os.path.join(IN, n)))["values"]


def _pois_ge(k, lam): return 1.0 - sum(math.exp(-lam) * lam ** j / math.factorial(j) for j in range(k))


def _pois_lam(k, p):
    lo, hi = 1e-4, 20.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if _pois_ge(k, mid) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def tables(IN, here):
    prb = {r[0]: r[3:11] for r in json.load(open(os.path.join(here, "probit.json")))}
    mul = {r[0]: [_num(x) for x in r[3:7]] for r in _vals(IN, "mult.json")[1:] if r and "|" in str(r[0])}
    role = {}
    for f, pos in (("proj_qb.json", "QB"), ("proj_rb.json", "RB"), ("proj_wr.json", "WR"), ("proj_te.json", "TE")):
        v = _vals(IN, f); ix = {c: i for i, c in enumerate(v[0])}; bt = {}
        for r in v[1:]:
            if not r or not r[0]: continue
            tm = r[ix["Team"]] if "Team" in ix and len(r) > ix["Team"] else ""
            fp = _num(r[ix["Proj Fantasy Pts"]]) if "Proj Fantasy Pts" in ix and len(r) > ix["Proj Fantasy Pts"] else None
            bt.setdefault(tm, []).append((fp or 0, r[0]))
        for xs in bt.values():
            for k, (_, nm) in enumerate(sorted(xs, key=lambda x: -x[0]), 1): role.setdefault(nm, (pos, k))
    return prb, mul, role


def _mixback(ps, w, p0):
    zs = [_N.inv_cdf(min(0.995, max(0.005, x))) for x in ps]
    lo, hi = -3.0, 3.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if sum(w[k] * _N.cdf(zs[k] + mid) for k in range(4)) < p0: lo = mid
        else: hi = mid
    return [_N.cdf(z + (lo + hi) / 2) for z in zs]


def player_sc(l, G, prb, mul, role):
    rl = role.get(l.get("pl"))
    if not rl or l.get("p") is None: return None
    rk = f"{rl[0]}{min(rl[1], CAP[rl[0]])}"
    frame = ["LEAD", "CLOSE_LOW", "SHOOTOUT", "TRAIL"] if l.get("tm") == G["a"] else ["TRAIL", "CLOSE_LOW", "SHOOTOUT", "LEAD"]
    m = str(l.get("m", "")); under = m.startswith("Under "); mk = m[6:] if under else m
    p0 = min(0.99, max(0.01, (1 - l["p"]) if under else l["p"]))   # the over side
    if mk in STAT:
        ab = prb.get(f"{rk}|{STAT[mk]}")
        if not ab: return None
        ps = [_N.cdf(ab[IDX[sc] * 2] + ab[IDX[sc] * 2 + 1] * _N.inv_cdf(p0)) for sc in frame]
    elif mk in TDS:
        mu = mul.get(f"{rk}|td")
        if not mu: return None
        ms = [mu[IDX[sc]] or 1 for sc in frame]
        if mk == "Anytime TD": ps = [1 - (1 - p0) ** x for x in ms]
        elif mk == "First TD": ps = [min(0.95, p0 * x) for x in ms]
        else:
            kk = 2 if mk == "2+ TD" else 3; lam = _pois_lam(kk, p0); ps = [_pois_ge(kk, lam * x) for x in ms]
    else: return None
    w = [max(0.0, x or 0) for x in G["probs"]]; sw = sum(w)
    if sw <= 0: return None
    ps = _mixback(ps, [x / sw for x in w], p0)
    return [round((1 - x) if under else x, 3) for x in ps]


def gl_sc(l, G):
    """Per-ending chances for an already-built game-line leg (same model as gamelines.game_legs, scaled to the leg's shown p)."""
    import gamelines as GLM
    side, ln, k = (l.get("gl") or {}).get("side"), l.get("ln") or 0, (l.get("gl") or {}).get("k")
    a = G["a"]; marg = (G.get("pa") or 0) - (G.get("pb") or 0); tot = (G.get("pa") or 0) + (G.get("pb") or 0)
    if l.get("m") == "Moneyline": ev = (0, None) if side == a else (None, 0)
    elif l.get("m") == "Spread": ev = (-ln, None) if side == a else (None, ln)
    elif l.get("m") == "Total": ev = (ln, None) if side == "OVER" else (None, ln)
    else: return None
    psm = GLM.by_script("M" if l.get("m") != "Total" else "T", ev, marg, tot)
    w = [max(0.0, x or 0) for x in G["probs"]]; sw = sum(w) or 1; w = [x / sw for x in w]
    mix = sum(w[i] * psm[i] for i in range(4)); sc = l["p"] / mix if mix > 0 else 1
    return [round(min(0.995, max(0.005, x * sc)), 3) for x in psm]


def attach(LEGS, GAMES, IN, here):
    prb, mul, role = tables(IN, here)
    G = {g["gid"]: g for g in GAMES}; n = 0
    for l in LEGS:
        if l.get("gl") or l.get("sc") or l.get("g") not in G: continue
        v = player_sc(l, G[l["g"]], prb, mul, role)
        if v: l["sc"] = v; n += 1
    return n
