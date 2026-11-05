#!/usr/bin/env python3
"""build_usage.py - two pages about volume (owner 10/30, ideas 3 and 4):

/usage/     USAGE TRENDS - every RB / WR / TE whose role is moving: last 3 team games vs his earlier games this season in snap share,
            target share, carries and PPR points. Each mover carries the injury context injweeks.py already computes for the projections:
            "filled in while <teammate> was hurt - he is back" (the bump may disappear) and "played hurt in Week N" (a dip that is not a
            role loss). Data: nflverse weekly stats + snap counts + injury report (plydata.py); weeks before this week only.

/benefits/  WHO BENEFITS - every QB / RB / WR / TE with a real role who is Out or Doubtful on this week's report, and what happened to
            his teammates in the games he missed this season (snaps, targets, carries, PPR per game with him vs without him). When he has
            not missed a game yet, the page says so and shows the volume he leaves (no invented split). Each teammate's best-priced leg this
            week sits next to him (FanDuel price, model %, edge) with a link to his player page.

Nothing here changes a projection (the sheet's own vacated-volume transfer already moves the numbers); these pages show the evidence.
Prints "wrote out/usage.html: R risers, F fallers (week W)" and "wrote out/benefits.html: N players out/doubtful, M with games missed".
"""
import os, json, html, datetime as dt, collections
import plydata as PD
try:
    import injweeks as IW
except Exception:
    IW = None
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); IN = os.path.join(HERE, "in")
E = html.escape
S = PD.load(HERE); W = S.week
INJ = IW.load(IN, W) if IW else None
try: SLUG = json.load(open(os.path.join(OUT, "players", "slugs.json")))
except Exception: SLUG = {}
def plink(name):
    s = SLUG.get(name)
    return f'<a href="/player/{s}/">{E(name)}</a>' if s else E(name)
def am(o):
    try: o = float(o)
    except Exception: return "—"
    return ("+" if o > 0 else "−") + str(int(abs(round(o))))
P = lambda x: "—" if x is None else f"{100 * x:.0f}%"
N = lambda x: "—" if x is None else f"{x:.1f}"
def dpp(a, b):   # percentage-point change, signed
    if a is None or b is None: return ""
    d = 100 * (b - a); c = "up" if d >= 0.5 else ("dn" if d <= -0.5 else "")
    return f'<em class="{c}">{"+" if d >= 0 else "−"}{abs(d):.0f}</em>'
def dn(a, b):
    if a is None or b is None: return ""
    d = b - a; c = "up" if d >= 0.25 else ("dn" if d <= -0.25 else "")
    return f'<em class="{c}">{"+" if d >= 0 else "−"}{abs(d):.1f}</em>'

def best_leg(p):
    ls = [l for l in p["legs"] if not l["m"].startswith("Under") and l["m"] in ("Receiving Yards", "Receptions", "Rushing Yards", "Rush + Rec Yards", "Passing Yards", "Anytime TD") and l.get("e") is not None]
    if not ls: return ""
    nt = [x for x in ls if x["m"] != "Anytime TD"]   # a yardage / catches line says more about volume than a TD price
    l = max(nt or ls, key=lambda x: x["e"]); e = l["e"]
    lab = l["m"] if l["m"] == "Anytime TD" else f'{int(l["ln"]) if float(l["ln"]).is_integer() else l["ln"]}+ {l["ms"].lower()}'
    fd = (l.get("fd") or {}).get("u")
    price = f'<a class="fd" href="{E(fd)}" target="_blank" rel="noopener">FD {am(l["o"])}</a>' if fd else f'FD {am(l["o"])}'
    return f'<span class="leg">{E(lab)} {price} <small>model {100 * l["p"]:.0f}% · edge <b class="{"up" if e > 0 else "dn"}">{"+" if e >= 0 else ""}{100 * e:.1f}</b></small></span>'

def status(p):
    st = p.get("status")
    if st and st[0] in ("Out", "Doubtful", "Questionable"):
        return f'<span class="st {"q" if st[0] == "Questionable" else ""}">{E(st[0])}</span>'
    return ""

