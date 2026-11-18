"""11/18 (owner: "Tighten all of those you listed"): Boards, the builder, Home, Survivor, the Guide, How and the legal pages on a phone.
Nothing is removed: board cards open on "Show the game", the builder's price grids on "Game lines", the home page's lower sections
sit under tabs, reading pages fold under their section titles, Survivor's tables show eight rows until asked. Wide screens are untouched."""
import asyncio, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); PORT = 8871
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)
SCR = "Math.round(document.documentElement.scrollHeight / 844 * 10) / 10"; OVER = "document.documentElement.scrollWidth - document.documentElement.clientWidth"
VIS = "(s) => { const e = document.querySelector(s); return !!e && e.getClientRects().length > 0 && e.checkVisibility(); }"
async def page(b, path, w=390, theme="dark"):
    ctx = await b.new_context(viewport={"width": w, "height": 844}, is_mobile=w < 700, has_touch=w < 700)
    await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
    for pat in ("**/*supabase*/**", "**/site.api.espn.com/**", "**/api.sleeper.app/**"): await ctx.route(pat, lambda r: r.abort())
    pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
    await pg.goto(f"http://127.0.0.1:{PORT}{path}", wait_until="domcontentloaded"); await pg.wait_for_timeout(1400)
    return ctx, pg, errs
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("dark", "light"):
            # ---- boards ----
            ctx, pg, errs = await page(b, "/boards/", theme=theme); await pg.add_style_tag(content=".card:not(.bsgshut){content-visibility:visible!important}")
            n = await pg.evaluate("document.querySelectorAll('section.card.bsgshut').length"); g = await pg.evaluate("[...document.querySelectorAll('section.card[id]')].filter(c => c.querySelector(':scope > .bestslip')).length")
            scr = await pg.evaluate(SCR); first = await pg.evaluate("document.querySelector('section.card.bsgshut').id")
            check(g >= 4 and n == g and scr <= 6.5 and await pg.evaluate(OVER) <= 0, f"boards, {theme}: every game card opens on its header and confidence line ({n} of {g} folded, {scr} screens)")
            await pg.click(f"#{first} > .bsgtog"); await pg.wait_for_timeout(200)
            check(await pg.evaluate(VIS, f"#{first} > .bestslip") and await pg.evaluate(f"document.querySelector('#{first} > .bsgtog').getAttribute('aria-expanded')") == "true" and "Hide the game" in await pg.evaluate(f"document.querySelector('#{first} > .bsgtog').textContent"), f"boards, {theme}: \"Show the game\" opens the lines, the buttons and the best parlay")
            await pg.click(f"#{first} > .bsgtog"); check(not await pg.evaluate(VIS, f"#{first} > .bestslip") and not errs, f"boards, {theme}: and closes it again ({errs[:1]})"); await ctx.close()
            # ---- builder ----
            ctx, pg, errs = await page(b, "/build/", theme=theme)
            cards = await pg.evaluate("[...document.querySelectorAll('#games > .gcard')].map(c => [c.id, c.classList.contains('glz'), !!c.querySelector('.glgrid') && c.querySelector('.glgrid').getClientRects().length > 0])")
            scr = await pg.evaluate(SCR)
            check(len(cards) >= 2 and cards[0][1] is False and cards[0][2] and all(c[1] and not c[2] for c in cards[1:]) and scr <= 6.5 and await pg.evaluate(OVER) <= 0, f"builder, {theme}: the next game shows its prices, the other {len(cards) - 1} show one \"Game lines\" row ({scr} screens)") if len(cards) >= 2 else check(True, f"builder, {theme}: fewer than two games to come - nothing to fold")
            if len(cards) >= 2:
                await pg.click(f"#{cards[1][0]} .gll"); await pg.wait_for_timeout(250)
                check(await pg.evaluate(VIS, f"#{cards[1][0]} .glgrid") and not await pg.evaluate(VIS, f"#{cards[1][0]} .gll"), f"builder, {theme}: a tap on \"Game lines\" opens that game's prices")
                await pg.click(f"#{cards[1][0]} .glgrid .glb, #{cards[1][0]} .glgrid button"); await pg.wait_for_timeout(250)
                check(await pg.evaluate(VIS, f"#{cards[1][0]} .glgrid") and not errs, f"builder, {theme}: and it stays open when a price is tapped ({errs[:1]})")
            await ctx.close()
            # ---- home ----
            ctx, pg, errs = await page(b, "/", theme=theme)
            tabs = await pg.evaluate("[...document.querySelectorAll('#hometabs .fxtabs .tab')].map(t => t.textContent.trim())")
            if len(tabs) >= 3:
                vis = await pg.evaluate("[...document.querySelectorAll('#hometabs > [data-tab]')].filter(e => e.getClientRects().length > 0).map(e => e.id)"); scr = await pg.evaluate(SCR)
                check(len(vis) == 1 and scr <= 6 and await pg.evaluate(OVER) <= 0, f"home, {theme}: the lower sections sit under one row of tabs ({tabs}; showing {vis}; {scr} screens)")
                await pg.evaluate("document.querySelector('#hometabs').scrollIntoView()"); await pg.click("#hometabs .fxtabs .tab:nth-child(2)"); await pg.wait_for_timeout(200)
                vis2 = await pg.evaluate("[...document.querySelectorAll('#hometabs > [data-tab]')].filter(e => e.getClientRects().length > 0).map(e => e.id)")
                check(len(vis2) == 1 and vis2 != vis and not errs, f"home, {theme}: a tab shows its section and hides the last ({vis2}; {errs[:1]})")
            else: check(not errs, f"home, {theme}: fewer than three lower sections today - no tabs, no errors")
            await ctx.close()
            # ---- reading pages ----
            for path, mx, first_open in (("/guide/", 4.5, True), ("/how/", 3.5, True), ("/terms/", 3.5, False), ("/privacy/", 3.0, False), ("/responsible-gambling/", 3.5, False)):
                ctx, pg, errs = await page(b, path, theme=theme)
                st = await pg.evaluate("[...document.querySelectorAll('h2.bsdfh')].map(h => h.getAttribute('aria-expanded'))"); scr = await pg.evaluate(SCR)
                check(len(st) >= 4 and st.count("true") == (1 if first_open else 0) and scr <= mx and await pg.evaluate(OVER) <= 0, f"{path}, {theme}: {len(st)} sections fold under their titles ({scr} screens)")
                await pg.click("h2.bsdfh:nth-of-type(1), h2.bsdfh >> nth=-1"); await pg.wait_for_timeout(150)
                last = await pg.evaluate("(() => { const h = [...document.querySelectorAll('h2.bsdfh')].pop(); return [h.getAttribute('aria-expanded'), h.nextElementSibling.hidden]; })()")
                await pg.click(".bsdfall"); await pg.wait_for_timeout(150); allopen = await pg.evaluate("[...document.querySelectorAll('.bsdfb')].every(b => !b.hidden)")
                check(allopen and await pg.evaluate("document.querySelector('.bsdfall').textContent") == "Close all sections" and not errs, f"{path}, {theme}: \"Open all sections\" opens every one ({errs[:1]})"); await ctx.close()
            # ---- survivor ----
            ctx, pg, errs = await page(b, "/survivor/", theme=theme)
            cap = await pg.evaluate("[...document.querySelectorAll('#svout .tw.svcap')].map(t => [t.querySelectorAll('tbody tr').length, [...t.querySelectorAll('tbody tr')].filter(r => r.getClientRects().length > 0).length])")
            if cap:
                check(all(v == 8 and n > 10 for n, v in cap) and await pg.evaluate(SCR) <= 4.2 and await pg.evaluate(OVER) <= 0, f"survivor, {theme}: long tables show eight rows until asked ({cap})")
                await pg.click("#svout .svmore"); await pg.wait_for_timeout(150); vis = await pg.evaluate("(() => { const t = document.querySelector('#svout .tw'); return [...t.querySelectorAll('tbody tr')].filter(r => r.getClientRects().length > 0).length; })()")
                check(vis == cap[0][0] and not errs, f"survivor, {theme}: \"Show all\" shows the rest ({vis} rows)")
            else: check(not errs, f"survivor, {theme}: no table over ten rows this week")
            check(await pg.evaluate("!!document.querySelector('details.svhow') && !document.querySelector('details.svhow').open"), f"survivor, {theme}: how the win chances are made sits under one line"); await ctx.close()
        # ---- a link to a section arrives with it open; wide screens are left alone ----
        ctx, pg, errs = await page(b, "/guide/"); ids = await pg.evaluate("[...document.querySelectorAll('.gd > section[id]')].map(s => s.id)"); await ctx.close()
        ctx, pg, errs = await page(b, f"/guide/#{ids[-1]}"); check(await pg.evaluate(f"document.querySelector('#{ids[-1]} > h2').getAttribute('aria-expanded')") == "true", f"guide: a link to a section (#{ids[-1]}) arrives with it open"); await ctx.close()
        ctx, pg, errs = await page(b, "/boards/"); gid = await pg.evaluate("document.querySelectorAll('section.card.bsgshut')[2].id"); await ctx.close()
        ctx, pg, errs = await page(b, f"/boards/#{gid}"); check(not await pg.evaluate(f"document.querySelector('#{gid}').classList.contains('bsgshut')"), f"boards: a link to a game (#{gid}) arrives with it open"); await ctx.close()
        for path, sel in (("/boards/", ".bsgshut, .bsgtog"), ("/guide/", "h2.bsdfh"), ("/", "#hometabs"), ("/survivor/", ".svcap")):
            ctx, pg, errs = await page(b, path, w=1200); check(await pg.evaluate(f"document.querySelectorAll('{sel}').length") == 0 and not errs, f"{path} on a wide screen: nothing is folded"); await ctx.close()
        ctx, pg, errs = await page(b, "/build/", w=1200); check(not await pg.evaluate(VIS, ".gll") and await pg.evaluate("[...document.querySelectorAll('#games .glgrid')].every(g => g.getClientRects().length > 0)"), "builder on a wide screen: every game shows its prices"); await ctx.close()
        await b.close()
    srv.shutdown(); print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
asyncio.run(main())
