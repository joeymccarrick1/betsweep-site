#!/usr/bin/env python3
"""flag_stats.py - the graded numbers quoted inside flags and slip warnings, counted on every build (owner 11/17: "Fix the 2 open things").

Until now each of these sentences carried a number typed in on the day its study ran ("Weeks 6-9 (439 legs)"), and nothing recounted
it when another week was graded. Each one is now counted from the sheet's leg snapshots (in/legsnaps.json: the latest frozen snapshot
of every FanDuel leg, HIT or MISS), the game log and the closing spreads, with the rule the flag itself uses:

  main        the main rushing line of each player-week (the rung nearest -110): how often the over missed = the under's rate.
              RUSH_UNDER_RATE in build_builder.py reads this, so the flat chance shown on a rushing under follows the grades.
  near_zero   floor legs (-180 or shorter) on a player who finished under half the line in a third or more of his games so far.
  losing      yardage floors (-180 or shorter) on underdogs of 5.5+ by the closing spread, against favorites of 5.5+. (The flag fires
              on "the model's most likely ending is the opponent by 10+"; past endings are not archived, and since the model takes its
              margin from FanDuel's line that is, in practice, an underdog of about 5.5 or more.)
  fav         every leg at -130 or shorter, and the same legs where the raw model was 5+ points over the price, by price band.
  disagree    legs where the raw model was 10+ points over the price: what it said, what happened.
  team        walk-forward: team-markets whose graded legs to date sat 4+ points under their prices (flags.py TREL), the week after.
  player      walk-forward: players flags.py would have called Reliable / Volatile from the weeks before (REL), the week after.

counts(in_dir) -> the raw numbers; text(in_dir) -> the sentences, each ending with its own span and leg count; every sentence has a
fallback (the 11/17 count) so a missing mirror never leaves a hole. `python3 flag_stats.py` prints both.
"""
import csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
NZ_STAT = {"Receiving Yards": "Rec Yds", "Receptions": "Receptions", "Rushing Yards": "Rush Yds", "Passing Yards": "Pass Yds"}
YARDS = ("Rushing Yards", "Receiving Yards", "Passing Yards", "Longest Reception")

def _num(x):
    try: return float(str(x).replace("%", "").replace("+", "").replace(",", ""))
    except (TypeError, ValueError): return None
def _imp(o): return (-o / (-o + 100.0)) if o < 0 else 100.0 / (o + 100.0)
def _dec(o): return 1 + (o / 100.0 if o > 0 else 100.0 / -o)
def _nn(s): return re.sub(r"[^a-z]", "", str(s).lower().replace(" jr", "").replace(" sr", "").replace(" iii", "").replace(" ii", ""))

def legs(in_dir):
    try: v = json.load(open(os.path.join(in_dir, "legsnaps.json")))["values"]
    except Exception: return []
    H = {c: i for i, c in enumerate(v[0])}; out = []
    for r in v[1:]:
        r = list(r) + [""] * (len(v[0]) - len(r))
        if r[H["Latest Snapshot"]] != "TRUE" or r[H["Result"]] not in ("HIT", "MISS"): continue
        o, w = _num(r[H["FanDuel odds"]]), _num(r[H["Week"]])
        if not o or not w: continue
        out.append({"w": int(w), "pl": r[H["Player"]], "tm": r[H["Team"]], "opp": r[H["Opp"]], "m": r[H["Market"]], "o": o, "hit": r[H["Result"]] == "HIT",
                    "raw": _num(r[H["Raw model %"]]), "ln": _num(r[H["Line (X+)"]])})
    return out

def _s(rows):
    n = len(rows)
    if not n: return {"n": 0, "hit": 0.0, "imp": 0.0, "roi": 0.0}
    return {"n": n, "hit": sum(x["hit"] for x in rows) / n, "imp": sum(_imp(x["o"]) for x in rows) / n, "roi": sum((_dec(x["o"]) - 1) if x["hit"] else -1 for x in rows) / n}

def _gamelog(in_dir):
    """{player: {week: {stat: value}}} for this season's game log"""
    try: g = json.load(open(os.path.join(in_dir, "gamelog.json")))["values"]
    except Exception: return {}
    H = {c: i for i, c in enumerate(g[0])}; out = {}
    for r in g[1:]:
        if len(r) <= H["Rec Yds"]: continue
        w = _num(r[H["Week"]])
        if not w: continue
        out.setdefault(r[H["Player"]], {})[int(w)] = {"Rec Yds": _num(r[H["Rec Yds"]]) or 0, "Receptions": _num(r[H["Receptions"]]) or 0, "Rush Yds": _num(r[H["Rush Yds"]]) or 0, "Pass Yds": _num(r[H["Pass Yds"]]) or 0}
    return out

