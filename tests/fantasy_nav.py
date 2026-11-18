"""Fantasy page and Trade calculator with MANY Sleeper leagues (owner 11/17: "make the fantasy page and trade calculator a little more
intuitive and maybe condensed. It's a lot of scrolling to find what you're looking for. I have a ton of sleeper teams").

Before, at phone size with a 14-league account: Trade calculator 19.6 screens, Fantasy 8.2. Now: a league bar with a sheet behind it
(every league, its record and - on the Trade calculator - buy / hold / sell with playoff odds), one row of section tabs, a saved
username that loads by itself. Sleeper is mocked (the sandbox cannot reach it): 14 leagues drafted from the page's own players.
Needs a built site (gp/site)."""
import asyncio, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8864
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)
NAMES = ["Nashville Dynasty", "Ole Red Redraft", "Berklee Boys SF", "Broadway Bandits", "Work League", "MC3 Dynasty", "Family League", "Titans Up", "High Stakes 12", "Best Ball Mania", "College Buddies", "Devy Dudes", "TE Premium Dynasty", "Guillotine Fun"]

def leagues(players, nl):
    need = {"QB": 2, "RB": 5, "WR": 6, "TE": 2}; out = []
    for li in range(nl):
        n = 12 if li % 3 else 10; pools = {k: [p for p in players if p["pos"] == k] for k in need}
        for k in pools: pools[k] = pools[k][li % 5:] + pools[k][:li % 5]
        ros = {i: [] for i in range(1, n + 1)}
        for k, c in need.items():
            order = list(range(1, n + 1)); order = order[li % n:] + order[:li % n]
            for rnd in range(c):
                for rid in (order if rnd % 2 == 0 else order[::-1]):
                    if pools[k]: ros[rid].append(pools[k].pop(0))
        wl = [(8, 2), (7, 3), (7, 3), (6, 4), (6, 4), (5, 5), (5, 5), (4, 6), (4, 6), (3, 7), (2, 8), (1, 9)][:n]
        mine = wl[(li * 5) % n]; rest = wl[:]; rest.remove(mine); rec = {1: mine}
        for i in range(2, n + 1): rec[i] = rest[i - 2]
        R = [{"roster_id": i, "owner_id": f"u{i}", "players": [p["id"] for p in ros[i]], "starters": [p["id"] for p in ros[i]][:8], "settings": {"wins": rec[i][0], "losses": rec[i][1], "ties": 0, "fpts": 1000 + 30 * rec[i][0], "fpts_decimal": 0}} for i in ros]
        L = {"league_id": f"L{li}", "name": NAMES[li % len(NAMES)], "total_rosters": n, "status": "in_season", "season": "2026", "settings": {"type": 2 if li % 2 == 0 else 0, "playoff_teams": 6, "playoff_week_start": 15},
             "scoring_settings": {"rec": 1 if li % 4 else 0.5, "pass_td": 4}, "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX"] + (["SUPER_FLEX"] if li % 3 == 2 else []) + ["BN"] * 7}
        U = [{"user_id": f"u{i}", "display_name": f"Manager {i}", "metadata": {"team_name": f"Team {i}"}} for i in ros]
        out.append((L, R, U, rec[1]))
    return out

