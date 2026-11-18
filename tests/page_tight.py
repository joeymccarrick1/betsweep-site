"""11/18 (owner: "Tighten all of those you listed"): Boards, the builder, Home, Survivor, the Guide, How and the legal pages on a phone.
Nothing is removed: the home page's lower sections sit under tabs, reading pages fold under their section titles, Survivor's tables
show eight rows until asked. Boards and the builder were re-done the same afternoon (owner 3:52 PM: "I don't really like how you have
packaged and condensed the parlay builder and the matchup boards ... make it make a little more sense"): a board card is the whole
scorecard again with only its fine print folded, and every builder game card carries the same two buttons. Wide screens are untouched."""
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
            ctx, pg, errs = await page(b, "/boards/", theme=theme); await pg.add_style_tag(content=".card{content-visibility:visible!important}"); await pg.wait_for_timeout(200)
            d = await pg.evaluate("""() => { const vis = e => !!e && e.getClientRects().length > 0, cs = [...document.querySelectorAll('section.card[id]')].filter(c => c.querySelector(':scope > .bestslip'));
              return {n: cs.length, first: cs.length ? cs[0].id : '', tidy: cs.filter(c => c.classList.contains('bstidy')).length, stub: document.querySelectorAll('.bsgtog, .bsgshut').length,
                full: cs.filter(c => vis(c.querySelector(':scope > .ginfo .gk')) && vis(c.querySelector(':scope > .vbtns .vbtn')) && vis(c.querySelector(':scope > .conf')) && (vis(c.querySelector(':scope > .bestslip .bpl')) || c.querySelector(':scope > .bestslip.none'))).length,
                work: cs.filter(c => { const w = c.querySelector(':scope > .bestslip > .bpwork'); return !w || (!vis(w) && vis(c.querySelector(':scope > .bestslip > .bpmore'))); }).length,
                lines: cs.map(c => Math.round(c.querySelector(':scope > .ginfo').getBoundingClientRect().height / 1.1)),
                add: cs.filter(c => { const f = c.querySelector(':scope > .bestslip > .fdgo'), o = c.querySelector(':scope > .bestslip > .bpodds'); return !vis(f) || !o || Math.abs(f.getBoundingClientRect().top - o.getBoundingClientRect().top) < 26; }).length,
                dots: cs.filter(c => { const k = [...c.querySelector(':scope > .ginfo').children].filter(vis); return k.length && k[0].tagName === 'SPAN' && k[k.length - 1].tagName === 'SPAN' && !k.some((e, i) => e.tagName === 'I' && k[i + 1] && k[i + 1].tagName === 'I'); }).length,
                card: Math.round(cs.reduce((a, c) => a + c.getBoundingClientRect().height, 0) / Math.max(cs.length, 1))}; }""")
            scr = await pg.evaluate(SCR); n = d["n"]
            check(n >= 4 and d["stub"] == 0 and d["tidy"] == n and d["full"] == n, f"boards, {theme}: no \"Show the game\" row - every card shows its kickoff, Game Script / Projections, its confidence line and its best parlay's legs ({d['full']} of {n})")
            check(d["work"] == n and d["add"] == n, f"boards, {theme}: on every card the leg-by-leg reasoning waits under \"Show the work\" and \"+ Add\" sits beside the parlay's price")
            check(d["dots"] == n and max(d["lines"]) <= 60 and sum(1 for h in d["lines"] if h <= 32) >= n // 2, f"boards, {theme}: the kickoff line is one line on most cards, two at most, with no stray dots (heights {sorted(set(d['lines']))})")
            check(d["card"] <= 600 and await pg.evaluate(OVER) <= 0, f"boards, {theme}: a card averages {d['card']}px tall (it was about 710 with everything open); the page is {scr} screens for {n} games")
            first = d["first"]; await pg.click(f"#{first} > .bestslip > .bpmore"); await pg.wait_for_timeout(200)
            check(await pg.evaluate(VIS, f"#{first} > .bestslip > .bpwork") and await pg.evaluate(f"document.querySelector('#{first} > .bestslip > .bpmore').getAttribute('aria-expanded')") == "true" and "Hide the work" in await pg.evaluate(f"document.querySelector('#{first} > .bestslip > .bpmore').textContent")
                  and not await pg.evaluate(f"document.querySelector('#{first}').classList.contains('expanded')"), f"boards, {theme}: \"Show the work\" opens the reasoning in place (the board itself stays shut)")
            await pg.click(f"#{first} > .bestslip > .bpmore"); await pg.wait_for_timeout(150); shut = not await pg.evaluate(VIS, f"#{first} > .bestslip > .bpwork")
            hid = await pg.evaluate(f"[...document.querySelectorAll('#{first} > .ginfo .bsx')].length"); await pg.click(f"#{first} > .vbtns .vbtn[data-view=script]"); await pg.wait_for_timeout(300)
            check(shut and await pg.evaluate(f"document.querySelector('#{first}').classList.contains('expanded')") and (hid == 0 or await pg.evaluate(VIS, f"#{first} > .ginfo .bsx")) and not errs, f"boards, {theme}: it closes again, and Game Script opens the full board with the stadium and the rest back on the kickoff line ({errs[:1]})")
            await ctx.close()
            # ---- builder ----
            ctx, pg, errs = await page(b, "/build/", theme=theme)
            CARDS = """() => [...document.querySelectorAll('#games > .gcard')].map(c => { const vis = e => !!e && e.getClientRects().length > 0, bs = [...c.querySelectorAll(':scope > .gsw .gswb')];
              return {id: c.id, btns: bs.map(x => x.textContent.replace(/[▾▴]/g, '').trim()), on: bs.map(x => x.classList.contains('on')), ax: bs.map(x => x.getAttribute('aria-expanded')), h: bs.map(x => Math.round(x.getBoundingClientRect().height / 1.1)),
                      grid: vis(c.querySelector('.glgrid')), body: !!c.querySelector('.gbody'), pill: vis(c.querySelector('.ghd .opn')), old: !!c.querySelector('.gll'), props: !/not posted|locked/i.test((c.querySelector('.ghd .gsum') || {}).textContent || ''), lines: !!c.querySelector('.glgrid'),
                      order: (() => { const g = c.querySelector('.glgrid'), y = c.querySelector('.gbody'); return g && y && vis(g) ? g.getBoundingClientRect().top < y.getBoundingClientRect().top : null; })()}; })"""
            cards = await pg.evaluate(CARDS); scr = await pg.evaluate(SCR)
            if len(cards) >= 2:
                both = [c for c in cards if c["btns"] == ["Game lines", "Player legs"]]; want = lambda c: (["Game lines"] if c["lines"] else []) + (["Player legs"] if c["props"] else [])
                check(all(c["btns"] == want(c) and not any(c["on"]) and not c["grid"] and not c["body"] and not c["pill"] and not c["old"] and min(c["h"] or [44]) >= 44 for c in cards) and len(both) >= 2 and cards[0]["btns"] == want(cards[0]),
                      f"builder, {theme}: every game card - the first like the rest - carries the same buttons, Game lines and Player legs, both shut ({len(both)} of {len(cards)} with both; the others have no player props posted yet; {scr} screens)")
                check(scr <= 6.0 and await pg.evaluate(OVER) <= 0, f"builder, {theme}: the page is {scr} phone screens (7.7 before the first pass)")
                gid = both[1]["id"]; ix = [c["id"] for c in cards].index(gid)
                await pg.click(f"#{gid} .gswb[data-gl]"); await pg.wait_for_timeout(250); c = (await pg.evaluate(CARDS))[ix]
                check(c["grid"] and c["on"] == [True, False] and c["ax"][0] == "true" and not c["body"], f"builder, {theme}: Game lines opens that game's prices and nothing else")
                await pg.click(f"#{gid} .glgrid .glb:not(.none)"); await pg.wait_for_timeout(250); c = (await pg.evaluate(CARDS))[ix]
                check(c["grid"] and await pg.evaluate(f"document.querySelectorAll('#{gid} .glgrid .glb.in').length") == 1 and not errs, f"builder, {theme}: a tapped price goes on the slip and the prices stay open ({errs[:1]})")
                await pg.click(f"#{gid} .gswb[data-gp]"); await pg.wait_for_timeout(350); c = (await pg.evaluate(CARDS))[ix]
                check(c["body"] and c["grid"] and c["on"] == [True, True] and c["order"] is True, f"builder, {theme}: Player legs opens the legs under the prices, and both buttons show as open")
                await pg.click(f"#{gid} .gswb[data-gl]"); await pg.wait_for_timeout(250); c = (await pg.evaluate(CARDS))[ix]
                check(not c["grid"] and c["body"] and c["on"] == [False, True], f"builder, {theme}: Game lines closes the prices and leaves the legs open")
                await pg.click(f"#{gid} .ghd"); await pg.wait_for_timeout(350); c = (await pg.evaluate(CARDS))[ix]
                check(not c["body"] and c["on"] == [False, False] and not errs, f"builder, {theme}: the header still opens and closes the player legs ({errs[:1]})")
            else: check(True, f"builder, {theme}: fewer than two games to come - nothing to compare")
            await ctx.close()
            # ---- home ----
            ctx, pg, errs = await page(b, "/", theme=theme)
            tabs = await pg.evaluate("[...document.querySelectorAll('#hometabs .fxtabs .tab')].map(t => t.textContent.trim())")
            if len(tabs) >= 3:
                vis = await pg.evaluate("[...document.querySelectorAll('#hometabs > [data-tab]')].filter(e => e.getClientRects().length > 0).map(e => e.id)"); scr = await pg.evaluate(SCR)
                check(len(vis) == 1 and scr <= 6.5 and await pg.evaluate(OVER) <= 0, f"home, {theme}: the lower sections sit under one row of tabs ({tabs}; showing {vis}; {scr} screens)")
                await pg.evaluate("document.querySelector('#hometabs').scrollIntoView()"); await pg.click("#hometabs .fxtabs .tab:nth-child(2)"); await pg.wait_for_timeout(200)
                vis2 = await pg.evaluate("[...document.querySelectorAll('#hometabs > [data-tab]')].filter(e => e.getClientRects().length > 0).map(e => e.id)")
                check(len(vis2) == 1 and vis2 != vis and not errs, f"home, {theme}: a tab shows its section and hides the last ({vis2}; {errs[:1]})")
            else: check(not errs, f"home, {theme}: fewer than three lower sections today - no tabs, no errors")
            # "Lines to check" (stale_lines.py): a heavy injury report shows two players and two lines each until asked
            ST = "(() => { const w = document.querySelector('#bsstale'); if(!w || w.hidden) return null; const vis = e => e.getClientRects().length > 0, li = [...w.querySelectorAll('li[data-ko]')], b = w.querySelector('.stmore'); return {all: li.filter(e => !e.hidden).length, shown: li.filter(vis).length, who: [...w.querySelectorAll('.stit')].filter(vis).length, btn: b && vis(b) ? b.textContent : '', h: Math.round(w.getBoundingClientRect().height / 1.1)}; })()"
            st = await pg.evaluate(ST)
            if st and st["all"] > 6:
                check(st["shown"] <= 4 and st["who"] <= 2 and f"Show all {st['all']} lines" in st["btn"], f"home, {theme}: Lines to check opens on {st['shown']} of {st['all']} lines ({st['who']} players, {st['h']}px) under \"{st['btn']}\"")
                await pg.click("#bsstale .stmore"); await pg.wait_for_timeout(150); st2 = await pg.evaluate(ST)
                check(st2["shown"] == st["all"] and st2["btn"] == "Show fewer" and not errs, f"home, {theme}: the button shows all {st2['shown']} lines and turns into \"Show fewer\"")
            elif st: check(st["shown"] == st["all"] and not st["btn"], f"home, {theme}: Lines to check is short today ({st['all']} lines) - all shown, no button")
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
        ctx, pg, errs = await page(b, "/boards/"); gid = await pg.evaluate("[...document.querySelectorAll('section.card.bstidy')][2].id"); await ctx.close()
        ctx, pg, errs = await page(b, f"/boards/#{gid}"); check(await pg.evaluate(f"document.querySelector('#{gid}').classList.contains('expanded')") and await pg.evaluate(f"[...document.querySelectorAll('section.card.expanded')].length") == 1, f"boards: a link to a game (#{gid}) arrives with that board open and the others as scorecards"); await ctx.close()
        wks = sorted([d for d in os.listdir(os.path.join(ROOT, "receipts")) if re.fullmatch(r"week\d+", d)], key=lambda d: int(d[4:])) if os.path.isdir(os.path.join(ROOT, "receipts")) else []
        if wks:   # the first pass had folded the weekly receipt's game cards too (any card with a kickoff line); they are left as they were
            ctx, pg, errs = await page(b, f"/receipts/{wks[-1]}/"); n = await pg.evaluate("document.querySelectorAll('section.card[id] > .ginfo').length")
            check(n >= 4 and await pg.evaluate("document.querySelectorAll('.bstidy, .bsgtog, .bsgshut, .bpmore, .ginfo .bsx').length") == 0 and not errs, f"/receipts/{wks[-1]}/ on a phone: its {n} game cards are not folded or trimmed"); await ctx.close()
        for path, sel in (("/boards/", ".bstidy, .bpmore, .bsgtog"), ("/guide/", "h2.bsdfh"), ("/", "#hometabs"), ("/survivor/", ".svcap")):
            ctx, pg, errs = await page(b, path, w=1200); check(await pg.evaluate(f"document.querySelectorAll('{sel}').length") == 0 and not errs, f"{path} on a wide screen: nothing is folded"); await ctx.close()
        ctx, pg, errs = await page(b, "/build/", w=1200)
        check(not await pg.evaluate(VIS, ".gsw") and await pg.evaluate("[...document.querySelectorAll('#games > .gcard:not(.done) .glgrid')].every(g => g.getClientRects().length > 0)") and await pg.evaluate(VIS, "#games .ghd .opn"), "builder on a wide screen: no button row - every game shows its prices and the header's pill opens the legs"); await ctx.close()
        await b.close()
    srv.shutdown(); print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
asyncio.run(main())
