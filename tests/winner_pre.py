"""A winner from before the site kept a record (owner 11/22: the Week 5 Piss Missile Monday, Bills @ Rams, posted on BetSweep's social
pages before the PROMO tab existed) is SHOWN in the home page's Winners and never COUNTED: the tab has no losses for those weeks, so
counting their one win would be a record with the misses left out (sweep.RECORD_FROM).
Part 1 runs the builders on made-up rows; part 2 looks at the built home page when the tab carries such a row.
  python3 tests/winner_pre.py [shots_dir]"""
import asyncio, json, os, re, sys, tempfile, threading, http.server, functools
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
import sweep as SW, home as HOME
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)

HEAD = ["Week", "Slot", "Title", "Legs (one per line: who | market | FanDuel odds)", "FanDuel odds", "FanDuel link", "Status", "Caption", "Result", "Posted", "Model % (auto)", "Fair odds (auto)", "Notes", "How to use"]
PRE = ["5", "1", "Piss Missile Monday", "Rex Runner | Rushing Yards 60+ |\nTom Test | Passing Yards 200+ |\nRex Runner | Anytime TD |", "6781", "", "HIDDEN", "Bills @ Rams, Monday night", "Hit", "2026-10-12", "", "", "", ""]
NOW = ["10", "1", "Tracked winner", "Rex Runner | Rushing Yards 50+ | -200\nTom Test | Passing Yards 200+ | -150", "302", "", "LIVE", "", "Hit", "2026-11-12", "", "", "", ""]
MISS = ["10", "2", "Tracked miss", "Rex Runner | Rushing Yards 150+ | +400", "400", "", "HIDDEN", "", "Missed", "2026-11-15", "", "", "", ""]
CASH = ["9", "4", "Graded by the grader", "Tom Test | Passing Yards 200+ | -150", "150", "", "HIDDEN", "", "Cashed", "2026-11-08", "", "", "", ""]
GLH = ["Week", "Player", "Team", "Pos", "Opponent", "Pass Att", "Completions", "Pass Yds", "Pass TD", "INT", "Rush Att", "Rush Yds", "Rush TD", "Targets", "Receptions", "Rec Yds", "Rec TD"]
def glrow(w, p, pos, py, ry): return [str(w), p, "AAA", pos, "BBB", "30", "20", str(py), "1", "0", "10", str(ry), "1", "0", "0", "0", "0"]
GL = [GLH, glrow(5, "Rex Runner", "RB", 0, 111), glrow(5, "Tom Test", "QB", 210, 12), glrow(10, "Rex Runner", "RB", 0, 88), glrow(10, "Tom Test", "QB", 250, 3)]

# ---------- part 1: the record never counts it ----------
base = SW.promo_weeks([HEAD, NOW, MISS, CASH])
check({k: [v[0], v[1], round(v[2], 2)] for k, v in base.items()} == {10: [2, 1, 2.02], 9: [1, 1, 1.5]}, f"the season count reads Hit, Missed and the grader's Cashed, by week ({ {k: [v[0], v[1], round(v[2], 2)] for k, v in sorted(base.items())} })")
check(SW.promo_weeks([HEAD, PRE, NOW, MISS, CASH]) == base, "a Week 5 win on the tab changes no week's count and adds no units")
check(SW.RECORD_FROM == 6 and 5 not in SW.promo_weeks([HEAD, PRE]) and SW.promo_weeks([HEAD, PRE]) == {}, "with only that row on the tab there is no record at all")
check(SW.promo_weeks([HEAD, ["6", "1", "Week six win", "x | Anytime TD | +100", "100", "", "HIDDEN", "", "Won", "", "", "", "", ""]]) == {6: [1, 1, 1.0]}, "Week 6 itself is counted")

# ---------- part 1b: the Winners section shows it, marked ----------
def block(rows):
    d = tempfile.mkdtemp(); json.dump({"values": [HEAD] + rows}, open(os.path.join(d, "promos.json"), "w")); json.dump({"values": GL}, open(os.path.join(d, "gamelog.json"), "w")); return HOME.winners_block(d)
