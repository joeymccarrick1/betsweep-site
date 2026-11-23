"""A posted slip comes off the site once a leg loses (owner 11/23 12:12 PM: "Once a leg from a slip that someone posted on social
loses please take the slip off the site").

What is checked, with a faked account client, a faked score feed and a faked box file (nothing here depends on the day or the week's
real games - the games are made up):
  A  the Social page: a slip with a dead leg, a stored result of lost or push, or every game over without every leg hit is drawn in no
     tab, no game view and no profile, the poster's own included; there is no Lost tab; a saved "lost" tab falls back to Top; and while
     the live scores are still on their way a slip whose game has kicked off is held back, so a dead slip never flashes on the page.
  B  the scores feed down, the week's box file up: the file alone keeps a lost slip off the page (a touchdown leg only the file calls
     dead waits for the scores, then goes).
  C  neither answers: after six seconds the slips show as they always did (the page never empties out because a feed is down).
  D  the slip's own link (/b/?p=) says it is off Social when a leg lost; an unknown player is never called a miss.
  E  Today's "Top on Social" lists only slips it knows are alive.
Serves SITE (default ./site).   python3 tests/social_gone.py [shots_dir]"""
import asyncio, json, os, re, sys, threading, http.server, functools, time
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("SITE") or os.path.join(HERE, "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8887
now = int(time.time() * 1000); PAST = now - 20 * 3600e3; RECENT = now - 3 * 3600e3; FUT = now + 5 * 3600e3
WEEK = int(re.search(r"var W = (\d+),", open(os.path.join(ROOT, "social", "index.html")).read()).group(1))
ME = "00000000-0000-0000-0000-0000000000aa"
U = lambda i: "00000000-0000-0000-0000-0000000000%02d" % i
def iso(ms): return __import__("datetime").datetime.fromtimestamp(ms / 1000, __import__("datetime").timezone.utc).isoformat()   # the database returns timestamptz as text
def leg(pl, m, ln, g, ko, o=-150, gl=None): d = {"pl": pl, "m": m, "ln": ln, "g": g, "ko": ko, "o": o, "k": f"{pl}|{m}|{ln}"}; d.update({"gl": gl} if gl else {}); return d
def post(i, uid, h, title, legs, score=0, week=WEEK, result=None):   # column types as in sql/social_v3.sql: result text, units numeric, tails int, rx jsonb, kickoffs timestamptz (text)
    return {"id": i, "user_id": uid, "status": "open", "tails": 0, "rx": {}, "result": result, "units": (-1 if result == "lost" else 1.5 if result == "won" else 0 if result else None), "handle": h, "title": title,
            "week": week, "legs": legs, "fd_odds": 300 + i, "first_ko": iso(min(l["ko"] for l in legs)), "last_ko": iso(max(l["ko"] for l in legs)), "score": score, "created_at": iso(now - 3600e3 - i * 1000)}
D = "CIN-PIT"; F = "BAL-LAC"; R = "DAL-NYG"      # finished yesterday / still to come / kicked off three hours ago and final
POSTS = [post(1, U(1), "opener", "Tonight", [leg("Justin Herbert", "Passing Yards", 175, F, FUT)], 5),
         post(2, U(2), "winner", "SNF four", [leg("Joe Burrow", "Passing Yards", 250, D, PAST), leg("Ja'Marr Chase", "Anytime TD", 1, D, PAST), leg("Over 41.5", "Total", 41.5, D, PAST, gl={"k": "T", "side": "OVER"})], 3),
         post(3, U(3), "loser", "Two TDs", [leg("Ja'Marr Chase", "2+ TD", 1, D, PAST), leg("Joe Burrow", "Passing TDs", 1, D, PAST)], 9),
         post(4, U(4), "ghost", "Not in box", [leg("Nobody Here", "Receptions", 2, D, PAST)], 8),
         post(5, U(5), "onrecord", "Lost on record", [leg("Joe Burrow", "Passing Yards", 250, D, PAST)], 7, result="lost"),
         post(6, U(6), "pusher", "Push on record", [leg("PIT +20", "Spread", 20, D, PAST, gl={"k": "M", "side": "PIT"})], 6, result="push"),
         post(7, U(7), "mixed", "One down one to go", [leg("Joe Burrow", "Passing Yards", 450, D, PAST), leg("Derrick Henry", "Rushing Yards", 60, F, FUT)], 10),
         post(8, ME, "MeUser", "Mine and dead", [leg("Joe Burrow", "Passing Yards", 500, D, PAST)], 0),
         post(9, ME, "MeUser", "Mine and open", [leg("Zay Flowers", "Receiving Yards", 50, F, FUT)], 0),
         post(10, U(10), "alive", "One hit one to go", [leg("Joe Burrow", "Passing Yards", 250, D, PAST), leg("Derrick Henry", "Anytime TD", 1, F, FUT)], 4),
         post(11, U(11), "fresh", "Just cashed", [leg("Dak Prescott", "Passing Yards", 200, R, RECENT)], 2)]
OLD = [post(20, U(1), "opener", "Old winner", [leg("Travis Kelce", "Receiving Yards", 50, "NYJ-KC", PAST - 7 * 864e5)], 2, week=WEEK - 1, result="won"),
       post(21, U(1), "opener", "Old loser", [leg("Travis Kelce", "Receiving Yards", 90, "NYJ-KC", PAST - 7 * 864e5)], 2, week=WEEK - 1, result="lost"),
       post(22, U(1), "opener", "Old and never graded", [leg("Travis Kelce", "First TD", 1, "NYJ-KC", PAST - 7 * 864e5)], 2, week=WEEK - 1)]
GONE = ["p3", "p4", "p5", "p6", "p7", "p8"]      # never drawn anywhere on Social
SCORE = {"events": [{"id": "E1", "status": {"type": {"state": "post"}}, "competitions": [{"competitors": [{"team": {"abbreviation": "CIN"}, "score": "38"}, {"team": {"abbreviation": "PIT"}, "score": "18"}]}]},
                    {"id": "E2", "status": {"type": {"state": "pre"}}, "competitions": [{"competitors": [{"team": {"abbreviation": "BAL"}, "score": "0"}, {"team": {"abbreviation": "LAC"}, "score": "0"}]}]},
                    {"id": "E3", "status": {"type": {"state": "post"}}, "competitions": [{"competitors": [{"team": {"abbreviation": "DAL"}, "score": "27"}, {"team": {"abbreviation": "NYG"}, "score": "20"}]}]}]}
def ath(n, st): return {"athlete": {"displayName": n}, "stats": st}
SUM = {"E1": {"boxscore": {"players": [{"statistics": [{"name": "passing", "keys": ["passingYards", "passingTouchdowns"], "athletes": [ath("Joe Burrow", ["409", "3"])]},
              {"name": "receiving", "keys": ["receptions", "receivingYards", "longReception", "receivingTouchdowns"], "athletes": [ath("Ja'Marr Chase", ["11", "231", "60", "1"])]}]}]}, "scoringPlays": []},
       "E3": {"boxscore": {"players": [{"statistics": [{"name": "passing", "keys": ["passingYards", "passingTouchdowns"], "athletes": [ath("Dak Prescott", ["288", "2"])]}]}]}, "scoringPlays": []}}
BOXFILE = {"week": WEEK, "final": False, "games": {D: [38, 18]}, "box": {"Joe Burrow": [409, 3, 0, 0, 0, 0, 0, 0, 0], "Ja'Marr Chase": [0, 0, 0, 0, 0, 11, 231, 1, 60]}}
LASTBOX = {"week": WEEK - 1, "final": True, "games": {"NYJ-KC": [12, 35]}, "box": {"Travis Kelce": [0, 0, 0, 1, 1, 4, 72, 0, 38]}}
FAKE = """window.__POSTS = %s;
window.__EVER = {};   // every slip card that was ever on the page, however briefly
new MutationObserver(function(ms){ ms.forEach(function(m){ [].forEach.call(m.addedNodes, function(n){ if(n.nodeType !== 1) return; var a = n.matches && n.matches('article.post') ? [n] : [].slice.call(n.querySelectorAll ? n.querySelectorAll('article.post') : []); a.forEach(function(x){ window.__EVER[x.id] = 1; }); }); }); }).observe(document, {childList: true, subtree: true});
function Q(rows, t){ var f = {}, q = {select: function(){ return q; }, eq: function(k, v){ f[k] = v; return q; }, gte: function(){ return q; }, in: function(){ return q; }, order: function(){ return q; }, limit: function(){ return q; },
  insert: function(){ return Promise.resolve({error: null}); }, upsert: function(){ return Promise.resolve({error: null}); }, delete: function(){ return q; },
  pick: function(){ return rows.filter(function(p){ return ['week', 'user_id', 'id', 'result'].every(function(k){ return f[k] == null || !(k in p) || p[k] === f[k]; }); }).slice().sort(function(a, b){ return (b.score || 0) - (a.score || 0); }); },
  maybeSingle: function(){ return Promise.resolve({data: q.pick()[0] || null, error: null}); },
  then: function(cb, eb){ return Promise.resolve({data: q.pick(), error: null}).then(cb, eb); }}; return q; }
var SIGNED = false; try { SIGNED = !!localStorage.getItem("t_user"); } catch(e){}
var CLIENT = {auth: {getSession: function(){ return Promise.resolve({data: {session: null}}); }, onAuthStateChange: function(){ return {data: {subscription: {unsubscribe: function(){}}}}; }},
  rpc: function(n){ return Promise.resolve({data: n === 'feed_profile_me' ? {user_id: "%s", handle: "MeUser", color: 4, emoji: null} : null, error: null}); },
  from: function(t){ return t === 'feed_posts' ? Q(window.__POSTS, t) : Q([], t); }};
window.bsAccount = {user: SIGNED ? {id: "%s"} : null, client: CLIENT};
try { if(localStorage.getItem("t_stub")) window.supabase = {createClient: function(){ return CLIENT; }}; } catch(e){}""" % (json.dumps(POSTS + OLD), ME, ME)
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
IDS = "Array.from(document.querySelectorAll('#feed article.post')).map(a => a.id)"
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{PORT}"
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def ctx_for(theme, espn="slow", file=False, vp=(390, 844), stub=False, user=False, sort=None):
            phone = vp[0] < 700
            ctx = await b.new_context(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=2 if phone else 1, is_mobile=phone, has_touch=phone)
            pre = f"try{{localStorage.setItem('bs_theme','{theme}');" + ("localStorage.setItem('t_stub','1');" if stub else "") + ("localStorage.setItem('t_user','1');" if user else "") + (f"if(!localStorage.getItem('t_sorted')){{localStorage.setItem('t_sorted','1');localStorage.setItem('bs_social_sort','{sort}');}}" if sort else "") + "}catch(e){}"
            await ctx.add_init_script(pre + FAKE)
            async def on_espn(route):
                if espn == "down": await route.abort(); return
                if espn == "slow": await asyncio.sleep(1.3)
                u = route.request.url; m = re.search(r"event=(\w+)", u)
                await route.fulfill(status=200, content_type="application/json", body=json.dumps(SCORE if "scoreboard" in u else SUM.get(m.group(1) if m else "", {"boxscore": {"players": []}})))
            await ctx.route("**/site.api.espn.com/**", on_espn)
            # the week's data files are the test's own, so the real build's games can never leak into it
            await ctx.route("**/data/weeks.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps({"weeks": [WEEK - 1] + ([WEEK] if file else [])})))
            await ctx.route("**/data/box-w*.json", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(BOXFILE if f"box-w{WEEK}.json" in r.request.url else LASTBOX)))
            await ctx.route("**/cdn.jsdelivr.net/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            return ctx, pg, errs
        ever = lambda pg: pg.evaluate("Object.keys(window.__EVER).sort()")

        # ---------------- A: the Social page, scores answering slowly ----------------
        for theme, vp in (("light", (390, 844)), ("dark", (390, 844)), ("light", (1280, 800))):
            tag = f"{theme} {vp[0]}"
            ctx, pg, errs = await ctx_for(theme, vp=vp)
            await pg.goto(base + "/social/", wait_until="domcontentloaded"); await pg.wait_for_selector("#p1", timeout=8000); await pg.wait_for_timeout(250)
            h0 = await pg.evaluate("({ids: %s, hold: !!document.querySelector('#feed .lede.hold'), info: document.getElementById('feedinfo').textContent})" % IDS)
            check(sorted(h0["ids"]) == ["p1", "p9"] and h0["hold"] and "2 open slips" in h0["info"], f"[{tag}] while the scores are on their way only the slips that have not kicked off are drawn, with a placeholder for the rest ({h0})")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/gone-hold-{theme}-{vp[0]}.png")
            await pg.wait_for_timeout(4200)
            a1 = await pg.evaluate("({ids: %s, hold: !!document.querySelector('#feed .lede.hold'), info: document.getElementById('feedinfo').textContent, tabs: Array.from(document.querySelectorAll('.soc .seg button')).map(b => b.dataset.s), cashed: document.querySelector('.seg button[data-s=\"cashed\"]').textContent, over: document.documentElement.scrollWidth - document.documentElement.clientWidth, rules: document.querySelector('.soc .rules').textContent})" % IDS)
            check(a1["ids"] == ["p1", "p10", "p9"] and not a1["hold"] and "3 open slips" in a1["info"] and "2 cashed" in a1["info"], f"[{tag}] once the scores are in, Top is the slips still alive, most upvotes first - the busted ones with more upvotes are not there ({a1['ids']}, {a1['info']})")
            check(a1["tabs"] == ["top", "new", "following", "cashed", "sharp"] and a1["cashed"] == "Cashed 2" and a1["over"] == 0, f"[{tag}] five tabs, no Lost tab, no sideways scroll ({a1['tabs']}, {a1['cashed']})")
            check("comes off Social" in a1["rules"] and "Lost" not in a1["rules"], f"[{tag}] the how-it-works line says a slip that loses a leg comes off Social")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/gone-top-{theme}-{vp[0]}.png")
            await pg.click('.seg button[data-s="new"]'); await pg.wait_for_timeout(300); n1 = await pg.evaluate(IDS)
            await pg.click('.seg button[data-s="cashed"]'); await pg.wait_for_timeout(300); c1 = await pg.evaluate(IDS)
            check(sorted(n1) == ["p1", "p10", "p9"] and sorted(c1) == ["p11", "p2"], f"[{tag}] New has the same three; Cashed has the two winners ({n1}, {c1})")
            ev = await ever(pg)
            check(not [x for x in ev if x in GONE], f"[{tag}] a slip with a dead leg, a lost or pushed result, or its games over without a win was never on the page, not even for a moment (ever drawn: {ev})")
            # one game: the finished one keeps its winner only; the one to come leaves out the slip that already lost a leg elsewhere
            await pg.goto(base + "/social/?a=1#g=" + D, wait_until="domcontentloaded"); await pg.wait_for_timeout(4600)
            g1 = await pg.evaluate("({ids: %s, info: document.getElementById('feedinfo').textContent})" % IDS)
            await pg.goto(base + "/social/?a=2#g=" + F, wait_until="domcontentloaded"); await pg.wait_for_timeout(4600)
            g2 = await pg.evaluate("({ids: %s, info: document.getElementById('feedinfo').textContent})" % IDS)
            check(g1["ids"] == ["p10", "p2"] and "2 slips on this game" in g1["info"] and "1 open" in g1["info"] and "1 cashed" in g1["info"] and "lost" not in g1["info"], f"[{tag}] a finished game's view: the slip still alive and the winner, nothing lost ({g1})")
            check(g2["ids"] == ["p1", "p10", "p9"] and "3 slips on this game" in g2["info"], f"[{tag}] a coming game's view leaves out the slip that already lost a leg in another game ({g2})")
            check(not [x for x in await ever(pg) if x in GONE] and not errs, f"[{tag}] ... and none of the lost ones was drawn on the way; no script errors {errs[:2]}")
            await ctx.close()

        # ---------------- A2: profiles, the saved Lost tab ----------------
        for theme in ("light", "dark"):
            ctx, pg, errs = await ctx_for(theme, espn="fast", user=True, sort="lost")
            await pg.goto(base + "/social/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600)
            s0 = await pg.evaluate("({on: Array.from(document.querySelectorAll('.soc .seg button.on')).map(b => b.dataset.s), ids: %s})" % IDS)
            check(s0["on"] == ["top"] and s0["ids"] == ["p1", "p10", "p9"], f"[{theme}] a reader whose saved tab was Lost lands on Top ({s0})")
            PROF = "(function(){ var s = document.querySelector('.prof'); return s ? {name: s.querySelector('h2').firstChild.textContent, line: s.querySelector('.pn p').textContent, ids: %s, empty: (document.querySelector('#feed .empty') || {}).textContent || '', note: (document.querySelector('#feed .offnote') || {}).textContent || '', over: document.documentElement.scrollWidth - document.documentElement.clientWidth} : null; })()" % IDS
            await pg.goto(base + "/social/?b=1#u=" + U(1), wait_until="domcontentloaded"); await pg.wait_for_timeout(2600); p1 = await pg.evaluate(PROF)
            check(p1 and p1["name"] == "@opener" and p1["ids"] == ["p1", "p20"] and "2 slips on Social" in p1["line"] and "posted" not in p1["line"] and not p1["note"], f"[{theme}] a profile lists the open slip and the old winner - not the old loser, not the old slip nobody graded - and counts the two it lists ({p1})")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/gone-profile-{theme}.png")
            await pg.goto(base + "/social/?b=2#u=" + U(3), wait_until="domcontentloaded"); await pg.wait_for_timeout(2600); p3 = await pg.evaluate(PROF)
            check(p3 and p3["ids"] == [] and "No open or cashed slips right now." in p3["empty"] and "slip" not in p3["line"] and not p3["note"], f"[{theme}] a poster whose only slip lost: no slip, no count, no note for a visitor ({p3})")
            await pg.goto(base + "/social/?b=3#u=" + ME, wait_until="domcontentloaded"); await pg.wait_for_timeout(2600); pm = await pg.evaluate(PROF)
            check(pm and pm["ids"] == ["p9"] and "1 slip on Social" in pm["line"] and "comes off Social once a leg loses" in pm["note"] and pm["over"] == 0, f"[{theme}] my own page: my dead slip is gone for me too, and one line says why ({pm})")
            if SHOTS: await pg.evaluate("document.querySelector('#feed .offnote').scrollIntoView({block: 'center'})"); await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/gone-mine-{theme}.png")
            check(not [x for x in await ever(pg) if x in GONE] and not errs, f"[{theme}] no lost slip on any profile; no script errors {errs[:2]}")
            await ctx.close()

        # ---------------- B: the scores feed down, the box file up ----------------
        ctx, pg, errs = await ctx_for("dark", espn="down", file=True)
        await pg.goto(base + "/social/", wait_until="domcontentloaded"); await pg.wait_for_selector("#p1", timeout=8000); await pg.wait_for_timeout(1500)
        b0 = await pg.evaluate("({ids: %s, hold: !!document.querySelector('#feed .lede.hold'), cashed: document.querySelector('.seg button[data-s=\"cashed\"]').textContent})" % IDS)
        check(b0["ids"] == ["p1", "p10", "p9"] and b0["hold"] and b0["cashed"] == "Cashed 1", f"with the scores feed down the week's box file settles yesterday's game at once: the alive slip and the winner are placed, a touchdown leg the file calls dead still waits ({b0})")
        await pg.wait_for_timeout(5600)
        b1 = await pg.evaluate("({ids: %s, hold: !!document.querySelector('#feed .lede.hold')})" % IDS); ev = await ever(pg)
        check(b1["ids"] == ["p1", "p10", "p11", "p9"] and not b1["hold"] and not [x for x in ev if x in GONE] and not errs, f"... and after the wait the lost ones are still nowhere; the slip whose game the file does not have shows as it always did ({b1}, ever drawn: {ev}) {errs[:2]}")
        await ctx.close()

        # ---------------- C: neither answers ----------------
        ctx, pg, errs = await ctx_for("light", espn="down")
        await pg.goto(base + "/social/", wait_until="domcontentloaded"); await pg.wait_for_selector("#p1", timeout=8000); await pg.wait_for_timeout(2500)
        c0 = await pg.evaluate("({ids: %s, hold: !!document.querySelector('#feed .lede.hold')})" % IDS)
        await pg.wait_for_timeout(4800); c1 = await pg.evaluate("({ids: %s, hold: !!document.querySelector('#feed .lede.hold')})" % IDS)
        check(sorted(c0["ids"]) == ["p1", "p9"] and c0["hold"] and not c1["hold"] and set(c1["ids"]) == {"p1", "p2", "p3", "p4", "p7", "p8", "p9", "p10", "p11"} and not errs,
              f"with no scores and no box file the page waits six seconds, then shows the slips as it always did - only the ones lost on record stay off ({c0['ids']} -> {c1['ids']}) {errs[:2]}")
        await ctx.close()

        # ---------------- D: the slip's own link ----------------
        async def slip(pg, n, x):
            await pg.goto(f"{base}/b/?p={n}&t={x}", wait_until="domcontentloaded")
            try: await pg.wait_for_function("(function(){ var t = (document.getElementById('blDyn') || {}).textContent || ''; return t && t.indexOf('Loading the slip') < 0; })()", timeout=9000)
            except Exception: pass
            return await pg.evaluate("(function(){ var b = document.getElementById('blDyn'), h = b.querySelector('h1'), n = b.querySelector('.none'); return {h1: h ? h.textContent : null, none: n ? n.textContent : null, link: n && n.querySelector('a') ? n.querySelector('a').getAttribute('href') : null}; })()")
        for theme in ("light", "dark"):
            ctx, pg, errs = await ctx_for(theme, espn="fast", stub=True)
            r = {n: await slip(pg, n, theme) for n in (1, 2, 3, 4, 5, 7, 10, 999)}
            check(r[1]["h1"] == "Tonight" and r[2]["h1"] == "SNF four" and r[10]["h1"] == "One hit one to go", f"[{theme}] the link of an open slip, a winner and a slip still alive opens the slip ({[r[n]['h1'] for n in (1, 2, 10)]})")
            check(all(r[n]["h1"] is None and "off Social - one of its legs lost" in (r[n]["none"] or "") and r[n]["link"] == "/social/" for n in (3, 5, 7)), f"[{theme}] the link of a slip that lost a leg (graded live, lost on record, one game still to come) says it is off Social and points at what is open ({[r[n]['none'] for n in (3, 5, 7)]})")
            check(r[4]["h1"] == "Not in box" and r[999]["h1"] is None and "This post is gone" in (r[999]["none"] or ""), f"[{theme}] a player the box score does not list is never called a miss; a post that does not exist says it is gone ({r[4]}, {r[999]['none']})")
            if SHOTS: await slip(pg, 3, theme + "s"); await pg.screenshot(path=f"{SHOTS}/gone-link-{theme}.png")
            check(not errs, f"[{theme}] no script errors on the slip page {errs[:2]}")
            await ctx.close()
        ctx, pg, errs = await ctx_for("light", espn="down", file=True, stub=True)
        r7, r3, r11 = await slip(pg, 7, "f"), await slip(pg, 3, "f"), await slip(pg, 11, "f")
        check("off Social" in (r7["none"] or "") and r3["h1"] == "Two TDs" and r11["h1"] == "Just cashed" and not errs, f"with only the box file to go on: a yards leg it has as missed takes the link down; a touchdown leg it calls dead does not (the file has no return touchdowns); a game nobody could read shows the slip ({r7['none']}, {r3['h1']}, {r11['h1']}) {errs[:2]}")
        await ctx.close()

        # ---------------- E: Today's strip ----------------
        ROWS = "(function(){ var s = document.getElementById('socstrip'); if(!s) return null; return {hidden: s.hidden, rows: Array.from(s.querySelectorAll('a.ssp')).map(function(a){ return a.getAttribute('href').replace('/b/?p=', 'p') + ' ' + a.querySelector('.w small').textContent; }), all: s.querySelector('.seeall').textContent, empty: (s.querySelector('.ssempty b') || {}).textContent || ''}; })()"
        for theme in ("light", "dark"):
            ctx, pg, errs = await ctx_for(theme, espn="fast")
            await pg.goto(base + "/?e=1", wait_until="domcontentloaded"); await pg.wait_for_timeout(3000); s1 = await pg.evaluate(ROWS)
            check(s1 and not s1["hidden"] and [x.split(" ")[0] for x in s1["rows"]] == ["p1", "p10", "p11"] and s1["all"] == "All 4 slips", f"[{theme}] Today lists the top slips that are alive - the most-upvoted one lost a leg yesterday and is not there ({s1})")
            check(s1 and s1["rows"][1].endswith("· live") and s1["rows"][2].endswith("· cashed") and "live" not in s1["rows"][0], f"[{theme}] ... a slip in play says live, one that just cashed says cashed, one that has not kicked off says neither")
            if SHOTS: await pg.evaluate("document.getElementById('socstrip').scrollIntoView({block: 'center'})"); await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/gone-today-{theme}.png")
            check(not errs, f"[{theme}] no script errors on Today {errs[:2]}")
            await ctx.close()
        ctx, pg, errs = await ctx_for("light", espn="down")
        await pg.goto(base + "/?e=2", wait_until="domcontentloaded"); await pg.wait_for_timeout(3000); s2 = await pg.evaluate(ROWS)
        check(s2 and [x.split(" ")[0] for x in s2["rows"]] == ["p1", "p9"] and s2["all"] == "Open Social" and not errs, f"with no scores and no box file the strip lists only what has not kicked off: a slip it cannot check is left out ({s2}) {errs[:2]}")
        await ctx.close()
        ctx, pg, errs = await ctx_for("light", espn="down", file=True)
        await pg.goto(base + "/?e=3", wait_until="domcontentloaded"); await pg.wait_for_timeout(3000); s3 = await pg.evaluate(ROWS)
        check(s3 and [x.split(" ")[0] for x in s3["rows"]] == ["p1", "p10", "p9"] and not errs, f"with the box file alone the slip whose first leg hit yesterday is back on the strip and the one whose first leg missed stays off ({s3}) {errs[:2]}")
        await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
