"""slipimport.py - Import a FanDuel betslip from a screenshot (owner 11/1: "Could they copy and paste a picture of their betslip and it get
imported as a saved slip in my betsweep?").

The /me/ page gets an "Import a FanDuel slip" card. The visitor picks or pastes a screenshot of a FanDuel betslip (the slip itself, a shared
slip, or a bet under My Bets). Everything happens in their browser: the picture is cleaned up on a canvas (brightest colour channel, dark
themes inverted, small shots doubled, thresholded - FanDuel's blue leg titles on its dark slip vanish in a plain greyscale), read with
tesseract.js (loaded from jsdelivr only when someone imports), and the text is matched leg by leg against this week's Parlay Builder data:

  "Caleb Douglas 30+ Yards" + "CALEB DOUGLAS - ALT RECEIVING YDS"      -> Caleb Douglas | Receiving Yards | 30
  "Quinshon Judkins Over +1.5" + "... - TOTAL RECEPTIONS"              -> Quinshon Judkins | Receptions | 2
  "Ladd McConkey Under 47.5" + "... - RECEIVING YDS"                    -> Ladd McConkey | Under Receiving Yards | 48
  "Jahmyr Gibbs" + "ANY TIME TOUCHDOWN SCORER"                          -> Jahmyr Gibbs | Anytime TD | 1   (FIRST TOUCHDOWN SCORER -> First TD)
  "Tre Tucker or Brock Bowers" + "EITHER PLAYER - ANYTIME TOUCHDOWN"    -> Tre Tucker or Brock Bowers | Either TD | 1
  "Detroit Lions" + "MONEYLINE" / "Detroit Lions -3.5" + "SPREAD" / "Over 46.5" + "TOTAL POINTS" -> the builder's game-line legs

Keys are the builder's own (legKey: player|market|Math.round(line)), so an imported slip is graded on /me/, counted in exposure and watched
by the slip alerts like any slip saved in the builder. Drive props and anything else we do not price are listed as "not imported".
The header odds ("7 Leg Parlay +2002") and the wager ("$10.00 TOTAL WAGER") are kept when the screenshot shows them.
Parser tested against the owner's own FanDuel screenshots (5-, 6-, 7-, 11- and 18-leg slips and a My Bets card) through tesseract 5.
"""

IMPORT_CSS = r"""
#import .imp{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-top:8px}
#import .imp label.cta{cursor:pointer}
#impout{margin-top:12px}
#impout .st{font-size:13px;color:var(--mute)}
#impout ul{list-style:none;margin:8px 0;padding:0;display:grid;gap:6px}
#impout li{display:flex !important;flex-direction:row !important;flex-wrap:nowrap !important;gap:10px;align-items:flex-start;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:14px;line-height:1.35}
#impout li>span{flex:1;min-width:0;display:block}
#impout li input{flex:0 0 auto}
#impout li input{margin-top:3px}
#impout li small{display:block;color:var(--mute);font-size:12px}
#impout li.no{opacity:.7;border-style:dashed}
#impout .row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:8px}
#impout .row input[type=text]{flex:1;min-width:180px;font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}
#impout .ok{color:var(--good)} #impout .warn{color:#b7791f}
#impout .impb{margin:10px 0;padding:10px 12px;border:1px solid var(--line);border-radius:10px} #impout .impb.one{margin:0;padding:0;border:0}
#impout .impb.no{border-style:dashed;color:var(--mute);font-size:14px} #impout .impb.no small{display:block;font-size:12.5px;margin-top:2px}
#impout .imph{display:flex;align-items:center;gap:9px;font-size:15px;cursor:pointer;min-height:34px;color:var(--ink)} #impout .imph input{width:18px;height:18px;flex:none}
#impout .impb .st{margin:2px 0 4px} #impout .impb small.dup{display:block;font-size:12.5px;margin:0 0 6px}
#impout details summary{cursor:pointer;font-size:13px;font-weight:600;color:var(--mute);padding:7px 0}
#impout .impsec{font:inherit;font-weight:700;padding:9px 14px;border-radius:8px;border:1px solid var(--line);background:none;color:var(--ink);cursor:pointer}
#impout .impact{margin-top:10px} #impout .impnote:empty{display:none} #impout button[disabled]{opacity:.5;cursor:default}
#impout .impdone li{flex-wrap:wrap !important;align-items:center} #impout .impdone li>span:first-child{flex:1 0 100%} #impout .impdone li>.impdo{flex:1 1 100%;min-width:0;display:flex;gap:8px;flex-wrap:wrap} #impout .impdone .psn{flex:1 0 100%;margin-top:4px}
#impout button.cta{border:0;font:inherit;font-weight:700;cursor:pointer} #impout .impdone .impdo button{flex:1 1 0;min-width:0;padding:10px 6px;font-size:14px;white-space:nowrap;border-radius:8px}
.me button.ldb{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:12px;letter-spacing:.06em;text-transform:uppercase;background:none;color:var(--ink);border:1px solid var(--line);padding:3px 9px;border-radius:4px;margin-left:6px;cursor:pointer}
"""

