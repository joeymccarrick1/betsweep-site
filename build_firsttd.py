#!/usr/bin/env python3
"""build_firsttd.py - First Touchdown Scorer page (out/firsttd.html) + the per-game strip data for the boards (out/firsttd_top.json).

Usage: python3 build_firsttd.py          (run BEFORE build_boards.py so the boards can show the First TD strip)
Inputs (in/): boards.json (week), proj_qb/rb/wr/te.json (projection tabs), games.csv (kickoffs), links.json ('AUTO - FanDuel Links'),
             ftdodds.json ('AUTO - First TD Odds'!A1:L1200, written by FanDuelOdds.gs 2026-10-15b+), firsttd.json (optional cross-check:
             'V2 - First TD Board'!A3:P700), settings.json (optional: 'AUTO - Settings'!A1:B300 to read B280/B281).

Model (validated out of sample on nflverse play-by-play, 2025 wk3+ and 2026, 317 games: log loss 2.979 vs 3.145 uniform; calibrated by
octile and by position; multipliers/exponents on the share did not help):
    P(first TD) = lambda_i / sum(lambda over both teams) x (1 - DEF_SHARE) x (1 - P_NO_TD)
    lambda_i    = projected rush TD + projected rec TD (QB: rush TD only), active players only
    DEF_SHARE   = 'AUTO - Settings'!B280 (0.05: defense/special-teams first TDs)   P_NO_TD = B281 (0.004: scoreless games)
The Sheet tab 'V2 - First TD Board' computes the same thing with formulas; when in/firsttd.json is present this script prints the largest
disagreement so a drift between the tab and the site is caught by the weekly run.
"""
import json, os, re, csv, html, datetime, math
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
E = html.escape
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def num(x):
    try: return float(str(x).replace(",", "").replace("%", "").replace("+", ""))
    except Exception: return None
exec(open(os.path.join(HERE, "brand.py")).read())   # NAMES, TEAMCOL, badge(), LOGO, BANNER
boards = vals("boards.json"); WEEK = int(float(boards[1][1]))
stamp = datetime.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p")

DEF_SHARE, P_NO_TD = 0.05, 0.004
try:
    st = vals("settings.json")
    for r in st:
        if len(r) >= 2 and str(r[0]).strip().lower().startswith("share of first touchdowns scored by defense"): DEF_SHARE = num(r[1]) or DEF_SHARE
        if len(r) >= 2 and str(r[0]).strip().lower().startswith("share of games with no touchdown"): P_NO_TD = num(r[1]) or P_NO_TD
except Exception: pass
SCALE = (1 - DEF_SHARE) * (1 - P_NO_TD)

def normname(x):
    x = re.sub(r"\.", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
def col(h, name):
    try: return h.index(name)
    except ValueError: return None
def am2p(o):
    o = num(o)
    if o is None or o == 0: return None
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)
def fair_odds(p):
    if p <= 0 or p >= 1: return ""
    return f"+{(1/p-1)*100:.0f}" if p < 0.5 else f"-{p/(1-p)*100:.0f}"
def odds_str(o):
    o = num(o)
    if o is None: return ""
    return f"+{int(o)}" if o > 0 else f"{int(o)}"

# ---- players: lambda from the projection tabs ----
P = []
v = vals("proj_qb.json"); h = v[0]; c = {k: col(h, k) for k in ("Opponent", "Proj Rush TD", "Weekly Active", "Proj Fantasy Pts")}
for r in v[1:]:
    if not r or not r[0] or len(r) <= (c["Weekly Active"] or 0): continue
    g = lambda k: r[c[k]] if c[k] is not None and c[k] < len(r) else ""
    if str(g("Weekly Active")).upper() != "YES" or g("Opponent") in ("", "BYE"): continue
    lam = num(g("Proj Rush TD")) or 0
    if lam > 0: P.append({"n": r[0], "t": r[1], "p": "QB", "o": g("Opponent"), "lam": lam})
