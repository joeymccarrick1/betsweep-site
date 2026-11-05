#!/usr/bin/env python3
"""gl_backtest.py - game-line backtest harness: market-as-prior + pre-kick adjustments, walk-forward by season.

Usage: python3 gl_backtest.py in/games.csv [--season 2026 --week 6]
Data: nflverse games.csv (closing spread_line / moneylines / total_line, rest days, div_game, roof, starting QBs).

What it answers:
  1. Is there any pre-kickoff signal that moves win probability beyond the closing moneyline? Candidates:
     rest edge, division game, road favourite, short-week, dome, QB change (starter differs from the team's previous game),
     recent SU/ATS form (last 3), favourite size. Each is fit as a logistic adjustment ON TOP of the market logit on seasons
     before the test season, then scored on the test season (Brier, log loss) against the market alone.
  2. Univariate upset rates: how often the favourite loses when each flag is on vs off (all seasons pooled).
  3. Post-mortem for one week (--season/--week): every game, the market's favourite, the result and the flags that were on.
Nothing here feeds the live pages until a season-level test beats the market two seasons running (promote-only-if-better).
"""
import csv, sys, math, collections
import numpy as np

def num(x):
    try: return float(x)
    except Exception: return None
def imp(o):
    o = num(o)
    if o is None or o == 0: return None
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)
def phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))
def logit(p): p = min(0.99, max(0.01, p)); return math.log(p / (1 - p))

path = sys.argv[1] if len(sys.argv) > 1 else "in/games.csv"
args = sys.argv[2:]; pm_season = int(args[args.index("--season") + 1]) if "--season" in args else None; pm_week = int(args[args.index("--week") + 1]) if "--week" in args else None
G = [g for g in csv.DictReader(open(path)) if g["game_type"] == "REG" and num(g["season"]) and num(g["season"]) >= 2020]
G.sort(key=lambda g: (int(g["season"]), int(g["week"]), g["gameday"], g["gametime"]))
# team form + QB continuity, built in order so nothing from the game itself leaks in
last_qb = {}; form = collections.defaultdict(list)   # team -> list of (su_win, ats_margin)
rows = []
for g in G:
    s, w = int(g["season"]), int(g["week"]); h, a = g["home_team"], g["away_team"]
    hs, as_ = num(g["home_score"]), num(g["away_score"]); sp = num(g["spread_line"]); tl = num(g["total_line"])
    ih, ia = imp(g["home_moneyline"]), imp(g["away_moneyline"])
    if ih is not None and ia is not None: p_mkt = ih / (ih + ia)
    elif sp is not None: p_mkt = phi(sp / 13.5)
    else: p_mkt = None
    def f3(t, i):
        xs = form[t][-3:]; return (sum(x[i] for x in xs) / len(xs)) if xs else 0.0
    qb_change_h = int(bool(last_qb.get((s, h))) and last_qb[(s, h)] != g["home_qb_id"]); qb_change_a = int(bool(last_qb.get((s, a))) and last_qb[(s, a)] != g["away_qb_id"])
    r = {"season": s, "week": w, "home": h, "away": a, "p_mkt": p_mkt, "sp": sp, "tl": tl, "hs": hs, "as": as_,
         "rest_edge": (num(g["home_rest"]) or 7) - (num(g["away_rest"]) or 7), "div": int(g["div_game"] == "1"), "dome": int(g["roof"] in ("dome", "closed")),
         "short_h": int((num(g["home_rest"]) or 7) <= 5), "short_a": int((num(g["away_rest"]) or 7) <= 5), "prime": int((g["gametime"] or "13:00") >= "19:30"),
         "road_fav": int(p_mkt is not None and p_mkt < 0.5), "big_fav": int(sp is not None and abs(sp) >= 7), "qb_change_h": qb_change_h, "qb_change_a": qb_change_a,
         "form_su_h": f3(h, 0), "form_su_a": f3(a, 0), "form_ats_h": f3(h, 1), "form_ats_a": f3(a, 1), "early": int(w <= 3),
         "qb_h": g["home_qb_name"], "qb_a": g["away_qb_name"], "ml_h": g["home_moneyline"], "ml_a": g["away_moneyline"]}
    rows.append(r)
    if hs is not None and as_ is not None:
        m = hs - as_
        form[h].append((int(m > 0), (m - (sp or 0)))); form[a].append((int(m < 0), (-(m) + (sp or 0))))
        if g["home_qb_id"]: last_qb[(s, h)] = g["home_qb_id"]
        if g["away_qb_id"]: last_qb[(s, a)] = g["away_qb_id"]
D = [r for r in rows if r["p_mkt"] is not None and r["hs"] is not None and r["hs"] != r["as"]]
for r in D: r["y"] = int(r["hs"] > r["as"]); r["fav_home"] = int(r["p_mkt"] >= 0.5); r["upset"] = int(r["y"] != r["fav_home"])

# ---- 1. walk-forward logistic adjustments on top of the market logit ----
FEATS = ["rest_edge", "div", "dome", "short_h", "short_a", "prime", "road_fav", "big_fav", "qb_change_h", "qb_change_a", "form_su_h", "form_su_a", "form_ats_h", "form_ats_a", "early"]
def X(rs, feats): return np.array([[1.0, logit(r["p_mkt"])] + [float(r[f]) for f in feats] for r in rs])
def fit(Xm, y, l2=1.0, it=50):
    b = np.zeros(Xm.shape[1]); b[1] = 1.0
    for _ in range(it):
        p = 1 / (1 + np.exp(-Xm @ b)); W = p * (1 - p)
        g = Xm.T @ (p - y) + l2 * np.r_[0, 0, b[2:]]; Hm = (Xm * W[:, None]).T @ Xm + l2 * np.diag(np.r_[0, 0, np.ones(len(b) - 2)])
        b -= np.linalg.solve(Hm, g)
    return b
