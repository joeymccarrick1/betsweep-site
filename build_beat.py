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
# ---- friend leagues (owner 11/10: "I'd love for us to start 1-3") ----------------------------------------------------------------------
# A league is a name and an invite code. Everything goes through the functions of sql/betsweep-leagues.sql (beat_league_create / join /
# leave / rename / delete / mine / board): the page never reads a table, and the board carries display names and hits only. Until the
# owner has run that SQL the functions do not exist - the card then hides itself, nothing else on the page changes.
LEAGUE_CSS = """
.lgchips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px} .lgchips button{font:inherit;font-family:var(--display);font-weight:700;font-size:13.5px;letter-spacing:.05em;text-transform:uppercase;min-height:40px;padding:0 13px;border-radius:8px;border:1.5px solid var(--line);background:none;color:var(--ink);cursor:pointer}
.lgchips button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)} .lgchips button.new{border-style:dashed;color:var(--mute)}
.lgrow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0 0} .lgrow input{flex:1;min-width:160px;font:inherit;font-size:16px;min-height:44px;padding:8px 12px;border:1.5px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink)}
.lgrow button,.lgrow a.b{font:inherit;font-size:13.5px;font-weight:600;min-height:44px;padding:0 14px;border-radius:8px;border:1.5px solid var(--line);background:none;color:var(--ink);cursor:pointer;text-decoration:none;display:inline-flex;align-items:center}
.lgrow button.pri{background:var(--red);border-color:var(--red);color:#fff;font-family:var(--display);font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.lginv{margin:10px 0 0;padding:10px 12px;border-radius:10px;background:var(--chalk);font-size:13.5px;line-height:1.45;word-break:break-all} .lginv code{font-family:ui-monospace,Menlo,monospace;font-size:13px;color:var(--ink)}
.lb tr.me td{font-weight:700} .lb tr.model td{color:var(--mute)}
"""
LEAGUE_JS = r"""<script>
(function(){
  var main = document.querySelector('main.bt'), W = +(main && main.dataset.week) || 0, card = document.getElementById('btlg'), body = document.getElementById('btlgbody'); if(!card || !body) return;
  var LIST = null, CUR = null, MSG = '', MISSING = false, BUSY = false, WANT = null;
  try { WANT = (new URLSearchParams(location.search).get('league') || '').trim().toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 12) || null; } catch(e){}
  try { CUR = localStorage.getItem('bs_beat_league') || null; } catch(e){}
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function acct(){ return window.bsAccount && window.bsAccount.user && window.bsAccount.client ? window.bsAccount : null; }
  function gone(err){ var m = String((err && (err.message || err.code)) || ''); return /PGRST202|Could not find the function|does not exist|404/i.test(m + ' ' + ((err && err.code) || '')); }
  function link(code){ return 'https://betsweep.co/beat/?league=' + code; }
  function rpc(fn, args){ var A = acct(); return A.client.rpc(fn, args || {}).then(function(r){ if(r.error) throw r.error; return r.data; }); }
  function setCur(c){ CUR = c; try { if(c) localStorage.setItem('bs_beat_league', c); else localStorage.removeItem('bs_beat_league'); } catch(e){} }
  function clearWant(){ WANT = null; try { var u = new URL(location.href); u.searchParams.delete('league'); history.replaceState(null, '', u.pathname + (u.search || '') + u.hash); } catch(e){} }
  function paint(board){
    if(MISSING){ card.hidden = true; return; } card.hidden = false;
    var A = acct(), h = '';
    if(!A){ body.innerHTML = '<p class="btnote">' + (WANT ? 'You were invited to a league. Sign in (menu, top right) and you are in.' : 'Sign in (menu, top right) to start a league with friends or join one from an invite link.') + '</p>'; return; }
    if(LIST === null){ body.innerHTML = '<p class="btnote">Loading…</p>'; return; }
    var cur = LIST.filter(function(l){ return l.code === CUR; })[0] || LIST[0] || null;
    h += '<div class="lgchips">' + LIST.map(function(l){ return '<button type="button" data-lg="' + esc(l.code) + '" class="' + (cur && l.code === cur.code ? 'on' : '') + '">' + esc(l.name) + '</button>'; }).join('') + '</div>';
    if(cur){
      h += '<div id="lgboard">' + (board ? boardHtml(board, cur) : '<p class="btnote">Loading the board…</p>') + '</div>';
      h += '<p class="lginv">Invite link: <code>' + esc(link(cur.code).replace('https://', '')) + '</code></p>';
      h += '<div class="lgrow"><button type="button" class="pri" data-act="share">Invite friends</button><button type="button" data-act="copy">Copy link</button>' + (cur.owner ? '<button type="button" data-act="rename">Rename</button><button type="button" data-act="close">Close league</button>' : '') + '<button type="button" data-act="leave">Leave</button></div>';
    } else h += '<p class="btnote">No league yet. Start one and send the link to your friends: everyone picks five a week, Tuesday grades it, and the board keeps score against each other and the model.</p>';
    h += '<div class="lgrow"><input type="text" id="lgname" maxlength="40" placeholder="' + (LIST.length ? 'Start another league' : 'League name (Sunday Crew)') + '"><button type="button" class="' + (cur ? '' : 'pri') + '" data-act="create">Start a league</button></div>';
    if(MSG) h += '<p class="btnote ' + (MSG.charAt(0) === '!' ? 'err' : 'ok') + '">' + esc(MSG.replace(/^!/, '')) + '</p>';
    body.innerHTML = h;
  }
  function boardHtml(rows, cur){
    if(!rows.length) return '<p class="btnote">Nobody here yet.</p>';
    var graded = rows.some(function(r){ return r.week_hits != null; }), n = 0;
    var h = '<table class="lb"><thead><tr><th>#</th><th>Name</th><th class="r">Hits</th><th class="r">Weeks</th><th class="r">Week ' + W + '</th></tr></thead><tbody>';
    rows.forEach(function(r){ if(!r.model) n++;
      h += '<tr class="' + (r.me ? 'me' : '') + (r.model ? ' model' : '') + '"><td>' + (r.model ? '—' : n) + '</td><td>' + esc(r.name) + (r.me ? ' (you)' : '') + '</td><td class="r">' + r.hits + '</td><td class="r">' + r.weeks + '</td><td class="r">' + (r.week_hits != null ? r.week_hits + '/5' : r.picked ? 'in' : 'not yet') + '</td></tr>'; });
    var mem = rows.filter(function(r){ return !r.model; }).length;
    return h + '</tbody></table><p class="btnote">' + mem + ' in ' + esc(cur.name) + '. Hits count from the week the league started, so everyone starts level. Graded Tuesdays.</p>';
  }
  function loadBoard(){ var cur = LIST && (LIST.filter(function(l){ return l.code === CUR; })[0] || LIST[0]); if(!cur) return; setCur(cur.code);
    rpc('beat_league_board', {p_code: cur.code, p_week: W}).then(function(rows){ if(CUR === cur.code) paint(rows || []); }).catch(function(){ var b = document.getElementById('lgboard'); if(b) b.innerHTML = '<p class="btnote">The board is unavailable right now.</p>'; }); }
  function load(){
    var A = acct(); if(!A){ LIST = null; paint(); return; }
    var first = WANT ? rpc('beat_league_join', {p_code: WANT}).then(function(r){ var x = (r && r[0]) || null; if(x){ setCur(x.code); MSG = 'You are in ' + x.name + '.'; } clearWant(); }).catch(function(e){ if(gone(e)){ MISSING = true; } else { MSG = '!' + (e.message || 'Could not join that league.'); clearWant(); } }) : Promise.resolve();
    first.then(function(){ if(MISSING){ paint(); return; }
      return rpc('beat_league_mine').then(function(rows){ LIST = rows || []; paint(); loadBoard(); }); })
    .catch(function(e){ if(gone(e)){ MISSING = true; paint(); } else { LIST = LIST || []; MSG = '!Leagues are unavailable right now.'; paint(); } });
  }
  function act(fn, args, okMsg, after){ if(BUSY) return; BUSY = true;
    rpc(fn, args).then(function(r){ BUSY = false; MSG = typeof okMsg === 'function' ? okMsg(r) : okMsg; if(after) after(r); load(); }).catch(function(e){ BUSY = false; MSG = '!' + (e.message || 'That did not work.'); paint(); loadBoard(); }); }
  card.addEventListener('click', function(e){
    var b = e.target.closest && e.target.closest('button'); if(!b) return; var A = acct(); if(!A) return;
    var cur = LIST && (LIST.filter(function(l){ return l.code === CUR; })[0] || LIST[0]);
    if(b.dataset.lg){ setCur(b.dataset.lg); MSG = ''; paint(); loadBoard(); return; }
    var a = b.dataset.act; if(!a) return;
    if(a === 'create'){ var nm = (document.getElementById('lgname').value || '').trim(); if(!nm){ MSG = '!Give the league a name first.'; paint(); return; }
      act('beat_league_create', {p_name: nm}, function(r){ var x = (r && r[0]) || {}; return 'Started ' + (x.name || nm) + '. Send the invite link to your friends.'; }, function(r){ var x = (r && r[0]) || {}; if(x.code) setCur(x.code); }); return; }
    if(!cur) return;
    var txt = 'Join my BetSweep league "' + cur.name + '": five picks a week against the model.';
    if(a === 'share'){ if(navigator.share){ navigator.share({title: 'BetSweep league', text: txt, url: link(cur.code)}).catch(function(){}); } else a = 'copy'; }
    if(a === 'copy'){ var t = txt + ' ' + link(cur.code); if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(function(){ MSG = 'Invite copied.'; paint(); loadBoard(); }, function(){ window.prompt('Copy this invite', t); }); else window.prompt('Copy this invite', t); return; }
    if(a === 'rename'){ var n2 = window.prompt('League name', cur.name); if(n2 && n2.trim()) act('beat_league_rename', {p_code: cur.code, p_name: n2.trim()}, 'Renamed.'); return; }
    if(a === 'close'){ if(window.confirm('Close "' + cur.name + '" for everyone in it? This cannot be undone.')) act('beat_league_delete', {p_code: cur.code}, 'League closed.', function(){ setCur(null); }); return; }
    if(a === 'leave'){ if(window.confirm('Leave "' + cur.name + '"?' + (cur.owner ? ' The longest-standing member becomes its owner.' : ''))) act('beat_league_leave', {p_code: cur.code}, 'You left ' + cur.name + '.', function(){ setCur(null); }); return; }
  });
  var tries = 0; (function wait(){ if(window.bsAccount && window.bsAccount.client){ load(); document.addEventListener('bs-account', load); window.addEventListener('bs-account', load); } else if(tries++ < 40) setTimeout(wait, 250); else paint(); })();
})();
</script>"""
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
# ---- suggested legs (owner 11/11 8:20 AM: "On beat the model your five can we have suggested legs around -110 that we can scroll through
# to build our five. Include percentage and position ranking in that stat vs defensive matchup in that stat for each leg") ----------------
# Around -110 = priced -125 to +100. One row per player, stat and side: the rung nearest -110. Only legs the model gives 50% or better (the
# contest counts hits, not odds). Each row carries the site's matchup pair (owner 10/29: "offense ranking vs defensive ranking"): his team's
# rank at his position in that stat (offranks.py, 1 = produces the most) against the opponent's rank against that position in that stat
# (the sheet's defense tab, 1 = allows the most) - the same two numbers as the builder's pill. An under uses its stat's ranks (the builder
# shows none on unders); Rush + Rec carries two pairs, rushing and receiving; Longest Reception uses receiving yards; a TD leg uses the
# position's TD column. The page hides a row once its game kicks off or the risk layer rules the player out.
# The rules and the rank lookup live in sugmatch.py, shared with the Parlay Builder's strip.
import sugmatch as _SM
SUG_LO, SUG_HI = _SM.LO, _SM.HI
KICK = {g["gid"]: g.get("kick", "") for g in D.get("games", [])}
_pk = {x[0]: x for x in pool}
sug = [[k, pos, KICK.get(_pk[k][4], ""), mu] for k, pos, mu in _SM.pick(D["legs"], os.path.join(HERE, "in"), W) if k in _pk]
built = dt.datetime.now(dt.timezone.utc)
json.dump({"week": W, "built": built.isoformat(), "model": model, "pool": [x[:10] for x in pool], "sug": sug, "band": [SUG_LO, SUG_HI]}, open(os.path.join(OUT, "beat.json"), "w"), separators=(",", ":"))
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
.sug{{margin-top:14px;border-top:1px solid var(--line);padding-top:12px}} .sugh{{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}} .sugh b{{font-family:var(--display);font-weight:700;font-size:17px}} .sugh span{{font-family:var(--display);font-weight:700;font-size:13px;color:var(--mute)}}
.sug > small{{display:block;color:var(--mute);font-size:12.5px;line-height:1.4;margin:2px 0 8px}}
.sugf{{display:flex;gap:6px;overflow-x:auto;padding-bottom:4px;scrollbar-width:none}} .sugf::-webkit-scrollbar{{display:none}}
.sugf button{{flex:none;font:inherit;font-family:var(--display);font-weight:700;font-size:13.5px;letter-spacing:.05em;text-transform:uppercase;min-height:40px;padding:0 13px;border-radius:999px;border:1.5px solid var(--line);background:none;color:var(--ink);cursor:pointer}} .sugf button.on{{background:var(--ink);border-color:var(--ink);color:var(--bg)}} .sugf i{{flex:none;width:1px;background:var(--line);margin:6px 3px}}
.sugl{{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:6px;max-height:min(62vh,540px);overflow-y:auto;-webkit-overflow-scrolling:touch}}
.sugl li{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;align-items:start;background:var(--chalk);border-radius:10px;padding:9px 10px 9px 12px;cursor:pointer;border:1.5px solid transparent}} .sugl li:focus-visible{{outline:2px solid var(--red);outline-offset:1px}}
.sugl li.on{{border-color:var(--good);background:color-mix(in srgb,var(--good) 12%,var(--chalk))}} .sugl li.gone{{opacity:.45;cursor:not-allowed}} .sugl li.none{{display:block;cursor:default;color:var(--mute);font-size:13.5px;background:none;border:1.5px dashed var(--line)}}
.sugl .w b{{font-weight:600;font-size:15px}} .sugl .w b i{{font-style:normal;font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.06em;color:var(--mute);margin-left:6px}} .sugl .w small{{display:block;color:var(--mute);font-size:12.5px;line-height:1.4}}
.sugl .n{{text-align:right;white-space:nowrap}} .sugl .n b{{display:block;font-family:var(--display);font-weight:700;font-size:22px;line-height:1}} .sugl .n small{{display:block;font-family:var(--display);font-weight:700;font-size:13px;color:var(--mute);margin-top:3px}}
.sugl .mu{{grid-column:1 / -1;display:flex;flex-wrap:wrap;align-items:center;gap:5px 8px;margin-top:5px}} .sugl .mu em{{font-style:normal;font-size:12px;color:var(--mute)}} .sugl .mu .ad{{margin-left:auto;font-family:var(--display);font-weight:700;font-size:12.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink)}} .sugl li.on .ad{{color:var(--good)}}
.sugl .mup{{display:inline-flex;align-items:stretch;border-radius:5px;overflow:hidden;font-family:var(--display);font-weight:700;font-size:12px;letter-spacing:.03em;white-space:nowrap}} .sugl .mup i{{font-style:normal;color:#fff;padding:3px 7px}} .sugl .mup u{{text-decoration:none;font-weight:600;font-size:10.5px;padding:3px 5px;background:var(--card);color:var(--mute)}}
.btslip{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:8px}} .btslip button{{font:inherit;font-family:var(--display);font-weight:700;font-size:15px;letter-spacing:.05em;text-transform:uppercase;min-height:46px;padding:0 18px;border-radius:10px;border:1.5px solid var(--ink);background:none;color:var(--ink);cursor:pointer;flex:1 1 auto}} .btslip button:disabled{{opacity:.45;cursor:not-allowed}} .btslip a{{font-family:var(--display);font-weight:700;font-size:15px;letter-spacing:.05em;text-transform:uppercase;color:var(--red)}} .btslip a[hidden]{{display:none}}
.btnote{{font-size:13px;color:var(--mute);margin-top:8px;line-height:1.45}} .btnote.ok{{color:var(--good)}} .btnote.err{{color:var(--bad)}}
table.lb{{width:100%;border-collapse:collapse;font-size:14px}} .lb th,.lb td{{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left}} .lb th.r,.lb td.r{{text-align:right;font-variant-numeric:tabular-nums}} .lb thead th{{font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)}} .lb tr.model td{{color:var(--redtxt,var(--red));font-weight:600}} .lb tr.me td{{background:color-mix(in srgb,var(--good) 9%,transparent)}}
{LEAGUE_CSS}
.btchip{{display:inline-block;font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.08em;text-transform:uppercase;padding:3px 8px;border-radius:999px;background:var(--chalk);color:var(--mute)}}
</style>
<main class="bt" data-week="{W}">
<h1><small>Week {W}</small>Beat the model</h1>
<p class="m">Five FanDuel legs, yours against the model's. Every player prop priced between -150 and +150 is in the pool, one leg per player; the suggested list under your five has the ones near -110 with the model's chance and the matchup. Hits count, not odds, so there is no prize for five -800 favourites. Picks lock when a leg's game kicks off; Tuesday grades everyone and the leaderboard keeps the season score.</p>
<div class="btgrid">
 <section class="btcard"><h2>The model's five <small id="btmnote">this week's build</small></h2><ul class="legl" id="btmodel"></ul></section>
 <section class="btcard"><h2>Your five <small id="btyn">0 of 5</small></h2><ul class="legl" id="btmine"></ul>
  <div class="sug" id="btsug" hidden><div class="sugh"><b>Suggested legs</b><span id="btsugn"></span></div>
   <small>Priced near -110 (-125 to +100), one line per player and stat, the model's most likely first. Tap a leg to add it.</small>
   <div class="sugf" id="btsugf" role="group" aria-label="Filter the suggested legs"><button type="button" data-side="over" class="on">Overs</button><button type="button" data-side="under">Unders</button><i></i><button type="button" data-pos="" class="on">All</button><button type="button" data-pos="QB">QB</button><button type="button" data-pos="RB">RB</button><button type="button" data-pos="WR">WR</button><button type="button" data-pos="TE">TE</button></div>
   <ul class="sugl" id="btsugl"></ul>
   <p class="btnote">The colored pair is the matchup in that leg's stat: his team's rank at his position (#1 produces the most) against the defense's rank against that position (#1 allows the most). Green helps the leg, red hurts it.</p></div>
  <div class="pick"><input type="search" id="btq" placeholder="Search a player or market (Allen 250, Anytime TD, Receptions)" autocomplete="off"><ul class="pool" id="btpool"></ul></div>
  <div class="btsub"><input type="text" id="btname" maxlength="20" placeholder="Name on the leaderboard"><button type="button" id="btgo" disabled>Lock in five</button></div>
  <div class="btslip"><button type="button" id="btslip" disabled>Add my five to betslip</button><a href="/build/" id="btslipgo" hidden>Open betslip</a></div>
  <p class="btnote" id="btnote">Sign in (menu, top right) to submit. Picks are one set per week; you can change them until a chosen leg's game kicks off.</p>
 </section>
</div>
<section class="btcard" style="margin-top:14px" id="btlg"><h2>Your leagues <small>friends only · invite with a link</small></h2><div id="btlgbody"><p class="btnote">Loading…</p></div></section>
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
  // suggested legs (owner 11/11): beat.json "sug" = [key, pos, kick, [[stat, offense rank, defense rank], ...]], the model's most likely first
  var SUG = [], SIDE = 'over', SPOS = '';
  function rankColor(r){{ var t = (r-1)/31, h, l; if(t < 0.5){{ h = 140 - 95*(t/0.5); l = 0.30 + 0.08*(t/0.5); }} else {{ h = 45 - 45*((t-0.5)/0.5); l = 0.38 - 0.10*((t-0.5)/0.5); }} return 'hsl(' + Math.round(h) + ' 62% ' + Math.round(l*100) + '%)'; }}
  function ruled(l){{ try {{ var v = window.BSRisk && BSRisk.verdict ? BSRisk.verdict(l[1], l[5]) : null; return !!(v && v.level === 'block'); }} catch(e){{ return false; }} }}
  function paintSug(){{ var box = $('btsug'); if (!box) return; if (!SUG.length || LOCKED){{ box.hidden = true; return; }} box.hidden = false;
    var minePl = {{}}; MINE.forEach(function(k){{ minePl[POOL[k] ? POOL[k][1] : k.split('|')[0]] = 1; }});
    var rows = SUG.filter(function(s){{ var l = POOL[s[0]]; return l && !started(l) && !ruled(l) && (/^Under /.test(l[5]) ? SIDE === 'under' : SIDE === 'over') && (!SPOS || s[1] === SPOS); }});
    $('btsugn').textContent = MINE.length + ' of 5 picked';
    $('btsugl').innerHTML = rows.map(function(s){{ var k = s[0], l = POOL[k], u = /^Under /.test(l[5]), on = MINE.indexOf(k) >= 0, gone = !on && (minePl[l[1]] || MINE.length >= 5);
      var mu = s[3].map(function(m){{ var o = m[1], d = m[2];   // green helps this leg: an under wants the high numbers
        return '<span class="mup" title="' + esc(l[2]) + ' ' + s[1] + 's rank #' + o + ' in ' + esc(m[0]) + ' produced; ' + esc(l[3]) + ' ranks #' + d + ' in ' + esc(m[0]) + ' allowed to ' + s[1] + 's"><i style="background:' + rankColor(u ? 33 - o : o) + '">' + esc(l[2]) + ' ' + s[1] + 's #' + o + '</i><u>vs</u><i style="background:' + rankColor(u ? 33 - d : d) + '">' + esc(l[3]) + ' def #' + d + '</i></span><em>' + esc(m[0]) + '</em>'; }}).join('');
      return '<li class="' + (on ? 'on' : '') + (gone ? ' gone' : '') + '" data-k="' + esc(k) + '" role="button" tabindex="0" aria-pressed="' + on + '"><div class="w"><b>' + esc(l[1]) + '<i>' + s[1] + '</i></b><small>' + esc(line(l)) + '</small><small>' + esc(l[2]) + ' v ' + esc(l[3]) + (s[2] ? ' · ' + esc(s[2]) : '') + '</small></div>' +
        '<div class="n"><b>' + Math.round(l[8] * 100) + '%</b><small>' + am(l[7]) + '</small></div><div class="mu">' + mu + '<span class="ad">' + (on ? '\u2713 In your five' : gone ? (MINE.length >= 5 ? 'Five picked' : 'Player picked') : '+ Add') + '</span></div></li>'; }}).join('') ||
      '<li class="none">No ' + (SIDE === 'under' ? 'under' : 'over') + (SPOS ? ' for a ' + SPOS : '') + ' near -110 clears 50% right now. Try ' + (SIDE === 'under' ? 'Overs' : 'Unders') + ', another position, or the search below.</li>'; }}
  function tapSug(li){{ if (!li || LOCKED) return; var k = li.getAttribute('data-k'), l = POOL[k]; if (!l || started(l)) return;
    var i = MINE.indexOf(k); if (i >= 0) MINE.splice(i, 1); else {{ if (MINE.length >= 5) return; if (MINE.some(function(x){{ return POOL[x] && POOL[x][1] === l[1]; }})) return; MINE.push(k); }}
    var ul = $('btsugl'), top = ul.scrollTop; paintMine(); ul.scrollTop = top; }}
  $('btsugl').addEventListener('click', function(e){{ tapSug(e.target.closest('li[data-k]')); }});
  $('btsugl').addEventListener('keydown', function(e){{ if (e.key !== 'Enter' && e.key !== ' ') return; var li = e.target.closest('li[data-k]'); if (!li) return; e.preventDefault(); var k = li.getAttribute('data-k'); tapSug(li); var n = $('btsugl').querySelector('li[data-k="' + (window.CSS && CSS.escape ? CSS.escape(k) : k) + '"]'); if (n) n.focus(); }});
  $('btsugf').addEventListener('click', function(e){{ var b = e.target.closest('button'); if (!b) return; if (b.hasAttribute('data-side')) SIDE = b.getAttribute('data-side'); else SPOS = b.getAttribute('data-pos');
    [].forEach.call($('btsugf').querySelectorAll('button'), function(x){{ var on = x.hasAttribute('data-side') ? x.getAttribute('data-side') === SIDE : x.getAttribute('data-pos') === SPOS; x.classList.toggle('on', on); x.setAttribute('aria-pressed', on); }}); paintSug(); $('btsugl').scrollTop = 0; }});
  // owner 11/11 12:10 PM: "Make it so you can add your 5 legs from beat the model into your betslip" - the shared slip key the builder,
  // boards and home page read (bs_slipk_w<week>); legs of games under way and ruled-out players are left out, as the builder would.
  function slipGet(){{ try {{ var a = JSON.parse(localStorage.getItem('bs_slipk_w' + W) || '[]'); return Array.isArray(a) ? a : []; }} catch(e){{ return []; }} }}
  function slipOk(k){{ var l = POOL[k]; return !!l && !started(l) && !ruled(l); }}
  function paintSlipBtn(){{ var b = $('btslip'); if (!b) return; var can = MINE.filter(slipOk), have = slipGet(), left = can.filter(function(k){{ return have.indexOf(k) < 0; }});
    b.disabled = !left.length; b.textContent = !MINE.length ? 'Add my five to betslip' : !can.length ? 'These games have kicked off' : !left.length ? 'In your betslip \u2713' : 'Add my ' + (can.length === 5 ? 'five' : can.length + (can.length === 1 ? ' leg' : ' legs')) + ' to betslip';
    var go = $('btslipgo'); go.hidden = !have.length; go.textContent = 'Open betslip (' + have.length + ')'; }}
  $('btslip').addEventListener('click', function(){{ var have = slipGet(), n = 0; MINE.filter(slipOk).forEach(function(k){{ if (have.indexOf(k) < 0){{ have.push(k); n++; }} }}); if (!n) return;
    var v = JSON.stringify(have); try {{ localStorage.setItem('bs_slipk_w' + W, v); }} catch(e){{ $('btslip').textContent = 'This browser would not save the slip'; return; }}
    try {{ window.dispatchEvent(new StorageEvent('storage', {{key: 'bs_slipk_w' + W, newValue: v}})); }} catch(e){{}}
    paintSlipBtn(); }});
  function paintMine(){{ var h = MINE.map(function(k){{ return legLi(k, {{rm: !LOCKED}}); }}); while (h.length < 5) h.push('<li class="empty">Pick ' + (h.length + 1) + ' of 5</li>'); $('btmine').innerHTML = h.join(''); $('btyn').textContent = MINE.length + ' of 5' + (LOCKED ? ' · locked' : ''); $('btgo').disabled = LOCKED || MINE.length !== 5; paintPool(); paintSug(); paintSlipBtn(); }}
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
      // owner 11/10 pick'em: weekly winners (most hits that week; ties share it) next to the model's hits that week
      var byW = {{}}; picks.forEach(function(p){{ (byW[p.week] = byW[p.week] || []).push(p); }});
      var wks = Object.keys(byW).map(Number).sort(function(a, b){{ return b - a; }});
      if (wks.length){{ h += '<h2 style="margin-top:16px">Weekly winners <small>most hits of five · ties share the week</small></h2><table class="lb"><thead><tr><th>Week</th><th>Winner</th><th class="r">Hits</th><th class="r">Model</th><th class="r">Players</th></tr></thead><tbody>';
        wks.forEach(function(w){{ var ps = byW[w], top = Math.max.apply(null, ps.map(function(p){{ return p.hits || 0; }})), win = ps.filter(function(p){{ return (p.hits || 0) === top; }}).map(function(p){{ return esc(p.name || 'Anonymous') + (p.user_id === me ? ' (you)' : ''); }});
          var mr = model.filter(function(m){{ return m.week === w; }})[0];
          h += '<tr><td>' + w + '</td><td>' + win.join(', ') + '</td><td class="r">' + top + '/5</td><td class="r">' + (mr && mr.hits != null ? mr.hits + '/5' : '—') + '</td><td class="r">' + ps.length + '</td></tr>'; }});
        h += '</tbody></table>'; }}
      $('btlb').innerHTML = h; }}).catch(function(){{ $('btlb').innerHTML = '<p class="btnote">Leaderboard unavailable right now.</p>'; }}); }}
  fetch('/b/beat.json').then(function(r){{ return r.json(); }}).then(function(j){{ DATA = j; (j.pool || []).forEach(function(l){{ POOL[l[0]] = l; }}); MODEL = j.model || []; SUG = j.sug || []; paintModel(); paintMine();
    try {{ var nm = localStorage.getItem('bs_beat_name'); if (nm) $('btname').value = nm; }} catch(e){{}}
    // last week's grades for the model's card when the week has turned (graded-w<W-1>) - shown under the leaderboard by the Tuesday build
    var tries = 0; (function wait(){{ if (window.bsAccount && window.bsAccount.client){{ loadMine(); loadLB(); window.addEventListener('bs-account', function(){{ loadMine(); loadLB(); }}); document.addEventListener('bs-account', function(){{ loadMine(); loadLB(); }}); }} else if (tries++ < 40) setTimeout(wait, 250); else loadLB(); }})(); }});
}})();
</script>
{LEAGUE_JS}
'''
open(os.path.join(OUT, "beat.html"), "w").write(body)
print(f"wrote out/beat.html + beat.json: pool {len(pool)} legs in the -150..+150 band, model's five: " + "; ".join(model))
