"""ask.py - Ask BetSweep, in the menu of every page (owner 11/11 12:15 AM: "Can ask betsweep just be on the Menu? I'd want this on the
menu of every page. And then it doesn't have to be actually on any page itself it can just be in the menu").

Until 11/11 there were two ask boxes: "Ask BetSweep" at the top of the Parlay Builder (a plain-language search over the week's board,
owner 11/5) and "Ask the model" on the home page (a written answer from the alerts function, signed-in visitors, 20 a day). Both are
this one box now. build_site.py puts FORM in the site menu, CSS in the shared stylesheet and JS in the shared app script, and no page
carries an ask box of its own.

How it answers. The first question loads two files: the week's board - the Parlay Builder's own data file, found through the pointer
/b/ask.json that build_site.py writes, so nothing is published twice - and the player index the search button uses (/b/players.json).
The answer is worked out in the browser:
  - a player and a stat ("Chase 75+ rec yds", "Maye pass tds"): the leg's card - FanDuel price, the model's chance, edge, fair price,
    projection, the flags - with Add to slip;
  - a player ("Henry"): his lines on the board, best price first; a player with nothing on the board gets his page and the reason;
  - a last name two players share ("Williams"): both, to pick from;
  - a team ("Jaguars"): the game, its board and preview, and the legs priced in the model's favour;
  - "who benefits Darnold out": the legs whose notes account for his absence;
  - "best", "safest", "plus money", "best td": the Model's Best legs still on the board (the tiers the model assigns, not a new list).
Under it, "Ask the model for a written answer" sends the same question to the alerts function (signed in only, 20 a day) - the old
home-page feature. A link with ?ask=<question> on any page opens the menu with the answer, so /build/?ask=... links keep working.

Add to slip stays on the page: it writes the shared slip key (bs_slipk_w<week>, the one the boards, the home page, the player pages
and the builder read) and tells the page, which repaints its own buttons. On the Parlay Builder the builder's own slip does it
(window.bsSlipToggle). A started game, or a player the risk layer has ruled out, cannot be added - the same two checks the builder runs.
"""

# The form. First thing in the open menu on a phone; the last thing in the tab row on a wide screen (CSS order). The hint names a
# question this week's board can answer (build_site.py picks it from the builder data), so the example is never a player on a bye.
import html as _html
def form(eg_leg=None, eg_team=None):
    eg_leg = eg_leg or "Chase 75+ rec yds"; eg_team = eg_team or "Jaguars"
    return (f'<div class="navask" id="navask" data-eg="{_html.escape(eg_leg)}" data-team="{_html.escape(eg_team)}"><form id="navaskf" role="search" action="/build/" method="get">'
            '<label for="navaskq">Ask BetSweep</label>'
            '<div class="navaskr"><input type="search" id="navaskq" name="ask" maxlength="400" placeholder="Ask BetSweep" autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search">'
            '<button type="submit">Ask</button></div>'
            f'<p class="navaskh">Try <b>{_html.escape(eg_leg)}</b>, <b>{_html.escape(eg_team)}</b> or <b>best td</b>.</p></form>'
            '<div class="navaskout" id="navaskout" hidden aria-live="polite"></div></div>')
FORM = form()

