"""A tap on the Live page shows at once on a phone (11/28).

The page holds a redraw back for a second after any touch or scroll, so that a score update never lands under a moving finger (on an
iPhone that kills the scroll). But the touch that makes a TAP set that same hold, so opening a game, the Settled fold, a slip or a star
took a full second to show on a phone, while a mouse click showed at once. Every Live test clicked, so none of them saw it. This one
taps the way a phone does and times the page from the click to the change, inside the page:
  - a game opens and shuts, a hub tab opens, a saved slip's own row opens: each within a quarter of a second of the tap;
  - and the hold is still there for what it is for: an update that arrives while a finger is moving waits, then lands.

Runs in any week on the page as built (no clock, no made-up scores); the network is cut off.
  python3 tests/live_tap.py        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, os, sys, threading
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
PORT = 8911; ok = [0, 0]; LIMIT = 250
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
# arm a stopwatch in the page: the time of the next click, and the time the element's state then changes (the page swaps nodes, so look it up each time)
ARM = """(a) => { var sel = a[0], attr = a[1], q = function(){ return document.querySelector(sel); }, was = q() ? (attr === 'class' ? q().className : q().getAttribute(attr)) : null, T = window.__tap = {c: 0, f: 0, was: was};
  var on = function(){ T.c = performance.now(); window.removeEventListener('click', on, true); }; window.addEventListener('click', on, true);
  var n = 0, t = setInterval(function(){ var e = q(), v = e ? (attr === 'class' ? e.className : e.getAttribute(attr)) : null; if(T.c && v !== was){ T.f = performance.now(); T.now = v; clearInterval(t); } if(++n > 400) clearInterval(t); }, 6); }"""

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); srv.handle_error = lambda *a: None; threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def open_(slips=None):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
            async def gate(route, request): await (route.continue_() if "127.0.0.1" in request.url else route.abort())
            await ctx.route("**/*", gate)
            if slips: await ctx.add_init_script("try{ if(!sessionStorage.getItem('seeded')){ sessionStorage.setItem('seeded','1'); var s = " + json.dumps(slips) + "; Object.keys(s).forEach(function(k){ localStorage.setItem(k, s[k]); }); } }catch(e){}")
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/live/", wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
            return pg, ctx, errs
        async def tap(pg, sel, attr="aria-expanded"):
            """a real touch tap on `sel`; returns (milliseconds from the click to the change, or None if it never changed; the state before; after)"""
            await pg.evaluate(ARM, [sel, attr]); await pg.tap(sel)
            for _ in range(60):
                t = await pg.evaluate("window.__tap")
                if t["f"]: return t["f"] - t["c"], t["was"], t.get("now")
                await pg.wait_for_timeout(50)
            t = await pg.evaluate("window.__tap"); return None, t["was"], None
        say = lambda ms: "never" if ms is None else f"{ms:.0f} ms"

        pg, ctx, errs = await open_()
        wk = await pg.evaluate("window.__LV.week"); gids = await pg.evaluate("Array.from(document.querySelectorAll('#lv .ghd2:not(.static)')).map(function(h){ return h.dataset.g; }).filter(function(g){ return g && g.indexOf('__') !== 0; })")
        if not gids:
            check(True, "no game on the Live page to tap right now: nothing to time"); print(f"{ok[0]} passed, {ok[1]} failed"); await b.close(); return
        sel = f'#lv .ghd2[data-g="{gids[0]}"]'
        ms, was, now = await tap(pg, sel)
        check(ms is not None and ms < LIMIT and was != now, f"a tap on a game opens it at once ({say(ms)} from the tap to the open game; limit {LIMIT})")
        await pg.wait_for_timeout(400); ms, was, now = await tap(pg, sel)
        check(ms is not None and ms < LIMIT and was != now, f"and a second tap shuts it at once ({say(ms)})")
        if len(gids) > 1:
            await pg.wait_for_timeout(1200); ms, was, now = await tap(pg, f'#lv .ghd2[data-g="{gids[-1]}"]')
            check(ms is not None and ms < LIMIT, f"the same for a game far down the page, which the tap first scrolls to ({say(ms)})")
        check(not errs, f"no page errors while tapping ({errs[:1]})")
        # ---- the hold is still there for what it is for: an update that arrives while a finger is moving waits, then lands ----
        ks = await pg.evaluate("window.__LV.legs.filter(function(l){ return !l.gl; }).slice(0, 2).map(function(l){ return l.pl + '|' + l.m + '|' + Math.floor((l.ln || 1) + 0.5); })")
        slips = json.dumps([{"id": "s1", "name": "Test slip", "keys": ks, "odds": 250, "stake": 5}])
        had = await pg.evaluate("document.querySelectorAll('.hubb[data-hub=\"__slips\"]').length")
        await pg.evaluate("(a) => { window.dispatchEvent(new Event('touchmove')); localStorage.setItem('bs_slips_w' + a[0], a[1]); document.dispatchEvent(new Event('visibilitychange')); }", [wk, slips])
        await pg.wait_for_timeout(350); mid = await pg.evaluate("document.querySelectorAll('.hubb[data-hub=\"__slips\"]').length")
        await pg.wait_for_timeout(1500); end = await pg.evaluate("document.querySelectorAll('.hubb[data-hub=\"__slips\"]').length")
        check(had == 0 and mid == 0 and end == 1, f"an update that arrives under a moving finger is still held back, then lands (the new slip's tab: {had} before, {mid} a third of a second in, {end} after the hold)")
        await ctx.close()
        # ---- with a saved slip: its tab, and the slip's own row ----
        pg, ctx, errs = await open_({f"bs_slips_w{wk}": slips})
        if await pg.evaluate("!!document.querySelector('.hubb[data-hub=\"__slips\"]')"):
            ms, was, now = await tap(pg, '.hubb[data-hub="__slips"]', "class")
            check(ms is not None and ms < LIMIT, f"a tap on the Your slips tab opens it at once ({say(ms)})")
            await pg.wait_for_timeout(500)
            if await pg.evaluate("!!document.querySelector('.sliptog[data-sid=\"s1\"]')"):
                ms, was, now = await tap(pg, '.sliptog[data-sid="s1"]')
                check(ms is not None and ms < LIMIT and was != now, f"and a tap on the slip's own row opens it at once ({say(ms)}; {was} -> {now})")
        check(not errs, f"no page errors with a saved slip ({errs[:1]})")
        await ctx.close(); await b.close()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
