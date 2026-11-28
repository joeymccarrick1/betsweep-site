"""Weather across a game header, and the number behind a player's name (owner 11/27 8:31 PM: "I also love the idea of weather in the
header"; "I love all 8": jersey numbers until headshots).

The layer is decoration on top of words the page already prints, so the test holds it to those words: a board wears rain only when
its own weather line says rain is likely, falling or moving in; snow only when it says snow is likely; wind only when it says windy -
and a board that says none of those wears nothing. The rule itself (wxfx.kind) is checked on made-up forecasts, the boards and the
Live page on the built site, the player header against the roster file.
  python3 tests/wx_fx.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, os, re, sys, threading
from playwright.async_api import async_playwright
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); sys.path.insert(0, HERE)
import wxfx as WX, helmets as HM
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); IN = os.path.join(HERE, "in"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8905; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
def skip(what): print("SKIP " + what)

# ---- the rule ----
f = lambda **k: dict({"roof": "outdoors", "pch": 0, "ptype": "none", "wind": 5, "gust": 8, "field": ""}, **k)
cases = [(f(pch=60), "r"), (f(pch=95, ptype="rain"), "r"), (f(pch=59, ptype="rain"), ""), (f(pch=8, field="rain now"), "r"), (f(pch=8, field="rain within 2 hours"), "r"), (f(pch=70, ptype="snow"), "s"),
         (f(pch=40, ptype="snow", wind=20), ""), (f(pch=10, wind=15), "w"), (f(pch=10, wind=8, gust=30), "w"), (f(pch=35, wind=22), ""), (f(pch=10, wind=14, gust=29), ""), (f(pch=100, roof="dome"), ""),
         (f(pch=100, roof="retractable"), ""), (None, ""), ({}, ""), ({"roof": "outdoors", "pc": "100", "pt": "rain", "w": "14", "gu": "35"}, "r"), ({"roof": "outdoors", "pc": "5", "pt": "none", "w": "18", "gu": "20"}, "w")]
bad = [(c, WX.kind(c), want) for c, want in cases if WX.kind(c) != want]
check(not bad, f"the rule: rain at 60%+ or when the last look says it is falling or moving in, snow at 60%+, wind (15+ mph or gusts 30+) only when neither, nothing indoors or under a roof that can close ({len(cases)} forecasts; first wrong: {bad[:1]})")
check(WX.tag("r") == '<i class="wxfx r" aria-hidden="true"></i>' and WX.tag("") == "" and WX.tag("x") == "", "the layer is one empty element, hidden from screen readers; no kind, no element")
css = WX.css()
check(all(x in css for x in (".wxfx.r::before", ".wxfx.s::before", ".wxfx.w::before", "@keyframes wxr1", "prefers-reduced-motion", ".card.done .wxfx{display:none}", "z-index:-1", "isolation:isolate")) and "url(\"http" not in css and "url(/" not in css,
      "its styles: three kinds, moved by a transform, stopped for reduced motion, gone on a finished board, behind the header's words, and no picture file (the marks are inline)")

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); srv.handle_error = lambda *a: None; threading.Thread(target=srv.serve_forever, daemon=True).start()   # a page closed mid-download is not an error worth printing
    WORDS = {"r": ("Rain likely", "Raining at the stadium now", "Rain moving in"), "s": ("Snow likely",), "w": ("Windy",)}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def open_(path, theme, clock=None, reduce=False):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block", color_scheme=theme, reduced_motion="reduce" if reduce else "no-preference")
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + (f";(function(){{var T={int(clock)},R=Date.now,S=R();Date.now=function(){{return T+(R()-S)}};}})();" if clock else ""))
            async def gate(route, request): await (route.continue_() if "127.0.0.1" in request.url else route.abort())
            await ctx.route("**/*", gate)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}{path}", wait_until="domcontentloaded"); await pg.wait_for_timeout(1700)
            return pg, ctx, errs
        BOARDS = """() => Array.from(document.querySelectorAll('section.card[id]')).filter(function(c){ return c.querySelector(':scope > header.hd'); }).map(function(c){ var h = c.querySelector(':scope > header.hd'), w = h.querySelector(':scope > .wxfx'), wx = c.querySelector('.wx'), cs = w ? getComputedStyle(w) : null, b4 = w ? getComputedStyle(w, '::before') : null;
            var txt = h.querySelector('.score'), tr = txt ? txt.getBoundingClientRect() : null, top = tr ? document.elementFromPoint(tr.left + tr.width / 2, tr.top + tr.height / 2) : null;
            return {id: c.id, ko: +c.getAttribute('data-ko') || 0, done: c.classList.contains('done'), kind: w ? w.className.replace('wxfx', '').trim() : '', words: wx ? wx.textContent.replace(/\\s+/g, ' ').trim() : '', roof: wx ? /roof can close/.test(wx.getAttribute('title') || '') : false, z: cs ? cs.zIndex : '', shown: cs ? cs.display !== 'none' : false, pe: cs ? cs.pointerEvents : '', anim: b4 ? b4.animationName : '', op: b4 ? +b4.opacity : 0,
              iso: getComputedStyle(h).isolation, clear: !w || !top || !top.classList.contains('wxfx')}; })"""
        # 11/28 (owner: "be on a continual loop and never stop"): at five moments of every layer's loop, the four corners of the moving sheet are
        # worked out from its own box, its transform origin and its transform at that moment; the header has to lie inside it each time.
        COVER = """() => { var out = [];
          Array.from(document.querySelectorAll('.wxfx')).forEach(function(w){ if(getComputedStyle(w).display === 'none') return; var W = w.clientWidth, H = w.clientHeight; if(!W || !H) return;
            document.getAnimations().filter(function(a){ return a.effect && a.effect.target === w && a.effect.pseudoElement; }).forEach(function(a){ var pe = a.effect.pseudoElement, d = +a.effect.getTiming().duration, it = a.effect.getTiming().iterations, cs = getComputedStyle(w, pe); a.pause();
              var L = parseFloat(cs.left), T = parseFloat(cs.top), bw = parseFloat(cs.width), bh = parseFloat(cs.height), o = cs.transformOrigin.split(' ').map(parseFloat), ox = L + o[0], oy = T + o[1];
              [0, 0.25, 0.5, 0.75, 0.999].forEach(function(f){ a.currentTime = d * f; var m = new DOMMatrixReadOnly(getComputedStyle(w, pe).transform);
                var quad = [[L, T], [L + bw, T], [L + bw, T + bh], [L, T + bh]].map(function(p){ var x = p[0] - ox, y = p[1] - oy; return [ox + m.a * x + m.c * y + m.e, oy + m.b * x + m.d * y + m.f]; });
                var inside = function(px, py){ var s = 0; for(var i = 0; i < 4; i++){ var p1 = quad[i], p2 = quad[(i + 1) % 4], cr = (p2[0] - p1[0]) * (py - p1[1]) - (p2[1] - p1[1]) * (px - p1[0]); if(Math.abs(cr) < 1e-6) continue; var g = cr > 0 ? 1 : -1; if(s === 0) s = g; else if(g !== s) return false; } return true; };
                out.push({host: (w.closest('[id]') || {}).id || '', kind: w.className.replace('wxfx', '').trim(), pe: pe, f: f, forever: it === Infinity, ok: inside(0.5, 0.5) && inside(W - 0.5, 0.5) && inside(W - 0.5, H - 0.5) && inside(0.5, H - 0.5),   /* half a pixel in: the header's size is read as a whole number */ W: W, H: H, box: [Math.round(bw), Math.round(bh)]}); });
              a.currentTime = 0; a.play(); }); });
          return out; }"""
        html_b = open(os.path.join(ROOT, "boards", "index.html"), encoding="utf-8").read(); kos = [int(x) for x in re.findall(r'<section class="card[^"]*" id="[A-Z]{2,3}-[A-Z]{2,3}" data-ko="(\d+)"', html_b)]
        early = (min(kos) - 30 * 3600e3) if kos else None
        for theme in ("dark", "light"):
            pg, ctx, errs = await open_("/boards/", theme, early); bs = await pg.evaluate(BOARDS)
            wet = [x for x in bs if x["kind"]]; dry = [x for x in bs if not x["kind"]]
            wrong = [(x["id"], x["kind"], x["words"][:40]) for x in wet if not any(x["words"].startswith(w) or ("forecast: " + w[0].lower() + w[1:]) in x["words"] for w in WORDS.get(x["kind"], ()))]
            loud = [(x["id"], x["words"][:40]) for x in dry if any(x["words"].startswith(w) for ws in WORDS.values() for w in ws) and not x["roof"]]   # a roof that can close: the words stay, the picture does not
            check(len(bs) >= 1 and not wrong and not loud and not any(x["roof"] for x in wet) and not errs, f"[{theme}] every board's layer matches its own weather line, a board whose line says rain likely, snow likely or windy is not left bare, and a stadium whose roof can close wears none ({len(wet)} of {len(bs)} boards wear one: {[(x['id'], x['kind']) for x in wet]}; wrong {wrong[:2]}; bare {loud[:2]}; {errs[:1]})")
            if wet:
                check(all(x["z"] == "-1" and x["iso"] == "isolate" and x["pe"] == "none" and x["clear"] and 0 < x["op"] <= 0.35 and x["anim"].startswith("wx") for x in wet if x["shown"]) and any(x["shown"] for x in wet),
                      f"[{theme}]   it sits behind the header's words, takes no taps, stays faint and moves ({[(x['id'], x['anim'], x['op']) for x in wet][:3]})")
                cv = await pg.evaluate(COVER); holes = [(c["host"], c["kind"], c["pe"], c["f"], c["W"], c["H"]) for c in cv if not c["ok"]]
                check(len(cv) >= 10 and not holes and all(c["forever"] for c in cv), f"[{theme}]   the loop never runs out: at the start, the quarters and the end of each pass the moving sheet still covers the whole header, and it repeats without end ({len(cv)} moments on {len(set(c['host'] for c in cv))} headers, sheets {sorted(set(tuple(c['box']) for c in cv))[:3]}; uncovered: {holes[:3]})")
                if SHOTS:
                    await pg.evaluate("(g) => { var h = document.getElementById(g).querySelector('header.hd'); window.scrollTo(0, h.getBoundingClientRect().top + window.scrollY - 130); }", wet[0]["id"]); await pg.wait_for_timeout(350); await pg.screenshot(path=os.path.join(SHOTS, f"wx_fx_board_{theme}.png"))
            else: skip(f"[{theme}] no board calls for weather this build, so there is no layer to look at")
            await ctx.close()
            if wet:
                pg, ctx, errs = await open_("/boards/", theme, early, reduce=True); r2 = await pg.evaluate(BOARDS); still = [x for x in r2 if x["kind"]]
                check(all(x["anim"] == "none" for x in still), f"[{theme}]   a reader who asks for less motion gets the still pattern ({[x['anim'] for x in still][:3]})")
                await ctx.close()
                g0 = wet[0]; late = g0["ko"] + 5 * 3600e3
                pg, ctx, errs = await open_("/boards/", theme, late); r3 = await pg.evaluate(BOARDS); x3 = next(x for x in r3 if x["id"] == g0["id"])
                check(x3["done"] and not x3["shown"], f"[{theme}]   five hours after kickoff the board is done and its layer is gone ({g0['id']}: done {x3['done']}, shown {x3['shown']})")
                await ctx.close()
                # the Live header for the same game: on before and during, off once it is final
                pg, ctx, errs = await open_("/live/", theme, early); await pg.wait_for_timeout(900)
                lv = await pg.evaluate("""() => Array.from(document.querySelectorAll('section[id^="lv-"], div[id^="lv-"]')).map(function(c){ var h = c.querySelector('.ghd2'), w = h ? h.querySelector('.wxfx') : null; return {id: c.id.slice(3), kind: w ? w.className.replace('wxfx', '').trim() : '', pos: h ? getComputedStyle(h).position : '', over: h ? getComputedStyle(h).overflow : ''}; })""")
                by = {x["id"]: x for x in lv}; exp = {x["id"]: x["kind"] for x in bs}
                same = [(k, by[k]["kind"], exp.get(k) if exp.get(k) is not None else exp.get("-".join(k.split("-")[::-1]))) for k in by]
                check(len(lv) >= 1 and all(a == (e or "") for _, a, e in same if e is not None) and all(x["pos"] == "relative" and x["over"] == "hidden" for x in lv if x["kind"]) and not errs, f"[{theme}]   the Live headers wear the same layers as the boards ({[(k, a) for k, a, e in same if a]}; {errs[:1]})")
                await ctx.close()
                pg, ctx, errs = await open_("/live/", theme, late); await pg.wait_for_timeout(900)
                l2 = await pg.evaluate("(g) => { var a = document.getElementById('lv-' + g) || document.getElementById('lv-' + g.split('-').reverse().join('-')); var h = a ? a.querySelector('.ghd2') : null; return h ? !!h.querySelector('.wxfx') : null; }", g0["id"])
                check(l2 is not True, f"[{theme}]   and it is gone once the game is over ({'no header left for it' if l2 is None else 'header without it'})")
                await ctx.close()
        # ---- the player header ----
        idx = os.path.join(ROOT, "player"); slugs = [d for d in sorted(os.listdir(idx)) if os.path.isfile(os.path.join(idx, d, "index.html"))] if os.path.isdir(idx) else []
        import plydata as PD
        names = {}
        try:
            import csv
            for r in csv.DictReader(open(os.path.join(IN, "roster_2026.csv"), newline="", encoding="utf-8")): names.setdefault(PD.slugify(r.get("full_name") or ""), r.get("full_name"))
        except Exception as e: print("note: no roster file -", e)
        seen = wrong = worn = 0; first = None
        for sl in slugs[:400]:
            h = open(os.path.join(idx, sl, "index.html"), encoding="utf-8").read(); m = re.search(r'<header class="pwash"[^>]*>(.*?)</header>', h, re.S)
            if not m: continue
            tm = re.search(r'class="tb" data-hm="([A-Z]{2,3})"', m.group(1)); nm = re.search(r"<h1>(.*?)</h1>", m.group(1)); big = re.search(r'<i class="pnum" aria-hidden="true">(\d+)</i>', m.group(1)); small = re.search(r'<span class="jnum">#(\d+)</span>', m.group(1))
            if not tm or not nm: continue
            import html as _h
            want = HM.num(IN, _h.unescape(nm.group(1)), tm.group(1)); seen += 1; worn += 1 if want else 0
            if (big.group(1) if big else "") != want or (small.group(1) if small else "") != want: wrong += 1; first = first or (sl, tm.group(1), want, big and big.group(1), small and small.group(1))
        check(seen >= 1 and wrong == 0, f"player pages: the number behind the name and in the line under it is the roster's number for that player on that team, and neither is there when the roster has none ({worn} of {seen} pages with a number; first wrong: {first})")
        if seen:
            sl = next((s_ for s_ in slugs if '<i class="pnum"' in open(os.path.join(idx, s_, "index.html"), encoding="utf-8").read()), None)
            if sl:
                for theme in ("dark", "light"):
                    pg, ctx, errs = await open_(f"/player/{sl}/", theme)
                    r = await pg.evaluate("""() => { var h = document.querySelector('.pp header'), n = h.querySelector('.pnum'), cs = getComputedStyle(n), t = h.querySelector('h1'), tr = t.getBoundingClientRect(), top = document.elementFromPoint(tr.left + 10, tr.top + tr.height / 2), hr = h.getBoundingClientRect(), nr = n.getBoundingClientRect();
                        return {z: cs.zIndex, pe: cs.pointerEvents, big: parseFloat(cs.fontSize), inside: nr.right <= hr.right + 1 && nr.left >= hr.left - 1, clear: !top.classList.contains('pnum'), over: document.documentElement.scrollWidth - innerWidth}; }""")
                    check(r["z"] == "-1" and r["pe"] == "none" and r["big"] >= 90 and r["inside"] and r["clear"] and r["over"] <= 0 and not errs, f"[{theme}] /player/{sl}/: the number is large, behind the header's words, inside the header, and takes no taps ({r}; {errs[:1]})")
                    if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"wx_fx_player_{theme}.png"))
                    await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
