"""NBA Stock Market at /nba/stocks/ - who is rising and who is falling in fantasy points, in the NFL Stock Market's own clothes.

Owner 11/22 3:27 PM: "Let's start adding nba, college football, and epl. I want each sport to basically look exactly like everything
we've built for NFL."; 7:14 PM, with the NBA boards up and the nightly grader running: "Alright get to what's next!"

Where the numbers come from: nba/stocks.json on the feeds-sports branch, written by sports/nba/stocks.py inside the feeds-sports job
(pandas lives there, not here). This script reads it through the clone with git and writes out/nba-stocks.html in plain Python.
Tonight's board (nba/board.json, the same branch) adds each player's game tonight and the model's numbers for it.

What it looks like: the NFL page's stylesheet, taken from build_stocks.py's own text (its CSS = \"\"\"...\"\"\" block - the script cannot be
imported, it builds when it loads), and the same markup: .skm, the search box, Rising / Falling, the G F C jumps, tiles (.sk) with
the same two-stroke sparkline, market-mover cards, and a player's panel under his row. Only what the NBA needs beyond that is new
(.nsk* classes).

A PREVIEW like /nba/: not in the menu, not in the sitemap, and it says so. No prices, no picks.

    python3 build_nba_stocks.py <clone>                          # the hourly job
    python3 build_nba_stocks.py --stocks FILE [--board FILE]     # tests and local work

With no stocks file in reach, one in another shape, or one whose games stop more than five days back, it writes nothing and removes
what an earlier run left.
"""
import datetime as dt, html, json, os, re, sys
import build_nba as N

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out")
PAGE = os.path.join(OUT, "nba-stocks.html"); DATA = os.path.join(OUT, "nba_stocks.json")
E = html.escape
FORMAT = 1                                   # sports/nba/stocks.py FORMAT
TOP = 8                                      # tiles shown per group before "Show all"
GROUPS = (("G", "Guards", "guard"), ("F", "Forwards", "forward"), ("C", "Centers", "center"))
GNAME = {a: c for a, b, c in GROUPS}
STAT = (("pts", "Points"), ("reb", "Rebounds"), ("ast", "Assists"), ("fg3", "Threes"), ("stl", "Steals"), ("blk", "Blocks"), ("tov", "Turnovers"))
# ESPN's abbreviations; nickname, primary, secondary
TEAMS = {"ATL": ("Hawks", "E03A3E", "C1D32F"), "BOS": ("Celtics", "007A33", "BA9653"), "BKN": ("Nets", "000000", "FFFFFF"), "CHA": ("Hornets", "1D1160", "00788C"), "CHI": ("Bulls", "CE1141", "000000"),
         "CLE": ("Cavaliers", "860038", "FDBB30"), "DAL": ("Mavericks", "00538C", "B8C4CA"), "DEN": ("Nuggets", "0E2240", "FEC524"), "DET": ("Pistons", "C8102E", "1D42BA"), "GS": ("Warriors", "FFC72C", "1D428A"),
         "HOU": ("Rockets", "CE1141", "000000"), "IND": ("Pacers", "002D62", "FDBB30"), "LAC": ("Clippers", "C8102E", "1D428A"), "LAL": ("Lakers", "552583", "FDB927"), "MEM": ("Grizzlies", "5D76A9", "12173F"),
         "MIA": ("Heat", "98002E", "F9A01B"), "MIL": ("Bucks", "00471B", "EEE1C6"), "MIN": ("Timberwolves", "0C2340", "78BE20"), "NO": ("Pelicans", "0C2340", "C8102E"), "NY": ("Knicks", "006BB6", "F58426"),
         "OKC": ("Thunder", "007AC1", "EF3B24"), "ORL": ("Magic", "0077C0", "C4CED4"), "PHI": ("76ers", "006BB6", "ED174C"), "PHX": ("Suns", "1D1160", "E56020"), "POR": ("Trail Blazers", "E03A3E", "000000"),
         "SAC": ("Kings", "5A2D81", "63727A"), "SA": ("Spurs", "C4CED4", "000000"), "TOR": ("Raptors", "CE1141", "000000"), "UTAH": ("Jazz", "002B5C", "F9A01B"), "WSH": ("Wizards", "002B5C", "E31837")}


