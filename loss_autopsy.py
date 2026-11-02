"""Why each losing leg lost (owner 11/1: "tag every losing promo and imported slip leg ... so the Tuesday report says '4 of 9 losses were injuries
we could have seen'"). RUNBOOK Step 5 (Tuesdays), after grading.

  python3 loss_autopsy.py <WEEK> [legs.json]

Inputs (in/): legsnaps.json ('V2 - FanDuel Leg Snapshots', graded), gamelog.json, snap_counts_2026.csv, games.csv (final scores),
weather.json, avail.json; out/promos.json (promo legs) when present. Imported FanDuel slips live in Supabase and are not reachable from
the rebuild, so they are not tagged here.

Every MISS leg (Latest Snapshot rows) gets ONE tag, first match wins:
  INJURY    played under 60% of his season snap share (left the game / limited) - or was on the availability tab as QUESTIONABLE / OUT
  WEATHER   passing / receiving leg in a game the weather tab rated HIGH at kickoff
  SCRIPT    passing / receiving leg for a team that won by 14+ (ran the clock), or a rushing leg for a team that lost by 14+ (abandoned the run)
  ROLE      healthy and no lopsided script, but his volume for this stat (pass attempts / carries / targets; touches for TDs) was under 70% of his season average
  NEAR MISS within 15% of the line (yards / receptions), or 1 short on a count
  VARIANCE  none of the above - the volume was there and it did not land
"Could have seen" = INJURY legs whose player was QUESTIONABLE / OUT on the availability tab, or carried a 'Playing hurt' / 'Playing through it' /
BetSweep-note flag, plus WEATHER legs (the forecast was in hand).
Writes out/autopsy.json and prints one summary line per group (all graded legs, promo legs).
"""
import csv, json, os, sys, re
from collections import Counter, defaultdict

IN, OUT = "in", "out"
def vals(n):
    p = os.path.join(IN, n)
    if not os.path.exists(p): return []
    d = json.load(open(p)); return d.get("values", d) if isinstance(d, dict) else d
def num(x):
    try: return float(str(x).replace(",", ""))
    except Exception: return None
