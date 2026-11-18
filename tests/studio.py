"""Promo Studio (/studio/, owner 11/18: "Can you do the promo studio"): the owner's tool that puts a promo's exact legs and prices on
his own art. The page reads the home page's promo cards in the browser, so the test serves a home page whose cards are made by the
home page's own function (home.promo_card) - if that markup moves, this fails. What the canvas draws is read by recording every
string the page paints. The slip must read as BetSweep's own card: its own colours, the stake called an example, the price source
named - never a sportsbook's betslip or a placed bet. Needs a built site (gp/site)."""
import asyncio, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8876
sys.path.insert(0, HERE)
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)

def leg(who, market, o, gid, p=0.6, hp=0.58, kick="Thu 7:15 PM", key=None):
    return {"who": who, "disp": f"{who} {market}", "market": market, "o": o, "p": p, "hp": hp, "gid": gid, "kick": kick, "key": key or f"{who}|{market}|1"}
def fixture():
    import home
    home.AT["HOU-IND"] = "IND @ HOU"   # what home.load() files from the schedule; the other games are left to the fallback ("A vs B")
    img = lambda s: {"square": f"/promo/w11-{s}-square.png", "story": f"/promo/w11-{s}-story.png", "feed": f"/promo/w11-{s}-feed.png"}
    A = {"week": 11, "slot": 3, "title": "Thursday Night Thievery", "fd": 512, "p": 0.19, "hp": 0.2, "fair": "+426", "hfair": "+400", "link": "https://sportsbook.fanduel.com/addToBetslip?marketId[0]=42.1&selectionId[0]=1",
         "caption": "Thursday Night Thievery\nThree legs, one script.\n20% profit boost on FanDuel same-game parlays tonight.", "first_ko": 1795137300000, "last_ko": 1795137300000, "img": img(3),
         "legs": [leg("Nico Collins", "Receiving Yards 60+", -165, "HOU-IND", key="Nico Collins|Receiving Yards|60"), leg("Jonathan Taylor", "Anytime TD", -120, "HOU-IND", key="Jonathan Taylor|Anytime TD|1"), leg("C.J. Stroud", "Passing Yards 225+", -150, "HOU-IND", key="C.J. Stroud|Passing Yards|225")]}
    B = {"week": 11, "slot": 5, "title": "Sunday Sampler", "fd": 1240, "p": 0.07, "hp": 0.08, "fair": "+1100", "link": "https://sportsbook.fanduel.com/addToBetslip?marketId[0]=42.2&selectionId[0]=2", "caption": "", "first_ko": 1795370400000, "last_ko": 1795382700000, "img": img(5),
         "legs": [leg("KC -15.5", "Spread", -110, "ARI-KC", kick="Sun 12:00 PM", key="KC -15.5|Spread|16"), leg("DET", "Moneyline", -260, "DET-TB", kick="Sun 12:00 PM", key="DET|Moneyline|1"), leg("Over 40.5 (DEN-LV)", "Total", -105, "DEN-LV", kick="Sun 3:25 PM", key="Over 40.5|Total|41"),
                  leg("Rome Odunze or Luther Burden", "Either TD", -140, "CHI-NO", kick="Sun 12:00 PM", key="Rome Odunze or Luther Burden|Either TD|1"), leg("Kyle Monangai", "Rush + Rec Yards 52+", -113, "CHI-NO", kick="Sun 12:00 PM", key="Kyle Monangai|Rush + Rec Yards|52")]}
    C = dict(A, slot=1, title="unused", name="Texans roll", day="Thu", caption="The Daily Sweep\nOne house slip.", fd=285)
    cards = home.promo_card(C, kicker="The Daily Sweep · Thursday", hero=True) + home.promo_card(A) + home.promo_card(B)
    return f'<!doctype html><html><head><meta charset="utf-8"><title>home</title></head><body><section class="sec" id="promo"><div class="promos">{cards}</div></section></body></html>'

