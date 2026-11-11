#!/usr/bin/env python3
"""build_boost.py - the Boost finder, /boost/ (owner 11/10 deep dive: "paste the day's boost and get the best slip for it").

Why: graded over Weeks 6-9 our over legs lost 7-11 units per 100 staked - the book's fee, leg after leg - and a four-leg slip pays
that fee four times. A profit boost is the one time the book hands some of it back, so the question worth a page is "which slip is
closest to fair BEFORE the boost, inside this boost's rules?".

Part 1, different games (the arithmetic is exact: legs from different games are independent, and FanDuel multiplies their prices):
the visitor picks the boost %, how many legs, the shortest price a leg may have and the shortest total; the page tries every
combination of the board's legs, one per game, and shows the slip most likely to land and - when it is a different one - the slip
with the best value after the boost that still lands one time in ten. A leg's chance is its FanDuel break-even less the fee our
graded legs have actually paid (7 per 100: FEE = 0.93), or the board's shown chance when that is lower. Why not the model's own gap:
graded over Weeks 6-9, legs the site showed at or above the price hit three points UNDER it, so a slip built from the widest gaps
is built from the model's biggest misses - the first version of this page answered a 25% boost with a +4530 ticket.
Value per $1 = chance x (1 + (price - 1) x (1 + boost)) - 1; each card also says what the boost itself is worth on that slip. (A
boost multiplies winnings, not the stake, so it is worth little on a short price: 25% on a -131 slip adds about 8 cents per dollar.)
Part 2, same-game boosts: FanDuel prices a same-game parlay its own way, so the page cannot know the quote. The visitor types the
price the app shows; the page applies the boost and holds it against the model's chance for that game's best parlay (or any chance
he types).

Reads out/builder_data.json and out/best_parlays.json. Writes out/boost.html (a plain page for build_site.py's place_plain) and
out/boost.json (served as /b/boost.json): the pool - per game, the legs with FanDuel ids whose chance x price is highest (props that
are not unders or first-TD, main moneylines, spreads and totals), each with its risk score - and the per-game best parlays.
"""
import html, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); E = html.escape
sys.path.insert(0, HERE)
import sweep as SW  # noqa: E402

PER_GAME = 8


def dec(o): o = float(o); return 1 + o / 100 if o > 0 else 1 + 100 / -o


def at(g): return f"{g['away']} {'vs' if g.get('nt') else '@'} {g['home']}" if g.get("home") and g.get("away") else f"{g['a']} - {g['b']}"


def leg_txt(l, G):
    if l.get("gl"):
        return l["pl"] if l["m"] != "Total" else f"{l['pl']} ({at(G[l['g']])})"
    if l["m"] == "Anytime TD": return f"{l['pl']} to score"
    return f"{l['pl']} {int(round(l['ln']))}+ {l['m'].lower()}"


def pool(BD):
    G = {g["gid"]: g for g in BD["games"]}; by = {}
    for l in BD["legs"]:
        if l.get("o") is None or l.get("p") is None or l.get("u") or str(l["m"]).startswith("Under") or l["m"] == "First TD": continue
        if l.get("gl") and (l.get("alt") or l.get("src") not in (None, "fd")): continue
        fd = l.get("fd") or {}
        if not (fd.get("m") and fd.get("s")) or not (-600 <= l["o"] <= 400) or l["g"] not in G: continue
        by.setdefault(l["g"], []).append(l)
    out = []
    for gid, ls in by.items():
        ls.sort(key=lambda l: -(l["p"] * dec(l["o"]))); seen = set(); n = 0
        for l in ls:
            k = (l["pl"], l["m"]) if not l.get("gl") else (l["m"], (l.get("gl") or {}).get("side"))
            if k in seen: continue                      # one rung per player and market: the closest to fair
            seen.add(k); n += 1
            out.append({"t": leg_txt(l, G), "g": gid, "pl": l["pl"], "gl": 1 if l.get("gl") else 0, "o": int(l["o"]), "p": round(l["p"], 4),
                        "r": int(SW.risk_score(l, BD)) if not l.get("gl") else 0, "fm": fd_id(l, "m"), "fs": fd_id(l, "s")})
            if n >= PER_GAME: break
    return out


def fd_id(l, k): return str((l.get("fd") or {}).get(k) or "")


