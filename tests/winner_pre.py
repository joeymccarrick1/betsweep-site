"""Early winners on the home page's Winners section, and the record they do or do not count in (sweep.RECORD_FROM, sweep.PAGES_FROM).
Week 5's Piss Missile Monday (Bills @ Rams) was posted on BetSweep's social pages before promoted bets had pages on the site. It was
first shown without being counted (11/22 1:12 AM: the tab had no misses for that week); the same morning the owner supplied the week's
nine other promos, all misses, so the record starts in Week 5 and the win counts. A win from a week BEFORE the record is still shown
and never counted: one win without its week's losses is a record with the misses left out.
Part 1 runs the builders on made-up rows; part 2 looks at the built home page when the tab carries an early winner.
  python3 tests/winner_pre.py [shots_dir]"""
import asyncio, json, os, re, sys, tempfile, threading, http.server, functools
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
import sweep as SW, home as HOME
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)

HEAD = ["Week", "Slot", "Title", "Legs (one per line: who | market | FanDuel odds)", "FanDuel odds", "FanDuel link", "Status", "Caption", "Result", "Posted", "Model % (auto)", "Fair odds (auto)", "Notes", "How to use"]
SOC = ["5", "10", "Piss Missile Monday", "Rex Runner | Rushing Yards 60+ |\nTom Test | Passing Yards 200+ |\nRex Runner | Anytime TD |", "6781", "", "HIDDEN", "Bills @ Rams, Monday night", "Hit", "2026-10-12", "", "", "", ""]
SOCMISS = [["5", str(i), f"Week five miss {i}", "Rex Runner | Rushing Yards 150+ |", "400", "", "HIDDEN", "", "Missed", "2026-10-11", "", "", "", ""] for i in (1, 2)]
PRE = ["4", "1", "Before the record", "Rex Runner | Rushing Yards 60+ |\nTom Test | Passing Yards 200+ |", "500", "", "HIDDEN", "Somewhere, Sunday", "Hit", "2026-10-04", "", "", "", ""]
NOW = ["10", "1", "Tracked winner", "Rex Runner | Rushing Yards 50+ | -200\nTom Test | Passing Yards 200+ | -150", "302", "", "LIVE", "", "Hit", "2026-11-12", "", "", "", ""]
MISS = ["10", "2", "Tracked miss", "Rex Runner | Rushing Yards 150+ | +400", "400", "", "HIDDEN", "", "Missed", "2026-11-15", "", "", "", ""]
CASH = ["9", "4", "Graded by the grader", "Tom Test | Passing Yards 200+ | -150", "150", "", "HIDDEN", "", "Cashed", "2026-11-08", "", "", "", ""]
GLH = ["Week", "Player", "Team", "Pos", "Opponent", "Pass Att", "Completions", "Pass Yds", "Pass TD", "INT", "Rush Att", "Rush Yds", "Rush TD", "Targets", "Receptions", "Rec Yds", "Rec TD"]
def glrow(w, p, pos, py, ry): return [str(w), p, "AAA", pos, "BBB", "30", "20", str(py), "1", "0", "10", str(ry), "1", "0", "0", "0", "0"]
GL = [GLH, glrow(4, "Rex Runner", "RB", 0, 99), glrow(4, "Tom Test", "QB", 222, 5), glrow(5, "Rex Runner", "RB", 0, 111), glrow(5, "Tom Test", "QB", 210, 12), glrow(10, "Rex Runner", "RB", 0, 88), glrow(10, "Tom Test", "QB", 250, 3)]
def rnd(d): return {k: [v[0], v[1], round(v[2], 2)] for k, v in sorted(d.items())}

# ---------- part 1: what the record counts ----------
check(SW.RECORD_FROM == 5 and SW.PAGES_FROM == 6, f"the record starts in Week {SW.RECORD_FROM}; promoted bets have pages from Week {SW.PAGES_FROM}")
base = SW.promo_weeks([HEAD, NOW, MISS, CASH])
check(rnd(base) == {9: [1, 1, 1.5], 10: [2, 1, 2.02]}, f"the season count reads Hit, Missed and the grader's Cashed, by week ({rnd(base)})")
w5 = SW.promo_weeks([HEAD, SOC] + SOCMISS + [NOW, MISS, CASH])
check(rnd(w5) == {5: [3, 1, 65.81], 9: [1, 1, 1.5], 10: [2, 1, 2.02]}, f"Week 5 counts: its win at the posted price and its misses at a unit each ({rnd(w5).get(5)})")
check(SW.promo_weeks([HEAD, PRE, NOW, MISS, CASH]) == base and SW.promo_weeks([HEAD, PRE]) == {}, "a win from before Week 5 changes no week's count and adds no units")

