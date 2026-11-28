#!/usr/bin/env python3
"""build_today.py - /today/ : the page the installed app opens to (owner 11/4: "I want BetSweep to be one of the few apps on the phone during
football season - Sleeper, FanDuel, BetSweep").

One scroll for the day: what kicks off today (or next), the model's plus-money looks for THOSE games, the news that moved the model, your slips
and your Sleeper guys in today's games, the rest of the week, and the record. Built once per rebuild; the browser picks "today" from the
kickoff stamps (America/Chicago), so the same build serves Thursday through Monday. Also writes out/today.json with a ready morning brief per
game day (title/body/url) for the push function (slip-alerts.ts mode "brief").

Reads: out/builder_data.json, out/best_parlays.json, in/gamelines.json, in/ctx_news.json (news desk), in/ctx_stakes.json, in/weather.json
(flags.Engine), out/voice.json (optional - "Sweep says" lines the rebuild session writes per RUNBOOK Step 3-voice), in/scorecard.json +
in/legsnaps.json (record, via home.py). Writes out/today.html (body; build_site wraps it) and out/today.json.
"""
import json, os, re, sys, html, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
sys.path.insert(0, HERE)
import home as HOME, flags as FLAGS, live as LIVE, wxfx as WXFX
E = html.escape
TEAM_OF = {"Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN",
           "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB", "Houston Texans": "HOU", "Indianapolis Colts": "IND",
           "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
           "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG", "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
           "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS"}
# hunches by game for the card line (out/hunches.json is written by hunches.py earlier in the build; absent on the very first pass)
try:
    HUNCH = {}
    for _h in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "hunches.json")))["hunches"]:
        if not _h.get("gone"): HUNCH.setdefault(_h["g"], []).append(_h)
except Exception: HUNCH = {}

def vals(n):
    p = os.path.join(IN, n)
    if not os.path.exists(p): return []
    d = json.load(open(p)); return d.get("values", d) if isinstance(d, dict) else d
def num(v):
    try: return float(str(v).replace("+", ""))
    except Exception: return None
def odds(o):
    try: o = int(round(float(o)))
    except Exception: return ""
    return f"+{o}" if o > 0 else str(o)
CT = dt.timezone(dt.timedelta(hours=-6))   # the site runs on Central time; CST in November (the browser recomputes with the real zone)
def ct_date(ms): return dt.datetime.fromtimestamp(ms / 1000, CT).strftime("%Y-%m-%d") if ms else None
def ct_label(ms): return dt.datetime.fromtimestamp(ms / 1000, CT).strftime("%a %-m/%-d") if ms else ""

def game_lines():
    """FanDuel spread (home team's point) and total per game from 'AUTO - FanDuel Game Lines'."""
    rows = vals("gamelines.json"); H = {c: i for i, c in enumerate(rows[0])} if rows else {}
    out = {}
    for r in rows[1:]:
        r = r + [""] * (len(rows[0]) - len(r)); g = r[H["Game"]]
        m = re.match(r"^(.*?) @ (.*)$", g)
        if not m: continue
        away, home = TEAM_OF.get(m.group(1).strip()), TEAM_OF.get(m.group(2).strip())
        if not away or not home: continue
        gid = "-".join(sorted([away, home])); d = out.setdefault(gid, {"away": away, "home": home})
        mk, side, pt, o = r[H["Market"]], r[H["Side"]], num(r[H["Point"]]), num(r[H["FanDuel odds"]])
        if mk == "Spread" and TEAM_OF.get(side.strip()) == home and pt is not None: d["spread"] = pt
        elif mk == "Total" and side.strip().lower() == "over" and pt is not None: d["total"] = pt
        elif mk == "Moneyline" and TEAM_OF.get(side.strip()) == home and o is not None: d["ml_home"] = o
        elif mk == "Moneyline" and TEAM_OF.get(side.strip()) == away and o is not None: d["ml_away"] = o
    return out

def freeze(prev, fresh, now_ms):
    """The pre-kickoff copy of what each game's card said (11/27): the Final card on Today reads it once the game is over, when
    FanDuel's lines and props have left the sheet. prev = {gid: entry} from the last build, fresh = {gid: (kickoff ms, entry)} from this
    one. A game that has not kicked off takes this build's entry - keeping the last copy of the spread, the total or the looks when this
    build has none (FanDuel pulls a game's markets shortly before kickoff). A game that has kicked off keeps what it had: nothing about
    it is ever written after the fact."""
    out = dict(prev or {})
    for gid, (ko, e) in fresh.items():
        if not ko or now_ms >= ko: continue
        old = out.get(gid) or {}; e = dict(e)
        for k in ("sp", "tot"):
            if e.get(k) is None and old.get(k) is not None: e[k] = old[k]
        if not e.get("looks") and old.get("looks"): e["looks"] = old["looks"]
        out[gid] = e
    return out

