"""Social on other pages (alpha plan step 5, 11/16): "Top on Social" on Today, "N slips on Social" on Boards game cards, and the
one-game filter on Social (/social/#g=BAL-LAC). Serves ./site with a faked account client.  python3 tests/social_elsewhere.py [shots_dir]

11/23 (owner: "Once a leg from a slip that someone posted on social loses please take the slip off the site"): a slip that lost a leg
is not listed on Today, not counted on a Boards card and not shown in a game's view. The week's box file is faked here too (weeks.json
and box-w<week>.json), so the real build's finals never reach the test."""
import asyncio, json, os, sys, threading, http.server, functools, time
from playwright.async_api import async_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
# 11/16: the games and the clock come from the built boards page. The page clock is frozen two hours before the week's last kickoff, so that
# game is always "still to come" and the first game of the week is always finished - on any day, in any week. The names below (BAL-LAC,
# CIN-PIT, DET-NE) are stand-ins swapped for the real game ids by J().
import re as _re
_cards = sorted((int(k), g) for g, k in _re.findall(r'<section class="card[^"]*" id="([A-Z]+-[A-Z]+)"[^>]*data-ko="(\d+)"', open(os.path.join(ROOT, "boards", "index.html")).read()))
WEEK = int(_re.search(r'id="hsbar" data-week="(\d+)"', open(os.path.join(ROOT, "index.html")).read()).group(1))     # the week the built site is on
GL, GD, GN = _cards[-1][1], _cards[0][1], _cards[1][1]          # last game of the week, the first (finished), another finished one with no posts
def J(x): return x.replace("BAL-LAC", GL).replace("CIN-PIT", GD).replace("DET-NE", GN).replace("BAL vs LAC", GL.replace("-", " vs ")) if isinstance(x, str) else json.loads(J(json.dumps(x)))
now = _cards[-1][0] - 2 * 3600e3; FUT = _cards[-1][0]; PAST = _cards[0][0]
FREEZE = "Date.now = function(){ return %d; };" % now
def iso(ms): return __import__("datetime").datetime.fromtimestamp(ms / 1000, __import__("datetime").timezone.utc).isoformat()   # the database returns timestamptz as text
def leg(pl, m, ln, g, ko): return {"pl": pl, "m": m, "ln": ln, "g": g, "ko": ko, "o": -150, "k": f"{pl}|{m}|{ln}"}
def post(i, h, title, legs, score, tails=0): return {"id": i, "user_id": "00000000-0000-0000-0000-00000000000%d" % i, "handle": h, "title": title, "week": WEEK, "legs": legs, "fd_odds": 250 + 10 * i, "first_ko": iso(min(l["ko"] for l in legs)), "last_ko": iso(max(l["ko"] for l in legs)), "score": score, "tails": tails, "rx": {}, "result": None, "units": None, "created_at": "2026-11-16T15:00:00Z"}
POSTS = [post(1, "HerbFan", "Herbo time", [leg("Justin Herbert", "Passing Yards", 175, "BAL-LAC", FUT), leg("Derrick Henry", "Anytime TD", 1, "BAL-LAC", FUT)], 7, 4),
         post(2, "RunHeavy", "", [leg("Derrick Henry", "Rushing Yards", 60, "BAL-LAC", FUT)], 9),
         post(3, "LateOne", "Monday three", [leg("Zay Flowers", "Receiving Yards", 50, "BAL-LAC", FUT), leg("Omarion Hampton", "Anytime TD", 1, "BAL-LAC", FUT), leg("Over 38.5", "Total", 38.5, "BAL-LAC", FUT)], 2),
         post(4, "Fourth", "Also tonight", [leg("Justin Herbert", "Rushing Yards", 15, "BAL-LAC", FUT)], 1),
         dict(post(5, "Sunday", "Old slip", [leg("Joe Burrow", "Passing Yards", 250, "CIN-PIT", PAST)], 30), result="lost", units=-1)]   # a finished, graded slip
POSTS = J(POSTS)
MORE = J([post(6, "DeadEarly", "Lost on Thursday", [leg("Test Player", "Receiving Yards", 60, "CIN-PIT", PAST), leg("Justin Herbert", "Passing Yards", 175, "BAL-LAC", FUT)], 50),
          post(7, "AliveEarly", "Hit on Thursday", [leg("Test Player", "Receptions", 2, "CIN-PIT", PAST), leg("Derrick Henry", "Rushing Yards", 60, "BAL-LAC", FUT)], 40),
          post(8, "NoRead", "Nobody can check", [leg("Someone Else", "Receptions", 3, "DET-NE", PAST), leg("Zay Flowers", "Receiving Yards", 50, "BAL-LAC", FUT)], 45)])
