#!/usr/bin/env python3
"""BetSweep Parlay Builder — v2026-10-14.
Reads the same ./in dumps as build_boards.py (legboard, boards, scripts, corr, gameday, games.csv) and writes
out/builder.html: one self-contained page listing every FanDuel leg on the slate priced against the model, with a slip
that prices any combination (Gaussian copula with the model's same-game correlations, Monte Carlo in the browser).
Prints "wrote .../out/builder.html: L legs, G games, week W".
"""
import json, sys, html, re, csv, datetime, os
from zoneinfo import ZoneInfo
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
E = html.escape
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def num(x):
    try: return float(str(x).replace("%", "").replace("+", "").replace(",", ""))
    except: return None
def pct(x):
    v = num(x)
    if v is None: return None
    return v / 100 if ("%" in str(x) or abs(v) > 1.5) else v
exec(open(os.path.join(HERE, "brand.py")).read())

boards = vals("boards.json"); WEEK = int(float(boards[1][1]))
scripts_raw = vals("scripts.json"); legs_raw = vals("legboard.json")
try: CORR = {r[0]: num(r[1]) for r in vals("corr.json")[1:] if r and "|" in str(r[0])}
except Exception: CORR = {}
def normname(x):
    x = re.sub(r"\.", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
LINKS = {}
try:
    for r in vals("links.json")[1:]:
        if len(r) >= 7 and r[0] and (r[4] or (r[5] and r[6])):
            mm = re.search(r"[?&]marketId=([^&#]+)", str(r[4])); ss_ = re.search(r"[?&]selectionId=([^&#]+)", str(r[4]))
            LINKS[r[0]] = {"u": r[4], "m": mm.group(1) if mm else str(r[5]), "s": ss_.group(1) if ss_ else str(r[6])}
except Exception: pass
SNAPS = {}  # 'AUTO - Snap Trends': model name -> note when the snap-decline factor is < 1
try:
    for r in vals("snaps.json")[1:]:
        if len(r) >= 10 and r[0] and num(r[9]) is not None and num(r[9]) < 0.999:
            SNAPS[r[0]] = f"Snap share down: {num(r[5])*100:.0f}% of snaps over the last 2 games vs {num(r[4])*100:.0f}% for the season (last game {num(r[6])*100:.0f}%); projection trimmed {(1-num(r[9]))*100:.0f}%"
except Exception: pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import flags as FLAGS
    FE = FLAGS.Engine(IN, WEEK)
except Exception as e:
    print("warn: flags engine unavailable:", e); FE = None
PF = {}  # player -> [[kind, tag, text], ...] (sent once per player; legs carry only their line-specific flag)
def leg_flags(player, market, line, team, opp):
    """All flags for a leg from flags.py. The leg's 'w' (risk) text is the bad flags only, so the clean filter keeps its meaning."""
    if not FE: return []
    try:
        fl = FE.leg({"player": player, "market": market, "line": line, "team": team, "opp": opp})
        if player not in PF: PF[player] = [[f["k"], f["tag"], f["txt"]] for f in FE.player(player, team, None, opp)]
        return [[f["k"], f["tag"], f["txt"]] for f in fl]
    except Exception: return []
def line_flags(fl, player):
    """Only the flags not already in the player's list (the this-season hit rate for this exact line)."""
    base = {tuple(x) for x in PF.get(player, [])}
    return [x for x in fl if tuple(x) not in base]
GAMEDAY = {}
try:
    for r in vals("gameday.json")[1:]:
        if len(r) >= 4 and str(r[0]) == str(WEEK) and r[1]: GAMEDAY[r[1].strip().lower()] = r[3].strip().upper()
except Exception: pass

# players -> position, team (from the boards blocks); game order follows the scripts tab like the boards do
POS, TEAM_OF = {}, {}
for _f, _pos in (("proj_qb.json", "QB"), ("proj_rb.json", "RB"), ("proj_wr.json", "WR"), ("proj_te.json", "TE")):   # fallback for players not on a board block
    try:
        for _r in vals(_f)[1:]:
            if _r and _r[0]: POS.setdefault(_r[0], _pos)
    except Exception: pass
import fillin as FILLIN
FILLS = FILLIN.load(IN, WEEK); FILL_BY_STANDIN = FILLIN.by_standin(FILLS)
if FE: FE.FILLIN = {f["player"]: f["note"] for f in FILLS}
blocks = []; i = 0
while i < len(boards):
    r = boards[i]
    if r and str(r[0]).startswith("🏈") and " vs " in r[0]:
        m = re.match(r"🏈 (\w+) vs (\w+)", r[0]); j = i + 2; pl = []
        while j < len(boards) and boards[j] and boards[j][0] and "|" not in boards[j][0] and not str(boards[j][0]).startswith("🏈"):
            p = boards[j] + [""] * (17 - len(boards[j]))
            if p[0] in FILL_BY_STANDIN and FILL_BY_STANDIN[p[0]]["team"] == p[2]: p[0] = FILL_BY_STANDIN[p[0]]["player"]; p[7] = "FILL-IN STARTER"   # real starter takes the stand-in's row
            POS[p[0]] = p[3] or POS.get(p[0], ""); TEAM_OF[p[0]] = p[2]; pl.append(p); j += 1
        blocks.append((m.group(1), m.group(2), pl)); i = j
    else: i += 1
SCRIPTS = {}
for r in scripts_raw[1:]:
    if len(r) < 11 or not r[0]: continue
    SCRIPTS[r[0]] = (r[0], r[1], num(r[2]), num(r[3]), num(r[5]), num(r[6]), num(r[7]), num(r[8]), num(r[9]), r[10])
GID = {}; GAMES = []
for a, b, pl in blocks:
    s = SCRIPTS.get(a) or SCRIPTS.get(b)
    if not s: continue
    if s[0] != a: a, b = b, a
    gid = f"{a}-{b}"; GID[a] = GID[b] = gid
    GAMES.append({"gid": gid, "a": a, "b": b, "pa": s[2], "pb": s[3], "tot": s[4], "probs": [s[5], s[6], s[7], s[8]], "most": s[9],
                  "na": NAMES.get(a, a), "nb": NAMES.get(b, b), "ca": list(TEAMCOL.get(a, ("#444", "#999"))), "cb": list(TEAMCOL.get(b, ("#444", "#999")))})
kick = {}
try:
    with open(os.path.join(IN, "games.csv"), newline="") as f:
        for g in csv.DictReader(f):
            if g["season"] == "2026" and g["week"] == str(WEEK) and g["game_type"] == "REG":
                hh, mm = g["gametime"].split(":"); ct = (int(hh) - 1) % 24; ap = "PM" if ct >= 12 else "AM"; h12 = ct - 12 if ct > 12 else (12 if ct == 0 else ct)
                dt = datetime.date.fromisoformat(g["gameday"])
                ko = int(datetime.datetime.fromisoformat(g["gameday"] + "T" + g["gametime"]).replace(tzinfo=ZoneInfo("America/New_York")).timestamp() * 1000)
                fin = ""
                if g.get("home_score") not in ("", None, "NA") and g.get("away_score") not in ("", None, "NA"):
                    hs, as_ = int(float(g["home_score"])), int(float(g["away_score"])); fin = f"{g['home_team']} {hs} – {g['away_team']} {as_}" if hs >= as_ else f"{g['away_team']} {as_} – {g['home_team']} {hs}"
                kick[frozenset([g["away_team"], g["home_team"]])] = (g["gameday"] + "T" + g["gametime"], f"{dt.strftime('%a')} {h12}:{mm} {ap}", ko, fin)
except Exception: pass
for g in GAMES:
    k = kick.get(frozenset([g["a"], g["b"]])); g["kick"] = k[1] if k else ""; g["sort"] = k[0] if k else "9"; g["ko"] = k[2] if k else None; g["fin"] = k[3] if k else ""
GAMES.sort(key=lambda g: g["sort"])

# defense ranks (season + last 3) and the per-player game log, for the matchup pill and the "last games" panel
RANKS, RANKS3 = {}, {}
try:
    rr = vals("ranks.json"); DCOL = {c: i for i, c in enumerate(rr[0][1:])}; blk = RANKS
    for r in rr[1:]:
        if not r: continue
        if str(r[0]).startswith("LAST 3"): blk = RANKS3; continue
        if r[0] in ("Defense", ""): continue
        if len(r) > 1 and num(r[1]) is not None: blk[r[0]] = [int(float(x)) if num(x) is not None else None for x in r[1:16]]
except Exception: DCOL = {}
def rank_col(pos, m):
    if m == "Passing Yards": return "QB Pass Yds"
    if m == "Rushing Yards": return f"{pos} Rush Yds"
    if m in ("Receiving Yards", "Longest Reception"): return f"{pos} Rec Yds"
    if m == "Receptions": return f"{pos} Receptions"
    if m == "Anytime TD": return "QB Rush TD" if pos == "QB" else ("RB Rush TD" if pos == "RB" else f"{pos} Rec TD")
    return None
def dranks(pos, opp, m):
    c = rank_col(pos, m)
    if not c or c not in DCOL: return None
    a = RANKS.get(opp); b = RANKS3.get(opp)
    return [a[DCOL[c]] if a else None, b[DCOL[c]] if b else None]
GL = {}
try:
    gl = vals("gamelog.json"); GH = {c: i for i, c in enumerate(gl[0])}
    def gv(r, c):
        try: return float(r[GH[c]])
        except Exception: return None
    for r in gl[1:]:
        if len(r) < 17 or not r[1]: continue
        try: wk = int(float(r[0]))
        except Exception: continue
        if wk >= WEEK: continue
        GL.setdefault(r[1], []).append({"w": wk, "opp": r[GH["Opponent"]] if "Opponent" in GH else "", "pass": gv(r, "Pass Yds"), "rush": gv(r, "Rush Yds"),
                                         "rec": gv(r, "Receptions"), "recy": gv(r, "Rec Yds"), "long": gv(r, "Longest Rec") if "Longest Rec" in GH else None,
                                         "rr": (gv(r, "Rush Yds") or 0) + (gv(r, "Rec Yds") or 0), "td": (gv(r, "Rush TD") or 0) + (gv(r, "Rec TD") or 0)})
    for k in GL: GL[k] = sorted(GL[k], key=lambda g: -g["w"])[:6]
except Exception: pass
# defense: what each D allowed per game to each position, by stat (last 6 weeks), plus league per-game averages
DEF = {}; LG = {}
try:
    tmp = {}
    for r in gl[1:]:
        if len(r) < 17 or not r[1]: continue
        try: wk = int(float(r[0]))
        except Exception: continue
        if wk >= WEEK: continue
        pos = r[GH["Pos"]]; opp = r[GH["Opponent"]]; tm = r[GH["Team"]]
        if pos not in ("QB", "RB", "WR", "TE") or not opp: continue
        vals_ = {"pass": gv(r, "Pass Yds"), "rush": gv(r, "Rush Yds"), "rec": gv(r, "Receptions"), "recy": gv(r, "Rec Yds"),
                 "long": gv(r, "Longest Rec") if "Longest Rec" in GH else None, "td": (gv(r, "Rush TD") or 0) + (gv(r, "Rec TD") or 0)}
        for sk, v in vals_.items():
            if v is None: continue
            d = tmp.setdefault((opp, pos, sk, wk), {"w": wk, "vs": tm, "tot": 0.0, "top": "", "topv": None, "pl": []})
            d["tot"] += v
            if sk == "long": d["tot"] = max(d["tot"], v)   # longest reception allowed = max, not sum
            if d["topv"] is None or v > d["topv"]: d["topv"] = v; d["top"] = r[1]
            d["pl"].append([r[1].split(" ")[-1], round(v, 1)])
    for (opp, pos, sk, wk), d in tmp.items():
        DEF.setdefault(opp, {}).setdefault(pos, {}).setdefault(sk, []).append(d)
    for opp in DEF:
        for pos in DEF[opp]:
            for sk in DEF[opp][pos]:
                DEF[opp][pos][sk] = sorted(DEF[opp][pos][sk], key=lambda d: -d["w"])[:6]
                for d in DEF[opp][pos][sk]:
                    d["tot"] = round(d["tot"], 1); d["topv"] = round(d["topv"], 1) if d["topv"] is not None else None
                    d["pl"] = sorted(d["pl"], key=lambda x: -x[1])[:3]
    for (opp, pos, sk, wk), d in tmp.items():
        LG.setdefault(pos, {}).setdefault(sk, []).append(d["tot"])
    LG = {pos: {sk: round(sum(v) / len(v), 1) for sk, v in d.items() if v} for pos, d in LG.items()}
except Exception as e: DEF, LG = {}, {}
STAT_KEY = {"Passing Yards": "pass", "Rushing Yards": "rush", "Receiving Yards": "recy", "Receptions": "rec", "Longest Reception": "long", "Anytime TD": "td", "Rush + Rec Yards": "rr"}

CODE_OF = {"Passing Yards": "PASS", "Rushing Yards": "RUSH", "Receiving Yards": "RECYDS", "Receptions": "REC", "Longest Reception": "LONG", "Anytime TD": "TD", "Rush + Rec Yards": "RUSH"}   # RR shares the rush correlation code (dominant component for the RBs who get the market)
SHORT = {"Passing Yards": "Pass yds", "Rushing Yards": "Rush yds", "Receiving Yards": "Rec yds", "Receptions": "Rec", "Longest Reception": "Long rec", "Anytime TD": "Anytime TD", "Rush + Rec Yards": "Rush+rec yds"}
LEGS = []
for r in legs_raw[1:]:
    if len(r) < 17 or not r[0]: continue
    r = r + [""] * (18 - len(r))
    p, book, odds = pct(r[10]), pct(r[12]), num(r[3])
    if p is None or book is None or odds is None: continue
    if r[6] in ("OUT", "BYE"): continue
    team = r[4]; gid = GID.get(team)
    if not gid: continue
    pos = POS.get(r[0], "")
    LEGS.append({"i": len(LEGS), "pl": r[0], "pos": pos, "tm": team, "opp": r[5], "g": gid, "m": r[1], "ms": SHORT.get(r[1], r[1]), "ln": num(r[2]), "o": int(odds),
                 "p": round(p, 4), "bk": round(book, 4), "e": round(p - book, 4), "w": "; ".join(f[2] for f in leg_flags(r[0], r[1], num(r[2]), team, r[5]) if f[0] == "bad"), "fh": line_flags(leg_flags(r[0], r[1], num(r[2]), team, r[5]), r[0]), "proj": num(r[7]), "avg": num(r[8]), "n": num(r[9]),
                 "c": f"{pos}_{CODE_OF.get(r[1], '')}" if pos else "", "gd": GAMEDAY.get(r[0].lower(), ""),
                 "fd": LINKS.get(f"{normname(r[0])}|{r[1]}|{int(num(r[2]) or 1)}"), "dr": dranks(pos, r[5], r[1]), "sk": STAT_KEY.get(r[1], "")})
# Anytime TD for every player FanDuel prices, not only the ones in the Leg Board. The odds pull that feeds the Leg Board keeps prices inside a
# window (about -350 to +260), so most anytime TD scorers (+260 and longer) never reach it; the FanDuel Links tab carries every one with its
# price and betslip IDs. Same model math as the Leg Board: P(anytime TD) = 1 - exp(-(projected rush TD + rec TD)) from the Matchup Boards tab.
import math as _mth
_have = {(l["pl"], l["m"]) for l in LEGS}
OUT_NOW = set()
try:
    for r in vals("avail.json")[1:]:
        if len(r) > 4 and str(r[0]) == str(WEEK) and r[4].strip().upper() in ("OUT", "IR", "DOUBTFUL"): OUT_NOW.add(normname(r[1]))
except Exception: pass
MODEL_BY_NORM = {}
for a_, b_, pl_ in blocks:
    for q in pl_:
        lam = (num(q[13]) or 0) + (num(q[14]) or 0)
        if q[0] and q[3] in ("QB", "RB", "WR", "TE"): MODEL_BY_NORM[normname(q[0])] = (q[0], q[2], q[4], q[3], lam)
NATD_X = 0
try:
    for r in vals("links.json")[1:]:
        if len(r) < 8 or "|Anytime TD|" not in str(r[0]): continue
        nm = normname(r[1]); mdl = MODEL_BY_NORM.get(nm); odds = num(r[7])
        if not mdl or odds is None or nm in OUT_NOW: continue
        name, team, opp, pos, lam = mdl
        if (name, "Anytime TD") in _have or lam <= 0: continue
        gid = GID.get(team)
        if not gid: continue
        pm = 1 - _mth.exp(-lam); bk = (100 / (odds + 100)) if odds > 0 else (-odds / (-odds + 100))
        fl = leg_flags(name, "Anytime TD", 1, team, opp)
        fl = fl + [["info", "Price", f"FanDuel price from the betslip-link pull ({r[9] if len(r) > 9 else 'earlier'} CT); this price sits outside the odds window the Leg Board uses, so check it on FanDuel."]]
        LEGS.append({"i": len(LEGS), "pl": name, "pos": pos, "tm": team, "opp": opp, "g": gid, "m": "Anytime TD", "ms": "Anytime TD", "ln": 1, "o": int(odds),
                     "p": round(pm, 4), "bk": round(bk, 4), "e": round(pm - bk, 4), "w": "; ".join(f[2] for f in fl if f[0] == "bad"), "fh": line_flags(fl, name), "proj": round(lam, 2), "avg": None, "n": None,
                     "c": f"{pos}_TD", "gd": GAMEDAY.get(name.lower(), ""), "fd": LINKS.get(r[0]), "dr": dranks(pos, opp, "Anytime TD"), "sk": "td"})
        _have.add((name, "Anytime TD")); NATD_X += 1
except Exception as e: print("warn: extra anytime TD legs skipped:", e)
print(f"anytime TD: {sum(1 for l in LEGS if l['m'] == 'Anytime TD')} legs ({NATD_X} added from the FanDuel Links tab beyond the Leg Board)")
# 2+ / 3+ TD scorer (owner 10/28): FanDuelOdds.gs v2026-10-28 writes FanDuel's "Over 1.5 / 2.5 touchdowns" prices to the Links tab as
# '2+ TD' / '3+ TD'. Same Poisson lambda as anytime: P(>=2) = 1 - e^-l(1 + l), P(>=3) = 1 - e^-l(1 + l + l^2/2).
NTD2 = 0
try:
    for r in vals("links.json")[1:]:
        if len(r) < 8 or not ("|2+ TD|" in str(r[0]) or "|3+ TD|" in str(r[0])): continue
        mk = "2+ TD" if "|2+ TD|" in str(r[0]) else "3+ TD"
        nm = normname(r[1]); mdl = MODEL_BY_NORM.get(nm); odds = num(r[7])
        if not mdl or odds is None or nm in OUT_NOW: continue
        name, team, opp, pos, lam = mdl
        if (name, mk) in _have or lam <= 0: continue
        gid = GID.get(team)
        if not gid: continue
        pm = 1 - _mth.exp(-lam) * (1 + lam) if mk == "2+ TD" else 1 - _mth.exp(-lam) * (1 + lam + lam * lam / 2)
        bk = (100 / (odds + 100)) if odds > 0 else (-odds / (-odds + 100))
        fl = leg_flags(name, "Anytime TD", 1, team, opp) + [["info", "Price", f"FanDuel {mk} price from the betslip-link pull ({r[9] if len(r) > 9 else 'earlier'} CT). Multi-TD games are rarer than a Poisson count says for most players - treat the model number as a ceiling."]]
        LEGS.append({"i": len(LEGS), "pl": name, "pos": pos, "tm": team, "opp": opp, "g": gid, "m": mk, "ms": mk, "ln": 1, "o": int(odds),
                     "p": round(pm, 4), "bk": round(bk, 4), "e": round(pm - bk, 4), "w": "; ".join(f[2] for f in fl if f[0] == "bad"), "fh": line_flags(fl, name), "proj": round(lam, 2), "avg": None, "n": None,
                     "c": f"{pos}_TD", "gd": GAMEDAY.get(name.lower(), ""), "fd": LINKS.get(r[0]), "dr": dranks(pos, opp, "Anytime TD"), "sk": "td"})
        _have.add((name, mk)); NTD2 += 1
except Exception as e: print("warn: 2+/3+ TD legs skipped:", e)
print(f"2+/3+ TD: {NTD2} legs from the FanDuel Links tab")
# Replacement starters with no game log (fillin.py): price their FanDuel lines from the sheet's fill-in projection; every leg carries a risk flag
NFILL = 0
for f in FILLS:
    gid = GID.get(f["team"]); opp = next((g["b"] if g["a"] == f["team"] else g["a"] for g in GAMES if f["team"] in (g["a"], g["b"])), "")
    if not gid: continue
    for r in vals("links.json")[1:]:
        if len(r) < 8 or normname(r[1]) != normname(f["player"]) or r[2] not in ("Passing Yards", "Rushing Yards", "Anytime TD"): continue
        ln = num(r[3]) or 1; odds = num(r[7]); pm = FILLIN.prob(f, r[2], ln)
        if odds is None or pm is None or (f["player"], r[2], ln) in {(l["pl"], l["m"], l["ln"]) for l in LEGS}: continue
        bk = (100 / (odds + 100)) if odds > 0 else (-odds / (-odds + 100))
        fl = [["bad", "Fill-in starter", f["note"]], ["info", "Price", "FanDuel price from the betslip-link pull."]]
        LEGS.append({"i": len(LEGS), "pl": f["player"], "pos": f["pos"], "tm": f["team"], "opp": opp, "g": gid, "m": r[2], "ms": SHORT.get(r[2], r[2]), "ln": ln, "o": int(odds),
                     "p": round(pm, 4), "bk": round(bk, 4), "e": round(pm - bk, 4), "w": f["note"], "fh": fl, "proj": round(f["proj"]["pass" if r[2] == "Passing Yards" else "rush" if r[2] == "Rushing Yards" else "rtd"], 2), "avg": None, "n": None,
                     "c": f"{f['pos']}_{CODE_OF.get(r[2], '')}", "gd": GAMEDAY.get(f["player"].lower(), ""), "fd": LINKS.get(r[0]), "dr": dranks(f["pos"], opp, r[2]), "sk": STAT_KEY.get(r[2], "")})
        NFILL += 1
    print(f"fill-in starter: {f['player']} ({f['team']}, for {f['for']}) priced on {f['standin']}'s fill-in projection - {NFILL} legs, all risk-flagged")
# Returning starters with no 2026 game log (returning.py): last year's share x this team's current volume, flagged, short-sample.
NRET = 0
try:
    import returning as RET
    PRIOR = RET.load_prior(HERE); TVOL = RET.team_volume(IN, WEEK); CV = RET.ladder_cv(LEGS)
    have_pl = {normname(l["pl"]) for l in LEGS}
    clr = {}   # cleared/questionable availability rows this week: name -> team (the only team source for a player who changed teams)
    for r in vals("avail.json")[1:]:
        if len(r) > 4 and str(r[0]) == str(WEEK) and r[1] and r[4].strip().upper() in ("CLEARED", "QUESTIONABLE", "ACTIVE"): clr[normname(r[1])] = r[2].strip()
    nick = {g["na"]: g["a"] for g in GAMES}; nick.update({g["nb"]: g["b"] for g in GAMES})
    by_name = {}
    for r in vals("links.json")[1:]:
        if len(r) < 9 or r[2] not in ("Receiving Yards", "Receptions", "Rushing Yards", "Anytime TD", "Rush + Rec Yards"): continue
        by_name.setdefault(r[1], []).append(r)
    for name, rs in by_name.items():
        nn = normname(name)
        if nn in have_pl or nn in OUT_NOW or name in GL or any(normname(k) == nn for k in GL): continue   # has a 2026 log: the model covers him
        pri = PRIOR["players"].get(name) or next((v for k, v in PRIOR["players"].items() if normname(k) == nn), None)
        if not pri: continue
        game_teams = [nick[n] for n in nick if n and n in str(rs[0][8])]
        team = clr.get(nn) or next((t for t in pri["teams"] if t in game_teams), None)
        if not team or team not in game_teams: continue
        pos = pri["pos"]; gid = GID.get(team); opp = next((g["b"] if g["a"] == team else g["a"] for g in GAMES if team in (g["a"], g["b"])), "")
        if not gid: continue
        pr = RET.project(name, team, pos, PRIOR, TVOL)
        if not pr: continue
        for r in rs:
            ln = num(r[3]) or 1; odds = num(r[7]); mk = r[2]
            if odds is None: continue
            pm = RET.prob(pr, mk, ln, CV)
            if pm is None: continue
            bk = (100 / (odds + 100)) if odds > 0 else (-odds / (-odds + 100))
            fl = leg_flags(name, mk, ln, team, opp)
            fl = [f for f in fl if not str(f[1]).endswith("game sample")] + [["watch", "Returning", pr["note"]], ["info", "Price", "FanDuel price from the betslip-link pull."]]
            proj = {"Receiving Yards": pr["recy"], "Rushing Yards": pr["rushy"], "Receptions": pr["rec"], "Anytime TD": pr["lam_td"], "Rush + Rec Yards": pr["recy"] + pr["rushy"]}[mk]
            LEGS.append({"i": len(LEGS), "pl": name, "pos": pos, "tm": team, "opp": opp, "g": gid, "m": mk, "ms": SHORT.get(mk, mk), "ln": ln, "o": int(odds),
                         "p": round(pm, 4), "bk": round(bk, 4), "e": round(pm - bk, 4), "w": "; ".join(f[2] for f in fl if f[0] == "bad"), "fh": line_flags(fl, name), "proj": round(proj, 2), "avg": None, "n": 0,
                         "c": f"{pos}_{CODE_OF.get(mk, '')}", "gd": GAMEDAY.get(name.lower(), ""), "fd": LINKS.get(r[0]), "dr": dranks(pos, opp, mk if mk != "Rush + Rec Yards" else "Rushing Yards"), "sk": STAT_KEY.get(mk, ""), "ret": True})
            NRET += 1
        have_pl.add(nn)
        print(f"returning starter: {name} ({team} {pos}) priced from 2025 share x {team} volume - tgt {pr['tgt']:.1f}, rec yds {pr['recy']:.0f}, rush yds {pr['rushy']:.0f}, TD lambda {pr['lam_td']:.2f}")
    if NRET: print(f"returning starters: {NRET} legs")
except Exception as e: print("warn: returning-starter legs skipped:", e)
# Rush + Rec Yards (owner request): FanDuel prices it, the Leg Board does not. Priced here as the sum of the player's rushing and receiving
# distributions: each component's mean is the model projection and its spread is backed out of the model's own alt-ladder probabilities for
# that player (probit fit of the rungs; fallback spread = 0.5x rush proj / 0.6x rec proj when a ladder is missing); components treated as
# independent (RB rush and rec yards are near-uncorrelated within a game). Legs come from 'AUTO - FanDuel Links' rows with market
# "Rush + Rec Yards" (FanDuelOdds.gs must pull player_rush_reception_yds + its alternate ladder); until then this block adds nothing.
NRR = 0
try:
    from statistics import median as _median, NormalDist as _ND
    _Z = _ND()
    def _sigma(pl, mkt, proj):
        zs = []
        for l in LEGS:
            if l["pl"] != pl or l["m"] != mkt or not (0.08 < l["p"] < 0.92) or l.get("alt"): continue
            z = _Z.inv_cdf(1 - l["p"])
            if abs(z) > 0.15: zs.append((float(l["ln"]) - proj) / z)
        zs = [z for z in zs if z > 0]
        return _median(zs) if len(zs) >= 2 else None
    _by_pl = {}
    for l in LEGS:
        if l["m"] in ("Rushing Yards", "Receiving Yards") and l.get("proj") is not None: _by_pl.setdefault(l["pl"], {})[l["m"]] = l
    for r in vals("links.json")[1:]:
        if len(r) < 8 or r[2] != "Rush + Rec Yards": continue
        name = r[1]; comp = _by_pl.get(name) or next((v for k, v in _by_pl.items() if normname(k) == normname(name)), None)
        if not comp or "Rushing Yards" not in comp or "Receiving Yards" not in comp: continue   # need both model projections
        ru, rc = comp["Rushing Yards"], comp["Receiving Yards"]
        if normname(name) in OUT_NOW: continue
        ln = num(r[3]); odds = num(r[7])
        if ln is None or odds is None: continue
        mu_r, mu_c = float(ru["proj"]), float(rc["proj"]); mu = mu_r + mu_c
        if mu <= 0: continue
        s_r = _sigma(ru["pl"], "Rushing Yards", mu_r) or 0.5 * max(mu_r, 5); s_c = _sigma(rc["pl"], "Receiving Yards", mu_c) or 0.6 * max(mu_c, 5)
        sd = (s_r ** 2 + s_c ** 2) ** 0.5
        pm = 1 - _Z.cdf((ln - 0.5 - mu) / sd)   # X+ means at least ln; continuity correction
        pm = min(0.97, max(0.03, pm))
        bk = (100 / (odds + 100)) if odds > 0 else (-odds / (-odds + 100))
        fl = leg_flags(ru["pl"], "Rush + Rec Yards", ln, ru["tm"], ru["opp"])
        fl = fl + [["info", "Combined", f"Priced as rushing ({mu_r:.0f}) + receiving ({mu_c:.0f}) projections; spread from the model's own alt ladders (rush ±{s_r:.0f}, rec ±{s_c:.0f}). Both-sides volume: receiving is {mu_c / mu * 100:.0f}% of the total."]]
        LEGS.append({"i": len(LEGS), "pl": ru["pl"], "pos": ru["pos"], "tm": ru["tm"], "opp": ru["opp"], "g": ru["g"], "m": "Rush + Rec Yards", "ms": SHORT["Rush + Rec Yards"], "ln": ln, "o": int(odds),
                     "p": round(pm, 4), "bk": round(bk, 4), "e": round(pm - bk, 4), "w": "; ".join(f[2] for f in fl if f[0] == "bad"), "fh": line_flags(fl, ru["pl"]), "proj": round(mu, 1),
                     "avg": round((ru.get("avg") or 0) + (rc.get("avg") or 0), 1) if ru.get("avg") is not None and rc.get("avg") is not None else None, "n": ru.get("n"),
                     "c": f"{ru['pos']}_RUSH", "gd": ru.get("gd", ""), "fd": LINKS.get(r[0]), "dr": dranks(ru["pos"], ru["opp"], "Rushing Yards"), "sk": "rr", "rr": {"rush": round(mu_r, 1), "rec": round(mu_c, 1), "rec_share": round(mu_c / mu, 2)}})
        NRR += 1
    if NRR: print(f"rush + rec yards: {NRR} legs priced from combined rush/rec projections")
except Exception as e: print("warn: rush + rec legs skipped:", e)
# First touchdown scorer legs from the first-TD model (out/firsttd_all.json, written by build_firsttd.py - run it first).
# Only players with a FanDuel first-TD price become legs (the builder prices every leg against FanDuel); two First TD legs in one game
# cannot both hit, and a player's First TD leg implies his Anytime TD - the slip math in the page handles both.
NFTD = 0
try:
    for f in json.load(open(os.path.join(OUT, "firsttd_all.json"))):
        if f.get("fd") is None or f.get("imp") is None: continue
        gid = GID.get(f["t"])
        if not gid: continue
        fdl = LINKS.get(f"{normname(f['n'])}|First TD|1") or ({"u": f.get("link") or "", "m": f["mid"], "s": f["sid"]} if f.get("mid") and f.get("sid") else None)
        LEGS.append({"i": len(LEGS), "pl": f["n"], "pos": f["p"], "tm": f["t"], "opp": f["o"], "g": gid, "m": "First TD", "ms": "First TD", "ln": 1, "o": int(f["fd"]),
                     "p": round(f["pr"], 4), "bk": round(f["imp"], 4), "e": round(f["pr"] - f["imp"], 4), "w": "; ".join(x[2] for x in leg_flags(f["n"], "First TD", 1, f["t"], f["o"]) if x[0] == "bad"), "fh": line_flags(leg_flags(f["n"], "First TD", 1, f["t"], f["o"]), f["n"]), "proj": None, "avg": None, "n": None,
                     "c": f"{f['p']}_FTD", "gd": GAMEDAY.get(f["n"].lower(), ""), "fd": fdl, "dr": dranks(f["p"], f["o"], "Anytime TD"), "sk": "td"})
        NFTD += 1
except Exception as e: print("warn: first TD legs skipped:", e)
stamp = datetime.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p")
NLINK = sum(1 for l in LEGS if l["fd"])
# ---- other books ('AUTO - Book Odds' via the sheet's FanDuelOdds.gs: DraftKings + Hard Rock rungs with prices, deep links and ids) ----
BOOKODDS = {}
try:
    for r in vals("bookodds.json")[1:]:
        if len(r) < 9 or not r[1]: continue
        BOOKODDS.setdefault(r[1], {})[r[0]] = {"o": num(r[5]), "u": r[6], "s": r[8], "e": r[9] if len(r) > 9 else ""}
except Exception as e: print("note: no book odds this run:", e)
NBK = 0
for l in LEGS:
    k = f"{normname(l['pl'])}|{l['m']}|{int(round(l['ln'] or 1))}" if l["m"] != "First TD" else f"{normname(l['pl'])}|First TD|1"
    b = BOOKODDS.get(k)
    if b:
        l["bks"] = {("dk" if bk == "draftkings" else "hr" if bk == "hardrockbet" else bk): {"o": int(v["o"]) if v["o"] is not None else None, "u": v["u"], "s": v["s"]} for bk, v in b.items() if v["o"] is not None}; NBK += 1
if BOOKODDS: print(f"book odds: {len(BOOKODDS)} rungs in the tab, {NBK} legs priced at DraftKings/Hard Rock")
# ---- calibration: the shown Model % for every player-prop leg is the raw model blended toward FanDuel's price (calib.py; Weeks 5-6 Brier) ----
import calib as CALIB
for l in LEGS:
    if l.get("p") is None or l.get("bk") is None: continue
    l["raw_p"] = l["p"]; l["p"] = round(CALIB.shrink(l["p"], l["bk"]), 4); l["e"] = round(l["p"] - l["bk"], 4)
# ---- FanDuel UNDERS on the main lines (owner 10/27) ------------------------------------------------------------------------------------
# 'AUTO - FanDuel Unders' (FanDuelOdds.gs v2026-10-27) carries each main line's Under price + betslip ids. A main line X.5 is the same event as
# the alt rung (X+1)+ on the Leg Board, so the under's model chance = 1 - that rung's model chance (raw = 1 - raw over; shown = the same
# 50/50 blend with the under's own price). Weeks 6-7 (all frozen rungs priced -135..+115): where the model sat 8+ pts below FanDuel's over
# price, the under won 57.1% / 60.8% (n=184 / 209) - the model's strongest signal (scratchpad tier/). Unders get "u": 1; the slip flips
# their correlations; markets are named "Under <market>" so they never collide with the over rung's slip key.
# The sheet shows 'Market ID' as a number and drops the last digit (42.619720881 -> 42.61972088); the Link column keeps the full id.
def _ufd(r):
    import re as _re
    link = str(r[10]) if len(r) > 10 else ""
    mm = _re.search(r"marketId=([\d.]+)", link); ms = _re.search(r"selectionId=(\d+)", link)
    m = mm.group(1) if mm else (str(r[8]) if len(r) > 8 and r[8] else ""); s = ms.group(1) if ms else (str(r[9]) if len(r) > 9 and r[9] else "")
    return {"u": link, "m": m, "s": s} if m and s else None
NUND = 0
try:
    _rung = {}
    for l in LEGS:
        if l.get("raw_p") is not None and l["m"] in ("Passing Yards", "Rushing Yards", "Receiving Yards", "Receptions") and not l.get("gl"):
            _rung[(normname(l["pl"]), l["m"], int(round(l["ln"])))] = l
    for r in vals("unders.json")[1:]:
        if len(r) < 10: continue
        mk, pt, uo = r[2], num(r[3]), num(r[4])
        if mk not in ("Passing Yards", "Rushing Yards", "Receiving Yards", "Receptions") or pt is None or uo is None: continue
        base = _rung.get((normname(r[1]), mk, int(_mth.floor(pt)) + 1))
        if not base or normname(base["pl"]) in OUT_NOW or base.get("status") == "OUT": continue
        bku = (100 / (uo + 100)) if uo > 0 else (-uo / (-uo + 100))
        ov = num(r[5]); bko = ((100 / (ov + 100)) if ov > 0 else (-ov / (-ov + 100))) if ov is not None else None
        raw_u = round(1 - base["raw_p"], 4)
        LEGS.append({"i": len(LEGS), "pl": base["pl"], "pos": base["pos"], "tm": base["tm"], "opp": base["opp"], "g": base["g"], "m": "Under " + mk, "ms": SHORT.get(mk, mk),
                     "ln": pt, "o": int(uo), "raw_p": raw_u, "p": round(CALIB.shrink(raw_u, bku), 4), "bk": round(bku, 4), "e": round(CALIB.shrink(raw_u, bku) - bku, 4), "u": 1,
                     "bko": round(bko, 4) if bko is not None else None, "w": "",
                     "fh": [["info", "Under", f"FanDuel main line {pt:g}: under {('+' if uo > 0 else '')}{int(uo)}. Model projects {base.get('proj')} - {(1 - base['raw_p']) * 100:.0f}% that he stays under {pt:g}."]],
                     "proj": base.get("proj"), "avg": base.get("avg"), "n": base.get("n"), "c": base.get("c", ""), "gd": base.get("gd", ""),
                     "fd": _ufd(r), "dr": base.get("dr"), "sk": base.get("sk", "")})
        NUND += 1
    print(f"unders: {NUND} FanDuel main-line unders priced from the model ladder")
except FileNotFoundError: print("unders: no in/unders.json (FanDuelOdds.gs v2026-10-27 not installed yet)")
except Exception as e: print("warn: unders skipped:", e)
# ---- Model's Best tier (owner 10/27: "primarily FanDuel lines around -110"; tested on Weeks 6-7 graded legs, scratchpad tier/) ----
#  even: priced -135..+115 and the model is 8+ pts off FanDuel's price (raw model vs the over's implied %): below -> the UNDER, above -> the over
#        (unders 59.0% n=393, overs 54.8% n=104 over the two weeks)
#  td:   Anytime TD the model likes (raw >= FanDuel implied) at +200 or shorter: 55.6% hit, +34% (n=18, Weeks 6-7 - small sample).
#        Longer prices were dropped 10/27: the full Week 6 pool at any price went 9-79, and bigger model-vs-book gaps did worse.
#  safe: calibrated (shown) model % >= 65% - "top-end pulled down": raw 80%+ only hit 59%, the calibrated 65%+ hit 64-68% -,
#        raw >= price, no "Cleared this line in only" warning, best-edge rung per player+market: 64.9% hit, +3.3% (n=154)
NT = {"even": 0, "td": 0, "safe": 0}
_safe_best = {}
for l in LEGS:
    if l.get("gl") or l.get("raw_p") is None or l.get("bk") is None or l.get("status") in ("OUT", "BYE"): continue
    o = l.get("o")
    if l.get("u"):
        bo = l.get("bko") if l.get("bko") is not None else 1 - l["bk"]
        if o is not None and -135 <= o <= 115 and bo - (1 - l["raw_p"]) >= 0.08: l["tier"] = "even"
    elif l["m"] == "Anytime TD":
        if l["raw_p"] >= l["bk"] and "/" not in l["pl"] and o is not None and o <= 200: l["tier"] = "td"
    elif l["m"] in ("Passing Yards", "Rushing Yards", "Receiving Yards", "Receptions", "Longest Reception"):
        if o is not None and -135 <= o <= 115 and l["raw_p"] - l["bk"] >= 0.08: l["tier"] = "even"
        elif (l.get("p") or 0) >= 0.65 and l["raw_p"] >= l["bk"] and "Cleared this line in only" not in (l.get("w") or ""):
            k = (l["pl"], l["m"])
            if k not in _safe_best or l["raw_p"] - l["bk"] > _safe_best[k]["raw_p"] - _safe_best[k]["bk"]: _safe_best[k] = l
for l in _safe_best.values():
    if not l.get("tier"): l["tier"] = "safe"
for l in LEGS:
    if l.get("tier"): NT[l["tier"]] += 1
print(f"model's best: {NT['even']} even-odds (overs + unders), {NT['td']} TDs, {NT['safe']} safer legs")
# frozen copy of the tier for its own scorecard (appended to 'V2 - Model Best Picks' by the runbook, graded by build_season.py)
try:
    _ko = {g["gid"]: g.get("ko") for g in GAMES}; _now = datetime.datetime.now(ZoneInfo("UTC")).timestamp() * 1000
    _stamp = datetime.datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M")
    _rows = [[WEEK, _stamp, l["g"], l["pl"], l["tm"], l["m"], l["ln"], l["o"], round(l["raw_p"], 4), round(l["bk"], 4), l["tier"],
              datetime.datetime.fromtimestamp(_ko[l["g"]] / 1000, ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M") if _ko.get(l["g"]) else ""]
             for l in LEGS if l.get("tier") and _ko.get(l["g"]) and _ko[l["g"]] > _now]
    json.dump({"header": ["Week", "Frozen at (CT)", "Game", "Player", "Team", "Market", "Line", "Odds", "Raw model %", "Book implied %", "Tier", "Kickoff (CT)"], "values": _rows},
              open(os.path.join(OUT, "best_rows.json"), "w"))
    print(f"wrote out/best_rows.json: {len(_rows)} Model's Best legs not yet kicked off")
except Exception as e: print("warn: best_rows skipped:", e)
# ---- nearest DraftKings / Hard Rock line for legs those books do not post at our rung (hrswap.py): the send links use it automatically, the slip note says so ----
import hrswap as HRSWAP
_LAD = {}
for l in LEGS:
    if l.get("raw_p") is not None and l["m"] in HRSWAP.MAX_GAP: _LAD.setdefault((HRSWAP.normname(l["pl"]), l["m"]), []).append((l["ln"], l["raw_p"]))
NHRA = HRSWAP.attach(LEGS, _LAD, BOOKODDS) if BOOKODDS else 0
if BOOKODDS: print(f"hard rock swaps: {NHRA} legs got a nearest Hard Rock line")
# ---- Game lines: moneyline, spread and total for every game (priced in gamelines.py, shared with the matchup boards' best parlays) ----
import gamelines as GLM
import live as LIVE
import books as BOOKS
import social as SOCIAL   # BetSweep Social: 'Post to Social' in the slip panel
import shortlinks as SHORTL   # 'Short link' in the slip panel (owner 10/27)
FDGL = GLM.load_fd(IN); SCHED = GLM.load_sched(IN, WEEK)
NGL = 0; NGL_FD = 0
for G in GAMES:
    for x in GLM.game_legs(G["a"], G["b"], G["pa"] or 0, G["pb"] or 0, G["probs"], SCHED, FDGL):
        LEGS.append({"i": len(LEGS), "pl": x["disp"], "pos": {"Moneyline": "ML", "Spread": "SPR", "Total": "TOT"}[x["m"]], "tm": x["tm"], "opp": x["opp"], "g": G["gid"], "m": x["m"], "ms": x["ms"],
                     "ln": x["ln"], "o": x["o"], "p": round(x["p"], 4), "bk": round(x["bk"], 4), "e": round(x["p"] - x["bk"], 4), "w": x["risk"],
                     "fh": ([["bad", f"Model vs market {x['gap']:.0f} pts", x["risk"]]] if x["risk"] else []) + [["info", "FanDuel" if x["fd"] else "Consensus price", x["why"]]],
                     "proj": None, "avg": None, "n": None, "c": "", "gd": "", "fd": ({"u": "", "m": x["fd"][1], "s": x["fd"][2]} if x["fd"] and x["fd"][1] and x["fd"][2] else None),
                     "dr": None, "sk": "", "gl": {"k": x["k"], "side": x["side"]}, "src": x["src"], "alt": x.get("alt", False)})
        NGL += 1; NGL_FD += 1 if x["fd"] else 0
NALT = sum(1 for l in LEGS if l.get("alt"))
import glbooks as GLB   # DraftKings / Hard Rock game lines (gl| rows in AUTO - Book Odds): exact number -> bks, nearest number -> alt (prop-style)
try: print("game-line books: %d exact, %d nearest-number" % GLB.attach([l for l in LEGS if l.get("gl")], vals("bookodds.json")[1:], {G["gid"]: ((G["pa"] or 0) - (G["pb"] or 0), (G["pa"] or 0) + (G["pb"] or 0)) for G in GAMES}))
except Exception as e: print("note: no game-line book odds this run:", e)
try:   # owner 10/29: say so when the gl| rows are from an earlier week (the DK/HR game-line job has its own Apps Script trigger and can go quiet)
    import datetime as _dt
    _gl = [r for r in vals("bookodds.json")[1:] if len(r) > 11 and str(r[1]).startswith("gl|")]
    _newest = max((str(r[11]) for r in _gl), default="")
    _age = (_dt.datetime.now() - _dt.datetime.strptime(_newest[:16], "%Y-%m-%d %H:%M")).days if _newest else None
    def _gk(game):
        aw, _, hm = str(game).partition(" @ "); return frozenset([GLM.TEAM_FULL.get(aw.strip()), GLM.TEAM_FULL.get(hm.strip())])
    _games = {_gk(r[10]) for r in _gl}
    _this = {frozenset([G["a"], G["b"]]) for G in GAMES}
    _hit = len(_games & _this)
    if not _gl or (_age is not None and _age > 6) or _hit == 0:
        print(f"WARNING: DK/HR game lines stale - newest gl| row {_newest or 'none'} ({len(_gl)} rows, {_hit} of this week's {len(GAMES)} games). "
              "Spread/total/ML legs have no DraftKings / Hard Rock price. Owner: FanDuel odds menu > Refresh game lines (DK/HR) now, then Turn on scheduled refresh. Put this line in the run summary.")
    else: print(f"game lines fresh: newest gl| row {_newest}, {len(_gl)} rows, {_hit} of {len(GAMES)} games")
except Exception as e: print("note: game-line freshness check skipped:", e)
PLAYERS = {p: GL[p] for p in {l["pl"] for l in LEGS} if p in GL}
# Projected snap share (out/projsnaps.json, written by build_boards.py via projsnaps.py): every leg carries sn (fraction, or null when the
# player has no 2026 snaps - fill-ins, 2025 returners, game lines), sn3 (last three played games, newest first) and snw (why). The page shows
# the chip in the player panel and the 'Min snaps' filter reads sn; nothing in the pricing touches it.
PROJSN = {}
try: PROJSN = json.load(open(os.path.join(OUT, "projsnaps.json")))["players"]
except Exception as e: print("warn: projected snaps not loaded (run build_boards.py first):", e)
for l in LEGS:
    s = PROJSN.get(l["pl"]) if not l.get("gl") else None
    l["sn"] = s["proj"] if s else None; l["sn3"] = s["l3"] if s else None; l["snw"] = (s.get("why") or "") if s else ""
print(f"projected snaps: {sum(1 for l in LEGS if l['sn'] is not None)} of {len(LEGS)} legs carry a snap projection")
OPPS = {l["opp"] for l in LEGS}
GLCORR = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "glcorr.json")))["rho"]
# owner 10/29: the player's OWN offense rank in the same stat sits next to every defense rank (offranks.py, mirror of the defense tab:
# rank 1 = the team's position group PRODUCES the most per game; season + last 3 weeks). l["or"] = [season, L3]; OSR = card header.
try:
    import offranks as _ORK
    _OR = _ORK.load(IN, WEEK)
    _chk = _ORK.check(IN, WEEK); print(f"offense ranks: {len(_OR['season'])} teams; defense self-check {_chk[1]}/{_chk[0]} cells match the sheet (max diff {_chk[2]})")
