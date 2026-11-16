"""Boards: played games fold under "N games already played" while a game is still to come (11/16).
Serves ./site and freezes the page clock one hour before the week's last kickoff, so the test means the same thing on any day.
  python3 tests/boards_fold.py [shots_dir]"""
import asyncio, json, os, sys, threading, http.server, functools
from playwright.async_api import async_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
FREEZE = "(function(){ var T = +(localStorage.getItem('t_now') || 0); if(T) Date.now = function(){ return T; }; })();"
STATE = """() => { var o = document.documentElement, grid = document.querySelector('.grid'), d = grid.querySelector(':scope > details.bdone'), all = Array.from(grid.querySelectorAll('.card[data-ko]'));
  var inside = all.filter(function(c){ return !!c.closest('details.bdone'); }), outside = all.filter(function(c){ return !c.closest('details.bdone'); });
  var chips = Array.from(document.querySelectorAll('nav.nav a[href^="#"]')).filter(function(a){ return a.getAttribute('href') !== '#summary'; });
  return {cards: all.length, inside: inside.length, outside: outside.length, doneOutside: outside.filter(function(c){ return c.classList.contains('done'); }).length, upInside: inside.filter(function(c){ return !c.classList.contains('done'); }).length,
          fold: !!d, open: !!(d && d.open), sum: d ? d.querySelector('summary b').textContent : '', sumH: d ? Math.round(d.querySelector('summary').getBoundingClientRect().height) : 0, last: !d || grid.lastElementChild === d,
          first: (grid.querySelector(':scope > .card[data-ko]') || {}).id || '', order: outside.map(function(c){ return +c.dataset.ko; }), inOrder: inside.map(function(c){ return +c.dataset.ko; }),
          chips: chips.map(function(a){ return a.classList.contains('played') ? 'p' : 'u'; }).join(''), firstPlayed: (chips.filter(function(a){ return a.classList.contains('played'); })[0] || {getAttribute: function(){ return ''; }}).getAttribute('href'),
          over: o.scrollWidth - o.clientWidth, h: o.scrollHeight}; }"""
asc = lambda a: all(a[i] <= a[i + 1] for i in range(len(a) - 1))
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8855), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    U = "http://127.0.0.1:8855/boards/"
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + FREEZE)
            await ctx.route("**/*espn.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body='{"events":[]}'))
            await ctx.route("**/*supabase*/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(U, wait_until="domcontentloaded"); await pg.wait_for_timeout(1200)
            kos = await pg.evaluate("() => Array.from(document.querySelectorAll('.card[data-ko]')).map(function(c){ return +c.dataset.ko; })")
            last = max(kos); days = len({int(k // 86400e3) for k in kos})
            # ---- one hour before the last kickoff ----
            await pg.evaluate(f"localStorage.setItem('t_now', '{int(last - 3600e3)}')"); await pg.goto(U + "?t=1", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
            s = await pg.evaluate(STATE); print(f"   [{theme}] before the last game:", json.dumps({k: v for k, v in s.items() if k not in ('order', 'inOrder')})[:520])
            if days < 2: print("   (single-day week: nothing is played an hour before the last kickoff; fold checks skipped)")
            else:
                check(s["fold"] and s["inside"] >= 1 and s["outside"] >= 1 and s["doneOutside"] == 0 and s["upInside"] == 0 and s["inside"] + s["outside"] == s["cards"], f"[{theme}] finished scorecards sit in the fold, games still to come sit above it ({s['outside']} up, {s['inside']} folded)")
                check(not s["open"] and s["sum"] == f"{s['inside']} game{'' if s['inside'] == 1 else 's'} already played" and s["sumH"] >= 44 and s["last"], f"[{theme}] the fold starts closed, says how many games it holds, and is the last thing in the grid ({s['sum']}, {s['sumH']}px)")
                check(asc(s["order"]) and asc(s["inOrder"]) and s["chips"].lstrip("u").strip("p") == "" and "u" in s["chips"] and "p" in s["chips"], f"[{theme}] kickoff order is kept on both sides of the fold; chips lead with games still to come ({s['chips']})")
                check(s["over"] == 0, f"[{theme}] no sideways scroll")
                if SHOTS: await pg.evaluate("document.querySelector('.grid').scrollIntoView({block: 'start'})"); await pg.wait_for_timeout(300); await pg.screenshot(path=f"{SHOTS}/boards-fold-{theme}.png", full_page=False)
                # a chip to a played game opens the fold, opens that card and lands on it
                href = s["firstPlayed"]; await pg.evaluate("""(h) => { var a = document.querySelector('nav.nav a[href="' + h + '"]'); a.scrollIntoView({inline: 'center', block: 'nearest'}); a.click(); }""", href); await pg.wait_for_timeout(900)
                j = await pg.evaluate("""(h) => { var d = document.querySelector('details.bdone'), t = document.getElementById(h.slice(1)), r = t.getBoundingClientRect(); return {open: d.open, top: Math.round(r.top), vis: r.height > 0, exp: t.classList.contains('expanded')}; }""", href)
                check(j["open"] and j["vis"] and j["exp"] and -5 <= j["top"] <= 400, f"[{theme}] tapping a played game's chip opens the fold and lands on its card, opened ({href}, top {j['top']}px)")
                h_open = (await pg.evaluate(STATE))["h"]; check(s["h"] < h_open, f"[{theme}] folding the played games shortens the page ({s['h']}px closed, {h_open}px open)")
                # the reader's choice holds through the page's own refresh (it re-sorts on every live update; the slip refresh runs each minute)
                await pg.evaluate("document.querySelector('details.bdone').open = false"); await pg.wait_for_timeout(11500)
                s2 = await pg.evaluate(STATE); check(not s2["open"] and s2["inside"] == s["inside"], f"[{theme}] a fold the reader closed stays closed through the next live refresh")
                # arriving on a link to a played game: the fold is open on it
                await pg.goto(U + "?t=2" + href, wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
                a = await pg.evaluate("""(h) => { var d = document.querySelector('details.bdone'), t = document.getElementById(h.slice(1)), r = t.getBoundingClientRect(); return {fold: !!d, open: !!(d && d.open), inFold: !!t.closest('details.bdone'), top: Math.round(r.top), exp: t.classList.contains('expanded')}; }""", href)
                check(a["fold"] and a["open"] and a["inFold"] and a["exp"] and -5 <= a["top"] <= 400, f"[{theme}] a link straight to a played game arrives with the fold open on that card ({a})")
            # ---- five hours after the last kickoff: nothing left to play, so no fold ----
            await pg.evaluate(f"localStorage.setItem('t_now', '{int(last + 5 * 3600e3)}')"); await pg.goto(U + "?t=3", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
            e = await pg.evaluate(STATE)
            check(not e["fold"] and e["outside"] == e["cards"] and e["doneOutside"] == e["cards"] and asc(e["order"]) and e["chips"].strip("p") == "", f"[{theme}] once every game is played there is no fold: every scorecard is on the page in kickoff order ({e['outside']} cards)")
            await pg.evaluate("localStorage.removeItem('t_now')")
            check(not errs, f"[{theme}] no script errors {errs[:2]}")
            await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