def team(ab):
    nm, p, s = TEAMS.get(ab, (ab, "333333", "000000"))
    return nm, "#" + p, "#" + s, ("#111" if N.lum(p) > 0.55 else "#fff")


def _g(x): return f"{round(x, 1):g}"
def spark(vals, k):
    """build_stocks.spark: every game left to right on a zero-based scale in a 120 x 40 box; the last k games again as their own path"""
    n = len(vals); lo = min(0.0, min(vals)); hi = max(vals)
    if hi - lo < 1e-9: hi = lo + 1.0
    pts = [((60.0 if n == 1 else 4 + 112.0 * i / (n - 1)), 5 + 30.0 * (1 - (v - lo) / (hi - lo))) for i, v in enumerate(vals)]
    path = lambda ps: ("M" + "L".join(f"{_g(x)} {_g(y)}" for x, y in ps)) if len(ps) > 1 else ""
    return path(pts), (path(pts[-k:]) if k else ""), _g(pts[-1][0]), _g(pts[-1][1])


def delta_text(d):
    """build_stocks.delta_text"""
    if abs(d) < 0.5: return ("" if f"{abs(d):.1f}" == "0.0" else ("+" if d >= 0 else "\N{MINUS SIGN}")) + f"{abs(d):.1f}"
    return ("\N{BLACK UP-POINTING TRIANGLE} " if d > 0 else "\N{BLACK DOWN-POINTING TRIANGLE} ") + f"{abs(d):.1f}"


def usable(S, today=None):
    if not S or not isinstance(S, dict): return False, "no nba/stocks.json in reach on the feeds-sports branch"
    if S.get("format") != FORMAT or S.get("sport") != "nba": return False, f"the stocks file is format {S.get('format')!r}, this page reads format {FORMAT}"
    if len(S.get("players") or []) < 50: return False, "the stocks file holds fewer than 50 players"
    try: through = dt.date.fromisoformat(S["data_through"])
    except Exception: return False, "the stocks file does not say how far its games go"
    today = today or dt.date.fromisoformat(N.nba_day())
    if (today - through).days > 5: return False, f"the games stop at {through}, more than five days back: the season data is not updating"
    return True, ""


STATUS = {"Out": ("OUT", "o"), "Doubtful": ("OUT", "o"), "Questionable": ("Q", ""), "Day-to-day": ("DTD", ""), "Probable": ("P", "")}


def tonight(p, B):
    """(sentences, link, status tag, tag class) for a player from tonight's board; all empty without a board"""
    if not B: return [], "", "", ""
    t = (B.get("teams") or {}).get(p["team"])
    lab = B.get("day_label") or "tonight"
    if not t: return [f"The {team(p['team'])[0]} do not play on {lab}."], "", "", ""
    g = next((g for g in B["games"] if p["team"] in (g["home"], g["away"])), None)
    where = (("vs " if g["home"] == p["team"] else "at ") + (g["away"] if g["home"] == p["team"] else g["home"]) + f", {g['tipct']} CT") if g else ""
    link = f"/nba/#{g['key']}" if g else ""
    o = next((o for o in t.get("out") or [] if o.get("name") == p["name"]), None)
    if o:
        tag, cls = STATUS.get(o.get("tag"), ("OUT", "o"))
        return [f"{lab}: {where}. Listed {str(o.get('tag') or 'out').lower()}" + (f" ({o['why']})" if o.get("why") else "") + ", so the board has no numbers for him."], link, tag, cls
    bp = next((x for x in B["players"] if str(x["id"]) == p["id"]), None)
    if not bp: return [f"{lab}: {where}. He is not in the board's rotation for this game."], link, "", ""
    pr = bp["proj"]; st = (bp.get("status") or {}).get("tag") or ""
    tag, cls = STATUS.get(st, ("", ""))
    say = [f"{lab}: {where}.", f"The model has him at {pr['pts']:.1f} points, {pr['reb']:.1f} rebounds, {pr['ast']:.1f} assists and {pr['fg3']:.1f} threes in about {round(bp['min'])} minutes."]
    if st: say.append(f"Listed {st.lower()}.")
    return say, link, tag, cls


