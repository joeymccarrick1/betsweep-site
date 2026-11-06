#!/usr/bin/env python3
"""BetSweep season-to-date receipt — v2026-10-14.
Inputs: in/scorecard.json ('V2 - Weekly Scorecard'!A1:K200), in/legsnaps.json ('V2 - FanDuel Leg Snapshots'!A1:AB6000), in/gamelog.json (matchup buckets), in/calls.json + in/games.csv (game calls vs the closing line), in/promos.json (promoted bets record),
        in/archive.json (optional, links to weekly receipts). Output: out/season-receipt.html
"""
import json, html, os, datetime
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
E = html.escape
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def num(x):
    try: return float(str(x).replace("%", "").replace("+", "").replace(",", ""))
    except: return None
exec(open(os.path.join(HERE, "brand.py")).read())

sc = vals("scorecard.json"); H = {c: i for i, c in enumerate(sc[0])}
rows = [r + [""] * (11 - len(r)) for r in sc[1:] if len(r) > 6]
def g(r, c): return r[H[c]] if c in H else ""
weeks = sorted({int(float(g(r, "Week"))) for r in rows if g(r, "Week") not in ("", "All") and (num(g(r, "With Stat Row")) or 0) > 0})
def cell(week, pos, col="MAE Fantasy Pts", snap=None):
    for r in rows:
        if str(g(r, "Week")) == str(week) and g(r, "Position") == pos and (snap is None or g(r, "Snapshot Type") == snap) and (num(g(r, "With Stat Row")) or 0) > 0:
            return num(g(r, col)), g(r, "Snapshot Type"), int(float(g(r, "With Stat Row")))
    return None, None, 0
series = {pos: [(w, cell(w, pos)) for w in weeks] for pos in ("All skill", "QB", "RB", "WR", "TE", "K")}
allrow = {pos: cell("All", pos, snap="Frozen") for pos in ("All skill", "QB", "RB", "WR", "TE", "K")}

# ---- legs across the season (latest snapshot rows) ----
L = []
try:
    lf = vals("legsnaps.json"); LH = {c: i for i, c in enumerate(lf[0])}
    for r in lf[1:]:
        r = r + [""] * (28 - len(r))
        if str(r[LH["Latest Snapshot"]]).upper() != "TRUE" or r[LH["Result"]].upper() not in ("HIT", "MISS"): continue
        L.append({"week": int(float(r[LH["Week"]])), "market": r[LH["Market"]], "res": r[LH["Result"]].upper(), "units": num(r[LH["Units (1u)"]]) or 0,
                  "warn": r[LH["Warnings"]], "p": num(r[LH["Model % (hist-adj)"]]), "book": num(r[LH["Book implied %"]]),
                  "ln": num(r[LH["Line (X+)"]]), "proj": num(r[LH["Projection"]]), "o": num(r[LH["FanDuel odds"]]), "player": r[LH["Player"]], "opp": r[LH["Opp"]]})
except Exception: pass
def pct(v): return None if v is None else (v / 100 if v > 1.5 else v)
for l in L: l["p"] = pct(l["p"]); l["book"] = pct(l["book"])
byw = defaultdict(lambda: [0, 0, 0.0]); bym = defaultdict(lambda: [0, 0, 0.0])
for l in L:
    for d, k in ((byw, l["week"]), (bym, l["market"])): d[k][0] += 1; d[k][1] += (l["res"] == "HIT"); d[k][2] += l["units"]
tot = [len(L), sum(1 for l in L if l["res"] == "HIT"), sum(l["units"] for l in L)]
clean = [l for l in L if not l["warn"]]; cl = [len(clean), sum(1 for l in clean if l["res"] == "HIT"), sum(l["units"] for l in clean)]

# ---- chart: MAE by week (inline SVG, to scale) ----
def chart():
    pts = [(w, v[0], v[1]) for w, v in series["All skill"] if v[0] is not None]
    if not pts: return '<p class="none">No graded weeks yet.</p>'
    W_, H_ = 640, 220; padl, padr, padt, padb = 44, 16, 18, 34
    ymax = max(8.0, max(p[1] for p in pts) * 1.15); ymin = 0
    xs = [w for w, _, _ in pts]; x0, x1 = min(xs), max(xs) if len(xs) > 1 else min(xs) + 1
    def X(w): return padl + (w - x0) / max(1, (x1 - x0)) * (W_ - padl - padr)
    def Y(v): return padt + (1 - (v - ymin) / (ymax - ymin)) * (H_ - padt - padb)
    grid = "".join(f'<line x1="{padl}" x2="{W_-padr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="g"/><text x="{padl-6}" y="{Y(t)+4:.1f}" class="tl" text-anchor="end">{t:g}</text>' for t in range(0, int(ymax) + 1, 2))
    path = " ".join(f'{"M" if i == 0 else "L"}{X(w):.1f} {Y(v):.1f}' for i, (w, v, _) in enumerate(pts))
    dots = "".join(f'<circle cx="{X(w):.1f}" cy="{Y(v):.1f}" r="4" class="{"dot" if t == "Frozen" else "dot re"}"><title>Week {w}: PPR MAE {v:.2f} ({t})</title></circle><text x="{X(w):.1f}" y="{Y(v)-9:.1f}" class="vl" text-anchor="middle">{v:.1f}</text><text x="{X(w):.1f}" y="{H_-padb+16}" class="tl" text-anchor="middle">Wk {w}</text>' for w, v, t in pts)
    return f'<svg viewBox="0 0 {W_} {H_}" class="chart" role="img" aria-label="PPR mean absolute error by week">{grid}<path d="{path}" class="ln"/>{dots}<text x="{padl}" y="{H_-4}" class="tl">● frozen pre-kickoff &nbsp; ○ reconstructed (weeks before snapshots began)</text></svg>'

def row_pos(pos):
    cells = "".join(f'<td>{"" if v[0] is None else f"{v[0]:.1f}"}{"" if v[1] != "Reconstructed" else "<small>r</small>"}</td>' for _, v in series[pos])
    a = allrow[pos]
    return f'<tr><th>{E(pos)}</th>{cells}<td class="tot">{"" if a[0] is None else f"{a[0]:.2f}"}<small>{a[2]}</small></td></tr>'
