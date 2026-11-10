#!/usr/bin/env python3
"""build_pairs.py - the either-or touchdown pair maker at /pairs/ (owner 11/8-11/9: "Give me your favorites from the either-ors that I
should stack into a parlay"; "there's a good chance that ONE of them hits a TD"; house rule: an either-or leg is judged as a pair).

FanDuel sells "A or B to score" as one leg. This page prices that leg the way the promo pipeline does (pairs.py): pick two players
with an anytime-TD price this week and it shows the chance that at least one scores, the fair price, what the pair is worth compared
with the two singles (a same-game pair shares the game's ending), its worst ending, and the pair's risk - the SAFER player's, because
one of them scoring is the bet. Type FanDuel's price for the pair and it says how many points you are paying or getting. Below, the
best pairs on the board. FanDuel's either-or prices are not in any feed we pull, so the page never shows one it was not given.

Reads out/builder_data.json. Writes out/pairs.html (placed at /pairs/ by build_site.py) and out/pairs.json (the same list, for /api/).
The JS repeats pairs.py's arithmetic; tests/pairs_page.py holds the two to the same numbers.
"""
import json, os, html, sys
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
import sweep as SW, pairs as PR
E = html.escape
try: BD = json.load(open(os.path.join(OUT, "builder_data.json")))
except Exception as e: raise SystemExit(f"build_pairs.py needs out/builder_data.json (run build_builder.py first): {e}")
WEEK = BD.get("week"); GAMES = {g["gid"]: g for g in BD.get("games", [])}
def at(g):
    h, a = g.get("home"), g.get("away")
    if h and a: return f"{a} {'vs' if g.get('nt') else '@'} {h}"
    return f"{g.get('a')} - {g.get('b')}"
def tags(l):
    out = []
    for f in (l.get("fh") or []) + ((BD.get("pf") or {}).get(l.get("pl")) or []):
        if f and f[0] == "bad" and f[1] not in out: out.append(f[1])
    return out[:3]
TD = []
for l in BD.get("legs", []):
    if l.get("m") != "Anytime TD" or l.get("p") is None or l.get("o") is None or l.get("g") not in GAMES: continue
    TD.append({"n": l["pl"], "tm": l.get("tm", ""), "opp": l.get("opp", ""), "g": l["g"], "pos": l.get("pos", ""), "o": int(l["o"]), "p": round(l["p"], 4), "bk": l.get("bk"),
               "sc": l.get("sc"), "r": SW.risk_score(l, BD), "fl": tags(l)})
TD.sort(key=lambda x: (GAMES[x["g"]].get("sort", ""), x["g"], -x["p"]))
GJ = {gid: {"a": g.get("a"), "b": g.get("b"), "probs": g.get("probs"), "lab": at(g), "kick": g.get("kick", ""), "ko": g.get("ko")} for gid, g in GAMES.items() if any(t["g"] == gid for t in TD)}
# the server's own list of the best pairs (the page rebuilds it in the browser so games that have kicked off drop out)
byn = {l["pl"]: l for l in BD.get("legs", []) if l.get("m") == "Anytime TD"}
top = sorted(TD, key=lambda x: -x["p"])[:16]; best = []
for i in range(len(top)):
    for j in range(i + 1, len(top)):
        A, B = byn[top[i]["n"]], byn[top[j]["n"]]; e = PR.either(A, B, GAMES)
        if e: best.append({"a": top[i]["n"], "b": top[j]["n"], "p": round(e["p"], 4), "fair": PR.fair_american(e["p"]), "hedge": round(e["hedge"], 4), "risk": min(top[i]["r"], top[j]["r"]), "same_game": e["same_game"]})
best.sort(key=lambda x: (x["risk"] >= 2, -x["p"]))
json.dump({"week": WEEK, "built": BD.get("built"), "players": TD, "games": GJ, "best": best[:20],
           "note": "p = chance that at least one of the two scores (pairs.py); risk = the safer player's risk score (0-1 low, 2-3 some, 4+ high). FanDuel's either-or prices are not included."},
          open(os.path.join(OUT, "pairs.json"), "w"))

