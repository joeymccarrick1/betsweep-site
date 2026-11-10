#!/usr/bin/env python3
"""tests/sweep_hero.py - the Daily Sweep hero on the home page, at four moments of the week (owner 11/10).

Needs a built site served locally (BASE, default http://localhost:8802) whose week has a Daily Sweep row for the first game day:
  python3 tests/sweep_hero.py            -> prints one line per check, exits 1 on a failure
The clock is faked in the browser and ESPN is answered from this file, so nothing outside the machine is touched.
  A  two days before the first kickoff: the day's card shows, status Pregame, teaser hidden
  B  during the game: legs get their hit / miss marks from the (fake) box score, the card stays up
  C  the next morning, every leg hit: card gone, teaser says when the next one posts and "Last: ... Cashed"
  D  the next morning, one leg missed: "Last: ... Missed" and the card was never hidden while it was the day's card
"""
import asyncio, json, os, re, sys
from playwright.async_api import async_playwright
BASE = os.environ.get("BASE", "http://localhost:8802")
SHOTS = os.environ.get("SHOTS")   # a folder for two phone screenshots (the card, the teaser); unset = no pictures

def espn(state, box, gid, eid="401"):
    a, b = gid.split("-")
    sb = {"events": [{"id": eid, "status": {"type": {"state": state}}, "competitions": [{"competitors": [{"team": {"abbreviation": a}, "score": "17"}, {"team": {"abbreviation": b}, "score": "24"}]}]}]}
    cats = {"passing": ["passingYards"], "rushing": ["rushingYards", "rushingTouchdowns"], "receiving": ["receptions", "receivingYards", "longReception", "receivingTouchdowns"]}
    stats = []
    for cat, keys in cats.items():
        ath = []
        for name, r in box.items():
            vals = {"passingYards": r.get("pass"), "rushingYards": r.get("rush"), "rushingTouchdowns": 0, "receptions": r.get("rec"), "receivingYards": r.get("recy"), "longReception": 0, "receivingTouchdowns": 0}
            if any(vals[k] is not None for k in keys if k not in ("rushingTouchdowns", "longReception", "receivingTouchdowns")):
                ath.append({"athlete": {"displayName": name}, "stats": [str(vals[k] or 0) for k in keys]})
        stats.append({"name": cat, "keys": keys, "athletes": ath})
    return sb, {"boxscore": {"players": [{"statistics": stats}]}, "scoringPlays": []}