table = f'<div class="tblwrap"><table class="season"><thead><tr><th>PPR MAE</th>{"".join(f"<th>Wk {w}</th>" for w in weeks)}<th>Frozen, all</th></tr></thead><tbody>{"".join(row_pos(p) for p in ("All skill","QB","RB","WR","TE","K"))}</tbody></table><p class="fn"><small>r</small> = reconstructed after the fact (before snapshots began in Week 5); the "Frozen, all" column counts only pre-kickoff snapshots, with players graded.</p></div>'

legs_week = "".join(f'<li><span class="bl-p">Week {w}</span><span class="bl-m">{v[1]}–{v[0]-v[1]} · {v[1]/v[0]*100:.0f}% hit</span><b class="{"pos" if v[2]>=0 else "neg"}">{v[2]:+.2f}u</b></li>' for w, v in sorted(byw.items())) or "<li class='none'>No graded FanDuel legs yet - leg freezing started Week 6; the first graded week lands on the Tuesday after.</li>"
legs_mkt = "".join(f'<li><span class="bl-p">{E(m)}</span><span class="bl-m">{v[1]}–{v[0]-v[1]} · {v[1]/v[0]*100:.0f}% hit</span><b class="{"pos" if v[2]>=0 else "neg"}">{v[2]:+.2f}u</b></li>' for m, v in sorted(bym.items(), key=lambda kv: -kv[1][0])) or "<li class='none'>—</li>"
# ---- calibration: did the legs we recommend hit as often as the model said? (the week-6 lesson, automated) ----
def calib_rows(groups):
    out = []
    for name, ls in groups:
        ls = [l for l in ls if l["p"] is not None]
        if len(ls) < 8: continue
        hit = sum(l["res"] == "HIT" for l in ls) / len(ls); mp = sum(l["p"] for l in ls) / len(ls); gap = (hit - mp) * 100
        out.append(f'<li><span class="bl-p">{E(name)}</span><span class="bl-m">{len(ls)} legs · hit {hit*100:.0f}% vs model {mp*100:.0f}%</span><b class="{"pos" if gap >= -3 else "neg"}">{gap:+.0f}</b></li>')
    return "".join(out)
def edge(l): return None if l["p"] is None or l["book"] is None else (l["p"] - l["book"]) * 100
def depth(l): return None if not l["ln"] or not l["proj"] or l["proj"] <= 0 else l["ln"] / l["proj"]
EB = [("Model fade (edge ≤ −5)", lambda l: edge(l) is not None and edge(l) <= -5), ("Edge −5…+5", lambda l: edge(l) is not None and -5 < edge(l) < 5),
      ("Edge +5…+10", lambda l: edge(l) is not None and 5 <= edge(l) < 10), ("Edge ≥ +10 (what we push)", lambda l: edge(l) is not None and edge(l) >= 10)]
FLOOR_MIN = {"Receiving Yards": 40, "Receptions": 3, "Rushing Yards": 50}
def is_floor_rule(l):   # mirrors home.py is_floor / the builder's "floor legs" filter, minus the flags it cannot see here
    d = depth(l); return (d is not None and 0.3 < d <= 0.6 and l["market"] in FLOOR_MIN and l["proj"] >= FLOOR_MIN[l["market"]]
            and l["o"] is not None and -400 <= l["o"] <= -130 and l["p"] is not None and l["book"] is not None and l["p"] >= l["book"] - 0.05 and not any(k in l["warn"] for k in ("Snap share slipping", "Next man up", "Rising:", "Fill-in", "Trending down", "Usage falling", "First game back")))   # First game back = the builder's Returning flag
DB = [("Floor rule (anchors: 30–60% of proj, primary role, −130…−400)", is_floor_rule), ("Deep floor (line ≤ 70% of proj)", lambda l: depth(l) is not None and depth(l) <= 0.7), ("Floor (70–85%)", lambda l: depth(l) is not None and 0.7 < depth(l) <= 0.85),
      ("Near projection (85–110%)", lambda l: depth(l) is not None and 0.85 < depth(l) <= 1.1), ("Above projection (>110%)", lambda l: depth(l) is not None and depth(l) > 1.1)]
# the snapshot's Warnings column carries the sheet's Leg Board wording (not the builder's flag names), so the buckets key off that text
import re as _re
def _cleared_pct(w):
    m = _re.search(r"Cleared this line in only (\d+)%", w); return int(m.group(1)) if m else None
WB = [("No warnings", lambda l: not l["warn"]), ("Cleared this line in under 50% of recent games", lambda l: (_cleared_pct(l["warn"]) or 100) < 50),
      ("Cleared this line in 50-65% of recent games", lambda l: 50 <= (_cleared_pct(l["warn"]) if _cleared_pct(l["warn"]) is not None else -1) < 65),
      ("Far from FanDuel's main line", lambda l: "far from market" in l["warn"]), ("Projection well above season avg", lambda l: "above season avg" in l["warn"]),
      ("Projection below season avg", lambda l: "below season avg" in l["warn"]), ("Questionable / first game back", lambda l: "Questionable" in l["warn"] or "First game back" in l["warn"]),
      ("Teammate returning", lambda l: "Teammate returning" in l["warn"]), ("QB rush line at/above his average", lambda l: "QB rush line" in l["warn"]),
      ("Small sample (fewer than 4 games)", lambda l: "Fewer than" in l["warn"]), ("History cuts the hit %", lambda l: "History cuts" in l["warn"]),
      ("Builder flags: cold streak / snaps / next man up / rising", lambda l: any(k in l["warn"] for k in ("Trending down", "Usage falling", "Snap share slipping", "Next man up", "Fill-in", "Rising:")))]
