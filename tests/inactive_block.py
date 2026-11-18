"""A player the live injury list has ruled out cannot be bet from any page (11/17).

The list (Supabase risk_feed) is filled every few minutes from ESPN's injury page and, about 90 minutes before a kickoff, from that
game's inactives. Every page reads it through /risk.js. The test answers that request itself: for each page it first looks at what
the page offers, picks a player it offers, rules him out ("OUT", detail "Inactive") and looks again.

What was already right before 11/17 and is pinned here: Boards and player pages refuse his add buttons and put a "Ruled out" chip
by his name; the builder refuses the tap; single-pick cards on Today and Model's Best leave with a note.
What 11/17 fixed: First TD kept a live "Add to slip" link on his row and kept him in its two lists; the Under of the day kept
offering his under with a FanDuel button (Today and the Short view); the Model's Best teaser on Today kept his row; the Boost finder
could put him in a slip; Line shop kept his rows.

The clock is set a day before the week's first kickoff and finals are taken out of the pages' own data, so this runs in any week.
A check whose page offers no player right now is skipped and says so.
  python3 tests/inactive_block.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, os, re, sys, threading, time
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("SITE") or os.path.join(HERE, "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8867; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
def skip(what): print("   (skipped: " + what + ")")
CLOCK = "(function(){var T=+(localStorage.getItem('t_now')||0);if(!T)return;var R=Date.now,S=R();Date.now=function(){return T+(R()-S)};var D0=Date;function ND(){if(arguments.length===0)return new D0(D0.now());return new (Function.prototype.bind.apply(D0,[null].concat([].slice.call(arguments))))();}ND.now=D0.now;ND.parse=D0.parse;ND.UTC=D0.UTC;ND.prototype=D0.prototype;window.Date=ND;})();"
VIS = "var vis = function(e){ if(!e) return false; var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; }, qa = function(s, r){ return Array.from((r || document).querySelectorAll(s)); }, nm = function(e){ return ((e.firstChild && e.firstChild.nodeType === 3) ? e.firstChild.nodeValue : e.textContent).trim(); };"

def builder_data():
    """the builder's data as the page serves it: {week, games: [{gid, ko, fin}], legs: [{pl, g, m, gl}]}"""
    ref = re.search(r"data-[0-9a-f]{8,}\.js", open(os.path.join(ROOT, "build", "index.html"), encoding="utf-8", errors="ignore").read())   # the file the page links (the folder keeps the previous build's too)
    s = open(os.path.join(ROOT, "build", ref.group(0)), encoding="utf-8").read(); m = re.search(r"window\.__BS\s*=\s*", s)
    return json.JSONDecoder().raw_decode(s, m.end())[0]

