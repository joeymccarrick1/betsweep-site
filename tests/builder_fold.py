"""The builder's finished-games fold and the last-games picture in a leg's details (11/16).
Serves ./site and freezes the page clock one hour before the week's last kickoff, so earlier games count as played whatever day the test runs.
  python3 tests/builder_fold.py [shots_dir]"""
import asyncio, json, os, sys, threading, http.server, functools
from playwright.async_api import async_playwright
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
FREEZE = "(function(){ var T = +(localStorage.getItem('t_now') || 0); if(T) Date.now = function(){ return T; }; })();"
STATE = """() => { var o = document.documentElement, d = document.querySelector('#games details.gdone'), all = Array.from(document.querySelectorAll('#games section.gcard'));
  var inside = all.filter(function(c){ return !!c.closest('details.gdone'); }), outside = all.filter(function(c){ return !c.closest('details.gdone'); });
  var chips = Array.from(document.querySelectorAll('nav.nav a[href^="#g-"]'));
  return {cards: all.length, inside: inside.length, outside: outside.length, doneOutside: outside.filter(function(c){ return c.classList.contains('done'); }).length, liveInside: inside.filter(function(c){ return !c.classList.contains('done'); }).length,
          fold: !!d, open: !!(d && d.open), sum: d ? d.querySelector('summary b').textContent : '', sumH: d ? d.querySelector('summary').getBoundingClientRect().height : 0,
          foldLast: !d || !d.nextElementSibling, chips: chips.map(function(a){ return (a.classList.contains('played') ? 'p' : 'u'); }).join(''), firstPlayed: (chips.filter(function(a){ return a.classList.contains('played'); })[0] || {getAttribute: function(){ return ''; }}).getAttribute('href'),
          over: o.scrollWidth - o.clientWidth, h: o.scrollHeight}; }"""
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8853), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + FREEZE)
            await ctx.route("**/site.api.espn.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body='{"events":[]}'))
            await ctx.route("**/*supabase*/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto("http://127.0.0.1:8853/build/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
            kos = await pg.evaluate("() => Object.keys(window.__BS.games || {}).map(function(k){ return window.__BS.games[k].ko || 0; }).concat((window.__BS.gorder || []).map(function(){ return 0; })).filter(Boolean)")
            if not kos: kos = await pg.evaluate("() => (window.__BS.games || []).map(function(g){ return g.ko || 0; }).filter(Boolean)")
            last = max(kos); days = len({int(k // 86400e3) for k in kos})
            # ---- one hour before the last kickoff: earlier games are played, the last is still to come ----
            await pg.evaluate(f"localStorage.setItem('t_now', '{int(last - 3600e3)}')"); await pg.goto("http://127.0.0.1:8853/build/?t=1", wait_until="domcontentloaded"); await pg.wait_for_timeout(2000)
            s = await pg.evaluate(STATE); print(f"   [{theme}] before the last game:", json.dumps(s)[:600])
            if days < 2: print("   (single-day week: fold checks that need an earlier game day are skipped)")
            else:
                check(s["fold"] and s["inside"] >= 1 and s["outside"] >= 1 and s["doneOutside"] == 0 and s["liveInside"] == 0 and s["inside"] + s["outside"] == s["cards"], f"[{theme}] every finished game sits in the fold and every game still to come sits above it ({s['outside']} up, {s['inside']} folded)")
                check(not s["open"] and s["sum"] == f"{s['inside']} game{'' if s['inside'] == 1 else 's'} already played" and s["sumH"] >= 44 and s["foldLast"], f"[{theme}] the fold starts closed, says how many games it holds, and is the last thing in the list ({s['sum']})")
                # the ORDER of the chips is set when the page is built, the dimming follows the clock. A page built after the last kickoff
                # (a Monday-night build) is in plain kickoff order, so the order is only asserted for a page built before it.
                late_build = os.path.getmtime(os.path.join(ROOT, "build", "index.html")) * 1000 > last
                check("u" in s["chips"] and "p" in s["chips"] and s["chips"].count("u") == s["outside"] and (late_build or s["chips"].lstrip("u").strip("p") == ""),
                      f"[{theme}] chips are dimmed by the clock" + ("" if late_build else " and lead with games still to come") + f" ({s['chips']}" + ("; built after the last kickoff, so kickoff order" if late_build else "") + ")")
                check(s["over"] == 0, f"[{theme}] no sideways scroll")
                if SHOTS: await pg.evaluate("document.querySelector('#games').scrollIntoView({block: 'start'})"); await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/builder-fold-{theme}.png")
                # a chip to a played game opens the fold and lands on that game
                href = s["firstPlayed"]; await pg.evaluate("""(h) => { var a = document.querySelector('nav.nav a[href="' + h + '"]'); a.scrollIntoView({inline: 'center', block: 'nearest'}); a.click(); }""", href); await pg.wait_for_timeout(900)
                j = await pg.evaluate("""(h) => { var d = document.querySelector('#games details.gdone'), t = document.getElementById(h.slice(1)), r = t.getBoundingClientRect(); return {open: d.open, top: Math.round(r.top), vis: r.height > 0}; }""", href)
                check(j["open"] and j["vis"] and -5 <= j["top"] <= 500, f"[{theme}] tapping a played game's chip opens the fold and lands on its card ({href}, top {j['top']}px)")
                # the fold stays open when the list redraws (opening a game redraws it)
                await pg.evaluate("""() => { var h = document.querySelector('#games > section.gcard .ghd'); if(h) h.click(); }"""); await pg.wait_for_timeout(600)
                check(await pg.evaluate("document.querySelector('#games details.gdone').open"), f"[{theme}] the fold stays open when the list redraws")
                h_open = (await pg.evaluate(STATE))["h"]; check(s["h"] < h_open, f"[{theme}] folding the played games shortens the page ({s['h']}px closed, {h_open}px open)")
            # ---- a leg's details lead with the last-games picture (in a game still to come) ----
            await pg.goto("http://127.0.0.1:8853/build/?t=2", wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            l = await pg.evaluate("""() => { var g = document.querySelector('#games > section.gcard'); if(!g) return {none: 'no game still to come'}; if(!g.classList.contains('open')) g.querySelector('.ghd').click();
                g = document.querySelector('#games > section.gcard'); var bs = Array.from(g.querySelectorAll('.l5, .mkbtn')), out = {tried: 0, n: bs.length};
                for(var i = 0; i < bs.length && i < 40; i++){ var host = bs[i].closest('.ar') || bs[i].closest('.lg'); if(!host) continue; bs[i].click(); out.tried++; g = document.querySelector('#games > section.gcard');
                  var c = g.querySelector('.hist .l10b'); if(c){ var hist = c.closest('.hist'), o = document.documentElement; c.scrollIntoView({block: 'center'});
                    out.bars = c.querySelectorAll('ol li').length; out.label = c.getAttribute('aria-label'); out.line = (c.querySelector('.ln i') || {}).textContent || ''; out.marks = Array.from(c.querySelectorAll('ol li .k')).map(function(k){ return k.textContent; }).join('');
                    out.first = hist.firstElementChild === c || hist.querySelector('.l10b') === hist.querySelector(':scope > *:not(b):not(h4):not(small)'); out.w = Math.round(c.getBoundingClientRect().width); out.over = o.scrollWidth - o.clientWidth; return out; }
                  bs = Array.from(document.querySelector('#games > section.gcard').querySelectorAll('.l5, .mkbtn')); }
                return out; }""")
            print(f"   [{theme}] leg details:", json.dumps(l, ensure_ascii=False)[:500])
            if l.get("none") or not l.get("n"): print("   (no open leg to test in a game still to come; chart checks skipped)")
            else:
                check(2 <= l.get("bars", 0) <= 10 and len(l.get("marks", "")) == l.get("bars") and set(l.get("marks", "")) <= {"✓", "–"}, f"[{theme}] a leg's details open on a bar for each of his last games (up to ten), each marked hit or miss ({l.get('bars')} bars)")
                check(bool(l.get("line")) and "oldest first" in (l.get("label") or "") and (" of " + str(l.get("bars")) + ".") in (l.get("label") or ""), f"[{theme}] the FanDuel line is drawn and named, and a screen reader hears the same numbers ({l.get('line')})")
                check(l.get("over") == 0 and l.get("w", 0) <= 390, f"[{theme}] the picture fits the phone ({l.get('w')}px wide)")
                if SHOTS: await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/builder-l10-{theme}.png")
            # ---- five hours after the last kickoff: everything is played, so the fold is simply open ----
            await pg.evaluate(f"localStorage.setItem('t_now', '{int(last + 5 * 3600e3)}')"); await pg.goto("http://127.0.0.1:8853/build/?t=3", wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            e = await pg.evaluate(STATE)
            check(e["fold"] and e["open"] and e["outside"] == 0 and e["inside"] == e["cards"] and e["chips"].strip("p") == "", f"[{theme}] once every game is played the fold is open on its own, so the page is never empty ({e['sum']})")
            await pg.evaluate("localStorage.removeItem('t_now')")
            check(not errs, f"[{theme}] no script errors {errs[:2]}")
            await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
