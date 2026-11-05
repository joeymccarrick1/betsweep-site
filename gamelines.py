"""Game-line legs (moneyline, spread, total) shared by the matchup boards and the parlay builder, so every page prices them the same way.

Model: final margin (A minus B) ~ Normal(model margin, 12.6) and total ~ Normal(model total, 12.9), independent. The SDs are the measured
residuals of final results around the closing market (816 games 2023-25; 2026 W1-5: 12.3 / 13.0).

Per game script: the four endings on the game-scripts tab are regions of (margin, total): A by 10+ (margin >= 10), close & low (|margin| <= 9,
total <= 50), shootout (|margin| <= 9, total >= 51), B by 10+. For each leg we compute its chance INSIDE each ending from the normal model
(e.g. Over 42.5 given "close, low" = P(42.5 < total <= 50.5) / P(total <= 50.5)), then mix with the tab's script odds. That keeps game lines
coherent with the player legs in a parlay: an Under next to a shootout leg prices as the long shot it is.

Market anchor: the model's team scores have NOT been back-tested against closing spreads/totals yet, so the chance we use is shrunk halfway to
FanDuel's no-vig price (SHRINK = 0.5). A model-vs-market gap of 4+ points is a risk flag; those legs never go into a best parlay.
"""
import json, os, re, math, csv

SD_MARGIN, SD_TOTAL = 12.6, 12.9
SHRINK = 0.5            # weight on the model; the rest is the market's no-vig chance (until game projections are validated)
GAP_FLAG = 4.0          # points of model-vs-market disagreement that make a leg a risk
ALT_ODDS_LIM = 1000     # alternate lines priced beyond -1000 / +1000 are dropped (FanDuel lists rungs out to -50000)
ALT_SPREAD_WIN = 14.0   # alternate spreads kept within this many points of FanDuel's main spread
ALT_TOTAL_WIN = 12.0    # alternate totals kept within this many points of FanDuel's main total
TEAM_FULL = {"Arizona Cardinals":"ARI","Atlanta Falcons":"ATL","Baltimore Ravens":"BAL","Buffalo Bills":"BUF","Carolina Panthers":"CAR","Chicago Bears":"CHI","Cincinnati Bengals":"CIN","Cleveland Browns":"CLE","Dallas Cowboys":"DAL","Denver Broncos":"DEN","Detroit Lions":"DET","Green Bay Packers":"GB","Houston Texans":"HOU","Indianapolis Colts":"IND","Jacksonville Jaguars":"JAX","Kansas City Chiefs":"KC","Las Vegas Raiders":"LV","Los Angeles Chargers":"LAC","Los Angeles Rams":"LA","Miami Dolphins":"MIA","Minnesota Vikings":"MIN","New England Patriots":"NE","New Orleans Saints":"NO","New York Giants":"NYG","New York Jets":"NYJ","Philadelphia Eagles":"PHI","Pittsburgh Steelers":"PIT","San Francisco 49ers":"SF","Seattle Seahawks":"SEA","Tampa Bay Buccaneers":"TB","Tennessee Titans":"TEN","Washington Commanders":"WAS"}
NICK = {v: k.split()[-1] for k, v in TEAM_FULL.items()}

def _phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))
def _imp(o): return (100 / (o + 100)) if o > 0 else (-o / (-o + 100))
def _num(x):
    try: return float(str(x).replace(",", "").replace("%", ""))
    except Exception: return None