def prep(S, B):
    """every player as the page needs him: the stocks row plus his tile's graph, his sentences and tonight"""
    out = []
    for p in S["players"]:
        vals = [r[10] for r in p["g"] if r[2] is not None]
        if not vals: continue
        pa, pr, ex, ey = spark(vals, min(5, len(vals)))
        nm, c1, c2, ink = team(p["team"])
        dm = p["rmin"] - p["pmin"]
        word = "up" if p["d"] > 0 else "down"
        say = [f"Last {p['nr']} games: {p['r']:.1f} fantasy points a game, {word} {abs(p['d']):.1f} on the {p['np']} before ({p['p']:.1f}).",
               f"Minutes: {p['rmin']:.1f} a game over those {p['nr']}, " + ("the same as before." if abs(dm) < 0.5 else f"{'up' if dm > 0 else 'down'} {abs(dm):.1f} from {p['pmin']:.1f}.")]
        if p.get("sat"): say.append(f"He sat out {p['sat']} of his team's last 5 games.")
        to, link, tag, cls = tonight(p, B)
        out.append({"k": p["id"], "n": p["name"], "t": p["team"], "tn": nm, "c": [c1, c2, ink], "g": p["grp"], "gp": p["gp"], "fp": p["fp"], "mn": p["min"], "r": p["r"], "p": p["p"], "d": p["d"],
                    "rm": p["rmin"], "pm": p["pmin"], "dir": p["dir"], "sp": [pa, pr, ex, ey], "avg": p["avg"], "ravg": p["ravg"], "rows": p["g"], "say": say, "to": to, "ln": link, "st": tag, "sc": cls,
                    "nr": p["nr"], "np": p["np"]})
    return out


TILE = ('<li class="sk {dir}" data-k="{k}" data-pos="{g}"{more}><button type="button" class="skb" aria-expanded="false" aria-label="{aria}">'
        '<b class="sknm">{n}</b>'
        '<span class="sktm tg"><i class="sktb" style="--p:{c1};--s:{c2};--i:{ink}">{t}</i><span class="sksu">{g}<span> · {tn}</span></span><i class="skst {sc}">{st}</i></span>'
        '<svg class="sksp" viewBox="0 0 120 40" aria-hidden="true" focusable="false"><path class="ska" d="{pa}"/><path class="skr" d="{pr}"/><circle cx="{ex}" cy="{ey}" r="3.5"/></svg>'
        '<span class="skpx"><span class="skv"><b>{val}</b><small>last {nr}</small></span><em>{dt}</em></span>'
        '</button></li>')


def tile(x, more=False):
    cls = "up" if x["d"] >= 0.5 else ("dn" if x["d"] <= -0.5 else "")
    aria = f"{x['n']}, {GNAME[x['g']]}, {x['tn']}: {x['r']:.1f} fantasy points a game over his last {x['nr']}, {'up' if x['d'] > 0 else 'down'} {abs(x['d']):.1f}. Open his numbers."
    return TILE.format(dir=cls, k=E(x["k"]), g=x["g"], more=' hidden data-more="1"' if more else "", aria=E(aria), n=E(x["n"]), c1=x["c"][0], c2=x["c"][1], ink=x["c"][2], t=E(x["t"]), tn=E(x["tn"]),
                       sc=x["sc"], st=E(x["st"]), pa=x["sp"][0], pr=x["sp"][1], ex=x["sp"][2], ey=x["sp"][3], val=f"{x['r']:.1f}", nr=x["nr"], dt=delta_text(x["d"]))


