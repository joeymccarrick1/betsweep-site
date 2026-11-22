"""See tool.py."""

import os as _os, sys as _sys
ROOT = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", ".."))
MIRROR = _os.environ.get("MIRROR") or _os.path.join(_os.path.dirname(ROOT), "sm", "in")
_sys.path.insert(0, ROOT); _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import csv, json, sys
from tool import *
import hunches as HN
log = HN.load_log(_os.path.join(MIRROR, 'gamelog.json'))
for r in log: r['s']=2026; r['td']=(r['rtd'] or 0)+(r['rectd'] or 0)
past=[]
for y in (2024,2025):
    for r in csv.DictReader(open(_os.path.join(ROOT, 'in', f'stats_player_week_{y}.csv'), newline='')):
        if r.get('season_type')!='REG' or r.get('position') not in ('QB','RB','WR','TE'): continue
        n=HN.num
        past.append({'s':y,'w':int(n(r['week'])),'pl':r['player_display_name'],'tm':HN.FIXT.get(r['team'],r['team']),'pos':r['position'],'opp':HN.FIXT.get(r['opponent_team'],r['opponent_team']),
                     'att':n(r.get('attempts')),'car':n(r.get('carries')),'tgt':n(r.get('targets')),'td':(n(r.get('rushing_tds')) or 0)+(n(r.get('receiving_tds')) or 0)})
def pct(rows,pos):
    v={}
    for d in {r['opp'] for r in rows}:
        x=[r for r in rows if r['opp']==d and r['pos']==pos]; g=len({(r['w'],r['tm']) for r in x})
        if g>=4: v[d]=sum(r['td'] for r in x)/g
    n=len(v); return {d:(sum(1 for e in v if v[e]<v[d])+0.5*(sum(1 for e in v if v[e]==v[d])-1))/(n-1) for d in v}, v
CUR={p:pct(log,p) for p in ('QB','RB','WR','TE')}
PP={(y,p):pct([r for r in past if r['s']==y],p)[0] for y in (2024,2025) for p in ('QB','RB','WR','TE')}
VOL={'RB':('car',10),'WR':('tgt',4),'TE':('tgt',4),'QB':('att',15)}
LOOK=json.load(open(_os.path.join(ROOT, 'out', 'hunch-looks.json')))['looks']
def nn(x): return HN._nn(x)
def check(l):
    pos=l['pos']; opp=l['opp']; cp,cv=CUR[pos]; p0=cp.get(opp); rank=1+sum(1 for d in cv if cv[d]>cv[opp])
    fl=tags(l)
    m_ok = p0 is not None and rank<=16 and 'Tough matchup' not in fl
    cb='n/a'; cb_ok=True
    if pos=='WR':
        ev=' '.join((LOOK.get(l['pl']) or {}).get('ev',[])); cb='favorable' if 'favorable' in ev else 'difficult' if 'difficult' in ev else 'neutral' if 'neutral' in ev else 'not on chart'
        cb_ok = cb in ('favorable','neutral')
    g=G[l['g']]; w=PR._w(g); sc=PR._sc(l,w); k=max(range(4),key=lambda i:w[i])
    s_ok = bool(sc) and sc[k]>=l['p']*0.97 and not ({'Trail script','Losing side','Blowout rest risk','Blowout script'} & set(fl))
    key,fl_=VOL[pos]
    gms=[r for r in past if nn(r['pl'])==nn(l['pl']) and (r[key] or 0)>=fl_ and abs(PP[(r['s'],pos)].get(r['opp'],9)-p0)<=0.15]
    hit=sum(1 for r in gms if r['td']>0)
    sim=None if len(gms)<4 else hit/len(gms)
    d_ok = sim is not None and sim>=max(0.5,l['bk']-0.05)
    return dict(m_ok=m_ok, rank=rank, tdpg=cv[opp], cb=cb, cb_ok=cb_ok, s_ok=s_ok, sck=sc[k] if sc else None, most=g['most'], sim=sim, n=len(gms), hit=hit, d_ok=d_ok, d_unknown=sim is None)
if __name__=='__main__':
    rows=[]
    for l in bd['legs']:
        if l['m']!='Anytime TD' or l['g'] not in SUN or not l.get('fd') or l['o']>220: continue
        gl=sorted(bd['gl'].get(l['pl'],[]), key=lambda x:-x['w']); td=[x['td'] or 0 for x in gl]
        if len(td)<3: continue
        c=check(l); c.update(l=l, sg=sum(1 for t in td if t>0), ng=len(td), l3=sum(td[:3]), tot=sum(td))
        rows.append(c)
    rows.sort(key=lambda c:(-(c['m_ok']+c['cb_ok']+c['s_ok']+c['d_ok']), -c['l']['p']))
    for c in rows:
        l=c['l']; ok=lambda b:'PASS' if b else 'fail'
        print(f"{l['pl']:<20.20} {l['tm']:<3} {l['pos']} {ost(l['o']):>5} p{l['p']*100:3.0f} r{l['r']:<2} scored {c['sg']}/{c['ng']} tot {c['tot']:.0f} L3 {c['l3']:.0f} | matchup {ok(c['m_ok'])} (#{c['rank']}, {c['tdpg']:.2f}/g) | cb {c['cb']} {ok(c['cb_ok'])} | script {ok(c['s_ok'])} ({c['most']}: {c['sck']*100 if c['sck'] else 0:.0f}%) | similar {'none' if c['d_unknown'] else f'{c[chr(104)+chr(105)+chr(116)]}/{c[chr(110)]}'} {ok(c['d_ok'])} | {','.join(tags(l))[:60]}")
