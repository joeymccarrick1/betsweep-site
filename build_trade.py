#!/usr/bin/env python3
"""build_trade.py - BetSweep trade calculator (rest-of-season values from the model's own data) - v2026-10-20.

Inputs: in/gamelog.json  ('AUTO - Player Game Log'!A1:X6000: every player-game this season)
        in/avail.json    ('AUTO - Weekly Availability': OUT / QUESTIONABLE rows with the injury text - IR "through Week N" is parsed)
        in/snaps.json    ('AUTO - Snap Trends': season / last-2 snap share, trend signal)
        in/settings.json ('AUTO - Settings': B2 = projection week)
        in/games.csv     (nflverse schedule: remaining games and byes per team)
        in/stats_player_week_2025.csv + _2024.csv (nflverse weekly, the prior seasons; downloaded from GitHub if missing)
        in/market.json   ('AUTO - Market Values'!A1:J1000: FantasyCalc values pulled by the sheet's Apps Script - optional; without it values are unblended)
        in/roster_2026.csv (nflverse roster: birth dates / draft slot; downloaded from GitHub if missing) + gen/dynasty.json (age curves, survival, rookie-pick ppg from gen/research/dynasty/)
Output: out/trade.html (+ out/trade_values.json for the Fantasy page / anyone else)

How a value is built (all of it is recomputed in the page when a toggle changes):
  per-game stat averages over the games the player actually played (a row in the log with a snap or a touch; missing weeks are not zeros)
  -> fantasy points per game under the chosen scoring (PPR / half, TE premium 0 / +0.5 / +1.0)
  -> blended with last season's per-game line (in/stats_player_week_2025.csv, aged a year) at the weight of 4 games; with no 2025 line, hot short samples are shrunk DOWN toward the average starter (1.5 pseudo-games), players below that are not lifted
  -> rest-of-season games = regular-season weeks left minus the bye minus injury weeks (IR "through Week N" / "out for the season" from the availability text)
  -> points above a bench-depth baseline (12 teams: QB 18, RB 45, WR 54, TE 18 = 1.5x starters; superflex moves QB to 30; league size scales those)
  -> trade value = 9999 x (points above replacement / the best player's)^1.4 - convex on purpose: one star beats two middling players,
     the same shape every market calculator has, but the ranking underneath is our projections, not a vote.
Dynasty toggle: + next two seasons aged with the position curve x survival x 0.8^year above the same replacement, plus rookie picks priced from draft-slot production (gen/dynasty.json).
"""
import json, html, os, re, csv, datetime, statistics
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
E = html.escape
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def num(x):
    try: return float(str(x).replace("%", "").replace(",", ""))
    except Exception: return None
exec(open(os.path.join(HERE, "brand.py")).read())

ALIAS = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
st_ = {r[0]: r[1] for r in vals("settings.json")[1:] if len(r) > 1}
WEEK = int(float(st_.get("Projection Week", 0)))
LAST_WEEK = 17   # fantasy regular season + playoffs end Week 17 in most leagues; Week 18 is excluded on purpose
# ---- schedule: remaining games per team (weeks WEEK..17), bye week ----
remaining = defaultdict(set); bye = {}
with open(os.path.join(IN, "games.csv"), newline="") as f:
    for g in csv.DictReader(f):
        if g["season"] != "2026" or g["game_type"] != "REG": continue
        w = int(g["week"])
        if WEEK <= w <= LAST_WEEK:
            remaining[ALIAS.get(g["home_team"], g["home_team"])].add(w); remaining[ALIAS.get(g["away_team"], g["away_team"])].add(w)
for t, ws in remaining.items():
    missing = [w for w in range(WEEK, LAST_WEEK + 1) if w not in ws]
    if missing: bye[t] = missing[0]
# ---- game log -> per-game averages ----
gl = vals("gamelog.json"); GH = {c: i for i, c in enumerate(gl[0])}
def g(r, c): return num(r[GH[c]]) if c in GH and GH[c] < len(r) else None
P = {}
for r in gl[1:]:
    if len(r) < 17 or num(r[0]) is None or int(num(r[0])) >= WEEK: continue   # never the target week
    name, team, pos = r[1].strip(), ALIAS.get(r[2], r[2]), r[3].strip()
    if pos not in ("QB", "RB", "WR", "TE"): continue
    touches = (g(r, "Pass Att") or 0) + (g(r, "Rush Att") or 0) + (g(r, "Targets") or 0)
    if touches <= 0: continue   # a row with no involvement is not a game played for value purposes
    p = P.setdefault(name, {"n": name, "pos": pos, "tm": team, "g": 0, "wk": [], "s": defaultdict(float), "games": []})
    p["tm"] = team
    p["games"].append({"wk": int(num(r[0])), "touch": touches, **{k: (g(r, c) or 0) for k, c in (("py", "Pass Yds"), ("ptd", "Pass TD"), ("int", "INT"), ("ry", "Rush Yds"), ("rtd", "Rush TD"), ("rec", "Receptions"), ("recy", "Rec Yds"), ("rectd", "Rec TD"), ("tgt", "Targets"), ("ra", "Rush Att"))}})
    # last-3 PPR points for the trend chip
    x = p["games"][-1]; x["pts"] = round(0.04 * x["py"] + 4 * x["ptd"] - 2 * x["int"] + 0.1 * x["ry"] + 6 * x["rtd"] + x["rec"] + 0.1 * x["recy"] + 6 * x["rectd"], 1)
# ---- availability ----
AV = {}
try:
    av = vals("avail.json"); AH = {c: i for i, c in enumerate(av[0])}
    for r in av[1:]:
        r = r + [""] * (13 - len(r))
        if num(r[0]) is not None and int(num(r[0])) != WEEK: continue
        AV[r[AH["Player"]].strip()] = {"st": r[AH["Availability"]].strip().upper(), "why": r[AH["Reason / Injury"]].strip(), "team": ALIAS.get(r[AH["Team"]], r[AH["Team"]]), "pos": r[AH["Pos"]]}
except Exception as e: print("warn: availability not read:", e)
def games_out(a):
    """weeks the player misses from WEEK on, from the availability text."""
    if not a: return 0, ""
    why = a["why"].lower(); st = a["st"]
    if st == "OUT":
        if "season" in why: return 99, "out for the season"
        m = re.search(r"through week (\d+)", why)
        if m: return max(0, int(m.group(1)) - WEEK + 1), f"IR through Week {m.group(1)}"
        m = re.search(r"min(?:imum)? (\d+) games", why)
        if m: return int(m.group(1)), f"IR, at least {m.group(1)} games"
        m = re.search(r"(\d+)\s*-\s*(\d+) weeks", why)
        if m: return (int(m.group(1)) + int(m.group(2))) // 2, f"out {m.group(1)}-{m.group(2)} weeks"
        if "released" in why or "not on a roster" in why: return 99, "not on a roster"
        return 4, "out, no timeline (4 weeks assumed)"
    if st == "QUESTIONABLE": return 0, "questionable"
    return 0, ""
# ---- snaps ----
SN = {}
try:
    sn = vals("snaps.json"); SH = {c: i for i, c in enumerate(sn[0])}
    for r in sn[1:]:
        if len(r) > SH["Signal"]: SN[r[0].strip()] = {"snap": num(r[SH["Season snap %"]]), "l2": num(r[SH["Last-2 snap %"]]), "sig": r[SH["Signal"]]}
