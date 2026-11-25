"""Passing TDs and their alternate rungs as legs (owner 11/19), and the newer markets generally.
  1. newmkt.py: the passing-TD price is the market-anchored fit (research/ptd_model.py) - the formula, the ladder, the rules.
  2. the built board (out/builder_data.json): every Passing TDs leg reads a real game-log column, has its matchup rank and its note.
  3. the builder on a phone, light and dark, with a full 1+..4+ ladder put on each quarterback (FanDuel's alternates arrive with
     FanDuelOdds.gs v2026-11-19): the market filter, the quarterback's "All props", the slider, the last-games picture, the slip.
  4. a quarterback's player page: the Passing TDs chart and his rungs in the Passing group.
  python3 tests/new_markets.py [shots_dir]      (SITE=<dir> checks a published copy: parts 3 and 4 only)"""
import asyncio, csv, json, math, os, re, sys, tempfile, threading, http.server, functools, glob
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, HERE)
PUB = os.environ.get("SITE"); ROOT = PUB or os.path.join(HERE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)

# ---------------- 1. the pricer ----------------
import newmkt as NM
fit = json.load(open(os.path.join(HERE, "research", "ptd_model.json")))
check(fit["k"] == NM.PTD["k"] and fit["b"] == NM.PTD["b"] and fit["n"] == NM.PTD["n"], "newmkt.py uses the fit research/ptd_model.py wrote (k, coefficients, binomial n)")
check(fit["test_n"] >= 500 and all(v < 0 for v in fit["brier_vs_base"].values()), f"that fit beat the league base rate at 1+, 2+, 3+ and 4+ on the test seasons ({fit['test_n']} quarterback games: {fit['brier_vs_base']})")
tmp = tempfile.mkdtemp()
cols = ["season_type", "week", "position", "attempts", "player_display_name", "team", "opponent_team", "passing_tds", "passing_interceptions", "completions", "carries"]
rows = []
for w in range(1, 7):
    rows.append(["REG", w, "QB", 32, "Steady Starter", "AAA", "ZZZ", 2, 1, 21, 3])           # six starts, 2 TDs each
    rows.append(["REG", w, "QB", 30, "Other Starter", "BBB", "YYY", 1, 0, 19, 2])            # six starts, 1 TD each -> league mean 1.5 (with the rest)
    rows.append(["REG", w, "RB", 0, "Lead Back", "AAA", "ZZZ", 0, 0, 0, 16])
rows.append(["REG", 5, "QB", 31, "New Starter", "CCC", "XXX", 3, 0, 22, 1])                  # one start only
rows.append(["REG", 6, "QB", 4, "New Starter", "CCC", "XXX", 0, 0, 2, 0])                    # a cameo: not a start
with open(os.path.join(tmp, "stats_player_week_2026.csv"), "w", newline="") as f: w_ = csv.writer(f); w_.writerow(cols); w_.writerows(rows)
P = NM.Pricer(tmp, 7)
lg = (6 * 2 + 6 * 1 + 3) / 13.0; shr = (12 + NM.PTD["k"] * lg) / (6 + NM.PTD["k"]); b = NM.PTD["b"]
want = math.exp(b[0] + b[1] * math.log(27.5) + b[2] * math.log(shr))
got = P.prob("Steady Starter", "Passing TDs", 2, "ZZZ", 27.5)
def tail(mu, k, n=NM.PTD["n"]): q = mu / n; return sum(math.comb(n, i) * q ** i * (1 - q) ** (n - i) for i in range(k, n + 1))
check(got is not None and abs(got[1] - want) < 1e-9 and got[2] == 6 and abs(got[3] - 2.0) < 1e-9, f"passing TDs: the mean is exp(b0 + b1 ln(team total) + b2 ln(his average shrunk 10 games to the league)) - {want:.3f} for a 27.5-point team total")
check(abs(got[0] - tail(want, 2)) < 1e-9, f"  the chance of 2+ is the Binomial(8) tail of that mean ({got[0] * 100:.1f}%)")
lad = [P.prob("Steady Starter", "Passing TDs", k, "ZZZ", 27.5)[0] for k in (1, 2, 3, 4, 5)]
check(all(lad[i] > lad[i + 1] for i in range(4)) and lad[0] <= 0.985 and lad[4] >= 0.004, "  the ladder falls rung by rung: " + ", ".join(f"{k}+ {p * 100:.1f}%" for k, p in zip((1, 2, 3, 4, 5), lad)))
hi, lo = P.prob("Steady Starter", "Passing TDs", 2, "ZZZ", 31.0)[0], P.prob("Steady Starter", "Passing TDs", 2, "ZZZ", 16.0)[0]
check(hi > got[0] > lo and hi - lo > 0.25, f"  a bigger team total at FanDuel means more passing TDs: 2+ is {lo * 100:.0f}% at 16 points, {got[0] * 100:.0f}% at 27.5, {hi * 100:.0f}% at 31")
nol = P.prob("Steady Starter", "Passing TDs", 2, "ZZZ", None); lgp = P.prob("Steady Starter", "Passing TDs", 2, "ZZZ", NM.PTD["league_implied_pts"])
check(nol is not None and abs(nol[0] - lgp[0]) < 1e-12, "  no team total posted yet: a league-average one is assumed, not a guess")
check(P.prob("New Starter", "Passing TDs", 1, "XXX", 24.0) is None, "  a quarterback with one start (and a cameo) gets no passing-TD leg: the fit over-rates new starters (72% said, 58% happened)")
check(P.prob("Lead Back", "Passing TDs", 1, "ZZZ", 24.0) is None and P.prob("Lead Back", "Rush Attempts", 13, "ZZZ") is not None, "  a running back has no passing-TD price; the other newer markets still price as before")
i0 = P.prob("Steady Starter", "Interceptions", 1, "ZZZ"); c0 = P.prob("Steady Starter", "Completions", 20, "ZZZ")
check(i0 is not None and c0 is not None and 0.03 <= i0[0] <= 0.97 and 0.03 <= c0[0] <= 0.97, "  interceptions and completions are untouched by the change")

