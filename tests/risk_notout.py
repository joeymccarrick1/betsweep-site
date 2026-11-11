#!/usr/bin/env python3
"""tests/risk_notout.py - the live risk chip and ESPN's stale tags (owner 11/10: "Cam Skattebo says ruled out on betsweep but that's
not true ... he was out last week but will be back").

risk.js reads Supabase risk_feed (ESPN's injury statuses, refreshed every 10 minutes) and feeds notout.json (.github/feeds.py). This
drives a built page with both answers faked and checks the chip and the add-leg block for each case.

  BASE=http://localhost:8802 python3 tests/risk_notout.py [Player Name]
"""
import json, os, sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:8802"); WHO = sys.argv[1] if len(sys.argv) > 1 else "Cam Skattebo"
fails = []
def ok(c, name, extra=""):
    print(("ok  " if c else "FAIL"), name, extra); 
    if not c: fails.append(name)

def feed(status="OUT", detail="Hamstring", kind="injury"):
    return [{"id": ("note|" if kind == "note" else "inj|") + WHO.lower(), "kind": kind, "week": 10, "player": WHO, "team": "NYG", "gid": "NYG-WAS", "status": status,
             "level": "block" if status == "OUT" else "warn", "detail": detail, "players": None, "updated_at": "2026-11-11T03:40:00Z"}]
OWNER = {"players": {WHO: {"src": "owner", "why": "Good to go for Thursday. He was out last week; full participant in Tuesday's practice.", "date": "2026-11-11T03:19:00Z"}}, "mirrored": "x"}
ESPN = {"players": {WHO: {"src": "espn", "why": "Skattebo (hamstring) was listed as a full participant in Tuesday's practice", "date": "2026-11-10T21:38Z"}}, "mirrored": "x"}

def look(pw, rows, notout, path="/build/"):
    b = pw.chromium.launch(); c = b.new_context(viewport={"width": 390, "height": 844}); pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    def route(r):
        u = r.request.url
        if "risk_feed" in u: return r.fulfill(status=200, content_type="application/json", body=json.dumps(rows))
        if u.endswith("/feeds/notout.json"): return r.fulfill(status=200, content_type="application/json", body=json.dumps(notout)) if notout is not None else r.fulfill(status=404, body="")
        if u.startswith(BASE): return r.continue_()
        return r.abort()
    pg.route("**/*", route); pg.goto(BASE + path, wait_until="load"); pg.wait_for_timeout(2500)
    res = pg.evaluate("""(who) => { var v = window.BSRisk && BSRisk.verdict(who, 'Receiving Yards');
        var chips = [].slice.call(document.querySelectorAll('.bsrc')).filter(function(c){ var h = c.parentNode; return h && h.textContent.indexOf(who) >= 0; }).map(function(c){ return c.textContent.trim(); });
        var btns = [].slice.call(document.querySelectorAll('button[data-k]')).filter(function(b){ return b.getAttribute('data-k').split('|')[0] === who; });
        return {verdict: v, chips: chips.slice(0, 3), nbtn: btns.length, blocked: btns.filter(function(b){ return b.classList.contains('bsrblock'); }).length, blockAdd: !!(window.BSRisk && BSRisk.blockAdd && v && v.level === 'block')}; }""", WHO)
    res["errs"] = errs; b.close(); return res

with sync_playwright() as pw:
    r = look(pw, feed(), None)
    ok(r["verdict"] and r["verdict"]["level"] == "block" and r["verdict"]["label"] == "Ruled out", "ESPN Out, no notout file: still Ruled out", json.dumps(r["verdict"])[:120])
    ok(r["nbtn"] == 0 or r["blocked"] == r["nbtn"], "  and his leg buttons refuse", f"{r['blocked']}/{r['nbtn']}")
    r = look(pw, feed(), {"players": {}, "mirrored": "x"})
    ok(r["verdict"] and r["verdict"]["level"] == "block", "ESPN Out, notout lists nobody: Ruled out")
    r = look(pw, feed(), OWNER)
    ok(r["verdict"] and r["verdict"]["level"] == "good" and r["verdict"]["label"] == "Good to go", "ESPN Out + the owner's call: Good to go", json.dumps(r["verdict"])[:200])
    ok(r["blocked"] == 0, "  his leg buttons take the leg", f"{r['blocked']}/{r['nbtn']}")
    ok(any("Good to go" in c for c in r["chips"]) or not r["chips"], "  the chip by his name says so", str(r["chips"]))
    ok(not r["errs"], "  no script errors", str(r["errs"])[:200])
    r = look(pw, feed(), ESPN)
    ok(r["verdict"] and r["verdict"]["level"] == "warn" and r["verdict"]["label"] == "Questionable" and "full participant" in r["verdict"]["why"], "ESPN Out + ESPN's own note: Questionable, with the note", json.dumps(r["verdict"])[:220])
    ok(r["blocked"] == 0, "  not refused")
    r = look(pw, feed("DOUBTFUL"), ESPN)
    ok(r["verdict"] and r["verdict"]["label"] == "Questionable" and "Doubtful" in r["verdict"]["why"], "ESPN Doubtful + its own note: Questionable")
    r = look(pw, feed("OUT", "Inactive"), OWNER)
    ok(r["verdict"] and r["verdict"]["level"] == "block", "a game-day inactive beats the owner's earlier call", json.dumps(r["verdict"])[:120])
    r = look(pw, feed("OUT", "could barely walk", kind="note"), OWNER)
    ok(r["verdict"] and r["verdict"]["level"] == "block", "an owner Out note on the player page still blocks")
    r = look(pw, feed("QUESTIONABLE", "Hamstring"), OWNER)
    ok(r["verdict"] and r["verdict"]["level"] == "warn", "a Questionable tag is left alone", json.dumps(r["verdict"])[:100])
    for path in ("/", "/boards/", "/pairs/", "/short/"):
        r0 = look(pw, feed(), None, path); r = look(pw, feed(), OWNER, path)
        ok(r["verdict"] and r["verdict"]["label"] == "Good to go" and not r["errs"], f"{path}: Good to go, no errors", f"chips before {r0['chips']} after {r['chips']}; buttons refused before {r0['blocked']}/{r0['nbtn']} after {r['blocked']}/{r['nbtn']}")
        ok(not any("Ruled out" in c for c in r["chips"]) and r["blocked"] == 0, f"{path}: nothing on the page still says Ruled out")
        if r0["chips"] or r0["nbtn"]: ok(any("Ruled out" in c for c in r0["chips"]) or r0["blocked"] > 0, f"{path}: (without the call the page did say Ruled out)")
print("risk notout:", "all checks passed" if not fails else f"{len(fails)} FAILED: {fails}"); sys.exit(1 if fails else 0)