# matchup buckets, leak-free: the opponent's allowed-per-game to the player's position in that stat, from game-log weeks BEFORE the leg's week
# (bottom 6 = tough, top 6 = soft - the same cut the builder's matchup flag uses). Snapshot rows carry no matchup column, so it is rebuilt here.
MSTAT = {"Passing Yards": "Pass Yds", "Rushing Yards": "Rush Yds", "Receiving Yards": "Rec Yds", "Receptions": "Receptions", "Longest Reception": "Rec Yds", "Anytime TD": None, "Rush + Rec Yards": None}
_MU = {}
try:
    _gl = vals("gamelog.json"); _GH = {c: i for i, c in enumerate(_gl[0])}
    _pos = {}; _rows = []
    for r in _gl[1:]:
        if len(r) <= _GH["Rec Yds"] or num(r[0]) is None: continue
        _pos.setdefault(r[1], r[3]); _rows.append(r)
    def matchup(l):
        st = MSTAT.get(l["market"]); pos = _pos.get(l["player"])
        if not st or not pos or not l["opp"]: return None
        key = (l["week"], pos, st)
        if key not in _MU:
            tot = defaultdict(float); gms = defaultdict(set)
            for r in _rows:
                if r[3] == pos and (num(r[0]) or 99) < l["week"] and r[4]:
                    tot[r[4]] += num(r[_GH[st]]) or 0; gms[r[4]].add(r[0])
            per = {t: tot[t] / len(gms[t]) for t in tot if gms[t]}
            order = sorted(per, key=lambda t: per[t]); _MU[key] = ({*order[:6]}, {*order[-6:]}) if len(order) >= 20 else (set(), set())
        tough, soft = _MU[key]
        return "tough" if l["opp"] in tough else "soft" if l["opp"] in soft else "mid"
except Exception:
    def matchup(l): return None
MB = [("Tough matchup (opp bottom-6 vs that stat)", lambda l: matchup(l) == "tough"), ("Middle of the pack", lambda l: matchup(l) == "mid"), ("Soft coverage (opp top-6 allowed)", lambda l: matchup(l) == "soft")]
cal_match = calib_rows([(n, [l for l in L if f(l)]) for n, f in MB])
cal_edge = calib_rows([(n, [l for l in L if f(l)]) for n, f in EB]); cal_depth = calib_rows([(n, [l for l in L if f(l)]) for n, f in DB]); cal_warn = calib_rows([(n, [l for l in L if f(l)]) for n, f in WB])
brier = ""
if L and all(l["p"] is not None and l["book"] is not None for l in L[:50]):
    Lb = [l for l in L if l["p"] is not None and l["book"] is not None]
    def bs(w): return sum(((1 - w) * l["book"] + w * l["p"] - (l["res"] == "HIT")) ** 2 for l in Lb) / len(Lb)
    best = min((bs(w / 10), w / 10) for w in range(11))
    import calib as CALIB
    brier = f'<p class="fn">Brier score (lower is better): raw model {bs(1):.4f} · FanDuel price {bs(0):.4f} · the number the site shows ({CALIB.W_MODEL*100:.0f}% model / {100-CALIB.W_MODEL*100:.0f}% book, promoted 2026-10-20) {bs(CALIB.W_MODEL):.4f} · best blend {best[0]:.4f} at {best[1]*100:.0f}% model / {100-best[1]*100:.0f}% book. If a different weight wins two weeks running, calib.py moves.</p>'
calib_block = "" if not L else f"""<section class="card calib"><h2>Are the recommendations calibrated? <small>graded legs, hit rate vs what the model said</small></h2>
<p>The number on the right is hit rate minus model probability, in points. Near zero is honest; negative means the legs in that bucket hit less often than promised. This is the check that caught Week 6 (edge ≥ +10 legs hit 35% against a 67% model), and it now runs every Tuesday.</p>
<div class="calgrid"><div><h3>By edge</h3><ul class="bl">{cal_edge or "<li class='none'>Not enough legs yet.</li>"}</ul></div>
<div><h3>By line depth</h3><ul class="bl">{cal_depth or "<li class='none'>Not enough legs yet.</li>"}</ul></div>
<div><h3>By warning</h3><ul class="bl">{cal_warn or "<li class='none'>Not enough legs yet.</li>"}</ul></div>
<div><h3>By matchup</h3><ul class="bl">{cal_match or "<li class='none'>Not enough legs yet.</li>"}</ul></div></div>{brier}</section>"""

