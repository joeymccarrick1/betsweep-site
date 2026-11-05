#!/usr/bin/env python3
"""build_beat.py - Beat the model (11/5 out-of-the-box batch): pick five FanDuel legs for the week, the model picks its five, Tuesday grades both.

The pool is every priced leg between -150 and +150 (so a hit means something and nobody wins by taking five -800 favourites); the model's five
are the highest-edge legs in that band, one per player and one per game, with the model's chance at or above 50%. Picks are stored in
Supabase (beat_picks: one row per user per week, five keys) and graded by the Edge Function's grade mode on Tuesday against
/data/graded-w<W>.json; the model's five are frozen into beat_model by the Edge Function's hourly run the first time it sees a week
without a row (so the Thursday-morning build's picks are the model's picks for the week, however the lines move afterwards).

Reads: out/builder_data.json. Writes: out/beat.html (wrapped at /beat/) and out/beat.json {week, built, model:[keys], pool:[[key, pl, tm, opp,
gid, m, ln, o, p, ko], ...]} (served at /b/beat.json).
"""
import json, os, math, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
E = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
D = json.load(open(os.path.join(OUT, "builder_data.json"))); W = D["week"]
KO = {g["gid"]: g.get("ko") for g in D.get("games", [])}
def skey(pl, m, ln): return f"{pl}|{m}|{int(math.floor((float(ln) if ln is not None else 1) + 0.5))}"
pool = []
for l in D["legs"]:
    o = l.get("o")
    if o is None or not (-150 <= o <= 150) or l.get("p") is None: continue
    if l.get("pos") in ("SPR", "TOT", "ML") or l["m"] in ("Spread", "Total", "Moneyline"): continue   # player props only: the results feed grades those
    pool.append([skey(l["pl"], l["m"], l.get("ln", 1)), l["pl"], l.get("tm", ""), l.get("opp", ""), l.get("g", ""), l["m"], l.get("ln", 1), o, round(l["p"], 3), KO.get(l.get("g", "")), round(l.get("e", 0), 3)])
pool.sort(key=lambda x: (x[9] or 0, x[1], x[5]))
# the model's five: best edge, chance >= 50%, one per player, one per game
# owner 11/5: at most two unders in the model's five - unders are where the biggest -150..+150 edges often sit, but five unders reads like a fade list, not a picks slate
MAX_UNDERS = 2
model, seen_p, seen_g, n_under = [], set(), set(), 0
for x in sorted(pool, key=lambda x: -x[10]):
    under = x[5].startswith("Under ")
    if x[8] < 0.5 or x[1] in seen_p or x[4] in seen_g or (under and n_under >= MAX_UNDERS): continue
    model.append(x[0]); seen_p.add(x[1]); seen_g.add(x[4]); n_under += under
    if len(model) == 5: break
built = dt.datetime.now(dt.timezone.utc)
json.dump({"week": W, "built": built.isoformat(), "model": model, "pool": [x[:10] for x in pool]}, open(os.path.join(OUT, "beat.json"), "w"), separators=(",", ":"))
try:
    import account as ACCT; _link, _base = ACCT._base_css()
