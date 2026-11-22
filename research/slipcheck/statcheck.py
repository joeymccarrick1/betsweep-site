"""See tool.py."""

import os as _os, sys as _sys
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
MIRROR = _os.environ.get("MIRROR") or _os.path.join(_os.path.dirname(ROOT), "sm", "in")
_sys.path.insert(0, ROOT); _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import csv, json, sys
from tool import *
import hunches as HN
log = HN.load_log(_os.path.join(MIRROR, 'gamelog.json'))
KEYS = sorted(log[0].keys())
def n0(x): return x or 0
for r in log:
    r['s']=2026; r['td']=n0(r.get('rtd'))+n0(r.get('rectd'))
past=[]
for y in (2024,2025):
    for r in csv.DictReader(open(_os.path.join(ROOT, 'in', f'stats_player_week_{y}.csv'), newline='')):
        if r.get('season_type')!='REG' or r.get('position') not in ('QB','RB','WR','TE'): continue
        n=HN.num
        past.append({'s':y,'w':int(n(r['week'])),'pl':r['player_display_name'],'tm':HN.FIXT.get(r['team'],r['team']),'pos':r['position'],'opp':HN.FIXT.get(r['opponent_team'],r['opponent_team']),
                     'att':n(r.get('attempts')),'car':n(r.get('carries')),'tgt':n(r.get('targets')),'td':n0(n(r.get('rushing_tds')))+n0(n(r.get('receiving_tds'))),
                     'pyd':n(r.get('passing_yards')),'ptd':n(r.get('passing_tds')),'ryd':n(r.get('rushing_yards')),'recyd':n(r.get('receiving_yards')),'rec':n(r.get('receptions'))})

for r in log: r['recyd'] = r.get('recy')
ALL = past + log
def val(r, m):
    if m == 'Passing Yards': return r.get('pyd')
    if m == 'Passing TDs': return r.get('ptd')
    if m == 'Rushing Yards': return r.get('ryd')
    if m == 'Receiving Yards': return r.get('recyd')
    if m == 'Receptions': return r.get('rec')
    if m == 'Rush + Rec Yards': return n0(r.get('ryd')) + n0(r.get('recyd'))
    if m == 'Anytime TD': return r.get('td')
    return None
def pct(rows, pos, m):
    v = {}
    for d in {r['opp'] for r in rows}:
        x = [r for r in rows if r['opp'] == d and r['pos'] == pos]; g = len({(r['w'], r['tm']) for r in x})
        if g >= 4: v[d] = sum(n0(val(r, m)) for r in x) / g
    n = len(v); return {d: (sum(1 for e in v if v[e] < v[d]) + 0.5 * (sum(1 for e in v if v[e] == v[d]) - 1)) / (n - 1) for d in v}, v
_C = {}
def P(season, pos, m):
    k = (season, pos, m)
    if k not in _C: _C[k] = pct([r for r in ALL if r['s'] == season], pos, m)
    return _C[k]
VOL = {'RB': ('car', 8), 'WR': ('tgt', 4), 'TE': ('tgt', 3), 'QB': ('att', 15)}
LOOK = json.load(open(_os.path.join(ROOT, 'out', 'hunch-looks.json')))['looks']
def nn(x): return HN._nn(x)
def check(l, week=11):
    pos = l['pos']; opp = l['opp']; m = l['m']; cp, cv = P(2026, pos, m); p0 = cp.get(opp); rank = (1 + sum(1 for d in cv if cv[d] > cv[opp])) if opp in cv else None
    fl = tags(l)
    m_ok = p0 is not None and rank <= 16 and 'Tough matchup' not in fl
    cb = 'n/a'; cb_ok = True
    if pos == 'WR':
        ev = ' '.join((LOOK.get(l['pl']) or {}).get('ev', [])); cb = 'favorable' if 'favorable' in ev else 'difficult' if 'difficult' in ev else 'neutral' if 'neutral' in ev else 'not on chart'
        cb_ok = cb in ('favorable', 'neutral')
    g = G[l['g']]; w = PR._w(g); sc = PR._sc(l, w); k = max(range(4), key=lambda i: w[i])
    s_ok = bool(sc) and sc[k] >= l['p'] * 0.97 and not ({'Trail script', 'Losing side', 'Blowout rest risk', 'Blowout script'} & set(fl))
    key, fl_ = VOL[pos]
    gms = [r for r in ALL if nn(r['pl']) == nn(l['pl']) and not (r['s'] == 2026 and r['w'] >= week) and n0(r.get(key)) >= fl_ and p0 is not None and abs(P(r['s'], pos, m)[0].get(r['opp'], 9) - p0) <= 0.15]
    need = l['ln'] if float(l['ln']).is_integer() else l['ln'] + 0.5
    hit = sum(1 for r in gms if n0(val(r, m)) >= need)
    sim = None if len(gms) < 4 else hit / len(gms)
    d_ok = sim is not None and sim >= max(0.5, l['bk'] - 0.05)
    # this season: how often he cleared this line
    cur = [r for r in log if nn(r['pl']) == nn(l['pl']) and r['w'] < week]; ch = sum(1 for r in cur if n0(val(r, m)) >= need)
    return dict(m_ok=m_ok, rank=rank, allow=cv.get(opp), cb=cb, cb_ok=cb_ok, s_ok=s_ok, sck=sc[k] if sc else None, most=g['most'], sim=sim, n=len(gms), hit=hit, d_ok=d_ok, d_unknown=sim is None, season=f"{ch}/{len(cur)}", l3=[n0(val(r, m)) for r in sorted(cur, key=lambda r: -r['w'])[:3]])
def row(l):
    c = check(l); ok = lambda b: 'PASS' if b else 'fail'
    simtxt = 'none' if c['d_unknown'] else f"{c['hit']}/{c['n']}"
    return (f"{l['g']:<8} {l['pl']:<19.19} {l['pos']} {l['ms']:<9.9} {l['ln']:>5g}+ {ost(l['o']):>5} p{l['p']*100:3.0f} raw{l['raw_p']*100:3.0f} bk{l['bk']*100:3.0f} r{l['r']} season {c['season']} L3 {c['l3']} | matchup {ok(c['m_ok'])} (#{c['rank']}) | cb {c['cb']} {ok(c['cb_ok'])} | script {ok(c['s_ok'])} ({c['most']}: {(c['sck'] or 0)*100:.0f}%) | similar {simtxt} {ok(c['d_ok']) if not c['d_unknown'] else '-'} | {','.join(tags(l))}", c)
if __name__ == '__main__':
    import time
    now = time.time() * 1000
    live = [g['gid'] for g in bd['games'] if g['ko'] > now and g['kick'].startswith('Sun')]
    lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (-199, -130)
    c = [l for l in bd['legs'] if l['g'] in live and l.get('fd') and l['m'] in ('Passing Yards', 'Passing TDs', 'Rushing Yards', 'Receiving Yards', 'Receptions', 'Rush + Rec Yards', 'Anytime TD') and lo <= l['o'] <= hi
         and l['r'] <= 1 and not [f for f in (l.get('fh') or []) + (bd['pf'].get(l['pl']) or []) if f[0] == 'bad'] and not l.get('w') and (l.get('z') or ['n'])[0] != 'l']
    out = []
    for l in c:
        t, k = row(l); out.append((-(k['m_ok'] + k['cb_ok'] + k['s_ok'] + (k['d_ok'] or 0)), -(l['raw_p'] - l['bk']), t))
    for _, _, t in sorted(out): print(t)
