"""Social feed states (11/16, alpha step 1): open / live / cashed / busted, the Cashed tab, last week's winners, house-slip grading and
the touchdown double-count. Serves ./site, fakes the account client and ESPN.  python3 tests/social_feed.py [shots_dir]"""
import asyncio, json, os, sys, threading, http.server, functools, time
from playwright.async_api import async_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
now = int(time.time() * 1000); PAST = now - 20 * 3600e3; FUT = now + 5 * 3600e3
def leg(pl, m, ln, g, ko, o=-150, gl=None): d = {"pl": pl, "m": m, "ln": ln, "g": g, "ko": ko, "o": o, "k": f"{pl}|{m}|{ln}"}; d.update({"gl": gl} if gl else {}); return d
def post(i, h, title, legs, score=0, week=10): return {"id": i, "user_id": "u%d" % i, "handle": h, "title": title, "week": week, "legs": legs, "fd_odds": 300 + i, "first_ko": min(l["ko"] for l in legs), "last_ko": max(l["ko"] for l in legs), "score": score, "created_at": "2026-11-15T20:00:00Z"}
POSTS = [post(1, "opener", "Tonight", [leg("Justin Herbert", "Passing Yards", 175, "BAL-LAC", FUT)], 5),
         post(2, "winner", "SNF four", [leg("Joe Burrow", "Passing Yards", 250, "CIN-PIT", PAST), leg("Ja'Marr Chase", "Anytime TD", 1, "CIN-PIT", PAST), leg("Over 41.5", "Total", 41.5, "CIN-PIT", PAST, gl={"k": "T", "side": "OVER"})], 3),
         post(3, "loser", "Two TDs", [leg("Ja'Marr Chase", "2+ TD", 1, "CIN-PIT", PAST), leg("Joe Burrow", "Passing TDs", 1, "CIN-PIT", PAST)], 1),
         post(4, "ghost", "Not in box", [leg("Nobody Here", "Receptions", 2, "CIN-PIT", PAST)], 0)]
LASTW = [post(9, "oldwin", "Week 9 hit", [leg("Travis Kelce", "Receiving Yards", 50, "NYJ-KC", PAST - 7 * 864e5)], 2, week=9), post(8, "oldloss", "Week 9 miss", [leg("Travis Kelce", "Receiving Yards", 90, "NYJ-KC", PAST - 7 * 864e5)], 2, week=9)]
SCORE = {"events": [{"id": "E1", "status": {"type": {"state": "post"}}, "competitions": [{"competitors": [{"team": {"abbreviation": "CIN"}, "score": "38"}, {"team": {"abbreviation": "PIT"}, "score": "18"}]}]},
                    {"id": "E2", "status": {"type": {"state": "pre"}}, "competitions": [{"competitors": [{"team": {"abbreviation": "BAL"}, "score": "0"}, {"team": {"abbreviation": "LAC"}, "score": "0"}]}]}]}
def ath(n, st): return {"athlete": {"displayName": n}, "stats": st}
SUMMARY = {"boxscore": {"players": [{"statistics": [{"name": "passing", "keys": ["passingYards", "passingTouchdowns"], "athletes": [ath("Joe Burrow", ["409", "3"])]},
            {"name": "receiving", "keys": ["receptions", "receivingYards", "longReception", "receivingTouchdowns"], "athletes": [ath("Ja'Marr Chase", ["11", "231", "60", "1"])]}]}]}, "scoringPlays": []}
