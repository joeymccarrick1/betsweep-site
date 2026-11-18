#!/usr/bin/env python3
"""fantasy_outlook.py - buy, hold or sell: a league's standings turned into a plan (owner 11/17).

Owner: "I think it'd be cool on the fantasy page to suggest whether to tank or buy players depending on record and likelihood of
making playoffs. Make suggestions of who to trade for with that in mind. Maybe get rid of vets to get better draft position."

What it does, in the browser, for a Sleeper league the reader has imported on the trade calculator (build_trade.py):
  1. Playoff odds. Every team's weekly score is a bell curve around a mean that is half its own points per game so far and half the
     strength of its best lineup by this model (each player's adjusted points per game; injured players do not start), with a spread
     of about 19% of the league's average score. The rest of the regular season is played 3,000 times on the league's real schedule
     (Sleeper's matchups for the weeks left; a random pairing if they cannot be read), wins first and points second, the league's
     playoff spots, an extra win against the weekly median where the league plays that way. The random numbers are seeded by the
     league and the week, so the same standings always give the same odds.
  2. A verdict from the reader's own odds: 70%+ buy, 35-70% bubble (buy small), 12-35% long shot, under 12% out. Selling only makes
     sense where something carries over, so "sell" is offered in dynasty and keeper leagues; a redraft team that is out is told so.
  3. Who to trade for. Buying: the players on teams that are out of it (25% or less) who would add the most points a week to the
     reader's best lineup, each with a bench player of similar value to offer. Selling: the reader's veterans (by age for the
     position, or with 70%+ of their value in this season) matched to the contender whose lineup they improve most, with a young
     player of similar value to ask for - and the draft slot the team is tracking for, since selling points also moves the pick.

JS exposes window.bsOutlook = {sim, plan, quick, lineup, slots, games, pf, html}; html(league, teams, sched, esc) returns the card. The
caller owns the data: teams = [{r: Sleeper roster, name, me, ps: [{mp: model player or null, v: trade value}]}] where a model player
carries n, pos, age, adj (points per game), Re (games left he is expected to play), st, ros, fut.
"""

CSS = r"""
.tc .olk{border:1.5px solid var(--line);border-radius:12px;padding:12px 14px 10px;margin:10px 0 14px;background:var(--card)}
.tc .olk .vd{display:inline-block;font-family:var(--display);font-weight:800;letter-spacing:.06em;text-transform:uppercase;font-size:12px;line-height:1;padding:5px 10px;border-radius:999px;color:#fff;background:var(--good);vertical-align:middle;margin-right:8px}
.tc .olk .vd.sell{background:var(--bad)} .tc .olk .vd.hold{background:var(--mute)}
.tc .olk h3{display:inline;font-family:var(--display);font-size:19px;line-height:1.2;margin:0;vertical-align:middle}
.tc .olk .olline{margin:8px 0 2px;font-size:14px;line-height:1.5} .tc .olk .olline b{font-family:var(--display);font-size:16px}
.tc .olk .olwhy{margin:2px 0 8px;color:var(--mute);font-size:13.5px;line-height:1.5}
.tc .olk h4{font-family:var(--display);font-weight:700;font-size:15px;margin:10px 0 0}
.tc .olk ul{list-style:none;margin:0;padding:0} .tc .olk li{padding:9px 0;border-top:1px solid var(--line);font-size:13.5px;line-height:1.45}
.tc .olk li:first-child{border-top:0} .tc .olk li b.t{font-family:var(--display);font-size:15px} .tc .olk li small{color:var(--mute)}
.tc .olk li .gn{font-weight:700;color:var(--good);white-space:nowrap}
.tc .olk li .of{display:flex;gap:10px;align-items:center;justify-content:space-between;margin-top:3px} .tc .olk li .of .addbtn{flex:none;margin:0;min-height:38px}
.tc .olk details{margin-top:8px;border-top:1px solid var(--line)} .tc .olk summary{cursor:pointer;min-height:40px;display:flex;align-items:center;font-size:13px;color:var(--mute)}
.tc .olk table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums} .tc .olk td{padding:5px 4px;border-top:1px solid var(--line)}
.tc .olk td.r{text-align:right;white-space:nowrap} .tc .olk tr.me td{font-weight:700}
.tc .olk .bar{display:inline-block;width:46px;height:6px;border-radius:3px;background:var(--line);vertical-align:middle;margin-left:6px;overflow:hidden} .tc .olk .bar i{display:block;height:100%;background:var(--good)}
.tc .olk .none{color:var(--mute);font-size:13.5px;margin:6px 0 2px}
"""

