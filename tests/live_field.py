"""The Live field faces the way the game's header does (11/27 night).

Before: the header had the away team on the left and the home team on the right (owner 11/27), while the field under it kept the home
end zone on the left, so the team on the left of the header drove toward the left. Now the away end zone is on the left and the home
end zone on the right, each with its own wordmark and paint, the home logo sits at midfield, and the win-chance bar runs the same way.

Runs in any week: a game is taken from the page's own data, its final is taken out, the page clock is set to forty minutes after its
kickoff, and ESPN (scoreboard and game summary), the change feed and the account service are faked or cut off.
  python3 tests/live_field.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, glob, http.server, json, os, re, sys, threading
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8898; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
_ref = re.search(r"/live/(data-[0-9a-f]+\.js)", open(os.path.join(ROOT, "live", "index.html")).read())
SRC = open(os.path.join(ROOT, "live", _ref.group(1)) if _ref else glob.glob(os.path.join(ROOT, "live", "data-*.js"))[0]).read(); _m = re.match(r"\s*window\.__LV\s*=\s*", SRC); D0 = json.loads(SRC[_m.end():].rstrip().rstrip(";"))
D = json.loads(json.dumps(D0)); D["fb"] = {}
for _g in D["games"]: _g.pop("fin", None)
BODY = "window.__LV = " + json.dumps(D, separators=(",", ":")) + ";"
ESPN = {"LA": "LAR", "WAS": "WSH"}   # the feed's own spelling of two teams: the field has to find their files all the same
GS = sorted([g for g in D["games"] if g.get("ko") and (g.get("info") or {}).get("home") in (g["a"], g["b"])], key=lambda g: (0 if (g["a"] in ESPN or g["b"] in ESPN) else 1, g["ko"]))
G = GS[0]; HOME = G["info"]["home"]; AWAY = G["b"] if G["a"] == HOME else G["a"]
CH, CA = "4f2683", "a71930"   # end-zone paint the faked feed gives the home and the away team
CLOCK = "(function(){var T=+(localStorage.getItem('t_now')||0);if(!T)return;var R=Date.now,S=R();Date.now=function(){return T+(R()-S)};var D0=Date;function ND(){if(arguments.length===0)return new D0(D0.now());return new (Function.prototype.bind.apply(D0,[null].concat([].slice.call(arguments))))()}ND.now=D0.now;ND.parse=D0.parse;ND.UTC=D0.UTC;ND.prototype=D0.prototype;window.Date=ND;})();"

def scoreboard():
    return {"events": [{"id": "401", "status": {"period": 2, "displayClock": "8:12", "type": {"state": "in", "completed": False, "shortDetail": "8:12 - 2nd"}},
                        "competitions": [{"competitors": [{"homeAway": "home", "team": {"abbreviation": ESPN.get(HOME, HOME), "id": "2"}, "score": "13"},
                                                           {"homeAway": "away", "team": {"abbreviation": ESPN.get(AWAY, AWAY), "id": "1"}, "score": "17"}], "situation": {}}]}]}

def summary(home_ball):
    """The away team at the home 37 (2nd and 4, drive began at its own 25), or the home team at its own 25 (1st and 10, drive began at
    its own 12). The feed's yard line counts from the home goal line."""
    pid = "2" if home_ball else "1"; yl, ds, down, dist = (25, 12, 1, 10) if home_ball else (37, 75, 2, 4)
    return {"header": {"competitions": [{"competitors": [{"homeAway": "home", "team": {"id": "2", "abbreviation": ESPN.get(HOME, HOME), "color": CH}},
                                                           {"homeAway": "away", "team": {"id": "1", "abbreviation": ESPN.get(AWAY, AWAY), "color": CA}}]}]},
            "drives": {"previous": [], "current": {"id": "d2", "team": {"id": pid, "abbreviation": ESPN.get(HOME if home_ball else AWAY, "")}, "description": "5 plays, 38 yards, 2:41", "start": {"yardLine": ds},
                                                    "plays": [{"text": "Run up the middle for 6 yards.", "scoringPlay": False, "period": {"number": 2}, "clock": {"displayValue": "8:12"}, "start": {"shortDownDistanceText": "1st & 10"},
                                                               "end": {"yardLine": yl, "team": {"id": pid}, "down": down, "distance": dist, "downDistanceText": "down and distance"}}]}},
            "boxscore": {"players": []}, "winprobability": [{"homeWinPercentage": 0.58}], "scoringPlays": []}

