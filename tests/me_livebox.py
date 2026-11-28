"""My BetSweep grades a slip from this week's FINISHED games the same night (owner 11/21: "Why haven't the box scores hit yet for Thursday
night's game? It's saying game hasn't been played yet on daily sweep and thievery"). /data/box-w<W>.json is a Tuesday file; until it
exists the page reads ESPN's scoreboard and final box scores. Stand-in ESPN, no network.   python3 tests/me_livebox.py"""
import asyncio, json, os, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8868
ok = [0, 0]; LEGS = [None]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
def ath(n, *st): return {"athlete": {"displayName": n}, "stats": [str(x) for x in st]}
RUSH = ["rushingAttempts", "rushingYards", "yardsPerRushAttempt", "rushingTouchdowns", "longRushing"]; REC = ["receptions", "receivingYards", "yardsPerReception", "receivingTouchdowns", "longReception", "receivingTargets"]
filler = [ath(f"Filler {i}", 1, 5, 5.0, 0, 5, 1) for i in range(10)]
SUM = {"boxscore": {"players": [{"team": {"abbreviation": "HOU"}, "statistics": [{"name": "rushing", "keys": RUSH, "athletes": [ath("David Montgomery", 26, 107, 4.1, 1, 18), ath("C.J. Stroud", 5, 28, 5.6, 0, 12)]},
                                                                               {"name": "receiving", "keys": REC, "athletes": [ath("Tank Dell", 3, 27, 9.0, 0, 14, 6)] + filler}]},
                                {"team": {"abbreviation": "IND"}, "statistics": [{"name": "rushing", "keys": RUSH, "athletes": [ath("Jonathan Taylor", 12, 31, 2.6, 0, 9)]}]}]}}
ev = lambda i, a, h, sa, sh, state: {"id": i, "status": {"type": {"state": state, "completed": state == "post"}}, "competitions": [{"competitors": [{"homeAway": "away", "team": {"abbreviation": a}, "score": str(sa)}, {"homeAway": "home", "team": {"abbreviation": h}, "score": str(sh)}]}]}
SB = {"events": [ev("1", "IND", "HOU", 3, 26, "post"), ev("2", "ARI", "KC", 0, 0, "pre"), ev("3", "WSH", "CIN", 7, 10, "in")]}
SLIPS = {"11": [{"name": "Daily Sweep", "keys": ["Tank Dell|Receiving Yards|30", "CJ Stroud|Rushing Yards|5", "David Montgomery|Rushing Yards|40", "Deion Burks|Receiving Yards|10", "Jonathan Taylor|Rushing Yards|40"], "odds": 484, "stake": 1},
                {"name": "Winner", "keys": ["David Montgomery|Rushing Yards|50", "David Montgomery|Anytime TD|1", "C.J. Stroud|Rushing Yards|5"], "odds": 300, "stake": 1},
                {"name": "Sunday", "keys": ["Patrick Mahomes|Passing Yards|200"], "odds": -150, "stake": 1},
                {"name": "Mixed", "keys": ["David Montgomery|Rushing Yards|50", "Patrick Mahomes|Passing Yards|200"], "odds": 150, "stake": 1}]}
