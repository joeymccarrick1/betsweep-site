#!/usr/bin/env python3
"""BetSweep weekly results page ("the receipt") — v2026-10-14.
Inputs: in/results.json ('V2 - Boards Results Feed'!A1:AG1200: latest frozen projections + actuals for the week just played),
        in/results_legs.json ('V2 - Boards Results Feed'!AJ1:BK3000: graded FanDuel legs for that week, may be empty - read the whole tab, a week can carry 1,700+ legs),
        in/games.csv (nflverse schedule with final scores), in/promos.json ('PROMO - Promoted Bets', the graded slips we posted that week), plus template assets next to this script.
Output: out/results-week<W>.html. Prints "wrote ... week W: N games, P players, L legs".
"""
import json, html, csv, os, datetime, statistics
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
E = html.escape
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def num(x):
    try: return float(str(x).replace("%", "").replace("+", "").replace(",", ""))
    except: return None
exec(open(os.path.join(HERE, "brand.py")).read())   # NAMES, TEAMCOL, badge(), PLAYS, SWOOSH, LOGO, LOGO_S, BANNER

feed = vals("results.json"); hdr = feed[0]; H = {c: i for i, c in enumerate(hdr)}
rows = [r + [""] * (33 - len(r)) for r in feed[1:] if len(r) > 5 and r[4]]
if not rows: raise SystemExit("no snapshot rows in the feed")
WEEK = int(float(rows[0][H["Week"]]))
try:
    lf = vals("results_legs.json"); LH = {c: i for i, c in enumerate(lf[0])}
    legs = [r + [""] * (28 - len(r)) for r in lf[1:] if len(r) > 3 and r[2] and r[0] not in ("", "no leg rows for that week")]
except Exception:
    legs, LH = [], {}

GAMES = {}
with open(os.path.join(IN, "games.csv"), newline="") as f:
    for g in csv.DictReader(f):
        if g["season"] == "2026" and g["week"] == str(WEEK) and g["game_type"] == "REG":
            GAMES[frozenset([g["away_team"], g["home_team"]])] = g

# ---- per-player records ----
P = []
for r in rows:
    has = str(r[H["Has Stat Row"]]).upper() == "TRUE"
    P.append({"pos": r[H["Pos"]], "name": r[H["Player"]], "team": r[H["Team"]], "opp": r[H["Opp"]], "proj": num(r[H["Proj Fantasy Pts"]]) or 0,
              "act": num(r[H["Act Fantasy Pts"]]) if has else None, "has": has, "type": r[H["Snapshot Type"]],
              "a_py": r[H["Act Pass Yds"]], "a_ry": r[H["Act Rush Yds"]], "a_rec": r[H["Act Rec"]], "a_rcy": r[H["Act Rec Yds"]],
              "a_td": (num(r[H["Act Pass TD"]]) or 0) + (num(r[H["Act Rush TD"]]) or 0) + (num(r[H["Act Rec TD"]]) or 0) if has else None,
              "p_py": r[H["Proj Pass Yds"]], "p_ry": r[H["Proj Rush Yds"]], "p_rec": r[H["Proj Rec"]], "p_rcy": r[H["Proj Rec Yds"]]})
graded = [p for p in P if p["has"] and p["act"] is not None]
for p in P: p["late"] = "AFTER" in str(p["type"]).upper()
pre = [p for p in graded if not p["late"]]
def mae(ps): return statistics.mean(abs(p["proj"] - p["act"]) for p in ps) if ps else None
by_pos = {pos: mae([p for p in pre if p["pos"] == pos]) for pos in ("QB", "RB", "WR", "TE")}
beats = sorted([p for p in graded if p["proj"] >= 5], key=lambda p: -(p["act"] - p["proj"]))[:5]
busts = sorted([p for p in graded if p["proj"] >= 8], key=lambda p: (p["act"] - p["proj"]))[:5]
nailed = sorted([p for p in graded if p["proj"] >= 10], key=lambda p: abs(p["act"] - p["proj"]))[:5]

# ---- legs ----
L = []
for r in legs:
    res = r[LH["Result"]].upper() if "Result" in LH else ""
    if res not in ("HIT", "MISS"): continue
    L.append({"player": r[LH["Player"]], "market": r[LH["Market"]], "line": r[LH["Line (X+)"]], "odds": r[LH["FanDuel odds"]], "team": r[LH["Team"]], "opp": r[LH["Opp"]],
              "p": num(r[LH["Model % (hist-adj)"]]), "book": num(r[LH["Book implied %"]]), "res": res, "units": num(r[LH["Units (1u)"]]) or 0, "actual": r[LH["Actual"]], "warn": r[LH["Warnings"]]})
def pct(v): return None if v is None else (v / 100 if v > 1.5 else v)
for l in L: l["p"] = pct(l["p"]); l["book"] = pct(l["book"])
hits = sum(1 for l in L if l["res"] == "HIT"); units = sum(l["units"] for l in L)
clean = [l for l in L if not l["warn"]]; clean_hits = sum(1 for l in clean if l["res"] == "HIT")
mk = defaultdict(lambda: [0, 0, 0.0])
for l in L: mk[l["market"]][0] += 1; mk[l["market"]][1] += (l["res"] == "HIT"); mk[l["market"]][2] += l["units"]

