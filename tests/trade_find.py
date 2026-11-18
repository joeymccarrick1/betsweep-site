"""Trade calculator, "Find a player" (owner 11/18: "look for a player and see who I should attach in a trade for each league ...
someone reach out that they wanted to trade me Jaxon Smith-Njigba ... I want to be able to see which players I could send him").
Sleeper is mocked (the sandbox cannot reach it): one account in four leagues drafted from the page's own player list - a ten-team
redraft league and a twelve-team dynasty superflex TE-premium league where another roster has the player, a league where the reader
has him, and a league where nobody does. Every number on the page is checked against values read from the calculator itself in
that league's format and against a lineup worked out here. Needs a built site (gp/site)."""
import asyncio, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8871
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)
FAIR = {1: (0.90, 1.12), 2: (0.98, 1.25), 3: (1.06, 1.36)}
FLEX = {"FLEX": ["RB", "WR", "TE"], "WRRB_FLEX": ["RB", "WR"], "REC_FLEX": ["WR", "TE"], "SUPER_FLEX": ["QB", "RB", "WR", "TE"]}
SLOTS_A = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX"]; SLOTS_B = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "SUPER_FLEX"]

def draft(players, n, need):
    pools = {k: [p for p in players if p["pos"] == k] for k in need}; ros = {i: [] for i in range(1, n + 1)}
    for k, c in need.items():
        for rnd in range(c):
            for rid in (range(1, n + 1) if rnd % 2 == 0 else range(n, 0, -1)):
                if pools[k]: ros[rid].append(pools[k].pop(0))
    return ros

def lineup(names, vals, slots):
    """the page's rule, worked out here: best available by points a game, fixed slots first, then the flex slots narrowest first"""
    pool = sorted([vals[n] for n in names if n in vals and vals[n]["Re"] > 0 and vals[n]["st"] != "OUT" and vals[n]["adj"] > 0], key=lambda p: -p["adj"]); used = set(); pts = 0.0; st = []
    def take(okp):
        nonlocal pts
        for i, p in enumerate(pool):
            if i in used or p["pos"] not in okp: continue
            used.add(i); pts += p["adj"]; st.append(p["n"]); return
    for s in slots:
        if s not in FLEX: take([s])
    for s in sorted([s for s in slots if s in FLEX], key=lambda s: len(FLEX[s])): take(FLEX[s])
    return pts, st

def leagues(players, target):
    rest = [p for p in players if p["n"] != target["n"]]
    def mk(lid, name, n, kind, rp, sc, need, where):
        ros = draft(rest, n, need)
        if where: ros[where].append(target)
        R = [{"roster_id": i, "owner_id": f"u{i}", "players": [p["id"] for p in ros[i]], "settings": {"wins": max(0, 10 - i), "losses": min(10, i), "ties": 0, "fpts": 1300 - 25 * i, "fpts_decimal": 0}} for i in ros]
        L = {"league_id": lid, "name": name, "total_rosters": n, "status": "in_season", "season": "2026", "settings": {"type": kind, "playoff_teams": 6, "playoff_week_start": 15, "draft_rounds": 4},
             "scoring_settings": sc, "roster_positions": rp + ["BN"] * 8}
        U = [{"user_id": f"u{i}", "display_name": f"Team {i}", "metadata": {"team_name": f"Club {i}"} if i == 3 else {}} for i in ros]
        return {"L": L, "R": R, "U": U, "ros": ros}
    return {
        "LA": mk("LA", "Redraft Ten", 10, 0, SLOTS_A, {"rec": 1}, {"QB": 2, "RB": 5, "WR": 6, "TE": 2}, 3),
        "LB": mk("LB", "League of Ordinary Gentlemen", 12, 2, SLOTS_B, {"rec": 1, "bonus_rec_te": 0.5}, {"QB": 3, "RB": 6, "WR": 7, "TE": 3}, 3),
        "LC": mk("LC", "Mine Here", 10, 0, SLOTS_A, {"rec": 0.5}, {"QB": 2, "RB": 5, "WR": 6, "TE": 2}, 1),
        "LD": mk("LD", "Nobody Has Him", 10, 0, SLOTS_A, {"rec": 1}, {"QB": 2, "RB": 5, "WR": 6, "TE": 2}, 0)}

# LB's traded picks: the reader (roster 1) holds roster 5's 2027 first and has sent his own 2027 second to roster 4
TRADED = [{"season": "2027", "round": 1, "roster_id": 5, "owner_id": 1, "previous_owner_id": 5}, {"season": "2027", "round": 2, "roster_id": 1, "owner_id": 4, "previous_owner_id": 1}]

