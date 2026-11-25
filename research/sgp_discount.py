#!/usr/bin/env python3
"""FanDuel's same-game discount, measured (owner 11/17: "get to the FanDuel same game discount").

FanDuel does not pay the legs multiplied on a same-game parlay: it prices the legs together (correlation) and keeps more for itself
the longer the slip. This script measures how much, from the only real quotes we hold: every slip on 'PROMO - Promoted Bets' whose
column E is FanDuel's own price (the rule since 10/22) and whose legs each carry a FanDuel price.

For each such slip:
    multiplied = the legs' decimal odds multiplied
    joint      = FanDuel's implied chance of every leg hitting, the legs tied together with the builder's own same-game correlations
                 (same Gaussian copula as joint() in build_builder.py; unders flip the sign)
    actual     = FanDuel's quote
and the fit is:   FanDuel's price for n legs in one game ~= exp(-c * (n - 1)^p) / joint
(n = 1 gives exactly the leg's own price; a slip over several games multiplies its games). c is least squares through the origin for
each p in (2, 2.5, 3); p is the one whose prices miss least when every slip is priced by a fit that never saw it.

Usage:  python3 research/sgp_discount.py [in-dir]         (default ./in; needs out/builder_data.json for the correlation tables)
Writes: research/sgp_discount.json (read by build_builder.py / build_boards.py at build time) and research/sgp_discount.md.
Run it on Tuesdays after the promos are graded; it only gets better as same-game promos with FanDuel's own price pile up.
Nothing is invented: a slip with an unpriced or unreadable leg is listed as skipped, and a "same-game" price that equals the legs
multiplied (how same-game slips were written before 10/22) is not a quote and is left out.
"""
import csv, json, math, os, re, sys, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); GP = os.path.dirname(HERE)
sys.path.insert(0, GP)
import slipgrade

C_OLD = None            # the estimate the builder used until 11/17: 0.85 / joint + 0.15
C_DEFAULT, P_DEFAULT = 0.00146, 3.0      # used by the generators when research/sgp_discount.json is missing (the 11/17 fit, 30 quotes)

def dec(o):
    try: o = float(str(o).replace("+", "").replace(",", "").replace("−", "-"))
    except Exception: return None
    if abs(o) < 100: return None
    return 1 + o / 100 if o > 0 else 1 + 100 / abs(o)
def am(d):
    if not d or d <= 1: return ""
    return f"+{round((d - 1) * 100)}" if d >= 2 else f"-{round(100 / (d - 1))}"

STAT = [("anytime td", "TD"), ("either", "TD"), ("2+ td", "TD"), ("first td", "FTD"), ("receiving yards", "RECYDS"), ("receptions", "REC"), ("longest reception", "LONG"),
        ("rush + rec", "RUSH"), ("rush+rec", "RUSH"), ("rushing + receiving", "RUSH"), ("rushing yards", "RUSH"), ("passing yards", "PASS"),
        ("passing td", ""), ("pass td", ""), ("completions", ""), ("rushing attempts", ""), ("carries", "")]

