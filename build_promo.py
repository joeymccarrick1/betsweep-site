#!/usr/bin/env python3
"""Promoted bets: the slips BetSweep posts on X / Instagram, shown front and center on the home page.

Input  in/promos.json  ('PROMO - Promoted Bets'!A1:N100): Week | Slot | Title | Legs | FanDuel odds | FanDuel link | Status | Caption | Result | Posted | ...
       Legs = one per line "who | market | odds". Markets priced here: Anytime TD, First TD, Either TD (who = "A or B"),
       <stat> N+ (Passing/Rushing/Receiving Yards, Receptions, Longest Reception), game lines by the builder's leg text ("Bears ML", "Over 44.5").
Output out/promos.json (enriched: model % per leg and for the slip, fair odds, EV vs the FanDuel price, kickoffs, matchup ranks for TD legs)
       out/promo/<week>-<slot>-square.png (1080x1080) and -story.png (1080x1920): the X / IG cards.
Nothing is invented: a leg the model cannot price is shown with its FanDuel odds only and the slip's model % is left blank.
"""
import json, os, re, math, sys, asyncio, html
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
# optional argv[1]: a folder of the owner's FanDuel slip screenshots named <week>-<slot>.png|jpg (the site repo's promo-slips/);
# copied into in/promo_slips/ so the posters can show the real slip in the phone frame
_slips = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
if _slips and os.path.isdir(_slips):
    import shutil; os.makedirs(os.path.join(IN, "promo_slips"), exist_ok=True)
    for f in os.listdir(_slips):
        if f.lower().endswith((".png", ".jpg", ".jpeg")): shutil.copy2(os.path.join(_slips, f), os.path.join(IN, "promo_slips", f))
exec(open(os.path.join(HERE, "brand.py")).read())   # LOGO, WORDMARK, BANNER
E = html.escape
import sweep as SW   # owner 11/10: the Daily Sweep - a promo row whose Title starts with "Daily Sweep" (sweep.py has the rules)
import pairs as PAIRS

def num(x):
    try: return float(str(x).replace("+", "").replace(",", "").replace("%", ""))
    except Exception: return None
def dec(o): return 1 + o / 100 if o > 0 else 1 + 100 / (-o)
def am(p): return "" if not p or p <= 0 or p >= 1 else (f"+{round((1/p-1)*100)}" if p < .5 else f"-{round(p/(1-p)*100)}")
def odds_str(o): return f"+{int(o)}" if o > 0 else f"{int(o)}"

bd = json.load(open(os.path.join(OUT, "builder_data.json")))
WEEK = bd["week"]; GAMES = {g["gid"]: g for g in bd["games"]}
LEGS = [l for l in bd["legs"] if not l.get("alt")]
TD = {l["pl"]: l for l in LEGS if l["m"] == "Anytime TD"}
try: FTD = {x["n"]: x for x in json.load(open(os.path.join(OUT, "firsttd_all.json")))}
except Exception: FTD = {}
try: MULT = {r[0]: [float(x) for x in r[3:7]] for r in json.load(open(os.path.join(IN, "mult.json")))["values"][1:] if r[0].endswith("|td")}
except Exception: MULT = {}
try:
    rk = [x for x in json.load(open(os.path.join(IN, "ranks.json")))["values"] if x]; RH = {c: i for i, c in enumerate(rk[0])}
    RANK_S = {x[0]: x for x in rk[1:33]}; RANK_3 = {x[0]: x for x in rk[33:]}
except Exception: RH, RANK_S, RANK_3 = {}, {}, {}

# roles (RB1, WR2 ...) by TD probability within team+position, for the script multipliers
_role = {}
_bt = {}
for l in TD.values(): _bt.setdefault((l["tm"], l["pos"]), []).append(l)
for (tm, pos), ls in _bt.items():
    ls.sort(key=lambda l: -l["p"])
    for k, l in enumerate(ls, 1): _role[l["pl"]] = f"{pos}{k}"
def p_script(l, k):
    m = MULT.get(_role.get(l["pl"], "") + "|td", [1, 1, 1, 1]); return min(.97, 1 - (1 - l["p"]) ** m[k])

def td_rank(l):
    """Opponent's TD-allowed rank at the player's position (1 = allows the most): (season, last 3)."""
    if not RH or not l: return None
    pos = l["pos"]; opp = l["opp"]
    stat = {"RB": "RB Rush TD", "WR": "WR Rec TD", "TE": "TE Rec TD", "QB": "QB Rush TD"}.get(pos)
    try: return int(RANK_S[opp][RH[stat]]), int(RANK_3[opp][RH[stat]])
    except Exception: return None

