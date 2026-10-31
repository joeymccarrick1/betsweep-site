#!/usr/bin/env python3
"""build_team.py - BetSweep "Fantasy" (was My Team): import a Sleeper league in the browser and grade it against the model.

Inputs (in/, fetched by prep.py from the Sheet):
  proj_qb.json  'AUTO - QB Projections'!A1:AS300   proj_rb.json 'AUTO - RB Projections'!A1:BD300
  proj_wr.json  'AUTO - WR Projections'!A1:AV300   proj_te.json 'AUTO - TE Projections'!A1:AR250
  proj_k.json   'AUTO - Kicker Projections'!A1:P100  proj_dst.json 'AUTO - DST Projections'!A1:M50
  eligible.json 'V1 - Eligible Fantasy Projections'!A1:I650 (NFL.com designations), avail.json, boards.json (week), games.csv (kickoffs), ranks.json (defense ranks)
Sleeper's public API is called from the visitor's browser (read-only, no login); nothing is sent anywhere else.
Writes out/team.html. Full-PPR model points are re-scored per league from the stat projections.
"""
import json, html, re, csv, datetime, os
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
E = html.escape
def vals(n): return json.load(open(os.path.join(IN, n)))["values"]
def num(x):
    try: return float(str(x).replace(",", "").replace("%", "").replace("+", ""))
    except Exception: return None
exec(open(os.path.join(HERE, "brand.py")).read())
boards = vals("boards.json"); WEEK = int(float(boards[1][1]))

def col(h, name):
    try: return h.index(name)
    except ValueError: return None
def nz(v): return round(v, 2) if v is not None else 0

PLAYERS = []
# QB
v = vals("proj_qb.json"); h = v[0]; c = {k: col(h, k) for k in ("Player", "Team", "Opponent", "Proj Pass Yds", "Proj Pass TD", "Proj Rush Yds", "Proj Rush TD", "Proj Fantasy Pts", "Proj INT", "Weekly Active", "Effective Weekly Role", "Availability Override", "Status", "Role Reason")}
for r in v[1:]:
    if len(r) <= c["Proj Fantasy Pts"] or not r[0]: continue
    g = lambda k: r[c[k]] if c[k] is not None and c[k] < len(r) else ""
    PLAYERS.append({"n": r[0], "t": r[1], "p": "QB", "o": g("Opponent"), "fp": nz(num(g("Proj Fantasy Pts"))), "py": nz(num(g("Proj Pass Yds"))), "ptd": nz(num(g("Proj Pass TD"))),
                    "int": nz(num(g("Proj INT"))), "ry": nz(num(g("Proj Rush Yds"))), "rtd": nz(num(g("Proj Rush TD"))), "rec": 0, "rcy": 0, "rctd": 0,
                    "act": str(g("Weekly Active")).upper() == "YES", "role": g("Effective Weekly Role"), "av": g("Availability Override"), "st": g("Status")})
# Replacement starters with no game log (fillin.py): the real starter takes the stand-in's QB row, same projection, role tagged
try:
    import fillin as FILLIN
    for f in FILLIN.load(IN, WEEK):
        for q in PLAYERS:
            if q["p"] == "QB" and q["n"] == f["standin"] and q["t"] == f["team"]: q["n"] = f["player"]; q["role"] = "FILL-IN STARTER (for " + f["for"] + ")"
except Exception as e: print("warn: fill-in starters skipped:", e)
# RB / WR / TE: receptions implied by the full-PPR total (model FP = 0.1*yds + 6*TD + 1*rec)
for fn, pos in (("proj_rb.json", "RB"), ("proj_wr.json", "WR"), ("proj_te.json", "TE")):
    v = vals(fn); h = v[0]; c = {k: col(h, k) for k in ("Opponent", "Proj Rush Yds", "Proj Rec Yds", "Proj Rush TD", "Proj Rec TD", "Proj Fantasy Pts", "Weekly Active", "Effective Weekly Role", "Availability Override", "Status")}
    for r in v[1:]:
        if len(r) <= c["Proj Fantasy Pts"] or not r[0]: continue
        g = lambda k: r[c[k]] if c[k] is not None and c[k] < len(r) else ""
        fp = num(g("Proj Fantasy Pts")) or 0; ry = num(g("Proj Rush Yds")) or 0; rcy = num(g("Proj Rec Yds")) or 0; rtd = num(g("Proj Rush TD")) or 0; rctd = num(g("Proj Rec TD")) or 0
        rec = max(0.0, fp - 0.1 * (ry + rcy) - 6 * (rtd + rctd))
        PLAYERS.append({"n": r[0], "t": r[1], "p": pos, "o": g("Opponent"), "fp": nz(fp), "py": 0, "ptd": 0, "int": 0, "ry": nz(ry), "rtd": nz(rtd), "rec": nz(rec), "rcy": nz(rcy), "rctd": nz(rctd),
                        "act": str(g("Weekly Active")).upper() == "YES", "role": g("Effective Weekly Role"), "av": g("Availability Override"), "st": g("Status")})
# K
v = vals("proj_k.json"); h = v[0]; ck = col(h, "Projected Kick Pts"); cs = col(h, "Status")
for r in v[1:]:
    if len(r) <= ck or not r[0]: continue
    fp = num(r[ck]) or 0
    PLAYERS.append({"n": r[0], "t": r[1], "p": "K", "o": r[2], "fp": nz(fp), "py": 0, "ptd": 0, "int": 0, "ry": 0, "rtd": 0, "rec": 0, "rcy": 0, "rctd": 0, "act": r[2] != "BYE" and fp > 0, "role": "K", "av": "", "st": r[cs] if cs is not None and cs < len(r) else ""})
# DST (team code as the name; Sleeper uses team codes for DEF, LAR for the Rams)
v = vals("proj_dst.json"); h = v[0]; cd = col(h, "Projected DST FP")
for r in v[1:]:
    if not r or not r[0] or r[0] == "Team": continue
    fp = num(r[cd]) if cd is not None and cd < len(r) else None
    t = r[0]
    PLAYERS.append({"n": t, "t": t, "p": "DEF", "o": r[1], "fp": nz(fp), "py": 0, "ptd": 0, "int": 0, "ry": 0, "rtd": 0, "rec": 0, "rcy": 0, "rctd": 0, "act": r[1] != "BYE" and bool(fp), "role": "DEF", "av": "", "st": ""})

# availability overrides: NFL.com designations (V1 - Eligible) and the model's weekly availability tab
ELIG = {}
try:
    for r in vals("eligible.json"):
        if len(r) >= 6 and r[0] and r[5] and r[5] not in ("ACTIVE", "Eligibility"): ELIG[(r[0], r[2])] = r[5].upper()
except Exception: pass
try:
    for r in vals("avail.json")[1:]:
        if len(r) >= 5 and str(r[0]) == str(WEEK) and r[4] == "OUT": ELIG[(r[1], r[3])] = "OUT"
except Exception: pass
SNAPS = {}
try:
    for r in vals("snaps.json")[1:]:
        if len(r) >= 10 and r[0] and num(r[9]) is not None and num(r[9]) < 0.999: SNAPS[r[0]] = (round(num(r[5]) * 100), round(num(r[4]) * 100), round((1 - num(r[9])) * 100))
except Exception: pass
# Strength of schedule (owner 10/29 "whenever you want to get to the SOS"): the same per-player multipliers the boards and Leg Board use
# (build_sos.py -> out/sos_values.json, F:I = x Pass yds, x Rush yds, x Receptions, x Rec yds; each = the two-way opponent factor over the
# sheet's own one-sided factor, so it multiplies the sheet projection directly). Yards and receptions move; TDs do not. The full-PPR model
# total moves by the stat deltas (0.04/pass yd, 0.1/rush or rec yd, 1/rec). p["sos"] = the FP delta, shown as a chip when it is 0.3+ either way.
SOS = {}
try:
    for _r in json.load(open(os.path.join(HERE, "out", "sos_values.json")))["values"]:
        if _r and _r[0]: SOS[_r[0]] = tuple((num(_r[i]) or 1.0) for i in (5, 6, 7, 8))
except Exception as e: print("note: no SOS multipliers for the fantasy / DFS pages this run:", e)
NSOS = 0
for p in PLAYERS:
    m = SOS.get(p["n"]) if p["p"] in ("QB", "RB", "WR", "TE") else None
    if not m: continue
    xp, xr, xc, xy = m; d = 0.0
    if p["p"] == "QB":
        py2 = p["py"] * xp; ry2 = p["ry"] * xr; d = 0.04 * (py2 - p["py"]) + 0.1 * (ry2 - p["ry"]); p["py"], p["ry"] = round(py2, 1), round(ry2, 1)
    else:
        ry2 = p["ry"] * xr; rcy2 = p["rcy"] * xy; rec2 = p["rec"] * xc
        d = 0.1 * (ry2 - p["ry"]) + 0.1 * (rcy2 - p["rcy"]) + 1.0 * (rec2 - p["rec"]); p["ry"], p["rcy"], p["rec"] = round(ry2, 1), round(rcy2, 1), round(rec2, 2)
    if abs(d) > 1e-9: p["fp"] = round(p["fp"] + d, 2); p["sos"] = round(d, 1); NSOS += 1
