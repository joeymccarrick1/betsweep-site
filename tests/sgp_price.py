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
# 11/23: on a Monday one game is left in the week, so there is no second game to pair with. That is the calendar, not a fault (the test
# failed the first Monday it ran). With priced legs in one game only, the two-game checks are skipped and the run says so; with legs in
# several games and no second one found, it is still a failure.
ONE_GAME = pair is not None and other is None and len(by) == 1
if ONE_GAME: print(f"NOTE priced legs in one game only ({pair[0]['g']}): the two-game checks are skipped this run")
else: check(other is not None, "a second game with a priced leg")
key = lambda l: f'{l["pl"]}|{l["m"]}|{round(l["ln"] or 1)}'
joint = sgp_discount.make_joint(D)
pb = joint([dict(x) for x in pair]) if pair else None
want = sgp.price(2, pb, S) if pair else None
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
            if not ONE_GAME:
                await pg.goto("http://127.0.0.1:8861/build/" + q([pair[0], other]), wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
                s = await pg.evaluate(READ); m = dec(pair[0]["o"]) * dec(other["o"])
                check("≈" not in s["price"] and "legs multiplied" in s["sub"] and not s["why"], f"{theme}: two games, one leg each - the price is the legs multiplied ({s['price']}; {s['sub'][:40]})")
                check(abs(am_to_dec(s["price"]) / m - 1) < 0.02, f"{theme}: and it equals the legs multiplied ({s['price']} vs {m:.2f})")
                check("≈" not in s["bar"], f"{theme}: the slip bar has no about mark ({s['bar']})")
                check(not await pg.evaluate("!!document.querySelector('#sgq')"), f"{theme}: no quote box when every leg is from a different game")
            # two legs in one game: the estimate
            await pg.goto("http://127.0.0.1:8861/build/" + q(list(pair)), wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            s = await pg.evaluate(READ); got = am_to_dec(s["price"])
            check(s["price"].startswith("≈") and "same-game estimate" in s["sub"] and "legs multiply to" in s["sub"], f"{theme}: two legs in one game - the price is marked as an estimate ({s['price']}; {s['sub'][:60]})")
            check(got is not None and abs(got / want - 1) < 0.05, f"{theme}: the estimate matches the Python fit ({s['price']} vs {want:.3f}; legs multiply to {mult2:.3f})")
            # 11/17: a quarterback's passing TDs and his passing yards are one bet on the same arm - priced together, not as strangers
            allv = [l for l in D["legs"] if not l.get("gl") and l.get("o") is not None and l.get("fd") and not l.get("u")]
            ptd = next((l for l in allv if l["m"] == "Passing TDs" and -250 <= l["o"] <= 200 and any(x["pl"] == l["pl"] and x["m"] == "Passing Yards" for x in allv)), None)
            check(ptd is not None, f"{theme}: a quarterback with passing TDs and passing yards both priced at FanDuel")
            if ptd:
                py = min((x for x in allv if x["pl"] == ptd["pl"] and x["m"] == "Passing Yards"), key=lambda x: abs((x.get("bk") or 0.5) - 0.5))
                check(ptd.get("c") == "QB_PTD" and (D["corr"].get("SP|QB_PASS|QB_PTD") or 0) >= 0.4, f"{theme}: passing TDs carry a correlation code and a measured tie to passing yards ({ptd.get('c')}, {D['corr'].get('SP|QB_PASS|QB_PTD')})")
                await pg.goto("http://127.0.0.1:8861/build/" + q([ptd, py]), wait_until="domcontentloaded"); await pg.wait_for_timeout(1800); t = await pg.evaluate(READ)
                mm = re.search(r"legs multiply to ([+\-−]\d+)", t["sub"]); e2, m2 = am_to_dec(t["price"]), (am_to_dec(mm.group(1)) if mm else None)
                check(t["price"].startswith("≈") and e2 and m2 and e2 < m2 * 0.93, f"{theme}: {ptd['pl']} {int(ptd['ln'])}+ pass TDs with {int(py['ln'])}+ yards is estimated well under the legs multiplied ({t['price']} vs {mm.group(1) if mm else None})")
                await pg.goto("http://127.0.0.1:8861/build/" + q(list(pair)), wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            # 11/17: the reader types FanDuel's own price for this exact slip - every number then uses it, and "Back to the estimate" undoes it
            await pg.evaluate("document.querySelector('.slipwrap') && document.querySelector('.slipwrap').classList.add('open')")
            await pg.evaluate("document.querySelector('#sgq') && document.querySelector('#sgq').scrollIntoView({block: 'center'})"); await pg.wait_for_timeout(250)
            check(await pg.evaluate("!!document.querySelector('#sgq') && !!document.querySelector('#sgqGo') && !document.querySelector('#sgqClr')"), f"{theme}: a same-game slip has the box for FanDuel's own price")
            await pg.fill('#sgq', '300'); await pg.click('#sgqGo'); await pg.wait_for_timeout(350); q1 = await pg.evaluate(READ)
            pay = await pg.evaluate("(function(){ var w = [].slice.call(document.querySelectorAll('#price .wide')).filter(function(x){ return /Payout on/.test(x.textContent); })[0]; return w ? w.querySelector('b').textContent : ''; })()")
            check(q1["price"] == "+300" and "you typed" in q1["sub"] and "estimate was" in q1["sub"] and not q1["why"] and "≈" not in q1["bar"], f"{theme}: a typed +300 becomes the slip's price, with the estimate kept beside it ({q1['price']}; {q1['sub'][:70]}; bar {q1['bar']})")
            check(pay == "$40.00", f"{theme}: the payout follows the typed price ({pay})")
            await pg.evaluate("document.querySelector('#sgq').scrollIntoView({block: 'center'})"); await pg.click('#sgqSign'); await pg.fill('#sgq', '120'); await pg.click('#sgqGo'); await pg.wait_for_timeout(350); q2 = await pg.evaluate(READ)
            check(q2["price"] == "-120", f"{theme}: the sign button makes it a minus price ({q2['price']})")
            await pg.evaluate("document.querySelector('#sgq').scrollIntoView({block: 'center'})"); await pg.fill('#sgq', '7'); await pg.click('#sgqGo'); await pg.wait_for_timeout(250); q3 = await pg.evaluate(READ)
            check(q3["price"] == "-120" and await pg.evaluate("document.querySelector('#sgq').classList.contains('bad')"), f"{theme}: a number that is not a price is refused ({q3['price']})")
            await pg.evaluate("document.querySelector('#sgqClr').scrollIntoView({block: 'center'})"); await pg.click('#sgqClr'); await pg.wait_for_timeout(350); q4 = await pg.evaluate(READ)
            check(q4["price"] == s["price"] and "same-game estimate" in q4["sub"] and bool(q4["why"]), f"{theme}: Back to the estimate restores it ({q4['price']} vs {s['price']})")
            check(got is not None and got < mult2, f"{theme}: a quarterback with his receiver is priced under the legs multiplied ({got:.3f} < {mult2:.3f})")
            # 11/25: a typed price is kept as a data point - sent to the database only for a signed-in reader, once per slip and price
            none = await pg.evaluate("typeof window.__sgqLast")
            await pg.evaluate("window.__rpc = []; window.bsAccount = {user: {id: 'u1'}, client: {rpc: function(fn, a){ window.__rpc.push([fn, a]); return Promise.resolve({data: true}); }}}")
            await pg.evaluate("document.querySelector('#sgq').scrollIntoView({block: 'center'})"); await pg.fill('#sgq', '310'); await pg.click('#sgqGo'); await pg.wait_for_timeout(300)
            await pg.evaluate("document.querySelector('#sgq').scrollIntoView({block: 'center'})"); await pg.fill('#sgq', '310'); await pg.click('#sgqGo'); await pg.wait_for_timeout(300)
            sent = await pg.evaluate("window.__rpc"); a0 = sent[0][1] if sent else {}
            check(none == "undefined" and len(sent) == 1 and sent[0][0] == "fd_quote_add" and a0.get("p_fanduel") == 310 and a0.get("p_src") == "typed" and isinstance(a0.get("p_week"), int) and isinstance(a0.get("p_est"), int) and abs(a0["p_est"]) >= 100
                  and len(a0.get("p_legs") or []) >= 2 and all(l.get("pl") and l.get("m") and l.get("g") and isinstance(l.get("o"), int) for l in a0["p_legs"]) and "p" not in a0["p_legs"][0],
                  f"{theme}: signed out, a typed price stays on the page; signed in, it is sent once with the slip's legs, FanDuel's leg prices and our estimate ({a0.get('p_est')}, {len(a0.get('p_legs') or [])} legs)")
            await pg.evaluate("delete window.bsAccount; document.querySelector('#sgqClr').scrollIntoView({block: 'center'})"); await pg.click('#sgqClr'); await pg.wait_for_timeout(300)
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
