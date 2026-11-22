"""A game card on the home page names its best hunch and links to it (11/21: Hunches had its own page but nothing on the day's
cards pointed at it). Only Backed / Mixed hunches and the owner's own ("From the desk") are shown; the line sits in the opened card.
  [SITE=<built site dir>] python3 tests/today_hunch.py     (serves SITE itself; BASE=<url> uses a server that is already up)
"""
import json, os, re, sys
from playwright.sync_api import sync_playwright
BASE = os.environ.get("BASE"); SITE = os.environ.get("SITE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site"))
if not BASE:   # 11/22: this needed someone else's server on :8802. In the pre-publish set that was a server left running on ANOTHER tree's
    # site, so a copy of the tree was never what got tested, and once that server stopped the test could only fail. It serves SITE itself now.
    import functools, http.server, threading
    class _Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    _srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8802), functools.partial(_Quiet, directory=SITE)); threading.Thread(target=_srv.serve_forever, daemon=True).start()
    BASE = "http://127.0.0.1:8802"
fails = []
def ok(c, name, extra=""):
    print(("ok  " if c else "FAIL"), name, extra)
    if not c: fails.append(name)
html = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
hp = open(os.path.join(SITE, "hunches", "index.html"), encoding="utf-8").read()
H = json.load(open(os.path.join(SITE, "b", "hunches.json")))
cards = H["hunches"]
links = re.findall(r'<a class="tdhunch" href="/hunches/#h-([^"]+)"><i>Hunch</i><span>(.*?)</span><b class="v(\w+)">(.*?)</b>', html)
good = {}
for c in cards:
    if c.get("kind") == "own" or c.get("verdict") in ("Backed", "Mixed"): good.setdefault(c.get("g"), []).append(c)
if not good:
    print("no Backed / Mixed hunch this build - nothing to show"); ok(not links, "no hunch line without a hunch"); sys.exit(1 if fails else 0)
ok(len(links) > 0, "cards carry a hunch line", str(len(links)))
ok(all(f'id="h-{g}"' in hp for g, _, _, _ in links), "every hunch line lands on that game on the Hunches page")
ok(all(v in ("Backed", "Mixed", "Our call") for _, _, _, v in links), "only Backed / Mixed / the desk's own are shown", str({v for _, _, _, v in links}))
import html as _h
ok(all(any(_h.unescape(t) == c["title"] for c in good.get(g, [])) for g, t, _, _ in links), "the line is a real hunch of that game")
ok(len({g for g, _, _, _ in links}) == len(links), "one line per card")
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for scheme in ("light", "dark"):
        c = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, color_scheme=scheme); pg = c.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(BASE) else r.abort())
        pg.goto(BASE + "/", wait_until="load"); pg.wait_for_timeout(1200)
        ok(not errs, f"{scheme}: no script errors", str(errs)[:200])
        r = pg.evaluate("""(function(){ var a = document.querySelector('.tdgame.show .tdhunch') || document.querySelector('.tdhunch'); if (!a) return null;
          var card = a.closest('.tdgame'); if (card) { card.classList.add('show'); card.classList.add('open'); card.classList.remove('tdx'); }
          var p = a.parentElement; while (p) { if (p.hidden) p.hidden = false; p = p.parentElement; }
          if (a.offsetParent === null) return {vis: 0, cls: card ? card.className : ''};
          a.scrollIntoView({block: 'center'});
          var q = a.getBoundingClientRect(), sp = getComputedStyle(a.querySelector('span'));
          return {vis: 1, w: q.width, right: q.right, h: q.height, fg: sp.color, bg: getComputedStyle(document.body).backgroundColor, over: document.documentElement.scrollWidth > 392}; })()""")
        ok(r is not None, f"{scheme}: the line is on the page")
        ok(bool(r and r.get("vis")), f"{scheme}: opening the card shows it", str(r))
        if r and r.get("vis"):
            ok(r["right"] <= 390 and not r["over"], f"{scheme}: fits a phone, no sideways scroll", str(r))
            ok(r["h"] < 110, f"{scheme}: stays a short line", str(r["h"]))
            ok(r["fg"] != r["bg"], f"{scheme}: text is readable against the page", f'{r["fg"]} on {r["bg"]}')
        pg.wait_for_timeout(300); pg.screenshot(path=f"/tmp/today_hunch_{scheme}.png")
        c.close()
    b.close()
print("FAILS:", fails) if fails else print("all good")
sys.exit(1 if fails else 0)
