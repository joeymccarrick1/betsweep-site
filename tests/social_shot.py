"""Post a slip to Social from a FanDuel screenshot (alpha plan step 3, 11/16). The picture reader itself (tesseract, slipimport.parse) is
stubbed - it cannot load here and has its own checks; this tests what happens with its answer: which legs may be posted, the hand-off to the
Parlay Builder, and the post form opening with the price from the picture. Page clock frozen two hours before the week's last kickoff.
  python3 tests/social_shot.py [shots_dir]"""
import asyncio, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
cards = sorted((int(k), g) for g, k in re.findall(r'<section class="card[^"]*" id="([A-Z]+-[A-Z]+)"[^>]*data-ko="(\d+)"', open(os.path.join(ROOT, "boards", "index.html")).read()))
GL, GD, T = cards[-1][1], cards[0][1], cards[-1][0] - 2 * 3600e3
WEEK = int(re.search(r'id="hsbar" data-week="(\d+)"', open(os.path.join(ROOT, "index.html")).read()).group(1))
FREEZE = "Date.now = function(){ return %d; };" % T
ACCT = """window.bsAccount = {user: {id: '00000000-0000-0000-0000-0000000000aa', email: 't@example.com'}, client: {rpc: function(){ return Promise.resolve({data: 'Tester', error: null}); },
  from: function(t){ var q = {select: function(){ return q; }, eq: function(){ return q; }, in: function(){ return q; }, order: function(){ return q; }, limit: function(){ return q; }, insert: function(r){ window.__posted = r; return {select: function(){ return Promise.resolve({data: [{id: 99}], error: null}); }}; },   // the real call is insert(row).select('id')
    then: function(cb, eb){ return Promise.resolve({data: t === 'feed_profiles' ? [{handle: 'Tester'}] : [], error: null}).then(cb, eb); }}; return q; }}};"""
