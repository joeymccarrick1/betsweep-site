#!/usr/bin/env python3
"""live_grade.py - grade the Live page's "from here" numbers (owner 11/4: "if the live plus-money TD calls grade well, that's a second product").

Inputs (all from the public `feeds` branch, written by .github/feeds.py every 10 minutes during games, plus the results feed):
  livelog.json            every in-progress game at every run: score, period, clock, possession, red zone, and the full box score
  livelegs_w<W>.json      the Live page's tracked legs with the pregame chance the page showed, pinned the first time week W had a game live
  in/results.json         'V2 - Boards Results Feed' projections block: the week's actual stats per player (Tuesday Step 1)

For every snapshot x tracked leg in that game that was still open, this recomputes the page's from-here chance with the same formulas
build_live.py ships in JavaScript (kept in sync by hand - change both), then grades it against the final stat:
  * calibration by from-here chance bucket and by quarter (mean chance vs hit rate, Brier) against the pregame chance as the baseline
  * "live calls": open legs whose from-here chance beats the PREGAME book implied chance by >= 5 pts in Q2-Q4 - the number a bettor would act
    on if FanDuel's live price had not moved (it has, so treat the hit rate as an upper bound until live prices are logged)
  * anytime TD calls separately, since that is the product idea
Output: research/live_grade_w<W>.txt (+ a one-line summary printed for the dev log). Nothing is written to the sheet or the site.

Usage: python3 live_grade.py [--week W]   (default: the week in in/results.json)
"""
import json, math, os, sys, subprocess, statistics, datetime, re
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); RES = os.path.join(HERE, "research"); os.makedirs(RES, exist_ok=True)
RAW = "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/"
SITE = os.environ.get("BS_SITE", "/home/claude/betsweep-site")
_fetched = {}
def fetch(name):
    """feeds-branch file: raw.githubusercontent.com when reachable, else `git fetch origin feeds` in the site clone (the sandbox can reach github.com only)."""
    try: return json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "30", RAW + name], stderr=subprocess.DEVNULL))
    except Exception: pass
    if not _fetched:
        subprocess.run(["git", "-C", SITE, "fetch", "-q", "origin", "feeds"], check=True); _fetched["ok"] = 1
    return json.loads(subprocess.check_output(["git", "-C", SITE, "show", f"FETCH_HEAD:{name}"], stderr=subprocess.DEVNULL))
def num(v):
    try: return float(str(v).replace(",", "").replace("%", ""))
    except Exception: return None