def sections(IN_, OUT_, clone=None):
    D = HOME.load(IN_, OUT_); bd = D["bd"]; W = bd.get("week") or 0
    games = sorted(bd["games"], key=lambda g: g.get("ko") or 0); G = {g["gid"]: g for g in games}
    try: FE = FLAGS.Engine(IN_, W)
    except Exception as e: print("today: flags engine failed", e); FE = None
    GL = game_lines()
    try: VOICE = json.load(open(os.path.join(OUT_, "voice.json")))
    except Exception: VOICE = {}
    vg = VOICE.get("games") or {}; vl = VOICE.get("legs") or {}
    # owner 11/10 (deep dive): Under of the day - one under per game day from the model's 55%+ unders, with its own record (under_day.py)
    under_html = ""
    try:
        import under_day as UD
        print(UD.build(IN_, OUT_)); under_html = UD.card(OUT_, "home")
    except Exception as e: print("under of the day: skipped -", e)
    # owner 11/10 (deep dive): "lines to check" - teammates of a player ruled out after the last FanDuel props pull (stale_lines.py)
    stale_html = ""
    try:
        import stale_lines as STL
        print(STL.build(IN_, OUT_)); stale_html = STL.card(OUT_)
    except Exception as e: print("lines to check: skipped -", e)
    # audit 11/10: the "Share this take" button the boards carry under each Sweep says line (owner 11/10) on the home cards too.
    # build_boards.py writes the buttons and the share-card script to out/sweepcards.json; missing or another week = no button.
    try:
        SWC = json.load(open(os.path.join(OUT_, "sweepcards.json")))
        if int(SWC.get("week") or 0) != int(W): SWC = {}
    except Exception: SWC = {}
    swb = SWC.get("btn") or {}
    try: NEWS = json.load(open(os.path.join(IN_, "ctx_news.json")))
    except Exception: NEWS = {"players": []}
    built = dt.datetime.now(CT)
    # ---- per-game cards -------------------------------------------------------------------------------------------------------------
    teams_of = {}
    for g in games: teams_of[g["a"]] = g["gid"]; teams_of[g["b"]] = g["gid"]
    def chips(g):
        out = []
        wx = (FE.WX.get(frozenset([g["a"], g["b"]])) if FE else None) or {}
        if wx.get("risk") in ("HIGH", "MODERATE"):
            bits = [x for x in [f"wind {wx['wind']:.0f} mph" if wx.get("wind") else "", (wx.get("ptype") or "").replace("none", "") if (wx.get("pch") or 0) >= 40 else ""] if x]
            out.append(("watch", "Weather", (wx["risk"].title() + " risk" + (": " + ", ".join(bits) if bits else ""))))
        for n in (FE.CTX_G.get(frozenset([g["a"], g["b"]]), []) if FE else []):
            if n.get("k") in ("watch", "bad") and n.get("tag") not in ("Standings",): out.append((n["k"], n["tag"], n["txt"].split(". ")[0]))
        if GL.get(g["gid"], {}).get("spread") is None: pass
        return out[:3]
    def news_for(g, limit=4):
        sev = {"bad": 0, "watch": 1, "good": 2, "info": 3}
        ns = [n for n in NEWS.get("players", []) if n.get("team") in (g["a"], g["b"]) and n.get("k") in ("bad", "watch", "good") and n.get("bucket") != "TREND"]
        ns.sort(key=lambda n: (sev.get(n["k"], 9), -(n.get("sev") or 0)))
        return ns[:limit]
    def tag_short(n):
        return {"News: out": "OUT", "News: concussion protocol": "Protocol", "News: limited / questionable": "Q", "News: doubtful": "Doubtful", "News: left last game": "Left game", "News: week-to-week": "Week-to-week", "News: role up": "Role up", "News: role down": "Role down",
                "News: back / practising": "Back", "News: trade / signing": "Trade"}.get(n.get("tag"), n.get("tag", ""))
    def script_line(g):
        fav = g["a"] if g["pa"] > g["pb"] else g["b"]; marg = abs(g["pa"] - g["pb"])
        try: _pr = json.loads(g["probs"]) if isinstance(g.get("probs"), str) else g.get("probs"); _pct = f" ({max(_pr):.0f}%)" if _pr and len(_pr) == 4 else ""
        except Exception: _pct = ""
        # owner 11/5: label the likeliest script so it doesn't read as a second, different projection
        return f"Model {E(g['a'])} {g['pa']:.0f} – {E(g['b'])} {g['pb']:.0f} · {E(fav)} by {marg:.1f}" + (f" · likeliest script: {E(g['most'])}{_pct}" if g.get('most') else "")
    def stat_strip(g):
        """owner 11/10 9:39 PM ("The first section with today's game looks really good though. Just make it better"): the card opened with one
        run-on line - FanDuel's spread, the total, the model's score, the margin and the script. The three numbers are a strip; the
        script is its own sentence under it."""
        L = GL.get(g["gid"]) or {}; cells = []
        sp = L.get("spread"); home = L.get("home"); away = L.get("away")
        if sp is not None and home:   # the favorite's side of FanDuel's line ("BUF −7.5", not "NYJ +7.5")
            cells.append(("Spread", f"{E(home)} PK" if not sp else f"{E(home)} −{abs(sp):g}" if sp < 0 else f"{E(away or home)} −{abs(sp):g}" if away else f"{E(home)} +{sp:g}"))
        if L.get("total") is not None: cells.append(("Total", f"{L['total']:g}"))
        hi, lo = (g["a"], g["b"]) if g["pa"] >= g["pb"] else (g["b"], g["a"]); ph, pl_ = max(g["pa"], g["pb"]), min(g["pa"], g["pb"])
        cells.append(("Model", f"{E(hi)} {ph:.0f}–{pl_:.0f}"))
        return '<div class="tdstats">' + "".join(f"<span><i>{k}</i><b>{v}</b></span>" for k, v in cells) + "</div>"
    def script_only(g):
        try: _pr = json.loads(g["probs"]) if isinstance(g.get("probs"), str) else g.get("probs"); _pct = f" ({max(_pr):.0f}%)" if _pr and len(_pr) == 4 else ""
        except Exception: _pct = ""
        most = str(g.get("most") or "").strip()
        if most and not most.split(" ")[0].isupper(): most = most[:1].lower() + most[1:]   # "Close, low scoring" reads on; "BUF by 10+" keeps its capitals
        return f"Likeliest script: {E(most)}{_pct}" if most else ""
    def market_line(g):
        L = GL.get(g["gid"]) or {}
        if "spread" not in L and "total" not in L: return ""
        home, away = L.get("home"), L.get("away"); sp = L.get("spread")
        parts = []
        if sp is not None: parts.append(f"{E(home)} {sp:+g}" if sp else f"{E(home)} PK")
        if L.get("total") is not None: parts.append(f"O/U {L['total']:g}")
        return "FanDuel " + " · ".join(parts)
    def parlay_for(gid):
        for b in D["bp"]:
            if b.get("gid") == gid and b.get("legs"): return b
        return None
    legs_by_g = {}
    now_ms = dt.datetime.now().timestamp() * 1000
    for l in bd["legs"]:
        if l.get("tier") in ("plus", "td") and not l.get("alt"): legs_by_g.setdefault(l["g"], []).append(l)
    for gid in legs_by_g:
        legs_by_g[gid].sort(key=lambda l: -((l.get("raw_p") or l["p"]) - l["bk"]))
    # owner 11/27 10:34 PM: the Trend check page (build_trends.py -> out/trends.json); a game card links to its own streak legs
    try:
        _TRD = json.load(open(os.path.join(OUT_, "trends.json")))
        if int(_TRD.get("week") or 0) != int(W): _TRD = {}
    except Exception: _TRD = {}
    _trg = {}
    for _x in _TRD.get("legs") or []: _trg[_x.get("g")] = _trg.get(_x.get("g"), 0) + 1
    cards = []; fresh = {}
    for g in games:
        L = GL.get(g["gid"]) or {}; away, home = L.get("away", g["a"]), L.get("home", g["b"])
        ch = chips(g); ns = news_for(g); bp = parlay_for(g["gid"]); say = vg.get(g["gid"])
        chip_html = "".join(f'<span class="tdc {E(k)}"><b>{E(t)}</b>{E(x)}</span>' for k, t, x in ch)
        news_html = "".join(f'<li class="{E(n["k"])}"><b>{E(tag_short(n))}</b> <span>{E(n["player"])}</span> <small>{E(n["team"])} {E(n.get("pos", ""))}</small></li>' for n in ns)
        legs = legs_by_g.get(g["gid"], [])[:3]
        fresh[g["gid"]] = (g.get("ko"), {"at": built.isoformat(timespec="minutes"), "pa": round(float(g["pa"]), 1), "pb": round(float(g["pb"]), 1), "sp": L.get("spread"), "tot": L.get("total"),
                                         "home": L.get("home"), "looks": [{"pl": l["pl"], "tm": l.get("tm", ""), "m": l["m"], "ln": l["ln"], "o": l["o"]} for l in legs]})
        legs_html = "".join(HOME.play_card(HOME._mb(D, l, G)).replace('<article class="play ', f'<article data-k="{E(HOME.leg_key(l["pl"], l["m"], l["ln"]))}" data-gap="{((l.get("raw_p") or l["p"]) - l["bk"]):.4f}" class="play ', 1) for l in legs)
        bp_html = ""
        if bp:
            price = bp.get("price") or bp.get("odds") or ""
            bp_html = ('<div class="tdbp"><small>Best parlay for this game</small><ul>' + "".join(f'<li><b>{E(str(x[0]))}</b> <span>{E(HOME.leg_line(x[1], x[2]))}</span><em>{E(odds(x[3]))}</em></li>' for x in bp["legs"][:4]) + '</ul>'
                       + (f'<a class="more" href="/boards/#g-{E(g["gid"])}">Full card →</a>') + '</div>')
        # 11/21 the game's lead hunch (hunches.py), inside the fold: the owner's own first, then Backed, then Mixed. Cautions and info stay on /hunches/.
        hx = [h for h in HUNCH.get(g["gid"], []) if h["kind"] == "own" or h["verdict"] in ("Backed", "Mixed")]
        hx.sort(key=lambda h: (h["kind"] != "own", h["verdict"] != "Backed", -(h.get("strength") or 0)))
        hunch_html = (f'<a class="tdhunch" href="/hunches/#h-{E(g["gid"])}"><i>Hunch</i><span>{E(hx[0]["title"])}</span><b class="v{E(hx[0]["verdict"].lower().split()[0])}">{E(hx[0]["verdict"])}</b>'
                      + (f'<em>+{len(HUNCH[g["gid"]]) - 1} more</em>' if len(HUNCH[g["gid"]]) > 1 else "") + '</a>') if hx else ""
        cards.append(f'''<article class="tdgame" id="td-{E(g["gid"])}" data-gid="{E(g["gid"])}" data-ko="{g.get("ko") or ""}" data-date="{E(ct_date(g.get("ko")) or "")}" data-fin="{E(g.get("fin", ""))}">
 <header><div class="tdm"><span class="tm">{HOME.HM.hm(away)}{E(away)}</span><span class="at">@</span><span class="tm">{HOME.HM.hm(home)}{E(home)}</span></div><div class="tdk"><b>{E(g.get("kick", ""))}</b><span class="tdcd" data-ko="{g.get("ko") or ""}"></span><span class="gl"></span></div></header>
 {stat_strip(g)}
 {f'<p class="tdl">{script_only(g)}</p>' if script_only(g) else ""}
 {(f'<p class="sweepsays"><i>Sweep says</i>{E(say)}</p>') if say else ""}
 <button type="button" class="tdtog" aria-expanded="false"><span>More<em> on this game</em></span><i>▾</i></button>
 <div class="tdmore">{swb.get(g["gid"], "") if say else ""}
 {hunch_html}
 {f'<div class="tdchips">{chip_html}</div>' if chip_html else ""}
 {f'<ul class="tdnews">{news_html}</ul>' if news_html else ""}
 {f'<div class="plays tdplays">{legs_html}</div>{bp_html}' if (legs_html or bp_html) else ""}
 </div>
 <div class="tdlinks"><a class="pri" href="/boards/#g-{E(g["gid"])}">Matchup board</a><a href="/build/#g-{E(g["gid"])}">Build a slip</a>{f'<a href="/trends/?g={E(g["gid"])}">Trend check</a>' if _trg.get(g["gid"]) else ""}<a href="/dossier/{E(g["gid"])}/">Preview</a><a href="/lab/merged/?g={E(g["gid"])}">Game Desk</a><a href="/live/#lv-{E(g["gid"])}">Live</a></div>
</article>''')
    # ---- the frozen pre-kickoff copy of each card (freeze() above): this run's file if an earlier pass wrote one, else the copy the
    # site is serving (the clone's data/ folder is added to, never emptied). The Final card reads it once the game is over.
    fz_name = f"looks-w{W}.json"; prev = {}
    for _src in (os.path.join(OUT_, fz_name), os.path.join(clone, "data", fz_name) if clone else None):
        if not _src or not os.path.exists(_src): continue
        try:
            _d = json.load(open(_src))
            if int(_d.get("week") or 0) == int(W): prev = _d.get("games") or {}; break
        except Exception: pass
    FZ = freeze(prev, fresh, now_ms)
    json.dump({"week": W, "built": built.isoformat(timespec="minutes"), "games": FZ}, open(os.path.join(OUT_, fz_name), "w"), separators=(",", ":"))
    def wx_kind(g):
        return WXFX.kind((FE.WX.get(frozenset([g["a"], g["b"]])) if FE else None) or {})
    # ---- news that moved the model (whole week, newest first) -------------------------------------------------------------------------
    sev = {"bad": 0, "watch": 1, "good": 2, "info": 3}
    news = [n for n in NEWS.get("players", []) if n.get("k") in ("bad", "watch", "good") and n.get("bucket") != "TREND"]
    news.sort(key=lambda n: (sev.get(n["k"], 9), str(n.get("ts") or "")), reverse=False)
    news.sort(key=lambda n: -(n.get("sev") or 0))
    def clean_txt(n):   # the desk's text starts with the headline ("Name: Out (Hamstring). ..."); the card already shows the name and tag
        t = re.sub(r"^" + re.escape(n["player"]) + r"\s*:[^.]*\.\s*", "", n["txt"]); return t
    news_items = "".join(f'<li class="{E(n["k"])}" data-team="{E(n.get("team", ""))}" data-player="{E(n["player"])}"><span class="nt">{E(tag_short(n))}{HOME.HM.hm(n.get("team", ""))}</span><div><b>{E(n["player"])} <small>{E(n.get("team", ""))} {E(n.get("pos", ""))}</small></b><p>{E(clean_txt(n))}</p></div></li>' for n in news[:30])
    # ---- record strip -----------------------------------------------------------------------------------------------------------------
    # audit 11/10: record_block's second argument is the latest week WITH A RECEIPT, not the current week - passing W linked "Week 10 receipt"
    # (/receipts/week10/, a 404) all week until Tuesday's grading. Same rule as build_site.py: receipts built this run + the archive tab.
    def _latest_receipt():
        ws = []
        for f in os.listdir(OUT_):
            m = re.match(r"results-week(\d+)\.html$", f)
            if m: ws.append(int(m.group(1)))
        for r in vals("archive.json")[1:]:
            try:
                if len(r) >= 3 and str(r[0]).strip() and ("claude.ai/artifact/" in str(r[2]) or "/receipts/week" in str(r[2])): ws.append(int(float(r[0])))
            except Exception: pass
        return max(ws) if ws else None
    try: R = HOME.record(D); rec_html = HOME.record_block(R, _latest_receipt())
    except Exception as e: rec_html = ""; print("today: record failed", e)
    # owner 11/10 (deep dive): the record leads with the slips the site posts as its own - the Daily Sweep, then the Under of the day -
    # ahead of the every-leg totals
    try:
        import sweep as _SWM
        _lead = []
        try: _R = _SWM.record(json.load(open(os.path.join(IN_, "promos.json")))["values"])
        except Exception: _R = _SWM.record(None)
        _lead.append(f'<div><b>{_R["w"]}–{_R["l"]}</b><span>The Daily Sweep · {_SWM.fmt_u(_R["u"])} at the posted price · one house slip every game day</span></div>' if _R["n"]
                     else '<div><b>0–0</b><span>The Daily Sweep · one house slip every game day, graded in public from the first one</span></div>')
        try: _ur = json.load(open(os.path.join(OUT_, "under_day.json"))).get("record") or {}
        except Exception: _ur = {}
        if _ur.get("w") or _ur.get("l"): _lead.append(f'<div><b>{_ur["w"]}–{_ur["l"]}</b><span>Under of the day · {_ur["units"]:+.1f}u at the posted price</span></div>')
        if rec_html.startswith('<div class="rec">'): rec_html = '<div class="rec">' + "".join(_lead) + rec_html[len('<div class="rec">'):]
    except Exception as e: print("today: record lead skipped", e)
    # ---- slip key -> gid map for "your legs today" (compact: per game, the leg keys) ------------------------------------------------------
    keys_by_g = {}
    for l in bd["legs"]:
        if l.get("gl"): continue
        keys_by_g.setdefault(l["g"], []).append(HOME.leg_key(l["pl"], l["m"], l["ln"]))
    # ---- morning briefs per game day for the push function -----------------------------------------------------------------------------
    days = {}
    for g in games:
        d = ct_date(g.get("ko"))
        if d: days.setdefault(d, []).append(g)
    briefs = {}
    try: _SWP = [p_ for p_ in json.load(open(os.path.join(OUT_, "promos.json"))) if p_.get("sweep") and p_.get("status", "LIVE") == "LIVE"]
    except Exception: _SWP = []
    try:
        import build_simple as _SIMPLE; _FAVS = _SIMPLE.fav_pool(bd)
    except Exception: _SIMPLE, _FAVS = None, []
    try: _UDP = json.load(open(os.path.join(OUT_, "under_day.json"))).get("picks") or []
    except Exception: _UDP = []
    for d, gs in sorted(days.items()):
        looks = []
        for g in gs:
            for l in legs_by_g.get(g["gid"], [])[:2]: looks.append(l)
        looks.sort(key=lambda l: -((l.get("raw_p") or l["p"]) - l["bk"])); looks = looks[:3]
        tms = {t for g in gs for t in (g["a"], g["b"])}
        hot = [n for n in news if n.get("team") in tms and n.get("k") in ("bad", "good")][:2]
        label = dt.datetime.strptime(d, "%Y-%m-%d").strftime("%A")
        title = f"{label}: {len(gs)} game{'s' if len(gs) != 1 else ''} · {', '.join((GL.get(g['gid']) or {}).get('away', g['a']) + '@' + (GL.get(g['gid']) or {}).get('home', g['b']) for g in gs[:3])}{'…' if len(gs) > 3 else ''}"
        body = []
        # owner 11/5 ("always push weather updates"): the brief names every game with a kickoff-hour weather risk first
        wxl = []
        for g in gs:
            wx = (FE.WX.get(frozenset([g["a"], g["b"]])) if FE else None) or {}
            if wx.get("risk") in ("HIGH", "MODERATE"):
                bits = [x for x in [f"wind {wx['wind']:.0f}" if wx.get("wind") else "", (wx.get("ptype") or "").replace("none", "") if (wx.get("pch") or 0) >= 40 else ""] if x]
                wxl.append(f"{g['a']}-{g['b']} {wx['risk'].lower()}" + (f" ({', '.join(bits)})" if bits else ""))
        if wxl: body.append("Weather: " + "; ".join(wxl[:3]))
        # owner 11/10 (deep dive): after the weather the brief leads with what the site stands behind - the Daily Sweep when one is
        # posted for the day, else the day's favorites, then the Under of the day. The plus-money looks (21-72 in Week 9) stay on the
        # page and no longer lead the push.
        _gids = {g["gid"] for g in gs}
        _swp = next((p_ for p_ in _SWP if p_.get("first_ko") and ct_date(p_["first_ko"]) == d), None)
        if _swp:
            try: _pr = f" ({odds(float(_swp['fd']))})"
            except Exception: _pr = ""
            body.append(f"{_swp.get('title') or 'Daily Sweep'}{_pr}")
        else:
            _fv = _SIMPLE.pick_favs([l for l in _FAVS if l["g"] in _gids]) if _SIMPLE else []
            if _fv: body.append("Favorites: " + " · ".join(f"{l['pl']} {HOME.leg_line(l['m'], l['ln'])} ({odds(l['o'])})" for l in _fv))
        _ud = next((e_ for e_ in _UDP if e_.get("date") == d), None)
        if _ud: body.append(f"Under of the day: {_ud['pl']} under {_ud['ln']:g} {UD.STAT[_ud['m']][1]} ({odds(_ud['o'])})")
        if hot: body.append("; ".join(f"{n['player']} {tag_short(n).lower()}" for n in hot))
        briefs[d] = {"title": title[:90], "body": ("; ".join(body) or "Today's games, looks and news in one place.")[:300], "url": "/today/?source=push", "games": [g["gid"] for g in gs]}
    today_json = {"week": W, "built": built.isoformat(), "briefs": briefs, "days": {d: [g["gid"] for g in gs] for d, gs in days.items()}}
    json.dump(today_json, open(os.path.join(OUT_, "today.json"), "w"))
    # ---- Trade desk (build_targets.py -> out/targets.json; 11/5): buy-low / sell-high, strongest on Tuesday when the week is in the books ----
    tgt_html = ""
    try:
        TG = json.load(open(os.path.join(OUT_, "targets.json")))
        from plydata import slugify as slug
        def tg_card(r, kind):
            sn = f"{r['snap']*100:.0f}% snaps" if r.get("snap") else ""
            rk = f"{E(r['pos'])}{r['mrank']}" + (f" <small>(market {E(r['pos'])}{r['krank']})</small>" if r.get("krank") else "")
            return (f'<li class="tg {kind}"><div class="tgh"><a href="/player/{slug(r["n"])}/"><b>{E(r["n"])}</b></a> <span class="tgm">{E(r["pos"])} · {E(r["tm"])}</span><span class="tgr">{rk}</span></div>'
                    f'<div class="tgn"><span><b>{r["S"]}</b> season</span><span><b>{r["l3"]}</b> last 3</span>{("<span>" + sn + "</span>") if sn else ""}</div><p>{E(r["why"])}</p></li>')
        if TG.get("buy") or TG.get("sell"):
            tgt_html = (f'<section class="sec" id="tdtrade"><h2 class="t">Trade desk <small class="tsub">buy low, sell high · snaps and schedule, not the box score</small></h2>'
                        f'<div class="tgcols"><div><h3 class="tgt buy">Buy low</h3><ul class="tgl">{"".join(tg_card(r, "buy") for r in TG["buy"][:6])}</ul></div>'
                        f'<div><h3 class="tgt sell">Sell high</h3><ul class="tgl">{"".join(tg_card(r, "sell") for r in TG["sell"][:6])}</ul></div></div>'
                        f'<p class="none" style="margin-top:8px;font-size:12.5px">Values for the whole offer: <a href="/trade/" style="color:var(--ink)">Trade calculator</a>. Market ranks come from FantasyCalc when the sheet has them.</p></section>')
    except FileNotFoundError: pass
    except Exception as _e: print("note: trade desk skipped:", _e)
    # ---- the Daily Sweep (owner 11/10): the house slip of the game day, first thing on the page (home.py sweep_block; sweep.py has the rules) ----
    try: sweep_html, _sw_on = HOME.sweep_block(IN_, OUT_, games)
    except Exception as _e: print("note: Daily Sweep block skipped:", _e); sweep_html = ""
    try: winners_html = HOME.winners_block(IN_)      # owner 11/13: a winning-promo section on the home page
    except Exception as _e: print("note: winners block skipped:", _e); winners_html = ""
    # owner 11/16: busted promos are NOT listed on this page (he tried a "Lost" fold here for an hour and took it off) - they leave it,
    # and the week's misses are on /receipts/ (build_site.py, home.lost_block).
    try:   # alpha plan step 5 (11/16): the three most-upvoted open slips, right under the promos
        # below today's game, never above it (owner's 11/11 rule for this page: the head, then the game; only the day's own callouts between)
        import social as _SOC; social_strip = _SOC.strip_html(W)
    except Exception as _e: print("note: Social strip skipped:", _e); social_strip = ""
    # owner 11/27 10:34 PM: one line to the Trend check page (build_trends.py -> out/trends.json), under today's games
    trend_door = ("<style>" + _TRD.get("door_css", "") + "</style>" + _TRD["door"]) if _TRD.get("door") else ""
    # ---- page ------------------------------------------------------------------------------------------------------------------------
    stamp = built.strftime("%a %-m/%-d %-I:%M %p")
    try:
        import how_stats as _HOWS; _PLUS_TXT = _HOWS.plus_phrase(IN)   # 11/17: counted from the graded legs (it quoted Weeks 6-8)
    except Exception: _PLUS_TXT = "Weeks 6–10: 40% hit against a 30% price, +30% at a unit each (175 legs)"
    body = f'''<title>Today · BetSweep</title>
<meta name="description" content="Today on BetSweep: what kicks off, the model's plus-money looks for today's games, the news that moved the numbers, your slips and your Sleeper team.">
<style>{TODAY_CSS}</style>
<script data-early>/* owner 11/10, Short view: a visitor who chose it opens there. Only the bare home address (or the installed app's) moves - a link with a hash or any other query stays on this page. ('simple' is the same choice, stored before the view was renamed.) */
try{{ var bsv = localStorage.getItem('bs_view'); if((bsv === 'short' || bsv === 'simple') && location.pathname === '/' && !location.hash && (!location.search || location.search === '?source=app')) location.replace('/short/'); }}catch(e){{}}</script>
<section class="tdhead"><div class="tdh1"><h1 id="tdtitle">Today</h1><span class="tdsub" id="tdsub">Week {W}</span></div><div class="tdact"><a class="tdshare" id="tdsimple" href="/short/" title="The short version: picks first, reading optional" onclick="try{{localStorage.setItem('bs_view','short')}}catch(e){{}}">Short view</a><a class="tdlive" href="/live/">Live</a></div></section>
<section class="tdhero" id="tdhero" aria-label="The next game" hidden></section>
{sweep_html}
{winners_html}
<!--bs:promos-->
{under_html}
{stale_html}
<section class="sec" id="tdlooks" hidden><h2 class="t">Today's looks <small class="tsub">plus-money edges</small></h2><div class="plays" id="tdlooksgrid"></div><p class="none" style="margin-top:8px;font-size:12.5px">The model's chance vs what FanDuel's price needs, +150 or longer, 5+ points of edge. {_PLUS_TXT}. Tap + Slip to collect them, then open the betslip.</p></section>
<section class="sec tdday" id="tdday"><div class="tdgames" id="tdgames">{"".join(cards)}</div><p class="none" id="tdnone" hidden></p>
 <p class="tdall"><a href="/boards/">All {len(games)} games this week</a></p></section>
{trend_door}
{social_strip}
<section class="sec" id="tdyou" hidden><h2 class="t">You today</h2><div class="tdyou" id="tdyoubox"></div></section>
<section class="sec" id="tdnewsS"><div class="sech"><h2 class="t">News desk</h2><a class="seeall" href="/news/">All {len(news)} notes</a></div>{("<ul class='tdnewsl' id='tdnewsl' data-cap='3'>" + news_items + "</ul>") if news_items else "<p class='none'>Quiet so far. The news desk refreshes with every rebuild.</p>"}</section>
<section class="sec" id="record"><div class="sech"><h2 class="t">Track record</h2><a class="seeall" href="/receipts/">Every week</a></div>{rec_html}<p class="none" style="margin-top:8px;font-size:12.5px"><a href="/how/" style="color:var(--ink)">How BetSweep picks</a></p></section>
<div class="hsbar" id="hsbar" data-week="{E(str(W))}"><b></b><a href="/build/">Open betslip</a></div>
<script>window.__TD = {json.dumps({"week": W, "built": built.isoformat(), "games": [{"gid": g["gid"], "a": g["a"], "b": g["b"], "ko": g.get("ko"), "kick": g.get("kick", ""), "fin": g.get("fin", ""), "home": (GL.get(g["gid"]) or {}).get("home", g["b"]), "away": (GL.get(g["gid"]) or {}).get("away", g["a"]),
                                                                                         "pa": round(float(g["pa"]), 1), "pb": round(float(g["pb"]), 1), "sp": (GL.get(g["gid"]) or {}).get("spread"), "tot": (GL.get(g["gid"]) or {}).get("total"),
                                                                                         "wx": wx_kind(g), "fz": FZ.get(g["gid"])} for g in games],
                                                                              "col": {t: HOME.HM.COL[t][0] for g in games for t in (g["a"], g["b"]) if t in HOME.HM.COL}, "teams": [[c, n] for c, n in __import__("account").TEAMS32], "keys": keys_by_g, "news": [{"player": n["player"], "team": n.get("team", ""), "k": n["k"], "tag": tag_short(n)} for n in news]}, separators=(",", ":"))};</script>
{TODAY_JS}
<script>{LIVE.LIVE_JS}</script>
{HOME.strip_js(games)}
{HOME.home_js(games)}
{HOME.HOME_SLIP_JS}
'''
    if swb and any(vg.get(g["gid"]) and swb.get(g["gid"]) for g in games): body += SWC.get("js", "") + "\n"   # the share-card style + script, once (same one the boards carry)
    open(os.path.join(OUT_, "today.html"), "w").write(body)
    # owner 11/10 9:39 PM ("compact the home page ... some things can move to different or new pages"): the full news list, the trade
    # desk and the week's game list are no longer on "/". build_site.py wraps these fragments as /news/ and /targets/ (the slate page
    # is built from home.py's cards).
    def news_li(n): return f'<li class="{E(n["k"])}" data-team="{E(n.get("team", ""))}" data-player="{E(n["player"])}"><span class="nt">{E(tag_short(n))}{HOME.HM.hm(n.get("team", ""))}</span><div><b>{E(n["player"])} <small>{E(n.get("team", ""))} {E(n.get("pos", ""))}</small></b><p>{E(clean_txt(n))}</p></div></li>'
    groups = [("Out or doubtful", [n for n in news if n["k"] == "bad"]), ("Limited, questionable or a smaller role", [n for n in news if n["k"] == "watch"]), ("Back, or a bigger role", [n for n in news if n["k"] == "good"])]
    # 11/17 (page pass): the same three groups as data, so /news/ can show one at a time under a tab (label = the tab's word)
    _labels = {"bad": "Out", "watch": "Limited", "good": "Back"}
    news_groups = [{"k": k, "label": _labels[k], "title": t, "n": len(ns), "html": '<ul class="tdnewsl">' + "".join(news_li(n) for n in ns) + '</ul>'}
                   for k, (t, ns) in zip(("bad", "watch", "good"), groups) if ns]
    json.dump({"week": W, "stamp": stamp, "n": len(news), "css": TODAY_CSS, "groups": news_groups,
               "news": "".join(f'<h2 class="t nwh">{E(t)} <small class="tsub">{len(ns)}</small></h2><ul class="tdnewsl">{"".join(news_li(n) for n in ns)}</ul>' for t, ns in groups if ns),
               "stale": stale_html, "targets": tgt_html, "teams": sorted({n.get("team", "") for n in news if n.get("team")})},
              open(os.path.join(OUT_, "today_parts.json"), "w"))
    print(f"wrote out/today.html + today.json: {len(games)} games over {len(days)} days, {sum(len(v) for v in legs_by_g.values())} plus/TD legs, {len(news)} news notes, voice lines {len(vg)}")
    return body

