"""fdimplied.py - FanDuel-implied fantasy stats and each player's "insurance" bet (owner 11/6, "Fantasy x betting").

FanDuel's ladders (the links tab: every X+ rung for every player, at FanDuel's current price) are the market's whole picture of a
player's stat line. De-vig each rung and add them up - E[X] = P(X >= 1) + P(X >= 2) + ... - and you have the market's expected
receptions, receiving / rushing / passing yards, passing TDs, interceptions and rush+rec TDs (anytime / 2+ / 3+ TD), with no model of
ours involved. The fantasy page scores those under each league's own settings next to our projection ("FD 13.9"), and can rank by
FanDuel or by a 50/50 blend (the blend is what calib.shrink found best for single props).

Between rungs the chance is interpolated on the probit scale; below the first rung it is extrapolated on the same line (capped at 99%),
above the last one it decays geometrically at the rate of the last two rungs. A market with one rung only is read as Poisson for the
count stats (receptions, TDs, interceptions) and skipped for yards.

De-vig: the power method, p_fair = p_implied ** K, with K solved from the main line's two sides when the unders tab has them, otherwise
1.09 (FanDuel's usual -113/-113 props) and 1.10 for the TD ladders (heavier hold).

Insurance (the opponent-stars card): each player's main-line over on his main stat (QB pass yds, RB rush yds, WR/TE rec yds) - the
bet that cashes in exactly the games where he beats you - with FanDuel's ids for a one-tap betslip link. Anytime TD when there is no
main line.
"""
import bisect, json, math, os, re
from statistics import NormalDist

_N = NormalDist()
STATS = {"Receiving Yards": "rcy", "Receptions": "rec", "Rushing Yards": "ry", "Passing Yards": "py", "Passing TDs": "ptd", "Interceptions": "int"}
COUNT = {"rec", "ptd", "int", "td"}
TDM = {"Anytime TD": 1, "2+ TD": 2, "3+ TD": 3}
PRIMARY = {"QB": "Passing Yards", "RB": "Rushing Yards", "WR": "Receiving Yards", "TE": "Receiving Yards"}
SHORT = {"Passing Yards": "pass yds", "Rushing Yards": "rush yds", "Receiving Yards": "rec yds"}
K_PROP, K_TD = 1.09, 1.10