def nn(x):
    x = re.sub(r"\.", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
TEAMFIX = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
PASSREC = ("Passing Yards", "Receiving Yards", "Receptions", "Longest Reception", "Rush + Rec Yards")

def main(W, legs_path=None):
    W = int(W)
    L = json.load(open(legs_path))["values"] if legs_path else vals("legsnaps.json")
    H = {c: i for i, c in enumerate(L[0])}; c = lambda r, k: r[H[k]] if H.get(k) is not None and H[k] < len(r) else ""
    legs = [r for r in L[1:] if str(c(r, "Week")) == str(W) and str(c(r, "Latest Snapshot")).upper() == "TRUE" and c(r, "Result") in ("HIT", "MISS")]
    # game log: this week's line and season-before averages
    G = vals("gamelog.json"); GH = {k: i for i, k in enumerate(G[0])} if G else {}
    g = lambda r, k: num(r[GH[k]]) if k in GH and GH[k] < len(r) else None
    this, prior = {}, defaultdict(list)
    for r in G[1:]:
        if not r or not r[0]: continue
        k = nn(r[1]); w = int(num(r[0]) or 0)
        if w == W: this[k] = r
        elif w < W: prior[k].append(r)
    def avg(k, col): xs = [g(r, col) for r in prior[k] if g(r, col) is not None]; return sum(xs) / len(xs) if xs else None
    # snaps
    snap_w, snap_prior = {}, defaultdict(list)
    try:
        for r in csv.DictReader(open(os.path.join(IN, "snap_counts_2026.csv"))):
            if r.get("game_type") != "REG": continue
            k = nn(r["player"]); w = int(r["week"]); p = num(r["offense_pct"])
            if p is None: continue
            if w == W: snap_w[k] = p
            elif w < W: snap_prior[k].append(p)
    except Exception as e: print("note: snap counts unavailable:", e)
    # final margins
    margin = {}
    try:
        for r in csv.DictReader(open(os.path.join(IN, "games.csv"))):
            if r["season"] == "2026" and int(r["week"]) == W and r["home_score"] not in ("", "NA"):
                a, h = TEAMFIX.get(r["away_team"], r["away_team"]), TEAMFIX.get(r["home_team"], r["home_team"]); d = int(r["home_score"]) - int(r["away_score"])
                margin[h], margin[a] = d, -d
    except Exception as e: print("note: games.csv unavailable:", e)
    # weather HIGH games, availability
    wxhigh = set()
    for r in vals("weather.json")[1:]:
        if len(r) > 14 and str(r[0]) == str(W) and str(r[14]).startswith("HIGH"): wxhigh |= {r[2], r[3]}
    avail = {}
    for r in vals("avail.json")[1:]:
        if len(r) > 4 and str(r[0]) == str(W) and r[1]: avail[nn(r[1])] = r[4]
    promo_keys = set()
    try:
        for p in json.load(open(os.path.join(OUT, "promos.json"))):
            if int(p.get("week") or 0) == W:
                for l in p.get("legs") or []: promo_keys.add(str(l.get("key") or ""))
    except Exception: pass

    out = []
    for r in legs:
        if c(r, "Result") != "MISS": continue
        pl, m, ln, tm = c(r, "Player"), c(r, "Market"), num(c(r, "Line (X+)")), TEAMFIX.get(c(r, "Team"), c(r, "Team"))
        k = nn(pl); act = num(c(r, "Actual")); warn = str(c(r, "Warnings"))
        sp = snap_w.get(k); sa = (sum(snap_prior[k]) / len(snap_prior[k])) if snap_prior.get(k) else None
        tag, why = None, ""
        if sp is not None and sa and sa >= 0.3 and sp < 0.6 * sa: tag, why = "INJURY", f"snaps {sp*100:.0f}% vs {sa*100:.0f}% season"
        elif avail.get(k) in ("QUESTIONABLE", "OUT"): tag, why = "INJURY", f"{avail[k].lower()} on the availability tab"
        if not tag and m in PASSREC and tm in wxhigh: tag, why = "WEATHER", "HIGH-risk kickoff weather"
        mg = margin.get(tm)
        if not tag and mg is not None:
            if m in PASSREC and mg >= 14: tag, why = "SCRIPT", f"team won by {mg} - ran the clock"
            elif m in ("Rushing Yards",) and mg <= -14: tag, why = "SCRIPT", f"team lost by {-mg} - abandoned the run"
        if not tag:
            col = {"Passing Yards": "Pass Att", "Rushing Yards": "Rush Att", "Receiving Yards": "Targets", "Receptions": "Targets", "Longest Reception": "Targets"}.get(m)
            tr = this.get(k)
            if tr is not None:
                if col: v, a = g(tr, col), avg(k, col)
                else:   # TDs and combos: touches
                    v = (g(tr, "Rush Att") or 0) + (g(tr, "Targets") or 0); a0 = [((g(x, "Rush Att") or 0) + (g(x, "Targets") or 0)) for x in prior[k]]; a = sum(a0) / len(a0) if a0 else None
                if v is not None and a and a >= 3 and v < 0.7 * a: tag, why = "ROLE", f"{col or 'touches'} {v:.0f} vs {a:.1f} avg"
        if not tag and act is not None and ln and m != "Anytime TD":
            if (m in ("Receptions",) and act >= ln - 1) or (ln >= 10 and act >= 0.85 * ln): tag, why = "NEAR MISS", f"{act:g} vs {ln:g}"
        tag = tag or "VARIANCE"
        seen = (tag == "WEATHER") or (tag == "INJURY" and (avail.get(k) in ("QUESTIONABLE", "OUT") or re.search(r"playing hurt|playing through|betsweep note", warn, re.I)))
        out.append({"player": pl, "market": m, "line": ln, "actual": act, "team": tm, "tag": tag, "why": why, "seen": bool(seen), "key": c(r, "Key"),
                    "promo": f"{pl}|{m}|{int(round(ln or 1))}" in promo_keys})
    # one row per player + market (alt-line ladders would count the same miss five times): keep the lowest line that missed
    best = {}
    for x in out:
        kk = (x["player"], x["market"]); y = best.get(kk)
        if y is None or (x["line"] or 0) < (y["line"] or 0): x["promo"] = x["promo"] or bool(y and y["promo"]); best[kk] = x
        elif x["promo"]: y["promo"] = True
    out = list(best.values())
    os.makedirs(OUT, exist_ok=True)
    def line(rows, label):
        if not rows: return f"{label}: no losing legs"
        C = Counter(x["tag"] for x in rows); s = sum(1 for x in rows if x["seen"])
        return f"{label}: {len(rows)} losses - " + ", ".join(f"{t.lower()} {n}" for t, n in C.most_common()) + f"; {s} we could have seen coming"
    summ = {"week": W, "graded": len(legs), "all": line(out, "All graded legs"), "promo": line([x for x in out if x["promo"]], "Promo legs"), "legs": out}
    json.dump(summ, open(os.path.join(OUT, "autopsy.json"), "w"), indent=1)
    print(summ["all"]); print(summ["promo"])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
