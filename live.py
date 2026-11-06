"""Live game status for the boards and the parlay builder (inlined into both pages).

The browser polls ESPN's public NFL scoreboard (site.api.espn.com, no key) while a game is near kickoff or in progress, and hands each
page a status per game: pre / in / post, the score, quarter + clock, down & distance, possession, red zone and the last play.
If the feed cannot be reached (offline, blocked), a game counts as finished 4.5 hours after kickoff or as soon as the page has a final
score from the nightly schedule data, so played games still sink to the bottom.
11/4 (owner's Tuesday list): the ticker on every game card links to that game's box score + play-by-play on /live/ (#box-<gid>).
"""
LIVE_CSS = r"""
.tick{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;align-items:center;padding:8px 14px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:color-mix(in srgb,var(--red) 7%,var(--card));font-size:12.5px;line-height:1.35}
.tick[hidden]{display:none}
body.compact .card:not(.expanded) > .tick:not([hidden]){display:grid}
.tick .tsc{grid-row:span 2;display:flex;align-items:center;gap:8px;font-family:var(--display);font-weight:800;font-size:20px;letter-spacing:.02em;font-variant-numeric:tabular-nums;white-space:nowrap}
.tick .tsc i{font-style:normal;font-size:10px;color:var(--red);letter-spacing:.1em}
.tick .tsc .tpos::after{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--red);margin-left:4px;vertical-align:4px}
.tick .tst{font-weight:700;color:var(--ink)} .tick .tst .rz{color:var(--red);margin-left:6px;font-size:11px;letter-spacing:.06em;text-transform:uppercase}
.tick .tlp{color:var(--mute);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.tick .tbox{margin-left:8px;font-family:var(--display);font-weight:800;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--red);text-decoration:none;white-space:nowrap;border:1.5px solid var(--red);border-radius:99px;padding:2px 8px} .tick .tbox:hover{background:var(--red);color:#fff}
@media (max-width:560px){ .tick{grid-template-columns:1fr} .tick .tsc{grid-row:auto;font-size:18px} }
.tick.final{background:var(--card)} .tick.final .tsc i{color:var(--mute)}
/* 11/5: a finished game already shows its score in the header pill (.gstat); the strip keeps only the status + Box & plays */
.card.done .tick.final{display:flex;flex-wrap:wrap;gap:4px 10px;padding:7px 14px} .card.done .tick.final .tsc{display:none} .card.done .tick.final .tlp:empty{display:none}
"""