for fn, pos in (("proj_rb.json", "RB"), ("proj_wr.json", "WR"), ("proj_te.json", "TE")):
    v = vals(fn); h = v[0]; c = {k: col(h, k) for k in ("Opponent", "Proj Rush TD", "Proj Rec TD", "Weekly Active")}
    for r in v[1:]:
        if not r or not r[0] or len(r) <= (c["Weekly Active"] or 0): continue
        g = lambda k: r[c[k]] if c[k] is not None and c[k] < len(r) else ""
        if str(g("Weekly Active")).upper() != "YES" or g("Opponent") in ("", "BYE"): continue
        lam = (num(g("Proj Rush TD")) or 0) + (num(g("Proj Rec TD")) or 0)
        if lam > 0: P.append({"n": r[0], "t": r[1], "p": pos, "o": g("Opponent"), "lam": lam})

# ---- games / kickoffs ----
GAMES = []
with open(os.path.join(IN, "games.csv"), newline="") as f:
    for g in csv.DictReader(f):
        if g["season"] == "2026" and g["week"] == str(WEEK) and g["game_type"] == "REG": GAMES.append(g)
def kick_of(g):
    try:
        hh, mm = g["gametime"].split(":"); ct = (int(hh) - 1) % 24; ampm = "PM" if ct >= 12 else "AM"; ct12 = ct - 12 if ct > 12 else (12 if ct == 0 else ct)
        dt = datetime.date.fromisoformat(g["gameday"]); return f"{dt.strftime('%a %-m/%-d')} {ct12}:{mm} {ampm} CT", f"{g['gameday']} {g['gametime']}"
    except Exception: return "", ""
GINFO = {}
for g in GAMES:
    k = frozenset([g["away_team"], g["home_team"]]); kick, sortk = kick_of(g)
    GINFO[k] = {"away": g["away_team"], "home": g["home_team"], "kick": kick, "sort": sortk, "stadium": g.get("stadium", "")}

# ---- FanDuel first-TD prices and betslip IDs ----
FD = {}   # normname -> {odds, link, mid, sid, upd}
try:
    for r in vals("ftdodds.json")[1:]:
        if len(r) >= 3 and r[0] and num(r[2]) is not None:
            k = str(r[0]).split("|")[0]
            FD[k] = {"odds": num(r[2]), "link": r[3] if len(r) > 3 else "", "mid": r[4] if len(r) > 4 else "", "sid": r[5] if len(r) > 5 else "", "upd": r[8] if len(r) > 8 else ""}
except Exception: pass
try:   # betslip IDs may also arrive via the links tab (key name|First TD|1)
    for r in vals("links.json")[1:]:
        if len(r) >= 7 and r[0] and str(r[0]).endswith("|First TD|1"):
            k = str(r[0]).split("|")[0]; d = FD.setdefault(k, {"odds": None, "link": "", "mid": "", "sid": "", "upd": ""})
            mm = re.search(r"[?&]marketId=([^&#]+)", str(r[4])); ss_ = re.search(r"[?&]selectionId=([^&#]+)", str(r[4]))
            d["mid"] = d["mid"] or (mm.group(1) if mm else str(r[5])); d["sid"] = d["sid"] or (ss_.group(1) if ss_ else str(r[6]))
            if d["odds"] is None and len(r) > 7: d["odds"] = num(r[7])
except Exception: pass