async def session(b, players, theme, nl=14, stored=None, mode=None, tweak=None):
    LS = leagues(players, nl); pm = {p["id"]: {"full_name": p["n"], "first_name": p["n"].split(" ")[0], "last_name": " ".join(p["n"].split(" ")[1:]), "position": p["pos"], "team": p.get("tm") or "", "fantasy_positions": [p["pos"]]} for p in players}; asked = []
    if tweak: tweak(LS, pm)
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
    await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
    if stored: await ctx.add_init_script(f"try{{localStorage.setItem('bs_sleeper_user','{stored}')}}catch(e){{}}")
    if mode: await ctx.add_init_script(f"try{{localStorage.setItem('bs_team_mode','{mode}')}}catch(e){{}}")
    async def api(route):
        u = route.request.url.split("/v1/")[1]; asked.append(u)
        m = re.match(r"league/([^/]+)/(\w+)(?:/(\d+))?", u); L = next((x for x in LS if m and x[0]["league_id"] == m.group(1)), None)
        if u == "state/nfl": body = {"season": "2026", "week": 11, "display_week": 11}
        elif u.startswith("user/") and "/leagues/" in u: body = [x[0] for x in LS]
        elif u.startswith("user/"): body = {"user_id": "u1", "username": "mock", "display_name": "mock"}
        elif u == "players/nfl": body = pm
        elif L and m.group(2) == "rosters": body = L[1]
        elif L and m.group(2) == "users": body = L[2]
        elif L and m.group(2) == "matchups": w = int(m.group(3)); n = L[0]["total_rosters"]; ids = list(range(1, n + 1)); ids = ids[w % (n - 1) + 1:] + ids[:w % (n - 1) + 1]; body = [{"roster_id": ids[i], "matchup_id": i // 2 + 1, "points": 0} for i in range(n)]
        else: body = []
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
    await ctx.route("**/api.sleeper.app/v1/**", api); await ctx.route("**/*supabase*/**", lambda r: r.abort())
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    return ctx, pg, asked, errs, LS

SCR = "Math.round(document.documentElement.scrollHeight / 844 * 10) / 10"
OVER = "document.documentElement.scrollWidth - document.documentElement.clientWidth"
VIS = "(s) => { const e = document.querySelector(s); return !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden'; }"

async def trade(b, players, theme):
    T = f"trade, {theme}"
    ctx, pg, asked, errs, LS = await session(b, players, theme)
    await pg.goto(f"http://127.0.0.1:{PORT}/trade/", wait_until="domcontentloaded"); await pg.wait_for_timeout(800)
    tabs = await pg.evaluate("[...document.querySelectorAll('#tcTabs .tab')].map(b => [b.dataset.t, b.classList.contains('on')])")
    check(tabs == [["calc", True], ["league", False], ["rank", False]] and await pg.evaluate(VIS, "#slUser") and await pg.evaluate(VIS, "#sideA") and not await pg.evaluate(VIS, "#rk"), f"{T}: a new visitor gets three tabs with the calculator open, and the username box at the top")
    h0 = await pg.evaluate(SCR); fm = await pg.evaluate("document.querySelector('#fmtSum').textContent"); check(h0 <= 3 and re.match(r"(Redraft|Dynasty) · (1QB|Superflex) · ", fm) and not await pg.evaluate("document.querySelector('#fmt').open"), f"{T}: the format is one line until asked ({fm}); the page is {h0} screens")
    check("70% the trade market and 30% our model" in await pg.evaluate("document.querySelector('#verdict').innerText"), f"{T}: the empty calculator says what the values are (70% market)")
    await pg.fill("#slUser", "mock"); await pg.click("#slGo"); await pg.wait_for_selector("#olk", timeout=15000); await pg.wait_for_timeout(700)
    bar = await pg.evaluate("document.querySelector('.lgbar .lgcur').innerText.replace(/\\n/g, ' | ')"); n1 = len(asked)
    check(await pg.evaluate("document.querySelector('#tcTabs .tab.on').dataset.t") == "league" and not await pg.evaluate(VIS, "#slUser") and not await pg.evaluate(VIS, "#slLeagues"), f"{T}: importing opens My league; the username box and the wall of league buttons are gone")
    r0 = LS[0][3]; check(bar.startswith("Nashville Dynasty") and f"{r0[0]}-{r0[1]}" in bar and "of 10" in bar and re.search(r"(Buy|Hold|Sell|Out) · ", bar) and "Switch · 14" in bar.replace("SWITCH", "Switch"), f"{T}: the bar names the league, its record and place, the verdict, and how many leagues there are ({bar})")
    h1 = await pg.evaluate(SCR); check(h1 <= 5, f"{T}: the league view is {h1} phone screens (the whole page was 19.6)")
    card = await pg.evaluate("document.querySelector('#olk .vd').textContent + '|' + document.querySelector('#olk').dataset.po"); chip = await pg.evaluate("document.querySelector('.lgbar .lgchip').textContent")
    check(chip.split(" · ")[0] == card.split("|")[0], f"{T}: the bar's chip is the card's verdict ({chip} / {card.split('|')[0]})")
    # the sheet
    await pg.click(".lgbar .lgcur"); await pg.wait_for_selector("#lgov .lgrow"); await pg.wait_for_function("document.querySelectorAll('#lgov .lgrow').length === 14 && ![...document.querySelectorAll('#lgov .lgrc')].some(e => e.textContent.trim() === '…') && document.querySelectorAll('#lgov .lgrow .lgchip').length === 14", timeout=25000)
    rows = await pg.evaluate("[...document.querySelectorAll('#lgov .lgrow')].map(r => [r.querySelector('b').textContent, r.querySelector('.lgrc').innerText.replace(/\\n/g, ' '), r.querySelector('.lgchip').textContent, r.classList.contains('on')])")
    want = [f"{x[3][0]}-{x[3][1]}" for x in LS]; check([r[1].split(" ")[0] for r in rows] == want, f"{T}: the sheet lists all 14 leagues with the reader's record in each ({[r[1].split(' ')[0] for r in rows][:5]}...)")
    check(all(re.fullmatch(r"(Buy|Hold|Sell|Out) · (\d+%\+?|under 1%|in|out)", r[2]) for r in rows) and rows[0][3] and sum(r[3] for r in rows) == 1, f"{T}: every league carries buy / hold / sell with its playoff odds; the one on screen is marked ({[r[2] for r in rows][:4]}...)")
    # 11/18: how much this week matters in each league, and "Biggest week first"
    sw = await pg.evaluate("[...document.querySelectorAll('#lgov .lgrow')].map(r => { var s = r.querySelector('.lgsw'); return [r.querySelector('b').textContent, s ? s.textContent : null, s ? s.className : '']; })")
    num = lambda x: int(re.match(r"(\d+)-pt week", x).group(1)) if x and re.match(r"(\d+)-pt week", x) else (0 if x == "no swing" else None)
    sws = [num(x[1]) for x in sw]
    check(all(v is not None for v in sws), f"{T}: every league says how many points of playoff odds this week moves ({[x[1] for x in sw][:5]}...)")
    mid = [v for v, x in zip(sws, LS) if 4 <= x[3][0] <= 6]; edge = [v for v, x in zip(sws, LS) if x[3][0] >= 8 or x[3][0] <= 1]
    check(mid and edge and max(mid) >= 15 and max(mid) > max(edge) and all(("big" in x[2]) == (v >= 25) for v, x in zip(sws, sw)), f"{T}: a bubble team's week swings more than an 8-2 or 1-9 team's (bubble {mid}, the ends {edge}); 25+ is marked")
    check(await pg.evaluate(VIS, "#lgov .lgsort"), f"{T}: with the weeks read, the list can be ordered by them")
    await pg.click('#lgov .lgsort [data-s="sw"]'); await pg.wait_for_timeout(200)
    srt = await pg.evaluate("[...document.querySelectorAll('#lgov .lgrow')].map(r => [r.querySelector('b').textContent, (r.querySelector('.lgsw') || {textContent: ''}).textContent, r.getAttribute('data-id')])")
    got = [num(x[1]) for x in srt]
    check(got == sorted(got, reverse=True) and sorted(x[2] for x in srt) == sorted(x[0]["league_id"] for x in LS) and got[0] == max(sws), f"{T}: Biggest week first puts the {got[0]}-point week on top and keeps all 14 ({got[:5]}...)")
    await pg.click('#lgov .lgsort [data-s=""]'); await pg.wait_for_timeout(200)
    back = await pg.evaluate("[...document.querySelectorAll('#lgov .lgrow')].map(r => r.getAttribute('data-id'))"); check(back == [x[0]["league_id"] for x in LS], f"{T}: Sleeper order puts them back")
    good = [r for r, x in zip(rows, LS) if x[3][0] >= 7]; poor = [r for r, x in zip(rows, LS) if x[3][0] <= 2]
    check(good and all(r[2].startswith("Buy") for r in good) and poor and all(r[2].startswith(("Sell", "Out")) for r in poor), f"{T}: 7+ win teams read Buy, 2-win teams Sell or Out ({[r[2] for r in good][:2]} / {[r[2] for r in poor][:2]})")
    ros = [u for u in asked if u.endswith("/rosters")]; check(len(set(ros)) == 14 and len(ros) <= 15, f"{T}: one rosters request per league ({len(ros)} for 14; the league on screen was already loaded)")
    check(await pg.evaluate(VIS, "#lgov .lgq"), f"{T}: more than eight leagues, so there is a search box")
    await pg.fill("#lgov .lgq", "dyn"); await pg.wait_for_timeout(250); found = await pg.evaluate("[...document.querySelectorAll('#lgov .lgrow b')].map(b => b.textContent)")
    check(found and all("dyn" in f.lower() for f in found) and len(found) < 14, f"{T}: typing narrows the list ({found})")
    await pg.fill("#lgov .lgq", "zzzz"); await pg.wait_for_timeout(250); check("No league matches" in await pg.evaluate("document.querySelector('#lgov .lglist').innerText"), f"{T}: no match says so")
    await pg.fill("#lgov .lgq", ""); await pg.wait_for_timeout(250); n2 = len(asked)
    await pg.click("#lgov .lgrow >> nth=5"); await pg.wait_for_function("!document.querySelector('#lgov')"); await pg.wait_for_selector("#olk", timeout=15000); await pg.wait_for_timeout(900)
    bar2 = await pg.evaluate("document.querySelector('.lgbar .lgcur').innerText.replace(/\\n/g, ' | ')"); fm2 = await pg.evaluate("document.querySelector('#fmtSum').textContent"); L5 = LS[5][0]
    check(bar2.startswith(L5["name"]) and await pg.evaluate("document.querySelector('#tcTabs .tab.on').dataset.t") == "league" and await pg.evaluate("Math.round(scrollY)") < 60, f"{T}: picking a league closes the sheet and shows that league from the top ({bar2[:60]})")
    check(("Superflex" in fm2) == ("SUPER_FLEX" in L5["roster_positions"]) and ("Dynasty" in fm2) == (L5["settings"]["type"] == 2) and str(L5["total_rosters"]) + " teams" in fm2, f"{T}: the calculator's format follows the league picked ({fm2})")
    # a trade loaded from the league lands in the calculator
    has = await pg.evaluate("!!document.querySelector('#olk [data-ol], #slIdeas [data-idea]')")
    if has:
        await pg.evaluate("document.querySelector('#olk [data-ol], #slIdeas [data-idea]').click()"); await pg.wait_for_timeout(700)
        sides = await pg.evaluate("document.querySelectorAll('#sideA li, #sideB li').length")
        check(await pg.evaluate("document.querySelector('#tcTabs .tab.on').dataset.t") == "calc" and sides >= 1 and await pg.evaluate("Math.round(scrollY)") < 60 and await pg.evaluate(VIS, "#sideA"), f"{T}: Load opens the calculator with the trade on it ({sides} player{'s' if sides != 1 else ''} loaded)")
    else: print(f"SKIP {T}: no idea to load in this league")
    # rankings
    await pg.click('#tcTabs [data-t="rank"]'); await pg.wait_for_timeout(300); nr = await pg.evaluate("document.querySelectorAll('#rk tr').length"); mb = await pg.evaluate("document.querySelector('#rkMore').textContent")
    check(nr == 30 and re.fullmatch(r"Show all \d+", mb) and await pg.evaluate(SCR) <= 6, f"{T}: rankings show 30 rows and one button for the rest ({mb}; {await pg.evaluate(SCR)} screens - the table alone was 13.7)")
    await pg.click("#rkMore"); await pg.wait_for_timeout(300); nr2 = await pg.evaluate("document.querySelectorAll('#rk tr').length"); check(nr2 > 30 and nr2 == int(mb.split(" ")[-1]) and await pg.evaluate("document.querySelector('#rkMore').textContent") == "Show the top 30", f"{T}: the button shows them all and offers the short list back ({nr2} rows)")
    check(not await pg.evaluate("document.querySelector('details.methd').open") and await pg.evaluate(OVER) <= 0, f"{T}: the method note is folded; no sideways scroll")
    # a return visit: no typing; the sheet's records and verdicts are remembered for the session
    await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_selector(".lgbar .lgcur", timeout=15000); await pg.wait_for_timeout(1200); n3 = len(asked)
    check(not await pg.evaluate(VIS, "#slUser") and (await pg.evaluate("document.querySelector('.lgbar .lgcur b').textContent")) == L5["name"], f"{T}: on a return visit the leagues load by themselves and the last league is back on the bar")
    await pg.click(".lgbar .lgcur"); await pg.wait_for_selector("#lgov .lgrow"); await pg.wait_for_timeout(1200)
    check(len(asked) == n3 and await pg.evaluate("document.querySelectorAll('#lgov .lgrow .lgchip').length") == 14, f"{T}: reopening the sheet asks Sleeper nothing more ({len(asked) - n3} requests) and still shows 14 verdicts")
    await pg.keyboard.press("Escape"); await pg.wait_for_timeout(200); gone = await pg.evaluate("!document.querySelector('#lgov')")
    await pg.click(".lgbar .lgcur"); await pg.click("#lgov .lgchg"); await pg.wait_for_timeout(300)
    check(gone and await pg.evaluate(VIS, "#slUser") and not await pg.evaluate(VIS, ".lgbar .lgcur") and await pg.evaluate("document.querySelector('#slUser').value") == "", f"{T}: Escape closes the sheet; \"Use another\" brings the username box back, empty")
    check(not errs, f"{T}: no script errors ({errs[:1]})"); await ctx.close()

SLOTPOS = {"QB": ("QB",), "RB": ("RB",), "WR": ("WR",), "TE": ("TE",), "FLEX": ("RB", "WR", "TE"), "SUPER_FLEX": ("QB", "RB", "WR", "TE")}
def real_lineups(players, hurt=(), best_ball=(), lineup=None):
    """The mock's rosters start their first eight players whatever the slot. For the lineup check each of MY rosters gets a legal lineup
    (the first fitting player per slot), `hurt` players are Out on Sleeper, `best_ball` leagues set themselves, and `lineup` = {league
    index: [player ids]} sets one league's starters outright."""
    pos = {p["id"]: p["pos"] for p in players}
    def tw(LS, pm):
        for li, (L, R, U, rec) in enumerate(LS):
            mine = R[0]; used = set(); st = []
            for sl in [x for x in L["roster_positions"] if x != "BN"]:
                pid = next((i for i in mine["players"] if i not in used and pos[i] in SLOTPOS[sl]), "0"); used.add(pid); st.append(pid)
            mine["starters"] = list(lineup[li]) if lineup and li in lineup else st
            if li in best_ball: L["settings"]["best_ball"] = 1
        for i in hurt: pm[i]["injury_status"] = "Out"
    return tw

ROWS = """[...document.querySelectorAll('#allg .allgr')].map(b => ({id: b.dataset.id, name: b.querySelector('b').textContent, why: b.querySelector('small').textContent, chip: b.querySelector('.lgchip').textContent}))"""
async def checklist(b, players, theme):
    T = f"all leagues, {theme}"
    hold = {}
    def tw(LS, pm): real_lineups(players, best_ball=[9])(LS, pm); hold["pm"] = pm
    ctx, pg, asked, errs, LS = await session(b, players, theme, tweak=tw)
    await pg.goto(f"http://127.0.0.1:{PORT}/team/", wait_until="domcontentloaded"); await pg.wait_for_timeout(600)
    check(not await pg.evaluate(VIS, "#allg"), f"{T}: nothing about other leagues before a username is given")
    # the player to hurt: a wide receiver I start in the first league who is playing this week (not on bye, active in the model)
    playing = set(await pg.evaluate("window.__BS.players.filter(p => p.o !== 'BYE' && p.act).map(p => p.n)")); byid = {p["id"]: p for p in players}
    hurt = next(i for i in LS[0][1][0]["starters"] if i != "0" and byid[i]["pos"] == "WR" and byid[i]["n"] in playing); hname = byid[hurt]["n"]; hold["pm"][hurt]["injury_status"] = "Out"
    where = [li for li, x in enumerate(LS) if hurt in x[1][0]["starters"] and li != 9]
    await pg.fill("#user", "mock"); await pg.click("#go"); await pg.wait_for_function("!document.querySelector('#out').hidden", timeout=15000)
    await pg.wait_for_function("document.querySelector('#allg') && !document.querySelector('#allg').hidden && !document.querySelector('#allg').classList.contains('busy')", timeout=25000); await pg.wait_for_timeout(300)
    head = await pg.evaluate("document.querySelector('#allg .allgh b').textContent"); sub = await pg.evaluate("document.querySelector('#allg .allgh small').textContent"); rows = await pg.evaluate(ROWS)
    m = re.match(r"(\d+) of (\d+) lineups need you$", head)
    check(bool(m) and int(m.group(1)) == len(rows) >= len(where) and int(m.group(2)) == 13, f"{T}: one line says how many lineups need you ({head}; {sub[:70]}…)")
    ros = [u for u in asked if u.endswith("/rosters")]; check(sorted(ros) == sorted(f"league/L{i}/rosters" for i in range(14)) and asked.count("players/nfl") == 1, f"{T}: read with one rosters call per league and one player list ({len(ros)} roster calls, {asked.count('players/nfl')} player list)")
    hit = [r for r in rows if r["id"] in [f"L{i}" for i in where]]
    check(len(hit) == len(where) and all(f"{hname[0]}. {hname.split(' ', 1)[1]} (out)" in r["why"] and "can't play" in r["why"] and r["chip"].startswith("Fix ") for r in hit), f"{T}: every league starting the injured player is listed and names him ({hname}: {len(where)} leagues; e.g. {hit[0]['why'] if hit else None})")
    check(not any(r["id"] == "L9" for r in rows) and "best-ball league sets itself" in await pg.evaluate("document.querySelector('#allg .allgf').textContent"), f"{T}: the best-ball league is not on the list; the footnote says it sets itself")
    order = [r["chip"].startswith("Fix ") for r in rows]; check(order == sorted(order, reverse=True) and all(re.match(r"(Fix \d+|\+\d+\.\d)$", r["chip"]) for r in rows), f"{T}: lineups with a starter who cannot play come before lineups that only leave points on the bench ({[r['chip'] for r in rows]})")
    box = await pg.evaluate("(() => { const r = document.querySelector('#allg').getBoundingClientRect(); return [Math.round(r.height), Math.round(r.right), Math.round(r.left)]; })()")
    check(await pg.evaluate(OVER) <= 0 and box[1] <= 390 and box[2] >= 0 and box[0] <= 80 and not await pg.evaluate(VIS, "#allg .allgr") and rows[0]["name"] in sub, f"{T}: until asked it is one line that names the first league to fix ({box[0]}px tall; no sideways scroll)")
    await pg.click("#allg .allgh"); await pg.wait_for_timeout(150)
    check(await pg.evaluate(VIS, "#allg .allgr") and await pg.evaluate("document.querySelector('#allg .allgh').getAttribute('aria-expanded')") == "true" and await pg.evaluate(OVER) <= 0, f"{T}: a tap opens the list in place")
    # each listed league agrees with its own Lineup tab
    agree = []
    for r in rows[:1] + rows[-2:]:
        await pg.click(f'#allg .allgr[data-id="{r["id"]}"]'); await pg.wait_for_function(f"document.querySelector('#leagueH').textContent.indexOf({json.dumps(r['name'])}) === 0", timeout=15000); await pg.wait_for_timeout(450)
        lh = await pg.evaluate("document.querySelector('#lineupH').innerText"); li = await pg.evaluate("document.querySelector('#lineup').innerText"); tab = await pg.evaluate("document.querySelector('#tmTabs .tab.on').dataset.t")
        top = await pg.evaluate("Math.round(document.querySelector('#tmTabs').getBoundingClientRect().top)")
        g1 = re.search(r"\+(\d+\.\d) pts", r["why"]); g2 = re.search(r"\+(\d+\.\d) pts", lh)
        dead = re.findall(r"([^,:·]+?) \((?:out|bye|IR|PUP|Sus)\)", r["why"].split("can't play:")[1].split("·")[0]) if "can't play" in r["why"] else []
        agree.append(tab == "lineup" and -5 <= top <= 140 and (not g1 or (g2 and abs(float(g1.group(1)) - float(g2.group(1))) < 0.11)) and all(d.strip().split(". ", 1)[-1] in li for d in dead))
        if not agree[-1]: print("   mismatch:", r, "|", lh.replace("\n", " "), "| tab", tab, "top", top)
    check(all(agree), f"{T}: a tap opens that league on its Lineup tab, and the tab shows the same points and the same sidelined starters ({len(agree)} leagues)")
    cur = await pg.evaluate("[...document.querySelectorAll('#allg .allgr.on')].map(b => b.dataset.id)"); check(cur == [rows[-1]["id"]] if len(rows) > 1 else True, f"{T}: the league on screen is marked in the list")
    # free agents who would start (the mock's draft leaves a few top players unpicked in most leagues, so the fold is never empty here)
    pk = await pg.evaluate("[...document.querySelectorAll('#allg .allgk .pk')].map(d => ({n: d.querySelector('b').textContent, sub: d.querySelector('small').textContent, ls: [...d.querySelectorAll('.allgo')].map(b => [b.dataset.id, b.textContent.trim()])}))")
    nfree = [int(re.search(r"free in (\d+) league", p["sub"]).group(1)) for p in pk]; name2id = {p["n"]: p["id"] for p in players}
    held = [(p["n"], lid) for p in pk for lid, _ in p["ls"] if any(name2id.get(p["n"]) in r["players"] for r in next(x[1] for x in LS if x[0]["league_id"] == lid))]
    check(1 <= len(pk) <= 5 and nfree == sorted(nfree, reverse=True) and all(1 <= len(p["ls"]) <= 3 and len(p["ls"]) == min(3, n) for p, n in zip(pk, nfree)) and not held
          and all(re.search(r"\+\d+\.\d$", x) and float(x.rsplit("+", 1)[1]) >= 2 for p in pk for _, x in p["ls"]),
          f"{T}: the fold lists free agents worth two points or more over a starter, the most widely available first, and only in leagues where nobody holds them ({[(p['n'], n) for p, n in zip(pk, nfree)][:3]})")
    if pk:
        first = pk[0]; lid, lab = first["ls"][0]; await pg.evaluate("document.querySelector('#allg .allgk').open = true"); await pg.click(f'#allg .allgk .allgo[data-id="{lid}"]')
        await pg.wait_for_function(f"document.querySelector('#leagueH').textContent.indexOf({json.dumps(next(x[0]['name'] for x in LS if x[0]['league_id'] == lid))}) === 0", timeout=15000); await pg.wait_for_timeout(450)
        tab = await pg.evaluate("document.querySelector('#tmTabs .tab.on').dataset.t"); wv = await pg.evaluate("[...document.querySelectorAll('#waiv li')].map(li => li.innerText.replace(/\\n/g, ' | '))")
        row = next((x for x in wv if x.startswith(first["n"])), ""); up = re.search(r"\+(\d+\.\d) over your [A-Z]+", row)
        check(tab == "waivers" and bool(up) and abs(float(up.group(1)) - float(lab.rsplit("+", 1)[1])) < 0.11, f"{T}: a tap opens that league's waiver list, and it shows the same player at the same margin ({row[:70]})")
    # the sheet: the same check as each row's chip, and its own order
    await pg.evaluate("window.scrollTo(0, 0)"); await pg.click(".lgbar .lgcur"); await pg.wait_for_selector("#lgov .lgrow")
    chips = await pg.evaluate("[...document.querySelectorAll('#lgov .lgrow')].map(b => [b.dataset.id, (b.querySelector('.lgchip') || {}).textContent || ''])")
    check(len(chips) == 14 and dict(chips)["L9"] == "Best ball" and all(c for _, c in chips) and {i for i, c in chips if c.startswith("Fix ") or c.startswith("+")} == {r["id"] for r in rows}, f"{T}: the league list carries the same verdict on every row ({[c for _, c in chips][:6]}…)")
    sb = await pg.evaluate("[...document.querySelectorAll('#lgov .lgsort .tab')].map(b => b.textContent)"); await pg.click('#lgov .lgsort [data-s="sw"]'); await pg.wait_for_timeout(200)
    first = await pg.evaluate("[...document.querySelectorAll('#lgov .lgrow .lgchip')].map(b => b.textContent)")
    rank = [2 if c.startswith("Fix ") else 1 if c.startswith("+") else 0 for c in first]
    check(sb == ["Sleeper order", "Needs you first"] and rank == sorted(rank, reverse=True) and len(first) == 14, f"{T}: \"Needs you first\" puts the lineups to fix on top ({first[:4]}…)")
    await pg.click('#lgov .lgsort [data-s=""]'); await pg.keyboard.press("Escape")
    # open stays open for the visit; a reload reads nothing twice
    n0 = len(asked); await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_function("!document.querySelector('#out').hidden", timeout=15000); await pg.wait_for_timeout(900)
    head2 = await pg.evaluate("document.querySelector('#allg .allgh b').textContent"); again = [u for u in asked[n0:] if u.endswith("/rosters")]
    check(head2 == head and await pg.evaluate(VIS, "#allg .allgr") and len(again) == 1, f"{T}: opened, it stays open for the visit, and a reload within the half hour asks Sleeper for the league on screen only ({len(again)} roster call)")
    most = await pg.evaluate("[...document.querySelectorAll('#allg .allgm:not(.allgk) span')].map(s => s.textContent.trim())")
    cnt = {}
    for li, x in enumerate(LS):
        if li == 9: continue
        for i in x[1][0]["starters"]:
            if i != "0": cnt[byid[i]["n"]] = cnt.get(byid[i]["n"], 0) + 1
    want = [f"{n} {c}" for n, c in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0])) if c >= 2][:8]
    got = [re.sub(r"(Q|BYE|OUT)$", "", x) for x in most]
    check(len(most) >= 3 and got == want, f"{T}: the most-started players are counted across leagues ({most[:3]})")
    check(not errs, f"{T}: no script errors ({errs[:1]})"); await ctx.close()
    return LS, rows