# ---- plain scorecard numbers ----
def avgp(ls, k): v = [l[k] for l in ls if l.get(k) is not None]; return (sum(v) / len(v)) if v else None
def within(ps, k): return (sum(1 for p in ps if abs(p["proj"] - p["act"]) <= k) / len(ps)) if ps else None
def bias(ps): return statistics.mean(p["proj"] - p["act"] for p in ps) if ps else None
def stat_mae(col, pos=None):
    v = [num(r[H[col]]) for r in rows if str(r[H["Has Stat Row"]]).upper() == "TRUE" and "AFTER" not in str(r[H["Snapshot Type"]]).upper() and (pos is None or r[H["Pos"]] in pos) and num(r[H[col]]) is not None]
    return (statistics.mean(v), len(v)) if v else (None, 0)
PROPS = ("Receiving Yards", "Rushing Yards", "Receptions", "Passing Yards", "Longest Reception", "Anytime TD", "First TD")
GL_MK = ("Moneyline", "Spread", "Total")
def rec_of(ls): h = sum(1 for l in ls if l["res"] == "HIT"); return h, len(ls) - h, (h / len(ls)) if ls else None, sum(l["units"] for l in ls)
edge5 = [l for l in L if not l["warn"] and l["p"] is not None and l["book"] is not None and l["p"] - l["book"] >= 0.05]
try:
    CJ = json.load(open(os.path.join(OUT, f"calls_week{WEEK}.json"))); CS = CJ["summary"]
except Exception: CJ, CS = None, None
def crec(k): return (CS[k][0], CS[k][1] - CS[k][0], (CS[k][0] / CS[k][1]) if CS[k][1] else None) if CS and CS.get(k) and CS[k][1] else None

# ---- render ----
POSORD = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "K": 4}
def delta_html(p):
    if p["act"] is None: return '<span class="na">no stat row</span>'
    d = p["act"] - p["proj"]; cls = "up" if d >= 0 else "down"
    return f'<span class="dl {cls}">{d:+.1f}</span>'
def actline(p):
    if p["act"] is None: return ""
    if p["pos"] == "K": return "kicker"
    if p["pos"] == "QB": return f'{p["a_py"]} pass yds · {p["a_ry"]} rush · {p["a_td"]:.0f} TD'
    if p["pos"] == "RB": return f'{p["a_ry"]} rush yds · {p["a_rec"]} rec, {p["a_rcy"]} yds · {p["a_td"]:.0f} TD'
    return f'{p["a_rec"]} rec · {p["a_rcy"]} yds · {p["a_td"]:.0f} TD'
def projline(p):
    if p["pos"] == "K": return ""
    if p["pos"] == "QB": return f'proj {p["p_py"]} / {p["p_ry"]}'
    if p["pos"] == "RB": return f'proj {p["p_ry"]} rush / {p["p_rec"]} rec, {p["p_rcy"]}'
    return f'proj {p["p_rec"]} rec / {p["p_rcy"]} yds'
def team_col(team, opp):
    ps = sorted([p for p in P if p["team"] == team], key=lambda p: (POSORD.get(p["pos"], 9), -p["proj"]))
    mx = max([max(p["proj"], p["act"] or 0) for p in ps] + [1])
    items = []; seen_pos = set()
    for p in ps:
        a = p["act"]; aw = (a / mx * 100) if a is not None else 0; pw = p["proj"] / mx * 100
        xtra = "" if p["pos"] not in seen_pos else " xtra"; seen_pos.add(p["pos"])
        late = '<span class="role note" title="This projection was frozen after the game had started (snapshot ran late); it is graded but does not count as a pre-kickoff call.">late freeze</span>' if p["late"] else ""
        items.append(f'''<li class="pl{xtra}"><span class="pos">{p["pos"]}</span>
 <div class="who"><span class="nm">{E(p["name"])}</span>{late}<span class="sl">{E(actline(p))}</span><span class="sl faint">{E(projline(p))}</span></div>
 <div class="cmp"><span class="nums"><b>{"" if a is None else f"{a:.1f}"}</b><small>proj {p["proj"]:.1f}</small>{delta_html(p)}</span>
  <i class="bar"><u style="--w:{pw:.0f}%"></u><s style="--w:{aw:.0f}%"></s></i></div></li>''')
    tl = [l for l in L if l["team"] == team]
    legs_html = "" if not tl else '<li class="glegs"><span>Legs</span>' + "".join(f'<em class="{l["res"].lower()}">{E(l["player"])} {E(l["market"].lower())} {l["line"]}+ <b>{l["res"]}</b><small>{l["actual"]}</small></em>' for l in tl) + '</li>'
    tp = [p for p in ps if p["act"] is not None]
    m = mae(tp); nlate = sum(1 for p in tp if p["late"])
    tag = f" · {nlate} late freeze" if nlate else ""
    return f'<ul class="col"><li class="dsum">{badge(team)}<span>{E(NAMES.get(team, team))}</span><span class="mini">{len(tp)} graded · PPR MAE {m:.1f}{tag}</span></li>{legs_html}{"".join(items)}</ul>'

teams = sorted({p["team"] for p in P})
pairs, seen = [], set()
for p in P:
    k = frozenset([p["team"], p["opp"]])
    if k in seen or p["opp"] not in teams: continue
    seen.add(k); pairs.append(k)
