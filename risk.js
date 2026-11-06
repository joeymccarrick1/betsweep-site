(function(){var s=document.createElement('style');s.textContent="\n.bsrmv{display:inline-flex;align-items:center;margin-left:6px;padding:1px 7px;border-radius:99px;font:600 11px/1.5 'IBM Plex Sans',system-ui,sans-serif;border:1px solid #2a8a4a;color:#2a8a4a;white-space:nowrap} .bsrmv.dn{border-color:#b7791f;color:#b7791f}\n.bsrzone{margin:0 0 8px;padding:7px 10px;border-radius:8px;background:color-mix(in srgb,#c98a12 16%,transparent);border:1px solid #c98a12;font-size:12.5px} .bsrdead{margin:0 0 8px;padding:8px 10px;border-radius:8px;background:color-mix(in srgb,#d7332a 18%,transparent);border:1px solid #d7332a;color:inherit;font-size:13px;font-weight:600} .bsr-dead{outline:2px solid #d7332a;outline-offset:-2px} .bsrhid{grid-column:1/-1;margin:6px 0;font-size:12.5px;color:#d7332a} .bsrc{display:inline-flex;align-items:center;gap:2px;margin-left:6px;padding:1px 7px;border-radius:99px;font:600 11px/1.5 'IBM Plex Sans',system-ui,sans-serif;letter-spacing:0;text-transform:none;vertical-align:middle;white-space:nowrap;cursor:help}\n.bsr-block{background:#b3261e;color:#fff} .bsr-warn{background:#f6e3b4;color:#6b4a00} .bsr-good{background:#dcefdc;color:#1f5d2b}\nbutton.bsrblock{opacity:.35;filter:grayscale(1)}\n#bsrpill{position:fixed;left:12px;right:12px;bottom:calc(var(--bs-tabs, 0px) + 74px);z-index:65;max-width:420px;margin:0 auto;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.3);font:14px/1.4 'IBM Plex Sans',system-ui,sans-serif;cursor:pointer;overflow:hidden}\n#bsrpill.warn{background:#fff4d6;color:#4d3600;border:1px solid #e3c477} #bsrpill.bad{background:#fde7e5;color:#5c120d;border:1px solid #e8a39d}\n#bsrpill .bsrh{padding:10px 14px;font-weight:700} #bsrpill .bsrb{display:none;padding:0 14px 12px} #bsrpill.open .bsrb{display:block}\n#bsrpill ul{margin:0 0 10px;padding:0;list-style:none;display:grid;gap:6px} #bsrpill li small{display:block;opacity:.8;font-size:12.5px}\n#bsrpill button{font:inherit;font-weight:700;font-size:13px;padding:7px 12px;border-radius:8px;border:0;background:#b3261e;color:#fff;margin-right:6px;cursor:pointer} #bsrpill button.sec{background:none;border:1px solid currentColor;color:inherit}\n.bsrtoast{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(var(--bs-tabs, 0px) + 20px);z-index:80;background:#141a24;color:#fff;padding:10px 14px;border-radius:10px;font:600 13.5px 'IBM Plex Sans',system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.35);max-width:90vw}\n.bsrnote{margin:12px 0 16px;padding:12px 14px;background:var(--card,#fff);border:1px solid var(--line,#d8d1c2);border-left:4px solid #d7332a;border-radius:10px;font-size:14px;line-height:1.4;font-style:normal;text-align:left}\n.bsrnote .bsrh{display:flex;align-items:baseline;justify-content:space-between;gap:8px;flex-wrap:wrap}\n.bsrnote .bsrh b{font-family:var(--display,inherit);font-weight:800;letter-spacing:.05em;text-transform:uppercase;font-size:13px}\n.bsrnote .bsrh span{font-size:11.5px;color:var(--mute,#6b655c);border:1px solid var(--line,#d8d1c2);border-radius:99px;padding:1px 8px}\n.bsrnote p{margin:4px 0 10px;color:var(--mute,#6b655c);font-size:12.5px}\n.bsrnote .row{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.4fr) auto;gap:8px;align-items:stretch}\n@media (max-width:560px){.bsrnote .row{grid-template-columns:1fr auto}.bsrnote .row select{grid-column:1/-1}}\n.bsrnote select,.bsrnote input{box-sizing:border-box;width:100%;font:inherit;font-size:16px;padding:9px 10px;border:1px solid var(--line,#d8d1c2);border-radius:8px;background:var(--paper,var(--bg,#fff));color:var(--ink,inherit)}\n.bsrnote button{font:inherit;font-weight:700;font-size:15px;padding:9px 16px;border-radius:8px;border:0;background:#d7332a;color:#fff;cursor:pointer}\n.bsrnote small#bsrmsg{display:block;margin-top:6px;font-size:12.5px;color:var(--mute,#6b655c)}\n@media (min-width:761px){ #bsrpill{left:auto;right:16px;bottom:16px;margin:0} }\n";document.head.appendChild(s);})();
(function(){
  if (window.BSRisk) return;
  var SB = 'https://fuwiqijgkgbzvnfnsans.supabase.co', KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1d2lxaWpna2dienZuZm5zYW5zIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI1NDMxNzMsImV4cCI6MjEwODExOTE3M30.cHHSmNne8GWkMvVO5n3DRIyrmC2D0hmpI8DNbOxs7eU';
  function nrm(s){ return String(s || '').replace(/\./g, '').trim().replace(/\s+(jr|sr|ii|iii|iv|v)$/i, '').replace(/\s+/g, ' ').toLowerCase(); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  var WXM = /^(Passing Yards|Receiving Yards|Receptions|Longest Reception|Rush \+ Rec Yards)$/;
  var P = {}, WX = {}, ROWS = [], loaded = false;
  function index(rows){ P = {}; WX = {}; ROWS = rows || [];
    ROWS.forEach(function(r){
      if (r.kind === 'weather'){ (r.players || []).forEach(function(n){ (WX[nrm(n)] = WX[nrm(n)] || []).push(r); }); return; }
      if (!r.player) return; (P[nrm(r.player)] = P[nrm(r.player)] || []).push(r); }); }
  // one verdict per player (+ market for weather): the worst of injury / owner note / weather
  function verdict(pl, m){ var n = nrm(pl), out = null, rk = {block: 3, warn: 2, good: 1};
    (P[n] || []).forEach(function(r){ var v = r.kind === 'note' ? noteV(r) : injV(r); if (v && (!out || rk[v.level] > rk[out.level])) out = v; });
    if ((!out || out.level !== 'block') && (WX[n] || []).length && (!m || WXM.test(String(m).replace(/^Under /, '')))){
      var w = WX[n][0]; if (!/^Under /.test(m || '')){ var v2 = {level: 'warn', label: 'Weather', why: w.detail || 'wind / rain at kickoff', short: 'Weather'}; if (!out || out.level === 'good') out = v2; } }
    return out; }
  // owner 11/6 Questionable translator: feeds q.json (this week's official report) adds the last practice and the chance he plays
  var QT = {}; function loadQ(){ try { fetch('https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/q.json', {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(j){ var o = {}; Object.keys((j && j.players) || {}).forEach(function(k){ o[nrm(k)] = j.players[k]; }); QT = o; decorate(); }).catch(function(){}); } catch(e){} }
  setTimeout(loadQ, 900); setInterval(loadQ, 6e5);
  var PW = {Full: 'full practice', Limited: 'limited in practice', DNP: 'did not practice', none: 'no practice listed'};
  function qtx(n){ var q = QT[nrm(n)]; return q && q.play != null ? q : null; }
  function injV(r){ var s = r.status;
    if (s === 'OUT') return {level: 'block', label: 'Ruled out', why: 'Out' + (r.detail ? ' (' + r.detail + ')' : '') + ' on the injury report', short: 'Out'};
    var q = qtx(r.player || '');
    if (s === 'DOUBTFUL') return {level: 'warn', label: 'Doubtful', why: 'Doubtful' + (r.detail ? ' (' + r.detail + ')' : '') + ' - none of 61 doubtful starters played in 2024-25', short: 'Doubtful'};
    if (s === 'QUESTIONABLE') return {level: 'warn', label: q ? 'Q · plays ~' + Math.round(q.play * 100) + '%' : 'Questionable', why: 'Questionable' + (r.detail ? ' (' + r.detail + ')' : '') + (q ? ' - ' + PW[q.ps] + ': players in this spot played ' + Math.round(q.play * 100) + '% of the time in 2024-25, and when they played got ~' + Math.round((q.snap || 0.9) * 100) + '% of their usual snaps' : ''), short: 'Q'};
    return null; }
  function noteV(r){ var d = r.detail ? ': ' + r.detail : '';
    if (r.status === 'OUT') return {level: 'block', label: 'Ruled out', why: 'BetSweep note - out' + d, short: 'Out'};
    if (r.status === 'HURT') return {level: 'warn', label: 'Hurt', why: 'BetSweep note - playing hurt' + d, short: 'Hurt'};
    if (r.status === 'LIMITED') return {level: 'warn', label: 'Limited', why: 'BetSweep note - limited role' + d, short: 'Limited'};
    if (r.status === 'STARTING') return {level: 'good', label: 'Starting', why: 'BetSweep note - starting' + d, short: 'Starting'};
    if (r.status === 'ROLE_UP') return {level: 'good', label: 'Role up', why: 'BetSweep note - bigger role' + d, short: 'Role up'};
    return null; }
  function chip(v){ return '<span class="bsrc bsr-' + v.level + '" title="' + esc(v.why) + '">' + (v.level === 'block' ? '⛔ ' : v.level === 'warn' ? '⚠ ' : '▲ ') + esc(v.label) + '</span>'; }
  // ---- decorate names wherever they appear ----
  function hosts(){ var out = [];
    document.querySelectorAll('.lg[data-orig]').forEach(function(el){ var q = el.getAttribute('data-orig').split('|'); var a = el.querySelector('a.pname'); if (a) out.push([a, q[0], q[1]]); });
    document.querySelectorAll('.pc[data-pk]').forEach(function(el){ var a = el.querySelector('a.pname'); if (a) out.push([a, el.getAttribute('data-pk').split('|')[0], null]); });
    document.querySelectorAll('tr[data-k]').forEach(function(el){ var q = el.getAttribute('data-k').split('|'); var b = el.querySelector('td.who b'); if (b) out.push([b, q[0], q[1]]); });
    document.querySelectorAll('span.nm').forEach(function(el){ var t = (el.firstChild && el.firstChild.nodeType === 3) ? el.firstChild.nodeValue : el.textContent; out.push([el, t.trim(), null]); });
    document.querySelectorAll('ul.legs > li > b').forEach(function(el){ var sm = el.parentNode.querySelector('small'); out.push([el, el.textContent.trim(), sm ? mkt(sm.textContent) : null]); });
    var h = document.querySelector('.pp h1'); if (h){ var t2 = (h.firstChild && h.firstChild.nodeType === 3) ? h.firstChild.nodeValue : h.textContent; out.push([h, t2.trim(), null]); }
    return out; }
  function mkt(t){ t = String(t).toLowerCase(); return /passing/.test(t) ? 'Passing Yards' : /receiving|reception|rec /.test(t) ? 'Receiving Yards' : /rushing/.test(t) ? 'Rushing Yards' : null; }
  var MOVES = {};
  function loadMoves(){ try { fetch('/data/price-moves.json', {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(j){ MOVES = {}; if (j && Array.isArray(j.moves)) j.moves.forEach(function(m){ if (m.key) MOVES[m.key] = m; }); decorate(); }).catch(function(){}); } catch(e){} }
  loadMoves(); setInterval(loadMoves, 10 * 60e3);
  var busy = false;
  function decorate(){ if (!loaded || busy) return; busy = true;
    try {
      hosts().forEach(function(h){ var el = h[0], v = verdict(h[1], h[2]); var cur = el.querySelector(':scope > .bsrc');
        var html = v ? chip(v) : ''; if (cur && cur.outerHTML === html) return; if (cur) cur.remove(); if (v) el.insertAdjacentHTML('beforeend', ' ' + html); });
      document.querySelectorAll('[data-k]').forEach(function(b){ if (b.tagName !== 'BUTTON') return; var q = b.getAttribute('data-k').split('|'), v = verdict(q[0], q[1]);
        b.classList.toggle('bsrblock', !!(v && v.level === 'block')); if (v && v.level === 'block') b.title = q[0] + ': ' + v.why;
        // price moves (11/4): a chip on any leg button whose FanDuel price moved 3+ implied points since the build (data/price-moves.json)
        var mv = MOVES[b.getAttribute('data-k')]; var host = b.closest('tr, .pb, .lg, .gdp, .sp, li') || b.parentNode; if (!host) return; var cur = host.querySelector(':scope .bsrmv');
        var html = mv ? '<span class="bsrmv ' + (mv.value ? 'up' : mv.dir === 'SHORTENED' ? 'up' : 'dn') + '" title="' + esc(mv.detail) + '">' + (mv.value ? '💰 better price now ' + (mv.now > 0 ? '+' : '') + Math.round(mv.now) : (mv.dir === 'SHORTENED' ? '📈 market moving our way ' : '📉 market drifted ') + (mv.pts > 0 ? '+' : '') + mv.pts) + '</span>' : '';
        if (cur && cur.outerHTML === html) return; if (cur) cur.remove(); if (mv) { var anchor = host.querySelector('.who b, .pbn, b') || b; anchor.insertAdjacentHTML('afterend', ' ' + html); } });
      pill(); stale();
    } catch(e){} busy = false; }
  // owner 11/5 "lists that don't go stale on Sunday morning": a ruled-out player (injury report, game-day inactive, owner OUT note) drops off
  // Model's Best / single-pick cards right away, and any listed parlay holding him gets a red "swap this leg" banner - no rebuild needed.
  var ZONES = null; function loadZones(){ try { fetch('/data/zones.json', {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(j){ ZONES = (j && j.zones) || {}; decorate(); }).catch(function(){}); } catch(e){} }
  setTimeout(loadZones, 800);
  function stale(){
    var nameOf = function(el){ var t = (el.firstChild && el.firstChild.nodeType === 3) ? el.firstChild.nodeValue : el.textContent; return String(t || '').trim(); };
    var hidden = new Map();
    document.querySelectorAll('article.play, .bestslip').forEach(function(card){
      var names = []; card.querySelectorAll('.who b, ul.plegs li b, ul.pl li b, ul.legs li b, span.nm').forEach(function(e){ var n = nameOf(e); if (n && names.indexOf(n) < 0) names.push(n); });
      card.querySelectorAll('[data-k]').forEach(function(e){ var n = String(e.getAttribute('data-k') || '').split('|')[0].trim(); if (n && names.indexOf(n) < 0) names.push(n); });
      var out = names.filter(function(n){ var v = verdict(n, null); return v && v.level === 'block'; });
      var multi = card.matches('.bestslip') || !!card.querySelector('ul.plegs, ul.pl, ul.legs');
      var ban = card.querySelector(':scope > .bsrdead');
      // 11/6 edge map: a listed parlay leg in a losing zone gets an amber note (the next rebuild leaves it out)
      if (ZONES && card.matches('.bestslip')){ var lz = []; card.querySelectorAll('[data-k]').forEach(function(e){ var k = e.getAttribute('data-k'), z = ZONES[k]; if (z && z[0] === 'r' && lz.indexOf(k.split('|')[0]) < 0) lz.push(k.split('|')[0]); });
        var zb = card.querySelector(':scope > .bsrzone'), zh = lz.length ? '<div class="bsrzone">⚠ ' + esc(lz.join(', ')) + ': this kind of leg sits in a losing zone (model edges there have lost money) - consider a swap.</div>' : '';
        if (zh && (!zb || zb.outerHTML !== zh)){ if (zb) zb.remove(); card.insertAdjacentHTML('afterbegin', zh); } else if (!zh && zb) zb.remove(); }
      if (!out.length){ if (ban) ban.remove(); card.classList.remove('bsr-dead'); if (card.dataset.bsrHid){ card.style.display = ''; delete card.dataset.bsrHid; } return; }
      if (multi){ var html = '<div class="bsrdead">⛔ ' + esc(out.join(', ')) + ' ruled out since this was built - swap ' + (out.length > 1 ? 'those legs' : 'that leg') + ' before betting.</div>';
        if (!ban || ban.outerHTML !== html){ if (ban) ban.remove(); card.insertAdjacentHTML('afterbegin', html); } card.classList.add('bsr-dead'); }
      else { card.style.display = 'none'; card.dataset.bsrHid = '1'; var par = card.parentNode; hidden.set(par, (hidden.get(par) || []).concat(out)); }
    });
    document.querySelectorAll('.bsrhid').forEach(function(n){ if (!hidden.has(n.parentNode)) n.remove(); });
    hidden.forEach(function(ns, par){ var note = par.querySelector(':scope > .bsrhid'), html = '<div class="bsrhid">⛔ Hidden since the build: ' + esc(ns.join(', ')) + ' (ruled out).</div>';
      if (!note || note.outerHTML !== html){ if (note) note.remove(); par.insertAdjacentHTML('beforeend', html); } });
  }
  // ---- the open betslip ----
  function slipKey(){ var best = null, w = -1; try{ for (var i = 0; i < localStorage.length; i++){ var k = localStorage.key(i), m = /^bs_slipk_w(\d+)$/.exec(k || ''); if (m && +m[1] > w){ w = +m[1]; best = k; } } }catch(e){} return best; }
  function slipRisk(){ var k = slipKey(); if (!k) return []; var keys = []; try{ keys = JSON.parse(localStorage.getItem(k) || '[]') || []; }catch(e){}
    return keys.map(function(x){ var q = String(x).split('|'); var v = verdict(q[0], q[1]); return v && v.level !== 'good' ? {k: x, pl: q[0], m: q[1], v: v} : null; }).filter(Boolean); }
  function pill(){ var rs = slipRisk(), el = document.getElementById('bsrpill');
    if (!rs.length){ if (el) el.remove(); return; }
    if (!el){ el = document.createElement('div'); el.id = 'bsrpill'; document.body.appendChild(el);
      el.addEventListener('click', function(e){ var b = e.target.closest('button'); if (!b) { el.classList.toggle('open'); return; }
        if (b.dataset.act === 'rm'){ var k = slipKey(), keys = []; try{ keys = JSON.parse(localStorage.getItem(k) || '[]') || []; }catch(x){}
          var bad = {}; slipRisk().forEach(function(r){ if (r.v.level === 'block') bad[r.k] = 1; }); keys = keys.filter(function(x){ return !bad[x]; });
          try{ localStorage.setItem(k, JSON.stringify(keys)); }catch(x){} location.reload(); }
        if (b.dataset.act === 'x') el.classList.remove('open'); }); }
    var nb = rs.filter(function(r){ return r.v.level === 'block'; }).length;
    el.className = (el.className.indexOf('open') >= 0 ? 'open ' : '') + (nb ? 'bad' : 'warn');
    el.innerHTML = '<div class="bsrh">' + (nb ? '⛔ ' : '⚠ ') + rs.length + ' leg' + (rs.length === 1 ? '' : 's') + ' in your betslip ' + (rs.length === 1 ? 'is' : 'are') + ' at risk</div>' +
      '<div class="bsrb"><ul>' + rs.map(function(r){ return '<li><b>' + esc(r.pl) + '</b> ' + esc(r.m || '') + '<small>' + esc(r.v.why) + '</small></li>'; }).join('') + '</ul>' +
      (nb ? '<button type="button" data-act="rm">Remove ruled-out legs</button>' : '') + '<button type="button" data-act="x" class="sec">Close</button></div>'; }
  // ---- block adds of ruled-out players ----
  document.addEventListener('click', function(e){ var b = e.target.closest && e.target.closest('button.bsrblock'); if (!b) return;
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation(); toast(b.title || 'Ruled out'); }, true);
  function toast(t){ var d = document.createElement('div'); d.className = 'bsrtoast'; d.textContent = '⛔ ' + t + ' - not added'; document.body.appendChild(d); setTimeout(function(){ d.remove(); }, 3200); }
  // ---- fetch ----
  function load(){ return fetch(SB + '/rest/v1/risk_feed?select=id,kind,week,player,team,gid,status,level,detail,players,updated_at', {headers: {apikey: KEY, Authorization: 'Bearer ' + KEY}, cache: 'no-store'})
    .then(function(r){ return r.ok ? r.json() : []; }).catch(function(){ return []; }).then(function(rows){ index(Array.isArray(rows) ? rows : []); loaded = true; decorate(); owner(); document.dispatchEvent(new CustomEvent('bs-risk')); }); }
  var mo = null, tmr = null; function watch(){ if (mo || !window.MutationObserver) return; mo = new MutationObserver(function(){ clearTimeout(tmr); tmr = setTimeout(decorate, 250); }); mo.observe(document.body, {childList: true, subtree: true}); }
  window.addEventListener('storage', function(e){ if (/^bs_slipk_w/.test(e.key || '')) pill(); });
  // ---- the owner's note panel on player pages ----
  var ownerChecked = false;
  // owner 11/5: "I don't think we need the Your BetSweep note section" - the panel is off; owner notes still come from the sheet (RUNBOOK Step 2a)
  function owner(){ return; var pp = document.querySelector('.pp h1'); if (!pp || ownerChecked) return; var A = window.bsAccount; if (!A || !A.client || !A.user) return; ownerChecked = true;
    A.client.rpc('bs_is_admin').then(function(r){ if (!r || r.data !== true) return; var name = ((pp.firstChild && pp.firstChild.nodeType === 3) ? pp.firstChild.nodeValue : pp.textContent).trim();
      var cur = (P[nrm(name)] || []).filter(function(x){ return x.kind === 'note'; })[0] || {};
      var box = document.createElement('div'); box.className = 'bsrnote';
      box.innerHTML = '<div class="bsrh"><b>Your BetSweep note</b><span>Only you see this box</span></div><p>Shows on every page within minutes; the next rebuild adjusts his numbers.</p><div class="row">' +
        '<select id="bsrst">' + [['', '- none -'], ['HURT', 'Hurt / playing through it'], ['LIMITED', 'Limited role'], ['OUT', 'Out'], ['STARTING', 'Starting'], ['ROLE_UP', 'Role up']].map(function(o){ return '<option value="' + o[0] + '"' + (cur.status === o[0] ? ' selected' : '') + '>' + o[1] + '</option>'; }).join('') + '</select>' +
        '<input id="bsrdt" maxlength="200" placeholder="e.g. could barely walk last week" value="' + esc(cur.detail || '') + '"><button type="button" id="bsrsv">Save</button></div><small id="bsrmsg"></small>';
      var hd = pp.closest('header') || pp; hd.parentNode.insertBefore(box, hd.nextSibling);   // below the whole name / team header, full width
      document.getElementById('bsrsv').addEventListener('click', function(){ var st = document.getElementById('bsrst').value, dt = document.getElementById('bsrdt').value.trim().slice(0, 200), id = 'note|' + nrm(name), msg = document.getElementById('bsrmsg');
        var W = +((document.querySelector('.pp') || {}).getAttribute ? document.querySelector('.pp').getAttribute('data-week') : 0) || 0;
        var q = !st ? A.client.from('risk_feed').delete().eq('id', id)
          : A.client.from('risk_feed').upsert({id: id, kind: 'note', week: W, player: name, status: st, level: (st === 'OUT' ? 'block' : (st === 'STARTING' || st === 'ROLE_UP') ? 'good' : 'warn'), detail: dt || null, by_owner: true, updated_at: new Date().toISOString()});
        q.then(function(r){ msg.textContent = r && r.error ? 'Could not save: ' + r.error.message : (st ? 'Saved - live on every page now.' : 'Cleared.'); load(); }); }); }); }
  document.addEventListener('bs-account', function(){ owner(); });
  window.BSRisk = {blockAdd: function(pl, m){ var v = verdict(pl, m); if (v && v.level === 'block'){ toast(pl + ': ' + v.why); return true; } return false; }, verdict: verdict, avoid: function(pl, m){ var v = verdict(pl, m); return !!(v && v.level !== 'good'); }, rows: function(){ return ROWS; }, reload: load};
  function start(){ watch(); load(); setInterval(load, 180000); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
