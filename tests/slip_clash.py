"""Two lines of one player's market on the same slip (owner 11/24: "Matt Stafford +200 from the builder and then ... +275 from the today
page ... those 2 legs conflict and won't work on FanDuel"). slipclash.py, appended to /account.js.
  1. the rule (node): which slips clash and which do not;
  2. the bar on a real page (SITE or ./site, /today/) on a phone, light and dark: it names the legs, fits, keeps one line on a tap.
  python3 tests/slip_clash.py"""
import asyncio, json, os, subprocess, sys, threading, http.server, functools
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); sys.path.insert(0, HERE)
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8896
import slipclash as SC
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
A, B, C = "Matthew Stafford|Passing Yards|200", "Matthew Stafford|Passing Yards|275", "Matthew Stafford|Passing TDs|2"
def find(keys):
    js = ("var window = {addEventListener: function(){}}, document = {readyState: 'complete', body: null, getElementById: function(){ return null; }}, Storage = function(){}, localStorage = {length: 0}, sessionStorage = {getItem: function(){ return null; }};\n"
          + SC.CLASH_JS + "\nconsole.log(JSON.stringify(window.BSClash.find(" + json.dumps(keys) + ")));")
    return json.loads(subprocess.check_output(["node", "-e", js], text=True))
r = find([A, "Kyren Williams|Anytime TD|1", B])
check(len(r) == 1 and r[0]["player"] == "Matthew Stafford" and r[0]["market"] == "Passing Yards" and [l["text"] for l in r[0]["legs"]] == ["200+", "275+"] and [l["key"] for l in r[0]["legs"]] == [A, B],
      f"the same player's passing yards at 200+ and 275+ is a clash, named with both lines ({r})")
check(find([A, C, "Jordan Love|Passing Yards|250", "Kyren Williams|Anytime TD|1", "Kyren Williams|Receiving Yards|20"]) == [], "different markets of one player, and the same market of two players, are not a clash")
r = find([A, "Matthew Stafford|Under Passing Yards|251"])
check(len(r) == 1 and [l["text"] for l in r[0]["legs"]] == ["200+", "under 251"], "an over and an under of the same market are the same market")
check(find([A, A]) == [] and find([]) == [] and find(None) == [] and find(["Over 44.5 (GB-LA)|Total|45", "Under 47.5 (GB-LA)|Total|48", "x", "|Passing Yards|200", "|Passing Yards|250"]) == [],
      "the same key twice, an empty slip, game lines and keys that are not legs raise nothing")
r = find([A, B, "Matthew Stafford|Passing Yards|300", "Puka Nacua|Receiving Yards|60", "Puka Nacua|Receiving Yards|80"])
check(len(r) == 2 and len(r[0]["legs"]) == 3 and r[1]["player"] == "Puka Nacua", "three lines of one market are one clash with three choices; a second player's clash is listed after it")
check("//" not in "".join(l.split("http")[0] for l in SC.CLASH_JS.splitlines()) and "Storage.prototype.setItem" in SC.CLASH_JS, "the script has no line comments (it ships inside another file) and watches every write of the slip key")

async def pages():
    from playwright.async_api import async_playwright
    if not os.path.exists(os.path.join(ROOT, "today", "index.html")): check(True, "(no built site here: the page part is skipped)"); return
    check(SC.CLASH_JS.strip()[:40] in open(os.path.join(ROOT, "account.js"), encoding="utf-8").read(), "the built /account.js carries the script")
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{ localStorage.setItem('bs_theme','{theme}'); if(!sessionStorage.getItem('t_seeded')){{ sessionStorage.setItem('t_seeded','1'); localStorage.setItem('bs_slipk_w98', JSON.stringify({json.dumps([A, 'Kyren Williams|Anytime TD|1', B])})); }} }}catch(e){{}}")
            await ctx.route("**/*supabase*/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
            await pg.goto(f"http://127.0.0.1:{PORT}/today/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
            s = await pg.evaluate("""() => { var e = document.getElementById('bsclash'); if(!e || e.hidden) return null; var r = e.getBoundingClientRect(), cs = getComputedStyle(e);
              return {txt: e.innerText.replace(/\\s+/g, ' '), top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right), btns: Array.from(e.querySelectorAll('button')).map(function(x){ var q = x.getBoundingClientRect(); return [x.textContent, Math.round(q.height), q.right <= r.right + 1]; }),
                      over: document.documentElement.scrollWidth - innerWidth, bg: cs.backgroundColor, ink: cs.color}; }""")
            check(bool(s) and "Matthew Stafford passing yards is on your slip twice (200+ and 275+)" in s["txt"] and "FanDuel takes one line per player and market" in s["txt"], f"[{theme}] with both lines on the slip, Today shows the bar naming the player, the market and the two lines ({(s or {}).get('txt', '')[:90]})")
            check(bool(s) and [x[0] for x in s["btns"]] == ["Keep 200+", "Keep 275+", "Leave both"] and all(x[1] >= 32 and x[2] for x in s["btns"]) and s["left"] >= 0 and s["right"] <= 390 and s["top"] >= 0 and s["bottom"] <= 844 - 60 and s["over"] <= 0 and s["bg"] != s["ink"],
                  f"[{theme}] it sits above the bottom tabs, inside the screen, with a button for each line and one to leave both ({s and [s['top'], s['bottom'], s['btns']]})")
            if len(sys.argv) > 1: await pg.screenshot(path=os.path.join(sys.argv[1], f"clash_{theme}.png"))
            await pg.click('#bsclash button[data-keep="all"]'); await pg.wait_for_timeout(250)
            gone = await pg.evaluate("document.getElementById('bsclash').hidden"); kept = await pg.evaluate("JSON.parse(localStorage.getItem('bs_slipk_w98'))")
            check(gone and len(kept) == 3, f"[{theme}] 'Leave both' puts the bar away and removes nothing")
            await pg.evaluate("localStorage.setItem('bs_slipk_w98', JSON.stringify(" + json.dumps([A, B, "Puka Nacua|Receiving Yards|60"]) + "))"); await pg.wait_for_timeout(250)
            back = await pg.evaluate("!document.getElementById('bsclash').hidden")
            await pg.evaluate("sessionStorage.removeItem('bs_clash_ok'); window.BSClash.check()"); await pg.wait_for_timeout(150)
            await pg.click('#bsclash button[data-keep="1"]'); await pg.wait_for_timeout(1800)
            after = await pg.evaluate("({keys: JSON.parse(localStorage.getItem('bs_slipk_w98')), bar: (function(){ var e = document.getElementById('bsclash'); return !!e && !e.hidden; })()})")
            check(after["keys"] == [B, "Puka Nacua|Receiving Yards|60"] and not after["bar"], f"[{theme}] 'Keep 275+' drops the 200+ line only, and after the page reloads there is no bar ({after}; bar hidden after 'Leave both' until the slip changed: {not back})")
            check(not errs, f"[{theme}] no script errors {errs[:2]}")
            await ctx.close()
        await b.close()
    srv.shutdown()
asyncio.run(pages())
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
