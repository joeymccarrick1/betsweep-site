#!/usr/bin/env python3
"""tests/menu_ask.py - Ask BetSweep in the menu of every page, Theme on My BetSweep, the Short view on the home page only
(owner 11/11 12:15 AM: "Can ask betsweep just be on the Menu? I'd want this on the menu of every page. And then it doesn't have to be
actually on any page itself it can just be in the menu. Also put theme in My Betsweep rather than the menu. Put short view access just
on the home page not in the menu."). ask.py, rechrome.py, build_site.py sitenav(), account.py.

  BASE=http://localhost:8803 SITE=/tmp/clonecopy python3 tests/menu_ask.py
SITE is a built site served at BASE - best the scratch copy of the live clone after reprice.copy_into_clone (RUNBOOK), because only
that has the older pages (receipts, /season/, last weeks' short links) whose menus rechrome.py refreshes. Non-local requests are
blocked; the account library and the alerts function are stubbed.
"""
import glob, json, os, re, sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8802"); SITE = os.environ.get("SITE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site"))
fails = []
def ok(c, name, extra=""):
    print(("ok  " if c else "FAIL"), name, extra)
    if not c: fails.append(name)

# ---------------- the files ----------------
pages = {}
for d, dirs, fs in os.walk(SITE):
    dirs[:] = [x for x in dirs if x not in (".git", "node_modules", "lab", "posts", "promo-slips")]
    for f in fs:
        if f.endswith(".html"): pages[os.path.relpath(os.path.join(d, f), SITE).replace(os.sep, "/")] = open(os.path.join(d, f), encoding="utf-8", errors="ignore").read()
menus = {p: re.search(r'<nav class="sitenav".*?</nav>', t, re.S).group(0) for p, t in pages.items() if 'id="sitenav"' in t}
ok(len(menus) > 400, "pages with the site menu", f"{len(menus)} of {len(pages)} html files")
bad = [p for p, m in menus.items() if m.count('id="navask"') != 1 or pages[p].count('id="navask"') != 1]
ok(not bad, "every one of them has Ask BetSweep in its menu, once", str(bad[:8]))
bad = [p for p, m in menus.items() if 'class="thm' in m or ">Theme<" in m]
ok(not bad, "no menu carries the Theme switch", str(bad[:8]))
bad = [p for p, m in menus.items() if "/short/" in m]
ok(not bad, "no menu links the Short view", str(bad[:8]))
short = sorted(p for p, t in pages.items() if 'href="/short/"' in t and 'http-equiv="refresh"' not in t[:800])
ok(short == ["index.html"], "the Short view is linked from the home page and nowhere else", str(short[:8]))
apps = sorted({x for t in pages.values() for x in re.findall(r"/s/app-[0-9a-f]+\.js", t)}); css = sorted({x for p in menus for x in re.findall(r"/s/site-[0-9a-f]+\.css", pages[p])})
ok(len(apps) == 1 and len(css) == 1, "one shared script and one shared stylesheet across the whole site", f"{apps} {css}")
bad = [p for p, t in pages.items() if 'id="tdask"' in t or 'id="askform"' in t or 'class="askbox"' in t or 'id="askq"' in t]
ok(not bad, "no page carries an ask box of its own", str(bad[:8]))
ok("askAnswer" not in pages.get("build/index.html", "x") and "ASKM" not in pages.get("build/index.html", "x"), "the Parlay Builder's own ask box is gone")
ok('class="thm methm"' in pages.get("me/index.html", ""), "My BetSweep carries the Theme buttons")
ptr = json.load(open(os.path.join(SITE, "b", "ask.json"))); src = os.path.join(SITE, ptr["src"].lstrip("/"))
ok(os.path.exists(src), "/b/ask.json points at a file that is there", ptr["src"])
raw = open(src, encoding="utf-8").read(); D = json.loads(raw[raw.index("{"):raw.rindex("}") + 1]); W = D["week"]
ok(raw.startswith("window.__BS = ") and ptr.get("week") == W and ptr["src"] in pages["build/index.html"], "it is the Parlay Builder's own data file, this week's", f"week {W}, {len(D['legs'])} legs")
LEGS = [l for l in D["legs"] if not l.get("gl")]; G = {g["gid"]: g for g in D["games"]}
eg = re.search(r'id="navask" data-eg="([^"]*)" data-team="([^"]*)"', menus["boards/index.html"]); EG, TEAM = (eg.group(1), eg.group(2)) if eg else ("", "")
m = re.match(r"(.+) (\d+)\+ (.+)$", EG); egleg = None
if m: egleg = next((l for l in LEGS if l["pl"] == m.group(1) and round(l["ln"]) == int(m.group(2)) and str(l.get("ms", "")).lower() == m.group(3)), None)
ok(bool(egleg), "the example in the hint is a leg on this week's board", EG)
ok(any(TEAM in (g.get("na"), g.get("nb")) for g in D["games"]), "and the team in it plays this week", TEAM)
KEY = f'{egleg["pl"]}|{egleg["m"]}|{int(egleg["ln"] + 0.5)}' if egleg else ""
PL = json.load(open(os.path.join(SITE, "b", "players.json")))
onboard = {l["pl"] for l in LEGS}
nolines = next((p for p in PL if p["n"] not in onboard and p.get("o") and p["o"] != "BYE" and "-".join(sorted([p["t"], p["o"]])) in G and sum(1 for q in PL if q["n"].split()[-1] == p["n"].split()[-1]) == 1 and len(p["n"].split()) == 2), None)