class Book:
    """who plays whom each week, and each player's team / position (game log first, the builder's legs for the week not played yet)"""
    def __init__(self, IN, bd):
        self.IN = IN; self.bd = bd; self.gr = {}
        g = json.load(open(os.path.join(IN, "gamelog.json")))["values"]; H = {c.strip(): i for i, c in enumerate(g[0])}
        self.seen = {}                                   # player -> [(week, team, pos)]
        for r in g[1:]:
            try: w = int(float(r[H["Week"]]))
            except Exception: continue
            self.seen.setdefault(slipgrade.norm(r[H["Player"]]), []).append((w, str(r[H["Team"]]).strip().upper(), str(r[H["Pos"]]).strip().upper()))
        self.opp = {}                                    # (week, team) -> opponent
        try:
            for x in csv.DictReader(open(os.path.join(IN, "games.csv"), newline="")):
                if x.get("season") != "2026" or x.get("game_type", "REG") != "REG": continue
                h, a = slipgrade.ALIAS.get(x["home_team"], x["home_team"]), slipgrade.ALIAS.get(x["away_team"], x["away_team"])
                self.opp[(int(x["week"]), h)] = a; self.opp[(int(x["week"]), a)] = h
        except Exception: pass
        self.bl = {}
        for l in bd.get("legs", []): self.bl.setdefault(slipgrade.norm(l["pl"]), l)
    def team(self, tok):
        t = str(tok).strip(); u = slipgrade.ALIAS.get(t.upper(), t.upper())
        if re.fullmatch(r"[A-Z]{2,3}", u) and u in set(slipgrade.NICK.values()): return u
        for w in reversed(t.lower().split()):
            if w in slipgrade.NICK: return slipgrade.NICK[w]
        return None
    def game(self, week, tm):
        o = self.opp.get((week, tm))
        return "-".join(sorted([tm, o])) if o else None
    def player(self, week, name):
        k = slipgrade.norm(name); rows = self.seen.get(k)
        if not rows:   # same last name, first three letters of the first name (as slipgrade)
            kw = k.split()
            for kk, v in self.seen.items():
                w = kk.split()
                if kw and w and len(w) == len(kw) and w[-1] == kw[-1] and w[0][:3] == kw[0][:3]: rows = v; break
        if rows:
            at = [x for x in rows if x[0] == week] or sorted([x for x in rows if x[0] < week], key=lambda x: -x[0])[:1] or sorted(rows)[:1]
            return k, at[0][1], at[0][2]
        b = self.bl.get(k)
        return (k, b["tm"], b["pos"]) if b else None

def resolve(B, week, who, market):
    ml = market.strip().lower(); under = ml.startswith("under ")
    if ml.startswith(("spread", "money")) or ml == "ml":
        tm = B.team(re.sub(r"\s*(?:[+-]\d+(?:\.\d+)?|ml|moneyline)\s*$", "", who.strip(), flags=re.I)); g = B.game(week, tm) if tm else None
        return {"pl": who, "tm": tm, "g": g, "c": "", "gl": {"k": "M", "side": tm}} if g else None
    if ml.startswith("total"):
        m = re.match(r"(over|under)\s+[\d.]+\s*\(?\s*([A-Za-z]{2,3})\s*[-@]\s*([A-Za-z]{2,3})", who.strip(), re.I)
        if not m: return None
        a = B.team(m.group(2)); g = B.game(week, a) if a else None
        return {"pl": who, "tm": "", "g": g, "c": "", "gl": {"k": "T", "side": m.group(1).upper()}} if g else None
    st = next((v for k, v in STAT if k in ml), None)
    if st is None: return None
    p = B.player(week, re.split(r"\s+or\s+|\s*/\s*", who.strip())[0])
    if not p: return None
    g = B.game(week, p[1])
    return {"pl": p[0], "tm": p[1], "g": g, "c": (f"{p[2]}_{st}" if st else ""), "u": under} if g else None

# ---- the builder's same-game correlation, ported (build_builder.py corr() / joint()) ----
def make_joint(bd):
    import numpy as np
    from statistics import NormalDist
    CORR = bd.get("corr") or {}; GL = bd.get("glcorr") or {}
    def glprop(gl, x):
        r = GL.get(x.get("c") or "")
        if not r: return 0.0
        if gl["gl"]["k"] == "M": return r["margin"] if gl["gl"]["side"] == x.get("tm") else -r["margin"]
        return r["total"] if gl["gl"]["side"] == "OVER" else -r["total"]
    def corr0(a, b):
        if a["g"] != b["g"]: return 0.0
        if a.get("gl") and b.get("gl"): return 0.0 if a["gl"]["k"] != b["gl"]["k"] else (0.999 if a["gl"]["side"] == b["gl"]["side"] else -0.999)
        if a.get("gl"): return glprop(a, b)
        if b.get("gl"): return glprop(b, a)
        if not a.get("c") or not b.get("c"): return 0.0
        rel = "SP" if a["pl"] == b["pl"] else ("TM" if a.get("tm") == b.get("tm") else "OPP")
        k = sorted([a["c"], b["c"]]); return float(CORR.get(f"{rel}|{k[0]}|{k[1]}", 0) or 0)
    def corr(a, b): return (-1 if a.get("u") else 1) * (-1 if b.get("u") else 1) * corr0(a, b)
    def joint(ls, key="bk", draws=400000):
        n = len(ls)
        if n == 1: return ls[0][key]
        C = [[1.0 if i == j else corr(ls[i], ls[j]) for j in range(n)] for i in range(n)]
        if not any(C[i][j] for i in range(n) for j in range(n) if i != j): return math.prod(l[key] for l in ls)
        z = np.array([NormalDist().inv_cdf(min(0.995, max(0.005, l[key]))) for l in ls])
        M = np.array(C); w, v = np.linalg.eigh(M); M = v @ np.diag(np.clip(w, 1e-6, None)) @ v.T
        g = np.random.default_rng(7).multivariate_normal(np.zeros(n), M, size=draws)
        return max(float(np.mean(np.all(g <= z, axis=1))), 1e-7)
    return joint