# ---- game calls vs the closing line (in/calls.json = 'AUTO - Model Calls Archive', in/games.csv = finals), latest pre-kickoff row per game ----
def calls_vs_line():
    import csv as _csv
    try:
        arc = vals("calls.json"); CH = {c: i for i, c in enumerate(arc[0])}
        fin = {}
        for g in _csv.DictReader(open(os.path.join(IN, "games.csv"))):
            if g["season"] == "2026" and g["game_type"] == "REG" and g.get("home_score") not in ("", None, "NA"):
                fin[(int(g["week"]), frozenset([g["away_team"], g["home_team"]]))] = (g["home_team"], float(g["home_score"]), float(g["away_score"]), g["gameday"] + "T" + g["gametime"])
    except Exception: return ""
    import re as _re
    from zoneinfo import ZoneInfo
    best = {}
    for r in arc[1:]:
        r = r + [""] * (29 - len(r))
        w = num(r[0]); a, b = r[CH["A"]], r[CH["B"]]
        if w is None or (int(w), frozenset([a, b])) not in fin: continue
        ht, hs, as_, ko = fin[(int(w), frozenset([a, b]))]
        kot = datetime.datetime.fromisoformat(ko).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(ZoneInfo("America/Chicago"))
        fz = _re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d)", str(r[1]))
        if fz and datetime.datetime.fromisoformat(fz.group(1)).replace(tzinfo=ZoneInfo("America/Chicago")) >= kot: continue
        best[(int(w), a, b)] = (r, (hs if ht == a else as_), (as_ if ht == a else hs))
    if not best: return ""
    def imp(o): return None if o is None or o == 0 else (100 / (o + 100) if o > 0 else -o / (-o + 100))
    W = defaultdict(lambda: {"ml": [0, 0], "fav": [0, 0], "spr": [0, 0], "tot": [0, 0], "dis": [0, 0], "mm": [], "km": [], "bm": [], "bk": []})
    for (w, a, b), (r, fa, fb) in best.items():
        g = lambda c: num(r[CH[c]]); m = fa - fb; t = fa + fb; d = W[w]
        pw, spA, fdt, mlA, mlB = g("Model P(A win) as shown"), g("FD spread (A)"), g("FD total"), g("FD ML A"), g("FD ML B")
        if pw is not None and m != 0:
            d["ml"][1] += 1; d["ml"][0] += int((m > 0) == (pw >= 0.5)); d["bm"].append((pw - (m > 0)) ** 2)
            if mlA is not None and mlB is not None:
                ia, ib = imp(mlA), imp(mlB); pk = ia / (ia + ib); fav_a = pk >= 0.5 if mlA != mlB else (spA or 0) < 0
                d["fav"][1] += 1; d["fav"][0] += int((m > 0) == fav_a); d["bk"].append((pk - (m > 0)) ** 2)
                if (pw >= 0.5) != fav_a: d["dis"][1] += 1; d["dis"][0] += int((m > 0) == (pw >= 0.5))
        pc = g("Model P(A covers) as shown")
        if pc is not None and spA is not None and m + spA != 0: d["spr"][1] += 1; d["spr"][0] += int(((m + spA) > 0) == (pc >= 0.5))
        po = g("Model P(over) as shown")
        if po is not None and fdt is not None and t != fdt: d["tot"][1] += 1; d["tot"][0] += int((t > fdt) == (po >= 0.5))
        if g("Model margin (A-B)") is not None: d["mm"].append(abs(g("Model margin (A-B)") - m))
        if spA is not None: d["km"].append(abs(-spA - m))
    def rec(x): return f"{x[0]}–{x[1]-x[0]}" if x[1] else "—"
    def avg(x): return f"{sum(x)/len(x):.1f}" if x else "—"
    def avg3(x): return f"{sum(x)/len(x):.3f}" if x else "—"
    tot = {"ml": [0, 0], "fav": [0, 0], "spr": [0, 0], "tot": [0, 0], "dis": [0, 0], "mm": [], "km": [], "bm": [], "bk": []}
    for d in W.values():
        for k in tot: tot[k] = [tot[k][0] + d[k][0], tot[k][1] + d[k][1]] if isinstance(tot[k], list) and len(tot[k]) == 2 and isinstance(d[k][0], int) else tot[k] + d[k]
    def row(label, d): return f'<tr><th>{E(str(label))}</th><td>{rec(d["ml"])}</td><td>{rec(d["fav"])}</td><td>{rec(d["dis"])}</td><td>{rec(d["spr"])}</td><td>{rec(d["tot"])}</td><td>{avg(d["mm"])} <small>vs {avg(d["km"])}</small></td><td>{avg3(d["bm"])} <small>vs {avg3(d["bk"])}</small></td></tr>'
    body = "".join(row(f"Week {w}", W[w]) for w in sorted(W)) + (row("Season", tot) if len(W) > 1 else "")
    return f"""<section class="card calib"><h2>Game calls vs the closing line <small>moneyline, spread and total, frozen before kickoff</small></h2>
<p>The honest test for the game model is not "how many winners" but "did it beat the closing line". Favourites = what FanDuel's closing moneyline picked; "where we disagreed" = games the model took the other side. Margin error and Brier show the model next to the market: lower is better, and the market is the bar to clear.</p>
<div class="tblwrap"><table class="season"><thead><tr><th></th><th>Model ML</th><th>FanDuel favourites</th><th>Where we disagreed</th><th>Spread</th><th>Total</th><th>Margin error <small>model vs line</small></th><th>Win Brier <small>model vs line</small></th></tr></thead><tbody>{body}</tbody></table></div>
<p class="fn">Backtest 2022–2026 (gen/gl_backtest.py, nflverse closing lines): no public pre-kick signal — rest, division game, road favourite, short week, QB change, recent form, prime time, dome — beats the closing moneyline out of sample; adjustments on top of the price made the Brier score worse in four of five seasons. Upset weeks like Week 6 (favourites 7–7 against an implied 9–5) are variance, not a missed signal, so the moneyline calls lean on the market and promos stay off mid-sized favourites.</p></section>"""
calls_block = calls_vs_line()

