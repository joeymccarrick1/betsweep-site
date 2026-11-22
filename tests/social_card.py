"""The buttons on a Social slip card (owner 11/22 11:40 AM, with a phone screenshot of his own post: "Make these buttons on the slip on
social just look a little better. They look like they're onto of each other and can be organized better").

What the card's action area is now, top to bottom:
  1  Tail on FanDuel, the one filled button, the full width of the card. On somebody else's slip "I'm tailing" sits beside it.
  2  Save slip and Load into my slip, two equal buttons on one row.
  3  a quiet last line: when it kicks off (or Live / Cashed / Busted) on the left; Delete or Report, then Open slip, on the right.
The test measures that on a 390x844 phone in light and dark and on a desktop, in every state a card has: my own open slip (the owner's
screenshot), somebody else's, a slip with no FanDuel link, a live slip, a cashed and a busted one, and Delete after its first tap.

Serves SITE (default ./site), fakes the account client and the score feed.   python3 tests/social_card.py [shots_dir]"""
import asyncio, json, os, re, sys, threading, http.server, functools, time
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("SITE") or os.path.join(HERE, "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8881
now = int(time.time() * 1000); PAST = now - 2 * 3600e3; FUT = now + 5 * 3600e3
WEEK = int(re.search(r"var W = (\d+),", open(os.path.join(ROOT, "social", "index.html")).read()).group(1))
ME = "00000000-0000-0000-0000-0000000000aa"
def iso(ms): return __import__("datetime").datetime.fromtimestamp(ms / 1000, __import__("datetime").timezone.utc).isoformat()
def leg(pl, m, ln, g, ko, o=-150, fd=True, n=[0]):
    n[0] += 1; d = {"pl": pl, "m": m, "ln": ln, "g": g, "ko": ko, "o": o, "k": f"{pl}|{m}|{ln}"}
    if fd: d["fd"] = {"m": "42.%d" % (626000000 + n[0]), "s": str(48000000 + n[0])}
    return d
def post(i, uid, h, title, legs, score=0, tails=0, rx=None, week=WEEK):
    return {"id": i, "user_id": uid, "tails": tails, "rx": rx or {}, "result": None, "units": None, "handle": h, "title": title, "week": week, "legs": legs, "fd_odds": 300 + i,
            "first_ko": iso(min(l["ko"] for l in legs)), "last_ko": iso(max(l["ko"] for l in legs)), "score": score, "created_at": iso(now - 3600e3)}
U = lambda i: "00000000-0000-0000-0000-00000000000%d" % i
three = lambda g, fd=True: [leg("James Cook", "Anytime TD", 1, g, FUT, -185, fd), leg("Bo Nix", "Passing Yards", 200, g, FUT, -172, fd), leg("Garrett Wilson", "Receiving Yards", 60, g, FUT, -148, fd)]
POSTS = [post(1, U(1), "opener", "Sunday three", three("BAL-LAC"), 5, tails=2, rx={"fire": 3}),
         post(5, ME, "MeUser", "Daily Sweep: Let Him Cook", three("BAL-LAC"), 4, rx={"fire": 1, "lock": 2}),
         post(6, U(6), "nolink", "By hand", [leg("Nobody Here", "Receiving Yards", 40, "BAL-LAC", FUT, -150, False), leg("Someone Else", "Rushing Yards", 50, "BAL-LAC", FUT, -140, False)], 2),
         post(7, U(7), "livewire", "One down", [leg("CeeDee Lamb", "Receiving Yards", 60, "DAL-PHI", PAST), leg("Justin Herbert", "Passing Yards", 225, "BAL-LAC", FUT)], 1),
         post(2, U(2), "winner", "SNF two", [leg("Joe Burrow", "Passing Yards", 250, "CIN-PIT", PAST - 20 * 3600e3), leg("Ja'Marr Chase", "Anytime TD", 1, "CIN-PIT", PAST - 20 * 3600e3)], 3),
         post(3, U(3), "loser", "Two TDs", [leg("Ja'Marr Chase", "2+ TD", 1, "CIN-PIT", PAST - 20 * 3600e3)], 1)]
def ev(i, a, b, st, sa="0", sb="0"): return {"id": i, "status": {"type": {"state": st}}, "competitions": [{"competitors": [{"team": {"abbreviation": a}, "score": sa}, {"team": {"abbreviation": b}, "score": sb}]}]}
SCORE = {"events": [ev("E1", "CIN", "PIT", "post", "38", "18"), ev("E2", "BAL", "LAC", "pre"), ev("E3", "DAL", "PHI", "in", "7", "3")]}
def ath(n, st): return {"athlete": {"displayName": n}, "stats": st}
SUMMARY = {"boxscore": {"players": [{"statistics": [{"name": "passing", "keys": ["passingYards", "passingTouchdowns"], "athletes": [ath("Joe Burrow", ["409", "3"])]},
            {"name": "receiving", "keys": ["receptions", "receivingYards", "longReception", "receivingTouchdowns"], "athletes": [ath("Ja'Marr Chase", ["11", "231", "60", "1"]), ath("CeeDee Lamb", ["2", "21", "12", "0"])]}]}]}, "scoringPlays": []}
FAKE = """window.__POSTS = %s; window.__CALLS = [];
var ME = "%s", T = {feed_records: [], feed_profiles: [{user_id: ME, handle: "MeUser", color: 4}], feed_tails: [], feed_reactions: [], feed_follows: []};
function Q(rows, t){ var f = {}, q = {select: function(){ return q; }, eq: function(k, v){ f[k] = v; if(t === 'feed_posts' && k === 'result') rows = []; return q; }, gte: function(){ return q; }, in: function(){ return q; }, order: function(){ return q; }, limit: function(){ return q; },
  insert: function(o){ window.__CALLS.push(t + ':insert'); return Promise.resolve({error: null}); }, upsert: function(o){ window.__CALLS.push(t + ':upsert'); return Promise.resolve({error: null}); },
  delete: function(){ window.__CALLS.push(t + ':delete'); return q; },
  then: function(cb){ var r = rows.filter(function(p){ return (f.week == null || p.week === f.week) && (f.user_id == null || p.user_id === f.user_id || t !== 'feed_posts' && t !== 'feed_records' && t !== 'feed_profiles'); }); return Promise.resolve({data: r, error: null}).then(cb); }}; return q; }
window.bsAccount = {user: {id: ME}, client: {rpc: function(n, a){ window.__CALLS.push('rpc:' + n); return Promise.resolve({data: {user_id: ME, handle: "MeUser", color: 4, emoji: null}, error: null}); },
  from: function(t){ return t === 'feed_posts' ? Q(window.__POSTS, t) : Q(T[t] || [], t); }}};""" % (json.dumps(POSTS), ME)
# every control of a card's action area, measured in screen pixels (the site zooms 1.1x on a phone, so these are what a thumb meets)
MEASURE = """(id) => { var c = document.getElementById(id); if(!c) return null;
  function box(e){ if(!e) return null; var r = e.getBoundingClientRect(), s = getComputedStyle(e); return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height, cy: (r.top + r.bottom) / 2, txt: e.textContent.trim(),
    wrap: e.scrollWidth > e.clientWidth + 1, bg: s.backgroundColor, fs: parseFloat(s.fontSize), tt: s.textTransform, lines: Math.round(r.height / (parseFloat(s.lineHeight) || r.height))}; }
  var pf = c.querySelector('.pf'), cs = getComputedStyle(pf), pr = pf.getBoundingClientRect(), z = pr.width / pf.offsetWidth;
  return {card: box(c), in: {l: pr.left + parseFloat(cs.paddingLeft) * z, r: pr.right - parseFloat(cs.paddingRight) * z}, zoom: z,
    rx: box(c.querySelector('.rx')), fd: box(c.querySelector('.pf a.fd')), tail: box(c.querySelector('[data-tail]')), save: box(c.querySelector('[data-save]')), load: box(c.querySelector('[data-load]')),
    del: box(c.querySelector('[data-del]')), rep: box(c.querySelector('[data-rep]')), open: box(c.querySelector('.pf a.open')), st: box(c.querySelector('.pf .st')), res: box(c.querySelector('.pf .res')),
    foot: box(c.querySelector('.pf .pm')), note: box(c.querySelector('.pf a.fd small')), sx: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
def near(a, b, tol=1.5): return abs(a - b) <= tol
def apart(*bs):   # no two of these boxes touch or overlap
    bs = [b for b in bs if b]
    return all(a["r"] <= b["l"] + 0.5 or b["r"] <= a["l"] + 0.5 or a["b"] <= b["t"] + 0.5 or b["b"] <= a["t"] + 0.5 for i, a in enumerate(bs) for b in bs[i + 1:])
def inside(m, *bs): return all(b["l"] >= m["in"]["l"] - 1 and b["r"] <= m["in"]["r"] + 1 for b in bs if b)

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme, vw, vh, phone in (("light", 390, 844, True), ("dark", 390, 844, True), ("dark", 1280, 900, False), ("dark", 320, 640, True)):
            narrow = vw < 360   # the smallest phones: a label may take two lines there; nothing may collide or leave the card
            tag = f"{theme} {'small phone' if narrow else 'phone' if phone else 'desktop'}"
            ctx = await b.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=2, is_mobile=phone, has_touch=phone)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + FAKE)
            async def espn(route):
                u = route.request.url; await route.fulfill(status=200, content_type="application/json", body=json.dumps(SCORE if "scoreboard" in u else SUMMARY))
            await ctx.route("**/site.api.espn.com/**", espn)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/social/", wait_until="domcontentloaded"); await pg.wait_for_timeout(3200)
            ids = await pg.evaluate("Array.from(document.querySelectorAll('#feed > article.post')).map(a => a.id)")
            check(set(ids) == {"p1", "p5", "p6", "p7"}, f"[{tag}] the feed shows the four slips still in play ({ids})")
            async def shot(i, name):
                if not SHOTS: return
                await pg.evaluate("(i) => { var c = document.getElementById(i), r = c.getBoundingClientRect(); window.scrollBy(0, r.top - Math.max(70, (innerHeight - r.height) / 2)); }", i); await pg.wait_for_timeout(120)
                r = await pg.evaluate("(i) => { var r = document.getElementById(i).getBoundingClientRect(); return {x: r.left, y: Math.max(0, r.top), width: r.width, height: Math.min(r.bottom, innerHeight) - Math.max(0, r.top)}; }", i)
                await pg.screenshot(path=f"{SHOTS}/card-{name}-{theme}-{'small' if narrow else 'phone' if phone else 'desk'}.png", clip=r)

            # ---- my own open slip: the owner's screenshot ----
            m = await pg.evaluate(MEASURE, "p5"); await shot("p5", "mine"); W = m["in"]["r"] - m["in"]["l"]
            check(m["sx"] <= 0, f"[{tag}] the page does not scroll sideways ({m['sx']})")
            check(bool(m["fd"] and m["save"] and m["load"] and m["del"] and m["open"] and m["st"]) and not m["tail"] and not m["rep"], f"[{tag}] my slip: Tail on FanDuel, Save slip, Load into my slip, Delete, Open slip and the kickoff are all there")
            if phone:
                check(near(m["fd"]["l"], m["in"]["l"]) and near(m["fd"]["r"], m["in"]["r"]), f"[{tag}] my slip: Tail on FanDuel is the full width of the card ({m['fd']['w']:.0f} of {W:.0f})")
                check(near(m["save"]["l"], m["in"]["l"]) and near(m["load"]["r"], m["in"]["r"]), f"[{tag}] my slip: Save and Load fill the row edge to edge")
            else:
                check(m["fd"]["w"] <= 340 and m["save"]["w"] <= 340, f"[{tag}] my slip: on a wide screen the buttons keep a button's width ({m['fd']['w']:.0f}, {m['save']['w']:.0f})")
            check(near(m["save"]["t"], m["load"]["t"]) and near(m["save"]["h"], m["load"]["h"]) and near(m["save"]["w"], m["load"]["w"], 2), f"[{tag}] my slip: Save slip and Load into my slip are one row of two equal buttons ({m['save']['w']:.0f} / {m['load']['w']:.0f})")
            gap = m["load"]["l"] - m["save"]["r"]
            check(6 <= gap <= 14, f"[{tag}] my slip: the two buttons have a clear gap between them ({gap:.1f}px)")
            MINH = 44 if phone else 40   # a thumb's 44px on a phone; the site's own button height with a mouse
            check(min(m["fd"]["h"], m["save"]["h"], m["load"]["h"]) >= MINH, f"[{tag}] my slip: every button is at least {MINH}px tall ({m['fd']['h']:.0f}, {m['save']['h']:.0f}, {m['load']['h']:.0f})")
            check(not (m["fd"]["wrap"] or m["save"]["wrap"] or m["load"]["wrap"]) and (narrow or near(m["save"]["h"], m["fd"]["h"], 2)), f"[{tag}] my slip: no button's words are cut{'' if narrow else ' or wrapped'}")
            rows = [m["rx"], m["fd"], m["save"], m["foot"]] if phone else [m["rx"], m["fd"], m["foot"]]
            gaps = [round(rows[i + 1]["t"] - rows[i]["b"], 1) for i in range(len(rows) - 1)]
            check(all(7 <= g <= 20 for g in gaps), f"[{tag}] my slip: reactions, buttons and the last line each sit clear of the row above ({gaps})")
            check(apart(m["fd"], m["save"], m["load"], m["del"], m["open"], m["st"]), f"[{tag}] my slip: no two controls touch")
            check(inside(m, m["fd"], m["save"], m["load"], m["del"], m["open"], m["st"]), f"[{tag}] my slip: everything stays inside the card's margins")
            one = near(m["st"]["cy"], m["open"]["cy"], 3)
            check(m["st"]["txt"].startswith("Kicks off") and (one or narrow and m["open"]["t"] >= m["st"]["b"] - 1) and near(m["del"]["cy"], m["open"]["cy"], 3), f"[{tag}] my slip: the kickoff, Delete and Open slip {'share the last line' if one else 'are the last two lines'} ({m['st']['txt']})")
            check(near(m["st"]["l"], m["in"]["l"], 2) and near(m["open"]["r"], m["in"]["r"], 2) and m["del"]["r"] < m["open"]["l"], f"[{tag}] my slip: the kickoff is on the left; Delete, then Open slip, on the right")
            check(m["open"]["l"] - m["del"]["r"] >= 12 and min(m["del"]["h"], m["open"]["h"]) >= 40, f"[{tag}] my slip: Delete and Open slip are {m['open']['l'] - m['del']['r']:.0f}px apart and {m['del']['h']:.0f}px tall to tap")
            check(m["fd"]["bg"] != m["save"]["bg"] and m["save"]["bg"] == m["load"]["bg"], f"[{tag}] my slip: one filled button, the others outlined")
            check(m["foot"]["t"] >= max(m["save"]["b"], m["fd"]["b"]) and m["st"]["fs"] <= m["save"]["fs"], f"[{tag}] my slip: the last line is under the buttons and no louder than them")

            # ---- Delete asks first: its longer words must not push anything out of the card ----
            await pg.click("#p5 [data-del]"); await pg.wait_for_timeout(150)
            a = await pg.evaluate(MEASURE, "p5"); await shot("p5", "mine-armed")
            check("tap again" in a["del"]["txt"] and inside(a, a["del"], a["open"], a["st"]) and apart(a["del"], a["open"], a["st"]) and a["sx"] <= 0, f"[{tag}] my slip: \"{a['del']['txt']}\" fits without touching its neighbours")
            check(not a["del"]["wrap"] and a["del"]["h"] <= m["del"]["h"] + 1, f"[{tag}] my slip: the question stays on one line")
            two = a["del"]["t"] >= a["st"]["b"] - 1
            check(near(a["del"]["cy"], a["open"]["cy"], 3) and near(a["open"]["r"], a["in"]["r"], 2) and (near(a["st"]["h"], a["del"]["h"], 2) if two else near(a["st"]["cy"], a["del"]["cy"], 3)), f"[{tag}] my slip: the last line stays even while it asks ({'two rows' if two else 'one row'})")
            await pg.wait_for_timeout(3100)
            check((await pg.evaluate(MEASURE, "p5"))["del"]["txt"] == "Delete" and "feed_posts:delete" not in await pg.evaluate("window.__CALLS"), f"[{tag}] my slip: left alone, it goes back to Delete and nothing is deleted")

            # ---- somebody else's slip: I'm tailing sits beside Tail on FanDuel ----
            o = await pg.evaluate(MEASURE, "p1"); await shot("p1", "theirs")
            check(bool(o["tail"] and o["fd"] and o["rep"]) and not o["del"], f"[{tag}] their slip: I'm tailing, Tail on FanDuel and Report")
            check(near(o["tail"]["t"], o["fd"]["t"]) and near(o["tail"]["h"], o["fd"]["h"]) and o["fd"]["r"] < o["tail"]["l"] and (o["fd"]["w"] > o["tail"]["w"] if phone else o["fd"]["w"] >= o["tail"]["w"] - 1), f"[{tag}] their slip: the two share a row, FanDuel first and {'wider' if phone else 'no narrower'} ({o['fd']['w']:.0f} / {o['tail']['w']:.0f})")
            check(o["tail"]["h"] >= MINH and not o["tail"]["wrap"] and o["tail"]["txt"] == "I'm tailing", f"[{tag}] their slip: I'm tailing is {o['tail']['h']:.0f}px tall, words whole")
            if phone: check(near(o["fd"]["l"], o["in"]["l"]) and near(o["tail"]["r"], o["in"]["r"]), f"[{tag}] their slip: that row runs edge to edge")
            check(apart(o["fd"], o["tail"], o["save"], o["load"], o["rep"], o["open"], o["st"]) and inside(o, o["fd"], o["tail"], o["save"], o["load"], o["rep"], o["open"], o["st"]), f"[{tag}] their slip: nothing touches, nothing leaves the card")
            await pg.click("#p1 [data-tail]"); await pg.wait_for_timeout(350)
            t = await pg.evaluate(MEASURE, "p1")
            check(t["tail"]["txt"].startswith("Tailing") and near(t["tail"]["t"], t["fd"]["t"]) and not t["tail"]["wrap"] and near(t["tail"]["w"], o["tail"]["w"], 2), f"[{tag}] their slip: after a tap it reads \"{t['tail']['txt']}\" and the row has not shifted")
            await shot("p1", "theirs-tailing")

            # ---- no FanDuel link: I'm tailing takes the row; nothing is left half-empty ----
            n = await pg.evaluate(MEASURE, "p6"); await shot("p6", "nolink")
            check(not n["fd"] and bool(n["tail"] and n["save"] and n["load"]), f"[{tag}] a slip with no FanDuel link has no FanDuel button")
            if phone: check(near(n["tail"]["l"], n["in"]["l"]) and near(n["tail"]["r"], n["in"]["r"]), f"[{tag}] ... and I'm tailing fills the row ({n['tail']['w']:.0f})")
            check(apart(n["tail"], n["save"], n["load"], n["rep"], n["open"], n["st"]), f"[{tag}] ... with nothing touching")

            # ---- a live slip: what is left to tail, no Save or Load, Live on the last line ----
            v = await pg.evaluate(MEASURE, "p7"); await shot("p7", "live")
            check(not v["save"] and not v["load"] and not v["tail"], f"[{tag}] a live slip has no Save, Load or I'm tailing")
            check(bool(v["fd"] and v["note"]) and "1 of 2 legs" in v["note"]["txt"] and v["note"]["t"] >= v["fd"]["t"] and v["note"]["b"] <= v["fd"]["b"] + 0.5 and inside(v, v["fd"]), f"[{tag}] a live slip: the FanDuel button says what is left to add, inside the button ({v['note']['txt'] if v['note'] else None})")
            check(v["st"]["txt"].startswith("Live") and (narrow or near(v["st"]["cy"], v["open"]["cy"], 3)) and apart(v["fd"], v["rep"], v["open"], v["st"]), f"[{tag}] a live slip: \"{v['st']['txt']}\" shares the last line with Open slip")

            # ---- settled slips: the result on the left, Open slip on the right, no buttons ----
            for i, word, tab in (("p2", "Cashed", "cashed"), ("p3", "Busted", "lost")):
                await pg.click(f'.seg button[data-s="{tab}"]'); await pg.wait_for_timeout(500)
                s = await pg.evaluate(MEASURE, i)
                if not s: check(False, f"[{tag}] {word}: the card is on its tab"); continue
                await shot(i, word.lower())
                check(bool(s["res"]) and s["res"]["txt"].startswith(word) and not (s["fd"] or s["save"] or s["load"] or s["tail"] or s["st"]), f"[{tag}] {word}: the result and no buttons ({s['res']['txt'] if s['res'] else None})")
                check(bool(s["res"] and s["open"]) and (narrow or near(s["res"]["cy"], s["open"]["cy"], 3)) and near(s["res"]["l"], s["in"]["l"], 2) and near(s["open"]["r"], s["in"]["r"], 2) and apart(s["res"], s["open"], s["rep"]), f"[{tag}] {word}: result left, Open slip right, one line")
            check(not errs, f"[{tag}] no script errors {errs[:2]}")
            if SHOTS and phone: await pg.click('.seg button[data-s="top"]'); await pg.wait_for_timeout(400); await pg.screenshot(path=f"{SHOTS}/feed-{theme}.png", full_page=True)
            await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