def movers(PL):
    """six headline cards: [{id, l (label), k (player), v (value), s (sub), tone}]"""
    out = []
    def card(i, lab, x, v, s, tone=""):
        if x: out.append({"id": i, "l": lab, "k": x["k"], "v": v, "s": s, "tone": tone})
    up = [x for x in PL if x["dir"] == "up"]; dn = [x for x in PL if x["dir"] == "dn"]
    a = max(up, key=lambda x: (x["d"], x["n"]), default=None); card("rise", "Biggest riser", a, a and f"+{a['d']:.1f}", a and f"{a['p']:.1f} to {a['r']:.1f} a game", "tu")
    a = min(dn, key=lambda x: (x["d"], x["n"]), default=None); card("fall", "Biggest faller", a, a and f"\N{MINUS SIGN}{abs(a['d']):.1f}", a and f"{a['p']:.1f} to {a['r']:.1f} a game", "td")
    a = max(PL, key=lambda x: (x["r"], x["n"]), default=None); card("hot", "Hottest", a, a and f"{a['r']:.1f}", a and f"a game over his last {a['nr']}")
    best = None
    for x in PL:
        for r in [r for r in x["rows"] if r[2] is not None][-5:]:
            if best is None or r[10] > best[1][10]: best = (x, r)
    if best: card("game", "Best game", best[0], f"{best[1][10]:.1f}", f"{best[1][0]} {best[1][1]}: {best[1][3]} pts, {best[1][4]} reb, {best[1][5]} ast")
    mu = [x for x in PL if x["r"] >= 15]; md = [x for x in PL if x["p"] >= 15]
    a = max(mu, key=lambda x: (x["rm"] - x["pm"], x["n"]), default=None); card("minup", "Minutes up", a, a and f"+{a['rm'] - a['pm']:.1f}", a and f"{a['pm']:.1f} to {a['rm']:.1f} a game", "tu")
    a = min(md, key=lambda x: (x["rm"] - x["pm"], x["n"]), default=None); card("mindn", "Minutes down", a, a and f"\N{MINUS SIGN}{abs(a['rm'] - a['pm']):.1f}", a and f"{a['pm']:.1f} to {a['rm']:.1f} a game", "td")
    return out


def mover_html(c, BY):
    x = BY[c["k"]]
    aria = f"{c['l']}: {x['n']}, {GNAME[x['g']]}, {x['tn']}. {c['v']}, {c['s']}. Open his numbers."
    return (f'<li><button type="button" class="skmc {c["tone"]}" data-k="{E(x["k"])}" data-m="{c["id"]}" aria-label="{E(aria)}"><span class="skmt">{E(c["l"])}</span><b class="skmn">{E(x["n"])}</b>'
            f'<span class="skmw"><i class="sktb" style="--p:{x["c"][0]};--s:{x["c"][1]};--i:{x["c"][2]}">{E(x["t"])}</i><span>{x["g"]}</span>'
            f'<svg class="sksp" viewBox="0 0 120 40" aria-hidden="true" focusable="false"><path class="ska" d="{x["sp"][0]}"/><path class="skr" d="{x["sp"][1]}"/></svg></span>'
            f'<span class="skmx"><b>{E(c["v"])}</b><small>{E(c["s"])}</small></span></button></li>')


def section(g, title, word, PL):
    up = sorted([x for x in PL if x["g"] == g and x["dir"] == "up"], key=lambda x: (-x["d"], x["n"]))
    dn = sorted([x for x in PL if x["g"] == g and x["dir"] == "dn"], key=lambda x: (x["d"], x["n"]))
    def block(xs, mode, verb):
        if not xs: return f'<p class="sknone" data-for="{mode}">No {word} is {verb} by the page\'s rule right now.</p>'
        h = f'<ul class="skg" data-for="{mode}" data-list="{g}-{mode}">' + "".join(tile(x, more=i >= TOP) for i, x in enumerate(xs)) + '</ul>'
        if len(xs) > TOP: h += f'<p class="skmr" data-for="{mode}"><button type="button" class="skmore" data-list="{g}-{mode}">Show all {len(xs)} {verb} {word}s</button></p>'
        return h
    return (f'<section class="sksec" id="nsk-{g.lower()}"><h2>{title} <small data-for="rise">{len(up)} rising</small><small data-for="fall">{len(dn)} falling</small></h2>'
            + block(up, "rise", "rising") + block(dn, "fall", "falling") + '</section>')