def load_fd(IN):
    """'AUTO - FanDuel Game Lines' -> {(team abbr or OVER/UNDER, market, point, frozenset game): (odds, marketId, selectionId)}"""
    out = {}
    try: rows = json.load(open(os.path.join(IN, "gamelines.json")))["values"]
    except Exception: return out
    for r in rows[1:]:
        if len(r) < 10 or not r[0]: continue
        away, _, home = r[1].partition(" @ "); ga, gh = TEAM_FULL.get(away.strip()), TEAM_FULL.get(home.strip())
        side = TEAM_FULL.get(r[4].strip(), r[4].strip().upper()); o = _num(r[6])
        if not (ga and gh) or o is None: continue
        # IDs from the link (the sheet can round the Market ID column); first kickoff wins if a matchup repeats in a later week
        mm = re.search(r"[?&]marketId=([^&#]+)", str(r[7])); ss = re.search(r"[?&]selectionId=([^&#]+)", str(r[7]))
        k = (side, r[3], _num(r[5]) if r[3] != "Moneyline" else 0, frozenset([ga, gh]))
        if k not in out: out[k] = (int(o), mm.group(1) if mm else str(r[8]), ss.group(1) if ss else str(r[9]))
    return out

def load_sched(IN, week):
    with open(os.path.join(IN, "games.csv"), newline="") as f:
        return {frozenset([g["away_team"], g["home_team"]]): g for g in csv.DictReader(f)
                if g["season"] == "2026" and g["week"] == str(week) and g["game_type"] == "REG"}

# ---- chance of a threshold event inside each script region ----
def _pint(lo, hi, mu, sd):   # P(lo < X < hi)
    a = 0.0 if lo is None else _phi((lo - mu) / sd); b = 1.0 if hi is None else _phi((hi - mu) / sd)
    return max(0.0, b - a)
def _cond(lo_ev, hi_ev, lo_r, hi_r, mu, sd):
    """P(event interval | region interval) for one normal variable."""
    pr = _pint(lo_r, hi_r, mu, sd)
    if pr < 1e-9: return None
    lo = lo_ev if lo_r is None else (lo_r if lo_ev is None else max(lo_ev, lo_r))
    hi = hi_ev if hi_r is None else (hi_r if hi_ev is None else min(hi_ev, hi_r))
    if lo is not None and hi is not None and lo >= hi: return 0.0
    return _pint(lo, hi, mu, sd) / pr
# regions in (margin A-B, total): 0 = A by 10+, 1 = close & low, 2 = shootout, 3 = B by 10+
M_REG = [(9.5, None), (-9.5, 9.5), (-9.5, 9.5), (None, -9.5)]
T_REG = [(None, None), (None, 50.5), (50.5, None), (None, None)]

def by_script(kind, ev, marg, tot):
    """kind 'M': ev = (lo, hi) on margin A-B; kind 'T': ev = (lo, hi) on total. Returns [P(leg | script k) for k in 0..3]."""
    out = []
    for k in range(4):
        if kind == "M": c = _cond(ev[0], ev[1], M_REG[k][0], M_REG[k][1], marg, SD_MARGIN)
        else: c = _cond(ev[0], ev[1], T_REG[k][0], T_REG[k][1], tot, SD_TOTAL)
        if c is None: c = _pint(ev[0], ev[1], marg if kind == "M" else tot, SD_MARGIN if kind == "M" else SD_TOTAL)
        out.append(min(0.995, max(0.005, c)))
    return out

