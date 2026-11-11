#!/usr/bin/env python3
"""tests/simple_view.py - the Short view at /short/ (first shipped as "Simple view", hence the file names) and the Short / Full switch (build_simple.py, build_today.py).

Needs a built site served locally (BASE, default http://localhost:8802) with out/builder_data.json, out/best_parlays.json and
out/simple.json from the same build. Checks: the page fits a phone and throws nothing; the one-tap FanDuel links carry exactly the
legs written next to them (ids read back against the builder's data, no unders, favorites only, no risk flag); a tap opens a game's
best parlay; kicked-off games leave; the choice of view is kept and moves only the bare home address; a ruled-out player is struck.
"""
import asyncio, json, os, re, sys
from urllib.parse import unquote
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
import sweep as SW
BASE = os.environ.get("BASE", "http://localhost:8802")
BD = json.load(open(os.path.join(HERE, "out", "builder_data.json"))); SJ = json.load(open(os.path.join(HERE, "out", "simple.json")))
GAMES = {g["gid"]: g for g in BD["games"]}; BYID = {}
for l in BD["legs"]:
    if (l.get("fd") or {}).get("m") and l["fd"].get("s"): BYID[(str(l["fd"]["m"]), str(l["fd"]["s"]))] = l
def ids_of(href):
    q = unquote(href.split("?", 1)[1]) if "?" in href else ""
    m = dict(re.findall(r"marketId\[(\d+)\]=([\d.]+)", q)); s = dict(re.findall(r"selectionId\[(\d+)\]=(\d+)", q))
    return [(m[i], s[i]) for i in sorted(m, key=int) if i in s]

