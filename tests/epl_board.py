"""/epl/ - Premier League Matchup Boards, the second page beyond the NFL. A PREVIEW: not in the menu, not in the sitemap.

Owner 11/22 3:27 PM: "Let's start adding nba, college football, and epl. I want each sport to basically look exactly like everything
we've built for NFL."; 9:32 PM: "Get to what's next".

The page ships the board it was drawn from (/epl/board.json, written by sports/epl/publish.py in the feeds-sports job). This test
redoes the page from that file - every match's expected goals and result chances, the posted line, the match tiles, each club's
ranks, outs and doubts, every player row in its order, his chips, chances and last appearances - at 390x844 in light and dark and on
a desktop. It also checks the board itself (chances add up, nobody who is out has numbers), the rules for which boards are drawn, and
the small publish for a preview folder.

Serves SITE (default ./site).   python3 tests/epl_board.py [shots_dir]
With no /epl/ page in the build it says so and passes: the page is optional, a stale one is not.
"""
import asyncio, json, os, re, sys, tempfile, shutil, threading, http.server, functools, datetime as dt
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); TREE = os.path.join(HERE, ".."); sys.path.insert(0, TREE)
ROOT = os.environ.get("SITE") or os.path.join(TREE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8885
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
import build_epl as K, build_nba as N
pct = lambda p: f"{round(p * 100)}%"


def rules():
    now = dt.datetime(2026, 11, 23, 4, 0, tzinfo=dt.timezone.utc)
    good = {"sport": "epl", "format": K.FORMAT, "built": "2026-11-23T03:40:00Z", "matches": [{"ko": "2026-11-23T20:00Z"}], "players": [{}]}
    r = [K.usable(None, now), K.usable(dict(good, format=7), now), K.usable(dict(good, matches=[]), now), K.usable(dict(good, built="2026-11-21T20:00:00Z"), now), K.usable(dict(good, matches=[{"ko": "2026-11-22T14:00Z"}]), now)]
    check(K.usable(good, now)[0] and not any(x[0] for x in r) and all(x[1] for x in r) and K.usable(dict(good, built="2026-11-01T00:00:00Z"), now, any_age=True)[0],
          f"a board is drawn when it is in the right shape, was built in the last day and has a match not long over; otherwise not, each with its reason (e.g. {r[4][1]}); a board named by hand is drawn at any age")
    # the small publish, for any preview folder
    import reprice as R
    keep = (R.SITE, R.OUT); d = tempfile.mkdtemp()
    try:
        R.SITE, R.OUT = os.path.join(d, "site"), os.path.join(d, "out"); clone = os.path.join(d, "clone")
        for x in (os.path.join(R.SITE, "epl"), os.path.join(R.SITE, "nba"), R.OUT, os.path.join(clone, "nba"), os.path.join(clone, "s"), os.path.join(R.SITE, "s")): os.makedirs(x)
        open(os.path.join(R.SITE, "epl", "index.html"), "w").write("new epl"); open(os.path.join(R.SITE, "nba", "index.html"), "w").write("new nba"); open(os.path.join(clone, "nba", "index.html"), "w").write("live nba")
        json.dump({"sig": "N1"}, open(os.path.join(R.OUT, "nba_sig.json"), "w")); json.dump({"sig": "N1"}, open(os.path.join(clone, "nba", "sig.json"), "w"))
        check(R.preview_changed(clone, "epl") is False and R.preview_changed(clone, "nba") is False, "no Premier League signature in the build and an unchanged NBA one: nothing to publish")
        json.dump({"sig": "E1"}, open(os.path.join(R.OUT, "epl_sig.json"), "w"))
        ch = [n for n in R.PREVIEWS if R.preview_changed(clone, n)]
        done = R.copy_only(clone, ch)
        check(ch == ["epl"] and done == ["epl"] and open(os.path.join(clone, "epl", "index.html")).read() == "new epl" and open(os.path.join(clone, "nba", "index.html")).read() == "live nba",
              "a Premier League page the live site does not have yet is a change: /epl/ alone is copied, the NBA folder is left as it is")
    finally:
        R.SITE, R.OUT = keep; shutil.rmtree(d, ignore_errors=True)


def expect(B):
    n = B.get("n_clubs") or 20
    ranks = {}
    for pos in K.POSN:
        for i, p in enumerate(sorted([p for p in B["players"] if p["pos"] == pos and K.regular(p)], key=lambda p: (-p["p_goal"], p["name"]))): ranks[(p["id"], p["match"])] = i + 1
    out = []
    for m in B["matches"]:
        h, a = m["home"], m["away"]; p = m["p"]; line = m.get("line") or {}
        cols = {}
        for ab, opp in ((h, a), (a, h)):
            t, o = B["teams"][ab], B["teams"][opp]
            ps = sorted([x for x in B["players"] if x["team"] == ab and x["match"] == m["id"]], key=lambda x: (not K.regular(x), -x["p_goal"], x["name"]))
            role = lambda x: {"start": "in the eleven", "bench": "on the bench", "no": "not in the squad"}.get(x.get("xi")) or f"started {x['starts5']} of last 5"
            cols[ab] = {"def": [f"Goals#{n + 1 - o['def'][0]}", f"Shots#{n + 1 - o['shots_against'][0]}"], "out": [x["name"] for x in t.get("out") or []], "doubt": [x["name"] for x in t.get("doubt") or []],
                        "players": [[x["id"], x["name"], x["pos"], role(x), pct(x["p_goal"]), (f"#{ranks[(x['id'], x['match'])]} {x['pos']}" if (x["id"], x["match"]) in ranks else ""), (x.get("status") or {}).get("tag") or "", not K.regular(x)] for x in ps],
                        "div": any(not K.regular(x) for x in ps)}
        best = m["scores"][0]
        out.append({"key": m["key"], "h": h, "a": a, "score": f"{m['xg']['home']:.2f}–{m['xg']['away']:.2f}", "small": f"{h} {pct(p['home'])} · draw {pct(p['draw'])} · {a} {pct(p['away'])}", "ko": m["koct"] + " CT",
                    "line": " · ".join(x for x in ((line.get("details") or ""), (f"O/U {line['total']:g}" if isinstance(line.get("total"), (int, float)) else "")) if x), "by": (line.get("by") or "").replace("Draft Kings", "DraftKings"),
                    "mk": [pct(p["over25"]), pct(p["btts"]), f"{best[0]} {pct(best[1])}", f"{m['shots']['home']:.0f}–{m['shots']['away']:.0f}"],
                    "nout": sum(len(B["teams"][x].get("out") or []) + len(B["teams"][x].get("doubt") or []) for x in (h, a)), "cols": cols})
    return out, ranks


READ = r"""(function(){
  var tx = function(e){ return e ? e.textContent.replace(/\s+/g, ' ').trim() : ''; };
  return [...document.querySelectorAll('.grid > .card[id]:not(.summary)')].map(function(c){
    var cols = {}; c.querySelectorAll('ul.col').forEach(function(u){
      var nm = function(e){ return tx(e).replace(tx(e.querySelector('small')), '').trim(); };
      cols[u.getAttribute('data-team')] = {def: [...u.querySelectorAll('.dsum .dm')].map(function(d){ return tx(d.querySelector('.dl')) + tx(d.querySelector('b')); }),
        out: [...u.querySelectorAll('.inj:not(.epldoubt) em')].map(nm), doubt: [...u.querySelectorAll('.inj.epldoubt em')].map(nm), div: !!u.querySelector('.epldiv'),
        players: [...u.querySelectorAll('li.pl')].map(function(li){ var n = li.querySelector('.nm'), tags = [...n.querySelectorAll('.nbtag')], v = li.querySelector('.ppr .v'), name = tx(n); tags.forEach(function(t){ name = name.replace(tx(t), ''); });
          var st = tags.filter(function(t){ return t.classList.contains('t-q'); }).map(tx)[0] || '';
          return [li.getAttribute('data-pid'), name.trim(), tx(li.querySelector('.pos')), tx(li.querySelector('.role')), v.childNodes[1].textContent.trim(), tx(li.querySelector('.rk')), st, li.classList.contains('eplsub')]; })};
    });
    var mk = c.querySelector('.ginfo .mkt'), by = mk && mk.querySelector('small');
    return {key: c.id, h: tx(c.querySelector('.tm.a b')), a: tx(c.querySelector('.tm.b b')), score: [...c.querySelectorAll('.score .pt')].map(tx).join('–'), small: tx(c.querySelector('.score small')), ko: tx(c.querySelector('.ginfo .gk')),
      line: mk ? tx(mk).replace(by ? tx(by) : '', '').trim() : '', by: by ? tx(by) : '', mk: [...c.querySelectorAll('.eplmk b')].map(tx), cols: cols,
      nout: parseInt(tx(c.querySelector('.vbtn[data-view="out"] small')) || '0', 10)};
  });
})()"""


async def main():
    rules()
    page_path = os.path.join(ROOT, "epl", "index.html")
    if not os.path.exists(page_path):
        check(not os.path.exists(os.path.join(ROOT, "epl", "board.json")), "this build has no Premier League page, and no leftover board file (the page is optional; a stale one is not allowed)")
        print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
    src = open(page_path, encoding="utf-8").read()
    B = json.load(open(os.path.join(ROOT, "epl", "board.json")))
    want, ranks = expect(B)
    P = B["players"]; mids = {m["id"] for m in B["matches"]}
    check(B.get("format") == K.FORMAT and B.get("sport") == "epl" and len(B["matches"]) >= 1 and len({m["key"] for m in B["matches"]}) == len(B["matches"]) and B.get("data_through"),
          f"the page ships its board: {K.round_label(B)}, {len(B['matches'])} matches, {len(P)} player rows, matches through {B.get('data_through')}")
    check(all(abs(m["p"]["home"] + m["p"]["draw"] + m["p"]["away"] - 1) < 0.003 and 0.2 < m["xg"]["home"] < 4.5 and 0.2 < m["xg"]["away"] < 4.5 and 0 < m["p"]["btts"] < 1 and m["p"]["over15"] > m["p"]["over25"] > m["p"]["over35"]
              and abs(sum(s[1] for s in m["scores"]) - 0.4) < 0.4 and m["home"] in B["teams"] and m["away"] in B["teams"] for m in B["matches"]),
          "every match: home, draw and away add up to 100%, the goal rates are in a football match's range, and over 1.5 is likelier than over 2.5 than over 3.5")
    check(all(p["match"] in mids and p["team"] in B["teams"] and p["opp"] in B["teams"] and 0 <= p["p_goal"] < 0.9 and p["p_goal2"] <= p["p_goal"] and 0 <= p["p_assist"] < 0.9 and p["shots"] >= p["sot"] >= 0 and 0 <= p["starts5"] <= p["apps5"] <= 5 and p["pos"] in K.POSN for p in P),
          "every player row has a match and a club on the board, a position, chances between 0 and 90%, shots no fewer than shots on target, and starts no more than appearances")
    outs = {(ab, o["name"]) for ab, t in B["teams"].items() for o in t.get("out") or []}
    check(not any((p.get("status") or {}).get("tag") in ("Out", "Suspended") for p in P) and all(o["tag"] in ("Out", "Suspended") for t in B["teams"].values() for o in t.get("out") or []) and all(o["tag"].endswith("%") or o["tag"] == "Doubt" for t in B["teams"].values() for o in t.get("doubt") or []),
          f"nobody listed out or suspended has numbers ({len(outs)} out across the clubs); a doubt keeps his, with his chance of playing")
    sm = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, "sitemap.xml")) else ""
    linkers = [rel for rel in ("index.html", "boards/index.html", "build/index.html", "stocks/index.html", "social/index.html") if os.path.exists(os.path.join(ROOT, rel)) and re.search(r'href="/epl/?"', open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore").read())]
    check("/epl/" not in sm and not linkers, f"it is a preview: not in the sitemap, and no NFL page or menu links to it ({linkers})")
    body = re.sub(r"<style.*?</style>|<script.*?</script>", "", src, flags=re.S)
    check("Premier League preview" in src and "no FanDuel prices yet" in src and "Player numbers assume he starts" in src and "Nothing here is a pick" in src and "sportsbook.fanduel.com" not in body and "thin evidence" in src and "checked against ESPN" in src,
          "the page says what it is: a preview, model numbers only, player numbers for a start, nothing a pick; where its data comes from; and that the test results behind it are thin")
    check(not re.search(r"\b(best bet|lock of|value bet|\+EV)\b", re.sub(r"<[^>]+>", " ", body), re.I), "nothing on it is called a best bet or value")

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme, vw, vh, phone in (("light", 390, 844, True), ("dark", 390, 844, True), ("dark", 1280, 900, False)):
            T = lambda s: f"[{theme} {'phone' if phone else 'desktop'}] {s}"
            ctx = await b.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=2 if phone else 1, is_mobile=phone, has_touch=phone)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            await ctx.route("**/*supabase*/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/epl/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1300)
            got = await pg.evaluate(READ)
            if theme == "light":
                check([g["key"] for g in got] == [w["key"] for w in want], f"one card a match, in kickoff order ({', '.join(g['key'] for g in got[:6])}...)")
                bad = [(g["key"], k, g[k], w[k]) for g, w in zip(got, want) for k in ("h", "a", "score", "small", "ko", "line", "by", "mk", "nout") if g[k] != w[k]]
                check(not bad, "each card's clubs (home first), expected goals, result chances, kickoff, posted line with the book named, the four match tiles and the count of outs and doubts are the board's"
                      + (f" (off: {bad[:2]})" if bad else f" (e.g. {got[0]['h']} {got[0]['score']} {got[0]['a']}: {got[0]['small']}; tiles {got[0]['mk']})"))
                badc = [(g["key"], ab, k, (g["cols"].get(ab) or {}).get(k), w["cols"][ab][k]) for g, w in zip(got, want) for ab in w["cols"] for k in ("def", "out", "doubt", "div") if (g["cols"].get(ab) or {}).get(k) != w["cols"][ab][k]]
                check(not badc, "each club's column: what the opponent allows in goals and in shots (1 = allows the most), who is out and who is a doubt, as the board has them" + (f" (off: {badc[:2]})" if badc else ""))
                badp = [(g["key"], ab, x, y) for g, w in zip(got, want) for ab in w["cols"] for x, y in zip((g["cols"].get(ab) or {}).get("players") or [], w["cols"][ab]["players"]) if x != y] \
                       + [(g["key"], ab, "count") for g, w in zip(got, want) for ab in w["cols"] if len((g["cols"].get(ab) or {}).get("players") or []) != len(w["cols"][ab]["players"])]
                n = sum(len(c["players"]) for w in want for c in w["cols"].values())
                check(not badp and n == len(P), f"all {n} player rows: the regulars first by chance to score, the others under a line, each with position, starts in the last five, chance to score, his rank among this round's regulars and his doubt tag" + (f" (off: {badp[:2]})" if badp else ""))
            st = await pg.evaluate("""(function(){ var cs = [...document.querySelectorAll('.grid > .card[id]:not(.summary)')], c = cs[0], vb = [...c.querySelectorAll('.vbtn')], bar = document.querySelector('.nbbar'), ks = [...bar.children].map(function(x){ return Math.round(x.getBoundingClientRect().top); }), mk = c.querySelector('.eplmk');
              return {compact: document.body.classList.contains('compact'), shown: cs.filter(function(x){ return x.querySelector('.cols').getClientRects().length; }).length, vb: vb.map(function(x){ var r = x.getBoundingClientRect(); return [x.textContent.replace(/\\s+/g, ' ').trim(), r.height]; }),
                over: document.documentElement.scrollWidth - innerWidth, sw: [...document.querySelectorAll('.nbsw a')].map(function(a){ return [a.textContent, a.getAttribute('href'), a.getAttribute('aria-current')]; }), bar: Math.max.apply(null, ks) - Math.min.apply(null, ks),
                mk: [mk.getClientRects().length > 0, mk.getBoundingClientRect().height, [...mk.children].every(function(x){ return x.scrollWidth <= x.clientWidth + 1; })], font: getComputedStyle(c.querySelector('.tm b')).fontFamily,
                names: cs.every(function(x){ return [...x.querySelectorAll('.hd .tm span:not(.badge)')].every(function(s){ return s.getBoundingClientRect().height < 34; }); })}; })()""")
            multi = len(want) > 1
            check(st["compact"] == multi and st["shown"] == (0 if multi else 1) and st["over"] <= 0, T(f"scorecards first, as on the NFL boards: {len(want)} matches, none opened, no sideways scroll"))
            has_nba = os.path.exists(os.path.join(ROOT, "nba", "index.html"))
            check(st["sw"] == [["NFL", "/boards/", None]] + ([["NBA", "/nba/", None]] if has_nba else []) + [["EPL", "/epl/", "page"]] and st["bar"] <= 6, T("the sport switch: NFL, " + ("NBA, " if has_nba else "") + "and EPL (this page), on one row with the key"))
            check(len(st["vb"]) == 2 and st["vb"][0][0].startswith("Projections") and st["vb"][1][0].startswith("Who's out") and min(v[1] for v in st["vb"]) >= 38 and st["mk"][0] and st["mk"][1] <= 78 and st["mk"][2] and st["names"],
                  T(f"each card shows its four match tiles in one row ({st['mk'][1]:.0f}px, nothing cut off), club names on one line, and two buttons: Projections and Who's out"))
            k0 = want[0]["key"]; w0 = want[0]
            await pg.click(f'#{k0} .vbtn[data-view="proj"]'); await pg.wait_for_timeout(350)
            o = await pg.evaluate("""(function(k){ var c = document.getElementById(k), r = [...c.querySelectorAll('li.pl')].filter(function(x){ return x.getClientRects().length; }), f = r[0];
              return {exp: c.classList.contains('expanded'), view: c.getAttribute('data-view'), rows: r.length, rowh: f.querySelector('.prow').getBoundingClientRect().height, w: parseFloat(getComputedStyle(f.querySelector('.ppr i')).getPropertyValue('--w')), over: document.documentElement.scrollWidth - innerWidth}; })""", k0)
            nrows = sum(len(c["players"]) for c in w0["cols"].values())
            check(o["exp"] and o["view"] == "proj" and o["rows"] == nrows and o["rowh"] >= 44 and o["over"] <= 0, T(f"Projections opens the match: {nrows} player rows, each {o['rowh']:.0f}px tall to tap"))
            # ---- a player opened
            tm = w0["h"]; pid = w0["cols"][tm]["players"][0][0]; X = next(x for x in P if x["id"] == pid and x["match"] == B["matches"][0]["id"]); O = B["teams"][X["opp"]]; n = B.get("n_clubs") or 20
            await pg.click(f'#{k0} li.pl[data-pid="{pid}"] .prow'); await pg.wait_for_timeout(250)
            d = await pg.evaluate(r"""(function(a){ var li = document.querySelector('#' + a[0] + ' li.pl[data-pid="' + a[1] + '"]'), dd = li.querySelector('.pdetail'), tx = function(e){ return e ? e.textContent.replace(/\s+/g, ' ').trim() : ''; };
              return {hidden: dd.hidden, chips: [...dd.querySelectorAll('.sl .sc')].map(function(c){ return [c.getAttribute('data-k'), tx(c.querySelector('small')), tx(c.querySelector('b')), tx(c.querySelector('.mu i')), tx(c.querySelector('.fd'))]; }),
                lad: [...dd.querySelectorAll('.nblad li')].map(function(l){ return [tx(l.querySelector('span')), [...l.querySelectorAll('em')].map(function(e){ return tx(e).replace(' ', ''); })]; }), rec: [...dd.querySelectorAll('.nbl5 tbody tr')].map(function(r){ return [...r.children].map(tx); }),
                flags: [...dd.querySelectorAll('.flags .fg')].map(tx), over: document.documentElement.scrollWidth - innerWidth, wide: dd.scrollWidth - dd.clientWidth}; })""", [k0, pid])
            ag, ash = n + 1 - O["def"][0], n + 1 - O["shots_against"][0]; f2 = lambda v: "–" if v is None else f"{v:.2f}"; tot = X["tot"]
            wchips = [["goal", "To score", pct(X["p_goal"]), f"{X['opp']} #{ag}", f"{tot['goals']} goal{'s' if tot['goals'] != 1 else ''} in {X['mins']} min 2+: {pct(X['p_goal2'])}"], ["assist", "An assist", pct(X["p_assist"]), f"{X['opp']} #{ag}", f"{tot['assists']} this season"],
                      ["shots", "Shots", f"{X['shots']:.1f}", f"{X['opp']} #{ash}", f"{f2(X['per90'].get('shots'))} per 90 {tot['shots']} taken"], ["sot", "On target", f"{X['sot']:.1f}", f"{X['opp']} #{ash}", f"{f2(X['per90'].get('sot'))} per 90 {tot['sot']} this season"]]
            check(not d["hidden"] and d["chips"] == wchips and d["over"] <= 0 and d["wide"] <= 1, T(f"{X['name']} opened: his chance to score and of an assist, his shots and shots on target, each with what {X['opp']} allow and his season beside it") + ("" if d["chips"] == wchips else f" (page {d['chips']}, board {wchips})"))
            wl = [[cap, [f"{L}+{pct(pr)}" for L, pr in X["ladder"][k] if pr >= 0.03]] for k, cap in (("shots", "Shots"), ("sot", "Shots on target")) if any(pr >= 0.03 for L, pr in X["ladder"][k])]
            check(d["lad"] == wl and d["rec"] == [[str(c) for c in g[:7]] for g in reversed(X["recent"])], T(f"the chance of each number of shots is the board's ({'; '.join(a + ' ' + ' '.join(b) for a, b in wl[:1])}), and his last {len(X['recent'])} appearances are listed newest first"))
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"epl_{theme}_{'phone' if phone else 'desk'}_player.png"))
            # ---- a player who is not a regular says so
            sub = next((x for x in P if x["match"] == B["matches"][0]["id"] and not K.regular(x) and x.get("xi") is None and not x.get("status")), None)
            if sub:
                await pg.click(f'#{k0} li.pl[data-pid="{sub["id"]}"] .prow'); await pg.wait_for_timeout(250)
                fl = await pg.evaluate("""(function(a){ var li = document.querySelector('#' + a[0] + ' li.pl[data-pid="' + a[1] + '"]'); return [[...li.querySelectorAll('.flags .fg')].map(function(e){ return e.textContent.trim(); }), li.classList.contains('eplsub'), li.querySelector('.flags li') ? li.querySelector('.flags li').textContent : '']; })""", [k0, sub["id"]])
                check(fl[0] == ["Not a regular starter"] and fl[1] and f"started {sub['starts5']} of his club's last 5" in fl[2], T(f"{sub['name']}, who started {sub['starts5']} of the last 5, sits under the line and is flagged: his numbers are for a start"))
            # ---- Who's out
            await pg.click(f'#{k0} .vbtn[data-view="out"]'); await pg.wait_for_timeout(300)
            v = await pg.evaluate("""(function(k){ var c = document.getElementById(k), vis = function(x){ return x.getClientRects().length; }; return {view: c.getAttribute('data-view'), rows: [...c.querySelectorAll('li.pl, .epldiv')].filter(vis).length,
              outs: [...c.querySelectorAll('.inj em')].filter(vis).length, none: [...c.querySelectorAll('.nbnoout')].filter(vis).length}; })""", k0)
            check(v["view"] == "out" and v["rows"] == 0 and v["outs"] == w0["nout"] and v["none"] == sum(1 for ab in (w0["h"], w0["a"]) if not B["teams"][ab].get("out")), T(f"Who's out shows the {w0['nout']} players out or doubtful for the two clubs and no player rows; a club with nobody out says so"))
            await pg.click(f'#{k0} .vbtn[data-view="out"]'); await pg.wait_for_timeout(250)
            # ---- the Slate card
            await pg.evaluate("window.scrollTo(0, 0)"); await pg.click(".card.summary .hd"); await pg.wait_for_timeout(250)
            s = await pg.evaluate(r"""(function(){ var c = document.querySelector('.card.summary'), tx = function(e){ return e.textContent.replace(/\s+/g, ' ').trim(); }, cols = [...c.querySelectorAll('.sumgrid > div')];
              return {exp: c.classList.contains('expanded'), heads: cols.map(function(x){ return tx(x.querySelector('h3')).replace(tx(x.querySelector('h3 small')), '').trim(); }), ms: [...cols[0].querySelectorAll('li a')].map(function(a){ return a.getAttribute('href'); }),
                sc: [...cols[1].querySelectorAll('li')].map(function(l){ return [l.querySelector('a').getAttribute('data-open'), l.querySelector('a').getAttribute('href'), tx(l.querySelector('.bl-m'))]; }), sh: [...cols[2].querySelectorAll('li a')].map(function(a){ return a.getAttribute('data-open'); })}; })()""")
            key = {m["id"]: m["key"] for m in B["matches"]}; reg = [x for x in P if K.regular(x)]
            sc6 = sorted(reg, key=lambda x: (-x["p_goal"], x["name"]))[:6]; sh6 = sorted(reg, key=lambda x: (-x["shots"], x["name"]))[:6]
            check(s["exp"] and s["heads"] == ["Matches", "Likeliest scorers", "Most shots"] and s["ms"] == ["#" + m["key"] for m in B["matches"]] and [x[:2] for x in s["sc"]] == [[x["id"], "#" + key[x["match"]]] for x in sc6]
                  and all(x[2] == f"{pct(y['p_goal'])} to score {y['shots']:.1f} shots" for x, y in zip(s["sc"], sc6)) and s["sh"] == [x["id"] for x in sh6],
                  T(f"the Slate card: every match, the six likeliest scorers among the regulars ({', '.join(x['name'] + ' ' + pct(x['p_goal']) for x in sc6[:3])}) and the six with the most shots"))
            if s["sc"]:
                await pg.click(f'.card.summary a[data-open="{s["sc"][0][0]}"]'); await pg.wait_for_timeout(600)
                j = await pg.evaluate("""(function(a){ var c = document.querySelector(a[1]), li = c.querySelector('li.pl[data-pid="' + a[0] + '"]'), r = li.getBoundingClientRect(); return [c.classList.contains('expanded'), !li.querySelector('.pdetail').hidden, r.top >= 0 && r.top <= innerHeight - 80]; })""", [s["sc"][0][0], s["sc"][0][1]])
                check(j == [True, True, True], T(f"tapping {sc6[0]['name']} in the Slate opens his match and his row, on screen"))
            late = max(K.when(m["ko"]) for m in B["matches"])
            try:
                from zoneinfo import ZoneInfo
                last_day = late.astimezone(ZoneInfo("America/Chicago")).date().isoformat()
            except Exception: last_day = (late - dt.timedelta(hours=6)).date().isoformat()
            ob = await pg.evaluate("[document.getElementById('nbold').hidden, document.querySelector('.grid').getAttribute('data-day')]")
            check(ob == [not (last_day < N.nba_day()), last_day], T(f"the old-board note is {'shown: every match has been played' if last_day < N.nba_day() else 'hidden: the last match is still to come'} ({last_day})"))
            check(not errs and (await pg.evaluate("document.documentElement.scrollWidth - innerWidth")) <= 0, T(f"no script errors, no sideways scroll {errs[:2]}"))
            if SHOTS:
                await pg.evaluate("window.scrollTo(0, 0)"); await pg.wait_for_timeout(200); await pg.screenshot(path=os.path.join(SHOTS, f"epl_{theme}_{'phone' if phone else 'desk'}.png"))
            await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
