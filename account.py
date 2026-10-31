"""account.py - optional BetSweep accounts (Supabase auth + per-user key/value sync) - v2026-10-20.

Imported by build_site.py, which writes /account.js and /me/index.html and puts the sign-in button in the site header.
Nothing on the site needs an account. Signed in, the browser-storage keys every page already uses (saved betslips, the builder slip,
trade scenarios, the hand-built fantasy team, the Sleeper username/league) are mirrored to the account and merged back on any device.

Supabase: project fuwiqijgkgbzvnfnsans, anon key below (public by design; row-level security keeps each user to their own rows).
One table, created once in the SQL editor (also in gen/account.sql):
  create table public.user_state (user_id uuid not null references auth.users(id) on delete cascade, key text not null,
    value jsonb not null, updated_at timestamptz not null default now(), primary key (user_id, key));
  alter table public.user_state enable row level security;
  create policy "own rows" on public.user_state for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
Auth: emailed magic link (Supabase's built-in mailer is enough to start; it is rate-limited, so switch to a real SMTP sender in
Authentication > SMTP once people sign up), 21+ attestation stored in the user's metadata; Google sign-in appears when
GOOGLE = True (needs a Google OAuth client added under Authentication > Providers).
"""
SUPABASE_URL = "https://fuwiqijgkgbzvnfnsans.supabase.co"
SUPABASE_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZ1d2lxaWpna2dienZuZm5zYW5zIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTI1NDMxNzMsImV4cCI6MjEwODExOTE3M30.cHHSmNne8GWkMvVO5n3DRIyrmC2D0hmpI8DNbOxs7eU"
GOOGLE = False
SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js"
# Slip alerts (owner 10/30): web push when a player on a saved slip is ruled out. Public VAPID key (the private half is a Supabase
# Edge Function secret, never in this bundle). Server side: gen/push/slip-alerts.ts + gen/push/push.sql (RUNBOOK "Slip alerts").
VAPID_PUBLIC = "BD3UuhEHyS404Cj8rHy4BOKOpVbRoWsAwL280ALvqmPlhct0Pc42PDiQ9UazK8KHF-sG4IxqEBpBWg3acsYljWk"

SQL = """-- BetSweep accounts: run once in the Supabase SQL editor
create table if not exists public.user_state (
  user_id uuid not null references auth.users(id) on delete cascade,
  key text not null,
  value jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, key)
);
alter table public.user_state enable row level security;
drop policy if exists "own rows" on public.user_state;
create policy "own rows" on public.user_state for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
"""

ACCOUNT_CSS = """
.sitenav .acct{display:flex;align-items:center;gap:6px;margin-left:auto}
.sitenav .acct+.tabs{margin-left:0}
.sitenav .acct button,.sitenav .acct a.me{font:inherit;font-size:13px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;padding:6px 11px;border-radius:999px;border:1.5px solid #d7332a;background:none;color:#d7332a;cursor:pointer;text-decoration:none;white-space:nowrap}
.sitenav .acct a.me{background:#d7332a;color:#fff}
.sitenav .acct a.me i{display:inline-block;width:18px;height:18px;border-radius:50%;background:#fff;color:#d7332a;font-style:normal;font-size:11px;line-height:18px;text-align:center;margin-right:5px}
.sitenav .acct button.out{border-color:#9a9388;color:#6b655c;padding:6px 8px}
@media(max-width:760px){.sitenav .acct{margin-left:auto;margin-right:6px}.sitenav .acct button,.sitenav .acct a.me{font-size:12px;padding:5px 9px}}
.bsdlg{position:fixed;inset:0;z-index:100;background:rgba(10,12,16,.55);display:flex;align-items:center;justify-content:center;padding:16px}
.bsdlg[hidden]{display:none}
.bsdlg .box{background:#f4efe3;color:#1b1a17;border-radius:16px;max-width:420px;width:100%;padding:22px 22px 18px;box-shadow:0 20px 60px rgba(0,0,0,.4);font-family:'IBM Plex Sans',system-ui,sans-serif}
.bsdlg h2{margin:0 0 4px;font-family:'Barlow Condensed',sans-serif;font-size:24px;letter-spacing:.02em}
.bsdlg p{margin:0 0 12px;font-size:13.5px;color:#5d574d;line-height:1.5}
.bsdlg input[type=email]{width:100%;box-sizing:border-box;font:inherit;font-size:16px;padding:10px 12px;border:1px solid #cfc7b6;border-radius:10px;background:#fff;color:#1b1a17}
.bsdlg label.chk{display:flex;gap:8px;align-items:flex-start;font-size:13px;margin:10px 0;color:#3b372f;line-height:1.4}
.bsdlg .go{width:100%;font:inherit;font-size:15px;font-weight:700;padding:11px;border:0;border-radius:10px;background:#d7332a;color:#fff;cursor:pointer;margin-top:4px}
.bsdlg .go[disabled]{opacity:.6}
.bsdlg .g{width:100%;font:inherit;font-size:14px;font-weight:600;padding:10px;border:1px solid #cfc7b6;border-radius:10px;background:#fff;color:#1b1a17;cursor:pointer;margin-top:8px}
.bsdlg .msg{font-size:13px;margin-top:10px;color:#2b6b3a;min-height:1.2em}.bsdlg .msg.err{color:#b3261e}
.bsdlg .x{float:right;background:none;border:0;font-size:22px;line-height:1;cursor:pointer;color:#6b655c;margin:-6px -6px 0 0}
.bsdlg small.lg{display:block;margin-top:10px;font-size:11.5px;color:#7a7368;line-height:1.4}
"""

