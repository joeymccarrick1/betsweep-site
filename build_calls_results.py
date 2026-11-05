#!/usr/bin/env python3
"""build_calls_results.py [week] - grade the model's frozen per-game calls ('AUTO - Model Calls Archive') after the games.

Inputs: in/calls.json ('AUTO - Model Calls Archive'!A1:AQ2000), in/games.csv (final scores), in/gamelog.json (player box scores,
for the best-parlay legs). Default week = the newest week in the archive that has final scores.
Per game it uses the LAST row frozen before kickoff (rows frozen after kickoff are ignored).

Writes out/calls_week<W>.json  - per-game grades + the summary the receipt page shows (build_results.py reads it)
       out/calls_grades.json   - {"updates": [{"range": "'AUTO - Model Calls Archive'!AD<r>:AQ<r>", "values": [[...]]}, ...]}
                                 for the runbook to write the grades back next to the frozen rows (columns AD..AQ).
Prints one summary line.
"""
import json, os, sys, csv, math, datetime, re
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def num(x):
    try: return float(str(x).replace("%", "").replace("+", "").replace(",", ""))
    except Exception: return None
def phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))
NICK = {"Cardinals":"ARI","Falcons":"ATL","Ravens":"BAL","Bills":"BUF","Panthers":"CAR","Bears":"CHI","Bengals":"CIN","Browns":"CLE","Cowboys":"DAL","Broncos":"DEN","Lions":"DET","Packers":"GB","Texans":"HOU","Colts":"IND","Jaguars":"JAX","Chiefs":"KC","Raiders":"LV","Chargers":"LAC","Rams":"LA","Dolphins":"MIA","Vikings":"MIN","Patriots":"NE","Saints":"NO","Giants":"NYG","Jets":"NYJ","Eagles":"PHI","Steelers":"PIT","49ers":"SF","Seahawks":"SEA","Buccaneers":"TB","Titans":"TEN","Commanders":"WAS"}

arc = vals("calls.json"); H = {c: i for i, c in enumerate(arc[0])}
rows = [(i + 2, r + [""] * (43 - len(r))) for i, r in enumerate(arc[1:]) if r and num(r[0]) is not None]
GAMES = {}
with open(os.path.join(IN, "games.csv"), newline="") as f:
    for g in csv.DictReader(f):
        if g["season"] == "2026" and g["game_type"] == "REG": GAMES[(int(g["week"]), frozenset([g["away_team"], g["home_team"]]))] = g
def final(week, a, b):
    g = GAMES.get((week, frozenset([a, b])))
    if not g or g.get("home_score") in ("", None, "NA"): return None
    hs, as_ = float(g["home_score"]), float(g["away_score"])
    return {"a": hs if g["home_team"] == a else as_, "b": as_ if g["home_team"] == a else hs, "ko": g["gameday"] + "T" + g["gametime"]}
weeks_done = sorted({int(num(r[0])) for _, r in rows if final(int(num(r[0])), r[H["A"]], r[H["B"]])})
WEEK = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else (weeks_done[-1] if weeks_done else None)
if WEEK is None: raise SystemExit("no archived week has final scores yet")

# player box scores for the week (best-parlay props)
GL = {}
try:
    gl = vals("gamelog.json"); GH = {c: i for i, c in enumerate(gl[0])}
    for r in gl[1:]:
        if len(r) > 16 and num(r[0]) == WEEK: GL[r[1]] = r
except Exception: GH = {}
def stat(name, market):
    r = GL.get(name)
    if not r: return None
    g = lambda c: num(r[GH[c]]) if c in GH and GH[c] < len(r) else None
    if market == "Passing Yards": return g("Pass Yds")
    if market == "Rushing Yards": return g("Rush Yds")
    if market == "Receiving Yards": return g("Rec Yds")
    if market == "Receptions": return g("Receptions")
    if market == "Longest Reception": return g("Longest Rec")
    if market == "Anytime TD": return (g("Rush TD") or 0) + (g("Rec TD") or 0)
    return None

def grade_leg(txt, a, b, fa, fb):
    """'player|market|line|odds' -> (desc, HIT/MISS/?)"""
    p = [x.strip() for x in txt.split("|")]
    if len(p) < 3: return (txt, "?")
    name, market, line = p[0], p[1], num(p[2])
    m = fa - fb; tot = fa + fb
    if market == "Moneyline":
        t = NICK.get(name.replace(" ML", "").strip(), name.replace(" ML", "").strip())
        won = (m > 0 and t == a) or (m < 0 and t == b); return (name, "PUSH" if m == 0 else ("HIT" if won else "MISS"))
    if market == "Spread":
        mm = re.match(r"(\w+)\s+([+-]?[\d.]+)", name); t, pt = mm.group(1), float(mm.group(2))
        marg = m if t == a else -m; v = marg + pt; return (name, "PUSH" if v == 0 else ("HIT" if v > 0 else "MISS"))
    if market == "Total":
        over = name.lower().startswith("over"); return (name, "PUSH" if tot == line else ("HIT" if (tot > line) == over else "MISS"))
    s = stat(name, market)
    if s is None: return (f"{name} {market.lower()} {int(line)}+", "?")
    need = 1 if market == "Anytime TD" else line
    return (f"{name} {market.lower()} {int(line)}+ ({s:g})", "HIT" if s >= need else "MISS")