h = block([NOW, MISS, PRE]); cards = re.findall(r'<article class="wcard[^"]*">.*?</article>', h, re.S)
check(len(cards) == 2 and "2 promoted bets cashed" in h and 'class="wcard pre"' in cards[1] and 'class="wcard"' in cards[0], f"Winners lists both wins, newest first, and the Week 5 one is marked ({len(cards)} cards)")
pre = cards[1] if len(cards) == 2 else ""; txt = re.sub(r"<[^>]+>", " ", pre); txt = re.sub(r"\s+", " ", txt)
check("Piss Missile Monday" in pre and ">+6781<" in pre and "$10 won $678.10" in pre and pre.count("<li>") == 3, f"its card has the name, the posted price, the legs and what $10 won ({txt[:90]})")
check("Mon 10/12 · Week 5 · Bills @ Rams, Monday night" in txt, "it names its game from the row's caption (the game is not on this week's board)")
check('class="wa"' not in pre and "111" not in pre and "210" not in pre, "no stat is printed beside its legs: the site did not grade that week")
check("<a " not in pre and "/b/w5-1/" not in h, "it has no See the slip link (there is no page for it)")
check("Posted on our social pages in Week 5, before this site kept a record. It is shown here and is not counted in the win-loss record, which starts in Week 6." in txt, "the card says where it was posted and that no record counts it")
now = cards[0] if cards else ""
check('class="wa"' in now and "88 yds" in now and '/b/w10-1/' in now and "wnote" not in now, "a tracked winner keeps its stats and its link and carries no such note")
check("Every promoted bet since Week 6, wins and misses, is on the" in h and "a slip from before that says so on its card" in h, "the section's footnote says the record starts in Week 6")
h0 = block([NOW, MISS])
check("Posted here before kickoff at FanDuel's price. Every promoted bet, wins and misses, is on the" in h0.replace("&#x27;", "'") and "wcard pre" not in h0, "without such a row the section reads as it always has")

# ---------- part 2: the built home page ----------
try: tab = json.load(open(os.path.join(HERE, "in", "promos.json")))["values"]
except Exception: tab = []
TH = {str(c).strip().split(" (")[0]: i for i, c in enumerate(tab[0])} if tab else {}
def _wk(r):
    try: return int(float(r[TH["Week"]]))
    except Exception: return None
live_pre = [r for r in tab[1:] if TH and len(r) > TH["Result"] and SW.res_kind(r[TH["Result"]]) == "W" and _wk(r) is not None and _wk(r) < SW.RECORD_FROM]
if not live_pre:
    print("   (the PROMO tab carries no winner from before Week %d - nothing to look at on the page)" % SW.RECORD_FROM)
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)

from playwright.async_api import async_playwright
PORT = 8880
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    want = [str(r[TH["Title"]]).strip() for r in live_pre]; nlegs = [len([x for x in str(r[TH["Legs"]]).split("\n") if x.strip()]) for r in live_pre]
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}');localStorage.setItem('bs_winners_open','1')}}catch(e){{}}")
            await ctx.route("**/*", lambda r: r.continue_() if "127.0.0.1" in r.request.url else r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            s = await pg.evaluate("""() => { var w = document.getElementById('winners'); if(!w) return null; var d = w.querySelector('details'); if(d) d.open = true;
              var cs = Array.from(w.querySelectorAll('.wcard.pre')).map(function(c){ var n = c.querySelector('.wnote'), r = c.getBoundingClientRect(); return {title: c.querySelector('h3').textContent, price: (c.querySelector('.wo') || {}).textContent, legs: c.querySelectorAll('li').length, stats: c.querySelectorAll('.wa').length, links: c.querySelectorAll('a').length, note: n ? n.textContent : '', pay: (c.querySelector('.wfoot b') || {}).textContent || '', meta: c.querySelector('.wmeta').textContent, right: Math.round(r.right), noteFs: n ? parseFloat(getComputedStyle(n).fontSize) : 0}; });
              return {head: w.querySelector('h2').textContent, all: w.querySelectorAll('.wcard').length, pre: cs, foot: (w.querySelector('p.none') || {}).textContent || '', over: document.documentElement.scrollWidth - innerWidth, vw: innerWidth}; }""")
            print(f"   [{theme}]", json.dumps(s, ensure_ascii=False)[:900])
            check(bool(s) and [c["title"] for c in s["pre"]] == want and [c["legs"] for c in s["pre"]] == nlegs, f"[{theme}] the home page's Winners shows the pre-record winner from the tab with all its legs ({[c['title'] for c in s['pre']] if s else None})")
            if s and s["pre"]:
                c = s["pre"][0]
                check(c["stats"] == 0 and c["links"] == 0 and "not counted in the win-loss record" in c["note"] and c["price"].startswith("+") and c["pay"].startswith("$10 won $"), f"[{theme}] marked as posted before the record, no stats, no link, price and payout shown ({c['price']}, {c['pay']})")
                check(s["over"] <= 0 and c["right"] <= s["vw"] and c["noteFs"] >= 11 and "since Week 6" in s["foot"], f"[{theme}] it fits the phone and the footnote names Week 6 ({s['over']}px sideways)")
            if SHOTS: await pg.evaluate("document.querySelector('#winners .wcard.pre').scrollIntoView({block: 'center'})"); await pg.wait_for_timeout(250); await pg.screenshot(path=f"{SHOTS}/winner-pre-{theme}.png")
            check(not errs, f"[{theme}] no script errors {errs[:2]}"); await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