def build(out_dir=OUT):
    BD = json.load(open(os.path.join(out_dir, "builder_data.json"))); G = {g["gid"]: g for g in BD["games"]}
    try: BP = json.load(open(os.path.join(out_dir, "best_parlays.json")))
    except Exception: BP = []
    legs = pool(BD)
    games = {g["gid"]: {"at": at(g), "ko": g.get("ko") or 0, "kick": g.get("kick", "")} for g in BD["games"]}
    sgp = [{"g": b["gid"], "pj": round(b["pj"], 4), "dec": round(b["dec"], 3), "legs": [x[0] if x[1] in ("Total", "Spread", "Moneyline") else f"{x[0]} {x[1].lower()} {x[2]:g}+" if x[1] != "Anytime TD" else f"{x[0]} to score" for x in b["legs"]]}
           for b in BP if b.get("pj") and b.get("gid") in games]
    data = {"week": BD.get("week"), "built": BD.get("built"), "legs": legs, "games": games, "sgp": sgp}
    json.dump(data, open(os.path.join(out_dir, "boost.json"), "w"), separators=(",", ":"), ensure_ascii=False)
    try:
        import account as ACCT; _link, _base = ACCT._base_css()
    except Exception: _link, _base = "", ""
    page = f"""<title>Boost finder · BetSweep</title>
<meta name="description" content="Got a profit boost? Enter its rules and BetSweep finds the slip closest to fair before the boost, so the boost does the most work. NFL Week {E(str(BD.get('week')))}.">
{_link}
<style>{_base}
{CSS}</style>
<div class="bz">
<div class="bzhead"><h1>Boost finder</h1><span class="sub">Week {E(str(BD.get("week")))}. A boost is the one time the book gives some of its fee back. Spend it on the slip that was closest to fair to begin with.</span></div>
<section class="card"><h2 class="brush">Your boost</h2>
<div class="bzform">
<label>Boost<select id="bzb"><option value="10">10%</option><option value="20">20%</option><option value="25" selected>25%</option><option value="30">30%</option><option value="33">33%</option><option value="40">40%</option><option value="50">50%</option><option value="100">100%</option></select></label>
<label>Legs<select id="bzn"><option>2</option><option selected>3</option><option>4</option><option>5</option><option>6</option></select></label>
<label>Each leg at least<select id="bzleg"><option value="">any price</option><option value="-500">-500</option><option value="-300">-300</option><option value="-250">-250</option><option value="-200">-200</option><option value="-150">-150</option><option value="100">+100</option></select></label>
<label>Slip total at least<select id="bztot"><option value="">any price</option><option value="100">+100</option><option value="200">+200</option><option value="300">+300</option><option value="400">+400</option><option value="500">+500</option><option value="1000">+1000</option></select></label>
<label class="chk"><input type="checkbox" id="bzsafe" checked> Low-risk legs only</label>
<label class="chk"><input type="checkbox" id="bzgl" checked> Include moneylines, spreads and totals</label>
</div>
<p class="fine">One leg per game, so the price is simply the legs multiplied. Chances here take off the fee our graded legs have paid (about 7 per 100), so they run a little under the board's and no slip shows a profit before the boost. For a same-game boost use the checker further down.</p></section>
<div id="bzout"></div>
<section class="card"><h2 class="brush">Same-game boost? Check it</h2>
<p class="fine" style="margin:0 0 10px">FanDuel prices a same-game parlay its own way. Type the price the app shows you and the page does the rest.</p>
<div class="bzform">
<label>Game's best parlay<select id="bzg"></select></label>
<label>Chance it lands<input id="bzp" type="number" min="1" max="99" step="1" inputmode="numeric" placeholder="%"></label>
<label>FanDuel's price<input id="bzq" type="text" inputmode="text" placeholder="+450" autocomplete="off"></label>
<label>Boost<select id="bzb2"><option value="0">none</option><option value="10">10%</option><option value="20">20%</option><option value="25" selected>25%</option><option value="30">30%</option><option value="33">33%</option><option value="40">40%</option><option value="50">50%</option><option value="100">100%</option></select></label>
</div>
<p class="bzlegs" id="bzglegs"></p>
<div class="bzverdict" id="bzv2" hidden></div></section>
<p class="foot">The chances are the model's, not guarantees. A boost has rules of its own (max stake, which markets, when it expires): read them in the app. 21+ | Gamble responsibly.</p>
</div>
<script>{JS}</script>
"""
    open(os.path.join(out_dir, "boost.html"), "w").write(page)
    return f"wrote out/boost.html + boost.json: {len(legs)} legs in the pool over {len({l['g'] for l in legs})} games, {len(sgp)} same-game parlays, week {BD.get('week')}"