AMBIG = set()   # game-line leg texts that matched lines in more than one game (promo check)
def _gl_find(w):
    """game-line leg by its builder text ('Bears ML', 'Over 44.5', 'KC -3.5'), alternate lines included. Totals share names across
    games, so the text may carry the game: 'Over 43.5 (KC-SEA)' (owner's 10/25 SNF promo matched NO-PIT's Over 43.5 without it)."""
    m = re.match(r"^(.*?)\s*\(([A-Z]{2,3}-[A-Z]{2,3})\)\s*$", w.strip())
    name, gid = (m.group(1), m.group(2)) if m else (w.strip(), None)
    hits = [l for l in bd["legs"] if l.get("gl") and l["pl"].lower() == name.lower() and (gid is None or l["g"] == gid)]
    if gid is None and len({l["g"] for l in hits}) > 1:
        AMBIG.add(w.strip())
        print(f"WARN promo leg '{w}' matches game lines in {sorted({l['g'] for l in hits})} - write it as '{name} (GAME)', e.g. '{name} ({hits[0]['g']})'")
    return hits[0] if hits else None
def slip_key(w, mk):
    """the builder's 'player|market|line' key for a promo leg, so Tail can save it to a slip and /me/ can grade it"""
    ml = mk.lower()
    if ml in ("anytime td", "anytime touchdown", "atd"): return f"{w}|Anytime TD|1"
    if ml in ("first td", "first touchdown", "ftd"): return f"{w}|First TD|1"
    if ml.startswith("either"): return f"{w}|Either TD|1"
    m = re.match(r"(.+?)\s+(\d+(?:\.\d+)?)\+?$", mk)
    if m: return f"{w}|{m.group(1).strip().title().replace('Tds', 'TDs')}|{int(__import__('math').floor(float(m.group(2)) + 0.5))}"
    l = _gl_find(w)   # game lines incl. FanDuel's alternate spreads / totals (10/25: 'KC -3.5' is an alt spread)
    if l: return f"{l['pl']}|{l['m']}|{int(__import__('math').floor(float(l['ln'] or 1) + 0.5))}"
    return f"{w}|{mk}|1"
