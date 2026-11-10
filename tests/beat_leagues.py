#!/usr/bin/env python3
"""tests/beat_leagues.py - the "Your leagues" card on /beat/ (owner 11/10), with Supabase stood in for.

Needs a built site served locally (BASE, default http://localhost:8802). window.bsAccount is replaced by a small in-page fake whose
rpc() behaves like sql/betsweep-leagues.sql (the SQL itself is tested by tests/leagues_test.sql on a real Postgres). Checks: the card
hides itself while the functions are not installed; signed out it asks for a sign-in (and says so when there is an invite in the
address); start a league, see the board and the invite link; an invite link joins and cleans the address; leave; phone width; no errors.
"""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
BASE = os.environ.get("BASE", "http://localhost:8802")
FAKE = r"""
(function(){
  var MODE = %(mode)s, DB = {leagues: %(leagues)s};   // leagues: [{code, name, owner, members:[names], board:[rows]}]
  function chain(){ var p = Promise.resolve({data: [], error: null}); var o = {}; ['select','eq','not','order','limit','upsert','in','gte'].forEach(function(k){ o[k] = function(){ return o; }; });
    o.maybeSingle = function(){ return Promise.resolve({data: null, error: null}); }; o.then = function(a, b){ return p.then(a, b); }; o.catch = function(a){ return p.catch(a); }; return o; }
  function rpc(fn, a){ a = a || {};
    if(MODE === 'missing') return Promise.resolve({data: null, error: {code: 'PGRST202', message: 'Could not find the function public.' + fn + ' in the schema cache'}});
    var L = DB.leagues, f = function(c){ return L.filter(function(l){ return l.code === String(c || '').toLowerCase(); })[0]; };
    if(fn === 'beat_league_mine') return Promise.resolve({data: L.filter(function(l){ return l.in; }).map(function(l){ return {code: l.code, name: l.name, members: l.board.filter(function(r){ return !r.model; }).length, owner: !!l.owner}; }), error: null});
    if(fn === 'beat_league_create'){ var n = {code: 'new12345', name: a.p_name, owner: true, in: true, board: [{name: 'Me', hits: 0, weeks: 0, week_hits: null, picked: false, me: true, model: false}]}; L.push(n); return Promise.resolve({data: [{code: n.code, name: n.name}], error: null}); }
    if(fn === 'beat_league_join'){ var l = f(a.p_code); if(!l) return Promise.resolve({data: null, error: {message: 'No league has that code.'}}); l.in = true; return Promise.resolve({data: [{code: l.code, name: l.name}], error: null}); }
    if(fn === 'beat_league_board'){ var l2 = f(a.p_code); return Promise.resolve({data: l2 && l2.in ? l2.board : [], error: null}); }
    if(fn === 'beat_league_leave'){ var l3 = f(a.p_code); if(l3) l3.in = false; return Promise.resolve({data: true, error: null}); }
    return Promise.resolve({data: true, error: null}); }
  var acct = MODE === 'out' ? {user: null, client: {from: chain, rpc: rpc}} : {user: {id: 'u1'}, client: {from: chain, rpc: rpc}};
  Object.defineProperty(window, 'bsAccount', {get: function(){ return acct; }, set: function(){}, configurable: true});
  window.__rpcDB = DB;
})();
"""
BOARD = [{"name": "Ace", "hits": 9, "weeks": 2, "week_hits": None, "picked": True, "me": False, "model": False}, {"name": "The model", "hits": 7, "weeks": 2, "week_hits": None, "picked": True, "me": False, "model": True},
         {"name": "Joey", "hits": 6, "weeks": 2, "week_hits": None, "picked": False, "me": True, "model": False}]

