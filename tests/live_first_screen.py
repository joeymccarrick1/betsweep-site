"""What the Live page opens on, in its three states (11/17): nothing in play with games to come, a game in play, the week finished.

Before: a card for the tools, a box holding one "What changed - nothing new" tab, and only then the game. The game chips under the title
did nothing for a game inside the closed Final fold, a finished week promised a "watch list below" that was not there, and an open card
of a live game led with its pregame notes.

Runs in any week: every game's final and the build's finals are taken out of the page's own data so the page clock alone decides what
has been played; ESPN, the change feed and the account service are faked or cut off.
  python3 tests/live_first_screen.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, datetime, functools, glob, http.server, json, os, re, sys, threading
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8863; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
_ref = re.search(r"/live/(data-[0-9a-f]+\.js)", open(os.path.join(ROOT, "live", "index.html")).read())
SRC = open(os.path.join(ROOT, "live", _ref.group(1)) if _ref else glob.glob(os.path.join(ROOT, "live", "data-*.js"))[0]).read(); _m = re.match(r"\s*window\.__LV\s*=\s*", SRC); D0 = json.loads(SRC[_m.end():].rstrip().rstrip(";"))
D = json.loads(json.dumps(D0)); D["fb"] = {}
for _g in D["games"]: _g.pop("fin", None)
BODY = "window.__LV = " + json.dumps(D, separators=(",", ":")) + ";"
GS = sorted([g for g in D["games"] if g.get("ko")], key=lambda g: g["ko"]); FIRST, LAST = GS[0], GS[-1]
CLOCK = "(function(){var T=+(localStorage.getItem('t_now')||0);if(!T)return;var R=Date.now,S=R();Date.now=function(){return T+(R()-S)};var D0=Date;function ND(){if(arguments.length===0)return new D0(D0.now());return new (Function.prototype.bind.apply(D0,[null].concat([].slice.call(arguments))))()}ND.now=D0.now;ND.parse=D0.parse;ND.UTC=D0.UTC;ND.prototype=D0.prototype;window.Date=ND;})();"
READ = """() => { var q = function(s){ return document.querySelector(s); }, qa = function(s){ return Array.from(document.querySelectorAll(s)); }, o = document.documentElement, R = function(e){ return e ? e.getBoundingClientRect() : null; };
  var kids = qa('#lv > *').map(function(e){ return e.getAttribute('data-key'); }), tools = R(q('.lvtools')), first = q('#lv > section.lg2:not(.hub)'), fr = R(first);
  var chips = qa('nav.nav a[href^="#lv-"]');
  return {kids: kids, hub: !!q('#lv .hub'), tabs: qa('#lv .hubb b').map(function(b){ return b.textContent; }), bar: (q('#lv .lvbar') || {textContent: ''}).textContent, barLinks: qa('#lv .lvbar a').map(function(a){ return a.getAttribute('href'); }),
          toolsH: tools ? Math.round(tools.height) : 0, toolsCard: getComputedStyle(q('.lvtools')).borderTopWidth !== '0px', imp: q('#impopen').textContent, impH: Math.round(R(q('#impopen')).height), rfrH: Math.round(R(q('#lvrefresh')).height), rfrW: Math.round(R(q('#lvrefresh')).width), upd: q('#upd').textContent,
          firstTop: fr ? Math.round(fr.top) : null, firstId: first ? first.id : null, firstLive: !!(first && first.classList.contains('live')),
          played: chips.filter(function(a){ return a.classList.contains('played'); }).length, liveChips: chips.filter(function(a){ return a.classList.contains('livenow'); }).map(function(a){ return a.getAttribute('href').slice(4); }), nchips: chips.length,
          fin: (q('[data-g="__fin"]') || {textContent: ''}).textContent, finOpen: !!(q('[data-g="__fin"]') && q('[data-g="__fin"]').getAttribute('aria-expanded') === 'true'), over: o.scrollWidth - o.clientWidth}; }"""

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    iso = lambda ms: datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def visit(t, theme, live=None, events=(), hash_=""):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
            await ctx.add_init_script(f"try{{if(localStorage.getItem('t_now')===null){{localStorage.setItem('bs_theme','{theme}');localStorage.setItem('t_now','{int(t)}');}}}}catch(e){{}}" + CLOCK)
            sb = {"events": []}
            if live: sb = {"events": [{"id": "401", "status": {"period": 2, "displayClock": "4:10", "type": {"state": "in", "completed": False, "shortDetail": "4:10 - 2nd"}},
                                      "competitions": [{"competitors": [{"team": {"abbreviation": live["a"], "id": "1"}, "score": "10"}, {"team": {"abbreviation": live["b"], "id": "2"}, "score": "7"}], "situation": {}}]}]}
            async def on_espn(route, request): await route.fulfill(status=200, content_type="application/json", body=json.dumps({} if "summary" in request.url else sb))
            async def on_feed(route, request): await route.fulfill(status=200, content_type="application/json", body=json.dumps({"events": list(events)} if "changes.json" in request.url else {}))
            async def on_data(route, request): await route.fulfill(status=200, content_type="application/javascript", body=BODY)
            await ctx.route("**/*espn.com/**", on_espn); await ctx.route("**/raw.githubusercontent.com/**", on_feed); await ctx.route("**/data/price-moves.json", on_feed); await ctx.route("**/*supabase*/**", lambda r: r.abort()); await ctx.route("**/live/data-*.js", on_data)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/live/" + hash_, wait_until="domcontentloaded"); await pg.wait_for_timeout(2600)
            return pg, ctx, errs
        for theme in ("dark", "light"):
            # ---- nothing in play, every game still to come ----
            pg, ctx, errs = await visit(FIRST["ko"] - 26 * 3600e3, theme); s = await pg.evaluate(READ)
            print(f"   [{theme}] before the week:", json.dumps({k: s[k] for k in ("kids", "bar", "toolsH", "imp", "impH", "rfrH", "upd", "firstTop", "played")})[:520])
            check(not s["hub"] and s["kids"][0] == "bar" and "next kickoff" in s["bar"] and FIRST["kick"] in s["bar"] and s["barLinks"] == ["#lv-" + FIRST["gid"]], f"[{theme}] with nothing new and no slips there is no empty box: the page starts with the next kickoff ({FIRST['kick']}), linked to its game")
            check(not s["toolsCard"] and s["toolsH"] <= 64 and s["imp"] == "Import a slip" and s["impH"] >= 40 and s["rfrH"] >= 40 and s["rfrW"] >= 40 and s["upd"].startswith("Updated "), f"[{theme}] the tools are one line, not a card, with finger-size buttons ({s['toolsH']}px tall; buttons {s['impH']}/{s['rfrH']}px; {s['upd']!r})")
            check(s["played"] == 0 and not s["liveChips"] and not s["fin"], f"[{theme}] before the first kickoff no chip is dimmed and there is no Final group")
            await pg.evaluate("() => document.querySelector('#lv .lvbar a').click()"); await pg.wait_for_timeout(1500)
            j = await pg.evaluate("""(gid) => { var e = document.getElementById('lv-' + gid), r = e.getBoundingClientRect(); return {open: e.classList.contains('open'), top: Math.round(r.top), bars: Math.round(Math.max(document.querySelector('nav.nav').getBoundingClientRect().bottom, document.getElementById('sitenav').getBoundingClientRect().bottom)), notesFold: !!e.querySelector('h4.subtog[data-g="' + gid + '|notes"]'), notes: !!e.querySelector('.gdet')}; }""", FIRST["gid"])
            check(j["open"] and 0 <= j["top"] - j["bars"] <= 24 and j["notes"] and not j["notesFold"], f"[{theme}] the link opens that game's card and lands it just under the header and the chips; before kickoff its notes are shown as before ({j})")
            check(s["over"] == 0 and not errs, f"[{theme}] no sideways scroll, no page errors {errs[:1]}")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/live-first-pre-{theme}.png")
            await ctx.close()
            # something did change: the hub is back with its count
            t0 = FIRST["ko"] - 26 * 3600e3
            pg, ctx, errs = await visit(t0, theme, events=[{"ts": iso(t0 - 3600e3), "k": "news", "t": "Test note: a starter was ruled out"}]); s = await pg.evaluate(READ); await ctx.close()
            check(s["hub"] and s["tabs"] == ["What changed"] and s["kids"][0] == "__hub", f"[{theme}] when something has changed the What changed tab is there ({s['tabs']})")
            # ---- a game in play ----
            pg, ctx, errs = await visit(FIRST["ko"] + 75 * 60e3, theme, live=FIRST); s = await pg.evaluate(READ)
            print(f"   [{theme}] {FIRST['gid']} in play:", json.dumps({k: s[k] for k in ("kids", "upd", "firstId", "firstTop", "liveChips", "played", "toolsH")})[:420])
            check(not s["hub"] and s["firstLive"] and s["firstId"] == "lv-" + FIRST["gid"] and s["firstTop"] <= 300, f"[{theme}] the game in play is the first thing under the tools ({s['firstTop']}px from the top; was 375)")
            check(s["liveChips"] == [FIRST["gid"]] and s["upd"].startswith("Live scores as of "), f"[{theme}] its chip is marked as on, and the status line gives the score feed's time ({s['upd']!r})")
            await pg.evaluate("(gid) => document.querySelector('#lv-' + gid + ' > .ghd2').click()", FIRST["gid"]); await pg.wait_for_timeout(1500)
            o = await pg.evaluate("""(gid) => { var e = document.getElementById('lv-' + gid), subs = Array.from(e.querySelectorAll('h4.subtog')); return {subs: subs.map(function(h){ return h.textContent.replace(/[▾▴]/g, '').trim(); }), notesOpen: !!e.querySelector('.gdet'), last: subs.length ? subs[subs.length - 1].getAttribute('data-g') : null}; }""", FIRST["gid"])
            check(o["last"] == FIRST["gid"] + "|notes" and not o["notesOpen"] and o["subs"][-1] == "Pregame notes", f"[{theme}] an open card of a game in play ends with its pregame notes, folded ({o['subs']})")
            await pg.evaluate("(gid) => document.querySelector('#lv-' + gid + ' h4.subtog[data-g=\"' + gid + '|notes\"]').click()", FIRST["gid"]); await pg.wait_for_timeout(1500)
            check(await pg.evaluate("(gid) => !!document.querySelector('#lv-' + gid + ' .gdet')", FIRST["gid"]), f"[{theme}] tapping Pregame notes shows them")
            check(not errs, f"[{theme}] no page errors with a game in play {errs[:1]}")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/live-first-in-{theme}.png")
            await ctx.close()
            # ---- the week is finished ----
            pg, ctx, errs = await visit(LAST["ko"] + 6 * 3600e3, theme); s = await pg.evaluate(READ)
            print(f"   [{theme}] week finished:", json.dumps({k: s[k] for k in ("kids", "bar", "barLinks", "fin", "played", "nchips")})[:520])
            check(s["kids"][0] == "bar" and f"Week {D['week']} is finished" in s["bar"] and "watch list" not in s["bar"] and s["barLinks"] == ["/results/", "/me/"], f"[{theme}] a finished week says so and points to Receipts and My BetSweep ({s['bar'][:50]!r})")
            check(s["played"] == s["nchips"] == len(D["games"]) and s["fin"].startswith(f"Final · {len(D['games'])} games") and not s["finOpen"], f"[{theme}] every chip is dimmed; the Final group says how many games it holds and starts closed ({s['fin'][:40]!r})")
            if D.get("next"): check(D["next"]["kick"] in s["bar"] and D["next"]["a"] in s["bar"] and D["next"]["h"] in s["bar"], f"[{theme}] it gives next week's first kickoff from the schedule ({D['next']['kick']}, {D['next']['a']} at {D['next']['h']})")
            gap = await pg.evaluate("() => { var a = Array.from(document.querySelectorAll('#lv .lvgo a')); if(a.length < 2) return null; var r0 = a[0].getBoundingClientRect(), r1 = a[1].getBoundingClientRect(); return {gap: Math.round(r1.top > r0.top + 5 ? r1.top - r0.bottom : r1.left - r0.right), h: Math.round(r0.height)}; }")
            check(gap and gap["gap"] >= 6 and gap["h"] >= 40, f"[{theme}] its two buttons are finger-size and do not touch ({gap})")
            tgt = GS[len(GS) // 2]["gid"]
            await pg.evaluate("""(gid) => { var a = document.querySelector('nav.nav a[href="#lv-' + gid + '"]'); a.click(); }""", tgt); await pg.wait_for_timeout(1700)
            j = await pg.evaluate("""(gid) => { var e = document.getElementById('lv-' + gid); if(!e) return {there: false}; var r = e.getBoundingClientRect(); return {there: true, open: e.classList.contains('open'), top: Math.round(r.top), bars: Math.round(Math.max(document.querySelector('nav.nav').getBoundingClientRect().bottom, document.getElementById('sitenav').getBoundingClientRect().bottom)), foldOpen: document.querySelector('[data-g="__fin"]').getAttribute('aria-expanded') === 'true', hash: location.hash}; }""", tgt)
            check(j.get("there") and j["open"] and j["foldOpen"] and 0 <= j["top"] - j["bars"] <= 24 and j["hash"] == "#lv-" + tgt, f"[{theme}] a chip for a finished game opens the Final group and the game and lands it just under the header and the chips (it did nothing before) {j}")
            check(s["over"] == 0 and not errs, f"[{theme}] finished week: no sideways scroll, no page errors {errs[:1]}")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/live-first-done-{theme}.png")
            await ctx.close()
        # arriving from search with the game in the address
        pg, ctx, errs = await visit(LAST["ko"] + 6 * 3600e3, "dark", hash_="#lv-" + FIRST["gid"]); await pg.wait_for_timeout(600)
        j = await pg.evaluate("""(gid) => { var e = document.getElementById('lv-' + gid); return e ? {open: e.classList.contains('open'), top: Math.round(e.getBoundingClientRect().top), bars: Math.round(Math.max(document.querySelector('nav.nav').getBoundingClientRect().bottom, document.getElementById('sitenav').getBoundingClientRect().bottom))} : null; }""", FIRST["gid"]); await ctx.close()
        check(bool(j) and j["open"] and 0 <= j["top"] - j["bars"] <= 24, f"a link to /live/#lv-{FIRST['gid']} lands on that game, opened, just under the bars, even when it sits in the Final group ({j})")
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
