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
import json, os, math, datetime as dt
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

D = json.load(open(os.path.join(OUT, "builder_data.json"))); W = D["week"]
fdgl = GL.load_fd(IN); sched = GL.load_sched(IN, W)
now = dt.datetime.now(dt.timezone.utc).timestamp() * 1000
games = D.get("games", [])
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
                p = PHI((mu + teased) / SDM)
                legs.append({"gid": g["gid"], "kind": "spread", "side": side, "nick": GL.NICK.get(side, side), "line": line, "teased": teased, "pts": pts, "p": round(p, 4),
                             "p0": round(PHI((mu + line) / SDM), 4), "key": crosses(line, teased), "ko": g.get("ko"), "kick": g.get("kick", ""), "a": a, "b": b, "ml": None})
        if tl is not None:
            for side, sgn in (("OVER", 1), ("UNDER", -1)):
                teased = tl - pts if side == "OVER" else tl + pts
                p = PHI((t_centre - teased) / SDT) if side == "OVER" else PHI((teased - t_centre) / SDT)
                p0 = PHI((t_centre - tl) / SDT) if side == "OVER" else PHI((tl - t_centre) / SDT)
                legs.append({"gid": g["gid"], "kind": "total", "side": side, "nick": side.title(), "line": tl, "teased": teased, "pts": pts, "p": round(p, 4), "p0": round(p0, 4),
                             "key": False, "ko": g.get("ko"), "kick": g.get("kick", ""), "a": a, "b": b, "ml": None})
# best pairs per points: top legs by chance, different games; joint = product; EV at the default price
pairs = {}
for pts in POINTS:
    cand = sorted([l for l in legs if l["pts"] == pts and l["p"] >= 0.70], key=lambda l: -l["p"])[:24]
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
json.dump({"week": W, "built": dt.datetime.now(dt.timezone.utc).isoformat(), "sd": {"margin": SDM, "total": SDT, "shrink": SHRINK}, "prices": {str(k): v for k, v in DEFAULT_PRICE.items()}, "legs": legs, "pairs": pairs}, open(os.path.join(OUT, "teasers.json"), "w"))

def leg_txt(l):
    if l["kind"] == "spread": return f"{l['nick']} {l['teased']:+g} <small>(from {l['line']:+g})</small>"
    return f"{l['nick']} {l['teased']:g} <small>(from {l['line']:g})</small>"
def leg_row(l):
    return (f'<tr class="{"keyx" if l["key"] else ""}"><td><b>{leg_txt(l)}</b><small class="g">{E(l["a"])} @ {E(l["b"])} · {E(l["kick"])}</small></td>'
            f'<td class="r"><b>{l["p"]*100:.0f}%</b><small>was {l["p0"]*100:.0f}%</small></td><td class="r">{"3 &amp; 7" if l["key"] else ""}</td></tr>')