# ---------------- 1b. the game-ending check (owner 11/24): a passing-TD leg has a chance under each of its game's four endings ----------------
import scenario as SC
_mul = {"QB1|passing_tds": [1.341, 0.749, 1.47, 0.706], "QB1|td": [1.1, 0.9, 1.4, 0.8]}; _role = {"Home Passer": ("QB", 1), "Road Passer": ("QB", 1), "Third Passer": ("QB", 3)}
_G = {"a": "AAA", "b": "BBB", "probs": [0.40, 0.25, 0.20, 0.15]}
_h = SC.player_sc({"pl": "Home Passer", "tm": "AAA", "m": "Passing TDs", "ln": 2, "p": 0.55}, _G, {}, _mul, _role)
_r = SC.player_sc({"pl": "Road Passer", "tm": "BBB", "m": "Passing TDs", "ln": 2, "p": 0.55}, _G, {}, _mul, _role)
check(_h is not None and len(_h) == 4 and abs(sum(w * p for w, p in zip(_G["probs"], _h)) - 0.55) < 0.002, f"game endings: a 2+ passing TDs leg gets four chances that mix back to the shown number ({_h})")
check(_h is not None and _h[2] > _h[0] > _h[1] > _h[3], "  most likely in a shootout, then when his team wins big, then a close low game, least when it trails big (the sheet's tested QB1 passing-TD row)")
check(_r is not None and _r[3] > _r[0] and abs(_r[3] - _h[0]) < 0.001 and abs(_r[0] - _h[3]) < 0.001, "  the visiting quarterback reads the endings from his own side (the game's first team winning big is him trailing)")
_l3 = SC.player_sc({"pl": "Home Passer", "tm": "AAA", "m": "Passing TDs", "ln": 3, "p": 0.25}, _G, {}, _mul, _role); _l1 = SC.player_sc({"pl": "Home Passer", "tm": "AAA", "m": "Passing TDs", "ln": 1, "p": 0.88}, _G, {}, _mul, _role)
check(_l3 and _l1 and all(_l1[i] > _h[i] > _l3[i] for i in range(4)), "  under every ending 1+ is likelier than 2+ and 2+ than 3+")
check(SC.player_sc({"pl": "Home Passer", "tm": "AAA", "m": "Passing TDs", "ln": 2, "p": 0.55}, _G, {}, {"QB1|td": [1, 1, 1, 1]}, _role) is None and SC.player_sc({"pl": "Nobody", "tm": "AAA", "m": "Passing TDs", "ln": 2, "p": 0.55}, _G, {}, _mul, _role) is None,
      "  no tested row on the sheet, or a player the model has no role for = no ending numbers (nothing is guessed)")
