"""My BetSweep carries the Social profile (owner 11/19: "My BetSweep and my profile on the social page need to combine"): one card with the
username, avatar, posted record and the editor; the header pill shows the same avatar. The real account script runs against a stand-in
Supabase client (no network).   python3 tests/me_profile.py [shots_dir]"""
import asyncio, os, sys, threading, http.server, functools
from playwright.async_api import async_playwright
ROOT = os.environ.get("SITE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
ME = "11111111-1111-1111-1111-111111111111"
FAKE = """
window.__CALLS = []; window.__PROF = {user_id: '%s', handle: 'BlitzRaven42', color: 2, emoji: null};
(function(){
  function q(table){ var f = {}, P = new Proxy(function(){}, {get: function(_, k){
      if(k === 'then') return function(res, rej){ var d = table === 'feed_records' ? [{user_id: '%s', graded: 5, won: 3, lost: 2, units: 1.4, posts: 6}] : table === 'feed_follows' ? [{follower: 'a'}, {follower: 'b'}] : []; return Promise.resolve({data: d, error: null}).then(res, rej); };
      return function(){ return P; }; }}); return P; }
  var S = {user: {id: '%s', email: 'joe@example.com'}};
  window.supabase = {createClient: function(){ return {
    auth: {getSession: function(){ return Promise.resolve({data: {session: window.__OUT ? null : S}}); }, onAuthStateChange: function(){ return {data: {subscription: {unsubscribe: function(){}}}}; }, signOut: function(){ return Promise.resolve({}); }},
    from: function(t){ return q(t); },
    rpc: function(n, a){ window.__CALLS.push(n + (a ? ':' + JSON.stringify(a) : ''));
      if(n === 'feed_profile_me') return Promise.resolve({data: window.__PROF, error: null});
      if(n === 'feed_profile_set'){ if(a.p_emoji === '🍕') return Promise.resolve({data: null, error: {message: 'Pick an avatar from the list'}}); window.__PROF = {user_id: '%s', handle: a.p_handle, color: a.p_color, emoji: a.p_emoji}; return Promise.resolve({data: window.__PROF, error: null}); }
      return Promise.resolve({data: null, error: null}); } }; }};
})();
""" % (ME, ME, ME, ME)
async def main():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8861), functools.partial(H, directory=ROOT)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for theme in ("light", "dark"):
            ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            await ctx.add_init_script(f"try{{localStorage.setItem('bs_theme','{theme}')}}catch(e){{}}" + FAKE)
            async def rt(route, request):
                u = request.url
                if "127.0.0.1" in u: await route.continue_()
                elif "supabase" in u and u.endswith(".js"): await route.fulfill(status=200, content_type="text/javascript", body="/* stand-in */")
                else: await route.abort()
            await ctx.route("**/*", rt)
            pg = await ctx.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            await pg.goto("http://127.0.0.1:8861/me/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1500)
            d = await pg.evaluate("(function(){ var m = document.getElementById('mep'), a = document.querySelector('#bsacct a.me'); return {vis: !m.hidden, h: (m.querySelector('h2') || {}).textContent, av: (m.querySelector('.pav') || {}).textContent, cls: (m.querySelector('.pav') || {}).className, line: (m.querySelector('.pn p') || {}).textContent, links: [...m.querySelectorAll('.pb a, .pb button')].map(function(x){ return x.textContent + '|' + (x.getAttribute('href') || ''); }), pill: a ? a.querySelector('i').textContent : null, first: document.querySelector('.me h1').nextElementSibling.id, over: document.documentElement.scrollWidth - innerWidth}; })()")
            check(d["vis"] and d["h"] == "@BlitzRaven42" and d["av"] == "BR" and "c2" in d["cls"] and d["first"] == "mep", f"[{theme}] signed in, My BetSweep opens on the profile card: username, initials on the chosen colour ({d['h']}, {d['av']}, {d['cls']})")
            check("3-2" in d["line"] and "+1.4 units" in d["line"] and "2 followers" in d["line"], f"[{theme}] the card carries the posted record and followers ({d['line']})")
            check(d["links"] == ["Edit profile|", f"My posted slips|/social/#u={ME}"], f"[{theme}] two actions: Edit profile, My posted slips ({d['links']})")
            check(d["pill"] == "B" and d["over"] <= 0, f"[{theme}] the header pill shows the username's initial, no sideways scroll ({d['pill']}, {d['over']})")
            await pg.click('#mep [data-pe="1"]'); await pg.wait_for_timeout(300)
            e = await pg.evaluate("(function(){ var a = [...document.querySelectorAll('#mep input[name=e]')], t = [...document.querySelectorAll('#mep label[title]')]; return [a.length, new Set(a.map(function(i){ return i.value; })).size, t.length, t.filter(function(l){ return l.getBoundingClientRect().width >= 44; }).length, document.querySelectorAll('#mep input[name=c]').length, document.documentElement.scrollWidth - innerWidth]; })()")
            check(e == [49, 49, 32, 32, 8, 0] or (e[:5] == [49, 49, 32, 32, 8] and e[5] <= 0), f"[{theme}] the editor offers 8 colours, initials, 16 emoji and the 32 teams, each a 44px target, no sideways scroll ({e})")
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"me_profile_edit_{theme}.png"), full_page=False)
            await pg.fill('#peh', 'bad name'); await pg.click('#mep .sv'); await pg.wait_for_timeout(200)
            check("3 to 20" in await pg.inner_text('#pemsg') and not any("feed_profile_set" in c for c in await pg.evaluate("window.__CALLS")), f"[{theme}] a bad username is stopped on the page, nothing is sent")
            await pg.fill('#peh', 'JoeyMac'); await pg.evaluate("document.querySelector('#mep input[name=c][value=\"5\"]').click(); document.querySelector('#mep label[title=\"Titans\"] input').click()")
            await pg.click('#mep .sv'); await pg.wait_for_timeout(500)
            s = await pg.evaluate("(function(){ var m = document.getElementById('mep'); return {h: m.querySelector('h2').textContent, av: m.querySelector('.pav').textContent, cls: m.querySelector('.pav').className, form: !!document.getElementById('pedit'), pill: document.querySelector('#bsacct a.me i').textContent, call: window.__CALLS.filter(function(x){ return /feed_profile_set.*JoeyMac.*\"p_color\":5/.test(x); }).length, cache: JSON.parse(localStorage.getItem('bs_prof') || '{}').handle}; })()")
            check(s["h"] == "@JoeyMac" and s["av"] == "⚔️" and "c5" in s["cls"] and not s["form"] and s["call"] == 1, f"[{theme}] saving sends one request and the card shows the new name, colour and team avatar ({s})")
            check(s["pill"] == "⚔️" and s["cache"] == "JoeyMac", f"[{theme}] the header pill takes the new avatar at once and it is remembered for the next page ({s['pill']}, {s['cache']})")
            if SHOTS: await pg.screenshot(path=os.path.join(SHOTS, f"me_profile_{theme}.png"), full_page=False)
            # the next page: the pill paints from the remembered profile
            await pg.goto("http://127.0.0.1:8861/social/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1200)
            pill = await pg.evaluate("(document.querySelector('#bsacct a.me i') || {}).textContent"); mb = await pg.evaluate("(function(){ var b = document.getElementById('mebtn'); return b ? [b.hidden, b.textContent] : null; })()")
            check(pill == "⚔️" and mb and mb[1] == "My slips", f"[{theme}] on Social the header shows the same avatar and the shortcut reads My slips ({pill}, {mb})")
            check(not errs, f"[{theme}] no script errors ({errs[:2]})")
            await ctx.close()
        # signed out: no card
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True); await ctx.add_init_script("window.__OUT = 1;" + FAKE); await ctx.route("**/*", rt)
        pg = await ctx.new_page(); await pg.goto("http://127.0.0.1:8861/me/", wait_until="domcontentloaded"); await pg.wait_for_timeout(1200)
        check(await pg.evaluate("document.getElementById('mep').hidden") and "Not signed in" in await pg.inner_text('#who'), "signed out, there is no profile card and the page says so")
        await b.close()
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
asyncio.run(main())