print(f"SOS applied to {NSOS} of {len(PLAYERS)} players ({sum(1 for p in PLAYERS if abs(p.get('sos') or 0) >= 0.3)} moved 0.3+ FP)")
for p in PLAYERS:
    if p["n"] in SNAPS: p["sd"] = SNAPS[p["n"]]
    e = ELIG.get((p["n"], p["p"]))
    if e in ("OUT", "IR", "DOUBTFUL", "PUP", "SUSPENDED"): p["act"] = False; p["av"] = e
    elif e == "QUESTIONABLE": p["q"] = True

# kickoffs for the week (CT) so the page can say who has already played / is on Thursday
KICK = {}
try:
    with open(os.path.join(IN, "games.csv"), newline="") as f:
        for g in csv.DictReader(f):
            if g["season"] == "2026" and g["week"] == str(WEEK) and g["game_type"] == "REG":
                hh, mm = g["gametime"].split(":"); ct = (int(hh) - 1) % 24; ap = "PM" if ct >= 12 else "AM"; h12 = ct - 12 if ct > 12 else (12 if ct == 0 else ct)
                dt = datetime.date.fromisoformat(g["gameday"]); lab = f"{dt.strftime('%a')} {h12}:{mm} {ap}"
                KICK[g["away_team"]] = lab; KICK[g["home_team"]] = lab
except Exception: pass

# defense ranks for the opponent pill (season), 1 = allows the most
RANKS = {}
try:
    rr = vals("ranks.json"); DCOL = {c: i for i, c in enumerate(rr[0][1:])}
    for r in rr[1:]:
        if not r or str(r[0]).startswith("LAST 3"): break
        if r[0] in ("Defense", ""): continue
        if len(r) > 1 and num(r[1]) is not None: RANKS[r[0]] = [int(float(x)) if num(x) is not None else None for x in r[1:16]]
except Exception: DCOL = {}
RANKCOL = {"QB": "QB Pass Yds", "RB": "RB Rush Yds", "WR": "WR Rec Yds", "TE": "TE Rec Yds"}
try:
    import offranks as _ORK
    _OR = _ORK.load(IN, WEEK)
except Exception as _e: _OR = None; print("note: offense ranks unavailable on the fantasy / DFS pages:", _e)
for p in PLAYERS:
    c = RANKCOL.get(p["p"]); opp = p["o"].replace("LAR", "LA")
    p["dr"] = RANKS.get(opp, [None] * 15)[DCOL[c]] if c and c in DCOL and opp in RANKS else None
    p["or"] = _ORK.rank(_OR, p["t"].replace("LAR", "LA"), c) if (_OR and c) else None   # owner 10/29: his own offense's rank in the same stat
    p["k"] = KICK.get(p["t"].replace("LAR", "LA"), "")

stamp = datetime.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p")
DATA = {"week": WEEK, "stamp": stamp, "players": PLAYERS}
n_act = sum(1 for p in PLAYERS if p["act"])