def price_leg(who, market, odds):
    """-> dict(p, bk, gid, tm, opp, kick, ko, disp, rank)"""
    mk = market.strip(); w = who.strip(); out = {"p": None, "bk": None, "gid": "", "tm": "", "opp": "", "kick": "", "ko": None, "disp": f"{w} · {mk}", "rank": None, "key": slip_key(w, mk)}
    def fill(l):
        out["src"] = {k: l.get(k) for k in ("pl", "m", "g", "tm", "c", "gl")}
        try: out["risk"] = SW.risk_score(l, bd)   # 0-1 low, 2-3 "Some risk", 4+ "High risk" - what the builder's slip shows before the live list
        except Exception: out["risk"] = None
        g = GAMES.get(l["g"], {}); hist = next((h[1] for h in (l.get("fh") or []) if "/" in str(h[1])), "")
        out.update(gid=l["g"], tm=l["tm"], opp=l["opp"], pos=l.get("pos", ""), kick=g.get("kick", ""), ko=g.get("ko"), bk=l["bk"], hist=hist, fdid=(l.get("fd") or {}).get("m") and (l["fd"]["m"], l["fd"]["s"]),
                   _bl={"pl": l["pl"], "m": l["m"], "ln": l["ln"], "bks": l.get("bks"), "ba": l.get("ba"), "gl": l.get("gl")})   # DraftKings / Hard Rock ids for booklinks.py
    ml = mk.lower()
    if ml in ("anytime td", "anytime touchdown", "atd"):
        l = TD.get(w)
        if l: fill(l); out["p"] = l["p"]; out["rank"] = td_rank(l); out["disp"] = f"{w} anytime TD"
        return out
    if ml in ("first td", "first touchdown", "ftd"):
        x = FTD.get(w); l = TD.get(w)
        if l: fill(l); out["_bl"] = None   # the anytime-TD leg's ids would send the wrong market to the other books
        if l: out["src"] = dict(out["src"], m="First TD", c=f"{l.get('pos', '')}_FTD")
        if x: out["p"] = x["pr"]; out["bk"] = (1 / dec(float(x["fd"]))) if x.get("fd") else out["bk"]
        out["disp"] = f"{w} first TD"; return out
    if ml in ("either td", "either player td", "either player anytime td", "either"):
        names = re.split(r"\s+or\s+|\s*/\s*", w)
        if len(names) == 2 and names[0] in TD and names[1] in TD:
            A, B = TD[names[0]], TD[names[1]]; g = GAMES.get(A["g"], {})
            probs = [x / 100 for x in g.get("probs", [25, 25, 25, 25])]; per = []
            for k in range(4):
                idx = lambda l: k if l["tm"] == g.get("a") else {0: 3, 3: 0}.get(k, k)
                pa, pb = p_script(A, idx(A)), p_script(B, idx(B)); pe = 1 - (1 - pa) * (1 - pb)
                if A["tm"] == B["tm"]: pe -= 0.02 * min(pa, pb)
                per.append(pe)
            fill(A); out["_bl"] = None; out["p"] = sum(p * q for p, q in zip(per, probs)); out["worst"] = min(per); out["src"] = dict(out["src"], m="Either TD")   # either-TD is not a DraftKings / Hard Rock market
            # owner 11/8-11/9: an either-or leg is judged as a pair (pairs.py). The chance comes from the legs' own per-ending chances, which
            # mix back to what the site shows for each player (the multiplier form above did not: two Lions pass-catchers came out ABOVE the
            # plain product, and two players in different games were mixed over one game's endings). Its risk is the safer player's.
            try:
                _pe = PAIRS.either(A, B, GAMES)
                if _pe:
                    out["p"] = _pe["p"]
                    if _pe.get("worst") is not None: out["worst"] = _pe["worst"]
                    out["hedge"] = round(_pe["hedge"], 4)
                out["risk"] = PAIRS.risk(A, B, bd); out["risks"] = [SW.risk_score(A, bd), SW.risk_score(B, bd)]
            except Exception as _e: print("note: pair pricing fell back to the old form:", _e)
            out["tm"] = f"{A['tm']}/{B['tm']}" if A["tm"] != B["tm"] else A["tm"]; out["opp"] = ""
            out["bk"] = 1 - (1 - A["bk"]) * (1 - B["bk"])   # FanDuel-equivalent from the two singles
            ra, rb = td_rank(A), td_rank(B); out["rank"] = None; out["ranks"] = [ra, rb]
        out["disp"] = f"{w} · either scores a TD"; return out
    m = re.match(r"(.+?)\s+(\d+(?:\.\d+)?)\+?$", mk)   # "Receiving Yards 50+"
    if m:
        market_name, line = m.group(1).strip(), float(m.group(2))
        out["disp"] = f"{w} {int(line) if line.is_integer() else line}+ {market_name.lower()}"
        rungs = sorted([l for l in LEGS if l["pl"] == w and l["m"].lower() == market_name.lower()], key=lambda l: float(l["ln"]))
        for l in rungs:
            if abs(float(l["ln"]) - line) < 0.01: fill(l); out["p"] = l["p"]; return out
        if len(rungs) >= 2:   # a rung FanDuel added below/above our pull: fit a normal through the two nearest priced rungs
            try:
                from statistics import NormalDist; N = NormalDist()
                a, b = sorted(rungs, key=lambda l: abs(float(l["ln"]) - line))[:2]
                z1, z2 = N.inv_cdf(1 - a["p"]), N.inv_cdf(1 - b["p"])
                if z1 != z2:
                    sd = (float(b["ln"]) - float(a["ln"])) / (z2 - z1); mu = float(a["ln"]) - 0.5 - z1 * sd
                    if sd > 0:
                        fill(a); out["p"] = min(0.98, max(0.02, 1 - N.cdf((line - 0.5 - mu) / sd))); out["bk"] = None; out["est"] = True; out["fdid"] = None; out["_bl"] = None   # estimated rung: no betslip ID (would add the wrong line)
            except Exception: pass
        return out
    l = _gl_find(w)   # game lines: builder leg text ("Bears ML", "Over 44.5", "Ravens -6.5", "Over 43.5 (KC-SEA)"), alternate lines included
    if l:
        fill(l); out["p"] = l["p"]; out["tm"] = ""; out["opp"] = ""; out["disp"] = f"{l['pl']} ({l.get('ms') or l['m']})"
        out["glx"] = {"k": l["gl"]["k"], "side": l["gl"]["side"], "ln": l["ln"], "m": l["m"]}   # live grading on the home page
        return out
    return out