ACCOUNT_JS = r"""
(function(){
  var CFG = window.__BS_ACCOUNT || {}; if(!CFG.url || !window.supabase) return;
  var sb = window.supabase.createClient(CFG.url, CFG.key, {auth: {persistSession: true, autoRefreshToken: true, detectSessionInUrl: true}});
  window.bsAccount = {client: sb, user: null};
  // ---- which browser-storage keys follow the account (everything a person builds; not caches) ----
  var SYNC = /^bs_(slips?_w\d+|slipk_w\d+|slipmeta_w\d+|trade_\d+|manual|teams|team_cur|sleeper_user|sleeper_league|team_mode|tip|tracked.*|dfs_saved|dfs_lu_.*|dfs_site|dfs_fmt|dfs_sal_.*|handle)$/;
  var META_KEY = 'bs_sync_meta', meta = {}; try{ meta = JSON.parse(localStorage.getItem(META_KEY)||'{}')||{}; }catch(e){}
  function saveMeta(){ try{ localStorage.setItem(META_KEY, JSON.stringify(meta)); }catch(e){} }
  var user = null, pending = {}, timer = null, ready = false;
  var _set = localStorage.setItem.bind(localStorage), _rm = localStorage.removeItem.bind(localStorage);
  localStorage.setItem = function(k, v){ _set(k, v); if (SYNC.test(k)){ meta[k] = Date.now(); saveMeta(); if (user && ready){ pending[k] = String(v); schedule(); } } };
  localStorage.removeItem = function(k){ _rm(k); if (SYNC.test(k)){ meta[k] = Date.now(); saveMeta(); if (user && ready){ pending[k] = null; schedule(); } } };
  function schedule(){ clearTimeout(timer); timer = setTimeout(flush, 800); }
  window.addEventListener('pagehide', function(){ if (Object.keys(pending).length) flush(); });   // owner 10/28: push the slip before leaving the page, not 800 ms later
  function flush(){ if(!user) return; var rows = [], dels = []; Object.keys(pending).forEach(function(k){ if (pending[k]===null) dels.push(k); else rows.push({user_id: user.id, key: k, value: {v: pending[k]}, updated_at: new Date(meta[k]||Date.now()).toISOString()}); }); pending = {};
    if (rows.length) sb.from('user_state').upsert(rows, {onConflict: 'user_id,key'}).then(function(r){ if(r.error) console.warn('sync', r.error.message); });
    if (dels.length) sb.from('user_state').delete().eq('user_id', user.id).in('key', dels).then(function(r){ if(r.error) console.warn('sync', r.error.message); }); }
  function pull(){ return sb.from('user_state').select('key,value,updated_at').then(function(r){ if (r.error){ console.warn('sync', r.error.message); if (/relation|does not exist/i.test(r.error.message)) toast('Account storage is not set up yet (table missing).'); return false; }
      var changed = false, remote = {}; (r.data||[]).forEach(function(x){ remote[x.key] = x; });
      // remote newer than local -> take it; local newer (or only local) -> push it
      Object.keys(remote).forEach(function(k){ var rt = Date.parse(remote[k].updated_at)||0, lt = meta[k]||0, lv = null; try{ lv = localStorage.getItem(k); }catch(e){}
        var rv = remote[k].value && remote[k].value.v; if (rv == null) return;
        if (lv === null || rt > lt){ if (lv !== rv){ _set(k, rv); changed = true; } meta[k] = rt; } else if (lt > rt && lv !== rv){ pending[k] = lv; } });
      try{ for (var i=0;i<localStorage.length;i++){ var k = localStorage.key(i); if (SYNC.test(k) && !remote[k]) pending[k] = localStorage.getItem(k); } }catch(e){}
      saveMeta(); flush(); return changed; }); }
  // ---- UI ----
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  var slot = document.getElementById('bsacct'); if(!slot) return;
  function paint(){ if (user){ var e = user.email||'', ini = (e[0]||'?').toUpperCase(); slot.innerHTML = '<a class="me" href="/me/" title="'+esc(e)+'"><i>'+esc(ini)+'</i>My BetSweep</a><button type="button" class="out" title="Sign out">Out</button>'; slot.querySelector('.out').addEventListener('click', function(){ sb.auth.signOut().then(function(){ location.reload(); }); }); }
    else { slot.innerHTML = '<button type="button" class="in">Sign in</button>'; slot.querySelector('.in').addEventListener('click', openDlg); } }
  var dlg = null;
  function openDlg(){ if(!dlg){ dlg = document.createElement('div'); dlg.className = 'bsdlg'; dlg.innerHTML = '<div class="box" role="dialog" aria-label="Sign in"><button class="x" type="button" aria-label="close">×</button><h2>Sign in to BetSweep</h2><p>Optional. Signed in, your saved betslips, built fantasy teams, trade scenarios and Sleeper league follow you to any device. Nothing here requires it.</p>'
      + '<input type="email" id="bsemail" placeholder="you@email.com" autocomplete="email"><label class="chk"><input type="checkbox" id="bs21"> I am 21 or older and I accept the <a href="/terms/" target="_blank">Terms</a> and <a href="/privacy/" target="_blank">Privacy Policy</a>.</label>'
      + '<button class="go" type="button" id="bsgo">Email me a sign-in link</button>' + (CFG.google ? '<button class="g" type="button" id="bsgoogle">Continue with Google</button>' : '') + '<div class="msg" id="bsmsg"></div><small class="lg">No passwords: the code (or link) in the email signs you in once, and you stay signed in on that device until you tap Out. We store what you build on the site and your email, nothing else. Information only, 21+, please bet responsibly.</small></div>';
      document.body.appendChild(dlg);
      dlg.addEventListener('click', function(e){ if (e.target===dlg || e.target.closest('.x')) dlg.hidden = true; });
      dlg.querySelector('#bsgo').addEventListener('click', function(){ var em = dlg.querySelector('#bsemail').value.trim(), ok = dlg.querySelector('#bs21').checked, m = dlg.querySelector('#bsmsg');
        if(!/.+@.+\..+/.test(em)){ m.textContent = 'Enter your email.'; m.className = 'msg err'; return; } if(!ok){ m.textContent = 'Please confirm you are 21+ and accept the terms.'; m.className = 'msg err'; return; }
        var b = dlg.querySelector('#bsgo'); b.disabled = true; m.textContent = 'Sending…'; m.className = 'msg';
        sb.auth.signInWithOtp({email: em, options: {emailRedirectTo: location.origin + location.pathname, data: {over21: true, accepted_terms_at: new Date().toISOString()}}}).then(function(r){ b.disabled = false;
          if (r.error){ m.textContent = r.error.message; m.className = 'msg err'; return; }
          // a 6-digit code typed here signs THIS app in - the email link opens the browser, which on a phone home-screen app is a different place
          m.innerHTML = 'Check your email. Type the <b>6-digit code</b> here (best on the home-screen app), or tap the link in the email.'; m.className = 'msg';
          var cb = dlg.querySelector('#bscode'); if (!cb){ cb = document.createElement('div'); cb.id = 'bscode'; cb.innerHTML = '<input type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="8" placeholder="123456" id="bsotp" style="width:100%;box-sizing:border-box;font:inherit;font-size:22px;letter-spacing:.3em;text-align:center;padding:10px;border:1px solid #cfc7b6;border-radius:10px;margin-top:10px"><button class="go" type="button" id="bsverify">Sign in with code</button>'; m.parentNode.insertBefore(cb, m.nextSibling);
            var vin = cb.querySelector('#bsotp'), vb = cb.querySelector('#bsverify');
            function verify(){ var code = vin.value.replace(/\D/g,''); if (code.length < 6){ m.textContent = 'Enter the code from the email.'; m.className = 'msg err'; return; } vb.disabled = true; m.textContent = 'Signing in…'; m.className = 'msg';
              sb.auth.verifyOtp({email: em, token: code, type: 'email'}).then(function(v){ vb.disabled = false; if (v.error){ m.textContent = v.error.message.indexOf('expired') >= 0 || v.error.message.indexOf('invalid') >= 0 ? 'That code did not work - check it, or send a new email.' : v.error.message; m.className = 'msg err'; } else { m.textContent = 'Signed in. You stay signed in on this device until you tap Out.'; dlg.hidden = true; } }); }
            vb.addEventListener('click', verify); vin.addEventListener('keydown', function(e){ if (e.key === 'Enter') verify(); }); vin.addEventListener('input', function(){ if (vin.value.replace(/\D/g,'').length === 6) verify(); }); }
          setTimeout(function(){ var i = dlg.querySelector('#bsotp'); if (i) i.focus(); }, 50); }); });
      var g = dlg.querySelector('#bsgoogle'); if (g) g.addEventListener('click', function(){ sb.auth.signInWithOAuth({provider: 'google', options: {redirectTo: location.origin + location.pathname}}); }); }
    dlg.hidden = false; setTimeout(function(){ var i = dlg.querySelector('#bsemail'); if(i) i.focus(); }, 50); }
  function toast(t){ var el = document.createElement('div'); el.textContent = t; el.style.cssText = 'position:fixed;left:50%;bottom:70px;transform:translateX(-50%);background:#1b1a17;color:#fff;padding:9px 14px;border-radius:999px;font:13px IBM Plex Sans,system-ui,sans-serif;z-index:120;box-shadow:0 8px 24px rgba(0,0,0,.3)'; document.body.appendChild(el); setTimeout(function(){ el.remove(); }, 3500); }
  function onSession(s){ var u = s && s.user; if (u && (!user || user.id !== u.id)){ user = u; window.bsAccount.user = u; paint(); pull().then(function(changed){ ready = true; document.dispatchEvent(new CustomEvent('bs-account', {detail: {user: u, changed: changed}})); if (changed && !/\/me\//.test(location.pathname)){ toast('Synced from your account'); setTimeout(function(){ location.reload(); }, 900); } }); }
    else if (!u){ user = null; window.bsAccount.user = null; ready = false; paint(); document.dispatchEvent(new CustomEvent('bs-account', {detail: {user: null}})); } }
  paint();
  sb.auth.getSession().then(function(r){ onSession(r.data && r.data.session); });
  sb.auth.onAuthStateChange(function(ev, s){ if (ev === 'SIGNED_IN' || ev === 'INITIAL_SESSION' || ev === 'TOKEN_REFRESHED') onSession(s); if (ev === 'SIGNED_OUT') onSession(null); if (ev === 'SIGNED_IN' && dlg) dlg.hidden = true; });
})();
"""

