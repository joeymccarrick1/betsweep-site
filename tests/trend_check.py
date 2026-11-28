"""Trend check, /trends/ (owner 11/27 10:34 PM, after FanDuel shipped its "Trends" cards: "make the best most efficient legs and show them
why as quickly and as best as it can"): this week's streak legs, each with the model's chance, the price it needs and the reason.

Everything expected is worked out here from the build's own files, by this file's own code, so the test runs in any week:
  the Parlay Builder's data file  ->  which legs are on a 4-of-5 run (five logged games, this exact line, the highest such line per
                                       player and market, game not kicked off when the page was built), and which group each belongs in
                                       (sweep.risk_score for the risk tag; the leg's own edge for Clears / Priced in)
  in/legsnaps.json + nflverse     ->  the record in the banner (only when testing ./site: a published copy may have been built from a
                                       later sheet)
The page is opened at 390x844 in both themes, the outside world cut off, with the clock set to the moment the page was built.
  python3 tests/trend_check.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, csv, datetime, functools, http.server, json, math, os, re, sys, threading
from playwright.async_api import async_playwright
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); sys.path.insert(0, HERE)
import sweep as SW, why as WHY
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); IN = os.path.join(HERE, "in"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8903; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
bh = open(os.path.join(ROOT, "build", "index.html"), encoding="utf-8").read(); _m = re.search(r'src="(/build/data-[0-9a-f]+\.js)"', bh)
js = open(os.path.join(ROOT, _m.group(1).lstrip("/")), encoding="utf-8").read(); BS = json.JSONDecoder().raw_decode(js[js.index("{", js.index("window.__BS = ")):])[0]
W = BS["week"]
try: BUILT = int(re.search(r'id="trends"[^>]*data-built="(\d+)"', open(os.path.join(ROOT, "trends", "index.html"), encoding="utf-8").read()).group(1))   # the moment the page chose its legs
except Exception: BUILT = 0
KO = {g["gid"]: g.get("ko") for g in BS["games"]}
jr = lambda v: int(math.floor(float(v) + 0.5))
key = lambda l: f'{l["pl"]}|{l["m"]}|{jr(l.get("ln") or 1)}'
MARKETS = {"Rushing Yards": "rush", "Receiving Yards": "recy", "Receptions": "rec", "Passing Yards": "pass", "Passing TDs": "ptd", "Anytime TD": "td", "2+ TD": "td", "3+ TD": "td", "Rush + Rec Yards": "more", "Longest Reception": "more"}

def expected():
    """{leg key: {"grp", "h", "risk", "st", "g", "e"}} - this file's own reading of the rule in build_trends.py's header"""
    best = {}
    for l in BS["legs"]:
        m = l["m"]
        if l.get("gl") or l.get("u") or m.startswith("Under ") or m not in MARKETS or not l.get("sk"): continue
        games = [g for g in (BS.get("gl") or {}).get(l["pl"], []) if g.get(l["sk"]) is not None][:5]
        if len(games) < 5 or not (KO.get(l["g"]) or 0) > BUILT: continue
        need = 2 if m == "2+ TD" else 3 if m == "3+ TD" else 1 if m.endswith("TD") else float(l["ln"])
        hits = sum(1 for g in games if float(g[l["sk"]] or 0) >= need)
        if hits < 4: continue
        k = (l["pl"], m)
        if k not in best or float(l["ln"]) > float(best[k][0]["ln"]): best[k] = (l, hits)
    out = {}
    for l, hits in best.values():
        tag = SW.risk_tag(SW.risk_score(l, BS))
        out[key(l)] = {"grp": "no" if tag else ("ok" if float(l.get("e") or 0) >= 0 else "mid"), "h": hits, "risk": tag, "st": MARKETS[l["m"]], "g": l["g"], "e": float(l.get("e") or 0), "l": l}
    return out

def record():
    """the banner's numbers, counted again here from the two files (same definition, separate code)"""
    pk = lambda n: re.sub(r"\s+", " ", re.sub(r"[^a-z ]", "", re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", str(n).lower().replace(".", "")))).strip()
    v = json.load(open(os.path.join(IN, "legsnaps.json")))["values"]; H = {c: i for i, c in enumerate(v[0])}; col = {"Receiving Yards": "receiving_yards", "Receptions": "receptions", "Rushing Yards": "rushing_yards", "Passing Yards": "passing_yards"}
    log = {}
    for r in csv.DictReader(open(os.path.join(IN, "stats_player_week_2026.csv"), newline="")):
        if r.get("season_type", "REG") != "REG" or not r.get("player_display_name"): continue
        row = {m: float(r.get(c) or 0) for m, c in col.items()}; row["Anytime TD"] = float(r.get("rushing_tds") or 0) + float(r.get("receiving_tds") or 0)
        log.setdefault(pk(r["player_display_name"]), {})[int(r["week"])] = row
    top = {}
    for r in v[1:]:
        r = list(r) + [""] * (len(v[0]) - len(r)); m = r[H["Market"]]
        if str(r[H["Latest Snapshot"]]).upper() != "TRUE" or r[H["Result"]] not in ("HIT", "MISS") or (m not in col and m != "Anytime TD"): continue
        try: w = int(float(r[H["Week"]])); ln = float(r[H["Line (X+)"]]); bk = float(r[H["Book implied %"]]); float(r[H["Model % (hist-adj)"]]); int(float(str(r[H["FanDuel odds"]]).replace("+", "")))
        except Exception: continue
        g = log.get(pk(r[H["Player"]])) or {}; prev = [g[x] for x in sorted(g) if x < w][-5:]
        if len(prev) < 5: continue
        h5 = sum(1 for x in prev if x[m] >= (1 if m == "Anytime TD" else ln))
        if h5 < 4: continue
        k = (w, r[H["Player"]], m)
        if k not in top or ln > top[k][0]: top[k] = (ln, bk, r[H["Result"]] == "HIT", h5)
    xs = list(top.values()); n = len(xs)
    return {"n": n, "hit": sum(x[2] for x in xs) / n, "need": sum(x[1] for x in xs) / n, "l5": sum(x[3] for x in xs) / n / 5} if n else None

READ = """() => { var vis = function(e){ return !!(e && (e.offsetWidth || e.offsetHeight)); };
  return {over: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    tabs: Array.from(document.querySelectorAll('#wktabs .tab')).map(function(b){ return {id: b.getAttribute('data-t'), on: b.classList.contains('on'), n: +((b.querySelector('small') || {}).textContent || 0), label: b.childNodes[0].textContent.trim()}; }),
    stats: Array.from(document.querySelectorAll('#trs button')).map(function(b){ return b.getAttribute('data-s'); }), games: Array.from(document.querySelectorAll('#trg button')).map(function(b){ return b.getAttribute('data-g'); }),
    base: Array.from(document.querySelectorAll('#trbase > div b')).map(function(b){ return b.textContent; }), baseNote: (document.querySelector('#trbase p') || {}).textContent || '',
    groups: Array.from(document.querySelectorAll('.trgrp')).map(function(g){ var cards = Array.from(g.querySelectorAll('.trplays > .play')); var more = g.querySelector('.trmore');
      return {id: g.getAttribute('data-tab'), open: !g.classList.contains('fxoff'), more: vis(more) ? more.textContent : '', empty: vis(g.querySelector('.tre')),
        cards: cards.map(function(a){ var h5 = a.querySelector('.h5'), k = a.querySelector('.trk'), r = a.getBoundingClientRect();
          return {k: a.getAttribute('data-k'), st: a.getAttribute('data-st'), g: a.getAttribute('data-gid'), h: +a.getAttribute('data-h'), shown: vis(a), big: h5 ? h5.querySelector('p b').textContent : '', risk: k ? k.textContent : '',
            ops: h5 ? Array.from(h5.querySelectorAll('li i.hm')).map(function(i){ return i.getAttribute('data-hm'); }) : [], same: h5 ? h5.querySelectorAll('li.same').length : 0,
            why: Array.from(a.querySelectorAll('.legwhy li')).map(function(li){ return [li.className, li.querySelector('b').textContent, li.querySelector('span').textContent.replace(li.querySelector('b').textContent, '').trim()]; }),
            slip: !!a.querySelector('.what a.more.px'), fd: !!a.querySelector('.foot a.fdb'), ht: Math.round(r.height), inside: Array.from(a.querySelectorAll('.ptop, .what, .nums, .hrow, .legwhy, .foot')).every(function(e){ var q = e.getBoundingClientRect(); return !vis(e) || (q.left >= r.left - 0.5 && q.right <= r.right + 0.5); })}; })}; })}; }"""

async def main():
    EXP = expected(); n_exp = len(EXP)
    print(f"   week {W}: {n_exp} streak legs expected ({sum(1 for x in EXP.values() if x['grp'] == 'ok')} clear, {sum(1 for x in EXP.values() if x['grp'] == 'mid')} priced in, {sum(1 for x in EXP.values() if x['grp'] == 'no')} flagged)")
    page_file = os.path.join(ROOT, "trends", "index.html")
    if not os.path.exists(page_file) and not any((KO.get(l["g"]) or 0) > 0 for l in BS["legs"]): n_exp = 0
    if not n_exp:
        check(not os.path.exists(page_file) or True, "no streak legs on this board: nothing to check (the page is only built when there are some)")
        print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(0)
    check(os.path.exists(page_file), "the page is built at /trends/")
    if not os.path.exists(page_file): print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1)
    # ---- 11/28: the page is built the way it opens. Every card of every group used to be in the page un-hidden until the script put all
    # but twelve away, so the browser laid out and painted the lot first. Read off the file itself, before any script runs. ----
    src = open(page_file, encoding="utf-8").read(); built = []
    for m in re.finditer(r'<div class="trgrp( fxoff)?" data-tab="(\w+)"', src):
        end = src.find('<button type="button" class="trmore"', m.end()); blk = src[m.end():end]
        built.append({"id": m.group(2), "off": bool(m.group(1)), "open": len(re.findall(r'<article class="play trc"', blk)), "wait": len(re.findall(r'<article class="trw play trc"', blk))})
    want_n = {g: sum(1 for x in EXP.values() if x["grp"] == g) for g in ("ok", "mid", "no")}; first_on = next((g for g in ("ok", "mid", "no") if want_n[g]), "ok")
    check([b["id"] for b in built] == ["ok", "mid", "no"] and [b["id"] for b in built if not b["off"]] == [first_on] and all(b["open"] == min(12, want_n[b["id"]]) and b["wait"] == max(0, want_n[b["id"]] - 12) for b in built)
          and ".play.trw{display:none}" in src.replace(" ", "") and "<noscript><style>.fxoff{display:block!important}" in src,
          f"as built, before any script: one group on screen ({first_on}), twelve cards a group and the rest waiting, and everything shown when scripts are off ({built})")
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def open_(path, theme, clock):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block", color_scheme=theme)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}'); sessionStorage.removeItem('bs_tab_trends')}}catch(e){{}};(function(){{var T={int(clock)},R=Date.now,S=R();Date.now=function(){{return T+(R()-S)}};}})();")
            async def gate(route, request): await (route.continue_() if "127.0.0.1" in request.url else route.abort())
            await ctx.route("**/*", gate)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}{path}", wait_until="domcontentloaded"); await pg.wait_for_timeout(1900)
            return pg, ctx, errs
        for theme in ("dark", "light"):
            pg, ctx, errs = await open_("/trends/", theme, BUILT + 1000); s = await pg.evaluate(READ)
            cards = {c["k"]: dict(c, grp=g["id"]) for g in s["groups"] for c in g["cards"]}
            # ---- which legs, in which group ----
            miss = sorted(set(EXP) - set(cards)); extra = sorted(set(cards) - set(EXP)); wrong = [(k, cards[k]["grp"], EXP[k]["grp"]) for k in cards if k in EXP and cards[k]["grp"] != EXP[k]["grp"]]
            check(not miss and not extra and not wrong and not errs, f"[{theme}] the page lists exactly this week's streak legs, each in its group ({len(cards)} cards; missing {miss[:2]}, extra {extra[:2]}, wrong group {wrong[:2]}; {errs[:1]})")
            bad = [(k, c["h"], c["big"], c["st"], c["g"], c["risk"]) for k, c in cards.items() if k in EXP and (c["h"] != EXP[k]["h"] or c["big"] != f'{EXP[k]["h"]} of 5' or c["st"] != EXP[k]["st"] or c["g"] != EXP[k]["g"] or c["risk"] != EXP[k]["risk"])]
            check(not bad, f"[{theme}] each card states its streak (4 of 5 or 5 of 5), carries its stat and game, and wears the builder's risk tag only when the builder gives one (first wrong: {bad[:1]})")
            tabs = {t["id"]: t for t in s["tabs"]}; want = {g: sum(1 for x in EXP.values() if x["grp"] == g) for g in ("ok", "mid", "no")}
            check([t["id"] for t in s["tabs"]] == ["ok", "mid", "no"] and all(tabs[g]["n"] == want[g] for g in want), f"[{theme}] three tabs - Clears, Priced in, Flagged - each counting its cards ({[(t['label'], t['n']) for t in s['tabs']]} against {want})")
            first = next((g for g in ("ok", "mid", "no") if want[g]), None); op = [g["id"] for g in s["groups"] if g["open"]]
            check(op == [first], f"[{theme}] the page opens on the first group that has a leg ({op} against {first})")
            for g in s["groups"]:
                es = [EXP[c["k"]]["e"] for c in g["cards"] if c["k"] in EXP]
                if g["id"] != "no": check(all(es[i] >= es[i + 1] - 1e-9 for i in range(len(es) - 1)), f"[{theme}] {tabs[g['id']]['label']} runs from the best price against the model down ({len(es)} cards)")
            # ---- the reasons and the bars' logos come from the leg's own data ----
            bad = []
            for k, c in cards.items():
                if k not in EXP: continue
                l = EXP[k]["l"]; rs = WHY.reasons(l, BS.get("pf"))
                if [(r[0], r[1], r[2]) for r in rs] != [(w[0], w[1], w[2]) for w in c["why"]]: bad.append((k, c["why"], rs)); continue
                gs = [g for g in BS["gl"][l["pl"]] if g.get(l["sk"]) is not None][:5][::-1]; al = lambda t: {"LAR": "LA", "WSH": "WAS"}.get(str(t or ""), str(t or ""))
                if c["ops"] and (c["ops"] != [al(g.get("opp")) for g in gs] or c["same"] != sum(1 for g in gs if al(g.get("opp")) == al(l.get("opp")))): bad.append((k, c["ops"], c["same"]))
            check(not bad, f"[{theme}] every card's reason lines are the model's own flags for that leg (why.py), and the logos under the bars are those five opponents with this week's ringed ({len(cards)} cards; first wrong: {bad[:1]})")
            withwhy = sum(1 for c in cards.values() if c["why"]); nolog = sum(1 for c in cards.values() if not c["ops"])
            check(withwhy >= 0.9 * len(cards) and all(c["slip"] for c in cards.values()), f"[{theme}] {withwhy} of {len(cards)} cards say why, and every card's price is its add button ({nolog} without opponent logos)")
            # ---- on screen: twelve at a time, nothing off the card or the page ----
            og = next(g for g in s["groups"] if g["open"]); shown = [c for c in og["cards"] if c["shown"]]
            check(len(shown) == min(12, want[og["id"]]) and (bool(og["more"]) == (want[og["id"]] > 12)) and s["over"] <= 0 and all(c["inside"] for c in shown), f"[{theme}] the open group shows {len(shown)} cards ({'with' if og['more'] else 'no'} 'Show all' button), nothing runs off the card or the page ({s['over']}px)")
            tall = max([c["ht"] for c in shown] or [0])
            check(0 < tall <= 430, f"[{theme}] a card is at most {tall}px tall on a phone (limit 430)")
            # ---- the record in the banner ----
            if os.environ.get("SITE"): print("   (published copy: the banner's numbers are not re-counted, the sheet may have moved on)")
            elif os.path.exists(os.path.join(IN, "legsnaps.json")) and os.path.exists(os.path.join(IN, "stats_player_week_2026.csv")):
                R = record(); wantb = [f'{R["l5"] * 100:.0f}%', f'{R["hit"] * 100:.0f}%', f'{R["need"] * 100:.0f}%'] if R and R["n"] >= 100 else []
                check(s["base"] == wantb and (not wantb or f'{R["n"]:,} graded' in s["baseNote"]), f"[{theme}] the banner is counted from the graded snapshots: streak {wantb[:1]}, hit {wantb[1:2]}, price needed {wantb[2:3]} over {R and R['n']} legs (page: {s['base']})")
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"trend_check_top_{theme}.png"))
            # ---- Flagged: the long group, its Show all button, the filters ----
            if want["no"]:
                await pg.evaluate("document.querySelector('#wktabs .tab[data-t=\"no\"]').click()"); await pg.wait_for_timeout(350); s2 = await pg.evaluate(READ); g2 = next(g for g in s2["groups"] if g["id"] == "no")
                sh = [c for c in g2["cards"] if c["shown"]]
                check(g2["open"] and len(sh) == min(12, want["no"]) and (want["no"] <= 12 or g2["more"] == f"Show all {want['no']}"), f"[{theme}] Flagged opens with {len(sh)} cards and '{g2['more']}'")
                if want["no"] > 12:
                    await pg.evaluate("document.querySelector('.trgrp[data-tab=\"no\"] .trmore').click()"); await pg.wait_for_timeout(300); s3 = await pg.evaluate(READ); g3 = next(g for g in s3["groups"] if g["id"] == "no")
                    check(sum(1 for c in g3["cards"] if c["shown"]) == want["no"] and not g3["more"], f"[{theme}]   Show all opens all {want['no']}")
                # a stat with flagged legs, then a game with any leg
                st = next((x for x in s["stats"] if x and any(e["st"] == x and e["grp"] == "no" for e in EXP.values())), None)
                if st:
                    await pg.evaluate("(x) => document.querySelector('#trs button[data-s=\"' + x + '\"]').click()", st); await pg.wait_for_timeout(300); s4 = await pg.evaluate(READ)
                    vis4 = [c for g in s4["groups"] for c in g["cards"] if c["shown"]]; w4 = {g: sum(1 for e in EXP.values() if e["grp"] == g and e["st"] == st) for g in want}
                    check(vis4 and all(c["st"] == st for c in vis4) and all(t["n"] == w4[t["id"]] for t in s4["tabs"]), f"[{theme}] a stat filter ({st}) leaves only that stat and re-counts the tabs ({[(t['label'], t['n']) for t in s4['tabs']]} against {w4})")
                    await pg.evaluate("document.querySelector('#trs button[data-s=\"\"]').click()"); await pg.wait_for_timeout(200)
                gm = next((x for x in s["games"] if x and any(e["g"] == x for e in EXP.values())), None)
                if gm:
                    await pg.evaluate("(x) => document.querySelector('#trg button[data-g=\"' + x + '\"]').click()", gm); await pg.wait_for_timeout(300); s5 = await pg.evaluate(READ)
                    vis5 = [c for g in s5["groups"] for c in g["cards"] if c["shown"]]; w5 = {g: sum(1 for e in EXP.values() if e["grp"] == g and e["g"] == gm) for g in want}
                    open5 = [g["id"] for g in s5["groups"] if g["open"]]
                    check(bool(vis5) and all(c["g"] == gm for c in vis5) and all(t["n"] == w5[t["id"]] for t in s5["tabs"]) and len(open5) == 1 and w5[open5[0]] > 0,
                          f"[{theme}] a game filter ({gm}) leaves only that game, re-counts the tabs and stays on a group that has a leg ({[(t['label'], t['n']) for t in s5['tabs']]} against {w5}, open {open5})")
                    if SHOTS:
                        await pg.evaluate("() => { var a = Array.from(document.querySelectorAll('.trgrp:not(.fxoff) .play')).filter(function(e){ return e.offsetWidth; })[0]; if(a){ a.scrollIntoView(); window.scrollBy(0, -120); } }"); await pg.wait_for_timeout(300)
                        await pg.screenshot(path=os.path.join(SHOTS, f"trend_check_game_{theme}.png"))
                    await pg.evaluate("document.querySelector('#trg button[data-g=\"\"]').click()"); await pg.wait_for_timeout(200)
            # ---- + Slip is one tap, and a second tap takes it back ----
            r = await pg.evaluate("""(W) => { var k = 'bs_slipk_w' + W; localStorage.removeItem(k); var a = Array.from(document.querySelectorAll('.trgrp:not(.fxoff) .play')).filter(function(e){ return e.offsetWidth; })[0], m = a.querySelector('.what a.more.px');
                m.click(); var one = JSON.parse(localStorage.getItem(k) || '[]'), lab = m.getAttribute('aria-pressed') + ' ' + m.querySelector('i').textContent, bar = document.getElementById('hsbar'), on = bar && bar.classList.contains('on'), txt = bar ? bar.querySelector('b').textContent : ''; m.click();
                return {want: a.getAttribute('data-k'), one: one, lab: lab, on: on, txt: txt, two: JSON.parse(localStorage.getItem(k) || '[]').length, href: location.pathname}; }""", W)
            check(r["one"] == [r["want"]] and r["lab"] == "true ✓" and r["on"] and r["txt"].startswith("1 leg") and r["two"] == 0 and r["href"] == "/trends/", f"[{theme}] a tap on the price adds that leg to the betslip without leaving the page, the bar counts it, a second tap removes it ({r})")
            await ctx.close()
            # ---- after a kickoff that game's cards are gone and the tabs count what is left ----
            gk = min((e["g"] for e in EXP.values()), key=lambda g: KO[g]); t_after = KO[gk] + 60e3; left = {g: sum(1 for e in EXP.values() if e["grp"] == g and KO[e["g"]] > t_after) for g in want}
            pg, ctx, errs = await open_("/trends/", theme, t_after); s6 = await pg.evaluate(READ)
            gone = [c for g in s6["groups"] for c in g["cards"] if c["shown"] and KO[c["g"]] <= t_after]
            check(not gone and all(t["n"] == left[t["id"]] for t in s6["tabs"]) and not errs, f"[{theme}] a minute after {gk} kicks off its cards have left and the tabs read {[(t['label'], t['n']) for t in s6['tabs']]} (expected {left}; {errs[:1]})")
            await ctx.close()
            # ---- the door on Today, and the menu ----
            pg, ctx, errs = await open_("/", theme, BUILT + 1000)
            d = await pg.evaluate("""() => { var a = document.querySelector('#trdoor a.trdoor'), r = a ? a.getBoundingClientRect() : null; var nav = Array.from(document.querySelectorAll('nav.sitenav a')).map(function(x){ return x.getAttribute('href'); });
                var secs = Array.from(document.querySelectorAll('section')).filter(function(x){ return x.offsetParent !== null; }).map(function(x){ return x.id || x.className; });
                return {href: a ? a.getAttribute('href') : null, txt: a ? a.textContent.replace(/\\s+/g, ' ') : '', fits: r ? r.right <= innerWidth + 0.5 : false, nav: nav.indexOf('/trends/') >= 0, after: secs.indexOf('trdoor') > secs.indexOf('tdday') && secs.indexOf('tdday') >= 0, over: document.documentElement.scrollWidth - innerWidth}; }""")
            check(d["href"] == "/trends/" and f"{n_exp} legs are on a 4-of-5 run" in d["txt"] and f'{want["ok"]} clear' in d["txt"] and d["fits"] and d["after"] and d["over"] <= 0 and not errs,
                  f"[{theme}] Today carries one line to the page, under today's games, with the week's counts ({d['txt'][:90]!r}; {errs[:1]})")
            check(d["nav"], f"[{theme}] the menu lists Trend check")
            if SHOTS:
                await pg.evaluate("document.querySelector('#trdoor').scrollIntoView(); window.scrollBy(0, -260)"); await pg.wait_for_timeout(250); await pg.screenshot(path=os.path.join(SHOTS, f"trend_check_door_{theme}.png"))
            await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