# ---------- slip probability: the parlay builder's method (owner 10/26 - one number on the site) ----------
# Gaussian copula over the legs' model probabilities with the builder's same-game correlations (bd["corr"]: same player / teammate /
# opponent by stat code; bd["glcorr"]: player stat vs the game's margin / total for game-line legs). Legs in different games are
# independent. Port of joint() in build_builder.py's page script (Monte Carlo, fixed seed). The old leg-product number is kept as
# "p_indep" so Tuesday's grading can score both against what happened.
CORR = bd.get("corr") or {}; GLCORR = bd.get("glcorr") or {}
def _glprop(gl, x):
    r = GLCORR.get(x.get("c") or "")
    if not r: return 0.0
    if gl["gl"]["k"] == "M": return r["margin"] if gl["gl"]["side"] == x.get("tm") else -r["margin"]
    return r["total"] if gl["gl"]["side"] == "OVER" else -r["total"]
def _corr(a, b):
    if not a.get("g") or a.get("g") != b.get("g"): return 0.0
    if a.get("gl") and b.get("gl"): return 0.0 if a["gl"]["k"] != b["gl"]["k"] else (0.999 if a["gl"]["side"] == b["gl"]["side"] else -0.999)
    if a.get("gl"): return _glprop(a, b)
    if b.get("gl"): return _glprop(b, a)
    if not a.get("c") or not b.get("c"): return 0.0
    rel = "SP" if a["pl"] == b["pl"] else ("TM" if a.get("tm") == b.get("tm") else "OPP")
    k = sorted([a["c"], b["c"]]); return float(CORR.get(f"{rel}|{k[0]}|{k[1]}", 0) or 0)
def joint_p(rows):
    """rows: [{"p", "src" (builder leg or None)}] -> P(all hit). First TD legs: two in one game cannot both hit; a first TD
    makes the same player's anytime TD redundant (as the builder)."""
    srcs = [r.get("src") or {} for r in rows]
    ftd = [x for x in srcs if x.get("m") == "First TD"]
    for i in range(len(ftd)):
        for j in range(i + 1, len(ftd)):
            if ftd[i].get("g") and ftd[i].get("g") == ftd[j].get("g"): return 0.0
    keep = [r for r in rows if not ((r.get("src") or {}).get("m") == "Anytime TD" and any(f.get("pl") == r["src"].get("pl") for f in ftd))]
    n = len(keep)
    if not n: return 0.0
    ls = [r.get("src") or {} for r in keep]
    C = [[1.0 if i == j else _corr(ls[i], ls[j]) for j in range(n)] for i in range(n)]
    if not any(C[i][j] for i in range(n) for j in range(n) if i != j):
        out = 1.0
        for r in keep: out *= r["p"]
        return out
    import numpy as np
    from statistics import NormalDist
    z = np.array([NormalDist().inv_cdf(min(0.995, max(0.005, r["p"]))) for r in keep])
    M = np.array(C); w, v = np.linalg.eigh(M); M = v @ np.diag(np.clip(w, 1e-6, None)) @ v.T
    g = np.random.default_rng(7).multivariate_normal(np.zeros(n), M, size=100000)
    return float(np.mean(np.all(g <= z, axis=1)))

# ---------- promo checks (owner 10/26): stop a broken card before it goes up ----------
_PLAYERS = {l["pl"] for l in bd["legs"]}
def promo_checks(legs):
    """-> (blocking issues, warnings). Blocking: a leg that matched nothing in the builder, a game-line text that matches several games,
    or a game line from a different game than every other leg of a one-game slip (the 10/25 'Over 43.5' matched NO-PIT on a KC-SEA slip).
    Warnings: a found leg the model cannot price, a Tail key that fell back to the default."""
    block, warn = [], []
    for l in legs:
        if not l.get("gid") and not (l.get("market") or "").lower().startswith("either"):
            # a player whose legs are all gone is usually a game that has kicked off (the builder drops started games) - keep the card;
            # a player who is in the builder but not on this market / line is a typo or a line FanDuel does not offer - hold the card
            if l["who"].strip() in _PLAYERS: block.append(f"'{l['who']} | {l['market']}' did not match any FanDuel leg in the builder (he has other legs - check the market / line)")
            else: warn.append(f"{l['who']}: not in this build (game started, or no FanDuel props)")
        if l["who"].strip() in AMBIG: block.append(f"'{l['who']}' matches game lines in several games - write it as '{l['who']} (GAME)'")
        if l.get("gid") and l.get("p") is None: warn.append(f"{l['who']} {l['market']}: no model price")
        if str(l.get("key", "")).endswith(f"|{l['market']}|1") and not (l.get("market") or "").lower().endswith("td"): warn.append(f"{l['who']} {l['market']}: Tail key is a fallback")
    gl_legs = [l for l in legs if (l.get("src") or {}).get("gl")]; other = {l["gid"] for l in legs if l.get("gid") and not (l.get("src") or {}).get("gl")}
    if len(other) == 1:
        for l in gl_legs:
            if l["gid"] not in other: block.append(f"game line '{l['who']}' matched {l['gid']} but every other leg is {next(iter(other))}")
    return block, warn