TODAY_CSS = r"""
/* UX audit 11/4: /today/ follows the same theme rule as the boards, builder, live and player pages (dark-first, cream when the phone
   prefers light or the menu's Theme switch says Light). Values mirror template.html; --bad is new here (home.py hard-codes #e07070). */
:root{--bad:#ef8a7e;--warn:#f2b35a;color-scheme:dark}
@media (prefers-color-scheme: light){ :root:not([data-theme="dark"]){--bg:#efe9da;--card:#f7f3e8;--chalk:#e4ddcb;--ink:#141a24;--mute:#5d6676;--line:#d3cbb8;--good:#1f7a4d;--bad:#b3372b;--warn:#a86400;--redtxt:#b8261d;color-scheme:light} }
:root[data-theme="light"]{--bg:#efe9da;--card:#f7f3e8;--chalk:#e4ddcb;--ink:#141a24;--mute:#5d6676;--line:#d3cbb8;--good:#1f7a4d;--bad:#b3372b;--warn:#a86400;--redtxt:#b8261d;color-scheme:light}
.play .nums .edge.neg,.play .hist.bad,.promo .ph .st.loss{color:var(--bad)}
.tdhead{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;max-width:1360px;margin:14px auto 0;padding:0 16px}
.tdh1 h1{margin:0;font-family:var(--brand);font-style:italic;font-weight:800;font-size:40px;letter-spacing:-.02em;line-height:1} .tdsub{display:block;margin-top:6px;color:var(--mute);font-family:var(--body);font-weight:500;font-size:14px;letter-spacing:0;text-transform:none;line-height:1.4;max-width:34ch}
.tdact{display:flex;gap:8px;align-items:center}
@media (max-width:560px){ .tdhead{flex-direction:column;align-items:stretch} .tdact{flex-wrap:wrap} } .tdshare,.tdlive{font:inherit;font-family:var(--display);font-weight:700;font-size:12.5px;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:7px 14px;cursor:pointer;text-decoration:none} .tdlive{background:var(--red);border-color:var(--red);color:#fff}
.tdday .tdgames{display:grid;gap:12px}
.tdhunch{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:4px 10px;align-items:center;margin:10px 0 0;padding:10px 12px;border:1px solid var(--line);border-radius:10px;text-decoration:none;color:var(--ink);font-size:14px;line-height:1.3}
.tdhunch i{font-style:normal;font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--red)} .tdhunch span{font-weight:600;overflow-wrap:anywhere}
.tdhunch b{font-family:var(--display);font-weight:700;font-size:12px;border:1px solid var(--line);border-radius:999px;padding:2px 9px;white-space:nowrap} .tdhunch b.vbacked{background:var(--good);border-color:var(--good);color:#fff}
.tdhunch em{grid-column:2 / -1;font-style:normal;font-size:12.5px;color:var(--mute)}
/* 11/20: a Sunday slate put 11 cards (4.6 phone screens) on Today. Past five games the first three show and one button opens the rest. */
.tdday:not(.all) .tdgame.tdx{display:none} .tdallb{display:flex;align-items:center;justify-content:center;width:100%;min-height:46px;margin-top:12px;font:inherit;font-family:var(--display);font-weight:700;font-size:14px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink);background:transparent;border:1.5px solid var(--line);border-radius:10px;cursor:pointer}
@media (min-width:900px){ .tdday:not(.all) .tdgame.tdx{display:flex} .tdallb{display:none} }
.tdgame{display:none;flex-direction:column;gap:10px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 14px 12px} .tdgame.show{display:flex} .tdgame.post{opacity:.72}
.tdgame header{display:flex;align-items:center;justify-content:space-between;gap:10px} .tdm{display:flex;align-items:baseline;gap:8px;font-family:var(--brand);font-style:italic;font-weight:800;font-size:30px;letter-spacing:-.01em;line-height:1} .tdm .at{font-size:16px;color:var(--mute);font-weight:600}
.tdk{text-align:right} .tdk b{display:block;font-family:var(--display);font-weight:700;font-size:15px;color:var(--mute)} .tdk .gl{display:block;font-family:var(--display);font-weight:800;font-size:17px;color:var(--ink)} .tdk .gl i{font-style:normal;color:var(--red);font-size:11px;letter-spacing:.14em;margin-right:6px}
.tdl{margin:0;color:var(--mute);font-size:13.5px;line-height:1.45}
.sweepsays{margin:0;position:relative;background:var(--chalk);border-radius:10px;padding:10px 12px 10px 14px;font-size:15px;line-height:1.4;font-weight:500} .sweepsays i{display:block;font-style:normal;font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--redtxt,var(--red));margin-bottom:3px} .sweepsays::before{content:"";position:absolute;left:0;top:10px;bottom:10px;width:3px;border-radius:3px;background:var(--red)}
.tdchips{display:flex;flex-wrap:wrap;gap:6px} .tdc{display:inline-flex;gap:6px;align-items:baseline;border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:12.5px;color:var(--ink)} .tdc b{font-family:var(--display);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--mute)} .tdc.watch{border-color:#b7791f} .tdc.watch b{color:#b7791f} .tdc.bad{border-color:var(--bad)} .tdc.bad b{color:var(--bad)}
.tdnews{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13.5px} .tdnews li b{font-family:var(--display);font-size:11px;letter-spacing:.1em;text-transform:uppercase;margin-right:4px} .tdnews li.bad b{color:var(--bad)} .tdnews li.watch b{color:#b7791f} .tdnews li.good b{color:var(--good)} .tdnews small{color:var(--mute)}
.tdplays.plays{grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
.tdbp{background:var(--chalk);border-radius:10px;padding:10px 12px} .tdbp small{font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--red)} .tdbp ul{list-style:none;margin:6px 0 4px;padding:0} .tdbp li{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:8px;align-items:baseline;padding:4px 0;font-size:14px} .tdbp li b{font-family:var(--display);font-weight:700;font-size:16px} .tdbp li span{color:var(--mute)} .tdbp li em{font-style:normal;font-family:var(--display);font-weight:800;color:var(--ink)} .tdbp .more{color:var(--mute);text-decoration:none;font-size:12.5px;font-weight:600}
.tdtog{display:none;font:inherit;font-family:var(--display);font-weight:700;font-size:13.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink);background:transparent;border:1.5px solid var(--line);border-radius:8px;min-height:38px;padding:8px 12px;cursor:pointer;text-align:left} .tdtog i{font-style:normal;float:right} .tdgame.compact .tdtog{display:block} .tdgame.compact .tdmore{display:none} .tdgame.compact.open .tdmore{display:block} .tdgame.compact.open .tdtog i{transform:rotate(180deg);display:inline-block} .tdmore{display:flex;flex-direction:column;gap:10px}
.tdlinks{display:flex;flex-wrap:wrap;gap:6px;margin-top:2px} .tdlinks a{text-decoration:none;color:var(--ink);font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line);border-radius:6px;padding:5px 10px} .tdlinks a:hover{border-color:var(--red)}
@media (pointer:coarse){ .tdlinks{gap:8px} .tdlinks a{padding:10px 12px} }
.tdyou{display:grid;gap:8px} .tdyou .yrow{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:14px} .tdyou .yrow b{font-family:var(--display);font-weight:700;font-size:16px} .tdyou .yrow small{color:var(--mute);display:block;font-size:12.5px} .tdyou .yk{font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--red);min-width:54px} .tdyou .yrow a{text-decoration:none;color:var(--ink);font-weight:600;font-size:13px;border:1px solid var(--line);border-radius:6px;padding:5px 9px;white-space:nowrap} .tdyou .yrow.bad .yk{color:var(--bad)} .tdyou .yrow.good .yk{color:var(--good)} .tdyou .yrow.watch .yk{color:#b7791f}
.tgcols{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))} .tgt{margin:0 0 8px;font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.1em;text-transform:uppercase} .tgt.buy{color:var(--good)} .tgt.sell{color:var(--redtxt,var(--red))}
.tgl{list-style:none;margin:0;padding:0;display:grid;gap:8px} .tg{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;border-left-width:4px} .tg.buy{border-left-color:var(--good)} .tg.sell{border-left-color:var(--red)}
.tgh{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap} .tgh a{color:var(--ink);text-decoration:none} .tgh a:hover{text-decoration:underline} .tgm{color:var(--mute);font-size:12.5px} .tgr{margin-left:auto;font-family:var(--display);font-weight:700;font-size:13px} .tgr small{font-weight:500;color:var(--mute)}
.tgn{display:flex;gap:14px;margin:6px 0 4px;font-size:12.5px;color:var(--mute)} .tgn b{color:var(--ink);font-family:var(--display);font-size:15px;font-weight:700;margin-right:3px} .tg p{margin:0;font-size:13.5px;line-height:1.45}
.tdnewsl{list-style:none;margin:0;padding:0;display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))} .tdnewsl li[hidden]{display:none} .tdnewsmore{display:block;width:100%;margin:10px 0 0;min-height:44px;font:inherit;font-weight:700;font-size:14px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);cursor:pointer} .tdnewsl li{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px} .tdnewsl li .nt{font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.12em;text-transform:uppercase;padding-top:3px;min-width:52px} .tdnewsl li .nt{display:flex;flex-direction:column;align-items:flex-start;gap:7px} .tdnewsl li .nt i.hm{height:26px;margin:0;vertical-align:0} .tdnewsl li.bad .nt{color:var(--bad)} .tdnewsl li.watch .nt{color:#b7791f} .tdnewsl li.good .nt{color:var(--good)} .tdnewsl li b{font-family:var(--display);font-weight:700;font-size:16px} .tdnewsl li b small{color:var(--mute);font-size:12px;font-weight:600;margin-left:4px} .tdnewsl li p{margin:2px 0 0;color:var(--mute);font-size:13px;line-height:1.45} .tdnewsl li.mine{border-color:var(--red)}
.tdweek{display:grid;gap:8px} .tdwd{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 12px;align-items:baseline;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px} .tdwd b{font-family:var(--display);font-weight:800;font-size:15px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)} .tdwd .g{display:flex;flex-wrap:wrap;gap:6px 12px;font-size:13.5px} .tdwd .g a{text-decoration:none;color:var(--ink);font-weight:600} .tdwd .g a small{color:var(--mute);font-weight:500;margin-left:4px} .tdwd .g a.post{opacity:.6}
.tdempty{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 16px;font-size:15px;line-height:1.5} .tdempty b{font-family:var(--display);font-size:22px;display:block;margin-bottom:4px}
/* owner 11/5: Listen - the brief read aloud by the phone's own voice */
.tdlisten{font:inherit;font-family:var(--display);font-weight:700;font-size:12.5px;letter-spacing:.05em;text-transform:uppercase;display:inline-flex;align-items:center;gap:6px;min-height:36px;padding:0 14px;border-radius:8px;border:1.5px solid var(--line);background:transparent;color:var(--ink);cursor:pointer} .tdlisten.on{border-color:var(--red);color:var(--red)}
@media (max-width:560px){.tdm{font-size:26px} .tdh1 h1{font-size:34px}}
/* 11/10 evening (owner: "The first section with today's game looks really good though. Just make it better"; "compact the home page") */
.tdstats{display:grid;grid-template-columns:repeat(auto-fit,minmax(0,1fr));gap:0;background:var(--chalk);border-radius:10px;overflow:hidden} .tdstats span{display:flex;flex-direction:column;gap:1px;padding:8px 12px;min-width:0} .tdstats span + span{border-left:1px solid var(--line)}
.tdstats i{font-style:normal;font-family:var(--body);font-weight:500;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)} .tdstats b{font-family:var(--display);font-weight:700;font-size:19px;line-height:1.1;font-variant-numeric:tabular-nums;white-space:nowrap}
.tdk .tdcd{display:block;font-family:var(--body);font-weight:500;font-size:12px;color:var(--mute);margin-top:1px} .tdk .tdcd:empty{display:none}
.tdlinks a.pri{background:var(--ink);border-color:var(--ink);color:var(--bg);flex:1 1 100%;text-align:center;font-size:13.5px;padding:10px 12px;border-radius:8px}
/* a folded card (three or more games on the day): head, the three numbers, the take, then two buttons side by side */
.tdgame.compact:not(.open){flex-direction:row;flex-wrap:wrap} .tdgame.compact:not(.open) > *{flex:1 1 100%;min-width:0} .tdgame.compact:not(.open) > .tdl{display:none}
.tdgame.compact:not(.open) > .tdlinks,.tdgame.compact:not(.open) > .tdtog{flex:1 1 calc(50% - 5px);margin:0} .tdgame.compact:not(.open) .tdlinks a:not(.pri){display:none} .tdgame.compact:not(.open) .tdlinks a.pri{padding:0 8px;min-height:40px;display:flex;align-items:center;justify-content:center}
.tdgame.compact .tdtog{order:5;min-height:40px;padding:0 12px;display:flex;align-items:center;justify-content:space-between;gap:8px} .tdgame.compact .tdlinks{order:4} .tdgame.compact.open .tdtog{order:0} .tdtog em{font-style:normal}
@media (max-width:480px){ .tdgame.compact:not(.open) .tdtog em{display:none} }
.tdall{display:flex;gap:8px;margin:10px 0 0} .tdall a{flex:1;text-align:center;text-decoration:none;color:var(--ink);font-family:var(--display);font-weight:700;font-size:13.5px;letter-spacing:.05em;text-transform:uppercase;border:1.5px solid var(--line);border-radius:8px;padding:10px 8px;background:var(--card)} .tdall a:hover{border-color:var(--red)}
.nwh{margin-top:22px}
/* 11/28: the page opens with the next game - or the one in play (owner 11/27 8:31 PM, "I love all 8": Today opens with the next game) */
.tdhero{max-width:1360px;margin:12px auto 0;padding:0 16px} .tdhero[hidden]{display:none}
.thl{position:relative;display:grid;gap:7px;padding:11px 14px 12px;border:1px solid var(--line);border-radius:16px;overflow:hidden;text-decoration:none;color:var(--ink);
 background:linear-gradient(90deg,color-mix(in srgb,var(--wa,transparent) 40%,transparent),transparent 42%,transparent 58%,color-mix(in srgb,var(--wb,transparent) 40%,transparent)),var(--card)}
.thk{display:flex;justify-content:space-between;align-items:center;gap:8px;font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--mute)}
.thk .lv{color:var(--redtxt,var(--red))} .thk .lv::before{content:"";display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--red);margin-right:6px;vertical-align:1px;animation:lsp 1.4s ease-in-out infinite}
.thm{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:8px}
.tht{display:flex;align-items:center;gap:8px;font-family:var(--brand);font-style:italic;font-weight:800;font-size:30px;letter-spacing:-.01em;line-height:1;min-width:0} .tht.r{justify-content:flex-end}
.tht i.hm{height:46px;margin:0;vertical-align:0}
.thc{text-align:center;font-family:var(--display)} .thc b{display:block;font-weight:800;font-size:30px;line-height:1;font-variant-numeric:tabular-nums;white-space:nowrap} .thc b i{font-style:normal;color:var(--red);margin:0 6px}
.thc small{display:block;margin-top:4px;font-family:var(--body);font-weight:500;font-size:12px;color:var(--mute);white-space:nowrap}
/* owner 11/28 1:21 AM ("make the countdown time a little more subtle"): before kickoff the two teams lead and the countdown sits back -
   smaller, lighter, in the quiet colour. A live score keeps the full weight. */
.thl[data-st="pre"] .thc b{font-weight:600;font-size:19px;color:var(--mute);letter-spacing:.01em}
.thf{text-align:center;font-size:12.5px;line-height:1.35;color:var(--mute)} .thf b{color:var(--ink);font-weight:600}
.thx{display:flex;gap:6px;overflow-x:auto;padding:8px 0 0;scrollbar-width:none} .thx::-webkit-scrollbar{display:none}
.thx span{flex:none;align-self:center;font-size:12px;color:var(--mute);margin-right:2px}
.thx a{flex:none;display:inline-flex;align-items:center;gap:5px;min-height:32px;padding:0 10px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink);text-decoration:none;font-family:var(--display);font-weight:700;font-size:13px}
.thx a i.hm{height:16px;margin:0;vertical-align:0}
/* favorite team: its game under the opener, the choice as a chip (a native list sits over it), its card marked */
.thx a.thmine{border-color:var(--ink)} .thx a.thmine small{font-family:var(--body);font-weight:500;font-size:11.5px;color:var(--mute);margin-left:3px}
.thfav{position:relative;flex:none;display:inline-flex;align-items:center;min-height:38px;margin-left:auto;padding:0 12px;border:1px dashed var(--line);border-radius:999px;color:var(--mute);font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.03em;cursor:pointer}
.thfav span{display:inline-flex;align-items:center;gap:5px;margin:0;font-size:inherit;color:inherit} .thfav span i.hm{height:16px;margin:0;vertical-align:0} .thfav span i:not(.hm){font-style:normal;font-size:10px;color:var(--mute)}
.thfav.set{border-style:solid;background:var(--card);color:var(--ink)}
.thfav select{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;font-size:16px;cursor:pointer}
.thfav:focus-within{outline:2px solid var(--red);outline-offset:2px}
.thx em.thoff{flex:none;align-self:center;font-style:normal;font-size:12px;color:var(--mute);margin-right:2px}
.tdgame.fav{box-shadow:inset 4px 0 0 var(--favc,var(--red))}
.tdfavt{display:inline-block;margin:0 0 3px;padding:1px 7px;border:1px solid var(--line);border-radius:999px;font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute)}
@media (max-width:420px){ .tht{font-size:26px;gap:6px} .tht i.hm{height:40px} .thc b{font-size:26px} .thl[data-st="pre"] .thc b{font-size:17px} }
@media (prefers-reduced-motion: reduce){ .thk .lv::before{animation:none} }
/* a team logo in front of each side of a game card */
.tdm .tm{display:inline-flex;align-items:center;gap:6px} .tdm .tm i.hm{height:28px;margin:0;vertical-align:0} .tdm{align-items:center}
/* 11/28: a game that is over turns into its Final card (owner 11/27 8:31 PM: Final cards on Today) - the score, how the model's call
   did against it, and the looks it showed before kickoff, graded from the box score when the reader asks */
.tdgame.fin .tdstats,.tdgame.fin > .tdl,.tdgame.fin > .sweepsays,.tdgame.fin > .tdtog,.tdgame.fin > .tdmore,.tdgame.fin .tdcd{display:none !important}
.tdgame.fin.compact:not(.open) > .tdlinks{flex:1 1 100%}
.tdfin{display:grid;gap:10px;min-width:0}
.fsc{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:8px;background:var(--chalk);border-radius:12px;padding:10px 12px}
.fsc .ft{display:flex;align-items:center;gap:8px;font-family:var(--display);font-weight:700;font-size:19px;color:var(--mute);min-width:0} .fsc .ft.r{justify-content:flex-end}
.fsc .ft i.hm{height:30px;margin:0;vertical-align:0} .fsc .ft em{font-style:normal;font-weight:800;font-size:34px;line-height:1;font-variant-numeric:tabular-nums}
.fsc .ft.w{color:var(--ink)} .fsc .fl{font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--mute)}
.fcall,.flk{list-style:none;margin:0;padding:0;display:grid;gap:7px}
.fcall li{display:grid;grid-template-columns:16px 56px minmax(0,1fr);gap:8px;align-items:baseline;font-size:13.5px;line-height:1.35}
.fcall li > i,.flk li > i{font-style:normal;font-weight:700;text-align:center;color:var(--mute)} .fcall li.hit > i,.flk li.hit > i{color:var(--good)} .fcall li.miss > i,.flk li.miss > i{color:var(--bad)}
.fcall li > span{font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute)}
.fcall li b{font-weight:600} .fcall li small{display:block;color:var(--mute);font-size:12.5px}
.fnote{margin:0;font-size:12px;line-height:1.4;color:var(--mute)} .fnote a{color:var(--ink)}
.flt{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;min-height:40px;padding:0 12px;font:inherit;font-family:var(--display);font-weight:700;font-size:13.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink);background:transparent;border:1.5px solid var(--line);border-radius:8px;cursor:pointer}
.flt small{font-family:var(--body);font-weight:500;font-size:12px;letter-spacing:0;text-transform:none;color:var(--mute)}
.flk[hidden]{display:none} .flk li{display:grid;grid-template-columns:16px minmax(0,1fr) auto;gap:8px;align-items:baseline;font-size:13.5px;line-height:1.35}
.flk li b{font-weight:600} .flk li small{color:var(--mute);font-size:12.5px;margin-left:4px} .flk li em{font-style:normal;font-family:var(--display);font-weight:700;font-size:15px;font-variant-numeric:tabular-nums}
/* 11/27 late: a game that has kicked off no longer offers its parlay or a way into the builder (its looks leave by home.py's kickoff rule) */
.tdgame.ko .tdbp,.tdgame.ko .tdlinks a[href^="/build/"],.tdgame.ko .tdlinks a[href^="/trends/"]{display:none}
@media (max-width:560px){ .tdnews{display:grid;grid-template-columns:1fr 1fr;gap:5px 12px} .tdnews li{min-width:0;line-height:1.3} }
"""

