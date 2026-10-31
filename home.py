"""Home page sections for betsweep.co (called from build_site.py's landing()).

Everything here is read from files the rebuild already produces - nothing is re-modelled:
  in/bestlegs.json        'V2 - Best Legs' (the sheet's own clean-leg list: STRONG VALUE / VALUE, warnings column)   -> Top plays
  out/builder_data.json   every priced leg (FanDuel links, kickoffs, game cards)                                        -> TD plays, game lines, slate, links
  out/best_parlays.json   the boards' best same-game parlay per game                                                  -> Best parlay
  in/scorecard.json + in/legsnaps.json   season record (same maths as build_season.py)                                  -> Track record
Games that have kicked off drop out of the plays lists in the browser (ESPN feed via live.py, kickoff fallback), and the
slate shows LIVE / FINAL badges, so the page stays honest on game day without a rebuild.
"""
import calib as CALIB
import json, math, os, html
from collections import defaultdict

E = html.escape

def _num(x):
    try: return float(str(x).replace("%", "").replace(",", "").replace("+", ""))
    except Exception: return None

def _pct(v):
    v = _num(v)
    return None if v is None else (v / 100 if v > 1.5 else v)

def odds_str(o):
    o = _num(o)
    if o is None: return ""
    return f"+{int(o)}" if o > 0 else f"{int(o)}"

def kick_short(k):   # "Sun 10/18 8:30 AM" -> "Sun 8:30 AM"
    p = (k or "").split()
    return " ".join([p[0]] + p[2:]) if len(p) >= 3 and "/" in p[1] else (k or "")

def load(IN, OUT):
    D = {}
    try: D["bd"] = json.load(open(os.path.join(OUT, "builder_data.json")))
    except Exception: D["bd"] = {"games": [], "legs": [], "week": 0}
    try: D["best"] = json.load(open(os.path.join(IN, "bestlegs.json")))["values"]
    except Exception: D["best"] = []
    try: D["bp"] = json.load(open(os.path.join(OUT, "best_parlays.json")))
    except Exception: D["bp"] = []
    try: D["score"] = json.load(open(os.path.join(IN, "scorecard.json")))["values"]
    except Exception: D["score"] = []
    try: D["legsnaps"] = json.load(open(os.path.join(IN, "legsnaps.json")))["values"]
    except Exception: D["legsnaps"] = []
    return D

# ---------- risk flags (owner 10/21-10/22: Raymond, Hutchinson, Lloyd) ----------
# A player whose ROLE is at risk is never a home-page pick: a bad flag on the leg itself (fh), or a bad role / usage flag on the player
# (builder "pf"): target or backfield competition, a teammate rising, limited role, snaps / carries / targets down, cold last 3,
# a fill-in fading. Context flags (tough matchup, low total, main-line hit rate) stay on the boards as notes and do not remove a pick -
# they describe the line, which the price already carries. Trail script removes rushing legs only.
ROLE_RISK = ("Target competition", "Backfield competition", "Rising", "Limited", "Snaps down", "Role Down", "Carries down", "Targets down",
             "Cold L3", "Fill-in", "Usage falling", "Boom/bust")
def _flagged(D, pl, l=None, m=None):
    if any(h[0] == "bad" for h in ((l or {}).get("fh") or [])): return True
    m = m or (l or {}).get("m") or ""
    for h in ((D["bd"].get("pf") or {}).get(pl) or []):
        if h[0] != "bad": continue
        if str(h[1]).startswith(ROLE_RISK): return True
        if h[1] == "Trail script" and m in ("Rushing Yards", "Rush + Rec Yards", "Anytime TD"): return True
    return False

# ---------- top plays (sheet's Best Legs, one per player, FanDuel link from the builder) ----------
def top_plays(D, n=8):
    bd = D["bd"]; games = {g["gid"]: g for g in bd["games"]}
    team_gid = {}
    for g in bd["games"]: team_gid[g["a"]] = g["gid"]; team_gid[g["b"]] = g["gid"]
    legs_by = {}
    for l in bd["legs"]:
        if l.get("alt") or l.get("gl"): continue
        legs_by[(l["pl"], l["m"], float(l["ln"]))] = l
    rows = D["best"][1:] if D["best"] and D["best"][0] and str(D["best"][0][0]).strip().lower() == "player" else D["best"]
    seen, out = set(), []
    for r in rows:
        r = list(r) + [""] * (11 - len(r))
        pl, mk, ln, o, mp, bp, ed, verdict, warn, game, kick = r[:11]
        if not pl or pl in seen or str(warn).strip(): continue
        if "VALUE" not in str(verdict).upper(): continue
        if _flagged(D, pl, legs_by.get((pl, mk, _num(ln))), mk): continue
        ln_f = _num(ln); mp_f = _pct(mp); bp_f = _pct(bp)
        if ln_f is None or mp_f is None: continue
        l = legs_by.get((pl, mk, ln_f))
        if l:   # selection rules learned from grading (week 6): role risks, cold streaks, QB rushing and above-projection lines lose to the price
            if any(k in (l.get("w") or "") for k in ("Snap share slipping", "Next man up", "Fill-in starter", "Trending down", "Usage falling")): continue
            if l.get("ret") or any(h[1] == "Returning" for h in (l.get("fh") or [])): continue   # returning starter priced off last year's share: short-sample, builder only
            if mk == "Rushing Yards" and l.get("pos") == "QB": continue
            if mk in ("Receiving Yards", "Passing Yards") and l.get("proj") and ln_f > 0.85 * float(l["proj"]): continue
            if mk == "Rushing Yards" and l.get("proj") and ln_f > 0.75 * float(l["proj"]): continue   # rushing projections ran hot in week 6 even at floor rungs
            if mk == "Rush + Rec Yards" and l.get("proj") and ln_f > 0.8 * float(l["proj"]): continue
        if mk == "Longest Reception": continue   # no edge in this market yet (week 6: 0-for-6 at edge >= +10, fades hit 47%)
        sp_f = CALIB.shrink(mp_f, bp_f)   # the number the whole site shows (calib.py): raw model blended toward the price
        if bp_f is not None and sp_f < 0.55: continue   # the leg must still be likely when the price gets its vote
        gid = l["g"] if l else None
        if not gid:   # fall back to the team in the game text
            for ab, gd in team_gid.items():
                g = games[gd]
                if g.get("na") and g["na"] in game or g.get("nb") and g["nb"] in game: gid = gd; break
        g = games.get(gid, {})
        seen.add(pl)
        out.append({"pl": pl, "pos": (l or {}).get("pos", ""), "tm": (l or {}).get("tm", ""), "opp": (l or {}).get("opp", ""), "m": mk, "ln": ln_f, "o": o,
                    "p": sp_f, "bk": bp_f, "e": (sp_f - bp_f) if bp_f is not None else _pct(ed), "raw_p": mp_f, "gid": gid or "", "ko": g.get("ko"), "kick": kick_short(kick) or g.get("kick", ""),
                    "fd": ((l or {}).get("fd") or {}).get("u"), "bks": (l or {}).get("bks"), "ba": (l or {}).get("ba"), "gl": (l or {}).get("gl"), "fh": (l or {}).get("fh") or [], "n": (l or {}).get("n"), "dr": (l or {}).get("dr")})
        if len(out) >= n: break
    return out

import booklinks as BL   # DraftKings / Hard Rock links (exact rung or the book's nearest line), owner 10/22
def leg_line(m, ln):
    if m in ("Anytime TD", "First TD", "2+ TD", "3+ TD"): return m
    if str(m).startswith("Under "): return f"under {float(ln):g} {m[6:].lower()}"   # FanDuel main-line unders (owner 10/27)
    if m in ("Total", "Spread", "Moneyline"): return {"Total": "game total", "Spread": "spread", "Moneyline": "moneyline"}[m]   # the name already carries the line ("Under 51.5", "CLE +6.5")
    if m == "Receptions": return f"{int(ln)}+ receptions" if float(ln).is_integer() else f"over {ln} receptions"
    if m == "Rush + Rec Yards": return f"{int(ln) if float(ln).is_integer() else ln}+ rush + rec yards"
    return f"{int(ln) if float(ln).is_integer() else ln}+ {m.lower()}" if ln else m

def leg_key(pl, m, ln):
    """the builder's slip key (player|market|rounded line) - must match legKey() in build_builder.py / template.html"""
    try: ln = float(ln)
    except Exception: ln = 1.0
    return f"{pl}|{m}|{int(math.floor((ln or 1) + 0.5))}"   # JS Math.round (Python round() would send 42.5 to 42, the builder to 43)
def build_href(gid, legs):
    """/build/ link that drops these legs into the reader's slip on arrival (builder reads ?add=key&add=key, then clears it)."""
    from urllib.parse import quote
    q = "&".join("add=" + quote(leg_key(pl, m, ln), safe="") for pl, m, ln in legs if pl and m)
    return "/build/" + (f"?{q}" if q else "") + (f"#g-{gid}" if gid else "")