def parse_rows():
    try: v = json.load(open(os.path.join(IN, "promos.json")))["values"]
    except Exception: return []
    out = []
    for r in v[1:]:
        r = list(r) + [""] * (14 - len(r))
        wk, slot, title, legs_txt, fd_odds, link, status, caption, result, posted = r[:10]
        if not title or str(status).strip().upper() not in ("LIVE", "HIDDEN", ""): continue
        if num(wk) != float(WEEK): continue
        legs = []
        for line in str(legs_txt).splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2 or not parts[0]: continue
            who, market = parts[0], parts[1]; odds = num(parts[2]) if len(parts) > 2 else None
            d = price_leg(who, market, odds); d.update(who=who, market=market, o=odds); legs.append(d)
        if not legs: continue
        fdo = num(fd_odds)
        _gids = [l["gid"] for l in legs if l.get("gid")]
        # owner 10/22: the TNF SGP posted at +679 (legs multiplied) was +595 on FanDuel, the lotto +8850 vs +5337 - a same-game parlay is
        # priced by FanDuel's SGP engine with the correlation built in, so multiplying the legs overstates it. Only cross-game slips get the
        # multiplied price; a same-game slip needs FanDuel's own SGP price typed into column E (else the card shows no price).
        if fdo is None and len(_gids) == len(set(_gids)) and all(l["o"] is not None for l in legs):
            dd = 1
            for l in legs: dd *= dec(l["o"])
            fdo = round((dd - 1) * 100) if dd >= 2 else -round(100 / (dd - 1))
        p = 1.0; priced = all(l["p"] is not None for l in legs); p_indep = None
        if priced:
            for l in legs: p *= l["p"]
            p_indep = p
            p = joint_p(legs)
        block, warn = promo_checks(legs)
        if link.strip() and block:
            # owner 10/29 ("no 777 bet on the home page"): when the owner pasted FanDuel's own link / share code, the card's job is to send people
            # to THAT slip - a leg the builder cannot match (FanDuel re-issued the ladder, an either-TD pair, a market the pull does not carry)
            # is a pricing gap, not a broken card. Keep the card; the unmatched legs show without a model price. Only the game-line
            # ambiguity check stays blocking (a wrong game is a wrong bet).
            keep = [b_ for b_ in block if "matches game lines in several games" in b_]
            warn = warn + [b_ + " (card kept: the row has its own FanDuel link)" for b_ in block if b_ not in keep]; block = keep
        for b_ in block: print(f"PROMO CHECK FAILED - slot {slot} '{title.strip()}': {b_} - card held back")
        for w_ in warn: print(f"promo check warning - slot {slot} '{title.strip()}': {w_}")
        gids = [l["gid"] for l in legs if l["gid"]]; same = len(gids) != len(set(gids))
        if not link.strip() and legs and all(l.get("fdid") for l in legs):   # no link in the sheet: build the multi-leg betslip link from the builder's FanDuel IDs
            link = "https://sportsbook.fanduel.com/addToBetslip?" + "&".join(f"marketId[{i}]={l['fdid'][0]}&selectionId[{i}]={l['fdid'][1]}" for i, l in enumerate(legs))
        import booklinks as BL
        books = BL.links([l.get("_bl") or {} for l in legs]) if all(l.get("_bl") for l in legs) else {}
        for l in legs: l.pop("fdid", None); l.pop("_bl", None); l.pop("src", None)
        kos = [l["ko"] for l in legs if l["ko"]]
        out.append({"week": int(num(wk)), "slot": int(num(slot) or 0), "title": title.strip(), "legs": legs, "fd": fdo, "fd_dec": dec(fdo) if fdo else None, "link": link.strip(),
                    "status": (status or "LIVE").strip().upper(), "caption": caption.strip(), "result": result.strip().upper(), "posted": posted.strip(),
                    "p": p if priced else None, "p_indep": p_indep, "fair": am(p) if priced else "", "checks": {"block": block, "warn": warn}, "ev": ((p * dec(fdo) - 1) if (priced and fdo) else None),
                    "same_game": same, "first_ko": min(kos) if kos else None, "last_ko": max(kos) if kos else None, "books": books,
                    "img": {"feed": f"/promo/{int(num(wk))}-{int(num(slot) or 0)}-feed.png", "square": f"/promo/{int(num(wk))}-{int(num(slot) or 0)}-square.png", "story": f"/promo/{int(num(wk))}-{int(num(slot) or 0)}-story.png"}})
    out.sort(key=lambda x: x["slot"])
    # owner 11/10: the Daily Sweep. sweep.py marks at most one row per game day (Title starts with "Daily Sweep"); the home page leads
    # with it and keeps its own record. Printed for the run log, with the house-rule checks the owner set for these slips (low-risk
    # legs only, about four legs, near +300) as WARNINGS - the card still goes up; the owner decides.
    for w_ in SW.one_per_day(out): print("DAILY SWEEP WARNING -", w_)
    for p_ in out:
        if not p_.get("sweep"): continue
        risky = [f'{l["who"]} {l["market"]} ({SW.risk_tag(l["risk"])})' for l in p_["legs"] if l.get("risk") is not None and l["risk"] >= 2]
        notes = ([f"{len(p_['legs'])} legs (house shape is about four)"] if not 3 <= len(p_["legs"]) <= 5 else []) \
              + ([f"price {odds_str(p_['fd'])} (house shape is near +300)"] if p_.get("fd") and not 200 <= p_["fd"] <= 450 else []) \
              + (["no FanDuel price in column E - a win could not be counted in units"] if not p_.get("fd") else []) \
              + (["risky legs: " + "; ".join(risky)] if risky else [])
        print(f'daily sweep: {SW.day_label(p_["first_ko"])} - slot {p_["slot"]} "{p_["title"]}" {odds_str(p_["fd"]) if p_.get("fd") else "no price"}, {len(p_["legs"])} legs' + (f' | status {p_["status"]}' if p_["status"] != "LIVE" else ""))
        for n_ in notes: print(f'DAILY SWEEP WARNING - slot {p_["slot"]}: {n_}')
    return out