ME_CSS = """
.pushbtns{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px} .pushbtns button{font:inherit;font-size:13px;font-weight:700;padding:8px 14px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.pushbtns #pushon{background:var(--red);border-color:var(--red);color:#fff} .pushprefs{display:grid;gap:8px;margin-top:12px;font-size:13.5px} .pushprefs[hidden]{display:none} .pushprefs label{display:flex;gap:8px;align-items:flex-start;line-height:1.4} .pushprefs input{width:18px;height:18px;margin-top:1px;accent-color:var(--red)} #pushmsg:empty{display:none} #pushmsg.ok{color:var(--good)} #pushmsg.err{color:var(--bad)}
.me{max-width:980px;margin:0 auto;padding:0 16px 40px}
.me .card{background:var(--card,#fff);border:1px solid var(--line,#d8d1c2);border-radius:14px;padding:16px 18px;margin:14px 0}
.me h1{font-family:'Barlow Condensed',sans-serif;font-size:30px;margin:18px 0 4px;letter-spacing:.02em}
.me h2{font-family:'Barlow Condensed',sans-serif;font-size:20px;margin:0 0 8px;display:flex;justify-content:space-between;align-items:baseline}
.me h2 a{font-size:13px;font-family:'IBM Plex Sans',system-ui,sans-serif;font-weight:500}
.me p.m{color:var(--mute,#6b655c);font-size:13.5px;line-height:1.55;margin:4px 0 10px}
.me ul{list-style:none;margin:0;padding:0}
.me li{padding:9px 0;border-top:1px solid var(--line,#d8d1c2);font-size:14px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.me li:first-child{border-top:0}
.me li b{font-family:'Barlow Condensed',sans-serif;font-size:16px}
.me li small{color:var(--mute,#6b655c)}
.me li .legs{flex-basis:100%;font-size:12.5px;color:var(--mute,#6b655c);line-height:1.5}
.me .cta{display:inline-block;font-weight:700;padding:10px 16px;border-radius:10px;background:#d7332a;color:#fff;text-decoration:none}
.me .none{color:var(--mute,#6b655c);font-size:13.5px}
.me .res{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border-radius:4px;background:#e4ddcc;color:#5d574d}
.me .res.hit{background:#2b6b3a;color:#fff}.me .res.miss{background:#b3261e;color:#fff}
.me i.g{display:inline-block;width:16px;height:16px;border-radius:50%;text-align:center;line-height:16px;font-size:11px;font-style:normal;margin-right:3px;background:#e4ddcc;color:#5d574d}
.me i.g.hit{background:#2b6b3a;color:#fff}.me i.g.miss{background:#b3261e;color:#fff}
.me .legs em{font-style:normal;color:#9a9388}
.me a.fdl{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;letter-spacing:.06em;text-transform:uppercase;background:#1493ff;color:#fff;padding:3px 9px;border-radius:4px;text-decoration:none}
"""

