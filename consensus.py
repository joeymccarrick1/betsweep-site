#!/usr/bin/env python3
"""consensus.py - "could the model be wrong here?" (owner 11/4 context desk, item 2).

Compares the model's weekly projection for every player with two outside projections mirrored on the `feeds` branch (projections.json,
.github/feeds.py, hourly): Sleeper's public weekly projections and ESPN's fantasy projections. Neither is ground truth - they are what the
market and most bettors are looking at - so a big gap is a question, not an answer: a stale input on our side (role, health, QB) or an edge.

Writes in/ctx_consensus.json:
  players: one note per player with a material gap - WATCH "Model disagrees with consensus" (ours far below) or INFO "Model above consensus"
           (ours far above), with the numbers; gap thresholds: pass yds 35, rush yds 18, rec yds 15, receptions 1.5, TD 0.25 (and >= 20% of ours)
  table:   every matched player's model vs Sleeper vs ESPN numbers, for the Tuesday grade (consensus_grade.py: who was right when we disagreed)
Usage: python3 consensus.py <WEEK>
"""
import json, os, re, subprocess, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
SITE = "/home/claude/betsweep-site"; RAW = "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/"
def nn(x):
    x = re.sub(r"[.'’]", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
def num(v):
    try: return float(str(v).replace(",", ""))
    except Exception: return None
def fetch(name):
    try: return json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "30", RAW + name], stderr=subprocess.DEVNULL))
    except Exception: pass
    subprocess.run(["git", "-C", SITE, "fetch", "-q", "origin", "feeds"], check=True)
    return json.loads(subprocess.check_output(["git", "-C", SITE, "show", f"FETCH_HEAD:{name}"], stderr=subprocess.DEVNULL))
def vals(n):
    p = os.path.join(IN, n)
    if not os.path.exists(p): return []
    d = json.load(open(p)); return d.get("values", d) if isinstance(d, dict) else d
STATS = ("pass_yd", "rush_yd", "rec_yd", "rec", "pass_td", "rush_td", "rec_td")
LABEL = {"pass_yd": "pass yds", "rush_yd": "rush yds", "rec_yd": "rec yds", "rec": "receptions", "pass_td": "pass TD", "rush_td": "rush TD", "rec_td": "rec TD"}
THR = {"pass_yd": 35, "rush_yd": 18, "rec_yd": 15, "rec": 1.5, "pass_td": 0.5, "rush_td": 0.25, "rec_td": 0.25}
ESPN_ID = {"3": "pass_yd", "4": "pass_td", "24": "rush_yd", "25": "rush_td", "42": "rec_yd", "43": "rec_td", "53": "rec"}

def model_rows():
    M = {}
    for f, pos, cols in (("proj_qb.json", "QB", None), ("proj_rb.json", "RB", None), ("proj_wr.json", "WR", None), ("proj_te.json", "TE", None)):
        rows = vals(f)
        if not rows: continue
        H = {c: i for i, c in enumerate(rows[0])}
        def g(r, c):
            i = H.get(c); return num(r[i]) if i is not None and i < len(r) else None
        for r in rows[1:]:
            if not r or not r[0]: continue
            M[nn(r[0])] = {"name": r[0], "team": r[1] if len(r) > 1 else "", "pos": pos,
                           "pass_yd": g(r, "Proj Pass Yds"), "pass_td": g(r, "Proj Pass TD"), "rush_yd": g(r, "Proj Rush Yds"), "rush_td": g(r, "Proj Rush TD"),
                           "rec_yd": g(r, "Proj Rec Yds"), "rec_td": g(r, "Proj Rec TD"), "rec": g(r, "Proj Rec") if "Proj Rec" in H else g(r, "Projected Receptions (Audit)"),
                           "fp": g(r, "Proj Fantasy Pts"), "active": ("NO" if ("Effective Weekly Role" in H and H["Effective Weekly Role"] < len(r) and r[H["Effective Weekly Role"]] in ("OUT", "DEPTH / CONTEXT")) else (r[H["Weekly Active"]] if "Weekly Active" in H and H["Weekly Active"] < len(r) else "YES"))}
    return M
def parse_sleeper(sl):
    out = {}
    for p in sl or []:
        pl = p.get("player") or {}; st = p.get("stats") or {}
        name = f"{pl.get('first_name', '')} {pl.get('last_name', '')}".strip()
        if not name or pl.get("position") not in ("QB", "RB", "WR", "TE"): continue
        out[nn(name)] = {k: num(st.get(k)) for k in STATS} | {"fp": num(st.get("pts_ppr")), "team": pl.get("team")}
    return out
