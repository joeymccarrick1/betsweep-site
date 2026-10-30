
(function(){
  var wk = document.querySelector('[data-week]'), W = wk ? +wk.getAttribute('data-week') : 0; if(!W) return;
  var KEY = 'bs_slipk_w' + W;
  function get(){ try{ var a = JSON.parse(localStorage.getItem(KEY) || '[]'); return Array.isArray(a) ? a : []; }catch(e){ return []; } }
  function put(a){ try{ localStorage.setItem(KEY, JSON.stringify(a)); }catch(e){} }
  var bar = document.getElementById('ppbar');
  function paint(){ var a = get(), m = {}; a.forEach(function(k){ m[k] = 1; });
    document.querySelectorAll('.pp .add[data-k]').forEach(function(b){ var on = !!m[b.getAttribute('data-k')]; b.classList.toggle('in', on); b.textContent = on ? '✓' : '+'; b.setAttribute('aria-pressed', on ? 'true' : 'false'); });
    if(bar){ bar.classList.toggle('on', a.length > 0); var n = bar.querySelector('b'); if(n) n.textContent = a.length + (a.length === 1 ? ' leg' : ' legs') + ' in your slip'; } }
  document.querySelectorAll('.pp .add[data-k]').forEach(function(b){
    var ko = +b.getAttribute('data-ko') || 0; if(ko && Date.now() >= ko){ b.disabled = true; b.title = 'This game has kicked off'; return; }
    b.addEventListener('click', function(){ var k = b.getAttribute('data-k'), a = get(), i = a.indexOf(k); if(i >= 0) a.splice(i, 1); else a.push(k); put(a); paint(); }); });
  window.addEventListener('storage', paint); paint();
  // directory filter
  var q = document.getElementById('pdq'); if(!q) return;
  var items = [].slice.call(document.querySelectorAll('.pd li')), pos = 'ALL', cnt = document.getElementById('pdcnt');
  function f(){ var s = q.value.trim().toLowerCase(), n = 0; items.forEach(function(li){ var ok = (pos === 'ALL' || li.getAttribute('data-pos') === pos) && (!s || li.getAttribute('data-s').indexOf(s) >= 0); li.hidden = !ok; if(ok) n++; }); if(cnt) cnt.textContent = n + ' players'; }
  q.addEventListener('input', f);
  document.querySelectorAll('.pd .pos button').forEach(function(b){ b.addEventListener('click', function(){ pos = b.getAttribute('data-p'); document.querySelectorAll('.pd .pos button').forEach(function(x){ x.classList.toggle('on', x === b); }); f(); }); });
  try{ var h = new URLSearchParams(location.search).get('q'); if(h){ q.value = h; } }catch(e){}
  f();
})();
