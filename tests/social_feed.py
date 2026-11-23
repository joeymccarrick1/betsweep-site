"""Social feed states (11/16, alpha step 1): open / live / cashed, the Cashed tab, last week's winners, house-slip grading and
the touchdown double-count. Since 11/23 a busted slip is drawn nowhere (owner: "Once a leg from a slip that someone posted on social
loses please take the slip off the site") - tests/social_gone.py has that rule in full; here the old Lost-tab checks became "not there". Serves ./site, fakes the account client and ESPN.  python3 tests/social_feed.py [shots_dir]"""
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
window.__SEL = [];
// 11/22: winners for the "hit recently" fire. opener cashed two days ago; loser's only win is three weeks old.
window.__WON = [{user_id: U1, result: 'won', status: 'open', last_ko: new Date(Date.now() - 2 * 864e5).toISOString(), created_at: new Date(Date.now() - 3 * 864e5).toISOString()},
                {user_id: "00000000-0000-0000-0000-000000000003", result: 'won', status: 'open', last_ko: new Date(Date.now() - 20 * 864e5).toISOString(), created_at: new Date(Date.now() - 21 * 864e5).toISOString()}];
function Q(rows, t){ var f = {}, q = {select: function(c){ window.__SEL.push(t + ':' + (c || '*')); return q; }, eq: function(k, v){ f[k] = v; if(t === 'feed_posts' && k === 'result') rows = window.__WON.filter(function(p){ return p.result === v; }); return q; }, gte: function(){ return q; }, in: function(){ return q; }, order: function(){ return q; }, limit: function(){ return q; },
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
            await ctx.route("**/data/weeks.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"weeks": [WEEK - 1]})))   # no box file for the test's own week: the made-up games are graded from the faked score feed alone
            await ctx.route(f"**/data/box-w{WEEK - 1}.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"week": WEEK - 1, "box": {"Travis Kelce": [0, 0, 0, 1, 1, 4, 72, 0, 38]}, "games": {"NYJ-KC": [12, 35]}, "final": True})))
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto("http://127.0.0.1:8823/social/", wait_until="domcontentloaded"); await pg.wait_for_timeout(3200)
            ids = lambda: pg.evaluate("Array.from(document.querySelectorAll('#feed > article.post')).map(a => a.id)")
            check(await ids() == ["p1"], f"[{theme}] Top shows only the open slip ({await ids()})")
            check("1 open slip" in (await pg.inner_text("#feedinfo")) and "1 cashed" in (await pg.inner_text("#feedinfo")), f"[{theme}] the count line says 1 open, 1 cashed")
            check("cashed 1" in (await pg.inner_text('.seg button[data-s="cashed"]')).lower(), f"[{theme}] the Cashed tab carries its count")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/social-top-{theme}.png")
            # ---- owner 11/22: "save slips right from social page" - signed out, one tap, the builder's own saved-slip entry
            sv0 = await pg.evaluate("(function(){ var b = document.querySelector('#p1 [data-save]'); if(!b) return null; var r = b.getBoundingClientRect(); return [b.textContent, b.getAttribute('aria-pressed'), Math.round(r.height), localStorage.getItem('bs_slips_w%d')]; })()" % WEEK)
            await pg.tap('#p1 [data-save]'); await pg.wait_for_timeout(300)
            sv1 = await pg.evaluate("(function(){ var b = document.querySelector('#p1 [data-save]'), t = document.querySelector('.soctoast'), a = JSON.parse(localStorage.getItem('bs_slips_w%d') || '[]'); return {btn: [b.textContent, b.getAttribute('aria-pressed'), b.classList.contains('on')], toast: t ? t.textContent : '', n: a.length, s: a[0] || null, over: document.documentElement.scrollWidth - innerWidth}; })()" % WEEK)
            e = sv1["s"] or {}
            check(bool(sv0) and sv0[:2] == ["Save slip", "false"] and sv0[2] >= 30 and not sv0[3] and sv1["btn"] == ["Saved ✓", "true", True] and "Saved to My BetSweep" in sv1["toast"] and sv1["over"] <= 0,
                  f"[{theme}] an open slip has a Save slip button; one tap, signed out, turns it to Saved and says where it went ({sv0}, {sv1['btn']}, {sv1['toast']})")
            check(sv1["n"] == 1 and e.get("id") == "f1" and e.get("keys") == ["Justin Herbert|Passing Yards|175"] and e.get("odds") == 301 and e.get("stake") == 1 and e.get("name") == "Tonight" and e.get("from") == "opener" and e.get("px") == {"Justin Herbert|Passing Yards|175": {"o": -150}} and isinstance(e.get("saved"), (int, float)),
                  f"[{theme}] what it saved is the builder's kind of entry: the leg keys, the posted price, each leg's price, a one-unit stake ({ {k: e.get(k) for k in ('id', 'keys', 'odds', 'stake', 'name', 'from')} })")
            await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
            kept = await pg.evaluate("(function(){ var b = document.querySelector('#p1 [data-save]'); return b ? [b.textContent, b.classList.contains('on')] : null; })()")
            await pg.goto("http://127.0.0.1:8823/me/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
            onme = await pg.evaluate("(function(){ var t = (document.getElementById('crec') || document.body).textContent; return [t.indexOf('Tonight') >= 0, t.indexOf('Justin Herbert') >= 0, (document.getElementById('hopen') || {}).textContent]; })()")
            # 11/22 7:40 PM: this wanted the open-slip count to be 1 and failed on a Sunday night. The saved leg is a real player's (Justin Herbert), and once his
            # real game is final My BetSweep settles the slip from the game log and stops counting it as open. Before his game is final the count must be 1;
            # after, the slip must still be listed with its leg, counted open or settled.
            try:
                _g = next((g for g in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "builder_data.json")))["games"] if "LAC" in (g.get("a"), g.get("b"))), None)
                _final = bool(_g and _g.get("fin"))
            except Exception: _final = None
            check(kept == ["Saved ✓", True] and onme[0] and onme[1] and (onme[2] == "1" or (_final is not False and onme[2] in ("0", "1"))),
                  f"[{theme}] it is still marked saved after a reload, and My BetSweep lists it with its leg" + (" (his real game is final, so it may be settled rather than open)" if _final else ", as an open slip") + f" ({kept}, {onme})")
            await pg.goto("http://127.0.0.1:8823/social/", wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
            await pg.tap('#p1 [data-save]'); await pg.wait_for_timeout(300)
            un = await pg.evaluate("(function(){ var b = document.querySelector('#p1 [data-save]'), t = [...document.querySelectorAll('.soctoast')].pop(); return [b.textContent, JSON.parse(localStorage.getItem('bs_slips_w%d') || '[]').length, t ? t.textContent : '']; })()" % WEEK)
            check(un[:2] == ["Save slip", 0] and "Removed" in un[2], f"[{theme}] a second tap takes it back out ({un})")
            await pg.click('.seg button[data-s="cashed"]'); await pg.wait_for_timeout(400)
            check(not await pg.query_selector('#feed [data-save]'), f"[{theme}] a slip whose games have started has no Save button")
            check(await ids() == ["p2"], f"[{theme}] Cashed lists the winner ({await ids()})")
            check(await pg.inner_text("#p2 .res") == "Cashed" and await pg.locator("#p2 li.hit").count() == 3, f"[{theme}] winner: three legs marked hit (yards, one TD, over)")
            check(await pg.locator("#feed article.post").count() == 1, f"[{theme}] Cashed holds winners only")
            # owner 11/23: no Lost tab; the slip that lost a leg (p3) and the one whose game ended without a win (p4) are in no tab at all.
            # p3 not being under Cashed is also the 11/16 check that a one-TD game does not pass 2+ TD after repeat reads.
            where = {}
            for tab in ("top", "new", "cashed"):
                await pg.click(f'.seg button[data-s="{tab}"]'); await pg.wait_for_timeout(350); where[tab] = await ids()
            check(not await pg.query_selector('.seg button[data-s="lost"]') and where == {"top": ["p1"], "new": ["p1"], "cashed": ["p2"]}, f"[{theme}] there is no Lost tab, and the busted slip and the one that ended without a win are in no tab ({where})")
            m = await pg.evaluate("({over: document.documentElement.scrollWidth - document.documentElement.clientWidth, tab: Math.round(document.querySelector('nav.apptabs').getBoundingClientRect().bottom)})")
            check(m["over"] == 0 and m["tab"] == 844, f"[{theme}] no sideways scroll, tab bar at the bottom ({m})")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/social-cashed-{theme}.png", full_page=False)
            # nothing open and nothing cashed -> last week's winners
            await pg.evaluate("localStorage.setItem('t_empty', '1')"); await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
            await pg.click('.seg button[data-s="top"]'); await pg.wait_for_timeout(900)
            t = await pg.inner_text("#feed")
            check("No open slips right now" in t and "Build a slip and post it" in t, f"[{theme}] empty feed says so and offers the action")
            check("Last week's winners" in t and await pg.locator("#feed article.post").count() == 1 and "Week 9 hit" in t, f"[{theme}] last week's winner shown from the graded box file, the loser is not")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/social-empty-{theme}.png")
            # ---- people (v3): avatar, record, tail, reactions, profile, follow, Following tab ----
            await pg.evaluate("localStorage.removeItem('t_empty'); localStorage.setItem('t_user', '1'); localStorage.setItem('bs_social_sort', 'top')"); await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
            c1 = await pg.evaluate("(function(){ var c = document.getElementById('p1'); return {av: (c.querySelector('.av')||{}).textContent, fire: (c.querySelector('[data-rx=\"1|fire\"] b')||{}).textContent, tn: (c.querySelector('.tn')||{}).textContent, tail: (c.querySelector('[data-tail]')||{}).textContent}; })()")
            check(c1 == {"av": "OP", "fire": "3", "tn": "2 tailing", "tail": "I'm tailing"}, f"[{theme}] a post shows avatar, reaction count, tail count and a tail button ({c1})")
            # ---- owner 11/22: no public records; a fire for accounts that hit recently, otherwise nothing
            W_ = "(function(){ var f = document.getElementById('feed'); return {cards: [...f.querySelectorAll('article.post')].map(function(c){ var h = c.querySelector('.who .hot'); return [c.id, !!c.querySelector('.who .rec'), h ? h.textContent : '', h ? h.getAttribute('aria-label') : '']; }), txt: f.textContent}; })()"
            hr = await pg.evaluate(W_)
            # the poster whose only win is three weeks old: his slip this week lost, so (11/23) it is on no tab - his profile is where his name shows
            await pg.goto("http://127.0.0.1:8823/social/?h=1#u=00000000-0000-0000-0000-000000000003", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600)
            hl = await pg.evaluate("(function(){ var s = document.querySelector('.prof'); return s ? {name: s.querySelector('h2').firstChild.textContent, hot: !!s.querySelector('h2 .hot'), cards: document.querySelectorAll('#feed article.post').length, txt: document.getElementById('feed').textContent} : null; })()")
            await pg.goto("http://127.0.0.1:8823/social/", wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
            import re as _re
            check(["p1", False, "🔥", "Hit recently"] in hr["cards"] and bool(hl) and hl["name"] == "@loser" and not hl["hot"] and hl["cards"] == 0,
                  f"[{theme}] a poster who cashed in the last week wears a fire; one whose only win is three weeks old wears nothing, and his lost slip is not on his profile ({hr['cards']}, {hl and [hl['name'], hl['hot'], hl['cards']]})")
            hr["txt"] += (hl or {}).get("txt", "")
            check("12-8" not in hr["txt"] and "6.4" not in hr["txt"] and not _re.search(r"\b\d+-\d+ · [+−-]\d", hr["txt"]), f"[{theme}] no win-loss record or units next to any name in the feed")
            await pg.click('#p1 [data-tail]'); await pg.wait_for_timeout(300); await pg.click('#p1 [data-rx="1|lock"]'); await pg.wait_for_timeout(300)
            c2 = await pg.evaluate("(function(){ var c = document.getElementById('p1'); return [c.querySelector('[data-tail]').textContent, c.querySelector('.tn').textContent, c.querySelector('[data-rx=\"1|lock\"]').className, (c.querySelector('[data-rx=\"1|lock\"] b')||{}).textContent, window.__CALLS.filter(function(x){ return /tails:insert|reactions:upsert:lock|rpc:feed_profile_me/.test(x); }).length]; })()")
            check(c2 == ["Tailing ✓", "3 tailing", "on", "1", 3], f"[{theme}] tailing and reacting update the card and write to the database ({c2})")
            if SHOTS: await pg.evaluate("document.getElementById('p1').scrollIntoView({block:'center'})"); await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/social-people-{theme}.png")
            await pg.click('#p1 b.h'); await pg.wait_for_timeout(700)
            pr = await pg.evaluate("(function(){ var s = document.querySelector('.prof'); return s ? [s.querySelector('h2').firstChild.textContent, (s.querySelector('h2 .hot') || {}).textContent || '', s.querySelectorAll('dd, dl, .pstats').length, s.querySelector('.fol').textContent, document.querySelectorAll('#feed article.post').length, s.textContent] : null; })()")
            check(pr[:5] == ["@opener", "🔥", 0, "Follow", 1], f"[{theme}] tapping a name opens the profile: the name, the fire, a Follow button and their slips ({pr[:5]})")
            pl = await pg.inner_text('.prof .pn p')
            check("1 slip on Social" in pl and "posted" not in pl and "21" not in pl, f"[{theme}] the profile counts the slips it lists, not every slip ever posted - a total would give the record away ({pl})")
            sel = await pg.evaluate("window.__SEL.filter(function(x){ return /^feed_records:/.test(x); })")
            check(not _re.search(r"Record|Units|Graded|12-8|6\.4", pr[5]) and sel and not any(_re.search(r"won|lost|units|graded", x) for x in sel), f"[{theme}] the profile shows no record, units or graded count, and the page never asks the database for them ({sorted(set(sel))})")
            await pg.click('.prof .fol'); await pg.wait_for_timeout(300)
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/social-profile-{theme}.png")
            check(await pg.inner_text('.prof .fol') == "Following ✓" and "1 follower" in await pg.inner_text('.prof .pn p'), f"[{theme}] following flips the button and the follower count")
            await pg.click('.seg button[data-s="following"]'); await pg.wait_for_timeout(400)
            check(await ids() == ["p1"] and "1 person you follow" in await pg.inner_text("#feedinfo"), f"[{theme}] the Following tab lists the followed poster's open slip")
            m2 = await pg.evaluate("({over: document.documentElement.scrollWidth - document.documentElement.clientWidth})")
            check(m2["over"] == 0, f"[{theme}] no sideways scroll with five tabs")
            # ---- own username and avatar (v4) ----
            await pg.click('.seg button[data-s="top"]'); await pg.wait_for_timeout(300)
            check(await pg.is_visible('#mebtn'), f"[{theme}] a signed-in account gets a My slips button")
            await pg.click('#mebtn'); await pg.wait_for_timeout(700); await pg.click('[data-edit="1"]'); await pg.wait_for_timeout(300)
            tm = await pg.evaluate("(function(){ var a = [...document.querySelectorAll('.pedit input[name=e]')].map(function(i){ return i.value; }), t = [...document.querySelectorAll('.pedit label[title]')]; return [a.length, new Set(a).size, t.length, t.filter(function(l){ return l.getBoundingClientRect().width >= 44; }).length, document.documentElement.scrollWidth - innerWidth]; })()")
            check(tm[0] == 49 and tm[1] == 49 and tm[2] == 32 and tm[3] == 32 and tm[4] <= 0, f"the avatar picker offers initials, 16 fun emoji and one for each of the 32 teams, none twice, each a 44px target, no sideways scroll ({tm})")
            await pg.screenshot(path="/tmp/soc/editor.png", full_page=True)
            # ---- owner 11/22: "press a color or emoji make the change in real time on the users profile picture"
            SAV = "(function(){ var a = document.querySelector('.prof .phd > .av') || document.querySelector('.prof > .av'); if(!a) return null; var r = a.getBoundingClientRect(), t = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return {t: a.textContent, c: a.className, top: Math.round(r.top), bottom: Math.round(r.bottom), seen: !!t && (t === a || a.contains(t)), bar: !!document.querySelector('.prof .phd')}; })()"
            v0 = await pg.evaluate(SAV); pickc = "6" if "c6" not in v0["c"] else "3"
            await pg.click(f'.pedit input[name=c][value="{pickc}"]', force=True); await pg.wait_for_timeout(150); v1 = await pg.evaluate(SAV)
            await pg.click('.pedit .em input[value="🔥"]', force=True); await pg.wait_for_timeout(150); v2 = await pg.evaluate(SAV)
            check(v0["bar"] and f"c{pickc}" in v1["c"] and v1["t"] == v0["t"] and v2["t"] == "🔥" and "em" in v2["c"].split() and f"c{pickc}" in v2["c"], f"[{theme}] on your own profile a tap on a colour, then an emoji, changes the picture at once ({v0['c']} {v0['t']} -> {v2['c']} {v2['t']})")
            await pg.evaluate("document.querySelector('.pedit label[title=\"Titans\"]').scrollIntoView({block: 'center'})"); await pg.wait_for_timeout(250)
            await pg.click('.pedit label[title="Titans"] input', force=True); await pg.wait_for_timeout(200); v3 = await pg.evaluate(SAV)
            check(v3["t"] == "⚔️" and v3["seen"] and v3["top"] >= 40 and v3["bottom"] <= 844 - 64, f"[{theme}] a team picked far down the list shows on the picture, which stays in view under the menu ({v3['top']}-{v3['bottom']}px)")
            await pg.evaluate("window.dispatchEvent(new Event('popstate'))"); await pg.wait_for_timeout(300)
            kp = await pg.evaluate("(function(){ var f = document.getElementById('pedit'); return f ? [(f.querySelector('input[name=c]:checked') || {}).value, (f.querySelector('input[name=e]:checked') || {}).value] : null; })()"); v4 = await pg.evaluate(SAV)
            check(kp == [pickc, "⚔️"] and v4["t"] == "⚔️" and f"c{pickc}" in v4["c"], f"[{theme}] the feed redrawing while the editor is open keeps what was picked ({kp})")
            check(not any("feed_profile_set" in c for c in await pg.evaluate("window.__CALLS")), f"[{theme}] none of that saved anything")
            await pg.click('.pedit [data-edit="0"]'); await pg.wait_for_timeout(250); v5 = await pg.evaluate(SAV)
            check(v5["t"] == v0["t"] and v5["c"] == v0["c"] and not v5["bar"] and not await pg.query_selector('#pedit'), f"[{theme}] Cancel puts the saved picture back ({v5['c']} {v5['t']})")
            await pg.evaluate("window.scrollTo(0, 0)"); await pg.click('[data-edit="1"]'); await pg.wait_for_timeout(300)
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