def calls_chip(a, b):
    if not CJ: return ""
    g = next((x for x in CJ["games"] if {x["a"], x["b"]} == {a, b}), None)
    if not g: return ""
    def m(h): return "✓" if h is True else ("✗" if h is False else "–")
    return f'<span>calls: ML {m(g["ml"][2])} · spread {m(g["spr"][3])} · total {m(g["tot"][3])} · script {m(g["scr_hit"])}</span>'
cards, nav = [], []
for k in pairs:
    g = GAMES.get(k); a, b = sorted(k)
    if g: a, b = g["away_team"], g["home_team"]
    gid = f"{a}-{b}"; nav.append(f'<a href="#{gid}">{a}·{b}</a>')
    if g and g.get("away_score"):
        sa, sb = num(g["away_score"]), num(g["home_score"]); score = f'<span class="pt">{sa:.0f}</span><span class="dash">–</span><span class="pt">{sb:.0f}</span><small>final · {E(g["stadium"])}</small>'
    else: score = '<span class="pt">—</span><small>final score not in the schedule feed yet</small>'
    gl = [l for l in L if l["team"] in (a, b)]; gh = sum(1 for l in gl if l["res"] == "HIT"); gu = sum(l["units"] for l in gl)
    rec = f'<span class="rec">Legs {gh}–{len(gl)-gh} · {gu:+.2f}u</span>' if gl else '<span class="rec faint">no frozen legs</span>'
    cards.append(f'''<section class="card" id="{gid}">
 <header class="hd">{PLAYS}<div class="tm a">{badge(a)}<b>{a}</b><span>{NAMES.get(a,a)}</span></div>
  <div class="score">{score}{SWOOSH}</div><div class="tm b">{badge(b)}<b>{b}</b><span>{NAMES.get(b,b)}</span></div></header>
 <div class="ginfo"><span class="k">{a} @ {b}</span><span>PPR miss {(mae([p for p in graded if p["team"] in (a, b)]) or 0):.1f} pts/player</span>{rec}{calls_chip(a, b)}</div>
 <div class="vbtns"><button type="button" class="vbtn" data-view="proj">Players: projection vs actual</button></div>
 <div class="cols">{team_col(a, b)}{team_col(b, a)}</div>
 <footer class="ft"><span class="brand"><img src="data:image/png;base64,{LOGO_S}" alt=""><span>BetSweep</span></span><span>Week {WEEK} receipt · frozen before kickoff, graded after</span><button class="snap more" type="button" data-target="{gid}">Show all players</button><button class="snap" type="button" data-target="{gid}">Copy card as image</button><button class="snap story" type="button" data-target="{gid}">Story 9:16</button></footer>
</section>''')

def li(p, kind):
    d = p["act"] - p["proj"]
    return f'<li><span class="bl-p">{E(p["name"])} <small>{p["pos"]} {p["team"]}</small></span><span class="bl-m">proj {p["proj"]:.1f} → actual {p["act"]:.1f}</span><b class="{"pos" if d>=0 else "neg"}">{d:+.1f}</b></li>'
mk_html = "".join(f'<li><span class="bl-p">{E(m)}</span><span class="bl-m">{v[1]}–{v[0]-v[1]} · {v[1]/v[0]*100:.0f}% hit</span><b class="{"pos" if v[2]>=0 else "neg"}">{v[2]:+.2f}u</b></li>' for m, v in sorted(mk.items(), key=lambda kv: -kv[1][0])) or "<li class='none'>No frozen FanDuel legs for this week (leg freezing started Week 6).</li>"
legs_line = (f'{hits}–{len(L)-hits} ({hits/len(L)*100:.0f}%) · {units:+.2f}u · clean legs {clean_hits}–{len(clean)-clean_hits}' if L else "no legs graded")
def tile(big, label, sub="", cls=""):
    return f'<div class="tile {cls}"><b>{big}</b><span>{E(label)}</span>{f"<small>{sub}</small>" if sub else ""}</div>'
def pctf(v): return "—" if v is None else f"{v*100:.0f}%"
lh, ll, lp, lu = rec_of(L); ch, cl_, cp, cu = rec_of(clean); eh, el, ep, eu = rec_of(edge5)
mp_all, bp_all = avgp(L, "p"), avgp(L, "book")
legs_tiles = (tile(f"{lh}–{ll}", "FanDuel legs we flagged", f"{pctf(lp)} hit · model said {pctf(mp_all)} · FanDuel's prices said {pctf(bp_all)} · {lu:+.1f}u at 1u each", "pos" if lu > 0 else "neg")
              + tile(f"{pctf(cp)}", "clean legs (no warnings)", f"{ch}–{cl_} · {cu:+.1f}u")
              + tile(f"{pctf(ep)}", "clean legs with edge ≥ +5", f"{eh}–{el} · model said {pctf(avgp(edge5, 'p'))} · {eu:+.1f}u")) if L else tile("—", "FanDuel legs", "Leg freezing started in Week 6; this week has no frozen legs to grade.")
rows_mk = ""
for m in PROPS + GL_MK:
    ls = [l for l in L if l["market"] == m]
    if not ls: continue
    h, lz, pr, u = rec_of(ls)
    rows_mk += f'<tr><td>{E(m)}</td><td>{h}–{lz}</td><td><b>{pctf(pr)}</b></td><td>{pctf(avgp(ls, "p"))}</td><td>{pctf(avgp(ls, "book"))}</td><td class="{"pos" if u >= 0 else "neg"}">{u:+.1f}u</td></tr>'
