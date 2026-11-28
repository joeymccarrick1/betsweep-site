"""The player sheet (owner 11/27 10:34 PM, after FanDuel shipped a "Player Props" sheet: "make the best most efficient legs and show them
why as quickly and as best as it can"): a tap on a name on a leg card opens his lines in place - chart, reasons, and every rung with
the model's chance beside its price - and the page behind keeps its place and its slip.

Everything expected is worked out here from the build's own files, by this file's own code, so the test runs in any week:
  the Parlay Builder's data file  ->  whose name is linked, which stats he is priced in and in what order, every rung's chance, needed
                                       win rate, edge and price, which rung a panel opens on (nearest even money), how many of his
                                       last five cleared each rung, the season count, the risk tag (sweep.py) and the reasons (why.py)
The pages are opened at 390x844 in both themes, the outside world cut off, the clock set a moment after the pages were built.
  python3 tests/player_sheet.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, html, http.server, json, math, os, re, sys, threading, urllib.parse
from playwright.async_api import async_playwright
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); sys.path.insert(0, HERE)
import sweep as SW, why as WHY
from plydata import slugify as slug   # the address rule the player pages are filed under
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8907; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
bh = open(os.path.join(ROOT, "build", "index.html"), encoding="utf-8").read(); _m = re.search(r'src="(/build/data-[0-9a-f]+\.js)"', bh)
js = open(os.path.join(ROOT, _m.group(1).lstrip("/")), encoding="utf-8").read(); BS = json.JSONDecoder().raw_decode(js[js.index("{", js.index("window.__BS = ")):])[0]
W = BS["week"]; GL = BS.get("gl") or {}; KO = {g["gid"]: g.get("ko") or 0 for g in BS["games"]}
try: BUILT = int(re.search(r'id="trends"[^>]*data-built="(\d+)"', open(os.path.join(ROOT, "trends", "index.html"), encoding="utf-8").read()).group(1))
except Exception: BUILT = min([k for k in KO.values() if k] or [0]) - 3600e3
jr = lambda v: int(math.floor(float(v) + 0.5))
key = lambda l: f'{l["pl"]}|{l["m"]}|{jr(l.get("ln") or 1)}'
STATS = [("pass", ("Passing Yards",)), ("ptd", ("Passing TDs",)), ("rush", ("Rushing Yards",)), ("rr", ("Rush + Rec Yards",)), ("recy", ("Receiving Yards",)), ("rec", ("Receptions",)),
         ("long", ("Longest Reception",)), ("td", ("Anytime TD", "2+ TD", "3+ TD", "First TD"))]
STAT_OF = {m: s for s, ms in STATS for m in ms}; MS = dict(STATS)
ORDER = {"QB": ["pass", "ptd", "rush", "td"], "RB": ["rush", "rr", "recy", "rec", "td", "long"]}; REST = ["recy", "rec", "td", "long", "rush", "rr"]
def need_of(l): m = l["m"]; return None if m == "First TD" else 2 if m == "2+ TD" else 3 if m == "3+ TD" else 1 if m.endswith("TD") else float(l["ln"])

def am(o): o = int(math.floor(float(o) + 0.5)); return f"+{o}" if o > 0 else f"\u2212{-o}"
def dec(o): o = float(o); return 1 + o / 100 if o > 0 else 1 + 100 / -o
def books_of(l):
    """the buttons the rung on the chart should carry, read off the builder's own leg: [book, words, id the link must carry, best?] -
    FanDuel with its price; DraftKings and Hard Rock with theirs at the same rung, or marked as a nearest line when they do not post it"""
    out = []; bks = l.get("bks") or {}; ba = l.get("ba") or {}
    ex = {b: bks[b] for b in ("dk", "hr") if (bks.get(b) or {}).get("s")}
    top = max([("fd", dec(l["o"]))] + [(b, dec(v["o"])) for b, v in ex.items() if v.get("o")], key=lambda t: (t[1], t[0] == "fd"))[0]
    if (l.get("fd") or {}).get("u"): out.append(["fdb", "FanDuel " + am(l["o"]), l["fd"]["u"], top == "fd" and bool(bks)])
    for b, lab in (("dk", "DK"), ("hr", "HR")):
        if b in ex: out.append([b + "b", lab + (" " + am(ex[b]["o"]) if ex[b].get("o") is not None else ""), str(ex[b]["s"]), top == b])
        elif (ba.get(b) or {}).get("s"): out.append([b + "b", lab + "\u2248", str(ba[b]["s"]), False])
    return out
def books_ok(s, row):
    """the sheet shows one group of book buttons, the chosen rung's, and it is the builder's"""
    want = row["books"] or []; got = s["books"]
    if not want: return not got
    if len(got) != 1 or got[0]["k"] != row["k"] or len(got[0]["a"]) != len(want): return False
    for a, w in zip(got[0]["a"], want):
        cl = a["cls"].split(); href = urllib.parse.unquote(a["href"] or "")
        if w[0] not in cl or a["t"] != w[1] or ("best" in cl) != w[3] or not a["shown"] or a["h"] < 38 or not a["fits"] or not a["blank"]: return False
        if (href != w[2]) if w[0] == "fdb" else (w[2] not in href): return False
    return True

def expected():
    """{player: {"chips": [stat ids], "rows": {stat: [row...]}, "open": {stat: key of the rung the panel opens on}}} - this file's own reading
    of the rule in psheet.py's header: overs and touchdowns of single players with a game log, a chip a stat in the position's order"""
    by = {}
    for l in BS["legs"]:
        if l.get("gl") or l.get("u") or str(l["m"]).startswith("Under ") or l["m"] not in STAT_OF or l["pl"] not in GL: continue
        by.setdefault(l["pl"], []).append(l)
    out = {}
    for pl, legs in by.items():
        order = list(ORDER.get(legs[0].get("pos") or "", REST)); order += [s for s, _ in STATS if s not in order]
        e = {"chips": [], "rows": {}, "open": {}, "g": legs[0]["g"]}
        for s in order:
            ls = sorted([l for l in legs if STAT_OF[l["m"]] == s], key=lambda l: (MS[s].index(l["m"]), float(l.get("ln") or 0)))
            if not ls: continue
            e["chips"].append(s); rows = []
            for l in ls:
                need = need_of(l); games = [g for g in GL[pl] if g.get(l.get("sk")) is not None][:5] if l.get("sk") else []
                ed = l.get("e") or 0; er = int(math.floor(abs(ed) * 100 + 0.5)) * (1 if ed >= 0 else -1)
                sn = next((h[1] for h in (l.get("fh") or []) if h[0] in ("good", "info", "bad") and "/" in str(h[1]) and str(h[1]).endswith("this season")), "")
                rows.append({"k": key(l), "l": l, "need": need, "books": books_of(l) if need is not None else None, "m": f'{l["p"] * 100:.0f}%', "n": f'{l["bk"] * 100:.0f}%' if l.get("bk") else "—", "e": ((f"{er:+d}" if er else "0") if l.get("bk") else "—"),
                             "px": (f'+{int(l["o"])}' if l["o"] > 0 else f'{int(l["o"])}'), "hits": (sum(1 for g in games if float(g[l["sk"]] or 0) >= need), len(games)) if need is not None else None,
                             "vals": [float(g[l["sk"]] or 0) for g in games][::-1], "sn": sn, "risk": SW.risk_tag(SW.risk_score(l, BS)) if need is not None else "", "why": [tuple(r) for r in WHY.reasons(l, BS.get("pf"))] if need is not None else []})
            e["rows"][s] = rows
            c = [r for r in rows if r["need"] is not None]
            if c: e["open"][s] = min(c, key=lambda r: (abs((r["l"].get("bk") if r["l"].get("bk") is not None else 0.5) - 0.5), float(r["l"].get("ln") or 0)))["k"]
        if e["chips"]: out[pl] = e
    return out

READ = """() => { var s = document.querySelector('.psh'); if(!s) return null; var r = s.getBoundingClientRect(), root = s.querySelector('.pshroot'), inn = s.querySelector('.pshin');
  var p = root ? root.querySelector('.pshp:not([hidden])') : null, h5 = p ? p.querySelector('.h5') : null, vis = function(e){ return !!(e && (e.offsetWidth || e.offsetHeight)); };
  var why = p ? Array.from(p.querySelectorAll('.pshwhy:not([hidden]) .legwhy li')).map(function(li){ var b = li.querySelector('b'), sp = li.querySelector('span'); return [li.className, b.textContent, sp.textContent.replace(b.textContent, '').trim()]; }) : [];
  return {rect: [r.left, r.top, r.right, r.bottom], vw: innerWidth, vh: innerHeight, over: inn ? inn.scrollWidth - inn.clientWidth : 0, role: s.getAttribute('role'), label: s.getAttribute('aria-label') || '', loaded: !!root,
    name: root ? root.querySelector('#pshname').textContent : '', sub: root ? root.querySelector('.pshwho p').textContent : '', week: root ? +root.getAttribute('data-week') : 0, ko: root ? root.classList.contains('pshko') : null,
    konote: root ? vis(root.querySelector('.pshkonote')) : null, full: root ? root.querySelector('a.pshfull').getAttribute('href') : '',
    chips: root ? Array.from(root.querySelectorAll('.pshchips button')).map(function(b){ return [b.getAttribute('data-st'), b.classList.contains('on'), b.getAttribute('aria-pressed')]; }) : [],
    panels: root ? Array.from(root.querySelectorAll('.pshp')).map(function(x){ return [x.getAttribute('data-st'), !x.hidden]; }) : [],
    st: p ? p.getAttribute('data-st') : '', title: p && p.querySelector('.pshmk b') ? p.querySelector('.pshmk b').textContent : '', risk: p && vis(p.querySelector('.pshrk')) ? p.querySelector('.pshrk').textContent : '', why: why,
    rows: p ? Array.from(p.querySelectorAll('.pshr')).map(function(tr){ var a = tr.querySelector('a.more'), b = tr.querySelector('.pshln'), ar = a.getBoundingClientRect(), br = b ? b.getBoundingClientRect() : null;
      return {k: tr.getAttribute('data-k'), on: tr.classList.contains('on'), m: tr.querySelector('.pshm').textContent, n: tr.querySelector('.pshn').textContent, e: tr.querySelector('.pshe').textContent, px: (a.getAttribute('data-px') || a.textContent).trim(),
        shown: vis(a), ah: Math.round(ar.height), aw: Math.round(ar.width), fits: ar.right <= r.right + 0.5, bh: br ? Math.round(br.height) : null, sel: !!b, inslip: a.classList.contains('inslip'), pressed: a.getAttribute('aria-pressed')}; }) : [],
    h5: h5 ? {big: h5.querySelector('p b').textContent, cap: h5.querySelector('p').textContent.replace(/\\s+/g, ' '), ov: h5.querySelectorAll('li.ov').length, n: h5.querySelectorAll('li').length, aria: h5.getAttribute('aria-label') || '',
      sn: (function(){ var x = h5.querySelector('p small:not(.vs)'); return x && vis(x) ? x.textContent : ''; })(),
      vals: Array.from(h5.querySelectorAll('li .v')).map(function(x){ return x.textContent; }), bars: Array.from(h5.querySelectorAll('li .b')).map(function(x){ return parseFloat(x.style.height); }),
      frac: (function(){ var l = h5.querySelector('.ln'), m = l ? /\\*\\s*([0-9.]+)\\)/.exec(l.style.bottom || '') : null; return m ? +m[1] : null; })(), lnVis: vis(h5.querySelector('.ln'))} : null,
    books: p ? Array.from(p.querySelectorAll('.pshbks')).filter(function(d){ return vis(d); }).map(function(d){ return {k: d.getAttribute('data-k'), a: Array.from(d.querySelectorAll('a')).map(function(a){ var q = a.getBoundingClientRect();
      return {cls: a.className, t: a.textContent, href: a.getAttribute('href'), shown: vis(a), h: Math.round(q.height), fits: q.right <= r.right + 0.5 && q.left >= r.left - 0.5, blank: a.target === '_blank'}; })}; }) : [],
    lock: document.documentElement.classList.contains('pshopen'), state: !!(history.state && history.state.bsPsh)}; }"""

async def main():
    EXP = expected()
    have = {pl: os.path.exists(os.path.join(ROOT, "player", slug(pl), "sheet.json")) for pl in EXP}
    pages = {pl: os.path.exists(os.path.join(ROOT, "player", slug(pl), "index.html")) for pl in EXP}
    print(f"   week {W}: {len(EXP)} players with over or touchdown lines and a game log; {sum(have.values())} sheets on the site")
    if not EXP:
        check(True, "no player lines on this board: nothing to check"); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(0)
    check(all(have[pl] for pl in EXP if pages[pl]) and sum(have.values()) > 0, f"every such player with a page has a sheet beside it ({sum(have.values())} of {sum(pages.values())}; missing: {[pl for pl in EXP if pages[pl] and not have[pl]][:4]})")
    extra = [d for d in os.listdir(os.path.join(ROOT, "player")) if os.path.exists(os.path.join(ROOT, "player", d, "sheet.json")) and d not in {slug(pl) for pl in EXP}]
    check(not extra, f"and nobody else has one ({extra[:4]})")
    bad = []
    for pl in EXP:
        if not have[pl]: continue
        try:
            j = json.load(open(os.path.join(ROOT, "player", slug(pl), "sheet.json"), encoding="utf-8"))
            ks = re.findall(r'<tr class="pshr[^"]*" data-k="([^"]*)"', j["html"]); want = [r["k"] for s in EXP[pl]["chips"] for r in EXP[pl]["rows"][s]]
            if j.get("week") != W or j.get("name") != pl or [html.unescape(k) for k in ks] != want: bad.append((pl, j.get("week"), len(ks), len(want)))
        except Exception as x: bad.append((pl, str(x)[:80]))
    check(not bad, f"each sheet is this week's, carries his name, and lists exactly his rungs in ladder order ({len(EXP)} sheets; first wrong: {bad[:3]})")

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); srv.handle_error = lambda *a: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    def chart_ok(s, r):
        """the open panel's chart against rung r: the five games, which of them clear it, the bars' heights and where the line sits"""
        h = s["h5"]
        if not (r["hits"] and r["hits"][1] >= 2): return not h
        if not h: return False
        top = (max(max(r["vals"]), r["need"]) * 1.12) or 1
        return (h["big"] == f'{r["hits"][0]} of {r["hits"][1]}' and h["ov"] == r["hits"][0] and h["n"] == r["hits"][1] and f'in {r["hits"][0]} of {r["hits"][1]}.' in h["aria"] and h["sn"] == r["sn"] and h["lnVis"]
                and h["vals"] == [str(jr(v)) for v in r["vals"]] and all(abs(b - max(7, v / top * 100)) <= 1.01 for b, v in zip(h["bars"], r["vals"])) and h["frac"] is not None and abs(h["frac"] - r["need"] / top) <= 0.0002)
    NAME = """() => { Array.from(document.querySelectorAll('article.play[data-pst]')).forEach(function(p){ p.removeAttribute('data-pst'); });   /* numbers handed out by an earlier call, on another tab's cards */
        var c = Array.from(document.querySelectorAll('article.play')).filter(function(p){ return p.offsetParent !== null && p.querySelector('.who a[href^="/player/"]') && p.querySelector('a.more[href^="/build/?add="]'); });
        return c.map(function(p, i){ p.setAttribute('data-pst', i); var a = p.querySelector('a.more[href^="/build/?add="]'); return {i: i, name: p.querySelector('.who a').textContent.trim(), href: p.querySelector('.who a').getAttribute('href'), k: new URL(a.getAttribute('href'), location.origin).searchParams.get('add')}; }); }"""
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def open_(path, theme, clock, wide=False, block_sheet=False):
            ctx = await b.new_context(viewport={"width": 1200, "height": 800} if wide else {"width": 390, "height": 844}, device_scale_factor=1 if wide else 2, is_mobile=not wide, has_touch=not wide, service_workers="block", color_scheme=theme)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}};(function(){{var T={int(clock)},R=Date.now,S=R();window.__setT=function(t){{T=t;S=R();}};Date.now=function(){{return T+(R()-S)}};}})();")
            async def gate(route, request):
                if "127.0.0.1" not in request.url: await route.abort()
                elif block_sheet and request.url.endswith("/sheet.json"): await route.fulfill(status=404, body="")
                else: await route.continue_()
            await ctx.route("**/*", gate)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}{path}", wait_until="domcontentloaded"); await pg.wait_for_timeout(1900)
            return pg, ctx, errs
        async def tap_name(pg, i):
            await pg.evaluate("(i) => { var a = document.querySelector('article.play[data-pst=\"' + i + '\"] .who a'); a.scrollIntoView({block: 'center'}); }", i); await pg.wait_for_timeout(150)
            y = await pg.evaluate("scrollY"); await pg.tap(f'article.play[data-pst="{i}"] .who a'); await pg.wait_for_timeout(700); return y
        def ladder(c):
            """a card worth testing the ladder on: three or more rungs in its stat, and one of them with a different count over his last five"""
            rows = EXP[c["name"]]["rows"].get(STAT_OF.get(c["k"].split("|")[1], ""), []); mine = next((r for r in rows if r["k"] == c["k"]), None)
            return bool(mine and mine["need"] is not None and len(rows) >= 3 and any(r["need"] is not None and r["hits"] != mine["hits"] for r in rows))
        async def pick_tab(pg, k=None):
            """Trend check shows one group at a time: the cards of the first group that holds leg k (or, with no k, a card with a ladder to test; failing that, any card)"""
            first = []
            for i in range(await pg.evaluate("document.querySelectorAll('#wktabs .tab').length") or 1):
                await pg.evaluate("(i) => { var t = document.querySelectorAll('#wktabs .tab')[i]; if(t) t.click(); document.querySelectorAll('.trgrp:not(.fxoff) .trmore').forEach(function(b){ if(b.offsetParent !== null) b.click(); }); }", i); await pg.wait_for_timeout(250)
                cs = [c for c in await pg.evaluate(NAME) if c["name"] in EXP and have.get(c["name"])]
                if (k and any(c["k"] == k for c in cs)) or (not k and any(ladder(c) for c in cs)): return cs
                first = first or cs
            return first
        T0 = BUILT + 1000
        # Today shows legs only on a game day before kickoff: three hours ahead of the next game that has lines (never before the build)
        T_TD = max(T0, min([KO[e["g"]] for e in EXP.values() if (KO.get(e["g"]) or 0) > T0] or [T0]) - 3 * 3600e3)
        for theme in ("light", "dark"):
            # ---- Trend check: the card's own rung opens, the ladder is the builder's, the chart recounts on a tap ----
            pg, ctx, errs = await open_("/trends/", theme, T0)
            cards = await pick_tab(pg)
            if not cards:
                check(True, f"[{theme}] no card with a linked name is on Trend check right now: the sheet is checked from the other pages"); await ctx.close()
            else:
                # a card whose stat has several rungs, so the ladder has something to move to
                c = next((c for c in cards if ladder(c)), cards[0]); e = EXP[c["name"]]; st = STAT_OF.get(c["k"].split("|")[1], "")
                if theme == "light": print(f"   Trend check card used: {c['k']} ({len(e['rows'][st])} rungs in that stat, {len(e['chips'])} stats)")
                url0 = await pg.evaluate("location.href"); y0 = await tap_name(pg, c["i"]); s = await pg.evaluate(READ)
                check(bool(s) and s["loaded"] and s["role"] == "dialog" and c["name"] in s["label"] and s["name"] == c["name"] and s["week"] == W and s["lock"] and not errs,
                      f"[{theme}] a tap on {c['name']}'s name opens his sheet, a labelled dialog, this week's ({(s or {}).get('label')!r}; {errs[:1]})")
                if not (s and s["loaded"]): await ctx.close(); continue
                y1 = await pg.evaluate("scrollY"); url1 = await pg.evaluate("location.href")
                check(url1 == url0 and abs(y1 - y0) <= 1 and s["rect"][0] >= -0.5 and s["rect"][2] <= s["vw"] + 0.5 and s["rect"][3] <= s["vh"] + 0.5 and s["rect"][1] >= s["vh"] * 0.08 and s["over"] <= 0,
                      f"[{theme}] the page behind has not moved or changed address, and the sheet sits inside the screen with nothing cut off sideways (top {s['rect'][1]:.0f} of {s['vh']}, overflow {s['over']})")
                check([x[0] for x in s["chips"]] == e["chips"] or (len(e["chips"]) == 1 and not s["chips"]), f"[{theme}] a chip for each stat he is priced in, his position's main stat first ({[x[0] for x in s['chips']]} vs {e['chips']})")
                check(s["st"] == st and [x for x in s["panels"] if x[1]] == [[st, True]] and [r["k"] for r in s["rows"] if r["on"]] == [c["k"]],
                      f"[{theme}] it opens on the stat and the rung of the card that was tapped ({s['st']}, {[r['k'] for r in s['rows'] if r['on']]} vs {c['k']})")
                rows = e["rows"][st]; got = [(r["k"], r["m"], r["n"], r["e"], r["px"].replace("−", "-")) for r in s["rows"]]; want = [(r["k"], r["m"], r["n"], r["e"], r["px"]) for r in rows]
                check(got == want, f"[{theme}] the ladder is every rung the builder prices in that stat, each with the model's chance, the needed win rate, the edge and FanDuel's price ({len(got)} rows; first wrong: {next(((g, w) for g, w in zip(got, want) if g != w), None)})")
                check(all(r["shown"] and r["ah"] >= 36 and r["aw"] >= 80 and r["fits"] for r in s["rows"]) and all((r["bh"] or 0) >= 38 for r in s["rows"] if r["sel"]), f"[{theme}] every price and every rung is a thumb-sized button inside the sheet ({[(r['ah'], r['aw'], r['bh']) for r in s['rows']][:3]})")
                sel = next(r for r in rows if r["k"] == c["k"])
                check(chart_ok(s, sel) and s["risk"] == sel["risk"] and [tuple(w) for w in s["why"]] == sel["why"],
                      f"[{theme}] for that rung: his last five counted against it ({(s['h5'] or {}).get('big')} vs {sel['hits']}), the season count, the builder's risk tag ({s['risk']!r} vs {sel['risk']!r}) and why.py's reasons ({len(s['why'])} vs {len(sel['why'])})")
                # ---- owner 11/28 1:38 AM ("other ways we can beat fanduel"): the rung on the chart can go straight to a book, each with its own price ----
                check(books_ok(s, sel), f"[{theme}] under the chart, that rung at each book: FanDuel's price and link, DraftKings' and Hard Rock's own, the best one marked, thumb-sized ({[(a['t'], a['cls']) for g in s['books'] for a in g['a']]} vs {[(w[1], w[3]) for w in sel['books'] or []]})")
                # ---- another rung: the one with a different count if there is one, else the last ----
                oth = next((r for r in rows if r["need"] is not None and r["k"] != c["k"] and r["hits"] != sel["hits"]), next((r for r in reversed(rows) if r["need"] is not None and r["k"] != c["k"]), None))
                if oth:
                    await pg.evaluate("(k) => { Array.from(document.querySelectorAll('.pshp:not([hidden]) .pshr')).filter(function(r){ return r.getAttribute('data-k') === k; })[0].querySelector('.pshln').click(); }", oth["k"]); await pg.wait_for_timeout(450)
                    s2 = await pg.evaluate(READ)
                    check([r["k"] for r in s2["rows"] if r["on"]] == [oth["k"]] and chart_ok(s2, oth) and s2["risk"] == oth["risk"] and [tuple(w) for w in s2["why"]] == oth["why"],
                          f"[{theme}] a tap on another rung ({oth['k'].split('|')[-1]}) moves the chart to it - bars rescaled, line moved, {(s2['h5'] or {}).get('big')} (expected {oth['hits']}), tag {s2['risk']!r}, its own reasons")
                    check(s2["title"] != s["title"] or oth["k"] == c["k"], f"[{theme}] and the heading names the rung on the chart ({s2['title']!r})")
                    check(books_ok(s2, oth), f"[{theme}] and the book buttons are that rung's now ({[(a['t'], a['cls']) for g in s2['books'] for a in g['a']]} vs {[(w[1], w[3]) for w in oth['books'] or []]})")
                # ---- the price is the add button, for the sheet and for the card behind it ----
                await pg.evaluate("(k) => { Array.from(document.querySelectorAll('.pshp:not([hidden]) .pshr')).filter(function(r){ return r.getAttribute('data-k') === k; })[0].querySelector('a.more').click(); }", c["k"]); await pg.wait_for_timeout(300)
                s3 = await pg.evaluate(READ); slip = await pg.evaluate("(w) => { try { return JSON.parse(localStorage.getItem('bs_slipk_w' + w) || '[]'); } catch(e){ return null; } }", W)
                card_in = await pg.evaluate("(i) => document.querySelector('article.play[data-pst=\"' + i + '\"] a.more[href^=\"/build/?add=\"]').classList.contains('inslip')", c["i"])
                r3 = next(r for r in s3["rows"] if r["k"] == c["k"])
                check(slip == [c["k"]] and r3["inslip"] and r3["pressed"] == "true" and card_in and await pg.evaluate("location.href") == url0, f"[{theme}] a tap on a price adds that rung to the slip without leaving the page, and the card behind shows it too (slip {slip})")
                await pg.evaluate("(k) => { Array.from(document.querySelectorAll('.pshp:not([hidden]) .pshr')).filter(function(r){ return r.getAttribute('data-k') === k; })[0].querySelector('a.more').click(); }", c["k"]); await pg.wait_for_timeout(250)
                slip = await pg.evaluate("(w) => JSON.parse(localStorage.getItem('bs_slipk_w' + w) || '[]')", W)
                check(slip == [], f"[{theme}] a second tap takes it out again (slip {slip})")
                # ---- another chip ----
                if len(e["chips"]) > 1:
                    o = next(x for x in e["chips"] if x != st)
                    await pg.evaluate("(s) => document.querySelector('.pshchips button[data-st=\"' + s + '\"]').click()", o); await pg.wait_for_timeout(250); s4 = await pg.evaluate(READ)
                    orow = next((r for r in e["rows"][o] if r["k"] == e["open"].get(o)), None)
                    check(s4["st"] == o and [x for x in s4["panels"] if x[1]] == [[o, True]] and [x[0] for x in s4["chips"] if x[1]] == [o] and [r["k"] for r in s4["rows"]] == [r["k"] for r in e["rows"][o]]
                          and (orow is None or ([r["k"] for r in s4["rows"] if r["on"]] == [orow["k"]] and chart_ok(s4, orow))),
                          f"[{theme}] another chip ({o}) shows that stat alone, opened on the rung priced nearest even money ({[r['k'].split('|')[-1] for r in s4['rows'] if r['on']]} vs {e['open'].get(o, '').split('|')[-1]})")
                if SHOTS: await pg.evaluate("(s) => { var b = document.querySelector('.pshchips button[data-st=\"' + s + '\"]'); if(b) b.click(); }", st); await pg.wait_for_timeout(250); await pg.screenshot(path=os.path.join(SHOTS, f"player_sheet_{theme}.png"))
                # ---- shut: the X, the back gesture, Escape, the backdrop ----
                await pg.tap(".pshx"); await pg.wait_for_timeout(350)
                z = await pg.evaluate("() => ({open: !!document.querySelector('.psh'), lock: document.documentElement.classList.contains('pshopen'), url: location.href, y: scrollY, state: !!(history.state && history.state.bsPsh), focus: document.activeElement ? document.activeElement.textContent.trim() : ''})")
                check(not z["open"] and not z["lock"] and z["url"] == url0 and abs(z["y"] - y0) <= 1 and not z["state"] and z["focus"] == c["name"], f"[{theme}] the X shuts it: same address, same place on the page, focus back on his name ({z})")
                await tap_name(pg, c["i"]); await pg.go_back(); await pg.wait_for_timeout(350)
                z = await pg.evaluate("() => ({open: !!document.querySelector('.psh'), url: location.href, y: scrollY})")
                check(not z["open"] and z["url"] == url0 and abs(z["y"] - y0) <= 1, f"[{theme}] the phone's back gesture shuts it and stays on the page ({z})")
                await tap_name(pg, c["i"]); await pg.keyboard.press("Escape"); await pg.wait_for_timeout(350); o1 = await pg.evaluate("!!document.querySelector('.psh')")
                await tap_name(pg, c["i"]); await pg.mouse.click(195, 30); await pg.wait_for_timeout(350); o2 = await pg.evaluate("!!document.querySelector('.psh')")
                check(not o1 and not o2 and await pg.evaluate("location.href") == url0 and not errs, f"[{theme}] Escape shuts it, and so does a tap on the page behind ({o1}, {o2}; {errs[:1]})")
                # ---- his full page takes the sheet's place in the history: Back returns here with the sheet shut ----
                await tap_name(pg, c["i"]); await pg.tap("a.pshfull"); await pg.wait_for_load_state("domcontentloaded"); await pg.wait_for_timeout(500); u = await pg.evaluate("location.pathname")
                await pg.go_back(); await pg.wait_for_timeout(900); z = await pg.evaluate("() => ({open: !!document.querySelector('.psh'), url: location.href})")
                check(u == c["href"] and z["url"] == url0 and not z["open"], f"[{theme}] the link at the foot opens his full page ({u}), and Back returns to the list with the sheet shut ({z})")
                await ctx.close()
                # ---- a game that has kicked off sells nothing ----
                pg, ctx, errs = await open_("/trends/", theme, T0); cards2 = [x for x in await pick_tab(pg, c["k"]) if x["k"] == c["k"]]
                if cards2:
                    await pg.evaluate("(t) => window.__setT(t)", KO[e["g"]] + 60e3)
                    await pg.evaluate("(i) => document.querySelector('article.play[data-pst=\"' + i + '\"] .who a').click()", cards2[0]["i"]); await pg.wait_for_timeout(700); s5 = await pg.evaluate(READ)
                    check(bool(s5) and s5["loaded"] and s5["ko"] and s5["konote"] and not any(r["shown"] for r in s5["rows"]) and not s5["books"] and not errs, f"[{theme}] a minute after his game kicks off the sheet offers no price and says the game has started ({errs[:1]})")
                await ctx.close()
                # ---- no sheet to load: his page opens, and Back does not land on a dead step ----
                pg, ctx, errs = await open_("/trends/", theme, T0, block_sheet=True); cards3 = [x for x in await pick_tab(pg, c["k"]) if x["k"] == c["k"]]
                if cards3:
                    url0 = await pg.evaluate("location.href"); await tap_name(pg, cards3[0]["i"]); await pg.wait_for_load_state("domcontentloaded"); await pg.wait_for_timeout(600); u = await pg.evaluate("location.pathname")
                    await pg.go_back(); await pg.wait_for_timeout(900); z = await pg.evaluate("() => ({open: !!document.querySelector('.psh'), url: location.href})")
                    check(u == c["href"] and z["url"] == url0 and not z["open"], f"[{theme}] with no sheet to load, the tap opens his page instead ({u}), and Back returns to the list ({z})")
                await ctx.close()
            # ---- the same tap on Today and on Model's Best ----
            for path, label in (("/", "Today"), ("/best/", "Model's Best")):
                pg, ctx, errs = await open_(path, theme, T_TD if path == "/" else T0)
                if path == "/":   # Today keeps a game's legs behind its "More on this game" button: open the first game that still has one
                    await pg.evaluate("() => { var b = Array.from(document.querySelectorAll('.tdgame .tdtog')).filter(function(x){ return x.offsetParent !== null && x.closest('.tdgame').querySelector('.tdmore .play .who a[href^=\"/player/\"]'); })[0]; if(b) b.click(); }"); await pg.wait_for_timeout(350)
                cs = [c for c in await pg.evaluate(NAME) if c["name"] in EXP and have.get(c["name"])]
                if not cs:
                    check(True, f"[{theme}] {label} shows no card with a linked name right now"); await ctx.close(); continue
                c = cs[0]; e = EXP[c["name"]]; st = STAT_OF.get(c["k"].split("|")[1], ""); y0 = await tap_name(pg, c["i"]); s = await pg.evaluate(READ)
                kk = [r["k"] for r in (s or {}).get("rows", []) if r["on"]]; row = next((r for r in e["rows"].get(st, []) if r["k"] == c["k"]), None)
                want_on = [c["k"]] if (row and row["need"] is not None) else ([e["open"][st]] if st in e["open"] else kk)   # an under or a First TD card has no rung of its own to open on
                check(bool(s) and s["loaded"] and s["name"] == c["name"] and (not st or st not in e["chips"] or s["st"] == st) and (kk == want_on or not row) and s["over"] <= 0 and s["rect"][3] <= s["vh"] + 0.5 and abs(await pg.evaluate("scrollY") - y0) <= 1 and not errs,
                      f"[{theme}] {label}: the same tap opens {c['name']}'s sheet on the card's stat and rung ({(s or {}).get('st')}, {kk}; {errs[:1]})")
                if SHOTS and s: await pg.screenshot(path=os.path.join(SHOTS, f"player_sheet_{'today' if path == '/' else 'best'}_{theme}.png"))
                await ctx.close()
        # ---- a wide screen: a centred box, not a full-width band ----
        pg, ctx, errs = await open_("/trends/", "dark", T0, wide=True); cs = await pick_tab(pg)
        if cs:
            await pg.evaluate("(i) => document.querySelector('article.play[data-pst=\"' + i + '\"] .who a').click()", cs[0]["i"]); await pg.wait_for_timeout(700); s = await pg.evaluate(READ)
            wdt = s["rect"][2] - s["rect"][0] if s else 0
            check(bool(s) and s["loaded"] and 400 <= wdt <= 640 and abs((s["rect"][0] + s["rect"][2]) / 2 - s["vw"] / 2) <= 2 and s["rect"][1] > 20 and s["rect"][3] < s["vh"] - 20 and not errs, f"on a wide screen the sheet is a centred box ({wdt:.0f} wide at {s['rect'][0]:.0f}, top {s['rect'][1]:.0f}; {errs[:1]})")
            # a click with Ctrl held is left alone: the name is still a plain link
            await pg.keyboard.press("Escape"); await pg.wait_for_timeout(250)
            n0 = len(ctx.pages); await pg.click(f'article.play[data-pst="{cs[0]["i"]}"] .who a', modifiers=["Control"]); await pg.wait_for_timeout(600)
            check(not await pg.evaluate("!!document.querySelector('.psh')"), f"a click with Ctrl held opens no sheet: the name stays a plain link ({len(ctx.pages) - n0} new tab)")
        await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
