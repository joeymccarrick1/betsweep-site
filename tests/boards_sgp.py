"""The boards page's own slip prices same-game legs like the builder (owner 11/24: an eight-leg GB-LA slip showed +8204, the legs
multiplied; FanDuel paid +2924). template.html slipDec, fed by SLIP_DATA.sgp from build_boards.py.
  python3 tests/boards_sgp.py      (SITE or ./site, /boards/, a phone, light and dark)"""
import asyncio, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); sys.path.insert(0, HERE)
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8897
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
am = lambda d: ("+" + str(round((d - 1) * 100))) if d >= 2 else str(round(-100 / (d - 1)))
dec = lambda o: 1 + (o / 100 if o > 0 else 100 / -o)
PICK = """() => { var D = window.__BSL || {}, L = (D.legs || []).filter(function(l){ return !l.gl && l.o != null && l.bk != null && !/TD/.test(l.m) && !/^Under /.test(l.m); }), now = Date.now();
  var by = {}; L.forEach(function(l){ (by[l.g] = by[l.g] || []).push(l); });
  var gs = Object.keys(by).filter(function(g){ var ps = {}; by[g].forEach(function(l){ ps[l.pl] = 1; }); return Object.keys(ps).length >= 3; });
  function three(g){ var seen = {}, out = []; by[g].forEach(function(l){ if(out.length < 3 && !seen[l.pl] && l.o < 0 && l.o > -400){ seen[l.pl] = 1; out.push(l); } }); return out; }
  var same = null, other = null; for(var i = 0; i < gs.length; i++){ var t = three(gs[i]); if(t.length === 3){ if(!same) same = t; else if(!other){ other = t[0]; break; } } }
  var key = function(l){ return l.pl + '|' + l.m + '|' + Math.round(l.ln || 1); };
  return {week: D.week, sgp: D.sgp || null, same: same && same.map(function(l){ return {k: key(l), o: l.o, g: l.g}; }), other: other && {k: key(other), o: other.o, g: other.g}}; }"""
READ = "() => ({price: (document.getElementById('bslipPrice') || {}).textContent || '', tgt: ((document.querySelector('#btgt .row span') || {}).textContent || ''), n: document.querySelectorAll('#bslipLegs li').length})"
async def main():
    if not os.path.exists(os.path.join(ROOT, "boards", "index.html")): check(True, "(no built boards page here)"); return
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}"); await ctx.route("**/*supabase*/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
            await pg.goto(f"http://127.0.0.1:{PORT}/boards/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
            d = await pg.evaluate(PICK)
            if not d.get("same"):
                check(True, f"[{theme}] (no game on this board with three priced legs of three players - nothing to price together)"); await ctx.close(); continue
            check(isinstance(d.get("sgp"), dict) and 0 <= d["sgp"]["c"] <= 0.05 and 1.5 <= d["sgp"]["p"] <= 3.5, f"[{theme}] the page carries the measured same-game discount ({d.get('sgp')})")
            async def slip(keys):
                await pg.evaluate("(a) => { localStorage.setItem('bs_slipk_w' + a[0], JSON.stringify(a[1])); }", [d["week"], keys]); await pg.reload(wait_until="domcontentloaded"); await pg.wait_for_timeout(1700)
                return await pg.evaluate(READ)
            s = await slip([x["k"] for x in d["same"]]); mult = 1.0
            for x in d["same"]: mult *= dec(x["o"])
            m = re.search(r"≈ ([+−-]\d+)", s["price"]); shown = m.group(1).replace("−", "-") if m else None
            check(s["n"] >= 3 and "FanDuel price (about)" in s["price"] and shown is not None and "same-game estimate" in s["price"] and f"legs multiplied ({am(mult)})" in s["price"] and "its betslip has the real price" in s["price"],
                  f"[{theme}] three legs of one game: the price is marked as an estimate and the legs multiplied ({am(mult)}) is named beside it, not shown as FanDuel's price (shows {shown})")
            check(shown is not None and shown != am(mult) and "about that price" in s["price"] and s["tgt"] == "Target price (legs multiplied)", f"[{theme}] the estimate is its own number, the $10 payout says 'about', and the slider says it works in legs multiplied ({s['tgt']})")
            want_rng = bool(((d["sgp"] or {}).get("spread") or {}).get("2-4", 0) >= ((d["sgp"] or {}).get("show") or 0.2))
            check(("likely" in s["price"].split("Model fair")[0]) == want_rng, f"[{theme}] a range is printed beside the estimate only where slips this long have missed by 20% or more (three legs: {'yes' if want_rng else 'no'})")
            if d.get("other"):
                s2 = await slip([d["same"][0]["k"], d["other"]["k"]]); m2 = dec(d["same"][0]["o"]) * dec(d["other"]["o"])
                c2 = s2["price"].split("Model fair")[0]     # the FanDuel cell only: the row of other books further down has its own "about" marks
                check("(about)" not in c2 and "\u2248" not in c2 and am(m2) in c2 and "legs multiplied" in c2 and "same-game" not in c2 and s2["tgt"] in ("Target FanDuel price", ""),
                      f"[{theme}] one leg from each of two games is still the legs multiplied ({am(m2)}), with no 'about'")
            check(not errs, f"[{theme}] no script errors {errs[:2]}")
            await ctx.close()
        await b.close()
    srv.shutdown()
asyncio.run(main())
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
