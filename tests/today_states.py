"""Today's opener and the three states of a game card (owner 11/27 8:31 PM, "I love all 8": Today opens with the next game; Final cards
on Today). Before kickoff: the opener counts down to the next game and the card is as it was. In play: the opener and the card carry
the score, and nothing on the card can still be bet. Over: the card is a Final card - the score, how the model's call did against it,
and the looks it showed before kickoff, graded from the box score.

Nothing here assumes a week or a clock: the games, their kickoffs and the frozen pre-kickoff copies are read from the built page's own
data (window.__TD), the page's clock is set from those kickoffs, and ESPN is played by this file (a scoreboard and one box score).
Every expected line of a Final card is worked out here from the frozen copy and the fake score.
  python3 tests/today_states.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, math, os, re, sys, threading
from playwright.async_api import async_playwright
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); sys.path.insert(0, HERE)
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8904; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
def skip(what): print("SKIP " + what)
ESPN = {"WAS": "WSH", "LA": "LAR"}

# ---- the freeze rule, on its own ----
import build_today as BT
old = {"A-B": {"at": "t0", "pa": 20.0, "pb": 24.0, "sp": -3.5, "tot": 44.5, "home": "B", "looks": [{"pl": "X"}]}, "C-D": {"at": "t0", "pa": 17.0, "pb": 17.0, "sp": None, "tot": None, "home": "D", "looks": []}}
fresh = {"A-B": (1000, {"at": "t1", "pa": 21.0, "pb": 23.0, "sp": None, "tot": 45.5, "home": "B", "looks": []}),      # not kicked off; this build has no spread and no looks
         "C-D": (500, {"at": "t1", "pa": 10.0, "pb": 30.0, "sp": -7.0, "tot": 40.0, "home": "D", "looks": [{"pl": "Y"}]}),   # kicked off
         "E-F": (400, {"at": "t1", "pa": 1.0, "pb": 2.0, "sp": 1.0, "tot": 2.0, "home": "F", "looks": []}),                  # kicked off, never frozen
         "G-H": (2000, {"at": "t1", "pa": 3.0, "pb": 4.0, "sp": 2.5, "tot": 30.0, "home": "H", "looks": [{"pl": "Z"}]})}     # new this build
fz = BT.freeze(old, fresh, 600)
check(fz["A-B"] == {"at": "t1", "pa": 21.0, "pb": 23.0, "sp": -3.5, "tot": 45.5, "home": "B", "looks": [{"pl": "X"}]}, "freeze: a game still to come takes this build's numbers and keeps the last spread and looks it had when this build has none")
check(fz["C-D"] == old["C-D"] and "E-F" not in fz and fz["G-H"] == fresh["G-H"][1] and old["A-B"]["pa"] == 20.0, "freeze: a game that has kicked off keeps what it had (or nothing), a new game is added, and the old copy is not changed in place")

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def open_(theme, clock, board=None, box=None):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block", color_scheme=theme)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}'); localStorage.removeItem('bs_view')}}catch(e){{}};(function(){{var T={int(clock)},R=Date.now,S=R();Date.now=function(){{return T+(R()-S)}};}})();")
            asked = []
            async def gate(route, request):
                u = request.url
                if "127.0.0.1" in u: return await route.continue_()
                if "espn.com" in u and "scoreboard" in u and board is not None: asked.append("sb"); return await route.fulfill(status=200, content_type="application/json", body=json.dumps(board))
                if "espn.com" in u and "summary" in u and box is not None: asked.append("sm"); return await route.fulfill(status=200, content_type="application/json", body=json.dumps(box))
                await route.abort()
            await ctx.route("**/*", gate)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2200)
            return pg, ctx, errs, asked
        READ = """() => { var vis = function(e){ return !!(e && (e.offsetWidth || e.offsetHeight)); }, h = document.querySelector('#tdhero .thl'), hs = document.getElementById('tdhero');
          return {over: document.documentElement.scrollWidth - innerWidth, heroOn: vis(hs), hero: h ? {gid: h.getAttribute('data-gid'), st: h.getAttribute('data-st'), href: h.getAttribute('href'), mid: h.querySelector('.thc b').textContent, small: h.querySelector('.thc small').textContent,
              teams: Array.from(h.querySelectorAll('.tht b')).map(function(x){ return x.textContent; }), logos: Array.from(h.querySelectorAll('.tht i.hm')).map(function(x){ return x.getAttribute('data-hm'); }), wx: (h.querySelector('.wxfx') || {className: ''}).className, line: (h.querySelector('.thf') || {}).textContent || '',
              more: Array.from(document.querySelectorAll('#tdhero .thx a')).map(function(a){ return a.getAttribute('href'); }), top: Math.round(h.getBoundingClientRect().top), h: Math.round(h.getBoundingClientRect().height)} : null,
            firstSecs: Array.from(document.querySelectorAll('section')).filter(vis).slice(0, 3).map(function(s){ return s.id || s.className; }),
            strip: Array.from(document.querySelectorAll('#lstrip .lsc')).map(function(a){ return a.getAttribute('href') + ' ' + a.textContent; }),
            cards: Array.from(document.querySelectorAll('#tdgames .tdgame')).filter(function(c){ return c.classList.contains('show'); }).map(function(c){ var pri = c.querySelector('.tdlinks a.pri'), q = function(s){ return c.querySelector(s); };
              return {gid: c.getAttribute('data-gid'), live: c.classList.contains('live'), fin: c.classList.contains('fin'), vis: vis(c), logos: Array.from(c.querySelectorAll('header .tdm i.hm')).map(function(x){ return x.getAttribute('data-hm'); }),
                chip: (q('.tdk .gl') || {}).textContent || '', pri: pri ? [pri.getAttribute('href'), pri.textContent] : null, looks: Array.from(c.querySelectorAll('.tdplays .play')).filter(vis).length, bp: vis(q('.tdbp')), build: Array.from(c.querySelectorAll('.tdlinks a[href^="/build/"]')).filter(vis).length,
                stats: vis(q('.tdstats')), fsc: q('.fsc') ? {txt: Array.from(c.querySelectorAll('.fsc .ft')).map(function(x){ return [x.querySelector('b').textContent, x.querySelector('em').textContent, x.classList.contains('w')]; }), logos: Array.from(c.querySelectorAll('.fsc i.hm')).map(function(x){ return x.getAttribute('data-hm'); })} : null,
                calls: Array.from(c.querySelectorAll('.fcall li')).map(function(li){ return [li.className, li.querySelector('span').textContent, li.querySelector('b').textContent, li.querySelector('small').textContent]; }),
                flt: q('.flt') ? q('.flt').textContent.replace(/\\s+/g, ' ').trim() : null, flk: Array.from(c.querySelectorAll('.flk li')).map(function(li){ return [li.className, li.querySelector('b').textContent, li.querySelector('em').textContent]; }), flkOpen: q('.flk') ? !q('.flk').hidden : null,
                note: (q('.fnote') || {}).textContent || ''}; })}; }"""
        # ---- the page's own games ----
        pg, ctx, errs, _ = await open_("dark", 0); T = await pg.evaluate("window.__TD"); await ctx.close()
        import datetime
        built = datetime.datetime.fromisoformat(T["built"]).timestamp() * 1000; games = sorted([g for g in T["games"] if g.get("ko")], key=lambda g: g["ko"])
        todo = [g for g in games if g["ko"] > built and not g.get("fin")]
        check(all(isinstance(g.get("pa"), (int, float)) and "fz" in g and "wx" in g for g in games) and isinstance(T.get("col"), dict), f"the page carries each game's model score, its frozen copy and its weather kind ({len(games)} games, {sum(1 for g in games if g.get('fz'))} with a frozen copy)")
        check(all(g.get("fz") and g["fz"].get("at") for g in todo), f"every game still to come when the page was built has a frozen copy ({len(todo)} games)")
        if not todo:
            skip("no game still to come in this build: the opener and the states have nothing to show"); await b.close(); srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
        k1 = todo[0]["ko"]; grp = [g for g in todo if g["ko"] == k1]; G0 = grp[0]; GT = next((g for g in grp if len(g["fz"].get("looks") or []) >= 2), next((g for g in grp if g["fz"].get("looks")), G0))
        away = lambda g: g.get("away") or g["a"]; home = lambda g: g.get("home") or g["b"]
        def left(ms): m = max(0, int(ms // 60000)); h = m // 60; d = h // 24; return f"{d}d {h % 24}h" if d >= 1 else f"{h}h {m % 60}m" if h >= 1 else f"{m}m"
        def board(states):   # {gid: (state, away score, home score, detail)} -> ESPN's scoreboard
            evs = []
            for i, g in enumerate(games):
                if g["gid"] not in states: continue
                st, sa, sh, det = states[g["gid"]]
                evs.append({"id": str(4000 + i), "status": {"period": 2, "displayClock": "5:32", "type": {"state": st, "completed": st == "post", "shortDetail": det}},
                            "competitions": [{"competitors": [{"homeAway": "away", "score": str(sa), "team": {"id": str(100 + 2 * i), "abbreviation": ESPN.get(away(g), away(g))}}, {"homeAway": "home", "score": str(sh), "team": {"id": str(101 + 2 * i), "abbreviation": ESPN.get(home(g), home(g))}}], "situation": {}, "broadcasts": []}]})
            return {"events": evs}
        for theme in ("dark", "light"):
            # ---- before kickoff: three hours out ----
            t0 = k1 - 3 * 3600e3 - 20e3; pg, ctx, errs, _ = await open_(theme, t0); s = await pg.evaluate(READ); h = s["hero"]
            check(bool(h) and s["heroOn"] and h["gid"] == G0["gid"] and h["st"] == "pre" and h["href"] == f"/boards/#g-{G0['gid']}" and h["teams"] == [away(G0), home(G0)] and h["logos"] == [away(G0), home(G0)] and not errs,
                  f"[{theme}] three hours out the page opens with the next game, away on the left, logos on both, a tap to its board ({h and (h['gid'], h['teams'], h['href'])}; {errs[:1]})")
            check(bool(h) and h["mid"] in ("3h 0m", "2h 59m") and h["small"] == G0.get("kick", "") and len(h["more"]) == len(grp) - 1 and h["top"] < 330 and 90 <= h["h"] <= 190,
                  f"[{theme}]   it counts down to kickoff ({h and h['mid']!r}, {h and h['small']!r}), lists the {len(grp) - 1} other games at that kickoff, and sits on the first screen ({h and h['top']}px down, {h and h['h']}px tall)")
            check(bool(h) and (("wxfx " + G0["wx"]) == h["wx"] if G0.get("wx") else h["wx"] == "") and ("Model" in h["line"]), f"[{theme}]   weather rides the opener only when the forecast calls for it ({G0.get('wx')!r} -> {h and h['wx']!r}), and the model's score is under it ({h and h['line'][:60]!r})")
            check(s["firstSecs"][:2] == ["tdhead", "tdhero"] and s["over"] <= 0, f"[{theme}]   the opener comes straight after the head; no sideways scroll ({s['firstSecs']}, {s['over']}px)")
            mine = [c for c in s["cards"] if c["gid"] in {g["gid"] for g in grp}]
            check(bool(mine) and all(not c["live"] and not c["fin"] and c["logos"] == [away(next(g for g in grp if g["gid"] == c["gid"])), home(next(g for g in grp if g["gid"] == c["gid"]))] and c["pri"][0].startswith("/boards/#g-") for c in mine),
                  f"[{theme}]   that day's cards are as before, now with a logo on each side ({len(mine)} cards)")
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"today_pre_{theme}.png"))
            await ctx.close()
            # ---- in play: forty minutes in, ESPN says 14-10 ----
            sb = board({g["gid"]: ("in", 14 if g is G0 else 3, 10 if g is G0 else 7, "5:32 - 2nd") for g in grp})
            pg, ctx, errs, asked = await open_(theme, k1 + 40 * 60e3, sb); s = await pg.evaluate(READ); h = s["hero"]; c0 = next((c for c in s["cards"] if c["gid"] == G0["gid"]), None)
            check(bool(h) and h["gid"] == G0["gid"] and h["st"] == "in" and h["mid"].replace("–", "-") == "14-10" and h["small"] == "5:32 - 2nd" and h["href"] == f"/live/#lv-{G0['gid']}" and h["wx"] == "" and not errs,
                  f"[{theme}] forty minutes in the opener is the game in play: the score away-home, the clock, a tap to Live ({h and (h['mid'], h['small'], h['href'])}; {errs[:1]})")
            check(bool(c0) and c0["live"] and not c0["fin"] and "LIVE" in c0["chip"] and "14–10" in c0["chip"] and c0["pri"] == [f"/live/#lv-{G0['gid']}", "Follow live"] and c0["looks"] == 0 and not c0["bp"] and c0["build"] == 0,
                  f"[{theme}]   its card says LIVE with the score, its main button follows it live, and its looks, parlay and builder link are gone ({c0 and (c0['chip'], c0['pri'], c0['looks'], c0['bp'], c0['build'])})")
            check(any(f"/live/#lv-{G0['gid']}" in x and "14" in x for x in s["strip"]) and len(s["strip"]) >= len(grp) and asked.count("sb") >= 1, f"[{theme}]   the scoreboard strip is up with every game in play, from the one ESPN read the page makes ({len(s['strip'])} chips, {asked.count('sb')} scoreboard requests in the first seconds)")
            await ctx.close()
            # ---- over: the Final card ----
            A, Hm = 20, 27; fzT = GT["fz"]; lk = fzT.get("looks") or []
            sb = board({g["gid"]: (("post", A, Hm, "Final") if g is GT else ("in", 3, 7, "9:10 - 4th")) for g in grp})
            SKEY = {"Passing Yards": ("passing", "passingYards"), "Passing TDs": ("passing", "passingTouchdowns"), "Rushing Yards": ("rushing", "rushingYards"), "Receptions": ("receiving", "receptions"), "Receiving Yards": ("receiving", "receivingYards"), "Longest Reception": ("receiving", "longReception")}
            cats = {"passing": ["passingYards", "passingTouchdowns", "interceptions"], "rushing": ["rushingYards", "rushingTouchdowns"], "receiving": ["receptions", "receivingYards", "receivingTouchdowns", "longReception"]}
            # the fake box score: the first look's player clears his line, the second falls one short, anyone else is left out of it
            rows = {c: {} for c in cats}
            for i, l in enumerate(lk[:2]):
                m = l["m"]; td = m.endswith("TD") and "Passing" not in m
                if m not in SKEY and not td and m != "Rush + Rec Yards": continue
                need = (2 if m == "2+ TD" else 3 if m == "3+ TD" else 1) if td else int(math.floor(float(l["ln"]) + 0.5)); val = need if i == 0 else max(0, need - 1)
                if td: rows["rushing"].setdefault(l["pl"], {}).update({"rushingTouchdowns": val})
                elif m == "Rush + Rec Yards": rows["rushing"].setdefault(l["pl"], {}).update({"rushingYards": val})
                else: rows[SKEY[m][0]].setdefault(l["pl"], {}).update({SKEY[m][1]: val})
            for j in range(12): rows["receiving"][f"Filler Player {j}"] = {"receptions": 1, "receivingYards": 5}
            box = {"boxscore": {"players": [{"statistics": [{"name": c, "keys": cats[c], "athletes": [{"athlete": {"displayName": n}, "stats": [str(v.get(k, 0)) for k in cats[c]]} for n, v in rows[c].items()]} for c in cats]}]}}
            # what each look must then read, by this file's own reading of that box score
            def got(pl, cat, key): return float((rows[cat].get(pl) or {}).get(key, 0))
            want = []
            for l in lk:
                m = l["m"]; pl = l["pl"]; td = m.endswith("TD") and "Passing" not in m and m != "First TD"
                if not any(pl in rows[c] for c in cats) or (m not in SKEY and not td and m != "Rush + Rec Yards"): want.append(("", pl, "no stat line")); continue
                if td: n = int(got(pl, "rushing", "rushingTouchdowns") + got(pl, "receiving", "receivingTouchdowns")); need = 2 if m == "2+ TD" else 3 if m == "3+ TD" else 1; want.append(("hit" if n >= need else "miss", pl, f"{n} TD" + ("" if n == 1 else "s"))); continue
                v = got(pl, "rushing", "rushingYards") + got(pl, "receiving", "receivingYards") if m == "Rush + Rec Yards" else got(pl, *SKEY[m])
                want.append(("hit" if v >= int(math.floor(float(l["ln"]) + 0.5)) else "miss", pl, f"{v:g}"))
            pg, ctx, errs, asked = await open_(theme, k1 + 3.4 * 3600e3, sb, box); await pg.wait_for_timeout(600); s = await pg.evaluate(READ); cT = next((c for c in s["cards"] if c["gid"] == GT["gid"]), None)
            aw, ho = away(GT), home(GT)
            check(bool(cT) and cT["fin"] and not cT["live"] and "FINAL" in cT["chip"] and cT["fsc"] and cT["fsc"]["txt"] == [[aw, str(A), False], [ho, str(Hm), True]] and cT["fsc"]["logos"] == [aw, ho] and not cT["stats"] and cT["looks"] == 0 and cT["pri"] == [f"/live/#box-{GT['gid']}", "Box score and plays"] and not errs,
                  f"[{theme}] when ESPN calls it final the card is a Final card: {aw} {A}, {ho} {Hm} with the winner marked, logos, a button to the box score, and no pre-game strip or looks ({cT and (cT['fsc'], cT['pri'])}; {errs[:1]})")
            # the calls, worked out here from the frozen copy
            mA = fzT["pa"] if aw == GT["a"] else fzT["pb"]; mH = fzT["pb"] if ho == GT["b"] else fzT["pa"]; mm = mH - mA; am = Hm - A; exp = []
            sgn = lambda x: "PK" if not x else ("+" if x > 0 else "−") + f"{abs(x):g}"
            if abs(mm) < 0.5: exp.append(["", "Winner", "Model had it a toss-up", f"{ho} won by {am}"])
            else: exp.append(["hit" if (am > 0) == (mm > 0) else "miss", "Winner", f"Model had {ho if mm > 0 else aw} by {abs(mm):.1f}", f"{ho} won by {am}"])
            if fzT.get("sp") is not None and fzT.get("home") == ho and abs(mm + fzT["sp"]) >= 0.05:
                sp = fzT["sp"]; side = ho if (mm + sp) > 0 else aw; cov = am + sp
                exp.append(["push" if cov == 0 else "hit" if (cov > 0) == (side == ho) else "miss", "Spread", "Model leaned " + (f"{ho} {sgn(sp)}" if side == ho else f"{aw} {sgn(-sp)}"), "It landed on the number" if cov == 0 else f"{ho if cov > 0 else aw} covered by {abs(cov):g}"])
            if fzT.get("tot") is not None and abs(mA + mH - fzT["tot"]) >= 0.05:
                tot = fzT["tot"]; over = (mA + mH) > tot; pts = A + Hm
                exp.append(["push" if pts == tot else "hit" if (pts > tot) == over else "miss", "Total", f"Model leaned {'over' if over else 'under'} {tot:g}", f"{pts} points"])
            check(bool(cT) and cT["calls"] == exp and "last copy before kickoff" in cT["note"], f"[{theme}]   the model's call is graded against the score from the copy frozen before kickoff: {[(e[0] or 'even', e[1]) for e in exp]} (page: {cT and cT['calls']})")
            if lk:
                if cT and not cT["flkOpen"]:
                    await pg.evaluate("(g) => document.querySelector('#td-' + g + ' .flt').click()", GT["gid"]); await pg.wait_for_timeout(900); s = await pg.evaluate(READ); cT = next((c for c in s["cards"] if c["gid"] == GT["gid"]), None)
                nh = sum(1 for w in want if w[0] == "hit"); ng = sum(1 for w in want if w[0]); no = len(want) - ng
                tail = (f"{nh} of {ng} hit" + (f" · {no} not graded" if no else "")) if ng else "not graded"
                check(bool(cT) and cT["flkOpen"] and [list(x) for x in want] == cT["flk"] and tail in (cT["flt"] or "") and asked.count("sm") == 1,
                      f"[{theme}]   its {len(lk)} frozen looks are graded from the box score - one request - a cleared line a hit, one short a miss, a man with no line left open ({cT and cT['flk']}; '{tail}'; {asked.count('sm')} box-score requests)")
            else: skip(f"[{theme}] {GT['gid']} had no looks frozen, so there is nothing to grade on its Final card")
            day = [c["gid"] for c in s["cards"] if c["vis"]]; h = s["hero"]
            tF = k1 + 3.4 * 3600e3
            def st_of(g): return ("post" if g is GT else "in") if g in grp else "post" if (g.get("fin") or tF >= g["ko"] + 4.5 * 3600e3) else "in" if tF >= g["ko"] else "pre"
            inplay = [g for g in games if st_of(g) == "in"]; coming = [g for g in games if st_of(g) == "pre"]; expg = (inplay or coming or [None])[0]
            check((h is None and expg is None) or (bool(h) and expg is not None and h["gid"] == expg["gid"] and h["gid"] != GT["gid"] and h["st"] == ("in" if inplay else "pre")), f"[{theme}]   the opener has moved on: a game still in play first, else the next one ({h and (h['gid'], h['st'])} against {expg and expg['gid']})")
            if len(grp) > 1:
                fins = [i for i, c in enumerate(s["cards"]) if c["fin"]]; others = [i for i, c in enumerate(s["cards"]) if not c["fin"]]
                check(not others or not fins or min(fins) > max(i for i in others), f"[{theme}]   finished games sit under the ones in play and still to come ({[(c['gid'], 'fin' if c['fin'] else 'live' if c['live'] else 'pre') for c in s['cards']][:6]})")
            check(s["over"] <= 0, f"[{theme}]   no sideways scroll ({s['over']}px)")
            if SHOTS:
                await pg.evaluate("(g) => { var c = document.getElementById('td-' + g), b = document.getElementById('tdallb'); if(c && c.classList.contains('tdx') && b && b.getAttribute('aria-expanded') !== 'true') b.click(); if(c){ c.scrollIntoView(); window.scrollBy(0, -150); } }", GT["gid"]); await pg.wait_for_timeout(300); await pg.screenshot(path=os.path.join(SHOTS, f"today_final_{theme}.png"))
            await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