CSS = """
.bz{max-width:720px;margin:14px auto 40px;padding:0 12px}
.bz .bzhead{margin:0 4px 14px} .bz h1{margin:0;font-family:var(--brand);font-style:italic;font-weight:800;font-size:40px;letter-spacing:-.02em;line-height:1}
.bz .sub{display:block;margin-top:6px;color:var(--mute);font-size:14px;line-height:1.45}
.bz .card{border:1px solid var(--line);border-radius:14px;background:var(--card);padding:14px 14px 12px;margin-bottom:12px}
.bz .card.best{border:2px solid var(--red)}
.bz h2{font-family:var(--display);font-weight:700;letter-spacing:.01em;font-size:22px;line-height:1.1;color:var(--ink);margin:0 0 10px;display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 10px}
.bz h2 small{font-family:var(--body);font-weight:500;font-size:13.5px;letter-spacing:0;color:var(--mute)}
.bz .bzform{display:grid;grid-template-columns:1fr 1fr;gap:10px 12px}
.bz label{display:flex;flex-direction:column;gap:5px;font-family:var(--display);font-weight:800;font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--mute)}
.bz label.chk{flex-direction:row;align-items:center;gap:8px;font-family:var(--body);font-weight:500;font-size:14px;letter-spacing:0;text-transform:none;color:var(--ink);grid-column:1 / -1}
.bz select,.bz input[type=number],.bz input[type=text]{font:inherit;font-family:var(--body);font-weight:600;font-size:16px;letter-spacing:0;text-transform:none;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:10px 10px;min-height:44px;width:100%;box-sizing:border-box}
.bz input[type=checkbox]{width:20px;height:20px;accent-color:var(--red)}
.bz .fine{margin:10px 0 0;color:var(--mute);font-size:12.5px;line-height:1.45}
.bz .legs{list-style:none;margin:0 0 10px;padding:0}
.bz .legs li{display:flex;justify-content:space-between;align-items:baseline;gap:10px;padding:9px 0;border-top:1px solid var(--line);font-size:15.5px;line-height:1.3}
.bz .legs li:first-child{border-top:0} .bz .legs b{font-weight:600} .bz .legs span{color:var(--mute);white-space:nowrap;font-size:14px}
.bz .nums{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:0 0 12px}
.bz .nums div{background:var(--chalk);border-radius:10px;padding:9px 11px} .bz .nums small{display:block;font-family:var(--display);font-weight:800;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--mute)}
.bz .nums b{font-family:var(--display);font-weight:800;font-size:21px;line-height:1.2} .bz .nums b s{font-weight:600;font-size:14px;color:var(--mute);margin-right:6px}
.bz .verd{margin:0 0 12px;font-size:14.5px;line-height:1.45} .bz .verd b{font-weight:700} .bz .up{color:var(--good)} .bz .dn{color:var(--redtxt,var(--red))}
.bz a.bsbtn{text-decoration:none;display:flex;width:100%;min-height:48px;font-size:16px;padding:13px 16px;box-sizing:border-box;justify-content:center;align-items:center;gap:8px}
.bz .none{color:var(--mute);font-size:15px;line-height:1.5;margin:8px 4px 16px}
.bz .rule{margin:0 4px 12px;font-size:14.5px;line-height:1.45;color:var(--ink)} .bz .rule b{font-weight:700}
.bz .bzlegs{margin:10px 0 0;font-size:14.5px;line-height:1.4;color:var(--ink)}
.bz .bzverdict{margin-top:12px}
.bz .foot{margin:18px 4px 0;color:var(--mute);font-size:12px;line-height:1.5}
@media (max-width:380px){.bz h1{font-size:34px}}
"""