async def run():
    fails = []
    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok: fails.append(what)
    async with async_playwright() as p:
        br = await p.chromium.launch()
        async def page_at(ms, state=None, box=None, gid=None):
            ctx = await br.new_context(viewport={"width": 390, "height": 844}); pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.clock.install(time=ms / 1000)
            sb, summ = espn(state, box or {}, gid) if state else ({"events": []}, {})
            async def route(r):
                u = r.request.url
                if u.startswith(BASE): await r.continue_()
                elif "site.api.espn.com" in u and "scoreboard" in u: await r.fulfill(status=200, content_type="application/json", body=json.dumps(sb))
                elif "site.api.espn.com" in u and "summary" in u: await r.fulfill(status=200, content_type="application/json", body=json.dumps(summ))
                else: await r.abort()
            await pg.route("**/*", route)
            await pg.goto(BASE + "/", wait_until="load"); await pg.clock.run_for(3000); await pg.wait_for_timeout(700)
            return ctx, pg, errs
        # the page's own data: days and the first Sweep card
        ctx, pg, errs = await page_at(0)
        meta = await pg.evaluate("""()=>{ const s=document.getElementById('sweep'); if(!s) return null; const c=[...s.querySelectorAll('.promo.sweep')].map(a=>({day:a.dataset.day, f:+a.dataset.firstKo, l:+a.dataset.lastKo, legs:[...a.querySelectorAll('li[data-g]')].map(li=>({g:li.dataset.g, who:li.dataset.who, mk:li.dataset.mk}))}));
            return {days: JSON.parse(s.dataset.days), cards: c}; }""")
        await ctx.close()
        check(bool(meta), "hero section #sweep is on the page")
        if not meta or not meta["cards"]:
            check(False, "the week has a Daily Sweep card to test with"); await br.close(); return fails
        c0 = meta["cards"][0]; d0 = [d for d in meta["days"] if d["d"] == c0["day"]][0]; gid = c0["legs"][0]["g"]
        def need(mk): m = re.search(r"(\d+(?:\.\d+)?)\+", mk); return float(m.group(1)) if m else 1
        def boxfor(legs, miss=None):
            box = {}
            for i, L in enumerate(legs):
                v = need(L["mk"]) + (5 if i != miss else -3); k = L["mk"].lower(); r = box.setdefault(L["who"], {})
                if "passing" in k: r["pass"] = v
                elif "rushing" in k: r["rush"] = v
                elif "receptions" in k: r["rec"] = v
                elif "receiving" in k: r["recy"] = v
                elif "rush + rec" in k: r["rush"] = v
            return box
        vis = """()=>{ const s=document.getElementById('sweep'); const cs=[...s.querySelectorAll('.promo.sweep')].filter(a=>!a.hidden); const t=document.getElementById('swtease');
            return {n: cs.length, day: cs[0]&&cs[0].dataset.day, st: cs[0]&&cs[0].querySelector('.ph .st').textContent, hits: cs[0]?cs[0].querySelectorAll('li.hit').length:0, dead: cs[0]?cs[0].querySelectorAll('li.dead').length:0,
                    tease: t&&!t.hidden, next: t&&t.querySelector('.swnext').textContent, last: t&&!t.querySelector('.swlast').hidden ? t.querySelector('.swlast').textContent : '', sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
                    side: (document.querySelector('#promo h2')||{}).textContent||'', kick: [...document.querySelectorAll('#promo .promo .ph small')].map(e=>e.textContent)} }"""
        # A: two days before
        ctx, pg, errs = await page_at(c0["f"] - 2 * 864e5)
        v = await pg.evaluate(vis)
        if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, "sweep_A.png"), clip={"x": 0, "y": 0, "width": 390, "height": 1500}, full_page=True)
        await ctx.close()
        check(v["n"] == 1 and v["day"] == c0["day"] and v["st"] == "Pregame" and not v["tease"], f"A before the game: the day's card shows, Pregame, no teaser {v['n'], v['st'], v['tease']}")
        check(v["sw"] <= v["cw"], f"A no sideways scroll on a phone ({v['sw']} vs {v['cw']})")
        check(not errs, f"A no script errors {errs[:2]}")
        print("     side section:", v["side"], v["kick"])
        # B: in play, first leg already over its line, the rest not yet
        partial = {c0["legs"][0]["who"]: boxfor(c0["legs"][:1])[c0["legs"][0]["who"]]}
        ctx, pg, errs = await page_at(c0["f"] + 3600e3, "in", partial, gid)
        v = await pg.evaluate(vis); await ctx.close()
        check(v["n"] == 1 and v["hits"] == 1 and v["dead"] == 0 and v["st"] == "Pregame", f"B in play: one leg marked hit, card up {v['n'], v['hits'], v['dead'], v['st']}")
        # C: next morning, all hit
        ctx, pg, errs = await page_at(d0["end"] + 6 * 3600e3, "post", boxfor(c0["legs"]), gid)
        v = await pg.evaluate(vis)
        if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, "sweep_C.png"), clip={"x": 0, "y": 0, "width": 390, "height": 700}, full_page=True)
        await ctx.close()
        check(v["tease"] and "Cashed" in v["last"] and (v["n"] == 0 or v["day"] != c0["day"]), f"C next morning, all legs hit: teaser + Last ... Cashed | {v['next']} | {v['last']}")
        # D: next morning, one leg short
        ctx, pg, errs = await page_at(d0["end"] + 6 * 3600e3, "post", boxfor(c0["legs"], miss=1), gid)
        v = await pg.evaluate(vis); await ctx.close()
        check(v["tease"] and "Missed" in v["last"], f"D next morning, one leg missed: Last ... Missed | {v['last']}")
        # D2: during the game with a dead leg at the final whistle the card is still the day's card (never hidden)
        ctx, pg, errs = await page_at(c0["l"] + 3.5 * 3600e3, "post", boxfor(c0["legs"], miss=1), gid)
        v = await pg.evaluate(vis); await ctx.close()
        check(v["n"] == 1 and v["dead"] == 1 and v["st"].startswith("Busted"), f"D2 final whistle, a leg missed: the Sweep stays up as a miss {v['n'], v['dead'], v['st']}")
        await br.close()
    return fails

if __name__ == "__main__":
    f = asyncio.run(run()); print("sweep hero:", "all checks passed" if not f else f"{len(f)} FAILED"); sys.exit(1 if f else 0)
