"""Slip-building checks used in chat (not part of the site build). Run from anywhere after a local build:
    python3 reprice.py --mirror ../sm/in --clone ~/betsweep-site --publish none     # fresh out/builder_data.json
    python3 research/slipcheck/statcheck.py [-199 -130]     # the matchup rule on every low-risk leg in a price range
    python3 research/slipcheck/tdcheck.py                   # the same four checks for anytime-TD legs
"The matchup rule" (owner 11/21): every leg must pass matchup and game script; a wide receiver needs a favorable or neutral corner on
the chart; and the player's record against similar defenses should clear the price. MIRROR=<sheet-mirror>/in overrides ../sm/in.
"""
import os as _os, sys as _sys
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
MIRROR = _os.environ.get("MIRROR") or _os.path.join(_os.path.dirname(ROOT), "sm", "in")
_sys.path.insert(0, ROOT); _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import json, sys, itertools, math
import sweep as SW, pairs as PR, sgp as SGP
import numpy as np
from statistics import NormalDist
bd = json.load(open(_os.path.join(ROOT, 'out', 'builder_data.json')))
CORR, GLCORR = bd['corr'], bd['glcorr']
G = {g['gid']: g for g in bd['games']}
SUN = [g['gid'] for g in bd['games'] if g['kick'].startswith('Sun')]
S = SGP.load()
def dec(o): return 1 + o / 100 if o > 0 else 1 + 100 / (-o)
def am(d): return f"+{round((d-1)*100)}" if d >= 2 else f"-{round(100/(d-1))}"
def ost(o): return f"+{int(o)}" if o > 0 else f"{int(o)}"
for l in bd['legs']: l['r'] = SW.risk_score(l, bd)
GL = ('Spread', 'Total', 'Moneyline')
def tags(l): return [f[1] for f in (l.get('fh') or []) + (bd['pf'].get(l['pl']) or []) if f[0] in ('bad', 'watch')]
def good(l): return [f[1] for f in (l.get('fh') or []) + (bd['pf'].get(l['pl']) or []) if f[0] == 'good']
def corr(a, b):
    if a['g'] != b['g']: return 0.0
    if not a.get('c') or not b.get('c'): return 0.0
    rel = "SP" if a["pl"] == b["pl"] else ("TM" if a.get("tm") == b.get("tm") else "OPP")
    k = sorted([a["c"], b["c"]]); return float(CORR.get(f"{rel}|{k[0]}|{k[1]}", 0) or 0)
RNG = np.random.default_rng(7).standard_normal((40000, 6))
def joint(ls, key='p'):
    n = len(ls); C = np.array([[1.0 if i == j else corr(ls[i], ls[j]) for j in range(n)] for i in range(n)])
    w, v = np.linalg.eigh(C); A = v @ np.diag(np.sqrt(np.clip(w, 1e-6, None)))
    z = np.array([NormalDist().inv_cdf(min(.995, max(.005, l[key]))) for l in ls])
    g = RNG[:, :n] @ A.T
    return float(np.mean(np.all(g <= z, axis=1)))
def line(l):
    return f"{l['pl']:<22.22} {l['tm']:<3} {l['pos']:<2} {l['ms']:<9.9} {l['ln']:>5g}+ {ost(l['o']):>5} p{l['p']*100:4.0f} bk{l['bk']*100:4.0f} e{l['e']*100:+4.0f} r{l['r']} proj {l.get('proj')} avg {l.get('avg')} n{l.get('n')} nz{l.get('nzr')} | {','.join(tags(l))[:60]} | +{','.join(good(l))[:40]}"
def props(g, lo, hi, td=False):
    return [l for l in bd['legs'] if l['g'] == g and l.get('fd') and l['m'] not in GL and not l['m'].startswith('Under') and l['m'] not in ('First TD', '2+ TD', '3+ TD')
            and lo <= l['o'] <= hi and (td or l['m'] != 'Anytime TD')]
def find(pl, ms, ln):
    c=[l for l in bd['legs'] if l['pl'].startswith(pl) and l['ms'].lower().startswith(ms.lower()) and abs(l['ln']-ln)<.01 and l.get('fd') and not l['m'].startswith('Under')]
    assert len(c)==1, (pl,ms,ln,[(x['pl'],x['ms'],x['m']) for x in c])
    return c[0]
def slip(*specs):
    ls=[find(*s) for s in specs]; n=len(ls)
    same=len({l['g'] for l in ls})==1
    jm=joint(ls,'p'); jb=joint(ls,'bk'); d=SGP.price(n,jb,S) if same else math.prod(dec(l['o']) for l in ls)
    return ls, jm, d
def show(*specs):
    ls,jm,d=slip(*specs)
    print(f"model {jm*100:.0f}% est {am(d)} ev {(jm*d-1)*100:+.0f}c :: "+' + '.join(f"{l['pl']} {l['ms']} {l['ln']:g}+ ({ost(l['o'])}, r{l['r']}, p{l['p']*100:.0f})" for l in ls))
    return ls
