#!/usr/bin/env python3
"""build_slipcheck.py - "Sweep my slip" (owner 11/10: "I'd love for us to start 1-3"): the front door at /sweep/.

A visitor uploads or pastes a screenshot of ANY FanDuel slip - his own or one somebody posted. The picture is read on his device by
the same reader /me/ uses (import.js, slipimport.py: tesseract in the browser, legs matched against this week's board); nothing is
uploaded. The legs go into the betslip and the Parlay Builder opens with the verdict showing (build_builder.py sweepBlock): the
slip's chance against its price, how many legs are low risk, the weakest leg, and a safer swap one tap applies. Legs we do not price
are named on the verdict, never guessed at.

Writes out/slipcheck.html (placed at /sweep/ by build_site.py). No data of its own - the page reads the board the builder publishes.
"""
import os, html
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
CSS = """
.sc{max-width:720px;margin:18px auto 40px}
.sc h1{font-family:var(--brand);font-style:italic;font-weight:800;font-size:36px;line-height:1;margin:0 0 8px;letter-spacing:-.01em}
.sc .lead{color:var(--mute);line-height:1.5;margin:0 0 16px;font-size:15.5px}
.sc .drop{border:2px dashed color-mix(in srgb,var(--red) 55%,var(--line));border-radius:16px;background:var(--card);padding:22px 18px;text-align:center}
.sc .drop.over{border-style:solid}
.sc .btns{display:flex;flex-wrap:wrap;gap:10px;justify-content:center}
.sc .cta{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:0 20px;border-radius:10px;border:2px solid var(--red);background:var(--red);color:#fff;font-family:var(--display);font-weight:800;font-size:15px;letter-spacing:.06em;text-transform:uppercase;cursor:pointer;text-decoration:none}
.sc .cta.alt{background:none;color:var(--ink);border-color:var(--line)}
.sc .hint{color:var(--mute);font-size:13px;line-height:1.5;margin:12px 0 0}
.sc #scpbox{margin:12px auto 0;max-width:420px;min-height:54px;border:1.5px solid var(--line);border-radius:10px;padding:14px;color:var(--mute);font-size:14px}
.sc #scout{margin-top:14px;font-size:14.5px;line-height:1.5;text-align:left}
.sc #scout .ok{color:var(--good)} .sc #scout .no{color:var(--mute)}
.sc #scout ul{margin:8px 0 0;padding-left:18px} .sc #scout li{margin:3px 0}
.sc .steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:18px 0 0}
.sc .steps div{border:1px solid var(--line);border-radius:12px;padding:12px 14px;background:var(--card)}
.sc .steps b{display:block;font-family:var(--display);font-weight:800;font-size:13px;letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px}
.sc .steps span{color:var(--mute);font-size:13.5px;line-height:1.45}
.sc .fn{color:var(--mute);font-size:12.5px;line-height:1.5;margin-top:16px} .sc .fn a{color:var(--ink)}
"""
JS = r"""
(function(){
  var out = document.getElementById('scout'), drop = document.getElementById('scdrop'), inp = document.getElementById('scfile'), pb = document.getElementById('scpbox'), busy = false;
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function say(h){ out.innerHTML = h; }
  function go(file){
    if(!file || busy) return; if(!window.BSImport || !window.BSImport.read){ say('The reader did not load. Check your connection and reload the page.'); return; }
    busy = true; say('Reading the slip… the first time takes a few seconds.');
    window.BSImport.read(file).then(function(x){ busy = false; var R = x.R, BS = x.BS, W = BS.week;
      var good = R.legs.filter(function(l){ return l.ok && !l.unpriced; }), off = R.legs.filter(function(l){ return !l.ok || l.unpriced; });
      if(!R.legs.length){ say('No FanDuel legs found in that picture. Use a full screenshot of the betslip, or of the bet under My Bets, with the leg names showing.'); return; }
      if(!good.length){ say('<span class="no">Read ' + R.legs.length + ' leg' + (R.legs.length === 1 ? '' : 's') + ', but none is on this week’s board, so there is nothing to price.</span><ul>' + off.slice(0, 8).map(function(l){ return '<li class="no">' + esc(l.label || l.raw) + (l.why ? ' – ' + esc(l.why) : '') + '</li>'; }).join('') + '</ul>'); return; }
      var keys = good.map(function(l){ return l.key; }), cur = [];
      try { cur = JSON.parse(localStorage.getItem('bs_slipk_w' + W) || '[]') || []; } catch(e){ cur = []; }
      var same = cur.length === keys.length && cur.slice().sort().join('~') === keys.slice().sort().join('~');
      if(cur.length && !same && !window.confirm('This replaces the ' + cur.length + ' leg' + (cur.length === 1 ? '' : 's') + ' in your betslip with the ' + keys.length + ' from the picture. Go ahead?')){ say('Left your betslip alone.'); return; }
      try { localStorage.setItem('bs_slipk_w' + W, JSON.stringify(keys));
            sessionStorage.setItem('bs_sweep', JSON.stringify({k: keys.slice().sort().join('~'), odds: R.odds || null, stake: R.stake || null, off: off.map(function(l){ return l.label || l.raw || 'a leg we could not read'; }), n: R.legs.length})); }
      catch(e){ say('Your browser would not let us keep the slip (private mode?).'); return; }
      say('<span class="ok">Read ' + good.length + ' of ' + R.legs.length + ' legs.</span> Opening the verdict…'); location.href = '/build/?sweep=1#slip';
    }).catch(function(e){ busy = false; say('Could not read that picture (' + esc((e && e.message) || e) + '). Try a full, uncropped screenshot of the slip.'); });
  }
  inp.addEventListener('change', function(){ go(inp.files && inp.files[0]); inp.value = ''; });
  ['dragenter', 'dragover'].forEach(function(t){ drop.addEventListener(t, function(e){ e.preventDefault(); drop.classList.add('over'); }); });
  ['dragleave', 'drop'].forEach(function(t){ drop.addEventListener(t, function(e){ e.preventDefault(); drop.classList.remove('over'); }); });
  drop.addEventListener('drop', function(e){ var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]; if(f) go(f); });
  document.addEventListener('paste', function(e){ var it = [].slice.call((e.clipboardData || {}).items || []).filter(function(x){ return /^image\//.test(x.type); })[0]; if(it){ e.preventDefault(); go(it.getAsFile()); } });
  // phones only paste into something editable: read the clipboard directly, else open a box to long-press and paste into (same as /me/)
  function fromBox(){ var im = pb.querySelector('img'); if(!im) return; var src = im.getAttribute('src') || ''; pb.innerHTML = 'Tap and hold here, then tap Paste.';
    if(!/^(data:|blob:)/.test(src)){ say('That paste did not include the picture itself. Save the screenshot and use Choose screenshot.'); return; }
    fetch(src).then(function(r){ return r.blob(); }).then(function(b){ pb.hidden = true; go(b); }).catch(function(){ say('Could not read the pasted picture. Use Choose screenshot.'); }); }
  pb.addEventListener('input', function(){ setTimeout(fromBox, 50); }); pb.addEventListener('focus', function(){ if(!pb.querySelector('img')) pb.textContent = ''; });
  document.getElementById('scpaste').addEventListener('click', function(){
    function box(){ pb.hidden = false; pb.textContent = 'Tap and hold here, then tap Paste.'; pb.focus(); }
    if(!(navigator.clipboard && navigator.clipboard.read)){ box(); return; }
    navigator.clipboard.read().then(function(items){ for(var i = 0; i < items.length; i++){ var t = (items[i].types || []).filter(function(x){ return /^image\//.test(x); })[0]; if(t) return items[i].getType(t).then(function(b){ go(b); }); }
      say('No picture on the clipboard. Copy the screenshot first (open it, tap Share, Copy), then tap Paste screenshot.'); }).catch(function(){ box(); }); });
})();
"""
try:
    import account as ACCT; _link, _base = ACCT._base_css()