ME_JS = r"""
(function(){
  function g(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } }
  function keys(re){ var out = []; try{ for (var i=0;i<localStorage.length;i++){ var k = localStorage.key(i); if (re.test(k)) out.push(k); } }catch(e){} return out.sort(); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function odds(o){ o = +o; return isNaN(o) ? '' : (o > 0 ? '+' + o : String(o)); }
  var NICK = {"Cardinals":"ARI","Falcons":"ATL","Ravens":"BAL","Bills":"BUF","Panthers":"CAR","Bears":"CHI","Bengals":"CIN","Browns":"CLE","Cowboys":"DAL","Broncos":"DEN","Lions":"DET","Packers":"GB","Texans":"HOU","Colts":"IND","Jaguars":"JAX","Chiefs":"KC","Raiders":"LV","Chargers":"LAC","Rams":"LA","Dolphins":"MIA","Vikings":"MIN","Patriots":"NE","Saints":"NO","Giants":"NYG","Jets":"NYJ","Eagles":"PHI","Steelers":"PIT","49ers":"SF","Seahawks":"SEA","Buccaneers":"TB","Titans":"TEN","Commanders":"WAS"};
  var BOX = {};   // week -> {box, games} once fetched
  function getBox(w){ if (BOX[w] !== undefined) return Promise.resolve(BOX[w]); return fetch('/data/box-w'+w+'.json').then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }).then(function(d){ BOX[w] = d; return d; }); }
  // grade one slip key against the week's box scores: returns {r: 'HIT'|'MISS'|'PUSH'|'?', a: actual text}
  function gradeKey(k, d){ if (!d) return {r: '?', a: 'not final'}; var p = String(k).split('|'); if (p.length < 3) return {r: '?', a: ''};
    var who = p[0], m = p[1], ln = parseFloat(p[2]); var S = {"Passing Yards":0, "Passing TDs":1, "Rushing Yards":3, "Receptions":5, "Receiving Yards":6, "Longest Reception":8};
    function team(t){ var n = Object.keys(NICK).filter(function(x){ return t.indexOf(x) >= 0; })[0]; return n ? NICK[n] : null; }
    function gameOf(ab){ var out = null; Object.keys(d.games||{}).forEach(function(g){ var q = g.split('-'); if (q[0]===ab || q[1]===ab) out = {a:q[0], h:q[1], as:d.games[g][0], hs:d.games[g][1]}; }); return out; }
    if (m === 'Moneyline'){ var t = team(who), gm = t && gameOf(t); if (!gm) return {r:'?', a:'game not final'}; var marg = (t===gm.h ? gm.hs-gm.as : gm.as-gm.hs); return {r: marg>0?'HIT':marg<0?'MISS':'PUSH', a: gm.a+' '+gm.as+' @ '+gm.h+' '+gm.hs}; }
    if (m === 'Spread'){ var t2 = team(who), gm2 = t2 && gameOf(t2), mm = who.match(/([+-]?\d+(?:\.\d+)?)\s*$/); if (!gm2 || !mm) return {r:'?', a:'game not final'}; var v = (t2===gm2.h ? gm2.hs-gm2.as : gm2.as-gm2.hs) + parseFloat(mm[1]); return {r: v>0?'HIT':v<0?'MISS':'PUSH', a: gm2.a+' '+gm2.as+' @ '+gm2.h+' '+gm2.hs}; }
    if (m === 'Total') return {r:'?', a:'totals need the game - coming'};
    if (m === 'First TD') return {r:'?', a:'first TD graded on the receipt'};
    if (m === 'Either TD'){ var names = who.split(/\s+or\s+/); var hit = names.some(function(n){ var b = d.box[n.trim()]; return b && (b[4]+b[7]) >= 1; }); var any = names.some(function(n){ return !!d.box[n.trim()]; }); return any ? {r: hit?'HIT':'MISS', a: hit?'scored':'no TD'} : {r:'?', a:'no box score'}; }
    var b = d.box[who]; if (!b) return {r:'?', a:'no box score (did not play?)'};
    if (/^Under /.test(m)){ var mu = S[m.slice(6)]; if (mu == null) return {r:'?', a:''}; var vu = b[mu]; return {r: vu < ln - 0.5 ? 'HIT' : 'MISS', a: String(vu)}; }   // FanDuel main-line unders (key line = rounded X.5)
    if (m === 'Anytime TD'){ var td = b[4]+b[7]; return {r: td>=1?'HIT':'MISS', a: td+' TD'}; }
    if (m === '2+ TD' || m === '3+ TD'){ var td2 = b[4]+b[7], need2 = m === '2+ TD' ? 2 : 3; return {r: td2>=need2?'HIT':'MISS', a: td2+' TD'}; }
    if (m === 'Rush + Rec Yards'){ var y = b[3]+b[6]; return {r: y>=ln?'HIT':'MISS', a: y+' yds'}; }
    if (S[m] != null){ var v2 = b[S[m]]; return {r: v2>=ln?'HIT':'MISS', a: String(v2)}; }
    return {r:'?', a:''}; }
  function dec(o){ o = +o; if (!o) return null; return o > 0 ? o/100 + 1 : 100/(-o) + 1; }
  function render(){
    var u = window.bsAccount && window.bsAccount.user; var who = document.getElementById('who');
    who.innerHTML = u ? 'Signed in as <b>'+esc(u.email||'')+'</b>. Everything below follows you to any device you sign in on.' : 'Not signed in: this page shows what is saved in this browser only. <button type="button" class="cta" id="mein" style="margin-left:8px;padding:6px 12px;font-size:13px">Sign in to sync it</button>';
    var b = document.getElementById('mein'); if (b) b.addEventListener('click', function(){ var s = document.querySelector('#bsacct .in'); if (s) s.click(); });
    // saved betslips (live page), by week
    var sl = [], ks = keys(/^bs_slips_w\d+$/); ks.forEach(function(k){ var w = k.replace('bs_slips_w',''); try{ (JSON.parse(g(k))||[]).forEach(function(s){ sl.push({w: +w, s: s}); }); }catch(e){} });
    sl.sort(function(a,b){ return b.w - a.w; });
    var el = document.getElementById('slips');
    if (!sl.length){ el.innerHTML = '<li class="none">No saved betslips yet. Build one on the Live page or the Parlay Builder, or tap Tail on a promoted bet, and it shows up here.</li>'; document.getElementById('record').textContent = ''; }
    else { el.innerHTML = '<li class="none">Grading…</li>';
      Promise.all(sl.map(function(x){ return getBox(x.w); })).then(function(ds){ var W = 0, L = 0, U = 0, P = 0, html = '';
        sl.forEach(function(x, i){ var s = x.s, d = ds[i], gs = (s.keys||[]).map(function(k){ return {k:k, g: gradeKey(k, d)}; });
          var live = gs.filter(function(g){ return g.g.r !== 'PUSH'; }); var res = live.some(function(g){ return g.g.r==='MISS'; }) ? 'MISS' : live.every(function(g){ return g.g.r==='HIT'; }) ? 'HIT' : 'PENDING';
          var stake = +s.stake || 1, dd = dec(s.odds), u = res==='HIT' ? (dd ? (dd-1)*stake : null) : res==='MISS' ? -stake : null;
          if (res==='HIT'){ W++; if (u!=null) U += u; } else if (res==='MISS'){ L++; U += u; } else P++;
          var bet = (res==='PENDING' && s.fd && !d) ? '<a class="fdl" href="'+esc(s.fd)+'" target="_blank" rel="noopener">Bet on FanDuel</a>' : '';
          html += '<li><b>'+esc(s.name||'Slip')+'</b><span class="res '+res.toLowerCase()+'">'+(res==='HIT'?'Cashed':res==='MISS'?'Missed':d?'Pending':'Not played yet')+'</span>'+bet+'<small>Week '+x.w+' · '+gs.length+' legs'+(s.odds? ' · '+odds(s.odds) : '')+' · '+stake+'u'+(u!=null? ' · '+(u>=0?'+':'')+u.toFixed(2)+'u' : '')+'</small><span class="legs">'+gs.map(function(g){ var q = String(g.k).split('|'); var lab = q[1]==='Anytime TD'||q[1]==='First TD'||q[1]==='Either TD' ? q[0]+' '+q[1].toLowerCase() : q[1]==='Moneyline'||q[1]==='Spread'||q[1]==='Total' ? q[0] : q[0]+' '+q[2]+'+ '+q[1].toLowerCase(); return '<i class="g '+g.g.r.replace('?','na').toLowerCase()+'">'+(g.g.r==='HIT'?'✓':g.g.r==='MISS'?'✗':g.g.r==='PUSH'?'=':'·')+'</i>'+esc(lab)+(g.g.a? ' <em>('+esc(g.g.a)+')</em>' : ''); }).join(' &nbsp; ')+'</span></li>'; });
        el.innerHTML = html; document.getElementById('record').textContent = (W+L) ? W+'–'+L+(P? ' ('+P+' pending)':'')+' · '+(U>=0?'+':'')+U.toFixed(2)+'u at 1u = your stake' : (P? P+' pending' : ''); }); }
    // exposure (owner 10/26, after 'I have so much riding on Ken Walker'): the latest week's saved slips + the working builder slip,
    // grouped by player (an either-TD leg counts for both names; game lines by their text). Stake and to-win at the slip's own stake/odds.
    (function(){ var ex = document.getElementById('expo'); if (!ex) return;
      var wk = sl.length ? Math.max.apply(null, sl.map(function(x){ return x.w; })) : 0, cur = sl.filter(function(x){ return x.w === wk; }).map(function(x){ return x.s; });
      var bk2 = keys(/^bs_slipk_w\d+$/).pop(); if (bk2 && +bk2.replace('bs_slipk_w','') >= wk){ try{ var bl2 = JSON.parse(g(bk2))||[]; if (bl2.length) cur.push({name: 'Builder slip (not saved)', keys: bl2}); }catch(e){} }
      if (!cur.length){ ex.innerHTML = '<li class="none">No open slips saved for this week.</li>'; return; }
      var P = {};
      cur.forEach(function(s){ var stake = +s.stake || 0, dd = dec(s.odds), win = (stake && dd) ? stake * (dd - 1) : 0, seen = {};
        (s.keys||[]).forEach(function(k){ var q = String(k).split('|'), who = q[0], m = q[1] || '';
          var names = /^either/i.test(m) ? who.split(/\s+or\s+|\s*\/\s*/) : [who];
          names.forEach(function(n){ n = n.trim(); if (!n) return; var e = P[n] = P[n] || {n: n, slips: [], stake: 0, win: 0, legs: {}};
            e.legs[(q[1]||'') + (q[2] && q[2] !== '1' ? ' ' + q[2] + '+' : '')] = 1;
            if (!seen[n]){ seen[n] = 1; e.slips.push(s.name || 'Slip'); e.stake += stake; e.win += win; } }); }); });
      var rows = Object.keys(P).map(function(k){ return P[k]; }).filter(function(e){ return e.slips.length >= 2; })
        .sort(function(a, b){ return (b.slips.length - a.slips.length) || (b.stake - a.stake); });
      var tot = cur.length;
      ex.innerHTML = rows.length ? rows.map(function(e){ var share = Math.round(e.slips.length / tot * 100);
        return '<li><b>'+esc(e.n)+'</b><span class="res '+(share >= 50 ? 'miss' : 'pending')+'">'+e.slips.length+' of '+tot+' slips</span><small>'
          + (e.stake ? e.stake.toFixed(2).replace(/\.00$/, '')+' staked on him' + (e.win ? ' · '+e.win.toFixed(0)+' to win dies with him' : '') + ' · ' : '')
          + 'legs: '+esc(Object.keys(e.legs).join(', '))+'</small><span class="legs">'+esc(e.slips.join(' · '))+'</span></li>'; }).join('')
        + (rows[0] && rows[0].slips.length / tot >= 0.5 ? '<li class="none">More than half of your open slips need '+esc(rows[0].n)+'. One quiet night from him and they all go together.</li>' : '')
        : '<li class="none">No player is in more than one of your '+tot+' open slips - nicely spread.</li>';
    })();
    // builder slip (this week's working slip)
    var bk = keys(/^bs_slipk_w\d+$/).pop(), bl = []; if (bk){ try{ bl = JSON.parse(g(bk))||[]; }catch(e){} }
    document.getElementById('builder').innerHTML = bk && bl.length ? '<li><b>Working slip</b><small>Week '+bk.replace('bs_slipk_w','')+' · '+bl.length+' legs</small><span class="legs">'+esc(bl.map(function(k){ return String(k).split('|').slice(0,3).join(' '); }).join(' · '))+'</span></li>' : '<li class="none">Nothing in the builder slip right now.</li>';
    // trade scenarios
    var tk = keys(/^bs_trade_\d+$/).pop(), t = null; if (tk){ try{ t = JSON.parse(g(tk)); }catch(e){} }
    document.getElementById('trades').innerHTML = t && ((t.A||[]).length || (t.B||[]).length) ? '<li><b>Side A gives</b><small>'+esc((t.A||[]).join(', ')||'—')+'</small></li><li><b>Side B gives</b><small>'+esc((t.B||[]).join(', ')||'—')+'</small></li><li><small>'+(t.dyn?'dynasty':'rest of season')+' · '+(t.sf?'superflex':'1QB')+(t.tep?' · TE +'+t.tep:'')+' · '+t.teams+' teams</small></li>' : '<li class="none">No trade scenario saved.</li>';
    // fantasy
    var su = g('bs_sleeper_user'), man = null; try{ man = JSON.parse(g('bs_manual')||'null'); }catch(e){}
    var mt = []; if (su) mt.push('<li><b>Sleeper</b><small>@'+esc(su)+(g('bs_sleeper_league')? ' · league remembered' : '')+'</small></li>');
    var tms = []; try{ tms = JSON.parse(g('bs_teams')||'[]')||[]; }catch(e){}
    tms.forEach(function(t){ mt.push('<li><b>'+esc(t.name)+'</b><small>'+((t.data&&t.data.r)||[]).length+' players · <a href="/team/">open on the Fantasy page</a></small></li>'); });
    if (!tms.length && man && (man.r||[]).length) mt.push('<li><b>Hand-built team</b><small>'+man.r.length+' players, not saved by name yet - tap Save team on the Fantasy page</small></li>');
    var lus = []; try{ lus = JSON.parse(g('bs_dfs_saved')||'[]')||[]; }catch(e){}
    lus.sort(function(a,b){ return (b.week||0)-(a.week||0); }).forEach(function(x){ mt.push('<li><b>'+esc(x.name)+'</b><small>DFS · '+(x.site==='fd'?'FanDuel':x.site==='dk'?'DraftKings':esc(x.site||''))+(x.sg?' showdown':'')+' · Week '+x.week+' · '+(x.lu||[]).length+' players · <a href="/dfs/">open</a></small></li>'); });
    document.getElementById('fantasy').innerHTML = mt.join('') || '<li class="none">No saved teams or DFS lineups yet. Build one on the Fantasy or DFS page and tap Save.</li>';
  }
  render(); document.addEventListener('bs-account', render);
})();
"""

