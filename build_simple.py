#!/usr/bin/env python3
"""build_simple.py - PREVIEW of the "Simple" view (owner 11/10: casual friends "want to just open up the app and everything they could
want is right there and not have to do any extra reading"; "Build as a preview so I can look it over before publishing to the site").

One screen, almost no reading: today's house slip if there is one, three easy picks with one FanDuel button, then every game as a
single row (who wins, the score, one line, the best parlay behind one button). Nothing here is new modelling - it is the same numbers
the full site shows (out/builder_data.json, out/best_parlays.json, out/promos.json, out/voice.json), with everything else left out.

Writes out/simple.html, a self-contained page (own CSS, no site template) so it can be looked at on its own. build_site.py does NOT
place it and no page links to it: it goes on the site only when the owner says so.
"""
import json, os, html, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); sys.path.insert(0, HERE)
import sweep as SW
E = html.escape
def load(n, d):
    try: return json.load(open(os.path.join(OUT, n)))
    except Exception: return d
BD = load("builder_data.json", None)
if not BD: raise SystemExit("build_simple.py needs out/builder_data.json")
WEEK = BD.get("week"); GAMES = BD["games"]; LEGS = BD["legs"]; BP = {b["gid"]: b for b in load("best_parlays.json", [])}
VOICE = load("voice.json", {}); SAY = (VOICE.get("games") or {}) if str(VOICE.get("week")) == str(WEEK) else {}
PROMOS = load("promos.json", []); PROMOS = PROMOS if isinstance(PROMOS, list) else PROMOS.get("promos", [])
def am(o): return f"+{int(o)}" if o > 0 else str(int(o))
def dec(o): return 1 + o / 100 if o > 0 else 1 + 100 / -o
def amd(d): return f"+{round((d - 1) * 100)}" if d >= 2 else f"-{round(100 / (d - 1))}"
def fd_link(legs):
    ids = [(l["fd"]["m"], l["fd"]["s"]) for l in legs if (l.get("fd") or {}).get("m") and l["fd"].get("s")]
    if len(ids) != len(legs) or not ids: return ""
    return "https://sportsbook.fanduel.com/addToBetslip?" + "&".join(f"marketId[{i}]={m}&selectionId[{i}]={s}" for i, (m, s) in enumerate(ids))
def at(g): return f"{g['away']} {'vs' if g.get('nt') else '@'} {g['home']}" if g.get("home") and g.get("away") else f"{g['a']} - {g['b']}"
def leg_txt(l):
    if l.get("gl"): return l["pl"]
    if l["m"] == "Anytime TD": return f"{l['pl']} to score"
    return f"{l['pl']} {int(round(l['ln']))}+ {l['m'].lower()}"
# ---- three easy picks: favorites the model agrees with, no risk flags, one per player, two per game at most ----
cand = [l for l in LEGS if not l.get("gl") and not l.get("u") and l["m"] not in ("First TD", "Longest Reception", "Rushing Yards") and l.get("o") is not None and l.get("p") is not None
        and -350 <= l["o"] <= -140 and l["p"] >= (l.get("bk") or 1) - 0.02 and SW.risk_score(l, BD) < 2 and (l.get("fd") or {}).get("m")]
cand.sort(key=lambda l: -l["p"]); easy = []; seen = set(); per_g = {}
for l in cand:
    if l["pl"] in seen or per_g.get(l["g"], 0) >= 2: continue
    easy.append(l); seen.add(l["pl"]); per_g[l["g"]] = per_g.get(l["g"], 0) + 1
    if len(easy) == 3: break