except Exception: pass
# ---- ages and draft capital (nflverse roster; downloaded once per container) ----
# 11/5: _norm lives at module level - it used to be defined inside this try, so one failed roster download (a GitHub 504) took the whole trade page down
def _norm(x): return re.sub(r"\s+", " ", re.sub(r"\.", "", str(x))).strip().lower().replace(" jr", "").replace(" sr", "").replace(" iii", "").replace(" ii", "")
AGE = {}
try:
    rp = os.path.join(IN, "roster_2026.csv")
    if not os.path.exists(rp):
        import urllib.request
        urllib.request.urlretrieve("https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_2026.csv", rp)
    with open(rp, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("position") not in ("QB", "RB", "WR", "TE") or not r.get("birth_date"): continue
            try: bd = datetime.date.fromisoformat(r["birth_date"][:10])
            except Exception: continue
            age = (datetime.date(2026, 9, 1) - bd).days / 365.25
            AGE[(_norm(r["full_name"]), r["position"])] = {"age": round(age, 1), "entry": int(r["entry_year"]) if str(r.get("entry_year", "")).isdigit() else None, "pick": int(float(r["draft_number"])) if r.get("draft_number") not in (None, "", "NA") else None}
except Exception as e: print("warn: roster ages not loaded:", e)
DYN = json.load(open(os.path.join(HERE, "dynasty.json")))
# ---- last season as a prior (nflverse weekly 2025; downloaded once per container): per-game averages over games with a touch ----
def season_lines(season):
    """{(norm name, pos): {"g": games with a touch, "a": per-game averages}} from the nflverse weekly file for that season (downloaded if missing)."""
    out = {}
    wp = os.path.join(IN, f"stats_player_week_{season}.csv")
    if not os.path.exists(wp):
        import urllib.request
        urllib.request.urlretrieve(f"https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv", wp)
    acc = {}
    with open(wp, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("season_type") != "REG" or r.get("position") not in ("QB", "RB", "WR", "TE"): continue
            fl = lambda k: float(r.get(k) or 0)
            if fl("attempts") + fl("carries") + fl("targets") <= 0: continue
            k = (_norm(r["player_display_name"]), r["position"]); d = acc.setdefault(k, {"g": 0, "touch": 0, "py": 0, "ptd": 0, "int": 0, "ry": 0, "rtd": 0, "rec": 0, "recy": 0, "rectd": 0})
            d["g"] += 1; d["touch"] += fl("attempts") + fl("carries") + fl("targets"); d["py"] += fl("passing_yards"); d["ptd"] += fl("passing_tds"); d["int"] += fl("passing_interceptions") or fl("interceptions"); d["ry"] += fl("rushing_yards"); d["rtd"] += fl("rushing_tds")
            d["rec"] += fl("receptions"); d["recy"] += fl("receiving_yards"); d["rectd"] += fl("receiving_tds")
    for k, d in acc.items():
        if d["g"] >= 4: out[k] = {"g": d["g"], "a": {kk: round(v / d["g"], 3) for kk, v in d.items() if kk != "g"}}
    return out
PRIOR = {}
try:
    L25 = season_lines(2025)
    try: L24 = season_lines(2024)
    except Exception as e: print("warn: 2024 prior not loaded:", e); L24 = {}
    for k in set(L25) | set(L24):
        PRIOR[k] = {"g25": L25.get(k, {}).get("g"), "a25": L25.get(k, {}).get("a"), "g24": L24.get(k, {}).get("g"), "a24": L24.get(k, {}).get("a")}
except Exception as e: print("warn: 2025 prior not loaded:", e)
# ---- market values ('AUTO - Market Values' tab = FantasyCalc API, pulled by the sheet's Apps Script; optional) ----
MKT = {}; PICKMKT = {}
try:
    mv = vals("market.json"); MH = {c: i for i, c in enumerate(mv[0])}
    for r in mv[1:]:
        r = r + [""] * (len(mv[0]) - len(r))
        if not r[MH["Player"]] or r[MH["Pos"]] not in ("QB", "RB", "WR", "TE"): continue
        MKT[(_norm(r[MH["Player"]]), r[MH["Pos"]])] = {"d1": num(r[MH["Dynasty 1QB"]]), "d2": num(r[MH["Dynasty SF"]]), "r1": num(r[MH["Redraft 1QB"]]), "r2": num(r[MH["Redraft SF"]]), "sid": r[MH.get("Sleeper ID", 0)] if "Sleeper ID" in MH else ""}
    print(f"market values: {len(MKT)} players (FantasyCalc via the sheet)")
    # rookie picks (owner 10/28: picks were priced far below the market): FantasyCalc's pick rows, keyed by our pick names;
    # 2028 has no early/mid/late split there, so the 2027 early/mid/late : plain-1st ratios are applied to the 2028 1st
    PM = {}
    for r in mv[1:]:
        r = r + [""] * (len(mv[0]) - len(r))
        if r[MH["Pos"]] == "PICK" and r[MH["Player"]]: PM[r[MH["Player"]].strip()] = {"d1": num(r[MH["Dynasty 1QB"]]), "d2": num(r[MH["Dynasty SF"]])}
    def _pm(name):
        v = PM.get(name); return v if v and v["d1"] else None
    for yr in (2027, 2028):
        base1 = _pm(f"{yr} 1st"); ref1 = _pm("2027 1st")
        for slot, mname in (("early 1st", "1st (Early)"), ("mid 1st", "1st (Mid)"), ("late 1st", "1st (Late)")):
            v = _pm(f"{yr} {mname}")
            if not v and base1 and ref1 and _pm(f"2027 {mname}"):
                v = {k: round(base1[k] * _pm(f"2027 {mname}")[k] / ref1[k]) for k in ("d1", "d2") if base1[k] and ref1[k]}
            if v: PICKMKT[f"{yr} {slot} round pick"] = v
        for slot, mname in (("2nd", "2nd"), ("3rd", "3rd")):
            v = _pm(f"{yr} {mname}")
            if v: PICKMKT[f"{yr} {slot} round pick"] = v
    print(f"market pick values: {len(PICKMKT)} of 10 picks matched")
except Exception as e: print("note: no market values this run (in/market.json missing or empty) - values shown unblended:", e)
# ---- player rows ----
rows = []
for name, p in P.items():
    pr = PRIOR.get((_norm(name), p["pos"]), {})
    # a game he left early (fewer than 35% of his normal touches, judged against last season when we have it, else his own best game)
    # is not a sample of the player - A.J. Brown's two injury-shortened games must not price him; it is dropped and the prior carries
    ref = (pr.get("a25") or pr.get("a24") or {}).get("touch") or (max(x["touch"] for x in p["games"]) if p["games"] else 0)
    full = [x for x in p["games"] if x["touch"] >= 0.35 * ref] if ref else p["games"]
    p["partial"] = len(p["games"]) - len(full); p["g"] = len(full)
    for x in full:
        for k in ("py", "ptd", "int", "ry", "rtd", "rec", "recy", "rectd", "tgt", "ra"): p["s"][k] += x[k]
    if p["g"] < 1 and not pr: continue
    a = AV.get(name); miss, why = games_out(a)
    R = len([w for w in remaining.get(p["tm"], ()) if w >= WEEK])
    R_eff = max(0, R - miss) if miss < 99 else 0
    avg = {k: round(v / p["g"], 3) for k, v in p["s"].items()} if p["g"] else {k: 0.0 for k in ("py", "ptd", "int", "ry", "rtd", "rec", "recy", "rectd", "tgt", "ra")}
    pts = sorted((x["wk"], x["pts"]) for x in full)
    l3 = round(statistics.mean(x[1] for x in pts[-3:]), 1) if pts else None
    sn_ = SN.get(name, {})
    ag = AGE.get((_norm(name), p["pos"])) if AGE else None
    rows.append({"n": name, "pos": p["pos"], "tm": p["tm"], "g": p["g"], "a": avg, "R": R, "Re": R_eff, "bye": bye.get(p["tm"]), "st": (a or {}).get("st", ""), "why": why or ((a or {}).get("why", "")[:80] if a else ""),
                 "l3": l3, "snap": sn_.get("snap"), "l2": sn_.get("l2"), "sig": sn_.get("sig", ""), "age": (ag or {}).get("age"), "entry": (ag or {}).get("entry"), "dpick": (ag or {}).get("pick"), "a25": pr.get("a25"), "g25": pr.get("g25"), "a24": pr.get("a24"), "g24": pr.get("g24"), "part": p["partial"], "mkt": MKT.get((_norm(name), p["pos"])), "sid": (MKT.get((_norm(name), p["pos"])) or {}).get("sid", "")})
# position means (PPR) for the shrink, computed in JS too - here only for the printed sanity line
def ppr(a): return 0.04 * a["py"] + 4 * a["ptd"] - 2 * a["int"] + 0.1 * a["ry"] + 6 * a["rtd"] + a["rec"] + 0.1 * a["recy"] + 6 * a["rectd"]
rows = [r for r in rows if ppr(r["a"]) >= 1.0 or r["g"] >= 3 or r["a25"] or r["a24"]]
rows.sort(key=lambda r: -ppr(r["a"]))
stamp = datetime.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p")
n_age = sum(1 for r in rows if r["age"]); n_prior = sum(1 for r in rows if r["a25"] or r["a24"]); n_mkt = sum(1 for r in rows if r["mkt"])
DATA = {"week": WEEK, "last": LAST_WEEK, "built": stamp, "players": rows, "dyn": DYN, "mkt_w": 0.3 if MKT else 0.0, "pickmkt": PICKMKT}
json.dump(DATA, open(os.path.join(OUT, "trade_values.json"), "w"), separators=(",", ":"))

CSS = r"""
.tc{max-width:1180px;margin:0 auto}
.tc .panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:14px}
.tc .opts{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;font-size:13px}
.tc .opts label{display:inline-flex;align-items:center;gap:6px;cursor:pointer;padding:6px 10px;border:1px solid var(--line);border-radius:999px;background:color-mix(in srgb,var(--chalk) 60%,transparent)}
.tc .opts label.on{border-color:var(--red);background:color-mix(in srgb,var(--red) 14%,transparent)}
.tc .opts select{font:inherit;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:5px 8px}
.tc .sides{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:760px){.tc .sides{grid-template-columns:1fr}}
.tc .side h2{margin:0 0 8px;font-family:var(--display);font-size:20px;letter-spacing:.02em}
.tc .side h2 small{color:var(--mute);font-weight:500;font-size:12px;margin-left:8px}
.tc .add{position:relative}
.tc .add input{width:100%;box-sizing:border-box;font:inherit;font-size:15px;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink)}
.tc .sug{position:absolute;left:0;right:0;top:100%;z-index:5;background:var(--card);border:1px solid var(--line);border-radius:10px;max-height:280px;overflow:auto;box-shadow:0 10px 30px rgba(0,0,0,.25)}
.tc .sug button{display:flex;width:100%;gap:10px;align-items:center;text-align:left;font:inherit;background:none;border:0;border-bottom:1px solid var(--line);padding:8px 12px;color:var(--ink);cursor:pointer}
.tc .sug button:hover,.tc .sug button.k{background:color-mix(in srgb,var(--red) 12%,transparent)}
.tc .sug b.v{margin-left:auto;font-variant-numeric:tabular-nums}
.tc .legs{list-style:none;margin:10px 0 0;padding:0}
.tc .legs li{display:grid;grid-template-columns:auto 1fr auto auto;gap:10px;align-items:center;padding:9px 0;border-top:1px solid var(--line);font-size:14px}
.tc .legs li:first-child{border-top:0}
.tc .pos{font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.08em;padding:2px 7px;border-radius:4px;background:var(--chalk);color:var(--ink);min-width:28px;text-align:center}
.tc .pos.QB{background:#7c3aed22;color:#a78bfa}.tc .pos.RB{background:#05966922;color:#34d399}.tc .pos.WR{background:#2563eb22;color:#60a5fa}.tc .pos.TE{background:#d9770622;color:#fbbf24}
.tc .legs .who b{display:block}.tc .legs .who small{color:var(--mute);font-size:12px}
.tc .legs .val{font-family:var(--display);font-weight:800;font-size:20px;font-variant-numeric:tabular-nums}
.tc .legs .x{background:none;border:0;color:var(--mute);font-size:18px;cursor:pointer;padding:0 4px}
.tc .tot{display:flex;justify-content:space-between;align-items:baseline;margin-top:10px;padding-top:10px;border-top:2px solid var(--line)}
.tc .tot b{font-family:var(--display);font-size:30px;font-weight:800;font-variant-numeric:tabular-nums}
.tc .tot small{color:var(--mute)}
.tc .verdict{text-align:center;padding:16px;font-family:var(--display)}
.tc .verdict .bar{height:12px;border-radius:999px;background:var(--chalk);overflow:hidden;display:flex;margin:10px auto 8px;max-width:640px}
.tc .verdict .bar i{display:block;height:100%}
.tc .verdict .bar i.a{background:var(--red)}.tc .verdict .bar i.b{background:#2563eb}
.tc .verdict h3{margin:0;font-size:22px}.tc .verdict p{margin:4px 0 0;color:var(--mute);font-size:13px;font-family:var(--body)}
.tc .warn{font-size:12px;color:var(--warn)}
.tc table.rk{width:100%;border-collapse:collapse;font-size:13.5px;font-variant-numeric:tabular-nums}
.tc table.rk th{text-align:left;font-family:var(--display);font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);padding:6px 8px;border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap}
.tc table.rk td{padding:7px 8px;border-bottom:1px solid var(--line)}
.tc table.rk td.r{text-align:right}.tc table.rk th.r{text-align:right}
.tc table.rk tr.out td{opacity:.55}
.tc table.rk{table-layout:auto}
.tc .rkwrap{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%}
@media (max-width:480px){.tc table.rk th.ol,.tc table.rk td.ol{display:none}.tc table.rk td,.tc table.rk th{padding:6px 4px}.tc table.rk{font-size:12.5px}}
.tc table.rk td{vertical-align:middle}
.tc table.rk td.n{color:var(--mute);width:24px;padding-right:2px}
.tc table.rk td.pl b{font-size:14px}.tc table.rk td.pl small{display:block;color:var(--mute);font-size:11.5px;margin-top:1px}
.tc table.rk td.pl em.st{font-style:normal;font-size:10.5px;font-weight:700;margin-left:6px;padding:0 5px;border-radius:3px;border:1px solid}
.tc table.rk td.pl em.st.dn{color:var(--bad)}.tc table.rk td.pl em.st.q{color:var(--warn)}
.tc table.rk td.ol .o1{display:block;font-weight:600;white-space:nowrap}.tc table.rk td.ol .o2{display:block;color:var(--mute);font-size:11px;white-space:nowrap}
.tc table.rk td.mk span{font-size:12.5px;font-weight:600;white-space:nowrap}.tc table.rk td.mk .up{color:var(--good)}.tc table.rk td.mk .dn{color:var(--bad)}.tc table.rk td.mk .na{color:var(--mute)}
.tc table.rk td.v b{font-size:15px}
.tc table.rk td.ab{white-space:nowrap;text-align:right;width:76px}.tc table.rk td.ab .addbtn{padding:3px 7px;margin:0 0 0 3px;min-width:32px;min-height:32px}
@media(max-width:640px){.tc table.rk th.ol,.tc table.rk td.ol{display:none}.tc table.rk td,.tc table.rk th{padding:7px 4px}.tc table.rk td.pl b{font-size:13.5px}}
.tc .chip{display:inline-block;font-size:11px;padding:1px 6px;border-radius:4px;border:1px solid var(--line);color:var(--mute);margin-left:4px}
.tc .chip.up{color:var(--good);border-color:var(--good)}.tc .chip.dn{color:var(--bad);border-color:var(--bad)}.tc .chip.q{color:var(--warn);border-color:var(--warn)}
.tc .rkopts{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px;align-items:center}
.tc .rkopts button{font:inherit;font-size:13px;padding:5px 10px;border-radius:999px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer}
.tc .rkopts button.on{border-color:var(--red);background:color-mix(in srgb,var(--red) 14%,transparent)}
.tc .meth{font-size:13px;color:var(--mute);line-height:1.55}
.tc .meth b{color:var(--ink)}
.tc .addbtn{font:inherit;font-size:12px;padding:3px 8px;border-radius:6px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer;margin-right:2px}
.tc .lg .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.tc .lg input{font:inherit;font-size:15px;padding:9px 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);min-width:220px}
.tc .lg .go{font:inherit;font-size:14px;font-weight:600;padding:9px 14px;border-radius:10px;border:0;background:var(--red);color:#fff;cursor:pointer}
.tc .lg .go[disabled]{opacity:.6}
.tc .lg .msg{font-size:13px;color:var(--mute);margin-top:6px}.tc .lg .msg.err{color:var(--bad)}
.tc .lg .leagues{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.tc .lg .leagues button{font:inherit;font-size:13px;padding:6px 10px;border-radius:999px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer;text-align:left}
.tc .lg .leagues button small{display:block;color:var(--mute);font-size:11px}
.tc .lg .leagues button.on{border-color:var(--red);background:color-mix(in srgb,var(--red) 14%,transparent)}
.tc .teams{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-top:12px}
.tc .team{border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:color-mix(in srgb,var(--chalk) 40%,transparent)}
.tc .team.me{border-color:var(--red)}
.tc .team h3{cursor:pointer;user-select:none}.tc .team h3 i.cv{font-style:normal;color:var(--mute);font-size:12px}
.tc .team.shut .pb,.tc .team.shut ul{display:none}
.tc .tgl{grid-column:1/-1;display:flex;gap:6px;flex-wrap:wrap}
.tc .team h3{margin:0;font-family:var(--display);font-size:16px;display:flex;justify-content:space-between;align-items:baseline}
.tc .team h3 b{font-variant-numeric:tabular-nums}
.tc .team .pb{display:flex;gap:6px;font-size:11px;color:var(--mute);margin:4px 0 6px;flex-wrap:wrap}
.tc .team .pb span b{color:var(--ink)}
.tc .team ul{list-style:none;margin:0;padding:0;max-height:260px;overflow:auto}
.tc .team li{display:flex;gap:6px;align-items:center;font-size:12.5px;padding:3px 0;border-top:1px solid var(--line)}
.tc .team li .nm{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tc .team li .vv{font-variant-numeric:tabular-nums;font-weight:600;min-width:44px;text-align:right}
.tc .ideas li{display:block;padding:8px 0;border-top:1px solid var(--line);font-size:13.5px}
.tc .ideas li b.t{font-family:var(--display)}
.tc .ideas li small{color:var(--mute)}
.tc .ideas li .addbtn{margin-left:6px}
"""

JS = r"""
(function(){
  var D = window.__BS, P = D.players, WEEK = D.week;
  var st = {sf:false, tep:0, ppr:1, teams:12, dyn:false, A:[], B:[], rkpos:'ALL', sortk:'v'};
  var DYN = D.dyn, DISC = 0.8, YEARS = 3, SEASON_G = 17;
  // rookie picks as tradeable assets (dynasty only): expected best ppg in the first three seasons, busts as zero (rookie_values.json)
  var PICKS = [];
  [[2027, 1], [2028, 2]].forEach(function(yr){ var y = yr[0], lag = yr[1];
    [['early 1st','early1'],['mid 1st','mid1'],['late 1st','late1'],['2nd','r2'],['3rd','r3']].forEach(function(k){
      var pn = y+' '+k[0]+' round pick'; PICKS.push({n: pn, pos:'PICK', tm:'pick', g:0, a:null, R:0, Re:0, st:'', why:'', ppg_rk: DYN.rookie[k[1]], lag: lag, pick:true, mkt: (D.pickmkt||{})[pn] || null}); }); });
  var ALL = P.concat(PICKS);
  try{ var s = JSON.parse(localStorage.getItem('bs_trade_'+WEEK)||'null'); if(s){ st.sf=!!s.sf; st.tep=s.tep||0; st.ppr=(s.ppr==null?1:s.ppr); st.teams=s.teams||12; st.dyn=!!s.dyn; st.A=s.A||[]; st.B=s.B||[]; } }catch(e){}
  function save(){ try{ localStorage.setItem('bs_trade_'+WEEK, JSON.stringify({sf:st.sf,tep:st.tep,ppr:st.ppr,teams:st.teams,dyn:st.dyn,A:st.A,B:st.B})); }catch(e){} }
  function curve(pos, age){ var c = DYN.curve[pos]; if(!c) return 1; var a = Math.round(age); if(c[a]!=null) return c[a]; var ks = Object.keys(c).map(Number); return a < Math.min.apply(null,ks) ? c[Math.min.apply(null,ks)] : c[Math.max.apply(null,ks)]; }
  function surv(pos, age){ var c = DYN.survival[pos]; if(!c) return 1; var a = Math.round(age); if(c[a]!=null) return c[a]; var ks = Object.keys(c).map(Number); return a < Math.min.apply(null,ks) ? c[Math.min.apply(null,ks)] : c[Math.max.apply(null,ks)]; }
  function ppgOf(a, pos, tep){ var rp = st.ppr + (pos==='TE'? (tep==null? st.tep : tep) : 0);
    return 0.04*a.py + 4*a.ptd - 2*a.int + 0.1*a.ry + 6*a.rtd + rp*a.rec + 0.1*a.recy + 6*a.rectd; }
  function ppg(p){ return ppgOf(p.a, p.pos); }
  // TE premium (owner 10/28: "some TEs went DOWN with TE premium on"): the bonus used to lift the replacement tight end too, so a
  // low-catch TE lost ground to TE18. Now the baseline is measured in base scoring and every tight end's bonus rides on top of it -
  // nobody drops when the premium goes on, and the heavier-volume tight ends gain the most.
  function adjOf(p, raw, tep){ var age = p.age || 26, pr = null, pw = 0;
    if (p.a25){ pr = (pr||0) + 2*ppgOf(p.a25, p.pos, tep)*curve(p.pos, age); pw += 2; }
    if (p.a24){ pr = (pr||0) + 1*ppgOf(p.a24, p.pos, tep)*curve(p.pos, age)*curve(p.pos, age-1); pw += 1; }
    if (pr!=null) return {prior: pr/pw, adj: (p.g*raw + 6*(pr/pw))/(p.g+6)};
    return null; }
  // the baseline is a bench-depth player (1.5x the starters), not the last starter: a WR40 is worth something in a trade, and
  // the convex curve keeps the stars where they belong. Superflex: QBs are startable to QB24, so the bench baseline moves to QB30.
  var REPL = {QB:18, RB:45, WR:54, TE:18};
  function compute(){
    var byPos = {QB:[],RB:[],WR:[],TE:[]}, raw = {};
    P.forEach(function(p){ raw[p.n] = ppg(p); byPos[p.pos].push(p); });
    var mean = {};
    var STARTERS = {QB:12, RB:24, WR:36, TE:12};   // the prior is a starter at the position, not the whole position (which is mostly backups)
    var meanAll = {};
    for (var k in byPos){ var all = byPos[k].filter(function(p){ return p.g>=2; }).map(function(p){ return raw[p.n]; }).sort(function(a,b){ return b-a; }); var xs = all.slice(0, STARTERS[k]); mean[k] = xs.length? xs.reduce(function(s,x){return s+x;},0)/xs.length : 0; meanAll[k] = all.length? all.reduce(function(s,x){return s+x;},0)/all.length : 0; }
    P.forEach(function(p){ p.ppg = raw[p.n];
      // prior: last season's per-game line (aged one year on the position curve) with the weight of 4 games - so a star who has
      // missed most of this year (A.J. Brown, 2 games) is still priced as the player he was; without a 2025 line, the one-sided
      // starter-mean shrink applies (a hot four-game start regresses toward an average starter, a backup is left where he is)
      // history: 2025 counts double, 2024 once (each aged to this season on the position curve); the blend carries the weight of six games
      var h = adjOf(p, raw[p.n], null);
      if (h){ p.prior = h.prior; p.adj = h.adj; }
      else { // no history at all (rookies, first-year starters): three pseudo-games of regression toward a target that is only an average
             // STARTER once he has four games behind him - a one-game wonder regresses toward an average body at the position instead
             var w = Math.min(1, p.g/4), target = w*mean[p.pos] + (1-w)*meanAll[p.pos]; p.prior = null; p.adj = (p.g*raw[p.n] + 3*Math.min(raw[p.n], target))/(p.g+3); }
      // base-scoring twin for tight ends under a premium (the replacement level is measured on it)
      p.adj0 = p.adj;
      if (p.pos==='TE' && st.tep){ var r0 = ppgOf(p.a, p.pos, 0), h0 = adjOf(p, r0, 0); p.adj0 = h0 ? h0.adj : p.adj - (raw[p.n] - r0); } });
    var scale = st.teams/12, repl = {};
    for (var k in byPos){
      var n = Math.round((k==='QB' && st.sf ? 30 : REPL[k]) * scale);
      var healthy = byPos[k].filter(function(p){ return p.Re>0; }).sort(function(a,b){ return b.adj0-a.adj0; });
      repl[k] = healthy[Math.min(n-1, healthy.length-1)] ? healthy[Math.min(n-1, healthy.length-1)].adj0 : 0;
    }
    var vmax = 0;
    // nobody who plays is a zero: a quarter of his raw points rides along under the above-baseline term, so a bench body with 8 ppg
    // keeps a small value and the practice-squad end of the table fades to nothing on its own
    P.forEach(function(p){ p.vorp = Math.max(0, p.adj0 - repl[p.pos]) + (p.adj - p.adj0) + 0.25*Math.max(0, p.adj); p.ros = p.vorp * p.Re; p.pts = Math.round(p.adj*p.Re);
      // dynasty: this season's remainder + the next two seasons, aged with the position curve, weighted by the chance he is still a
      // relevant player, discounted 20% a year; the replacement level is the same format's starter. No age on file -> 26 assumed, flagged.
      var age = p.age || 26, ppg = p.adj, ppg0 = p.adj0, sv = 1, fut = 0, future = [];
      for (var y=1; y<YEARS; y++){ var ay = age + y; ppg = ppg * curve(p.pos, ay); ppg0 = ppg0 * curve(p.pos, ay); sv = sv * surv(p.pos, ay - 1); var vy = (Math.max(0, ppg0 - repl[p.pos]) + (ppg - ppg0) + 0.25*Math.max(0, ppg)) * SEASON_G * sv * Math.pow(DISC, y); fut += vy; future.push(Math.round(ppg*10)/10); }
      p.fut = fut; p.futppg = future; p.score = st.dyn ? p.ros + fut : p.ros; if (p.score>vmax) vmax=p.score; });
    var flexRepl = (repl.RB + repl.WR) / 2;
    // owner 10/28 ("picks need to be valued a lot higher"): a pick is the player it turns into, priced the way every player here is -
    // his first THREE seasons from the draft year (not just the part inside our window, which left a 2028 pick with one season),
    // 70% of his expected best-ppg as a rookie then 100%, above the flex baseline plus a tenth of his points as a floor (a player on a roster today gets a quarter; a pick is not a body yet),
    // each season discounted 20% a year from today. Checked against FantasyCalc 10/28: firsts and seconds within ~15% of the market, 2028 firsts a little above it (we discount
    // 20% a year, the market more), thirds below it (busts are zero here; the market prices hope) - then the 30% market blend applies.
    PICKS.forEach(function(p){ var sc = 0;
      if (st.dyn){ for (var i=0; i<YEARS; i++){ var y = p.lag + i, pp = p.ppg_rk * (i===0 ? 0.7 : 1.0); sc += (Math.max(0, pp - flexRepl) + 0.10*pp) * SEASON_G * Math.pow(DISC, y); } }
      p.score = sc; p.ros = 0; p.fut = sc; p.adj = p.ppg_rk; p.pts = 0; p.vorp = 0; });
    // market (FantasyCalc, the format that matches the toggles), rescaled to its own top
    var W = D.mkt_w || 0, mk = function(p){ if(!p.mkt) return null; var v = st.dyn ? (st.sf ? p.mkt.d2 : p.mkt.d1) : (st.sf ? p.mkt.r2 : p.mkt.r1); return (v==null||isNaN(v))? null : v; };
    var mmax = 0; P.forEach(function(p){ var v = mk(p); if (v!=null && v>mmax) mmax = v; });
    ALL.forEach(function(p){ var v = mk(p); p.mv = (v!=null && mmax)? Math.round(9999*v/mmax) : null; });
    // the curve's steepness is fitted to the market's shape (least squares on log value, players the market has at 1,000+), so a
    // "vs market" gap is a real disagreement about a player and not our scale being steeper than theirs; 1.4 when there is no market
    var expo = 1.4;
    if (W){ var fitP = P.filter(function(p){ return p.mv!=null && p.mv>=1000 && p.score>0; }); if (fitP.length >= 30){ var best = null;
      for (var e=0.7; e<=1.8; e+=0.05){ var ss = 0; fitP.forEach(function(p){ var o = 9999*Math.pow(p.score/vmax, e); ss += Math.pow(Math.log(Math.max(o,1)/p.mv), 2); }); if (best===null || ss<best[0]) best=[ss,e]; } expo = best[1]; } }
    st.expo = expo;
    ALL.forEach(function(p){ p.ours = vmax? Math.round(9999*Math.pow(Math.max(0,p.score)/vmax, expo)) : 0; p.v = (W && p.mv!=null)? Math.round((1-W)*p.ours + W*p.mv) : p.ours; });
    var ranks = {}; ALL.slice().sort(function(a,b){ return b.v-a.v || (b.adj||0)-(a.adj||0); }).forEach(function(p){ ranks[p.pos]=(ranks[p.pos]||0)+1; p.prk = (p.pos==='PICK'?'pick ':p.pos)+ranks[p.pos]; });
    st.repl = repl;
  }
  var byName = {}; ALL.forEach(function(p){ byName[p.n]=p; });
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function chips(p){ var h='';
    if (p.pick) return '<span class="chip">rookie pick · '+p.ppg_rk.toFixed(1)+' ppg expected</span>';
    if (st.dyn){ h += '<span class="chip">'+(p.age? 'age '+p.age.toFixed(0) : 'age ? (26 assumed)')+'</span>'; if (p.futppg) h += '<span class="chip">\'27 '+p.futppg[0].toFixed(1)+' · \'28 '+p.futppg[1].toFixed(1)+' ppg</span>'; }
    if (p.mv!=null && D.mkt_w){ var d = p.ours - p.mv; h += '<span class="chip '+(d>=1500?'up':d<=-1500?'dn':'')+'" title="our number '+p.ours.toLocaleString()+' vs the market '+p.mv.toLocaleString()+'">'+(d>=0?'+':'')+Math.round(d/100)/10+'k vs market</span>'; }
    if (p.Re===0) h += '<span class="chip dn">'+esc(p.why||'out')+'</span>';
    else if (p.st==='OUT') h += '<span class="chip dn">'+esc(p.why)+'</span>';
    else if (p.st==='QUESTIONABLE') h += '<span class="chip q">questionable</span>';
    if (p.l3!=null && p.g>=3){ var d = p.l3 - p.ppg; if (d>=4) h+='<span class="chip up">L3 '+p.l3.toFixed(1)+'</span>'; else if (d<=-4) h+='<span class="chip dn">L3 '+p.l3.toFixed(1)+'</span>'; }
    if (p.sig && /DOWN|SLIP|FALL/i.test(p.sig)) h += '<span class="chip dn">snaps slipping</span>';
    if (p.g<3) h += '<span class="chip">'+p.g+' full game'+(p.g===1?'':'s')+(p.part? ' ('+p.part+' left early)' : '')+(p.prior!=null? ' · \'25 '+p.prior.toFixed(1)+' ppg' : '')+'</span>';
    if (p.bye && p.bye>=WEEK) h += '<span class="chip">bye '+p.bye+'</span>';
    return h; }
  function sideHtml(key){ var list = st[key].map(function(n){ return byName[n]; }).filter(Boolean); var tot = list.reduce(function(s,p){ return s+p.v; },0);
    return list.map(function(p){ return '<li><span class="pos '+p.pos+'">'+(p.pick?'PK':p.pos)+'</span><span class="who"><b>'+esc(p.n)+(p.pick?'':' <small>'+p.tm+' · '+p.prk+'</small>')+'</b><small>'+(p.pick? '' : p.adj.toFixed(1)+' ppg · '+p.pts+' pts over '+p.Re+' games')+chips(p)+'</small></span><span class="val">'+p.v.toLocaleString()+'</span><button class="x" data-side="'+key+'" data-n="'+esc(p.n)+'" aria-label="remove">×</button></li>'; }).join('')
      + '<div class="tot"><small>'+(list.length? list.length+' player'+(list.length>1?'s':'') : 'add players')+'</small><b>'+tot.toLocaleString()+'</b></div>'; }
  function verdict(){ var a = st.A.reduce(function(s,n){ return s+(byName[n]?byName[n].v:0); },0), b = st.B.reduce(function(s,n){ return s+(byName[n]?byName[n].v:0); },0);
    var el = document.getElementById('verdict'); if(!a && !b){ el.innerHTML = '<h3>Add players to both sides</h3><p>Values are rest-of-season, from the model\'s own game data - not a vote.</p>'; return; }
    var t=a+b, pa = t? a/t*100 : 50, diff = Math.abs(a-b), pct = t? diff/Math.max(a,b)*100 : 0;
    var who = diff/Math.max(a,b,1) < 0.05 ? 'Fair trade' : (a>b ? 'Side A wins' : 'Side B wins');
    el.innerHTML = '<h3>'+who+(who==='Fair trade'?'':' by '+pct.toFixed(0)+'%')+'</h3><div class="bar"><i class="a" style="width:'+pa.toFixed(1)+'%"></i><i class="b" style="width:'+(100-pa).toFixed(1)+'%"></i></div><p>Side A '+a.toLocaleString()+' · Side B '+b.toLocaleString()+' · '+(st.dyn?'dynasty (3-year)':'rest of season')+' · '+(st.sf?'superflex':'1QB')+(st.tep?' · TE +'+st.tep:'')+' · '+(st.ppr===1?'PPR':st.ppr===0.5?'half PPR':'standard')+' · '+st.teams+' teams</p>'; }
  function render(){ compute(); document.getElementById('sideA').innerHTML = sideHtml('A'); document.getElementById('sideB').innerHTML = sideHtml('B'); verdict(); rankings(); save(); if (window.__bsLeague && !document.getElementById('slOut').hidden) window.__bsLeague();
    document.querySelectorAll('.opts label').forEach(function(l){ var i=l.querySelector('input'); if(i) l.classList.toggle('on', i.checked); }); }
  function rankings(){ var pos = st.rkpos, list = ALL.filter(function(p){ return (pos==='ALL' || p.pos===pos) && (st.dyn || !p.pick); }).sort(function(a,b){ return st.sortk==='adj'? b.adj-a.adj : st.sortk==='pts'? b.pts-a.pts : b.v-a.v; }).slice(0, pos==='ALL'?150:60);
    document.getElementById('rk').innerHTML = list.map(function(p,i){
      var status = p.pick ? '' : p.Re===0 ? '<em class="st dn">'+esc(p.why||'out')+'</em>' : p.st==='OUT' ? '<em class="st dn">'+esc(p.why)+'</em>' : p.st==='QUESTIONABLE' ? '<em class="st q">Q</em>' : '';
      var sub = p.pick ? 'rookie pick' : esc(p.tm)+' · '+p.prk+(st.dyn && p.age ? ' · age '+p.age.toFixed(0) : '');
      var look = p.pick ? '<span class="o1">'+p.ppg_rk.toFixed(1)+'</span><span class="o2">ppg at best</span>' : st.dyn && p.futppg ? '<span class="o1">'+p.adj.toFixed(1)+' → '+p.futppg[0].toFixed(1)+' → '+p.futppg[1].toFixed(1)+'</span><span class="o2">ppg now · \'27 · \'28</span>' : '<span class="o1">'+p.adj.toFixed(1)+' ppg</span><span class="o2">'+p.Re+' games · '+p.pts+' pts</span>';
      var d = (p.mv!=null && D.mkt_w) ? p.ours - p.mv : null, mk = d==null ? '<span class="na">—</span>' : '<span class="'+(d>=1500?'up':d<=-1500?'dn':'')+'" title="our number '+p.ours.toLocaleString()+' vs the market '+p.mv.toLocaleString()+'">'+(d>=0?'+':'')+(Math.round(d/100)/10).toFixed(1)+'k</span>';
      return '<tr class="'+(p.Re===0 && !p.pick?'out':'')+'"><td class="r n">'+(i+1)+'</td><td class="pl"><b>'+esc(p.n)+'</b>'+status+'<small>'+sub+'</small></td><td class="r ol">'+look+'</td><td class="r mk">'+mk+'</td><td class="r v"><b>'+p.v.toLocaleString()+'</b></td><td class="ab"><button class="addbtn" data-n="'+esc(p.n)+'" data-side="A" title="add to side A">A</button><button class="addbtn" data-n="'+esc(p.n)+'" data-side="B" title="add to side B">B</button></td></tr>'; }).join('');
    document.getElementById('rkhead').textContent = st.dyn ? 'Dynasty rankings' : 'Rest-of-season rankings';
    document.getElementById('replnote').textContent = 'Baseline this format: QB '+st.repl.QB.toFixed(1)+' · RB '+st.repl.RB.toFixed(1)+' · WR '+st.repl.WR.toFixed(1)+' · TE '+st.repl.TE.toFixed(1)+' ppg'+(D.mkt_w? ' · curve fitted to the market (exponent '+st.expo.toFixed(2)+')' : '')+'.'; }
  // search
  function wire(key){ var inp = document.getElementById('in'+key), sug = document.getElementById('sug'+key), k = -1, cur = [];
    function show(){ var q = inp.value.trim().toLowerCase(); if(q.length<2){ sug.hidden=true; return; }
      cur = ALL.filter(function(p){ return (st.dyn || !p.pick) && p.n.toLowerCase().indexOf(q)>=0 && st.A.indexOf(p.n)<0 && st.B.indexOf(p.n)<0; }).sort(function(a,b){ return b.v-a.v; }).slice(0,8); k=-1;
      sug.innerHTML = cur.map(function(p,i){ return '<button type="button" data-i="'+i+'"><span class="pos '+p.pos+'">'+p.pos+'</span><span>'+esc(p.n)+' <small>'+p.tm+' · '+p.prk+'</small></span><b class="v">'+p.v.toLocaleString()+'</b></button>'; }).join(''); sug.hidden = !cur.length; }
    function pick(i){ if(!cur[i]) return; st[key].push(cur[i].n); inp.value=''; sug.hidden=true; render(); }
    inp.addEventListener('input', show); inp.addEventListener('focus', show);
    inp.addEventListener('keydown', function(e){ if(sug.hidden) return; if(e.key==='ArrowDown'){ k=Math.min(k+1,cur.length-1); } else if(e.key==='ArrowUp'){ k=Math.max(k-1,0); } else if(e.key==='Enter'){ e.preventDefault(); pick(k<0?0:k); return; } else if(e.key==='Escape'){ sug.hidden=true; return; } else return; e.preventDefault(); sug.querySelectorAll('button').forEach(function(b,i){ b.classList.toggle('k', i===k); }); });
    sug.addEventListener('mousedown', function(e){ var b = e.target.closest('button'); if(b){ e.preventDefault(); pick(+b.dataset.i); } });
    document.addEventListener('click', function(e){ if(!sug.contains(e.target) && e.target!==inp) sug.hidden=true; }); }
  wire('A'); wire('B');
  document.addEventListener('click', function(e){ var x = e.target.closest('.x[data-side]'); if(x){ var s = st[x.dataset.side]; var i = s.indexOf(x.dataset.n); if(i>=0) s.splice(i,1); render(); return; }
    var ab = e.target.closest('.addbtn[data-side]'); if(ab){ if(st.A.indexOf(ab.dataset.n)<0 && st.B.indexOf(ab.dataset.n)<0){ st[ab.dataset.side].push(ab.dataset.n); render(); window.scrollTo({top:0,behavior:'smooth'}); } return; }
    var rb = e.target.closest('.rkopts button'); if(rb){ if(rb.dataset.pos){ st.rkpos = rb.dataset.pos; } document.querySelectorAll('.rkopts button[data-pos]').forEach(function(b){ b.classList.toggle('on', b.dataset.pos===st.rkpos); }); rankings(); return; }
    var th = e.target.closest('th[data-k]'); if(th){ st.sortk = th.dataset.k; rankings(); } });
  document.getElementById('sf').addEventListener('change', function(e){ st.sf = e.target.checked; render(); });
  document.getElementById('dyn').addEventListener('change', function(e){ st.dyn = e.target.checked; if(!st.dyn){ st.A = st.A.filter(function(n){ return !(byName[n]&&byName[n].pick); }); st.B = st.B.filter(function(n){ return !(byName[n]&&byName[n].pick); }); } render(); });
  document.getElementById('tep').addEventListener('change', function(e){ st.tep = +e.target.value; render(); });
  document.getElementById('ppr').addEventListener('change', function(e){ st.ppr = +e.target.value; render(); });
  document.getElementById('teams').addEventListener('change', function(e){ st.teams = +e.target.value; render(); });
  document.getElementById('swap').addEventListener('click', function(){ var t = st.A; st.A = st.B; st.B = t; render(); });
  document.getElementById('clear').addEventListener('click', function(){ st.A=[]; st.B=[]; render(); });
  // ---- Sleeper league import ----
  (function(){
    var API = 'https://api.sleeper.app/v1/', $ = function(q){ return document.querySelector(q); };
    function get(path){ return fetch(API + path).then(function(r){ if(!r.ok) throw new Error(path + ' -> ' + r.status); return r.json(); }); }
    function say(t, err){ var m = $('#slMsg'); m.hidden = !t; m.textContent = t || ''; m.classList.toggle('err', !!err); }
    function normn(x){ return String(x).replace(/\./g,'').replace(/\s+(jr|sr|ii|iii|iv|v)$/i,'').replace(/\s+/g,' ').trim().toLowerCase(); }
    var bySid = {}, byNorm = {}; P.forEach(function(p){ if (p.sid) bySid[String(p.sid)] = p; var k = normn(p.n)+'|'+p.pos; if(!byNorm[k] || byNorm[k].g < p.g) byNorm[k] = p; });
    var PM = null;
    function players(){ if (PM) return Promise.resolve(PM);
      try{ var c = JSON.parse(localStorage.getItem('bs_sleeper_players')||'null'); if(c && Date.now()-c.t < 36e5*20){ PM = c.m; return Promise.resolve(PM); } }catch(e){}
      return get('players/nfl').then(function(all){ var m = {}; Object.keys(all).forEach(function(id){ var x = all[id]; if(!x || ['QB','RB','WR','TE'].indexOf(x.position)<0) return; m[id] = {n: x.full_name || ((x.first_name||'')+' '+(x.last_name||'')), t: x.team||'', p: x.position, i: x.injury_status||''}; }); PM = m; try{ localStorage.setItem('bs_sleeper_players', JSON.stringify({t: Date.now(), m: m})); }catch(e){} return m; }); }
    function modelFor(id, pm){ if (bySid[id]) return bySid[id]; var sp = pm[id]; if(!sp) return null; return byNorm[normn(sp.n)+'|'+sp.p] || null; }
    var S = {user:null, leagues:[], league:null, season:null, rosters:null, users:null, pm:null};
    $('#slGo').addEventListener('click', connect); $('#slUser').addEventListener('keydown', function(e){ if(e.key==='Enter') connect(); });
    try{ var su = localStorage.getItem('bs_sleeper_user'); if(su) $('#slUser').value = su; }catch(e){}
    function connect(){ var u = $('#slUser').value.trim().replace(/^@/,''); if(!u) return; $('#slGo').disabled = true; say('Looking up '+u+' on Sleeper…'); $('#slOut').hidden = true; $('#slLeagues').innerHTML = '';
      get('state/nfl').then(function(x){ S.season = String(x.season || new Date().getFullYear()); return get('user/'+encodeURIComponent(u)); })
      .then(function(user){ if(!user || !user.user_id) throw new Error('no user'); S.user = user; try{ localStorage.setItem('bs_sleeper_user', u); }catch(e){} return get('user/'+user.user_id+'/leagues/nfl/'+S.season); })
      .then(function(ls){ ls = (ls||[]).filter(function(l){ return l.status !== 'pre_draft'; }); S.leagues = ls; if(!ls.length){ say('No '+S.season+' NFL leagues on that account.', true); return; } say('');
        var box = $('#slLeagues'), last = ''; try{ last = localStorage.getItem('bs_sleeper_league')||''; }catch(e){}
        ls.forEach(function(l){ var b = document.createElement('button'); b.type='button'; b.innerHTML = esc(l.name)+'<small>'+l.total_rosters+' teams'+(l.settings && l.settings.type===2 ? ' · dynasty' : '')+((l.roster_positions||[]).indexOf('SUPER_FLEX')>=0 ? ' · superflex' : '')+'</small>'; b.addEventListener('click', function(){ pick(l, b); }); box.appendChild(b); });
        var auto = ls.filter(function(l){ return l.league_id===last; })[0] || ls[0]; if(auto) pick(auto, box.children[ls.indexOf(auto)]); })
      .catch(function(e){ say('Could not find that Sleeper username (it is the username, not the team name).', true); console.error(e); })
      .then(function(){ $('#slGo').disabled = false; }); }
    function pick(l, btn){ S.league = l; try{ localStorage.setItem('bs_sleeper_league', l.league_id); }catch(e){}
      Array.prototype.forEach.call($('#slLeagues').children, function(b){ b.classList.toggle('on', b===btn); }); say('Loading '+l.name+'…'); $('#slOut').hidden = true;
      // the league's format drives the toggles: superflex slot, TE premium bonus, PPR value, dynasty type, team count
      var sc = l.scoring_settings || {}, rp = l.roster_positions || [];
      st.sf = rp.indexOf('SUPER_FLEX') >= 0; st.tep = (sc.bonus_rec_te || 0) >= 0.75 ? 1 : (sc.bonus_rec_te || 0) > 0 ? 0.5 : 0; st.ppr = (sc.rec||0) >= 0.75 ? 1 : (sc.rec||0) > 0 ? 0.5 : 0;
      st.dyn = !!(l.settings && l.settings.type === 2); st.teams = [10,12,14].reduce(function(b,x){ return Math.abs(x-(l.total_rosters||12)) < Math.abs(b-(l.total_rosters||12)) ? x : b; }, 12);
      $('#sf').checked = st.sf; $('#dyn').checked = st.dyn; $('#tep').value = String(st.tep); $('#ppr').value = String(st.ppr); $('#teams').value = String(st.teams);
      Promise.all([players(), get('league/'+l.league_id+'/rosters'), get('league/'+l.league_id+'/users')]).then(function(r){ S.pm = r[0]; S.rosters = r[1]; S.users = r[2]; render(); say(''); })
      .catch(function(e){ say('Sleeper did not answer for that league. Try again in a moment.', true); console.error(e); }); }
    var OPEN = {me: true, opp: false};   // my roster open, opponents collapsed by default; a single card's own toggle overrides the group
    document.addEventListener('click', function(e){ var tg = e.target.closest('[data-tg]'); if (tg){ var k = tg.dataset.tg; OPEN[k] = !OPEN[k]; if (k==='opp') Object.keys(OPEN).forEach(function(x){ if (x!=='me' && x!=='opp') delete OPEN[x]; }); render(); return; }
      var h = e.target.closest('.team h3'); if (h && !e.target.closest('button')){ var c = h.parentNode; if (c.dataset.me==='1') OPEN.me = !OPEN.me; else { var rid = c.dataset.rid; var cur = OPEN[rid] != null ? OPEN[rid] : OPEN.opp; OPEN[rid] = !cur; } render(); } });
    function render(){ if(!S.rosters) return; compute(); var l = S.league, me = S.user.user_id, uname = {}; S.users.forEach(function(u){ uname[u.user_id] = (u.metadata && u.metadata.team_name) || u.display_name; });
      var teams = S.rosters.map(function(r){ var ps = (r.players||[]).map(function(id){ var mp = modelFor(id, S.pm); var sp = S.pm[id]; return {id:id, mp:mp, sp:sp, v: mp? mp.v : 0}; }).filter(function(x){ return x.mp || x.sp; });
        ps.sort(function(a,b){ return b.v-a.v; }); var byp = {QB:0,RB:0,WR:0,TE:0}, cnt = {QB:0,RB:0,WR:0,TE:0}; ps.forEach(function(x){ if(x.mp){ byp[x.mp.pos]+=x.v; cnt[x.mp.pos]++; } });
        return {r:r, name: uname[r.owner_id] || ('Team '+r.roster_id), me: r.owner_id===me || (r.co_owners||[]).indexOf(me)>=0, ps:ps, tot: ps.reduce(function(s,x){ return s+x.v; },0), byp:byp, cnt:cnt, rec: (r.settings? r.settings.wins+'-'+r.settings.losses : '')}; });
      teams.sort(function(a,b){ return b.tot-a.tot; });
      $('#slFmt').textContent = l.name+': '+(st.dyn?'dynasty':'redraft')+' · '+(st.sf?'superflex':'1QB')+(st.tep?' · TE +'+st.tep:'')+' · '+(st.ppr===1?'PPR':st.ppr===0.5?'half PPR':'standard')+' · '+l.total_rosters+' teams. Toggles above were set from the league settings; change them if your league scores differently.';
      $('#slTeams').innerHTML = '<div class="tgl"><button type="button" class="addbtn" data-tg="me">'+(OPEN.me?'Collapse':'Expand')+' my team</button><button type="button" class="addbtn" data-tg="opp">'+(OPEN.opp?'Collapse':'Expand')+' all opponents</button></div>' + teams.map(function(t, i){ var open = t.me ? OPEN.me : (OPEN[t.r.roster_id] != null ? OPEN[t.r.roster_id] : OPEN.opp); return '<div class="team'+(t.me?' me':'')+(open?'':' shut')+'" data-rid="'+t.r.roster_id+'" data-me="'+(t.me?1:0)+'"><h3 role="button" tabindex="0"><span><i class="cv">'+(open?'▾':'▸')+'</i> '+(i+1)+'. '+esc(t.name)+(t.me?' <small>(you)</small>':'')+' <small>'+esc(t.rec)+'</small></span><b>'+t.tot.toLocaleString()+'</b></h3><div class="pb">'+['QB','RB','WR','TE'].map(function(k){ return '<span>'+k+' <b>'+t.byp[k].toLocaleString()+'</b> ('+t.cnt[k]+')</span>'; }).join('')+'</div><ul>'+t.ps.map(function(x){ var mp = x.mp; return '<li><span class="pos '+(mp?mp.pos:(x.sp.p||''))+'">'+(mp?mp.pos:x.sp.p)+'</span><span class="nm">'+esc(mp?mp.n:x.sp.n)+(mp?'':' <small>not valued</small>')+'</span>'+(mp? '<button class="addbtn" data-n="'+esc(mp.n)+'" data-side="'+(t.me?'A':'B')+'">'+(t.me?'+A':'+B')+'</button>' : '')+'<span class="vv">'+(mp? mp.v.toLocaleString() : '—')+'</span></li>'; }).join('')+'</ul></div>'; }).join('');
      // trade ideas: my surplus position (most value above the league average at that position) for their need, 1-for-1 within 12%
      var mine = teams.filter(function(t){ return t.me; })[0]; var ideas = [];
      if (mine){ var avg = {}; ['QB','RB','WR','TE'].forEach(function(k){ avg[k] = teams.reduce(function(s,t){ return s+t.byp[k]; },0)/teams.length; });
        var surplus = ['QB','RB','WR','TE'].filter(function(k){ return mine.byp[k] > avg[k]*1.15 && mine.cnt[k] >= (k==='QB'||k==='TE'?2:4); }).sort(function(a,b){ return (mine.byp[b]-avg[b])-(mine.byp[a]-avg[a]); });
        var need = ['QB','RB','WR','TE'].filter(function(k){ return mine.byp[k] < avg[k]*0.9; }).sort(function(a,b){ return (mine.byp[a]-avg[a])-(mine.byp[b]-avg[b]); });
        if (!need.length) need = ['QB','RB','WR','TE'].sort(function(a,b){ return (mine.byp[a]-avg[a])-(mine.byp[b]-avg[b]); }).slice(0,1);
        teams.forEach(function(t){ if (t.me) return;
          surplus.forEach(function(sk){ var give = mine.ps.filter(function(x){ return x.mp && x.mp.pos===sk; }).slice(sk==='QB'||sk==='TE'?1:2); // keep my starters
            need.forEach(function(nk){ if (t.byp[nk] < avg[nk]*0.9 && t.byp[sk] < avg[sk]*1.15 || true){ var gets = t.ps.filter(function(x){ return x.mp && x.mp.pos===nk; });
              give.forEach(function(g){ gets.forEach(function(x){ var d = (g.v - x.v)/Math.max(g.v, x.v, 1); if (Math.abs(d) <= 0.12 && g.v > 300 && x.v > 300 && t.byp[sk] < mine.byp[sk]) ideas.push({give:g.mp, get:x.mp, team:t.name, d:d, gain: x.v - g.v}); }); }); } }); }); });
        ideas.sort(function(a,b){ return (b.give.v+b.get.v)-(a.give.v+a.get.v); });
        var seen = {}; ideas = ideas.filter(function(i){ var k = i.give.n+'|'+i.get.n; if(seen[k]) return false; seen[k]=true; return true; }).slice(0,8); }
      $('#slIdeas').innerHTML = ideas.length ? ideas.map(function(i){ return '<li><b class="t">'+esc(i.give.n)+'</b> <small>('+i.give.pos+', '+i.give.v.toLocaleString()+')</small> for <b class="t">'+esc(i.get.n)+'</b> <small>('+i.get.pos+', '+i.get.v.toLocaleString()+') with '+esc(i.team)+' · '+(i.gain>=0?'+':'')+i.gain.toLocaleString()+' for you</small><button class="addbtn" data-idea="'+esc(i.give.n)+'|'+esc(i.get.n)+'">Load</button></li>'; }).join('') : '<li><small>'+(mine? 'No balanced 1-for-1 swaps from a surplus position right now - use the +A / +B buttons on the rosters to build one by hand.' : 'You are not on a roster in this league.')+'</small></li>';
      $('#slOut').hidden = false; }
    document.addEventListener('click', function(e){ var b = e.target.closest('[data-idea]'); if(!b) return; var k = b.dataset.idea.split('|'); st.A = [k[0]]; st.B = [k[1]]; window.__bsRender(); window.scrollTo({top:0,behavior:'smooth'}); });
    window.__bsLeague = render;
  })();
  window.__bsRender = render;
  document.getElementById('sf').checked = st.sf; document.getElementById('dyn').checked = st.dyn; document.getElementById('tep').value = String(st.tep); document.getElementById('ppr').value = String(st.ppr); document.getElementById('teams').value = String(st.teams);
  render();
})();
"""

body = f'''<div class="tc">
 <section class="panel">
  <div class="opts">
   <label><input type="checkbox" id="dyn"> Dynasty <small>(3-year value, rookie picks)</small></label>
   <label><input type="checkbox" id="sf"> Superflex <small>(2 QB starters)</small></label>
   <label>TE premium <select id="tep"><option value="0">off</option><option value="0.5">+0.5 / catch</option><option value="1">+1.0 / catch</option></select></label>
   <label>Scoring <select id="ppr"><option value="1">PPR</option><option value="0.5">Half PPR</option><option value="0">Standard</option></select></label>
   <label>Teams <select id="teams"><option>10</option><option selected>12</option><option>14</option></select></label>
   <button type="button" id="swap" class="addbtn" style="font-size:13px;padding:6px 10px">Swap sides</button>
   <button type="button" id="clear" class="addbtn" style="font-size:13px;padding:6px 10px">Clear</button>
  </div>
 </section>
 <section class="panel verdict" id="verdict"></section>
 <div class="sides">
  <section class="panel side"><h2>Side A <small>gives</small></h2><div class="add"><input id="inA" placeholder="Add a player…" autocomplete="off"><div class="sug" id="sugA" hidden></div></div><ul class="legs" id="sideA"></ul></section>
  <section class="panel side"><h2>Side B <small>gives</small></h2><div class="add"><input id="inB" placeholder="Add a player…" autocomplete="off"><div class="sug" id="sugB" hidden></div></div><ul class="legs" id="sideB"></ul></section>
 </div>
 <section class="panel lg" id="league">
  <h2 style="margin:0 0 6px;font-family:var(--display);font-size:20px">Your league <small style="color:var(--mute);font-size:12px;font-weight:500">Sleeper import · every roster valued · trade ideas</small></h2>
  <div class="row"><input id="slUser" placeholder="Sleeper username" autocomplete="off"><button type="button" class="go" id="slGo">Import</button><span class="meth">Reads only public league data; nothing is posted to Sleeper.</span></div>
  <div class="msg" id="slMsg" hidden></div>
  <div class="leagues" id="slLeagues"></div>
  <div id="slOut" hidden>
   <p class="meth" id="slFmt"></p>
   <h3 style="margin:12px 0 4px;font-family:var(--display);font-size:16px">Trade ideas for you</h3>
   <p class="meth" style="margin:0 0 4px">Swaps where you give from a position you are deep at and get back a position you are thin at, priced within 12% either way by the calculator - so the other manager can say yes. Tap one to load it above and adjust.</p>
   <ul class="ideas" id="slIdeas"></ul>
   <div class="teams" id="slTeams"></div>
  </div>
 </section>
 <section class="panel">
  <h2 style="margin:0 0 6px;font-family:var(--display);font-size:20px"><span id="rkhead">Rest-of-season rankings</span> <small style="color:var(--mute);font-size:12px;font-weight:500">Weeks {WEEK}–{LAST_WEEK} · recomputed with the toggles above</small></h2>
  <div class="rkopts"><button type="button" data-pos="ALL" class="on">All</button><button type="button" data-pos="QB">QB</button><button type="button" data-pos="RB">RB</button><button type="button" data-pos="WR">WR</button><button type="button" data-pos="TE">TE</button><span class="meth" id="replnote"></span></div>
  <div class="rkwrap"><table class="rk"><thead><tr><th class="r n">#</th><th>Player</th><th class="r ol" data-k="adj">Outlook</th><th class="r mk" title="our value minus the market's (FantasyCalc), on the same 0-9,999 scale">vs mkt</th><th class="r v" data-k="v">Value</th><th class="ab">Add</th></tr></thead><tbody id="rk"></tbody></table></div>
 </section>
 <section class="panel meth">
  <b>How the value is built.</b> Every number starts from this season's game log, games the player actually played and finished (a missed week is not a zero, and a game he left early - under 35% of his normal touches - is dropped rather than counted as a bad game). Per-game averages become fantasy points under the scoring you pick, are blended with the last two seasons' per-game lines (2025 counting double, each aged to this season on the position curve, together weighted like six games - so a star who has missed most of this season is still priced as the player he was, and a hot month does not rewrite him); a player with no history at all (a rookie, a first-year starter) is pulled down toward the average starter when a short sample is running hot - three pseudo-games' worth, because five good games is not yet a career - and left alone otherwise; then multiplied by the games left: regular-season weeks through Week {LAST_WEEK}, minus the bye, minus the weeks the injury report says he misses (IR "through Week N" and "out for the season" are read from our availability table; an unlisted timeline assumes four weeks). Nobody who plays is a zero: a quarter of a player's own points rides along under the above-baseline term, so bench bodies keep a small value and the table fades to nothing only at the practice-squad end. Value is points above a bench-depth baseline for your format (the 18th QB, 45th RB, 54th WR, 18th TE in a 12-team league - 1.5x the starters, so a fringe starter is worth something); with superflex on, the baseline is the 30th QB instead of the 18th, which is why quarterbacks jump - raised to a power and scaled so the best player is 9,999. The curve is deliberate - one star is worth more than two average starters, which is how real trade markets behave - and its steepness is fitted to the market's own shape when market values are on, so a "vs market" gap is a disagreement about a player, not about scale. With TE premium on, the bonus is added on top of a baseline measured in base scoring, so every tight end goes up and the high-catch ones go up most. Superflex, TE premium, scoring and league size recompute everything on the page.<br><br>
  <b>Dynasty.</b> With the toggle on, value is this season's remainder plus the next two seasons: next year's points per game is this year's times the position's age curve (from every 2012-2025 pair of seasons with 8+ games both years: running backs lose about 11% a year from 25 and 21% a year from 30; receivers hold until 24 then lose 6% at 25 and 15% a year at 30; tight ends peak at 24; quarterbacks are flat to 30), times the chance he is still a relevant player the following year (about 80% in the mid-20s, 60% for a 30-year-old back), above the same replacement starter, discounted 20% a year. Rookie picks are priced from what drafted players actually produced in their first three seasons, busts counted as zero (early firsts about 16.5 ppg at their best, mid firsts 13.4, late firsts 11.2, seconds 10.2, thirds 8.2; NFL round-one pick buckets stand in for early/mid/late fantasy firsts, which is an approximation) priced like any player here: his first three seasons from the draft year (70% of that number as a rookie, then 100%), above the flex baseline, discounted 20% a year from today, then blended 30% with the market's pick prices when they are on. Firsts and seconds land within about 15% of the market; thirds run below it because busts count as zero here and the market prices hope. A player with no birth date on file is treated as 26 and says so. The research, tables and sample sizes are published in the generator bundle (gen/research/dynasty/RESEARCH.md). It is a projection-model view of dynasty value, deliberately blind to hype; contracts and depth charts beyond this season are not in it yet.<br><br>
  <b>Market blend.</b> {"The value shown is 70% ours and 30% the market (FantasyCalc's crowd-sourced trade values for the matching format: redraft or dynasty, 1QB or superflex), each on the 0-9,999 scale. The chip on each player shows how far our number sits from the market's - that gap is where the model disagrees with the crowd, and it is the part worth reading." if n_mkt else "Market values were not available for this build, so the numbers shown are ours alone; when the market feed is on, the shown value is 70% ours / 30% FantasyCalc and each player carries a 'vs market' chip."}<br><br>
  Built {stamp} CT from data through Week {WEEK - 1}; ages on file for {n_age} of {len(rows)} players, prior-season lines for {n_prior}, market values for {n_mkt}. Information only.
 </section>
</div>
<script>window.__BS = {json.dumps(DATA, separators=(",", ":"))};</script>
<script>{JS}</script>'''

page = (open(os.path.join(HERE, "template.html")).read()
        .replace("<title>BetSweep Matchup Boards</title>", "<title>BetSweep Trade Calculator</title>")
        .replace("<h1>Week {{WEEK}} · <b>Matchup Boards</b></h1>", "<h1>Week {{WEEK}} · <b>Trade Calculator</b></h1>")
        .replace("</style>", CSS + "\n</style>", 1)
        .replace("{{DESC}}", f"Trade values built from the model's own game data, not a vote: {len(rows)} players, rest-of-season or dynasty (age curves + rookie picks), superflex and TE-premium toggles, every value recomputed on the page; import a Sleeper league to see every roster valued and trade ideas.")
        .replace("{{NAV}}", '<a href="https://claude.ai/artifact/RTTqiN3sdMHGgojimQ9hZv">← This week\'s boards</a>').replace("{{CARDS}}", body)
        .replace("{{LOGO}}", LOGO).replace("{{BANNER}}", BANNER).replace("{{WEEK}}", str(WEEK)).replace("{{STAMP}}", stamp).replace("{{ARCHIVE}}", ""))
page = re.sub(r'<div class="key">.*?</dl>\n</div>\n', '', page, count=1, flags=re.S)
page = page.replace('<div class="grid">', '<div class="grid" style="display:block">', 1)
out = os.path.join(OUT, "trade.html"); open(out, "w").write(page)
top = rows[:5]
print(f"wrote {out}: {len(rows)} players valued, week {WEEK} (games through week {WEEK-1}), {len(page)//1024} KB; top PPR ppg: " + ", ".join(f"{r['n']} {ppr(r['a']):.1f}" for r in top))
