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
        allc, _ = await at(0); cards = [c for c in allc if c["t"] is not None and c["f"]]
        # 11/22: a slip with a status label and no kickoff time can never leave "Pregame". build_promo.py used to lose the kickoff of every leg
        # FanDuel had taken off its board (tests/promo_kickoff.py); this is the same rule seen from the page.
        nok = [c for c in allc if c["t"] is not None and not c["f"]]
        check(not nok, f"every ungraded posted slip on the page carries its kickoff times ({len(allc) - len(nok)} of {len(allc)})")
        if not cards: print(f"no ungraded posted slip with a kickoff on the built Today page - nothing more to check ({ok[0]} passed, {ok[1]} failed)"); await b.close(); srv.shutdown(); sys.exit(1 if ok[1] else 0)
        f, l = min(c["f"] for c in cards), max(c["l"] for c in cards)
        pre, e1 = await at(f - 3600e3); live, e2 = await at(f + 600e3); late, e3 = await at(l + 5 * 3600e3)
        pre, live, late = [[c for c in x if c["t"] is not None] for x in (pre, live, late)]
        # The label only ever moves forward, and each card starts from the label its own HTML was built with: a slip whose first game had
        # kicked off when the page was built already says In play. So an hour before the first kickoff every card must still say exactly
        # what it was built saying - Pregame for the slips not yet started (11/22: this used to be all-or-nothing, and failed on a Sunday
        # afternoon page that carried slips in play beside a Sunday-night slip).
        import re as _re
        built = _re.findall(r'data-role="pst">([^<]*)<', open(os.path.join(ROOT, "index.html"), encoding="utf-8").read())
        built = [x.replace("&middot;", "\u00b7") for x in built]
        check(len(built) == len(pre) and all(c["t"] == b_ for c, b_ in zip(pre, built)), f"an hour before the first kickoff every slip says what its page was built saying - Pregame unless its game had started ({[c['t'] for c in pre]} built {built})")
        check(all(c["t"] == "In play" and "live" in c["cls"] for c in live if c["f"] <= f + 600e3) and any(c["t"] == "In play" for c in live), f"ten minutes after kickoff, with no scores loading, it says In play ({[c['t'] for c in live]})")
        kept = [c for c in late if c["keep"]]
        check(all(c["t"] == "Final · grading" and "live" not in c["cls"] for c in late if not c["hidden"]) and not any(c["t"] == "Pregame" for c in late), f"five hours after the last kickoff nothing says Pregame or In play: it is final and waiting to be graded ({[(c['t'], 'hidden' if c['hidden'] else 'shown') for c in late]})")
        check(not (e1 or e2 or e3), f"no script errors {(e1 + e2 + e3)[:2]}")
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