NSK_CSS = """
.skm .nbbar{margin:0 0 10px;padding:0} .skm .nbpre{margin:0 0 12px}
.skm .skml{scroll-snap-type:none}
.skm .skt{cursor:default} .skm .skt:hover{border-color:var(--line)}
.skm .skt{grid-template-columns:minmax(0,1fr)} .skm .sktv em.up{color:var(--good)} .skm .sktv em.dn{color:var(--bad)}
.skm .skts{margin:10px 0 0}
.skm .nskw{overflow-x:auto;-webkit-overflow-scrolling:touch}
.skm .sktbl table.nskt{max-width:none;font-size:12px} .skm .sktbl table.nskt th,.skm .sktbl table.nskt td{padding:6px 3px;white-space:nowrap} .skm .sktbl table.nskt th{font-size:11.5px;letter-spacing:.02em} .skm .sktbl table.nskt th:nth-child(n+3),.skm .sktbl table.nskt td:nth-child(n+3){text-align:right}
.skm .sktbl table.nskt td.fp{font-weight:700;color:var(--ink)} .skm .sktbl table.nskt td.dnp{text-align:left;color:var(--mute);white-space:normal}
.skm .sktbl table.nskt tr.rc td:first-child{box-shadow:inset 3px 0 0 var(--mute)} .skm .skp.up .sktbl table.nskt tr.rc td:first-child{box-shadow:inset 3px 0 0 var(--good)} .skm .skp.dn .sktbl table.nskt tr.rc td:first-child{box-shadow:inset 3px 0 0 var(--bad)}
.skm .skqc b.up{color:var(--good)} .skm .skqc b.dn{color:var(--bad)}
@media (min-width:761px){ .skm .skml{grid-template-columns:repeat(3,minmax(0,1fr))} }
"""