FAKE = """window.__POSTS = %s; window.__LASTW = %s; try{ if(localStorage.getItem("t_empty")) window.__POSTS = []; }catch(e){}
function Q(rows){ var f = {}, q = {select: function(){ return q; }, eq: function(k, v){ f[k] = v; return q; }, gte: function(){ return q; }, in: function(){ return q; }, order: function(){ return q; }, limit: function(){ return q; },
  then: function(cb){ var r = rows.filter(function(p){ return f.week == null || p.week === f.week; }); return Promise.resolve({data: r, error: null}).then(cb); }}; return q; }
window.bsAccount = {user: null, client: {from: function(t){ return t === 'feed_posts' ? Q(window.__POSTS.concat(window.__LASTW)) : Q([]); }}};""" % (json.dumps(POSTS), json.dumps(LASTW))
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(H, directory=ROOT)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8823), h); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + FAKE)
            async def espn(route):
                u = route.request.url; await route.fulfill(status=200, content_type="application/json", body=json.dumps(SCORE if "scoreboard" in u else SUMMARY))
            await ctx.route("**/site.api.espn.com/**", espn)
            await ctx.route("**/data/box-w9.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"week": 9, "box": {"Travis Kelce": [0, 0, 0, 1, 1, 4, 72, 0, 38]}, "games": {"NYJ-KC": [12, 35]}, "final": True})))
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto("http://127.0.0.1:8823/social/", wait_until="domcontentloaded"); await pg.wait_for_timeout(3200)
            ids = lambda: pg.evaluate("Array.from(document.querySelectorAll('#feed > article.post')).map(a => a.id)")
            check(await ids() == ["p1"], f"[{theme}] Top shows only the open slip ({await ids()})")
            check("1 open slip" in (await pg.inner_text("#feedinfo")) and "1 cashed" in (await pg.inner_text("#feedinfo")), f"[{theme}] the count line says 1 open, 1 cashed")
            check("cashed 1" in (await pg.inner_text('.seg button[data-s="cashed"]')).lower(), f"[{theme}] the Cashed tab carries its count")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/social-top-{theme}.png")
            await pg.click('.seg button[data-s="cashed"]'); await pg.wait_for_timeout(400)
            check(await ids() == ["p2"], f"[{theme}] Cashed lists the winner ({await ids()})")
            check(await pg.inner_text("#p2 .res") == "Cashed" and await pg.locator("#p2 li.hit").count() == 3, f"[{theme}] winner: three legs marked hit (yards, one TD, over)")
            check(await pg.locator("#feed article.post").count() == 1, f"[{theme}] Cashed holds winners only")
            await pg.click('.seg button[data-s="lost"]'); await pg.wait_for_timeout(400)
            bust = await pg.evaluate("Array.from(document.querySelectorAll('#feed article.post')).map(a => a.id + ':' + (a.querySelector('.res')||{}).textContent)")
            check(bust == ["p3:Busted · 1 of 2 hit", "p4:Final · 0 of 1 graded hits"], f"[{theme}] Lost tab: a one-TD game does not pass 2+ TD after repeat reads; an unknown player is never called a miss ({bust})")
            m = await pg.evaluate("({over: document.documentElement.scrollWidth - document.documentElement.clientWidth, tab: Math.round(document.querySelector('nav.apptabs').getBoundingClientRect().bottom)})")
            check(m["over"] == 0 and m["tab"] == 844, f"[{theme}] no sideways scroll, tab bar at the bottom ({m})")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/social-lost-{theme}.png", full_page=False)
            # nothing open and nothing cashed -> last week's winners
            await pg.evaluate("localStorage.setItem('t_empty', '1')"); await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
            await pg.click('.seg button[data-s="top"]'); await pg.wait_for_timeout(900)
            t = await pg.inner_text("#feed")
            check("No open slips right now" in t and "Build a slip and post it" in t, f"[{theme}] empty feed says so and offers the action")
            check("Last week's winners" in t and await pg.locator("#feed article.post").count() == 1 and "Week 9 hit" in t, f"[{theme}] last week's winner shown from the graded box file, the loser is not")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/social-empty-{theme}.png")
            hs = await pg.evaluate("Array.from(document.querySelectorAll('.hcard .hst')).map(x => x.className + '|' + x.textContent)")
            print(f"   [{theme}] house cards: {hs}")
            check(not errs, f"[{theme}] no script errors {errs[:2]}")
            await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
