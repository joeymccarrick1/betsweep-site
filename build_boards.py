#!/usr/bin/env python3
"""BetSweep Matchup Boards page generator (v2026-10-14c).

Reads raw Google Sheets range dumps from ./in/ (each a JSON file shaped {"values": [[...], ...]} as returned by
the Sheets connector's get_values) plus the nflverse schedule, and writes ./out/matchup-boards.html.

Inputs (ranges to dump, exactly):
  in/boards.json    '2026 Matchup Boards'!A1:Q560
  in/ranks.json     'AUTO - Defensive Stat Matchup Ranks'!A1:P68
  in/weather.json   'AUTO - Game Weather'!A3:P40
  in/avail.json     'AUTO - Weekly Availability'!A1:M300
  in/scripts.json   'V2 - Game Scripts'!A4:K20
  in/legboard.json  'V2 - Leg Board'!A4:R1604
  in/bestlegs.json  'V2 - Best Legs'!A6:K60
  in/mult.json      'AUTO - Script Multipliers'!A1:H23   (mean multipliers; TD legs in script plays)
  in/archive.json   'AUTO - Boards Archive'!A1:F60       (optional; links to past receipts)
  in/games.csv      https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv
Assets next to this script: template.html, logo_b64.txt, logo_small_b64.txt, banner_b64.txt, probit.json
"""
import json, html, re, csv, datetime, math, os, sys
from collections import defaultdict
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
E = html.escape
def vals(name):
    return json.load(open(os.path.join(IN, name)))["values"]
def num(x):
    try: return float(str(x).replace("%", "").replace("+", ""))
    except: return None
def pct(x):
    v = num(x)
    if v is None: return None
    if "%" in str(x) or abs(v) > 1.5: return v / 100
    return v

# ---------------- inputs ----------------
boards = vals("boards.json"); WEEK = int(float(boards[1][1]))
ranks_raw = vals("ranks.json"); weather_raw = vals("weather.json"); avail_raw = vals("avail.json")
scripts_raw = vals("scripts.json"); legs_raw = vals("legboard.json"); best_raw = vals("bestlegs.json")
try: mult_raw = vals("mult.json")
except Exception: mult_raw = []
try: CORR = {r[0]: num(r[1]) for r in vals("corr.json")[1:] if r and "|" in str(r[0])}
except Exception: CORR = {}
GAMEDAY = {}
try:
    gd = vals("gameday.json")
    for r in gd[1:]:
        if len(r) >= 4 and str(r[0]) == str(WEEK) and r[1]: GAMEDAY[r[1].strip().lower()] = {"status": r[3].strip().upper(), "note": (r[4] if len(r) > 4 else ""), "time": (r[5] if len(r) > 5 else "")}
