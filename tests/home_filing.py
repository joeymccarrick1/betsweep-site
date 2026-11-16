"""Home page (11/16): a promo that loses a leg moves into Lost at once, a promo that cashes moves into Winners, a busted Daily Sweep is
archived with a copy in Lost, a cashed Sweep stays in the hero. Serves ./site and fakes ESPN.  python3 tests/home_filing.py [shots_dir]"""
import asyncio, json, os, sys, threading, http.server, functools
from playwright.async_api import async_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
KO = 1794878100000   # BAL-LAC, Mon 11/16 7:15 PM CT
def ath(n, st): return {"athlete": {"displayName": n}, "stats": st}
def summary(herb, briss, flowers, henry_td, hampton_td):
    return {"boxscore": {"players": [{"statistics": [
        {"name": "passing", "keys": ["passingYards", "passingTouchdowns"], "athletes": [ath("Justin Herbert", [str(herb[0]), str(herb[1])]), ath("Jacoby Brissett", [str(briss), "1"])]},
        {"name": "rushing", "keys": ["rushingYards", "rushingTouchdowns"], "athletes": [ath("Justin Herbert", [str(herb[2]), "0"]), ath("Derrick Henry", ["80", str(henry_td)]), ath("Omarion Hampton", ["40", str(hampton_td)])]},
        {"name": "receiving", "keys": ["receptions", "receivingYards", "longReception", "receivingTouchdowns"], "athletes": [ath("Zay Flowers", ["5", str(flowers), "20", "0"])]}]}]}, "scoringPlays": []}
def board(state, bal, lac): return {"events": [{"id": "E1", "status": {"type": {"state": state}}, "competitions": [{"competitors": [{"team": {"abbreviation": "BAL"}, "score": str(bal)}, {"team": {"abbreviation": "LAC"}, "score": str(lac)}]}]}]}
CASES = {"bust": (board("post", 20, 10), summary((250, 2, 20), 210, 60, 1, 1)),      # 30 points: both overs dead, Chargers lose
         "cash": (board("post", 21, 24), summary((260, 2, 20), 210, 60, 1, 1))}      # 45 points, Chargers win, every leg clears
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8824), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for case, (sb, sm) in CASES.items():
            for theme in ("light", "dark"):
                ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
                await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}; (function(){{ var t = {KO} + 4 * 3600e3, D = Date; var N = Date.now; Date.now = function(){{ return t; }}; }})();")
                async def espn(route, request, sb=sb, sm=sm): await route.fulfill(status=200, content_type="application/json", body=json.dumps(sb if "scoreboard" in route.request.url else sm))
                await ctx.route("**/site.api.espn.com/**", espn)
                pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
                await pg.goto("http://127.0.0.1:8824/?x=1", wait_until="domcontentloaded"); await pg.wait_for_timeout(3500)
                st = await pg.evaluate("""() => ({promo: Array.from(document.querySelectorAll('#promo .promos > .promo')).filter(c => !c.hidden).map(c => c.querySelector('h3').textContent),
                    lost: Array.from(document.querySelectorAll('#lost .promo')).map(c => c.querySelector('h3').textContent + '|' + (c.querySelector('.st')||{}).textContent),
                    won: Array.from(document.querySelectorAll('#winners .promo')).map(c => c.querySelector('h3').textContent + '|' + (c.querySelector('.st')||{}).textContent),
                    wopen: !!(document.querySelector('#winners details') || {}).open, lkids: (document.querySelectorAll('#lost .lgrid > *') || []).length, built: Array.from(document.querySelectorAll('#lost .lcard h3')).map(x => x.textContent), lsub: (document.querySelector('#lost .tsub') || {}).textContent || '',
                    hero: Array.from(document.querySelectorAll('#sweep .promo.sweep')).filter(c => !c.hidden).map(c => c.querySelector('h3').textContent + '|' + (c.querySelector('.st')||{}).textContent),
                    last: (document.querySelector('#swtease .swlast') || {}).textContent || '', over: document.documentElement.scrollWidth - document.documentElement.clientWidth})""")
                print(f"   [{case} {theme}]", json.dumps(st)[:520])
                if case == "bust":
                    check("Piss Missile Monday" not in st["promo"] and st["lkids"] == 0 and not st["built"], f"[{case} {theme}] the busted promo left the page and there is no Lost section on Today")
                    check(not st["hero"], f"[{case} {theme}] the busted Sweep is off the hero")
                    check("Missed" in st["last"] and "Herbo" in st["last"], f"[{case} {theme}] the hero strip names the missed Sweep ({st['last'][:70]})")
                    check(st["promo"] == [], f"[{case} {theme}] no dead slip is left in the promo list")
                    rc = open(os.path.join(ROOT, "receipts", "index.html"), encoding="utf-8").read()
                    check("This week" in rc and "Sure Hands" in rc and "One From Every Game" in rc and "Busted: John Metchie III" in rc, f"[{case} {theme}] the week's misses are listed on the receipts page")
                else:
                    check(any(x.startswith("Piss Missile Monday|Cashed") for x in st["won"]) and st["wopen"] and "Piss Missile Monday" not in st["promo"], f"[{case} {theme}] the cashed promo moved to Winners and the fold opened")
                    check(st["hero"] == ["Herbo Fully Loaded|Cashed"] and not st["lost"], f"[{case} {theme}] the cashed Sweep stays in the hero, no live card in Lost ({st['hero']})")
                check(st["over"] == 0 and not errs, f"[{case} {theme}] no sideways scroll, no script errors {errs[:1]}")
                if SHOTS:
                    await pg.evaluate("(function(){ var e = document.getElementById(%s); if(e) e.scrollIntoView(); })()" % json.dumps("sweep" if case == "bust" else "winners"))
                    await pg.wait_for_timeout(300); await pg.screenshot(path=f"{SHOTS}/home-{case}-{theme}.png")
                await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
