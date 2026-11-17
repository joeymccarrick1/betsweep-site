"""The Live page never settles a leg without real numbers (11/17).

The bug this pins down: once the build held a final score for every game that had kicked off, the page stopped asking ESPN for anything and
graded every leg against a 0-0 score and an empty box score. Five winning legs read "0 hit - 5 dead", "My week" read 0-5, and those losses
were written into the reader's saved season record.

Everything here is made up from the built page's own data, so it runs in any week: one game is kept, given a kickoff, a final score and
a box score invented so that chosen legs win, and the page clock is set around that kickoff. ESPN is faked or cut off per case.
  python3 tests/live_finals.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, glob, http.server, json, math, os, re, sys, threading
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8861; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)

_ref = re.search(r"/live/(data-[0-9a-f]+\.js)", open(os.path.join(ROOT, "live", "index.html")).read())      # the copy the page loads (a published folder keeps older ones too)
SRC = open(os.path.join(ROOT, "live", _ref.group(1)) if _ref else glob.glob(os.path.join(ROOT, "live", "data-*.js"))[0]).read(); _m = re.match(r"\s*window\.__LV\s*=\s*", SRC); D0 = json.loads(SRC[_m.end():].rstrip().rstrip(";"))
WEEK = D0["week"]; ALL = D0["legs"] + D0.get("extra", [])
def key(l): return f"{l['pl']}|{l['m']}|{int(math.floor((l.get('ln') or 1) + 0.5))}"
FIRSTKEY = {}
for _l in ALL: FIRSTKEY.setdefault(key(_l), _l)
def mine(l): return FIRSTKEY[key(l)] is l                     # the page tracks the first leg it meets for a key
def props(g): return [l for l in ALL if l.get("g") == g["gid"] and not l.get("gl") and mine(l)]
G = max(D0["games"], key=lambda g: len({l["pl"] for l in props(g)})); GID = G["gid"]; A, B = G["a"], G["b"]
P = props(G); STAT = {"Receiving Yards": 6, "Rushing Yards": 3, "Receptions": 5, "Passing Yards": 0}     # market -> slot in the build's stat row
def over(l): return l["m"] in STAT and not l.get("u")
used = set()
def take(pred):
    for l in sorted(P, key=lambda l: (l["pl"], l["m"], l.get("ln") or 0)):
        if l["pl"] not in used and pred(l): used.add(l["pl"]); return l
    return None
Y1 = take(over); Y2 = take(over); TD = take(lambda l: l["m"] == "Anytime TD"); UN = take(lambda l: l["m"].startswith("Under ") and l["m"][6:] in STAT)
WATCH = {id(l) for l in D0["legs"]}                          # the game card lists the watch-list legs only
DNP = take(lambda l: over(l) and id(l) in WATCH); ABS = take(over)   # a man who did not play (shown in the game card), and a man with no stat line
GL = [l for l in ALL if l.get("g") == GID and l.get("gl") and mine(l)]
ML = next((l for l in GL if l["m"] == "Moneyline" and l.get("tm") == A), None); OV = next((l for l in GL if l["m"] == "Total" and str(l["gl"].get("side")).upper() == "OVER"), None)
NEED = {"two yardage legs": Y1 and Y2, "an anytime-TD leg": TD, "a moneyline on the home side": ML, "an over on the total": OV, "two more players with a leg": ABS and DNP}
SA, SB = (int(OV["ln"]) + 1 if OV else 30), 7            # the made-up final: A wins, and the total clears the over
KO = (int(__import__("time").time()) // 60 * 60 + 48 * 3600) * 1000

def row(**kw):
    r = [0] * 13
    for k, v in kw.items(): r[{"pass": 0, "ptd": 1, "int": 2, "rush": 3, "rtd": 4, "rec": 5, "recy": 6, "ctd": 7, "cmp": 8, "patt": 9, "ratt": 10, "tgt": 11, "xtd": 12}[k]] = v
    return r
SLOT = {0: "pass", 3: "rush", 5: "rec", 6: "recy"}
RETURN_TD = {"on": False}                                   # when on, the scorer's touchdown is a kick return (the last number of his row), not a rush
def winbox(lose=()):
    """stat lines that make every chosen leg win (a leg named in `lose` falls short instead)"""
    box = {}
    for l in (Y1, Y2):
        box[l["pl"]] = row(**{SLOT[STAT[l["m"]]]: (max(0, int(l["ln"]) - 3) if l in lose else int(l["ln"]) + 5)})
    box[TD["pl"]] = row(rush=12, **({"xtd": 1} if RETURN_TD["on"] else {"rtd": 0 if TD in lose else 1}))
    if UN: box[UN["pl"]] = row(**{SLOT[STAT[UN["m"][6:]]]: max(0, int(math.floor(UN["ln"])) - 2)})
    return box
def data(final=True, fb="box", dnp=False, fin=True, lose=()):
    """the page's data with only the chosen game. final: its kickoff is two days ahead and the clock decides; fb: 'box' (score + stat lines),
    'score' (score only) or None (the build knows nothing); fin: whether the schedule's final-score text is there."""
    D = json.loads(json.dumps(D0)); g = next(x for x in D["games"] if x["gid"] == GID); g["ko"] = KO; g.pop("fin", None)
    if fin: g["fin"] = f"{A} {SA} – {B} {SB}"
    D["games"] = [g]; D["legs"] = [l for l in D["legs"] if l.get("g") == GID]; D["extra"] = [l for l in D.get("extra", []) if l.get("g") == GID]
    D["fb"] = {}
    if fb:
        rec = {"sc": {A: SA, B: SB}}
        if fb == "box":
            rec["box"] = winbox(lose)
            if dnp: rec["dnp"] = [DNP["pl"]]
        D["fb"][GID] = rec
    return "window.__LV = " + json.dumps(D, separators=(",", ":")) + ";"