CSS = """
.pr{max-width:720px;margin:18px auto 40px}
.pr h1{font-family:var(--brand);font-style:italic;font-weight:800;font-size:36px;line-height:1;margin:0 0 8px;letter-spacing:-.01em}
.pr .lead{color:var(--mute);line-height:1.5;margin:0 0 14px;font-size:15.5px}
.pr .card{border:1px solid var(--line);border-radius:16px;background:var(--card);padding:14px}
.pr .pick{display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:center}
.pr .pick i{font-style:normal;color:var(--mute);font-family:var(--display);font-weight:800;font-size:13px;letter-spacing:.1em}
.pr select,.pr input{width:100%;min-height:46px;border:1.5px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink);font:inherit;font-size:15px;padding:0 10px;min-width:0}
.pr .big{margin:14px 0 2px;font-family:var(--display);font-weight:800;font-size:40px;line-height:1;letter-spacing:-.01em}
.pr .big small{display:block;margin-top:6px;font-family:inherit;font-weight:600;font-size:14px;letter-spacing:0;color:var(--mute);line-height:1.35}
.pr .rows{margin:12px 0 0;padding:0;list-style:none;font-size:14px;line-height:1.45}
.pr .rows li{padding:7px 0;border-top:1px solid var(--line);display:flex;gap:8px;justify-content:space-between;align-items:baseline}
.pr .rows li span:last-child{color:var(--mute);text-align:right}
.pr .rows li.note{display:block;color:var(--mute)} .pr .rows li.note b{color:var(--ink)}
.pr .rk{display:inline-block;padding:1px 8px;border-radius:9px;font-size:12px;font-weight:700;background:#dcefdc;color:#14532d}
.pr .rk.mid{background:#f6e3b8;color:#7a4b00} .pr .rk.hi{background:#b3261e;color:#fff}
.pr .fd{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;margin-top:12px}
.pr .fd label{font-size:14px;color:var(--mute)} .pr .fd input{width:120px;text-align:center}
.pr #prv{margin:10px 0 0;font-size:15px;line-height:1.45} .pr #prv b.up{color:var(--good)} .pr #prv b.dn{color:var(--redtxt)}
.pr h2{font-family:var(--display);font-weight:800;font-size:15px;letter-spacing:.1em;text-transform:uppercase;margin:22px 0 8px}
.pr .best{list-style:none;margin:0;padding:0;border:1px solid var(--line);border-radius:14px;overflow:hidden;background:var(--card)}
.pr .best li{border-top:1px solid var(--line)} .pr .best li:first-child{border-top:0}
.pr .best button{all:unset;box-sizing:border-box;display:grid;grid-template-columns:1fr auto;gap:2px 10px;width:100%;padding:11px 14px;cursor:pointer;font-size:14.5px;line-height:1.35}
.pr .best button:focus-visible{outline:2px solid var(--red);outline-offset:-2px}
.pr .best b{font-weight:700} .pr .best em{font-style:normal;font-family:var(--display);font-weight:800;font-size:17px;text-align:right}
.pr .best small{grid-column:1/-1;color:var(--mute);font-size:12.5px}
.pr .fn{color:var(--mute);font-size:12.5px;line-height:1.5;margin-top:16px} .pr .fn a{color:var(--ink)}
.pr .none{color:var(--mute);font-size:15px;line-height:1.5;margin:6px 0}
@media (max-width:480px){.pr .pick{grid-template-columns:1fr}.pr .pick i{text-align:center}.pr .big{font-size:34px}}
"""
JS = r"""
(function(){
  var D = __DATA__, G = D.games, $ = function(id){ return document.getElementById(id); };
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function pc(p){ return (p * 100).toFixed(p >= 0.995 || p < 0.1 ? 1 : 0) + '%'; }
  function am(o){ return (o > 0 ? '+' : '') + o; }
  function fair(p){ if(!(p > 0 && p < 1)) return null; return p >= 0.5 ? -Math.round(100 * p / (1 - p)) : Math.round(100 * (1 - p) / p); }
  function implied(o){ o = parseFloat(o); if(!isFinite(o) || o === 0 || Math.abs(o) < 100) return null; return o > 0 ? 100 / (o + 100) : -o / (-o + 100); }
  function wts(g){ var pr = (g && g.probs || []).map(Number), s = 0; pr.forEach(function(x){ s += x || 0; }); return pr.length === 4 && s > 0 ? pr.map(function(x){ return (x || 0) / s; }) : null; }
  function scn(l, w){ if(l.p == null || !l.sc || l.sc.length !== 4 || !w) return null; var m = 0; for(var k = 0; k < 4; k++) m += w[k] * l.sc[k]; if(m <= 0) return null;
    return l.sc.map(function(x){ return Math.min(0.97, Math.max(0, x * l.p / m)); }); }
  // pairs.py either(): same arithmetic, same numbers (tests/pairs_page.py)
  function either(A, B){
    var ind = 1 - (1 - A.p) * (1 - B.p), sg = A.g === B.g, st = A.tm === B.tm, wa = wts(G[A.g]), wb = wts(G[B.g]), sa = scn(A, wa), sb = scn(B, wb), out = {ind: ind, sg: sg, st: st, per: null, worst: null};
    out.book = A.bk != null && B.bk != null ? 1 - (1 - A.bk) * (1 - B.bk) : null;
    if(sg && sa && sb){ var per = [], p = 0; for(var k = 0; k < 4; k++){ var pe = 1 - (1 - sa[k]) * (1 - sb[k]); if(st) pe -= 0.02 * Math.min(sa[k], sb[k]); per.push(pe); p += wa[k] * pe; }
      out.p = p; out.per = per; out.worst = Math.min.apply(null, per); }
    else { out.p = ind - (st ? 0.02 * Math.min(A.p, B.p) : 0); if(sa && sb) out.worst = 1 - (1 - Math.min.apply(null, sa)) * (1 - Math.min.apply(null, sb)); }
    out.hedge = out.p - ind; return out; }
  window.BSPairs = {either: either, data: D, fair: fair, implied: implied};
  function live(t){ var g = G[t.g]; return !(g && g.ko && Date.now() >= g.ko); }
  function verdict(t){ try{ return window.BSRisk && window.BSRisk.verdict(t.n, 'Anytime TD'); }catch(e){ return null; } }
  function out(t){ var v = verdict(t); return !!(v && v.level === 'block'); }
  function risk(t){ var v = verdict(t); return t.r + (v && v.level === 'warn' ? 3 : 0); }
  var P = D.players.filter(live), byN = {}; P.forEach(function(t){ byN[t.n] = t; });
  function opts(sel, keep){
    var h = '<option value="">Pick a player</option>', gids = []; P.forEach(function(t){ if(gids.indexOf(t.g) < 0) gids.push(t.g); });
    gids.forEach(function(gid){ var g = G[gid]; h += '<optgroup label="' + esc(g.lab + (g.kick ? ' · ' + g.kick : '')) + '">';
      P.filter(function(t){ return t.g === gid; }).forEach(function(t){ h += '<option value="' + esc(t.n) + '"' + (t.n === keep ? ' selected' : '') + '>' + esc(t.n + ' (' + t.tm + ') ' + pc(t.p) + (out(t) ? ' - ruled out' : '')) + '</option>'; });
      h += '</optgroup>'; });
    sel.innerHTML = h; }
  function rkTag(s){ return s >= 4 ? '<span class="rk hi">High risk</span>' : s >= 2 ? '<span class="rk mid">Some risk</span>' : '<span class="rk">Low risk</span>'; }
  function endLab(g, k){ return [g.a + ' by 10+', 'a close, low game', 'a shootout', g.b + ' by 10+'][k]; }
  function show(){
    var A = byN[$('pra').value], B = byN[$('prb').value], box = $('prout');
    if(!A || !B){ box.innerHTML = '<p class="none">Pick two players and the pair is priced here.</p>'; return; }
    if(A.n === B.n){ box.innerHTML = '<p class="none">Pick two different players.</p>'; return; }
    var oa = out(A), ob = out(B);
    if(oa || ob){ var s = oa && ob ? null : (oa ? B : A);
      box.innerHTML = '<p class="none"><b>' + esc((oa ? A : B).n) + ' is ruled out' + (oa && ob ? ', and so is ' + esc(B.n) : '') + '.</b> ' + (s ? 'That leaves a single on ' + esc(s.n) + ' (' + pc(s.p) + '). Check how FanDuel settles the pair before you bet it.' : 'Pick another pair.') + '</p>'; return; }
    var e = either(A, B), f = fair(e.p), rs = Math.min(risk(A), risk(B)), g = G[A.g], h = '';
    h += '<p class="big">' + pc(e.p) + '<small>that ' + esc(A.n) + ' or ' + esc(B.n) + ' scores' + (f != null ? ' · fair price ' + am(f) : '') + '</small></p>';
    h += '<ul class="rows">';
    [A, B].forEach(function(t){ h += '<li><span><b>' + esc(t.n) + '</b> ' + esc(t.tm) + '</span><span>' + pc(t.p) + ' alone · FanDuel ' + am(t.o) + '</span></li>'; });
    var d = Math.round(e.hedge * 1000) / 10;
    h += '<li class="note">' + (!e.sg ? 'Different games, so the two do not affect each other.' : e.per == null ? 'Same game.' : d >= 0.5 ? '<b>Good pair:</b> they need different kinds of game, so together they are worth ' + d.toFixed(1) + ' points more than the two singles suggest.' : d <= -0.5 ? '<b>Overlap:</b> they need the same kind of game' + (e.st ? ' and share the ball' : '') + ', so together they are worth ' + Math.abs(d).toFixed(1) + ' points less than the two singles suggest.' : 'Same game, and the game script barely moves this pair.') + '</li>';
    if(e.per && g){ var k = e.per.indexOf(e.worst); h += '<li><span>Worst ending</span><span>' + esc(endLab(g, k)) + ': ' + pc(e.worst) + '</span></li>'; }
    var both = [A, B].filter(function(t){ return risk(t) >= 2; }), why = both.length === 2 ? 'Both names carry flags: ' + esc(A.fl.concat(B.fl).filter(function(x, i, a){ return a.indexOf(x) === i; }).slice(0, 4).join(', ') || 'see the builder') + '.' : both.length === 1 ? esc(both[0].n) + ' carries flags' + (both[0].fl.length ? ' (' + esc(both[0].fl.slice(0, 2).join(', ')) + ')' : '') + '; ' + esc((both[0] === A ? B : A).n) + ' is clean, and one of them scoring is the bet.' : 'Neither name carries a risk flag.';
    h += '<li class="note">' + rkTag(rs) + ' ' + why + '</li></ul>';
    h += '<div class="fd"><label for="prfd">FanDuel\'s price for this pair' + (e.book != null && fair(e.book) != null ? ' <small>(its two singles point to about ' + am(fair(e.book)) + ')</small>' : '') + '</label><input id="prfd" inputmode="numeric" placeholder="-475" autocomplete="off"></div><p id="prv" aria-live="polite"></p>';
    box.innerHTML = h;
    var inp = $('prfd'); try{ var sv = sessionStorage.getItem('bs_pair_fd|' + [A.n, B.n].sort().join('|')); if(sv) inp.value = sv; }catch(x){}
    function judge(){ var raw = inp.value.replace(/[^\d+\-.]/g, ''), need = implied(raw), v = $('prv');
      try{ sessionStorage.setItem('bs_pair_fd|' + [A.n, B.n].sort().join('|'), raw); }catch(x){}
      if(!raw){ v.innerHTML = ''; return; } if(need == null){ v.textContent = 'Type the price the way FanDuel shows it, like -475 or +120.'; return; }
      var gap = Math.round((e.p - need) * 1000) / 10;
      v.innerHTML = 'At ' + esc(am(parseFloat(raw))) + ' the pair has to score ' + pc(need) + ' of the time. The model has ' + pc(e.p) + ': ' + (gap >= 1 ? '<b class="up">' + gap.toFixed(1) + ' points on your side.</b>' : gap <= -1 ? '<b class="dn">you are paying ' + Math.abs(gap).toFixed(1) + ' points too much.</b>' : '<b>about a fair price.</b>') + (rs >= 2 ? ' Both names carry flags, so treat it as a risky leg either way.' : ''); }
    inp.addEventListener('input', judge); judge(); }
  function best(){
    var top = P.filter(function(t){ return !out(t); }).slice().sort(function(a, b){ return b.p - a.p; }).slice(0, 16), rows = [];
    for(var i = 0; i < top.length; i++) for(var j = i + 1; j < top.length; j++){ var e = either(top[i], top[j]); rows.push({a: top[i], b: top[j], e: e, r: Math.min(risk(top[i]), risk(top[j]))}); }
    rows.sort(function(x, y){ return ((x.r >= 2) - (y.r >= 2)) || (y.e.p - x.e.p); });
    var seen = {}, pick = []; rows.forEach(function(r){ if(pick.length >= 8) return; var ca = seen[r.a.n] || 0, cb = seen[r.b.n] || 0; if(ca >= 2 || cb >= 2) return; seen[r.a.n] = ca + 1; seen[r.b.n] = cb + 1; pick.push(r); });
    var el = $('prbest'); if(!pick.length){ el.innerHTML = ''; $('prbesth').hidden = true; return; } $('prbesth').hidden = false;
    el.innerHTML = pick.map(function(r){ var f = fair(r.e.p), d = Math.round(r.e.hedge * 1000) / 10;
      return '<li><button type="button" data-a="' + esc(r.a.n) + '" data-b="' + esc(r.b.n) + '"><b>' + esc(r.a.n) + ' or ' + esc(r.b.n) + '</b><em>' + pc(r.e.p) + '</em><small>' + (r.r >= 4 ? 'High risk' : r.r >= 2 ? 'Some risk' : 'Low risk') + (f != null ? ' · fair ' + am(f) : '') + ' · ' + esc(r.a.tm === r.b.tm ? r.a.tm : r.a.tm + ' / ' + r.b.tm) + (r.e.sg && d >= 0.5 ? ' · different needs, +' + d.toFixed(1) : r.e.sg && d <= -0.5 ? ' · overlap, ' + d.toFixed(1) : '') + '</small></button></li>'; }).join(''); }
  function init(){
    if(!P.length){ $('prcard').innerHTML = '<p class="none">' + (D.players.length ? 'Every game with a touchdown price has kicked off. Next week\'s prices land midweek.' : 'FanDuel has not posted touchdown prices for this week yet. They usually land by Thursday.') + '</p>'; $('prbesth').hidden = true; return; }
    var q = new URLSearchParams(location.search), a = q.get('a'), b = q.get('b');
    opts($('pra'), byN[a] ? a : ''); opts($('prb'), byN[b] ? b : ''); show(); best(); }
  $('pra').addEventListener('change', show); $('prb').addEventListener('change', show);
  $('prbest').addEventListener('click', function(ev){ var b = ev.target.closest && ev.target.closest('button[data-a]'); if(!b) return; $('pra').value = b.getAttribute('data-a'); $('prb').value = b.getAttribute('data-b'); show(); $('prcard').scrollIntoView({behavior: 'smooth', block: 'start'}); });
  document.addEventListener('bs-risk', function(){ try{ var a = $('pra').value, b = $('prb').value; opts($('pra'), a); opts($('prb'), b); show(); best(); }catch(e){} });
  init();
})();
"""
try:
    import account as ACCT; _link, _base = ACCT._base_css()