# ---------- cards ----------
CARD_CSS = """
*{box-sizing:border-box;margin:0}
body{background:#0f141c;color:#efe9da;font-family:'IBM Plex Sans',system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.card{position:relative;width:1080px;overflow:hidden;background:#0f141c url(data:image/png;base64,BANNER) top/cover no-repeat;display:flex;flex-direction:column}
.card.square{height:1080px}.card.story{height:1920px}
.card::before{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(15,20,28,.55) 0%,rgba(15,20,28,.92) 28%,#0f141c 46%)}
.in{position:relative;display:flex;flex-direction:column;height:100%;padding:56px 64px 48px}
.hd{display:flex;align-items:center;justify-content:space-between}
.hd img{height:78px}
.tag{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:28px;letter-spacing:.2em;text-transform:uppercase;color:#fff;background:#d7332a;padding:8px 18px;border-radius:6px}
h1{font-family:'Barlow',sans-serif;font-style:italic;font-weight:800;font-size:76px;line-height:1;letter-spacing:-.02em;margin:40px 0 10px}
.sub{font-size:26px;color:#9aa3b2;margin-bottom:26px}
.legs{display:flex;flex-direction:column;gap:0;background:rgba(22,29,40,.9);border:1px solid #2b3442;border-radius:18px;padding:6px 28px;flex:0 1 auto;min-height:0;overflow:hidden}
.ft{flex-shrink:0}
.leg{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 24px;align-items:baseline;padding:16px 0;border-top:1px solid #2b3442}
.leg:first-child{border-top:0}
.leg b{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:40px;letter-spacing:.01em;line-height:1.05}
.leg small{display:block;color:#9aa3b2;font-size:22px;margin-top:2px}
.leg .o{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:40px;font-variant-numeric:tabular-nums}
.leg .mp{grid-column:2;color:#5fcf93;font-size:21px;text-align:right}
.legs.n7 .leg{padding:11px 0} .legs.n7 .leg b{font-size:33px} .legs.n7 .leg small{font-size:19px} .legs.n7 .leg .o{font-size:33px} .legs.n7 .leg .mp{font-size:18px}
.legs.n10 .leg{padding:7px 0;grid-template-columns:minmax(0,1fr) auto} .legs.n10 .leg b{font-size:27px} .legs.n10 .leg small{display:none} .legs.n10 .leg .o{font-size:27px} .legs.n10 .leg .mp{display:none}
.ft{margin-top:auto;display:grid;grid-template-columns:auto 1fr auto;align-items:end;gap:28px;padding-top:30px}
.ft .big{font-family:'Barlow Condensed',sans-serif;font-weight:800;font-size:112px;line-height:.9;letter-spacing:-.01em}
.ft .big small{display:block;font-size:22px;letter-spacing:.18em;text-transform:uppercase;color:#1493ff;font-weight:700;margin-bottom:8px}
.ft .model{font-size:24px;color:#9aa3b2;line-height:1.4} .ft .model b{color:#efe9da}
.ft .site{font-family:'Barlow',sans-serif;font-style:italic;font-weight:800;font-size:34px;text-align:right} .ft .site i{color:#d7332a;font-style:normal}
.ft .site span{display:block;font-family:'Barlow Condensed',sans-serif;font-style:normal;font-weight:600;font-size:18px;letter-spacing:.12em;text-transform:uppercase;color:#9aa3b2;margin-top:4px}
.story h1{font-size:92px;margin-top:70px} .story .sub{font-size:30px} .story .leg b{font-size:48px} .story .leg .o{font-size:48px} .story .leg small{font-size:26px} .story .leg{padding:22px 0}
.story .legs.n7 .leg{padding:14px 0} .story .legs.n7 .leg b{font-size:40px} .story .legs.n7 .leg .o{font-size:40px} .story .legs.n7 .leg small{font-size:22px}
.story .legs.n10 .leg{padding:11px 0} .story .legs.n10 .leg b{font-size:34px} .story .legs.n10 .leg .o{font-size:34px} .story .legs.n10 .leg small{display:block;font-size:19px}
.story .ft .big{font-size:150px} .story .ft .model{font-size:28px}
.disc{position:relative;font-size:17px;color:#6f7886;padding:14px 64px 0;line-height:1.35}
"""
def card_html(pr, kind):
    n = len(pr["legs"]); cls = "n10" if n >= 9 else ("n7" if n >= 6 else "")
    legs = ""
    for l in pr["legs"]:
        rk = l.get("rank"); pos = {"RB": "RB", "WR": "WR", "TE": "TE", "QB": "QB rush"}.get((TD.get(l["who"]) or {}).get("pos", ""), "")
        mk = (f"{l['opp']} #{rk[0]} vs {pos} TDs" + (f", #{rk[1]} last 3" if rk[1] != rk[0] else "")) if rk else (f"vs {l['opp']}" if l.get("opp") and "/" not in l.get("tm", "") else "")
        sub = " · ".join(s for s in [l.get("kick", ""), mk] if s)
        mp = f'<span class="mp">model {l["p"]*100:.0f}%</span>' if l.get("p") is not None else ""
        who = l["who"]; mlabel = l["disp"][len(who):].strip(" ·") if l["disp"].startswith(who) else l["disp"]
        sub = " · ".join(x for x in [mlabel, sub] if x)
        legs += f'<div class="leg"><b>{E(who)}</b><span class="o">{E(odds_str(l["o"])) if l["o"] is not None else ""}</span><small>{E(sub)}</small>{mp}</div>'
    model = f'<b>Model {pr["p"]*100:.1f}%</b> to hit · fair {E(pr["fair"])}' if pr.get("p") else "Model price not available for every leg"
    sub = f'Week {pr["week"]} · {n} legs · one tap on FanDuel'
    return f'''<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:ital,wght@1,800&family=Barlow+Condensed:wght@600;700;800&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CARD_CSS.replace("BANNER", BANNER)}</style></head><body>
<div class="card {kind}"><div class="in">
 <div class="hd"><img src="data:image/png;base64,{WORDMARK}" alt="BetSweep"><span class="tag">Promoted</span></div>
 <h1>{E(pr["title"])}</h1><div class="sub">{E(sub)}</div>
 <div class="legs {cls}">{legs}</div>
 <div class="ft"><div class="big"><small>FanDuel</small>{E(odds_str(pr["fd"])) if pr.get("fd") else ""}</div><div class="model">{model}<br>Snapshot at post time; prices move.</div>
  <div class="site">betsweep<i>.co/b/w{pr["week"]}-{pr["slot"]}</i><span>Picks. Data. Edge. Sweep.</span></div></div>
</div><div class="disc">21+ · information, not advice · 1-800-GAMBLER</div></div></body></html>'''

