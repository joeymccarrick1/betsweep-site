#!/usr/bin/env python3
"""build_live.py - the Live page: during games, every model-liked leg that has not happened yet, with the live box score and the
model's chance from here.

Inputs: out/builder_data.json (written by build_builder.py: every priced leg + games), out/best_parlays.json (build_boards.py),
template assets. Output: out/live.html. The page itself polls ESPN's public scoreboard and game summaries (box scores) in the
browser every 30 seconds while a game is in progress; nothing here is fetched at build time.

Live chance from here (client side, per leg):
  yards / receptions  X_final = current + remaining, remaining ~ N(mu*f, sigma*sqrt(f)), f = fraction of regulation left; mu is the
                      pregame projection, sigma backed out of the pregame chance at that line (so it matches the site's pregame number)
  longest reception   P(a longer catch is still coming) = 1 - (1 - p_pregame)^f once the current long is below the line
  anytime TD          lambda = -ln(1 - p_pregame); P = 1 - exp(-lambda*f) until he scores
  first TD            settled by the first touchdown of the game (ESPN scoring plays); pregame chance until then
  game lines          remaining margin ~ N(mu_m*f, 12.6*sqrt(f)), remaining total ~ N(mu_t*f, 12.9*sqrt(f)), mu backed out of the
                      chances the site showed pregame, so they agree at kickoff
These are the same shapes the pregame model uses, pushed forward in time; they do not know about injuries during the game, garbage
time or pace, so treat them as a guide to what is still open, then price it against FanDuel's live number yourself.
"""
import json, os, re, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out")
exec(open(os.path.join(HERE, "brand.py")).read())
import live as LIVE
D = json.load(open(os.path.join(OUT, "builder_data.json")))
WEEK = D["week"]
try: BP = {b["gid"]: b for b in json.load(open(os.path.join(OUT, "best_parlays.json")))}
except Exception: BP = {}
# legs the page tracks: one per player-market (the best edge, clean preferred), every anytime TD and first TD, the six main game lines; no alternates
keep = []; seen = {}
for l in sorted(D["legs"], key=lambda l: -(l["e"] + (0.5 if not l["w"] else 0))):
    if l.get("alt"): continue
    if l.get("gl"): keep.append(l); continue
    k = (l["pl"], l["m"])
    if k in seen: continue
    seen[k] = 1; keep.append(l)
bp_keys = {(p, m, int(ln) if m not in ("Spread", "Total") else ln) for b in BP.values() for (p, m, ln, o, pr, e) in b["legs"]}
for l in keep: l["bp"] = (l["pl"], l["m"], int(l["ln"]) if l["m"] not in ("Spread", "Total") else l["ln"]) in bp_keys
FIELDS = ("i", "pl", "pos", "tm", "opp", "g", "m", "ms", "ln", "o", "p", "bk", "e", "w", "proj", "c", "gl", "src", "bp", "alt")
def _slim(l):
    o = {k: l[k] for k in FIELDS if k in l}
    if l.get("fd") and l["fd"].get("m"): o["fd"] = {"m": l["fd"]["m"], "s": l["fd"]["s"]}   # FanDuel market/selection ids: "Open in FanDuel" on a slip
    return o
slim = [_slim(l) for l in keep]
keep_ids = {l["i"] for l in keep}
extra = [_slim(l) for l in D["legs"] if l["i"] not in keep_ids]   # everything else, so a slip leg of any kind can be tracked
games = [{k: g[k] for k in ("gid", "a", "b", "pa", "pb", "tot", "probs", "most", "na", "nb", "ca", "cb", "kick", "ko", "fin", "sort")} for g in D["games"]]
# owner 11/1: FanDuel stops pricing a leg at kickoff, so a rebuild during the games drops it from the builder data and a saved slip (or a promo)
# with that leg could no longer be tracked here. Add the latest pre-kickoff frozen copy of every leg this week ('V2 - FanDuel Leg Snapshots',
# in/legsnaps.json) that the builder no longer carries, so every slip leg keeps its live line, status and model chance.
try:
    _have = {(l["pl"], l["m"], round(float(l.get("ln") or 1))) for l in D["legs"]}; _gids = {g["gid"] for g in D["games"]}; _add = 0
    _v = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "in", "legsnaps.json")))["values"]; _h = {c: i for i, c in enumerate(_v[0])}
    for _r in _v[1:]:
        _r = list(_r) + [""] * (len(_v[0]) - len(_r))
        if str(_r[_h["Latest Snapshot"]]).upper() != "TRUE" or str(_r[_h["Week"]]).split(".")[0] != str(WEEK): continue
        try: _ln = float(_r[_h["Line (X+)"]]); _o = int(float(str(_r[_h["FanDuel odds"]]).replace("+", ""))); _p = float(_r[_h["Model % (hist-adj)"]])
        except Exception: continue
        _pl, _m, _tm, _op = _r[_h["Player"]], _r[_h["Market"]], _r[_h["Team"]], _r[_h["Opp"]]
        _g = "-".join(sorted([_tm, _op]))
        if _g not in _gids or (_pl, _m, round(_ln)) in _have: continue
        _have.add((_pl, _m, round(_ln)))
        try: _bk = float(_r[_h["Book implied %"]])
        except Exception: _bk = None
        extra.append({"pl": _pl, "m": _m, "ln": _ln, "o": _o, "p": _p, "bk": _bk, "tm": _tm, "opp": _op, "g": _g, "snap": 1}); _add += 1
    print(f"live page: {_add} legs restored from the pre-kickoff snapshots (no longer priced by FanDuel)")
except Exception as _e:
    print("note: no leg snapshots for the live page:", _e)
LD = {"week": WEEK, "games": games, "legs": slim, "extra": extra, "built": D["built"]}
print(f"live page: {len(slim)} tracked legs across {len(games)} games")