# ---- model vs market: the big disagreements, one row per side taken (owner 10/26) ----
# Display only - nothing here feeds picks. The 2022-26 backtest found no public signal that beats the closing line, so the model's
# game-line opinions are tracked, not trusted: every game where the frozen pre-kickoff model differed from FanDuel by
#   moneyline: model win % vs FanDuel's no-vig win % >= 10 points;  spread: model margin vs the line >= 3 points;  total: >= 3 points,
# with the result and 1 unit on the model's side at FanDuel's price (-110 for spreads / totals when the archive has no odds).
# Promotion rule (RUNBOOK): the model's side may count toward picks only after 40+ graded disagreements in a market show positive
# units AND a model Brier below the market's on those games, in two separate halves of the sample.
def disagreements_block():
    import csv as _csv, re as _re
    from zoneinfo import ZoneInfo
    try:
        arc = vals("calls.json"); CH = {c: i for i, c in enumerate(arc[0])}
        fin = {}
        for g in _csv.DictReader(open(os.path.join(IN, "games.csv"))):
            if g["season"] == "2026" and g["game_type"] == "REG" and g.get("home_score") not in ("", None, "NA"):
                fin[(int(g["week"]), frozenset([g["away_team"], g["home_team"]]))] = (g["home_team"], float(g["home_score"]), float(g["away_score"]), g["gameday"] + "T" + g["gametime"])
    except Exception: return ""
    best = {}
    for r in arc[1:]:
        r = r + [""] * (29 - len(r)); w = num(r[0]); a, b = r[CH["A"]], r[CH["B"]]
        if w is None or (int(w), frozenset([a, b])) not in fin: continue
        ht, hs, as_, ko = fin[(int(w), frozenset([a, b]))]
        kot = datetime.datetime.fromisoformat(ko).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(ZoneInfo("America/Chicago"))
        fz = _re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d)", str(r[1]))
        if fz and datetime.datetime.fromisoformat(fz.group(1)).replace(tzinfo=ZoneInfo("America/Chicago")) >= kot: continue
        best[(int(w), a, b)] = (r, (hs if ht == a else as_), (as_ if ht == a else hs))
    def imp(o): return None if o is None or o == 0 else (100 / (o + 100) if o > 0 else -o / (-o + 100))
    def payout(o): return (o / 100 if o > 0 else 100 / -o) if o else 100 / 110
    rows, T = [], {"ml": [0, 0, 0.0], "spr": [0, 0, 0.0], "tot": [0, 0, 0.0]}
    for (w, a, b), (r, fa, fb) in sorted(best.items()):
        g = lambda c: num(r[CH[c]]); m = fa - fb; t = fa + fb; res = f"{a} {fa:g} – {b} {fb:g}"
        pw, mlA, mlB, mm, spA, mt, fdt, so, oo = g("Model P(A win) as shown"), g("FD ML A"), g("FD ML B"), g("Model margin (A-B)"), g("FD spread (A)"), g("Model total"), g("FD total"), g("FD spread odds (A)"), g("FD over odds")
        if pw is not None and mlA is not None and mlB is not None and m != 0:
            ia, ib = imp(mlA), imp(mlB); pk = ia / (ia + ib)
            if abs(pw - pk) >= 0.10:
                side_a = pw > pk; won = (m > 0) == side_a; o = mlA if side_a else mlB; u = payout(o) if won else -1.0
                T["ml"][0] += won; T["ml"][1] += 1; T["ml"][2] += u
                rows.append((w, f"{a}-{b}", "Moneyline", f"{a if side_a else b} to win · model {(pw if side_a else 1-pw)*100:.0f}%", f"{(pk if side_a else 1-pk)*100:.0f}% ({o:+.0f})", res, won, u))
        if mm is not None and spA is not None and abs(mm + spA) >= 3 and m + spA != 0:
            side_a = (mm + spA) > 0; won = ((m + spA) > 0) == side_a; u = payout(so if side_a and so else None) if won else -1.0
            T["spr"][0] += won; T["spr"][1] += 1; T["spr"][2] += u
            ln = spA if side_a else -spA
            rows.append((w, f"{a}-{b}", "Spread", f"{a if side_a else b} {ln:+g} (model: {a if mm > 0 else b} by {abs(mm):.1f})", f"line {a} {spA:+g}", res, won, u))
        if mt is not None and fdt is not None and abs(mt - fdt) >= 3 and t != fdt:
            over = mt > fdt; won = (t > fdt) == over; u = payout(oo if over and oo else None) if won else -1.0
            T["tot"][0] += won; T["tot"][1] += 1; T["tot"][2] += u
            rows.append((w, f"{a}-{b}", "Total", f"{'Over' if over else 'Under'} {fdt:g} (model {mt:.1f})", f"total {fdt:g}", res, won, u))
    if not rows: return ""
    def tl(k, lab): x = T[k]; return f'<tr><th>{lab}</th><td><b>{x[0]}–{x[1]-x[0]}</b></td><td>{x[2]:+.1f}u</td><td>{x[1]} / 40</td></tr>' if x[1] else f'<tr><th>{lab}</th><td>—</td><td></td><td>0 / 40</td></tr>'
    body = "".join(f'<tr><td>W{w}</td><td>{E(gm)}</td><td>{E(mk)}</td><td>{E(mv)}</td><td>{E(mkt)}</td><td>{E(res)}</td><td class="{"up" if won else "dn"}">{"✓" if won else "✗"} {u:+.2f}u</td></tr>' for w, gm, mk, mv, mkt, res, won, u in sorted(rows, key=lambda x: (-x[0], x[1])))
    return f"""<section class="card calib"><h2>Model vs market <small>the big disagreements, tracked - not bet</small></h2>
<p>Every game where the model's frozen pre-kickoff view was far from FanDuel's: 10+ points apart on the win chance, or 3+ points apart on the margin or the total. One unit on the model's side at FanDuel's price shows whether those disagreements are worth anything. Until a market clears 40 graded disagreements with positive units and a better Brier score than the market in both halves of the sample, these opinions do not feed any pick on the site.</p>
<div class="tblwrap"><table class="season" style="min-width:0;width:100%"><thead><tr><th>Season</th><th>Record</th><th>1u each</th><th>Graded</th></tr></thead><tbody>{tl("ml", "Moneyline")}{tl("spr", "Spread")}{tl("tot", "Total")}</tbody></table></div>
<details><summary>Game by game ({len(rows)})</summary><div class="tblwrap"><table class="season"><thead><tr><th>Wk</th><th>Game</th><th>Market</th><th>Model side</th><th>FanDuel</th><th>Final</th><th>1u</th></tr></thead><tbody>{body}</tbody></table></div></details>
</section>"""
try: disagree_block = disagreements_block()
except Exception as _e: print("warn: disagreements block skipped:", _e); disagree_block = ""