mk_table = f'<div style="overflow-x:auto;max-width:100%"><table class="sc" style="min-width:0;width:100%;font-size:12.5px"><thead><tr><th>Market</th><th>W–L</th><th>Hit</th><th>Model</th><th>Price</th><th>Units</th></tr></thead><tbody>{rows_mk}</tbody></table></div>' if rows_mk else ""
calls_tiles = ""
if CS:
    for key, label in (("ml", "moneyline leans"), ("spread", "spread leans"), ("total", "over/under leans"), ("script", "game script called"), ("best_parlay", "best parlays")):
        r = crec(key)
        if not r: continue
        sub = f"{r[0]}–{r[1]} · {CS['games']} games"
        if key == "ml" and CS.get("market_fav") and CS["market_fav"][1]:   # the honest comparison: what the closing favourites did, and how we did when we broke from them
            fv, dg = CS["market_fav"], CS.get("ml_disagree") or [0, 0]
            sub = f"{r[0]}–{r[1]} · favourites went {fv[0]}–{fv[1]-fv[0]}" + (f" · we broke from the market {dg[1]}× and went {dg[0]}–{dg[1]-dg[0]}" if dg[1] else " · never broke from the market")
        calls_tiles += tile(pctf(r[2]), label, sub)
    mm, mt = CS.get("mae_margin", {}), CS.get("mae_total", {})
    if mm: calls_tiles += tile(f"{mm.get('model', '—')}", "avg margin miss, pts", f"FanDuel's line missed by {mm.get('market', '—')}", "pos" if (mm.get("model") or 99) <= (mm.get("market") or 0) else "neg")
    if mt: calls_tiles += tile(f"{mt.get('model', '—')}", "avg total miss, pts", f"FanDuel's total missed by {mt.get('market', '—')}", "pos" if (mt.get("model") or 99) <= (mt.get("market") or 0) else "neg")
else: calls_tiles = tile("—", "game calls", "Moneyline / spread / total grading starts the week the calls archive was frozen.")
w5 = within(pre, 5); b_ = bias(pre)
# yardstick: what a projection that just used each player's season-to-date PPR average would have missed by (same players, same games)
base_mae, base_n = None, 0
try:
    gl = vals("gamelog.json"); GH = {c: i for i, c in enumerate(gl[0])}
    def fp(r):
        g = lambda c: num(r[GH[c]]) or 0
        return g("Pass Yds") / 25 + 4 * g("Pass TD") - 2 * g("INT") + g("Rush Yds") / 10 + 6 * g("Rush TD") + g("Receptions") + g("Rec Yds") / 10 + 6 * g("Rec TD")
    hist = defaultdict(list)
    for r in gl[1:]:
        try: w = int(float(r[0]))
        except Exception: continue
        if w < WEEK and len(r) > GH["Rec TD"]: hist[r[GH["Player"]]].append(fp(r))
    diffs = [abs(statistics.mean(hist[p["name"]]) - p["act"]) for p in pre if hist.get(p["name"])]
    if diffs: base_mae, base_n = statistics.mean(diffs), len(diffs)
except Exception: pass
model_on_same = None
if base_n:
    same = [p for p in pre if hist.get(p["name"])]; model_on_same = mae(same)
proj_tiles = (tile(f"{mae(pre):.1f}" if pre else "—", "fantasy points off, per player", f"{len(pre)} players frozen before kickoff · {pctf(w5)} landed within 5 pts · average lean {('over' if (b_ or 0) > 0 else 'under')} by {abs(b_ or 0):.1f}")
              + (tile(f"{(1 - model_on_same / base_mae) * 100:+.0f}%", "vs just using season averages", f"season-average guesses missed by {base_mae:.1f} pts on the same {base_n} players; the model missed by {model_on_same:.1f}. Positive = the model beat the lazy baseline.", "pos" if model_on_same < base_mae else "neg") if base_n and model_on_same is not None else "")
              + "".join(tile(f"{v:.1f}", f"{pos} fantasy points off") for pos, v in by_pos.items() if v is not None))
stat_rows = ""
for col, label, poss in (("Abs Pass Yds Error", "Passing yards", ("QB",)), ("Abs Rush Yds Error", "Rushing yards", ("RB", "QB")), ("Abs Rec Yds Error", "Receiving yards", ("WR", "TE", "RB"))):
    v, n = stat_mae(col, poss)
    if v is not None: stat_rows += f'<tr><td>{label}</td><td><b>{v:.1f} yds</b></td><td>{n} players</td></tr>'
stat_table = f'<table class="sc"><thead><tr><th>Stat</th><th>Average miss</th><th>Graded</th></tr></thead><tbody>{stat_rows}</tbody></table>' if stat_rows else ""
game_rows = ""
for k in pairs:
    g = GAMES.get(k); a, b = sorted(k)
    if g: a, b = g["away_team"], g["home_team"]
    gp = [p for p in graded if p["team"] in (a, b)]; gl = [l for l in L if l["team"] in (a, b)]; gh = sum(1 for l in gl if l["res"] == "HIT")
    cg = next((x for x in CJ["games"] if {x["a"], x["b"]} == {a, b}), None) if CJ else None
    def m(h): return '<i class="ok">✓</i>' if h is True else ('<i class="no">✗</i>' if h is False else '<i class="na">–</i>')
    calls_c = (m(cg["ml"][2]) + m(cg["spr"][3]) + m(cg["tot"][3]) + m(cg["scr_hit"])) if cg else '<i class="na">–</i>'
    game_rows += f'<tr><td><a href="#{a}-{b}">{a} @ {b}</a></td><td>{(mae(gp) or 0):.1f}</td><td>{f"{gh}–{len(gl)-gh}" if gl else "—"}</td><td class="cc">{calls_c}</td></tr>'