CSS = r"""
.lv{max-width:1100px;margin:0 auto}
.lvbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 14px;margin-bottom:12px;background:var(--card);border:1px solid var(--line);border-radius:10px;font-size:12.5px;color:var(--mute)}
.lvbar b{color:var(--ink)} .lvbar .seg{margin-left:auto}
.lvbar .seg button.on{background:var(--red);color:#fff}
.lvbar .upd{font-variant-numeric:tabular-nums}
.lg2{background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:14px;overflow:hidden}
.lg2.live{border-color:var(--red)} .lg2.pre{opacity:.85}
.lg2 .ghd2{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);grid-template-areas:"a m b" "s s s";align-items:center;gap:6px 10px;padding:12px 14px;background:var(--chalk);border:0;border-bottom:1px solid var(--line);width:100%;text-align:left;font:inherit;color:inherit;cursor:pointer}
.lg2 .ghd2 > .t:first-child{grid-area:a} .lg2 .ghd2 > .mid{grid-area:m} .lg2 .ghd2 > .t.r{grid-area:b}
.lg2 .ghd2 .tog{grid-area:s;display:flex;align-items:center;justify-content:space-between;margin-top:4px;padding-top:6px;border-top:1px dashed var(--line);font-size:12px;color:var(--mute)}
.lg2 .ghd2 .tog .car{font-style:normal;font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--red);border:1.5px solid var(--red);border-radius:99px;padding:3px 10px}
.lg2 .ghd2 .tog .car::before{content:"Show "} .lg2.open .ghd2 .tog .car::before{content:"Hide "}
.logcard .ghd2 .t{color:var(--red)} .logbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:8px 14px;border-bottom:1px solid var(--line);font-size:12px;color:var(--mute)} .logcard td.st{font-size:14px;font-weight:700} .logcard tr.hit td.st{color:var(--good)} .logcard tr.dead td.st{color:var(--bad)}
.lg2:not(.open) .ghd2{border-bottom:0} @media (hover:hover) and (pointer:fine){ .lg2 .ghd2:hover .tog .car{background:var(--red);color:#fff} } .lg2.open .ghd2 .tog .car{background:var(--red);color:#fff}
.lg2 .ghd2:focus{outline:none} .lg2 .ghd2:focus-visible{outline:2px solid var(--red);outline-offset:-2px}
.lg2 .ghd2 .t{display:flex;align-items:center;gap:8px;font-family:var(--display);font-weight:800;font-size:22px} .lg2 .ghd2 .t.r{justify-content:flex-end} .lg2 .ghd2 .t small{font-family:var(--body);font-weight:500;font-size:12px;color:var(--mute)}
.lg2 .ghd2 .mid{text-align:center;font-family:var(--display)} .lg2 .ghd2 .mid b{display:block;font-size:30px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1} .lg2 .ghd2 .mid b i{font-style:normal;color:var(--red);margin:0 8px}
.lg2 .ghd2 .mid small{display:block;font-family:var(--body);font-size:11.5px;color:var(--mute);margin-top:3px} .lg2 .ghd2 .mid .lvtag{color:var(--red);font-weight:800;letter-spacing:.1em;text-transform:uppercase;font-size:11px}
.lg2 .sit{padding:6px 14px;font-size:12px;color:var(--mute);border-bottom:1px solid var(--line);background:var(--card)} .lg2 .sit b{color:var(--ink)}
.lg2 h4{margin:0;padding:8px 14px 4px;font-family:var(--display);font-weight:700;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--mute)}
.lg2 h4.hot{color:var(--red)}
table.lvt{width:100%;border-collapse:collapse;font-size:13px} table.lvt td{padding:7px 14px;border-top:1px solid var(--line);vertical-align:middle}
table.lvt td.who b{display:block;font-weight:600} table.lvt td.who small{color:var(--mute);font-size:11.5px}
table.lvt td.now{white-space:nowrap;font-variant-numeric:tabular-nums} table.lvt td.now b{font-size:15px} table.lvt td.now small{display:block;color:var(--mute);font-size:11px}
table.lvt td.pr{text-align:right;white-space:nowrap} table.lvt td.pr b{font-family:var(--display);font-size:20px;font-weight:800} table.lvt td.pr small{display:block;color:var(--mute);font-size:11px}
table.lvt td.pr b.up{color:var(--good)} table.lvt td.pr b.dn{color:var(--bad)}
table.lvt tr.hit td{background:color-mix(in srgb,var(--good) 10%,var(--card))} table.lvt tr.dead td{opacity:.5}
table.lvt .chip{display:inline-block;font-family:var(--display);font-weight:700;font-size:10px;letter-spacing:.1em;text-transform:uppercase;padding:2px 7px;border-radius:99px;border:1px solid var(--line);color:var(--mute);margin-left:6px;vertical-align:1px}
table.lvt .chip.hit{background:var(--good);border-color:var(--good);color:#fff} table.lvt .chip.bp{border-color:var(--red);color:var(--red)} table.lvt .chip.warn{border-color:var(--warn);color:var(--warn)}
.bar{position:relative;height:5px;border-radius:3px;background:var(--line);margin-top:4px;min-width:90px} .bar i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--red)} .bar.ok i{background:var(--good)}
.lvnote{font-size:12px;color:var(--mute);padding:8px 14px 12px;line-height:1.5}
/* game drill-down: box score + play by play (11/4) */
.drillbar{display:flex;align-items:center;gap:10px;padding:8px 14px;border-bottom:1px solid var(--line);font-size:12px;color:var(--mute)}
.drill{font:inherit;font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--red);background:transparent;border:1.5px solid var(--red);border-radius:99px;padding:5px 12px;cursor:pointer} .drill:hover{background:var(--red);color:#fff}
#lvdrill{position:fixed;inset:0;z-index:60;background:rgba(10,16,28,.55);overflow:auto;-webkit-overflow-scrolling:touch;padding:12px} body.drillopen{overflow:hidden}
#lvdrill .dwrap{max-width:760px;margin:0 auto;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;min-height:50vh}
#lvdrill .dhd{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 14px;background:var(--chalk);border-bottom:1px solid var(--line)} #lvdrill .dt{font-family:var(--display);font-weight:800;font-size:20px;display:flex;align-items:center;gap:6px;flex-wrap:wrap} #lvdrill .dt b{font-size:26px} #lvdrill .dt small{flex-basis:100%;font-family:var(--body);font-weight:500;font-size:12px;color:var(--mute)}
#lvdrill .dclose{font:inherit;font-size:26px;line-height:1;background:transparent;border:0;color:var(--mute);cursor:pointer;padding:4px 8px}
#lvdrill .dtabs{display:flex;gap:6px;padding:10px 14px;border-bottom:1px solid var(--line)} #lvdrill .dtab{font:inherit;font-family:var(--display);font-weight:800;font-size:11px;letter-spacing:.08em;text-transform:uppercase;padding:6px 12px;border-radius:99px;border:1.5px solid var(--line);background:transparent;color:var(--mute);cursor:pointer} #lvdrill .dtab.on{border-color:var(--red);background:var(--red);color:#fff}
#lvdrill .dbody{padding:10px 14px 18px} #lvdrill h4{font-family:var(--display);font-size:14px;letter-spacing:.08em;text-transform:uppercase;margin:12px 0 6px;color:var(--mute)}
.bxw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:10px} table.bx{width:100%;border-collapse:collapse;font-size:12.5px} table.bx th{font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);text-align:right;padding:4px 6px;border-bottom:1px solid var(--line)} table.bx th:first-child{text-align:left} table.bx td{padding:5px 6px;text-align:right;font-variant-numeric:tabular-nums;border-bottom:1px solid color-mix(in srgb,var(--line) 60%,transparent)} table.bx td.nm{text-align:left;font-weight:600;white-space:nowrap}
table.bx tr.mine td{background:color-mix(in srgb,var(--red) 8%,var(--card))} .lms{display:flex;flex-wrap:wrap;gap:4px;margin-top:3px} .lm{display:inline-block;font-size:10.5px;font-weight:600;padding:1px 7px;border-radius:99px;border:1px solid var(--line);color:var(--mute);white-space:nowrap} .lm.hit{border-color:var(--good);color:var(--good)} .lm.dead{border-color:var(--bad);color:var(--bad);text-decoration:line-through} .lm.open{border-color:var(--red);color:var(--red)}
table.bx.sc td{text-align:left} table.bx.sc td.q,table.bx.sc td.tm{white-space:nowrap;font-weight:700} table.bx.sc td small{display:block;font-weight:500;color:var(--mute);font-size:11px} table.bx.sc td.scr{text-align:right;font-family:var(--display);font-weight:800;white-space:nowrap}
.drv{border:1px solid var(--line);border-radius:10px;margin-bottom:10px;overflow:hidden} .drv.score{border-color:var(--good)} .drv .dh{padding:7px 10px;background:var(--chalk);font-size:12px;color:var(--mute)} .drv .dh b{color:var(--ink)} .drv .dh i{font-style:normal;font-weight:700;color:var(--red);margin-left:6px}
.drv .pl{display:grid;grid-template-columns:70px minmax(0,1fr) auto;gap:8px;padding:6px 10px;font-size:12.5px;border-top:1px solid color-mix(in srgb,var(--line) 60%,transparent)} .drv .pl .dd{color:var(--mute);font-size:11px;white-space:nowrap} .drv .pl .tx{text-align:left} .drv .dh{text-align:left} .drv .pl .ck{color:var(--mute);font-size:11px;white-space:nowrap}
.drv .pl.td{background:color-mix(in srgb,var(--good) 14%,var(--card))} .drv .pl.td b.sc{color:var(--good);font-family:var(--display);letter-spacing:.06em;text-transform:uppercase;font-size:11px} .drv .pl.mine .tx{font-weight:700} .drv .pl.mine{box-shadow:inset 3px 0 0 var(--red)}
/* owner 11/1 cleanup: one toolbar, help folded away, finished games grouped, quieter rows */
.lvtools{gap:6px} .lvtools .upd{flex-basis:100%;font-size:11.5px} .lvtools #lvrefresh{font-size:15px;line-height:1;padding:5px 10px}
.lvhelp{margin:-4px 0 12px;font-size:12.5px;color:var(--mute)} .lvhelp summary{cursor:pointer;font-weight:600;padding:2px 2px 6px;list-style:none} .lvhelp summary::-webkit-details-marker{display:none} .lvhelp summary::before{content:'ⓘ  '}
.lvhelp[open]{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px} .lvhelp p{margin:6px 0;line-height:1.5}
.fingrp .ghd2.fin{grid-template-columns:1fr;grid-template-areas:"a" "s"} .fingrp .ghd2.fin .t{font-size:18px} .finin .lg2{margin:8px 10px;border-radius:8px}
.lvt td.who small{white-space:normal}
.lg2.slipcard{transition:box-shadow .3s;scroll-margin-top:96px} .lg2.slipcard.hl{box-shadow:0 0 0 3px var(--red)}
table.lvt td.st,table.lvt td.who{display:table-cell;background:none;border-radius:0;gap:0;line-height:1.3;font-size:13px;white-space:normal;flex:none;padding:7px 14px;text-align:left} table.lvt td.st{width:28px;padding-right:0;vertical-align:top;text-align:center;padding-top:6px} .star{margin-top:-1px} .star{font:inherit;font-size:17px;line-height:1;background:none;border:0;color:var(--mute);cursor:pointer;padding:2px 4px} tr.starred .star{color:var(--warn)}
table.lvt .chip.slip{background:var(--ink);border-color:var(--ink);color:var(--bg)} table.lvt .chip.rz{background:var(--red);border-color:var(--red);color:#fff}
.pace{display:inline-block;font-size:10.5px;font-weight:600;color:var(--mute);margin-left:6px;vertical-align:1px} .pace.up{color:var(--good)} .pace.dn{color:var(--bad)}
@keyframes lvflash{0%{background:color-mix(in srgb,var(--warn) 35%,var(--card))}100%{background:transparent}} table.lvt tr.flash td{animation:lvflash 2.5s ease-out}
.lg2.slipcard{border-color:var(--ink)} .lg2 .ghd2.static{cursor:default} .lg2 .ghd2.static .t{font-size:18px}
.lvbar .rfr{font:inherit;font-size:12px;font-weight:600;color:var(--ink);background:var(--chalk);border:1px solid var(--line);border-radius:4px;padding:5px 10px;cursor:pointer} .lvbar .rfr:hover{border-color:var(--red)}
.empty{padding:14px;color:var(--mute);font-size:13px}
table.lvt td.st{width:30px} table.lvt td.st .add{display:block;font:inherit;font-size:15px;font-weight:700;line-height:1;background:none;border:1.5px solid var(--line);border-radius:5px;color:var(--mute);cursor:pointer;padding:1px 5px;margin:4px auto 0} table.lvt td.st .add.in{background:var(--ink);border-color:var(--ink);color:var(--bg)}
table.lvt td.st .rm{font:inherit;font-size:14px;line-height:1;background:none;border:0;color:var(--mute);cursor:pointer;padding:4px 6px} table.lvt td.st .rm:hover{color:var(--bad)}
.slipcard .ghd2 .t input{font:inherit;font-family:var(--display);font-weight:800;font-size:18px;border:0;border-bottom:1px dashed var(--line);background:none;color:inherit;width:100%;min-width:0;padding:0} .slipcard .ghd2 .t.r small{text-align:right;white-space:normal}
.slipbar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px 14px;border-top:1px solid var(--line);font-size:12px;color:var(--mute)} .slipbar .rfr{font:inherit;font-size:12px;font-weight:600;color:var(--ink);background:var(--chalk);border:1px solid var(--line);border-radius:4px;padding:5px 10px;cursor:pointer;text-decoration:none} .slipbar .rfr.fd{border-color:var(--red);color:var(--red)} .slipbar .rfr:hover{border-color:var(--red)}
.slipbar label{display:inline-flex;align-items:center;gap:4px} .slipbar input{font:inherit;font-size:12px;width:64px;border:1px solid var(--line);border-radius:4px;padding:4px 6px;background:var(--card);color:var(--ink)}
.addmenu{position:absolute;z-index:40;background:var(--card);border:1px solid var(--ink);border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.18);padding:6px;min-width:190px;max-width:260px} .addmenu button{display:block;width:100%;text-align:left;font:inherit;font-size:13px;background:none;border:0;border-radius:5px;padding:7px 9px;cursor:pointer;color:var(--ink)} .addmenu button:hover{background:var(--chalk)} .addmenu button.in::before{content:"✓ ";color:var(--good);font-weight:700} .addmenu button.new{color:var(--red);font-weight:700;border-top:1px solid var(--line);border-radius:0;margin-top:4px;padding-top:9px} .addmenu small{display:block;padding:2px 9px 4px;color:var(--mute);font-size:11px}
.imp{background:var(--card);border:1px solid var(--ink);border-radius:10px;padding:12px 14px;margin-bottom:14px;font-size:13px} .imp h3{margin:0 0 6px;font-family:var(--display);font-size:16px} .imp p{margin:0 0 8px;color:var(--mute);font-size:12px;line-height:1.45}
.imp textarea{width:100%;box-sizing:border-box;min-height:110px;font:inherit;font-size:13px;border:1px solid var(--line);border-radius:6px;padding:8px;background:var(--bg);color:var(--ink)} .imp .row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:8px} .imp .row input{font:inherit;font-size:13px;border:1px solid var(--line);border-radius:6px;padding:6px 8px;background:var(--bg);color:var(--ink)} .imp .row input.nm{flex:1;min-width:140px} .imp .row input.od{width:84px}
.imp ul{list-style:none;margin:10px 0 0;padding:0;border-top:1px solid var(--line)} .imp li{display:flex;gap:8px;align-items:flex-start;padding:7px 0;border-bottom:1px solid var(--line)} .imp li i{font-style:normal;font-weight:800;width:18px;flex:none} .imp li.ok i{color:var(--good)} .imp li.near i{color:var(--warn)} .imp li.no i{color:var(--bad)} .imp li small{display:block;color:var(--mute);font-size:11.5px} .imp li s{color:var(--mute)}
.imp .rfr{font:inherit;font-size:12.5px;font-weight:600;color:var(--ink);background:var(--chalk);border:1px solid var(--line);border-radius:4px;padding:6px 12px;cursor:pointer} .imp .rfr.go{background:var(--red);border-color:var(--red);color:#fff} .imp .rfr[disabled]{opacity:.5;cursor:default}
@media (max-width:560px){ .lg2.slipcard .ghd2{grid-template-columns:minmax(0,1.4fr) auto minmax(0,1fr)} .lg2.slipcard .ghd2 .t small{display:block} .lg2.slipcard .ghd2 .t.r small{font-size:10.5px} .slipbar{padding:8px 8px} }
@media (max-width:560px){ .lg2 .ghd2{gap:6px 6px;padding:10px 10px} .lg2 .ghd2 .t{font-size:15px;gap:5px} .lg2 .ghd2 .t small{display:none} .lg2 .ghd2 .t .badge{width:30px;height:30px;font-size:9px;border-radius:6px} .lg2 .ghd2 .mid b{font-size:22px} .lg2 .ghd2 .mid small{font-size:10.5px} table.lvt td,table.lvt td.st,table.lvt td.who{padding:8px 6px} table.lvt td.who{padding-left:2px} table.lvt td.who b{font-size:13.5px} table.lvt td.who small{font-size:11px;line-height:1.35} table.lvt td.now{padding-left:4px;padding-right:4px} table.lvt td.now b{font-size:13px} table.lvt td.pr{padding-right:8px} table.lvt td.pr b{font-size:17px} table.lvt td.pr small{font-size:10px;max-width:84px;white-space:normal;line-height:1.2} table.lvt .chip{font-size:9px;padding:1px 5px;margin-left:4px} }
"""