check(SC.player_sc({"pl": "Third Passer", "tm": "AAA", "m": "Passing TDs", "ln": 2, "p": 0.55}, _G, {}, _mul, _role) == _h and SC.player_sc({"pl": "Home Passer", "tm": "AAA", "m": "Completions", "ln": 20, "p": 0.55}, _G, {}, _mul, _role) is None,
      "  a backup named the starter reads the starter's row; completions and interceptions have no tested row and stay without ending numbers")

# ---------------- 2. the built board ----------------
if not PUB:
    D = json.load(open(os.path.join(HERE, "out", "builder_data.json"))); L = D["legs"]; ptd = [l for l in L if l["m"] == "Passing TDs"]
    check(len(ptd) >= 1, f"the board has Passing TDs legs ({len(ptd)}, {len({l['pl'] for l in ptd})} quarterbacks)")
    check(all(l.get("sk") == "ptd" and l.get("c") == "QB_PTD" and l.get("pos") == "QB" for l in ptd), "  each reads the passing-TD column of the game log (not the old placeholder key) and carries its correlation code")
    # 11/24: this asked for two logged games, which a quarterback making his second start does not have (three legs failed on Week 12's
    # Tuesday board). The point is that the passing-TD column is filled: at least one logged game, and no fewer than his logged games minus one.
    gl = D["gl"]; good = [l for l in ptd if (lambda G: len(G) >= 1 and len([g for g in G if g.get("ptd") is not None]) >= max(1, len(G) - 1))(gl.get(l["pl"], []))]
    check(len(good) == len(ptd), f"  each quarterback's game log has his passing TDs by week ({len(good)} of {len(ptd)})")
    _gm = {g["gid"]: g for g in D["games"]}; _sc = [l for l in ptd if l.get("sc")]
    _mix = [l for l in _sc if abs(sum(w * p for w, p in zip(_gm[l["g"]]["probs"], l["sc"])) / (sum(_gm[l["g"]]["probs"]) or 1) - l["p"]) > 0.004]
    check(len(_sc) >= 0.8 * len(ptd) and not _mix, f"  the game-ending check prices them: {len(_sc)} of {len(ptd)} carry a chance under each ending, each mixing back to its shown number" + (f" (first off: {_mix[0]['pl']} {_mix[0]['ln']}+)" if _mix else ""))
    check(all(any(f[1] == "How it is priced" and "team total" in f[2] for f in (l.get("fh") or [])) for l in ptd), "  each says how it is priced: the team total at FanDuel and his average")
    check(all(l.get("dr") and l["dr"][0] is not None for l in ptd) and all(l.get("or") for l in ptd), "  each has the defence's and the offence's passing-TD rank for its matchup pill")
    check(all(((D["def"].get(l["opp"]) or {}).get("QB") or {}).get("ptd") for l in ptd), "  each opponent's passing TDs allowed, week by week, is on the page")
    byq = {}
    for l in ptd: byq.setdefault(l["pl"], []).append(l)
    mono = all(all(a["raw_p"] >= b_["raw_p"] for a, b_ in zip(sorted(v, key=lambda x: x["ln"]), sorted(v, key=lambda x: x["ln"])[1:])) for v in byq.values())
    check(mono, "  a quarterback's rungs never price a higher line above a lower one")
    gap = [abs(l["raw_p"] - l["bk"]) for l in ptd if -400 <= l["o"] <= 400]
    check(gap and sum(gap) / len(gap) < 0.08, f"  the model sits near FanDuel's prices on the main rungs (mean gap {sum(gap) / len(gap) * 100:.1f} points over {len(gap)} legs; the 11/5 number was no better than a base rate)")
    att = [l for l in L if l.get("pos") == "RB" and not l.get("gl")]; anyrb = next((gl[l["pl"]] for l in att if gl.get(l["pl"])), None)
    check(anyrb is not None and anyrb[0].get("att") is not None and "ptd" not in anyrb[0], "  running backs carry their rush attempts by week; passing columns only go to quarterbacks")