NSK_JS = r"""
<script>
(function(){
  var D = window.__NSK, root = document.getElementById('nsk'), BY = {};
  if(!D || !root) return;
  D.pl.forEach(function(p){ BY[p.k] = p; });
  var STAT = D.stat, find = document.getElementById('nskfind'), res = document.getElementById('nskres'), none = document.getElementById('nsknone'), q = document.getElementById('nskq');
  function esc(s){ return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function f1(x){ return (Math.round(x * 10) / 10).toFixed(1); }
  function dtx(d){ if(Math.abs(d) < 0.5) return (f1(Math.abs(d)) === '0.0' ? '' : (d >= 0 ? '+' : '−')) + f1(Math.abs(d)); return (d > 0 ? '▲ ' : '▼ ') + f1(Math.abs(d)); }
  function dir(d){ return d >= 0.5 ? 'up' : (d <= -0.5 ? 'dn' : ''); }
  function tile(p){
    return '<li class="sk ' + dir(p.d) + '" data-k="' + esc(p.k) + '" data-pos="' + p.g + '"><button type="button" class="skb" aria-expanded="false" aria-label="' + esc(p.n + ', ' + D.gname[p.g] + ', ' + p.tn + '. Open his numbers.') + '">' +
      '<b class="sknm">' + esc(p.n) + '</b><span class="sktm tg"><i class="sktb" style="--p:' + p.c[0] + ';--s:' + p.c[1] + ';--i:' + p.c[2] + '">' + esc(p.t) + '</i><span class="sksu">' + p.g + '<span> · ' + esc(p.tn) + '</span></span><i class="skst ' + p.sc + '">' + esc(p.st) + '</i></span>' +
      '<svg class="sksp" viewBox="0 0 120 40" aria-hidden="true" focusable="false"><path class="ska" d="' + p.sp[0] + '"/><path class="skr" d="' + p.sp[1] + '"/><circle cx="' + p.sp[2] + '" cy="' + p.sp[3] + '" r="3.5"/></svg>' +
      '<span class="skpx"><span class="skv"><b>' + f1(p.r) + '</b><small>last ' + p.nr + '</small></span><em>' + dtx(p.d) + '</em></span></button></li>';
  }
  function panel(p){
    var played = p.rows.filter(function(r){ return r[2] !== null; }), cut = played.length - p.nr, seen = 0;
    var rows = p.rows.map(function(r){
      if(r[2] === null) return '<tr><td>' + esc(r[0]) + '</td><td>' + esc(r[1]) + '</td><td class="dnp" colspan="9">' + esc(r[3]) + '</td></tr>';
      var rc = seen++ >= cut;
      return '<tr' + (rc ? ' class="rc"' : '') + '><td>' + esc(r[0]) + '</td><td>' + esc(r[1]) + '</td><td class="fp">' + f1(r[10]) + '</td>' + r.slice(2, 10).map(function(v){ return '<td>' + v + '</td>'; }).join('') + '</tr>';
    }).reverse().join('');
    var stats = STAT.map(function(s){ var a = p.ravg[s[0]], b = p.avg[s[0]], d = a - b, good = s[0] === 'tov' ? -d : d;
      return '<div class="skt" data-s="' + s[0] + '"><span class="sktl">' + s[1] + '</span><span class="sktv"><b>' + f1(a) + '</b><em class="' + (Math.abs(d) < 0.05 ? '' : (good > 0 ? 'up' : 'dn')) + '">' + (Math.abs(d) < 0.05 ? 'season ' + f1(b) : (d > 0 ? '+' : '−') + f1(Math.abs(d)) + ' on season') + '</em></span></div>'; }).join('');
    return '<div class="skph"><div><h3>' + esc(p.n) + '</h3><p>' + esc(p.tn) + ' · ' + D.gname[p.g] + ' · ' + p.gp + ' games this season</p></div><button type="button" class="skx">Close</button></div>' +
      '<div class="skqt"><div class="skqc"><span>Last ' + p.nr + '</span><b class="' + dir(p.d) + '">' + f1(p.r) + '</b><small>FP a game</small></div><div class="skqc"><span>The ' + p.np + ' before</span><b>' + f1(p.p) + '</b><small>' + dtx(p.d) + ' since</small></div>' +
      '<div class="skqc"><span>Season</span><b>' + f1(p.fp) + '</b><small>' + f1(p.mn) + ' min a game</small></div></div>' +
      '<div class="skfx"><div><b>What moved</b>' + p.say.map(function(s){ return '<p>' + esc(s) + '</p>'; }).join('') + '</div>' + (p.to.length ? '<div><b>His next game</b>' + p.to.map(function(s){ return '<p>' + esc(s) + '</p>'; }).join('') + '</div>' : '') + '</div>' +
      '<div class="skts">' + stats + '</div>' +
      '<details class="sktbl"><summary>Game by game, newest first</summary><div class="nskw"><table class="nskt"><thead><tr><th>Date</th><th>Opp</th><th>FP</th><th>Min</th><th>Pts</th><th>Reb</th><th>Ast</th><th>3s</th><th>Stl</th><th>Blk</th><th>TO</th></tr></thead><tbody>' + rows + '</tbody></table></div></details>' +
      (p.ln ? '<p class="skpl"><a href="' + p.ln + '" data-pid="' + esc(p.k) + '">See his game on the NBA board</a></p>' : '');
  }
  function shut(){ var o = root.querySelector('li.skp'); if(o) o.remove(); root.querySelectorAll('.skb[aria-expanded="true"]').forEach(function(b){ b.setAttribute('aria-expanded', 'false'); }); }
  function open(li, jump){
    var was = li.querySelector('.skb').getAttribute('aria-expanded') === 'true'; shut(); if(was) return;
    var p = BY[li.getAttribute('data-k')]; if(!p) return;
    li.querySelector('.skb').setAttribute('aria-expanded', 'true');
    var last = li, top = li.offsetTop, x = li.nextElementSibling;
    while(x){ if(!x.hidden && x.classList.contains('sk')){ if(x.offsetTop !== top) break; last = x; } x = x.nextElementSibling; }
    var el = document.createElement('li'); el.className = 'skp ' + dir(p.d); el.setAttribute('data-k', p.k); el.innerHTML = panel(p); last.after(el);
    if(jump) li.scrollIntoView({block: 'start'});
  }
  function mode(m){ shut(); root.setAttribute('data-mode', m); root.querySelectorAll('.skmode button').forEach(function(b){ b.setAttribute('aria-pressed', b.getAttribute('data-mode') === m ? 'true' : 'false'); }); }
  function norm(s){ return String(s).toLowerCase().replace(/[^a-z0-9 ]/g, ''); }
  function search(v){
    var s = norm(v).trim(); shut();
    var on = s.length >= 2;
    find.hidden = !on; root.querySelectorAll('.sksec:not(#nskfind), .skmk, .skmode, .skbar').forEach(function(e){ e.hidden = on; });
    if(!on){ res.innerHTML = ''; return []; }
    var hit = D.pl.filter(function(p){ return norm(p.n).indexOf(s) >= 0 || norm(p.tn).indexOf(s) >= 0 || p.t.toLowerCase() === s; }).slice(0, 60);
    res.innerHTML = hit.map(tile).join(''); none.hidden = hit.length > 0;
    return hit;
  }
  function openKey(k){
    var p = BY[k]; if(!p) return;
    if(q.value){ q.value = ''; search(''); }
    var want = p.dir === 'dn' ? 'fall' : (p.dir === 'up' ? 'rise' : root.getAttribute('data-mode'));
    var li = p.dir ? root.querySelector('.sksec .skg[data-for="' + want + '"] li.sk[data-k="' + k + '"]') : null;
    if(li){ mode(want); var ul = li.parentNode; if(li.hidden){ ul.querySelectorAll('li[data-more]').forEach(function(x){ x.hidden = false; }); var mb = root.querySelector('.skmore[data-list="' + ul.getAttribute('data-list') + '"]'); if(mb) mb.parentNode.hidden = true; } open(li, true); return; }
    q.value = p.n; search(p.n); li = res.querySelector('li.sk[data-k="' + k + '"]'); if(li) open(li, true);
  }
  root.addEventListener('click', function(e){
    var t = e.target, b;
    if((b = t.closest('.skx'))){ var k = b.closest('li.skp').getAttribute('data-k'); shut(); var o = root.querySelector('li.sk[data-k="' + k + '"]:not([hidden]) .skb'); if(o) o.focus(); return; }
    if((b = t.closest('.skmc'))){ openKey(b.getAttribute('data-k')); return; }
    if((b = t.closest('.skmode button'))){ mode(b.getAttribute('data-mode')); return; }
    if((b = t.closest('.skmore'))){ root.querySelectorAll('.skg[data-list="' + b.getAttribute('data-list') + '"] li[data-more]').forEach(function(x){ x.hidden = false; }); b.parentNode.hidden = true; return; }
    if((b = t.closest('.skb'))){ open(b.parentNode, false); return; }
  });
  q.addEventListener('input', function(){ search(q.value); });
  window.__nskOpen = openKey;
})();
</script>"""


