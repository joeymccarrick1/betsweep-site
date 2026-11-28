"""Favorite team on Today (the seventh of the eight ideas the owner approved 11/27 8:31 PM; 11/28 1:29 AM: "make sure all 8 ... are
finished"). One team a device, kept in the browser (bs_fav). With a team chosen, Today names its game under the opener, puts its card
first among games in the same state and marks it; with none, one chip offers the choice.

Everything expected is read from the page's own data (window.__TD: the week's games and the 32 teams), so the test runs in any week.
The page is opened at 390x844 in both themes, the outside world cut off, three hours before the next kickoff.
  python3 tests/fav_team.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, os, re, sys, threading
from playwright.async_api import async_playwright
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8909; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
h = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read(); m = re.search(r"window\.__TD = (\{.*?\});</script>", h, re.S)
TD = json.loads(m.group(1)) if m else {"games": [], "teams": []}
READ = """() => { var vis = function(e){ return !!(e && (e.offsetWidth || e.offsetHeight)); }, hero = document.getElementById('tdhero'), sel = document.getElementById('tdfavsel'), lab = document.getElementById('tdfavp'), lr = lab ? lab.getBoundingClientRect() : null;
  var rows = Array.from(document.querySelectorAll('#tdhero .thx')).map(function(r){ return {label: (r.querySelector(':scope > span') || {}).textContent || '', mine: (function(){ var a = r.querySelector('a.thmine'); return a ? {href: a.getAttribute('href'), txt: a.textContent.replace(/\\s+/g, ' ').trim()} : null; })(), off: (r.querySelector('.thoff') || {}).textContent || '', chips: Array.from(r.querySelectorAll('a:not(.thmine)')).map(function(a){ return a.getAttribute('href'); })}; });
  var cards = Array.from(document.querySelectorAll('#tdgames .tdgame.show')).map(function(c){ return {gid: c.getAttribute('data-gid'), fav: c.classList.contains('fav'), tag: (c.querySelector('.tdfavt') || {}).textContent || '', shown: vis(c), st: c.classList.contains('live') ? 'in' : c.classList.contains('fin') ? 'post' : 'pre', ko: +c.getAttribute('data-ko')}; });
  return {pick: lab ? {txt: (lab.querySelector('span').textContent || '').trim(), set: lab.classList.contains('set'), inHead: !!lab.closest('.tdhead .tdact'), fits: lr.left >= 0 && lr.right <= innerWidth + 0.5, h: Math.round(lr.height), logo: !!lab.querySelector('i.hm')} : null, kick: ((document.querySelector('#tdhero .thk em') || {}).textContent || ''), hero: hero && !hero.hidden, opener: (document.querySelector('#tdhero .thl') || {getAttribute: function(){ return null; }}).getAttribute('data-gid'), rows: rows, cards: cards, sel: sel ? {n: sel.options.length, v: sel.value, h: Math.round(sel.getBoundingClientRect().height)} : null, fav: (function(){ try { return localStorage.getItem('bs_fav'); } catch(e){ return null; } })(), over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }"""

async def main():
    games = [g for g in TD.get("games", []) if g.get("ko")]; teams = [t[0] for t in TD.get("teams", [])]
    if not games or not teams:
        check(True, "Today carries no games or no team list in this build: nothing to check"); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(0)
    built = __import__("datetime").datetime.fromisoformat(TD["built"]).timestamp() * 1000
    fut = sorted([g for g in games if g["ko"] > built + 60e3], key=lambda g: g["ko"])
    if not fut:
        check(True, "every game on this board has kicked off: nothing to check"); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(0)
    T0 = max(built + 1000, fut[0]["ko"] - 3 * 3600e3); first = fut[0]
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); srv.handle_error = lambda *a: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def open_(theme, clock, fav=None):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block", color_scheme=theme)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}');" + (f"if(!sessionStorage.getItem('__f')){{sessionStorage.setItem('__f','1');localStorage.setItem('bs_fav','{fav}');}}" if fav else "") + f"}}catch(e){{}};(function(){{var T={int(clock)},R=Date.now,S=R();Date.now=function(){{return T+(R()-S)}};}})();")
            async def gate(route, request): await (route.continue_() if "127.0.0.1" in request.url else route.abort())
            await ctx.route("**/*", gate)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2000)
            return pg, ctx, errs
        for theme in ("light", "dark"):
            pg, ctx, errs = await open_(theme, T0); s = await pg.evaluate(READ)
            pk = s["pick"] or {}
            check(s["hero"] and s["opener"] == first["gid"] and pk.get("txt") == "+ Your team" and pk.get("inHead") and pk.get("fits") and pk.get("h", 0) >= 36 and not pk.get("set") and not any(r["label"] == "Your team" for r in s["rows"]) and s["sel"] and s["sel"]["n"] == len(teams) + 1 and not any(c["fav"] for c in s["cards"]) and s["fav"] is None and s["over"] <= 0 and not errs,
                  f"[{theme}] with no team chosen one chip beside Short view and Live offers the choice, '+ Your team', over a list of all {len(teams)} teams; no card is marked ({pk}; {errs[:1]})")
            shown = [c for c in s["cards"]]; day = [g for g in games if any(c["gid"] == g["gid"] for c in shown)]
            # a team that plays on the day shown, not in the opener's game, whose card is not already first
            cand = next((t for g in day[1:] if g["gid"] != first["gid"] for t in (g["a"], g["b"])), None)
            if cand:
                g1 = next(g for g in games if cand in (g["a"], g["b"]))
                await pg.select_option("#tdfavsel", cand); await pg.wait_for_timeout(500); z = await pg.evaluate(READ)
                mine = next((r for r in z["rows"] if r["label"] == "Your team"), None); c0 = z["cards"][0] if z["cards"] else {}
                pre = [c for c in z["cards"] if c["st"] == "pre"]
                check(z["fav"] == cand and mine is not None and mine["mine"] and mine["mine"]["href"] == "/boards/#g-" + g1["gid"] and (g1.get("kick") or "") in mine["mine"]["txt"] and z["pick"]["txt"].startswith(cand) and z["pick"]["set"] and z["pick"]["logo"] and z["pick"]["fits"] and z["sel"]["v"] == cand and not errs,
                      f"[{theme}] choosing {cand} keeps it in this browser and adds a 'Your team' row: its game with the kickoff, linked to its board, and the chip now reads {cand} ({(mine or {}).get('mine')}; {errs[:1]})")
                check(bool(pre) and pre[0]["gid"] == g1["gid"] and pre[0]["fav"] and pre[0]["tag"] == "Your team" and pre[0]["shown"] and sum(1 for c in z["cards"] if c["fav"]) == 1 and not any("/boards/#g-" + g1["gid"] in r["chips"] for r in z["rows"]) and z["over"] <= 0,
                      f"[{theme}]   its card is first among the games still to kick off, marked 'Your team', and its game is not listed twice under the opener (first card {pre[0]['gid'] if pre else None})")
                if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"fav_team_{theme}.png"))
                await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_timeout(1800); z2 = await pg.evaluate(READ)
                check(z2["fav"] == cand and any(r["label"] == "Your team" for r in z2["rows"]) and any(c["fav"] for c in z2["cards"]), f"[{theme}]   the choice is still there after a reload")
                # the opener's own team: no second chip for the same game
                await pg.select_option("#tdfavsel", first["a"]); await pg.wait_for_timeout(500); z3 = await pg.evaluate(READ); mine3 = next((r for r in z3["rows"] if r["label"] == "Your team"), None)
                check(z3["fav"] == first["a"] and mine3 is None and z3["pick"]["txt"].startswith(first["a"]) and "your team" in z3["kick"] and [c["gid"] for c in z3["cards"] if c["fav"]] == [first["gid"]], f"[{theme}] choosing a team in the opener's own game marks that card, and the opener itself says 'your team' instead of a second chip ({z3['kick']!r})")
                # a team with no game this week
                idle = next((t for t in teams if not any(t in (g["a"], g["b"]) for g in TD["games"])), None)
                if idle:
                    await pg.select_option("#tdfavsel", idle); await pg.wait_for_timeout(500); z4 = await pg.evaluate(READ); mine4 = next((r for r in z4["rows"] if r["label"] == "Your team"), None)
                    check(mine4 is not None and idle in mine4["off"] and "off this week" in mine4["off"] and not any(c["fav"] for c in z4["cards"]), f"[{theme}] a team with no game this week is said to be off, and no card is marked ({(mine4 or {}).get('off')!r})")
                await pg.select_option("#tdfavsel", ""); await pg.wait_for_timeout(500); z5 = await pg.evaluate(READ)
                check(z5["fav"] is None and z5["pick"]["txt"] == "+ Your team" and not any(r["label"] == "Your team" for r in z5["rows"]) and not any(c["fav"] or c["tag"] for c in z5["cards"]) and [c["gid"] for c in z5["cards"]] == [c["gid"] for c in s["cards"]] and not errs,
                      f"[{theme}] choosing 'No team' takes it all back: no row, no mark, the cards in their first order ({errs[:1]})")
                await ctx.close()
                # after its kickoff the chip follows the game to Live
                pg, ctx, errs = await open_(theme, g1["ko"] + 20 * 60e3, fav=cand); z6 = await pg.evaluate(READ); mine6 = next((r for r in z6["rows"] if r["label"] == "Your team"), None)
                on_opener = z6["opener"] == g1["gid"]
                check((on_opener and "your team" in z6["kick"]) or (mine6 is not None and mine6["mine"] and mine6["mine"]["href"] == "/live/#lv-" + g1["gid"]) and not errs, f"[{theme}] twenty minutes after its kickoff the row points at Live ({'the opener is its game' if on_opener else (mine6 or {}).get('mine')}; {errs[:1]})")
            else: check(True, f"[{theme}] the day shown has one game: no second team to choose")
            await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