def scoreboard(state, sa, sb, period=3, clock="8:12"):
    return {"events": [{"id": "401", "status": {"period": period, "displayClock": clock, "type": {"state": state, "completed": state == "post", "shortDetail": "Final" if state == "post" else f"{clock} - {period}"}},
        "competitions": [{"competitors": [{"team": {"abbreviation": A, "id": "1"}, "score": str(sa)}, {"team": {"abbreviation": B, "id": "2"}, "score": str(sb)}], "situation": {}}]}]}
def summary(lose=()):
    def ath(n, st): return {"athlete": {"displayName": n}, "stats": [str(x) for x in st]}
    cats = {"passing": (["completions/passingAttempts", "passingYards", "passingTouchdowns", "interceptions"], []), "rushing": (["rushingAttempts", "rushingYards", "rushingTouchdowns"], []),
            "receiving": (["receptions", "receivingYards", "receivingTouchdowns", "longReception", "receivingTargets"], [])}
    cats["kickReturns"] = (["kickReturns", "kickReturnYards", "yardsPerKickReturn", "longKickReturn", "kickReturnTouchdowns"], [])     # ESPN's shape as far as known; not checked against a live answer
    for n, r in winbox(lose).items():
        if r[0]: cats["passing"][1].append(ath(n, ["20/30", r[0], r[1], r[2]]))
        if r[3] or r[4]: cats["rushing"][1].append(ath(n, [12, r[3], r[4]]))
        if r[5] or r[6]: cats["receiving"][1].append(ath(n, [r[5] or 4, r[6], r[7], 18, 7]))
        if r[12]: cats["kickReturns"][1].append(ath(n, [1, 98, "98.0", 98, r[12]]))
    return {"boxscore": {"players": [{"team": {"abbreviation": A}, "statistics": [{"name": k, "keys": v[0], "athletes": v[1]} for k, v in cats.items()]}]},
            "scoringPlays": [{"type": {"text": "Rushing Touchdown"}, "text": f"{TD['pl']} 3 Yd Run (kick)"}] if TD not in lose and not RETURN_TD["on"] else []}

