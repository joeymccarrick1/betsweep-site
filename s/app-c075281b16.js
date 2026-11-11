
(function(){
  // ---- 11/4 UX audit: three site-wide behaviours ----
  // 1. game deep links: the home page and Today link to /boards/#g-BAL-JAX, the boards card is id="BAL-JAX", the builder's is "g-BAL-JAX" and
  //    the Live page's is "lv-BAL-JAX" - land on the game whichever form the link used
  function landOnHash(){ var h = (location.hash || '').slice(1); if(!h) return; var el = document.getElementById(h);
    if(!el){ var m = h.match(/^(?:g-|lv-|box-|td-)?([A-Z]{2,3}-[A-Z]{2,3})$/); if(!m) return;
      el = ['g-' + m[1], 'lv-' + m[1], 'td-' + m[1], m[1]].map(function(id){ return document.getElementById(id); }).filter(Boolean)[0]; if(!el) return; }
    if(el.classList.contains('gcard') || el.classList.contains('lg2') || el.classList.contains('tdgame')) el.classList.add('open');
    if(el.classList.contains('card')) el.classList.add('expanded');   // boards card (template.html folds .card:not(.expanded) on phones)
    var det = el.querySelector('details'); if(det && el.tagName !== 'DETAILS') det.open = true;
    setTimeout(function(){
      // land just below the sticky chrome as it will look once scrolled (the header compacts on scroll), whatever the page's own margins
      document.body.classList.add('bs-scrolled');
      var nav = document.querySelector('.sitenav'), top = document.querySelector('.top');
      var chrome = (nav ? nav.getBoundingClientRect().height : 0) + (top && getComputedStyle(top).position === 'sticky' ? top.getBoundingClientRect().height : 0) + 8;
      var y = el.getBoundingClientRect().top + (window.scrollY || 0) - chrome; window.scrollTo(0, Math.max(0, y)); lastY = y; }, 60); }
  window.addEventListener('load', landOnHash); window.addEventListener('hashchange', landOnHash);
  // 1b. 11/10 evening: on a phone the first screen of many pages was the title and eight lines of explanation. An introduction longer
  //     than about three lines folds to three with a "More" button; nothing is removed, and wide screens are untouched.
  function foldIntro(){ if(!window.matchMedia || !matchMedia('(max-width:760px)').matches) return;
    [].slice.call(document.querySelectorAll('h1 + p, h1 + .sub, h1 + .lead, h1 + .lede')).forEach(function(p){
      if(p.closest('.sitenav, .top, article, .tdhead, .bssrch, dialog') || p.dataset.fold) return; p.dataset.fold = '1';
      if((p.textContent || '').trim().length < 190) return;
      p.classList.add('bsclamp'); var b = document.createElement('button'); b.type = 'button'; b.className = 'bsmore'; b.textContent = 'More'; b.setAttribute('aria-expanded', 'false');
      b.addEventListener('click', function(){ var open = p.classList.toggle('bsclamp') === false; b.textContent = open ? 'Less' : 'More'; b.setAttribute('aria-expanded', open); });
      p.parentNode.insertBefore(b, p.nextSibling); }); }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', foldIntro); else foldIntro();
  // 2. the page's sticky header collapses while scrolling down (CSS: body.bs-scrolled; phones hide the mast, desktop keeps title + chips)
  var lastY = 0; window.addEventListener('scroll', function(){ var y = window.scrollY || 0; if(y > 140 && y > lastY + 4) document.body.classList.add('bs-scrolled'); else if(y < lastY - 12 || y < 80) document.body.classList.remove('bs-scrolled'); lastY = y; }, {passive: true});
  // 3. player search from any page: /b/players.json (name, slug, team, pos, opp, has props) -> player page, builder, boards
  var sb = document.getElementById('bssrchbtn');
  if(sb){ var IDX = null, box = null, list = null, inp = null, sel = 0;
    function build(){ box = document.createElement('div'); box.className = 'bssrch'; box.innerHTML = '<div class="box"><div class="row"><input type="search" placeholder="Player, team or position" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="Find a player"><button type="button" class="x" aria-label="Close">×</button></div><ul></ul><div class="hint">Tap a name for his page. Builder opens his legs in the Parlay Builder; Board opens his game. Type a team code (BUF) or a position (TE).</div></div>'; document.body.appendChild(box); inp = box.querySelector('input'); list = box.querySelector('ul');
      box.addEventListener('click', function(e){ if(e.target === box || e.target.classList.contains('x')) close(); }); inp.addEventListener('input', function(){ sel = 0; render(); });
      inp.addEventListener('keydown', function(e){ var items = list.querySelectorAll('li'); if(e.key === 'ArrowDown'){ sel = Math.min(sel + 1, items.length - 1); paint(); e.preventDefault(); } else if(e.key === 'ArrowUp'){ sel = Math.max(sel - 1, 0); paint(); e.preventDefault(); } else if(e.key === 'Enter'){ var a = items[sel] && items[sel].querySelector('a.pl'); if(a) location.href = a.getAttribute('href'); } else if(e.key === 'Escape') close(); }); }
    function paint(){ list.querySelectorAll('li').forEach(function(li, i){ li.classList.toggle('on', i === sel); }); }
    function norm(s){ return String(s || '').toLowerCase().replace(/[.'\u2019]/g, ''); }
    function render(){ var q = norm(inp.value).trim(); if(!IDX){ list.innerHTML = '<li><a class="pl">Loading players…</a></li>'; return; }
      var terms = q.split(/\s+/).filter(Boolean); var hits = !terms.length ? [] : IDX.filter(function(p){ var hay = norm(p.n) + ' ' + norm(p.t) + ' ' + norm(p.p) + ' ' + norm(p.o); return terms.every(function(t){ return hay.indexOf(t) >= 0; }); });
      hits.sort(function(a, b){ var an = norm(a.n).indexOf(terms[0]) === 0 ? 0 : 1, bn = norm(b.n).indexOf(terms[0]) === 0 ? 0 : 1; return an - bn || (b.l - a.l) || a.n.localeCompare(b.n); });
      list.innerHTML = hits.slice(0, 12).map(function(p){ var gid = p.t && p.o ? [p.t, p.o].sort().join('-') : ''; return '<li><a class="pl" href="/player/' + p.s + '/">' + esc(p.n) + '<small>' + esc(p.p) + ' · ' + esc(p.t) + (p.o ? ' ' + (p.o === 'BYE' ? '· bye' : 'vs ' + esc(p.o)) : '') + (p.l ? ' · props this week' : '') + '</small></a><span class="go">' + (p.l ? '<a href="/build/?p=' + encodeURIComponent(p.n) + '">Builder</a>' : '') + (gid && p.o !== 'BYE' ? '<a href="/boards/#' + gid + '">Board</a>' : '') + '</span></li>'; }).join('') || (terms.length ? '<li><a class="pl">No player, team or position matches "' + esc(inp.value) + '"</a></li>' : ''); paint(); }
    function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
    function open(){ if(!box) build(); box.classList.add('open'); inp.value = ''; list.innerHTML = ''; setTimeout(function(){ inp.focus(); }, 30);
      if(!IDX){ fetch('/b/players.json', {cache: 'force-cache'}).then(function(r){ return r.ok ? r.json() : []; }).then(function(j){ IDX = Array.isArray(j) ? j : []; render(); }).catch(function(){ IDX = []; render(); }); } }
    function close(){ if(box) box.classList.remove('open'); }
    sb.addEventListener('click', open);
    document.addEventListener('keydown', function(e){ if((e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey))) && !/input|textarea|select/i.test((document.activeElement || {}).tagName || '')){ e.preventDefault(); open(); } }); }
  // full-bleed header: inner pages pad/margin the body, so measure the nav's inset and pull it back to the viewport edge
  function bleed(){ var n = document.getElementById('sitenav'); if(!n) return; var d = document.documentElement.style; d.setProperty('--bs-inset', '0px'); var l = Math.round(n.getBoundingClientRect().left); if(l > 0) d.setProperty('--bs-inset', l + 'px'); }
  window.addEventListener('resize', bleed); window.addEventListener('orientationchange', bleed);
  if('serviceWorker' in navigator){ window.addEventListener('load', function(){ navigator.serviceWorker.register('/sw.js').catch(function(){}); }); }
  // install hint: Chrome/Android fire beforeinstallprompt; iOS gets a one-line how-to. Dismissal is remembered for 30 days.
  var bar = document.getElementById('installbar'); if(!bar) return;
  var dismissed = 0; try { dismissed = +localStorage.getItem('bs_install_dismissed') || 0; } catch(e){}
  var standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  if(standalone || Date.now() - dismissed < 30*864e5) return;
  var deferred = null;
  window.addEventListener('beforeinstallprompt', function(e){ e.preventDefault(); deferred = e; bar.querySelector('.msg').textContent = 'Add BetSweep to your home screen - opens full screen, works like an app.'; bar.querySelector('.go').hidden = false; bar.classList.add('show'); });
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
  if(ios){ bar.querySelector('.msg').innerHTML = 'Install BetSweep: tap <b>Share</b> then <b>Add to Home Screen</b>.'; bar.classList.add('show'); }
  bar.querySelector('.go').addEventListener('click', function(){ if(deferred){ deferred.prompt(); deferred = null; } bar.classList.remove('show'); });
  bar.querySelector('.x').addEventListener('click', function(){ bar.classList.remove('show'); try { localStorage.setItem('bs_install_dismissed', String(Date.now())); } catch(e){} });
})();
(function(){
  // 11/4 UX audit: Theme switch (Auto / Dark / Light). Auto follows the phone; the choice is kept in localStorage and applied before
  // paint by the one-line script in <head>. Home stays dark (hero landing); every app page honours data-theme.
  // 11/11 (owner: "put theme in My Betsweep rather than the menu"): the buttons are a card on /me/ (account.me_page); this binds any .thm group.
  var gs = [].slice.call(document.querySelectorAll('.thm')); if(!gs.length) return;
  function cur(){ try { var t = localStorage.getItem('bs_theme'); return (t === 'dark' || t === 'light') ? t : 'auto'; } catch(e){ return 'auto'; } }
  function paint(){ var c = cur(); gs.forEach(function(g){ g.querySelectorAll('button[data-thm]').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-thm') === c); b.setAttribute('aria-pressed', b.getAttribute('data-thm') === c ? 'true' : 'false'); }); }); }
  gs.forEach(function(g){ g.addEventListener('click', function(e){
    var b = e.target.closest('button[data-thm]'); if(!b) return;
    var t = b.getAttribute('data-thm');
    try { if(t === 'auto') localStorage.removeItem('bs_theme'); else localStorage.setItem('bs_theme', t); } catch(err){}
    if(t === 'auto') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', t);
    paint();
  }); });
  window.addEventListener('storage', function(e){ if(e.key === 'bs_theme') paint(); });
  paint();
})();

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

/* page counts (owner 11/10): one anonymous +1 per page view - the page's path and nothing else. No cookie, no id. Skipped when the browser sends Do Not Track or Global Privacy Control. */
(function(){ try{ var n = navigator; if(n.globalPrivacyControl || n.doNotTrack === '1' || window.doNotTrack === '1') return; if(/bot|crawl|spider|headless|lighthouse/i.test(n.userAgent || '')) return;
  var p = location.pathname.toLowerCase().replace(/index\.html$/, ''); if(!/^\/[a-z0-9\/_-]*$/.test(p) || p.length > 80) return;
  fetch('https://fuwiqijgkgbzvnfnsans.supabase.co/rest/v1/rpc/hit', {method: 'POST', keepalive: true, headers: {'Content-Type': 'application/json', apikey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1d2lxaWpna2dienZuZm5zYW5zIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI1NDMxNzMsImV4cCI6MjEwODExOTE3M30.cHHSmNne8GWkMvVO5n3DRIyrmC2D0hmpI8DNbOxs7eU', Authorization: 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1d2lxaWpna2dienZuZm5zYW5zIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI1NDMxNzMsImV4cCI6MjEwODExOTE3M30.cHHSmNne8GWkMvVO5n3DRIyrmC2D0hmpI8DNbOxs7eU'}, body: JSON.stringify({p: p})}).catch(function(){}); }catch(e){} })();