except Exception: _link, _base = "", ""
body = f'''<title>Beat the model · Week {W} · BetSweep</title>
<meta name="description" content="Pick five FanDuel legs for the week and go head to head with the BetSweep model's five. Graded Tuesday; the leaderboard keeps score all season.">
{_link}
<style>{_base}
.bt{{max-width:1100px;margin:16px auto 40px;padding:0 16px}} .bt h1{{font-family:var(--brand);font-style:italic;font-weight:800;font-size:32px;line-height:1;margin:0 0 6px;letter-spacing:-.01em}} .bt h1 small{{display:block;font-family:var(--display);font-style:normal;font-weight:700;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--redtxt,var(--red));margin-bottom:4px}}
.bt p.m{{color:var(--mute);line-height:1.5;margin:0 0 14px;max-width:72ch}} .bt h2{{font-family:var(--display);font-weight:700;font-size:20px;margin:18px 0 8px}} .bt h2 small{{font-family:var(--body);font-weight:400;font-size:12.5px;color:var(--mute);margin-left:8px}}
.btgrid{{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}} .btcard{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}}
.legl{{list-style:none;margin:0;padding:0;display:grid;gap:6px}} .legl li{{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:4px 10px;align-items:center;background:var(--chalk);border-radius:10px;padding:8px 10px;font-size:14px}}
.legl li b{{display:block}} .legl li small{{color:var(--mute);font-size:12px}} .legl .o{{font-family:var(--display);font-weight:700;font-size:15px}} .legl .pc{{font-family:var(--display);font-weight:700;color:var(--mute);font-size:13px}} .legl li.hit{{border-left:4px solid var(--good)}} .legl li.miss{{border-left:4px solid var(--bad);opacity:.8}} .legl li.push{{border-left:4px solid var(--mute)}}
.legl li.empty{{display:block;color:var(--mute);text-align:center;border:1.5px dashed var(--line);background:transparent}} .legl li .rm{{font:inherit;background:none;border:0;color:var(--mute);cursor:pointer;min-width:36px;min-height:36px;border-radius:8px}} .legl li .rm:hover{{color:var(--ink);background:var(--card)}}
.pick{{margin-top:10px}} .pick input{{width:100%;font:inherit;font-size:16px;min-height:44px;padding:8px 12px;border:1.5px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink)}} .pick input:focus{{outline:none;border-color:var(--red)}}
.pool{{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:4px;max-height:420px;overflow:auto}} .pool li{{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;align-items:center;padding:8px 10px;border-radius:8px;cursor:pointer;font-size:14px}} .pool li:hover{{background:var(--chalk)}} .pool li.gone{{opacity:.45;cursor:not-allowed}} .pool li.on{{background:color-mix(in srgb,var(--good) 14%,transparent)}}
.pool li b{{display:block;font-weight:600}} .pool li small{{color:var(--mute);font-size:12px}} .pool .o{{font-family:var(--display);font-weight:700}} .pool .pc{{font-family:var(--display);color:var(--mute);font-size:13px}}
.btsub{{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px}} .btsub input{{flex:1;min-width:140px;font:inherit;font-size:16px;min-height:44px;padding:8px 12px;border:1.5px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink)}}
.btsub button{{font:inherit;font-family:var(--display);font-weight:700;letter-spacing:.06em;text-transform:uppercase;min-height:44px;padding:0 18px;border-radius:8px;border:0;background:var(--red);color:#fff;cursor:pointer}} .btsub button[disabled]{{opacity:.5;cursor:default}}
.btnote{{font-size:13px;color:var(--mute);margin-top:8px;line-height:1.45}} .btnote.ok{{color:var(--good)}} .btnote.err{{color:var(--bad)}}
table.lb{{width:100%;border-collapse:collapse;font-size:14px}} .lb th,.lb td{{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left}} .lb th.r,.lb td.r{{text-align:right;font-variant-numeric:tabular-nums}} .lb thead th{{font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)}} .lb tr.model td{{color:var(--redtxt,var(--red));font-weight:600}} .lb tr.me td{{background:color-mix(in srgb,var(--good) 9%,transparent)}}
.btchip{{display:inline-block;font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.08em;text-transform:uppercase;padding:3px 8px;border-radius:999px;background:var(--chalk);color:var(--mute)}}
</style>
<main class="bt" data-week="{W}">
<h1><small>Week {W}</small>Beat the model</h1>
<p class="m">Five FanDuel legs, yours against the model's. Every player prop priced between -150 and +150 is in the pool, one leg per player. Hits count, not odds, so there is no prize for five -800 favourites. Picks lock when a leg's game kicks off; Tuesday grades everyone and the leaderboard keeps the season score.</p>
<div class="btgrid">
 <section class="btcard"><h2>The model's five <small id="btmnote">this week's build</small></h2><ul class="legl" id="btmodel"></ul></section>
 <section class="btcard"><h2>Your five <small id="btyn">0 of 5</small></h2><ul class="legl" id="btmine"></ul>
  <div class="pick"><input type="search" id="btq" placeholder="Search a player or market (Allen 250, Anytime TD, Receptions)" autocomplete="off"><ul class="pool" id="btpool"></ul></div>
  <div class="btsub"><input type="text" id="btname" maxlength="20" placeholder="Name on the leaderboard"><button type="button" id="btgo" disabled>Lock in five</button></div>
  <p class="btnote" id="btnote">Sign in (menu, top right) to submit. Picks are one set per week; you can change them until a chosen leg's game kicks off.</p>
 </section>
</div>
<section class="btcard" style="margin-top:14px"><h2>Leaderboard <small>graded Tuesdays · hits of five · season total</small></h2><div id="btlb"><p class="btnote">Loading…</p></div></section>
</main>
<script>
(function(){{
  var W = {W}; var DATA = null, POOL = {{}}, MODEL = [], MINE = [], LOCKED = false, GRADES = null, FROZEN = false;
  var $ = function(id){{ return document.getElementById(id); }};
  function am(o){{ return o > 0 ? '+' + o : String(o); }}
  function esc(s){{ return String(s).replace(/[&<>"]/g, function(c){{ return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]; }}); }}
  function line(l){{ var m = l[5], ln = l[6]; if (/Anytime TD|First TD|Interception/.test(m) && ln <= 1) return m; var u = /^Under /.test(m); return (u ? m.replace(/^Under /, '') + ' under ' + ln : m + ' ' + ln + '+'); }}
  function started(l){{ return l[9] && l[9] <= Date.now(); }}
  function legLi(k, opts){{ var l = POOL[k]; var g = GRADES && GRADES[k]; if (!l) return '<li class="' + (g || '') + '"><div><b>' + esc(k.split('|')[0]) + '</b><small>' + esc(k.split('|').slice(1).join(' ')) + '</small></div><span></span><span></span></li>';
    return '<li class="' + (g || '') + '"><div><b>' + esc(l[1]) + '</b><small>' + esc(line(l)) + ' · ' + esc(l[2]) + ' v ' + esc(l[3]) + (g ? ' · ' + g.toUpperCase() : '') + '</small></div><span class="o">' + am(l[7]) + '</span>' + (opts && opts.rm ? '<button type="button" class="rm" data-k="' + esc(k) + '" aria-label="Remove">✕</button>' : '<span class="pc">' + Math.round(l[8] * 100) + '%</span>') + '</li>'; }}
  function paintModel(){{ $('btmodel').innerHTML = MODEL.map(function(k){{ return legLi(k); }}).join('') || '<li class="empty">No picks yet.</li>'; $('btmnote').textContent = FROZEN ? 'frozen at the first build of the week' : "this week's build"; }}
  function paintMine(){{ var h = MINE.map(function(k){{ return legLi(k, {{rm: !LOCKED}}); }}); while (h.length < 5) h.push('<li class="empty">Pick ' + (h.length + 1) + ' of 5</li>'); $('btmine').innerHTML = h.join(''); $('btyn').textContent = MINE.length + ' of 5' + (LOCKED ? ' · locked' : ''); $('btgo').disabled = LOCKED || MINE.length !== 5; paintPool(); }}
  function paintPool(){{ var q = ($('btq').value || '').trim().toLowerCase(); var ul = $('btpool'); if (!q || LOCKED){{ ul.innerHTML = ''; return; }}
    var ws = q.split(/\\s+/); var hits = Object.keys(POOL).filter(function(k){{ var l = POOL[k]; var s = (l[1] + ' ' + l[5] + ' ' + l[6] + ' ' + l[2] + ' ' + l[3]).toLowerCase(); return ws.every(function(w){{ return s.indexOf(w) >= 0; }}); }}).slice(0, 40);
    var minePl = {{}}; MINE.forEach(function(k){{ minePl[POOL[k] ? POOL[k][1] : k.split('|')[0]] = 1; }});
    ul.innerHTML = hits.map(function(k){{ var l = POOL[k]; var on = MINE.indexOf(k) >= 0, gone = started(l) || (!on && (minePl[l[1]] || MINE.length >= 5)); return '<li class="' + (on ? 'on' : '') + (gone ? ' gone' : '') + '" data-k="' + esc(k) + '"><div><b>' + esc(l[1]) + '</b><small>' + esc(line(l)) + ' · ' + esc(l[2]) + ' v ' + esc(l[3]) + (started(l) ? ' · kicked off' : '') + '</small></div><span class="o">' + am(l[7]) + '</span><span class="pc">' + Math.round(l[8] * 100) + '%</span></li>'; }}).join('') || '<li><small>Nothing in the pool matches - the pool is every player prop priced -150 to +150.</small></li>'; }}
  $('btq').addEventListener('input', paintPool);
  $('btpool').addEventListener('click', function(e){{ var li = e.target.closest('li[data-k]'); if (!li || LOCKED) return; var k = li.getAttribute('data-k'), l = POOL[k]; if (!l || started(l)) return;
    var i = MINE.indexOf(k); if (i >= 0) MINE.splice(i, 1); else {{ if (MINE.length >= 5) return; if (MINE.some(function(x){{ return POOL[x] && POOL[x][1] === l[1]; }})) return; MINE.push(k); }} paintMine(); }});
  $('btmine').addEventListener('click', function(e){{ var b = e.target.closest('.rm'); if (!b || LOCKED) return; MINE = MINE.filter(function(k){{ return k !== b.getAttribute('data-k'); }}); paintMine(); }});
  function note(t, cls){{ var n = $('btnote'); n.textContent = t; n.className = 'btnote' + (cls ? ' ' + cls : ''); }}
  function acct(){{ return window.bsAccount && window.bsAccount.user && window.bsAccount.client ? window.bsAccount : null; }}
  $('btgo').addEventListener('click', function(){{ var A = acct(); if (!A){{ note('Sign in first (menu, top right) - picks are saved to your account.', 'err'); var s = document.querySelector('#bsacct .in'); if (s) s.focus(); return; }}
    if (MINE.length !== 5) return; if (MINE.some(function(k){{ return POOL[k] && started(POOL[k]); }})){{ note('One of your legs has already kicked off - swap it out.', 'err'); return; }}
    var name = ($('btname').value || '').trim().slice(0, 20) || 'Anonymous'; try {{ localStorage.setItem('bs_beat_name', name); }} catch(e){{}}
    $('btgo').disabled = true; note('Saving…');
    A.client.from('beat_picks').upsert({{user_id: A.user.id, week: W, keys: MINE, name: name, submitted_at: new Date().toISOString()}}, {{onConflict: 'user_id,week'}}).then(function(r){{
      if (r.error){{ note('Could not save: ' + r.error.message, 'err'); $('btgo').disabled = false; return; }} note('Locked in. Change them any time before your first leg kicks off; Tuesday grades everyone.', 'ok'); paintMine(); loadLB(); }}); }});
  function loadMine(){{ var A = acct(); if (!A) return; A.client.from('beat_picks').select('keys,name,hits,graded_at').eq('user_id', A.user.id).eq('week', W).maybeSingle().then(function(r){{
    if (r.error || !r.data) return; MINE = (r.data.keys || []).slice(0, 5); if (r.data.name) $('btname').value = r.data.name; LOCKED = !!r.data.graded_at || MINE.some(function(k){{ return POOL[k] && started(POOL[k]); }}); paintMine();
    if (r.data.graded_at) note('Graded: ' + r.data.hits + ' of 5 hit.', 'ok'); else if (LOCKED) note('Locked - one of your legs has kicked off. Tuesday grades everyone.'); }}); }}
  function loadLB(){{ var A = window.bsAccount; var cl = A && A.client; if (!cl){{ $('btlb').innerHTML = '<p class="btnote">Sign in to see the leaderboard.</p>'; return; }}
    Promise.all([cl.from('beat_picks').select('user_id,week,name,hits,keys').not('hits', 'is', null), cl.from('beat_model').select('week,keys,hits').order('week', {{ascending: false}}), cl.from('beat_picks').select('user_id,name,keys').eq('week', W)]).then(function(rs){{
      var picks = rs[0].data || [], model = rs[1].data || [], thisWk = rs[2].data || []; var me = acct() ? acct().user.id : null;
      var mrow = model.filter(function(m){{ return m.week === W; }})[0]; if (mrow && mrow.keys && mrow.keys.length){{ MODEL = mrow.keys; FROZEN = true; paintModel(); }}
      var season = {{}}; picks.forEach(function(p){{ var s = season[p.user_id] = season[p.user_id] || {{name: p.name || 'Anonymous', hits: 0, weeks: 0, me: p.user_id === me}}; s.hits += p.hits || 0; s.weeks++; s.name = p.name || s.name; }});
      var msum = model.filter(function(m){{ return m.hits != null; }}).reduce(function(a, m){{ return a + m.hits; }}, 0), mweeks = model.filter(function(m){{ return m.hits != null; }}).length;
      var rows = Object.keys(season).map(function(u){{ return season[u]; }}).sort(function(a, b){{ return b.hits - a.hits || a.weeks - b.weeks; }}).slice(0, 25);
      var h = '<table class="lb"><thead><tr><th>#</th><th>Name</th><th class="r">Hits</th><th class="r">Weeks</th></tr></thead><tbody>';
      h += '<tr class="model"><td>—</td><td>The model</td><td class="r">' + msum + '</td><td class="r">' + mweeks + '</td></tr>';
      rows.forEach(function(r, i){{ h += '<tr class="' + (r.me ? 'me' : '') + '"><td>' + (i + 1) + '</td><td>' + esc(r.name) + '</td><td class="r">' + r.hits + '</td><td class="r">' + r.weeks + '</td></tr>'; }});
      if (!rows.length) h += '<tr><td colspan="4"><span class="btnote">Nobody has been graded yet - the first week grades Tuesday.</span></td></tr>';
      h += '</tbody></table><p class="btnote">' + thisWk.length + ' set' + (thisWk.length === 1 ? '' : 's') + ' of five in for week ' + W + '.</p>';
      $('btlb').innerHTML = h; }}).catch(function(){{ $('btlb').innerHTML = '<p class="btnote">Leaderboard unavailable right now.</p>'; }}); }}
  fetch('/b/beat.json').then(function(r){{ return r.json(); }}).then(function(j){{ DATA = j; (j.pool || []).forEach(function(l){{ POOL[l[0]] = l; }}); MODEL = j.model || []; paintModel(); paintMine();
    try {{ var nm = localStorage.getItem('bs_beat_name'); if (nm) $('btname').value = nm; }} catch(e){{}}
    // last week's grades for the model's card when the week has turned (graded-w<W-1>) - shown under the leaderboard by the Tuesday build
    var tries = 0; (function wait(){{ if (window.bsAccount && window.bsAccount.client){{ loadMine(); loadLB(); window.addEventListener('bs-account', function(){{ loadMine(); loadLB(); }}); document.addEventListener('bs-account', function(){{ loadMine(); loadLB(); }}); }} else if (tries++ < 40) setTimeout(wait, 250); else loadLB(); }})(); }});
}})();
</script>
'''
open(os.path.join(OUT, "beat.html"), "w").write(body)
print(f"wrote out/beat.html + beat.json: pool {len(pool)} legs in the -150..+150 band, model's five: " + "; ".join(model))
