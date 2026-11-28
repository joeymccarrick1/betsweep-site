"""The Live game's story under its field (owner 11/27 8:31 PM, "I love all 8": a live win-chance line and a drive strip).

The drive strip: every drive of the game as a chip, newest first - whose drive, how it ended, plays and yards; a score and a
giveaway are marked, the drive on the field says so. The win-chance line: the home team's chance after every play as one line, the
50% rule across the middle, a rule where each quarter begins, a dot at now. Fewer than eight points draws no line.

Runs in any week: a game is taken from the page's own data, its final is taken out, the page clock is set to forty minutes after its
kickoff, and ESPN (scoreboard and game summary), the change feed and the account service are faked or cut off.
  python3 tests/live_flow.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, glob, http.server, json, os, re, sys, threading
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8906; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
_ref = re.search(r"/live/(data-[0-9a-f]+\.js)", open(os.path.join(ROOT, "live", "index.html")).read())
SRC = open(os.path.join(ROOT, "live", _ref.group(1)) if _ref else glob.glob(os.path.join(ROOT, "live", "data-*.js"))[0]).read(); _m = re.match(r"\s*window\.__LV\s*=\s*", SRC); D0 = json.loads(SRC[_m.end():].rstrip().rstrip(";"))
D = json.loads(json.dumps(D0)); D["fb"] = {}
for _g in D["games"]: _g.pop("fin", None)
BODY = "window.__LV = " + json.dumps(D, separators=(",", ":")) + ";"
ESPN = {"LA": "LAR", "WAS": "WSH"}
GS = sorted([g for g in D["games"] if g.get("ko") and (g.get("info") or {}).get("home") in (g["a"], g["b"])], key=lambda g: (0 if (g["a"] in ESPN or g["b"] in ESPN) else 1, g["ko"]))
G = GS[0]; HOME = G["info"]["home"]; AWAY = G["b"] if G["a"] == HOME else G["a"]; EH, EA = ESPN.get(HOME, HOME), ESPN.get(AWAY, AWAY)
CLOCK = "(function(){var T=+(localStorage.getItem('t_now')||0);if(!T)return;var R=Date.now,S=R();Date.now=function(){return T+(R()-S)};var D0=Date;function ND(){if(arguments.length===0)return new D0(D0.now());return new (Function.prototype.bind.apply(D0,[null].concat([].slice.call(arguments))))()}ND.now=D0.now;ND.parse=D0.parse;ND.UTC=D0.UTC;ND.prototype=D0.prototype;window.Date=ND;})();"

def scoreboard():
    return {"events": [{"id": "401", "status": {"period": 2, "displayClock": "6:40", "type": {"state": "in", "completed": False, "shortDetail": "6:40 - 2nd"}},
                        "competitions": [{"competitors": [{"homeAway": "home", "team": {"abbreviation": EH, "id": "2"}, "score": "3"}, {"homeAway": "away", "team": {"abbreviation": EA, "id": "1"}, "score": "7"}], "situation": {}}]}]}

# the game so far: (team id, how it ended, scored?, description, quarter, plays in it); the last one is still on the field
DRIVES = [("1", "TD", True, "8 plays, 75 yards, 4:12", 1, 8), ("2", "PUNT", False, "3 plays, 4 yards, 1:30", 1, 3), ("1", "INT", False, "5 plays, 22 yards, 2:10", 2, 5), ("2", "FG", True, "10 plays, 61 yards, 5:02", 2, 10), ("1", "", False, "1 play, 9 yards, 0:20", 2, 1)]
def summary(points=None, drives=True):
    """points = how many win-chance readings to send (default one per play). The home chance drifts from 50% to 36%."""
    prev, plays, n = [], [], 0
    for i, (tid, res, sc, desc, q, np_) in enumerate(DRIVES):
        ps = []
        for j in range(np_):
            n += 1; ps.append({"id": f"p{n}", "text": f"Play {n}.", "scoringPlay": False, "period": {"number": q}, "clock": {"displayValue": "9:00"}, "start": {"shortDownDistanceText": "1st & 10"},
                               "end": {"yardLine": 40, "team": {"id": tid}, "down": 1, "distance": 10, "downDistanceText": "1st & 10 at the 40"}})
        d = {"id": f"d{i}", "team": {"id": tid, "abbreviation": EA if tid == "1" else EH}, "description": desc, "start": {"yardLine": 75 if tid == "1" else 25}, "plays": ps, "isScore": sc}
        if res: d["shortDisplayResult"] = res; d["displayResult"] = {"TD": "Touchdown", "PUNT": "Punt", "INT": "Interception", "FG": "Field Goal"}[res]
        prev.append(d); plays += ps
    cur = prev.pop()
    k = len(plays) if points is None else points
    wp = [dict({"homeWinPercentage": round(0.5 - 0.14 * (i / max(1, k - 1)), 4)}, **({"playId": plays[min(i, len(plays) - 1)]["id"]} if drives else {})) for i in range(k)]
    return {"header": {"competitions": [{"competitors": [{"homeAway": "home", "team": {"id": "2", "abbreviation": EH, "color": "4f2683"}}, {"homeAway": "away", "team": {"id": "1", "abbreviation": EA, "color": "a71930"}}]}]},
            "drives": {"previous": prev if drives else [], "current": cur if drives else None}, "boxscore": {"players": []}, "winprobability": wp, "scoringPlays": []}

READ = """(gid) => { var card = document.getElementById('lv-' + gid), w = card && card.querySelector('.gcw'); if(!w) return null; var vis = function(e){ return !!(e && (e.offsetWidth || e.offsetHeight)); };
  var strip = w.querySelector('.gc-drv'), line = w.querySelector('.gc-wpl'), f = w.querySelector('svg.gc-field'), fr = f.getBoundingClientRect(), wr = w.getBoundingClientRect();
  var path = line ? line.querySelector('path.wln') : null, d = path ? path.getAttribute('d') : '', dot = line ? line.querySelector('.wdot') : null, lr = line ? line.getBoundingClientRect() : null, sr = strip ? strip.getBoundingClientRect() : null;
  return {over: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    strip: strip ? {aria: strip.getAttribute('aria-label'), chips: Array.from(strip.querySelectorAll('.dv')).map(function(c){ var i = c.querySelector('i.hm'); return {cls: c.className.replace('dv', '').trim(), team: i ? i.getAttribute('data-hm') : (c.querySelector('em') || {}).textContent, res: c.querySelector('b').textContent, small: (c.querySelector('small') || {}).textContent || '', caps: c.querySelector('small') ? getComputedStyle(c.querySelector('small')).textTransform : 'none'}; }),
                    below: sr.top >= fr.bottom - 1, inside: sr.left >= wr.left - 1 && sr.right <= wr.right + 1, firstX: Math.round(strip.querySelector('.dv').getBoundingClientRect().left - sr.left), h: Math.round(sr.height)} : null,
    line: line ? {pts: (d.match(/[ML]/g) || []).length, last: d.slice(d.lastIndexOf('L') + 1).trim().split(' ').map(Number), dot: dot ? [parseFloat(dot.style.left), parseFloat(dot.style.top)] : null, labels: Array.from(line.querySelectorAll('.wl')).map(function(x){ return x.textContent; }),
                  q: line.querySelectorAll('line.wq').length, mid: !!line.querySelector('line.wm'), aria: line.querySelector('svg').getAttribute('aria-label'), fills: Array.from(line.querySelectorAll('path[clip-path]')).map(function(x){ return getComputedStyle(x).fill; }),
                  below: lr.top >= fr.bottom - 1, h: Math.round(lr.height), w: Math.round(lr.width), inside: lr.left >= wr.left - 1 && lr.right <= wr.right + 1} : null,
    wptext: (w.querySelector('.gc-wp') || {}).textContent || ''}; }"""

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); srv.handle_error = lambda *a: None; threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"   game {G['gid']}: {AWAY} at {HOME} (the feed calls them {EA} and {EH})")
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def visit(theme, sm):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block", color_scheme=theme)
            await ctx.add_init_script(f"try{{if(localStorage.getItem('t_now')===null){{localStorage.setItem('bs_theme','{theme}');localStorage.setItem('t_now','{int(G['ko'] + 40 * 60e3)}');}}}}catch(e){{}}" + CLOCK)
            async def on_espn(route, request): await route.fulfill(status=200, content_type="application/json", body=json.dumps(sm if "summary" in request.url else scoreboard()))
            async def on_feed(route, request): await route.fulfill(status=200, content_type="application/json", body=json.dumps({"events": []} if "changes.json" in request.url else {}))
            async def on_data(route, request): await route.fulfill(status=200, content_type="application/javascript", body=BODY)
            await ctx.route("**/*espn.com/**", on_espn); await ctx.route("**/raw.githubusercontent.com/**", on_feed); await ctx.route("**/data/price-moves.json", on_feed); await ctx.route("**/*supabase*/**", lambda r: r.abort()); await ctx.route("**/live/data-*.js", on_data)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/live/", wait_until="domcontentloaded"); await pg.wait_for_timeout(4200)
            s = await pg.evaluate(READ, G["gid"])
            if not s:
                await pg.evaluate("(gid) => { var c = document.getElementById('lv-' + gid), h = c && c.querySelector('.ghd2'); if(h) h.click(); }", G["gid"]); await pg.wait_for_timeout(2600); s = await pg.evaluate(READ, G["gid"])
            return pg, ctx, errs, s
        nplays = sum(d[5] for d in DRIVES)
        for theme in ("dark", "light"):
            pg, ctx, errs, s = await visit(theme, summary())
            if not s: check(False, f"[{theme}] the game in play shows its field"); await ctx.close(); continue
            st, ln = s["strip"], s["line"]
            want = [("dvc", AWAY, "On the field", "1 play · 9 yds"), ("dvs", HOME, "FG", "10 plays · 61 yds"), ("dvt", AWAY, "INT", "5 plays · 22 yds"), ("", HOME, "PUNT", "3 plays · 4 yds"), ("dvs", AWAY, "TD", "8 plays · 75 yds")]
            got = [(c["cls"], c["team"], c["res"], c["small"]) for c in (st or {}).get("chips", [])]
            check(bool(st) and got == want and "newest first" in st["aria"], f"[{theme}] the strip has every drive, newest first: whose it was (the site's own logo, whatever the feed calls the team), how it ended, plays and yards; scores and the giveaway are marked and the drive on the field says so ({got})")
            check(bool(st) and st["below"] and st["inside"] and st["firstX"] <= 2 and st["h"] <= 60 and all(c["caps"] == "none" for c in st["chips"]), f"[{theme}]   it sits under the field, inside the card, opens on the newest drive, and every chip's small print is plain text ({st and (st['below'], st['inside'], st['firstX'], st['h'])})")
            check(bool(ln) and ln["pts"] == nplays and ln["dot"] == [100.0, 64.0] and abs(ln["last"][1] - 0.64 * 60) < 0.2 and ln["labels"] == [EH, EA] and ln["mid"] and ln["q"] == 1,
                  f"[{theme}] the line has one point a play ({ln and ln['pts']} of {nplays}), ends at the home side's 36% (dot {ln and ln['dot']}), names home at the top and away at the bottom, with the 50% rule and one rule where the second quarter begins ({ln and ln['q']})")
            check(bool(ln) and f"{EA} 64%" in ln["aria"] and f"{EH} 36%" in ln["aria"] and re.search(rf"{re.escape(EA)} 64%\s*·\s*{re.escape(EH)} 36%", s["wptext"]) is not None and len(set(ln["fills"])) == 2,
                  f"[{theme}]   it agrees with the win-chance figures above it and paints the two sides in two colours ({ln and ln['aria']!r}; {s['wptext']!r})")
            check(bool(ln) and ln["below"] and ln["inside"] and 50 <= ln["h"] <= 70 and ln["w"] >= 300 and s["over"] <= 0 and not errs, f"[{theme}]   it is a thin band under the field, inside the card; no sideways scroll, no page errors ({ln and (ln['h'], ln['w'])}, {s['over']}px, {errs[:1]})")
            if SHOTS:
                el = await pg.query_selector(f"#lv-{G['gid']} .gcw")
                if el: await el.scroll_into_view_if_needed(); await pg.wait_for_timeout(500); await el.screenshot(path=os.path.join(SHOTS, f"live_flow_{theme}.png"))
            await ctx.close()
        # ---- too few readings: no line, the strip still there; no drives: no strip ----
        pg, ctx, errs, s = await visit("dark", summary(points=5))
        check(bool(s) and s["line"] is None and bool(s["strip"]) and len(s["strip"]["chips"]) == 5 and not errs, f"with five win-chance readings there is no line yet, and the strip is unchanged ({s and (s['line'], s['strip'] and len(s['strip']['chips']))}; {errs[:1]})")
        await ctx.close()
        pg, ctx, errs, s = await visit("dark", summary(drives=False))
        check(s is None or (s["strip"] is None and not errs), f"a summary with no drives draws no strip and breaks nothing ({'no field block' if s is None else s['strip']}; {errs[:1]})")
        await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
