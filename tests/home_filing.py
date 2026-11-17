"""Today: posted slips are filed live by the page - a slip that loses a leg leaves the page at once (the Sweep hero falls back to its
one-line "Missed" strip), a slip that cashes moves into Winners, a cashed Sweep stays in the hero.

Rebuilt 11/17 on made-up slips so it runs in any week (it used to act on the two Week 10 Monday slips of the real build and could not
run once they were graded). tests/fixtures/promos_w10_mnf.json holds two built promo records - the Daily Sweep "Herbo Fully Loaded" and
the side slip "Piss Missile Monday" with its +7.5 spread leg. Here they are given a kickoff two days from now, rendered with the CURRENT
home.sweep_block / home.promos_block (so the page script under test is today's code), and put into the built Today page in place of
its own Sweep and promo sections. The score feed is faked for BAL / LAC and the page clock is set around that kickoff.

  python3 tests/home_filing.py [shots_dir]"""
import asyncio, json, os, re, sys, tempfile, threading, time, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); GP = os.path.join(HERE, ".."); ROOT = os.path.join(GP, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
sys.path.insert(0, GP)
import home, sweep as SW

KO = (int(time.time()) // 60 * 60 + 48 * 3600) * 1000        # the made-up kickoff: two days from now, so the build keeps both slips as live cards
def blocks():
    ps = json.load(open(os.path.join(HERE, "fixtures", "promos_w10_mnf.json")))["promos"]
    for p in ps:
        p["first_ko"] = p["last_ko"] = KO; p["day"] = SW.day_of(KO); p["result"] = ""; p["status"] = "LIVE"
        for l in p["legs"]: l["ko"] = KO
    IN_T, OUT_T = tempfile.mkdtemp(), tempfile.mkdtemp()                      # an empty input folder: no game log, so nothing is graded at build time
    json.dump(ps, open(os.path.join(OUT_T, "promos.json"), "w"))
    sw, _ = home.sweep_block(IN_T, OUT_T, [{"gid": "BAL-LAC", "ko": KO, "a": "LAC", "b": "BAL", "home": "BAL", "away": "LAC"}])
    return sw, home.promos_block(OUT_T, sweep_exists=True)
def section(html, sid):
    m = re.search(r'<section[^>]*\bid="%s"[^>]*>' % sid, html)
    if not m: return None
    j = html.index("</section>", m.end()) + len("</section>"); assert "<section" not in html[m.end():j], f"#{sid} has a section inside it - the test's cut would be wrong"
    return m.start(), j
def page():
    """the built Today page with its own Sweep and promo sections swapped for the made-up ones"""
    sw, pr = blocks(); html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    assert sw.count('class="promo sweep"') == 1 and pr.count('<article class="promo"') == 1, "the fixture did not render as one Sweep and one side slip"
    s = section(html, "promo")
    if s: html = html[:s[0]] + html[s[1]:]
    s = section(html, "sweep")
    if s: html = html[:s[0]] + sw + html[s[1]:]
    else: s = section(html, "tdday"); assert s, "no #sweep and no #tdday on the built page"; html = html[:s[0]] + sw + html[s[0]:]
    w = section(html, "winners") or section(html, "sweep")
    return html[:w[1]] + pr + html[w[1]:]

def ath(n, st): return {"athlete": {"displayName": n}, "stats": st}
def summary(herb, briss, flowers, henry_td, hampton_td):
    return {"boxscore": {"players": [{"statistics": [
        {"name": "passing", "keys": ["passingYards", "passingTouchdowns"], "athletes": [ath("Justin Herbert", [str(herb[0]), str(herb[1])]), ath("Jacoby Brissett", [str(briss), "1"])]},
        {"name": "rushing", "keys": ["rushingYards", "rushingTouchdowns"], "athletes": [ath("Justin Herbert", [str(herb[2]), "0"]), ath("Derrick Henry", ["80", str(henry_td)]), ath("Omarion Hampton", ["40", str(hampton_td)])]},
        {"name": "receiving", "keys": ["receptions", "receivingYards", "longReception", "receivingTouchdowns"], "athletes": [ath("Zay Flowers", ["5", str(flowers), "20", "0"])]}]}]}, "scoringPlays": []}
def board(state, bal, lac): return {"events": [{"id": "E1", "status": {"type": {"state": state}}, "competitions": [{"competitors": [{"team": {"abbreviation": "BAL"}, "score": str(bal)}, {"team": {"abbreviation": "LAC"}, "score": str(lac)}]}]}]}
GOOD = summary((260, 2, 20), 210, 60, 1, 1)
CASES = {"pre": (board("pre", 0, 0), {"boxscore": {"players": []}}, -3600e3),            # an hour before kickoff
         "bust": (board("post", 20, 10), summary((250, 2, 20), 210, 60, 1, 1), 4 * 3600e3),  # 30 points: both overs dead, Chargers lose by 10
         "cash": (board("post", 21, 24), GOOD, 4 * 3600e3),                                  # 45 points, Chargers win, every leg clears
         "cover": (board("post", 27, 24), GOOD, 4 * 3600e3),                                 # Chargers lose by 3 and cover +7.5: the side slip still cashes
         "nocover": (board("post", 34, 24), GOOD, 4 * 3600e3),                               # 58 points, Chargers lose by 10: the side slip dies on the spread, the Sweep cashes
         "herbert": (board("post", 20, 23), summary((129, 0, 51), 340, 74, 2, 1), 4 * 3600e3)}  # what happened on 11/16: 129 passing yards, no passing TD
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
READ = """() => ({promo: Array.from(document.querySelectorAll('#promo .promos > .promo')).filter(c => !c.hidden).map(c => c.querySelector('h3').textContent + '|' + (c.querySelector('.st')||{}).textContent),
    won: Array.from(document.querySelectorAll('#winners .promo')).map(c => c.querySelector('h3').textContent + '|' + (c.querySelector('.st')||{}).textContent),
    wopen: !!(document.querySelector('#winners details') || {}).open, lost: !!document.getElementById('lost'),
    hero: Array.from(document.querySelectorAll('#sweep .promo.sweep')).filter(c => !c.hidden && c.offsetParent !== null).map(c => c.querySelector('h3').textContent + '|' + (c.querySelector('.st')||{}).textContent),
    last: (document.querySelector('#swtease .swlast') || {}).textContent || '', dead: Array.from(document.querySelectorAll('.promo li.dead')).map(li => li.dataset.who + ' ' + li.dataset.mk).slice(0, 6),
    over: document.documentElement.scrollWidth - document.documentElement.clientWidth})"""
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8824), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    HTML = page()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for case, (sb, sm, dt) in CASES.items():
            for theme in ("light", "dark"):
                # service workers off: the site's worker would answer the page load itself and bypass the page served below
                ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
                await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}; Date.now = function(){{ return {int(KO + dt)}; }};")
                async def espn(route, request, sb=sb, sm=sm): await route.fulfill(status=200, content_type="application/json", body=json.dumps(sb if "scoreboard" in request.url else sm))
                async def doc(route, request):
                    if request.resource_type == "document": await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=HTML)
                    else: await route.continue_()
                await ctx.route("**/*", doc); await ctx.route("**/site.api.espn.com/**", espn); await ctx.route("**/*supabase*/**", lambda r: r.abort())
                pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
                await pg.goto("http://127.0.0.1:8824/?x=1", wait_until="domcontentloaded"); await pg.wait_for_timeout(3500)
                st = await pg.evaluate(READ); T = f"[{case} {theme}]"
                if theme == "light": print("  ", T, json.dumps(st)[:420])
                if case == "pre":
                    check(st["promo"] == ["Piss Missile Monday|Pregame"] and st["hero"] == ["Herbo Fully Loaded|Pregame"] and not st["dead"], f"{T} an hour before kickoff both slips are up and say Pregame")
                elif case in ("bust", "herbert"):
                    check(st["promo"] == [] and not st["lost"], f"{T} the busted side slip left the page and there is no Lost section on Today")
                    check(not st["hero"] and "Missed" in st["last"] and "Herbo" in st["last"], f"{T} the busted Sweep is off the hero and the strip names it as missed ({st['last'][:60]})")
                    if case == "herbert": check(any("Justin Herbert" in d and "175" in d for d in st["dead"]) and any("225" in d for d in st["dead"]), f"{T} 129 passing yards kills the 175+ and the 225+ legs ({st['dead'][:4]})")
                elif case == "nocover":
                    check(st["promo"] == [] and not any(x.startswith("Piss Missile Monday") for x in st["won"]), f"{T} a 10-point loss kills the +7.5 leg: the side slip leaves the page and is not a winner")
                    check(st["hero"] == ["Herbo Fully Loaded|Cashed"], f"{T} the Sweep (no side in it) still cashes ({st['hero']})")
                else:
                    check(any(x.startswith("Piss Missile Monday|Cashed") for x in st["won"]) and st["wopen"] and st["promo"] == [], f"{T} the cashed side slip moved to Winners and the fold opened")
                    check(st["hero"] == ["Herbo Fully Loaded|Cashed"] and not st["lost"], f"{T} the cashed Sweep stays in the hero ({st['hero']})")
                check(st["over"] == 0 and not errs, f"{T} no sideways scroll, no script errors {errs[:1]}")
                if SHOTS and case in ("bust", "cash"):
                    await pg.evaluate("(function(){ var e = document.getElementById(%s); if(e) e.scrollIntoView(); })()" % json.dumps("sweep" if case == "bust" else "winners")); await pg.wait_for_timeout(300); await pg.screenshot(path=f"{SHOTS}/home-{case}-{theme}.png")
                await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
