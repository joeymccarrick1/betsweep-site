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

  python3 tests/page_fold.py [shots_dir]      (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, http.server, json, os, re, sys, threading
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8871; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
def skip(what): print("SKIP " + what)
def has(path): return os.path.isfile(os.path.join(ROOT, path.strip("/"), "index.html"))
# longest a page may open at on a phone, in screens. Loose on purpose: a busy week adds rows, and the caps are what hold the length.
LIMIT = {"/usage/": 5.0, "/benefits/": 4.5, "/shop/": 4.5, "/news/": 5.0, "/best/": 4.5, "/dfs/": 5.0, "/firsttd/": 6.5}
VIS = "var qa = function(s, r){ return Array.from((r || document).querySelectorAll(s)); }, vis = function(e){ if(e.checkVisibility && !e.checkVisibility()) return false; var r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };"   # checkVisibility: a closed <details> keeps its content's box
LEN = "() => ({scr: document.documentElement.scrollHeight / innerHeight, over: document.documentElement.scrollWidth - document.documentElement.clientWidth})"

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
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
            M = "() => { " + VIS + " var tabs = qa('.wk .fxtabs .tab'); var on = document.querySelector('.wk .fxtabs .tab.on'); return {tabs: tabs.map(function(b){ return b.dataset.t + ':' + b.textContent.trim(); }), on: on ? on.dataset.t : null, cards: qa('article.play, .parlay, .pmini').length, shown: qa('article.play, .parlay, .pmini').filter(vis).length, secs: qa('.wk [data-tab]').filter(vis).map(function(e){ return e.getAttribute('data-tab'); }), best: vis(document.getElementById('best') || document.body), top: tabs.length ? Math.round(document.querySelector('.wk .fxtabs').getBoundingClientRect().top) : null, nav: Math.round(document.querySelector('.sitenav').getBoundingClientRect().bottom), onIn: on ? (on.getBoundingClientRect().left >= 0 && on.getBoundingClientRect().right <= innerWidth + 1) : null}; }"
            pg, ctx, errs = await page("/best/", t=T0); s = await pg.evaluate(M)
            if not s["tabs"]: skip("Model's Best has one section this build, so it has no tabs")
            else:
                ids = [t.split(":")[0] for t in s["tabs"]]; cnt = {t.split(":")[0]: (int(m.group(1)) if (m := re.search(r"(\d+)$", t)) else 0) for t in s["tabs"]}
                check(s["on"] == ids[0] and set(s["secs"]) == {ids[0]} and s["shown"] == cnt[ids[0]], f"Model's Best opens on its first tab with that tab's {s['shown']} cards and nothing else ({[t.split(':')[1] for t in s['tabs']]})")
                check(sum(cnt.values()) == s["cards"], f"the tab counts add up to every card on the page ({s['cards']})")
                seen = 0
                for i in ids:
                    await pg.click(f'.wk .fxtabs [data-t="{i}"]'); await pg.wait_for_timeout(120); z = await pg.evaluate(M); seen += z["shown"]
                    if z["on"] != i or set(z["secs"]) != {i} or z["shown"] != cnt[i] or not z["onIn"]: check(False, f"tab {i}: on {z['on']}, sections {z['secs']}, {z['shown']} cards against a count of {cnt[i]}, tab in view {z['onIn']}")
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
        await b.close()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
