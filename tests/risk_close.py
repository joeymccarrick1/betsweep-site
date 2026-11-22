"""The "leg in your betslip is at risk" box goes away when Close is tapped (owner 11/21: "When I press close, it's not closing"; 11/22:
"still won't close"). Two faults, in the order they were found: the box redrew itself on every page mutation, so a tap that landed
mid-redraw was lost; and Close only folded the list, leaving the bar on the screen. Close and the x on the bar now remove the box, and
it stays away on every page until the warning changes. Stand-in risk feed.   python3 tests/risk_close.py [shots_dir]"""
import asyncio, json, os, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8869
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
FEED = [{"id": 1, "kind": "weather", "week": 11, "player": None, "team": None, "gid": "TEN-DAL", "status": "wind", "level": "warn", "detail": "Wind 20 mph at kickoff", "players": ["Test Player", "Other Player"], "updated_at": "2026-11-21T18:00:00Z"}]
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ONE = "['Test Player|Passing Yards|200']"; TWO = "['Test Player|Passing Yards|200','Other Player|Receiving Yards|50']"
HERE_ = "(function(){ var e = document.getElementById('bsrpill'); return !!e && e.getClientRects().length > 0; })()"
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        await ctx.add_init_script("try{ if(!localStorage.getItem('__t')){ localStorage.setItem('__t', '1'); localStorage.setItem('bs_slipk_w11', JSON.stringify(" + ONE + ")); } }catch(e){}")
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
        xb = await pg.evaluate("(function(){ var b = document.querySelector('#bsrpill .bsrh .bsrx'); if(!b) return null; var r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), b.getAttribute('aria-label')]; })()")
        check(bool(xb) and xb[0] >= 44 and xb[1] >= 44 and "Close" in xb[2], f"the bar itself carries an x to close it, a 44px target ({xb})")
        if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, "risk_open.png"))
        # ---- Close takes the whole box away (11/22: it used to fold the list and leave the bar on the screen)
        await pg.wait_for_timeout(900); await pg.tap("#bsrpill .bsrb button[data-act=x]"); await pg.wait_for_timeout(400)
        gone = not await pg.evaluate(HERE_)
        await pg.evaluate("var i = 0, t = setInterval(function(){ var d = document.createElement('i'); document.body.appendChild(d); d.remove(); if(++i > 6) clearInterval(t); }, 150)"); await pg.wait_for_timeout(1400)
        check(gone and not await pg.evaluate(HERE_), "Close takes the whole box off the screen, and it is still gone after the page has been busy for a second")
        if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, "risk_closed.png"))
        await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_timeout(1800); r1 = await pg.evaluate(HERE_)
        await pg.goto(f"http://127.0.0.1:{PORT}/build/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1800); r2 = await pg.evaluate(HERE_)
        chips = await pg.evaluate("window.BSRisk && !!window.BSRisk.verdict('Test Player', 'Passing Yards')")
        check(not r1 and not r2 and chips, "it stays away after a reload and on another page, while the leg is still flagged where it is listed")
        # ---- a new warning brings it back
        await pg.evaluate("localStorage.setItem('bs_slipk_w11', JSON.stringify(" + TWO + "))"); await pg.reload(wait_until="domcontentloaded")
        try: await pg.wait_for_selector("#bsrpill", timeout=6000); back = await pg.inner_text("#bsrpill .bsrh span")
        except Exception: back = ""
        check("2 legs in your betslip are at risk" in back, f"another leg at risk brings the box back ({back.strip()})")
        await pg.tap("#bsrpill .bsrh .bsrx"); await pg.wait_for_timeout(400); x1 = await pg.evaluate(HERE_)
        await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
        check(not x1 and not await pg.evaluate(HERE_), "the x on the bar closes it in one tap, without opening the list first")
        # ---- a slip with nothing at risk forgets the close, so the next warning shows
        await pg.evaluate("localStorage.setItem('bs_slipk_w11', '[]')"); await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
        forgot = await pg.evaluate("localStorage.getItem('bs_risk_closed')")
        await pg.evaluate("localStorage.setItem('bs_slipk_w11', JSON.stringify(" + TWO + "))"); await pg.reload(wait_until="domcontentloaded")
        try: await pg.wait_for_selector("#bsrpill", timeout=6000); again = True
        except Exception: again = False
        check(not forgot and again, "once nothing in the slip is at risk the close is forgotten, and the same legs coming back at risk are shown again")
        # ---- Remove ruled-out legs still works from the open box (a block-level row)
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