sections = []
for pts in POINTS:
    ls = sorted([l for l in legs if l["pts"] == pts], key=lambda l: -l["p"])[:16]
    ps = pairs[str(pts)][:8]
    def pair_li(p): return (f'<li><div class="pl">{leg_txt(p["legs"][0])}<i>+</i>{leg_txt(p["legs"][1])}</div><div class="pn"><b>{p["joint"]*100:.0f}%</b><small>to cash</small></div>'
                      f'<div class="pe {"up" if p["edge"] >= 0 else "dn"}" data-joint="{p["joint"]}"><b>{p["edge"]:+.1f}</b><small>vs the price</small></div>{"<span class=\"kx\">crosses 3 &amp; 7</span>" if p["keys"] else ""}</li>')
    kl_html = "".join(pair_li(p) for p in pairs[str(pts) + "k"][:6]) or '<li class="none">No two legs cross both 3 and 7 this week at this number.</li>'
    pr_html = "".join(f'<li><div class="pl">{leg_txt(p["legs"][0])}<i>+</i>{leg_txt(p["legs"][1])}</div><div class="pn"><b>{p["joint"]*100:.0f}%</b><small>to cash</small></div>'
                      f'<div class="pe {"up" if p["edge"] >= 0 else "dn"}" data-joint="{p["joint"]}"><b>{p["edge"]:+.1f}</b><small>vs the price</small></div>{"<span class=\"kx\">crosses 3 &amp; 7</span>" if p["keys"] else ""}</li>' for p in ps) or '<li class="none">No pair clears the price at this number.</li>'
    sections.append(f'''<section class="tz" data-pts="{pts:g}">
 <div class="tzh"><h2>{pts:g}-point teasers</h2><label>Your book's price for two legs <input type="text" inputmode="numeric" class="px" value="{DEFAULT_PRICE[pts]}" size="5"></label></div>
 <h3>Classic pairs <small>both legs cross 3 and 7 · the smooth curve under-counts games landing on 3 or 7, so these run a touch better than shown</small></h3>
 <ul class="pairs">{kl_html}</ul>
 <h3>Model's best pairs <small>different games · chance of both · edge vs the price in points</small></h3>
 <ul class="pairs">{pr_html}</ul>
 <h3>Every teased leg <small>model chance after the move · "was" = the plain line</small></h3>
 <table class="tl"><thead><tr><th>Leg</th><th class="r">Chance</th><th class="r">Crosses</th></tr></thead><tbody>{"".join(leg_row(l) for l in ls)}</tbody></table>
</section>''')
try:
    import account as ACCT; _link, _base = ACCT._base_css()
except Exception: _link, _base = "", ""
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
@media (max-width:560px){{ .pairs li{{grid-template-columns:minmax(0,1fr) auto}} .pairs .pe{{grid-column:2}} }}
</style>
<div class="tzw" data-week="{W}">
<h1><small>Week {W}</small>Teaser finder</h1>
<p class="m">A teaser moves every spread and total in the slip 6, 6.5 or 7 points your way and prices two legs at one number. The chance of each teased leg comes from the same model the boards use (final margin spread 12.6 points, totals 12.9, centred halfway between the model and FanDuel's line). Legs that cross both 3 and 7 are the ones the sharp money has teased for decades. Type your book's two-leg price and the edges update.</p>
{"".join(sections)}
<p class="m" style="font-size:12.5px">Pairs are from different games only. Teased totals rarely carry a real edge - the historically proven play is the spread that crosses 3 and 7, so start from the classic list. A smooth curve under-counts games that land exactly on 3 or 7, so the classic legs are likely a touch better than the model shows. The model's game lines have not been back-tested as long as its player props, so treat these as a screen, not a lock. Not betting advice.</p>
</div>
<script>
(function(){{ function imp(o){{ o = +o; if (!o) return null; return o > 0 ? 100/(o+100) : -o/(-o+100); }}
  document.querySelectorAll('.tz').forEach(function(sec){{ var inp = sec.querySelector('.px');
    function paint(){{ var o = imp(inp.value); if (o == null) return; sec.querySelectorAll('.pairs li').forEach(function(li){{ var pe = li.querySelector('.pe'); if (!pe) return; var j = +pe.getAttribute('data-joint'); var e = (j - o) * 100; pe.querySelector('b').textContent = (e >= 0 ? '+' : '') + e.toFixed(1); pe.classList.toggle('up', e >= 0); pe.classList.toggle('dn', e < 0); }}); }}
    inp.addEventListener('input', paint); }}); }})();
</script>
'''
open(os.path.join(OUT, "teasers.html"), "w").write(body)
nk = sum(1 for l in legs if l["key"] and l["pts"] == 6.0)
print(f"wrote out/teasers.html + teasers.json: {len(legs)} teased legs over {len({l['gid'] for l in legs})} games, week {W}; {nk} six-point legs cross 3 and 7; best 6-pt pair edge {pairs['6.0'][0]['edge']:+.1f} pts" if pairs.get("6.0") else f"wrote out/teasers.html: {len(legs)} legs, no pairs")
