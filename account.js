
(function(){
  var CFG = window.__BS_ACCOUNT || {}; if(!CFG.url || !window.supabase) return;
  var sb = window.supabase.createClient(CFG.url, CFG.key, {auth: {persistSession: true, autoRefreshToken: true, detectSessionInUrl: true}});
  window.bsAccount = {client: sb, user: null};
  // ---- which browser-storage keys follow the account (everything a person builds; not caches) ----
  var SYNC = /^bs_(slips?_w\d+|slipk_w\d+|slipmeta_w\d+|trade_\d+|manual|sleeper_user|sleeper_league|team_mode|tip|tracked.*)$/;
  var META_KEY = 'bs_sync_meta', meta = {}; try{ meta = JSON.parse(localStorage.getItem(META_KEY)||'{}')||{}; }catch(e){}
  function saveMeta(){ try{ localStorage.setItem(META_KEY, JSON.stringify(meta)); }catch(e){} }
  var user = null, pending = {}, timer = null, ready = false;
  var _set = localStorage.setItem.bind(localStorage), _rm = localStorage.removeItem.bind(localStorage);
  localStorage.setItem = function(k, v){ _set(k, v); if (SYNC.test(k)){ meta[k] = Date.now(); saveMeta(); if (user && ready){ pending[k] = String(v); schedule(); } } };
  localStorage.removeItem = function(k){ _rm(k); if (SYNC.test(k)){ meta[k] = Date.now(); saveMeta(); if (user && ready){ pending[k] = null; schedule(); } } };
  function schedule(){ clearTimeout(timer); timer = setTimeout(flush, 800); }
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
      + '<button class="go" type="button" id="bsgo">Email me a sign-in link</button>' + (CFG.google ? '<button class="g" type="button" id="bsgoogle">Continue with Google</button>' : '') + '<div class="msg" id="bsmsg"></div><small class="lg">No passwords: the link in the email signs you in. We store what you build on the site and your email, nothing else. Information only, 21+, please bet responsibly.</small></div>';
      document.body.appendChild(dlg);
      dlg.addEventListener('click', function(e){ if (e.target===dlg || e.target.closest('.x')) dlg.hidden = true; });
      dlg.querySelector('#bsgo').addEventListener('click', function(){ var em = dlg.querySelector('#bsemail').value.trim(), ok = dlg.querySelector('#bs21').checked, m = dlg.querySelector('#bsmsg');
        if(!/.+@.+\..+/.test(em)){ m.textContent = 'Enter your email.'; m.className = 'msg err'; return; } if(!ok){ m.textContent = 'Please confirm you are 21+ and accept the terms.'; m.className = 'msg err'; return; }
        var b = dlg.querySelector('#bsgo'); b.disabled = true; m.textContent = 'Sending…'; m.className = 'msg';
        sb.auth.signInWithOtp({email: em, options: {emailRedirectTo: location.origin + location.pathname, data: {over21: true, accepted_terms_at: new Date().toISOString()}}}).then(function(r){ b.disabled = false;
          if (r.error){ m.textContent = r.error.message; m.className = 'msg err'; } else { m.textContent = 'Check your email - the link signs you in (look in spam if it is slow).'; m.className = 'msg'; } }); });
      var g = dlg.querySelector('#bsgoogle'); if (g) g.addEventListener('click', function(){ sb.auth.signInWithOAuth({provider: 'google', options: {redirectTo: location.origin + location.pathname}}); }); }
    dlg.hidden = false; setTimeout(function(){ var i = dlg.querySelector('#bsemail'); if(i) i.focus(); }, 50); }
  function toast(t){ var el = document.createElement('div'); el.textContent = t; el.style.cssText = 'position:fixed;left:50%;bottom:70px;transform:translateX(-50%);background:#1b1a17;color:#fff;padding:9px 14px;border-radius:999px;font:13px IBM Plex Sans,system-ui,sans-serif;z-index:120;box-shadow:0 8px 24px rgba(0,0,0,.3)'; document.body.appendChild(el); setTimeout(function(){ el.remove(); }, 3500); }
  function onSession(s){ var u = s && s.user; if (u && (!user || user.id !== u.id)){ user = u; window.bsAccount.user = u; paint(); pull().then(function(changed){ ready = true; document.dispatchEvent(new CustomEvent('bs-account', {detail: {user: u, changed: changed}})); if (changed && !/\/me\//.test(location.pathname)){ toast('Synced from your account'); setTimeout(function(){ location.reload(); }, 900); } }); }
    else if (!u){ user = null; window.bsAccount.user = null; ready = false; paint(); document.dispatchEvent(new CustomEvent('bs-account', {detail: {user: null}})); } }
  paint();
  sb.auth.getSession().then(function(r){ onSession(r.data && r.data.session); });
  sb.auth.onAuthStateChange(function(ev, s){ if (ev === 'SIGNED_IN' || ev === 'INITIAL_SESSION' || ev === 'TOKEN_REFRESHED') onSession(s); if (ev === 'SIGNED_OUT') onSession(null); if (ev === 'SIGNED_IN' && dlg) dlg.hidden = true; });
})();