# ---- closing line value (owner 10/27): did FanDuel's price move toward the side the model liked between our freeze and kickoff? ----
# in/closing.json = 'V2 - Closing Lines' (ClosingLines.gs keeps the last pre-kickoff FanDuel price per week + line). A leg's CLV = closing
# implied % minus the implied % we froze at. For a leg the model liked (raw edge >= +5) a positive move means the market came our way.
def clv_block():
    try: cl = vals("closing.json"); lf = vals("legsnaps.json")
    except Exception: return ""
    if len(cl) < 2 or len(lf) < 2: return ""
    CH = {c: i for i, c in enumerate(cl[0])}; LH = {c: i for i, c in enumerate(lf[0])}
    close = {}
    for r in cl[1:]:
        r = r + [""] * (len(cl[0]) - len(r)); w = num(r[CH["Week"]]); ci = num(r[CH["Close implied"]])
        if w is None or ci is None: continue
        close[(int(w), str(r[CH["Key"]]).strip().lower())] = (ci, str(r[CH["Pulled at (CT)"]]))
    rows = []
    for r in lf[1:]:
        r = r + [""] * (len(lf[0]) - len(r))
        if str(r[LH["Latest Snapshot"]]).upper() != "TRUE": continue
        w = num(r[0]); fi = num(r[LH["Book implied %"]]); raw = num(r[LH["Raw model %"]])
        if w is None or fi is None or raw is None: continue
        ln = num(r[LH["Line (X+)"]]); k = f'{str(r[LH["Player"]]).strip().lower()}|{r[LH["Market"]]}|{int(ln) if ln is not None and ln == int(ln) else r[LH["Line (X+)"]]}'
        c = close.get((int(w), k.lower()))
        if not c or c[1][:16] <= str(r[LH["Frozen At"]])[:16]: continue   # need a price pulled after we froze
        rows.append({"w": int(w), "m": r[LH["Market"]], "edge": raw - fi, "mv": c[0] - fi})
    if len(rows) < 30: return f'<section class="card calib"><h2>Did the market move our way? <small>closing line value</small></h2><p>Collecting FanDuel\'s last price before kickoff for every frozen leg ({len(rows)} matched so far). This fills in after the next slate.</p></section>'
    def summ(rs):
        liked = [x for x in rs if x["edge"] >= 0.05]; faded = [x for x in rs if x["edge"] <= -0.05]
        mv = [x for x in rs if abs(x["mv"]) >= 0.01 and abs(x["edge"]) >= 0.02]
        agree = sum(1 for x in mv if (x["mv"] > 0) == (x["edge"] > 0))
        f = lambda xs: (sum(1 for x in xs if x["mv"] > 0.005) / len(xs) * 100, sum(x["mv"] for x in xs) / len(xs) * 100) if xs else (None, None)
        return len(rs), f(liked), len(liked), f(faded), len(faded), (agree / len(mv) * 100 if mv else None), len(mv)
    def cells(s):
        n, (lb, lm), nl, (fb, fm), nf, ag, nm = s
        p = lambda v, d=0: "—" if v is None else f"{v:.{d}f}"
        return (f'<td>{n}</td><td>{p(lb)}% <small>({nl})</small></td><td class="{"pos" if (lm or 0) > 0 else "neg"}">{"" if lm is None else f"{lm:+.1f}"}</td>'
                f'<td>{p(fb)}% <small>({nf})</small></td><td><b>{p(ag)}%</b> <small>({nm})</small></td>')
    mk = sorted({x["m"] for x in rows}, key=lambda m: -sum(1 for x in rows if x["m"] == m))
    body = f'<tr><td><b>All legs</b></td>{cells(summ(rows))}</tr>' + "".join(f'<tr><td>{E(m)}</td>{cells(summ([x for x in rows if x["m"] == m]))}</tr>' for m in mk if sum(1 for x in rows if x["m"] == m) >= 20)
    wk = sorted({x["w"] for x in rows})
    return f"""<section class="card calib"><h2>Did the market move our way? <small>closing line value · weeks {", ".join(map(str, wk))}</small></h2>
<p>Wins and losses on a week of legs are noisy; whether FanDuel's price moves toward our side between our pre-kickoff freeze and kickoff is the quickest honest read on real edge. <b>Market agreed</b> = of the legs whose price moved at least a point, the share that moved the way the model leaned (shorter when the model liked the over, longer when it faded it). Above 50% means the model sees things before the market prices them.</p>
<div class="tblwrap"><table class="season" style="min-width:0;width:100%"><thead><tr><th>Market</th><th>Legs</th><th>Liked: price shortened</th><th>Liked: avg move (pts)</th><th>Faded: price shortened</th><th>Market agreed</th></tr></thead><tbody>{body}</tbody></table></div>
</section>"""
# ---- Model's Best scorecard (owner 10/27): the tier frozen before kickoff ('V2 - Model Best Picks', in/bestpicks.json), graded from the game log ----
def best_block():
    try: bp = vals("bestpicks.json"); gl = vals("gamelog.json")
    except Exception: return ""
    if len(bp) < 2 or len(gl) < 2: return ""
    BH = {c: i for i, c in enumerate(bp[0])}; GH = {c: i for i, c in enumerate(gl[0])}
    act = {}
    for r in gl[1:]:
        r = r + [""] * (len(gl[0]) - len(r)); w = num(r[0])
        if w is None: continue
        g = lambda c: num(r[GH[c]]) if c in GH else None
        act[(int(w), str(r[GH["Player"]]).strip().lower())] = {"Passing Yards": g("Pass Yds"), "Rushing Yards": g("Rush Yds"), "Receiving Yards": g("Rec Yds"),
            "Receptions": g("Receptions"), "Anytime TD": (g("Rush TD") or 0) + (g("Rec TD") or 0)}
    last = {}
    for r in bp[1:]:
        r = r + [""] * (len(bp[0]) - len(r)); w = num(r[BH["Week"]])
        if w is None: continue
        if str(r[BH["Kickoff (CT)"]])[:16] and str(r[BH["Frozen at (CT)"]])[:16] >= str(r[BH["Kickoff (CT)"]])[:16]: continue
        last[(int(w), r[BH["Player"]], r[BH["Market"]], str(r[BH["Line"]]))] = r
    T = defaultdict(lambda: [0, 0, 0.0])   # (tier, week) -> n, hits, units
    for (w, pl, mk, ln), r in last.items():
        a = act.get((w, str(pl).strip().lower()))
        if not a: continue   # no stat row yet (not played / not final) - never graded as a miss
        under = str(mk).startswith("Under "); base = mk[6:] if under else mk
        v = a.get(base); line = num(ln); o = num(r[BH["Odds"]])
        if v is None or line is None or o is None: continue
        hit = (v < line) if under else (v >= 1 if base == "Anytime TD" else v >= line)
        tier = r[BH["Tier"]] + (" (unders)" if under else "")
        for key in ((tier, w), (tier, 0)):
            d = T[key]; d[0] += 1; d[1] += int(hit); d[2] += ((o / 100) if o > 0 else (100 / -o)) if hit else -1.0
    if not T: return '<section class="card calib"><h2>Model\'s Best <small>graded</small></h2><p>The tier is frozen before every kickoff from Week 8 on; the first grades land next Tuesday.</p></section>'
    lab = {"even": "Even money · overs", "even (unders)": "Even money · unders", "td": "Touchdowns", "safe": "Safer (65%+)"}
    weeks = sorted({w for _, w in T if w})
    rows = ""
    for tier in ("even (unders)", "even", "td", "safe"):
        if (tier, 0) not in T: continue
        cells = "".join(f'<td>{T[(tier, w)][1]}–{T[(tier, w)][0]-T[(tier, w)][1]}</td>' if (tier, w) in T else "<td>—</td>" for w in weeks)
        n, h, u = T[(tier, 0)]
        rows += f'<tr><td>{lab.get(tier, tier)}</td>{cells}<td><b>{h/n*100:.0f}%</b> <small>({n})</small></td><td style="color:var({"--good" if u >= 0 else "--bad"});font-weight:700;white-space:nowrap">{u:+.1f}u ({u/n*100:+.0f}%)</td></tr>'
    return f"""<section class="card calib"><h2>Model's Best <small>graded · frozen before kickoff</small></h2>
<p>The tier the home page and builder lead with: lines near even money where the model is 8+ points off FanDuel (mostly unders), touchdowns the model likes, and safer 65%+ legs. Graded from the box scores at the frozen FanDuel price, 1 unit each. Break-even at −110 is 52.4%.</p>
<div class="tblwrap"><table class="season" style="min-width:0;width:100%"><thead><tr><th>Tier</th>{"".join(f"<th>Wk {w}</th>" for w in weeks)}<th>Hit</th><th>Units</th></tr></thead><tbody>{rows}</tbody></table></div></section>"""
try: best_html = best_block()
except Exception as _e: print("warn: Model's Best block skipped:", _e); best_html = ""
# owner 11/5 "our own record on game lines": research/gl_disagree.py rebuilds our formula walk-forward (with the 11/5 injury adjustment) and
# grades it against the closing spread / total when they disagree. Reads out/gl_disagree.json (Tuesday step) or the committed research copy.
def gl_record_block():
    for p in (os.path.join(OUT, "gl_disagree.json"), os.path.join(HERE, "research", "gl_disagree.json")):
        if os.path.exists(p): J = json.load(open(p)); break
    else: return ""
    pc = lambda a: (f'{a[0]}-{a[1]-a[0]} <small>({a[0]/a[1]*100:.0f}%)</small>' if a[1] else "-")
    rows = "".join(f'<tr><td><b>{s}</b></td>' + "".join(f'<td>{pc(J["by_season"][s][g]["side"])}</td><td>{pc(J["by_season"][s][g]["total"])}</td>' for g in ("3", "5")) + '</tr>' for s in sorted(J["by_season"]))
    al = J["by_gap"]
    rows += '<tr><td><b>All</b></td>' + "".join(f'<td><b>{pc(al[g]["side"])}</b></td><td><b>{pc(al[g]["total"])}</b></td>' for g in ("3", "5")) + '</tr>'
    wk = "".join(f'<span>W{w}: {J["2026_weeks"][w]["side"][0]}-{J["2026_weeks"][w]["side"][1]-J["2026_weeks"][w]["side"][0]} sides</span> ' for w in sorted(J["2026_weeks"], key=int) if J["2026_weeks"][w]["side"][1])
    s3 = al["3"]["side"]; verdict = "the line has been right more often - do not bet a side just because our number differs" if s3[1] and s3[0] / s3[1] < 0.524 else "our number has beaten the line - worth a look when they disagree"
    return (f'<section class="card calib"><h2>Our number vs the line <small>game sides and totals · 2023-2026, walk-forward</small></h2>'
            f'<p>Our own team-score formula (season averages, injury-adjusted) against the closing spread and total, only in games where they disagree (3+ or 5+ points apart). Break-even at -110 is 52.4%. So far: {verdict}.</p>'
            f'<div class="tblwrap"><table class="season" style="min-width:0;width:100%"><thead><tr><th>Season</th><th>Side 3+</th><th>Total 3+</th><th>Side 5+</th><th>Total 5+</th></tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p style="font-size:12px;color:var(--mute)">2026 by week (3+ pts apart): {wk}</p></section>')