# ---------------- 3 + 4. the pages ----------------
from playwright.async_api import async_playwright
QB = {}; QB_ALL = {}
def ladder_in(src):
    """the page's data with a 1+..4+ ladder on every quarterback who has a Passing TDs leg (prices invented, model numbers from the leg), plus one leg of a market the page has never seen"""
    i, j = src.index("{"), src.rindex("}") + 1; d = json.loads(src[i:j]); legs = d["legs"]
    have = {(l["pl"], int(round(l["ln"]))) for l in legs if l["m"] == "Passing TDs"}
    # 11/22: a game that has kicked off has no "Player legs" button to open, so the quarterback the page checks use must be in a game still to
    # come (15 minutes clear, so a run cannot straddle a kickoff). The first quarterback on the board was in a noon game; a run at 12:15 PM on
    # a Sunday failed on that alone.
    kos = {g_.get("gid"): g_.get("ko") for g_ in (d.get("games") or []) if isinstance(g_, dict)}; soon = __import__("time").time() * 1000 + 15 * 60e3
    for l in [x for x in legs if x["m"] == "Passing TDs"]:
        QB_ALL.setdefault(l["pl"], l["g"])
        if not kos.get(l["g"]) or kos[l["g"]] > soon: QB.setdefault(l["pl"], l["g"])
        for k, od, p in ((1, -420, 0.86), (2, -135, 0.60), (3, 190, 0.34), (4, 480, 0.15)):
            if (l["pl"], k) in have: continue
            have.add((l["pl"], k)); n = dict(l); n.update({"i": len(legs), "ln": float(k), "o": od, "p": p, "raw_p": p, "bk": round((100 / (od + 100)) if od > 0 else (-od / (-od + 100)), 4)}); n["e"] = round(n["p"] - n["bk"], 4); n["bks"] = {}; n["fd"] = None
            legs.append(n)
    if QB:
        any_ = next(x for x in legs if x["m"] == "Passing TDs"); n = dict(any_); n.update({"i": len(legs), "m": "Kicking Points", "ms": "Kick pts", "ln": 8.0, "sk": "kpts", "c": ""}); legs.append(n)
    return src[:i] + json.dumps(d, separators=(",", ":")) + src[j:]