# The menu is the cream bar on every page and in both themes, so these colours are the bar's own, not the page's variables.
CSS = """
/* ===== Ask BetSweep in the menu (11/11, ask.py) ===== */
.sitenav .tabs{min-width:0}
.sitenav .navask{order:9;position:relative;flex:0 1 auto;min-width:0;margin-left:8px;font-family:'IBM Plex Sans',system-ui,sans-serif;letter-spacing:0;text-transform:none}
.sitenav .navask label{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.sitenav .navask .navaskh{display:none;position:absolute;right:0;top:calc(100% + 10px);z-index:89;margin:0;width:max-content;max-width:min(360px,calc(100vw - 32px));padding:9px 12px;background:#141a24;color:#efe9da;border-radius:8px;font-size:13px;line-height:1.4;box-shadow:0 10px 24px rgba(0,0,0,.3)} .sitenav .navask .navaskh b{font-weight:600;color:#fff}
.sitenav .navask form:focus-within .navaskh{display:block} .sitenav .navask.has .navaskh,.sitenav .navask.has form:focus-within .navaskh{display:none}
.sitenav .navask form{margin:0} .sitenav .navaskr{display:flex;gap:6px;align-items:center}
.sitenav .navask input{font:inherit;font-size:14.5px;font-weight:500;flex:0 1 210px;width:210px;min-width:104px;min-height:36px;padding:6px 10px;border:1.5px solid #141a24;border-radius:8px;background:#fff;color:#141a24;-webkit-appearance:none;appearance:none}
.sitenav .navask input::placeholder{color:#6b7280;opacity:1}
.sitenav .navask input:focus{outline:none;border-color:#d7332a;box-shadow:0 0 0 3px rgba(215,51,42,.22)}
.sitenav .navask form button{flex:none;font:inherit;font-family:'Barlow Condensed','IBM Plex Sans',sans-serif;font-weight:700;font-size:14.5px;letter-spacing:.06em;text-transform:uppercase;min-height:36px;padding:0 14px;border:0;border-radius:8px;background:#d7332a;color:#fff;cursor:pointer}
.sitenav .navask form button:hover{background:#b8261d}
.sitenav .navaskout{position:absolute;right:0;top:calc(100% + 10px);z-index:90;width:min(500px,calc(100vw - 32px));max-height:min(76vh,680px);overflow:auto;overscroll-behavior:contain;background:#efe9da;color:#141a24;border:1px solid #d9d1bf;border-top:3px solid #d7332a;border-radius:0 0 12px 12px;box-shadow:0 18px 40px rgba(0,0,0,.35);padding:12px 14px 14px;font-size:14px;line-height:1.45}
.sitenav .navaskout[hidden]{display:none}
.sitenav .navask .nahd{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:-4px 0 6px} .sitenav .navask .nahd small{color:#5b6473;font-size:12px}
.sitenav .navask .nax{font:inherit;font-size:24px;line-height:1;background:none;border:0;color:#5b6473;margin:0 -6px 0 0;padding:4px 8px;min-width:36px;min-height:36px;cursor:pointer} .sitenav .navask .nax:hover{color:#141a24}
.sitenav .navask .nac{padding:10px 12px;border-radius:10px;background:#e4ddcb;margin-top:8px} .sitenav .navask .nahd + .nac{margin-top:0} .sitenav .navask .nac p{margin:6px 0 0}
.sitenav .navask .nah{display:flex;justify-content:space-between;gap:4px 10px;align-items:baseline;flex-wrap:wrap}
.sitenav .navask .nah b,.sitenav .navask .nac > b{font-family:'Barlow Condensed','IBM Plex Sans',sans-serif;font-weight:700;font-size:20px;letter-spacing:.01em;line-height:1.15} .sitenav .navask .nah small{color:#5b6473;font-size:12.5px}
.sitenav .navask .nag{display:grid;grid-template-columns:repeat(auto-fit,minmax(56px,1fr));gap:6px;margin:10px 0 2px}
.sitenav .navask .nag span{display:flex;flex-direction:column} .sitenav .navask .nag small{font-size:10.5px;color:#5b6473;text-transform:uppercase;letter-spacing:.06em}
.sitenav .navask .nag b{font-family:'Barlow Condensed','IBM Plex Sans',sans-serif;font-weight:700;font-size:22px;line-height:1.1;font-variant-numeric:tabular-nums} .sitenav .navask .nag b.up{color:#1f7a4d} .sitenav .navask .nag b.dn{color:#b3372b}
.sitenav .navask .naf{list-style:none;margin:8px 0 0;padding:0;font-size:12.5px;color:#5b6473} .sitenav .navask .naf li{margin:4px 0} .sitenav .navask .naf li b{color:#141a24} .sitenav .navask .naf li.bad b{color:#b3372b} .sitenav .navask .naf li.good b{color:#1f7a4d}
.sitenav .navask .wr{color:#b3372b;font-size:12.5px} .sitenav .navask .nt{color:#5b6473;font-size:12.5px}
.sitenav .navask .nab{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.sitenav .navask .nab a{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:0 13px;margin:0;border:1.5px solid #c9c1ad;border-radius:8px;background:none;color:#141a24;text-decoration:none;font-family:'Barlow Condensed','IBM Plex Sans',sans-serif;font-weight:700;font-size:14.5px;letter-spacing:.04em;text-transform:uppercase;text-align:center}
.sitenav .navask .nab a:hover{border-color:#141a24} .sitenav .navask .nab a.go{background:#141a24;border-color:#141a24;color:#efe9da} .sitenav .navask .nab a.go.in{background:#1f7a4d;border-color:#1f7a4d;color:#fff} .sitenav .navask .nab a[hidden]{display:none}
.sitenav .navask .nal{margin:6px 0 0;padding:0;list-style:none} .sitenav .navask .nal li{padding:8px 0;border-top:1px solid #d3cbb8;display:flex;justify-content:space-between;gap:10px;align-items:baseline} .sitenav .navask .nal li:first-child{border-top:0}
.sitenav .navask .nal a{display:inline;padding:0;margin:0;border:0;font-family:'IBM Plex Sans',system-ui,sans-serif;font-size:14.5px;font-weight:600;letter-spacing:0;text-transform:none;text-align:left;color:#141a24;text-decoration:underline;text-decoration-color:#b9b09a;text-underline-offset:3px}
.sitenav .navask .nal small{color:#5b6473;font-size:12.5px;white-space:nowrap;font-variant-numeric:tabular-nums}
.sitenav .navask a.inl{display:inline;padding:0;margin:0;border:0;font:inherit;letter-spacing:0;text-transform:none;color:#141a24;text-decoration:underline}
.sitenav .navask .nam{margin-top:10px;font-size:13px;color:#5b6473}
.sitenav .navask .namgo,.sitenav .navask .namin{font:inherit;font-weight:600;color:#141a24;background:none;border:0;border-bottom:2px solid #d7332a;padding:0 0 1px;cursor:pointer}
.sitenav .navask .namout{margin:8px 0 0;padding:10px 12px;border-left:3px solid #d7332a;background:#f7f3e8;border-radius:0 8px 8px 0;color:#141a24;white-space:pre-wrap;font-size:14.5px;line-height:1.5} .sitenav .navask .namout[hidden]{display:none}
@media (max-width:1240px){
  .sitenav .navask{order:-2;margin:0;padding:12px 14px 13px;border-bottom:1px solid #d9d1bf;background:#e9e2d0}
  .sitenav .navask label{position:static;width:auto;height:auto;margin:0 0 8px;overflow:visible;clip:auto;white-space:normal;display:block;font-family:'Barlow Condensed','IBM Plex Sans',sans-serif;font-weight:700;font-size:17px;letter-spacing:.05em;text-transform:uppercase;color:#141a24}
  .sitenav .navask .navaskh,.sitenav .navask form:focus-within .navaskh{display:block;position:static;width:auto;max-width:none;margin:8px 0 0;padding:0;background:none;box-shadow:none;border-radius:0;font-size:13px;line-height:1.4;color:#5b6473} .sitenav .navask .navaskh b{color:#141a24}
  .sitenav .navask input{flex:1 1 auto;width:auto;min-height:46px;font-size:16px;padding:8px 12px} .sitenav .navask form button{min-height:46px;padding:0 20px;font-size:16px}
  .sitenav .navaskout{position:static;width:auto;max-height:none;overflow:visible;margin:10px 0 0;padding:0;border:0;border-radius:0;box-shadow:none;background:none}
  .sitenav .navask .nahd{margin:0 0 4px}
  .sitenav .navask.has .navaskh,.sitenav .navask.has form:focus-within .navaskh{display:none}
  .sitenav .navask .nac{background:#efe9da;border:1px solid #d9d1bf}
  .sitenav .navask .nab a{flex:1 1 auto;min-height:44px}
}
/* Theme lives on My BetSweep since 11/11 (owner: "put theme in My Betsweep rather than the menu"): one row under the page title, where it
   is found without scrolling; the buttons take the page's colours */
.methmrow{display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px;margin:12px 0 4px}
.methmrow > span{font-family:var(--ctl,'Barlow Condensed',sans-serif);font-weight:700;font-size:13.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute,#6b655c)}
.methm{display:flex;gap:6px;flex-wrap:wrap}
.methm button{font:inherit;font-family:var(--ctl,'Barlow Condensed',sans-serif);font-weight:700;font-size:14.5px;letter-spacing:.05em;text-transform:uppercase;min-height:40px;padding:0 18px;border:1.5px solid var(--line,#d3cbb8);border-radius:999px;background:transparent;color:var(--ink,#141a24);cursor:pointer}
.methm button.on{background:var(--ink,#141a24);border-color:var(--ink,#141a24);color:var(--bg,#efe9da)}
"""