JS = r"""
(function(){
  var $ = function(i){ return document.getElementById(i); }, D = null;
  // What a leg is really worth. Graded over Weeks 6-9 our over legs lost 7 to 11 per 100 staked whatever the model said about them,
  // so a leg's chance here is its FanDuel break-even less that fee (FEE), or the board's own number when that is lower - never more.
  var FEE = 0.93, FLOOR = 0.10;
  function dec(o){ return o > 0 ? 1 + o / 100 : 1 + 100 / -o; }
  function am(d){ if(!(d > 1)) return ''; return d >= 2 ? '+' + Math.round((d - 1) * 100) : '−' + Math.round(100 / (d - 1)); }
  function amo(o){ return o > 0 ? '+' + o : '−' + (-o); }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function money(x){ return (x < 0 ? '−$' : '$') + Math.abs(x).toFixed(2); }
  function boosted(d, b){ return 1 + (d - 1) * (1 + b); }
  // every combination of n games, one leg from each: keep the best value after the boost and the most likely that still clears the rules
  function find(o){
    var now = Date.now(), by = {};
    D.legs.forEach(function(l){ var g = D.games[l.g]; if(!g || (g.ko && g.ko <= now)) return; if(o.safe && l.r >= 2) return; if(!o.gl && l.gl) return;
      var d = dec(l.o); if(o.minLeg != null && d < dec(o.minLeg) - 1e-9) return; var pe = Math.min(l.p, FEE / d); (by[l.g] = by[l.g] || []).push({l: l, d: d, pe: pe, v: pe * d}); });
    var gs = Object.keys(by), per = o.n >= 5 ? 3 : o.n === 4 ? 6 : 99;      // three legs or fewer: every leg of the pool is tried, so the answer is exact
    gs.forEach(function(g){ var a = by[g].slice().sort(function(x, y){ return (y.v - x.v) || (y.pe - x.pe); }).slice(0, per), b = by[g].slice().sort(function(x, y){ return y.pe - x.pe; }).slice(0, 2);
      b.forEach(function(x){ if(a.indexOf(x) < 0) a.push(x); }); by[g] = a; });
    if(gs.length < o.n) return {games: gs.length};
    var minD = o.minTot != null ? dec(o.minTot) : 0, best = null, safe = null, tried = 0, pick = [];
    // Two answers. "Most likely to land": the highest all-hit chance inside the rules. "More boost for the risk": the best value
    // after the boost among slips that still land at least one time in ten - a boost is worth more on a longer price, and without
    // that floor the arithmetic always picks a lottery ticket.
    function rec(i, left, P, Dd){
      if(left === 0){ tried++; if(Dd < minD - 1e-9) return; var ev = P * boosted(Dd, o.b) - 1;
        if(P >= FLOOR && (!best || ev > best.ev + 1e-12)) best = {ev: ev, P: P, D: Dd, legs: pick.slice()};
        if(!safe || P > safe.P + 1e-12) safe = {ev: ev, P: P, D: Dd, legs: pick.slice()}; return; }
      if(gs.length - i < left) return;
      rec(i + 1, left, P, Dd);
      var a = by[gs[i]]; for(var k = 0; k < a.length; k++){ pick.push(a[k].l); rec(i + 1, left - 1, P * a[k].pe, Dd * a[k].d); pick.pop(); }
    }
    rec(0, o.n, 1, 1);
    return {best: best, safe: safe, tried: tried, games: gs.length};
  }
  function fd(legs){ return 'https://sportsbook.fanduel.com/addToBetslip?' + legs.map(function(l, i){ return 'marketId[' + i + ']=' + encodeURIComponent(l.fm) + '&selectionId[' + i + ']=' + encodeURIComponent(l.fs); }).join('&'); }
  function verdict(ev0, ev1){
    var a = 'Per $10 staked, over time: <b class="' + (ev0 >= 0 ? 'up' : 'dn') + '">' + money(ev0 * 10) + '</b> without the boost, <b class="' + (ev1 >= 0 ? 'up' : 'dn') + '">' + money(ev1 * 10) + '</b> with it (the boost is worth ' + money((ev1 - ev0) * 10) + '). ';
    return a + (ev1 >= 0.005 ? '<b class="up">The boost puts this one in front.</b>' : ev1 >= -0.03 ? '<b>About even with the boost.</b> As good as a boost gets on this board.' : '<b class="dn">Still behind, even boosted.</b> A bigger boost or a shorter slip would be needed.'); }
  function card(title, sub, r, b, cls){
    var bd = boosted(r.D, b);
    return '<section class="card ' + cls + '"><h2 class="brush">' + title + ' <small>' + sub + '</small></h2><ul class="legs">' +
      r.legs.map(function(l){ return '<li><b>' + esc(l.t) + '</b><span>' + Math.round(Math.min(l.p, FEE / dec(l.o)) * 100) + '% · ' + amo(l.o) + '</span></li>'; }).join('') + '</ul>' +
      '<div class="nums"><div><small>Pays</small><b><s>' + am(r.D) + '</s>' + am(bd) + '</b></div><div><small>All hit</small><b>about ' + Math.round(r.P * 100) + '%</b></div></div>' +
      '<p class="verd">' + verdict(r.P * r.D - 1, r.ev) + '</p>' +
      '<a class="bsbtn" href="' + esc(fd(r.legs)) + '" target="_blank" rel="noopener">Open on FanDuel <small>' + am(r.D) + ' before the boost</small></a></section>';
  }
  function same(a, b){ return a && b && a.legs.length === b.legs.length && a.legs.every(function(l, i){ return l === b.legs[i]; }); }
  function run(){
    if(!D) return; var out = $('bzout');
    var o = {b: (+$('bzb').value) / 100, n: +$('bzn').value, minLeg: $('bzleg').value === '' ? null : +$('bzleg').value, minTot: $('bztot').value === '' ? null : +$('bztot').value, safe: $('bzsafe').checked, gl: $('bzgl').checked};
    var r = find(o);
    if(!r.safe){ out.innerHTML = '<p class="none">' + (r.games < o.n ? 'Only ' + r.games + ' game' + (r.games === 1 ? ' has' : 's have') + ' a leg that fits, so a ' + o.n + '-leg slip from different games is not there yet. More props post as the week goes on. Try fewer legs' + (o.safe ? ' or untick low-risk only' : '') + '.' : 'No ' + o.n + '-leg slip on this board clears those prices. Loosen one of the rules.') + '</p>'; return; }
    var h = '<p class="rule">A boost is paid on your winnings, not your stake, so it does more on a longer price. Each leg costs about 7 cents on the dollar in fee, on our graded legs. The cards below show what this boost is worth on each slip.</p>';
    h += card('Most likely to land', 'inside these rules', r.safe, o.b, 'best');
    if(r.best && !same(r.best, r.safe) && r.best.ev > r.safe.ev + 0.005) h += card('More boost for the risk', 'longer price, still lands 1 in 10 or better', r.best, o.b, '');
    out.innerHTML = h;
  }
  function sgp(){
    var g = $('bzg').value, s = null; (D.sgp || []).forEach(function(x){ if(x.g === g) s = x; });
    if(s && !$('bzp').dataset.typed) $('bzp').value = Math.round(s.pj * 100);
    $('bzglegs').textContent = s ? s.legs.join(' + ') + ' (legs multiplied: ' + am(s.dec) + ')' : '';
    var q = $('bzq').value.replace(/−/g, '-').replace(/[^0-9+\-]/g, ''), o = parseInt(q, 10), p = (+$('bzp').value) / 100, b = (+$('bzb2').value) / 100, v = $('bzv2');
    if(!q || isNaN(o) || Math.abs(o) < 100 || !(p > 0 && p < 1)){ v.hidden = true; return; }
    var d = dec(o), bd = boosted(d, b);
    v.hidden = false; v.innerHTML = '<div class="nums"><div><small>Pays</small><b><s>' + am(d) + '</s>' + am(bd) + '</b></div><div><small>Needs to land</small><b>' + Math.round(100 / bd) + '% <s style="margin-left:6px">model ' + Math.round(p * 100) + '%</s></b></div></div><p class="verd">' + verdict(p * d - 1, p * bd - 1) + '</p>';
  }
  fetch('/b/boost.json', {cache: 'no-store'}).then(function(r){ return r.json(); }).then(function(d){ D = d;
    var now = Date.now(), sel = $('bzg'); sel.innerHTML = '<option value="">my own slip</option>' + (D.sgp || []).filter(function(s){ var g = D.games[s.g]; return g && !(g.ko && g.ko <= now); }).map(function(s){ return '<option value="' + esc(s.g) + '">' + esc(D.games[s.g].at) + '</option>'; }).join('');
    run(); sgp(); }).catch(function(){ $('bzout').innerHTML = '<p class="none">The board did not load. Pull to refresh.</p>'; });
  ['bzb', 'bzn', 'bzleg', 'bztot', 'bzsafe', 'bzgl'].forEach(function(i){ $(i).addEventListener('change', run); });
  $('bzp').addEventListener('input', function(){ this.dataset.typed = this.value ? '1' : ''; sgp(); });
  $('bzg').addEventListener('change', function(){ $('bzp').dataset.typed = ''; sgp(); });
  ['bzq', 'bzb2'].forEach(function(i){ $(i).addEventListener('input', sgp); $(i).addEventListener('change', sgp); });
})();
"""

if __name__ == "__main__":
    print(build())