def brier(p, y): return float(np.mean((p - y) ** 2))
def ll(p, y): p = np.clip(p, 1e-4, 1 - 1e-4); return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
seasons = sorted({r["season"] for r in D})
print("=== 1. market-as-prior + adjustments, walk-forward (train = earlier seasons) ===")
print(f"{'test':>5s} {'n':>4s} | {'Brier mkt':>9s} {'Brier adj':>9s} | {'LL mkt':>7s} {'LL adj':>7s} | {'fav SU%':>7s} | strongest adjustments (logit units per unit of feature)")
for s in seasons[2:]:
    tr = [r for r in D if r["season"] < s]; te = [r for r in D if r["season"] == s]
    if len(te) < 20: continue
    b = fit(X(tr, FEATS), np.array([r["y"] for r in tr]))
    pm = np.array([r["p_mkt"] for r in te]); y = np.array([r["y"] for r in te]); pa = 1 / (1 + np.exp(-(X(te, FEATS) @ b)))
    top = sorted(zip(FEATS, b[2:]), key=lambda kv: -abs(kv[1]))[:4]
    print(f"{s:>5d} {len(te):4d} | {brier(pm, y):9.4f} {brier(pa, y):9.4f} | {ll(pm, y):7.4f} {ll(pa, y):7.4f} | {np.mean([r['upset']==0 for r in te])*100:6.1f}% | " + ", ".join(f"{k} {v:+.2f}" for k, v in top))
print("market coefficient on its own logit (1.00 = take the price as is):", ", ".join(f"{s}: {fit(X([r for r in D if r['season'] < s], []), np.array([r['y'] for r in D if r['season'] < s]))[1]:.2f}" for s in seasons[2:]))

# ---- 2. univariate upset rates ----
print("\n=== 2. how often the favourite lost, flag on vs off (all seasons with lines) ===")
FLAGS = [("QB change, favourite", lambda r: (r["qb_change_h"] if r["fav_home"] else r["qb_change_a"])), ("QB change, underdog", lambda r: (r["qb_change_a"] if r["fav_home"] else r["qb_change_h"])),
         ("Division game", lambda r: r["div"]), ("Road favourite", lambda r: r["road_fav"]), ("Favourite on short week", lambda r: (r["short_h"] if r["fav_home"] else r["short_a"])),
         ("Underdog on short week", lambda r: (r["short_a"] if r["fav_home"] else r["short_h"])), ("Favourite rest edge >= 3 days", lambda r: int((r["rest_edge"] if r["fav_home"] else -r["rest_edge"]) >= 3)),
         ("Underdog rest edge >= 3 days", lambda r: int((-r["rest_edge"] if r["fav_home"] else r["rest_edge"]) >= 3)), ("Prime time", lambda r: r["prime"]), ("Dome", lambda r: r["dome"]),
         ("Favourite 0-3 SU last 3 (cold)", lambda r: int((r["form_su_h"] if r["fav_home"] else r["form_su_a"]) == 0)), ("Underdog 3-0 SU last 3 (hot)", lambda r: int((r["form_su_a"] if r["fav_home"] else r["form_su_h"]) == 1)),
         ("Favourite -7 or more", lambda r: r["big_fav"]), ("Weeks 1-3", lambda r: r["early"])]
base = np.mean([r["upset"] for r in D])
print(f"baseline upset rate {base*100:.1f}% over {len(D)} games; market-implied upset rate {np.mean([1-max(r['p_mkt'],1-r['p_mkt']) for r in D])*100:.1f}%")
print(f"{'flag':34s} {'n on':>5s} {'upset% on':>9s} {'upset% off':>10s} {'exp% on':>8s}   (exp = what the moneyline implied for those games)")
for name, f in FLAGS:
    on = [r for r in D if f(r)]; off = [r for r in D if not f(r)]
    if len(on) < 30: continue
    exp = np.mean([1 - max(r["p_mkt"], 1 - r["p_mkt"]) for r in on])
    print(f"{name:34s} {len(on):5d} {np.mean([r['upset'] for r in on])*100:8.1f}% {np.mean([r['upset'] for r in off])*100:9.1f}% {exp*100:7.1f}%")

# ---- 3. one-week post-mortem ----
if pm_season and pm_week:
    print(f"\n=== 3. post-mortem {pm_season} week {pm_week} ===")
    for r in [r for r in rows if r["season"] == pm_season and r["week"] == pm_week and r["hs"] is not None]:
        fav = r["home"] if (r["p_mkt"] or 0.5) >= 0.5 else r["away"]; dog = r["away"] if fav == r["home"] else r["home"]
        won = r["home"] if r["hs"] > r["as"] else r["away"] if r["as"] > r["hs"] else "tie"
        on = [n for n, f in FLAGS if r.get("p_mkt") is not None and f({**r, "fav_home": int((r["p_mkt"] or 0.5) >= 0.5)})]
        print(f"{r['away']} {int(r['as'])} @ {r['home']} {int(r['hs'])}  fav {fav} ({max(r['p_mkt'],1-r['p_mkt'])*100:.0f}%, spread {r['sp']:+.1f} home)  {'UPSET' if won not in (fav, 'tie') else 'held'}  "
              f"QBs {r['qb_a']} / {r['qb_h']}  rest {r['rest_edge']:+.0f}  form SU {r['form_su_a']:.2f}/{r['form_su_h']:.2f}  flags: {', '.join(on) or '-'}")
