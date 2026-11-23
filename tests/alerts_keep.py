"""Alerts stay on (owner 11/23: "I keep having to turn on alerts. Why won't it just stay on?").
A phone can drop its push sign-up, and the alert service removes a device its push service reports gone. The site now puts both back
by itself (account.py KEEP_JS, on every page through account.js and inline on My BetSweep) and carries the reader's choices over.
Serves ./site with a made-up account client, a made-up database table with the owner-only rule, and a made-up push service; no network.
   python3 tests/alerts_keep.py [shots_dir]"""
import asyncio, json, os, re, subprocess, sys, tempfile, threading, http.server, functools
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
PORT = 8889; BASE = f"http://127.0.0.1:{PORT}"
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)

FAKE = r"""
(function(){
  var LS = localStorage;
  function g(k, d){ try { var v = LS.getItem(k); return v === null ? d : JSON.parse(v); } catch(e){ return d; } }
  function s(k, v){ LS.setItem(k, JSON.stringify(v)); }
  function bump(k){ s(k, g(k, 0) + 1); }
  var COLS = {live: true, weekly: true, promo: false, news: false, team: null};
  function q(table){
    var f = [], op = 'select', vals = null, ret = false, single = false;
    function exec(){
      if(g('t_down', false)) return {data: null, error: {message: 'Failed to fetch'}};
      if(table !== 'push_subs') return {data: single ? null : [], error: null};
      var rows = g('t_db', []), me = g('t_user', null), nocol = g('t_nocol', []);
      function mine(r){ return r.user_id === me && f.every(function(x){ return r[x[0]] === x[1]; }); }
      if(op === 'select'){ var out = rows.filter(mine); return {data: single ? (out[0] || null) : out, error: null}; }
      if(op === 'upsert'){
        var ex = rows.filter(function(r){ return r.endpoint === vals.endpoint; })[0];
        if((ex && ex.user_id !== me) || vals.user_id !== me) return {data: null, error: {code: '42501', message: 'new row violates row-level security policy for table "push_subs"'}};
        if(ex) Object.keys(vals).forEach(function(k){ ex[k] = vals[k]; });
        else { var nr = {}; Object.keys(COLS).forEach(function(k){ if(nocol.indexOf(k) < 0) nr[k] = COLS[k]; }); Object.keys(vals).forEach(function(k){ nr[k] = vals[k]; }); rows.push(nr); }
        s('t_db', rows); return {data: null, error: null};
      }
      if(op === 'update'){
        var bad = Object.keys(vals).filter(function(k){ return nocol.indexOf(k) >= 0; });
        if(bad.length) return {data: null, error: {message: 'column push_subs.' + bad[0] + ' does not exist'}};
        var hit = rows.filter(mine); hit.forEach(function(r){ Object.keys(vals).forEach(function(k){ r[k] = vals[k]; }); }); s('t_db', rows);
        return {data: ret ? hit.map(function(r){ return {endpoint: r.endpoint}; }) : null, error: null};
      }
      if(op === 'delete'){ s('t_db', rows.filter(function(r){ return !mine(r); })); return {data: null, error: null}; }
      return {data: null, error: null};
    }
    function run(){ return new Promise(function(res){ setTimeout(function(){ if(table === 'push_subs') bump('t_calls'); res(exec()); }, 25); }); }
    var b = new Proxy({}, {get: function(_, name){
      if(name === 'then') return function(a, c){ return run().then(a, c); };
      if(name === 'catch') return function(c){ return run().catch(c); };
      if(name === 'select') return function(){ if(op !== 'select') ret = true; return b; };
      if(name === 'eq') return function(k, v){ f.push([k, v]); return b; };
      if(name === 'maybeSingle' || name === 'single') return function(){ single = true; return b; };
      if(name === 'upsert' || name === 'update' || name === 'insert') return function(v){ op = name; vals = v; return b; };
      if(name === 'delete') return function(){ op = 'delete'; return b; };
      return function(){ return b; };
    }});
    return b;
  }
  var client = {
    auth: {
      getSession: function(){ var u = g('t_user', null); return Promise.resolve({data: {session: u ? {user: {id: u, email: u + '@example.test'}, access_token: 'tok'} : null}}); },
      onAuthStateChange: function(){ return {data: {subscription: {unsubscribe: function(){}}}}; },
      signOut: function(){ s('t_user', null); return Promise.resolve({}); }
    },
    from: q, rpc: function(){ return Promise.resolve({data: null, error: null}); }
  };
  window.supabase = {createClient: function(){ return client; }};
  /* the push service: one sign-up per browser, a new address each time one is made */
  function fakeSub(ep){ return {endpoint: ep, toJSON: function(){ return {endpoint: ep, keys: {p256dh: 'p-' + ep.slice(-3), auth: 'a-' + ep.slice(-3)}}; }, unsubscribe: function(){ s('t_sub', ''); bump('t_unsubs'); return Promise.resolve(true); }}; }
  var pm = {
    getSubscription: function(){ if(g('t_blind', false)) return Promise.resolve(null); if(g('t_nullonce', 0) > 0){ s('t_nullonce', g('t_nullonce', 0) - 1); return Promise.resolve(null); } var ep = g('t_sub', ''); return Promise.resolve(ep ? fakeSub(ep) : null); },
    subscribe: function(){ bump('t_subs');
      if(g('t_subfail', false)) return Promise.reject(new Error('push service error'));
      if(g('t_perm', 'default') !== 'granted') return Promise.reject(new Error('Push notification prompting can only be done from a user gesture'));
      if(g('t_blind', false) && g('t_sub', '')) return Promise.resolve(fakeSub(g('t_sub', '')));
      var n = g('t_n', 0) + 1; s('t_n', n); var ep = 'https://push.example.test/send/e' + n; s('t_sub', ep); return Promise.resolve(fakeSub(ep)); }
  };
  var reg = {pushManager: pm, showNotification: function(){ return Promise.resolve(); }};
  var sw = {ready: g('t_nosw', false) ? new Promise(function(){}) : Promise.resolve(reg), register: function(){ return Promise.resolve(reg); }, addEventListener: function(){}, controller: null, getRegistration: function(){ return Promise.resolve(reg); }};
  try { Object.defineProperty(Navigator.prototype, 'serviceWorker', {get: function(){ return sw; }, configurable: true}); } catch(e){}
  if(!g('t_nopush', false)) window.PushManager = window.PushManager || function(){}; else { try { delete window.PushManager; } catch(e){} }
  var N = {requestPermission: function(){ bump('t_prompts'); if(g('t_perm', 'default') === 'default') s('t_perm', g('t_answer', 'granted')); return Promise.resolve(g('t_perm', 'default')); }};
  Object.defineProperty(N, 'permission', {get: function(){ return g('t_perm', 'default'); }});
  try { Object.defineProperty(window, 'Notification', {value: N, configurable: true, writable: true}); } catch(e){ window.Notification = N; }
  /* what the reader saw: was the "Turn on alerts" button ever on screen, and every line the card said */
  window.__everOn = false; window.__msgs = [];
  document.addEventListener('DOMContentLoaded', function(){
    var b = document.getElementById('pushon'), m = document.getElementById('pushmsg'); if(!b || !m) return;
    new MutationObserver(function(){ if(!b.hidden) window.__everOn = true; }).observe(b, {attributes: true});
    new MutationObserver(function(){ window.__msgs.push(m.textContent); }).observe(m, {childList: true, characterData: true, subtree: true});
  });
})();
"""
READ = """() => { function g(k, d){ try { var v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch(e){ return d; } }
  var q = function(id){ var e = document.getElementById(id); return e ? {hidden: !!e.hidden, text: e.textContent, checked: !!e.checked, value: e.value} : null; };
  return {db: g('t_db', []), sub: g('t_sub', ''), subs: g('t_subs', 0), prompts: g('t_prompts', 0), unsubs: g('t_unsubs', 0), calls: g('t_calls', 0), note: g('bs_push_dev', {}),
          on: q('pushon'), off: q('pushoff'), test: q('pushtest'), msg: q('pushmsg'), promo: q('pppromo'), promolab: q('pppromolab'), news: q('ppnews'), newslab: q('ppnewslab'), team: q('ppteam'), live: q('pplive'), weekly: q('ppweekly'), prefs: q('pushprefs'),
          everOn: !!window.__everOn, msgs: window.__msgs || []}; }"""