async def run():
    fails = []
    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok: fails.append(what)
    async with async_playwright() as p:
        br = await p.chromium.launch()
        async def open_page(mode, leagues, path="/beat/", w=390):
            ctx = await br.new_context(viewport={"width": w, "height": 844}); pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            async def route(r):
                if r.request.url.startswith(BASE): await r.continue_()
                else: await r.abort()
            await pg.route("**/*", route)
            await ctx.add_init_script(FAKE % {"mode": json.dumps(mode), "leagues": json.dumps(leagues)})
            await pg.goto(BASE + path, wait_until="load"); await pg.wait_for_timeout(900)
            return ctx, pg, errs
        S = """()=>{ const c=document.getElementById('btlg'), b=document.getElementById('btlgbody'); return {hidden: c.hidden, txt: b.textContent.replace(/\\s+/g,' '), chips: [...b.querySelectorAll('.lgchips button')].map(x=>x.textContent),
              rows: [...b.querySelectorAll('table.lb tbody tr')].map(tr=>[...tr.children].map(td=>td.textContent)), acts: [...b.querySelectorAll('[data-act]')].map(x=>x.dataset.act), url: location.search,
              sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth} }"""
        ctx, pg, errs = await open_page("missing", [])
        v = await pg.evaluate(S); check(v["hidden"] and not errs, f"functions not installed: the card hides itself, nothing breaks {errs[:2]}"); await ctx.close()
        ctx, pg, errs = await open_page("out", [], path="/beat/?league=abc12345")
        v = await pg.evaluate(S); check(not v["hidden"] and "You were invited" in v["txt"] and "Sign in" in v["txt"], "signed out with an invite: asks for a sign-in"); await ctx.close()
        ctx, pg, errs = await open_page("in", [])
        v = await pg.evaluate(S); check("No league yet" in v["txt"] and v["acts"] == ["create"], f"signed in, no league: explains and offers to start one {v['acts']}")
        await pg.fill("#lgname", "Sunday Crew"); await pg.click('[data-act="create"]'); await pg.wait_for_timeout(500); v = await pg.evaluate(S)
        check(v["chips"] == ["Sunday Crew"] and "betsweep.co/beat/?league=new12345" in v["txt"] and "Started Sunday Crew" in v["txt"], f"start a league: chip, invite link, confirmation {v['chips']}")
        check(len(v["rows"]) == 1 and "Me (you)" in v["rows"][0][1] and set(["share", "copy", "rename", "close", "leave", "create"]) <= set(v["acts"]), "the owner sees the board and Rename / Close")
        check(v["sw"] <= v["cw"] and not errs, f"fits a phone, no errors ({v['sw']}/{v['cw']}) {errs[:2]}"); await ctx.close()
        lg = [{"code": "abc12345", "name": "The Office", "owner": False, "in": False, "board": BOARD}]
        ctx, pg, errs = await open_page("in", lg, path="/beat/?league=ABC12345")
        v = await pg.evaluate(S)
        check(v["chips"] == ["The Office"] and "You are in The Office" in v["txt"] and "league=" not in v["url"], f"an invite link joins and the address is cleaned ({v['url']!r})")
        check([r[1] for r in v["rows"]] == ["Ace", "The model", "Joey (you)"] and v["rows"][0][4] == "in" and v["rows"][2][4] == "not yet" and v["rows"][1][0] == "—" and v["rows"][2][0] == "2", f"board: order, the model unranked, this week's status {v['rows']}")
        check("rename" not in v["acts"] and "close" not in v["acts"] and "leave" in v["acts"], "a member (not the owner) gets Leave only")
        pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await pg.click('[data-act="leave"]'); await pg.wait_for_timeout(500); v = await pg.evaluate(S)
        check(v["chips"] == [] and "You left The Office" in v["txt"] and not errs, f"leave: gone from the list {errs[:2]}"); await ctx.close()
        ctx, pg, errs = await open_page("in", [{"code": "abc12345", "name": "The Office", "owner": False, "in": True, "board": BOARD}], path="/beat/?league=zzzz9999")
        v = await pg.evaluate(S); check("No league has that code" in v["txt"] and v["chips"] == ["The Office"], "a bad invite code says so and keeps the leagues you have"); await ctx.close()
        ctx, pg, errs = await open_page("in", [{"code": "abc12345", "name": "The Office", "owner": True, "in": True, "board": BOARD}], w=1280)
        v = await pg.evaluate(S); check(v["sw"] <= v["cw"] and not errs and len(v["rows"]) == 3, "desktop: board shows, no sideways scroll, no errors"); await ctx.close()
        await br.close()
    return fails

if __name__ == "__main__":
    f = asyncio.run(run()); print("beat leagues:", "all checks passed" if not f else f"{len(f)} FAILED"); sys.exit(1 if f else 0)