ko_of = {g["gid"]: g.get("ko") or 0 for g in GAMES}
easy_html = ""
if easy:
    d = 1.0
    for l in easy: d *= dec(l["o"])
    link = fd_link(easy)
    rows = "".join(f'<li data-ko="{ko_of.get(l["g"], 0)}"><b>{E(leg_txt(l))}</b><span>{l["p"] * 100:.0f}% · {am(l["o"])}</span></li>' for l in easy)
    easy_html = (f'<section class="card" id="easy" data-ko="{min(ko_of.get(l["g"], 0) for l in easy)}"><h2>3 easy picks</h2><ul class="legs">{rows}</ul>'
                 + (f'<a class="go" href="{E(link)}" target="_blank" rel="noopener">Bet all 3 on FanDuel <small>about {amd(d)}</small></a>' if link and len(easy) == 3 else "")
                 + '<p class="fine">Favorites the model has at or within a hair of the FanDuel price, no risk flags.</p></section>')
# ---- today's house slip, when one is posted ----
sw = next((p for p in PROMOS if p.get("sweep") and str(p.get("status", "LIVE")).upper() == "LIVE" and not p.get("result")), None)
sweep_html = ""
if sw:
    rows = "".join(f'<li><b>{E(str(l.get("disp") or l.get("who") or ""))}</b></li>' for l in sw.get("legs", []))
    sweep_html = (f'<section class="card hero"><h2>Today\'s slip</h2><p class="nm">{E(str(sw.get("name") or sw.get("title") or ""))}</p><ul class="legs">{rows}</ul>'
                  + (f'<a class="go" href="{E(sw["link"])}" target="_blank" rel="noopener">Bet it on FanDuel <small>{E(am(float(sw["fd"]))) if sw.get("fd") else ""}</small></a>' if sw.get("link") else "") + '</section>')
# ---- every game on one row ----
ML = {}
for l in LEGS:
    if l["m"] == "Moneyline" and not l.get("alt"): ML.setdefault(l["g"], {})[l["tm"]] = l
BYK = {}
for l in LEGS: BYK.setdefault((l["g"], l["pl"], l["m"]), l)
days = {}
for g in sorted(GAMES, key=lambda g: g.get("sort", "")):
    a, b = g["a"], g["b"]; ml = ML.get(g["gid"], {}); pa = (ml.get(a) or {}).get("p"); pb = (ml.get(b) or {}).get("p")
    if pa is not None and pb is not None: win, wp = (a, pa) if pa >= pb else (b, pb)
    else: win, wp = (a if (g.get("pa") or 0) >= (g.get("pb") or 0) else b), None
    hi, lo = max(g.get("pa") or 0, g.get("pb") or 0), min(g.get("pa") or 0, g.get("pb") or 0)
    close = wp is not None and wp < 0.55
    pick = f'<b>{E(win)}</b> {"by a hair" if close else "to win"}' + (f' <i>{wp * 100:.0f}%</i>' if wp is not None else "") + f' <span class="sc">{hi:.0f}-{lo:.0f}</span>'
    bp = BP.get(g["gid"]); bp_html = ""
    if bp:
        legs = [BYK.get((g["gid"], x[0], x[1])) for x in bp["legs"]]; link = fd_link([l for l in legs if l]) if all(legs) else ""
        bp_html = ('<div class="bp"><small>Best parlay</small><span>' + " + ".join(E(leg_txt(l) if l else str(x[0])) for l, x in zip(legs, bp["legs"])) + '</span>'
                   + (f'<a class="go sm" href="{E(link)}" target="_blank" rel="noopener">Bet {amd(bp["dec"])}</a>' if link else f'<em>{amd(bp["dec"])}</em>') + '</div>')
    say = SAY.get(g["gid"]); day = (g.get("kick") or "").split(" ")[0]
    days.setdefault(day, []).append(
        f'<details class="gm" data-ko="{g.get("ko") or 0}"><summary><span class="mt">{E(at(g))}<small>{E(g.get("kick", ""))}</small></span><span class="pk">{pick}</span></summary>'
        + (f'<p class="say">{E(say)}</p>' if say else "") + bp_html + f'<a class="more" href="https://betsweep.co/boards/#{E(g["gid"])}">Full board</a></details>')