async def checklist_set(b, players):
    """When Sleeper's lineup IS the model's lineup, the league reads Set - checked by asking the page for its lineup and playing it back."""
    ctx, pg, asked, errs, LS = await session(b, players, "dark", stored="mock", tweak=real_lineups(players))
    await pg.goto(f"http://127.0.0.1:{PORT}/team/", wait_until="domcontentloaded"); await pg.wait_for_function("!document.querySelector('#out').hidden", timeout=15000); await pg.wait_for_timeout(700)
    names = await pg.evaluate("[...document.querySelectorAll('#lineup li .who > b')].map(b => b.childNodes[0].textContent.trim())"); await ctx.close()
    ids = [next((p["id"] for p in players if p["n"] == n), None) for n in names]
    check(len(ids) >= 8 and all(ids), f"the page's own best lineup for the first league can be read back ({len(ids)} starters)")
    ctx, pg, asked, errs, LS = await session(b, players, "dark", stored="mock", tweak=real_lineups(players, lineup={0: ids}))
    await pg.goto(f"http://127.0.0.1:{PORT}/team/", wait_until="domcontentloaded"); await pg.wait_for_function("!document.querySelector('#out').hidden", timeout=15000)
    await pg.wait_for_function("document.querySelector('#allg') && !document.querySelector('#allg').classList.contains('busy')", timeout=25000); await pg.wait_for_timeout(300)
    rows = await pg.evaluate(ROWS); lh = await pg.evaluate("document.querySelector('#lineupH').innerText"); chip = await pg.evaluate("(document.querySelector('.lgbar .lgchip') || {}).textContent || ''")
    check(not any(r["id"] == "L0" for r in rows) and "match the model" in lh and chip == "Set" and not errs, f"a lineup that already is the model's lineup reads Set and stays off the list (bar chip: {chip}; {lh.strip()[:60].replace(chr(10), " ")})"); await ctx.close()
    # one league: no card
    ctx, pg, asked, errs, LS = await session(b, players, "dark", nl=1, stored="mock", tweak=real_lineups(players))
    await pg.goto(f"http://127.0.0.1:{PORT}/team/", wait_until="domcontentloaded"); await pg.wait_for_function("!document.querySelector('#out').hidden", timeout=15000); await pg.wait_for_timeout(900)
    check(not await pg.evaluate(VIS, "#allg") and not errs, "a one-league account gets no all-leagues card"); await ctx.close()

