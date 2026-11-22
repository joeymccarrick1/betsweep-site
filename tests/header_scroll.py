"""The page header that gets shorter as you scroll must come to rest.

Found 11/22 by the NBA page's test, on a desktop: on every page with the big masthead (Boards, Builder, Live, Trade, the season page...) the header keeps its
place at the top and gets shorter once you scroll down (body.bs-scrolled). The browser answers a change of height above the reader by moving the scroll position
to hold his place, the site's scroll handler read that move as "he scrolled back up" and reopened the header, the browser moved the page again, and so on: sixty
times a second. After a wheel scroll it flickered about ten times; after a jump made by a script (a card opening and scrolling itself into view) it never stopped,
and nothing on the page could be clicked. Phones were not affected (there the title scrolls away and only the chip row sticks).

This test scrolls each of those pages the ways a reader and a script do, on a desktop and on a phone, and counts how many times the header changes:
once per scroll at most, the page still, the header collapsed on the way down and open again on the way up.

Serves SITE (default ./site).   python3 tests/header_scroll.py
"""
import asyncio, os, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("SITE") or os.path.join(HERE, "..", "site")
PORT = 8883
PAGES = ["/boards/", "/build/", "/live/", "/trade/", "/season/", "/nba/"]
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)

WATCH = """(function(){ var last = document.body.classList.contains('bs-scrolled'); window.__flips = 0;
  new MutationObserver(function(){ var now = document.body.classList.contains('bs-scrolled'); if(now !== last){ last = now; window.__flips++; } }).observe(document.body, {attributes: true, attributeFilter: ['class']}); })()"""
STATE = "[window.__flips, Math.round(window.scrollY), document.body.classList.contains('bs-scrolled')]"


async def rest(pg, ms=900):
    """wait, then read the header's state twice a third of a second apart: [flips, y, collapsed, still]"""
    await pg.wait_for_timeout(ms); a = await pg.evaluate(STATE); await pg.wait_for_timeout(330); b = await pg.evaluate(STATE)
    return b + [a == b]


async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    pages = [p for p in PAGES if os.path.exists(os.path.join(ROOT, p.strip("/"), "index.html")) and 'class="top"' in open(os.path.join(ROOT, p.strip("/"), "index.html"), encoding="utf-8", errors="ignore").read()]
    check(len(pages) >= 4, f"pages with the big masthead in this build: {', '.join(pages)}")
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for phone in (False, True):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True) if phone else await b.new_context(viewport={"width": 1280, "height": 900})
            await ctx.route("**/*supabase*/**", lambda r: r.abort()); await ctx.route("**/site.api.espn.com/**", lambda r: r.abort())
            for path in pages:
                T = lambda s: f"[{'phone' if phone else 'desktop'} {path}] {s}"
                pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
                await pg.goto(f"http://127.0.0.1:{PORT}{path}", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
                await pg.evaluate("history.replaceState(null, '', location.pathname); window.scrollTo(0, 0)"); await pg.wait_for_timeout(500)
                await pg.evaluate(WATCH)
                info = await pg.evaluate("(function(){ var t = document.querySelector('.top'), s = t && getComputedStyle(t); return {max: document.documentElement.scrollHeight - innerHeight, sticky: !!s && s.position === 'sticky' && t.getBoundingClientRect().height > 0, h: t ? t.getBoundingClientRect().height : 0}; })()")
                if info["max"] < 700:
                    check(True, T(f"the page is too short to scroll far ({info['max']}px); nothing to test")); await pg.close(); continue
                # ---- down to three places and back up from each, by script
                bad = []
                for y in [v for v in (200, 460, 900) if v <= info["max"] - 120]:
                    await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(500); n0 = (await pg.evaluate(STATE))[0]
                    await pg.evaluate(f"window.scrollTo(0, {y})"); d = await rest(pg)
                    if not (d[0] - n0 == 1 and d[2] and d[3]): bad.append(("down to", y, "changes", d[0] - n0, "collapsed", d[2], "still", d[3]))
                    await pg.evaluate(f"window.scrollTo(0, {max(90, d[1] - 60)})"); u = await rest(pg)
                    if not (u[0] - d[0] == 1 and not u[2] and u[3]): bad.append(("up from", d[1], "changes", u[0] - d[0], "collapsed", u[2], "still", u[3]))
                check(not bad, T("scrolled down to 200, 460 and 900 and a little back up from each: the header collapses once on the way down, opens once on the way up, and the page comes to rest") + (f" {bad[:3]}" if bad else ""))
                # ---- the header itself, where it sticks (a desktop): shorter when collapsed, still at the top
                if info["sticky"]:
                    await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(500); await pg.evaluate("window.scrollTo(0, 460)"); await rest(pg, 600)
                    h = await pg.evaluate("(function(){ var r = document.querySelector('.top').getBoundingClientRect(); return [r.height, r.top]; })()")
                    check(h[0] < info["h"] - 20 and -1 <= h[1] <= 80, T(f"the collapsed header is shorter ({info['h']:.0f}px to {h[0]:.0f}px) and still at the top"))
                # ---- a mouse wheel, as a reader does it
                if not phone:
                    await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(500); n0 = (await pg.evaluate(STATE))[0]
                    await pg.mouse.move(640, 520)
                    for _ in range(3): await pg.mouse.wheel(0, 100); await pg.wait_for_timeout(120)
                    w = await rest(pg, 1300)
                    check(w[0] - n0 == 1 and w[2] and w[3], T(f"three notches of a mouse wheel: the header collapses once ({w[0] - n0} change{'s' if w[0] - n0 != 1 else ''}) and stays"))
                # ---- an element that scrolls itself into view (what an opened card does), from above and from below
                pick = """(function(){ var max = document.documentElement.scrollHeight - innerHeight, want = max * 0.5, best = null, bd = 1e9;
                  document.querySelectorAll('.card, .gcard, section, article, h2, h3, li').forEach(function(e){ var r = e.getBoundingClientRect(); if(!r.height) return; var t = r.top + scrollY, d = Math.abs(t - want); if(t > 320 && t < max - 200 && d < bd){ bd = d; best = e; } });
                  window.__el = best; return !!best; })()"""
                await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(500)
                if await pg.evaluate(pick):
                    n0 = (await pg.evaluate(STATE))[0]; await pg.evaluate("window.__el.scrollIntoView({block: 'start'})"); a = await rest(pg)
                    await pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)"); await rest(pg, 500); n1 = (await pg.evaluate(STATE))[0]
                    await pg.evaluate("window.__el.scrollIntoView({block: 'start'})"); c = await rest(pg)
                    check(a[0] - n0 <= 1 and a[3] and c[0] - n1 <= 1 and c[3], T(f"something that scrolls itself into view, from above and from below: the page comes to rest both times (header changes {a[0] - n0} and {c[0] - n1})"))
                else:
                    check(True, T("nothing far enough down the page to jump to"))
                check(not errs, T(f"no script errors {errs[:2]}"))
                await pg.close()
            await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
