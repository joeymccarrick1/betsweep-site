#!/usr/bin/env python3
"""tests/survivor_plan.py - the Survivor planner (/survivor/) picks the provably best road (owner 11/10).

Needs a built site served locally (BASE, default http://localhost:8802). For three sets of used teams it reads the road the page shows
and checks its product of win chances against an exact search done here (dynamic programme over teams x week-sets), then checks the
basics: a used team is never offered, pools keep separate lists, the list survives a reload, kicked-off games drop out of this week and
the plan moves on to next week once the week is over, and the page fits a phone.
"""
import asyncio, json, math, os, re, sys
from playwright.async_api import async_playwright
BASE = os.environ.get("BASE", "http://localhost:8802")
SHOTS = os.environ.get("SHOTS")

def exact(D, used, frm, to, now_ms):
    """best total log win chance over weeks frm..to, one team per week, no team twice; None if a week has no team"""
    weeks = list(range(frm, to + 1)); P = {}
    for w in weeks:
        m = P[w] = {}
        for g in D["weeks"].get(str(w), []):
            if w == frm and (g["fin"] or (g["ko"] and g["ko"] <= now_ms)): continue
            m[g["h"]] = g["p"]; m[g["a"]] = 1 - g["p"]
    teams = [t for t in D["teams"] if t not in used]; full = (1 << len(weeks)) - 1
    dp = {0: 0.0}
    for t in teams:
        nd = dict(dp)
        for mask, v in dp.items():
            for i, w in enumerate(weeks):
                if mask >> i & 1 or t not in P[w] or P[w][t] <= 0: continue
                nv = v + math.log(P[w][t]); k = mask | 1 << i
                if nv > nd.get(k, -1e18): nd[k] = nv
        dp = nd
    return dp.get(full)

