"""risk.py - the live risk layer (owner 11/1: "Injuries and weather seem to be the biggest challenges for us today what can we do to flag
these things and keep legs off our betslips that could be affected" -> "Yes I'll want you to do all of them").

One shared list, public.risk_feed in Supabase, that every page reads live (no rebuild needed):
  injury   written every 10 minutes by the slip-alerts Edge Function from ESPN's injury report: OUT / DOUBTFUL / QUESTIONABLE (+ body part)
  weather  same run: open-air games kicking off within 24 hours whose kickoff-window forecast reaches wind 15+ mph (gusts 28+) or real rain;
           carries the passing / receiving players of that game, the legs wind and rain hurt
  note     the owner's own one-tap notes from any player page (admin only): HURT, LIMITED, OUT, STARTING, ROLE UP, with a short note
Rows the function stops seeing are deleted after 25 minutes; owner notes stay until the owner clears them (or the week rolls).

risk.js (this module's RISK_JS, written to /risk.js by build_site.py and loaded on every page next to account.js):
  - a chip next to the player's name wherever it appears (boards, builder list + cards, player page, Live page rows, promo pages):
      red  "Ruled out" (Out / owner Out) - add buttons ( + with data-k ) refuse the leg with a note
      amber "Doubtful", "Questionable (hamstring)", "Owner: hurt - could barely walk", "Weather: wind 21 mph" (passing / receiving legs only)
      green "Owner: starting" / "Role up"
  - a pill above the bottom tabs when the open betslip (bs_slipk_w<W>) holds risky legs: tap for the list and "Remove ruled-out legs"
  - window.BSRisk.avoid(player, market): the builder's quick builds and "Build me a +N" skip those legs
  - the owner's note panel on player pages (shown only when bs_is_admin() says yes)
The rebuild reads the owner notes too (RUNBOOK Step 2a): OUT -> OUT, HURT / LIMITED -> QUESTIONABLE with the note, STARTING -> CLEARED
(QB: Forced Role QB1), so the next build's projections move with them.
"""
import account as ACCT

SQL = r"""-- BetSweep live risk list (owner 11/1). Run once in the Supabase SQL editor.
create table if not exists public.risk_feed (
  id         text primary key,                 -- inj|<player>  wx|<game>  note|<player>
  kind       text not null check (kind in ('injury', 'weather', 'note')),
  week       int  not null,
  player     text,
  team       text,
  gid        text,
  status     text not null,                    -- OUT DOUBTFUL QUESTIONABLE | WEATHER | HURT LIMITED OUT STARTING ROLE_UP
  level      text not null check (level in ('block', 'warn', 'good')),
  detail     text check (detail is null or length(detail) <= 300),
  players    jsonb,                            -- weather: the passing / receiving players in that game
  by_owner   boolean not null default false,
  updated_at timestamptz not null default now()
);
alter table public.risk_feed enable row level security;
drop policy if exists "read risk" on public.risk_feed;
create policy "read risk" on public.risk_feed for select using (true);
drop policy if exists "owner notes in" on public.risk_feed;
create policy "owner notes in" on public.risk_feed for insert with check (public.bs_is_admin() and kind = 'note');
drop policy if exists "owner notes up" on public.risk_feed;
create policy "owner notes up" on public.risk_feed for update using (public.bs_is_admin() and kind = 'note') with check (public.bs_is_admin() and kind = 'note');
drop policy if exists "owner notes out" on public.risk_feed;
create policy "owner notes out" on public.risk_feed for delete using (public.bs_is_admin() and kind = 'note');
-- the owner's user id, for promo-watch pushes (Edge Function only)
create or replace function public.bs_owner_id() returns uuid language sql stable security definer set search_path = public, auth as $$
  select id from auth.users where lower(email) = '__OWNER_EMAIL__' limit 1
$$;
revoke all on function public.bs_owner_id() from public, anon, authenticated;
"""

RISK_JS = r"""(function(){
  if (window.BSRisk) return;
  var SB = '__SB__', KEY = '__KEY__';
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
  function injV(r){ var s = r.status;
    if (s === 'OUT') return {level: 'block', label: 'Ruled out', why: 'Out' + (r.detail ? ' (' + r.detail + ')' : '') + ' on the injury report', short: 'Out'};
    if (s === 'DOUBTFUL') return {level: 'warn', label: 'Doubtful', why: 'Doubtful' + (r.detail ? ' (' + r.detail + ')' : '') + ' - doubtful players rarely play', short: 'Doubtful'};
    if (s === 'QUESTIONABLE') return {level: 'warn', label: 'Questionable', why: 'Questionable' + (r.detail ? ' (' + r.detail + ')' : ''), short: 'Q'};
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
  var busy = false;
  function decorate(){ if (!loaded || busy) return; busy = true;
    try {
      hosts().forEach(function(h){ var el = h[0], v = verdict(h[1], h[2]); var cur = el.querySelector(':scope > .bsrc');
        var html = v ? chip(v) : ''; if (cur && cur.outerHTML === html) return; if (cur) cur.remove(); if (v) el.insertAdjacentHTML('beforeend', ' ' + html); });
      document.querySelectorAll('[data-k]').forEach(function(b){ if (b.tagName !== 'BUTTON') return; var q = b.getAttribute('data-k').split('|'), v = verdict(q[0], q[1]);
        b.classList.toggle('bsrblock', !!(v && v.level === 'block')); if (v && v.level === 'block') b.title = q[0] + ': ' + v.why; });
      pill();
    } catch(e){} busy = false; }
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
  function owner(){ var pp = document.querySelector('.pp h1'); if (!pp || ownerChecked) return; var A = window.bsAccount; if (!A || !A.client || !A.user) return; ownerChecked = true;
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
"""

