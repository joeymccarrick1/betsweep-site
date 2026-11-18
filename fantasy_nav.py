#!/usr/bin/env python3
"""fantasy_nav.py - the two pieces the Fantasy page and the Trade calculator share so a manager with many Sleeper leagues is not
scrolling for his league or for the section he came for (owner 11/17: "make the fantasy page and trade calculator a little more
intuitive and maybe condensed. It's a lot of scrolling to find what you're looking for. I have a ton of sleeper teams").

Measured before, phone (390x844), a 14-league account: Trade calculator 19.6 screens - the league buttons alone 0.6 of a screen,
the import box 1.2 screens down, the rankings table 13.7 screens; Fantasy 8.2 screens with two intro cards filling the first one.

  bsTabs  one row of section tabs that stays under the site bar; one section on screen at a time. Sections are wrapped in
          <div data-tab="id"> so the page's own show / hide logic on its panels is left alone.
  bsLg    the league bar (the league on screen, its record, a verdict chip when the page has one) and the sheet behind it: every
          league in one tight list with a search box past eight, each row filling in its record (one Sleeper call per league,
          three at a time, kept for half an hour) and, where the page gives an `extra` hook, its buy / hold / sell chip.

Both are plain functions on window; a page calls bsTabs.mount(...) and bsLg.mount(...) and keeps its own connect / pick code.
CSS uses the site's variables only. The tab buttons carry class "tab" inside ".tabs" and take the site's segmented-control look
(build_site.py)."""

CSS = r"""
/* ---- section tabs (fantasy_nav.py) ---- */
.fxtabs{position:sticky;top:calc((53px + env(safe-area-inset-top,0px)) / 1.1);z-index:6;display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;background:var(--bg);padding:8px 0;margin:0 0 12px;border-bottom:1px solid var(--line)}
.fxtabs::-webkit-scrollbar{display:none}
.fxtabs .tab{flex:1 0 auto;white-space:nowrap;min-height:40px}
.fxtabs .tab small{font:inherit;font-size:11.5px;opacity:.75;margin-left:2px}
.fxoff{display:none!important}
@media (min-width:900px){ .fxtabs{top:0} .fxtabs .tab{flex:0 0 auto} }
/* ---- league bar + sheet ---- */
.lgbar{margin:0 0 10px}
.lgbar[hidden]{display:none}
.lgbar .lgcur{display:flex;align-items:center;gap:10px;width:100%;text-align:left;font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 12px;min-height:54px;cursor:pointer}
.lgbar .lgcur .lgtx,.lgrow .lgtx{flex:1;min-width:0}
.lgbar .lgcur b,.lgrow b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lgbar .lgcur b{font-family:var(--display);font-size:18px;line-height:1.15;letter-spacing:.01em}
.lgbar .lgcur small,.lgrow small{display:block;color:var(--mute);font-size:12px;line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lgbar .lgcur .lgsx{flex:none;font-family:var(--ctl,var(--display));font-weight:700;font-size:12.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--red);white-space:nowrap}
.lgchip{flex:none;display:inline-block;font-size:11.5px;font-weight:700;line-height:1;border-radius:999px;padding:4px 8px;border:1px solid var(--line);color:var(--mute);white-space:nowrap}
.lgchip.buy{color:var(--good);border-color:var(--good)} .lgchip.sell{color:var(--bad);border-color:var(--bad)}
html.lgopen{overflow:hidden}
.lgov{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.55);display:flex;align-items:flex-end;justify-content:center}
.lgsheet{width:100%;max-width:560px;max-height:84vh;display:flex;flex-direction:column;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-bottom:0;border-radius:16px 16px 0 0;padding-bottom:env(safe-area-inset-bottom,0px)}
@media (min-width:700px){ .lgov{align-items:center} .lgsheet{border-bottom:1px solid var(--line);border-radius:16px;max-height:78vh} }
.lgsheet header{display:flex;align-items:center;gap:10px;padding:14px 16px 6px}
.lgsheet header h3{flex:1;margin:0;font-family:var(--display);font-size:20px;letter-spacing:.01em}
.lgsheet header h3 small{font-family:var(--body);font-weight:500;font-size:13px;color:var(--mute);margin-left:6px}
.lgsheet .lgx{font:inherit;font-size:18px;line-height:1;color:var(--ink);background:none;border:1px solid var(--line);border-radius:8px;width:40px;height:40px;cursor:pointer}
.lgsheet .lgwho{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:0;padding:0 16px 10px;color:var(--mute);font-size:13px;text-align:left}
.lgsheet .lgwho span{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lgsheet .lgwho b{display:inline;color:var(--ink);font-weight:600}
.lgsheet .lgchg{flex:none;display:inline-block;width:auto;min-height:36px;margin:0;font:inherit;font-size:13px;color:var(--red);background:none;border:0;padding:6px 4px;cursor:pointer;text-decoration:underline}
.lgsheet .lgq{font:inherit;font-size:16px;color:var(--ink);background:var(--card);border:1.5px solid var(--line);border-radius:10px;padding:9px 12px;min-height:44px;margin:0 16px 8px}
.lgsheet .lgq:focus{outline:none;border-color:var(--red)}
.lgsheet ul{list-style:none;margin:0;padding:0 8px 10px;overflow-y:auto;-webkit-overflow-scrolling:touch}
.lgsheet li.none{padding:18px 8px;color:var(--mute);font-size:14px}
.lgrow{display:flex;align-items:center;gap:10px;width:100%;text-align:left;font:inherit;color:var(--ink);background:none;border:0;border-bottom:1px solid var(--line);border-radius:0;padding:9px 8px;min-height:54px;cursor:pointer}
.lgsheet li:last-child .lgrow{border-bottom:0}
.lgrow.on{background:var(--card);border-radius:10px;border-bottom-color:transparent;box-shadow:inset 3px 0 0 var(--red)}
.lgrow b{font-size:15px;font-weight:600}
.lgrow .lgrc{flex:none;text-align:right;font-variant-numeric:tabular-nums;font-size:14px;font-weight:600;min-width:52px}
.lgrow .lgrc i{display:block;font-style:normal;font-weight:400;color:var(--mute);font-size:11.5px}
.lgrow:focus-visible,.lgbar .lgcur:focus-visible,.lgsheet .lgx:focus-visible{outline:2px solid var(--red);outline-offset:2px}
"""