except Exception: pass
MULT = {r[0]: [num(x) for x in r[3:7]] for r in mult_raw[1:] if r and "|" in str(r[0])}
def normname(x):
    x = re.sub(r"\.", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
LINKS = {}  # 'AUTO - FanDuel Links': key -> (marketId, selectionId)
try:
    for r in vals("links.json")[1:]:
        if len(r) >= 7 and r[0] and (r[4] or (r[5] and r[6])):
            mm = re.search(r"[?&]marketId=([^&#]+)", str(r[4])); ss_ = re.search(r"[?&]selectionId=([^&#]+)", str(r[4]))
            LINKS[r[0]] = (mm.group(1) if mm else str(r[5]), ss_.group(1) if ss_ else str(r[6]))
except Exception: pass
def fd_ids(l): return LINKS.get(f"{normname(l['player'])}|{l['market']}|{int(l['line'] or 1)}")
def leg_key(l): return f"{l['player']}|{l['market']}|{int(math.floor((l['line'] or 1) + 0.5))}"   # JS Math.round, so spreads/totals (-2.5, 42.5) key the same as the builder
SLIP_USED = set()   # leg keys that appear on an Add-to-betslip button (the page embeds only those legs)
def fd_button(legs, what):
    """Add-to-betslip button for a list of leg dicts: adds them to the page's slip (priced by the model, sent to FanDuel from there)."""
    if not legs: return ""
    keys = [leg_key(l) for l in legs]; SLIP_USED.update(keys)
    return (f'<button type="button" class="fdgo addbs" data-k="{E("||".join(keys))}" data-n="{len(legs)}" title="Add {what} leg{"s" if len(legs) > 1 else ""} to your slip">'
            f'+ Add{f" <small>{len(legs)} legs</small>" if len(legs) > 1 else ""}</button>')
def plus_btn(l):
    """Small + that adds one leg to the betslip (same as the First TD strip's)."""
    k = leg_key(l); SLIP_USED.add(k)
    return f'<button type="button" class="addmini addbs" data-k="{E(k)}" title="Add {E(l["player"])} {E(l["market"].lower())}{(" " + format(l["line"], "g") + "+") if l.get("line") and l["market"] not in ("Anytime TD", "First TD") else ""} to your betslip" aria-label="Add {E(l["player"])} {E(l["market"].lower())} to your betslip">+</button>'
def fd_button_legacy(legs, what):
    ids = [fd_ids(l) for l in legs]; ok = [x for x in ids if x]
    if not ok: return ""
    q = "&".join(f"marketId[{i}]={m}&selectionId[{i}]={s}" for i, (m, s) in enumerate(ok))
    note = f"{len(ok)} legs" if len(ok) == len(legs) else f"{len(ok)} of {len(legs)} legs"
    return f'<a class="fdgo" href="https://sportsbook.fanduel.com/addToBetslip?{q}" target="_blank" rel="noopener" title="Opens FanDuel with these {what} legs on your betslip; check the lines before you place it">Add to FanDuel slip <small>{note}</small></a>'
FTD = {}   # out/firsttd_top.json from build_firsttd.py (run first): gid -> top-4 [name, pos, team, p, fair, fd odds, marketId, selectionId]
try: FTD = json.load(open(os.path.join(OUT, "firsttd_top.json")))["games"]
except Exception: pass
def ftd_strip(a, b):
    rs = FTD.get(f"{a}-{b}") or FTD.get(f"{b}-{a}")
    if not rs: return ""
    ids = [(r[6], r[7]) for r in rs if len(r) > 7 and r[6] and r[7]]
    def one(r):
        price = f' <small>FD {odds_str(r[5])}</small>' if r[5] is not None else ""
        k = f"{r[0]}|First TD|1"; SLIP_USED.add(k)
        btn = f'<button type="button" class="addmini addbs" data-k="{E(k)}" title="Add {E(r[0])} first TD to your betslip">+</button>' if r[5] is not None else ""
        return f'<span class="sp">{E(r[0])} <small>{E(r[1])}</small><b>{r[3]*100:.1f}%</b> <small>fair {E(r[4])}</small>{price}{btn}</span>'
    return (f'<div class="splays ftd"><span class="lt">First TD <small>model, whole game</small></span>{"".join(one(r) for r in rs)}'
            f'<a class="ftdmore" href="https://betsweep.co/firsttd/">Every player + FanDuel prices →</a></div>')
def cov_strip(a, b):
    """Mike Clay WR-CB read for both teams' receivers (flags.py WRCB): who draws the softer corner this week. One line per game card."""
    def arrow(c):
        dtr, dfr = c.get("d_tr"), c.get("d_fr")
        if dtr is not None and abs(dtr) > 1: dtr = dtr / 100.0
        if dtr is None or dfr is None: return "·", "cov-n"
        if dtr >= 0.08 and dfr >= 0.15: return "▲", "cov-up"
        if dtr <= -0.08 and dfr <= -0.15: return "▼", "cov-dn"
        return "·", "cov-n"
    def team(t):
        rs = sorted([c for c in FE.WRCB.values() if c.get("team") == t], key=lambda c: -(c.get("tgt") or 0))
        if not rs: return ""
        out = []
        for c in rs:
            ar, cls = arrow(c); dtr, dfr = c.get("d_tr"), c.get("d_fr")
            if dtr is not None and abs(dtr) > 1: dtr = dtr / 100.0
            tip = f"vs {c['cb']}" + (f" on ~{(c['exp']*100 if c['exp'] <= 1 else c['exp']):.0f}% of routes" if c.get("exp") is not None else "") + (f" · Clay: targets {dtr*100:+.0f}%, pts/route {dfr:+.2f} vs his season rates" if dtr is not None and dfr is not None else "")
            out.append(f'<span class="sp {cls}" title="{E(tip)}">{E(c["name"].split(" ")[-1] if len(c["name"]) > 14 else c["name"])} <small>{E(c["cb"].split(" ")[-1])}</small><b>{ar}</b></span>')
        return f'<span class="covt"><em>{t}</em>{"".join(out)}</span>'
    ta, tb = team(a), team(b)
    if not (ta or tb): return ""
    return (f'<div class="splays cov"><span class="lt">Coverage <small>Clay WR-CB · ▲ softer corner · ▼ tougher</small></span>{ta}{tb}</div>')
PROBIT = {r[0]: r[3:11] for r in json.load(open(os.path.join(HERE, "probit.json")))}
import calib as CALIB
exec(open(os.path.join(HERE, "brand.py")).read())   # NAMES, TEAMCOL, badge(), PLAYS, SWOOSH, LOGO, LOGO_S, BANNER

FULL = {v if k not in("LA","LAC","NYG","NYJ") else k: k for k, v in NAMES.items()}
FULLNAME = {"Arizona Cardinals":"ARI","Atlanta Falcons":"ATL","Baltimore Ravens":"BAL","Buffalo Bills":"BUF","Carolina Panthers":"CAR","Chicago Bears":"CHI","Cincinnati Bengals":"CIN",
"Cleveland Browns":"CLE","Dallas Cowboys":"DAL","Denver Broncos":"DEN","Detroit Lions":"DET","Green Bay Packers":"GB","Houston Texans":"HOU","Indianapolis Colts":"IND",
"Jacksonville Jaguars":"JAX","Kansas City Chiefs":"KC","Las Vegas Raiders":"LV","Los Angeles Chargers":"LAC","Los Angeles Rams":"LA","Miami Dolphins":"MIA","Minnesota Vikings":"MIN",
"New England Patriots":"NE","New Orleans Saints":"NO","New York Giants":"NYG","New York Jets":"NYJ","Philadelphia Eagles":"PHI","Pittsburgh Steelers":"PIT","San Francisco 49ers":"SF",
"Seattle Seahawks":"SEA","Tampa Bay Buccaneers":"TB","Tennessee Titans":"TEN","Washington Commanders":"WAS"}

# ---- defense ranks (season + last 3) ----
DCOLS = ranks_raw[0][1:]; DCOL = {c: i for i, c in enumerate(DCOLS)}
RANKS, RANKS3 = {}, {}
block = RANKS
for r in ranks_raw[1:]:
    if not r: continue
    if str(r[0]).startswith("LAST 3"): block = RANKS3; continue
    if r[0] == "Defense" or r[0] == "": continue
    if len(r) > 1 and num(r[1]) is not None: block[r[0]] = [int(float(x)) if num(x) is not None else None for x in r[1:16]]
def drank(opp, col, last3=False):
    t = (RANKS3 if last3 else RANKS).get(opp); return None if not t or col not in DCOL else t[DCOL[col]]
def rank_color(r):
    t = (r - 1) / 31
    if t < 0.5: h = 140 - 95 * (t / 0.5); l = 0.30 + 0.08 * (t / 0.5)
    else: h = 45 - 45 * ((t - 0.5) / 0.5); l = 0.38 - 0.10 * ((t - 0.5) / 0.5)
    return f"hsl({h:.0f} 62% {l*100:.0f}%)"

# ---- schedule / venues ----
GAMES = []
with open(os.path.join(IN, "games.csv"), newline="") as f:
    for g in csv.DictReader(f):
        if g["season"] == "2026" and g["week"] == str(WEEK) and g["game_type"] == "REG":
            GAMES.append(g)
def game_for(a, b):
    for g in GAMES:
        if {g["away_team"], g["home_team"]} == {a, b}: return g
    return None

# ---- weather by team pair ----
WX = {}
wh = weather_raw[0]
for r in weather_raw[1:]:
    if len(r) < 4 or str(r[0]) != str(WEEK): continue
    r = r + [""] * (16 - len(r))
    _vh = re.search(r"\((\w+) home\)", str(r[4]))
    if _vh and _vh.group(1) not in (r[2], r[3]): continue   # stale row: the matchup columns rolled to this week but the venue/forecast are still last week's refresh (seen Tue 10/20: Week 6 Lambeau wind under CLE-TEN)
    WX[frozenset([r[2], r[3]])] = {"roof": r[5], "temp": num(r[8]), "wind": num(r[9]), "gust": num(r[10]), "ptype": r[11], "pch": num(r[12]), "risk": (r[14] or "").split()[0] if r[14] else "", "updated": r[7]}

# ---- availability ----
OUT_LIST = defaultdict(list); QUEST = {}
for r in avail_raw[1:]:
    if len(r) < 5 or str(r[0]) != str(WEEK): continue
    r = r + [""] * (13 - len(r))
    if r[4] == "OUT": OUT_LIST[r[2]].append((r[1], r[3], r[9]))
    if r[4] == "QUESTIONABLE": QUEST[r[1]] = r[9]

# ---- game scripts ----
SCRIPTS = {}
for r in scripts_raw[1:]:
    if len(r) < 11 or not r[0]: continue
    SCRIPTS[r[0]] = (r[0], r[1], num(r[2]), num(r[3]), num(r[5]), num(r[6]), num(r[7]), num(r[8]), num(r[9]), r[10])

# ---- leg board ----
LEGS = []
for r in legs_raw[1:]:
    if len(r) < 17 or not r[0]: continue
    r = r + [""] * (18 - len(r))
    _p, _bk = pct(r[10]), pct(r[12]); _ps = CALIB.shrink(_p, _bk)   # shown % = raw model blended toward the price (calib.py); edge follows it
    LEGS.append({"player": r[0], "market": r[1], "line": num(r[2]), "odds": num(r[3]), "team": r[4], "opp": r[5], "status": r[6], "proj": num(r[7]),
                 "p": _ps, "fair": r[11], "book": _bk, "edge": (_ps - _bk) if _ps is not None and _bk is not None else pct(r[13]), "verdict": r[14], "warn": r[15], "game": r[16], "kick": r[17], "raw_p": _p})
def odds_str(o):
    if o is None: return ""
    return f"+{int(o)}" if o > 0 else f"{int(o)}"

# ---- player flags (flags.py): this-season form, usage, matchup, weather, script, injuries/vacated volume, FD line hit-rate ----
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flags as FLAGS
FE = FLAGS.Engine(IN, WEEK)
import faceoff as FACEOFF   # receiver face-off on each game card (owner 10/22: Burden over Odunze was visible in usage + corner data)
try: FO = FACEOFF.load(IN, WEEK)
except Exception as e: FO = {}; print("note: receiver face-off unavailable:", e)
def faceoff_block(a, b):
    try: return FACEOFF.block(FO, LEGS, FE.WRCB, a, b)
    except Exception as e: print("note: face-off failed for", a, b, e); return ""
for l in LEGS:
    try: fl = FE.leg(l)
    except Exception: fl = []
    l["flags"] = fl; l["warn"] = FLAGS.warn_text(fl); l["note"] = FLAGS.note_text(fl); l["good"] = FLAGS.good_text(fl); l["hit"] = FLAGS.hit_of(fl)
# ---- projected snap share (projsnaps.py): recency-weighted share, redistributed for same-position OUTs / returners; computed once
# per build, out/projsnaps.json is read by build_builder.py. Shown as a small chip on each player's row; nothing else uses it. ----
import projsnaps as PS
try: PROJSN = PS.build(IN, OUT, WEEK)
except Exception as e: print("warn: projected snaps skipped:", e); PROJSN = {}
def snaps_chip(name):
    s = PROJSN.get(name)
    if not s or s.get("proj") is None: return ""
    l3 = " · ".join(f"{x*100:.0f}" for x in s.get("l3") or [])
    tip = "Projected offensive snap share for this game; last three games newest first" + (f"; {s['why']}" if s.get("why") else "")
    return f'<span class="role sn" title="{E(tip)}">Snaps ~{s["proj"]*100:.0f}%{f" ({l3})" if l3 else ""}</span>'
def flag_tip(l):
    """Tooltip text for a leg: bad / watch / good lines, in that order."""
    parts = []
    for k, lab in (("bad", "RISK"), ("watch", "WATCH"), ("info", "NOTE"), ("good", "PLUS")):
        for f in l.get("flags", []):
            if f["k"] == k: parts.append(f"{lab}: {f['txt']}")
    return " | ".join(parts) if parts else "no flags"
def flags_html(name, team=None, pos=None, opp=None):
    fl = FE.player(name, team, pos, opp)
    if not fl: return '<div class="flags empty"><span class="fg info">no flags</span></div>'
    pills = "".join(f'<span class="fg {f["k"]}" title="{E(f["txt"])}">{E(f["tag"])}</span>' for f in fl)
    items = "".join(f'<li class="{f["k"]}"><b>{E(f["tag"])}</b>{E(f["txt"])}</li>' for f in fl)
    nb = sum(1 for f in fl if f["k"] == "bad"); ng = sum(1 for f in fl if f["k"] == "good")
    return f'<details class="flags"><summary>{pills}<i class="more" title="tap for the full read">{nb} risk · {ng} plus ▾</i></summary><ul>{items}</ul></details>'

# ---- FanDuel main line per player + market (line priced nearest -112) ----
MAIN = {}
for l in LEGS:
    if l["market"] in ("Passing Yards", "Rushing Yards", "Receiving Yards", "Receptions") and l["odds"] is not None and l["line"] is not None:
        k = (l["player"], l["market"]); d = abs(l["odds"] + 112)
        if k not in MAIN or d < MAIN[k][1]: MAIN[k] = (l["line"], d, l["proj"], l)
MK_OF = {"pass yds": "Passing Yards", "rush yds": "Rushing Yards", "rec yds": "Receiving Yards", "rec": "Receptions"}
# owner 10/28: FanDuel's anytime-TD price + a "+" on the TD chip too (RB/QB: the rush TD chip, WR/TE: the TD chip - one per player)
ATD = {}
for l in LEGS:
    if l["market"] == "Anytime TD" and l["odds"] is not None and "/" not in l["player"] and l["player"] not in ATD: ATD[l["player"]] = l
def fd_note(player, label, val):
    if label in ("TD", "rush TD"):
        leg = ATD.get(player)
        if not leg or leg.get("p") is None or leg.get("status") in ("OUT", "BYE"): return ""
        return (f'<span class="fd" title="FanDuel anytime touchdown at {odds_str(leg["odds"])}; model {leg["p"]*100:.0f}%">FD anytime TD'
                f'<small class="fdo">{odds_str(leg["odds"])}</small>{plus_btn(leg)}</span>')
    mk = MK_OF.get(label)
    if not mk or (player, mk) not in MAIN: return ""
    line, _, _, leg = MAIN[(player, mk)]; v = num(val)
    if v is None: return ""
    diff = v - line; cls = "up" if diff > 0 else "down"
    # owner 10/26: "+" right on the stat adds FanDuel's line for it (the rung priced nearest -112) to the betslip
    add = plus_btn(leg) if leg.get("p") is not None and leg.get("status") not in ("OUT", "BYE") else ""
    return (f'<span class="fd {cls}" title="FanDuel main line {line:g}+ at {odds_str(leg["odds"])} (the rung priced nearest -112) vs the model">FD {line:g} <b>{diff:+.0f}</b>'
            f'<small class="fdo">{odds_str(leg["odds"])}</small>{add}</span>')

# ---- boards blocks ----
blocks = []; i = 0
while i < len(boards):
    r = boards[i]
    if r and str(r[0]).startswith("🏈") and " vs " in r[0]:
        m = re.match(r"🏈 (\w+) vs (\w+)", r[0]); players = []; j = i + 2
        while j < len(boards) and boards[j] and boards[j][0] and "|" not in boards[j][0] and not str(boards[j][0]).startswith("🏈"):
            players.append(boards[j] + [""] * (17 - len(boards[j]))); j += 1
        if players: blocks.append((m.group(1), m.group(2), players))
        i = j
    else: i += 1
# Replacement starters with no game log (fillin.py): the real starter takes over the stand-in's row, same projection, tagged
import fillin as FILLIN
FILLS = FILLIN.load(IN, WEEK); FILL_BY_STANDIN = FILLIN.by_standin(FILLS); FILL_BY_NAME = {f["player"]: f for f in FILLS}
for _a, _b, _pl in blocks:
    for _p in _pl:
        f = FILL_BY_STANDIN.get(_p[0])
        if f and _p[2] == f["team"]: _p[0] = f["player"]; _p[7] = "FILL-IN STARTER"
FE.FILLIN = {f["player"]: f["note"] for f in FILLS}
if FILLS: print("fill-in starters:", ", ".join(f"{f['player']} ({f['team']}, for {f['for']}, on {f['standin']}'s row)" for f in FILLS))

def kick_ms(a, b):
    """Kickoff as epoch ms (nflverse gametime is US Eastern); None when the schedule has no time."""
    g = game_for(a, b)
    if not g or not g.get("gametime"): return None
    return int(datetime.datetime.fromisoformat(g["gameday"] + "T" + g["gametime"]).replace(tzinfo=ZoneInfo("America/New_York")).timestamp() * 1000)
def final_text(a, b):
    """'DEN 17 – SEA 14' once the schedule feed carries the final score (refreshed on every rebuild), else ''."""
    g = game_for(a, b)
    if not g or g.get("home_score", "") in ("", None) or g.get("away_score", "") in ("", None): return ""
    hs, as_ = int(float(g["home_score"])), int(float(g["away_score"])); h, aw = g["home_team"], g["away_team"]
    return f"{h} {hs} – {aw} {as_}" if hs >= as_ else f"{aw} {as_} – {h} {hs}"
# order the cards by kickoff (nflverse schedule: gameday + gametime), unknown kickoffs last
def _kick_key(blk):
    g = game_for(blk[0], blk[1])
    return (g["gameday"], g["gametime"]) if g else ("9999-99-99", "99:99")
blocks.sort(key=_kick_key)

# ---------------- rendering helpers ----------------
ICONS = {
 "sun": '<circle cx="12" cy="12" r="4.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1" stroke-linecap="round"/>',
 "moon": '<path d="M20 15.5A8.5 8.5 0 0 1 8.5 4a7 7 0 1 0 11.5 11.5z"/>',
 "cloud": '<path d="M7 18h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.2 9.6 4.2 4.2 0 0 0 7 18z"/>',
 "rain": '<path d="M7 15h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.2 6.6 4.2 4.2 0 0 0 7 15z"/><path d="M8 18l-1 3M12 18l-1 3M16 18l-1 3" stroke-linecap="round"/>',
 "snow": '<path d="M7 14h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.2 5.6 4.2 4.2 0 0 0 7 14z"/><path d="M8 17v4M6.5 18.5l3 1M6.5 20l3-1M12 17v4M10.5 18.5l3 1M10.5 20l3-1M16 17v4M14.5 18.5l3 1M14.5 20l3-1" stroke-linecap="round"/>',
 "wind": '<path d="M3 8h11a2.5 2.5 0 1 0-2.5-2.5M3 12h15a2.5 2.5 0 1 1-2.5 2.5M3 16h9a2 2 0 1 1-2 2" stroke-linecap="round"/>',
 "dome": '<path d="M3 15a9 9 0 0 1 18 0"/><path d="M2 15h20M5 15v4M19 15v4M12 6v-2" stroke-linecap="round"/>'}
# owner 10/29: the player's OWN offense rank in the same stat (offranks.py: rank 1 = his team's position group produces the most per game,
# season + last 3) sits next to the defense rank in every stat box, labelled def / off.
try:
    import offranks as _ORK
    _OR = _ORK.load(IN, WEEK)
except Exception as _e: _OR = None; print("note: offense ranks unavailable on the boards:", _e)
def orank(tm, col, last3=False): return _ORK.rank(_OR, tm, col, "l3" if last3 else "season") if (_OR and tm and col) else None
def chip(label, val, opp, col, fd="", sub="", tm=None):
    """One stat cell: label, projected value (+ an optional sub-line, e.g. the carries behind a rush-yard projection), opponent defense rank pill
    and the player's own offense rank pill (season + L3 each), FanDuel main-line note."""
    if val in ("", None): return ""
    sub = f'<em class="sub">{E(sub)}</em>' if sub else ""
    r = drank(opp, col) if col else None
    o = orank(tm, col); o3 = orank(tm, col, True); r3 = drank(opp, col, True) if r is not None else None
    if r is None and o is None: return f'<span class="sc"><small>{E(label)}</small><b>{E(str(val))}</b>{sub}{fd}</span>'
    # owner 10/29 "when I say matchup, show the literal matchup": his offense's rank in this stat vs the opponent's defense rank, one pill
    tip = ((f"{tm} offense #{o} of 32 in {col} produced" + ("" if o3 is None else f" (last 3 weeks #{o3})") + ", 1 = produces the most") if o else "") + \
          (" | " if (o and r) else "") + ((f"{opp} defense #{r} of 32 in {col} allowed" + ("" if r3 is None else f" (last 3 weeks #{r3})") + ", 1 = allows the most") if r else "")
    mu = (f'<span class="mu">' + (f'<i style="background:{rank_color(o)}">{E(tm)} #{o}</i>' if o else (f'<i style="background:var(--line);color:var(--ink)">{E(tm)}</i>' if tm else '')) + '<b>vs</b>' +
          (f'<i style="background:{rank_color(r)}">{E(opp)} #{r}</i>' if r else f'<i style="background:var(--line);color:var(--ink)">{E(opp)}</i>') + '</span>')
    return (f'<span class="sc"{(' style="--c:' + rank_color(r) + '"') if r else ""} title="{E(tip)}"><small>{E(label)}</small><b>{E(str(val))}</b>{sub}{mu}{fd}</span>')

# advanced view (owner 10/29): every stat, each team's offense rank next to the other team's defense rank, season + last 3
MBS_ROWS = [("QB", "pass yds", "QB Pass Yds"), ("QB", "pass TD", "QB Pass TD"), ("QB", "rush yds", "QB Rush Yds"), ("QB", "rush TD", "QB Rush TD"),
            ("RB", "rush yds", "RB Rush Yds"), ("RB", "rush TD", "RB Rush TD"), ("RB", "rec yds", "RB Rec Yds"), ("RB", "receptions", "RB Receptions"), ("RB", "rec TD", "RB Rec TD"),
            ("WR", "rec yds", "WR Rec Yds"), ("WR", "receptions", "WR Receptions"), ("WR", "rec TD", "WR Rec TD"),
            ("TE", "rec yds", "TE Rec Yds"), ("TE", "receptions", "TE Receptions"), ("TE", "rec TD", "TE Rec TD")]
def _rkc(r, r3):
    if r is None: return "<td>—</td>"
    return f'<td><span class="rkc" style="background:{rank_color(r)}">{r}</span>{"" if r3 is None else f"<small>{r3}</small>"}</td>'
def mbs_block(a, b):
    if not _OR: return ""
    rows, last = [], None
    for pos, lab, col in MBS_ROWS:
        head = f'<tr class="pg"><th colspan="5">{pos}</th></tr>' if pos != last else ""; last = pos
        rows.append(head + f'<tr><th>{E(lab)}</th>{_rkc(orank(a, col), orank(a, col, True))}{_rkc(drank(b, col), drank(b, col, True))}'
                    f'{_rkc(orank(b, col), orank(b, col, True))}{_rkc(drank(a, col), drank(a, col, True))}</tr>')
    return (f'<details class="mbsg"><summary><span class="lt">Matchup by stat <small>each offense vs the other defense, every stat · rank 1 = produces / allows the most · small number = last 3 weeks</small></span></summary>'
            f'<div class="mbtbl"><table><thead><tr><th></th><th>{E(a)} off</th><th>{E(b)} def</th><th>{E(b)} off</th><th>{E(a)} def</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></details>')
# projected carries (owner 10/26): 'AUTO - RB Projections' column BD "Proj Carries" = the carries the rush-yard projection is built on
# (season carries + injury carry transfer, x snap trend). Missing column (old input) -> no chip.
CARRIES = {}
try:
    _v = json.load(open(os.path.join(IN, "proj_rb.json")))["values"]; _h = _v[0]
    if "Proj Carries" in _h:
        _i = _h.index("Proj Carries")
        for _r in _v[1:]:
            if len(_r) > _i and _r[0] and num(_r[_i]): CARRIES[_r[0]] = num(_r[_i])
except Exception: pass
def ei(x, pre=""):
    """edge pill: rounded first (no "-0"), coloured by sign (audit 10/26: "-1" edges were green)"""
    v = int(round((x or 0) * 100)); return f'<i class="{"en" if v < 0 else "ep" if v > 0 else "ez"}">{pre}{"0" if v == 0 else f"{v:+d}"}</i>'
# owner 10/27 (accuracy item 1): FanDuel's implied team total scales yards and TDs ('AUTO - Market Team Points' O:Z, fitted 2019-23 /
# tested 2024-26 - scratchpad volume/results.md). The Leg Board applies the same multipliers in its Model proj column, so the chips here
# show the same numbers the legs are priced from.
TMULT = {}
try:
    _v = json.load(open(os.path.join(IN, "teammkt.json")))["values"]; _h = _v[0]
    _cols = {k: _h.index(k) for k in ("x Pass yds", "x Pass TD", "x Rush yds", "x Rush TD", "x Receptions", "x Rec yds", "x Rec TD") if k in _h}
    if len(_cols) == 7:
        for _r in _v[1:]:
            if _r and _r[0]: TMULT[_r[0]] = {k: (num(_r[i]) if i < len(_r) and num(_r[i]) else 1.0) for k, i in _cols.items()}
except Exception: pass
# 2026-10-29 (owner 10/27 "do the others"): strength-of-schedule multipliers per player (build_sos.py -> out/sos_values.json ->
# 'AUTO - SOS Adjust'; the Leg Board applies them in Model proj as z_s), so the yards / receptions chips match the legs again.
SMULT = {}
try:
    _sv = json.load(open(os.path.join(OUT, "sos_values.json")))["values"]
    for _r in _sv:
        if _r and _r[0]: SMULT[_r[0]] = {"x Pass yds": num(_r[5]) or 1.0, "x Rush yds": num(_r[6]) or 1.0, "x Receptions": num(_r[7]) or 1.0, "x Rec yds": num(_r[8]) or 1.0}
except Exception: pass
def _mx(val, team, key, nd=1, name=None):
    v = num(val); m = (TMULT.get(team, {}).get(key) or 1.0) * (SMULT.get(name, {}).get(key, 1.0) if name else 1.0)
    if v is None or abs(m - 1) < 1e-9: return val
    return f"{v * m:.{nd}f}"
def statline(p):
    pos, opp, nm = p[3], p[4], p[0]; py, ry, rcy, rec, ptd, rtd, rctd = p[8:15]
    tm_ = p[2]; py, ry, rcy, rec = _mx(py, tm_, "x Pass yds", 1, nm), _mx(ry, tm_, "x Rush yds", 1, nm), _mx(rcy, tm_, "x Rec yds", 1, nm), _mx(rec, tm_, "x Receptions", 1, nm)
    ptd, rtd, rctd = _mx(ptd, tm_, "x Pass TD", 2), _mx(rtd, tm_, "x Rush TD", 2), _mx(rctd, tm_, "x Rec TD", 2)
    def c(label, val, col): return chip(label, val, opp, col, fd_note(nm, label, val), tm=tm_)
    if pos == "QB": return c("pass yds", py, "QB Pass Yds") + chip("pass TD", ptd, opp, "QB Pass TD", tm=tm_) + c("rush yds", ry, "QB Rush Yds") + c("rush TD", rtd, "QB Rush TD")
    # owner 10/27: carries ride inside the rush-yards box (their own box cluttered the card)
    if pos == "RB": return chip("rush yds", ry, opp, "RB Rush Yds", fd_note(nm, "rush yds", ry), f"{CARRIES[nm]:.1f} carries" if nm in CARRIES else "", tm=tm_) + c("rec yds", rcy, "RB Rec Yds") + c("rec", rec, "RB Receptions") + c("rush TD", rtd, "RB Rush TD") + chip("rec TD", rctd, opp, "RB Rec TD", tm=tm_)
    if pos in ("WR", "TE"): return c("rec yds", rcy, pos + " Rec Yds") + c("rec", rec, pos + " Receptions") + c("TD", rctd, pos + " Rec TD")
    return ""
def leg_html(t, name=""):
    if not t or t.startswith("no FanDuel"): return '<span class="leg none"><em>Best leg</em>no FanDuel line yet</span>'
    parts = [s.strip() for s in t.lstrip("! ").split("|")]
    market, odds, edge = (parts + ["", "", ""])[:3]; ev = num(edge)
    cls = "pos" if ev is not None and ev >= 0 else "neg"
    # the flag on the best leg is the player's risk flags plus the this-season hit rate for that exact line
    w = ""
    m = re.match(r"(.*?)\s+(\d+(?:\.\d+)?)\+$", market)
    lk = {"player": name, "market": m.group(1) if m else market, "line": num(m.group(2)) if m else (1 if "TD" in market else None), "team": None, "opp": None}
    try: fl = FE.leg(lk) if name else []
    except Exception: fl = []
    bad = [f for f in fl if f["k"] == "bad"]
    if bad: w = f'<span class="warn" title="{E(" | ".join(f["txt"] for f in bad))}">!</span>'
    fdb = ""
    if name:
        match = [l for l in LEGS if l["player"] == name and l["market"] == lk["market"] and l["line"] == lk["line"]]
        if match: fdb = fd_button(match[:1], "best leg")
    return f'<span class="leg"><em>Best leg</em>{w}<span class="mk">{E(market)}</span><span class="od">{E(odds)}</span><span class="ed {cls}">{E(edge)}</span>{fdb}</span>'
def dsummary(opp, team):
    items = [("QB", "QB Pass Yds"), ("RB", "RB Rush Yds"), ("WR", "WR Rec Yds"), ("TE", "TE Rec Yds")]   # position overalls; the per-stat ranks live in each player's dropdown
    out = []
    for lab, col in items:
        r = drank(opp, col); r3 = drank(opp, col, True)
        if r is None: continue
        out.append(f'<span class="dm" style="--c:{rank_color(r)}" title="{E(opp)} ranks #{r} of 32 in {E(col)} allowed this season{"" if r3 is None else f", #{r3} last 3 weeks"}"><span class="dl">{lab}</span><b>#{r}</b>{"" if r3 is None else f"<u>L3 #{r3}</u>"}</span>')
    inj = OUT_LIST.get(team, [])
    injhtml = "" if not inj else '<li class="inj"><span>Out this week</span>' + "".join(f'<em>{E(n)} <small>{E(p)} · {E(w[:60])}</small></em>' for n, p, w in inj) + '</li>'
    return f'<li class="dsum">{badge(team)}<span>vs {E(opp)} D</span><span class="dgrid">{"".join(out)}</span></li>' + injhtml
from urllib.parse import quote as _q
_NEWS_SVG = '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path fill="currentColor" d="M2 3h9v10H3a1 1 0 0 1-1-1V3zm10 2h2v7a1 1 0 0 1-1 1h-1V5zM4 5v2h5V5H4zm0 3.5v1h5v-1H4zm0 2v1h5v-1H4z"/></svg>'
_ESPN_ID = None
def _espn_ids():
    """name -> ESPN player id from the nflverse roster (in/roster_2026.csv; downloaded once if a build step has not already fetched it).
    Latest week wins, so a traded player keeps one id either way (ids never change)."""
    global _ESPN_ID
    if _ESPN_ID is not None: return _ESPN_ID
    _ESPN_ID = {}
    rp = os.path.join(HERE, "in", "roster_2026.csv")
    try:
        if not os.path.exists(rp):
            import urllib.request
            urllib.request.urlretrieve("https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_2026.csv", rp)
        import csv as _csv
        best = {}
        for r in _csv.DictReader(open(rp, newline="")):
            eid = (r.get("espn_id") or "").strip()
            if not eid or eid == "NA": continue
            try: wk = int(r.get("week") or 0)
            except ValueError: wk = 0
            for nm in {(r.get("full_name") or "").strip(), ((r.get("football_name") or "").strip() + " " + (r.get("last_name") or "").strip()).strip()}:
                if nm and (nm not in best or wk >= best[nm][0]): best[nm] = (wk, eid.split(".")[0])
        _ESPN_ID = {k: v[1] for k, v in best.items()}
        print(f"news links: ESPN ids for {len(_ESPN_ID)} roster names")
    except Exception as e:
        print("warn: news links fall back to Google News (roster not read):", e)
    return _ESPN_ID
_CARD_SVG = '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path fill="currentColor" d="M2.5 2h11A1.5 1.5 0 0 1 15 3.5v9a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 1 12.5v-9A1.5 1.5 0 0 1 2.5 2zm0 1.3a.2.2 0 0 0-.2.2v9c0 .1.1.2.2.2h11c.1 0 .2-.1.2-.2v-9a.2.2 0 0 0-.2-.2h-11zM5.5 5a1.6 1.6 0 1 1 0 3.2 1.6 1.6 0 0 1 0-3.2zM3 11c0-1.3 1.1-2.1 2.5-2.1S8 9.7 8 11H3zm6.5-5.5H13v1.2H9.5V5.5zm0 2.5H13v1.2H9.5V8z"/></svg>'
def _pslug(name):
    # same rule as plydata.slugify (dots dropped, Jr/Sr/II.. dropped) so the link lands on build_players.py's page
    s = re.sub(r"\.", "", str(name)).strip(); s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s, flags=re.I); s = re.sub(r"\s+", " ", s).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")
