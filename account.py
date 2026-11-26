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
# owner 11/10 (deep dive): anonymous page counts - one "+1" per page view, the path only (sql/betsweep-pagehits.sql: table page_hits,
# function hit). OFF until the owner has run that SQL: switching it on adds the request to every page AND changes the privacy page in
# the same build (build_legal.py reads this flag), because that page promises to change first. Set PAGE_COUNTS_SINCE to the date.
# 11/10 9:25 PM: the owner had the SQL in hand ("On it"), so the switch is on. The request fails quietly until the function exists and
# starts counting the moment it does - nothing else to do on either side. (The session cannot reach Supabase to confirm the function.)
PAGE_COUNTS = True
# owner 11/17 ("I want all four"): "tell me when a slip posts" - one more switch under Slip alerts. It stayed off until the owner had run
# sql/push_promo.sql and redeployed push/slip-alerts.ts (promoUp): a switch that does nothing is worse than none. The box reads and
# writes push_subs.promo on its own, so a database without the column only hides it.
PROMO_ALERTS = True   # 11/17, 9:23 PM CT: the owner ran sql/push_promo.sql and redeployed slip-alerts ("Ran the sql and slip alerts")
# 11/20 (owner: "push notifications about prominent players being out or released"): same rule as PROMO_ALERTS. False until the owner
# has run sql/push_news.sql and redeployed slip-alerts.ts (newsUp).
NEWS_ALERTS = True   # 11/20, 8:22 PM CT: the owner ran betsweep-push-news.sql and redeployed slip-alerts ("Did the sql and slip alerts")
TEAMS32 = [("ARI", "Arizona Cardinals"), ("ATL", "Atlanta Falcons"), ("BAL", "Baltimore Ravens"), ("BUF", "Buffalo Bills"), ("CAR", "Carolina Panthers"), ("CHI", "Chicago Bears"), ("CIN", "Cincinnati Bengals"),
           ("CLE", "Cleveland Browns"), ("DAL", "Dallas Cowboys"), ("DEN", "Denver Broncos"), ("DET", "Detroit Lions"), ("GB", "Green Bay Packers"), ("HOU", "Houston Texans"), ("IND", "Indianapolis Colts"),
           ("JAX", "Jacksonville Jaguars"), ("KC", "Kansas City Chiefs"), ("LV", "Las Vegas Raiders"), ("LAC", "Los Angeles Chargers"), ("LA", "Los Angeles Rams"), ("MIA", "Miami Dolphins"), ("MIN", "Minnesota Vikings"),
           ("NE", "New England Patriots"), ("NO", "New Orleans Saints"), ("NYG", "New York Giants"), ("NYJ", "New York Jets"), ("PHI", "Philadelphia Eagles"), ("PIT", "Pittsburgh Steelers"), ("SF", "San Francisco 49ers"),
           ("SEA", "Seattle Seahawks"), ("TB", "Tampa Bay Buccaneers"), ("TEN", "Tennessee Titans"), ("WAS", "Washington Commanders")]
NEWS_CB = (('<label id="ppnewslab" hidden><input type="checkbox" id="ppnews"> Big-name news: when a star player is ruled out, released or traded, whether or not he is on your slips</label>'
            '<label id="ppteamlab" class="ppteam" hidden>Favorite team: its rule-outs and ESPN stories, up to six a day <select id="ppteam"><option value="">No team</option>'
            + "".join(f'<option value="{c}">{n}</option>' for c, n in TEAMS32) + '</select></label>')
           if NEWS_ALERTS else "")
PROMO_CB = ('<label id="pppromolab" hidden><input type="checkbox" id="pppromo"> When BetSweep posts a slip: the Daily Sweep and the long shots, the moment they go up</label>'
            if PROMO_ALERTS else "")
PAGE_COUNTS_SINCE = "November 10, 2026"
HIT_JS = r"""
/* page counts (owner 11/10): one anonymous +1 per page view - the page's path and nothing else. No cookie, no id. Skipped when the browser sends Do Not Track or Global Privacy Control. */
(function(){ try{ var n = navigator; if(n.globalPrivacyControl || n.doNotTrack === '1' || window.doNotTrack === '1') return; if(/bot|crawl|spider|headless|lighthouse/i.test(n.userAgent || '')) return;
  var p = location.pathname.toLowerCase().replace(/index\.html$/, ''); if(!/^\/[a-z0-9\/_-]*$/.test(p) || p.length > 80) return;
  fetch('__SB__/rest/v1/rpc/hit', {method: 'POST', keepalive: true, headers: {'Content-Type': 'application/json', apikey: '__KEY__', Authorization: 'Bearer __KEY__'}, body: JSON.stringify({p: p})}).catch(function(){}); }catch(e){} })();
"""
def hit_js():
    return HIT_JS.replace("__SB__", SUPABASE_URL).replace("__KEY__", SUPABASE_ANON) if PAGE_COUNTS else ""
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

# 11/23: the device keeps its own alerts alive (see the comment inside). Included in account.js and inline on My BetSweep.
KEEP_JS = r"""
/* Alerts that stay on (owner 11/23: "I keep having to turn on alerts. Why won't it just stay on?").
   A phone can drop its push sign-up by itself (iPhone home-screen apps are known for it), and the alert service removes a device its
   push service reports gone. Nothing put either back: the reader met "Turn on alerts" again, and the choices made on the old sign-up
   (slip posts, big-name news, favorite team) went with it. This keeps one note on the device (on or off, whose it is, the sign-up's
   address, the choices) and, while that same reader is signed in and notifications are still allowed, makes a missing sign-up again,
   saves a missing row again and puts the choices back. Never after "Turn off on this device", never for another account, and never
   when the browser would have to ask permission, which takes a tap. One copy runs per page: account.js carries it to every page and
   My BetSweep carries its own, so a fresh page never leans on an older cached account.js. */
window.bsPushKeep = window.bsPushKeep || (function(){
  var KEY = 'bs_push_dev', VAPID = '__VAPID__', COLS = ['live', 'weekly', 'promo', 'news', 'team'], busy = null, busyForce = false;
  function C(){ return window.bsAccount && window.bsAccount.client; }
  function U(){ return window.bsAccount && window.bsAccount.user; }
  function note(){ try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch(e){ return {}; } }
  function put(o){ try { localStorage.setItem(KEY, JSON.stringify(o)); } catch(e){} }
  function ok(){ return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window; }
  function key(s){ s = s.replace(/-/g, '+').replace(/_/g, '/'); while(s.length % 4) s += '='; var b = atob(s), u = new Uint8Array(b.length); for(var i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }
  function opts(){ return {userVisibleOnly: true, applicationServerKey: key(VAPID)}; }
  function wait(ms){ return new Promise(function(r){ setTimeout(r, ms); }); }
  /* a service worker that never comes up must not leave the card waiting for good */
  function sw(){ return Promise.race([navigator.serviceWorker.ready, wait(8000).then(function(){ throw new Error('The app is still starting. Reload the page and try again.'); })]); }
  function row(ep){ return C().from('push_subs').select('*').eq('endpoint', ep).maybeSingle().then(function(r){ if(r && r.error) throw r.error; return (r && r.data) || null; }); }
  function choices(r){ var c = {}; COLS.forEach(function(k){ if(r && k in r) c[k] = r[k]; }); return c; }
  /* the database must hold this sign-up. A row that has to be made again gets the choices the device remembers, and the row of the address it replaces goes. */
  function ensure(sub, made){
    var u = U(), c = C(), j = sub.toJSON(), n = note(), mine = !!u && n.u === u.id, lost = false;
    var old = mine && n.ep && n.ep !== j.endpoint ? n.ep : null, had = mine && n.on === 1 && n.c ? n.c : {};
    return row(j.endpoint).then(function(r0){
      if(r0) return r0;
      lost = mine && n.on === 1;
      return c.from('push_subs').upsert({endpoint: j.endpoint, user_id: u.id, p256dh: j.keys.p256dh, auth: j.keys.auth, ua: navigator.userAgent.slice(0, 200)}, {onConflict: 'endpoint'}).then(function(r){
        if(r && r.error){ if(r.error.code === '42501' || /row-level security/i.test(r.error.message || '')){ var e = new Error('This device is signed up for alerts under another account.'); e.foreign = true; throw e; } throw r.error; }
        return Promise.all(Object.keys(had).map(function(k){ var v = {}; v[k] = had[k]; return c.from('push_subs').update(v).eq('endpoint', j.endpoint).then(function(){}, function(){}); }));
      }).then(function(){ return row(j.endpoint); });
    }).then(function(r1){
      if(old) c.from('push_subs').delete().eq('endpoint', old).then(function(){}, function(){});
      var m = {on: 1, u: u.id, ep: j.endpoint, c: choices(r1), t: Date.now(), rn: mine ? (n.rn || 0) : 0, re: mine ? (n.re || 0) : 0, h: mine && n.h ? n.h.slice(-5) : []};
      /* counted as lost only when something really was: a new address, or a row that had to be made again. A browser that says "none" and then hands back the same sign-up lost nothing. */
      if(lost || (made && old)){ m.rn += 1; m.re = Date.now(); }
      if(made) m.h.push(Date.now());
      put(m); return r1;
    });
  }
  /* the check every page runs. force (My BetSweep) skips the half-hour rest between database checks and the ten-minute rest after a failed try. */
  function keep(force){
    if(busy){ if(busyForce || !force) return busy; return busy.then(function(){ return keep(true); }); }
    busyForce = !!force;
    busy = Promise.resolve().then(function(){
      var u = U(), n = note();
      if(!u || !C() || !ok() || Notification.permission !== 'granted') return {sub: null};
      var mine = n.on === 1 && n.u === u.id;
      return sw().then(function(reg){
        return reg.pushManager.getSubscription().then(function(sub){
          if(sub) return {sub: sub, made: false};
          if(!mine) return {sub: null};
          if(!force && Date.now() - (n.f || 0) < 600000) return {sub: null};
          /* a browser that keeps answering "none" must not be signed up over and over: three tries an hour in the background, then only My BetSweep */
          if(!force && (n.h || []).filter(function(t){ return Date.now() - t < 3600000; }).length >= 3) return {sub: null};
          /* the device says alerts are on but the browser gave no sign-up: ask once more (an iPhone can answer "none" right after the app opens), then make it again */
          return wait(1200).then(function(){ return reg.pushManager.getSubscription(); }).then(function(s2){
            if(s2) return {sub: s2, made: false};
            return reg.pushManager.subscribe(opts()).then(function(s3){ return {sub: s3, made: true}; }, function(e){ var m = note(); m.f = Date.now(); put(m); return {sub: null, err: e}; });
          });
        });
      }).then(function(x){
        if(!x.sub) return x;
        if(mine){
          if(!force && n.ep === x.sub.endpoint && Date.now() - (n.t || 0) < 1800000){ if(x.made){ var m0 = note(); m0.h = (m0.h || []).slice(-5); m0.h.push(Date.now()); put(m0); } return {sub: x.sub, row: null}; }
          return ensure(x.sub, x.made).then(function(r){ return {sub: x.sub, row: r, made: x.made}; }, function(e){ return e && e.foreign ? {sub: null, foreign: true} : {sub: x.sub, row: null, err: e}; });
        }
        /* no note for this reader (a device from before 11/23, or another account's sign-up): alerts are on only if this account already has the row. Never make one unasked.
           When the database cannot be asked, a device that carries no other account's note keeps reading as on, as it did before. */
        if(n.on === 0 && n.u === u.id) return {sub: null};
        if(!force && n.su === u.id && Date.now() - (n.st || 0) < 1800000) return {sub: null, stray: true};
        return row(x.sub.endpoint).then(function(r){
          if(!r){ var ms = note(); ms.su = u.id; ms.st = Date.now(); put(ms); return {sub: null, stray: true}; }
          put({on: 1, u: u.id, ep: x.sub.endpoint, c: choices(r), t: Date.now(), rn: 0, re: 0});
          return {sub: x.sub, row: r};
        }, function(e){ return n.u && n.u !== u.id ? {sub: null, err: e} : {sub: x.sub, row: null, err: e}; });
      });
    }).then(function(res){ busy = null; return res; }, function(e){ busy = null; return {sub: null, err: e}; });
    return busy;
  }
  /* from a tap: may ask for permission. A sign-up that belongs to another account on this device is replaced by a new one for this account. */
  function turnOn(){
    return Notification.requestPermission().then(function(p){
      if(p !== 'granted') throw new Error('Notifications were not allowed.');
      return sw();
    }).then(function(reg){
      return reg.pushManager.getSubscription().then(function(s){ return s || reg.pushManager.subscribe(opts()); }).then(function(sub){
        return ensure(sub, false).then(function(r){ return {sub: sub, row: r}; }, function(e){
          if(!e || !e.foreign) throw e;
          return sub.unsubscribe().then(function(){ return reg.pushManager.subscribe(opts()); }).then(function(s2){ return ensure(s2, false).then(function(r){ return {sub: s2, row: r}; }); });
        });
      });
    });
  }
  /* the note goes to "off" first, so nothing switches alerts back on if the rest is cut short */
  function turnOff(){
    var n = note(), u = U(), c = C(), eps = [];
    put({on: 0, u: u ? u.id : (n.u || null), t: Date.now()});
    if(u && n.u === u.id && n.ep) eps.push(n.ep);
    if(!ok()) return Promise.resolve();
    return sw().then(function(reg){ return reg.pushManager.getSubscription(); }).then(function(sub){
      if(!sub) return; if(eps.indexOf(sub.endpoint) < 0) eps.push(sub.endpoint);
      return sub.unsubscribe();
    }).then(function(){ if(!c) return; return Promise.all(eps.map(function(ep){ return c.from('push_subs').delete().eq('endpoint', ep).then(function(){}, function(){}); })); });
  }
  /* save choices. A save that changed no row is not a save: the row is put back and the save tried once more before anything is reported. */
  function save(ep, vals){
    var c = C(); if(!c || !ep) return Promise.resolve({error: {message: 'Alerts are not on for this device.'}});
    function go(){ return c.from('push_subs').update(vals).eq('endpoint', ep).select('endpoint').then(function(r){ return r || {}; }); }
    return go().then(function(r){
      if(r.error || (r.data || []).length) return r;
      return sw().then(function(reg){ return reg.pushManager.getSubscription(); }).then(function(sub){
        if(!sub || sub.endpoint !== ep) return {error: {message: 'This device lost its alert sign-up. Reload the page to switch it back on.'}};
        return ensure(sub, false).then(go);
      });
    }).then(function(r){
      if(!r.error && !(r.data || []).length) r = {error: {message: 'That did not save. Turn alerts off and on again.'}};
      if(!r.error){ var m = note(); if(m.ep === ep){ m.c = m.c || {}; Object.keys(vals).forEach(function(k){ m.c[k] = vals[k]; }); put(m); } }
      return r;
    }, function(e){ return {error: {message: String(e && (e.message || e))}}; });
  }
  return {note: note, keep: keep, turnOn: turnOn, turnOff: turnOff, save: save, supported: ok};
})();
"""

