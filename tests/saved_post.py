"""A saved slip is posted to Social from where it is listed (owner 11/22 2:09 AM: "Make it easier for you to send saved betslips to
social"): a "Post to Social" button on each open slip on My BetSweep, and a "From saved slips" panel on Social. Both hand the slip's
legs to the one post form (social.py POST_JS / SAVED_JS). The real account script runs against a stand-in Supabase client (no network);
the page clock is frozen two hours before the week's last kickoff.   python3 tests/saved_post.py [shots_dir]"""
import asyncio, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8877; B = f"http://127.0.0.1:{PORT}"
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)

# this week's board, as the page itself loads it
bh = open(os.path.join(ROOT, "build", "index.html"), encoding="utf-8").read(); m = re.search(r'src="(/build/data-[0-9a-f]+\.js)"', bh)
js = open(os.path.join(ROOT, m.group(1).lstrip("/")), encoding="utf-8").read() if m else bh
BS = json.JSONDecoder().raw_decode(js[js.index("{", js.index("window.__BS = ")):])[0]
W = int(BS["week"]); games = sorted(BS["games"], key=lambda g: g["ko"])
# 11/24: early in the week the last game has no player lines yet (IndexError on Tuesday's board); the "late" game is the latest one
# with yardage / catch legs for three players and a total.
def _ready(gid):
    P = {l["pl"] for l in BS["legs"] if l["g"] == gid and not l.get("gl") and re.search(r"Yards|Receptions", l["m"]) and not l["m"].startswith("Under")}
    return len(P) >= 3 and any(l["g"] == gid and l["m"] == "Total" for l in BS["legs"])
_late = next((g for g in reversed(games) if _ready(g["gid"])), games[-1]); GL = _late["gid"]; T = _late["ko"] - 2 * 3600e3
def key(l): return f"{l['pl']}|{l['m']}|{int(round(l['ln'] or 1)) if (l['ln'] or 1) % 1 != 0.5 else int((l['ln'] or 1) + 0.5)}"
late = [l for l in BS["legs"] if l["g"] == GL and not l.get("gl") and re.search(r"Yards|Receptions", l["m"]) and not l["m"].startswith("Under")]
seen = {}; props = [seen.setdefault(l["pl"], l) for l in late if l["pl"] not in seen][:3]
tot = [l for l in BS["legs"] if l["g"] == GL and l["m"] == "Total"][0]
A, Bk, C, TK = key(props[0]), key(props[1]), key(props[2]), key(tot)
EITHER = f"{props[0]['pl']} or {props[1]['pl']}|Either TD|1"; EARLY = "Early Bird|Receiving Yards|40"
SLIPS = [
    {"id": "b1", "name": "Clean two", "keys": [A, Bk], "odds": 264, "stake": 1, "saved": 1},
    {"id": "fd2", "name": "FanDuel 3-leg +650", "keys": [A, C, TK], "g": {TK: ["__other"]}, "odds": 650, "stake": 1, "saved": 2, "src": "fanduel-screenshot"},
    {"id": "b3", "name": "Mixed", "keys": [A, EITHER, EARLY], "odds": 900, "stake": 1, "saved": 3},
    {"id": "b4", "name": "Dead", "keys": [EITHER, TK], "odds": 300, "stake": 1, "saved": 4},
    {"id": "f77", "name": "Sharp's slip", "keys": [A], "odds": 120, "stake": 1, "saved": 5, "from": "Sharp", "post": 77},
    {"id": f"promo-{W}-1", "name": "House promo", "keys": [Bk], "odds": 130, "stake": 1, "promo": True},
    {"id": "b6", "name": "Up already", "keys": [C], "odds": 140, "stake": 1, "saved": 6, "posted": 41},
]
OLD = [{"id": "b7", "name": "Last week", "keys": [A], "odds": 110, "stake": 1, "saved": 0}]
ME = "22222222-2222-2222-2222-222222222222"
FAKE = """
Date.now = function(){ return %d; };
(function(){
  function q(table){ var f = {}, P = new Proxy(function(){}, {get: function(_, k){
      if(k === 'insert') return function(r){ if(table === 'feed_posts'){ window.__posted = Array.isArray(r) ? r[0] : r; f.ins = 1; } return P; };
      if(k === 'then') return function(res, rej){ var d = table === 'feed_profiles' ? [{user_id: '%s', handle: 'Tester'}] : (table === 'feed_posts' && f.ins) ? [{id: 99}] : []; return Promise.resolve({data: d, error: null}).then(res, rej); };
      return function(){ return P; }; }}); return P; }
  var S = {user: {id: '%s', email: 't@example.com'}};
  window.supabase = {createClient: function(){ return {
    auth: {getSession: function(){ return Promise.resolve({data: {session: localStorage.getItem('t_out') ? null : S}}); }, onAuthStateChange: function(){ return {data: {subscription: {unsubscribe: function(){}}}}; }, signOut: function(){ return Promise.resolve({}); }},
    from: function(t){ return q(t); },
    rpc: function(n, a){ return Promise.resolve({data: n === 'feed_handle' ? 'Tester' : n === 'feed_profile_me' ? {user_id: '%s', handle: 'Tester', color: 1, emoji: null} : null, error: null}); } }; }};
})();
try{ if(!localStorage.getItem('t_seeded')){ localStorage.setItem('t_seeded', '1'); if(!localStorage.getItem('t_none')){ localStorage.setItem('bs_slips_w%d', JSON.stringify(%s)); localStorage.setItem('bs_slips_w%d', JSON.stringify(%s)); } } }catch(e){}
""" % (T, ME, ME, ME, W, json.dumps(SLIPS), W - 1, json.dumps(OLD))
# The board as shipped, plus two made-up games in its own shape (a list of {gid, ko}): one that kicked off an hour ago with one leg, and one
# still to come that carries the same total line as the week's last game - which is what makes that line "in more than one game".
BOARD = """() => window.BSImport.data().then(function(BS){ if(BS.__t) return true; BS.__t = 1;
  var a = BS.legs.filter(function(l){ return l.g === %s && l.pl === %s; })[0], t = BS.legs.filter(function(l){ return l.g === %s && l.m === 'Total' && (l.pl + '|Total|' + Math.round(l.ln || 1)) === %s; })[0];
  BS.games.push({gid: '__early', ko: Date.now() - 3600e3}); BS.games.push({gid: '__other', ko: Date.now() + 5 * 3600e3});
  BS.legs.push(Object.assign({}, a, {pl: 'Early Bird', m: 'Receiving Yards', ln: 39.5, g: '__early'})); BS.legs.push(Object.assign({}, t, {g: '__other', tm: 'OTH'}));
  return true; })""" % (json.dumps(GL), json.dumps(props[0]["pl"]), json.dumps(GL), json.dumps(TK))