P_GRID = (2.0, 2.5, 3.0)
DOG = 0.45              # a "long shot" leg: FanDuel's own price puts it under 45% (owner 11/25: "get better at mathematically getting the right number")
def k_of(c, n, p=2.0): return math.exp(-c * (n - 1) ** p)
def estimate(c, groups, joint, p=2.0):
    """groups: the slip's legs by game -> the estimated FanDuel decimal price"""
    d = 1.0
    for ls in groups:
        d *= (1 / ls[0]["bk"]) if len(ls) == 1 else max(1.01, k_of(c, len(ls), p) / joint(ls))
    return d

def record(base, D, legs, gs, joint, src):
    groups = list(gs.values()); x = None; mult = math.prod(l["d"] for l in legs)
    base_d = 1.0
    for v in groups: base_d *= (1 / v[0]["bk"]) if len(v) == 1 else 1 / joint(v)
    return {**base, "src": src, "games": len(groups), "max_n": max(len(v) for v in groups), "ns": [len(v) for v in groups if len(v) > 1], "actual": D, "mult": mult, "base": base_d,
            "y": math.log(D / base_d), "dogs": sum(1 for v in groups if len(v) > 1 for l in v if l["bk"] < DOG), "old": math.prod((1 / v[0]["bk"]) if len(v) == 1 else max(1.01, 0.85 * (1 / joint(v)) + 0.15) for v in groups),
            "legs": [l["txt"] for l in legs]}

SITE_MAX = 400          # the most site quotes kept (newest first); a fit is a few dozen slips
def site_quotes(IN, save=True):
    """FanDuel prices typed into the builder, or read off an imported FanDuel betslip, by signed-in readers (owner 11/25: keep every
    price as a data point). They reach the sheet-mirror as in/fd_quotes.json (the sheet-mirror job asks the database for them); this
    merges them into research/sgp_quotes_site.json so a run without the mirror still has them. A row is kept only if it can be a
    FanDuel same-game price at all: 2-12 legs, each with a real price, two or more in one game, and a price between 3% and 160% of the
    legs multiplied (a typo, or a price for another slip, is neither). One quote per identical slip: the newest."""
    path = os.path.join(HERE, "sgp_quotes_site.json")
    try: have = json.load(open(path)).get("quotes", [])
    except Exception: have = []
    try: new = json.load(open(os.path.join(IN, "fd_quotes.json"))).get("quotes", [])
    except Exception: new = []
    by, bad = {}, 0
    for q in have + new:
        try:
            legs = q["legs"]; D = dec(q["fanduel"]); week = int(q["week"])
            if not (2 <= len(legs) <= 12) or not D or not (1 <= week <= 25): raise ValueError
            ds = [dec(l["o"]) for l in legs]
            if any(d is None or d <= 1 for d in ds) or any(not l.get("pl") or not l.get("g") or not l.get("m") for l in legs): raise ValueError
            gs = {}
            for l in legs: gs[l["g"]] = gs.get(l["g"], 0) + 1
            mult = math.prod(ds)
            if max(gs.values()) < 2 or not (0.03 <= (D - 1) / (mult - 1) <= 1.6) or abs(D / mult - 1) < 0.004: raise ValueError
            key = (week, tuple(sorted((str(l["pl"]), str(l["m"]), float(l.get("ln") or 0), int(l["o"])) for l in legs)))
            keep = {"id": q.get("id"), "at": str(q.get("at") or ""), "week": week, "src": str(q.get("src") or "typed")[:12], "fanduel": int(q["fanduel"]), "est": q.get("est"),
                    "title": f'Site quote {str(q.get("at") or "")[:10]} ({q.get("src") or "typed"}, {len(legs)} legs)',
                    "legs": [{k: l[k] for k in ("pl", "m", "ln", "o", "tm", "g", "c", "gl", "u") if l.get(k) is not None} for l in legs]}
            if key not in by or keep["at"] >= by[key]["at"]: by[key] = keep
        except Exception: bad += 1
    out = sorted(by.values(), key=lambda q: q["at"], reverse=True)[:SITE_MAX]
    if save and (out or have):
        json.dump({"source": "FanDuel prices typed into the builder or read from an imported FanDuel betslip on the site (database table fd_quotes, through the sheet-mirror's in/fd_quotes.json). No account is stored with a row.",
                   "quotes": out}, open(path, "w"), indent=1)
    return out, bad