TEAM_CSS = r"""
.tm-wrap{max-width:1360px;margin:0 auto;display:grid;gap:14px}
.tm-wrap .panel{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.tm-wrap h2{font-family:var(--display);font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:13px;margin:0;padding:10px 14px;border-bottom:1px solid var(--line);color:var(--mute);display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.tm-wrap h2 b{color:var(--ink)} .tm-wrap h2 .r{margin-left:auto;font-family:var(--body);font-weight:500;letter-spacing:0;text-transform:none;font-size:12px}
.connect{display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:14px}
.connect label{font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:12px;color:var(--mute)}
.connect input{font:inherit;font-size:16px;color:var(--ink);background:var(--chalk);border:1px solid var(--line);border-radius:6px;padding:9px 12px;min-width:220px;flex:1 1 220px}
.connect button{font:inherit;font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:14px;color:var(--red-ink);background:var(--red);border:0;border-radius:6px;padding:10px 18px;cursor:pointer}
.connect button:disabled{opacity:.6;cursor:wait}
.connect .how{flex-basis:100%;margin:0;color:var(--mute);font-size:12.5px;line-height:1.5}
.msg{padding:10px 14px;font-size:13px;color:var(--ink);border-top:1px solid var(--line)} .msg.err{color:var(--bad)} .msg[hidden]{display:none}
.leagues{display:flex;flex-wrap:wrap;gap:8px;padding:10px 14px;border-top:1px solid var(--line)}
.leagues button{font:inherit;font-size:13px;color:var(--ink);background:var(--chalk);border:1px solid var(--line);border-radius:6px;padding:8px 12px;cursor:pointer;text-align:left}
.leagues button.on{border-color:var(--red);box-shadow:inset 0 0 0 1px var(--red)}
.leagues button small{display:block;color:var(--mute);font-size:11px}
/* owner 10/31: once a league is chosen, only that league shows; "Switch league" opens the rest */
.leagues.picked button.lgo:not(.on){display:none}
.leagues button.lgsw{background:none;border-style:dashed;color:var(--mute);align-self:center}
.leagues:not(.picked) button.lgsw{display:none}
.scoreline{display:flex;flex-wrap:wrap;gap:6px 14px;padding:8px 14px;border-top:1px solid var(--line);font-size:12.5px;color:var(--mute)} .scoreline b{color:var(--ink)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1px;background:var(--line)}
.tiles > div{background:var(--card);padding:12px 14px}
.tiles small{display:block;font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:11px;color:var(--mute)}
.tiles b{display:block;font-family:var(--display);font-weight:800;font-size:30px;line-height:1.05;margin-top:2px}
.tiles span{display:block;color:var(--mute);font-size:12px;margin-top:2px}
.tiles .wp b{color:var(--red)}
.lineup{list-style:none;margin:0;padding:0}
.lineup li{display:grid;grid-template-columns:52px minmax(0,1fr) auto;gap:4px 10px;align-items:center;padding:8px 14px;border-bottom:1px solid var(--line);font-size:13px}
.lineup li:nth-child(even){background:color-mix(in srgb,var(--chalk) 35%,transparent)}
.lineup .slot{font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.08em;color:var(--red)}
.lineup .who{min-width:0} .lineup .who b{display:block;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lineup .who span{color:var(--mute);font-size:11.5px}
.lineup .pts{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap} .lineup .pts b{display:block;font-family:var(--display);font-size:17px}
.lineup .pts small{color:var(--mute);font-size:11px}
.lineup li.chg{box-shadow:inset 4px 0 0 var(--good)}
.lineup .was{grid-column:2/-1;font-size:12px;color:var(--mute);padding:2px 0 0}
.lineup .was b{color:var(--good);font-weight:600}
.bt{display:inline-block;font-family:var(--display);font-weight:700;font-size:10px;letter-spacing:.06em;padding:1px 5px;border-radius:3px;margin-left:5px;vertical-align:1px;text-transform:uppercase}
.bt.sos.up{background:color-mix(in srgb,var(--good) 22%,transparent);color:var(--good);border:1px solid color-mix(in srgb,var(--good) 50%,transparent)} .bt.sos.dn{background:color-mix(in srgb,var(--bad) 18%,transparent);color:var(--bad);border:1px solid color-mix(in srgb,var(--bad) 45%,transparent)} .bt.out{background:var(--bad);color:#fff} .bt.q{background:var(--warn);color:var(--card)} .bt.bye{background:var(--line);color:var(--ink)} .bt.np{background:var(--line);color:var(--mute)} .bt.hot{background:var(--red);color:#fff} .bt.sd{background:var(--warn);color:var(--card)}
.dpill{display:inline-flex;align-items:center;font-family:var(--display);font-weight:700;font-size:10px;letter-spacing:.04em;padding:1px 5px;border-radius:3px;color:#fff;white-space:nowrap;vertical-align:1px;margin-left:5px} .mup{display:inline-flex;align-items:stretch;border-radius:4px;overflow:hidden;font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.03em;white-space:nowrap;vertical-align:middle;border:1px solid var(--line);margin-left:5px} .mup i{font-style:normal;color:#fff;padding:1px 6px;display:flex;align-items:center} .mup b{font-weight:600;font-size:9px;padding:0 4px;background:var(--chalk,rgba(127,127,127,.15));color:var(--mute);display:flex;align-items:center}
.roster{list-style:none;margin:0;padding:0;columns:2;column-gap:0}
.roster li{break-inside:avoid;display:grid;grid-template-columns:30px minmax(0,1fr) auto;gap:4px 10px;align-items:center;padding:7px 14px;border-bottom:1px solid var(--line);font-size:13px}
.roster .pz{font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.08em;color:var(--red)}
.roster .who b{display:block;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis} .roster .who span{color:var(--mute);font-size:11.5px}
.roster .pts{text-align:right;font-variant-numeric:tabular-nums} .roster .pts b{display:block;font-family:var(--display);font-size:16px} .roster .pts small{color:var(--mute);font-size:11px}
.roster li.st{background:color-mix(in srgb,var(--good) 8%,transparent)}
.waiv{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.waiv > div{background:var(--card);border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.waiv h3{margin:0;padding:8px 14px;font-family:var(--display);font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:12px;color:var(--red);border-bottom:1px solid var(--line)}
.waiv ul{list-style:none;margin:0;padding:0}
.waiv li{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;padding:7px 14px;border-bottom:1px solid var(--line);font-size:13px;align-items:center}
.waiv li b{font-weight:600} .waiv li span{display:block;color:var(--mute);font-size:11.5px}
.waiv li .pts{font-family:var(--display);font-size:16px;text-align:right}
.waiv li .pts small{display:block;font-family:var(--body);font-size:10.5px;color:var(--good)}
.note{padding:8px 14px;color:var(--mute);font-size:12px;line-height:1.5;border-top:1px solid var(--line);margin:0}
.oppbar{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;padding:12px 14px;border-top:1px solid var(--line)}
.oppbar .side{min-width:0} .oppbar .side b{display:block;font-family:var(--display);font-size:26px;line-height:1} .oppbar .side span{display:block;color:var(--mute);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.oppbar .side.r{text-align:right} .oppbar .vs{font-family:var(--display);font-weight:700;color:var(--mute);letter-spacing:.1em}
.meter{height:8px;background:var(--barbg);border-radius:99px;overflow:hidden;margin:0 14px 12px} .meter i{display:block;height:100%;background:var(--red)}
.hid[hidden]{display:none}
.mode{display:flex;border-bottom:1px solid var(--line)}
.mode button{flex:1;font:inherit;font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:13px;padding:12px 10px;background:var(--chalk);color:var(--mute);border:0;border-bottom:3px solid transparent;cursor:pointer}
.mode button.on{background:var(--card);color:var(--ink);border-bottom-color:var(--red)}
#sleeperBox[hidden],#manualBox[hidden],.slist[hidden]{display:none}
#manualBox button.ghost{background:none;color:var(--ink);border:1px solid var(--line);margin-left:6px}
#msaved{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
#msaved li{display:flex;align-items:center;gap:10px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card)}
#msaved li.on{border-color:var(--red);background:color-mix(in srgb,var(--red) 8%,var(--card))}
#msaved li b{font-family:var(--display);font-size:16px}#msaved li span{color:var(--mute);font-size:12.5px;flex:1}
#msaved li button{font:inherit;font-size:12px;font-weight:600;padding:4px 10px;border-radius:6px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer}
#msaved li button.rm{color:var(--mute)}#msaved li.none{color:var(--mute);font-size:13px;border-style:dashed}
.mstep{display:grid;grid-template-columns:150px minmax(0,1fr);gap:8px 14px;padding:12px 14px;border-bottom:1px solid var(--line);align-items:start}
.mstep .lab{font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:12px;color:var(--mute);padding-top:6px}
.mstep .lab small{display:block;font-family:var(--body);font-weight:500;text-transform:none;letter-spacing:0;font-size:11px}
.mstep .hint,.mstep .chips{grid-column:2}
.mstep .hint{margin:0;color:var(--mute);font-size:12px;line-height:1.5}
#mscore{display:flex;flex-wrap:wrap;gap:8px}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:5px;overflow:hidden}
.seg button{font:inherit;font-size:12.5px;padding:6px 10px;background:none;border:0;color:var(--mute);cursor:pointer}
.seg button.on{background:var(--red);color:var(--red-ink)}
#mslots{display:flex;flex-wrap:wrap;gap:8px 14px}
#mslots label{font-family:var(--display);font-weight:700;letter-spacing:.06em;font-size:12px;color:var(--mute);display:inline-flex;align-items:center;gap:6px}
#mslots input{width:46px;font:inherit;font-size:14px;color:var(--ink);background:var(--chalk);border:1px solid var(--line);border-radius:4px;padding:4px 6px;text-align:center}
.srch{position:relative;display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.srch input{font:inherit;font-size:16px;color:var(--ink);background:var(--chalk);border:1px solid var(--line);border-radius:6px;padding:8px 12px;flex:1 1 240px;min-width:0}
.srch .cnt{color:var(--mute);font-size:12px}
.slist{position:absolute;left:0;top:100%;z-index:20;margin-top:4px;min-width:280px;max-width:100%;background:var(--card);border:1px solid var(--line);border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,.35);overflow:hidden}
.slist button{display:flex;flex-direction:column;align-items:flex-start;width:100%;font:inherit;font-size:13px;color:var(--ink);background:none;border:0;border-bottom:1px solid var(--line);padding:7px 12px;text-align:left;cursor:pointer}
.slist button:hover{background:var(--chalk)} .slist button b{font-weight:600} .slist button span{color:var(--mute);font-size:11.5px}
.chips{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:6px}
.chips li{display:grid;grid-template-columns:auto auto minmax(0,1fr) auto;gap:6px;align-items:center;padding:5px 6px 5px 4px;background:var(--chalk);border:1px solid var(--line);border-radius:6px;font-size:13px}
.chips li.st{border-color:var(--good);box-shadow:inset 0 0 0 1px var(--good)}
.chips li.empty{display:block;grid-column:1/-1;background:none;border-style:dashed;color:var(--mute);font-size:12.5px;padding:10px 12px}
.chips .pz{font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.06em;color:var(--red)}
.chips .who{min-width:0} .chips .who b{display:block;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis} .chips .who span{color:var(--mute);font-size:11px}
.chips button{font:inherit;background:none;border:0;color:var(--mute);cursor:pointer;font-size:16px;line-height:1;padding:2px 4px}
.chips button.star{color:var(--warn);font-size:17px} .chips li.st button.star{color:var(--good)}
.chips button.rm:hover{color:var(--bad)}
@media (max-width:760px){ .mstep{grid-template-columns:1fr} .mstep .hint,.mstep .chips{grid-column:1} .mode button{font-size:12px;padding:11px 6px} }
#out[hidden]{display:none} #out{scroll-margin-top:175px}
@media (max-width:760px){ .roster{columns:1} .tiles b{font-size:24px} }
"""