def _spreads(in_dir, season):
    """{(week, team): points the team was favoured by at the close (negative = underdog)}"""
    out = {}
    try:
        for r in csv.DictReader(open(os.path.join(in_dir, "games.csv"), encoding="utf-8")):
            if str(r.get("season")) != str(season) or r.get("spread_line") in ("", "NA", None): continue
            sp = float(r["spread_line"]); w = int(r["week"]); out[(w, r["home_team"])] = sp; out[(w, r["away_team"])] = -sp
    except Exception: pass
    return out

def scripts(in_dir="in"):
    """{(week, team): (most likely ending, the game's two teams)} from the model's own pre-kickoff read of each game: Weeks 8-10
    recovered from the site's history (research/scripts_history.json), later weeks from the file build_boards writes at every build
    (data/scripts-w<week>.json - the published copy under BS_SITE, else the last local build's). A week still being played is left out."""
    import glob, time
    here = os.path.dirname(os.path.abspath(__file__)); out = {}; now = time.time() * 1000
    def take(wk, games):
        if not games or max((g.get("ko") or 0) for g in games.values()) > now: return
        for g in games.values():
            if g.get("a") and g.get("b") and g.get("most"): out[(int(wk), g["a"])] = (g["most"], g["b"]); out[(int(wk), g["b"])] = (g["most"], g["a"])
    try:
        for wk, games in (json.load(open(os.path.join(here, "research", "scripts_history.json")))["weeks"]).items(): take(wk, games)
    except Exception: pass
    for d in ([os.path.join(os.environ["BS_SITE"], "data")] if os.environ.get("BS_SITE") else []) + [os.path.join(here, "out", "data")]:
        for f in sorted(glob.glob(os.path.join(d, "scripts-w*.json"))):
            try:
                j = json.load(open(f, encoding="utf-8"))
                if not any(k[0] == int(j["week"]) for k in out): take(j["week"], j.get("games") or {})
            except Exception: pass
    return out

def counts(in_dir="in", season=None):
    L = legs(in_dir)
    if len(L) < 1000: return None
    weeks = sorted({x["w"] for x in L}); C = {"weeks": weeks, "n": len(L)}
    # main rushing line of each player-week
    best = {}
    for x in L:
        if x["m"] != "Rushing Yards": continue
        k = (x["w"], x["pl"])
        if k not in best or abs(x["o"] + 110) < abs(best[k]["o"] + 110): best[k] = x
    mains = [x for x in best.values() if -160 <= x["o"] <= 130]; s = _s(mains)
    C["main"] = {"n": s["n"], "under": 1 - s["hit"], "by_week": {w: 1 - _s([x for x in mains if x["w"] == w])["hit"] for w in weeks}}
    # near-zero floor legs
    G = _gamelog(in_dir); nz = []
    for x in L:
        if x["o"] > -180 or x["m"] not in NZ_STAT or not x["ln"]: continue
        gs = [v[NZ_STAT[x["m"]]] for w, v in (G.get(x["pl"]) or {}).items() if w < x["w"]]
        if len(gs) >= 4 and sum(1 for v in gs if v < 0.5 * x["ln"]) * 3 >= len(gs): nz.append(x)
    C["near_zero"] = dict(_s(nz), weeks_under=sum(1 for w in weeks if (lambda t: t["n"] and t["hit"] < t["imp"])(_s([x for x in nz if x["w"] == w]))), weeks_with=sum(1 for w in weeks if any(x["w"] == w for x in nz)))
    # yardage floors by closing spread
    if season is None:   # the newest season in the schedule file that has these weeks
        try: season = max(int(r["season"]) for r in csv.DictReader(open(os.path.join(in_dir, "games.csv"), encoding="utf-8")) if r.get("season", "").isdigit())
        except Exception: season = 2026
    SP = _spreads(in_dir, season); fl = [x for x in L if x["o"] <= -180 and x["m"] in YARDS and (x["w"], x["tm"]) in SP]
    C["losing"] = {"dog": _s([x for x in fl if SP[(x["w"], x["tm"])] <= -5.5]), "fav": _s([x for x in fl if SP[(x["w"], x["tm"])] >= 5.5])}
    # 11/17 evening: the same flag by ITS OWN definition - the team the model's likeliest ending has losing by 10+ - on the weeks whose
    # pre-kickoff scripts are on file (scripts()). The spread version above stays as the fallback and as a second view.
    SC = scripts(in_dir); own = [x for x in L if x["o"] <= -180 and x["m"] in YARDS and (x["w"], x["tm"]) in SC]
    lose = [x for x in own if SC[(x["w"], x["tm"])][0] == f'{x["opp"]} by 10+']; win = [x for x in own if SC[(x["w"], x["tm"])][0] == f'{x["tm"]} by 10+']
    ow = sorted({x["w"] for x in own})
    C["losing_own"] = {"weeks": ow, "lose": _s(lose), "win": _s(win), "rest": _s([x for x in own if x not in lose and x not in win]) if len(own) < 5000 else {},
                       "weeks_under": sum(1 for w in ow if (lambda t: t["n"] and t["hit"] < t["imp"])(_s([x for x in lose if x["w"] == w])))}
    # favorites, with and without a model edge
    fav = [x for x in L if x["o"] <= -130]; ed = [x for x in fav if x["raw"] is not None and x["raw"] - _imp(x["o"]) >= 0.05]
    bands = [_s([x for x in ed if lo <= x["o"] <= hi]) for lo, hi in ((-179, -130), (-249, -180), (-99999, -250))]
    C["fav"] = {"all": _s(fav), "edge": _s(ed), "edge_bands": [b["roi"] for b in bands if b["n"] >= 40]}
    # the raw model 10+ points over the price
    dis = [x for x in L if x["raw"] is not None and x["raw"] - _imp(x["o"]) >= 0.10]
    C["disagree"] = dict(_s(dis), model=(sum(x["raw"] for x in dis) / len(dis)) if dis else 0.0)
    # walk-forward: flags.py REL / TREL built from the weeks before, scored on the week itself (no-vig price = implied / 1.045)
    def nv(x): return _imp(x["o"]) / 1.045
    acc = {"team_under": [0, 0.0, 0.0], "team_rest": [0, 0.0, 0.0], "reliable": [0, 0.0, 0.0], "volatile": [0, 0.0, 0.0], "rest": [0, 0.0, 0.0]}
    R = [x for x in L if x["m"] != "Longest Reception"]
    for w in weeks[1:]:
        S, T = {}, {}
        for x in R:
            if x["w"] >= w: continue
            a = S.setdefault(_nn(x["pl"]), [0, 0, 0.0]); a[0] += 1; a[1] += x["hit"]; a[2] += nv(x)
            b = T.setdefault((x["tm"], x["m"]), [0, 0, 0.0]); b[0] += 1; b[1] += x["hit"]; b[2] += nv(x)
        rel = {p: (h - b) / (n + 12) for p, (n, h, b) in S.items() if n >= 8}; trel = {k: (h - b) / (n + 20) for k, (n, h, b) in T.items() if n >= 15}
        for x in R:
            if x["w"] != w: continue
            d = rel.get(_nn(x["pl"])); grp = "reliable" if d is not None and d >= 0.05 else "volatile" if d is not None and d <= -0.05 else "rest"
            for g in (grp, "team_under" if trel.get((x["tm"], x["m"]), 0) <= -0.04 else "team_rest"):
                acc[g][0] += 1; acc[g][1] += x["hit"]; acc[g][2] += nv(x)
    C["walk"] = {k: {"n": n, "gap": ((h - b) / n) if n else 0.0} for k, (n, h, b) in acc.items()}; C["walk_weeks"] = weeks[1:]
    return C