CSS = """
.uw{max-width:1100px;margin:16px auto 40px}
.uw h1{font-family:var(--display);font-size:30px;margin:0 0 4px;letter-spacing:.02em} .uw p.m{color:var(--mute);margin:0 0 12px;line-height:1.5;max-width:860px}
.uw a{color:var(--ink)}
.uw .ctl{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px}
.uw .ctl button{font:inherit;font-size:12.5px;font-weight:700;padding:8px 12px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.uw .ctl button.on{background:var(--red);border-color:var(--red);color:#fff} .uw .ctl .sp{width:10px}
.uw section{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:0 0 14px;overflow:hidden}
.uw h2{margin:0;padding:10px 14px;border-bottom:1px solid var(--line);font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:15px;display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline}
.uw h2 small{font-family:var(--body);font-weight:400;letter-spacing:0;text-transform:none;color:var(--mute);font-size:12.5px}
.uw .tw{overflow-x:auto}
.uw table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
.uw th,.uw td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;vertical-align:top}
.uw th:first-child,.uw td:first-child{text-align:left}
.uw thead th{font-family:var(--display);font-weight:700;letter-spacing:.06em;text-transform:uppercase;font-size:11.5px;color:var(--mute)}
.uw td small{color:var(--mute)} .uw td.nm{white-space:normal;min-width:170px} .uw td.nm b{font-weight:600}
.uw em{font-style:normal;font-size:11.5px;margin-left:5px;color:var(--mute)} .uw em.up,.uw b.up{color:var(--good)} .uw em.dn,.uw b.dn{color:var(--bad)}
.uw .tag{display:block;margin-top:3px;font-size:11.5px;line-height:1.35;white-space:normal;color:var(--warn)}
.uw .tag.ok{color:var(--mute)}
.uw .st{display:inline-block;margin-left:6px;font-size:10px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:1px 6px;border-radius:3px;background:var(--red);color:#fff;vertical-align:1px}
.uw .st.q{background:var(--warn);color:#0f141c}
.uw .leg{font-size:12px;white-space:normal} .uw .leg a.fd{display:inline-block;font-weight:700;text-decoration:none;background:#1493ff;color:#fff;border-radius:4px;padding:1px 6px;margin:0 3px}
.uw .none{padding:12px 14px;color:var(--mute);font-size:13px;margin:0;line-height:1.5}
.uw .vac{display:flex;flex-wrap:wrap;gap:6px 16px;padding:10px 14px;font-size:13px;color:var(--mute);border-bottom:1px solid var(--line)} .uw .vac b{color:var(--ink)}
.uw tr[hidden]{display:none}
.uw .pos{font-size:11px;color:var(--mute);margin-left:4px}
"""
def head(title, desc):
    link, base = __import__("account")._base_css()
    return f"<title>{E(title)}</title>\n<meta name=\"description\" content=\"{E(desc)}\">\n{link}\n<style>{base}{CSS}</style>\n"

# ---------------- usage trends ----------------
rows = []
for k, p in S.players.items():
    if p["pos"] not in ("RB", "WR", "TE") or not p["games"]: continue
    if p.get("status") and p["status"][0] in ("Out", "Doubtful"): continue   # not playing this week - he is on Who benefits instead
    tw = [w for w in S.team_weeks.get(p["team"], []) if w < W]
    if len(tw) < 4: continue
    l3 = tw[-3:]; early = tw[:-3]
    a = S.usage(k, early); b = S.usage(k, l3)
    if not a or not b or a["n"] < 2 or b["n"] < 2: continue
    if max(a["snap"] or 0, b["snap"] or 0) < 0.25 and max(a["ppr"], b["ppr"]) < 5: continue   # depth players
    dsn = ((b["snap"] or 0) - (a["snap"] or 0)) * 100
    dts = (b["ts"] - a["ts"]) * 100; dcs = (b["cs"] - a["cs"]) * 100
    score = 0.5 * dsn + dts + (0.5 * dcs if p["pos"] == "RB" else 0)
    tags = []
    if INJ:
        fil = INJ.fill(p["name"], p["team"], p["pos"])
        fw = sorted(w for w in fil if w in l3)
        if fw: tags.append(("warn", f"Filled in while {fil[fw[-1]][0]} was hurt (Week{'s' if len(fw) > 1 else ''} {', '.join(map(str, fw))}) - he is back this week, so this bump may fade."))
        lim = INJ.limited(p["name"], p["team"]); lw = sorted(w for w in lim if w in l3)
        if lw: tags.append(("warn", f"Played hurt in Week {', '.join(map(str, lw))} ({lim[lw[-1]].split(' - ')[0]}) - a dip there is the injury, not a lost role."))
    missed = [w for w in l3 if w not in {g["w"] for g in p["games"]}]
    if missed: tags.append(("ok", f"Did not play Week {', '.join(map(str, missed))}; L3 averages use the games he played."))
    rows.append({"k": k, "p": p, "a": a, "b": b, "score": score, "dsn": dsn, "tags": tags})
