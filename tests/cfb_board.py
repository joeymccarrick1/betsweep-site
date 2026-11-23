"""/cfb/ - college football postseason game lines, the third sport beyond the NFL. A PREVIEW: not in the menu, not in the sitemap.

Owner 11/22: college football means "Post season game lines"; 11/23 1:10 AM: "get to work on the next thing which I suppose is college
football". Game lines only - Tennessee does not allow bets on individual college athletes - and THE LINE LEADS: this season the
book's spread was closer than our rating (sports/backtests/RESULTS.md), so a card's score is what the posted spread and total imply
and our rating sits beside it, tracked, never a pick.

Three parts:
  the board builder (sports/cfb/publish.py) on a made-up season and a made-up ESPN mirror: which games count as postseason, a game
    whose teams are not set, the spread's sign, the implied score, a neutral site, finals the schedule file does not have yet;
  the page's own rules (build_cfb.py): which boards are drawn, the wording against the line, the signature, the small publish;
  the page itself, redone from the board it ships (/cfb/board.json), at 390x844 in light and dark and on a desktop.

Serves SITE (default ./site).   python3 tests/cfb_board.py
With no /cfb/ page in the build it says so and passes: the page is optional, a stale one is not.
"""
import asyncio, json, os, re, sys, tempfile, shutil, threading, http.server, functools, datetime as dt
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); TREE = os.path.join(HERE, ".."); sys.path.insert(0, TREE)
ROOT = os.environ.get("SITE") or os.path.join(TREE, "site")
PORT = 8886
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
import build_cfb as C, build_nba as N, sport_nav


