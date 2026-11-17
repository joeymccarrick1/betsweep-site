"""My BetSweep: the top of the page shows open slips, the record in units and profit by week (alpha plan step 7, 11/16).
Serves ./site with made-up saved slips in the browser and made-up weekly box files; no network.   python3 tests/me_hub.py [shots_dir]"""
import asyncio, json, os, sys, threading, http.server, functools
from playwright.async_api import async_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
# box rows: [passYds, passTD, int, rushYds, rushTD, rec, recYds, recTD, longRec]
BOX = {8: {"week": 8, "final": True, "games": {"AAA-BBB": [20, 17]}, "box": {"Tom Test": [250, 2, 0, 10, 0, 0, 0, 0, 0]}},
       9: {"week": 9, "final": True, "games": {"CCC-DDD": [24, 10]}, "box": {"Rex Runner": [0, 0, 0, 88, 1, 2, 15, 0, 9]}}}
SLIPS = {8: [{"name": "W8 winner", "keys": ["Tom Test|Passing Yards|200"], "odds": 150, "stake": 1}, {"name": "W8 loser", "keys": ["Tom Test|Passing Yards|300"], "odds": 200, "stake": 2}],
         9: [{"name": "W9 winner", "keys": ["Rex Runner|Rushing Yards|50", "Rex Runner|Anytime TD|1"], "odds": 300, "stake": 1}],
         10: [{"name": "Open one", "keys": ["Rex Runner|Rushing Yards|50"], "odds": 120, "stake": 2}, {"name": "Open two", "keys": ["Tom Test|Passing Yards|200", "Rex Runner|Anytime TD|1"], "odds": -110, "stake": 1}]}
