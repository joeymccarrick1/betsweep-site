(function(){
  var TESS = 'https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js';
  var NICK = {ARI:'Cardinals',ATL:'Falcons',BAL:'Ravens',BUF:'Bills',CAR:'Panthers',CHI:'Bears',CIN:'Bengals',CLE:'Browns',DAL:'Cowboys',DEN:'Broncos',DET:'Lions',GB:'Packers',HOU:'Texans',IND:'Colts',JAX:'Jaguars',KC:'Chiefs',LV:'Raiders',LAC:'Chargers',LA:'Rams',MIA:'Dolphins',MIN:'Vikings',NE:'Patriots',NO:'Saints',NYG:'Giants',NYJ:'Jets',PHI:'Eagles',PIT:'Steelers',SF:'49ers',SEA:'Seahawks',TB:'Buccaneers',TEN:'Titans',WAS:'Commanders'};
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function nrm(s){ return String(s||'').toLowerCase().replace(/[^a-z ]+/g, ' ').replace(/\b(jr|sr|ii|iii|iv|v|ill)\b/g, ' ').replace(/\s+/g, ' ').trim(); }
  function lev(a, b){ if (a === b) return 0; var m = a.length, n = b.length, d = [], i, j; for (i = 0; i <= n; i++) d[i] = i;
    for (i = 1; i <= m; i++){ var p = d[0]; d[0] = i; for (j = 1; j <= n; j++){ var t = d[j]; d[j] = Math.min(d[j] + 1, d[j-1] + 1, p + (a[i-1] === b[j-1] ? 0 : 1)); p = t; } } return d[n]; }
  function legKey(l){ return l.pl + '|' + l.m + '|' + Math.round(l.ln || 1); }

  // ---- the parser (pure: text + builder data in, legs out) ----
  var MK = [[/DRIVE|QUARTER|1ST HALF|FIRST HALF|2ND HALF/i, null], [/EITHER PLAYER/i, 'Either TD'], [/FIRST TOUCHDOWN|1ST TOUCHDOWN/i, 'First TD'],
    [/TIME TOUCHDOWN|ANYTIME TD/i, 'Anytime TD'], [/RUSH(ING)?\s*\+\s*REC/i, 'Rush + Rec Yards'], [/LONGEST RECEPTION/i, 'Longest Reception'],
    [/RECEPTIONS/i, 'Receptions'], [/RECEIV/i, 'Receiving Yards'], [/RUSHING\s*Y/i, 'Rushing Yards'], [/PASSING\s*Y/i, 'Passing Yards'],
    [/MONEYLINE/i, 'Moneyline'], [/SPREAD/i, 'Spread'], [/TOTAL POINTS|GAME TOTAL/i, 'Total']];
  function descriptor(line){   // the grey caps line under each leg title
    var letters = line.replace(/[^A-Za-z]/g, ''); if (letters.length < 6) return undefined;
    var caps = line.replace(/[^A-Z]/g, '').length / letters.length; if (caps < 0.7) return undefined;
    for (var i = 0; i < MK.length; i++) if (MK[i][0].test(line)) return MK[i][1];
    return undefined; }
  function oddsIn(s){ var m = String(s).match(/(?:^|\s)([+\-−~“"]?)(\d{3,6})\s*$/); if (!m) return null; var sign = m[1] === '+' ? 1 : -1; return m[1] === '+' ? +m[2] : -m[2]; }
  function players(BS){ var P = {}; (BS.legs || []).forEach(function(l){ if (!l.gl && l.pl) P[l.pl] = 1; }); (BS.__names || []).forEach(function(n){ P[n] = 1; });   // __names: the Players directory, so legs FanDuel stopped pricing at kickoff still import
    return Object.keys(P).map(function(p){ return {pl: p, n: nrm(p)}; }); }
  function matchName(text, P){   // best player whose name is in the text (exact, else within 2 edits per window)
    var t = nrm(text); if (t.length < 4) return null; var best = null, bs = 0, words = t.split(' ');
    P.forEach(function(p){ var s = 0;
      if ((' ' + t + ' ').indexOf(' ' + p.n + ' ') >= 0) s = 100 + p.n.length;
      else { var k = p.n.split(' ').length; for (var i = 0; i + k <= words.length; i++){ var w = words.slice(i, i + k).join(' '), d = lev(w, p.n), r = 1 - d / Math.max(w.length, p.n.length); if (r >= 0.8 && r * 100 > s) s = r * 100; } }
      if (s > bs){ bs = s; best = p.pl; } });
    return best; }
  function parse(text, BS){
    var P = players(BS), legs = BS.legs || [], out = {legs: [], odds: null, stake: null};
    var L = String(text).split(/\n+/).map(function(s){ return s.replace(/[|]/g, ' ').replace(/\s+/g, ' ').trim(); }).filter(Boolean);
    L.forEach(function(s, i){ var h = s.match(/(\d+)\s*Leg[^+\-]*?([+-]\d{3,7})/i); if (h && out.odds == null) out.odds = +h[2];
      if (/TOTAL WAGER/i.test(s) && i > 0){ var w = L[i-1].match(/\$\s*(\d+(?:\.\d{1,2})?)/); if (w) out.stake = +w[1]; } });
    var used = {};
    L.forEach(function(s, i){
      var m = descriptor(s); if (m === undefined) return;
      // the title: the nearest line above with real words (skip lone odds / icon noise and the game line)
      var t = '', j = i - 1; while (j >= 0 && j >= i - 3){ var c = L[j]; if (c.replace(/[^A-Za-z]/g, '').length >= 4 && !/ @ /.test(c) && descriptor(c) === undefined && !used[j]){ t = c; used[j] = 1; break; } j--; }
      var game = (L[i+1] && / @ /.test(L[i+1])) ? L[i+1] : '';
      var odds = oddsIn(t) || oddsIn(s) || (L[i-1] && /^[+\-−~“"]?\d{3,6}$/.test(L[i-1]) ? oddsIn(L[i-1]) : null);
      var title = t.replace(/\s*[+\-−~“"]?\d{3,6}\s*$/, '');
      var raw = (title || s).replace(/^[^A-Za-z]*(?:[A-Za-z]{1,2}[^A-Za-z]+)?/, '');
      if (m === null){ out.legs.push({ok: false, raw: raw, why: 'drive / quarter props are not priced on BetSweep'}); return; }
      if (m === 'Either TD'){ var two = title.split(/\s+or\s+/i); var a = two[0] && matchName(two[0], P), b = two[1] && matchName(two[1], P);
        if (a && b) out.legs.push({ok: true, key: a + ' or ' + b + '|Either TD|1', label: a + ' or ' + b + ' anytime TD', odds: odds});
        else out.legs.push({ok: false, raw: raw, why: 'could not read both names'}); return; }
      if (m === 'Moneyline' || m === 'Spread' || m === 'Total'){
        var gl = legs.filter(function(l){ return l.gl && l.m === m; }), hit = null;
        if (m === 'Total'){ var tm = title.match(/(Over|Under)\s*\+?(\d+(?:\.\d+)?)/i); if (tm){ var pl = tm[1][0].toUpperCase() + tm[1].slice(1).toLowerCase() + ' ' + tm[2];
            hit = gl.filter(function(l){ return l.pl === pl && (!game || game.indexOf(NICK[l.g.split('-')[0]] || '~') >= 0 || game.indexOf(NICK[l.g.split('-')[1]] || '~') >= 0); })[0]; } }
        else { var ab = Object.keys(NICK).filter(function(k){ return title.indexOf(NICK[k]) >= 0; })[0];
          if (ab){ if (m === 'Moneyline') hit = gl.filter(function(l){ return l.pl === NICK[ab] + ' ML'; })[0];
            else { var sp = title.match(/([+-]\d+(?:\.\d+)?)\s*$/); if (sp) hit = gl.filter(function(l){ return l.pl === ab + ' ' + sp[1]; })[0]; } } }
        if (hit) out.legs.push({ok: true, key: legKey(hit), label: hit.pl + (m === 'Total' ? ' (' + hit.g + ')' : ''), odds: odds, leg: hit});
        else out.legs.push({ok: false, raw: raw, why: 'game line not on this week\'s board'}); return; }
      // player props: name from the caps line (cleaner), else the title
      var capName = s.split(/\s+-\s+/)[0]; var who = (capName && capName !== s ? matchName(capName, P) : null) || matchName(title, P);
      if (!who){ out.legs.push({ok: false, raw: raw, why: 'player not on this week\'s board'}); return; }
      var ln = 1, mk = m, n;
      if (m === 'Anytime TD' || m === 'First TD') ln = 1;
      else if ((n = title.match(/(\d+(?:\.\d+)?)\s*\+/))) ln = +n[1];
      else if ((n = title.match(/Over\s*\+?(\d+(?:\.\d+)?)/i))) ln = Math.ceil(+n[1]);
      else if ((n = title.match(/Under\s*\+?(\d+(?:\.\d+)?)/i))){ ln = +n[1]; mk = 'Under ' + m; }
      else { out.legs.push({ok: false, raw: raw, why: 'could not read the line'}); return; }
      var same = legs.filter(function(l){ return l.pl === who && l.m === mk && Math.round(l.ln || 1) === Math.round(ln || 1); })[0];
      var key = same ? legKey(same) : who + '|' + mk + '|' + Math.round(ln || 1);
      var label = mk === 'Anytime TD' ? who + ' anytime TD' : mk === 'First TD' ? who + ' first TD' : /^Under /.test(mk) ? who + ' under ' + ln + ' ' + mk.slice(6).toLowerCase() : who + ' ' + ln + '+ ' + mk.toLowerCase();
      out.legs.push({ok: true, key: key, label: label, odds: odds, leg: same, unpriced: !same});
    });
    return out; }

  // ---- image -> text, in the browser ----
  function loadTess(){ if (window.Tesseract) return Promise.resolve(window.Tesseract);
    return new Promise(function(res, rej){ var s = document.createElement('script'); s.src = TESS; s.onload = function(){ res(window.Tesseract); }; s.onerror = function(){ rej(new Error('could not load the reader')); }; document.head.appendChild(s); }); }
  function prep(file){ return new Promise(function(res, rej){ var img = new Image(), u = URL.createObjectURL(file);
    img.onload = function(){ var sc = img.width < 1400 ? 2 : 1, w = img.width * sc, h = img.height * sc, c = document.createElement('canvas'); c.width = w; c.height = h;
      var x = c.getContext('2d'); x.imageSmoothingQuality = 'high'; x.drawImage(img, 0, 0, w, h); var d = x.getImageData(0, 0, w, h), p = d.data, sum = 0, i;
      for (i = 0; i < p.length; i += 4){ var v = Math.max(p[i], p[i+1], p[i+2]); p[i] = v; sum += v; }
      var dark = sum / (p.length / 4) < 128;
      for (i = 0; i < p.length; i += 4){ var g = dark ? 255 - p[i] : p[i]; g = g < 150 ? 0 : 255; p[i] = p[i+1] = p[i+2] = g; p[i+3] = 255; }
      x.putImageData(d, 0, 0); URL.revokeObjectURL(u); res(c); };
    img.onerror = function(){ rej(new Error('that file is not a picture we can open')); }; img.src = u; }); }
  var BSD = null;
  function builderData(){ if (BSD) return Promise.resolve(BSD);
    return fetch('/build/', {cache: 'no-cache'}).then(function(r){ return r.text(); }).then(function(h){ var m = h.match(/src="(\/build\/data-[0-9a-f]+\.js)"/); return m ? fetch(m[1]).then(function(r){ return r.text(); }) : h; })
      .then(function(js){ var i = js.indexOf('window.__BS = '); if (i < 0) throw new Error('no board data'); var s = js.indexOf('{', i), dep = 0, q = false, e = false, k;
        for (k = s; k < js.length; k++){ var ch = js[k]; if (q){ if (e) e = false; else if (ch === '\\') e = true; else if (ch === '"') q = false; continue; } if (ch === '"') q = true; else if (ch === '{') dep++; else if (ch === '}'){ dep--; if (!dep) break; } }
        BSD = JSON.parse(js.slice(s, k + 1)); return fetch('/player/').then(function(r){ return r.ok ? r.text() : ''; }).catch(function(){ return ''; })
          .then(function(h){ var names = [], re = /<span><b>([^<]+)<\/b>/g, m; while ((m = re.exec(h))) names.push(m[1].replace(/&#x27;|&#39;/g, "'").replace(/&amp;/g, '&')); BSD.__names = names; return BSD; }); }); }

  // owner 11/1: "when I import a slip from Fanduel I can load it to my betslip on betsweep" - the open betslip is bs_slipk_w<W> (the same key the
  // builder, boards and player pages share); legs the builder prices come up in the slip with the model's numbers, the rest stay on the saved slip.
  function loadSlip(BS, keys){
    var W = BS.week, have = {}; (BS.legs || []).forEach(function(l){ have[legKey(l)] = 1; });
    var on = keys.filter(function(k){ return have[k]; }), off = keys.length - on.length;
    try{ localStorage.setItem('bs_slipk_w' + W, JSON.stringify(on)); if (off) sessionStorage.setItem('bs_impnote', off + ' leg' + (off === 1 ? '' : 's') + ' from your FanDuel slip ' + (off === 1 ? 'is' : 'are') + ' not on the builder board (games already under way, either-player TDs or lines we do not price) - ' + (off === 1 ? 'it stays' : 'they stay') + ' on the saved slip.'); }catch(e){}
    location.href = '/build/#slip'; }
  window.BSLoadSlip = function(keys){ return builderData().then(function(BS){ loadSlip(BS, keys); }); };
  // ---- the card on /me/ ----
  function am(o){ o = +o; return isNaN(o) || !o ? '' : (o > 0 ? '+' + o : String(o)); }
  function setup(){
    var card = document.getElementById('import'); if (!card) return; var out = document.getElementById('impout'), inp = card.querySelector('input[type=file]');
    function say(h){ out.innerHTML = '<p class="st">' + h + '</p>'; }
    function go(file){ if (!file) return; say('Reading your slip… (the first time takes a few seconds to load the reader)');
      Promise.all([builderData(), loadTess().then(function(T){ return prep(file).then(function(c){ return T.recognize(c, 'eng', {tessedit_pageseg_mode: '4'}); }); })])
        .then(function(r){ show(parse(r[1].data.text || '', r[0]), r[0]); })
        .catch(function(e){ say('Could not read that picture (' + esc(e.message || e) + '). Try a full, uncropped screenshot of the slip.'); }); }
    function show(R, BS){
      var good = R.legs.filter(function(l){ return l.ok; });
      if (!R.legs.length){ say('No FanDuel legs found in that picture. Use a screenshot of the betslip or of the bet under My Bets, with the leg names showing.'); return; }
      var h = '<p class="st">Found ' + good.length + ' of ' + R.legs.length + ' legs' + (R.odds ? ' · FanDuel ' + am(R.odds) : '') + '. Untick anything that is wrong.</p><ul>';
      R.legs.forEach(function(l, i){ h += l.ok ? '<li><input type="checkbox" checked data-i="' + i + '"><span>' + esc(l.label) + (l.odds ? ' <b>' + am(l.odds) + '</b>' : '') +
          '<small class="' + (l.unpriced ? 'warn' : 'ok') + '">' + (l.unpriced ? 'saved and graded - not on our board at this exact line, so no model price' : 'matched to this week\'s board') + '</small></span></li>'
        : '<li class="no"><span>✗ ' + esc(l.raw) + '<small>' + esc(l.why) + ' - not imported</small></span></li>'; });
      if (!good.length){ out.innerHTML = h + '</ul><p class="st">None of these legs are markets BetSweep prices, so there is nothing to save. Player yards, catches, touchdowns and game lines import fine.</p>'; return; }
      h += '</ul><div class="row"><input type="text" id="impname" maxlength="60" value="FanDuel ' + (good.length) + '-leg' + (R.odds ? ' ' + am(R.odds) : '') + '"><input type="text" id="impodds" inputmode="text" maxlength="9" style="flex:0 0 110px;min-width:0" placeholder="Odds +650" value="' + (R.odds ? am(R.odds) : '') + '"><button type="button" class="cta" id="impsave">Save slip</button><button type="button" class="sec" id="impload" style="font:inherit;font-weight:700;padding:9px 14px;border-radius:8px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer">Load into betslip</button></div>';
      out.innerHTML = h;
      function ticked(){ var keys = []; out.querySelectorAll('input[type=checkbox]').forEach(function(c){ if (c.checked) keys.push(R.legs[+c.dataset.i].key); }); return keys; }
      document.getElementById('impload').addEventListener('click', function(){ var keys = ticked(); if (!keys.length){ say('Nothing ticked - nothing to load.'); return; } loadSlip(BS, keys); });
      document.getElementById('impsave').addEventListener('click', function(){
        var keys = []; out.querySelectorAll('input[type=checkbox]').forEach(function(c){ if (c.checked) keys.push(R.legs[+c.dataset.i].key); });
        if (!keys.length){ say('Nothing ticked - nothing saved.'); return; }
        var W = BS.week, k = 'bs_slips_w' + W, all = []; try{ all = JSON.parse(localStorage.getItem(k) || '[]') || []; }catch(e){ all = []; }
        var od = parseInt(String(document.getElementById('impodds').value || '').replace(/[^0-9+-]/g, ''), 10); if (isNaN(od) || Math.abs(od) < 100) od = R.odds || null;
        all.push({id: 'fd' + Date.now(), name: (document.getElementById('impname').value || 'FanDuel slip').trim().slice(0, 60), keys: keys, odds: od, stake: R.stake || undefined, saved: Date.now(), src: 'fanduel-screenshot'});
        try{ localStorage.setItem(k, JSON.stringify(all)); }catch(e){ say('Your browser would not let us save it (private mode?).'); return; }
        say('<span class="ok">Saved "' + esc(all[all.length-1].name) + '" with ' + keys.length + ' legs.</span> It is in Your record above, graded after the games, and your slip alerts now watch it. <button type="button" class="cta" id="imploaded" style="margin-left:6px;padding:6px 12px;font-size:13px">Load into betslip</button>');
        var lb = document.getElementById('imploaded'); if (lb) lb.addEventListener('click', function(){ loadSlip(BS, keys); });
        document.dispatchEvent(new CustomEvent('bs-account', {detail: {imported: true}})); });
    }
    inp.addEventListener('change', function(){ go(inp.files && inp.files[0]); inp.value = ''; });
    // owner 11/1 "paste import doesn't look like it works": phones only paste into something editable, so the Paste button reads the clipboard
    // directly (Safari shows its own Paste bubble), and when the browser will not allow that it opens a box to long-press and paste into
    var pb = document.getElementById('imppbox'), pbtn = document.getElementById('imppaste');
    function fromImgEl(){ var im = pb && pb.querySelector('img'); if (!im) return false; var src = im.getAttribute('src') || ''; pb.innerHTML = 'Tap and hold here, then tap Paste.';
      if (!/^(data:|blob:)/.test(src)) { say('That paste did not include the picture itself - save the screenshot and use Choose screenshot.'); return true; }
      fetch(src).then(function(r){ return r.blob(); }).then(function(b){ pb.hidden = true; go(b); }).catch(function(){ say('Could not read the pasted picture - use Choose screenshot.'); }); return true; }
    if (pb){ pb.addEventListener('input', function(){ setTimeout(fromImgEl, 50); }); pb.addEventListener('focus', function(){ if (!pb.querySelector('img')) pb.textContent = ''; }); }
    if (pbtn) pbtn.addEventListener('click', function(){
      function box(){ if (!pb) return; pb.hidden = false; pb.textContent = 'Tap and hold here, then tap Paste.'; pb.focus(); }
      if (!(navigator.clipboard && navigator.clipboard.read)) { box(); return; }
      navigator.clipboard.read().then(function(items){ for (var i = 0; i < items.length; i++){ var t = (items[i].types || []).filter(function(x){ return /^image\//.test(x); })[0];
          if (t) return items[i].getType(t).then(function(b){ go(b); }); }
        say('No picture on the clipboard - copy the screenshot first (open it, tap Share, Copy), then tap Paste screenshot.'); })
      .catch(function(){ box(); }); });
    document.addEventListener('paste', function(e){ var it = [].slice.call((e.clipboardData || {}).items || []).filter(function(x){ return /^image\//.test(x.type); })[0]; if (it){ e.preventDefault(); go(it.getAsFile()); } });
    if (location.hash === '#import') card.scrollIntoView({block: 'start'});
  }
  window.BSImport = {parse: parse};
  if (typeof document !== 'undefined') { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup); else setup(); }
})();