REC = """(() => { window.__t = []; const f = CanvasRenderingContext2D.prototype.fillText; CanvasRenderingContext2D.prototype.fillText = function(t){ window.__t.push(String(t)); return f.apply(this, arguments); }; })()"""
PIX = """() => { const b = window.__studio.st.slipBox, c = document.getElementById('cv'), x = c.getContext('2d'); const px = (u, v) => [...x.getImageData(Math.round(b.x + b.w * u), Math.round(b.y + b.h * v), 1, 1).data].slice(0, 3);
  const near = (p, q, d) => Math.abs(p[0] - q[0]) + Math.abs(p[1] - q[1]) + Math.abs(p[2] - q[2]) <= d; let blue = 0, n = 0;
  for(let u = 0.03; u < 0.98; u += 0.05) for(let v = 0.02; v < 0.98; v += 0.03){ n++; if(near(px(u, v), [27, 111, 216], 60)) blue++; }
  return {head: px(0.5, 0.012), body: px(0.97, 0.5), foot: px(0.5, 0.995 - 12 / (b.h / (b.w / 480))), blue: blue, n: n, box: [Math.round(b.w), Math.round(b.h)], cv: [c.width, c.height]}; }"""

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{PORT}"; page_path = os.path.join(ROOT, "studio", "index.html")
    check(os.path.exists(page_path) and all(os.path.exists(os.path.join(ROOT, "studio", "fonts", f)) for f in ("brush.woff", "marker.woff", "anton.woff", "bc700.woff")), "the build writes /studio/ with its page and fonts")
    if not os.path.exists(page_path): print(f"\n{ok} passed, {bad} failed"); sys.exit(1)
    src = open(page_path, encoding="utf-8").read(); sm = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, "sitemap.xml")) else ""
    check('content="noindex,nofollow"' in src and "/studio/" not in sm, "the page asks not to be indexed and is not in the sitemap")
    check(not re.search(r"TOTAL WAGER|TOTAL PAYOUT|sportsbook-style|Bet placed|BET ID", src, re.I), "nothing in the page draws or asks for a sportsbook's betslip or a placed-bet record")
    home_html = fixture(); check(home_html.count('<article class="promo') == 3 and 'data-who="Nico Collins"' in home_html, "the fixture home page carries three promo cards made by home.promo_card")
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def open_(w=1280, h=900, home=home_html, q="", mobile=False):
            ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, accept_downloads=True); await ctx.add_init_script(REC)
            async def root(route):
                if home is None: await route.continue_()
                else: await route.fulfill(status=200, content_type="text/html", body=home)
            await ctx.route(re.compile(r"^http://127\.0\.0\.1:%d/$" % PORT), root)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200])); bad_ = []; pg.on("response", lambda r: bad_.append(r.url) if r.status >= 400 else None)
            await pg.goto(base + "/studio/" + q, wait_until="load"); await pg.wait_for_function("document.querySelector('#promo option') && !/Loading/.test(document.querySelector('#promo option').textContent)", timeout=15000); await pg.wait_for_timeout(400)
            return ctx, pg, errs, bad_
        ctx, pg, errs, bad_ = await open_()
        opts = await pg.evaluate("[...document.querySelectorAll('#promo option')].map(o => o.textContent)")
        check(len(opts) == 3 and opts[0].startswith("The Daily Sweep · Thursday: Texans roll · +285 · 3 legs") and opts[1] == "Thursday Night Thievery · +512 · 3 legs" and opts[2] == "Sunday Sampler · +1240 · 5 legs", f"the menu lists the home page's three promos, the Sweep under its own name ({opts})")
        await pg.select_option("#promo", "1"); await pg.wait_for_timeout(300)
        v = await pg.evaluate("({title: document.getElementById('title').value, odds: document.getElementById('odds').value, boost: document.getElementById('boost').value, legs: document.getElementById('legs').value.split('\\n'), setup: document.getElementById('setup').value.split('\\n')})")
        check(v["title"] == "Thursday Night Thievery" and v["odds"] == "+512" and v["boost"] == "20", f"picking a promo fills its title, FanDuel price and the boost named in its caption ({v['title']}, {v['odds']}, {v['boost']}%)")
        check(v["legs"] == ["Nico Collins 60+ Yards | RECEIVING YARDS | -165", "Jonathan Taylor | ANYTIME TOUCHDOWN | -120", "C.J. Stroud 225+ Yards | PASSING YARDS | -150"], f"its legs, in plain words with their prices ({v['legs']})")
        check(len(v["setup"]) == 3 and all("%" in x for x in v["setup"]), f"and a note per leg from the graded chance on the card ({v['setup']})")
        await pg.evaluate("window.__t = []; window.__studio.draw()"); t = await pg.evaluate("window.__t"); px = await pg.evaluate(PIX)
        need = ["SAME-GAME PARLAY", "Colts @ Texans", "Nico Collins 60+ Yards", "-165", "EXAMPLE STAKE", "WOULD PAY", "$100.00", "BETSWEEP PICK · FANDUEL PRICES WHEN POSTED · PRICES MOVE", "WITH A 20% PROFIT BOOST", "+512"]
        check(all(any(n == s or n in s for s in t) for n in need), f"the slip draws the kind of parlay, the game the way the schedule has it (Colts @ Texans, though the game's id is HOU-IND), every leg and price, the boost, and says the stake is an example and whose prices these are (missing: {[n for n in need if not any(n in s for s in t)]})")
        check(not any(re.search(r"TOTAL WAGER|TOTAL PAYOUT|^SGP$|SCORER|ALT ", s) for s in t), "no sportsbook wording on it (no TOTAL WAGER / TOTAL PAYOUT, no SGP chip, no book market names)")
        near = lambda a, q, d=40: sum(abs(a[i] - q[i]) for i in range(3)) <= d
        check(near(px["head"], [15, 20, 28]) and near(px["body"], [244, 239, 227]) and px["blue"] == 0, f"the card is BetSweep's: navy header {px['head']}, cream body {px['body']}, no sportsbook blue anywhere on it ({px['blue']} of {px['n']} samples)")
        pay = [s for s in t if s.startswith("$") and s != "$100.00"]; check(pay == ["$714.40"], f"the example pays what +512 boosted 20% pays on $100 ({pay})")   # the boost is on the profit: 5.12 to 1 becomes 6.144 to 1, so $100 returns $714.40
        await pg.click("#pr-full"); await pg.wait_for_timeout(200); pr = await pg.input_value("#prompt")
        check("BetSweep slip card" in pr and "not a sportsbook's betslip" in pr and "Example stake $100.00" in pr and "Would pay $714.40" in pr and all(x in pr for x in ("Nico Collins 60+ Yards (-165)", "Jonathan Taylor (-120)", "C.J. Stroud 225+ Yards (-150)")) and "Indianapolis Colts @ Houston Texans" in pr and "Do not use official NFL or team logos" in pr,
              "the 'ChatGPT draws it all' prompt asks for the same BetSweep card with every leg, and no logos or real faces")
        await pg.click("#pr-blank"); await pg.wait_for_timeout(150); pr2 = await pg.input_value("#prompt"); check("EMPTY dark rounded rectangle" in pr2 and "Nico Collins" not in pr2, "the blank-panel prompt leaves the slip to the page")
        # full poster, three sizes
        await pg.click('#mode button[data-m="poster"]'); await pg.wait_for_timeout(250); sizes = {}
        for sz in ("square", "feed", "story"):
            await pg.click(f'#size button[data-s="{sz}"]'); await pg.wait_for_timeout(250); await pg.evaluate("window.__t = []; window.__studio.draw()")
            sizes[sz] = await pg.evaluate("({wh: [document.getElementById('cv').width, document.getElementById('cv').height], t: window.__t})")
        check([sizes[k]["wh"] for k in ("square", "feed", "story")] == [[1080, 1080], [1080, 1350], [1080, 1920]], f"the full poster draws at 1080x1080, 1080x1350 and 1080x1920")
        miss = {k: [n for n in ("THURSDAY", "THIEVERY", "TAIL IT NOW", "21+", "EXAMPLE STAKE", "Jonathan Taylor") if not any(n in s for s in sizes[k]["t"])] for k in sizes}
        check(not any(miss.values()), f"every size carries the title, the slip, the tail line and the 21+ strip (missing: {miss})")
        async with pg.expect_download() as dl: await pg.click("#save")
        d = await dl.value; path = await d.path(); size = os.path.getsize(path)
        check(d.suggested_filename == "betsweep-thursday-night-thievery-story.png" and size > 40000 and open(path, "rb").read(8) == b"\x89PNG\r\n\x1a\n", f"Download PNG saves {d.suggested_filename} ({size // 1024} KB)")
        # a multi-game promo: spread, moneyline, total, either-or TD, combined yards
        await pg.select_option("#promo", "2"); await pg.wait_for_timeout(300); legs = (await pg.input_value("#legs")).split("\n")
        check(legs == ["Kansas City Chiefs (-15.5) | SPREAD | -110", "Detroit Lions | TO WIN | -260", "Over 40.5 (DEN-LV) | TOTAL POINTS | -105", "Rome Odunze or Luther Burden | EITHER TO SCORE A TOUCHDOWN | -140", "Kyle Monangai 52+ Rush + Rec Yds | RUSH + REC YARDS | -113"], f"a five-leg, four-game promo reads in plain words too ({legs})")
        await pg.click('#mode button[data-m="overlay"]'); await pg.wait_for_timeout(250); await pg.evaluate("window.__t = []; window.__studio.draw()"); t2 = await pg.evaluate("window.__t")
        check(any(s == "5-LEG PARLAY" for s in t2) and any("4 games · Week 11" in s for s in t2) and not any("PROFIT BOOST" in s for s in t2), "its slip says 5-leg parlay, four games, and no boost it was not given")
        check(not errs and not bad_, f"no script errors and nothing missing ({errs[:2]} {bad_[:2]})")
        txt = await pg.evaluate("document.body.innerText"); check(not re.search(r"undefined|NaN|\[object", txt), "no 'undefined' or 'NaN' on the page"); await ctx.close()
        # the address can name a promo
        ctx, pg, errs, bad_ = await open_(q="?p=w11-5"); check(await pg.input_value("#title") == "Sunday Sampler" and not errs, "/studio/?p=w11-5 opens on that promo"); await ctx.close()
        # the real home page as built today (it may have no promos): the page still works by hand
        ctx, pg, errs, bad_ = await open_(home=None); n = await pg.evaluate("window.__studio.st.promos.length"); msg = await pg.evaluate("document.getElementById('msg').textContent")
        if n == 0:
            check("No promoted bets found" in msg, f"today's built home page has no promos up: the page says so ('{msg}')")
            await pg.fill("#title", "By hand"); await pg.fill("#odds", "+300"); await pg.fill("#legs", "Tank Dell 37+ Yards | RECEIVING YARDS | -114\nIND +12.5 | SPREAD | -110"); await pg.evaluate("window.__t = []; window.__studio.draw()"); t3 = await pg.evaluate("window.__t")
            check(any("Tank Dell 37+ Yards" in s for s in t3) and any(s == "2-LEG PARLAY" for s in t3) and any(s == "$400.00" for s in t3), "legs typed by hand are drawn, with what $100 would pay at +300")
        else: check(n >= 1 and await pg.input_value("#title") != "", f"today's built home page has {n} promo(s) and the first is loaded")
        check(not errs and not bad_, f"no script errors against the built home page ({errs[:2]} {bad_[:2]})"); await ctx.close()
        # a phone: one column, nothing wider than the screen
        ctx, pg, errs, bad_ = await open_(w=390, h=844, mobile=True); over = await pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"); cw = await pg.evaluate("document.getElementById('cv').getBoundingClientRect().width")
        check(over <= 0 and 300 <= cw <= 390 and not errs, f"on a phone the canvas is {cw:.0f}px wide and nothing runs off the screen")
        if os.environ.get("SHOT"):
            await pg.select_option("#promo", "1"); await pg.wait_for_timeout(300); await pg.screenshot(path=os.path.join(os.environ["SHOT"], "studio_phone.png"))
            png = await pg.evaluate("document.getElementById('cv').toDataURL('image/png')"); import base64; open(os.path.join(os.environ["SHOT"], "studio_overlay.png"), "wb").write(base64.b64decode(png.split(",")[1]))
            await pg.click('#mode button[data-m="poster"]'); await pg.wait_for_timeout(300); png = await pg.evaluate("document.getElementById('cv').toDataURL('image/png')"); open(os.path.join(os.environ["SHOT"], "studio_poster.png"), "wb").write(base64.b64decode(png.split(",")[1]))
        await ctx.close(); await b.close()
    srv.shutdown(); print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
asyncio.run(main())