except Exception: _link, _base = "", ""
data = json.dumps({"week": WEEK, "players": TD, "games": GJ}, separators=(",", ":")).replace("</", "<\\/")
page = f"""<title>Either-or TDs · BetSweep</title>
<meta name="description" content="Price FanDuel's either-or touchdown legs: pick two players and see the chance one of them scores, the fair price, and whether the pair is worth more or less than its two singles.">
{_link}
<style>{_base}
{CSS}</style>
<div class="pr">
<h1>Either-or TDs</h1>
<p class="lead">Two names, one leg: it cashes when either one scores. Pick the pair and see what it is really worth before you pay FanDuel's price.</p>
<div class="card" id="prcard">
 <div class="pick"><select id="pra" aria-label="First player"></select><i>OR</i><select id="prb" aria-label="Second player"></select></div>
 <div id="prout" aria-live="polite"></div>
</div>
<h2 id="prbesth">Best pairs on the board</h2>
<ul class="best" id="prbest"></ul>
<p class="fn">Week {E(str(WEEK))}. A pair in the same game is priced with the game's four endings, so a back who needs a lead and a receiver who needs a chase are worth more together than apart. The pair's risk is the safer player's: one of them scoring is the bet. FanDuel's either-or prices are not in our feed, so type the one you see. Information, not betting advice. <a href="/how/">How BetSweep picks</a></p>
</div>
<script>{JS.replace("__DATA__", data)}</script>
"""
open(os.path.join(OUT, "pairs.html"), "w").write(page)
print(f"wrote out/pairs.html + pairs.json: {len(TD)} players with an anytime-TD price over {len(GJ)} games, week {WEEK}; best pair "
      + (f"{best[0]['a']} or {best[0]['b']} {best[0]['p'] * 100:.0f}% (fair {best[0]['fair']:+d}, {SW.risk_tag(best[0]['risk']) or 'low risk'})" if best else "none yet"))
