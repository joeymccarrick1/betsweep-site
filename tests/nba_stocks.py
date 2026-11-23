"""/nba/stocks/ - the NBA Stock Market, in the NFL Stock Market's clothes. A PREVIEW like /nba/: not in the menu, not in the sitemap.

Owner 11/22 3:27 PM: "I want each sport to basically look exactly like everything we've built for NFL."; 7:14 PM: "Alright get to what's next!"

The page ships the file it was drawn from (/nba/stocks/stocks.json: the stocks numbers the feeds-sports job wrote, and which board it used).
This test redoes the page from that file and tonight's board (/nba/board.json): the tiles of each position in each mode and their order,
every tile's number and move, the mover cards, a player's panel (his sentences, his next game, his stats, his games), the search - at
390x844 in light and dark and on a desktop. Plus the builder's rules on made-up data: which files are drawn, what "his next game" says.

Serves SITE (default ./site).   python3 tests/nba_stocks.py [shots_dir]
With no /nba/stocks/ in the build it says so and passes: the page is optional, a stale one is not.
"""
import asyncio, json, os, re, sys, threading, http.server, functools, datetime as dt
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); TREE = os.path.join(HERE, ".."); sys.path.insert(0, TREE)
ROOT = os.environ.get("SITE") or os.path.join(TREE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8884
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
import build_nba_stocks as K
f1 = lambda x: f"{x:.1f}"


def rules():
    good = {"sport": "nba", "format": K.FORMAT, "data_through": "2026-11-21", "players": [{}] * 60}
    day = dt.date(2026, 11, 22)
    r = [K.usable(None, day), K.usable(dict(good, format=9), day), K.usable(dict(good, players=[{}] * 10), day), K.usable(dict(good, data_through="2026-11-10"), day), K.usable({k: v for k, v in good.items() if k != "data_through"}, day)]
    check(K.usable(good, day)[0] and K.usable(good, dt.date(2026, 11, 26))[0] and not any(x[0] for x in r) and all(x[1] for x in r),
          f"a stocks file is drawn when it is in the right shape, holds 50+ players and its games reach within five days; otherwise not, each with its reason (e.g. {r[3][1][:58]}...)")
    check([K.delta_text(x) for x in (19.04, -18.6, 0.3, -0.2, 0.04)] == ["▲ 19.0", "▼ 18.6", "+0.3", "−0.2", "0.0"], "a move reads as on the NFL page: a triangle from half a point, a plain sign under it, no sign on 0.0")
    B = {"day_label": "Sun 11/22", "games": [{"key": "BOS-GS", "home": "GS", "away": "BOS", "tipct": "7:30 PM"}],
         "teams": {"BOS": {"out": [{"name": "Out Guy", "tag": "Out", "why": "Knee"}]}, "GS": {"out": []}},
         "players": [{"id": "1", "proj": {"pts": 26.84, "reb": 7.6, "ast": 4.9, "fg3": 3.1}, "min": 34.6, "status": None}, {"id": "2", "proj": {"pts": 10, "reb": 3, "ast": 2, "fg3": 1}, "min": 22, "status": {"tag": "Questionable"}}]}
    a = K.tonight({"id": "1", "name": "Star", "team": "BOS"}, B); q = K.tonight({"id": "2", "name": "Iffy", "team": "GS"}, B)
    o = K.tonight({"id": "3", "name": "Out Guy", "team": "BOS"}, B); n = K.tonight({"id": "4", "name": "Idle", "team": "LAL"}, B); x = K.tonight({"id": "5", "name": "Deep Bench", "team": "GS"}, B)
    check(a == (["Sun 11/22: at GS, 7:30 PM CT.", "The model has him at 26.8 points, 7.6 rebounds, 4.9 assists and 3.1 threes in about 35 minutes."], "/nba/#BOS-GS", "", "") and q[0][0] == "Sun 11/22: vs BOS, 7:30 PM CT." and q[0][-1] == "Listed questionable." and q[2:] == ("Q", ""),
          "his next game: where and when, and the board's numbers for him; a questionable player says so and wears a Q")
    check(o[0] == ["Sun 11/22: at GS, 7:30 PM CT. Listed out (Knee), so the board has no numbers for him."] and o[2:] == ("OUT", "o") and n == (["The Lakers do not play on Sun 11/22."], "", "", "") and "not in the board's rotation" in x[0][0] and K.tonight({"id": "1", "name": "Star", "team": "BOS"}, None) == ([], "", "", ""),
          "a player listed out gets no numbers and an OUT tag; a team that is off says so; a player outside the rotation says so; with no board the block is left out")


READ = r"""(function(){
  var tx = function(e){ return e ? e.textContent.replace(/\s+/g, ' ').trim() : ''; }, vis = function(e){ return !!e && e.getClientRects().length > 0; };
  var out = {mode: document.getElementById('nsk').getAttribute('data-mode'), secs: {}};
  document.querySelectorAll('.sksec[id^="nsk-"]').forEach(function(s){
    var g = s.id.slice(4).toUpperCase(), o = {};
    ['rise', 'fall'].forEach(function(m){
      var ul = s.querySelector('.skg[data-for="' + m + '"]'), mb = s.querySelector('.skmr[data-for="' + m + '"] .skmore');
      o[m] = {shown: vis(ul), tiles: ul ? [...ul.querySelectorAll('li.sk')].map(function(li){ return [li.getAttribute('data-k'), tx(li.querySelector('.sknm')), tx(li.querySelector('.sktb')), tx(li.querySelector('.skv b')), tx(li.querySelector('em')), li.classList.contains('up') ? 'up' : (li.classList.contains('dn') ? 'dn' : ''), !li.hidden, tx(li.querySelector('.skst')), li.querySelector('.skb').getBoundingClientRect().height]; }) : [],
              more: mb && vis(mb) ? tx(mb) : '', none: vis(s.querySelector('.sknone[data-for="' + m + '"]')), count: tx(s.querySelector('h2 small[data-for="' + m + '"]'))};
    });
    out.secs[g] = o;
  });
  out.mk = [...document.querySelectorAll('#nskmk .skmc')].map(function(b){ return [b.getAttribute('data-m'), b.getAttribute('data-k'), tx(b.querySelector('.skmt')), tx(b.querySelector('.skmn')), tx(b.querySelector('.skmx b')), tx(b.querySelector('.skmx small'))]; });
  out.bar = [[...document.querySelectorAll('.nbsw:not(.nbpg) a')].map(function(a){ return [a.textContent, a.getAttribute('href'), a.getAttribute('aria-current')]; }), [...document.querySelectorAll('.nbsw.nbpg a')].map(function(a){ return [a.textContent, a.getAttribute('href'), a.getAttribute('aria-current')]; })];
  out.over = document.documentElement.scrollWidth - innerWidth; out.h1 = tx(document.querySelector('.skhd h1')); out.font = getComputedStyle(document.querySelector('.skhd h1')).fontFamily; out.bg = getComputedStyle(document.querySelector('.skb')).backgroundColor;
  return out; })()"""

PANEL = r"""(function(){
  var p = document.querySelector('li.skp'); if(!p) return null;
  var tx = function(e){ return e ? e.textContent.replace(/\s+/g, ' ').trim() : ''; }, d = p.querySelector('details.sktbl'); d.open = true;
  var fx = [...p.querySelectorAll('.skfx > div')].map(function(x){ return [tx(x.querySelector('b')), [...x.querySelectorAll('p')].map(tx)]; }), pr = p.previousElementSibling, w = p.querySelector('.nskw');
  return {k: p.getAttribute('data-k'), h: tx(p.querySelector('.skph h3')), sub: tx(p.querySelector('.skph p')), q: [...p.querySelectorAll('.skqc')].map(function(c){ return [tx(c.querySelector('span')), tx(c.querySelector('b')), tx(c.querySelector('small'))]; }), fx: fx,
    st: [...p.querySelectorAll('.skt')].map(function(t){ return [t.getAttribute('data-s'), tx(t.querySelector('.sktl')), tx(t.querySelector('.sktv b')), tx(t.querySelector('.sktv em'))]; }),
    head: [...p.querySelectorAll('.nskt thead th')].map(tx), rows: [...p.querySelectorAll('.nskt tbody tr')].map(function(r){ return [...r.children].map(tx); }), rc: p.querySelectorAll('.nskt tbody tr.rc').length,
    link: (p.querySelector('.skpl a') || {getAttribute: function(){ return ''; }}).getAttribute('href'), full: p.getBoundingClientRect().width >= p.parentNode.getBoundingClientRect().width - 2, after: !!pr && pr.classList.contains('sk'),
    over: document.documentElement.scrollWidth - innerWidth, fits: w.scrollWidth - w.clientWidth, cls: p.className}; })()"""


async def main():
    rules()
    page_path = os.path.join(ROOT, "nba", "stocks", "index.html")
    if not os.path.exists(page_path):
        check(not os.path.exists(os.path.join(ROOT, "nba", "stocks", "stocks.json")), "this build has no NBA Stock Market page, and no leftover file of one (the page is optional; a stale one is not allowed)")
        print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
    src = open(page_path, encoding="utf-8").read()
    F = json.load(open(os.path.join(ROOT, "nba", "stocks", "stocks.json"))); S = F["stocks"]
    bp = os.path.join(ROOT, "nba", "board.json"); B = json.load(open(bp)) if os.path.exists(bp) else None
    if B is not None and (B.get("day") != F.get("board_day") or B.get("built") != F.get("board_built")): B = None if F.get("board_day") is None else B
    check((B or {}).get("built") == F.get("board_built"), f"the board beside /nba/ is the one this page took 'his next game' from ({F.get('board_day')})")
    PL = K.prep(S, B); BY = {x["k"]: x for x in PL}
    r = S["rule"]
    check(S.get("format") == K.FORMAT and len(PL) >= 50 and all(x["nr"] == r["recent"] and x["np"] >= 3 for x in PL), f"the page ships its numbers: {len(PL)} players through {S['data_through']}, each with {r['recent']} recent games and at least 3 before")
    bad = [x["n"] for x in PL if (x["dir"] == "up") != (x["d"] >= r["move"] and x["r"] >= r["floor"]) or (x["dir"] == "dn") != (x["d"] <= -r["move"] and x["p"] >= r["floor"]) or abs(round(x["r"] - x["p"], 1) - x["d"]) > 0.11]
    check(not bad, f"rising and falling follow the stated rule for every player: a move of {r['move']:g}+ with {r['floor']:g}+ a game on the better side ({sum(1 for x in PL if x['dir'] == 'up')} rising, {sum(1 for x in PL if x['dir'] == 'dn')} falling)" + (f" off: {bad[:4]}" if bad else ""))
    sm = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, "sitemap.xml")) else ""
    linkers = [rel for rel in ("index.html", "boards/index.html", "stocks/index.html", "build/index.html", "social/index.html") if os.path.exists(os.path.join(ROOT, rel)) and "/nba/stocks/" in open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore").read()]
    check("/nba/" not in sm and not linkers and '/nba/stocks/' in open(os.path.join(ROOT, "nba", "index.html"), encoding="utf-8").read(), f"it is a preview: not in the sitemap, linked from the NBA boards page and from nowhere else ({linkers})")
    check("NBA preview" in src and "no FanDuel prices yet, so nothing here is a pick" in src and "sportsbook.fanduel.com" not in src and "not betting advice" in src and "a move here is something to look into, not a forecast" in src,
          "the page says what it is: a preview, results and model numbers, no prices, no picks; and that five games is a short run")

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    want = {}
    for g, _, _ in K.GROUPS:
        want[g] = {"rise": sorted([x for x in PL if x["g"] == g and x["dir"] == "up"], key=lambda x: (-x["d"], x["n"])), "fall": sorted([x for x in PL if x["g"] == g and x["dir"] == "dn"], key=lambda x: (x["d"], x["n"]))}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme, vw, vh, phone in (("light", 390, 844, True), ("dark", 390, 844, True), ("dark", 1280, 900, False)):
            T = lambda s: f"[{theme} {'phone' if phone else 'desktop'}] {s}"
            ctx = await b.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=2 if phone else 1, is_mobile=phone, has_touch=phone)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            await ctx.route("**/*supabase*/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/nba/stocks/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
            st = await pg.evaluate(READ)
            check(st["h1"] == "Stock Market" and st["mode"] == "rise" and st["over"] <= 0 and "Barlow" in st["font"] and st["bar"] == [[["NFL", "/stocks/", None], ["NBA", "/nba/stocks/", "page"]], [["Boards", "/nba/", None], ["Stocks", "/nba/stocks/", "page"]]],
                  T("it opens on Rising in the site's own type, with the sport switch (NFL goes to the NFL Stock Market) and the NBA's pages above it, and no sideways scroll"))
            if theme == "light":
                badm = []
                for mode in ("rise", "fall"):
                    for g in want:
                        w = want[g][mode]; got = st["secs"][g][mode]
                        exp = [[x["k"], x["n"], x["t"], f1(x["r"]), K.delta_text(x["d"]), "up" if x["d"] >= 0.5 else ("dn" if x["d"] <= -0.5 else ""), i < K.TOP, x["st"]] for i, x in enumerate(w)]
                        if [t[:8] for t in got["tiles"]] != exp or got["count"] != f"{len(w)} {'rising' if mode == 'rise' else 'falling'}" or got["none"] != (mode == "rise" and not w) or got["shown"] != (mode == "rise" and bool(w)) \
                           or (mode == "rise" and got["more"] != (f"Show all {len(w)} rising {K.GNAME[g]}s" if len(w) > K.TOP else "")):
                            badm.append((g, mode, len(got["tiles"]), len(exp), got["count"], got["more"]))
                n = sum(len(want[g][m]) for g in want for m in want[g])
                check(not badm, f"all {n} tiles are the file's: each position's risers by the size of the move and its fallers likewise, the first {K.TOP} showing, each with name, team, last-{r['recent']} average, move and injury tag" + (f" (off: {badm[:3]})" if badm else ""))
                mk = K.movers(PL)
                check(st["mk"] == [[c["id"], c["k"], c["l"], BY[c["k"]]["n"], c["v"], c["s"]] for c in mk] and len(mk) == 6 and F.get("movers") == mk,
                      "six mover cards, each redone from the file: " + "; ".join(f"{c['l']} {BY[c['k']]['n']} {c['v']}" for c in mk[:4]))
            hts = [t[8] for g in st["secs"].values() for t in g["rise"]["tiles"] if t[6]]
            check(hts and min(hts) >= 44, T(f"every tile is at least 44px tall to tap ({min(hts):.0f}px)"))
            # ---- a player's panel
            g0 = next(g for g in want if want[g]["rise"]); x = want[g0]["rise"][0]
            await pg.click(f'#nsk-{g0.lower()} .skg[data-for="rise"] li.sk[data-k="{x["k"]}"] .skb'); await pg.wait_for_timeout(300)
            pn = await pg.evaluate(PANEL)
            wq = [[f"Last {x['nr']}", f1(x["r"]), "FP a game"], [f"The {x['np']} before", f1(x["p"]), f"{K.delta_text(x['d'])} since"], ["Season", f1(x["fp"]), f"{f1(x['mn'])} min a game"]]
            wfx = [["What moved", x["say"]]] + ([["His next game", x["to"]]] if x["to"] else [])
            check(bool(pn) and pn["k"] == x["k"] and pn["h"] == x["n"] and pn["sub"] == f"{x['tn']} · {K.GNAME[x['g']].capitalize()} · {x['gp']} games this season" and pn["q"] == wq and pn["fx"] == wfx and pn["full"] and pn["over"] <= 0 and ("up" in pn["cls"].split()),
                  T(f"a tap opens {x['n']}'s panel across the row: last {x['nr']} ({f1(x['r'])}), the {x['np']} before ({f1(x['p'])}), season ({f1(x['fp'])}); what moved, and his next game - all as the file has them") + ("" if pn and pn["q"] == wq and pn["fx"] == wfx else f" (page {json.dumps(pn and [pn['q'], pn['fx']])[:400]})"))
            wst = []
            for k, lab in K.STAT:
                a_, b_ = x["ravg"][k], x["avg"][k]; d_ = a_ - b_
                wst.append([k, lab, f1(a_), f"season {f1(b_)}" if abs(d_) < 0.05 else f"{'+' if d_ > 0 else chr(0x2212)}{f1(abs(d_))} on season"])
            rows = list(reversed(x["rows"]))
            wrows = [[r_[0], r_[1], r_[3]] if r_[2] is None else [r_[0], r_[1], f1(r_[10])] + [str(v) for v in r_[2:10]] for r_ in rows]
            check(pn["st"] == wst and pn["head"] == ["Date", "Opp", "FP", "Min", "Pts", "Reb", "Ast", "3s", "Stl", "Blk", "TO"] and pn["rows"] == wrows and pn["rc"] == x["nr"] and pn["link"] == x["ln"],
                  T(f"his seven stats over the last {x['nr']} beside the season's, and his last {len(rows)} games newest first with fantasy points first and the recent {x['nr']} marked"))
            extra = "" if pn["fits"] <= 0 else " but for %dpx that scroll inside it" % pn["fits"]
            check(pn["fits"] <= (0 if not phone else 24), T("the game table fits its box" + extra))
            if SHOTS:
                await pg.evaluate("document.querySelector('li.skp').scrollIntoView({block: 'start'}); window.scrollBy(0, -120)"); await pg.wait_for_timeout(200)
                await pg.screenshot(path=os.path.join(SHOTS, f"nbastocks_{theme}_{'phone' if phone else 'desk'}_panel.png"))
            await pg.click("li.skp .skx"); await pg.wait_for_timeout(200)
            check(await pg.evaluate("!document.querySelector('li.skp') && !document.querySelector('.skb[aria-expanded=\"true\"]')"), T("Close puts the panel away"))
            # ---- Show all, and Falling
            big = next((g for g in want if len(want[g]["rise"]) > K.TOP), None)
            if big:
                await pg.click(f'.skmore[data-list="{big}-rise"]'); await pg.wait_for_timeout(200)
                n_ = await pg.evaluate(f"""[[...document.querySelectorAll('.skg[data-list="{big}-rise"] li.sk')].filter(function(l){{ return l.getClientRects().length; }}).length, !!document.querySelector('.skmore[data-list="{big}-rise"]').getClientRects().length]""")
                check(n_ == [len(want[big]["rise"]), False], T(f"Show all brings out all {len(want[big]['rise'])} rising {K.GNAME[big]}s and the button goes"))
            await pg.click('.skmode button[data-mode="fall"]'); await pg.wait_for_timeout(250)
            fl = await pg.evaluate(READ)
            okf = fl["mode"] == "fall" and all(fl["secs"][g]["fall"]["shown"] == bool(want[g]["fall"]) and not fl["secs"][g]["rise"]["shown"] and fl["secs"][g]["fall"]["none"] == (not want[g]["fall"]) and all(t[5] == "dn" for t in fl["secs"][g]["fall"]["tiles"]) for g in want)
            check(okf and fl["over"] <= 0, T("Falling swaps every list for the fallers, drawn in the falling colour; a position with none says so"))
            await pg.click('.skmode button[data-mode="rise"]'); await pg.wait_for_timeout(200)
            # ---- a mover card opens its player, wherever he is
            mk = K.movers(PL); c = next(c for c in mk if c["id"] == "fall")
            await pg.evaluate("window.scrollTo(0, 0)"); await pg.click(f'#nskmk .skmc[data-m="fall"]'); await pg.wait_for_timeout(500)
            mo = await pg.evaluate("(function(){ var p = document.querySelector('li.skp'); return p ? [p.getAttribute('data-k'), document.getElementById('nsk').getAttribute('data-mode'), p.getBoundingClientRect().top < innerHeight] : null; })()")
            check(mo == [c["k"], "fall", True], T(f"the Biggest faller card switches to Falling and opens {BY[c['k']]['n']}"))
            c = next(c for c in mk if c["id"] == "hot"); await pg.evaluate("window.scrollTo(0, 0)"); await pg.click('#nskmk .skmc[data-m="hot"]'); await pg.wait_for_timeout(500)
            mo = await pg.evaluate("(function(){ var p = document.querySelector('li.skp'); return p ? p.getAttribute('data-k') : null; })()")
            check(mo == c["k"], T(f"the Hottest card opens {BY[c['k']]['n']}" + ("" if BY[c["k"]]["dir"] else ", who is on neither list, through the search")))
            # ---- search
            await pg.fill("#nskq", ""); await pg.wait_for_timeout(150)
            plain = next(x for x in PL if not x["dir"] and len(x["n"].split()[-1]) >= 5)
            qy = plain["n"].split()[-1].lower()[:5]; nrm = lambda s_: re.sub(r"[^a-z0-9 ]", "", s_.lower())
            hits = [x["k"] for x in PL if nrm(qy) in nrm(x["n"]) or nrm(qy) in nrm(x["tn"]) or x["t"].lower() == qy][:60]
            await pg.fill("#nskq", qy); await pg.wait_for_timeout(300)
            sr = await pg.evaluate("[[...document.querySelectorAll('#nskres li.sk')].map(function(l){ return l.getAttribute('data-k'); }), [...document.querySelectorAll('.sksec:not(#nskfind), #nskmk, .skmode, .skbar')].filter(function(e){ return e.getClientRects().length; }).length, document.getElementById('nsknone').hidden]")
            check(sr[0] == hits and plain["k"] in hits and sr[1] == 0 and sr[2], T(f"searching \"{qy}\" lists the {len(hits)} matching player{'s' if len(hits) != 1 else ''} ({plain['n']}, on neither list, among them) and puts the lists away"))
            await pg.click(f'#nskres li.sk[data-k="{plain["k"]}"] .skb'); await pg.wait_for_timeout(250)
            check(await pg.evaluate("(document.querySelector('li.skp') || {getAttribute: function(){}}).getAttribute('data-k')") == plain["k"], T("a search result opens like any tile"))
            tm = PL[0]["t"].lower(); await pg.fill("#nskq", tm); await pg.wait_for_timeout(250)
            n_t = await pg.evaluate("document.querySelectorAll('#nskres li.sk').length")
            check(n_t == len([x for x in PL if nrm(tm) in nrm(x["n"]) or nrm(tm) in nrm(x["tn"]) or x["t"].lower() == tm][:60]) and n_t >= 3, T(f"a team's letters ({tm.upper()}) list that team's players ({n_t})"))
            await pg.fill("#nskq", "zzzzqq"); await pg.wait_for_timeout(250)
            z = await pg.evaluate("[document.querySelectorAll('#nskres li.sk').length, document.getElementById('nsknone').getClientRects().length > 0]")
            await pg.fill("#nskq", ""); await pg.wait_for_timeout(250)
            back = await pg.evaluate("[document.getElementById('nskfind').hidden, [...document.querySelectorAll('.sksec:not(#nskfind), #nskmk, .skmode, .skbar')].every(function(e){ return e.getClientRects().length > 0; })]")
            check(z == [0, True] and back == [True, True], T("a name nobody has says so; clearing the box brings the lists back"))
            check(not errs and (await pg.evaluate("document.documentElement.scrollWidth - innerWidth")) <= 0, T(f"no script errors, no sideways scroll {errs[:2]}"))
            if SHOTS:
                await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(200); await pg.screenshot(path=os.path.join(SHOTS, f"nbastocks_{theme}_{'phone' if phone else 'desk'}.png"))
            await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