import posters as SOCIAL   # 10/27: the poster module was renamed from social.py (social.py is now the Social page) - build_promo crashed on render without it
COLORS = {}
for g in bd["games"]: COLORS[g["a"]] = g["ca"][0]; COLORS[g["b"]] = g["cb"][0]
def kick_line(pr):
    ks = [l.get("kick", "") for l in pr["legs"] if l.get("kick")]
    days = sorted({k.split()[0] for k in ks}, key=lambda d: ["Thu", "Fri", "Sat", "Sun", "Mon", "Tue", "Wed"].index(d) if d in ["Thu", "Fri", "Sat", "Sun", "Mon", "Tue", "Wed"] else 9)
    first = min((l["ko"], l["kick"]) for l in pr["legs"] if l.get("ko"))[1] if any(l.get("ko") for l in pr["legs"]) else ""
    dn = {"Thu": "Thursday", "Sun": "Sunday", "Mon": "Monday", "Sat": "Saturday"}
    return (" + ".join(dn.get(d, d) for d in days) + (f" · first kick {first.split(' ', 1)[1]} CT" if first else "")) if days else f'Week {pr["week"]}'
def callouts(pr):
    """Up to 4 tiles: for a short slip, one per leg (matchup rank + this season); for a long slip, the slip's story."""
    if len(pr["legs"]) <= 6:
        return []   # the leg rows already carry matchup + this-season
        out = []
        for l in pr["legs"]:
            rk = l.get("rank"); pos = l.get("pos", "")
            bits = []
            if rk: bits.append(f'<i>{E(l["opp"])} #{rk[0]}</i> vs {"QB rush" if pos == "QB" else pos} TDs' + (f', #{rk[1]} last 3' if rk[1] != rk[0] else ''))
            if l.get("hist"): bits.append(f'scored in <i>{E(l["hist"].replace(" this season", ""))}</i> this season')
            if l.get("p") is not None: bits.append(f'model <i>{l["p"]*100:.0f}%</i>')
            out.append((l["who"], " · ".join(bits), COLORS.get(l.get("tm", ""), "#d7332a")))
        return out
    ws = [l.get("worst") for l in pr["legs"] if l.get("worst") is not None]
    out = [(f'{len({l["gid"] for l in pr["legs"] if l.get("gid")})} games, one leg each', "no two legs ride the same game", "#d7332a")]
    if ws: out.append((f'{min(ws)*100:.0f}% floor', "every pair's worst game script still clears this", "#1493ff"))
    if pr.get("p"): out.append((f'{pr["p"]*100:.1f}% · fair {pr["fair"]}', "the model's number for the whole slip", "#5fcf93"))
    return out[:4]

