"""A posted slip's status label follows the clock even when live scores never load (11/16 late). Serves ./site with the score feed blocked
and the page clock set around the slip's own kickoff times (read from the page), so it works for whatever slips the build carries.
  python3 tests/promo_clock.py"""
import asyncio, json, os, sys, threading, http.server, functools
from playwright.async_api import async_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
READ = """() => Array.from(document.querySelectorAll('.promo[data-first-ko]')).map(function(c){ var st = c.querySelector('[data-role=pst]'); return {f: +c.dataset.firstKo, l: +c.dataset.lastKo || +c.dataset.firstKo, keep: !!c.dataset.keep, hidden: c.hidden || c.offsetParent === null, t: st ? st.textContent : null, cls: st ? st.className : null}; })"""
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8871), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def at(t):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
            if t: await ctx.add_init_script("Date.now = function(){ return %d; };" % t)
            await ctx.route("**/*espn.com/**", lambda r: r.abort()); await ctx.route("**/*supabase*/**", lambda r: r.abort())      # no live scores at all
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
            await pg.goto("http://127.0.0.1:8871/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1800); r = await pg.evaluate(READ); await ctx.close(); return r, errs
        cards, _ = await at(0); cards = [c for c in cards if c["t"] is not None and c["f"]]
        if not cards: print("no ungraded posted slip on the built Today page - nothing to check (0 passed, 0 failed)"); await b.close(); srv.shutdown(); return
        f, l = min(c["f"] for c in cards), max(c["l"] for c in cards)
        pre, e1 = await at(f - 3600e3); live, e2 = await at(f + 600e3); late, e3 = await at(l + 5 * 3600e3)
        pre, live, late = [[c for c in x if c["t"] is not None] for x in (pre, live, late)]
        # a page BUILT after kickoff already says In play in its HTML (the label only ever moves forward), so "Pregame" is only checked for a page built before it
        built_pre = 'data-role="pst">Pregame<' in open(os.path.join(ROOT, "index.html")).read()
        if built_pre: check(all(c["t"] == "Pregame" and "live" not in c["cls"] for c in pre), f"an hour before the first kickoff every slip says Pregame ({[c['t'] for c in pre]})")
        else: check(all(c["t"] != "Pregame" for c in pre), f"this page was built after kickoff, so its own HTML already says the game is on ({[c['t'] for c in pre]}) - the Pregame check is for a page built before kickoff")
        check(all(c["t"] == "In play" and "live" in c["cls"] for c in live if c["f"] <= f + 600e3) and any(c["t"] == "In play" for c in live), f"ten minutes after kickoff, with no scores loading, it says In play ({[c['t'] for c in live]})")
        kept = [c for c in late if c["keep"]]
        check(all(c["t"] == "Final · grading" and "live" not in c["cls"] for c in late if not c["hidden"]) and not any(c["t"] == "Pregame" for c in late), f"five hours after the last kickoff nothing says Pregame or In play: it is final and waiting to be graded ({[(c['t'], 'hidden' if c['hidden'] else 'shown') for c in late]})")
        check(not (e1 or e2 or e3), f"no script errors {(e1 + e2 + e3)[:2]}")
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