game_table = f'<table class="sc games"><thead><tr><th>Game</th><th>Pts off / player</th><th>Legs W–L</th><th>ML · spread · total · script</th></tr></thead><tbody>{game_rows}</tbody></table>'
# ---- what we actually posted: the owner's promoted bets for this week ('PROMO - Promoted Bets', graded Tuesday by grade_promos.py) ----
# The leg pool above is every line the model priced; this is the record of the slips BetSweep put its name on, at the posted FanDuel odds.
promo_tiles, promo_table = "", ""
try:
    pv = vals("promos.json"); PR = []
    for r in pv[1:]:
        r = list(r) + [""] * (10 - len(r))
        if num(r[0]) != WEEK or not str(r[2]).strip() or str(r[8]).strip().upper() not in ("HIT", "WON", "WIN", "CASHED", "MISSED", "MISS", "LOST", "LOSS"): continue   # grade_promos writes Cashed/Missed (11/3 audit: Cashed was unreadable here)
        hit = str(r[8]).strip().upper() in ("HIT", "WON", "WIN", "CASHED"); fdo = num(r[4]); nlegs = len([x for x in str(r[3]).splitlines() if x.strip()])
        dec = (fdo / 100 + 1) if fdo and fdo > 0 else (100 / -fdo + 1) if fdo else None
        PR.append({"title": str(r[2]).strip(), "n": nlegs, "fd": fdo, "hit": hit, "u": ((dec - 1) if hit else -1.0) if dec else (0.0 if hit else -1.0)})
    if PR:
        ph = sum(1 for x in PR if x["hit"]); pu = sum(x["u"] for x in PR)
        promo_tiles = tile(f"{ph}–{len(PR)-ph}", "promoted bets we posted", f"{pu:+.1f}u at 1u each, at the posted FanDuel odds · {sum(x['n'] for x in PR)} legs across {len(PR)} slips", "pos" if pu > 0 else "neg")
        # owner 11/3 audit: core slips (under +2000) and lottery slips (+2000 and up, the Piss Missiles) are different products - show both records
        core = [x for x in PR if x["fd"] is None or x["fd"] < 2000]; lotto = [x for x in PR if x["fd"] is not None and x["fd"] >= 2000]
        for grp, lab in ((core, "core slips (under +2000)"), (lotto, "lottery slips (+2000 and up)")):
            if grp:
                gh = sum(1 for x in grp if x["hit"]); gu = sum(x["u"] for x in grp)
                promo_tiles += tile(f"{gh}–{len(grp)-gh}", lab, f"{gu:+.1f}u · avg price {'+' if sum(x['fd'] or 0 for x in grp)/len(grp) > 0 else ''}{sum(x['fd'] or 0 for x in grp)/len(grp):.0f}", "pos" if gu > 0 else "neg")
        def _odds(o): return "" if o is None else (f"+{int(o)}" if o > 0 else f"{int(o)}")
        promo_table = '<table class="sc"><thead><tr><th>Slip</th><th>Legs</th><th>FanDuel</th><th>Result</th><th>Units</th></tr></thead><tbody>' + "".join(
            f'<tr><td>{E(x["title"])}</td><td>{x["n"]}</td><td>{_odds(x["fd"])}</td><td><b>{"HIT" if x["hit"] else "MISS"}</b></td><td class="{"pos" if x["u"] >= 0 else "neg"}">{x["u"]:+.1f}u</td></tr>' for x in PR) + "</tbody></table>"
except Exception as e: print("warn: promoted bets not graded on the receipt:", e)
# ---- the model's own slip vs what we posted (owner 11/3: "would the model's slip have cashed?") ----
# Model's Best tier frozen before each kickoff ('V2 - Model Best Picks', in/bestpicks.json), graded from the game log at the frozen odds, same
# week only - the record of the legs the site led with, next to the record of the slips the owner posted.
best_tiles = ""
try:
    bp = vals("bestpicks.json"); gl_ = vals("gamelog.json"); BH = {c: i for i, c in enumerate(bp[0])}; GH_ = {c: i for i, c in enumerate(gl_[0])}
    act = {}
    for r in gl_[1:]:
        r = r + [""] * (len(gl_[0]) - len(r))
        if num(r[0]) != WEEK: continue
        g_ = lambda c: num(r[GH_[c]]) if c in GH_ else None
        act[str(r[GH_["Player"]]).strip().lower()] = {"Passing Yards": g_("Pass Yds"), "Rushing Yards": g_("Rush Yds"), "Receiving Yards": g_("Rec Yds"), "Receptions": g_("Receptions"), "Anytime TD": (g_("Rush TD") or 0) + (g_("Rec TD") or 0)}
    last = {}
    for r in bp[1:]:
        r = r + [""] * (len(bp[0]) - len(r))
        if num(r[BH["Week"]]) != WEEK: continue
        if str(r[BH["Kickoff (CT)"]])[:16] and str(r[BH["Frozen at (CT)"]])[:16] >= str(r[BH["Kickoff (CT)"]])[:16]: continue
        last[(r[BH["Player"]], r[BH["Market"]], str(r[BH["Line"]]))] = r
    T = {}
    for (pl, mk, ln), r in last.items():
        a = act.get(str(pl).strip().lower())
        if not a: continue
        under = str(mk).startswith("Under "); base = mk[6:] if under else mk; v = a.get(base); line = num(ln); o = num(r[BH["Odds"]])
        if v is None or line is None or o is None: continue
        hit = (v < line) if under else (v >= 1 if base == "Anytime TD" else v >= line)
        tier = {"even": "Even money", "td": "Touchdowns", "safe": "Safer 65%+"}.get(r[BH["Tier"]], r[BH["Tier"]])
        for key in (tier, "Model's Best, all"):
            d = T.setdefault(key, [0, 0, 0.0]); d[0] += 1; d[1] += int(hit); d[2] += ((o / 100) if o > 0 else (100 / -o)) if hit else -1.0
    if T.get("Model's Best, all"):
        n_, h_, u_ = T["Model's Best, all"]
        best_tiles = tile(f"{h_}–{n_-h_}", "the model's own picks (Model's Best tier)", f"{h_/n_*100:.0f}% hit · {u_:+.1f}u at 1u each · " + " · ".join(f"{k} {v[1]}–{v[0]-v[1]}" for k, v in T.items() if k != "Model's Best, all"), "pos" if u_ > 0 else "neg")