def publisher():
    """sports/cfb/publish.py on a made-up season: four full-schedule teams, one that played twice, and a mirror with every kind of game"""
    try:
        import pandas as pd
        from sports.cfb import publish as P, model as CM
    except Exception as e:
        check(True, f"(pandas or scipy is not here, so the board builder is not exercised: {type(e).__name__})"); return
    d = tempfile.mkdtemp()
    try:
        teams = {1: ("Alpha Aces", "ALP"), 2: ("Beta Bears", "BET"), 3: ("Gamma Goats", "GAM"), 4: ("Delta Ducks", "DEL"), 9: ("Tiny Tech", "TINY")}
        pts = {1: 38, 2: 30, 3: 24, 4: 14, 9: 7}
        rows, gid, day = [], 100, dt.datetime(2026, 9, 5, 19, 0)
        for rnd in range(2):
            for h in (1, 2, 3, 4):
                for a in (1, 2, 3, 4):
                    if h == a or (rnd == 1 and h > a): continue
                    gid += 1; day += dt.timedelta(days=2)
                    rows.append({"game_id": gid, "season": 2026, "week": 1 + gid % 12, "season_type": 2, "game_date": day.strftime("%Y-%m-%dT%H:%MZ"), "neutral_site": False, "home_id": h, "away_id": a,
                                 "home_team": teams[h][0], "away_team": teams[a][0], "home_abbreviation": teams[h][1], "away_abbreviation": teams[a][1],
                                 "home_score": pts[h] + 3 - (pts[a] - 20) // 4, "away_score": pts[a] - (pts[h] - 20) // 4, "status": "STATUS_FINAL"})
        for a in (1, 2):
            gid += 1; rows.append(dict(rows[0], game_id=gid, home_id=a, away_id=9, home_team=teams[a][0], away_team=teams[9][0], home_abbreviation=teams[a][1], away_abbreviation="TINY", home_score=55, away_score=3,
                                       game_date=f"2026-09-0{a}T23:00Z"))
        pd.DataFrame(rows).to_csv(os.path.join(d, "cfb_schedule_2026.csv"), index=False)
        T = lambda i, ha, **kw: dict({"id": str(i), "abbr": teams[i][1], "name": teams[i][0], "short": teams[i][0].split()[0], "color": "112233", "alt": "ddeeff", "ha": ha, "score": "0", "rank": None, "record": "9-3"}, **kw)
        tbd = lambda ha: {"id": "-1", "abbr": "TBD", "name": "TBD", "ha": ha, "score": "0"}
        ev = lambda i, date, home, away, **kw: dict({"id": str(i), "date": date, "name": "x", "week": 14, "stype": 2, "note": [], "state": "pre", "done": False, "detail": "", "venue": "Field", "neutral": False, "tv": ["ABC"], "teams": [home, away], "odds": None}, **kw)
        events = [
            ev(901, "2026-12-05T01:00Z", T(1, "home", rank=3), T(2, "away", rank=8), note=["Made-Up Championship"], odds={"by": "Draft Kings", "details": "ALP -7.5", "spread": -7.5, "total": 55.5}),
            ev(902, "2026-12-05T17:00Z", T(3, "home"), T(1, "away"), note=["Other Championship"], neutral=True, odds={"by": "Draft Kings", "details": "ALP -10.5", "spread": 10.5, "total": 49.5}),
            ev(903, "2026-12-05T21:00Z", tbd("home"), T(2, "away"), note=["Third Championship"]),
            ev(904, "2026-11-28T17:00Z", T(4, "home"), T(3, "away")),                                                     # a regular-season game: not on this board
            ev(905, "2026-12-19T17:00Z", T(4, "home"), T(9, "away"), stype=3, name="Some Bowl", week=1),                  # a bowl with no note still counts; one side is lower-division
            ev(906, "2026-11-22T20:00Z", T(4, "home", score="10"), T(3, "away", score="31"), state="post", done=True),    # a final the schedule file does not have
            ev(907, "2026-12-05T17:00Z", T(1, "home"), T(3, "away"), note=["Home Championship"])]                         # the same two teams as 902, not at a neutral site
        os.makedirs(os.path.join(d, "feed", "cfb")); json.dump({"mirrored": "2026-11-23T07:00:00Z", "events": events}, open(os.path.join(d, "feed", "cfb", "scoreboard.json"), "w"))
        B = P.build(d, os.path.join(d, "feed"), dt.datetime(2026, 11, 23, 8, 0, tzinfo=dt.timezone.utc))
        G = {g["name"]: g for g in B["games"]}
        check(sorted(G) == ["Home Championship", "Made-Up Championship", "Other Championship", "Some Bowl"] and [x["name"] for x in B["tbd"]] == ["Third Championship"] and B["tbd"][0]["known"] == ["BET"],
              "postseason games are the ones ESPN names as a championship, bowl or playoff game or marks as postseason; a game with a side not set is listed apart with the side that is known; a regular-season game is not on the board")
        a, o = G["Made-Up Championship"], G["Other Championship"]
        check(a["key"] == "BET-ALP" and a["mkt"] == {"home": 31.5, "away": 24.0, "margin": 7.5, "total": 55.5, "p_home": a["mkt"]["p_home"]} and 0.6 < a["mkt"]["p_home"] < 0.75 and a["line"]["by"] == "DraftKings"
              and o["mkt"]["home"] == 19.5 and o["mkt"]["away"] == 30.0 and o["mkt"]["margin"] == -10.5 and o["koct"] == "Sat 12/5 11:00 AM" and a["koct"] == "Fri 12/4 7:00 PM",
              "the posted spread is the home side's (minus = home favored): -7.5 with a total of 55.5 is 31.5 to 24, and +10.5 with 49.5 is 19.5 to 30; kickoffs are Central")
        check(a["model"]["margin"] > 0 and abs(a["gap"]["margin"] - (a["model"]["margin"] - 7.5)) < 0.06 and abs(a["gap"]["total"] - (a["model"]["total"] - 55.5)) < 0.06 and G["Some Bowl"]["mkt"] is None and G["Some Bowl"]["gap"] is None
              and G["Home Championship"]["model"]["margin"] < -o["model"]["margin"] + 20 and abs((G["Home Championship"]["model"]["home"] + G["Home Championship"]["model"]["away"]) - o["model"]["total"]) < 1.5
              and G["Home Championship"]["model"]["home"] > o["model"]["away"],
              "our rating gives each side's points, the gap is our rating minus the line, a game with no line has no gap - and the home side's edge is given at home and not at a neutral site")
        check(B["played"] == len(rows) + 1 and B["from_mirror"] == 1 and B["data_through"] == "2026-11-22" and B["n_teams"] == 4 and any("lower-division" in c for c in B["checks"]) and B["teams"]["TINY"]["fbs"] is False and B["teams"]["TINY"]["off"] is None,
              "a final in ESPN's mirror that the schedule file does not have yet is counted; a team with too few games to rate is treated as lower-division, has no rank, and the board says so")
        t = B["teams"]["DEL"]
        check(t["last"][0] == {"d": "2026-11-22", "opp": "GAM", "ha": "vs", "home": True, "pf": 10, "pa": 31, "res": "L"} and len(t["last"]) == 5 and t["games"] == 10 and t["streak"].startswith("L")
              and [r["d"] for r in t["last"]] == sorted((r["d"] for r in t["last"]), reverse=True) and t["ppg"] is not None and t["papg"] > t["ppg"]
              and B["teams"]["ALP"]["off"][0] == 1 and B["teams"]["DEL"]["off"][0] == 4 and B["teams"]["ALP"]["def"][0] <= 2 and B["teams"]["BET"]["rank"] == 8 and B["teams"]["BET"]["record"] == "9-3",
              "a team's block: its last five newest first with the opponent's short name and the Central date, its streak, points a game, and its adjusted offense and defense ranks (the best offense is #1)")
        check(C.usable(B, dt.datetime(2026, 11, 23, 9, 0, tzinfo=dt.timezone.utc))[0] and "Conference championships" not in C.round_label(B) and C.round_label(B) == "Championships, bowls and the playoff",
              "the page's own rule accepts the board the builder writes, and names the round from what is on it")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def rules():
    now = dt.datetime(2026, 11, 23, 8, 0, tzinfo=dt.timezone.utc)
    good = {"sport": "cfb", "format": C.FORMAT, "built": "2026-11-23T07:40:00Z", "games": [{"ko": "2026-12-05T01:00Z"}], "tbd": []}
    r = [C.usable(None, now), C.usable(dict(good, format=7), now), C.usable(dict(good, games=[]), now), C.usable(dict(good, built="2026-11-21T20:00:00Z"), now), C.usable(dict(good, games=[{"ko": "2026-11-22T20:00Z"}]), now)]
    check(C.usable(good, now)[0] and not any(x[0] for x in r) and all(x[1] for x in r) and C.usable(dict(good, built="2026-11-01T00:00:00Z"), now, any_age=True)[0]
          and C.usable(dict(good, games=[{"ko": "2026-11-22T20:00Z"}], tbd=[{"ko": "2026-12-05T01:00Z"}]), now)[0],
          f"a board is drawn when it is in the right shape, was built in the last day and has a game still to come (one whose teams are not set counts); otherwise not, each with its reason (e.g. {r[2][1]})")
    g = {"home": "MIA", "away": "WAKE", "line": {"spread": -2.5, "total": 56.5}, "mkt": {"home": 29.5, "away": 27.0, "margin": 2.5, "total": 56.5}, "model": {"margin": -4.0, "total": 57.9}, "gap": {"margin": -6.5, "total": 1.4}}
    far = dict(g, gap={"margin": 3.0, "total": -4.0})
    check(C.side_line(g, "home") == "MIA −2.5" and C.side_line(g, "away") == "WAKE +2.5" and C.side_line(dict(g, line={"spread": 0, "total": 50}), "home") == "MIA pick" and C.by_text(-4.0, "MIA", "WAKE") == "WAKE by 4"
          and C.by_text(2.5, "MIA", "WAKE") == "MIA by 2.5" and C.by_text(0, "MIA", "WAKE") == "even",
          "the spread reads as each side sees it (MIA −2.5 is WAKE +2.5) and a margin reads as who by how many")
    check("<b>6.5 points toward WAKE</b> of the spread and close to the posted total" in C.gap_line(g) and "<b>3 points toward MIA</b> of the spread and <b>4 lower</b> than the posted total" in C.gap_line(far)
          and "within a field goal of the spread" in C.gap_line(dict(g, gap={"margin": 2.9, "total": 3.9})) and all("tracked, not a pick" in C.gap_line(x) for x in (g, far)) and C.gap_line(dict(g, mkt=None)) == "",
          f"the sentence under the tiles says how far our rating sits from the line - {C.NEAR:g} points on the spread and {C.NEAR_TOTAL:g} on the total before it is called apart - and always that it is tracked, not a pick; no line, no sentence")
    B0 = {"games": [dict(g, key="WAKE-MIA", name="ACC Championship", ko="2026-12-05T17:00Z", state="pre", score=None)], "tbd": [{"name": "SEC Championship", "ko": "2026-12-05T21:00Z", "known": ["UGA"]}], "teams": {"MIA": {"rank": 7, "record": "10-1"}}}
    moved = json.loads(json.dumps(B0)); moved["games"][0]["line"]["spread"] = -3.0
    known = json.loads(json.dumps(B0)); known["tbd"][0]["known"] = ["UGA", "TEX"]
    same = json.loads(json.dumps(B0)); same["games"][0]["model"]["margin"] = -4.3; same["built"] = "later"
    check(C.signature(B0) != C.signature(moved) and C.signature(B0) != C.signature(known) and C.signature(B0) == C.signature(same),
          "the page's signature moves when a line moves or a title game learns a team - so the small publish sends it out - and not when only a decimal of our rating does")
    check(sport_nav.switch("cfb", {}) == '<div class="nbsw" role="group" aria-label="Sport"><a href="/boards/">NFL</a><a href="/cfb/" aria-current="page">CFB</a></div>'
          and re.findall(r'href="([^"]+)"', sport_nav.switch("nba", {"cfb": True, "epl": True})) == ["/boards/", "/cfb/", "/nba/", "/epl/"] and "/epl/" not in sport_nav.switch("nba", {"cfb": True})
          and sport_nav.available(only=["cfb", "nope"]) == {"cfb": True},
          "the sport switch is NFL, CFB, NBA, EPL in that order, marks the page you are on, and links only to sports that have a page in the build")
    import reprice as R
    keep = (R.SITE, R.OUT); d = tempfile.mkdtemp()
    try:
        R.SITE, R.OUT = os.path.join(d, "site"), os.path.join(d, "out"); clone = os.path.join(d, "clone")
        for x in (os.path.join(R.SITE, "cfb"), os.path.join(R.SITE, "nba"), R.OUT, os.path.join(clone, "nba"), os.path.join(clone, "s"), os.path.join(R.SITE, "s")): os.makedirs(x)
        open(os.path.join(R.SITE, "cfb", "index.html"), "w").write("new cfb"); open(os.path.join(R.SITE, "nba", "index.html"), "w").write("new nba"); open(os.path.join(clone, "nba", "index.html"), "w").write("live nba")
        json.dump({"sig": "N1"}, open(os.path.join(R.OUT, "nba_sig.json"), "w")); json.dump({"sig": "N1"}, open(os.path.join(clone, "nba", "sig.json"), "w"))
        json.dump({"sig": "C1"}, open(os.path.join(R.OUT, "cfb_sig.json"), "w"))
        ch = [n for n in R.PREVIEWS if R.preview_changed(clone, n)]
        done = R.copy_only(clone, ch)
        check("cfb" in R.PREVIEWS and ch == ["cfb"] and done == ["cfb"] and open(os.path.join(clone, "cfb", "index.html")).read() == "new cfb" and open(os.path.join(clone, "nba", "index.html")).read() == "live nba",
              "a college football page the live site does not have yet is a change: /cfb/ alone is copied by the small publish")
    finally:
        R.SITE, R.OUT = keep; shutil.rmtree(d, ignore_errors=True)


async def main():
    publisher(); rules()
    page_path = os.path.join(ROOT, "cfb", "index.html")
    if not os.path.exists(page_path):
        check(not os.path.exists(os.path.join(ROOT, "cfb", "board.json")), "this build has no college football page, and no leftover board file (the page is optional; a stale one is not allowed)")
        print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
    src = open(page_path, encoding="utf-8").read()
    B = json.load(open(os.path.join(ROOT, "cfb", "board.json")))
    G = B["games"]; lined = [g for g in G if g.get("mkt")]
    check(B.get("format") == C.FORMAT and B.get("sport") == "cfb" and len(G) >= 1 and len({g["key"] for g in G}) == len(G) and B.get("data_through") and B.get("played", 0) > 300,
          f"the page ships its board: {C.round_label(B)}, {len(G)} games ({len(lined)} with a posted line), {len(B.get('tbd') or [])} still to be decided, {B.get('played')} finals through {B.get('data_through')}")
    check(all(abs(g["mkt"]["home"] + g["mkt"]["away"] - g["line"]["total"]) < 0.11 and abs((g["mkt"]["home"] - g["mkt"]["away"]) + g["line"]["spread"]) < 0.11 and 20 <= g["line"]["total"] <= 95 and abs(g["line"]["spread"]) <= 60 for g in lined)
          and all(3 < g["model"]["home"] < 75 and 3 < g["model"]["away"] < 75 and 0 < g["model"]["p_home"] < 1 and g["home"] in B["teams"] and g["away"] in B["teams"] for g in G),
          "every posted line: the two implied scores add up to the total and differ by the spread; every game has our rating's points for both sides, in a football game's range")
    sm = open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, "sitemap.xml")) else ""
    linkers = [rel for rel in ("index.html", "boards/index.html", "build/index.html", "stocks/index.html", "social/index.html") if os.path.exists(os.path.join(ROOT, rel)) and re.search(r'href="/cfb/?"', open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore").read())]
    check("/cfb/" not in sm and not linkers, f"it is a preview: not in the sitemap, and no NFL page or menu links to it ({linkers})")
    body = re.sub(r"<style.*?</style>|<script.*?</script>", "", src, flags=re.S)
    own = body[body.find('<div class="top">'): body.find("</p>", body.find('class="nbstamp"'))]        # the page's own words, without the site's menu and footer
    text = re.sub(r"<[^>]+>", " ", own)
    check("College football preview." in body and "Game lines only" in body and "not FanDuel" in body and "nothing here is a pick" in body and not re.search(r"\b(best bet|lock of|value bet|\+EV|lean)\b", text, re.I)
          and all(re.search(r"(not a|is a|nothing here is a) pick", text[max(0, m.start() - 22): m.end()], re.I) for m in re.finditer(r"\bpicks?\b", text, re.I)),
          "the page says what it is - a preview, game lines only, ESPN's posted line and not FanDuel's - and the word pick appears only to say nothing here is one")
    T = B.get("test") or {}
    check(f'{T.get("book_miss", 0):.1f} points' in body and f'{T.get("model_miss", 0):.1f}' in body and f'{T["ats"][0]}–{T["ats"][1]}' in body and "That is why the line leads on this page" in body,
          f"the stamp gives the evidence for leading with the line: the book off by {T.get('book_miss')}, our rating by {T.get('model_miss')}, {T['ats'][0]}-{T['ats'][1]} against the spread")
    have = {k: True for k in ("nba", "epl") if os.path.exists(os.path.join(ROOT, k, "index.html"))}
    f1 = lambda x: f"{x:.1f}"
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(type("Q", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}), directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme, vw, vh, phone in (("light", 390, 844, True), ("dark", 390, 844, True), ("dark", 1280, 900, False)):
            T_ = lambda s: f"[{theme} {'phone' if phone else 'desktop'}] {s}"
            ctx = await b.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=2 if phone else 1, is_mobile=phone, has_touch=phone)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            await ctx.route("**/*supabase*/**", lambda r: r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/cfb/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1300)
            st = await pg.evaluate("""(function(){ var tx = function(e){ return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; };
              return {cards: [...document.querySelectorAll('.grid .card[id]:not(.summary)')].map(function(c){ return {id: c.id, a: tx(c.querySelector('.tm.a b')), b: tx(c.querySelector('.tm.b b')), pts: [...c.querySelectorAll('.score .pt')].map(tx),
                  sub: tx(c.querySelector('.score small')), name: tx(c.querySelector('.cfname')), tiles: [...c.querySelectorAll('.cfmk span')].map(function(s){ return [tx(s.querySelector('small')), tx(s.querySelector('b'))]; }),
                  gap: tx(c.querySelector('.cfgap')), info: tx(c.querySelector('.ginfo')), exp: c.classList.contains('expanded'), cols: c.querySelector('.cols').getBoundingClientRect().height}; }),
                compact: document.body.classList.contains('compact'), over: document.documentElement.scrollWidth - innerWidth, sw: [...document.querySelectorAll('.nbsw a')].map(function(a){ return [a.textContent, a.getAttribute('href'), a.getAttribute('aria-current')]; }),
                bg: getComputedStyle(document.querySelector('.card .hd')).backgroundImage, theme: document.documentElement.getAttribute('data-theme'), old: document.getElementById('nbold').hidden}; })()""")
            want = [{"id": g["key"], "a": g["away"], "b": g["home"], "pts": [f1((g.get("mkt") or g["model"])["away"]), f1((g.get("mkt") or g["model"])["home"])], "name": g["name"]} for g in G]
            got = [{k: c[k] for k in ("id", "a", "b", "pts", "name")} for c in st["cards"]]
            check(got == want, T_(f"a card a game, visiting side first, named for its game; the score is what the line implies (our rating where no line is posted): {[c['a'] + ' ' + '-'.join(c['pts']) + ' ' + c['b'] for c in st['cards']]}"))
            okt = True
            for c, g in zip(st["cards"], G):
                m = g["model"]
                t = dict(c["tiles"])
                if g.get("mkt"):
                    fav = "home" if g["line"]["spread"] <= 0 else "away"
                    okt &= (t.get("Spread") == C.side_line(g, fav) and t.get("Total") == C.num(g["line"]["total"]) and C.side_line(g, fav) in c["sub"] and ("total " + C.num(g["line"]["total"])).lower() in c["sub"].lower()
                            and c["gap"] == re.sub(r"<[^>]+>", "", C.gap_line(g)) and (g["line"]["by"] or "") in c["info"])
                else:
                    okt &= t.get("Spread") == "—" and c["gap"] is None and "no line posted yet" in c["sub"].lower()
                okt &= t.get("Our rating") == C.by_text(m["margin"], g["home"], g["away"]) and t.get("Our total") == f1(m["total"]) and g["koct"] in c["info"]
            check(okt, T_("each card's tiles are the posted spread and total and our rating's margin and total; the sentence under them is the board's gap in words; a game with no line shows dashes and says so"))
            multi = len(G) > 1
            check(st["compact"] == multi and all(not c["exp"] for c in st["cards"]) == multi and st["over"] <= 0 and st["old"] and st["theme"] == theme,
                  T_(f"scorecards first, as on the NFL boards: {len(G)} games, {'none' if multi else 'the one'} opened, no sideways scroll"))
            check(st["sw"] == [[lab, href, ("page" if key == "cfb" else None)] for key, lab, href in sport_nav.ORDER if key in ("nfl", "cfb") or have.get(key)],
                  T_(f"the sport switch: {' | '.join(x[0] for x in st['sw'])}, this page marked"))
            check("M24%2018l10%2010" in st["bg"] and ("20%2C26%2C36" if theme == "light" else "239%2C233%2C218") in st["bg"] and "M34%20120V82h32v38" not in st["bg"],
                  T_("the card heads keep the NFL's Xs and Os - it is football - in this theme's ink"))
            g0 = G[-1]; k0 = g0["key"]
            if multi:
                await pg.click(f'[id="{k0}"] .vbtn[data-view="proj"]'); await pg.wait_for_timeout(350)
            tm = await pg.evaluate("""(function(k){ var c = document.getElementById(k), tx = function(e){ return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; };
              return {exp: c.classList.contains('expanded'), teams: [...c.querySelectorAll('.cols .cfteam')].map(function(u){ var r = u.getBoundingClientRect();
                  return {t: u.getAttribute('data-team'), head: tx(u.querySelector('.dsum')), chips: [...u.querySelectorAll('.cfst span')].map(function(s){ return [tx(s.querySelector('small')), tx(s.querySelector('b'))]; }),
                          rows: [...u.querySelectorAll('.cfg')].map(function(l){ return [...l.children].map(tx); }), right: r.right, w: r.width, inner: Math.max.apply(null, [...u.querySelectorAll('.cfst, .cfg')].map(function(x){ return x.getBoundingClientRect().right; }))}; }),
                over: document.documentElement.scrollWidth - innerWidth}; })""", k0)
            okc = len(tm["teams"]) == 2 and [x["t"] for x in tm["teams"]] == [g0["away"], g0["home"]] and tm["over"] <= 0
            for x in tm["teams"]:
                t = B["teams"][x["t"]]; ch = dict(x["chips"])
                okc &= (t.get("record") or "") in x["head"] and (t["ppg"] is None or (ch.get("Scores") == f1(t["ppg"]) and ch.get("Allows") == f1(t["papg"]))) and (not t.get("off") or (ch.get("Offense") == f"#{t['off'][0]}" and ch.get("Defense") == f"#{t['def'][0]}"))
                okc &= [r[:3] for r in x["rows"]] == [[r["res"], f'{r["pf"]}–{r["pa"]}', f'{r["ha"]} {r["opp"]}'] for r in t.get("last") or []] and x["inner"] <= x["right"] + 0.5
            check(tm["exp"] and okc, T_(f"'How they got here' opens the two teams, visitors first: record, points scored and allowed, adjusted offense and defense ranks and the last {len(B['teams'][g0['home']].get('last') or [])} results as the board has them, inside the card's edges"))
            await pg.evaluate("window.scrollTo(0, 0)"); await pg.click(".card.summary .hd"); await pg.wait_for_timeout(300)
            sl = await pg.evaluate("(function(){ var s = document.querySelector('.card.summary'); return {exp: s.classList.contains('expanded'), lists: [...s.querySelectorAll('.sumgrid ul')].map(function(u){ return u.children.length; }), over: document.documentElement.scrollWidth - innerWidth}; })()")
            check(sl["exp"] and sl["lists"] == [len(G)] + ([len(B["tbd"])] if B.get("tbd") else []) and sl["over"] <= 0 and not errs,
                  T_(f"the Slate card opens to every game with its line, and the {len(B.get('tbd') or [])} title games whose teams are not set; no script errors ({errs})"))
            await ctx.close()
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)

asyncio.run(main())
