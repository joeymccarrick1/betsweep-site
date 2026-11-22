"""/nba/ - NBA Matchup Boards, the first page beyond the NFL (owner 11/22 3:27 PM: "Let's start adding nba, college football, and epl.
I want each sport to basically look exactly like everything we've built for NFL."). A PREVIEW: not in the menu, not in the sitemap.

The page ships the board it was drawn from (/nba/board.json, written by sports/nba/publish.py in the feeds-sports job). This test
redoes the page from that file - every score, every out, every player row, his chips, his chances and his last games - so a number on
the page that the board does not carry cannot pass. It also checks the things that make it "look like the NFL boards": the NFL boards'
own stylesheet and markup (scorecards first, two view buttons, a tap to open a player), on a 390x844 phone in light and dark and on a
desktop. And the rule for the small NBA-only publish (reprice.nba_changed / copy_only).

Serves SITE (default ./site).   python3 tests/nba_board.py [shots_dir]
With no /nba/ page in the build (the feed has no board) the test says so and passes: the page is optional, a stale one is not.
"""
import asyncio, json, os, re, sys, tempfile, shutil, threading, http.server, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); TREE = os.path.join(HERE, "..")
ROOT = os.environ.get("SITE") or os.path.join(TREE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8882
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
f1 = lambda x: "–" if x is None else f"{x:.1f}"
NUM = re.compile(r"\d+(?:\.\d+)?")
def same(a, b, tol=0.051):
    na, nb = NUM.findall(a or ""), NUM.findall(b or "")
    return NUM.sub("#", a or "") == NUM.sub("#", b or "") and len(na) == len(nb) and all(abs(float(x) - float(y)) <= tol for x, y in zip(na, nb))


def publish_rule():
    """reprice.nba_changed and copy_only, on made-up folders"""
    sys.path.insert(0, TREE)
    import reprice as R
    keep = (R.SITE, R.OUT)
    d = tempfile.mkdtemp()
    try:
        R.SITE, R.OUT = os.path.join(d, "site"), os.path.join(d, "out"); clone = os.path.join(d, "clone")
        for x in (os.path.join(R.SITE, "nba"), os.path.join(R.SITE, "s"), os.path.join(R.SITE, "boards"), R.OUT, os.path.join(clone, "s"), os.path.join(clone, "boards"), os.path.join(clone, ".github")):
            os.makedirs(x)
        open(os.path.join(R.SITE, "nba", "index.html"), "w").write('<link href="/s/site-aaaaaa1111.css"><script src="/s/app-bbbbbb2222.js"></script><link href="/s/tpl-cccccc3333.css">new nba')
        for f in ("site-aaaaaa1111.css", "app-bbbbbb2222.js", "tpl-cccccc3333.css", "site-unrelated99.css"): open(os.path.join(R.SITE, "s", f), "w").write(f)
        open(os.path.join(R.SITE, "boards", "index.html"), "w").write("new boards"); open(os.path.join(clone, "boards", "index.html"), "w").write("live boards")
        open(os.path.join(clone, "s", "tpl-cccccc3333.css"), "w").write("already there"); open(os.path.join(clone, ".github", "x"), "w").write("job")
        check(R.nba_changed(clone) is False, "no NBA board in the build: nothing to publish for it")
        json.dump({"sig": "A"}, open(os.path.join(R.OUT, "nba_sig.json"), "w"))
        check(R.nba_changed(clone) is True, "a board when the live site has none yet: changed")
        os.makedirs(os.path.join(clone, "nba")); json.dump({"sig": "A"}, open(os.path.join(clone, "nba", "sig.json"), "w")); open(os.path.join(clone, "nba", "old.txt"), "w").write("x")
        check(R.nba_changed(clone) is False, "the same board as the live one: not changed")
        json.dump({"sig": "B"}, open(os.path.join(R.OUT, "nba_sig.json"), "w"))
        check(R.nba_changed(clone) is True, "a different board (a new day, an out, a point): changed")
        done = R.copy_only(clone, ["nba", ".github", "missing"])
        got = sorted(os.listdir(os.path.join(clone, "s")))
        check(done == ["nba"] and open(os.path.join(clone, "nba", "index.html")).read().endswith("new nba") and not os.path.exists(os.path.join(clone, "nba", "old.txt")), "the small publish replaces /nba/ and nothing else is named done")
        check(got == ["app-bbbbbb2222.js", "site-aaaaaa1111.css", "tpl-cccccc3333.css"] and open(os.path.join(clone, "s", "tpl-cccccc3333.css")).read() == "already there",
              f"it brings the shared files the page links that the live site lacks, leaves one it has, and no others ({got})")
        check(open(os.path.join(clone, "boards", "index.html")).read() == "live boards" and open(os.path.join(clone, ".github", "x")).read() == "job", "the NFL pages and the jobs folder are not touched")
    finally:
        R.SITE, R.OUT = keep; shutil.rmtree(d, ignore_errors=True)


def stale_rule():
    """build_nba.usable: which boards are drawn"""
    import datetime as dt
    import build_nba as N
    now = dt.datetime(2026, 11, 23, 2, 30, tzinfo=dt.timezone.utc)      # Sunday 8:30 PM Central
    good = {"format": N.FORMAT, "day": "2026-11-22", "games": [{}], "players": [{}]}
    check(N.nba_day(now) == "2026-11-22" and N.nba_day(dt.datetime(2026, 11, 23, 8, 30, tzinfo=dt.timezone.utc)) == "2026-11-22" and N.nba_day(dt.datetime(2026, 11, 23, 10, 30, tzinfo=dt.timezone.utc)) == "2026-11-23",
          "the NBA day is the Central date four hours ago: 8:30 PM and 2:30 AM are still Sunday's slate, 4:30 AM is Monday's")
    check(N.usable(good, now)[0] and N.usable(dict(good, day="2026-11-24"), now)[0], "a board for today, or for the next day with games, is drawn")
    r = [N.usable(None, now), N.usable(dict(good, format=1), now), N.usable({k: v for k, v in good.items() if k != "format"}, now), N.usable(dict(good, games=[]), now), N.usable(dict(good, day="2026-11-21"), now)]
    check(not any(x[0] for x in r) and all(x[1] for x in r), f"no board, a board in another shape, one with no games, and one for a day already over are not drawn, each with its reason (e.g. {r[4][1][:60]}...)")
    check(N.usable(dict(good, day="2026-11-21"), now, any_day=True)[0], "a board file named by hand is drawn whatever its day (tests and local work)")


def expect(B):
    """what the page must show, from the board alone"""
    ranks = {}
    for g in ("G", "F", "C"):
        for i, p in enumerate(sorted([p for p in B["players"] if p["grp"] == g], key=lambda p: -(p["proj"].get("pts") or 0))): ranks[p["id"]] = i + 1
    games = []
    for g in B["games"]:
        a, h = g["away"], g["home"]; pa, ph = g["proj"].get(a), g["proj"].get(h)
        fav, by = (a, pa - ph) if pa >= ph else (h, ph - pa)
        line = g.get("line") or {}
        cols = {}
        for ab in (a, h):
            t = B["teams"][ab]; ps = sorted([p for p in B["players"] if p["team"] == ab], key=lambda p: -(p["proj"].get("pts") or 0))
            cols[ab] = {"def": [f"{x}#{(t['opp_def'].get(x) or {}).get('pts', [None])[0]}" for x in ("G", "F", "C") if (t.get("opp_def") or {}).get(x)], "out": [o["name"] for o in t.get("out") or []], "back": list(t.get("back") or []),
                        "players": [[p["id"], p["name"], p["grp"], f"~{round(p['min'])} min", f1(p["proj"].get("pts")), f"#{ranks[p['id']]} {p['grp']}", (p.get("status") or {}).get("tag") or ""] for p in ps]}
        games.append({"key": g["key"], "a": a, "h": h, "score": f"{pa:.1f}–{ph:.1f}", "small": f"total {pa + ph:.1f} · " + ("even" if round(by, 1) == 0 else f"{fav} by {by:.1f}"), "tip": g["tipct"] + " CT",
                      "line": " · ".join(x for x in ((line.get("details") or ""), (f"O/U {line['total']:g}" if isinstance(line.get("total"), (int, float)) else "")) if x), "by": (line.get("by") or "").replace("Draft Kings", "DraftKings"),
                      "state": g.get("state") if g.get("state") in ("in", "post") and g.get("score") else None, "cols": cols, "nout": sum(len(B["teams"][x].get("out") or []) for x in (a, h))})
    return games, ranks


READ = r"""(function(){
  var tx = function(e){ return e ? e.textContent.replace(/\s+/g, ' ').trim() : ''; };
  return [...document.querySelectorAll('.grid > .card[id]:not(.summary)')].map(function(c){
    var cols = {}; c.querySelectorAll('ul.col').forEach(function(u){
      cols[u.getAttribute('data-team')] = {def: [...u.querySelectorAll('.dsum .dm')].map(function(d){ return tx(d.querySelector('.dl')) + tx(d.querySelector('b')); }),
        out: [...u.querySelectorAll('.inj:not(.nbback) em')].map(function(e){ return tx(e).replace(tx(e.querySelector('small')), '').trim(); }),
        back: [...u.querySelectorAll('.inj.nbback em')].map(function(e){ return tx(e).replace(tx(e.querySelector('small')), '').trim(); }),
        players: [...u.querySelectorAll('li.pl')].map(function(li){ var nm = li.querySelector('.nm'), tag = nm.querySelector('.nbtag'), v = li.querySelector('.ppr .v');
          return [li.getAttribute('data-pid'), tx(nm).replace(tag ? tx(tag) : '', '').trim(), tx(li.querySelector('.pos')), tx(li.querySelector('.role')), v.childNodes[1].textContent.trim(), tx(li.querySelector('.rk')), tag ? tx(tag) : '']; })};
    });
    var mk = c.querySelector('.ginfo .mkt'), by = mk && mk.querySelector('small'), st = c.querySelector('.nbstate');
    return {key: c.id, a: tx(c.querySelector('.tm.a b')), h: tx(c.querySelector('.tm.b b')), score: [...c.querySelectorAll('.score .pt')].map(tx).join('–'), small: tx(c.querySelector('.score small')), tip: tx(c.querySelector('.ginfo .gk')),
      line: mk ? tx(mk).replace(by ? tx(by) : '', '').trim() : '', by: by ? tx(by) : '', state: st ? (st.classList.contains('s-post') ? 'post' : 'in') : null, cols: cols,
      nout: parseInt(tx(c.querySelector('.vbtn[data-view="out"] small')) || '0', 10), ko: c.getAttribute('data-ko')};
  });
})()"""


async def main():
    publish_rule(); stale_rule()
    page_path = os.path.join(ROOT, "nba", "index.html")
    if not os.path.exists(page_path):
        check(not os.path.exists(os.path.join(ROOT, "nba", "board.json")), "this build has no NBA board, so it has no /nba/ page and no leftover board file (the page is optional; a stale one is not allowed)")
        print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
    src = open(page_path, encoding="utf-8").read()
    B = json.load(open(os.path.join(ROOT, "nba", "board.json")))
    want, ranks = expect(B)
    import build_nba as N, datetime as dt
    check(B.get("format") == N.FORMAT, f"the board is in the shape the page reads (format {B.get('format')})")
    check(B.get("sport") == "nba" and len(B["games"]) >= 1 and len(B["players"]) >= 10 * len(B["games"]) and B.get("data_through") and B.get("day"), f"the page ships its board: {B.get('day_label')}, {len(B['games'])} games, {len(B['players'])} players, games through {B.get('data_through')}")
    check(all(p["team"] in B["teams"] and p["game"] in {g["id"] for g in B["games"]} and p["min"] >= 12 and all(p["proj"].get(k) is not None for k in ("pts", "reb", "ast", "fg3")) for p in B["players"]), "every player on the board has a team, a game, 12+ minutes and all four projections")
    outs = {(ab, o["name"]) for ab, t in B["teams"].items() for o in t.get("out") or []}
    check(not any((p["team"], p["name"]) in outs for p in B["players"]) and all(o.get("tag") in ("Out", "Doubtful") for t in B["teams"].values() for o in t.get("out") or []), "nobody listed out or doubtful has a projection")
    # ---- a preview: reachable by its address only
    sm = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, "sitemap.xml")) else ""
    linkers = []
    for rel in ("index.html", "boards/index.html", "build/index.html", "stocks/index.html", "social/index.html"):
        fp = os.path.join(ROOT, rel)
        if os.path.exists(fp) and re.search(r'href="/nba/?"', open(fp, encoding="utf-8", errors="ignore").read()): linkers.append(rel)
    check("/nba/" not in sm and not linkers, f"it is a preview: not in the sitemap, and no other page or menu links to it ({linkers})")
    check("NBA preview" in src and "Model numbers only" in src and "FanDuel prices are not connected yet" in src and "being graded" in src, "the page says it is a preview: model numbers only, no FanDuel prices yet, graded before anything is a pick")
    body = re.sub(r"<style.*?</style>|<script.*?</script>", "", src, flags=re.S)
    cards_html = body[body.find('<div class="grid">'):]
    check(not re.search(r"\b(best bet|best parlay|lock|edge|value|\+EV)\b", re.sub(r"<[^>]+>", " ", cards_html[:cards_html.find('class="nbstamp"')]), re.I) and "sportsbook.fanduel.com" not in cards_html,
          "no card calls anything a best bet, an edge or value, and none links to a sportsbook")
    tpl = re.search(r"<style[^>]*>(.*?)</style>", open(os.path.join(TREE, "template.html"), encoding="utf-8").read(), re.S).group(1)
    shared = re.findall(r'/s/(tpl-[0-9a-f]+\.css)', src)
    check(bool(shared) and os.path.exists(os.path.join(ROOT, "s", shared[0])) and ".card{" in open(os.path.join(ROOT, "s", shared[0]), encoding="utf-8").read() or tpl[:400] in src, "it wears the NFL boards' own stylesheet")

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme, vw, vh, phone in (("light", 390, 844, True), ("dark", 390, 844, True), ("dark", 1280, 900, False)):
            T = lambda s: f"[{theme} {'phone' if phone else 'desktop'}] {s}"
            ctx = await b.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=2 if phone else 1, is_mobile=phone, has_touch=phone)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            await ctx.route("**/*supabase*/**", lambda r: r.abort()); await ctx.route("**/site.api.espn.com/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/nba/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1200)
            got = await pg.evaluate(READ)
            if theme == "light":   # the content is the same in every theme: read it once
                check([g["key"] for g in got] == [g["key"] for g in want], f"one card a game, in the board's order ({', '.join(g['key'] for g in got)})")
                bad = [(g["key"], k, g[k], w[k]) for g, w in zip(got, want) for k in ("a", "h", "tip", "line", "by", "state", "nout") if g[k] != w[k]] + [(g["key"], k, g[k], w[k]) for g, w in zip(got, want) for k in ("score", "small") if not same(g[k], w[k])]
                check(not bad, f"each card's teams, model score, total and margin, tip time, posted line with the book named, state and count of outs are the board's" + (f" (off: {bad[:2]})" if bad else f" (e.g. {got[0]['a']} {got[0]['score']} {got[0]['h']}, {got[0]['small']}; {got[0]['line']} {got[0]['by']})"))
                badc = [(g["key"], ab, k) for g, w in zip(got, want) for ab in w["cols"] for k in ("def", "out", "back") if (g["cols"].get(ab) or {}).get(k) != w["cols"][ab][k]]
                check(not badc, "each team's column: what the opponent allows to guards, forwards and centers, who is out tonight and who is back, as the board has them" + (f" (off: {badc[:3]})" if badc else ""))
                badp = []
                for g, w in zip(got, want):
                    for ab in w["cols"]:
                        gp, wp = (g["cols"].get(ab) or {}).get("players") or [], w["cols"][ab]["players"]
                        if len(gp) != len(wp): badp.append((g["key"], ab, len(gp), len(wp))); continue
                        badp += [(g["key"], x, y) for x, y in zip(gp, wp) if x[:4] != y[:4] or not same(x[4], y[4]) or x[5:] != y[5:]]
                n = sum(len(c["players"]) for w in want for c in w["cols"].values())
                check(not badp and n == len(B["players"]), f"all {n} players are on the page once, highest projected points first in each team, each with his position, minutes, points, tonight's rank at his position and his injury tag" + (f" (off: {badp[:2]})" if badp else ""))
            # ---- scorecards first; a tap opens a game
            st = await pg.evaluate("""(function(){ var cs = [...document.querySelectorAll('.grid > .card[id]:not(.summary)')], c = cs[0], vb = [...c.querySelectorAll('.vbtn')];
              return {compact: document.body.classList.contains('compact'), shown: cs.filter(function(x){ return x.querySelector('.cols').getClientRects().length; }).length, vb: vb.map(function(x){ var r = x.getBoundingClientRect(); return [x.textContent.replace(/\\s+/g, ' ').trim(), r.height, r.top, r.width]; }),
                over: document.documentElement.scrollWidth - innerWidth, h: document.documentElement.scrollHeight / innerHeight, first: cs[0].getBoundingClientRect().top, sw: [...document.querySelectorAll('.nbsw a')].map(function(a){ return [a.textContent, a.getAttribute('href'), a.getAttribute('aria-current')]; }),
                font: getComputedStyle(c.querySelector('.tm b')).fontFamily, sum: document.querySelector('.card.summary .sumgrid').getClientRects().length}; })()""")
            multi = len(want) > 1
            check(st["compact"] == multi and st["shown"] == (0 if multi else 1) and st["over"] <= 0, T(f"scorecards first, as on the NFL boards: {len(want)} games, none opened, no sideways scroll, page {st['h']:.1f} screens long"))
            check(len(st["vb"]) == 2 and st["vb"][0][0] == "Projections" and st["vb"][1][0].startswith("Who's out") and min(v[1] for v in st["vb"]) >= 38 and abs(st["vb"][0][2] - st["vb"][1][2]) < 2 and abs(st["vb"][0][3] - st["vb"][1][3]) < 3,
                  T(f"each card has two equal buttons, Projections and Who's out ({st['vb'][0][1]:.0f}px tall)"))
            check(st["sw"] == [["NFL", "/boards/", None], ["NBA", "/nba/", "page"]], T("a sport switch sits above the cards: NFL (to the NFL boards) and NBA (this page)"))
            k0 = want[0]["key"]; w0 = want[0]
            await pg.click(f'#{k0} .vbtn[data-view="proj"]'); await pg.wait_for_timeout(350)
            o = await pg.evaluate("""(function(k){ var c = document.getElementById(k), r = c.querySelectorAll('li.pl'), f = r[0], b = f.querySelector('.prow').getBoundingClientRect(), bar = f.querySelector('.ppr i'), ibar = getComputedStyle(bar).getPropertyValue('--w');
              return {exp: c.classList.contains('expanded'), view: c.getAttribute('data-view'), rows: [...r].filter(function(x){ return x.getClientRects().length; }).length, rowh: b.height, top: c.getBoundingClientRect().top, w: parseFloat(ibar), det: f.querySelector('.pdetail').hidden,
                pressed: getComputedStyle(c.querySelector('.vbtn[data-view="proj"]')).backgroundColor !== getComputedStyle(c.querySelector('.vbtn[data-view="out"]')).backgroundColor, over: document.documentElement.scrollWidth - innerWidth}; })""", k0)
            nrows = sum(len(c["players"]) for c in w0["cols"].values())
            check(o["exp"] and o["view"] == "proj" and o["rows"] == nrows and o["det"] and o["pressed"] and o["over"] <= 0 and 40 <= o["top"] <= 260, T(f"Projections opens the game: {nrows} player rows, the button shown pressed, the card at the top of the screen"))
            check(o["rowh"] >= 44 and abs(o["w"] - 100) < 0.2, T(f"a player's row is {o['rowh']:.0f}px tall to tap, and the game's top scorer has the full bar"))
            # ---- a player opened: chips, chances, last games - all from the board
            tm = w0["a"]; pid = w0["cols"][tm]["players"][0][0]; P = next(p for p in B["players"] if p["id"] == pid); od = B["teams"][tm]["opp_def"].get(P["grp"], {})
            await pg.click(f'#{k0} li.pl[data-pid="{pid}"] .prow'); await pg.wait_for_timeout(250)
            d = await pg.evaluate(r"""(function(pid){ var li = document.querySelector('li.pl[data-pid="' + pid + '"]'), dd = li.querySelector('.pdetail'), tx = function(e){ return e ? e.textContent.replace(/\s+/g, ' ').trim() : ''; };
              return {hidden: dd.hidden, exp: li.querySelector('.prow').getAttribute('aria-expanded'), chips: [...dd.querySelectorAll('.sl .sc')].map(function(c){ return [tx(c.querySelector('small')), tx(c.querySelector('b')), tx(c.querySelector('.mu i')), tx(c.querySelector('.fd'))]; }),
                lad: [...dd.querySelectorAll('.nblad li')].map(function(l){ return [tx(l.querySelector('span')), [...l.querySelectorAll('em')].map(tx)]; }), rec: [...dd.querySelectorAll('.nbl5 tbody tr')].map(function(r){ return [...r.children].map(tx); }),
                flags: [...dd.querySelectorAll('.flags .fg')].map(tx), over: document.documentElement.scrollWidth - innerWidth, wide: dd.scrollWidth - dd.clientWidth}; })""", pid)
            labs = [("pts", "points", "Points"), ("reb", "rebounds", "Rebounds"), ("ast", "assists", "Assists"), ("fg3", "threes", "Threes")]
            wchips = [[lab, f1(P["proj"].get(k)), (f"{w0['h'] if tm == w0['a'] else w0['a']} #{od[k][0]}" if od.get(k) else ""), f"avg {f1(P['avg'].get(k))}" + (f" last 10: {f1(P['l10'].get(k))}" if P["l10"].get(k) is not None else "")] for k, lab, _ in labs]
            okc = len(d["chips"]) == 4 and all(a[0] == w[0] and same(a[1], w[1]) and a[2] == w[2] and same(a[3], w[3]) for a, w in zip(d["chips"], wchips))
            check(not d["hidden"] and d["exp"] == "true" and okc and d["over"] <= 0 and d["wide"] <= 1, T(f"{P['name']} opened: points, rebounds, assists and threes with his average, his last 10, and what the opponent allows to his position ({' | '.join(c[1] + ' ' + c[0] for c in d['chips'])})") + ("" if okc else f" (page {d['chips']}, board {wchips})"))
            wl = []
            for k, _, cap in labs:
                r = sorted(sorted(P["ladder"].get(k) or [], key=lambda x: abs(x[1] - 0.5))[:4], key=lambda x: x[0])
                if r: wl.append([cap, [f"{L}+{round(pr * 100)}%" for L, pr in r]])
            check([[a, [x.replace(" ", "") for x in b]] for a, b in d["lad"]] == wl and all(len(b) <= 4 for _, b in wl), T(f"the chance of each line is the board's, at most four a stat, the ones nearest an even chance ({'; '.join(a + ' ' + ' '.join(b) for a, b in wl[:2])})"))
            check(d["rec"] == [[str(c) for c in g] for g in reversed(P["recent"])], T(f"his last {len(P['recent'])} games are listed newest first, as the board has them"))
            wf = ([P["status"]["tag"]] if P.get("status") else []) + [w.partition(":")[0].strip() for w in P.get("warn") or []]
            check(d["flags"] == wf, T(f"his notes are the board's ({wf or 'none'})"))
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"nba_{theme}_{'phone' if phone else 'desk'}_player.png"))
            # ---- Who's out
            await pg.click(f'#{k0} .vbtn[data-view="out"]'); await pg.wait_for_timeout(300)
            v = await pg.evaluate("""(function(k){ var c = document.getElementById(k); return {view: c.getAttribute('data-view'), exp: c.classList.contains('expanded'), rows: [...c.querySelectorAll('li.pl')].filter(function(x){ return x.getClientRects().length; }).length,
              outs: [...c.querySelectorAll('.inj:not(.nbback) em')].filter(function(x){ return x.getClientRects().length; }).length, none: [...c.querySelectorAll('.nbnoout')].filter(function(x){ return x.getClientRects().length; }).length}; })""", k0)
            check(v["view"] == "out" and v["exp"] and v["rows"] == 0 and v["outs"] == w0["nout"] and v["none"] == sum(1 for ab in (w0["a"], w0["h"]) if not B["teams"][ab].get("out")), T(f"Who's out shows the {w0['nout']} players out for the two teams and no player rows; a team with nobody out says so"))
            await pg.click(f'#{k0} .vbtn[data-view="out"]'); await pg.wait_for_timeout(250)
            check(not await pg.evaluate(f"document.getElementById('{k0}').classList.contains('expanded')"), T("the same button again closes the game"))
            # ---- the Slate card and a jump from it
            await pg.evaluate("window.scrollTo(0, 0)"); await pg.click(".card.summary .hd"); await pg.wait_for_timeout(250)
            s = await pg.evaluate(r"""(function(){ var c = document.querySelector('.card.summary'), tx = function(e){ return e.textContent.replace(/\s+/g, ' ').trim(); }, cols = [...c.querySelectorAll('.sumgrid > div')];
              return {exp: c.classList.contains('expanded'), heads: cols.map(function(x){ return tx(x.querySelector('h3')).replace(tx(x.querySelector('h3 small')), '').trim(); }), games: [...cols[0].querySelectorAll('li a')].map(function(a){ return a.getAttribute('href'); }),
                top: [...cols[1].querySelectorAll('li')].map(function(l){ return [tx(l.querySelector('a')), l.querySelector('a').getAttribute('data-open'), tx(l.querySelector('.bl-m'))]; }), up: [...cols[2].querySelectorAll('li a')].map(function(a){ return a.getAttribute('data-open'); })}; })()""")
            top6 = sorted(B["players"], key=lambda p: -(p["proj"].get("pts") or 0))[:6]; up6 = sorted([p for p in B["players"] if p.get("base_min") and p["min"] - p["base_min"] >= 1.5], key=lambda p: -(p["min"] - p["base_min"]))[:6]
            check(s["exp"] and s["heads"] == ["Tonight", "Top projected scorers", "More minutes tonight"] and s["games"] == ["#" + g["key"] for g in want], T("the Slate card opens to tonight's games, the top projected scorers and whose minutes go up"))
            check([t[1] for t in s["top"]] == [p["id"] for p in top6] and all(same(t[2], f"{f1(p['proj'].get('pts'))} points {round(p['min'])} min") for t, p in zip(s["top"], top6)) and s["up"] == [p["id"] for p in up6],
                  T(f"its lists are the board's: {', '.join(p['name'] + ' ' + f1(p['proj'].get('pts')) for p in top6[:3])}; more minutes for {', '.join(p['name'] for p in up6[:3]) or 'nobody'}"))
            if s["top"]:
                await pg.click(f'.card.summary a[data-open="{s["top"][0][1]}"]'); await pg.wait_for_timeout(500)
                j = await pg.evaluate("""(function(pid){ var li = document.querySelector('li.pl[data-pid="' + pid + '"]'), r = li.getBoundingClientRect(); return {exp: li.closest('.card').classList.contains('expanded'), open: !li.querySelector('.pdetail').hidden, top: r.top, vh: innerHeight}; })""", s["top"][0][1])
                check(j["exp"] and j["open"] and 0 <= j["top"] <= j["vh"] - 100, T(f"tapping {s['top'][0][0]} in the Slate opens his game and his row, on screen"))
            last = want[-1]["key"]
            await pg.evaluate("window.scrollTo(0, 0)"); await pg.click(f'.nav a[href="#{last}"]'); await pg.wait_for_timeout(500)
            n = await pg.evaluate(f"(function(){{ var c = document.getElementById('{last}'); return [c.classList.contains('expanded'), c.getBoundingClientRect().top]; }})()")
            check(n[0] and -5 <= n[1] <= 320, T(f"a game's chip at the top jumps to that game and opens it ({last})"))
            late = B["day"] < N.nba_day()
            nb = await pg.evaluate("(function(){ var o = document.getElementById('nbold'); return [!!o && o.hidden, o ? o.getClientRects().length : -1, document.querySelector('.grid').getAttribute('data-day')]; })()")
            check(nb[2] == B["day"] and nb[0] == (not late) and (nb[1] == 0) == (not late), T(f"the old-board note is {'shown: the board is for a day already over' if late else 'hidden: the board is for today or a day to come'} ({B['day']})"))
            check(not errs, T(f"no script errors {errs[:2]}"))
            if SHOTS:
                await pg.evaluate("window.scrollTo(0, 0)"); await pg.screenshot(path=os.path.join(SHOTS, f"nba_{theme}_{'phone' if phone else 'desk'}.png"))
            await ctx.close()
        # ---- the same page read three days later: it says whose board it is
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        await ctx.add_init_script("(function(){ var n = Date.now; Date.now = function(){ return n() + 3 * 86400000; }; })()")
        await ctx.route("**/*supabase*/**", lambda r: r.abort())
        pg = await ctx.new_page(); await pg.goto(f"http://127.0.0.1:{PORT}/nba/", wait_until="domcontentloaded"); await pg.wait_for_timeout(900)
        ob = await pg.evaluate("(function(){ var o = document.getElementById('nbold'), r = o.getBoundingClientRect(), g = document.querySelector('.grid').getBoundingClientRect(); return [o.hidden, o.textContent.replace(/\\s+/g, ' ').trim(), r.height, r.top < g.top, document.documentElement.scrollWidth - innerWidth]; })()")
        check(not ob[0] and ob[1].startswith(f"This board is for {B['day_label']}.") and ob[2] > 30 and ob[3] and ob[4] <= 0, f"read three days later, the page says so above the cards: \"{ob[1][:70]}...\"")
        if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, "nba_old_board.png"))
        await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
