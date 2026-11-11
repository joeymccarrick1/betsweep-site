#!/usr/bin/env python3
"""gate.py [results.json] - turn a site_crawl.py run into a yes / no for an unattended publish (reprice.py, owner 11/10).

Fails (exit 1) when any crawled page threw a JS error, asked for a local file that is not there, shows a broken image, or prints
'undefined' / 'NaN' / '[object Object]' in its text.  Sideways overflow and link checks are left to site_summary.py: they are worth
a look, not worth holding prices back for.  Prints one line per problem and a one-line verdict.
"""
import json, sys
d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/site_crawl.json")); bad = []
for r in sorted(d, key=lambda r: r["path"]):
    if r.get("errors"): bad.append(f"JS ERROR {r['path']} {r['errors'][:2]}")
    if r.get("bad"): bad.append(f"MISSING FILE {r['path']} {r['bad'][:3]}")
    if r.get("imgs"): bad.append(f"BROKEN IMAGE {r['path']} {r['imgs'][:3]}")
    if r.get("flags"): bad.append(f"TEXT {r['path']} {r['flags'][:2]}")
for b in bad: print(b)
print(f"gate: {len(d)} pages, {len(bad)} problems -> {'HOLD' if bad or not d else 'ok to publish'}")
sys.exit(1 if bad or not d else 0)