def play_card(x, cls=""):
    hist = next((h for h in x.get("fh", []) if h[0] in ("good", "info", "bad") and "/" in str(h[1])), None)   # the this-season hit pill only
    hist_html = f'<span class="hist {hist[0]}">{E(hist[1])}</span>' if hist else ""
    sub = " · ".join(s for s in [E(x.get("pos", "")), (E(x["tm"]) + " vs " + E(x["opp"])) if x.get("tm") and x.get("opp") else E(x.get("gid", "").replace("-", " @ ")), E(x.get("kick", ""))] if s)
    bb = BL.best(x); btn = (f'<a class="fdb{" best" if bb == "fd" and (x.get("bks") or {}) else ""}" href="{E(x["fd"])}" target="_blank" rel="noopener">Add to FanDuel</a>' if x.get("fd") else "") + BL.buttons([x], price=True)
    more = f'<a class="more" href="{E(build_href(x.get("gid"), [(x["pl"], x["m"], x["ln"])]))}" title="Open the parlay builder with this leg in your slip">+ Builder</a>' 
    e = x.get("e"); ecls = "pos" if (e or 0) > 0 else "neg"
    proj_html = f'<small class="proj">proj {float(x["proj"]):g}</small>' if x.get("proj") and cls == "floor" else ""
    return (f'<article class="play {cls}" data-gid="{E(x.get("gid",""))}" data-ko="{x.get("ko") or ""}">'
            f'<div class="who"><b>{E(x["pl"])}</b><small>{sub}</small></div>'
            f'<div class="what">{E(leg_line(x["m"], x["ln"]))}{proj_html}<span class="odds">{E(odds_str(x["o"]))}</span></div>'
            f'<div class="nums"><span><i>Model</i>{x["p"]*100:.0f}%</span><span><i>Price needs</i>{(x["bk"] or 0)*100:.0f}%</span><span class="edge {ecls}"><i>Edge</i>{(e or 0)*100:+.0f}</span></div>'
            f'<div class="foot">{hist_html}{more}{btn}</div></article>')

# ---------- anytime TD plays and game lines from the builder legs ----------
def td_plays(D, n=4):
    out = []
    for l in D["bd"]["legs"]:
        if l["m"] != "Anytime TD" or l.get("alt") or l.get("risk"): continue
        if l["p"] < 0.2 or (l.get("o") or 0) > 600: continue   # no longshots; the price cap keeps it to real role players
        if abs(l["e"]) > 0.025: continue   # week 6: TD legs where the raw model beat the price by 5+ went 2-for-32 (2.5 after the calib.py blend); show only legs the model and FanDuel agree on
        if _flagged(D, l["pl"], l): continue
        if any(k in (l.get("w") or "") for k in ("Snap share slipping", "Next man up", "Fill-in starter", "Rising:")): continue
        out.append(l)
    out.sort(key=lambda l: -(l["bk"] or 0))   # by the price-implied chance, model as the tiebreak
    seen, res = set(), []
    for l in out:
        if l["pl"] in seen: continue
        seen.add(l["pl"]); res.append(l)
        if len(res) >= n: break
    games = {g["gid"]: g for g in D["bd"]["games"]}
    return [{"pl": l["pl"], "pos": l["pos"], "tm": l["tm"], "opp": l["opp"], "m": l["m"], "ln": 1, "o": l["o"], "p": l["p"], "bk": l["bk"], "e": l["e"], "gid": l["g"],
             "ko": games.get(l["g"], {}).get("ko"), "kick": games.get(l["g"], {}).get("kick", ""), "fd": (l.get("fd") or {}).get("u"), "bks": l.get("bks"), "ba": l.get("ba"), "gl": l.get("gl"), "fh": l.get("fh") or [], "n": l.get("n")} for l in res]

# ---------- floor legs: the parlay-anchor strategy (primary role, line at 30-60% of projection, fair price, no role risk, no cold streak; ranked by probability) ----------
FLOOR_MIN = {"Receiving Yards": 40, "Receptions": 3, "Rushing Yards": 50, "Rush + Rec Yards": 60}
_HAS_RR = set()
def _two_way(legs):   # players whose Rush + Rec leg should replace rushing-only floors (receiving >= 20% of the combined projection)
    _HAS_RR.clear(); _HAS_RR.update(l["pl"] for l in legs if l.get("m") == "Rush + Rec Yards" and (l.get("rr") or {}).get("rec_share", 0) >= 0.2)
def is_floor(l):
    m = l.get("m"); proj = l.get("proj"); o = l.get("o")
    if m not in FLOOR_MIN or l.get("alt") or l.get("gl") or not proj or float(proj) < FLOOR_MIN[m]: return False
    if m == "Rushing Yards" and l["pl"] in _HAS_RR: return False
    if m == "Rush + Rec Yards" and (l.get("rr") or {}).get("rec_share", 0) < 0.2: return False
    d = float(l["ln"]) / float(proj)
    if not (0.3 < d <= 0.6): return False
    if o is None or o > -130 or o < -400: return False
    if l["p"] < (l.get("bk") or 0) - 0.025: return False   # shown % is the calib.py blend; -2.5 here == raw model -5
    if m == "Rushing Yards" and l.get("pos") == "QB": return False
    if any(k in (l.get("w") or "") for k in ("Snap share slipping", "Next man up", "Fill-in", "Rising:", "Trending down", "Usage falling")): return False   # cold streak excluded 2026-10-20 (Raymond 2+ rec, Week 6)
    if any(h[0] == "bad" for h in (l.get("fh") or [])): return False
    if l.get("ret"): return False   # returning starter, 2025-share projection
    return True
def floor_plays(D, n=8):
    games = {g["gid"]: g for g in D["bd"]["games"]}
    _two_way(D["bd"]["legs"]); cands = [l for l in D["bd"]["legs"] if is_floor(l) and not _flagged(D, l["pl"], l)]
    cands.sort(key=lambda l: (-l["p"], -(l.get("bk") or 0)))   # l["p"] is already the calib.py blend
    seen, res = set(), []
    for l in cands:
        if l["pl"] in seen: continue
        seen.add(l["pl"]); res.append(l)
        if len(res) >= n: break
    return [{"pl": l["pl"], "pos": l["pos"], "tm": l["tm"], "opp": l["opp"], "m": l["m"], "ln": l["ln"], "o": l["o"], "p": l["p"], "bk": l["bk"], "e": l["e"], "gid": l["g"], "proj": l.get("proj"),
             "ko": games.get(l["g"], {}).get("ko"), "kick": games.get(l["g"], {}).get("kick", ""), "fd": (l.get("fd") or {}).get("u"), "bks": l.get("bks"), "ba": l.get("ba"), "gl": l.get("gl"), "fh": l.get("fh") or [], "n": l.get("n")} for l in res]

def floor_slip(D, fl, n=5):
    """A ready slip from the floor list: receiving legs only, one per game, with the FanDuel multi-leg link."""
    bd = D["bd"]; by = {}
    for l in bd["legs"]:
        if l.get("alt") or l.get("gl"): continue
        by[(l["pl"], l["m"], float(l["ln"]))] = l
    legs, seen_g = [], set()
    for x in fl:
        if x["m"] not in ("Receiving Yards", "Receptions") or x["gid"] in seen_g: continue
        l = by.get((x["pl"], x["m"], float(x["ln"])))
        if not l or not (l.get("fd") or {}).get("m"): continue
        seen_g.add(x["gid"]); legs.append((x, l))
        if len(legs) >= n: break
    if len(legs) < 3: return None
    dec = 1.0; pm = 1.0; pb = 1.0
    for x, _ in legs:
        o = float(x["o"]); dec *= (1 + o / 100) if o > 0 else (1 + 100 / -o); pm *= x["p"]; pb *= (x["bk"] or 0)
    url = "https://sportsbook.fanduel.com/addToBetslip?" + "&".join(f"marketId[{i}]={l['fd']['m']}&selectionId[{i}]={l['fd']['s']}" for i, (_, l) in enumerate(legs))
    return {"legs": [x for x, _ in legs], "bl": [l for _, l in legs], "dec": dec, "pm": pm, "pb": pb, "url": url, "first_ko": min((x.get("ko") or 0) for x, _ in legs) or None, "gids": [x["gid"] for x, _ in legs]}

def floor_slip_block(fs):
    if not fs: return ""
    legs = "".join(f'<li><b>{E(x["pl"])}</b><span>{E(leg_line(x["m"], x["ln"]))} <small>{E(odds_str(x["o"]))}</small></span><em>{x["p"]*100:.0f}%</em></li>' for x in fs["legs"])
    return (f'<div class="parlay fslip" data-gid="{E(fs["gids"][0])}" data-ko="{fs.get("first_ko") or ""}"><div class="phd"><small>Floor {len(fs["legs"])} · ready slip</small><h3>One anchor per game</h3>'
            f'<p>{len(fs["legs"])} fair-priced floor legs across {len(fs["legs"])} games, about <b>{E(dec_to_us(fs["dec"]))}</b> on FanDuel. Straight multiplication gives it <b>{fs["pm"]*100:.0f}%</b> by the model and <b>{fs["pb"]*100:.0f}%</b> by the price - these legs are calibrated, not edges, so treat it as a fun slip at fair odds and swap in your own reads.</p></div>'
            f'<ul class="plegs">{legs}</ul><div class="pfoot"><a class="fdb" href="{E(fs["url"])}" target="_blank" rel="noopener">Add all to FanDuel</a>{BL.buttons(fs.get("bl") or [], single=False)}<a class="more" href="{E(build_href(fs["gids"][0], [(x["pl"], x["m"], x["ln"]) for x in fs["legs"]]))}">Edit in the builder →</a></div></div>')

