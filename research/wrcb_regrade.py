"""Regrade the WR-CB chart's alignment flag with one sign for every week (11/17). usage: python3 research/wrcb_regrade.py <in dir with gamelog.json, wrcb.json, legsnaps.json>
FAVORABLE = the defense allows the most to his alignment (low rank). Receiving-yards line nearest -110 from the latest freeze."""
import json,collections,statistics as st,sys
IN=sys.argv[1]
def V(f):
    d=json.load(open(IN+'/'+f)); return d["values"] if isinstance(d,dict) else d
def num(s):
    s=str(s).strip()
    if s=="": return None
    try: return float(s.rstrip("%"))/100 if s.endswith("%") else float(s)
    except: return None
gl=V("gamelog.json"); H={c:i for i,c in enumerate(gl[0])}
act={}
for r in gl[1:]:
    f=lambda c: float(r[H[c]] or 0)
    act[(int(r[0]),r[1])]={"y":f("Rec Yds"),"rec":f("Receptions"),"tg":f("Targets")}
hist=collections.defaultdict(list)
for (w,p),a in act.items(): hist[p].append((w,a))
def prior(p,w):
    xs=[a for ww,a in hist[p] if ww<w and a["tg"]>0]
    return (st.mean(a["y"] for a in xs), st.mean(a["tg"] for a in xs), len(xs)) if len(xs)>=3 else None
wc=V("wrcb.json"); ls=V("legsnaps.json"); L={c:i for i,c in enumerate(ls[0])}
imp=lambda o:(-o/(-o+100)) if o<0 else 100/(o+100)
best={}
for r in ls[1:]:
    r=r+[""]*(len(ls[0])-len(r))
    try: w=int(float(r[0])); o=float(r[L["FanDuel odds"]]); ln=float(r[L["Line (X+)"]])
    except Exception: continue
    if r[L["Market"]]!="Receiving Yards" or not(-170<=o<=150): continue
    k=(w,r[L["Player"]]); d=abs(imp(o)-.5238); fz=r[L["Frozen At"]]
    if k not in best or (fz,-d)>(best[k][0],-best[k][1]): best[k]=(fz,d,ln,o)
rows=[]
for r in wc[1:]:
    r=r+[""]*(46-len(r))
    try: w=int(r[1])
    except: continue
    if w<7 or w>10: continue
    p=r[2]; a=act.get((w,p))
    if not a or (a["tg"]==0 and a["y"]==0): continue
    rank=num(r[35]); sc=(16.5-rank)/15.5 if rank is not None else None
    fix="FAVORABLE" if sc is not None and sc>=0.4 else "DIFFICULT" if sc is not None and sc<=-0.4 else "NEUTRAL"
    b=best.get((w,p))
    rows.append(dict(w=w,p=p,fl=r[42],fix=fix,rank=rank,y=a["y"],tg=a["tg"],pr=prior(p,w),line=b[2] if b else None,tgt=num(r[8]) or 0))
print(len(rows),"receiver-weeks with a stat line; weeks",sorted(collections.Counter(x["w"] for x in rows).items()))
def rep(name,xs):
    if len(xs)<6: print(f"{name:44} n={len(xs)} (too few)"); return
    wl=[x for x in xs if x["line"] is not None]; wp=[x for x in xs if x["pr"]]
    oh=sum(x["y"]>=x["line"] for x in wl)/len(wl) if wl else float("nan")
    dy=st.mean(x["y"]-x["pr"][0] for x in wp) if wp else float("nan"); dt=st.mean(x["tg"]-x["pr"][1] for x in wp) if wp else float("nan")
    print(f"{name:44} n={len(xs):3} | rec-yds line over hit {oh*100:5.1f}% (n={len(wl):3}) | vs season avg: {dy:+5.1f} yds, {dt:+4.1f} tgts (n={len(wp)})")
rep("ALL chart receivers",rows)
print("-- the flag on the sheet (before 11/17 the Week 8-10 blocks carried the opposite sign: FAVORABLE 55.9% (34), NEUTRAL 53.2% (190), DIFFICULT 39.2% (51))")
for f in ("FAVORABLE","NEUTRAL","DIFFICULT"): rep("stored flag "+f,[x for x in rows if x["fl"]==f])
print("-- the flag with one sign for every week (low rank = defense allows the most = FAVORABLE)")
for f in ("FAVORABLE","NEUTRAL","DIFFICULT"): rep("corrected flag "+f,[x for x in rows if x["fix"]==f])
for w in (7,8,9,10):
    for f in ("FAVORABLE","DIFFICULT"): rep(f"   week {w} corrected {f}",[x for x in rows if x["fix"]==f and x["w"]==w])
s=sorted([x for x in rows if x["rank"] is not None],key=lambda x:x["rank"]); n=len(s)//3
rep("easiest third by alignment rank",s[:n]); rep("middle third",s[n:2*n]); rep("toughest third by alignment rank",s[2*n:])