CLOCK = "(function(){var T=+(localStorage.getItem('t_now')||0);if(!T)return;var R=Date.now,S=R();Date.now=function(){return T+(R()-S)};var D0=Date;function ND(){if(arguments.length===0)return new D0(D0.now());return new (Function.prototype.bind.apply(D0,[null].concat([].slice.call(arguments))))()}ND.now=D0.now;ND.parse=D0.parse;ND.UTC=D0.UTC;ND.prototype=D0.prototype;window.Date=ND;})();"
READ = """(gid) => { var q = function(s, r){ return (r || document).querySelector(s); }, qa = function(s, r){ return Array.from((r || document).querySelectorAll(s)); };
  var card = q('.slipcard[data-sid="s1"]'), tab = function(k){ var b = q('.hubb[data-hub="' + k + '"] small'); return b ? b.textContent : null; };
  var gsec = document.getElementById('lv-' + gid), o = document.documentElement, log = null; try { log = JSON.parse(localStorage.getItem('bs_log_w' + window.__LV.week)); } catch(e){}
  return {slip: card ? q('.scp b', card).textContent : null, slipSub: card ? q('.scp small', card).textContent : null, facts: card ? q('.scn small', card).textContent : null, money: card ? qa('.scm span', card).map(function(x){ return x.textContent; }) : [],
          share: !!(card && q('.winshare', card)), rows: card ? qa('table.lvt tr', card).map(function(tr){ return tr.textContent.replace(/\\s+/g, ' ').trim(); }) : [],
          week: tab('__log'), season: tab('__season'), log: log,
          score: gsec ? q('.mid b', gsec).textContent : null, tog: gsec ? q('.ghd2 .tog', gsec).textContent : null, subs: gsec ? qa('h4.subtog', gsec).map(function(h){ return h.textContent; }) : [], gopen: !!(gsec && gsec.classList.contains('open')),
          bar: (q('#lv .lvbar') || {textContent: ''}).textContent, dead: qa('#lv .chip').filter(function(c){ return c.textContent === 'Dead'; }).length + qa('#lv .scp.dead').length,
          over: o.scrollWidth - o.clientWidth}; }"""