JS = r"""
(function(){
  function $(s, r){ return (r || document).querySelector(s); }
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function ord(n){ var s = ['th','st','nd','rd'], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }

  // ---------- section tabs ----------
  // mount(host, [{id, label}], {root, key, start, onShow}) -> {show(id, quiet), cur(), count(id, n)}
  function tabsMount(host, tabs, opt){ opt = opt || {}; var root = opt.root || document, cur = null;
    host.classList.add('tabs'); host.classList.add('fxtabs'); host.setAttribute('role', 'tablist');
    var anchor = document.createElement('div'); anchor.className = 'fxanchor'; host.parentNode.insertBefore(anchor, host);   // where the row sits when it is not pinned
    host.innerHTML = tabs.map(function(t){ return '<button type="button" class="tab" role="tab" data-t="' + esc(t.id) + '">' + esc(t.label) + '<small></small></button>'; }).join('');
    // a row too wide for the screen keeps the chosen tab in view (again after a count changes a tab's width)
    function keep(){ var b = host.querySelector('.tab.on'); if(b && host.scrollWidth > host.clientWidth + 2) host.scrollLeft = Math.max(0, b.offsetLeft - (host.clientWidth - b.offsetWidth) / 2); }
    function show(id, quiet){ if(!tabs.some(function(t){ return t.id === id; })) id = tabs[0].id; cur = id;
      Array.prototype.forEach.call(host.children, function(b){ var on = b.dataset.t === id; b.classList.toggle('on', on); b.setAttribute('aria-selected', on ? 'true' : 'false'); });
      keep();
      Array.prototype.forEach.call(root.querySelectorAll('[data-tab]'), function(el){ el.classList.toggle('fxoff', el.dataset.tab !== id); });
      if(opt.key){ try{ sessionStorage.setItem(opt.key, id); }catch(e){} }
      // a tap while the row is pinned: bring the new section's start up under it instead of leaving the reader mid-way down
      if(!quiet){ var off = parseFloat(getComputedStyle(host).top) || 0, y = anchor.getBoundingClientRect().top + window.scrollY - off; if(window.scrollY > y) window.scrollTo(0, Math.max(0, y)); }
      if(opt.onShow) opt.onShow(id); }
    host.addEventListener('click', function(e){ var b = e.target.closest('.tab'); if(b) show(b.dataset.t); });
    var first = opt.start; if(!first && opt.key){ try{ first = sessionStorage.getItem(opt.key); }catch(e){} }
    show(first || tabs[0].id, true);
    return { show: show, cur: function(){ return cur; }, count: function(id, n){ var b = host.querySelector('[data-t="' + id + '"] small'); if(b){ var x = n ? ' ' + n : ''; if(b.textContent !== x){ b.textContent = x; keep(); } } } }; }
  window.bsTabs = { mount: tabsMount };

  // ---------- league bar + sheet ----------
  var LG = { opt: null, user: null, uname: '', leagues: [], cur: null, rec: {}, chip: {}, q: '', busy: 0, queue: [] };
  function meta(l){ var rp = l.roster_positions || [], sc = l.scoring_settings || {}, t = l.settings ? l.settings.type : 0, rec = sc.rec || 0;
    var b = [(l.total_rosters || '?') + ' teams', t === 2 ? 'dynasty' : t === 1 ? 'keeper' : 'redraft'];
    if(rp.indexOf('SUPER_FLEX') >= 0) b.push('superflex');
    b.push(rec >= 0.75 ? 'PPR' : rec > 0 ? 'half PPR' : 'standard'); if((sc.bonus_rec_te || 0) > 0) b.push('TE premium');
    return b.join(' · '); }
  function kind(l){ var t = l.settings ? l.settings.type : 0; return (t === 2 ? 'dynasty' : t === 1 ? 'keeper' : 'redraft') + ((l.roster_positions || []).indexOf('SUPER_FLEX') >= 0 ? ' · superflex' : ''); }
  function ckey(){ return 'bs_lg_rec_' + ((LG.user && LG.user.user_id) || ''); }
  function load(){ LG.rec = {}; LG.chip = {}; try{ var c = JSON.parse(sessionStorage.getItem(ckey()) || 'null'); if(c && Date.now() - c.t < 18e5){ LG.rec = c.rec || {}; LG.chip = c.chip || {}; } }catch(e){} }
  function save(){ try{ sessionStorage.setItem(ckey(), JSON.stringify({ t: Date.now(), rec: LG.rec, chip: LG.chip })); }catch(e){} }
  function byId(id){ return LG.leagues.filter(function(l){ return l.league_id === id; })[0]; }
  function recOf(ros){ var me = LG.user && LG.user.user_id, r = (ros || []).filter(function(x){ return x.owner_id === me || (x.co_owners || []).indexOf(me) >= 0; })[0];
    if(!r) return null; var s = r.settings || {}, f = function(x){ var q = x.settings || {}; return (q.fpts || 0) + (q.fpts_decimal || 0) / 100; };
    var order = ros.slice().sort(function(a, b){ return ((b.settings || {}).wins || 0) - ((a.settings || {}).wins || 0) || f(b) - f(a); });
    return { txt: (s.wins || 0) + '-' + (s.losses || 0) + (s.ties ? '-' + s.ties : ''), rank: order.indexOf(r) + 1, n: ros.length }; }
  function bar(){ var h = LG.opt && LG.opt.bar; if(!h) return; if(!LG.leagues.length){ h.hidden = true; h.innerHTML = ''; return; }
    var l = LG.cur, r = l && LG.rec[l.league_id], c = l && LG.chip[l.league_id]; h.hidden = false;
    h.innerHTML = '<button type="button" class="lgcur" aria-haspopup="dialog"><span class="lgtx"><b>' + esc(l ? l.name : 'Pick a league') + '</b><small>' + (l ? (r ? esc(r.txt) + ' · ' + ord(r.rank) + ' of ' + r.n + ' · ' + esc(kind(l)) : esc(meta(l))) : LG.leagues.length + ' leagues on this account') + '</small></span>'
      + (c ? '<span class="lgchip ' + esc(c.cls || '') + '"' + (c.title ? ' title="' + esc(c.title) + '"' : '') + '>' + esc(c.txt) + '</span>' : '')
      + '<span class="lgsx">' + (LG.leagues.length > 1 ? 'Switch · ' + LG.leagues.length : 'League') + ' ▾</span></button>';
    h.firstChild.addEventListener('click', open); }
  function rowHtml(l){ var r = LG.rec[l.league_id], c = LG.chip[l.league_id], on = LG.cur && LG.cur.league_id === l.league_id;
    return '<button type="button" class="lgrow' + (on ? ' on' : '') + '" data-id="' + esc(l.league_id) + '"' + (on ? ' aria-current="true"' : '') + '><span class="lgtx"><b>' + esc(l.name) + '</b><small>' + esc(meta(l)) + '</small></span>'
      + (c ? '<span class="lgchip ' + esc(c.cls || '') + '"' + (c.title ? ' title="' + esc(c.title) + '"' : '') + '>' + esc(c.txt) + '</span>' : '')
      + '<span class="lgrc">' + (r ? esc(r.txt) + '<i>' + ord(r.rank) + ' of ' + r.n + '</i>' : r === null ? '<i>not on a roster</i>' : '<i>…</i>') + '</span></button>'; }
  function list(){ var ul = $('#lgov .lglist'); if(!ul) return;
    var ls = LG.leagues.filter(function(l){ return !LG.q || String(l.name).toLowerCase().indexOf(LG.q) >= 0; });
    ul.innerHTML = ls.length ? ls.map(function(l){ return '<li>' + rowHtml(l) + '</li>'; }).join('') : '<li class="none">No league matches that.</li>'; }
  function refresh(id){ var b = $('#lgov .lgrow[data-id="' + id + '"]'), l = byId(id); if(b && l) b.parentNode.innerHTML = rowHtml(l); if(LG.cur && LG.cur.league_id === id) bar(); }
  function pump(){ while(LG.busy < 3 && LG.queue.length){ (function(l){ LG.busy++;
      LG.opt.get('league/' + l.league_id + '/rosters').then(function(ros){ ros = ros || []; LG.rec[l.league_id] = recOf(ros);
          if(LG.opt.extra && LG.rec[l.league_id] && LG.chip[l.league_id] === undefined) return Promise.resolve(LG.opt.extra(l, ros)).then(function(c){ LG.chip[l.league_id] = c || null; }, function(){ LG.chip[l.league_id] = null; });
          if(LG.chip[l.league_id] === undefined) LG.chip[l.league_id] = null; })
        .catch(function(){ })   // left unset: the next open asks again
        .then(function(){ LG.busy--; save(); refresh(l.league_id); pump(); }); })(LG.queue.shift()); } }
  function fill(){ LG.queue = LG.leagues.filter(function(l){ return LG.rec[l.league_id] === undefined || (LG.opt.extra && LG.rec[l.league_id] && LG.chip[l.league_id] === undefined); }); pump(); }
  function close(){ var ov = $('#lgov'); if(ov){ ov.remove(); document.documentElement.classList.remove('lgopen'); var b = $('.lgbar .lgcur'); if(b) b.focus({ preventScroll: true }); } }
  function open(){ close(); LG.q = ''; var ov = document.createElement('div'); ov.className = 'lgov'; ov.id = 'lgov';
    ov.innerHTML = '<div class="lgsheet" role="dialog" aria-modal="true" aria-label="Your Sleeper leagues"><header><h3>Your leagues<small>' + LG.leagues.length + '</small></h3><button type="button" class="lgx" aria-label="Close">✕</button></header>'
      + '<div class="lgwho"><span>Sleeper username <b>' + esc(LG.uname) + '</b></span><button type="button" class="lgchg">Use another</button></div>'
      + (LG.leagues.length > 8 ? '<input type="search" class="lgq" placeholder="Search your leagues" autocomplete="off" aria-label="Search your leagues">' : '')
      + '<ul class="lglist"></ul></div>';
    document.body.appendChild(ov); document.documentElement.classList.add('lgopen');
    ov.addEventListener('click', function(e){
      if(e.target === ov || e.target.closest('.lgx')){ close(); return; }
      if(e.target.closest('.lgchg')){ close(); if(LG.opt.onChange) LG.opt.onChange(); return; }
      var row = e.target.closest('.lgrow'); if(row){ var l = byId(row.dataset.id); close(); if(l && LG.opt.onPick) LG.opt.onPick(l); } });
    var q = $('.lgq', ov); if(q) q.addEventListener('input', function(){ LG.q = q.value.trim().toLowerCase(); list(); });
    list(); fill(); var on = $('.lgrow.on', ov); if(on && on.scrollIntoView) on.scrollIntoView({ block: 'nearest' }); }
  document.addEventListener('keydown', function(e){ if(e.key === 'Escape' && $('#lgov')) close(); });
  window.bsLg = {
    // mount({bar: element, get: function(path) -> Promise, onPick(league), onChange(), extra(league, rosters) -> {txt, cls, title} | Promise})
    mount: function(opt){ LG.opt = opt; bar(); },
    // after the page has the account's leagues
    set: function(user, uname, leagues, cur){ var same = LG.user && user && LG.user.user_id === user.user_id; LG.user = user; LG.uname = uname || ''; LG.leagues = leagues || []; LG.cur = cur || null; if(!same) load(); bar(); },
    current: function(l){ LG.cur = l; bar(); },
    // the page already has this league's rosters (and maybe its verdict): no second request for it
    note: function(id, ros, chip){ if(ros) LG.rec[id] = recOf(ros); if(chip !== undefined) LG.chip[id] = chip; save(); refresh(id); },
    open: open, close: close, meta: meta, clear: function(){ LG.leagues = []; LG.cur = null; bar(); }
  };
})();
"""

# 11/17 (page pass): the section tabs on their own, for pages with no league bar (Model's Best, the News desk, DFS, the record pages)
TABS_CSS = CSS[:CSS.index("/* ---- league bar + sheet ---- */")]
TABS_JS = JS[:JS.index("  // ---------- league bar + sheet ----------")] + "})();\n"
