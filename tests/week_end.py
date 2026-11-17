"""Pages do not offer bets on games that have kicked off (11/17, found on a finished week).

Before: First TD listed finished games' players under "Most likely to score first" and "Best edges vs FanDuel" all week, with working
"add to slip" links; Today and Model's Best kept a finished game's "Best parlay" with its "Add all to FanDuel" button; the Daily Sweep
record read "1-0" above a slip marked Missed, with two more waiting for Tuesday's grade.

The page clock is set around the week's own kickoffs (read from the built First TD page), so this runs in any week. ESPN and the account
service are cut off - the clock alone has to be enough.
  python3 tests/week_end.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, os, re, sys, threading
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8865; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
FT = open(os.path.join(ROOT, "firsttd", "index.html")).read()
KOS = sorted({int(k) for k in re.findall(r'<section class="ftd" id="ftd-[A-Z-]+" data-ko="(\d+)"', FT)})
CLOCK = "(function(){var T=+(localStorage.getItem('t_now')||0);if(!T)return;var R=Date.now,S=R();Date.now=function(){return T+(R()-S)};var D0=Date;function ND(){if(arguments.length===0)return new D0(D0.now());return new (Function.prototype.bind.apply(D0,[null].concat([].slice.call(arguments))))()}ND.now=D0.now;ND.parse=D0.parse;ND.UTC=D0.UTC;ND.prototype=D0.prototype;window.Date=ND;})();"
FTREAD = """() => { var qa = function(s, r){ return Array.from((r || document).querySelectorAll(s)); }, vis = function(e){ var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  var lists = qa('.ftdwrap .strips ul').map(function(ul){ return {rows: qa('li[data-ko]', ul).filter(vis).length, started: qa('li[data-ko]', ul).filter(vis).filter(function(li){ return Date.now() >= +li.getAttribute('data-ko'); }).length, note: (ul.querySelector('li.alldone') || {textContent: ''}).textContent, fd: qa('a.fdgo', ul).filter(vis).length}; });
  var secs = qa('section.ftd'), st = secs.filter(function(s){ return s.classList.contains('started'); });
  return {lists: lists, games: secs.length, started: st.length, fdStarted: st.reduce(function(a, s){ return a + qa('a.fdgo', s).filter(vis).length; }, 0), fdOpen: secs.filter(function(s){ return !s.classList.contains('started'); }).reduce(function(a, s){ return a + qa('a.fdgo', s).filter(vis).length; }, 0),
          chips: qa('nav.nav a[href^="#ftd-"]').filter(function(a){ return a.classList.contains('played'); }).length, over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""

async def main():
    if len(KOS) < 1: check(False, "the First TD page carries each game's kickoff time (data-ko on its game sections)"); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1)
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def page(path, t, theme="dark", nofin=False):
            """nofin: serve the page with the finals taken out of its own game list - a build made after the week carries them, and a final beats the clock"""
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
            if nofin:
                src = re.sub(r'"fin":\s*"[^"]*"', '"fin":""', open(os.path.join(ROOT, path.strip("/"), "index.html")).read())
                async def doc(route, request): await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=src)
                await ctx.route(f"**{path}", doc)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}');localStorage.setItem('t_now','{int(t)}');}}catch(e){{}}" + CLOCK)
            await ctx.route("**/*espn.com/**", lambda r: r.abort()); await ctx.route("**/*supabase*/**", lambda r: r.abort()); await ctx.route("**/raw.githubusercontent.com/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}{path}", wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            return pg, ctx, errs
        first, last = KOS[0], KOS[-1]; ngames = len(re.findall(r'<section class="ftd" id=', FT))
        # ---- First TD ----
        for theme in ("dark", "light"):
            pg, ctx, errs = await page("/firsttd/", first - 26 * 3600e3, theme); s = await pg.evaluate(FTREAD); await ctx.close()
            print(f"   [{theme}] First TD before the week:", json.dumps(s)[:330])
            check(s["started"] == 0 and s["chips"] == 0 and s["lists"][0]["rows"] == 12 and not s["lists"][0]["note"] and s["over"] == 0 and not errs, f"[{theme}] before the first kickoff nothing is marked, the first list shows 12 players, no sideways scroll, no errors")
            if len(KOS) > 1:
                pg, ctx, errs = await page("/firsttd/", first + 60 * 60e3, theme); s = await pg.evaluate(FTREAD)
                n1 = len([k for k in re.findall(r'<section class="ftd" id="ftd-[A-Z-]+" data-ko="(\d+)"', FT) if int(k) <= first + 3600e3])
                print(f"   [{theme}] First TD an hour into the first game:", json.dumps(s)[:330])
                check(s["started"] == n1 and s["chips"] == n1 and s["fdStarted"] == 0, f"[{theme}] the game that has kicked off is marked, its chip is dimmed, and it shows no FanDuel button ({s['started']} of {s['games']} games)")
                check(all(l["started"] == 0 for l in s["lists"]) and s["lists"][0]["rows"] == 12, f"[{theme}] its players have left both lists and the next ones moved up ({[l['rows'] for l in s['lists']]} rows shown, none from a game in play)")
                if SHOTS: await pg.screenshot(path=f"{SHOTS}/firsttd-mid-{theme}.png")
                await ctx.close()
            pg, ctx, errs = await page("/firsttd/", last + 6 * 3600e3, theme); s = await pg.evaluate(FTREAD)
            print(f"   [{theme}] First TD after the last game:", json.dumps(s)[:330])
            check(s["started"] == s["games"] == ngames and s["fdStarted"] == 0 and s["fdOpen"] == 0 and all(l["fd"] == 0 and l["rows"] == 0 for l in s["lists"]), f"[{theme}] after the last kickoff no FanDuel button is left anywhere on the page (was 31 on 11/17)")
            check(all("kicked off" in l["note"] for l in s["lists"] if True) and s["over"] == 0 and not errs, f"[{theme}] both lists say every game has kicked off ({s['lists'][0]['note'][:44]!r})")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/firsttd-done-{theme}.png")
            await ctx.close()
        # ---- Best parlay on Today and on Model's Best ----
        PREAD = """() => { var p = document.getElementById('parlay'), vis = function(e){ var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
          return p ? {there: true, shown: vis(p), cards: Array.from(p.querySelectorAll('.parlay,.pmini')).filter(vis).length, fd: Array.from(p.querySelectorAll('a[href*="fanduel.com"]')).filter(vis).length, note: (p.querySelector('.pdone') || {textContent: ''}).textContent, ko: +((p.querySelector('.parlay') || {getAttribute: function(){ return 0; }}).getAttribute('data-ko')) || 0} : {there: false}; }"""
        pg, ctx, errs = await page("/", first - 26 * 3600e3); s = await pg.evaluate(PREAD); await ctx.close()
        if not s["there"] or not s["ko"]: print("   (no lead parlay on the built Today page; its checks are skipped)")
        else:
            pg, ctx, errs = await page("/", s["ko"] - 2 * 3600e3); a = await pg.evaluate(PREAD); await ctx.close()
            pg, ctx, errs = await page("/", s["ko"] + 10 * 60e3); z = await pg.evaluate(PREAD); await ctx.close()
            check(a["shown"] and a["cards"] >= 1 and not z["shown"] and z["fd"] == 0 and not errs, f"Today shows its lead parlay before that game kicks off and drops it once it has (before: {a['cards']} card, {a['fd']} FanDuel link; after: shown {z['shown']})")
        pg, ctx, errs = await page("/best/", first - 26 * 3600e3, nofin=True); a = await pg.evaluate(PREAD); await ctx.close()
        pg, ctx, errs = await page("/best/", last + 6 * 3600e3); z = await pg.evaluate(PREAD)
        if not a["there"]: print("   (no Best parlay section on the built Model's Best page; its checks are skipped)")
        else:
            check(a["cards"] >= 1 and not a["note"], f"Model's Best lists the parlays before the week ({a['cards']} cards)")
            check(z["cards"] == 0 and z["fd"] == 0 and "kicked off" in z["note"] and "Tuesday" in z["note"] and not errs, f"after the last kickoff it shows one line instead of bets nobody can place ({z['note'][:60]!r})")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/best-done-dark.png")
        await ctx.close()
        # ---- Today: what it says when the week is over, and the Daily Sweep record ----
        pg, ctx, errs = await page("/", last + 12 * 3600e3)
        t = await pg.evaluate("""() => ({title: document.getElementById('tdtitle').textContent, sub: document.getElementById('tdsub').textContent, none: (document.getElementById('tdnone') || {textContent: ''}).textContent, rec: (document.querySelector('.swrec') || {textContent: ''}).textContent})"""); await ctx.close()
        print("   Today after the week:", json.dumps(t)[:420])
        check("in the books" in t["title"] and "Tuesday" in t["sub"] and "Thursday morning" not in t["sub"] and "Thursday morning" not in t["none"], f"Today says next week's board posts Tuesday, as the short page does (was 'Thursday morning'): {t['sub']!r}")
        short = open(os.path.join(ROOT, "short", "index.html")).read()
        check("land Tuesday" in short, "the short page still says Tuesday (the two pages agree)")
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
            import sweep as SW
            R = SW.record(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "in", "promos.json")))["values"])
        except Exception as e: R = None; print("   (promos tab not readable here, the record check is skipped:", str(e)[:80], ")")
        if R and R["n"] and R["pending"] and not os.environ.get("SITE"):
            check(f"{R['w']}–{R['l']}" in t["rec"] and f"{R['pending']} to grade Tuesday" in t["rec"], f"the Daily Sweep record names the slips still to be graded ({t['rec']!r}; the tab has {R['pending']} ungraded)")
        elif R and not os.environ.get("SITE"): print(f"   (the promos tab has no ungraded Sweep beside a graded one right now - record line is {t['rec']!r}; that check is skipped)")
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
