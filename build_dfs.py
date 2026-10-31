#!/usr/bin/env python3
"""build_dfs.py - DFS lineup builder page (out/dfs.html): build DraftKings / FanDuel classic lineups against the model.

Usage: python3 build_dfs.py   (after build_firsttd.py; reads the same inputs as build_team.py - it reuses that file's player loader)
Inputs (in/): proj_qb/rb/wr/te/k/dst.json, eligible.json, avail.json, snaps.json, ranks.json, games.csv, boards.json; out/firsttd_top.json (optional).
Salaries are NOT in the sheet: the page takes the DraftKings or FanDuel "player list" CSV that every contest offers (pasted or uploaded,
parsed in the browser, kept in localStorage), matches names to the model, re-scores every player in that site's scoring, and runs the
optimizer. Nothing leaves the browser. Player IDs from the CSV let the page export a lineup file the site accepts for upload.
"""
import json, os, re, html, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
# reuse build_team.py's loader: PLAYERS (n,t,p,o,fp,py,ptd,int,ry,rtd,rec,rcy,rctd,act,role,av,st,sd,q,dr,k), WEEK, LOGO, BANNER, vals(), E
src = open(os.path.join(HERE, "build_team.py")).read().split("stamp = datetime")[0]
exec(src)
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
stamp = datetime.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p")
FTD = {}
try:
    for gid, rs in json.load(open(os.path.join(OUT, "firsttd_top.json")))["games"].items():
        for r in rs: FTD[r[0]] = r[3]
except Exception: pass
POOL = []
for p in PLAYERS:   # kickers stay in the pool: single-game (MVP/Captain) contests use them; classic mode hides them
    q = {k: p.get(k) for k in ("n", "t", "p", "o", "fp", "py", "ptd", "int", "ry", "rtd", "rec", "rcy", "rctd", "act", "av", "st", "q", "k", "dr", "or", "sos")}
    if p.get("sd"): q["sd"] = p["sd"]
    if p["n"] in FTD: q["ftd"] = FTD[p["n"]]
    POOL.append(q)
DATA = {"week": WEEK, "stamp": stamp, "players": POOL}
# DraftKings salaries, pulled automatically by the sheet's DKSalaries.gs into 'AUTO - DK Salaries' (A:I = DraftKings' own player-list CSV for the
# main classic slate, K1:L4 = Updated / Draft group / Slate / Start). Embedded as CSV text so the page's importCSV() reads it exactly like a pasted
# file. Skipped when the tab is missing/empty or the slate started more than 2 days before this build (stale list).
DK_AUTO = None
try:
    _rows = json.load(open(os.path.join(HERE, "in", "dksal.json"))).get("values") or []
    _meta = {}
    for _r in _rows[:6]:
        if len(_r) > 11 and str(_r[10]).strip(): _meta[str(_r[10]).strip().lower()] = str(_r[11]).strip()
    _body = [list(_r[:9]) for _r in _rows if _r and str(_r[0]).strip()]
    if len(_body) > 20 and "salary" in [str(c).strip().lower() for c in _body[0]]:
        _start = _meta.get("start", "")
        _fresh = True
        try:
            _sd = datetime.datetime.fromisoformat(_start[:16].replace(" ", "T"))
            _fresh = (datetime.datetime.now() - _sd).days < 2
        except Exception: pass
        if _fresh:
            def _q(c):
                c = str(c); return '"' + c.replace('"', '""') + '"' if any(x in c for x in ',"\n') else c
            DK_AUTO = {"csv": "\n".join(",".join(_q(c) for c in (r + [""] * (9 - len(r)))) for r in _body),
                       "upd": _meta.get("updated", ""), "slate": _meta.get("slate", "main slate"), "start": _start, "n": len(_body) - 1}
            DATA["dk"] = DK_AUTO
except FileNotFoundError: pass
except Exception as _e: print("WARN DK auto salaries not embedded:", _e)
n_act = sum(1 for p in POOL if p["act"])

CSS = r"""
.dfs{max-width:1360px;margin:0 auto;display:grid;gap:14px}
.dfs .panel{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.dfs h2{font-family:var(--display);font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:13px;margin:0;padding:10px 14px;border-bottom:1px solid var(--line);color:var(--mute);display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.dfs h2 b{color:var(--ink)} .dfs h2 .r{margin-left:auto;font-family:var(--body);font-weight:500;letter-spacing:0;text-transform:none;font-size:12px}
.dfs .seg{display:inline-flex;border:1px solid var(--line);border-radius:6px;overflow:hidden}
.dfs .seg button{font:inherit;font-family:var(--display);font-weight:700;letter-spacing:.06em;text-transform:uppercase;font-size:12px;background:var(--card);color:var(--ink);border:0;border-right:1px solid var(--line);padding:7px 12px;cursor:pointer}
.dfs .seg button:last-child{border-right:0} .dfs .seg button.on{background:var(--ink);color:var(--bg)}
.dfs .src{padding:12px 14px;display:grid;gap:10px}
.dfs .src.drop{outline:2px dashed var(--ink);outline-offset:-6px;background:color-mix(in srgb,var(--ink) 6%,var(--card))}
.dfs .src .how.ph{font-size:12.5px}
.dfs .src .row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.dfs .src textarea{font:12px/1.4 ui-monospace,Menlo,Consolas,monospace;width:100%;min-height:84px;border:1px solid var(--line);border-radius:6px;padding:8px;background:var(--chalk);color:var(--ink)}
.dfs .src input[type=file]{font-size:13px}
.dfs .btn{font:inherit;font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:13px;color:var(--red-ink);background:var(--red);border:0;border-radius:6px;padding:9px 16px;cursor:pointer}
.dfs .btn.sec{background:var(--chalk);color:var(--ink);border:1px solid var(--line)} .dfs .btn:disabled{opacity:.5;cursor:not-allowed}
.dfs .how{margin:0;color:var(--mute);font-size:12.5px;line-height:1.5} .dfs .how b{color:var(--ink)}
.dfs .msg{font-size:13px;padding:8px 10px;border-radius:6px;background:var(--chalk)} .dfs .msg.err{color:var(--bad)} .dfs .msg.ok{color:var(--good)}
.dfs .status{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12.5px;color:var(--mute);padding:8px 14px;border-top:1px solid var(--line)} .dfs .status b{color:var(--ink)}
.dfs .grid2{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:14px;align-items:start}
@media(max-width:980px){.dfs .grid2{grid-template-columns:1fr}}
.dfs .filters{display:flex;flex-wrap:wrap;gap:8px;padding:10px 14px;border-bottom:1px solid var(--line);align-items:center}
.dfs .filters select,.dfs .filters input{font:inherit;font-size:13px;color:var(--ink);background:var(--chalk);border:1px solid var(--line);border-radius:6px;padding:7px 9px}
.dfs .filters input[type=search]{flex:1 1 160px;min-width:140px}
.dfs .filters label{font-size:12.5px;color:var(--mute);display:inline-flex;gap:5px;align-items:center}
.dfs table{width:100%;border-collapse:collapse;font-size:13px}
.dfs th{font:600 10.5px/1 var(--body);text-transform:uppercase;letter-spacing:.06em;color:var(--mute);text-align:right;padding:8px 8px;border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap;user-select:none}
.dfs th.l,.dfs td.l{text-align:left} .dfs th.on{color:var(--ink)}
.dfs td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.dfs td.l{white-space:normal}
.dfs tr.inl td{background:color-mix(in srgb,var(--good) 10%,transparent)}
.dfs tr.ex td{opacity:.45}
.dfs tr.na td{opacity:.5}
.dfs td .nm{font-weight:600} .dfs td .mt{display:block;color:var(--mute);font-size:11px;font-weight:400}
.dfs td .pos{display:inline-block;font-family:var(--display);font-weight:700;font-size:11px;color:var(--red);margin-left:6px}
.dfs td.sal input{width:62px;font:inherit;font-size:13px;text-align:right;background:transparent;border:0;border-bottom:1px dashed var(--line);color:var(--ink)}
.dfs td.val b{color:var(--good)} .dfs td.val.lo b{color:var(--mute)}
.dfs td.act{white-space:nowrap} .dfs td.act button{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--chalk);border-radius:5px;padding:3px 8px;cursor:pointer;color:var(--ink)}
.dfs td.act button.add{background:var(--ink);color:var(--bg);border-color:var(--ink)} .dfs td.act button.rm{background:var(--red);color:#fff;border-color:var(--red)}
.dfs td.act button.x.on{background:var(--bad);color:var(--bg);border-color:var(--bad)}
.dfs .tag{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.04em;border-radius:4px;padding:1px 5px;margin-left:4px;vertical-align:middle;background:var(--chalk);color:var(--mute)}
.dfs .tag.out{background:var(--bad);color:#fff} .dfs .tag.q{background:var(--warn);color:#000} .dfs .tag.sd{background:#fde7c8;color:#7a4b00} .dfs .tag.ftd{background:#e8f0ff;color:#1a3f8a}
.dfs .more{display:block;width:100%;text-align:left;font:inherit;font-size:13px;color:var(--red);background:none;border:0;padding:10px 14px;cursor:pointer}
.dfs .lu{position:sticky;top:120px}
.dfs .cap{padding:10px 14px;border-bottom:1px solid var(--line)}
.dfs .cap .bar{height:10px;border-radius:5px;background:var(--chalk);overflow:hidden;margin:6px 0 4px}
.dfs .cap .bar i{display:block;height:100%;background:var(--good);transition:width .2s} .dfs .cap .bar i.over{background:var(--bad)}
.dfs .cap .nums{display:flex;justify-content:space-between;font-size:12.5px;color:var(--mute)} .dfs .cap .nums b{color:var(--ink)}
.dfs .tot{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:var(--line);border-bottom:1px solid var(--line)}
.dfs .tot div{background:var(--card);padding:8px 12px} .dfs .tot small{display:block;font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:10.5px;color:var(--mute)}
.dfs .tot b{font-family:var(--display);font-weight:800;font-size:24px;line-height:1.1}
.dfs ul.slots{list-style:none;margin:0;padding:0}
.dfs ul.slots li{display:grid;grid-template-columns:44px 1fr auto auto;gap:8px;align-items:center;padding:7px 12px;border-bottom:1px solid var(--line);font-size:13px}
.dfs ul.slots li .sl{font-family:var(--display);font-weight:700;font-size:12px;color:var(--mute);letter-spacing:.06em}
.dfs ul.slots li .who{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap} .dfs ul.slots li .who small{color:var(--mute)}
.dfs ul.slots li .who.empty{color:var(--mute);font-style:italic}
.dfs ul.slots li .pts{font-variant-numeric:tabular-nums;text-align:right} .dfs ul.slots li .pts small{display:block;color:var(--mute);font-size:11px}
.dfs ul.slots li .ops{display:flex;gap:4px} .dfs ul.slots li .ops button{font:inherit;font-size:11px;border:1px solid var(--line);background:var(--chalk);border-radius:4px;padding:2px 6px;cursor:pointer;color:var(--ink)}
.dfs ul.slots li .ops button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.dfs .opts{padding:10px 12px;border-bottom:1px solid var(--line);display:grid;gap:6px;font-size:12.5px;color:var(--mute)}
.dfs .opts label{display:flex;align-items:center;gap:6px;flex-wrap:wrap} .dfs .opts select,.dfs .opts input[type=number]{font:inherit;font-size:12.5px;padding:3px 6px;border:1px solid var(--line);border-radius:5px;background:var(--chalk);color:var(--ink)}
.dfs .acts{display:flex;flex-wrap:wrap;gap:8px;padding:10px 12px}
.dfs .alts{padding:0 12px 10px} .dfs .alts h3{font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:11.5px;color:var(--mute);margin:8px 0 6px}
.dfs .alts .alt{border:1px solid var(--line);border-radius:6px;padding:7px 9px;margin-bottom:6px;font-size:12px;line-height:1.45}
.dfs .alts .alt b{font-family:var(--display);font-size:14px} .dfs .alts .alt button{float:right;font:inherit;font-size:11px;border:1px solid var(--line);background:var(--chalk);border-radius:4px;padding:2px 7px;cursor:pointer;color:var(--ink)}
.dfs .note{padding:8px 12px;font-size:11.5px;color:var(--mute);line-height:1.5}
.dfs .tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
.dfs .mbar{display:none}
@media(max-width:980px){.dfs .lu{position:static}
 .dfs .mbar{display:flex;position:fixed;left:12px;right:12px;bottom:12px;z-index:20;background:var(--ink);color:var(--bg);border-radius:10px;padding:10px 14px;justify-content:space-between;align-items:center;font-size:13px;text-decoration:none;box-shadow:0 6px 20px rgba(0,0,0,.25)}
 .dfs .mbar b{font-family:var(--display);letter-spacing:.06em;text-transform:uppercase;font-size:12px}
 .dfs{padding-bottom:60px}}
@media(max-width:700px){.dfs table{font-size:12.5px}.dfs td,.dfs th{padding:5px 4px}.dfs td.sal input{width:50px;font-size:12.5px}.dfs td.act button{padding:3px 6px;font-size:11.5px}.dfs td .mt{font-size:10.5px}.dfs th:nth-child(4),.dfs td.val{display:none}.dfs td .pos{margin-left:4px}.dfs .tag{font-size:9px;padding:1px 4px}}
.dfs #fmtSeg{margin-left:6px}
.dfs ul.slots li.mvp{background:color-mix(in srgb,var(--warn) 18%,transparent)}
.dfs ul.slots li.mvp .sl{color:var(--ink)} .dfs ul.slots li .sl em{font-style:normal;color:var(--red);font-size:11px}
.dfs ul.slots li .ops button.mv{color:#b07800;font-size:12px}
.dfs #optsSG,.dfs #optsClassic{display:grid;gap:6px} .dfs #optsSG[hidden],.dfs #optsClassic[hidden]{display:none}
.dfs #sgHint{color:var(--mute);line-height:1.4}
.dfs .expl{padding:12px 14px;font-size:13.5px;line-height:1.55;color:var(--ink)} .dfs .expl p{margin:0 0 8px} .dfs .expl dl{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;margin:6px 0 0;font-size:13px} .dfs .expl dt{font-weight:700} .dfs .expl dd{margin:0}
"""

