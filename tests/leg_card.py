"""The leg card's three pictures (11/27 night; owner: "I love all 8. Let's do it all"): a jersey number beside the player, Model vs FanDuel
as one bar, and his last five games against the leg's line. Also team logos on News desk notes and five bars on the builder's best-legs
cards.
11/27 late (owner 10:34 PM, after FanDuel's "Trends" cards: "show them why as quickly and as best as it can"): the opponent's logo under
each bar with this week's opponent ringed and said in words, and the leg's strongest reason for and against, a line each (why.py).

Every expectation is worked out from the build's own files, so the test runs in any week:
  the Parlay Builder's data file (legs, each player's game log)  ->  which bars a card must draw and how many are green
  in/roster_2026.csv (through helmets.num)                        ->  the number on the shirt, or no shirt
The pages are opened at 390x844 in both themes with the outside world cut off.
  python3 tests/leg_card.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, math, os, re, sys, threading, urllib.parse
from playwright.async_api import async_playwright
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); sys.path.insert(0, HERE)
import helmets as HM, why as WHY
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); IN = os.path.join(HERE, "in"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8899; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
bh = open(os.path.join(ROOT, "build", "index.html"), encoding="utf-8").read(); _m = re.search(r'src="(/build/data-[0-9a-f]+\.js)"', bh)
js = open(os.path.join(ROOT, _m.group(1).lstrip("/")), encoding="utf-8").read(); BS = json.JSONDecoder().raw_decode(js[js.index("{", js.index("window.__BS = ")):])[0]
LEGS = {}
for l in BS["legs"]:
    if l.get("gl"): continue
    try: k = f'{l["pl"]}|{l["m"]}|{int(math.floor(float(l.get("ln") or 1) + 0.5))}'
    except Exception: continue
    LEGS.setdefault(k, l)
jr = lambda v: int(math.floor(float(v) + 0.5))

def expect_h5(l):
    """(values oldest first, hits, caption words) the card must show for this leg, or None when it must draw no bars"""
    m, sk = l["m"], l.get("sk")
    if not sk or m == "First TD": return None
    gs = [g for g in (BS.get("gl") or {}).get(l["pl"], []) if g.get(sk) is not None][:5][::-1]
    if len(gs) < 2: return None
    ln = float(l["ln"]); under = m.startswith("Under "); td = m.endswith("TD"); need = 2 if m == "2+ TD" else 3 if m == "3+ TD" else 1 if td else ln
    vals = [float(g[sk] or 0) for g in gs]; won = (lambda v: v < ln) if under else (lambda v: v >= need)
    return [str(jr(v)) for v in vals], sum(1 for v in vals if won(v)), ("stayed" if under else "scored" if td else "cleared")

READ = """() => { var vis = function(e){ return !!(e && (e.offsetWidth || e.offsetHeight)); };
  var cards = Array.from(document.querySelectorAll('article.play')).filter(function(a){ return vis(a) && !a.classList.contains('gl') && !a.classList.contains('nm'); });
  return {over: document.documentElement.scrollWidth - document.documentElement.clientWidth, cards: cards.map(function(a){
    var q = function(s){ return a.querySelector(s); }, more = q('a.more[href*="add="]'), key = a.getAttribute('data-k') || (more ? decodeURIComponent((/[?&]add=([^&#]+)/.exec(more.getAttribute('href')) || [])[1] || '') : '');
    var m = q('.nums.mtr'), cs = m ? getComputedStyle(m) : null, bar = q('.mvb'), br = bar ? bar.getBoundingClientRect() : null, R = function(s){ var e = q(s); return e ? e.getBoundingClientRect() : null; };
    var base = R('.mvb .mv0'), gap = R('.mvb .mv1'), tick = R('.mvb .mv2'), fdn = R('.fdn'), ar = a.getBoundingClientRect(), jn = q('.jn'), h5 = q('.h5');
    var nums = m ? Array.from(m.querySelectorAll(':scope > span')).map(function(s){ return s.textContent.replace(/\\s+/g, ''); }) : [];
    return {key: key, name: (q('.who b') || {}).textContent || '', sub: (q('.who small') || {}).textContent || '', logo: (q('.who small i.hm') || {getAttribute: function(){ return ''; }}).getAttribute('data-hm') || '',
      jn: jn ? jn.textContent.trim() : null, jnBox: jn ? [jn.offsetWidth, jn.offsetHeight] : null,
      nums: nums, up: m ? m.classList.contains('mtr-up') : null, dn: m ? m.classList.contains('mtr-dn') : null,
      lo: cs ? +cs.getPropertyValue('--lo') : null, hi: cs ? +cs.getPropertyValue('--hi') : null, b: cs ? +cs.getPropertyValue('--b') : null,
      bar: br ? Math.round(br.width) : 0, baseW: base && br ? base.width / br.width * 100 : null, gapL: gap && br ? (gap.left - br.left) / br.width * 100 : null, gapW: gap && br ? gap.width / br.width * 100 : null,
      tickX: tick && br ? (tick.left + tick.width / 2 - br.left) / br.width * 100 : null, fdnIn: fdn ? (fdn.left >= ar.left - 0.5 && fdn.right <= ar.right + 0.5) : null, fdnMid: fdn && br ? (fdn.left + fdn.width / 2 - br.left) / br.width * 100 : null,
      h5: h5 ? {v: Array.from(h5.querySelectorAll('li .v')).map(function(e){ return e.textContent; }), ov: h5.querySelectorAll('li.ov').length, cap: h5.querySelector('p').textContent.replace(/\\s+/g, ' ').trim(), big: h5.querySelector('p b').textContent,
                 ops: Array.from(h5.querySelectorAll('li i.hm')).map(function(i){ return i.getAttribute('data-hm'); }), same: h5.querySelectorAll('li.same').length, vs: (h5.querySelector('p small.vs') || {}).textContent || '', lnY: (function(){ var l = h5.querySelector('.ln'), bs = Array.from(h5.querySelectorAll('li .b')); if(!l || !bs.length) return null; var base = Math.max.apply(null, bs.map(function(e){ return e.getBoundingClientRect().bottom; })); return Math.round(base - l.getBoundingClientRect().top); })(),
                 hBar: Array.from(h5.querySelectorAll('li .b')).map(function(e){ return Math.round(e.getBoundingClientRect().height); }), lnVis: vis(h5.querySelector('.ln')), w: Math.round(h5.getBoundingClientRect().width), fits: h5.getBoundingClientRect().right <= ar.right + 0.5, aria: h5.getAttribute('aria-label') || ''} : null,
      why: Array.from(a.querySelectorAll('.why li')).map(function(li){ return [li.className, li.querySelector('b').textContent, li.querySelector('span').textContent.replace(li.querySelector('b').textContent, '').trim()]; }), pill: !!q('.foot .hist'),
      hist: (q('.hrow > .hist') || {}).textContent || '', slip: !!q('.hrow a.more'), fd: Array.from(a.querySelectorAll('.foot a.fdb')).filter(vis).length, h: Math.round(ar.height), inside: Array.from(a.querySelectorAll('.ptop, .what, .nums, .hrow, .foot')).concat(Array.from(a.querySelectorAll('.why'))).every(function(e){ var r = e.getBoundingClientRect(); return r.left >= ar.left - 0.5 && r.right <= ar.right + 0.5; })}; })}; }"""

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def open_(path, theme, clock=None):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block", color_scheme=theme)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + (f";(function(){{var T={int(clock)},R=Date.now,S=R();Date.now=function(){{return T+(R()-S)}};}})();" if clock else ""))
            async def gate(route, request): await (route.continue_() if "127.0.0.1" in request.url else route.abort())
            await ctx.route("**/*", gate)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}{path}", wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            return pg, ctx, errs
        # a clock before the week's first kickoff, so no card is hidden as started
        kos = [g["ko"] for g in BS["games"] if g.get("ko")]; early = (min(kos) - 30 * 3600e3) if kos else None
        for theme in ("dark", "light"):
            pg, ctx, errs = await open_("/best/", theme, early)
            # every tab's cards, not only the open one: tap through the row of tabs and read what each shows
            ntabs = await pg.evaluate("document.querySelectorAll('#wktabs .tab').length"); seen = {}; over = 0
            for ti in range(max(1, ntabs)):
                if ntabs: await pg.evaluate("(i) => document.querySelectorAll('#wktabs .tab')[i].click()", ti); await pg.wait_for_timeout(350)
                part = await pg.evaluate(READ); over = max(over, part["over"])
                for c in part["cards"]: seen.setdefault((ti, c["key"], c["name"]), c)
            s = {"over": over, "cards": list(seen.values())}; cards = [c for c in s["cards"] if c["key"] in LEGS]
            print(f"   [{theme}] /best/: {len(s['cards'])} leg cards across {max(1, ntabs)} tabs, {len(cards)} matched to a builder leg; first: {json.dumps(cards[0])[:420] if cards else None}")
            check(len(cards) >= 1 and len(cards) == len(s["cards"]), f"[{theme}] every leg card on Model's Best is a leg on this week's board ({len(cards)} of {len(s['cards'])})")
            if not cards: await ctx.close(); continue
            # ---- Model vs FanDuel ----
            bad = []
            for c in cards:
                l = LEGS[c["key"]]; mi, bi = int(f'{l["p"] * 100:.0f}'), int(f'{(l.get("bk") or 0) * 100:.0f}'); e = l["p"] - (l.get("bk") or 0)
                want = [f"Model{mi}%", f"Edge{e * 100:+.0f}", f"FanDuelneeds{bi}%"]
                if c["nums"] != want or c["lo"] != min(mi, bi) or c["hi"] != max(mi, bi) or c["b"] != bi or c["up"] != (e > 0) or c["dn"] != (e < 0): bad.append((c["name"], c["nums"], want, c["lo"], c["hi"], c["b"]))
            check(not bad, f"[{theme}] each card states Model, Edge and what FanDuel's price needs, and the bar is set from those same numbers ({len(cards)} cards; first wrong: {bad[:1]})")
            geo = [c for c in cards if c["bar"] < 200 or c["baseW"] is None or abs(c["baseW"] - c["lo"]) > 1.2 or abs(c["gapL"] - c["lo"]) > 1.2 or abs(c["gapW"] - (c["hi"] - c["lo"])) > 1.2 or abs(c["tickX"] - c["b"]) > 1.2]
            check(not geo, f"[{theme}] on screen the grey runs to the lower number, the painted gap spans the two, and the tick sits at FanDuel's number ({[(c['name'], c['lo'], c['hi'], round(c['baseW'] or 0, 1), round(c['gapW'] or 0, 1), round(c['tickX'] or 0, 1)) for c in geo[:2]]})")
            lab = [c for c in cards if not c["fdnIn"] or abs(c["fdnMid"] - c["b"]) > 26]
            check(not lab, f"[{theme}] the FanDuel label stays inside the card and near its tick, also at very low and very high prices ({[(c['name'], c['b'], round(c['fdnMid'] or 0)) for c in lab[:3]]}; prices from {min(c['b'] for c in cards)}% to {max(c['b'] for c in cards)}%)")
            # ---- last five games ----
            bad, drawn, plain = [], 0, 0
            for c in cards:
                ex = expect_h5(LEGS[c["key"]])
                if ex is None:
                    plain += 1
                    if c["h5"]: bad.append((c["name"], "bars with no log to draw"))
                    continue
                drawn += 1; vals, hits, verb = ex; _l = LEGS[c["key"]]
                _ops = [HM.ALIAS.get(str(g.get("opp") or ""), str(g.get("opp") or "")) for g in [g for g in BS["gl"][_l["pl"]] if g.get(_l["sk"]) is not None][:5][::-1]]
                said = ", ".join(v + ((" vs " + o) if o else "") for v, o in zip(vals, _ops))   # the label read to a screen reader names each game's opponent (11/27 late)
                if not c["h5"] or c["h5"]["v"] != vals or c["h5"]["ov"] != hits or c["h5"]["big"] != f"{hits} of {len(vals)}" or verb not in c["h5"]["cap"] or not c["h5"]["lnVis"] or not c["h5"]["fits"] or min(c["h5"]["hBar"]) < 1 or said not in c["h5"]["aria"]:
                    bad.append((c["name"], c["key"], c["h5"], vals, hits))
            check(not bad, f"[{theme}] the bars are his last games from the builder's own log, oldest first, green where the leg would have won, and the caption counts them ({drawn} cards with bars, {plain} without a log; first wrong: {bad[:1]})")
            check(all((c["hist"] == "") for c in cards if c["h5"]) and all(c["slip"] for c in cards), f"[{theme}] the season count rides under the caption when there are bars, and every card keeps its slip button")
            # ---- 11/27 late: the opponents under the bars, and the reasons ----
            al = lambda t: HM.ALIAS.get(str(t or ""), str(t or "")); bad, ringed, logod = [], 0, 0
            for c in cards:
                l = LEGS[c["key"]]
                if not c["h5"] or expect_h5(l) is None: continue
                gs = [g for g in BS["gl"][l["pl"]] if g.get(l["sk"]) is not None][:5][::-1]; ops = [al(g.get("opp")) for g in gs]; met = [g for g in gs if al(g.get("opp")) == al(l.get("opp"))]
                if all(o in HM.TEAMS for o in ops):
                    logod += 1; ringed += 1 if met else 0
                    wantvs = (f'vs {al(l.get("opp"))} in Week {met[-1].get("w")}: {jr(met[-1][l["sk"]] or 0)}' if met else "")
                    if c["h5"]["ops"] != ops or c["h5"]["same"] != len(met) or c["h5"]["vs"] != wantvs or not (c["h5"]["lnY"] is not None and 0 <= c["h5"]["lnY"] <= 34): bad.append((c["name"], c["h5"]["ops"], ops, c["h5"]["same"], c["h5"]["vs"], wantvs, c["h5"]["lnY"]))
                elif c["h5"]["ops"]: bad.append((c["name"], "logos for a team the site has no logo for", c["h5"]["ops"]))
            check(not bad, f"[{theme}] under each bar sits that game's opponent, a game against this week's opponent is ringed and said in words, and the dashed line still crosses the bars ({logod} cards with logos, {ringed} with a ringed game; first wrong: {bad[:1]})")
            bad = [(c["name"], c["why"], WHY.reasons(LEGS[c["key"]], BS.get("pf"))) for c in cards if [tuple(w) for w in c["why"]] != [tuple(r) for r in WHY.reasons(LEGS[c["key"]], BS.get("pf"))]]
            said = sum(1 for c in cards if c["why"])
            check(not bad and all(len(c["why"]) <= 2 and not (c["why"] and c["pill"]) for c in cards), f"[{theme}] each card says the model's strongest reason for and against that leg, at most one of each, in place of the loose pill ({said} of {len(cards)} cards with a reason; first wrong: {bad[:1]})")
            # ---- jersey numbers and logos ----
            bad, worn = [], 0
            for c in cards:
                l = LEGS[c["key"]]; n = HM.num(IN, l["pl"], l.get("tm") or "")
                if (c["jn"] or "") != n or (n and c["jnBox"] != [38, 40]): bad.append((c["name"], l.get("tm"), c["jn"], n, c["jnBox"]))
                worn += 1 if n else 0
            check(not bad, f"[{theme}] the shirt shows the roster's number for that player on that team, and no shirt when the roster has none ({worn} of {len(cards)} with a number; first wrong: {bad[:1]})")
            check(all(c["logo"] == (LEGS[c["key"]].get("tm") or "") for c in cards if (LEGS[c["key"]].get("tm") or "") in HM.TEAMS), f"[{theme}] each card has its team's logo beside the matchup ({[(c['name'], c['logo']) for c in cards if c['logo'] != (LEGS[c['key']].get('tm') or '')][:2]})")
            check(s["over"] <= 0 and all(c["inside"] for c in cards) and not errs, f"[{theme}] nothing runs off the card or the page, no page errors ({s['over']}px; {[c['name'] for c in cards if not c['inside']][:2]}; {errs[:1]})")
            tall = max(c["h"] for c in cards)
            check(tall <= 460, f"[{theme}] a card is at most {tall}px tall on a phone (limit 460: jersey row, bar, five bars with logos, two reasons and the book buttons)")
            if SHOTS:
                if ntabs: await pg.evaluate("document.querySelectorAll('#wktabs .tab')[0].click()"); await pg.wait_for_timeout(350)
                await pg.evaluate("() => { var a = Array.from(document.querySelectorAll('article.play')).filter(function(e){ return e.offsetWidth; })[0]; if(a){ a.scrollIntoView(); window.scrollBy(0, -110); } }"); await pg.wait_for_timeout(300)
                await pg.screenshot(path=os.path.join(SHOTS, f"leg_card_best_{theme}.png"))
            await ctx.close()
            # ---- Today: the game cards' looks use the same card ----
            pg, ctx, errs = await open_("/", theme, early); s = await pg.evaluate(READ); tc = [c for c in s["cards"] if c["key"] in LEGS]
            ok_t = all(c["nums"][:1] == [f"Model{int(format(LEGS[c['key']]['p'] * 100, '.0f'))}%"] and (c["h5"] is not None) == (expect_h5(LEGS[c["key"]]) is not None) for c in tc)
            check(ok_t and s["over"] <= 0 and not errs, f"[{theme}] Today's looks are the same card: bar, bars and number ({len(tc)} on screen; {s['over']}px sideways; {errs[:1]})")
            await ctx.close()
            # ---- News desk: a logo on every note that names a team ----
            pg, ctx, errs = await open_("/news/", theme)
            n = await pg.evaluate("""() => Array.from(document.querySelectorAll('.tdnewsl li')).map(function(li){ var i = li.querySelector('.nt i.hm'), r = i ? i.getBoundingClientRect() : null; return [li.getAttribute('data-team') || '', i ? i.getAttribute('data-hm') : '', i ? i.offsetHeight : 0, li.querySelector('.nt').textContent.trim(), !!(li.offsetWidth || li.offsetHeight)]; })""")
            named = [x for x in n if x[0] in HM.TEAMS]; wrong = [x for x in named if x[1] != x[0] or (x[4] and x[2] != 26) or not x[3]]
            over = await pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check(len(n) == 0 or (len(named) >= 1 and not wrong), f"[{theme}] every News desk note that names a team carries that team's logo under its status word ({len(named)} of {len(n)} notes; first wrong: {wrong[:1]})")
            check(over <= 0 and not errs, f"[{theme}] the News desk has no sideways scroll and no page errors ({over}px, {errs[:1]})")
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"leg_card_news_{theme}.png"))
            await ctx.close()
            # ---- the builder's best-legs strip ----
            pg, ctx, errs = await open_("/build/", theme, early); await pg.wait_for_timeout(1500)
            bq = await pg.evaluate("""() => Array.from(document.querySelectorAll('#bql .bqc')).map(function(c){ var h = c.querySelector('.h5'), b = c.querySelector('button[data-i]'), r = c.getBoundingClientRect(), hr = h ? h.getBoundingClientRect() : null;
                return {i: b ? +b.getAttribute('data-i') : null, v: h ? Array.from(h.querySelectorAll('li .v')).map(function(e){ return e.textContent; }) : null, ov: h ? h.querySelectorAll('li.ov').length : null, big: h ? h.querySelector('p b').textContent : null, fits: hr ? (hr.left >= r.left - 0.5 && hr.right <= r.right + 0.5) : true, h: Math.round(r.height)}; })""")
            bad = []
            for c in bq:
                l = BS["legs"][c["i"]] if c["i"] is not None and c["i"] < len(BS["legs"]) else None; ex = expect_h5(l) if l else None
                if ex is None:
                    if c["v"] is not None: bad.append((c["i"], "bars with no log"))
                elif c["v"] != ex[0] or c["ov"] != ex[1] or c["big"] != f"{ex[1]} of {len(ex[0])}" or not c["fits"]: bad.append((l["pl"], l["m"], c, ex))
            check(not bad and not errs, f"[{theme}] the builder's best-legs cards draw the same five bars from the same log ({len(bq)} cards, {sum(1 for c in bq if c['v'])} with bars; first wrong: {bad[:1]}; {errs[:1]})")
            if SHOTS and bq:
                el = await pg.query_selector("#bq"); await el.scroll_into_view_if_needed(); await pg.wait_for_timeout(300); await el.screenshot(path=os.path.join(SHOTS, f"leg_card_builder_{theme}.png"))
            await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
