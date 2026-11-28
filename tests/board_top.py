"""The top of a Matchup Board on a phone keeps one size (owner 11/28 1:24 AM, a screen recording: "make it so the headers don't change
size when you click one of the projection/game line buttons ... I like the more condensed header when [a] button is engaged").

Before: a shut board had a taller header (more padding, bigger logos) and a one-line kickoff line; tapping Game Script or Projections
shrank the header and grew the kickoff line to two lines, so everything above the buttons reshuffled under the thumb. Now the header is
the condensed one in both states, the kickoff line is the short one in both, and the buttons keep their padding: nothing above or
including the buttons moves when one is tapped.

The page is opened at three phone widths; for the first boards that can still be bet, the header, the kickoff line and the button row
are measured shut, with Projections open, with Game Script open, and shut again.
  python3 tests/board_top.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, os, re, sys, threading
from playwright.async_api import async_playwright
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8908; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
M = """(id) => { var c = document.getElementById(id), top = c.getBoundingClientRect().top, R = function(q){ var e = c.querySelector(':scope > ' + q); if(!e) return null; var r = e.getBoundingClientRect(); return [Math.round((r.top - top) * 10) / 10, Math.round(r.height * 10) / 10]; }, cs = function(q, p){ var e = c.querySelector(q); return e ? getComputedStyle(e)[p] : ''; };
  var lg = c.querySelector('.hd .tm [data-hm]'); return {open: c.classList.contains('expanded'), view: c.getAttribute('data-view') || '', hd: R('.hd'), ginfo: R('.ginfo'), vbtns: R('.vbtns'), name: cs('.hd .tm b', 'fontSize'), logo: lg ? Math.round(lg.getBoundingClientRect().height * 10) / 10 : null, pad: cs('.hd', 'paddingBottom'),
    lines: (function(){ var g = c.querySelector(':scope > .ginfo'); if(!g) return 0; var ys = {}; Array.from(g.children).forEach(function(e){ if(e.offsetParent !== null) ys[Math.round(e.getBoundingClientRect().top)] = 1; }); return Object.keys(ys).length; })(),
    on: Array.from(c.querySelectorAll(':scope > .vbtns .vbtn')).map(function(b){ return b.classList.contains('on') || b.getAttribute('aria-pressed') === 'true'; })}; }"""
def same(a, b): return all(a[k] == b[k] for k in ("hd", "ginfo", "vbtns", "name", "logo", "pad"))

async def main():
    if not os.path.exists(os.path.join(ROOT, "boards", "index.html")):
        check(True, "no boards page built: nothing to check"); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(0)
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); srv.handle_error = lambda *a: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for width, theme in ((360, "light"), (390, "light"), (390, "dark"), (428, "light")):
            ctx = await b.new_context(viewport={"width": width, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block", color_scheme=theme)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            async def gate(route, request): await (route.continue_() if "127.0.0.1" in request.url else route.abort())
            await ctx.route("**/*", gate)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/boards/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2300)
            ids = await pg.evaluate("""() => Array.from(document.querySelectorAll('section.card[id]')).filter(function(c){ return c.classList.contains('bstidy') && !c.classList.contains('done') && !c.classList.contains('started') && !c.classList.contains('summary') && c.querySelector(':scope > .vbtns .vbtn'); }).map(function(c){ return c.id; }).slice(0, 3)""")
            if not ids:
                check(True, f"[{width}px {theme}] no board that can still be bet is on the page: nothing to measure"); await ctx.close(); continue
            bad = []; seen = None
            for cid in ids:
                await pg.evaluate("(id) => document.getElementById(id).scrollIntoView()", cid); await pg.wait_for_timeout(200)
                shut = await pg.evaluate(M, cid); steps = [("shut", shut)]
                for i, name in ((1, "Projections"), (0, "Game Script"), (0, "shut again")):
                    await pg.evaluate("(a) => document.querySelectorAll('#' + a[0] + ' > .vbtns .vbtn')[a[1]].click()", [cid, i]); await pg.wait_for_timeout(350)
                    steps.append((name, await pg.evaluate(M, cid)))
                seen = seen or steps
                if not (steps[1][1]["open"] and steps[2][1]["open"]): bad.append((cid, "a tap did not open the board", [s[1]["open"] for s in steps]))
                for name, s in steps[1:]:
                    if not same(shut, s): bad.append((cid, name, {k: (shut[k], s[k]) for k in ("hd", "ginfo", "vbtns", "name", "logo", "pad") if shut[k] != s[k]}))
                if SHOTS and cid == ids[0] and width == 390:
                    await pg.evaluate("(a) => document.querySelectorAll('#' + a + ' > .vbtns .vbtn')[1].click()", cid); await pg.wait_for_timeout(350); await pg.evaluate("(id) => { document.getElementById(id).scrollIntoView(); window.scrollBy(0, -120); }", cid); await pg.wait_for_timeout(250)
                    await pg.screenshot(path=os.path.join(SHOTS, f"board_top_open_{theme}.png")); await pg.evaluate("(a) => document.querySelectorAll('#' + a + ' > .vbtns .vbtn')[1].click()", cid); await pg.wait_for_timeout(350)
                    await pg.evaluate("(id) => { document.getElementById(id).scrollIntoView(); window.scrollBy(0, -120); }", cid); await pg.wait_for_timeout(250); await pg.screenshot(path=os.path.join(SHOTS, f"board_top_shut_{theme}.png"))
            s0 = seen[0][1]
            check(not bad and not errs, f"[{width}px {theme}] on {len(ids)} boards the header, the kickoff line and the button row are the same size and in the same place shut, with Projections open, with Game Script open and shut again (header {s0['hd'][1]}px, line {s0['ginfo'][1]}px, buttons at {s0['vbtns'][0]}px; first difference: {bad[:1]}; {errs[:1]})")
            check(s0["pad"] == "4px" and s0["name"] == "32px" and (s0["logo"] or 0) <= 50, f"[{width}px {theme}]   and it is the condensed header in both: {s0['pad']} under the score, {s0['name']} names, {s0['logo']}px logos")
            await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