ONCE = re.compile(r"^Alerts are on for this device\. It lost its sign-up once and was switched back on for you \([A-Z][a-z]{2} \d{1,2}, \d{1,2}:\d{2}\s?[AP]M\)\.$")
MANY = lambda n: re.compile(r"^Alerts are on for this device\. It lost its sign-up %d times and was switched back on each time \(last [A-Z][a-z]{2} \d{1,2}, \d{1,2}:\d{2}\s?[AP]M\)\.$" % n)
PLAIN = "Alerts are on for this device."
SIGNIN = "Sign in (top right) to turn on alerts."

def rows(st, user): return [r for r in st["db"] if r["user_id"] == user]
def pick(r): return {k: r.get(k) for k in ("promo", "news", "team", "live", "weekly")}
def nc(st): return st["note"].get("c") or {}

async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        errs = []
        async def ctx_new(seed, theme="dark", vp=(390, 844)):
            ctx = await b.new_context(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=2, is_mobile=vp[0] < 700, has_touch=vp[0] < 700)
            first = "try{ if(!localStorage.getItem('t_seeded')){ var S = %s; Object.keys(S).forEach(function(k){ localStorage.setItem(k, JSON.stringify(S[k])); }); localStorage.setItem('t_seeded', '1'); localStorage.setItem('bs_theme', '%s'); } }catch(e){}" % (json.dumps(seed), theme)
            await ctx.add_init_script(first + FAKE)
            await ctx.route("**/cdn.jsdelivr.net/**", lambda r: r.abort()); await ctx.route("**/*supabase.co/**", lambda r: r.abort())
            await ctx.route("**/*espn.com/**", lambda r: r.fulfill(status=200, content_type="application/json", body='{"events":[]}'))
            await ctx.route("**/raw.githubusercontent.com/**", lambda r: r.fulfill(status=404, content_type="text/plain", body="none"))
            pg = await ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            return ctx, pg
        async def me(pg, wait=2600): await pg.goto(BASE + "/me/", wait_until="domcontentloaded"); await pg.wait_for_timeout(wait); return await pg.evaluate(READ)
        async def home(pg, wait=4600): await pg.goto(BASE + "/", wait_until="domcontentloaded"); await pg.wait_for_timeout(wait); return await pg.evaluate(READ)
        async def setls(pg, **kv): await pg.evaluate("(kv) => { Object.keys(kv).forEach(function(k){ localStorage.setItem(k, JSON.stringify(kv[k])); }); }", kv)
        async def tap(pg, id_, wait=700): await pg.evaluate("(i) => document.getElementById(i).click()", id_); await pg.wait_for_timeout(wait); return await pg.evaluate(READ)
        async def tick(pg, id_, val, wait=500):
            await pg.evaluate("(a) => { var e = document.getElementById(a[0]); if(e.type === 'checkbox') e.checked = a[1]; else e.value = a[1]; e.dispatchEvent(new Event('change', {bubbles: true})); }", [id_, val]); await pg.wait_for_timeout(wait); return await pg.evaluate(READ)

        # ---------- A. turning alerts on the first time ----------
        ctx, pg = await ctx_new({"t_user": "u-a"})
        st = await me(pg)
        check(not st["on"]["hidden"] and st["off"]["hidden"] and st["msg"]["text"] == "" and st["subs"] == 0 and st["db"] == [] and st["prompts"] == 0, f"A: a signed-in reader who never turned alerts on gets the button and nothing is signed up unasked (button shown {not st['on']['hidden']}, sign-ups {st['subs']}, rows {len(st['db'])})")
        check(SIGNIN not in st["msgs"], f"A: 'Sign in' never flashes at a reader who is signed in (lines shown: {st['msgs']})")
        st = await tap(pg, "pushon")
        r = rows(st, "u-a")
        check(st["prompts"] == 1 and st["sub"].endswith("/e1") and len(st["db"]) == 1 and len(r) == 1 and r[0]["endpoint"] == st["sub"] and r[0]["p256dh"] == "p-/e1" and pick(r[0]) == {"promo": False, "news": False, "team": None, "live": True, "weekly": True}, f"A: the tap asks permission once, signs the device up and saves it with the default choices ({pick(r[0]) if r else None})")
        check(st["msg"]["text"] == PLAIN and st["on"]["hidden"] and not st["off"]["hidden"] and not st["test"]["hidden"] and not st["prefs"]["hidden"] and not st["promolab"]["hidden"] and not st["promo"]["checked"], f"A: the card says alerts are on and shows the choices ({st['msg']['text']!r})")
        n = st["note"]; check(n.get("on") == 1 and n.get("u") == "u-a" and n.get("ep") == st["sub"] and n.get("rn") == 0, f"A: the device keeps a note that alerts are on, whose they are and the sign-up's address (on {n.get('on')}, lost count {n.get('rn')})")
        st = await tick(pg, "pppromo", True); check(rows(st, "u-a")[0]["promo"] is True and st["msg"]["text"] == "On - you will hear when a slip posts." and nc(st).get("promo") is True, f"A: 'when BetSweep posts a slip' saves to the database and to the device's note ({st['msg']['text']!r})")
        st = await tick(pg, "ppnews", True); st = await tick(pg, "ppteam", "TEN"); st = await tick(pg, "pplive", False)
        want = {"promo": True, "news": True, "team": "TEN", "live": False, "weekly": True}
        check(pick(rows(st, "u-a")[0]) == want and {k: nc(st).get(k) for k in want} == want and st["msg"]["text"] == "Saved.", f"A: news, favorite team and live updates save the same way ({pick(rows(st, 'u-a')[0])})")

        # ---------- B. the phone drops its sign-up ----------
        await setls(pg, t_sub="")
        st = await home(pg)
        r = rows(st, "u-a")
        check(st["sub"].endswith("/e2") and st["subs"] == 2 and st["prompts"] == 1, f"B: on any page the site signs the device up again by itself, with no permission prompt (new address {st['sub'][-3:]}, sign-ups {st['subs']}, prompts {st['prompts']})")
        check(len(st["db"]) == 1 and len(r) == 1 and r[0]["endpoint"] == st["sub"] and pick(r[0]) == want, f"B: the new sign-up is saved with the SAME choices and the old address's row is gone (rows {len(st['db'])}, choices {pick(r[0]) if r else None})")
        check(st["note"].get("ep") == st["sub"] and st["note"].get("rn") == 1 and st["note"].get("re", 0) > 0, f"B: the note counts that the sign-up was lost once ({st['note'].get('rn')})")
        st = await me(pg)
        check(not st["everOn"] and st["on"]["hidden"] and bool(ONCE.match(st["msg"]["text"])), f"B: My BetSweep never shows 'Turn on alerts' again and says what happened ({st['msg']['text']!r})")
        check(st["promo"]["checked"] and st["news"]["checked"] and st["team"]["value"] == "TEN" and not st["live"]["checked"] and st["weekly"]["checked"] and st["subs"] == 2, "B: the boxes show the choices that were carried over, and nothing is signed up twice")

        # ---------- C. the database lost the device (the alert service removes a device its push service reports gone) ----------
        await setls(pg, t_db=[])
        st = await home(pg, 3400)
        check(st["db"] == [], f"C: off My BetSweep the database is checked at most every half hour, so a page opened right after does not ask again (rows {len(st['db'])})")
        n = dict(st["note"]); n["t"] = n["t"] - 31 * 60000; await setls(pg, bs_push_dev=n)
        st = await home(pg, 3400)
        r = rows(st, "u-a")
        check(len(r) == 1 and r[0]["endpoint"] == st["sub"] and pick(r[0]) == want and st["subs"] == 2 and st["note"].get("rn") == 2, f"C: half an hour on, any page puts the missing row back with the same address and choices (rows {len(r)}, choices {pick(r[0]) if r else None}, lost count {st['note'].get('rn')})")
        await setls(pg, t_db=[])
        st = await me(pg)
        r = rows(st, "u-a")
        check(len(r) == 1 and pick(r[0]) == want and st["subs"] == 2 and not st["everOn"] and bool(MANY(3).match(st["msg"]["text"])) and st["promo"]["checked"] and st["team"]["value"] == "TEN", f"C: My BetSweep always checks, and puts it back at once ({st['msg']['text']!r})")

        # ---------- D. a choice saved while the row is missing ----------
        await setls(pg, t_db=[])
        st = await tick(pg, "ppnews", False, 800)
        r = rows(st, "u-a"); want2 = dict(want, news=False)
        check(len(r) == 1 and pick(r[0]) == want2 and st["msg"]["text"] == "Saved." and nc(st).get("news") is False, f"D: with the row gone behind the page's back, a change puts the row back and THEN saves - 'Saved' means saved ({pick(r[0]) if r else None})")
        await setls(pg, t_db=[], t_sub="")
        st = await tick(pg, "pppromo", False, 800)
        check(st["db"] == [] and st["promo"]["checked"] and "lost its alert sign-up" in st["msg"]["text"] and "Saved" not in st["msg"]["text"], f"D: with the sign-up gone as well, the box goes back and the card says so instead of 'Saved' ({st['msg']['text']!r})")
        st = await me(pg, 3800)
        r = rows(st, "u-a")
        check(st["sub"].endswith("/e3") and len(st["db"]) == 1 and len(r) == 1 and pick(r[0]) == want2 and not st["everOn"] and st["on"]["hidden"], f"D: the reload switches alerts back on with the choices as they were last saved ({pick(r[0]) if r else None})")

        # ---------- G. an iPhone can answer "no sign-up" right after the app opens ----------
        subs0 = st["subs"]; ep0 = st["sub"]
        await setls(pg, t_nullonce=1); st = await me(pg, 3800)
        check(st["subs"] == subs0 and st["sub"] == ep0 and not st["everOn"] and st["on"]["hidden"] and len(st["db"]) == 1, f"G: a first answer of 'none' is asked again before anything is made, so no second sign-up and no button (sign-ups {st['subs']} = {subs0})")
        await setls(pg, t_nullonce=1); st = await home(pg)
        check(st["subs"] == subs0 and st["sub"] == ep0 and len(st["db"]) == 1, "G: the same on any other page")

        # ---------- H. the push service refuses a new sign-up ----------
        await setls(pg, t_sub="", t_subfail=True)
        st = await home(pg)
        check(st["subs"] == subs0 + 1 and st["sub"] == "" and st["note"].get("f", 0) > 0 and st["note"].get("on") == 1, f"H: a refused sign-up is tried once and noted (tries {st['subs'] - subs0})")
        st = await home(pg)
        check(st["subs"] == subs0 + 1, f"H: the next page does not hammer the push service - it rests ten minutes (tries {st['subs'] - subs0})")
        st = await me(pg, 3800)
        check(st["subs"] == subs0 + 2 and not st["on"]["hidden"] and st["msg"]["text"] == "", f"H: My BetSweep tries again, and when that fails too the button is there for a tap (tries {st['subs'] - subs0}, button shown {not st['on']['hidden']})")
        await setls(pg, t_subfail=False); st = await tap(pg, "pushon")
        r = rows(st, "u-a")
        check(len(r) == 1 and r[0]["endpoint"] == st["sub"] and pick(r[0]) == want2 and st["on"]["hidden"] and st["msg"]["text"].startswith(PLAIN), f"H: the tap brings alerts back with the remembered choices ({pick(r[0]) if r else None})")

        # ---------- F. the phone took the permission back: only a tap can ask again ----------
        subs1 = st["subs"]; pr1 = st["prompts"]
        await setls(pg, t_sub="", t_perm="default")
        st = await home(pg)
        check(st["subs"] == subs1 and st["prompts"] == pr1 and st["sub"] == "", f"F: with permission no longer granted nothing is tried in the background (tries {st['subs'] - subs1}, prompts {st['prompts'] - pr1})")
        st = await me(pg)
        check(not st["on"]["hidden"] and st["subs"] == subs1 and st["prompts"] == pr1, "F: My BetSweep shows the button and waits for the tap")
        st = await tap(pg, "pushon"); r = rows(st, "u-a")
        check(st["prompts"] == pr1 + 1 and len(r) == 1 and r[0]["endpoint"] == st["sub"] and pick(r[0]) == want2, f"F: one tap, and the choices come back with it ({pick(r[0]) if r else None})")

        # ---------- E. "Turn off on this device" stays off ----------
        st = await tap(pg, "pushoff")
        check(st["sub"] == "" and st["db"] == [] and st["note"].get("on") == 0 and "c" not in st["note"] and st["msg"]["text"] == "Alerts are off for this device." and not st["on"]["hidden"], f"E: turning alerts off removes the sign-up and the row, and the note says off ({st['note']})")
        subs2 = st["subs"]
        st = await home(pg)
        check(st["subs"] == subs2 and st["sub"] == "" and st["db"] == [], f"E: nothing switches them back on afterwards (tries {st['subs'] - subs2})")
        st = await me(pg)
        check(not st["on"]["hidden"] and st["msg"]["text"] == "" and st["subs"] == subs2 and st["db"] == [], "E: My BetSweep shows the button, and still nothing is signed up")
        st = await tap(pg, "pushon"); r = rows(st, "u-a")
        check(len(r) == 1 and pick(r[0]) == {"promo": False, "news": False, "team": None, "live": True, "weekly": True} and st["msg"]["text"] == PLAIN, f"E: turned on again by hand, it starts from the default choices - an explicit off forgets them ({pick(r[0]) if r else None})")

        # ---------- I. another account signs in on the same device ----------
        a_ep = st["sub"]; subs3 = st["subs"]; un3 = st["unsubs"]
        await setls(pg, t_user="u-b")
        st = await home(pg)
        check(st["subs"] == subs3 and len(st["db"]) == 1 and rows(st, "u-b") == [] and st["note"].get("u") == "u-a", "I: a second account on the device gets nothing signed up in the background")
        st = await me(pg)
        check(not st["on"]["hidden"] and st["msg"]["text"] == "" and rows(st, "u-b") == [] and PLAIN not in st["msgs"], f"I: it is offered the button - the card does not claim alerts are on for it (lines shown: {st['msgs']})")
        st = await tap(pg, "pushon", 900); rb = rows(st, "u-b")
        check(len(rb) == 1 and rb[0]["endpoint"] == st["sub"] and st["sub"] != a_ep and st["unsubs"] == un3 + 1 and st["note"].get("u") == "u-b" and st["msg"]["text"] == PLAIN and len(rows(st, "u-a")) == 1, f"I: its tap replaces the device's sign-up with one of its own; the first account's row is not touched (rows for the second account {len(rb)}, first account {len(rows(st, 'u-a'))})")
        await ctx.close()

        # ---------- J. a device from before this change (no note) ----------
        old = "https://push.example.test/send/old1"
        ctx, pg = await ctx_new({"t_user": "u-j", "t_perm": "granted", "t_sub": old, "t_db": [{"endpoint": old, "user_id": "u-j", "p256dh": "p", "auth": "a", "live": True, "weekly": False, "promo": True, "news": False, "team": "TEN"}]})
        st = await me(pg)
        check(st["on"]["hidden"] and not st["everOn"] and st["msg"]["text"] == PLAIN and st["promo"]["checked"] and not st["weekly"]["checked"] and st["team"]["value"] == "TEN" and st["subs"] == 0 and st["note"].get("on") == 1 and st["note"].get("ep") == old and nc(st).get("promo") is True, f"J: a device that already had alerts on is taken as on, with its choices noted for next time ({st['note'].get('c')})")
        await ctx.close()
        ctx, pg = await ctx_new({"t_user": "u-k", "t_perm": "granted", "t_sub": old})
        st = await home(pg); c1 = st["calls"]; st = await home(pg, 3400); st2 = await me(pg)
        check(st["db"] == [] and st2["db"] == [] and not st2["on"]["hidden"] and st2["msg"]["text"] == "" and PLAIN not in st2["msgs"] and st2["note"].get("on") is None, "J: a leftover sign-up with no row and no note is NOT taken as this account's - the card shows the button and says nothing false")
        check(c1 == 1 and st["calls"] == 1 and st2["calls"] == 2, f"J: it is looked up once, then left alone for half an hour on other pages; My BetSweep always looks (database calls {c1}, {st['calls']}, {st2['calls']})")
        st = await tap(pg, "pushon"); r = rows(st, "u-k")
        check(len(r) == 1 and r[0]["endpoint"] == old and st["subs"] == 0 and st["msg"]["text"] == PLAIN, "J: one tap saves it, and from then on it keeps itself")
        await ctx.close()

        # ---------- Q. a browser that keeps answering "none" while the sign-up is really still there (reported on iPhone home-screen apps) ----------
        ctx, pg = await ctx_new({"t_user": "u-q", "t_perm": "granted", "t_sub": old, "t_db": [{"endpoint": old, "user_id": "u-q", "p256dh": "p", "auth": "a", "live": True, "weekly": True, "promo": True, "news": False, "team": None}]})
        st = await me(pg); c0 = st["calls"]
        await setls(pg, t_blind=True)
        for _ in range(4): st = await home(pg, 3600)
        check(st["subs"] == 3 and st["calls"] == c0 and st["note"].get("rn") == 0 and st["note"].get("ep") == old and len(st["db"]) == 1, f"Q: it is asked for the sign-up again at most three times an hour in the background, the database is not touched and nothing is counted as lost (asks {st['subs']} over four pages, database calls {st['calls'] - c0}, lost count {st['note'].get('rn')})")
        st = await me(pg, 3800)
        check(st["on"]["hidden"] and not st["everOn"] and st["msg"]["text"] == PLAIN and st["sub"] == old and len(st["db"]) == 1 and st["promo"]["checked"] and st["subs"] == 4, f"Q: My BetSweep still reads as on, with no button and no 'lost' line, because nothing was lost ({st['msg']['text']!r})")
        await ctx.close()

        # ---------- L. signed out; M. database unreachable; N. a database without the newer settings; O. browsers that cannot ----------
        ctx, pg = await ctx_new({"t_user": None, "t_perm": "granted", "t_sub": old, "bs_push_dev": {"on": 1, "u": "u-a", "ep": old, "c": {}, "t": 1}})
        st = await home(pg, 3400); st2 = await me(pg)
        check(st2["msg"]["text"] == SIGNIN and st2["on"]["hidden"] and st2["subs"] == 0 and st2["calls"] == 0 and st["calls"] == 0, f"L: signed out, the card asks for a sign-in and nothing is read or written ({st2['msg']['text']!r})")
        await ctx.close()
        ctx, pg = await ctx_new({"t_user": "u-m", "t_perm": "granted", "t_sub": old, "t_down": True, "bs_push_dev": {"on": 1, "u": "u-m", "ep": old, "c": {"promo": True}, "t": 1, "rn": 0, "re": 0}})
        st = await me(pg)
        check(st["msg"]["text"] == PLAIN and st["on"]["hidden"] and st["promolab"]["hidden"] and st["note"].get("on") == 1 and nc(st).get("promo") is True, f"M: with the database unreachable the card still says alerts are on (the phone holds the sign-up) and the note is left alone ({st['msg']['text']!r})")
        st = await tick(pg, "pplive", False, 700)
        check("Saved" not in st["msg"]["text"] and st["msg"]["text"] != "", f"M: a change that could not be saved says so ({st['msg']['text']!r})")
        await ctx.close()
        ctx, pg = await ctx_new({"t_user": "u-m2", "t_perm": "granted", "t_sub": old, "t_down": True})
        st = await me(pg)
        check(st["msg"]["text"] == PLAIN and st["on"]["hidden"] and st["note"].get("on") is None, f"M: the same for a device from before this change - it reads as on, as it always did, and no note is written on a guess ({st['msg']['text']!r})")
        await ctx.close()
        ctx, pg = await ctx_new({"t_user": "u-n", "t_perm": "default", "t_nocol": ["promo", "news", "team"]})
        st = await me(pg); st = await tap(pg, "pushon")
        check(st["msg"]["text"] == PLAIN and st["promolab"]["hidden"] and st["newslab"]["hidden"] and not st["prefs"]["hidden"] and "promo" not in rows(st, "u-n")[0], "N: a database without the newer settings shows no dead switches")
        await ctx.close()
        ctx, pg = await ctx_new({"t_user": "u-o", "t_nopush": True})
        st = await home(pg, 2600); st2 = await me(pg)
        check(st2["msg"]["text"] == "This browser cannot receive alerts." and st2["on"]["hidden"] and st2["subs"] == 0 and st2["calls"] == 0, f"O: a browser without push says so and nothing is tried ({st2['msg']['text']!r})")
        await ctx.close()
        ctx, pg = await ctx_new({"t_user": "u-p", "t_perm": "denied"})
        st = await me(pg)
        check("blocked" in st["msg"]["text"] and st["on"]["hidden"] and st["subs"] == 0, "O: notifications blocked in the browser's settings: the card says where to allow them")
        await ctx.close()

        # ---------- how the card looks with the longer line (phone light and dark, desktop) ----------
        for theme, vp in (("light", (390, 844)), ("dark", (390, 844)), ("dark", (1280, 900))):
            ctx, pg = await ctx_new({"t_user": "u-s", "t_perm": "granted", "t_sub": old, "t_db": [{"endpoint": old, "user_id": "u-s", "p256dh": "p", "auth": "a", "live": True, "weekly": True, "promo": True, "news": True, "team": "TEN"}],
                                     "bs_push_dev": {"on": 1, "u": "u-s", "ep": old, "c": {}, "t": 1, "rn": 3, "re": 1795464060000}}, theme, vp)
            st = await me(pg)
            g = await pg.evaluate("""() => { var c = document.getElementById('alerts'); c.classList.remove('shut'); var m = document.getElementById('pushmsg'), r = m.getBoundingClientRect(), cr = c.getBoundingClientRect();
              return {w: Math.round(r.width), h: Math.round(r.height), inside: r.left >= cr.left - 1 && r.right <= cr.right + 1, over: document.documentElement.scrollWidth - document.documentElement.clientWidth, color: getComputedStyle(m).color, bg: getComputedStyle(document.body).backgroundColor}; }""")
            check(bool(MANY(3).match(st["msg"]["text"])) and g["inside"] and g["over"] <= 0 and g["h"] > 0 and g["color"] != g["bg"], f"[{theme} {vp[0]}px] the longer line wraps inside the card, no sideways scroll ({g['w']}x{g['h']}px)")
            if SHOTS:
                await pg.evaluate("document.getElementById('alerts').scrollIntoView({block: 'start'})"); await pg.wait_for_timeout(250); await pg.screenshot(path=f"{SHOTS}/alerts-keep-{theme}-{vp[0]}.png")
            await ctx.close()
        check(not errs, f"no script errors {errs[:3]}")
        await b.close()
    srv.shutdown()

    # ---------- the service worker: every push ends in a notification (an iPhone drops the sign-up after three that show nothing) ----------
    swp = os.path.join(ROOT, "sw.js")
    HARN = r"""
const fs = require('fs'); const src = fs.readFileSync(process.argv[2], 'utf8');
const L = {}; let calls = []; let failFirst = false;
const self = {addEventListener: (n, f) => { L[n] = f; }, skipWaiting: () => Promise.resolve(), clients: {claim: () => Promise.resolve(), matchAll: () => Promise.resolve([]), openWindow: () => Promise.resolve()},
  registration: {showNotification: (t, o) => { calls.push({t, o}); if (failFirst && calls.length === 1) return Promise.reject(new Error('refused')); return Promise.resolve(); }}};
const caches = {open: () => Promise.resolve({add: () => Promise.resolve(), put: () => Promise.resolve()}), keys: () => Promise.resolve([]), match: () => Promise.resolve(null), delete: () => Promise.resolve(true)};
new Function('self', 'caches', 'location', 'fetch', src)(self, caches, {origin: 'https://betsweep.co'}, () => Promise.reject(new Error('no network')));
async function fire(data, ff){ calls = []; failFirst = !!ff; let p = null, threw = null; try { L.push({data, waitUntil: (x) => { p = x; }}); } catch (e) { threw = String(e); }
  let settled = 'none'; if (p) { try { await p; settled = 'ok'; } catch (e) { settled = 'rejected'; } } return {threw, settled, n: calls.length, last: calls[calls.length - 1] || null}; }
(async () => { const out = {};
  out.normal = await fire({json: () => ({title: 'Daily Sweep is up', body: 'Four legs', url: '/x/', tag: 'bs-promo'}), text: () => ''});
  out.nulljson = await fire({json: () => null, text: () => 'null'});
  out.string = await fire({json: () => 'hello', text: () => '"hello"'});
  out.badjson = await fire({json: () => { throw new Error('bad'); }, text: () => 'plain words'});
  out.bothbad = await fire({json: () => { throw new Error('bad'); }, text: () => { throw new Error('worse'); }});
  out.nodata = await fire(null);
  out.refused = await fire({json: () => ({title: 'T', body: 'B'}), text: () => ''}, true);
  out.numbers = await fire({json: () => ({title: 42, body: 7, tag: 9}), text: () => ''});
  console.log(JSON.stringify(out)); })();
"""
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "h.js"); open(f, "w", encoding="utf-8").write(HARN)
        r = subprocess.run(["node", f, swp], capture_output=True, text=True, timeout=60)
    try: o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: o = None
    check(o is not None, f"the service worker's push handler runs under node ({(r.stderr or '').strip()[:160]})")
    if o:
        check(all(v["threw"] is None and v["settled"] == "ok" and v["n"] >= 1 for v in o.values()), "sw: every kind of push - a normal message, an empty one, one that is not an object, unreadable text, no data at all - ends in a notification: " + ", ".join(f"{k} {v['n']}" for k, v in o.items()))
        check(o["normal"]["last"]["t"] == "Daily Sweep is up" and o["normal"]["last"]["o"]["body"] == "Four legs" and o["normal"]["last"]["o"]["tag"] == "bs-promo" and o["normal"]["last"]["o"]["data"]["url"] == "/x/", "sw: a normal message shows its own title, text, tag and link")
        check(o["nulljson"]["last"]["t"] == "BetSweep" and o["badjson"]["last"]["o"]["body"] == "plain words" and o["bothbad"]["last"]["t"] == "BetSweep" and o["nodata"]["last"]["t"] == "BetSweep", "sw: a message it cannot read still shows as a BetSweep notification")
        check(o["refused"]["n"] == 2 and o["refused"]["last"]["t"] == "T" and o["refused"]["last"]["o"] == {"body": "B"}, "sw: when the first try to show it is refused, a plain one is shown instead")
        check(o["numbers"]["last"]["t"] == "42" and o["numbers"]["last"]["o"]["body"] == "7" and o["numbers"]["last"]["o"]["tag"] == "9", "sw: odd value types are turned into text rather than refused")

    # ---------- the built files carry it ----------
    acct = open(os.path.join(ROOT, "account.js"), encoding="utf-8").read(); mep = open(os.path.join(ROOT, "me", "index.html"), encoding="utf-8").read()
    check("window.bsPushKeep = window.bsPushKeep ||" in acct and "window.bsPushKeep = window.bsPushKeep ||" in mep and "__VAPID__" not in acct and "__VAPID__" not in mep and "__KEEP__" not in acct, "account.js (every page) and My BetSweep both carry the keeper, with the public key filled in")
    check("bs_push_dev" in acct and not re.search(r"SYNC = /\^bs_\([^/]*push_dev", acct), "the device's note is not one of the keys that follow the account to other devices")
    for secret in ("VAPID_PRIVATE", "service_role", "CRON_SECRET", "sb_secret_"):
        check(secret not in acct and secret not in mep, f"no secret name in the public files ({secret})")
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