ACCOUNT_JS = r"""
(function(){
  var CFG = window.__BS_ACCOUNT || {}; if(!CFG.url || !window.supabase) return;
  var sb = window.supabase.createClient(CFG.url, CFG.key, {auth: {persistSession: true, autoRefreshToken: true, detectSessionInUrl: true}});
  window.bsAccount = {client: sb, user: null};
  __KEEP__
  /* 11/23: any page keeps the device's alerts alive, and looks once more when the app comes back to the front. My BetSweep runs its own check. */
  document.addEventListener('bs-account', function(e){ if(e.detail && e.detail.user && window.bsPushKeep && location.pathname.indexOf('/me/') !== 0) setTimeout(function(){ window.bsPushKeep.keep(false); }, 1500); });
  document.addEventListener('visibilitychange', function(){ if(document.visibilityState === 'visible' && window.bsAccount && window.bsAccount.user && window.bsPushKeep && location.pathname.indexOf('/me/') !== 0) window.bsPushKeep.keep(false); });
  // ---- which browser-storage keys follow the account (everything a person builds; not caches) ----
  var SYNC = /^bs_(bankroll(?:_plan)?|clv_w\d+|log_w\d+|slips?_w\d+|slipk_w\d+|slipg_w\d+|slipmeta_w\d+|trade_\d+|manual|teams|team_cur|sleeper_user|sleeper_league|team_mode|tip|tracked.*|dfs_saved|dfs_lu_.*|dfs_site|dfs_fmt|dfs_sal_.*|handle|survivor)$/;
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
        if (lv === null && lt > rt){ pending[k] = null; return; }   // 11/15: removed here after the account copy was written - push the removal, don't restore it
        if (lv === null || rt > lt){ if (lv !== rv){ _set(k, rv); changed = true; } meta[k] = rt; } else if (lt > rt && lv !== rv){ pending[k] = lv; } });
      try{ for (var i=0;i<localStorage.length;i++){ var k = localStorage.key(i); if (SYNC.test(k) && !remote[k]) pending[k] = localStorage.getItem(k); } }catch(e){}
      saveMeta(); flush(); return changed; }); }
  // ---- UI ----
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  var slot = document.getElementById('bsacct'); if(!slot) return;
  function prof(){ if (!user) return null; if (window.bsAccount.profile && window.bsAccount.profile.user_id === user.id) return window.bsAccount.profile; try { var p = JSON.parse(localStorage.getItem('bs_prof') || 'null'); return p && p.user_id === user.id ? p : null; } catch(e){ return null; } }
  // 11/19 (owner: "My BetSweep and my profile on the social page need to combine"): one identity. The header shows the avatar picked on My BetSweep.
  window.bsAccount.setProfile = function(p){ if (!p || !p.handle) return; window.bsAccount.profile = p; try { localStorage.setItem('bs_prof', JSON.stringify({user_id: p.user_id, handle: p.handle, color: p.color, emoji: p.emoji || null})); } catch(e){} paint(); document.dispatchEvent(new CustomEvent('bs-profile', {detail: p})); };
  function profLoad(){ if (!user || !sb.rpc) return; var c = prof(), fresh = 0; try { fresh = +sessionStorage.getItem('bs_prof_at') || 0; } catch(e){} if (c) window.bsAccount.profile = c; if (c && Date.now() - fresh < 600000) return;
    sb.rpc('feed_profile_me').then(function(r){ if (r && r.data && r.data.user_id && user && r.data.user_id === user.id){ try { sessionStorage.setItem('bs_prof_at', String(Date.now())); } catch(e){} window.bsAccount.setProfile(r.data); } }, function(){}); }
  function paint(){ if (user){ var e = user.email||'', pf = prof(), ini = pf && pf.emoji ? pf.emoji : ((pf && pf.handle ? pf.handle[0] : e[0])||'?').toUpperCase(); slot.innerHTML = '<a class="me" href="/me/" title="'+esc(e)+'"><i>'+esc(ini)+'</i>My BetSweep</a><button type="button" class="out" title="Sign out">Out</button>'; slot.querySelector('.out').addEventListener('click', function(){ sb.auth.signOut().then(function(){ location.reload(); }); });
      var tabs = document.querySelector('.sitenav .tabs'); if (tabs && !tabs.querySelector('.mout')){ var mo = document.createElement('a'); mo.href = '#'; mo.className = 'mout'; mo.textContent = 'Sign out'; mo.addEventListener('click', function(e){ e.preventDefault(); sb.auth.signOut().then(function(){ location.reload(); }); }); tabs.appendChild(mo); }
      var mm0 = tabs && tabs.querySelector('.mme'); if (mm0) mm0.parentNode.removeChild(mm0); }
    else { slot.innerHTML = '<button type="button" class="in">Sign in</button>'; slot.querySelector('.in').addEventListener('click', openDlg);
      // 11/11: the Theme switch moved from the menu to My BetSweep (owner). Signed in, the header pill goes there; signed out there was no
      // way to the page from the menu, so the menu gets one line for it (the page works without an account: this browser's slips, record, theme).
      var tabs2 = document.querySelector('.sitenav .tabs'); if (tabs2 && !tabs2.querySelector('.mme')){ var mm = document.createElement('a'); mm.href = '/me/'; mm.className = 'mme' + (location.pathname.indexOf('/me/') === 0 ? ' on' : ''); mm.textContent = 'My BetSweep'; tabs2.appendChild(mm); } } }
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
  function onSession(s){ var u = s && s.user; if (u && (!user || user.id !== u.id)){ user = u; window.bsAccount.user = u; paint(); profLoad(); pull().then(function(changed){ ready = true; document.dispatchEvent(new CustomEvent('bs-account', {detail: {user: u, changed: changed}})); if (changed && !/\/me\//.test(location.pathname)){ toast('Synced from your account');
        // 11/15 (owner video: the builder "freaking out flashing"): a page that rewrote a synced key on load made every pull look like a change, so
        // the page reloaded itself over and over. One sync reload per tab per 2 minutes; past that the synced data shows on the next visit.
        var last = 0; try { last = +sessionStorage.getItem('bs_sync_rl') || 0; } catch(e){}
        if (Date.now() - last > 120000){ try { sessionStorage.setItem('bs_sync_rl', String(Date.now())); } catch(e){} setTimeout(function(){ location.reload(); }, 900); } } }); }
    else if (!u){ user = null; window.bsAccount.user = null; ready = false; paint(); document.dispatchEvent(new CustomEvent('bs-account', {detail: {user: null}})); } }
  paint();
  sb.auth.getSession().then(function(r){ onSession(r.data && r.data.session); });
  sb.auth.onAuthStateChange(function(ev, s){ if (ev === 'SIGNED_IN' || ev === 'INITIAL_SESSION' || ev === 'TOKEN_REFRESHED') onSession(s); if (ev === 'SIGNED_OUT') onSession(null); if (ev === 'SIGNED_IN' && dlg) dlg.hidden = true; });
})();
"""
ACCOUNT_JS = ACCOUNT_JS.replace("  __KEEP__\n", KEEP_JS).replace("__VAPID__", VAPID_PUBLIC)   # 11/23: alerts that stay on