def _span(ws, plain=True):
    if len(ws) > 1 and ws == list(range(ws[0], ws[-1] + 1)): return f"Weeks {ws[0]}-{ws[-1]}"
    return ("Week " if len(ws) == 1 else "Weeks ") + ", ".join(str(w) for w in ws)
def _pts(x): return f"{abs(100 * x):.0f} point{'s' if round(abs(100 * x)) != 1 else ''} {'under' if x < 0 else 'over'}"
def _pct(x): return f"{100 * x:.0f}%"
def _roi(x): return f"{'+' if x > 0 else '-' if x < 0 else ''}{abs(100 * x):.0f}%"

DEFAULT = {
    "rush_under_rate": 0.57,
    "rush_under": "the rate main-line rushing unders have hit in Weeks 6-10 (389 lines)",
    "near_zero": "Floor legs on players like that hit 61% against a 70% price in Weeks 6-10 (247 legs, under in all 5 weeks).",
    "losing": "Yardage floors on the side the model had losing big have hit 59% against a 70% price in Weeks 8-10 (318 legs, under in all 3 weeks); on the side it had winning big, 70%.",
    "fav": "graded Weeks 6-10, favorites returned about -10% per leg (-6% even where the model had an edge)",
    "disagree": "When we disagree with the book by 10+ points the book has usually been closer (Weeks 6-10: model 66%, hit 51%)",
    "team": "Team-markets this far under went on to hit about 4 points under their prices, the rest about 3 points under (Weeks 7-10).",
    "reliable": "Players like that went on to hit about 2 points under their prices, the rest about 3 points under (Weeks 7-10).",
    "volatile": "Volatile players went on to hit about 3 points under their prices (Weeks 7-10), about the same as the rest.",
}
def text(in_dir="in"):
    """the sentences, counted; any piece that cannot be counted keeps its DEFAULT"""
    T = dict(DEFAULT)
    try: C = counts(in_dir)
    except Exception as e: print("note flag_stats: counted nothing, the 11/17 numbers stay -", e); C = None
    if not C: return T
    W = _span(C["weeks"]); WW = _span(C["walk_weeks"])
    m = C["main"]
    if m["n"] >= 150: T["rush_under_rate"] = min(0.62, max(0.50, round(m["under"], 2))); T["rush_under"] = f"the rate main-line rushing unders have hit in {W} ({m['n']} lines)"
    z = C["near_zero"]
    if z["n"] >= 60: T["near_zero"] = f"Floor legs on players like that hit {_pct(z['hit'])} against a {_pct(z['imp'])} price in {W} ({z['n']} legs" + (f", under in all {z['weeks_with']} weeks" if z["weeks_under"] == z["weeks_with"] and z["weeks_with"] > 1 else f", under in {z['weeks_under']} of {z['weeks_with']} weeks") + ")."
    d, f = C["losing"]["dog"], C["losing"]["fav"]
    if d["n"] >= 100 and f["n"] >= 100: T["losing"] = f"Yardage floors on underdogs of 5.5 or more have hit {_pct(d['hit'])} against a {_pct(d['imp'])} price in {W} ({d['n']} legs); on favorites that big, {_pct(f['hit'])}."
    lo = C.get("losing_own") or {}
    if lo and lo["lose"]["n"] >= 150 and lo["win"]["n"] >= 150:   # the flag's own definition, once enough weeks of scripts are on file
        T["losing"] = (f"Yardage floors on the side the model had losing big have hit {_pct(lo['lose']['hit'])} against a {_pct(lo['lose']['imp'])} price in {_span(lo['weeks'])} ({lo['lose']['n']} legs"
                       + (f", under in all {len(lo['weeks'])} weeks" if lo["weeks_under"] == len(lo["weeks"]) and len(lo["weeks"]) > 1 else "") + f"); on the side it had winning big, {_pct(lo['win']['hit'])}.")
    a, eb = C["fav"]["all"], C["fav"]["edge_bands"]
    e = C["fav"]["edge"]
    if a["n"] >= 500: T["fav"] = f"graded {W}, favorites returned about {_roi(a['roi'])} per leg" + (f" ({_roi(e['roi'])} even where the model had an edge)" if e["n"] >= 100 else "")
    g = C["disagree"]
    if g["n"] >= 150: T["disagree"] = f"When we disagree with the book by 10+ points the book has usually been closer ({W}: model {_pct(g['model'])}, hit {_pct(g['hit'])})" if g["hit"] < g["model"] - 0.03 else f"Legs where we sat 10+ points over the book have hit {_pct(g['hit'])} against the model's {_pct(g['model'])} ({W})"
    wk = C["walk"]
    if wk["team_under"]["n"] >= 150 and wk["team_rest"]["n"] >= 150: T["team"] = f"Team-markets this far under went on to hit about {_pts(wk['team_under']['gap'])} their prices, the rest about {_pts(wk['team_rest']['gap'])} ({WW})."
    if wk["reliable"]["n"] >= 100 and wk["rest"]["n"] >= 100:
        T["reliable"] = (f"Players like that went on to hit about {_pts(wk['reliable']['gap'])} their prices, the rest about {_pts(wk['rest']['gap'])} ({WW})."
                         if wk["reliable"]["gap"] > wk["rest"]["gap"] else f"So far that has not carried over: players like that went on to hit about {_pts(wk['reliable']['gap'])} their prices, the rest about {_pts(wk['rest']['gap'])} ({WW}).")
    if wk["volatile"]["n"] >= 100 and wk["rest"]["n"] >= 100:
        T["volatile"] = f"Volatile players went on to hit about {_pts(wk['volatile']['gap'])} their prices ({WW})" + (f", worse than the rest ({_pts(wk['rest']['gap'])})." if wk["volatile"]["gap"] < wk["rest"]["gap"] - 0.01 else ", about the same as the rest.")
    return T

if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "in"); C = counts(d)
    if C:
        print("main rushing line:", C["main"]["n"], "lines, under", round(100 * C["main"]["under"], 1), {w: round(100 * v, 1) for w, v in C["main"]["by_week"].items()})
        for k in ("near_zero",): print(k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in C[k].items()})
        print("losing", {k: {a: round(b, 3) for a, b in v.items()} for k, v in C["losing"].items()})
        print("fav", {k: ({a: round(b, 3) for a, b in v.items()} if isinstance(v, dict) else [round(b, 3) for b in v]) for k, v in C["fav"].items()})
        print("disagree", {a: round(b, 3) for a, b in C["disagree"].items()}); print("walk", C["walk_weeks"], {k: (v["n"], round(100 * v["gap"], 1)) for k, v in C["walk"].items()})
    for k, v in text(d).items(): print(f"{k:16s} {v}")