async def run():
    fails = []
    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok: fails.append(what)
    async with async_playwright() as p:
        br = await p.chromium.launch()
        async def open_page(ms=None, state=None, w=390):
            ctx = await br.new_context(viewport={"width": w, "height": 844}); pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            if ms: await pg.clock.install(time=ms / 1000)
            async def route(r):
                if r.request.url.startswith(BASE): await r.continue_()
                else: await r.abort()
            await pg.route("**/*", route)
            if state is not None: await ctx.add_init_script("try{ if(!sessionStorage.getItem('_sv')){ localStorage.setItem('bs_survivor', %s); sessionStorage.setItem('_sv','1'); } }catch(e){}" % json.dumps(json.dumps(state)))
            await pg.goto(BASE + "/survivor/", wait_until="load"); await pg.wait_for_timeout(500)
            return ctx, pg, errs
        road_js = """()=>{ const tb=[...document.querySelectorAll('.sv table')]; const road=tb[tb.length-2]; const opt=tb[0];
            const rows=[...road.querySelectorAll('tbody tr')].map(tr=>({w:+tr.children[0].textContent, t:(tr.querySelector('b.t')||{}).textContent||null}));
            return {D: window.__SV, call: (document.querySelector('.sv .call b.pick')||{}).textContent, road: rows, opts: [...opt.querySelectorAll('tbody tr')].map(tr=>tr.dataset.pick), heads: [...document.querySelectorAll('.sv h2')].map(h=>h.textContent),
                    sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, used: document.getElementById('svused').textContent} }"""
        ctx, pg, errs = await open_page()
        v = await pg.evaluate(road_js); D = v["D"]; now = await pg.evaluate("Date.now()")
        check(not errs, f"page loads without script errors {errs[:2]}")
        check(v["sw"] <= v["cw"], f"fits a phone ({v['sw']} vs {v['cw']})")
        frm = v["road"][0]["w"]; to = v["road"][-1]["w"]
        def lp_of(road, used):
            s = 0.0; seen = set(used)
            for r in road:
                g = [g for g in D["weeks"][str(r["w"])] if r["t"] in (g["h"], g["a"])]
                if not g or r["t"] in seen: return None
                seen.add(r["t"]); s += math.log(g[0]["p"] if g[0]["h"] == r["t"] else 1 - g[0]["p"])
            return s
        got = lp_of(v["road"], []); want = exact(D, set(), frm, to, now)
        check(got is not None and want is not None and abs(got - want) < 1e-6, f"no teams used: the road shown is the best possible ({math.exp(got or 0)*100:.2f}% vs exact {math.exp(want or 0)*100:.2f}%), weeks {frm}-{to}")
        if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, "survivor.png"), full_page=True)
        # mark the five best-rated teams as used, through the page
        top5 = list(D["rate"].keys())[:5]
        for t in top5: await pg.click(f'#svteams button[data-t="{t}"]')
        await pg.wait_for_timeout(200); v2 = await pg.evaluate(road_js)
        got = lp_of(v2["road"], top5); want = exact(D, set(top5), frm, to, now)
        check(got is not None and abs(got - want) < 1e-6, f"five best teams used: still the best road ({math.exp(got or 0)*100:.2f}% vs exact {math.exp(want)*100:.2f}%)")
        check(not (set(top5) & set(v2["opts"])) and not (set(top5) & {r["t"] for r in v2["road"]}), "used teams are never offered")
        # tap another option: the road starts with it
        alt = v2["opts"][3]; await pg.click(f'.sv tr.opt[data-pick="{alt}"]'); await pg.wait_for_timeout(150); v3 = await pg.evaluate(road_js)
        check(v3["road"][0]["t"] == alt and lp_of(v3["road"], top5) is not None, f"tapping {alt} shows the road that starts with it")
        got3 = lp_of(v3["road"], top5); want3 = math.log([ (g["p"] if g["h"]==alt else 1-g["p"]) for g in D["weeks"][str(frm)] if alt in (g["h"], g["a"])][0]) + exact(D, set(top5) | {alt}, frm + 1, to, now)
        check(abs(got3 - want3) < 1e-6, "and the rest of that road is the best one left")
        # reload: the list is still there
        await pg.reload(wait_until="load"); await pg.wait_for_timeout(400); v4 = await pg.evaluate(road_js)
        check(all(t in v4["used"] for t in top5), "the used teams survive a reload")
        await ctx.close()
        # two pools keep separate lists
        st = {"cur": 1, "pools": [{"name": "Office", "used": top5, "to": D["last"]}, {"name": "Family", "used": [], "to": D["week"] + 3}]}
        ctx, pg, errs = await open_page(state=st); v5 = await pg.evaluate(road_js)
        check("None marked" in v5["used"] and v5["road"][-1]["w"] == D["week"] + 3, f"second pool: its own (empty) list and its own last week ({v5['road'][-1]['w']})")
        await pg.click('#svpools button[data-i="0"]'); await pg.wait_for_timeout(150); v6 = await pg.evaluate(road_js)
        check(all(t in v6["used"] for t in top5), "first pool still has its five"); await ctx.close()
        # the clock: after the Thursday game has kicked off its two teams are gone from this week; after the week is over the plan starts next week
        g0 = D["weeks"][str(D["week"])][0]; lastko = max(g["ko"] for g in D["weeks"][str(D["week"])])
        ctx, pg, errs = await open_page(ms=g0["ko"] + 60e3); v7 = await pg.evaluate(road_js); await ctx.close()
        check(g0["h"] not in v7["opts"] and g0["a"] not in v7["opts"] and v7["road"][0]["w"] == D["week"], f"after {g0['a']}-{g0['h']} kicks off neither is offered this week")
        ctx, pg, errs = await open_page(ms=lastko + 3600e3); v8 = await pg.evaluate(road_js); await ctx.close()
        check(v8["road"][0]["w"] == D["week"] + 1, f"once every game of the week has kicked off the plan starts at Week {D['week'] + 1}")
        # desktop width
        ctx, pg, errs = await open_page(w=1280); v9 = await pg.evaluate(road_js); await ctx.close()
        check(v9["sw"] <= v9["cw"] and not errs, "desktop: no sideways scroll, no errors")
        await br.close()
    return fails

if __name__ == "__main__":
    f = asyncio.run(run()); print("survivor planner:", "all checks passed" if not f else f"{len(f)} FAILED"); sys.exit(1 if f else 0)