def _base_css():
    """the site's colour tokens, fonts, light/dark modes and body rule, taken from template.html so /me/ matches every other page
    (audit 10/26: /me/ rendered in Times on white, ignoring dark mode)"""
    import os, re
    try:
        t = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html")).read()
        link = re.search(r'<link rel="stylesheet" href="https://fonts\.googleapis[^>]*>', t).group(0)
        css = t[t.index("<style>") + 7: t.index("/* ---- masthead ---- */")]
        return link, css + "a{color:var(--ink)}\n"
    except Exception: return "", ""
def me_page():
    _link, _base = _base_css()
    return f"""<title>My BetSweep</title>
<meta name="description" content="Your saved betslips, built fantasy teams, trade scenarios and Sleeper league - in this browser, or on every device when you sign in.">
{_link}
<style>{_base}{ME_CSS}</style>
<div class="me">
 <h1>My BetSweep</h1>
 <p class="m" id="who"></p>
 <div class="card"><h2>Your record <span id="record" style="font-size:16px"></span></h2><p class="m">Every slip you save - from the Parlay Builder's Save slip, the Live page, or Tail on a promoted bet - sits here with its Bet on FanDuel button until kickoff, then is graded from the box scores after the games, the same way we grade our own legs. Units at the slip's odds and stake; a push drops the leg. Totals and first-TD legs show as pending until that grading lands.</p><ul id="slips"></ul></div>
 <div class="card"><h2>Exposure this week</h2><p class="m">Who your open slips depend on. Every player in at least two of this week's saved slips, with the stake riding on him and what you would stop being able to win if he has a bad night. Only slips saved here count - tap Tail on a promo or Save slip in the builder for the bets you place.</p><ul id="expo"></ul></div>
 <div class="card" id="alerts"><h2>Slip alerts</h2><p class="m">Get a notification on this device when a player on one of your saved slips (or your open betslip) is ruled <b>Out</b> or <b>Doubtful</b> before kickoff - with a swap idea from the same game - plus, if you want them, live updates on your saved slips during games and a Thursday note when the Model's Best picks are up. Alerts follow the slips saved to your account, so sign in first.</p><p class="m" id="pushmsg"></p><div class="pushbtns"><button type="button" id="pushon" hidden>Turn on alerts</button><button type="button" id="pushtest" hidden>Send a test alert</button><button type="button" id="pushoff" hidden>Turn off on this device</button></div><div class="pushprefs" id="pushprefs" hidden><label><input type="checkbox" id="pplive" checked> Live updates during games: a leg on a saved slip hits or busts, a slip cashes</label><label><input type="checkbox" id="ppweekly" checked> Thursday note when the week's Model's Best picks are up</label></div></div>
 <div class="card"><h2>Parlay Builder <a href="/build/">Open →</a></h2><ul id="builder"></ul></div>
 <div class="card"><h2>Trade calculator <a href="/trade/">Open →</a></h2><ul id="trades"></ul></div>
 <div class="card"><h2>Fantasy teams &amp; DFS lineups <a href="/team/">Fantasy →</a></h2><ul id="fantasy"></ul></div>
 <p class="m">Accounts are optional and free. Sign out from the header at any time; to delete your account and everything saved with it, email support@betsweep.co from the signed-in address.</p>
</div>
<script>{ME_JS}</script>
<script>{PUSH_JS.replace("__VAPID__", VAPID_PUBLIC).replace("__SB__", SUPABASE_URL)}</script>"""