def actual_script(a, b, m, tot):
    if m >= 10: return f"{a} by 10+"
    if m <= -10: return f"{b} by 10+"
    return "shootout" if tot >= 51 else "close, low"
def norm_script(s, a, b):
    s = str(s).strip().lower()
    if "shootout" in s: return "shootout"
    if "close" in s: return "close, low"
    mm = re.match(r"(\w+)\s+by", s)
    return (mm.group(1).upper() + " by 10+") if mm else s

CT = ZoneInfo("America/Chicago"); now = datetime.datetime.now(CT).strftime("%Y-%m-%d %H:%M")
# latest pre-kickoff row per game
best = {}
for rn, r in rows:
    if int(num(r[0])) != WEEK: continue
    a, b = r[H["A"]], r[H["B"]]; fin = final(WEEK, a, b)
    if not fin: continue
    ko = datetime.datetime.fromisoformat(fin["ko"]).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(CT)
    fz = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d)", str(r[1]))
    if fz and datetime.datetime.fromisoformat(fz.group(1)).replace(tzinfo=CT) >= ko: continue   # frozen after kickoff
    best[(a, b)] = (rn, r, fin)
games_out, updates = [], []
n = {"ml": [0, 0], "spr": [0, 0], "tot": [0, 0], "scr": [0, 0], "bp": [0, 0], "fav": [0, 0], "ml_agree": [0, 0], "ml_disagree": [0, 0], "ats_fav": [0, 0]}   # fav = market favourite's record; agree/disagree = model ML vs market favourite
mae = {"model_m": [], "mkt_m": [], "model_t": [], "mkt_t": []}; brier = {"shown": [], "raw": [], "mkt": []}
for (a, b), (rn, r, fin) in sorted(best.items(), key=lambda kv: kv[1][2]["ko"]):
    fa, fb = fin["a"], fin["b"]; m = fa - fb; tot = fa + fb
    g = lambda c: r[H[c]]
    pw, pc, po = num(g("Model P(A win) as shown")), num(g("Model P(A covers) as shown")), num(g("Model P(over) as shown"))
    spA, fdt = num(g("FD spread (A)")), num(g("FD total"))
    mlA, mlB = num(g("FD ML A")), num(g("FD ML B"))
    def lean(p, yes, no): return None if p is None else (yes if p >= 0.5 else no)
    ml_lean = lean(pw, a, b); ml_hit = None if ml_lean is None or m == 0 else ((m > 0) == (ml_lean == a))
    # the market's own pick (lower moneyline = favourite), so a 7-7 upset week reads next to what the closing favourites did
    mkt_fav = None if mlA is None or mlB is None else (a if mlA < mlB else b if mlB < mlA else (None if not spA else (a if spA < 0 else b)))   # equal moneylines (a -108/-108 pick'em): the spread names the favourite
    fav_hit = None if mkt_fav is None or m == 0 else ((m > 0) == (mkt_fav == a))
    mkt_imp = None
    if mlA is not None and mlB is not None:
        _ia = (100 / (mlA + 100)) if mlA > 0 else (-mlA / (-mlA + 100)); _ib = (100 / (mlB + 100)) if mlB > 0 else (-mlB / (-mlB + 100)); mkt_imp = _ia / (_ia + _ib)
    disagree = mkt_fav is not None and ml_lean is not None and ml_lean != mkt_fav
    spr_lean = lean(pc, a, b); spr_v = None if spA is None else m + spA; spr_hit = None if spr_lean is None or spr_v is None or spr_v == 0 else ((spr_v > 0) == (spr_lean == a))
    tot_lean = lean(po, "Over", "Under"); tot_hit = None if tot_lean is None or fdt is None or tot == fdt else ((tot > fdt) == (tot_lean == "Over"))
    act = actual_script(a, b, m, tot); scr_hit = norm_script(g("Most likely"), a, b) == act
    legs = [x for x in str(g("Best parlay legs")).split(" | ") if x.strip()]
    gl = [grade_leg(x, a, b, fa, fb) for x in legs]
    bp = "" if not legs else ("ungradable" if any(x[1] == "?" for x in gl) else ("HIT" if all(x[1] in ("HIT", "PUSH") for x in gl) else f"MISS ({sum(1 for x in gl if x[1]=='HIT')}/{len(gl)})"))
    for k, h in (("ml", ml_hit), ("spr", spr_hit), ("tot", tot_hit), ("scr", scr_hit), ("fav", fav_hit)):
        if h is not None: n[k][1] += 1; n[k][0] += 1 if h else 0
    if ml_hit is not None and mkt_fav is not None:
        k = "ml_disagree" if disagree else "ml_agree"; n[k][1] += 1; n[k][0] += 1 if ml_hit else 0
    if bp in ("HIT",) or bp.startswith("MISS"): n["bp"][1] += 1; n["bp"][0] += 1 if bp == "HIT" else 0
    mm, mt = num(g("Model margin (A-B)")), num(g("Model total"))
    if mm is not None: mae["model_m"].append(abs(mm - m))
    if spA is not None: mae["mkt_m"].append(abs(-spA - m))
    if mt is not None: mae["model_t"].append(abs(mt - tot))
    if fdt is not None: mae["mkt_t"].append(abs(fdt - tot))
    y = 1.0 if m > 0 else 0.0
    if m != 0:
        if pw is not None: brier["shown"].append((pw - y) ** 2)
        if mm is not None: brier["raw"].append((phi(mm / 12.6) - y) ** 2)
        if mlA is not None and mlB is not None:
            ia = (100 / (mlA + 100)) if mlA > 0 else (-mlA / (-mlA + 100)); ib = (100 / (mlB + 100)) if mlB > 0 else (-mlB / (-mlB + 100))
            brier["mkt"].append((ia / (ia + ib) - y) ** 2)
    Y = lambda h: "" if h is None else ("HIT" if h else "MISS")
    vals_ = [fa, fb, m, tot, act, ml_lean or "", Y(ml_hit), spr_lean or "", Y(spr_hit), tot_lean or "", Y(tot_hit), "HIT" if scr_hit else "MISS", bp, now]
    updates.append({"range": f"'AUTO - Model Calls Archive'!AD{rn}:AQ{rn}", "values": [vals_]})
    games_out.append({"gid": f"{a}-{b}", "a": a, "b": b, "fa": fa, "fb": fb, "pa": num(g("Model A pts")), "pb": num(g("Model B pts")), "most": norm_script(g("Most likely"), a, b), "act": act, "scr_hit": scr_hit,
                      "ml": [ml_lean, pw, ml_hit], "mkt_fav": mkt_fav, "mkt_imp": mkt_imp, "ml_disagree": disagree, "spr": [spr_lean, spA, pc, spr_hit], "tot": [tot_lean, fdt, po, tot_hit], "bp": {"legs": gl, "price": g("Best parlay price"), "pj": num(g("Best parlay model %")), "fit": g("Built for"), "res": bp},
                      "src": g("Line source"), "frozen": g("Frozen at (CT)")})
avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
summary = {"week": WEEK, "games": len(games_out), "ml": n["ml"], "spread": n["spr"], "total": n["tot"], "script": n["scr"], "best_parlay": n["bp"],
           "market_fav": n["fav"], "ml_agree": n["ml_agree"], "ml_disagree": n["ml_disagree"],
           "mae_margin": {"model": avg(mae["model_m"]), "market": avg(mae["mkt_m"])}, "mae_total": {"model": avg(mae["model_t"]), "market": avg(mae["mkt_t"])},
           "brier_win": {"shown": avg(brier["shown"]), "raw_model": avg(brier["raw"]), "market": avg(brier["mkt"])}, "graded_at": now}
json.dump({"summary": summary, "games": games_out}, open(os.path.join(OUT, f"calls_week{WEEK}.json"), "w"), indent=1)
json.dump({"updates": updates}, open(os.path.join(OUT, "calls_grades.json"), "w"), indent=1)
print(f"graded week {WEEK}: {len(games_out)} games - ML {n['ml'][0]}/{n['ml'][1]}, spread {n['spr'][0]}/{n['spr'][1]}, total {n['tot'][0]}/{n['tot'][1]}, script {n['scr'][0]}/{n['scr'][1]}, best parlay {n['bp'][0]}/{n['bp'][1]}; "
      f"margin MAE model {summary['mae_margin']['model']} vs market {summary['mae_margin']['market']}; total MAE model {summary['mae_total']['model']} vs market {summary['mae_total']['market']}; "
      f"win Brier shown {summary['brier_win']['shown']} / raw {summary['brier_win']['raw_model']} / market {summary['brier_win']['market']}")