async def main():
    BD = builder_data(); week = BD["week"]; games = {g["gid"]: g for g in BD["games"]}
    kos = sorted(g["ko"] for g in BD["games"] if g.get("ko"))
    T = int(kos[0] - 26 * 3600e3)
    # the main player: most legs in the last game that has player legs
    cnt = {}
    for l in BD["legs"]:
        if l.get("gl") or " or " in l.get("pl", "") or not games.get(l.get("g"), {}).get("ko"): continue
        cnt[(l["pl"], l["g"])] = cnt.get((l["pl"], l["g"]), 0) + 1
    if not cnt: print("no player legs in this build - nothing to check"); print(f"{ok[0]} passed, {ok[1]} failed"); return
    lastg = max({g for _, g in cnt}, key=lambda g: games[g]["ko"])
    P1 = max((k for k in cnt if k[1] == lastg), key=lambda k: cnt[k])[0]
    slug = re.sub(r"[^a-z0-9]+", "-", P1.lower().replace("'", "").replace(".", "")).strip("-")
    print(f"   week {week}; main player {P1} ({lastg}, {cnt[(P1, lastg)]} legs); clock set to {time.strftime('%a %m/%d %H:%M', time.gmtime(T / 1000))} UTC")

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    def feed(pl): return [{"id": "inj|" + pl.lower(), "kind": "injury", "week": week, "player": pl, "team": "", "gid": "", "status": "OUT", "level": "block", "detail": "Inactive", "players": None,
                           "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}]
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def page(path, out=None, theme="dark"):
            """out = the player the injury list rules out (None = nobody)"""
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}');localStorage.setItem('t_now','{T}');}}catch(e){{}}" + CLOCK)
            body = json.dumps(feed(out) if out else [])
            async def risk(route, request): await route.fulfill(status=200, content_type="application/json", body=body)
            async def local(route, request):       # a build made after a game carries its final, and a final beats the clock: serve the page's own data without it
                u = request.url.split("?")[0].split("#")[0].replace(f"http://127.0.0.1:{PORT}", "")
                fp = os.path.join(ROOT, u.strip("/"), "index.html") if u.endswith("/") else os.path.join(ROOT, u.strip("/"))
                if os.path.isfile(fp) and fp.rsplit(".", 1)[-1] in ("html", "json", "js") and os.path.getsize(fp) < 6e6:
                    src = open(fp, encoding="utf-8", errors="replace").read()
                    if '"fin"' in src:
                        ct = {"html": "text/html; charset=utf-8", "json": "application/json", "js": "text/javascript; charset=utf-8"}[fp.rsplit(".", 1)[-1]]
                        await route.fulfill(status=200, content_type=ct, body=re.sub(r'"fin":\s*"[^"]*"', '"fin":""', src)); return
                await route.continue_()
            await ctx.route(f"http://127.0.0.1:{PORT}/**", local)
            await ctx.route("**/*espn.com/**", lambda r: r.abort()); await ctx.route("**/raw.githubusercontent.com/**", lambda r: r.abort())
            await ctx.route("**/*supabase*/**", lambda r: r.abort()); await ctx.route("**/rest/v1/risk_feed**", risk)
            pg = await ctx.new_page(); errs = []; pops = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200])); ctx.on("page", lambda q: pops.append(1))
            await pg.goto(f"http://127.0.0.1:{PORT}{path}", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600)
            return pg, ctx, errs, pops
        async def shot(pg, name):
            if SHOTS: await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/{name}.png")

        # ---- Boards: nobody out (control), then the main player out ----
        BREAD = "(P) => { " + VIS + """ var bs = qa('button[data-k]').filter(function(b){ return b.getAttribute('data-k').split('|')[0] === P; });
          return {btns: bs.length, blocked: bs.filter(function(b){ return b.classList.contains('bsrblock'); }).length, allBlocked: qa('.bsrblock').length, chips: qa('.bsrc.bsr-block').length,
                  over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""
        pg, ctx, errs, _ = await page("/boards/"); s0 = await pg.evaluate(BREAD, P1); await ctx.close()
        if not s0["btns"]: skip(f"Boards has no add button for {P1}")
        else:
            check(s0["allBlocked"] == 0 and s0["chips"] == 0 and not errs, f"Boards with nobody ruled out: no button is refused, no Ruled out chip ({s0})")
            pg, ctx, errs, _ = await page("/boards/", P1); s = await pg.evaluate(BREAD, P1)
            check(s["btns"] == s0["btns"] and s["blocked"] == s["btns"] and s["allBlocked"] == s["btns"] and s["chips"] >= 1 and s["over"] == 0 and not errs,
                  f"Boards with {P1} ruled out: every one of his {s['btns']} add buttons is refused, nobody else's is, and a Ruled out chip sits by his name ({s})")
            tap = await pg.evaluate("(P) => { " + VIS + """ var b = qa('button[data-k].bsrblock').filter(vis)[0] || qa('button[data-k].bsrblock')[0]; if(!b) return null; b.scrollIntoView({block: 'center'}); b.click();
              var t = document.querySelector('.bsrtoast'), keys = []; for(var i = 0; i < localStorage.length; i++){ var k = localStorage.key(i); if(/^bs_slipk?_w/.test(k)) keys.push(localStorage.getItem(k)); }
              return {toast: t ? t.textContent : '', slip: keys.join('')}; }""", P1)
            check(tap and "not added" in tap["toast"] and P1.split(" ")[-1] in tap["toast"] and P1 not in tap["slip"], f"Boards: tapping his leg says why and adds nothing ({(tap or {}).get('toast')!r})")
            await shot(pg, "inactive-boards"); await ctx.close()

        # ---- Builder: open his game, tap one of his legs ----
        pg, ctx, errs, _ = await page("/build/", P1)
        r = await pg.evaluate("(a) => { " + VIS + """ var c = document.getElementById('g-' + a[1]); if(!c) return {card: false}; var h = c.querySelector('.ghd'); if(h && h.getAttribute('aria-expanded') !== 'true') h.click(); return {card: true}; }""", [P1, lastg])
        await pg.wait_for_timeout(1300)
        r = await pg.evaluate("(P) => { " + VIS + """ var pc = qa('li.pc[data-pk]').filter(function(e){ return e.getAttribute('data-pk').split('|')[0] === P; })[0]; if(!pc) return {row: false};
          pc.scrollIntoView({block: 'center'}); var bt = qa('button.add', pc).filter(vis)[0]; if(bt) bt.click();
          var t = document.querySelector('.bsrtoast'), n = document.querySelector('.slipbar .n');
          return {row: true, chip: !!pc.querySelector('.bsrc.bsr-block'), btn: !!bt, on: bt ? bt.classList.contains('on') || bt.classList.contains('sel') : null, toast: t ? t.textContent : '', n: n ? n.textContent.trim() : null,
                  saved: (localStorage.getItem('bs_slipk_w' + (window.__BS ? window.__BS.week : '')) || '')}; }""", P1)
        if not r.get("row") or not r.get("btn"): skip(f"the builder shows no leg button for {P1} ({r})")
        else: check(r["chip"] and "not added" in r["toast"] and r["n"] in ("0", "", None) and P1 not in r["saved"] and not errs, f"Builder: his card carries the Ruled out chip, and tapping a leg says why and leaves the slip empty ({r['toast']!r}, slip count {r['n']!r})")
        await shot(pg, "inactive-builder"); await ctx.close()

        # ---- his player page ----
        if not os.path.isdir(os.path.join(ROOT, "player", slug)): skip(f"no player page for {P1}")
        else:
            pg, ctx, errs, _ = await page(f"/player/{slug}/", P1); s = await pg.evaluate(BREAD, P1)
            h1 = await pg.evaluate("() => !!(document.querySelector('.pp h1') && document.querySelector('.pp h1 .bsrc.bsr-block'))"); await ctx.close()
            if not s["btns"]: skip(f"{P1}'s page has no add buttons")
            else: check(s["blocked"] == s["btns"] and h1 and not errs, f"His player page: all {s['btns']} add buttons are refused and the chip is on his name")

        # ---- First TD ----
        FREAD = "(P) => { " + VIS + """ var rows = qa('[data-rk]').filter(function(e){ return e.getAttribute('data-rk').split('|')[0] === P; }), lis = rows.filter(function(e){ return e.tagName === 'LI'; }), trs = rows.filter(function(e){ return e.tagName === 'TR'; });
          return {trs: trs.length, lis: lis.length, liShown: lis.filter(vis).length, out: rows.filter(function(e){ return e.classList.contains('bsr-out'); }).length, chips: rows.filter(function(e){ return e.querySelector('.bsrc.bsr-block'); }).length,
                  links: rows.reduce(function(a, e){ return a + qa('a.fdgo', e).length; }, 0), blocked: rows.reduce(function(a, e){ return a + qa('a.fdgo.bsrblock', e).length; }, 0),
                  lists: qa('.ftdwrap .strips ul').map(function(ul){ return qa('li[data-ko]', ul).filter(vis).length; }), others: qa('[data-rk].bsr-out').length - rows.filter(function(e){ return e.classList.contains('bsr-out'); }).length,
                  over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""
        pg, ctx, errs, _ = await page("/firsttd/")
        pf = await pg.evaluate("() => { " + VIS + " var lis = qa('.ftdwrap .strips ul li[data-rk]').filter(vis), li = lis.filter(function(e){ return e.querySelector('a.fdgo'); })[0] || lis[0]; return li ? li.getAttribute('data-rk').split('|')[0] : null; }")
        f0 = await pg.evaluate(FREAD, pf) if pf else None; await ctx.close()
        if not pf: skip("First TD lists nobody right now (no prices yet, or the page predates data-rk)")
        else:
            pg, ctx, errs, pops = await page("/firsttd/", pf); f = await pg.evaluate(FREAD, pf)
            check(f["trs"] >= 1 and f["out"] == f["trs"] + f["lis"] and f["chips"] == f["trs"] + f["lis"] and f["blocked"] == f["links"] and f["others"] == 0 and f["over"] == 0 and not errs,
                  f"First TD with {pf} ruled out: his table row and list rows are marked, each has the chip, every FanDuel link of his is refused, nobody else is touched ({f})")
            check(f0["liShown"] >= 1 and f["liShown"] == 0 and f["lists"] == f0["lists"], f"First TD: he leaves the two lists at the top and the next players move up (rows shown {f0['lists']} -> {f['lists']})")
            tap = await pg.evaluate("(P) => { " + VIS + """ var a = qa('tr[data-rk] a.fdgo.bsrblock').filter(function(x){ return x.closest('tr').getAttribute('data-rk').split('|')[0] === P; })[0]; if(!a) return null;
              a.scrollIntoView({block: 'center', inline: 'center'}); a.click(); var t = document.querySelector('.bsrtoast'); return {toast: t ? t.textContent : ''}; }""", pf)
            await pg.wait_for_timeout(500)
            if tap is None: skip(f"{pf} has no FanDuel link on his table row (no price for him)")
            else: check("not added" in tap["toast"] and not pops, f"First TD: tapping his 'Add to slip' opens nothing and says why ({tap['toast']!r})")
            await shot(pg, "inactive-firsttd"); await ctx.close()

        # ---- Today and the Short view: single picks, the Under of the day, the Model's Best teaser ----
        TREAD = "() => { " + VIS + """ var play = qa('article.play').filter(function(a){ return vis(a) && a.querySelector('.who b') && qa('a.fdb', a).some(vis); })[0];
          var ud = qa('.udcard').filter(vis)[0], mb = qa('.mbl.teaser .mbrow').filter(vis);
          return {play: play ? nm(play.querySelector('.who b')) : null, ud: ud ? ud.getAttribute('data-pl') : null, uds: qa('.udcard').length, mb: mb.map(function(e){ return e.getAttribute('data-k').split('|')[0]; }), mbAll: qa('.mbl.teaser .mbrow').length}; }"""
        TOUT = "(P) => { " + VIS + """ var plays = qa('article.play').filter(function(a){ return a.querySelector('.who b') && nm(a.querySelector('.who b')) === P; });
          var ud = qa('.udcard').filter(vis)[0], sec = document.getElementById('bsunder');
          return {plays: plays.length, playsShown: plays.filter(vis).length, fd: plays.reduce(function(n, a){ return n + qa('a.fdb, a.more', a).filter(vis).length; }, 0), note: qa('.bsrhid').filter(vis).map(function(e){ return e.textContent; }).join(' | '),
                  ud: ud ? ud.getAttribute('data-pl') : null, udSec: !!(sec && !sec.hidden), mb: qa('.mbl.teaser .mbrow').filter(vis).map(function(e){ return e.getAttribute('data-k').split('|')[0]; }),
                  over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""
        for path, label in (("/", "Today"), ("/short/", "Short view")):
            if not os.path.isfile(os.path.join(ROOT, path.strip("/"), "index.html")): skip(f"no {label} page"); continue
            pg, ctx, errs, _ = await page(path); t0 = await pg.evaluate(TREAD); await ctx.close()
            if label == "Today":
                if not t0["play"]: skip("Today shows no single pick with a FanDuel button right now")
                else:
                    pg, ctx, errs, _ = await page(path, t0["play"]); t = await pg.evaluate(TOUT, t0["play"])
                    check(t["plays"] >= 1 and t["playsShown"] == 0 and t["fd"] == 0 and t0["play"] in t["note"] and t["over"] == 0 and not errs, f"Today with {t0['play']} ruled out: his pick card{'s' if t['plays'] > 1 else ''} ({t['plays']}) left the page and a note says who was hidden ({t['note'][:70]!r})")
                    await shot(pg, "inactive-today"); await ctx.close()
                if not t0["mb"]: skip("Today's Model's Best teaser is empty right now")
                else:
                    who = t0["mb"][0]; pg, ctx, errs, _ = await page(path, who); t = await pg.evaluate(TOUT, who); await ctx.close()
                    left = len({k for k in t0["mb"]} - {who})
                    check(who not in t["mb"] and len(t["mb"]) >= min(left, len(t0["mb"]) - 1) and not errs, f"Today's Model's Best teaser with {who} ruled out: his row is gone ({t0['mb']} -> {t['mb']})")
            if label == "Today":
                PL = sorted({l["pl"] for l in BD["legs"] if not l.get("gl")})
                pg, ctx, errs, _ = await page(path)
                pp = await pg.evaluate("(PL) => { " + VIS + " var out = null; qa('div.parlay').filter(vis).some(function(c){ if(!qa('.pfoot a.fdb', c).some(vis)) return false; return qa('ul.plegs li b', c).some(function(b){ var n = b.textContent.trim(); if(PL.indexOf(n) >= 0){ out = n; return true; } return false; }); }); return out; }", PL); await ctx.close()
                if not pp: skip("Today shows no ready-made parlay with a player leg and a FanDuel button right now")
                else:
                    pg, ctx, errs, _ = await page(path, pp)
                    d = await pg.evaluate("(P) => { " + VIS + " var c = qa('div.parlay').filter(function(c){ return qa('ul.plegs li b', c).some(function(b){ return b.textContent.trim().indexOf(P) === 0; }); })[0]; if(!c) return null; c.scrollIntoView({block: 'center'}); var ban = c.querySelector('.bsrdead'); return {dead: c.classList.contains('bsr-dead'), ban: ban ? ban.textContent : '', books: qa('.pfoot a.fdb, .pfoot a.dkb, .pfoot a.hrb, .pfoot a.more[href*=\"/build/?\"]', c).filter(vis).length, board: qa('.pfoot a.more', c).filter(vis).length, over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }", pp)
                    check(d and d["dead"] and pp in d["ban"] and d["books"] == 0 and d["board"] == 1 and d["over"] == 0 and not errs, f"Today's ready-made parlay with {pp} ruled out: a banner names him, the book and add-to-slip buttons are gone, the link to the board stays ({(d or {}).get('ban', '')[:64]!r})")
                    await shot(pg, "inactive-parlay"); await ctx.close()
            if not t0["ud"]: skip(f"{label} shows no Under of the day right now")
            else:
                who = t0["ud"]; pg, ctx, errs, _ = await page(path, who); t = await pg.evaluate(TOUT, who)
                check(t["ud"] != who and (t["udSec"] == bool(t["ud"])) and not errs, f"{label}: the Under of the day on {who} is not offered once he is ruled out ({'the next card shows: ' + t['ud'] if t['ud'] else 'the card is gone'})")
                await shot(pg, "inactive-under-" + label.split(" ")[0].lower()); await ctx.close()

        # ---- Model's Best ----
        if os.path.isfile(os.path.join(ROOT, "best", "index.html")):
            pg, ctx, errs, _ = await page("/best/"); t0 = await pg.evaluate(TREAD); await ctx.close()
            if not t0["play"]: skip("Model's Best shows no pick with a FanDuel button right now")
            else:
                pg, ctx, errs, _ = await page("/best/", t0["play"]); t = await pg.evaluate(TOUT, t0["play"]); await ctx.close()
                check(t["plays"] >= 1 and t["playsShown"] == 0 and t["fd"] == 0 and t0["play"] in t["note"] and t["over"] == 0 and not errs, f"Model's Best with {t0['play']} ruled out: his {t['plays']} card{'s' if t['plays'] > 1 else ''} left the page with a note")

        # ---- Boost finder ----
        if os.path.isfile(os.path.join(ROOT, "b", "boost.json")) and os.path.isfile(os.path.join(ROOT, "boost", "index.html")):
            BZ = json.load(open(os.path.join(ROOT, "b", "boost.json"))); by_t = {l["t"]: l for l in BZ.get("legs", [])}
            ZREAD = "() => { " + VIS + " return {cards: qa('#bzout .card').length, legs: qa('#bzout .card ul.legs li b').map(function(b){ return b.textContent; }), none: !!document.querySelector('#bzout .none'), fd: qa('#bzout a.bsbtn').map(function(a){ return a.getAttribute('href'); })}; }"
            NOGL = "() => { var c = document.getElementById('bzgl'); if(c && c.checked){ c.checked = false; c.dispatchEvent(new Event('change', {bubbles: true})); } }"   # player legs only
            pg, ctx, errs, _ = await page("/boost/"); await pg.evaluate(NOGL); await pg.wait_for_timeout(500); z0 = await pg.evaluate(ZREAD); await ctx.close()
            pz = next((by_t[t]["pl"] for t in z0["legs"] if t in by_t and not by_t[t].get("gl")), None)
            if not pz: skip(f"the Boost finder has no player-leg slip right now ({z0['legs'][:3] or 'no slip'})")
            else:
                pg, ctx, errs, _ = await page("/boost/", pz); await pg.evaluate(NOGL); await pg.wait_for_timeout(500); z = await pg.evaluate(ZREAD); await ctx.close()
                his = [t for t in z["legs"] if t in by_t and by_t[t].get("pl") == pz]
                ids = {str(l["fs"]) for l in BZ["legs"] if l.get("pl") == pz}
                check(not his and not any(i in u for u in z["fd"] for i in ids) and (z["cards"] >= 1 or z["none"]) and not errs, f"Boost finder with {pz} ruled out: no slip holds one of his legs and no FanDuel link carries his selection ({z0['legs'][:3]} -> {z['legs'][:3] or 'no slip fits'})")

        # ---- Line shop ----
        if os.path.isfile(os.path.join(ROOT, "shop", "index.html")):
            SREAD = "(P) => { " + VIS + " var rows = qa('.shl li'); return {shown: rows.filter(vis).length, first: (rows.filter(function(e){ return vis(e) && e.getAttribute('data-rk'); })[0] || {getAttribute: function(){ return ''; }}).getAttribute('data-rk').split('|')[0], his: rows.filter(function(e){ return (e.getAttribute('data-rk') || '').split('|')[0] === P; }).length, hisShown: rows.filter(function(e){ return vis(e) && (e.getAttribute('data-rk') || '').split('|')[0] === P; }).length}; }"
            # 11/17: the list shows its first 15 rows with the rest behind "Show all" - open it, so a row leaving is counted and not back-filled
            SALL = "() => { var b = document.getElementById('shmore'); if(b && !b.parentNode.hidden) b.click(); }"
            pg, ctx, errs, _ = await page("/shop/"); await pg.evaluate(SALL); h0 = await pg.evaluate(SREAD, ""); await ctx.close()
            if not h0["first"]: skip("Line shop lists no player leg right now (or the page predates data-rk)")
            else:
                ps = h0["first"]; pg, ctx, errs, _ = await page("/shop/", ps); await pg.evaluate(SALL); h = await pg.evaluate(SREAD, ps); await ctx.close()
                check(h["his"] >= 1 and h["hisShown"] == 0 and h["shown"] == h0["shown"] - h["his"] and not errs, f"Line shop with {ps} ruled out: his {h['his']} row{'s' if h['his'] > 1 else ''} left the list, the other {h['shown']} stay")
        await b.close()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
