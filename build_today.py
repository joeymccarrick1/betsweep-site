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
import home as HOME, flags as FLAGS
E = html.escape
TEAM_OF = {"Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN",
           "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB", "Houston Texans": "HOU", "Indianapolis Colts": "IND",
           "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
           "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG", "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
           "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS"}
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

def sections(IN_, OUT_):
    D = HOME.load(IN_, OUT_); bd = D["bd"]; W = bd.get("week") or 0
    games = sorted(bd["games"], key=lambda g: g.get("ko") or 0); G = {g["gid"]: g for g in games}
    try: FE = FLAGS.Engine(IN_, W)
    except Exception as e: print("today: flags engine failed", e); FE = None
    GL = game_lines()
    try: VOICE = json.load(open(os.path.join(OUT_, "voice.json")))
    except Exception: VOICE = {}
    vg = VOICE.get("games") or {}; vl = VOICE.get("legs") or {}
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
        return {"News: out": "OUT", "News: concussion protocol": "Protocol", "News: limited / questionable": "Q", "News: doubtful": "Doubtful", "News: role up": "Role up", "News: role down": "Role down",
                "News: back / practising": "Back", "News: trade / signing": "Trade"}.get(n.get("tag"), n.get("tag", ""))
    def script_line(g):
        fav = g["a"] if g["pa"] > g["pb"] else g["b"]; marg = abs(g["pa"] - g["pb"])
        return f"Model {E(g['a'])} {g['pa']:.0f} – {E(g['b'])} {g['pb']:.0f} · {E(fav)} by {marg:.1f} · {E(g.get('most', ''))}"
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
    cards = []
    for g in games:
        L = GL.get(g["gid"]) or {}; away, home = L.get("away", g["a"]), L.get("home", g["b"])
        ch = chips(g); ns = news_for(g); bp = parlay_for(g["gid"]); say = vg.get(g["gid"])
        chip_html = "".join(f'<span class="tdc {E(k)}"><b>{E(t)}</b>{E(x)}</span>' for k, t, x in ch)
        news_html = "".join(f'<li class="{E(n["k"])}"><b>{E(tag_short(n))}</b> <span>{E(n["player"])}</span> <small>{E(n["team"])} {E(n.get("pos", ""))}</small></li>' for n in ns)
        legs = legs_by_g.get(g["gid"], [])[:3]
        legs_html = "".join(HOME.play_card(HOME._mb(D, l, G)).replace('<article class="play ', f'<article data-k="{E(HOME.leg_key(l["pl"], l["m"], l["ln"]))}" data-gap="{((l.get("raw_p") or l["p"]) - l["bk"]):.4f}" class="play ', 1) for l in legs)
        bp_html = ""
        if bp:
            price = bp.get("price") or bp.get("odds") or ""
            bp_html = ('<div class="tdbp"><small>Best parlay for this game</small><ul>' + "".join(f'<li><b>{E(str(x[0]))}</b> <span>{E(HOME.leg_line(x[1], x[2]))}</span><em>{E(odds(x[3]))}</em></li>' for x in bp["legs"][:4]) + '</ul>'
                       + (f'<a class="more" href="/boards/#g-{E(g["gid"])}">Full card →</a>') + '</div>')
        cards.append(f'''<article class="tdgame" id="td-{E(g["gid"])}" data-gid="{E(g["gid"])}" data-ko="{g.get("ko") or ""}" data-date="{E(ct_date(g.get("ko")) or "")}" data-fin="{E(g.get("fin", ""))}">
 <header><div class="tdm"><span class="tm">{E(away)}</span><span class="at">@</span><span class="tm">{E(home)}</span></div><div class="tdk"><b>{E(g.get("kick", ""))}</b><span class="gl"></span></div></header>
 <p class="tdl">{market_line(g)}{" · " if market_line(g) else ""}{script_line(g)}</p>
 {f'<p class="sweepsays"><i>Sweep says</i>{E(say)}</p>' if say else ""}
 {f'<div class="tdchips">{chip_html}</div>' if chip_html else ""}
 {f'<ul class="tdnews">{news_html}</ul>' if news_html else ""}
 {f'<button type="button" class="tdtog" aria-expanded="false">Looks &amp; parlay <i>▾</i></button><div class="tdmore"><div class="plays tdplays">{legs_html}</div>{bp_html}</div>' if (legs_html or bp_html) else ""}
 <div class="tdlinks"><a href="/boards/#g-{E(g["gid"])}">Matchup card</a><a href="/build/#g-{E(g["gid"])}">Builder</a><a href="/lab/merged/?g={E(g["gid"])}">Game Desk</a><a href="/live/#lv-{E(g["gid"])}">Live</a></div>
</article>''')
    # ---- news that moved the model (whole week, newest first) -------------------------------------------------------------------------
    sev = {"bad": 0, "watch": 1, "good": 2, "info": 3}
    news = [n for n in NEWS.get("players", []) if n.get("k") in ("bad", "watch", "good") and n.get("bucket") != "TREND"]
    news.sort(key=lambda n: (sev.get(n["k"], 9), str(n.get("ts") or "")), reverse=False)
    news.sort(key=lambda n: -(n.get("sev") or 0))
    def clean_txt(n):   # the desk's text starts with the headline ("Name: Out (Hamstring). ..."); the card already shows the name and tag
        t = re.sub(r"^" + re.escape(n["player"]) + r"\s*:[^.]*\.\s*", "", n["txt"]); return t
    news_items = "".join(f'<li class="{E(n["k"])}" data-team="{E(n.get("team", ""))}" data-player="{E(n["player"])}"><span class="nt">{E(tag_short(n))}</span><div><b>{E(n["player"])} <small>{E(n.get("team", ""))} {E(n.get("pos", ""))}</small></b><p>{E(clean_txt(n))}</p></div></li>' for n in news[:30])
    # ---- record strip -----------------------------------------------------------------------------------------------------------------
    try: R = HOME.record(D); rec_html = HOME.record_block(R, W)
    except Exception as e: rec_html = ""; print("today: record failed", e)
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
        if hot: body.append("; ".join(f"{n['player']} {tag_short(n).lower()}" for n in hot))
        if looks: body.append("Looks: " + " · ".join(f"{l['pl']} {HOME.leg_line(l['m'], l['ln'])} ({odds(l['o'])}, {l['p']*100:.0f}%)" for l in looks))
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
    # ---- page ------------------------------------------------------------------------------------------------------------------------
    stamp = built.strftime("%a %-m/%-d %-I:%M %p")
    body = f'''<title>Today · BetSweep</title>
<meta name="description" content="Today on BetSweep: what kicks off, the model's plus-money looks for today's games, the news that moved the numbers, your slips and your Sleeper team.">
<style>{TODAY_CSS}</style>
<section class="tdhead"><div class="tdh1"><h1 id="tdtitle">Today</h1><span class="tdsub" id="tdsub">Week {W}</span></div><div class="tdact"><button type="button" class="tdlisten" id="tdlisten" hidden title="Read today's brief aloud">▶ Listen</button><button type="button" class="tdshare" id="tdshare" title="Share today's card as an image">Share</button><a class="tdlive" href="/live/">Live</a></div></section>
<section class="sec" id="tdlooks" hidden><h2 class="t">Today's looks <small class="tsub">plus-money edges</small></h2><div class="plays" id="tdlooksgrid"></div><p class="none" style="margin-top:8px;font-size:12.5px">The model's chance vs what FanDuel's price needs, +150 or longer, 5+ points of edge. Weeks 6–8: 41% hit at about +200, +31% at a unit each. Tap + Slip to collect them, then open the betslip.</p></section>
<section class="sec tdday" id="tdday"><div class="tdgames" id="tdgames">{"".join(cards)}</div><p class="none" id="tdnone" hidden></p></section>
<section class="sec" id="tdyou" hidden><h2 class="t">You today</h2><div class="tdyou" id="tdyoubox"></div></section>
<section class="sec" id="tdask"><h2 class="t">Ask the model <small class="tsub">the week's numbers, in a sentence or two</small></h2>
 <form class="askbox" id="askform"><input type="text" id="askq" maxlength="400" placeholder="Charbonnet 60+ rush yds tonight?" autocomplete="off"><button type="submit" class="bsbtn" id="askgo">Ask</button></form>
 <p class="asknote" id="asknote">Signed-in users get 20 questions a day. Answers quote the model's chance, the FanDuel price and the flags - nothing it does not have.</p>
 <div class="askans" id="askans" hidden></div>
</section>
<section class="sec" id="tdnewsS"><h2 class="t">News that moved the model <small class="tsub">as of {E(stamp)} CT</small></h2>{("<ul class='tdnewsl' id='tdnewsl'>" + news_items + "</ul>") if news_items else "<p class='none'>Quiet so far. The news desk refreshes with every rebuild.</p>"}<p class="none" style="margin-top:8px;font-size:12.5px">From the news desk: ESPN, RotoWire, CBS, Yahoo and the team injury pages, read at every rebuild. Red = out, amber = limited or a role change, green = back or a bigger role. Live injury chips on names update every 10 minutes everywhere on the site.</p></section>
{tgt_html}
<section class="sec" id="tdweek"><h2 class="t">The rest of the week</h2><div class="tdweek" id="tdweeklist"></div></section>
<section class="sec" id="record"><h2 class="t">Track record</h2>{rec_html}<p class="none" style="margin-top:8px;font-size:12.5px"><a href="/how/" style="color:var(--ink)">How BetSweep picks</a> · <a href="/season/" style="color:var(--ink)">every week graded</a></p></section>
<div class="hsbar" id="hsbar" data-week="{E(str(W))}"><b></b><a href="/build/">Open betslip</a></div>
<script>window.__TD = {json.dumps({"week": W, "built": built.isoformat(), "games": [{"gid": g["gid"], "a": g["a"], "b": g["b"], "ko": g.get("ko"), "kick": g.get("kick", ""), "fin": g.get("fin", ""), "home": (GL.get(g["gid"]) or {}).get("home", g["b"]), "away": (GL.get(g["gid"]) or {}).get("away", g["a"])} for g in games], "keys": keys_by_g, "news": [{"player": n["player"], "team": n.get("team", ""), "k": n["k"], "tag": tag_short(n)} for n in news]}, separators=(",", ":"))};</script>
{TODAY_JS}
{HOME.home_js(games)}
{HOME.HOME_SLIP_JS}
'''
    open(os.path.join(OUT_, "today.html"), "w").write(body)
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
.tdact{display:flex;gap:8px;align-items:center} .tdshare,.tdlive{font:inherit;font-family:var(--display);font-weight:700;font-size:12.5px;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:7px 14px;cursor:pointer;text-decoration:none} .tdlive{background:var(--red);border-color:var(--red);color:#fff}
.tdday .tdgames{display:grid;gap:12px}
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
.tdyou{display:grid;gap:8px} .tdyou .yrow{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:14px} .tdyou .yrow b{font-family:var(--display);font-weight:700;font-size:16px} .tdyou .yrow small{color:var(--mute);display:block;font-size:12.5px} .tdyou .yk{font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--red);min-width:54px} .tdyou .yrow a{text-decoration:none;color:var(--ink);font-weight:600;font-size:13px;border:1px solid var(--line);border-radius:6px;padding:5px 9px;white-space:nowrap} .tdyou .yrow.bad .yk{color:var(--bad)} .tdyou .yrow.good .yk{color:var(--good)} .tdyou .yrow.watch .yk{color:#b7791f}
.tgcols{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))} .tgt{margin:0 0 8px;font-family:var(--display);font-weight:700;font-size:13px;letter-spacing:.1em;text-transform:uppercase} .tgt.buy{color:var(--good)} .tgt.sell{color:var(--redtxt,var(--red))}
.tgl{list-style:none;margin:0;padding:0;display:grid;gap:8px} .tg{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;border-left-width:4px} .tg.buy{border-left-color:var(--good)} .tg.sell{border-left-color:var(--red)}
.tgh{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap} .tgh a{color:var(--ink);text-decoration:none} .tgh a:hover{text-decoration:underline} .tgm{color:var(--mute);font-size:12.5px} .tgr{margin-left:auto;font-family:var(--display);font-weight:700;font-size:13px} .tgr small{font-weight:500;color:var(--mute)}
.tgn{display:flex;gap:14px;margin:6px 0 4px;font-size:12.5px;color:var(--mute)} .tgn b{color:var(--ink);font-family:var(--display);font-size:15px;font-weight:700;margin-right:3px} .tg p{margin:0;font-size:13.5px;line-height:1.45}
.tdnewsl{list-style:none;margin:0;padding:0;display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr))} .tdnewsl li{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px} .tdnewsl li .nt{font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.12em;text-transform:uppercase;padding-top:3px;min-width:52px} .tdnewsl li.bad .nt{color:var(--bad)} .tdnewsl li.watch .nt{color:#b7791f} .tdnewsl li.good .nt{color:var(--good)} .tdnewsl li b{font-family:var(--display);font-weight:700;font-size:16px} .tdnewsl li b small{color:var(--mute);font-size:12px;font-weight:600;margin-left:4px} .tdnewsl li p{margin:2px 0 0;color:var(--mute);font-size:13px;line-height:1.45} .tdnewsl li.mine{border-color:var(--red)}
.tdweek{display:grid;gap:8px} .tdwd{display:grid;grid-template-columns:auto minmax(0,1fr);gap:4px 12px;align-items:baseline;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px} .tdwd b{font-family:var(--display);font-weight:800;font-size:15px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)} .tdwd .g{display:flex;flex-wrap:wrap;gap:6px 12px;font-size:13.5px} .tdwd .g a{text-decoration:none;color:var(--ink);font-weight:600} .tdwd .g a small{color:var(--mute);font-weight:500;margin-left:4px} .tdwd .g a.post{opacity:.6}
.tdempty{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 16px;font-size:15px;line-height:1.5} .tdempty b{font-family:var(--display);font-size:22px;display:block;margin-bottom:4px}
.askbox{display:flex;gap:8px} .askbox input{flex:1;min-width:0;font:inherit;font-size:16px;min-height:44px;padding:8px 12px;border:1.5px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)} .askbox input:focus{outline:none;border-color:var(--red);box-shadow:0 0 0 3px color-mix(in srgb,var(--red) 22%,transparent)}
.asknote{margin:6px 0 0;color:var(--mute);font-size:13px} .askans{margin-top:10px;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--red);border-radius:12px;padding:12px 14px;font-size:15px;line-height:1.5;white-space:pre-wrap}
/* owner 11/5: Listen - the brief read aloud by the phone's own voice */
.tdlisten{font:inherit;font-family:var(--display);font-weight:700;font-size:12.5px;letter-spacing:.05em;text-transform:uppercase;display:inline-flex;align-items:center;gap:6px;min-height:36px;padding:0 14px;border-radius:8px;border:1.5px solid var(--line);background:transparent;color:var(--ink);cursor:pointer} .tdlisten.on{border-color:var(--red);color:var(--red)}
@media (max-width:560px){.tdm{font-size:26px} .tdh1 h1{font-size:34px}}
"""

TODAY_JS = r"""<script>
(function(){ // Ask the model (owner 11/5): POST {mode:'ask', q} to the alert function with the user's session token
  var f = document.getElementById('askform'), q = document.getElementById('askq'), go = document.getElementById('askgo'), out = document.getElementById('askans'), note = document.getElementById('asknote'); if (!f) return;
  var CFG = window.__BS_ACCOUNT || {}; var FN = (CFG.url || '') + '/functions/v1/slip-alerts';
  f.addEventListener('submit', function(e){ e.preventDefault(); var text = (q.value || '').trim(); if (text.length < 3) return;
    var acct = window.bsAccount; if (!acct || !acct.user || !acct.client){ note.textContent = 'Sign in (menu, top right) to ask - it is free, 20 a day.'; var s = document.querySelector('#bsacct .in'); if (s) s.focus(); return; }
    go.disabled = true; out.hidden = false; out.textContent = 'Thinking…';
    acct.client.auth.getSession().then(function(r){ var tok = r.data && r.data.session && r.data.session.access_token;
      return fetch(FN, {method: 'POST', headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok, 'apikey': CFG.key || ''}, body: JSON.stringify({mode: 'ask', q: text})}); })
    .then(function(r){ return r.json(); }).then(function(j){ out.textContent = j && j.a ? j.a : (j && j.error) || 'No answer came back.'; if (j && typeof j.left === 'number') note.textContent = j.left + ' questions left today.'; })
    .catch(function(){ out.textContent = 'Could not reach the model desk.'; }).then(function(){ go.disabled = false; }); });
})();
(function(){ // Listen (owner 11/5): the day's brief through speechSynthesis - no server, works in the car
  var b = document.getElementById('tdlisten'); if (!b || !('speechSynthesis' in window)) return;
  function text(){ var parts = []; var h = document.getElementById('tdtitle'); if (h) parts.push(h.textContent.trim() + '.');
    document.querySelectorAll('.tdgame.show').forEach(function(g){ var m = g.querySelector('.tdm'); var say = g.querySelector('.sweepsays'); var l = g.querySelector('.tdl');
      if (m) parts.push(m.textContent.replace(/\s+/g, ' ').replace('@', ' at ') + '.'); if (l) parts.push(l.textContent.replace(/\s+/g, ' ') + '.'); if (say) parts.push(say.textContent.replace(/^Sweep says/i, 'Sweep says:').replace(/\s+/g, ' ') + '.'); });
    var looks = document.querySelectorAll('#tdlooksgrid .play'); if (looks.length){ parts.push("Today's looks."); looks.forEach(function(p, i){ if (i > 3) return; var who = p.querySelector('.who b'), what = p.querySelector('.what'); if (who && what) parts.push(who.textContent + ', ' + what.textContent.replace(/\s+/g, ' ') + '.'); }); }
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
  else { title.textContent = 'Week ' + T.week + ' is in the books'; sub.textContent = 'Receipts grade Tuesday · the next slate lands Thursday morning'; }
  var showG = {}; shown.forEach(function(g){ showG[g.gid] = 1; });
  document.querySelectorAll('.tdgame').forEach(function(el){ el.classList.toggle('show', !!showG[el.getAttribute('data-gid')]); });
  if(shown.length > 2){ document.querySelectorAll('.tdgame.show').forEach(function(el){ if(el.querySelector('.tdmore')) el.classList.add('compact'); });
    var plays = [].slice.call(document.querySelectorAll('.tdgame.show .play[data-gap]')).sort(function(a, b){ return (+b.getAttribute('data-gap')) - (+a.getAttribute('data-gap')); }).slice(0, 6);
    if(plays.length){ var grid = document.getElementById('tdlooksgrid'); plays.forEach(function(p, i){ var c = p.cloneNode(true); c.classList.toggle('lead', i === 0); grid.appendChild(c); }); document.getElementById('tdlooks').hidden = false; } }
  document.addEventListener('click', function(ev){ var b = ev.target.closest && ev.target.closest('.tdtog'); if(!b) return; var card = b.closest('.tdgame'); card.classList.toggle('open'); b.setAttribute('aria-expanded', card.classList.contains('open')); });
  if(!shown.length){ none.hidden = false; none.innerHTML = '<div class="tdempty"><b>No games on the board.</b> The week is graded on the <a href="/receipts/" style="color:var(--ink)">receipts</a> page; Thursday morning\'s rebuild brings the next slate. Your <a href="/team/" style="color:var(--ink)">fantasy team</a> and the <a href="/trade/" style="color:var(--ink)">trade calculator</a> work all week.</div>'; }
  // the rest of the week
  var wk = document.getElementById('tdweeklist'); var html = '';
  dates.forEach(function(d){ if(d === pick) return; html += '<div class="tdwd"><b>' + esc(shortDay(d)) + (d < today ? ' · final' : '') + '</b><div class="g">' + byDay[d].map(function(g){ return '<a href="/boards/#g-' + esc(g.gid) + '" class="' + (d < today ? 'post' : '') + '">' + esc(g.away) + ' @ ' + esc(g.home) + '<small>' + esc((g.kick || '').replace(/^\w{3}\s*/, '')) + '</small></a>'; }).join('') + '</div></div>'; });
  if(html) wk.innerHTML = html; else document.getElementById('tdweek').hidden = true;
  // news: today's teams first
  var tms = {}; shown.forEach(function(g){ tms[g.a] = 1; tms[g.b] = 1; });
  var nl = document.getElementById('tdnewsl');
  if(nl){ var items = [].slice.call(nl.children); items.sort(function(x, y){ var a = tms[x.getAttribute('data-team')] ? 0 : 1, b = tms[y.getAttribute('data-team')] ? 0 : 1; return a - b; }); items.forEach(function(li){ nl.appendChild(li); }); }
  // ---- you today: slip legs in these games + your Sleeper roster vs the news ----
  var you = document.getElementById('tdyou'), box = document.getElementById('tdyoubox'); var rows = [];
  function render(){ if(!rows.length) return; you.hidden = false; box.innerHTML = rows.map(function(r){ return '<div class="yrow ' + esc(r.k || '') + '"><span class="yk">' + esc(r.kind) + '</span><div><b>' + esc(r.title) + '</b><small>' + esc(r.sub) + '</small></div>' + (r.href ? '<a href="' + esc(r.href) + '">' + esc(r.cta || 'Open') + '</a>' : '') + '</div>'; }).join(''); }
  try {
    var slip = JSON.parse(localStorage.getItem('bs_slipk_w' + T.week) || '[]'); if(!Array.isArray(slip)) slip = [];
    var saved = JSON.parse(localStorage.getItem('bs_slips_w' + T.week) || '[]'); var allKeys = slip.slice();
    (Array.isArray(saved) ? saved : []).forEach(function(s){ (s.keys || s.legs || []).forEach(function(k){ allKeys.push(typeof k === 'string' ? k : (k.key || '')); }); });
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
</script>"""
if __name__ == "__main__":
    sections(IN, OUT)