SEED = "try{ if(!localStorage.getItem('t_empty')){ var S = %s; Object.keys(S).forEach(function(w){ localStorage.setItem('bs_slips_w' + w, JSON.stringify(S[w])); }); } else { ['8','9','10'].forEach(function(w){ localStorage.removeItem('bs_slips_w' + w); }); } }catch(e){}" % json.dumps(SLIPS)
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8857), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async def data(route, request):
        u = request.url; w = int(u.split("-w")[-1].split(".")[0]) if "-w" in u else 0
        if "/data/box-w" in u and w in BOX: await route.fulfill(status=200, content_type="application/json", body=json.dumps(BOX[w]))
        else: await route.fulfill(status=404, content_type="text/plain", body="none")
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + SEED)
            await ctx.route("**/data/box-w*.json", data); await ctx.route("**/data/close-w*.json", data)
            await ctx.route("**/*supabase*/**", lambda r: r.abort()); await ctx.route("**/*espn.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body='{"events":[]}'))
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto("http://127.0.0.1:8857/me/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2200)
            s = await pg.evaluate("""() => { var o = document.documentElement, T = function(id){ var e = document.getElementById(id); return e ? e.textContent : null; }, hub = document.getElementById('hub'), cs = getComputedStyle(document.getElementById('hrec'));
              return {open: T('hopen'), opens: T('hopens'), rec: T('hrec'), units: T('hunits'), wl: T('hweekl'), week: T('hweek'), weeks: T('hweeks'), recUp: document.getElementById('hrec').classList.contains('up'), font: cs.fontFamily.slice(0, 22),
                      top: Math.round(hub.getBoundingClientRect().top + scrollY), bottom: Math.round(hub.getBoundingClientRect().bottom + scrollY), tileH: Math.min.apply(null, Array.from(hub.querySelectorAll('.ht')).map(function(a){ return Math.round(a.getBoundingClientRect().height); })),
                      bars: Array.from(hub.querySelectorAll('.pw li')).map(function(li){ return li.className + '|' + li.querySelector('button').getAttribute('aria-label') + '|' + li.querySelector('b').textContent + '|' + li.querySelector('small').textContent + '|' + ((li.querySelector('i') || {}).offsetHeight || 0); }),
                      firstCard: (document.querySelector('.me .card') || {}).id, themeBelow: document.getElementById('cthm').getBoundingClientRect().top > document.getElementById('cbank').getBoundingClientRect().top, recShut: document.getElementById('crec').classList.contains('shut'), bankShut: document.getElementById('cbank').classList.contains('shut'), over: o.scrollWidth - o.clientWidth}; }""")
            print(f"   [{theme}]", json.dumps(s, ensure_ascii=False)[:900])
            check(s["open"] == "2" and s["opens"] == "3u at stake · 3.3u if all cash", f"[{theme}] open slips: how many, what is staked and what they pay if all cash ({s['open']} | {s['opens']})")
            check(s["rec"] == "2–1" and s["units"] == "+2.50u all weeks" and s["recUp"], f"[{theme}] record in units over every graded week: {s['rec']}, {s['units']}")
            check(s["wl"] == "Week 10" and s["week"] == "–" and s["weeks"] == "nothing graded yet · 2 open", f"[{theme}] this week says nothing is graded yet rather than showing a zero ({s['wl']}: {s['week']} | {s['weeks']})")
            check(len(s["bars"]) == 3 and s["bars"][0].startswith("down|Week 8: −0.50 units, 1–1 on 2 graded slips|−0.5|W8|") and s["bars"][1].startswith("up|Week 9: +3 units, 1–0 on 1 graded slip|+3.0|W9|") and s["bars"][2].startswith("open|Week 10: not graded yet, 2 open|2 open|W10|"), f"[{theme}] profit by week: a losing week hangs below the line, a winning one stands above it, an ungraded week is marked open ({[x.split('|')[0] + ' ' + x.split('|')[2] for x in s['bars']]})")
            h8, h9 = int(s["bars"][0].split("|")[-1]), int(s["bars"][1].split("|")[-1]); check(h9 == 40 and 5 <= h8 <= 9, f"[{theme}] bar heights follow the units (+3.0 is the tallest at {h9}px; -0.5 is {h8}px)")
            check(s["firstCard"] == "crec" and not s["recShut"] and s["bankShut"] and s["top"] < 260 and s["themeBelow"] and s["tileH"] >= 88 and s["over"] == 0, f"[{theme}] the hub sits at the top (starts {s['top']}px down), slips come first and open, the bankroll is folded, no sideways scroll")
            if SHOTS: await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(250); await pg.screenshot(path=f"{SHOTS}/me-hub-{theme}.png")
            # tapping a week opens that week's slips in the list
            await pg.click('#hub .pw button[data-w="8"]'); await pg.wait_for_timeout(900)
            w8 = await pg.evaluate("""() => { var h = document.querySelector('#slips .wkh[data-w="8"]'), sl = Array.from(document.querySelectorAll('#slips li.sl.w8')); return {on: !!h && h.classList.contains('on'), shown: sl.filter(function(x){ return x.offsetHeight > 0; }).length, names: sl.map(function(x){ return x.querySelector('b').textContent + ' ' + x.querySelector('.res').textContent; }), top: h ? Math.round(h.getBoundingClientRect().top) : -1}; }""")
            check(w8["on"] and w8["shown"] == 2 and w8["names"] == ["W8 winner Cashed", "W8 loser Missed"] and 0 <= w8["top"] <= 420, f"[{theme}] tapping Week 8 opens that week's slips and brings them into view ({w8})")
            # a tile opens the slips card even if the reader had folded it
            await pg.evaluate("document.getElementById('crec').classList.add('shut'); window.scrollTo(0, 0)"); await pg.click('#hub .ht'); await pg.wait_for_timeout(700)
            check(not await pg.evaluate("document.getElementById('crec').classList.contains('shut')"), f"[{theme}] tapping a tile opens the slips list")
            # nothing saved yet
            await pg.evaluate("localStorage.setItem('t_empty', '1')"); await pg.goto("http://127.0.0.1:8857/me/?e=1", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
            e = await pg.evaluate("""() => { var T = function(id){ return document.getElementById(id).textContent; }; return [T('hopen'), T('hopens'), T('hrec'), T('hunits'), T('hweek'), document.getElementById('hubw').hidden]; }""")
            check(e == ["0", "Save a slip and it is tracked here", "–", "no graded slips yet", "–", True], f"[{theme}] with nothing saved the hub says so and shows no chart ({e})")
            await pg.evaluate("localStorage.removeItem('t_empty')")
            check(not errs, f"[{theme}] no script errors {errs[:2]}")
            await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