# ---------- next man up: thinned rooms (flags.py "Room thinned"), with the cheapest volume leg FanDuel has on him ----------
def nextman_plays(D, n=6):
    games = {g["gid"]: g for g in D["bd"]["games"]}
    PF = D["bd"].get("pf") or {}
    by_pl = {}
    for l in D["bd"]["legs"]:
        if l.get("alt") or l.get("gl"): continue
        rt = next((h for h in (l.get("fh") or []) + PF.get(l["pl"], []) if h[1] == "Room thinned"), None)
        if not rt: continue
        by_pl.setdefault(l["pl"], {"legs": [], "flag": rt, "pos": l["pos"], "tm": l["tm"], "opp": l["opp"], "gid": l["g"]})["legs"].append(l)
    out = []
    for pl, d in by_pl.items():
        if d["flag"][0] != "good": continue   # first in line only
        if _flagged(D, pl): continue   # first in line, but another risk flag (a starter returning, trail script...) keeps him off the picks
        pref = ({"Rushing Yards": 0, "Rush + Rec Yards": 1, "Receptions": 2, "Receiving Yards": 3} if d["pos"] == "RB" else {"Receptions": 0, "Receiving Yards": 1, "Longest Reception": 3})   # volume legs only, never touchdowns
        cands = [l for l in d["legs"] if l["m"] in pref and (l.get("o") or 0) >= -300]
        cands.sort(key=lambda l: (pref[l["m"]], float(l["ln"])))
        best = cands[0] if cands else None
        g = games.get(d["gid"], {})
        out.append({"pl": pl, "pos": d["pos"], "tm": d["tm"], "opp": d["opp"], "gid": d["gid"], "ko": g.get("ko"), "kick": g.get("kick", ""), "txt": d["flag"][2],
                    "leg": best and {"pl": pl, "m": best["m"], "ln": best["ln"], "o": best["o"], "p": best["p"], "bk": best["bk"], "fd": (best.get("fd") or {}).get("u"), "bks": best.get("bks"), "ba": best.get("ba")}})
    out.sort(key=lambda x: (x["leg"] is None, -(x["leg"]["bk"] if x["leg"] else 0)))
    return out[:n]

def nextman_block(xs):
    if not xs: return ""
    cards = []
    for x in xs:
        sub = " · ".join(s for s in [E(x["pos"]), f'{E(x["tm"])} vs {E(x["opp"])}', E(x.get("kick", ""))] if s)
        if x["leg"]:
            l = x["leg"]; what = f'{E(leg_line(l["m"], l["ln"]))} <span class="odds">{E(odds_str(l["o"]))}</span>'
            nums = f'<div class="nums"><span><i>Model</i>{l["p"]*100:.0f}%</span><span><i>Price needs</i>{(l["bk"] or 0)*100:.0f}%</span><span><i>Room math</i>{E(_room_pct(x["txt"]))}</span></div>'
            bb = BL.best(l); btn = (f'<a class="fdb{" best" if bb == "fd" and (l.get("bks") or {}) else ""}" href="{E(l["fd"])}" target="_blank" rel="noopener">Add to FanDuel</a>' if l.get("fd") else "") + BL.buttons([l], price=True)
        else:
            what = 'No FanDuel line in the pull yet <span class="odds">check the app</span>'; nums = f'<div class="nums"><span><i>Room math</i>{E(_room_pct(x["txt"]))}</span></div>'; btn = ""
        cards.append(f'<article class="play nm" data-gid="{E(x["gid"])}" data-ko="{x.get("ko") or ""}"><div class="who"><b>{E(x["pl"])}</b><small>{sub}</small></div>'
                     f'<div class="what">{what}</div>{nums}<p class="why">{E(x["txt"])}</p><div class="foot"><a class="more" href="{E(build_href(x["gid"], [(x["pl"], x["leg"]["m"], x["leg"]["ln"])] if x["leg"] else []))}" title="Open the parlay builder with this leg in your slip">{"+ Builder" if x["leg"] else "Builder →"}</a>{btn}</div></article>')
    return "".join(cards)

def _room_pct(txt):
    import re as _re
    m = _re.search(r"2\+ catches ~(\d+)%", txt)
    if m: return f"2+ rec ~{m.group(1)}%"
    m = _re.search(r"that is ~([\d.]+) (targets|carries)", txt)
    return f"~{m.group(1)} {m.group(2)}" if m else "—"

def gl_plays(D, n=3):
    # Week 6: the game model went 7-7 on moneylines while the closing favourites went 9-5, lost both games where it broke from the market,
    # and missed margins by 6.9 pts vs the line's 6.4. Until it beats the closing line out of sample, a game line is shown here only when
    # the model is 8+ points off the market, and it is framed as information, not a pick.
    out = [l for l in D["bd"]["legs"] if l.get("gl") and not l.get("alt") and not l.get("risk") and l["e"] >= 0.08]
    out.sort(key=lambda l: -l["e"])
    games = {g["gid"]: g for g in D["bd"]["games"]}
    res, seen = [], set()
    for l in out:
        if l["g"] in seen: continue
        seen.add(l["g"])
        res.append({"pl": l["pl"], "pos": "", "tm": "", "opp": "", "m": l["m"], "ln": l["ln"], "o": l["o"], "p": l["p"], "bk": l["bk"], "e": l["e"], "gid": l["g"],
                    "ko": games.get(l["g"], {}).get("ko"), "kick": games.get(l["g"], {}).get("kick", ""), "fd": (l.get("fd") or {}).get("u"), "bks": l.get("bks"), "ba": l.get("ba"), "gl": l.get("gl"), "fh": [], "disp": l.get("ms") or l["m"]})
        if len(res) >= n: break
    return res

def gl_card(x):
    e = x["e"]
    return (f'<article class="play gl" data-gid="{E(x["gid"])}" data-ko="{x.get("ko") or ""}">'
            f'<div class="who"><b>{E(x["pl"])}</b><small>{E(x["gid"].replace("-", " @ "))} · {E(x.get("kick",""))}</small></div>'
            f'<div class="what">{E(x.get("disp") or x["m"])}<span class="odds">{E(odds_str(x["o"]))}</span></div>'
            f'<div class="nums"><span><i>Model</i>{x["p"]*100:.0f}%</span><span><i>Price needs</i>{x["bk"]*100:.0f}%</span><span class="edge {"pos" if e>0 else "neg"}"><i>Edge</i>{e*100:+.0f}</span></div>'
            f'<div class="foot"><a class="more" href="/boards/#g-{E(x["gid"])}">Board →</a>' + (f'<a class="fdb{" best" if BL.best(x) == "fd" and (x.get("bks") or {}) else ""}" href="{E(x["fd"])}" target="_blank" rel="noopener">Add to FanDuel</a>' if x.get("fd") else "") + BL.buttons([x], price=True) + '</div></article>')

# ---------- best same-game parlay ----------
def parlays(D):
    games = {g["gid"]: g for g in D["bd"]["games"]}
    bp = [p for p in D["bp"] if p.get("legs")]
    bp.sort(key=lambda p: -(p.get("ev") or 0))
    out = []
    for p in bp:
        g = games.get(p["gid"], {})
        bl = []
        for l in p["legs"]:
            m = next((x for x in D["bd"]["legs"] if x["pl"] == l[0] and x["m"] == l[1] and abs(float(x["ln"] or 0) - float(l[2] or 0)) < 0.01 and x["g"] == p["gid"]), None)
            bl.append(m)
        fdl = ("https://sportsbook.fanduel.com/addToBetslip?" + "&".join(f"marketId[{i}]={x['fd']['m']}&selectionId[{i}]={x['fd']['s']}" for i, x in enumerate(bl))) if bl and all(x and (x.get("fd") or {}).get("m") for x in bl) else None
        out.append({"gid": p["gid"], "a": p["a"], "b": p["b"], "pj": p["pj"], "ev": p["ev"], "dec": p["dec"], "fit": p.get("fit", ""), "ko": g.get("ko"), "kick": g.get("kick", ""), "fin": g.get("fin", ""),
                    "legs": [{"pl": l[0], "m": l[1], "ln": l[2], "o": l[3], "p": l[4], "e": l[5]} for l in p["legs"]], "fd": fdl, "bl": bl if all(bl) else []})
    return out

def dec_to_us(d):
    try: d = float(d)
    except Exception: return ""
    if d <= 1: return ""
    return f"+{round((d-1)*100)}" if d >= 2 else f"-{round(100/(d-1))}"

def parlay_block(ps):
    if not ps: return ""
    top = ps[0]
    legs = "".join(f'<li><b>{E(l["pl"])}</b><span>{E(leg_line(l["m"], l["ln"]))} <small>{E(odds_str(l["o"]))}</small></span><em>{l["p"]*100:.0f}%</em></li>' for l in top["legs"])
    others = "".join(f'<a class="pmini" href="/boards/#g-{E(p["gid"])}" data-gid="{E(p["gid"])}" data-ko="{p.get("ko") or ""}"><b>{E(p["a"])} @ {E(p["b"])}</b><span>{len(p["legs"])} legs · {E(dec_to_us(p["dec"]))}</span><em>model {p["pj"]*100:.0f}% · EV {p["ev"]*100:+.0f}%</em></a>' for p in ps[1:5])
    return (f'<div class="parlay" data-gid="{E(top["gid"])}" data-ko="{top.get("ko") or ""}"><div class="phd"><small>Best same-game parlay</small><h3>{E(top["a"])} @ {E(top["b"])} <span>{E(top.get("kick",""))}</span></h3>'
            f'<p>Built for the game\'s most likely script ({E(top["fit"])}); the model gives the full slip <b>{top["pj"]*100:.0f}%</b> against a FanDuel-equivalent price of <b>{E(dec_to_us(top["dec"]))}</b> (EV {top["ev"]*100:+.0f}%).</p></div>'
            f'<ul class="plegs">{legs}</ul><div class="pfoot">' + (f'<a class="fdb" href="{E(top["fd"])}" target="_blank" rel="noopener">Add all to FanDuel</a>' if top.get("fd") else "") + BL.buttons(top.get("bl") or [], single=False) + f'<a class="more" href="/boards/#g-{E(top["gid"])}">Open the board →</a><a class="more" href="{E(build_href(top["gid"], [(l["pl"], l["m"], l["ln"]) for l in top["legs"]]))}">Edit in the builder →</a></div></div>'
            + (f'<div class="pothers">{others}</div>' if others else ""))