# ---------- part 1b: how Winners shows each kind ----------
def block(rows):
    d = tempfile.mkdtemp(); json.dump({"values": [HEAD] + rows}, open(os.path.join(d, "promos.json"), "w")); json.dump({"values": GL}, open(os.path.join(d, "gamelog.json"), "w")); return HOME.winners_block(d)
def text(x): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x))
h = block([NOW, MISS, SOC] + SOCMISS + [PRE]); cards = re.findall(r'<article class="wcard[^"]*">.*?</article>', h, re.S)
check(len(cards) == 3 and "3 promoted bets cashed" in h and 'class="wcard"' in cards[0] and 'class="wcard soc"' in cards[1] and 'class="wcard pre"' in cards[2], f"Winners lists all three wins, newest first, and marks the two early ones ({len(cards)} cards)")
soc = cards[1] if len(cards) == 3 else ""; st = text(soc)
check("Piss Missile Monday" in soc and ">+6781<" in soc and "$10 won $678.10" in soc and soc.count("<li>") == 3, f"the Week 5 card has the name, the posted price, the legs and what $10 won ({st[:80]})")
check("Mon 10/12 · Week 5 · Bills @ Rams, Monday night" in st, "it names its game from the row's caption (the game is not on this week's board)")
check(soc.count('class="wa"') == 2 and "111 yds" in soc and "210 yds" in soc, "its legs carry their final numbers from the game log, like any counted winner")
check("<a " not in soc and "/b/w5-10/" not in h, "it has no See the slip link (Week 5 had no slip pages)")
check("Posted on our social pages in Week 5, before promoted bets had their own pages here. It counts in the record along with that week\u2019s 2 misses.".replace("\u2019", "'") in st.replace("&#x27;", "'"), f"the card says where it was posted and that it counts, with the week's misses ({st[-150:]})")
pre = cards[2] if len(cards) == 3 else ""; pt = text(pre)
check('class="wa"' not in pre and "<a " not in pre and "Posted on our social pages in Week 4, before this site kept a record. It is shown here and is not counted in the win-loss record, which starts in Week 5." in pt,
      "a win from before the record is shown with no stats and no link, and says it is not counted")
now = cards[0] if cards else ""
check('class="wa"' in now and "88 yds" in now and '/b/w10-1/' in now and "wnote" not in now, "a winner from a week with slip pages keeps its stats and its link and carries no note")
check("Every promoted bet since Week 5, wins and misses, is on the" in h and "a slip from before that says so on its card" in h, "with a pre-record win showing, the footnote says the record starts in Week 5")
h1 = block([NOW, MISS, SOC] + SOCMISS)
check("Every promoted bet from Week 6 on, wins and misses, is on the" in h1 and "went out on our social pages and are counted in the" in h1 and "wcard pre" not in h1, "with only the Week 5 win early, the footnote says the receipts start in Week 6 and the earlier slips are in the season record")
h0 = block([NOW, MISS])
check("Posted here before kickoff at FanDuel's price. Every promoted bet, wins and misses, is on the" in h0.replace("&#x27;", "'") and "wcard pre" not in h0 and "wcard soc" not in h0, "without an early winner the section reads as it always has")
one = text(block([SOC]))
check("It counts in the record." in one and "along with" not in one, "a week with no misses on the tab does not invent any")

# ---------- part 2: the built home page ----------
try: tab = json.load(open(os.path.join(HERE, "in", "promos.json")))["values"]
except Exception: tab = []
TH = {str(c).strip().split(" (")[0]: i for i, c in enumerate(tab[0])} if tab else {}
def _wk(r):
    try: return int(float(r[TH["Week"]]))
    except Exception: return None
