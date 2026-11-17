"""The builder shows FanDuel's same-game price as an estimate, not the legs multiplied (owner 11/17: the same-game discount).
Serves ./site at phone size, light and dark.
  python3 tests/sgp_price.py [shots_dir]"""
import asyncio, json, math, os, re, sys, threading, http.server, functools, urllib.parse
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); GP = os.path.join(HERE, "..")
sys.path.insert(0, GP); sys.path.insert(0, os.path.join(GP, "research"))
import sgp, sgp_discount
ROOT = os.path.join(GP, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
def dec(o): return 1 + o / 100 if o > 0 else 1 + 100 / (-o)
def am_to_dec(t):
    m = re.search(r"([+-]\d+)", t.replace("−", "-")); return dec(float(m.group(1))) if m else None

idx = open(os.path.join(ROOT, "build", "index.html")).read(); f = re.search(r"data-[0-9a-f]{8,}\.js", idx).group(0)
src = open(os.path.join(ROOT, "build", f)).read(); D = json.loads(src[src.index("{"):src.rindex("}") + 1])
S = D.get("sgp") or {}
check(bool(S) and 0 < S.get("c", 0) < 0.05 and "note" in S, f"the page's data carries the measured discount (c = {S.get('c')}, {S.get('quotes')} quotes)")
legs = [l for l in D["legs"] if not l.get("gl") and l.get("o") is not None and l.get("fd") and l["m"] in ("Passing Yards", "Receiving Yards", "Receptions", "Rushing Yards") and -400 <= l["o"] <= 250]
by = {}
for l in legs: by.setdefault(l["g"], []).append(l)
pair = None
for g, v in by.items():
    q = next((l for l in v if l["m"] == "Passing Yards"), None)
    w = next((l for l in v if q and l["m"] == "Receiving Yards" and l["tm"] == q["tm"] and l["pos"] == "WR"), None)
    if q and w: pair = (q, w); break
check(pair is not None, "a game with a quarterback's passing yards and his receiver's yards priced at FanDuel")
other = next((l for l in legs if pair and l["g"] != pair[0]["g"]), None)
check(other is not None, "a second game with a priced leg")
key = lambda l: f'{l["pl"]}|{l["m"]}|{round(l["ln"] or 1)}'
joint = sgp_discount.make_joint(D)
pb = joint([dict(x) for x in pair]) if pair else None
want = sgp.price(2, pb, S["c"]) if pair else None
mult2 = dec(pair[0]["o"]) * dec(pair[1]["o"]) if pair else None

READ = """() => { var p = document.querySelector('#price'), d = p ? p.querySelector('div') : null, o = document.documentElement;
  return {price: d ? d.querySelector('b').textContent : '', sub: d ? d.querySelector('span').textContent : '', why: p && p.querySelector('.sgwhy') ? p.querySelector('.sgwhy').textContent : '',
          bar: (document.querySelector('.slipbar b') || {}).textContent || '', pay: p ? Array.from(p.querySelectorAll('.wide small')).map(function(x){ return x.textContent; }).join(' | ') : '',
          tgt: (document.querySelector('#tgt .row span') || {}).textContent || '', n: document.querySelectorAll('#slip li, #sliplist li').length, over: o.scrollWidth - o.clientWidth}; }"""
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8861), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            # the clock sits before the week's first kickoff so every leg is open whatever day the test runs
            t0 = min((g.get("ko") or 0) for g in D["games"] if g.get("ko")) - 3 * 3600 * 1000
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}; (function(){{ var T = {t0}; Date.now = function(){{ return T; }}; }})();")
            await ctx.route("**/site.api.espn.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body='{"events":[]}'))
            await ctx.route("**/*supabase*/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            q = lambda ls: "?new=1&" + "&".join("add=" + urllib.parse.quote(key(l)) for l in ls)
            # one leg per game: the legs multiplied, no "about" mark
            await pg.goto("http://127.0.0.1:8861/build/" + q([pair[0], other]), wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            s = await pg.evaluate(READ); m = dec(pair[0]["o"]) * dec(other["o"])
            check("≈" not in s["price"] and "legs multiplied" in s["sub"] and not s["why"], f"{theme}: two games, one leg each - the price is the legs multiplied ({s['price']}; {s['sub'][:40]})")
            check(abs(am_to_dec(s["price"]) / m - 1) < 0.02, f"{theme}: and it equals the legs multiplied ({s['price']} vs {m:.2f})")
            check("≈" not in s["bar"], f"{theme}: the slip bar has no about mark ({s['bar']})")
            # two legs in one game: the estimate
            await pg.goto("http://127.0.0.1:8861/build/" + q(list(pair)), wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            s = await pg.evaluate(READ); got = am_to_dec(s["price"])
            check(s["price"].startswith("≈") and "same-game estimate" in s["sub"] and "legs multiply to" in s["sub"], f"{theme}: two legs in one game - the price is marked as an estimate ({s['price']}; {s['sub'][:60]})")
            check(got is not None and abs(got / want - 1) < 0.05, f"{theme}: the estimate matches the Python fit ({s['price']} vs {want:.3f}; legs multiply to {mult2:.3f})")
            check(got is not None and got < mult2, f"{theme}: a quarterback with his receiver is priced under the legs multiplied ({got:.3f} < {mult2:.3f})")
            check("FanDuel prices same-game legs together" in s["why"] and "Check the quote" in s["why"], f"{theme}: the panel says why, with the measured numbers ({s['why'][28:110]})")
            check("≈" in s["bar"], f"{theme}: the slip bar carries the about mark ({s['bar']})")
            check("about that price" in s["pay"], f"{theme}: the payout line says about ({s['pay'][:60]})")
            check(s["tgt"] in ("", "Target price (legs multiplied)"), f"{theme}: the target slider says it works on the legs multiplied ({s['tgt']})")
            # the verdict note
            btn = await pg.query_selector("#sweepbtn")
            if btn:
                await pg.evaluate("document.querySelector('.slipwrap') && document.querySelector('.slipwrap').classList.add('open')")
                await btn.click(); await pg.wait_for_timeout(700)
                v = await pg.evaluate("(document.querySelector('#sweepv') || {}).textContent || ''")
                check("our estimate of FanDuel" in v and "legs multiplied; FanDuel" not in v, f"{theme}: Sweep this slip names the estimate ({v[v.find('At '):v.find('At ') + 110]})")
            check(s["over"] <= 1, f"{theme}: no sideways scroll ({s['over']})")
            check(not errs, f"{theme}: no script errors {errs[:2]}")
            if SHOTS:
                os.makedirs(SHOTS, exist_ok=True)
                await pg.evaluate("document.querySelector('#price') && document.querySelector('#price').scrollIntoView({block: 'center'})"); await pg.wait_for_timeout(300)
                await pg.screenshot(path=os.path.join(SHOTS, f"sgp_{theme}.png"))
            await ctx.close()
        await b.close()
    srv.shutdown()
asyncio.run(main())
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
