"""Passing TDs on the matchup boards (owner 11/23: "How come I can't add passing TDs from the matchup boards").
The QB's "pass TD" box carries FanDuel's main passing-TD line with a +, priced the builder's way, so the board and the builder show the
same number for the same rung, and the + puts that rung in the betslip. Needs a built out/ and site/ (the day's lines decide how many QBs
have one; with none on the board the page checks say so and pass).   python3 tests/boards_ptd.py [shots_dir]"""
import asyncio, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.environ.get("SITE") or os.path.join(HERE, "site"); OUT = os.environ.get("OUT") or os.path.join(HERE, "out")
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None; PORT = 8891
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)

src = open(os.path.join(HERE, "build_boards.py"), encoding="utf-8").read()
check('MK_OF["pass TD"] = "Passing TDs"' in src and 'c("pass TD", ptd, "QB Pass TD")' in src and "for l in LEGS + PTD_LEGS:" in src,
      "the QB pass TD box goes through the same FanDuel note and + as the yards boxes, and its rungs are embedded for the slip")
check("PTD_LEGS.append" in src and not re.search(r'(?<!PTD_)LEGS\.append\(\{"player": _bn', src), "the passing-TD legs are kept out of LEGS, so the boards' parlays, script plays and picks do not change")

page = open(os.path.join(SITE, "boards", "index.html"), encoding="utf-8").read()
m = re.search(r"window\.__BSL = (\{.*?\});", page, re.S)
if not m:   # the published page moves the slip data into a hashed file next to it
    dn = re.search(r'src="/boards/(data-[0-9a-f]+\.js)"', page)
    if dn: m = re.search(r"window\.__BSL = (\{.*\});?", open(os.path.join(SITE, "boards", dn.group(1)), encoding="utf-8").read(), re.S)
S = json.loads(m.group(1).rstrip(";")) if m else {"legs": []}
emb = [l for l in S["legs"] if l.get("m") == "Passing TDs"]
pluses = re.findall(r'data-k="([^"]*\|Passing TDs\|\d+)"', page)
try:
    bd = json.load(open(os.path.join(OUT, "builder_data.json")))
    B = {f"{l['pl']}|Passing TDs|{int(round(l['ln']))}": l for l in bd["legs"] if l.get("m") == "Passing TDs"}
except Exception: B = None
print(f"   {len(pluses)} passing-TD + buttons, {len(emb)} passing-TD rungs embedded" + ("" if B is None else f", {len(B)} in the builder"))
check(all(k in {l["k"] for l in emb} for k in pluses), "every passing-TD + has its rung in the page's slip data")
if B is not None:
    off = [l["k"] for l in emb if l["k"] not in B or abs(l["p"] - B[l["k"]]["p"]) > 1e-9 or l["o"] != B[l["k"]]["o"]]
    check(not off, f"every embedded passing-TD rung shows exactly the builder's chance and price ({len(emb)} rungs" + (f"; first off: {off[0]}" if off else "") + ")")
    qbs_b = {k.split("|")[0] for k in B}; qbs_pl = {k.split("|")[0] for k in pluses}
    check(qbs_pl <= qbs_b, f"a + only where the builder prices the same quarterback ({sorted(qbs_pl)})")
check(all(l.get("fd") for l in emb), "each rung carries its FanDuel ids, so the slip's link works")
fds = [x.group(1) for seg in page.split('<small>pass TD</small>')[1:] for x in [re.search(r'^(?:(?!<span class="sc").)*?<span class="fd[^"]*"[^>]*>FD [\d.]+ <b>([^<]*)</b>', seg, re.S)] if x]
check(all(re.fullmatch(r"[+-]\d+\.\d", x) for x in fds), f"the pass TD note shows the difference to one decimal ({fds[:3]})")

async def main():
    if not pluses: print("   no passing-TD line on the board today: page tap skipped"); return
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=SITE)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    k0 = pluses[0]; leg = next(l for l in emb if l["k"] == k0); ko = leg.get("ko") or 0
    freeze = f"(function(){{ var T = {int(ko) - 3600000 if ko else 0}; if(T) Date.now = function(){{ return T; }}; }})();"
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme, vp in (("light", (390, 844)), ("dark", (390, 844)), ("dark", (1280, 900))):
            ctx = await b.new_context(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=2, is_mobile=vp[0] < 700, has_touch=vp[0] < 700)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + freeze)
            await ctx.route("**/cdn.jsdelivr.net/**", lambda r: r.abort()); await ctx.route("**/*supabase.co/**", lambda r: r.abort())
            await ctx.route("**/*espn.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body='{"events":[]}'))
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/boards/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            r = await pg.evaluate("""(k) => { var b = document.querySelector('button.addbs[data-k="' + k + '"]'); if(!b) return {found: false};
                var card = b.closest('.card'), v = card && card.querySelector('.vbtn[data-view="proj"]'); if(v) v.click();
                var li = b.closest('li'); if(li){ var row = li.querySelector('.prow'); if(row && row.getAttribute('aria-expanded') !== 'true') row.click(); }
                return {found: true}; }""", k0)
            await pg.wait_for_timeout(500)
            if r.get("found"):
                r = await pg.evaluate("""(k) => { var b = document.querySelector('button.addbs[data-k="' + k + '"]'); b.scrollIntoView({block: 'center'}); var rr = b.getBoundingClientRect(), y = document.querySelector('button.addbs[data-k*="|Passing Yards|"]');
                  var ry = y ? y.getBoundingClientRect() : null; return {found: true, w: Math.round(rr.width), h: Math.round(rr.height), vis: rr.width > 0 && rr.height > 0, yards_w: ry ? Math.round(ry.width) : null}; }""", k0)
                await pg.wait_for_timeout(300)
            check(r.get("found") and r.get("vis"), f"[{theme} {vp[0]}px] the + on {k0} is on screen once the QB's row is open ({r})")
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/boards-ptd-{theme}-{vp[0]}.png")
            await pg.evaluate("(k) => document.querySelector('button.addbs[data-k=\"' + k + '\"]').click()", k0); await pg.wait_for_timeout(700)
            st = await pg.evaluate("(k) => { var hits = []; for (var i = 0; i < localStorage.length; i++){ var n = localStorage.key(i), v = localStorage.getItem(n) || ''; if (v.indexOf(k) >= 0) hits.push(n); } return hits; }", k0)
            check(len(st) >= 1, f"[{theme} {vp[0]}px] tapping it puts {k0} in the betslip (saved under {st})")
            check(not errs, f"[{theme} {vp[0]}px] no script errors {errs[:2]}")
            await ctx.close()
        await b.close()
    srv.shutdown()
asyncio.run(main())
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
