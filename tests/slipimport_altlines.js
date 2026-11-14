const fs=require('fs'); const code=require('child_process').execSync('python3 -c "import slipimport,sys;sys.stdout.write(slipimport.IMPORT_JS)"',{cwd:__dirname+'/..'}).toString();
global.window={}; global.document={addEventListener(){},getElementById(){return null},querySelector(){return null},readyState:'complete'}; global.localStorage={getItem(){return null},setItem(){}}; global.sessionStorage=global.localStorage; global.location={};
try{ eval(code); }catch(e){}
const D=JSON.parse(fs.readFileSync(process.argv[2]||'/tmp/D.json','utf8'));
const shots={
JAX:`Same Game Parlay +289
Jacksonville Jaguars @ Tennessee Titans SUN 12:01PM CT
Nate Boerkircher 5+ Yards
NATE BOERKIRCHER - ALT RECEIVING YDS
Calvin Ridley 10+ Yards
CALVIN RIDLEY - ALT RECEIVING YDS
Tennessee Titans (+19.5)
ALTERNATE SPREAD
Over (40.5)
ALTERNATE TOTAL POINTS`,
DET:`Same Game Parlay +270
New England Patriots @ Detroit Lions SUN 8:30AM CT
Drake Maye 225+ Yards
DRAKE MAYE - ALT PASSING YDS
Jahmyr Gibbs
ANY TIME TOUCHDOWN SCORER
Detroit Lions (+2.5)
ALTERNATE SPREAD
Over (47.5)
ALTERNATE TOTAL POINTS`,
ARI:`Same Game Parlay +172
Los Angeles Rams @ Arizona Cardinals SUN 3:06PM CT
Kyren Williams 10+ Yards
KYREN WILLIAMS - ALT RECEIVING YDS
Arizona Cardinals (+15.5)
ALTERNATE SPREAD
Over (34.5)
ALTERNATE TOTAL POINTS`,
GB:`Green Bay Packers (−3)
SPREAD
Minnesota Vikings @ Green Bay Packers
Under 42.5
TOTAL POINTS
Minnesota Vikings @ Green Bay Packers`};
for (const k in shots){ const r=window.BSImport.parse(shots[k],D); console.log(k, r.legs.map(l=>(l.ok?'OK ':'NO ')+(l.label||l.raw)+(l.ok?'':' ('+l.why+')')+(l.leg&&l.leg.g?' ['+l.leg.g+']':'')).join(' | ')); }