TEAM_JS = r"""
(function(){
  var D = window.__BS, P = D.players, WEEK = D.week;
  var $ = function(s){ return document.querySelector(s); };
  var API = 'https://api.sleeper.app/v1/';
  function norm(s){ return String(s||'').toLowerCase().replace(/\./g,'').replace(/['’]/g,'').replace(/\s+(jr|sr|ii|iii|iv|v)$/,'').replace(/[^a-z0-9 ]/g,'').replace(/\s+/g,' ').trim(); }
  var TEAMFIX = {LA:'LAR'};  // model code -> Sleeper code
  var byName = {}, byNameTeam = {};
  P.forEach(function(p){ var k = norm(p.n); (byName[k] = byName[k] || []).push(p); byNameTeam[k + '|' + (TEAMFIX[p.t] || p.t)] = p; });

  // ---- league scoring: re-score the model's full-PPR projection from its stat lines ----
  function sc(s, k, d){ var v = s && s[k]; return (v === undefined || v === null) ? d : Number(v); }
  function scorePlayer(p, s){
    if(!p) return null;
    if(p.p === 'K' || p.p === 'DEF') return p.fp;   // kicker/defense models already produce fantasy points
    var pts = p.fp;
    pts += (sc(s,'pass_yd',0.04) - 0.04) * p.py + (sc(s,'pass_td',4) - 4) * p.ptd + sc(s,'pass_int',-1) * p.int;
    pts += (sc(s,'rush_yd',0.1) - 0.1) * p.ry + (sc(s,'rush_td',6) - 6) * p.rtd;
    pts += (sc(s,'rec',1) - 1) * p.rec + (sc(s,'rec_yd',0.1) - 0.1) * p.rcy + (sc(s,'rec_td',6) - 6) * p.rctd;
    if(p.p === 'TE') pts += sc(s,'bonus_rec_te',0) * p.rec;
    // yardage bonuses: approximate with a smooth probability of clearing the threshold
    function pb(mean, thr, sd){ if(!mean) return 0; var z = (thr - mean) / sd; return 1 / (1 + Math.exp(1.7 * z)); }
    pts += sc(s,'bonus_pass_yd_300',0) * pb(p.py, 300, 55) + sc(s,'bonus_pass_yd_400',0) * pb(p.py, 400, 55);
    pts += sc(s,'bonus_rush_yd_100',0) * pb(p.ry, 100, 28) + sc(s,'bonus_rec_yd_100',0) * pb(p.rcy, 100, 30);
    return Math.max(0, pts);
  }
  function scoringLabel(s){
    var rec = sc(s,'rec',1), ptd = sc(s,'pass_td',4), te = sc(s,'bonus_rec_te',0);
    var out = [rec === 1 ? 'Full PPR' : rec === 0.5 ? 'Half PPR' : rec === 0 ? 'Standard (no PPR)' : rec + ' per catch'];
    out.push(ptd + '-pt pass TD'); if(te) out.push('TE +' + te + '/catch');
    if(sc(s,'pass_int',-1) !== -1) out.push(sc(s,'pass_int',-1) + ' per INT');
    return out.join(' · ');
  }
  var FLEX = {FLEX:['RB','WR','TE'], SUPER_FLEX:['QB','RB','WR','TE'], REC_FLEX:['WR','TE'], WRRB_FLEX:['RB','WR'], WRRB_WRT:['RB','WR','TE'], QB:['QB'], RB:['RB'], WR:['WR'], TE:['TE'], K:['K'], DEF:['DEF'], DL:[], LB:[], DB:[], IDP_FLEX:[]};
  function slotOrder(s){ var e = FLEX[s]; return e ? e.length : 9; }
  function optimal(slots, pool){
    // pool: [{id, pos, pts}] ; fill most restrictive slots first, then improve by swaps
    var order = slots.map(function(s, i){ return {s: s, i: i}; }).filter(function(x){ return x.s !== 'BN' && x.s !== 'IR' && x.s !== 'TAXI'; }).sort(function(a, b){ return slotOrder(a.s) - slotOrder(b.s) || a.i - b.i; });
    var used = {}, assign = {};
    order.forEach(function(x){
      var el = FLEX[x.s] || []; var best = null;
      pool.forEach(function(p){ if(used[p.id] || el.indexOf(p.pos) < 0) return; if(!best || p.pts > best.pts) best = p; });
      if(best){ used[best.id] = 1; assign[x.i] = best; }
    });
    // swap pass: a bench player who fits a slot better than its occupant, or two starters who should trade slots
    for(var it = 0; it < 3; it++){
      var changed = false;
      order.forEach(function(x){
        var el = FLEX[x.s] || []; var cur = assign[x.i];
        pool.forEach(function(p){
          if(used[p.id] || el.indexOf(p.pos) < 0) return;
          if(!cur || p.pts > cur.pts + 1e-9){ if(cur) delete used[cur.id]; used[p.id] = 1; assign[x.i] = p; cur = p; changed = true; }
        });
      });
      if(!changed) break;
    }
    return assign;
  }
  function pct(x){ return (x * 100).toFixed(0) + '%'; }
  function f1(x){ return (Math.round(x * 10) / 10).toFixed(1); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function rankColor(r){ if(!r) return 'var(--mute)'; var h = 140 - (r - 1) * (140 / 31); return 'hsl(' + h.toFixed(0) + ' 55% 36%)'; }
  function opill(p){ return p && p.or ? '<span class="dpill opill" style="background:' + rankColor(p.or) + '" title="' + esc(p.t) + ' offense ranks #' + p.or + ' of 32 in ' + p.p + ' production this season (1 = produces the most)">' + esc(p.t) + ' off #' + p.or + '</span>' : ''; }
  // owner 10/29: the matchup pill is the literal matchup - his offense's rank in his headline stat vs the opponent defense's rank
  function dpill(p){ if(!p || !p.o) return ''; if(!p.or && !p.dr) return dpill0(p);
    var t = (p.or ? esc(p.t) + ' offense #' + p.or + ' of 32 in ' + p.p + ' production (1 = produces the most)' : '') + (p.or && p.dr ? ' | ' : '') + (p.dr ? esc(p.o) + ' defense #' + p.dr + ' of 32 in ' + p.p + ' production allowed (1 = allows the most)' : '');
    return '<span class="mup" title="' + t + '">' + (p.or ? '<i style="background:' + rankColor(p.or) + '">' + esc(p.t) + ' #' + p.or + '</i>' : '<i style="background:var(--line);color:var(--ink)">' + esc(p.t) + '</i>') + '<b>vs</b>' + (p.dr ? '<i style="background:' + rankColor(p.dr) + '">' + esc(p.o) + ' #' + p.dr + '</i>' : '<i style="background:var(--line);color:var(--ink)">' + esc(p.o) + '</i>') + '</span>'; }
  function dpill0(p){ return p && p.dr ? '<span class="dpill" style="background:' + rankColor(p.dr) + '" title="' + esc(p.o) + ' defense ranks #' + p.dr + ' of 32 in ' + p.p + ' production allowed this season (1 = allows the most)">vs ' + esc(p.o) + ' #' + p.dr + '</span>' : (p && p.o ? '<span class="dpill" style="background:var(--line);color:var(--ink)">vs ' + esc(p.o) + '</span>' : ''); }
  function normalCdf(z){ var t = 1 / (1 + 0.2316419 * Math.abs(z)); var d = 0.3989423 * Math.exp(-z * z / 2); var p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274)))); return z > 0 ? 1 - p : p; }

  // ---- Sleeper fetches ----
  function get(path){ return fetch(API + path).then(function(r){ if(!r.ok) throw new Error(path + ' -> ' + r.status); return r.json(); }); }
  var PMAP = null;
  function playersMap(){
    if(PMAP) return Promise.resolve(PMAP);
    try{ var c = JSON.parse(localStorage.getItem('bs_sleeper_players') || 'null'); if(c && Date.now() - c.t < 36e5 * 20){ PMAP = c.m; return Promise.resolve(PMAP); } }catch(e){}
    return get('players/nfl').then(function(all){
      var m = {}; Object.keys(all).forEach(function(id){ var x = all[id]; if(!x || !x.position) return;
        if(['QB','RB','WR','TE','K','DEF'].indexOf(x.position) < 0 && !(x.fantasy_positions || []).some(function(f){ return ['QB','RB','WR','TE','K','DEF'].indexOf(f) >= 0; })) return;
        m[id] = {n: x.position === 'DEF' ? id : (x.full_name || ((x.first_name || '') + ' ' + (x.last_name || ''))), t: x.team || '', p: x.position, i: x.injury_status || '', s: x.status || ''}; });
      PMAP = m; try{ localStorage.setItem('bs_sleeper_players', JSON.stringify({t: Date.now(), m: m})); }catch(e){}
      return m; });
  }
  function modelFor(sp){
    if(!sp) return null;
    if(sp.mp) return sp.mp;
    if(sp.p === 'DEF'){ var code = sp.n; return byNameTeam[norm(code) + '|' + code] || (byName[norm(code)] || [])[0] || null; }
    var k = norm(sp.n); var hit = byNameTeam[k + '|' + sp.t]; if(hit) return hit;
    var c = (byName[k] || []).filter(function(p){ return p.p === sp.p; }); if(c.length === 1) return c[0];
    if(c.length > 1){ c.sort(function(a, b){ return b.fp - a.fp; }); return c[0]; }
    return (byName[k] || [])[0] || null;
  }
  function badInjury(sp){ return sp && /^(Out|IR|PUP|Sus|Doubtful|NA)$/i.test(sp.i || ''); }

  var state = {user: null, leagues: [], league: null, week: WEEK, season: null};
  var msg = $('#msg'), out = $('#out');
  function say(t, err){ msg.hidden = !t; msg.textContent = t || ''; msg.classList.toggle('err', !!err); }

  $('#go').addEventListener('click', connect); $('#user').addEventListener('keydown', function(e){ if(e.key === 'Enter') connect(); });
  function connect(){
    var u = $('#user').value.trim().replace(/^@/, ''); if(!u) return;
    $('#go').disabled = true; say('Looking up ' + u + ' on Sleeper…'); out.hidden = true; $('#leagues').innerHTML = ''; $('#leagues').classList.remove('picked');
    get('state/nfl').then(function(st){ state.season = String(st.season || new Date().getFullYear()); state.week = st.week || WEEK; return get('user/' + encodeURIComponent(u)); })
    .then(function(user){ if(!user || !user.user_id) throw new Error('no user'); state.user = user; try{ localStorage.setItem('bs_sleeper_user', u); }catch(e){}
      return get('user/' + user.user_id + '/leagues/nfl/' + state.season); })
    .then(function(ls){ ls = (ls || []).filter(function(l){ return l.status !== 'pre_draft'; }); state.leagues = ls;
      if(!ls.length){ say('No ' + state.season + ' NFL leagues on that account.', true); return; }
      say(''); var box = $('#leagues'); var last = ''; try{ last = localStorage.getItem('bs_sleeper_league') || ''; }catch(e){}
      ls.forEach(function(l){ var b = document.createElement('button'); b.type = 'button'; b.className = 'lgo'; b.innerHTML = esc(l.name) + '<small>' + l.total_rosters + ' teams · ' + esc(scoringLabel(l.scoring_settings)) + '</small>'; b.addEventListener('click', function(){ pick(l, b); }); box.appendChild(b); });
      if(ls.length > 1){ var sw = document.createElement('button'); sw.type = 'button'; sw.className = 'lgsw'; sw.textContent = 'Switch league (' + ls.length + ') ▾'; sw.addEventListener('click', function(){ box.classList.remove('picked'); }); box.appendChild(sw); }
      var auto = ls.filter(function(l){ return l.league_id === last; })[0] || ls[0];
      if(auto) pick(auto, box.children[ls.indexOf(auto)]); })
    .catch(function(e){ say('Could not find that Sleeper username. Check the spelling (it is the username, not the team name).', true); console.error(e); })
    .then(function(){ $('#go').disabled = false; });
  }
  function pick(l, btn){
    state.league = l; try{ localStorage.setItem('bs_sleeper_league', l.league_id); }catch(e){}
    Array.prototype.forEach.call($('#leagues').children, function(b){ b.classList.toggle('on', b === btn); });
    $('#leagues').classList.add('picked');
    say('Loading ' + l.name + '…'); out.hidden = true;
    var wk = Math.min(Math.max(state.week || WEEK, 1), 18);
    Promise.all([playersMap(), get('league/' + l.league_id + '/rosters'), get('league/' + l.league_id + '/users'), get('league/' + l.league_id + '/matchups/' + wk).catch(function(){ return []; }), get('players/nfl/trending/add?lookback_hours=24&limit=40').catch(function(){ return []; })])
    .then(function(r){ render(l, r[0], r[1], r[2], r[3], r[4], wk); say(''); })
    .catch(function(e){ say('Sleeper did not answer for that league. Try again in a moment.', true); console.error(e); });
  }

  function render(l, pm, rosters, users, matchups, trending, wk){
    var s = l.scoring_settings || {}; var slots = l.roster_positions || [];
    var me = l.me || (state.user && state.user.user_id); var manual = !!l.manual;
    var mine = rosters.filter(function(r){ return r.owner_id === me || (r.co_owners || []).indexOf(me) >= 0; })[0];
    if(!mine){ say('You are not on a roster in ' + l.name + '.', true); return; }
    var uname = {}; users.forEach(function(u){ uname[u.user_id] = (u.metadata && u.metadata.team_name) || u.display_name; });
    var hot = {}; (trending || []).forEach(function(t){ hot[t.player_id] = t.count; });
    var owned = {}; rosters.forEach(function(r){ (r.players || []).forEach(function(id){ owned[id] = r.roster_id; }); });

    function entry(id){
      var sp = pm[id] || {n: id, t: '', p: '?', i: ''}; var mp = modelFor(sp); var pts = mp ? scorePlayer(mp, s) : null;
      var flag = '';
      if(mp && mp.o === 'BYE'){ pts = 0; flag = 'bye'; }
      else if(badInjury(sp)){ pts = 0; flag = 'out'; }
      else if(mp && !mp.act){ pts = 0; flag = mp.av ? 'out' : 'np'; }
      else if(/Questionable/i.test(sp.i || '') || (mp && mp.q)) flag = 'q';
      if(pts === null && !flag) flag = 'np';
      return {id: id, sp: sp, mp: mp, pos: sp.p === 'DEF' ? 'DEF' : (mp ? mp.p : sp.p), pts: pts || 0, flag: flag, name: sp.p === 'DEF' ? (sp.n + ' D/ST') : sp.n};
    }
    var roster = (mine.players || []).map(entry);
    var pool = roster.filter(function(e){ return e.flag !== 'out' && e.flag !== 'bye'; }).map(function(e){ return {id: e.id, pos: e.pos, pts: e.pts, e: e}; });
    var best = optimal(slots, pool);
    var byId = {}; roster.forEach(function(e){ byId[e.id] = e; });
    var curStarters = (mine.starters || []).filter(function(id){ return id && id !== '0'; }); var noCur = !curStarters.length;
    var curTotal = 0; curStarters.forEach(function(id){ var e = byId[id]; if(e) curTotal += e.pts; });
    var bestTotal = 0; Object.keys(best).forEach(function(i){ bestTotal += best[i].pts; });
    var startSet = {}; Object.keys(best).forEach(function(i){ startSet[best[i].id] = 1; });

    // opponent this week
    var myM = (matchups || []).filter(function(m){ return m.roster_id === mine.roster_id; })[0];
    var oppM = myM ? (matchups || []).filter(function(m){ return m.matchup_id === myM.matchup_id && m.roster_id !== mine.roster_id; })[0] : null;
    var oppRoster = oppM ? rosters.filter(function(r){ return r.roster_id === oppM.roster_id; })[0] : null;
    var oppTotal = 0, oppN = 0;
    if(oppM){ (oppM.starters || []).forEach(function(id){ if(id && id !== '0'){ var e = entry(id); oppTotal += e.pts; oppN++; } }); }
    var oppName = oppRoster ? (uname[oppRoster.owner_id] || 'Opponent') : '';
    var myName = uname[mine.owner_id] || state.user.display_name;

    // tiles
    var nStart = Object.keys(best).length; var sd = Math.sqrt(nStart) * 5.2; // ~5.2 pts of noise per starter, independent
    var wp = oppM ? normalCdf((bestTotal - oppTotal) / (sd * Math.SQRT2)) : null;
    var gain = bestTotal - curTotal;
    $('#tiles').innerHTML =
      '<div><small>Model lineup</small><b>' + f1(bestTotal) + '</b><span>best ' + nStart + ' starters by the model</span></div>' +
      (noCur ? '<div><small>Your current lineup</small><b>—</b><span>' + (manual ? 'star your current starters to see what the swaps are worth' : 'no starters set in Sleeper yet') + '</span></div>' : '<div><small>Your current lineup</small><b>' + f1(curTotal) + '</b><span>' + (gain > 0.05 ? '<span style="color:var(--good)">+' + f1(gain) + ' available</span> with the swaps below' : 'already the model\'s lineup') + '</span></div>') +
      (oppM ? '<div><small>' + esc(oppName) + '</small><b>' + f1(oppTotal) + '</b><span>their current starters, same model</span></div><div class="wp"><small>Win chance</small><b>' + pct(wp) + '</b><span>model lineup vs their current one</span></div>' : '<div><small>Matchup</small><b>—</b><span>no Week ' + wk + ' matchup found</span></div>');
    $('#oppbar').innerHTML = oppM ? '<div class="side"><b>' + f1(bestTotal) + '</b><span>' + esc(myName) + '</span></div><div class="vs">VS</div><div class="side r"><b>' + f1(oppTotal) + '</b><span>' + esc(oppName) + '</span></div>' : '';
    $('#meter').innerHTML = oppM ? '<i style="width:' + (wp * 100).toFixed(1) + '%"></i>' : ''; $('#meter').hidden = !oppM;

    // lineup list
    var li = ''; var changes = 0;
    var benched = curStarters.filter(function(id){ return byId[id] && !startSet[id]; }).map(function(id){ return byId[id]; });
    slots.forEach(function(sl, i){
      if(sl === 'BN' || sl === 'IR' || sl === 'TAXI') return;
      var p = best[i]; var cur = null;
      if(p && curStarters.indexOf(p.id) < 0){ var el = FLEX[sl] || []; var k = -1;
        benched.forEach(function(b, j){ if(k < 0 && b.pos === p.pos) k = j; }); if(k < 0) benched.forEach(function(b, j){ if(k < 0 && el.indexOf(b.pos) >= 0) k = j; });
        if(k >= 0) cur = benched.splice(k, 1)[0]; }
      var wasStarting = p && curStarters.indexOf(p.id) >= 0; var chg = p && !wasStarting && !noCur;
      if(chg) changes++;
      li += '<li class="' + (chg ? 'chg' : '') + '"><span class="slot">' + esc(sl.replace('SUPER_FLEX', 'SFLX').replace('REC_FLEX', 'W/T').replace('WRRB_FLEX', 'W/R')) + '</span>' +
        (p ? '<span class="who"><b>' + esc(p.e.name) + tagFor(p.e) + '</b><span>' + esc(p.pos) + (p.e.mp ? ' · ' + esc(p.e.mp.t) + (p.e.mp.k ? ' · ' + esc(p.e.mp.k) : '') : '') + '</span></span><span class="pts"><b>' + f1(p.pts) + '</b>' + dpill(p.e.mp) + '</span>' : '<span class="who"><b style="color:var(--mute)">nobody healthy fits</b></span><span class="pts"><b>0.0</b></span>') +
        (chg ? '<span class="was">' + (cur ? 'over <b>' + esc(cur.name) + '</b> (' + f1(cur.pts) + (cur.flag === 'out' ? ', out' : cur.flag === 'bye' ? ', bye' : '') + ')' : 'moves into the lineup') + '</span>' : '') + '</li>';
    });
    $('#lineup').innerHTML = li;
    $('#lineupH').innerHTML = '<b>Lineup check</b> ' + (noCur ? '<span class="r">the model\'s lineup for this roster</span>' : changes ? '<span class="r" style="color:var(--good)">' + changes + ' change' + (changes > 1 ? 's' : '') + ' · +' + f1(gain) + ' pts</span>' : '<span class="r">your starters match the model</span>');

    // full roster
    roster.sort(function(a, b){ return b.pts - a.pts || a.name.localeCompare(b.name); });
    $('#roster').innerHTML = roster.map(function(e){ return '<li class="' + (startSet[e.id] ? 'st' : '') + '"><span class="pz">' + esc(e.pos) + '</span><span class="who"><b>' + esc(e.name) + tagFor(e) + '</b><span>' + (e.mp ? esc(e.mp.t) + (e.mp.o ? ' vs ' + esc(e.mp.o) : '') + (e.mp.role && e.mp.role !== e.pos ? ' · ' + esc(e.mp.role) : '') : 'not in the model this week') + '</span></span><span class="pts"><b>' + f1(e.pts) + '</b><small>' + (startSet[e.id] ? 'start' : 'bench') + '</small></span></li>'; }).join('');

    // waivers: best unowned by position, with trending-add flag; compare to your weakest starter at that position
    var worst = {}; Object.keys(best).forEach(function(i){ var p = best[i]; if(!(p.pos in worst) || p.pts < worst[p.pos]) worst[p.pos] = p.pts; });
    var fa = []; Object.keys(pm).forEach(function(id){ if(owned[id]) return; var sp = pm[id]; var mp = modelFor(sp); if(!mp || !mp.act || mp.o === 'BYE' || badInjury(sp)) return; var pts = scorePlayer(mp, s); if(pts > 1) fa.push({id: id, sp: sp, mp: mp, pts: pts, hot: hot[id] || 0}); });
    var wh = ''; ['QB','RB','WR','TE','K','DEF'].forEach(function(pos){
      if(!slots.some(function(sl){ return (FLEX[sl] || []).indexOf(pos) >= 0; })) return;
      var list = fa.filter(function(x){ return x.mp.p === pos; }).sort(function(a, b){ return b.pts - a.pts; }).slice(0, 5);
      if(!list.length) return;
      wh += '<div><h3>' + pos + '</h3><ul>' + list.map(function(x){ var up = (pos in worst) ? x.pts - worst[pos] : null; return '<li><div><b>' + esc(pos === 'DEF' ? x.sp.n + ' D/ST' : x.sp.n) + snapTag(x.mp) + sosTag(x.mp) + (x.hot ? '<span class="bt hot" title="' + x.hot + ' adds on Sleeper in the last 24h">trending</span>' : '') + (/Questionable/i.test(x.sp.i) ? '<span class="bt q">Q</span>' : '') + '</b><span>' + esc(x.mp.t) + ' vs ' + esc(x.mp.o) + (x.mp.role && x.mp.role !== pos ? ' · ' + esc(x.mp.role) : '') + '</span></div><div class="pts">' + f1(x.pts) + (up !== null && up >= 0.05 ? '<small>+' + f1(up) + ' over your ' + pos + (worst[pos] === 0 ? ' hole' : '') + '</small>' : '') + '</div></li>'; }).join('') + '</ul></div>';
    });
    $('#waiv').innerHTML = wh || '<div><p class="note">No free agents clear the model this week.</p></div>';
    $('#waivH').innerHTML = manual ? '<b>Players to target</b> <span class="r">best players not on your roster, by the model · the ones your league mates have not grabbed are your waiver claims</span>' : '<b>Waiver wire</b> <span class="r">best free agents in this league by the model · trending = most-added on Sleeper today</span>';
    $('#waivNote').textContent = manual ? '"Over your X" compares the player to the weakest player the model would start at that spot this week. Check your league\'s free-agent list to see which of these are actually available.' : '"Over your X" compares the free agent to the weakest player the model would start at that spot this week. A one-week number is not a season-long ranking; treat the big gaps as the ones worth a claim.';
    $('#leagueH').innerHTML = '<b>' + esc(l.name) + '</b> <span class="r">' + esc(scoringLabel(s)) + ' · Week ' + wk + (wk !== WEEK ? ' (model is on Week ' + WEEK + ')' : '') + (manual ? ' · built by hand' : '') + '</span>';
    out.hidden = false; out.scrollIntoView({block: 'start', behavior: 'smooth'});
  }
  function sosTag(mp){ var d = mp && mp.sos; if(!d || Math.abs(d) < 0.3) return ''; return '<span class="bt sos ' + (d > 0 ? 'up' : 'dn') + '" title="Strength of schedule: the defenses this player has faced so far made his season numbers look ' + (d > 0 ? 'worse' : 'better') + ' than they are; projection ' + (d > 0 ? 'raised' : 'lowered') + ' ' + Math.abs(d).toFixed(1) + ' pts for this matchup">SOS ' + (d > 0 ? '+' : '\u2212') + Math.abs(d).toFixed(1) + '</span>'; }
  function snapTag(mp){ return mp && mp.sd ? '<span class="bt sd" title="Snap share down: ' + mp.sd[0] + '% of snaps over the last 2 games vs ' + mp.sd[1] + '% for the season; projection trimmed ' + mp.sd[2] + '%">snaps ↓' + mp.sd[2] + '%</span>' : ''; }
  function tagFor(e){ return (e.mp ? snapTag(e.mp) + sosTag(e.mp) : '') + (e.flag === 'out' ? '<span class="bt out">' + (e.sp.i && /IR|PUP|Sus/i.test(e.sp.i) ? esc(e.sp.i) : 'OUT') + '</span>' : e.flag === 'bye' ? '<span class="bt bye">BYE</span>' : e.flag === 'q' ? '<span class="bt q">Q</span>' : e.flag === 'np' ? '<span class="bt np">no proj</span>' : ''); }


  // ---- Manual roster builder (no Sleeper) ----
  var M = {roster: [], starters: {}, opp: []};
  var active = P.map(function(p, i){ return {i: i, p: p}; }).filter(function(x){ return true; });
  function pLabel(p){ return (p.p === 'DEF' ? p.n + ' D/ST' : p.n) + ' · ' + p.p + ' · ' + p.t + (p.o === 'BYE' ? ' · bye' : ''); }
  function searchBox(inputSel, listSel, onPick){
    var inp = $(inputSel), list = $(listSel);
    function show(){
      var q = norm(inp.value); list.innerHTML = ''; if(q.length < 2){ list.hidden = true; return; }
      var hits = active.filter(function(x){ return norm(x.p.n).indexOf(q) >= 0 || (x.p.p === 'DEF' && norm(x.p.t).indexOf(q) >= 0); }).sort(function(a, b){ return (b.p.act - a.p.act) || (b.p.fp - a.p.fp); }).slice(0, 8);
      if(!hits.length){ list.hidden = true; return; }
      hits.forEach(function(x){ var b = document.createElement('button'); b.type = 'button'; b.innerHTML = '<b>' + esc(x.p.p === 'DEF' ? x.p.n + ' D/ST' : x.p.n) + '</b><span>' + esc(x.p.p + ' · ' + x.p.t + (x.p.o && x.p.o !== 'BYE' ? ' vs ' + x.p.o : x.p.o === 'BYE' ? ' · bye' : '') + (x.p.act ? '' : ' · inactive')) + '</span>'; b.addEventListener('mousedown', function(ev){ ev.preventDefault(); onPick(x.i); inp.value = ''; list.hidden = true; inp.focus(); }); list.appendChild(b); });
      list.hidden = false;
    }
    inp.addEventListener('input', show); inp.addEventListener('focus', show); inp.addEventListener('blur', function(){ setTimeout(function(){ list.hidden = true; }, 150); });
    inp.addEventListener('keydown', function(e){ if(e.key === 'Enter'){ e.preventDefault(); var f = list.querySelector('button'); if(f && !list.hidden) f.dispatchEvent(new MouseEvent('mousedown')); } });
  }
  function chips(){
    $('#mroster').innerHTML = M.roster.map(function(i){ var p = P[i]; return '<li class="' + (M.starters[i] ? 'st' : '') + '"><button type="button" class="star" data-i="' + i + '" title="' + (M.starters[i] ? 'in your current lineup (tap to bench)' : 'tap if this player is in your current lineup') + '">' + (M.starters[i] ? '★' : '☆') + '</button><span class="pz">' + esc(p.p) + '</span><span class="who"><b>' + esc(p.p === 'DEF' ? p.n + ' D/ST' : p.n) + '</b><span>' + esc(p.t + (p.o === 'BYE' ? ' · bye' : p.o ? ' vs ' + p.o : '')) + '</span></span><button type="button" class="rm" data-i="' + i + '" aria-label="remove">×</button></li>'; }).join('') || '<li class="empty">No players yet. Search above and add your whole roster, bench included.</li>';
    $('#mopp').innerHTML = M.opp.map(function(i){ var p = P[i]; return '<li><span class="pz">' + esc(p.p) + '</span><span class="who"><b>' + esc(p.p === 'DEF' ? p.n + ' D/ST' : p.n) + '</b><span>' + esc(p.t) + '</span></span><button type="button" class="rm" data-i="' + i + '" aria-label="remove">×</button></li>'; }).join('') || '<li class="empty">Optional: add your opponent\'s starters to get a win chance.</li>';
    var n = M.roster.length, ns = Object.keys(M.starters).length; $('#mcount').textContent = n ? (n + ' players' + (ns ? ' · ' + ns + ' starred as current starters' : '')) : '';
    try{ localStorage.setItem('bs_manual', JSON.stringify({r: M.roster.map(function(i){ return P[i].n + '|' + P[i].t + '|' + P[i].p; }), s: M.roster.filter(function(i){ return M.starters[i]; }).map(function(i){ return P[i].n + '|' + P[i].t + '|' + P[i].p; }), o: M.opp.map(function(i){ return P[i].n + '|' + P[i].t + '|' + P[i].p; }), sc: readScoring(), sl: readSlots()})); }catch(e){}
  }
  $('#mroster').addEventListener('click', function(e){ var b = e.target.closest('button'); if(!b) return; var i = +b.dataset.i; if(b.classList.contains('rm')){ M.roster = M.roster.filter(function(x){ return x !== i; }); delete M.starters[i]; } else { if(M.starters[i]) delete M.starters[i]; else M.starters[i] = 1; } chips(); });
  $('#mopp').addEventListener('click', function(e){ var b = e.target.closest('button.rm'); if(!b) return; var i = +b.dataset.i; M.opp = M.opp.filter(function(x){ return x !== i; }); chips(); });
  searchBox('#msearch', '#mlist', function(i){ if(M.roster.indexOf(i) < 0) M.roster.push(i); chips(); });
  searchBox('#osearch', '#olist', function(i){ if(M.opp.indexOf(i) < 0) M.opp.push(i); chips(); });
  document.querySelectorAll('#mscore .seg').forEach(function(seg){ seg.addEventListener('click', function(e){ var b = e.target.closest('button'); if(!b) return; seg.querySelectorAll('button').forEach(function(x){ x.classList.toggle('on', x === b); }); chips(); }); });
  function segVal(id){ var b = $('#' + id + ' button.on'); return b ? Number(b.dataset.v) : 0; }
  function readScoring(){ return {rec: segVal('sc_rec'), pass_td: segVal('sc_ptd'), bonus_rec_te: segVal('sc_te'), pass_yd: 0.04, rush_yd: 0.1, rec_yd: 0.1, rush_td: 6, rec_td: 6, pass_int: segVal('sc_int')}; }
  function readSlots(){ var o = {}; document.querySelectorAll('#mslots input').forEach(function(i){ o[i.dataset.s] = Math.max(0, Math.min(4, parseInt(i.value || '0', 10) || 0)); }); return o; }
  function slotList(o){ var out = []; ['QB','RB','WR','TE','FLEX','SUPER_FLEX','K','DEF'].forEach(function(k){ for(var i = 0; i < (o[k] || 0); i++) out.push(k); }); return out; }
  document.querySelectorAll('#mslots input').forEach(function(i){ i.addEventListener('change', chips); });
  $('#mgo').addEventListener('click', function(){
    if(!M.roster.length){ say('Add at least a few players first.', true); return; }
    var slots = slotList(readSlots()); if(!slots.length){ say('Set at least one lineup slot.', true); return; }
    var pm = {}; M.roster.concat(M.opp).forEach(function(i){ var p = P[i]; pm['m' + i] = {n: p.n, t: p.t, p: p.p, i: '', mp: p}; });
    var ids = M.roster.map(function(i){ return 'm' + i; }); var st = M.roster.filter(function(i){ return M.starters[i]; }).map(function(i){ return 'm' + i; });
    var oids = M.opp.map(function(i){ return 'm' + i; });
    // everyone else is "available": give the target list the full model pool
    P.forEach(function(p, i){ if(!pm['m' + i]) pm['m' + i] = {n: p.n, t: p.t, p: p.p, i: '', mp: p}; });
    var rosters = [{roster_id: 1, owner_id: 'me', players: ids, starters: st}]; var matchups = [];
    if(oids.length){ rosters.push({roster_id: 2, owner_id: 'opp', players: oids, starters: oids}); matchups = [{roster_id: 1, matchup_id: 1, starters: st}, {roster_id: 2, matchup_id: 1, starters: oids}]; }
    var l = {name: 'My roster', scoring_settings: readScoring(), roster_positions: slots, manual: true, me: 'me'};
    say(''); render(l, pm, rosters, [{user_id: 'me', display_name: 'My roster'}, {user_id: 'opp', display_name: 'Opponent'}], matchups, [], WEEK);
  });
  document.querySelectorAll('.mode button').forEach(function(b){ b.addEventListener('click', function(){ document.querySelectorAll('.mode button').forEach(function(x){ x.classList.toggle('on', x === b); }); var man = b.dataset.m === 'manual'; $('#sleeperBox').hidden = man; $('#manualBox').hidden = !man; out.hidden = true; say(''); try{ localStorage.setItem('bs_team_mode', b.dataset.m); }catch(e){} }); });
  // ---- saved teams (bs_teams: [{id, name, data: same shape as bs_manual, saved}]) ----
  function teams(){ try{ var a = JSON.parse(localStorage.getItem('bs_teams') || '[]'); return Array.isArray(a) ? a : []; }catch(e){ return []; } }
  function writeTeams(a){ try{ localStorage.setItem('bs_teams', JSON.stringify(a)); }catch(e){} }
  function curData(){ try{ return JSON.parse(localStorage.getItem('bs_manual') || 'null'); }catch(e){ return null; } }
  var curTeam = null; try{ curTeam = localStorage.getItem('bs_team_cur') || null; }catch(e){}
  function renderTeams(){ var a = teams(), ul = $('#msaved'); if(!ul) return;
    ul.innerHTML = a.length ? a.map(function(t){ var n = (t.data && t.data.r || []).length; return '<li class="' + (t.id === curTeam ? 'on' : '') + '"><b>' + esc(t.name) + '</b><span>' + n + ' players' + (t.data && t.data.o && t.data.o.length ? ' · opponent set' : '') + '</span><button type="button" data-load="' + esc(t.id) + '">' + (t.id === curTeam ? 'Open' : 'Load') + '</button><button type="button" class="rm" data-del="' + esc(t.id) + '" aria-label="delete">×</button></li>'; }).join('') : '<li class="none">No saved teams yet.</li>'; }
  $('#msave').addEventListener('click', function(){ var d = curData(); if(!d || !(d.r || []).length){ say('Add some players before saving.', true); return; }
    var a = teams(), t = a.filter(function(x){ return x.id === curTeam; })[0];
    var name = prompt(t ? 'Save changes to this team (or rename it):' : 'Name this team (e.g. Work league, Home league):', t ? t.name : 'Team ' + (a.length + 1)); if(name === null) return; name = name.trim() || (t ? t.name : 'Team ' + (a.length + 1));
    if(t){ t.name = name; t.data = d; t.saved = Date.now(); } else { t = {id: 't' + Date.now().toString(36), name: name, data: d, saved: Date.now()}; a.push(t); curTeam = t.id; try{ localStorage.setItem('bs_team_cur', curTeam); }catch(e){} }
    writeTeams(a); renderTeams(); say('Saved "' + name + '".' + (window.bsAccount && window.bsAccount.user ? ' It follows you to every device.' : ' Sign in to keep it on every device.')); });
  $('#mnew').addEventListener('click', function(){ M.roster = []; M.starters = {}; M.opp = []; curTeam = null; try{ localStorage.removeItem('bs_team_cur'); }catch(e){} chips(); renderTeams(); out.hidden = true; say(''); $('#msearch').focus(); });
  $('#msaved').addEventListener('click', function(e){ var b = e.target.closest('button'); if(!b) return;
    if(b.dataset.del){ if(!confirmDel(b)) return; writeTeams(teams().filter(function(x){ return x.id !== b.dataset.del; })); if(curTeam === b.dataset.del){ curTeam = null; try{ localStorage.removeItem('bs_team_cur'); }catch(e){} } renderTeams(); return; }
    if(b.dataset.load){ var t = teams().filter(function(x){ return x.id === b.dataset.load; })[0]; if(!t) return; M.roster = []; M.starters = {}; M.opp = []; restoreManual(t.data); curTeam = t.id; try{ localStorage.setItem('bs_team_cur', curTeam); }catch(e){} chips(); renderTeams(); $('#mgo').click(); } });
  function confirmDel(b){ if(b.dataset.armed){ return true; } b.dataset.armed = '1'; b.textContent = 'Delete?'; setTimeout(function(){ delete b.dataset.armed; b.textContent = '×'; }, 2500); return false; }
  function restoreManual(mv){ if(!mv) return;
    var find = function(k){ var a = k.split('|'); for(var i = 0; i < P.length; i++){ if(P[i].n === a[0] && P[i].t === a[1] && P[i].p === a[2]) return i; } for(var j = 0; j < P.length; j++){ if(P[j].n === a[0] && P[j].p === a[2]) return j; } return -1; };
    M.roster = (mv.r || []).map(find).filter(function(i){ return i >= 0; }); (mv.s || []).map(find).forEach(function(i){ if(i >= 0) M.starters[i] = 1; }); M.opp = (mv.o || []).map(find).filter(function(i){ return i >= 0; });
    if(mv.sc){ [['sc_rec', mv.sc.rec], ['sc_ptd', mv.sc.pass_td], ['sc_te', mv.sc.bonus_rec_te], ['sc_int', mv.sc.pass_int]].forEach(function(x){ document.querySelectorAll('#' + x[0] + ' button').forEach(function(b){ b.classList.toggle('on', Number(b.dataset.v) === Number(x[1])); }); }); }
    if(mv.sl){ document.querySelectorAll('#mslots input').forEach(function(i){ if(i.dataset.s in mv.sl) i.value = mv.sl[i.dataset.s]; }); } }
  document.addEventListener('bs-account', renderTeams);
  // restore a hand-built roster
  try{ var mv = JSON.parse(localStorage.getItem('bs_manual') || 'null'); if(mv){
    var find = function(k){ var a = k.split('|'); for(var i = 0; i < P.length; i++){ if(P[i].n === a[0] && P[i].t === a[1] && P[i].p === a[2]) return i; } return -1; };
    M.roster = (mv.r || []).map(find).filter(function(i){ return i >= 0; }); (mv.s || []).map(find).forEach(function(i){ if(i >= 0) M.starters[i] = 1; }); M.opp = (mv.o || []).map(find).filter(function(i){ return i >= 0; });
    if(mv.sc){ [['sc_rec', mv.sc.rec], ['sc_ptd', mv.sc.pass_td], ['sc_te', mv.sc.bonus_rec_te], ['sc_int', mv.sc.pass_int]].forEach(function(x){ document.querySelectorAll('#' + x[0] + ' button').forEach(function(b){ b.classList.toggle('on', Number(b.dataset.v) === Number(x[1])); }); }); }
    if(mv.sl){ document.querySelectorAll('#mslots input').forEach(function(i){ if(i.dataset.s in mv.sl) i.value = mv.sl[i.dataset.s]; }); }
  } }catch(e){}
  chips(); renderTeams();
  try{ if(localStorage.getItem('bs_team_mode') === 'manual' && !new URLSearchParams(location.search).get('u')) $('.mode button[data-m="manual"]').click(); }catch(e){}
  try{ var saved = localStorage.getItem('bs_sleeper_user'); if(saved){ $('#user').value = saved; } }catch(e){}
  var q = new URLSearchParams(location.search).get('u'); if(q){ $('#user').value = q; connect(); }
})();
"""

