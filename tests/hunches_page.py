"""/hunches/ on a phone, light and dark: cards by game, each with evidence, the case against and a verdict; the filter chips; FanDuel links
that match the board's ids; the week's frozen file.   python3 tests/hunches_page.py [shots_dir]"""
import asyncio, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8867; SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
async def main():
    D = json.load(open(os.path.join(ROOT, "b", "hunches.json"))); live = [h for h in D["hunches"] if not h.get("gone")]; W = D["week"]
    bdir = os.path.join(ROOT, "build"); bf = [f for f in os.listdir(bdir) if f.startswith("data") and f.endswith((".js", ".json"))]
    blob = open(os.path.join(bdir, sorted(bf)[-1])).read() if bf else ""
    legs = [h["leg"] for h in live if h.get("leg")]
    check(len(live) >= 1 and all(h["ev"] and h["vs"] and h["verdict"] in ("Backed", "Mixed", "Caution", "Info") for h in live), f"every hunch has evidence, a case against and a verdict ({len(live)} this week)")
    check(all(not h.get("leg") for h in live if h["verdict"] in ("Caution", "Info")) and all(not (h["leg"] or {}).get("bad") for h in live if h["verdict"] == "Backed"), "a Backed hunch never carries a leg the builder flags; cautions carry no leg")
    check(not blob or all(str(l["fs"]) in blob for l in legs), f"every suggested leg's FanDuel selection id is on the builder's board ({len(legs)} legs)")
    fz = json.load(open(os.path.join(ROOT, "data", f"hunches-w{W}.json")))
    check({h["id"] for h in live} <= {h["id"] for h in fz["hunches"]}, f"the week's list is frozen in data/hunches-w{W}.json for grading ({len(fz['hunches'])})")
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            await ctx.route("**/*", lambda r: r.continue_() if "127.0.0.1" in r.request.url else r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/hunches/", wait_until="domcontentloaded"); await pg.wait_for_timeout(900)
            d = await pg.evaluate("(function(){ var c = [...document.querySelectorAll('.hx .hc')]; return {n: c.length, over: document.documentElement.scrollWidth - innerWidth, btn: [...document.querySelectorAll('.hx .hchips button, .hx .hleg a')].every(function(x){ return x.getBoundingClientRect().height >= 40; }), first: c.slice(0, 3).map(function(x){ return x.getAttribute('data-v'); }), menu: !!document.querySelector('a[href=\"/hunches/\"]'), h1: document.querySelector('.hx h1').textContent}; })()")
            check(d["n"] == len(live) and d["over"] <= 0 and d["btn"] and not errs, f"[{theme}] {d['n']} cards, no sideways scroll, every chip and FanDuel button 40px or taller ({d['over']}; {errs[:1]})")
            check(d["menu"], f"[{theme}] the site menu links to Hunches")
            await pg.click('#hchips button[data-k="Backed"]'); await pg.wait_for_timeout(150)
            v = await pg.evaluate("[...document.querySelectorAll('.hx .hc')].filter(function(c){ return c.getClientRects().length > 0; }).map(function(c){ return c.getAttribute('data-v'); })")
            nb = sum(1 for h in live if h["verdict"] == "Backed")
            check(len(v) == nb and all(x == "Backed" for x in v) and (nb > 0 or not await pg.evaluate("document.getElementById('hempty').hidden")), f"[{theme}] \"Backed only\" leaves the {nb} backed cards, and games with none fold away")
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"hunches_{theme}.png"))
            await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