def news_icon(name):
    """Owner 10/31: the icon next to a player's name now opens his BetSweep player page (/player/<slug>/: lines at every book, hit
    rates, game log) in the same tab; the ESPN news link lives on that page. (10/22-10/30 it opened ESPN player news / Google News.)
    A span (not <a>) because the row is a <button>; template.html follows it and stops the tap from also opening the row.
    The function keeps its old name so nothing else changes."""
    u = f"/player/{_pslug(name)}/"
    return f'<span class="newsl" role="link" tabindex="0" data-href="{E(u)}" title="{E(name)}: player page" aria-label="Player page: {E(name)}">{_CARD_SVG}</span>'

_PL_ORDER = ("Passing Yards", "Rushing Yards", "Receiving Yards", "Receptions", "Rush + Rec Yards", "Anytime TD")
_PL_SHORT = {"Passing Yards": "Pass yds", "Rushing Yards": "Rush yds", "Receiving Yards": "Rec yds", "Receptions": "Rec", "Rush + Rec Yards": "Rush+rec", "Anytime TD": "TD"}
_PL_BY = None
CHIP_USED = set()   # leg keys on a player-dropdown chip: embedded as that single rung only (no ladder, no flag triples) to keep the page light
def _chip_btn(l):
    k = leg_key(l); CHIP_USED.add(k)
    return f'<button type="button" class="addmini addbs" data-k="{E(k)}" title="Add {E(l["player"])} {E(l["market"].lower())}{(" " + format(l["line"], "g") + "+") if l.get("line") and l["market"] not in ("Anytime TD", "First TD") else ""} to your betslip" aria-label="Add {E(l["player"])} {E(l["market"].lower())} to your betslip">+</button>'