STUB = """window.supabase = {createClient: function(){ var sess = window.__TEST_SESSION || null;
  function chain(){ var p = Promise.resolve({data: [], error: null}); var h = {get: function(t, k){ if(k === 'then') return p.then.bind(p); if(k === 'catch') return p.catch.bind(p); return function(){ return new Proxy({}, h); }; }}; return new Proxy({}, h); }
  return {auth: {getSession: function(){ return Promise.resolve({data: {session: sess}}); }, onAuthStateChange: function(){ return {data: {subscription: {unsubscribe: function(){}}}}; }, signOut: function(){ return Promise.resolve(); }}, from: function(){ return chain(); }}; }};"""

with sync_playwright() as pw:
    b = pw.chromium.launch()
    def page(path, when=None, w=390, h=844, session=None):
        c = b.new_context(viewport={"width": w, "height": h}, is_mobile=w < 600, has_touch=w < 600); pg = c.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        def route(r):
            u = r.request.url
            if u.startswith(BASE): return r.continue_()
            if "supabase" in u and u.endswith(".js"): return r.fulfill(status=200, content_type="application/javascript", body=STUB)
            if "/functions/v1/slip-alerts" in u: return r.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"}, body=json.dumps({"a": "Written answer for: " + (json.loads(r.request.post_data or "{}").get("q") or ""), "left": 19}))
            return r.abort()
        pg.route("**/*", route)
        if session: pg.add_init_script("window.__TEST_SESSION = " + json.dumps(session) + ";")
        if when: pg.clock.install(time=when)
        pg.goto(BASE + path, wait_until="load"); pg.wait_for_timeout(900); return pg, errs
    def ask(pg, q, wait=1200):
        pg.fill("#navaskq", q); pg.press("#navaskq", "Enter"); pg.wait_for_timeout(wait)
        return pg.evaluate("document.getElementById('navaskout').innerText")
    OUT = "document.getElementById('navaskout')"

    # ---- a phone, on a page that is not the builder ----
    pg, errs = page("/news/")
    ok(pg.evaluate("getComputedStyle(document.querySelector('#sitenav .tabs')).display") == "none", "phone: the menu starts closed")
    pg.click("#sitenav .menu"); pg.wait_for_timeout(250)
    tops = pg.evaluate("(function(){ var a = document.getElementById('navask').getBoundingClientRect(), t = document.querySelector('#sitenav .tabs > a').getBoundingClientRect(), i = document.getElementById('navaskq'); return {ask: a.top, first: t.top, vis: a.height > 60, font: parseFloat(getComputedStyle(i).fontSize), h: i.getBoundingClientRect().height, label: getComputedStyle(document.querySelector('#navask label')).position, hint: document.querySelector('.navaskh').innerText}; })()")
    ok(tops["vis"] and tops["ask"] < tops["first"], "phone: Ask BetSweep is the first thing in the open menu", str(tops))
    ok(tops["font"] >= 16 and tops["h"] >= 44 and tops["label"] == "static", "phone: a 16px field (no zoom on focus), a 44px target, the label showing")
    ok(EG in tops["hint"] and TEAM in tops["hint"], "phone: the hint names this week's example", tops["hint"])
    if egleg:
        txt = ask(pg, EG, 2200)
        want = [("+" if egleg["o"] > 0 else "") + str(egleg["o"]), f'{round(egleg["p"] * 100)}%', ("+" if egleg["e"] >= 0 else "") + f'{egleg["e"] * 100:.1f}']
        ok(egleg["pl"] in txt and all(x in txt for x in want), "the example gets its card: FanDuel price, model chance and edge are the board's", f"{want} | {txt[:140]!r}".replace("\n", " "))
        ok(f"Week {W} board" in txt and str(D.get("built")) in txt, "the answer says which board it read", txt.split("\n")[0])
        ok(pg.evaluate(f"!!{OUT}.querySelector('.naadd') && {OUT}.querySelector('.naslip').hidden"), "Add to slip is offered; no betslip link while the slip is empty")
        pg.click("#navaskout .naadd"); pg.wait_for_timeout(300)
        st = pg.evaluate(f"({{slip: localStorage.getItem('bs_slipk_w{W}'), btn: {OUT}.querySelector('.naadd').textContent, pressed: {OUT}.querySelector('.naadd').getAttribute('aria-pressed'), link: {OUT}.querySelector('.naslip').hidden ? '' : {OUT}.querySelector('.naslip').textContent, path: location.pathname}})")
        ok(json.loads(st["slip"] or "[]") == [KEY] and "In your slip" in st["btn"] and st["pressed"] == "true" and st["link"] == "Open betslip (1)" and st["path"] == "/news/", "Add to slip puts the leg in the shared slip and stays on the page", str(st))
        pg.click("#navaskout .naadd"); pg.wait_for_timeout(300)
        st = pg.evaluate(f"({{slip: localStorage.getItem('bs_slipk_w{W}'), btn: {OUT}.querySelector('.naadd').textContent, hidden: {OUT}.querySelector('.naslip').hidden}})")
        ok(json.loads(st["slip"] or "[]") == [] and st["btn"] == "Add to slip" and st["hidden"], "a second tap takes it out again", str(st))
        last = egleg["pl"].split()[-1]
        txt = ask(pg, last + " " + str(egleg["ms"]).lower())
        ok(egleg["pl"] in txt and "FANDUEL" in txt.upper(), "last name and a stat finds him too", txt[:120].replace("\n", " | "))
    txt = ask(pg, TEAM); g = next(x for x in D["games"] if TEAM in (x.get("na"), x.get("nb")))
    links = pg.evaluate(f"[].map.call({OUT}.querySelectorAll('.nab a'), function(a){{ return a.getAttribute('href'); }})")
    ok(f'{g.get("away") or g["a"]} at {g.get("home") or g["b"]}' in txt and f'/boards/#{g["gid"]}' in links and f'/dossier/{g["gid"]}/' in links, "a team name gets its game, with the board and the preview", str(links))
    if nolines:
        txt = ask(pg, nolines["n"].split()[-1] + " rec yds"); href = pg.evaluate(f"({OUT}.querySelector('.nab a') || {{getAttribute: function(){{ return ''; }}}}).getAttribute('href')")
        ok(nolines["n"] in txt and "no lines for him" in txt and href == f'/player/{nolines["s"]}/' and os.path.exists(os.path.join(SITE, "player", nolines["s"], "index.html")) and not pg.evaluate(f"!!{OUT}.querySelector('.naadd')"),
           "a player with nothing on the board: says so, links his page, offers no leg", f'{nolines["n"]}: {txt[:110]!r}'.replace("\n", " "))
    # two players on the board who share a last name -> the choice, not a guess
    by_last = {}
    for n in onboard: by_last.setdefault(n.split()[-1], set()).add(n)
    both = next((sorted(v) for k, v in sorted(by_last.items()) if len(v) > 1 and all(len(x.split()) == 2 for x in v)), None)
    if both:
        txt = ask(pg, both[0].split()[-1]); picks = pg.evaluate(f"[].map.call({OUT}.querySelectorAll('.napick'), function(a){{ return a.textContent; }})")
        ok("Which one?" in txt and all(n in picks for n in both), "a last name two players on the board share: both are offered", f"{both} -> {picks}")
        pg.click("#navaskout .napick"); pg.wait_for_timeout(500); ok(picks[0] in pg.evaluate(f"{OUT}.innerText") and "Which one?" not in pg.evaluate(f"{OUT}.innerText"), "tapping one answers for him")
    else: print("note: no shared last name on this week's board; that check is skipped")
    txt = ask(pg, "qqq zzz"); ok("No player or team" in txt and EG in txt, "a question it cannot read says so and names the example", txt[:130].replace("\n", " | "))
    tiers = [l for l in LEGS if l.get("tier")]
    txt = ask(pg, "best"); ok("Model's Best" in txt and (not tiers or any(l["pl"] in txt for l in tiers)), "'best' lists Model's Best legs from the board", txt[:120].replace("\n", " | "))
    # the written answer: a signed-out visitor is asked to sign in, not sent anywhere
    pg.click("#navaskout .namgo"); pg.wait_for_timeout(300)
    ok("free account" in pg.evaluate(f"{OUT}.querySelector('.namout').innerText"), "written answer, signed out: asks for a free account", pg.evaluate(f"{OUT}.querySelector('.namout').innerText")[:90])
    if pg.evaluate(f"!!{OUT}.querySelector('.namin')"):
        pg.click("#navaskout .namin"); pg.wait_for_timeout(300); ok(pg.evaluate("!!document.querySelector('.bsdlg') && !document.querySelector('.bsdlg').hidden"), "and its Sign in button opens the sign-in box")
    ok(pg.evaluate("(function(){ var a = document.querySelector('#sitenav .tabs a.mme'); return !!a && a.getAttribute('href') === '/me/'; })()"), "signed out: the menu has a line to My BetSweep (where Theme lives)")
    ok(pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth") and not errs, "phone: no sideways scroll, no script errors", str(errs)[:200])
    pg.context.close()

    # ---- a link with ?ask= opens the menu with the answer, on any page (and the builder's old links) ----
    for path in ("/teams/?ask=" + TEAM, "/build/?ask=" + TEAM):
        pg, errs = page(path); st = pg.evaluate(f"({{open: document.getElementById('sitenav').classList.contains('open'), q: document.getElementById('navaskq').value, txt: {OUT}.innerText}})")
        ok(st["open"] and st["q"] == TEAM and " at " in st["txt"] and not errs, f"{path.split('?')[0]}?ask=... opens the menu with the answer", st["txt"][:70].replace("\n", " | ")); pg.context.close()

    # ---- the builder: no box in the page; the menu adds to the builder's own slip without a reload ----
    if egleg:
        pg, errs = page("/build/"); pg.evaluate("window.__mark = 1")
        ok(pg.evaluate("!document.getElementById('ask') && !document.querySelector('.askbox') && typeof window.bsSlipToggle === 'function'"), "builder: no ask box in the page")
        pg.click("#sitenav .menu"); pg.wait_for_timeout(200); ask(pg, EG, 900); pg.click("#navaskout .naadd"); pg.wait_for_timeout(400)
        st = pg.evaluate(f"({{has: window.bsSlipHas({json.dumps(KEY)}), n: window.bsSlipCount(), mark: window.__mark, btn: {OUT}.querySelector('.naadd').textContent, stored: localStorage.getItem('bs_slipk_w{W}')}})")
        ok(st["has"] and st["n"] == 1 and st["mark"] == 1 and "In your slip" in st["btn"] and KEY in (st["stored"] or ""), "builder: Add to slip from the menu lands in the builder's slip, no reload", str(st))
        pg.click("#navaskout .naslip"); pg.wait_for_timeout(250)
        ok(not pg.evaluate("document.getElementById('sitenav').classList.contains('open')") and pg.evaluate("location.pathname") == "/build/", "builder: Open betslip closes the menu (the slip is this page's)")
        ok(not errs, "builder: no script errors", str(errs)[:200]); pg.context.close()
        # after his game kicks off the board is closed for him
        ko = (G[egleg["g"]]["ko"] + 60000) / 1000
        pg, errs = page("/news/", when=ko); pg.click("#sitenav .menu"); txt = ask(pg, EG, 2000)
        ok("kicked off" in txt and not pg.evaluate(f"!!{OUT}.querySelector('.naadd')"), "after kickoff: no leg is offered for a game under way", txt[:120].replace("\n", " | ")); pg.context.close()

    # ---- the home page: no ask section; the Short view button is there ----
    pg, errs = page("/")
    st = pg.evaluate("({ask: !!document.getElementById('tdask') || !!document.getElementById('askform'), pill: (function(){ var a = document.getElementById('tdsimple'); return a ? [a.textContent.trim(), a.getAttribute('href'), a.offsetParent !== null] : null; })()})")
    ok(not st["ask"] and st["pill"] == ["Short view", "/short/", True] and not errs, "home: no Ask section; the Short view button is on the page", str(st)); pg.context.close()

    # ---- Theme on My BetSweep ----
    pg, errs = page("/me/")
    st = pg.evaluate("(function(){ var g = document.querySelector('.me .thm'); var r = g.getBoundingClientRect(); return {n: g.querySelectorAll('button[data-thm]').length, on: [].map.call(g.querySelectorAll('button.on'), function(b){ return b.textContent; }), top: r.top, nav: !!document.querySelector('.sitenav .thm')}; })()")
    ok(st["n"] == 3 and st["on"] == ["Auto"] and st["top"] < 500 and not st["nav"], "My BetSweep: Theme (Auto / Dark / Light) near the top of the page, not in the menu", str(st))
    pg.click('.me .thm button[data-thm="dark"]'); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.getAttribute('data-theme') === 'dark' && localStorage.getItem('bs_theme') === 'dark'"), "Dark is applied and kept")
    pg.goto(BASE + "/boards/", wait_until="load"); pg.wait_for_timeout(300); dark = pg.evaluate("[document.documentElement.getAttribute('data-theme'), getComputedStyle(document.body).backgroundColor]")
    pg.goto(BASE + "/me/", wait_until="load"); pg.wait_for_timeout(300); pg.click('.me .thm button[data-thm="auto"]'); pg.wait_for_timeout(200)
    ok(dark[0] == "dark" and pg.evaluate("document.documentElement.getAttribute('data-theme') === null && localStorage.getItem('bs_theme') === null") and not errs, "other pages follow it; Auto clears it", str(dark)); pg.context.close()

    # ---- a wide screen: one row, the answer in a panel under the box ----
    for w in (1241, 1366):
        for who, sess in (("signed out", None), ("signed in", {"access_token": "t", "user": {"id": "u1", "email": "tester@example.com"}})):
            pg, errs = page("/boards/", w=w, h=860, session=sess)
            st = pg.evaluate("(function(){ var n = document.getElementById('sitenav'), i = document.getElementById('navaskq').getBoundingClientRect(); return {h: n.getBoundingClientRect().height, over: document.documentElement.scrollWidth - window.innerWidth, input: Math.round(i.width), right: Math.round(i.right), acct: document.getElementById('bsacct').innerText.replace(/\\s+/g, ' ').trim(), tops: [].map.call(n.querySelectorAll('.tabs > *'), function(k){ return k.offsetParent === null ? null : Math.round(k.getBoundingClientRect().height); }).filter(function(x){ return x !== null; })}; })()")
            ok(st["h"] <= 56 and st["over"] <= 0 and st["input"] >= 104 and st["right"] <= w and max(st["tops"]) <= 50, f"{w}px, {who}: the menu is one row with the ask box in it", str(st))
            if w == 1366 and not sess:
                pg.click("#navaskq"); pg.wait_for_timeout(150); ok(pg.evaluate("getComputedStyle(document.querySelector('.navaskh')).display") == "block", "wide: the hint shows under the box while it has focus")
                ask(pg, EG or TEAM, 1500); r = pg.evaluate(f"(function(){{ var o = {OUT}.getBoundingClientRect(); return {{pos: getComputedStyle({OUT}).position, l: o.left, r: o.right, t: o.top, w: o.width, hint: getComputedStyle(document.querySelector('.navaskh')).display}}; }})()")
                ok(r["pos"] == "absolute" and r["l"] >= 0 and r["r"] <= w and r["t"] > 40 and r["w"] >= 380 and r["hint"] == "none", "wide: the answer is a panel under the box, inside the screen", str(r))
                pg.mouse.click(200, 600); pg.wait_for_timeout(150); ok(pg.evaluate(f"{OUT}.hidden"), "wide: a click elsewhere puts it away")
            if sess and w == 1366:
                pg.click("#navaskq"); ask(pg, TEAM, 1500); pg.click("#navaskout .namgo"); pg.wait_for_timeout(500)
                ok("Written answer for: " + TEAM in pg.evaluate(f"{OUT}.querySelector('.namout').innerText") and "19 questions left" in pg.evaluate(f"{OUT}.querySelector('.namout').innerText"), "signed in: the written answer comes back under the board's answer")
                ok(not pg.evaluate("!!document.querySelector('#sitenav .tabs a.mme')"), "signed in: no second My BetSweep line in the menu (the header has it)")
            ok(not errs, f"{w}px, {who}: no script errors", str(errs)[:200]); pg.context.close()

    # ---- the pages the build did not make: same menu, and it works there ----
    older = [p for p in ("receipts/week6/index.html", "receipts/week8/index.html", "b/w8-1/index.html", "b/w9-1/index.html", "season/index.html", "receipts/week9/index.html") if p in pages]
    if not older: print("note: SITE has no older pages (receipts, /season/, old short links); run against the scratch copy of the clone to check them")
    for p in older:
        path = "/" + p[:-len("index.html")]; pg, errs = page(path); pg.click("#sitenav .menu"); pg.wait_for_timeout(250)
        groups = pg.evaluate("[].map.call(document.querySelectorAll('#sitenav .ddb'), function(b){ return b.textContent.replace(/[^A-Za-z]/g, ''); })")
        txt = ask(pg, TEAM, 2000); st = pg.evaluate("({over: document.documentElement.scrollWidth - window.innerWidth, navh: document.querySelector('#sitenav .in').getBoundingClientRect().height, tabs: getComputedStyle(document.querySelector('.apptabs')).display})")
        ok(groups == ["Games", "Betting", "Play", "Players", "Fantasy", "Results"] and " at " in txt and st["over"] <= 0 and st["navh"] <= 60 and st["tabs"] == "flex" and not errs, f"older page {path}: this build's menu, Ask answers, nothing broken", f"{groups} {st} {str(errs)[:120]}")
        pg.context.close()
    b.close()
print("menu ask:", "all checks passed" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