except Exception as e: print("warn: Model's Best week record skipped:", e)
promo_block = f'<h3>What we posted</h3><p class="exp">The slips BetSweep put out on X and Instagram that week, graded at the odds we posted. The leg pool above is everything the model priced; this is what we actually told you to bet. The last tile is the model\'s own frozen picks for the same week, so you can see whether the slips we built beat what the model would have led with.</p><div class="tiles">{promo_tiles}{best_tiles}</div>{promo_table}' if promo_tiles else ""
scorecard = f'''<section class="card scorecard expanded" id="scorecard">
 <header class="hd">{PLAYS}<div class="tm a"><b>Week {WEEK}</b><span>how the model did</span></div>
  <div class="score"><span class="pt">{pctf(lp) if L else (f"{mae(pre):.1f}" if pre else "—")}</span><small>{"of the FanDuel legs we froze hit" if L else "fantasy points off per player"}</small>{SWOOSH}</div>
  <div class="tm b"><img class="bsmark" src="data:image/png;base64,{LOGO_S}" alt="BS"><span>graded after the games</span></div></header>
 <div class="scbody">
  <h3>Against FanDuel's lines</h3><p class="exp">Every leg here was frozen before kickoff with the model's chance and FanDuel's price. "Model said" is what the model promised; "price said" is what the odds implied; the hit rate is what happened.</p>
  <div class="tiles">{legs_tiles}</div>{mk_table}
  {promo_block}
  <h3>Game calls</h3><p class="exp">The side the model leaned to at freeze time, graded against the final score; parlays graded leg by leg.</p>
  <div class="tiles">{calls_tiles}</div>
  <h3>Projections vs the box score</h3><p class="exp">How far the frozen fantasy-point and yardage projections landed from the real numbers. Smaller is better; 0 would be perfect.</p>
  <div class="tiles">{proj_tiles}</div>{stat_table}
  <h3>Game by game</h3>{game_table}
 </div>
 <footer class="ft"><span class="brand"><img src="data:image/png;base64,{LOGO_S}" alt=""><span>BetSweep</span></span><span>Week {WEEK} receipt · frozen before kickoff, graded after</span><button class="snap" type="button" data-target="scorecard">Copy card as image</button><button class="snap story" type="button" data-target="scorecard">Story 9:16</button></footer>
</section>'''
summary = f'''<section class="card summary" id="summary">
 <header class="hd">{PLAYS}<div class="tm a"><b>Details</b><span>Week {WEEK} · beats, busts, markets</span></div>
  <div class="score"><span class="pt">{mae(pre) if pre else mae(graded):.1f}</span><small>avg fantasy points off per player · {len(pre)} pre-kickoff calls graded{f" · all {len(graded)} incl. late freezes: {mae(graded):.1f}" if len(pre) != len(graded) else ""}</small>{SWOOSH}</div>
  <div class="tm b"><img class="bsmark" src="data:image/png;base64,{LOGO_S}" alt="BS"><span>BetSweep model</span></div></header>
 <div class="ginfo"><span class="k">By position</span>{"".join(f"<span>{pos} {v:.1f}</span>" for pos, v in by_pos.items() if v is not None)}<span class="k">FanDuel legs</span><span>{legs_line}</span></div>
 <div class="sumgrid">
  <div><h3>Biggest beats <small>actual over projection</small></h3><ul class="bl">{"".join(li(p,"beat") for p in beats)}</ul></div>
  <div><h3>Biggest busts <small>projection over actual</small></h3><ul class="bl">{"".join(li(p,"bust") for p in busts)}</ul></div>
  <div><h3>Nailed it <small>closest calls, 10+ pt projections</small></h3><ul class="bl">{"".join(li(p,"nail") for p in nailed)}</ul></div>
  <div><h3>Legs by market <small>frozen pre-kickoff</small></h3><ul class="bl">{mk_html}</ul></div>
 </div>
 <footer class="ft"><span class="brand"><img src="data:image/png;base64,{LOGO_S}" alt=""><span>BetSweep</span></span><span>Picks. Data. Edge. Sweep.</span><button class="snap" type="button" data-target="summary">Copy card as image</button><button class="snap story" type="button" data-target="summary">Story 9:16</button></footer>
</section>'''