# ---------- slate ----------
def slate(D):
    gs = sorted(D["bd"]["games"], key=lambda g: g.get("ko") or 0)
    items = []
    for g in gs:
        fav = g["a"] if g["pa"] > g["pb"] else g["b"]; marg = abs(g["pa"] - g["pb"])
        items.append(f'<a class="game" href="/boards/#g-{E(g["gid"])}" data-gid="{E(g["gid"])}" data-ko="{g.get("ko") or ""}" data-fin="{E(g.get("fin",""))}">'
                     f'<span class="gk">{E(g.get("kick",""))}</span><span class="gm"><b>{E(g["a"])}</b> @ <b>{E(g["b"])}</b></span>'
                     f'<span class="gp">{E(fav)} by {marg:.1f} · O/U {g["tot"]:.1f}</span><span class="gs">{E(g.get("most",""))}</span><span class="gl"></span></a>')
    return '<div class="slate">' + "".join(items) + "</div>"

# ---------- track record ----------
def record(D):
    sc = D["score"]; H = {c: i for i, c in enumerate(sc[0])} if sc else {}
    def cell(week, pos, snap):
        for r in sc[1:]:
            r = r + [""] * (11 - len(r))
            if str(r[H["Week"]]) == str(week) and r[H["Position"]] == pos and r[H["Snapshot Type"]] == snap: return _num(r[H["MAE Fantasy Pts"]]), r[H["With Stat Row"]]
        return None, None
    mae, npg = cell("All", "All skill", "Frozen")
    weeks = sorted({int(float(r[H["Week"]])) for r in sc[1:] if H and r and str(r[H["Week"]]).strip().replace(".", "").isdigit()
                    and len(r) > H["MAE Fantasy Pts"] and _num(r[H["MAE Fantasy Pts"]]) is not None and r[H["Position"]] == "All skill"}) if sc else []
    L = []
    try:
        lf = D["legsnaps"]; LH = {c: i for i, c in enumerate(lf[0])}
        for r in lf[1:]:
            r = r + [""] * (28 - len(r))
            if str(r[LH["Latest Snapshot"]]).upper() != "TRUE" or r[LH["Result"]].upper() not in ("HIT", "MISS"): continue
            L.append({"res": r[LH["Result"]].upper(), "units": _num(r[LH["Units (1u)"]]) or 0, "warn": r[LH["Warnings"]]})
    except Exception: pass
    tot = (len(L), sum(1 for l in L if l["res"] == "HIT"), sum(l["units"] for l in L))
    clean = [l for l in L if not l["warn"]]; cl = (len(clean), sum(1 for l in clean if l["res"] == "HIT"), sum(l["units"] for l in clean))
    return {"mae": mae, "npg": npg, "weeks": weeks, "legs": tot, "clean": cl}

def record_block(R, latest_week):
    tiles = []
    if R["mae"] is not None: tiles.append(f'<div><b>{R["mae"]:.1f}</b><span>PPR points off per player, frozen before kickoff ({E(str(R["npg"]))} player-games)</span></div>')
    if R["legs"][0]:
        t = R["legs"]; c = R["clean"]
        tiles.append(f'<div><b>{t[1]}–{t[0]-t[1]}</b><span>FanDuel legs graded · {t[1]/t[0]*100:.0f}% hit · {t[2]:+.1f}u at 1u each</span></div>')
        if c[0]: tiles.append(f'<div><b>{c[1]}–{c[0]-c[1]}</b><span>clean legs (no warnings) · {c[2]:+.1f}u</span></div>')
    else:
        tiles.append('<div><b>Tue</b><span>FanDuel legs are frozen before kickoff and graded Tuesday - the first graded record lands then</span></div>')
    if R["weeks"]: tiles.append(f'<div><b>{len(R["weeks"])}</b><span>weeks graded · <a href="/receipts/week{latest_week}/">Week {latest_week} receipt</a> · <a href="/season/">season</a></span></div>' if latest_week else f'<div><b>{len(R["weeks"])}</b><span>weeks graded · <a href="/season/">season to date</a></span></div>')
    return '<div class="rec">' + "".join(tiles) + "</div>"

# ---------- promoted bets ----------
# Owner 10/26: grade promo legs live on the home page and take a busted card down. While a promo's games are on (15 min before the
# first kickoff to 6 h after the last), the page reads ESPN's public scoreboard + game summaries every 60 s (the feeds the Live page
# uses). A leg turns HIT the moment it clears (yards / catches / TD / an over that is already over) and DEAD when it can no longer hit
# (its game is final short of the line; an under already passed; a first TD scored by someone else). A card with a dead leg says
# "Busted: <leg>" and leaves the page once that leg's game is final; all legs hit = "Cashed". A player with no box-score line at the
# final stays open (likely inactive - FanDuel voids the leg). Grading of record is still Tuesday's, from the game log.
PROMO_LIVE_JS = r"""<script>(function(){
  var cards = [].slice.call(document.querySelectorAll('.promo[data-last-ko]')); if(!cards.length || !window.fetch) return;
  var ESPN = {WSH: 'WAS', LAR: 'LA'}; function ab(x){ return ESPN[x] || x; }
  function norm(n){ return String(n || '').toLowerCase().replace(/\./g, '').replace(/\s+(jr|sr|ii|iii|iv|v)$/, '').replace(/[^a-z ]/g, '').replace(/\s+/g, ' ').trim(); }
  var legs = []; cards.forEach(function(card){ card.querySelectorAll('li[data-g]').forEach(function(li){ if(!li.dataset.g) return; legs.push({card: card, li: li, g: li.dataset.g, who: li.dataset.who, mk: li.dataset.mk, glx: li.dataset.glx ? JSON.parse(li.dataset.glx) : null}); }); });
  if(!legs.length) return;
  var kos = cards.map(function(c){ return [+c.dataset.firstKo || 0, +c.dataset.lastKo || 0]; });
  function active(){ var t = Date.now(); return kos.some(function(k){ return k[0] && t >= k[0] - 9e5 && t <= (k[1] || k[0]) + 6 * 36e5; }); }
  function ymd(t){ var d = new Date(t); return d.getFullYear() + String(d.getMonth()+1).padStart(2,'0') + String(d.getDate()).padStart(2,'0'); }
  var G = {}, BOX = {}, FIRST = {};
  function parseBox(js, gid){
    try { (js.boxscore.players || []).forEach(function(tm){ (tm.statistics || []).forEach(function(cat){ var keys = cat.keys || cat.labels || [];
      (cat.athletes || []).forEach(function(a){ var n = norm(a.athlete && (a.athlete.displayName || a.athlete.shortName)); if(!n) return;
        var r = BOX[n] = BOX[n] || {pass: 0, rush: 0, rec: 0, recy: 0, long: 0, td: 0, g: gid}; var S = {}; keys.forEach(function(k, i){ S[k] = a.stats[i]; });
        var num = function(v){ var m = String(v == null ? '' : v).match(/-?\d+(\.\d+)?/); return m ? +m[0] : 0; };
        if(cat.name === 'passing') r.pass = num(S.passingYards != null ? S.passingYards : S.YDS);
        if(cat.name === 'rushing'){ r.rush = num(S.rushingYards != null ? S.rushingYards : S.YDS); r.td += num(S.rushingTouchdowns != null ? S.rushingTouchdowns : S.TD); }
        if(cat.name === 'receiving'){ r.rec = num(S.receptions != null ? S.receptions : S.REC); r.recy = num(S.receivingYards != null ? S.receivingYards : S.YDS); r.long = Math.max(r.long, num(S.longReception != null ? S.longReception : S.LONG)); r.td += num(S.receivingTouchdowns != null ? S.receivingTouchdowns : S.TD); }
      }); }); });
      var sp = (js.scoringPlays || []).filter(function(p){ return (p.type && /touchdown/i.test(p.type.text || '')) || /\bTD\b|touchdown/i.test(p.text || ''); });
      if(sp.length){ var m = (sp[0].text || '').match(/^([A-Z][\w.'-]+(?:\s[A-Z][\w.'-]+){0,3}?)\s+\d+\s+(?:Yd|Yard)/i); FIRST[gid] = m ? norm(m[1]) : '?'; }
    } catch(e){}
  }
  var STAT = /^(Passing Yards|Rushing Yards|Receiving Yards|Receptions|Longest Reception|Rush \+ Rec Yards)\s+(\d+(?:\.\d+)?)\+?/i;
  function grade(L){
    var g = G[L.g]; if(!g || g.st === 'pre') return 'open'; var fin = g.st === 'post', mk = L.mk || '';
    if(L.glx){ var x = L.glx, sa = +g.sa || 0, sb = +g.sb || 0, tot = sa + sb;
      if(x.k !== 'M'){ var over = String(x.side).toUpperCase() === 'OVER'; if(over){ return tot > x.ln ? 'hit' : (fin ? 'dead' : 'open'); } return tot > x.ln ? 'dead' : (fin ? 'hit' : 'open'); }
      if(!fin) return 'open'; var me = x.side === g.a ? sa : sb, them = x.side === g.a ? sb : sa; return (me - them + (+x.ln || 0)) > 0 ? 'hit' : 'dead'; }
    var names = /^either/i.test(mk) ? L.who.split(/\s+or\s+|\s*\/\s*/) : [L.who];
    var rows = names.map(function(n){ return BOX[norm(n)]; });
    if(/^first/i.test(mk)){ var f = FIRST[L.g]; if(!f) return fin ? 'dead' : 'open'; return f === norm(L.who) ? 'hit' : 'dead'; }
    if(/^(anytime|either)/i.test(mk)){ if(rows.some(function(r){ return r && r.td >= 1; })) return 'hit'; return fin ? (rows.some(function(r){ return r; }) ? 'dead' : 'open') : 'open'; }
    var m = mk.match(STAT); if(!m) return 'open'; var need = +m[2], r = rows[0];
    if(!r) return 'open';   // no box line yet / inactive (FanDuel voids) - never call it dead
    var k = m[1].toLowerCase(), v = k === 'passing yards' ? r.pass : k === 'rushing yards' ? r.rush : k === 'receiving yards' ? r.recy : k === 'receptions' ? r.rec : k === 'longest reception' ? r.long : r.rush + r.recy;
    return v >= need ? 'hit' : (fin ? 'dead' : 'open');
  }
  function paint(){
    var anyShown = false;
    cards.forEach(function(card){
      var ls = legs.filter(function(L){ return L.card === card; }); var dead = null, deadFinal = false, hits = 0;
      ls.forEach(function(L){ var s = grade(L); L.li.classList.toggle('hit', s === 'hit'); L.li.classList.toggle('dead', s === 'dead');
        if(s === 'hit') hits++; if(s === 'dead' && !dead){ dead = L; deadFinal = (G[L.g] || {}).st === 'post'; } });
      var st = card.querySelector('[data-role=pst]');
      if(dead){ card.classList.add('busted'); if(st){ st.textContent = 'Busted: ' + dead.who + (dead.mk && !/td$/i.test(dead.mk) ? ' ' + dead.mk.replace(/\s+(\d)/, ' $1') : (/td$/i.test(dead.mk) ? ' TD' : '')); st.className = 'st loss'; }
        if(deadFinal) card.hidden = true; }
      else if(ls.length && hits === ls.length){ if(st){ st.textContent = 'Cashed'; st.className = 'st win'; } }
      if(!card.hidden) anyShown = true;
    });
    var sec = document.getElementById('promo'); if(sec && !anyShown) sec.hidden = true;
  }
  var busy = false;
  function poll(){
    if(busy || !active()) return; busy = true;
    var t0 = Math.min.apply(null, kos.map(function(k){ return k[0]; }).filter(Boolean)), t1 = Math.max.apply(null, kos.map(function(k){ return k[1] || k[0]; }));
    fetch('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=' + ymd(t0 - 864e5) + '-' + ymd(t1 + 864e5), {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(js){
      if(!js){ busy = false; return; }
      var want = {}; legs.forEach(function(L){ want[L.g] = 1; });
      (js.events || []).forEach(function(ev){ var c = (ev.competitions || [])[0]; if(!c) return; var by = {}; (c.competitors || []).forEach(function(x){ by[ab(x.team && x.team.abbreviation)] = x.score; });
        Object.keys(want).forEach(function(gid){ var p = gid.split('-'); if(!(p[0] in by) || !(p[1] in by)) return; var ty = ((ev.status || c.status || {}).type) || {};
          G[gid] = {eid: ev.id, st: ty.state || 'pre', a: p[0], b: p[1], sa: by[p[0]], sb: by[p[1]]}; }); });
      var live = Object.keys(G).filter(function(gid){ return G[gid].st !== 'pre'; });
      return Promise.all(live.map(function(gid){ return fetch('https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=' + G[gid].eid, {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(s){ if(s) parseBox(s, gid); }).catch(function(){}); }));
    }).then(function(){ busy = false; paint(); }).catch(function(){ busy = false; });
  }
  poll(); setInterval(poll, 60000);
})();</script>"""