early = [r for r in tab[1:] if TH and len(r) > TH["Result"] and SW.res_kind(r[TH["Result"]]) == "W" and _wk(r) is not None and _wk(r) < SW.PAGES_FROM]
if not early:
    print("   (the PROMO tab carries no winner from before Week %d - nothing to look at on the page)" % SW.PAGES_FROM)
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
PW = SW.promo_weeks(tab)

from playwright.async_api import async_playwright
PORT = 8880
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    early.sort(key=lambda r: (-_wk(r), -int(float(r[TH["Slot"]] or 0))))
    want = [(str(r[TH["Title"]]).strip(), "pre" if _wk(r) < SW.RECORD_FROM else "soc", len([x for x in str(r[TH["Legs"]]).split("\n") if x.strip()]), _wk(r)) for r in early]
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}');localStorage.setItem('bs_winners_open','1')}}catch(e){{}}")
            await ctx.route("**/*", lambda r: r.continue_() if "127.0.0.1" in r.request.url else r.abort())
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1800)
            s = await pg.evaluate("""() => { var w = document.getElementById('winners'); if(!w) return null; var d = w.querySelector('details'); if(d) d.open = true;
              var cs = Array.from(w.querySelectorAll('.wcard.pre, .wcard.soc')).map(function(c){ var n = c.querySelector('.wnote'), r = c.getBoundingClientRect(); return {title: c.querySelector('h3').textContent, kind: c.classList.contains('pre') ? 'pre' : 'soc', price: (c.querySelector('.wo') || {}).textContent, legs: c.querySelectorAll('li').length, stats: c.querySelectorAll('.wa').length, links: c.querySelectorAll('a').length, note: n ? n.textContent : '', pay: (c.querySelector('.wfoot b') || {}).textContent || '', meta: c.querySelector('.wmeta').textContent, right: Math.round(r.right), noteFs: n ? parseFloat(getComputedStyle(n).fontSize) : 0}; });
              return {head: w.querySelector('h2').textContent, all: w.querySelectorAll('.wcard').length, early: cs, foot: (w.querySelector('p.none') || {}).textContent || '', over: document.documentElement.scrollWidth - innerWidth, vw: innerWidth}; }""")
            print(f"   [{theme}]", json.dumps(s, ensure_ascii=False)[:900])
            check(bool(s) and [(c["title"], c["kind"], c["legs"]) for c in s["early"]] == [w[:3] for w in want], f"[{theme}] the home page's Winners shows each early winner from the tab with all its legs ({[(c['title'], c['kind']) for c in s['early']] if s else None})")
            for c, w in zip(s["early"] if s else [], want):
                if w[1] == "soc":
                    rec = PW.get(w[3]) or [0, 0, 0]; miss = rec[0] - rec[1]
                    check(c["links"] == 0 and c["stats"] >= 1 and c["note"].startswith(f"Posted on our social pages in Week {w[3]}, before promoted bets had their own pages here. It counts in the record") and ((f"that week's {miss} miss" in c["note"].replace("\u2019", "'")) if miss else "along with" not in c["note"]) and c["price"].startswith("+") and c["pay"].startswith("$10 won $"),
                          f"[{theme}] {w[0]}: counted, says where it was posted and the week's {miss} misses, final numbers on its legs, no link ({c['price']}, {c['pay']}, {c['stats']} stats)")
                else:
                    check(c["links"] == 0 and c["stats"] == 0 and "not counted in the win-loss record" in c["note"], f"[{theme}] {w[0]}: from before the record - shown, not counted, no stats, no link")
            if s and s["early"]:
                check(s["over"] <= 0 and all(c["right"] <= s["vw"] and c["noteFs"] >= 11 for c in s["early"]) and (f"since Week {SW.RECORD_FROM}" in s["foot"] if any(w[1] == "pre" for w in want) else f"from Week {SW.PAGES_FROM} on" in s["foot"]), f"[{theme}] the cards fit the phone and the footnote says where the receipts start ({s['over']}px sideways)")
            if SHOTS: await pg.evaluate("document.querySelector('#winners .wcard.pre, #winners .wcard.soc').scrollIntoView({block: 'center'})"); await pg.wait_for_timeout(250); await pg.screenshot(path=f"{SHOTS}/winner-early-{theme}.png")
            check(not errs, f"[{theme}] no script errors {errs[:2]}"); await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
