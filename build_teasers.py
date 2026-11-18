#!/usr/bin/env python3
"""build_teasers.py - the teaser finder (owner 11/5: "do all of your out of the box things").

A teaser moves every spread / total in the slip 6, 6.5 or 7 points in your favour and prices the two-leg combination at one fixed number
(FanDuel: about -130 for 6 points, -140 for 6.5, -150 for 7 - the page lets you set the exact number your book shows). The classic edge
(Wong teasers) is a leg whose move crosses both 3 and 7: an underdog +1.5 to +2.5 teased to +7.5 / +8.5, a favourite -7.5 to -8.5 teased
to -1.5 / -2.5. We score every teased leg with the same model gamelines.py uses for the boards and builder: final margin ~ Normal(model
margin, 12.6) and total ~ Normal(model total, 12.9), the model's centre shrunk halfway to FanDuel's main line (SHRINK = 0.5, exactly as
the game-line legs are priced). The chance of the teased leg is then Phi((centre + teased line) / sd). Two legs from different games are
independent; same-game pairs are not offered (spread and total of one game are correlated, and books void them anyway).

Reads: out/builder_data.json (games: pa, pb, ko), in/gamelines.json + in/games.csv (FanDuel main spread / total; the nflverse line as
the fallback). Writes: out/teasers.html (page body, wrapped by build_site.py at /teasers/) and out/teasers.json.
"""
import json, os, math, csv, datetime as dt
import gamelines as GL

HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
E = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
PHI = GL._phi; SDM, SDT, SHRINK = GL.SD_MARGIN, GL.SD_TOTAL, GL.SHRINK
POINTS = [6.0, 6.5, 7.0]
DEFAULT_PRICE = {6.0: -130, 6.5: -140, 7.0: -150}   # two-leg teaser prices the page starts with (editable on the page)

def imp(o): return (100 / (o + 100)) if o > 0 else (-o / (-o + 100))
def am(o): o = int(round(o)); return f"+{o}" if o > 0 else str(o)
def crosses(lo, hi):
    """does the move from line lo to hi (both from the bettor's side, e.g. -8 -> -2 or +2 -> +8) cross both 3 and 7?"""
    a, b = sorted([abs(lo), abs(hi)]); return a <= 3 <= b and a <= 7 <= b

def kind_of(lo, hi):
    """The kind of move from the bettor's own line lo to the teased line hi: 'k2' through both 3 and 7 (the page's 'crosses' test),
    'z' a favourite teased across zero into a dog, 'k1' through one of 3 / 7, 'k0' through neither."""
    if lo * hi < 0 or lo == 0 or hi == 0: return "z"
    if crosses(lo, hi): return "k2"
    a, b = sorted([abs(lo), abs(hi)]); return "k1" if (a <= 3 <= b or a <= 7 <= b) else "k0"
KIND_TXT = {"k2": "Through 3 and 7", "k1": "Through 3 or 7", "z": "Favorite teased past zero", "k0": "Through neither", "tot": "Totals, over or under"}
HIST_FROM = 2015   # the extra point moved back in 2015, which changed how often games land on each margin
def history(path):
    """How every teased leg would have done, regular season since HIST_FROM, at the closing line in in/games.csv (nflverse: result = home
    margin, spread_line = points the home team was favoured by). {pts: {kind: [won, lost, pushed]}}. 11/17: until now every leg on the page
    came off a smooth curve, and because the model's margin IS FanDuel's line the page said 68% for every 6-point leg and 47% / -9.9 for
    every pair - it could not tell a teaser through 3 and 7 from any other."""
    out = {pts: {k: [0, 0, 0] for k in KIND_TXT} for pts in POINTS}
    def f(x):
        try: return float(x)
        except (TypeError, ValueError): return None
    try: rows = list(csv.DictReader(open(path, encoding="utf-8")))
    except Exception as e: print("note: teaser history not read:", e); return out
    for r in rows:
        try:
            if int(r.get("season") or 0) < HIST_FROM or r.get("game_type") != "REG": continue
        except ValueError: continue
        res, sp, tl, tt = f(r.get("result")), f(r.get("spread_line")), f(r.get("total_line")), f(r.get("total"))
        for pts in POINTS:
            if res is not None and sp is not None:
                for sgn in (1, -1):
                    line = -sp * sgn; x = res * sgn + line + pts
                    out[pts][kind_of(line, line + pts)][0 if x > 0 else 1 if x < 0 else 2] += 1
            if tl is not None and tt is not None:
                for x in (tt - (tl - pts), (tl + pts) - tt): out[pts]["tot"][0 if x > 0 else 1 if x < 0 else 2] += 1
    return out
