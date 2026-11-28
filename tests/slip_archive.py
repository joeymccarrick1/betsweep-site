"""A saved slip leaves the betslip the moment it is decided or its first game kicks off (owner 11/27 8:48 PM: "Whenever saved slips bust
or win they need to be immediately archived. Muddies up a users betslip").

Before: the Saved list in the betslip (Parlay Builder and Matchup Boards) kept every slip of the week, won, lost or in play, with dead
prices and Load / FanDuel buttons; My BetSweep listed open and settled slips mixed together.

Now: a slip marked decided (res on the saved slip: the Live page and My BetSweep write it when they grade) or whose first game has
kicked off is out of the Saved list, with one line saying where it went; My BetSweep shows this week's open slips first and the settled
ones under a fold, and writes the mark itself when the box scores decide a slip. Nothing is deleted.

Built from the page's own data, so it runs in any week: slips are made from this week's legs, the page clock is set between two
kickoffs, and the box scores My BetSweep grades from are invented so chosen slips win and lose. The Live page's side is in live_finals.
  python3 tests/slip_archive.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, math, os, re, sys, threading
from playwright.async_api import async_playwright
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8900; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
bh = open(os.path.join(ROOT, "build", "index.html"), encoding="utf-8").read(); _m = re.search(r'src="(/build/data-[0-9a-f]+\.js)"', bh)
js = open(os.path.join(ROOT, _m.group(1).lstrip("/")), encoding="utf-8").read(); BS = json.JSONDecoder().raw_decode(js[js.index("{", js.index("window.__BS = ")):])[0]
W = BS["week"]; GAMES = {g["gid"]: g for g in BS["games"] if g.get("ko")}
def key(l): return f'{l["pl"]}|{l["m"]}|{int(math.floor(float(l.get("ln") or 1) + 0.5))}'
kos = sorted({g["ko"] for g in GAMES.values()})
STAT = {"Receiving Yards": 6, "Rushing Yards": 3, "Receptions": 5, "Passing Yards": 0}
def props(gid): return [l for l in BS["legs"] if l["g"] == gid and not l.get("gl") and not l.get("u") and l["m"] in STAT and " or " not in l["pl"]]
# the latest kickoff slot holds the slips that stay open; an earlier slot holds the one that has kicked off
LATE = [g for g in GAMES.values() if g["ko"] == kos[-1] and len({l["pl"] for l in props(g["gid"])}) >= 3]
EARLY = [g for g in GAMES.values() if g["ko"] < kos[-1]]
NOW = (kos[-1] - 3600e3) if len(kos) > 1 else None          # an hour before the last kickoff: every earlier game has started
def early_key():
    """a leg of an earlier game that is still on the builder's board (a finished game keeps its game lines), with its game"""
    for g in sorted(EARLY, key=lambda g: -g["ko"]):
        for l in BS["legs"]:
            if l["g"] == g["gid"] and (l.get("gl") or l["m"] in STAT): return key(l), g["gid"], l
    return None, None, None

READ_TRAY = """(sel) => { var box = document.querySelector(sel); if(!box) return null; var rows = Array.from(box.querySelectorAll('tbody tr:not(.lgrow)')).map(function(tr){ return (tr.querySelector('td.nm b') || {textContent: ''}).textContent.trim(); });
  var mv = box.querySelector('.moved'); var all = []; try { all = JSON.parse(localStorage.getItem('bs_slips_w' + %d) || '[]'); } catch(e){}
  return {rows: rows, moved: mv ? mv.textContent.replace(/\\s+/g, ' ').trim() : '', links: mv ? Array.from(mv.querySelectorAll('a')).map(function(a){ return a.getAttribute('href'); }) : [], none: (box.querySelector('p.none:not(.moved)') || {textContent: ''}).textContent.slice(0, 40),
          stored: all.map(function(x){ return x.id; }), over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }""" % W