TODAY_JS = r"""<script>
(function(){ // Listen (owner 11/5): the day's brief through speechSynthesis - no server, works in the car
  var b = document.getElementById('tdlisten'); if (!b || !('speechSynthesis' in window)) return;
  function text(){ var parts = []; var h = document.getElementById('tdtitle'); if (h) parts.push(h.textContent.trim() + '.');
    document.querySelectorAll('.tdgame.show').forEach(function(g){ var m = g.querySelector('.tdm'); var say = g.querySelector('.sweepsays'); var l = g.querySelector('.tdl');
      if (m) parts.push(m.textContent.replace(/\s+/g, ' ').replace('@', ' at ') + '.'); if (l) parts.push(l.textContent.replace(/\s+/g, ' ') + '.'); if (say) parts.push(say.textContent.replace(/^Sweep says/i, 'Sweep says:').replace(/\s+/g, ' ') + '.'); });
    var looks = document.querySelectorAll('#tdlooksgrid .play'); if (looks.length){ parts.push("Today's looks."); looks.forEach(function(p, i){ if (i > 3) return; var who = p.querySelector('.who b'), what = p.querySelector('.what .wl') || p.querySelector('.what'); if (who && what) parts.push(who.textContent + ', ' + what.textContent.replace(/\s+/g, ' ') + '.'); }); }
    return parts.join(' '); }
  b.hidden = false; var on = false;
  b.addEventListener('click', function(){ if (on){ speechSynthesis.cancel(); on = false; b.classList.remove('on'); b.textContent = '▶ Listen'; return; }
    var u = new SpeechSynthesisUtterance(text()); u.rate = 1.02; u.onend = function(){ on = false; b.classList.remove('on'); b.textContent = '▶ Listen'; };
    speechSynthesis.cancel(); speechSynthesis.speak(u); on = true; b.classList.add('on'); b.textContent = '■ Stop'; });
})();
(function(){
  var T = window.__TD || {games: [], keys: {}, news: []}; var TZ = 'America/Chicago';
  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
  function ymd(ms){ try{ var p = new Intl.DateTimeFormat('en-CA', {timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit'}).formatToParts(new Date(ms)); var o = {}; p.forEach(function(x){ o[x.type] = x.value; }); return o.year + '-' + o.month + '-' + o.day; }catch(e){ return new Date(ms).toISOString().slice(0,10); } }
  function dayName(ymdStr){ var d = new Date(ymdStr + 'T12:00:00Z'); return d.toLocaleDateString('en-US', {weekday: 'long', timeZone: 'UTC'}); }
  function shortDay(ymdStr){ var d = new Date(ymdStr + 'T12:00:00Z'); return d.toLocaleDateString('en-US', {weekday: 'short', month: 'numeric', day: 'numeric', timeZone: 'UTC'}); }
  var now = Date.now(), today = ymd(now);
  var byDay = {}; T.games.forEach(function(g){ if(!g.ko) return; var d = ymd(g.ko); (byDay[d] = byDay[d] || []).push(g); });
  var dates = Object.keys(byDay).sort();
  var pick = dates.indexOf(today) >= 0 ? today : (dates.filter(function(d){ return d > today; })[0] || null);
  // a game day stays "today" until ~4 am the next morning so Monday night's game is still the card at 11 pm
  var late = dates.filter(function(d){ return d < today; }).slice(-1)[0];
  if(pick !== today && late){ var lastKo = Math.max.apply(null, byDay[late].map(function(g){ return g.ko; })); if(now - lastKo < 5 * 3600e3) pick = late; }
  var title = document.getElementById('tdtitle'), sub = document.getElementById('tdsub'), none = document.getElementById('tdnone');
  var shown = pick ? byDay[pick] : [];
  if(pick === today){ title.textContent = 'Today'; sub.textContent = 'Week ' + T.week + ' · ' + shortDay(pick) + ' · ' + shown.length + (shown.length === 1 ? ' game' : ' games'); }
  else if(pick){ title.textContent = 'Next up: ' + dayName(pick); sub.textContent = 'Week ' + T.week + ' · ' + shortDay(pick) + ' · ' + shown.length + (shown.length === 1 ? ' game' : ' games') + ' · nothing kicks off today'; }
  else { title.textContent = 'Week ' + T.week + ' is in the books'; sub.textContent = 'Graded on Tuesday · next week\'s board posts the same day'; }   // 11/17: said "Thursday morning" while the short page said Tuesday; the roll is Tuesday
  var showG = {}; shown.forEach(function(g){ showG[g.gid] = 1; });
  document.querySelectorAll('.tdgame').forEach(function(el){ el.classList.toggle('show', !!showG[el.getAttribute('data-gid')]); });
  // 11/10 evening: on a day with three or more games every card folds to its head, the three numbers and the take ("More on this
  // game" opens the share button, weather, injuries, looks and parlay), and Today's looks shows three cards, not six
  if(shown.length > 2){ document.querySelectorAll('.tdgame.show').forEach(function(el){ if(el.querySelector('.tdmore')) el.classList.add('compact'); });
    var plays = [].slice.call(document.querySelectorAll('.tdgame.show .play[data-gap]')).filter(function(p){ var k = +p.getAttribute('data-ko'); return !k || k > now; }).sort(function(a, b){ return (+b.getAttribute('data-gap')) - (+a.getAttribute('data-gap')); }).slice(0, 3);
    if(plays.length){ var grid = document.getElementById('tdlooksgrid'); plays.forEach(function(p, i){ var c = p.cloneNode(true); c.classList.toggle('lead', i === 0); grid.appendChild(c); }); document.getElementById('tdlooks').hidden = false; } }
  if(shown.length > 5){ var day = document.getElementById('tdday'), cs = [].slice.call(document.querySelectorAll('.tdgame.show'));
    cs.slice(3).forEach(function(el){ el.classList.add('tdx'); });
    var ab = document.createElement('button'); ab.type = 'button'; ab.className = 'tdallb'; ab.id = 'tdallb'; ab.setAttribute('aria-expanded', 'false'); ab.textContent = 'Show all ' + cs.length + ' games';
    document.getElementById('tdgames').after(ab);
    ab.addEventListener('click', function(){ var on = day.classList.toggle('all'); ab.setAttribute('aria-expanded', on); ab.textContent = on ? 'Show fewer games' : 'Show all ' + cs.length + ' games'; if(!on) day.scrollIntoView(); });
    if(location.hash && /^#td-/.test(location.hash) && document.querySelector(location.hash + '.tdx')){ day.classList.add('all'); ab.setAttribute('aria-expanded', 'true'); ab.textContent = 'Show fewer games'; } }
  document.addEventListener('click', function(ev){ var b = ev.target.closest && ev.target.closest('.tdtog'); if(!b) return; var card = b.closest('.tdgame'); card.classList.toggle('open'); b.setAttribute('aria-expanded', card.classList.contains('open')); });
  if(!shown.length){ none.hidden = false; none.innerHTML = '<div class="tdempty"><b>No games on the board.</b> The week is graded on the <a href="/receipts/" style="color:var(--ink)">receipts</a> page; next week\'s board posts Tuesday and its prop prices fill in by Thursday. Your <a href="/team/" style="color:var(--ink)">fantasy team</a> and the <a href="/trade/" style="color:var(--ink)">trade calculator</a> work all week.</div>'; }
  // the rest of the week
  var wk = document.getElementById('tdweeklist') || {}; var html = '';
  dates.forEach(function(d){ if(d === pick) return; html += '<div class="tdwd"><b>' + esc(shortDay(d)) + (d < today ? ' · final' : '') + '</b><div class="g">' + byDay[d].map(function(g){ return '<a href="/boards/#g-' + esc(g.gid) + '" class="' + (d < today ? 'post' : '') + '">' + esc(g.away) + ' @ ' + esc(g.home) + '<small>' + esc((g.kick || '').replace(/^\w{3}\s*/, '')) + '</small></a>'; }).join('') + '</div></div>'; });
  if(html) wk.innerHTML = html; else if(document.getElementById('tdweek')) document.getElementById('tdweek').hidden = true;
  // kickoff countdown on each card (the live score chip takes over at kickoff)
  function cd(){ var t = Date.now();
    // 11/17: the lead parlay of a game that has kicked off can no longer be bet as built - it leaves Today (it sat here with its "Add all to FanDuel" button after the week was over)
    var psx = document.getElementById('parlay'), plx = psx && psx.querySelector('.parlay[data-ko]'); if(plx && +plx.getAttribute('data-ko') && t >= +plx.getAttribute('data-ko')) psx.hidden = true;
    document.querySelectorAll('.tdgame[data-ko]').forEach(function(el){ var k = +el.getAttribute('data-ko'); if(k) el.classList.toggle('ko', t >= k); });
    document.querySelectorAll('.tdcd[data-ko]').forEach(function(el){ var d = (+el.getAttribute('data-ko')) - t; if(!(d > 0)){ el.textContent = ''; return; }
    var m = Math.floor(d / 60000), h = Math.floor(m / 60), dd = Math.floor(h / 24);
    el.textContent = dd >= 1 ? 'in ' + dd + 'd ' + (h % 24) + 'h' : h >= 1 ? 'in ' + h + 'h ' + (m % 60) + 'm' : 'in ' + m + 'm'; }); }
  cd(); setInterval(cd, 30000);
  // news: today's teams first
  var tms = {}; shown.forEach(function(g){ tms[g.a] = 1; tms[g.b] = 1; });
  var nl = document.getElementById('tdnewsl');
  if(nl){ var items = [].slice.call(nl.children); items.sort(function(x, y){ var a = tms[x.getAttribute('data-team')] ? 0 : 1, b = tms[y.getAttribute('data-team')] ? 0 : 1; return a - b; }); items.forEach(function(li){ nl.appendChild(li); }); }
  // audit 11/10: the list ran ~5,800px on a phone (30 notes, a quarter of the page). The first eight show (today's teams first); the rest open on tap.
  // 11/10 evening: the home page shows the first three (today's teams first); the whole list is /news/
  if(nl){ var NCAP = +nl.getAttribute('data-cap') || 8, lis = [].slice.call(nl.children); if(lis.length > NCAP){ lis.forEach(function(li, i){ if(i >= NCAP) li.hidden = true; }); } }
  // ---- you today: slip legs in these games + your Sleeper roster vs the news ----
  var you = document.getElementById('tdyou'), box = document.getElementById('tdyoubox'); var rows = [];
  function render(){ if(!rows.length) return; you.hidden = false; box.innerHTML = rows.map(function(r){ return '<div class="yrow ' + esc(r.k || '') + '"><span class="yk">' + esc(r.kind) + '</span><div><b>' + esc(r.title) + '</b><small>' + esc(r.sub) + '</small></div>' + (r.href ? '<a href="' + esc(r.href) + '">' + esc(r.cta || 'Open') + '</a>' : '') + '</div>'; }).join(''); }
  try {
    var slip = JSON.parse(localStorage.getItem('bs_slipk_w' + T.week) || '[]'); if(!Array.isArray(slip)) slip = [];
    var saved = JSON.parse(localStorage.getItem('bs_slips_w' + T.week) || '[]'); var allKeys = slip.slice();
    (Array.isArray(saved) ? saved : []).forEach(function(s){ if(s && s.res) return;   // 11/27: a settled slip (marked won, lost or void) is no longer one of "your legs today"
      (s.keys || s.legs || []).forEach(function(k){ allKeys.push(typeof k === 'string' ? k : (k.key || '')); }); });
    var kset = {}; allKeys.forEach(function(k){ if(k) kset[k] = 1; });
    var n = 0, games = {};
    shown.forEach(function(g){ (T.keys[g.gid] || []).forEach(function(k){ if(kset[k]){ n++; games[g.gid] = (games[g.gid] || 0) + 1; } }); });
    if(n){ rows.push({kind: 'Slips', k: 'watch', title: n + (n === 1 ? ' leg' : ' legs') + ' of yours ' + (pick === today ? 'kick off today' : 'play ' + dayName(pick)), sub: Object.keys(games).map(function(g){ return g.replace('-', ' / ') + ' ×' + games[g]; }).join(' · ') + ' · tracked live with the model\'s chance from here', href: '/live/', cta: 'Live'}); }
    else if(allKeys.length){ rows.push({kind: 'Slips', title: allKeys.length + ' legs in your slips this week', sub: 'none of them ' + (pick === today ? 'today' : dayName(pick || today)) + ' - the Live page tracks them when they do', href: '/live/', cta: 'Live'}); }
  } catch(e){}
  render();
  var su = null, sl = null; try{ su = localStorage.getItem('bs_sleeper_user'); sl = localStorage.getItem('bs_sleeper_league'); }catch(e){}
  if(su && sl && shown.length){
    var API = 'https://api.sleeper.app/v1/'; function get(p){ return fetch(API + p).then(function(r){ if(!r.ok) throw new Error(p); return r.json(); }); }
    var pm = null; try{ var c = JSON.parse(localStorage.getItem('bs_sleeper_players') || 'null'); if(c && c.m) pm = c.m; }catch(e){}
    var norm = function(s){ return String(s || '').toLowerCase().replace(/[.'’]/g, '').replace(/\s+(jr|sr|ii|iii|iv|v)$/, '').replace(/\s+/g, ' ').trim(); };
    var TF = {LAR: 'LA', WSH: 'WAS', JAC: 'JAX'};
    Promise.all([get('user/' + encodeURIComponent(su)), get('league/' + sl + '/rosters'), pm ? Promise.resolve(pm) : get('players/nfl').then(function(all){ var m = {}; Object.keys(all).forEach(function(id){ var x = all[id]; if(x && x.position && ['QB','RB','WR','TE','K','DEF'].indexOf(x.position) >= 0) m[id] = {n: x.position === 'DEF' ? id : (x.full_name || ((x.first_name||'') + ' ' + (x.last_name||''))), t: x.team || '', p: x.position}; }); try{ localStorage.setItem('bs_sleeper_players', JSON.stringify({t: Date.now(), m: m})); }catch(e){} return m; })])
    .then(function(r){ var user = r[0], rosters = r[1], map = r[2]; var mine = rosters.filter(function(x){ return x.owner_id === user.user_id || (x.co_owners || []).indexOf(user.user_id) >= 0; })[0]; if(!mine) return;
      var players = (mine.players || []).map(function(id){ return map[id]; }).filter(Boolean); var starters = {}; (mine.starters || []).forEach(function(id){ starters[id] = 1; });
      var byName = {}; players.forEach(function(p){ byName[norm(p.n)] = p; });
      var newsMine = T.news.filter(function(n){ return byName[norm(n.player)]; });
      var playing = players.filter(function(p){ var t = TF[p.t] || p.t; return tms[t]; });
      newsMine.forEach(function(n){ var p = byName[norm(n.player)]; rows.push({kind: n.tag, k: n.k, title: n.player, sub: (TF[p.t] || p.t) + ' ' + p.p + (tms[TF[p.t] || p.t] ? ' · plays ' + (pick === today ? 'today' : dayName(pick)) : '') + ' · on your Sleeper roster', href: '/player/?q=' + encodeURIComponent(n.player), cta: 'Player'}); });
      if(playing.length) rows.push({kind: 'Sleeper', title: playing.length + ' of your players ' + (pick === today ? 'play today' : 'play ' + dayName(pick)), sub: playing.slice(0, 8).map(function(p){ return p.n; }).join(', ') + (playing.length > 8 ? '…' : ''), href: '/team/', cta: 'Start / sit'});
      render();
      // mark their news in the list
      if(nl) [].slice.call(nl.children).forEach(function(li){ if(byName[norm(li.getAttribute('data-player'))]) li.classList.add('mine'); });
    }).catch(function(e){ console.warn('sleeper', e); });
  } else if(shown.length && !su) { rows.push({kind: 'Sleeper', title: 'Connect your Sleeper team', sub: 'see which of your players have news today, and who the model would start', href: '/team/', cta: 'Connect'}); render(); }
  // share: the first visible game card as an image
  var sb = document.getElementById('tdshare');
  if(sb){ sb.addEventListener('click', function(){ var el = document.querySelector('.tdgame.show') || document.getElementById('tdday'); if(!window.html2canvas || !el){ if(navigator.share) navigator.share({title: 'BetSweep today', url: location.href}); return; }
    sb.disabled = true; sb.textContent = '…';
    html2canvas(el, {backgroundColor: getComputedStyle(document.body).getPropertyValue('--card').trim() || '#161d28', scale: 2, useCORS: true, logging: false}).then(function(c){ return new Promise(function(res){ c.toBlob(res, 'image/png'); }); }).then(function(blob){
      var f = new File([blob], 'betsweep-today.png', {type: 'image/png'});
      if(navigator.canShare && navigator.canShare({files: [f]})) return navigator.share({files: [f], title: 'BetSweep today', text: 'Today on BetSweep · betsweep.co/today/'});
      var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'betsweep-today.png'; a.click();
    }).catch(function(e){ console.warn(e); }).then(function(){ sb.disabled = false; sb.textContent = 'Share'; }); }); }
})();
/* 11/28 (owner 11/27 8:31 PM, "I love all 8"): the opener - the next game, or the one in play - and each game card's state:
   a countdown before kickoff, the score while it is on, and a Final card afterwards. The state comes from the page's live feed
   (home.py fires "bs-live" with it); until the first one lands the clock and the build's own final scores stand in. */
(function(){
  var T = window.__TD || {games: []}, COL = T.col || {}, LIVE = null, TZ = 'America/Chicago';
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function hm(t){ return /^[A-Z]{2,3}$/.test(t) ? '<i class="hm" data-hm="' + t + '" role="img" aria-label="' + t + '"></i>' : ''; }
  function stateOf(g){ var s = LIVE && LIVE[g.gid]; if(s) return s; var now = Date.now();
    if(g.fin) return {st: 'post', finTxt: g.fin}; if(g.ko && now >= g.ko + 4.5 * 3600e3) return {st: 'post'}; if(g.ko && now >= g.ko) return {st: 'in', nofeed: true}; return {st: 'pre'}; }
  function scoreOf(g, s){ var a = s && s.sa != null && s.sa !== '' ? +s.sa : null, b = s && s.sb != null && s.sb !== '' ? +s.sb : null;
    if(a == null || b == null || isNaN(a) || isNaN(b)){ var m = /^([A-Z]{2,3})\s+(\d+)\s*[–-]\s*([A-Z]{2,3})\s+(\d+)$/.exec(String((s && s.finTxt) || g.fin || '').trim()); if(!m) return null;
      var by = {}; by[m[1]] = +m[2]; by[m[3]] = +m[4]; if(by[g.a] == null || by[g.b] == null) return null; a = by[g.a]; b = by[g.b]; }
    var o = {}; o[g.a] = a; o[g.b] = b; return o; }
  function left(ms){ var m = Math.max(0, Math.floor(ms / 60000)), h = Math.floor(m / 60), d = Math.floor(h / 24); return d >= 1 ? d + 'd ' + (h % 24) + 'h' : h >= 1 ? h + 'h ' + (m % 60) + 'm' : m + 'm'; }
  function sgn(x){ return !x ? 'PK' : (x > 0 ? '+' : '−') + Math.abs(x); }
  function lineOf(g){ var parts = [], hi = g.pa >= g.pb ? g.a : g.b; if(isFinite(g.pa) && isFinite(g.pb)) parts.push('Model <b>' + esc(hi) + ' ' + Math.max(g.pa, g.pb).toFixed(0) + '–' + Math.min(g.pa, g.pb).toFixed(0) + '</b>');
    if(g.sp != null && g.home) parts.push(!g.sp ? esc(g.home) + ' PK' : g.sp < 0 ? esc(g.home) + ' −' + Math.abs(g.sp) : esc(g.away || g.home) + ' −' + Math.abs(g.sp));
    if(g.tot != null) parts.push('O/U ' + g.tot); return parts.join(' · '); }
  /* ---- the opener ---- */
  function hero(){ var el = document.getElementById('tdhero'); if(!el) return; var now = Date.now();
    var live = T.games.filter(function(g){ return stateOf(g).st === 'in'; }), next = T.games.filter(function(g){ return g.ko && stateOf(g).st === 'pre'; }).sort(function(x, y){ return x.ko - y.ko; });
    var g = live[0] || next[0]; if(!g){ el.hidden = true; el.innerHTML = ''; return; }
    var s = stateOf(g), on = s.st === 'in', sc = on ? scoreOf(g, s) : null, away = g.away || g.a, home = g.home || g.b;
    var more = (on ? live : next.filter(function(x){ return x.ko === g.ko; })).filter(function(x){ return x !== g; }), mineG = favGame(fav()) === g;
    var mid = on ? (sc ? '<b>' + sc[away] + '<i>–</i>' + sc[home] + '</b>' : '<b>Live</b>') + '<small>' + esc(s.nofeed || !s.det ? 'In progress' : s.det) + '</small>'
                 : '<b>' + esc(left(g.ko - now)) + '</b><small>' + esc(g.kick || '') + '</small>';
    var h = '<a class="thl wxhost" href="' + (on ? '/live/#lv-' : '/boards/#g-') + esc(g.gid) + '" style="--wa:' + esc(COL[away] || 'transparent') + ';--wb:' + esc(COL[home] || 'transparent') + '" data-gid="' + esc(g.gid) + '" data-st="' + (on ? 'in' : 'pre') + '">' +
      (!on && g.wx ? '<i class="wxfx ' + esc(g.wx) + '" aria-hidden="true"></i>' : '') +
      '<span class="thk">' + (on ? '<em class="lv" style="font-style:normal">Live now' + (mineG ? ' \u00b7 your team' : '') + '</em>' : '<em style="font-style:normal">Next up' + (mineG ? ' \u00b7 your team' : '') + '</em>') + '<em style="font-style:normal">' + (on ? 'Follow live' : 'Matchup board') + ' →</em></span>' +
      '<span class="thm"><span class="tht">' + hm(away) + '<b>' + esc(away) + '</b></span><span class="thc">' + mid + '</span><span class="tht r"><b>' + esc(home) + '</b>' + hm(home) + '</span></span>' +
      (lineOf(g) ? '<span class="thf">' + lineOf(g) + '</span>' : '') + '</a>';
    var f = fav(), fg = favGame(f), fc = favChip(f, g);
    if(fc){ h += '<div class="thx thxf"><span>Your team</span>' + fc + '</div>'; more = more.filter(function(x){ return x !== fg; }); }
    if(more.length) h += '<div class="thx"><span>' + (on ? 'Also live' : 'Same kickoff') + '</span>' + more.map(function(x){ var xa = x.away || x.a, xh = x.home || x.b;
      return '<a href="' + (on ? '/live/#lv-' : '/boards/#g-') + esc(x.gid) + '">' + hm(xa) + esc(xa) + ' @ ' + esc(xh) + hm(xh) + '</a>'; }).join('') + '</div>';
    if(el.getAttribute('data-h') !== h){ el.setAttribute('data-h', h); el.innerHTML = h; } el.hidden = false; }
  /* ---- favorite team (the seventh of the eight ideas, owner 11/27 8:31 PM "I love all 8"; 11/28 1:29 AM "make sure all 8 ... are
     finished"). One team a device, kept in this browser (bs_fav) and never sent anywhere; the alerts' "Favorite team" box on My
     BetSweep sets the same choice. With a team chosen, Today names its game under the opener (kickoff, the live score or the final),
     puts its card first among the games in the same state and marks it. The choice itself is one chip beside Short view and Live
     (a native list sits over it): "+ Your team" until a team is chosen, then that team's logo and letters. ---- */
  var TEAMS = T.teams || [];
  function fav(){ try { var v = localStorage.getItem('bs_fav') || ''; return TEAMS.some(function(t){ return t[0] === v; }) ? v : ''; } catch(e){ return ''; } }
  function favGame(f){ return f ? T.games.filter(function(g){ return g.a === f || g.b === f; })[0] || null : null; }
  function favPick(){ var host = document.querySelector('.tdhead .tdact'); if(!host || !TEAMS.length) return; var f = fav(), lab = document.getElementById('tdfavp');
    if(!lab){ lab = document.createElement('label'); lab.className = 'thfav'; lab.id = 'tdfavp';
      lab.innerHTML = '<span></span><select id="tdfavsel" aria-label="Your favorite team"><option value="">No team</option>' + TEAMS.map(function(t){ return '<option value="' + esc(t[0]) + '">' + esc(t[1]) + '</option>'; }).join('') + '</select>';
      host.appendChild(lab); }
    var want = f ? hm(f) + esc(f) + ' <i aria-hidden="true">\u25be</i>' : '+ Your team', sp = lab.firstChild, sel = lab.querySelector('select');
    if(lab.getAttribute('data-f') !== f){ lab.setAttribute('data-f', f); sp.innerHTML = want; lab.classList.toggle('set', !!f); }
    if(sel && sel.value !== f && document.activeElement !== sel) sel.value = f; }
  function favChip(f, g0){
    if(!f) return '';
    var g = favGame(f); if(!g) return '<em class="thoff">' + esc(f) + ' is off this week</em>';
    if(g === g0) return '';   /* its game is the one the opener already shows */
    var s = stateOf(g), sc = scoreOf(g, s), a = g.away || g.a, hh = g.home || g.b;
    var tail = s.st === 'in' ? (sc ? sc[a] + '\u2013' + sc[hh] + ' live' : 'Live') : s.st === 'post' ? (sc ? 'Final ' + sc[a] + '\u2013' + sc[hh] : 'Final') : (g.kick || '');
    return '<a class="thmine" href="' + (s.st === 'in' ? '/live/#lv-' : s.st === 'post' ? '/live/#box-' : '/boards/#g-') + esc(g.gid) + '">' + hm(a) + esc(a) + ' @ ' + esc(hh) + hm(hh) + (tail ? '<small>' + esc(tail) + '</small>' : '') + '</a>'; }
  document.addEventListener('change', function(e){ if(!e.target || e.target.id !== 'tdfavsel') return; var v = e.target.value;
    try { if(v) localStorage.setItem('bs_fav', v); else localStorage.removeItem('bs_fav'); } catch(x){}
    e.target.blur(); var el = document.getElementById('tdhero'); if(el) el.removeAttribute('data-h'); paint(); });
  /* ---- the Final card ---- */
  function legLine(m, ln){ var n = Math.round(+ln); if(/TD$/.test(m) && m.indexOf('Passing') < 0) return m; if(m === 'Passing TDs') return n + '+ passing TDs'; if(m === 'Receptions') return n + '+ receptions';
    if(m === 'Rush + Rec Yards') return n + '+ rush + rec yards'; return n + '+ ' + String(m).toLowerCase(); }
  function odds(o){ o = Math.round(+o); return isNaN(o) ? '' : (o > 0 ? '+' + o : String(o).replace('-', '−')); }
  function calls(g, fz, A, H, away, home){ if(!fz || !isFinite(fz.pa) || !isFinite(fz.pb)) return ''; var rows = [], mA = away === g.a ? fz.pa : fz.pb, mH = home === g.b ? fz.pb : fz.pa, mm = mH - mA, am = H - A;
    var win = A === H ? 'It ended level' : (H > A ? home : away) + ' won by ' + Math.abs(am);
    if(Math.abs(mm) < 0.5) rows.push(['', 'Winner', 'Model had it a toss-up', win]);
    else rows.push([A === H ? 'push' : ((am > 0) === (mm > 0)) ? 'hit' : 'miss', 'Winner', 'Model had ' + (mm > 0 ? home : away) + ' by ' + Math.abs(mm).toFixed(1), win]);
    if(fz.sp != null && fz.home === home && Math.abs(mm + fz.sp) >= 0.05){ var sp = +fz.sp, side = (mm + sp) > 0 ? home : away, cov = am + sp;
      rows.push([cov === 0 ? 'push' : ((cov > 0) === (side === home)) ? 'hit' : 'miss', 'Spread', 'Model leaned ' + (side === home ? home + ' ' + sgn(sp) : away + ' ' + sgn(-sp)), cov === 0 ? 'It landed on the number' : (cov > 0 ? home : away) + ' covered by ' + Math.abs(cov)]); }
    if(fz.tot != null && Math.abs(mA + mH - fz.tot) >= 0.05){ var tot = +fz.tot, over = (mA + mH) > tot, pts = A + H;
      rows.push([pts === tot ? 'push' : ((pts > tot) === over) ? 'hit' : 'miss', 'Total', 'Model leaned ' + (over ? 'over ' : 'under ') + tot, pts + ' points']); }
    var mark = {hit: '✓', miss: '✗', push: '='};
    return '<ul class="fcall">' + rows.map(function(r){ return '<li class="' + r[0] + '"><i aria-hidden="true">' + (mark[r[0]] || '·') + '</i><span>' + r[1] + '</span><div><b>' + esc(r[2]) + '</b><small>' + esc(r[3]) + '</small></div></li>'; }).join('') + '</ul>'; }
  function when(iso){ try { return new Date(iso).toLocaleString('en-US', {weekday: 'short', hour: 'numeric', minute: '2-digit', timeZone: TZ}); } catch(e){ return ''; } }
  function finalCard(card, g, s){ var sc = scoreOf(g, s), key = sc ? sc[g.a] + '-' + sc[g.b] : 'none'; if(card.getAttribute('data-fin-shown') === key) return; card.setAttribute('data-fin-shown', key);
    var box = card.querySelector('.tdfin'); if(!box){ box = document.createElement('div'); box.className = 'tdfin'; var hd = card.querySelector('header'); hd.parentNode.insertBefore(box, hd.nextSibling); }
    if(!sc){ box.innerHTML = '<p class="fnote">Final. The score has not reached this page yet: <a href="/live/#box-' + esc(g.gid) + '">box score on Live</a>.</p>'; return; }
    var away = g.away || g.a, home = g.home || g.b, A = sc[away], H = sc[home], fz = g.fz || null, lk = (fz && fz.looks) || [];
    var h = '<div class="fsc" aria-label="Final: ' + esc(away) + ' ' + A + ', ' + esc(home) + ' ' + H + '"><span class="ft' + (A > H ? ' w' : '') + '">' + hm(away) + '<b>' + esc(away) + '</b><em>' + A + '</em></span><span class="fl">Final</span>' +
      '<span class="ft r' + (H > A ? ' w' : '') + '"><em>' + H + '</em><b>' + esc(home) + '</b>' + hm(home) + '</span></div>' + calls(g, fz, A, H, away, home);
    if(lk.length) h += '<button type="button" class="flt" aria-expanded="false" data-g="' + esc(g.gid) + '"><span>The model’s ' + (lk.length === 1 ? 'look' : lk.length + ' looks') + ' <small class="flr"></small></span><i aria-hidden="true">▾</i></button>' +
      '<ul class="flk" hidden>' + lk.map(function(l, i){ return '<li data-i="' + i + '"><i aria-hidden="true">·</i><div><b>' + esc(l.pl) + '</b><small>' + esc(legLine(l.m, l.ln)) + ' · ' + esc(odds(l.o)) + '</small></div><em></em></li>'; }).join('') + '</ul>';
    if(fz && fz.at) h += '<p class="fnote">The model’s score, FanDuel’s line' + (lk.length ? ' and the looks' : '') + ' are the last copy before kickoff (' + esc(when(fz.at)) + ' CT).</p>';
    box.innerHTML = h; }
  /* the looks are graded from ESPN's box score, and only when the reader opens them: one request per game */
  var EA = {WSH: 'WAS', LAR: 'LA', JAC: 'JAX'}, BOXP = {};
  function nrm(n){ return String(n || '').toLowerCase().replace(/[.'’]/g, '').replace(/\s+(jr|sr|ii|iii|iv|v)$/, '').replace(/\s+/g, ' ').trim(); }
  function ymd(t){ var d = new Date(t); return d.getFullYear() + String(d.getMonth() + 1).padStart(2, '0') + String(d.getDate()).padStart(2, '0'); }
  function boxOf(g){ if(BOXP[g.gid]) return BOXP[g.gid]; var S = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl', num = function(v){ var x = parseFloat(String(v).split('/')[0]); return isFinite(x) ? x : 0; };
    var s = LIVE && LIVE[g.gid], eid = s && s.eid ? Promise.resolve(s.eid) : fetch(S + '/scoreboard?dates=' + ymd(g.ko - 864e5) + '-' + ymd(g.ko + 864e5), {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(sb){
      var id = null; ((sb && sb.events) || []).forEach(function(ev){ var c = (ev.competitions || [])[0] || {}, ts = (c.competitors || []).map(function(x){ var a = x.team && x.team.abbreviation; return EA[a] || a; }); if(ts.indexOf(g.a) >= 0 && ts.indexOf(g.b) >= 0) id = ev.id; }); return id; });
    return BOXP[g.gid] = eid.then(function(id){ if(!id) return null; return fetch(S + '/summary?event=' + id, {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }); }).then(function(sm){ if(!sm) return null; var box = {}, tds = {};
      (((sm.boxscore || {}).players) || []).forEach(function(tm){ (tm.statistics || []).forEach(function(cat){ var keys = cat.keys || [];
        (cat.athletes || []).forEach(function(at){ var nm = at.athlete && at.athlete.displayName; if(!nm) return; var st = {}; keys.forEach(function(k, i){ st[k] = (at.stats || [])[i]; }); var row = box[nrm(nm)] = box[nrm(nm)] || [0, 0, 0, 0, 0, 0, 0, 0, 0];
          if(cat.name === 'passing'){ row[0] = num(st.passingYards); row[1] = num(st.passingTouchdowns); row[2] = num(st.interceptions); }
          if(cat.name === 'rushing'){ row[3] = num(st.rushingYards); row[4] = num(st.rushingTouchdowns); }
          if(cat.name === 'receiving'){ row[5] = num(st.receptions); row[6] = num(st.receivingYards); row[7] = num(st.receivingTouchdowns); row[8] = num(st.longReception); } }); }); });
      return Object.keys(box).length >= 10 ? {box: box} : null; }).catch(function(){ return null; }); }
  var SK = {'Passing Yards': 0, 'Passing TDs': 1, 'Rushing Yards': 3, 'Receptions': 5, 'Receiving Yards': 6, 'Longest Reception': 8};
  function grade(l, d){ var row = d.box[nrm(l.pl)], m = l.m; if(!row) return null;
    if(/TD$/.test(m) && m.indexOf('Passing') < 0 && m !== 'First TD'){ var n = row[4] + row[7], need = m === '2+ TD' ? 2 : m === '3+ TD' ? 3 : 1; return {hit: n >= need, val: n + (n === 1 ? ' TD' : ' TDs')}; }
    var v = m === 'Rush + Rec Yards' ? row[3] + row[6] : SK[m] != null ? row[SK[m]] : null; if(v == null) return null; return {hit: v >= Math.round(+l.ln), val: String(v)}; }
  function openLooks(btn){ var card = btn.closest('.tdgame'), ul = card.querySelector('.flk'), g = T.games.filter(function(x){ return x.gid === btn.getAttribute('data-g'); })[0]; if(!ul || !g) return;
    var on = ul.hidden; ul.hidden = !on; btn.setAttribute('aria-expanded', on ? 'true' : 'false'); if(!on || btn.getAttribute('data-done')) return; btn.setAttribute('data-done', '1');
    var note = btn.querySelector('.flr'); note.textContent = 'reading the box score…';
    boxOf(g).then(function(d){ if(!d){ note.textContent = 'box score not available here'; btn.removeAttribute('data-done'); delete BOXP[g.gid]; return; } var hit = 0, n = 0, open = 0;
      [].forEach.call(ul.children, function(li){ var l = g.fz.looks[+li.getAttribute('data-i')], r = grade(l, d); if(!r){ open++; li.querySelector('em').textContent = 'no stat line'; return; }
        n++; if(r.hit) hit++; li.className = r.hit ? 'hit' : 'miss'; li.querySelector('i').textContent = r.hit ? '✓' : '✗'; li.querySelector('em').textContent = r.val; });
      note.textContent = n ? hit + ' of ' + n + ' hit' + (open ? ' · ' + open + ' not graded' : '') : 'not graded'; }); }
  document.addEventListener('click', function(e){ var b = e.target.closest && e.target.closest('.flt'); if(b) openLooks(b); });
  /* ---- each card's state, and the order: in play, then still to come, then finished ---- */
  function cards(){ var shown = 0, FV = fav(); T.games.forEach(function(g){ var card = document.getElementById('td-' + g.gid); if(!card) return; var s = stateOf(g), st = s.st, sc = scoreOf(g, s), away = g.away || g.a, home = g.home || g.b;
      card.classList.toggle('live', st === 'in'); card.classList.toggle('fin', st === 'post'); if(card.classList.contains('show')) shown++;
      var mine = !!FV && (g.a === FV || g.b === FV), ft = card.querySelector('.tdfavt'); card.classList.toggle('fav', mine);
      if(mine){ card.style.setProperty('--favc', COL[FV] || 'var(--red)'); if(!ft){ var tk = card.querySelector('.tdk'); if(tk){ ft = document.createElement('span'); ft.className = 'tdfavt'; ft.textContent = 'Your team'; tk.insertBefore(ft, tk.firstChild); } } }
      else if(ft) ft.remove();
      var chip = card.querySelector('.tdk .gl'); if(chip){ var c = st === 'in' ? '<i>LIVE</i>' + (sc ? sc[away] + '–' + sc[home] : '') + (s.det && !s.nofeed ? ' <small>' + esc(s.det) + '</small>' : '') : st === 'post' ? '<i>FINAL</i>' : ''; if(chip.innerHTML !== c) chip.innerHTML = c; }
      var pri = card.querySelector('.tdlinks a.pri'); if(pri){ if(!pri.getAttribute('data-h0')){ pri.setAttribute('data-h0', pri.getAttribute('href')); pri.setAttribute('data-t0', pri.textContent); }
        var want = st === 'in' ? ['/live/#lv-' + g.gid, 'Follow live'] : st === 'post' ? ['/live/#box-' + g.gid, 'Box score and plays'] : [pri.getAttribute('data-h0'), pri.getAttribute('data-t0')];
        if(pri.getAttribute('href') !== want[0]){ pri.setAttribute('href', want[0]); pri.textContent = want[1]; } }
      if(st === 'post') finalCard(card, g, s); });
    var wrap = document.getElementById('tdgames'), cs = wrap ? [].slice.call(wrap.querySelectorAll('.tdgame.show')) : []; if(cs.length > 1){
      var rank = function(el){ return el.classList.contains('live') ? 0 : el.classList.contains('fin') ? 2 : 1; };
      var isF = function(el){ return el.classList.contains('fav') ? 0 : 1; };
      var want = cs.slice().sort(function(x, y){ return rank(x) - rank(y) || isF(x) - isF(y) || (+x.getAttribute('data-ko') - +y.getAttribute('data-ko')); });
      if(!want.every(function(el, i){ return el === cs[i]; })) want.forEach(function(el){ wrap.appendChild(el); });
      if(document.getElementById('tdallb')) want.forEach(function(el, i){ el.classList.toggle('tdx', i >= 3); }); }
    /* on a day with one or two games the cards are open, so their looks are read at once */
    if(shown && shown <= 2) [].forEach.call(document.querySelectorAll('.tdgame.show.fin .flt:not([data-done])'), function(b){ if(b.getAttribute('aria-expanded') !== 'true') openLooks(b); }); }
  function paint(){ try { favPick(); cards(); hero(); } catch(e){ if(window.console) console.warn('today state', e); } }
  document.addEventListener('bs-live', function(e){ if(e.detail) LIVE = e.detail; paint(); });
  paint(); setInterval(paint, 30000);
})();
</script>"""
if __name__ == "__main__":
    sections(IN, OUT, sys.argv[1] if len(sys.argv) > 1 else None)   # the site clone: the frozen pre-kickoff copy the site is serving lives in its data/ folder
