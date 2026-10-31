#!/usr/bin/env python3
"""build_players.py - one page per player at /player/<slug>/ plus a searchable directory at /player/ (owner 10/30: "a page for every
player"). Everything on a page is already in the build - nothing here changes a projection or a price:

  this week's props   every rung the Parlay Builder prices for him (out/builder_data.json): FanDuel price, DraftKings / Hard Rock price
                      where they post the same line, the model % shown on the site (calib blend), book %, edge, and how often he has
                      cleared that line this season (from the nflverse game log - games played only)
  the matchup         his offense's rank vs the opponent's defense rank in each stat he has a prop in (offranks / the sheet's tab)
  the flags           the model's notes on him (flags.py text the builder already carries)
  game log + usage    week by week: snap share, targets, carries, yards, TDs, PPR points; target / carry share season vs last 3
  status              this week's injury report line

Writes out/players/<slug>.html (page bodies, wrapped by build_site.py), out/players/index.html (the directory), out/players/player.css
and out/players/player.js (shared by every page, so each page stays small), and out/players/slugs.json {name: slug} that the other
pages use to link names here. Prints "wrote out/players: N player pages (L with props this week), week W".
Add to betslip writes the same browser key the boards / builder slip uses (bs_slipk_w<W>, keys "player|market|line"), so a leg added here
is in the slip on every page.
"""
import os, re, json, csv, html, math, datetime as dt
import plydata as PD
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); IN = os.path.join(HERE, "in")
E = html.escape
S = PD.load(HERE); W = S.week
try:
    import booklinks as BL
except Exception:
    BL = None
CT = ZoneInfo("America/Chicago")

def rank_color(r):   # same scale as the boards / builder (1 = green ... 32 = red)
    t = (r - 1) / 31
    if t < 0.5: h = 140 - 95 * (t / 0.5); l = 0.30 + 0.08 * (t / 0.5)
    else: h = 45 - 45 * ((t - 0.5) / 0.5); l = 0.38 - 0.10 * ((t - 0.5) / 0.5)
    return f"hsl({h:.0f} 62% {l*100:.0f}%)"

def am(o):
    try: o = float(o)
    except Exception: return "—"
    return ("+" if o > 0 else "−") + str(int(abs(round(o))))

def pc(x): return "—" if x is None else f"{100 * x:.0f}%"

def jsround(x): return int(math.floor(float(x) + 0.5))

def legkey(l): return f'{l["pl"]}|{l["m"]}|{jsround(l.get("ln") or 1)}'

# market -> (stat getter over a game-log row, label)
def _stat(m):
    base = m[6:] if m.startswith("Under ") else m
    return {"Receiving Yards": lambda g: g["recy"], "Receptions": lambda g: g["rec"], "Rushing Yards": lambda g: g["rush"],
            "Passing Yards": lambda g: g["pass"], "Rush + Rec Yards": lambda g: g["rush"] + g["recy"], "Anytime TD": lambda g: g["td"],
            "2+ TD": lambda g: g["td"], "3+ TD": lambda g: g["td"]}.get(base)

def cleared(l, games):
    f = _stat(l["m"])
    if not f or not games: return None
    ln = float(l.get("ln") or 1)
    if l["m"] == "2+ TD": ln = 2
    if l["m"] == "3+ TD": ln = 3
    if l["m"].startswith("Under "): hit = sum(1 for g in games if f(g) < ln)
    else: hit = sum(1 for g in games if f(g) >= ln)
    return hit, len(games)

MORDER = ["Passing Yards", "Rushing Yards", "Receiving Yards", "Receptions", "Rush + Rec Yards", "Longest Reception", "Anytime TD", "First TD", "2+ TD", "3+ TD",
          "Under Passing Yards", "Under Rushing Yards", "Under Receiving Yards", "Under Receptions"]

