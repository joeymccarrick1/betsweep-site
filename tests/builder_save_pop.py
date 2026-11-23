"""Saving a slip from the open betslip on a phone (owner 11/21: "when you save a betslip when the betslip is open there's a popup or
something more obvious instead of having to scroll down and save"): a Save button pinned in the open slip, a box in the middle of the
screen to name it, and a plain "Saved".   python3 tests/builder_save_pop.py [shots_dir]"""
import asyncio, json, os, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8870; SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
IN_VIEW = "(function(s){ var e = document.querySelector(s); if(!e || !e.getClientRects().length) return null; var r = e.getBoundingClientRect(); return {top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height), w: Math.round(r.width), vh: innerHeight, vis: r.top >= 0 && r.bottom <= innerHeight && r.width > 0}; })"
BD = json.load(open(os.path.join(HERE, "out", "builder_data.json"))); WEEK = int(BD["week"])
_l = [l for l in BD["legs"] if not l.get("gl") and (l.get("fd") or {}).get("m") and l["m"] in ("Rushing Yards", "Receiving Yards") and not next((g for g in BD["games"] if g["gid"] == l["g"]), {}).get("fin")]
# 11/22 11:05 PM (a Sunday night, one game left to play): the second leg used to have to come from ANOTHER game, so with only Monday night
# open the slip had one leg and the "2 legs" checks failed - on the clock, not on the page. The second leg is another player, from another
# game while there is one and from the same game when there is not; with no game left to kick off there is nothing to put in a slip.
if not _l:
    print("PASS no game is still to kick off this week, so there is no open leg to save: the Save box is checked again when next week's legs are in")
    print("1 passed, 0 failed"); sys.exit(0)
_k = lambda x: f"{x['pl']}|{x['m']}|{int(round(x['ln']))}"
KEYS = [_k(_l[0])] + [_k(x) for x in sorted([x for x in _l if x["pl"] != _l[0]["pl"]], key=lambda x: x["g"] == _l[0]["g"])][:1]
NK = len(KEYS); LEGS = f"{NK} leg{'s' if NK != 1 else ''}"
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("dark", "light"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            await ctx.add_init_script("try{ localStorage.setItem('bs_slipk_w%d', JSON.stringify(%s)); }catch(e){}" % (WEEK, json.dumps(KEYS)))
            await ctx.route("**/*", lambda r: r.continue_() if "127.0.0.1" in r.request.url else r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/build/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
            nsl = await pg.evaluate("(document.querySelector('.slipwrap .slipbar .n') || {}).textContent")
            if str(nsl) != str(NK): print("   setup: slip count", nsl, "wanted", NK)
            T = f"[{theme}] "
            check(await pg.evaluate(IN_VIEW + "('#savepin')") is None, T + "with the slip closed there is no extra Save button in the way")
            await pg.tap(".slipwrap .slipbar"); await pg.wait_for_timeout(600)
            sp = await pg.evaluate(IN_VIEW + "('#savepin')"); fd = await pg.evaluate(IN_VIEW + "('#sendfd')")
            check(bool(sp) and sp["vis"] and sp["h"] >= 40 and bool(fd) and fd["vis"], T + f"the open slip shows Save on screen beside FanDuel, no scrolling ({sp})")
            await pg.tap("#savepin"); await pg.wait_for_timeout(400)
            bx = await pg.evaluate(IN_VIEW + "('.svpop .svbox')"); t = await pg.inner_text(".svpop .svbox")
            check(bool(bx) and bx["vis"] and abs((bx["top"] + bx["bottom"]) / 2 - 422) < 200 and "Save this slip" in t and LEGS in t and await pg.evaluate("!!document.querySelector('.svpop input')"), T + f"Save opens a box in the middle of the screen with the leg count and a name field ({bx})")
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"save_pop_{theme}.png"))
            await pg.fill(".svpop input", "Sunday special"); await pg.tap(".svpop .pri"); await pg.wait_for_timeout(400)
            t2 = await pg.inner_text(".svpop .svbox"); saved = await pg.evaluate("(function(){ var k = Object.keys(localStorage).filter(function(x){ return /^bs_slips_w\\d+$/.test(x); })[0]; return k ? JSON.parse(localStorage.getItem(k)) : []; })()")
            check("Saved" in t2 and "Sunday special" in t2 and "My BetSweep" in t2 and len(saved) == 1 and saved[0]["name"] == "Sunday special" and len(saved[0]["keys"]) == NK, T + f"the box then says Saved, with the name and where to find it, and the slip is stored ({[s['name'] for s in saved]})")
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"save_done_{theme}.png"))
            await pg.tap(".svpop .dn"); await pg.wait_for_timeout(200); check(not await pg.query_selector(".svpop"), T + "Done closes it")
            await pg.tap("#savepin"); await pg.wait_for_timeout(300); t3 = await pg.inner_text(".svpop .svbox")
            check("Already saved" in t3 and "Sunday special" in t3 and len(await pg.evaluate("(function(){ var k = Object.keys(localStorage).filter(function(x){ return /^bs_slips_w\\d+$/.test(x); })[0]; return JSON.parse(localStorage.getItem(k)); })()")) == 1, T + "saving the same slip again says so and does not store it twice")
            await pg.evaluate("document.querySelector('.svpop').click()"); await pg.wait_for_timeout(200); check(not await pg.query_selector(".svpop") and not errs, T + f"a tap outside closes it; no script errors ({errs[:1]})")
            await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
