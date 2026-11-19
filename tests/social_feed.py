"""Social feed states (11/16, alpha step 1): open / live / cashed / busted, the Cashed tab, last week's winners, house-slip grading and
the touchdown double-count. Serves ./site, fakes the account client and ESPN.  python3 tests/social_feed.py [shots_dir]"""
import asyncio, json, os, sys, threading, http.server, functools, time
from playwright.async_api import async_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
now = int(time.time() * 1000); PAST = now - 20 * 3600e3; FUT = now + 5 * 3600e3
def leg(pl, m, ln, g, ko, o=-150, gl=None): d = {"pl": pl, "m": m, "ln": ln, "g": g, "ko": ko, "o": o, "k": f"{pl}|{m}|{ln}"}; d.update({"gl": gl} if gl else {}); return d
# 11/17: the week comes from the built Social page, so the test means the same thing after the week rolls (it was written against Week 10).
# The games in it (BAL-LAC, NYJ-KC) are made up for the faked score feed and are not tied to any week's board.
WEEK = int(__import__("re").search(r"var W = (\d+),", open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "social", "index.html")).read()).group(1))
def iso(ms): return __import__("datetime").datetime.fromtimestamp(ms / 1000, __import__("datetime").timezone.utc).isoformat()   # the database returns timestamptz as text, so the fake does too (11/16)
def post(i, h, title, legs, score=0, week=WEEK): return {"id": i, "user_id": "00000000-0000-0000-0000-00000000000%d" % i, "tails": 2 if i == 1 else 0, "rx": {"fire": 3} if i == 1 else {}, "result": None, "units": None, "handle": h, "title": title, "week": week, "legs": legs, "fd_odds": 300 + i, "first_ko": iso(min(l["ko"] for l in legs)), "last_ko": iso(max(l["ko"] for l in legs)), "score": score, "created_at": "2026-11-15T20:00:00Z"}
POSTS = [post(1, "opener", "Tonight", [leg("Justin Herbert", "Passing Yards", 175, "BAL-LAC", FUT)], 5),
         post(2, "winner", "SNF four", [leg("Joe Burrow", "Passing Yards", 250, "CIN-PIT", PAST), leg("Ja'Marr Chase", "Anytime TD", 1, "CIN-PIT", PAST), leg("Over 41.5", "Total", 41.5, "CIN-PIT", PAST, gl={"k": "T", "side": "OVER"})], 3),
         post(3, "loser", "Two TDs", [leg("Ja'Marr Chase", "2+ TD", 1, "CIN-PIT", PAST), leg("Joe Burrow", "Passing TDs", 1, "CIN-PIT", PAST)], 1),
         post(4, "ghost", "Not in box", [leg("Nobody Here", "Receptions", 2, "CIN-PIT", PAST)], 0)]
LASTW = [post(9, "oldwin", "Week 9 hit", [leg("Travis Kelce", "Receiving Yards", 50, "NYJ-KC", PAST - 7 * 864e5)], 2, week=WEEK - 1), post(8, "oldloss", "Week 9 miss", [leg("Travis Kelce", "Receiving Yards", 90, "NYJ-KC", PAST - 7 * 864e5)], 2, week=WEEK - 1)]
SCORE = {"events": [{"id": "E1", "status": {"type": {"state": "post"}}, "competitions": [{"competitors": [{"team": {"abbreviation": "CIN"}, "score": "38"}, {"team": {"abbreviation": "PIT"}, "score": "18"}]}]},
                    {"id": "E2", "status": {"type": {"state": "pre"}}, "competitions": [{"competitors": [{"team": {"abbreviation": "BAL"}, "score": "0"}, {"team": {"abbreviation": "LAC"}, "score": "0"}]}]}]}
def ath(n, st): return {"athlete": {"displayName": n}, "stats": st}
SUMMARY = {"boxscore": {"players": [{"statistics": [{"name": "passing", "keys": ["passingYards", "passingTouchdowns"], "athletes": [ath("Joe Burrow", ["409", "3"])]},
            {"name": "receiving", "keys": ["receptions", "receivingYards", "longReception", "receivingTouchdowns"], "athletes": [ath("Ja'Marr Chase", ["11", "231", "60", "1"])]}]}]}, "scoringPlays": []}
