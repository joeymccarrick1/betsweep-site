#!/usr/bin/env python3
"""deepdive_pages.py - the pages and cards of the 11/10 deep-dive batch, in a phone-sized headless browser.

  BASE=http://localhost:8802 python3 tests/deepdive_pages.py        (needs a built site and out/*.json from the same build)

Boost finder: every shown slip takes one leg per game, its numbers are the pool's own (chance multiplied, price multiplied, boost on
the profit only), its FanDuel link carries exactly those legs' ids, the rules (legs, shortest leg, shortest total, low risk) hold,
and the same-game checker's verdict is the arithmetic. Line shop: every row is a real better price at the same line, widest gap
first, and kicked-off games leave. Short view: "3 favorites", the all-three chance is the product. Live: the win card draws.
Under of the day and Lines to check: the picking, freezing and grading rules on made-up boards (no browser).
Every request that is not local is blocked.
"""
import datetime, json, os, re, sys, tempfile, urllib.parse
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); GP = os.path.dirname(HERE); OUT = os.path.join(GP, "out"); sys.path.insert(0, GP)
BASE = os.environ.get("BASE", "http://127.0.0.1:8801"); fails = []; n = 0


def check(ok, what):
    global n
    n += 1
    if not ok: fails.append(what); print("FAIL", what)


def dec(o): return 1 + o / 100 if o > 0 else 1 + 100 / -o
def jr(x): return int(x + 0.5) if x >= 0 else -int(-x + 0.5)       # JavaScript's Math.round
def amd(d): return ("+" + str(jr((d - 1) * 100))) if d >= 2 else (chr(0x2212) + str(jr(100 / (d - 1))))


def fd_ids(url):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query); out = []; i = 0
    while f"marketId[{i}]" in q: out.append((q[f"marketId[{i}]"][0], q[f"selectionId[{i}]"][0])); i += 1
    if not out and "marketId" in q: out.append((q["marketId"][0], q["selectionId"][0]))
    return out