ROWS = """() => Array.from(document.querySelectorAll('#slips li.sl')).map(function(li){ var b = li.querySelector('button.psb'), a = li.querySelector('a.pon'), n = li.querySelector('.psn');
  return {name: li.querySelector('b').textContent, post: b ? b.textContent : null, h: b ? Math.round(b.getBoundingClientRect().height) : 0, on: a ? a.textContent + ' ' + a.getAttribute('href') : null, note: n && !n.hidden ? n.textContent : '', ask: n && n.querySelector('button') ? n.querySelector('button').textContent : null, shown: li.offsetHeight > 0}; })"""
DLG = "() => ({open: !document.getElementById('sdlg').hidden, title: document.getElementById('sdT').value, odds: document.getElementById('sdO').value, as: document.getElementById('sdH').textContent, msg: document.getElementById('sdM').textContent, legs: document.getElementById('sdL').hidden ? null : document.getElementById('sdL').textContent})"
POSTED = "() => { var r = window.__posted; return r ? {n: (r.legs || []).length, keys: (r.legs || []).map(function(l){ return l.k; }), g: (r.legs || []).map(function(l){ return l.g; }), kos: (r.legs || []).every(function(l){ return typeof l.ko === 'number' && l.ko > Date.now(); }), odds: r.fd_odds, title: r.title, week: r.week, fko: typeof r.first_ko, lko: typeof r.last_ko} : null; }"

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async def rt(route, request):
        u = request.url
        if "/data/box-w" in u or "/data/close-w" in u: await route.fulfill(status=404, content_type="text/plain", body="none")   # nothing played yet
        elif "127.0.0.1" in u: await route.continue_()
        elif "supabase" in u and u.endswith(".js"): await route.fulfill(status=200, content_type="text/javascript", body="/* stand-in */")
        elif "espn.com" in u: await route.fulfill(status=200, content_type="application/json", body='{"events":[]}')
        else: await route.abort()
    async def tap_row(pg, name, what="button.psb"):
        await pg.evaluate("""([n, w]) => { var li = Array.from(document.querySelectorAll('#slips li.sl')).filter(function(x){ return x.querySelector('b').textContent === n; })[0]; li.scrollIntoView({block: 'center'}); li.querySelector(w).click(); }""", [name, what])
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            async def fresh(extra=""):
                ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
                await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}');{extra}}}catch(e){{}}" + FAKE); await ctx.route("**/*", rt)
                pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200])); return ctx, pg, errs
            # ================= My BetSweep =================
            ctx, pg, errs = await fresh()
            await pg.goto(B + "/me/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600); await pg.evaluate(BOARD)
            rows = {r["name"]: r for r in await pg.evaluate(ROWS)}; over = await pg.evaluate("document.documentElement.scrollWidth - innerWidth")
            print(f"   [{theme}]", json.dumps(rows, ensure_ascii=False)[:900])
            mine = ["Clean two", "FanDuel 3-leg +650", "Mixed", "Dead"]
            check(all(rows[n]["post"] == "Post to Social" for n in mine), f"[{theme}] each open slip of your own has a Post to Social button ({[rows[n]['post'] for n in mine]})")
            check(rows["Sharp's slip"]["post"] is None and rows["House promo"]["post"] is None, f"[{theme}] a slip saved from someone's post and a tailed BetSweep promo have no such button - they are not yours to post")
            check(rows["Up already"]["post"] is None and rows["Up already"]["on"] == "On Social ✓ /social/#p41", f"[{theme}] a slip that is already posted links to its post instead ({rows['Up already']['on']})")
            check(rows["Last week"]["post"] is None, f"[{theme}] last week's slip has no button")
            check(over <= 0 and all(rows[n]["h"] >= 24 for n in mine), f"[{theme}] the row fits the phone ({over}px sideways; button {rows['Clean two']['h']}px tall)")
            if SHOTS: await pg.evaluate("document.getElementById('slips').scrollIntoView({block: 'start'}); window.scrollBy(0, -80)"); await pg.wait_for_timeout(250); await pg.screenshot(path=f"{SHOTS}/saved-post-me-{theme}.png")
            # --- a clean slip: one tap opens the form with the slip's own name as the title ---
            await tap_row(pg, "Clean two"); await pg.wait_for_timeout(900); d = await pg.evaluate(DLG)
            check(d["open"] and d["title"] == "Clean two" and d["odds"] == "" and d["as"] == "@Tester" and d["msg"] == "", f"[{theme}] one tap opens the post form: the slip's name is the title, no price is claimed for a builder save ({d})")
            want_l = "2 legs: " + "; ".join(f"{l['pl']} {int(l['ln'] + 0.5)}+ {l['m'].lower()}" for l in props[:2])
            check(d["legs"] == want_l, f"[{theme}] the form says which legs are about to go up ({d['legs']})")
            check(await pg.evaluate("window.__posted === undefined"), f"[{theme}] nothing is posted until Post is pressed")
            if SHOTS: await pg.wait_for_timeout(150); await pg.screenshot(path=f"{SHOTS}/saved-post-form-{theme}.png")
            await pg.click("#sdGo"); await pg.wait_for_timeout(300); po = await pg.evaluate(POSTED)
            check(po and po["keys"] == [A, Bk] and po["g"] == [GL, GL] and po["kos"] and po["title"] == "Clean two" and po["week"] == W and po["fko"] == "string" and isinstance(po["odds"], int), f"[{theme}] Post sends exactly the slip's two legs, each with its game and kickoff, for this week ({po})")
            await pg.wait_for_timeout(1500)
            r1 = {r["name"]: r for r in await pg.evaluate(ROWS)}["Clean two"]; st = await pg.evaluate("() => ({path: location.pathname, dlg: document.getElementById('sdlg').hidden, posted: (JSON.parse(localStorage.getItem('bs_slips_w%d')).filter(function(s){ return s.id === 'b1'; })[0] || {}).posted})" % W)
            check(st == {"path": "/me/", "dlg": True, "posted": 99} and r1["post"] is None and r1["on"] == "On Social ✓ /social/#p99", f"[{theme}] after the post you are still on My BetSweep and the row says On Social, linked to the post ({st}, {r1['on']})")
            # --- a screenshot import: the book's price is offered, the made-up name is not a title, and a total goes to its own game ---
            await pg.evaluate("window.__posted = undefined"); await tap_row(pg, "FanDuel 3-leg +650"); await pg.wait_for_timeout(900); d = await pg.evaluate(DLG)
            check(d["open"] and d["title"] == "" and d["odds"] == "+650", f"[{theme}] an imported FanDuel slip offers the price from the screenshot and leaves the made-up name out of the title ({d})")
            await pg.click("#sdGo"); await pg.wait_for_timeout(300); po = await pg.evaluate(POSTED)
            check(po and po["keys"] == [A, C, TK] and po["g"] == [GL, GL, "__other"] and po["odds"] == 650 and po["title"] is None, f"[{theme}] it posts at that price, and the total goes to the game the slip has on record, not the first game with that number ({po})")
            await pg.wait_for_timeout(1500)
            # --- legs that cannot go up: say which and why, and ask before a shorter slip is posted ---
            await pg.evaluate("window.__posted = undefined"); await tap_row(pg, "Mixed"); await pg.wait_for_timeout(900)
            r3 = {r["name"]: r for r in await pg.evaluate(ROWS)}["Mixed"]; d = await pg.evaluate(DLG)
            check(not d["open"] and r3["note"].startswith("1 of 3 legs can be posted. Left out: ") and "(either-player touchdowns are not posted)" in r3["note"] and "Early Bird 40+ receiving yards (that game has already kicked off)" in r3["note"] and r3["ask"] == "Post the one leg",
                  f"[{theme}] a slip with legs that cannot be posted says which and why and asks first ({r3['note'][:150]} | {r3['ask']})")
            if SHOTS: await pg.wait_for_timeout(150); await pg.screenshot(path=f"{SHOTS}/saved-post-ask-{theme}.png")
            ov = await pg.evaluate("document.documentElement.scrollWidth - innerWidth")
            await tap_row(pg, "Mixed", ".psn button"); await pg.wait_for_timeout(700); d = await pg.evaluate(DLG)
            check(d["open"] and d["odds"] == "" and ov <= 0, f"[{theme}] saying yes opens the form for the legs that are left, with no price carried over from the longer slip ({d})")
            await pg.click("#sdGo"); await pg.wait_for_timeout(300); po = await pg.evaluate(POSTED)
            check(po and po["keys"] == [A] and po["n"] == 1, f"[{theme}] and only that leg is posted ({po})")
            await pg.wait_for_timeout(1500)
            # --- nothing postable: no form at all ---
            await pg.evaluate("window.__posted = undefined"); await tap_row(pg, "Dead"); await pg.wait_for_timeout(900)
            r4 = {r["name"]: r for r in await pg.evaluate(ROWS)}["Dead"]; d = await pg.evaluate(DLG)
            check(not d["open"] and r4["note"].startswith("None of this slip’s legs can be posted: ") and "(the same line is in more than one game)" in r4["note"] and r4["ask"] is None and await pg.evaluate("window.__posted === undefined"),
                  f"[{theme}] a slip with nothing postable says so and opens no form; a total with no game on record is not guessed at ({r4['note'][:170]})")
            check(not errs, f"[{theme}] My BetSweep: no script errors {errs[:2]}"); await ctx.close()
            # --- signed out: the button asks you to sign in, and posts nothing ---
            ctx, pg, errs = await fresh("localStorage.setItem('t_out','1');")
            await pg.goto(B + "/me/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600); await pg.evaluate(BOARD)
            await tap_row(pg, "Clean two"); await pg.wait_for_timeout(900)
            so = await pg.evaluate("() => ({form: !document.getElementById('sdlg').hidden, signin: !!document.querySelector('.bsdlg') && document.querySelector('.bsdlg').offsetHeight > 0, posted: window.__posted === undefined})")
            check(so == {"form": False, "signin": True, "posted": True}, f"[{theme}] signed out, Post to Social opens the sign-in box instead of the form ({so})")
            check(not errs, f"[{theme}] signed out: no script errors {errs[:2]}"); await ctx.close()
            # ================= Social =================
            ctx, pg, errs = await fresh()
            await pg.goto(B + "/social/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600); await pg.evaluate(BOARD)
            s0 = await pg.evaluate("() => { var b = document.getElementById('savbtn'), r = b.getBoundingClientRect(); return {text: b.textContent, shown: !b.hidden && r.height > 0, h: Math.round(r.height), panel: !document.getElementById('sav').hidden, exp: b.getAttribute('aria-expanded'), over: document.documentElement.scrollWidth - innerWidth}; }")
            check(s0 == {"text": "From saved slips", "shown": True, "h": s0["h"], "panel": False, "exp": "false", "over": s0["over"]} and s0["h"] >= 44 and s0["over"] <= 0, f"[{theme}] Social has a 'From saved slips' button when this device has open slips; its panel starts closed ({s0})")
            await pg.click("#savbtn"); await pg.wait_for_timeout(400)
            s1 = await pg.evaluate("""() => ({open: !document.getElementById('sav').hidden, exp: document.getElementById('savbtn').getAttribute('aria-expanded'), rows: Array.from(document.querySelectorAll('#savlist li')).map(function(li){ var g = li.querySelector('button.go'), a = li.querySelector('a.on');
                return li.querySelector('b').textContent + ' | ' + li.querySelector('small').textContent + ' | ' + (g ? g.textContent + ' ' + Math.round(g.getBoundingClientRect().height) : a ? a.textContent + ' ' + a.getAttribute('href') : ''); }), over: document.documentElement.scrollWidth - innerWidth})""")
            print(f"   [{theme}]", json.dumps(s1, ensure_ascii=False)[:700])
            check(s1["open"] and s1["exp"] == "true" and [r.split(" | ")[0] for r in s1["rows"]] == ["Clean two", "FanDuel 3-leg +650", "Mixed", "Dead", "Up already"], f"[{theme}] the panel lists your own open slips for this week - not the promo, not someone else's slip ({[r.split(' | ')[0] for r in s1['rows']]})")
            check(s1["rows"][0].startswith("Clean two | 2 legs · +264 | Post ") and int(s1["rows"][0].split(" ")[-1]) >= 44 and s1["rows"][4] == "Up already | 1 leg · +140 | On Social ✓ /social/#p41" and s1["over"] <= 0, f"[{theme}] each row has its legs, price and a Post button a thumb can hit; a posted one links to its post ({s1['rows'][0]} / {s1['rows'][4]})")
            if SHOTS: await pg.evaluate("document.getElementById('sav').scrollIntoView({block: 'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(250); await pg.screenshot(path=f"{SHOTS}/saved-post-social-{theme}.png")
            # one panel at a time
            await pg.click("#shotbtn"); await pg.wait_for_timeout(250); x1 = await pg.evaluate("[document.getElementById('shot').hidden, document.getElementById('sav').hidden, document.getElementById('savbtn').getAttribute('aria-expanded')]")
            await pg.click("#savbtn"); await pg.wait_for_timeout(250); x2 = await pg.evaluate("[document.getElementById('shot').hidden, document.getElementById('sav').hidden, document.getElementById('shotbtn').getAttribute('aria-expanded')]")
            check(x1 == [False, True, "false"] and x2 == [True, False, "false"], f"[{theme}] opening the screenshot panel closes this one and the other way round ({x1}, {x2})")
            # a slip with legs left out asks in the panel
            await pg.evaluate("Array.from(document.querySelectorAll('#savlist li')).filter(function(li){ return li.querySelector('b').textContent === 'Mixed'; })[0].querySelector('button.go').click()"); await pg.wait_for_timeout(900)
            a1 = await pg.evaluate("() => ({st: (document.querySelector('#savout .st') || {}).textContent || '', btn: (document.querySelector('#savout button.go') || {}).textContent || '', form: !document.getElementById('sdlg').hidden})")
            check(a1["st"].startswith("1 of 3 legs can be posted. Left out: ") and a1["btn"] == "Post the one leg" and not a1["form"], f"[{theme}] in the panel too, a slip with legs left out asks first ({a1['st'][:80]} | {a1['btn']})")
            # post a clean one: the form, the post, then the feed reloads on that post
            await pg.evaluate("Array.from(document.querySelectorAll('#savlist li')).filter(function(li){ return li.querySelector('b').textContent === 'Clean two'; })[0].querySelector('button.go').click()"); await pg.wait_for_timeout(900); d = await pg.evaluate(DLG)
            check(d["open"] and d["title"] == "Clean two" and d["as"] == "@Tester", f"[{theme}] Post in the panel opens the same form ({d})")
            await pg.click("#sdGo"); await pg.wait_for_timeout(300); po = await pg.evaluate(POSTED)
            check(po and po["keys"] == [A, Bk] and po["week"] == W, f"[{theme}] and posts the slip's legs ({po})")
            await pg.wait_for_timeout(2600)
            af = await pg.evaluate("() => ({hash: location.hash, posted: (JSON.parse(localStorage.getItem('bs_slips_w%d')).filter(function(s){ return s.id === 'b1'; })[0] || {}).posted, fresh: window.__posted === undefined})" % W)
            check(af == {"hash": "#p99", "posted": 99, "fresh": True}, f"[{theme}] afterwards the feed reloads on the new post and the saved slip is marked as posted ({af})")
            check(not errs, f"[{theme}] Social: no script errors {errs[:2]}"); await ctx.close()
            # no saved slips on this device: no button
            ctx, pg, errs = await fresh("localStorage.setItem('t_none','1');")
            await pg.goto(B + "/social/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2200)
            check(await pg.evaluate("document.getElementById('savbtn').hidden && document.getElementById('sav').hidden"), f"[{theme}] with no saved slips the button is not there")
            check(not errs, f"[{theme}] Social, nothing saved: no script errors {errs[:2]}"); await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