try: gl_html = gl_record_block()
except Exception as _e: print("warn: game-line record skipped:", _e); gl_html = ""
try: clv_html = clv_block()
except Exception as _e: print("warn: CLV block skipped:", _e); clv_html = ""

# ---- confidence grades, graded (owner 10/26): did LOW games really miss more, and was the market's read better there? ----
def conf_block():
    import csv as _csv
    from zoneinfo import ZoneInfo
    try: arc = vals("confarc.json")
    except Exception: return ""
    if len(arc) < 2: return ""
    H = {c: i for i, c in enumerate(arc[0])}
    fin = {}
    for g in _csv.DictReader(open(os.path.join(IN, "games.csv"))):
        if g["season"] == "2026" and g["game_type"] == "REG" and g.get("home_score") not in ("", None, "NA"):
            fin[(int(g["week"]), frozenset([g["away_team"], g["home_team"]]))] = (g["home_team"], float(g["home_score"]), float(g["away_score"]), g["gameday"] + "T" + g["gametime"])
    best = {}
    for r in arc[1:]:
        r = r + [""] * (len(arc[0]) - len(r)); w = num(r[0]); a, b = r[H["A"]], r[H["B"]]
        if w is None or (int(w), frozenset([a, b])) not in fin: continue
        ht, hs, as_, ko = fin[(int(w), frozenset([a, b]))]
        kot = datetime.datetime.fromisoformat(ko).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(ZoneInfo("America/Chicago"))
        try:
            if datetime.datetime.fromisoformat(str(r[1])[:16]).replace(tzinfo=ZoneInfo("America/Chicago")) >= kot: continue
        except Exception: continue
        best[(int(w), a, b)] = (r, (hs if ht == a else as_) - (as_ if ht == a else hs))
    if not best: return ""
    G = defaultdict(lambda: [0, 0.0, 0.0, 0])   # grade -> n, our margin miss, market margin miss, n with a market line
    rows = []
    for (w, a, b), (r, m) in sorted(best.items()):
        gr = r[H["Grade"]]; pa, pb, sp = num(r[H["Model A pts"]]), num(r[H["Model B pts"]]), num(r[H["FD spread (A)"]])
        if pa is None or pb is None: continue
        ours = abs((pa - pb) - m); d = G[gr]; d[0] += 1; d[1] += ours
        mk = abs(-sp - m) if sp is not None else None
        if mk is not None: d[2] += mk; d[3] += 1
        rows.append(f'<tr><td>{w}</td><td>{E(a)}-{E(b)}</td><td>{E(gr)}</td><td>{ours:.1f}</td><td>{"" if mk is None else format(mk, ".1f")}</td><td style="text-align:left;white-space:normal;font-size:11px">{E(str(r[H["Flags"]])[:220])}</td></tr>')
    tl = "".join(f'<tr><td>{g}</td><td>{G[g][0]}</td><td>{G[g][1]/G[g][0]:.1f}</td><td>{(G[g][2]/G[g][3]) if G[g][3] else 0:.1f}</td></tr>' for g in ("HIGH", "MEDIUM", "LOW") if G[g][0])
    return f"""<section class="card calib"><h2>Game confidence, graded <small>does a LOW grade really mean "trust the market"?</small></h2>
<p>Every game card carries a confidence grade (market gap, line moves, QB changes, newly-out players, boom/bust QBs). Here is how far off our projected margin and FanDuel's spread were, by grade, using the last grade set before kickoff. If the flags work, the LOW row misses by far more than the HIGH row, and the market's miss stays smaller than ours there.</p>
<div class="tblwrap"><table class="season" style="min-width:0;width:100%"><thead><tr><th>Grade</th><th>Games</th><th>Our avg miss</th><th>Market's avg miss</th></tr></thead><tbody>{tl}</tbody></table></div>
<details><summary>Game by game ({len(rows)})</summary><div class="tblwrap"><table class="season"><thead><tr><th>Wk</th><th>Game</th><th>Grade</th><th>Our miss</th><th>Market miss</th><th>Flags</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></details>
</section>"""
try: conf_graded = conf_block()
except Exception as _e: print("warn: confidence block skipped:", _e); conf_graded = ""