body = f'''<div class="tm-wrap">
 <section class="panel">
  <div class="mode"><button type="button" class="on" data-m="sleeper">Import from Sleeper</button><button type="button" data-m="manual">No Sleeper? Build it by hand</button></div>
  <div id="sleeperBox">
  <h2><b>Connect your Sleeper</b> <span class="r">read-only · no password · nothing leaves your browser except the Sleeper lookups</span></h2>
  <div class="connect">
   <label for="user">Sleeper username</label>
   <input id="user" type="text" autocomplete="username" autocapitalize="none" spellcheck="false" placeholder="your Sleeper username (not the team name)">
   <button type="button" id="go">Grade my team</button>
   <p class="how">Sleeper publishes leagues, rosters and scoring rules through a public read-only feed, so there is nothing to log into. We pull your leagues, apply <b>your league's scoring</b> (PPR, half, TE premium, 6-point passing TDs, all of it) to the model's stat projections for every player, then show the lineup the model would start, what it is worth over your current one, and the best free agents in your league.</p>
  </div>
  <div class="leagues" id="leagues"></div>
  </div>
  <div id="manualBox" hidden>
   <h2><b>Build your roster</b> <span class="r">any platform · save as many teams as you play · synced when you sign in</span></h2>
   <div class="mstep"><span class="lab">1 · Scoring</span><div id="mscore">
    <span class="seg" id="sc_rec"><button type="button" data-v="1" class="on">Full PPR</button><button type="button" data-v="0.5">Half PPR</button><button type="button" data-v="0">Standard</button></span>
    <span class="seg" id="sc_ptd"><button type="button" data-v="4" class="on">4-pt pass TD</button><button type="button" data-v="6">6-pt pass TD</button></span>
    <span class="seg" id="sc_te"><button type="button" data-v="0" class="on">No TE premium</button><button type="button" data-v="0.5">TE +0.5</button><button type="button" data-v="1">TE +1</button></span>
    <span class="seg" id="sc_int"><button type="button" data-v="-1" class="on">INT −1</button><button type="button" data-v="-2">INT −2</button><button type="button" data-v="0">INT 0</button></span>
   </div></div>
   <div class="mstep"><span class="lab">2 · Lineup slots</span><div id="mslots">
    <label>QB <input type="number" min="0" max="4" value="1" data-s="QB"></label><label>RB <input type="number" min="0" max="4" value="2" data-s="RB"></label><label>WR <input type="number" min="0" max="4" value="2" data-s="WR"></label><label>TE <input type="number" min="0" max="4" value="1" data-s="TE"></label><label>FLEX <input type="number" min="0" max="4" value="1" data-s="FLEX"></label><label>SUPERFLEX <input type="number" min="0" max="2" value="0" data-s="SUPER_FLEX"></label><label>K <input type="number" min="0" max="2" value="1" data-s="K"></label><label>DEF <input type="number" min="0" max="2" value="1" data-s="DEF"></label>
   </div></div>
   <div class="mstep"><span class="lab">3 · Your players</span><div class="srch"><input id="msearch" type="search" autocomplete="off" placeholder="type a name… e.g. Bijan, JSN, Ravens D"><div class="slist" id="mlist" hidden></div><span class="cnt" id="mcount"></span></div>
    <ul class="chips" id="mroster"></ul>
    <p class="hint">Add everyone, bench included. Tap the ☆ next to the players who are in your lineup right now and the model will show you what each swap is worth; leave them blank and it just builds the best lineup.</p></div>
   <div class="mstep"><span class="lab">4 · Opponent <small>(optional)</small></span><div class="srch"><input id="osearch" type="search" autocomplete="off" placeholder="your opponent's starters, for a win chance"><div class="slist" id="olist" hidden></div></div>
    <ul class="chips" id="mopp"></ul></div>
   <div class="connect" style="padding-top:4px"><button type="button" id="mgo">Grade my roster</button><button type="button" id="msave" class="ghost">Save team</button><button type="button" id="mnew" class="ghost">New team</button></div>
   <div class="mstep" id="msavedWrap"><span class="lab">Saved teams</span><div><ul class="saved" id="msaved"></ul><p class="hint" id="msavedHint">Save every team you play - a home league, a work league, a best-ball - and switch between them here. Signed in, they follow you to every device and show on My BetSweep.</p></div></div>
  </div>
  <div class="msg" id="msg" hidden></div>
 </section>
 <div id="out" hidden>
  <section class="panel" style="margin-bottom:14px">
   <h2 id="leagueH"></h2>
   <div class="tiles" id="tiles"></div>
   <div class="oppbar" id="oppbar"></div>
   <div class="meter" id="meter" hidden></div>
  </section>
  <section class="panel" style="margin-bottom:14px">
   <h2 id="lineupH"><b>Lineup check</b></h2>
   <ul class="lineup" id="lineup"></ul>
   <p class="note">Green bar = a player the model would start who is not in your lineup right now. Points are the model's projection under this league's scoring. Players Sleeper lists as Out, IR or Doubtful, players on bye, and players the model has inactive are scored 0 and never recommended. Sleeper has no public way to set a lineup from here, so make the swaps in the Sleeper app.</p>
  </section>
  <section class="panel" style="margin-bottom:14px">
   <h2><b>Your roster</b> <span class="r">highlighted = model starter</span></h2>
   <ul class="roster" id="roster"></ul>
  </section>
  <section class="panel">
   <h2 id="waivH"><b>Waiver wire</b></h2>
   <div class="waiv" id="waiv"></div>
   <p class="note" id="waivNote"></p>
  </section>
 </div>
</div>
<script>window.__BS = {json.dumps(DATA, separators=(",", ":"))};</script>
<script>{TEAM_JS}</script>'''