JS = r"""
(function(){
  var D = window.__BS, P = D.players, $ = function(s){ return document.querySelector(s); }, $$ = function(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); };
  var SITES = {
    dk: {name:'DraftKings', cap:50000, slots:['QB','RB','RB','WR','WR','WR','TE','FLEX','DST'], flex:['RB','WR','TE'], def:'DST', upload:'QB,RB,RB,WR,WR,WR,TE,FLEX,DST'},
    fd: {name:'FanDuel', cap:60000, slots:['QB','RB','RB','WR','WR','WR','TE','FLEX','DEF'], flex:['RB','WR','TE'], def:'DEF', upload:'QB,RB,RB,WR,WR,WR,TE,FLEX,DEF'}
  };
  // contest format: 'classic' (9 positional slots) or 'sg' (single game: N flex slots, one MVP/Captain worth SG.mult points;
  // both DraftKings (Captain) and FanDuel (MVP) charge 1.5x salary for that slot; the player lists carry it: DK as separate CPT rows, FD as an 'MVP 1.5x Salary' column)
  var fmt = 'classic', SG = {n:6, mult:1.5, smult:{dk:1.5, fd:1.5}, game:''}, mvp = null, UNIT_SG = 100;
  try { var _f = JSON.parse(localStorage.getItem('bs_dfs_fmt') || 'null'); if(_f){ fmt = _f.fmt === 'sg' ? 'sg' : 'classic'; if(_f.sg){ SG.n = +_f.sg.n || 6; SG.mult = +_f.sg.mult || 1.5; SG.smult = Object.assign(SG.smult, _f.sg.smult || {}); SG.game = _f.sg.game || ''; } } } catch(e){}
  function isSG(){ return fmt === 'sg'; }
  function mvpLabel(){ return site === 'dk' ? 'CPT' : 'MVP'; }
  function saveFmt(){ try { localStorage.setItem('bs_dfs_fmt', JSON.stringify({fmt:fmt, sg:SG})); } catch(e){} }
  var ALIAS = {JAC:'JAX', LAR:'LA', WSH:'WAS', GNB:'GB', KAN:'KC', NWE:'NE', NOR:'NO', SFO:'SF', TAM:'TB', LVR:'LV', ARZ:'ARI', BLT:'BAL', CLV:'CLE', HST:'HOU'};
  var NICK = {ARI:'cardinals',ATL:'falcons',BAL:'ravens',BUF:'bills',CAR:'panthers',CHI:'bears',CIN:'bengals',CLE:'browns',DAL:'cowboys',DEN:'broncos',DET:'lions',GB:'packers',HOU:'texans',IND:'colts',JAX:'jaguars',KC:'chiefs',LV:'raiders',LAC:'chargers',LA:'rams',MIA:'dolphins',MIN:'vikings',NE:'patriots',NO:'saints',NYG:'giants',NYJ:'jets',PHI:'eagles',PIT:'steelers',SF:'49ers',SEA:'seahawks',TB:'buccaneers',TEN:'titans',WAS:'commanders'};
  function tc(t){ t = String(t||'').toUpperCase().trim(); return ALIAS[t] || t; }
  function norm(s){ return String(s||'').replace(/\./g,'').replace(/\s+(jr|sr|ii|iii|iv|v)$/i,'').replace(/[’']/g,"'").replace(/\s+/g,' ').trim().toLowerCase(); }
  function ncdf(z){ var t = 1/(1+0.2316419*Math.abs(z)); var d = 0.3989423*Math.exp(-z*z/2); var p = d*t*(0.3193815+t*(-0.3565638+t*(1.781478+t*(-1.821256+t*1.330274)))); return z > 0 ? 1-p : p; }
  function pOver(mean, thr, sdf, sdmin){ if(!mean) return 0; var sd = Math.max(sdmin, sdf*mean); return 1 - ncdf((thr - mean)/sd); }
  function score(p, site){
    if(p.p === 'DEF' || p.p === 'K') return p.fp || 0;
    var s = 0.04*p.py + 4*p.ptd - 1*p.int + 0.1*p.ry + 6*p.rtd + 0.1*p.rcy + 6*p.rctd;
    if(site === 'dk'){ s += 1*p.rec; s += 3*pOver(p.py,300,0.3,35) + 3*pOver(p.ry,100,0.5,22) + 3*pOver(p.rcy,100,0.5,22); }
    else { s += 0.5*p.rec; }
    return Math.round(s*100)/100;
  }
  // ---- state ----
  var site = 'dk', SAL = {}, SRC = null, lineup = [], locks = {}, excl = {}, sortKey = 'val', sortDir = -1, shown = 60, alts = [];
  try { site = localStorage.getItem('bs_dfs_site') || 'dk'; } catch(e){}
  function key(p){ return p.p + '|' + norm(p.n); }
  function luKey(){ return 'bs_dfs_lu_' + site + (isSG() ? '_sg' : ''); }
  function loadLu(){ try { var l = JSON.parse(localStorage.getItem(luKey()) || 'null'); var ok = l && l.week === D.week; lineup = ok ? l.lu : []; locks = (ok && l.locks) || {}; excl = (ok && l.excl) || {}; mvp = (ok && l.mvp) || null; } catch(e){ lineup = []; locks = {}; excl = {}; mvp = null; } }
  function load(){
    try { var s = JSON.parse(localStorage.getItem('bs_dfs_sal_' + site) || 'null'); if(s && s.week === D.week){ SAL = s.map; SRC = s.src; } else { SAL = {}; SRC = null; } } catch(e){ SAL = {}; SRC = null; }
    // DraftKings: salaries come pre-loaded from the site build (main classic slate) unless this viewer loaded their own list
    if(site === 'dk' && D.dk && D.dk.csv && (!Object.keys(SAL).length || (SRC && SRC.indexOf('loaded automatically') >= 0))){
      var ra = importCSV(D.dk.csv); if(!ra.err){ SAL = ra.map; SRC = 'DraftKings ' + (D.dk.slate || 'main slate') + ' salaries loaded automatically, ' + ra.n + ' players' + (D.dk.upd ? ' (pulled ' + D.dk.upd + ')' : ''); } }
    applyShared();
    loadLu();
  }
  // ---- shared salaries (owner 10/30): DraftKings pulled every 3 hours by the Supabase function "slip-alerts" (mode dk), FanDuel shared
  // from the owner's own upload - both in Supabase public.dfs_salaries (site, week). A viewer's own loaded list always wins.
  var SHARED = {}, ADMIN = false, LASTCSV = null, LASTSITE = null;
  function applyShared(){ var s = SHARED[site]; if(!s || !s.csv) return false;
    var own = Object.keys(SAL).length && !(SRC && SRC.indexOf('loaded automatically') >= 0); if(own) return false;
    var ra = importCSV(s.csv); if(ra.err) return false;
    SAL = ra.map; SRC = (site === 'dk' ? 'DraftKings ' : 'FanDuel ') + (s.slate || 'main slate') + ' salaries loaded automatically, ' + ra.n + ' players' + (s.updated_at ? ' (updated ' + new Date(s.updated_at).toLocaleString([], {weekday: 'short', hour: 'numeric', minute: '2-digit'}) + ')' : ''); return true; }
  function sbc(){ var C = window.__BS_ACCOUNT || {}; if(window.bsAccount && window.bsAccount.client) return window.bsAccount.client; return (window.supabase && C.url) ? window.supabase.createClient(C.url, C.key) : null; }
  (function fetchShared(tries){ var c = sbc(); if(!c){ if(tries < 60) setTimeout(function(){ fetchShared(tries + 1); }, 150); return; }
    c.from('dfs_salaries').select('site,week,slate,csv,players,updated_at').eq('week', D.week).then(function(r){ if(r.error || !r.data) return;
      r.data.forEach(function(x){ SHARED[x.site] = x; }); if(applyShared()){ save(); renderAll(); } });
    function adm(){ var u = window.bsAccount && window.bsAccount.user; if(!u){ ADMIN = false; showShare(); return; } c.rpc('bs_is_admin').then(function(r){ ADMIN = !!(r && r.data === true); showShare(); }); }
    document.addEventListener('bs-account', adm); adm(); })(0);
  function showShare(){ var b = document.getElementById('shareSal'); if(!b) return; b.hidden = !(ADMIN && LASTCSV && LASTSITE === site); b.textContent = 'Share these ' + (site === 'dk' ? 'DraftKings' : 'FanDuel') + ' salaries with everyone'; }
  function save(){ try { localStorage.setItem('bs_dfs_site', site); localStorage.setItem('bs_dfs_sal_' + site, JSON.stringify({week:D.week, map:SAL, src:SRC})); localStorage.setItem(luKey(), JSON.stringify({week:D.week, lu:lineup, locks:locks, excl:excl, mvp:mvp})); } catch(e){} saveFmt(); }
  // ---- CSV ----
  function parseCSV(text){
    var rows = [], row = [], cur = '', q = false;
    for(var i = 0; i < text.length; i++){ var c = text[i];
      if(q){ if(c === '"'){ if(text[i+1] === '"'){ cur += '"'; i++; } else q = false; } else cur += c; }
      else if(c === '"') q = true; else if(c === ','){ row.push(cur); cur = ''; } else if(c === '\n' || c === '\r'){ if(c === '\r' && text[i+1] === '\n') i++; row.push(cur); rows.push(row); row = []; cur = ''; } else cur += c; }
    if(cur.length || row.length){ row.push(cur); rows.push(row); }
    return rows.filter(function(r){ return r.length > 1 && r.join('').trim(); });
  }
  function importCSV(text){
    var rows = parseCSV(text); if(!rows.length) return {err:'Nothing to read - paste the whole CSV, header row included.'};
    // find the header row (DK sometimes exports instructions above it)
    var hi = -1, H = null;
    for(var i = 0; i < Math.min(rows.length, 12); i++){ var h = rows[i].map(function(x){ return x.trim().toLowerCase(); }); if(h.indexOf('salary') >= 0 && (h.indexOf('position') >= 0)){ hi = i; H = h; break; } }
    if(hi < 0) return {err:'That does not look like a DraftKings or FanDuel player list (no Position + Salary columns).'};
    var isFD = H.indexOf('nickname') >= 0, isDK = H.indexOf('roster position') >= 0 || H.indexOf('name + id') >= 0;
    var ix = function(n){ return H.indexOf(n); };
    var map = {}, n = 0, unmatched = [], byLast = {}, gameset = {}, sgSeen = false, irp = H.indexOf('roster position');
    P.forEach(function(p){ var ln = norm(p.n).split(' ').pop(); (byLast[p.p + '|' + ln + '|' + p.t] = byLast[p.p + '|' + ln + '|' + p.t] || []).push(p); });
    for(var r = hi + 1; r < rows.length; r++){ var x = rows[r]; if(x.length < H.length - 2) continue;
      var pos, name, id, sal, team, opp, game;
      var inj = ix('injury indicator') >= 0 ? String(x[ix('injury indicator')] || '').toUpperCase().trim() : '';
      if(isFD){ pos = (x[ix('position')]||'').toUpperCase(); name = x[ix('nickname')]; id = x[ix('id')]; sal = +x[ix('salary')]; team = tc(x[ix('team')]); opp = tc(x[ix('opponent')]); game = x[ix('game')]; if(pos === 'D') pos = 'DEF'; }
      else { pos = (x[ix('position')]||'').toUpperCase(); name = x[ix('name')]; id = x[ix('id')]; sal = +x[ix('salary')]; team = tc(x[ix('teamabbrev')]); game = x[ix('game info')]||''; var m = /([A-Z]{2,3})@([A-Z]{2,3})/.exec(game); opp = m ? (tc(m[1]) === team ? tc(m[2]) : tc(m[1])) : ''; if(pos === 'DST') pos = 'DEF'; }
      if(!sal || !pos) continue;
      var rp = irp >= 0 ? String(x[irp] || '').toUpperCase().trim() : '';
      var isCpt = rp === 'CPT' || rp === 'CAPTAIN' || rp === 'MVP';
      var imv = H.indexOf('mvp 1.5x salary'); if(imv < 0) imv = H.findIndex(function(c){ return /mvp|captain|cpt/.test(c) && /salary/.test(c); });
      var mvpSal = imv >= 0 ? +x[imv] : 0;   // FanDuel single game: MVP salary column on the same row (same player ID)   // DraftKings Showdown lists every player twice: CPT (1.5x salary, own ID) and FLEX
      var target = null;
      if(pos === 'DEF'){ var tcode = team || Object.keys(NICK).filter(function(k){ return norm(name).indexOf(NICK[k]) >= 0; })[0]; if(!tcode) continue; target = P.filter(function(p){ return p.p === 'DEF' && (p.t === tcode || tc(p.t) === tcode); })[0]; }
      else if(['QB','RB','WR','TE','K'].indexOf(pos) >= 0){
        target = P.filter(function(p){ return p.p === pos && norm(p.n) === norm(name); })[0];
        if(!target){ var cands = byLast[pos + '|' + norm(name).split(' ').pop() + '|' + team] || []; if(cands.length === 1) target = cands[0]; }
      } else continue;
      if(team && opp) gameset[[team, opp].sort().join('-')] = 1;
      if(!target){ if(!isCpt) unmatched.push(name + (team ? ' ' + team : '') + ' (' + pos + ')'); continue; }
      var kk = key(target);
      if(isCpt){ (map[kk] = map[kk] || {}).cpt = {sal:sal, id:id}; sgSeen = true; }
      else { map[kk] = Object.assign(map[kk] || {}, {sal:sal, id:id, team:team, opp:opp, inj:inj}); if(mvpSal > 0){ map[kk].cpt = {sal:mvpSal, id:id}; sgSeen = true; } n++; }
    }
    if(!n) return {err:'Read the file but matched nobody to the model - is this a classic NFL slate for this week?'};
    var glist = Object.keys(gameset);
    return {map:map, n:n, unmatched:unmatched, sg:sgSeen || (glist.length === 1 && n <= 80), games:glist, src:(isFD ? 'FanDuel' : isDK ? 'DraftKings' : 'CSV') + (sgSeen || glist.length === 1 ? ' single-game' : '') + ' player list, ' + n + ' players, loaded ' + new Date().toLocaleString()};
  }
  // ---- helpers ----
  // m = true -> the player in the MVP/Captain slot: SG.mult x points; salary = his CPT row from the file if there is one, else salary x SG.smult
  function sal(p, m){ var s = SAL[key(p)]; if(!s) return null; if(m){ if(s.cpt && s.cpt.sal) return s.cpt.sal; return s.sal ? Math.round(s.sal * (SG.smult[site] || 1) / 100) * 100 : null; } return s.sal || null; }
  function pts(p, m){ return score(p, site) * (m ? SG.mult : 1); }
  function hasSal(){ return Object.keys(SAL).length > 0; }
  // the site's own injury flag from the player list (FanDuel has one): O / IR / NA / PUP / SUSP = never optimized in; Q / D shown as tags
  function siteInj(p){ var s = SAL[key(p)]; return s && s.inj ? s.inj : ''; }
  function siteOut(p){ return /^(O|OUT|IR|NA|PUP|SUSP|SSPD)$/.test(siteInj(p)); }
  function isM(k){ return isSG() && k === mvp; }
  function used(){ return lineup.reduce(function(a, k){ var p = byKey[k]; var s = p ? sal(p, isM(k)) : 0; return a + (s || 0); }, 0); }
  function total(){ return lineup.reduce(function(a, k){ var p = byKey[k]; return a + (p ? pts(p, isM(k)) : 0); }, 0); }
  function capNow(){ return SITES[site].cap; }
  var byKey = {}; P.forEach(function(p){ byKey[key(p)] = p; });
  function slotsFor(sel){ // assign selected keys to slots; returns [{slot, key|null}]
    if(isSG()){ var o2 = [{slot:'MVP', key:null}], r2 = sel.slice(); for(var i = 1; i < SG.n; i++) o2.push({slot:'FLEX', key:null});
      if(mvp && r2.indexOf(mvp) >= 0){ o2[0].key = mvp; r2.splice(r2.indexOf(mvp), 1); }
      for(var j = 1; j < SG.n && r2.length; j++) o2[j].key = r2.shift();
      if(!o2[0].key && r2.length) o2[0].key = r2.shift();
      return {slots:o2, extra:r2}; }
    var S = SITES[site], out = S.slots.map(function(s){ return {slot:s, key:null}; }), rem = sel.slice();
    S.slots.forEach(function(s, i){ if(s === 'FLEX') return; var j = -1; for(var k = 0; k < rem.length; k++){ var p = byKey[rem[k]]; if(p && (p.p === s || (s === S.def && p.p === 'DEF'))){ j = k; break; } } if(j >= 0){ out[i].key = rem[j]; rem.splice(j, 1); } });
    out.forEach(function(o){ if(o.slot === 'FLEX' && !o.key){ var j = -1; for(var k = 0; k < rem.length; k++){ var p = byKey[rem[k]]; if(p && S.flex.indexOf(p.p) >= 0){ j = k; break; } } if(j >= 0){ o.key = rem[j]; rem.splice(j, 1); } } });
    return {slots:out, extra:rem};
  }
  function canAdd(p){ var t = slotsFor(lineup.concat([key(p)])); return t.extra.length === 0; }
  function fixMvp(){ if(!isSG()) return; var k = slotsFor(lineup).slots[0].key; mvp = k || (mvp && lineup.indexOf(mvp) >= 0 ? mvp : null); }
  // ---- optimizer: exact salary-cap solve (per-position cardinality knapsacks combined by max-plus convolution), FLEX by enumeration ----
  function exactSolve(groups, capU){ // groups: [{k, players:[{s(units), v, ref}]}]; returns {v, picks:[ref...]} or null
    var F = new Float64Array(capU + 1).fill(-1e9), Farg = []; F[0] = 0; var Gs = [];
    for(var gi = 0; gi < groups.length; gi++){ var g = groups[gi], k = g.k; if(!k){ Gs.push(null); Farg.push(null); continue; }
      var ps = g.players; if(ps.length < k) return null;
      var layers = []; var cur = []; for(var j = 0; j <= k; j++){ cur.push(new Float64Array(capU + 1).fill(-1e9)); } cur[0].fill(0);
      for(var i = 0; i < ps.length; i++){ var p = ps[i]; var nxt = cur.map(function(a){ return Float64Array.from(a); });
        for(var j = 1; j <= k; j++){ var prev = cur[j - 1], row = nxt[j]; for(var b = p.s; b <= capU; b++){ var cand = prev[b - p.s]; if(cand > -1e8 && cand + p.v > row[b]) row[b] = cand + p.v; } }
        layers.push(nxt); cur = nxt; }
      var G = cur[k]; // exactly k players, salary exactly b -> make it "at most b" by prefix max is NOT needed for combination (we combine exact sums then take best <= cap)
      Gs.push({G:G, layers:layers, ps:ps, k:k});
      var Fn = new Float64Array(capU + 1).fill(-1e9), arg = new Int32Array(capU + 1).fill(-1);
      for(var b2 = 0; b2 <= capU; b2++){ if(F[b2] < -1e8) continue; for(var x = 0; b2 + x <= capU; x++){ if(G[x] < -1e8) continue; var val = F[b2] + G[x]; if(val > Fn[b2 + x]){ Fn[b2 + x] = val; arg[b2 + x] = x; } } }
      F = Fn; Farg.push(arg); }
    var bestB = -1, bestV = -1e9; for(var b3 = 0; b3 <= capU; b3++){ if(F[b3] > bestV){ bestV = F[b3]; bestB = b3; } }
    if(bestB < 0) return null;
    var picks = [], b = bestB;
    for(var gi2 = groups.length - 1; gi2 >= 0; gi2--){ var gs = Gs[gi2]; if(!gs) continue; var x2 = Farg[gi2][b]; b -= x2;
      // reconstruct inside the group: walk layers backwards
      var j = gs.k, bb = x2;
      for(var i2 = gs.ps.length - 1; i2 >= 0 && j > 0; i2--){ var before = i2 > 0 ? gs.layers[i2 - 1][j][bb] : (j === 0 ? 0 : -1e9); var after = gs.layers[i2][j][bb];
        if(after > before + 1e-9 || (i2 === 0)){ picks.push(gs.ps[i2].ref); bb -= gs.ps[i2].s; j--; } } }
    return {v:bestV, picks:picks};
  }
  function optimize(fixedKeys, opts){
    var S = SITES[site], need = slotsFor(fixedKeys);
    if(need.extra.length) return null;
    var fixed = fixedKeys.map(function(k){ return byKey[k]; });
    var open = need.slots.filter(function(o){ return !o.key; }).map(function(o){ return o.slot; });
    if(!open.length) return (!hasSal() || fixed.reduce(function(a, p){ return a + (sal(p) || 0); }, 0) <= S.cap) ? fixedKeys.slice() : null;
    var pool = P.filter(function(p){ return p.act && !siteOut(p) && !excl[key(p)] && fixedKeys.indexOf(key(p)) < 0 && (!hasSal() || sal(p)) && (!opts.noQ || !p.q) && (!opts.game || p.t === opts.game.a || p.t === opts.game.b); })
      .map(function(p){ var q = Object.assign({}, p); q._pts = pts(p) * (opts.jit ? (1 + (Math.random() - 0.5) * 2 * opts.jit) : 1); q._sal = sal(p) || 0; return q; });
    fixed.forEach(function(p){ p._pts = pts(p); p._sal = sal(p) || 0; });
    var UNIT = 100, capU = hasSal() ? Math.floor((S.cap - fixed.reduce(function(a, p){ return a + p._sal; }, 0)) / UNIT) : 2000;
    if(capU < 0) return null;
    var teamOK = function(sel){ if(!opts.maxTeam) return true; var c = {}; for(var i = 0; i < sel.length; i++){ c[sel[i].t] = (c[sel[i].t] || 0) + 1; if(c[sel[i].t] > opts.maxTeam) return false; } return true; };
    var hasStack = function(sel){ var qb = sel.filter(function(p){ return p.p === 'QB'; })[0]; return !qb || sel.some(function(p){ return p.t === qb.t && (p.p === 'WR' || p.p === 'TE'); }); };
    var cnt = {}; open.forEach(function(s){ cnt[s] = (cnt[s] || 0) + 1; });
    var byPos = {}; ['QB','RB','WR','TE','DEF'].forEach(function(pos){ byPos[pos] = pool.filter(function(p){ return p.p === pos; }).sort(function(a, b){ return b._pts - a._pts; }); });
    var tops = {QB:12, RB:30, WR:36, TE:16, DEF:12};
    var mk = function(pos, k, extraFilter){ var all = byPos[pos].filter(extraFilter || function(){ return true; }); var pick = {}, ps = [];
      var add = function(p){ if(!pick[key(p)]){ pick[key(p)] = 1; ps.push(p); } };
      all.slice(0, tops[pos]).forEach(add);                                                                   // best projections
      if(hasSal()){ all.slice().sort(function(a, b){ return b._pts / Math.max(1, b._sal) - a._pts / Math.max(1, a._sal); }).slice(0, tops[pos]).forEach(add);   // best value
        all.slice().sort(function(a, b){ return a._sal - b._sal || b._pts - a._pts; }).slice(0, 8).forEach(add); }                                             // cheapest punts
      return {k:k, players:ps.map(function(p){ return {s:hasSal() ? Math.ceil(p._sal / UNIT) : 0, v:p._pts, ref:p}; })}; };
    var solveWith = function(filter){ var best = null;
      var flexOpts = cnt.FLEX ? S.flex : [null];
      flexOpts.forEach(function(fx){ var groups = ['QB','RB','WR','TE'].map(function(pos){ return mk(pos, (cnt[pos] || 0) + (fx === pos ? 1 : 0), filter); }); groups.push(mk('DEF', cnt[S.def] || 0, filter));
        var r = exactSolve(groups, capU); if(r && (!best || r.v > best.v)) best = r; });
      return best; };
    var finalize = function(r){ if(!r) return null; var sel = fixed.concat(r.picks); return teamOK(sel) ? sel : null; };
    var best = finalize(solveWith(null));
    if(opts.stack && best && !hasStack(best)){ // enumerate QB + pass-catcher pairs and take the best stacked lineup
      var qbs = fixed.some(function(p){ return p.p === 'QB'; }) ? fixed.filter(function(p){ return p.p === 'QB'; }) : byPos.QB.slice(0, 10), sb = null;
      qbs.forEach(function(qb){ var mates = pool.filter(function(p){ return p.t === qb.t && (p.p === 'WR' || p.p === 'TE'); }).sort(function(a, b){ return b._pts - a._pts; }).slice(0, 3);
        mates.forEach(function(m){ var fk = fixedKeys.slice(); if(fixedKeys.indexOf(key(qb)) < 0) fk.push(key(qb)); fk.push(key(m)); var sub = slotsFor(fk); if(sub.extra.length) return;
          var o2 = Object.assign({}, opts, {stack:false}); var r = optimize(fk, o2); if(!r) return; var sel = r.map(function(k){ return byKey[k]; }); var v = sel.reduce(function(a, p){ return a + pts(p); }, 0); var sv = sel.reduce(function(a, p){ return a + (sal(p) || 0); }, 0); if(hasSal() && sv > S.cap) return; if(!sb || v > sb.v) sb = {v:v, keys:r}; }); });
      if(sb && sb.v >= best.reduce(function(a, p){ return a + p._pts; }, 0) - 4) return sb.keys;
    }
    if(!best && opts.maxTeam){ // team cap violated: thin the worst offenders and retry a few times
      var tried = 0, banned = {}; while(tried++ < 6){ var r = solveWith(function(p){ return !banned[key(p)]; }); if(!r) break; var sel = fixed.concat(r.picks); if(teamOK(sel)) return sel.map(key);
        var c = {}; sel.forEach(function(p){ c[p.t] = (c[p.t] || 0) + 1; }); var t = Object.keys(c).filter(function(k){ return c[k] > opts.maxTeam; })[0]; var worst = sel.filter(function(p){ return p.t === t && fixed.indexOf(p) < 0; }).sort(function(a, b){ return a._pts - b._pts; })[0]; if(!worst) break; banned[key(worst)] = 1; }
      return null;
    }
    return best ? best.map(key) : null;
  }
  // ---- single-game optimizer: try each realistic MVP; the other N-1 slots are an exact knapsack under the cap left after his (MVP) salary;
  //      both teams must be represented (DraftKings/FanDuel rule) ----
  function sgGroup(av, k){ var pick = {}, ps = []; var add = function(p){ if(!pick[p._k]){ pick[p._k] = 1; ps.push(p); } };
    av.slice().sort(function(a, b){ return b._pts - a._pts; }).slice(0, 40).forEach(add);
    if(hasSal()){ av.slice().sort(function(a, b){ return b._pts / Math.max(1, b._sal) - a._pts / Math.max(1, a._sal); }).slice(0, 30).forEach(add);
      av.slice().sort(function(a, b){ return a._sal - b._sal || b._pts - a._pts; }).slice(0, 8).forEach(add); }
    return {k:k, players:ps.map(function(p){ return {s:hasSal() ? Math.ceil(p._sal / UNIT_SG) : 0, v:p._pts, ref:p}; })}; }
  function optimizeSG(fixedKeys, fixedMvp, opts){
    var n = SG.n, cap = hasSal() ? capNow() : Infinity, g = SG.game; if(!g) return null;
    var ta = g.split('-')[0], tb = g.split('-')[1], inGame = function(p){ return p.t === ta || p.t === tb; };
    if(fixedKeys.length > n) return null;
    var J = function(){ return opts.jit ? (1 + (Math.random() - 0.5) * 2 * opts.jit) : 1; };
    var mk = function(p, j){ var q = Object.assign({}, p); q._pts = pts(p) * j; q._sal = sal(p) || 0; q._k = key(p); return q; };
    var fx = fixedKeys.map(function(k){ return mk(byKey[k], 1); });
    var pool = P.filter(function(p){ return p.act && !siteOut(p) && inGame(p) && !excl[key(p)] && fixedKeys.indexOf(key(p)) < 0 && (!hasSal() || sal(p)) && (!opts.noQ || !p.q); }).map(function(p){ return mk(p, J()); });
    var cands = fixedMvp ? fx.filter(function(p){ return p._k === fixedMvp; }) : fx.concat(pool.slice().sort(function(a, b){ return b._pts - a._pts; }).slice(0, 30));
    var both = function(sel){ var t = {}; sel.forEach(function(p){ t[p.t] = 1; }); return Object.keys(t).length >= 2; };
    var best = null;
    cands.forEach(function(c){
      var cSal = hasSal() ? sal(c, true) : 0; if(hasSal() && !cSal) return;
      var others = fx.filter(function(p){ return p._k !== c._k; }), r = n - 1 - others.length; if(r < 0) return;
      var base = c._pts * SG.mult + others.reduce(function(a, p){ return a + p._pts; }, 0);
      var used0 = cSal + others.reduce(function(a, p){ return a + p._sal; }, 0); if(hasSal() && used0 > cap) return;
      var capU = hasSal() ? Math.floor((cap - used0) / UNIT_SG) : 2000;
      var avail = pool.filter(function(p){ return p._k !== c._k; });
      var solve = function(forced){ var rr = r - (forced ? 1 : 0), av = forced ? avail.filter(function(p){ return p._k !== forced._k; }) : avail;
        var cu = capU - (forced && hasSal() ? Math.ceil(forced._sal / UNIT_SG) : 0); if(cu < 0 || rr < 0) return null;
        var picks = []; if(rr > 0){ var res = exactSolve([sgGroup(av, rr)], cu); if(!res) return null; picks = res.picks; }
        if(forced) picks = picks.concat([forced]);
        return {v:base + picks.reduce(function(a, p){ return a + p._pts; }, 0), sel:[c].concat(others, picks)}; };
      var res = solve(null);
      if(res && !both(res.sel)){ var other = res.sel[0].t === ta ? tb : ta, bb = null;
        avail.filter(function(p){ return p.t === other; }).sort(function(a, b){ return b._pts - a._pts; }).slice(0, 8).forEach(function(f){ var x = solve(f); if(x && both(x.sel) && (!bb || x.v > bb.v)) bb = x; });
        res = bb; }
      if(res && (!best || res.v > best.v)) best = {v:res.v, sel:res.sel, mvp:c._k};
    });
    return best ? {keys:best.sel.map(function(p){ return p._k; }), mvp:best.mvp} : null;
  }
  // ---- render ----
  function tags(p){ var t = '', si = siteInj(p); if(!p.act) t += '<span class="tag out">' + (p.av || 'OUT') + '</span>'; else if(siteOut(p)) t += '<span class="tag out" title="' + SITES[site].name + ' lists him ' + si + ' - left out of Optimize">' + (site === 'dk' ? 'DK' : 'FD') + ' ' + si + '</span>'; else if(p.q || si === 'Q' || si === 'D') t += '<span class="tag q"' + (si ? ' title="' + SITES[site].name + ' lists him ' + si + '"' : '') + '>' + (si === 'D' ? 'D' : 'Q') + '</span>'; if(p.sd) t += '<span class="tag sd" title="snap share down: last 2 ' + p.sd[0] + '% vs season ' + p.sd[1] + '%; projection trimmed ' + p.sd[2] + '%">snaps ↓</span>'; if(p.ftd && p.ftd >= 0.08) t += '<span class="tag ftd" title="model chance of the game\'s first touchdown">1st TD ' + Math.round(p.ftd*100) + '%</span>'; return t; }
  function renderList(){
    var fPos = $('#fPos').value, fGame = $('#fGame').value, q = $('#fQ').value.trim().toLowerCase(), onlyAct = $('#fAct').checked, onlySal = $('#fSal').checked;
    var rows = P.filter(function(p){ if(!isSG() && p.p === 'K') return false; if(isSG() && SG.game && p.t !== SG.game.split('-')[0] && p.t !== SG.game.split('-')[1]) return false; if(fPos !== 'all' && !(fPos === 'FLEX' ? SITES[site].flex.indexOf(p.p) >= 0 : p.p === fPos)) return false; if(fGame !== 'all' && p.t !== fGame.split('-')[0] && p.t !== fGame.split('-')[1]) return false; if(q && (p.n + ' ' + p.t).toLowerCase().indexOf(q) < 0) return false; if(onlyAct && (!p.act || siteOut(p))) return false; if(onlySal && hasSal() && !sal(p)) return false; return true; });
    rows.forEach(function(p){ p._pts = pts(p); p._sal = sal(p); p._val = p._sal ? p._pts / (p._sal / 1000) : null; });
    rows.sort(function(a, b){ var ka = a[{val:'_val', pts:'_pts', sal:'_sal', name:'n'}[sortKey]], kb = b[{val:'_val', pts:'_pts', sal:'_sal', name:'n'}[sortKey]]; if(ka == null && kb == null) return 0; if(ka == null) return 1; if(kb == null) return -1; return (ka < kb ? -1 : ka > kb ? 1 : 0) * sortDir; });
    var inL = {}; lineup.forEach(function(k){ inL[k] = 1; });
    $('#count').textContent = rows.length + ' players';
    $('#plist').innerHTML = rows.slice(0, shown).map(function(p){ var k = key(p); var cls = (inL[k] ? 'inl ' : '') + (excl[k] ? 'ex ' : '') + (!p.act || siteOut(p) ? 'na' : '');
      var vcls = p._val == null ? '' : (p._val >= 3 ? '' : 'lo');
      return '<tr class="' + cls + '" data-k="' + k + '"><td class="l"><span class="nm">' + p.n + '</span><span class="pos">' + p.p + '</span>' + tags(p) + '<span class="mt">' + p.t + ' ' + (p.o ? 'vs ' + p.o : '') + (p.k ? ' · ' + p.k : '') + ((p.or || p.dr) ? ' · matchup ' + (p.or ? p.t + ' #' + p.or : p.t) + ' vs ' + (p.dr ? p.o + ' #' + p.dr : p.o) : '') + '</span></td>' +
        '<td class="sal"><input type="number" inputmode="numeric" value="' + (p._sal || '') + '" placeholder="—" aria-label="salary"></td>' +
        '<td><b>' + p._pts.toFixed(1) + '</b>' + (isSG() ? '<span class="mt">' + mvpLabel() + ' ' + (p._pts * SG.mult).toFixed(1) + (sal(p, true) ? ' · $' + sal(p, true).toLocaleString() : '') + '</span>' : '') + '</td><td class="val ' + vcls + '">' + (p._val == null ? '—' : '<b>' + p._val.toFixed(2) + '</b>') + '</td>' +
        '<td class="act">' + (inL[k] ? '<button class="rm">Remove</button>' : '<button class="add"' + (!p.act ? ' title="listed out / inactive"' : '') + '>Add</button>') + ' <button class="x' + (excl[k] ? ' on' : '') + '" title="exclude from Optimize">✕</button></td></tr>'; }).join('');
    $('#more').textContent = rows.length > shown ? 'Show ' + Math.min(60, rows.length - shown) + ' more' : ''; $('#more').hidden = rows.length <= shown;
    $$('#plist th').forEach(function(th){ th.classList.toggle('on', th.dataset.s === sortKey); });
  }
  function renderLineup(){
    fixMvp();
    var S = SITES[site], t = slotsFor(lineup), u = used(), cap = S.cap, left = cap - u, empty = t.slots.filter(function(o){ return !o.key; }).length, NS = t.slots.length;
    $('#slots').innerHTML = t.slots.map(function(o){ var p = o.key ? byKey[o.key] : null, m = o.slot === 'MVP';
      var lab = m ? mvpLabel() + ' <em>' + SG.mult + '×</em>' : o.slot;
      return '<li' + (m ? ' class="mvp"' : '') + '><span class="sl">' + lab + '</span>' + (p ? '<span class="who"><b>' + (p.p === 'DEF' ? p.n + ' D/ST' : p.n) + '</b> <small>' + p.p + ' ' + p.t + (p.o ? ' vs ' + p.o : '') + '</small>' + tags(p) + '</span><span class="pts">' + pts(p, m).toFixed(1) + (sal(p, m) ? '<small>$' + sal(p, m).toLocaleString() + '</small>' : '') + '</span><span class="ops">' + (isSG() && !m ? '<button class="mv" data-k="' + o.key + '" title="make him the ' + mvpLabel() + ' (' + SG.mult + 'x points' + ((SG.smult[site] || 1) > 1 ? ', ' + SG.smult[site] + 'x salary' : '') + ')">★</button>' : '') + '<button class="lk' + (locks[o.key] ? ' on' : '') + '" data-k="' + o.key + '" title="keep this player when optimizing">' + (locks[o.key] ? 'Locked' : 'Lock') + '</button><button class="rm" data-k="' + o.key + '">✕</button></span>' : '<span class="who empty">' + (m ? 'empty - the optimizer picks the best ' + mvpLabel() : 'empty') + '</span><span class="pts"></span><span class="ops"></span>') + '</li>'; }).join('');
    var pct = hasSal() ? Math.min(100, u / cap * 100) : 0;
    $('#capbar').style.width = pct + '%'; $('#capbar').classList.toggle('over', u > cap);
    $('#capUsed').textContent = hasSal() ? '$' + u.toLocaleString() : 'no salaries loaded'; $('#capLeft').textContent = hasSal() ? (left >= 0 ? '$' + left.toLocaleString() + ' left' : '$' + (-left).toLocaleString() + ' OVER') : '';
    $('#capAvg').textContent = hasSal() && empty ? '$' + Math.round(left / empty).toLocaleString() + ' per open slot' : '';
    $('#totPts').textContent = total().toFixed(1); $('#totSal').textContent = hasSal() ? '$' + u.toLocaleString() : '—'; $('#totN').textContent = (NS - empty) + '/' + NS;
    $('#exportBtn').disabled = empty > 0 || !hasSal() || !lineup.every(function(k){ return SAL[k] && (isM(k) && site === 'dk' ? SAL[k].cpt && SAL[k].cpt.id : SAL[k].id); });
    $('#copyBtn').disabled = lineup.length === 0;
    var mb = $('#mbarTxt'); if(mb) mb.textContent = 'Lineup ' + (NS - empty) + '/' + NS + ' · ' + total().toFixed(1) + ' pts' + (hasSal() ? ' · ' + (left >= 0 ? '$' + left.toLocaleString() + ' left' : 'OVER CAP') : '');
    $('#optBtn').textContent = empty === NS ? 'Build the best lineup' : (empty ? 'Fill the ' + empty + ' open slot' + (empty > 1 ? 's' : '') : 'Re-optimize around locks');
  }
  function renderAlts(){ $('#alts').innerHTML = alts.length ? '<h3>Other strong builds</h3>' + alts.map(function(a, i){ var keys = Array.isArray(a) ? a : a.keys, am = Array.isArray(a) ? null : a.mvp;
      var tp = keys.reduce(function(x, k){ return x + pts(byKey[k], k === am); }, 0), ts = keys.reduce(function(x, k){ return x + (sal(byKey[k], k === am) || 0); }, 0);
      var names = (am ? [mvpLabel() + ' ' + byKey[am].n] : []).concat(keys.filter(function(k){ return k !== am; }).map(function(k){ return byKey[k].n; }));
      return '<div class="alt"><button data-i="' + i + '">Load</button><b>' + tp.toFixed(1) + '</b> pts' + (hasSal() ? ' · $' + ts.toLocaleString() : '') + '<br>' + names.join(', ') + '</div>'; }).join('') : ''; }
  function renderSrc(){ $('#srcStat').innerHTML = SRC ? '<b>' + SRC + '</b> · scored as ' + SITES[site].name : 'No salaries loaded for ' + SITES[site].name + ' - the builder works on projections alone until you load a player list.'; $('#siteName').textContent = SITES[site].name + (isSG() ? ' · single game' : ''); $('#capLabel').textContent = '$' + SITES[site].cap.toLocaleString() + ' cap'; applyFmtUI(); }
  function applyFmtUI(){
    $$('#fmtSeg button').forEach(function(x){ x.classList.toggle('on', x.dataset.v === fmt); });
    $('#optsClassic').hidden = isSG(); $('#optsSG').hidden = !isSG();
    $('#sgGame').value = SG.game || ''; $('#sgN').value = String(SG.n); $('#sgMult').value = String(SG.mult); $('#sgSal').value = String(SG.smult[site] || 1);
    $('#sgHint').textContent = site === 'dk' ? 'DraftKings Showdown: 6 slots, Captain scores 1.5x and costs 1.5x salary, K and D/ST allowed, both teams required.' : 'FanDuel single game: MVP scores 1.5x and costs 1.5x salary (the MVP 1.5x Salary column in FanDuel\'s player list), both teams required.';
    $('#fGame').disabled = isSG(); if(isSG()) $('#fGame').value = 'all';
    var kopt = $('#fPos option[value="K"]'); if(kopt) kopt.hidden = !isSG();
  }
  function renderAll(){ renderSrc(); renderList(); renderLineup(); renderAlts(); if (typeof renderSavedLus === 'function') renderSavedLus(); }
  // ---- events ----
  $$('#siteSeg button').forEach(function(b){ b.addEventListener('click', function(){ site = b.dataset.v; showShare(); $$('#siteSeg button').forEach(function(x){ x.classList.toggle('on', x === b); }); load(); alts = []; renderAll(); save(); }); });
  $$('#siteSeg button').forEach(function(x){ x.classList.toggle('on', x.dataset.v === site); });
  $$('#fmtSeg button').forEach(function(b){ b.addEventListener('click', function(){ if(fmt === b.dataset.v) return; save(); fmt = b.dataset.v; saveFmt(); loadLu(); alts = []; renderAll(); }); });
  ['sgN','sgMult','sgSal'].forEach(function(id){ $('#' + id).addEventListener('change', function(){ SG.n = +$('#sgN').value; SG.mult = +$('#sgMult').value; SG.smult[site] = +$('#sgSal').value;
    if(lineup.length > SG.n){ lineup = lineup.slice(0, SG.n); } alts = []; save(); renderAll(); }); });
  $('#sgGame').addEventListener('change', function(){ SG.game = this.value; var ta = SG.game.split('-')[0], tb = SG.game.split('-')[1];
    lineup = lineup.filter(function(k){ var p = byKey[k]; return p && (p.t === ta || p.t === tb); }); if(mvp && lineup.indexOf(mvp) < 0) mvp = null; alts = []; shown = 60; save(); renderAll(); });
  $('#csvBtn').addEventListener('click', function(){ var txt = $('#csv').value, r = importCSV(txt); if(!r.err){ LASTCSV = txt; LASTSITE = site; setTimeout(showShare, 0); } var m = $('#srcMsg'); m.hidden = false; if(r.err){ m.className = 'msg err'; m.textContent = r.err; return; } SAL = r.map; SRC = r.src;
    if(r.sg && r.games.length === 1){ if(!isSG()){ save(); fmt = 'sg'; loadLu(); } SG.game = r.games[0]; if(Object.keys(r.map).some(function(k){ return r.map[k].cpt; })) SG.smult[site] = 1.5; lineup = lineup.filter(function(k){ var p = byKey[k]; return p && [p.t, p.o].sort().join('-') === SG.game; }); }
    m.className = 'msg ok'; m.textContent = 'Loaded ' + r.n + ' salaries.' + (r.unmatched.length ? ' Not in the model (' + r.unmatched.length + '): ' + r.unmatched.slice(0, 12).join(', ') + (r.unmatched.length > 12 ? '…' : '') : ''); $('#csv').value = ''; save(); alts = []; renderAll(); });
  $('#csvFile').addEventListener('change', function(){ var f = this.files[0]; if(!f) return; var rd = new FileReader(); rd.onload = function(){ $('#csv').value = rd.result; $('#csvBtn').click(); }; rd.readAsText(f); });
  // drag a player-list CSV straight onto the salaries box (or anywhere on the page)
  (function(){ var box = $('.dfs .src'), n = 0; function has(ev){ return ev.dataTransfer && Array.prototype.indexOf.call(ev.dataTransfer.types || [], 'Files') >= 0; }
    document.addEventListener('dragenter', function(ev){ if(!has(ev)) return; ev.preventDefault(); n++; box.classList.add('drop'); });
    document.addEventListener('dragover', function(ev){ if(!has(ev)) return; ev.preventDefault(); ev.dataTransfer.dropEffect = 'copy'; });
    document.addEventListener('dragleave', function(ev){ if(!has(ev)) return; n = Math.max(0, n - 1); if(!n) box.classList.remove('drop'); });
    document.addEventListener('drop', function(ev){ if(!has(ev)) return; ev.preventDefault(); n = 0; box.classList.remove('drop'); var f = ev.dataTransfer.files[0]; if(!f) return;
      if(!/\.csv$|\.txt$/i.test(f.name) && f.type.indexOf('csv') < 0 && f.type.indexOf('text') < 0){ var m = $('#srcMsg'); m.hidden = false; m.className = 'msg err'; m.textContent = 'That is not a CSV - drop the player list file DraftKings or FanDuel gave you.'; return; }
      var rd = new FileReader(); rd.onload = function(){ $('#csv').value = rd.result; $('#csvBtn').click(); }; rd.readAsText(f); });
  })();
  $('#clearSal').addEventListener('click', function(){ SAL = {}; SRC = null; LASTCSV = null; showShare(); save(); renderAll(); });
  $('#shareSal').addEventListener('click', function(){ var c = sbc(), b = this, m = $('#srcMsg'); if(!c || !LASTCSV || LASTSITE !== site) return; b.disabled = true;
    var ra = importCSV(LASTCSV), row = {site: site, week: D.week, slate: (ra.sg && ra.games && ra.games.length === 1) ? ra.games[0].replace('-', ' · ') + ' single game' : 'main slate', csv: LASTCSV, players: ra.n, updated_at: new Date().toISOString()};
    c.from('dfs_salaries').upsert(row, {onConflict: 'site,week'}).then(function(r){ b.disabled = false; m.hidden = false;
      if(r.error){ m.className = 'msg err'; m.textContent = 'Not shared: ' + r.error.message; return; }
      SHARED[site] = row; m.className = 'msg ok'; m.textContent = 'Shared - everyone opening the ' + (site === 'dk' ? 'DraftKings' : 'FanDuel') + ' tab this week now gets these ' + ra.n + ' salaries automatically (unless they load their own list).'; LASTCSV = null; showShare(); }); });
  ['fPos','fGame','fQ','fAct','fSal'].forEach(function(id){ $('#' + id).addEventListener('input', function(){ shown = 60; renderList(); }); $('#' + id).addEventListener('change', function(){ shown = 60; renderList(); }); });
  $('#more').addEventListener('click', function(){ shown += 60; renderList(); });
  $$('#plist th[data-s]').forEach(function(th){ th.addEventListener('click', function(){ if(sortKey === th.dataset.s) sortDir = -sortDir; else { sortKey = th.dataset.s; sortDir = th.dataset.s === 'name' ? 1 : -1; } renderList(); }); });
  $('#plist').addEventListener('click', function(ev){ var tr = ev.target.closest('tr'); if(!tr) return; var k = tr.dataset.k, p = byKey[k];
    if(ev.target.classList.contains('add')){ if(lineup.indexOf(k) >= 0) return;
      if(isSG()){ var g2 = [p.t, p.o].sort().join('-'); if(!SG.game){ SG.game = g2; } else if(g2 !== SG.game){ flash('Single-game lineups use one game (' + SG.game.replace('-', ' · ') + '). Change the game first.'); return; } }
      if(!canAdd(p)){ flash(isSG() ? 'All ' + SG.n + ' slots are full - remove someone first.' : 'No open slot for a ' + p.p + ' - remove someone first.'); return; } lineup.push(k); delete excl[k]; save(); renderAll(); }
    else if(ev.target.classList.contains('rm')){ lineup = lineup.filter(function(x){ return x !== k; }); delete locks[k]; save(); renderList(); renderLineup(); }
    else if(ev.target.classList.contains('x')){ if(excl[k]) delete excl[k]; else { excl[k] = 1; lineup = lineup.filter(function(x){ return x !== k; }); delete locks[k]; } save(); renderList(); renderLineup(); } });
  $('#plist').addEventListener('change', function(ev){ if(!ev.target.matches('td.sal input')) return; var k = ev.target.closest('tr').dataset.k; var v = +ev.target.value; if(v > 0){ SAL[k] = Object.assign(SAL[k] || {}, {sal:v}); if(!SRC) SRC = 'salaries typed by hand'; } else delete SAL[k]; save(); renderList(); renderLineup(); });
  $('#slots').addEventListener('click', function(ev){ var b = ev.target.closest('button'); if(!b) return; var k = b.dataset.k; if(b.classList.contains('mv')){ mvp = k; } else if(b.classList.contains('lk')){ if(locks[k]) delete locks[k]; else locks[k] = 1; } else { lineup = lineup.filter(function(x){ return x !== k; }); delete locks[k]; if(mvp === k) mvp = null; } save(); renderList(); renderLineup(); });
  $('#clearBtn').addEventListener('click', function(){ lineup = []; locks = {}; alts = []; mvp = null; save(); renderAll(); });
  // ---- saved lineups (bs_dfs_saved: [{id, name, site, sg, week, lu, mvp, locks, saved}]) - build several, compare, keep them ----
  function savedLus(){ try{ var a = JSON.parse(localStorage.getItem('bs_dfs_saved') || '[]'); return Array.isArray(a) ? a : []; }catch(e){ return []; } }
  function writeLus(a){ try{ localStorage.setItem('bs_dfs_saved', JSON.stringify(a)); }catch(e){} }
  function renderSavedLus(){ var box = $('#savedLus'); if(!box) return; var all = savedLus().filter(function(x){ return x.week === D.week; }), here = all.filter(function(x){ return x.site === site && !!x.sg === isSG(); });
    if(!all.length){ box.innerHTML = ''; return; }
    box.innerHTML = '<h3>Saved lineups <small style="font-weight:500;letter-spacing:0;text-transform:none">' + (window.bsAccount && window.bsAccount.user ? 'synced to your account' : 'in this browser - sign in to keep them on every device') + '</small></h3>' + (here.length ? here.map(function(x){ var keys = x.lu.filter(function(k){ return byKey[k]; });
        var tp = keys.reduce(function(a, k){ return a + pts(byKey[k], isSG() && k === x.mvp); }, 0), ts = keys.reduce(function(a, k){ return a + (sal(byKey[k], isSG() && k === x.mvp) || 0); }, 0);
        return '<div class="alt"><button data-lload="' + x.id + '">Load</button><button data-ldel="' + x.id + '" style="margin-left:4px">×</button> <b>' + esc(x.name) + '</b> · ' + tp.toFixed(1) + ' pts' + (hasSal() && ts ? ' · $' + ts.toLocaleString() : '') + '<br>' + keys.map(function(k){ return (isSG() && k === x.mvp ? mvpLabel() + ' ' : '') + byKey[k].n; }).join(', ') + '</div>'; }).join('') : '')
      + (all.length > here.length ? '<p class="note" style="margin:6px 0 0">' + (all.length - here.length) + ' more saved for another site or format - switch above to see them.</p>' : ''); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  $('#saveLuBtn').addEventListener('click', function(){ if(!lineup.length){ flash('Add players first.'); return; } var a = savedLus(); var name = prompt('Name this lineup:', (isSG() ? 'Showdown ' : '') + 'Lineup ' + (a.filter(function(x){ return x.week === D.week; }).length + 1) + ' · ' + total().toFixed(1) + ' pts'); if(name === null) return;
    a.push({id: 'l' + Date.now().toString(36), name: name.trim() || 'Lineup', site: site, sg: isSG(), week: D.week, lu: lineup.slice(), mvp: mvp, locks: locks, saved: Date.now()}); writeLus(a); renderSavedLus(); flash('Saved.'); });
  $('#savedLus').addEventListener('click', function(e){ var b = e.target.closest('button'); if(!b) return;
    if(b.dataset.ldel){ writeLus(savedLus().filter(function(x){ return x.id !== b.dataset.ldel; })); renderSavedLus(); return; }
    if(b.dataset.lload){ var x = savedLus().filter(function(y){ return y.id === b.dataset.lload; })[0]; if(!x) return; lineup = x.lu.filter(function(k){ return byKey[k]; }); mvp = x.mvp || null; locks = x.locks || {}; alts = []; save(); renderAll(); flash('Loaded "' + x.name + '".'); } });
  document.addEventListener('bs-account', renderSavedLus);
  function optOpts(){ var g = $('#oGame').value; return {stack:$('#oStack').checked, noQ:$('#oNoQ').checked, maxTeam:+$('#oMax').value || 0, game:g === 'all' ? null : {a:g.split('-')[0], b:g.split('-')[1]}}; }
  $('#optBtn').addEventListener('click', function(){ var btn = this; btn.disabled = true; btn.textContent = 'Working…'; setTimeout(function(){ try { runOpt(); } finally { btn.disabled = false; renderLineup(); } }, 30); });
  function runOpt(){
    if(isSG()){
      if(!SG.game){ flash('Pick the game first - single-game contests use one game.'); return; }
      var t0 = slotsFor(lineup), e0 = t0.slots.filter(function(o){ return !o.key; }).length;
      var fixed0 = e0 === 0 ? lineup.filter(function(k){ return locks[k]; }) : lineup.slice();
      var fm = mvp && fixed0.indexOf(mvp) >= 0 && (e0 > 0 || locks[mvp]) && t0.slots[0].key === mvp ? mvp : null;
      var o0 = {noQ:$('#oNoQ2').checked};
      var r0 = optimizeSG(fixed0, fm, o0);
      if(!r0){ flash('Could not fill the lineup under the cap with those locks - unlock someone or clear.'); return; }
      lineup = r0.keys; mvp = r0.mvp; save(); renderList(); renderLineup();
      alts = []; var oj = Object.assign({}, o0, {jit:0.12}), tr = 0;
      var diffN = function(a, b){ return a.keys.filter(function(k){ return b.keys.indexOf(k) < 0; }).length + (a.mvp !== b.mvp ? 1 : 0); };
      while(alts.length < 4 && tr++ < 25){ var a0 = optimizeSG(fixed0, fm, oj); if(!a0) break; if(diffN(a0, r0) >= 2 && !alts.some(function(b){ return diffN(a0, b) < 2; })) alts.push(a0); }
      renderAlts(); return;
    }
    var S = SITES[site], t = slotsFor(lineup), empty = t.slots.filter(function(o){ return !o.key; }).length;
    var fixed = empty === 0 ? lineup.filter(function(k){ return locks[k]; }) : lineup.slice();
    var res = optimize(fixed, optOpts());
    if(!res){ flash('Could not fill the lineup under the cap with those locks - unlock someone or clear.'); return; }
    lineup = res; save(); renderList(); renderLineup();
    // alternatives: jittered projections, must differ by 2+ players
    alts = []; var o = Object.assign(optOpts(), {jit:0.12}); var tries = 0;
    while(alts.length < 4 && tries++ < 25){ var a = optimize(fixed, o); if(!a) break; var diff = a.filter(function(k){ return lineup.indexOf(k) < 0; }).length; if(diff >= 2 && !alts.some(function(b){ return b.filter(function(k){ return a.indexOf(k) < 0; }).length < 2; })) alts.push(a); }
    renderAlts();
  }
  $('#alts').addEventListener('click', function(ev){ var b = ev.target.closest('button'); if(!b) return; var a = alts[+b.dataset.i]; alts.splice(+b.dataset.i, 1);
    if(Array.isArray(a)){ alts.unshift(lineup.slice()); lineup = a.slice(); } else { alts.unshift({keys:lineup.slice(), mvp:mvp}); lineup = a.keys.slice(); mvp = a.mvp; } save(); renderAll(); });
  $('#copyBtn').addEventListener('click', function(){ var t = slotsFor(lineup); var txt = 'BetSweep DFS - ' + SITES[site].name + (isSG() ? ' single game ' + SG.game.replace('-', ' v ') : '') + ' Week ' + D.week + '\n' + t.slots.map(function(o){ var p = o.key ? byKey[o.key] : null; var m = o.slot === 'MVP'; return (m ? mvpLabel() + ' (' + SG.mult + 'x)' : o.slot) + ': ' + (p ? p.n + ' (' + p.t + ') ' + pts(p, m).toFixed(1) + (sal(p, m) ? ' $' + sal(p, m) : '') : '-'); }).join('\n') + '\nTotal ' + total().toFixed(1) + ' pts' + (hasSal() ? ', $' + used().toLocaleString() : '') + '\nbetsweep.co/dfs/'; var done = function(ok){ flash(ok ? 'Copied.' : 'Copy failed - select the text and copy it by hand.'); }; if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(function(){ done(true); }, function(){ done(false); }); else done(false); });
  $('#exportBtn').addEventListener('click', function(){ var S = SITES[site], t = slotsFor(lineup);
    var ids = t.slots.map(function(o){ return o.slot === 'MVP' && site === 'dk' ? SAL[o.key].cpt.id : SAL[o.key].id; });
    var head = !isSG() ? S.upload : (site === 'dk' ? ['CPT'] : ['MVP - 1.5X Points']).concat(t.slots.slice(1).map(function(){ return site === 'dk' ? 'FLEX' : 'AnyFLEX'; })).join(',');
    var csv = head + '\n' + ids.join(',') + '\n'; if(window.claude || location.hostname.indexOf('claude') >= 0){ var ok = function(){ flash('Upload file copied as text - paste it into a .csv file and import it on ' + S.name + '.'); }; if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(csv).then(ok, function(){ prompt('Copy this and save it as a .csv file:', csv); }); else prompt('Copy this and save it as a .csv file:', csv); return; }
    var blob = new Blob([csv], {type:'text/csv'}); var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'betsweep-' + site + '-week' + D.week + '.csv'; document.body.appendChild(a); a.click(); setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 500); flash('Lineup file saved - upload it on ' + S.name + ' (Upload lineups / Import).'); });
  var ft; function flash(s){ var m = $('#flash'); m.textContent = s; m.hidden = false; clearTimeout(ft); ft = setTimeout(function(){ m.hidden = true; }, 3500); }
  // games for filters
  var games = {}; P.forEach(function(p){ if(p.o && p.t && p.p !== 'DEF'){ var k = [p.t, p.o].sort().join('-'); games[k] = 1; } });
  var gopts = Object.keys(games).sort().map(function(k){ return '<option value="' + k + '">' + k.replace('-', ' · ') + '</option>'; }).join('');
  $('#fGame').insertAdjacentHTML('beforeend', gopts); $('#oGame').insertAdjacentHTML('beforeend', gopts); $('#sgGame').insertAdjacentHTML('beforeend', gopts);
  load(); renderAll();
})();
"""