# ---- compute ----
bygame = {}
for p in P: bygame.setdefault(frozenset([p["t"], p["o"]]), []).append(p)
rows = []
for gk, ps in bygame.items():
    if len(gk) != 2: continue
    tot = sum(q["lam"] for q in ps)
    team_tot = {}
    for q in ps: team_tot[q["t"]] = team_tot.get(q["t"], 0) + q["lam"]
    gi = GINFO.get(gk); a, b = sorted(gk)
    if gi: a, b = gi["away"], gi["home"]
    for q in ps:
        pr = q["lam"] / tot * SCALE
        fd = FD.get(normname(q["n"]), {})
        imp = am2p(fd.get("odds")); edge = (pr - imp) if imp is not None else None
        verdict = ("VALUE" if edge >= 0.03 else "FAIR" if edge >= 0 else "PASS") if edge is not None else ""
        rows.append({**q, "game": f"{a} @ {b}", "gid": f"{a}-{b}", "a": a, "b": b, "kick": gi["kick"] if gi else "", "sort": gi["sort"] if gi else "9",
                     "tshare": team_tot[q["t"]] / tot, "pr": pr, "fair": fair_odds(pr), "fd": fd.get("odds"), "imp": imp, "edge": edge, "verdict": verdict,
                     "mid": fd.get("mid", ""), "sid": fd.get("sid", ""), "link": fd.get("link", "")})
rows.sort(key=lambda r: (r["sort"], r["gid"], -r["pr"]))
npriced = sum(1 for r in rows if r["imp"] is not None)

# cross-check with the Sheet tab when its snapshot is present
try:
    sheet = {normname(r[0]): num(r[9]) for r in vals("firsttd.json")[1:] if len(r) > 9 and num(r[9]) is not None}
    diffs = sorted(((abs(r["pr"] - sheet[normname(r["n"])]), r["n"]) for r in rows if normname(r["n"]) in sheet), reverse=True)
    missing = [r["n"] for r in rows if normname(r["n"]) not in sheet]
    print(f"cross-check vs 'V2 - First TD Board': {len(diffs)} matched, max |diff| = {diffs[0][0]*100:.2f} pts ({diffs[0][1]}); on site but not in tab: {len(missing)}; in tab but not on site: {len(set(sheet)-{normname(r['n']) for r in rows})}")
    if diffs and diffs[0][0] > 0.005: print("WARN: site and Sheet disagree by more than 0.5 pts - check the tab's formulas / inputs")
except Exception as e: print("cross-check skipped:", e)

# ---- boards strip data ----
top = {}
for r in rows: top.setdefault(r["gid"], []).append([r["n"], r["p"], r["t"], round(r["pr"], 4), r["fair"], r["fd"], r["mid"], r["sid"]])
json.dump({"week": WEEK, "scale": SCALE, "games": {k: v[:4] for k, v in top.items()}}, open(os.path.join(OUT, "firsttd_top.json"), "w"))
json.dump([{"n": r["n"], "t": r["t"], "p": r["p"], "o": r["o"], "a": r["a"], "b": r["b"], "pr": round(r["pr"], 4), "fair": r["fair"], "fd": r["fd"], "imp": (round(r["imp"], 4) if r["imp"] is not None else None), "mid": r["mid"], "sid": r["sid"], "link": r["link"]} for r in rows],
          open(os.path.join(OUT, "firsttd_all.json"), "w"))   # every player, for the parlay builder's First TD legs

# ---- page ----
def fdlink(r, label="Add to FanDuel slip"):
    if r["mid"] and r["sid"]:
        return f'<a class="fdgo" href="https://sportsbook.fanduel.com/addToBetslip?marketId[0]={E(str(r["mid"]))}&selectionId[0]={E(str(r["sid"]))}" target="_blank" rel="noopener" title="Opens FanDuel with {E(r["n"])} first touchdown scorer on your betslip; check the price before you place it">{label}</a>'
    if r["link"]: return f'<a class="fdgo" href="{E(str(r["link"]))}" target="_blank" rel="noopener">Open on FanDuel</a>'
    return ""
def pos_b(p): return f'<b class="pos {p}">{p}</b>'
def edge_cell(r):
    if r["edge"] is None: return '<td class="imp"></td><td class="edge none" title="no FanDuel price yet">—</td>'
    cls = "val" if r["verdict"] == "VALUE" else "fair" if r["verdict"] == "FAIR" else "pass"
    return f'<td class="imp">{r["imp"]*100:.1f}%</td><td class="edge {cls}">{r["edge"]*100:+.1f} <small>{r["verdict"]}</small></td>'

