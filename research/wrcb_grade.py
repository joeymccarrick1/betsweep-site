import json,collections,statistics as st
def V(f):
    d=json.load(open(f)); return d["values"] if isinstance(d,dict) else d
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
wc=V("wrcb.json")
ls=V("legsnaps.json"); L={c:i for i,c in enumerate(ls[0])}
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
    if w>=10: continue
    p=r[2]; a=act.get((w,p))
    if not a or (a["tg"]==0 and a["y"]==0): continue
    dtr=num(r[44]); dfr=num(r[45])
    if dtr is not None and abs(dtr)>1: dtr/=100
    b=best.get((w,p))
    rows.append(dict(w=w,p=p,fl=r[42],sh=r[17]=="YES",dtr=dtr,dfr=dfr,adj=num(r[40]),y=a["y"],tg=a["tg"],pr=prior(p,w),line=b[2] if b else None,tgt=num(r[8]) or 0))
print(len(rows),"receiver-weeks with a stat line; weeks",sorted(collections.Counter(x["w"] for x in rows).items()))
def rep(name,xs):
    if len(xs)<6: print(f"{name:40} n={len(xs)} (too few)"); return
    wl=[x for x in xs if x["line"] is not None]; wp=[x for x in xs if x["pr"]]
    oh=sum(x["y"]>=x["line"] for x in wl)/len(wl) if wl else float("nan")
    dy=st.mean(x["y"]-x["pr"][0] for x in wp) if wp else float("nan"); dt=st.mean(x["tg"]-x["pr"][1] for x in wp) if wp else float("nan")
    beat=sum(x["y"]>x["pr"][0] for x in wp)/len(wp) if wp else float("nan")
    print(f"{name:40} n={len(xs):3} | rec-yds line over hit {oh*100:5.1f}% (n={len(wl):3}) | vs season avg: {dy:+5.1f} yds, {dt:+4.1f} tgts, beat avg {beat*100:4.0f}% (n={len(wp)})")
rep("ALL chart receivers",rows)
for f in ("FAVORABLE","NEUTRAL","DIFFICULT"): rep("sheet flag "+f,[x for x in rows if x["fl"]==f])
rep("projected SHADOW",[x for x in rows if x["sh"]])
d=[x for x in rows if x["dtr"] is not None and x["dfr"] is not None]
print("-- Clay delta rows, weeks",sorted({x['w'] for x in d}),len(d))
E=lambda x: x["dtr"]>=.08 and x["dfr"]>=.15; T=lambda x: x["dtr"]<=-.08 and x["dfr"]<=-.15
rep("Coverage edge (+8% T/R & +0.15 F/R)",[x for x in d if E(x)]); rep("Tough coverage (-8% & -0.15)",[x for x in d if T(x)]); rep("in between",[x for x in d if not E(x) and not T(x)])
for w in sorted({x['w'] for x in d}): rep(f"   edge, week {w}",[x for x in d if E(x) and x["w"]==w]); rep(f"   tough, week {w}",[x for x in d if T(x) and x["w"]==w])
s=sorted(d,key=lambda x:-x["dfr"]); rep("F/R delta top third",s[:len(d)//3]); rep("F/R delta bottom third",s[-(len(d)//3):])
big=[x for x in d if x["tgt"]>=.18]; s=sorted(big,key=lambda x:-x["dfr"])
rep("starters (18%+ tgt): softer half",s[:len(s)//2]); rep("starters (18%+ tgt): tougher half",s[len(s)//2:])
