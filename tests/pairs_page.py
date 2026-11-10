#!/usr/bin/env python3
"""tests/pairs_page.py - the either-or touchdown pair maker at /pairs/ (build_pairs.py, pairs.py).

Needs a built site served locally (BASE, default http://localhost:8802) and out/builder_data.json from the same build. Checks: the page's
arithmetic is pairs.py's to nine decimals for every pair on the board; picking a pair shows its chance, fair price and risk; FanDuel's
price gets a verdict; the best-pairs list fills the picker; a kicked-off game drops out; a ruled-out player is called out; phone width.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
import pairs as PR
BASE = os.environ.get("BASE", "http://localhost:8802")
BD = json.load(open(os.path.join(HERE, "out", "builder_data.json"))); GAMES = {g["gid"]: g for g in BD["games"]}
TD = {l["pl"]: l for l in BD["legs"] if l["m"] == "Anytime TD" and l.get("p") is not None and l.get("o") is not None}

async def run():
    fails = []
    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok: fails.append(what)
    if len(TD) < 4: print("skip: fewer than four anytime-TD prices on the board this build"); return fails
    async with async_playwright() as p:
        br = await p.chromium.launch()
        async def open_page(path="/pairs/", w=390, now=None, init=None):
            ctx = await br.new_context(viewport={"width": w, "height": 844}); pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            async def route(r):
                if r.request.url.startswith(BASE): await r.continue_()
                else: await r.abort()
            await pg.route("**/*", route)
            if now: await pg.clock.install(time=now)
            if init: await ctx.add_init_script(init)
            await pg.goto(BASE + path, wait_until="load"); await pg.wait_for_timeout(700)
            return ctx, pg, errs
        first_ko = min(g["ko"] for g in GAMES.values() if g.get("ko") and any(l["g"] == g["gid"] for l in TD.values()))
        early = (first_ko - 6 * 3600 * 1000) / 1000
        ctx, pg, errs = await open_page(now=early)
        # 1) same numbers as pairs.py
        names = sorted(TD); pairs_ = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
        js = await pg.evaluate("""(pp) => { const by = {}; BSPairs.data.players.forEach(t => by[t.n] = t); return pp.map(([a, b]) => { const e = BSPairs.either(by[a], by[b]); return [e.p, e.hedge, e.worst, e.sg, e.st]; }); }""", pairs_)
        worst = 0.0; bad = None
        for (a, b), (jp, jh, jw, sg, st) in zip(pairs_, js):
            e = PR.either(TD[a], TD[b], GAMES)
            # the page carries each chance rounded to 4 places, so allow that much
            d = max(abs(e["p"] - jp), abs(e["hedge"] - jh), abs((e["worst"] or 0) - (jw or 0)))
            if d > worst: worst, bad = d, (a, b, e["p"], jp)
            if sg != e["same_game"] or st != e["same_team"]: worst, bad = 1, (a, b, "flags")
        check(worst < 2e-4, f"the page's arithmetic is pairs.py's for all {len(pairs_)} pairs (largest gap {worst:.6f}) {bad if worst >= 2e-4 else ''}")
        # 2) pick a pair
        S = """() => { const o = document.getElementById('prout'); return {big: (o.querySelector('.big') || {}).textContent || '', txt: o.textContent.replace(/\\s+/g, ' '), rk: (o.querySelector('.rk') || {}).textContent || '', v: (document.getElementById('prv') || {}).textContent || '',
                 best: [...document.querySelectorAll('#prbest button')].map(b => [b.dataset.a, b.dataset.b, b.querySelector('em').textContent]), a: document.getElementById('pra').value, b: document.getElementById('prb').value,
                 nopt: document.querySelectorAll('#pra option').length, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth}; }"""
        v = await pg.evaluate(S)
        check("Pick two players" in v["txt"] and v["nopt"] == len(TD) + 1, f"opens empty with every priced player in the picker ({v['nopt'] - 1})")
        check(1 <= len(v["best"]) <= 8 and max(sum(1 for r in v["best"] if n in r[:2]) for n in {x for r in v["best"] for x in r[:2]}) <= 2, f"best pairs: {len(v['best'])} rows, nobody more than twice")
        a, b = v["best"][0][0], v["best"][0][1]; e = PR.either(TD[a], TD[b], GAMES)
        await pg.click("#prbest button"); await pg.wait_for_timeout(300); v = await pg.evaluate(S)
        check(v["a"] == a and v["b"] == b and f"{e['p'] * 100:.0f}%" in v["big"] and "fair price" in v["big"], f"tapping the first row fills the picker and prices it ({v['big'][:60]})")
        check(v["rk"] in ("Low risk", "Some risk", "High risk") and "alone" in v["txt"] and "FanDuel" in v["txt"], f"shows each single, and the pair's risk ({v['rk']})")
        fair = PR.fair_american(e["p"])
        await pg.fill("#prfd", str(fair - 400 if fair < 0 else -400)); await pg.wait_for_timeout(200); v1 = await pg.evaluate(S)
        await pg.fill("#prfd", "+150"); await pg.wait_for_timeout(200); v2 = await pg.evaluate(S)
        await pg.fill("#prfd", "abc"); await pg.wait_for_timeout(200); v3 = await pg.evaluate(S)
        await pg.fill("#prfd", "50"); await pg.wait_for_timeout(200); v4 = await pg.evaluate(S)
        check("paying" in v1["v"] and "too much" in v1["v"], f"a price far past fair: paying too much ({v1['v'][:90]})")
        check("on your side" in v2["v"], "a plus price on a likely pair: points on your side")
        check(v3["v"] == "" and "Type the price" in v4["v"], "letters are ignored; a number that is not a price asks for one")
        await pg.select_option("#prb", a); await pg.wait_for_timeout(200); v = await pg.evaluate(S)
        check("two different players" in v["txt"], "the same player twice is refused")
        check(v["sw"] <= v["cw"] and not errs, f"fits a phone, no errors ({v['sw']}/{v['cw']}) {errs[:2]}"); await ctx.close()
        # 3) a link can carry the pair; a same-game pair explains itself
        sg = next(((x, y) for x, y in pairs_ if TD[x]["g"] == TD[y]["g"]), None); cg = next(((x, y) for x, y in pairs_ if TD[x]["g"] != TD[y]["g"]), None)
        if sg:
            from urllib.parse import quote
            ctx, pg, errs = await open_page(f"/pairs/?a={quote(sg[0])}&b={quote(sg[1])}", now=early); v = await pg.evaluate(S)
            check(v["a"] == sg[0] and v["b"] == sg[1] and "Worst ending" in v["txt"] and not errs, "a link with ?a=&b= opens on that pair; a same-game pair shows its worst ending"); await ctx.close()
        if cg:
            from urllib.parse import quote
            ctx, pg, errs = await open_page(f"/pairs/?a={quote(cg[0])}&b={quote(cg[1])}", now=early); v = await pg.evaluate(S)
            check("Different games" in v["txt"] and "Worst ending" not in v["txt"], "two games: says they do not affect each other"); await ctx.close()
        # 4) kickoffs
        kos = sorted({GAMES[l["g"]]["ko"] for l in TD.values()})
        if len(kos) > 1:
            ctx, pg, errs = await open_page(now=(kos[0] + 60000) / 1000); v = await pg.evaluate(S)
            left = sum(1 for l in TD.values() if GAMES[l["g"]]["ko"] > kos[0] + 60000)
            check(v["nopt"] == left + 1 and not errs, f"after the first kickoff its players are gone ({v['nopt'] - 1} left of {len(TD)})"); await ctx.close()
        ctx, pg, errs = await open_page(now=(kos[-1] + 60000) / 1000)
        t = await pg.evaluate("document.getElementById('prcard').textContent"); check("has kicked off" in t and not errs, "after the last kickoff the page says so"); await ctx.close()
        # 5) a player ruled out since the build
        outp = sorted(TD, key=lambda n: -TD[n]["p"])[0]; other = next(n for n in names if n != outp)
        init = "document.addEventListener('DOMContentLoaded', function(){ window.BSRisk = {verdict: function(pl){ return pl === %s ? {level: 'block', why: 'Ruled out'} : null; }}; document.dispatchEvent(new Event('bs-risk')); });" % json.dumps(outp)
        from urllib.parse import quote
        ctx, pg, errs = await open_page(f"/pairs/?a={quote(outp)}&b={quote(other)}", now=early, init=init); await pg.wait_for_timeout(600); v = await pg.evaluate(S)
        check("is ruled out" in v["txt"] and "single on " + other in v["txt"] and all(outp not in r[:2] for r in v["best"]) and not errs, f"a ruled-out player: called out, and left off the best pairs {errs[:2]}"); await ctx.close()
        ctx, pg, errs = await open_page(w=1280, now=early); v = await pg.evaluate(S); check(v["sw"] <= v["cw"] and not errs, "desktop: no sideways scroll, no errors"); await ctx.close()
        await br.close()
    return fails

if __name__ == "__main__":
    f = asyncio.run(run()); print("pairs page:", "all checks passed" if not f else f"{len(f)} FAILED"); sys.exit(1 if f else 0)