IMPORT_JS = r"""(function(){
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
    var used = {}, hdr = '';
    L.forEach(function(s, i){
      if (/ @ /.test(s)) hdr = s;   // 11/14: the game header sits above its legs; a total must come from that game, not the first "Over 40.5" on the board
      var m = descriptor(s); if (m === undefined) return;
      // the title: the nearest line above with real words (skip lone odds / icon noise and the game line)
      var t = '', j = i - 1; while (j >= 0 && j >= i - 3){ var c = L[j]; if (c.replace(/[^A-Za-z]/g, '').length >= 4 && !/ @ /.test(c) && descriptor(c) === undefined && !used[j]){ t = c; used[j] = 1; break; } j--; }
      var game = (L[i+1] && / @ /.test(L[i+1])) ? L[i+1] : hdr;
      var odds = oddsIn(t) || oddsIn(s) || (L[i-1] && /^[+\-−~“"]?\d{3,6}$/.test(L[i-1]) ? oddsIn(L[i-1]) : null);
      var title = t.replace(/\s*[+\-−~“"]?\d{3,6}\s*$/, '');
      var raw = (title || s).replace(/^[^A-Za-z]*(?:[A-Za-z]{1,2}[^A-Za-z]+)?/, '');
      if (m === null){ out.legs.push({ok: false, raw: raw, why: 'drive / quarter props are not priced on BetSweep'}); return; }
      if (m === 'Either TD'){ var two = title.split(/\s+or\s+/i); var a = two[0] && matchName(two[0], P), b = two[1] && matchName(two[1], P);
        if (a && b) out.legs.push({ok: true, key: a + ' or ' + b + '|Either TD|1', label: a + ' or ' + b + ' anytime TD', odds: odds});
        else out.legs.push({ok: false, raw: raw, why: 'could not read both names'}); return; }
      if (m === 'Moneyline' || m === 'Spread' || m === 'Total'){
        var gl = legs.filter(function(l){ return l.gl && l.m === m; }), hit = null;
        var inGame = function(l){ return !game || game.indexOf(NICK[l.g.split('-')[0]] || '~') >= 0 || game.indexOf(NICK[l.g.split('-')[1]] || '~') >= 0; };
        if (m === 'Total'){ var tm = title.match(/(Over|Under)\s*\(?\s*\+?(\d+(?:\.\d+)?)/i); if (tm){ var pl = tm[1][0].toUpperCase() + tm[1].slice(1).toLowerCase() + ' ' + (+tm[2]);
            hit = gl.filter(function(l){ return l.pl === pl && inGame(l); })[0]; } }
        else { var ab = Object.keys(NICK).filter(function(k){ return title.indexOf(NICK[k]) >= 0; })[0];
          if (ab){ if (m === 'Moneyline') hit = gl.filter(function(l){ return l.pl === NICK[ab] + ' ML'; })[0];
            else { var tt2 = title.replace(/[−–—~]/g, '-'), sp = tt2.match(/\(\s*([+-]?)\s*(\d+(?:\.\d+)?)\s*\)/) || tt2.match(/([+-]?)\s*(\d+(?:\.\d+)?)\s*$/);   // 11/14: the bracketed number wins wherever it sits - the odds after it can read as junk ("(+2.5) 1M" was -111)
              if (sp){ var num = +sp[2], cand = sp[1] ? [sp[1] + num] : ['+' + num, '-' + num];   // sign lost in the read: whichever of the two this team has
                hit = gl.filter(function(l){ return cand.some(function(c){ return l.pl === ab + ' ' + c; }) && inGame(l); })[0]; } } } }
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
  // 11/14: a total's key has no game in it ("Over 49.5|Total|50" is a line in several games), so the builder also reads bs_slipg_w<W>
  // ({key: [gid, ...]} in slip order) to put each one back in its own game. The importer never wrote it, so every imported total opened
  // in the first game with that number (owner's 12-leg slip: seven totals all came back as DET-NE). gmapOf builds it from the matched legs.
  function gmapOf(BS, legs){ var n = {}; (BS.legs || []).forEach(function(l){ var k = legKey(l); (n[k] = n[k] || {})[l.g] = 1; });
    var g = {}; legs.forEach(function(x){ if (x && x.key && x.leg && x.leg.g && n[x.key] && (Object.keys(n[x.key]).length > 1 || x.leg.m === 'Total')) (g[x.key] = g[x.key] || []).push(x.leg.g); }); return g; }
  function loadSlip(BS, keys, gm){
    var W = BS.week, have = {}; (BS.legs || []).forEach(function(l){ have[legKey(l)] = 1; });
    var on = keys.filter(function(k){ return have[k]; }), off = keys.length - on.length;
    try{ localStorage.setItem('bs_slipg_w' + W, JSON.stringify(gm || {}));   /* 11/15: never removeItem here - a removal undone by the account sync reloaded the page in a loop */ }catch(e){}
    try{ localStorage.setItem('bs_slipk_w' + W, JSON.stringify(on)); if (off) sessionStorage.setItem('bs_impnote', off + ' leg' + (off === 1 ? '' : 's') + ' from your FanDuel slip ' + (off === 1 ? 'is' : 'are') + ' not on the builder board (games already under way, either-player TDs or lines we do not price) - ' + (off === 1 ? 'it stays' : 'they stay') + ' on the saved slip.'); }catch(e){}
    location.href = '/build/#slip'; }
  window.BSLoadSlip = function(keys, gm){ return builderData().then(function(BS){ loadSlip(BS, keys, gm); }); };
  // ---- the card on /me/ ----
  function am(o){ o = +o; return isNaN(o) || !o ? '' : (o > 0 ? '+' + o : String(o)); }
  function setup(){
    var card = document.getElementById('import'); if (!card) return; var out = document.getElementById('impout'), inp = card.querySelector('input[type=file]');
    // owner 11/22 2:09 AM ("batch import multiple slips to save multiple betslips all at once"): PEND is the queue of screenshots read
    // and not saved yet. Several pictures can be chosen at once, or added one after another (a phone pastes one picture at a time);
    // one picture looks and works as it always has, two or more get a block each and a single "Save N slips" button.
    var PEND = [], MAXB = 12, busy = false, DONE = {}, DONEBS = null;
    function say(h){ out.innerHTML = '<p class="st">' + h + '</p>'; }
    function note(h){ var n = out.querySelector('.impnote'); if (n) n.innerHTML = h; else say(h); }
    function board(){ var BS = null; PEND.forEach(function(x){ if (x.BS) BS = x.BS; }); return BS; }
    // one picture that never comes back must not jam the queue: 90 seconds, then it counts as unreadable and the next one is read
    function readT(f){ return new Promise(function(res, rej){ var over = 0, t = setTimeout(function(){ if (!over){ over = 1; rej(new Error('the reader took too long')); } }, 90000);
      window.BSImport.read(f).then(function(r){ if (!over){ over = 1; clearTimeout(t); res(r); } }, function(e){ if (!over){ over = 1; clearTimeout(t); rej(e); } }); }); }
    var WAIT = [];   // pictures that arrive while others are being read wait their turn
    function go(files){ files = (files && typeof files.length === 'number' ? [].slice.call(files) : [files]).filter(Boolean); if (!files.length) return;
      if (busy){ WAIT = WAIT.concat(files); return; }
      sync(); var room = Math.max(0, MAXB - PEND.length), cut = files.length > room; files = files.slice(0, room);
      if (!files.length){ render('That is ' + MAXB + ' screenshots, the most that are read in one go. Save these, then add the rest.'); return; }
      busy = true; var i = 0, n = files.length;
      (function next(){
        if (i >= n){ busy = false; render(cut ? 'Only the first ' + MAXB + ' screenshots were read. Save these, then add the rest.' : ''); if (WAIT.length){ var w = WAIT; WAIT = []; go(w); } return; }
        say('Reading ' + (n > 1 ? 'slip ' + (i + 1) + ' of ' + n : 'your slip') + '… (the first time takes a few seconds to load the reader)');
        readT(files[i]).then(function(r){ PEND.push({R: r.R, BS: r.BS}); }, function(e){ PEND.push({err: String((e && e.message) || e || 'unknown')}); }).then(function(){ i++; next(); });
      })(); }
    function legRow(l, i, off){ return l.ok ? '<li><input type="checkbox"' + (off ? '' : ' checked') + ' data-i="' + i + '"><span>' + esc(l.label) + (l.odds ? ' <b>' + am(l.odds) + '</b>' : '') +
        '<small class="' + (l.unpriced ? 'warn' : 'ok') + '">' + (l.unpriced ? 'saved and graded - not on our board at this exact line, so no model price' : 'matched to this week\'s board') + '</small></span></li>'
      : '<li class="no"><span>✗ ' + esc(l.raw) + '<small>' + esc(l.why) + ' - not imported</small></span></li>'; }
    // what is typed and ticked survives a repaint (another screenshot arriving)
    function sync(){ out.querySelectorAll('.impb[data-n]').forEach(function(b){ var x = PEND[+b.dataset.n]; if (!x) return; var on = b.querySelector('.impon'); if (on) x.inc = on.checked;
      x.nm = b.querySelector('.impname').value; x.od = b.querySelector('.impodds').value; x.un = {}; b.querySelectorAll('li input[type=checkbox]').forEach(function(c){ if (!c.checked) x.un[c.dataset.i] = 1; }); var d = b.querySelector('details'); x.open = !!(d && d.open); }); }
    function picked(b){ var x = PEND[+b.dataset.n], ls = []; b.querySelectorAll('li input[type=checkbox]').forEach(function(c){ if (c.checked) ls.push(x.R.legs[+c.dataset.i]); }); return ls; }
    function count(){ var sb = document.getElementById('impsaveall'); if (!sb) return; var n = 0; out.querySelectorAll('.impb[data-n]').forEach(function(b){ var on = b.querySelector('.impon'); if ((!on || on.checked) && picked(b).length) n++; });
      sb.textContent = 'Save ' + (n === 1 ? '1 slip' : n + ' slips'); sb.disabled = !n; }
    function render(msg){
      if (!PEND.length){ out.innerHTML = msg ? '<p class="st">' + msg + '</p>' : ''; return; }
      var many = PEND.length > 1, BS = board();
      if (!many){ var x0 = PEND[0], g0 = x0.R ? x0.R.legs.filter(function(l){ return l.ok; }) : [];   // one picture that came to nothing: the answers this card has always given
        if (x0.err){ PEND = []; say('Could not read that picture (' + esc(x0.err) + '). Try a full, uncropped screenshot of the slip.'); return; }
        if (!x0.R.legs.length){ PEND = []; say('No FanDuel legs found in that picture. Use a screenshot of the betslip or of the bet under My Bets, with the leg names showing.'); return; }
        if (!g0.length){ PEND = []; out.innerHTML = '<p class="st">Found 0 of ' + x0.R.legs.length + ' legs.</p><ul>' + x0.R.legs.map(function(l, i){ return legRow(l, i); }).join('') + '</ul><p class="st">None of these legs are markets BetSweep prices, so there is nothing to save. Player yards, catches, touchdowns and game lines import fine.</p>'; return; } }
      var have = []; try{ have = JSON.parse(localStorage.getItem('bs_slips_w' + (BS ? BS.week : 0)) || '[]') || []; }catch(e){ have = []; }
      var seen = {}; have.forEach(function(s){ if (s && s.keys) seen[s.keys.slice().sort().join('||')] = '"' + (s.name || 'a saved slip') + '", which is already saved'; });
      var h = '';
      PEND.forEach(function(x, n){
        var legs = x.R ? x.R.legs : [], good = legs.filter(function(l){ return l.ok; });
        if (x.err || !good.length){ h += '<div class="impb no"><b>Screenshot ' + (n + 1) + '</b><small>' + (x.err ? 'could not be read - try a full, uncropped screenshot of the slip' : !legs.length ? 'no FanDuel legs found in it' : 'none of its legs are markets BetSweep prices') + ' - not imported</small></div>'; return; }
        var sg = good.map(function(l){ return l.key; }).sort().join('||'), dup = seen[sg] || null; if (!dup) seen[sg] = 'screenshot ' + (n + 1);
        if (x.inc == null) x.inc = !dup;
        var odd = legs.length - good.length + good.filter(function(l){ return l.unpriced; }).length, dn = 'FanDuel ' + good.length + '-leg' + (x.R.odds ? ' ' + am(x.R.odds) : '');
        h += '<div class="impb' + (many ? '' : ' one') + '" data-n="' + n + '">' + (many ? '<label class="imph"><input type="checkbox" class="impon"' + (x.inc ? ' checked' : '') + '><b>Screenshot ' + (n + 1) + '</b></label>' : '') +
          '<p class="st">Found ' + good.length + ' of ' + legs.length + ' legs' + (x.R.odds ? ' · FanDuel ' + am(x.R.odds) : '') + '.' + (many ? '' : ' Untick anything that is wrong.') + '</p>' +
          (dup ? '<small class="warn dup">Same legs as ' + esc(dup) + (many ? ' - left out unless you tick it.' : '.') + '</small>' : '') +
          (many ? '<details' + (odd || x.open || (x.un && Object.keys(x.un).length) ? ' open' : '') + '><summary>Check the legs</summary>' : '') + '<ul>' + legs.map(function(l, i){ return legRow(l, i, x.un && x.un[i]); }).join('') + '</ul>' + (many ? '</details>' : '') +
          '<div class="row"><input type="text" class="impname"' + (many ? '' : ' id="impname"') + ' maxlength="60" aria-label="Slip name" value="' + esc(x.nm != null ? x.nm : dn) + '"><input type="text" class="impodds"' + (many ? '' : ' id="impodds"') + ' inputmode="text" maxlength="9" aria-label="FanDuel odds" style="flex:0 0 110px;min-width:0" placeholder="Odds +650" value="' + esc(x.od != null ? x.od : (x.R.odds ? am(x.R.odds) : '')) + '"></div></div>'; });
      h += '<p class="st impnote" aria-live="polite">' + (msg || '') + '</p><div class="row impact">' +
        (many ? '<button type="button" class="cta" id="impsaveall">Save slips</button>' : '<button type="button" class="cta" id="impsave">Save slip</button><button type="button" class="impsec" id="impload">Load into betslip</button>') +
        '<button type="button" class="impsec" id="impmore">Add another screenshot</button><button type="button" class="impsec" id="impclear">Clear</button></div>';
      out.innerHTML = h; count(); }
    function saveAll(){
      var BS = board(); if (!BS) return; var W = BS.week, k = 'bs_slips_w' + W, all = []; try{ all = JSON.parse(localStorage.getItem(k) || '[]') || []; }catch(e){ all = []; }
      var t0 = Date.now(), saved = [];
      out.querySelectorAll('.impb[data-n]').forEach(function(b){ var on = b.querySelector('.impon'); if (on && !on.checked) return; var x = PEND[+b.dataset.n], tl = picked(b); if (!tl.length) return;
        var od = parseInt(String(b.querySelector('.impodds').value || '').replace(/[^0-9+-]/g, ''), 10); if (isNaN(od) || Math.abs(od) < 100) od = x.R.odds || null;
        var e = {id: 'fd' + (t0 + saved.length), name: (b.querySelector('.impname').value || 'FanDuel slip').trim().slice(0, 60), keys: tl.map(function(l){ return l.key; }), g: gmapOf(BS, tl), odds: od, stake: x.R.stake || undefined, saved: t0, src: 'fanduel-screenshot'};
        all.push(e); saved.push(e); });
      if (!saved.length){ note('Nothing ticked - nothing saved.'); return; }
      try{ localStorage.setItem(k, JSON.stringify(all)); }catch(e){ note('Your browser would not let us save ' + (saved.length === 1 ? 'it' : 'them') + ' (private mode?).'); return; }
      PEND = []; DONE = {}; DONEBS = BS; saved.forEach(function(e){ DONE[e.id] = e; });
      var one = saved.length === 1;
      out.innerHTML = '<p class="st"><span class="ok">Saved ' + (one ? '"' + esc(saved[0].name) + '" with ' + saved[0].keys.length + ' legs' : saved.length + ' slips') + '.</span> ' + (one ? 'It is' : 'They are') + ' in Your record above, graded after the games, and your slip alerts now watch ' + (one ? 'it' : 'them') + '.</p><ul class="impdone">' +
        saved.map(function(e){ return '<li><span><b>' + esc(e.name) + '</b><small>' + e.keys.length + ' leg' + (e.keys.length === 1 ? '' : 's') + (e.odds ? ' · ' + am(e.odds) : '') + '</small></span><span class="impdo"><button type="button" class="impsec" data-load="' + esc(e.id) + '">Load into betslip</button><button type="button" class="cta" data-psb data-w="' + W + '" data-id="' + esc(e.id) + '">Post to Social</button></span></li>'; }).join('') + '</ul>';
      document.dispatchEvent(new CustomEvent('bs-account', {detail: {imported: true}})); }
    out.addEventListener('change', function(e){ if (e.target && e.target.type === 'checkbox') count(); });
    out.addEventListener('click', function(e){ var t = e.target.closest && e.target.closest('button'); if (!t) return;
      if (t.id === 'impmore'){ inp.click(); return; }
      if (t.id === 'impclear'){ PEND = []; out.innerHTML = ''; return; }
      if (t.id === 'impsave' || t.id === 'impsaveall'){ saveAll(); return; }
      if (t.id === 'impload'){ var b = out.querySelector('.impb[data-n]'), ls = b ? picked(b) : []; if (!ls.length){ note('Nothing ticked - nothing to load.'); return; } var BS = board(); loadSlip(BS, ls.map(function(x){ return x.key; }), gmapOf(BS, ls)); return; }
      var d = t.getAttribute('data-load'); if (d && DONE[d] && DONEBS) loadSlip(DONEBS, DONE[d].keys, DONE[d].g); });
    inp.addEventListener('change', function(){ var fs = [].slice.call(inp.files || []); inp.value = ''; go(fs); });
    // owner 11/1 "paste import doesn't look like it works": phones only paste into something editable, so the Paste button reads the clipboard
    // directly (Safari shows its own Paste bubble), and when the browser will not allow that it opens a box to long-press and paste into
    var pb = document.getElementById('imppbox'), pbtn = document.getElementById('imppaste');
    function fromImgEl(){ var ims = pb ? [].slice.call(pb.querySelectorAll('img')) : []; if (!ims.length) return false; var srcs = ims.map(function(im){ return im.getAttribute('src') || ''; }).filter(function(u){ return /^(data:|blob:)/.test(u); }); pb.innerHTML = 'Tap and hold here, then tap Paste.';
      if (!srcs.length) { say('That paste did not include the picture itself - save the screenshot and use Choose screenshots.'); return true; }
      Promise.all(srcs.map(function(u){ return fetch(u).then(function(r){ return r.blob(); }); })).then(function(bs){ pb.hidden = true; go(bs); }).catch(function(){ say('Could not read the pasted picture - use Choose screenshots.'); }); return true; }
    if (pb){ pb.addEventListener('input', function(){ setTimeout(fromImgEl, 50); }); pb.addEventListener('focus', function(){ if (!pb.querySelector('img')) pb.textContent = ''; }); }
    if (pbtn) pbtn.addEventListener('click', function(){
      function box(){ if (!pb) return; pb.hidden = false; pb.textContent = 'Tap and hold here, then tap Paste.'; pb.focus(); }
      if (!(navigator.clipboard && navigator.clipboard.read)) { box(); return; }
      navigator.clipboard.read().then(function(items){ var ps = []; for (var i = 0; i < items.length; i++){ var t = (items[i].types || []).filter(function(x){ return /^image\//.test(x); })[0]; if (t) ps.push(items[i].getType(t)); }
        if (ps.length) return Promise.all(ps).then(function(bs){ go(bs); });
        note('No picture on the clipboard - copy the screenshot first (open it, tap Share, Copy), then tap Paste screenshot.'); })
      .catch(function(){ box(); }); });
    document.addEventListener('paste', function(e){ var fs = [].slice.call((e.clipboardData || {}).items || []).filter(function(x){ return /^image\//.test(x.type); }).map(function(x){ return x.getAsFile(); }).filter(Boolean); if (fs.length){ e.preventDefault(); go(fs); } });
    if (location.hash === '#import') card.scrollIntoView({block: 'start'});
  }
  // owner 11/10 "Sweep my slip" (/sweep/): the same reader for another page - picture in, {R: parsed legs, BS: this week's board} out
  window.BSImport = {parse: parse, data: builderData, gmap: gmapOf, read: function(file){
    return Promise.all([builderData(), loadTess().then(function(T){ return prep(file).then(function(c){ return T.recognize(c, 'eng', {tessedit_pageseg_mode: '4'}); }); })])
      .then(function(r){ return {R: parse(r[1].data.text || '', r[0]), BS: r[0]}; }); }};
  if (typeof document !== 'undefined') { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', setup); else setup(); }
})();
"""

CARD_HTML = ('<div class="card" id="import" data-def="open"><h2>Import a FanDuel slip</h2><p class="m">Took the bet on FanDuel? Screenshot the betslip (or the bet under '
             'My Bets), then choose the picture here or paste it - several at once is fine, and one button saves them all. Your phone reads them; '
             'the pictures never leave this device. Each slip is graded after the games, counted in your exposure and watched by your slip alerts.</p>'
             '<div class="imp"><label class="cta">Choose screenshots<input type="file" accept="image/*" multiple hidden></label><button type="button" class="cta" id="imppaste" style="background:none;color:var(--ink);border:1px solid var(--line)">Paste screenshot</button></div><div id="imppbox" contenteditable="true" hidden aria-label="Paste your screenshot here" style="margin-top:10px;min-height:64px;padding:12px;border:2px dashed var(--line);border-radius:10px;color:var(--mute);font-size:14px;line-height:1.4">Tap and hold here, then tap Paste.</div>'
             '<div id="impout"></div></div>')