def player_legs_html(name):
    """Owner 10/25: bet a player straight from his boards dropdown. One rung per market - the best model edge among unflagged rungs the
    model gives 55-85% (parlay-leg range; else any 55-85% rung; else the rung closest to 70%; anytime TD has one rung) - each with a + that drops it into the shared slip (same key as the parlay builder, so it
    shows up there too), and a link that opens the builder filtered to him for every rung and market."""
    global _PL_BY
    if _PL_BY is None:
        _PL_BY = defaultdict(list)
        for l in LEGS:
            if l["market"] in _PL_SHORT and l["p"] is not None and l["book"] is not None and l["odds"] is not None and l["status"] not in ("OUT", "BYE"):
                _PL_BY[(l["player"], l["market"])].append(l)
    chips = []
    for mk in _PL_ORDER:
        rungs = _PL_BY.get((name, mk))
        if not rungs: continue
        mid = [x for x in rungs if 0.55 <= x["p"] <= 0.85 and not x.get("warn")] or [x for x in rungs if 0.55 <= x["p"] <= 0.85]
        l = max(mid, key=lambda x: (x["p"] - x["book"], x["p"])) if mid else min(rungs, key=lambda x: abs(x["p"] - 0.70))
        ln = "" if mk == "Anytime TD" else f' {int(l["line"]) if l["line"] == int(l["line"]) else l["line"]}+'
        e = l["p"] - l["book"]; w = '<i class="pw" title="' + E(str(l.get("warn"))[:90]) + '">!</i>' if l.get("warn") else ""
        chips.append(f'<span class="pleg">{w}<b>{_PL_SHORT[mk]}{ln}</b><small>{odds_str(l["odds"])}</small><span class="pp {"up" if e >= 0 else "down"}">{l["p"]*100:.0f}%</span>{_chip_btn(l)}</span>')
    url = "https://betsweep.co/build/?p=" + _q(str(name))
    link = f'<a class="pall" href="{E(url)}" title="Open the parlay builder filtered to {E(name)}: every market and rung">All his legs &rarr;</a>'
    # owner 10/27: the "Add to slip" chip row is gone (the best leg + the builder link cover it); the link stays
    return f'<div class="plegs">{link}</div>'

def team_col(players, team, maxppr):
    opp = [x for x in players if x[2] == team][0][4]
    rows = [dsummary(opp, team)]
    POSORD = {"QB": 0, "RB": 1, "WR": 2, "TE": 3}; seen_pos = {}
    for p in sorted([x for x in players if x[2] == team], key=lambda x: (POSORD.get(x[3], 9), -(num(x[5]) or 0))):
        ppr = num(p[5]) or 0; role = p[7]
        keep = {"QB": 1, "RB": 1, "WR": 2, "TE": 1}.get(p[3], 0); seen_pos[p[3]] = seen_pos.get(p[3], 0) + 1
        xtra = "" if seen_pos[p[3]] <= keep else " xtra"
        chipr = ""  # role signal now lives in the flag strip
        q = f'<span class="role note" title="{E(QUEST[p[0]])}">Questionable</span>' if p[0] in QUEST else ""
        gdst = GAMEDAY.get(p[0].lower())
        if gdst:
            st = gdst["status"]
            if st.startswith("CONFIRMED"): q += f'<span class="role down gd" title="{E(gdst["note"])} ({E(gdst["time"])})">OUT - inactive</span>'
            elif st.startswith("PROPS") or st.startswith("UNCONF"): q += f'<span class="role note gd" title="{E(gdst["note"])} ({E(gdst["time"])})">props pulled - verify</span>'
            elif st.startswith("ACTIVE") or st.startswith("FALSE"): q += f'<span class="role up gd" title="{E(gdst["note"])} ({E(gdst["time"])})">Active (game day)</span>'
        if gdst and gdst["status"].startswith("CONFIRMED"): xtra += " scratched"
        q += snaps_chip(p[0])   # 'Snaps ~65% (73 · 66 · 50)': projected share, last three played games newest first (skipped when he has no 2026 snaps)
        rows.append(f'''<li class="pl pos-{p[3]}{xtra}">
  <button type="button" class="prow" aria-expanded="false"><span class="pos">{p[3]}</span><span class="who"><span class="nm">{E(p[0])}{news_icon(p[0])}</span>{q}</span>
   <span class="ppr"><span class="v"><small>Proj</small>{p[5]}<small>fantasy pts</small></span><i style="--w:{(ppr/maxppr*100) if maxppr else 0:.1f}%"></i><span class="rk">#{p[6]} {p[3]}</span></span><i class="car" aria-hidden="true">▾</i></button>
  <div class="pdetail" hidden><div class="sl">{statline(p)}</div>{flags_html(p[0], p[2], p[3], p[4])}{leg_html(p[15], p[0])}{player_legs_html(p[0])}</div></li>''')
    return "\n".join(rows)

# ---- alt-line ladders ----
LADDER_MARKETS = ("Receiving Yards", "Rushing Yards", "Passing Yards", "Receptions", "Longest Reception")
def ladders_for(team, players, n=2):
    by = defaultdict(list)
    for l in LEGS:
        if l["team"] == team and l["market"] in LADDER_MARKETS and l["p"] is not None and l["line"] is not None: by[(l["player"], l["market"])].append(l)
    cands = [(k, sorted(v, key=lambda x: x["line"])) for k, v in by.items() if len(v) >= 3]
    ppr = {p[0]: num(p[5]) or 0 for p in players}
    cands.sort(key=lambda kv: (-len(kv[1]), -ppr.get(kv[0][0], 0)))
    out = []
    for (pl, mk), rungs in cands[:n]:
        cells = []
        for l in rungs:
            cls = "up" if (l["edge"] or 0) >= 0 else "down"; w = "!" if l["warn"] else ""
            cells.append(f'<span class="rung {cls}" title="{E(flag_tip(l))}"><b>{int(l["line"]) if l["line"]==int(l["line"]) else l["line"]}+</b><span>{l["p"]*100:.0f}%</span><small>{odds_str(l["odds"])}</small>{ei(l["edge"], w)}</span>')
        out.append(f'<div class="ladder"><span class="lt">{E(pl)} <small>{E(mk.lower())}</small></span>{"".join(cells)}</div>')
    return "".join(out)