def promos_block(OUT):
    # owner 10/23: archive a promo once its games are done - off the home page when every leg's game has kicked off 4.5+ hours ago
    # (or it already has a graded result); the page script also hides it in the browser between rebuilds (data-last-ko). Grading and
    # the receipts still read it from the sheet; only the home page card goes away.
    import time as _t
    _now = _t.time() * 1000
    def _live(p):
        if p.get("status", "LIVE") != "LIVE": return False
        if (p.get("result") or "").strip(): return False
        if (p.get("checks") or {}).get("block"): return False   # promo check failed (build_promo prints why): never post a broken card
        lk = p.get("last_ko")
        return not (lk and _now > float(lk) + 4.5 * 3600e3)
    try: ps = [p for p in json.load(open(os.path.join(OUT, "promos.json"))) if _live(p)]
    except Exception: ps = []
    if not ps: return ""
    cards = []
    for p in ps:
        many = len(p["legs"]) >= 7
        legs = ""
        for l in p["legs"]:
            who = l["who"]; ml = l["disp"][len(who):].strip(" ·") if l["disp"].startswith(who) else l["disp"]
            rk = l.get("rank"); mk = f'{l["opp"]} #{rk[0]} vs {"QB rush" if l.get("pos") == "QB" else l.get("pos", "")} TDs' if rk else ""
            sub = " · ".join(x for x in [ml, l.get("kick", ""), mk] if x)
            mp = f'<span class="mp">model {l["p"]*100:.0f}%</span>' if l.get("p") is not None else ""
            _gx = f' data-glx="{E(json.dumps(l["glx"]))}"' if l.get("glx") else ""
            legs += f'<li data-g="{E(l.get("gid") or "")}" data-who="{E(who)}" data-mk="{E(l.get("market") or "")}"{_gx}><b>{E(who)}</b><span class="o">{E(odds_str(l["o"])) if l.get("o") is not None else ""}</span><small>{E(sub)}</small>{mp}</li>'
        res = (p.get("result") or "").upper()
        st = '<span class="st win">Cashed</span>' if res in ("W", "WIN", "HIT") else ('<span class="st loss">Missed</span>' if res in ("L", "LOSS", "MISS") else '<span class="st" data-role="pst">Pregame</span>')
        # audit 10/26: a +11825 lotto showing "Model 0.1% to hit · fair +181169" read like the site arguing against its own post -
        # longshots (model under 3%) are labelled as such and the fair price is dropped
        if p.get("p") and p["p"] < 0.03: model = f'<b>Longshot</b> · model {"under 1" if p["p"] < 0.01 else format(p["p"]*100, ".0f")}% to hit - a small-stake swing, not a value bet'
        else: model = f'<b>Model {p["p"]*100:.1f}%</b> to hit · fair {E(p["fair"])}' if p.get("p") else "Model price not available for every leg"
        # X caption written for @Playbook's parser (Action Network's bot: tag it and it replies with a tail link for every sportsbook):
        # one plain leg per line, "Player Market N+ odds", no bullets or model numbers, the book named, @Playbook on its own line.
        def _pb_leg(l):
            who = l["who"]; mk = (l.get("market") or "").strip()
            if mk.lower().startswith("either"): return f"{who} either to score a TD"
            if mk.lower().startswith("anytime"): return f"{who} anytime TD"
            if mk.lower().startswith("first"): return f"{who} first TD"
            return f"{who} {mk}"
        tweet = (f'{p["title"]} · {len(p["legs"])}-leg parlay · FanDuel {odds_str(p["fd"]) if p.get("fd") else ""}\n\n'
                 + "\n".join(f'{_pb_leg(l)} {odds_str(l["o"]) if l.get("o") is not None else ""}'.rstrip() for l in p["legs"])
                 + f"\n\n@Playbook\nbetsweep.co/b/w{p['week']}-{p['slot']}")
        share = "https://twitter.com/intent/tweet?text=" + __import__("urllib.parse").parse.quote(tweet)
        def _bkey(l):
            mk = (l.get("market") or "").strip(); import re as _re
            if mk.lower().startswith(("either", "first")) or " or " in l["who"]: return None
            if mk.lower().startswith("anytime"): return (l["who"], "Anytime TD", 1)
            mm = _re.match(r"(Passing Yards|Rushing Yards|Receiving Yards|Receptions|Longest Reception|Rush \+ Rec Yards)\s+(\d+(?:\.\d+)?)\+?$", mk, _re.I)
            return (l["who"], mm.group(1).title().replace("Td", "TD"), float(mm.group(2))) if mm else None
        bkeys = [_bkey(l) for l in p["legs"]]
        edit = f'<a href="{E(build_href((p["legs"][0] or {}).get("gid"), [k for k in bkeys if k]))}">Edit in the builder</a>' if bkeys and all(bkeys) else ""
        tail = f'<button type="button" class="tail" data-w="{p["week"]}" data-id="promo-{p["week"]}-{p["slot"]}" data-name="{E(p["title"])}" data-keys="{E(json.dumps([l.get("key") for l in p["legs"] if l.get("key")]))}" data-odds="{int(p["fd"]) if p.get("fd") else ""}">Tail</button>' if all(l.get("key") for l in p["legs"]) else ""
        bk = "".join(f'<a class="{b}" href="{E(v["url"])}" target="_blank" rel="noopener" title="{E((BL.NAMES[b] + " uses its nearest line: " + "; ".join(v["subs"]) + ". Prices and model % shown are FanDuel's.") if v["subs"] else "Opens " + BL.NAMES[b] + " with these legs on the betslip")}">Bet it on {BL.NAMES[b]}{"≈" if v["subs"] else ""}</a>' for b, v in (p.get("books") or {}).items())
        btns = (f'<a class="fd" href="{E(p["link"])}" target="_blank" rel="noopener">Bet it on FanDuel</a>' if p.get("link") else "") + bk + tail + edit + f'<a href="{E(share)}" target="_blank" rel="noopener">Share on X</a><a href="{E(p["img"].get("feed", p["img"]["square"]))}" download>Post 4:5</a><a href="{E(p["img"]["square"])}" download>Square</a><a href="{E(p["img"]["story"])}" download>Story</a>'
        _su = f"https://betsweep.co/b/w{p['week']}-{p['slot']}"
        cap = (f'<p class="cap">{E(p["caption"])}</p>' if p.get("caption") else "") + f'<p class="slink">Short link <code>{E(_su.replace("https://", ""))}</code><button type="button" class="cpy" data-copy="{E(_su)}">Copy</button> <a href="/b/w{p["week"]}-{p["slot"]}/">open →</a></p>'
        subs = [f'{BL.NAMES[b]}: ' + "; ".join(v["subs"]) for b, v in (p.get("books") or {}).items() if v["subs"]]
        if subs: cap += f'<p class="bknote">Nearest line at the other books - {E(" · ".join(subs))}. Prices and model % shown are FanDuel\'s.</p>'
        cards.append(f'<article class="promo" data-first-ko="{p.get("first_ko") or ""}" data-last-ko="{p.get("last_ko") or ""}"><div class="ph"><small>Promoted</small>{st}</div><h3>{E(p["title"])}</h3><div class="meta">Week {p["week"]} · {len(p["legs"])} legs</div>'
                     f'<ul class="pl{" many" if many else ""}">{legs}</ul><div class="pf"><div class="big"><small>FanDuel</small>{E(odds_str(p["fd"])) if p.get("fd") else "—"}</div><div class="md">{model}<br>Snapshot at post time; prices move.</div></div>{cap}<div class="pa">{btns}</div></article>')
    tail_js = """<script>(function(){ document.querySelectorAll('.promo .slink .cpy').forEach(function(b){ b.addEventListener('click', function(){ var t = b.dataset.copy; function done(){ b.textContent = 'Copied'; setTimeout(function(){ b.textContent = 'Copy'; }, 1400); } if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, function(){ prompt('Copy this link', t); }); else prompt('Copy this link', t); }); }); })();</script>
<script>(function(){ document.querySelectorAll('.promo .tail').forEach(function(b){ var key = 'bs_slips_w' + b.dataset.w, id = b.dataset.id; function has(){ try{ return (JSON.parse(localStorage.getItem(key)||'[]')||[]).some(function(s){ return s && s.id === id; }); }catch(e){ return false; } }
  function paint(){ var on = has(); b.textContent = on ? 'Tailed ✓' : 'Tail'; b.classList.toggle('on', on); }
  b.addEventListener('click', function(){ var slips = []; try{ slips = JSON.parse(localStorage.getItem(key)||'[]')||[]; }catch(e){} if (has()){ slips = slips.filter(function(s){ return !s || s.id !== id; }); } else { slips.push({id: id, name: b.dataset.name, keys: JSON.parse(b.dataset.keys), odds: b.dataset.odds ? +b.dataset.odds : null, stake: 1, promo: true}); }
    try{ localStorage.setItem(key, JSON.stringify(slips)); }catch(e){} paint(); var t = document.createElement('div'); t.textContent = has() ? 'Saved to My BetSweep - graded after the games' : 'Removed from your slips'; t.style.cssText = 'position:fixed;left:50%;bottom:70px;transform:translateX(-50%);background:#1b1a17;color:#fff;padding:9px 14px;border-radius:999px;font:13px IBM Plex Sans,system-ui,sans-serif;z-index:120'; document.body.appendChild(t); setTimeout(function(){ t.remove(); }, 2500); });
  paint(); }); })();</script>"""
    return f'<section class="sec" id="promo"><h2 class="t">Promoted bets</h2><div class="promos">{"".join(cards)}</div>{tail_js}{PROMO_LIVE_JS}<p class="none" style="margin-top:8px;font-size:12.5px">The slips we post on X and Instagram, graded Tuesday like everything else. Share on X pre-fills the legs in plain text with @Playbook tagged, so the Playbook bot replies with a tail link for whichever sportsbook the reader uses. Sportsbook links may earn BetSweep a commission; it never changes a pick or a grade. One tap loads the whole slip on FanDuel.</p></section>'

# ---------- assemble ----------
HOME_CSS = r"""
.hsbar{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(var(--bs-tabs,0px) + 12px);z-index:65;display:none;align-items:center;gap:12px;background:var(--ink);color:var(--bg);border-radius:999px;padding:8px 8px 8px 16px;box-shadow:0 8px 24px rgba(0,0,0,.4);font-size:13px;font-weight:600;white-space:nowrap}
.hsbar.on{display:flex} .hsbar a{background:var(--red);color:#fff;text-decoration:none;border-radius:999px;padding:6px 12px;font-weight:700}
a.more.inslip{background:var(--red);border-color:var(--red);color:#fff}
.promos{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.promo[hidden],#promo[hidden]{display:none!important} .promo{position:relative;display:flex;flex-direction:column;background:var(--card);border:1px solid color-mix(in srgb,var(--red) 55%,var(--line));border-radius:14px;overflow:hidden}
.promo .ph{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 16px 0}
.promo .ph small{font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#fff;background:var(--red);padding:3px 9px;border-radius:99px}
.promo .ph .st{font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--mute)} .promo .ph .st.live{color:var(--red)} .promo .ph .st.win{color:var(--good)} .promo .ph .st.loss{color:#e07070}
.promo h3{margin:8px 16px 0;font-family:var(--brand);font-style:italic;font-weight:800;font-size:30px;letter-spacing:-.02em;line-height:1}
.promo .meta{margin:4px 16px 10px;color:var(--mute);font-size:13px}
.promo .pl{list-style:none;margin:0 16px;padding:0;border-top:1px solid var(--line)}
.promo .pl li{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;padding:8px 0;border-bottom:1px solid var(--line);font-size:14px}
.promo .pl li.hit b::before{content:"✓ ";color:var(--good)} .promo .pl li.dead{opacity:.6} .promo .pl li.dead b{text-decoration:line-through} .promo .pl li.dead b::before{content:"✗ ";color:var(--bad);display:inline-block;text-decoration:none}
.promo.busted{border-color:var(--line)}
.promo .pl b{font-family:var(--display);font-weight:700;font-size:17px;letter-spacing:.01em} .promo .pl small{color:var(--mute);font-size:12px} .promo .pl .o{font-family:var(--display);font-weight:800;font-size:17px;font-variant-numeric:tabular-nums} .promo .pl .mp{grid-column:2;font-size:11.5px;color:var(--good);text-align:right}
.promo .pl.many li{padding:5px 0} .promo .pl.many b{font-size:15px} .promo .pl.many small{font-size:11.5px} .promo .pl.many .mp{display:none}
.promo .pf{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;align-items:end;padding:12px 16px 4px}
.promo .pf .big{font-family:var(--display);font-weight:800;font-size:44px;line-height:.9} .promo .pf .big small{display:block;font-size:10.5px;letter-spacing:.18em;text-transform:uppercase;color:#1493ff;font-weight:700;margin-bottom:4px}
.promo .pf .md{font-size:13px;color:var(--mute);line-height:1.4} .promo .pf .md b{color:var(--ink)}
.promo .pa{display:flex;flex-wrap:wrap;gap:8px;padding:10px 16px 14px;margin-top:auto}
.promo .pa a,.promo .pa .tail{text-decoration:none;font-family:var(--display);font-weight:700;font-size:12.5px;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line);color:var(--ink);border-radius:6px;padding:7px 11px}.promo .pa .tail{cursor:pointer;background:none;color:var(--ink)}.promo .pa .tail.on{background:var(--good);color:#fff;border-color:var(--good)}
.promo .pa a.fd{background:#1493ff;border-color:#1493ff;color:#0b0f15} .promo .pa a:hover{border-color:var(--red)}
.promo .cap{margin:0 16px 10px;color:var(--mute);font-size:13px;line-height:1.5}
.promo .slink{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:0 16px 10px;font-size:12px;color:var(--mute)} .promo .slink code{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:var(--ink);background:var(--chalk);padding:2px 7px;border-radius:6px} .promo .slink button{font:inherit;font-size:11.5px;font-weight:600;padding:3px 8px;border-radius:6px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer} .promo .slink a{color:var(--ink)}
.promo .cap[hidden]{display:none}

.plays{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.play{position:relative;display:flex;flex-direction:column;gap:8px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 14px 12px}
.play.lead{border-color:color-mix(in srgb,var(--red) 55%,var(--line))}
.play.lead::before{content:"TOP PLAY";position:absolute;top:-9px;left:12px;background:var(--red);color:#fff;font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.14em;padding:2px 8px;border-radius:99px}
.play .who{display:flex;flex-direction:column} .play .who b{font-family:var(--display);font-weight:700;font-size:21px;letter-spacing:.01em;line-height:1.1} .play .who small{color:var(--mute);font-size:12.5px;margin-top:2px}
.play .what{display:flex;align-items:baseline;justify-content:space-between;gap:8px;font-size:15px;font-weight:600} .play .what .odds{font-family:var(--display);font-weight:700;font-size:18px;color:var(--ink);font-variant-numeric:tabular-nums}
.play .nums{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;background:var(--chalk);border-radius:8px;padding:8px 10px;font-family:var(--display);font-weight:700;font-size:20px;font-variant-numeric:tabular-nums}
.play .nums span{display:flex;flex-direction:column} .play .nums i{font-style:normal;font-family:var(--body);font-weight:500;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)}
.play .nums .edge.pos{color:var(--good)} .play .nums .edge.neg{color:#e07070}
.play .foot{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:auto}
.play .hist{font-size:11.5px;color:var(--mute);border:1px solid var(--line);border-radius:99px;padding:2px 8px} .play .hist.good{color:var(--good);border-color:color-mix(in srgb,var(--good) 40%,var(--line))} .play .hist.bad{color:#e07070}
.play .more,.pfoot .more{color:var(--mute);text-decoration:none;font-size:12.5px;font-weight:600} .play .more:hover,.pfoot .more:hover{color:var(--ink)}
.fdb{margin-left:auto;text-decoration:none;font-family:var(--display);font-weight:700;font-size:12.5px;letter-spacing:.06em;text-transform:uppercase;color:#0b0f15;background:#1493ff;border-radius:6px;padding:6px 10px}
.fdb:hover{filter:brightness(1.08)}
.dkb,.hrb{text-decoration:none;font-family:var(--display);font-weight:700;font-size:12.5px;letter-spacing:.06em;text-transform:uppercase;border-radius:6px;padding:6px 9px;margin-left:6px} .fdb.best,.dkb.best,.hrb.best{box-shadow:0 0 0 2px var(--card),0 0 0 4px var(--good);position:relative} .fdb.best::after,.dkb.best::after,.hrb.best::after{content:"best";position:absolute;top:-9px;right:-6px;font-size:9px;letter-spacing:.08em;padding:1px 5px;border-radius:99px;background:var(--good);color:#0b1a07} .dkb{background:#53d337;color:#0b1a07} .hrb{background:#5b2d8e;color:#fff} .dkb:hover,.hrb:hover{filter:brightness(1.08)} .fslip .pfoot .dkb,.parlay .pfoot .dkb{margin-left:0}
@media (max-width:560px){.promo .pa a.fd,.promo .pa a.dk,.promo .pa a.hr{flex:1 1 100%;text-align:center;white-space:nowrap}}
.promo .pa a.dk{background:#53d337;border-color:#53d337;color:#0b1a07} .promo .pa a.hr{background:#5b2d8e;border-color:#5b2d8e;color:#fff} .promo .bknote{font-size:11.5px;color:var(--mute);margin:4px 16px 0;line-height:1.4}
.play.started{display:none}
.play.floor{border-color:color-mix(in srgb,var(--good) 45%,var(--line))}
.play.nm{border-color:color-mix(in srgb,#1493ff 45%,var(--line))} .play.nm .why{margin:0;color:var(--mute);font-size:12.5px;line-height:1.45}
.parlay.fslip::after{background:var(--good)} .parlay.fslip small{color:var(--good)} .fslip .pfoot{align-items:center} .fslip .pfoot .fdb{margin-left:0}
.play .what .proj{color:var(--mute);font-weight:500;font-size:12px;margin-left:6px;margin-right:auto}
.sec h2 .tsub{font-family:var(--body);font-weight:500;font-size:12.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin-left:10px}
.subt{font-family:var(--display);font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:12px;color:var(--mute);margin:18px 0 8px}
.none{color:var(--mute);font-size:14px;margin:0}
.ptwo{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:12px} @media (max-width:760px){.ptwo{grid-template-columns:1fr}}
.parlay{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 16px 14px;position:relative;overflow:hidden}
.parlay::after{content:"";position:absolute;right:-30px;top:-30px;width:140px;height:100px;background:var(--red);clip-path:polygon(30% 0,100% 0,100% 100%,0 60%);opacity:.9}
.parlay .phd{position:relative} .parlay small{font-family:var(--display);font-weight:700;letter-spacing:.12em;text-transform:uppercase;font-size:11.5px;color:var(--red)}
.parlay h3{margin:2px 0 6px;font-family:var(--display);font-weight:700;font-size:26px;letter-spacing:.01em} .parlay h3 span{font-size:14px;color:var(--mute);font-weight:600;margin-left:8px}
.parlay p{margin:0 0 10px;color:var(--mute);font-size:14px;line-height:1.5;max-width:60ch} .parlay p b{color:var(--ink)}
.plegs{list-style:none;margin:0;padding:0;display:flex;flex-direction:column} .plegs li{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:10px;align-items:baseline;padding:8px 0;border-top:1px solid var(--line);font-size:14px}
.plegs b{font-family:var(--display);font-weight:700;font-size:17px} .plegs span{color:var(--mute)} .plegs span small{color:var(--ink);font-weight:600} .plegs em{font-style:normal;font-family:var(--display);font-weight:700;font-size:17px;color:var(--good)}
.pfoot{display:flex;gap:16px;margin-top:10px}
.pothers{display:grid;grid-template-columns:1fr;gap:8px;align-content:start}
.pmini{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;text-decoration:none;color:var(--ink)}
.pmini:hover{border-color:var(--red)} .pmini b{font-family:var(--display);font-weight:700;font-size:17px} .pmini span{grid-column:2;grid-row:1/3;align-self:center;font-family:var(--display);font-weight:700;font-size:16px;text-align:right} .pmini em{font-style:normal;color:var(--mute);font-size:12.5px}
.pmini.started,.parlay.started{opacity:.55}
.slate{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px}
.game{display:grid;grid-template-columns:1fr auto;gap:1px 8px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;text-decoration:none;color:var(--ink);font-size:12.5px}
.game:hover{border-color:var(--red)} .game .gk{color:var(--mute)} .game .gm{grid-column:1;font-family:var(--display);font-weight:700;font-size:19px;letter-spacing:.01em} .game .gp{grid-column:1;color:var(--ink)} .game .gs{grid-column:1;color:var(--mute)}
.game .gl{grid-column:1/-1;display:none;align-items:baseline;gap:8px;margin-top:6px;padding-top:6px;border-top:1px solid var(--line);font-family:var(--display);font-weight:800;font-size:16px;line-height:1.2} .game.live .gl,.game.post .gl{display:flex} .game .gl i{font-style:normal;font-size:10px;letter-spacing:.12em;color:var(--red)} .game .gl small{font-family:var(--body);font-weight:500;color:var(--mute);font-size:12px} .game.post .gl i{color:var(--mute)}
.game.post{opacity:.6;order:9}
.rec{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
.rec div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px} .rec b{display:block;font-family:var(--display);font-weight:700;font-size:30px;line-height:1;margin-bottom:4px} .rec span{color:var(--mute);font-size:13px;line-height:1.4} .rec a{color:var(--ink)}
"""

def home_js(games):
    gs = json.dumps([{"gid": g["gid"], "a": g["a"], "b": g["b"], "ko": g.get("ko"), "fin": g.get("fin", "")} for g in games])
    return r"""
<script>
(function(){
  var GAMES = """ + gs + r""";
  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
  function apply(st){
    var started = {};
    GAMES.forEach(function(g){ var s = st[g.gid] || {st:'pre'}; started[g.gid] = s.st !== 'pre';
      document.querySelectorAll('.game[data-gid="'+g.gid+'"]').forEach(function(el){
        el.classList.toggle('post', s.st==='post'); el.classList.toggle('live', s.st==='in');
        var b = el.querySelector('.gl');
        if(s.st==='in'){ b.innerHTML = '<i>LIVE</i>' + esc((s.sa!=null?s.sa:'')+'–'+(s.sb!=null?s.sb:'')) + (s.det?' <small>'+esc(s.det)+'</small>':''); }
        else if(s.st==='post'){ var f = (s.sa!=null) ? g.a+' '+s.sa+' – '+s.sb+' '+g.b : (s.finTxt||g.fin||'Final'); b.innerHTML = '<i>FINAL</i>' + esc(f); }
        else b.innerHTML = '';
      });
    });
    var now = Date.now();
    document.querySelectorAll('.promo').forEach(function(el){ var st = el.querySelector('[data-role=pst]'); if(!st || el.classList.contains('busted') || /^Cashed/.test(st.textContent)) return; var f = +el.getAttribute('data-first-ko'), l = +el.getAttribute('data-last-ko');
      if(l && now > l + 4.5*3600e3){ el.hidden = true; } else if(f && now >= f){ st.textContent = 'In play'; st.className = 'st live'; } });
    var psec = document.getElementById('promo'); if(psec && !psec.querySelector('.promo:not([hidden])')) psec.hidden = true;   // every promo archived: drop the section
    ['.play','.pmini','.parlay'].forEach(function(sel){ document.querySelectorAll(sel).forEach(function(el){ var g = el.getAttribute('data-gid'); if(g && started[g]) el.classList.add('started'); }); });
    document.querySelectorAll('.plays').forEach(function(grid){ var left = grid.querySelectorAll('.play:not(.started)').length; var note = grid.nextElementSibling;
      if(note && note.classList.contains('allstarted')) note.hidden = left > 0; });
  }
  if(window.BSLive) window.BSLive.start(GAMES, apply);
})();
</script>"""

# ---------- Model's Best (owner 10/27): even-money lines where the model is 8+ pts off FanDuel (mostly unders), TDs it likes, safer 65%+ legs ----------
def _mb(D, l, games):
    return {"pl": l["pl"], "pos": l.get("pos", ""), "tm": l["tm"], "opp": l["opp"], "m": l["m"], "ln": l["ln"], "o": l["o"], "p": l["p"], "bk": l["bk"], "e": l["e"], "gid": l["g"],
            "proj": l.get("proj"), "ko": games.get(l["g"], {}).get("ko"), "kick": games.get(l["g"], {}).get("kick", ""), "fd": (l.get("fd") or {}).get("u"), "bks": l.get("bks"),
            "ba": l.get("ba"), "gl": l.get("gl"), "fh": l.get("fh") or [], "n": l.get("n")}
def model_best(D):
    games = {g["gid"]: g for g in D["bd"]["games"]}; legs = D["bd"]["legs"]; now = __import__("time").time() * 1000
    open_ = lambda l: not (games.get(l["g"], {}).get("ko") and now >= games[l["g"]]["ko"])
    def gap(l):   # how far the model is from FanDuel on the leg's own side (raw model vs price)
        return (l.get("raw_p") or l["p"]) - l["bk"]
    def pick(tier, key, n):
        seen, out = set(), []
        for l in sorted([l for l in legs if l.get("tier") == tier and open_(l)], key=key):
            if l["pl"] in seen: continue
            seen.add(l["pl"]); out.append(_mb(D, l, games))
            if len(out) >= n: break
        return out
    return pick("even", lambda l: -gap(l), 8), pick("td", lambda l: -gap(l), 4), pick("safe", lambda l: -l["p"], 6)

def sections(IN, OUT, latest_week=None):
    D = load(IN, OUT)
    week = D["bd"].get("week") or ""
    tp = top_plays(D); td = td_plays(D); gl = gl_plays(D); ps = parlays(D); R = record(D); fl = floor_plays(D); fs = floor_slip(D, floor_plays(D, n=16)); nm = nextman_plays(D)
    out = []
    pb = promos_block(OUT)
    if pb: out.append(pb)
    mbe, mbt, mbs = model_best(D)
    if mbe or mbt or mbs:
        out.append('<section class="sec" id="best"><h2 class="t">Model\'s Best <small class="tsub">near even money</small></h2>'
                   + (f'<div class="subt">Lines priced near −110 where the model is 8+ points off FanDuel · in Weeks 6–7 unders like these won 59% (393 legs), overs 55%</div><div class="plays">{"".join(play_card(x, "lead" if i == 0 else "") for i, x in enumerate(mbe))}</div>' if mbe else "")
                   + (f'<div class="subt">Touchdowns the model likes at +200 or shorter · 10–8 in Weeks 6–7 (small sample — tracked on the season page)</div><div class="plays">{"".join(play_card(x) for x in mbt)}</div>' if mbt else "")
                   + (f'<div class="subt">Safer picks · model 65%+ and at or above the price · 65% hit at about −195 in Weeks 6–7, roughly break-even</div><div class="plays">{"".join(play_card(x, "floor") for x in mbs)}</div>' if mbs else "")
                   + '<p class="none allstarted" hidden>All kicked off.</p><p class="none" style="margin-top:10px;font-size:12.5px">Graded every week on the season page. At −110 a pick has to win 52.4% to break even, so 59% is a strong number; nothing here is a lock. <a href="/build/?best=1" style="color:var(--ink)">All Model\'s Best legs in the builder →</a></p></section>')
    plays_html = "".join(play_card(x, "lead" if i == 0 else "") for i, x in enumerate(tp))
    out.append('<section class="sec" id="plays"><h2 class="t">The model\'s top plays this week</h2>'
               + (f'<div class="plays">{plays_html}</div><p class="none allstarted" hidden>Every top play has kicked off. The <a href="/live/" style="color:var(--ink)">Live page</a> tracks what is still open; the next slate\'s plays land after the next rebuild.</p>'
                  if tp else '<p class="none">No clean plays on the sheet right now - the next rebuild refreshes this.</p>')
               + '<p class="none" style="margin-top:10px;font-size:12.5px">From the sheet\'s Best Legs: strong-value lines with no warnings, best line per player, floor lines only (no above-projection rungs, no cold streaks, no longest-reception legs), and the leg must stay likely when FanDuel\'s price gets an equal vote. Model % is the projected hit rate; "price needs" is what FanDuel\'s odds imply; edge is the gap in points.</p></section>')
    if fl:
        out.append('<section class="sec" id="floor"><h2 class="t">Floor legs <small class="tsub">parlay anchors</small></h2>'
                   + f'<div class="plays">{"".join(play_card(x, "floor") for x in fl)}</div><p class="none allstarted" hidden>All kicked off.</p>'
                   + (f'<div class="ptwo" style="margin-top:12px"><div>{floor_slip_block(fs)}</div></div>' if fs else "")
                   + '<p class="none" style="margin-top:10px;font-size:12.5px">The strategy that graded clean in Week 6: a primary role\'s line set at 30–60% of the model\'s projection, priced −130 to −400, model not fading it, no role risk, no cold streak (a player whose yards or targets are down 25%+ over his last three is out - that is what sank Kalif Raymond 2+ rec in Week 6). Ranked by probability, not edge - fair-priced building blocks for a slip rather than an edge hunt. Rushing yards are held to the same rule but ran hot last week; lean receiving. The <a href="/build/" style="color:var(--ink)">builder</a> has the same filter (\"floor legs\").</p></section>')
    if nm:
        out.append('<section class="sec" id="nextman"><h2 class="t">Next man up <small class="tsub">thinned rooms</small></h2>'
                   + f'<div class="plays">{nextman_block(nm)}</div><p class="none allstarted" hidden>All kicked off.</p>'
                   + '<p class="none" style="margin-top:10px;font-size:12.5px">Players first in line when several absences stack up at one position - the Josh Cuevas case (BAL TE, Week 6: two tight ends out, FanDuel priced his receptions on a one-target-a-game history, he caught four). Room math = his own recent volume plus ~60% of what the absent players leave behind, turned into a catch count; FanDuel often has not moved yet. Volume legs only - receptions and short yardage - not touchdowns.</p></section>')
    if td or gl:
        out.append('<section class="sec"><h2 class="t">Also on the radar</h2>'
                   + (f'<div class="subt">Anytime touchdown · priced fairly, model agrees</div><div class="plays">{"".join(play_card(x) for x in td)}</div><p class="none allstarted" hidden>All kicked off.</p>' if td else "")
                   + (f'<div class="subt">Game lines the model is 8+ points off the market on · information, not picks: the game model has not beaten the closing line yet (Week 6 moneylines 7–7 vs favourites 9–5)</div><div class="plays">{"".join(gl_card(x) for x in gl)}</div><p class="none allstarted" hidden>All kicked off.</p>' if gl else "")
                   + '</section>')
    if ps:
        out.append(f'<section class="sec" id="parlay"><h2 class="t">Best parlay</h2><div class="ptwo">{parlay_block(ps)}</div></section>')
    if D["bd"]["games"]:
        out.append(f'<section class="sec" id="slate"><h2 class="t">Week {week} slate</h2>{slate(D)}<p class="none" style="margin-top:8px;font-size:12.5px">Model line and total, most likely game script. Tap a game for its board. Scores update live on game day.</p></section>')
    out.append(f'<section class="sec" id="record"><h2 class="t">Track record</h2>{record_block(R, latest_week)}</section>')
    # owner 10/30: "add players on the home page to my betslip without jumping to the parlay builder" - every "+ Builder" link becomes a
    # "+ Slip" toggle that writes the shared slip key (bs_slipk_w<W>, the same one the boards, player pages and builder use); a bar at the
    # bottom counts the legs and opens the betslip. Links still work without JavaScript (they open the builder with the legs added).
    out.append(f'<div class="hsbar" id="hsbar" data-week="{E(str(week))}"><b></b><a href="/build/">Open betslip</a></div>')
    return "\n".join(out), home_js(D["bd"]["games"]) + HOME_SLIP_JS

HOME_SLIP_JS = r"""<script>(function(){
  var bar = document.getElementById('hsbar'); if(!bar) return; var W = +bar.getAttribute('data-week'); if(!W) return;
  var KEY = 'bs_slipk_w' + W;
  function get(){ try { var a = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(a) ? a : []; } catch(e){ return []; } }
  function put(a){ try { localStorage.setItem(KEY, JSON.stringify(a)); } catch(e){} }
  function keysOf(a){ try { return new URL(a.getAttribute('href'), location.origin).searchParams.getAll('add'); } catch(e){ return []; } }
  var links = [].slice.call(document.querySelectorAll('a.more[href^="/build/?add="]'));
  links.forEach(function(a){ if(!a.dataset.lab) a.dataset.lab = a.textContent; });
  function paint(){ var s = get(), m = {}; s.forEach(function(k){ m[k] = 1; });
    links.forEach(function(a){ var ks = keysOf(a), all = ks.length && ks.every(function(k){ return m[k]; });
      a.classList.toggle('inslip', !!all); a.textContent = all ? (ks.length > 1 ? '\u2713 All in slip' : '\u2713 In slip') : (ks.length > 1 ? '+ Add all to slip' : '+ Slip');
      a.title = all ? 'In your betslip - tap to remove' : 'Add to your betslip (stays on this page)'; });
    bar.classList.toggle('on', s.length > 0); bar.querySelector('b').textContent = s.length + (s.length === 1 ? ' leg' : ' legs') + ' in your slip'; }
  document.addEventListener('click', function(ev){ var a = ev.target.closest && ev.target.closest('a.more[href^="/build/?add="]'); if(!a) return;
    if(ev.metaKey || ev.ctrlKey || ev.shiftKey) return;   // a modified click still opens the builder
    ev.preventDefault(); var ks = keysOf(a), s = get(), m = {}; s.forEach(function(k){ m[k] = 1; });
    var all = ks.every(function(k){ return m[k]; });
    if(all) s = s.filter(function(k){ return ks.indexOf(k) < 0; }); else ks.forEach(function(k){ if(!m[k]) s.push(k); });
    put(s); paint(); bar.animate && bar.animate([{transform: 'translateX(-50%) scale(1.06)'}, {transform: 'translateX(-50%) scale(1)'}], {duration: 220}); });
  window.addEventListener('storage', paint); paint();
})();</script>"""