except Exception as _e: _OR = None; print("note: offense ranks unavailable:", _e)
def oranks(pos, tm, m):
    c = rank_col(pos, m)
    if not _OR or not c or not tm: return None
    return [_ORK.rank(_OR, tm, c), _ORK.rank(_OR, tm, c, "l3")]
for l in LEGS:
    if not l.get("gl") and l.get("pos"): l["or"] = oranks(l["pos"], l.get("tm"), l["m"]); l["rc"] = rank_col(l["pos"], l["m"])
TEAMS_ = {l["tm"] for l in LEGS if l.get("tm")}
OSR = {t: {pos: oranks(pos, t, {"QB": "Passing Yards", "RB": "Rushing Yards", "WR": "Receiving Yards", "TE": "Receiving Yards"}[pos]) for pos in ("QB", "RB", "WR", "TE")} for t in TEAMS_}
# full tables for the player panel's "matchup by stat" (owner 10/29: advanced views show offense and defense ranks for every stat separately)
RKTAB = {"cols": list(_ORK.COLS) if _OR else [], "off": _OR["season"] if _OR else {}, "off3": _OR["l3"] if _OR else {},
         "def": {t: RANKS[t] for t in RANKS}, "def3": {t: RANKS3[t] for t in RANKS3}, "dcols": list(DCOL.keys()) if DCOL else []}
POSR = {o: {pos: dranks(pos, o, {"QB": "Passing Yards", "RB": "Rushing Yards", "WR": "Receiving Yards", "TE": "Receiving Yards"}[pos]) for pos in ("QB", "RB", "WR", "TE")} for o in OPPS}   # card header: "GB vs QB #24"
DATA = {"week": WEEK, "built": stamp, "games": GAMES, "legs": LEGS, "pf": PF, "posr": POSR, "osr": OSR, "rk": RKTAB, "corr": CORR, "glcorr": GLCORR, "nlink": NLINK, "gl": PLAYERS, "def": {o: DEF[o] for o in OPPS if o in DEF}, "lg": LG}