# ---- Model calls (game level): frozen in 'AUTO - Model Calls Archive', graded by build_calls_results.py ----
calls_html = ""
try:
    C = json.load(open(os.path.join(OUT, f"calls_week{WEEK}.json"))); S = C["summary"]
    def rec(k): return f'{S[k][0]}–{S[k][1]-S[k][0]}' if S[k][1] else "—"
    def mk(h): return '<b class="ok">✓</b>' if h is True else ('<b class="no">✗</b>' if h is False else '<b class="na">–</b>')
    trs = []
    for g in C["games"]:
        bp = g["bp"]; bpl = " + ".join(f'{E(x[0])} {mk(x[1]=="HIT" if x[1] in ("HIT","MISS") else None)}' for x in bp["legs"]) if bp["legs"] else "—"
        sp = g["spr"]; sptxt = f'{sp[0]} {("+" if (sp[1] or 0) > 0 else "")}{sp[1]:g}' if sp[0] == g["a"] and sp[1] is not None else (f'{sp[0]} {("+" if -(sp[1] or 0) > 0 else "")}{-(sp[1] or 0):g}' if sp[0] else "—")
        trs.append(f"""<tr><td class="g">{badge(g["a"])}{badge(g["b"])}<b>{g["a"]}–{g["b"]}</b><small>{E(g["src"])} lines</small></td>
 <td><span class="pr">{g["pa"]:.0f}–{g["pb"]:.0f}</span><span class="ac">{g["fa"]:.0f}–{g["fb"]:.0f}</span></td>
 <td><span class="pr">{E(g["most"])}</span><span class="ac">{E(g["act"])}</span>{mk(g["scr_hit"])}</td>
 <td>{E(g["ml"][0] or "—")} <small>{(g["ml"][1] or 0)*100:.0f}%{" · vs market" if g.get("ml_disagree") else ""}</small>{mk(g["ml"][2])}</td>
 <td>{E(sptxt)} <small>{(sp[2] or 0)*100:.0f}%</small>{mk(sp[3])}</td>
 <td>{E(g["tot"][0] or "—")} {g["tot"][1] if g["tot"][1] is not None else ""} <small>{(g["tot"][2] or 0)*100:.0f}%</small>{mk(g["tot"][3])}</td>
 <td class="bp">{bpl}<small>{E(str(bp["price"]))} · model {(bp["pj"] or 0)*100:.0f}% · for {E(str(bp["fit"]))} · <b>{E(bp["res"] or "—")}</b></small></td></tr>""")
    mm, mt, bw = S["mae_margin"], S["mae_total"], S["brier_win"]
    calls_html = f"""<section class="card calls" id="calls">
 <header class="hd">{PLAYS}<div class="tm a"><b>Calls</b><span>Week {WEEK} · game-level model calls, frozen before kickoff</span></div>
  <div class="score"><span class="pt">{rec("script")}</span><small>game script called right · {S["games"]} games graded</small>{SWOOSH}</div>
  <div class="tm b"><img class="bsmark" src="data:image/png;base64,{LOGO_S}" alt="BS"><span>model vs market</span></div></header>
 <div class="ginfo"><span class="k">Leans</span><span>moneyline {rec("ml")}</span><span>spread {rec("spread")}</span><span>total {rec("total")}</span><span class="k">Best parlays</span><span>{rec("best_parlay")}</span>
  <span class="k">Avg miss</span><span>margin: model {mm["model"]} vs market {mm["market"]} pts</span><span>total: model {mt["model"]} vs market {mt["market"]} pts</span><span class="k">Win-prob Brier</span><span>shown {bw["shown"]} · raw model {bw["raw_model"]} · market {bw["market"]} (lower is better)</span></div>
 <div class="callswrap"><table class="calls"><thead><tr><th>Game</th><th>Model → final</th><th>Script → actual</th><th>ML lean</th><th>Spread lean</th><th>Total lean</th><th>Best parlay</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>
 <p class="schint">Leans are the side the model rated over 50% at freeze time (its chance shown). Game-line chances were pulled halfway toward FanDuel's price this week because the model's team scores were not yet validated; "raw model" Brier scores the unshrunk projection so the two can be compared.</p>
 <footer class="ft"><span class="brand"><img src="data:image/png;base64,{LOGO_S}" alt=""><span>BetSweep</span></span><span>Week {WEEK} receipt · model calls</span><button class="snap" type="button" data-target="calls">Copy card as image</button></footer>
</section>"""
except FileNotFoundError: pass
except Exception as e: print("warn: model calls section skipped:", e)
RESULTS_JS = """
<script>
// receipts: every scorecard opens and closes on a tap of its header (the boards use the view buttons; here there is one view)
(function(){
  document.querySelectorAll('.card[id]:not(.summary):not(.scorecard):not(.calls) .hd').forEach(function(hd){
    hd.style.cursor = 'pointer';
    hd.addEventListener('click', function(ev){ if(ev.target.closest('a,button')) return; var c = hd.closest('.card'); var open = c.classList.toggle('expanded'); if(open){ c.dataset.view = 'proj'; c.scrollIntoView({block:'start', behavior:'smooth'}); } else delete c.dataset.view; });
  });
  var all = document.getElementById('toggleall'); if(all){ all.addEventListener('click', function(){ var cs = document.querySelectorAll('.card[id]:not(.summary):not(.scorecard):not(.calls)'); var anyClosed = Array.prototype.some.call(cs, function(c){ return !c.classList.contains('expanded'); }); cs.forEach(function(c){ c.classList.toggle('expanded', anyClosed); if(anyClosed) c.dataset.view = 'proj'; else delete c.dataset.view; }); all.textContent = anyClosed ? 'Collapse all games' : 'Open all games'; }); }
})();
</script>"""
CALLS_CSS = """
.card.scorecard .scbody{padding:6px 16px 14px} .card.scorecard h3{font-family:var(--display);font-weight:700;font-size:15px;letter-spacing:.08em;text-transform:uppercase;margin:16px 0 4px} .card.scorecard .exp{margin:0 0 10px;color:var(--mute);font-size:13px;line-height:1.45;max-width:72ch}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,210px),1fr));gap:10px;margin-bottom:10px}
.tile{background:var(--chalk);border:1px solid var(--line);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:2px;min-width:0}
.tile b{font-family:var(--display);font-weight:800;font-size:32px;line-height:1;letter-spacing:-.01em} .tile.pos b{color:var(--good)} .tile.neg b{color:var(--bad)}
.tile span{font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink)} .tile small{color:var(--mute);font-size:12px;line-height:1.4}
table.sc{width:100%;border-collapse:collapse;font-size:13px;margin:4px 0 8px} table.sc th{font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--mute);text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)} table.sc td{padding:7px 8px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums} table.sc td.pos{color:var(--good)} table.sc td.neg{color:var(--bad)}
table.sc a{color:var(--ink)} table.sc td.cc i{font-style:normal;font-weight:800;margin-right:8px} table.sc i.ok{color:var(--good)} table.sc i.no{color:var(--bad)} table.sc i.na{color:var(--mute)}
body.compact .card.scorecard{grid-column:1/-1} body.compact .card.scorecard > *{display:revert} body.compact .card.scorecard > .hd{display:grid}
.card .vbtns .vbtn{flex:1} body.compact .card:not(.expanded) > .vbtns{display:flex;padding:8px 12px}
.toggleall{display:block;margin:0 0 10px;font:inherit;font-weight:600;font-size:13px;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 12px;cursor:pointer} .toggleall:hover{border-color:var(--red)}
body.compact .card.calls:not(.expanded) > :not(.hd){display:block} body.compact .card.calls:not(.expanded) > .ginfo{display:flex}
.card.calls .callswrap{overflow:auto;padding:0 14px 10px}
table.calls{width:100%;border-collapse:collapse;font-size:12.5px} table.calls th{font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--mute);text-align:left;padding:8px 6px;border-bottom:1px solid var(--line)}
table.calls td{padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top;line-height:1.3} table.calls td.g{white-space:nowrap} table.calls td.g .badge{width:26px;height:26px;font-size:10px;border-radius:4px;margin-right:2px} table.calls td.g b{margin-left:6px}
table.calls td small{display:block;color:var(--mute);font-size:11px} table.calls .pr{display:block;color:var(--mute)} table.calls .ac{display:block;font-weight:700}
table.calls b.ok{color:var(--good);margin-left:4px} table.calls b.no{color:var(--bad);margin-left:4px} table.calls b.na{color:var(--mute);margin-left:4px} table.calls td.bp{min-width:220px}
"""
stamp = datetime.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p")
page = (open(os.path.join(HERE, "template.html")).read().replace("</style>", CALLS_CSS + "</style>", 1)
        .replace("<title>BetSweep Matchup Boards</title>", f"<title>BetSweep Week {WEEK} Receipt</title>")
        .replace("<h1>Week {{WEEK}} · <b>Matchup Boards</b></h1>", f"<h1>Week {WEEK} · <b>Receipt</b></h1>")
        .replace("{{DESC}}", f"Built {stamp} CT. Every projection here was frozen before its kickoff and graded from the box score afterward; nothing was changed after the games.")
        .replace("{{NAV}}", '<a href="#scorecard">Scorecard</a> <a href="#summary">Details</a> ' + ('<a href="#calls">Calls</a> ' if calls_html else '') + " ".join(nav)).replace("{{CARDS}}", scorecard + "\n" + summary + "\n" + calls_html + "\n" + '<button type="button" class="toggleall" id="toggleall">Open all games</button>\n' + "\n".join(cards) + RESULTS_JS)
        .replace("{{LOGO}}", LOGO).replace("{{BANNER}}", BANNER).replace("{{WEEK}}", str(WEEK)).replace("{{STAMP}}", stamp)
        .replace("{{ARCHIVE}}", '<nav class="archive" aria-label="back to boards"><span>Current</span><a href="https://claude.ai/artifact/RTTqiN3sdMHGgojimQ9hZv">This week\'s matchup boards →</a><a href="https://claude.ai/artifact/A7tt7rCuMgVvwSqBm9A7Pv">Season to date</a></nav>'))
# hide the boards key (not relevant here)
import re
page = re.sub(r'<div class="key">.*?</div>\n', '', page, count=1, flags=re.S)
out = os.path.join(OUT, f"results-week{WEEK}.html"); open(out, "w").write(page)
print(f"wrote {out} week {WEEK}: {len(cards)} games, {len(graded)} players, {len(L)} legs")