rows.sort(key=lambda r: -r["score"])
def trow(r, kind):
    p, a, b = r["p"], r["a"], r["b"]
    tg = "".join(f'<span class="tag {c}">{E(t)}</span>' for c, t in r["tags"])
    return (f'<tr data-pos="{p["pos"]}" data-kind="{kind}"><td class="nm"><b>{plink(p["name"])}</b><span class="pos">{p["pos"]} · {E(p["team"])}</span>{status(p)}{tg}</td>'
            f'<td>{P(b["snap"])}{dpp(a["snap"], b["snap"])}</td><td>{P(b["ts"])}{dpp(a["ts"], b["ts"])}</td><td>{N(b["tgt"])}{dn(a["tgt"], b["tgt"])}</td>'
            f'<td>{N(b["car"])}{dn(a["car"], b["car"])}</td><td>{N(b["ppr"])}{dn(a["ppr"], b["ppr"])}</td><td>{best_leg(p)}</td></tr>')
up = [r for r in rows if r["score"] >= 4][:60]; down = [r for r in reversed(rows) if r["score"] <= -4][:60]
thead = '<thead><tr><th>Player</th><th>Snaps L3</th><th>Tgt share L3</th><th>Tgt / g</th><th>Car / g</th><th>PPR / g</th><th>Best-priced leg this week</th></tr></thead>'
lastw = max((w for t in S.team_weeks.values() for w in t if w < W), default=W - 1)
usage = (head(f"NFL usage trends: snap share & target share risers and fallers · Week {W} · BetSweep",
              f"Whose role is growing or shrinking going into Week {W}: snap share, target share, carries and PPR points over each team's last 3 games vs earlier, with the injury context.")
         + f'<div class="uw"><h1>Usage trends</h1><p class="m">Whose role is moving going into Week {W}: each player\'s last 3 team games (through Week {lastw}) against his earlier games this season. '
         'The big number is the last 3 games; the small one is the change (snap and target share in percentage points). Roles that grew because a teammate was hurt - and that teammate is back - are flagged, '
         'and so are dips from playing hurt. Tap a name for his full page.</p>'
         '<div class="ctl" id="uctl"><button type="button" class="on" data-k="up">Rising</button><button type="button" data-k="down">Falling</button><span class="sp"></span>'
         + "".join(f'<button type="button" data-p="{x}"{" class=\"on\"" if x == "ALL" else ""}>{x}</button>' for x in ("ALL", "RB", "WR", "TE")) + '</div>'
         '<section><h2 id="uh">Rising roles <small>sorted by how much the role grew</small></h2><div class="tw"><table>' + thead + '<tbody>'
         + "".join(trow(r, "up") for r in up) + "".join(trow(r, "down") for r in down)
         + '</tbody></table></div><p class="none" id="uempty" hidden>Nobody in this group.</p></section>'
         '<p class="m" style="font-size:12px">Snap share from nflverse snap counts; targets, carries and PPR from the nflverse weekly stats; injury context from the weekly injury report, the same detection the projections use (an injury-shaped week is not read as a role change). '
         'The model already adjusts for snap trends; this page shows the evidence. <a href="/benefits/">Who benefits from this week\'s injuries →</a></p></div>'
         """<script>(function(){var k='up',p='ALL',rows=[].slice.call(document.querySelectorAll('.uw tbody tr')),h=document.getElementById('uh'),em=document.getElementById('uempty');
function f(){var n=0;rows.forEach(function(r){var ok=r.getAttribute('data-kind')===k&&(p==='ALL'||r.getAttribute('data-pos')===p);r.hidden=!ok;if(ok)n++;});em.hidden=n>0;
h.firstChild.nodeValue=k==='up'?'Rising roles ':'Falling roles ';h.querySelector('small').textContent=k==='up'?'sorted by how much the role grew':'sorted by how much the role shrank';}
document.querySelectorAll('#uctl button').forEach(function(b){b.addEventListener('click',function(){if(b.hasAttribute('data-k')){k=b.getAttribute('data-k');document.querySelectorAll('#uctl [data-k]').forEach(function(x){x.classList.toggle('on',x===b);});}else{p=b.getAttribute('data-p');document.querySelectorAll('#uctl [data-p]').forEach(function(x){x.classList.toggle('on',x===b);});}f();});});f();})();</script>""")
open(os.path.join(OUT, "usage.html"), "w").write(usage)
print(f"wrote out/usage.html: {len(up)} risers, {len(down)} fallers (week {W})")