BUILDER_CSS = r"""
.bld{max-width:1360px;margin:0 auto;display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:14px;align-items:start}
.bld .panel{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.bld h2{font-family:var(--display);font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:13px;margin:0;padding:10px 14px;border-bottom:1px solid var(--line);color:var(--mute);display:flex;align-items:center;gap:10px}
.bld h2 b{color:var(--ink)}
.filters{display:flex;flex-wrap:wrap;gap:8px;padding:10px 14px;border-bottom:1px solid var(--line);align-items:center;font-size:12.5px}
.filters select,.filters input[type=search]{font:inherit;font-size:13px;color:var(--ink);background:var(--chalk);border:1px solid var(--line);border-radius:4px;padding:5px 8px}
.filters input[type=search]{min-width:150px}
.filters label{display:inline-flex;align-items:center;gap:5px;color:var(--mute);white-space:nowrap}
.filters label input{accent-color:var(--red)}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:4px;overflow:hidden}
.seg button{font:inherit;font-size:12px;padding:5px 9px;background:none;border:0;color:var(--mute);cursor:pointer}
.seg button.on{background:var(--chalk);color:var(--ink)}
.legs{list-style:none;margin:0;padding:0;max-height:calc(100vh - 230px);overflow:auto}
.bld [hidden]{display:none!important}
.tabs{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid var(--line)}
.tab{font:inherit;font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.08em;text-transform:uppercase;display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.tab.on{background:var(--red);border-color:var(--red);color:#fff} .tab .car{font-style:normal;font-size:11px;opacity:.8} .tab[aria-expanded="true"] .car{display:inline-block;transform:rotate(180deg)}
.tabs #count{font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)}
.filters .reset{font:inherit;font-size:12px;font-weight:600;color:var(--ink);background:none;border:1px solid var(--line);border-radius:3px;padding:6px 10px;cursor:pointer} .filters .reset:hover{border-color:var(--red)}
.filters #fQ{flex:1 1 100%;font-size:15px;padding:10px 12px}
/* Games view */
.games{display:grid;gap:10px;padding:12px 14px}
.gcard{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--card)}
.gcard.open{border-color:var(--red)} .gcard.done{opacity:.6} .gcard.live{border-color:var(--red)}
.livetag{font-style:normal;font-weight:800;color:var(--red);letter-spacing:.08em;text-transform:uppercase}
.ghd{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);grid-template-areas:"a m b" "s s s";gap:4px 10px;align-items:center;width:100%;padding:12px 14px 10px;border:0;background:var(--chalk) var(--plays,none) center/360px 130px repeat;color:var(--ink);font:inherit;text-align:left;cursor:pointer}
.ghd:disabled{cursor:not-allowed}
.ghd .gteam{grid-area:a;display:flex;align-items:center;gap:10px;min-width:0} .ghd .gteam.r{grid-area:b;flex-direction:row-reverse;text-align:right}
.ghd .gteam b{font-family:var(--brand);font-style:italic;font-weight:800;font-size:28px;line-height:1} .ghd .gteam small{display:block;color:var(--mute);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase}
.ghd .gteam > span:not(.badge){display:flex;flex-direction:column}
.ghd .badge{display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:7px;background:var(--p);color:var(--ink);font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.06em;box-shadow:inset 0 -4px 0 var(--s);flex:none}
.ghd .gmid{grid-area:m;text-align:center;font-family:var(--display)} .ghd .gmid b{display:block;font-size:26px;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums} .ghd .gmid b i{font-style:normal;color:var(--red);margin:0 6px} .ghd .gmid small{display:block;font-family:var(--body);font-size:11px;color:var(--mute);margin-top:2px}
.ghd .gsum{grid-area:s;display:flex;align-items:center;justify-content:space-between;margin-top:6px;padding-top:8px;border-top:1px dashed var(--line);font-size:12px;color:var(--mute)} .ghd .gsum .car{font-style:normal;color:var(--ink)}
.gbody{border-top:1px solid var(--line)}
.glgrid{display:grid;grid-template-columns:minmax(0,1fr) 128px minmax(0,1fr);gap:8px 14px;padding:10px 14px 8px;border-top:1px solid var(--line);background:var(--card);align-items:start}
.glside{display:grid;grid-template-columns:1fr;gap:6px;width:128px} .glside.l{justify-self:start} .glside.r{justify-self:end} .glmid{display:grid;grid-template-rows:auto auto;gap:6px}
.glb{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;min-height:52px;padding:5px 4px;border-radius:7px;border:1.5px solid var(--line);background:var(--bg);color:var(--ink);font:inherit;cursor:pointer;font-variant-numeric:tabular-nums;line-height:1.15}
.glb small{font-size:12px;font-weight:600;color:var(--mute)} .glb b{font-family:var(--display);font-size:17px;font-weight:700;letter-spacing:.02em} .glb i{font-style:normal;font-size:10px;font-weight:700} .glb i.up{color:var(--good)} .glb i.dn{color:var(--bad)}
.glb:hover:not(:disabled){border-color:var(--red)} .glb.in{background:var(--red);border-color:var(--red);color:#fff} .glb.in small,.glb.in i{color:rgba(255,255,255,.9)}
.glb:disabled{cursor:not-allowed;opacity:.5} .glb.none{border-style:dashed;color:var(--mute);cursor:default}
.glnote{grid-column:1/-1;font-size:10.5px;color:var(--mute);text-align:right}
.altbtn{grid-column:1/-1;display:flex;align-items:center;gap:8px;margin-top:4px;padding:8px 12px;font:inherit;font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink);background:var(--chalk);border:1px solid var(--line);border-radius:7px;cursor:pointer}
.altbtn small{font-family:var(--body);font-weight:500;letter-spacing:0;text-transform:none;color:var(--mute)} .altbtn .car{margin-left:auto;font-style:normal} .altbtn:hover,.altbtn.on{border-color:var(--red)}
.altpanel{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,1fr) 128px minmax(0,1fr);gap:8px 14px;align-items:start;padding:4px 4px 8px 0;max-height:540px;overflow:auto;overscroll-behavior:contain}
.altcol{display:grid;gap:6px;width:100%;max-width:128px} .altcol:first-child{justify-self:start} .altcol.mid{justify-self:center;max-width:none} .altcol:last-child{justify-self:end}
.altcol h4{margin:0 0 2px;font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--mute);text-align:center}
.altpair{display:grid;grid-template-columns:1fr 1fr;gap:6px} .altcol.mid .glb{min-height:46px}
@media (max-width:560px){ .altpanel{grid-template-columns:minmax(0,1fr) 82px minmax(0,1fr);gap:6px} .altcol{max-width:82px} .altpair{grid-template-columns:1fr;gap:5px} }
@media (max-width:560px){ .glgrid{grid-template-columns:minmax(0,1fr) 82px minmax(0,1fr);gap:6px;padding:8px 10px} .glside{gap:5px;width:82px} .glb b{font-size:14px} .glb small{font-size:11px} .glb{min-height:46px;padding:4px 2px} }
.gteamlist h3{margin:0;padding:8px 14px;font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink);background:color-mix(in srgb,var(--chalk) 60%,transparent);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:8px}
.gteamlist h3 .hint{margin-left:auto;display:inline-flex;align-items:center;gap:5px;font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--red);border:1.5px solid var(--red);border-radius:99px;padding:3px 10px;white-space:nowrap} .gteamlist h3 .hint .car{font-style:normal} @media (max-width:560px){ .gteamlist h3 .hint span{display:none} .gteamlist h3 .hint{font-size:10.5px;padding:3px 8px} }
.gteamlist h3 .badge{width:26px;height:26px;font-size:10px;border-radius:5px} .gteamlist h3 small{font-family:var(--body);font-weight:500;letter-spacing:0;text-transform:none;color:var(--mute);margin-left:auto;font-size:11px}
.gteamlist .legs{max-height:none;overflow:visible}
.ghd .gsum .opn{display:inline-flex;align-items:center;gap:5px;font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--red);border:1.5px solid var(--red);border-radius:99px;padding:4px 11px;white-space:nowrap;transition:background .12s,color .12s}
.ghd .gsum .opn.on{background:var(--red);color:#fff}
@media (hover:hover) and (pointer:fine){ .ghd:hover:not(:disabled) .gsum .opn{background:var(--red);color:#fff} }
.ghd:focus{outline:none} .ghd:focus-visible{outline:2px solid var(--red);outline-offset:-2px}
.ghd .gsum .opn .car{margin:0;font-style:normal}
@media (max-width:560px){ .ghd{grid-template-columns:1fr 1fr;grid-template-areas:"a b" "m m" "s s";row-gap:6px} .ghd .gteam b{font-size:24px} .ghd .gteam small{display:none} .ghd .gmid b{font-size:24px} .ghd .gsum{font-size:11px;margin-top:2px} }
.lg{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto auto auto;gap:4px 10px;align-items:center;padding:8px 14px;border-bottom:1px solid var(--line);font-size:13px}
.lg:nth-child(even){background:color-mix(in srgb,var(--chalk) 35%,transparent)}
.lg > .pz{font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.08em;color:var(--red);width:22px}
.lg > .who{min-width:0}
.lg > .who b{display:block;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lg > .who span{color:var(--mute);font-size:11.5px}
.lg > .mk{font-family:var(--display);font-weight:600;font-size:14px;white-space:nowrap}
.lg > .mk small.mp{display:none} .lg > .mk small{display:block;font-family:var(--body);font-weight:500;font-size:11px;color:var(--mute);text-align:right}
.lg > .nums{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.lg > .nums b{display:block;font-size:14px}
.lg > .nums small{color:var(--mute);font-size:11px}
.lg > .nums .e{font-weight:600}
.e.up{color:var(--good)} .e.dn{color:var(--bad)}
.lg > button{font:inherit;font-size:12px;font-weight:600;color:var(--ink);background:none;border:1px solid var(--red);border-radius:3px;padding:4px 9px;cursor:pointer;white-space:nowrap}
.lg > button.in{background:var(--red);color:var(--red-ink)}
.glsrc{font-family:var(--body);font-weight:600;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin-left:6px}
.lg > button.lockd,.alts .ar button.lockd{border-color:var(--line);color:var(--mute);cursor:not-allowed;background:none}
.slip li em.stx{font-style:normal;font-weight:700;color:var(--bad)}
.lg .wf,.slip .wf,.pc .wf{display:inline-block;color:var(--warn);cursor:pointer;font-weight:800;width:18px;height:18px;line-height:16px;text-align:center;border:1.5px solid var(--warn);border-radius:50%;font-size:12px;margin-left:4px;vertical-align:middle}
.why{grid-column:1/-1;margin:0;padding:8px 10px 8px 12px;background:color-mix(in srgb,var(--warn) 12%,transparent);border-left:3px solid var(--warn);border-radius:0 4px 4px 0;font-size:12.5px;line-height:1.45;color:var(--ink)}
.why b{display:block;font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:11px;color:var(--warn);margin-bottom:3px}
.why b small{font-family:var(--body);font-weight:600;text-transform:none;letter-spacing:0;color:var(--mute);margin-left:6px}
.why ul{list-style:none;margin:0;padding:0;display:grid;gap:3px} .why li{padding-left:12px;position:relative} .why li::before{content:"";position:absolute;left:0;top:7px;width:6px;height:6px;border-radius:50%;background:var(--mute)}
.why li.bad::before{background:var(--bad)} .why li.good::before{background:var(--good)} .why li.watch::before{background:var(--warn)}
.why li b{display:inline;font-family:var(--body);text-transform:none;letter-spacing:0;font-size:12.5px;color:var(--ink);margin:0 4px 0 0} .why li.bad b{color:var(--bad)} .why li.good b{color:var(--good)} .why li.watch b{color:var(--warn)}
.slip .why li,.lg .why li,.alts .why li{display:block;grid-template-columns:none;padding:3px 0 3px 12px;border:0;font-size:12.5px;line-height:1.45;color:var(--ink)}
.slip .why li b,.lg .why li b,.alts .why li b{display:inline;font-weight:700} .slip .why li span{display:inline}
.slip .why{grid-column:1/-1;margin-top:4px}
.lg .wf.ok,.slip .wf.ok,.pc .wf.ok{color:var(--good);border-color:var(--good)} .lg .wf.nt,.slip .wf.nt,.pc .wf.nt{color:var(--mute);border-color:var(--mute);font-style:italic;font-family:Georgia,serif}
.why ul{margin:0;padding-left:16px} .why li{margin:2px 0}
.why[hidden]{display:none}
.lg .who b .pn{cursor:pointer}
.lg .who b .pn:hover{color:var(--red)}
.lg.open .who b .pn{color:var(--red)}
.alts{grid-column:1/-1;margin:2px 0 0;padding:4px 0 2px 10px;border-left:3px solid var(--line);display:grid;gap:0}
.alts .ar{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:4px 10px;align-items:center;padding:6px 0;border-top:1px dashed var(--line);font-size:12.5px}
.alts .ar:first-child{border-top:0}
.alts .ar .mk{font-family:var(--display);font-weight:600;font-size:13px;display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px}
.alts .ar .mk small{font-family:var(--body);font-weight:500;font-size:11px;color:var(--mute)}
.alts .ar .nums{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums} .alts .ar .nums b{display:block;font-size:13px} .alts .ar .nums small{color:var(--mute);font-size:11px}
.alts .ar button{font:inherit;font-size:11px;font-weight:600;color:var(--ink);background:none;border:1px solid var(--red);border-radius:3px;padding:3px 8px;cursor:pointer;white-space:nowrap}
.alts .ar button.in{background:var(--red);color:var(--red-ink)} .alts .ar .why,.alts .ar .hist{grid-column:1/-1}
.alts .none{padding:6px 0;color:var(--mute);font-size:12px}
.dpill{display:inline-flex;align-items:center;gap:4px;font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.04em;padding:1px 6px;border-radius:3px;color:#fff;white-space:nowrap;vertical-align:middle}
.dpill small{font-weight:600;opacity:.85} .mup{display:inline-flex;align-items:stretch;border-radius:4px;overflow:hidden;font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.03em;white-space:nowrap;vertical-align:middle;border:1px solid var(--line)}
.mup i{font-style:normal;color:#fff;padding:1px 6px;display:flex;align-items:center} .mup b{font-weight:600;font-size:9px;padding:0 4px;background:var(--chalk);color:var(--mute);display:flex;align-items:center;text-transform:lowercase}
.mup em{font-style:normal;font-weight:600;font-size:9.5px;padding:0 5px;background:var(--chalk);color:var(--mute);display:flex;align-items:center;text-transform:uppercase;letter-spacing:.06em}
.hist table.mbs{border-collapse:collapse;margin:4px 0 6px;font-size:12px;font-variant-numeric:tabular-nums} .hist table.mbs th,.hist table.mbs td{padding:3px 8px;text-align:center;border-bottom:1px solid var(--line)} .hist table.mbs tbody th{text-align:left;font-weight:600;color:var(--ink);white-space:nowrap} .hist table.mbs thead th{font-family:var(--display);font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)} .hist table.mbs tr.cur th{color:var(--red)} .rkc{display:inline-block;min-width:24px;padding:1px 4px;border-radius:3px;color:#fff;font-family:var(--display);font-weight:700;font-size:11px} .dpill.opill{box-shadow:inset 0 0 0 1.5px rgba(255,255,255,.55)} .pc .posm + .posm{margin-left:4px}
.lg .who .tierb{display:inline-block;margin-top:4px;font-size:10px;font-weight:700;letter-spacing:.03em;padding:2px 6px;border-radius:3px;background:#d7332a;color:#fff} .lg .who .tierb.t-td{background:#7a3fd0} .lg .who .tierb.t-safe{background:#1f7a4d}
.lg .who .dprow{display:block;margin-top:3px;line-height:1} .lg .who .dprow .dpill{color:#fff;font-size:10px;padding:1px 5px}
.snchip{display:inline-flex;align-items:baseline;gap:4px;font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.04em;padding:1px 6px;border-radius:3px;border:1px solid var(--line);color:var(--mute);white-space:nowrap;vertical-align:middle;cursor:help;font-variant-numeric:tabular-nums} .alts .snrow{padding:4px 0 2px} .hist .snrow{margin-top:4px}
.mkbtn{cursor:pointer;display:inline-flex;align-items:center;gap:6px}
.mkbtn:hover{color:var(--red)}
.l5{display:inline-flex;gap:2px;align-items:center;padding:3px 5px;border-radius:99px;background:color-mix(in srgb,var(--chalk) 80%,transparent);border:1px solid var(--line);cursor:pointer} .pb .l5:hover{border-color:var(--red)}
.l5 i{width:6px;height:6px;border-radius:50%;background:var(--line);display:inline-block}
.l5 i.ok{background:var(--good)} .l5 i.no{background:var(--bad)}
.l5 small{font-family:var(--body);font-weight:600;font-size:9.5px;color:var(--mute);margin-left:3px;letter-spacing:.04em}
.mkbtn:hover .l5{border-color:var(--red)}
.lg > .mk .pn{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;margin-right:6px;border:1px solid var(--line);border-radius:4px;cursor:pointer;vertical-align:middle}
.lg > .mk .m{display:none}
.lg > .mk .pn:hover,.lg.open > .mk .pn{border-color:var(--red)}
.pn .car{display:inline-block;font-style:normal;font-size:15px;line-height:1;color:var(--ink)}
.lg > .mk .pn.cyc{width:auto;height:auto;padding:2px 7px;gap:4px} .lg > .mk .pn.cyc small{font-family:var(--body);font-size:10px;color:var(--mute)}
.addnote{position:fixed;left:50%;bottom:calc(var(--bs-tabs,0px) + 70px);transform:translateX(-50%);z-index:60;max-width:min(92vw,520px);background:var(--ink);color:var(--bg);font-size:13px;font-weight:600;padding:10px 14px;border-radius:10px;box-shadow:0 10px 30px rgba(0,0,0,.35);transition:opacity .4s} .addnote.out{opacity:0}
.tip{display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;padding:8px 14px;border-bottom:1px solid var(--line);background:color-mix(in srgb,var(--red) 8%,transparent);font-size:12.5px;color:var(--ink)}
.tip b{font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:11px;color:var(--red)}
.tip .ex{display:inline-flex;align-items:center;gap:6px;color:var(--mute)}
.tip .ex .l5{padding:2px 4px}
.tip button{margin-left:auto;font:inherit;font-size:12px;font-weight:600;background:none;border:1px solid var(--line);border-radius:3px;color:var(--ink);padding:3px 9px;cursor:pointer}
.tip[hidden]{display:none}
.helpbtn{font:inherit;font-size:12px;font-weight:600;letter-spacing:0;text-transform:none;color:var(--ink);background:none;border:1px solid var(--line);border-radius:3px;padding:3px 9px;cursor:pointer}
.helpbtn:hover{border-color:var(--red)}
.help{padding:10px 14px 12px;border-bottom:1px solid var(--line);background:color-mix(in srgb,var(--chalk) 60%,transparent)}
.help dl{margin:0;display:grid;gap:8px}
.help dl > div{display:grid;grid-template-columns:92px minmax(0,1fr);gap:10px;font-size:12.5px;line-height:1.45}
.help dt{font-family:var(--display);font-weight:700;letter-spacing:.06em;text-transform:uppercase;font-size:11.5px;color:var(--red);padding-top:2px}
.help dd{margin:0;color:var(--ink)}
.help[hidden]{display:none}
.lg > .nums small.edgel,.alts .ar .nums small.edgel{cursor:help;border-bottom:1px dotted var(--mute)}
@media (max-width:560px){ .help dl > div{grid-template-columns:1fr;gap:2px} }
.hist{grid-column:1/-1;margin:0;padding:8px 10px 8px 12px;background:color-mix(in srgb,var(--chalk) 70%,transparent);border-left:3px solid var(--mute);border-radius:0 4px 4px 0;font-size:12.5px;line-height:1.5}
.hist b.t{display:block;font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:11px;color:var(--mute);margin-bottom:4px}
.hist .gm{display:inline-flex;align-items:center;gap:5px;margin:2px 10px 2px 0;font-variant-numeric:tabular-nums}
.hist .gm i{width:8px;height:8px;border-radius:50%;background:var(--bad);display:inline-block} .hist .gm i.ok{background:var(--good)} .hist .gm i.mid{background:var(--mute)} .hist .gm i.cold{background:var(--bad)}
.hist .gm small{color:var(--mute)}
.hist .sum{display:block;margin-top:4px;color:var(--ink)}
.hist .sum b{font-weight:700}
.hist[hidden]{display:none}
.slip li .why{grid-column:1/-1} .slip li .hrs{grid-column:1/-1;font-size:12px;color:var(--mute);padding:4px 8px;border-left:3px solid #c9a227;background:rgba(201,162,39,.08)} .slip li .hrs.on{border-left-color:#1a1a1a} .slip li .hrs b{display:inline;font-weight:700;color:var(--ink)} .slip li .hrs button{font:inherit;font-size:11.5px;font-weight:700;margin-left:6px;padding:3px 8px;border:1px solid #c9a227;border-radius:3px;background:#1a1a1a;color:#e8c55a;cursor:pointer} .slip li small.swl{font-weight:700;color:#8a6d12;margin-left:4px} .slip li .hrs.dk{border-left-color:#53d337;background:rgba(83,211,55,.10)} .slip li .hrs.dk button{background:#53d337;border-color:#53d337;color:#0b1a07} .slip li .hrs.hr{border-left-color:#5b2d8e;background:rgba(91,45,142,.08)} .slip li .hrs.hr button{background:#5b2d8e;border-color:#5b2d8e;color:#fff} .slip li small.swl.dk{color:#2f8f1c} .slip li small.swl.hr{color:#5b2d8e}
.lg .gdo{color:var(--bad);font-size:10px;letter-spacing:.06em;text-transform:uppercase}
.bar{height:4px;background:var(--barbg);border-radius:2px;position:relative;width:64px;margin-left:auto}
.bar i{position:absolute;left:0;top:0;bottom:0;background:var(--bar);border-radius:2px}
.bar em{position:absolute;top:-3px;width:2px;height:10px;background:var(--red)}
.more{padding:10px 14px;color:var(--mute);font-size:12px}
.lad{display:inline-flex;align-items:center;gap:2px;vertical-align:middle}
.lad button{font:inherit;width:22px;height:22px;line-height:20px;padding:0;border:1px solid var(--line);border-radius:3px;background:var(--chalk);color:var(--ink);cursor:pointer;font-size:14px}
.lad button:disabled{opacity:.3;cursor:default}
.lad button:hover:not(:disabled){border-color:var(--red)}
.lad b{min-width:44px;text-align:center;font-family:var(--display);font-weight:600;font-size:14px}
.lad .dots{display:inline-flex;gap:2px;margin-left:4px}
.lad .dots i{width:4px;height:4px;border-radius:50%;background:var(--line)} .lad .dots i.on{background:var(--red)}
.slip li .lad b{font-size:13px;min-width:40px} .slip li .lad button{width:20px;height:20px;line-height:18px;font-size:12px}
.slip{position:sticky;top:120px}
.slip ul{list-style:none;margin:0;padding:0}
.slip li{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;align-items:center;padding:8px 14px;border-bottom:1px solid var(--line);font-size:13px}
.slip li b{display:block;font-weight:600}
.slip li span{color:var(--mute);font-size:11.5px}
.slip li .x{background:none;border:0;color:var(--mute);font-size:18px;cursor:pointer;padding:0 4px}
.slip li.empty{display:block;padding:18px 14px;color:var(--mute);font-size:13px}
.price{padding:12px 14px;display:grid;grid-template-columns:1fr 1fr;gap:8px 12px;font-size:12.5px;border-bottom:1px solid var(--line)}
.price div{display:flex;flex-direction:column}
.price small{color:var(--mute);font-size:11px;letter-spacing:.04em;text-transform:uppercase}
.price b{font-family:var(--display);font-size:22px;font-weight:700;line-height:1.1}
.price .wide{grid-column:1/-1}
.take{padding:10px 14px;background:var(--chalk);font-size:13px;border-bottom:1px solid var(--line)}
.tgt{padding:10px 14px 12px;border-bottom:1px solid var(--line)}
.tgt .row{display:flex;align-items:baseline;justify-content:space-between;gap:10px;font-size:12px;color:var(--mute)}
.tgt .row b{font-family:var(--display);font-size:18px;color:var(--ink)}
.tgt input[type=range]{width:100%;margin:8px 0 2px;accent-color:var(--red)}
.tgt .ends{display:flex;justify-content:space-between;font-size:11px;color:var(--mute)}
.tgt .hint{font-size:11.5px;color:var(--mute);margin:6px 0 0}
.tgt[hidden]{display:none}
.take b{color:var(--good)}
.flags{padding:8px 14px;font-size:12px;color:var(--warn);border-bottom:1px solid var(--line)}
.flags:empty{display:none}
.acts{display:flex;flex-wrap:wrap;gap:6px;padding:10px 14px}
.acts button{font:inherit;font-size:12px;font-weight:600;color:var(--ink);background:none;border:1px solid var(--line);border-radius:3px;padding:6px 10px;cursor:pointer}
.acts button.pri{border-color:var(--red)} .acts a.fd,.lg a.fd{font:inherit;font-size:12px;font-weight:700;color:#fff;background:#1493ff;border:1px solid #1493ff;border-radius:3px;padding:6px 10px;text-decoration:none;white-space:nowrap} .acts a.fd[aria-disabled=true]{opacity:.45;pointer-events:none}
.acts button:hover{border-color:var(--red)}
.lg > .mk small.bks{display:block;font-size:10.5px;color:var(--mute)} .bks span{margin-right:6px} .bks span.best{color:var(--good);font-weight:700} .bks em{font-style:normal;color:var(--good)}
.acts a.fd.dk,.saved .ops a.fd.dk{background:#53d337;border-color:#53d337;color:#0b1a07} .acts a.fd.hr,.saved .ops a.fd.hr{background:#5b2d8e;border-color:#5b2d8e;color:#fff} .acts a.fd[aria-disabled=true]{opacity:.5;pointer-events:none}
.price .books3{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:baseline} .price .books3 small{flex-basis:100%} .price .books3 span{font-size:13px} .price .books3 span b{font-size:15px} .price .books3 span.best b{color:var(--good)} .price .books3 i{font-style:normal;font-size:11px;color:var(--mute);flex-basis:100%}
.saved{padding:10px 14px;border-top:1px solid var(--line)}
.saved h3{margin:0 0 6px;font-family:var(--display);font-size:15px;letter-spacing:.04em;text-transform:uppercase}.saved h3 small{font-family:var(--body);font-weight:500;letter-spacing:0;text-transform:none;color:var(--mute);font-size:12px;margin-left:6px}
.saved .none{font-size:12.5px;color:var(--mute)}
.saved table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
.saved th{text-align:left;font-family:var(--display);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);padding:4px 6px;border-bottom:1px solid var(--line)}
.saved td{padding:6px 6px;border-bottom:1px solid var(--line);vertical-align:top}
.saved td.r,.saved th.r{text-align:right;white-space:nowrap}
.saved .lgt{display:inline-flex;align-items:center;gap:4px;margin-top:3px;font:inherit;font-size:12px;font-weight:600;color:var(--mute);background:none;border:1px solid var(--line);border-radius:12px;padding:2px 9px;cursor:pointer;white-space:nowrap} .saved .lgt i{font-style:normal;transition:transform .15s} .saved .lgt.on{color:var(--ink);border-color:var(--red)} .saved .lgt.on i{transform:rotate(180deg)} .saved tr.lgrow td{padding:0 6px 10px;border-bottom:1px solid var(--line)} .saved tr.lgrow[hidden]{display:none} .saved .sllegs{list-style:none;margin:0;padding:8px 10px;background:var(--chalk);border-radius:6px;display:grid;gap:5px} .saved .sllegs li{padding:2px 0 !important;border:0 !important;grid-template-columns:none;display:flex;flex-wrap:wrap;gap:2px 8px;align-items:baseline;font-size:13px;line-height:1.35} .saved .sllegs li b{font-weight:600;display:inline} .saved .sllegs li span{color:var(--mute)} .saved tr:has(+ tr.lgrow:not([hidden])) td{border-bottom:0} .saved td.nm b{display:block}.saved td.nm small{color:var(--mute);display:block;line-height:1.35}
.saved tr.cur td{background:color-mix(in srgb,var(--red) 8%,transparent)}
.saved .ops{white-space:nowrap}.saved .ops button,.saved .ops a{font:inherit;font-size:11.5px;font-weight:600;padding:3px 7px;border-radius:3px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer;text-decoration:none;margin-left:3px}
.saved .ops a.fd{background:#1493ff;border-color:#1493ff;color:#fff}.saved .ops button.del{color:var(--mute)}
.saved .e.up{color:var(--good)}.saved .e.dn{color:var(--bad)}
/* owner 10/31: saved slips are one card per slip (name + legs, then FanDuel / Model / Edge / $10 pays, then the buttons) so nothing runs off the side of the betslip */
.saved{overflow:hidden} .saved h3 small{display:block;margin:2px 0 0}
.saved table,.saved tbody{display:block;width:100%} .saved thead{display:none}
.saved tbody tr:not(.lgrow){display:grid;grid-template-columns:repeat(4,minmax(0,1fr));column-gap:6px;padding:9px 2px 8px;border-bottom:1px solid var(--line)}
.saved tbody tr:not(.lgrow) td{border:0 !important;padding:0;min-width:0}
.saved tbody td.nm{grid-column:1/-1;display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;margin-bottom:6px;min-width:0} .saved tbody td.nm b{display:inline} .saved tbody td.nm small{flex-basis:100%} .saved tbody td.nm .lgt{margin-top:0}
.saved tbody td.r{text-align:left;font-size:14px;font-weight:600}
.saved tbody td.r::before{display:block;font-family:var(--display);font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin-bottom:1px}
.saved tbody td.r:nth-child(2)::before{content:"FanDuel"} .saved tbody td.r:nth-child(3)::before{content:"Model"} .saved tbody td.r:nth-child(4)::before{content:"Edge"} .saved tbody td.r:nth-child(5)::before{content:"$10 pays"}
.saved tbody td.ops{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;white-space:normal}
.saved tbody .ops button,.saved tbody .ops a{margin-left:0;padding:6px 12px;font-size:12.5px} .saved tbody .ops button.del{margin-left:auto}
.saved tbody tr.lgrow{display:block} .saved tbody tr.lgrow td{display:block;padding:0 0 10px}
.saved tbody tr.cur{background:color-mix(in srgb,var(--red) 8%,transparent)} .saved tbody tr.cur td{background:none}
.saved .namebox{display:flex;gap:6px;margin:6px 0}.saved .namebox input{flex:1;font:inherit;font-size:13px;padding:6px 8px;border:1px solid var(--line);border-radius:4px;background:var(--card);color:var(--ink)}
.quick{display:flex;flex-wrap:wrap;gap:6px;padding:10px 14px;border-bottom:1px solid var(--line)}
.quick button{font:inherit;font-size:12px;font-weight:600;color:var(--ink);background:var(--chalk);border:1px solid var(--line);border-radius:3px;padding:6px 10px;cursor:pointer}
.quick button:hover{border-color:var(--red)}
.gen{display:grid;gap:8px;padding:10px 14px;border-bottom:1px solid var(--line);font-size:13px}
.gen .grow{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px}
.gen .grow > b{font-family:var(--display);letter-spacing:.06em;text-transform:uppercase;font-size:13px}
.gen #genT{width:84px;font:inherit;font-size:16px;font-weight:700;padding:5px 8px;border:1px solid var(--line);border-radius:4px;background:var(--card);color:var(--ink)}
.gen .presets{display:flex;gap:4px;flex-wrap:wrap} .gen .presets button{font:inherit;font-size:12px;padding:4px 7px;border:1px solid var(--line);border-radius:3px;background:var(--chalk);color:var(--ink);cursor:pointer}
.gen .opts label{display:inline-flex;align-items:center;gap:4px} .gen #genX{flex:1 1 160px;min-width:0;font:inherit;font-size:16px;padding:5px 8px;border:1px solid var(--line);border-radius:4px;background:var(--card);color:var(--ink)}
.gen select{font:inherit;font-size:16px}
.gen .btn{font:inherit;font-family:var(--display);font-weight:700;letter-spacing:.06em;text-transform:uppercase;background:var(--red);color:#fff;border:0;border-radius:4px;padding:8px 14px;cursor:pointer}
.gen .note{color:var(--mute);font-size:12px}
.gen .sug{border:1px solid var(--line);border-radius:6px;padding:8px 10px;margin-top:6px;background:var(--card)}
.gen .sug .sh{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font-family:var(--display);font-weight:700}
.gen .sug .sh b{font-size:18px} .gen .sug ul{margin:4px 0 6px;padding-left:16px} .gen .sug li{margin:1px 0}
.gen .sug button{font:inherit;font-size:12px;font-weight:600;border:1px solid var(--red);color:var(--red);background:none;border-radius:3px;padding:4px 10px;cursor:pointer}
.note{padding:10px 14px;font-size:11.5px;color:var(--mute);line-height:1.45}
.slipbar{display:none}
@media (max-width:900px){
  .bld{grid-template-columns:1fr}
  .legs{max-height:none}
  .slip{position:static}
  .slipwrap{position:fixed;left:0;right:0;bottom:var(--bs-tabs,0px);z-index:40;max-height:75vh;overflow:auto;background:var(--card);border-top:2px solid var(--red);box-shadow:0 -8px 30px rgba(0,0,0,.4);transform:translateY(calc(100% - 52px));transition:transform .2s}
  .slipwrap.open{transform:none}
  .slipbar{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:0 14px;height:52px;cursor:pointer;font-size:13px}
  .slipbar b{font-family:var(--display);font-size:16px}
  .slipbar .n{background:var(--red);color:#fff;border-radius:99px;padding:1px 8px;font-weight:700;font-size:12px}
  body{padding-bottom:64px}
  .lg{grid-template-columns:auto minmax(0,1fr) auto;grid-template-areas:"pz who who" "mk mk add";row-gap:6px}   /* owner 10/28: name + game on top; then the arrow, the prop, its dots and matchup, + Add; the prices; model / book / edge */
  .lg > .pz{grid-area:pz} .lg > .who{grid-area:who} .lg > button{grid-area:add;align-self:start;margin-top:2px} .lg > .nums:not(.bk){display:none} .lg > .mk .d,.lg > .mk small.bks,.lg > .who .dprow{display:none} .lg > .mk .m{display:inline}
  .lg > .mk .dprow.m{display:inline-flex} .lg > .mk small.bkl{display:block;flex-basis:100%;font-size:12px;color:var(--mute)} .lg > .mk small.bkl .best{color:var(--good);font-weight:700} .lg > .mk small.mp{flex-basis:100%} .lg > .mk small.mp b{font-weight:700} .lg > .mk{grid-area:mk;text-align:left;display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px} .lg > .mk small{display:inline;text-align:left} .lg > .nums:not(.bk){grid-area:nums;align-self:center}
  .lg > .nums.bk{display:none} .lg > .mk small.mp{display:block} .lg > .who b{white-space:normal}
}
/* ---- player cards (owner 10/28) ---- */
.pc{list-style:none;margin:0 0 12px;padding:0;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
a.pname{color:inherit;text-decoration:none;cursor:pointer} a.pname:hover,a.pname:focus-visible{text-decoration:underline;text-underline-offset:2px;text-decoration-color:var(--red)} /* owner 10/31: tap the name for his player page */
.pc .pch{display:flex;align-items:flex-start;gap:10px;padding:12px 14px 8px} .pch .pcn{flex:1;min-width:0} .pcg small a.pplink{color:inherit;text-decoration:underline;text-underline-offset:2px} .pcg .mul{font-family:var(--display);font-weight:600;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;margin-right:-6px} .pcg .mup{max-width:100%}
.pc .pch .pz{font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.08em;color:var(--red);width:24px;padding-top:4px;flex:none}
.pc .pcn{flex:1;min-width:0} .pc .pcn > b{display:block;font-size:17px;font-weight:700;line-height:1.2}
.pc .pcn .pcg{display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;margin-top:4px;color:var(--mute);font-size:12px}
.pc .posm{display:inline-flex;align-items:center;gap:4px;white-space:nowrap;font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.04em;padding:2px 7px;border-radius:4px;color:#fff;background:var(--c)} .pc .posm b{font-weight:800} .pc .posm small{font-weight:600;opacity:.85;font-size:10px}
.pc .pcall{flex:none;font:inherit;font-size:12px;font-weight:600;color:var(--ink);background:none;border:1px solid var(--line);border-radius:999px;padding:5px 11px;cursor:pointer;white-space:nowrap} .pc .pcall .car{font-style:normal;font-size:10px;color:var(--mute)} .pc .pcall:hover,.pc.open .pcall{border-color:var(--red)}
.pc .why{margin:0 14px 8px}
.pc .pcb{display:grid;gap:8px;padding:0 10px 10px}
@media (min-width:901px){ .pc.open .pcb{grid-template-columns:1fr 1fr} }
.pb{background:color-mix(in srgb,var(--chalk) 55%,transparent);border:1px solid var(--line);border-radius:11px;padding:10px 12px 10px}
.pb .pbh{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px}
.pb .pbh .mkbtn{font-family:var(--display);font-weight:700;font-size:15px;letter-spacing:.02em;color:var(--ink)}
.seg{display:inline-flex;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:2px;gap:2px}
.seg button{font:inherit;font-size:12px;font-weight:700;padding:4px 10px;border:0;border-radius:6px;background:none;color:var(--mute);cursor:pointer;white-space:nowrap}
.seg button.on{background:var(--red);color:#fff} .seg button:disabled{opacity:.4;cursor:not-allowed}
.pb .pbl{display:grid;grid-template-columns:auto 1fr;grid-template-areas:"line rng" "note note";align-items:center;column-gap:12px}
.pb .pbline{grid-area:line;font-family:var(--display);font-weight:800;font-size:22px;line-height:1;font-variant-numeric:tabular-nums;white-space:nowrap}
.pb .rng{grid-area:rng;width:100%;margin:0;accent-color:var(--red);height:28px} .pb .rng:disabled{opacity:.35}
.pb .pbnote{grid-area:note;font-size:10.5px;color:var(--mute);letter-spacing:.04em;text-transform:uppercase;margin-top:2px}
.pb .pbm{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;margin:8px 0 8px} .pb .pbm .proj{color:var(--mute);font-size:11.5px}
.pb .pbp{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px}
.pb .pbk{display:inline-flex;gap:10px;font-variant-numeric:tabular-nums;font-weight:700;font-size:14px} .pb .pbk small{display:block;font-size:9.5px;font-weight:600;letter-spacing:.08em;color:var(--mute)} .pb .pbk .best{color:var(--good)}
.pb .pbn{display:inline-flex;flex-direction:column;line-height:1.1;font-variant-numeric:tabular-nums} .pb .pbn b{font-size:14px} .pb .pbn small{font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute)}
.pb .add{margin-left:auto;font:inherit;font-size:13px;font-weight:700;color:var(--ink);background:none;border:1.5px solid var(--red);border-radius:8px;padding:7px 13px;cursor:pointer;white-space:nowrap}
.pb .add.in{background:var(--red);color:#fff} .pb .add.lockd{border-color:var(--line);color:var(--mute);cursor:not-allowed}
.pb .tierb{display:inline-block;margin-top:8px;font-size:10px;font-weight:700;letter-spacing:.03em;padding:2px 6px;border-radius:3px;background:#d7332a;color:#fff} .pb .tierb.t-td{background:#7a3fd0} .pb .tierb.t-safe{background:#1f7a4d} .pb .hist{margin-top:8px}
.pb.td .pbh{margin-bottom:2px}

/* ---- slip panel cleanup (owner 10/28): one collapsible build box, book buttons by name, a BetSweep social button ---- */
.buildbox{border-bottom:1px solid var(--line)} .buildbox summary{list-style:none;display:flex;align-items:center;gap:8px;padding:10px 14px;cursor:pointer} .buildbox summary::-webkit-details-marker{display:none}
.buildbox summary b{font-family:var(--display);font-weight:700;font-size:14px;letter-spacing:.04em;white-space:nowrap} .buildbox summary small{color:var(--mute);font-size:11.5px} .buildbox summary .car{margin-left:auto;font-style:normal;color:var(--mute);font-size:11px;transition:transform .15s} .buildbox[open] summary .car{transform:rotate(180deg)}
.buildbox .quick{border-bottom:0;padding-top:2px} .buildbox .gen{border-bottom:0;padding-top:0}
.acts.books3{padding-bottom:4px} .acts.books3 a.fd{flex:1;text-align:center;font-size:13px;padding:9px 10px;border-radius:8px}
.acts.share{padding-top:4px;align-items:stretch}
.acts .social{flex:1;display:inline-flex;align-items:center;gap:10px;text-align:left;font:inherit;padding:8px 12px;border-radius:10px;border:1.5px solid var(--red);background:linear-gradient(135deg,color-mix(in srgb,var(--red) 14%,var(--card)),var(--card));color:var(--ink);cursor:pointer}
.acts .social img{width:34px;height:34px;border-radius:50%;flex:none} .acts .social b{display:block;font-family:var(--display);font-weight:700;font-size:15px;letter-spacing:.02em;line-height:1.1} .acts .social small{display:block;color:var(--mute);font-size:11px;margin-top:2px}
.acts .social:hover{background:linear-gradient(135deg,color-mix(in srgb,var(--red) 24%,var(--card)),var(--card))}
.acts.share #shortl{border-radius:10px;padding:8px 12px;align-self:center}

"""

