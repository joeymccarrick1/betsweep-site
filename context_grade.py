#!/usr/bin/env python3
"""context_grade.py - Tuesday grade for the context desk (owner 11/4): did the disagreements and the hype mean anything?

  1. Consensus: for every player where the model and the Sleeper/ESPN consensus disagreed by the consensus.py thresholds, who was closer to the
     actual (per stat)? Reported by direction (we were below / above) and by stat. If "we were below" keeps losing, our under-projections are stale
     inputs, not edges; if it keeps winning, the market is paying for names.
  2. Trending: the week's top-20 most-mentioned players (trending_w<W>.json) - did their graded FanDuel legs (results_legs.json) hit below implied?
     The fade hypothesis from the deep dig. Needs 2+ weeks before anything changes on the site.
Inputs: <site clone>/data/consensus-w<W>.json and trending-w<W>.json (kept by build_site.py), in/results.json (actuals), in/results_legs.json.
Usage: python3 context_grade.py <GRADED WEEK>   -> prints the block for the dev-log row; writes research/context_grade_w<W>.txt
"""
import json, os, re, sys, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); RES = os.path.join(HERE, "research"); os.makedirs(RES, exist_ok=True)
SITE = "/home/claude/betsweep-site"
def nn(x):
    x = re.sub(r"[.'’]", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
def num(v):
    try: return float(str(v).replace(",", "").replace("%", ""))
    except Exception: return None
def vals(n):
    p = os.path.join(IN, n)
    if not os.path.exists(p): return []
    d = json.load(open(p)); return d.get("values", d) if isinstance(d, dict) else d
THR = {"pass_yd": 35, "rush_yd": 18, "rec_yd": 15, "rec": 1.5, "pass_td": 0.5, "rush_td": 0.25, "rec_td": 0.25}
ACTCOL = {"pass_yd": "Act Pass Yds", "rush_yd": "Act Rush Yds", "rec_yd": "Act Rec Yds", "rec": "Act Rec", "pass_td": "Act Pass TD", "rush_td": "Act Rush TD", "rec_td": "Act Rec TD"}
def main(week):
    week = int(week); out = [f"CONTEXT DESK GRADE - Week {week}", ""]
    rows = vals("results.json"); H = {h: i for i, h in enumerate(rows[0])} if rows else {}
    ACT = {}
    for r in rows[1:]:
        r = r + [""] * (len(rows[0]) - len(r))
        if int(num(r[H["Week"]]) or 0) != week or str(r[H["Has Stat Row"]]).upper() != "TRUE": continue
        ACT[nn(r[H["Player"]])] = {k: num(r[H[c]]) for k, c in ACTCOL.items()}
    # 1. consensus
    try: C = json.load(open(os.path.join(SITE, "data", f"consensus-w{week}.json")))["rows"]
    except Exception as e: C = []; out.append(f"consensus: no table for week {week} ({e})")
    res = {"below": {"model": 0, "consensus": 0}, "above": {"model": 0, "consensus": 0}}; bystat = {}
    for r in C:
        a = ACT.get(nn(r["player"]))
        if not a: continue
        for x, thr in THR.items():
            mv = (r["model"] or {}).get(x); cs = [v for v in ((r.get("sleeper") or {}).get(x), (r.get("espn") or {}).get(x)) if v is not None]
            if mv is None or not cs or a.get(x) is None: continue
            c = sum(cs) / len(cs); d = mv - c
            if abs(d) < thr or abs(d) < 0.2 * max(abs(c), 1e-9): continue
            side = "below" if d < 0 else "above"; win = "model" if abs(mv - a[x]) < abs(c - a[x]) else "consensus"
            res[side][win] += 1; bystat.setdefault(x, {"model": 0, "consensus": 0})[win] += 1
    if C:
        out.append("CONSENSUS DISAGREEMENTS (who was closer to the actual):")
        for side in ("below", "above"):
            n = res[side]["model"] + res[side]["consensus"]
            out.append(f"  model {side} consensus: n={n}  model closer {res[side]['model']}  consensus closer {res[side]['consensus']}" + (f"  ({100*res[side]['model']/n:.0f}% us)" if n else ""))
        for x, v in sorted(bystat.items()): out.append(f"    {x:<8} model {v['model']:>3}  consensus {v['consensus']:>3}")
        out.append("  READ: 'below' calls losing week after week = stale inputs on our side (role / health / QB) -> the news desk should have caught them.")
    # 2. trending fade test
    try: T = json.load(open(os.path.join(SITE, "data", f"trending-w{week}.json")))["top"]
    except Exception as e: T = []; out.append(f"trending: no list for week {week} ({e})")
    L = vals("results_legs.json")
    if T and L:
        LH = {h: i for i, h in enumerate(L[0])}; top = {nn(t["player"]) for t in T}
        def pct(v): return None if v is None else (v / 100 if v > 1.5 else v)
        g = {"trend": [], "rest": []}
        for r in L[1:]:
            r = r + [""] * (len(L[0]) - len(r)); resv = str(r[LH.get("Result", 0)]).upper()
            if resv not in ("HIT", "MISS"): continue
            bk = pct(num(r[LH["Book implied %"]])) if "Book implied %" in LH else None
            if bk is None: continue
            g["trend" if nn(r[LH["Player"]]) in top else "rest"].append((1 if resv == "HIT" else 0, bk))
        out.append(""); out.append("TRENDING (top-20 most-mentioned players Wed-Sun) - graded FanDuel legs, hit rate vs implied:")
        for k, xs in g.items():
            if xs: out.append(f"  {k:<6} n={len(xs):>4}  hit {100*statistics.mean(x[0] for x in xs):5.1f}%  implied {100*statistics.mean(x[1] for x in xs):5.1f}%  -> {100*(statistics.mean(x[0] for x in xs)-statistics.mean(x[1] for x in xs)):+.1f} pts")
        out.append("  READ: trending legs under implied by 3+ pts for two graded weeks -> 'Trending' becomes a watch flag and an under-side nudge.")
    txt = "\n".join(out); open(os.path.join(RES, f"context_grade_w{week}.txt"), "w").write(txt); print(txt)
if __name__ == "__main__": main(sys.argv[1] if len(sys.argv) > 1 else 9)