def run(IN):
    bd = json.load(open(os.path.join(GP, "out", "builder_data.json")))
    B = Book(IN, bd); joint = make_joint(bd)
    promos = json.load(open(os.path.join(IN, "promos.json")))["values"]
    quotes, skipped, multiplied = [], [], []
    for i, r in enumerate(promos[1:], start=2):
        r = list(r) + [""] * (14 - len(r))
        try: week = int(float(r[0]))
        except Exception: continue
        D = dec(r[4]); legs = []; bad = None
        for l in str(r[3]).split("\n"):
            if not l.strip(): continue
            p = [x.strip() for x in l.split("|")]
            if len(p) < 3 or dec(p[2]) is None: bad = f"a leg has no price ({p[0][:30]})"; break
            x = resolve(B, week, p[0], p[1])
            if not x: bad = f"a leg could not be placed in a game ({p[0][:30]})"; break
            x["d"] = dec(p[2]); x["bk"] = 1 / x["d"]; x["txt"] = f"{p[0]} {p[1]} ({p[2]})"; legs.append(x)
        gs = {}
        for l in legs: gs.setdefault(l["g"], []).append(l)
        same = any(len(v) > 1 for v in gs.values())
        base = {"row": i, "week": week, "title": str(r[2]).strip(), "n": len(legs)}
        if not D: continue
        if bad:
            skipped.append({**base, "why": bad}); continue
        if not same: continue
        mult = math.prod(l["d"] for l in legs)
        if abs(D / mult - 1) < 0.004:
            multiplied.append({**base, "price": am(D)}); continue      # the legs multiplied, not FanDuel's quote
        quotes.append(record(base, D, legs, gs, joint, "posted"))
    # FanDuel prices the owner read off his own betslip (screenshots) for slips that were never posted: research/sgp_quotes_owner.json holds
    # each slip's legs with that morning's leg prices from the site build of the hour (see the file's "source" line)
    try: extra = json.load(open(os.path.join(HERE, "sgp_quotes_owner.json")))
    except Exception: extra = {"quotes": []}
    site, site_bad = site_quotes(IN)
    for k, q in enumerate(extra.get("quotes", []) + site):
        from_site = k >= len(extra.get("quotes", []))
        legs = []
        for l in q["legs"]:
            x = dict(l); x["d"] = dec(l["o"]); x["bk"] = 1 / x["d"]; x["pl"] = slipgrade.norm(l["pl"]) if not l.get("gl") else l["pl"]; x["ln"] = float(l.get("ln") or 0); x.setdefault("c", "")
            x["txt"] = f'{l["pl"]} {"" if l.get("gl") else l["m"] + " " + format(l["ln"], "g") + "+ "}({am(x["d"])})'; legs.append(x)
        gs = {}
        for l in legs: gs.setdefault(l["g"], []).append(l)
        if not any(len(v) > 1 for v in gs.values()): continue
        quotes.append(record({"row": (f"site-{q.get('id') or k}" if from_site else f"owner-{k + 1}"), "week": int(q["week"]), "title": q["title"], "n": len(legs)}, dec(q["fanduel"]), legs, gs, joint, "typed on the site" if from_site else "owner's betslip"))
    if not quotes: return None
    X = lambda q, p: sum((n - 1) ** p for n in q["ns"])
    fit = lambda qs, p: max(0.0, -sum(X(q, p) * q["y"] for q in qs) / sum(X(q, p) ** 2 for q in qs))
    def loo(p):
        out = []
        for k, q in enumerate(quotes):
            c1 = fit(quotes[:k] + quotes[k + 1:], p) if len(quotes) > 2 else fit(quotes, p)
            out.append(q["base"] * math.exp(-c1 * X(q, p)))                # priced by a fit that never saw this slip
        return out
    tries = {p: loo(p) for p in P_GRID}
    miss = {p: statistics.median(abs(math.log(e / q["actual"])) for e, q in zip(v, quotes)) for p, v in tries.items()}
    p = min(P_GRID, key=lambda x: (round(miss[x], 4), x)); c = fit(quotes, p)
    # ---- 11/25: is there a better formula in these quotes? Every candidate is priced the same way - each slip by a fit that never saw it - and
    # one is promoted only if it is no worse than the current formula on ALL FOUR measures (median, mean, short slips, long slips) and
    # better on at least two. Tried by hand on 35 quotes 11/25 and NOT better: a term for same-player pairs, one for a QB with his own
    # receivers, one for other teammates (all fitted to zero); our leg-to-leg links scaled 0.6x-2x (better median, worse on long slips); a
    # cut that grows with the price itself (worse everywhere). The one with something in it is below: an extra cut for each long-shot leg -
    # where the current formula misses, it says too long a price on slips full of long shots and too short on slips of heavy favorites.
    def fit2(qs, pp):
        a11 = sum(X(q, pp) ** 2 for q in qs); a12 = sum(X(q, pp) * q["dogs"] for q in qs); a22 = sum(q["dogs"] ** 2 for q in qs)
        b1 = -sum(X(q, pp) * q["y"] for q in qs); b2 = -sum(q["dogs"] * q["y"] for q in qs); det = a11 * a22 - a12 * a12
        if det > 1e-9:
            cc, dd = (b1 * a22 - b2 * a12) / det, (a11 * b2 - a12 * b1) / det
            if cc >= 0 and dd >= 0: return cc, dd
        c_only = max(0.0, b1 / a11) if a11 else 0.0; d_only = max(0.0, b2 / a22) if a22 else 0.0
        e = lambda cc, dd: sum((q["y"] + cc * X(q, pp) + dd * q["dogs"]) ** 2 for q in qs)
        return (c_only, 0.0) if e(c_only, 0.0) <= e(0.0, d_only) else (0.0, d_only)
    def loo2(pp):
        out = []
        for k, q in enumerate(quotes):
            cc, dd = fit2(quotes[:k] + quotes[k + 1:], pp) if len(quotes) > 3 else fit2(quotes, pp)
            out.append(q["base"] * math.exp(-cc * X(q, pp) - dd * q["dogs"]))
        return out
    def measures(est):
        e = [abs(math.log(x / q["actual"])) for x, q in zip(est, quotes)]
        sh = [x for x, q in zip(e, quotes) if max(q["ns"]) <= 4]; lg = [x for x, q in zip(e, quotes) if max(q["ns"]) >= 5]
        return [round(statistics.median(e), 4), round(statistics.mean(e), 4), round(statistics.median(sh), 4) if sh else 0.0, round(statistics.median(lg), 4) if lg else 0.0]
    m_now = measures(tries[p]); t2 = loo2(p); m_dog = measures(t2); c2, d2 = fit2(quotes, p)
    promote = len(quotes) >= 30 and d2 > 0 and all(b <= a + 1e-9 for a, b in zip(m_now, m_dog)) and sum(1 for a, b in zip(m_now, m_dog) if b < a * 0.98) >= 2
    dog = 0.0
    if promote: c, dog, loo_used = c2, d2, t2
    else: loo_used = tries[p]
    variants = [{"formula": "the legs' count only (in use)" if not promote else "the legs' count only", "median": m_now[0], "mean": m_now[1], "2-4 legs": m_now[2], "5+ legs": m_now[3]},
                {"formula": "count + a cut for each long-shot leg" + (" (in use)" if promote else ""), "median": m_dog[0], "mean": m_dog[1], "2-4 legs": m_dog[2], "5+ legs": m_dog[3], "c": round(c2, 6), "per_long_shot": round(d2, 5)}]
    for q, e in zip(quotes, loo_used):
        q["new"] = q["base"] * math.exp(-c * X(q, p) - dog * q["dogs"]); q["loo"] = e
        q["pct_mult"] = (q["actual"] - 1) / (q["mult"] - 1)
    err = lambda key, qs=None: statistics.median(abs(math.log(q[key] / q["actual"])) for q in (qs or quotes))
    short = [q for q in quotes if max(q["ns"]) <= 4]; long_ = [q for q in quotes if max(q["ns"]) >= 5]
    bands = []
    for lab, lo, hi in (("2-3 legs", 2, 3), ("4 legs", 4, 4), ("5-6 legs", 5, 6), ("7+ legs", 7, 99)):
        qs = [q for q in quotes if q["games"] == 1 and lo <= q["n"] <= hi]
        v = sorted(q["pct_mult"] for q in qs)
        bands.append({"legs": lab, "quotes": len(qs), "low": round(v[0], 3) if v else None, "median": round(statistics.median(v), 3) if v else None, "high": round(v[-1], 3) if v else None,
                      "k": round(k_of(c, statistics.median([lo, min(hi, 9)]), p), 3)})
    # how far off the estimate has been, by the slip's longest same-game group: the range the pages print beside a long slip's estimate.
    # 80th percentile of the left-out misses, so about four slips in five landed inside it.
    def q80(v): v = sorted(v); return v[min(len(v) - 1, int(math.ceil(0.8 * len(v))) - 1)] if v else None
    spread = {}
    for lab, lo, hi in (("2-4", 2, 4), ("5-6", 5, 6), ("7+", 7, 99)):
        v = [abs(math.log(q["loo"] / q["actual"])) for q in quotes if lo <= max(q["ns"]) <= hi]
        spread[lab] = {"quotes": len(v), "miss80": round(q80(v), 3) if v else None}
    out = {"dog": round(dog, 5), "dog_under": DOG, "variants": variants, "spread": spread, "c": round(c, 6), "p": p, "p_tried": {str(k): round(v, 3) for k, v in miss.items()}, "quotes": len(quotes), "posted": sum(1 for q in quotes if q["src"] == "posted"), "from_site": sum(1 for q in quotes if q["src"] == "typed on the site"), "site_rows_dropped": site_bad, "weeks": sorted({q["week"] for q in quotes}),
           "err_median": {"legs multiplied": round(err("mult"), 3), "old estimate (0.85 / joint + 0.15)": round(err("old"), 3), "new estimate, each slip left out of its own fit": round(err("loo"), 3)},
           "err_new_by_length": {"2-4 legs": [len(short), round(err("loo", short), 3) if short else None], "5+ legs": [len(long_), round(err("loo", long_), 3) if long_ else None]},
           "k": {str(n): round(k_of(c, n, p), 3) for n in range(2, 11)}, "bands": bands,
           "rows": [{"week": q["week"], "title": q["title"], "source": q["src"], "legs": q["n"], "fanduel": am(q["actual"]), "multiplied": am(q["mult"]), "pct_of_multiplied_payout": round(q["pct_mult"], 3),
                     "old_estimate": am(q["old"]), "new_estimate": am(q["loo"]), "leg_list": q["legs"]} for q in quotes],
           "not_quotes": multiplied, "skipped": skipped}
    return out

