"""Results-trained picks - a SHADOW list (owner 11/15: "the goal is to have picks that win so do everything you can think of").

Instead of hand-set rules, a small logistic model is fitted on every graded FanDuel leg we have (in/legsnaps.json, about 1,600 new
legs a week). It starts from FanDuel's own price and learns what moves a leg away from it:

    market, price band (floor / plus money), how far our model sits above or below the price (separately for floor legs),
    whether the model's most likely ending has his team winning or losing by 10+, and how often he has finished near zero.

First test, 11/15 (Weeks 6-9, each week scored with a fit on the other three): legs where this chance beat FanDuel's price returned
+6.2% a leg (698 legs); legs where our model's own chance beat the price returned -4.9% (1,633 legs). As a forecast it only matches
the price (error 0.2350 vs 0.2351), and the features were chosen while looking at the same four weeks - so this is a lead, not proof.
That is why it is a shadow list: it is written to data/learned-w<week>-<mmdd>.json on every build, graded every Tuesday against results
and the closing price, and drives nothing on the site until the owner says so.

    python3 learned.py           refit on in/ and print the coefficients and the leave-one-week-out check
"""
import json, os, math, datetime
import numpy as np
import honest

MK = ["Receiving Yards", "Receptions", "Rushing Yards", "Passing Yards", "Longest Reception", "Anytime TD"]
STAT = {"Receiving Yards": "Rec Yds", "Receptions": "Receptions", "Rushing Yards": "Rush Yds", "Passing Yards": "Pass Yds", "Longest Reception": "Longest Rec"}
NAMES = ["base", "FanDuel price"] + MK[1:] + ["floor (-200 or shorter)", "plus money", "model above (not floor)", "model above (floor)", "model below", "projected to lose big", "projected to win big", "near-zero rate", "near-zero rate on a floor"]
LAM = 3.3; MIN_EDGE = 0.03

def feats(fair, market, odds, model, lose, win, nz):
    fair = min(0.97, max(0.03, fair)); gap = (model - fair) if model is not None else 0.0; floor = 1.0 if odds <= -200 else 0.0
    return [1.0, math.log(fair / (1 - fair))] + [1.0 if market == m else 0.0 for m in MK[1:]] + [floor, 1.0 if odds > 115 else 0.0, max(0.0, gap) * (1 - floor), max(0.0, gap) * floor, min(0.0, gap), float(lose), float(win), float(nz), float(nz) * floor]

def _num(x):
    try: return float(str(x).replace("%", "").replace("+", ""))
    except Exception: return None

def training(IN="in"):
    """(X, y, weeks) from the graded leg snapshots, with each leg's side-of-game and near-zero rate as they stood before that week."""
    v = json.load(open(os.path.join(IN, "legsnaps.json")))["values"]; H = {c: i for i, c in enumerate(v[0])}
    g = json.load(open(os.path.join(IN, "gamelog.json")))["values"]; G = {c: i for i, c in enumerate(g[0])}
    log = {}
    for r in g[1:]:
        r = list(r) + [""] * (len(g[0]) - len(r))
        try: log.setdefault(r[G["Player"]].strip().lower(), []).append((int(float(r[G["Week"]])), r))
        except Exception: pass
    most = {}
    try:
        c = json.load(open(os.path.join(IN, "calls.json")))["values"]; C = {k: i for i, k in enumerate(c[0])}
        for r in c[1:]:
            r = list(r) + [""] * (len(c[0]) - len(r))
            try: most[(int(float(r[0])), frozenset((r[C["A"]], r[C["B"]])))] = r[C["Most likely"]]   # rows are in time order: the last snapshot wins
            except Exception: pass
    except Exception: pass
    X, y, W = [], [], []
    for r in v[1:]:
        r = list(r) + [""] * (len(v[0]) - len(r))
        if r[H["Latest Snapshot"]] != "TRUE" or r[H["Result"]] not in ("HIT", "MISS") or r[H["Market"]] not in MK: continue
        o = _num(r[H["FanDuel odds"]]); w = _num(r[0]); ln = _num(r[H["Line (X+)"]]); mp = _num(r[H["Model % (hist-adj)"]])
        if not o or w is None or mp is None: continue
        w = int(w); mp = mp / 100 if mp > 1 else mp; tm, opp, m = r[H["Team"]], r[H["Opp"]], r[H["Market"]]
        ml = most.get((w, frozenset((tm, opp))), ""); nz = 0.0
        if m in STAT and ln:
            pr = [(_num(x[G[STAT[m]]]) or 0) for wk, x in log.get(r[H["Player"]].strip().lower(), []) if wk < w]
            if len(pr) >= 4: nz = sum(1 for p in pr if p < 0.5 * ln) / len(pr)
        X.append(feats(honest.implied(o) / honest.VIG, m, o, mp, ml == f"{opp} by 10+", ml == f"{tm} by 10+", nz)); y.append(1.0 if r[H["Result"]] == "HIT" else 0.0); W.append(w)
    return np.array(X, float), np.array(y, float), np.array(W, int)