PUSH_JS = r"""
(function(){
  var VAPID = '__VAPID__', FN = '__SB__/functions/v1/slip-alerts';
  var msg = document.getElementById('pushmsg'), on = document.getElementById('pushon'), test = document.getElementById('pushtest'), off = document.getElementById('pushoff');
  if(!msg) return;
  function say(t, c){ msg.textContent = t; msg.className = 'm ' + (c || ''); }
  var prefs = document.getElementById('pushprefs'), pl = document.getElementById('pplive'), pw = document.getElementById('ppweekly'), curEp = null;
  function show(a, b, c){ on.hidden = !a; test.hidden = !b; off.hidden = !c; if(prefs) prefs.hidden = !c; }
  function loadPrefs(ep){ curEp = ep; if(!client() || !ep) return; client().from('push_subs').select('live,weekly').eq('endpoint', ep).maybeSingle().then(function(r){ if(r && r.data){ pl.checked = r.data.live !== false; pw.checked = r.data.weekly !== false; } }); }
  function savePref(){ if(!client() || !curEp) return; client().from('push_subs').update({live: pl.checked, weekly: pw.checked}).eq('endpoint', curEp).then(function(r){ if(r && r.error) say(/column/i.test(r.error.message) ? 'Saved alerts work; these two settings switch on after the next server update.' : r.error.message, 'err'); else say('Saved.', 'ok'); }); }
  if(pl) pl.addEventListener('change', savePref); if(pw) pw.addEventListener('change', savePref);
  function key(s){ s = s.replace(/-/g, '+').replace(/_/g, '/'); while(s.length % 4) s += '='; var b = atob(s), u = new Uint8Array(b.length); for(var i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }
  var supported = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent), standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  function user(){ return window.bsAccount && window.bsAccount.user; }
  function client(){ return window.bsAccount && window.bsAccount.client; }
  function refresh(){
    if(!supported){ show(0,0,0); say(ios && !standalone ? 'On iPhone, alerts need the app: tap Share, then Add to Home Screen, open BetSweep from your home screen and come back here.' : 'This browser cannot receive alerts.'); return; }
    if(!user()){ show(0,0,0); say('Sign in (top right) to turn on alerts.'); return; }
    if(Notification.permission === 'denied'){ show(0,0,0); say('Notifications are blocked for betsweep.co in this browser\'s settings - allow them there, then reload.', 'err'); return; }
    navigator.serviceWorker.ready.then(function(reg){ return reg.pushManager.getSubscription(); }).then(function(sub){
      if(sub && Notification.permission === 'granted'){ show(0,1,1); say('Alerts are on for this device.', 'ok'); loadPrefs(sub.endpoint); } else { show(1,0,0); say(''); } }).catch(function(){ show(1,0,0); });
  }
  function save(sub){
    var j = sub.toJSON(), u = user();
    return client().from('push_subs').upsert({endpoint: j.endpoint, user_id: u.id, p256dh: j.keys.p256dh, auth: j.keys.auth, ua: navigator.userAgent.slice(0, 200)}, {onConflict: 'endpoint'}).then(function(r){ if(r.error) throw r.error; });
  }
  on.addEventListener('click', function(){
    on.disabled = true; say('Asking for permission…');
    Notification.requestPermission().then(function(p){
      if(p !== 'granted') throw new Error('Notifications were not allowed.');
      return navigator.serviceWorker.ready;
    }).then(function(reg){ return reg.pushManager.getSubscription().then(function(s){ return s || reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: key(VAPID)}); }); })
    .then(function(sub){ return save(sub).then(function(){ return sub; }); }).then(function(sub){ say('Alerts are on for this device.', 'ok'); show(0,1,1); loadPrefs(sub.endpoint); })
    .catch(function(e){ var t = String(e && (e.message || e)); say(/push_subs|relation|does not exist/i.test(t) ? 'Alerts are not switched on on our side yet - try again soon.' : t, 'err'); })
    .then(function(){ on.disabled = false; });
  });
  test.addEventListener('click', function(){
    test.disabled = true; say('Sending…');
    client().auth.getSession().then(function(r){ var tok = r.data && r.data.session && r.data.session.access_token;
      return fetch(FN, {method: 'POST', headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok}, body: JSON.stringify({test: true})}); })
    .then(function(r){ return r.text().then(function(t){ var j = null; try { j = JSON.parse(t); } catch(e){} return {s: r.status, j: j, t: t}; }); })
    .then(function(x){ var j = x.j; if(j && j.sent) say('Sent - it should show up in a few seconds.', 'ok'); else say((j && j.error) || ('The alert service answered ' + x.s + ': ' + String((j && (j.message || j.msg)) || x.t || 'no details').slice(0, 160)), 'err'); })
    .catch(function(){ say('Could not reach the alert service.', 'err'); }).then(function(){ test.disabled = false; });
  });
  off.addEventListener('click', function(){
    navigator.serviceWorker.ready.then(function(reg){ return reg.pushManager.getSubscription(); }).then(function(sub){ if(!sub) return;
      var ep = sub.endpoint; return sub.unsubscribe().then(function(){ return client() && client().from('push_subs').delete().eq('endpoint', ep); }); })
    .then(function(){ say('Alerts are off for this device.'); show(1,0,0); }).catch(function(){ refresh(); });
  });
  document.addEventListener('bs-account', refresh); setTimeout(refresh, 1500); refresh();
})();
"""