LIVE_JS = r"""
window.BSLive = (function(){
  var ESPN = {WSH:'WAS', LAR:'LA'};
  var games = [], cb = null, state = {}, timer = null, lastFetch = 0, feed = {ok: null, at: 0, err: '', src: ''};
  function ab(x){ return ESPN[x] || x; }
  function ymd(t){ var d = new Date(t); return d.getFullYear() + String(d.getMonth()+1).padStart(2,'0') + String(d.getDate()).padStart(2,'0'); }
  function url(){ var kos = games.map(function(g){ return g.ko; }).filter(Boolean); if(!kos.length) return null;
    return 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=' + ymd(Math.min.apply(null, kos) - 864e5) + '-' + ymd(Math.max.apply(null, kos) + 864e5); }
  function parse(js){
    var out = {};
    (js.events || []).forEach(function(ev){
      var c = (ev.competitions || [])[0]; if(!c) return;
      var cs = c.competitors || [], by = {}, idab = {};
      cs.forEach(function(x){ var a = ab(x.team && x.team.abbreviation); by[a] = x.score; idab[x.team && x.team.id] = a; });
      var abs = Object.keys(by);
      games.forEach(function(g){
        if(abs.indexOf(g.a) < 0 || abs.indexOf(g.b) < 0) return;
        var st = ev.status || c.status || {}, ty = st.type || {}, si = c.situation || {};
        out[g.gid] = { eid: ev.id, period: st.period || 0, clock: st.displayClock || '', st: ty.state || 'pre', done: !!ty.completed, sa: by[g.a], sb: by[g.b], det: ty.shortDetail || ty.detail || '',
          poss: si.possession ? idab[si.possession] || '' : '', dd: si.downDistanceText || si.shortDownDistanceText || '', rz: !!si.isRedZone,
          last: (si.lastPlay && si.lastPlay.text) || '',
          tv: (c.broadcasts || []).map(function(b){ return (b.names || []).join('/'); }).filter(Boolean).join(', ') || ((c.geoBroadcasts || [])[0] && c.geoBroadcasts[0].media && c.geoBroadcasts[0].media.shortName) || '' };
      });
    });
    return out;
  }
  function fallback(g, now){   // no feed for this game
    if(g.fin) return { st: 'post', done: true, finTxt: g.fin };
    if(g.ko && now >= g.ko + 4.5*3600e3) return { st: 'post', done: true };
    if(g.ko && now >= g.ko) return { st: 'in', done: false, nofeed: true };
    return { st: 'pre', done: false };
  }
  function merged(){ var now = Date.now(), m = {}; games.forEach(function(g){ var s = state[g.gid];
      m[g.gid] = s && (s.st !== 'pre' || now < g.ko) ? s : fallback(g, now); if(g.fin && m[g.gid].st === 'post') m[g.gid].finTxt = g.fin; }); return m; }
  function needFeed(){ var now = Date.now();
    return games.some(function(g){ if(!g.ko) return false; var s = state[g.gid]; if(s && s.done) return false; if(g.fin) return false;
      return now >= g.ko - 15*60e3 && now < g.ko + 6*3600e3; }); }
  // two routes to the same ESPN scoreboard: site.api first, the cdn core feed second (different host, same JSON under .content.sbData)
  function url2(){ var u = url(); return u ? u.replace('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?', 'https://cdn.espn.com/core/nfl/scoreboard?xhr=1&') : null; }
  function fetchNow(){
    var u = url(); if(!u || !window.fetch){ cb(merged()); return; }
    lastFetch = Date.now();
    var ctl = window.AbortController ? new AbortController() : null; if(ctl) setTimeout(function(){ ctl.abort(); }, 12000);
    var get = function(addr, src){ return fetch(addr, {cache: 'no-store', signal: ctl ? ctl.signal : undefined}).then(function(r){ if(!r.ok) throw new Error(src + ' HTTP ' + r.status); return r.json(); })
      .then(function(js){ if(js && js.content && js.content.sbData) js = js.content.sbData; if(!js || !js.events) throw new Error(src + ' no events'); return {js: js, src: src}; }); };
    get(u, 'site.api').catch(function(e1){ var u2 = url2(); return u2 ? get(u2, 'cdn').catch(function(e2){ throw new Error(String(e1 && e1.message || e1) + ' | ' + String(e2 && e2.message || e2)); }) : Promise.reject(e1); })
      .then(function(got){ var p = parse(got.js); Object.keys(p).forEach(function(k){ state[k] = p[k]; }); feed = {ok: true, at: Date.now(), err: '', src: got.src, n: Object.keys(p).length}; cb(merged()); })
      .catch(function(e){ feed = {ok: false, at: Date.now(), err: String(e && e.message || e), src: ''}; cb(merged()); });
  }
  // owner 11/5 ("load like instantaneously in real time"): poll every 10 s while a game is on and the page is visible; nothing while hidden; refresh the moment the page comes back
  function tick(){ if(document.hidden) return; if(needFeed() && Date.now() - lastFetch >= 9e3) fetchNow(); else cb(merged()); }
  document.addEventListener('visibilitychange', function(){ if(!document.hidden && cb && needFeed() && Date.now() - lastFetch >= 4e3) fetchNow(); });
  return { refresh: function(){ lastFetch = 0; fetchNow(); }, status: function(){ return feed; },
    start: function(gs, onUpdate){ games = gs; cb = onUpdate;
      var now = Date.now(); if(games.some(function(g){ return g.ko && now >= g.ko - 15*60e3 && !g.fin; })) fetchNow(); else cb(merged());
      timer = setInterval(tick, 10e3); },
    esc: function(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(ch){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]; }); },
    // ticker HTML for one game (a = left team, b = right team); the box link opens the game's box score + play-by-play on /live/
    tickHtml: function(g, s){
      var E = this.esc; var box = g.gid && (location.pathname.indexOf('/live') !== 0) ? '<a class="tbox" href="/live/#box-' + E(g.gid) + '">Box &amp; plays</a>' : '';
      if(!s || s.st === 'pre') return '';
      if(s.nofeed){ if(g.fin) return '<span class="tsc"><i>FINAL</i>' + E(g.fin) + '</span><span class="tst">Final' + box + '</span><span class="tlp"></span>';
        return '<span class="tsc"><i>LIVE</i></span><span class="tst">In progress' + box + '</span><span class="tlp">Live score is delayed - it will update on its own.</span>'; }
      var sa = s.sa != null ? s.sa : '', sb = s.sb != null ? s.sb : '';
      if(s.st === 'post'){ var ft = (sa !== '' ? g.a + ' ' + sa + ' – ' + sb + ' ' + g.b : (s.finTxt || '')); return ft ? '<span class="tsc"><i>FINAL</i>' + E(ft) + '</span><span class="tst">' + E(s.det || 'Final') + box + '</span><span class="tlp"></span>' : ''; }
      return '<span class="tsc"><i>LIVE</i><span class="' + (s.poss === g.a ? 'tpos' : '') + '">' + E(g.a) + ' ' + E(sa) + '</span>–<span class="' + (s.poss === g.b ? 'tpos' : '') + '">' + E(sb) + ' ' + E(g.b) + '</span></span>' +
        '<span class="tst">' + E(s.det) + (s.dd ? ' · ' + (s.poss ? E(s.poss) + ' ball, ' : '') + E(s.dd) : '') + (s.rz ? '<span class="rz">Red zone</span>' : '') + box + '</span>' +
        '<span class="tlp" title="' + E(s.last) + '">' + (s.last ? 'Last play: ' + E(s.last) : '') + '</span>';
    }
  };
})();
"""
