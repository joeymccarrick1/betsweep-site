#!/usr/bin/env python3
"""build_survivor.py - the Survivor planner (owner 11/10: "I just want betsweep to help me optimize in leagues I'm already in").

Elimination / survivor pools: one team to win each week, never the same team twice. The hard part is not this week's pick, it is
not burning a team you will need later. The page takes the teams you have already used and gives, for every pool you keep on it:
  - this week's options ranked by the chance of getting through the whole run if you take that team now
  - the best team for every week left (an exact assignment: weeks x teams, maximising the product of the win chances)

Win chances (nothing here is a pick, and nothing is invented):
  - the current week: FanDuel's moneylines with the vig removed (in/gamelines.json, the same pull the builder uses); a game without one
    falls back to the closing spread in the schedule, then to the ratings below
  - later weeks: team ratings fitted to this season's FanDuel-era closing spreads (nflverse schedule, in/games.csv) - ridge least
    squares, recent weeks weighted more, one home-field number - turned into a win chance with the usual 13.5-point spread of NFL
    margins. They are ESTIMATES (marked "est." on the page) and move every rebuild as new lines close; injuries that have not reached
    a closing line yet are not in them.
Reads in/games.csv, in/gamelines.json, out/builder_data.json (the week). Writes out/survivor.html (placed at /survivor/ by
build_site.py) and out/survivor.json. Prints one line for the run log.
"""
import json, os, csv, math, datetime, html
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
E = html.escape
exec(open(os.path.join(HERE, "brand.py")).read())   # NAMES, TEAMCOL
SD = 13.5          # NFL final margin around the spread: standard deviation in points (2026 Weeks 1-9: favourites won 69% vs 63% predicted - inside the noise of 136 games)
DECAY = 0.85       # a closing line from k weeks ago weighs 0.85^k (teams change: quarterbacks, injuries)
RIDGE = 0.05       # pulls ratings gently to 0 so a team with few lines cannot run away
def phi(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
def num(x):
    try: return float(str(x).replace("+", "").strip())
    except Exception: return None

try: WEEK = int(json.load(open(os.path.join(OUT, "builder_data.json"))).get("week") or 0)
except Exception: WEEK = 0
rows = [r for r in csv.DictReader(open(os.path.join(IN, "games.csv"), newline="")) if r.get("season") == "2026" and r.get("game_type") == "REG"]
if not WEEK:   # no builder data: the first week with a game that has no result yet
    WEEK = min([int(r["week"]) for r in rows if (r.get("result") or "") in ("", "NA")] or [18])
LAST = max(int(r["week"]) for r in rows)
TEAMS = sorted({r["home_team"] for r in rows} | {r["away_team"] for r in rows})

# ---- ratings from the season's closing spreads (home spread, positive = home favoured) ----
obs = []
for r in rows:
    sp = num(r.get("spread_line")); w = int(r["week"])
    if sp is None or w > WEEK: continue
    neutral = str(r.get("location") or "").strip().lower() == "neutral"
    obs.append((r["home_team"], r["away_team"], sp, 0.0 if neutral else 1.0, DECAY ** (WEEK - w)))
idx = {t: i for i, t in enumerate(TEAMS)}; n = len(TEAMS) + 1   # last column = home field
A = [[0.0] * n for _ in range(n)]; B = [0.0] * n
for h, a, sp, hf, wt in obs:
    x = [0.0] * n; x[idx[h]] = 1.0; x[idx[a]] = -1.0; x[n - 1] = hf
    for i in range(n):
        if x[i] == 0.0: continue
        B[i] += wt * x[i] * sp
        for j in range(n):
            if x[j] != 0.0: A[i][j] += wt * x[i] * x[j]
for i in range(n - 1): A[i][i] += RIDGE
A[n - 1][n - 1] += 1e-9
def solve(A, B):
    n = len(B); M = [row[:] + [B[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12: continue
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c and M[r][c]:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1): M[r][k] -= f * M[c][k]
    return [(M[i][n] / M[i][i]) if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]
sol = solve(A, B) if obs else [0.0] * n
RATE = {t: sol[idx[t]] for t in TEAMS}; HFA = sol[n - 1] if obs else 1.5
mean = sum(RATE.values()) / len(RATE) if RATE else 0.0
RATE = {t: v - mean for t, v in RATE.items()}
fit = [(sp - (RATE[h] - RATE[a] + HFA * hf)) for h, a, sp, hf, wt in obs if wt >= DECAY ** 3]   # how well the ratings reproduce the last four weeks' lines
rmse = math.sqrt(sum(e * e for e in fit) / len(fit)) if fit else None

# ---- this week's FanDuel moneylines, vig removed ----
FD = {}
try:
    import gamelines as GLM
    gv = json.load(open(os.path.join(IN, "gamelines.json")))["values"]; H = {c: i for i, c in enumerate(gv[0])}
    ml = {}
    for r in gv[1:]:
        r = r + [""] * (len(gv[0]) - len(r))
        if r[H["Market"]] != "Moneyline": continue
        aw, _, hm = str(r[H["Game"]]).partition(" @ "); a_, h_ = GLM.TEAM_FULL.get(aw.strip()), GLM.TEAM_FULL.get(hm.strip()); side = GLM.TEAM_FULL.get(str(r[H["Side"]]).strip()); o = num(r[H["FanDuel odds"]])
        if a_ and h_ and side and o: ml.setdefault(frozenset([a_, h_]), {})[side] = o
    for k, d in ml.items():
        if len(d) != 2: continue
        imp = {t: (100 / (o + 100) if o > 0 else -o / (-o + 100)) for t, o in d.items()}; s = sum(imp.values())
        FD[k] = {t: v / s for t, v in imp.items()}
except Exception as _e: print("survivor: FanDuel moneylines unavailable, using the schedule's lines:", _e)

def ko_ms(r):
    try: return int(datetime.datetime.fromisoformat(r["gameday"] + "T" + r["gametime"]).replace(tzinfo=ZoneInfo("America/New_York")).timestamp() * 1000)
    except Exception: return None
def kick(ms):
    return datetime.datetime.fromtimestamp(ms / 1000, ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p") if ms else ""

WEEKS = {}; nfd = nsp = nest = 0
for r in sorted(rows, key=lambda r: (int(r["week"]), r["gameday"], r["gametime"])):
    w = int(r["week"])
    if w < WEEK: continue
    h, a = r["home_team"], r["away_team"]; neutral = str(r.get("location") or "").strip().lower() == "neutral"
    est_sp = RATE[h] - RATE[a] + (0 if neutral else HFA)
    src = "est"; ph = phi(est_sp / SD); sp = est_sp
    if w == WEEK and FD.get(frozenset([h, a])): ph = FD[frozenset([h, a])][h]; src = "fd"; nfd += 1; sp = num(r.get("spread_line")) if num(r.get("spread_line")) is not None else est_sp
    elif num(r.get("spread_line")) is not None: sp = num(r["spread_line"]); ph = phi(sp / SD); src = "line"; nsp += 1
    else: nest += 1
    fin = (r.get("result") or "") not in ("", "NA")
    ms = ko_ms(r)
    WEEKS.setdefault(w, []).append({"h": h, "a": a, "nt": 1 if neutral else 0, "ko": ms, "k": kick(ms), "p": round(ph, 4), "s": src, "sp": round(sp, 1), "fin": 1 if fin else 0})
DATA = {"week": WEEK, "last": LAST, "built": datetime.datetime.now(ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p"), "sd": SD,
        "teams": {t: {"n": NAMES.get(t, t), "c": list(TEAMCOL.get(t, ("#444", "#999")))} for t in TEAMS},
        "weeks": {str(w): g for w, g in sorted(WEEKS.items())},
        "rate": {t: round(v, 2) for t, v in sorted(RATE.items(), key=lambda kv: -kv[1])}, "hfa": round(HFA, 2)}
json.dump(DATA, open(os.path.join(OUT, "survivor.json"), "w"), separators=(",", ":"))

CSS = """
.sv{max-width:980px;margin:18px auto 40px}
.sv h1{font-family:var(--brand);font-style:italic;font-weight:800;font-size:34px;line-height:1;margin:0 0 6px;letter-spacing:-.01em}
.sv .lead{color:var(--mute);line-height:1.5;margin:0 0 14px;max-width:720px}
.sv h2{font-family:var(--display);font-weight:800;font-size:15px;letter-spacing:.12em;text-transform:uppercase;margin:22px 0 8px;color:var(--mute)}
.sv .pools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 10px}
.sv .pools button{font:inherit;font-family:var(--display);font-weight:700;font-size:13.5px;letter-spacing:.05em;text-transform:uppercase;min-height:38px;padding:0 13px;border-radius:8px;border:1.5px solid var(--line);background:none;color:var(--ink);cursor:pointer}
.sv .pools button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.sv .pools button.add{border-style:dashed;color:var(--mute)}
.sv .row{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin:8px 0 4px;font-size:14px;color:var(--mute)}
.sv .row select{font:inherit;min-height:38px;padding:0 8px;border-radius:8px;border:1.5px solid var(--line);background:var(--card);color:var(--ink)}
.sv .row button{font:inherit;font-size:13px;min-height:38px;padding:0 11px;border-radius:8px;border:1.5px solid var(--line);background:none;color:var(--ink);cursor:pointer}
.sv .teams{display:grid;grid-template-columns:repeat(auto-fill,minmax(74px,1fr));gap:7px}
.sv .teams button{font:inherit;font-family:var(--display);font-weight:800;font-size:15px;letter-spacing:.04em;min-height:44px;border-radius:9px;border:1.5px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer;border-left:6px solid var(--tc,var(--line))}
.sv .teams button.used{background:none;color:var(--mute);text-decoration:line-through;opacity:.62;border-style:dashed;border-left-style:solid}
.sv .hint{color:var(--mute);font-size:13px;margin:6px 0 0;line-height:1.45}
.sv .call{margin:14px 0 6px;padding:14px 16px;border:2px solid var(--red);border-radius:14px;background:var(--card)}
.sv .call small{display:block;font-family:var(--display);font-weight:800;font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--mute);margin-bottom:4px}
.sv .call b.pick{font-family:var(--brand);font-style:italic;font-weight:800;font-size:30px;line-height:1.05;letter-spacing:-.01em;display:block}
.sv .call p{margin:6px 0 0;line-height:1.5;font-size:14.5px}
.sv .tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
.sv table{width:100%;border-collapse:collapse;font-size:14px}
.sv th{text-align:left;font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--mute);padding:6px 8px;border-bottom:1.5px solid var(--line);white-space:nowrap}
.sv td{padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.sv td.n{font-variant-numeric:tabular-nums;white-space:nowrap}
.sv tr.sel td{background:color-mix(in srgb,var(--red) 9%,transparent)}
.sv tr.opt{cursor:pointer}
.sv td b.t{font-family:var(--display);font-weight:800;font-size:16px;letter-spacing:.03em}
.sv td small{display:block;color:var(--mute);font-size:12px;margin-top:1px}
.sv .tag{display:inline-block;font-family:var(--display);font-weight:700;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;border:1px solid var(--line);border-radius:99px;padding:1px 7px;color:var(--mute);margin-left:6px;vertical-align:middle}
.sv .tag.best{border-color:var(--red);color:var(--ink)}
.sv .est{color:var(--mute)}
.sv .none{color:var(--mute);line-height:1.5}
.sv .fn{color:var(--mute);font-size:12.5px;line-height:1.5;margin-top:14px}
.sv .fn a{color:var(--ink)}
@media (max-width:560px){ .sv h1{font-size:29px} .sv td,.sv th{padding:8px 6px} .sv .hidem{display:none} }
"""

JS = r"""
(function(){
  var D = window.__SV, T = D.teams, ALL = Object.keys(T).sort(), KEY = 'bs_survivor', $ = function(s){ return document.querySelector(s); };
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function pct(p){ return p >= 0.995 ? '99%+' : p < 0.0005 ? '<0.1%' : p < 0.1 ? (p * 100).toFixed(1) + '%' : Math.round(p * 100) + '%'; }
  // ---- saved state: several pools, each with its own used teams and its last week ----
  var S; try { S = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch(e){ S = null; }
  if(!S || !Array.isArray(S.pools) || !S.pools.length) S = {cur: 0, pools: [{name: 'My pool', used: [], to: D.last, pick: {}}]};
  S.pools.forEach(function(p){ p.used = (p.used || []).filter(function(t){ return T[t]; }); p.to = Math.min(D.last, Math.max(D.week, +p.to || D.last)); p.pick = p.pick || {}; });
  if(!(S.cur >= 0 && S.cur < S.pools.length)) S.cur = 0;
  function save(){ try { localStorage.setItem(KEY, JSON.stringify(S)); } catch(e){} }
  function P(){ return S.pools[S.cur]; }
  // ---- the week to plan from: the first week that still has a game to kick off ----
  function openGames(w){ var t = Date.now(); return (D.weeks[w] || []).filter(function(g){ return !g.fin && (!g.ko || g.ko > t); }); }
  function firstWeek(){ for(var w = D.week; w <= D.last; w++){ if(openGames(w).length) return w; } return null; }
  // ---- win chance table: week -> team -> {p, opp, home, src, k} (only games that have not kicked off) ----
  function table(from, to){ var M = {}; for(var w = from; w <= to; w++){ var m = M[w] = {}; (w === from ? openGames(w) : (D.weeks[w] || [])).forEach(function(g){
      m[g.h] = {p: g.p, opp: g.a, at: g.nt ? 'vs' : 'vs', home: !g.nt, s: g.s, k: g.k, sp: g.sp}; m[g.a] = {p: 1 - g.p, opp: g.h, at: g.nt ? 'vs' : '@', home: false, s: g.s, k: g.k, sp: -g.sp}; }); } return M; }
  // ---- exact assignment (Hungarian, rows = weeks, columns = teams): the set of picks with the highest product of win chances ----
  function assign(cost){ var n = cost.length, m = cost[0].length, INF = 1e18, u = [], v = [], p = [], way = [], i, j;
    for(i = 0; i <= n; i++) u.push(0); for(j = 0; j <= m; j++){ v.push(0); p.push(0); way.push(0); }
    for(i = 1; i <= n; i++){ p[0] = i; var j0 = 0, minv = [], used = []; for(j = 0; j <= m; j++){ minv.push(INF); used.push(false); }
      do { used[j0] = true; var i0 = p[j0], delta = INF, j1 = 0;
        for(j = 1; j <= m; j++) if(!used[j]){ var cur = cost[i0 - 1][j - 1] - u[i0] - v[j]; if(cur < minv[j]){ minv[j] = cur; way[j] = j0; } if(minv[j] < delta){ delta = minv[j]; j1 = j; } }
        for(j = 0; j <= m; j++){ if(used[j]){ u[p[j]] += delta; v[j] -= delta; } else minv[j] -= delta; }
        j0 = j1; } while(p[j0] !== 0);
      do { var j2 = way[j0]; p[j0] = p[j2]; j0 = j2; } while(j0); }
    var ans = []; for(i = 0; i < n; i++) ans.push(-1); for(j = 1; j <= m; j++) if(p[j]) ans[p[j] - 1] = j - 1; return ans; }
  var BIG = 50;   // -ln of an impossible pick; a plan that needs one is reported as "no team left"
  function best(M, weeks, banned){ if(!weeks.length) return {lp: 0, picks: {}, ok: true};
    var cost = weeks.map(function(w){ return ALL.map(function(t){ var x = M[w][t]; return (!x || banned[t] || x.p <= 0) ? BIG : -Math.log(x.p); }); });
    var a = assign(cost), lp = 0, picks = {}, ok = true;
    weeks.forEach(function(w, i){ var c = cost[i][a[i]]; if(a[i] < 0 || c >= BIG){ ok = false; return; } lp -= c; picks[w] = ALL[a[i]]; });
    return {lp: lp, picks: picks, ok: ok}; }
  // ---- render ----
  var sel = null;   // the team the user tapped for this week (null = the planner's own best)
  function render(){
    var p = P(), from = firstWeek(), poolsEl = $('#svpools');
    poolsEl.innerHTML = S.pools.map(function(x, i){ return '<button type="button" data-i="' + i + '" class="' + (i === S.cur ? 'on' : '') + '">' + esc(x.name) + '</button>'; }).join('') + (S.pools.length < 6 ? '<button type="button" class="add" data-add="1">+ Add a pool</button>' : '');
    var usedSet = {}; p.used.forEach(function(t){ usedSet[t] = 1; });
    $('#svteams').innerHTML = ALL.map(function(t){ return '<button type="button" data-t="' + t + '" class="' + (usedSet[t] ? 'used' : '') + '" style="--tc:' + esc(T[t].c[0]) + '" title="' + esc(T[t].n) + '" aria-pressed="' + (usedSet[t] ? 'true' : 'false') + '">' + t + '</button>'; }).join('');
    $('#svused').textContent = p.used.length ? p.used.length + ' used: ' + p.used.slice().sort().join(', ') : 'None marked yet. Tap every team you have already picked in this pool.';
    var toSel = $('#svto'), o = ''; for(var w = (from || D.week); w <= D.last; w++) o += '<option value="' + w + '"' + (w === p.to ? ' selected' : '') + '>Week ' + w + (w === D.last ? ' (end of the regular season)' : '') + '</option>'; toSel.innerHTML = o;
    var out = $('#svout');
    if(from === null){ out.innerHTML = '<p class="none">The regular season is over - nothing left to plan.</p>'; return; }
    var to = Math.max(from, Math.min(p.to, D.last)), weeks = []; for(w = from; w <= to; w++) weeks.push(w);
    var M = table(from, to), rest = weeks.slice(1), cands = [];
    Object.keys(M[from]).forEach(function(t){ if(usedSet[t]) return; var b = {}; for(var k in usedSet) b[k] = 1; b[t] = 1;
      var r = best(M, rest, b); cands.push({t: t, x: M[from][t], lp: Math.log(M[from][t].p) + r.lp, ok: r.ok, picks: r.picks}); });
    if(!cands.length){ out.innerHTML = '<p class="none">No team is left for Week ' + from + ': every team that still has a game to play this week is marked as used.</p>'; return; }
    cands.sort(function(a, b){ return (b.ok - a.ok) || (b.lp - a.lp); });
    var top = cands[0], safest = cands.slice().sort(function(a, b){ return b.x.p - a.x.p; })[0];
    if(sel && !cands.some(function(c){ return c.t === sel; })) sel = null;
    var cur = sel ? cands.filter(function(c){ return c.t === sel; })[0] : top;
    function vs(t, x){ return (x.at === '@' ? '@ ' : 'vs ') + x.opp; }
    function src(x){ return x.s === 'fd' ? '' : ' <span class="est" title="' + (x.s === 'line' ? 'from the closing spread' : 'estimated from this season’s closing lines') + '">est.</span>'; }
    var planned = {}; Object.keys(top.picks).forEach(function(w){ planned[top.picks[w]] = +w; }); planned[top.t] = from;
    var one = weeks.length === 1, h = '';
    h += '<div class="call"><small>Week ' + from + ' · ' + esc(p.name) + '</small><b class="pick">' + esc(T[top.t].n) + ' <span style="font-size:.6em;font-style:normal;opacity:.7">' + top.t + ' ' + esc(vs(top.t, top.x)) + '</span></b>'
       + '<p>' + pct(top.x.p) + ' to win this week' + (top.x.s === 'fd' ? ' at FanDuel’s line' : ' (estimate)') + (one ? '.' : '. Taking them now leaves the best road through Week ' + to + ': <b>' + pct(Math.exp(top.lp)) + '</b> to survive every week' + (top.ok ? '' : ' - but some later week has no team left') + '.') + '</p>'
       + ((safest.t !== top.t && !one) ? '<p>The safest pick this week is ' + esc(T[safest.t].n) + ' (' + pct(safest.x.p) + '), but ' + (planned[safest.t] && planned[safest.t] !== from ? 'the plan wants them in Week ' + planned[safest.t] + ': ' : '') + 'taking them now drops the whole run from ' + pct(Math.exp(top.lp)) + ' to ' + pct(Math.exp(safest.lp)) + '.</p>' : '')
       + '</div>';
    h += '<h2>Week ' + from + ' options</h2><div class="tw"><table><thead><tr><th>Team</th><th>Win this week</th>' + (one ? '' : '<th>Survive to Wk ' + to + '</th><th class="hidem">Plan wants them</th>') + '</tr></thead><tbody>';
    cands.slice(0, 14).forEach(function(c, i){ h += '<tr class="opt' + (c.t === cur.t ? ' sel' : '') + '" data-pick="' + c.t + '"><td><b class="t">' + c.t + '</b> ' + esc(vs(c.t, c.x)) + (i === 0 ? '<span class="tag best">Best</span>' : '') + (c.t === safest.t && i !== 0 ? '<span class="tag">Safest</span>' : '') + '<small>' + esc(c.x.k) + '</small></td><td class="n">' + pct(c.x.p) + src(c.x) + '</td>'
        + (one ? '' : '<td class="n">' + (c.ok ? pct(Math.exp(c.lp)) : 'no team left later') + '</td><td class="n hidem">' + (planned[c.t] ? (planned[c.t] === from ? 'now' : 'Week ' + planned[c.t]) : '—') + '</td>') + '</tr>'; });
    h += '</tbody></table></div><p class="hint">Tap a team to see the road if you take it this week.' + (cands.length > 14 ? ' Showing the best 14 of ' + cands.length + '.' : '') + '</p>';
    if(!one){ var run = Math.log(cur.x.p), cum = cur.x.p;
      h += '<h2>The road if you take ' + cur.t + '</h2><div class="tw"><table><thead><tr><th>Week</th><th>Pick</th><th>Win</th><th>Still alive</th></tr></thead><tbody>';
      h += '<tr class="sel"><td class="n">' + from + '</td><td><b class="t">' + cur.t + '</b> ' + esc(vs(cur.t, cur.x)) + '<small>' + esc(cur.x.k) + '</small></td><td class="n">' + pct(cur.x.p) + src(cur.x) + '</td><td class="n">' + pct(cum) + '</td></tr>';
      rest.forEach(function(w){ var t = cur.picks[w]; if(!t){ h += '<tr><td class="n">' + w + '</td><td colspan="3" class="est">no team left</td></tr>'; return; } var x = M[w][t]; cum *= x.p;
        h += '<tr><td class="n">' + w + '</td><td><b class="t">' + t + '</b> ' + esc(vs(t, x)) + '<small>' + esc(x.k) + '</small></td><td class="n">' + pct(x.p) + src(x) + '</td><td class="n">' + pct(cum) + '</td></tr>'; });
      h += '</tbody></table></div>'; }
    out.innerHTML = h;
  }
  document.addEventListener('click', function(e){
    var b = e.target.closest && e.target.closest('button, tr.opt'); if(!b || !b.closest('.sv')) return;
    if(b.dataset.t){ var p = P(), i = p.used.indexOf(b.dataset.t); if(i >= 0) p.used.splice(i, 1); else p.used.push(b.dataset.t); sel = null; save(); render(); }
    else if(b.dataset.i != null && b.closest('#svpools')){ S.cur = +b.dataset.i; sel = null; save(); render(); }
    else if(b.dataset.add){ var nm = window.prompt('Name this pool', 'Pool ' + (S.pools.length + 1)); if(nm === null) return; S.pools.push({name: (nm || 'Pool ' + (S.pools.length + 1)).slice(0, 30), used: [], to: D.last, pick: {}}); S.cur = S.pools.length - 1; sel = null; save(); render(); }
    else if(b.id === 'svrename'){ var n2 = window.prompt('Pool name', P().name); if(n2){ P().name = n2.slice(0, 30); save(); render(); } }
    else if(b.id === 'svclear'){ if(window.confirm('Clear the used teams for "' + P().name + '"?')){ P().used = []; sel = null; save(); render(); } }
    else if(b.id === 'svdel'){ if(S.pools.length > 1 && window.confirm('Remove "' + P().name + '" from this page?')){ S.pools.splice(S.cur, 1); S.cur = 0; sel = null; save(); render(); } }
    else if(b.dataset.pick){ sel = b.dataset.pick; render(); }
  });
  $('#svto').addEventListener('change', function(){ P().to = +this.value; sel = null; save(); render(); });
  window.addEventListener('storage', function(e){ if(e.key === KEY){ try { var n = JSON.parse(e.newValue); if(n && n.pools) { S = n; render(); } } catch(_){} } });
  document.addEventListener('bs-account', function(e){ if(e.detail && e.detail.changed){ try { var n = JSON.parse(localStorage.getItem(KEY) || 'null'); if(n && n.pools){ S = n; render(); } } catch(_){} } });
  render();
})();
"""

try:
    import account as ACCT; _link, _base = ACCT._base_css()
except Exception: _link, _base = "", ""
rt = sorted(RATE.items(), key=lambda kv: -kv[1])
rate_rows = "".join(f'<tr><td class="n">{i + 1}</td><td><b class="t">{E(t)}</b> {E(NAMES.get(t, t))}</td><td class="n">{v:+.1f}</td></tr>' for i, (t, v) in enumerate(rt))
page = f"""<title>Survivor planner · BetSweep</title>
<meta name="description" content="Survivor and elimination pools: mark the teams you have used and get the best pick this week plus the best team for every week left, from FanDuel's lines and this season's closing spreads.">
{_link}
<style>{_base}
{CSS}</style>
<div class="sv">
<h1>Survivor planner</h1>
<p class="lead">For elimination pools where you pick one team to win each week and can never use a team twice. Mark the teams you have already used. You get the best pick this week and the best team for every week left, so you do not burn one you will need later.</p>
<div class="pools" id="svpools"></div>
<div class="row"><span>Plan through</span><select id="svto" aria-label="Last week of the pool"></select><button type="button" id="svrename">Rename</button><button type="button" id="svclear">Clear used teams</button><button type="button" id="svdel">Remove pool</button></div>
<h2>Teams you have used</h2>
<div class="teams" id="svteams"></div>
<p class="hint" id="svused"></p>
<div id="svout"></div>
<details style="margin-top:22px"><summary style="cursor:pointer;color:var(--mute);font-size:13.5px">Team ratings behind the later weeks</summary>
<div class="tw"><table style="max-width:420px"><thead><tr><th>#</th><th>Team</th><th>Points vs average</th></tr></thead><tbody>{rate_rows}</tbody></table></div>
<p class="hint">Home field is worth {HFA:+.1f} points in these lines.{f" Over the last four weeks the ratings land within {rmse:.1f} points of the actual closing spread on average." if rmse is not None else ""}</p></details>
<p class="fn">Week {WEEK} win chances are FanDuel's moneylines with the vig removed. Later weeks are estimates ("est."): team ratings fitted to this season's closing spreads, recent weeks counted more, turned into a win chance. They move every rebuild as new lines close, and an injury that has not reached a closing line yet is not in them. "Survive" is the chance of winning every pick on the road shown; it does not know what the rest of your pool picks. Your pools are saved on this device (and to your account when you are signed in). Built {E(DATA["built"])} CT. Information, not betting advice. <a href="/how/">How BetSweep picks</a></p>
</div>
<script>window.__SV = {json.dumps(DATA, separators=(",", ":"))};</script>
<script>{JS}</script>
"""
open(os.path.join(OUT, "survivor.html"), "w").write(page)
print(f"wrote out/survivor.html: week {WEEK}-{LAST}, {sum(len(g) for g in WEEKS.values())} games ({nfd} FanDuel moneylines, {nsp} closing spreads, {nest} estimated), {len(obs)} lines behind the ratings, home field {HFA:+.2f}" + (f", ratings vs last four weeks' lines rmse {rmse:.2f}" if rmse is not None else ""))