def parse_espn(es, week):
    out = {}
    for p in es or []:
        pl = p.get("player") or p; name = pl.get("fullName")
        if not name: continue
        proj = None
        for s in pl.get("stats") or []:
            if s.get("statSourceId") == 1 and s.get("statSplitTypeId") == 1 and (week is None or s.get("scoringPeriodId") == week): proj = s.get("stats") or {}
        if proj is None: continue
        rec = {v: num(proj.get(k)) for k, v in ESPN_ID.items()}
        rec["fp"] = num(next((s.get("appliedTotal") for s in pl.get("stats") or [] if s.get("statSourceId") == 1 and s.get("statSplitTypeId") == 1), None))
        out[nn(name)] = rec
    return out
def main(week):
    week = int(week); now = dt.datetime.now()
    PJ = fetch("projections.json"); M = model_rows()
    SL = parse_sleeper(PJ.get("sleeper")); ES = parse_espn(PJ.get("espn"), PJ.get("week") or week)
    if PJ.get("week") and int(PJ["week"]) != week: print(f"consensus: feeds projections are for week {PJ['week']}, not {week} - skipping"); return
    notes = []; table = []
    for k, m in M.items():
        if str(m.get("active", "YES")).upper() == "NO": continue
        s, e = SL.get(k), ES.get(k)
        if not s and not e: continue
        row = {"player": m["name"], "team": m["team"], "pos": m["pos"], "model": {x: m.get(x) for x in STATS + ("fp",)}, "sleeper": {x: (s or {}).get(x) for x in STATS + ("fp",)}, "espn": {x: (e or {}).get(x) for x in STATS + ("fp",)}}
        table.append(row)
        gaps = []
        for x in STATS:
            mv = m.get(x); cs = [v[x] for v in (s, e) if v and v.get(x) is not None]
            if mv is None or not cs: continue
            c = sum(cs) / len(cs)
            if c < 1 and mv < 1 and x.endswith("_yd"): continue
            d = mv - c
            if abs(d) >= THR[x] and abs(d) >= 0.2 * max(abs(c), 1e-9): gaps.append((x, mv, c, d, len(cs)))
        if not gaps: continue
        big = max(gaps, key=lambda g: abs(g[3]) / THR[g[0]])
        parts = [f"{LABEL[x]} {mv:.1f} vs {c:.1f} consensus" for x, mv, c, d, n in sorted(gaps, key=lambda g: -abs(g[3]) / THR[g[0]])[:3]]
        srcs = " + ".join(w for w, v in (("Sleeper", s), ("ESPN", e)) if v)
        if big[3] < 0:
            notes.append({"player": m["name"], "team": m["team"], "pos": m["pos"], "k": "watch", "tag": "Model disagrees with consensus",
                          "txt": f"Our projection is well below {srcs}: " + "; ".join(parts) + ". Either we are missing news (role, health, a new QB) or the market is paying for a name - check before trusting the under / fading him."})
        else:
            notes.append({"player": m["name"], "team": m["team"], "pos": m["pos"], "k": "info", "tag": "Model above consensus",
                          "txt": f"Our projection is well above {srcs}: " + "; ".join(parts) + ". Our edge if the role read is right; the graded record of these disagreements is on the Tuesday receipt."})
    json.dump({"week": week, "built": now.isoformat(), "players": notes, "games": {}, "sources": {"sleeper": len(SL), "espn": len(ES), "mirrored": PJ.get("mirrored")}}, open(os.path.join(IN, "ctx_consensus.json"), "w"), indent=1)
    json.dump({"week": week, "built": now.isoformat(), "rows": table}, open(os.path.join(OUT, f"consensus_w{week}.json"), "w"))
    print(f"consensus week {week}: Sleeper {len(SL)} / ESPN {len(ES)} players, {len(table)} matched, {len(notes)} notes ({sum(1 for n in notes if n['k']=='watch')} below, {sum(1 for n in notes if n['k']=='info')} above)")
    for n in sorted(notes, key=lambda n: n["k"])[:40]: print(f"  [{n['tag']}] {n['player']} ({n['team']} {n['pos']}): {n['txt'][:140]}")
if __name__ == "__main__": main(sys.argv[1] if len(sys.argv) > 1 else 9)