page = (open(os.path.join(HERE, "template.html")).read()
        .replace("<title>BetSweep Matchup Boards</title>", "<title>BetSweep Fantasy</title>")
        .replace("<h1>Week {{WEEK}} · <b>Matchup Boards</b></h1>", "<h1>Week {{WEEK}} · <b>Fantasy</b></h1>")
        .replace("</style>", TEAM_CSS + "\n</style>", 1)
        .replace("{{DESC}}", f"Import your Sleeper league and the model grades it: the lineup it would start under your league's scoring, how many points you are leaving on the bench, your matchup odds, and the best free agents available. {n_act} players projected for Week {WEEK}. Built {stamp} CT.")
        .replace("{{NAV}}", '<a href="https://claude.ai/artifact/RTTqiN3sdMHGgojimQ9hZv">← This week\'s boards</a>').replace("{{CARDS}}", body)
        .replace("{{LOGO}}", LOGO).replace("{{BANNER}}", BANNER).replace("{{WEEK}}", str(WEEK)).replace("{{STAMP}}", stamp).replace("{{ARCHIVE}}", ""))
page = re.sub(r'<div class="key">.*?</dl>\n</div>\n', '', page, count=1, flags=re.S)
page = page.replace('<div class="grid">', '<div class="grid" style="display:block">', 1)
out = os.path.join(OUT, "team.html"); open(out, "w").write(page)
print(f"wrote {out}: {len(PLAYERS)} players ({n_act} active), week {WEEK}, {len(page)//1024} KB")
