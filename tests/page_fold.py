"""The long pages are short now, and nothing went missing (owner 11/17: "It's a lot of scrolling to find what you're looking for";
9:23 PM: "Did you finish updating and optimizing every page?").

Phone lengths before, on the live copy that night (390x844): First TD 17.8 screens, Line shop 14.0, Usage 12.8, DFS 10.3,
Model's Best 9.2, News 9.0, Who benefits 7.6. Each page keeps every row it had; what changed is how much of it opens at once:

  Usage          the first 12 of a list, the rest behind "Show all N"; the position and Rising / Falling switches re-count it
  Who benefits   one folded block per injured player, the header says who got the work
  Line shop      three-line rows with the better price on the button, the first 15, a book switch
  News desk      one group per tab, notes two lines until tapped, the team filter re-counts the tabs
  Model's Best   one tier / section per tab; /best/#parlay opens on the parlays
  DFS            Players / Lineup / How it works as tabs on one column; side by side on a wide screen as before
  First TD       each game folded behind a header naming its top three; a chip or a name opens the game
  Players        the first 30 (props this week first), search and position re-count, one button for the rest  (was 33.9 screens)
  Teams          Standings / League table as tabs  (6.9)
  Teasers        one teaser size per tab  (6.9)
  Season         on a phone its report cards open on their titles; the fold is in the shared script because a reprice does not
                 rebuild that page  (10.4 with every card laid out)
  A player       opens on this week's props; Last N games, the model's notes and the stats are tabs  (6.7). A player with no lines
                 this week opens on his last games instead of an empty Props tab. Always the same opening tab: a tap on a name
                 anywhere should land on his props, whatever was open on the last player.
  A team         Stats / Games / Leaders tabs  (5.8)
  A game preview on one column: the game, then each offense as a tab; two columns on a wide screen as before  (6.1)
  A receipt      on a phone its scorecard shows one group at a time (Lines / Posted / Calls / Projections / Games) with two tiles to a
                 row; the share picture still draws the whole card. Shared script, like Season  (15.0 with every card laid out)

  python3 tests/page_fold.py [shots_dir]      (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, os, re, sys, threading
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8871; ok = [0, 0]; CLONE = os.environ.get("CLONE", "/home/claude/betsweep-site")
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
def skip(what): print("SKIP " + what)
def has(path): return os.path.isfile(os.path.join(ROOT, path.strip("/"), "index.html"))
# longest a page may open at on a phone, in screens. Loose on purpose: a busy week adds rows, and the caps are what hold the length.
# 11/27 late: /best/ 4.5 -> 5.5. Every leg card now carries its reasons (why.py) and the opponents under its bars, about 70px a card;
# eight cards on the first tab opened at 5.2 screens; since 11/28 a list opens on its first five cards (owner: "keep trimming"), back under 4.5. /news/ is back under its 5.0: a group opens with 24 notes and a Show all button.
LIMIT = {"/usage/": 5.0, "/benefits/": 4.5, "/shop/": 4.5, "/news/": 5.0, "/best/": 4.5, "/dfs/": 5.0, "/firsttd/": 6.5}
VIS = "var qa = function(s, r){ return Array.from((r || document).querySelectorAll(s)); }, vis = function(e){ if(e.checkVisibility && !e.checkVisibility()) return false; var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };"   # checkVisibility: a closed <details> keeps its content's box
LEN = "() => ({scr: document.documentElement.scrollHeight / innerHeight, over: document.documentElement.scrollWidth - document.documentElement.clientWidth})"

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
        def translate_path(self, path):
            # a page a reprice keeps (Season, the receipts) links the published copy's own /s/tpl-<hash>.css, which a local ./site does not
            # have; the publish step merges s/, so the published site does. Serve such a file from the published copy when it is here.
            p = super().translate_path(path)
            if not os.path.exists(p) and path.startswith("/s/") and os.path.isfile(os.path.join(CLONE, path.split("?")[0].lstrip("/"))): return os.path.join(CLONE, path.split("?")[0].lstrip("/"))
            return p
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def page(path, theme="dark", w=390, t=None):
            ctx = await b.new_context(viewport={"width": w, "height": 844}, device_scale_factor=1, is_mobile=w < 700, has_touch=w < 700, service_workers="block")
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            if t:   # a fixed clock, so a week that is over still shows its lists
                await ctx.add_init_script("(function(){var T=" + str(int(t)) + ",R=Date.now,S=R();Date.now=function(){return T+(R()-S)};var D0=Date;function ND(){if(arguments.length===0)return new D0(D0.now());return new (Function.prototype.bind.apply(D0,[null].concat([].slice.call(arguments))))()}ND.now=D0.now;ND.parse=D0.parse;ND.UTC=D0.UTC;ND.prototype=D0.prototype;window.Date=ND;})();")
            for pat in ("**/*espn.com/**", "**/*supabase*/**", "**/raw.githubusercontent.com/**", "**/cdn.jsdelivr.net/**"): await ctx.route(pat, lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}{path}", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
            return pg, ctx, errs
        async def shot(pg, name):
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/{name}.png")
        # the week's first kickoff, read from the built First TD page: pages are opened a day before it so nothing has "kicked off"
        kos = sorted({int(k) for k in re.findall(r'<section class="ftd" id="ftd-[A-Z-]+" data-ko="(\d+)"', open(os.path.join(ROOT, "firsttd", "index.html")).read())}) if has("/firsttd/") else []
        T0 = (kos[0] - 26 * 3600e3) if kos else None

        # ---------- every page: length, no sideways scroll, no errors, both themes ----------
        for path, lim in LIMIT.items():
            if not has(path): skip(f"{path} is not in this build"); continue
            for theme in ("dark", "light"):
                pg, ctx, errs = await page(path, theme, t=T0); d = await pg.evaluate(LEN); await shot(pg, f"fold-{path.strip('/')}-{theme}"); await ctx.close()
                check(d["scr"] <= lim and d["over"] <= 1 and not errs, f"[{theme}] {path} opens at {d['scr']:.1f} phone screens (limit {lim}), no sideways scroll, no script errors {errs[:1] or ''}")

        # ---------- Usage ----------
        if has("/usage/"):
            pg, ctx, errs = await page("/usage/")
            R = "() => { " + VIS + " var rows = qa('.uw tbody tr'), k = document.querySelector('#uctl [data-k].on').getAttribute('data-k'), p = document.querySelector('#uctl [data-p].on').getAttribute('data-p'); var mine = rows.filter(function(r){ return r.getAttribute('data-kind') === k && (p === 'ALL' || r.getAttribute('data-pos') === p); }); return {all: rows.length, mine: mine.length, shown: rows.filter(vis).length, wrong: rows.filter(vis).filter(function(r){ return mine.indexOf(r) < 0; }).length, firstShown: mine.slice(0, 12).every(vis), more: vis(document.getElementById('umore')), btn: document.getElementById('umoreb').textContent, sub: document.querySelector('#uh small').textContent}; }"
            u = await pg.evaluate(R)
            check(u["shown"] == min(12, u["mine"]) and u["wrong"] == 0 and u["firstShown"] and u["more"] == (u["mine"] > 12), f"Usage opens on the 12 biggest risers of {u['mine']} ({u['shown']} rows on screen, {u['sub']!r})")
            if u["mine"] > 12:
                check(u["btn"] == f"Show all {u['mine']}", f"the button says how many there are ({u['btn']!r})")
                await pg.click("#umoreb"); v = await pg.evaluate(R); check(v["shown"] == v["mine"] and not v["more"], f"Show all opens every one of the {v['mine']}")
            await pg.click('#uctl [data-k="down"]'); f = await pg.evaluate(R)
            check(f["shown"] == min(12, f["mine"]) and f["wrong"] == 0 and "drops" in f["sub"], f"Falling starts short again: {f['shown']} of {f['mine']} ({f['sub']!r})")
            await pg.click('#uctl [data-p="TE"]'); g = await pg.evaluate(R)
            check(g["shown"] == min(12, g["mine"]) and g["wrong"] == 0 and g["more"] == (g["mine"] > 12), f"a position filter counts its own list: {g['shown']} of {g['mine']} falling tight ends, button {'shown' if g['more'] else 'not needed'}")
            check(not errs, f"Usage: no script errors {errs[:1] or ''}"); await ctx.close()

        # ---------- Who benefits ----------
        if has("/benefits/"):
            pg, ctx, errs = await page("/benefits/")
            B = "() => { " + VIS + " var ds = qa('.uw details.bfold'); return {n: ds.length, open: ds.filter(function(d){ return d.open; }).length, gain: ds.map(function(d){ return (d.querySelector('.bgain') || {textContent: ''}).textContent; }), tables: qa('.uw details.bfold table').filter(vis).length, links: qa('.uw details.bfold > summary a').length}; }"
            s = await pg.evaluate(B)
            if not s["n"]: skip("nobody newly Out or Doubtful this build, so Who benefits has no folded block")
            else:
                check(s["open"] == 0 and s["tables"] == 0, f"Who benefits: {s['n']} players, each folded")
                check(all(len(x) > 20 for x in s["gain"]) and s["links"] == 0, f"every header says who got the work, and holds no link that would steal the tap ({s['gain'][0][:70]!r})")
                await pg.click(".uw details.bfold > summary"); o = await pg.evaluate(B)
                check(o["open"] == 1 and o["tables"] == 1, "a tap opens that player's table")
                check(await pg.evaluate("() => !!document.querySelector('.uw details.bfold[open] .bwhy a[href^=\"/player/\"]')"), "his name inside links to his page")
            check(not errs, f"Who benefits: no script errors {errs[:1] or ''}"); await ctx.close()

        # ---------- Line shop ----------
        if has("/shop/"):
            pg, ctx, errs = await page("/shop/", t=T0)
            S = "() => { " + VIS + " var rows = qa('.shl li'), on = document.querySelector('#shbk .tab.on'), bk = on ? on.getAttribute('data-b') : ''; var mine = rows.filter(function(r){ return !bk || r.getAttribute('data-b') === bk; }); return {all: rows.length, mine: mine.length, shown: rows.filter(vis).length, wrong: rows.filter(vis).filter(function(r){ return mine.indexOf(r) < 0; }).length, more: !!document.getElementById('shmorep') && vis(document.getElementById('shmorep')), btn: (document.getElementById('shmore') || {textContent: ''}).textContent, books: qa('#shbk .tab').map(function(b){ return b.getAttribute('data-b') + ':' + b.textContent.trim(); }), h: Math.max.apply(null, rows.filter(vis).map(function(r){ return r.getBoundingClientRect().height; }).concat([0])), btnw: Math.max.apply(null, qa('.shl li a.bsbtn').filter(vis).map(function(a){ return a.getBoundingClientRect().width; }).concat([0])), price: qa('.shl li a.bsbtn').filter(vis).every(function(a){ return /[+\\u2212]\\d+/.test(a.textContent); })}; }"
            s = await pg.evaluate(S)
            if not s["all"]: skip("Line shop lists nothing this build")
            else:
                check(s["shown"] == min(15, s["mine"]) and s["more"] == (s["mine"] > 15), f"Line shop opens on the 15 widest gaps of {s['mine']} ({s['shown']} rows)")
                check(s["h"] <= 130 and s["btnw"] <= 150 and s["price"], f"a row is a few lines, not a card: tallest {s['h']:.0f}px, and its button carries the better price (widest {s['btnw']:.0f}px)")
                if s["mine"] > 15: await pg.click("#shmore"); v = await pg.evaluate(S); check(v["shown"] == v["mine"] and not v["more"], f"Show all opens all {v['mine']}")
                bk = [x for x in s["books"] if not x.startswith(":")]
                if len(bk) < 2: skip("only one other book has a better price this build, so there is no book switch")
                else:
                    code = bk[-1].split(":")[0]; await pg.click(f'#shbk [data-b="{code}"]'); k = await pg.evaluate(S)
                    n = int(re.search(r"(\d+)\s*$", bk[-1]).group(1))
                    check(k["wrong"] == 0 and k["mine"] == n and k["shown"] == min(15, n), f"the book switch keeps one book's rows: {k['shown']} shown of {n} ({bk[-1]})")
            check(not errs, f"Line shop: no script errors {errs[:1] or ''}"); await shot(pg, "fold-shop-book"); await ctx.close()

        # ---------- News desk ----------
        if has("/news/"):
            pg, ctx, errs = await page("/news/")
            N = "() => { " + VIS + " var tabs = qa('#news .fxtabs .tab'), grps = qa('#news .nwgrp'); return {tabs: tabs.map(function(b){ return b.textContent.trim(); }), on: (document.querySelector('#news .fxtabs .tab.on') || {dataset: {}}).dataset.t, grps: grps.map(function(g){ return {id: g.getAttribute('data-tab'), vis: vis(g), n: qa('li', g).length, shown: qa('li', g).filter(vis).length}; }), total: qa('#news .tdnewsl li').length, clamp: qa('#news .nwgrp li p').filter(vis).map(function(p){ return p.getBoundingClientRect().height; }), none: vis(document.getElementById('nwnone'))}; }"
            s = await pg.evaluate(N)
            if not s["tabs"]: skip("the News desk has one group this build, so it has no tabs")
            else:
                g0 = s["grps"][0]
                check(len(s["tabs"]) == len(s["grps"]) and [g["vis"] for g in s["grps"]] == [True] + [False] * (len(s["grps"]) - 1), f"News: {len(s['tabs'])} tabs, the first group on screen ({s['tabs']})")
                check(all(re.search(r"(\d+)$", t) and int(re.search(r"(\d+)$", t).group(1)) == g["n"] for t, g in zip(s["tabs"], s["grps"])) and sum(g["n"] for g in s["grps"]) == s["total"], f"each tab counts its notes and every note is under a tab ({s['total']} notes)")
                check(s["clamp"] and max(s["clamp"]) <= 52, f"a note is two lines until it is tapped (tallest {max(s['clamp']):.0f}px)")
                long = await pg.evaluate("() => { var ls = [...document.querySelectorAll('#news .nwgrp:not(.fxoff) li')].filter(function(li){ var p = li.querySelector('p'); return p && p.scrollHeight > p.clientHeight + 4; }); if(!ls.length) return null; var p = ls[0].querySelector('p'), h0 = p.getBoundingClientRect().height; ls[0].click(); return [h0, p.getBoundingClientRect().height, ls[0].getAttribute('aria-expanded')]; }")
                if long: check(long[1] > long[0] + 10 and long[2] == "true", f"a tap opens the whole note ({long[0]:.0f}px -> {long[1]:.0f}px)")
                last = s["grps"][-1]["id"]; await pg.click(f'#news .fxtabs [data-t="{last}"]'); z = await pg.evaluate(N)
                check(z["on"] == last and [g["vis"] for g in z["grps"]] == [False] * (len(z["grps"]) - 1) + [True], f"a tab shows its group and hides the others ({z['tabs'][-1]})")
                # a team with notes in some group but not the one on screen: the filter moves there
                pick = await pg.evaluate("() => { var grps = [...document.querySelectorAll('#news .nwgrp')], cur = document.querySelector('#news .fxtabs .tab.on').dataset.t; var by = {}; grps.forEach(function(g){ [...g.querySelectorAll('li')].forEach(function(li){ var t = li.getAttribute('data-team'); (by[t] = by[t] || {})[g.getAttribute('data-tab')] = ((by[t] || {})[g.getAttribute('data-tab')] || 0) + 1; }); }); var t = Object.keys(by).filter(function(k){ return k && !by[k][cur]; })[0]; return t ? {team: t, by: by[t]} : null; }")
                if not pick: skip("every team has a note in the last group, so the filter's jump has nothing to do")
                else:
                    await pg.click(f'#nwf [data-t="{pick["team"]}"]'); f = await pg.evaluate(N)
                    want = next(g["id"] for g in f["grps"] if pick["by"].get(g["id"]))
                    shown = sum(g["shown"] for g in f["grps"]); cnt = {t: 0 for t in pick["by"]}
                    check(f["on"] == want and shown == pick["by"][want] and not f["none"], f"picking {pick['team']} (no note in the group on screen) moves to the first group that has one ({want}, {shown} note{'s' if shown != 1 else ''})")
                    tabn = {g["id"]: (int(m.group(1)) if (m := re.search(r"(\d+)$", t)) else 0) for t, g in zip(f["tabs"], f["grps"])}
                    check(all(tabn[g["id"]] == pick["by"].get(g["id"], 0) for g in f["grps"]), f"the tabs re-count for that team ({f['tabs']})")
                    await pg.click('#nwf [data-t=""]'); a = await pg.evaluate(N); check([re.search(r"(\d+)$", t).group(1) for t in a["tabs"]] == [str(g["n"]) for g in a["grps"]], "All teams puts the counts back")
            check(not errs, f"News: no script errors {errs[:1] or ''}"); await ctx.close()

        # ---------- Model's Best ----------
        if has("/best/"):
            # 11/20: a tab's count is the cards still open to bet; a card whose game has kicked off stays on the page dimmed (.started) and is not counted
            M = "() => { " + VIS + " var tabs = qa('.wk .fxtabs .tab'); var on = document.querySelector('.wk .fxtabs .tab.on'); return {tabs: tabs.map(function(b){ return b.dataset.t + ':' + b.textContent.trim(); }), on: on ? on.dataset.t : null, cards: qa('article.play, .parlay, .pmini').filter(function(c){ return !c.classList.contains('started'); }).length, shown: qa('article.play, .parlay, .pmini').filter(function(c){ return !c.classList.contains('started'); }).filter(vis).length, folded: qa('article.play.bcapx').filter(function(c){ var sec = c.closest('[data-tab]'); return !c.classList.contains('started') && sec && vis(sec); }).length, more: qa('.tdnewsmore.bmore').filter(vis).map(function(b){ return b.textContent.trim(); }), secs: qa('.wk [data-tab]').filter(vis).map(function(e){ return e.getAttribute('data-tab'); }), best: vis(document.getElementById('best') || document.body), top: tabs.length ? Math.round(document.querySelector('.wk .fxtabs').getBoundingClientRect().top) : null, nav: Math.round(document.querySelector('.sitenav').getBoundingClientRect().bottom), onIn: on ? (on.getBoundingClientRect().left >= 0 && on.getBoundingClientRect().right <= innerWidth + 1) : null}; }"
            pg, ctx, errs = await page("/best/", t=T0); s = await pg.evaluate(M)
            if not s["tabs"]: skip("Model's Best has one section this build, so it has no tabs")
            else:
                ids = [t.split(":")[0] for t in s["tabs"]]; cnt = {t.split(":")[0]: (int(m.group(1)) if (m := re.search(r"(\d+)$", t)) else 0) for t in s["tabs"]}
                # 11/28 (owner: "keep trimming"): a list of more than six leg cards opens on its first five, the rest behind one "Show all N" button
                c0 = cnt[ids[0]]
                check(s["on"] == ids[0] and set(s["secs"]) == {ids[0]} and s["shown"] + s["folded"] == c0 and ((s["folded"] == 0 and not s["more"]) or (s["shown"] == 5 and s["more"] == [f"Show all {c0}"])),
                      f"Model's Best opens on its first tab with that tab's cards and nothing else: {s['shown']} showing, {s['folded']} behind {s['more'] or 'no button'} ({[t.split(':')[1] for t in s['tabs']]})")
                if s["folded"]:
                    await pg.click(".tdnewsmore.bmore"); await pg.wait_for_timeout(200); s1 = await pg.evaluate(M)
                    check(s1["shown"] == c0 and s1["folded"] == 0 and not s1["more"], f"the button shows the rest: {s1['shown']} of {c0} cards, and it steps aside ({s1['more']})")
                check(sum(cnt.values()) == s["cards"], f"the tab counts add up to every card on the page ({s['cards']})")
                seen = 0
                for i in ids:
                    await pg.click(f'.wk .fxtabs [data-t="{i}"]'); await pg.wait_for_timeout(120); z = await pg.evaluate(M); seen += z["shown"] + z["folded"]
                    if z["on"] != i or set(z["secs"]) != {i} or z["shown"] + z["folded"] != cnt[i] or not z["onIn"]: check(False, f"tab {i}: on {z['on']}, sections {z['secs']}, {z['shown']} cards showing and {z['folded']} folded against a count of {cnt[i]}, tab in view {z['onIn']}")
                check(seen == s["cards"], f"walking the tabs shows every card once ({seen} of {s['cards']})")
                await pg.evaluate("window.scrollTo(0, 700)"); await pg.wait_for_timeout(300); y = await pg.evaluate(M)
                check(abs(y["top"] - y["nav"]) <= 2, f"the tab row stays under the site bar while the page scrolls (row at {y['top']}px, bar ends at {y['nav']}px)")
                await shot(pg, "fold-best-scrolled")
            check(not errs, f"Model's Best: no script errors {errs[:1] or ''}"); await ctx.close()
            if s["tabs"] and "parlay" in [t.split(":")[0] for t in s["tabs"]]:
                pg, ctx, errs = await page("/best/#parlay", t=T0); h = await pg.evaluate(M); await ctx.close()
                check(h["on"] == "parlay" and h["secs"] == ["parlay"] and h["onIn"] and not errs, f"/best/#parlay (Today's \"Every game\" link) opens on the parlays, with that tab in view")

        # ---------- DFS ----------
        if has("/dfs/"):
            D = "() => { " + VIS + " var t = document.querySelector('.dfs .fxtabs'); return {tabs: t && vis(t) ? qa('.tab', t).map(function(b){ return b.textContent.trim() + (b.classList.contains('on') ? '*' : ''); }) : null, pool: vis(document.querySelector('.dfs [data-tab=pool]')), lu: vis(document.getElementById('lineup')), how: vis(document.querySelector('.dfs [data-tab=how]')), rows: qa('#plist tr').length, more: document.getElementById('more').textContent, bar: vis(document.getElementById('mbar')), build: vis(document.getElementById('optBtn')), first: qa('#plist tr b').slice(0, 3).map(function(b){ return b.textContent; })}; }"
            pg, ctx, errs = await page("/dfs/"); s = await pg.evaluate(D)
            check(s["tabs"] and s["tabs"][0] == "Players*" and s["pool"] and not s["lu"] and not s["how"], f"DFS on a phone: three tabs, the player pool first ({s['tabs']})")
            check(s["rows"] <= 20 and ("more of" in s["more"] or s["rows"] < 20), f"the pool opens on {s['rows']} rows ({s['more']!r})")
            pts = await pg.evaluate("() => [...document.querySelectorAll('#plist tr')].map(function(r){ return parseFloat(r.querySelectorAll('td')[2].textContent); })")
            sal = await pg.evaluate("() => [...document.querySelectorAll('#plist td.sal input')].some(function(i){ return i.value; })")
            if not sal: check(pts == sorted(pts, reverse=True), f"with no salaries loaded the best projections lead ({pts[:4]})")
            n0 = s["rows"]; 
            if "more of" in s["more"]: await pg.click("#more"); m = await pg.evaluate(D); check(m["rows"] > n0, f"Show more adds rows ({n0} -> {m['rows']})")
            await pg.click("#plist tr .add"); await pg.wait_for_timeout(150); a = await pg.evaluate(D)
            check(any(t.startswith("Lineup 1/") for t in a["tabs"]) and a["bar"], f"adding a player shows on the Lineup tab and the bar ({a['tabs'][1]})")
            await pg.click("#mbar"); await pg.wait_for_timeout(200); l = await pg.evaluate(D)
            check(l["lu"] and not l["pool"] and l["build"] and not l["bar"] and l["tabs"][1].endswith("*"), "the lineup bar opens the Lineup tab, where Build the best lineup is on screen")
            await pg.click('.dfs .fxtabs [data-t="how"]'); h = await pg.evaluate(D); check(h["how"] and not h["lu"] and not h["pool"], "How it works is its own tab")
            check(not errs, f"DFS phone: no script errors {errs[:1] or ''}"); await shot(pg, "fold-dfs-lineup"); await ctx.close()
            pg, ctx, errs = await page("/dfs/", w=1280); w = await pg.evaluate(D); await ctx.close()
            check(w["tabs"] is None and w["pool"] and w["lu"] and w["how"] and w["rows"] > 20 and not errs, f"DFS on a wide screen is unchanged: no tab row, pool and lineup side by side, {w['rows']} rows")
            pg, ctx, errs = await page("/dfs/#lineup"); x = await pg.evaluate(D); await ctx.close()
            check(x["lu"] and not x["pool"], "/dfs/#lineup opens on the lineup")

        # ---------- First TD ----------
        if has("/firsttd/"):
            F = "() => { " + VIS + " var ds = qa('section.ftd details.fgd'); return {n: qa('section.ftd').length, folded: ds.length, open: ds.filter(function(d){ return d.open; }).map(function(d){ return d.parentNode.id; }), top3: ds.map(function(d){ return (d.querySelector('.ftop3') || {textContent: ''}).textContent; }), tables: qa('section.ftd table').filter(vis).length, lists: qa('.ftdwrap .strips ul').map(function(ul){ return qa('li[data-ko]', ul).filter(vis).length; }), sw: vis(document.getElementById('fsw')), how: (document.querySelector('.ftdwrap details.how') || {open: null}).open, y: Math.round(scrollY)}; }"
            pg, ctx, errs = await page("/firsttd/", t=T0); s = await pg.evaluate(F)
            check(s["n"] >= 1 and s["folded"] == s["n"] and not s["open"] and s["tables"] == 0, f"First TD: {s['n']} games, each folded")
            check(all(t.count("%") == 3 for t in s["top3"]), f"every game's header names its three most likely scorers ({s['top3'][0][:70]!r})")
            check(s["sw"] and s["lists"][0] == 12 and s["lists"][1] == 0 and s["how"] is False, f"on a phone one list shows at a time ({s['lists']}) and the method is folded")
            await pg.click('#fsw [data-s="1"]'); e = await pg.evaluate(F); check(e["lists"][0] == 0 and e["lists"][1] >= 1, f"Best edges swaps the list ({e['lists']})")
            await pg.click('#fsw [data-s="0"]')
            gid = await pg.evaluate("() => document.querySelector('.ftdwrap .strips ul li:not([hidden]) a[href^=\"#ftd-\"]').getAttribute('href').slice(1)")
            await pg.click('.ftdwrap .strips ul li:not([hidden]) a[href^="#ftd-"]'); await pg.wait_for_timeout(400); o = await pg.evaluate(F)
            check(o["open"] == [gid] and o["tables"] == 1 and o["y"] > 200, f"a name in the list opens his game and goes to it ({gid})")
            chip = await pg.evaluate("() => { var a = [...document.querySelectorAll('nav.nav a[href^=\"#ftd-\"]')].pop(); return a ? a.getAttribute('href') : null; }")
            if chip:
                await pg.evaluate("(h) => { [...document.querySelectorAll('nav.nav a')].filter(function(a){ return a.getAttribute('href') === h; })[0].click(); }", chip); await pg.wait_for_timeout(400); c = await pg.evaluate(F)
                check(chip[1:] in c["open"], f"a game chip opens its game ({chip})")
            await pg.click(f"#{gid} summary"); await pg.wait_for_timeout(150); c2 = await pg.evaluate(F); check(gid not in c2["open"], "a tap on an open header folds it again")
            check(not errs, f"First TD: no script errors {errs[:1] or ''}"); await shot(pg, "fold-firsttd-open"); await ctx.close()
            g1 = re.search(r'<section class="ftd" id="(ftd-[A-Z-]+)"', open(os.path.join(ROOT, "firsttd", "index.html")).read()).group(1)
            pg, ctx, errs = await page(f"/firsttd/#{g1}", t=T0); d = await pg.evaluate(F); await ctx.close()
            check(d["open"] == [g1] and not errs, f"a shared link to one game (/firsttd/#{g1}) arrives with it open")
            pg, ctx, errs = await page("/firsttd/", w=1280, t=T0); w = await pg.evaluate(F); await ctx.close()
            check(not w["sw"] and w["lists"][0] == 12 and w["lists"][1] >= 1 and not errs, f"on a wide screen both lists stay side by side ({w['lists']})")
        # ---------- Players (the directory) ----------
        if has("/player/"):
            P = "() => { " + VIS + " var lis = qa('.pd li'); return {all: lis.length, shown: lis.filter(vis).length, more: vis(document.getElementById('pdmore')), btn: document.getElementById('pdmoreb').textContent, cnt: document.getElementById('pdcnt').textContent, first: lis.slice(0, 30).every(vis)}; }"
            pg, ctx, errs = await page("/player/"); s = await pg.evaluate(P); d = await pg.evaluate(LEN)
            check(s["shown"] == min(30, s["all"]) and s["first"] and s["more"] == (s["all"] > 30) and d["scr"] <= 4.5 and d["over"] <= 1, f"Players opens on the first 30 of {s['all']} at {d['scr']:.1f} phone screens ({s['cnt']!r})")
            if s["all"] > 30:
                check(s["btn"] == f"Show all {s['all']}", f"its button says how many ({s['btn']!r})")
                await pg.fill("#pdq", "chiefs kc"); await pg.wait_for_timeout(120); z = await pg.evaluate(P)
                await pg.fill("#pdq", "kc"); await pg.wait_for_timeout(120); k = await pg.evaluate(P)
                hit = await pg.evaluate("() => [...document.querySelectorAll('.pd li')].filter(function(li){ return !li.hidden; }).every(function(li){ return li.getAttribute('data-s').indexOf('kc') >= 0; })")
                check(k["shown"] >= 1 and hit, f"a search still looks through every player, not the first 30 ({k['shown']} shown for 'kc', {k['cnt']!r})")
                await pg.fill("#pdq", "zzzz"); await pg.wait_for_timeout(120); n = await pg.evaluate(P); check(n["shown"] == 0 and "Nobody" in n["cnt"] and not n["more"], f"a search with no match says so ({n['cnt']!r})")
                await pg.fill("#pdq", ""); await pg.wait_for_timeout(120); await pg.click("#pdmoreb"); a = await pg.evaluate(P); check(a["shown"] == a["all"] and not a["more"], f"Show all lists all {a['all']}")
                await pg.click('.pd .pos [data-p="TE"]'); t = await pg.evaluate(P); te = await pg.evaluate("() => [...document.querySelectorAll('.pd li')].filter(function(li){ return !li.hidden; }).every(function(li){ return li.getAttribute('data-pos') === 'TE'; })")
                check(te and t["shown"] <= 30, f"a position starts short again ({t['shown']} tight ends shown, {t['cnt']!r})")
            check(not errs, f"Players: no script errors {errs[:1] or ''}"); await ctx.close()
            src = open(os.path.join(ROOT, "player", "index.html"), encoding="utf-8").read()
            check(len(re.findall(r'<li data-pos=', src)) == s["all"] and src.count('href="/player/') >= s["all"], "every player's link is still in the page for search engines and the site search")

        # ---------- Teams (the directory) ----------
        if has("/teams/"):
            T = "() => { " + VIS + " var t = document.querySelector('.tdir .fxtabs'); return {tabs: t ? qa('.tab', t).map(function(b){ return b.textContent.trim() + (b.classList.contains('on') ? '*' : ''); }) : null, divs: qa('.tdir section.div').filter(vis).length, teams: qa('.tdir section.div a').filter(vis).length, table: vis(document.getElementById('leaguet')), rows: qa('#leaguet tbody tr').length}; }"
            pg, ctx, errs = await page("/teams/"); s = await pg.evaluate(T); d = await pg.evaluate(LEN)
            check(s["tabs"] == ["Standings*", "League table"] and s["teams"] == 32 and not s["table"] and d["scr"] <= 5.0 and d["over"] <= 1, f"Teams opens on the standings: {s['divs']} divisions, {s['teams']} teams, {d['scr']:.1f} phone screens")
            await pg.click('.tdir .fxtabs [data-t="lt"]'); l = await pg.evaluate(T); d2 = await pg.evaluate(LEN)
            check(l["table"] and l["divs"] == 0 and l["rows"] == 32, f"League table is its own tab: {l['rows']} rows, {d2['scr']:.1f} screens")
            r0 = await pg.evaluate("() => document.querySelector('#leaguet tbody tr td').textContent.trim()"); await pg.click('#leaguet th.sort[data-c="3"]'); await pg.wait_for_timeout(120)
            r1 = await pg.evaluate("() => [...document.querySelectorAll('#leaguet tbody tr')].map(function(tr){ return +tr.children[3].getAttribute('data-v'); })")
            check(r1 == sorted(r1) or r1 == sorted(r1, reverse=True), "its columns still sort under the tab")
            check(not errs, f"Teams: no script errors {errs[:1] or ''}"); await ctx.close()

        # ---------- Teasers ----------
        if has("/teasers/"):
            Z = "() => { " + VIS + " var t = document.querySelector('.tzw .fxtabs'); return {tabs: t ? qa('.tab', t).map(function(b){ return b.textContent.trim() + (b.classList.contains('on') ? '*' : ''); }) : null, secs: qa('.tzw section.tz').map(function(s){ return [s.getAttribute('data-pts'), vis(s)]; }), verdict: (qa('.tzw section.tz').filter(vis)[0] || document.body).querySelector('.tzv').textContent}; }"
            pg, ctx, errs = await page("/teasers/"); s = await pg.evaluate(Z); d = await pg.evaluate(LEN)
            if not s["tabs"]: skip("Teasers has one size this build, so it has no tabs")
            else:
                check(len(s["tabs"]) == len(s["secs"]) and [v for _, v in s["secs"]] == [True] + [False] * (len(s["secs"]) - 1) and d["scr"] <= 4.5 and d["over"] <= 1, f"Teasers opens on one size ({s['tabs']}) at {d['scr']:.1f} phone screens")
                await pg.click(".tzw .fxtabs .tab:last-child"); z = await pg.evaluate(Z)
                check([v for _, v in z["secs"]] == [False] * (len(z["secs"]) - 1) + [True] and z["tabs"][-1].endswith("*"), f"a tab shows its size alone ({z['tabs'][-1]})")
                v0 = z["verdict"]; await pg.fill(".tzw section.tz:not(.fxoff) input.px", "120"); await pg.wait_for_timeout(120); v1 = (await pg.evaluate(Z))["verdict"]
                check(v1 != v0 and "-120" in v1, f"typing a price still re-scores the size on screen ({v1[:48]!r})")
            check(not errs, f"Teasers: no script errors {errs[:1] or ''}"); await ctx.close()

        # ---------- Season (built on Tuesdays; its fold lives in the shared script) ----------
        if has("/season/"):
            S2 = "() => { " + VIS + " var cs = qa('section.card.calib'); return {n: cs.length, folded: cs.filter(function(c){ return c.classList.contains('bsfold'); }).length, body: cs.reduce(function(a, c){ return a + qa(':scope > :not(h2)', c).filter(vis).length; }, 0), heads: qa('section.card.calib > h2').filter(vis).length, sum: vis(document.getElementById('summary') || document.body)}; }"
            pg, ctx, errs = await page("/season/"); s = await pg.evaluate(S2); d = await pg.evaluate(LEN)   # a folded card is laid out at its real size (no 900px placeholder), so this length is the real one
            if not s["n"]: skip("this build's Season page has no report cards")
            else:
                check(s["folded"] == s["n"] and s["body"] == 0 and s["heads"] == s["n"] and s["sum"] and d["scr"] <= 5.5 and d["over"] <= 1, f"Season on a phone: the summary, then {s['n']} report cards on their titles - {d['scr']:.1f} phone screens")
                await pg.click("section.card.calib > h2"); o = await pg.evaluate(S2); ex = await pg.evaluate("() => document.querySelector('section.card.calib > h2').getAttribute('aria-expanded')")
                check(o["folded"] == o["n"] - 1 and o["body"] >= 1 and ex == "true", "a tap on a title opens that card")
                await pg.click("section.card.calib > h2"); c = await pg.evaluate(S2); check(c["folded"] == c["n"], "and a second tap folds it")
            check(not errs, f"Season phone: no script errors {errs[:1] or ''}"); await ctx.close()
            pg, ctx, errs = await page("/season/", w=1280); w = await pg.evaluate(S2); await ctx.close()
            check(w["folded"] == 0 and not errs, "on a wide screen the Season cards are open as before")

        # ---------- a player's page ----------
        pdir = os.path.join(ROOT, "player"); with_props = no_props = None
        if os.path.isdir(pdir):
            for sl in sorted(os.listdir(pdir)):
                fp = os.path.join(pdir, sl, "index.html")
                if not os.path.isfile(fp): continue
                src = open(fp, encoding="utf-8").read()
                if 'id="ppTabs"' not in src: continue
                if with_props is None and '<div data-tab="props">' in src and 'class="add"' in src and src.count("data-tab=") >= 4: with_props = sl
                if no_props is None and '<div data-tab="props" class="fxoff">' in src: no_props = sl
                if with_props and no_props: break
        PP = "() => { " + VIS + " var t = document.querySelector('.pp .fxtabs'); var secs = qa('.pp section'); return {tabs: t ? qa('.tab', t).map(function(b){ return b.dataset.t + (b.classList.contains('on') ? '*' : ''); }) : null, panels: qa('.pp [data-tab]').map(function(p){ return [p.getAttribute('data-tab'), vis(p), qa('section', p).length]; }), secs: secs.length, shown: secs.filter(vis).map(function(s){ return (s.querySelector('h2') || {textContent: ''}).textContent.trim().slice(0, 22); }), loose: secs.filter(function(s){ return !s.closest('[data-tab]'); }).length, top: t ? Math.round(t.getBoundingClientRect().top) : null, nav: Math.round(document.querySelector('.sitenav').getBoundingClientRect().bottom), bar: (document.querySelector('#ppbar b') || {textContent: ''}).textContent}; }"
        if not with_props: skip("no player page with props and tabs in this build")
        else:
            path = f"/player/{with_props}/"
            for theme in ("light", "dark"):   # the dark page stays open for the checks that follow
                pg, ctx, errs = await page(path, theme, t=T0); d = await pg.evaluate(LEN); s = await pg.evaluate(PP); await shot(pg, f"fold-player-{theme}")
                check(d["scr"] <= 4.5 and d["over"] <= 1 and not errs, f"[{theme}] a player page ({with_props}) opens at {d['scr']:.1f} phone screens (it was 6.7), no sideways scroll, no script errors {errs[:1] or ''}")
                if theme == "light": await ctx.close()
            check(s["tabs"] and s["tabs"][0] == "props*" and [p[1] for p in s["panels"]] == [True] + [False] * (len(s["panels"]) - 1) and any("props" in x.lower() for x in s["shown"]), f"it opens on this week's props, the other sections one tap away ({s['tabs']})")
            check(s["loose"] == 0 and sum(p[2] for p in s["panels"]) == s["secs"], f"every section of the page is under a tab ({s['secs']} sections in {len(s['panels'])} tabs)")
            seen = 0
            for i in [x.rstrip("*") for x in s["tabs"]]:
                await pg.click(f'.pp .fxtabs [data-t="{i}"]'); await pg.wait_for_timeout(100); z = await pg.evaluate(PP); seen += len(z["shown"])
                if [p[0] for p in z["panels"] if p[1]] != [i]: check(False, f"tab {i} shows {[p[0] for p in z['panels'] if p[1]]}")
            check(seen == s["secs"], f"walking the tabs shows every section once ({seen} of {s['secs']})")
            await pg.click('.pp .fxtabs [data-t="props"]'); await pg.wait_for_timeout(100)
            addsel = ".pp [data-tab=props] .add[data-k]:not([disabled])"
            if await pg.evaluate("(s) => { var qa = function(q){ return Array.from(document.querySelectorAll(q)); }; return qa(s).filter(function(e){ return !e.checkVisibility || e.checkVisibility(); }).length; }", addsel):
                await pg.evaluate("(s) => { var b = Array.from(document.querySelectorAll(s)).filter(function(e){ return !e.checkVisibility || e.checkVisibility(); })[0]; b.scrollIntoView({block: 'center'}); b.click(); }", addsel); await pg.wait_for_timeout(150); a = await pg.evaluate(PP)
                check("1 leg" in a["bar"], f"a + on a line still adds it to the slip ({a['bar']!r})")
            await pg.evaluate("window.scrollTo(0, 900)"); await pg.wait_for_timeout(300); y = await pg.evaluate(PP)
            check(abs(y["top"] - y["nav"]) <= 2, f"the tab row stays under the site bar while the page scrolls (row at {y['top']}px, bar ends at {y['nav']}px)")
            await ctx.close()
            last = [x.rstrip("*") for x in s["tabs"]][-1]
            pg, ctx, errs = await page(path + "#" + last, t=T0); h = await pg.evaluate(PP); await ctx.close()
            check(h["tabs"][-1] == last + "*" and not errs, f"{path}#{last} opens on that tab")
            src = open(os.path.join(pdir, with_props, "index.html"), encoding="utf-8").read()
            check("<noscript><style>.fxoff{display:block!important}</style></noscript>" in src, "with scripts off every section shows (noscript)")
        if not no_props: skip("every player page in this build has props, so the no-props opening has nothing to check")
        else:
            pg, ctx, errs = await page(f"/player/{no_props}/", t=T0); n = await pg.evaluate(PP); d = await pg.evaluate(LEN); await ctx.close()
            on = [x for x in n["tabs"] if x.endswith("*")][0]
            check(on != "props*" and "props" in n["tabs"] and len([p for p in n["panels"] if p[1]]) == 1 and d["scr"] <= 4.5 and not errs, f"a player with no lines this week ({no_props}) opens on {on.rstrip('*')} instead of an empty Props tab ({n['tabs']}, {d['scr']:.1f} screens)")

        # ---------- a team's page ----------
        tdir = os.path.join(ROOT, "teams"); team = next((x for x in sorted(os.listdir(tdir)) if os.path.isfile(os.path.join(tdir, x, "index.html")) and 'id="tpTabs"' in open(os.path.join(tdir, x, "index.html"), encoding="utf-8").read()), None) if os.path.isdir(tdir) else None
        if not team: skip("no team page with tabs in this build")
        else:
            TP = "() => { " + VIS + " var t = document.querySelector('.pp .fxtabs'); return {tabs: t ? qa('.tab', t).map(function(b){ return b.dataset.t + (b.classList.contains('on') ? '*' : ''); }) : null, panels: qa('.pp [data-tab]').map(function(p){ return [p.getAttribute('data-tab'), vis(p)]; }), loose: qa('.pp section').filter(function(s){ return !s.closest('[data-tab]'); }).length, games: qa('.pp details.gm[data-g]').filter(vis).length, box: qa('.pp details.gm[open] .pbox table').filter(vis).length}; }"
            for theme in ("light", "dark"):   # the dark page stays open for the checks that follow
                pg, ctx, errs = await page(f"/teams/{team}/", theme); d = await pg.evaluate(LEN); s = await pg.evaluate(TP); await shot(pg, f"fold-team-{theme}")
                check(d["scr"] <= 4.5 and d["over"] <= 1 and not errs, f"[{theme}] a team page ({team}) opens at {d['scr']:.1f} phone screens (it was 5.8), no sideways scroll, no script errors {errs[:1] or ''}")
                if theme == "light": await ctx.close()
            check(s["tabs"] == ["stats*", "games", "leaders"] and [p[1] for p in s["panels"]] == [True, False, False] and s["loose"] == 0 and s["games"] == 0, f"it opens on Stats; Games and Leaders are tabs ({s['tabs']})")
            await pg.click('.pp .fxtabs [data-t="games"]'); await pg.wait_for_timeout(120); g = await pg.evaluate(TP)
            check(g["games"] >= 1 and [p[1] for p in g["panels"]] == [False, True, False], f"Games lists the results and schedule ({g['games']} played games)")
            await pg.click(".pp details.gm[data-g] > summary"); await pg.wait_for_timeout(700); b2 = await pg.evaluate(TP)
            check(b2["box"] >= 1, f"a tap on a game still loads its box score ({b2['box']} tables)")
            await pg.click('.pp .fxtabs [data-t="leaders"]'); await pg.wait_for_timeout(120); l = await pg.evaluate(TP)
            check([p[1] for p in l["panels"]] == [False, False, True] and not errs, "Leaders is its own tab")
            await ctx.close()
            pg, ctx, errs = await page(f"/teams/{team}/#games"); h = await pg.evaluate(TP); await ctx.close()
            check(h["tabs"][1] == "games*" and not errs, f"/teams/{team}/#games opens on the games")

        # ---------- a game preview ----------
        ddir = os.path.join(ROOT, "dossier"); gm = next((x for x in sorted(os.listdir(ddir)) if os.path.isfile(os.path.join(ddir, x, "index.html")) and 'id="dsTabs"' in open(os.path.join(ddir, x, "index.html"), encoding="utf-8").read()), None) if os.path.isdir(ddir) else None
        if not gm: skip("no game preview with tabs in this build")
        else:
            DS = "() => { " + VIS + " var t = document.querySelector('.pp .fxtabs'); return {tabs: t && vis(t) ? qa('.tab', t).map(function(b){ return b.textContent.trim() + (b.classList.contains('on') ? '*' : ''); }) : null, panels: qa('.pp [data-tab]').map(function(p){ return [p.getAttribute('data-tab'), vis(p), qa('section', p).length]; }), loose: qa('.pp section').filter(function(s){ return !s.closest('[data-tab]'); }).length, cols: (function(){ var x = qa('.dsx > div').filter(vis).map(function(e){ return Math.round(e.getBoundingClientRect().left); }); return x.filter(function(v, i){ return x.indexOf(v) === i; }).length; })()}; }"
            for theme in ("light", "dark"):   # the dark page stays open for the checks that follow
                pg, ctx, errs = await page(f"/dossier/{gm}/", theme); d = await pg.evaluate(LEN); s = await pg.evaluate(DS); await shot(pg, f"fold-preview-{theme}")
                check(d["scr"] <= 4.5 and d["over"] <= 1 and not errs, f"[{theme}] a game preview ({gm}) opens at {d['scr']:.1f} phone screens (it was 6.1), no sideways scroll, no script errors {errs[:1] or ''}")
                if theme == "light": await ctx.close()
            a_, b_ = gm.split("-")
            check(s["tabs"] == ["Game*", f"{a_} offense", f"{b_} offense"] and [p[1] for p in s["panels"]] == [True, False, False] and s["loose"] == 0 and s["panels"][0][2] == 3, f"it opens on the game: script, injuries / weather / news, tested spots ({s['tabs']})")
            await pg.click(f'#dsTabs [data-t="o{b_.lower()}"]'); await pg.wait_for_timeout(120); o = await pg.evaluate(DS)
            check([p[1] for p in o["panels"]] == [False, False, True] and o["panels"][2][2] == 3, f"{b_} offense shows that side's three sections alone")
            await ctx.close()
            pg, ctx, errs = await page(f"/dossier/{gm}/", w=1280); w = await pg.evaluate(DS); await ctx.close()
            check(w["tabs"] is None and all(p[1] for p in w["panels"]) and w["cols"] == 2 and not errs, "on a wide screen the preview is unchanged: no tab row, the game on top, the two offenses side by side")
            pg, ctx, errs = await page(f"/dossier/{gm}/#o{a_.lower()}"); h = await pg.evaluate(DS); await ctx.close()
            check(h["tabs"][1].endswith("*") and not errs, f"/dossier/{gm}/#o{a_.lower()} opens on that offense")

        # ---------- a weekly receipt (kept by a reprice; its scorecard tabs come from the shared script) ----------
        rdir = os.path.join(ROOT, "receipts"); weeks = sorted((int(x[4:]) for x in os.listdir(rdir) if re.fullmatch(r"week\d+", x) and os.path.isfile(os.path.join(rdir, x, "index.html"))), reverse=True) if os.path.isdir(rdir) else []
        RC = "() => { " + VIS + " var sb = document.querySelector('section.card.scorecard .scbody'); if(!sb) return null; var t = sb.querySelector(':scope > .fxtabs'); var grp = qa(':scope > [data-tab]', sb); return {tabs: t && vis(t) ? qa('.tab', t).map(function(b){ return b.textContent.trim() + (b.classList.contains('on') ? '*' : ''); }) : null, groups: grp.map(function(g){ return [vis(g), (g.querySelector('h3') || {textContent: ''}).textContent.trim().slice(0, 24)]; }), loose: qa(':scope > *', sb).filter(function(e){ return !e.hasAttribute('data-tab') && !e.classList.contains('fxtabs') && !e.classList.contains('fxanchor'); }).length, h3: qa('h3', sb).length, cols: (function(){ var x = qa('.tiles', sb).filter(vis)[0]; if(!x) return 0; var l = qa('.tile', x).map(function(e){ return Math.round(e.getBoundingClientRect().left); }); return l.filter(function(v, i){ return l.indexOf(v) === i; }).length; })(), cardH: Math.round(document.querySelector('section.card.scorecard').getBoundingClientRect().height)}; }"
        if not weeks: skip("no weekly receipt in this copy")
        else:
            wk = weeks[0]; pg, ctx, errs = await page(f"/receipts/week{wk}/"); s = await pg.evaluate(RC)
            if not s or not s["tabs"]: check(False, f"the Week {wk} receipt's scorecard has its tabs on a phone ({s})")
            else:
                check(len(s["tabs"]) == s["h3"] == len(s["groups"]) and [g[0] for g in s["groups"]] == [True] + [False] * (len(s["groups"]) - 1) and s["loose"] == 0, f"the Week {wk} receipt's scorecard shows one group at a time on a phone ({s['tabs']})")
                check(s["cols"] == 2, f"its tiles sit two to a row ({s['cols']})")
                seen = []
                for i in range(len(s["tabs"])):
                    await pg.click(f'section.card.scorecard .scbody > .fxtabs [data-t="sc{i}"]'); await pg.wait_for_timeout(100); z = await pg.evaluate(RC); seen.append([g[1] for g in z["groups"] if g[0]])
                check(all(len(x) == 1 for x in seen) and len({x[0] for x in seen}) == len(s["tabs"]), f"each tab shows its own group ({[x[0] for x in seen]})")
            check(not errs, f"Week {wk} receipt: no script errors {errs[:1] or ''}"); await ctx.close()
            pg, ctx, errs = await page(f"/receipts/week{wk}/"); await pg.add_style_tag(content="*{content-visibility:visible!important}"); await pg.wait_for_timeout(300); d = await pg.evaluate(LEN); await ctx.close()
            check(d["scr"] <= 12.5, f"with every card laid out the Week {wk} receipt is {d['scr']:.1f} phone screens (it was 15.0)")
            for w2 in weeks[1:]:
                pg, ctx, errs = await page(f"/receipts/week{w2}/"); o = await pg.evaluate(RC); await ctx.close()
                if o and o["h3"] >= 3: check(bool(o["tabs"]) and o["loose"] == 0 and len(o["tabs"]) == o["h3"] and not errs, f"the Week {w2} receipt gets the same tabs ({o['tabs']})")
            pg, ctx, errs = await page(f"/receipts/week{wk}/", w=1280); w = await pg.evaluate(RC); await ctx.close()
            check(w and w["tabs"] is None and not w["groups"] and not errs, "on a wide screen the scorecard is one piece, as before")

        # ---------- the picture buttons ("Copy card as image"): the whole card, on any card ----------
        # Found 11/17 on the published pages: the scorecard's picture failed ("Could not render": a color-mix() background the image tool
        # cannot read) and every other card's stopped at 992px (a lazy card keeps its 900px placeholder in the tool's off-screen copy).
        async def picture(path, sel, w=390):
            pg, ctx, errs = await page(path, w=w)
            c = await pg.evaluate("(s) => { var c = document.querySelector(s); if(!c) return null; var b = c.querySelector('.snap:not(.story):not(.more)'); if(!b) return null; c.classList.add('bsshoot'); var r = c.getBoundingClientRect(); var out = [r.width, r.height]; c.classList.remove('bsshoot'); b.scrollIntoView({block: 'center'}); b.click(); return out; }", sel)
            if not c: await ctx.close(); return None
            try:
                await pg.wait_for_selector(sel + " .shotwrap img", timeout=60000); await pg.wait_for_timeout(300)
                im = await pg.evaluate("(s) => { var i = document.querySelector(s + ' .shotwrap img'), c = document.querySelector(s); return [i.naturalWidth, i.naturalHeight, c.classList.contains('bsshoot')]; }", sel)
            except Exception:
                im = [0, 0, await pg.evaluate("(s) => (document.querySelector(s + ' .snap:not(.story):not(.more)') || {textContent: ''}).textContent", sel)]
            await ctx.close(); return {"card": c, "pic": im, "errs": errs}
        if weeks:   # the Story frame is not zoomed with the rest of the page, so the 540px picture holds the whole width of the card
            for w in (390, 1280):
                pg, ctx, errs = await page(f"/receipts/week{weeks[0]}/", w=w)
                z = await pg.evaluate("() => { var f = document.createElement('div'); f.className = 'storyframe'; var c = document.querySelector('section.card.calls, section.card.summary').cloneNode(true); c.removeAttribute('id'); f.appendChild(c); document.body.appendChild(f); var r = [getComputedStyle(f).zoom, Math.round(f.getBoundingClientRect().width), Math.round(c.getBoundingClientRect().right), getComputedStyle(document.querySelector('.top, main, .grid') || document.body).zoom]; f.remove(); return r; }"); await ctx.close()
                check(str(z[0]) == "1" and z[1] == 540 and z[2] <= 541, f"the Story frame at {w}px is 540px wide with the card inside it (frame {z[1]}px, card's right edge {z[2]}px; the page itself is zoomed {z[3]})")
        shots = [(f"/receipts/week{weeks[0]}/", "section.card.scorecard", 390, "a receipt's scorecard, phone (folded on screen)"), (f"/receipts/week{weeks[0]}/", "section.card.scorecard", 1280, "a receipt's scorecard, wide"), (f"/receipts/week{weeks[0]}/", "section.card.calls", 390, "a receipt's Calls card")] if weeks else []
        if has("/season/"): shots.append(("/season/", "section.card.summary", 390, "the Season card"))
        for path, sel, w, what in shots:
            r = await picture(path, sel, w)
            if not r: skip(f"{what}: no picture button on this copy"); continue
            if not r["pic"][0]: check(False, f"{what}: the picture did not render ({r['pic'][2]!r})"); continue
            ratio = r["pic"][1] / r["pic"][0]; want = r["card"][1] / r["card"][0]
            check(want * 0.85 <= ratio <= want * 1.03 and r["pic"][1] > 2100 and r["pic"][2] is False, f"{what}: the picture is the whole card ({r['pic'][0]}x{r['pic'][1]}, height/width {ratio:.2f} against the card's {want:.2f})")
        await b.close()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