# the stand-in for the reader: two legs of the week's last game (still to come), one of its first game (kicked off), one line not on the board, one unknown market
STUB = """(mode) => window.BSImport.data().then(function(BS){
  function key(l){ return l.pl + '|' + l.m + '|' + Math.round(l.ln || 1); }
  var late = BS.legs.filter(function(l){ return l.g === '%s' && !l.gl && /Yards|Receptions/.test(l.m) && !/^Under/.test(l.m); });
  // a leg whose game has kicked off: the board drops finished games' legs, so one is made from a real leg and an hour-old kickoff ('%s' is the week's first game)
  var a = late[0], b = late.filter(function(l){ return l.pl !== a.pl; })[0], c = Object.assign({}, a, {pl: 'Early Bird', g: '__early'}); BS.games['__early'] = {ko: Date.now() - 3600e3};
  function ok(l){ return {ok: true, key: key(l), leg: l, label: l.pl + ' ' + Math.round(l.ln) + '+ ' + l.m, odds: l.o}; }
  var legs = mode === 'all' ? [ok(a), ok(b)] : [ok(a), ok(b), ok(c), {ok: true, unpriced: true, key: 'Nobody Real|Receiving Yards|33', leg: null, label: 'Nobody Real 33+ Receiving Yards'}, {ok: false, raw: 'FIRST DRIVE RESULT - PUNT', why: 'a drive prop'}];
  window.__want = [key(a), key(b)]; window.__early = c.pl;
  window.BSImport.read = function(){ return Promise.resolve({R: {legs: legs, odds: 650}, BS: BS}); };
  window.BSLoadSlip = function(keys, gm){ window.__loaded = {keys: keys, gm: gm}; };
  return window.__want; })""" % (GL, GD)
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8859), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    B = "http://127.0.0.1:8859"
    async def ctx_for(b, theme, extra=""):
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + FREEZE + ACCT + extra)
        await ctx.route("**/*espn.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body='{"events":[]}'))
        await ctx.route("**/*supabase*/**", lambda r: r.abort()); await ctx.route("**/cdn.jsdelivr.net/**", lambda r: r.abort())
        return ctx
    async with async_playwright() as p:
        b = await p.chromium.launch(); want = None
        for theme in ("light", "dark"):
            # ---------- Social: read, choose, hand off ----------
            ctx = await ctx_for(b, theme); pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(B + "/social/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
            s0 = await pg.evaluate("() => ({btn: !!document.getElementById('shotbtn'), hidden: document.getElementById('shot').hidden, exp: document.getElementById('shotbtn').getAttribute('aria-expanded'), reader: !!(window.BSImport && window.BSImport.gmap)})")
            check(s0 == {"btn": True, "hidden": True, "exp": "false", "reader": True}, f"[{theme}] Social has a 'From a screenshot' button, its panel starts closed, and the reader is loaded ({s0})")
            want = await pg.evaluate(STUB, "mixed")
            await pg.click("#shotbtn"); await pg.set_input_files("#shotf", {"name": "slip.png", "mimeType": "image/png", "buffer": b"\x89PNG"}); await pg.wait_for_timeout(900)
            r = await pg.evaluate("""() => { var o = document.documentElement, box = document.getElementById('shot'); return {open: !box.hidden, exp: document.getElementById('shotbtn').getAttribute('aria-expanded'), st: Array.from(box.querySelectorAll('#shotout .st')).map(function(x){ return x.textContent; }),
                yes: Array.from(box.querySelectorAll('li:not(.no)')).length, no: Array.from(box.querySelectorAll('li.no small')).map(function(x){ return x.textContent; }), go: (document.getElementById('shotgo') || {}).textContent, goH: document.getElementById('shotgo') ? Math.round(document.getElementById('shotgo').getBoundingClientRect().height) : 0, over: o.scrollWidth - o.clientWidth}; }""")
            print(f"   [{theme}]", json.dumps(r, ensure_ascii=False)[:700])
            check(r["open"] and r["exp"] == "true" and r["st"][0] == "2 of 5 legs can be posted · FanDuel +650" and r["yes"] == 2, f"[{theme}] the panel says how many of the legs on the picture can be posted ({r['st'][0] if r['st'] else None})")
            check(r["no"] == ["that game has already kicked off", "not on this week's board at that exact line, so it cannot be posted", "a drive prop"], f"[{theme}] each leg left out says why: kicked off, not on the board, not a market we price")
            check(r["go"] == "Post these 2 legs" and r["goH"] >= 44 and r["over"] == 0 and "for the whole slip" in " ".join(r["st"]), f"[{theme}] one button posts what is left; the slip price is left off because legs were dropped; nothing overflows")
            if SHOTS: await pg.evaluate("document.getElementById('shot').scrollIntoView({block: 'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(250); await pg.screenshot(path=f"{SHOTS}/social-shot-{theme}.png")
            await pg.click("#shotgo"); await pg.wait_for_timeout(300)
            h = await pg.evaluate("() => ({loaded: window.__loaded, flag: JSON.parse(sessionStorage.getItem('bs_postnow') || 'null'), want: window.__want})")
            check(h["loaded"] and h["loaded"]["keys"] == h["want"] and h["flag"] and h["flag"]["odds"] is None and h["flag"]["keys"] == sorted(h["want"]) and h["flag"]["t"] == T, f"[{theme}] the two legs go to the Parlay Builder with a single-use note to open its post form (no price, since legs were dropped)")
            # every leg comes along: the price on the picture is carried
            await pg.evaluate(STUB, "all"); await pg.set_input_files("#shotf", {"name": "slip.png", "mimeType": "image/png", "buffer": b"\x89PNG"}); await pg.wait_for_timeout(700); await pg.click("#shotgo"); await pg.wait_for_timeout(300)
            h2 = await pg.evaluate("() => ({st: document.querySelector('#shotout .st') ? 1 : 0, flag: JSON.parse(sessionStorage.getItem('bs_postnow') || 'null')})")
            check(h2["flag"]["odds"] == 650, f"[{theme}] when every leg comes along the price on the picture is carried (+650)")
            await pg.click("#shotbtn"); check(await pg.evaluate("document.getElementById('shot').hidden"), f"[{theme}] the button closes the panel again")
            check(not errs, f"[{theme}] Social: no script errors {errs[:2]}"); await ctx.close()
            # ---------- Parlay Builder: the post form opens for exactly that slip ----------
            def seed(keys, flag): return ("try{ localStorage.setItem('bs_slipk_w%d', %s); localStorage.setItem('bs_slipg_w%d', '{}'); %s }catch(e){}" % (WEEK, json.dumps(json.dumps(keys)), WEEK, ("sessionStorage.setItem('bs_postnow', %s);" % json.dumps(json.dumps(flag))) if flag else "sessionStorage.removeItem('bs_postnow');"))
            DLG = "() => ({open: !document.getElementById('sdlg').hidden, odds: document.getElementById('sdO').value, as: document.getElementById('sdH').textContent, legs: window.bsSlipLegs().length})"
            ctx = await ctx_for(b, theme, seed(want, {"odds": 650, "keys": sorted(want), "t": T})); pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(B + "/build/#slip", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600)
            d = await pg.evaluate(DLG); check(d == {"open": True, "odds": "+650", "as": "@Tester", "legs": 2}, f"[{theme}] the builder opens its post form by itself for the slip that was read, price filled in, nothing posted yet ({d})")
            check(await pg.evaluate("window.__posted === undefined"), f"[{theme}] nothing is posted until the reader presses Post")
            if SHOTS: await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/social-shot-form-{theme}.png")
            await pg.fill("#sdT", "From my FanDuel"); await pg.click("#sdGo"); await pg.wait_for_timeout(250)     # the page moves on to Social 600 ms after a post - read before it does
            po = await pg.evaluate("() => { var r = window.__posted; r = Array.isArray(r) ? r[0] : r; return r ? {n: (r.legs || []).length, odds: r.fd_odds, title: r.title, keys: (r.legs || []).map(function(l){ return l.k; }).sort(), fko: typeof r.first_ko, week: r.week} : null; }")
            check(po and po["n"] == 2 and po["odds"] == 650 and po["title"] == "From my FanDuel" and po["keys"] == sorted(want) and po["fko"] == "string" and po["week"] == WEEK, f"[{theme}] pressing Post sends those two legs with the price and the title ({po})")
            check(not errs, f"[{theme}] builder: no script errors {errs[:2]}"); await ctx.close()
            # a different slip on the page, or an old note: the form stays shut
            for name, keys, flag in (("the slip on the page is not the one that was read", want[:1], {"odds": 650, "keys": sorted(want), "t": T}), ("the note is more than two minutes old", want, {"odds": 650, "keys": sorted(want), "t": T - 5 * 60e3})):
                ctx = await ctx_for(b, theme, seed(keys, flag)); pg = await ctx.new_page(); await pg.goto(B + "/build/#slip", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600)
                d = await pg.evaluate(DLG); check(not d["open"] and d["odds"] == "", f"[{theme}] the form does not open by itself when {name}")
                if "old" in name:
                    await pg.evaluate("document.getElementById('postsl').click()"); await pg.wait_for_timeout(500); d = await pg.evaluate(DLG)
                    check(d["open"] and d["odds"] == "+650", f"[{theme}] ...but opening it by hand within half an hour still offers the price for that same slip ({d['odds']})")
                await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