cards, nav = [], []
for gid in dict.fromkeys(r["gid"] for r in rows):
    rs = [r for r in rows if r["gid"] == gid]; a, b = rs[0]["a"], rs[0]["b"]
    nav.append(f'<a href="#ftd-{gid}">{a}·{b}</a>')
    ta = sum(r["lam"] for r in rs if r["t"] == a); tb = sum(r["lam"] for r in rs if r["t"] == b); tot = ta + tb
    trs = "".join(
        f'<tr class="{"lead" if i < 3 else ""}"><td class="rk">{i+1}</td><td class="plc"><span class="plw">{badge(r["t"])}<span>{E(r["n"])}</span>{pos_b(r["p"])}</span></td>'
        f'<td class="lam" title="projected rushing + receiving TD">{r["lam"]:.2f}</td><td class="pr"><b>{r["pr"]*100:.1f}%</b></td><td class="fair">{r["fair"]}</td>'
        f'<td class="fdp">{odds_str(r["fd"]) or "—"}</td>{edge_cell(r)}<td class="go">{fdlink(r, "Add to slip")}</td></tr>'
        for i, r in enumerate(rs))
    cards.append(f'''<section class="ftd" id="ftd-{gid}">
 <div class="fhd" style="--ca:{TEAMCOL.get(a, ("#333","#333"))[0]};--cb:{TEAMCOL.get(b, ("#333","#333"))[0]}">
  <h2>{badge(a)} {E(NAMES.get(a, a))} <small>@</small> {badge(b)} {E(NAMES.get(b, b))}</h2>
  <p>{E(rs[0]["kick"])}{" · " if rs[0]["kick"] else ""}model: {a} {ta:.2f} TD, {b} {tb:.2f} TD ({tot:.2f} total) · {a} scores first {ta/tot*SCALE*100:.0f}%, {b} {tb/tot*SCALE*100:.0f}%, D/ST or no TD {(1-SCALE)*100:.1f}%</p>
 </div>
 <div class="tw"><table><thead><tr><th></th><th>Player</th><th title="projected rushing + receiving TD">Proj TD</th><th>First TD</th><th>Fair</th><th>FanDuel</th><th>Book %</th><th>Edge</th><th></th></tr></thead><tbody>{trs}</tbody></table></div>
</section>''')

likely = sorted(rows, key=lambda r: -r["pr"])[:12]
edges = sorted([r for r in rows if r["edge"] is not None], key=lambda r: -r["edge"])[:12]
def strip(rs, kind):
    if not rs: return '<li class="none">FanDuel first-TD prices load into the sheet when the odds refresh runs (usually Thursday); edges appear here then.</li>'
    out = []
    for r in rs:
        price = f'<small>FD {odds_str(r["fd"])} · {r["edge"]*100:+.1f}</small>' if r["edge"] is not None else f'<small>fair {r["fair"]}</small>'
        out.append(f'<li><a href="#ftd-{r["gid"]}">{badge(r["t"])}<span class="n">{E(r["n"])}</span>{pos_b(r["p"])}<b>{r["pr"]*100:.1f}%</b>{price}</a>{fdlink(r, "+ slip") if kind == "edge" else ""}</li>')
    return "".join(out)

