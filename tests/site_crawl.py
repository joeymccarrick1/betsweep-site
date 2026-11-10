#!/usr/bin/env python3
"""site_crawl.py [regex] - load every page of the site on a phone-sized screen and record JS errors, failed local requests, broken images,
sideways overflow, 'undefined'/'NaN' in the text, local links, title / description / canonical / h1. Writes /tmp/site_crawl.json;
site_summary.py prints the problems (and checks that every local link has a file).

Run against a local copy of the site (the Step 6 clone or any checkout of main):
    cd <site clone> && python3 -m http.server 8801 &
    python3 tests/site_crawl.py [args]
Needs playwright + chromium (already in the cloud sessions). Every request that is not to the local server is blocked, so nothing
here touches Supabase, ESPN or FanDuel. Written in the 11/10 site audit; see RUNBOOK "Site checks".
"""
import asyncio, json, os, re, sys, glob
from playwright.async_api import async_playwright
ROOT = os.environ.get('SITE', '/home/claude/betsweep-site'); PORT = 8801; BASE = os.environ.get('BASE', f'http://127.0.0.1:{PORT}')
pages = []
for f in sorted(glob.glob(ROOT + '/**/index.html', recursive=True)):
    rel = os.path.relpath(os.path.dirname(f), ROOT); pages.append('/' if rel == '.' else '/' + rel + '/')
pages += ['/404.html', '/offline.html']
only = sys.argv[1] if len(sys.argv) > 1 else None
if only: pages = [p for p in pages if re.search(only, p)]
JS = r"""() => {
  const de = document.documentElement, t = (document.body && document.body.innerText) || '';
  const flags = []; const re = /\bundefined\b|\bNaN\b|\[object Object\]|\bnull\b|\bInfinity\b/g; let m;
  while ((m = re.exec(t)) && flags.length < 6) flags.push(t.slice(Math.max(0, m.index - 50), m.index + 30).replace(/\s+/g, ' '));
  const links = Array.from(document.querySelectorAll('a[href]')).map(a => a.getAttribute('href')).filter(h => h && !/^(https?:|mailto:|sms:|tel:|#|javascript:|data:)/.test(h));
  const ext = Array.from(document.querySelectorAll('a[href^="http"]')).map(a => a.href);
  const imgs = Array.from(document.images).filter(i => i.src.startsWith(location.origin) && i.complete && i.naturalWidth === 0).map(i => i.getAttribute('src'));
  const wide = []; if (de.scrollWidth > window.innerWidth + 2) { document.querySelectorAll('body *').forEach(e => { const r = e.getBoundingClientRect(); if (r.width > 0 && r.right > window.innerWidth + 2 && wide.length < 5 && getComputedStyle(e).position !== 'fixed') { let p = e.parentElement, clipped = false; while (p && p !== document.body) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden') { clipped = true; break; } p = p.parentElement; } if (!clipped) wide.push((e.tagName + '.' + (e.className && e.className.baseVal === undefined ? e.className : '')).slice(0, 60) + ' r=' + Math.round(r.right)); } }); }
  const meta = n => { const e = document.querySelector('meta[name="' + n + '"],meta[property="' + n + '"]'); return e ? e.getAttribute('content') : null; };
  const can = document.querySelector('link[rel=canonical]');
  const weeks = Array.from(new Set((t.match(/\bWeek \d{1,2}\b/gi) || []).map(s => s.toLowerCase())));
  const small = []; document.querySelectorAll('body *').forEach(e => { if (small.length >= 3 || !e.childNodes.length) return; const hasText = Array.from(e.childNodes).some(n => n.nodeType === 3 && n.textContent.trim().length > 3); if (!hasText) return; const fs = parseFloat(getComputedStyle(e).fontSize); const r = e.getBoundingClientRect(); if (fs && fs < 10 && r.width > 0 && r.height > 0) small.push(e.tagName + ':' + fs + ':' + e.textContent.trim().slice(0, 30)); });
  return { title: document.title, desc: meta('description'), og: meta('og:image'), ogt: meta('og:title'), vp: meta('viewport'), lang: de.getAttribute('lang'), canon: can ? can.getAttribute('href') : null,
    h1: Array.from(document.querySelectorAll('h1')).map(h => h.innerText.trim().slice(0, 80)), sw: de.scrollWidth, iw: window.innerWidth, wide, flags, links: Array.from(new Set(links)), ext: Array.from(new Set(ext)), imgs, weeks, len: t.length, small,
    robots: meta('robots') };
}"""
async def one(ctx, path, out, sem):
    async with sem:
        pg = await ctx.new_page(); rec = {'path': path, 'errors': [], 'console': [], 'bad': []}
        pg.on('pageerror', lambda e: rec['errors'].append(str(e)[:300]))
        pg.on('console', lambda m: rec['console'].append(m.text[:300]) if m.type == 'error' and 'net::ERR_FAILED' not in m.text and 'ERR_BLOCKED' not in m.text else None)
        def on_resp(r):
            if r.url.startswith(BASE) and r.status >= 400: rec['bad'].append(f'{r.status} {r.url[len(BASE):][:160]}')
        pg.on('response', on_resp)
        await pg.route(lambda u: not u.startswith(BASE), lambda r: r.abort())
        try:
            resp = await pg.goto(BASE + path, wait_until='domcontentloaded', timeout=30000); rec['status'] = resp.status if resp else None
            await pg.wait_for_timeout(1800)
            rec.update(await pg.evaluate(JS))
        except Exception as e: rec['errors'].append('NAV: ' + str(e)[:200])
        await pg.close(); out.append(rec)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 390, 'height': 844}, service_workers='block', is_mobile=True, has_touch=True,
                                  user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1')
        out = []; sem = asyncio.Semaphore(6)
        await asyncio.gather(*[one(ctx, pth, out, sem) for pth in pages])
        await b.close()
    json.dump(out, open('/tmp/site_crawl.json', 'w'))
    print('pages', len(out))
asyncio.run(main())