DK_LINE = "<b>DraftKings salaries load automatically</b> for the main Sunday slate - nothing to do. <b>FanDuel</b> main-slate salaries load automatically too once BetSweep posts them for the week."
body = f'''<div class="dfs">
 <section class="panel">
  <h2>DFS lineup builder <b id="siteName">DraftKings</b><span class="r"><span class="seg" id="siteSeg"><button type="button" data-v="dk">DraftKings</button><button type="button" data-v="fd">FanDuel</button></span> <span class="seg" id="fmtSeg"><button type="button" data-v="classic">Classic</button><button type="button" data-v="sg">Single game (MVP)</button></span></span></h2>
  <div class="src">
   <p class="how">{DK_LINE} For <b>FanDuel</b> (or a DraftKings showdown / other slate), load the site's own player list: on FanDuel open a contest and use <b>Download players list</b> above the player pool; on DraftKings use <b>Export to CSV</b> on the draft screen. <b>Drop the file on this box</b>, choose it, or paste its contents. It stays in your browser - nothing is uploaded anywhere. Salaries change during the week, so reload before you enter.</p>
   <p class="how ph"><b>On a phone:</b> the FanDuel and DraftKings apps have no download button. Open fanduel.com (or draftkings.com) in Safari or Chrome, switch to the desktop site (Safari: tap <b>aA</b> &rarr; <b>Request Desktop Website</b>; Chrome: <b>&#8942;</b> &rarr; <b>Desktop site</b>), log in, open the contest and tap <b>Download players list</b>. The file lands in Files &rarr; Downloads (iPhone) or Downloads (Android); come back here and tap <b>Choose file</b>.</p>
   <textarea id="csv" placeholder="Paste the CSV here (header row included)…"></textarea>
   <div class="row"><button type="button" class="btn" id="csvBtn">Load salaries</button><input type="file" id="csvFile" accept=".csv,text/csv"><button type="button" class="btn sec" id="clearSal">Clear salaries</button><button type="button" class="btn" id="shareSal" hidden>Share these salaries with everyone</button><span class="how" style="flex-basis:auto">No file? You can type a salary into any row below and build with the ones you fill in.</span></div>
   <div class="msg" id="srcMsg" hidden></div>
  </div>
  <div class="status"><span id="srcStat"></span><span>Week {WEEK} model · {n_act} active players · built {stamp} CT</span></div>
 </section>
 <div class="grid2">
  <section class="panel">
   <h2>Player pool <span class="r" id="count"></span></h2>
   <div class="filters">
    <select id="fPos" aria-label="position"><option value="all">All positions</option><option>QB</option><option>RB</option><option>WR</option><option>TE</option><option value="FLEX">FLEX (RB/WR/TE)</option><option value="DEF">DEF</option><option value="K">K</option></select>
    <select id="fGame" aria-label="game"><option value="all">All games</option></select>
    <input id="fQ" type="search" placeholder="Search player or team">
    <label><input type="checkbox" id="fAct" checked> active only</label>
    <label><input type="checkbox" id="fSal" checked> priced only</label>
   </div>
   <div class="tw"><table><thead><tr><th class="l" data-s="name">Player</th><th data-s="sal">Salary</th><th data-s="pts">Proj</th><th data-s="val">Pts / $1K</th><th></th></tr></thead><tbody id="plist"></tbody></table></div>
   <button type="button" class="more" id="more"></button>
   <p class="note">Proj = the model's projection re-scored in the selected site's rules (DraftKings: full PPR, 4-pt pass TD, +3 bonuses for 300 pass / 100 rush / 100 rec yards counted at the model's chance of clearing them; FanDuel: half PPR, 4-pt pass TD). Pts / $1K is the value number: 3+ is the usual bar for a cash-game play, 2.5 is roster filler. ✕ keeps a player out of Optimize. Tags: Q = questionable, snaps ↓ = snap share falling (projection already trimmed), 1st TD = the model's first-touchdown chance.</p>
  </section>
  <aside class="panel lu" id="lineup">
   <h2>Your lineup <span class="r" id="capLabel"></span></h2>
   <div class="cap"><div class="nums"><b id="capUsed"></b><span id="capLeft"></span></div><div class="bar"><i id="capbar"></i></div><div class="nums"><span id="capAvg"></span></div></div>
   <div class="tot"><div><small>Projected</small><b id="totPts">0.0</b></div><div><small>Salary</small><b id="totSal">—</b></div><div><small>Filled</small><b id="totN">0/9</b></div></div>
   <ul class="slots" id="slots"></ul>
   <div class="opts">
   <div id="optsClassic">
    <label><input type="checkbox" id="oStack" checked> stack the QB with one of his pass catchers</label>
    <label><input type="checkbox" id="oNoQ"> skip questionable players</label>
    <label>max players from one team <select id="oMax"><option value="0">no limit</option><option>3</option><option>4</option><option>5</option></select></label>
    <label>build from <select id="oGame"><option value="all">the whole slate</option></select></label>
   </div>
   <div id="optsSG" hidden>
    <label>game <select id="sgGame"><option value="">choose the game</option></select></label>
    <label>slots <select id="sgN"><option value="6">6 (1 MVP + 5 FLEX)</option><option value="5">5 (1 MVP + 4 FLEX)</option></select></label>
    <label>MVP / Captain points <select id="sgMult"><option value="1.5">1.5x</option><option value="2">2x</option></select></label>
    <label>MVP / Captain salary <select id="sgSal"><option value="1.5">1.5x (DraftKings Captain / FanDuel MVP)</option><option value="1">same as FLEX</option></select></label>
    <label><input type="checkbox" id="oNoQ2"> skip questionable players</label>
    <small id="sgHint"></small>
   </div>
   </div>
   <div class="acts"><button type="button" class="btn" id="optBtn">Build the best lineup</button><button type="button" class="btn sec" id="copyBtn">Copy</button><button type="button" class="btn sec" id="exportBtn" title="CSV in the site's upload format, using the player IDs from the list you loaded">Download upload file</button><button type="button" class="btn sec" id="saveLuBtn">Save lineup</button><button type="button" class="btn sec" id="clearBtn">Clear</button></div>
   <div class="msg" id="flash" hidden style="margin:0 12px 10px"></div>
   <div class="alts" id="alts"></div>
   <div class="alts" id="savedLus"></div>
   <p class="note">Optimize fills the open slots with the highest projected total under the cap (locked players stay; ✕'d players stay out), then shows other strong builds that differ by two or more players. The model does not know contest size or ownership: for big tournaments, lean on the alternatives and the 1st TD / snap tags to be different on purpose; for cash games take the top build. Information only, not a guarantee - 21+, please play responsibly.</p>
  </aside>
 </div>
 <a class="mbar" id="mbar" href="#lineup"><span id="mbarTxt">Lineup 0/9</span><b>View lineup ↓</b></a>
 <section class="panel"><div class="expl">
  <p><b>How it works.</b> Every number here is the BetSweep model's Week {WEEK} projection (the same one behind the matchup boards and the parlay builder), converted to the site's scoring, with injury designations and the snap-share trim already applied. Salaries come from the player list you load, matched to the model by name and team; players the model does not project (deep bench, injured all year) are listed in the load message and skipped. A player is scored only if he projects - we never fill a missing player with zero.</p>
  <dl><dt>Proj</dt><dd>projected fantasy points in the site's rules</dd><dt>Pts / $1K</dt><dd>projected points per $1,000 of salary - the value column; sort by it to find the cheap plays the model likes</dd><dt>Lock</dt><dd>keep this player when you re-optimize</dd><dt>✕</dt><dd>exclude from the optimizer (he stays in the list)</dd><dt>Single game (MVP)</dt><dd>for Showdown / single-game contests: pick the game, and the lineup is one MVP (Captain on DraftKings) plus FLEX slots, any position including K and D/ST. The MVP scores 1.5x and costs 1.5x salary on both sites (read straight from the player list when it has the MVP / Captain salary). The optimizer tries every realistic MVP, fills the rest exactly under the cap, and keeps at least one player from each team. A DraftKings Showdown file switches this on by itself. ★ on a FLEX row makes that player the MVP.</dd><dt>Upload file</dt><dd>a one-lineup CSV in the site's import format, built from the IDs in the list you loaded - import it on the contest's upload page instead of clicking nine players</dd></dl>
 </div></section>
</div>
<script>window.__BS = {json.dumps(DATA, separators=(",", ":"))};</script>
<script>{JS}</script>'''