CSS = """
.ftdwrap{max-width:none;margin:0;padding:0;color:var(--ink)}
.ftdwrap .badge{width:30px;height:22px;font-size:10px;border-radius:5px;padding-bottom:2px;box-shadow:inset 0 -3px 0 var(--s)}
.ftdwrap .strips{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:14px 0 18px}
@media(max-width:760px){.ftdwrap .strips{grid-template-columns:minmax(0,1fr)}}
.ftdwrap .strips>div{min-width:0}
.ftdwrap .strips li a:first-child{overflow:hidden}
@media(max-width:520px){.ftdwrap .strips li a:first-child{flex-wrap:wrap;row-gap:0}.ftdwrap .strips li a:first-child small{flex-basis:100%;padding-left:38px;margin-top:-2px}}
.ftdwrap .strips>div{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.ftdwrap .strips h3{margin:0 0 8px;font:700 15px/1.2 "Barlow Condensed",sans-serif;text-transform:uppercase;letter-spacing:.04em}
.ftdwrap .strips h3 small{font-weight:500;text-transform:none;letter-spacing:0;color:var(--mute);margin-left:6px}
.ftdwrap .strips ul{list-style:none;margin:0;padding:0}
.ftdwrap .strips li{display:flex;align-items:center;gap:8px;padding:5px 0;border-top:1px dashed var(--line);font-size:14px}
.ftdwrap .strips li:first-child{border-top:0}
.ftdwrap .strips li a:first-child{display:flex;align-items:center;gap:8px;flex:1;min-width:0;color:inherit;text-decoration:none}
.ftdwrap .strips li .n{flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}
.ftdwrap .strips li a:first-child .pos{margin-right:auto}
.ftdwrap .strips li b{font-variant-numeric:tabular-nums}
.ftdwrap .strips li small{color:var(--mute);font-variant-numeric:tabular-nums;white-space:nowrap}
.ftdwrap .strips li.none{color:var(--mute);font-size:13px}
.ftd{background:var(--card);border:1px solid var(--line);border-radius:14px;margin:0 0 16px;overflow:hidden;scroll-margin-top:170px}
.ftd .fhd{display:block;position:relative;background:#141a24;color:#fff;padding:18px 14px 12px}
.ftd .fhd::before{content:"";position:absolute;left:0;right:0;top:0;height:6px;background:linear-gradient(90deg,var(--ca) 0,var(--ca) 50%,var(--cb) 50%,var(--cb) 100%)}
.ftd .fhd .badge{width:38px;height:28px;font-size:13px}
.ftd .fhd h2{margin:0;font:800 22px/1.1 "Barlow Condensed",sans-serif;display:flex;align-items:center;gap:8px;flex-wrap:wrap;color:#fff}
.ftd .fhd h2 small{opacity:.8;font-weight:500}
.ftd .fhd p{margin:4px 0 0;font-size:12.5px;opacity:.95}
.ftd table{width:100%;border-collapse:collapse;font-size:14px}
.ftd th{font:600 11px/1 "IBM Plex Sans",sans-serif;text-transform:uppercase;letter-spacing:.06em;color:var(--mute);text-align:right;padding:9px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
.ftd th:nth-child(2){text-align:left}
.ftd td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.ftd td.plc{text-align:left;width:26%;min-width:220px}
.ftd td.plc .plw{display:inline-flex;align-items:center;gap:8px;white-space:nowrap}
.ftd td.plc .plw>span{font-weight:600}
.ftd td.fdp{font-weight:600}
.ftd td.rk{color:var(--mute);font-size:12px;width:22px}
.ftd td.lam{color:var(--mute)}
.ftd td.pr b{font-size:15px}
.ftd tr.lead td.pr b{color:var(--red)}
.ftd td.edge.val{color:var(--good);font-weight:700}.ftd td.edge.fair{color:var(--warn)}.ftd td.edge.pass{color:var(--bad)}
.ftd td.edge small{font-weight:600;font-size:10px;letter-spacing:.04em;margin-left:3px}
.ftd td.edge.none{color:var(--mute);text-align:center}
.ftd td.go{width:1%}
.ftd .fdgo,.ftdwrap .strips .fdgo{display:inline-block;background:#1493ff;color:#fff;border-radius:7px;padding:4px 9px;font:600 12px/1.2 "IBM Plex Sans",sans-serif;text-decoration:none;white-space:nowrap}
.ftdwrap .how{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:0 0 16px;font-size:14px;color:var(--ink)}
.ftdwrap .how h3{margin:0 0 6px;font:700 15px/1.2 "Barlow Condensed",sans-serif;text-transform:uppercase;letter-spacing:.04em}
.ftdwrap .how p{margin:0 0 6px}
.ftdwrap .how dl{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;margin:6px 0 0}
.ftdwrap .how dt{font-weight:700}.ftdwrap .how dd{margin:0}
.ftd .tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
@media(max-width:700px){.ftd th:nth-child(5),.ftd th:nth-child(7),.ftd td.fair,.ftd td.imp{display:none}.ftd th:nth-child(3),.ftd td.lam,.ftd th:nth-child(1),.ftd td.rk{display:none}.ftd table{font-size:13px}.ftd td,.ftd th{padding:6px 5px}.ftd td.edge.none small{font-size:10px}.ftd .fhd h2{font-size:19px}}
"""
body = f'''<div class="ftdwrap">
 <div class="strips">
  <div><h3>Most likely to score first<small>whole slate</small></h3><ul>{strip(likely, "likely")}</ul></div>
  <div><h3>Best edges vs FanDuel<small>{npriced} players priced</small></h3><ul>{strip(edges, "edge")}</ul></div>
 </div>
 <div class="how"><h3>How we get the number</h3>
  <p>Each player's chance of the game's first touchdown is his share of the projected touchdowns in that game: his projected rushing + receiving TD over both teams' total, times {SCALE*100:.1f}% (the remaining {(1-SCALE)*100:.1f}% covers a defensive or special-teams first TD and games with no TD). That is the whole model: team strength, pace and game script are already inside the projections, so the share is the clean way to convert them. Tested on every 2025 and 2026 game since Week 3 ({'317'} games): it beats an even split by a wide margin and is calibrated top to bottom, and no extra tilt toward the favorite or the top option improved it.</p>
  <dl><dt>First TD</dt><dd>the model's probability he scores the game's first touchdown</dd><dt>Fair</dt><dd>the American odds that probability converts to, no vig</dd><dt>FanDuel / Book %</dt><dd>FanDuel's first touchdown scorer price and the hit rate it implies</dd><dt>Edge</dt><dd>First TD % minus Book %, in points: <b>VALUE</b> at +3 or better, <b>FAIR</b> from 0 to +3, <b>PASS</b> below 0</dd></dl>
  <p style="margin-top:8px;color:var(--mute);font-size:13px">First TD is a high-variance market by nature: the best number on the slate is usually under 20%. Treat these as single legs or small plays, and shop the price. Built {stamp} CT from the live sheet. Information only, not a guarantee; 21+, please bet responsibly.</p>
 </div>
 {"".join(cards)}
</div>'''