def game_legs(a, b, pa, pb, probs, sched, fdgl):
    """All game-line legs for game a vs b (a/b in the game-scripts tab's order). probs = the tab's four script odds (any scale).
    Returns a list of dicts: disp, m (Moneyline/Spread/Total), ms, side (team or OVER/UNDER), tm, opp, ln, o, bk, nv (no-vig market chance),
    pm (plain model chance), ps (per-script chance, after the market anchor), p (script-mixed chance, after the market anchor), fd (ids or None),
    src ('fd'/'cons'), gap, risk (text or ''), why."""
    marg = (pa or 0) - (pb or 0); tot = (pa or 0) + (pb or 0)
    w = [max(0.0, (x or 0)) for x in probs]; sw = sum(w)
    if sw <= 0:   # no script odds: use the normal model's own region weights
        w = [_pint(9.5, None, marg, SD_MARGIN), _pint(-9.5, 9.5, marg, SD_MARGIN) * _pint(None, 50.5, tot, SD_TOTAL),
             _pint(-9.5, 9.5, marg, SD_MARGIN) * _pint(50.5, None, tot, SD_TOTAL), _pint(None, -9.5, marg, SD_MARGIN)]; sw = sum(w)
    w = [x / sw for x in w]
    sch = sched.get(frozenset([a, b]))
    def cons(field): return _num(sch[field]) if sch and sch.get(field) not in (None, "", "NA") else None
    home = sch["home_team"] if sch else b
    sl = cons("spread_line"); tl = cons("total_line")
    g = frozenset([a, b])
    def fd_at(side, mk, pt):
        k = (side, mk, pt if mk != "Moneyline" else 0, g); v = fdgl.get(k)
        if v: return pt, v
        if mk != "Moneyline":   # FanDuel may hang a different number: take its line for this side
            alt = sorted([(k_, v_) for k_, v_ in fdgl.items() if k_[0] == side and k_[1] == mk and k_[3] == g], key=lambda x: abs((x[0][2] or 0) - (pt or 0)))
            if alt: return alt[0][0][2], alt[0][1]
        return pt, None
    raw = []
    for t, o_t in ((a, b), (b, a)):
        is_home = (t == home); sgn = 1 if t == a else -1
        pt, fd = fd_at(t, "Moneyline", 0)
        raw.append(dict(disp=f"{NICK.get(t, t)} ML", m="Moneyline", ms="ML", side=t, tm=t, opp=o_t, ln=0, fd=fd,
                        co=cons("home_moneyline" if is_home else "away_moneyline"), kind="M", ev=((0, None) if sgn == 1 else (None, 0))))
        base = None if sl is None else (-sl if is_home else sl)
        if base is not None or any(k[0] == t and k[1] == "Spread" and k[3] == g for k in fdgl):
            pt, fd = fd_at(t, "Spread", base if base is not None else 0)
            # team t covers pt: (t's margin) + pt > 0  ->  margin A-B > -pt for A, < pt for B
            raw.append(dict(disp=f"{t} {pt:+g}", m="Spread", ms="Spread", side=t, tm=t, opp=o_t, ln=pt, fd=fd,
                            co=(cons("home_spread_odds" if is_home else "away_spread_odds") if base is not None and pt == base else None),
                            kind="M", ev=((-pt, None) if sgn == 1 else (None, pt))))
    for side in ("OVER", "UNDER"):
        pt, fd = fd_at(side, "Total", tl if tl is not None else 0)
        if tl is None and not fd: continue
        raw.append(dict(disp=f"{side.title()} {pt:g}", m="Total", ms="Total", side=side, tm=a, opp=b, ln=pt, fd=fd,
                        co=(cons("over_odds" if side == "OVER" else "under_odds") if tl is not None and pt == tl else None),
                        kind="T", ev=((pt, None) if side == "OVER" else (None, pt))))
    # FanDuel alternate spreads / totals (Market 'Alt Spread' / 'Alt Total' in the tab): every rung, priced by the same model; alt=True
    main_pts = {(r["m"], r["side"], r["ln"]) for r in raw}
    main_sp = {r["side"]: r["ln"] for r in raw if r["m"] == "Spread"}; main_tot = next((r["ln"] for r in raw if r["m"] == "Total"), None)
    for (side, mk, pt, gg), v in sorted(fdgl.items(), key=lambda kv: (kv[0][1], str(kv[0][0]), kv[0][2] or 0)):
        if gg != g or mk not in ("Alt Spread", "Alt Total") or pt is None: continue
        if not (-ALT_ODDS_LIM <= v[0] <= ALT_ODDS_LIM): continue
        if mk == "Alt Spread" and side in main_sp and abs(pt - main_sp[side]) > ALT_SPREAD_WIN: continue
        if mk == "Alt Total" and main_tot is not None and abs(pt - main_tot) > ALT_TOTAL_WIN: continue
        if mk == "Alt Spread":
            if side not in (a, b) or ("Spread", side, pt) in main_pts: continue
            sgn = 1 if side == a else -1
            raw.append(dict(disp=f"{side} {pt:+g}", m="Spread", ms="Spread", side=side, tm=side, opp=(b if side == a else a), ln=pt, fd=v, co=None,
                            kind="M", ev=((-pt, None) if sgn == 1 else (None, pt)), alt=True))
        else:
            if side not in ("OVER", "UNDER") or ("Total", side, pt) in main_pts: continue
            raw.append(dict(disp=f"{side.title()} {pt:g}", m="Total", ms="Total", side=side, tm=a, opp=b, ln=pt, fd=v, co=None,
                            kind="T", ev=((pt, None) if side == "OVER" else (None, pt)), alt=True))
    # no-vig market chance from the two sides of each market
    for r in raw:
        r["o"] = r["fd"][0] if r["fd"] else r["co"]
    out = []
    for r in raw:
        if r["o"] is None: continue
        twin = [x for x in raw if x is not r and x["m"] == r["m"] and x["o"] is not None and bool(x.get("alt")) == bool(r.get("alt")) and (r["m"] != "Spread" or abs(x["ln"] + r["ln"]) < 1e-9) and (r["m"] != "Total" or x["ln"] == r["ln"])]
        bk = _imp(r["o"]); nv = bk / (bk + _imp(twin[0]["o"])) if twin else bk
        lo, hi = r["ev"]
        pm = _pint(lo, hi, marg if r["kind"] == "M" else tot, SD_MARGIN if r["kind"] == "M" else SD_TOTAL)
        ps_model = by_script(r["kind"], r["ev"], marg, tot)
        mix = sum(w[k] * ps_model[k] for k in range(4))
        p = SHRINK * mix + (1 - SHRINK) * nv
        scale = p / mix if mix > 0 else 1
        ps = [min(0.995, max(0.005, x * scale)) for x in ps_model]
        p = sum(w[k] * ps[k] for k in range(4))
        mkt_marg = None if sl is None else (sl if home == a else -sl)
        if r["m"] == "Total": gap = abs(tot - tl) if tl is not None else 0
        else: gap = abs(marg - mkt_marg) if mkt_marg is not None else 0
        risk = ""
        if gap >= GAP_FLAG:
            risk = (f"Model and market disagree by {gap:.1f} points on this game's {'total' if r['m'] == 'Total' else 'margin'} "
                    f"(model {'total ' + format(tot, '.1f') if r['m'] == 'Total' else a + ' by ' + format(marg, '+.1f')}, "
                    f"market {'total ' + format(tl, 'g') if r['m'] == 'Total' else a + ' by ' + format(mkt_marg, '+g')}). "
                    "The model's game projections have not been tested against closing lines yet, so this edge is unproven.")
        lab = [f"{a} by 10+", "close, low", "shootout", f"{b} by 10+"]
        why = (f"Model {a} {pa:.1f} - {b} {pb:.1f} (total {tot:.1f}). By ending: " + ", ".join(f"{lab[k]} {ps_model[k]*100:.0f}%" for k in range(4)) +
               f"; mixed with the script odds = {mix*100:.0f}%, then anchored halfway to the market's no-vig {nv*100:.0f}% (game projections not yet back-tested) = {p*100:.0f}%. " +
               ("FanDuel price." if r["fd"] else "Consensus market price from the schedule feed - add it on FanDuel by hand."))
        out.append(dict(disp=r["disp"], m=r["m"], ms=r["ms"], side=r["side"], tm=r["tm"], opp=r["opp"], ln=r["ln"], o=int(r["o"]), bk=bk, nv=nv,
                        pm=pm, mix=mix, ps=ps, p=p, fd=r["fd"], src="fd" if r["fd"] else "cons", gap=gap, risk=risk, why=why,
                        k="M" if r["kind"] == "M" else "T", alt=bool(r.get("alt"))))
    return out