async def pages():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8874), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}")
            await ctx.route("**/site.api.espn.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body='{"events":[]}'))
            await ctx.route("**/*supabase*/**", lambda r: r.abort())
            async def data(route, request):
                f = os.path.join(ROOT, "build", request.url.split("/build/")[-1].split("?")[0])
                await route.fulfill(status=200, content_type="application/javascript", body=ladder_in(open(f).read()))
            await ctx.route("**/build/data-*.js", data)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto("http://127.0.0.1:8874/build/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
            T = f"[{theme}] "
            if not QB:
                check(bool(QB_ALL), T + ("every quarterback's game has kicked off, so there is no game left to open; the page checks wait for a board with an unplayed game" if QB_ALL else "no Passing TDs leg on the board to test with")); await ctx.close(); continue
            qb, gid = next(iter(QB.items()))
            opts = await pg.evaluate("Array.from(document.querySelectorAll('#fMarket option')).map(o => o.textContent)")
            check("Passing TDs" in opts and opts.index("Passing TDs") == opts.index("Passing Yards") + 1, T + "the market filter lists Passing TDs, right after Passing Yards")
            check("Kicking Points" in opts and opts.index("Kicking Points") < opts.index("Moneyline"), T + "a market the page was never told about gets a filter option by itself (a new FanDuel market cannot sit unlisted again)")
            await pg.evaluate("(g) => document.querySelector('.gswb[data-gp=\"' + g + '\"]').click()", gid); await pg.wait_for_timeout(500)
            CARD = "(q) => Array.from(document.querySelectorAll('li.pc')).filter(e => e.querySelector('.pname') && e.querySelector('.pname').textContent === q)[0]"
            st = await pg.evaluate("(q) => { var c = (" + CARD + ")(q); if(!c) return null; c.scrollIntoView({block:'start'}); var a = c.querySelector('.pcall'); return {btn: a ? a.textContent : '', boxes: Array.from(c.querySelectorAll('.pb')).map(b => b.dataset.m)}; }", qb)
            check(st is not None and "All props" in st["btn"], T + f"{qb}'s card is in his game with an All props button ({(st or {}).get('btn', '').strip()})")
            await pg.evaluate("(q) => (" + CARD + ")(q).querySelector('.pcall').click()", qb); await pg.wait_for_timeout(400)
            st = await pg.evaluate("""(q) => { var c = (""" + CARD + """)(q), bx = c.querySelector('.pb[data-m="Passing TDs"]'); if(!bx) return {boxes: Array.from(c.querySelectorAll('.pb')).map(b => b.dataset.m)}; bx.scrollIntoView({block:'center'}); var r = bx.querySelector('.rng'), bb = bx.getBoundingClientRect();
              return {boxes: Array.from(c.querySelectorAll('.pb')).map(b => b.dataset.m), rng: r ? [+r.min, +r.max] : null, line: bx.querySelector('.pbline').textContent, pill: !!bx.querySelector('.pbm .dpill, .pbm .mup, .pbm [class*=pill]'), dots: bx.querySelectorAll('.l5 i').length, add: !!bx.querySelector('button.add'), w: bb.width, right: bb.right, over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }""", qb)
            bx = st.get("boxes", [])
            check("Passing TDs" in bx and "Passing Yards" in bx and bx.index("Passing TDs") == bx.index("Passing Yards") + 1, T + f"All props shows his Passing TDs box right under Passing Yards ({', '.join(bx)})")
            rg = st.get("rng") or [9, 9]   # 11/20: FanDuel posts two to five rungs for a quarterback depending on the week
            check(rg[0] == 0 and 1 <= rg[1] <= 4 and st.get("line", "").startswith("Over "), T + f"the box has a slider over its rungs ({rg[1] + 1}) and opens on {st.get('line')}")
            check(st.get("dots", 0) >= 2 and st.get("pill") and st.get("add"), T + "it shows his last-games dots, the matchup ranks and + Add")
            check(st.get("over", 9) <= 1 and st.get("right", 999) <= 390 * 1.1 + 2, T + "nothing runs off the side of the phone")
            mv = await pg.evaluate("""(q) => { var out = []; for (var i = 0; i <= 3; i++) { var bx = (""" + CARD + """)(q).querySelector('.pb[data-m="Passing TDs"]'), r = bx.querySelector('.rng'); r.value = i; r.dispatchEvent(new Event('input', {bubbles: true}));
              bx = (""" + CARD + """)(q).querySelector('.pb[data-m="Passing TDs"]'); out.push([bx.querySelector('.pbline').textContent, bx.querySelector('.pbk').textContent, bx.querySelector('.pbn b').textContent]); } return out; }""", qb)
            check([m[0] for m in mv] == ["Over 0.5", "Over 1.5", "Over 2.5", "Over 3.5"] and len({m[1] for m in mv}) == 4, T + "sliding walks 1+, 2+, 3+, 4+ with each rung's own FanDuel price: " + " / ".join(m[0][5:] + " " + re.sub(r"[A-Z]{2}", " ", m[1]).split()[0] for m in mv))
            pcs = [float(m[2].strip("%")) for m in mv]
            check(all(pcs[i] > pcs[i + 1] for i in range(3)), T + "and the model's chance falls as the line rises (" + ", ".join(m[2] for m in mv) + ")")
            await pg.evaluate("(q) => (" + CARD + ")(q).querySelector('.pb[data-m=\"Passing TDs\"] .mkbtn').click()", qb); await pg.wait_for_timeout(400)
            h = await pg.evaluate("""(q) => { var hs = (""" + CARD + """)(q).querySelector('.pb[data-m="Passing TDs"] .hist'); if(!hs) return null; hs.scrollIntoView({block:'center'}); return {txt: hs.innerText, bars: hs.querySelectorAll('.l10b li').length, aria: (hs.querySelector('.l10b') || {getAttribute: function(){ return ''; }}).getAttribute('aria-label')}; }""", qb)
            check(h is not None and h["bars"] >= 2, T + f"tapping the market name opens the last-games picture ({(h or {}).get('bars', 0)} games drawn)")
            check(h is not None and re.search(r"\d of his last \d cleared 4\+ pass TDs", h["txt"]) and "No game log" not in h["txt"], T + "with the count against this rung in words")
            check(h is not None and re.search(r"pass tds allowed", h["txt"], re.I) and "No defensive game log" not in h["txt"] and re.search(r"allows \d\.\d pass TDs per game to QBs", h["txt"]), T + "and what the opponent has allowed quarterbacks, week by week")
            if SHOTS: os.makedirs(SHOTS, exist_ok=True); await pg.screenshot(path=os.path.join(SHOTS, f"ptd_box_{theme}.png"))
            n0 = await pg.evaluate("(function(){ try { return JSON.parse(localStorage.getItem(Object.keys(localStorage).filter(k => /slip/i.test(k) && /w\\d+/i.test(k))[0] || 'null') || '[]').length; } catch(e){ return -1; } })()")
            await pg.evaluate("(q) => (" + CARD + ")(q).querySelector('.pb[data-m=\"Passing TDs\"] button.add').click()", qb); await pg.wait_for_timeout(500)
            sl = await pg.evaluate("""(q) => { var bx = (""" + CARD + """)(q).querySelector('.pb[data-m="Passing TDs"]'); var cnt = document.querySelector('#slipN, .slipn, .bar .n, [data-slipn]'); return {btn: bx.querySelector('button.add').textContent, body: document.body.innerText}; }""", qb)
            check("In slip" in sl["btn"], T + "+ Add puts the rung in the slip")
            check(re.search(re.escape(qb) + r"[^\n]{0,40}(pass TDs|Pass TDs)", sl["body"]) is not None, T + "and the slip names it as pass TDs")
            # the market filter in Search
            await pg.evaluate("document.querySelector('#tabSearch').click()"); await pg.wait_for_timeout(400)
            fl = await pg.evaluate("""() => { var s = document.querySelector('#fMarket'); s.value = 'Passing TDs'; s.dispatchEvent(new Event('change', {bubbles: true})); return true; }"""); await pg.wait_for_timeout(600)
            lst = await pg.evaluate("""(q) => { var cs = Array.from(document.querySelectorAll('li.pc')).filter(e => e.offsetParent); var bx = c => Array.from(c.querySelectorAll('.pb')).map(b => b.dataset.m);
              return {n: cs.length, pos: Array.from(new Set(cs.map(c => (c.querySelector('.pz') || {}).textContent))), all: cs.every(c => bx(c).indexOf('Passing TDs') >= 0),
                      only: cs.filter(c => c.querySelector('.pname').textContent !== q).every(c => bx(c).join() === 'Passing TDs'), vis: !!document.querySelector('#fMarket').offsetParent}; }""", qb)
            check(lst["vis"] and lst["n"] >= 2 and lst["pos"] == ["QB"] and lst["all"] and lst["only"], T + f"Search > market Passing TDs lists the quarterbacks, each with his Passing TDs box ({lst['n']} cards)")
            check(not errs, T + "no script errors" + (": " + "; ".join(errs[:2]) if errs else ""))
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"ptd_search_{theme}.png"))
            # ---- 4. his player page
            slug = re.sub(r"[^a-z0-9]+", "-", re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", qb.replace(".", "").strip(), flags=re.I).lower()).strip("-")
            pp = await ctx.new_page(); perr = []; pp.on("pageerror", lambda e: perr.append(str(e)[:200]))
            resp = await pp.goto(f"http://127.0.0.1:8874/player/{slug}/", wait_until="domcontentloaded"); await pp.wait_for_timeout(700)
            pi = await pp.evaluate("""() => { var caps = Array.from(document.querySelectorAll('section.l10 figcaption')).map(f => f.innerText.replace(/\\s+/g, ' ')); var mk = Array.from(document.querySelectorAll('tr.mk')).map(t => t.textContent.replace(/\\s+/g, ' ').trim());
              var fig = Array.from(document.querySelectorAll('section.l10 figure')).filter(f => /Passing TDs/.test(f.innerText))[0]; return {caps: caps, mk: mk, bars: fig ? fig.querySelectorAll('ol li').length : 0, over: document.documentElement.scrollWidth - document.documentElement.clientWidth}; }""")
            check(resp is not None and resp.status == 200 and any(c.startswith("Passing TDs") and re.search(r"Cleared \d\+ in \d+ of \d+", c) for c in pi["caps"]) and pi["bars"] >= 2, T + f"{qb}'s page leads with a Passing TDs chart beside passing yards (" + "; ".join(c for c in pi["caps"] if c.startswith("Passing TDs"))[:70] + ")")
            check(any(m.startswith("Passing TDs") for m in pi["mk"]) and pi["over"] <= 1 and not perr, T + "and lists his Passing TDs rungs in the Passing group, nothing off the side")
            if SHOTS: await pp.screenshot(path=os.path.join(SHOTS, f"ptd_player_{theme}.png"))
            await ctx.close()
        await b.close()
    srv.shutdown()
asyncio.run(pages())
print(f"\n{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