BUILDER_JS = r"""
(function(){
  var D = window.__BS;
  var legs = D.legs, games = {}, gorder = [];
  var PF = D.pf || {};
  // Games lock at kickoff: their legs leave the list and quick builds, their Add buttons lock, and slip legs from them are marked and left out of the FanDuel link.
  function started(gid){ var g = games[gid]; return !!(g && g.ko && Date.now() >= g.ko); }
  var LV = {};   // live status per game (live.py: ESPN scoreboard, with a 4.5-hours-after-kickoff fallback)
  function finished(gid){ var s = LV[gid]; if(s) return s.st === 'post'; var g = games[gid]; return !!(g && (g.fin || (g.ko && Date.now() >= g.ko + 4.5*3600e3))); }
  legs.forEach(function(l){ var base = PF[l.pl] || []; var fh = l.fh || []; var bad = fh.filter(function(f){ return f[0] === 'bad'; }); l.fl = bad.concat(base).concat(fh.filter(function(f){ return f[0] !== 'bad'; })); });
  D.games.forEach(function(g){ games[g.gid] = g; gorder.push(g.gid); });
  // The slip is shared with the matchup boards: legs are stored by key (player|market|line) under one localStorage entry per week.
  var sel = {}, KEYS = 'bs_slipk_w' + D.week, extraKeys = [];
  function legKey(l){ return l.pl + '|' + l.m + '|' + Math.round(l.ln || 1); }
  // Other books: a leg is sent to DraftKings / Hard Rock at its exact rung when the book posts it (l.bks[b]), otherwise at the book's nearest
  // line (l.ba[b], hrswap.py / glbooks.py). The slip itself stays priced at FanDuel; the note under the buttons lists every substituted line.
  var BN = {dk: 'DraftKings', hr: 'Hard Rock'};
  function bookPick(l, b){ if(l.bks && l.bks[b]) return {s: l.bks[b].s, o: l.bks[b].o, sub: false}; if(l.ba && l.ba[b]) return {s: l.ba[b].s, o: l.ba[b].o, ln: l.ba[b].ln, sub: true}; return null; }
  function subName(l, x){ if(l.gl){ var sd = l.gl.side; return l.m === 'Total' ? (sd === 'OVER' ? 'Over ' : 'Under ') + x.ln : sd + ' ' + (x.ln > 0 ? '+' : '') + x.ln; } return l.pl + ' ' + x.ln + '+'; }
  var TIERL = {even: "Model's Best · even odds", td: "Model's Best · TD", safe: "Model's Best · safer"};
  var TIERT = {even: 'Priced near even money and the model is 8+ pts off FanDuel - in Weeks 6-7 these unders won 59%, overs 55%', td: 'Anytime TD the model rates at or above FanDuel\'s price - 34% hit at ~+270 in Weeks 6-7 (small sample)', safe: 'Model 65%+ and at or above the price - 65% hit at about -195 in Weeks 6-7'};
  function tierChip(l){ return l.tier ? '<span class="tierb t-' + l.tier + '" title="' + esc(TIERT[l.tier]) + '">' + TIERL[l.tier] + '</span>' : ''; }
  function lnTxt(l){ return l.u ? 'under ' + l.ln : Math.round(l.ln) + '+'; }   // unders show FanDuel's main line ('under 74.5')
  function legName(l){ return l.pl + (isGL(l) || isTD(l) || l.m === 'First TD' ? '' : ' ' + lnTxt(l)); }
  function bookNote(ls){ var el = $('#bknote'); if(!el) return; var out = [];
    ['dk', 'hr'].forEach(function(b){ if(!ls.some(function(l){ return bookPick(l, b); })) return;
      var miss = ls.filter(function(l){ return !bookPick(l, b); }), subs = ls.filter(function(l){ var x = bookPick(l, b); return x && x.sub; });
      if(miss.length) out.push(BN[b] + ' doesn\'t price ' + miss.map(legName).join(', ') + ', so the slip can\'t be sent there as built.');
      else if(subs.length) out.push('Send to ' + BN[b] + ' uses its nearest line where it doesn\'t post ours: ' + subs.map(function(l){ var x = bookPick(l, b); return subName(l, x) + ' (' + am(x.o) + ') for ' + (l.gl ? l.pl : lnTxt(l)); }).join(', ') + '. The prices and model % on this slip are FanDuel\'s.'); });
    el.innerHTML = out.map(esc).join('<br>'); }
  var KEYIDX = {}; legs.forEach(function(l){ if(!(legKey(l) in KEYIDX)) KEYIDX[legKey(l)] = l.i; });
  try {
    var ks = JSON.parse(localStorage.getItem(KEYS) || 'null');
    if(Array.isArray(ks)){ ks.forEach(function(k){ if(k in KEYIDX) sel[KEYIDX[k]] = true; else extraKeys.push(k); }); }
    else { (JSON.parse(localStorage.getItem('bs_slip_w' + D.week) || '[]')).forEach(function(i){ if(legs[i]) sel[i] = true; }); }
  } catch(e){}
  // ?add=player|market|line (one or more): legs handed over from the home page / boards land in the slip, then the query is cleared so a reload does not re-add
  var ADDED = null;
  try {
    var adds = new URLSearchParams(location.search).getAll('add');
    if(adds.length){
      ADDED = {ok: [], late: [], missing: []};
      adds.forEach(function(k){ if(k in KEYIDX){ var i = KEYIDX[k]; if(started(legs[i].g)) ADDED.late.push(legs[i]); else { sel[i] = true; ADDED.ok.push(legs[i]); } } else ADDED.missing.push(k); });
      save(); history.replaceState(null, '', location.pathname + location.hash);
    }
  } catch(e){}
  var GROUPS = {}; legs.forEach(function(l){ var k = l.pl + '|' + l.m; (GROUPS[k] = GROUPS[k] || []).push(l); });
  Object.keys(GROUPS).forEach(function(k){ GROUPS[k].sort(function(a,b){ return a.ln - b.ln; }); });
  var pick = {};   // player|market -> index into its ladder (set by the fader); default = best edge
  function ladderOf(l){ return GROUPS[l.pl + '|' + l.m]; }
  // Floor legs: the strategy that graded clean in week 6 - a primary role's line at 30-60% of the projection, -130 to -400, model not fading it, no role risk, no cold streak (Trending down / Usage falling). Ranked by probability, not edge.
  var FLOOR_MIN = {'Receiving Yards': 40, 'Receptions': 3, 'Rushing Yards': 50, 'Rush + Rec Yards': 60};
  // two-way backs: when a player's receiving projection is 20%+ of his rush+rec total, the combined line is the steadier floor (two volume
  // streams, lower variance per yard of projection), so his rushing-only floor legs step aside for the Rush + Rec leg when FanDuel offers one.
  var HAS_RR = {}; legs.forEach(function(l){ if(l.m === 'Rush + Rec Yards' && l.rr && l.rr.rec_share >= 0.2) HAS_RR[l.pl] = true; });
  function isFloor(l){ if(!(l.m in FLOOR_MIN) || l.alt || l.gl || l.proj == null || !(l.proj >= FLOOR_MIN[l.m])) return false; var d = l.ln / l.proj; if(!(d > 0.3 && d <= 0.6)) return false;
    if(l.o == null || l.o > -130 || l.o < -400) return false; if(l.p < l.bk - 0.05) return false; if(l.m === 'Rushing Yards' && l.pos === 'QB') return false;
    if(l.m === 'Rushing Yards' && HAS_RR[l.pl]) return false; if(l.m === 'Rush + Rec Yards' && !(l.rr && l.rr.rec_share >= 0.2)) return false;
    var w = l.w || ''; if(/Snap share slipping|Next man up|Fill-in|Rising:|Trending down|Usage falling/.test(w)) return false; if((l.fh || []).some(function(f){ return f[0] === 'bad'; })) return false; return true; }
  function shown(k){ var g = GROUPS[k]; if(pick[k] != null) return g[pick[k]];
    if(st.floor){ var fp = g.filter(isFloor); if(!fp.length) return null; var hb = fp[0]; fp.forEach(function(x){ if(x.p > hb.p) hb = x; }); return hb; }
    var pool = st.clean ? g.filter(function(x){ return !x.w; }) : g; if(!pool.length) pool = g; var best = pool[0]; pool.forEach(function(x){ if(x.e > best.e) best = x; }); return best; }
  function fader(l, cls){
    var g = ladderOf(l); if(!g || g.length < 2 || isTD(l)) return '';
    var i = g.indexOf(l);
    return '<span class="lad ' + (cls||'') + '" data-k="' + esc(l.pl + '|' + l.m) + '" data-i="' + i + '"><button type="button" data-d="-1" ' + (i<=0?'disabled':'') + ' aria-label="safer line">‹</button><b>' + Math.round(l.ln) + '+</b><button type="button" data-d="1" ' + (i>=g.length-1?'disabled':'') + ' aria-label="longer line">›</button><span class="dots" aria-hidden="true">' + g.map(function(_,j){ return '<i class="' + (j===i?'on':'') + '"></i>'; }).join('') + '</span></span>';
  }
  function fade(k, d, fromSlip){
    var g = GROUPS[k]; if(!g) return;
    var cur = shown(k); if(!cur) return; var i = Math.max(0, Math.min(g.length-1, g.indexOf(cur) + d)); if(g[i] === cur) return;
    pick[k] = i;
    var inSlip = g.filter(function(x){ return sel[x.i]; });
    if(inSlip.length || fromSlip){ inSlip.forEach(function(x){ delete sel[x.i]; }); sel[g[i].i] = true; }
    renderList(); renderSlip();
  }
  var st = { game: 'all', market: 'all', pos: 'all', odds: 'all', clean: false, best: true, floor: false, soft: false, green: false, tier: /[?&]best=1/.test(location.search), snaps: 0, q: '', sort: 'edge', limit: 80, view: 'games' };
  // projected snap share chip (projsnaps.py via build_boards.py): sn is a fraction or null (no 2026 snaps / game line), sn3 the last three played games newest first
  function snChip(l){ if(l.sn == null) return ''; var l3 = (l.sn3 || []).map(function(x){ return Math.round(x*100); }).join(' · ');
    return '<span class="snchip" title="Projected offensive snap share for this game; last three games newest first' + (l.snw ? '; ' + esc(l.snw) : '') + '">Snaps ~' + Math.round(l.sn*100) + '%' + (l3 ? ' (' + l3 + ')' : '') + '</span>'; }
  var openG = {};   // game cards opened on the Games view
  var openAlt = {}; // Alt game lines panel open per game
  function lum(h){ h = h.replace('#',''); var r = parseInt(h.substr(0,2),16)/255, g = parseInt(h.substr(2,2),16)/255, b = parseInt(h.substr(4,2),16)/255; return 0.2126*r + 0.7152*g + 0.0722*b; }
  function badge(t, col){ var p = col[0], s2 = col[1]; return '<span class="badge" style="--p:' + p + ';--s:' + s2 + ';--ink:' + (lum(p) > 0.45 ? '#101820' : '#ffffff') + '">' + t + '</span>'; }
  var $ = function(s, r){ return (r||document).querySelector(s); }, $$ = function(s, r){ return [].slice.call((r||document).querySelectorAll(s)); };
  function am(o){ return o > 0 ? '+' + o : '' + o; }
  // other books: DraftKings / Hard Rock price for the same rung, best price marked (FanDuel stays the reference everywhere else)
  function bookStrip(l){ if (!l.bks) return ''; var rows = [['FD', l.o]]; if (l.bks.dk && l.bks.dk.o != null) rows.push(['DK', l.bks.dk.o]); if (l.bks.hr && l.bks.hr.o != null) rows.push(['HR', l.bks.hr.o]); if (rows.length < 2) return '';
    var best = rows.reduce(function(b, r){ return dec(r[1]) > dec(b[1]) ? r : b; }); return '<small class="bks">' + rows.slice(1).map(function(r){ return '<span class="' + (r[0] === best[0] ? 'best' : '') + '">' + r[0] + ' ' + am(r[1]) + '</span>'; }).join(' ') + (best[0] !== 'FD' ? ' <em>best ' + best[0] + '</em>' : '') + '</small>'; }
  // phone layout (owner 10/28): one line of prices - FD first, then DK / HR where they post the leg
  function booksLine(l){ var rows = [[l.src === 'cons' ? 'Mkt' : 'FD', l.o]]; if (l.bks && l.bks.dk && l.bks.dk.o != null) rows.push(['DK', l.bks.dk.o]); if (l.bks && l.bks.hr && l.bks.hr.o != null) rows.push(['HR', l.bks.hr.o]);
    var best = rows.reduce(function(b, r){ return dec(r[1]) > dec(b[1]) ? r : b; }); return rows.map(function(r){ return '<span class="' + (rows.length > 1 && r[0] === best[0] ? 'best' : '') + '">' + r[0] + ' ' + am(r[1]) + '</span>'; }).join(' '); }
  function dkUrl(ls){ var ids = ls.map(function(l){ var x = bookPick(l, 'dk'); return x && x.s; }).filter(Boolean); if (!ids.length || ids.length !== ls.length) return null; return 'https://sportsbook.draftkings.com/?outcomes=' + ids.map(encodeURIComponent).join('+'); /* DraftKings joins betslip outcomes with '+' (each '#' as %23); a comma loaded only the first leg */ }
  // Hard Rock: the format of a real shared Hard Rock parlay (share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/<id>,<id>,...),
  // ids = the outcome ids The Odds API returns for hardrockbet (the same ids its per-leg links use)
  function hrUrl(ls){ var ids = ls.map(function(l){ var x = bookPick(l, 'hr'); return x && x.s; }).filter(Boolean); if (!ids.length || ids.length !== ls.length) return null; return ids.length > 1 ? 'hardrock://betslip/' + ids.join(',') : 'https://share.hardrock.bet/Pt0T/bet?deep_link_value=hardrock://betslip/' + ids[0]; /* owner-tested 10/21: the share link only carries one selection into the app; the hardrock:// scheme carries the whole parlay (needs the app installed) */ }
  function bookParlay(ls, k){ var d = 1, n = 0; ls.forEach(function(l){ var x = k === 'fd' ? {o: l.o} : bookPick(l, k); if (x && x.o != null){ d *= dec(x.o); n++; } }); return n === ls.length ? d : null; }
  function bookSubbed(ls, k){ return ls.some(function(l){ var x = bookPick(l, k); return x && x.sub; }); }
  function dec(o){ return o > 0 ? 1 + o/100 : 1 + 100/(-o); }
  function toAm(p){ if(p <= 0 || p >= 1) return '—'; return p < 0.5 ? '+' + Math.round((1/p - 1) * 100) : '-' + Math.round(p/(1-p) * 100); }
  function decToAm(d){ return d >= 2 ? '+' + Math.round((d-1)*100) : '-' + Math.round(100/(d-1)); }
  function pc(p){ return Math.round(p*100) + '%'; }
  function legText(l){ if(isGL(l)) return l.pl + (l.m === 'Moneyline' ? '' : '') ; return l.pl + ' ' + (l.m === 'First TD' ? 'first TD' : isTD(l) ? 'anytime TD' : l.ms.toLowerCase() + ' ' + lnTxt(l)); }
  // ---- normal helpers + Gaussian copula Monte Carlo (same math as the boards' slips) ----
  function nppf(p){ var a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00],b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,6.680131188771972e+01,-1.328068155288572e+01],c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,-2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00],d=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,3.754408661907416e+00],q,r;
    if(p<0.02425){q=Math.sqrt(-2*Math.log(p));return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);}
    if(p>1-0.02425){q=Math.sqrt(-2*Math.log(1-p));return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);}
    q=p-0.5;r=q*q;return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1); }
  function rng(seed){ return function(){ seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function isTD(l){ return l.m === 'Anytime TD' || l.m === 'First TD' || l.m === '2+ TD' || l.m === '3+ TD'; }
  // FanDuel will not pay for a leg another leg already guarantees: a player's Anytime TD is implied by his First TD, so it is left out of the book price
  function bookLegs(ls){ var f = ls.filter(function(l){ return l.m === 'First TD'; }); return f.length ? ls.filter(function(l){ return !(l.m === 'Anytime TD' && f.some(function(x){ return x.pl === l.pl; })); }) : ls; }
  function isGL(l){ return !!l.gl; }
  function glPoint(l){ return l.m === 'Spread' ? ' ' + (l.ln > 0 ? '+' : '') + l.ln : (l.m === 'Total' ? ' ' + l.ln : ''); }
  // Game lines in the same game are thresholds on the same two numbers (margin, total): ML and spread on one side move together (+1), opposite sides (-1);
  // over/under likewise; margin vs total ~0. Game lines vs player legs: glcorr.json (stat vs own-team margin / game total, nflverse 2023-25).
  function glCorr(l1, l2){
    if(l1.gl.k !== l2.gl.k) return 0;
    return l1.gl.side === l2.gl.side ? 0.999 : -0.999;
  }
  // game line vs player leg (same game): stat-vs-margin / stat-vs-total correlations by position (nflverse 2023-25), signed by side
  function glProp(gl, pl){ var r = (D.glcorr || {})[pl.c]; if(!r) return 0; if(gl.gl.k === 'M') return gl.gl.side === pl.tm ? r.margin : -r.margin; return gl.gl.side === 'OVER' ? r.total : -r.total; }
  function corr(l1, l2){ var sgn = (l1.u ? -1 : 1) * (l2.u ? -1 : 1); return sgn * corr0(l1, l2); }   // unders: the opposite tail of the same stat
  function corr0(l1, l2){ if(l1.g !== l2.g) return 0; if(l1.gl && l2.gl) return glCorr(l1, l2); if(l1.gl) return glProp(l1, l2); if(l2.gl) return glProp(l2, l1); if(!l1.c || !l2.c) return 0; var rel = l1.pl === l2.pl ? 'SP' : (l1.tm === l2.tm ? 'TM' : 'OPP'); var k = [l1.c, l2.c].sort(); return D.corr[rel + '|' + k[0] + '|' + k[1]] || 0; }
  function chol(C){ var n = C.length, L = []; for(var i=0;i<n;i++){ L.push(new Array(n).fill(0)); for(var j=0;j<=i;j++){ var s=0; for(var k=0;k<j;k++) s += L[i][k]*L[j][k]; L[i][j] = (i===j) ? Math.sqrt(Math.max(C[i][i]-s, 1e-9)) : (C[i][j]-s)/L[j][j]; } } return L; }
  function joint(ls){
    // first-TD rules: two First TD legs in the same game cannot both hit; a player's First TD implies his Anytime TD (drop the implied leg)
    var ftd = ls.filter(function(l){ return l.m === 'First TD'; });
    for(var a = 0; a < ftd.length; a++) for(var b = a + 1; b < ftd.length; b++) if(ftd[a].g === ftd[b].g) return 0;
    if(ftd.length) ls = ls.filter(function(l){ return !(l.m === 'Anytime TD' && ftd.some(function(f){ return f.pl === l.pl; })); });
    var n = ls.length; if(!n) return 0;
    var z = ls.map(function(l){ return nppf(Math.min(0.995, Math.max(0.005, l.p))); });
    var C = []; var anyCorr = false;
    for(var i=0;i<n;i++){ C.push([]); for(var j=0;j<n;j++){ C[i][j] = i===j ? 1 : corr(ls[i], ls[j]); if(i!==j && C[i][j]) anyCorr = true; } }
    if(!anyCorr){ return ls.reduce(function(a,l){ return a*l.p; }, 1); }
    var L = chol(C), R = rng(7), N = 20000, hits = 0, g = new Array(n);
    for(var t=0;t<N;t++){
      for(var i=0;i<n;i++){ var u1 = R() || 1e-9, u2 = R(); g[i] = Math.sqrt(-2*Math.log(u1))*Math.cos(2*Math.PI*u2); }
      var ok = true;
      for(var i=0;i<n && ok;i++){ var x = 0; for(var j=0;j<=i;j++) x += L[i][j]*g[j]; if(x > z[i]) ok = false; }
      if(ok) hits++;
    }
    return hits / N;
  }
  // ---- list ----
  function oddsOk(o){ if(st.odds==='all') return true; if(st.odds==='anchor') return o <= -200; if(st.odds==='mid') return o > -200 && o < 200; return o >= 200; }
  function filtered(){
    var q = st.q.trim().toLowerCase();
    var out = legs.filter(function(l){
      if(st.game !== 'all' && l.g !== st.game) return false;
      if(st.market !== 'all' && (st.market === 'UNDERS' ? !l.u : l.m !== st.market)) return false;
      if(st.tier && !l.tier && !sel[l.i]) return false;
      if(st.pos !== 'all' && l.pos !== st.pos) return false;
      if(!oddsOk(l.o)) return false;
      if(st.clean && l.w) return false;
      if(st.floor && !isFloor(l) && !sel[l.i]) return false;
      if(st.soft && !isSoft(l) && !sel[l.i]) return false;
      if(st.green && !isGreen(l) && !sel[l.i]) return false;
      if(st.snaps && !(l.sn != null && l.sn >= st.snaps) && !sel[l.i]) return false;   // null sn (no 2026 snaps, game lines) hides under any threshold
      if(l.gd.indexOf('CONFIRMED') === 0) return false;
      if(started(l.g) && !sel[l.i]) return false;
      if(q && (l.pl + ' ' + l.tm + ' ' + l.opp + ' ' + l.m).toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
    if(st.best){ out = out.filter(function(l){ return shown(l.pl + '|' + l.m) === l || sel[l.i]; }); }
    // sort by the ladder's best rung so a row does not jump around when you fade it
    var bestE = {}, bestP = {}; legs.forEach(function(l){ var k = l.pl + '|' + l.m; if(bestE[k] == null || l.e > bestE[k]) bestE[k] = l.e; if(bestP[k] == null || l.p > bestP[k]) bestP[k] = l.p; });
    var ke = function(l){ return st.best ? bestE[l.pl + '|' + l.m] : l.e; }, kp = function(l){ return st.best ? bestP[l.pl + '|' + l.m] : l.p; };
    out.sort(function(a,b){ if(st.sort==='edge') return ke(b) - ke(a) || b.e - a.e; if(st.sort==='model') return kp(b) - kp(a) || b.p - a.p; if(st.sort==='odds') return b.o - a.o; if(st.sort==='kick') return (games[a.g].sort+a.g).localeCompare(games[b.g].sort+b.g) || b.e - a.e; return 0; });
    return out;
  }
  // owner 10/26: 'soft matchup' = the opponent ranks top 12 in allowing this stat to this position both on the season and over the last 3 weeks (#1 allows the most)
  // owner 10/30: "green on both sides of offense and defense, or at least gray on offense and dark green on defense" - an OPT-IN filter.
  // Overs: off <= 10 and def <= 10, or off 11-21 and def <= 5 (rank 1 = produces / allows the most). Unders mirror it (red both sides).
  // Not a default gate: 2019-2026 nflverse shows green-both players go OVER an average-based projection ~8 pts less often than the rest
  // (regression - hot averages meet a matchup bump); Weeks 6-7 graded FanDuel legs lean the other way but not significantly (dev log 10/30).
  function isGreen(l){ var o = l.or && l.or[0], d = l.dr && l.dr[0]; if(o == null || d == null) return false;
    if(l.u) return (o >= 23 && d >= 23) || (o >= 12 && o <= 22 && d >= 28);
    return (o <= 10 && d <= 10) || (o >= 11 && o <= 21 && d <= 5); }
  function isSoft(l){ return !!(l.dr && l.dr[0] != null && l.dr[0] <= 12 && (l.dr[1] == null || l.dr[1] <= 12)); }
  function row(l){
    var ok = l.pl + '|' + l.m, cyc = cycleList(l), ci = 0;
    if(CYC[ok] != null){ var j = cyc.findIndex(function(x){ return x.i === CYC[ok]; }); if(j > 0){ l = cyc[j]; ci = j; } else delete CYC[ok]; }
    var g = games[l.g];
    return '<li class="lg' + (openPl[l.pl + '|' + l.m] ? ' open' : '') + '" data-i="' + l.i + '" data-orig="' + esc(ok) + '"><span class="pz">' + l.pos + '</span>' +
      '<span class="who"><b><a class="pname" href="/player/' + plSlug(l.pl) + '/" title="' + esc(l.pl) + ': lines at every book, hit rates, game log">' + esc(l.pl) + '</a>' + flagMark(l) + (l.gd ? ' <span class="gdo">' + esc(l.gd) + '</span>' : '') + '</b><span>' + l.tm + ' vs ' + l.opp + ' · ' + esc(g.kick) + '</span>' + ((l.dr && l.dr[0] != null) || (l.or && l.or[0] != null) ? '<span class="dprow">' + mupill(l) + '</span>' : '') + tierChip(l) + '</span>' +
      '<span class="mk">' + (cyc.length > 1 ? '<span class="pn cyc" role="button" tabindex="0" data-orig="' + esc(ok) + '" title="Next prop for ' + esc(l.pl) + ' (' + (ci + 1) + ' of ' + cyc.length + ')"><i class="car">›</i><small>' + (ci + 1) + '/' + cyc.length + '</small></span>' : '') + '<span class="mkbtn" role="button" tabindex="0" title="Recent games and matchup">' + esc(l.ms) + l5(l) + '</span>' + (isTD(l) ? '' : isGL(l) ? '<small class="glsrc">' + (l.src === 'fd' ? 'FanDuel' : 'consensus') + '</small>' : (ladderOf(l).length > 1 && st.best ? ' ' + fader(l) : ' ' + lnTxt(l))) + ((l.dr && l.dr[0] != null) || (l.or && l.or[0] != null) ? '<span class="dprow m">' + mupill(l) + '</span>' : '') + '<small class="d">' + (l.src === 'cons' ? 'Mkt ' : 'FD ') + am(l.o) + (l.proj != null && l.m !== 'Anytime TD' ? ' · proj ' + l.proj : '') + '</small>' + bookStrip(l) + '<small class="bkl m">' + booksLine(l) + '</small><small class="mp">Model ' + pc(l.p) + ' · book ' + pc(l.bk) + (l.proj != null && l.m !== 'Anytime TD' ? ' · proj ' + l.proj : '') + ' · <b class="e ' + (l.e >= 0 ? 'up' : 'dn') + '">' + (l.e >= 0 ? '+' : '') + (l.e*100).toFixed(1) + ' edge</b></small></span>' +
      '<span class="nums bk"><b>' + pc(l.p) + '</b><small>book ' + pc(l.bk) + '</small><span class="bar"><i style="width:' + Math.round(l.p*100) + '%"></i><em style="left:' + Math.round(l.bk*100) + '%"></em></span></span>' +
      '<span class="nums"><b class="e ' + (l.e >= 0 ? 'up' : 'dn') + '">' + (l.e >= 0 ? '+' : '') + (l.e*100).toFixed(1) + '</b><small class="edgel" title="What is edge?">edge</small></span>' +
      (started(l.g) && !sel[l.i] ? '<button type="button" class="lockd" disabled>Started</button>' : '<button type="button" class="' + (sel[l.i] ? 'in' : '') + '">' + (sel[l.i] ? 'In slip' : '+ Add') + '</button>') + whyBlock(l) + histBlock(l) + altsBlock(l) + '</li>';
  }
  var openPl = {};   // player names whose "other markets" strip is open
  var openHist = {}; // player|market keys whose last-games panel is open
  function rankColor(r){ var t = (r-1)/31, h, l; if(t < 0.5){ h = 140 - 95*(t/0.5); l = 0.30 + 0.08*(t/0.5); } else { h = 45 - 45*((t-0.5)/0.5); l = 0.38 - 0.10*((t-0.5)/0.5); } return 'hsl(' + Math.round(h) + ' 62% ' + Math.round(l*100) + '%)'; }
  // owner 10/29: "when I say matchup, show the literal matchup - offense ranking vs defensive ranking". One pill, two halves:
  // left = his team's offense rank in this stat (1 = produces the most), right = the opponent's defense rank (1 = allows the most). Green = good for the over on both sides.
  function mupill(l, lab){
    var o = l.or && l.or[0] != null ? l.or[0] : null, d = l.dr && l.dr[0] != null ? l.dr[0] : null; if(o == null && d == null) return '';
    var t = (o != null ? esc(l.tm) + ' offense #' + o + (l.or[1] ? ' (last 3 weeks #' + l.or[1] + ')' : '') + ' in this stat, 1 = produces the most' : '') + (o != null && d != null ? ' | ' : '') +
            (d != null ? esc(l.opp) + ' defense #' + d + (l.dr[1] ? ' (last 3 weeks #' + l.dr[1] + ')' : '') + ', 1 = allows the most' : '');
    return '<span class="mup" title="' + t + '">' + (lab ? '<em>' + lab + '</em>' : '') + (o != null ? '<i style="background:' + rankColor(o) + '">' + esc(l.tm) + ' #' + o + '</i>' : '<i style="background:var(--line);color:var(--ink)">' + esc(l.tm) + '</i>') + '<b>vs</b>' + (d != null ? '<i style="background:' + rankColor(d) + '">' + esc(l.opp) + ' #' + d + '</i>' : '<i style="background:var(--line);color:var(--ink)">' + esc(l.opp) + '</i>') + '</span>';
  }
  // advanced: every stat for his position, offense rank and defense rank side by side (season and last 3)
  var POSCOLS = {QB: ['QB Pass Yds', 'QB Pass TD', 'QB Rush Yds', 'QB Rush TD'], RB: ['RB Rush Yds', 'RB Rush TD', 'RB Rec Yds', 'RB Receptions', 'RB Rec TD'],
                 WR: ['WR Rec Yds', 'WR Receptions', 'WR Rec TD'], TE: ['TE Rec Yds', 'TE Receptions', 'TE Rec TD']};
  function rkCell(r){ return r == null ? '<td>—</td>' : '<td><span class="rkc" style="background:' + rankColor(r) + '">' + r + '</span></td>'; }
  function mbsTable(l){
    var R = D.rk || {}, cs = POSCOLS[l.pos]; if(!cs || !R.cols || !R.cols.length) return '';
    var oi = function(c){ return R.cols.indexOf(c); }, di = function(c){ return (R.dcols || []).indexOf(c); };
    var get = function(tab, t, i){ var a = tab && tab[t]; return a && i >= 0 && a[i] != null ? a[i] : null; };
    var rows = cs.map(function(c){ var lab = c.replace(/^(QB|RB|WR|TE) /, '').toLowerCase();
      return '<tr' + (c === l.rc ? ' class="cur"' : '') + '><th>' + esc(lab) + '</th>' + rkCell(get(R.off, l.tm, oi(c))) + rkCell(get(R.off3, l.tm, oi(c))) + rkCell(get(R.def, l.opp, di(c))) + rkCell(get(R.def3, l.opp, di(c))) + '</tr>'; }).join('');
    return '<b class="t" style="margin-top:8px">Matchup by stat · ' + esc(l.tm) + ' ' + l.pos + 's on offense vs ' + esc(l.opp) + ' defense vs ' + l.pos + 's</b>' +
      '<table class="mbs"><thead><tr><th></th><th>' + esc(l.tm) + ' off</th><th>L3</th><th>' + esc(l.opp) + ' def</th><th>L3</th></tr></thead><tbody>' + rows + '</tbody></table>' +
      '<span class="sum">Offense: #1 = the ' + esc(l.tm) + ' ' + l.pos + ' group produces the most of this per game. Defense: #1 = ' + esc(l.opp) + ' allows the most of it to ' + l.pos + 's. Green on both sides is the over-friendly spot. L3 = last 3 weeks.</span>';
  }
  function opill(l){   // owner 10/29: the player's own offense rank in the same stat (1 = produces the most), always beside the defense pill
    if(!l.or || l.or[0] == null) return '';
    var r = l.or[0], r3 = l.or[1];
    return '<span class="dpill opill" style="background:' + rankColor(r) + '" title="' + esc(l.tm) + ' offense rank in this stat for ' + esc(l.pos) + 's: #1 produces the most, #32 the least (season' + (r3 ? ', last 3 weeks' : '') + ')">' + esc(l.tm) + ' off #' + r + (r3 ? '<small>L3 #' + r3 + '</small>' : '') + '</span>';
  }
  function dpill(l){
    if(!l.dr || l.dr[0] == null) return '';
    var r = l.dr[0], r3 = l.dr[1];
    return '<span class="dpill" style="background:' + rankColor(r) + '" title="' + esc(l.opp) + ' defense rank vs this stat: #1 allows the most, #32 the least (season' + (r3 ? ', last 3 weeks' : '') + ')">vs ' + esc(l.opp) + ' #' + r + (r3 ? '<small>L3 #' + r3 + '</small>' : '') + '</span>';
  }
  function l5(l){
    var gs = (D.gl[l.pl] || []).slice(0, 5); if(!gs.length) return '';
    var need = l.m === '2+ TD' ? 2 : l.m === '3+ TD' ? 3 : isTD(l) ? 1 : l.ln;
    var won = function(v){ return l.u ? v < l.ln : v >= need; };   // unders: stayed under the line
    var dots = gs.map(function(g){ var v = g[l.sk]; return '<i class="' + (v == null ? '' : (won(v) ? 'ok' : 'no')) + '"></i>'; }).join('');
    var hit = gs.filter(function(g){ return g[l.sk] != null && won(g[l.sk]); }).length;
    if(l.m === 'First TD') return '';   // no real first-TD history per game in the feed; the anytime TD row already shows his TD games
    return '<span class="l5" title="last ' + gs.length + ' games vs this line, newest first"> ' + dots + '<small>' + hit + '/' + gs.length + '</small></span>';
  }
  function histBlock(l){
    var k = l.pl + '|' + l.m; if(!openHist[k] || isGL(l)) return '';
    var gs = D.gl[l.pl] || []; var need = l.m === '2+ TD' ? 2 : l.m === '3+ TD' ? 3 : isTD(l) ? 1 : l.ln;
    var vals = gs.map(function(g){ return g[l.sk]; });
    var shownG = gs.slice(0, 5);
    var wonH = function(v){ return v != null && (l.u ? v < l.ln : v >= need); };   // unders: stayed under the line
    var items = shownG.map(function(g){ var v = g[l.sk]; var ok = wonH(v); return '<span class="gm"><i class="' + (ok ? 'ok' : '') + '"></i>Wk ' + g.w + ' <small>' + esc(g.opp || '') + '</small> <b>' + (v == null ? '—' : (isTD(l) ? (v >= 1 ? 'TD' : 'no TD') : Math.round(v))) + '</b></span>'; }).join('');
    var l3 = gs.slice(0, 3).filter(function(g){ return g[l.sk] != null; }), l3hit = l3.filter(function(g){ return wonH(g[l.sk]); }).length;
    var all = gs.filter(function(g){ return g[l.sk] != null; }), allhit = all.filter(function(g){ return wonH(g[l.sk]); }).length;
    var line = l.u ? 'under ' + l.ln + ' ' + l.ms.toLowerCase() : l.m === '2+ TD' || l.m === '3+ TD' ? 'scored ' + need + '+ TDs' : isTD(l) ? 'scored a TD' : Math.round(l.ln) + '+ ' + l.ms.toLowerCase();
    var body = gs.length ? items + '<span class="sum"><b>' + l3hit + ' of ' + l3.length + '</b> of his last ' + l3.length + (l.u ? ' stayed ' : ' cleared ') + esc(line) + ' · <b>' + allhit + ' of ' + all.length + '</b> this season' + (l.avg != null && l.m !== 'Anytime TD' ? ' · season avg ' + l.avg : '') + (l.proj != null && l.m !== 'Anytime TD' ? ' · model proj ' + l.proj : '') + '</span>' : '<span class="sum">No game log yet this season for ' + esc(l.pl) + '.</span>';
    var dgs = ((D.def[l.opp] || {})[l.pos] || {})[l.sk] || []; var lgavg = (D.lg[l.pos] || {})[l.sk];
    var posLabel = l.pos + 's', unit = isTD(l) ? 'TDs' : l.ms.toLowerCase();
    var cleared = function(g){ var c = (g.pl || []).some(function(x){ return x[1] >= need; }) || (g.topv != null && g.topv >= need); return l.u ? !c : c; };   // unders: nobody cleared the line
    var dItems = dgs.slice(0, 5).map(function(g){ var ok = cleared(g); var who = (g.pl || []).filter(function(x){ return x[1] >= need; });
      var detail = l.sk === 'td' ? '' : (who.length ? ' <small>(' + who.map(function(x){ return esc(x[0]) + ' ' + Math.round(x[1]); }).join(', ') + ')</small>' : (g.top ? ' <small>(best ' + esc(g.top.split(' ').slice(-1)[0]) + ' ' + Math.round(g.topv) + ')</small>' : ''));
      return '<span class="gm"><i class="' + (ok ? 'ok' : 'no') + '"></i>Wk ' + g.w + ' <small>vs ' + esc(g.vs) + '</small> <b>' + (l.sk === 'td' ? g.tot : Math.round(g.tot)) + '</b>' + detail + '</span>'; }).join('');
    var nHit = dgs.filter(cleared).length, n3 = dgs.slice(0, 3).filter(cleared).length, n3tot = Math.min(3, dgs.length);
    var dAvg = dgs.length ? dgs.reduce(function(a,g){ return a + g.tot; }, 0) / dgs.length : null;
    var lineTxt = l.u ? 'stayed under ' + l.ln + ' ' + esc(unit) : l.sk === 'td' ? (need > 1 ? 'scored ' + need + '+ TDs' : 'scored') : 'cleared ' + Math.round(l.ln) + '+ ' + esc(unit);
    var defBody = dgs.length ? dItems + '<span class="sum">A ' + l.pos + ' has ' + lineTxt + ' against ' + esc(l.opp) + ' in <b>' + nHit + ' of ' + dgs.length + '</b> games this season (<b>' + n3 + ' of ' + n3tot + '</b> of the last ' + n3tot + '). Green = someone at the position hit this line that week; names in parentheses are who did it. ' + esc(l.opp) + ' allows ' + (l.sk === 'td' ? dAvg.toFixed(1) : Math.round(dAvg)) + ' ' + esc(unit) + ' per game to ' + posLabel + '.</span>' : '<span class="sum">No defensive game log for ' + esc(l.opp) + ' yet.</span>';
    return '<div class="hist"><b class="t">Recent games · ' + esc(l.ms) + ' ' + (isTD(l) ? '' : lnTxt(l)) + '</b>' + body + (snChip(l) ? '<div class="snrow">' + snChip(l) + '</div>' : '') +
      '<b class="t" style="margin-top:8px">' + esc(l.opp) + ' defense vs ' + posLabel + ' · ' + esc(unit) + ' allowed (total, who cleared ' + (l.sk === 'td' ? 'a TD' : lnTxt(l)) + ')' + (l.dr && l.dr[0] != null ? ' ' + dpill(l) : '') + '</b>' + defBody + mbsTable(l) + '</div>';
  }
  // the player's other markets (one rung each, fixed market order) - the "scroll through props" arrow and the old dropdown both use it
  function otherMarkets(l){
    var seen = {}; seen[l.m] = true; var rows = [];
    if(isGL(l)){ rows = legs.filter(function(x){ return isGL(x) && !x.alt && x.g === l.g && x.i !== l.i; }); rows.sort(function(a,b){ return b.e - a.e; }); return rows; }
    Object.keys(GROUPS).forEach(function(k){ var g = GROUPS[k]; if(g[0].pl !== l.pl || seen[g[0].m]) return; seen[g[0].m] = true;
      if(g[0].gd.indexOf('CONFIRMED') === 0) return;
      var x = shown(k); if(!x) return; if(st.clean && x.w && !sel[x.i]){ var c = g.filter(function(y){ return !y.w; }); if(c.length){ var b = c[0]; c.forEach(function(y){ if(y.e > b.e) b = y; }); x = b; } }
      rows.push(x); });
    var MO = l.pos === 'QB' ? ['Anytime TD', 'Passing Yards', 'Rushing Yards', 'Receiving Yards', 'Receptions', 'Longest Reception', 'First TD']
           : l.pos === 'RB' ? ['Anytime TD', 'Rushing Yards', 'Rush + Rec Yards', 'Receiving Yards', 'Receptions', 'Longest Reception', 'Passing Yards', 'First TD']
           : ['Anytime TD', 'Receiving Yards', 'Receptions', 'Longest Reception', 'Rushing Yards', 'Passing Yards', 'First TD'];
    rows.sort(function(a,b){ var ia = MO.indexOf(a.m), ib = MO.indexOf(b.m); return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib); });
    return rows;
  }
  // owner 10/28: the arrow scrolls through the player's props in place - the row swaps to his next market (dots, matchup rank,
  // prices, model %, edge all follow). CYC[origin key] = index of the leg currently shown in that row.
  var CYC = {};
  function cycleList(o){ return [o].concat(otherMarkets(o)); }
  function altsBlock(l){
    if(!openPl[l.pl + '|' + l.m]) return '';
    var seen = {}; seen[l.m] = true; var rows = [];
    if(isGL(l)){ rows = legs.filter(function(x){ return isGL(x) && !x.alt && x.g === l.g && x.i !== l.i; }); rows.sort(function(a,b){ return b.e - a.e; });
      return '<div class="alts">' + rows.map(function(x){ return '<div class="ar" data-i="' + x.i + '"><span class="mk">' + esc(x.ms) + ' ' + esc(x.pl) + '<small>' + (x.src === 'cons' ? 'Mkt ' : 'FD ') + am(x.o) + ' · model ' + pc(x.p) + ' · book ' + pc(x.bk) + '</small></span><span class="nums"><b class="e ' + (x.e >= 0 ? 'up' : 'dn') + '">' + (x.e >= 0 ? '+' : '') + (x.e*100).toFixed(1) + '</b><small class="edgel">edge</small></span>' + (started(x.g) && !sel[x.i] ? '<button type="button" class="lockd" disabled>Started</button>' : '<button type="button" class="' + (sel[x.i] ? 'in' : '') + '">' + (sel[x.i] ? 'In slip' : '+ Add') + '</button>') + '</div>'; }).join('') + '</div>'; }
    Object.keys(GROUPS).forEach(function(k){ var g = GROUPS[k]; if(g[0].pl !== l.pl || seen[g[0].m]) return; seen[g[0].m] = true;
      if(g[0].gd.indexOf('CONFIRMED') === 0) return;
      var x = shown(k); if(!x) return; if(st.clean && x.w && !sel[x.i]){ var c = g.filter(function(y){ return !y.w; }); if(c.length){ var b = c[0]; c.forEach(function(y){ if(y.e > b.e) b = y; }); x = b; } }
      rows.push(x); });
    // fixed market order per position (not by edge): the headline leg is Anytime TD; then QB pass yds, rush yds; RB rush yds, rec yds,
    // receptions, longest rec; WR/TE rec yds, receptions, longest rec; First TD last
    var MO = l.pos === 'QB' ? ['Anytime TD', 'Passing Yards', 'Rushing Yards', 'Receiving Yards', 'Receptions', 'Longest Reception', 'First TD']
           : l.pos === 'RB' ? ['Anytime TD', 'Rushing Yards', 'Rush + Rec Yards', 'Receiving Yards', 'Receptions', 'Longest Reception', 'Passing Yards', 'First TD']
           : ['Anytime TD', 'Receiving Yards', 'Receptions', 'Longest Reception', 'Rushing Yards', 'Passing Yards', 'First TD'];
    rows.sort(function(a,b){ var ia = MO.indexOf(a.m), ib = MO.indexOf(b.m); return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib); });
    var snrow = snChip(l) ? '<div class="snrow">' + snChip(l) + '</div>' : '';
    if(!rows.length) return '<div class="alts">' + snrow + '<div class="none">No other FanDuel markets for ' + esc(l.pl) + ' this week.</div></div>';
    return '<div class="alts">' + snrow + rows.map(function(x){
      return '<div class="ar" data-i="' + x.i + '"><span class="mk"><span class="mkbtn" role="button" tabindex="0" title="Recent games and matchup">' + esc(x.ms) + l5(x) + '</span>' + (isTD(x) ? '' : isGL(x) ? ' ' + esc(x.pl) : (ladderOf(x).length > 1 ? ' ' + fader(x) : ' ' + lnTxt(x))) + '<small>' + (x.src === 'cons' ? 'Mkt ' : 'FD ') + am(x.o) + (x.proj != null && x.m !== 'Anytime TD' ? ' · proj ' + x.proj : '') + ' · model ' + pc(x.p) + ' · book ' + pc(x.bk) + '</small>' + dpill(x) + flagMark(x) + '</span>' +
        '<span class="nums"><b class="e ' + (x.e >= 0 ? 'up' : 'dn') + '">' + (x.e >= 0 ? '+' : '') + (x.e*100).toFixed(1) + '</b><small class="edgel" title="What is edge?">edge</small></span>' +
        (started(x.g) && !sel[x.i] ? '<button type="button" class="lockd" disabled>Started</button>' : '<button type="button" class="' + (sel[x.i] ? 'in' : '') + '">' + (sel[x.i] ? 'In slip' : '+ Add') + '</button>') + whyBlock(x) + histBlock(x) + '</div>';
    }).join('') + '</div>';
  }
  function flagMark(l){
    var fl = l.fl || [];
    if(l.w) return ' <span class="wf" role="button" tabindex="0" aria-label="flags on this leg" title="Risk flags - tap to read">!</span>';
    if(fl.some(function(f){ return f[0] === 'good'; })) return ' <span class="wf ok" role="button" tabindex="0" aria-label="flags on this leg" title="Good flags - tap to read">✓</span>';
    if(fl.length) return ' <span class="wf nt" role="button" tabindex="0" aria-label="flags on this leg" title="Notes - tap to read">i</span>';
    return '';
  }
  function whyBlock(l){
    var fl = l.fl || [];
    if(!fl.length) return '';
    var nb = fl.filter(function(f){ return f[0] === 'bad'; }).length, ng = fl.filter(function(f){ return f[0] === 'good'; }).length;
    var items = fl.map(function(f){ return '<li class="' + f[0] + '"><b>' + esc(f[1]) + '</b> ' + esc(f[2]) + '</li>'; }).join('');
    return '<div class="why" hidden><b>Flags on this leg <small>' + nb + ' risk · ' + ng + ' plus · this season only</small></b><ul>' + items + '</ul></div>';
  }
  function toggleWhy(el){ var li = el.closest('li'); var w = li && li.querySelector('.why'); if(w) w.hidden = !w.hidden; }
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  // ---- Games view: one scorecard per game; open it for every player in the game (his anytime-TD leg, or his best leg when FanDuel has no TD price) ----
  function gameLegs(gid){
    // one row per player: the Anytime TD leg if he has one, else his best-edge leg; honours the clean filter and skips confirmed-out players
    var byPl = {};
    legs.forEach(function(l){ if(l.g !== gid || l.gd.indexOf('CONFIRMED') === 0 || l.m === 'First TD' || isGL(l)) return; (byPl[l.pl] = byPl[l.pl] || []).push(l); });
    return Object.keys(byPl).map(function(pl){ var ls = byPl[pl]; var td = ls.filter(function(l){ return l.m === 'Anytime TD'; })[0];
      if(!td){ var pos = ls[0].pos, order = pos === 'QB' ? ['Passing Yards', 'Rushing Yards'] : pos === 'RB' ? ['Rushing Yards', 'Receiving Yards', 'Receptions', 'Longest Reception'] : ['Receiving Yards', 'Receptions', 'Longest Reception'];
        order.some(function(m){ var c = ls.filter(function(l){ return l.m === m; }); if(!c.length) return false; td = c[0]; c.forEach(function(l){ if(l.e > td.e) td = l; }); return true; });
        if(!td){ ls.forEach(function(l){ if(!td || l.e > td.e) td = l; }); } }
      return td; }).filter(Boolean);
  }
  // FanDuel-style game lines on the scorecard: one row per team, Spread | Moneyline | Total; tap a cell to add it to the slip
  function glGrid(g, off){
    var gls = legs.filter(function(l){ return isGL(l) && l.g === g.gid; }); if(!gls.length) return '';
    function cell(l, top){
      if(!l) return '<span class="glb none">—</span>';
      var e = l.e*100, cls = 'glb' + (sel[l.i] ? ' in' : '') + (l.w ? ' flag' : '');
      var tip = l.pl + ' · ' + (l.src === 'fd' ? 'FanDuel ' : 'market ') + am(l.o) + ' · model ' + pc(l.p) + ' vs book ' + pc(l.bk) + (l.w ? ' · ' + l.w : '');
      return '<button type="button" class="' + cls + '" data-i="' + l.i + '" title="' + esc(tip) + '"' + (off && !sel[l.i] ? ' disabled' : '') + '>' + (top ? '<small>' + top + '</small>' : '') +
        '<b>' + am(l.o) + '</b><i class="' + (e >= 0 ? 'up' : 'dn') + '">' + (l.w ? '⚠ ' : '') + (e >= 0 ? '+' : '') + e.toFixed(1) + '</i></button>';
    }
    function find(m, side){ return gls.filter(function(l){ return !l.alt && l.m === m && (m === 'Total' ? l.gl.side === side : l.tm === side); })[0]; }
    var alts = gls.filter(function(l){ return l.alt; });
    function altPanel(){
      if(!alts.length) return '';
      var btn = '<button type="button" class="altbtn' + (openAlt[g.gid] ? ' on' : '') + '" data-g="' + g.gid + '">Alt game lines <small>' + alts.length + ' FanDuel alternates</small><i class="car">' + (openAlt[g.gid] ? '▴' : '▾') + '</i></button>';
      if(!openAlt[g.gid]) return btn;
      var byLn = function(x, y){ return x.ln - y.ln; };
      var spA = alts.filter(function(l){ return l.m === 'Spread' && l.tm === g.a; }).sort(byLn), spB = alts.filter(function(l){ return l.m === 'Spread' && l.tm === g.b; }).sort(byLn);
      var pts = []; alts.forEach(function(l){ if(l.m === 'Total' && pts.indexOf(l.ln) < 0) pts.push(l.ln); }); pts.sort(function(x, y){ return x - y; });
      var tot = pts.map(function(pt){ var o = alts.filter(function(l){ return l.m === 'Total' && l.gl.side === 'OVER' && l.ln === pt; })[0], u = alts.filter(function(l){ return l.m === 'Total' && l.gl.side === 'UNDER' && l.ln === pt; })[0];
        return '<div class="altpair">' + cell(o, o ? 'O ' + pt : '') + cell(u, u ? 'U ' + pt : '') + '</div>'; }).join('');
      var col = function(ls, t){ return '<div class="altcol"><h4>' + esc(t) + ' alt spreads</h4>' + (ls.map(function(l){ return cell(l, (l.ln > 0 ? '+' : '') + l.ln); }).join('') || '<span class="glnote">none</span>') + '</div>'; };
      return btn + '<div class="altpanel">' + col(spA, g.a) + '<div class="altcol mid"><h4>Alt totals</h4>' + (tot || '<span class="glnote">none</span>') + '</div>' + col(spB, g.b) + '</div>';
    }
    var side = function(t, lr){ var sp = find('Spread', t), ml = find('Moneyline', t);
      return '<div class="glside ' + lr + '">' + cell(ml, 'ML') + cell(sp, sp ? (sp.ln > 0 ? '+' : '') + sp.ln : 'Spread') + '</div>'; };
    var ov = find('Total', 'OVER'), un = find('Total', 'UNDER');
    var anyCons = gls.some(function(l){ return l.src === 'cons'; });
    return '<div class="glgrid">' + side(g.a, 'l') +
      '<div class="glmid">' + cell(ov, ov ? 'O ' + ov.ln : 'Over') + cell(un, un ? 'U ' + un.ln : 'Under') + '</div>' + side(g.b, 'r') +
      '<span class="glnote">' + (anyCons ? 'market-average prices (FanDuel\'s game lines are not posted yet) · ' : '') + 'bottom number = model edge vs the price (%)</span>' + altPanel() + '</div>';
  }
  function renderGames(){
    var wrap = $('#games'); if(!wrap) return;
    var posOrd = {QB:0, RB:1, WR:2, TE:3};
    // finished games sink below the ones still to come or in progress (kickoff order kept within each group)
    var ord = gorder.filter(function(gid){ return !finished(gid); }).concat(gorder.filter(function(gid){ return finished(gid); }));
    wrap.innerHTML = ord.map(function(gid){
      var g = games[gid], gl = gameLegs(gid), off = started(gid), open = !!openG[gid] && !off;
      var best = null; gl.forEach(function(l){ if(!best || l.e > best.e) best = l; });
      var nAll = legs.filter(function(l){ return l.g === gid; }).length;
      var fav = g.pa >= g.pb ? g.a : g.b, mar = Math.abs(g.pa - g.pb);
      var head = '<button type="button" class="ghd" data-g="' + gid + '" aria-expanded="' + open + '"' + (off ? ' disabled' : '') + '>' +
        '<span class="gteam">' + badge(g.a, g.ca) + '<b>' + g.a + '</b><small>' + esc(g.na) + '</small></span>' +
        '<span class="gmid"><b>' + g.pa.toFixed(1) + '<i>–</i>' + g.pb.toFixed(1) + '</b><small>' + (finished(gid) ? (g.fin ? 'Final: ' + esc(g.fin) : 'Final') + ' · projected above' : off ? '<em class="livetag">Live</em> · projected above' : esc(g.kick) + ' · ' + esc(g.most)) + '</small></span>' +
        '<span class="gteam r">' + badge(g.b, g.cb) + '<b>' + g.b + '</b><small>' + esc(g.nb) + '</small></span>' +
        '<span class="gsum"><span>' + (off ? 'Legs locked at kickoff' : !gl.length ? 'Game lines only - player props not posted yet' : (gl.length + ' players · ' + nAll + ' legs' + (best ? ' · best edge ' + esc(best.pl.split(' ').slice(-1)[0]) + ' ' + (best.e>=0?'+':'') + (best.e*100).toFixed(1) : ''))) + '</span>' +
        (off || !gl.length ? '' : '<span class="opn' + (open ? ' on' : '') + '">' + (open ? 'Hide player legs <i class="car">▴</i>' : 'Tap for player legs <i class="car">▾</i>') + '</span>') + '</span></button>';
      var body = '';
      if(open){
        var teams = [g.a, g.b]; body = '<div class="gbody">' + teams.map(function(tm){
          var rows = gl.filter(function(l){ return l.tm === tm; }).sort(function(a,b){ return (posOrd[a.pos] != null ? posOrd[a.pos] : 9) - (posOrd[b.pos] != null ? posOrd[b.pos] : 9) || b.p - a.p; });
          var html = cards(rows);   // QB, then RB, WR, TE - one card per player
          return '<div class="gteamlist"><h3>' + badge(tm, tm === g.a ? g.ca : g.cb) + ' ' + (tm === g.a ? esc(g.na) : esc(g.nb)) + '</h3><ul class="legs">' + (html || '<li class="more">No FanDuel legs priced yet.</li>') + '</ul></div>';
        }).join('') + '</div>';
      }
      var lv = LV[gid], tk = (lv && window.BSLive) ? window.BSLive.tickHtml(g, lv) : '';
      return '<section class="gcard' + (open ? ' open' : '') + (off ? ' off' : '') + (finished(gid) ? ' done' : '') + (lv && lv.st === 'in' ? ' live' : '') + '" id="g-' + gid + '">' + head +
        '<div class="tick' + (lv && lv.st === 'post' ? ' final' : '') + '" id="tk-' + gid + '" aria-live="polite"' + (tk ? '' : ' hidden') + '>' + tk + '</div>' + glGrid(g, off) + body + '</section>';
    }).join('');
  }
  function isFiltered(){ return st.game !== 'all' || st.market !== 'all' || st.pos !== 'all' || st.odds !== 'all' || st.clean || st.floor || st.soft || st.tier || !!st.snaps || !st.best || st.q.trim() !== ''; }
  function setView(v){
    st.view = v;
    $('#tabGames').classList.toggle('on', v === 'games'); $('#tabSearch').classList.toggle('on', v === 'list');
    $('#tabSearch').setAttribute('aria-expanded', String(v === 'list'));
    $('#filters').hidden = v !== 'list'; $('#games').hidden = v !== 'games'; $('#legs').hidden = v !== 'list'; $('#more').hidden = v !== 'list'; $('#count').hidden = v !== 'list';
    if(v === 'list'){ renderList(); var q = $('#fQ'); if(q && window.matchMedia('(min-width: 901px)').matches) q.focus(); } else renderGames();
  }
  function renderList(){
    if(st.view === 'games'){ renderGames(); }
    var f = filtered(); var ul = $('#legs'); ul.innerHTML = cards(f.slice(0, st.limit)) || '<li class="more">No legs match these filters.</li>';
    $('#count').textContent = f.length + ' legs';
    $('#more').style.display = f.length > st.limit ? 'block' : 'none';
    $('#more').textContent = 'Show ' + Math.min(80, f.length - st.limit) + ' more (' + (f.length - st.limit) + ' hidden)';
  }
  // ---- slip ----
  function slipLegs(){ return Object.keys(sel).map(function(i){ return legs[+i]; }).sort(function(a,b){ return (games[a.g].sort+a.g).localeCompare(games[b.g].sort+b.g); }); }
  window.bsSlipLegs = slipLegs; window.bsGameKo = function(gid){ var g = games[gid]; return g && g.ko ? +g.ko : null; };   // for "Post to Social" (social.py)
  function save(){ try { var ks = Object.keys(sel).map(function(i){ return legKey(legs[+i]); }); localStorage.setItem(KEYS, JSON.stringify(ks.concat(extraKeys))); localStorage.setItem('bs_slip_w' + D.week, JSON.stringify(Object.keys(sel).map(Number))); } catch(e){} }
  function reloadSel(){ try { var ks = JSON.parse(localStorage.getItem(KEYS) || '[]'); var before = JSON.stringify(Object.keys(sel).map(function(i){ return legKey(legs[+i]); }).concat(extraKeys).sort()); sel = {}; extraKeys = []; (Array.isArray(ks) ? ks : []).forEach(function(k){ if(k in KEYIDX) sel[KEYIDX[k]] = true; else extraKeys.push(k); }); if(JSON.stringify(ks.slice().sort()) !== before){ renderList(); renderSlip(); } } catch(err){} }
  window.addEventListener('storage', function(e){ if(e.key === KEYS) reloadSel(); });
  // owner 10/28: same slip on every page - re-read storage when the page comes back into view (back/forward cache keeps the old
  // in-memory slip) and after the account sync pulls a newer copy
  window.addEventListener('pageshow', function(e){ if(e.persisted) reloadSel(); });
  document.addEventListener('visibilitychange', function(){ if(document.visibilityState === 'visible') reloadSel(); });
  window.addEventListener('focus', reloadSel);
  document.addEventListener('bs-account', function(e){ if(e.detail && e.detail.changed) reloadSel(); });
  function renderSlip(){
    var ls = slipLegs(); var ul = $('#slipLegs');
    $$('.slipbar .n').forEach(function(n){ n.textContent = ls.length; });
    if(!ls.length){ ul.innerHTML = '<li class="empty">Tap <b>+ Add</b> on any leg. The slip prices the combination against the model, with same-game legs correlated the way the boards do it.</li>'; $('#price').innerHTML = ''; $('#take').style.display='none'; $('#flags').innerHTML=''; $('.slipbar b').textContent = 'Your slip'; $('#tgt').hidden = true; fdButton(ls); dkButton(ls); hrButton(ls); bookNote(ls); save(); if (typeof renderSaved === 'function') renderSaved(); return; }
    ul.innerHTML = ls.map(function(l){ return '<li><div><b>' + esc(l.pl) + ' ' + (isGL(l) ? '<small class="glsrc">' + esc(l.ms) + (l.src === 'fd' ? '' : ' · consensus') + '</small>' : l.m === 'First TD' ? 'first TD scorer' : isTD(l) ? 'anytime TD' : esc(l.ms.toLowerCase()) + ' ' + (ladderOf(l).length > 1 ? fader(l, 'sl') : lnTxt(l))) + flagMark(l) + '</b><span>' + (started(l.g) ? '<em class="stx">Game started</em> · ' : '') + l.tm + ' vs ' + l.opp + ' · ' + (l.src === 'cons' ? 'Mkt ' : 'FD ') + am(l.o) + ' · model ' + pc(l.p) + ' vs book ' + pc(l.bk) + '</span></div><span class="e ' + (l.e>=0?'up':'dn') + '">' + (l.e>=0?'+':'') + (l.e*100).toFixed(1) + '</span><button class="x" type="button" data-i="' + l.i + '" aria-label="remove">×</button>' + whyBlock(l) + '</li>'; }).join('');
    var bls = bookLegs(ls), implied = ls.length - bls.length;
    var bookDec = bls.reduce(function(a,l){ return a*dec(l.o); }, 1), bookP = 1/bookDec;
    var ind = ls.reduce(function(a,l){ return a*l.p; }, 1), fair = joint(ls);
    var ev = fair*bookDec - 1;
    var sameGame = {}; ls.forEach(function(l){ sameGame[l.g] = (sameGame[l.g]||0) + 1; }); var sgp = Object.keys(sameGame).filter(function(g){ return sameGame[g] > 1; });
    $('#price').innerHTML =
      '<div><small>FanDuel price</small><b>' + decToAm(bookDec) + '</b><span>legs multiplied' + (implied ? ' (implied anytime TD not counted)' : '') + ' · implies ' + pc(bookP) + '</span></div>' +
      '<div><small>Model fair</small><b>' + toAm(fair) + '</b><span>' + pc(fair) + ' to hit' + (Math.abs(fair-ind) > 0.002 ? ' · ' + pc(ind) + ' if independent' : '') + '</span></div>' +
      '<div><small>Edge</small><b class="e ' + (fair-bookP>=0?'up':'dn') + '">' + (fair-bookP>=0?'+':'') + ((fair-bookP)*100).toFixed(1) + ' pts</b></div>' +
      '<div><small>EV per $1</small><b class="e ' + (ev>=0?'up':'dn') + '">' + (ev>=0?'+$':'−$') + Math.abs(ev).toFixed(2) + '</b></div>' +
      '<div class="wide"><small>Payout on $10 at the FanDuel price</small><b>$' + (10*bookDec).toFixed(2) + '</b></div>' + bookRow(ls, bookDec);
    $('#take').style.display = ''; $('#take').innerHTML = 'Take it at <b>' + toAm(fair*0.95) + '</b> or better' + (sgp.length ? ' — it has same-game legs, so compare that number to FanDuel\'s same-game quote, not the multiplied price.' : '.');
    var flags = [];
    if(sgp.length) flags.push(sgp.length + ' game' + (sgp.length>1?'s':'') + ' with multiple legs (correlation priced in)');
    var pls = {}; ls.forEach(function(l){ pls[l.pl] = (pls[l.pl]||0)+1; }); var dupe = Object.keys(pls).filter(function(p){ return pls[p] > 1; }); if(dupe.length) flags.push('same player twice: ' + dupe.join(', '));
    var warned = ls.filter(function(l){ return l.w; }); if(warned.length) flags.push(warned.length + ' leg' + (warned.length>1?'s':'') + ' carr' + (warned.length>1?'y':'ies') + ' a model warning');
    var neg = ls.filter(function(l){ return l.e < 0; }); if(neg.length) flags.push(neg.length + ' leg' + (neg.length>1?'s':'') + ' priced worse than the model');
    var mixG = {}; ls.forEach(function(l){ mixG[l.g] = mixG[l.g] || {gl:0, pr:0}; mixG[l.g][isGL(l) ? 'gl' : 'pr']++; });
    if(Object.keys(mixG).some(function(g){ return mixG[g].gl && mixG[g].pr; })) flags.push('game lines and player legs from the same game are priced together: the model uses how each stat moves with the margin and the total (e.g. QB passing yards rise with the total, RB rushing yards with a lead)');
    ls.forEach(function(x){ if(x.m === 'Moneyline' && ls.some(function(y){ return y.m === 'Spread' && y.g === x.g && y.tm === x.tm; })) flags.push(x.pl + ' and his spread overlap (a cover usually means a win) - the model prices that, but the multiplied FanDuel price overstates the payout; the FanDuel SGP quote will be much shorter'); });
    // owner 10/26 (Javonte Williams 2+ rec on MNF: Dallas led all night, he ran 20+ times and caught nothing): backs catch fewer passes when their
    // team is ahead (2019-26 nflverse: RB1 -0.4 receptions, +2 carries when leading by 10+), so a back's receptions leg works against legs that need his team ahead
    ls.forEach(function(x){ if(x.pos !== 'RB' || (x.m !== 'Receptions' && x.m !== 'Receiving Yards')) return;
      var win = ls.filter(function(y){ return y.g === x.g && y.tm === x.tm && (y.m === 'Moneyline' || y.m === 'Spread'); });
      var rush = ls.filter(function(y){ return y.pl === x.pl && (y.m === 'Rushing Yards' || y.m === 'Rush Attempts'); });
      if(win.length) flags.push(x.pl + ' ' + x.ms.toLowerCase() + ' works against ' + win.map(function(y){ return y.pl; }).join(' / ') + ': when ' + x.tm + ' gets ahead, backs run more and catch less - consider his rushing line instead');
      if(rush.length) flags.push(x.pl + ' rushing and receiving legs pull in opposite directions (big rushing games come with a lead, when backs catch less) - pick one'); });
    var gm = {}; ls.forEach(function(x){ if(x.m === 'Total'){ gm[x.g] = gm[x.g] || {}; gm[x.g][x.gl.side] = 1; } }); if(Object.keys(gm).some(function(g){ return gm[g].OVER && gm[g].UNDER; })) flags.push('over and under on the same game can never both hit');
    var cons = ls.filter(function(l){ return l.src === 'cons'; }); if(cons.length) flags.push(cons.length + ' game line' + (cons.length>1?'s are':' is') + ' priced off the consensus market, not FanDuel, and cannot be sent to FanDuel - add ' + (cons.length>1?'them':'it') + ' by hand at FanDuel\'s number');
    var gone = ls.filter(function(l){ return started(l.g); }); if(gone.length) flags.unshift(gone.length + ' leg' + (gone.length>1?'s are':' is') + ' from a game that already kicked off - FanDuel will not take ' + (gone.length>1?'them':'it') + ', so ' + (gone.length>1?'they are':'it is') + ' left out of the FanDuel slip; remove ' + (gone.length>1?'them':'it'));
    var fg = {}; ls.forEach(function(l){ if(l.m === 'First TD') fg[l.g] = (fg[l.g]||0)+1; }); if(Object.keys(fg).some(function(g){ return fg[g] > 1; })) flags.push('two First TD legs in the same game can never both hit - the slip is dead as built');
    ls.forEach(function(l){ if(l.m === 'First TD' && ls.some(function(x){ return x.m === 'Anytime TD' && x.pl === l.pl; })) flags.push(l.pl + ' first TD already implies his anytime TD - it adds nothing to the model chance and FanDuel will not pay for it, so it is left out of the price; remove it'); });
    if(ls.some(function(l){ return l.m === 'First TD'; }) && !flags.some(function(f){ return f.indexOf('never both') >= 0; })) flags.push('First TD is a high-variance market: the model treats it as independent of the other legs except the rules above');
    if(flags.some(function(f){ return f.indexOf('never both') >= 0 || f.indexOf('slip is dead') >= 0; })){ $('#take').innerHTML = '<b>This slip cannot win as built</b> - see the warning below.'; }
    $('#flags').innerHTML = flags.map(function(f){ return '⚠ ' + esc(f); }).join('<br>');
    $('.slipbar b').textContent = ls.length + ' leg' + (ls.length>1?'s':'') + ' · FD ' + decToAm(bookDec) + ' · fair ' + toAm(fair);
    fdButton(ls); dkButton(ls); hrButton(ls); bookNote(ls); syncTarget(ls, bookDec);
    save(); if (typeof renderSaved === 'function') renderSaved();
  }
  function bookRow(ls, fdDec){ var dk = bookParlay(ls, 'dk'), hr = bookParlay(ls, 'hr'); if (dk == null && hr == null) return '';
    var rows = [['FanDuel', fdDec]]; if (dk != null) rows.push(['DraftKings', dk]); if (hr != null) rows.push(['Hard Rock', hr]); var best = rows.reduce(function(b, r){ return r[1] > b[1] ? r : b; });
    return '<div class="wide books3"><small>Same slip at each book (legs multiplied; SGP quotes differ)</small>' + rows.map(function(r){ var sub = (r[0] === 'DraftKings' && bookSubbed(ls, 'dk')) || (r[0] === 'Hard Rock' && bookSubbed(ls, 'hr')); return '<span class="' + (r[0] === best[0] ? 'best' : '') + '">' + r[0] + ' <b>' + (sub ? '≈' : '') + decToAm(r[1]) + '</b></span>'; }).join('') + (dk == null && ls.length ? '<i>DraftKings: not every leg priced</i>' : '') + (bookSubbed(ls, 'dk') || bookSubbed(ls, 'hr') ? '<i>≈ uses that book\'s nearest line for a leg it doesn\'t post</i>' : '') + '</div>'; }
  function dkButton(ls){ var a = $('#senddk'); if(!a) return; var url = ls.length ? dkUrl(ls.filter(function(l){ return !started(l.g); })) : null; if (!url || ls.some(function(l){ return started(l.g); })){ a.style.display = ls.length && ls.some(function(l){ return bookPick(l, 'dk'); }) ? '' : 'none'; a.setAttribute('aria-disabled', 'true'); a.href = '#'; a.title = 'DraftKings does not price every leg in this slip'; return; } a.style.display = ''; a.removeAttribute('aria-disabled'); a.href = url; a.title = 'Opens DraftKings with these ' + ls.length + ' legs on the betslip'; }
  function hrButton(ls){ var a = $('#sendhr'); if(!a) return; var url = ls.length && !ls.some(function(l){ return started(l.g); }) ? hrUrl(ls) : null; if (!url){ a.style.display = ls.length && ls.some(function(l){ return bookPick(l, 'hr'); }) ? '' : 'none'; a.setAttribute('aria-disabled', 'true'); a.href = '#'; a.title = 'Hard Rock does not price every leg in this slip'; return; } a.style.display = ''; a.removeAttribute('aria-disabled'); a.href = url; a.title = 'Opens Hard Rock Bet with these ' + ls.length + ' legs on the betslip'; }
  function fdUrl(ls){
    var ok = ls.filter(function(l){ return l.fd && l.fd.m && l.fd.s && !started(l.g); });
    if(!ok.length) return null;
    if(ok.length === 1 && ok[0].fd.u) return ok[0].fd.u;
    return 'https://sportsbook.fanduel.com/addToBetslip?' + ok.map(function(l, i){ return 'marketId[' + i + ']=' + encodeURIComponent(l.fd.m) + '&selectionId[' + i + ']=' + encodeURIComponent(l.fd.s); }).join('&');
  }
  function fdButton(ls){
    var a = $('#sendfd'), note = $('#fdnote'); if(!a) return;
    var missing = ls.filter(function(l){ return !(l.fd && l.fd.m && l.fd.s); });
    var url = fdUrl(ls);
    if(!D.nlink){ a.style.display = 'none'; note.textContent = ''; return; }
    a.style.display = '';
    if(!url){ a.setAttribute('aria-disabled', 'true'); a.href = '#'; note.textContent = ls.length ? 'FanDuel IDs are not available for these legs yet.' : ''; return; }
    a.removeAttribute('aria-disabled'); a.href = url;
    note.textContent = 'Opens the FanDuel app or site with ' + (ls.length - missing.length) + ' of ' + ls.length + ' leg' + (ls.length>1?'s':'') + ' in your betslip at FanDuel\'s current price' + (missing.length ? ' (' + missing.map(function(l){ return l.pl; }).join(', ') + ' not linkable — add by hand)' : '') + '. Set your stake there.';
  }
  // ---- target-price fader: choose one rung per ladder so the slip's FanDuel price lands near the target ----
  var TGT = {min: 1, max: 1, busy: false};
  function slipGroups(){
    var ls = slipLegs(); return ls.map(function(l){ var g = ladderOf(l); if(!(g && g.length > 1 && l.m !== 'Anytime TD')) return [l];
      var c = st.clean ? g.filter(function(x){ return !x.w || sel[x.i]; }) : g; return c.length > 1 ? c : g; });
  }
  function priceRange(){
    var gs = slipGroups(); var lo = 1, hi = 1;
    gs.forEach(function(g){ var ds = g.map(function(l){ return dec(l.o); }); lo *= Math.min.apply(null, ds); hi *= Math.max.apply(null, ds); });
    return [lo, hi];
  }
  function sliderToDec(v){ return Math.exp(Math.log(TGT.min) + (v/1000) * (Math.log(TGT.max) - Math.log(TGT.min))); }
  function decToSlider(d){ return Math.round(1000 * (Math.log(d) - Math.log(TGT.min)) / Math.max(1e-9, Math.log(TGT.max) - Math.log(TGT.min))); }
  function retarget(targetDec){
    var gs = slipGroups(); if(!gs.length) return;
    // enumerate (ladders capped at 8 rungs; slip rarely > 6 legs): closest in log-price wins, within 8% prefer the best edge
    var best = null, lt = Math.log(targetDec);
    var cap = gs.map(function(g){ return g.slice(0, 8); });
    (function walk(i, chosen, ld, ev){
      if(i === cap.length){
        var dist = Math.abs(ld - lt);
        var score = (dist <= 0.08 ? 0 : dist) * 10 - ev;   // inside the band: pure edge; outside: distance dominates
        if(!best || score < best.score) best = {score: score, chosen: chosen.slice()};
        return;
      }
      cap[i].forEach(function(l){ chosen.push(l); walk(i+1, chosen, ld + Math.log(dec(l.o)), ev + (l.e || 0)); chosen.pop(); });
    })(0, [], 0, 0);
    if(!best) return;
    sel = {}; best.chosen.forEach(function(l){ sel[l.i] = true; var g = ladderOf(l); if(g && g.length > 1) pick[l.pl + '|' + l.m] = g.indexOf(l); });
    TGT.busy = true; renderList(); renderSlip(); TGT.busy = false;
  }
  function syncTarget(ls, bookDec){
    var box = $('#tgt'); if(!box) return;
    var fadeable = ls.some(function(l){ var g = ladderOf(l); return g && g.length > 1 && l.m !== 'Anytime TD'; });
    if(!ls.length || !fadeable){ box.hidden = true; return; }
    box.hidden = false; var r = priceRange(); TGT.min = r[0]; TGT.max = r[1];
    $('#tgtMin').textContent = 'safest ' + decToAm(TGT.min); $('#tgtMax').textContent = 'longest ' + decToAm(TGT.max);
    $('#tgtVal').textContent = decToAm(bookDec);
    if(!TGT.busy) $('#tgtRange').value = decToSlider(bookDec);
  }
  // owner 10/29 ("everything needs to be way more fluid"): + Add / In slip no longer rebuilds the whole list (80 cards of innerHTML per tap,
  // which dropped the scroll position and stalled the tap on phones). syncSel flips just the buttons for that leg wherever it is on the page.
  function syncSel(i){ var on = !!sel[i], lab = on ? 'In slip \u2713' : '+ Add';
    $$('[data-i="' + i + '"]').forEach(function(el){
      if(el.classList.contains('glb')){ el.classList.toggle('in', on); return; }
      $$('button', el).forEach(function(b){ if(b.closest('[data-i]') !== el || b.disabled) return; var t = b.textContent.trim(); if(t === '+ Add' || t.indexOf('In slip') === 0){ b.classList.toggle('in', on); b.textContent = lab; } });
    }); }
  function toggle(i){ if(sel[i]) delete sel[i]; else { if(started(legs[i].g)) return; sel[i] = true; } syncSel(i); renderSlip(); }
  // ---- quick builds ----
  function pickLegs(cands, n, opts){
    var used = {}, usedG = {}, out = [];
    cands.forEach(function(l){ if(out.length >= n) return; if(used[l.pl]) return; if(opts.distinctGames && usedG[l.g]) return;
      // game lines: at most one margin leg (ML or spread) and one total leg per game - two of the same kind are the same bet twice or can't both hit
      if(isGL(l) && out.some(function(x){ return isGL(x) && x.g === l.g && x.gl.k === l.gl.k; })) return;
      used[l.pl] = 1; usedG[l.g] = 1; out.push(l); });
    return out;
  }
  function quick(kind){
    var pool = legs.filter(function(l){ return !l.w && !l.alt && l.gd.indexOf('CONFIRMED') !== 0 && !started(l.g) && (st.game === 'all' || l.g === st.game); });
    var bestOf = {}; pool.forEach(function(l){ var k = l.pl + '|' + l.m; if(!bestOf[k] || l.e > bestOf[k].e) bestOf[k] = l; }); pool = Object.keys(bestOf).map(function(k){ return bestOf[k]; });
    var picks = [];
    if(kind === 'anchor'){ picks = pickLegs(pool.filter(function(l){ return l.o <= -130 && l.e >= -0.005; }).sort(function(a,b){ return b.p - a.p; }), 3, {distinctGames: st.game === 'all'}); }
    if(kind === 'value'){ picks = pickLegs(pool.filter(function(l){ return l.o > -250 && l.o < 250 && l.e >= 0.015; }).sort(function(a,b){ return b.e - a.e; }), 4, {distinctGames: st.game === 'all'}); }
    if(kind === 'moon'){ picks = pickLegs(pool.filter(function(l){ return l.o >= 150 && l.e >= 0; }).sort(function(a,b){ return b.e - a.e; }), 5, {distinctGames: st.game === 'all'}); }
    sel = {}; pick = {}; picks.forEach(function(l){ sel[l.i] = true; }); renderList(); renderSlip();
    if(window.innerWidth <= 900) $('.slipwrap').classList.add('open');
  }
  // ---- "Build me a +N" (owner 10/26): the most likely slip near a target price ----
  // Pool: open games only, not confirmed out, one rung per player|market kept per search; optional clean-only / soft-matchup / leave-out.
  // Scope: the game picked in the filters (same-game parlay), else the whole slate with one leg per game.
  // Search: beam over legs ranked by model %, priced fast (legs multiplied), then the finalists are re-priced with the slip's own
  // correlation model (joint()) - model % from the model's probabilities, the FanDuel price from FanDuel's implied probabilities with
  // the same correlations (same-game prices are an ESTIMATE: FanDuel's SGP engine prices correlation its own way and keeps more hold on
  // long slips; owner quotes 10/25-26 came in 0.45-0.95x of this estimate). Ranked by model %; shows the top 3.
  function oddsIn(t){ var v = parseFloat(String(t).replace(/[^0-9.+-]/g, '')); if(!v || Math.abs(v) < 100) return null; return v > 0 ? 1 + v/100 : 1 + 100/(-v); }
  function withP(ls, key){ return ls.map(function(l){ var c = Object.create(l); c.p = l[key]; return c; }); }
  function genRun(){
    var T = oddsIn($('#genT').value); var out = $('#genOut');
    if(!T){ out.innerHTML = '<p class="note">Type a price like +500.</p>'; return; }
    var N = +$('#genN').value, clean = $('#genClean').checked, soft = $('#genSoft').checked, green = $('#genGreen') && $('#genGreen').checked;
    var xs = $('#genX').value.toLowerCase().split(/[,;]+/).map(function(x){ return x.trim(); }).filter(Boolean);
    var one = st.game !== 'all';
    var pool = legs.filter(function(l){ return !started(l.g) && l.gd.indexOf('CONFIRMED') !== 0 && (!one || l.g === st.game) && l.p >= 0.18 && l.o >= -800 && l.o <= 1500 && l.m !== 'First TD'
      && (!clean || !l.w) && (!soft || isSoft(l)) && (!green || isGreen(l)) && !xs.some(function(x){ return l.pl.toLowerCase().indexOf(x) >= 0; }) && l.e >= -0.04; });
    pool.sort(function(a, b){ return b.p - a.p; }); pool = pool.slice(0, one ? 80 : 160);
    if(pool.length < 2){ out.innerHTML = '<p class="note">Not enough open legs with these settings.</p>'; return; }
    var hiMul = one ? 2.6 : 1.25, loMul = one ? 0.9 : 0.8;
    var beam = [{ls: [], p: 1, d: 1}], fin = [], seen = {};
    function ok(ls, l){ for(var i = 0; i < ls.length; i++){ var x = ls[i]; if(x.pl === l.pl) return false; if(!one && x.g === l.g) return false;
        if(isGL(l) && isGL(x) && x.g === l.g && x.gl.k === l.gl.k) return false; } return true; }
    for(var step = 0; step < N; step++){
      var next = [];
      beam.forEach(function(b){ pool.forEach(function(l){ if(!ok(b.ls, l)) return; var d = b.d * dec(l.o); if(d > T * hiMul) return;
        var ls = b.ls.concat([l]); var key = ls.map(function(x){ return x.i; }).sort().join(','); if(seen[key]) return; seen[key] = 1;
        var st2 = {ls: ls, p: b.p * l.p, d: d}; next.push(st2); if(ls.length >= 2 && d >= T * loMul) fin.push(st2); }); });
      // keep two kinds of partial slips: the most likely ones, and the ones buying the most price per unit of probability (log p / log price),
      // so long targets (+5000) and whole-slate searches still reach the price
      var eff = function(x){ return Math.log(x.p) / Math.max(1e-6, Math.log(x.d)); };
      var byP = next.slice().sort(function(a, b){ return b.p - a.p; }).slice(0, 40), byE = next.slice().sort(function(a, b){ return eff(b) - eff(a); }).slice(0, 80);
      var mk = {}; beam = []; byP.concat(byE).forEach(function(x){ var k = x.ls.map(function(l){ return l.i; }).sort().join(','); if(!mk[k]){ mk[k] = 1; beam.push(x); } });
      if(!beam.length) break;
    }
    if(!fin.length){ out.innerHTML = '<p class="note">Nothing lands near ' + decToAm(T) + ' with these settings - try more legs or a different price.</p>'; return; }
    fin.sort(function(a, b){ return b.p - a.p; }); fin = fin.slice(0, 40);
    var scored = fin.map(function(f){ var pm = joint(f.ls), pb = joint(withP(f.ls, 'bk')); var same = f.ls.some(function(l, i){ return f.ls.some(function(m, j){ return j !== i && m.g === l.g; }); });
      var est = same ? Math.max(1.01, 0.85 / Math.max(pb, 1e-6) + 0.15) : f.d; /* ~15% SGP hold, from the owner's 10/25-26 FanDuel quotes */ return {ls: f.ls, pm: pm, est: est, same: same}; })
      .filter(function(x){ return x.est >= T * 0.8 && x.est <= T * 1.3; });
    scored.sort(function(a, b){ return b.pm - a.pm; });
    var pickd = [], used = {};
    scored.forEach(function(x){ if(pickd.length >= 3) return; var sig = x.ls.map(function(l){ return l.pl; }).sort().join('|'); if(used[sig]) return; used[sig] = 1; pickd.push(x); });
    if(!pickd.length){ out.innerHTML = '<p class="note">Nothing lands near ' + decToAm(T) + ' once same-game correlation is priced in - try more legs.</p>'; return; }
    window.__GEN = pickd;
    out.innerHTML = pickd.map(function(x, k){ return '<div class="sug"><div class="sh"><span>' + x.ls.length + ' legs · model ' + (x.pm < 0.1 ? (x.pm*100).toFixed(1) + '%' : pc(x.pm)) + '</span><b>' + (x.same ? '≈' : '') + decToAm(x.est) + '</b></div><ul>' +
      x.ls.map(function(l){ return '<li>' + esc(legText(l)) + ' <small>' + am(l.o) + ' · ' + pc(l.p) + (l.dr && l.dr[0] != null ? ' · vs ' + esc(l.opp) + ' #' + l.dr[0] : '') + '</small></li>'; }).join('') +
      '</ul><button type="button" data-k="' + k + '">Load into my slip</button> <small class="note">fair ' + toAm(x.pm) + (x.same ? ' · same-game price is an estimate - check FanDuel\'s quote' : '') + '</small></div>'; }).join('');
  }
  $('#genGo').addEventListener('click', genRun);
  $$('#gen .presets button').forEach(function(b){ b.addEventListener('click', function(){ $('#genT').value = b.dataset.t; genRun(); }); });
  $('#genOut').addEventListener('click', function(ev){ var b = ev.target.closest('button[data-k]'); if(!b) return; var x = (window.__GEN || [])[+b.dataset.k]; if(!x) return;
    sel = {}; pick = {}; x.ls.forEach(function(l){ sel[l.i] = true; }); save(); renderList(); renderSlip(); if(window.innerWidth <= 900) $('.slipwrap').classList.add('open'); });
  function genScope(){ var gv = $('#fGame').value, g = gv && gv !== 'all' ? games[gv] : null; $('#genScope').textContent = g ? 'Same-game: ' + g.a + ' · ' + g.b + ' (game picked in the filters)' : 'Whole slate, one leg per game - pick a game in the filters for a same-game parlay'; }
  genScope(); $('#fGame').addEventListener('change', genScope);
  // ---- wire up ----
  var gsel = $('#fGame'); gorder.forEach(function(gid){ if(started(gid)) return; var g = games[gid]; var o = document.createElement('option'); o.value = gid; o.textContent = g.a + ' · ' + g.b + '  ' + g.kick; gsel.appendChild(o); });
  $('#fGame').addEventListener('change', function(){ st.game = this.value; st.limit = 80; renderList(); });
  $('#fMarket').addEventListener('change', function(){ st.market = this.value; st.limit = 80; renderList(); });
  $('#fPos').addEventListener('change', function(){ st.pos = this.value; st.limit = 80; renderList(); });
  $('#fSort').addEventListener('change', function(){ st.sort = this.value; renderList(); });
  $('#fClean').addEventListener('change', function(){ st.clean = this.checked; renderList(); });
  $('#fSoft').addEventListener('change', function(){ st.soft = this.checked; renderList(); });
  $('#fGreen').addEventListener('change', function(){ st.green = this.checked; renderList(); });
  $('#fTier').addEventListener('change', function(){ st.tier = this.checked; renderList(); });
  if(st.tier){ $('#fTier').checked = true; setTimeout(function(){ setView('list'); }, 0); }   // /build/?best=1 opens the leg list on the Model's Best tier
  $('#fFloor').addEventListener('change', function(){ st.floor = this.checked; if(st.floor){ st.sort = 'model'; $('#fSort').value = 'model'; } renderList(); });
  $('#fSnaps').addEventListener('change', function(){ st.snaps = parseFloat(this.value) || 0; st.limit = 80; renderList(); });
  $('#fBest').addEventListener('change', function(){ st.best = this.checked; renderList(); });
  (function(){ var qt = null; $('#fQ').addEventListener('input', function(){ var v = this.value; clearTimeout(qt); qt = setTimeout(function(){ st.q = v; st.limit = 80; renderList(); }, 140); }); })();   // owner 10/29: one render per pause in typing, not per keystroke
  $$('#fOdds button').forEach(function(b){ b.addEventListener('click', function(){ $$('#fOdds button').forEach(function(x){ x.classList.remove('on'); }); b.classList.add('on'); st.odds = b.dataset.v; st.limit = 80; renderList(); }); });
  // ---------------- player cards (owner 10/28): one card per player, every prop in its own box ----------------
  // A box shows one market: a slider over FanDuel's ladder that starts at the main line (the rung whose under FanDuel posts,
  // else the rung priced nearest -110), an Over / Under switch (FanDuel prices unders on the main line only, so Under locks the
  // slider there), the last-5 dots and the matchup rank underneath, then the prices, model %, book % and edge with + Add.
  // The TD box is a switch: Anytime / First (/ 2+ when FanDuel posts it). BOX[player|market] = {i: rung index, side: 'o'|'u'}.
  var BOX = {}, OPENP = {}, UND = {};
  legs.forEach(function(l){ if(l.u) UND[l.pl + '|' + l.m.replace(/^Under /, '')] = l; });
  var TDM = ['Anytime TD', 'First TD', '2+ TD', '3+ TD'];
  var MORD = {QB: ['Passing Yards', 'Rushing Yards', 'Receiving Yards', 'Receptions', 'Longest Reception', 'Rush + Rec Yards'],
              RB: ['Rushing Yards', 'Rush + Rec Yards', 'Receiving Yards', 'Receptions', 'Longest Reception', 'Passing Yards'],
              WR: ['Receiving Yards', 'Receptions', 'Longest Reception', 'Rushing Yards', 'Rush + Rec Yards', 'Passing Yards'],
              TE: ['Receiving Yards', 'Receptions', 'Longest Reception', 'Rushing Yards', 'Rush + Rec Yards', 'Passing Yards']};
  function ladder(pl, m){ return (GROUPS[pl + '|' + m] || []).filter(function(x){ return !x.u; }); }
  function mainIdx(pl, m){ var g = ladder(pl, m); if(!g.length) return 0; var u = UND[pl + '|' + m];
    if(u){ var want = Math.floor(u.ln) + 1; for(var i = 0; i < g.length; i++) if(Math.round(g[i].ln) === want) return i; }
    var best = 0, bd = 1e9; g.forEach(function(x, i){ var d = Math.abs((x.o == null ? 9999 : x.o) + 110); if(d < bd){ bd = d; best = i; } }); return best; }
  function overTxt(l){ return 'Over ' + (Math.round(l.ln) - 0.5); }
  function boxLeg(pl, m){ var s = BOX[pl + '|' + m]; var g = ladder(pl, m); if(!g.length) return null;
    if(s && s.side === 'u' && UND[pl + '|' + m]) return UND[pl + '|' + m];
    var i = s && s.i != null ? Math.max(0, Math.min(g.length - 1, s.i)) : mainIdx(pl, m); return g[i]; }
  function posMatch(l){ var pr = (D.posr || {})[l.opp]; var r = pr && pr[l.pos]; var oq = (D.osr || {})[l.tm]; var o = oq && oq[l.pos];
    var hl = {QB: 'pass yds', RB: 'rush yds', WR: 'rec yds', TE: 'rec yds'}[l.pos] || '';
    var pill = mupill({tm: l.tm, opp: l.opp, or: o, dr: r}); return pill ? '<span class="mul">' + l.pos + ' ' + hl + '</span>' + pill : ''; }
  function pricesHtml(l){ var rows = [[l.src === 'cons' ? 'Mkt' : 'FD', l.o]]; if(l.bks && l.bks.dk && l.bks.dk.o != null) rows.push(['DK', l.bks.dk.o]); if(l.bks && l.bks.hr && l.bks.hr.o != null) rows.push(['HR', l.bks.hr.o]);
    var best = rows.reduce(function(b, r){ return dec(r[1]) > dec(b[1]) ? r : b; });
    return rows.map(function(r){ return '<span class="' + (rows.length > 1 && r[0] === best[0] ? 'best' : '') + '"><small>' + r[0] + '</small>' + am(r[1]) + '</span>'; }).join(''); }
  function addBtn(l){ return started(l.g) && !sel[l.i] ? '<button type="button" class="add lockd" disabled>Started</button>' : '<button type="button" class="add' + (sel[l.i] ? ' in' : '') + '">' + (sel[l.i] ? 'In slip ✓' : '+ Add') + '</button>'; }
  function boxBody(l){   // the parts that change with the slider / switch
    return '<div class="pbm">' + l5(l) + mupill(l) + (l.proj != null && !isTD(l) ? '<small class="proj">proj ' + l.proj + '</small>' : '') + '</div>' +
      '<div class="pbp"><span class="pbk">' + pricesHtml(l) + '</span><span class="pbn"><b>' + pc(l.p) + '</b><small>model</small></span><span class="pbn"><b>' + pc(l.bk) + '</b><small>book</small></span><span class="pbn"><b class="e ' + (l.e >= 0 ? 'up' : 'dn') + '">' + (l.e >= 0 ? '+' : '') + (l.e*100).toFixed(1) + '</b><small>edge</small></span>' + addBtn(l) + '</div>' + tierChip(l);
  }
  function statBox(pl, m, pos){
    var g = ladder(pl, m); if(!g.length) return ''; var l = boxLeg(pl, m); var s = BOX[pl + '|' + m] || {}; var u = UND[pl + '|' + m]; var under = s.side === 'u' && u;
    var idx = under ? mainIdx(pl, m) : g.indexOf(l);
    return '<div class="pb ar" data-i="' + l.i + '" data-pl="' + esc(pl) + '" data-m="' + esc(m) + '">' +
      '<div class="pbh"><span class="mkbtn" role="button" tabindex="0" title="Recent games and matchup">' + esc(m) + '</span>' +
      '<span class="seg"><button type="button" data-side="o" class="' + (under ? '' : 'on') + '">Over</button><button type="button" data-side="u" class="' + (under ? 'on' : '') + '"' + (u ? '' : ' disabled title="FanDuel has no under posted on this line yet"') + '>Under</button></span></div>' +
      '<div class="pbl"><b class="pbline">' + (under ? 'Under ' + u.ln : overTxt(l)) + '</b>' + (g.length > 1 ? '<input type="range" class="rng" min="0" max="' + (g.length - 1) + '" value="' + idx + '" step="1"' + (under ? ' disabled' : '') + ' aria-label="line">' : '') +
      '<small class="pbnote">' + (under ? 'FanDuel prices unders on the main line only' : (idx === mainIdx(pl, m) ? 'main line' : 'alt line')) + '</small></div>' +
      '<div class="pbb">' + boxBody(l) + '</div>' + (openHist[pl + '|' + m] ? histBlock(l) : '') + '</div>';
  }
  function tdBox(pl, pos){
    var have = TDM.filter(function(m){ return (GROUPS[pl + '|' + m] || []).length; }); if(!have.length) return '';
    var s = BOX[pl + '|TD'] || {}; var m = have.indexOf(s.m) >= 0 ? s.m : have[0]; var l = GROUPS[pl + '|' + m][0];
    return '<div class="pb ar td" data-i="' + l.i + '" data-pl="' + esc(pl) + '" data-m="TD">' +
      '<div class="pbh"><span class="mkbtn" role="button" tabindex="0" title="Recent games and matchup">Touchdown</span><span class="seg">' + have.map(function(x){ return '<button type="button" data-td="' + esc(x) + '" class="' + (x === m ? 'on' : '') + '">' + (x === 'Anytime TD' ? 'Anytime' : x === 'First TD' ? 'First' : x.replace(' TD', '')) + '</button>'; }).join('') + '</span></div>' +
      '<div class="pbb">' + boxBody(l) + '</div>' + (openHist[pl + '|' + m] ? histBlock(l) : '') + '</div>';
  }
  function card(pl, gid, markets, pos){
    var any = legs.filter(function(x){ return x.pl === pl && x.g === gid && !x.gl; })[0]; if(!any) return '';
    var g = games[gid]; var key = pl + '|' + gid; var open = !!OPENP[key];
    var all = (MORD[pos] || MORD.WR).filter(function(m){ return ladder(pl, m).length; }); var hasTD = TDM.some(function(m){ return (GROUPS[pl + '|' + m] || []).length; });
    var shownM = markets.slice(); if(open){ if(hasTD && shownM.indexOf('TD') < 0) shownM.push('TD'); all.forEach(function(m){ if(shownM.indexOf(m) < 0) shownM.push(m); }); }
    var nAll = all.length + (hasTD ? 1 : 0), more = nAll - shownM.length;
    var boxes = shownM.map(function(m){ return m === 'TD' ? tdBox(pl, pos) : statBox(pl, m, pos); }).join('');
    return '<li class="pc' + (open ? ' open' : '') + '" data-pk="' + esc(key) + '" data-i="' + any.i + '">' +
      '<div class="pch"><span class="pz">' + pos + '</span><div class="pcn"><b><a class="pname" href="/player/' + plSlug(pl) + '/" title="' + esc(pl) + ': lines at every book, hit rates, game log">' + esc(pl) + '</a>' + flagMark(any) + (any.gd ? ' <span class="gdo">' + esc(any.gd) + '</span>' : '') + '</b>' +
      '<span class="pcg">' + posMatch(any) + '<small>' + any.tm + ' vs ' + any.opp + ' · ' + esc(g.kick) + ' · <a class="pplink" href="https://betsweep.co/player/' + plSlug(pl) + '/" title="His page: lines at every book, hit rates, snap share, game log">player page</a></small>' + snChip(any) + '</span></div>' +
      (nAll > 1 ? '<button type="button" class="pcall" aria-expanded="' + open + '" title="Every prop for this player">' + (open ? 'Less <i class="car">▴</i>' : 'All props' + (more ? ' (' + nAll + ')' : '') + ' <i class="car">▾</i>') + '</button>' : '') + '</div>' +
      whyBlock(any) + '<div class="pcb">' + boxes + '</div></li>';
  }
  // owner 10/30: /player/<slug>/ pages (build_players.py; same slug rule as plydata.slugify - dots dropped, Jr/Sr/II.. suffix dropped)
  function plSlug(n){ return String(n).replace(/\./g, '').trim().replace(/\s+(jr|sr|ii|iii|iv|v)$/i, '').replace(/\s+/g, ' ').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''); }
  function cards(list){   // list = legs in display order -> one card per player+game, boxes for the markets that are in the list (their rung as the box default)
    var out = [], seen = {};
    list.forEach(function(l){
      if(l.gl){ out.push({html: row(l)}); return; }
      var key = l.pl + '|' + l.g, m = TDM.indexOf(l.m) >= 0 ? 'TD' : l.m.replace(/^Under /, '');
      var c = seen[key]; if(!c){ c = seen[key] = {pl: l.pl, g: l.g, pos: l.pos, ms: []}; out.push(c); }
      if(c.ms.indexOf(m) < 0){ c.ms.push(m);
        var bk = l.pl + '|' + m; if(!BOX[bk] || BOX[bk].auto){ if(m === 'TD') BOX[bk] = {m: l.m, auto: true}; else if(l.u) BOX[bk] = {side: 'u', i: mainIdx(l.pl, m), auto: true}; else BOX[bk] = {side: 'o', i: ladder(l.pl, m).indexOf(l), auto: true}; } }
    });
    return out.map(function(c){ return c.html || card(c.pl, c.g, c.ms, c.pos); }).join('');
  }
  // in-place updates: slider, Over/Under, TD switch, All props
  function refreshBox(box){ var pl = box.dataset.pl, m = box.dataset.m, l;
    if(m === 'TD'){ var s = BOX[pl + '|TD'] || {}; var mm = s.m || 'Anytime TD'; l = GROUPS[pl + '|' + mm][0]; box.querySelectorAll('.seg button').forEach(function(b){ b.classList.toggle('on', b.dataset.td === mm); }); }
    else { l = boxLeg(pl, m); var u = UND[pl + '|' + m], st2 = BOX[pl + '|' + m] || {}, under = st2.side === 'u' && u; var g = ladder(pl, m);
      box.querySelector('.pbline').textContent = under ? 'Under ' + u.ln : overTxt(l);
      var r = box.querySelector('.rng'); if(r){ r.disabled = !!under; if(under) r.value = mainIdx(pl, m); else r.value = g.indexOf(l); }
      var nt = box.querySelector('.pbnote'); if(nt) nt.textContent = under ? 'FanDuel prices unders on the main line only' : (g.indexOf(l) === mainIdx(pl, m) ? 'main line' : 'alt line');
      box.querySelectorAll('.seg button').forEach(function(b){ b.classList.toggle('on', (b.dataset.side === 'u') === !!under); }); }
    box.dataset.i = l.i; box.querySelector('.pbb').innerHTML = boxBody(l); var h = box.querySelector('.hist'); if(h) h.remove(); }
  function cardsInput(ev){ var r = ev.target.closest('.rng'); if(!r) return; var box = r.closest('.pb'); var k = box.dataset.pl + '|' + box.dataset.m; BOX[k] = {side: 'o', i: +r.value}; refreshBox(box); }
  function cardsClick(ev){
    var sb = ev.target.closest('.seg button'); if(sb){ if(sb.disabled) return true; var box = sb.closest('.pb'); var pl = box.dataset.pl, m = box.dataset.m;
      if(sb.dataset.td){ BOX[pl + '|TD'] = {m: sb.dataset.td}; } else { var cur = BOX[pl + '|' + m] || {i: mainIdx(pl, m)}; BOX[pl + '|' + m] = {side: sb.dataset.side, i: sb.dataset.side === 'u' ? mainIdx(pl, m) : (cur.i != null ? cur.i : mainIdx(pl, m))}; }
      refreshBox(box); return true; }
    var pa = ev.target.closest('.pcall'); if(pa){ var key = pa.closest('.pc').dataset.pk; if(OPENP[key]) delete OPENP[key]; else OPENP[key] = true; renderList(); return true; }
    return false;
  }
  $('#legs').addEventListener('input', cardsInput); $('#games').addEventListener('input', cardsInput);
  function legsClick(ev){
    if(cardsClick(ev)) return;
    var gb = ev.target.closest('.glb[data-i]'); if(gb){ if(!gb.disabled) toggle(+gb.dataset.i); return; }
    var ab = ev.target.closest('.altbtn'); if(ab){ var ag = ab.dataset.g; if(openAlt[ag]) delete openAlt[ag]; else openAlt[ag] = true; renderGames(); return; }
    var gh = ev.target.closest('.ghd'); if(gh){ var gid = gh.dataset.g; if(openG[gid]) delete openG[gid]; else openG[gid] = true; renderGames(); if(openG[gid]) $('#g-' + gid).scrollIntoView({block:'start', behavior:'smooth'}); return; }
    var pn = ev.target.closest('.pn.cyc'); if(pn){ var ok = pn.dataset.orig; var li = pn.closest('.lg'); var cur = legs[+li.dataset.i];
      var orig = legs.filter(function(x){ return x.pl + '|' + x.m === ok; })[0]; if(!orig) return; var cl = cycleList(orig); var j = cl.findIndex(function(x){ return x.i === cur.i; }); var nx = cl[(j + 1) % cl.length];
      if(nx.i === orig.i) delete CYC[ok]; else CYC[ok] = nx.i; var html = row(orig); var tmp = document.createElement('ul'); tmp.innerHTML = html; li.replaceWith(tmp.firstElementChild); return; }
    var mb = ev.target.closest('.mkbtn, .l5'); if(mb){ var host = mb.closest('.ar') || mb.closest('.lg'); var lg = legs[+host.dataset.i]; var hk = lg.pl + '|' + lg.m; if(openHist[hk]) delete openHist[hk]; else openHist[hk] = true;
      if(host.classList.contains('pb')){ var hb = host.querySelector('.hist'); if(hb) hb.remove(); else host.insertAdjacentHTML('beforeend', histBlock(lg)); return; } renderList(); return; }
    var w = ev.target.closest('.wf'); if(w){ var host = w.closest('.ar') || w.closest('li'); var y = host && host.querySelector('.why'); if(y) y.hidden = !y.hidden; return; }
    var f = ev.target.closest('.lad button'); if(f){ fade(f.closest('.lad').dataset.k, +f.dataset.d, false); return; }
    var b = ev.target.closest('button'); if(!b || !(b.closest('.lg') || b.closest('.pc'))) return;
    var ar = b.closest('.ar'); toggle(+(ar ? ar.dataset.i : (b.closest('.lg') || b.closest('.pc')).dataset.i)); }
  $('#legs').addEventListener('click', legsClick); $('#games').addEventListener('click', legsClick);
  // live tickers update in place; the cards re-sort (full re-render) only when a game kicks off or goes final
  var sigOf = function(){ return gorder.map(function(gid){ return (started(gid) ? 's' : '') + (finished(gid) ? 'f' : ''); }).join(','); }, lastSig = sigOf();
  if(window.BSLive) window.BSLive.start(gorder.map(function(gid){ var g = games[gid]; return {gid: gid, a: g.a, b: g.b, ko: g.ko, fin: g.fin}; }), function(m){
    LV = m; var sig = sigOf();
    if(sig !== lastSig){ lastSig = sig; renderGames(); return; }
    gorder.forEach(function(gid){ var el = document.getElementById('tk-' + gid); if(!el) return; var h = window.BSLive.tickHtml(games[gid], LV[gid]); el.innerHTML = h; el.hidden = !h; el.classList.toggle('final', !!(LV[gid] && LV[gid].st === 'post')); });
  });
  $('#tabGames').addEventListener('click', function(){ setView('games'); });
  $('#tabSearch').addEventListener('click', function(){ setView(st.view === 'list' ? 'games' : 'list'); });
  $('#fReset').addEventListener('click', function(){ st.game = 'all'; st.market = 'all'; st.pos = 'all'; st.odds = 'all'; st.clean = false; st.floor = false; $('#fFloor').checked = false; st.soft = false; $('#fSoft').checked = false; st.green = false; $('#fGreen').checked = false; st.tier = false; $('#fTier').checked = false; st.snaps = 0; $('#fSnaps').value = '0'; st.best = true; st.q = ''; st.limit = 80;
    $('#fGame').value = 'all'; $('#fMarket').value = 'all'; $('#fPos').value = 'all'; $('#fQ').value = ''; $('#fClean').checked = false; $('#fBest').checked = true; $$('#fOdds button').forEach(function(x){ x.classList.toggle('on', x.dataset.v === 'all'); }); renderList(); });
  $('#more').addEventListener('click', function(){ st.limit += 80; renderList(); });
  $('#slipLegs').addEventListener('click', function(ev){
    var w = ev.target.closest('.wf'); if(w){ toggleWhy(w); return; }
    var f = ev.target.closest('.lad button'); if(f){ fade(f.closest('.lad').dataset.k, +f.dataset.d, true); return; }
    var b = ev.target.closest('.x'); if(b) toggle(+b.dataset.i); });
  $('#clear').addEventListener('click', function(){ sel = {}; renderList(); renderSlip(); });
  // ---- saved slips: the same bs_slips_w<W> list the Live page tracks and /me/ grades; here they are the comparison table ----
  var SLKEY = 'bs_slips_w' + D.week;
  function savedSlips(){ try{ var a = JSON.parse(localStorage.getItem(SLKEY)||'[]'); return Array.isArray(a) ? a.filter(function(s){ return s && s.id && Array.isArray(s.keys); }) : []; }catch(e){ return []; } }
  function writeSlips(a){ try{ localStorage.setItem(SLKEY, JSON.stringify(a)); }catch(e){} }
  function legsForKeys(ks){ return ks.map(function(k){ return KEYIDX[k] != null ? legs[KEYIDX[k]] : null; }); }
  function priceKeys(ks){ var ls = legsForKeys(ks).filter(Boolean); if (!ls.length) return null; var bls = bookLegs(ls); var bookDec = bls.reduce(function(a,l){ return a*dec(l.o); }, 1); return {ls: ls, n: ks.length, missing: ks.length - ls.length, bookDec: bookDec, fair: joint(ls), fd: fdUrl(ls)}; }
  function curKeys(){ return Object.keys(sel).map(function(i){ return legKey(legs[+i]); }).concat(extraKeys); }
  function sameSet(a, b){ if (a.length !== b.length) return false; var m = {}; a.forEach(function(k){ m[k] = 1; }); return b.every(function(k){ return m[k]; }); }
  // saved slips: legs fold into a drop-down under each row (owner 10/23: one long line was unreadable on a phone)
  var SLOPEN = {};
  function slLeg(k){ var q = String(k).split('|'), who = q[0], m = String(q[1]||''), ln = q[2];
      var what = (m==='Anytime TD'||m==='First TD'||m==='Either TD') ? m.replace('TD','touchdown').toLowerCase() : (m==='Moneyline'||m==='Spread'||m==='Total') ? m.toLowerCase() : ln + '+ ' + m.toLowerCase();
      return '<li><b>' + esc(who) + '</b><span>' + esc(what) + '</span></li>'; }
  function renderSaved(){ var box = $('#savedList'); if(!box) return; var all = savedSlips(), cur = curKeys();
    if(!all.length){ box.innerHTML = '<p class="none">Nothing saved yet. Build a slip, tap <b>Save slip</b>, build another - every saved slip lines up here with its FanDuel price, model chance and edge, and sends to FanDuel from this table whenever you are ready. Saved slips also show on <a href="/me/">My BetSweep</a>, graded after the games' + (window.bsAccount && window.bsAccount.user ? '' : ' (sign in and they follow you to every device)') + '.</p>'; return; }
    var rows = all.map(function(s){ var pr = priceKeys(s.keys); return {s: s, pr: pr}; }).sort(function(a,b){ var ea = a.pr ? a.pr.fair - 1/a.pr.bookDec : -9, eb = b.pr ? b.pr.fair - 1/b.pr.bookDec : -9; return eb - ea; });
    box.innerHTML = '<table><thead><tr><th>Slip</th><th class="r">FanDuel</th><th class="r">Model</th><th class="r">Edge</th><th class="r">$10 pays</th><th></th></tr></thead><tbody>' + rows.map(function(r){ var s = r.s, pr = r.pr, isCur = sameSet(s.keys, cur);
      var e = pr ? pr.fair - 1/pr.bookDec : null;
      return '<tr class="' + (isCur ? 'cur' : '') + '"><td class="nm"><b>' + esc(s.name || 'Slip') + (s.promo ? ' <small style="display:inline">· promoted</small>' : '') + '</b><button type="button" class="lgt' + (SLOPEN[s.id] ? ' on' : '') + '" data-tog="' + esc(s.id) + '" aria-expanded="' + (SLOPEN[s.id] ? 'true' : 'false') + '">' + s.keys.length + ' legs <i>▾</i></button>' + (pr && pr.missing ? '<small>' + pr.missing + ' no longer priced' + '</small>' : '') + '</td>'
        + '<td class="r">' + (pr ? decToAm(pr.bookDec) : (s.odds ? am(s.odds) : '—')) + '</td><td class="r">' + (pr ? pc(pr.fair) : '—') + '</td><td class="r e ' + (e!=null && e>=0 ? 'up' : 'dn') + '">' + (e!=null ? (e>=0?'+':'') + (e*100).toFixed(1) : '—') + '</td><td class="r">' + (pr ? '$' + (10*pr.bookDec).toFixed(2) : '—') + '</td>'
        + '<td class="ops">' + (pr && pr.fd ? '<a class="fd" href="' + esc(pr.fd) + '" target="_blank" rel="noopener">FD</a>' : (s.fd ? '<a class="fd" href="' + esc(s.fd) + '" target="_blank" rel="noopener">FD</a>' : '')) + (pr && pr.ls.length === s.keys.length && dkUrl(pr.ls) ? '<a class="fd dk" href="' + esc(dkUrl(pr.ls)) + '" target="_blank" rel="noopener">DK</a>' : '') + (pr && pr.ls.length === s.keys.length && hrUrl(pr.ls) ? '<a class="fd hr" href="' + esc(hrUrl(pr.ls)) + '" target="_blank" rel="noopener">HR</a>' : '') + '<button type="button" data-load="' + esc(s.id) + '">' + (isCur ? 'Loaded' : 'Load') + '</button><button type="button" class="del" data-del="' + esc(s.id) + '">×</button></td></tr>' + '<tr class="lgrow"' + (SLOPEN[s.id] ? '' : ' hidden') + '><td colspan="6"><ul class="sllegs">' + s.keys.map(slLeg).join('') + '</ul></td></tr>'; }).join('') + '</tbody></table>'; }
  $('#savesl').addEventListener('click', function(){ var ks = curKeys(); if(!ks.length){ $('#fdnote').textContent = 'Add a leg or two first.'; return; }
    var all = savedSlips(), dup = all.filter(function(s){ return sameSet(s.keys, ks); })[0]; if (dup){ $('#fdnote').textContent = 'Already saved as "' + (dup.name||'Slip') + '".'; renderSaved(); return; }
    var box = $('#savedList'); var pr = priceKeys(ks); var dflt = 'Slip ' + (all.length + 1) + (pr ? ' · ' + decToAm(pr.bookDec) : '');
    var nb = document.createElement('div'); nb.className = 'namebox'; nb.innerHTML = '<input type="text" value="' + esc(dflt) + '" aria-label="slip name" maxlength="60"><button type="button" class="pri">Save</button><button type="button" class="cx">Cancel</button>'; box.parentNode.insertBefore(nb, box);
    var inp = nb.querySelector('input'); inp.focus(); inp.select();
    function done(){ var name = inp.value.trim() || dflt; all.push({id: 'b' + Date.now().toString(36), name: name, keys: ks, odds: pr ? +decToAm(pr.bookDec).replace('+','') : null, stake: 1, fd: pr ? pr.fd : null, fair: pr ? Math.round(pr.fair*10000)/10000 : null, saved: Date.now()}); writeSlips(all); nb.remove(); renderSaved(); $('#fdnote').textContent = 'Saved. It is on My BetSweep too, graded after the games.'; }
    nb.querySelector('.pri').addEventListener('click', done); inp.addEventListener('keydown', function(e){ if(e.key==='Enter') done(); if(e.key==='Escape') nb.remove(); }); nb.querySelector('.cx').addEventListener('click', function(){ nb.remove(); }); });
  $('#savedList').addEventListener('click', function(e){ var b = e.target.closest('button'); if(!b) return;
    if (b.dataset.tog){ var id = b.dataset.tog, row = b.closest('tr').nextElementSibling; SLOPEN[id] = !SLOPEN[id]; if(row && row.classList.contains('lgrow')) row.hidden = !SLOPEN[id]; b.classList.toggle('on', !!SLOPEN[id]); b.setAttribute('aria-expanded', SLOPEN[id] ? 'true' : 'false'); return; }
    if (b.dataset.load){ var s = savedSlips().filter(function(x){ return x.id === b.dataset.load; })[0]; if(!s) return; sel = {}; extraKeys = []; s.keys.forEach(function(k){ if (k in KEYIDX) sel[KEYIDX[k]] = true; else extraKeys.push(k); }); renderList(); renderSlip(); window.scrollTo({top: $('#slipLegs').getBoundingClientRect().top + scrollY - 120, behavior: 'smooth'}); }
    if (b.dataset.del){ writeSlips(savedSlips().filter(function(x){ return x.id !== b.dataset.del; })); renderSaved(); } });
  document.addEventListener('bs-account', renderSaved);
  function slipText(){
    var ls = slipLegs(); if(!ls.length) return '';
    var bookDec = bookLegs(ls).reduce(function(a,l){ return a*dec(l.o); }, 1), fair = joint(ls);
    return 'BetSweep slip · Week ' + D.week + '\n' + ls.map(function(l){ return '• ' + legText(l) + ' (' + am(l.o) + ') — model ' + pc(l.p) + ' vs book ' + pc(l.bk); }).join('\n') + '\nFanDuel ' + decToAm(bookDec) + ' · model fair ' + toAm(fair) + ' (' + pc(fair) + ')\nbetsweep.co';
  }

  $('#copy').addEventListener('click', function(){
    var txt = slipText(); if(!txt) return;
    var done = function(ok){ $('#copy').textContent = ok ? 'Copied' : 'Copy failed'; setTimeout(function(){ $('#copy').textContent = 'Copy slip'; }, 1800); };
    if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(function(){ done(true); }, function(){ done(false); }); else done(false);
  });
  $$('.quick button').forEach(function(b){ b.addEventListener('click', function(){ quick(b.dataset.k); }); });
  (function(){ var t = null; var rng = $('#tgtRange');
    rng.addEventListener('input', function(){ $('#tgtVal').textContent = decToAm(sliderToDec(+rng.value)); clearTimeout(t); t = setTimeout(function(){ retarget(sliderToDec(+rng.value)); }, 120); });
  })();
  $('.slipbar').addEventListener('click', function(){ $('.slipwrap').classList.toggle('open'); });
  function toggleHelp(force){ var h = $('#help'); h.hidden = force === true ? false : !h.hidden; if(!h.hidden) h.scrollIntoView({block: 'nearest', behavior: 'smooth'}); }
  $('#helpbtn').addEventListener('click', function(){ toggleHelp(); });
  $('#legs').addEventListener('click', function(ev){ if(ev.target.closest('.edgel')) toggleHelp(true); }); $('#games').addEventListener('click', function(ev){ if(ev.target.closest('.edgel')) toggleHelp(true); });
  (function(){ var seen = false; try { seen = localStorage.getItem('bs_tip1') === '1'; } catch(e){}
    var t = $('#tip'); if(t && !seen) t.hidden = false;
    $('#tipok').addEventListener('click', function(){ t.hidden = true; try { localStorage.setItem('bs_tip1', '1'); } catch(e){} }); })();
  // ?p=Player Name (from a matchup-boards dropdown's 'All his legs'): open the search view filtered to him, every rung shown, then clear the query
  var JUMP = null; try { JUMP = new URLSearchParams(location.search).get('p'); } catch(e){}
  if(JUMP){
    st.q = JUMP; st.best = false; st.limit = 200; $('#fQ').value = JUMP; $('#fBest').checked = false;
    try { history.replaceState(null, '', location.pathname + location.hash); } catch(e){}
    setView('list'); renderSlip();
    var tgt = $('#filters'); if(tgt) setTimeout(function(){ tgt.scrollIntoView({block:'start'}); }, 50);
  } else { setView('games'); renderSlip(); }
  if(ADDED){
    var msg = ADDED.ok.length ? 'Added to your slip: ' + ADDED.ok.map(function(l){ return l.pl + ' ' + (l.m === 'Anytime TD' ? 'anytime TD' : l.m === 'First TD' ? 'first TD' : l.ms.toLowerCase() + ' ' + lnTxt(l)); }).join(', ') : '';
    if(ADDED.late.length) msg += (msg ? ' · ' : '') + 'Already kicked off, not added: ' + ADDED.late.map(function(l){ return l.pl; }).join(', ');
    if(ADDED.missing.length) msg += (msg ? ' · ' : '') + ADDED.missing.length + ' leg' + (ADDED.missing.length > 1 ? 's are' : ' is') + ' not on this board any more';
    if(msg){ var n = document.createElement('div'); n.className = 'addnote'; n.textContent = msg; document.body.appendChild(n); setTimeout(function(){ n.classList.add('out'); setTimeout(function(){ n.remove(); }, 400); }, 4200); }
    if(ADDED.ok.length && window.innerWidth <= 900) $('.slipwrap').classList.add('open');
  }
})();
"""

