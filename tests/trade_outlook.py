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
    L = {"league_id": f"L{int(me_good)}{kind}", "name": "Mock League", "total_rosters": 10, "status": "in_season", "season": "2026", "settings": {"type": kind, "playoff_teams": 6, "playoff_week_start": 15},
         "scoring_settings": {"rec": 1}, "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX"] + ["BN"] * 7}
    U = [{"user_id": f"u{i}", "display_name": f"Team {i}", "metadata": {}} for i in rosters]
    return L, R, U, rosters

async def run(b, theme, players, me_good, kind, auto=False, traded=None):
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
        elif u.endswith("/traded_picks") and traded is not None: body = traded
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
                buys: lis('Who to trade for'), sells: lis('Who to sell'), picks: (o.querySelector('.olpk') || {}).innerText || '', wk: (function(){ const w = o.querySelector('.olwk'); return w ? {sw: +w.dataset.sw, pw: +w.dataset.pw, win: +w.dataset.win, lose: +w.dataset.lose, text: w.innerText.replace(/\s+/g, ' '), cardSw: o.dataset.sw, big: !!w.querySelector('.olsw.big'), after: w.previousElementSibling.className, before: w.nextElementSibling.className} : null; })(), rows: [...o.querySelectorAll('table tr')].map(tr => [...tr.children].map(td => td.textContent)), over: de.scrollWidth - de.clientWidth, top: Math.round(o.getBoundingClientRect().top + scrollY)}; }""")
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
            # 11/18: how much this week matters - the reader's chance to win it, and the playoff odds on each side of the result
            w = d["wk"]
            check(bool(w) and re.search(r"Week 11 vs Team \d+", w["text"]) and w["after"] == "olline" and w["before"] == "olwhy", f"{theme}: under the odds, this week's game against the real opponent ({w and w['text'][:96]})")
            if w:
                check(0.05 < w["pw"] < 0.95 and w["lose"] <= d["po"] <= w["win"] and abs(w["pw"] * w["win"] + (1 - w["pw"]) * w["lose"] - d["po"]) <= 0.01, f"{theme}: win {w['win']:.0%} / lose {w['lose']:.0%} at {w['pw']:.0%} to win averages back to the {d['po']:.0%} on the card")
                check(w["sw"] == round((w["win"] - w["lose"]) * 100) and ((f"{w['sw']}-point week" in w["text"].lower()) if w["sw"] >= 1 else ("no swing" in w["text"].lower())) and str(w["sw"]) == str(w["cardSw"]), f"{theme}: the swing is the gap between the two, in points ({w['sw']}; the card carries {w['cardSw']} for the league list)")
            check(d["over"] <= 0 and not errs, f"{theme}: no sideways scroll, no script errors ({d['over']}, {errs[:1]})")
            if theme == "dark":
                # 11/17 evening: a saved username imports by itself on a return visit; the page comes back on the tab it was left on (the
                # calculator, after Load), so the league is one tap away
                await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_selector(".lgbar .lgcur", timeout=15000); await pg.click('#tcTabs [data-t="league"]'); await pg.wait_for_selector("#olk", timeout=15000); await pg.wait_for_timeout(400)
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
        # ---- 5. who holds which rookie picks (owner 11/17): only a pick the paying side really has is named ----
        TR = [{"season": "2027", "round": 2, "roster_id": 1, "previous_owner_id": 1, "owner_id": 2},     # the reader's 2027 2nd now sits with Team 2
              {"season": "2027", "round": 1, "roster_id": 9, "previous_owner_id": 9, "owner_id": 2},     # Team 2 also holds Team 9's 2027 1st
              {"season": "2028", "round": 1, "roster_id": 10, "previous_owner_id": 10, "owner_id": 1},   # the reader holds Team 10's 2028 1st
              {"season": "2026", "round": 1, "roster_id": 3, "previous_owner_id": 3, "owner_id": 1},     # a draft already held: ignored
              {"season": "2029", "round": 1, "roster_id": 3, "previous_owner_id": 3, "owner_id": 1}]     # further out than the page prices: ignored
        pg, ctx, d, errs, asked, rosters = await run(b, "dark", players, False, 2, traded=TR)
        check(any(u.endswith("/traded_picks") for u in asked), "the league's traded picks are read")
        check(d["picks"].replace("\n", " ").startswith("Your picks 2027: 1st, 3rd · 2028: 1st, 1st (Team 10's), 2nd, 3rd"), f"the card lists the picks the reader holds - his 2027 2nd is gone, Team 10's 2028 1st is his ({d['picks'][:80]})")
        hold = {"Team 2": {"their 2027 1st", "the 2027 1st they hold from Team 9", "their 2027 2nd", "the 2027 2nd they hold from Team 1", "their 2027 3rd", "their 2028 1st", "their 2028 2nd", "their 2028 3rd"}}
        asks = [(re.search(r"to (Team \d+)", x).group(1), m.group(1)) for x in d["sells"] for m in [re.search(r"Ask for ((?:their|the) 20\d\d (?:1st|2nd|3rd)(?: they hold from Team \d+)?) \(", x)] if m]
        generic = [x for x in d["sells"] if "a pick worth about the same" in x]
        check(not generic and all(not (t in hold) or a in hold[t] for t, a in asks) and all(not a.startswith("their 2027 2nd") or t != "Team 1" for t, a in asks), f"a pick asked for is one that buyer holds, named as theirs ({asks[:3] or 'no pick asks this build: every ask was a player'})")
        check(not errs and d["over"] <= 0, f"picks view: no script errors, no sideways scroll ({errs[:1]})"); await ctx.close()
        pg, ctx, d, errs, asked, rosters = await run(b, "light", players, True, 2, traded=TR)
        mine = re.findall(r"A pick of yours worth about the same: ((?:your|the) 20\d\d (?:1st|2nd|3rd)(?: you hold from Team \d+)?) \(", " ".join(d["buys"])); gen = [x for x in d["buys"] if "A pick worth about the same" in x]
        check(not gen and all(m != "your 2027 2nd" for m in mine), f"a buyer is only told to pay with a pick he holds - never the 2027 2nd he traded away ({mine[:3] or 'every offer this build was a bench player'})")
        if mine:
            await pg.evaluate("(() => { const b = [...document.querySelectorAll('#olk li')].find(li => li.innerText.indexOf('A pick of yours') >= 0).querySelector('[data-ol]'); b.click(); })()"); await pg.wait_for_timeout(400)
            stt = await pg.evaluate("(() => { for (const k of Object.keys(localStorage)) if (k.indexOf('bs_trade_') === 0) return JSON.parse(localStorage.getItem(k)); return null; })()")
            check(bool(stt) and len(stt.get("A") or []) == 1 and re.fullmatch(r"20\d\d (early 1st|mid 1st|late 1st|2nd|3rd) round pick", stt["A"][0] or "") is not None, f"Load puts that pick on the calculator as the asset it is priced as ({stt and stt.get('A')})")
        await ctx.close()
        pg, ctx, d, errs, asked, rosters = await run(b, "dark", players, False, 0, traded=TR)
        check(d["picks"] == "" and not errs, "a redraft league has no picks line (nothing carries over)"); await ctx.close()
        pg, ctx, d, errs, asked, rosters = await run(b, "dark", players, False, 2)
        check(d["picks"] == "" and not errs, "when Sleeper gives no pick list the card says nothing about who holds what"); await ctx.close()
        fp = open(os.path.join(ROOT, "team", "index.html"), encoding="utf-8").read(); check('href="/trade/#league"' in fp and "Buy or sell?" in fp, "the Fantasy page carries the Buy or sell? card")
        await b.close()
    srv.shutdown(); print(f"{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
asyncio.run(main())