FMT_JS = r"""(f) => { const set = (id, v, chk) => { const e = document.getElementById(id); if(chk){ if(e.checked !== v){ e.checked = v; e.dispatchEvent(new Event('change', {bubbles: true})); } } else if(e.value !== String(v)){ e.value = String(v); e.dispatchEvent(new Event('change', {bubbles: true})); } };
  set('dyn', f.dyn, true); set('sf', f.sf, true); set('tep', f.tep); set('ppr', f.ppr); set('teams', f.teams);
  const o = {}; window.__BS.players.forEach(p => { o[p.n] = {n: p.n, pos: p.pos, v: p.v, adj: p.adj, Re: p.Re, st: p.st}; }); return o; }"""
READ_JS = r"""() => { const de = document.documentElement, box = document.querySelector('#fpOut');
  const num = s => +String(s).replace(/[^0-9.\-−]/g, '').replace('−', '-');
  return {who: (box.querySelector('.fpwho b') || {}).textContent || '', sum: (box.querySelector('.fpsum') || {}).innerText || '', busy: !!box.querySelector('.fpsum.busy'), none: (box.querySelector(':scope > .fpnone') || {}).innerText || '',
    blocks: [...box.querySelectorAll('.fpl')].map(b => ({id: b.dataset.id, open: b.classList.contains('open'), name: b.querySelector('.fplh b').textContent, sub: b.querySelector('.fplh small').textContent, meta: (b.querySelector('.fpmeta') || {}).innerText || '', none: (b.querySelector('.fpnone') || {}).innerText || '',
      offers: [...b.querySelectorAll('.fpo > li')].map(li => ({parts: [...li.querySelectorAll('.fpp li')].map(p => ({pos: p.querySelector('.pos').textContent, n: p.querySelector('.nm').textContent, v: num(p.querySelector('.vv').textContent)})),
        sum: num(li.querySelector('.fpt b').textContent), line: li.querySelector('.fpt').innerText, x: li.querySelector('.fpx').innerText, mine: num(li.querySelectorAll('.fpx b')[0].textContent), theirs: num(li.querySelectorAll('.fpx b')[1].textContent), btn: li.querySelector('.fpgo').getBoundingClientRect().height}))})),
    also: [...box.querySelectorAll('.fpalso')].map(p => [p.dataset.kind, p.innerText]), hint: !document.querySelector('#fpHint').hidden, over: de.scrollWidth - de.clientWidth,
    tabs: [...document.querySelectorAll('#tcTabs .tab')].map(t => [t.dataset.t, t.textContent.trim(), t.classList.contains('on')]), tabOver: (h => h.scrollWidth - h.clientWidth)(document.querySelector('#tcTabs')), tab: (document.querySelector('#tcTabs .tab.on') || {dataset: {}}).dataset.t}; }"""

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{PORT}"
    async with async_playwright() as p:
        b = await p.chromium.launch()
        # ---- the calculator's own numbers, one format at a time (no Sleeper): what every league below must agree with ----
        c0 = await b.new_context(viewport={"width": 390, "height": 844}); await c0.route("**/*supabase*/**", lambda r: r.abort()); await c0.route("**/api.sleeper.app/**", lambda r: r.abort()); p0 = await c0.new_page()
        await p0.goto(base + "/trade/", wait_until="domcontentloaded"); await p0.wait_for_timeout(900)
        VA = await p0.evaluate(FMT_JS, {"dyn": False, "sf": False, "tep": 0, "ppr": 1, "teams": 10})
        VB = await p0.evaluate(FMT_JS, {"dyn": True, "sf": True, "tep": 0.5, "ppr": 1, "teams": 12})
        VC = await p0.evaluate(FMT_JS, {"dyn": False, "sf": False, "tep": 0, "ppr": 0.5, "teams": 10})
        VD = await p0.evaluate(FMT_JS, {"dyn": False, "sf": False, "tep": 0, "ppr": 1, "teams": 12})   # the page's own default, for the no-league checks
        players = sorted([{"id": "m%d" % i, **v} for i, v in enumerate(VA.values()) if v["Re"] > 0 and v["st"] != "OUT" and v["adj"] > 0 and v["v"] > 0], key=lambda x: -x["v"])
        await c0.close(); check(len(players) >= 260, f"the page's own player list drafts the mock leagues ({len(players)} healthy players with a value)")
        target = next((x for x in players if x["n"] == "Jaxon Smith-Njigba"), None) or next(x for x in players if x["pos"] == "WR")
        check(VB[target["n"]]["v"] > 0 and VB[target["n"]]["v"] != VA[target["n"]]["v"], f"target {target['n']}: {VA[target['n']]['v']:,} in the redraft format, {VB[target['n']]['v']:,} in dynasty superflex")
        LG = leagues(players, target); pm = {x["id"]: {"full_name": x["n"], "position": x["pos"], "team": ""} for x in players}; idn = {x["id"]: x["n"] for x in players}
        mine = {k: [x["n"] for x in LG[k]["ros"][1]] for k in LG}; theirs = {k: [x["n"] for x in LG[k]["ros"][3]] for k in LG}

        async def session(theme, user=True, hash_=""):
            asked = []; ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            if user: await ctx.add_init_script("try{localStorage.setItem('bs_sleeper_user','mock')}catch(e){}")
            async def api(route):
                u = route.request.url.split("/v1/")[1]; asked.append(u); m = re.match(r"league/([^/]+)/(rosters|users|traded_picks|matchups/(\d+))", u)
                if u == "state/nfl": body = {"season": "2026", "week": 11}
                elif u.startswith("user/") and "/leagues/" in u: body = [LG[k]["L"] for k in ("LA", "LB", "LC", "LD")]
                elif u.startswith("user/"): body = {"user_id": "u1", "username": "mock"}
                elif u == "players/nfl": body = pm
                elif m and m.group(2) == "rosters": body = LG[m.group(1)]["R"]
                elif m and m.group(2) == "users": body = LG[m.group(1)]["U"]
                elif m and m.group(2) == "traded_picks": body = TRADED if m.group(1) == "LB" else []
                elif m: n = len(LG[m.group(1)]["R"]); w = int(m.group(3)); ids = list(range(1, n + 1)); ids = ids[w % (n - 1) + 1:] + ids[:w % (n - 1) + 1]; body = [{"roster_id": ids[i], "matchup_id": i // 2 + 1} for i in range(n)]
                else: body = {}
                await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
            await ctx.route("**/api.sleeper.app/v1/**", api); await ctx.route("**/*supabase*/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(base + "/trade/" + hash_, wait_until="domcontentloaded"); await pg.wait_for_timeout(900)
            return ctx, pg, errs, asked
        async def settled(pg):   # the league on screen is in and the all-leagues read has finished
            await pg.wait_for_selector("#lgbar .lgcur", timeout=15000)
            await pg.wait_for_function("(() => { const a = document.querySelector('#allg'); return a && !a.hidden && !a.classList.contains('busy'); })()", timeout=30000); await pg.wait_for_timeout(300)
        async def search(pg, text, name):
            await pg.click("#inF"); await pg.fill("#inF", ""); await pg.type("#inF", text, delay=20); await pg.wait_for_selector("#sugF:not([hidden]) button", timeout=4000)
            sugs = await pg.evaluate("[...document.querySelectorAll('#sugF button')].map(b => b.innerText.replace(/\\s+/g, ' '))")
            i = next((j for j, s in enumerate(sugs) if name in s), -1)
            if i >= 0: await pg.evaluate(f"document.querySelectorAll('#sugF button')[{i}].dispatchEvent(new MouseEvent('mousedown', {{bubbles: true, cancelable: true}}))")
            return sugs, i
        async def done(pg):
            await pg.wait_for_function("(() => { const s = document.querySelector('#fpOut .fpsum'); return s && !s.classList.contains('busy'); })()", timeout=20000); await pg.wait_for_timeout(200)

        for theme in ("dark", "light"):
            ctx, pg, errs, asked = await session(theme); await settled(pg)
            before = await pg.evaluate("(() => { const o = {}; window.__BS.players.slice(0, 60).forEach(p => { o[p.n] = [p.v, Math.round(p.adj * 1000)]; }); return o; })()")
            d = await pg.evaluate(READ_JS)
            check([t[0] for t in d["tabs"]] == ["calc", "league", "find", "rank"] and d["tabs"][2][1] == "Find a player", f"{theme}: four tabs, the third is 'Find a player' ({[t[1] for t in d['tabs']]})")
            check(d["tabOver"] <= 2, f"{theme}: the four tabs fit a phone's width without sliding (overflow {d['tabOver']}px)")
            await pg.click('#tcTabs .tab[data-t="find"]'); await pg.wait_for_timeout(200); d = await pg.evaluate(READ_JS)
            check(d["tab"] == "find" and d["hint"] and not d["blocks"], f"{theme}: the tab opens on a search box and one line saying what it does")
            mark = len(asked)
            sugs, i = await search(pg, "jsn" if target["n"] == "Jaxon Smith-Njigba" else target["n"].split()[-1][:5], target["n"])
            check(i >= 0, f"{theme}: typing {'his initials (jsn)' if target['n'] == 'Jaxon Smith-Njigba' else 'part of his name'} lists him ({sugs[:3]})")
            await done(pg); d = await pg.evaluate(READ_JS); new = asked[mark:]
            if os.environ.get("SHOT"):
                await pg.evaluate("document.querySelector('#fp').scrollIntoView({block: 'start'}); window.scrollBy(0, -110)"); await pg.wait_for_timeout(250); await pg.screenshot(path=os.path.join(os.environ["SHOT"], f"find_{theme}.png"), full_page=False)
                await pg.screenshot(path=os.path.join(os.environ["SHOT"], f"find_{theme}_full.png"), full_page=True)
            by = {x["id"]: x for x in d["blocks"]}
            check(d["who"] == target["n"] and not d["hint"], f"{theme}: his name heads the results and the hint steps aside")
            check(set(by) == {"LA", "LB"} and [x["id"] for x in d["blocks"]] == ["LA", "LB"], f"{theme}: one block for each league where another roster has him, in Sleeper's order ({[x['name'] for x in d['blocks']]})")
            check("2 of your 4 leagues" in d["sum"], f"{theme}: the count line: {d['sum']!r}")
            also = dict(d["also"])
            check("Mine Here" in also.get("mine", "") and "Nobody Has Him" in also.get("fa", "") and "none" not in also and "err" not in also, f"{theme}: 'On your roster in: Mine Here' and 'Free agent in: Nobody Has Him', one line each ({d['also']})")
            check(str(f"{VC[target['n']]['v']:,}") in also.get("mine", ""), f"{theme}: the league where he is the reader's shows his value in that league's half-PPR format ({VC[target['n']]['v']:,})")
            check(by["LA"]["open"] and not by["LB"]["open"], f"{theme}: the league on screen opens by itself, the other waits for a tap")
            await pg.click('#fpOut .fpl[data-id="LB"] .fplh'); await pg.wait_for_timeout(150); d = await pg.evaluate(READ_JS); by = {x["id"]: x for x in d["blocks"]}
            check(by["LB"]["open"] and by["LA"]["open"], f"{theme}: a tap opens the second league and leaves the first open")
            for k, V, slots, team, fmt in (("LA", VA, SLOTS_A, "Club 3", "redraft"), ("LB", VB, SLOTS_B, "Club 3", "dynasty, superflex, TE premium")):
                blk = by[k]; T = V[target["n"]]["v"]
                check(team in blk["sub"] and "has him" in blk["sub"] and team in blk["meta"] and f"{T:,}" in blk["meta"] and f"({fmt})" in blk["meta"], f"{theme} {k}: '{blk['meta'][:110]}' - the team's own name, his value in this league's format ({T:,}, {fmt})")
                offs = blk["offers"]; check(1 <= len(offs) <= 4, f"{theme} {k}: {len(offs)} offers listed (one to four)")
                held = set(mine[k]); okp = oks = okb = okv = True; leads = {}
                for o in offs:
                    n = len(o["parts"]); s = 0
                    for q in o["parts"]:
                        if q["pos"] == "PK":
                            okp &= (k == "LB") and ("2027 2nd" not in q["n"] or "your" not in q["n"]); s += q["v"]; continue
                        okp &= q["n"] in held; okv &= (V[q["n"]]["v"] == q["v"]); s += q["v"]
                    oks &= (s == o["sum"]); okb &= FAIR[n][0] - 1e-9 <= o["sum"] / T <= FAIR[n][1] + 1e-9; leads[o["parts"][0]["n"]] = leads.get(o["parts"][0]["n"], 0) + 1
                check(okp, f"{theme} {k}: every piece offered is on the reader's own roster in that league (or a pick he holds)")
                check(okv, f"{theme} {k}: every piece carries its value in that league's format")
                check(oks, f"{theme} {k}: each offer's total is the sum of its pieces")
                check(okb, f"{theme} {k}: every total sits in the fair band for its size ({[round(o['sum'] / T, 2) for o in offs]} of his {T:,})")
                names = [set(q["n"] for q in o["parts"]) for o in offs]
                check(max(leads.values()) <= 2 and all(len(names[i] & names[j]) < 2 for i in range(len(names)) for j in range(i)), f"{theme} {k}: no main piece in more than two offers, and no two offers share two pieces")
                check(all(max(q["v"] for q in o["parts"]) <= T * 0.97 + 1e-9 for o in offs if len(o["parts"]) > 1), f"{theme} {k}: no two- or three-piece offer leads with a player worth as much as him ({[[q['v'] for q in o['parts']] for o in offs]})")
                # the two lineups, worked out here from the calculator's own points a game in this format
                o = offs[0]; give = [q["n"] for q in o["parts"] if q["pos"] != "PK"]
                m0, _ = lineup(mine[k], V, slots); m1, _ = lineup([x for x in mine[k] if x not in give] + [target["n"]], V, slots)
                t0, _ = lineup(theirs[k], V, slots); t1, st1 = lineup([x for x in theirs[k] if x != target["n"]] + give, V, slots)
                check(abs((m1 - m0) - o["mine"]) <= 0.06 and abs((t1 - t0) - o["theirs"]) <= 0.06, f"{theme} {k}: first offer's lineup numbers match a lineup worked out here (yours {o['mine']:+.1f} vs {m1 - m0:+.2f}; theirs {o['theirs']:+.1f} vs {t1 - t0:+.2f})")
                starters = [g for g in give if g in st1]
                check(all(g in o["x"] for g in starters) and (("start" in o["x"]) == bool(starters)), f"{theme} {k}: 'starts there' names exactly the pieces that make the other lineup ({starters or 'none'}): {o['x'][:120]!r}")
                check(all(x["btn"] >= 40 for x in offs), f"{theme} {k}: every 'Open in the calculator' button is at least 40px tall")
                order = [o2["mine"] for o2 in offs]; check(len(offs) < 2 or order[0] >= min(order) - 1e-9, f"{theme} {k}: offers listed ({order} points a week for the reader, first to last)")
            fp = await pg.evaluate("(() => { const r = window.__bsFind.res; const o = {}; Object.keys(r).forEach(k => { o[k] = {kind: r[k].kind, np: r[k].np, picks: r[k].picks || [], thin: r[k].thin || []}; }); return o; })()")
            check(fp["LA"]["picks"] == [] and any("2027 1st (Team 5's)" in x for x in fp["LB"]["picks"]) and any(x == "your 2027 1st" for x in fp["LB"]["picks"]) and not any(x == "your 2027 2nd" for x in fp["LB"]["picks"]) and any(x == "your 2028 2nd" for x in fp["LB"]["picks"]),
                  f"{theme}: picks count only in the dynasty league and only the ones he holds - his own firsts, Team 5's 2027 first, not the 2027 second he traded away ({fp['LB']['picks']})")
            exp = {"league/LB/users", "league/LB/traded_picks"}
            check(set(new) == exp and len(new) == 2, f"{theme}: the search asked Sleeper for two things only - names and pick ownership in the league not on screen (rosters were already read): {new}")
            after = await pg.evaluate("(() => { const o = {}; window.__BS.players.slice(0, 60).forEach(p => { o[p.n] = [p.v, Math.round(p.adj * 1000)]; }); return o; })()")
            check(after == before, f"{theme}: the calculator's own values are back in the on-screen league's format after reading the others")
            check(d["over"] <= 0, f"{theme}: nothing wider than the phone screen (overflow {d['over']}px)")
            # a second player: rosters come from memory
            mark = len(asked); qb = next(x for x in players if x["pos"] == "QB" and x["n"] in theirs["LB"] and x["n"] in theirs["LA"]) if any(x["pos"] == "QB" and x["n"] in theirs["LB"] and x["n"] in theirs["LA"] for x in players) else next(x for x in players if x["pos"] == "QB" and x["n"] not in mine["LB"])
            sugs, i = await search(pg, qb["n"].split()[-1][:6], qb["n"]); await done(pg); d2 = await pg.evaluate(READ_JS); by2 = {x["id"]: x for x in d2["blocks"]}
            check(i >= 0 and d2["who"] == qb["n"] and not [u for u in asked[mark:] if u.endswith("/rosters")], f"{theme}: a second search ({qb['n']}) reads no roster again ({asked[mark:]})")
            if "LB" in by2 and "LA" in by2:
                check(f"{VB[qb['n']]['v']:,}" in by2["LB"]["meta"] and f"{VA[qb['n']]['v']:,}" in by2["LA"]["meta"] and VB[qb["n"]]["v"] > VA[qb["n"]]["v"], f"{theme}: a quarterback is worth more in the superflex league ({VB[qb['n']]['v']:,}) than the 1QB league ({VA[qb['n']]['v']:,}), each shown in its own block")
            # load an offer: the calculator switches to that league and holds both sides
            await search(pg, target["n"].split()[-1][:5], target["n"]); await done(pg)
            if not await pg.evaluate("document.querySelector('#fpOut .fpl[data-id=\"LB\"]').classList.contains('open')"): await pg.click('#fpOut .fpl[data-id="LB"] .fplh'); await pg.wait_for_timeout(150)
            d3 = await pg.evaluate(READ_JS); o = {x["id"]: x for x in d3["blocks"]}["LB"]["offers"][0]
            await pg.click('#fpOut .fpl[data-id="LB"] .fpo > li:first-child .fpgo'); await pg.wait_for_timeout(900)
            c = await pg.evaluate("(() => ({tab: document.querySelector('#tcTabs .tab.on').dataset.t, a: [...document.querySelectorAll('#sideA li .who b')].map(b => b.firstChild.textContent.trim()), b: [...document.querySelectorAll('#sideB li .who b')].map(b => b.firstChild.textContent.trim()), fmt: document.querySelector('#fmtSum').textContent, bar: document.querySelector('#lgbar .lgcur b').textContent, verdict: document.querySelector('#verdict h3').textContent, ta: document.querySelector('#sideA .tot b').textContent}))()")
            check(c["tab"] == "calc" and c["b"] == [target["n"]] and len(c["a"]) == len(o["parts"]) and c["bar"] == "League of Ordinary Gentlemen" and c["fmt"].startswith("Dynasty · Superflex"), f"{theme}: 'Open in the calculator' loads the offer - Side A {c['a']}, Side B {c['b']}, format '{c['fmt']}', league bar '{c['bar']}'")
            check(int(c["ta"].replace(",", "")) == o["sum"], f"{theme}: Side A's total in the calculator ({c['ta']}) is the total the offer showed ({o['sum']:,})")
            T = VB[target["n"]]["v"]; gap = abs(o["sum"] - T) / max(o["sum"], T); exp = "Fair trade" if gap < 0.05 else ("Side A" if o["sum"] > T else "Side B") + f" gives {round(abs(o['sum'] - T) / min(o['sum'], T) * 100)}% more"
            check(c["verdict"] == exp and "wins" not in c["verdict"], f"{theme}: the calculator's headline says who gives more, not who 'wins' ('{c['verdict']}')")
            check(not errs, f"{theme}: no script errors ({errs[:2]})")
            await ctx.close()

        # no Sleeper account on the device: the tab still answers, and says what it needs
        ctx, pg, errs, asked = await session("dark", user=False); await pg.click('#tcTabs .tab[data-t="find"]'); sugs, i = await search(pg, target["n"].split()[-1][:5], target["n"]); await pg.wait_for_timeout(300); d = await pg.evaluate(READ_JS)
        check(i >= 0 and d["who"] == target["n"] and "Sleeper username" in d["none"] and not d["blocks"] and not errs, f"no account: his name, then 'Type your Sleeper username at the top of this page...' ({d['none'][:60]!r})")
        await ctx.close()
        # a link to a player: /trade/#find=Name opens the tab and runs once the leagues are in
        ctx, pg, errs, asked = await session("dark", hash_="#find=" + target["n"].replace(" ", "%20")); await pg.wait_for_selector("#fpOut .fpsum", timeout=15000); await done(pg); d = await pg.evaluate(READ_JS)
        check(d["tab"] == "find" and d["who"] == target["n"] and len(d["blocks"]) == 2 and not errs, f"/trade/#find={target['n']} opens the tab with his results ({len(d['blocks'])} leagues)")
        # a reload in the same visit keeps the player
        await pg.goto(base + "/trade/", wait_until="domcontentloaded"); await pg.wait_for_selector("#fpOut .fpsum", timeout=15000, state="attached"); await done(pg); d = await pg.evaluate(READ_JS); v = await pg.input_value("#inF")
        check(d["who"] == target["n"] and v == target["n"] and len(d["blocks"]) == 2, "a reload in the same visit keeps the player and his results")
        await ctx.close()
        # wide screen: the tab row and the results hold
        ctx = await b.new_context(viewport={"width": 1280, "height": 900}); await ctx.add_init_script("try{localStorage.setItem('bs_sleeper_user','mock')}catch(e){}")
        await ctx.close(); await b.close()
    print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
asyncio.run(main())