# ---- script plays (probit transform) ----
SC_IDX = {"LEAD": 0, "CLOSE_LOW": 1, "SHOOTOUT": 2, "TRAIL": 3}
STAT_OF = {"Passing Yards": "passing_yards", "Rushing Yards": "rushing_yards", "Receiving Yards": "receiving_yards", "Receptions": "receptions"}
def ncdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def nppf(p):  # Acklam
    a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00]
    b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,6.680131188771972e+01,-1.328068155288572e+01]
    c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,-2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00]
    d=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl: q = math.sqrt(-2*math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph: q = math.sqrt(-2*math.log(1-p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5; r = q*q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
def roles_for(players):
    roles = {}
    for pos in ("QB", "RB", "WR", "TE"):
        for team in {p[2] for p in players}:
            ps = sorted([p for p in players if p[3] == pos and p[2] == team], key=lambda x: -(num(x[5]) or 0))
            for k, p in enumerate(ps, 1): roles[p[0]] = f"{pos}{k}"
    return roles
SC_LABEL = lambda a, b: [f"{a} by 10+", "close, low", "shootout", f"{b} by 10+"]
def script_plays(a, b, players, s, k=None):
    """Top legs if script k happens (default: the most-likely script). s = SCRIPTS tuple for team a."""
    probs = s[5:9]; kk = max(range(4), key=lambda i: probs[i] or 0)
    if k is None: k = kk
    most = s[9] if k == kk else SC_LABEL(a, b)[k]
    sc_a = ["LEAD", "CLOSE_LOW", "SHOOTOUT", "TRAIL"][k]; sc_b = {"LEAD": "TRAIL", "TRAIL": "LEAD"}.get(sc_a, sc_a)
    roles = roles_for(players); out = []
    for l in LEGS:
        if l["team"] not in (a, b) or l["p"] is None or l["book"] is None or l["status"] in ("OUT", "BYE"): continue
        sc = sc_a if l["team"] == a else sc_b; role = roles.get(l["player"], ""); p = l["p"]
        if l["market"] == "Anytime TD":
            key = f"{role}|td"
            if key not in MULT or "/" in l["player"]: continue
            m = MULT[key][SC_IDX[sc]] or 1
            ps = min(0.99, max(0.01, 1 - (1 - p) ** m))
            out.append((ps - l["book"], ps, l, sc)); continue
        st = STAT_OF.get(l["market"]); key = f"{role}|{st}"
        if key not in PROBIT: continue
        ab = PROBIT[key][SC_IDX[sc]*2: SC_IDX[sc]*2+2]
        ps = min(0.99, max(0.01, ncdf(ab[0] + ab[1] * nppf(min(0.99, max(0.01, p))))))
        out.append((ps - l["book"], ps, l, sc))
    out.sort(key=lambda x: -x[0])
    seen = set(); picks = []
    for e, ps, l, sc in out:
        if (l["player"], l["market"]) in seen or ps < (0.40 if l["market"] == "Anytime TD" else 0.55): continue
        if l["warn"]: continue   # owner 10/21 (Kalif Raymond / Xavier Hutchinson): a leg with a risk flag - cold last 3, targets or snaps falling, boom/bust, fill-in - never rides in a listed parlay, this strip included
        seen.add((l["player"], l["market"])); picks.append((e, ps, l, sc))
        if len(picks) == 4: break
    if not picks: return "", most
    items = "".join(f'<span class="sp{" w" if l["warn"] else ""}" title="{E(flag_tip(l))}">{E(l["player"])} {"anytime TD" if l["market"]=="Anytime TD" else E(l["market"].lower()) + " " + str(int(l["line"])) + "+"} <small>{odds_str(l["odds"])}</small><b>{ps*100:.0f}%</b>{ei(e)}{plus_btn(l)}</span>' for e, ps, l, sc in picks)
    return f'<div class="splays" data-sc="{k}"><span class="lt">If {E(most)} <small>({probs[k]:.0f}%)</small></span>{items}{fd_button([l for _, _, l, _ in picks], "script")}</div>', most

def wx_block(a, b, kick_hour):
    w = WX.get(frozenset([a, b]))
    if not w: return ""
    roof, temp, wind, gust, ptype, pch, risk = w["roof"], w["temp"], w["wind"], w["gust"], w["ptype"], w["pch"], w["risk"] or "LOW"
    if roof == "dome": ic, lab = "dome", "Dome"
    elif ptype.startswith("snow"): ic, lab = "snow", "Snow"
    elif ptype.startswith("rain") or (pch or 0) >= 40: ic, lab = "rain", ("Rain likely" if ptype == "rain" else "Rain possible")
    elif (wind or 0) >= 15 or (gust or 0) >= 30: ic, lab = "wind", "Windy"
    elif (pch or 0) >= 15: ic, lab = "cloud", "Cloudy"
    else: ic, lab = ("moon", "Clear night") if kick_hour >= 19 else ("sun", "Clear")
    svg = f'<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">{ICONS[ic]}</svg>'
    if roof == "dome": head, txt = "Dome", "indoors · no weather"
    elif temp is None: head, txt = lab, "forecast pending"
    else:
        head = f"{lab} · {temp:.0f}°F"
        txt = f"wind {wind:.0f} mph" + (f" (gusts {gust:.0f})" if (gust or 0) >= 20 else "") + f" · {pch:.0f}% precip" + (" · roof can close" if roof == "retractable" else "")
    return (f'<span class="wx r-{risk.lower()}" title="{E(txt)} · kickoff-hour forecast, Open-Meteo, updated {E(w["updated"])}">{svg}{head}{f" <u>{risk}</u>" if risk in ("HIGH", "MED") else ""}'
            f'{"" if roof == "dome" or temp is None else f"<small>, wind {wind:.0f}" + (f" (g {gust:.0f})" if (gust or 0) >= 20 else "") + f", {pch:.0f}% precip</small>"}</span>')

# ---- SGP pricing: Gaussian copula, Monte Carlo (deterministic seed) ----
import random
CODE_OF = {"Passing Yards": "PASS", "Rushing Yards": "RUSH", "Receiving Yards": "RECYDS", "Receptions": "REC", "Longest Reception": "LONG", "Anytime TD": "TD"}
def leg_code(l, players):
    pos = next((p[3] for p in players if p[0] == l["player"]), None)
    if not pos: return None
    return f"{pos}_{CODE_OF.get(l['market'], '')}"
GLCORR = json.load(open(os.path.join(HERE, "glcorr.json")))["rho"]   # stat-vs-margin/total copula correlations (nflverse 2023-25)
def gl_prop_corr(gl, c):
    """Correlation between a game-line leg and a player leg with code pos_STAT in the same game: margin legs by whether the line is on the player's team, total legs by over/under."""
    r = GLCORR.get(c)
    if not r: return 0.0
    if gl["gl"]["k"] == "M": return r["margin"] if gl["gl"]["side"] == gl.get("_pteam") else -r["margin"]
    return r["total"] if gl["gl"]["side"] == "OVER" else -r["total"]
def corr_between(l1, c1, l2, c2):
    if l1.get("gl") and l2.get("gl"):
        if l1["gl"]["k"] != l2["gl"]["k"]: return 0.0
        return 0.999 if l1["gl"]["side"] == l2["gl"]["side"] else -0.999
    if l1.get("gl") or l2.get("gl"):
        gl, pl, c = (l1, l2, c2) if l1.get("gl") else (l2, l1, c1)
        if not c: return 0.0
        gl = dict(gl); gl["_pteam"] = pl["team"]; return gl_prop_corr(gl, c)
    if l1["player"] == l2["player"]: rel = "SP"
    elif l1["team"] == l2["team"]: rel = "TM"
    else: rel = "OPP"
    a, b = sorted([c1, c2]); return CORR.get(f"{rel}|{a}|{b}", 0.0)
def chol(C):
    n = len(C); L = [[0.0]*n for _ in range(n)]
    for i in range(n):
        for j in range(i+1):
            ssum = sum(L[i][k]*L[j][k] for k in range(j))
            if i == j: L[i][j] = math.sqrt(max(C[i][i]-ssum, 1e-9))
            else: L[i][j] = (C[i][j]-ssum)/L[j][j]
    return L
def joint_prob(ps, C, n=30000):
    k = len(ps); z = [nppf(min(0.995, max(0.005, p))) for p in ps]
    L = chol(C); rng = random.Random(7); hits = 0
    for _ in range(n):
        g = [rng.gauss(0, 1) for _ in range(k)]
        ok = True
        for i in range(k):
            x = sum(L[i][j]*g[j] for j in range(i+1))
            if x > z[i]: ok = False; break      # leg hits when latent < Phi^-1(p)
        hits += ok
    return hits / n
def fair_odds(p):
    if p <= 0 or p >= 1: return ""
    return f"+{(1/p-1)*100:.0f}" if p < 0.5 else f"-{p/(1-p)*100:.0f}"
def slip_for(a, b, players, s, k=None):
    """Pick up to 3 legs from the script-play candidates (distinct players), price base + if-script with correlations."""
    probs = s[5:9]; kk = max(range(4), key=lambda i: probs[i] or 0)
    if k is None: k = kk
    most = s[9] if k == kk else SC_LABEL(a, b)[k]
    sc_a = ["LEAD", "CLOSE_LOW", "SHOOTOUT", "TRAIL"][k]; sc_b = {"LEAD": "TRAIL", "TRAIL": "LEAD"}.get(sc_a, sc_a)
    roles = roles_for(players); cands = []
    for l in LEGS:
        if l["team"] not in (a, b) or l["p"] is None or l["book"] is None or l["status"] in ("OUT", "BYE") or l["warn"]: continue
        if GAMEDAY.get(l["player"].lower(), {}).get("status", "").startswith("CONFIRMED"): continue
        sc = sc_a if l["team"] == a else sc_b; role = roles.get(l["player"], ""); p = l["p"]
        if l["market"] == "Anytime TD":
            key = f"{role}|td"
            if key not in MULT or "/" in l["player"]: continue
            ps = min(0.99, max(0.01, 1 - (1 - p) ** (MULT[key][SC_IDX[sc]] or 1)))
        else:
            key = f"{role}|{STAT_OF.get(l['market'], '')}"
            if key not in PROBIT: continue
            ab = PROBIT[key][SC_IDX[sc]*2: SC_IDX[sc]*2+2]
            ps = min(0.99, max(0.01, ncdf(ab[0] + ab[1] * nppf(min(0.99, max(0.01, p))))))
        if p < 0.55 and l["market"] != "Anytime TD": continue
        if l["market"] == "Anytime TD" and p < 0.40: continue
        cands.append((ps - l["book"], ps, l))
    cands.sort(key=lambda x: -x[0]); picks = []; used = set()
    for e, ps, l in cands:
        if l["player"] in used or e < -0.02: continue
        used.add(l["player"]); picks.append((e, ps, l))
        if len(picks) == 3: break
    if len(picks) < 2: return ""
    codes = [leg_code(l, players) or "" for _, _, l in picks]
    n = len(picks); C = [[1.0]*n for _ in range(n)]
    for i in range(n):
        for j in range(i+1, n): C[i][j] = C[j][i] = corr_between(picks[i][2], codes[i], picks[j][2], codes[j])
    p_base = joint_prob([l["p"] for _, _, l in picks], C); p_script = joint_prob([ps for _, ps, _ in picks], C)
    ind_book = 1.0
    for _, _, l in picks: ind_book *= l["book"]
    legs_html = "".join(f'<span class="sp">{E(l["player"])} {"anytime TD" if l["market"]=="Anytime TD" else E(l["market"].lower()) + " " + str(int(l["line"])) + "+"} <small>{odds_str(l["odds"])}</small><b>{l["p"]*100:.0f}%</b>{plus_btn(l)}</span>' for _, _, l in picks)
    return (f'<div class="slip" data-sc="{k}"><span class="lt">BetSweep slip <small>{n} legs, same-game links priced</small></span>{legs_html}'
            f'<span class="sfair">fair <b>{fair_odds(p_base)}</b> <small>({p_base*100:.0f}%)</small> · if {E(most)} <b>{fair_odds(p_script)}</b> <small>({p_script*100:.0f}%)</small> · book legs multiply to {fair_odds(ind_book)}</span>'
            f'<span class="stake">Take it at <b>{fair_odds(p_base * 0.95)}</b> or better</span>{fd_button([l for _, _, l in picks], "slip")}</div>')


# ---- Best Parlay: the slip most likely to cash at a FanDuel price between -110 and +500, built from the script strips ----
def dec_odds(o): return 1 + o/100 if o > 0 else 1 + 100/(-o)
def am_from_dec(d): return f"+{(d-1)*100:.0f}" if d >= 2 else f"-{100/(d-1):.0f}"
BP_LO, BP_HI = 100/110 + 1, 6.0      # -110 .. +500 as decimal odds
import gamelines as GLM
GL_FD = GLM.load_fd(IN); GL_SCHED = GLM.load_sched(IN, WEEK)
GL_LEGS = []   # every game-line leg the boards show (for the betslip dataset)
GL_MT = {}   # gid -> (model margin a-b, model total) for glbooks.py's nearest-number pricing
def gl_legs(a, b, s):
    """Moneyline / spread / total legs for this game, priced per game script (gamelines.py), as leg dicts the best parlay can use."""
    out = []; GL_MT[f"{a}-{b}"] = ((s[2] or 0) - (s[3] or 0), (s[2] or 0) + (s[3] or 0))
    for x in GLM.game_legs(a, b, s[2] or 0, s[3] or 0, list(s[5:9]), GL_SCHED, GL_FD):
        if x.get("alt"): continue   # alternate spreads/totals live on the parlay builder; the best parlay sticks to FanDuel's main lines
        l = {"player": x["disp"], "market": x["m"], "line": x["ln"], "odds": x["o"], "book": x["bk"], "p": x["p"], "team": x["tm"], "opp": x["opp"], "status": "",
             "warn": x["risk"], "hit": None, "gl": {"k": x["k"], "side": x["side"]}, "ps": x["ps"], "src": x["src"], "g": f"{a}-{b}",
             "fdid": (x["fd"][1], x["fd"][2]) if x["fd"] and x["fd"][1] and x["fd"][2] else None,
             "flags": ([{"k": "bad", "tag": "Model vs market", "txt": x["risk"]}] if x["risk"] else []) + [{"k": "info", "tag": "Game line", "txt": x["why"]}]}
        out.append(l); GL_LEGS.append(l)
    return out
BP_ROWS = {}   # gid -> best_parlay's scored legs (each with its chance under all four endings) - reused for "legs that hit either way"
def best_parlay(a, b, players, s, wts=None):
    """Legs come from the four script strips (top plays under each ending); each leg's chance is averaged over the model's
    script odds so the slip does not depend on one ending. Pick the combination (2-4 legs, distinct players, 2+ scripts
    represented) with the highest joint hit chance whose FanDuel price lands between -110 and +500 and is not worse than the
    model's fair price; if nothing in range is +EV, take the best-EV build in range and say so. Returns (html, record)."""
    probs = [(x or 0) / 100 for x in (wts or s[5:9])]; tot = sum(probs) or 1; w = [x / tot for x in probs]
    roles = roles_for(players); rows = {}
    for l in LEGS:
        if l["team"] not in (a, b) or l["p"] is None or l["book"] is None or l["odds"] is None or l["status"] in ("OUT", "BYE", "QUESTIONABLE"): continue   # a questionable player is not a "cash often" leg
        # trend gate: a line the player has cleared in only a minority of recent games is not a "cash often" leg; other
        # warnings (projection far from season average / market) stay in but are shown with a flag
        h = l.get("hit"); trend_bad = bool(h and h[1] >= 3 and h[0] / h[1] <= 0.4)
        if trend_bad and h[0] / h[1] < 0.3: continue   # never use a line he has cleared under 30% of the time this season
        if GAMEDAY.get(l["player"].lower(), {}).get("status", "").startswith("CONFIRMED"): continue
        if "/" in l["player"]: continue
        # owner 10/27: best-parlay player legs come from the Model's Best tier only (Weeks 6-7: 65%+ legs at or above the price hit 64.9%;
        # even-money lines the model is 8+ pts above hit 55%) - TDs keep their own rule below
        _rp = l.get("raw_p"); _o = l.get("odds")
        if l["market"] != "Anytime TD" and not (_rp is not None and l["book"] is not None and ((l["p"] >= 0.65 and _rp >= l["book"]) or (_o is not None and -135 <= _o <= 115 and _rp - l["book"] >= 0.08))): continue
        if l["market"] == "Anytime TD" and not (_rp is not None and _rp >= l["book"] and _o is not None and _o <= 200): continue
        role = roles.get(l["player"], ""); p = l["p"]; ps = []
        for k in range(4):
            sc_a = ["LEAD", "CLOSE_LOW", "SHOOTOUT", "TRAIL"][k]; sc = sc_a if l["team"] == a else {"LEAD": "TRAIL", "TRAIL": "LEAD"}.get(sc_a, sc_a)
            if l["market"] == "Anytime TD":
                key = f"{role}|td"
                if key not in MULT: ps = None; break
                ps.append(min(0.99, max(0.01, 1 - (1 - p) ** (MULT[key][SC_IDX[sc]] or 1))))
            else:
                key = f"{role}|{STAT_OF.get(l['market'], '')}"
                if key not in PROBIT: ps = None; break
                ab = PROBIT[key][SC_IDX[sc]*2: SC_IDX[sc]*2+2]
                ps.append(min(0.99, max(0.01, ncdf(ab[0] + ab[1] * nppf(min(0.99, max(0.01, p)))))))
        if ps is None: continue
        floor = 0.40 if l["market"] == "Anytime TD" else 0.55
        # risk flags count against a leg here: the model's % is season-weighted, the flags are recency-weighted, and a "cash often" slip
        # should not lean on a player whose usage, form, snaps or matchup have turned (3+ risk flags = out; otherwise -6% per flag for ranking)
        nbad = sum(1 for f in l.get("flags", []) if f["k"] == "bad" and not f["tag"].startswith("O/U"))
        if nbad >= 3: continue
        # owner 10/22 (Hutchinson in the HOU best parlay after his target-competition flag): a ROLE-risk flag keeps the leg out entirely -
        # same list as home.py ROLE_RISK; trail script only on rushing / TD legs. Context flags (matchup, total, hit rate) still just cost 6%.
        if any(f["k"] == "bad" and (f["tag"].startswith(ROLE_RISK) or (f["tag"] == "Trail script" and l["market"] in ("Rushing Yards", "Rush + Rec Yards", "Anytime TD"))) for f in l.get("flags", [])): continue
        prob = sum(w[k] * ps[k] for k in range(4))
        rows[id(l)] = {"l": l, "ps": ps, "prob": prob, "padj": prob * (1 - 0.06 * nbad), "nbad": nbad, "pmin": min(ps), "scripts": set(), "floor": floor, "tb": trend_bad}
    # game lines (moneyline / spread / total) compete for the same slip: each already carries its chance under each ending, so it mixes with
    # the player legs coherently (a JAX -2.5 is near-certain when the game ends "JAX by 10+" and a coin flip when it ends close). Legs where the
    # model and the market disagree by 4+ points are left out (the model's game projections are not back-tested yet).
    for l in gl_legs(a, b, s):
        if l["warn"]: continue
        ps = l["ps"]; prob = sum(w[k] * ps[k] for k in range(4))
        rows[id(l)] = {"l": l, "ps": ps, "prob": prob, "padj": prob, "nbad": 0, "pmin": min(ps), "scripts": set(), "floor": 0.55, "tb": False}
    BP_ROWS[f"{a}-{b}"] = rows
    # script membership: a leg "belongs" to an ending when it is a play under that ending - clears the strip's probability floor
    # and is priced at or better than fair there (the card's strip shows the top four of these; the parlay may use any of them)
    for k in range(4):
        for r in rows.values():
            if r["ps"][k] >= r["floor"]: r["scripts"].add(k)
    # keep legs priced within a few points of fair (edge >= -3 pts); loosen to -6 when the book leaves a game thin
    # legs the player has cleared under half the time lately are a last resort (flagged on the chip when used)
    nplayers = lambda rs: len({r["l"]["player"] for r in rs})
    cands = [r for r in rows.values() if r["scripts"] and not r["tb"] and r["prob"] - r["l"]["book"] >= -0.015]
    if nplayers(cands) < 4: cands = [r for r in rows.values() if r["scripts"] and not r["tb"] and r["prob"] - r["l"]["book"] >= -0.03]
    if nplayers(cands) < 4: cands = [r for r in rows.values() if r["scripts"] and r["prob"] - r["l"]["book"] >= -0.03]
    # one line per player: keep his most likely strip leg
    byp = {}
    for r in cands:
        pl = (r["l"]["player"], r["l"]["market"])
        if pl not in byp or r["prob"] > byp[pl]["prob"]: byp[pl] = r
    cands = sorted(byp.values(), key=lambda r: -(r["padj"] + (r["prob"] - r["l"]["book"])))[:18]
    if len(cands) < 2: return "", None
    codes = {id(r): (leg_code(r["l"], players) or "") for r in cands}
    import itertools
    def enumerate_combos(min_scripts):
        out = []
        for n in (2, 3, 4):
            for combo in itertools.combinations(cands, n):
                if len({r["l"]["player"] for r in combo}) < n: continue
                gk = [r["l"]["gl"]["k"] for r in combo if r["l"].get("gl")]
                if len(gk) != len(set(gk)): continue   # one margin leg (ML or spread) and one total leg at most
                d = 1.0
                for r in combo: d *= dec_odds(r["l"]["odds"])
                if d < BP_LO or d > BP_HI: continue
                # script-coherent screen: the legs share ONE game ending, so the slip's chance is the mix over endings of
                # "all legs hit given that ending" - not the product of each leg's script-averaged chance. Builds whose legs
                # need different endings (e.g. a QB yardage leg that needs a shootout next to a run leg that needs a lead) sink.
                pen = 1.0
                for r in combo: pen *= r["padj"] / r["prob"] if r["prob"] else 1
                ind = pen * sum(w[k] * math.prod(r["ps"][k] for r in combo) for k in range(4))
                out.append((ind, d, combo))
        return out
    combos = enumerate_combos(1)
    if not combos: return "", None
    combos.sort(key=lambda x: -x[0]); short = combos[:14]
    priced = []
    for ind, d, combo in short:
        n = len(combo); C = [[1.0]*n for _ in range(n)]
        for i in range(n):
            for j in range(i+1, n): C[i][j] = C[j][i] = corr_between(combo[i]["l"], codes[id(combo[i])], combo[j]["l"], codes[id(combo[j])])
        pj = sum(w[k] * joint_prob([r["ps"][k] for r in combo], C, n=3000) for k in range(4) if w[k] > 0)
        priced.append((pj, pj * d - 1, d, combo, C))
    plus = [x for x in priced if x[1] >= 0]
    near = [x for x in priced if x[1] >= -0.05]
    pool = plus or near
    pj, ev, d, combo, C = max(pool, key=lambda x: (x[0], x[1])) if pool else max(priced, key=lambda x: x[1])
    by_k = [joint_prob([r["ps"][k] for r in combo], C, n=12000) if w[k] > 0 else 0.0 for k in range(4)]
    pj = sum(w[k] * by_k[k] for k in range(4)); ev = pj * d - 1
    fit_k = max(range(4), key=lambda k: w[k] * by_k[k])   # the ending this slip is built for (largest share of its hit chance)
    best = max(combo, key=lambda r: r["padj"] + (r["prob"] - r["l"]["book"]) - 0.05 * r["nbad"] - (0.1 if r["tb"] else 0))
    covered = sorted(set().union(*[r["scripts"] for r in combo]))
    lab = SC_LABEL(a, b)
    def leg_html(r):
        l = r["l"]; e = r["prob"] - l["book"]
        mk = "" if l.get("gl") else ("anytime TD" if l["market"] == "Anytime TD" else f'{E(l["market"].lower())} {int(l["line"])}+')
        why = f'{l["prob"]*100 if False else r["prob"]*100:.0f}% to hit averaged over the four endings (worst case {r["pmin"]*100:.0f}%); FanDuel price implies {l["book"]*100:.0f}%; shows up in the {", ".join(lab[k] for k in sorted(r["scripts"]))} strip{"s" if len(r["scripts"])>1 else ""}'
        flag = l["warn"]
        why += ". " + flag_tip(l)
        if l.get("gl"):
            by_end = ", ".join(f"{lab[k]} {r['ps'][k]*100:.0f}%" for k in range(4))
            why = f'{r["prob"]*100:.0f}% to hit mixing its chance under each ending ({by_end}); {"FanDuel" if l["src"] == "fd" else "the consensus line"} implies {l["book"]*100:.0f}%. ' + flag_tip(l)
        return (f'<span class="bpl{" best" if r is best else ""}{" glbpl" if l.get("gl") else ""}" title="{E(why)}">{"<em title=\"best leg\">★</em>" if r is best else ""}{E(l["player"])}{(" " + mk) if mk else ""}{" <span class=wf role=button tabindex=0 title=" + chr(34) + E(flag) + chr(34) + " data-f=" + chr(34) + E(flag) + chr(34) + " data-p=" + chr(34) + E(l["player"]) + chr(34) + ">⚠</span>" if flag else ""} <small>{odds_str(l["odds"])}</small>'
                f'<b>{r["prob"]*100:.0f}%</b>{ei(e)}{plus_btn(l)}</span>')
    legs_html = "".join(leg_html(r) for r in combo)
    note = "" if plus else ('<span class="bpwarn">no +EV build lands in the -110 to +500 window this run; this one is within 5 cents of fair</span>' if near else '<span class="bpwarn">no +EV build lands in the -110 to +500 window this run; this is the closest</span>')
    html_ = (f'<div class="bestslip"><span class="lt">Best parlay <small>{len(combo)} legs</small></span><span class="bpodds" title="FanDuel price for the {len(combo)}-leg slip">{am_from_dec(d)}</span>{legs_html}'
             f'<span class="bpnum">model <b>{pj*100:.0f}%</b> to hit · fair {fair_odds(pj)} · EV <b class="{"up" if ev>=0 else "dn"}">{"+" if ev>=0 else ""}${ev:.2f}</b> per $1 · does best if <b title="if the game ends {E(lab[fit_k])}, this slip hits {by_k[fit_k]*100:.0f}% of the time">{E(lab[fit_k])}</b> <span title="the model&#39;s chance of that ending">({w[fit_k]*100:.0f}% likely)</span></span>{note}{fd_button([r["l"] for r in combo], "best parlay")}</div>')
    rec = {"gid": f"{a}-{b}", "a": a, "b": b, "pj": pj, "ev": ev, "dec": d, "fit": lab[fit_k], "by_k": by_k, "legs": [(r["l"]["player"], r["l"]["market"], r["l"]["line"], r["l"]["odds"], r["prob"], r["prob"] - r["l"]["book"]) for r in combo], "best": best["l"]["player"]}
    return html_, rec
BEST_PARLAYS = []
ROLE_RISK = ("Target competition", "Backfield competition", "Rising", "Limited", "Snaps down", "Role Down", "Carries down", "Targets down",
             "Cold L3", "Fill-in", "Usage falling", "Boom/bust")   # keep in step with home.py

# ---------------- confidence + market script (owner 10/26 - see confidence.py) ----------------
import confidence as CONF
CF = CONF.Conf(IN, WEEK, GL_FD, GL_SCHED)
import runlean as RUNLEAN   # pregame run-lean read per team (runlean_v1.json; owner 10/26)
try: RL = RUNLEAN.RunLean(json.load(open(os.path.join(IN, "gamelog.json")))["values"], int(WEEK))
except Exception as _e: print("warn: run-lean skipped:", _e); RL = None
def lean_reads(a, b):
    sp, tot = CF.market(a, b)
    if RL is None or sp is None or tot is None: return {}
    out = {}
    for t, o, s_ in ((a, b, sp), (b, a, -sp)):
        x = RL.read(t, o, s_, tot)
        if x: out[t] = x
    return out
CONF_ROWS = []   # (gid, grade, score, flags) for the summary card
CONF_ARC = []    # rows for 'AUTO - Confidence Archive' (graded on the season page) - out/conf_rows.json, appended by the runbook
CONF_HDR = ["Week", "Frozen at (CT)", "Game", "A", "B", "Grade", "Score", "Flags", "Model A pts", "Model B pts", "FD spread (A)", "FD total",
            "Mkt A by 10+ %", "Mkt close-low %", "Mkt shootout %", "Mkt B by 10+ %", "Run-lean A", "Run-lean B"]
def either_way(a, b):
    """Legs whose chance stays 60%+ under every ending (min over the four scripts) - the ones that do not need us to call the game right."""
    rows = [r for r in BP_ROWS.get(f"{a}-{b}", {}).values() if not r["l"].get("warn") and not r["tb"] and r["pmin"] >= 0.60 and r["nbad"] == 0
            and r["prob"] - (r["l"]["book"] or 1) >= -0.03]
    rows.sort(key=lambda r: -r["pmin"]); seen = set(); out = []
    for r in rows:
        if r["l"]["player"] in seen: continue
        seen.add(r["l"]["player"]); out.append(r)
        if len(out) == 4: break
    return out
def lean_html(lr):
    items = []
    for tm, x in lr.items():
        if not x["flag"]: continue
        if x["flag"] == "RUN":
            items.append(f'<li class="lean run"><b>{E(tm)} run-lean</b> expected run rate {x["pred"]*100:.0f}% vs its usual {x["norm"]*100:.0f}% (backs ~{x["rb_car"]:.0f} carries). Leans: lead back\'s carries / rushing yards; fade his catches.</li>')
        else:
            items.append(f'<li class="lean pass"><b>{E(tm)} pass-lean</b> expected run rate {x["pred"]*100:.0f}% vs its usual {x["norm"]*100:.0f}%. Backs\' catches hold up better than their rushing here.</li>')
    if not items: return ""
    return ('<ul class="leans">' + "".join(items) + '</ul><p class="cfctx">Run-lean comes from each team\'s run rate, run game vs this defense, and the spread and total. In 2024-26 tests flagged teams\' lead backs went over their carries 55% of the time (49% overall) and over their catches 35% (40%) - a lean, not a lock.</p>')
def conf_block(a, b, s, cf, ew, lr=None):
    g = cf["grade"]; m = cf["mkt"]
    head = {"HIGH": "High confidence", "MEDIUM": "Medium confidence", "LOW": "Low confidence"}[g]
    lede = {"HIGH": "No major flags. The script and player numbers should hold up." if cf["flags"] else "No flags. The script and player numbers should hold up.",
            "MEDIUM": "A few flags - read them before betting this game.",
            "LOW": "Lots of flags: this game can go sideways. Favor the 'hit either way' legs and keep stakes small."}[g]
    fl = "".join(f'<li><b>{E(k)}</b> {E(t)}</li>' for p, k, t in sorted(cf["flags"], key=lambda x: -x[0]))
    ctx = f'<p class="cfctx">Context: {E("; ".join(cf["context"]))}</p>' if cf["context"] else ""
    mk = ""; fo = cf["form"]
    if fo["used"]:
        pr = fo["probs"]; kk = max(range(4), key=lambda i: pr[i]); lab = SC_LABEL(a, b)
        mk = (f'<div class="mread"><span class="lt">Our formula\'s read <small>season averages only: {a} {fo["pa"]:.1f}, {b} {fo["pb"]:.1f} (the score above is FanDuel\'s line)</small></span>'
              f'<div class="mscripts">' + "".join(f'<i class="s{k+1}{" on" if k == kk else ""}" style="--p:{pr[k]:.0f}%"><em>{E(lab[k])}</em><b>{pr[k]:.0f}%</b></i>' for k in range(4)) +
              f'</div><small class="mnote">Game scripts use FanDuel\'s spread and total once posted: from 2019-26 the line\'s endings beat this formula\'s (avg miss 9.5 vs 10.3 pts). Player projections are still ours.</small></div>')
    elif m:
        pr = m["probs"]; kk = max(range(4), key=lambda i: pr[i]); lab = SC_LABEL(a, b)
        mk = (f'<div class="mread"><span class="lt">Market\'s read <small>FanDuel {a} {m["spread_a"]:+g} · O/U {m["total"]:g} → {a} {m["pa"]:.1f}, {b} {m["pb"]:.1f}</small></span>'
              f'<div class="mscripts">' + "".join(f'<i class="s{k+1}{" on" if k == kk else ""}" style="--p:{pr[k]:.0f}%"><em>{E(lab[k])}</em><b>{pr[k]:.0f}%</b></i>' for k in range(4)) +
              f'</div><small class="mnote">Most likely per the market: <b>{E(lab[kk])}</b> ({pr[kk]:.0f}%). The best parlay below is weighted by these odds - in 2019-26 tests the market\'s endings beat our formula\'s.</small></div>')
    ewh = ""
    if ew:
        items = "".join(f'<span class="sp" title="{E(flag_tip(r["l"]))}">{E(r["l"]["player"])} {"anytime TD" if r["l"]["market"]=="Anytime TD" else E(r["l"]["market"].lower()) + (" " + format(r["l"]["line"], "g") + ("+" if r["l"].get("gl") is None else "") if r["l"]["line"] is not None else "")} <small>{odds_str(r["l"]["odds"])}</small><b>{r["pmin"]*100:.0f}%+</b>{plus_btn(r["l"]) if r["l"].get("gl") is None else ""}</span>' for r in ew)
        ewh = f'<div class="splays ew"><span class="lt">Hit either way <small>60%+ under all four endings</small></span>{items}{fd_button([r["l"] for r in ew], "either")}</div>'
    return (f'<details class="conf c-{g.lower()}"><summary><span class="cg">{head}</span><span class="cl">{E(lede)}</span>'
            + "".join(f'<span class="lp {x["flag"].lower()}">{E(tm)} {"run" if x["flag"] == "RUN" else "pass"}-lean</span>' for tm, x in (lr or {}).items() if x["flag"]) +
            f'<span class="cn">{len(cf["flags"])} flag{"s" if len(cf["flags"]) != 1 else ""}</span></summary>'
            f'{"<ul>" + fl + "</ul>" if fl else "<p class=cfctx>No flags.</p>"}{ctx}{lean_html(lr or {})}{mk}{ewh}</details>')

# ---------------- cards ----------------
cards, nav, summary_rows = [], [], {"mkt": [], "wx": [], "plays": []}
for a, b, pl_all in blocks:
    pl = [p for p in pl_all if p[3] != "K"]
    s = SCRIPTS.get(a) or SCRIPTS.get(b)
    if not s: continue
    if s[0] != a: a, b = b, a  # align with script table order
    maxppr = max((num(p[5]) or 0) for p in pl) or 1
    fav = a if s[2] > s[3] else b; margin = abs(s[2] - s[3]); gid = f"{a}-{b}"
    nav.append(f'<a href="#{gid}">{a}·{b}</a>')
    gi = game_for(a, b); info = ""; ct = 12
    if gi:
        hh, mm = gi["gametime"].split(":"); ct = (int(hh) - 1) % 24; ampm = "PM" if ct >= 12 else "AM"; ct12 = ct - 12 if ct > 12 else (12 if ct == 0 else ct)
        dt = datetime.date.fromisoformat(gi["gameday"]); kick = f"{dt.strftime('%a %-m/%-d')} {ct12}:{mm} {ampm} CT"
        roof = {"dome": "dome", "outdoors": "outdoors", "closed": "roof closed", "open": "roof open"}.get(gi["roof"] or "", "retractable roof")
        sp = num(gi["spread_line"]) or 0; tot = num(gi["total_line"])
        mkt_fav = gi["home_team"] if sp > 0 else gi["away_team"]; mkt = f"{mkt_fav} -{abs(sp):g}" if sp else "pick"
        diff = abs(abs(sp) - margin) if mkt_fav == fav else abs(sp) + margin
        agree = "agree" if diff <= 3 else "differ"
        if agree == "differ": summary_rows["mkt"].append((diff, f"{gi['away_team']} @ {gi['home_team']}", f"market {mkt}, model {fav} by {margin:.1f}"))
        info = (f'<div class="ginfo"><span class="gk">{kick}</span><i>·</i><span title="{roof} · {E(gi["surface"])}">{E(gi["stadium"])}</span><i>·</i>{wx_block(a, b, ct)}<i>·</i>'
                f'<span class="mkt {agree}" title="closing-line market from the schedule feed; model {fav} by {margin:.1f}, {s[4]:.1f} total">{mkt} · O/U {tot:g}</span>'
                f'</div><div class="vbtns"><button type="button" class="vbtn" data-view="script">Game Script</button><button type="button" class="vbtn" data-view="proj">Projections</button></div>')
    w = WX.get(frozenset([a, b]))
    if w and w["risk"] in ("HIGH", "MED"): summary_rows["wx"].append((w["risk"], f"{a}/{b}", f"wind {w['wind']:.0f} mph" + (f", gusts {w['gust']:.0f}" if w["gust"] else "") + (f", {w['ptype']}" if w["ptype"] not in ("none", "") else "")))
    _ko = kick_ms(a, b); _lr = lean_reads(a, b)
    cf = CF.assess(a, b, s[2] or 0, s[3] or 0)
    bp_html, bp_rec = best_parlay(a, b, pl, s, None if cf["form"]["used"] or not cf["mkt"] else cf["mkt"]["probs"])
    CONF_ROWS.append((gid, cf["grade"], cf["score"], [(k, t_) for _, k, t_ in cf["flags"]]))
    if _ko is None or _ko > datetime.datetime.now(ZoneInfo("UTC")).timestamp() * 1000:
        _m = cf["mkt"] or {}
        CONF_ARC.append([WEEK, datetime.datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M"), gid, a, b, cf["grade"], cf["score"],
                         " | ".join(f"{k}: {t_}" for _, k, t_ in cf["flags"])[:1500], round(s[2] or 0, 2), round(s[3] or 0, 2),
                         _m.get("spread_a", ""), _m.get("total", "")] + list(_m.get("probs", ["", "", "", ""]))
                        + [round(_lr[t_]["lean"], 4) if t_ in _lr else "" for t_ in (a, b)])
    conf_html = conf_block(a, b, s, cf, either_way(a, b), _lr)
    if bp_rec: BEST_PARLAYS.append(bp_rec)
    else: bp_html = '<div class="bestslip none"><span class="lt">Best parlay</span><span class="bpwarn">no build this run: FanDuel has too few clean, healthy legs priced in this game to land a -110 to +500 slip</span></div>'
    plays_html, most = script_plays(a, b, pl, s)
    kk = max(range(4), key=lambda i: (s[5:9][i] or 0))
    sc_blocks = ""
    for k in range(4):
        ph, _ = script_plays(a, b, pl, s, k); sh = slip_for(a, b, pl, s, k)
        if k != kk: ph = ph.replace('<div class="splays"', '<div class="splays" hidden', 1); sh = sh.replace('<div class="slip"', '<div class="slip" hidden', 1)
        sc_blocks += (ph or f'<div class="splays none" data-sc="{k}"{"" if k == kk else " hidden"}><span class="lt">If {E(SC_LABEL(a, b)[k])} <small>({s[5+k]:.0f}%)</small></span><small>no leg clears 55% under this script</small></div>') + sh
    _ko = kick_ms(a, b); _fin = final_text(a, b)
    cards.append(f'''<section class="card" id="{gid}"{f' data-ko="{_ko}"' if _ko else ""}{f' data-final="{E(_fin)}"' if _fin else ""}>
 <header class="hd">{PLAYS}
  <div class="tm a">{badge(a)}<b>{a}</b><span>{NAMES.get(a, a)}</span></div>
  <div class="score"><span class="pt">{s[2]:.1f}</span><span class="dash">–</span><span class="pt">{s[3]:.1f}</span>
    <small>total {s[4]:.1f} · {fav} by {margin:.1f}</small>{SWOOSH}</div>
  <div class="tm b">{badge(b)}<b>{b}</b><span>{NAMES.get(b, b)}</span></div>
 </header>
 {info}
 {conf_html}
 {bp_html}
 <div class="scripts" aria-label="game script odds · tap a script to see its plays" data-on="{kk}">
  <i class="s1{" on" if kk==0 else ""}" data-sc="0" role="button" tabindex="0" style="--p:{s[5]:.0f}%"><em>{a} by 10+</em><b>{s[5]:.0f}%</b></i>
  <i class="s2{" on" if kk==1 else ""}" data-sc="1" role="button" tabindex="0" style="--p:{s[6]:.0f}%"><em>close, low</em><b>{s[6]:.0f}%</b></i>
  <i class="s3{" on" if kk==2 else ""}" data-sc="2" role="button" tabindex="0" style="--p:{s[7]:.0f}%"><em>shootout</em><b>{s[7]:.0f}%</b></i>
  <i class="s4{" on" if kk==3 else ""}" data-sc="3" role="button" tabindex="0" style="--p:{s[8]:.0f}%"><em>{b} by 10+</em><b>{s[8]:.0f}%</b></i>
 </div>
 <p class="schint">Tap a slice of the bar to see the plays and slip for that game script.</p>
 <p class="legend"><b>{"How the game should end, from FanDuel's spread and total" if cf["form"]["used"] else ("How the model sees the game ending" + ((" · model total " + format(s[4], ".1f") + (" vs market " + format(tot, "g") if gi and tot else "")) if s[4] else ""))}:</b>
  <span><i class="d s1"></i>{s[5]:.0f}% {a} wins by 10+</span><span><i class="d s2"></i>{s[6]:.0f}% close game, under 51 total points</span>
  <span><i class="d s3"></i>{s[7]:.0f}% shootout (close, 51+ points)</span><span><i class="d s4"></i>{s[8]:.0f}% {b} wins by 10+</span></p>
 {sc_blocks}
 {ftd_strip(a, b)}
 {cov_strip(a, b)}
 {faceoff_block(a, b)}
 {mbs_block(a, b)}
 <div class="cols"><ul class="col">{team_col(pl, a, maxppr)}</ul><ul class="col">{team_col(pl, b, maxppr)}</ul></div>
 <footer class="ft"><span class="brand"><img src="data:image/png;base64,{LOGO_S}" alt=""><span>BetSweep</span></span><span>PPR projection · bar scaled to this game's top player · Week {WEEK}</span><button class="snap more" type="button" data-target="{gid}">Show all players</button><button class="snap" type="button" data-target="{gid}">Copy card as image</button><button class="snap story" type="button" data-target="{gid}">Story 9:16</button></footer>
</section>''')

json.dump({"header": CONF_HDR, "values": CONF_ARC}, open(os.path.join(HERE if "HERE" in globals() else os.path.dirname(os.path.abspath(__file__)), "out", "conf_rows.json"), "w"))
print(f"wrote out/conf_rows.json: {len(CONF_ARC)} games graded for confidence ({sum(1 for r in CONF_ARC if r[5] == 'LOW')} low, {sum(1 for r in CONF_ARC if r[5] == 'MEDIUM')} medium)")
# ---------------- summary card ----------------
# best clean legs: shown edge >= +2.5 pts (raw model +5 before the calib.py blend), >= 55% to hit, active, no risk flags (this-season form/usage/matchup/weather/line hit-rate), one per player
_seen = set(); best = []
for l in sorted(LEGS, key=lambda x: -((x["edge"] or 0))):
    if l["status"] != "ACTIVE" or l["p"] is None or l["edge"] is None or l["odds"] is None or "/" in l["player"]: continue
    if l["p"] < 0.55 or l["edge"] < 0.025 or l["warn"] or l["player"] in _seen or l["player"] in QUEST: continue
    if GAMEDAY.get(l["player"].lower(), {}).get("status", "").startswith("CONFIRMED"): continue
    _seen.add(l["player"]); best.append([l["player"], l["market"], f"{l['line']:g}" if l["line"] is not None else "", odds_str(l["odds"]), l["team"], l["opp"], f"{l['edge']*100:+.1f}", f"{l['p']*100:.0f}%", l["good"], plus_btn(l)])
    if len(best) == 6: break
best_html = "".join(f'<li title="{E(r[8]) if r[8] else "no risk flags"}"><span class="bl-p">{E(r[0])}{r[9]}</span><span class="bl-m">{E(r[1])} {E(r[2])}+ <small>{E(r[3])} · {E(r[7])}</small></span><span class="bl-n">{E(r[4])} <small>vs {E(r[5])}</small></span><b class="pos">{E(r[6])}</b></li>' for r in best) or '<li class="none">No clean legs clear the filter yet (FanDuel posts more lines closer to kickoff).</li>'
conf_html_sum = "".join([f'<li><span class="bl-p"><a href="#{E(g)}">{E(g.replace("-", " · "))}</a></span><span class="bl-m">{E(", ".join(k for k, _ in fl[:3]))}</span><b class="{"neg" if gr == "LOW" else "warnc"}">{gr}</b></li>'
    for g, gr, sc, fl in sorted(CONF_ROWS, key=lambda x: -x[2]) if gr != "HIGH"][:5]) or "<li class='none'>No game carries more than one flag this week.</li>"
mkt_html = "".join(f'<li><span class="bl-p">{E(g)}</span><span class="bl-m">{E(t)}</span><b>{d:.1f} pts</b></li>' for d, g, t in sorted(summary_rows["mkt"], reverse=True)[:4]) or "<li class='none'>Market and model agree within 3 points everywhere.</li>"
wx_html = "".join(f'<li><span class="bl-p">{E(g)}</span><span class="bl-m">{E(t)}</span><b class="{ "neg" if r=="HIGH" else "warnc"}">{r}</b></li>' for r, g, t in sorted(summary_rows["wx"])) or "<li class='none'>No weather flags this week.</li>"
# script plays across the slate: re-run per game and collect top edges
allplays = []
for a, b, pl_all in blocks:
    s = SCRIPTS.get(a) or SCRIPTS.get(b)
    if not s: continue
    if s[0] != a: a, b = b, a
    html_p, most = script_plays(a, b, [p for p in pl_all if p[3] != "K"], s)
    for m in re.finditer(r'<span class="sp( w)?" title="([^"]*)">(.*?) <small>([^<]*)</small><b>(\d+)%</b><i>([+-]\d+)</i>(?:<button[^>]*?data-k="([^"]*)"[^>]*>[^<]*</button>)?</span>', html_p):
        allplays.append((int(m.group(6)), m.group(3), m.group(4), m.group(5), most, bool(m.group(1)), m.group(7)))
allplays.sort(key=lambda x: -x[0])
plays_html = "".join(f'<li><span class="bl-p">{p}{" <span class=warn>!</span>" if w else ""}{(chr(32)[:0] + f'<button type="button" class="addmini addbs" data-k="{k}" title="Add to your betslip">+</button>') if k else ""}</span><span class="bl-m">if {E(most)} <small>{o}</small></span><span class="bl-n">{hit}%</span><b class="pos">{e:+d}</b></li>' for e, p, o, hit, most, w, k in allplays[:6]) or "<li class='none'>No script plays above 55% yet.</li>"
summary = f'''<section class="card summary" id="summary">
 <header class="hd">{PLAYS}<div class="tm a"><b>Slate</b><span>Week {WEEK} at a glance</span></div><div class="score"><span class="pt">{len(cards)}</span><small>games on the board</small>{SWOOSH}</div><div class="tm b"><img class="bsmark" src="data:image/png;base64,{LOGO_S}" alt="BS"><span>BetSweep model</span></div></header>
 <div class="sumgrid">
  <div><h3>Best clean legs <small>model edge, no risk flags this season</small></h3><ul class="bl">{best_html}</ul></div>
  <div><h3>Script plays <small>if the likely script happens</small></h3><ul class="bl">{plays_html}</ul></div>
  <div><h3>Trust least <small>most flags · tap a game</small></h3><ul class="bl">{conf_html_sum}</ul></div>
  <div><h3>Weather watch <small>kickoff-hour forecast</small></h3><ul class="bl">{wx_html}</ul></div>
 </div>
 <footer class="ft"><span class="brand"><img src="data:image/png;base64,{LOGO_S}" alt=""><span>BetSweep</span></span><span>Picks. Data. Edge. Sweep.</span><button class="snap" type="button" data-target="summary">Copy card as image</button><button class="snap story" type="button" data-target="summary">Story 9:16</button></footer>
</section>'''

stamp = datetime.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p")
ARCHIVE = ""
try:
    arc = [r for r in vals("archive.json")[1:] if len(r) >= 3 and r[2].startswith("http")]
    ARCHIVE = '<nav class="archive" aria-label="past weeks"><span>Tools</span><a href="https://claude.ai/artifact/FQVqm3BhG4BfMPd63tRQRa">Parlay builder</a><span>Receipts</span><a href="https://claude.ai/artifact/A7tt7rCuMgVvwSqBm9A7Pv">Season to date</a>' + " ".join(f'<a href="{E(r[2])}">Week {E(r[0])}</a>' for r in sorted(arc, key=lambda r: -(num(r[0]) or 0))) + '</nav>'
except Exception: pass
# ---- betslip dataset: every leg behind an Add-to-betslip button, with what the slip needs to price it (same fields as the builder) ----
SHORT = {"Passing Yards": "Pass yds", "Rushing Yards": "Rush yds", "Receiving Yards": "Rec yds", "Receptions": "Rec", "Longest Reception": "Long rec", "Anytime TD": "Anytime TD", "First TD": "First TD"}
GID_OF = {}; PLAYERS_OF = {}
for a_, b_, pl_ in blocks:
    for t_ in (a_, b_): GID_OF[t_] = f"{a_}-{b_}"; PLAYERS_OF[t_] = pl_
SLIP_LEGS = []; _seenk = set()
def fl_triples(l): return [[f.get("k", "info"), f.get("tag", ""), f.get("txt", "")] for f in (l.get("flags") or []) if f.get("txt")]
# every rung of a player|market ladder rides along once any rung of it is on an Add button, so the slip's ‹ › faders and target price work here as in the builder
USED_PM = {tuple(k.split("|")[:2]) for k in SLIP_USED}
for l in LEGS:
    k = leg_key(l)
    if (k not in SLIP_USED and k not in CHIP_USED and (l["player"], l["market"]) not in USED_PM) or k in _seenk or l["p"] is None or l["book"] is None or l["odds"] is None or l["status"] in ("OUT", "BYE"): continue
    _seenk.add(k); ids = fd_ids(l)
    SLIP_LEGS.append({"k": k, "pl": l["player"], "m": l["market"], "ms": SHORT.get(l["market"], l["market"]), "ln": l["line"] or 1, "o": int(l["odds"]), "p": round(l["p"], 4), "bk": round(l["book"], 4),
                      "e": round(l["p"] - l["book"], 4), "tm": l["team"], "opp": l["opp"], "g": GID_OF.get(l["team"], ""), "c": leg_code(l, PLAYERS_OF.get(l["team"], [])) or "",
                      "fd": {"m": ids[0], "s": ids[1]} if ids else None, "w": l.get("warn", ""), "fl": fl_triples(l) if k in SLIP_USED else None, "proj": l.get("proj")})   # flags ride on the button rung; faded rungs borrow them in the page (keeps the page ~0.5 MB smaller)
try:
    for f in json.load(open(os.path.join(OUT, "firsttd_all.json"))):
        k = f"{f['n']}|First TD|1"
        if k not in SLIP_USED or k in _seenk or f.get("fd") is None or f.get("imp") is None: continue
        _seenk.add(k)
        SLIP_LEGS.append({"k": k, "pl": f["n"], "m": "First TD", "ms": "First TD", "ln": 1, "o": int(f["fd"]), "p": round(f["pr"], 4), "bk": round(f["imp"], 4), "e": round(f["pr"] - f["imp"], 4),
                          "tm": f["t"], "opp": f["o"], "g": GID_OF.get(f["t"], ""), "c": f"{f['p']}_FTD", "fd": {"m": f["mid"], "s": f["sid"]} if f.get("mid") and f.get("sid") else None, "w": ""})
except Exception as e: print("warn: first TD slip legs skipped:", e)
for l in GL_LEGS:   # game-line legs on a best parlay (same key, price and FanDuel IDs as the parlay builder's game-line buttons)
    k = leg_key(l)
    if k not in SLIP_USED or k in _seenk: continue
    _seenk.add(k)
    SLIP_LEGS.append({"k": k, "pl": l["player"], "m": l["market"], "ms": {"Moneyline": "ML"}.get(l["market"], l["market"]), "ln": l["line"], "o": int(l["odds"]), "p": round(l["p"], 4), "bk": round(l["book"], 4),
                      "e": round(l["p"] - l["book"], 4), "tm": l["team"], "opp": l["opp"], "g": l["g"], "c": "", "gl": l["gl"], "src": l["src"],
                      "fd": {"m": l["fdid"][0], "s": l["fdid"][1]} if l["fdid"] else None, "w": l["warn"], "fl": fl_triples(l)})
KO_OF = {}
for a_, b_, _ in blocks:
    KO_OF[f"{a_}-{b_}"] = kick_ms(a_, b_)
for l_ in SLIP_LEGS: l_["ko"] = KO_OF.get(l_["g"])
# other books on the page slip ('AUTO - Book Odds': DraftKings + Hard Rock prices, deep links and selection ids; same join as build_builder.py)
BOOKODDS = {}
try:
    for r in vals("bookodds.json")[1:]:
        if len(r) < 9 or not r[1]: continue
        BOOKODDS.setdefault(r[1], {})[r[0]] = {"o": num(r[5]), "s": r[8]}
except Exception as e: print("note: no book odds this run:", e)
NBK = 0
for l_ in SLIP_LEGS:
    b_ = BOOKODDS.get(f"{normname(l_['pl'])}|{l_['m']}|{int(round(l_['ln'] or 1))}" if l_["m"] != "First TD" else f"{normname(l_['pl'])}|First TD|1")
    if b_:
        l_["bks"] = {("dk" if bk == "draftkings" else "hr" if bk == "hardrockbet" else bk): {"o": int(v["o"]), "s": v["s"]} for bk, v in b_.items() if v["o"] is not None}; NBK += 1
if BOOKODDS: print(f"book odds: {NBK} of {len(SLIP_LEGS)} slip legs priced at DraftKings/Hard Rock")
import hrswap as HRSWAP   # nearest Hard Rock line for prop legs Hard Rock does not post at our rung (offered as an explicit swap on the slip)
_LAD = {}
for l in LEGS:
    if l.get("raw_p") is not None and l["market"] in HRSWAP.MAX_GAP and l.get("line") is not None: _LAD.setdefault((HRSWAP.normname(l["player"]), l["market"]), []).append((l["line"], l["raw_p"]))
if BOOKODDS: print(f"hard rock swaps: {HRSWAP.attach(SLIP_LEGS, _LAD, BOOKODDS)} slip legs got a nearest Hard Rock line")
import glbooks as GLB   # DraftKings / Hard Rock game lines (gl| rows in AUTO - Book Odds): exact number -> bks, nearest number -> alt
try: print("game-line books: %d exact, %d nearest-number" % GLB.attach(SLIP_LEGS, vals("bookodds.json")[1:], GL_MT))
except Exception as e: print("note: no game-line book odds this run:", e)
GSORT = {}
for a_, b_, _ in blocks:
    g_ = game_for(a_, b_); GSORT[f"{a_}-{b_}"] = (g_["gameday"] + " " + g_["gametime"]) if g_ else "9999"
for l_ in SLIP_LEGS:   # trim: the page rebuilds the warning text from the bad flags; hra is the pre-alt field name
    if l_.get("fl") and l_.get("w"): l_["w"] = ""; l_["wf"] = 1
    l_.pop("hra", None)
SLIP_DATA = {"week": WEEK, "legs": SLIP_LEGS, "corr": CORR, "glcorr": GLCORR, "gsort": GSORT, "builder": "https://betsweep.co/build/"}
import live as LIVE
import books as BOOKS
json.dump(BEST_PARLAYS, open(os.path.join(OUT, "best_parlays.json"), "w"))   # for build_calls.py (model-calls archive)
page = (open(os.path.join(HERE, "template.html")).read().replace("/*SLIPDATA*/null", json.dumps(SLIP_DATA, separators=(",", ":"))).replace("/*LIVEJS*/", LIVE.LIVE_JS).replace("/*BOOKSJS*/", BOOKS.BOOKS_JS).replace("/*BOOKSCSS*/", BOOKS.BOOKS_CSS).replace("<!--BOOKSHTML-->", BOOKS.panel_html("bslipBooksPanel")).replace("/*LIVECSS*/", LIVE.LIVE_CSS)
        .replace("{{NAV}}", '<a href="https://claude.ai/artifact/FQVqm3BhG4BfMPd63tRQRa" class="tool">Parlay Builder →</a> <a href="#summary">Slate</a> ' + " ".join(nav)).replace("{{CARDS}}", summary + "\n" + "\n".join(cards))
        .replace("{{LOGO}}", LOGO).replace("{{BANNER}}", BANNER).replace("{{WEEK}}", str(WEEK)).replace("{{STAMP}}", stamp).replace("{{ARCHIVE}}", ARCHIVE).replace("{{DESC}}", f"Model projections, matchup colors and the best FanDuel leg per player, from the Fantasy Projection Model 2026. Page built {stamp} CT from the live sheet: projections, per-game defense ranks (season and last 3 weeks), FanDuel lines and the kickoff-hour forecast."))
out = os.path.join(OUT, "matchup-boards.html"); open(out, "w").write(page)
print(f"wrote {out}: {len(cards)} games, {len(page)//1024} KB, week {WEEK}")