READ = """(gid) => { var card = document.getElementById('lv-' + gid), s = card && card.querySelector('svg.gc-field'); if(!s) return null;
  var N = function(e, a){ return parseFloat(e.getAttribute(a)); }, q = function(x){ return Array.from(s.querySelectorAll(x)); };
  var hd = Array.from(card.querySelectorAll('.ghd2 [data-hm]')).filter(function(e){ return e.offsetWidth > 0; }).sort(function(a, b){ return a.getBoundingClientRect().left - b.getBoundingClientRect().left; }).map(function(e){ return e.getAttribute('data-hm'); });
  var img = q('image').map(function(e){ var t = /translate\\(([0-9.]+)/.exec(e.getAttribute('transform') || ''); return {href: e.getAttribute('href'), x: t ? +t[1] : N(e, 'x') + N(e, 'width') / 2, f: e.getAttribute('filter') || ''}; });
  var zones = q('rect').filter(function(e){ return N(e, 'width') === 100 && N(e, 'height') === 230 && (N(e, 'x') === 0 || N(e, 'x') === 1100) && /^#[0-9a-f]{3,6}$/i.test(e.getAttribute('fill') || '') && !/^#2[af]6/i.test(e.getAttribute('fill')); }).map(function(e){ return [N(e, 'x'), e.getAttribute('fill').toLowerCase()]; });
  var ball = s.querySelector('ellipse'), tip = q('path').map(function(e){ var m = /^M([0-9.]+)/.exec(e.getAttribute('d') || ''); return m ? +m[1] : null; })[0];
  var lines = q('line').filter(function(e){ return N(e, 'stroke-width') === 5; }).map(function(e){ return [e.getAttribute('stroke'), N(e, 'x1')]; });
  var drive = q('rect').filter(function(e){ return N(e, 'height') === 46; }).map(function(e){ return [N(e, 'x'), N(e, 'x') + N(e, 'width')]; })[0] || null;
  var wp = card.querySelector('.gc-wp'), bar = wp ? Array.from(wp.querySelectorAll('.gc-wpbar i')).map(function(e){ return parseInt(e.style.width, 10); }) : [];
  return {hd: hd, img: img, zones: zones, ball: ball ? N(ball, 'cx') : null, tip: tip, lines: lines, drive: drive, wp: wp ? wp.textContent : '', wpb: wp && wp.querySelector('b') ? wp.querySelector('b').textContent : '', bar: bar,
          over: document.documentElement.scrollWidth - document.documentElement.clientWidth, w: Math.round(s.getBoundingClientRect().width)}; }"""

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    hk, ak = HOME.lower(), AWAY.lower()
    print(f"   game {G['gid']}: {AWAY} at {HOME} (the feed calls them {ESPN.get(AWAY, AWAY)} and {ESPN.get(HOME, HOME)})")
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def visit(theme, home_ball):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block", color_scheme=theme)
            await ctx.add_init_script(f"try{{if(localStorage.getItem('t_now')===null){{localStorage.setItem('bs_theme','{theme}');localStorage.setItem('t_now','{int(G['ko'] + 40 * 60e3)}');}}}}catch(e){{}}" + CLOCK)
            def espn(hb):
                async def on_espn(route, request): await route.fulfill(status=200, content_type="application/json", body=json.dumps(summary(hb) if "summary" in request.url else scoreboard()))
                return on_espn
            async def on_feed(route, request): await route.fulfill(status=200, content_type="application/json", body=json.dumps({"events": []} if "changes.json" in request.url else {}))
            async def on_data(route, request): await route.fulfill(status=200, content_type="application/javascript", body=BODY)
            await ctx.route("**/*espn.com/**", espn(home_ball)); await ctx.route("**/raw.githubusercontent.com/**", on_feed); await ctx.route("**/data/price-moves.json", on_feed); await ctx.route("**/*supabase*/**", lambda r: r.abort()); await ctx.route("**/live/data-*.js", on_data)
            pg = await ctx.new_page(); errs = []; got = {}; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            pg.on("response", lambda r: got.__setitem__(r.url.split(f"127.0.0.1:{PORT}")[-1], r.status) if r.url.endswith(".webp") else None)
            await pg.goto(f"http://127.0.0.1:{PORT}/live/", wait_until="domcontentloaded"); await pg.wait_for_timeout(4200)
            s = await pg.evaluate(READ, G["gid"])
            if not s:   # the card of a game in play opens by itself; if this build keeps it shut, open it
                await pg.evaluate("(gid) => { var c = document.getElementById('lv-' + gid), h = c && c.querySelector('.ghd2'); if(h) h.click(); }", G["gid"]); await pg.wait_for_timeout(2600); s = await pg.evaluate(READ, G["gid"])
            return pg, ctx, errs, s, got
        for theme in ("dark", "light"):
            # ---- the away team has the ball at the home 37, 2nd and 4, on a drive that began at its own 25 ----
            pg, ctx, errs, s, got = await visit(theme, False)
            if not s:
                check(False, f"[{theme}] the game in play shows its field"); await ctx.close(); continue
            print(f"   [{theme}] away ball:", json.dumps({k: s[k] for k in ("hd", "zones", "ball", "tip", "lines", "drive", "wp", "bar", "w")})[:560])
            wm = [i for i in s["img"] if "/s/wm/" in i["href"]]; logo = [i for i in s["img"] if "/s/wm/" not in i["href"]]
            check(s["hd"][:1] == [AWAY] and s["hd"][-1:] == [HOME], f"[{theme}] the header has the away team on the left and the home team on the right ({s['hd']})")
            check(sorted(s["zones"]) == [[0, "#" + CA], [1100, "#" + CH]], f"[{theme}] the left end zone wears the away team's paint and the right one the home team's ({s['zones']})")
            check(len(wm) == 2 and sorted((i["x"], i["href"]) for i in wm) == [(50, f"/s/wm/{ak}.webp"), (1150, f"/s/wm/{hk}.webp")], f"[{theme}] each end zone carries its own team's wordmark, away on the left and home on the right, whatever the feed calls the team ({[(i['x'], i['href']) for i in wm]})")
            check(len(logo) == 1 and logo[0]["href"].endswith(f"/{hk}-l.webp") and logo[0]["x"] == 600 and not logo[0]["f"], f"[{theme}] the home team's logo sits at midfield in its own colours ({logo})")
            files = [f"/s/wm/{ak}.webp", f"/s/wm/{hk}.webp", logo[0]["href"] if logo else ""]
            check(all(got.get(f) == 200 for f in files), f"[{theme}] the three picture files are on the site and load ({[(f, got.get(f)) for f in files]})")
            check(s["ball"] == 730 and s["tip"] is not None and s["tip"] > s["ball"], f"[{theme}] the away team at the home 37 is 37 yards from the right-hand goal line and its arrow points right, at the home end zone (ball {s['ball']}, arrow tip {s['tip']})")
            check(["#f5d33b", 770] in s["lines"] and ["#4aa3ff", 730] in s["lines"], f"[{theme}] the line to gain is 4 yards nearer the home end zone than the ball ({s['lines']})")
            check(s["drive"] == [350, 730], f"[{theme}] the drive bar runs from where the drive began to the ball ({s['drive']})")
            check(re.search(rf"Win chance\s*{re.escape(ESPN.get(AWAY, AWAY))} 42%\s*·\s*{re.escape(ESPN.get(HOME, HOME))} 58%", s["wp"]) is not None and s["wpb"] == f"{ESPN.get(HOME, HOME)} 58%" and s["bar"] == [42, 58], f"[{theme}] win chance reads away then home like the header, the likelier side in bold, and the bar is split the same way ({s['wp']!r}, bold {s['wpb']!r}, bar {s['bar']})")
            check(s["over"] <= 0 and not errs, f"[{theme}] no sideways scroll and no page errors ({s['over']}px, {errs[:1]})")
            if SHOTS:
                el = await pg.query_selector(f"#lv-{G['gid']} .gcw")
                if el: await el.scroll_into_view_if_needed(); await pg.wait_for_timeout(500); await el.screenshot(path=os.path.join(SHOTS, f"live_field_{theme}.png"))
            await ctx.close()
            # ---- the home team has it at its own 25, 1st and 10, on a drive that began at its own 12 ----
            pg, ctx, errs, s, got = await visit(theme, True)
            if not s:
                check(False, f"[{theme}] the field shows with the home team on offense"); await ctx.close(); continue
            print(f"   [{theme}] home ball:", json.dumps({k: s[k] for k in ("ball", "tip", "lines", "drive")}))
            check(s["ball"] == 850 and s["tip"] is not None and s["tip"] < s["ball"], f"[{theme}] the home team at its own 25 is 25 yards out from the right-hand goal line and its arrow points left, at the away end zone (ball {s['ball']}, arrow tip {s['tip']})")
            check(["#f5d33b", 750] in s["lines"] and s["drive"] == [850, 980], f"[{theme}] its line to gain is 10 yards toward the away end zone and its drive bar starts at its own 12 ({s['lines']}, {s['drive']})")
            check(not errs, f"[{theme}] no page errors with the home team on offense ({errs[:1]})")
            await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
