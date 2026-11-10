#!/usr/bin/env python3
"""site_clicks.py /path/ [/path/ ...] - on each page: type into every text box, then click every button, toggle and select it can find
(up to 12 per kind, 7 rounds), and record any JS error with the control that caused it. Found on 11/10: Parlay Builder Save slip
(byKey not defined), Social Sharps tab, the Trade page's click handler. Writes /tmp/site_clicks.json and prints one line per page.

Run against a local copy of the site (the Step 6 clone or any checkout of main):
    cd <site clone> && python3 -m http.server 8801 &
    python3 tests/site_clicks.py [args]
Needs playwright + chromium (already in the cloud sessions). Every request that is not to the local server is blocked, so nothing
here touches Supabase, ESPN or FanDuel. Written in the 11/10 site audit; see RUNBOOK "Site checks".
"""
import asyncio, json, os, re, sys
from playwright.async_api import async_playwright
BASE = os.environ.get('BASE', 'http://127.0.0.1:8801')
pages = sys.argv[1:] or ['/build/', '/boards/', '/live/', '/team/', '/dfs/', '/trade/', '/firsttd/', '/teasers/', '/beat/', '/', '/me/', '/player/aaron-jones/', '/player/', '/usage/', '/benefits/', '/season/', '/receipts/week9/', '/social/', '/team/compare/', '/lab/merged/', '/teams/buf/', '/dossier/ARI-LA/', '/b/']
COLLECT = """(seen) => { const sig = e => e.tagName + '|' + (typeof e.className === 'string' ? e.className : '') + '|' + (e.id||'') + '|' + (e.innerText||'').trim().slice(0, 20) + '|' + (e.getAttribute('data-k')||e.getAttribute('data-g')||e.getAttribute('data-id')||'').slice(0,20);
  const els = Array.from(document.querySelectorAll('button, summary, [role=button], input[type=checkbox], input[type=radio], select, [data-k].add, .chip[data-f]')).filter(e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && !e.disabled; });
  const cls = {}; const out = [];
  for (const e of els) { const s = sig(e); if (seen.indexOf(s) >= 0) continue; const c = e.tagName + '|' + (typeof e.className === 'string' ? e.className : ''); cls[c] = (cls[c]||0) + 1; if (cls[c] > 12) continue; out.push(e); if (out.length >= 80) break; }
  window.__els = out; return out.map(sig); }"""
async def one(b, path, out, sem):
    async with sem:
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, service_workers='block', is_mobile=True, has_touch=True)
        pg = await ctx.new_page(); rec = {'path': path, 'errors': [], 'dialogs': [], 'clicked': 0, 'typed': 0, 'overflow': []}
        cur = {'label': 'load'}
        pg.on('pageerror', lambda e: rec['errors'].append((cur['label'], str(e)[:260])))
        async def on_dialog(d):
            rec['dialogs'].append((cur['label'], d.type, d.message[:80])); await d.dismiss()
        pg.on('dialog', lambda d: asyncio.ensure_future(on_dialog(d)))
        await pg.route(lambda u: not u.startswith(BASE), lambda r: r.abort())
        await pg.add_init_script("window.open = function(){ return null; }; try{ Object.defineProperty(navigator,'share',{value:undefined}); }catch(e){}")
        try:
            await pg.goto(BASE + path, wait_until='domcontentloaded', timeout=30000); await pg.wait_for_timeout(2200)
            # type into text/search inputs
            ins = await pg.evaluate("""() => { const a = Array.from(document.querySelectorAll('input[type=text],input[type=search],input:not([type])')).filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && !e.disabled; }); window.__ins = a.slice(0, 6); return window.__ins.length; }""")
            for i in range(ins):
                cur['label'] = f'type input {i}'
                try:
                    await pg.evaluate("(i) => { const e = window.__ins[i]; e.focus(); e.value = 'jef'; e.dispatchEvent(new Event('input', {bubbles: true})); e.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true, key: 'f'})); }", i)
                    rec['typed'] += 1; await pg.wait_for_timeout(250)
                    await pg.evaluate("(i) => { const e = window.__ins[i]; e.value = ''; e.dispatchEvent(new Event('input', {bubbles: true})); }", i)
                except Exception as e: rec['errors'].append((cur['label'], 'TYPE: ' + str(e)[:120]))
            seen = []
            for rnd in range(7):
                sigs = await pg.evaluate(COLLECT, seen)
                if not sigs: break
                for i, s in enumerate(sigs):
                    seen.append(s); cur['label'] = s[:70]
                    try:
                        await pg.evaluate("(i) => { const e = window.__els[i]; if (!e || !e.isConnected) return; if (e.tagName === 'SELECT') { if (e.options.length > 1) { e.selectedIndex = (e.selectedIndex + 1) % e.options.length; e.dispatchEvent(new Event('change', {bubbles: true})); } } else e.click(); }", i)
                        rec['clicked'] += 1; await pg.wait_for_timeout(90)
                        if not pg.url.startswith(BASE + path.split('?')[0]):
                            await pg.goto(BASE + path, wait_until='domcontentloaded'); await pg.wait_for_timeout(1500); break
                    except Exception as e: rec['errors'].append((cur['label'], 'CLICK: ' + str(e)[:160]))
                sw = await pg.evaluate('document.documentElement.scrollWidth')
                if sw > 392: rec['overflow'].append((rnd, sw))
            rec['flags'] = await pg.evaluate(r"""() => { const t = document.body.innerText; const f = []; const re = /\bundefined\b|\bNaN\b|\[object Object\]|\bnull\b|\bInfinity\b/g; let m; while ((m = re.exec(t)) && f.length < 5) f.push(t.slice(Math.max(0, m.index - 50), m.index + 30).replace(/\s+/g, ' ')); return f; }""")
        except Exception as e: rec['errors'].append(('load', str(e)[:200]))
        await ctx.close(); out.append(rec)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); out = []; sem = asyncio.Semaphore(5)
        await asyncio.gather(*[one(b, pth, out, sem) for pth in pages]); await b.close()
    json.dump(out, open('/tmp/site_clicks.json', 'w'))
    for r in out: print(r['path'], 'clicked', r['clicked'], 'typed', r['typed'], '| errors', r['errors'][:3], '| flags', r.get('flags', ['PAGE DID NOT LOAD'])[:2])
asyncio.run(main())