ME_CSS = """
.me .ppteam{display:block} .me .ppteam select{display:block;width:100%;max-width:340px;margin-top:6px;font:inherit;font-size:16px;padding:10px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
/* 11/19 the profile card: the Social username and avatar live here now (one identity for the header, My BetSweep and Social) */
.me .mep{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px 12px;align-items:center;margin:12px 0 10px;padding:14px;border:1px solid var(--line);border-radius:14px;background:var(--card)}
.me .mep[hidden]{display:none}
.me .mep .pav{width:56px;height:56px;border-radius:50%;display:grid;place-items:center;font-family:var(--display);font-weight:700;font-size:20px;font-style:normal;color:#fff;letter-spacing:.02em} .me .mep .pav.em{font-size:29px;letter-spacing:0}
.me .pav.c0{background:#c2410c}.me .pav.c1{background:#0f766e}.me .pav.c2{background:#1d4ed8}.me .pav.c3{background:#7e22ce}.me .pav.c4{background:#be123c}.me .pav.c5{background:#4d7c0f}.me .pav.c6{background:#b45309}.me .pav.c7{background:#334155}
.me .mep h2{margin:0;font-family:var(--display);font-size:22px;line-height:1.1;color:var(--ink);overflow-wrap:anywhere} .me .mep h2 .hot{display:inline-block;margin-left:6px;font-size:18px;line-height:1} .me .mep .pn p{margin:3px 0 0;color:var(--mute);font-size:13px;line-height:1.35}
.me .mep .pb{grid-column:1 / -1;display:flex;flex-wrap:wrap;gap:8px} .me .mep .pb a,.me .mep .pb button{display:inline-flex;align-items:center;min-height:44px;padding:0 16px;border-radius:999px;border:1px solid var(--line);background:none;color:var(--ink);font:inherit;font-weight:700;font-size:14px;text-decoration:none;cursor:pointer}
/* 11/22 (owner: "press a color or emoji make the change in real time on the users profile picture"): while the editor is open the
   picture and name are one bar that stays under the menu, so a tap on a colour, an emoji or a team far down the list is seen at once */
.me .mep .phd{grid-column:1 / -1;display:grid;grid-template-columns:auto minmax(0,1fr);gap:0 12px;align-items:center;position:sticky;top:calc(53px / 1.06);z-index:4;margin:-14px -14px 0;padding:10px 14px;background:var(--card);border-bottom:1px solid var(--line);border-radius:13px 13px 0 0}
.me .mep .phd .pav{transition:background-color .15s}
@media (max-width:760px){ .me .mep .phd{top:calc((53px + env(safe-area-inset-top,0px)) / 1.1)} }
@media (prefers-reduced-motion: reduce){ .me .mep .phd .pav{transition:none} }
.me .mep .phd + .pedit{border-top:0;padding-top:4px}
.me .pedit{grid-column:1 / -1;border-top:1px solid var(--line);padding-top:12px} .me .pedit label[for]{display:block;font-size:12px;font-weight:700;color:var(--mute);margin-bottom:4px}
.me .pedit input#peh{width:100%;box-sizing:border-box;font:inherit;font-size:16px;padding:11px 12px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.me .pedit .hint{margin:5px 0 10px;font-size:12.5px;color:var(--mute)} .me .pedit fieldset{border:0;padding:0;margin:0 0 10px;min-width:0} .me .pedit legend{font-size:12px;font-weight:700;color:var(--mute);padding:0;margin-bottom:6px}
.me .pedit .sw,.me .pedit .em{display:flex;flex-wrap:wrap;gap:8px} .me .pedit .sw label,.me .pedit .em label{position:relative;cursor:pointer} .me .pedit input[type=radio]{position:absolute;opacity:0;inset:0;margin:0;cursor:pointer}
.me .pedit .sw i{display:block;width:40px;height:40px;border-radius:50%;border:3px solid transparent} .me .pedit .sw input:checked + i{border-color:var(--ink)} .me .pedit .sw input:focus-visible + i,.me .pedit .em input:focus-visible + i{outline:2px solid var(--red);outline-offset:2px}
.me .pedit .em i{display:grid;place-items:center;width:44px;height:44px;border-radius:10px;border:1px solid var(--line);font-style:normal;font-size:22px;color:var(--ink)} .me .pedit .em input:checked + i{border-color:var(--ink);background:color-mix(in srgb,var(--ink) 12%,transparent)}
.me .pedit .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)} .me .pedit .msg{min-height:18px;margin:4px 0 8px;font-size:13.5px;color:var(--mute)} .me .pedit .msg.err{color:var(--bad);font-weight:700}
.me .pedit .pbtn{display:flex;gap:8px} .me .pedit .pbtn button{font:inherit;font-weight:700;font-size:14px;min-height:44px;padding:0 18px;border-radius:999px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer} .me .pedit .pbtn .sv{background:var(--red);border-color:var(--red);color:#fff}
/* 11/16 the hub: three numbers and profit by week, before any scrolling */
.me .hub{margin:14px 0 4px}
.me .hubt{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.me .ht{display:flex;flex-direction:column;gap:2px;min-height:92px;padding:11px 12px;border:1px solid var(--line);border-radius:14px;background:var(--card);color:var(--ink);text-decoration:none;min-width:0}
.me .ht small{color:var(--mute);font-size:12px;font-weight:600} .me .ht b{font-family:var(--display);font-size:30px;line-height:1.05;font-variant-numeric:tabular-nums} .me .ht span{color:var(--mute);font-size:12px;line-height:1.3}
.me .ht b.up{color:var(--good)} .me .ht b.down{color:var(--bad)}
.me .hubw{margin-top:8px;padding:12px 12px 10px;border:1px solid var(--line);border-radius:14px;background:var(--card)}
.me .hubw h3{margin:0 0 8px;font-family:var(--display);font-size:17px;color:var(--ink)} .me .hubw h3 small{font-family:inherit;font-weight:400;font-size:12px;color:var(--mute);margin-left:6px;font-family:'IBM Plex Sans',system-ui,sans-serif}
.me .pw{list-style:none;margin:0;padding:0;display:flex;gap:0;overflow-x:auto;scrollbar-width:none} .me .pw::-webkit-scrollbar{display:none}
.me .pw.noneg button{grid-template-rows:42px 18px auto auto} .me .pw.nopos button{grid-template-rows:8px 42px auto auto}
.me .pw li{flex:1 0 40px;max-width:72px;display:block;padding:0;border:0;font-size:inherit} .me .pw li b{font-family:inherit} .me .pw button{display:grid;grid-template-rows:42px 42px auto auto;width:100%;min-height:44px;padding:0;border:0;background:none;color:var(--ink);font:inherit;cursor:pointer;text-align:center}
.me .pw .t{display:flex;align-items:flex-end;justify-content:center;border-bottom:1px solid var(--line)} .me .pw .d{display:flex;align-items:flex-start;justify-content:center}
.me .pw i{display:block;width:56%;max-width:28px;border-radius:3px 3px 0 0;background:var(--good)} .me .pw .d i{border-radius:0 0 3px 3px;background:var(--bad)} .me .pw .flat i{background:var(--mute)}
.me .pw i.o{width:9px;height:9px;margin-top:5px;border-radius:50%;background:none;border:2px solid var(--mute)}
.me .pw b{font-size:12.5px;font-variant-numeric:tabular-nums;margin-top:3px} .me .pw li.up b{color:var(--good)} .me .pw li.down b{color:var(--bad)} .me .pw li.open b{color:var(--mute);font-weight:500;font-size:11px}
.me .pw small{font-size:11px;color:var(--mute)}
.me #crec > h2{flex-wrap:wrap} .me #crec > h2 #record{order:10;flex-basis:100%;margin-top:2px;font-family:'IBM Plex Sans',system-ui,sans-serif;font-weight:500;font-size:13px !important;line-height:1.4;color:var(--mute)}
.me details.how{margin:0 0 8px} .me details.how summary{display:inline-flex;align-items:center;min-height:44px;cursor:pointer;font-size:13px;font-weight:600;color:var(--ink);text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px;list-style:none} .me details.how summary::-webkit-details-marker{display:none}
.me details.how summary::after{content:"";width:7px;height:7px;margin-left:8px;border-right:2px solid var(--mute);border-bottom:2px solid var(--mute);transform:translateY(-2px) rotate(45deg)} .me details.how[open] summary::after{transform:translateY(1px) rotate(225deg)}
@media(max-width:380px){.me .ht b{font-size:26px} .me .ht{padding:10px}}
.pushbtns{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px} .pushbtns button{font:inherit;font-size:13px;font-weight:700;padding:8px 14px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.pushbtns #pushon{background:var(--red);border-color:var(--red);color:#fff} .pushprefs{display:grid;gap:8px;margin-top:12px;font-size:13.5px} .pushprefs[hidden]{display:none} .pushprefs label[hidden]{display:none} .pushprefs label{display:flex;gap:8px;align-items:flex-start;line-height:1.4} .pushprefs input{width:18px;height:18px;margin-top:1px;accent-color:var(--red)} #pushmsg:empty{display:none} #pushmsg.ok{color:var(--good)} #pushmsg.err{color:var(--bad)}
.me{max-width:980px;margin:0 auto;padding:0 16px 40px}
.me .card{background:var(--card,#fff);border:1px solid var(--line,#d8d1c2);border-radius:14px;padding:16px 18px;margin:14px 0}
.me h1{font-family:'Barlow Condensed',sans-serif;font-size:30px;margin:18px 0 4px;letter-spacing:.02em}
.me h2{font-family:'Barlow Condensed',sans-serif;font-size:20px;margin:0 0 8px;display:flex;justify-content:space-between;align-items:baseline}
.me h2 a{font-size:13px;font-family:'IBM Plex Sans',system-ui,sans-serif;font-weight:500;display:inline-block;padding:8px 0 8px 10px}
.me p.m{color:var(--mute,#6b655c);font-size:13.5px;line-height:1.55;margin:4px 0 10px}
.me ul{list-style:none;margin:0;padding:0}
.me li{padding:9px 0;border-top:1px solid var(--line,#d8d1c2);font-size:14px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.me li:first-child{border-top:0}
.me li b{font-family:'Barlow Condensed',sans-serif;font-size:16px}
.me li small{color:var(--mute,#6b655c)}
.me li .legs{flex-basis:100%;font-size:12.5px;color:var(--mute,#6b655c);line-height:1.5}
.me .cta{display:inline-block;font-weight:700;padding:10px 16px;border-radius:10px;background:#d7332a;color:#fff;text-decoration:none}
.me .none{color:var(--mute,#6b655c);font-size:13.5px} .me .none .meact{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px} .me .none .meact a{flex:1 1 140px}
.me .res{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border-radius:4px;background:#e4ddcc;color:#5d574d}
.me .res.hit{background:#2b6b3a;color:#fff}.me .res.miss{background:#b3261e;color:#fff}
.me details.brk{margin:8px 0 10px}.me details.brk summary{cursor:pointer;font-weight:700;font-size:14px}
/* owner 11/8: bankroll tracker - private (this browser + the signed-in account only) */
.me .bkh{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}
.me .bkh div{background:var(--chalk,#f4efe3);border:1px solid var(--line,#d8d1c2);border-radius:10px;padding:8px 10px}
.me .bkh small{display:block;font-size:11.5px;color:var(--mute,#6b655c)} .me .bkh b{font-family:'Barlow Condensed',sans-serif;font-size:22px}
.me .bkh b.up{color:#2b6b3a} .me .bkh b.dn{color:#b3261e}
.me .bkstop{background:#b3261e;color:#fff;border-radius:8px;padding:8px 10px;font-size:13.5px;margin:8px 0}
.me .bkg{margin:8px 0;padding-left:18px;font-size:13.5px} .me .bkg li{margin:2px 0}
.me table.bkt{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0} .me table.bkt th,.me table.bkt td{text-align:right;padding:4px 6px;border-bottom:1px solid var(--line,#d8d1c2)} .me table.bkt th:first-child,.me table.bkt td:first-child{text-align:left}
.me .bkf{display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end;margin:8px 0} .me .bkf label{font-size:12px;color:var(--mute,#6b655c);display:flex;flex-direction:column;gap:3px}
.me .bkf input{font:inherit;font-size:15px;padding:6px 8px;border:1px solid var(--line,#cfc7b6);border-radius:8px;width:96px;background:#fff;color:#1b1a17} .me .bkf input.wide{width:150px}
.me .bkf button{font:inherit;font-size:13px;font-weight:700;padding:8px 12px;border:0;border-radius:8px;background:#d7332a;color:#fff;cursor:pointer} .me .bkf button.g{background:#e4ddcc;color:#1b1a17}
.me i.g{display:inline-block;width:16px;height:16px;border-radius:50%;text-align:center;line-height:16px;font-size:11px;font-style:normal;margin-right:3px;background:#e4ddcc;color:#5d574d}
.me i.g.hit{background:#2b6b3a;color:#fff}.me i.g.miss{background:#b3261e;color:#fff}
.me .legs em{font-style:normal;color:#9a9388}
/* owner 11/1: collapsible cards, week groups and per-slip legs */
.me .card > h2{cursor:pointer;user-select:none} .me .card > h2::after{content:'▾';font-size:15px;color:var(--mute,#6b655c);margin-left:10px;transition:transform .15s;order:9}
.me .card.shut > h2{margin-bottom:0} .me .card.shut > h2::after{transform:rotate(-90deg)} .me .card.shut > :not(h2){display:none !important}
.me li.wkh{padding:10px 0 4px} .me .wkt{font:inherit;font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:16px;letter-spacing:.04em;text-transform:uppercase;background:none;border:0;padding:0;color:var(--ink);cursor:pointer;display:flex;gap:8px;align-items:baseline}
.me .wkt small{font-family:'IBM Plex Sans',system-ui,sans-serif;font-weight:500;font-size:12.5px;text-transform:none;letter-spacing:0;color:var(--mute,#6b655c)} .me .wkt i{font-style:normal;transition:transform .15s} .me li.wkh:not(.on) .wkt i{transform:rotate(-90deg)}
.me li.sl.wkoff{display:none} .me li.sl .legs{display:none} .me li.sl.lo .legs{display:block}
.me .sla{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 6px} .me .sla a.fdl,.me .sla button{display:inline-flex;align-items:center;min-height:34px;padding:0 11px;margin-left:0;font-size:12.5px}
.me li.sl small.clv,.me li.sl small.away{display:block;margin-top:3px;font-size:12.5px;color:var(--mute)} .me li.sl small.away b{color:var(--ink)} .me li.sl .legs em.cl{font-style:normal;font-size:11.5px;color:var(--mute);margin-left:4px} .me li.sl .legs em.cl.up{color:var(--good)} .me li.sl .legs em.cl.dn{color:var(--bad)}
.me li.sl{row-gap:6px} .me li.sl > b{font-size:19px;line-height:1.15;min-width:0} .me li.sl > .res{margin-left:auto}
.me li.sl small.mt{flex-basis:100%;font-size:13px;line-height:1.5} .me li.sl .pl{font-weight:700;white-space:nowrap} .me li.sl .pl.up{color:var(--good)} .me li.sl .pl.dn{color:var(--bad)}
.me li.sl small.clv{flex-basis:100%} .me li.sl small.away{flex-basis:100%;box-sizing:border-box;margin-top:0;padding:8px 10px;border-radius:8px;background:var(--chalk);line-height:1.45} .me li.sl small.away b{font-family:inherit;font-size:13px;font-weight:600}
.me li.sl .sla{flex-basis:100%;margin:2px 0 0;align-items:center} .me li.sl .sla .lgt{margin-left:auto;min-height:34px;padding:0 12px;border-radius:17px} .me li.sl .sla .lgt i{margin-left:5px}
.me li.sl.lo .legs{display:block;margin-top:2px} .me .legs .lg{display:flex;gap:9px;align-items:center;padding:8px 0;border-top:1px solid var(--line)} .me .legs .lg:first-child{border-top:0}
.me .legs .lg .ln{flex:1;min-width:0;color:var(--ink);font-size:13.5px;line-height:1.35} .me .legs .lg em.ra{font-style:normal;color:var(--mute);font-size:12.5px;text-align:right;white-space:nowrap}
.me .legs .lg i.g{flex:none;box-sizing:border-box;width:20px;height:20px;line-height:20px;font-size:12px;margin-right:0} .me .legs .lg i.g.na{background:transparent;border:1.5px solid var(--line);color:var(--mute);line-height:17px}
.me .lgt{font:inherit;font-size:12px;font-weight:600;color:var(--mute,#6b655c);background:none;border:1px solid var(--line,#d8d1c2);border-radius:12px;padding:1px 9px;cursor:pointer} .me .lgt i{font-style:normal;display:inline-block;transition:transform .15s} .me li.sl.lo .lgt i{transform:rotate(180deg)}
.me a.fdl{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;letter-spacing:.06em;text-transform:uppercase;background:#1493ff;color:#fff;padding:3px 9px;border-radius:4px;text-decoration:none}
"""

