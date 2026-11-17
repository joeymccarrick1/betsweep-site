"""The Live page tracks a slip's game total against the right game (11/17).

A game total's key ("Over 38.5|Total|39") is the main or an alternate total of most games. The key alone used to go to the first game
with that number, so a slip's total could be followed against another game. The page now reads the game on record for such a key
(a saved slip's `g`, the builder slip's bs_slipg_w<W>), falls back to the one game the slip's other legs are in, and records the game
itself when a leg is added, imported or removed here.

Made up from the built page's own data, so it runs in any week: two games are kept, both given the SAME total line, a kickoff and a
final - game G's total clears the line, game H's does not. ESPN is cut off.
  python3 tests/live_gamemap.py [shots_dir]        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import asyncio, functools, glob, http.server, json, math, os, re, sys, threading, time
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8862; ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
_ref = re.search(r"/live/(data-[0-9a-f]+\.js)", open(os.path.join(ROOT, "live", "index.html")).read())
SRC = open(os.path.join(ROOT, "live", _ref.group(1)) if _ref else glob.glob(os.path.join(ROOT, "live", "data-*.js"))[0]).read(); _m = re.match(r"\s*window\.__LV\s*=\s*", SRC); D0 = json.loads(SRC[_m.end():].rstrip().rstrip(";"))
WEEK = D0["week"]; ALL = D0["legs"] + D0.get("extra", [])
def key(l): return f"{l['pl']}|{l['m']}|{int(math.floor((l.get('ln') or 1) + 0.5))}"
FIRSTKEY = {}
for _l in ALL: FIRSTKEY.setdefault(key(_l), _l)
def watch_props(g): return [l for l in ALL if FIRSTKEY[key(l)] is l and l.get("g") == g["gid"] and not l.get("gl") and l["m"] in ("Receiving Yards", "Rushing Yards", "Receptions", "Passing Yards") and not l.get("u")]
def main_over(g): return next((l for l in D0["legs"] if l.get("g") == g["gid"] and l.get("gl") and l["m"] == "Total" and str(l["gl"].get("side")).upper() == "OVER"), None)
CAND = [g for g in D0["games"] if main_over(g) and len({l["pl"] for l in watch_props(g)}) >= 1]
G, H = (CAND + [None, None])[:2]
KO = (int(time.time()) // 60 * 60 + 48 * 3600) * 1000
SLOT = {"Passing Yards": 0, "Rushing Yards": 3, "Receptions": 5, "Receiving Yards": 6}

def build():
    """two games, one total line: G finishes over it, H finishes under it; one winning yardage leg in each"""
    D = json.loads(json.dumps(D0)); gids = (G["gid"], H["gid"]); ov = main_over(G); LN = ov["ln"]; name = ov["pl"]
    D["games"] = [g for g in D["games"] if g["gid"] in gids]
    keep = lambda l: l.get("g") in gids and not (l.get("gl") and l["m"] == "Total" and l["pl"] == name)        # drop every copy of that total, then put one back per game
    D["legs"] = [l for l in D["legs"] if keep(l)]; D["extra"] = [l for l in D.get("extra", []) if keep(l)]
    hov = main_over(H)
    D["legs"] += [dict(ov, i=900001), dict(hov, i=900002, pl=name, ln=LN, o=-110)]
    D["fb"] = {}
    for g, (sa, sb) in ((G, (int(LN) + 1, 7)), (H, (3, 0))):
        gg = next(x for x in D["games"] if x["gid"] == g["gid"]); gg["ko"] = KO; gg["fin"] = f"{gg['a']} {sa} – {gg['b']} {sb}"
        p = sorted(watch_props(g), key=lambda l: (l["pl"], l["m"], l["ln"]))[0]; r = [0] * 12; r[SLOT[p["m"]]] = int(p["ln"]) + 5
        D["fb"][g["gid"]] = {"sc": {gg["a"]: sa, gg["b"]: sb}, "box": {p["pl"]: r}}
    return D
CLOCK = "(function(){var T=+(localStorage.getItem('t_now')||0);if(!T)return;var R=Date.now,S=R();Date.now=function(){return T+(R()-S)};var D0=Date;function ND(){if(arguments.length===0)return new D0(D0.now());return new (Function.prototype.bind.apply(D0,[null].concat([].slice.call(arguments))))()}ND.now=D0.now;ND.parse=D0.parse;ND.UTC=D0.UTC;ND.prototype=D0.prototype;window.Date=ND;})();"
READ = """() => { var qa = function(s, r){ return Array.from((r || document).querySelectorAll(s)); }, wk = window.__LV.week, J = function(k){ try { return JSON.parse(localStorage.getItem(k)); } catch(e){ return null; } };
  var cards = {}; qa('.slipcard').forEach(function(c){ cards[c.getAttribute('data-sid')] = {st: c.querySelector('.scp b').textContent, facts: c.querySelector('.scn small').textContent, rows: qa('table.lvt tr', c).map(function(tr){ return tr.textContent.replace(/\\s+/g, ' ').trim(); })}; });
  var tab = function(k){ var b = document.querySelector('.hubb[data-hub="' + k + '"] small'); return b ? b.textContent : null; };
  return {cards: cards, week: tab('__log'), slips: J('bs_slips_w' + wk), bk: J('bs_slipk_w' + wk), bg: J('bs_slipg_w' + wk), log: J('bs_log_w' + wk)}; }"""

async def main():
    if not G or not H: print("SKIP: this week's Live data does not have two games with a main total and a yardage leg"); return
    D = build(); OVK = key(main_over(G)); LN = main_over(G)["ln"]; NAME = main_over(G)["pl"]
    yg = sorted(watch_props(G), key=lambda l: (l["pl"], l["m"], l["ln"]))[0]; yh = sorted(watch_props(H), key=lambda l: (l["pl"], l["m"], l["ln"]))[0]
    ga, gb = next(x for x in D["games"] if x["gid"] == G["gid"]), next(x for x in D["games"] if x["gid"] == H["gid"])
    print(f"   {NAME} is on both {G['gid']} (finishes over) and {H['gid']} (finishes under); key {OVK}; yardage legs: {yg['pl']} ({G['gid']}), {yh['pl']} ({H['gid']})")
    class Hd(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(Hd, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    body = "window.__LV = " + json.dumps(D, separators=(",", ":")) + ";"
    async with async_playwright() as p:
        b = await p.chromium.launch()
        async def visit(slips=None, bk=None, bg=None, theme="dark", hash_=""):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
            ls = {"bs_theme": theme, "t_now": str(int(KO + 6 * 3600e3)), "bs_live_hub": "__slips", "bs_live_slipsopen": "1", "bs_live_open": json.dumps(["slip|" + s["id"] for s in (slips or [])] + ["slip|builder"])}
            if slips is not None: ls[f"bs_slips_w{WEEK}"] = json.dumps(slips)
            if bk is not None: ls[f"bs_slipk_w{WEEK}"] = json.dumps(bk)
            if bg is not None: ls[f"bs_slipg_w{WEEK}"] = json.dumps(bg)
            await ctx.add_init_script("try{" + "".join(f"if(localStorage.getItem({json.dumps(k)})===null)localStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in ls.items()) + "}catch(e){}" + CLOCK)
            await ctx.route("**/*espn.com/**", lambda r: r.abort()); await ctx.route("**/*supabase*/**", lambda r: r.abort())
            async def on_data(route, request): await route.fulfill(status=200, content_type="application/javascript", body=body)
            await ctx.route("**/live/data-*.js", on_data)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(f"http://127.0.0.1:{PORT}/live/" + hash_, wait_until="domcontentloaded"); await pg.wait_for_timeout(2400)
            return pg, ctx, errs
        slip = lambda sid, keys, g=None: dict({"id": sid, "name": sid, "keys": keys}, **({"g": g} if g else {}))
        row = lambda s, sid: next((r for r in s["cards"][sid]["rows"] if NAME in r), "")
        # ---- 1. the game on record decides ----
        pg, ctx, errs = await visit([slip("onG", [OVK], {OVK: [G["gid"]]}), slip("onH", [OVK], {OVK: [H["gid"]]})]); s = await pg.evaluate(READ); await ctx.close()
        print("   on record:", {k: (v["st"], v["rows"][0][:70]) for k, v in s["cards"].items()})
        check(s["cards"]["onG"]["st"] == "CASHED" and f"{ga['a']} vs {ga['b']}" in row(s, "onG").replace(ga["b"] + " vs " + ga["a"], f"{ga['a']} vs {ga['b']}"), f"a total on record for {G['gid']} is followed in {G['gid']} and cashes ({s['cards']['onG']['st']})")
        check(s["cards"]["onH"]["st"] == "DEAD", f"the same number on record for {H['gid']} is followed there and loses ({s['cards']['onH']['st']})")
        check(not errs, f"no page errors {errs[:1]}")
        # ---- 2. nothing on record: the game the slip's other legs are in ----
        pg, ctx, errs = await visit([slip("sgpG", [key(yg), OVK]), slip("sgpH", [OVK, key(yh)])]); s = await pg.evaluate(READ); await ctx.close()
        print("   same-game slips, nothing on record:", {k: (v["st"], v["facts"]) for k, v in s["cards"].items()}, "| My week", s["week"])
        check(s["cards"]["sgpG"]["st"] == "CASHED" and "2 hit" in s["cards"]["sgpG"]["facts"], f"with no game on record a slip whose other leg is in {G['gid']} follows the total there (CASHED, 2 hit) - {s['cards']['sgpG']}")
        check(s["cards"]["sgpH"]["st"] == "DEAD" and "1 hit" in s["cards"]["sgpH"]["facts"] and "1 dead" in s["cards"]["sgpH"]["facts"], f"and one whose other leg is in {H['gid']} follows it there (1 hit, 1 dead) - {s['cards']['sgpH']['facts']}")
        check(s["week"] == "3–1" and len(s["log"] or []) == 4 and sum(1 for r in s["log"] if r[0] == NAME) == 2, f"My week counts each game's total once: 3-1 over four legs ({s['week']}, {len(s['log'] or [])} saved)")
        # ---- 3. the builder slip reads the builder's game map ----
        pg, ctx, errs = await visit([], bk=[OVK], bg={OVK: [H["gid"]]}); s = await pg.evaluate(READ); await ctx.close()
        check(s["cards"].get("builder", {}).get("st") == "DEAD", f"the builder slip's total follows the game the builder put on record ({s['cards'].get('builder', {}).get('st')})")
        # ---- 4. adding the total from a game card puts that game on record; the other game's row is not marked ----
        pg, ctx, errs = await visit([slip("mine", [key(yg)])], hash_="#lv-" + H["gid"])
        async def unfold(gid):
            """every list in a game card starts folded: open them all, one at a time (each tap redraws the card)"""
            for _ in range(8):
                more = await pg.evaluate("""(h) => { var x = Array.from(document.querySelectorAll('#lv-' + h + ' h4.subtog')).filter(function(e){ return e.getAttribute('aria-expanded') !== 'true'; })[0]; if(x) x.click(); return !!x; }""", gid)
                if not more: break
                await pg.wait_for_timeout(1300)
        await unfold(H["gid"])
        info = await pg.evaluate("""(a) => new Promise(function(res){ var tr = Array.from(document.querySelectorAll('#lv-' + a.h + ' tr')).filter(function(t){ return t.getAttribute('data-k') === a.k; })[0]; if(!tr){ res({row: false}); return; }
              tr.querySelector('.add').click(); setTimeout(function(){ var m = document.querySelector('.addmenu'), head = m ? m.querySelector('small').textContent : '', btn = m ? Array.from(m.querySelectorAll('button')).filter(function(x){ return x.dataset.sid === 'mine'; })[0] : null; if(btn) btn.click(); res({row: true, menu: !!m, head: head}); }, 250); })""", {"h": H["gid"], "k": OVK})
        await pg.wait_for_timeout(1600); s = await pg.evaluate(READ)
        await unfold(H["gid"]); await pg.evaluate("(g) => { location.hash = '#lv-' + g; }", G["gid"]); await pg.wait_for_timeout(1500); await unfold(G["gid"])      # the leg moved into the card's own lists; open the other game's card too
        marks = await pg.evaluate("""(a) => { var f = function(g){ var card = document.getElementById('lv-' + g); if(!card) return null; var tr = Array.from(card.querySelectorAll('tr')).filter(function(t){ return t.getAttribute('data-k') === a.k; })[0]; return tr ? !!tr.querySelector('.chip.slip') : null; }; return {h: f(a.h), g: f(a.g)}; }""", {"h": H["gid"], "g": G["gid"], "k": OVK})
        mine = (s["slips"] or [{}])[0]
        print("   added from the", H["gid"], "card:", info, "| slip:", {k: mine.get(k) for k in ("keys", "g")}, "| card:", s["cards"].get("mine", {}).get("facts"), "| marked:", marks)
        check(info.get("row") and info.get("menu") and (gb["a"] in info.get("head", "") or gb["b"] in info.get("head", "")), f"the + menu on a shared total names the game ({info.get('head')!r})")
        check(mine.get("keys") == [key(yg), OVK] and mine.get("g") == {OVK: [H["gid"]]}, f"adding the total from the {H['gid']} card puts {H['gid']} on record ({mine.get('g')})")
        check(s["cards"]["mine"]["st"] == "DEAD" and marks == {"h": True, "g": False}, f"the slip follows {H['gid']}'s total even though its other leg is in {G['gid']}; that row is marked as in the slip and {G['gid']}'s same-number row is not ({s['cards']['mine']['st']}, {marks})")
        if SHOTS: await pg.screenshot(path=f"{SHOTS}/live-gamemap-dark.png", full_page=True)
        # ---- 5. removing it with the slip's x takes the record away too ----
        await pg.evaluate("""(k) => { var b = Array.from(document.querySelectorAll('.slipcard[data-sid="mine"] .rm')).filter(function(x){ return x.dataset.k === k; })[0]; if(b) b.click(); }""", OVK); await pg.wait_for_timeout(1500); s = await pg.evaluate(READ); await ctx.close()
        mine = (s["slips"] or [{}])[0]
        check(mine.get("keys") == [key(yg)] and "g" not in mine and s["cards"]["mine"]["st"] == "CASHED", f"removing it leaves the slip as it was, with nothing on record ({mine.get('keys')}, g {'kept' if 'g' in mine else 'gone'}, {s['cards']['mine']['st']})")
        # ---- 6. pasting a slip: the team named with the total decides the game ----
        pg, ctx, errs = await visit([])
        nick = gb.get("na") or gb["a"]
        await pg.evaluate("""(t) => { document.getElementById('impopen').click(); var x = document.getElementById('imptxt'); x.value = t; document.getElementById('impmatch').click(); }""", f"Over {LN} {nick}")
        await pg.wait_for_timeout(500); matched = await pg.evaluate("() => ({go: !document.getElementById('impgo').disabled, list: document.getElementById('implist').textContent})")
        await pg.evaluate("() => document.getElementById('impgo').click()"); await pg.wait_for_timeout(1500); s = await pg.evaluate(READ); await ctx.close()
        imp = (s["slips"] or [{}])[0]
        print("   pasted 'Over", LN, nick + "':", matched, "| slip:", {k: imp.get(k) for k in ("keys", "g")})
        check(matched["go"] and imp.get("keys") == [OVK] and imp.get("g") == {OVK: [H["gid"]]}, f"a pasted total with a team name is tracked in that team's game ({imp.get('g')})")
        check(list(s["cards"].values())[0]["st"] == "DEAD" if s["cards"] else False, "and it grades against that game's final")
        await b.close()
    srv.shutdown()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
