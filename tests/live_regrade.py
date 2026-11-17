"""The Live page puts right the results it saved for earlier weeks (11/17).

Until 11/17 the page could save a loss for a leg it had no numbers for. A rolled week cannot heal itself, so each saved earlier week
(bs_log_w<W>) is checked once against that week's graded file (/data/box-w<W>.json). Only rows the file settles are changed; a game
total with no game on record, a first touchdown, a push and a player the file does not list stay exactly as saved, and no row is added or removed.

Uses the real file of the week before the one the site is on (rows are chosen from it, expected results worked out here by the same
rules), so it runs in any week. ESPN and the account service are cut off.
  python3 tests/live_regrade.py        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, math, os, re, sys, threading
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); PORT = 8864; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
_ref = re.search(r"/live/(data-[0-9a-f]+\.js)", open(os.path.join(ROOT, "live", "index.html")).read())
SRC = open(os.path.join(ROOT, "live", _ref.group(1))).read(); _m = re.match(r"\s*window\.__LV\s*=\s*", SRC); D = json.loads(SRC[_m.end():].rstrip().rstrip(";")); WEEK = int(D["week"]); PW = WEEK - 1
BOXF = os.path.join(ROOT, "data", f"box-w{PW}.json")

async def main():
    if not os.path.exists(BOXF): print(f"SKIP: no graded file for week {PW} in this copy of the site"); return
    box = json.load(open(BOXF)); B = box["box"]; G = box["games"]; nick = D.get("nick") or {}
    if not nick: check(False, "the page data carries the team nickname map (D.nick)"); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1)
    ab2nick = {v: k for k, v in nick.items()}
    pick = lambda f: next((n for n in sorted(B) if f(B[n])), None)
    rec = pick(lambda b: b[6] >= 60); rush = pick(lambda b: b[3] >= 60 and b[4] + b[7] >= 1); qb = pick(lambda b: b[0] >= 200 and b[1] >= 1); low = pick(lambda b: 1 <= b[5] <= 3 and b[6] > 0); zero = pick(lambda b: b[4] + b[7] == 0 and b[5] >= 2)
    g0 = next(k for k, v in sorted(G.items()) if v[0] != v[1]); away, home = g0.split("-"); sa, sh = G[g0]; win, lose = (home, away) if sh > sa else (away, home); margin = abs(sh - sa); tot = sa + sh
    need = {"a 60-yard receiver": rec, "a 60-yard rusher who scored": rush, "a 200-yard passer with a TD": qb, "a player with 1-3 catches": low, "a player with 2+ catches and no TD": zero}
    if not all(need.values()): print("SKIP: last week's file lacks " + ", ".join(k for k, v in need.items() if not v)); return
    # rows as the bug left them (every one a loss), with what the file says they should be. None = the file cannot settle it: left as saved.
    rows = [([rec, "Receiving Yards", 50, -150, 0], 1, "a receiver who cleared 50"),
            ([rec, "Receiving Yards", 400, 900, 0], 0, "the same receiver at a line he did not reach"),
            ([rush, "Anytime TD", 1, 120, 0], 1, "a scorer's anytime TD"),
            ([rush, "Rushing Yards", 60, -115, 0], 1, "his 60+ rushing yards"),
            ([qb, "Passing TDs", 1, -250, 0], 1, "a passer's 1+ passing TD"),
            ([low, "Under Receptions", 3.5, -110, 0], 1, "an under 3.5 catches that came in"),
            ([low, "Under Receptions", 0.5, 400, 1], 0, "an under 0.5 catches saved as a win that lost"),
            ([zero, "Anytime TD", 1, 250, 0], None, "a man the file shows no rushing or receiving touchdown for, saved as a loss"),
            ([zero, "Anytime TD", 1, 251, 1], None, "the same leg saved as a win (a return touchdown is not in the file, so a TD leg is never taken away)"),
            ([f"{ab2nick[win]} ML", "Moneyline", 0, -150, 0], 1, "the winner's moneyline"),
            ([f"{ab2nick[lose]} ML", "Moneyline", 0, 130, 1], 0, "the loser's moneyline saved as a win"),
            ([f"{lose} +{margin + 0.5}", "Spread", margin + 0.5, -110, 0], 1, "the loser covering a bigger spread"),
            ([f"{win} -{margin}", "Spread", -margin, -110, 0], None, "a spread that landed exactly on the number (a push)"),
            ([f"Over {tot - 3.5}", "Total", tot - 3.5, -110, 0], 1, "a game total a saved slip put on record for its game"),
            ([f"Under {tot - 3.5}", "Total", tot - 3.5, -110, 1], 0, "the under on that same total, saved as a win"),
            ([f"Over {tot + 20.5}", "Total", tot + 20.5, -110, 0], None, "a game total with no game on record (the row does not say which game)"),
            ([rush, "First TD", 1, 900, 0], None, "a first touchdown"),
            (["Nobody Atall", "Receiving Yards", 20, -110, 0], None, "a player the file does not list")]
    jsr = lambda x: int(math.floor(x + 0.5)); gid = "-".join(sorted([away, home]))
    slips = [{"id": "p1", "name": "old slip", "keys": [f"Over {tot - 3.5}|Total|{jsr(tot - 3.5)}", f"Under {tot - 3.5}|Total|{jsr(tot - 3.5)}"], "g": {f"Over {tot - 3.5}|Total|{jsr(tot - 3.5)}": [gid], f"Under {tot - 3.5}|Total|{jsr(tot - 3.5)}": [gid]}}]
    saved = [r for r, _, _ in rows]; want = [dict(zip("pmloh", r)) for r, _, _ in rows]
    expect = [[*r[:4], (r[4] if e is None else e)] for r, e, _ in rows]
    other = [[rec, "Receiving Yards", 50, -150, 0]]                      # the week the site is on is never touched by this
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
        ls = {"bs_theme": "dark", f"bs_log_w{PW}": json.dumps(saved), f"bs_slips_w{PW}": json.dumps(slips), "bs_live_hub": "__season"}
        await ctx.add_init_script("try{" + "".join(f"if(localStorage.getItem({json.dumps(k)})===null)localStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in ls.items()) + "}catch(e){}")
        asked = []
        async def on_box(route, request): asked.append(request.url.split("/")[-1]); await route.continue_()
        await ctx.route("**/data/box-w*.json", on_box); await ctx.route("**/*espn.com/**", lambda r: r.abort()); await ctx.route("**/*supabase*/**", lambda r: r.abort()); await ctx.route("**/raw.githubusercontent.com/**", lambda r: r.abort())
        pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        await pg.goto(f"http://127.0.0.1:{PORT}/live/", wait_until="domcontentloaded"); await pg.wait_for_timeout(6500)
        got = await pg.evaluate(f"() => JSON.parse(localStorage.getItem('bs_log_w{PW}'))")
        for (r, e, what), g in zip(rows, got):
            check(g[:4] == r[:4] and g[4] == (r[4] if e is None else e), f"{what}: " + ("left as saved" if e is None else f"saved as {'a win' if r[4] else 'a loss'}, now {'a win' if e else 'a loss'}") + f" ({r[0]} {r[1]} {r[2]})")
        check(len(got) == len(saved), f"no row is added or removed ({len(got)} of {len(saved)})")
        s = await pg.evaluate("""() => ({tab: (document.querySelector('.hubb[data-hub="__season"] small') || {}).textContent, note: Array.from(document.querySelectorAll('#lv .seasoncard .logbar')).map(function(e){ return e.textContent; }).filter(function(t){ return /corrected/.test(t); })[0] || '', chk: localStorage.getItem('bs_logchk')})""")
        nfix = sum(1 for r, e, _ in rows if e is not None and e != r[4]); w = sum(1 for r in expect if r[4]); l = len(expect) - w
        check(s["tab"] == f"{w}–{l}" and f"{nfix} saved results were corrected" in s["note"], f"My season shows the corrected record ({s['tab']}) and says {nfix} saved results were corrected")
        check(asked.count(f"box-w{PW}.json") == 1 and not errs, f"the week's file was read once ({asked}); no page errors {errs[:1]}")
        # a second visit does not read the file again or change anything
        asked.clear(); await pg.goto(f"http://127.0.0.1:{PORT}/live/?again=1", wait_until="domcontentloaded"); await pg.wait_for_timeout(5500)
        got2 = await pg.evaluate(f"() => JSON.parse(localStorage.getItem('bs_log_w{PW}'))")
        check(got2 == got and not asked, f"a week already checked is not read again ({asked or 'no file asked for'})")
        # the saved text changes (a stale copy comes back from another device): it is checked again
        await pg.evaluate(f"(v) => localStorage.setItem('bs_log_w{PW}', v)", json.dumps(saved)); asked.clear()
        await pg.goto(f"http://127.0.0.1:{PORT}/live/?stale=1", wait_until="domcontentloaded"); await pg.wait_for_timeout(5500)
        got3 = await pg.evaluate(f"() => JSON.parse(localStorage.getItem('bs_log_w{PW}'))")
        check(got3 == got and asked.count(f"box-w{PW}.json") == 1, "if the old copy comes back (another device), it is put right again")
        await ctx.close(); await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