ME_JS = r"""
(function(){
  function g(k){ try{ return localStorage.getItem(k); }catch(e){ return null; } }
  /* owner 11/24 ("it's saying a lot of the bets were -20u or -25u. That shouldn't be the case"): a slip's `stake` is DOLLARS whenever a
     person or a screenshot supplied it - the Live page's "stake $" box writes it, and an imported FanDuel slip carries its "TOTAL WAGER"
     ($20, $25) - and it was being counted as that many units. Only the builder's own default (1) is a unit. A dollar stake is turned
     into units by the bankroll tracker's unit (its starting bankroll x its percent); with no tracker set there is no unit to measure dollars
     in, so the slip counts 1 unit, as a slip saved in the builder does. */
  function unitNow(){ var p = null; try{ p = JSON.parse(g('bs_bankroll_plan') || 'null'); }catch(e){} if (!p || !(+p.pct > 0)) return 0; var br = +p.start || 0; return Math.round(br * p.pct) / 100; }   // the STARTING bankroll: the running one is itself built from these units, so reading it here would move every slip's units each time the page loads
  function wagerOf(s){ var v = +s.stake || 0; if (s.wager != null) return +s.wager || 0; return (s.src === 'fanduel-screenshot' || (v > 0 && v !== 1)) ? v : 0; }
  function stakeU(s){ var d = wagerOf(s), u = unitNow(); return d > 0 && u > 0 ? Math.max(0.01, Math.round(d / u * 100) / 100) : 1; }
  function keys(re){ var out = []; try{ for (var i=0;i<localStorage.length;i++){ var k = localStorage.key(i); if (re.test(k)) out.push(k); } }catch(e){} return out.sort(); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function odds(o){ o = +o; return isNaN(o) ? '' : (o > 0 ? '+' + o : String(o)); }
  function oddsC(o){ o = +o; if (isNaN(o)) return ''; var t = String(Math.abs(Math.round(o))).replace(/\B(?=(\d{3})+(?!\d))/g, ','); return (o > 0 ? '+' : '-') + t; }   // 11/25: +199085 reads as +199,085 in the slip list
  var NICK = {"Cardinals":"ARI","Falcons":"ATL","Ravens":"BAL","Bills":"BUF","Panthers":"CAR","Bears":"CHI","Bengals":"CIN","Browns":"CLE","Cowboys":"DAL","Broncos":"DEN","Lions":"DET","Packers":"GB","Texans":"HOU","Colts":"IND","Jaguars":"JAX","Chiefs":"KC","Raiders":"LV","Chargers":"LAC","Rams":"LA","Dolphins":"MIA","Vikings":"MIN","Patriots":"NE","Saints":"NO","Giants":"NYG","Jets":"NYJ","Eagles":"PHI","Steelers":"PIT","49ers":"SF","Seahawks":"SEA","Buccaneers":"TB","Titans":"TEN","Commanders":"WAS"};
  var BOX = {};   // week -> {box, games} once fetched
  // 11/21 (owner: "Why haven't the box scores hit yet for Thursday night's game? It's saying game hasn't been played yet on daily sweep and
  // thievery"): /data/box-w<W>.json is written from the sheet's game log, which gets a week on Tuesday. Until that file exists the page
  // reads the week's FINISHED games from ESPN itself (scoreboard, then each final's box score) and grades from that: same nine numbers per
  // player, same game scores. A game still in progress or not yet played is left out, so nothing is graded early; a player with no stat
  // line stays open until Tuesday's file (he may simply have had no catch). Names are matched without dots, apostrophes or Jr. / III.
  function nrm(n){ return String(n || '').toLowerCase().replace(/[.'’]/g, '').replace(/\s+(jr|sr|ii|iii|iv|v)$/, '').replace(/\s+/g, ' ').trim(); }
  var EAB = {WSH: 'WAS', LAR: 'LA', JAC: 'JAX'};
  function espnBox(w){ var S = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl', num = function(v){ var x = parseFloat(String(v).split('/')[0]); return isFinite(x) ? x : 0; };
    return fetch(S + '/scoreboard?seasontype=2&week=' + w, {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(sb){
      var fin = ((sb && sb.events) || []).filter(function(ev){ var t = (ev.status || {}).type || {}; return t.state === 'post' && t.completed !== false; }); if (!fin.length) return null;
      var d = {week: w, box: {}, games: {}, final: false, live: true, open: ((sb && sb.events) || []).length - fin.length}, idx = {};
      return Promise.all(fin.map(function(ev){ var c = (ev.competitions || [])[0] || {}, by = {}; (c.competitors || []).forEach(function(x){ by[x.homeAway] = x; });
        var a = by.away && by.away.team ? (EAB[by.away.team.abbreviation] || by.away.team.abbreviation) : null, h = by.home && by.home.team ? (EAB[by.home.team.abbreviation] || by.home.team.abbreviation) : null;
        return fetch(S + '/summary?event=' + ev.id, {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(sm){ if (!sm) return; var n0 = Object.keys(idx).length;
          (((sm.boxscore || {}).players) || []).forEach(function(tm){ (tm.statistics || []).forEach(function(cat){ var keys = cat.keys || [];
            (cat.athletes || []).forEach(function(at){ var nm = at.athlete && at.athlete.displayName; if (!nm) return; var st = {}; keys.forEach(function(k, i){ st[k] = (at.stats || [])[i]; });
              var row = idx[nrm(nm)] = idx[nrm(nm)] || [0, 0, 0, 0, 0, 0, 0, 0, 0];
              if (cat.name === 'passing'){ row[0] = num(st.passingYards); row[1] = num(st.passingTouchdowns); row[2] = num(st.interceptions); }
              if (cat.name === 'rushing'){ row[3] = num(st.rushingYards); row[4] = num(st.rushingTouchdowns); }
              if (cat.name === 'receiving'){ row[5] = num(st.receptions); row[6] = num(st.receivingYards); row[7] = num(st.receivingTouchdowns); row[8] = num(st.longReception); } }); }); });
          if (a && h && Object.keys(idx).length - n0 >= 10) d.games[a + '-' + h] = [num(by.away.score), num(by.home.score)]; }).catch(function(){}); })).then(function(){
        if (!Object.keys(d.games).length) return null;
        d.box = (typeof Proxy === 'function') ? new Proxy(idx, {get: function(t, k){ return typeof k === 'string' ? t[nrm(k)] : undefined; }}) : idx; return d; }); }).catch(function(){ return null; }); }
  var BOXP = {};   // one read per week however many slips ask at once
  function getBox(w){ if (BOX[w] !== undefined) return Promise.resolve(BOX[w]); if (BOXP[w]) return BOXP[w]; return BOXP[w] = fetch('/data/box-w'+w+'.json').then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }).then(function(d){ return d || espnBox(w); }).then(function(d){ BOX[w] = d; return d; }); }
  // owner 11/5 ("your CLV"): closing FanDuel prices per leg key (data/close-w<W>.json from build_mydata.py) + the build prices as the fallback for slips saved before prices were stored
  var CLOSE = {};
  function getClose(w){ if (CLOSE[w] !== undefined) return Promise.resolve(CLOSE[w]); return fetch('/data/close-w'+w+'.json').then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }).then(function(d){ CLOSE[w] = d; return d; }); }
  function imp(o){ o = +o; if (!o) return null; return o > 0 ? 100/(o+100) : -o/(-o+100); }
  function clvOf(s, k, c){ var mine = (s.px && s.px[k] && s.px[k].o != null) ? +s.px[k].o : (c && c.build && c.build[k] ? +c.build[k].o : null); var cl = c && c.close && c.close[k] ? +c.close[k].o : null;
    if (mine == null || cl == null) return null; return {mine: mine, close: cl, pts: Math.round((imp(cl) - imp(mine)) * 1000) / 10}; }
  // grade one slip key against the week's box scores: returns {r: 'HIT'|'MISS'|'PUSH'|'?', a: actual text}
  // 11/25 (owner screenshot: Thursday's players under a Wednesday slip all read "no box score (did not play?)"): while the week is read
  // live from ESPN, a man with no stat line whose game has not been played is "not played yet"; only Tuesday's file can say he sat.
  function noBox(d, gid){ if (!d.live) return 'no box score (did not play?)'; var played = false, want = gid ? String(gid).split('-').sort().join() : null;
    if (want) Object.keys(d.games || {}).forEach(function(g){ if (g.split('-').sort().join() === want) played = true; });
    return played ? 'no stat line yet' : (want || d.open) ? 'not played yet' : 'no stat line yet'; }
  function onlyGame(){ return null; }   // a total saved before 11/14 carries no game: left ungraded rather than guessed
  function gradeKey(k, d, gid){ if (!d) return {r: '?', a: 'not final'}; var p = String(k).split('|'); if (p.length < 3) return {r: '?', a: ''};
    var who = p[0], m = p[1], ln = parseFloat(p[2]); var S = {"Passing Yards":0, "Passing TDs":1, "Rushing Yards":3, "Receptions":5, "Receiving Yards":6, "Longest Reception":8};
    function team(t){ var n = Object.keys(NICK).filter(function(x){ return t.indexOf(x) >= 0; })[0]; return n ? NICK[n] : null; }
    function gameOf(ab){ var out = null; Object.keys(d.games||{}).forEach(function(g){ var q = g.split('-'); if (q[0]===ab || q[1]===ab) out = {a:q[0], h:q[1], as:d.games[g][0], hs:d.games[g][1]}; }); return out; }
    if (m === 'Moneyline'){ var t = team(who), gm = t && gameOf(t); if (!gm) return {r:'?', a:'game not final'}; var marg = (t===gm.h ? gm.hs-gm.as : gm.as-gm.hs); return {r: marg>0?'HIT':marg<0?'MISS':'PUSH', a: gm.a+' '+gm.as+' @ '+gm.h+' '+gm.hs}; }
    if (m === 'Spread'){ var t2 = team(who), gm2 = t2 && gameOf(t2), mm = who.match(/([+-]?\d+(?:\.\d+)?)\s*$/); if (!gm2 || !mm) return {r:'?', a:'game not final'}; var v = (t2===gm2.h ? gm2.hs-gm2.as : gm2.as-gm2.hs) + parseFloat(mm[1]); return {r: v>0?'HIT':v<0?'MISS':'PUSH', a: gm2.a+' '+gm2.as+' @ '+gm2.h+' '+gm2.hs}; }
    if (m === 'Total'){ var tt = who.match(/^(Over|Under)\s+(\d+(?:\.\d+)?)/i), gg = null;   // 11/14: the slip's game map (s.g) says which game; a key only one game uses carries none, so fall back to that one game
      Object.keys(d.games||{}).forEach(function(g){ var q = g.split('-'); if (gid && (g === gid || (q[1] + '-' + q[0]) === gid || gid.split('-').sort().join() === q.slice().sort().join())) gg = d.games[g]; });
      if (!tt || !gg) return {r:'?', a: gid ? 'game not final' : 'game not on record'}; var sum = (+gg[0]) + (+gg[1]), line = parseFloat(tt[2]), over = /^o/i.test(tt[1]);
      return {r: sum === line ? 'PUSH' : ((sum > line) === over ? 'HIT' : 'MISS'), a: sum + ' total'}; }
    if (m === 'First TD') return {r:'?', a:'first TD graded on the receipt'};
    if (m === 'Either TD'){ var names = who.split(/\s+or\s+/); var hit = names.some(function(n){ var b = d.box[n.trim()]; return b && (b[4]+b[7]) >= 1; }); var any = names.some(function(n){ return !!d.box[n.trim()]; }); return any ? {r: hit?'HIT':'MISS', a: hit?'scored':'no TD'} : {r:'?', a: d.live ? noBox(d, gid) : 'no box score'}; }
    var b = d.box[who]; if (!b) return {r:'?', a: noBox(d, gid)};
    if (/^Under /.test(m)){ var mu = S[m.slice(6)]; if (mu == null) return {r:'?', a:''}; var vu = b[mu]; return {r: vu < ln - 0.5 ? 'HIT' : 'MISS', a: String(vu)}; }   // FanDuel main-line unders (key line = rounded X.5)
    if (m === 'Anytime TD'){ var td = b[4]+b[7]; return {r: td>=1?'HIT':'MISS', a: td+' TD'}; }
    if (m === '2+ TD' || m === '3+ TD'){ var td2 = b[4]+b[7], need2 = m === '2+ TD' ? 2 : 3; return {r: td2>=need2?'HIT':'MISS', a: td2+' TD'}; }
    if (m === 'Rush + Rec Yards'){ var y = b[3]+b[6]; return {r: y>=ln?'HIT':'MISS', a: y+' yds', v: y, need: ln}; }
    if (S[m] != null){ var v2 = b[S[m]]; return {r: v2>=ln?'HIT':'MISS', a: String(v2), v: v2, need: ln}; }
    return {r:'?', a:''}; }
  function dec(o){ o = +o; if (!o) return null; return o > 0 ? o/100 + 1 : 100/(-o) + 1; }

  function brkRender(B){ var el = document.getElementById('recbrk'); if (!el) return;
    function rows(o, slips){ return Object.keys(o).sort(function(a, b){ return o[b][1] - o[a][1]; }).map(function(k){ var c = o[k], pct = Math.round(100 * c[0] / c[1]);
      return '<tr><td>' + esc(k) + '</td><td>' + c[0] + '-' + (c[1] - c[0]) + '</td><td>' + pct + '%</td>' + (slips ? '<td style="color:' + (c[2] >= 0 ? '#2b6b3a' : '#b3261e') + '">' + (c[2] >= 0 ? '+' : '') + c[2].toFixed(1) + 'u</td>' : '') + '</tr>'; }).join(''); }
    if (!Object.keys(B.m).length){ el.innerHTML = ''; return; }
    el.innerHTML = '<details class="brk"><summary>Your record, broken down</summary>'
      + '<table class="bkt"><thead><tr><th>Legs by market</th><th>W-L</th><th>Hit</th></tr></thead><tbody>' + rows(B.m) + '</tbody></table>'
      + (Object.keys(B.n).length ? '<table class="bkt"><thead><tr><th>Slips by size</th><th>W-L</th><th>Hit</th><th>Units</th></tr></thead><tbody>' + rows(B.n, 1) + '</tbody></table>'
      + '<table class="bkt"><thead><tr><th>Slips by price</th><th>W-L</th><th>Hit</th><th>Units</th></tr></thead><tbody>' + rows(B.o, 1) + '</tbody></table>' : '')
      + '<p class="m">Graded from the box scores. Units are at each slip\'s own stake.</p></details>'; }
  // 11/16 (alpha plan step 7): the top of the page answers three things before any scrolling - what is open, the record in units, and
  // how each week went. Same numbers the record list below works out; nothing here is graded twice or guessed. o = null: nothing saved yet.
  function hubRender(o){ var $ = function(id){ return document.getElementById(id); }; if (!$('hub')) return;
    function un(v, d){ return (v >= 0 ? '+' : '\u2212') + Math.abs(v).toFixed(d == null ? 2 : d).replace(/\.00$/, '') + 'u'; }
    function tone(el, v){ el.classList.toggle('up', v > 0); el.classList.toggle('down', v < 0); }
    if (!o){ $('hopen').textContent = '0'; $('hopens').textContent = 'Save a slip and it is tracked here'; $('hrec').textContent = '\u2013'; $('hunits').textContent = 'no graded slips yet'; $('hweek').textContent = '\u2013'; $('hweeks').textContent = ''; $('hubw').hidden = true; tone($('hrec'), 0); tone($('hweek'), 0); return; }
    var st = o.open.reduce(function(a, x){ return a + (+x.st || 0); }, 0), allWin = o.open.length && o.open.every(function(x){ return x.win != null; }), win = o.open.reduce(function(a, x){ return a + (x.win || 0); }, 0);
    $('hopen').textContent = String(o.open.length);
    $('hopens').textContent = o.open.length ? un(st, 2).replace(/^[+\u2212]/, '') + ' at stake' + (allWin ? ' \u00b7 ' + un(win, 1).replace(/^\+/, '') + ' if all cash' : '') : 'none open this week';
    var graded = o.W + o.L; $('hrec').textContent = graded ? o.W + '\u2013' + o.L : '\u2013'; $('hunits').textContent = graded ? un(o.U) + ' all weeks' : 'no graded slips yet'; tone($('hrec'), graded ? o.U : 0);
    var by = {}; o.bk.forEach(function(b){ var e = by[b.w] = by[b.w] || {u: 0, w: 0, l: 0, p: 0}; if (b.res === 'HIT'){ e.w++; if (b.u != null) e.u += b.u; } else if (b.res === 'MISS'){ e.l++; e.u += b.u; } else e.p++; });
    var tw = by[o.topW] || {u: 0, w: 0, l: 0, p: 0}, tg = tw.w + tw.l; $('hweekl').textContent = 'Week ' + o.topW;
    $('hweek').textContent = tg ? un(tw.u) : '\u2013'; tone($('hweek'), tg ? tw.u : 0); $('hweeks').textContent = (tg ? tw.w + '\u2013' + tw.l + ' graded' : 'nothing graded yet') + (tw.p ? ' \u00b7 ' + tw.p + ' open' : '');
    var wks = Object.keys(by).map(Number).sort(function(a, b){ return a - b; }), anyG = wks.some(function(w){ return by[w].w + by[w].l; }), box = $('hubw');
    if (!anyG){ box.hidden = true; return; }
    var mx = Math.max.apply(null, wks.map(function(w){ return Math.abs(by[w].u); }).concat([0.01]));
    var neg = wks.some(function(w){ return by[w].u < 0 && by[w].w + by[w].l; }), pos = wks.some(function(w){ return by[w].u > 0; });
    box.hidden = false; box.innerHTML = '<h3>Profit by week <small>units, at each slip\u2019s own stake</small></h3><ol class="pw' + (neg ? '' : ' noneg') + (pos ? '' : ' nopos') + '">' + wks.map(function(w){ var e = by[w], g = e.w + e.l, h = g ? Math.max(3, Math.round(40 * Math.abs(e.u) / mx)) : 0, cls = !g ? 'open' : e.u > 0 ? 'up' : e.u < 0 ? 'down' : 'flat';
      var say = 'Week ' + w + ': ' + (g ? un(e.u).replace(/u$/, '') + ' units, ' + e.w + '\u2013' + e.l + ' on ' + g + ' graded slip' + (g === 1 ? '' : 's') : 'not graded yet') + (e.p ? ', ' + e.p + ' open' : '');
      return '<li class="' + cls + '"><button type="button" data-w="' + w + '" aria-label="' + esc(say) + '"><span class="t">' + (cls === 'up' || cls === 'flat' ? '<i style="height:' + (cls === 'flat' ? 3 : h) + 'px"></i>' : '') + '</span><span class="d">' + (cls === 'down' ? '<i style="height:' + h + 'px"></i>' : cls === 'open' ? '<i class="o"></i>' : '') + '</span><b>' + (g ? un(e.u, 1).replace(/u$/, '') : e.p + ' open') + '</b><small>W' + w + '</small></button></li>'; }).join('') + '</ol>'; }
  function hubGo(id, w){ var c = document.getElementById(id); if (!c) return; c.classList.remove('shut');
    if (w != null){ var t = c.querySelector('.wkh[data-w="' + w + '"]'); if (t){ if (!t.classList.contains('on')){ var bt = t.querySelector('.wkt'); if (bt) bt.click(); } c = t; } }
    c.scrollIntoView({block: 'start', behavior: 'smooth'}); }
  document.addEventListener('click', function(e){ var t = e.target.closest && e.target.closest('#hub .ht, #hub .pw button'); if (!t) return; e.preventDefault(); hubGo('crec', t.dataset.w != null ? t.dataset.w : null); });
  function render(){
    var u = window.bsAccount && window.bsAccount.user; var who = document.getElementById('who');
    who.innerHTML = u ? 'Signed in as <b>'+esc(u.email||'')+'</b>. Everything below follows you to any device you sign in on.' : 'Not signed in: this page shows what is saved in this browser only. <button type="button" class="cta" id="mein" style="margin-left:8px;padding:6px 12px;font-size:13px">Sign in to sync it</button>';
    var b = document.getElementById('mein'); if (b) b.addEventListener('click', function(){ var s = document.querySelector('#bsacct .in'); if (s) s.click(); });
    // saved betslips (live page), by week
    var sl = [], ks = keys(/^bs_slips_w\d+$/); ks.forEach(function(k){ var w = k.replace('bs_slips_w',''); try{ (JSON.parse(g(k))||[]).forEach(function(s){ sl.push({w: +w, s: s}); }); }catch(e){} });
    sl.sort(function(a,b){ return b.w - a.w; });
    var el = document.getElementById('slips');
    if (!sl.length){ bankRender([]); hubRender(null); el.innerHTML = '<li class="none">No saved slips yet. Import the bets you placed on FanDuel, or build one here, and each is graded from the box scores after the games.<span class="meact"><a class="bsbtn" href="#import" data-impgo>Import FanDuel screenshots</a><a class="bsbtn sec" href="/build/">Build a slip</a><a class="bsbtn sec" href="/social/">Tail a posted slip</a></span></li>'; document.getElementById('record').textContent = ''; }
    else { el.innerHTML = '<li class="none">Grading…</li>';
      Promise.all(sl.map(function(x){ return getBox(x.w); }).concat(sl.map(function(x){ return getClose(x.w); }))).then(function(all){ var ds = all.slice(0, sl.length), cs = all.slice(sl.length); var W = 0, L = 0, U = 0, P = 0, OPEN = [], BK = [], BRK = {m:{}, n:{}, o:{}}, html = '', lastW = null, topW = sl.length ? sl[0].w : 0, CB = 0, CN = 0, CP = 0;
        sl.forEach(function(x, i){ var s = x.s, d = ds[i], c = cs[i], seen = {}, gs = (s.keys||[]).map(function(k){ var n = seen[k] = (seen[k] || 0) + 1, gid = s.g && s.g[k] ? s.g[k][n - 1] : (/\|Total\|/.test(k) ? onlyGame(k) : null); return {k:k, g: gradeKey(k, d, gid), clv: clvOf(s, k, c)}; });
          var withClv = gs.filter(function(g){ return g.clv; }), beat = withClv.filter(function(g){ return g.clv.pts > 0; }).length, avg = withClv.length ? withClv.reduce(function(a,g){ return a + g.clv.pts; }, 0) / withClv.length : null;
          CB += beat; CN += withClv.length; CP += withClv.reduce(function(a,g){ return a + g.clv.pts; }, 0);
          var live = gs.filter(function(g){ return g.g.r !== 'PUSH'; }); var res = live.some(function(g){ return g.g.r==='MISS'; }) ? 'MISS' : live.every(function(g){ return g.g.r==='HIT'; }) ? 'HIT' : 'PENDING';
          var stake = stakeU(s), dd = dec(s.odds), u = res==='HIT' ? (dd ? (dd-1)*stake : null) : res==='MISS' ? -stake : null;
          if (res==='HIT'){ W++; if (u!=null) U += u; } else if (res==='MISS'){ L++; U += u; } else P++; BK.push({w: x.w, u: u, res: res, st: stake, name: s.name || 'Slip'}); if (res === 'PENDING' && x.w === topW) OPEN.push({name: s.name || 'Slip', st: stake, win: dd ? (dd - 1) * stake : null, keys: gs.filter(function(g){ return g.g.r !== 'HIT' && g.g.r !== 'MISS' && g.g.r !== 'PUSH'; }).map(function(g){ return g.k; })});
          // owner 11/1 item 6: record breakdown - legs by market, slips by leg count and by price band
          gs.forEach(function(g){ if (g.g.r !== 'HIT' && g.g.r !== 'MISS') return; var mk = String(g.k).split('|')[1] || '?'; mk = mk.replace(/^Under /, 'Under: '); var c = BRK.m[mk] = BRK.m[mk] || [0, 0]; c[1]++; if (g.g.r === 'HIT') c[0]++; });
          if (res === 'HIT' || res === 'MISS'){ var nl = (s.keys||[]).length, nb = nl <= 1 ? '1 leg' : nl <= 3 ? '2-3 legs' : nl <= 5 ? '4-5 legs' : '6+ legs';
            var od = +s.odds, ob = !od ? 'unknown price' : od < 150 ? 'under +150' : od < 500 ? '+150 to +499' : od < 2000 ? '+500 to +1999' : '+2000 and up';
            [[BRK.n, nb], [BRK.o, ob]].forEach(function(p){ var c2 = p[0][p[1]] = p[0][p[1]] || [0, 0, 0]; c2[1]++; if (res === 'HIT') c2[0]++; if (u != null) c2[2] += u; }); }
          var misses = gs.filter(function(g){ return g.g.r === 'MISS'; }), oneAway = (res === 'MISS' && misses.length === 1) ? misses[0] : null;
          var extra = '';
          if (withClv.length) extra += '<small class="clv">Closing line: beat it on ' + beat + ' of ' + withClv.length + ' leg' + (withClv.length===1?'':'s') + (avg != null ? ' (' + (avg>=0?'+':'') + avg.toFixed(1) + ' pts avg)' : '') + '</small>';
          if (oneAway){ var q0 = String(oneAway.k).split('|'), gg = oneAway.g, short = (gg.v != null && gg.need != null) ? (Math.round((gg.need - gg.v) * 10) / 10) + ' short (' + gg.v + ' vs ' + gg.need + '+)' : (gg.a || 'missed');
            extra += '<small class="away">One leg away: <b>' + esc(q0[0]) + ' ' + esc(q0[1].toLowerCase()) + '</b> ' + esc(short) + '</small>'; }
          var bet = (res==='PENDING' && s.fd && !d) ? '<a class="fdl" href="'+esc(s.fd)+'" target="_blank" rel="noopener">Bet on FanDuel</a>' : '';
          if (res==='PENDING') bet += '<button type="button" class="fdl ldb" data-keys="'+esc(JSON.stringify(s.keys||[]))+'" data-g="'+esc(JSON.stringify(s.g||{}))+'">Load into betslip</button>';   // owner 11/1
          // owner 11/22 ("Make it easier for you to send saved betslips to social"): this week's open slips of your own post from here (social.py SAVED_JS);
          // a slip saved from someone's post, or a tailed BetSweep promo, is not yours to post. Once posted the row links to it instead.
          if (res==='PENDING' && x.w === topW && s.id != null && !s.promo && !s.post) bet += s.posted ? '<a class="fdl pon" href="/social/'+(s.posted === true ? '' : '#p'+esc(s.posted))+'">On Social \u2713</a>' : '<button type="button" class="fdl psb" data-psb data-w="'+x.w+'" data-id="'+esc(s.id)+'">Post to Social</button>';   // NOT class ldb: that is Load into betslip's own handler
          if (x.w !== lastW){ lastW = x.w; var wn = sl.filter(function(y){ return y.w === x.w; }).length; html += '<li class="wkh'+(x.w === topW ? ' on' : '')+'" data-w="'+x.w+'"><button type="button" class="wkt">Week '+x.w+' <small>'+wn+' slip'+(wn===1?'':'s')+'</small><i>▾</i></button></li>'; }
          html += '<li class="sl w'+x.w+(x.w === topW ? '' : ' wkoff')+'"><b>'+esc(s.name||'Slip')+'</b><span class="res '+res.toLowerCase()+'">'+(res==='HIT'?'Cashed':res==='MISS'?'Missed':d?'Pending':'Not played yet')+'</span>'+'<small class="mt">Week '+x.w+' · '+gs.length+(gs.length===1?' leg':' legs')+(s.odds? ' · '+oddsC(s.odds) : '')+' · '+stake+'u'+(wagerOf(s) ? ' ($'+wagerOf(s)+' bet)' : '')+(u!=null? ' · <span class="pl '+(u>=0?'up':'dn')+'">'+(u>=0?'+':'')+u.toFixed(2)+'u</span>' : '')+'</small>'+extra+'<span class="sla">'+bet+'<button type="button" class="lgt" aria-expanded="false">Legs <i>▾</i></button></span><span class="legs">'+gs.map(function(g){ var q = String(g.k).split('|'); var lab = q[1]==='Anytime TD'||q[1]==='First TD'||q[1]==='Either TD' ? q[0]+' '+q[1].toLowerCase() : q[1]==='Moneyline'||q[1]==='Spread'||q[1]==='Total' ? q[0] : q[0]+' '+q[2]+'+ '+q[1].toLowerCase(); var cv = g.clv ? ' <em class="cl '+(g.clv.pts>0?'up':g.clv.pts<0?'dn':'')+'" title="your price '+odds(g.clv.mine)+' · closed '+odds(g.clv.close)+'">'+(g.clv.pts>0?'▲':g.clv.pts<0?'▼':'=')+' '+(g.clv.pts>0?'+':'')+g.clv.pts+' vs close</em>' : ''; return '<span class="lg"><i class="g '+g.g.r.replace('?','na').toLowerCase()+'">'+(g.g.r==='HIT'?'✓':g.g.r==='MISS'?'✗':g.g.r==='PUSH'?'=':'·')+'</i><span class="ln">'+esc(lab)+cv+'</span>'+(g.g.a? '<em class="ra">'+esc(g.g.a)+'</em>' : '')+'</span>'; }).join('')+'</span></li>'; });   // 11/25 (owner screenshot, "Make this look better"): one leg per row, result on the right
        // owner 11/15 ("check the whole day, not each slip"): the same player on more than one open slip means one quiet game costs several bets
        (function(){ var by = {}; OPEN.forEach(function(o, i){ var seen = {}; o.keys.forEach(function(k){ var pl = String(k).split('|')[0]; if (!pl || /\|(Total|Spread|Moneyline)\|/.test(k) || seen[pl]) return; seen[pl] = 1; (by[pl] = by[pl] || []).push(o); }); });
          var rep = Object.keys(by).filter(function(p){ return by[p].length > 1; }).sort(function(a, b){ return by[b].length - by[a].length; });
          if (!rep.length) return;
          html = '<li class="none" id="exposure" style="border-left:3px solid var(--red);padding-left:10px;margin-bottom:10px"><b>Same player on more than one open slip.</b> One quiet game would sink every slip he is on:<br>' +
            rep.slice(0, 8).map(function(p){ var st = by[p].reduce(function(a, o){ return a + (+o.st || 0); }, 0), any = by[p].some(function(o){ return +o.st > 1; });
              return esc(p) + ': ' + by[p].length + ' slips (' + by[p].map(function(o){ return esc(o.name); }).join(', ') + ')' + (any ? ', ' + st.toFixed(0) + ' staked' : ''); }).join('<br>') + '</li>' + html; })();
        el.innerHTML = html; bankRender(BK); brkRender(BRK); hubRender({W: W, L: L, U: U, open: OPEN, bk: BK, topW: topW}); document.getElementById('record').textContent = ((W+L) ? W+'–'+L+(P? ' ('+P+' pending)':'')+' · '+(U>=0?'+':'')+U.toFixed(2)+'u' : (P? P+' pending' : '')) + (CN ? ' · beat the close on '+CB+' of '+CN+' legs ('+(CP/CN>=0?'+':'')+(CP/CN).toFixed(1)+' pts avg)' : ''); }); }
    // exposure (owner 10/26, after 'I have so much riding on Ken Walker'): the latest week's saved slips + the working builder slip,
    // grouped by player (an either-TD leg counts for both names; game lines by their text). Stake and to-win at the slip's own stake/odds.
    (function(){ var ex = document.getElementById('expo'); if (!ex) return;
      var wk = sl.length ? Math.max.apply(null, sl.map(function(x){ return x.w; })) : 0, cur = sl.filter(function(x){ return x.w === wk; }).map(function(x){ return x.s; });
      var bk2 = keys(/^bs_slipk_w\d+$/).pop(); if (bk2 && +bk2.replace('bs_slipk_w','') >= wk){ try{ var bl2 = JSON.parse(g(bk2))||[]; if (bl2.length) cur.push({name: 'Builder slip (not saved)', keys: bl2}); }catch(e){} }
      if (!cur.length){ ex.innerHTML = '<li class="none">No open slips saved for this week.</li>'; return; }
      var P = {};
      cur.forEach(function(s){ var stake = stakeU(s), dd = dec(s.odds), win = (stake && dd) ? stake * (dd - 1) : 0, seen = {};
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
  // ---- owner 11/8 bankroll tracker: start bankroll, unit = pct% of the bankroll at the start of each week (resets Tuesday), saved slips
  // grade in at their stake in units x that week's unit, plus manual entries for bets placed elsewhere. Stop line: down 10u in a week.
  var BANKROWS = [];
  function curWeek(){ var t0 = Date.UTC(2026, 8, 8, 12); var w = Math.floor((Date.now() - t0) / 864e5 / 7) + 1; return Math.max(1, Math.min(18, w)); }
  function bkPlan(){ try{ return JSON.parse(g('bs_bankroll_plan') || 'null'); }catch(e){ return null; } }
  function bkSave(p){ try{ localStorage.setItem('bs_bankroll_plan', JSON.stringify(p)); }catch(e){} }
  function money(v){ var n = Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : (Math.round(v * 100) / 100).toFixed(2).replace(/\.00$/, ''); return (v < 0 ? '-$' : '$') + String(n).replace('-', ''); }
  function bankRender(rows){
    if (rows) BANKROWS = rows; var el = document.getElementById('bank'), hd = document.getElementById('bkhead'); if (!el) return;
    var p = bkPlan(), cw = curWeek();
    if (!p){ var dw = cw + ([0, 1].indexOf(new Date().getDay()) >= 0 ? 1 : 0);
      hd.textContent = ''; el.innerHTML = '<div class="bkf"><label>Starting bankroll $<input id="bks" type="number" inputmode="decimal" min="1" step="50" value="1000"></label><label>Unit (% of bankroll)<input id="bkp" type="number" inputmode="decimal" min="0.5" max="5" step="0.5" value="2"></label><label>Count from week<input id="bkw" type="number" min="1" max="18" value="' + Math.min(18, dw) + '"></label><button type="button" id="bkgo">Start tracking</button></div><p class="m">2% a unit is a steady pace; 1% is safer. Bigger units do not reach big goals faster - they reach zero faster.</p>'; return; }
    var weeks = {}, last = cw; BANKROWS.forEach(function(r){ if (r.w >= p.since){ (weeks[r.w] = weeks[r.w] || []).push(r); if (r.w > last) last = r.w; } }); (p.adj || []).forEach(function(a){ if (a.w > last) last = a.w; });
    var br = +p.start, tab = '', thisW = null;
    for (var w = p.since; w <= last; w++){
      var unit = Math.round(br * p.pct) / 100, rs = weeks[w] || [], gu = 0, pend = 0, n = 0;
      rs.forEach(function(r){ if (r.res === 'PENDING'){ pend += r.st; } else if (r.u != null){ gu += r.u; n++; } });
      var adj = (p.adj || []).filter(function(a){ return a.w === w; }), ad = adj.reduce(function(s, a){ return s + (+a.amt || 0); }, 0);
      var pl = gu * unit + ad, start = br; br = Math.max(0, br + pl);
      if (w === cw || (w === last && thisW == null && w >= cw)) thisW = {w: w, unit: unit, gu: gu, pend: pend, start: start, pl: pl, adj: adj};
      tab += '<tr><td>Week ' + w + '</td><td>' + money(start) + '</td><td>' + money(unit) + '</td><td>' + n + (pend ? ' +' + pend + 'u open' : '') + '</td><td style="color:' + (pl > 0 ? '#2b6b3a' : pl < 0 ? '#b3261e' : 'inherit') + '">' + (pl >= 0 ? '+' : '') + money(pl) + '</td><td>' + money(br) + '</td></tr>';
    }
    if (!thisW) thisW = {w: Math.max(cw, p.since), unit: Math.round(br * p.pct) / 100, gu: 0, pend: 0, start: br, pl: 0, adj: []};
    var tot = br - p.start, u = thisW.unit;
    hd.textContent = money(br) + ' · ' + (tot >= 0 ? '+' : '') + money(tot);
    try{ localStorage.setItem('bs_bankroll', String(Math.round(br * 100) / 100)); }catch(e){}
    var html = '<div class="bkh"><div><small>Bankroll now</small><b class="' + (tot > 0 ? 'up' : tot < 0 ? 'dn' : '') + '">' + money(br) + '</b></div><div><small>Week ' + thisW.w + ' unit</small><b>' + money(u) + '</b></div><div><small>Week ' + thisW.w + ' so far</small><b class="' + (thisW.pl > 0 ? 'up' : thisW.pl < 0 ? 'dn' : '') + '">' + (thisW.pl >= 0 ? '+' : '') + money(thisW.pl) + '</b></div></div>'; var wu = u ? thisW.pl / u : 0;
    if (wu <= -10) html += '<div class="bkstop">Down ' + Math.abs(Math.round(wu * 10) / 10) + 'u this week - that is the stop line. No more bets until Tuesday, and never size up to win it back.</div>';
    html += '<ul class="bkg"><li><b>Short favorite slips (about +300):</b> 1u = ' + money(u) + '</li><li><b>With a TD booster (+500 to +1000):</b> 0.5u = ' + money(u / 2) + '</li><li><b>Long shots (+2000 and up):</b> 0.25u = ' + money(u / 4) + ', one or two a week</li><li><b>Stop for the week</b> at -10u (' + money(-10 * u) + ')</li></ul>';
    html += '<table class="bkt"><thead><tr><th>Week</th><th>Start</th><th>Unit</th><th>Graded</th><th>P/L</th><th>End</th></tr></thead><tbody>' + tab + '</tbody></table>';
    html += '<div class="bkf"><label>Week<input id="bkaw" type="number" min="1" max="18" value="' + thisW.w + '"></label><label>Won / lost $<input id="bkaa" type="number" inputmode="decimal" step="1" placeholder="-20 or 65"></label><label>Note<input id="bkan" class="wide" type="text" maxlength="60" placeholder="bet placed elsewhere"></label><button type="button" id="bkadd">Add</button></div>';
    var ad2 = (p.adj || []).map(function(a, i){ return {a: a, i: i}; }).filter(function(x){ return x.a.w >= p.since; });
    if (ad2.length) html += '<ul class="bkg">' + ad2.map(function(x){ return '<li>Week ' + x.a.w + ': ' + (x.a.amt >= 0 ? '+' : '') + money(x.a.amt) + (x.a.note ? ' - ' + esc(x.a.note) : '') + ' <button type="button" class="lgt bkdel" data-i="' + x.i + '">remove</button></li>'; }).join('') + '</ul>';
    html += '<p class="m">Started ' + money(p.start) + ' in Week ' + p.since + ' at ' + p.pct + '% a unit. <button type="button" class="lgt" id="bkreset">Change start</button></p>';
    el.innerHTML = html; }
  document.addEventListener('click', function(ev){ var t = ev.target; if (!t || !t.id && !t.classList) return;
    if (t.id === 'bkgo'){ var s = +document.getElementById('bks').value, pc = +document.getElementById('bkp').value, w = +document.getElementById('bkw').value; if (!(s > 0) || !(pc > 0) || !(w >= 1)) return; var old = bkPlan(); if (!old){ try{ old = JSON.parse(g('bs_bankroll_plan_prev') || 'null'); }catch(e){} } bkSave({start: s, pct: Math.min(5, pc), since: Math.min(18, Math.round(w)), adj: old && old.adj || []}); bankRender(); }
    else if (t.id === 'bkadd'){ var p = bkPlan(); if (!p) return; var a = +document.getElementById('bkaa').value, w2 = +document.getElementById('bkaw').value; if (!a || !(w2 >= 1)) return; (p.adj = p.adj || []).push({w: Math.round(w2), amt: a, note: (document.getElementById('bkan').value || '').slice(0, 60)}); bkSave(p); bankRender(); }
    else if (t.classList && t.classList.contains('bkdel')){ var p2 = bkPlan(); if (!p2) return; p2.adj.splice(+t.getAttribute('data-i'), 1); bkSave(p2); bankRender(); }
    else if (t.id === 'bkreset'){ var p3 = bkPlan(); if (!p3) return; var el = document.getElementById('bank'); try{ localStorage.removeItem('bs_bankroll_plan'); }catch(e){} bankRender(); var a1 = document.getElementById('bks'), a2 = document.getElementById('bkp'), a3 = document.getElementById('bkw'); if (a1){ a1.value = p3.start; a2.value = p3.pct; a3.value = p3.since; } try{ localStorage.setItem('bs_bankroll_plan_prev', JSON.stringify(p3)); }catch(e){} } });
  render(); document.addEventListener('bs-account', render);
  // owner 11/1: "make a bunch of things collapsible" - every card folds on its title (remembered per browser), slips group by week (this week open),
  // and each slip's legs fold behind a Legs button
  (function(){ var st = {}; try{ st = JSON.parse(localStorage.getItem('bs_me_fold2') || '{}') || {}; }catch(e){}
    var hashId = (location.hash || '').slice(1);
    document.querySelectorAll('.me .card[id]').forEach(function(c){ var open = st[c.id] != null ? st[c.id] : c.getAttribute('data-def') !== 'shut'; if (c.id === hashId) open = true; c.classList.toggle('shut', !open); });
    document.addEventListener('click', function(e){
      var h = e.target.closest && e.target.closest('.me .card > h2'); if (h && !e.target.closest('a,button')){ var c = h.parentNode; c.classList.toggle('shut'); st[c.id] = !c.classList.contains('shut'); try{ localStorage.setItem('bs_me_fold2', JSON.stringify(st)); }catch(x){} return; }
      var w = e.target.closest && e.target.closest('.wkt'); if (w){ var li = w.parentNode, on = !li.classList.contains('on'); li.classList.toggle('on', on); document.querySelectorAll('.me li.sl.w' + li.dataset.w).forEach(function(x){ x.classList.toggle('wkoff', !on); }); return; }
      var g = e.target.closest && e.target.closest('.lgt'); if (g){ var gl = g.closest('li'); if (gl){ g.setAttribute('aria-expanded', gl.classList.toggle('lo') ? 'true' : 'false'); } } }); })();
  document.addEventListener('click', function(e){ var b = e.target.closest && e.target.closest('.ldb'); if (!b) return; var ks = [], gm = {}; try{ ks = JSON.parse(b.getAttribute('data-keys')) || []; gm = JSON.parse(b.getAttribute('data-g') || '{}') || {}; }catch(x){}
    if (window.BSLoadSlip) window.BSLoadSlip(ks, gm); else { b.textContent = 'Loading…'; setTimeout(function(){ if (window.BSLoadSlip) window.BSLoadSlip(ks, gm); }, 800); } });
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
MEP_JS = r"""
(function(){
  var box = document.getElementById('mep'); if(!box) return;
  var EMOJI = __EMOJI__, TEAMS = __TEAMS__, EDIT = false, P = null, REC = null, FANS = null, FOR = null, HOT = false;
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function inits(h){ var m = String(h || '').match(/[A-Z]/g) || []; return (m.slice(0, 2).join('') || String(h || '?').slice(0, 2)).toUpperCase(); }
  function hcol(){ if(P.color != null) return P.color; var h = 0, t = String(P.handle || ''); for(var i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) % 8; return h; }
  function acc(){ return window.bsAccount || null; }
  function form(){ var c = hcol();
    return '<form class="pedit" id="pedit" autocomplete="off"><label for="peh">Username</label><input id="peh" name="h" value="' + esc(P.handle) + '" maxlength="20" inputmode="text" autocapitalize="off" spellcheck="false">' +
      '<p class="hint">3 to 20 letters, numbers or underscores. You can change it once every 30 days. It is the name on the slips you post to Social.</p>' +
      '<fieldset><legend>Colour</legend><div class="sw">' + [0,1,2,3,4,5,6,7].map(function(i){ return '<label><input type="radio" name="c" value="' + i + '"' + (i === c ? ' checked' : '') + '><i class="pav c' + i + '" aria-hidden="true"></i><span class="sr">Colour ' + (i + 1) + '</span></label>'; }).join('') + '</div></fieldset>' +
      '<fieldset><legend>Avatar</legend><div class="em"><label><input type="radio" name="e" value=""' + (!P.emoji ? ' checked' : '') + '><i>Aa</i><span class="sr">My initials</span></label>' + EMOJI.map(function(x){ return '<label><input type="radio" name="e" value="' + x + '"' + (P.emoji === x ? ' checked' : '') + '><i>' + x + '</i></label>'; }).join('') + '</div></fieldset>' +
      '<fieldset><legend>Team</legend><div class="em">' + TEAMS.map(function(t){ return '<label title="' + t[0] + '"><input type="radio" name="e" value="' + t[1] + '"' + (P.emoji === t[1] ? ' checked' : '') + '><i>' + t[1] + '</i><span class="sr">' + t[0] + '</span></label>'; }).join('') + '</div></fieldset>' +
      '<p class="msg" id="pemsg" role="status"></p><div class="pbtn"><button type="submit" class="sv">Save profile</button><button type="button" data-pe="0">Cancel</button></div></form>'; }
  function paint(){ var A = acc(), u = A && A.user; if(!u || !P || P.user_id !== u.id){ box.hidden = true; box.innerHTML = ''; return; }
    // owner 11/22 1:46 AM ("Don't make actual record public knowledge for each user ... I don't want to see 0-23 -23.0u. You can put a fire
    // emoji for users that have hit recently. Otherwise don't put anything"): the card no longer reads or prints a win-loss record or
    // units for posted slips. It says how many slips are posted, and wears the same fire Social shows when one cashed in the last 7 days.
    var r = REC, n = r ? (r.posts || 0) : 0;
    var line = n ? n + ' slip' + (n === 1 ? '' : 's') + ' posted to Social' : 'No slips posted to Social yet';
    box.hidden = false;
    var head = '<i class="pav c' + hcol() + (P.emoji ? ' em' : '') + '" aria-hidden="true">' + esc(P.emoji || inits(P.handle)) + '</i><div class="pn"><h2>@' + esc(P.handle) + (HOT ? '<span class="hot" role="img" aria-label="Hit recently" title="One of your posted slips cashed in the last 7 days">🔥</span>' : '') + '</h2><p>' + esc(line) + (FANS != null ? ' · ' + FANS + ' follower' + (FANS === 1 ? '' : 's') : '') + '</p></div>';
    var keep = EDIT ? picked() : null;   /* a repaint while the editor is open (the record or follower count arriving) must not undo unsaved taps */
    box.innerHTML = EDIT ? '<div class="phd">' + head + '</div>' + form() : head + '<div class="pb"><button type="button" data-pe="1">Edit profile</button><a href="/social/#u=' + esc(u.id) + '">My posted slips</a></div>';
    if(keep) restore(keep); }
  /* the editor's current choices: colour, avatar, username - null when the editor is not on the page */
  function picked(){ var f = document.getElementById('pedit'); if(!f) return null; var a = document.activeElement;
    return {c: (f.querySelector('input[name=c]:checked') || {}).value, e: (f.querySelector('input[name=e]:checked') || {}).value, h: f.h.value, foc: a && a.id === 'peh' ? [a.selectionStart, a.selectionEnd] : null}; }
  function restore(k){ var f = document.getElementById('pedit'); if(!f) return;
    [['c', k.c], ['e', k.e]].forEach(function(x){ if(x[1] == null) return; [].forEach.call(f.querySelectorAll('input[name=' + x[0] + ']'), function(i){ i.checked = i.value === x[1]; }); });
    if(k.h != null) f.h.value = k.h;
    if(k.foc){ f.h.focus(); try{ f.h.setSelectionRange(k.foc[0], k.foc[1]); }catch(e){} }
    preview(); }
  /* owner 11/22: the picture follows the form before anything is saved. Cancel repaints it from the saved profile. */
  function preview(){ var k = picked(), a = box.querySelector('.phd > .pav'); if(!EDIT || !k || !a) return;
    var em = k.e || '', h = (k.h || '').replace(/^\s+|\s+$/g, '') || P.handle;
    a.className = 'pav c' + (+k.c || 0) + (em ? ' em' : ''); a.textContent = em || inits(h); }
  function load(){ var A = acc(), u = A && A.user; if(!u || !A.client || !A.client.rpc){ P = null; paint(); return; } if(A.profile && A.profile.user_id === u.id){ P = A.profile; paint(); } if(FOR === u.id) return; FOR = u.id;
    A.client.rpc('feed_profile_me').then(function(r){ if(r && r.data && r.data.user_id === u.id){ P = r.data; if(A.setProfile) A.setProfile(P); paint(); } }, function(){});
    A.client.from('feed_records').select('user_id,posts').eq('user_id', u.id).then(function(r){ REC = ((r && r.data) || [])[0] || null; paint(); }, function(){});
    A.client.from('feed_posts').select('user_id,last_ko,created_at,result').eq('status', 'open').eq('result', 'won').eq('user_id', u.id).gte('created_at', new Date(Date.now() - 14 * 864e5).toISOString()).limit(20).then(function(r){
      var now = Date.now(); HOT = ((r && r.data) || []).some(function(x){ if(!x || x.result !== 'won') return false; var t = Date.parse(x.last_ko) || Date.parse(x.created_at) || 0; return t && t <= now && now - t <= 7 * 864e5; }); paint(); }, function(){});
    A.client.from('feed_follows').select('follower').eq('followee', u.id).then(function(r){ if(r && r.data) FANS = r.data.length; paint(); }, function(){}); }
  box.addEventListener('click', function(e){ var b = e.target.closest && e.target.closest('[data-pe]'); if(!b) return; EDIT = b.dataset.pe === '1'; paint(); if(EDIT){ var i = document.getElementById('peh'); if(i) i.focus(); } });
  box.addEventListener('change', function(e){ var t = e.target; if(t && (t.name === 'c' || t.name === 'e')) preview(); });
  box.addEventListener('input', function(e){ if(e.target && e.target.id === 'peh') preview(); });
  box.addEventListener('submit', function(e){ if(e.target.id !== 'pedit') return; e.preventDefault(); var A = acc();
    var f = e.target, msg = document.getElementById('pemsg'), h = f.h.value.trim(), c = +(f.querySelector('input[name=c]:checked') || {}).value || 0, em = (f.querySelector('input[name=e]:checked') || {}).value || null, sv = f.querySelector('.sv');
    if(!/^[A-Za-z0-9_]{3,20}$/.test(h)){ msg.textContent = 'Usernames are 3 to 20 letters, numbers or underscores.'; msg.className = 'msg err'; return; }
    sv.disabled = true; msg.textContent = 'Saving…'; msg.className = 'msg';
    A.client.rpc('feed_profile_set', {p_handle: h, p_color: c, p_emoji: em}).then(function(r){ sv.disabled = false;
      if(r.error){ msg.textContent = /avatar from the list/i.test(r.error.message || '') ? 'Team avatars are being switched on. Pick another for now.' : (r.error.message || 'Could not save.').replace(/^.*?: /, ''); msg.className = 'msg err'; return; }
      P = r.data && r.data.user_id ? r.data : Object.assign({}, P, {handle: h, color: c, emoji: em}); EDIT = false; if(A.setProfile) A.setProfile(P); paint(); },
      function(){ sv.disabled = false; msg.textContent = 'Could not save. Check your connection and try again.'; msg.className = 'msg err'; }); });
  document.addEventListener('bs-account', function(){ FOR = null; REC = null; FANS = null; HOT = false; load(); });
  document.addEventListener('bs-profile', function(e){ var A = acc(); if(e.detail && A && A.user && e.detail.user_id === A.user.id && !EDIT){ P = e.detail; paint(); } });
  var n = 0; (function wait(){ var A = acc(); if(A && A.user) return load(); if(++n < 40) setTimeout(wait, 150); })();
})();
"""
def _mep_js():
    """The avatar lists come from social.py's own picker, so the two editors can never offer different sets."""
    import re, os
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "social.py"), encoding="utf-8").read()
    em = re.search(r"EMOJI = (\[.*?\]), TEAMS = (\[.*?\]);", src)
    return MEP_JS.replace("__EMOJI__", em.group(1)).replace("__TEAMS__", em.group(2))