async def main():
    if NOW is None or not LATE or not EARLY:
        print("SKIP: this week's board has one kickoff slot only (or no late game with three players) - nothing to tell an open slip from a started one"); return
    L = LATE[0]; pl = []
    for l in sorted(props(L["gid"]), key=lambda l: (l["pl"], l["m"], l["ln"])):
        if l["pl"] not in [x["pl"] for x in pl]: pl.append(l)
        if len(pl) == 3: break
    ek, egid, eleg = early_key()
    if not ek: print("SKIP: no leg of an earlier game is on the board any more"); return
    gone_pl = "Zz Archive Tester"       # a player who is on no board: placed only through the team list
    eg = GAMES[egid]; PT = {gone_pl: eg["a"]}
    SLIPS = [{"id": "open1", "name": "Open one", "keys": [key(pl[0]), key(pl[1])], "odds": 250, "stake": 1},
             {"id": "kick1", "name": "Kicked off", "keys": [ek, key(pl[2])], "odds": 300, "stake": 1},
             {"id": "won1", "name": "Marked won", "keys": [key(pl[0])], "odds": 120, "stake": 1, "res": "W", "resAt": 1},
             {"id": "gone1", "name": "Off the board", "keys": [f"{gone_pl}|Receiving Yards|40"], "odds": 110, "stake": 1}]
    print(f"   week {W}; open game {L['gid']}; earlier game {egid} (leg {ek}); the clock is an hour before {L['gid']} kicks off")
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def open_(path, theme, slips, now=NOW, box=None, pt=True):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block", color_scheme=theme)
            ls = {"bs_theme": theme, f"bs_slips_w{W}": json.dumps(slips)}
            await ctx.add_init_script("try{" + "".join(f"if(localStorage.getItem({json.dumps(k)})===null)localStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in ls.items()) + "}catch(e){}"
                                      + (f";(function(){{var T={int(now)},R=Date.now,S=R();Date.now=function(){{return T+(R()-S)}};}})();" if now else ""))
            async def gate(route, request):
                u = request.url
                if "127.0.0.1" not in u: await route.abort(); return
                if "/data/pteam.json" in u:
                    if not pt: await route.fulfill(status=404, body=""); return
                    base = {}
                    try: base = json.load(open(os.path.join(ROOT, "data", "pteam.json")))
                    except Exception: pass
                    await route.fulfill(status=200, content_type="application/json", body=json.dumps(dict(base, **PT))); return
                if box is not None and f"/data/box-w{W}.json" in u: await route.fulfill(status=200, content_type="application/json", body=json.dumps(box)); return
                if f"/data/close-w{W}.json" in u: await route.fulfill(status=404, body=""); return
                await route.continue_()
            await ctx.route("**/*", gate)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}{path}", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600)
            return pg, ctx, errs
        for theme in ("dark", "light"):
            for path, sel, name in (("/build/", "#savedList", "Parlay Builder"), ("/boards/", "#bsavedList", "Matchup Boards")):
                pg, ctx, errs = await open_(path, theme, SLIPS); s = await pg.evaluate(READ_TRAY, sel)
                print(f"   [{theme}] {name}:", json.dumps(s)[:420])
                check(s is not None and s["rows"] == ["Open one"], f"[{theme}] {name}: the Saved list holds only the slip that can still be sent ({s and s['rows']})")
                check(s is not None and s["moved"].startswith("3 saved slips have kicked off or settled") and s["links"] == ["/live/", "/me/#crec"], f"[{theme}] {name}: one line says three slips moved - one kicked off, one marked won, one whose player's team has kicked off - and links to Live and My BetSweep ({s and s['moved'][:70]!r})")
                check(s is not None and s["stored"] == ["open1", "kick1", "won1", "gone1"] and s["over"] <= 0 and not errs, f"[{theme}] {name}: nothing is deleted - all four slips are still saved on the device; no sideways scroll, no page errors ({s and s['stored']}, {errs[:1]})")
                if SHOTS:
                    await pg.evaluate("(sel) => { var b = document.getElementById('bslip'); if(b) b.classList.add('open'); var e = document.querySelector(sel); if(e) e.scrollIntoView({block: 'center'}); }", sel); await pg.wait_for_timeout(400)
                    await pg.screenshot(path=os.path.join(SHOTS, f"slip_archive_{'build' if 'build' in path else 'boards'}_{theme}.png"))
                await ctx.close()
            # only decided slips saved: the list says where they went, not "Nothing saved yet"
            pg, ctx, errs = await open_("/build/", theme, SLIPS[1:]); s = await pg.evaluate(READ_TRAY, "#savedList")
            check(s["rows"] == [] and s["moved"].startswith("3 saved slips") and not s["none"], f"[{theme}] with nothing left to send the list is that one line, not 'Nothing saved yet' ({s['moved'][:50]!r}, {s['none']!r})")
            await ctx.close()
            # before any kickoff nothing has moved except the slip already marked
            pg, ctx, errs = await open_("/build/", theme, SLIPS, now=kos[0] - 6 * 3600e3); s = await pg.evaluate(READ_TRAY, "#savedList")
            check(sorted(s["rows"]) == ["Kicked off", "Off the board", "Open one"] and s["moved"].startswith("1 saved slip has "), f"[{theme}] six hours before the week's first kickoff only the marked slip is away ({sorted(s['rows'])}, {s['moved'][:40]!r})")
            await ctx.close()
            # the team list cannot be read: a slip is never put away on a guess
            pg, ctx, errs = await open_("/build/", theme, SLIPS, pt=False); s = await pg.evaluate(READ_TRAY, "#savedList")
            check(sorted(s["rows"]) == ["Off the board", "Open one"] and not errs, f"[{theme}] without the player-team list a leg that is on no board is not guessed at: that slip stays ({sorted(s['rows'])})")
            await ctx.close()

            # ---- My BetSweep: open first, settled under a fold, marks written from the box scores ----
            a, c, d = pl[0], pl[1], pl[2]
            def row(l, hit):
                r = [0] * 9; r[STAT[l["m"]]] = (float(l["ln"]) + 20) if hit else max(0.0, float(l["ln"]) - 20 if float(l["ln"]) >= 21 else 0.0); return r
            box = {"games": {L["gid"]: [24, 17]}, "box": {a["pl"]: row(a, True), c["pl"]: row(c, False)}}     # d has no line: his slip stays open
            mine = [{"id": "w", "name": "Wins", "keys": [key(a)], "odds": 150, "stake": 1}, {"id": "l", "name": "Loses", "keys": [key(a), key(c)], "odds": 300, "stake": 1}, {"id": "o", "name": "Still open", "keys": [key(d)], "odds": 110, "stake": 1}]
            pg, ctx, errs = await open_("/me/", theme, mine, now=None, box=box); await pg.wait_for_timeout(1200)
            READ_ME = """() => { var vis = function(e){ return !!(e.offsetWidth || e.offsetHeight); }, rows = Array.from(document.querySelectorAll('#slips li.sl')).filter(function(li){ return li.querySelector(':scope > b'); });
              var st = document.querySelector('#slips .setlt'), all = []; try { all = JSON.parse(localStorage.getItem('bs_slips_w%d') || '[]'); } catch(e){}
              return {shown: rows.filter(vis).map(function(li){ return [li.querySelector(':scope > b').textContent, li.querySelector('.res').textContent]; }), hidden: rows.filter(function(li){ return !vis(li); }).map(function(li){ return li.querySelector(':scope > b').textContent; }),
                      fold: st ? {txt: st.textContent.replace(/\\s+/g, ' ').trim(), open: st.getAttribute('aria-expanded')} : null, marks: all.map(function(x){ return [x.id, x.res || '']; }), hopen: (document.getElementById('hopen') || {}).textContent, rec: (document.getElementById('hrec') || {}).textContent,
                      order: Array.from(document.querySelectorAll('#slips > li')).map(function(li){ return li.classList.contains('wkh') ? 'week' : li.classList.contains('setlh') ? 'fold' : li.classList.contains('setl') ? 'settled' : li.querySelector(':scope > b') ? 'open' : 'note'; }),
                      over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }""" % W
            s = await pg.evaluate(READ_ME)
            print(f"   [{theme}] My BetSweep:", json.dumps(s)[:520])
            check(s["shown"] == [["Still open", "Not played yet"]] or (len(s["shown"]) == 1 and s["shown"][0][0] == "Still open"), f"[{theme}] My BetSweep opens on the one slip that is still open ({s['shown']})")
            check(sorted(s["hidden"]) == ["Loses", "Wins"] and s["fold"] and s["fold"]["open"] == "false" and "2 slips" in s["fold"]["txt"] and "1 cashed" in s["fold"]["txt"] and "1 missed" in s["fold"]["txt"], f"[{theme}] the two decided slips are under one Settled line, shut, that says 2 slips, 1 cashed, 1 missed ({s['fold']})")
            check(s["order"] == ["week", "open", "fold", "settled", "settled"], f"[{theme}] the order is week, open slips, the fold, then the settled ones ({s['order']})")
            check(sorted(s["marks"]) == [["l", "L"], ["o", ""], ["w", "W"]], f"[{theme}] grading from the box scores marks the decided slips on the device (W and L) and leaves the open one alone ({s['marks']})")
            check(s["hopen"] == "1" and s["rec"] == "1–1", f"[{theme}] the top of the page still counts 1 open slip and a 1-1 record ({s['hopen']}, {s['rec']})")
            await pg.evaluate("() => document.querySelector('#slips .setlt').click()"); await pg.wait_for_timeout(400); s2 = await pg.evaluate(READ_ME)
            check(sorted(x[0] for x in s2["shown"]) == ["Loses", "Still open", "Wins"] and s2["fold"]["open"] == "true" and dict((x[0], x[1]) for x in s2["shown"]).get("Wins") == "Cashed" and dict((x[0], x[1]) for x in s2["shown"]).get("Loses") == "Missed", f"[{theme}] a tap opens the fold: Wins reads Cashed and Loses reads Missed ({s2['shown']})")
            check(s2["over"] <= 0 and not errs, f"[{theme}] My BetSweep has no sideways scroll and no page errors ({s2['over']}px, {errs[:1]})")
            if SHOTS:
                await pg.evaluate("() => { var e = document.getElementById('crec'); if(e) e.scrollIntoView(); window.scrollBy(0, -80); }"); await pg.wait_for_timeout(300); await pg.screenshot(path=os.path.join(SHOTS, f"slip_archive_me_{theme}.png"))
            await ctx.close()
            # the betslip reads those marks: back on the builder, before any kickoff, the two decided slips are gone from the Saved list
            marked = [dict(m, res="W") if m["id"] == "w" else dict(m, res="L") if m["id"] == "l" else m for m in mine]
            pg, ctx, errs = await open_("/build/", theme, marked, now=kos[0] - 6 * 3600e3); s = await pg.evaluate(READ_TRAY, "#savedList")
            check(s["rows"] == ["Still open"] and s["moved"].startswith("2 saved slips"), f"[{theme}] the betslip reads the marks My BetSweep wrote: only the open slip is listed ({s['rows']}, {s['moved'][:40]!r})")
            await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