JS = r"""
window.bsOutlook = (function(){
  function rng(a){ return function(){ a |= 0; a = a + 0x6D2B79F5 | 0; var t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function gauss(R){ var u = 0, v = 0; while(u === 0) u = R(); while(v === 0) v = R(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  var FLEX = {FLEX: ['RB','WR','TE'], WRRB_FLEX: ['RB','WR'], REC_FLEX: ['WR','TE'], SUPER_FLEX: ['QB','RB','WR','TE']};
  var OLD = {QB: 31, RB: 26, WR: 28, TE: 29};   // the age a position starts losing trade value faster than it scores
  function slots(l){ var s = (l.roster_positions || []).filter(function(x){ return x === 'QB' || x === 'RB' || x === 'WR' || x === 'TE' || FLEX[x]; }); return s.length ? s : ['QB','RB','RB','WR','WR','TE','FLEX']; }
  function avail(x){ return !!(x && x.mp && x.mp.Re > 0 && x.mp.st !== 'OUT' && x.mp.adj > 0); }
  // best lineup by points per game: the fixed slots first, then the flex slots from the narrowest to the widest
  function lineup(ps, sl){ var pool = ps.filter(avail).sort(function(a, b){ return b.mp.adj - a.mp.adj; }), used = {}, pts = 0, st = [];
    function take(ok){ for(var i = 0; i < pool.length; i++){ if(used[i] || ok.indexOf(pool[i].mp.pos) < 0) continue; used[i] = 1; pts += pool[i].mp.adj; st.push(pool[i]); return; } }
    sl.filter(function(s){ return !FLEX[s]; }).forEach(function(s){ take([s]); });
    sl.filter(function(s){ return FLEX[s]; }).sort(function(a, b){ return FLEX[a].length - FLEX[b].length; }).forEach(function(s){ take(FLEX[s]); });
    return {pts: pts, st: st}; }
  function games(r, l){ var s = r.settings || {}, g = (s.wins || 0) + (s.losses || 0) + (s.ties || 0); return (l.settings && l.settings.league_average_match) ? g / 2 : g; }
  function pf(r){ var s = r.settings || {}; return (s.fpts || 0) + (s.fpts_decimal || 0) / 100; }
  function sim(l, teams, sched, n){
    var T = teams.length, sl = slots(l), set = l.settings || {}, spots = Math.max(1, Math.min(T - 1, set.playoff_teams || 6)), median = !!set.league_average_match;
    var gp = Math.max.apply(null, teams.map(function(t){ return games(t.r, l); })), last = (set.playoff_week_start || 15) - 1, tot = 0, tg = 0;
    teams.forEach(function(t){ tot += pf(t.r); tg += games(t.r, l); t.str = lineup(t.ps, sl).pts; });
    var sbar = teams.reduce(function(s, t){ return s + t.str; }, 0) / T, L = tg ? tot / tg : sbar;
    teams.forEach(function(t){ var g = games(t.r, l), own = g ? pf(t.r) / g : L; t.ppg = g ? own : null; t.mu = L + 0.5 * (own - L) + 0.5 * (t.str - sbar); });
    var sd = Math.max(14, 0.19 * L), weeks = [], idx = {}; for(var w = gp + 1; w <= last; w++) weeks.push(w);
    teams.forEach(function(t, i){ idx[t.r.roster_id] = i; });
    var seed = 7 + gp; String(l.league_id || '').split('').forEach(function(c){ seed = (seed * 31 + c.charCodeAt(0)) >>> 0; });
    var R = rng(seed), res = teams.map(function(){ return {inn: 0, w: 0, rank: 0}; }); n = weeks.length ? (n || 3000) : 1;
    for(var k = 0; k < n; k++){
      var W = teams.map(function(t){ var s = t.r.settings || {}; return (s.wins || 0) + 0.5 * (s.ties || 0); }), F = teams.map(function(t){ return pf(t.r); });
      weeks.forEach(function(wk){ var sc = teams.map(function(t){ return t.mu + sd * gauss(R); }), pairs = sched && sched[wk];
        if(!pairs || !pairs.length){ var o = teams.map(function(_, i){ return i; }); for(var i = o.length - 1; i > 0; i--){ var j = Math.floor(R() * (i + 1)), tmp = o[i]; o[i] = o[j]; o[j] = tmp; }
          pairs = []; for(i = 0; i + 1 < o.length; i += 2) pairs.push([teams[o[i]].r.roster_id, teams[o[i + 1]].r.roster_id]); }
        pairs.forEach(function(p){ var a = idx[p[0]], b = idx[p[1]]; if(a == null || b == null) return; if(sc[a] > sc[b]) W[a]++; else W[b]++; });
        if(median){ var m = sc.slice().sort(function(x, y){ return x - y; }), med = (m[Math.floor((T - 1) / 2)] + m[Math.ceil((T - 1) / 2)]) / 2; sc.forEach(function(s, i){ if(s > med) W[i]++; }); }
        sc.forEach(function(s, i){ F[i] += s; }); });
      teams.map(function(_, i){ return i; }).sort(function(a, b){ return (W[b] - W[a]) || (F[b] - F[a]); }).forEach(function(i, pos){ res[i].rank += pos + 1; res[i].w += W[i]; if(pos < spots) res[i].inn++; });
    }
    teams.forEach(function(t, i){ t.po = res[i].inn / n; t.ew = res[i].w / n; t.er = res[i].rank / n; });
    return {weeks: weeks, spots: spots, last: last, gp: gp, L: L, sd: sd, median: median};
  }
  function nowShare(p){ var a = p.ros || 0, b = p.fut || 0; return a + b > 0 ? a / (a + b) : 1; }
  function nearPick(picks, want){ var best = null; (picks || []).forEach(function(p){ if(!(p.v > 0)) return; var r = p.v / Math.max(want, 1); if(r >= 0.6 && r <= 1.25 && (!best || Math.abs(p.v - want) < Math.abs(best.v - want))) best = p; }); return best; }
  function plan(l, teams, info, picks){
    var me = teams.filter(function(t){ return t.me; })[0]; if(!me) return null;
    var ty = l.settings ? l.settings.type : 0, kind = ty === 2 ? 'dynasty' : ty === 1 ? 'keeper' : 'redraft', keep = kind !== 'redraft', sl = slots(l);
    var v = !info.weeks.length ? (me.po >= 0.5 ? 'in' : 'out') : me.po >= 0.7 ? 'buy' : me.po >= 0.35 ? 'bubble' : me.po >= 0.12 ? 'long' : 'out';
    var base = lineup(me.ps, sl), mine = {}, buys = [], sells = []; base.st.forEach(function(x){ mine[x.mp.n] = 1; });
    if(v === 'buy' || v === 'bubble' || v === 'in'){
      var from = teams.filter(function(t){ return !t.me && t.po <= 0.25; }); if(from.length < 2) from = teams.filter(function(t){ return !t.me && t.po < me.po; });
      from.forEach(function(t){ t.ps.forEach(function(x){ if(!avail(x)) return; var g = lineup(me.ps.concat([x]), sl).pts - base.pts; if(g >= 1) buys.push({x: x, t: t, gain: g}); }); });
      buys.sort(function(a, b){ return b.gain - a.gain; }); buys = buys.slice(0, 5);
      var bench = me.ps.filter(function(x){ return x.mp && !mine[x.mp.n] && x.v >= 200; });
      bench.sort(function(a, b){ return b.v - a.v; });
      buys.forEach(function(b){ var want = b.x.v, one = null, two = null; bench.forEach(function(c){ var r = c.v / Math.max(want, 1); if(r >= 0.8 && r <= 1.2 && (!one || Math.abs(c.v - want) < Math.abs(one.v - want))) one = c; });
        // nobody alone: two bench players whose values add up to his (a contender can pay two for one - it also opens a roster spot)
        if(!one){ var top = bench.slice(0, 12); for(var i = 0; i < top.length; i++) for(var j = i + 1; j < top.length; j++){ var sum = top[i].v + top[j].v, r2 = sum / Math.max(want, 1); if(r2 >= 0.9 && r2 <= 1.2 && (!two || Math.abs(sum - want) < Math.abs(two[0].v + two[1].v - want))) two = [top[i], top[j]]; } }
        b.offer = one ? [one] : two; b.pick = b.offer ? null : nearPick(picks, want); });
    }
    if(keep && (v === 'long' || v === 'out')){
      var to = teams.filter(function(t){ return !t.me && t.po >= 0.5; }); if(to.length < 2) to = teams.filter(function(t){ return !t.me && t.po > me.po; });
      var bases = to.map(function(t){ return lineup(t.ps, sl); });
      me.ps.forEach(function(x){ if(!avail(x) || x.v < 400) return; var p = x.mp; if(!((p.age || 0) >= OLD[p.pos] || nowShare(p) >= 0.7)) return;
        var best = null; to.forEach(function(t, i){ var g = lineup(t.ps.concat([x]), sl).pts - bases[i].pts; if(g >= 1 && (!best || g > best.gain)) best = {t: t, gain: g, st: bases[i].st}; });
        if(!best) return; var their = {}, ask = null; best.st.forEach(function(y){ their[y.mp.n] = 1; });
        best.t.ps.forEach(function(y){ if(!y.mp || their[y.mp.n] || !y.mp.age || y.mp.age > 25) return; var r = y.v / Math.max(x.v, 1); if(r >= 0.6 && r <= 1.2 && (!ask || (y.mp.fut || 0) > (ask.mp.fut || 0))) ask = y; });
        sells.push({x: x, t: best.t, gain: best.gain, ask: ask, pick: ask ? null : nearPick(picks, x.v)}); });
      sells.sort(function(a, b){ return b.x.v - a.x.v; }); sells = sells.slice(0, 5);
    }
    return {v: v, kind: kind, keep: keep, me: me, buys: buys, sells: sells, slot: teams.filter(function(t){ return t.er > me.er; }).length + 1, n: teams.length};
  }
  function pct(p, live){ return !live ? (p >= 0.5 ? 'in' : 'out') : p >= 0.995 ? '99%+' : p < 0.005 ? 'under 1%' : Math.round(p * 100) + '%'; }
  function ord(n){ var s = ['th','st','nd','rd'], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
  function who(x){ var p = x.mp; return '<b class="t">' + E(p.n) + '</b> <small>(' + p.pos + (p.age ? ', ' + Math.round(p.age) : '') + ')</small>'; }
  var E = function(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); };
  function html(l, teams, sched, picks){
    var info = sim(l, teams, sched), pl = plan(l, teams, info, picks); if(!pl) return '';
    var me = pl.me, s = me.r.settings || {}, live = info.weeks.length > 0, rec = (s.wins || 0) + '-' + (s.losses || 0) + (s.ties ? '-' + s.ties : '');
    var pfr = teams.slice().sort(function(a, b){ return pf(b.r) - pf(a.r); }).indexOf(me) + 1, one = me.po > 0 ? Math.max(2, Math.round(1 / me.po)) : 0;
    var chip = {buy: ['Buy', ''], 'in': ['Buy', ''], bubble: ['Hold', 'hold'], long: [pl.keep ? 'Sell' : 'Hold', pl.keep ? 'sell' : 'hold'], out: [pl.keep ? 'Sell' : 'Out', pl.keep ? 'sell' : 'hold']}[pl.v];
    var title = {buy: 'You are in the hunt: buy for the playoffs', 'in': 'You are in: buy for the playoffs', bubble: 'On the bubble: buy small, sell nothing',
                 long: pl.keep ? 'A long shot: start selling veterans' : 'A long shot: keep your best lineup', out: pl.keep ? 'Out of it: sell veterans, get younger' : 'Out of it this year'}[pl.v];
    var why = {buy: 'Trade future value for points now. The best targets sit on teams that are out of it, where a veteran is worth less to them than to you.',
               'in': 'The regular season is done and you are in. Any deal now is about the playoff weeks only.',
               bubble: 'Close enough to chase, not safe enough to pay up. Add points where the price is small and keep what you have.',
               long: pl.keep ? 'About a 1 in ' + one + ' shot. Contenders still pay full price for veterans who will not matter to you next year - sell before the deadline.' : 'About a 1 in ' + one + ' shot. Nothing carries over in a redraft league, so there is nothing to sell: play your best lineup and take the upside plays.',
               out: pl.keep ? 'Turn veterans into younger players and picks while contenders will pay. Fewer points now also moves your draft slot up: you are tracking for the ' + ord(pl.slot) + ' pick of ' + pl.n + (pl.kind === 'keeper' ? ' (if your league drafts in reverse order of finish).' : ' in a reverse-standings rookie draft.') : 'Nothing carries over in a redraft league, so there is nothing to sell and no pick to play for. Set your best lineup and play spoiler.'}[pl.v];
    var h = '<div class="olk" id="olk" data-v="' + pl.v + '" data-kind="' + pl.kind + '" data-po="' + me.po.toFixed(4) + '"><span class="vd ' + chip[1] + '">' + chip[0] + '</span><h3>' + title + '</h3>' +
      '<p class="olline"><b>' + rec + '</b> · ' + ord(pfr) + ' of ' + pl.n + ' in points · <b>' + pct(me.po, live) + '</b>' + (live ? ' to make the playoffs' : ' of the playoffs') + ' (' + info.spots + ' of ' + pl.n + ' get in)' +
      (live ? ' · about ' + me.ew.toFixed(1) + ' wins · regular season ends Week ' + info.last : '') + '</p><p class="olwhy">' + why + '</p>';
    if(pl.buys.length){ h += '<h4>Who to trade for</h4><ul>' + pl.buys.map(function(b){ var o = b.offer, ot = !o ? (b.pick ? 'Nobody on your bench matches him. A pick worth about the same: ' + E(b.pick.n) + ' (' + b.pick.v.toLocaleString() + ')' : 'Nobody on your bench matches his value - build the offer above')
          : 'Offer ' + o.map(function(c){ return E(c.mp.n) + ' (' + c.mp.pos + ', ' + c.v.toLocaleString() + ')'; }).join(' and ') + ' off your bench', give = o ? o.map(function(c){ return c.mp.n; }).join(';') : (b.pick ? b.pick.n : '');
        return '<li>' + who(b.x) + ' <span class="gn">+' + b.gain.toFixed(1) + ' pts a week</span> <small>from ' + E(b.t.name) + ' (' + pct(b.t.po, live) + (live ? ' to make it' : '') + ') · value ' + b.x.v.toLocaleString() + '</small>' +
          '<span class="of"><small>' + ot + '</small> <button type="button" class="addbtn" data-ol="' + E(give) + '|' + E(b.x.mp.n) + '">Load</button></span></li>'; }).join('') + '</ul>';
    } else if(pl.v === 'buy' || pl.v === 'bubble' || pl.v === 'in') h += '<p class="none">No player on a team that is out of it would lift your best lineup by a point a week. Your starters are already the strong part.</p>';
    if(pl.sells.length){ h += '<h4>Who to sell, and to whom</h4><ul>' + pl.sells.map(function(b){ var a = b.ask;
        return '<li>' + who(b.x) + ' <small>to ' + E(b.t.name) + ' (' + pct(b.t.po, live) + (live ? ' to make it' : '') + ') · value ' + b.x.v.toLocaleString() + '</small> <span class="gn">+' + b.gain.toFixed(1) + ' pts a week for them</span>' +
          '<span class="of"><small>' + (a ? 'Ask for ' + E(a.mp.n) + ' (' + a.mp.pos + ', ' + Math.round(a.mp.age) + ', ' + a.v.toLocaleString() + ')' : b.pick ? 'Ask for a pick worth about the same: ' + E(b.pick.n) + ' (' + b.pick.v.toLocaleString() + ')' : 'Ask for a pick: nobody young on their bench is near his value') + '</small> <button type="button" class="addbtn" data-ol="' + E(b.x.mp.n) + '|' + E(a ? a.mp.n : b.pick ? b.pick.n : '') + '">Load</button></span></li>'; }).join('') + '</ul>';
    } else if(pl.keep && (pl.v === 'long' || pl.v === 'out')) h += '<p class="none">No veteran on your roster would lift a contender\'s lineup by a point a week, so there is no obvious sale. Hold your young players.</p>';
    h += '<details><summary>Every team\'s playoff odds</summary><table>' + teams.slice().sort(function(a, b){ return (b.po - a.po) || (b.ew - a.ew); }).map(function(t){ var ts = t.r.settings || {};
        return '<tr class="' + (t.me ? 'me' : '') + '"><td>' + E(t.name) + (t.me ? ' (you)' : '') + '</td><td class="r">' + (ts.wins || 0) + '-' + (ts.losses || 0) + '</td><td class="r">' + (t.ppg == null ? '' : t.ppg.toFixed(1)) + '</td><td class="r">' + pct(t.po, live) + '<span class="bar"><i style="width:' + Math.round(t.po * 100) + '%"></i></span></td></tr>'; }).join('') +
      '</table><p class="none">' + (live ? 'The weeks left were played 3,000 times on your league\'s schedule. Each team scores around a mean that is half its points per game so far and half the strength of its best lineup by this model' + (info.median ? ', with the extra game against the weekly median' : '') + '. ' : '') + 'Columns: record, points per game, playoff odds.</p></details></div>';
    return h;
  }
  // One league's verdict in a word, for a list of many leagues (fantasy_nav.py's league sheet): the same odds and the same cut-offs
  // as the card - 70 / 35 / 12% - without the trade search. n = sims (1,500 is plenty for a chip). null when the reader has no roster.
  function quick(l, teams, sched, n){ var me = teams.filter(function(t){ return t.me; })[0]; if(!me) return null;
    var info = sim(l, teams, sched, n || 1500), ty = l.settings ? l.settings.type : 0, keep = ty === 1 || ty === 2, live = info.weeks.length > 0;
    var v = !live ? (me.po >= 0.5 ? 'in' : 'out') : me.po >= 0.7 ? 'buy' : me.po >= 0.35 ? 'bubble' : me.po >= 0.12 ? 'long' : 'out';
    var chip = {buy: ['Buy', 'buy'], 'in': ['Buy', 'buy'], bubble: ['Hold', 'hold'], long: [keep ? 'Sell' : 'Hold', keep ? 'sell' : 'hold'], out: [keep ? 'Sell' : 'Out', keep ? 'sell' : 'hold']}[v];
    return {v: v, txt: chip[0], cls: chip[1], po: me.po, pct: pct(me.po, live), live: live}; }
  return {sim: sim, plan: plan, quick: quick, lineup: lineup, slots: slots, games: games, pf: pf, html: html};
})();
"""