FAKE = """window.__POSTS = %s; window.__LASTW = %s; try{ if(localStorage.getItem("t_empty")) window.__POSTS = []; }catch(e){}
window.__CALLS = [];
var U1 = "00000000-0000-0000-0000-000000000001", ME = "00000000-0000-0000-0000-0000000000aa";
var T = {feed_records: [{user_id: U1, handle: "opener", graded: 20, won: 12, lost: 8, units: 6.4, posts: 21}], feed_profiles: [{user_id: U1, handle: "opener", color: 2}], feed_tails: [], feed_reactions: [], feed_follows: []};
function Q(rows, t){ var f = {}, q = {select: function(){ return q; }, eq: function(k, v){ f[k] = v; return q; }, gte: function(){ return q; }, in: function(){ return q; }, order: function(){ return q; }, limit: function(){ return q; },
  insert: function(o){ window.__CALLS.push(t + ':insert:' + JSON.stringify(o)); return Promise.resolve({error: null}); }, upsert: function(o){ window.__CALLS.push(t + ':upsert:' + o.kind); return Promise.resolve({error: null}); },
  delete: function(){ window.__CALLS.push(t + ':delete'); return q; },
  then: function(cb){ var r = rows.filter(function(p){ return (f.week == null || p.week === f.week) && (f.user_id == null || p.user_id === f.user_id || t !== 'feed_posts' && t !== 'feed_records' && t !== 'feed_profiles'); }); return Promise.resolve({data: r, error: null}).then(cb); }}; return q; }
var SIGNED = false; try { SIGNED = !!localStorage.getItem("t_user"); } catch(e){}
window.bsAccount = {user: SIGNED ? {id: ME} : null, client: {rpc: function(n, a){ window.__CALLS.push('rpc:' + n + (a ? ':' + JSON.stringify(a) : ''));
    if(n === 'feed_profile_set'){ if(/taken/i.test(a.p_handle)) return Promise.resolve({data: null, error: {message: 'That username is taken'}}); return Promise.resolve({data: {user_id: ME, handle: a.p_handle, color: a.p_color, emoji: a.p_emoji}, error: null}); }
    return Promise.resolve({data: {user_id: ME, handle: "MeUser", color: 4, emoji: null}, error: null}); },
  from: function(t){ return t === 'feed_posts' ? Q(window.__POSTS.concat(window.__LASTW), t) : Q(T[t] || [], t); }}};""" % (json.dumps(POSTS), json.dumps(LASTW))
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
            await ctx.route(f"**/data/box-w{WEEK - 1}.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"week": WEEK - 1, "box": {"Travis Kelce": [0, 0, 0, 1, 1, 4, 72, 0, 38]}, "games": {"NYJ-KC": [12, 35]}, "final": True})))
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
            # ---- people (v3): avatar, record, tail, reactions, profile, follow, Following tab ----
            await pg.evaluate("localStorage.removeItem('t_empty'); localStorage.setItem('t_user', '1'); localStorage.setItem('bs_social_sort', 'top')"); await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
            c1 = await pg.evaluate("(function(){ var c = document.getElementById('p1'); return {av: (c.querySelector('.av')||{}).textContent, rec: (c.querySelector('.rec')||{}).textContent, fire: (c.querySelector('[data-rx=\"1|fire\"] b')||{}).textContent, tn: (c.querySelector('.tn')||{}).textContent, tail: (c.querySelector('[data-tail]')||{}).textContent}; })()")
            check(c1 == {"av": "OP", "rec": "12-8 · +6.4u", "fire": "3", "tn": "2 tailing", "tail": "I'm tailing"}, f"[{theme}] a post shows avatar, record, reaction count, tail count and a tail button ({c1})")
            await pg.click('#p1 [data-tail]'); await pg.wait_for_timeout(300); await pg.click('#p1 [data-rx="1|lock"]'); await pg.wait_for_timeout(300)
            c2 = await pg.evaluate("(function(){ var c = document.getElementById('p1'); return [c.querySelector('[data-tail]').textContent, c.querySelector('.tn').textContent, c.querySelector('[data-rx=\"1|lock\"]').className, (c.querySelector('[data-rx=\"1|lock\"] b')||{}).textContent, window.__CALLS.filter(function(x){ return /tails:insert|reactions:upsert:lock|rpc:feed_profile_me/.test(x); }).length]; })()")
            check(c2 == ["Tailing ✓", "3 tailing", "on", "1", 3], f"[{theme}] tailing and reacting update the card and write to the database ({c2})")
            if SHOTS: await pg.evaluate("document.getElementById('p1').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/social-people-{theme}.png")
            await pg.click('#p1 b.h'); await pg.wait_for_timeout(700)
            pr = await pg.evaluate("(function(){ var s = document.querySelector('.prof'); return s ? [s.querySelector('h2').textContent, Array.from(s.querySelectorAll('dd')).map(function(d){ return d.textContent; }).join('|'), s.querySelector('.fol').textContent, document.querySelectorAll('#feed article.post').length] : null; })()")
            check(pr == ["@opener", "12-8|+6.4|20", "Follow", 1], f"[{theme}] tapping a name opens the profile with record, units and their slips ({pr})")
            await pg.click('.prof .fol'); await pg.wait_for_timeout(300)
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/social-profile-{theme}.png")
            check(await pg.inner_text('.prof .fol') == "Following ✓" and "1 follower" in await pg.inner_text('.prof .pn p'), f"[{theme}] following flips the button and the follower count")
            await pg.click('.seg button[data-s="following"]'); await pg.wait_for_timeout(400)
            check(await ids() == ["p1"] and "1 person you follow" in await pg.inner_text("#feedinfo"), f"[{theme}] the Following tab lists the followed poster's open slip")
            m2 = await pg.evaluate("({over: document.documentElement.scrollWidth - document.documentElement.clientWidth})")
            check(m2["over"] == 0, f"[{theme}] no sideways scroll with six tabs")
            # ---- own username and avatar (v4) ----
            await pg.click('.seg button[data-s="top"]'); await pg.wait_for_timeout(300)
            check(await pg.is_visible('#mebtn'), f"[{theme}] a signed-in account gets a My profile button")
            await pg.click('#mebtn'); await pg.wait_for_timeout(700); await pg.click('[data-edit="1"]'); await pg.wait_for_timeout(300)
            tm = await pg.evaluate("(function(){ var a = [...document.querySelectorAll('.pedit input[name=e]')].map(function(i){ return i.value; }), t = [...document.querySelectorAll('.pedit label[title]')]; return [a.length, new Set(a).size, t.length, t.filter(function(l){ return l.getBoundingClientRect().width >= 44; }).length, document.documentElement.scrollWidth - innerWidth]; })()")
            check(tm[0] == 49 and tm[1] == 49 and tm[2] == 32 and tm[3] == 32 and tm[4] <= 0, f"the avatar picker offers initials, 16 fun emoji and one for each of the 32 teams, none twice, each a 44px target, no sideways scroll ({tm})")
            await pg.screenshot(path="/tmp/soc/editor.png", full_page=True)
            await pg.fill('#peh', 'bad name'); await pg.click('.pedit .sv'); await pg.wait_for_timeout(200)
            e1 = await pg.inner_text('#pemsg')
            await pg.fill('#peh', 'TakenName'); await pg.click('.pedit .sv'); await pg.wait_for_timeout(300); e2 = await pg.inner_text('#pemsg')
            check("3 to 20" in e1 and e2 == "That username is taken", f"[{theme}] a bad username is refused on the page and the database's reason is shown ({e1[:30]} / {e2})")
            await pg.fill('#peh', 'JoeyMac'); await pg.evaluate("document.querySelector('.pedit input[name=c][value=\"5\"]').click(); document.querySelector('.pedit input[name=e][value=\"🏈\"]').click()")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/social-edit-{theme}.png")
            await pg.click('.pedit .sv'); await pg.wait_for_timeout(500)
            pr2 = await pg.evaluate("(function(){ var s = document.querySelector('.prof'); return [s.querySelector('h2').textContent, s.querySelector('.av').textContent, s.querySelector('.av').className, !!document.getElementById('pedit'), window.__CALLS.filter(function(x){ return /feed_profile_set.*JoeyMac.*\"p_color\":5/.test(x); }).length]; })()")
            check(pr2 == ["@JoeyMac", "🏈", "av big c5 em", False, 1], f"[{theme}] saving sets the username, colour and avatar ({pr2})")
            m3 = await pg.evaluate("({over: document.documentElement.scrollWidth - document.documentElement.clientWidth})"); check(m3["over"] == 0, f"[{theme}] the edit form does not scroll sideways")
            hs = await pg.evaluate("Array.from(document.querySelectorAll('.hcard .hst')).map(x => x.className + '|' + x.textContent)")
            print(f"   [{theme}] house cards: {hs}")
            check(not errs, f"[{theme}] no script errors {errs[:2]}")
            await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