JS = r"""
/* Ask BetSweep in the menu (11/11): see ask.py */
(function(){
  var wrap = document.getElementById('navask'); if(!wrap) return;
  var nav = document.getElementById('sitenav'), form = document.getElementById('navaskf'), inp = document.getElementById('navaskq'), out = document.getElementById('navaskout');
  var D = null, legs = [], BYI = {}, games = {}, PIDX = {}, ready = null, NAMES = null, lastQ = '';
  var wide = window.matchMedia ? window.matchMedia('(min-width:1241px)') : {matches: false};
  function ph(){ inp.placeholder = wide.matches ? 'Ask BetSweep' : 'Any player, stat, line or team'; }
  ph(); if(wide.addEventListener) wide.addEventListener('change', ph);
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function am(o){ return o > 0 ? '+' + o : '' + o; }
  function isTD(l){ return l.m === 'Anytime TD' || l.m === 'First TD' || l.m === '2+ TD' || l.m === '3+ TD'; }
  function isU(l){ return /^Under /.test(l.m); }
  function slug(n){ var p = PIDX[n]; if(p && p.s) return p.s; return String(n).replace(/\./g, '').trim().replace(/\s+(jr|sr|ii|iii|iv|v)$/i, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, ''); }
  function norm(s){ return String(s).toLowerCase().replace(/[^a-z0-9.+ ]/g, ' ').replace(/\s+/g, ' ').trim(); }
  function toks(n){ return norm(n).replace(/\./g, '').split(' ').filter(function(t){ return t && !/^(jr|sr|ii|iii|iv)$/.test(t); }); }
  function key(l){ return l.pl + '|' + l.m + '|' + Math.round(l.ln || 1); }
  function what(l){ var ms = String(l.ms || l.m); return isTD(l) ? ms : isU(l) ? 'under ' + l.ln + ' ' + ms.replace(/^under\s+/i, '').toLowerCase() : Math.round(l.ln || 1) + '+ ' + ms.toLowerCase(); }
  function started(gid){ var g = games[gid]; return !!(g && g.ko && Date.now() >= g.ko); }
  function openLegs(){ return legs.filter(function(l){ return !started(l.g); }); }
  function verdict(l){ try { return (window.BSRisk && BSRisk.verdict) ? BSRisk.verdict(l.pl, l.m) : null; } catch(e){ return null; } }
  // ---- the week's board: the builder's own on the Parlay Builder, otherwise its data file read as text (it sets a global other pages use for their own data)
  function board(){ var b = window.__BS; if(b && b.legs && b.games) return Promise.resolve(b);
    return fetch('/b/ask.json', {cache: 'no-store'}).then(function(r){ if(!r.ok) throw new Error('pointer'); return r.json(); })
      .then(function(j){ if(!j || !j.src) throw new Error('pointer'); return fetch(j.src); })
      .then(function(r){ if(!r.ok) throw new Error('board'); return r.text(); })
      .then(function(js){ var s = js.indexOf('{'), e = js.lastIndexOf('}'); if(s < 0 || e < s) throw new Error('board'); return JSON.parse(js.slice(s, e + 1)); }); }
  function load(){ if(ready) return ready;
    var idx = fetch('/b/players.json', {cache: 'force-cache'}).then(function(r){ return r.ok ? r.json() : []; }).catch(function(){ return []; });
    ready = Promise.all([board(), idx]).then(function(r){ D = r[0]; games = {}; (D.games || []).forEach(function(g){ games[g.gid] = g; });
      legs = (D.legs || []).filter(function(l){ return !l.gl; }); BYI = {}; legs.forEach(function(l){ BYI[l.i] = l; });
      PIDX = {}; (Array.isArray(r[1]) ? r[1] : []).forEach(function(p){ if(p && p.n) PIDX[p.n] = p; }); NAMES = null; });
    ready.catch(function(){ ready = null; }); return ready; }
  // ---- the slip: shared with every page through one browser key; the Parlay Builder keeps its own and offers these two hooks
  function wk(){ return 'bs_slipk_w' + D.week; }
  function slipGet(){ try { var a = JSON.parse(localStorage.getItem(wk()) || '[]'); return Array.isArray(a) ? a : []; } catch(e){ return []; } }
  function inSlip(k){ return window.bsSlipHas ? !!window.bsSlipHas(k) : slipGet().indexOf(k) >= 0; }
  function slipN(){ return window.bsSlipCount ? window.bsSlipCount() : slipGet().length; }
  function slipToggle(l){ var k = key(l);   // true = now in, false = taken out, null = refused, undefined = no storage (the link opens the builder instead)
    if(window.bsSlipToggle) return window.bsSlipToggle(k);
    var a = slipGet(), i = a.indexOf(k);
    if(i >= 0) a.splice(i, 1);
    else { if(started(l.g)) return null; if(window.BSRisk && BSRisk.blockAdd && BSRisk.blockAdd(l.pl, l.m)) return null; a.push(k); }
    var v = JSON.stringify(a); try { localStorage.setItem(wk(), v); if(localStorage.getItem(wk()) !== v) return undefined; } catch(e){ return undefined; }
    try { window.dispatchEvent(new StorageEvent('storage', {key: wk(), newValue: v})); } catch(e){}
    return i < 0; }
  function addBtn(l){ var on = inSlip(key(l)); return '<a class="go naadd' + (on ? ' in' : '') + '" data-i="' + l.i + '" href="/build/?add=' + encodeURIComponent(key(l)) + '" role="button" aria-pressed="' + on + '">' + (on ? 'In your slip ✓' : 'Add to slip') + '</a>'; }
  function slipLink(){ var n = D ? slipN() : 0; return '<a class="naslip" href="/build/"' + (n ? '' : ' hidden') + '>Open betslip (' + n + ')</a>'; }
  function paintSlip(){ [].slice.call(out.querySelectorAll('.naadd')).forEach(function(a){ var l = BYI[+a.getAttribute('data-i')]; if(!l) return; var on = inSlip(key(l)); a.classList.toggle('in', on); a.setAttribute('aria-pressed', on); a.textContent = on ? 'In your slip ✓' : 'Add to slip'; });
    var n = slipN(); [].slice.call(out.querySelectorAll('.naslip')).forEach(function(a){ a.hidden = !n; a.textContent = 'Open betslip (' + n + ')'; }); }
  // ---- reading the question
  var ASKM = [[/rush(ing)?\s*(\+|and)?\s*rec|scrimmage/, 'Rush + Rec Yards'], [/long(est)?/, 'Longest Reception'], [/pass(ing)?\s*(tds?|touchdowns?)|(tds?|touchdowns?)\s*pass(es)?/, 'Passing TDs'],
    [/first\s*(td|touchdown)|1st\s*(td|touchdown)|scores?\s*first/, 'First TD'], [/\b(2|two)\s*\+?\s*(tds?|touchdowns?)/, '2+ TD'], [/\b(3|three)\s*\+?\s*(tds?|touchdowns?)/, '3+ TD'], [/\btds?\b|touchdowns?|\bscores?\b|anytime/, 'Anytime TD'],
    [/rec(eiving)?\s*y(ar)?ds?|receiving/, 'Receiving Yards'], [/rush(ing)?|carries/, 'Rushing Yards'], [/pass(ing)?|throws?/, 'Passing Yards'], [/\brec(eptions?)?\b|catch(es)?/, 'Receptions']];
  function market(s){ var mk = null; ASKM.some(function(x){ if(x[0].test(s)){ mk = x[1]; return true; } return false; }); return mk; }
  function names(){ if(NAMES) return NAMES; var s = {}; legs.forEach(function(l){ s[l.pl] = 1; }); Object.keys(D.gl || {}).forEach(function(n){ s[n] = 1; }); Object.keys(D.pf || {}).forEach(function(n){ s[n] = 1; }); Object.keys(PIDX).forEach(function(n){ s[n] = 1; }); NAMES = Object.keys(s); return NAMES; }
  // the best-matching player, or the players who tie for it (a last name two players share)
  function player(q, mk){ var ns = names(), qt = toks(q), firsts = {}, L = openLegs(), sc = [];
    ns.forEach(function(n){ var f = toks(n)[0]; firsts[f] = (firsts[f] || 0) + 1; });
    ns.forEach(function(n){ var t = toks(n), last = t[t.length - 1], s = 0;
      t.forEach(function(x, k){ if(x.length > 1 && qt.indexOf(x) >= 0) s += (x === last ? 3 : (k === 0 && firsts[x] === 1 ? 2.5 : 1)); });
      if(!s) return;
      var has = L.filter(function(l){ return l.pl === n; });
      s += (mk && has.some(function(l){ return l.m === mk || l.m === 'Under ' + mk; }) ? 2 : 0) + (has.length ? 0.5 : 0);
      sc.push([s, n]); });
    sc.sort(function(a, b){ return b[0] - a[0]; });
    if(!sc.length || sc[0][0] < 2.5) return null;
    var top = sc.filter(function(x){ return x[0] > sc[0][0] - 0.01; }).map(function(x){ return x[1]; });
    return top.length > 1 ? {amb: top.slice(0, 8)} : {name: top[0]}; }
  function fair(p){ var o = p >= 0.5 ? -Math.round(100 * p / (1 - p)) : Math.round(100 * (1 - p) / p); return o > 0 ? '+' + o : '' + o; }
  function where(n){ var p = PIDX[n]; return p ? [p.p, p.t + (p.o ? (p.o === 'BYE' ? ', bye week' : ' vs ' + p.o) : '')].filter(Boolean).join(' · ') : ''; }
  function card(l, note){ var g = games[l.g] || {}, v = verdict(l), out2 = v && v.level === 'block';
    var fl = (l.fh || []).slice(0, 4).map(function(f){ return '<li class="' + esc(f[0]) + '"><b>' + esc(f[1]) + '</b> ' + esc(f[2] || '') + '</li>'; }).join('');
    return '<div class="nac main"><div class="nah"><b>' + esc(l.pl) + ' ' + esc(what(l)) + '</b><small>' + esc(l.tm) + ' vs ' + esc(l.opp) + (g.kick ? ' · ' + esc(g.kick) : '') + '</small></div>' + (note ? '<p class="nt">' + esc(note) + '</p>' : '') +
      '<div class="nag"><span><small>FanDuel</small><b>' + am(l.o) + '</b></span><span><small>Model</small><b>' + Math.round(l.p * 100) + '%</b></span><span><small>Edge</small><b class="' + (l.e >= 0 ? 'up' : 'dn') + '">' + (l.e >= 0 ? '+' : '') + (l.e * 100).toFixed(1) + '</b></span><span><small>Fair</small><b>' + fair(l.p) + '</b></span>' + (l.proj != null ? '<span><small>Proj</small><b>' + (Math.round(l.proj * 10) / 10) + '</b></span>' : '') + '</div>' +
      (v ? '<p class="' + (v.level === 'good' ? 'nt' : 'wr') + '">' + esc(v.label) + (v.why ? ': ' + esc(v.why) : '') + '</p>' : '') + (l.w ? '<p class="wr">' + esc(l.w) + '</p>' : '') + (fl ? '<ul class="naf">' + fl + '</ul>' : '') +
      '<p class="nab">' + (out2 ? '' : addBtn(l)) + slipLink() + '<a href="/player/' + slug(l.pl) + '/">Player page</a></p></div>'; }
  function list(ls, bare){ return ls.length ? '<ul class="nal">' + ls.map(function(l){ return '<li><a href="#" class="napick" data-q="' + esc(l.pl + ' ' + (isTD(l) ? (l.m === 'First TD' ? 'first td' : l.m === 'Anytime TD' ? 'td' : l.m) : (isU(l) ? 'under ' : '') + (l.ms || l.m) + ' ' + (isU(l) ? l.ln : Math.round(l.ln || 1)))) + '">' + (bare ? '' : esc(l.pl) + ' ') + esc(what(l)) + '</a><small>' + am(l.o) + ' · ' + Math.round(l.p * 100) + '% · edge ' + (l.e >= 0 ? '+' : '') + (l.e * 100).toFixed(1) + '</small></li>'; }).join('') + '</ul>' : '<p>Nothing priced in the model\'s favour right now.</p>'; }
  function noLines(pl){ var p = PIDX[pl] || {}, gid = p.t && p.o && p.o !== 'BYE' ? [p.t, p.o].sort().join('-') : '', g = games[gid], v = null; try { v = window.BSRisk && BSRisk.verdict ? BSRisk.verdict(pl, '') : null; } catch(e){}
    var why = p.o === 'BYE' ? 'On a bye this week.' : (g && started(gid)) ? 'His game has kicked off, so the board is closed for him.' : (v && v.level === 'block') ? esc(v.label) + (v.why ? ': ' + esc(v.why) : '') : 'FanDuel has no lines for him on the board right now. They may not be posted yet.';
    return '<div class="nac"><div class="nah"><b>' + esc(pl) + '</b><small>' + esc(where(pl)) + '</small></div><p>' + why + '</p><p class="nab"><a class="go" href="/player/' + slug(pl) + '/">Player page</a>' +
      (g ? (started(gid) ? '<a href="/live/#lv-' + esc(gid) + '">Live</a>' : '<a href="/boards/#' + esc(gid) + '">Matchup board</a>') : '') + '</p></div>'; }
  function answer(raw){
    var q = norm(raw), L = openLegs(), words = q.split(' ');
    var team = Object.keys(games).map(function(g){ return games[g]; }).filter(function(g){
      var alt = [norm(g.na || ''), norm(g.nb || '')].concat(words.length <= 3 ? [String(g.a).toLowerCase(), String(g.b).toLowerCase()] : []).filter(Boolean);
      return alt.length && new RegExp('\\b(' + alt.map(function(a){ return a.replace(/[.+]/g, '\\$&'); }).join('|') + ')\\b').test(q); });
    var hit = player(q, market(q)), pl = hit && hit.name;
    var bq = /benefit|without|\bout\b|replace|fill.?in/.test(q);
    if(bq && !pl){ var tk = words.filter(function(t){ return t.length > 3 && !/^(who|benefits?|without|with|replace|fill|does|from|when|sits?)$/.test(t); })[0];
      if(tk){ var mm = null, cap = tk.charAt(0).toUpperCase() + tk.slice(1); L.some(function(l){ return (l.fh || []).concat((D.pf || {})[l.pl] || []).some(function(f){ var m = new RegExp("([A-Z][A-Za-z.'-]+ " + cap.replace(/[^A-Za-z'-]/g, '') + "(?: Jr\\.)?)").exec(String(f[2] || '')); if(m){ mm = m[1]; return true; } return false; }); }); if(mm){ pl = mm; hit = {name: mm}; } } }
    if(bq && pl){ var last = pl.split(' ').pop(), RET = /return|is back|back this week|back from/i, OUTN = /out this week|vacated|fill.?in|steps into|without|ruled out|inactive|sidelined|room thinned/i;
      var about = function(l, re, not){ return l.pl !== pl && (l.fh || []).concat((D.pf || {})[l.pl] || []).some(function(f){ var t = String(f[1] || '') + ' ' + String(f[2] || ''); return (String(f[2] || '').indexOf(pl) >= 0 || String(f[1] || '').indexOf(last) >= 0) && re.test(t) && !(not && not.test(t)); }); };
      var top8 = function(ls){ var seen = {}; return ls.sort(function(a, b){ return b.e - a.e; }).filter(function(l){ if(seen[l.pl + l.m]) return false; seen[l.pl + l.m] = 1; return true; }).slice(0, 8); };
      var outs = top8(L.filter(function(l){ return about(l, OUTN, RET); })), backs = outs.length ? [] : top8(L.filter(function(l){ return about(l, RET); }));
      return '<div class="nac"><b>' + (outs.length || !backs.length ? 'With ' + esc(pl) + ' out' : esc(pl) + ' is back this week') + '</b>' +
        (outs.length ? '<p>Legs whose model notes account for his absence, best price first.</p>' + list(outs) : backs.length ? '<p>Nobody is filling in for him. These legs carry a note that his return takes work away from them.</p>' + list(backs) : '<p>No leg on the board carries a note about his absence right now.</p>') +
        '<p class="nab"><a href="/benefits/">Who benefits</a><a href="/player/' + slug(pl) + '/">Player page</a></p></div>'; }
    if(hit && hit.amb){ var qt = toks(q);
      return '<div class="nac"><b>Which one?</b><ul class="nal">' + hit.amb.map(function(n){ var rest = words.filter(function(w){ return toks(n).indexOf(w.replace(/\./g, '')) < 0; }).join(' ');
        return '<li><a href="#" class="napick" data-q="' + esc((n + ' ' + rest).trim()) + '">' + esc(n) + '</a><small>' + esc(where(n)) + '</small></li>'; }).join('') + '</ul></div>'; }
    if(pl){ var nt = toks(pl), rest = words.filter(function(w){ return nt.indexOf(w.replace(/\./g, '')) < 0; }).join(' '), mk = market(rest);
      var num = (rest.match(/(\d+(\.\d+)?)/) || [])[1], under = /\bunder\b/.test(q);
      var all = L.filter(function(l){ return l.pl === pl; }); if(!all.length) return noLines(pl);
      var mine = all.filter(function(l){ return (!mk || l.m === mk || l.m === 'Under ' + mk) && (under ? isU(l) : !isU(l)); }), note = '';
      if(!mine.length && under && mk){ mine = all.filter(function(l){ return l.m === mk; }); if(mine.length) note = 'No under is on the board for him at that stat. This is the over.'; }
      if(!mine.length){ note = mk ? 'FanDuel has no ' + mk.toLowerCase() + ' line for him on the board. These are his other lines.' : ''; mk = null; mine = all; }
      if(num != null && mk){ var n = +num; mine.sort(function(a, b){ return Math.abs((a.ln || 1) - n) - Math.abs((b.ln || 1) - n); }); var h = mine[0];
        return card(h, note || (!isTD(h) && Math.abs((h.ln || 1) - n) > 0.6 ? 'FanDuel has no ' + n + (isU(h) ? '' : '+') + ' line. The closest is ' + (isU(h) ? h.ln : Math.round(h.ln || 1) + '+') + '.' : '')); }
      if(mk){ mine.sort(function(a, b){ return Math.abs(a.p - 0.55) - Math.abs(b.p - 0.55); });   // the main rung first
        return card(mine[0], note) + (mine.length > 1 ? '<div class="nac"><b>Other ' + esc(mk.toLowerCase()) + ' lines</b>' + list(mine.slice(1, 7), true) + '</div>' : ''); }
      return '<div class="nac"><div class="nah"><b>' + esc(pl) + '</b><small>' + esc(where(pl)) + '</small></div>' + (note ? '<p class="nt">' + esc(note) + '</p>' : '') + list(mine.slice().sort(function(a, b){ return b.e - a.e; }).slice(0, 8), true) +
        '<p class="nab"><a href="/player/' + slug(pl) + '/">Player page</a>' + slipLink() + '</p></div>'; }
    if(team.length){ var g = team[0], gl = L.filter(function(l){ return l.g === g.gid && l.e > 0; }).sort(function(a, b){ return b.e - a.e; }).slice(0, 6);
      return '<div class="nac"><div class="nah"><b>' + esc(g.away || g.a) + ' at ' + esc(g.home || g.b) + '</b><small>' + esc(g.kick || '') + '</small></div>' +
        (started(g.gid) ? '<p>This game has kicked off.</p>' : gl.length ? list(gl) : '<p>No player prop in this game is priced in the model\'s favour right now.</p>') +
        '<p class="nab"><a class="go" href="' + (started(g.gid) ? '/live/#lv-' : '/boards/#') + esc(g.gid) + '">' + (started(g.gid) ? 'Live' : 'Matchup board') + '</a><a href="/dossier/' + esc(g.gid) + '/">Preview</a><a href="/teams/' + esc(String(g.a).toLowerCase()) + '/">' + esc(g.a) + '</a><a href="/teams/' + esc(String(g.b).toLowerCase()) + '/">' + esc(g.b) + '</a></p></div>'; }
    if(/\b(best|top|safest|safe|locks?|plus.?money|long.?shots?|value|edges?)\b/.test(q)){   // the Model's Best tiers the model assigned, nothing new
      var tier = /\bsafe(st)?\b|\blocks?\b/.test(q) ? 'safe' : /plus.?money|long.?shots?/.test(q) ? 'plus' : null, mk2 = market(q);
      var bl = L.filter(function(l){ var v = verdict(l); return l.tier && (!tier || l.tier === tier) && (!mk2 || l.m === mk2) && !(v && v.level === 'block'); }).sort(function(a, b){ return tier === 'safe' ? b.p - a.p : b.e - a.e; }).slice(0, 8);
      return '<div class="nac"><b>Model\'s Best' + (tier === 'safe' ? ', safer legs' : tier === 'plus' ? ', plus money' : '') + (mk2 ? ', ' + esc(mk2.toLowerCase()) : '') + '</b>' + (bl.length ? list(bl) : '<p>None on the board right now.</p>') + '<p class="nab"><a class="go" href="/best/">Model\'s Best</a>' + slipLink() + '</p></div>'; }
    return '<div class="nac"><p style="margin:0">No player or team in that one. Try <b>' + esc(wrap.getAttribute('data-eg') || 'a player and a stat') + '</b>, <b>' + esc(wrap.getAttribute('data-team') || 'a team') + '</b>, <b>best td</b> or <b>who benefits</b> and a player who is out.</p></div>'; }
  function show(html){ out.hidden = false; wrap.classList.add('has');
    out.innerHTML = '<div class="nahd"><small>' + (D ? 'Week ' + esc(D.week) + ' board' + (D.built ? ', built ' + esc(D.built) : '') : '') + '</small><button type="button" class="nax" aria-label="Close the answer">×</button></div>' + html; }
  function hide(){ out.hidden = true; out.innerHTML = ''; wrap.classList.remove('has'); }
  function run(raw){ raw = String(raw || '').trim(); lastQ = raw; if(!raw){ hide(); return; }
    show('<div class="nac"><p style="margin:0">Reading this week\'s board…</p></div>');
    load().then(function(){ if(lastQ !== raw) return;
      show(answer(raw) + '<div class="nam"><button type="button" class="namgo">Ask the model for a written answer</button><p class="namout" hidden></p></div>');
      if(!wide.matches){ var tb = nav.querySelector('.tabs'); if(tb) tb.scrollTop = 0; } })
    .catch(function(){ if(lastQ === raw) show('<div class="nac"><p style="margin:0">This week\'s board did not load. Check the connection and ask again.</p></div>'); }); }
  form.addEventListener('submit', function(e){ e.preventDefault(); run(inp.value); if(!wide.matches){ try { inp.blur(); } catch(x){} } });
  inp.addEventListener('input', function(){ if(!inp.value.trim()){ lastQ = ''; hide(); } });
  out.addEventListener('click', function(e){ var t = e.target; if(!t.closest) return;
    var p = t.closest('.napick'); if(p){ e.preventDefault(); inp.value = p.getAttribute('data-q'); run(inp.value); return; }
    if(t.closest('.nax')){ hide(); return; }
    var ad = t.closest('.naadd'); if(ad){ if(e.metaKey || e.ctrlKey || e.shiftKey) return; var l = BYI[+ad.getAttribute('data-i')]; if(!l) return;
      var r = slipToggle(l); if(r === undefined) return; e.preventDefault(); paintSlip(); return; }
    if(t.closest('.naslip') && window.bsSlipToggle){ e.preventDefault(); nav.classList.remove('open'); var mb0 = nav.querySelector('.menu'); if(mb0) mb0.setAttribute('aria-expanded', 'false'); if(wide.matches) hide(); return; }   // on the builder the slip is this page's own
    if(t.closest('.namin')){ var s = document.querySelector('#bsacct .in'); if(s) s.click(); return; }
    var mg = t.closest('.namgo'); if(!mg) return;
    // the written answer (the home page's old "Ask the model"): signed-in visitors, 20 a day, from the alerts function
    var box = out.querySelector('.namout'), CFG = window.__BS_ACCOUNT || {}, acct = window.bsAccount; box.hidden = false;
    if(!acct || !acct.user || !acct.client){ box.innerHTML = 'A written answer needs a free account, 20 questions a day. ' + (document.querySelector('#bsacct .in') ? '<button type="button" class="namin">Sign in</button>' : 'Sign in from the home page.'); return; }
    mg.disabled = true; box.textContent = 'Thinking…'; var asked = lastQ;
    acct.client.auth.getSession().then(function(r){ var tok = r.data && r.data.session && r.data.session.access_token;
      return fetch((CFG.url || '') + '/functions/v1/slip-alerts', {method: 'POST', headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok, 'apikey': CFG.key || ''}, body: JSON.stringify({mode: 'ask', q: asked})}); })
    .then(function(r){ return r.json(); }).then(function(j){ box.textContent = (j && j.a ? j.a : (j && j.error) || 'No answer came back.') + (j && typeof j.left === 'number' ? '\n\n' + j.left + ' questions left today.' : ''); })
    .catch(function(){ box.textContent = 'Could not reach the model desk.'; }).then(function(){ mg.disabled = false; }); });
  window.addEventListener('storage', function(e){ if(D && !out.hidden && (!e.key || e.key === wk())) paintSlip(); });
  document.addEventListener('bs-slip', function(){ if(D && !out.hidden) paintSlip(); });
  document.addEventListener('keydown', function(e){ if(e.key === 'Escape' && !out.hidden){ hide(); } });
  // wide screens: the answer is a panel under the box, so a click anywhere else puts it away (a phone keeps it in the open menu)
  document.addEventListener('click', function(e){ if(out.hidden || !wide.matches) return; var t = e.target; if(!t || !document.contains(t) || (t.closest && t.closest('#navask'))) return; hide(); });
  // a link with ?ask=... on any page opens the menu with the answer (the builder's old /build/?ask= links; this form without script)
  try { var q0 = new URLSearchParams(location.search).get('ask');
    if(q0 !== null){ nav.classList.add('open'); var mb = nav.querySelector('.menu'); if(mb) mb.setAttribute('aria-expanded', 'true'); inp.value = q0;
      if(q0.trim()) run(q0); else setTimeout(function(){ try { inp.focus(); } catch(e){} }, 80); } } catch(e){}
})();
"""