except Exception: _link, _base = "", ""
page = f"""<title>Sweep my slip · BetSweep</title>
<meta name="description" content="Screenshot any FanDuel slip and get a plain verdict before you bet it: its chance against its price, the weakest leg, and a safer swap. Read on your device; nothing is uploaded.">
{_link}
<style>{_base}
{CSS}</style>
<div class="sc">
<h1>Sweep my slip</h1>
<p class="lead">Before you place it, sweep it. Screenshot any FanDuel slip, yours or one somebody posted, and get a plain verdict: its chance against its price, the weakest leg, and a safer swap.</p>
<div class="drop" id="scdrop">
 <div class="btns"><label class="cta">Choose screenshot<input type="file" id="scfile" accept="image/*" hidden></label><button type="button" class="cta alt" id="scpaste">Paste screenshot</button></div>
 <div id="scpbox" contenteditable="true" hidden></div>
 <p class="hint">The betslip itself, a shared slip, or a bet under My Bets all work. Your phone reads the picture; it never leaves this device.</p>
 <div id="scout" aria-live="polite"></div>
</div>
<div class="btns" style="margin-top:14px"><a class="cta alt" href="/build/?sweep=1#slip">Sweep the slip I am building</a></div>
<div class="steps">
 <div><b>Chance vs price</b><span>The model's chance the whole slip cashes, next to what the price needs.</span></div>
 <div><b>Weakest leg</b><span>The riskiest leg and why, in a few words.</span></div>
 <div><b>Safer swap</b><span>One tap moves it to a safer line and shows the new price.</span></div>
</div>
<p class="fn">It prices player yards, catches, touchdowns and game lines that are on this week's board; anything else is named on the verdict and left out of the numbers. Information, not betting advice. <a href="/how/">How BetSweep picks</a></p>
</div>
<script defer src="/import.js"></script>
<script>{JS}</script>
"""
open(os.path.join(OUT, "slipcheck.html"), "w").write(page)
print("wrote out/slipcheck.html (Sweep my slip, /sweep/)")
