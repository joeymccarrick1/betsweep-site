"""Trade calculator, league view: buy / hold / sell from the standings (owner 11/17: "suggest whether to tank or buy players depending
on record and likelihood of making playoffs. Make suggestions of who to trade for").
Sleeper is mocked (the sandbox cannot reach it): a ten-team league drafted from the page's own player list, three times -
a contender in a dynasty league, the same roster at 1-9, and that 1-9 team in a redraft league. Needs a built site (gp/site)."""
import asyncio, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site")
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)
OLD = {"QB": 31, "RB": 26, "WR": 28, "TE": 29}

def league(players, me_good, kind):
    """ten rosters by snake draft; roster 1 is the reader. me_good: 8-2 and scoring; else 1-9 with the oldest good players added."""
    need = {"QB": 2, "RB": 5, "WR": 6, "TE": 2}; pools = {k: [p for p in players if p["pos"] == k] for k in need}
    rosters = {i: [] for i in range(1, 11)}
    for k, n in need.items():
        order = list(range(1, 11)); pool = pools[k]
        for rnd in range(n):
            for rid in (order if rnd % 2 == 0 else order[::-1]):
                if pool: rosters[rid].append(pool.pop(0))
    if not me_good:   # hand the reader three old stars from other rosters so there is something to sell
        vets = sorted([p for rid in range(4, 9) for p in rosters[rid] if (p["age"] or 0) >= OLD[p["pos"]] and p["v"] >= 1500], key=lambda p: -p["v"])[:3]
        for p in vets:
            for rid in range(4, 9):
                if p in rosters[rid]: rosters[rid].remove(p)
            rosters[1].append(p)
    rec = {1: (8, 2, 1290) if me_good else (1, 9, 1010), 2: (8, 2, 1270), 3: (7, 3, 1250), 4: (6, 4, 1220), 5: (6, 4, 1200), 6: (5, 5, 1180), 7: (4, 6, 1150), 8: (3, 7, 1120), 9: (2, 8, 1060), 10: (1, 9, 1000) if me_good else (8, 2, 1280)}
    R = [{"roster_id": i, "owner_id": f"u{i}", "players": [p["id"] for p in rosters[i]], "settings": {"wins": rec[i][0], "losses": rec[i][1], "ties": 0, "fpts": rec[i][2], "fpts_decimal": 0}} for i in rosters]
    L = {"league_id": f"L{int(me_good)}{kind}", "name": "Mock League", "total_rosters": 10, "status": "in_season", "settings": {"type": kind, "playoff_teams": 6, "playoff_week_start": 15},
         "scoring_settings": {"rec": 1}, "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX"] + ["BN"] * 7}
    U = [{"user_id": f"u{i}", "display_name": f"Team {i}", "metadata": {}} for i in rosters]
    return L, R, U, rosters