# ---------------- who benefits ----------------
now_ms = dt.datetime.now(dt.timezone.utc).timestamp() * 1000
REL = {"QB": ("QB", "RB", "WR", "TE"), "RB": ("RB", "WR", "TE"), "WR": ("WR", "TE", "RB"), "TE": ("TE", "WR", "RB")}
blocks = []; n_out = 0; n_missed = 0
outs = []; longout = []
for k, p in S.players.items():
    st = p.get("status")
    if not st or st[0] not in ("Out", "Doubtful"): continue
    tw = [w for w in S.team_weeks.get(p["team"], []) if w < W]
    u = S.usage(k, tw)
    if not u: continue
    role = (u["snap"] or 0) >= 0.4 or u["ts"] >= 0.12 or u["cs"] >= 0.25 or (p["pos"] == "QB" and (sum(g["att"] for g in p["games"]) / max(1, u["n"])) >= 15)
    if not role: continue
    g = S.game_of(p["team"])
    if g and (g.get("fin") or (g.get("ko") or 0) <= now_ms): continue   # his game is over / under way
    played_w = {gg["w"] for gg in p["games"]}
    if not any(w in played_w for w in tw[-2:]):   # out for a while: the team has already adjusted - listed at the bottom, no table
        longout.append((k, p, u)); continue
    outs.append((k, p, u, tw, g))
