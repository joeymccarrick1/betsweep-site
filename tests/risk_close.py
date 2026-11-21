"""The "leg in your betslip is at risk" box closes when Close is tapped (owner 11/21: "When I press close, it's not closing"). The box
used to redraw itself on every page mutation, its own redraw included, so a tap that landed mid-redraw was lost. Stand-in risk feed.
python3 tests/risk_close.py"""
import asyncio, json, os, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8869
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
FEED = [{"id": 1, "kind": "weather", "week": 11, "player": None, "team": None, "gid": "TEN-DAL", "status": "wind", "level": "warn", "detail": "Wind 20 mph at kickoff", "players": ["Test Player"], "updated_at": "2026-11-21T18:00:00Z"}]
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        await ctx.add_init_script("try{ localStorage.setItem('bs_slipk_w11', JSON.stringify(['Test Player|Passing Yards|200'])); }catch(e){}")
        async def rt(route, request):
            u = request.url
            if "127.0.0.1" in u: return await route.continue_()
            if "risk_feed" in u: return await route.fulfill(status=200, content_type="application/json", body=json.dumps(FEED))
            await route.abort()
        await ctx.route("**/*", rt); pg = await ctx.new_page()
        await pg.goto(f"http://127.0.0.1:{PORT}/boards/", wait_until="domcontentloaded"); await pg.wait_for_selector("#bsrpill", timeout=8000)
        await pg.evaluate("window.__n = 0; new MutationObserver(function(){ window.__n++; }).observe(document.getElementById('bsrpill'), {childList: true})")
        # other things on the page keep changing; the box must not answer each one by replacing itself
        await pg.evaluate("var i = 0, t = setInterval(function(){ var d = document.createElement('i'); document.body.appendChild(d); d.remove(); if(++i > 10) clearInterval(t); }, 150)")
        await pg.wait_for_timeout(2600); n = await pg.evaluate("window.__n")
        check(n == 0, f"the box is not redrawn while nothing about it has changed ({n} redraws in 2.6 seconds of page activity)")
        await pg.tap("#bsrpill .bsrh"); await pg.wait_for_timeout(300); opened = await pg.evaluate("document.getElementById('bsrpill').classList.contains('open')")
        vis = await pg.evaluate("(function(){ var b = document.querySelector('#bsrpill button[data-act=x]'); return !!b && b.getClientRects().length > 0 && b.getBoundingClientRect().height >= 40; })()")
        dbg = await pg.evaluate("(function(){ var e = document.getElementById('bsrpill'), b = e.querySelector('button[data-act=x]'), r = b.getBoundingClientRect(), p = e.getBoundingClientRect(); return [e.className, Math.round(r.height), Math.round(r.top), Math.round(p.top), Math.round(p.bottom), innerHeight, getComputedStyle(e).position]; })()")
        check(opened and vis and "Test Player" in await pg.inner_text("#bsrpill"), f"a tap opens it: the leg, the reason and a Close button 40px or taller ({dbg})")
        await pg.wait_for_timeout(900); await pg.tap("#bsrpill button[data-act=x]"); await pg.wait_for_timeout(1200)
        closed = await pg.evaluate("(function(){ var e = document.getElementById('bsrpill'), b = e.querySelector('button[data-act=x]'); return !e.classList.contains('open') && !(b && b.getClientRects().length > 0); })()")
        check(closed, "Close closes it, and it stays closed a second later")
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