def norm(n): return re.sub(r"[^a-z]", "", str(n).lower().replace(" jr", "").replace(" sr", "").replace(" iii", "").replace(" ii", ""))
def phi(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def nppf(p):
    # Acklam's rational approximation (matches the page's nppf to ~1e-9)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    p = min(max(p, 1e-9), 1 - 1e-9); pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5; r = q*q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

def remaining_frac(snap):
    per = snap.get("period") or 1; m = str(snap.get("clock") or "0:00").split(":")
    secs = (num(m[0]) or 0) * 60 + (num(m[1]) if len(m) > 1 and num(m[1]) is not None else 0)
    if per > 4: return max(0.02, secs / 3600)
    return max(0.0, ((4 - per) * 900 + secs) / 3600)
def tilt(l, g, snap):
    if (snap.get("period") or 1) < 3: return 1
    m = (num(snap.get("hs")) or 0) - (num(snap.get("as")) or 0)   # home - away
    mine = m if l["tm"] == snap.get("home") else -m
    pas = l["m"] in ("Passing Yards", "Receiving Yards", "Receptions", "Longest Reception"); rush = l["m"] == "Rushing Yards"; td = l["m"] == "Anytime TD"
    if mine <= -7: return 1.12 if pas else 0.88 if rush else 1.04 if td else 1
    if mine >= 10: return 0.9 if pas else 1.12 if rush else 0.96 if td else 1
    return 1
def stat_for(m, b):
    return {"Passing Yards": b.get("pass"), "Rushing Yards": b.get("rush"), "Receiving Yards": b.get("recy"), "Receptions": b.get("rec"), "Anytime TD": b.get("td")}.get(m)
def from_here(l, snap, box):
    """Same shapes as build_live.py chanceNow(): returns (p, status)."""
    f = remaining_frac(snap)
    cur = stat_for(l["m"], box) if box is not None else None
    if l["m"] == "Anytime TD":
        if cur is not None and cur >= 1: return 1.0, "hit"
        lam = -math.log(1 - min(0.99, l["p"])) * tilt(l, None, snap); rz = bool(snap.get("rz")) and snap.get("poss") == l["tm"]
        return (min(0.97, 1 - math.exp(-lam * f) + (0.06 if rz else 0)) if f > 0 else 0.0), ("open" if f > 0 else "dead")
    if l["m"] not in ("Passing Yards", "Rushing Yards", "Receiving Yards", "Receptions"): return None, "skip"
    if cur is None: return l["p"], "open"
    L = l["ln"]
    if cur >= L: return 1.0, "hit"
    if f <= 0: return 0.0, "dead"
    mu = (l["proj"] if l.get("proj") is not None else L) * tilt(l, None, snap); z = nppf(1 - min(0.99, max(0.01, l["p"])))
    kmin = {"Passing Yards": 0.28, "Rushing Yards": 0.45, "Receptions": 0.35}.get(l["m"], 0.5)
    sig = abs((L - 0.5 - mu) / z) if abs(z) > 0.05 else 0; sig = min(max(sig, kmin * mu, 2), 1.2 * mu + 5)
    return 1 - phi((L - 0.5 - cur - mu * f) / (sig * math.sqrt(f))), "open"

def main():
    week = None
    if "--week" in sys.argv: week = int(sys.argv[sys.argv.index("--week") + 1])
    results = json.load(open(os.path.join(IN, "results.json")))
    rows = results.get("values") if isinstance(results, dict) else results
    H = {h: i for i, h in enumerate(rows[0])}
    graded = [r + [""] * (len(rows[0]) - len(r)) for r in rows[1:] if len(r) > H["Has Stat Row"] and str(r[H["Has Stat Row"]]).upper() == "TRUE"]
    if week is None:
        wks = [int(num(r[H["Week"]])) for r in graded if num(r[H["Week"]])]
        week = max(wks) if wks else None   # the latest graded week (the feed holds several)
    if week is None: sys.exit("live_grade: cannot tell the week; pass --week")
    ACT = {}
    for r in graded:
        if int(num(r[H["Week"]]) or 0) != week: continue
        td = sum(num(r[H[k]]) or 0 for k in ("Act Rush TD", "Act Rec TD"))
        ACT[norm(r[H["Player"]])] = {"Passing Yards": num(r[H["Act Pass Yds"]]), "Rushing Yards": num(r[H["Act Rush Yds"]]), "Receptions": num(r[H["Act Rec"]]),
                                     "Receiving Yards": num(r[H["Act Rec Yds"]]), "Anytime TD": td}
    try: legs = fetch(f"livelegs_w{week}.json")
    except Exception as e: sys.exit(f"live_grade: no pinned legs for week {week} on the feeds branch yet ({e}); nothing to grade")
    log = fetch("livelog.json").get("snaps", [])
    gids = {}
    for g in legs.get("games", []): gids[frozenset([g["a"], g["b"]])] = g["gid"]
    by_game = {}
    for l in legs["legs"]:
        if l.get("p") is None: continue
        by_game.setdefault(l["g"], []).append(l)
    obs = []   # one per snapshot x open leg
    for sn in log:
        gid = gids.get(frozenset([sn.get("home"), sn.get("away")]))
        if not gid or gid not in by_game: continue
        box = sn.get("box") or {}; boxn = {norm(k): v for k, v in box.items()}
        for l in by_game[gid]:
            act = ACT.get(norm(l["pl"]))
            if not act or act.get(l["m"]) is None: continue
            p, st = from_here(l, sn, boxn.get(norm(l["pl"])) if boxn else None)
            if st != "open" or p is None: continue
            hit = 1 if (act[l["m"]] >= 1 if l["m"] == "Anytime TD" else act[l["m"]] >= l["ln"]) else 0
            obs.append({"gid": gid, "pl": l["pl"], "m": l["m"], "ln": l["ln"], "o": l.get("o"), "pre": l["p"], "bk": l.get("bk"), "p": p, "per": sn.get("period") or 1,
                        "f": remaining_frac(sn), "hit": hit, "ts": sn["ts"]})
    if not obs: sys.exit(f"live_grade: week {week}: {len(log)} snapshots but no open tracked legs matched the results feed")
    out = [f"LIVE 'FROM HERE' GRADE - Week {week}  ({len(obs)} snapshot x leg observations, {len({o['gid'] for o in obs})} games, {len(log)} snapshots)",
           f"built {datetime.datetime.now():%Y-%m-%d %H:%M}; pregame legs pinned {legs.get('pinned', '?')}", ""]
    def brier(xs, key): return statistics.mean((o[key] - o["hit"]) ** 2 for o in xs) if xs else None
    def line(name, xs):
        if not xs: return f"{name:<34} -"
        return f"{name:<34} n={len(xs):>5}  from-here {100*statistics.mean(o['p'] for o in xs):5.1f}%  hit {100*statistics.mean(o['hit'] for o in xs):5.1f}%  Brier {brier(xs,'p'):.3f} (pregame {brier(xs,'pre'):.3f})"
    out.append("CALIBRATION (mean from-here chance vs actual hit rate; Brier lower is better, pregame chance as the baseline)")
    for lo, hi in ((0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)): out.append(line(f"  chance {int(lo*100)}-{int(min(hi,1)*100)}%", [o for o in obs if lo <= o["p"] < hi]))
    out.append("")
    for per in (1, 2, 3, 4): out.append(line(f"  quarter {per}", [o for o in obs if o["per"] == per]))
    out.append("")
    for m in ("Anytime TD", "Receiving Yards", "Receptions", "Rushing Yards", "Passing Yards"): out.append(line(f"  {m}", [o for o in obs if o["m"] == m]))
    out.append(""); out.append("LIVE CALLS - open legs in Q2-Q4 where from-here beats the PREGAME book implied chance by >= 5 pts (upper bound: FanDuel's live price moves too)")
    calls = [o for o in obs if o["bk"] and o["per"] >= 2 and o["p"] - o["bk"] >= 0.05 and o["f"] >= 0.08]
    out.append(line("  all markets", calls)); out.append(line("  anytime TD", [o for o in calls if o["m"] == "Anytime TD"]))
    out.append(line("  anytime TD, plus-money pregame", [o for o in calls if o["m"] == "Anytime TD" and (o["o"] or 0) >= 100]))
    out.append(line("  yards / receptions", [o for o in calls if o["m"] != "Anytime TD"]))
    # de-duplicated: one observation per leg per quarter (snapshots of the same leg are correlated)
    seen = {}; ded = []
    for o in sorted(calls, key=lambda o: o["ts"]):
        k = (o["pl"], o["m"], o["ln"], o["per"])
        if k in seen: continue
        seen[k] = 1; ded.append(o)
    out.append(line("  (first call per leg per quarter)", ded))
    tdc = [o for o in ded if o["m"] == "Anytime TD"]
    if tdc:
        out.append(""); out.append("  anytime TD calls, first per leg per quarter:")
        for o in sorted(tdc, key=lambda o: -o["p"])[:40]:
            out.append(f"    Q{o['per']} {o['pl']:<22} pregame {100*o['pre']:4.0f}% (FD {o['o']:+d}, implied {100*o['bk']:4.0f}%)  from here {100*o['p']:4.0f}%  -> {'HIT' if o['hit'] else 'miss'}")
    out.append(""); out.append("READ: a product needs the from-here hit rate to clear the book's LIVE price, which this log does not have. If the Q3-Q4 anytime TD")
    out.append("calls land near their from-here chance for 3+ weeks, the next step is logging FanDuel's live TD prices in the same feeds run and re-grading.")
    txt = "\n".join(out); fn = os.path.join(RES, f"live_grade_w{week}.txt"); open(fn, "w").write(txt); print(txt); print("\nwrote", fn)
    n_td = [o for o in ded if o["m"] == "Anytime TD"]
    print(f"\nDEVLOG: Live from-here grade W{week}: {len(obs)} obs, Brier {brier(obs,'p'):.3f} vs pregame {brier(obs,'pre'):.3f}; "
          f"TD calls {len(n_td)} first-per-quarter, hit {100*statistics.mean(o['hit'] for o in n_td) if n_td else 0:.0f}% vs from-here {100*statistics.mean(o['p'] for o in n_td) if n_td else 0:.0f}%")
if __name__ == "__main__": main()
