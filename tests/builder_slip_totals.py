#!/usr/bin/env python3
"""builder_slip_totals.py - the Parlay Builder keeps a game total on the game it was picked for.

A total's key ("Over 40.5|Total|41") is shared by every game with that number (Week 10: the main total of GB-MIN, IND-MIA and ARI-LA,
and an alternate total of most other games). Before the 11/10 audit a reload, coming back to the tab or loading a saved slip swapped
the leg to the FIRST game with that number - another game at another price - and two games' same-number totals collapsed into one leg.
The slip now records the game per shared key in bs_slipg_w<W> ({key: [gid, ...]}); this test drives that end to end.

Run against a local copy of the site (the Step 6 clone or any checkout of main) built from the same out/builder_data.json:
    cd <site clone> && python3 -m http.server 8801 &
    python3 tests/builder_slip_totals.py
Needs playwright + chromium (already in the cloud sessions). Requests that are not to the local server are blocked.
Prints PASS / FAIL lines and "RESULT ALL PASS" or "RESULT FAILURES" (exit code 1).
"""
import asyncio, json, os, sys, collections
from playwright.async_api import async_playwright
BASE = 'http://127.0.0.1:8801'
D = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'out', 'builder_data.json')))
W = D['week']; KS, KG = f'bs_slipk_w{W}', f'bs_slipg_w{W}'
key = lambda l: f"{l['pl']}|{l['m']}|{int(l['ln'] + 0.5)}"
tot = [(i, l) for i, l in enumerate(D['legs']) if l['m'] == 'Total']
by = collections.defaultdict(dict)
for i, l in tot:
    if not l.get('alt'): by[key(l)].setdefault(l['g'], i)
shared = {k: v for k, v in by.items() if len(v) >= 2}
first = {}
for i, l in tot: first.setdefault(key(l), l['g'])
SLIP = "(function(){ return Array.from(document.querySelectorAll('#slipLegs > li')).filter(function(li){ return !li.classList.contains('empty') && /FD|model|TOTAL/i.test(li.innerText); }).map(function(li){ return li.innerText.replace(/\\s+/g,' ').slice(0, 70); }); })()"
def vs(g): a, b = g.split('-'); return f'{a} vs {b}'

async def main():
    ok = True
    def check(label, got, want):
        nonlocal ok
        good = len(got) == len(want) and all(any(w in g for g in got) for w in want)
        ok = ok and good; print(('PASS' if good else 'FAIL'), label, '|', got)
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={'width': 1280, 'height': 900}, service_workers='block')
        pg = await ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        await pg.route(lambda u: not u.startswith(BASE), lambda r: r.abort())
        await pg.goto(BASE + '/build/', wait_until='domcontentloaded'); await pg.wait_for_timeout(1800)
        await pg.evaluate("localStorage.clear()"); await pg.reload(wait_until='domcontentloaded'); await pg.wait_for_timeout(2200)
        if shared:
            # a main total two or more games share: pick it on a game that is NOT the first one with that key
            k, games = sorted(shared.items(), key=lambda kv: -len(kv[1]))[0]
            gs = [g for g in games if g != first[k]] or list(games)
            A = gs[0]; B = next((g for g in games if g not in (A, first[k])), None)
            print(f'week {W}: {k} is the main total of {sorted(games)}; first leg with that key is in {first[k]}; picking {A}' + (f' then {B}' if B else ''))
            await pg.evaluate(f"document.querySelector('button.glb[data-i=\"{games[A]}\"]').click()"); await pg.wait_for_timeout(300)
            check('picked', await pg.evaluate(SLIP), [vs(A)])
            await pg.evaluate("window.dispatchEvent(new Event('focus'))"); await pg.wait_for_timeout(300)
            await pg.evaluate("document.dispatchEvent(new Event('visibilitychange'))"); await pg.wait_for_timeout(200)
            check('after coming back to the tab', await pg.evaluate(SLIP), [vs(A)])
            await pg.reload(wait_until='domcontentloaded'); await pg.wait_for_timeout(2200)
            check('after a reload', await pg.evaluate(SLIP), [vs(A)])
            fd = await pg.evaluate("(document.getElementById('sendfd') || {}).href || ''")
            good = D['legs'][games[A]]['fd']['m'] in fd; ok = ok and good; print(('PASS' if good else 'FAIL'), 'FanDuel button carries that game\'s market |', fd[:100])
            want = [vs(A)]
            if B:
                await pg.evaluate(f"document.querySelector('button.glb[data-i=\"{games[B]}\"]').click()"); await pg.wait_for_timeout(300)
                want = [vs(A), vs(B)]
                check('two games, one number', await pg.evaluate(SLIP), want)
                await pg.reload(wait_until='domcontentloaded'); await pg.wait_for_timeout(2200)
                check('two games after a reload', await pg.evaluate(SLIP), want)
            await pg.evaluate("document.querySelector('#savesl').click()"); await pg.wait_for_timeout(200)
            await pg.evaluate("document.querySelector('.namebox .pri').click()"); await pg.wait_for_timeout(300)
            sv = json.loads(await pg.evaluate(f"localStorage.getItem('bs_slips_w{W}')") or '[]')
            good = bool(sv) and all(D['legs'][games[g]]['fd']['m'] in (sv[0].get('fd') or '') for g in ([A, B] if B else [A])); ok = ok and good
            print(('PASS' if good else 'FAIL'), 'saved slip carries the right markets | g =', (sv[0].get('g') if sv else None))
            await pg.evaluate(f"localStorage.setItem('{KS}', '[]'); localStorage.removeItem('{KG}'); window.dispatchEvent(new Event('focus'))"); await pg.wait_for_timeout(300)
            check('cleared', await pg.evaluate(SLIP), [])
            await pg.evaluate("document.querySelector('#savedList button[data-load]').click()"); await pg.wait_for_timeout(400)
            check('saved slip loaded back', await pg.evaluate(SLIP), want)
        else:
            print(f'week {W}: no main total is shared by two games this week - checking the stored-key path with an alternate total')
        # stored key + game on record (what another device or the boards page leaves behind): any total key that two games use
        allk = collections.defaultdict(dict)
        for i, l in tot: allk[key(l)].setdefault(l['g'], i)
        k2, g2 = next(((k, v) for k, v in allk.items() if len(v) >= 2), (None, None))
        if k2:
            other = [g for g in g2 if g != first[k2]][0]
            await pg.evaluate(f"localStorage.setItem('{KS}', JSON.stringify([{json.dumps(k2)}])); localStorage.setItem('{KG}', JSON.stringify({{{json.dumps(k2)}: [{json.dumps(other)}]}})); window.dispatchEvent(new Event('focus'))"); await pg.wait_for_timeout(300)
            check(f'stored key with {other} on record', await pg.evaluate(SLIP), [vs(other)])
            await pg.evaluate(f"localStorage.removeItem('{KG}'); localStorage.setItem('{KS}', JSON.stringify([{json.dumps(k2)}])); window.dispatchEvent(new Event('focus'))"); await pg.wait_for_timeout(200)
            await pg.reload(wait_until='domcontentloaded'); await pg.wait_for_timeout(2200)
            check('stored key with no game on record resolves as before (first leg with that number)', await pg.evaluate(SLIP), [vs(first[k2])])
        print('RESULT', 'ALL PASS' if ok and not errs else 'FAILURES', '| js errors', errs)
        await b.close()
    sys.exit(0 if ok and not errs else 1)
asyncio.run(main())
