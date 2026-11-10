#!/usr/bin/env python3
"""tests/slip_verdict.py - "Sweep my slip": the verdict in the Parlay Builder and the screenshot front door at /sweep/ (owner 11/10).

Needs a built site served locally (BASE, default http://localhost:8802) and out/builder_data.json from the same build (DATA).
The picture reader is not exercised here (it needs the tesseract download) - /sweep/ is driven with a stand-in for BSImport.read that
returns what the reader returns. Checks: a clean slip reads clean and its numbers match the price panel; a slip with a risky leg names
it and the one-tap swap really swaps it; Drop removes it; a slip arriving from /sweep/ carries its printed price and names the legs
that are not on the board; nothing throws; a phone screen does not scroll sideways.
"""
import asyncio, json, os, re, sys
from playwright.async_api import async_playwright
BASE = os.environ.get("BASE", "http://localhost:8802")
DATA = os.environ.get("DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "builder_data.json"))
SHOTS = os.environ.get("SHOTS")
D = json.load(open(DATA)); W = D["week"]; PF = D.get("pf") or {}
def risk(l):
    w = {"bad": 3, "watch": 1, "good": -1}
    return max(0, sum(w.get(f[0], 0) for f in (l.get("fh") or [])) + sum(w.get(f[0], 0) for f in (PF.get(l["pl"]) or [])))
def key(l): return f'{l["pl"]}|{l["m"]}|{round(l["ln"] or 1)}'
props = [l for l in D["legs"] if not l.get("gl") and l.get("o") is not None and not l["m"].startswith("Under") and l["m"] in ("Receiving Yards", "Receptions", "Passing Yards", "Rushing Yards", "Rush + Rec Yards")]
by = {}
for l in props: by.setdefault((l["pl"], l["m"]), []).append(l)
for k in by: by[k].sort(key=lambda l: l["ln"])
clean = []; seen = set()
for l in sorted(props, key=lambda l: -l["p"]):
    if l["pl"] in seen or risk(l) >= 2 or not -400 <= l["o"] <= -150: continue
    seen.add(l["pl"]); clean.append(l)
    if len(clean) == 4: break
# a risky leg whose ladder has a safer, low-risk rung
riskyleg = None
for (pl, m), g in by.items():
    if pl in seen: continue
    for i, l in enumerate(g):
        if i > 0 and risk(l) >= 4 and any(risk(x) < 2 and x["p"] > l["p"] for x in g[:i]): riskyleg = l; break
    if riskyleg: break

async def run():
    fails = []
    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok: fails.append(what)
    check(len(clean) == 4, f"test data: four low-risk favorites on the board ({[l['pl'] for l in clean]})")
    check(riskyleg is not None, f"test data: a high-risk leg with a safer low-risk rung ({riskyleg and (riskyleg['pl'], riskyleg['m'], riskyleg['ln'])})")
    async with async_playwright() as p:
        br = await p.chromium.launch()
        async def ctx_page(keys=None, w=390, init=None, sweep=None):
            ctx = await br.new_context(viewport={"width": w, "height": 844}); pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            async def route(r):
                if r.request.url.startswith(BASE): await r.continue_()
                else: await r.abort()
            await pg.route("**/*", route)
            js = ""
            if keys is not None: js += "if(!sessionStorage.getItem('_t')){ localStorage.setItem('bs_slipk_w%d', %s); sessionStorage.setItem('_t','1'); }" % (W, json.dumps(json.dumps(keys)))
            if sweep is not None: js += "if(!sessionStorage.getItem('_t2')){ sessionStorage.setItem('bs_sweep', %s); sessionStorage.setItem('_t2','1'); }" % json.dumps(json.dumps(sweep))
            if init: js += init
            if js: await ctx.add_init_script("try{ %s }catch(e){}" % js)
            return ctx, pg, errs
        V = """()=>{ const b=document.getElementById('sweepv'); const legs=[...document.querySelectorAll('#slipLegs > li')].filter(li=>!li.classList.contains('empty')).length;
            const price=[...document.querySelectorAll('#price > div')].map(d=>d.textContent.replace(/\\s+/g,' '));
            return {on: b && !b.hidden, head: b && (b.querySelector('.vh b')||{}).textContent, txt: b ? b.textContent.replace(/\\s+/g,' ') : '', legs: legs, price: price,
                    swap: !!(b && b.querySelector('[data-swk]')), drop: !!(b && b.querySelector('[data-swdrop]')), btn: (document.getElementById('sweepbtn')||{}).textContent,
                    sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth} }"""
        # 1. a clean slip, verdict off until asked for
        ctx, pg, errs = await ctx_page([key(l) for l in clean])
        await pg.goto(BASE + "/build/#slip", wait_until="load"); await pg.wait_for_timeout(1500)
        v = await pg.evaluate(V)
        check(v["legs"] == 4 and not v["on"] and v["btn"] == "Sweep this slip", f"four legs load, the verdict stays hidden until asked ({v['legs']}, {v['on']}, {v['btn']})")
        await pg.evaluate("document.getElementById('sweepbtn').click()"); await pg.wait_for_timeout(300); v = await pg.evaluate(V)
        check(v["on"] and v["head"] in ("Clean slip", "One weak spot"), f"four low-risk favorites: '{v['head']}'")
        m = re.search(r"Chance to cash: (\d+)%\. At ([+-]\d+) it has to hit (\d+)%", v["txt"]); fd = next((x for x in v["price"] if "FanDuel price" in x), ""); fair = next((x for x in v["price"] if "Model fair" in x), "")
        check(bool(m) and m.group(2) in fd and (m.group(1) + "% to hit") in fair, f"its numbers are the price panel's ({m and m.groups()} | {fd[:40]} | {fair[:40]})")
        check("4 of 4 legs are low risk" in v["txt"], "says 4 of 4 legs are low risk")
        check(v["sw"] <= v["cw"] and not errs, f"phone width holds, no script errors ({v['sw']}/{v['cw']}, {errs[:2]})")
        if SHOTS:
            el = await pg.query_selector("#sweepv"); await el.scroll_into_view_if_needed(); await el.screenshot(path=os.path.join(SHOTS, "verdict_clean.png"))
        await pg.evaluate("document.getElementById('sweepbtn').click()"); await pg.wait_for_timeout(200); v = await pg.evaluate(V)
        check(not v["on"], "the button hides it again"); await ctx.close()
        # 2. three clean legs + the risky one, arriving with ?sweep=1
        if riskyleg:
            ks = [key(l) for l in clean[:3]] + [key(riskyleg)]
            ctx, pg, errs = await ctx_page(ks)
            await pg.goto(BASE + "/build/?sweep=1#slip", wait_until="load"); await pg.wait_for_timeout(1500); v = await pg.evaluate(V)
            check(v["on"] and v["head"] in ("One weak spot", "Risky slip") and riskyleg["pl"] in v["txt"] and "Weakest leg" in v["txt"], f"?sweep=1 opens the verdict and names the risky leg: '{v['head']}'")
            check(v["swap"] and v["drop"], "offers a swap and a drop")
            if SHOTS:
                el = await pg.query_selector("#sweepv"); await el.scroll_into_view_if_needed(); await el.screenshot(path=os.path.join(SHOTS, "verdict_risky.png"))
            before = await pg.evaluate("localStorage.getItem('bs_slipk_w%d')" % W)
            await pg.evaluate("document.querySelector('#sweepv [data-swk]').click()"); await pg.wait_for_timeout(400); v2 = await pg.evaluate(V)
            after = json.loads(await pg.evaluate("localStorage.getItem('bs_slipk_w%d')" % W))
            swapped = [k for k in after if k.startswith(riskyleg["pl"] + "|" + riskyleg["m"] + "|")]
            check(v2["legs"] == 4 and len(swapped) == 1 and swapped[0] != key(riskyleg) and int(swapped[0].split("|")[-1]) < round(riskyleg["ln"]), f"the swap puts a safer line in the slip ({key(riskyleg)} -> {swapped})")
            check(v2["head"] in ("Clean slip", "One weak spot") and not errs, f"and the verdict improves: '{v2['head']}' {errs[:2]}")
            await ctx.close()
            ctx, pg, errs = await ctx_page(ks)
            await pg.goto(BASE + "/build/?sweep=1#slip", wait_until="load"); await pg.wait_for_timeout(1500)
            await pg.evaluate("document.querySelector('#sweepv [data-swdrop]').click()"); await pg.wait_for_timeout(400); v3 = await pg.evaluate(V)
            check(v3["legs"] == 3 and riskyleg["pl"] not in " ".join(json.loads(await pg.evaluate("localStorage.getItem('bs_slipk_w%d')" % W))), "Drop removes the leg"); await ctx.close()
        # 3. the front door: /sweep/ with a stand-in reader
        fake = {"R": {"legs": [{"ok": True, "key": key(l), "label": l["pl"]} for l in clean] + [{"ok": False, "raw": "Some Player 1st Drive Result", "why": "a market we do not price"}], "odds": 345, "stake": 10}, "BS": {"week": W}}
        init = "window.addEventListener('DOMContentLoaded', function(){ var t = setInterval(function(){ if(window.BSImport){ clearInterval(t); window.BSImport.read = function(){ return Promise.resolve(%s); }; } }, 20); });" % json.dumps(fake)
        ctx, pg, errs = await ctx_page(keys=[], init=init)
        await pg.goto(BASE + "/sweep/", wait_until="load"); await pg.wait_for_timeout(600)
        h1 = await pg.evaluate("document.querySelector('.sc h1').textContent"); ov = await pg.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        check(h1 == "Sweep my slip" and ov[0] <= ov[1], "the /sweep/ page loads and fits a phone")
        if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, "sweep_page.png"), full_page=True)
        await pg.set_input_files("#scfile", files=[{"name": "slip.png", "mimeType": "image/png", "buffer": b"\x89PNG\r\n\x1a\n"}])
        try: await pg.wait_for_url("**/build/?sweep=1*", timeout=8000)
        except Exception as e: check(False, f"/sweep/ hands the slip to the builder ({str(e)[:80]})")
        await pg.wait_for_timeout(1500); v = await pg.evaluate(V)
        check(v["on"] and v["legs"] == 4, f"/sweep/ hands the slip to the builder with the verdict open ({v['legs']} legs)")
        check("+345 (the price on your slip)" in v["txt"], "the verdict uses the price printed on the slip")
        check("Not on our board" in v["txt"] and "1st Drive" in v["txt"], "and names the leg it could not price")
        check(not errs, f"no script errors on the way {errs[:2]}"); await ctx.close()
        # 4. desktop
        ctx, pg, errs = await ctx_page([key(l) for l in clean], w=1280)
        await pg.goto(BASE + "/build/?sweep=1", wait_until="load"); await pg.wait_for_timeout(1500); v = await pg.evaluate(V)
        check(v["on"] and v["sw"] <= v["cw"] and not errs, "desktop: verdict shows, no sideways scroll, no errors"); await ctx.close()
        await br.close()
    return fails

if __name__ == "__main__":
    f = asyncio.run(run()); print("sweep my slip:", "all checks passed" if not f else f"{len(f)} FAILED"); sys.exit(1 if f else 0)