# ESPN news link (same rule as the boards: ESPN player news by id from the nflverse roster, else Google News)
_ESPN = {}
try:
    with open(os.path.join(IN, "roster_2026.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            eid = (r.get("espn_id") or "").strip()
            if eid and eid not in ("NA",): _ESPN[PD.norm(r.get("full_name"))] = eid.split(".")[0]
except Exception: pass
def news_url(name):
    eid = _ESPN.get(PD.norm(name))
    if eid: return f"https://www.espn.com/nfl/player/news/_/id/{eid}/{PD.slugify(name)}", "ESPN"
    import urllib.parse
    return "https://news.google.com/search?q=" + urllib.parse.quote(f'"{name}" NFL'), "Google News"

def status_badge(st):
    if not st: return ""
    rep, prac, inj = st
    if rep in ("Out", "Doubtful", "Questionable"):
        cls = {"Out": "out", "Doubtful": "dbt", "Questionable": "q"}[rep]
        short = re.split(r" - |; |\(", inj)[0].strip()[:40] if inj else ""
        return f'<span class="st {cls}" title="{E(inj)}">{E(rep)}{(" · " + E(short)) if short else ""}</span>'
    if prac and not prac.startswith("Full"):
        return f'<span class="st q">{E(prac.replace(" In Practice", "").replace("Participation", "practice"))}{(" · " + E(inj)) if inj else ""}</span>'
    return ""

def pill(tm, o, opp, d):
    if o is None and d is None: return ""
    a = f'<i style="background:{rank_color(o)}">{E(tm)} #{o}</i>' if o is not None else f'<i class="nr">{E(tm)}</i>'
    b = f'<i style="background:{rank_color(d)}">{E(opp)} #{d}</i>' if d is not None else f'<i class="nr">{E(opp)}</i>'
    return f'<span class="mup">{a}<b>vs</b>{b}</span>'

def kick_text(g):
    if not g: return ""
    return E(g.get("kick") or "")

# which players get a page: a prop this week, or a real role this season (2+ games and 4+ PPR / game or 25%+ snaps)
pages = {}
for k, p in S.players.items():
    gs = p["games"]; u = S.usage(k, [g["w"] for g in gs]) if gs else None
    if p["legs"] or (u and u["n"] >= 2 and ((u["ppr"] or 0) >= 4 or (u["snap"] or 0) >= 0.25)):
        pages[k] = p
by_team = {}
for k, p in pages.items(): by_team.setdefault(p["team"], []).append(k)

PCSS = r"""
.pp{max-width:1100px;margin:16px auto 40px}
.pp a{color:var(--ink)}
.pp .crumb{font-size:12px;color:var(--mute);margin:0 0 10px}.pp .crumb a{color:var(--mute)}
.pp header{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;align-items:center;background:var(--chalk) var(--plays) center/360px 130px repeat;border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-bottom:14px}
.pp .tb{grid-row:1/3;display:inline-flex;align-items:center;justify-content:center;width:56px;height:56px;border-radius:10px;background:var(--p,#333);box-shadow:inset 0 -6px 0 var(--s,#000);color:#fff;font-family:var(--display);font-weight:700;font-size:22px;letter-spacing:.04em}
.pp h1{margin:0;font-family:var(--brand);font-style:italic;font-weight:800;font-size:clamp(28px,5vw,40px);line-height:1;letter-spacing:-.01em}
.pp .sub{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center;color:var(--mute);font-size:13px}
.pp .sub b{color:var(--ink);font-weight:600}
.pp .st{font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:2px 8px;border-radius:3px;color:#fff;background:var(--warn)}
.pp .st.out{background:var(--red)} .pp .st.dbt{background:#b3372b} .pp .st.q{background:var(--warn);color:#0f141c}
.pp .acts{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
.pp .acts a{font-size:12.5px;font-weight:600;text-decoration:none;border:1px solid var(--line);background:var(--card);border-radius:999px;padding:5px 12px}
.pp .acts a:hover{border-color:var(--red)}
.pp section{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:0 0 14px;overflow:hidden}
.pp h2{margin:0;padding:10px 14px;border-bottom:1px solid var(--line);font-family:var(--display);font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:14px;display:flex;gap:10px;align-items:baseline}
.pp h2 small{font-family:var(--body);font-weight:400;letter-spacing:0;text-transform:none;color:var(--mute);font-size:12px}
.pp .tw{overflow-x:auto}
.pp table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
.pp th,.pp td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
.pp th:first-child,.pp td:first-child{text-align:left}
.pp thead th{font-family:var(--display);font-weight:700;letter-spacing:.06em;text-transform:uppercase;font-size:11.5px;color:var(--mute)}
.pp tr.mk td{background:color-mix(in srgb,var(--chalk) 70%,transparent);font-family:var(--display);font-weight:700;letter-spacing:.06em;text-transform:uppercase;font-size:12px;text-align:left;padding:6px 10px}
.pp tr.mk td .mup{margin-left:8px;vertical-align:1px}
.pp .e.up{color:var(--good);font-weight:700} .pp .e.dn{color:var(--bad)}
.pp .hr{color:var(--mute)} .pp .hr b{color:var(--ink)}
.pp .bk a{display:inline-block;font-size:11.5px;font-weight:700;text-decoration:none;padding:3px 8px;border-radius:4px;margin-left:4px;color:#fff;background:#1493ff}
.pp .bk a.dkb{background:#53d337;color:#0b1a07} .pp .bk a.hrb{background:#5b2d8e} .pp .bk a.best{outline:2px solid var(--good);outline-offset:1px}
.pp .add{font:inherit;font-size:14px;font-weight:700;width:26px;height:26px;border-radius:5px;border:1px solid var(--red);background:none;color:var(--ink);cursor:pointer;line-height:1}
.pp .add.in{background:var(--red);color:#fff} .pp .add:disabled{opacity:.35;cursor:not-allowed}
.pp .mup{display:inline-flex;align-items:center;gap:3px;font-family:var(--body);font-size:11px;font-weight:700;letter-spacing:0;text-transform:none}
.pp .mup i{font-style:normal;color:#fff;padding:1px 6px;border-radius:3px} .pp .mup i.nr{background:var(--line);color:var(--ink)} .pp .mup b{color:var(--mute);font-weight:600}
.pp ul.fl{list-style:none;margin:0;padding:10px 14px;display:grid;gap:6px}
.pp ul.fl li{font-size:13px;line-height:1.45;padding-left:12px;position:relative}
.pp ul.fl li::before{content:"";position:absolute;left:0;top:7px;width:6px;height:6px;border-radius:50%;background:var(--mute)}
.pp ul.fl li.good::before{background:var(--good)} .pp ul.fl li.bad::before{background:var(--bad)} .pp ul.fl li.watch::before{background:var(--warn)}
.pp ul.fl li b{margin-right:5px} .pp ul.fl li.good b{color:var(--good)} .pp ul.fl li.bad b{color:var(--bad)} .pp ul.fl li.watch b{color:var(--warn)}
.pp .use{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:0}
.pp .use div{padding:10px 14px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.pp .use small{display:block;color:var(--mute);font-size:11px;letter-spacing:.06em;text-transform:uppercase}
.pp .use b{font-family:var(--display);font-size:22px} .pp .use em{font-style:normal;font-size:12px;margin-left:6px}
.pp .use em.up{color:var(--good)} .pp .use em.dn{color:var(--bad)}
.pp .bars{display:flex;align-items:flex-end;gap:6px;height:90px;padding:12px 14px 4px}
.pp .bars div{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;font-size:10.5px;color:var(--mute)}
.pp .bars i{display:block;width:100%;max-width:38px;background:var(--red);border-radius:3px 3px 0 0;min-height:2px}
.pp .bars i.lim{background:var(--warn)} .pp .bars span{margin-top:3px}
.pp .note{margin:0;padding:8px 14px 10px;color:var(--mute);font-size:12px;line-height:1.45}
.pp .mates{display:flex;flex-wrap:wrap;gap:6px;padding:10px 14px}
.pp .mates a{font-size:12.5px;text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:4px 10px;background:var(--chalk)}
.pp .mates a small{color:var(--mute);margin-left:4px}
.pp .none{padding:12px 14px;color:var(--mute);font-size:13px;margin:0}
.pp h2{flex-wrap:wrap}
.pp details.pg{border-top:1px solid var(--line)} .pp details.pg:first-of-type{border-top:0}
.pp details.pg>summary{list-style:none;cursor:pointer;display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;padding:11px 14px;background:color-mix(in srgb,var(--chalk) 55%,transparent)}
.pp details.pg>summary::-webkit-details-marker{display:none}
.pp details.pg>summary b.gt{font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:14px}
.pp details.pg>summary b.gt::before{content:"\25B8";display:inline-block;margin-right:7px;color:var(--red);transition:transform .15s}
.pp details.pg[open]>summary b.gt::before{transform:rotate(90deg)}
.pp details.pg>summary .gs{color:var(--mute);font-size:12.5px} .pp details.pg>summary .gs i{font-style:normal;font-weight:700} .pp i.up{color:var(--good)} .pp i.dn{color:var(--bad)}
.pp details.pg>summary .mup{margin-left:auto}
.pp details.pg thead th{background:none}
.pp .rec{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
.pp .rec div{padding:10px 14px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.pp .rec small{display:block;color:var(--mute);font-size:11px;letter-spacing:.06em;text-transform:uppercase} .pp .rec b{font-family:var(--display);font-size:24px;margin-right:8px}
.pp .rec i{font-style:normal;font-weight:700} .pp .rec em{font-style:normal;color:var(--mute);font-size:12px}
@media (max-width:640px){
 .pp table.props thead{display:none}
 .pp table.props tr:not(.mk){display:grid;grid-template-columns:1fr auto auto;grid-template-areas:"ln e ad" "bk bk bk" "mp bp hr";gap:6px 10px;padding:9px 12px;border-bottom:1px solid var(--line)}
 .pp table.props tr.mk{display:block} .pp table.props tr.mk td{display:block;white-space:normal;padding:6px 12px}
 .pp table.props td{border:0;padding:0;text-align:left}
 .pp table.props td.ln{grid-area:ln;font-weight:700;font-size:15px;align-self:center} .pp table.props td.e{grid-area:e;align-self:center;font-size:14px}
 .pp table.props td.ad{grid-area:ad} .pp table.props td.bk{grid-area:bk;white-space:normal} .pp table.props td.bk a:first-child{margin-left:0}
 .pp table.props td.mp{grid-area:mp} .pp table.props td.bp{grid-area:bp} .pp table.props td.hr{grid-area:hr}
 .pp table.props td[data-l]::before{content:attr(data-l) " ";color:var(--mute);font-size:11px;text-transform:uppercase;letter-spacing:.04em}
 .pp table.props td.mp,.pp table.props td.bp,.pp table.props td.hr{font-size:12.5px}
 .pp header{padding:14px} .pp .tb{width:46px;height:46px;font-size:18px}
}
.ppbar{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(var(--bs-tabs,0px) + 12px);z-index:65;display:none;align-items:center;gap:12px;background:var(--ink);color:var(--bg);border-radius:999px;padding:8px 8px 8px 16px;box-shadow:0 8px 24px rgba(0,0,0,.4);font-size:13px;font-weight:600}
.ppbar.on{display:flex} .ppbar a{background:var(--red);color:#fff;text-decoration:none;border-radius:999px;padding:6px 12px;font-weight:700}
/* directory */
.pd{max-width:1100px;margin:16px auto 40px}
.pd h1{font-family:var(--display);font-size:30px;margin:0 0 4px} .pd p.m{color:var(--mute);margin:0 0 12px;line-height:1.5}
.pd .ctl{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.pd input{flex:1 1 220px;font:inherit;font-size:15px;padding:9px 12px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.pd .pos button{font:inherit;font-size:12.5px;font-weight:700;padding:8px 12px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.pd .pos button.on{background:var(--red);border-color:var(--red);color:#fff}
.pd ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px}
.pd li a{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:10px;padding:9px 12px}
.pd li a:hover{border-color:var(--red)}
.pd li .tb{flex:none;display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:7px;background:var(--p,#333);box-shadow:inset 0 -4px 0 var(--s,#000);color:#fff;font-family:var(--display);font-weight:700;font-size:13px}
.pd li b{display:block;font-weight:600} .pd li small{color:var(--mute);font-size:12px}
.pd li .st{margin-left:auto;font-size:10px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:2px 6px;border-radius:3px;background:var(--red);color:#fff}
.pd li .st.q{background:var(--warn);color:#0f141c}
.pd .cnt{color:var(--mute);font-size:12px;margin:8px 0 0}
"""

PJS = r"""
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
"""

def team_colors(team):
    g = S.game_of(team)
    if g:
        c = g.get("ca") if g.get("a") == team else g.get("cb")
        if c and len(c) >= 2: return c[0], c[1]
    return "#2b3442", "#141a24"

def head(title, desc):
    link, base = __import__("account")._base_css()
    return f'<title>{E(title)}</title>\n<meta name="description" content="{E(desc)}">\n{link}\n<link rel="stylesheet" href="/player/player.css">\n<style>/* styles: /player/player.css */</style>\n'

PGROUPS = {"td": ("Touchdowns", ["Anytime TD", "First TD", "2+ TD", "3+ TD"]),
           "rec": ("Receiving", ["Receiving Yards", "Receptions", "Longest Reception"]),
           "rush": ("Rushing", ["Rushing Yards", "Rush + Rec Yards"]),
           "pass": ("Passing", ["Passing Yards"]),
           "und": ("Unders", ["Under Passing Yards", "Under Rushing Yards", "Under Receiving Yards", "Under Receptions"])}
PORDER = {"QB": ["pass", "rush", "td", "und"], "RB": ["rush", "rec", "td", "und"], "WR": ["rec", "td", "rush", "und"], "TE": ["rec", "td", "rush", "und"]}
TDLAB = {"Anytime TD": "Anytime", "First TD": "First TD", "2+ TD": "2+ TDs", "3+ TD": "3+ TDs"}
def _leg_row(p, l, m, lab, played, ko):
    hr = cleared(l, played)
    e = l.get("e"); ecls = "up" if (e or 0) > 0 else "dn"
    fd = (l.get("fd") or {}).get("u")
    bk = (f'<a href="{E(fd)}" target="_blank" rel="noopener" title="Open FanDuel with this leg">FD {am(l["o"])}</a>' if fd else f'<span class="hr">FD {am(l["o"])}</span>')
    if BL:
        try: bk += BL.buttons([l], price=True)
        except Exception: pass
    return (f'<tr><td class="ln">{E(lab)}</td><td class="bk">{bk}</td><td class="mp" data-l="Model">{pc(l.get("p"))}</td><td class="bp" data-l="Book">{pc(l.get("bk"))}</td>'
            f'<td class="e {ecls}" data-l="Edge">{("+" if (e or 0) >= 0 else "")}{(e or 0) * 100:.1f}</td>'
            f'<td class="hr" data-l="Season">{("<b>" + str(hr[0]) + "</b>/" + str(hr[1])) if hr else "—"}</td>'
            f'<td class="ad"><button type="button" class="add" data-k="{E(legkey(l))}" data-ko="{ko}" aria-label="Add {E(p["name"])} {E(m)} {E(lab)} to betslip">+</button></td></tr>')

def props_block(p):
    """owner 10/30: like props grouped (Touchdowns: anytime / first / 2+ / 3+; Receiving; Rushing; Passing), each group collapsible.
    His main group (by position) opens; the rest are closed with a one-line summary: lines, best edge and where it is."""
    legs = [l for l in p["legs"] if l["m"] in MORDER]
    if not legs: return '<section><h2>This week\'s props</h2><p class="none">No FanDuel player props for him on the board this week' + (" (his game has kicked off or he is not active)" if p["games"] else "") + '.</p></section>'
    g = S.games.get(legs[0].get("g")) or S.game_of(p["team"]); ko = (g or {}).get("ko") or 0
    played = [x for x in p["games"] if x["w"] < W] or p["games"]
    order = PORDER.get(p["pos"], ["rec", "rush", "td", "pass"]); order = order + [k for k in PGROUPS if k not in order]
    blocks = []; first = True
    for gk in order:
        gname, ms = PGROUPS[gk]
        gl = [l for l in legs if l["m"] in ms]
        if not gl: continue
        rows = []
        if gk == "td":
            l0 = gl[0]; o, d = (l0.get("or") or [None])[0], (l0.get("dr") or [None])[0]
            for m in ms:
                for l in [l for l in gl if l["m"] == m]: rows.append(_leg_row(p, l, m, TDLAB[m], played, ko))
            mup = pill(p["team"], o, l0.get("opp"), d) if (o is not None or d is not None) else ""
        else:
            mup = ""
            for m in ms:
                ls = sorted([l for l in gl if l["m"] == m], key=lambda l: float(l.get("ln") or 0))
                if not ls: continue
                l0 = ls[0]; o, d = (l0.get("or") or [None])[0], (l0.get("dr") or [None])[0]
                rows.append(f'<tr class="mk"><td colspan="8">{E(m)}{(" · proj " + str(round(l0["proj"], 1))) if isinstance(l0.get("proj"), (int, float)) else ""}{pill(p["team"], o, l0.get("opp"), d) if (o is not None or d is not None) else ""}</td></tr>')
                for l in ls:
                    lab = ("Under " + str(l["ln"])) if m.startswith("Under ") else f'{jsround(l["ln"]) if float(l["ln"]).is_integer() else l["ln"]}+'
                    rows.append(_leg_row(p, l, m, lab, played, ko))
        best = max(gl, key=lambda l: (l.get("e") if l.get("e") is not None else -9))
        be = best.get("e") or 0
        bl = TDLAB.get(best["m"]) or (("under " + str(best["ln"])) if best["m"].startswith("Under ") else f'{jsround(best["ln"])}+ {str(best.get("ms") or best["m"]).lower()}')
        summ = (f'<summary><b class="gt">{gname}</b><span class="gs">{len(gl)} line{"s" if len(gl) != 1 else ""} · best edge <i class="{"up" if be > 0 else "dn"}">{"+" if be >= 0 else ""}{100 * be:.1f}</i> {E(bl)}</span>{mup}</summary>')
        blocks.append(f'<details class="pg"{" open" if first else ""}>{summ}<div class="tw"><table class="props"><thead><tr><th>Line</th><th>Bet it</th><th>Model</th><th>Book</th><th>Edge</th><th>This season</th><th>Slip</th></tr></thead><tbody>'
                      + "".join(rows) + '</tbody></table></div></details>')
        first = False
    return ('<section><h2>This week\'s props <small>tap a group to open it · FanDuel price · model % (what the site shows) · book % · edge · cleared this line in his games this season</small></h2>'
            + "".join(blocks) +
            '<p class="note">Model % is the number the whole site shows (the model blended with FanDuel\'s price). "This season" counts the games he played, before this week. DK / HR buttons show their price when they post the same line; ≈ means their nearest line.</p></section>')

# ---- the model's record on him (owner 10/30): every leg frozen before kickoff and graded from the box score ('V2 - FanDuel Leg Snapshots',
# in/legsnaps.json, the latest frozen copy of each leg). "Liked" = the verdict the boards show (VALUE / STRONG VALUE); units at the FanDuel price.
REC = {}
try:
    _v = json.load(open(os.path.join(IN, "legsnaps.json")))["values"]; _h = {c: i for i, c in enumerate(_v[0])}
    for _r in _v[1:]:
        _r = list(_r) + [""] * (len(_v[0]) - len(_r))
        if str(_r[_h["Latest Snapshot"]]).upper() != "TRUE" or _r[_h["Result"]] not in ("HIT", "MISS"): continue
        try: _u = float(_r[_h["Units (1u)"]])
        except Exception: _u = None
        try: _bk = float(_r[_h["Book implied %"]])
        except Exception: _bk = None
        REC.setdefault(PD.norm(_r[_h["Player"]]), []).append({"w": int(float(_r[_h["Week"]])), "m": _r[_h["Market"]], "hit": _r[_h["Result"]] == "HIT", "u": _u, "bk": _bk,
            "liked": str(_r[_h["Verdict"]]).upper() in ("VALUE", "STRONG VALUE")})
except Exception as _e:
    print("note: no leg snapshots for player records:", _e)

def record_block(p):
    rs = REC.get(PD.norm(p["name"]))
    if not rs: return ""
    lk = [r for r in rs if r["liked"]]
    wk = sorted({r["w"] for r in rs}); span = f"Week {wk[0]}" + (f"-{wk[-1]}" if len(wk) > 1 else "")
    def wl(xs): h = sum(r["hit"] for r in xs); return f"{h}-{len(xs) - h}"
    def un(xs): u = sum(r["u"] for r in xs if r["u"] is not None); return f'<i class="{"up" if u >= 0 else "dn"}">{"+" if u >= 0 else "\u2212"}{abs(u):.1f}u</i>'
    hit = sum(r["hit"] for r in rs) / len(rs); bks = [r["bk"] for r in rs if r["bk"] is not None]; bk = sum(bks) / len(bks) if bks else None
    head = (f'<div class="rec"><div><small>Legs we flagged as value</small><b>{wl(lk) if lk else "—"}</b>{un(lk) if lk else ""}</div>'
            f'<div><small>Every line we priced on him</small><b>{100 * hit:.0f}%</b><em>hit{(" · book expected " + format(100 * bk, ".0f") + "%") if bk is not None else ""}</em></div></div>')
    bym = {}
    for r in rs: bym.setdefault(r["m"], []).append(r)
    rows = "".join(f'<tr><td>{E(m)}</td><td>{len(xs)}</td><td>{wl(xs)}</td><td>{wl([r for r in xs if r["liked"]]) if any(r["liked"] for r in xs) else "—"}</td><td>{un([r for r in xs if r["liked"]]) if any(r["liked"] for r in xs) else "—"}</td></tr>'
                   for m, xs in sorted(bym.items(), key=lambda kv: -len(kv[1])))
    return ('<section><h2>BetSweep\'s record on him <small>' + span + ' · every line frozen before kickoff, graded from the box score</small></h2>' + head +
            '<details class="pg"><summary><b class="gt">By market</b></summary><div class="tw"><table><thead><tr><th>Market</th><th>Lines</th><th>All W-L</th><th>Value W-L</th><th>Value units</th></tr></thead><tbody>' + rows +
            '</tbody></table></div></details><p class="note">"Value" = the legs the boards marked VALUE or STRONG VALUE before kickoff; units are 1 unit each at the FanDuel price. Every week\'s full grading is on the <a href="/receipts/">receipts</a>.</p></section>')

def jsonld(p, opp):
    import json as _j
    g = S.game_of(p["team"]); tn = None
    if g: tn = g.get("na") if g.get("a") == p["team"] else g.get("nb")
    POSN = {"QB": "quarterback", "RB": "running back", "WR": "wide receiver", "TE": "tight end"}
    d = {"@context": "https://schema.org", "@type": "ProfilePage", "name": f'{p["name"]} props, stats & matchup',
         "mainEntity": {"@type": "Person", "name": p["name"], "jobTitle": f'NFL {POSN.get(p["pos"], p["pos"])}', **({"memberOf": {"@type": "SportsTeam", "name": tn, "sport": "American football"}} if tn else {})}}
    return '<script type="application/ld+json">' + _j.dumps(d).replace("</", "<\\/") + '</script>'

def flags_block(p):
    seen, items = set(), []
    for l in p["legs"]:
        for f in (l.get("fh") or []):
            if len(f) >= 3 and f[2] not in seen:
                seen.add(f[2]); items.append(f'<li class="{E(f[0])}"><b>{E(f[1])}</b>{E(f[2])}</li>')
    for l in p["legs"]:
        for t in str(l.get("w") or "").split(";"):
            t = t.strip()
            if t and t not in seen and not any(t in s for s in seen): seen.add(t); items.append(f'<li>{E(t)}</li>')
    if not items: return ""
    return '<section><h2>What the model sees</h2><ul class="fl">' + "".join(items[:14]) + '</ul></section>'

def usage_block(k, p):
    gs = p["games"]
    if not gs: return ""
    past = [g for g in gs if g["w"] < W] or gs
    tw = [w for w in S.team_weeks.get(p["team"], []) if w < W]; l3 = tw[-3:]
    s = S.usage(k, [g["w"] for g in past]); r = S.usage(k, l3)
    def cell(lab, a, b, fmt, pct=False):
        if a is None: return ""
        d = "" if (b is None) else (b - a)
        em = ""
        if b is not None and abs(d) >= (0.03 if pct else 0.5):
            em = f'<em class="{"up" if d > 0 else "dn"}">L3 {fmt(b)}</em>'
        elif b is not None: em = f'<em>L3 {fmt(b)}</em>'
        return f'<div><small>{lab}</small><b>{fmt(a)}</b>{em}</div>'
    P = lambda x: f"{100 * x:.0f}%"; N = lambda x: f"{x:.1f}"
    cells = cell("Snap share", s["snap"], r["snap"] if r else None, P, True)
    if p["pos"] in ("WR", "TE", "RB"): cells += cell("Target share", s["ts"], r["ts"] if r else None, P, True) + cell("Targets / game", s["tgt"], r["tgt"] if r else None, N)
    if p["pos"] in ("RB", "QB"): cells += cell("Carries / game", s["car"], r["car"] if r else None, N)
    if p["pos"] == "RB": cells += cell("Carry share", s["cs"], r["cs"] if r else None, P, True)
    cells += cell("PPR pts / game", s["ppr"], r["ppr"] if r else None, N)
    # snap bars, one per team week (a missed week shows as a gap labelled "-")
    bars = ""
    have = {g["w"]: g for g in gs}
    for w in S.team_weeks.get(p["team"], []):
        g = have.get(w); v = (g or {}).get("snap")
        h = 0 if v is None else max(2, round(v * 100))
        bars += f'<div title="Week {w}{(" vs " + g["opp"]) if g else ""}: {("%d%% of snaps" % round(v * 100)) if v is not None else ("did not play" if not g else "no snap data")}"><i style="height:{h}%"></i><span>{("W" + str(w)) if g else "out"}</span></div>'
    return ('<section><h2>Usage <small>season (games played) · last 3 team games (L3) · snap share by week</small></h2><div class="use">' + cells + '</div>'
            f'<div class="bars" aria-label="snap share by week">{bars}</div></section>')

def log_block(p):
    gs = p["games"]
    if not gs: return '<section><h2>Game log</h2><p class="none">No games for him in the 2026 game log yet.</p></section>'
    qb = p["pos"] == "QB"
    if qb:
        hdr = "<th>Wk</th><th>Opp</th><th>Snap</th><th>Att</th><th>Pass yds</th><th>Pass TD</th><th>INT</th><th>Car</th><th>Rush yds</th><th>Rush TD</th><th>PPR</th>"
        def row(g): return (f'<td>{g["w"]}</td><td>{E(g["opp"])}</td><td>{("%d%%" % round(g["snap"] * 100)) if g["snap"] is not None else "—"}</td><td>{g["att"]:.0f}</td><td>{g["pass"]:.0f}</td><td>{g["ptd"]:.0f}</td><td>{g["int"]:.0f}</td>'
                            f'<td>{g["car"]:.0f}</td><td>{g["rush"]:.0f}</td><td>{g["td"]:.0f}</td><td>{g["ppr"]:.1f}</td>')
    else:
        hdr = "<th>Wk</th><th>Opp</th><th>Snap</th><th>Tgt</th><th>Rec</th><th>Rec yds</th><th>Car</th><th>Rush yds</th><th>TD</th><th>Tgt share</th><th>PPR</th>"
        def row(g): return (f'<td>{g["w"]}</td><td>{E(g["opp"])}</td><td>{("%d%%" % round(g["snap"] * 100)) if g["snap"] is not None else "—"}</td><td>{g["tgt"]:.0f}</td><td>{g["rec"]:.0f}</td><td>{g["recy"]:.0f}</td>'
                            f'<td>{g["car"]:.0f}</td><td>{g["rush"]:.0f}</td><td>{g["td"]:.0f}</td><td>{100 * g["ts"]:.0f}%</td><td>{g["ppr"]:.1f}</td>')
    body = "".join(f"<tr>{row(g)}</tr>" for g in reversed(gs))
    return f'<section><h2>Game log <small>2026 regular season, newest first</small></h2><div class="tw"><table><thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table></div></section>'

def mates_block(k, p):
    ms = [kk for kk in by_team.get(p["team"], []) if kk != k]
    if not ms: return ""
    def score(kk):
        u = S.usage(kk, [g["w"] for g in pages[kk]["games"]]) if pages[kk]["games"] else None
        return -((u or {}).get("ppr") or 0)
    ms.sort(key=score)
    return '<section><h2>Teammates</h2><div class="mates">' + "".join(f'<a href="/player/{pages[kk]["slug"]}/">{E(pages[kk]["name"])}<small>{pages[kk]["pos"]}</small></a>' for kk in ms[:16]) + '</div></section>'

def page(k, p):
    g = S.game_of(p["team"]); c1, c2 = team_colors(p["team"])
    opp = (g["b"] if g["a"] == p["team"] else g["a"]) if g else None
    home = g and g.get("b") == p["team"]
    tp = (g["pb"] if home else g["pa"]) if g else None
    sub = f'<b>{p["pos"]}</b> · {E(p["team"])}'
    if g: sub += f' · {"vs" if home else "@"} {E(opp)} · {kick_text(g)}' + (f' · team total {tp:.1f} (model)' if isinstance(tp, (int, float)) else "")
    nu, nsrc = news_url(p["name"])
    top = sorted([l for l in p["legs"] if l["m"] in MORDER and l.get("e") is not None], key=lambda l: -l["e"])[:1]
    desc = f'{p["name"]} ({p["pos"]}, {p["team"]}) Week {W}' + (f' vs {opp}' if opp else "") + ': props with FanDuel, DraftKings and Hard Rock prices, the BetSweep model\'s chance and edge, hit rates, matchup ranks, snap share and game log.'
    acts = (f'<a href="/build/?p={E(p["name"])}">Open in Parlay Builder</a>' if p["legs"] else "") + f'<a href="{E(nu)}" target="_blank" rel="noopener">News ({nsrc})</a>' + (f'<a href="/boards/#{E(g["gid"])}">Matchup board</a>' if g else "") + '<a href="/benefits/">Who benefits</a><a href="/player/">All players</a>'
    body = (head(f'{p["name"]} props, stats & matchup · Week {W} · BetSweep', desc) +
            f'<div class="pp" data-week="{W}"><p class="crumb"><a href="/player/">Players</a> › {E(p["team"])} › {E(p["name"])}</p>'
            f'<header><span class="tb" style="--p:{c1};--s:{c2}">{E(p["team"])}</span><h1>{E(p["name"])}</h1><div class="sub">{sub} {status_badge(p["status"])}</div><div class="acts">{acts}</div></header>'
            + props_block(p) + record_block(p) + flags_block(p) + usage_block(k, p) + log_block(p) + mates_block(k, p) + jsonld(p, opp) +
            '</div><div class="ppbar" id="ppbar"><b></b><a href="/build/">Open betslip</a></div><script src="/player/player.js" defer></script>')
    return body, desc

os.makedirs(os.path.join(OUT, "players"), exist_ok=True)
for f in os.listdir(os.path.join(OUT, "players")): os.remove(os.path.join(OUT, "players", f))
slugs = {}; n_legs = 0
for k, p in pages.items():
    body, desc = page(k, p)
    open(os.path.join(OUT, "players", p["slug"] + ".html"), "w").write(body)
    slugs[p["name"]] = p["slug"]; n_legs += bool(p["legs"])
open(os.path.join(OUT, "players", "player.css"), "w").write(__import__("account")._base_css()[1] + PCSS)   # site tokens + light/dark, once for every page
open(os.path.join(OUT, "players", "player.js"), "w").write(PJS)
json.dump(slugs, open(os.path.join(OUT, "players", "slugs.json"), "w"))

# directory
def dir_item(k, p):
    c1, c2 = team_colors(p["team"]); g = S.game_of(p["team"])
    opp = (g["b"] if g["a"] == p["team"] else g["a"]) if g else ""
    top = sorted([l for l in p["legs"] if l["m"] in MORDER and l.get("e") is not None], key=lambda l: -l["e"])[:1]
    sub = f'{p["pos"]} · {p["team"]}' + (f' vs {opp}' if opp else " · bye") + (f' · {len([1 for l in p["legs"] if l["m"] in MORDER])} props' if p["legs"] else "")
    st = p["status"] and p["status"][0] in ("Out", "Doubtful", "Questionable") and p["status"][0]
    sp = f'<span class="st{"" if st in ("Out", "Doubtful") else " q"}">{E(st)}</span>' if st else ""
    s = (p["name"] + " " + p["team"] + " " + p["pos"] + " " + (opp or "")).lower()
    u = S.usage(k, [g["w"] for g in p["games"]]) if p["games"] else None
    return (-(1 if p["legs"] else 0), -((u or {}).get("ppr") or 0)), f'<li data-pos="{p["pos"]}" data-s="{E(s)}"><a href="/player/{p["slug"]}/"><span class="tb" style="--p:{c1};--s:{c2}">{E(p["team"])}</span><span><b>{E(p["name"])}</b><small>{E(sub)}</small></span>{sp}</a></li>'
items = sorted(dir_item(k, p) for k, p in pages.items())
idx = (head(f"NFL player props & stats · Week {W} · BetSweep", f"Every NFL player with a prop or a role this season: FanDuel, DraftKings and Hard Rock prices against the BetSweep model, hit rates, matchups, snap share and game logs. Week {W}.") +
       f'<div class="pd" data-week="{W}"><h1>Players</h1><p class="m">Every player with a prop on the board this week (listed first) or a real role this season. One page each: his lines at FanDuel, DraftKings and Hard Rock against the model, how often he has cleared them, his offense vs the defense, snap share and game log.</p>'
       '<div class="ctl"><input id="pdq" type="search" placeholder="Search a player, team or position" autocomplete="off" aria-label="Search players"><div class="pos">' +
       "".join(f'<button type="button" data-p="{x}"{" class=\"on\"" if x == "ALL" else ""}>{x}</button>' for x in ("ALL", "QB", "RB", "WR", "TE")) +
       '</div></div><ul>' + "".join(h for _, h in items) + '</ul><p class="cnt" id="pdcnt"></p></div><script src="/player/player.js" defer></script>')
open(os.path.join(OUT, "players", "index.html"), "w").write(idx)
print(f"wrote out/players: {len(pages)} player pages ({n_legs} with props this week), week {W}")
