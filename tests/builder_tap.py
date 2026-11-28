"""An add on the Parlay Builder answers at once: a slip change only flips the best-legs cards it touches (11/28).

Every change to the slip - an add or a remove anywhere on the page - used to redraw the whole "Best legs near -110" strip: about 150
cards, each with its bars, logos and matchup pills. On the copy live before this an add cost about 100 ms of the browser's time on a
desktop processor (four to six times that on a phone); with the strip left alone, about 40. This test holds the behaviour that makes
it so, without timing anything (a stopwatch is at the mercy of the machine):
  - a tap on a card's button flips that card - its button, its state - and every card on the strip is still the same node;
  - a leg added from elsewhere on the page (the hook the site menu's Ask BetSweep uses) flips its card too, and back again;
  - the strip is still drawn whole when it has to be: a filter, or a card whose game has kicked off since it was drawn.
And the strip itself is drawn a few cards at once and the rest in batches straight after (it was a quarter of the page's work at
load, and most of a second on a phone after a tap on a filter): every card still arrives, the list says it is busy until the last
batch, and a leg added while batches are still landing is marked on its card when that card arrives.

Runs in any week on the builder as built; the clock is set a day and a half before the first kickoff.
  python3 tests/builder_tap.py        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, os, re, sys, threading
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
PORT = 8912; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
bh = open(os.path.join(ROOT, "build", "index.html"), encoding="utf-8").read(); _m = re.search(r'src="(/build/data-[0-9a-f]+\.js)"', bh)
js = open(os.path.join(ROOT, _m.group(1).lstrip("/")), encoding="utf-8").read(); BS = json.JSONDecoder().raw_decode(js[js.index("{", js.index("window.__BS = ")):])[0]
KOS = sorted(g["ko"] for g in BS["games"] if g.get("ko"))
# every card: which leg, whether it is on, what its button says; and how many still carry the mark put on them
READ = """() => { var cs = Array.from(document.querySelectorAll('#bql .bqc')); return {n: cs.length, kept: cs.filter(function(c){ return c.__mark === 1; }).length,
  cards: cs.map(function(c){ var b = c.querySelector('button[data-i]'); return {i: +b.getAttribute('data-i'), on: c.classList.contains('on'), txt: b.textContent.trim(), pressed: b.getAttribute('aria-pressed')}; }),
  slip: window.bsSlipCount ? window.bsSlipCount() : null}; }"""
MARK = "() => { Array.from(document.querySelectorAll('#bql .bqc')).forEach(function(c){ c.__mark = 1; }); }"

async def main():
    if not KOS:
        check(True, "the builder's data has no kickoff times this build: nothing to check"); print(f"{ok[0]} passed, {ok[1]} failed"); return
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); srv.handle_error = lambda *a: None; threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
        T0 = int(KOS[0] - 36 * 3600e3)
        await ctx.add_init_script(f"(function(){{var R=Date.now,S=R();window.__T={T0};Date.now=function(){{return window.__T+(R()-S)}};window.__setT=function(t){{window.__T=t-(R()-S)}};}})();")
        async def gate(route, request): await (route.continue_() if "127.0.0.1" in request.url else route.abort())
        await ctx.route("**/*", gate)
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        async def settle():   # the strip's batches have all landed
            await pg.wait_for_function("() => { var u = document.getElementById('bql'); return !u || !u.hasAttribute('aria-busy'); }", timeout=15000)
        await pg.goto(f"http://127.0.0.1:{PORT}/build/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500); await settle()
        s0 = await pg.evaluate(READ)
        if not s0["n"]:
            check(True, "no card on the best-legs strip right now: nothing to check"); print(f"{ok[0]} passed, {ok[1]} failed"); await b.close(); return
        legs = BS["legs"]; key = lambda l: f'{l["pl"]}|{l["m"]}|{int(float(l.get("ln") or 1) + 0.5)}'
        print(f"   {s0['n']} cards on the strip; clock a day and a half before the first kickoff")
        # ---- every card arrives: the strip's list of overs, read here from the builder's own data ----
        KEYI = {}
        for i, l in enumerate(legs): KEYI.setdefault(key(l), i)
        overs = [KEYI[x[0]] for x in (BS.get("sug") or []) if x[0] in KEYI and not legs[KEYI[x[0]]].get("u")]
        check([c["i"] for c in s0["cards"]] == overs and len(overs) >= 1, f"the strip is drawn in batches and every card arrives, in the builder's own order ({s0['n']} cards on the page, {len(overs)} overs on the list)")
        # ---- a tap on a card: that card flips, and every card is still the same node ----
        await pg.evaluate(MARK); c0 = s0["cards"][0]
        await pg.tap(f'#bql .bqc button[data-i="{c0["i"]}"]'); await pg.wait_for_timeout(350); s1 = await pg.evaluate(READ)
        me = next(c for c in s1["cards"] if c["i"] == c0["i"]); others = [c for c in s1["cards"] if c["i"] != c0["i"]]
        check(me["on"] and me["txt"].startswith("In slip") and me["pressed"] == "true" and s1["slip"] == 1 and not any(c["on"] for c in others), f"a tap on a card's button puts that leg in the slip and the card says so ({me}; slip {s1['slip']})")
        check(s1["n"] == s0["n"] and s1["kept"] == s0["n"], f"and the strip was not redrawn for it: all {s0['n']} cards are the same nodes as before the tap ({s1['kept']} kept)")
        # ---- a leg added from elsewhere on the page flips its card too ----
        c1 = next((c for c in s0["cards"] if legs[c["i"]]["g"] != legs[c0["i"]]["g"]), s0["cards"][-1]); k1 = key(legs[c1["i"]])
        r = await pg.evaluate("(k) => window.bsSlipToggle(k)", k1); await pg.wait_for_timeout(250); s2 = await pg.evaluate(READ); m2 = next(c for c in s2["cards"] if c["i"] == c1["i"])
        check(r is True and m2["on"] and m2["txt"].startswith("In slip") and m2["pressed"] == "true" and s2["slip"] == 2 and s2["kept"] == s0["n"], f"a leg added from elsewhere on the page flips its card as well, again with nothing redrawn ({m2}; {s2['kept']} of {s0['n']} kept)")
        r = await pg.evaluate("(k) => window.bsSlipToggle(k)", k1); await pg.wait_for_timeout(250); s3 = await pg.evaluate(READ); m3 = next(c for c in s3["cards"] if c["i"] == c1["i"])
        check(r is False and not m3["on"] and m3["txt"] == "+ Add to parlay" and m3["pressed"] == "false" and s3["slip"] == 1 and s3["kept"] == s0["n"], f"and taking it out again puts the card back ({m3})")
        # ---- the strip is still drawn whole when it has to be: a filter ----
        await pg.tap('#bq .bqf button[data-pos="RB"]'); await pg.wait_for_timeout(300); await settle(); s4 = await pg.evaluate(READ)
        check(s4["kept"] == 0 and all(legs[c["i"]].get("pos") == "RB" for c in s4["cards"]), f"a filter still draws the strip afresh: {s4['n']} running-back cards, none of them an old node")
        # back on All, with a leg added the instant the tap is made: its card is far down the strip and arrives in a later batch, already marked
        far = s0["cards"][-1]
        got = await pg.evaluate("(k) => { document.querySelector('#bq .bqf button[data-pos=\"\"]').click(); var u = document.getElementById('bql'); var first = u.children.length, busy = u.hasAttribute('aria-busy'); return {first: first, busy: busy, added: window.bsSlipToggle(k)}; }", key(legs[far["i"]]))
        await pg.wait_for_timeout(300); await settle(); s5 = await pg.evaluate(READ); late = next((c for c in s5["cards"] if c["i"] == far["i"]), None)
        check(s5["n"] == s0["n"] and next(c for c in s5["cards"] if c["i"] == c0["i"])["on"], f"and back on All the leg in the slip is still marked as in ({s5['n']} cards)")
        check(got["first"] < s0["n"] and got["busy"] and got["added"] is True and bool(late) and late["on"] and late["txt"].startswith("In slip"),
              f"the first cards are on the page at once ({got['first']} of {s0['n']}, the list marked busy) and a leg added before its card has arrived is marked when it does ({late})")
        await pg.evaluate("(k) => window.bsSlipToggle(k)", key(legs[far["i"]])); await pg.wait_for_timeout(200)
        # ---- ... and a card whose game has kicked off since the strip was drawn leaves on the next slip change ----
        g0 = min({legs[c["i"]]["g"] for c in s5["cards"]}, key=lambda g: next(x["ko"] for x in BS["games"] if x["gid"] == g)); ko0 = next(x["ko"] for x in BS["games"] if x["gid"] == g0)
        later = [c for c in s5["cards"] if next(x["ko"] for x in BS["games"] if x["gid"] == legs[c["i"]]["g"]) > ko0 + 3600e3 and not c["on"]]
        if not later: print("   every card on the strip kicks off within the same hour: the kickoff case has nothing to compare")
        else:
            await pg.evaluate(MARK); await pg.evaluate("(t) => window.__setT(t)", ko0 + 60e3)
            r = await pg.evaluate("(k) => window.bsSlipToggle(k)", key(legs[later[-1]["i"]])); await pg.wait_for_timeout(300); s6 = await pg.evaluate(READ)
            gone = [c for c in s6["cards"] if legs[c["i"]]["g"] == g0]; had = sum(1 for c in s5["cards"] if legs[c["i"]]["g"] == g0)
            check(r is True and had >= 1 and not gone and s6["n"] < s5["n"] and s6["kept"] == 0 and next(c for c in s6["cards"] if c["i"] == later[-1]["i"])["on"],
                  f"a minute after {g0} kicks off, the next slip change redraws the strip without its {had} card{'s' if had != 1 else ''} ({s5['n']} -> {s6['n']} cards) and the new leg is marked as in")
        check(not errs, f"no page errors ({errs[:1]})")
        await b.close()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