def page(S, B, PL):
    sk_css = re.search(r'^CSS = """(.*?)^"""', open(os.path.join(HERE, "build_stocks.py"), encoding="utf-8").read(), re.S | re.M).group(1)
    BY = {x["k"]: x for x in PL}
    mk = movers(PL)
    through = N.day_label(S["data_through"])
    r = S["rule"]
    blob = {"pl": PL, "stat": [list(s) for s in STAT], "gname": {a: c.capitalize() for a, b, c in GROUPS}}
    foot = (f'<p class="skfoot">Built {N.fmt_ct(S.get("built"))} from box scores through {E(through)}. Fantasy points use {E(S["scoring"][0].lower() + S["scoring"][1:])}. '
            f'Rising: up {r["move"]:g} or more a game over the last {r["recent"]} against the {r["before"]} before, and averaging {r["floor"]:g} or more now. Falling: down {r["move"]:g} or more after averaging {r["floor"]:g} or more. '
            f'A player is listed with {r["games"]} or more games this season and a rotation role. Five games is a short run: a move here is something to look into, not a forecast. For entertainment; not betting advice.</p>')
    link, base = __import__("account")._base_css()      # the site's fonts and theme colours, as the NFL Stock Market takes them
    return ('<title>BetSweep · NBA Stock Market</title>\n'
            f'{link}\n<style>{base}{sk_css}</style>\n<style>{N.NB_CSS}</style>\n<style>{NSK_CSS}</style>\n'
            '<main class="skm" id="nsk" data-mode="rise">\n'
            '<div class="nbbar"><div class="nbsw" role="group" aria-label="Sport"><a href="/stocks/">NFL</a><a href="/nba/stocks/" aria-current="page">NBA</a></div>'
            '<div class="nbsw nbpg" role="group" aria-label="NBA pages"><a href="/nba/">Boards</a><a href="/nba/stocks/" aria-current="page">Stocks</a></div></div>\n'
            f'<div class="skhd"><h1>Stock Market</h1><span class="sksub">NBA · games through {E(through)}. Who is up and who is down in fantasy points over the last {r["recent"]} games, against the {r["before"]} before.</span></div>\n'
            '<div class="nbpre"><b>NBA preview.</b> Results and model numbers only: no FanDuel prices yet, so nothing here is a pick.</div>\n'
            '<div class="skfind"><label class="sr" for="nskq">Search players</label><input id="nskq" type="search" placeholder="Search a player or team" autocomplete="off" autocapitalize="words" spellcheck="false" enterkeyhint="search"></div>\n'
            + ('<section class="skmk" id="nskmk" aria-label="Market movers"><ul class="skml">' + "".join(mover_html(c, BY) for c in mk) + '</ul></section>\n' if mk else '')
            + '<div class="skmode" role="group" aria-label="Show the risers or the fallers"><button type="button" data-mode="rise" aria-pressed="true">Rising</button><button type="button" data-mode="fall" aria-pressed="false">Falling</button></div>\n'
            '<div class="skbar"><nav class="skj" aria-label="Jump to a position">' + "".join(f'<a href="#nsk-{a.lower()}">{a}</a>' for a, b, c in GROUPS) + '</nav>'
            f'<p class="skkey"><span><i class="k2"></i>last {r["recent"]} games</span><span><i></i>earlier games</span></p></div>\n'
            + "\n".join(section(a, b, c, PL) for a, b, c in GROUPS)
            + '\n<section class="sksec" id="nskfind" hidden><h2>Search</h2><ul class="skg" id="nskres"></ul><p class="sknone" id="nsknone" hidden>No listed player or team matches. A player is listed with 8 or more games and a rotation role.</p></section>\n'
            + foot + '\n</main>\n'
            '<script>window.__NSK = ' + json.dumps(blob, separators=(",", ":")).replace("</", "<\\/") + ';</script>\n' + NSK_JS + '\n'), mk