JS = r"""
(function(){
  var D = window.__LV, legs = D.legs, games = {}, order = []; D.games.forEach(function(g){ games[g.gid] = g; order.push(g.gid); });
  var $ = function(s, r){ return (r||document).querySelector(s); };
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(ch){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]; }); }
  function am(o){ return o > 0 ? '+' + o : '' + o; } function pc(p){ return Math.round(p*100) + '%'; }
  function lum(h){ h = h.replace('#',''); return 0.2126*parseInt(h.substr(0,2),16)/255 + 0.7152*parseInt(h.substr(2,2),16)/255 + 0.0722*parseInt(h.substr(4,2),16)/255; }
  function badge(t, col){ return '<span class="badge" style="--p:' + col[0] + ';--s:' + col[1] + ';--ink:' + (lum(col[0]) > 0.45 ? '#101820' : '#ffffff') + '">' + t + '</span>'; }
  function norm(s){ return String(s||'').replace(/\./g,'').replace(/\s+(jr|sr|ii|iii|iv|v)$/i,'').replace(/\s+/g,' ').toLowerCase().trim(); }
  function phi(z){ var t = 1/(1+0.2316419*Math.abs(z)), d = 0.3989423*Math.exp(-z*z/2), p = d*t*(0.3193815+t*(-0.3565638+t*(1.781478+t*(-1.821256+t*1.330274)))); return z >= 0 ? 1-p : p; }
  function nppf(p){ var a=[-3.969683028665376e+01,2.209460984245205e+02,-2.759285104469687e+02,1.383577518672690e+02,-3.066479806614716e+01,2.506628277459239e+00],b=[-5.447609879822406e+01,1.615858368580409e+02,-1.556989798598866e+02,6.680131188771972e+01,-1.328068155288572e+01],c=[-7.784894002430293e-03,-3.223964580411365e-01,-2.400758277161838e+00,-2.549732539343734e+00,4.374664141464968e+00,2.938163982698783e+00],d=[7.784695709041462e-03,3.224671290700398e-01,2.445134137142996e+00,3.754408661907416e+00],q,r;
    p = Math.min(0.9999, Math.max(0.0001, p));
    if(p<0.02425){q=Math.sqrt(-2*Math.log(p));return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);}
    if(p>1-0.02425){q=Math.sqrt(-2*Math.log(1-p));return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);}
    q=p-0.5;r=q*q;return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1); }
  var STATE = {}, BOX = {}, FIRST = {}, lastBox = {}, mode = 'likes', OPEN = {}, SUMM = {}, DRILL = null;
  var SKEY = 'bs_livestar_w' + D.week, STARS = {}; try { (JSON.parse(localStorage.getItem(SKEY) || '[]')).forEach(function(k){ STARS[k] = true; }); } catch(e){}
  function saveStars(){ try { localStorage.setItem(SKEY, JSON.stringify(Object.keys(STARS))); } catch(e){} }
  function legKey(l){ return l.pl + '|' + l.m + '|' + Math.round(l.ln || 1); }
  var SLIP = {}; function loadSlip(){ SLIP = {}; try { (JSON.parse(localStorage.getItem('bs_slipk_w' + D.week) || '[]')).forEach(function(k){ SLIP[k] = true; }); } catch(e){} }
  function saveBuilderSlip(){ try { localStorage.setItem('bs_slipk_w' + D.week, JSON.stringify(Object.keys(SLIP))); } catch(e){} }
  // ---- slips: the builder slip (shared with the boards / builder) plus any number of slips built or imported here; each is tracked live as one parlay ----
  var SLKEY = 'bs_slips_w' + D.week, SLIPS = [], INSLIP = {}, LEGIDX = {};
  legs.concat(D.extra || []).forEach(function(l){ var k = legKey(l); if(!(k in LEGIDX)) LEGIDX[k] = l; });
  function loadSlips(){ loadSlip(); SLIPS = []; try { SLIPS = JSON.parse(localStorage.getItem(SLKEY) || '[]'); if(!Array.isArray(SLIPS)) SLIPS = []; } catch(e){ SLIPS = []; }
    SLIPS = SLIPS.filter(function(s){ return s && s.id && Array.isArray(s.keys); });
    INSLIP = {}; Object.keys(SLIP).forEach(function(k){ (INSLIP[k] = INSLIP[k] || []).push('builder'); }); SLIPS.forEach(function(s){ s.keys.forEach(function(k){ (INSLIP[k] = INSLIP[k] || []).push(s.id); }); }); }
  function saveSlips(){ try { localStorage.setItem(SLKEY, JSON.stringify(SLIPS)); } catch(e){} }
  var BMETA = {}; try { BMETA = JSON.parse(localStorage.getItem('bs_slipmeta_w' + D.week) || '{}') || {}; } catch(e){}
  function saveBMeta(){ try { localStorage.setItem('bs_slipmeta_w' + D.week, JSON.stringify(BMETA)); } catch(e){} }
  function allSlips(){ var out = []; var bk = Object.keys(SLIP); if(bk.length) out.push({id: 'builder', name: BMETA.name || 'Builder slip', keys: bk, odds: BMETA.odds, stake: BMETA.stake, builder: true}); return out.concat(SLIPS); }
  function slipById(id){ return id === 'builder' ? allSlips()[0] : SLIPS.filter(function(s){ return s.id === id; })[0]; }
  function toggleIn(id, k){
    if(id === 'builder'){ if(SLIP[k]) delete SLIP[k]; else SLIP[k] = true; saveBuilderSlip(); }
    else { var s = slipById(id); if(!s) return; var i = s.keys.indexOf(k); if(i >= 0) s.keys.splice(i, 1); else s.keys.push(k); saveSlips(); }
    loadSlips(); render(); }
  function newSlip(name, keys, odds, stake){ var s = {id: 's' + Date.now().toString(36), name: name || ('Slip ' + (SLIPS.length + 1)), keys: keys || [], odds: odds || null, stake: stake || null, made: Date.now()}; SLIPS.push(s); saveSlips(); loadSlips(); return s; }
  function dec(o){ return o > 0 ? 1 + o/100 : 1 + 100/(-o); } function amer(d){ return d >= 2 ? Math.round((d - 1)*100) : -Math.round(100/(d - 1)); }
  function parseOdds(v){ var m = String(v == null ? '' : v).trim().match(/^([+-])?\s*(\d{3,5})$/); return m ? (m[1] === '-' ? -1 : 1) * (+m[2]) : null; }
  function slipLegs(sl){ return sl.keys.map(function(k){ return LEGIDX[k]; }).filter(Boolean); }
  function slipCard(sl){
    var ls = slipLegs(sl); var missing = sl.keys.length - ls.length;
    var sr = ls.map(function(l){ var g = games[l.g], s = STATE[l.g] || {st:'pre'}; return {l: l, r: live(l, g, s), s: s}; });
    var nh = sr.filter(function(x){ return x.r.status === 'hit'; }).length, nd = sr.filter(function(x){ return x.r.status === 'dead'; }).length, no = sr.length - nh - nd;
    var pj = sr.reduce(function(a, x){ return a * (x.r.status === 'hit' ? 1 : x.r.status === 'dead' ? 0 : x.r.p); }, 1);
    var pre = sr.reduce(function(a, x){ return a * x.l.p; }, 1);
    var legsDec = ls.reduce(function(a, l){ return a * dec(l.o); }, 1); var price = sl.odds || (ls.length ? amer(legsDec) : null);
    var toWin = (sl.stake && price) ? sl.stake * (dec(price) - 1) : null;
    var fdOk = ls.filter(function(l){ return l.fd && l.fd.m; });
    var fdUrl = fdOk.length ? 'https://sportsbook.fanduel.com/addToBetslip?' + fdOk.map(function(l, i){ return 'marketId[' + i + ']=' + encodeURIComponent(l.fd.m) + '&selectionId[' + i + ']=' + encodeURIComponent(l.fd.s); }).join('&') : '';
    var done = nd ? 'DEAD' : (no === 0 && nh ? 'CASHED' : pc(pj));
    var sub = nd ? nh + ' hit · ' + nd + ' dead' : (no === 0 && nh ? 'all ' + nh + ' hit' : nh + ' hit · ' + no + ' open · chance from here' + (ls.length ? ' (pregame ' + pc(pre) + ')' : ''));
    var rows = sr.map(function(x){ var l = x.l, r = x.r, st = x.s; return '<tr class="' + (r.status === 'hit' ? 'hit' : r.status === 'dead' ? 'dead' : '') + '"><td class="st"><button type="button" class="rm" data-sid="' + esc(sl.id) + '" data-k="' + esc(legKey(l)) + '" title="Remove from this slip">×</button></td><td class="who"><b>' + esc(legText(l)) + (r.status === 'hit' ? '<span class="chip hit">Hit</span>' : r.status === 'dead' ? '<span class="chip">Dead</span>' : '') + '</b><small>' + esc(l.tm) + ' vs ' + esc(l.opp) + ' · FD ' + am(l.o) + ' · ' + (st.st === 'in' ? esc(st.det || 'live') : st.st === 'post' ? 'final' : esc(games[l.g].kick)) + '</small></td><td class="now"><b>' + esc(r.now || '') + '</b></td><td class="pr"><b class="' + (r.status === 'hit' ? 'up' : r.status === 'dead' ? 'dn' : '') + '">' + pc(r.p) + '</b><small>' + (st.st === 'pre' ? 'pregame' : 'from here') + '</small></td></tr>'; }).join('');
    if(missing) rows += '<tr><td class="st"></td><td class="who" colspan="3"><small>' + missing + ' leg' + (missing > 1 ? 's' : '') + ' from an older board are not on this week\'s page and cannot be tracked.</small></td></tr>';
    if(!ls.length && !missing) rows = '<tr><td class="who" colspan="4"><small>Empty - tap + on any leg below to add it here.</small></td></tr>';
    return '<section class="lg2 slipcard open" data-sid="' + esc(sl.id) + '"><div class="ghd2 static"><span class="t"><input type="text" class="slipname" data-sid="' + esc(sl.id) + '" value="' + esc(sl.name) + '" aria-label="Slip name"><small>' + ls.length + ' leg' + (ls.length === 1 ? '' : 's') + (sl.builder ? ' · shared with the boards / builder' : '') + '</small></span><span class="mid"><b>' + done + '</b><small>' + sub + '</small></span><span class="t r"><small>' + (price ? (sl.odds ? 'ticket ' : 'legs imply ') + am(price) : '') + (toWin != null ? '<br>$' + (+sl.stake).toFixed(2) + ' → wins $' + toWin.toFixed(2) : '') + (no && pj > 0 && pj < 1 ? '<br>fair from here ' + am(amer(1/pj)) : '') + '</small></span></div>' +
      '<table class="lvt">' + rows + '</table>' +
      '<div class="slipbar">' + (fdUrl ? '<a class="rfr fd" href="' + fdUrl + '" target="_blank" rel="noopener">Open in FanDuel' + (fdOk.length < ls.length ? ' (' + fdOk.length + '/' + ls.length + ')' : '') + '</a>' : '') +
      '<label>ticket <input type="text" inputmode="numeric" class="slipodds" data-sid="' + esc(sl.id) + '" placeholder="+593" value="' + (sl.odds ? am(sl.odds) : '') + '"></label><label>stake $<input type="text" inputmode="decimal" class="slipstake" data-sid="' + esc(sl.id) + '" placeholder="10" value="' + (sl.stake || '') + '"></label>' +
      '<button type="button" class="rfr slipdel" data-sid="' + esc(sl.id) + '">' + (sl.builder ? 'Clear' : 'Delete') + '</button></div></section>'; }
  var PREV = {}, FLASH = {};   // status per leg from the last render, to flash what just changed   // OPEN[gid] = true/false once the user has toggled; otherwise live games open, others closed
  // ---- ESPN game summary -> per-player box + first TD scorer ----
  function parseBox(js){
    var box = {}, first = null;
    try {
      (js.boxscore.players || []).forEach(function(tm){
        (tm.statistics || []).forEach(function(cat){
          var keys = cat.keys || cat.labels || [];
          (cat.athletes || []).forEach(function(a){
            var n = norm(a.athlete && (a.athlete.displayName || a.athlete.shortName)); if(!n) return;
            var row = box[n] = box[n] || {pass:0, rush:0, rec:0, recy:0, long:0, td:0, name: a.athlete.displayName};
            var S = {}; keys.forEach(function(k, i){ S[k] = a.stats[i]; });
            var num = function(v){ var m = String(v == null ? '' : v).match(/-?\d+(\.\d+)?/); return m ? +m[0] : 0; };
            if(cat.name === 'passing'){ row.pass = num(S.passingYards != null ? S.passingYards : S.YDS); }
            if(cat.name === 'rushing'){ row.rush = num(S.rushingYards != null ? S.rushingYards : S.YDS); row.td += num(S.rushingTouchdowns != null ? S.rushingTouchdowns : S.TD); }
            if(cat.name === 'receiving'){ row.rec = num(S.receptions != null ? S.receptions : S.REC); row.recy = num(S.receivingYards != null ? S.receivingYards : S.YDS); row.long = Math.max(row.long, num(S.longReception != null ? S.longReception : S.LONG)); row.td += num(S.receivingTouchdowns != null ? S.receivingTouchdowns : S.TD); }
          });
        });
      });
      var sp = (js.scoringPlays || []).filter(function(p){ return p.type && /touchdown/i.test(p.type.text || '') || /\bTD\b|touchdown/i.test(p.text || ''); });
      if(sp.length){ var t = sp[0].text || ''; var m = t.match(/^([A-Z][\w.'-]+(?:\s[A-Z][\w.'-]+){0,3}?)\s+\d+\s+(?:Yd|Yard)/i); first = m ? norm(m[1]) : t; }
    } catch(e){}
    return {box: box, first: first};
  }
  function remainingFrac(s){
    if(!s || s.st === 'pre') return 1; if(s.st === 'post') return 0;
    var per = s.period || 1, m = String(s.clock || '0:00').split(':'), secs = (+m[0] || 0)*60 + (+m[1] || 0);
    if(per > 4) return Math.max(0.02, secs/3600);   // overtime: a little time left
    return Math.max(0, ((4 - per)*900 + secs)/3600);
  }
  function statFor(l, b){ return l.m === 'Passing Yards' ? b.pass : l.m === 'Rushing Yards' ? b.rush : l.m === 'Receiving Yards' ? b.recy : l.m === 'Receptions' ? b.rec : l.m === 'Longest Reception' ? b.long : (l.m === 'Anytime TD' || l.m === 'First TD' || l.m === '2+ TD' || l.m === '3+ TD') ? b.td : null; }
  // live chance for one leg; returns {p, status: 'open'|'hit'|'dead'|'pre', now: text}
  function live(l, g, s){
    if(l.u){ var o2 = Object.assign({}, l, {m: l.m.replace(/^Under /, ''), u: 0, p: 1 - l.p, ln: Math.floor(l.ln) + 1}); var r2 = live(o2, g, s);   // under = the other side of the (X+1)+ over
      return {p: 1 - r2.p, status: r2.status === 'hit' ? 'dead' : r2.status === 'dead' ? 'hit' : r2.status, now: r2.now}; }
    var f = remainingFrac(s);
    if(!s || s.st === 'pre') return {p: l.p, status: 'pre', now: ''};
    var sa = +(s.sa||0), sb = +(s.sb||0), m = sa - sb, tot = sa + sb;
    if(l.gl){
      var sd = l.gl.k === 'M' ? 12.6 : 12.9;
      if(l.m === 'Moneyline'){ var pt0 = 0, mu = -nppf(1 - l.p)*12.6 * (l.tm === g.a ? 1 : -1); var mm = l.tm === g.a ? m : -m; if(f <= 0) return {p: mm > 0 ? 1 : 0, status: mm > 0 ? 'hit' : 'dead', now: sa + '-' + sb}; return {p: 1 - phi((0 - mm - (l.tm === g.a ? mu : -mu)*f)/(sd*Math.sqrt(f))), status: 'open', now: (l.tm === g.a ? g.a : g.b) + (mm >= 0 ? ' +' : ' ') + mm}; }
      if(l.m === 'Spread'){ var pt = l.ln, mm2 = l.tm === g.a ? m : -m, muS = -pt - nppf(1 - l.p)*12.6; if(f <= 0) return {p: mm2 + pt > 0 ? 1 : 0, status: mm2 + pt > 0 ? 'hit' : 'dead', now: 'final ' + sa + '-' + sb}; return {p: 1 - phi((-pt - mm2 - muS*f)/(sd*Math.sqrt(f))), status: 'open', now: (mm2 >= 0 ? '+' : '') + mm2 + ' now · needs ' + (pt > 0 ? '+' : '') + pt}; }
      if(l.m === 'Total'){ var over = l.gl.side === 'OVER', L = l.ln, muT = L - nppf(1 - (over ? l.p : 1 - l.p))*12.9; var pOver = f <= 0 ? (tot > L ? 1 : 0) : 1 - phi((L - tot - muT*f)/(sd*Math.sqrt(f))); var p = over ? pOver : 1 - pOver; var done = f <= 0 || (over && tot > L); return {p: p, status: done ? (p > 0.5 ? 'hit' : 'dead') : 'open', now: tot + ' pts · line ' + L}; }
    }
    var b = BOX[norm(l.pl)]; var cur = b ? statFor(l, b) : (lastBox[g.gid] ? 0 : null);   // box loaded and he is not in it = no stats yet
    if(l.m === 'First TD'){ var ft = FIRST[g.gid]; if(ft){ return {p: ft === norm(l.pl) ? 1 : 0, status: ft === norm(l.pl) ? 'hit' : 'dead', now: ft === norm(l.pl) ? 'scored first' : 'first TD gone'}; } return {p: l.p, status: f > 0 ? 'open' : 'dead', now: 'no TD yet'}; }
    if(l.m === '2+ TD' || l.m === '3+ TD'){ var needT = l.m === '2+ TD' ? 2 : 3; if(cur != null && cur >= needT) return {p: 1, status: 'hit', now: cur + ' TD'}; var lamT = -Math.log(1 - Math.min(0.99, l.p)) * tilt(l, g, s); var left = needT - (cur || 0); var pr = 0; if(f > 0){ var mu = lamT * f; var term = Math.exp(-mu), cum = term; for(var kk = 1; kk < left; kk++){ term *= mu / kk; cum += term; } pr = Math.max(0, 1 - cum); } return {p: f > 0 ? Math.min(0.97, pr) : 0, status: f > 0 ? 'open' : 'dead', now: (cur || 0) + ' TD so far, needs ' + needT}; }
    if(l.m === 'Anytime TD'){ if(cur != null && cur >= 1) return {p: 1, status: 'hit', now: cur + ' TD'}; var lam = -Math.log(1 - Math.min(0.99, l.p)) * tilt(l, g, s); var rz = s.rz && s.poss === l.tm; return {p: f > 0 ? Math.min(0.97, 1 - Math.exp(-lam*f) + (rz ? 0.06 : 0)) : 0, status: f > 0 ? 'open' : 'dead', now: rz ? 'no TD yet · team in the red zone' : 'no TD yet', rz: rz}; }
    if(cur == null){ var fsx = (window.BSLive.status && window.BSLive.status()) || {}; return {p: l.p, status: f > 0 ? 'open' : 'dead', now: fsx.ok === false ? 'score feed down' : (s.st === 'post' ? 'stats not loaded' : 'waiting for stats')}; }
    var L = l.ln;
    if(cur >= L) return {p: 1, status: 'hit', now: cur + ' / ' + L};
    if(f <= 0) return {p: 0, status: 'dead', now: cur + ' / ' + L};
    if(l.m === 'Longest Reception'){ return {p: 1 - Math.pow(1 - Math.min(0.99, l.p), f), status: 'open', now: 'long ' + cur + ' / ' + L}; }
    var mu = (l.proj != null ? l.proj : L) * tilt(l, g, s); var z = nppf(1 - Math.min(0.99, Math.max(0.01, l.p))); var kmin = l.m === 'Passing Yards' ? 0.28 : l.m === 'Rushing Yards' ? 0.45 : l.m === 'Receptions' ? 0.35 : 0.5;   // floor on the spread: a pregame chance near 50% backs out an unrealistically tight sigma
    var sig = Math.abs(z) > 0.05 ? Math.abs((L - 0.5 - mu)/z) : 0; sig = Math.min(Math.max(sig, kmin*mu, 2), 1.2*mu + 5);
    return {p: 1 - phi((L - 0.5 - cur - mu*f)/(sig*Math.sqrt(f))), status: 'open', now: cur + ' / ' + L};
  }
  // game-state tilt for the rest of the game: after halftime a team trailing by 7+ throws more (pass/rec x1.12, rush x0.88); leading by 10+ runs more (rush x1.12, pass/rec x0.9); TD rate follows the team's own scoring tilt
  function tilt(l, g, s){
    if(!s || s.st !== 'in' || (s.period || 1) < 3) return 1;
    var m = (+(s.sa||0)) - (+(s.sb||0)); var mine = l.tm === g.a ? m : -m;
    var pass = l.m === 'Passing Yards' || l.m === 'Receiving Yards' || l.m === 'Receptions' || l.m === 'Longest Reception', rush = l.m === 'Rushing Yards', td = l.m === 'Anytime TD';
    if(mine <= -7){ return pass ? 1.12 : rush ? 0.88 : td ? 1.04 : 1; }
    if(mine >= 10){ return pass ? 0.9 : rush ? 1.12 : td ? 0.96 : 1; }
    return 1;
  }
  // pace: current stat vs the share of the game already played, against the line
  function pace(l, r, s){
    if(l.gl || l.m === 'First TD' || l.m === 'Anytime TD' || l.m === 'Longest Reception' || !s || s.st !== 'in') return '';
    var f = remainingFrac(s), el = 1 - f; if(el < 0.12) return '';
    var cur = +String(r.now).split(' / ')[0].replace(/[^\d.]/g, ''); if(!(cur >= 0)) return '';
    var onp = cur / el; var rel = onp / l.ln;
    return rel >= 1.15 ? '<span class="pace up">ahead of pace</span>' : rel >= 0.9 ? '' : '<span class="pace dn">behind</span>';
  }
  function legText(l){ if(l.gl) return l.pl; return l.pl + ' ' + (l.m === 'First TD' ? 'first TD' : l.m === 'Anytime TD' ? 'anytime TD' : (l.m === '2+ TD' || l.m === '3+ TD') ? l.m : l.ms.toLowerCase() + ' ' + (l.u ? 'under ' + l.ln : Math.round(l.ln) + '+')); }
  function liked(l){ return l.bp || (l.e >= 0.05 && !l.w) || (l.m === 'Anytime TD' && l.e >= 0.03 && !l.w); }
  function pickScore(l){ var k = legKey(l); return (INSLIP[k] ? 400 : 0) + (STARS[k] ? 300 : 0) + (l.bp ? 200 : 0) + (l.e || 0) * 100; }
  // ---- DOM diff: replace only the cards whose HTML changed, keep the rest (and the scroll position) in place ----
  var LASTSCROLL = 0, RENDER_WAIT = null, LASTHTML = {};
  ['scroll', 'touchmove', 'touchstart', 'wheel'].forEach(function(ev){ window.addEventListener(ev, function(){ LASTSCROLL = Date.now(); }, {passive: true}); });
  function applyParts(wrap, parts){
    var want = {}; parts.forEach(function(p){ want[p[0]] = true; });
    wrap.style.minHeight = wrap.offsetHeight + 'px';   // no height collapse mid-swap
    Array.prototype.slice.call(wrap.children).forEach(function(el){ if(!want[el.getAttribute('data-key')]){ el.remove(); delete LASTHTML[el.getAttribute('data-key')]; } });
    var prev = null;
    parts.forEach(function(p){
      var key = p[0], h = p[1]; var el = null;
      for(var i = 0; i < wrap.children.length; i++){ if(wrap.children[i].getAttribute('data-key') === key){ el = wrap.children[i]; break; } }
      if(!el || LASTHTML[key] !== h){
        var tmp = document.createElement('div'); tmp.innerHTML = h; var nel = tmp.firstElementChild; if(!nel) return; nel.setAttribute('data-key', key);
        if(el) wrap.replaceChild(nel, el); else wrap.insertBefore(nel, prev ? prev.nextSibling : wrap.firstChild);
        el = nel; LASTHTML[key] = h;
      } else if(el.previousElementSibling !== prev){ wrap.insertBefore(el, prev ? prev.nextSibling : wrap.firstChild); }
      prev = el;
    });
    requestAnimationFrame(function(){ wrap.style.minHeight = ''; });
  }
  function render(){
    var wrap = $('#lv'); var now = Date.now(); var html = ''; var parts = []; loadSlips();
    if(Date.now() - LASTSCROLL < 900){ if(!RENDER_WAIT){ RENDER_WAIT = setTimeout(function(){ RENDER_WAIT = null; render(); }, 1000); } return; }   // never re-render under a finger: iOS kills the scroll
    // slips: the builder slip plus anything built or imported on this page, each tracked live as one parlay
    allSlips().forEach(function(sl){ parts.push(['slip:' + sl.id, slipCard(sl)]); });
    // week log: the legs you pinned or carried in your slip, as they resolve - copy or download it after the games
    var mine = legs.concat(D.extra || []).filter(function(l){ var k = legKey(l); return STARS[k] || INSLIP[k]; });
    if(mine.length){
      var mr = mine.map(function(l){ var g = games[l.g], s = STATE[l.g] || {st:'pre'}; return {l: l, r: live(l, g, s), s: s}; });
      var w = mr.filter(function(x){ return x.r.status === 'hit'; }).length, lz = mr.filter(function(x){ return x.r.status === 'dead'; }).length, op = mr.length - w - lz;
      var units = mr.reduce(function(a, x){ return a + (x.r.status === 'hit' ? (x.l.o > 0 ? x.l.o / 100 : 100 / -x.l.o) : x.r.status === 'dead' ? -1 : 0); }, 0);
      var lrows = mr.sort(function(a, b){ return (a.l.g > b.l.g ? 1 : a.l.g < b.l.g ? -1 : 0) || (b.r.p - a.r.p); }).map(function(x){ var l = x.l, r = x.r; return '<tr class="' + (r.status === 'hit' ? 'hit' : r.status === 'dead' ? 'dead' : '') + '"><td class="st">' + (r.status === 'hit' ? '✓' : r.status === 'dead' ? '✗' : '·') + '</td><td class="who"><b>' + esc(legText(l)) + '</b><small>' + esc(l.g.replace('-', ' @ ')) + ' · FD ' + am(l.o) + ' · model ' + pc(l.p) + (INSLIP[legKey(l)] ? ' · ' + INSLIP[legKey(l)].map(function(id){ var sx = slipById(id); return sx ? sx.name : id; }).join(', ') : '') + '</small></td><td class="now"><b>' + esc(r.now || (x.s.st === 'pre' ? 'not started' : '')) + '</b></td><td class="pr"><b class="' + (r.status === 'hit' ? 'up' : r.status === 'dead' ? 'dn' : '') + '">' + (r.status === 'hit' ? 'WIN' : r.status === 'dead' ? 'LOSS' : pc(r.p)) + '</b></td></tr>'; }).join('');
      parts.push(['log', '<section class="lg2 logcard' + (OPEN.__log === false ? '' : ' open') + '"><button type="button" class="ghd2" data-g="__log" aria-expanded="' + (OPEN.__log !== false) + '"><span class="t">My week<small>' + mine.length + ' legs you pinned or slipped</small></span><span class="mid"><b>' + w + '–' + lz + '</b><small>' + (op ? op + ' still open · ' : '') + (units >= 0 ? '+' : '') + units.toFixed(2) + 'u at 1u each</small></span><span class="tog"><i class="car">' + (OPEN.__log !== false ? '▴' : '▾') + '</i></span></button>' +
        (OPEN.__log !== false ? '<div class="logbar"><button type="button" class="rfr" id="logcopy">Copy as text</button><button type="button" class="rfr" id="logcsv">Download CSV</button><span>Pin a leg (☆) or add it to your slip and it shows up here; results fill in as the games end.</span></div><table class="lvt">' + lrows + '</table>' : '') + '</section>']);
      window.__BSLOG = mr.map(function(x){ var l = x.l, r = x.r; return [D.week, l.g, l.pl, l.m, l.ln, l.o, Math.round(l.p * 1000) / 10, r.status === 'hit' ? 'WIN' : r.status === 'dead' ? 'LOSS' : 'OPEN', r.now || '', (INSLIP[legKey(l)] || []).map(function(id){ var sx = slipById(id); return sx ? sx.name : id; }).join('; ')]; });
    }
    var liveG = order.filter(function(gid){ var s = STATE[gid]; return s && s.st === 'in'; });
    var preG = order.filter(function(gid){ var s = STATE[gid]; return !s || s.st === 'pre'; });
    var doneG = order.filter(function(gid){ var s = STATE[gid]; return s && s.st === 'post'; });
    var seq = liveG.concat(preG).concat(doneG);
    if(!liveG.length){ var nxt = preG.length ? games[preG[0]] : null; parts.push(['bar', '<div class="lvbar"><span>No game in progress' + (nxt ? ' · next kickoff <b>' + esc(nxt.kick) + '</b> (' + nxt.a + '·' + nxt.b + ')' : '') + ' · the watch list below is what the model likes going in</span></div>']); }
    var FIN = [];
    seq.forEach(function(gid){
      var g = games[gid], s = STATE[gid] || {st:'pre'}; var f = remainingFrac(s);
      var gl = legs.filter(function(l){ return l.g === gid; });
      if(mode !== 'all'){   // picks view: your slip + pinned + best-parlay legs, then the clearest clean edges up to 8 rows, one line per player-market
        var keep = gl.filter(function(l){ var k = legKey(l); return INSLIP[k] || STARS[k] || l.bp; });
        var rest = gl.filter(function(l){ return keep.indexOf(l) < 0 && !l.w && (l.e || 0) > 0; }).sort(function(a, b){ return (liked(b) ? 1 : 0) - (liked(a) ? 1 : 0) || (b.e - a.e); });
        var seenPM = {}; keep.forEach(function(l){ seenPM[l.pl + '|' + l.m] = true; });
        rest.forEach(function(l){ var pm = l.pl + '|' + l.m; if(keep.length < 8 && !seenPM[pm]){ keep.push(l); seenPM[pm] = true; } });
        gl = keep;
      }
      var rows = gl.map(function(l){ var r = live(l, g, s); return {l: l, r: r}; });
      var open = rows.filter(function(x){ return x.r.status === 'open' || x.r.status === 'pre'; }).sort(function(a, b){ var sa_ = STARS[legKey(a.l)] ? 1 : 0, sb_ = STARS[legKey(b.l)] ? 1 : 0; return (sb_ - sa_) || (b.r.p - a.r.p); });
      var hit = rows.filter(function(x){ return x.r.status === 'hit'; }), dead = rows.filter(function(x){ return x.r.status === 'dead'; });
      var isOpen = (gid in OPEN) ? OPEN[gid] : (s.st === 'in' && rows.length > 0);
      var head = '<button type="button" class="ghd2" data-g="' + gid + '" aria-expanded="' + isOpen + '"><span class="t">' + badge(g.a, g.ca) + g.a + '<small>' + esc(g.na) + '</small></span><span class="mid"><b>' + (s.st === 'pre' ? g.pa.toFixed(1) + '<i>–</i>' + g.pb.toFixed(1) : (s.sa != null ? s.sa : '–') + '<i>–</i>' + (s.sb != null ? s.sb : '–')) + '</b><small>' + (s.st === 'in' ? '<span class="lvtag">Live</span> · ' + esc(s.det || '') : s.st === 'post' ? 'Final' : esc(g.kick) + ' · model ' + esc(g.most)) + '</small></span><span class="t r"><small>' + esc(g.nb) + '</small>' + g.b + badge(g.b, g.cb) + '</span>' +
        '<span class="tog">' + (s.st === 'in' ? open.length + ' open · ' + hit.length + ' hit' : s.st === 'pre' ? open.length + ' on the watch list' : hit.length + ' hit · ' + dead.length + ' gone') + '<i class="car">' + (isOpen ? '▴' : '▾') + '</i></span></button>';
      var sit = s.st === 'in' ? '<div class="sit">' + (s.poss ? '<b>' + esc(s.poss) + ' ball</b>' + (s.dd ? ', ' + esc(s.dd) : '') + ' · ' : '') + Math.round(f*100) + '% of regulation left' + (s.last ? ' · last: ' + esc(s.last) : '') + (BOX && Object.keys(BOX).length ? '' : ' · box score loading…') + '</div>' : '';
      var tr = function(x){ var l = x.l, r = x.r; var d = r.p - l.p; var k = legKey(l); var cls = (r.status === 'hit' ? 'hit' : r.status === 'dead' ? 'dead' : '') + (FLASH[k] ? ' flash' : '') + (STARS[k] ? ' starred' : '');
        var chips = (r.status === 'hit' ? '<span class="chip hit">Hit</span>' : '') + (INSLIP[k] ? '<span class="chip slip">' + (INSLIP[k].length > 1 ? INSLIP[k].length + ' slips' : esc((slipById(INSLIP[k][0]) || {name: 'slip'}).name)) + '</span>' : '') + (l.bp ? '<span class="chip bp">Best parlay</span>' : '') + (r.rz ? '<span class="chip rz">Red zone</span>' : '') + (l.w ? '<span class="chip warn" title="' + esc(l.w) + '">⚠</span>' : '') + pace(l, r, s);
        var prog = (!l.gl && r.status === 'open' && /\//.test(r.now)) ? '<div class="bar' + (r.p >= 0.5 ? ' ok' : '') + '"><i style="width:' + Math.min(100, Math.round(100*(+r.now.split(' / ')[0].replace(/[^\d.]/g,'') || 0)/l.ln)) + '%"></i></div>' : '';
        return '<tr class="' + cls + '" data-k="' + esc(k) + '"><td class="st"><button type="button" class="star" data-k="' + esc(k) + '" title="' + (STARS[k] ? 'Unpin' : 'Pin to the top') + '">' + (STARS[k] ? '★' : '☆') + '</button><button type="button" class="add' + (INSLIP[k] ? ' in' : '') + '" data-k="' + esc(k) + '" title="Add to a slip">+</button></td><td class="who"><b>' + esc(legText(l)) + chips + '</b><small>' + esc(l.tm) + ' · ' + (l.src === 'cons' ? 'mkt ' : 'FD ') + am(l.o) + ' · model ' + pc(l.p) + '</small></td>' +
          '<td class="now"><b>' + esc(r.now || (s.st === 'pre' ? '' : '—')) + '</b>' + prog + '</td>' +
          '<td class="pr"><b class="' + (r.status === 'hit' ? 'up' : r.status === 'dead' ? 'dn' : (d >= 0 ? 'up' : '')) + '">' + (s.st === 'pre' ? pc(l.p) : pc(r.p)) + '</b><small>' + (s.st === 'pre' ? 'pregame' : r.status === 'hit' ? 'cashed' : r.status === 'dead' ? 'gone' : (Math.round(d*100) ? (d >= 0 ? '▲' : '▼') + Math.abs(Math.round(d*100)) + ' since kickoff' : 'from here')) + '</small></td></tr>'; };
      var body = '';
      if(!rows.length) body = '<div class="empty">Nothing tracked for this game' + (mode === 'likes' ? ' at the "model likes" filter - switch to All' : '') + '.</div>';
      else {
        body += '<h4 class="' + (s.st === 'in' ? 'hot' : '') + '">' + (s.st === 'in' ? 'Still open · ' + open.length : s.st === 'pre' ? 'Watch list · ' + open.length : 'Open at the end · ' + open.length) + '</h4><table class="lvt">' + open.map(tr).join('') + '</table>';
        if(hit.length) body += '<h4>Already hit · ' + hit.length + '</h4><table class="lvt">' + hit.map(tr).join('') + '</table>';
        if(dead.length) body += '<h4>Gone · ' + dead.length + '</h4><table class="lvt">' + dead.map(tr).join('') + '</table>';
      }
      var drill = (s.st === 'in' || s.st === 'post') && s.eid ? '<div class="drillbar"><button type="button" class="drill" data-g="' + gid + '">Box score &amp; plays</button>' + (s.st === 'in' ? '<span>scoring plays highlighted · your legs marked</span>' : '') + '</div>' : '';
      var sec = '<section class="lg2 ' + (s.st === 'in' ? 'live' : s.st) + (isOpen ? ' open' : '') + '" id="lv-' + gid + '">' + head + (isOpen ? sit + drill + body : '') + '</section>';
      if(s.st === 'post') FIN.push([gid, sec, hit.length, dead.length]); else parts.push([gid, sec]);
    });
    if(FIN.length){   // owner 11/1 cleanup: finished games fold into one group at the bottom
      var fo = OPEN.__fin === true, fh = FIN.reduce(function(a, x){ return a + x[2]; }, 0), fd = FIN.reduce(function(a, x){ return a + x[3]; }, 0);
      parts.push(['__fin', '<section class="lg2 fingrp' + (fo ? ' open' : '') + '"><button type="button" class="ghd2 fin" data-g="__fin" aria-expanded="' + fo + '"><span class="t">Final<small>' + FIN.length + ' game' + (FIN.length === 1 ? '' : 's') + '</small></span><span class="tog">' + fh + ' hit · ' + fd + ' gone<i class="car">' + (fo ? '▴' : '▾') + '</i></span></button>' + (fo ? '<div class="finin">' + FIN.map(function(x){ return x[1]; }).join('') + '</div>' : '') + '</section>']); }
    FLASH = {}; legs.forEach(function(l){ var s = STATE[l.g]; if(!s || s.st !== 'in') return; var r = live(l, games[l.g], s); var k = legKey(l); if(PREV[k] && PREV[k] !== r.status) FLASH[k] = true; PREV[k] = r.status; });
    if(Object.keys(FLASH).length){ parts = parts.map(function(p){ return [p[0], p[1].replace(/<tr class="([^"]*)" data-k="([^"]*)"/g, function(m0, c, k){ return FLASH[k.replace(/&amp;/g,'&').replace(/&#39;/g, "'").replace(/&quot;/g,'"')] ? '<tr class="' + c + ' flash" data-k="' + k + '"' : m0; })]; }); }
    applyParts(wrap, parts);
    var nLiveOpen = 0; order.forEach(function(gid){ var s = STATE[gid]; if(s && s.st === 'in') nLiveOpen++; }); document.title = (nLiveOpen ? '● ' : '') + 'BetSweep Live';
    var fs = (window.BSLive.status && window.BSLive.status()) || {}; var ft = fs.at ? new Date(fs.at).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit', second: '2-digit'}) : '';
    $('#upd').textContent = 'updated ' + new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit', second: '2-digit'}) + (fs.ok === true ? ' · scores ' + ft + (fs.src === 'cdn' ? ' (backup feed)' : '') : fs.ok === false ? ' · live scores delayed, retrying' : '');
    // owner 11/1: a live slip notification opens /live/?slip=<id> - jump to that slip card (its legs already show hit / open / gone) and flash it
    if(FOCUS && !FOCUSED){ var fe = FOCUS === 'all' ? wrap.querySelector('.slipcard') : [].slice.call(wrap.querySelectorAll('.slipcard')).filter(function(x){ return x.getAttribute('data-sid') === FOCUS; })[0];
      if(fe){ FOCUSED = true; HLID = fe.getAttribute('data-sid'); HLT = Date.now() + 5000; setTimeout(function(){ fe.scrollIntoView({block: 'start', behavior: 'smooth'}); }, 60); setTimeout(render, 5100); } }
    [].slice.call(wrap.querySelectorAll('.slipcard')).forEach(function(x){ x.classList.toggle('hl', !!HLID && Date.now() < HLT && x.getAttribute('data-sid') === HLID); });
  }
  var FOCUS = (function(){ try { return new URLSearchParams(location.search).get('slip'); } catch(e){ return null; } })(), FOCUSED = false, HLID = null, HLT = 0;
  // ---- game drill-down (owner 11/1 Tuesday list): box score, play-by-play with scoring plays highlighted, your legs marked ----
  function myLegsFor(gid){ var out = {}; legs.concat(D.extra || []).forEach(function(l){ if(l.g !== gid || l.gl) return; var k = legKey(l); if(INSLIP[k] || STARS[k]) (out[norm(l.pl)] = out[norm(l.pl)] || []).push(l); }); return out; }
  function legMark(l){ var g = games[l.g], s = STATE[l.g] || {st: 'in'}; var r = live(l, g, s); var cls = r.status === 'hit' ? 'hit' : r.status === 'dead' ? 'dead' : 'open'; return '<span class="lm ' + cls + '">' + (r.status === 'hit' ? '✓ ' : r.status === 'dead' ? '✗ ' : '') + esc(legText(l).replace(l.pl, '').trim()) + (r.now ? ' · ' + esc(r.now) : '') + '</span>'; }
  function drillBox(js, gid){
    var mine = myLegsFor(gid), html = '';
    (js.boxscore && js.boxscore.players || []).forEach(function(tm){
      var ab = tm.team && tm.team.abbreviation || ''; html += '<h4>' + esc(tm.team && tm.team.displayName || ab) + '</h4>';
      (tm.statistics || []).forEach(function(cat){
        if(['passing', 'rushing', 'receiving', 'fumbles', 'interceptions', 'kicking', 'kickReturns', 'puntReturns', 'defensive'].indexOf(cat.name) < 0) return;
        var labs = cat.labels || []; if(!(cat.athletes || []).length) return;
        html += '<div class="bxw"><table class="bx"><thead><tr><th>' + esc(cat.text || cat.name) + '</th>' + labs.map(function(x){ return '<th>' + esc(x) + '</th>'; }).join('') + '</tr></thead><tbody>';
        (cat.athletes || []).forEach(function(a){ var nm = a.athlete && a.athlete.displayName || ''; var ml = mine[norm(nm)]; html += '<tr' + (ml ? ' class="mine"' : '') + '><td class="nm">' + esc(a.athlete && a.athlete.shortName || nm) + (ml ? '<div class="lms">' + ml.map(legMark).join('') + '</div>' : '') + '</td>' + (a.stats || []).map(function(v){ return '<td>' + esc(v) + '</td>'; }).join('') + '</tr>'; });
        html += '</tbody></table></div>';
      });
    });
    return html || '<p class="none">No box score yet.</p>';
  }
  function drillScoring(js){
    var sp = js.scoringPlays || []; if(!sp.length) return '<p class="none">No scoring plays yet.</p>';
    return '<table class="bx sc"><tbody>' + sp.map(function(p){ return '<tr><td class="q">Q' + (p.period && p.period.number) + '<small>' + esc(p.clock && p.clock.displayValue || '') + '</small></td><td class="tm">' + esc(p.team && p.team.abbreviation || '') + '<small>' + esc(p.type && p.type.text || '') + '</small></td><td class="tx">' + esc(p.text || '') + '</td><td class="scr">' + esc(p.awayScore) + '–' + esc(p.homeScore) + '</td></tr>'; }).join('') + '</tbody></table>';
  }
  function drillPlays(js, gid){
    var dr = (js.drives && js.drives.previous || []).slice(); if(js.drives && js.drives.current && (!dr.length || dr[dr.length-1].id !== js.drives.current.id)) dr.push(js.drives.current);
    if(!dr.length) return '<p class="none">No plays yet.</p>';
    var mine = myLegsFor(gid), names = Object.keys(mine).map(function(n){ var p = n.split(' '); return p.length > 1 ? p[p.length - 1] : n; });
    return dr.slice().reverse().map(function(d){
      var plays = (d.plays || []).slice().reverse();
      return '<div class="drv' + (/touchdown|field goal/i.test(d.result || d.displayResult || '') ? ' score' : '') + '"><div class="dh"><b>' + esc(d.team && d.team.abbreviation || '') + '</b> ' + esc(d.description || '') + ' <i>' + esc(d.displayResult || d.result || (d.isScore ? 'Score' : '')) + '</i></div>' +
        plays.map(function(p){ var t = p.text || ''; var hit = names.length && names.some(function(n){ return n.length > 2 && new RegExp('\\b' + n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i').test(t); });
          return '<div class="pl' + (p.scoringPlay ? ' td' : '') + (hit ? ' mine' : '') + '"><span class="dd">' + esc(p.start && p.start.shortDownDistanceText || (p.start && p.start.downDistanceText) || '') + '</span><span class="tx">' + (p.scoringPlay ? '<b class="sc">' + esc(p.type && p.type.text || 'Score') + '</b> ' : '') + esc(t) + '</span><span class="ck">' + esc(p.clock && p.clock.displayValue || '') + (p.period ? ' Q' + p.period.number : '') + '</span></div>'; }).join('') + '</div>';
    }).join('');
  }
  function drawDrill(){
    if(!DRILL) return; var gid = DRILL.gid, js = SUMM[gid], g = games[gid], s = STATE[gid] || {}; var box = $('#lvdrill');
    var tabs = ['box', 'plays', 'scoring'].map(function(t){ return '<button type="button" class="dtab' + (DRILL.tab === t ? ' on' : '') + '" data-t="' + t + '">' + ({box: 'Box score', plays: 'Play by play', scoring: 'Scoring'})[t] + '</button>'; }).join('');
    var body = !js ? '<p class="none">Loading from ESPN…</p>' : DRILL.tab === 'box' ? drillBox(js, gid) : DRILL.tab === 'plays' ? drillPlays(js, gid) : drillScoring(js);
    box.innerHTML = '<div class="dwrap"><div class="dhd"><div class="dt">' + badge(g.a, g.ca) + ' ' + g.a + ' <b>' + (s.sa != null ? s.sa : '–') + '–' + (s.sb != null ? s.sb : '–') + '</b> ' + g.b + ' ' + badge(g.b, g.cb) + '<small>' + (s.st === 'in' ? '<span class="lvtag">Live</span> ' + esc(s.det || '') : s.st === 'post' ? 'Final' : '') + ' · refreshes every 30 s</small></div><button type="button" class="dclose" aria-label="Close">×</button></div><div class="dtabs">' + tabs + '</div><div class="dbody">' + body + '</div></div>';
    box.hidden = false; document.body.classList.add('drillopen');
  }
  function openDrill(gid, tab){ DRILL = {gid: gid, tab: tab || (DRILL && DRILL.tab) || 'box'}; drawDrill(); if(!SUMM[gid]){ lastBox[gid] = 0; busy[gid] = false; pullBox(gid); } try { history.replaceState(null, '', '#box-' + gid); } catch(e){} }
  function closeDrill(){ DRILL = null; var box = $('#lvdrill'); box.hidden = true; box.innerHTML = ''; document.body.classList.remove('drillopen'); try { history.replaceState(null, '', location.pathname + location.search); } catch(e){} }
  document.addEventListener('click', function(ev){
    var b = ev.target.closest('.drill'); if(b){ openDrill(b.dataset.g); return; }
    if(ev.target.closest('.dclose') || (ev.target.id === 'lvdrill')){ closeDrill(); return; }
    var t = ev.target.closest('.dtab'); if(t && DRILL){ DRILL.tab = t.dataset.t; drawDrill(); } });
  document.addEventListener('keydown', function(ev){ if(ev.key === 'Escape' && DRILL) closeDrill(); });
  (function(){ var m = (location.hash || '').match(/^#box-([A-Z]{2,3}-[A-Z]{2,3})$/); if(m && games[m[1]]) setTimeout(function(){ openDrill(m[1]); }, 1200); })();
  // ---- polling: scoreboard (BSLive) + one summary call per live game every 30 s ----
  var busy = {};
  function pullBox(gid){
    var s = STATE[gid]; if(!s || !s.eid || busy[gid] || !window.fetch) return; if(lastBox[gid] && Date.now() - lastBox[gid] < 28000) return;
    busy[gid] = true;
    fetch('https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=' + s.eid, {cache: 'no-store'}).then(function(r){ return r.ok ? r.json() : null; }).then(function(js){
      busy[gid] = false; lastBox[gid] = Date.now(); if(!js) return; SUMM[gid] = js; if(DRILL && DRILL.gid === gid) drawDrill(); var pb = parseBox(js); Object.keys(pb.box).forEach(function(k){ BOX[k] = pb.box[k]; }); if(pb.first) FIRST[gid] = pb.first; render();
    }).catch(function(){ busy[gid] = false; lastBox[gid] = Date.now(); });
  }
  window.BSLive.start(D.games.map(function(g){ return {gid: g.gid, a: g.a, b: g.b, ko: g.ko, fin: g.fin}; }), function(m){
    STATE = m; render();
    order.forEach(function(gid){ var s = m[gid]; if(s && (s.st === 'in' || (s.st === 'post' && !lastBox[gid]))) pullBox(gid); });
  });
  $('#lv').addEventListener('click', function(ev){
    if(ev.target.id === 'logcopy' || ev.target.id === 'logcsv'){ var rows = window.__BSLOG || []; var hdr = ['week', 'game', 'player', 'market', 'line', 'fd_odds', 'model_pct', 'result', 'final_stat', 'slips'];
      if(ev.target.id === 'logcsv'){ var csv = [hdr].concat(rows).map(function(r){ return r.map(function(v){ return '"' + String(v).replace(/"/g, '""') + '"'; }).join(','); }).join('\n'); var a = document.createElement('a'); a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv); a.download = 'betsweep-week' + D.week + '-log.csv'; document.body.appendChild(a); a.click(); a.remove(); }
      else { var txt = 'BetSweep week ' + D.week + ' log\n' + rows.map(function(r){ return r[7] + ' · ' + r[2] + ' ' + r[3] + ' ' + r[4] + '+ (' + am(r[5]) + ', model ' + r[6] + '%)' + (r[8] ? ' · ' + r[8] : ''); }).join('\n'); (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(function(){ ev.target.textContent = 'Copied'; setTimeout(function(){ ev.target.textContent = 'Copy as text'; }, 1500); }).catch(function(){ prompt('Copy your log:', txt); }); }
      return; }
    var ad = ev.target.closest('.add'); if(ad){ openAddMenu(ad, ad.dataset.k); return; }
    var rm = ev.target.closest('.rm'); if(rm){ toggleIn(rm.dataset.sid, rm.dataset.k); return; }
    var dl = ev.target.closest('.slipdel'); if(dl){ var sx = slipById(dl.dataset.sid); if(!sx) return; if(!confirm((sx.builder ? 'Clear' : 'Delete') + ' "' + sx.name + '"?')) return; if(sx.builder){ SLIP = {}; saveBuilderSlip(); } else { SLIPS = SLIPS.filter(function(x){ return x.id !== sx.id; }); saveSlips(); } loadSlips(); render(); return; }
    var st = ev.target.closest('.star'); if(st){ var k = st.dataset.k; if(STARS[k]) delete STARS[k]; else STARS[k] = true; saveStars(); render(); return; }
    var h = ev.target.closest('.ghd2'); if(!h || h.classList.contains('static')) return; var gid = h.dataset.g; if(gid === '__log'){ OPEN.__log = OPEN.__log === false; render(); return; } var cur = h.getAttribute('aria-expanded') === 'true'; OPEN[gid] = !cur; render(); });   // owner 11/1 cleanup: the header knows its own state (empty live games and the Final group start folded)
  // slip name / ticket price / stake edits (change event: typing must not re-render under the cursor)
  $('#lv').addEventListener('change', function(ev){
    var t = ev.target, id = t.dataset.sid; if(!id) return; var sx = slipById(id); if(!sx) return;
    var set = function(k, v){ if(sx.builder){ BMETA[k] = v; saveBMeta(); } else { sx[k] = v; saveSlips(); } };
    if(t.classList.contains('slipname')) set('name', t.value.trim() || sx.name);
    if(t.classList.contains('slipodds')) set('odds', parseOdds(t.value));
    if(t.classList.contains('slipstake')){ var v = parseFloat(String(t.value).replace(/[^\d.]/g, '')); set('stake', v > 0 ? v : null); }
    loadSlips(); render(); });
  $('#lv').addEventListener('keydown', function(ev){ if(ev.key === 'Enter' && ev.target.dataset && ev.target.dataset.sid){ ev.target.blur(); } });
  // + menu: which slip to put the leg in
  var MENU = null; function closeMenu(){ if(MENU){ MENU.remove(); MENU = null; } }
  function openAddMenu(btn, k){
    closeMenu(); var l = LEGIDX[k]; var m = document.createElement('div'); m.className = 'addmenu';
    var h = '<small>' + esc(l ? legText(l) : k) + '</small>';
    h += '<button type="button" data-sid="builder" class="' + (SLIP[k] ? 'in' : '') + '">' + esc(BMETA.name || 'Builder slip') + '</button>';
    SLIPS.forEach(function(sx){ h += '<button type="button" data-sid="' + esc(sx.id) + '" class="' + (sx.keys.indexOf(k) >= 0 ? 'in' : '') + '">' + esc(sx.name) + '</button>'; });
    h += '<button type="button" data-sid="__new" class="new">+ New slip…</button>';
    m.innerHTML = h; document.body.appendChild(m); MENU = m;
    var r = btn.getBoundingClientRect(); var left = Math.min(r.left + window.scrollX, window.scrollX + window.innerWidth - m.offsetWidth - 8); m.style.left = Math.max(8, left) + 'px'; m.style.top = (r.bottom + window.scrollY + 4) + 'px';
    m.addEventListener('click', function(ev){ var b = ev.target.closest('button'); if(!b) return; var id = b.dataset.sid; closeMenu();
      if(id === '__new'){ var nm = prompt('Name this slip', 'Slip ' + (SLIPS.length + 1)); if(nm === null) return; var ns = newSlip(nm.trim(), [k]); render(); return; }
      toggleIn(id, k); }); }
  document.addEventListener('click', function(ev){ if(MENU && !ev.target.closest('.addmenu') && !ev.target.closest('.add')) closeMenu(); }, true);
  // ---- import: paste a slip (one leg per line) and match it to this week's legs ----
  var PLAYERS = {}; legs.concat(D.extra || []).forEach(function(l){ if(l.gl) return; var n = norm(l.pl); if(!PLAYERS[n]) PLAYERS[n] = {name: l.pl, tm: l.tm, g: l.g, legs: []}; PLAYERS[n].legs.push(l); });
  var TEAMS = {}; D.games.forEach(function(g){ [[g.a, g.na], [g.b, g.nb]].forEach(function(t){ TEAMS[t[0].toLowerCase()] = t[0]; TEAMS[norm(t[1])] = t[0]; }); });
  function matchLine(raw){
    var t = raw.replace(/[•·|\/@]/g, ' ').replace(/\bvs\.?\b/gi, ' ').replace(/\s+/g, ' ').trim(); if(!t) return null;
    var low = t.toLowerCase().replace(/\.(?!\d)/g, '').replace(/,/g, '').replace(/\s+(jr|sr|ii|iii|iv|v)\b/g, '').replace(/\s+/g, ' ').trim(); var oddsM = low.match(/(^|\s)([+-]\d{3,5})(\s|$)/); var odds = oddsM ? +oddsM[2] : null; low = low.replace(/(^|\s)[+-]\d{3,5}(\s|$)/g, ' ').trim();
    var m = null;
    if(/first (td|touchdown)|1st (td|touchdown)|first scorer/.test(low)) m = 'First TD';
    else if(/anytime|any time|to score|\btd\b|touchdown/.test(low)) m = 'Anytime TD';
    else if(/longest/.test(low)) m = 'Longest Reception';
    else if(/rec(eiving)? ?(yds|yards)|receiving/.test(low)) m = 'Receiving Yards';
    else if(/rush(ing)? ?(yds|yards)|rushing/.test(low)) m = 'Rushing Yards';
    else if(/pass(ing)? ?(yds|yards)|passing/.test(low)) m = 'Passing Yards';
    else if(/receptions?|\brecs?\b|catches/.test(low)) m = 'Receptions';
    else if(/\bover\b|\bunder\b|\bo ?\d|\bu ?\d|total/.test(low)) m = 'Total';
    else if(/moneyline|\bml\b|to win/.test(low)) m = 'Moneyline';
    else if(/[+-] ?\d+(\.\d+)?/.test(low)) m = 'Spread';
    var out = {raw: raw, m: m, odds: odds, leg: null, note: ''};
    if(!m){ out.note = 'could not tell the market'; return out; }
    if(m === 'Total' || m === 'Spread' || m === 'Moneyline'){
      var tm = null; Object.keys(TEAMS).sort(function(a, b){ return b.length - a.length; }).some(function(k){ if(new RegExp('(^|\\s)' + k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(\\s|$)').test(low)){ tm = TEAMS[k]; return true; } return false; });
      if(!tm){ out.note = 'no team found'; return out; }
      var cands = legs.concat(D.extra || []).filter(function(l){ return l.gl && l.m === m && (l.tm === tm || (m === 'Total' && l.opp === tm)); });
      if(m === 'Total'){ var side = /\bunder\b|\bu ?\d/.test(low) ? 'UNDER' : 'OVER'; cands = cands.filter(function(l){ return l.gl.side === side; }); var nT = low.match(/(\d+(\.\d+)?)/); if(!nT){ out.note = 'no total number'; return out; } out.leg = nearest(cands, +nT[1], out, 1.5); }
      else if(m === 'Spread'){ cands = cands.filter(function(l){ return l.gl.side === tm; }); var nS = low.match(/([+-]) ?(\d+(\.\d+)?)/); if(!nS){ out.note = 'no spread number'; return out; } out.leg = nearest(cands, (nS[1] === '-' ? -1 : 1) * +nS[2], out, 1.5); }
      else { cands = cands.filter(function(l){ return l.gl.side === tm; }); out.leg = cands[0] || null; if(!out.leg) out.note = 'no moneyline on the board'; }
      return out; }
    // player prop: last name as a whole word, first name / initial to break ties
    var words = low.split(' ');
    var hits = Object.keys(PLAYERS).filter(function(n){ var p = n.split(' '); var last = p[p.length - 1]; return last.length > 2 && words.indexOf(last) >= 0 && PLAYERS[n].legs.some(function(l){ return l.m === m; }); });
    if(hits.length > 1){ var h2 = hits.filter(function(n){ var f = n.split(' ')[0]; return words.indexOf(f) >= 0 || words.some(function(w){ return w.length <= 2 && f.charAt(0) === w.charAt(0); }); }); if(h2.length) hits = h2; }
    if(!hits.length){ out.note = 'no player with that market on this week\'s board'; return out; }
    if(hits.length > 1){ out.note = 'ambiguous: ' + hits.map(function(n){ return PLAYERS[n].name; }).join(' / '); return out; }
    var P = PLAYERS[hits[0]]; var cands2 = P.legs.filter(function(l){ return l.m === m; });
    if(m === 'Anytime TD' || m === 'First TD'){ out.leg = cands2[0]; return out; }
    var nm = low.replace(new RegExp(hits[0].split(' ').join('|'), 'g'), ' ').match(/(\d+(\.\d+)?)/); if(!nm){ out.note = 'no line number'; return out; }
    out.leg = nearest(cands2, +nm[1], out, m === 'Receptions' ? 1 : 10); return out; }
  function nearest(cands, want, out, tol){
    if(!cands.length){ out.note = 'not priced on the board'; return null; }
    var ex = cands.filter(function(l){ return Math.abs(l.ln - want) < 0.01; }); if(ex.length) return ex[0];
    var best = cands.slice().sort(function(a, b){ return Math.abs(a.ln - want) - Math.abs(b.ln - want); })[0];
    if(Math.abs(best.ln - want) > tol){ out.note = 'line ' + want + ' not on the board (closest ' + best.ln + ')'; return null; }
    out.note = 'closest line on the board: ' + best.ln + ' (you had ' + want + ')'; return best; }
  var IMPM = [];
  function runImport(){ var txt = $('#imptxt').value; IMPM = txt.split(/\n/).map(matchLine).filter(Boolean);
    var ok = IMPM.filter(function(x){ return x.leg; });
    $('#implist').innerHTML = IMPM.length ? IMPM.map(function(x){ var cls = x.leg ? (x.note ? 'near' : 'ok') : 'no'; return '<li class="' + cls + '"><i>' + (x.leg ? (x.note ? '≈' : '✓') : '✗') + '</i><span>' + (x.leg ? '<b>' + esc(legText(x.leg)) + '</b> <small>' + esc(x.leg.tm) + ' · FD ' + am(x.leg.o) + ' · model ' + pc(x.leg.p) + '</small>' : '<s>' + esc(x.raw) + '</s>') + (x.note ? '<small>' + esc(x.note) + '</small>' : '') + '</span></li>'; }).join('') : '';
    $('#impgo').disabled = !ok.length; $('#impgo').textContent = ok.length ? 'Track ' + ok.length + ' leg' + (ok.length > 1 ? 's' : '') + ' as a slip' : 'Nothing matched yet';
  }
  $('#impopen').addEventListener('click', function(){ var w = $('#impwrap'); w.hidden = !w.hidden; if(!w.hidden) $('#imptxt').focus(); });
  $('#impnew').addEventListener('click', function(){ var nm = prompt('Name this slip', 'Slip ' + (SLIPS.length + 1)); if(nm === null) return; newSlip(nm.trim(), []); render(); window.scrollTo({top: 0, behavior: 'smooth'}); });
  $('#impmatch').addEventListener('click', runImport); $('#imptxt').addEventListener('input', function(){ clearTimeout(window.__impT); window.__impT = setTimeout(runImport, 400); });
  $('#impgo').addEventListener('click', function(){ var ok = IMPM.filter(function(x){ return x.leg; }); if(!ok.length) return; var keys = []; ok.forEach(function(x){ var k = legKey(x.leg); if(keys.indexOf(k) < 0) keys.push(k); });
    var stake = parseFloat(String($('#impstake').value).replace(/[^\d.]/g, ''));
    newSlip(($('#impname').value || '').trim() || ('Imported slip ' + (SLIPS.length + 1)), keys, parseOdds($('#impodds').value), stake > 0 ? stake : null);
    $('#imptxt').value = ''; $('#impname').value = ''; $('#impodds').value = ''; $('#impstake').value = ''; $('#implist').innerHTML = ''; $('#impgo').disabled = true; $('#impwrap').hidden = true; render(); window.scrollTo({top: 0, behavior: 'smooth'}); });
  $('#lvrefresh').addEventListener('click', function(){ lastBox = {}; window.BSLive.refresh && window.BSLive.refresh(); order.forEach(function(gid){ var s = STATE[gid]; if(s && s.st !== 'pre') pullBox(gid); }); render(); });
  window.addEventListener('pageshow', function(e){ if(e.persisted){ loadSlips(); render(); } });   // owner 10/28: same slip on every page
  document.addEventListener('visibilitychange', function(){ if(document.visibilityState === 'visible'){ loadSlips(); render(); } });
  document.addEventListener('bs-account', function(e){ if(e.detail && e.detail.changed){ loadSlips(); render(); } });
  window.addEventListener('storage', function(e){ if(e.key === 'bs_slipk_w' + D.week || e.key === SLKEY || e.key === SKEY){ if(e.key === SKEY){ STARS = {}; try { (JSON.parse(e.newValue || '[]')).forEach(function(k){ STARS[k] = true; }); } catch(x){} } render(); } });
  document.querySelectorAll('#lvmode button').forEach(function(b){ b.addEventListener('click', function(){ document.querySelectorAll('#lvmode button').forEach(function(x){ x.classList.remove('on'); }); b.classList.add('on'); mode = b.dataset.v; render(); }); });
  render();
})();
"""
stamp = datetime.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p")
body = f'''<div class="lv">
 <div class="lvbar lvtools"><span class="seg" id="lvmode"><button type="button" class="on" data-v="likes">Picks</button><button type="button" data-v="all">Every leg</button></span><button type="button" class="rfr" id="impnew">+ New slip</button><button type="button" class="rfr" id="impopen">Import</button><button type="button" class="rfr" id="lvrefresh" title="Pull the scores and box scores again now">↻</button><span class="upd" id="upd"></span></div>
 <details class="lvhelp"><summary>How this page works</summary><p><b>Picks</b> shows your slip, anything you pinned (☆), the best parlay legs and the model's clearest edges for each game; Every leg shows the whole board. During a game each leg shows the live stat against its line and the model's chance from here. Pin the legs you bet and "My week" keeps the running record you can copy or download when the games are done.</p><p><b>Slips:</b> every slip here is tracked live as one parlay. Tap <b>+</b> on any leg to put it in a slip, build a new one, or paste a bet you already placed and the page matches it to this week's legs.</p><p class="lvnote2">Live score, clock, possession and box scores come from ESPN's public scoreboard, refreshed every 30 seconds while a game is on. "From here" pushes the pregame model forward with the time left: yardage and reception legs assume the rest of the game runs at the pregame rate with the pregame spread of outcomes; a touchdown leg keeps the pregame scoring rate for the minutes left; first-TD legs settle on the game's first touchdown; game lines use the same margin and total spreads as the pregame price. After halftime the rest-of-game rates tilt with the score (a team down 7+ throws more, a team up 10+ runs more) and a team in the red zone lifts its players' touchdown chances. None of it knows about an in-game injury, a blowout that benches a starter, or a team sitting on the ball - read the situation line before you trust the number. ☆ pins a leg to the top of its game (saved on this device); + puts a leg in a slip; every slip (the builder slip, slips you build here, slips you import) is tracked at the top of the page as one parlay with the model's chance from here, the ticket price or the price the legs imply, and a fair price from here; slips live on this device only; rows flash when their status changes; "on pace / behind pace" compares the current stat to the share of the game played.</p></details>
 <div class="imp" id="impwrap" hidden><h3>Import a slip</h3><p>One leg per line, the way you'd say it or the way FanDuel shows it: <em>Bijan Robinson 60+ rushing yards</em> · <em>Drake London anytime TD</em> · <em>Commanders -3.5</em> · <em>Over 48.5 SF/WAS</em> · <em>Kittle 4+ receptions</em>. Lines are matched to this week's board; a leg at a line the board doesn't carry is matched to the closest one and marked ≈.</p>
  <textarea id="imptxt" placeholder="Paste or type your legs here…"></textarea>
  <div class="row"><input type="text" class="nm" id="impname" placeholder="Slip name (optional)"><input type="text" class="od" id="impodds" inputmode="numeric" placeholder="+593"><input type="text" class="od" id="impstake" inputmode="decimal" placeholder="stake $"><button type="button" class="rfr" id="impmatch">Match</button><button type="button" class="rfr go" id="impgo" disabled>Nothing matched yet</button></div>
  <ul id="implist"></ul></div>
 <div id="lv"></div>
 <div id="lvdrill" hidden></div>

</div>
<script>window.__LV = {json.dumps(LD, separators=(",", ":"))};</script>
<script>{LIVE.LIVE_JS}</script>
<script>{JS}</script>'''
page = (open(os.path.join(HERE, "template.html")).read()
        .replace("<title>BetSweep Matchup Boards</title>", "<title>BetSweep Live</title>")
        .replace("<h1>Week {{WEEK}} · <b>Matchup Boards</b></h1>", "<h1>Week {{WEEK}} · <b>Live</b></h1>")
        .replace("</style>", CSS + "\n</style>", 1)
        .replace("{{DESC}}", f"What the model likes that has not happened yet. Every tracked Week {WEEK} leg against the live box score, with the model's chance from here. Built {stamp} CT.")
        .replace("{{NAV}}", '<a href="https://claude.ai/artifact/FQVqm3BhG4BfMPd63tRQRa">← Parlay builder</a>').replace("{{CARDS}}", body)
        .replace("{{LOGO}}", LOGO).replace("{{BANNER}}", BANNER).replace("{{WEEK}}", str(WEEK)).replace("{{STAMP}}", stamp).replace("{{ARCHIVE}}", ""))
page = re.sub(r'<div class="key">.*?</div>\n', '', page, count=1, flags=re.S)
page = page.replace('<div class="grid">', '<div class="grid" style="display:block">', 1)
# the boards' own slip/lock scripts expect board markup; strip them from this page (keep styles)
page = re.sub(r'<script>window.__BSL = /\*SLIPDATA\*/null;</script>\n<script>/\*LIVEJS\*/</script>', '', page)
page = re.sub(r'<script>\n\(function\(\)\{\n  // ---- page betslip.*?\}\)\(\);\n</script>', '', page, flags=re.S)
out = os.path.join(OUT, "live.html"); open(out, "w").write(page)
print(f"wrote {out}: {len(slim)} legs, {len(games)} games, week {WEEK}")