body = f'''<div class="bld">
 <section class="panel">
  <div class="tabs"><button type="button" id="tabGames" class="tab on">Games</button><button type="button" id="tabSearch" class="tab" aria-expanded="false" aria-controls="filters"><svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>Search &amp; filter<i class="car">▾</i></button><b id="count" hidden></b><button type="button" id="helpbtn" class="helpbtn" style="margin-left:auto">What do the numbers mean?</button></div>
  <div class="help" id="help" hidden>
   <dl>
    <div><dt>Model %</dt><dd>How often BetSweep expects this leg to hit: the model's history-adjusted hit rate for that line, blended half-and-half with what FanDuel's price implies. The blend is there because on the graded pre-kickoff legs the raw model ran overconfident where it disagreed with the price; the half-way number has scored better two weeks running.</dd></div>
    <div><dt>Book %</dt><dd>How often it <em>has</em> to hit for FanDuel's price to break even. −110 means 52.4%; +200 means 33.3%. The book builds its margin in here.</dd></div>
    <div><dt>Edge</dt><dd><b>Model % minus Book %</b>, in percentage points. +7.0 means the model thinks the leg hits 7 points more often than the price requires — you're being paid more than the risk deserves. Negative means FanDuel is charging more than the leg is worth. Rough guide: <b>+1 and up</b> is value, <b>+2.5 and up</b> is strong value, between −1 and +1 is a fair price, below −1 is a pass. Edge is the main sort because it's the number that makes money over time, not the hit rate on its own.</dd></div>
    <div><dt>Fair</dt><dd>The odds the model would set for the whole slip. If FanDuel's price is longer than fair, the parlay has edge; the "take it at … or better" line leaves a 5% cushion for line movement.</dd></div>
    <div><dt>EV per $1</dt><dd>Expected profit per dollar staked if the model is right: model hit chance × payout − 1. Positive is good; it is an average over many bets, not a promise on this one.</dd></div>
    <div><dt>Last 5 dots</dt><dd>Did he clear the selected line in each of his last five games, newest first. Tap for the full panel and what the defense has allowed.</dd></div>
    <div><dt>Game lines</dt><dd>The six buttons on each scorecard are FanDuel's moneyline, spread and total. The model prices them from its projected score, worked out under each game ending and mixed by the script odds, then pulled halfway toward FanDuel's no-vig price because the model's team scores have not been back-tested against closing lines yet. The small number is the edge in percentage points. "Mkt" means a consensus price from the schedule feed, not FanDuel's. A spread or total where model and market differ by 4+ points carries a risk flag.</dd></div>
    <div><dt>Live / Final</dt><dd>At kickoff a game's legs lock (you can still remove them from your slip) and the card shows LIVE with the score and last play; once it goes final it drops below the games still to come.</dd></div>
   </dl>
  </div>
  <div class="filters" id="filters" hidden>
   <input id="fQ" type="search" placeholder="Search player or team" autocomplete="off">
   <select id="fGame" aria-label="game"><option value="all">All games</option></select>
   <select id="fMarket" aria-label="market"><option value="all">All markets</option><option value="UNDERS">Unders</option><option>Anytime TD</option><option>First TD</option><option>Receiving Yards</option><option>Receptions</option><option>Rushing Yards</option><option>Rush + Rec Yards</option><option>Passing Yards</option><option>Longest Reception</option><option>Moneyline</option><option>Spread</option><option>Total</option></select>
   <select id="fPos" aria-label="position"><option value="all">All positions</option><option>QB</option><option>RB</option><option>WR</option><option>TE</option></select>
   <span class="seg" id="fOdds"><button type="button" class="on" data-v="all">Any odds</button><button type="button" data-v="anchor">Anchors ≤ −200</button><button type="button" data-v="mid">−200 to +200</button><button type="button" data-v="long">+200 and up</button></span>
   <select id="fSort" aria-label="sort"><option value="edge">Sort: edge</option><option value="model">Sort: model %</option><option value="odds">Sort: odds</option><option value="kick">Sort: kickoff</option></select>
   <label><input id="fClean" type="checkbox"> clean legs only (hide flagged)</label>
   <label title="Only the Model's Best tier: lines near even money where the model is 8+ pts off FanDuel (mostly unders), TDs the model likes, and 65%+ legs at a fair price"><input id="fTier" type="checkbox"> <b>Model's Best</b> only</label>
   <label title="Opponent ranks top 12 in allowing this stat to this position, both this season and over the last 3 weeks (#1 allows the most). Game lines have no matchup rank and drop out."><input id="fSoft" type="checkbox"> soft matchups only</label>
   <label title="His offense AND the opposing defense both green for this stat (both top 10), or offense middling (11-21) with the defense top 5. #1 = produces / allows the most. Unders flip it."><input id="fGreen" type="checkbox"> green matchups (off + def)</label>
   <label title="Primary roles only, line at 30–60% of the projection, −130 to −400, model not fading it, no role risk, no cold streak. Ranked by probability - the parlay-anchor strategy, not an edge hunt."><input id="fFloor" type="checkbox"> floor legs (anchors)</label>
   <select id="fSnaps" aria-label="minimum projected snap share" title="Hide legs whose projected offensive snap share (nflverse snaps, recency-weighted, redistributed for same-position absences and returners) is below the threshold. Legs with no snap projection (no 2026 snaps: fill-in starters, returners from 2025, game lines) stay visible under 'any' and are hidden under every threshold."><option value="0">Min snaps: any</option><option value="0.4">Min snaps: 40%</option><option value="0.55">Min snaps: 55%</option><option value="0.7">Min snaps: 70%</option></select>
   <label><input id="fBest" type="checkbox" checked> one box per player (his best line; the slider still reaches every line)</label>
   <button type="button" id="fReset" class="reset">Reset filters</button>
  </div>
  <div class="games" id="games"></div>
  <div class="tip" id="tip" hidden><b>How to dig in</b><span class="ex"><u>All props</u> opens every market for a player</span><span class="ex">Slide to change the line; Over / Under switches sides</span><span class="ex">Tap a stat or its dots <span class="l5"><i class="ok"></i><i class="no"></i><i class="ok"></i><i class="ok"></i><i class="no"></i></span> for his last 5 games and the defense's</span><button type="button" id="tipok">Got it</button></div>
  <ul class="legs" id="legs"></ul>
  <button type="button" class="more" id="more" style="background:none;border:0;cursor:pointer;width:100%;text-align:left"></button>
 </section>
 <aside class="slipwrap">
  <div class="slipbar" role="button" aria-label="open slip"><b>Your slip</b><span class="n">0</span></div>
  <section class="panel slip">
   <h2>Your slip <span class="n" style="margin-left:auto;background:var(--red);color:#fff;border-radius:99px;padding:1px 8px;font-size:12px"></span></h2>
   <details class="buildbox" id="buildBox"><summary><b>Build a slip for me</b><small>quick builds · pick a target price</small><i class="car">▾</i></summary>
   <div class="quick"><button type="button" data-k="anchor">Anchor 3</button><button type="button" data-k="value">Value 4</button><button type="button" data-k="moon">Moonshot 5</button><span class="note" style="padding:4px 0 0;flex-basis:100%">Quick builds use clean legs (player props and game lines), one per player, one per game when "All games" is selected. Edit freely.</span></div>
   <div class="gen" id="gen">
    <div class="grow"><b>Build me a</b><input id="genT" type="text" inputmode="numeric" value="+500" aria-label="target odds"><span class="presets"><button type="button" data-t="+150">+150</button><button type="button" data-t="+300">+300</button><button type="button" data-t="+500">+500</button><button type="button" data-t="+1000">+1000</button><button type="button" data-t="+5000">+5000</button></span></div>
    <div class="grow opts"><label><input id="genClean" type="checkbox" checked> clean legs</label><label><input id="genSoft" type="checkbox"> soft matchups</label><label title="Only legs with a green matchup on both sides (offense + defense)"><input id="genGreen" type="checkbox"> green matchups</label><label>legs <select id="genN"><option>3</option><option>4</option><option selected>5</option><option>6</option><option>7</option><option>8</option></select></label><input id="genX" type="text" placeholder="leave out a player (e.g. Walker)" aria-label="leave out players"></div>
    <div class="grow"><button type="button" class="btn" id="genGo">Find it</button><span class="note" id="genScope"></span></div>
    <div id="genOut"></div>
   </div>
   </details>
   <ul id="slipLegs"></ul>
   <div class="tgt" id="tgt" hidden>
    <div class="row"><span>Target FanDuel price</span><b id="tgtVal">—</b></div>
    <input type="range" id="tgtRange" min="0" max="1000" step="1" aria-label="target FanDuel price">
    <div class="ends"><span id="tgtMin"></span><span>drag to re-pick lines</span><span id="tgtMax"></span></div>
    <p class="hint" id="tgtHint">Moves the ‹ › faders for you: every leg with a ladder is re-picked so the slip's FanDuel price lands near the target, keeping the best model edge among the ways to get there.</p>
   </div>
   <div class="price" id="price"></div>
   <div class="take" id="take" style="display:none"></div>
   <div class="flags" id="flags"></div>
   <div class="acts books3"><a class="fd" id="sendfd" href="#" target="_blank" rel="noopener" aria-disabled="true">FanDuel</a><a class="fd dk" id="senddk" href="#" target="_blank" rel="noopener" aria-disabled="true" style="display:none">DraftKings</a><a class="fd hr" id="sendhr" href="#" target="_blank" rel="noopener" aria-disabled="true" style="display:none">Hard Rock</a></div>
   <div class="acts"><button type="button" class="pri" id="savesl">Save slip</button><button type="button" class="pri" id="copy">Copy slip</button><button type="button" id="clear">Clear</button></div>
   <div class="acts share"><button type="button" class="social" id="postsl" title="Post this slip to BetSweep Social for others to tail and upvote"><img src="data:image/png;base64,{LOGO_S}" alt=""><span><b>Post to BetSweep Social</b><small>let people tail it · upvotes put it on top</small></span></button>{SHORTL.BTN_HTML}</div>
   <p class="note" id="fdnote" style="padding-top:0"></p>
   <p class="note" id="bknote" style="padding-top:0"></p>
   <p class="note" style="padding-top:0">DraftKings and Hard Rock load the same legs on their betslip at their price (nearest line where they don't post ours - the note above lists any). Model, edges and grading stay against FanDuel.</p>
   <div class="saved" id="saved"><h3>Saved slips <small>build a few, compare, send the one you like</small></h3><div id="savedList"></div></div>
   <p class="note">Model % is the model's history-adjusted hit rate for that line, blended 50/50 with FanDuel's price (see "What do the numbers mean?"); book % is what FanDuel's price implies; edge is the difference in points (positive = the price pays more than the risk deserves). "Fair" prices the whole combination: legs from different games are independent, legs from the same game are linked with the model's correlations (receptions ↔ receiving yards, QB ↔ his receivers, and so on). Odds move; this page was built {stamp} CT. Information only, not a guarantee — 21+, please bet responsibly.</p>
  </section>
 </aside>
</div>
{SOCIAL.POST_HTML}<style>{SOCIAL.POST_CSS}</style>
<script>window.__BS = {json.dumps(DATA, separators=(",", ":"))};</script>
<script>{LIVE.LIVE_JS}</script>
<script>{BOOKS.BOOKS_JS}</script>
<script>{BUILDER_JS}</script>'''