def me_page():
    _link, _base = _base_css()
    return f"""<title>My BetSweep</title>
<meta name="description" content="Your saved betslips, built fantasy teams, trade scenarios and Sleeper league - in this browser, or on every device when you sign in.">
{_link}
<style>{_base}{ME_CSS}{__import__("slipimport").IMPORT_CSS}{__import__("social").SAVED_CSS}{__import__("social").POST_CSS}</style>
<div class="me">
 <h1>My BetSweep</h1>
 <section class="mep" id="mep" aria-label="Your profile" hidden></section>
 <p class="m" id="who"></p>
 <section class="hub" id="hub" aria-label="Your bets at a glance">
  <div class="hubt"><a class="ht" href="#crec"><small>Open slips</small><b id="hopen">&ndash;</b><span id="hopens"></span></a><a class="ht" href="#crec"><small>Record</small><b id="hrec">&ndash;</b><span id="hunits"></span></a><a class="ht" href="#crec"><small id="hweekl">This week</small><b id="hweek">&ndash;</b><span id="hweeks"></span></a></div>
  <div class="hubw" id="hubw" hidden></div>
 </section>
 <div class="card" id="crec"><h2>Your slips <span id="record" style="font-size:16px"></span></h2>{__import__("slipimport").CARD_HTML}<p class="m">Every slip you save, graded from the box scores after the games.</p><details class="how"><summary>How saving and grading work</summary><p class="m">Save slip in the Parlay Builder, the Live page, or Tail on a promoted bet puts a slip here with its Bet on FanDuel button until kickoff. After the games it is graded from the box scores, the same way we grade our own legs. Units are at the slip's own odds and stake; a push drops the leg. Totals and first-TD legs show as pending until that grading lands.</p></details><div id="recbrk"></div><ul id="slips"></ul></div>
 <div class="card" id="cbank" data-def="shut"><h2>Bankroll <span id="bkhead" style="font-size:16px"></span></h2><p class="m">Private to you. Saved slips grade into it automatically; add anything you bet elsewhere below.</p><details class="how"><summary>How the bankroll works</summary><p class="m">It is kept in this browser and, when you sign in, in your own account - no one else can see it. Slips from Save slip, Tail, or the FanDuel screenshot import grade into it. Your unit resets every Tuesday to a set share of the bankroll, so it grows when you win and shrinks when you lose.</p></details><div id="bank"></div></div>
 <div class="card" id="cexpo" data-def="shut"><h2>Exposure this week</h2><p class="m">Who your open slips depend on. Every player in at least two of this week's saved slips, with the stake riding on him and what you would stop being able to win if he has a bad night. Only slips saved here count - tap Tail on a promo or Save slip in the builder for the bets you place.</p><ul id="expo"></ul></div>
 <div class="card" id="alerts" data-def="shut"><h2>Slip alerts</h2><p class="m">Get a notification on this device when a player on one of your saved slips (or your open betslip) is ruled <b>Out</b> or <b>Doubtful</b> before kickoff - with a swap idea from the same game - plus, if you want them, live updates on your saved slips during games and a Thursday note when the Model's Best picks are up. Alerts follow the slips saved to your account, so sign in first.</p><p class="m" id="pushmsg"></p><div class="pushbtns"><button type="button" id="pushon" hidden>Turn on alerts</button><button type="button" id="pushtest" hidden>Send a test alert</button><button type="button" id="pushoff" hidden>Turn off on this device</button></div><div class="pushprefs" id="pushprefs" hidden><label><input type="checkbox" id="pplive" checked> Live updates during games: a leg on a saved slip hits or busts, a slip cashes</label><label><input type="checkbox" id="ppweekly" checked> Thursday note when the week's Model's Best picks are up</label>{PROMO_CB}{NEWS_CB}</div></div>
 <div class="card" id="cmail" data-def="shut"><h2>Email digest</h2><p class="m">The morning brief by email on game days (Thursday and Sunday, 9:20 AM CT): the weather watch, the news that moved the model and the top looks. Same text as the push, for people who never allow notifications.</p><p class="m" id="mailmsg"></p><div class="pushbtns"><label id="maillab" hidden><input type="checkbox" id="mailon"> Email me the brief at <b id="mailaddr"></b></label></div></div>
 <div class="card" id="cbld" data-def="shut"><h2>Parlay Builder <a href="/build/">Open →</a></h2><ul id="builder"></ul></div>
 <div class="card" id="ctrd" data-def="shut"><h2>Trade calculator <a href="/trade/">Open →</a></h2><ul id="trades"></ul></div>
 <div class="card" id="cfan" data-def="shut"><h2>Fantasy teams &amp; DFS lineups <a href="/team/">Fantasy →</a></h2><ul id="fantasy"></ul></div>
 <div class="methmrow" id="cthm" title="How BetSweep looks on this device. Auto follows your phone or computer's light or dark setting."><span id="thmlab">Theme</span><div class="thm methm" role="group" aria-labelledby="thmlab"><button type="button" data-thm="auto">Auto</button><button type="button" data-thm="dark">Dark</button><button type="button" data-thm="light">Light</button></div></div>
 <p class="m">Accounts are optional and free. Sign out from the header at any time; to delete your account and everything saved with it, email support@betsweep.co from the signed-in address.</p>
</div>
<script>{ME_JS}</script>
<script>{_mep_js()}</script>
<script defer src="/import.js"></script>
{__import__("social").POST_HTML}
{__import__("social").POST_JS}
{__import__("social").SAVED_JS}
<script>{KEEP_JS.replace("__VAPID__", VAPID_PUBLIC)}{PUSH_JS.replace("__SB__", SUPABASE_URL)}</script>"""

