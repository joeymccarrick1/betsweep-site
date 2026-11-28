"""The game-script strip reads the way the header does (owner 11/27 10:19 PM: "we need to swap the side that the Script Strip is reading.
Titans on the left should read like their 4% chance to win by 10 first. Close game under next. Shootout and then jags by 10+").

Since 11/27 a board's header has the away team on the left and the home team on the right, but the strip under it still read in the
scripts tab's own order, so on about half the cards the right-hand team's blowout came first. Now every card's strip, its legend line and
the small strips in the confidence block run: left team by 10+, close and low, shootout, right team by 10+ - with each slice still tied
to its own script (the plays and slip it opens), and the slice colours by place.

Read off the built Boards page itself, every card, so it runs in any week.
  python3 tests/board_strip.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, os, sys, threading
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8901; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
READ = """() => Array.from(document.querySelectorAll('section.card[id]')).filter(function(c){ return c.querySelector('.scripts'); }).map(function(c){
  var T = function(e){ return e ? e.textContent.replace(/\\s+/g, ' ').trim() : ''; }, sl = Array.from(c.querySelectorAll('.scripts i[data-sc]'));
  return {id: c.id, flip: c.classList.contains('scf'), left: T(c.querySelector('.hd .tm.a b')), right: T(c.querySelector('.hd .tm.b b')),
          strip: sl.map(function(i){ return [T(i.querySelector('em')), i.getAttribute('data-sc'), (i.className.match(/\\bs[1-4]\\b/) || [''])[0], T(i.querySelector('b')), Math.round(i.getBoundingClientRect().left)]; }),
          legend: Array.from(c.querySelectorAll('.legend span')).map(function(s){ return [T(s), ((s.querySelector('i.d') || {className: ''}).className.match(/\\bs[1-4]\\b/) || [''])[0]]; }),
          minis: Array.from(c.querySelectorAll('.mscripts')).map(function(m){ return Array.from(m.querySelectorAll('i')).map(function(i){ return [T(i.querySelector('em')), (i.className.match(/\\bs[1-4]\\b/) || [''])[0]]; }); }),
          on: sl.filter(function(i){ return i.classList.contains('on'); }).map(function(i){ return i.getAttribute('data-sc'); })}; })"""
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("dark", "light"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block", color_scheme=theme)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            async def gate(route, request): await (route.continue_() if "127.0.0.1" in request.url else route.abort())
            await ctx.route("**/*", gate)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/boards/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            cs = await pg.evaluate(READ); flips = [c for c in cs if c["flip"]]
            print(f"   [{theme}] {len(cs)} boards with a strip, {len(flips)} of them turned; first turned: {json.dumps(flips[0])[:520] if flips else None}")
            check(len(cs) >= 1 and all(c["left"] and c["right"] for c in cs), f"[{theme}] every board with a strip has a team on each side of its header ({len(cs)} boards)")
            bad = [c for c in cs if [x[0].lower() for x in c["strip"]] != [f"{c['left']} by 10+".lower(), "close, low", "shootout", f"{c['right']} by 10+".lower()]]
            check(not bad, f"[{theme}] the strip reads left team by 10+, close and low, shootout, right team by 10+ on every board (first wrong: {[(c['id'], c['left'], c['right'], [x[0] for x in c['strip']]) for c in bad[:1]]})")
            bad = [c for c in cs if [x[2] for x in c["strip"]] != ["s1", "s2", "s3", "s4"] or [x[4] for x in c["strip"]] != sorted(x[4] for x in c["strip"])]
            check(not bad, f"[{theme}] the slices are coloured by place and sit left to right in that order ({[(c['id'], [x[2] for x in c['strip']]) for c in bad[:1]]})")
            bad = [c for c in cs if [x[1] for x in c["strip"]] != (["3", "1", "2", "0"] if c["flip"] else ["0", "1", "2", "3"])]
            check(not bad, f"[{theme}] each slice keeps its own script: a turned card runs scripts 3-1-2-0, the others 0-1-2-3 ({[(c['id'], c['flip'], [x[1] for x in c['strip']]) for c in bad[:1]]})")
            bad = [c for c in cs if len(c["legend"]) != 4 or not c["legend"][0][0].lower().endswith(f"{c['left']} wins by 10+".lower()) or not c["legend"][3][0].lower().endswith(f"{c['right']} wins by 10+".lower()) or [x[1] for x in c["legend"]] != ["s1", "s2", "s3", "s4"]
                   or [x[0].split("%")[0] for x in c["legend"]] != [x[3].rstrip("%") for x in c["strip"]]]
            check(not bad, f"[{theme}] the legend line under the strip runs in the same order with the same four numbers ({[(c['id'], c['legend']) for c in bad[:1]]})")
            bad = [(c["id"], m) for c in cs for m in c["minis"] if [x[0].lower() for x in m] != [f"{c['left']} by 10+".lower(), "close, low", "shootout", f"{c['right']} by 10+".lower()] or [x[1] for x in m] != ["s1", "s2", "s3", "s4"]]
            check(not bad, f"[{theme}] the small strips in the confidence block read the same way ({sum(len(c['minis']) for c in cs)} of them; first wrong: {bad[:1]})")
            # a tap on the left slice opens the left team's ending, on a turned card too
            tgt = (flips or cs)[0]
            r = await pg.evaluate("""(id) => { var c = document.getElementById(id); c.classList.add('expanded'); var first = c.querySelector('.scripts i[data-sc]'); first.click(); var k = first.getAttribute('data-sc');
                var vis = Array.from(c.querySelectorAll('.splays[data-sc]')).filter(function(e){ return !e.hidden; }).map(function(e){ return [e.getAttribute('data-sc'), (e.querySelector('.lt') || e).textContent.replace(/\\s+/g, ' ').trim().slice(0, 60), getComputedStyle(e).borderLeftColor]; });
                return {k: k, on: first.classList.contains('on'), vis: vis, sliceBg: getComputedStyle(first).backgroundColor}; }""", tgt["id"])
            check(r["on"] and r["vis"] and all(v[0] == r["k"] for v in r["vis"]) and all(v[2] == r["sliceBg"] for v in r["vis"]), f"[{theme}] tapping the left slice on {tgt['id']} opens that same ending's plays, edged in the slice's own colour ({r})")
            over = await pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check(over <= 0 and not errs, f"[{theme}] no sideways scroll, no page errors ({over}px, {errs[:1]})")
            if SHOTS:
                await pg.evaluate("(id) => { var e = document.getElementById(id); e.scrollIntoView(); window.scrollBy(0, -100); }", tgt["id"]); await pg.wait_for_timeout(300); await pg.screenshot(path=os.path.join(SHOTS, f"board_strip_{theme}.png"))
            await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