DAYN = {"Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday", "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday"}
games_html = "".join(f'<h3>{E(DAYN.get(d, d))}</h3>' + "".join(v) for d, v in days.items())
CSS = """
:root{--bg:#f5f0e4;--card:#efe9da;--ink:#16202b;--mute:#5d6b78;--line:#d8cfbb;--red:#d7332a;--good:#1f7a4d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:560px;margin:0 auto;padding:14px 12px 60px}
header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
header b{font-size:24px;font-style:italic;font-weight:800;letter-spacing:-.02em}header b i{color:var(--red);font-style:italic}
.tog{display:inline-flex;border:1.5px solid var(--line);border-radius:999px;overflow:hidden;font-size:13px;font-weight:700}
.tog span,.tog a{padding:6px 12px;color:var(--mute);text-decoration:none}.tog span{background:var(--ink);color:#fff}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px;margin-bottom:12px}.card.hero{border-color:var(--red)}
h2{margin:0 0 8px;font-size:13px;letter-spacing:.12em;text-transform:uppercase}h3{margin:18px 2px 6px;font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:var(--mute)}
.nm{margin:0 0 6px;font-size:20px;font-weight:800;font-style:italic}
.legs{list-style:none;margin:0 0 10px;padding:0}.legs li{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-top:1px solid var(--line);font-size:15.5px}.legs li:first-child{border-top:0}
.legs span{color:var(--mute);white-space:nowrap}
.go{display:flex;justify-content:center;align-items:center;gap:8px;min-height:48px;border-radius:12px;background:var(--red);color:#fff;font-weight:800;text-decoration:none;font-size:16px}
.go small{font-weight:600;opacity:.9}.go.sm{display:inline-flex;min-height:36px;padding:0 14px;font-size:14px;border-radius:10px}
.fine{margin:8px 0 0;color:var(--mute);font-size:12.5px}
.gm{background:var(--card);border:1px solid var(--line);border-radius:14px;margin-bottom:8px}
.gm summary{list-style:none;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:12px 14px;cursor:pointer}.gm summary::-webkit-details-marker{display:none}
.mt{font-weight:800;font-size:16px}.mt small{display:block;font-weight:500;color:var(--mute);font-size:12.5px}
.pk{text-align:right;font-size:14.5px}.pk i{font-style:normal;color:var(--good);font-weight:700}.pk .sc{display:block;color:var(--mute);font-size:12.5px}
.say{margin:0;padding:0 14px 10px;color:var(--mute);font-size:14px}
.bp{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;padding:10px 14px;border-top:1px solid var(--line);font-size:14.5px}.bp small{flex-basis:100%;font-weight:700;font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--mute)}.bp span{flex:1}.bp em{font-style:normal;font-weight:800}
.more{display:block;padding:10px 14px;border-top:1px solid var(--line);color:var(--ink);font-size:13.5px;font-weight:700;text-decoration:none}
.foot{margin-top:18px;color:var(--mute);font-size:12px;text-align:center}
"""
JS = "(function(){var n=Date.now();document.querySelectorAll('[data-ko]').forEach(function(e){var k=+e.getAttribute('data-ko');if(k&&n>=k){if(e.id==='easy'||e.tagName==='LI'){var c=e.closest('#easy');if(c)c.hidden=true;}else e.hidden=true;}});})();"
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>BetSweep - Simple view (preview)</title><style>{CSS}</style></head><body><div class="wrap">
<header><b>Bet<i>Sweep</i></b><span class="tog"><span>Simple</span><a href="https://betsweep.co/">Full</a></span></header>
{sweep_html}{easy_html}<h2 style="margin:16px 2px 0">Week {E(str(WEEK))} games <small style="font-weight:500;letter-spacing:0;text-transform:none;color:var(--mute)">tap one for its best parlay</small></h2>
{games_html}
<p class="foot">Model picks, not guarantees. 21+ | Gamble responsibly.</p></div><script>{JS}</script></body></html>"""
open(os.path.join(OUT, "simple.html"), "w").write(page)
print(f"wrote out/simple.html (PREVIEW, not placed on the site): week {WEEK}, {len(GAMES)} games, {len(easy)} easy picks, house slip {'yes' if sw else 'none posted'}")
