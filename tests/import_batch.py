"""Import several FanDuel screenshots at once on My BetSweep (owner 11/22 2:09 AM: "batch import multiple slips to save multiple betslips
all at once"). The picture reader (tesseract + slipimport.parse) is stubbed - it cannot load here and has its own checks - so this tests
the card: the queue, one block per screenshot, duplicates, what is saved, and posting a saved one to Social from the list it leaves.
The real account script runs against a stand-in Supabase client; page clock frozen two hours before the week's last kickoff.
  python3 tests/import_batch.py [shots_dir]"""
import asyncio, json, os, re, sys, threading, http.server, functools
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8879; B = f"http://127.0.0.1:{PORT}"
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)

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
def key(l): return f"{l['pl']}|{l['m']}|{int((l['ln'] or 1) + 0.5)}"
late = [l for l in BS["legs"] if l["g"] == GL and not l.get("gl") and re.search(r"Yards|Receptions", l["m"]) and not l["m"].startswith("Under")]
seen = {}; props = [seen.setdefault(l["pl"], l) for l in late if l["pl"] not in seen][:3]
A, Bk, C = key(props[0]), key(props[1]), key(props[2])
BEFORE = [{"id": "b0", "name": "Saved before", "keys": [C], "odds": 140, "stake": 1, "saved": 1}]
ME = "33333333-3333-3333-3333-333333333333"
FAKE = """
Date.now = function(){ return %d; };
(function(){
  function q(table){ var f = {}, P = new Proxy(function(){}, {get: function(_, k){
      if(k === 'insert') return function(r){ if(table === 'feed_posts'){ window.__posted = Array.isArray(r) ? r[0] : r; f.ins = 1; } return P; };
      if(k === 'then') return function(res, rej){ var d = table === 'feed_profiles' ? [{user_id: '%s', handle: 'Tester'}] : (table === 'feed_posts' && f.ins) ? [{id: 77}] : []; return Promise.resolve({data: d, error: null}).then(res, rej); };
      return function(){ return P; }; }}); return P; }
  var S = {user: {id: '%s', email: 't@example.com'}};
  window.supabase = {createClient: function(){ return {
    auth: {getSession: function(){ return Promise.resolve({data: {session: S}}); }, onAuthStateChange: function(){ return {data: {subscription: {unsubscribe: function(){}}}}; }, signOut: function(){ return Promise.resolve({}); }},
    from: function(t){ return q(t); },
    rpc: function(n, a){ return Promise.resolve({data: n === 'feed_handle' ? 'Tester' : n === 'feed_profile_me' ? {user_id: '%s', handle: 'Tester', color: 1, emoji: null} : null, error: null}); } }; }};
})();
try{ if(!localStorage.getItem('t_seeded')){ localStorage.setItem('t_seeded', '1'); localStorage.setItem('bs_slips_w%d', JSON.stringify(%s)); } }catch(e){}
""" % (T, ME, ME, ME, W, json.dumps(BEFORE))
# the stand-in reader answers by file name: a = two legs, b = two legs and a drive prop, c = nothing on the picture, d = cannot be read,
# e = the same two legs as a, f = the legs of a slip that is already saved, anything else = a
STUB = """() => window.BSImport.data().then(function(BS){
  function key(l){ return l.pl + '|' + l.m + '|' + Math.round(l.ln || 1); }
  var L = BS.legs.filter(function(l){ return l.g === %s && !l.gl && /Yards|Receptions/.test(l.m) && !/^Under/.test(l.m); }), by = {};
  L.forEach(function(l){ if(!by[key(l)]) by[key(l)] = l; });
  function okLeg(k){ var l = by[k]; return {ok: true, key: k, leg: l, label: l.pl + ' ' + Math.round(l.ln) + '+ ' + l.m, odds: l.o}; }
  var A = %s, Bk = %s, C = %s;
  var OUT = {a: {legs: [okLeg(A), okLeg(Bk)], odds: 264}, b: {legs: [okLeg(A), okLeg(C), {ok: false, raw: 'FIRST DRIVE RESULT - PUNT', why: 'a drive prop'}], odds: 650, stake: 5},
             c: {legs: []}, e: {legs: [okLeg(Bk), okLeg(A)], odds: 270}, f: {legs: [okLeg(C)], odds: 140}};
  window.__reads = []; window.BSImport.read = function(f){ var n = String((f && f.name) || 'a').charAt(0); window.__reads.push(n);
    return new Promise(function(res, rej){ setTimeout(function(){ if(n === 'd') rej(new Error('that file is not a picture we can open')); else res({R: JSON.parse(JSON.stringify(OUT[n] || OUT.a, function(k, v){ return k === 'leg' ? undefined : v; })), BS: BS}); }, 30); }); };
  // JSON round trip drops the board leg, so put it back by key (gmapOf needs it)
  var read0 = window.BSImport.read; window.BSImport.read = function(f){ return read0(f).then(function(r){ r.R.legs.forEach(function(l){ if(l.ok) l.leg = by[l.key]; }); return r; }); };
  return true; })""" % (json.dumps(GL), json.dumps(A), json.dumps(Bk), json.dumps(C))
