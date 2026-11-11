
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
  var g = document.querySelector('.sitenav .thm'); if(!g) return;
  function cur(){ try { var t = localStorage.getItem('bs_theme'); return (t === 'dark' || t === 'light') ? t : 'auto'; } catch(e){ return 'auto'; } }
  function paint(){ var c = cur(); g.querySelectorAll('button').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-thm') === c); b.setAttribute('aria-pressed', b.getAttribute('data-thm') === c ? 'true' : 'false'); }); }
  g.addEventListener('click', function(e){
    var b = e.target.closest('button[data-thm]'); if(!b) return;
    var t = b.getAttribute('data-thm');
    try { if(t === 'auto') localStorage.removeItem('bs_theme'); else localStorage.setItem('bs_theme', t); } catch(err){}
    if(t === 'auto') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', t);
    paint();
  });
  paint();
})();

/* page counts (owner 11/10): one anonymous +1 per page view - the page's path and nothing else. No cookie, no id. Skipped when the browser sends Do Not Track or Global Privacy Control. */
(function(){ try{ var n = navigator; if(n.globalPrivacyControl || n.doNotTrack === '1' || window.doNotTrack === '1') return; if(/bot|crawl|spider|headless|lighthouse/i.test(n.userAgent || '')) return;
  var p = location.pathname.toLowerCase().replace(/index\.html$/, ''); if(!/^\/[a-z0-9\/_-]*$/.test(p) || p.length > 80) return;
  fetch('https://fuwiqijgkgbzvnfnsans.supabase.co/rest/v1/rpc/hit', {method: 'POST', keepalive: true, headers: {'Content-Type': 'application/json', apikey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1d2lxaWpna2dienZuZm5zYW5zIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI1NDMxNzMsImV4cCI6MjEwODExOTE3M30.cHHSmNne8GWkMvVO5n3DRIyrmC2D0hmpI8DNbOxs7eU', Authorization: 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1d2lxaWpna2dienZuZm5zYW5zIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI1NDMxNzMsImV4cCI6MjEwODExOTE3M30.cHHSmNne8GWkMvVO5n3DRIyrmC2D0hmpI8DNbOxs7eU'}, body: JSON.stringify({p: p})}).catch(function(){}); }catch(e){} })();