HIST = history(os.path.join(IN, "games.csv"))
def hrate(pts, k):
    w, l, _ = HIST[pts][k]; return (w / (w + l)) if (w + l) >= 150 else None   # too few games: the caller keeps the smooth curve
def leg_p(pts, k, smooth, sd):
    """History for this kind of move, shifted by however far the model's own centre sits from the line (zero when they agree)."""
    h = hrate(pts, k)
    return smooth if h is None else min(0.99, max(0.01, h + (smooth - PHI(pts / sd))))

D = json.load(open(os.path.join(OUT, "builder_data.json"))); W = D["week"]
fdgl = GL.load_fd(IN); sched = GL.load_sched(IN, W)
now = dt.datetime.now(dt.timezone.utc).timestamp() * 1000
games = D.get("games", [])
def _at(g):   # audit 11/10: "WAS @ NYG" from the schedule (build_builder puts home / away on each game); a-b is not away-home
    return f'{g["away"]} @ {g["home"]}' if g.get("home") and g.get("away") and not g.get("nt") else f'{g.get("a", "")} vs {g.get("b", "")}'
live = [g for g in games if not g.get("ko") or g["ko"] > now]
if not live and os.environ.get("TEASERS_ALL"): live = games   # smoke builds on stale data: TEASERS_ALL=1 keeps kicked-off games
legs = []
for g in live:
    a, b, pa, pb = g["a"], g["b"], g.get("pa"), g.get("pb")
    if pa is None or pb is None: continue
    key = frozenset([a, b]); sch = sched.get(key)
    home = sch["home_team"] if sch else b
    # FanDuel main spread (home team's line) and total; nflverse consensus as the fallback
    def fd_main(side, mk):
        c = [(k, v) for k, v in fdgl.items() if k[0] == side and k[1] == mk and k[3] == key]
        if not c: return None, None
        # the main line = the one priced nearest -110 on both sides; FanDuel lists alternates too
        c.sort(key=lambda kv: abs(abs(kv[1][0]) - 110)); return c[0][0][2], c[0][1][0]
    sh, osh = fd_main(home, "Spread"); tl, otl = fd_main("OVER", "Total")
    if sh is None and sch and sch.get("spread_line") not in (None, "", "NA"): sh = -float(sch["spread_line"]) if home == sch["home_team"] else float(sch["spread_line"])   # nflverse spread_line = home margin
    if tl is None and sch and sch.get("total_line") not in (None, "", "NA"): tl = float(sch["total_line"])
    m_model = (pb - pa) if home == b else (pa - pb)    # model home margin = home points - away points (pa/pb are team a's / team b's)
    t_model = pa + pb
    m_centre = m_model if sh is None else SHRINK * m_model + (1 - SHRINK) * (-sh)
    t_centre = t_model if tl is None else SHRINK * t_model + (1 - SHRINK) * tl
    away = a if home == b else b
    for pts in POINTS:
        if sh is not None:
            for side, sgn in ((home, 1), (away, -1)):
                line = sh * sgn            # this side's own line (home: sh; away: -sh)
                teased = line + pts        # more points in the bettor's favour
                mu = m_centre * sgn        # this side's expected margin
                ps = PHI((mu + teased) / SDM); mk = kind_of(line, teased); p = leg_p(pts, mk, ps, SDM)
                legs.append({"gid": g["gid"], "kind": "spread", "side": side, "nick": GL.NICK.get(side, side), "line": line, "teased": teased, "pts": pts, "p": round(p, 4), "ps": round(ps, 4), "mk": mk,
                             "p0": round(PHI((mu + line) / SDM), 4), "key": crosses(line, teased), "ko": g.get("ko"), "kick": g.get("kick", ""), "a": a, "b": b, "at": _at(g), "ml": None})
        if tl is not None:
            for side, sgn in (("OVER", 1), ("UNDER", -1)):
                teased = tl - pts if side == "OVER" else tl + pts
                ps = PHI((t_centre - teased) / SDT) if side == "OVER" else PHI((teased - t_centre) / SDT); p = leg_p(pts, "tot", ps, SDT)
                p0 = PHI((t_centre - tl) / SDT) if side == "OVER" else PHI((tl - t_centre) / SDT)
                legs.append({"gid": g["gid"], "kind": "total", "side": side, "nick": side.title(), "line": tl, "teased": teased, "pts": pts, "p": round(p, 4), "ps": round(ps, 4), "mk": "tot", "p0": round(p0, 4),
                             "key": False, "ko": g.get("ko"), "kick": g.get("kick", ""), "a": a, "b": b, "at": _at(g), "ml": None})