async def team(b, players, theme):
    T = f"fantasy, {theme}"
    ctx, pg, asked, errs, LS = await session(b, players, theme)
    await pg.goto(f"http://127.0.0.1:{PORT}/team/", wait_until="domcontentloaded"); await pg.wait_for_timeout(800)
    q = await pg.evaluate("[...document.querySelectorAll('.quick a')].map(a => [a.textContent, a.getAttribute('href')])"); h0 = await pg.evaluate(SCR)
    check(q == [["Who should I start?", "/team/compare/"], ["Buy or sell?", "/trade/#league"]] and await pg.evaluate("document.querySelector('#go').getBoundingClientRect().bottom") < 844 and h0 <= 2.5, f"{T}: a new visitor sees two small buttons and the whole connect form on the first screen ({h0} screens in all)")
    check(not asked, f"{T}: nothing is asked of Sleeper before a username is given")
    await pg.fill("#user", "mock"); await pg.click("#go"); await pg.wait_for_function("!document.querySelector('#out').hidden", timeout=15000); await pg.wait_for_timeout(900)
    tabs = await pg.evaluate("[...document.querySelectorAll('#tmTabs .tab')].filter(b => !b.hidden).map(b => [b.dataset.t, b.classList.contains('on')])")
    check(tabs == [["lineup", True], ["roster", False], ["league", False], ["waivers", False]] and not await pg.evaluate(VIS, "#user") and not await pg.evaluate(VIS, "#leagues"), f"{T}: graded - four tabs with the lineup open; the connect form and the league buttons are gone")
    bar = await pg.evaluate("document.querySelector('.lgbar .lgcur').innerText.replace(/\\n/g, ' | ')"); r0 = LS[0][3]
    check(bar.startswith("Nashville Dynasty") and f"{r0[0]}-{r0[1]}" in bar and "14" in bar, f"{T}: the bar names the league and the record ({bar})")
    sizes = {}
    for t, sel in (("lineup", "#lineup"), ("roster", "#roster"), ("league", "#pr"), ("waivers", "#waiv")):
        await pg.click(f'#tmTabs [data-t="{t}"]'); await pg.wait_for_timeout(250); sizes[t] = await pg.evaluate(SCR)
        vis = {s: await pg.evaluate(VIS, s) for s in ("#lineup", "#roster", "#pr", "#waiv")}
        check(vis[sel] and sum(vis.values()) == 1, f"{T}: the {t} tab shows its own section and nothing else ({sizes[t]} screens)")
    check(max(sizes.values()) <= 4.5, f"{T}: no tab is longer than 4.5 phone screens (the page was 8.2: {sizes})")
    await pg.evaluate("window.scrollTo(0, 900)"); await pg.wait_for_timeout(200); top = await pg.evaluate("Math.round(document.querySelector('#tmTabs').getBoundingClientRect().top)")
    check(40 <= top <= 80, f"{T}: scrolled down, the tabs stay under the site bar ({top}px from the top)")
    await pg.click('#tmTabs [data-t="lineup"]'); await pg.wait_for_timeout(300); y = await pg.evaluate("Math.round(document.querySelector('[data-tab=lineup]').getBoundingClientRect().top)")
    check(60 <= y <= 200, f"{T}: a tab tapped from down the page starts its section right under the tabs ({y}px)")
    await pg.evaluate("window.scrollTo(0, 0)"); await pg.click(".lgbar .lgcur"); await pg.wait_for_selector("#lgov .lgrow"); await pg.wait_for_function("![...document.querySelectorAll('#lgov .lgrc')].some(e => e.textContent.trim() === '…')", timeout=20000)
    recs = await pg.evaluate("[...document.querySelectorAll('#lgov .lgrc')].map(e => e.innerText.split('\\n')[0])"); check(recs == [f"{x[3][0]}-{x[3][1]}" for x in LS], f"{T}: the sheet shows the record in all 14 leagues")
    await pg.click("#lgov .lgrow >> nth=3"); await pg.wait_for_function("document.querySelector('#leagueH').textContent.indexOf('Broadway Bandits') === 0", timeout=15000); await pg.wait_for_timeout(500)
    check((await pg.evaluate("document.querySelector('.lgbar .lgcur b').textContent")) == "Broadway Bandits" and await pg.evaluate("Math.round(scrollY)") < 60, f"{T}: picking another league regrades in place, no jump down the page")
    check(await pg.evaluate(OVER) <= 0 and not errs, f"{T}: no sideways scroll, no script errors ({errs[:1]})")
    await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_function("!document.querySelector('#out').hidden", timeout=15000); await pg.wait_for_timeout(600)
    check((await pg.evaluate("document.querySelector('.lgbar .lgcur b').textContent")) == "Broadway Bandits" and not await pg.evaluate(VIS, "#user"), f"{T}: a return visit grades the last league by itself - no typing, no button")
    await ctx.close()

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch(); c0 = await b.new_context(); p0 = await c0.new_page()
        await p0.goto(f"http://127.0.0.1:{PORT}/trade/", wait_until="domcontentloaded"); await p0.wait_for_timeout(900)
        players = await p0.evaluate("window.__BS.players.filter(p => p.Re > 0 && p.st !== 'OUT' && p.adj > 0).sort((a, b) => b.adj - a.adj).map((p, i) => ({id: 'm' + i, n: p.n, pos: p.pos, tm: p.tm, adj: p.adj}))")
        mw = await p0.evaluate("window.__BS.mkt_w"); await c0.close()
        check(len(players) >= 200, f"the page's own player list drafts the mock leagues ({len(players)} healthy players)")
        check(mw == 0.7 or mw == 0, f"the market's share of a trade value is 70% when the market feed is on ({mw})")
        for theme in ("dark", "light"): await trade(b, players, theme)
        for theme in ("dark", "light"): await team(b, players, theme)
        for theme in ("dark", "light"): await checklist(b, players, theme)
        await checklist_set(b, players)
        # a hand-built team is left alone: no Sleeper request on load
        ctx, pg, asked, errs, LS = await session(b, players, "dark", stored="mock", mode="manual")
        await pg.goto(f"http://127.0.0.1:{PORT}/team/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
        check(not asked and await pg.evaluate("!document.querySelector('#manualBox').hidden"), f"a reader who builds his team by hand is not sent to Sleeper on load ({len(asked)} requests)"); await ctx.close()
        # one league: no search box, no "Switch"
        ctx, pg, asked, errs, LS = await session(b, players, "dark", nl=1, stored="mock")
        await pg.goto(f"http://127.0.0.1:{PORT}/trade/#league", wait_until="domcontentloaded"); await pg.wait_for_selector("#olk", timeout=15000); await pg.wait_for_timeout(500)
        bar = await pg.evaluate("document.querySelector('.lgbar .lgcur').innerText"); await pg.click(".lgbar .lgcur"); await pg.wait_for_selector("#lgov .lgrow")
        check("Switch" not in bar and "SWITCH" not in bar and not await pg.evaluate("!!document.querySelector('#lgov .lgq')") and await pg.evaluate("document.querySelectorAll('#lgov .lgrow').length") == 1 and not errs, "a one-league account gets the bar without a search box or a count"); await ctx.close()
        await b.close()
    srv.shutdown(); print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
asyncio.run(main())