def browser_checks():
    BO = json.load(open(os.path.join(OUT, "boost.json"))); SH = json.load(open(os.path.join(OUT, "shop.json"))); SJ = json.load(open(os.path.join(OUT, "simple.json")))
    BYT = {l["t"]: l for l in BO["legs"]}
    with sync_playwright() as p:
        b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        first_ko = min(g["ko"] for g in BO["games"].values() if g["ko"])
        page = ctx.new_page(); errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(BASE) else route.abort())
        page.clock.install(time=datetime.datetime.fromtimestamp(first_ko / 1000 - 6 * 3600, datetime.timezone.utc))
        # ---- boost finder
        page.goto(BASE + "/boost/"); page.wait_for_selector("#bzout .card, #bzout .none", timeout=15000)
        def cards():
            return page.evaluate("""() => [...document.querySelectorAll('#bzout .card')].map(c => ({title: c.querySelector('h2').childNodes[0].textContent.trim(),
                legs: [...c.querySelectorAll('.legs li')].map(li => [li.querySelector('b').textContent, li.querySelector('span').textContent]),
                nums: [...c.querySelectorAll('.nums b')].map(x => x.textContent), verd: c.querySelector('.verd').textContent, href: c.querySelector('a.bsbtn').href}))""")
        def verify(boost, nlegs, min_leg=None, min_tot=None, safe=True, label=""):
            cs = cards(); check(len(cs) >= 1, f"boost {label}: a slip is shown")
            for c in cs:
                legs = [BYT.get(t) for t, _ in c["legs"]]
                check(all(legs) and len(legs) == nlegs, f"boost {label}: {c['title']} has {nlegs} legs from the pool")
                if not all(legs): continue
                check(len({l["g"] for l in legs}) == nlegs, f"boost {label}: {c['title']} takes one leg per game")
                if safe: check(all(l["r"] < 2 for l in legs), f"boost {label}: {c['title']} low-risk only")
                if min_leg is not None: check(all(dec(l["o"]) >= dec(min_leg) - 1e-9 for l in legs), f"boost {label}: every leg at least {min_leg}")
                P = 1.0; D = 1.0
                for l in legs: P *= min(l["p"], 0.93 / dec(l["o"])); D *= dec(l["o"])
                if min_tot is not None: check(D >= dec(min_tot) - 1e-9, f"boost {label}: total at least +{min_tot}")
                bd = 1 + (D - 1) * (1 + boost)
                check(c["nums"][0] == amd(D) + amd(bd), f"boost {label}: {c['title']} pays {amd(D)} -> {amd(bd)} (page: {c['nums'][0]})")
                check(c["nums"][1] == f"about {jr(P * 100)}%", f"boost {label}: {c['title']} all-hit chance {jr(P * 100)}% (page: {c['nums'][1]})")
                check(P * D <= 1 + 1e-9, f"boost {label}: {c['title']} is never shown as better than fair before the boost")
                ev0, ev1 = P * D - 1, P * bd - 1
                check(f"${abs(ev0 * 10):.2f}" in c["verd"] and f"${abs(ev1 * 10):.2f}" in c["verd"], f"boost {label}: {c['title']} value per $10 {ev0 * 10:.2f} / {ev1 * 10:.2f} (page: {c['verd'][:90]})")
                check(fd_ids(c["href"]) == [(l["fm"], l["fs"]) for l in legs], f"boost {label}: {c['title']} FanDuel link carries exactly its legs' ids")
            return cs
        c1 = verify(0.25, 3, label="25% x3")
        # "Most likely to land" really is the likeliest one-per-game triple of the low-risk pool; a second card, when shown, has more
        # value after the boost and still lands one time in ten; nothing is shown ahead before the boost
        if c1:
            from itertools import combinations
            pe = lambda l: min(l["p"], 0.93 / dec(l["o"])); pool = [l for l in BO["legs"] if l["r"] < 2]; bestP = -1; bestEV = -9
            for tri in combinations(pool, 3):
                if len({l["g"] for l in tri}) < 3: continue
                P = pe(tri[0]) * pe(tri[1]) * pe(tri[2]); D = dec(tri[0]["o"]) * dec(tri[1]["o"]) * dec(tri[2]["o"]); bestP = max(bestP, P)
                if P >= 0.10: bestEV = max(bestEV, P * (1 + (D - 1) * 1.25) - 1)
            def pd(c):
                P = 1.0; D = 1.0
                for l in [BYT[t] for t, _ in c["legs"]]: P *= pe(l); D *= dec(l["o"])
                return P, D
            P0, D0 = pd(c1[0]); check(c1[0]["title"] == "Most likely to land" and abs(P0 - bestP) < 1e-9, f"boost: the first card is the likeliest one-per-game triple in the pool ({P0:.4f} vs {bestP:.4f})")
            if len(c1) > 1:
                P1, D1 = pd(c1[1]); ev1 = P1 * (1 + (D1 - 1) * 1.25) - 1
                check(P1 >= 0.10 - 1e-9 and abs(ev1 - bestEV) < 1e-9 and ev1 > P0 * (1 + (D0 - 1) * 1.25) - 1, f"boost: the second card is the best value after the boost among slips that land 1 in 10 ({ev1:.4f} vs {bestEV:.4f}, chance {P1:.2f})")
            ev0 = P0 * D0 - 1; ev1 = P0 * (1 + (D0 - 1) * 1.25) - 1
            check(f"the boost is worth ${(ev1 - ev0) * 10:.2f}" in c1[0]["verd"], f"boost: the card says what the boost itself is worth (${(ev1 - ev0) * 10:.2f}; {c1[0]['verd'][:120]!r})")
        page.select_option("#bzb", "50"); page.select_option("#bzn", "2"); page.select_option("#bzleg", "-200"); page.select_option("#bztot", "200"); page.wait_for_timeout(150)
        if page.query_selector("#bzout .card"): verify(0.5, 2, min_leg=-200, min_tot=200, label="50% x2, legs -200+, total +200+")
        else: check("clears those prices" in page.inner_text("#bzout") or "not there yet" in page.inner_text("#bzout"), "boost: an impossible rule set says so")
        page.select_option("#bzn", "6"); page.select_option("#bzleg", ""); page.select_option("#bztot", ""); page.uncheck("#bzsafe"); page.wait_for_timeout(400)
        check(page.query_selector("#bzout .card") is not None or "not there yet" in page.inner_text("#bzout"), "boost: six legs either finds a slip or says the board is too thin")
        if page.query_selector("#bzout .card"): verify(0.5, 6, safe=False, label="50% x6")
        # same-game checker
        g0 = BO["sgp"][0]; page.select_option("#bzg", g0["g"]); page.fill("#bzq", "+450"); page.select_option("#bzb2", "30"); page.wait_for_timeout(150)
        v = page.inner_text("#bzv2"); bd = 1 + 4.5 * 1.3; pj = jr(g0["pj"] * 100) / 100
        check(amd(5.5) + amd(bd) in v.replace("\n", ""), f"boost checker: +450 at 30% pays {amd(bd)} ({v[:60]!r})")
        check(f"{jr(100 / bd)}%" in v and f"model {jr(g0['pj'] * 100)}%" in v, "boost checker: needs-to-land and the model's chance are shown")
        check(f"${abs((pj * bd - 1) * 10):.2f}" in v, f"boost checker: value per $10 with the boost {((pj * bd - 1) * 10):.2f}")
        check(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"), "boost: fits a phone")
        # ---- line shop
        page.goto(BASE + "/shop/"); rows = page.evaluate("""() => [...document.querySelectorAll('.shl li')].map(li => ({t: li.querySelector('.lg b').textContent, px: li.querySelector('.px').textContent, href: li.querySelector('a').href, hidden: li.hidden}))""")
        check(len(rows) == min(60, len(SH["rows"])), f"shop: {len(rows)} rows shown of {len(SH['rows'])}")
        gaps = [r["gap"] for r in SH["rows"]]; check(gaps == sorted(gaps, reverse=True) and all(g >= 0.015 for g in gaps), "shop: widest gap first, every row 1.5+ points")
        BD = json.load(open(os.path.join(OUT, "builder_data.json"))); ok = True
        for r in SH["rows"]:
            m = [l for l in BD["legs"] if l["g"] == r["g"] and l.get("o") == r["fd"] and ((l.get("bks") or {}).get(r["b"]) or {}).get("o") == r["o"]]
            ok = ok and bool(m) and dec(r["o"]) > dec(r["fd"]) and abs((1 / dec(r["fd"]) - 1 / dec(r["o"])) - r["gap"]) < 1e-3
        check(ok, "shop: every row is a board leg whose other book really pays more at that line, gap as stated")
        check(all(("draftkings.com" in r["href"] or "hardrock" in r["href"]) for r in rows), "shop: every button goes to the better book")
        check(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 2"), "shop: fits a phone")
        if rows:
            last_ko = max(r["ko"] for r in SH["rows"]); page.clock.set_fixed_time(datetime.datetime.fromtimestamp(last_ko / 1000 + 120, datetime.timezone.utc)); page.reload()
            check(page.evaluate("[...document.querySelectorAll('.shl li')].every(li => li.hidden) && !document.getElementById('shnone').hidden"), "shop: after the last kickoff every row is gone and the page says so")
            page.clock.set_fixed_time(datetime.datetime.fromtimestamp(first_ko / 1000 - 6 * 3600, datetime.timezone.utc))
        # ---- short view
        page.goto(BASE + "/short/"); page.evaluate("try{localStorage.removeItem('bs_view')}catch(e){}")
        if SJ.get("easy"):
            check(page.inner_text("#sveasy h2").strip().lower() == "3 favorites", "short: the card is called 3 favorites")
            pall = 1.0
            for e in SJ["easy"]: pall *= e["p"]
            check(page.inner_text("#sveasy .all3").replace("\n", " ").strip() == f"All three hit about {round(pall * 100)}%", f"short: all-three chance is the product ({round(pall * 100)}%; page {page.inner_text('#sveasy .all3')!r})")
            alt = page.query_selector("#sveasy a.bsbtn.alt")
            if alt:
                bk = alt.get_attribute("data-book"); legs = [next(l for l in BD["legs"] if l["pl"] == e["pl"] and l["m"] == e["m"] and round(l["ln"], 1) == round(e["ln"], 1)) for e in SJ["easy"]]
                dfd = 1.0; dbk = 1.0
                for l in legs: dfd *= dec(l["o"]); dbk *= dec(l["bks"][bk]["o"])
                check(dbk > dfd * 1.01, f"short: the second book button only shows when it pays more ({bk}: {dbk:.3f} vs FanDuel {dfd:.3f})")
        # ---- home: the new blocks do not break the page; the record leads with the Daily Sweep
        page.goto(BASE + "/"); page.wait_for_timeout(300)
        check(page.inner_text("#record .rec div:first-child span").startswith("The Daily Sweep"), "home: Track record leads with the Daily Sweep")
        UD = json.load(open(os.path.join(OUT, "under_day.json")))
        has = page.query_selector("#bsunder") is not None
        check(has == bool(UD.get("picks")), f"home: Under of the day card present only when there is a pick ({len(UD.get('picks') or [])} picks)")
        if has:
            vis = page.evaluate("[...document.querySelectorAll('#bsunder .udcard')].filter(e => !e.hidden).length"); check(vis == 1, "home: exactly one Under of the day card shows (the next game day's)")
        # ---- live: the win card draws
        page.goto(BASE + "/live/"); page.wait_for_function("() => !!window.__bsWin", timeout=15000)
        keys = page.evaluate("window.__bsWinKeys(4)")
        if len(keys) >= 3:
            page.evaluate("(k) => { window.__bsWin(k, 'Sunday favorites', 285, 10); }", keys[:4]); page.wait_for_timeout(900)
            px = page.evaluate("""() => { const c = window.__bsWinCard, x = c.getContext('2d'); const a = x.getImageData(540, 322, 1, 1).data, b = x.getImageData(20, 20, 1, 1).data, t = x.getImageData(0, 760, 1080, 300).data;
                let light = 0; for(let i = 0; i < t.length; i += 4) if(t[i] > 200 && t[i + 1] > 200) light++; return {w: c.width, h: c.height, mid: [a[0], a[1], a[2]], corner: [b[0], b[1], b[2]], light}; }""")
            check(px["w"] == 1080 and px["h"] == 1350, "win card: 1080 x 1350")
            check(px["corner"] == [14, 24, 32], f"win card: brand background ({px['corner']})")
            check(px["light"] > 800, f"win card: the legs are written on it ({px['light']} light pixels in the leg area)")
            try:
                png = page.evaluate("window.__bsWinCard.toDataURL('image/png')"); import base64
                open("/tmp/win_card.png", "wb").write(base64.b64decode(png.split(",", 1)[1]))
            except Exception: pass
        else: check(False, "win card: the live page has no leg keys to build a slip from")
        check(not errs, f"no page errors on boost / shop / short / home / live: {errs[:3]}")
        b.close()


def logic_checks():
    import under_day as UD, stale_lines as STL, shadow_slips as SH
    now = int(datetime.datetime(2026, 11, 11, 3, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000); day = 86400000
    def leg(pl, m, ln, o, p, g, fh=None, **kw):
        d = {"pl": pl, "m": m, "ln": ln, "o": o, "p": p, "bk": 1 / dec(o), "g": g, "tm": g.split("-")[0], "opp": g.split("-")[1], "pos": "WR", "fd": {"m": "42.1", "s": pl.replace(" ", "")}, "fh": fh or []}
        d.update(kw); return d
    bd = {"week": 10, "games": [{"gid": "AAA-BBB", "ko": now + day, "kick": "Thu 7:15 PM", "home": "BBB", "away": "AAA"}, {"gid": "CCC-DDD", "ko": now + 4 * day, "kick": "Sun 12:00 PM", "home": "DDD", "away": "CCC"}],
          "legs": [leg("A One", "Under Receptions", 4.5, -120, 0.60, "AAA-BBB", u=1), leg("A Two", "Under Receiving Yards", 40.5, -114, 0.70, "AAA-BBB", u=1, fh=[["watch", "Market disagrees", "x"]]),
                   leg("A Three", "Under Rushing Yards", 20.5, -114, 0.54, "AAA-BBB", u=1), leg("A Four", "Under Receptions", 3.5, -150, 0.59, "AAA-BBB", u=1),
                   leg("C One", "Under Receptions", 5.5, -110, 0.58, "CCC-DDD", u=1, fh=[["watch", "Q · plays ~64%", "x"]]), leg("C Two", "Under Passing Yards", 220.5, 100, 0.56, "CCC-DDD", u=1)]}
    picks = UD.choose(bd, now); d1, d2 = UD.day_of(now + day), UD.day_of(now + 4 * day)
    check(picks[d1]["pl"] == "A One", f"under of the day: the widest gap WITHOUT a 'Market disagrees' tag wins ({picks[d1]['pl']})")
    check(picks[d2]["pl"] == "C Two", f"under of the day: a questionable player is skipped ({picks[d2]['pl']})")
    check(all(l["pl"] not in ("A Three", "A Four") for l in UD.candidates(bd)), "under of the day: under 55% or below break-even never qualifies")
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(d + "/in"); os.makedirs(d + "/out"); os.makedirs(d + "/clone/data")
        json.dump(bd, open(d + "/out/builder_data.json", "w"))
        gl = [["Week", "Player", "Receptions", "Rec Yds", "Rush Yds", "Pass Yds", "Rush TD", "Rec TD", "Longest Rec"], ["10", "A One", "4", "50", "0", "0", "0", "1", "20"], ["10", "C Two", "0", "0", "0", "250", "0", "0", "0"], ["10", "Fav One", "5", "60", "0", "0", "0", "0", "22"]]
        json.dump({"values": gl[:1]}, open(d + "/in/gamelog.json", "w"))
        UD.build(d + "/in", d + "/out", d + "/clone", now_ms=now); log = json.load(open(d + "/out/data/under-day.json"))
        check([e["pl"] for e in log] == ["A One", "C Two"] and all(e["res"] is None for e in log), "under of the day: both game days logged, ungraded before kickoff")
        # the board changes before kickoff -> the entry follows it; after kickoff it is frozen and graded
        os.replace(d + "/out/data/under-day.json", d + "/clone/data/under-day.json")
        bd2 = json.loads(json.dumps(bd)); bd2["legs"][0]["p"] = 0.50; json.dump(bd2, open(d + "/out/builder_data.json", "w"))
        UD.build(d + "/in", d + "/out", d + "/clone", now_ms=now); log = json.load(open(d + "/out/data/under-day.json"))
        check(log[0]["pl"] == "A Two", f"under of the day: before kickoff the entry follows the board ({log[0]['pl']})")
        json.dump(bd, open(d + "/out/builder_data.json", "w")); UD.build(d + "/in", d + "/out", d + "/clone", now_ms=now); os.replace(d + "/out/data/under-day.json", d + "/clone/data/under-day.json")
        json.dump({"values": gl}, open(d + "/in/gamelog.json", "w")); json.dump(bd2, open(d + "/out/builder_data.json", "w"))
        UD.build(d + "/in", d + "/out", d + "/clone", now_ms=now + 6 * day); log = json.load(open(d + "/out/data/under-day.json")); rec = json.load(open(d + "/out/under_day.json"))["record"]
        check(log[0]["pl"] == "A One" and log[0]["res"] == "HIT" and log[1]["res"] == "MISS", f"under of the day: frozen at kickoff and graded from the game log ({[(e['pl'], e['res']) for e in log]})")
        check(rec["w"] == 1 and rec["l"] == 1 and abs(rec["units"] - (100 / 120 - 1)) < 0.011, f"under of the day: record 1-1 at the posted prices ({rec})")
        check(UD.grade({"m": "Under Receptions", "ln": 4.5, "pl": "Nobody", "week": 10}, gl)[0] == "VOID", "under of the day: a player with no row that week is VOID, not a loss")
        # shadow slips: grading with a void leg
        idx, weeks = SH.gamelog_index(d + "/in")
        check(SH.grade_leg({"pl": "Fav One", "m": "Receiving Yards", "ln": 50, "week": 10}, idx, weeks) == "HIT" and SH.grade_leg({"pl": "Fav One", "m": "Receptions", "ln": 6, "week": 10}, idx, weeks) == "MISS"
              and SH.grade_leg({"pl": "A One", "m": "Anytime TD", "ln": 1, "week": 10}, idx, weeks) == "HIT" and SH.grade_leg({"pl": "Ghost", "m": "Receptions", "ln": 1, "week": 10}, idx, weeks) == "VOID"
              and SH.grade_leg({"pl": "Fav One", "m": "Receptions", "ln": 1, "week": 11}, idx, weeks) is None, "shadow slips: over / TD / void / not-yet-in-the-log grading")
        # lines to check: only news after the last pull, only the position room, never a QB
        json.dump({"values": [["Key", "Player", "Market", "Alt", "Link", "M", "S", "Odds", "Game", "Updated"], ["k", "X", "Receptions", "1", "", "", "", "-110", "", "2026-11-10 6:24"]]}, open(d + "/in/links.json", "w"))
        news = [{"player": "B Star", "team": "AAA", "pos": "WR", "k": "bad", "tag": "News: out", "bucket": "OUT", "ts": "2026-11-11T01:00:00+00:00", "txt": "ruled out", "src": "t"},
                {"player": "Old News", "team": "CCC", "pos": "WR", "k": "bad", "tag": "News: out", "bucket": "OUT", "ts": "2026-11-10T10:00:00+00:00", "txt": "ruled out early", "src": "t"},
                {"player": "Q Back", "team": "AAA", "pos": "QB", "k": "bad", "tag": "News: out", "bucket": "OUT", "ts": "2026-11-11T02:00:00+00:00", "txt": "out", "src": "t"}]
        json.dump({"players": news}, open(d + "/in/ctx_news.json", "w"))
        bd3 = json.loads(json.dumps(bd)); bd3["legs"] += [leg("B Star", "Receptions", 5, -110, 0.5, "AAA-BBB"), leg("Old News", "Receptions", 5, -110, 0.5, "CCC-DDD"), leg("Q Back", "Passing Yards", 200, -110, 0.5, "AAA-BBB", pos="QB"),
                                                           leg("Mate One", "Receptions", 4, -130, 0.55, "AAA-BBB", proj=50), leg("Mate One", "Receptions", 6, 150, 0.35, "AAA-BBB", proj=50),
                                                           leg("Mate RB", "Rushing Yards", 50, -110, 0.5, "AAA-BBB", pos="RB"), leg("Other Team", "Receptions", 4, -110, 0.5, "CCC-DDD")]
        json.dump(bd3, open(d + "/out/builder_data.json", "w"))
        STL.build(d + "/in", d + "/out", now=datetime.datetime.fromtimestamp(now / 1000, datetime.timezone.utc)); st = json.load(open(d + "/out/stale.json"))
        check([i["out"]["pl"] for i in st["items"]] == ["B Star"], f"lines to check: only the player ruled out after the last pull, never a quarterback ({[i['out']['pl'] for i in st['items']]})")
        if st["items"]:
            names = {l["pl"] for l in st["items"][0]["legs"]}; check(names == {"Mate One"}, f"lines to check: only his position room on his team ({names})")
            check([l["ln"] for l in st["items"][0]["legs"] if l["m"] == "Receptions"] == [4], "lines to check: the rung closest to even money")
            check(len(STL.card(d + "/out")) > 200 and "pulled before the news" in STL.card(d + "/out"), "lines to check: the card says the price predates the news")


if __name__ == "__main__":
    logic_checks(); browser_checks()
    print(f"deep-dive pages: {n - len(fails)} of {n} checks passed" if fails else f"deep-dive pages: all {n} checks passed")
    sys.exit(1 if fails else 0)