# best pairs per points: top legs by chance, different games; joint = product; EV at the default price
pairs = {}
for pts in POINTS:
    cand = sorted([l for l in legs if l["pts"] == pts], key=lambda l: (-l["p"], l["kind"] != "spread"))[:24]
    out = []
    for i in range(len(cand)):
        for j in range(i + 1, len(cand)):
            x, y = cand[i], cand[j]
            if x["gid"] == y["gid"]: continue
            joint = x["p"] * y["p"]; price = DEFAULT_PRICE[pts]; be = imp(price)
            out.append({"legs": [x, y], "joint": round(joint, 4), "edge": round((joint - be) * 100, 1), "keys": int(x["key"]) + int(y["key"])})
    out.sort(key=lambda p: (-p["edge"], -p["keys"])); pairs[str(pts)] = out[:12]
    kl = sorted([l for l in legs if l["pts"] == pts and l["key"]], key=lambda l: -l["p"])
    classic = []
    for i in range(len(kl)):
        for j in range(i + 1, len(kl)):
            x, y = kl[i], kl[j]
            if x["gid"] == y["gid"]: continue
            joint = x["p"] * y["p"]; classic.append({"legs": [x, y], "joint": round(joint, 4), "edge": round((joint - imp(DEFAULT_PRICE[pts])) * 100, 1), "keys": 2})
    classic.sort(key=lambda p: -p["edge"]); pairs[str(pts) + "k"] = classic[:8]
json.dump({"week": W, "built": dt.datetime.now(dt.timezone.utc).isoformat(), "sd": {"margin": SDM, "total": SDT, "shrink": SHRINK}, "history": {"from": HIST_FROM, "by": {f"{k:g}": v for k, v in HIST.items()}}, "prices": {str(k): v for k, v in DEFAULT_PRICE.items()}, "legs": legs, "pairs": pairs}, open(os.path.join(OUT, "teasers.json"), "w"))

def leg_txt(l):
    if l["kind"] == "spread": return f"{l['nick']} {l['teased']:+g} <small>(from {l['line']:+g})</small>"
    return f"{l['nick']} {l['teased']:g} <small>(from {l['line']:g})</small>"
CROSS_TXT = {"k2": "3 &amp; 7", "k1": "3 or 7", "z": "past zero", "k0": "", "tot": ""}
def rec_txt(pts, k):
    w, l, _ = HIST[pts][k]; return f"{w:,}&ndash;{l:,}"
def leg_row(l):
    h = hrate(l["pts"], l["mk"])
    return (f'<tr class="{"keyx" if l["key"] else ""}"><td><b>{leg_txt(l)}</b><small class="g">{E(l.get("at") or (l["a"] + " vs " + l["b"]))} · {E(l["kick"])}</small></td>'
            f'<td class="r"><b>{l["p"]*100:.0f}%</b>' + (f'<small>{rec_txt(l["pts"], l["mk"])}</small>' if h is not None else '<small>model curve</small>') + f'</td><td class="r">{CROSS_TXT.get(l["mk"], "")}</td></tr>')
def am_from_p(pr):
    """American odds whose implied chance is pr."""
    return -100 * pr / (1 - pr) if pr >= 0.5 else 100 * (1 - pr) / pr
def verdict(pts, price):
    """One plain answer for this number at this price (the page's script rewrites it when the price box changes; keep the two in step)."""
    be = imp(price); need = math.sqrt(be); h2 = hrate(pts, "k2")
    if h2 is None: return f"At {am(price)} each leg has to win {need*100:.1f}%."
    w, l, _ = HIST[pts]["k2"]; others = max((hrate(pts, k) or 0) for k in ("k1", "k0", "z", "tot"))
    head = f"At {am(price)} each leg has to win <b>{need*100:.1f}%</b>. Since {HIST_FROM}, legs teased through 3 and 7 have won <b>{h2*100:.1f}%</b> ({w:,}&ndash;{l:,})"
    safe = math.ceil(am_from_p(h2 * h2) / 5) * 5
    if h2 >= need: return head + f", so two of them clear this price by {(h2*h2 - be)*100:.1f} points. No other kind of leg has won more than {others*100:.0f}%."
    return head + f" - {(need - h2)*100:.1f} short, and no other kind has won more than {others*100:.0f}%. Nothing clears this price; two legs through 3 and 7 need about {am(safe)} or better."