BOXFILE = J({"week": WEEK, "final": False, "games": {"CIN-PIT": [20, 17]}, "box": {"Test Player": [0, 0, 0, 0, 0, 2, 31, 0, 20]}})   # the week's first game is a final in the file; "DET-NE" is not in it
FAKE = """window.__POSTS = %s; try{ if(localStorage.getItem("t_empty")) window.__POSTS = window.__POSTS.filter(function(p){ return p.id === 5; }); }catch(e){}
try{ if(localStorage.getItem("t_more")) window.__POSTS = window.__POSTS.concat(%s); }catch(e){}
var PRO = [{user_id: "00000000-0000-0000-0000-000000000001", handle: "HerbFan", color: 2, emoji: "\\ud83c\\udfc8"}];
function Q(rows, t){ var f = {}, cols = '', q = {select: function(c){ cols = c || ''; return q; }, eq: function(k, v){ f[k] = v; return q; }, gte: function(){ return q; }, in: function(){ return q; }, order: function(){ return q; }, limit: function(){ return q; },
  then: function(cb, eb){ var old = false; try{ old = !!localStorage.getItem("t_nov4"); }catch(e){}
    if(old && t === 'feed_profiles' && /emoji/.test(cols)) return Promise.resolve({data: null, error: {message: 'column feed_profiles.emoji does not exist'}}).then(cb, eb);
    return Promise.resolve({data: rows.map(function(p){ if(old && t === 'feed_profiles'){ var c = {}; for(var k in p) if(k !== 'emoji') c[k] = p[k]; return c; } return p; }).filter(function(p){ return f.week == null || p.week == null || p.week === f.week; }).slice().sort(function(a, b){ return (b.score || 0) - (a.score || 0); }), error: null}).then(cb, eb); }}; return q; }
window.bsAccount = {user: null, client: {rpc: function(){ return Promise.resolve({data: null, error: null}); }, from: function(t){ return t === 'feed_posts' ? Q(window.__POSTS, t) : t === 'feed_profiles' ? Q(PRO, t) : Q([], t); }}};""" % (json.dumps(POSTS), json.dumps(MORE))
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8851), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + FREEZE + FAKE)
            await ctx.route("**/site.api.espn.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body='{"events":[]}'))
            await ctx.route("**/data/weeks.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"weeks": [WEEK]})))
            await ctx.route(f"**/data/box-w{WEEK}.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(BOXFILE)))
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            _ev, _go = pg.evaluate, pg.goto
            async def ev(src, *a, _ev=_ev): return await _ev(J(src), *a)
            async def go(url, _go=_go, **k): return await _go(J(url), **k)
            pg.evaluate, pg.goto = ev, go
            # ---- Today ----
            await pg.goto("http://127.0.0.1:8851/?x=1", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
            st = await pg.evaluate("""() => { var s = document.getElementById('socstrip'); if(!s) return null; s.scrollIntoView({block: 'center'}); var o = document.documentElement;
                return {hidden: s.hidden, rows: Array.from(s.querySelectorAll('a.ssp')).map(function(a){ return a.querySelector('.w b').textContent + ' | ' + a.querySelector('.w small').textContent + ' | ' + a.querySelector('.od').textContent + ' | ' + a.getAttribute('href') + ' | ' + a.querySelector('.av').textContent; }),
                        all: s.querySelector('.seeall').textContent, over: o.scrollWidth - o.clientWidth, after: (s.previousElementSibling || {}).id || (s.previousElementSibling || {}).className, minH: Math.min.apply(null, Array.from(s.querySelectorAll('a.ssp')).map(function(a){ return a.getBoundingClientRect().height; }))}; }""")
            print(f"   [{theme}] strip:", json.dumps(st, ensure_ascii=False)[:700])
            check(st and not st["hidden"] and len(st["rows"]) == 3 and st["rows"][0].startswith("Derrick Henry 60+ | @RunHeavy · 1 leg | +270▲ 9 | /b/?p=2"), f"[{theme}] Today lists the three most-upvoted slips still to be played, top first; an untitled slip is named by its leg")
            check(st and "Herbo time | @HerbFan · 2 legs · 4 tailing" in st["rows"][1] and st["rows"][1].endswith("🏈") and all("Old slip" not in r for r in st["rows"]), f"[{theme}] tail count and the poster's chosen avatar show; Sunday's finished slip is not listed")
            check(st and st["all"] == "All 4 slips" and st["over"] == 0 and st["minH"] >= 56, f"[{theme}] the link counts the open slips, rows are tap-sized, no sideways scroll ({st and st['all']}, {st and st['minH']})")
            if SHOTS: await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/today-social-{theme}.png")
            # the note under the promos (11/16): the commission line stays in view, the how-to opens on a tap
            pn = await pg.evaluate("""() => { var n = document.querySelector('#promo .pnote'); if(!n) return null; var d = n.querySelector('details'), p = n.querySelector(':scope > p'), q = d.querySelector('p');
                var r = {vis: p.textContent, h: Math.round(p.getBoundingClientRect().height), open: d.open, sumH: Math.round(d.querySelector('summary').getBoundingClientRect().height), howH: Math.round(q.getBoundingClientRect().height)};
                d.querySelector('summary').click(); r.opened = d.open; r.how = q.textContent; d.querySelector('summary').click(); r.closedAgain = !d.open; return r; }""")
            if pn is None: print(f"   [{theme}] (no promo grid on Today in this build; the note check is skipped)")
            else: check("may earn BetSweep a commission" in pn["vis"] and not pn["open"] and pn["opened"] and pn["closedAgain"] and pn["sumH"] >= 44 and pn["h"] <= 90 and "FanDuel" in pn["how"], f"[{theme}] under the promos: the commission line is in view in a few lines, the how-to opens on a tap ({pn['h']}px of text; closed until tapped)")
            # ---- Boards ----
            await pg.goto("http://127.0.0.1:8851/boards/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
            bd = await pg.evaluate("""() => { var o = document.documentElement; function a(id){ var c = document.getElementById(id), x = c && c.querySelector('.ginfo a.socn'); return x ? x.textContent + ' -> ' + x.getAttribute('href') : null; }
                var c = document.getElementById('BAL-LAC'); c.querySelector('.ginfo').scrollIntoView({block: 'center'}); return {mnf: a('BAL-LAC'), cin: a('CIN-PIT'), det: a('DET-NE'), over: o.scrollWidth - o.clientWidth}; }""")
            check(bd == J({"mnf": "4 slips on Social -> /social/#g=BAL-LAC", "cin": None, "det": None, "over": 0}), f"[{theme}] Boards: each game card counts its posted slips and links to them; a finished game whose only slip lost says nothing, like one with none ({bd})")
            if SHOTS: await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/boards-social-{theme}.png")
            # ---- Social, one game ----
            await pg.goto("http://127.0.0.1:8851/social/#g=BAL-LAC", wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
            so = await pg.evaluate("""() => ({ids: Array.from(document.querySelectorAll('#feed > article.post')).map(function(a){ return a.id; }), bar: (document.querySelector('#feed .gfbar') || {}).textContent || '', house: !!(document.querySelector('.soc .house') && !document.querySelector('.soc .house').hidden)})""")
            check(so["ids"] == ["p2", "p1", "p3", "p4"] and J("BAL vs LAC") in so["bar"] and not so["house"], f"[{theme}] Social opened from a game card shows that game's slips only, says so, and the house slips step aside ({so})")
            if SHOTS: await pg.evaluate("window.scrollTo(0, Math.max(0, document.querySelector('#feed .gfbar').getBoundingClientRect().top + scrollY - 190))"); await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/social-onegame-{theme}.png")
            await pg.click('#feed .gfbar a'); await pg.wait_for_timeout(400)
            so2 = await pg.evaluate("""() => ({bar: !!document.querySelector('#feed .gfbar'), house: !!(document.querySelector('.soc .house') && !document.querySelector('.soc .house').hidden), hash: location.hash, any: !!document.querySelector('.soc .house')})""")
            # the house slips come back when the build has any (a Tuesday build has none until the week's first promo is posted)
            any_house = so2.pop("any")
            check(so2 == {"bar": False, "house": any_house, "hash": ""}, f"[{theme}] 'Show every game' clears the filter" + ("" if any_house else " (no house slips in this build)") + f" ({so2})")
            # a finished game whose only slip lost (owner 11/23): the slip is off the site, so the game's view is empty and says so
            await pg.goto("http://127.0.0.1:8851/social/?y=1#g=CIN-PIT", wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
            sf = await pg.evaluate("""() => ({ids: Array.from(document.querySelectorAll('#feed > article.post')).map(function(a){ return a.id; }), info: (document.getElementById('feedinfo') || {}).textContent || '', empty: (document.querySelector('#feed .empty b') || {}).textContent || ''})""")
            check(sf["ids"] == [] and sf["empty"] == "No slips on this game right now." and "0 slips on this game" in sf["info"] and "lost" not in sf["info"], f"[{theme}] a finished game whose only slip lost shows no slip and no count of lost ones ({sf})")
            # ---- 11/23: three more posts. One lost its first leg in the finished game (the most upvotes of all), one's first leg hit there, one has a leg in a finished game nobody can read ----
            await pg.evaluate("localStorage.setItem('t_more', '1')"); await pg.goto("http://127.0.0.1:8851/?x=5", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600)
            sm = await pg.evaluate("""() => { var s = document.getElementById('socstrip'); return {rows: Array.from(s.querySelectorAll('a.ssp')).map(function(a){ return a.getAttribute('href') + ' ' + a.querySelector('.w small').textContent; }), all: s.querySelector('.seeall').textContent}; }""")
            check([r.split(" ")[0] for r in sm["rows"]] == ["/b/?p=7", "/b/?p=2", "/b/?p=1"] and sm["rows"][0].endswith("· live") and sm["all"] == "All 5 slips", f"[{theme}] Today: the slip that lost a leg is not listed though it has the most upvotes, nor is the one nobody can check; the one whose first leg hit is, as live ({sm})")
            await pg.goto("http://127.0.0.1:8851/boards/?x=5", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600)
            bm = await pg.evaluate("""() => { function a(id){ var c = document.getElementById(id), x = c && c.querySelector('.ginfo a.socn'); return x ? x.textContent + ' -> ' + x.getAttribute('href') : null; } return {mnf: a('BAL-LAC'), cin: a('CIN-PIT'), det: a('DET-NE')}; }""")
            check(bm == J({"mnf": "6 slips on Social -> /social/#g=BAL-LAC", "cin": "1 slip on Social -> /social/#g=CIN-PIT", "det": "1 slip on Social -> /social/#g=DET-NE"}), f"[{theme}] Boards: the slip that lost a leg is counted on neither of its games; the other two are counted on both of theirs ({bm})")
            await pg.goto("http://127.0.0.1:8851/social/?x=5#g=BAL-LAC", wait_until="domcontentloaded"); await pg.wait_for_timeout(3000)
            g0 = await pg.evaluate("""() => Array.from(document.querySelectorAll('#feed > article.post')).map(function(a){ return a.id; })""")
            await pg.wait_for_timeout(4800)
            g1 = await pg.evaluate("""() => ({ids: Array.from(document.querySelectorAll('#feed > article.post')).map(function(a){ return a.id; }), info: (document.getElementById('feedinfo') || {}).textContent || ''})""")
            check(g0 == ["p7", "p2", "p1", "p3", "p4"] and g1["ids"] == ["p8", "p7", "p2", "p1", "p3", "p4"] and "6 slips on this game" in g1["info"], f"[{theme}] Social, one game: the six the card counted and not the slip that lost a leg; the one nobody can check waits six seconds, then shows ({g0} -> {g1})")
            await pg.evaluate("localStorage.removeItem('t_more')")
            # ---- nobody has posted ----
            await pg.evaluate("localStorage.setItem('t_empty', '1')"); await pg.goto("http://127.0.0.1:8851/?x=2", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
            em = await pg.evaluate("""() => { var s = document.getElementById('socstrip'); s.scrollIntoView({block: 'center'}); var e = s.querySelector('.ssempty'); return e ? [e.querySelector('b').textContent, e.querySelector('a').textContent, e.querySelector('a').getAttribute('href'), s.querySelector('.seeall').textContent] : null; }""")
            check(em == ["No open slips for the games left this week.", "Post the first slip", "/build/", "Open Social"], f"[{theme}] with nothing posted the strip invites the first slip ({em})")
            if SHOTS: await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/today-social-empty-{theme}.png")
            await pg.goto("http://127.0.0.1:8851/boards/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
            b2 = await pg.evaluate("""() => { function a(id){ var c = document.getElementById(id), x = c && c.querySelector('.ginfo a.socn'); return x ? x.textContent + ' -> ' + x.getAttribute('href') : null; } return [a('BAL-LAC'), a('DET-NE')]; }""")
            check(b2 == J(["Post a slip for this game -> /build/#g-BAL-LAC", None]), f"[{theme}] an upcoming game nobody has posted on offers the builder ({b2})")
            await pg.evaluate("localStorage.removeItem('t_empty')")
            # ---- a database that has not had sql/social_v4.sql yet (no emoji column): the poster's colour still shows ----
            await pg.evaluate("localStorage.setItem('t_nov4', '1')"); await pg.goto("http://127.0.0.1:8851/?x=4", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
            o4 = await pg.evaluate("""() => { var a = Array.from(document.querySelectorAll('#socstrip a.ssp')).filter(function(x){ return /HerbFan/.test(x.textContent); })[0], v = a && a.querySelector('.av'); return v ? [v.textContent, v.className] : null; }""")
            check(o4 == ["HF", "av c2"], f"[{theme}] before the username script is run the strip still shows the poster's colour and initials ({o4})")
            await pg.evaluate("localStorage.removeItem('t_nov4')")
            check(not errs, f"[{theme}] no script errors {errs[:2]}")
            await ctx.close()
        # no account client at all: the strip hides, nothing breaks
        ctx = await b.new_context(viewport={"width": 390, "height": 844}); pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        await pg.goto("http://127.0.0.1:8851/?x=3", wait_until="domcontentloaded"); await pg.wait_for_timeout(7500)
        check(await pg.evaluate("document.getElementById('socstrip').hidden") and not errs, f"without the account client the strip hides itself and nothing errors {errs[:1]}")
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