def md(o):
    L = ["# FanDuel's same-game discount (measured)", "",
         f"{o['quotes']} same-game slips with FanDuel's own price, Weeks {o['weeks'][0]}-{o['weeks'][-1]}: {o['posted']} we posted (the promo tab) and {o['quotes'] - o['posted']} the owner priced on his",
         "betslip without posting (screenshots of 11/14). \"Share of the multiplied payout\" = FanDuel's",
         "payout on $1 divided by what the legs multiplied would pay.", "",
         "| Legs in one game | Quotes | Share of the multiplied payout (low - median - high) |", "|---|---|---|"]
    for b in o["bands"]:
        L.append(f"| {b['legs']} | {b['quotes']} | " + (f"{b['low']:.0%} - {b['median']:.0%} - {b['high']:.0%}" if b["quotes"] else "no quotes yet") + " |")
    L += ["", f"Fit: FanDuel's price for n legs in one game = exp(-{o['c']} x (n-1)^{o['p']:g}) / (FanDuel's implied chances joined with our same-game correlations).",
          "That multiplier by leg count: " + ", ".join(f"{n} legs {v:.0%}" for n, v in o["k"].items()) + ".",
          "Median miss (log price): " + "; ".join(f"{k} {v:.2f}" for k, v in o["err_median"].items()) + ". By length, new estimate: " + "; ".join(f"{k} {v[1]:.2f} ({v[0]} slips)" for k, v in o["err_new_by_length"].items() if v[1] is not None) + ".", "",
          "Is there a better formula? Each candidate prices every slip with a fit that never saw it (median, mean, short slips, long slips; lower is better): "
          + "; ".join(f"{v['formula']}: {v['median']:.3f} / {v['mean']:.3f} / {v['2-4 legs']:.3f} / {v['5+ legs']:.3f}" + (f" (each long-shot leg x{math.exp(-v['per_long_shot']):.2f})" if v.get("per_long_shot") else "") for v in o.get("variants", []))
          + ". A candidate replaces the formula in use only when it is no worse on all four and better on two.",
          "How far off the estimate has been (four slips in five landed inside): " + "; ".join(f"{k} legs x/÷ {math.exp(v['miss80']):.2f} ({v['quotes']} slips)" for k, v in o.get("spread", {}).items() if v.get("miss80") is not None) + ".",
          f"From the site: {o.get('from_site', 0)} quotes typed or imported by readers ({o.get('site_rows_dropped', 0)} rows dropped as not a possible same-game price).", "",
          "| Wk | Slip | From | Legs | FanDuel | Legs multiplied | Share | Old estimate | New estimate (left out of its own fit) |", "|---|---|---|---|---|---|---|---|---|"]
    for r in o["rows"]:
        L.append(f"| {r['week']} | {r['title']} | {r['source']} | {r['legs']} | {r['fanduel']} | {r['multiplied']} | {r['pct_of_multiplied_payout']:.0%} | {r['old_estimate']} | {r['new_estimate']} |")
    if o["not_quotes"]: L += ["", "Same-game slips whose tab price is just the legs multiplied (not a quote, left out): " + "; ".join(f"Wk {x['week']} {x['title']}" for x in o["not_quotes"]) + "."]
    if o["skipped"]: L += ["", "Skipped: " + "; ".join(f"Wk {x['week']} {x['title']} - {x['why']}" for x in o["skipped"]) + "."]
    return "\n".join(L) + "\n"

if __name__ == "__main__":
    IN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(GP, "in")
    o = run(IN)
    if not o: print("no same-game quotes on the promo tab yet"); sys.exit(0)
    json.dump(o, open(os.path.join(HERE, "sgp_discount.json"), "w"), indent=1)
    open(os.path.join(HERE, "sgp_discount.md"), "w", encoding="utf-8").write(md(o))
    print(f"wrote research/sgp_discount.json + .md: {o['quotes']} quotes, c = {o['c']}, p = {o['p']} (tried {o['p_tried']}), median miss {o['err_median']}, by length {o['err_new_by_length']}")
    for b in o["bands"]: print("  ", b)