sections = []
for pts in POINTS:
    mine = [l for l in legs if l["pts"] == pts]
    k2 = sorted([l for l in mine if l["mk"] == "k2"], key=lambda l: (-l["p"], l.get("ko") or 0))
    rest = sorted([l for l in mine if l["mk"] != "k2"], key=lambda l: (-l["p"], l["kind"] != "spread", l.get("ko") or 0))[:12]
    ps = pairs[str(pts)][:3]
    def pair_li(p): return (f'<li><div class="pl">{leg_txt(p["legs"][0])}<i>+</i>{leg_txt(p["legs"][1])}</div><div class="pn"><b>{p["joint"]*100:.0f}%</b><small>to cash</small></div>'
                      f'<div class="pe {"up" if p["edge"] >= 0 else "dn"}" data-joint="{p["joint"]}"><b>{p["edge"]:+.1f}</b><small>vs the price</small></div>{"<span class=\"kx\">both through 3 &amp; 7</span>" if p["keys"] == 2 else ""}</li>')
    pr_html = "".join(pair_li(p) for p in ps) or '<li class="none">No two legs from different games this week.</li>'
    h2 = hrate(pts, "k2"); w2, l2, _ = HIST[pts]["k2"]; oth = max((hrate(pts, k) or 0) for k in ("k1", "k0", "z", "tot"))
    hist_rows = "".join(f'<tr data-rate="{(hrate(pts, k) or 0):.4f}"><td><b>{KIND_TXT[k]}</b></td><td class="r">{rec_txt(pts, k)}</td><td class="r"><b>{(hrate(pts, k) or 0)*100:.1f}%</b></td></tr>'
                        for k in ("k2", "k1", "tot", "z", "k0") if (HIST[pts][k][0] + HIST[pts][k][1]))
    sections.append(f'''<section class="tz" data-tab="p{str(pts).replace(".", "")}" data-label="{pts:g}-point" data-pts="{pts:g}" data-from="{HIST_FROM}" data-h2="{(h2 or 0):.4f}" data-w2="{w2}" data-l2="{l2}" data-oth="{oth:.4f}">
 <div class="tzh"><h2>{pts:g}-point teasers</h2><label>Your book's price for two legs <input type="text" inputmode="numeric" class="px" value="{DEFAULT_PRICE[pts]}" size="5"></label></div>
 <p class="tzv">{verdict(pts, DEFAULT_PRICE[pts])}</p>
 <h3>Best pairs this week <small>different games · chance of both · points over or under the price</small></h3>
 <ul class="pairs">{pr_html}</ul>
 <h3>Legs through 3 and 7 <small>{len(k2)} this week · any two from different games make the classic teaser</small></h3>
 {('<table class="tl"><thead><tr><th>Leg</th><th class="r">Chance</th><th class="r">Crosses</th></tr></thead><tbody>' + "".join(leg_row(l) for l in k2) + '</tbody></table>') if k2 else '<p class="tznone">No leg crosses both 3 and 7 at this number this week.</p>'}
 <details class="tzmore"><summary>Every other leg <small>{len(rest)} best</small></summary>
 <table class="tl"><thead><tr><th>Leg</th><th class="r">Chance</th><th class="r">Crosses</th></tr></thead><tbody>{"".join(leg_row(l) for l in rest)}</tbody></table></details>
 <h3>How each kind of move has done <small>regular season since {HIST_FROM} at the closing line · pushes left out</small></h3>
 <table class="tl hist"><thead><tr><th>Move</th><th class="r">Record</th><th class="r">Won</th></tr></thead><tbody>{hist_rows}</tbody></table>
</section>''')
try:
    import account as ACCT; _link, _base = ACCT._base_css()