PNG = b"\x89PNG"
def F(*names): return [{"name": n + ".png", "mimeType": "image/png", "buffer": PNG} for n in names]
VIEW = """() => { var out = document.getElementById('impout'), sb = document.getElementById('impsaveall');
  return {blocks: Array.from(out.querySelectorAll('.impb')).map(function(b){ var on = b.querySelector('.impon'), d = b.querySelector('details'), nm = b.querySelector('.impname'), od = b.querySelector('.impodds'), du = b.querySelector('.dup');
      return {no: b.classList.contains('no'), head: (b.querySelector('.imph b, b') || {}).textContent || '', inc: on ? on.checked : null, st: (b.querySelector('.st') || {}).textContent || '', why: b.classList.contains('no') ? b.querySelector('small').textContent : '', open: d ? d.open : null,
              ticks: b.querySelectorAll('li input[type=checkbox]').length, miss: b.querySelectorAll('li.no').length, name: nm ? nm.value : null, odds: od ? od.value : null, dup: du ? du.textContent : ''}; }),
    all: sb ? sb.textContent + (sb.disabled ? ' (off)' : '') : null, one: !!document.getElementById('impsave'), load: !!document.getElementById('impload'), more: !!document.getElementById('impmore'), clear: !!document.getElementById('impclear'),
    count: (out.querySelector('.impcount') || {}).textContent || '', note: (out.querySelector('.impnote') || {}).textContent || '', st0: (out.querySelector('.st') || {}).textContent || '', over: document.documentElement.scrollWidth - innerWidth,
    hs: Array.from(out.querySelectorAll('.impact button')).map(function(x){ return Math.round(x.getBoundingClientRect().height); })}; }"""
