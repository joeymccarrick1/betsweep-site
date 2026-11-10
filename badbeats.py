#!/usr/bin/env python3
"""badbeats.py <GRADED WEEK> - 'Missed by one' (owner 11/10): the week's most painful FanDuel misses, for a weekly bad-beats post.

A bad beat = a graded FanDuel over that MISSED by a hair: receptions one short, rushing / receiving yards 1-3 short, passing yards 1-6 short,
and FanDuel had it at 55%+ implied (a leg people actually played). Ranked by how close it came (share of the line it reached), then by price.
Also lists BetSweep promos from 'PROMO - Promoted Bets' that lost by exactly one leg.
Reads in/legsnaps.json (graded, Latest Snapshot) and in/promos.json when present. Writes out/badbeats.html (placed at /badbeats/ by
build_site.py) and out/badbeats.json. Nothing here is a pick; it is content.
"""
import json, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
W = str(int(sys.argv[1]))
E = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
TOL = {"Receiving Yards": 3, "Rushing Yards": 3, "Passing Yards": 6, "Receptions": 1}
UNIT = {"Receiving Yards": "rec yds", "Rushing Yards": "rush yds", "Passing Yards": "pass yds", "Receptions": "catches"}
v = json.load(open(os.path.join(IN, "legsnaps.json")))["values"]; H = {c: i for i, c in enumerate(v[0])}
beats = []
for r in v[1:]:
    r = r + [""] * (len(v[0]) - len(r))
    if r[0] != W or str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] != "MISS": continue
    m = r[H["Market"]]
    if m not in TOL: continue
    try: ln = float(r[H["Line (X+)"]]); ac = float(r[H["Actual"]]); bk = float(r[H["Book implied %"]])
    except Exception: continue
    bk = bk / 100 if bk > 1 else bk; short = ln - ac
    if short <= 0 or short > TOL[m] or bk < 0.55: continue
    beats.append({"pl": r[H["Player"]], "tm": r[H["Team"]], "opp": r[H["Opp"]], "m": m, "ln": ln, "ac": ac, "short": short, "o": r[H["FanDuel odds"]], "bk": round(bk, 3), "reach": ac / ln if ln else 0})
beats.sort(key=lambda b: (-b["reach"], -b["bk"]))
top = beats[:10]
promos = []
try:
    pv = json.load(open(os.path.join(IN, "promos.json")))["values"]; PH = {c: i for i, c in enumerate(pv[0])}
    for r in pv[1:]:
        r = r + [""] * (len(pv[0]) - len(r))
        if r[0] != W: continue
        note = r[PH.get("Notes", 12)] if len(r) > 12 else ""
        mm = re.search(r"(\d+)/(\d+) legs hit", note or "")
        if mm and int(mm.group(2)) >= 2 and int(mm.group(2)) - int(mm.group(1)) == 1: promos.append({"title": r[PH.get("Title", 2)], "odds": r[PH.get("FanDuel odds", 4)], "note": note})
except Exception as e: print("note: promos not read:", e)
json.dump({"week": int(W), "beats": top, "promos": promos, "n": len(beats)}, open(os.path.join(OUT, "badbeats.json"), "w"))
def odds(o):
    try: o = int(float(o)); return f"+{o}" if o > 0 else str(o)
    except Exception: return str(o)
def line(b):
    return f'{b["pl"]} {int(b["ln"])}+ {UNIT[b["m"]]}'
rows = "".join(f'<li><b>{E(line(b))}</b><span class="o">{E(odds(b["o"]))}</span><small>{E(b["tm"])} vs {E(b["opp"])} · finished with <b>{b["ac"]:g}</b> - {b["short"]:g} short · FanDuel had it at {round(b["bk"]*100)}%</small></li>' for b in top)
prow = "".join(f'<li><b>{E(p["title"])}</b><span class="o">+{E(p["odds"])}</span><small>{E(p["note"])}</small></li>' for p in promos)
share = "Missed by one, Week " + W + ":\n" + "\n".join(f"{line(b)} ({odds(b['o'])}) - finished with {b['ac']:g}" for b in top[:5]) + "\nbetsweep.co/badbeats/"
html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Missed by one - Week {W} bad beats - BetSweep</title>
<meta name="description" content="The week's most painful FanDuel misses: favorites that came up one catch or a few yards short.">
<style>.bb{{max-width:760px;margin:16px auto 40px;padding:0 16px}} .bb h1{{font-family:var(--brand);font-style:italic;font-weight:800;font-size:32px;margin:0 0 6px}}
.bb p.m{{color:var(--mute);line-height:1.5;margin:0 0 14px}} .bb h2{{font-family:var(--display);font-weight:700;font-size:20px;margin:22px 0 8px}}
.bbl{{list-style:none;margin:0;padding:0;display:grid;gap:8px}} .bbl li{{display:grid;grid-template-columns:1fr auto;gap:2px 10px;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--red);border-radius:10px;padding:10px 12px}}
.bbl li small{{grid-column:1/-1;color:var(--mute);font-size:13px}} .bbl .o{{font-family:var(--display);font-weight:700}}
.bbsh{{font:inherit;font-weight:700;font-size:14px;padding:10px 16px;border-radius:10px;border:0;background:var(--red);color:#fff;cursor:pointer;margin:6px 0 14px}}</style></head><body>
<div class="bb"><h1>Missed by one</h1><p class="m">Week {W}'s most painful FanDuel misses: favorites priced 55% or better that came up one catch or a few yards short. {len(beats)} legs this week missed by that little.</p>
<button type="button" class="bbsh" data-t="{E(share)}">Share this list</button>
<ul class="bbl">{rows or '<li>No bad beats graded yet.</li>'}</ul>
{('<h2>Our promos that lost by one leg</h2><ul class="bbl">' + prow + '</ul>') if promos else ''}
<p class="m" style="margin-top:18px">Graded from the final box scores against FanDuel's price when we froze the leg. A bad beat is not a bad bet - and sometimes it is.</p></div>
<script>document.addEventListener('click',function(e){{var b=e.target.closest&&e.target.closest('.bbsh');if(!b)return;var t=b.getAttribute('data-t');if(navigator.share)navigator.share({{text:t}}).catch(function(){{}});else if(navigator.clipboard)navigator.clipboard.writeText(t).then(function(){{b.textContent='Copied';}});}});</script>
</body></html>"""
open(os.path.join(OUT, "badbeats.html"), "w").write(html)
print(f"wrote out/badbeats.html: week {W}, {len(beats)} near misses ({len(top)} shown), {len(promos)} promos lost by one leg")