outs.sort(key=lambda x: (-(x[2]["ppr"] or 0)))
for k, p, u, tw, g in outs:
    n_out += 1
    played = {gg["w"] for gg in p["games"] if gg["w"] < W}
    lim = INJ.limited(p["name"], p["team"]) if INJ else {}
    first = min(played) if played else W
    without = [w for w in tw if w not in played and w > first]   # weeks before his first game this season were not "missed" (signed / promoted later)
    withw = [w for w in tw if w in played and w not in lim]
    mates = [kk for kk, q in S.players.items() if q["team"] == p["team"] and kk != k and q["pos"] in REL[p["pos"]] and q["games"]]
    st = p["status"]
    opp = (g["b"] if g["a"] == p["team"] else g["a"]) if g else ""; vs = "vs" if (g and g.get("b") == p["team"]) else "@"
    head_h = (f'<h2>{plink(p["name"])} <span class="st{" q" if st[0] == "Doubtful" else ""}">{E(st[0])}</span> <small>{p["pos"]} · {E(p["team"])}'
              f'{(" " + vs + " " + E(opp) + " · " + E(g.get("kick") or "")) if g else ""}{(" · " + E(st[2])) if st[2] else ""}</small></h2>')
    vac = (f'<div class="vac"><span>He leaves per game: <b>{P(u["snap"])}</b> of snaps</span>' + (f'<span><b>{u["tgt"]:.1f}</b> targets ({P(u["ts"])} share)</span>' if p["pos"] != "QB" else "")
           + (f'<span><b>{u["car"]:.1f}</b> carries</span>' if p["pos"] in ("RB", "QB") else "") + f'<span><b>{u["ppr"]:.1f}</b> PPR pts</span></div>')
    if without and withw:
        n_missed += 1
        trs = []
        for kk in mates:
            a = S.usage(kk, withw); b = S.usage(kk, without)
            if not b: continue
            if not a: a = None
            delta = (b["tgt"] + b["car"]) - ((a["tgt"] + a["car"]) if a else 0)
            if (b["snap"] or 0) < 0.15 and (b["tgt"] + b["car"]) < 2: continue
            gained = a is None or delta > 0.25 or ((b["snap"] or 0) - (a["snap"] or 0)) > 0.03 or (b["ppr"] - a["ppr"]) > 0.5
            q = S.players[kk]
            trs.append((-delta + (0 if gained else 100), f'<tr><td class="nm"><b>{plink(q["name"])}</b><span class="pos">{q["pos"]}</span>{status(q)}</td>'
                               f'<td>{P(b["snap"])}{dpp(a["snap"] if a else None, b["snap"])}</td><td>{N(b["tgt"])}{dn(a["tgt"] if a else None, b["tgt"])}</td>'
                               f'<td>{N(b["car"])}{dn(a["car"] if a else None, b["car"])}</td><td>{N(b["ppr"])}{dn(a["ppr"] if a else None, b["ppr"])}</td><td>{best_leg(q)}</td></tr>'))
        trs.sort(key=lambda x: x[0])
        note = f'In the {len(without)} game{"s" if len(without) > 1 else ""} he missed this season (Week {", ".join(map(str, without))}) vs the {len(withw)} he played in full. Big number = without him, small = the change.'
        if len(without) == 1: note += " One game is a small sample - read it as who got the work, not a rate."
        body = (vac + f'<p class="none" style="padding-bottom:0">{E(note)}</p><div class="tw"><table><thead><tr><th>Teammate</th><th>Snaps</th><th>Targets / g</th><th>Carries / g</th><th>PPR / g</th><th>Best-priced leg this week</th></tr></thead><tbody>'
                + "".join(h for o, h in trs[:8] if o < 50 or len([1 for x in trs if x[0] < 50]) < 3) + '</tbody></table></div>')
    else:
        # no games without him: show who is next in line by current role (last 3), no invented split
        trs = []
        l3 = tw[-3:]
        for kk in mates:
            b = S.usage(kk, l3)
            if not b or ((b["snap"] or 0) < 0.1 and (b["tgt"] + b["car"]) < 1.5): continue
            q = S.players[kk]
            trs.append((-((b["snap"] or 0) + 0.02 * (b["tgt"] + b["car"])), f'<tr><td class="nm"><b>{plink(q["name"])}</b><span class="pos">{q["pos"]}</span>{status(q)}</td><td>{P(b["snap"])}</td><td>{N(b["tgt"])}</td><td>{N(b["car"])}</td><td>{N(b["ppr"])}</td><td>{best_leg(q)}</td></tr>'))
        trs.sort(key=lambda x: x[0])
        body = (vac + '<p class="none" style="padding-bottom:0">He has not missed a game this season, so there is no "without him" split yet. These are his teammates\' roles over the last 3 games - the volume he leaves goes to some of them; the model\'s projections already move it by role.</p>'
                '<div class="tw"><table><thead><tr><th>Teammate</th><th>Snaps L3</th><th>Targets / g</th><th>Carries / g</th><th>PPR / g</th><th>Best-priced leg this week</th></tr></thead><tbody>' + "".join(h for _, h in trs[:8]) + '</tbody></table></div>')
    blocks.append(f'<section>{head_h}{body}</section>')
bene = (head(f"Who benefits from NFL injuries · Week {W} · BetSweep",
             f"Week {W}: every starter who is Out or Doubtful, and who got his snaps, targets and carries in the games he missed - with each teammate's best-priced prop.")
        + f'<div class="uw"><h1>Who benefits</h1><p class="m">Every player with a real role who is <b>Out</b> or <b>Doubtful</b> on this week\'s injury report, and where his work went in the games he already missed this season. '
        'Books often move the injured player\'s lines first and the backup\'s last - the best-priced leg for each teammate is next to his name. Updated every rebuild (Thursday, Saturday, Sunday morning); inactives are final about 90 minutes before kickoff.</p>'
        + "".join(blocks) + (('<section><h2>Out for a while <small>no game in his team\'s last two - the offense has already adjusted, so his split is in the usage trends</small></h2><div class="vac">'
           + "".join(f'<span>{plink(p["name"])} <small>{p["pos"]} · {E(p["team"])} · {E(p["status"][0])}</small></span>' for k, p, u in sorted(longout, key=lambda x: -(x[2]["ppr"] or 0))) + '</div></section>') if longout else "")
        + ("" if blocks else f'<section><p class="none">Nobody with a real role was newly ruled Out or Doubtful for the games still to play in Week {W}.</p></section>')
        + '<p class="m" style="font-size:12px">With / without splits use this season\'s games only; weeks he left hurt are left out of both sides. Status from the nflverse weekly injury report. <a href="/usage/">Usage trends →</a></p></div>')
open(os.path.join(OUT, "benefits.html"), "w").write(bene)
print(f"wrote out/benefits.html: {n_out} players newly out/doubtful ({n_missed} with games missed), {len(longout)} out for a while (week {W})")