page = (open(os.path.join(HERE, "template.html")).read()
        .replace("<title>BetSweep Matchup Boards</title>", "<title>BetSweep First TD</title>")
        .replace("<h1>Week {{WEEK}} · <b>Matchup Boards</b></h1>", "<h1>Week {{WEEK}} · <b>First TD Scorer</b></h1>")
        .replace("</style>", CSS + "\n</style>", 1)
        .replace("{{DESC}}", f"Who scores first in every Week {WEEK} game: the model's first-touchdown probability for every active skill player, the fair odds, and FanDuel's first touchdown scorer price next to it with the edge. Built {stamp} CT.")
        .replace("{{NAV}}", "".join(nav)).replace("{{CARDS}}", body)
        .replace("{{LOGO}}", LOGO).replace("{{BANNER}}", BANNER).replace("{{WEEK}}", str(WEEK)).replace("{{STAMP}}", stamp).replace("{{ARCHIVE}}", ""))
page = re.sub(r'<div class="key">.*?</dl>\n</div>\n', '', page, count=1, flags=re.S)
page = page.replace('<div class="grid">', '<div class="grid" style="display:block">', 1)
out = os.path.join(OUT, "firsttd.html"); open(out, "w").write(page)
print(f"wrote {out}: {len(rows)} players, {len(cards)} games, week {WEEK}, {npriced} with FanDuel prices, {sum(1 for r in rows if r['mid'] and r['sid'])} with betslip IDs; DEF {DEF_SHARE} / no-TD {P_NO_TD}")
