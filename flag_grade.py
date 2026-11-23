"""Grade the builder's risk flags against what happened (owner 11/15: "Do all of these", idea 1).

Reads published builder boards (build/data-<hash>.js from the site's history, saved by hand into a folder) and the game log, grades
every player leg, and reports for each flag tag: legs, hit rate, the fair rate FanDuel's price implied (implied / 1.045), and units won
per leg at the posted price. Also grades the risk-score buckets. Usage: python3 flag_grade.py <folder of data-*.js> [out.json]

Getting the boards (one per week, the last build before Sunday's first kickoff):
    git clone --filter=blob:none --no-checkout <site repo> hist && cd hist
    c=$(git rev-list -1 --before="2026-11-15 18:00 +0000" origin/main)
    git show $c:$(git ls-tree -r --name-only $c | grep '^build/data-' | head -1) > ../boards/w10.js
From 11/23 the site repository's history starts at a snapshot (RUNBOOK, "the site repository's size"). A build from before a snapshot is in
the private archive instead: clone https://github.com/joeymccarrick1/betsweep-site-archive with --branch archive/<day>/main and use that
branch in place of origin/main (Week 11: archive/2026-11-23/main).
Run it on Tuesdays once the game log has the week. A tag earns a weight in sweep.TAG_W only when it points the same way in every week
graded and has 100+ player-weeks; two weeks of anything else is noise.
"""
import json, sys, os, glob, re, collections, math

STAT = {"Receiving Yards": "Rec Yds", "Receptions": "Receptions", "Rushing Yards": "Rush Yds", "Passing Yards": "Pass Yds", "Longest Reception": "Longest Rec"}
def num(x):
    try: return float(x)
    except Exception: return None

def load_log(path):
    v = json.load(open(path))["values"]; H = {c: i for i, c in enumerate(v[0])}; out = {}
    for r in v[1:]:
        r = r + [""] * (len(v[0]) - len(r))
        try: w = int(float(r[H["Week"]]))
        except Exception: continue
        out[(w, r[H["Player"]].strip().lower())] = {c: num(r[i]) for c, i in H.items()}
    return out

def grade(l, row):
    m = str(l.get("m", "")); under = m.startswith("Under "); base = m[6:] if under else m; ln = l.get("ln")
    if base in STAT: x = row.get(STAT[base])
    elif base == "Anytime TD": x = (row.get("Rush TD") or 0) + (row.get("Rec TD") or 0)
    elif base == "Rush + Rec Yards": x = (row.get("Rush Yds") or 0) + (row.get("Rec Yds") or 0)
    else: return None
    if x is None or ln is None: return None
    return (x < ln) if under else (x >= ln)

def run(folder, logpath):
    log = load_log(logpath); rows = []
    for f in sorted(glob.glob(os.path.join(folder, "*.js"))):
        t = open(f, encoding="utf-8").read(); d = json.loads(t[t.index("{"):t.rindex("}") + 1]); w = int(d["week"]); pf = d.get("pf") or {}
        played = {p for (wk, p) in log if wk == w}
        if not played: continue
        for l in d["legs"]:
            if l.get("gl") or l.get("o") is None or not l.get("pl"): continue
            row = log.get((w, l["pl"].strip().lower()))
            if row is None: continue          # did not play / no stat row: sportsbooks void these
            hit = grade(l, row)
            if hit is None: continue
            fl = list(l.get("fh") or []) + list(pf.get(l["pl"]) or [])
            o = l["o"]; imp = (-o / (-o + 100.0)) if o < 0 else 100.0 / (o + 100.0)
            rows.append({"w": w, "f": os.path.basename(f), "pl": l["pl"], "m": l["m"], "ln": l["ln"], "o": o, "imp": imp, "p": l.get("p"), "hit": bool(hit),
                         "tags": sorted({(x[0], x[1]) for x in fl if isinstance(x, list) and len(x) > 1}), "under": str(l["m"]).startswith("Under ")})
    return rows

def summ(rs):
    n = len(rs)
    if not n: return None
    h = sum(r["hit"] for r in rs); fair = sum(r["imp"] / 1.045 for r in rs) / n
    u = sum(((100.0 / -r["o"]) if r["o"] < 0 else r["o"] / 100.0) if r["hit"] else -1 for r in rs) / n
    # a player's ladder is many rungs of one game, so the honest count is player-weeks: mean (hit - fair) per player-week, t across them
    c = collections.defaultdict(list)
    for r in rs: c[(r["w"], r["pl"])].append(r["hit"] - r["imp"] / 1.045)
    m = [sum(v) / len(v) for v in c.values()]; mu = sum(m) / len(m); sd = math.sqrt(sum((x - mu) ** 2 for x in m) / len(m)) if len(m) > 1 else 0
    return {"n": n, "players": len(m), "hit": round(h / n, 4), "fair": round(fair, 4), "diff": round(mu, 4), "t": round(mu / (sd / math.sqrt(len(m))), 2) if sd else 0.0, "units": round(u, 4)}

if __name__ == "__main__":
    folder = sys.argv[1]; rows = run(folder, os.path.join(os.path.dirname(os.path.abspath(__file__)), "in", "gamelog.json"))
    # one board per week: the latest file name seen for that week wins (caller passes one board per week)
    overs = [r for r in rows if not r["under"]]
    out = {"weeks": sorted({r["w"] for r in rows}), "all_overs": summ(overs), "tags": {}, "score": {}}
    by = collections.defaultdict(list)
    for r in overs:
        for k, t in r["tags"]: by[(k, t)].append(r)
    for (k, t), rs in sorted(by.items(), key=lambda x: -len(x[1])):
        s = summ(rs); s["kind"] = k; s["by_week"] = {w: summ([r for r in rs if r["w"] == w])["diff"] for w in sorted({r["w"] for r in rs})}; out["tags"][t + "|" + k] = s
    W = {"bad": 3, "watch": 1, "good": -1}
    def sc(r): return max(0, sum(W.get(k, 0) for k, _ in r["tags"]))
    for name, lo, hi in (("0 (low)", 0, 0), ("1 (low)", 1, 1), ("2-3 (some)", 2, 3), ("4+ (high)", 4, 99)):
        out["score"][name] = summ([r for r in overs if lo <= sc(r) <= hi])
    floor = [r for r in overs if r["o"] <= -180]
    out["floor"] = {name: summ([r for r in floor if lo <= sc(r) <= hi]) for name, lo, hi in (("low", 0, 1), ("some", 2, 3), ("high", 4, 99))}
    out["floor_gap"] = {"model 8+ pts above FanDuel": summ([r for r in floor if r["p"] is not None and r["p"] - r["imp"] / 1.045 >= 0.08]), "rest": summ([r for r in floor if r["p"] is None or r["p"] - r["imp"] / 1.045 < 0.08])}
    if len(sys.argv) > 2: json.dump(out, open(sys.argv[2], "w"), indent=1)
    print("weeks", out["weeks"], "all overs", out["all_overs"])
    print("score buckets:"); [print("  ", k, v) for k, v in out["score"].items()]
    print("floor legs (-180 or shorter):"); [print("  ", k, v) for k, v in out["floor"].items()]; [print("  ", k, v) for k, v in out["floor_gap"].items()]
    print("tags (overs, 25+ player-weeks):")
    for k, v in out["tags"].items():
        if v["players"] >= 25: print(f'  {k:42s} legs={v["n"]:5d} player-weeks={v["players"]:4d} hit={v["hit"]:.3f} fair={v["fair"]:.3f} diff={v["diff"]:+.3f} t={v["t"]:+.1f} units={v["units"]:+.3f} wk={v["by_week"]}')