PUSH_JS = r"""
(function(){
  var FN = '__SB__/functions/v1/slip-alerts', K = window.bsPushKeep;
  var msg = document.getElementById('pushmsg'), on = document.getElementById('pushon'), test = document.getElementById('pushtest'), off = document.getElementById('pushoff');
  if(!msg || !K) return;
  function say(t, c){ msg.textContent = t; msg.className = 'm ' + (c || ''); }
  var prefs = document.getElementById('pushprefs'), pl = document.getElementById('pplive'), pw = document.getElementById('ppweekly'), curEp = null;
  function show(a, b, c){ on.hidden = !a; test.hidden = !b; off.hidden = !c; if(prefs) prefs.hidden = !c; }
  /* 11/23: every choice is saved through bsPushKeep.save, which reports a save only when a row really changed (it used to say "On" with the row missing) */
  var pp = document.getElementById('pppromo'), ppl = document.getElementById('pppromolab');
  if(pp) pp.addEventListener('change', function(){ if(!curEp) return; K.save(curEp, {promo: pp.checked}).then(function(r){ if(r && r.error){ pp.checked = !pp.checked; say('Could not save that: ' + r.error.message, 'err'); } else say(pp.checked ? 'On - you will hear when a slip posts.' : 'Saved.', 'ok'); }); });
  var pn = document.getElementById('ppnews'), pnl = document.getElementById('ppnewslab');
  if(pn) pn.addEventListener('change', function(){ if(!curEp) return; K.save(curEp, {news: pn.checked}).then(function(r){ if(r && r.error){ pn.checked = !pn.checked; say('Could not save that: ' + r.error.message, 'err'); } else say(pn.checked ? 'On - you will hear when a big name is out, released or traded.' : 'Saved.', 'ok'); }); });
  var pt = document.getElementById('ppteam'), ptl = document.getElementById('ppteamlab'), ptWas = '';
  if(pt) pt.addEventListener('change', function(){ if(!curEp) return; var v = pt.value || null; K.save(curEp, {team: v}).then(function(r){ if(r && r.error){ pt.value = ptWas; say('Could not save that: ' + r.error.message, 'err'); } else { ptWas = pt.value; say(v ? 'On - you will get ' + pt.options[pt.selectedIndex].text + ' news.' : 'Saved.', 'ok'); } }); });
  function savePref(){ if(!curEp) return; K.save(curEp, {live: pl.checked, weekly: pw.checked}).then(function(r){ if(r && r.error) say(/column/i.test(r.error.message) ? 'Saved alerts work; these two settings switch on after the next server update.' : r.error.message, 'err'); else say('Saved.', 'ok'); }); }
  if(pl) pl.addEventListener('change', savePref); if(pw) pw.addEventListener('change', savePref);
  /* the boxes come from the device's own row; a setting the database does not have yet stays hidden */
  function fill(row){
    if(pp){ if(row && 'promo' in row){ ppl.hidden = false; pp.checked = !!row.promo; } else ppl.hidden = true; }
    if(pn){ if(row && 'news' in row){ pnl.hidden = false; pn.checked = !!row.news; } else pnl.hidden = true; }
    if(pt){ if(row && 'team' in row){ ptl.hidden = false; pt.value = row.team || ''; ptWas = pt.value; } else ptl.hidden = true; }
    if(row){ pl.checked = row.live !== false; pw.checked = row.weekly !== false; }
  }
  /* says so when the device had lost its sign-up and it was put back: the reader should know it happened, and it is the only count of how often it does */
  function onText(){
    var n = K.note(); if(!n.rn || !n.re) return 'Alerts are on for this device.';
    var d = new Date(n.re), when = d.toLocaleDateString('en-US', {month: 'short', day: 'numeric'}) + ', ' + d.toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit'});
    return 'Alerts are on for this device. It lost its sign-up ' + (n.rn === 1 ? 'once and was switched back on for you (' + when + ').' : n.rn + ' times and was switched back on each time (last ' + when + ').');
  }
  function painted(res){ curEp = res.sub.endpoint; show(0,1,1); say(onText(), 'ok'); fill(res.row); }
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent), standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  function user(){ return window.bsAccount && window.bsAccount.user; }
  function client(){ return window.bsAccount && window.bsAccount.client; }
  var known = false, seq = 0, last = null, lastAt = 0, lastU = null;
  function refresh(){
    if(!K.supported()){ show(0,0,0); say(ios && !standalone ? 'On iPhone, alerts need the app: tap Share, then Add to Home Screen, open BetSweep from your home screen and come back here.' : 'This browser cannot receive alerts.'); return; }
    /* 11/23: until the account script has answered, say nothing - "Sign in" used to flash at readers who were signed in */
    if(!user()){ show(0,0,0); say(known ? 'Sign in (top right) to turn on alerts.' : ''); return; }
    if(Notification.permission === 'denied'){ show(0,0,0); say('Notifications are blocked for betsweep.co in this browser\'s settings - allow them there, then reload.', 'err'); return; }
    if(last && lastU === user().id && Date.now() - lastAt < 5000){ if(last.sub) painted(last); return; }
    var my = ++seq, uid = user().id;
    K.keep(true).then(function(res){
      if(my !== seq) return;
      last = res || {}; lastAt = Date.now(); lastU = uid;
      if(last.sub) painted(last); else { curEp = null; show(1,0,0); say(''); }
    });
  }
  on.addEventListener('click', function(){
    on.disabled = true; say('Asking for permission…'); seq++;
    K.turnOn().then(function(res){ last = res; lastAt = Date.now(); lastU = user() && user().id; painted(res); })
    .catch(function(e){ var t = String(e && (e.message || e)); say(/push_subs|relation|does not exist/i.test(t) ? 'Alerts are not switched on on our side yet - try again soon.' : t, 'err'); })
    .then(function(){ on.disabled = false; });
  });
  // owner 11/5: email digest opt-in (email_prefs: the signed-in user's own address; the function sends through Resend)
  (function(){ var lab = document.getElementById('maillab'), cb = document.getElementById('mailon'), msg = document.getElementById('mailmsg'); if (!lab || !cb) return;
    function paintMail(){ var u = user(); if (!u || !u.email){ lab.hidden = true; msg.textContent = 'Sign in to get the brief by email.'; return; }
      lab.hidden = false; document.getElementById('mailaddr').textContent = u.email; msg.textContent = '';
      client().from('email_prefs').select('digest').eq('user_id', u.id).maybeSingle().then(function(r){ cb.checked = !!(r.data && r.data.digest); }).catch(function(){}); }
    cb.addEventListener('change', function(){ var u = user(); if (!u) return; cb.disabled = true;
      client().from('email_prefs').upsert({user_id: u.id, email: u.email, digest: cb.checked, updated_at: new Date().toISOString()}, {onConflict: 'user_id'}).then(function(r){ msg.textContent = r.error ? 'Could not save that: ' + r.error.message : (cb.checked ? 'On - the next game-day brief lands in your inbox.' : 'Off.'); }).catch(function(){ msg.textContent = 'Could not save that.'; }).then(function(){ cb.disabled = false; }); });
    document.addEventListener('bs-account', paintMail); paintMail(); })();
  test.addEventListener('click', function(){
    test.disabled = true; say('Sending…');
    client().auth.getSession().then(function(r){ var tok = r.data && r.data.session && r.data.session.access_token;
      return fetch(FN, {method: 'POST', headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + tok}, body: JSON.stringify({test: true})}); })
    .then(function(r){ return r.text().then(function(t){ var j = null; try { j = JSON.parse(t); } catch(e){} return {s: r.status, j: j, t: t}; }); })
    .then(function(x){ var j = x.j; if(j && j.sent) say('Sent - it should show up in a few seconds.', 'ok'); else say((j && j.error) || ('The alert service answered ' + x.s + ': ' + String((j && (j.message || j.msg)) || x.t || 'no details').slice(0, 160)), 'err'); })
    .catch(function(){ say('Could not reach the alert service.', 'err'); }).then(function(){ test.disabled = false; });
  });
  off.addEventListener('click', function(){
    seq++; last = null;
    K.turnOff().then(function(){ curEp = null; say('Alerts are off for this device.'); show(1,0,0); }).catch(function(){ refresh(); });
  });
  document.addEventListener('bs-account', function(){ known = true; last = null; refresh(); });
  /* back from the background: the check may have made a new sign-up, so the card reads the state again */
  document.addEventListener('visibilitychange', function(){ if(document.visibilityState === 'visible'){ last = null; refresh(); } });
  setTimeout(function(){ known = true; refresh(); }, 1500); refresh();
})();
"""