def main():
    a = sys.argv[1:]
    named = "--stocks" in a
    clone = None if named else (a[0] if a else None)
    if named:
        S = N.load(path=a[a.index("--stocks") + 1]); B = N.load(path=a[a.index("--board") + 1]) if "--board" in a else None
    else:
        B = N.load(clone=clone)                       # fetches the branch
        S = N.feed_file(clone, "nba/stocks.json")
    ok, why = usable(S, today=dt.date.fromisoformat(S["data_through"]) if (named and S and S.get("data_through")) else None)
    if not ok:
        for f in (PAGE, DATA):
            if os.path.exists(f): os.remove(f)
        print(f"nba stocks: no page written - {why}")
        return
    if B is not None and not N.usable(B, any_day=named)[0]: B = None     # an old or odd board adds nothing: the page is drawn without "his next game"
    PL = prep(S, B)
    h, mk = page(S, B, PL)
    os.makedirs(OUT, exist_ok=True)
    open(PAGE, "w", encoding="utf-8").write(h)
    json.dump({"stocks": S, "board_day": (B or {}).get("day"), "board_built": (B or {}).get("built"), "movers": mk}, open(DATA, "w"), separators=(",", ":"))
    print(f"nba stocks: {len(PL)} players through {S['data_through']}, {sum(1 for x in PL if x['dir'] == 'up')} rising, {sum(1 for x in PL if x['dir'] == 'dn')} falling, "
          f"{'with' if B else 'without'} tonight's board; {os.path.getsize(PAGE) // 1024} KB -> {PAGE}")


if __name__ == "__main__":
    main()