arch = ""
try:
    a = [r for r in vals("archive.json")[1:] if len(r) >= 3 and str(r[2]).startswith("http")]
    arch = "".join(f'<li><span class="bl-p"><a href="{E(r[2])}">Week {E(r[0])} receipt</a></span><span class="bl-m">{E(r[3] if len(r)>3 else "")}</span></li>' for r in sorted(a, key=lambda r: -(num(r[0]) or 0)))
except Exception: pass
legs_line = f'{tot[1]}–{tot[0]-tot[1]} ({tot[1]/tot[0]*100:.0f}%) · {tot[2]:+.2f}u · clean {cl[1]}–{cl[0]-cl[1]}' if tot[0] else "no legs graded yet"
# promoted bets, season to date (the slips we actually posted, at posted FanDuel odds) - the honest headline next to the leg pool
promo_line = ""
try:
    PRW = defaultdict(lambda: [0, 0, 0.0])
    for r in vals("promos.json")[1:]:
        r = list(r) + [""] * (10 - len(r)); res = str(r[8]).strip().upper()
        if num(r[0]) is None or res not in ("HIT", "WON", "WIN", "MISSED", "MISS", "LOST", "LOSS"): continue
        hit = res in ("HIT", "WON", "WIN"); fdo = num(r[4]); dec = (fdo / 100 + 1) if fdo and fdo > 0 else (100 / -fdo + 1) if fdo else None
        d = PRW[int(num(r[0]))]; d[0] += 1; d[1] += hit; d[2] += ((dec - 1) if hit else -1.0) if dec else (0.0 if hit else -1.0)
    if PRW:
        n_ = sum(d[0] for d in PRW.values()); h_ = sum(d[1] for d in PRW.values()); u_ = sum(d[2] for d in PRW.values())
        promo_line = f'<span class="k">Promoted bets</span><span>{h_}–{n_-h_} · {u_:+.1f}u at posted odds · ' + ", ".join(f"Wk {w} {d[1]}–{d[0]-d[1]}" for w, d in sorted(PRW.items())) + '</span>'
except Exception: pass
head_mae = allrow["All skill"][0]
summary = f'''<section class="card summary" id="summary">
 <header class="hd">{PLAYS}<div class="tm a"><b>Season</b><span>2026 · receipts to date</span></div>
  <div class="score"><span class="pt">{"" if head_mae is None else f"{head_mae:.1f}"}</span><small>avg fantasy points off per player · frozen weeks · {allrow["All skill"][2]} player-games</small>{SWOOSH}</div>
  <div class="tm b"><img class="bsmark" src="data:image/png;base64,{LOGO_S}" alt="BS"><span>BetSweep model</span></div></header>
 <div class="ginfo"><span class="k">FanDuel legs</span><span>{legs_line}</span><span class="k">Weeks graded</span><span>{", ".join(str(w) for w in weeks)}</span>{promo_line}</div>
 <div class="chartwrap">{chart()}</div>
 {table}
 <div class="sumgrid">
  <div><h3>Legs by week <small>frozen pre-kickoff, 1u each</small></h3><ul class="bl">{legs_week}</ul></div>
  <div><h3>Legs by market</h3><ul class="bl">{legs_mkt}</ul></div>
  <div><h3>Weekly receipts</h3><ul class="bl">{arch or "<li class='none'>none published yet</li>"}</ul></div>
 </div>
 <footer class="ft"><span class="brand"><img src="data:image/png;base64,{LOGO_S}" alt=""><span>BetSweep</span></span><span>Picks. Data. Edge. Sweep.</span><button class="snap" type="button" data-target="summary">Copy card as image</button><button class="snap story" type="button" data-target="summary">Story 9:16</button></footer>
</section>
{calib_block}
{best_html}{clv_html}{gl_html}{calls_block}{conf_graded}{disagree_block}'''
stamp = datetime.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p")
page = (open(os.path.join(HERE, "template.html")).read()
        .replace("<title>BetSweep Matchup Boards</title>", "<title>BetSweep Season Receipt</title>")
        .replace("<h1>Week {{WEEK}} · <b>Matchup Boards</b></h1>", "<h1>2026 · <b>Season Receipt</b></h1>")
        .replace("{{DESC}}", f"Built {stamp} CT. How the model has done week by week: projection error by position and the FanDuel leg record, all from snapshots frozen before kickoff.")
        .replace("{{NAV}}", '<a href="https://claude.ai/artifact/RTTqiN3sdMHGgojimQ9hZv">← This week\'s boards</a>').replace("{{CARDS}}", summary)
        .replace("{{LOGO}}", LOGO).replace("{{BANNER}}", BANNER).replace("{{WEEK}}", "").replace("{{STAMP}}", stamp).replace("{{ARCHIVE}}", ""))
import re
page = re.sub(r'<div class="key">.*?</div>\n', '', page, count=1, flags=re.S)
out = os.path.join(OUT, "season-receipt.html"); open(out, "w").write(page)
print(f"wrote {out}: weeks {weeks}, legs {tot[0]}")