SAVED = "() => (JSON.parse(localStorage.getItem('bs_slips_w%d') || '[]')).map(function(s){ return {id: s.id, name: s.name, keys: s.keys, odds: s.odds, stake: s.stake, src: s.src, posted: s.posted}; })" % W
DONE = """() => { var out = document.getElementById('impout'); return {st: (out.querySelector('.st') || {}).textContent || '', rows: Array.from(out.querySelectorAll('.impdone li')).map(function(li){ var p = li.querySelector('button[data-psb]'), n = li.querySelector('.psn');
  return {name: li.querySelector('b').textContent, sub: li.querySelector('small').textContent, load: !!li.querySelector('button[data-load]'), post: p ? (p.hidden ? 'hidden' : p.textContent + ' ' + Math.round(p.getBoundingClientRect().height)) : null, note: n && !n.hidden ? n.textContent : ''}; }),
  list: Array.from(document.querySelectorAll('#slips li.sl')).map(function(li){ return li.querySelector('b').textContent + (li.querySelector('a.pon') ? ' [on social]' : li.querySelector('button.psb') ? ' [post]' : ''); }), over: document.documentElement.scrollWidth - innerWidth}; }"""

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async def rt(route, request):
        u = request.url
        if "/data/box-w" in u or "/data/close-w" in u: await route.fulfill(status=404, content_type="text/plain", body="none")
        elif "127.0.0.1" in u: await route.continue_()
        elif "supabase" in u and u.endswith(".js"): await route.fulfill(status=200, content_type="text/javascript", body="/* stand-in */")
        elif "espn.com" in u: await route.fulfill(status=200, content_type="application/json", body='{"events":[]}')
        else: await route.abort()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            async def fresh():
                ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
                await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + FAKE); await ctx.route("**/*", rt)
                pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
                await pg.goto(B + "/me/", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600); await pg.evaluate(STUB)
                await pg.evaluate("(function(){ var c = document.getElementById('import'); c.classList.remove('shut'); c.scrollIntoView({block: 'start'}); })()"); return ctx, pg, errs
            FILE = "#import input[type=file]"
            # ---------- the card ----------
            ctx, pg, errs = await fresh()
            c0 = await pg.evaluate("""() => { var p = document.getElementById('import'), i = p.querySelector('input[type=file]'), l = i.closest('label'), r = p.getBoundingClientRect(), pb = document.getElementById('imppaste').getBoundingClientRect(), lb = l.getBoundingClientRect();
              return {multi: i.multiple, label: l.textContent.trim(), h: Math.round(lb.height), title: p.querySelector('h3').textContent, lim: p.querySelector('.implim').textContent, limB: p.querySelector('.implim b').textContent,
                      inSlips: !!p.closest('#crec'), first: (document.querySelector('.me .card') || {}).id, above: r.top < document.getElementById('slips').getBoundingClientRect().top, top: Math.round(r.top + scrollY), ph: Math.round(r.height),
                      oneRow: Math.abs(pb.top - lb.top) < 12, dashed: getComputedStyle(p).borderTopStyle, over: document.documentElement.scrollWidth - innerWidth, vh: innerHeight}; }""")
            print(f"   [{theme}]", json.dumps(c0, ensure_ascii=False)[:500])
            check(c0["inSlips"] and c0["first"] == "crec" and c0["above"] and c0["top"] < 1.1 * c0["vh"] and c0["dashed"] == "dashed", f"[{theme}] the importer sits at the top of Your slips, above the list, within the first screen or so ({c0['top']}px down, {c0['ph']}px tall)")
            check(c0["title"] == "Import your FanDuel bets" and c0["multi"] and c0["label"] == "Choose screenshots" and c0["h"] >= 40 and c0["oneRow"] and c0["over"] <= 0, f"[{theme}] it is named for what it does, with Choose screenshots and Paste side by side ({c0['label']}, {c0['h']}px)")
            check(c0["limB"] == "Up to 12 screenshots at a time." and c0["lim"].startswith("Up to 12 screenshots at a time."), f"[{theme}] the 12-at-a-time limit is spelled out in the panel ({c0['limB']})")
            # ---------- one picture: as it always was, plus Add another ----------
            await pg.set_input_files(FILE, F("a")); await pg.wait_for_timeout(500); v = await pg.evaluate(VIEW)
            print(f"   [{theme}]", json.dumps(v, ensure_ascii=False)[:600])
            b0 = v["blocks"][0] if v["blocks"] else {}
            check(len(v["blocks"]) == 1 and b0["st"] == "Found 2 of 2 legs · FanDuel +264. Untick anything that is wrong." and b0["inc"] is None and b0["ticks"] == 2 and b0["name"] == "FanDuel 2-leg +264" and b0["odds"] == "+264",
                  f"[{theme}] one screenshot reads as before: the legs to untick, a name, the price ({b0.get('st')})")
            check(v["one"] and v["load"] and v["more"] and v["clear"] and v["all"] is None and min(v["hs"]) >= 40 and v["over"] <= 0, f"[{theme}] Save slip and Load into betslip are there, with Add another screenshot and Clear beside them (heights {v['hs']})")
            check(v["count"] == "1 of 12 screenshots in this batch.", f"[{theme}] the batch says how many of the twelve are in ({v['count']})")
            if SHOTS: await pg.evaluate("document.getElementById('import').scrollIntoView({block: 'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/import-one-{theme}.png")
            # ---------- a second one joins it: what was typed and unticked in the first stays ----------
            await pg.fill("#impname", "My first"); await pg.evaluate("document.querySelector('#impout li input[data-i=\"1\"]').click()")
            await pg.set_input_files(FILE, F("b")); await pg.wait_for_timeout(500); v = await pg.evaluate(VIEW)
            print(f"   [{theme}]", json.dumps(v, ensure_ascii=False)[:900])
            check(len(v["blocks"]) == 2 and [x["head"] for x in v["blocks"]] == ["Screenshot 1", "Screenshot 2"] and v["blocks"][0]["name"] == "My first" and v["blocks"][0]["inc"] is True and v["blocks"][1]["inc"] is True,
                  f"[{theme}] adding a second screenshot gives each its own block; the name typed for the first one is kept ({[x['head'] + ': ' + str(x['name']) for x in v['blocks']]})")
            unt = await pg.evaluate("Array.from(document.querySelectorAll('#impout .impb')[0].querySelectorAll('li input[type=checkbox]')).map(function(c){ return c.checked; })")
            check(unt == [True, False], f"[{theme}] and the leg unticked in the first one stays unticked ({unt})")
            check(v["blocks"][1]["st"] == "Found 2 of 3 legs · FanDuel +650." and v["blocks"][1]["miss"] == 1 and v["blocks"][1]["open"] is True and v["blocks"][0]["open"] is True,
                  f"[{theme}] a screenshot with a leg that was not imported opens its legs so it is seen ({v['blocks'][1]['st']}, open {v['blocks'][1]['open']})")
            check(v["all"] == "Save 2 slips" and not v["one"] and not v["load"] and v["over"] <= 0, f"[{theme}] one button saves them all ({v['all']})")
            await pg.evaluate("document.querySelectorAll('#impout .impon')[1].click()"); await pg.wait_for_timeout(120); t1 = await pg.evaluate("document.getElementById('impsaveall').textContent")
            await pg.evaluate("document.querySelectorAll('#impout .impon')[1].click()"); await pg.wait_for_timeout(120); t2 = await pg.evaluate("document.getElementById('impsaveall').textContent")
            check(t1 == "Save 1 slip" and t2 == "Save 2 slips", f"[{theme}] unticking a screenshot takes it out of the count ({t1} -> {t2})")
            if SHOTS: await pg.evaluate("document.getElementById('import').scrollIntoView({block: 'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/import-two-{theme}.png", full_page=False)
            await pg.click("#impsaveall"); await pg.wait_for_timeout(1500); sv = await pg.evaluate(SAVED); dn = await pg.evaluate(DONE)
            print(f"   [{theme}]", json.dumps(sv, ensure_ascii=False)[:700]); print(f"   [{theme}]", json.dumps(dn, ensure_ascii=False)[:800])
            new = [s for s in sv if s["src"] == "fanduel-screenshot"]
            check(len(sv) == 3 and len(new) == 2 and new[0]["name"] == "My first" and new[0]["keys"] == [A] and new[0]["odds"] == 264 and new[1]["name"] == "FanDuel 2-leg +650" and new[1]["keys"] == [A, C] and new[1]["odds"] == 650 and new[1]["stake"] == 5 and new[0]["id"] != new[1]["id"],
                  f"[{theme}] Save 2 slips saves both, each with its own legs, name, price and stake ({[(s['name'], len(s['keys']), s['odds']) for s in new]})")
            check(dn["st"].startswith("Saved 2 slips. They are in your list below") and [r["name"] for r in dn["rows"]] == ["My first", "FanDuel 2-leg +650"] and all(r["load"] and (r["post"] or "").startswith("Post to Social") and int(r["post"].split(" ")[-1]) >= 40 for r in dn["rows"]) and dn["over"] <= 0,
                  f"[{theme}] the card then lists what was saved, each with Load into betslip and Post to Social ({dn['st'][:40]} | {[r['post'] for r in dn['rows']]})")
            check("My first [post]" in dn["list"] and "FanDuel 2-leg +650 [post]" in dn["list"] and "Saved before [post]" in dn["list"], f"[{theme}] and both are in the saved slips list under it straight away ({dn['list']})")
            if SHOTS: await pg.evaluate("document.getElementById('import').scrollIntoView({block: 'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/import-saved-{theme}.png")
            # ---------- post one of them to Social from that list ----------
            await pg.evaluate("document.querySelectorAll('#impout .impdone button[data-psb]')[1].click()"); await pg.wait_for_timeout(900)
            d = await pg.evaluate("() => ({open: !document.getElementById('sdlg').hidden, odds: document.getElementById('sdO').value, title: document.getElementById('sdT').value, legs: document.getElementById('sdL').textContent})")
            check(d["open"] and d["odds"] == "+650" and d["title"] == "" and d["legs"].startswith("2 legs: "), f"[{theme}] Post to Social in that list opens the post form with the screenshot's price ({d})")
            await pg.click("#sdGo"); await pg.wait_for_timeout(1800); dn = await pg.evaluate(DONE); sv = await pg.evaluate(SAVED)
            po = await pg.evaluate("() => { var r = window.__posted; return r ? {keys: r.legs.map(function(l){ return l.k; }), odds: r.fd_odds, week: r.week} : null; }")
            check(po == {"keys": [A, C], "odds": 650, "week": W} and dn["rows"][1]["post"] == "hidden" and dn["rows"][1]["note"].startswith("Posted to Social.") and dn["rows"][0]["post"].startswith("Post to Social") and [s for s in sv if s["name"] == "FanDuel 2-leg +650"][0]["posted"] == 77,
                  f"[{theme}] it posts that slip, its button goes away and the row says Posted to Social; the other slip can still be posted ({po}, {dn['rows'][1]})")
            check("FanDuel 2-leg +650 [on social]" in dn["list"] and "My first [post]" in dn["list"], f"[{theme}] the saved slips list under it shows it as On Social ({dn['list']})")
            check(not errs, f"[{theme}] one, then two: no script errors {errs[:2]}"); await ctx.close()
            # ---------- several chosen at once: good ones, an empty picture, an unreadable one, a repeat, one already saved ----------
            ctx, pg, errs = await fresh()
            await pg.evaluate("window.__says = []; new MutationObserver(function(){ var s = document.querySelector('#impout > .st'); if(s && /^Reading/.test(s.textContent) && window.__says[window.__says.length - 1] !== s.textContent) window.__says.push(s.textContent); }).observe(document.getElementById('impout'), {childList: true, subtree: true})")
            await pg.set_input_files(FILE, F("a", "b", "c", "d", "e", "f")); await pg.wait_for_timeout(1200); v = await pg.evaluate(VIEW); says = await pg.evaluate("window.__says"); reads = await pg.evaluate("window.__reads")
            print(f"   [{theme}]", json.dumps(v, ensure_ascii=False)[:1500])
            check(reads == ["a", "b", "c", "d", "e", "f"] and len(says) == 6 and says[0].startswith("Reading slip 1 of 6") and says[5].startswith("Reading slip 6 of 6"), f"[{theme}] six screenshots chosen together are read one after another, with a count as they go ({says[0][:22]} ... {says[-1][:22] if says else None})")
            bl = v["blocks"]
            check(len(bl) == 6 and [x["no"] for x in bl] == [False, False, True, True, False, False] and bl[2]["why"] == "no FanDuel legs found in it - not imported" and bl[3]["why"] == "could not be read - try a full, uncropped screenshot of the slip - not imported",
                  f"[{theme}] each gets a block; a picture with no legs and one that cannot be read say so and are left out ({[x['why'] for x in bl if x['no']]})")
            check(bl[4]["inc"] is False and bl[4]["dup"] == "Same legs as screenshot 1 - left out unless you tick it." and bl[5]["inc"] is False and bl[5]["dup"] == "Same legs as \"Saved before\", which is already saved - left out unless you tick it.",
                  f"[{theme}] a repeat of another screenshot and a slip that is already saved are left unticked, with the reason ({bl[4]['dup']} / {bl[5]['dup']})")
            check(bl[0]["open"] is False and bl[1]["open"] is True and v["all"] == "Save 2 slips" and v["over"] <= 0, f"[{theme}] clean screenshots keep their legs folded, and the button counts only what will be saved ({v['all']})")
            if SHOTS: await pg.evaluate("document.getElementById('import').scrollIntoView({block: 'start'}); window.scrollBy(0, -70)"); await pg.wait_for_timeout(200); await pg.screenshot(path=f"{SHOTS}/import-six-{theme}.png", full_page=True)
            await pg.click("#impsaveall"); await pg.wait_for_timeout(1200); sv = await pg.evaluate(SAVED)
            check(len(sv) == 3 and [s["name"] for s in sv[1:]] == ["FanDuel 2-leg +264", "FanDuel 2-leg +650"], f"[{theme}] saving keeps the two good ones and nothing else ({[s['name'] for s in sv]})")
            # everything unticked: nothing to save, and it says so
            await pg.set_input_files(FILE, F("e", "f")); await pg.wait_for_timeout(600); v = await pg.evaluate(VIEW)
            check(v["all"] == "Save 0 slips (off)" and all(x["inc"] is False for x in v["blocks"]), f"[{theme}] when every screenshot is a repeat the button is off ({v['all']})")
            await pg.click("#impclear"); await pg.wait_for_timeout(150)
            check(await pg.evaluate("document.getElementById('impout').innerHTML === ''"), f"[{theme}] Clear empties the queue")
            # one picture that came to nothing keeps its old answer
            await pg.set_input_files(FILE, F("c")); await pg.wait_for_timeout(500); v = await pg.evaluate(VIEW)
            check(v["st0"].startswith("No FanDuel legs found in that picture.") and not v["blocks"], f"[{theme}] one picture with no legs gets the plain answer ({v['st0'][:40]})")
            await pg.set_input_files(FILE, F("d")); await pg.wait_for_timeout(500); v = await pg.evaluate(VIEW)
            check(v["st0"].startswith("Could not read that picture (that file is not a picture we can open)."), f"[{theme}] one picture that cannot be opened says why ({v['st0'][:60]})")
            # more than twelve
            await pg.evaluate("window.__reads = []"); await pg.set_input_files(FILE, F(*["a%d" % i for i in range(14)])); await pg.wait_for_timeout(1800); v = await pg.evaluate(VIEW); reads = await pg.evaluate("window.__reads.length")
            check(reads == 12 and len(v["blocks"]) == 12 and v["note"] == "Only the first 12 screenshots were read. Save these, then add the rest.", f"[{theme}] past twelve it reads twelve and says to add the rest after ({reads} read; {v['note']})")
            check(v["count"] == "12 of 12 screenshots in this batch. That is the most in one go: save these, then add more." and not v["more"] and v["clear"], f"[{theme}] at twelve the batch says it is full and stops offering Add another ({v['count'][:40]}; add-another shown: {v['more']})")
            await pg.click("#impclear")
            # pasting two pictures in one go
            await pg.evaluate("""() => { window.__reads = []; var dt = new DataTransfer(); dt.items.add(new File(['x'], 'a.png', {type: 'image/png'})); dt.items.add(new File(['y'], 'b.png', {type: 'image/png'})); document.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""")
            await pg.wait_for_timeout(700); v = await pg.evaluate(VIEW); reads = await pg.evaluate("window.__reads")
            check(reads == ["a", "b"] and len(v["blocks"]) == 2 and [x["head"] for x in v["blocks"]] == ["Screenshot 1", "Screenshot 2"], f"[{theme}] a paste with two pictures queues both ({reads}, {len(v['blocks'])} blocks)")
            check(not errs, f"[{theme}] several at once: no script errors {errs[:2]}"); await ctx.close()
            # ---------- nothing saved yet: the empty list itself offers the import; the menu and a link land on it ----------
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}');localStorage.setItem('t_seeded','1');localStorage.setItem('bs_me_fold2', JSON.stringify({{crec: false}}))}}catch(e){{}}" + FAKE); await ctx.route("**/*", rt)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto(B + "/me/#import", wait_until="domcontentloaded"); await pg.wait_for_timeout(2600)
            dl = await pg.evaluate("() => { var p = document.getElementById('import'), r = p.getBoundingClientRect(); return {shut: document.getElementById('crec').classList.contains('shut'), top: Math.round(r.top), h: Math.round(r.height), vh: innerHeight}; }")
            check(not dl["shut"] and dl["h"] > 0 and 0 <= dl["top"] < dl["vh"] * 0.6, f"[{theme}] a link to /me/#import opens Your slips even if it was folded and lands on the importer ({dl})")
            em = await pg.evaluate("() => { var a = document.querySelector('#slips [data-impgo]'), li = document.querySelector('#slips li.none'); return {btn: a ? a.textContent : null, first: li ? (li.querySelector('.meact a') || {}).textContent : null, text: li ? li.textContent.slice(0, 60) : null, h: a ? Math.round(a.getBoundingClientRect().height) : 0}; }")
            check(em["btn"] == "Import FanDuel screenshots" and em["first"] == "Import FanDuel screenshots" and em["h"] >= 40, f"[{theme}] with nothing saved, the empty list leads with Import FanDuel screenshots ({em})")
            try:
                async with pg.expect_file_chooser(timeout=3000) as fc: await pg.click("#slips [data-impgo]")
                chooser = await fc.value; opened = chooser.is_multiple()
            except Exception as e: opened = f"no chooser: {str(e)[:60]}"
            check(opened is True, f"[{theme}] tapping it opens the picture chooser, several allowed ({opened})")
            nav = await pg.evaluate("() => { var a = document.querySelector('#sitenav a[href=\"/me/#import\"]'); return a ? a.textContent : null; }")
            check(nav is not None and nav.startswith("Import FanDuel slips") and "12 at a time" in nav, f"[{theme}] the site menu has Import FanDuel slips ({nav})")
            check(not errs, f"[{theme}] empty state: no script errors {errs[:2]}"); await ctx.close()
        await b.close()
    srv.shutdown(); print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
