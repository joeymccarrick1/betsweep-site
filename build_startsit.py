"""/team/compare/ - "Who should I start?" (owner 11/1: "just 2 search bars. You search for a player and it gives you the player, matchup,
stats. Compare them and give a reason why you pick that player. Also add a + to add a 3rd, 4th ... The objective is who to play in someone's
flex position or potentially start ... give them the info and a suggestion").

Called from build_team.py (build(PLAYERS, WEEK, IN, OUT)) after the fantasy projections are final. Writes:
  out/startsit.html  - the page (build_site places it at /team/compare/)
  out/startsit.json  - one row per active QB/RB/WR/TE: this week's projection and stat line (from build_team), matchup ranks, availability,
                       last-4 games (fantasy points full PPR, snaps, carries / targets), season average, a floor / ceiling from his own
                       game-to-game spread, and his flags (flags.py: good / bad / watch tags with text)
The pick is made in the browser so league scoring (full / half / standard) and the "safe floor / need upside" switch re-rank instantly.
Nothing here changes a projection: it only lays the model's numbers side by side and explains the call.
"""
import csv, json, os, re, statistics

def nn(x):
    x = re.sub(r"\.", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
def num(x):
    try: return float(str(x).replace(",", ""))
    except Exception: return None
def slug(n):
    s = re.sub(r"\.", "", n.lower()); s = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", s); return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

def build(PLAYERS, WEEK, IN, OUT):
    def vals(n):
        p = os.path.join(IN, n)
        if not os.path.exists(p): return []
        d = json.load(open(p)); return d.get("values", d) if isinstance(d, dict) else d
    G = vals("gamelog.json"); H = {k: i for i, k in enumerate(G[0])} if G else {}
    g = lambda r, k: (num(r[H[k]]) or 0) if k in H and H[k] < len(r) else 0
    logs = {}
    for r in G[1:]:
        if not r or not r[0] or num(r[0]) is None or int(num(r[0])) >= WEEK: continue
        logs.setdefault(nn(r[1]), []).append(r)
    snaps = {}
    try:
        for r in csv.DictReader(open(os.path.join(IN, "snap_counts_2026.csv"))):
            if r.get("game_type") == "REG" and num(r.get("offense_pct")) is not None: snaps[(nn(r["player"]), int(r["week"]))] = num(r["offense_pct"])
    except Exception: pass
    try:
        import flags as FL
        FE = FL.Engine(IN, WEEK)
    except Exception as e:
        print("note: flags unavailable on /team/compare/:", e); FE = None
    rows = []
    for p in PLAYERS:
        if p.get("p") not in ("QB", "RB", "WR", "TE"): continue
        k = nn(p["n"]); gl = sorted(logs.get(k, []), key=lambda r: num(r[0]))
        games = []
        for r in gl:
            fp = 0.04 * g(r, "Pass Yds") + 4 * g(r, "Pass TD") - 2 * g(r, "INT") + 0.1 * g(r, "Rush Yds") + 6 * g(r, "Rush TD") + g(r, "Receptions") + 0.1 * g(r, "Rec Yds") + 6 * g(r, "Rec TD") + 2 * g(r, "Pass 2PT")
            w = int(num(r[0]))
            games.append({"w": w, "o": r[H["Opponent"]] if "Opponent" in H else "", "fp": round(fp, 1), "rec": g(r, "Receptions"),
                          "car": g(r, "Rush Att"), "tgt": g(r, "Targets"), "att": g(r, "Pass Att"), "yd": g(r, "Pass Yds") + g(r, "Rush Yds") + g(r, "Rec Yds"),
                          "td": g(r, "Pass TD") + g(r, "Rush TD") + g(r, "Rec TD"), "sn": snaps.get((k, w))})
        fps = [x["fp"] for x in games]
        sd = statistics.pstdev(fps) if len(fps) >= 3 else None
        fl = []
        if FE:
            try: fl = [[f["k"], f["tag"], f["txt"]] for f in FE.player(p["n"], p["t"], p["p"], p["o"]) if f["k"] in ("good", "bad", "watch")][:6]
            except Exception: fl = []
        rows.append({"n": p["n"], "t": p["t"], "p": p["p"], "o": p["o"], "k": p.get("k", ""), "fp": p["fp"], "rec": p.get("rec", 0),
                     "py": p.get("py", 0), "ptd": p.get("ptd", 0), "ry": p.get("ry", 0), "rtd": p.get("rtd", 0), "rcy": p.get("rcy", 0), "rctd": p.get("rctd", 0),
                     "act": p.get("act"), "av": p.get("av", ""), "st": p.get("st", ""), "role": p.get("role", ""), "dr": p.get("dr"), "or": p.get("or"), "sos": p.get("sos", 0),
                     "avg": round(sum(fps) / len(fps), 1) if fps else None, "gp": len(fps), "sd": round(sd, 1) if sd is not None else None,
                     "g": games[-4:], "fl": fl, "s": slug(p["n"])})
    rows.sort(key=lambda r: -(r["fp"] or 0))
    json.dump({"week": WEEK, "players": rows}, open(os.path.join(OUT, "startsit.json"), "w"), separators=(",", ":"))
    open(os.path.join(OUT, "startsit.html"), "w").write(page(WEEK))
    print(f"wrote out/startsit.html + startsit.json: {len(rows)} players for week {WEEK}")

CSS = r"""
.ss{max-width:1100px;margin:0 auto;padding:14px 16px 30px}
.ss h1{font-family:var(--display);font-weight:800;letter-spacing:.04em;text-transform:uppercase;font-size:clamp(22px,4.5vw,30px);margin:6px 0 2px}
.ss .sub{color:var(--mute);font-size:14px;line-height:1.5;margin:0 0 12px}
.ss .ctl{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin:0 0 12px;font-size:13px;color:var(--mute)}
.ss .seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.ss .seg button{font:inherit;font-size:13px;padding:6px 10px;border:0;background:var(--card);color:var(--ink);cursor:pointer}
.ss .seg button.on{background:var(--ink);color:var(--paper,#fff)}
.ss .slots{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}
.ss .slot{position:relative}
.ss .slot input{width:100%;box-sizing:border-box;font:inherit;font-size:16px;color:var(--ink);background:var(--card);border:1.5px solid var(--line);border-radius:10px;padding:11px 36px 11px 12px}
.ss .slot input:focus{outline:none;border-color:var(--red)}
.ss .slot .x{position:absolute;right:6px;top:7px;border:0;background:none;color:var(--mute);font-size:20px;cursor:pointer;line-height:1;padding:4px 6px}
.ss .sug{position:absolute;left:0;right:0;top:calc(100% + 2px);z-index:20;background:var(--card);border:1px solid var(--line);border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.18);max-height:300px;overflow:auto}
.ss .sug button{display:flex;width:100%;gap:8px;align-items:center;text-align:left;font:inherit;font-size:14px;padding:9px 12px;border:0;background:none;color:var(--ink);cursor:pointer;border-bottom:1px solid var(--line)}
.ss .sug button:hover,.ss .sug button.hi{background:var(--chalk,rgba(0,0,0,.05))}
.ss .sug small{color:var(--mute);margin-left:auto;white-space:nowrap}
.ss .add{font:inherit;font-family:var(--display);font-weight:700;letter-spacing:.06em;text-transform:uppercase;font-size:14px;border:1.5px dashed var(--line);background:none;color:var(--ink);border-radius:10px;padding:11px;cursor:pointer;min-height:46px}
.ss .verdict{margin:14px 0 10px;border-radius:12px;padding:14px 16px;background:var(--card);border:2px solid var(--red)}
.ss .verdict h2{margin:0 0 6px;font-family:var(--display);font-size:20px;letter-spacing:.03em}
.ss .verdict h2 small{font-family:var(--body);font-weight:500;font-size:13px;color:var(--mute);letter-spacing:0}
.ss .verdict ul{margin:6px 0 0;padding-left:18px;line-height:1.55;font-size:14.5px}
.ss .verdict .close{color:var(--mute);font-size:13px;margin-top:6px}
.ss .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px}
.ss .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;position:relative}
.ss .card.pick{border:2px solid var(--red)}
.ss .card .badge{position:absolute;top:-10px;right:10px;background:var(--red);color:#fff;font-family:var(--display);font-weight:800;letter-spacing:.08em;font-size:11px;padding:3px 8px;border-radius:99px;text-transform:uppercase}
.ss .card h3{margin:0;font-size:17px}
.ss .card h3 a{color:var(--ink);text-decoration:none}
.ss .card .meta{color:var(--mute);font-size:13px;margin:2px 0 8px}
.ss .big{display:flex;gap:14px;align-items:baseline;margin-bottom:8px}
.ss .big b{font-family:var(--display);font-size:30px;font-weight:800}
.ss .big span{color:var(--mute);font-size:12.5px}
.ss .rng{height:8px;border-radius:9px;background:var(--line);position:relative;margin:4px 0 2px}
.ss .rng i{position:absolute;top:0;bottom:0;border-radius:9px;background:var(--good,#2e7d32);opacity:.55}
.ss .rng em{position:absolute;top:-3px;width:3px;height:14px;background:var(--ink);border-radius:2px}
.ss .rngl{display:flex;justify-content:space-between;color:var(--mute);font-size:11.5px;margin-bottom:8px}
.ss table{width:100%;border-collapse:collapse;font-size:13px}
.ss td,.ss th{padding:4px 2px;text-align:left;border-top:1px solid var(--line)}
.ss th{color:var(--mute);font-weight:500;font-size:11.5px;text-transform:uppercase;letter-spacing:.04em}
.ss .kv{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr);gap:4px 10px;font-size:13.5px;margin:0 0 8px;align-items:baseline}
.ss .kv span{color:var(--mute);font-size:12.5px}.ss .kv b{text-align:right;font-weight:600}
.ss .rk{display:inline-block;min-width:26px;text-align:center;padding:1px 6px;border-radius:99px;color:#fff;font-weight:700;font-size:12px}
.ss .fl{list-style:none;margin:8px 0 0;padding:0;font-size:12.5px;line-height:1.45}
.ss .fl li{margin:4px 0}
.ss .fl b{display:inline-block;padding:0 6px;border-radius:99px;font-size:11px;margin-right:4px}
.ss .fl .good b{background:#dcefdc;color:#1f5d2b} .ss .fl .bad b{background:#f7d4d1;color:#8a1c14} .ss .fl .watch b{background:#f6e3b4;color:#6b4a00}
.ss .st{display:inline-block;padding:1px 7px;border-radius:99px;font-size:11.5px;font-weight:700;background:#b3261e;color:#fff;margin-left:6px;vertical-align:middle}
.ss .st.q{background:#f6e3b4;color:#6b4a00}
.ss .empty{color:var(--mute);font-size:14px;padding:18px 0}
.ss .note{color:var(--mute);font-size:12px;line-height:1.5;margin-top:14px}
"""

def page(WEEK):
    try:
        import account as ACCT
        link, base = ACCT._base_css()
    except Exception: link, base = "", ""
    return f"""<title>Who Should I Start? · BetSweep</title>
<meta name="description" content="Compare two or more players for your flex or last starting spot: projection, matchup, recent games, floor and ceiling, risk flags - and the model's pick with the reasons.">
{link}
<style>{base}{CSS}</style>
<main class="ss">
<p style="margin:4px 0 0;font-size:13px"><a href="/team/">← Fantasy</a></p>
<h1>Who should I start?</h1>
<p class="sub">Search two players for your flex or last starting spot. BetSweep lays out each player's Week {WEEK} projection, matchup, recent games and risks side by side, then makes the call and tells you why. Tap <b>+</b> to compare more.</p>
<div class="ctl"><span>Scoring</span><span class="seg" id="ssc"><button type="button" data-v="1" class="on">Full PPR</button><button type="button" data-v="0.5">Half</button><button type="button" data-v="0">Standard</button></span>
<span>I need</span><span class="seg" id="smode"><button type="button" data-v="mid" class="on">Best bet</button><button type="button" data-v="floor">Safe floor</button><button type="button" data-v="ceil">Upside</button></span></div>
<div class="slots" id="slots"></div>
<div id="out"></div>
<p class="note">Projections are the BetSweep model's for Week {WEEK} (the same numbers as the Fantasy page). Floor and ceiling come from each player's own game-to-game swings this season around this week's projection. Injury chips update live. Information only - you make the call.</p>
</main>
<script>
(function(){{
  var P = [], BY = {{}}, sel = [null, null], REC = 1, MODE = 'mid';
  try {{ var s = JSON.parse(localStorage.getItem('bs_ss') || 'null'); if (s && Array.isArray(s.sel)) sel = s.sel.slice(0, 8); if (sel.length < 2) sel.push(null); if (s && s.rec != null) REC = s.rec; if (s && s.mode) MODE = s.mode; }} catch(e) {{}}
  var q = new URLSearchParams(location.search).getAll('p'); if (q.length) {{ sel = q.slice(0, 8); while (sel.length < 2) sel.push(null); }}
  function save(){{ try {{ localStorage.setItem('bs_ss', JSON.stringify({{sel: sel, rec: REC, mode: MODE}})); }} catch(e) {{}} }}
  function esc(s){{ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){{ return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]; }}); }}
  function norm(s){{ return String(s || '').toLowerCase().replace(/[.']/g, '').replace(/\\s+(jr|sr|ii|iii|iv|v)$/, '').replace(/\\s+/g, ' ').trim(); }}
  function pts(p){{ return p.fp - (1 - REC) * (p.rec || 0); }}
  function band(p){{ var f = pts(p), sd = p.sd; if (sd == null || p.gp < 3) sd = Math.max(3, f * 0.45); sd = Math.min(sd, Math.max(4, f * 0.8)); return [Math.max(0, f - 0.84 * sd), f + 0.84 * sd]; }}
  function rkColor(r){{ if (r == null) return '#888'; var h = Math.round(120 - (r - 1) * (120 / 31)); return 'hsl(' + h + ' 55% 36%)'; }}
  function out(p){{ return !p.act || /^(OUT|IR|DOUBTFUL)/.test(p.av) || p.st === 'BYE'; }}
  function quest(p){{ return p.av === 'QUESTIONABLE'; }}
  function live(p){{ var v = window.BSRisk && window.BSRisk.verdict(p.n, null); return v; }}
  function score(p){{ var b = band(p), f = pts(p); var s = MODE === 'floor' ? b[0] * 0.7 + f * 0.3 : MODE === 'ceil' ? b[1] * 0.7 + f * 0.3 : f;
    var lv = live(p); if (out(p) || (lv && lv.level === 'block')) return -99; if (quest(p) || (lv && lv.level === 'warn')) s -= Math.max(1.5, f * 0.12);
    p.fl.forEach(function(x){{ if (x[0] === 'bad') s -= 0.4; else if (x[0] === 'good') s += 0.2; }}); return s; }}
  var POSD = {{QB: 'QBs', RB: 'RBs', WR: 'WRs', TE: 'TEs'}};
  function vol(p){{ var g = p.g || []; if (!g.length) return null; var a = function(k){{ return g.reduce(function(t, x){{ return t + (x[k] || 0); }}, 0) / g.length; }};
    if (p.p === 'QB') return {{lab: 'pass att / game', v: a('att')}}; if (p.p === 'RB') return {{lab: 'touches / game', v: a('car') + a('rec')}}; return {{lab: 'targets / game', v: a('tgt')}}; }}
  function snapAvg(p){{ var g = (p.g || []).filter(function(x){{ return x.sn != null; }}); return g.length ? g.reduce(function(t, x){{ return t + x.sn; }}, 0) / g.length : null; }}
  function line(p){{ var a = []; if (p.p === 'QB') a.push(Math.round(p.py) + ' pass yds', p.ptd.toFixed(1) + ' pass TD'); if (p.ry >= 3) a.push(Math.round(p.ry) + ' rush yds');
    if (p.p !== 'QB') {{ if (p.rec) a.push(p.rec.toFixed(1) + ' rec'); if (p.rcy) a.push(Math.round(p.rcy) + ' rec yds'); a.push((p.rtd + p.rctd).toFixed(2) + ' TD'); }} return a.join(' · '); }}

  function slotsUI(){{
    var h = sel.map(function(n, i){{ return '<div class="slot" data-i="' + i + '"><input type="search" autocomplete="off" placeholder="' + (i === 0 ? 'Search a player (e.g. Diggs)' : i === 1 ? 'Search a second player' : 'Add another player') + '" value="' + esc(n || '') + '" aria-label="Player ' + (i + 1) + '">' +
      (n || i > 1 ? '<button type="button" class="x" aria-label="Clear">×</button>' : '') + '<div class="sug" hidden></div></div>'; }}).join('');
    document.getElementById('slots').innerHTML = h + (sel.length < 8 ? '<button type="button" class="add" id="addb">+ Add a player</button>' : '');
  }}
  function matches(t){{ t = norm(t); if (!t) return []; var a = [], b = [];
    P.forEach(function(p){{ var n = norm(p.n); if (n.indexOf(t) === 0 || n.split(' ').some(function(w){{ return w.indexOf(t) === 0; }})) a.push(p); else if (n.indexOf(t) >= 0 || (p.t.toLowerCase() === t)) b.push(p); }});
    return a.concat(b).slice(0, 8); }}
  document.addEventListener('input', function(e){{ var inp = e.target.closest && e.target.closest('.ss .slot input'); if (!inp) return;
    var box = inp.parentNode.querySelector('.sug'), m = matches(inp.value);
    box.innerHTML = m.map(function(p, j){{ return '<button type="button" data-n="' + esc(p.n) + '"' + (j === 0 ? ' class="hi"' : '') + '><b>' + esc(p.n) + '</b> ' + esc(p.p) + ' · ' + esc(p.t) + '<small>' + (p.st === 'BYE' ? 'bye' : pts(p).toFixed(1) + ' pts') + '</small></button>'; }}).join('');
    box.hidden = !m.length; }});
  document.addEventListener('keydown', function(e){{ var inp = e.target.closest && e.target.closest('.ss .slot input'); if (!inp || e.key !== 'Enter') return; var f = inp.parentNode.querySelector('.sug button'); if (f) {{ e.preventDefault(); f.click(); }} }});
  document.addEventListener('click', function(e){{
    var sb = e.target.closest('.ss .sug button'); if (sb) {{ var i = +sb.closest('.slot').dataset.i; sel[i] = sb.dataset.n; if (sel.indexOf(null) < 0 && sel.length < 2) sel.push(null); save(); slotsUI(); render(); var nx = document.querySelector('.ss .slot input[value=""]'); if (nx && window.innerWidth > 700) nx.focus(); return; }}
    var x = e.target.closest('.ss .slot .x'); if (x) {{ var j = +x.closest('.slot').dataset.i; if (sel.length > 2) sel.splice(j, 1); else sel[j] = null; save(); slotsUI(); render(); return; }}
    if (e.target.id === 'addb') {{ sel.push(null); slotsUI(); var ins = document.querySelectorAll('.ss .slot input'); ins[ins.length - 1].focus(); return; }}
    var sg = e.target.closest('.ss .seg button'); if (sg) {{ sg.parentNode.querySelectorAll('button').forEach(function(b){{ b.classList.toggle('on', b === sg); }});
      if (sg.parentNode.id === 'ssc') REC = +sg.dataset.v; else MODE = sg.dataset.v; save(); slotsUI(); render(); return; }}
    if (!e.target.closest('.ss .slot')) document.querySelectorAll('.ss .sug').forEach(function(b){{ b.hidden = true; }});
  }});

  function reasons(a, b){{
    var r = [], fa = pts(a), fb = pts(b), d = fa - fb;
    if (out(b)) {{ r.push(esc(b.n) + ' is ' + (b.st === 'BYE' ? 'on a bye this week' : 'ruled out (' + esc(b.av || 'inactive') + ')') + ' - he will score 0.'); r.push(esc(a.n) + ' projects <b>' + fa.toFixed(1) + '</b> points.'); }}
    else if (Math.abs(d) >= 0.3) r.push('Projects <b>' + fa.toFixed(1) + '</b> points to ' + esc(b.n) + "'s " + fb.toFixed(1) + ' (' + (d >= 0 ? '+' : '') + d.toFixed(1) + ').');
    else if (quest(b)) r.push(esc(b.n) + ' is questionable - a late scratch or a limited game is the risk.');
    var lb = live(b); if (lb && lb.level !== 'good' && !out(b)) r.push(esc(b.n) + ': ' + esc(lb.why) + '.');
    if (a.dr != null && b.dr != null && Math.abs(a.dr - b.dr) >= 6) r.push((a.dr < b.dr ? 'Softer matchup: ' + esc(a.o) + ' is #' + a.dr + ' in yards allowed to ' + POSD[a.p] + ' (1 = most), ' + esc(b.o) + ' #' + b.dr + ' for ' + esc(b.n) + '.' : 'Tougher matchup on paper (' + esc(a.o) + ' #' + a.dr + ' vs ' + esc(b.o) + ' #' + b.dr + '), but the projection already prices that in.'));
    var va = vol(a), vb = vol(b); if (va && vb && va.lab === vb.lab && va.v > vb.v * 1.2 && va.v - vb.v >= 1.5) r.push('More volume: ' + va.v.toFixed(1) + ' ' + va.lab + ' over his last ' + a.g.length + ' vs ' + vb.v.toFixed(1) + '.');
    var sa = snapAvg(a), sbb = snapAvg(b); if (sa != null && sbb != null && sa - sbb >= 0.12) r.push('Bigger role: ' + Math.round(sa * 100) + '% of snaps lately vs ' + Math.round(sbb * 100) + '%.');
    var ba = band(a), bb = band(b);
    if (MODE === 'floor' && ba[0] > bb[0] + 0.8) r.push('Higher floor: about ' + ba[0].toFixed(1) + ' points on a bad day vs ' + bb[0].toFixed(1) + '.');
    if (MODE === 'ceil' && ba[1] > bb[1] + 0.8) r.push('Higher ceiling: about ' + ba[1].toFixed(1) + ' on a good day vs ' + bb[1].toFixed(1) + '.');
    var gfa = a.fl.filter(function(x){{ return x[0] === 'good'; }})[0]; if (gfa) r.push(esc(gfa[1]) + ': ' + esc(gfa[2]));
    var bfb = b.fl.filter(function(x){{ return x[0] === 'bad'; }})[0]; if (bfb) r.push('Against ' + esc(b.n) + ' - ' + esc(bfb[1]).toLowerCase() + ': ' + esc(bfb[2]));
    return r.slice(0, 5);
  }}
  function card(p, isPick){{
    var f = pts(p), b = band(p), mx = 40, lv = live(p);
    var st = out(p) ? '<span class="st">' + esc(p.st === 'BYE' ? 'BYE' : (p.av || 'OUT')) + '</span>' : quest(p) ? '<span class="st q">Q</span>' : '';
    var g = (p.g || []).slice().reverse();
    return '<div class="card' + (isPick ? ' pick' : '') + '">' + (isPick ? '<span class="badge">Start</span>' : '') +
      '<h3><a href="/player/' + esc(p.s) + '/">' + esc(p.n) + '</a>' + st + '</h3>' +
      '<div class="meta">' + esc(p.p) + ' · ' + esc(p.t) + ' ' + (p.o === 'BYE' || p.st === 'BYE' ? '· bye week' : 'vs ' + esc(p.o) + (p.k ? ' · ' + esc(p.k) : '')) + (p.role ? ' · ' + esc(p.role) : '') + '</div>' +
      '<div class="big"><b>' + f.toFixed(1) + '</b><span>projected pts<br>' + (p.avg != null ? 'season avg ' + p.avg.toFixed(1) + ' (' + p.gp + ' g)' : 'no games yet') + '</span></div>' +
      '<div class="rng"><i style="left:' + Math.min(100, b[0] / mx * 100) + '%;width:' + Math.max(2, Math.min(100, (b[1] - b[0]) / mx * 100)) + '%"></i><em style="left:' + Math.min(99, f / mx * 100) + '%"></em></div>' +
      '<div class="rngl"><span>floor ' + b[0].toFixed(1) + '</span><span>ceiling ' + b[1].toFixed(1) + '</span></div>' +
      '<div class="kv"><span>Projection</span><b>' + esc(line(p)) + '</b>' +
      (p.dr != null ? '<span>' + esc(p.o) + ' defense vs ' + POSD[p.p] + '</span><b><i class="rk" style="background:' + rkColor(p.dr) + '">#' + p.dr + '</i></b>' : '') +
      (p.or != null ? '<span>' + esc(p.t) + ' offense, same stat</span><b><i class="rk" style="background:' + rkColor(p.or) + '">#' + p.or + '</i></b>' : '') +
      (vol(p) ? '<span>' + vol(p).lab + ' (last ' + p.g.length + ')</span><b>' + vol(p).v.toFixed(1) + '</b>' : '') +
      (snapAvg(p) != null ? '<span>Snap share (last ' + p.g.length + ')</span><b>' + Math.round(snapAvg(p) * 100) + '%</b>' : '') + '</div>' +
      (g.length ? '<table><tr><th>Wk</th><th>Opp</th><th>Pts</th><th>' + (p.p === 'QB' ? 'Att' : p.p === 'RB' ? 'Car/Rec' : 'Tgt/Rec') + '</th><th>Yds</th><th>TD</th></tr>' + g.map(function(x){{
        var ptsx = x.fp - (1 - REC) * (x.rec || 0); return '<tr><td>' + x.w + '</td><td>' + esc(x.o) + '</td><td><b>' + ptsx.toFixed(1) + '</b></td><td>' + (p.p === 'QB' ? x.att : p.p === 'RB' ? x.car + '/' + x.rec : x.tgt + '/' + x.rec) + '</td><td>' + Math.round(x.yd) + '</td><td>' + x.td + '</td></tr>'; }}).join('') + '</table>' : '') +
      ((p.fl.length || lv) ? '<ul class="fl">' + (lv ? '<li class="' + (lv.level === 'good' ? 'good' : lv.level === 'block' ? 'bad' : 'watch') + '"><b>' + esc(lv.label || lv.short || 'Live') + '</b>' + esc(lv.why) + '</li>' : '') +
        p.fl.slice(0, 4).map(function(x){{ return '<li class="' + x[0] + '"><b>' + esc(x[1]) + '</b>' + esc(x[2]) + '</li>'; }}).join('') + '</ul>' : '') + '</div>';
  }}
  function render(){{
    var ps = sel.filter(Boolean).map(function(n){{ return BY[norm(n)]; }}).filter(Boolean);
    var o = document.getElementById('out');
    if (ps.length < 2){{ o.innerHTML = '<p class="empty">' + (ps.length ? 'Add one more player to get the call.' : 'Pick two players to compare.') + '</p>' + (ps.length ? '<div class="cards">' + card(ps[0], false) + '</div>' : ''); return; }}
    var ranked = ps.slice().sort(function(a, b){{ return score(b) - score(a); }}), top = ranked[0], nxt = ranked[1];
    var gap = score(top) - score(nxt);
    var h = '<div class="verdict"><h2>Start ' + esc(top.n) + ' <small>' + (gap < 0.75 ? 'coin flip - lean' : gap < 2 ? 'slight edge' : 'clear call') + (ps.length > 2 ? ' · then ' + ranked.slice(1).map(function(p){{ return esc(p.n); }}).join(', ') : '') + '</small></h2>' +
      '<ul>' + reasons(top, nxt).map(function(x){{ return '<li>' + x + '</li>'; }}).join('') + '</ul>' +
      (gap < 0.75 ? '<p class="close">These two are within a point. Tiebreakers: ' + (MODE === 'mid' ? 'switch to <b>Safe floor</b> if you are favored this week, <b>Upside</b> if you are the underdog.' : 'go with the later kickoff so you can pivot if news breaks.') + '</p>' : '') + '</div>';
    o.innerHTML = h + '<div class="cards">' + ranked.map(function(p, i){{ return card(p, i === 0); }}).join('') + '</div>';
  }}
  function boot(D){{ P = D.players || []; P.forEach(function(p){{ BY[norm(p.n)] = p; }});
    document.querySelectorAll('#ssc button').forEach(function(b){{ b.classList.toggle('on', +b.dataset.v === REC); }});
    document.querySelectorAll('#smode button').forEach(function(b){{ b.classList.toggle('on', b.dataset.v === MODE); }});
    slotsUI(); render(); document.addEventListener('bs-risk', render); }}
  fetch('/team/compare/data.json', {{cache: 'no-cache'}}).then(function(r){{ return r.json(); }}).then(boot).catch(function(){{ document.getElementById('out').innerHTML = '<p class="empty">Could not load this week\\'s projections - refresh to try again.</p>'; }});
}})();
</script>
"""
