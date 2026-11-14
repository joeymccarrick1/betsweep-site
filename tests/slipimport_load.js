// 11/14: the owner's 12-leg slip - import, load into the betslip, and resolve every leg the way the builder does (bs_slipk + bs_slipg)
const fs=require('fs'), cp=require('child_process');
const code=cp.execSync('python3 -c "import slipimport,sys;sys.stdout.write(slipimport.IMPORT_JS)"',{cwd:__dirname+'/..'}).toString();
const store={}; global.window={}; global.document={addEventListener(){},getElementById(){return null},querySelector(){return null},readyState:'complete'};
global.localStorage={getItem(k){return k in store?store[k]:null},setItem(k,v){store[k]=String(v)},removeItem(k){delete store[k]}}; global.sessionStorage={getItem(){return null},setItem(){},removeItem(){}}; global.location={};
eval(code);
const D=JSON.parse(fs.readFileSync(process.argv[2]||'/tmp/D.json','utf8'));
const text=`12 Leg Parlay +197085
Over 49.5 -110
TOTAL POINTS
New England Patriots @ Detroit Lions SUN 8:30AM CT
Atlanta Falcons (+5.5) -166
ALTERNATE SPREAD
Kansas City Chiefs @ Atlanta Falcons SUN 12:01PM CT
Buffalo Bills -7.5 -110
SPREAD
Buffalo Bills @ New York Jets SUN 12:01PM CT
Carolina Panthers (+2.5) 1M
ALTERNATE SPREAD
Carolina Panthers @ New Orleans S... SUN 12:01PM CT
Cleveland Browns (+3.5) +100
ALTERNATE SPREAD
Houston Texans @ Cleveland Browns SUN 12:01PM CT
Over (45.5) -113
ALTERNATE TOTAL POINTS
Jacksonville Jaguars @ Tennessee... SUN 12:01PM CT
Under 42.5 -115
TOTAL POINTS
Minnesota Vikings @ Green Bay Pac... SUN 12:01PM CT
Over (37.5) -120
ALTERNATE TOTAL POINTS
Miami Dolphins @ Indianapolis Colts SUN 12:01PM CT
Under 39.5 -110
TOTAL POINTS
Los Angeles Rams @ Arizona Cardin... SUN 3:06PM CT
Las Vegas Raiders (+5.5) +106
ALTERNATE SPREAD
Seattle Seahawks @ Las Vegas Raid... SUN 3:06PM CT
Under (56.5) -115
ALTERNATE TOTAL POINTS
San Francisco 49ers @ Dallas Cowb... SUN 3:26PM CT
Under 49.5 -115
TOTAL POINTS
Pittsburgh Steelers @ Cincinnati Beng... SUN 7:21PM CT`;
const want=['DET-NE','ATL-KC','BUF-NYJ','CAR-NO','CLE-HOU','JAX-TEN','GB-MIN','IND-MIA','ARI-LA','LV-SEA','DAL-SF','CIN-PIT'];
const R=window.BSImport.parse(text,D);
// what the Load button does: keys + the game map
const legKey=l=>l.pl+'|'+l.m+'|'+Math.round(l.ln||1);
const n={}; D.legs.forEach(l=>{const k=legKey(l);(n[k]=n[k]||{})[l.g]=l.i;});
const gm={}; R.legs.forEach(x=>{ if(x.ok&&x.leg&&(Object.keys(n[x.key]).length>1||x.leg.m==='Total')) (gm[x.key]=gm[x.key]||[]).push(x.leg.g); });
// the builder's resolveKeys
const used={}, seen={}; let bad=0;
R.legs.forEach((x,i)=>{ if(!x.ok){ console.log('NOT READ', x.raw, x.why); bad++; return; }
  const m=n[x.key]; const c=seen[x.key]=(seen[x.key]||0)+1; const g=(gm[x.key]||[])[c-1]; let idx=null;
  if(g!=null&&m[g]!=null&&!used[m[g]]) idx=m[g]; else for(const gg of Object.keys(m)) if(!used[m[gg]]){idx=m[gg];break;}
  used[idx]=1; const l=D.legs[idx]; const ok=l.g===want[i]; if(!ok) bad++;
  console.log((ok?'OK  ':'BAD '), l.pl, l.g, l.o, ok?'':'(wanted '+want[i]+')'); });
console.log(bad? bad+' WRONG':'all 12 legs load into their own games'); process.exit(bad?1:0);
