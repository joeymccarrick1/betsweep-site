#!/usr/bin/env python3
"""site_summary.py [results.json] - print what site_crawl.py found: JS errors, bad responses, broken images, overflow, text flags,
and local links with no file behind them (app deep links such as hardrock:// are not pages - ignore those).

Run against a local copy of the site (the Step 6 clone or any checkout of main):
    cd <site clone> && python3 -m http.server 8801 &
    python3 tests/site_summary.py [args]
Needs playwright + chromium (already in the cloud sessions). Every request that is not to the local server is blocked, so nothing
here touches Supabase, ESPN or FanDuel. Written in the 11/10 site audit; see RUNBOOK "Site checks".
"""
import json, os, sys, re, urllib.parse
ROOT=os.environ.get('SITE', '/home/claude/betsweep-site')
f = sys.argv[1] if len(sys.argv) > 1 else '/tmp/site_crawl.json'
d = json.load(open(f)); print('pages', len(d))
def exists(href, base):
    h = href.split('#')[0].split('?')[0]
    if not h: return True
    p = urllib.parse.urljoin(base, h); p = urllib.parse.unquote(p)
    fp = ROOT + p
    return os.path.isfile(fp) or os.path.isfile(os.path.join(fp, 'index.html')) or (os.path.isdir(fp) and os.path.isfile(fp.rstrip('/') + '/index.html'))
errs = bad = imgs = wide = flags = 0; broken = {}
for r in sorted(d, key=lambda r: r['path']):
    if r.get('errors'): errs += 1; print('JS ERROR', r['path'], r['errors'][:2])
    if r.get('console'): print('console', r['path'], r['console'][:2])
    b = [x for x in r.get('bad', [])]
    if b: bad += 1; print('BAD RESP', r['path'], b[:4])
    if r.get('imgs'): imgs += 1; print('BROKEN IMG', r['path'], r['imgs'][:4])
    if r.get('sw', 0) > r.get('iw', 9999) + 2: wide += 1; print('OVERFLOW', r['path'], r['sw'], r.get('wide', [])[:2])
    if r.get('flags'): flags += 1; print('FLAG', r['path'], r['flags'][:2])
    for h in r.get('links', []):
        if not exists(h, r['path']): broken.setdefault(h, []).append(r['path'])
for h, ps in sorted(broken.items()): print('BROKEN LINK', h, 'on', len(ps), 'pages e.g.', ps[:3])
print(f'summary: js-error pages {errs}, bad-response pages {bad}, broken-img pages {imgs}, overflow pages {wide}, flag pages {flags}, broken links {len(broken)}')