except Exception: _link, _base = "", ""
import fantasy_nav as _FN   # 11/17 (page pass): the three teaser sizes were one 6.9-screen scroll on a phone; one size per tab
body = f'''<title>Teaser finder · Week {W} · BetSweep</title>
<meta name="description" content="Six, six-and-a-half and seven-point NFL teasers scored by the BetSweep model: which teased spreads and totals clear the price, and which cross 3 and 7.">
{_link}
<style>{_base}
.tzw{{max-width:1100px;margin:16px auto 40px}} .tzw h1{{font-family:var(--brand);font-style:italic;font-weight:800;font-size:32px;line-height:1;margin:0 0 6px;letter-spacing:-.01em}} .tzw h1 small{{display:block;font-family:var(--display);font-style:normal;font-weight:700;font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--redtxt,var(--red));margin-bottom:4px}}
.tzw p.m{{color:var(--mute);line-height:1.5;margin:0 0 14px;max-width:72ch}}
.tz{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:0 0 14px}} .tzh{{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px}} .tz h2{{margin:0;font-family:var(--display);font-weight:700;font-size:22px}}
.tzh label{{font-size:13px;color:var(--mute)}} .tzh input{{font:inherit;font-size:16px;width:76px;min-height:36px;padding:4px 8px;border:1.5px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);margin-left:6px;text-align:center}}
.tz h3{{margin:14px 0 6px;font-family:var(--display);font-weight:700;font-size:16px;letter-spacing:.01em}} .tz h3 small{{font-family:var(--body);font-weight:400;color:var(--mute);font-size:12.5px;margin-left:6px}}
.pairs{{list-style:none;margin:0;padding:0;display:grid;gap:8px}} .pairs li{{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:6px 12px;align-items:center;background:var(--chalk);border-radius:10px;padding:10px 12px;position:relative}} .pairs li.none{{display:block;color:var(--mute)}}
.pairs .pl{{font-size:14.5px;line-height:1.4}} .pairs .pl i{{font-style:normal;color:var(--mute);margin:0 8px}} .pairs .pl small{{color:var(--mute)}} .pairs .pn,.pairs .pe{{text-align:right;font-variant-numeric:tabular-nums}} .pairs .pn b,.pairs .pe b{{display:block;font-family:var(--display);font-size:20px;font-weight:700}} .pairs small{{color:var(--mute);font-size:11.5px}}
.pairs .pe.up b{{color:var(--good)}} .pairs .pe.dn b{{color:var(--bad)}} .pairs .kx{{grid-column:1/-1;font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--redtxt,var(--red))}}
table.tl{{width:100%;border-collapse:collapse;font-size:14px}} .tl th,.tl td{{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}} .tl th.r,.tl td.r{{text-align:right;white-space:nowrap}} .tl thead th{{font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)}}
.tl td small{{display:block;color:var(--mute);font-size:12px}} .tl td b small{{display:inline;font-weight:400}} .tl tr.keyx td{{background:color-mix(in srgb,var(--good) 7%,transparent)}}
.tzv{{background:var(--chalk);border-left:3px solid var(--red);border-radius:0 8px 8px 0;padding:10px 12px;margin:12px 0 4px;font-size:14.5px;line-height:1.5}} .tzv.ok{{border-left-color:var(--good)}}
.tznone{{color:var(--mute);margin:0 0 6px;font-size:14px}} .tl.hist tr.ok td b{{color:var(--good)}} .tl.hist td{{vertical-align:middle}}
details.tzmore{{margin:14px 0 0;border-top:1px solid var(--line)}} details.tzmore > summary{{cursor:pointer;list-style:none;min-height:44px;display:flex;align-items:center;justify-content:space-between;font-family:var(--display);font-weight:700;font-size:16px}} details.tzmore > summary::-webkit-details-marker{{display:none}}
details.tzmore > summary small{{font-family:var(--body);font-weight:400;color:var(--mute);font-size:12.5px;margin-left:6px;margin-right:auto}} details.tzmore > summary::after{{content:"▾";color:var(--mute)}} details.tzmore[open] > summary::after{{content:"▴"}}
@media (max-width:560px){{ .pairs li{{grid-template-columns:minmax(0,1fr) auto}} .pairs .pe{{grid-column:2}} }}
{_FN.TABS_CSS}
</style>
<div class="tzw" data-week="{W}">
<h1><small>Week {W}</small>Teaser finder</h1>
<p class="m">A teaser moves every spread and total in the slip 6, 6.5 or 7 points your way and prices two legs at one number. Each leg's chance here is how that kind of move has really done in every regular-season game since {HIST_FROM}, shifted when the model's own number sits off FanDuel's line. Type your book's two-leg price and the verdict and edges update.</p>
<div id="tzTabs"></div>
{"".join(sections)}
<p class="m" style="font-size:12.5px">Pairs are from different games only. "Through 3 and 7" means the move covers both of the two most common winning margins: an underdog of +1 to +3 teased up past +7, or a favorite of -7 to -9 teased down under -3. History is every regular-season game since {HIST_FROM} at the closing line, so it is a long-run rate for that kind of move, not a read on this week's teams. Not betting advice.</p>
</div>
<script>{_FN.TABS_JS}</script>
<script>
(function(){{ var th = document.getElementById('tzTabs'), tw = document.querySelector('.tzw');
  if(th && tw && window.bsTabs){{ var ts = [].map.call(tw.querySelectorAll('.tz[data-tab]'), function(s){{ return {{id: s.getAttribute('data-tab'), label: s.getAttribute('data-label')}}; }}); if(ts.length > 1) bsTabs.mount(th, ts, {{root: tw, key: 'bs_tab_teaser'}}); }} }})();
(function(){{ function imp(o){{ o = +o; if (!o) return null; return o > 0 ? 100/(o+100) : -o/(-o+100); }}
  document.querySelectorAll('.tz').forEach(function(sec){{ var inp = sec.querySelector('.px');
    // a phone's number pad has no minus key: a bare 130 is -130 (teasers are priced minus); a typed + keeps it plus
    function px(){{ var t = String(inp.value).trim(), n = parseFloat(t.replace(/[^0-9.]/g, '')); if (!(n >= 100)) return null; return /^\+/.test(t) ? n : -n; }}
    function paint(){{ var o = imp(px()); if (o == null) return; sec.querySelectorAll('.pairs li').forEach(function(li){{ var pe = li.querySelector('.pe'); if (!pe) return; var j = +pe.getAttribute('data-joint'); var e = (j - o) * 100; pe.querySelector('b').textContent = (e >= 0 ? '+' : '') + e.toFixed(1); pe.classList.toggle('up', e >= 0); pe.classList.toggle('dn', e < 0); }}); }}
    var v = sec.querySelector('.tzv'), h2 = +sec.dataset.h2, oth = +sec.dataset.oth, w2 = (+sec.dataset.w2).toLocaleString('en-US'), l2 = (+sec.dataset.l2).toLocaleString('en-US');
    function am(o){{ o = Math.round(o); return (o > 0 ? '+' : '') + o; }}
    function say(){{ var be = imp(px()); if (be == null || !v || !h2) return; var need = Math.sqrt(be), o = px();
      var head = 'At ' + am(o) + ' each leg has to win <b>' + (need * 100).toFixed(1) + '%</b>. Since ' + sec.dataset.from + ', legs teased through 3 and 7 have won <b>' + (h2 * 100).toFixed(1) + '%</b> (' + w2 + '&ndash;' + l2 + ')';
      var j = h2 * h2, fair = j >= 0.5 ? -100 * j / (1 - j) : 100 * (1 - j) / j, safe = Math.ceil(fair / 5) * 5;
      v.innerHTML = h2 >= need ? head + ', so two of them clear this price by ' + ((j - be) * 100).toFixed(1) + ' points. No other kind of leg has won more than ' + Math.round(oth * 100) + '%.'
        : head + ' - ' + ((need - h2) * 100).toFixed(1) + ' short, and no other kind has won more than ' + Math.round(oth * 100) + '%. Nothing clears this price; two legs through 3 and 7 need about ' + am(safe) + ' or better.';
      v.classList.toggle('ok', h2 >= need);
      sec.querySelectorAll('.tl.hist tbody tr').forEach(function(tr){{ tr.classList.toggle('ok', +tr.dataset.rate >= need); }}); }}
    inp.addEventListener('input', function(){{ paint(); say(); }}); say(); }}); }})();
</script>
'''
open(os.path.join(OUT, "teasers.html"), "w").write(body)
nk = sum(1 for l in legs if l["key"] and l["pts"] == 6.0)
print(f"wrote out/teasers.html + teasers.json: {len(legs)} teased legs over {len({l['gid'] for l in legs})} games, week {W}; {nk} six-point legs cross 3 and 7; best 6-pt pair edge {pairs['6.0'][0]['edge']:+.1f} pts" if pairs.get("6.0") else f"wrote out/teasers.html: {len(legs)} legs, no pairs")