page = (open(os.path.join(HERE, "template.html")).read()
        .replace("<title>BetSweep Matchup Boards</title>", "<title>BetSweep DFS Builder</title>")
        .replace("<h1>Week {{WEEK}} · <b>Matchup Boards</b></h1>", "<h1>Week {{WEEK}} · <b>DFS Lineup Builder</b></h1>")
        .replace("</style>", CSS + "\n</style>", 1)
        .replace("{{DESC}}", f"Build DraftKings and FanDuel lineups against the BetSweep model - classic, or single game with an MVP / Captain at 1.5x: load the site's player list, see every player's projection in that site's scoring and his points per $1K, tap players in or let the optimizer fill the lineup under the cap, then download the upload file. Built {stamp} CT.")
        .replace("{{NAV}}", "").replace("{{CARDS}}", body)
        .replace("{{LOGO}}", LOGO).replace("{{BANNER}}", BANNER).replace("{{WEEK}}", str(WEEK)).replace("{{STAMP}}", stamp).replace("{{ARCHIVE}}", ""))
page = re.sub(r'<div class="key">.*?</dl>\n</div>\n', '', page, count=1, flags=re.S)
page = page.replace('<div class="grid">', '<div class="grid" style="display:block">', 1)
out = os.path.join(OUT, "dfs.html"); open(out, "w").write(page)
print(f"wrote {out}: {len(POOL)} players ({n_act} active), week {WEEK}")