async def run():
    fails = []
    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok: fails.append(what)
    kos = sorted(g["ko"] for g in GAMES.values() if g.get("ko")); early = (kos[0] - 6 * 3600 * 1000) / 1000
    async with async_playwright() as p:
        br = await p.chromium.launch()
        async def ctx_page(w=390, now=early, scheme="dark", store=None, init=None):
            ctx = await br.new_context(viewport={"width": w, "height": 844}, color_scheme=scheme); pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            async def route(r):
                if r.request.url.startswith(BASE): await r.continue_()
                else: await r.abort()
            await pg.route("**/*", route)
            if now: await pg.clock.install(time=now)
            if store is not None: await ctx.add_init_script("try{ if(!sessionStorage.getItem('__seeded')){ localStorage.setItem('bs_view', %s); sessionStorage.setItem('__seeded', '1'); } }catch(e){}" % json.dumps(store))
            if init: await ctx.add_init_script(init)
            return ctx, pg, errs
        S = """() => ({rows: [...document.querySelectorAll('.sv .gm')].filter(e => !e.hidden).map(e => e.dataset.g), days: [...document.querySelectorAll('.sv h3[data-day]')].filter(e => !e.hidden).map(e => e.textContent),
                 easy: [...document.querySelectorAll('#sveasy li')].map(li => [li.dataset.pl, li.dataset.m, li.querySelector('b').textContent, li.classList.contains('gone')]), easyHidden: !document.getElementById('sveasy') || document.getElementById('sveasy').hidden,
                 go: (() => { const a = document.querySelector('#sveasy .bsbtn'); return a && !a.hidden ? a.href : ''; })(), keep: (document.getElementById('svkeep') || {}).textContent || '', none: !document.getElementById('svnone').hidden, head: !document.getElementById('svgames').hidden,
                 fn: (document.getElementById('sveasyfn') || {}).textContent || '', pref: localStorage.getItem('bs_view'), sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, path: location.pathname,
                 bg: getComputedStyle(document.body).backgroundColor, font: getComputedStyle(document.querySelector('.sv h1')).fontFamily, logo: !!document.querySelector('.sitenav .brand img')})"""
        ctx, pg, errs = await ctx_page(); await pg.goto(BASE + "/short/", wait_until="load"); await pg.wait_for_timeout(600); v = await pg.evaluate(S)
        check(v["sw"] <= v["cw"] and not errs, f"phone: no sideways scroll, no errors ({v['sw']}/{v['cw']}) {errs[:2]}")
        check(len(v["rows"]) == len(GAMES) and v["head"] and not v["none"], f"every game of the week is one row ({len(v['rows'])})")
        check("Barlow" in v["font"] and v["logo"], f"the site's own header and type ({v['font'][:30]})")
        # the one-tap link carries exactly the three legs written above it
        if SJ["easy"]:
            ids = ids_of(v["go"]); legs = [BYID.get(i) for i in ids]
            check(len(ids) == 3 and all(legs) and [l["pl"] for l in legs] == [e[0] for e in v["easy"]] and [l["m"] for l in legs] == [e[1] for e in v["easy"]], f"'Bet all 3' link read back: its ids are the three legs shown, in order {[(l or {}).get('pl') for l in legs]}")
            check(all(not l.get("u") and not l["m"].startswith("Under") and not l.get("gl") for l in legs), "none of them is an under or a game line")
            check(all(-350 <= l["o"] <= -140 and SW.risk_score(l, BD) < 2 for l in legs) and len({l["pl"] for l in legs}) == 3, "all three are favorites with no risk flag, three different players")
            check(all(str(int(round(l["ln"]))) + "+" in e[2] or l["m"] == "Anytime TD" for l, e in zip(legs, v["easy"])), "the line printed is the line in the link")
        else: check(v["easyHidden"], "no easy picks this build: the card is not there")
        # a game opens to its best parlay
        g0 = next((r for r in SJ["games"] if r["bp"]), None)
        if g0:
            await pg.click(f'.gm[data-g="{g0["gid"]}"] summary'); await pg.wait_for_timeout(200)
            o = await pg.evaluate("""(g) => { const d = document.querySelector('.gm[data-g="' + g + '"]'); const a = d.querySelector('.bp a.bsbtn'); return {open: d.open, bp: (d.querySelector('.bp span') || {}).textContent || '', href: a ? a.href : '', more: d.querySelector('.more').getAttribute('href'), say: !!d.querySelector('.sweepsays')}; }""", g0["gid"])
            check(o["open"] and o["bp"] and o["more"] == "/boards/#" + g0["gid"], f"tap a game: best parlay and a way to its full board ({o['bp'][:50]})")
            if o["href"]:
                legs = [BYID.get(i) for i in ids_of(o["href"])]
                check(all(legs) and [(l["pl"], l["m"], round(float(l["ln"] or 0), 1)) for l in legs] == [(x[0], x[1], round(float(x[2] or 0), 1)) for x in g0["bp"]] and all(l["g"] == g0["gid"] for l in legs), "the best parlay's Bet link read back: the same legs at the same lines, from that game")
        await ctx.close()
        # kickoffs
        ctx, pg, errs = await ctx_page(now=(kos[0] + 60000) / 1000); await pg.goto(BASE + "/short/", wait_until="load"); await pg.wait_for_timeout(500); v = await pg.evaluate(S)
        left = [g for g in GAMES.values() if g["ko"] > kos[0] + 60000]
        check(len(v["rows"]) == len(left) and not errs, f"after the first kickoff that game is gone ({len(v['rows'])} of {len(GAMES)} left)")
        first_day_left = any(g["kick"].split(" ")[0] == sorted(GAMES.values(), key=lambda g: g["ko"])[0]["kick"].split(" ")[0] for g in left)
        check(len(v["days"]) == len({g["kick"].split(" ")[0] for g in left}), f"a day with nothing left loses its heading {v['days']}")
        if SJ["easy"]:
            ez_ko = min(GAMES[e["g"]]["ko"] for e in SJ["easy"]); check(v["easyHidden"] == (kos[0] + 60000 >= ez_ko), "the easy picks go once one of their games has started")
        await ctx.close()
        ctx, pg, errs = await ctx_page(now=(kos[-1] + 60000) / 1000); await pg.goto(BASE + "/short/", wait_until="load"); await pg.wait_for_timeout(500); v = await pg.evaluate(S)
        check(v["rows"] == [] and v["none"] and not v["head"] and v["easyHidden"] and not errs, "after the last kickoff the page says so"); await ctx.close()
        # the switch
        ctx, pg, errs = await ctx_page(); await pg.goto(BASE + "/", wait_until="load"); await pg.wait_for_timeout(600)
        pill = await pg.evaluate("(() => { const a = document.getElementById('tdsimple'); return a ? [a.textContent, a.getAttribute('href'), location.pathname] : null; })()")
        check(pill == ["Short view", "/short/", "/"], f"home page (no choice made): stays Full and offers the Short view pill {pill}")
        await pg.click("#tdsimple"); await pg.wait_for_url("**/short/"); await pg.wait_for_timeout(400); v = await pg.evaluate(S)
        check(v["path"] == "/short/" and v["pref"] == "short" and "your home page" in v["keep"], "tapping the pill opens the Short view and keeps the choice")
        await pg.goto(BASE + "/", wait_until="load"); await pg.wait_for_timeout(600); check((await pg.evaluate("location.pathname")) == "/short/", "the bare home address now opens the Short view")
        await pg.goto(BASE + "/?source=app", wait_until="load"); await pg.wait_for_timeout(600); check((await pg.evaluate("location.pathname")) == "/short/", "so does the installed app's start address")
        await pg.goto(BASE + "/?source=push", wait_until="load"); await pg.wait_for_timeout(500); a1 = await pg.evaluate("location.pathname")
        await pg.goto(BASE + "/#sweep", wait_until="load"); await pg.wait_for_timeout(500); a2 = await pg.evaluate("location.pathname")
        await pg.goto(BASE + "/boards/", wait_until="load"); await pg.wait_for_timeout(300); a3 = await pg.evaluate("location.pathname")
        check(a1 == "/" and a2 == "/" and a3 == "/boards/", "a notification link, a link to a section and every other page are left alone")
        await pg.goto(BASE + "/short/", wait_until="load"); await pg.wait_for_timeout(300); await pg.click("#svfull"); await pg.wait_for_timeout(900)
        check((await pg.evaluate("[location.pathname, localStorage.getItem('bs_view')]")) == ["/", "full"] and not errs, f"Full goes back to the full home page and stays there {errs[:2]}"); await ctx.close()
        ctx, pg, errs = await ctx_page(); await pg.goto(BASE + "/short/", wait_until="load"); await pg.wait_for_timeout(400); v = await pg.evaluate(S)
        check(v["pref"] is None and "Make this my home page" in v["keep"], "opening /short/ from a link does not change anyone's home page by itself")
        await pg.click("#svkeepb"); await pg.wait_for_timeout(200); v = await pg.evaluate(S); check(v["pref"] == "short" and "your home page" in v["keep"], "'Make this my home page' does"); await ctx.close()
        # the name it had for an afternoon: the old address lands on the new one, and a choice stored under the old name still counts
        ctx, pg, errs = await ctx_page(); await pg.goto(BASE + "/simple/?x=1#y", wait_until="load"); await pg.wait_for_timeout(700)
        check((await pg.evaluate("location.pathname + location.search + location.hash")) == "/short/?x=1#y" and not errs, "the old /simple/ address lands on /short/ and keeps what followed it"); await ctx.close()
        ctx, pg, errs = await ctx_page(store="simple"); await pg.goto(BASE + "/", wait_until="load"); await pg.wait_for_timeout(700); v = await pg.evaluate(S)
        check(v["path"] == "/short/" and "your home page" in v["keep"], "a phone that chose 'Simple' before the rename still opens the Short view"); await ctx.close()
        # a player ruled out since the build
        if SJ["easy"]:
            init = "document.addEventListener('DOMContentLoaded', function(){ window.BSRisk = {verdict: function(pl){ return pl === %s ? {level: 'block', why: 'Ruled out'} : null; }}; document.dispatchEvent(new Event('bs-risk')); });" % json.dumps(SJ["easy"][0]["pl"])
            ctx, pg, errs = await ctx_page(init=init); await pg.goto(BASE + "/short/", wait_until="load"); await pg.wait_for_timeout(700); v = await pg.evaluate(S)
            check(v["easy"][0][3] and not v["go"] and "ruled out" in v["fn"] and not errs, f"a ruled-out player: his pick is struck and the one-tap button is gone {errs[:2]}"); await ctx.close()
        # looks: dark and light both come from the site's palette; desktop
        ctx, pg, errs = await ctx_page(scheme="dark"); await pg.goto(BASE + "/short/", wait_until="load"); await pg.wait_for_timeout(400); d = await pg.evaluate(S)
        if os.environ.get("SHOTS"): await pg.screenshot(path=os.path.join(os.environ["SHOTS"], "simple-dark.png"), clip={"x": 0, "y": 0, "width": 390, "height": 1250}, full_page=True)
        await ctx.close()
        ctx, pg, errs = await ctx_page(scheme="light"); await pg.goto(BASE + "/short/", wait_until="load"); await pg.wait_for_timeout(400); l = await pg.evaluate(S)
        if os.environ.get("SHOTS"):
            await pg.click(".sv .gm summary"); await pg.wait_for_timeout(200); await pg.screenshot(path=os.path.join(os.environ["SHOTS"], "simple-light.png"), clip={"x": 0, "y": 0, "width": 390, "height": 1250}, full_page=True)
        await ctx.close()
        check(d["bg"] != l["bg"], f"dark and light follow the site's palette (dark {d['bg']}, light {l['bg']})")
        ctx, pg, errs = await ctx_page(w=1280); await pg.goto(BASE + "/short/", wait_until="load"); await pg.wait_for_timeout(400); v = await pg.evaluate(S)
        check(v["sw"] <= v["cw"] and not errs, "desktop: no sideways scroll, no errors"); await ctx.close()
        await br.close()
    return fails

if __name__ == "__main__":
    f = asyncio.run(run()); print("short view:", "all checks passed" if not f else f"{len(f)} FAILED"); sys.exit(1 if f else 0)