async def render(promos):
    from playwright.async_api import async_playwright
    d = os.path.join(OUT, "promo"); os.makedirs(d, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for pr in promos:
            pr["kick_line"] = kick_line(pr); slip, ratio = SOCIAL.slip_image(IN, pr); cos = callouts(pr)
            for kind, h in (("feed", 1350), ("square", 1080), ("story", 1920)):
                pg = await b.new_page(viewport={"width": 1080, "height": h}, device_scale_factor=1)
                await pg.set_content(SOCIAL.poster_html(pr, kind, BANNER, WORDMARK, slip, COLORS, cos, ratio), wait_until="networkidle")
                await pg.wait_for_timeout(400)
                await pg.screenshot(path=os.path.join(d, f'{pr["week"]}-{pr["slot"]}-{kind}.png'), clip={"x": 0, "y": 0, "width": 1080, "height": h})
                await pg.close()
        await b.close()

if __name__ == "__main__":
    promos = parse_rows()
    json.dump(promos, open(os.path.join(OUT, "promos.json"), "w"), indent=1)
    for pr in promos:
        unpriced = [l["who"] for l in pr["legs"] if l["p"] is None]
        print(f'{pr["title"]}: {len(pr["legs"])} legs, FanDuel {odds_str(pr["fd"]) if pr["fd"] else "?"}, model {pr["p"]*100:.2f}% fair {pr["fair"]}' if pr["p"] else f'{pr["title"]}: {len(pr["legs"])} legs, unpriced: {unpriced}', f'| status {pr["status"]}' + (f' | unpriced legs: {unpriced}' if unpriced and pr["p"] else ""))
    if promos and "--no-images" not in sys.argv:
        asyncio.run(render(promos)); print(f"wrote {len(promos)*3} promo posters (feed 4:5, square, story) -> out/promo/")
    print(f"wrote out/promos.json: {len(promos)} promoted bets for week {WEEK}")