async def run(b, have_file):
    calls = []
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
    await ctx.add_init_script("try{ var S = %s; Object.keys(S).forEach(function(w){ localStorage.setItem('bs_slips_w' + w, JSON.stringify(S[w])); }); }catch(e){}" % json.dumps(SLIPS))
    async def rt(route, request):
        u = request.url
        if "127.0.0.1" in u:
            if "/data/box-w11.json" in u:
                if have_file: return await route.fulfill(status=200, content_type="application/json", body=json.dumps({"week": 11, "box": {"David Montgomery": [0, 0, 0, 60, 0, 0, 0, 0, 0]}, "games": {}, "final": True}))
                return await route.fulfill(status=404, body="")
            return await route.continue_()
        if "site.api.espn.com" in u:
            calls.append(u.split("/nfl/")[1])
            if "scoreboard" in u: return await route.fulfill(status=200, content_type="application/json", body=json.dumps(SB))
            if "summary?event=1" in u: return await route.fulfill(status=200, content_type="application/json", body=json.dumps(SUM))
            return await route.fulfill(status=404, body="")
        await route.abort()
    await ctx.route("**/*", rt)
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    await pg.goto(f"http://127.0.0.1:{PORT}/me/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
    rows = await pg.evaluate("[...document.querySelectorAll('li.sl')].map(function(li){ return [li.querySelector('b').textContent, li.querySelector('.res').textContent]; })")
    # 11/27: this week's decided slips sit under a Settled fold; open it, the checks below read every slip's legs
    await pg.evaluate("() => { var s = document.querySelector('#slips .setlt'); if(s && s.getAttribute('aria-expanded') !== 'true') s.click(); }"); await pg.wait_for_timeout(200)
    # 11/25 (owner screenshot, "Make this look better"): the legs open one per row with the result on the right, and a leg whose game has
    # not been played says so instead of "no box score (did not play?)".
    LEGS[0] = await pg.evaluate("""() => { var out = {}; Array.from(document.querySelectorAll('li.sl')).forEach(function(li){ var t = li.querySelector('.lgt'); t.click();
      var rows = Array.from(li.querySelectorAll('.legs .lg')); out[li.querySelector('b').textContent] = {open: li.classList.contains('lo') && t.getAttribute('aria-expanded') === 'true',
        legs: rows.map(function(r){ var e = r.querySelector('em.ra'); return [r.querySelector('.ln').textContent, e ? e.textContent : '', Math.round(r.getBoundingClientRect().top), Math.round(r.getBoundingClientRect().right)]; }),
        meta: li.querySelector('small.mt').textContent, pl: (li.querySelector('.pl') || {}).className || '', tgl: Math.round(t.getBoundingClientRect().height)}; });
      out.__w = [document.documentElement.scrollWidth, window.innerWidth]; return out; }""")
    await ctx.close(); return dict(rows), calls, errs
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        r, calls, errs = await run(b, False)
        check(not errs and len(r) == 4, f"the page draws the four saved slips with no script error ({errs[:1]}; {r})")
        check(r.get("Daily Sweep") == "Missed", f"a slip from the finished Thursday game is graded the same night - Dell 27 against 30+ ({r.get('Daily Sweep')})")
        check(r.get("Winner") == "Cashed", f"a slip whose legs all cleared is Cashed, with 'C.J. Stroud' found from ESPN's name ({r.get('Winner')})")
        check(r.get("Sunday") == "Pending" and r.get("Mixed") == "Pending", f"legs in games not yet played stay open - nothing is graded early ({r.get('Sunday')}, {r.get('Mixed')})")
        check(sorted(calls) == ["scoreboard?seasontype=2&week=11", "summary?event=1"], f"ESPN is asked for the week's scoreboard and only the finished game's box score ({calls})")
        L = LEGS[0]; ds = L["Daily Sweep"]["legs"]; tops = [x[2] for x in ds]
        check(L["Daily Sweep"]["open"] and len(ds) == 5 and len(set(tops)) == 5 and tops == sorted(tops), f"the Legs button opens one leg per row ({tops})")
        check(all(x[3] <= 390 for x in ds) and L["__w"][0] <= L["__w"][1], f"no leg row runs off a phone screen (page {L['__w']})")
        check(L["Sunday"]["legs"][0][1] == "not played yet" and L["Mixed"]["legs"][1][1] == "not played yet", f"a leg in a game still to come reads 'not played yet' ({L['Sunday']['legs'][0][1]!r})")
        check([x[1] for x in ds if x[0].startswith("Tank Dell")] == ["27"] and not any("(" in x[1] for x in ds), f"a graded leg shows its number on the right, no brackets ({[x[1] for x in ds]})")
        check("dn" in L["Daily Sweep"]["pl"] and "up" in L["Winner"]["pl"] and "+484" in L["Daily Sweep"]["meta"], f"the units won or lost are colored ({L['Daily Sweep']['pl']!r}, {L['Winner']['pl']!r})")
        check(L["Daily Sweep"]["tgl"] >= 34, f"the Legs button is a fair tap target ({L['Daily Sweep']['tgl']}px)")
        r2, calls2, _ = await run(b, True)
        L2 = LEGS[0]
        check(L2["Sunday"]["legs"][0][1] == "no box score (did not play?)", f"with Tuesday's file a man with no line is still 'did not play?' ({L2['Sunday']['legs'][0][1]!r})")
        check(calls2 == [] and r2.get("Mixed") == "Pending" and r2.get("Winner") in ("Pending", "Missed"), f"once the Tuesday file exists it is used and ESPN is not asked ({calls2})")
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