def normname(x):
    x = re.sub(r"\.", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()


def _imp(o): o = float(o); return 100.0 / (o + 100.0) if o > 0 else -o / (-o + 100.0)


def _vals(IN, n): return json.load(open(os.path.join(IN, n)))["values"]


def _power_k(po, pu):
    """K with po**K + pu**K = 1 (both implied, vig in)."""
    lo, hi = 1.0, 3.0
    if po + pu <= 1.0: return 1.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if po ** mid + pu ** mid > 1: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def _poisson_lam(k, p):
    """Poisson mean with P(X >= k) = p."""
    def tail(lam): return 1.0 - sum(math.exp(-lam) * lam ** j / math.factorial(j) for j in range(k))
    lo, hi = 1e-4, 60.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if tail(mid) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2


def surv_mean(rungs, count=False):
    """E[X] from [(k, P(X >= k))] - k integer thresholds, chances already fair."""
    d = {}
    for k, p in rungs: d.setdefault(k, []).append(p)
    ks = sorted(d); ps = [sum(d[k]) / len(d[k]) for k in ks]
    for i in range(1, len(ps)): ps[i] = min(ps[i], ps[i - 1] * 0.995)   # monotone (alt prices can cross by a hair)
    ps = [min(0.99, max(0.002, p)) for p in ps]
    if len(ks) == 1: return _poisson_lam(ks[0], ps[0]) if count else None
    zs = [_N.inv_cdf(p) for p in ps]
    lam = max(1e-3, math.log(ps[-2] / ps[-1]) / (ks[-1] - ks[-2]))
    s0 = (zs[1] - zs[0]) / (ks[1] - ks[0])
    def S(x):
        if x <= ks[0]: return min(0.99, max(ps[0], _N.cdf(zs[0] + s0 * (x - ks[0]))))
        if x >= ks[-1]: return ps[-1] * math.exp(-lam * (x - ks[-1]))
        i = bisect.bisect_right(ks, x) - 1; t = (x - ks[i]) / (ks[i + 1] - ks[i])
        return _N.cdf(zs[i] + t * (zs[i + 1] - zs[i]))
    top = ks[-1] + int(math.ceil(10 / lam))
    return sum(S(x) for x in range(1, top + 1))


def load(IN):
    lad = {}   # normname -> market -> [(k, odds, market id, selection id)]
    for r in _vals(IN, "links.json")[1:]:
        if len(r) < 8 or not r[0] or str(r[0]).count("|") != 2: continue
        name, mk, k = str(r[0]).split("|")
        if mk not in STATS and mk not in TDM: continue
        try: k = int(float(k)); o = float(r[7])
        except Exception: continue
        if abs(o) < 100: continue
        lad.setdefault(name, {}).setdefault(mk, []).append((k, o, str(r[5] or ""), str(r[6] or "")))
    und = {}   # (normname, market, X+ of the main line) -> (over odds, under odds)
    try:
        # 11/10: the unders tab can still hold LAST week's two-way prices (pulled on its own schedule); a row whose kickoff day has
        # passed is not this week's main line, so it must not de-vig this week's ladder
        import datetime as _dtm, re as _rex
        from zoneinfo import ZoneInfo as _ZI
        _tod = _dtm.datetime.now(_ZI("America/Chicago")).date()
        def _past(r):
            m = _rex.search(r"(\d{1,2})/(\d{1,2})", str(r[7]) if len(r) > 7 else "")
            if not m: return False
            try: d = _dtm.date(_tod.year, int(m.group(1)), int(m.group(2)))
            except Exception: return False
            return d < _tod and (_tod - d).days < 200
        for r in _vals(IN, "unders.json")[1:]:
            if len(r) < 6 or not r[1] or _past(r): continue
            try: und[(normname(r[1]), r[2], int(float(r[3]) + 0.5))] = (float(r[5]), float(r[4]))
            except Exception: pass
    except Exception: pass
    return lad, und


def _main(rungs):
    """The main line: the one rung whose market id is its own (the alt ladder shares one id)."""
    ids = {}
    for x in rungs: ids.setdefault(x[2], []).append(x)
    solo = [v[0] for v in ids.values() if len(v) == 1]
    if len(rungs) == 1: return rungs[0]
    if len(solo) == 1 and len(ids) > 1: return solo[0]
    return None


def player(name, pos, lad, und):
    """-> (fd dict of expected stats, insurance bet or None)."""
    L = lad.get(normname(name))
    if not L: return {}, None
    fd = {}; mains = {}
    for mk, key in STATS.items():
        rungs = L.get(mk)
        if not rungs: continue
        m = _main(rungs); K = K_PROP
        if m is not None and (normname(name), mk, m[0]) in und:
            po, pu = und[(normname(name), mk, m[0])]; K = _power_k(_imp(po), _imp(pu))
        if m is not None: mains[mk] = (m, K)
        v = surv_mean([(k, _imp(o) ** K) for k, o, _, _ in rungs], count=key in COUNT)
        if v is not None: fd[key] = round(v, 2)
    td = [(TDM[mk], _imp(o) ** K_TD) for mk in TDM for k, o, _, _ in (L.get(mk) or [])[:1]]
    if td: fd["td"] = round(surv_mean(td, count=True), 3)
    ins = None
    mk = PRIMARY.get(pos)
    if mk in mains:
        (k, o, mid, sid), K = mains[mk]
        if -200 <= o <= 200: ins = [SHORT[mk], k - 0.5, int(o), mid, sid, round(_imp(o) ** K, 3), "y"]
    if ins is None and L.get("Anytime TD"):
        k, o, mid, sid = L["Anytime TD"][0]; p = _imp(o) ** K_TD
        if p >= 0.2: ins = ["anytime TD", 0.5, int(o), mid, sid, round(p, 3), "t"]
    return fd, ins


def attach(PLAYERS, IN):
    """Adds p['fd'] (market expected stats) and p['ins'] (insurance bet) to the fantasy players. Skips same-name collisions and
    anything wildly off our own projection (a stale or half-posted ladder)."""
    lad, und = load(IN)
    seen = {}
    for p in PLAYERS:
        if p.get("p") in PRIMARY: seen[normname(p["n"])] = seen.get(normname(p["n"]), 0) + 1
    n = 0
    for p in PLAYERS:
        if p.get("p") not in PRIMARY or seen.get(normname(p["n"])) != 1: continue
        fd, ins = player(p["n"], p["p"], lad, und)
        for key in list(fd):
            mine = (p.get("rtd") or 0) + (p.get("rctd") or 0) if key == "td" else p.get(key)
            if isinstance(mine, (int, float)) and mine >= (0.3 if key in COUNT else 8) and not (0.35 <= fd[key] / mine <= 2.8): fd.pop(key)
        if fd: p["fd"] = fd; n += 1
        if ins: p["ins"] = ins
    print(f"FanDuel-implied fantasy stats: {n} players; insurance bets for {sum(1 for p in PLAYERS if p.get('ins'))}")
    return n
