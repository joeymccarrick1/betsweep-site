"""slipclash.py - two lines of one player's market on the same slip (owner 11/24 11:42 PM).

"If I were to add say Matt Stafford +200 from the builder and then add Matt Stafford +275 from the today page, we need to do something
to say that those 2 legs conflict and won't work on FanDuel."

Every page that adds a leg writes the same browser key (bs_slipk_w<week>, keys "player|market|line"): the builder, the boards, Today,
the home page, player pages, Beat the model, Ask, the slip check, Live. Each adds its own leg without looking at the others, so
"Matthew Stafford|Passing Yards|200" and "...|275" can sit side by side - and FanDuel takes one selection per player and market.

One small script, appended to /account.js (which every page loads), so it is the same on every page:
  - it looks at the slip when a page opens, whenever any page writes the slip key (this tab or another), and when the page is shown again;
  - two or more keys with the same player and market (an Under counts as the same market as its Over) = a clash;
  - a bar above the bottom tabs names the player, the market and the lines, says FanDuel will not take both, and offers one button
    per line ("Keep 200+"). Tapping one rewrites the slip without the other line(s) and reloads the page so every panel agrees.
    "Leave both" hides the bar for that pair until the slip changes.
Game lines (Total / Spread / Moneyline) are not judged here. Nothing is removed unless the reader taps a button.
"""

CLASH_JS = r"""
(function(){
  if (window.BSClash) return;
  var RE = /^bs_slipk_w\d+$/, SKIP = /^(Total|Spread|Moneyline)$/, rawSet = Storage.prototype.setItem;
  function slipKey(){ var best = null, bw = -1; try { for (var i = 0; i < localStorage.length; i++){ var k = localStorage.key(i); if (RE.test(k)){ var w = +k.replace('bs_slipk_w', ''); if (w > bw){ bw = w; best = k; } } } } catch(e){} return best; }
  function read(k){ try { var a = JSON.parse(localStorage.getItem(k) || '[]'); return Array.isArray(a) ? a : []; } catch(e){ return []; } }
  function lineText(q){ var m = String(q[1]), ln = q[2]; if (/^Under /.test(m)) return 'under ' + ln; if (/TD$/.test(m)) return m.toLowerCase(); return ln + '+'; }
  function find(keys){ var by = {}, order = [], out = [];
    (keys || []).forEach(function(k){ var q = String(k).split('|'); if (q.length < 3 || !q[0] || SKIP.test(q[1])) return; var b = q[0] + '|' + String(q[1]).replace(/^Under /, '');
      if (!by[b]){ by[b] = []; order.push(b); } if (by[b].map(function(x){ return x.key; }).indexOf(k) < 0) by[b].push({key: k, text: lineText(q)}); });
    order.forEach(function(b){ if (by[b].length > 1){ var q = b.split('|'); out.push({player: q[0], market: q[1], legs: by[b]}); } });
    return out; }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function hushed(c){ try { return sessionStorage.getItem('bs_clash_ok') === c.legs.map(function(l){ return l.key; }).sort().join('~'); } catch(e){ return false; } }
  function bar(){ var el = document.getElementById('bsclash'); if (el) return el;
    el = document.createElement('div'); el.id = 'bsclash'; el.setAttribute('role', 'alert'); el.hidden = true;
    el.style.cssText = 'position:fixed;left:8px;right:8px;bottom:calc(84px + env(safe-area-inset-bottom, 0px));z-index:2147483000;max-width:560px;margin:0 auto;padding:12px 14px;border-radius:14px;border:2px solid var(--bad, #b3261e);background:var(--chalk, #f4efe2);color:var(--ink, #14212e);box-shadow:0 8px 28px rgba(0,0,0,.35);font:500 14px/1.4 var(--body, system-ui, sans-serif)';
    document.body.appendChild(el); return el; }
  function check(){ if (!document.body) return; var k = slipKey(), cs = k ? find(read(k)).filter(function(c){ return !hushed(c); }) : [], el = document.getElementById('bsclash');
    if (!cs.length){ if (el) el.hidden = true; return; }
    var c = cs[0]; el = bar();
    var btn = 'font:700 13px/1 var(--display, system-ui, sans-serif);letter-spacing:.03em;padding:10px 12px;border-radius:10px;border:1px solid var(--line, #c9c2ae);background:var(--ink, #14212e);color:var(--chalk, #f4efe2);cursor:pointer';
    el.innerHTML = '<b style="display:block;font:700 15px/1.25 var(--display, system-ui, sans-serif);margin-bottom:4px">Two lines for the same bet</b>'
      + '<span>' + esc(c.player) + ' ' + esc(c.market.toLowerCase()) + ' is on your slip ' + (c.legs.length === 2 ? 'twice' : c.legs.length + ' times') + ' (' + c.legs.map(function(l){ return esc(l.text); }).join(' and ') + '). FanDuel takes one line per player and market, so its betslip will not accept both.</span>'
      + '<span style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">' + c.legs.map(function(l, i){ return '<button type="button" data-keep="' + i + '" style="' + btn + '">Keep ' + esc(l.text) + '</button>'; }).join('')
      + '<button type="button" data-keep="all" style="' + btn + ';background:transparent;color:var(--ink, #14212e)">Leave both</button></span>';
    el.hidden = false;
    el.onclick = function(ev){ var t = ev.target && ev.target.closest ? ev.target.closest('button[data-keep]') : null; if (!t) return; var v = t.getAttribute('data-keep');
      if (v === 'all'){ try { sessionStorage.setItem('bs_clash_ok', c.legs.map(function(l){ return l.key; }).sort().join('~')); } catch(e){} check(); return; }
      var keep = c.legs[+v].key, drop = c.legs.map(function(l){ return l.key; }).filter(function(x){ return x !== keep; }), now = read(k).filter(function(x){ return drop.indexOf(x) < 0; });
      try { rawSet.call(localStorage, k, JSON.stringify(now)); localStorage.removeItem(k.replace('bs_slipk_w', 'bs_slip_w')); } catch(e){}
      el.hidden = true; setTimeout(function(){ location.reload(); }, 60); }; }
  var timer = null; function soon(){ clearTimeout(timer); timer = setTimeout(check, 30); }
  try { Storage.prototype.setItem = function(k, v){ var r = rawSet.apply(this, arguments); if (RE.test(String(k))) soon(); return r; }; } catch(e){}
  window.addEventListener('storage', function(e){ if (!e.key || RE.test(e.key)) soon(); });
  window.addEventListener('pageshow', soon);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', soon); else soon();
  window.BSClash = {find: find, check: check};
})();
"""