async def main():
    miss = [k for k, v in NEED.items() if not v]
    if miss: print("SKIP: this week's Live data has no game with " + ", ".join(miss) + " - nothing to build the cases from"); return
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    WIN = [Y1, Y2, TD, ML, OV] + ([UN] if UN else []); NW = len(WIN)
    print(f"   game {GID} (home {A}), made-up final {A} {SA} - {B} {SB}; legs: " + "; ".join(f"{l['pl']} {l['m']} {l['ln']}" for l in WIN) + f"; no stat line: {ABS['pl']}; did not play: {DNP['pl']}")
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def run(name, theme="dark", t=None, espn="off", sb=None, sm=None, keys=None, oldlog=None, hash_=None, wait=2600, events=(), **dk):
            """one visit: returns (what the page shows, the ESPN addresses it asked for, page errors, the page)"""
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
            ls = {"bs_theme": theme, "t_now": str(int(t if t is not None else KO + 6 * 3600e3)), "bs_live_hub": "__slips", "bs_live_slipsopen": "1", "bs_live_open": json.dumps(["slip|s1"]),
                  f"bs_slips_w{WEEK}": json.dumps([{"id": "s1", "name": "Test slip", "keys": [key(l) for l in (keys or WIN)], "odds": 600, "stake": 10}])}
            if oldlog is not None: ls[f"bs_log_w{WEEK}"] = json.dumps(oldlog)
            await ctx.add_init_script("try{" + "".join(f"if(localStorage.getItem({json.dumps(k)})===null)localStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in ls.items()) + "}catch(e){}" + CLOCK)
            asked = []
            async def on_espn(route, request):
                asked.append(request.url)
                if espn == "off": await route.abort(); return
                await route.fulfill(status=200, content_type="application/json", body=json.dumps((sm if sm is not None else {}) if "summary" in request.url else (sb if sb is not None else {"events": []})))
            async def on_feed(route, request): await route.fulfill(status=200, content_type="application/json", body=json.dumps({"events": list(events)} if "changes.json" in request.url else {}))
            await ctx.route("**/raw.githubusercontent.com/**", on_feed)
            await ctx.route("**/*espn.com/**", on_espn); await ctx.route("**/*supabase*/**", lambda r: r.abort())
            body = data(**dk)
            async def on_data(route, request): await route.fulfill(status=200, content_type="application/javascript", body=body)
            await ctx.route("**/live/data-*.js", on_data)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/live/" + (hash_ or ""), wait_until="domcontentloaded"); await pg.wait_for_timeout(wait)
            s = await pg.evaluate(READ, GID)
            if SHOTS: await pg.screenshot(path=f"{SHOTS}/live-{name}-{theme}.png", full_page=True)
            return s, asked, errs, pg, ctx
        wins = lambda s: [r for r in (s["log"] or []) if r[4] == 1]; losses = lambda s: [r for r in (s["log"] or []) if r[4] == 0]

        # ---- 1. the week is finished, the build holds the finals, ESPN cannot be reached ----
        for theme in ("dark", "light"):
            s, asked, errs, pg, ctx = await run("final-build", theme=theme, hash_="#lv-" + GID)
            print(f"   [{theme}] finals in the build, no ESPN:", json.dumps({k: s[k] for k in ("slip", "facts", "week", "score", "tog", "subs", "bar")})[:520])
            check(s["slip"] == "CASHED" and f"{NW} hit" in (s["facts"] or "") and s["dead"] == 0, f"[{theme}] {NW} winning legs read CASHED with {NW} hit and nothing dead, with ESPN cut off (was: 0 hit, all dead)")
            check(s["week"] == f"{NW}–0" and len(wins(s)) == NW and not losses(s), f"[{theme}] My week reads {NW}-0 and the saved season record holds {NW} wins and no loss ({s['week']}, {len(wins(s))} wins / {len(losses(s))} losses saved)")
            check(re.sub(r"\D+", " ", s["score"] or "").split() == [str(SA), str(SB)], f"[{theme}] the finished game shows its score ({s['score']!r}), not dashes")
            check(s["gopen"] and "Week" in s["bar"] and "finished" in s["bar"] and "watch list below" not in s["bar"], f"[{theme}] a link to the game opens it inside the Final fold; the top line says the week is finished ({s['bar'][:60]!r})")
            labels = await pg.evaluate("""(gid) => { var c = function(sel){ var e = document.querySelector(sel); return e ? getComputedStyle(e, '::before').content.replace(/"/g, '').trim() : null; };
                var card = '#lv-' + gid, was = c(card + ' > .ghd2 .tog .car'); document.querySelector(card + ' > .ghd2').click();
                return new Promise(function(res){ setTimeout(function(){ res({fold: c('[data-g="__fin"] .tog .car'), openCard: was, closedCard: c(card + ' > .ghd2 .tog .car'), closed: !document.querySelector(card).classList.contains('open')}); }, 1600); }); }""", GID)
            check(labels == {"fold": "Hide", "openCard": "Hide", "closedCard": "Show", "closed": True}, f"[{theme}] a closed game inside the open Final fold says Show, an open one says Hide ({labels})")
            check(s["over"] == 0 and not errs, f"[{theme}] no sideways scroll, no page errors {errs[:1]}")
            await ctx.close()
        # an old, wrong record (every leg saved as a loss by the bug) is put right on the next visit
        s, asked, errs, pg, ctx = await run("heal", oldlog=[[l["pl"], l["m"], l["ln"], l["o"], 0] for l in WIN]); await ctx.close()
        check(len(wins(s)) == NW and not losses(s), f"a season record the bug had filled with {NW} losses is rewritten as {NW} wins once real numbers are there")
        # a real loss still reads as a loss
        s, asked, errs, pg, ctx = await run("real-loss", lose=(Y1,)); await ctx.close()
        check(s["slip"] == "DEAD" and len(losses(s)) == 1 and losses(s)[0][0] == Y1["pl"] and len(wins(s)) == NW - 1, f"a leg that fell short is dead, the slip is DEAD, and that one loss is saved ({s['slip']}, {s['facts']})")

        # a touchdown on a return pays an anytime-TD leg
        RETURN_TD["on"] = True; s, asked, errs, pg, ctx = await run("return-td"); await ctx.close(); RETURN_TD["on"] = False
        check(s["slip"] == "CASHED" and f"{NW} hit" in s["facts"], f"an anytime-TD leg is paid on a return touchdown, not only a rush or a catch ({s['slip']}: {s['facts']})")

        # ---- 2. the build has the score but no stat lines; ESPN cannot be reached ----
        s, asked, errs, pg, ctx = await run("score-only", fb="score", hash_="#lv-" + GID); await ctx.close()
        print("   score only, no ESPN:", json.dumps({k: s[k] for k in ("slip", "slipSub", "facts", "week", "tog", "subs")})[:520])
        check(s["slip"] == "Grading" and s["dead"] == 0 and "2 hit" in s["facts"] and f"{NW - 2} not graded yet" in s["facts"], f"with a score but no stat lines the two game-line legs are graded, the {NW - 2} player legs wait, nothing is dead ({s['slip']}: {s['facts']})")
        check(len(wins(s)) == 2 and not losses(s) and s["week"] == "2–0", f"only the two graded legs are saved ({len(wins(s))} wins, {len(losses(s))} losses; My week {s['week']})")
        check(any(x.startswith("Not graded yet") for x in s["subs"]) and "not graded yet" in (s["tog"] or ""), f"the game card files those legs under Not graded yet ({s['subs']})")
        # ---- 3. the build knows nothing about the game (4.5 hours after kickoff counts as over); ESPN cannot be reached ----
        s, asked, errs, pg, ctx = await run("nothing", fb=None, fin=False, oldlog=[[Y1["pl"], Y1["m"], Y1["ln"], Y1["o"], 1]]); await ctx.close()
        check(s["slip"] == "Grading" and s["dead"] == 0 and f"{NW} not graded yet" in s["facts"] and s["week"] == "0–0", f"with no score and no stat lines every leg waits - no win, no loss ({s['slip']}: {s['facts']}; My week {s['week']})")
        check(s["log"] == [[Y1["pl"], Y1["m"], Y1["ln"], Y1["o"], 1]], "a result saved earlier is kept while its leg is waiting for numbers (a slow box score does not erase it)")

        # ---- 4. the build has nothing for the game, ESPN answers: the page asks for the scores once and for that box score ----
        s, asked, errs, pg, ctx = await run("espn-final", fb=None, fin=False, espn="on", sb=scoreboard("post", SA, SB), sm=summary(), keys=WIN + [ABS], wait=3600); await ctx.close()
        nsb = sum("scoreboard" in u for u in asked); nsm = sum("summary" in u for u in asked)
        print(f"   ESPN final: {nsb} scoreboard call(s), {nsm} box score call(s);", json.dumps({k: s[k] for k in ("slip", "facts", "week")})[:300])
        check(nsb >= 1 and nsm == 1, f"the page asked ESPN for the scores and for the one box score it needed ({nsb} + {nsm} calls)")
        check(s["slip"] == "Grading" and s["dead"] == 0 and f"{NW} hit" in s["facts"] and "1 not graded yet" in s["facts"], f"ESPN's box score grades the {NW} winners; the man with no stat line waits instead of losing ({s['slip']}: {s['facts']})")
        check(len(wins(s)) == NW and not losses(s), "and he is not saved as a loss")
        RETURN_TD["on"] = True; sm_ret = summary(); RETURN_TD["on"] = False
        s, asked, errs, pg, ctx = await run("espn-return-td", fb=None, fin=False, espn="on", sb=scoreboard("post", SA, SB), sm=sm_ret, keys=[TD, ML], wait=3600); await ctx.close()
        check(s["slip"] == "CASHED" and "2 hit" in s["facts"], f"from ESPN's box score too, a kick-return touchdown pays the anytime-TD leg ({s['slip']}: {s['facts']}) - against ESPN's layout as far as it is known")
        # ---- 5. a leg on a player who did not play is void, not lost ----
        s, asked, errs, pg, ctx = await run("void", dnp=True, keys=[Y1, Y2, DNP], hash_="#lv-" + GID); await ctx.close()
        print("   did not play:", json.dumps({k: s[k] for k in ("slip", "facts", "money", "share", "subs")})[:420], "|", [r for r in s["rows"] if "did not play" in r][:2])
        check(s["slip"] == "CASHED" and "2 hit" in s["facts"] and "1 void" in s["facts"] and s["dead"] == 0, f"two winners and a man who did not play: CASHED, 2 hit, 1 void ({s['slip']}: {s['facts']})")
        check(not any("wins" in m for m in s["money"]) and not s["share"] and any("did not play" in r and "voids" in r for r in s["rows"]), "the slip explains the void and does not claim the full ticket payout or offer a win card")
        check(len(wins(s)) == 2 and not losses(s) and any(x.startswith("Did not play") for x in s["subs"]), f"the void leg is not saved as a win or a loss, and the game card lists it under Did not play ({s['subs']})")

        # ---- 6. a game in play: unchanged, plus the end of regulation is not a final ----
        s, asked, errs, pg, ctx = await run("in-play", t=KO + 75 * 60e3, fb=None, fin=False, espn="on", sb=scoreboard("in", 13, 17), sm=summary(lose=(Y1,)), keys=WIN + [ABS], wait=3600); await ctx.close()
        row_abs = next((r for r in s["rows"] if r.startswith("×" + ABS["pl"]) or ABS["pl"] in r), "")
        print("   in play:", json.dumps({k: s[k] for k in ("slip", "facts", "score", "week")})[:300], "|", row_abs[:110])
        check(re.sub(r"\D+", " ", s["score"]).split() == ["13", "17"] and re.fullmatch(r"\d+%", s["slip"] or "") is not None and "not graded" not in s["facts"], f"in play: live score, a chance from here, nothing waiting ({s['score']!r}, {s['slip']}, {s['facts']})")
        check(f"0 / {int(ABS['ln'])}" in row_abs and "Dead" not in row_abs, f"in play a man who is not in the box score yet stands at 0, still open ({row_abs[:80]!r})")
        s, asked, errs, pg, ctx = await run("end-of-regulation", t=KO + 190 * 60e3, fb=None, fin=False, espn="on", sb=scoreboard("in", 20, 20, period=4, clock="0:00"), sm=summary(lose=(Y1,)), keys=[Y1, ML], wait=3600); await ctx.close()
        check(s["dead"] == 0 and not s["log"], f"tied at the end of regulation (overtime to come): nothing is dead and nothing is saved yet ({s['slip']}: {s['facts']})")
        # ---- 7. kickoff has passed and the score feed cannot be reached ----
        s, asked, errs, pg, ctx = await run("no-feed", t=KO + 75 * 60e3, fb=None, fin=False, keys=[ML, OV, Y1]); await ctx.close()
        check(s["dead"] == 0 and not s["log"] and sum("score delayed" in r for r in s["rows"]) == 2, f"with the game on and no score feed the game-line legs say the score is delayed instead of being worked out on 0-0 ({[r[-40:] for r in s['rows'][:2]]})")
        # ---- 8. the inactives list: a leg on a player ruled out before kickoff is void from that moment ----
        iso = lambda ms: __import__("datetime").datetime.fromtimestamp(ms / 1000, __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        note = lambda l, ts, tm=None: {"ts": iso(ts), "k": "inactive", "pl": l["pl"], "tm": tm or l["tm"], "t": f"{l['pl']} ({tm or l['tm']}) INACTIVE"}
        rowof = lambda s, l: next((r for r in s["rows"] if l["pl"] in r), "")
        s, asked, errs, pg, ctx = await run("inactive-pregame", t=KO - 80 * 60e3, fb=None, fin=False, keys=[Y1, ABS], events=[note(ABS, KO - 95 * 60e3)], wait=3600); await ctx.close()
        print("   inactive, before kickoff:", json.dumps({k: s[k] for k in ("slip", "facts")}), "|", rowof(s, ABS)[:120])
        check("1 void" in s["facts"] and "Void" in rowof(s, ABS) and "inactive" in rowof(s, ABS) and s["dead"] == 0 and not errs, f"a player on the inactives list before kickoff: his leg is void at once and the slip says so ({s['facts']})")
        s, asked, errs, pg, ctx = await run("inactive-in-play", t=KO + 75 * 60e3, fb=None, fin=False, espn="on", sb=scoreboard("in", 13, 17), sm=summary(lose=(Y1,)), keys=[Y1, ABS], events=[note(ABS, KO - 95 * 60e3)], wait=3800); await ctx.close()
        check("Void" in rowof(s, ABS) and "0 /" not in rowof(s, ABS) and "1 void" in s["facts"], f"with the game on he stays void instead of sitting at 0 ({rowof(s, ABS)[:70]!r})")
        s, asked, errs, pg, ctx = await run("inactive-but-played", t=KO + 75 * 60e3, fb=None, fin=False, espn="on", sb=scoreboard("in", 13, 17), sm=summary(), keys=[Y1, ABS], events=[note(Y1, KO - 95 * 60e3)], wait=3800); await ctx.close()
        check("Void" not in rowof(s, Y1) and "Hit" in rowof(s, Y1), f"a note that turns out wrong does not void a man who is in the box score ({rowof(s, Y1)[:70]!r})")
        s, asked, errs, pg, ctx = await run("inactive-other", t=KO - 80 * 60e3, fb=None, fin=False, keys=[Y1, ABS], events=[note(ABS, KO - 95 * 60e3, tm="ZZZ"), note(Y1, KO - 6 * 86400e3)], wait=3600); await ctx.close()
        check("void" not in s["facts"] and "Void" not in rowof(s, ABS) and "Void" not in rowof(s, Y1), f"a note for another team's player of the same name, or one from last week, voids nothing ({s['facts']})")
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed")
    sys.exit(1 if ok[1] else 0)
asyncio.run(main())