RISK_CSS = r"""
.bsrc{display:inline-flex;align-items:center;gap:2px;margin-left:6px;padding:1px 7px;border-radius:99px;font:600 11px/1.5 'IBM Plex Sans',system-ui,sans-serif;letter-spacing:0;text-transform:none;vertical-align:middle;white-space:nowrap;cursor:help}
.bsr-block{background:#b3261e;color:#fff} .bsr-warn{background:#f6e3b4;color:#6b4a00} .bsr-good{background:#dcefdc;color:#1f5d2b}
button.bsrblock{opacity:.35;filter:grayscale(1)}
#bsrpill{position:fixed;left:12px;right:12px;bottom:calc(var(--bs-tabs, 0px) + 74px);z-index:65;max-width:420px;margin:0 auto;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.3);font:14px/1.4 'IBM Plex Sans',system-ui,sans-serif;cursor:pointer;overflow:hidden}
#bsrpill.warn{background:#fff4d6;color:#4d3600;border:1px solid #e3c477} #bsrpill.bad{background:#fde7e5;color:#5c120d;border:1px solid #e8a39d}
#bsrpill .bsrh{padding:10px 14px;font-weight:700} #bsrpill .bsrb{display:none;padding:0 14px 12px} #bsrpill.open .bsrb{display:block}
#bsrpill ul{margin:0 0 10px;padding:0;list-style:none;display:grid;gap:6px} #bsrpill li small{display:block;opacity:.8;font-size:12.5px}
#bsrpill button{font:inherit;font-weight:700;font-size:13px;padding:7px 12px;border-radius:8px;border:0;background:#b3261e;color:#fff;margin-right:6px;cursor:pointer} #bsrpill button.sec{background:none;border:1px solid currentColor;color:inherit}
.bsrtoast{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(var(--bs-tabs, 0px) + 20px);z-index:80;background:#141a24;color:#fff;padding:10px 14px;border-radius:10px;font:600 13.5px 'IBM Plex Sans',system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.35);max-width:90vw}
.bsrnote{margin:12px 0 16px;padding:12px 14px;background:var(--card,#fff);border:1px solid var(--line,#d8d1c2);border-left:4px solid #d7332a;border-radius:10px;font-size:14px;line-height:1.4;font-style:normal;text-align:left}
.bsrnote .bsrh{display:flex;align-items:baseline;justify-content:space-between;gap:8px;flex-wrap:wrap}
.bsrnote .bsrh b{font-family:var(--display,inherit);font-weight:800;letter-spacing:.05em;text-transform:uppercase;font-size:13px}
.bsrnote .bsrh span{font-size:11.5px;color:var(--mute,#6b655c);border:1px solid var(--line,#d8d1c2);border-radius:99px;padding:1px 8px}
.bsrnote p{margin:4px 0 10px;color:var(--mute,#6b655c);font-size:12.5px}
.bsrnote .row{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.4fr) auto;gap:8px;align-items:stretch}
@media (max-width:560px){.bsrnote .row{grid-template-columns:1fr auto}.bsrnote .row select{grid-column:1/-1}}
.bsrnote select,.bsrnote input{box-sizing:border-box;width:100%;font:inherit;font-size:16px;padding:9px 10px;border:1px solid var(--line,#d8d1c2);border-radius:8px;background:var(--paper,var(--bg,#fff));color:var(--ink,inherit)}
.bsrnote button{font:inherit;font-weight:700;font-size:15px;padding:9px 16px;border-radius:8px;border:0;background:#d7332a;color:#fff;cursor:pointer}
.bsrnote small#bsrmsg{display:block;margin-top:6px;font-size:12.5px;color:var(--mute,#6b655c)}
@media (min-width:761px){ #bsrpill{left:auto;right:16px;bottom:16px;margin:0} }
"""

def js():
    import json
    css = "(function(){var s=document.createElement('style');s.textContent=" + json.dumps(RISK_CSS) + ";document.head.appendChild(s);})();\n"
    return css + RISK_JS.replace("__SB__", ACCT.SUPABASE_URL).replace("__KEY__", ACCT.SUPABASE_ANON)