page = (open(os.path.join(HERE, "template.html")).read()
        .replace("<title>BetSweep Matchup Boards</title>", "<title>BetSweep Parlay Builder</title>")
        .replace("<h1>Week {{WEEK}} · <b>Matchup Boards</b></h1>", "<h1>Week {{WEEK}} · <b>Parlay Builder</b></h1>")
        .replace("</style>", BUILDER_CSS + LIVE.LIVE_CSS + BOOKS.BOOKS_CSS + "\n</style>", 1)
        .replace("{{DESC}}", f"Every FanDuel player prop on the Week {WEEK} slate, priced against the model. Filter to what you like, tap legs into a slip, and see the model's fair odds for the whole parlay next to FanDuel's. Built {stamp} CT.")
        .replace("{{NAV}}", '<a href="https://claude.ai/artifact/RTTqiN3sdMHGgojimQ9hZv">← This week\'s boards</a>').replace("{{CARDS}}", body)
        .replace("{{LOGO}}", LOGO).replace("{{BANNER}}", BANNER).replace("{{WEEK}}", str(WEEK)).replace("{{STAMP}}", stamp).replace("{{ARCHIVE}}", ""))
page = re.sub(r'<div class="key">.*?</div>\n', '', page, count=1, flags=re.S)
page = page.replace('<div class="grid">', '<div class="grid" style="display:block">', 1)
page += SOCIAL.POST_JS + SHORTL.BTN_JS
out = os.path.join(OUT, "builder.html"); open(out, "w").write(page)
json.dump(DATA, open(os.path.join(OUT, "builder_data.json"), "w"), separators=(",", ":"))   # for build_live.py
print(f"game lines: {NGL} legs ({NGL_FD} FanDuel-priced, {NGL - NGL_FD} consensus, {NALT} alternate spreads/totals)")
print(f"wrote {out}: {len(LEGS)} legs, {len(GAMES)} games, week {WEEK}, {NLINK} with FanDuel links, {NFTD} first-TD legs")
