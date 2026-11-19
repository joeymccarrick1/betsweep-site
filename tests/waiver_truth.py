"""The Waivers tab only lists men who are really free and whose projection rests on something (owner 11/19: "Ken Walker is not on the
waiver wire in ANY league" / "Michael Carter has 0 shot to score 9.3 points"). Stand-in Sleeper feed, no network.
python3 tests/waiver_truth.py"""
import asyncio, glob, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8866
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
t = open(glob.glob(os.path.join(ROOT, "team", "data-*.js"))[0]).read(); P = json.loads(t[t.index("{"):t.rindex("}") + 1])["players"]
act = [p for p in P if p["act"] and p["o"] != "BYE"]
top = lambda pos, n: sorted([p for p in act if p["p"] == pos], key=lambda p: -p["fp"])[:n]
star = top("RB", 1)[0]                                                                  # the best back on the board: rostered by the other team
stale = sorted([p for p in act if p.get("gn") is not None and p["gn"] <= 2 and p.get("idle", 0) >= 2], key=lambda p: -p["fp"])
thin = sorted([p for p in act if p.get("gn") is not None and p["gn"] <= 2 and p.get("idle", 0) < 2 and p["fp"] > 3], key=lambda p: -p["fp"])
mine = top("QB", 2)[1:] + top("RB", 30)[20:23] + top("WR", 40)[30:33] + top("TE", 20)[12:13]
def sp(p, i, team=None, pos=None, name=None): return str(i), {"full_name": name or p["n"], "first_name": "x", "last_name": "y", "position": pos or p["p"], "team": p["t"] if team is None else team, "fantasy_positions": [pos or p["p"]]}
pm = {}; ids = {}
for i, p in enumerate(mine): k, v = sp(p, 100 + i); pm[k] = v
k, v = sp(star, 200); pm[k] = v
bare = re.sub(r"\s+(Jr\.?|Sr\.?|II|III|IV)$", "", star["n"])
k, v = sp(star, 201, team="", name=bare); pm[k] = v                                    # Sleeper's other, unsigned man of the same name
k, v = sp(star, 202, team="", pos="WR", name=bare); pm[k] = v                          # ... and one at another position
if stale: k, v = sp(stale[0], 300); pm[k] = v
if thin: k, v = sp(thin[0], 301); pm[k] = v
L = {"league_id": "L1", "name": "Test League", "total_rosters": 2, "status": "in_season", "season": "2026", "settings": {"type": 0}, "scoring_settings": {"rec": 1, "pass_td": 4}, "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN", "BN", "BN"]}
R = [{"roster_id": 1, "owner_id": "u1", "players": [str(100 + i) for i in range(len(mine))], "starters": [str(100 + i) for i in range(7)], "settings": {"wins": 5, "losses": 5, "ties": 0, "fpts": 1000}},
     {"roster_id": 2, "owner_id": "u2", "players": ["200"], "starters": ["200"], "settings": {"wins": 5, "losses": 5, "ties": 0, "fpts": 1000}}]
U = [{"user_id": "u1", "display_name": "Me", "metadata": {}}, {"user_id": "u2", "display_name": "Them", "metadata": {}}]
async def run(b, hot):
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    await ctx.add_init_script("try{localStorage.setItem('bs_sleeper_user','mock')}catch(e){}")
    async def api(route):
        u = route.request.url.split("/v1/")[1]
        if u == "state/nfl": body = {"season": "2026", "week": 11, "display_week": 11}
        elif u.startswith("user/") and "/leagues/" in u: body = [L]
        elif u.startswith("user/"): body = {"user_id": "u1", "username": "mock", "display_name": "mock"}
        elif u == "players/nfl": body = pm
        elif u.endswith("/rosters"): body = R
        elif u.endswith("/users"): body = U
        elif "trending" in u: body = [{"player_id": "300", "count": 900}] if hot else []
        else: body = []
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
    await ctx.route("**/api.sleeper.app/v1/**", api); await ctx.route("**/*supabase*/**", lambda r: r.abort())
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    await pg.goto(f"http://127.0.0.1:{PORT}/team/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2500)
    if not await pg.evaluate("(document.getElementById('waiv') || {}).innerHTML"):
        for sel in ("[data-league='L1']", ".lg", "#lglist button", "#lglist a"):
            if await pg.query_selector(sel): await pg.click(sel); await pg.wait_for_timeout(1500); break
    rows = await pg.evaluate("[...document.querySelectorAll('#waiv li')].map(function(li){ return li.querySelector('b').textContent + ' || ' + [...li.querySelectorAll('.bt')].map(function(x){ return x.textContent; }).join(',') })")
    await ctx.close(); return rows, errs
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        rows, errs = await run(b, False); names = [r.split(" || ")[0] for r in rows]
        check(len(rows) >= 1 and not errs, f"the Waivers tab fills from the stand-in league ({len(rows)} rows; {errs[:1]})")
        check(not any(n.startswith(bare) for n in names), f"a rostered player ({star['n']}) is not offered through an unsigned or other-position Sleeper entry of the same name ({names})")
        if stale: check(stale[0]["n"] not in names, f"{stale[0]['n']} ({stale[0]['gn']} game, last played Week {stale[0]['lw']}, {stale[0]['idle']} team games since, projected {stale[0]['fp']}) is left off")
        if thin:
            r = [x for x in rows if x.startswith(thin[0]["n"])]; check(bool(r) and "game" in r[0], f"{thin[0]['n']} (played lately, {thin[0]['gn']} games in all) stays on with a small-sample tag ({r})")
        if stale:
            rows2, _ = await run(b, True); r = [x for x in rows2 if x.startswith(stale[0]["n"])]
            check(bool(r) and "last played Wk" in r[0], f"when Sleeper managers are adding him today, {stale[0]['n']} is listed again, marked with the week he last played ({r})")
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