def fit(X, y, lam=LAM, iters=40):
    """Ridge logistic regression by Newton steps (no penalty on the base term)."""
    b = np.zeros(X.shape[1]); R = lam * np.eye(X.shape[1]); R[0, 0] = 0.0
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ b, -30, 30))); Wt = p * (1 - p) + 1e-9
        step = np.linalg.solve((X.T * Wt) @ X + R, X.T @ (y - p) - R @ b); b += step
        if np.abs(step).max() < 1e-8: break
    return b

def predict(b, x): return float(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, float(np.dot(b, x)))))))

def picks(IN, legs, games, week, out_dir=None, risk_of=None, now=None):
    """Score the current board. legs = builder legs (pl, tm, opp, g, m, ln, o, p / raw_p, nzr = near-zero rate); games = builder games (gid, most).
    Returns the dict it wrote: singles (one per player, learned chance 3+ points over the price) and two-leg pairs from different games."""
    X, y, W = training(IN)
    if len(y) < 1500: return {"note": f"only {len(y)} graded legs - no fit", "singles": [], "pairs": []}
    b = fit(X, y); most = {g["gid"]: g.get("most") for g in games}; best = {}
    for l in legs:
        if l.get("gl") or l.get("o") is None or l.get("m") not in MK or not l.get("pl"): continue
        mp = l.get("raw_p") if l.get("raw_p") is not None else l.get("p")
        if mp is None: continue
        ml = most.get(l.get("g")) or ""; imp = honest.implied(l["o"])
        p = predict(b, feats(imp / honest.VIG, l["m"], l["o"], mp, ml == f'{l.get("opp")} by 10+', ml == f'{l.get("tm")} by 10+', l.get("nzr") or 0.0))
        e = p - imp
        if e < MIN_EDGE: continue
        row = {"pl": l["pl"], "tm": l.get("tm"), "opp": l.get("opp"), "g": l.get("g"), "m": l["m"], "ln": l.get("ln"), "o": l["o"], "fd": round(imp, 4), "model": round(mp, 4), "learned": round(p, 4), "edge": round(e, 4),
               "risk": (risk_of(l) if risk_of else None)}
        if l["pl"] not in best or e > best[l["pl"]]["edge"]: best[l["pl"]] = row
    singles = sorted(best.values(), key=lambda r: -r["edge"])[:40]; pairs = []
    top = singles[:14]
    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            if top[i]["g"] == top[j]["g"]: continue
            d = lambda o: 1 + (o / 100.0 if o > 0 else 100.0 / -o); dd = d(top[i]["o"]) * d(top[j]["o"])
            pairs.append({"legs": [f'{top[i]["pl"]}|{top[i]["m"]}|{top[i]["ln"]:g}', f'{top[j]["pl"]}|{top[j]["m"]}|{top[j]["ln"]:g}'], "price": round((dd - 1) * 100), "learned": round(top[i]["learned"] * top[j]["learned"], 4),
                          "ev": round(top[i]["learned"] * top[j]["learned"] * dd - 1, 4)})
    pairs = sorted(pairs, key=lambda r: -r["ev"])[:10]
    now = now or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-6)))
    out = {"week": week, "built": now.strftime("%Y-%m-%d %H:%M CT"), "shadow": True, "trained_on": int(len(y)), "weeks": sorted(int(w) for w in set(W.tolist())),
           "coef": {n: round(float(c), 3) for n, c in zip(NAMES, b)}, "singles": singles, "pairs": pairs}
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        json.dump(out, open(os.path.join(out_dir, f"learned-w{week}-{now.strftime('%m%d')}.json"), "w"), separators=(",", ":"))
    return out

if __name__ == "__main__":
    IN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "in"); X, y, W = training(IN)
    print(f"graded legs {len(y)}, weeks {sorted(set(W.tolist()))}")
    P = np.zeros(len(y))
    for w in sorted(set(W.tolist())):
        b = fit(X[W != w], y[W != w]); P[W == w] = 1 / (1 + np.exp(-(X[W == w] @ b)))
    fair = 1 / (1 + np.exp(-X[:, 1])); print(f"leave one week out, forecast error: FanDuel no-vig {np.mean((fair - y) ** 2):.4f} | learned {np.mean((P - y) ** 2):.4f}")
    b = fit(X, y); print("coefficients:", ", ".join(f"{n} {c:+.2f}" for n, c in zip(NAMES, b)))
