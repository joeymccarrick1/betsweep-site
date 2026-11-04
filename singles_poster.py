#!/usr/bin/env python3
"""singles_poster.py - the daily singles post (owner 11/4: "singles post generator").

usage: python3 singles_poster.py <legs.json> <out_prefix> [--record "12-18 · +4.2u"] [--title "Thursday singles"] [--week 9]
  legs.json = [{"pl": "Josh Cameron", "m": "Receptions", "ln": 4, "o": 180, "p": 0.45, "bk": 0.36, "why": "one line"}, ...]  (3-5 legs; "u": 1 for an under)
Writes <out_prefix>-square.png (1080x1080), <out_prefix>-story.png (1080x1920) and <out_prefix>.txt (the X / Instagram caption).
Design: BetSweep chalkboard (dark navy, cream type, red swoosh), one row per leg with the line, FanDuel price, model % vs implied %, and the
running singles record under the title. The owner lays his own art over it in ChatGPT; this is the data layer.
"""
import json, os, sys, asyncio, html
HERE = os.path.dirname(os.path.abspath(__file__))
def arg(flag, default=None):
    if flag in sys.argv: i = sys.argv.index(flag); return sys.argv[i + 1] if i + 1 < len(sys.argv) else default
    return default
legs = json.load(open(sys.argv[1])); outp = sys.argv[2]; record = arg("--record", ""); title = arg("--title", "Today's singles"); week = arg("--week", "")
def am(o): o = int(round(float(o))); return f"+{o}" if o > 0 else str(o)
def pc(p): return f"{round(float(p) * 100)}%"
def short(m): return {"Receiving Yards": "rec yds", "Rushing Yards": "rush yds", "Passing Yards": "pass yds", "Receptions": "catches", "Longest Reception": "long rec", "Anytime TD": "anytime TD", "First TD": "first TD"}.get(m, m)
def leg_txt(l): return l["pl"] + (" " + ("under " if l.get("u") else "") + (f"{int(round(l['ln']))}+ " if l["m"] not in ("Anytime TD", "First TD") else "") + short(l["m"]))
try: LOGO = open(os.path.join(HERE, "wordmark_b64.txt")).read().strip()
except Exception: LOGO = ""
E = html.escape
rows = "".join(f'<div class="leg"><div class="n"><b>{E(leg_txt(l))}</b><small>{E(l.get("why", ""))}</small></div><div class="px"><b>{am(l["o"])}</b><small>FanDuel</small></div><div class="pm"><b>{pc(l["p"])}</b><small>model · book {pc(l["bk"])}</small></div></div>' for l in legs)
page = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
body{{margin:0;background:#0f141c;color:#efe9da;font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}} .d{{font-family:"Arial Narrow","Helvetica Neue",Arial,sans-serif;font-weight:800}}
.sq{{width:1080px;height:1080px;position:relative;overflow:hidden;background:#0f141c radial-gradient(1200px 600px at 20% -10%,#1d2633,transparent)}}
.st{{width:1080px;height:1920px}}
.in{{position:absolute;inset:0;padding:60px 64px;display:flex;flex-direction:column}}
.hd{{display:flex;align-items:center;justify-content:space-between}} .hd img{{height:60px}} .hd .wk{{font-weight:800;font-size:26px;letter-spacing:.12em;text-transform:uppercase;color:#9aa3b2}}
h1{{font-style:italic;font-weight:900;font-size:62px;line-height:1;margin:30px 0 6px;letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}} h1 i{{font-style:italic;color:#d7332a}} .sub{{font-weight:800;font-size:28px;color:#d7332a;letter-spacing:.02em;margin-top:2px}} .swoosh{{height:10px;width:46%;border-radius:5px;background:linear-gradient(90deg,#d7332a,#d7332a 80%,transparent);margin:6px 0 14px}}
.rec{{font-weight:800;font-size:24px;letter-spacing:.08em;text-transform:uppercase;color:#9aa3b2;margin-bottom:22px}} .rec b{{color:#5fcf93;margin-left:8px}}
.leg{{display:grid;grid-template-columns:minmax(0,1fr) 150px 230px;align-items:center;gap:16px;padding:16px 22px;background:#161d28;border:1px solid #2b3442;border-radius:16px;margin-bottom:12px;min-height:108px}}
.leg .n b{{display:block;font-weight:900;font-size:33px;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}} .leg .n small{{display:block;margin-top:5px;font-size:18px;color:#9aa3b2;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.leg .px,.leg .pm{{text-align:right}} .leg .px b{{display:block;font-weight:900;font-size:42px;color:#efe9da;line-height:1}} .leg .pm b{{display:block;font-weight:900;font-size:42px;color:#5fcf93;line-height:1}} .leg .px small,.leg .pm small{{display:block;font-size:14px;color:#9aa3b2;letter-spacing:.06em;text-transform:uppercase;margin-top:4px}}
.ft{{margin-top:auto;padding-top:12px;display:flex;align-items:center;justify-content:space-between;font-weight:800;font-size:22px;letter-spacing:.1em;text-transform:uppercase;color:#9aa3b2}} .ft b{{color:#d7332a}}

.st .in{{padding:140px 72px}} .st h1{{font-size:70px;white-space:normal}} .st .leg{{padding:26px 24px;min-height:150px;margin-bottom:18px}} .st .leg .n b{{font-size:40px;white-space:normal}} .st .leg .n small{{white-space:normal}} .st .ft{{font-size:26px}}
</style></head><body>
<div class="sq" id="sq"><div class="in"><div class="hd">{('<img src="data:image/png;base64,' + LOGO + '">') if LOGO else '<b style="font-family:Barlow;font-style:italic;font-weight:800;font-size:44px">BetSweep</b>'}<span class="wk">{E(('Week ' + str(week)) if week else '')}</span></div>
<h1>{E(title)}</h1><div class="sub">Plus-money edges · model vs FanDuel</div><div class="swoosh"></div><div class="rec">Singles record{('<b>' + E(record) + '</b>') if record else '<b>new this week</b>'}</div>{rows}
<div class="ft"><span>Model % vs FanDuel's implied %</span><span>betsweep.co <b>/how</b></span></div></div></div>
<div class="sq st" id="st"><div class="in"><div class="hd">{('<img src="data:image/png;base64,' + LOGO + '">') if LOGO else '<b style="font-family:Barlow;font-style:italic;font-weight:800;font-size:44px">BetSweep</b>'}<span class="wk">{E(('Week ' + str(week)) if week else '')}</span></div>
<h1>{E(title)}</h1><div class="sub">Plus-money edges · model vs FanDuel</div><div class="swoosh"></div><div class="rec">Singles record{('<b>' + E(record) + '</b>') if record else '<b>new this week</b>'}</div>{rows}
<div class="ft"><span>Model % vs FanDuel's implied %</span><span>betsweep.co <b>/how</b></span></div></div></div>
</body></html>"""
tmp = outp + ".html"; open(tmp, "w").write(page)
async def shoot():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page(viewport={"width": 1080, "height": 3000}, device_scale_factor=1)
        await pg.goto("file://" + os.path.abspath(tmp)); await pg.wait_for_timeout(900)
        await (await pg.query_selector("#sq")).screenshot(path=outp + "-square.png"); await (await pg.query_selector("#st")).screenshot(path=outp + "-story.png"); await b.close()
asyncio.run(shoot()); os.remove(tmp)
cap = f"{title} - plus-money edges, model vs the price:\n" + "\n".join(f"- {leg_txt(l)} ({am(l['o'])}) · model {pc(l['p'])} vs {pc(l['bk'])}" for l in legs) + (f"\nSingles record: {record}" if record else "") + "\nEvery pick graded Tuesday at the posted price: betsweep.co/how\n21+. Problem gambling help: 1-800-GAMBLER."
open(outp + ".txt", "w").write(cap)
print(f"wrote {outp}-square.png, {outp}-story.png, {outp}.txt ({len(legs)} legs)")