async def run(b, theme, players, me_good, kind, auto=False):
    L, R, U, rosters = league(players, me_good, kind); pm = {p["id"]: {"full_name": p["n"], "position": p["pos"], "team": p.get("tm") or ""} for p in players}; asked = []
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
    await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
    if auto: await ctx.add_init_script("try{localStorage.setItem('bs_sleeper_user','mock')}catch(e){}")
    async def api(route):
        u = route.request.url.split("/v1/")[1]; asked.append(u)
        m = re.match(r"league/[^/]+/matchups/(\d+)", u)
        if u == "state/nfl": body = {"season": "2026", "week": 11}
        elif u.startswith("user/") and "/leagues/" in u: body = [L]
        elif u.startswith("user/"): body = {"user_id": "u1", "username": "mock"}
        elif u.endswith("/rosters"): body = R
        elif u.endswith("/users"): body = U
        elif u == "players/nfl": body = pm
        elif m: w = int(m.group(1)); ids = list(range(1, 11)); ids = ids[w % 9 + 1:] + ids[:w % 9 + 1]; body = [{"roster_id": ids[i], "matchup_id": i // 2 + 1} for i in range(10)]
        else: body = {}
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
    await ctx.route("**/api.sleeper.app/v1/**", api); await ctx.route("**/*supabase*/**", lambda r: r.abort())
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    await pg.goto("http://127.0.0.1:8863/trade/" + ("#league" if auto else ""), wait_until="domcontentloaded"); await pg.wait_for_timeout(900)
    if not auto: await pg.fill("#slUser", "mock"); await pg.click("#slGo")
    await pg.wait_for_selector("#olk", timeout=15000); await pg.wait_for_timeout(500)
    d = await pg.evaluate(r"""() => { const o = document.querySelector('#olk'), de = document.documentElement; const lis = h => { const hd = [...o.querySelectorAll('h4')].find(x => x.textContent.indexOf(h) === 0); return hd ? [...hd.nextElementSibling.querySelectorAll('li')].map(li => li.innerText.replace(/\s+/g, ' ')) : []; };
        return {v: o.dataset.v, kind: o.dataset.kind, po: +o.dataset.po, chip: o.querySelector('.vd').textContent, title: o.querySelector('h3').textContent, line: o.querySelector('.olline').innerText, why: o.querySelector('.olwhy').innerText,
                buys: lis('Who to trade for'), sells: lis('Who to sell'), rows: [...o.querySelectorAll('table tr')].map(tr => [...tr.children].map(td => td.textContent)), over: de.scrollWidth - de.clientWidth, top: Math.round(o.getBoundingClientRect().top + scrollY)}; }""")
    if os.environ.get("SHOT"):   # a picture of the card for a human to look at
        await pg.evaluate("document.querySelector('#olk').scrollIntoView({block: 'start'}); window.scrollBy(0, -64)"); await pg.wait_for_timeout(300)
        await pg.screenshot(path=os.path.join(os.environ["SHOT"], f"outlook_{int(me_good)}{kind}_{theme}.png"))
    return pg, ctx, d, errs, asked, rosters

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8863), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch(); c0 = await b.new_context(); p0 = await c0.new_page()
        await p0.goto("http://127.0.0.1:8863/trade/", wait_until="domcontentloaded"); await p0.wait_for_timeout(900)
        players = await p0.evaluate("window.__BS.players.filter(p => p.Re > 0 && p.st !== 'OUT' && p.adj > 0 && p.v > 0).sort((a, b) => b.v - a.v).map((p, i) => ({id: 'm' + i, n: p.n, pos: p.pos, tm: p.tm, age: p.age || null, v: p.v, adj: p.adj}))")
        await c0.close(); check(len(players) >= 200, f"the page's own player list drafts the mock league ({len(players)} healthy players with a value)")
        # ---- 1. contender, dynasty ----
        for theme in ("dark", "light"):
            pg, ctx, d, errs, asked, rosters = await run(b, theme, players, True, 2)
            check(d["v"] in ("buy", "in") and d["chip"] == "Buy" and d["po"] >= 0.7, f"{theme}: 8-2 and first in points reads Buy ({d['title']}; {d['po']:.0%})")
            check("8-2" in d["line"] and "1st of 10 in points" in d["line"] and "6 of 10 get in" in d["line"] and "Week 14" in d["line"], f"{theme}: the line states record, points rank, odds, spots and the last week ({d['line'][:110]})")
            check(any(re.match(r"league/[^/]+/matchups/1[1-4]$", u) for u in asked) and not any(u.endswith("matchups/15") for u in asked), f"{theme}: the weeks left (11-14) are read from the league's schedule ({sorted(u[-2:] for u in asked if 'matchups' in u)})")
            odds = [int(re.sub(r"\D", "", r[3]) or 0) for r in d["rows"]]; check(len(odds) == 10 and abs(sum(odds) - 600) <= 12, f"{theme}: ten teams' odds add up to the six spots ({sum(odds)}%)")
            check(len(d["buys"]) >= 1 and not d["sells"], f"{theme}: a buyer gets targets and no sell list ({len(d['buys'])} targets)")
            src = [int(m.group(1)) for x in d["buys"] for m in [re.search(r"from Team \d+ \((?:under )?(\d+)%\+? to make it\)", x)] if m]; gains = [float(m.group(1)) for x in d["buys"] for m in [re.search(r"\+(\d+\.\d) pts a week", x)] if m]
            check(len(src) == len(d["buys"]) and all(s <= 25 for s in src), f"{theme}: every target sits on a team that is out of it ({src})")
            check(len(gains) == len(d["buys"]) and all(g >= 1 for g in gains) and gains == sorted(gains, reverse=True), f"{theme}: each one lifts the lineup by a point or more, biggest first ({gains})")
            mine = {p["n"] for p in rosters[1]}; names = [re.match(r"(.+?) \(", x).group(1) for x in d["buys"]]; check(not (set(names) & mine), f"{theme}: no target is already on the roster ({names[:3]})")
            await pg.evaluate("document.querySelector('#olk [data-ol]').scrollIntoView({block: 'center'})"); await pg.click("#olk [data-ol]"); await pg.wait_for_timeout(400)
            stt = await pg.evaluate("(() => { for (const k of Object.keys(localStorage)) if (k.indexOf('bs_trade_') === 0) return JSON.parse(localStorage.getItem(k)); return null; })()")
            check(bool(stt) and stt.get("B") == [names[0]], f"{theme}: Load puts the target on the calculator's other side ({stt and stt.get('B')})")
            check(d["over"] <= 0 and not errs, f"{theme}: no sideways scroll, no script errors ({d['over']}, {errs[:1]})")
            if theme == "dark":
                await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_timeout(700); await pg.fill("#slUser", "mock"); await pg.click("#slGo"); await pg.wait_for_selector("#olk", timeout=15000); await pg.wait_for_timeout(400)
                po2 = float(await pg.evaluate("document.querySelector('#olk').dataset.po")); check(po2 == d["po"], f"the same standings give the same odds twice ({po2} = {d['po']})")
            await ctx.close()
        # ---- 2. the same roster at 1-9, dynasty: sell ----
        pg, ctx, d, errs, asked, rosters = await run(b, "dark", players, False, 2)
        check(d["v"] in ("out", "long") and d["chip"] == "Sell" and d["po"] < 0.35, f"1-9 in a dynasty league reads Sell ({d['title']}; {d['po']:.1%})")
        check(len(d["sells"]) >= 1 and not d["buys"], f"a seller gets a sell list and no targets ({len(d['sells'])})")
        to = [int(m.group(1)) for x in d["sells"] for m in [re.search(r"to Team \d+ \((?:under )?(\d+)%\+? to make it\)", x)] if m]; check(len(to) == len(d["sells"]) and all(t >= 50 for t in to), f"every buyer named is a contender ({to})")
        sold = [re.match(r"(.+?) \((\w+), (\d+)\)", x) for x in d["sells"]]; mine = {p["n"]: p for p in rosters[1]}
        check(all(m and m.group(1) in mine for m in sold), f"every player to sell is on the reader's roster ({[m.group(1) for m in sold if m][:3]})")
        check("pick of 10" in d["why"] and "reverse-standings" in d["why"], f"the draft slot it is tracking for is stated ({d['why'][-90:]})")
        ask = [m.group(1) for x in d["sells"] for m in [re.search(r"Ask for .+? \(\w+, (\d+),", x)] if m]; check(all(int(a) <= 25 for a in ask), f"anyone to ask for is 25 or younger ({ask})")
        check(d["over"] <= 0 and not errs, f"sell view: no sideways scroll, no script errors ({d['over']}, {errs[:1]})"); await ctx.close()
        # ---- 3. the same 1-9 team, redraft: nothing to sell ----
        pg, ctx, d, errs, asked, rosters = await run(b, "light", players, False, 0)
        check(d["kind"] == "redraft" and d["v"] in ("out", "long") and d["chip"] in ("Out", "Hold") and not d["sells"] and not d["buys"], f"1-9 in a redraft league is told it is out, with nothing to sell ({d['chip']}: {d['title']})")
        check("Nothing carries over" in d["why"] and "pick" not in d["why"].replace("no pick to play for", ""), f"and why ({d['why'][:80]})")
        check(d["over"] <= 0 and not errs, f"redraft view: no sideways scroll, no script errors ({d['over']}, {errs[:1]})"); await ctx.close()
        # ---- 4. arriving from the Fantasy page's card with a username already on the device: no typing ----
        pg, ctx, d, errs, asked, rosters = await run(b, "dark", players, True, 2, auto=True)
        y = await pg.evaluate("Math.round(document.querySelector('#league').getBoundingClientRect().top)")
        check(d["chip"] == "Buy" and not errs, f"/trade/#league with a saved username imports by itself ({d['title'][:40]})"); check(-200 <= y <= 400, f"and lands on the league section (its top is {y}px from the top of the screen)"); await ctx.close()
        fp = open(os.path.join(ROOT, "team", "index.html"), encoding="utf-8").read(); check('href="/trade/#league"' in fp and "Buy or sell?" in fp, "the Fantasy page carries the Buy or sell? card")
        await b.close()
    srv.shutdown(); print(f"{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
asyncio.run(main())
