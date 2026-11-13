#!/usr/bin/env python3
"""tests/home_compact.py - the short home page, the regrouped menu and the "Where to next" strips (owner 11/10 9:33-9:41 PM:
"make sure all of the pages are more fluid and make more sense moving from one to the next ... make the organization of the pages
more optimized where they are in the menu"; "Let's compact the home page ... Slate probably doesn't need to be on the home page").

  BASE=http://localhost:8802 SITE=<built site dir> python3 tests/home_compact.py
Needs a built site (./site by default) served at BASE. Non-local requests are blocked.
"""
import datetime, json, os, re, sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8802"); SITE = os.environ.get("SITE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site"))
fails = []
def ok(c, name, extra=""):
    print(("ok  " if c else "FAIL"), name, extra)
    if not c: fails.append(name)
def has_file(href):
    p = href.split("#")[0].split("?")[0]
    if not p.startswith("/"): return True
    f = os.path.join(SITE, p.strip("/"), "index.html") if p.endswith("/") else os.path.join(SITE, p.lstrip("/"))
    return os.path.exists(f) or p.startswith(("/lab/", "/receipts/", "/season/", "/data/", "/me/", "/promo/", "/social/"))   # served by the clone, not rebuilt every run

with sync_playwright() as pw:
    b = pw.chromium.launch()
    def page(path, when=None, w=390, h=844):
        c = b.new_context(viewport={"width": w, "height": h}, is_mobile=w < 600, has_touch=w < 600); pg = c.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(BASE) else r.abort())
        if when: pg.clock.install(time=when)
        pg.goto(BASE + path, wait_until="load"); pg.wait_for_timeout(1300); return pg, errs
    # ---- the home page, as built (the next game day has few games) ----
    pg, errs = page("/")
    H = pg.evaluate("document.documentElement.scrollHeight"); ids = pg.evaluate("[].slice.call(document.querySelectorAll('section[id]')).filter(function(s){ return s.offsetParent !== null; }).map(function(s){ return s.id; })")
    ok(not errs, "home: no script errors", str(errs)[:200])
    ok(H < 7500, "home: under 7,500px on a phone (it was 15,690)", f"{H}px, sections {ids}")
    ok(not any(x in ids for x in ("slate", "tdtrade", "tdweek", "plays", "nextman", "radar")), "home: the slate, the trade desk, the week list, top plays, next man up and the radar are gone")
    ok(pg.evaluate("document.querySelectorAll('#hsbar').length") == 1, "home: one betslip bar (there were two)")
    first = pg.evaluate("(function(){ var s = [].slice.call(document.querySelectorAll('section')).filter(function(x){ return x.offsetParent !== null; }); return s.slice(0, 5).map(function(x){ return x.id || x.className; }); })()")
    # 11/11: the FanDuel unders pull is back (the owner installed FanDuelOdds.gs v2026-11-10), so "Under of the day" (#bsunder) has a card
    # again. Only the day's two single-card callouts - the Daily Sweep and the Under of the day - may sit between the head and the games.
    before = first[1:first.index("tdday")] if "tdday" in first else None
    ok(first[:1] == ["tdhead"] and before is not None and all(x in ("sweep", "winners", "bsunder") for x in before), "home: the head, then today's game - only the Daily Sweep and the Under of the day may come between", str(first))
    st = pg.evaluate("(function(){ var c = document.querySelector('.tdgame.show'); if(!c) return null; return {stats: [].slice.call(c.querySelectorAll('.tdstats span')).map(function(x){ return x.textContent; }), cd: (c.querySelector('.tdcd') || {}).textContent, pri: (c.querySelector('.tdlinks a.pri') || {}).getAttribute('href')}; })()")
    ok(st and len(st["stats"]) >= 2 and st["pri"] and st["pri"].startswith("/boards/#g-"), "today's game: a number strip and one main button to its board", str(st))
    ok(st and re.match(r"^in \d+[dhm]", st["cd"] or ""), "today's game: a kickoff countdown", str(st and st["cd"]))
    rows = pg.evaluate("[].slice.call(document.querySelectorAll('.mbl.teaser .mbrow')).filter(function(x){ return !x.hidden; }).length")
    dup = pg.evaluate("(function(){ var up = {}; document.querySelectorAll('.tdgame.show .play[data-k]').forEach(function(p){ if(p.offsetParent !== null) up[p.getAttribute('data-k')] = 1; }); return [].slice.call(document.querySelectorAll('.mbl.teaser .mbrow')).filter(function(x){ return !x.hidden && up[x.getAttribute('data-k')]; }).length; })()")
    ok(rows <= 3 and dup == 0, "Model's Best: at most three rows, none repeating a look already in today's game", f"{rows} rows, {dup} repeats")
    if rows:
        r = pg.evaluate("(function(){ var a = [].slice.call(document.querySelectorAll('.mbl.teaser .mbrow:not([hidden]) a.more'))[0]; var W = +document.getElementById('hsbar').getAttribute('data-week'); var k = 'bs_slipk_w' + W; localStorage.removeItem(k); a.click(); var one = JSON.parse(localStorage.getItem(k) || '[]'); var lab = a.textContent; a.click(); var two = JSON.parse(localStorage.getItem(k) || '[]'); return {one: one.length, lab: lab, two: two.length}; })()")
        ok(r["one"] == 1 and "In slip" in r["lab"] and r["two"] == 0, "+ Slip on a row adds the leg and a second tap removes it (the page ran the script twice and undid every tap)", str(r))
    nn = pg.evaluate("[].slice.call(document.querySelectorAll('#tdnewsl li')).filter(function(x){ return !x.hidden; }).length")
    ok(nn <= 3 and pg.evaluate("!!document.querySelector('#tdnewsS a.seeall[href=\"/news/\"]')"), "news: three notes and a link to the rest", f"{nn} shown")
    doors = pg.evaluate("[].slice.call(document.querySelectorAll('#doors a')).map(function(a){ return a.getAttribute('href'); })")
    ok(len(doors) == 8 and all(has_file(h) for h in doors), "eight doors, every one a page", str([h for h in doors if not has_file(h)]))
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "home: no sideways scroll")
    pg.context.close()
    # ---- a twelve-game Sunday ----
    try:
        bd = json.load(open(os.path.join(os.path.dirname(SITE), "out", "builder_data.json"))); kos = sorted(g["ko"] for g in bd["games"] if g.get("ko"))
        byday = {}
        for k in kos: byday.setdefault(datetime.datetime.fromtimestamp(k / 1000, datetime.timezone(datetime.timedelta(hours=-6))).date(), []).append(k)
        big = max(byday.items(), key=lambda kv: len(kv[1]))
    except Exception as e: big = None; print("note: no builder data for the busy-day check:", e)
    if big and len(big[1]) >= 3:
        when = datetime.datetime.fromtimestamp(min(big[1]) / 1000 - 3 * 3600, datetime.timezone.utc)
        pg, errs = page("/", when=when)
        info = pg.evaluate("({h: document.documentElement.scrollHeight, shown: document.querySelectorAll('.tdgame.show').length, folded: document.querySelectorAll('.tdgame.show.compact').length, looks: document.querySelectorAll('#tdlooksgrid .play').length, card: Math.round(document.querySelector('.tdgame.show').getBoundingClientRect().height)})")
        ok(not errs and info["shown"] == len(big[1]) and info["folded"] == info["shown"], f"a {len(big[1])}-game day: every card folds", str(info) + str(errs)[:120])
        ok(info["looks"] <= 3 and info["card"] < 400, "  three looks at most, a folded card under 400px", str(info))
        pg.evaluate("document.querySelector('.tdgame.show .tdtog').click()"); pg.wait_for_timeout(200)
        ok(pg.evaluate("(function(){ var c = document.querySelector('.tdgame.show'); return c.classList.contains('open') && c.querySelector('.tdmore').offsetParent !== null; })()"), "  More on this game opens it")
        pg.context.close()
    # ---- the pages the sections moved to ----
    for path, sel, least in (("/best/", ".play, .parlay", 1), ("/slate/", "a.game", 2), ("/news/", ".tdnewsl li", 1), ("/all/", ".nxl a", 30)):
        if not has_file(path): ok(path == "/best/" and False, f"{path} exists"); continue
        pg, errs = page(path)
        n = pg.evaluate("(s) => document.querySelectorAll(s).length", sel)
        ok(not errs and n >= least and pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), f"{path}: {n} items, no errors, fits a phone", str(errs)[:160])
        if path == "/news/":
            r = pg.evaluate("(function(){ var b = document.querySelectorAll('#nwf button')[1]; if(!b) return null; b.click(); var t = b.getAttribute('data-t'); var vis = [].slice.call(document.querySelectorAll('#news .tdnewsl li')).filter(function(x){ return !x.hidden; }); return {t: t, n: vis.length, all: vis.every(function(x){ return x.getAttribute('data-team') === t; })}; })()")
            ok(r and r["n"] >= 1 and r["all"], "  the team filter shows only that team", str(r))
        if path == "/slate/": ok(n == len(json.load(open(os.path.join(os.path.dirname(SITE), "out", "builder_data.json")))["games"]), "  every game of the week is listed", str(n))
        pg.context.close()
    # ---- menu and strips, read from the built files ----
    idx = open(os.path.join(SITE, "boards", "index.html"), encoding="utf-8").read()
    nav = re.search(r'<nav class="sitenav".*?</nav>', idx, re.S).group(0); links = re.findall(r'<a href="([^"]+)"', nav)
    groups = re.findall(r'class="ddb"[^>]*>([^<]+?) <i', nav); sizes = [len(re.findall(r"<a ", m)) for m in re.findall(r'<div class="ddm">(.*?)</div>', nav, re.S)]
    ok(all(has_file(h) for h in links), "menu: every link is a page", str([h for h in links if not has_file(h)]))
    ok(max(sizes) <= 8 and len(groups) == len(sizes), "menu: no group longer than eight", str(dict(zip(groups, sizes))))
    miss, bad, n = [], [], 0
    for d, _, fs in os.walk(SITE):
        if "index.html" not in fs: continue
        rel = "/" + os.path.relpath(d, SITE).replace(os.sep, "/") + "/"; rel = "/" if rel == "/./" else rel
        if rel == "/" or rel.startswith(("/terms", "/privacy", "/responsible", "/all/", "/today/", "/simple/", "/app/", "/p/", "/b/", "/s/", "/data/")): continue
        h = open(os.path.join(d, "index.html"), encoding="utf-8", errors="ignore").read()
        if 'http-equiv="refresh"' in h[:600]: continue
        m = re.search(r'<nav class="nx".*?</nav>', h, re.S); n += 1
        if not m: miss.append(rel); continue
        hs = re.findall(r'<a href="([^"]+)"', m.group(0))
        if not (2 <= len(hs) <= 3) or any(not has_file(x) for x in hs) or any(x.split("?")[0] == rel for x in hs): bad.append(rel)
    ok(not miss, f"Where to next: on every content page ({n} checked)", str(miss[:8]))
    ok(not bad, "  two or three doors each, every one a page, never the page itself", str(bad[:8]))
    # ---- phones: text that sits on the page background is not at the edge of the glass ----
    for path in ("/pairs/", "/sweep/", "/player/", "/usage/", "/receipts/", "/boards/"):
        if not has_file(path): continue
        pg, errs = page(path)
        x = pg.evaluate("(function(){ var h = document.querySelector('h1'); return h ? Math.round(h.getBoundingClientRect().left) : -1; })()")
        ok(x >= 12, f"{path}: the title sits {x}px in (was 5)")
        pg.context.close()
    b.close()
print("home, menu and flow:", "all checks passed" if not fails else f"{len(fails)} FAILED: {fails}"); sys.exit(1 if fails else 0)
