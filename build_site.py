#!/usr/bin/env python3
"""BetSweep static site assembler — v2026-10-14.
Takes the built pages in ./out (after render_images.py) and lays out a deployable static site in ./site:
  site/index.html + site/img/                 this week's boards
  site/season/index.html + site/season/img/   season receipt
  site/receipts/week<W>/index.html + img/     weekly receipts (every out/results-week*.html present)
  site/receipts/index.html                    list of receipts (from in/archive.json + what is on disk)
  site/CNAME, favicon.png, og.png, 404.html
Cross-links to the claude.ai artifacts are rewritten to site paths; each page gets a full HTML document wrapper
with social-preview tags (the artifact viewer adds that wrapper itself; a plain host does not).
usage: python3 build_site.py [domain=betsweep.co]
"""
import os, re, json, glob, shutil, base64, html, datetime as _dt
import account as ACCT
BIGGER_CSS = """
/* bigger text, less gutter (users: "text is a little small") - phones use the full width, everything scales up ~10% */
@media (max-width:760px){
 body{margin:0 !important;padding-left:5px !important;padding-right:5px !important}
 body > :not(.sitenav):not(.apptabs):not(script):not(style):not(.bsdlg):not(.hero):not(.installbar){zoom:1.1}
}
/* owner 10/23 (betslip "stuck" mid-screen with the tab bar): iOS Safari zooms the page in when a form field under 16px gets focus (the
   builder search box, the filter dropdowns, the slip-name box were 13px) and stays zoomed, so the fixed tab bar and slip sit mid-screen.
   16px fields on touch screens stop the zoom. */
@media (pointer:coarse){ input:not([type=checkbox]):not([type=radio]):not([type=range]),select,textarea{font-size:16px !important} }
@media (min-width:761px){
 body > :not(.sitenav):not(.apptabs):not(script):not(style):not(.bsdlg):not(.hero):not(.installbar){zoom:1.06}
}
@media (max-width:760px){.hero{min-height:0 !important;aspect-ratio:1600/640 !important;background-size:100% auto !important;background-position:center 50% !important}}

"""
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "out"); SITE = os.path.join(HERE, "site"); IN = os.path.join(HERE, "in")
import sys
DOMAIN = sys.argv[1] if len(sys.argv) > 1 else "betsweep.co"; BASE = f"https://{DOMAIN}"
POSTS_DIR = sys.argv[2] if len(sys.argv) > 2 else None   # folder of images the owner uploaded (repo /posts); newest first by name
ART = {"RTTqiN3sdMHGgojimQ9hZv": "/boards/", "A7tt7rCuMgVvwSqBm9A7Pv": "/season/", "J4Lagt8tbuaLYnDfZfaVZt": "/receipts/week5/", "FQVqm3BhG4BfMPd63tRQRa": "/build/", "EbpLXvGQWy6MoybbFsjxNY": "/team/", "EKtgfWz91Q8ckuPuxfmak4": "/firsttd/", "W4L5R482imAeJhDxUHDMPF": "/dfs/"}
try:   # archive tab maps week -> receipt artifact url; rewrite those to /receipts/week<W>/
    for r in json.load(open(os.path.join(IN, "archive.json")))["values"][1:]:
        if len(r) >= 3 and "claude.ai/artifact/" in str(r[2]) and str(r[0]).strip():
            ART[r[2].rstrip("/").split("/")[-1]] = f"/receipts/week{int(float(r[0]))}/"
except Exception: pass

if os.path.isdir(SITE): shutil.rmtree(SITE)
os.makedirs(SITE)
exec(open(os.path.join(HERE, "brand.py")).read())   # LOGO (b64 png)
open(os.path.join(SITE, "favicon.png"), "wb").write(base64.b64decode(LOGO))
open(os.path.join(SITE, "wordmark.png"), "wb").write(base64.b64decode(WORDMARK))
open(os.path.join(SITE, "wordmark-ink.png"), "wb").write(base64.b64decode(WORDMARK_INK))
open(os.path.join(SITE, "CNAME"), "w").write(DOMAIN + "\n")
# link-preview card (texts, X, iMessage): cream header look, wordmark + swoosh, tagline, red rule
def make_og(path):
    import io
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630; im = Image.new("RGB", (W, H), "#efe9da"); d = ImageDraw.Draw(im)
    wm = Image.open(io.BytesIO(base64.b64decode(WORDMARK_INK))).convert("RGBA")
    a = wm.getchannel("A"); a.paste(0, (0, 0, int(wm.width * 0.08), int(wm.height * 0.5))); wm.putalpha(a)   # stray specks left of the B
    tw = 940; wm = wm.resize((tw, round(wm.height * tw / wm.width)), Image.LANCZOS)
    y = (H - wm.height) // 2 - 40; im.paste(wm, ((W - tw) // 2, y), wm)
    try: f = ImageFont.truetype("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", 34)
    except Exception: f = ImageFont.load_default()
    tag = "P I C K S .   D A T A .   E D G E .   S W E E P ."
    tw2 = d.textlength(tag, font=f); d.text(((W - tw2) / 2, y + wm.height + 46), tag, fill="#4a5260", font=f)
    d.rectangle([0, H - 18, W, H], fill="#d7332a")
    im.save(path, optimize=True)
make_og(os.path.join(SITE, "og.png"))

# ---- installable app (PWA): icons, manifest, service worker, iOS meta ----
def make_icons():
    import io
    from PIL import Image
    logo = Image.open(io.BytesIO(base64.b64decode(LOGO))).convert("RGBA")
    os.makedirs(os.path.join(SITE, "app"), exist_ok=True)
    for size in (192, 512):
        im = Image.new("RGBA", (size, size), "#141a24"); lg = logo.resize((int(size * 0.82), int(size * 0.82)), Image.LANCZOS)
        im.alpha_composite(lg, ((size - lg.width) // 2, (size - lg.height) // 2)); im.convert("RGB").save(os.path.join(SITE, "app", f"icon-{size}.png"))
        # maskable: safe zone is the inner 80%, so the mark sits smaller on a full-bleed background
        mk = Image.new("RGBA", (size, size), "#141a24"); lg2 = logo.resize((int(size * 0.6), int(size * 0.6)), Image.LANCZOS)
        mk.alpha_composite(lg2, ((size - lg2.width) // 2, (size - lg2.height) // 2)); mk.convert("RGB").save(os.path.join(SITE, "app", f"maskable-{size}.png"))
    ap = Image.new("RGBA", (180, 180), "#141a24"); lg3 = logo.resize((148, 148), Image.LANCZOS); ap.alpha_composite(lg3, (16, 16)); ap.convert("RGB").save(os.path.join(SITE, "apple-touch-icon.png"))
make_icons()
MANIFEST = {"name": "BetSweep", "short_name": "BetSweep", "description": "NFL projections priced against FanDuel: matchup boards, parlay builder, live tracker, receipts.",
            "start_url": "/?source=app", "scope": "/", "display": "standalone", "orientation": "portrait", "background_color": "#141a24", "theme_color": "#d7332a", "lang": "en-US",
            "icons": [{"src": "/app/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/app/icon-512.png", "sizes": "512x512", "type": "image/png"},
                      {"src": "/app/maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"}, {"src": "/app/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
            "shortcuts": [{"name": "Today", "url": "/", "icons": [{"src": "/app/icon-192.png", "sizes": "192x192"}]}, {"name": "Live", "url": "/live/"}, {"name": "Parlay Builder", "url": "/build/"}, {"name": "Matchup Boards", "url": "/boards/"}],
            "categories": ["sports"]}
open(os.path.join(SITE, "manifest.webmanifest"), "w").write(json.dumps(MANIFEST, indent=1))
SW_VERSION = _dt.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%Y%m%d%H%M") if "_dt" in globals() else __import__("datetime").datetime.now().strftime("%Y%m%d%H%M")
SW = r'''// BetSweep service worker: app shell cached for instant open; pages are network-first so the data is always this build's,
// with the last good copy served when the connection drops (stadium wifi). Version: __V__
var V = 'bs-__V__', SHELL = ['/', '/boards/', '/build/', '/live/', '/social/', '/team/', '/firsttd/', '/teasers/', '/beat/', '/teams/', '/dossier/', '/dfs/', '/receipts/', '/season/', '/player/', '/usage/', '/benefits/', '/guide/', '/offline.html', '/wordmark.png', '/wordmark-ink.png', '/favicon.png', '/logo.png', '/banner.jpg', '/app/icon-192.png'];
self.addEventListener('install', function(e){ e.waitUntil(caches.open(V).then(function(c){ return Promise.all(SHELL.map(function(u){ return c.add(u).catch(function(){}); })); }).then(function(){ return self.skipWaiting(); })); });
self.addEventListener('activate', function(e){ e.waitUntil(caches.keys().then(function(ks){ return Promise.all(ks.filter(function(k){ return k !== V; }).map(function(k){ return caches.delete(k); })); }).then(function(){ return self.clients.claim(); })); });
self.addEventListener('fetch', function(e){
  var req = e.request; if(req.method !== 'GET') return;
  var url = new URL(req.url);
  if(url.origin !== location.origin) return;   // ESPN, fonts, FanDuel links: straight to the network
  if(url.pathname.indexOf('/data/') === 0 || req.cache === 'no-store' || req.cache === 'reload'){   // 11/5: hourly files (risk notes, price moves) must not be pinned for a whole build
    e.respondWith(fetch(req).then(function(r){ var copy = r.clone(); caches.open(V).then(function(c){ c.put(req, copy); }); return r; }).catch(function(){ return caches.match(req); })); return; }
  if(req.mode === 'navigate' || url.pathname.endsWith('.html') || url.pathname.endsWith('/')){
    e.respondWith(fetch(req).then(function(r){ var copy = r.clone(); caches.open(V).then(function(c){ c.put(req, copy); }); return r; })
      .catch(function(){ return caches.match(req).then(function(r){ return r || caches.match('/offline.html'); }); }));
    return;
  }
  e.respondWith(caches.match(req).then(function(r){ return r || fetch(req).then(function(res){ var copy = res.clone(); caches.open(V).then(function(c){ c.put(req, copy); }); return res; }); }));
});
// slip alerts (owner 10/30): the Supabase function "slip-alerts" pushes {title, body, url, tag}; tapping opens the page
self.addEventListener('push', function(e){
  var d = {}; try { d = e.data ? e.data.json() : {}; } catch(x){ d = {title: 'BetSweep', body: e.data ? e.data.text() : ''}; }
  e.waitUntil(self.registration.showNotification(d.title || 'BetSweep', {body: d.body || '', icon: '/app/icon-192.png', badge: '/app/icon-192.png', tag: d.tag || 'bs', data: {url: d.url || '/me/'}}));
});
self.addEventListener('notificationclick', function(e){
  e.notification.close(); var u = (e.notification.data || {}).url || '/me/';
  e.waitUntil(self.clients.matchAll({type: 'window', includeUncontrolled: true}).then(function(cs){
    for (var i = 0; i < cs.length; i++){ if ('focus' in cs[i]) { cs[i].navigate(u); return cs[i].focus(); } }
    return self.clients.openWindow(u); }));
});
'''.replace("__V__", SW_VERSION)
open(os.path.join(SITE, "sw.js"), "w").write(SW)
open(os.path.join(SITE, "account.js"), "w").write(ACCT.ACCOUNT_JS)
open(os.path.join(SITE, "import.js"), "w").write(__import__("slipimport").IMPORT_JS)   # owner 11/1: FanDuel screenshot import on /me/ (slipimport.py)
open(os.path.join(SITE, "risk.js"), "w").write(__import__("risk").js())   # owner 11/1: live injury / weather / owner-note layer (risk.py)
open(os.path.join(SITE, "offline.html"), "w").write('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BetSweep · offline</title><style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#141a24;color:#f1e8d8;font-family:"IBM Plex Sans",system-ui,sans-serif;text-align:center;padding:24px}img{width:260px;max-width:80vw}p{color:#a9a294;line-height:1.5}a{color:#f1e8d8}</style></head><body><div><img src="/wordmark.png" alt="BetSweep"><p>You are offline and this page was not saved yet.<br>The pages you opened before are still available from the menu.</p><p><a href="/">Try again</a></p></div></body></html>')

open(os.path.join(SITE, ".nojekyll"), "w").write("")

NAV_ITEMS = [("/", "Home"), ("/boards/", "Matchup Boards"), ("/build/", "Parlay Builder"), ("/player/", "Players"), ("/live/", "Live"), ("/social/", "Social"), ("/team/", "Fantasy"), ("/usage/", "Usage"), ("/trade/", "Trade"), ("/firsttd/", "First TD"), ("/dfs/", "DFS"), ("/receipts/", "Receipts"), ("/season/", "Season")]
# owner 10/30: "start grouping pages in the menu ... Fantasy and then it drops down to teams, trade, and dfs. Group like pages"
NAV_GROUPS = [("/", "Home", None), ("/simple/", "Simple view", None),   # owner 11/10: the short version for casual visitors (build_simple.py)
              (None, "Betting", [("/boards/", "Matchup Boards", "One board per game"), ("/dossier/", "Game previews", "The read before the bet"), ("/build/?ask=", "Ask BetSweep", "Any player, stat or line"), ("/build/", "Parlay Builder", "Every prop, priced"), ("/sweep/", "Sweep my slip", "A verdict from a screenshot"), ("/firsttd/", "First TD", "Who scores first"), ("/pairs/", "Either-or TDs", "Two names, one leg"), ("/teasers/", "Teaser finder", "6, 6.5 and 7 points, priced"), ("/beat/", "Beat the model", "Your five vs its five"), ("/survivor/", "Survivor planner", "Your pick, and who to save"), ("/live/", "Live", "Your legs vs the box score")]),
              (None, "Players", [("/player/", "All players", "Lines, hit rates, game logs"), ("/teams/", "Teams", "Stats, results, box scores"), ("/usage/", "Usage trends", "Rising and falling roles"), ("/benefits/", "Who benefits", "When a starter is out")]),
              (None, "Fantasy", [("/team/", "My team", "Start / sit, Sleeper import"), ("/team/compare/", "Who should I start?", "Compare players for your flex"), ("/trade/", "Trade calculator", "Rest-of-season values"), ("/dfs/", "DFS", "Lineup builder")]),
              ("/social/", "Social", None),
              (None, "Results", [("/receipts/", "Receipts", "Every week, graded"), ("/season/", "Season", "The running record"), ("/badbeats/", "Missed by one", "The week's bad beats"), ("/guide/", "How to read BetSweep", "Colors, ranks, edge"), ("/how/", "How BetSweep picks", "The method and the record"), ("/api/", "API", "Every JSON the site serves")])]
NAV_CSS = """<style>""" + ACCT.ACCOUNT_CSS + BIGGER_CSS + """
.sitenav{position:sticky;top:0;z-index:60;margin-left:calc(-1 * var(--bs-inset,0px));margin-right:calc(-1 * var(--bs-inset,0px));margin-top:calc(-1 * var(--bs-top,0px));padding-top:env(safe-area-inset-top,0px);background:#efe9da;border-bottom:3px solid #d7332a;font-family:'Barlow Condensed','IBM Plex Sans',system-ui,sans-serif;box-shadow:0 2px 14px rgba(0,0,0,.25)}
.sitenav .in{max-width:1360px;margin:0 auto;padding:0 16px;display:flex;align-items:center;gap:14px;min-height:50px}
.sitenav .brand{display:inline-flex;align-items:center;text-decoration:none;padding:7px 0}
.sitenav .brand img{height:32px;width:auto;display:block}
.sitenav .brand img.cream{display:none}
.sitenav .srch{margin-left:auto;display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;border:1.5px solid #141a24;border-radius:8px;background:none;color:#141a24;cursor:pointer;flex:none} .sitenav .srch:hover{background:#141a24;color:#efe9da} .sitenav .srch + .menu{margin-left:8px}
.bssrch{position:fixed;inset:0;z-index:200;background:rgba(15,20,28,.72);display:none;align-items:flex-start;justify-content:center;padding:max(10px,env(safe-area-inset-top)) 10px 10px} .bssrch.open{display:flex}
.bssrch .box{width:100%;max-width:560px;background:#efe9da;color:#141a24;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.45);overflow:hidden;font-family:'IBM Plex Sans',system-ui,sans-serif}
.bssrch .row{display:flex;align-items:center;gap:8px;padding:10px 10px 8px;border-bottom:1px solid #d9d2c0} .bssrch input{flex:1;font:inherit;font-size:17px;padding:10px 12px;border:1.5px solid #141a24;border-radius:8px;background:#fff;color:#141a24;min-width:0} .bssrch input:focus{outline:none;border-color:#d7332a;box-shadow:0 0 0 3px rgba(215,51,42,.22)} .bssrch .x{font:inherit;font-size:20px;background:none;border:0;color:#5b6473;padding:6px 10px;cursor:pointer}
.bssrch ul{list-style:none;margin:0;padding:4px 0;max-height:min(60vh,520px);overflow:auto} .bssrch li{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 10px;align-items:center;padding:0}
.bssrch li a.pl{display:block;padding:10px 14px;text-decoration:none;color:#141a24;font-weight:600;font-size:15px;line-height:1.2} .bssrch li a.pl small{display:block;color:#5b6473;font-weight:500;font-size:12px;margin-top:2px}
.bssrch li .go{display:flex;gap:6px;padding-right:10px} .bssrch li .go a{text-decoration:none;font-family:'Barlow Condensed','IBM Plex Sans',sans-serif;font-weight:700;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;border:1px solid #c9c1ad;border-radius:6px;padding:6px 8px;color:#141a24;white-space:nowrap}
.bssrch li.on a.pl,.bssrch li a.pl:hover{background:#e6dfcc} .bssrch .hint{padding:8px 14px 12px;color:#5b6473;font-size:12.5px}
@media (max-width:760px){
  .top .mast{padding-block:8px 4px;gap:8px} .top .mast img{display:none} .top .mast h1{font-size:22px;gap:2px} .top .mast h1 small{font-size:10.5px;letter-spacing:.14em} .top .mast p{display:none} .top .nav{padding-block:0 8px;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch} .top .nav::-webkit-scrollbar{display:none}
  .top .nav a{white-space:nowrap;flex:none}
  body.bs-scrolled .top .mast{display:none} body.bs-scrolled .top{margin-bottom:10px}
}
@media (min-width:761px){
  /* desktop: the sticky page header is up to 197px tall (logo, title, paragraph, slate chips); scrolling down keeps title + chips only */
  body.bs-scrolled .top .mast p,body.bs-scrolled .top .mast img{display:none} body.bs-scrolled .top .mast{padding-block:6px 0} body.bs-scrolled .top .mast h1{font-size:22px} body.bs-scrolled .top .mast h1 small{display:none}
}
/* deep links (#g-X / #lv-X / #box-X / a boards card) land below the sticky chrome instead of under it */
.gcard,.lg2,.tdgame,[id^="box-"],.player .sec,.pcard{scroll-margin-top:140px}
@media (min-width:761px){ .gcard,.lg2,.tdgame,[id^="box-"]{scroll-margin-top:230px} }
.sitenav .tabs{display:flex;gap:4px;margin-left:auto;align-items:center;padding:0;border:0;background:none}
.sitenav .tabs a{color:#4a5260;text-decoration:none;font-weight:700;font-size:15px;letter-spacing:.05em;text-transform:uppercase;padding:14px 10px 11px;border-bottom:3px solid transparent;margin-bottom:-3px}
.sitenav .tabs a:hover{color:#141a24}
.sitenav .tabs a.on{color:#141a24;border-bottom-color:#d7332a}
@media (max-width:1180px){ .sitenav .tabs{gap:0} .sitenav .tabs a{font-size:13.5px;padding:14px 7px 11px;letter-spacing:.04em} }
/* 10/30: Players + Usage made 13 tabs - tighter between 1100 and 1420, the menu button below 1100 */
.sitenav .dd{position:relative;display:flex;align-items:stretch}
.sitenav .ddb{font:inherit;color:#4a5260;font-weight:700;font-size:15px;letter-spacing:.05em;text-transform:uppercase;background:none;border:0;border-bottom:3px solid transparent;margin-bottom:-3px;padding:14px 10px 11px;cursor:pointer;display:inline-flex;align-items:center;gap:5px}
.sitenav .ddb i{font-style:normal;font-size:10px;transition:transform .15s}
.sitenav .dd.open .ddb{color:#141a24} .sitenav .dd.on .ddb{color:#141a24;border-bottom-color:#d7332a}
@media (hover:hover){ .sitenav .dd:hover .ddb{color:#141a24} .sitenav .dd:hover .ddm{display:flex} .sitenav .dd:hover .ddb i{transform:rotate(180deg)} }
.sitenav .dd:last-child .ddm{left:auto;right:0}
.sitenav .ddm{display:none;position:absolute;top:100%;left:0;z-index:80;min-width:230px;flex-direction:column;background:#efe9da;border:1px solid #d9d1bf;border-top:3px solid #d7332a;border-radius:0 0 8px 8px;box-shadow:0 14px 30px rgba(0,0,0,.28);padding:6px 0}
.sitenav .dd.open .ddm{display:flex}
.sitenav .dd.open .ddb i{transform:rotate(180deg)}
.sitenav .ddm a{display:block;padding:9px 16px !important;border:0 !important;margin:0 !important;text-transform:none !important;letter-spacing:.01em !important;font-size:16px !important;color:#141a24 !important}
.sitenav .ddm a small{display:block;font-family:'IBM Plex Sans',system-ui,sans-serif;font-weight:500;font-size:12px;color:#5d6676;letter-spacing:0;margin-top:1px}
.sitenav .ddm a:hover,.sitenav .ddm a.on{background:#e4ddcb} .sitenav .ddm a.on{box-shadow:inset 3px 0 0 #d7332a}
.sitenav .ddh{display:none}
.sitenav .thm{display:flex;align-items:center;gap:6px;padding:8px 10px;border-left:1px solid #d9d1bf;margin-left:6px} .sitenav .thm span{font-weight:700;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#4a5260;margin-right:2px}
.sitenav .thm button{font:inherit;font-weight:700;font-size:12.5px;letter-spacing:.04em;text-transform:uppercase;color:#4a5260;background:none;border:1.5px solid #d9d1bf;border-radius:999px;padding:4px 10px;cursor:pointer;min-height:30px} .sitenav .thm button.on{color:#efe9da;background:#141a24;border-color:#141a24}
@media (max-width:1240px){ .sitenav .thm{border-left:0;margin:0;padding:12px 18px;border-bottom:1px solid #d9d1bf} .sitenav .thm span{font-size:14px;margin-right:auto} .sitenav .thm button{min-height:36px;padding:6px 14px;font-size:14px} }
@media (max-width:1240px){
  .sitenav .dd{display:block;border-bottom:1px solid #d9d1bf}
  .sitenav .ddb{display:flex;width:100%;justify-content:space-between;align-items:center;text-align:left;padding:13px 18px;font-size:17px;border:0;margin:0;color:#4a5260}
  .sitenav .dd.on .ddb{color:#141a24;box-shadow:inset 4px 0 0 #d7332a} .sitenav .ddb i{font-size:12px}
  .sitenav .ddm{display:none;position:static;box-shadow:none;border:0;border-radius:0;padding:0 0 6px;min-width:0;background:#e9e2d0}
  .sitenav .dd.open .ddm{display:flex}
  .sitenav .ddm a{padding:10px 18px 10px 30px !important;border-bottom:1px solid #ddd5c2 !important;font-size:16px !important}
  .sitenav .ddm a:last-child{border-bottom:0 !important}
  /* no overflow-x:clip on .sitenav: iOS Safari clipped the dropdown to the header box (owner 11/5, blank menu) */ .sitenav.open .tabs{z-index:75} .sitenav .tabs{max-height:calc(100vh - 70px);overflow-y:auto;-webkit-overflow-scrolling:touch;overscroll-behavior:contain}
}
.sitenav .menu{display:none;margin-left:auto;font:inherit;font-weight:700;font-size:14px;letter-spacing:.06em;text-transform:uppercase;color:#141a24;background:none;border:1.5px solid #141a24;border-radius:4px;padding:6px 10px;cursor:pointer}
@media (max-width:1240px){
  .sitenav .menu{display:inline-flex;align-items:center;gap:6px}
  .sitenav .tabs{display:none;position:absolute;left:0;right:0;top:100%;flex-direction:column;align-items:stretch;gap:0;padding:0;background:#efe9da;border-bottom:3px solid #d7332a;box-shadow:0 12px 30px rgba(0,0,0,.35)}
  .sitenav.open .tabs{display:flex}
  .sitenav .tabs a{display:block;text-align:left;padding:13px 18px;border-bottom:1px solid #d9d1bf;font-size:17px;margin-bottom:0}
  .sitenav .tabs a.on{border-left:4px solid #d7332a;border-bottom-color:#d9d1bf}
  .top{top:calc(50px + env(safe-area-inset-top,0px))}
}
/* 11/4: phones zoom page content 1.1x (BIGGER_CSS), so a 50px sticky offset lands at 55px and a 2px strip of page showed between the
   site nav (53px) and the page header; the offset is set in pre-zoom units */
@media (max-width:760px){ .top{top:calc((53px + env(safe-area-inset-top,0px)) / 1.1)} }
@media (display-mode: standalone){ .sitenav .in{min-height:54px} }
/* app tab bar: the installed app and phones get bottom tabs like a native app; the top menu stays for everything else */
.apptabs{display:none;position:fixed;left:0;right:0;bottom:0;z-index:70;background:#141a24;border-top:1px solid #2a3240;padding:6px 4px calc(6px + env(safe-area-inset-bottom));box-shadow:0 -6px 20px rgba(0,0,0,.35)}
.apptabs a{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;color:#a9a294;text-decoration:none;font-family:'Barlow Condensed','IBM Plex Sans',system-ui,sans-serif;font-weight:700;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;padding:4px 0}
.apptabs a svg{width:22px;height:22px;stroke:currentColor;fill:none;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
.apptabs a.on{color:#fff} .apptabs a.on svg{stroke:#d7332a}
@media (max-width:760px){ .apptabs{display:flex} body{padding-bottom:calc(64px + env(safe-area-inset-bottom))} :root{--bs-tabs:calc(64px + env(safe-area-inset-bottom))} .slipwrap,.bslip{bottom:var(--bs-tabs)} .dfs .mbar{bottom:calc(var(--bs-tabs) + 12px)} }
@media (display-mode: standalone){ .apptabs{display:flex} body{padding-bottom:calc(64px + env(safe-area-inset-bottom))} .sitenav .menu{display:inline-flex} :root{--bs-tabs:calc(64px + env(safe-area-inset-bottom))} .slipwrap,.bslip{bottom:var(--bs-tabs)} .dfs .mbar{bottom:calc(var(--bs-tabs) + 12px)} }
.installbar{display:none;align-items:center;gap:10px;max-width:1360px;margin:10px auto 0;padding:10px 14px;background:#141a24;color:#f1e8d8;border-radius:8px;font-family:'IBM Plex Sans',system-ui,sans-serif;font-size:13px}
.installbar.show{display:flex} .installbar b{font-family:'Barlow Condensed',sans-serif;font-size:15px;letter-spacing:.04em;text-transform:uppercase}
.installbar button{margin-left:auto;font:inherit;font-weight:700;color:#141a24;background:#f1e8d8;border:0;border-radius:4px;padding:6px 12px;cursor:pointer} .installbar .x{margin-left:0;background:none;color:#a9a294;font-size:18px;padding:0 6px}
/* 11/5 (owner: "header you can't see log out and zooms are weird"): signed in, the header row (wordmark + search + Menu + My BetSweep + Out) was 478px of
   non-shrinking content on a 390px phone, so iOS laid the page out at 478px and zoomed out - every page looked small and Out was off-screen.
   The row may never exceed the viewport: the wordmark shrinks, the account button is the avatar alone, nothing wraps or overflows. */
/* 11/5 evening (owner: "I liked it better when it said My BetSweep in the header"): the pill keeps its words; to fit 390px the Menu button is the
   icon alone and Out moves into the menu panel (account.py adds "Sign out" there). */
@media (max-width:560px){ .sitenav .in{flex-wrap:nowrap;min-width:0;gap:8px;padding:0 10px} .sitenav .brand{min-width:0;flex:0 1 auto} .sitenav .brand img{height:26px;max-width:100%;object-fit:contain}
  .sitenav .srch{width:36px;height:36px;flex:none} .sitenav .menu{flex:none;width:40px;height:36px;padding:0;justify-content:center;font-size:0;gap:0} .sitenav .menu svg,.sitenav .menu i,.sitenav .menu span{font-size:18px}
  .sitenav .acct{flex:none;gap:4px;margin-right:0} .sitenav .acct a.me{font-size:11.5px;padding:4px 9px 4px 4px;white-space:nowrap} .sitenav .acct a.me i{width:20px;height:20px;line-height:20px;margin-right:5px}
  .sitenav .acct button.out{display:none} }
/* the open menu scrolls inside the screen (it used to run under the bottom tabs with no way to reach the last items) */
@media (max-width:1240px){ .sitenav .tabs{max-height:calc(100vh - 56px - env(safe-area-inset-top,0px) - var(--bs-tabs,0px));max-height:calc(100dvh - 56px - env(safe-area-inset-top,0px) - var(--bs-tabs,0px));overflow-y:auto;overscroll-behavior:contain}
  .sitenav .tabs .mout{color:#b8261d} }
</style>
"""

BRAND_CSS = """<style>
/* ===== BetSweep brand layer (11/5) - one control system and one heading system for every page; loads after the page's own CSS ===== */
:root{--brush:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 8'%3E%3Cpath d='M1.5 5.2C10 2.6 18 2.2 27 3.4c7 1 14 2.6 21 1.6 4-.6 7-1.9 10-2.9' fill='none' stroke='%23d7332a' stroke-width='3.4' stroke-linecap='round'/%3E%3Cpath d='M3 6.4c9-1.3 17-2 26-1 7 .8 13 2 19 1.1' fill='none' stroke='%23d7332a' stroke-width='1.5' stroke-linecap='round' opacity='.8'/%3E%3C/svg%3E");--ctl:'Barlow Condensed','IBM Plex Sans',system-ui,sans-serif}
/* the brushed red stroke under a section title (the board's "PICKS. DATA." dash) */
.brush{position:relative;padding-bottom:12px} .brush::after{content:"";position:absolute;left:0;bottom:0;width:54px;height:8px;background:var(--brush) no-repeat left center/100% 100%}
/* segmented controls: builder view tabs, live Picks / Every leg, players position filter, usage/benefits chips */
.tabs .tab,.seg button,.pos button,.usg .tabs button,.bnf .tabs button{font:inherit;font-family:var(--ctl);font-weight:700;font-size:13.5px;letter-spacing:.06em;text-transform:uppercase;display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:36px;padding:0 14px;border-radius:8px;border:1.5px solid var(--line);background:transparent;color:var(--ink);cursor:pointer;line-height:1}
body .tabs .tab.on,body .seg button.on,body .pos button.on,body .usg .tabs button.on,body .bnf .tabs button.on{background:var(--ink);border-color:var(--ink);color:var(--bg)}
.seg{display:inline-flex;gap:6px;background:none;border:0;padding:0}
/* primary action = red; secondary = outline; both in the control face */
.dfs .btn:not(.sec),.tc .lg .go,.tdlive,a.pri.solid,.bsbtn{font:inherit;font-family:var(--ctl);font-weight:700;font-size:14px;letter-spacing:.05em;text-transform:uppercase;display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:0 16px;border-radius:8px;border:1.5px solid var(--red);background:var(--red);color:#fff;cursor:pointer;text-decoration:none}
.dfs .btn.sec,.rfr,.tdshare,.altbtn,.bsbtn.sec{font:inherit;font-family:var(--ctl);font-weight:700;font-size:13.5px;letter-spacing:.05em;text-transform:uppercase;display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:36px;padding:0 14px;border-radius:8px;border:1.5px solid var(--line);background:transparent;color:var(--ink);cursor:pointer;text-decoration:none}
.rfr:hover,.tdshare:hover,.altbtn:hover,.dfs .btn.sec:hover{border-color:var(--red)}
/* inputs */
.lvbar input,.pd input,.tc input[type=text],.slform input,.bslip .namebox input{font:inherit;font-size:16px;min-height:42px;padding:8px 12px;border:1.5px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
.lvbar input:focus,.pd input:focus,.tc input[type=text]:focus,.slform input:focus{outline:none;border-color:var(--red);box-shadow:0 0 0 3px color-mix(in srgb,var(--red) 22%,transparent)}
/* status pills stay pills; everything else squares off at 8px */
.tdlinks a,.fdgo,.bslip .acts button,.bslip .acts a,.acts button,.acts a.fd,.lg a.fd{border-radius:8px}
/* page titles and section titles on the pages that carry their own CSS (usage, who-benefits, social, how-to guide, receipts) */
.uw h1,.soc h1,.sp h1,.gd h1{font-family:var(--brand);font-style:italic;font-weight:800;font-size:32px;letter-spacing:-.01em;line-height:1}
.uw h2,.gd h2{letter-spacing:.01em;text-transform:none;font-size:19px} .gd h2{font-size:22px;margin:0 0 10px;padding-bottom:12px;position:relative} .gd h2::after{content:"";position:absolute;left:0;bottom:0;width:54px;height:8px;background:var(--brush) no-repeat left center/100% 100%}
/* focus is visible everywhere, in the brand red */
a:focus-visible,button:focus-visible,summary:focus-visible{outline:2px solid var(--red);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms !important;transition-duration:.01ms !important}}
</style>
"""

# ---- 11/5 efficiency pass: one copy of the shared CSS / JS per build instead of 27 KB inlined on every page (and 65 KB of
# template CSS on every template page); self-hosted fonts (no Google Fonts round trip, no third-party request); html2canvas
# self-hosted and loaded on first use instead of 195 KB on every page load. Files land in /s/ with a content hash in the name,
# so the service worker's cache can never serve a stale one. assets/ ships with the generators (gen-overrides).
import hashlib as _hl
_ASSETS = os.path.join(HERE, "assets")
_LATIN = "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"
_FONTS = [("Barlow", "italic", 800, "barlow-latin-800-italic.woff2"), ("Barlow Condensed", "normal", 500, "barlow-condensed-latin-500-normal.woff2"),
          ("Barlow Condensed", "normal", 600, "barlow-condensed-latin-600-normal.woff2"), ("Barlow Condensed", "normal", 700, "barlow-condensed-latin-700-normal.woff2"),
          ("IBM Plex Sans", "normal", 400, "ibm-plex-sans-latin-400-normal.woff2"), ("IBM Plex Sans", "normal", 500, "ibm-plex-sans-latin-500-normal.woff2"),
          ("IBM Plex Sans", "normal", 600, "ibm-plex-sans-latin-600-normal.woff2")]
FONT_CSS = "".join(f"@font-face{{font-family:'{fam}';font-style:{sty};font-weight:{w};font-display:swap;src:url(/s/fonts/{f}) format('woff2');unicode-range:{_LATIN}}}\n" for fam, sty, w, f in _FONTS) if os.path.isdir(os.path.join(_ASSETS, "fonts")) else ""
def _inner(block, tag):
    i = block.index("<" + tag + ">") + len(tag) + 2; j = block.rindex("</" + tag + ">"); return block[i:j]
def _h(txt): return _hl.md5(txt.encode("utf-8") if isinstance(txt, str) else txt).hexdigest()[:10]
_TPL_CSS = ""
try:
    _t = open(os.path.join(HERE, "template.html"), encoding="utf-8").read(); _TPL_CSS = _t[_t.index("<style>") + 7: _t.index("</style>")]
    if "/*LIVECSS*/" in _TPL_CSS: _TPL_CSS = _TPL_CSS[:_TPL_CSS.index("/*LIVECSS*/")]   # build_boards fills the placeholders after this point; the prefix is identical on every template page
except Exception: _TPL_CSS = ""
SHARED = {}   # name -> (served path, content)
def _write_shared():
    os.makedirs(os.path.join(SITE, "s", "fonts"), exist_ok=True)
    for fam, sty, w, f in _FONTS:
        src = os.path.join(_ASSETS, "fonts", f)
        if os.path.exists(src): shutil.copy(src, os.path.join(SITE, "s", "fonts", f))
    h2c = os.path.join(_ASSETS, "html2canvas.min.js")
    if os.path.exists(h2c): shutil.copy(h2c, os.path.join(SITE, "s", "html2canvas.min.js"))
    site_css = FONT_CSS + _inner(NAV_CSS, "style") + "\n" + _inner(BRAND_CSS, "style")
    app_js = _inner(APP_JS, "script")
    for name, txt, ext in (("site", site_css, "css"), ("app", app_js, "js")) + ((("tpl", _TPL_CSS, "css"),) if _TPL_CSS else ()):
        fn = f"{name}-{_h(txt)}.{ext}"; open(os.path.join(SITE, "s", fn), "w", encoding="utf-8").write(txt); SHARED[name] = "/s/" + fn
    return SHARED
_H2C_STUB = ('<script>window.html2canvas=window.html2canvas||function(el,o){return (window.__bsh2c||(window.__bsh2c=new Promise(function(res,rej){var s=document.createElement("script");'
             's.src="/s/html2canvas.min.js";s.onload=function(){res(window.html2canvas)};s.onerror=rej;document.head.appendChild(s)}))).then(function(h){return h(el,o)})};</script>')
# owner 11/5: "merge Today and the Home Screen together. Lose the today button and give back the social button" - Today's content is the home page now (the logo goes home)
APP_TABS = [("/boards/", "Boards", '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10"/></svg>'),
            ("/build/", "Builder", '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/><circle cx="12" cy="12" r="9"/></svg>'),
            ("/team/", "Fantasy", '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>'),
            ("/live/", "Live", '<svg viewBox="0 0 24 24"><path d="M4 12h3l2-6 4 12 2-6h5"/></svg>'),
            ("/social/", "Social", '<svg viewBox="0 0 24 24"><path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/></svg>')]   # owner 11/5: Boards, Builder, Fantasy, Live, Social
def apptabs(path):
    # five bottom tabs; Fantasy lights up for every page in the Fantasy group
    def on(p): return path == p or (p != "/" and path.startswith(p)) or (p == "/team/" and path.startswith(("/trade/", "/dfs/")))
    return '<nav class="apptabs" aria-label="app tabs">' + "".join(f'<a href="{p}" class="{"on" if on(p) else ""}">{svg}<span>{t}</span></a>' for p, t, svg in APP_TABS) + '</nav>\n'
APP_JS = r"""<script>
(function(){
  // ---- 11/4 UX audit: three site-wide behaviours ----
  // 1. game deep links: the home page and Today link to /boards/#g-BAL-JAX, the boards card is id="BAL-JAX", the builder's is "g-BAL-JAX" and
  //    the Live page's is "lv-BAL-JAX" - land on the game whichever form the link used
  function landOnHash(){ var h = (location.hash || '').slice(1); if(!h) return; var el = document.getElementById(h);
    if(!el){ var m = h.match(/^(?:g-|lv-|box-|td-)?([A-Z]{2,3}-[A-Z]{2,3})$/); if(!m) return;
      el = ['g-' + m[1], 'lv-' + m[1], 'td-' + m[1], m[1]].map(function(id){ return document.getElementById(id); }).filter(Boolean)[0]; if(!el) return; }
    if(el.classList.contains('gcard') || el.classList.contains('lg2') || el.classList.contains('tdgame')) el.classList.add('open');
    if(el.classList.contains('card')) el.classList.add('expanded');   // boards card (template.html folds .card:not(.expanded) on phones)
    var det = el.querySelector('details'); if(det && el.tagName !== 'DETAILS') det.open = true;
    setTimeout(function(){
      // land just below the sticky chrome as it will look once scrolled (the header compacts on scroll), whatever the page's own margins
      document.body.classList.add('bs-scrolled');
      var nav = document.querySelector('.sitenav'), top = document.querySelector('.top');
      var chrome = (nav ? nav.getBoundingClientRect().height : 0) + (top && getComputedStyle(top).position === 'sticky' ? top.getBoundingClientRect().height : 0) + 8;
      var y = el.getBoundingClientRect().top + (window.scrollY || 0) - chrome; window.scrollTo(0, Math.max(0, y)); lastY = y; }, 60); }
  window.addEventListener('load', landOnHash); window.addEventListener('hashchange', landOnHash);
  // 2. the page's sticky header collapses while scrolling down (CSS: body.bs-scrolled; phones hide the mast, desktop keeps title + chips)
  var lastY = 0; window.addEventListener('scroll', function(){ var y = window.scrollY || 0; if(y > 140 && y > lastY + 4) document.body.classList.add('bs-scrolled'); else if(y < lastY - 12 || y < 80) document.body.classList.remove('bs-scrolled'); lastY = y; }, {passive: true});
  // 3. player search from any page: /b/players.json (name, slug, team, pos, opp, has props) -> player page, builder, boards
  var sb = document.getElementById('bssrchbtn');
  if(sb){ var IDX = null, box = null, list = null, inp = null, sel = 0;
    function build(){ box = document.createElement('div'); box.className = 'bssrch'; box.innerHTML = '<div class="box"><div class="row"><input type="search" placeholder="Player, team or position" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="Find a player"><button type="button" class="x" aria-label="Close">×</button></div><ul></ul><div class="hint">Tap a name for his page. Builder opens his legs in the Parlay Builder; Board opens his game. Type a team code (BUF) or a position (TE).</div></div>'; document.body.appendChild(box); inp = box.querySelector('input'); list = box.querySelector('ul');
      box.addEventListener('click', function(e){ if(e.target === box || e.target.classList.contains('x')) close(); }); inp.addEventListener('input', function(){ sel = 0; render(); });
      inp.addEventListener('keydown', function(e){ var items = list.querySelectorAll('li'); if(e.key === 'ArrowDown'){ sel = Math.min(sel + 1, items.length - 1); paint(); e.preventDefault(); } else if(e.key === 'ArrowUp'){ sel = Math.max(sel - 1, 0); paint(); e.preventDefault(); } else if(e.key === 'Enter'){ var a = items[sel] && items[sel].querySelector('a.pl'); if(a) location.href = a.getAttribute('href'); } else if(e.key === 'Escape') close(); }); }
    function paint(){ list.querySelectorAll('li').forEach(function(li, i){ li.classList.toggle('on', i === sel); }); }
    function norm(s){ return String(s || '').toLowerCase().replace(/[.'\u2019]/g, ''); }
    function render(){ var q = norm(inp.value).trim(); if(!IDX){ list.innerHTML = '<li><a class="pl">Loading players…</a></li>'; return; }
      var terms = q.split(/\s+/).filter(Boolean); var hits = !terms.length ? [] : IDX.filter(function(p){ var hay = norm(p.n) + ' ' + norm(p.t) + ' ' + norm(p.p) + ' ' + norm(p.o); return terms.every(function(t){ return hay.indexOf(t) >= 0; }); });
      hits.sort(function(a, b){ var an = norm(a.n).indexOf(terms[0]) === 0 ? 0 : 1, bn = norm(b.n).indexOf(terms[0]) === 0 ? 0 : 1; return an - bn || (b.l - a.l) || a.n.localeCompare(b.n); });
      list.innerHTML = hits.slice(0, 12).map(function(p){ var gid = p.t && p.o ? [p.t, p.o].sort().join('-') : ''; return '<li><a class="pl" href="/player/' + p.s + '/">' + esc(p.n) + '<small>' + esc(p.p) + ' · ' + esc(p.t) + (p.o ? ' ' + (p.o === 'BYE' ? '· bye' : 'vs ' + esc(p.o)) : '') + (p.l ? ' · props this week' : '') + '</small></a><span class="go">' + (p.l ? '<a href="/build/?p=' + encodeURIComponent(p.n) + '">Builder</a>' : '') + (gid && p.o !== 'BYE' ? '<a href="/boards/#' + gid + '">Board</a>' : '') + '</span></li>'; }).join('') || (terms.length ? '<li><a class="pl">No player, team or position matches "' + esc(inp.value) + '"</a></li>' : ''); paint(); }
    function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
    function open(){ if(!box) build(); box.classList.add('open'); inp.value = ''; list.innerHTML = ''; setTimeout(function(){ inp.focus(); }, 30);
      if(!IDX){ fetch('/b/players.json', {cache: 'force-cache'}).then(function(r){ return r.ok ? r.json() : []; }).then(function(j){ IDX = Array.isArray(j) ? j : []; render(); }).catch(function(){ IDX = []; render(); }); } }
    function close(){ if(box) box.classList.remove('open'); }
    sb.addEventListener('click', open);
    document.addEventListener('keydown', function(e){ if((e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey))) && !/input|textarea|select/i.test((document.activeElement || {}).tagName || '')){ e.preventDefault(); open(); } }); }
  // full-bleed header: inner pages pad/margin the body, so measure the nav's inset and pull it back to the viewport edge
  function bleed(){ var n = document.getElementById('sitenav'); if(!n) return; var d = document.documentElement.style; d.setProperty('--bs-inset', '0px'); var l = Math.round(n.getBoundingClientRect().left); if(l > 0) d.setProperty('--bs-inset', l + 'px'); }
  window.addEventListener('resize', bleed); window.addEventListener('orientationchange', bleed);
  if('serviceWorker' in navigator){ window.addEventListener('load', function(){ navigator.serviceWorker.register('/sw.js').catch(function(){}); }); }
  // install hint: Chrome/Android fire beforeinstallprompt; iOS gets a one-line how-to. Dismissal is remembered for 30 days.
  var bar = document.getElementById('installbar'); if(!bar) return;
  var dismissed = 0; try { dismissed = +localStorage.getItem('bs_install_dismissed') || 0; } catch(e){}
  var standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  if(standalone || Date.now() - dismissed < 30*864e5) return;
  var deferred = null;
  window.addEventListener('beforeinstallprompt', function(e){ e.preventDefault(); deferred = e; bar.querySelector('.msg').textContent = 'Add BetSweep to your home screen - opens full screen, works like an app.'; bar.querySelector('.go').hidden = false; bar.classList.add('show'); });
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
  if(ios){ bar.querySelector('.msg').innerHTML = 'Install BetSweep: tap <b>Share</b> then <b>Add to Home Screen</b>.'; bar.classList.add('show'); }
  bar.querySelector('.go').addEventListener('click', function(){ if(deferred){ deferred.prompt(); deferred = null; } bar.classList.remove('show'); });
  bar.querySelector('.x').addEventListener('click', function(){ bar.classList.remove('show'); try { localStorage.setItem('bs_install_dismissed', String(Date.now())); } catch(e){} });
})();
(function(){
  // 11/4 UX audit: Theme switch (Auto / Dark / Light). Auto follows the phone; the choice is kept in localStorage and applied before
  // paint by the one-line script in <head>. Home stays dark (hero landing); every app page honours data-theme.
  var g = document.querySelector('.sitenav .thm'); if(!g) return;
  function cur(){ try { var t = localStorage.getItem('bs_theme'); return (t === 'dark' || t === 'light') ? t : 'auto'; } catch(e){ return 'auto'; } }
  function paint(){ var c = cur(); g.querySelectorAll('button').forEach(function(b){ b.classList.toggle('on', b.getAttribute('data-thm') === c); b.setAttribute('aria-pressed', b.getAttribute('data-thm') === c ? 'true' : 'false'); }); }
  g.addEventListener('click', function(e){
    var b = e.target.closest('button[data-thm]'); if(!b) return;
    var t = b.getAttribute('data-thm');
    try { if(t === 'auto') localStorage.removeItem('bs_theme'); else localStorage.setItem('bs_theme', t); } catch(err){}
    if(t === 'auto') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', t);
    paint();
  });
  paint();
})();
</script>"""
INSTALL_BAR = '<div class="installbar" id="installbar"><b>App</b><span class="msg"></span><button type="button" class="go" hidden>Install</button><button type="button" class="x" aria-label="dismiss">×</button></div>'
def sitenav(path):
    def on(p): return path == p or (p != "/" and path.startswith(p))
    tabs = ""
    for p, t, kids in NAV_GROUPS:
        if not kids: tabs += f'<a href="{p}" class="{"on" if on(p) else ""}">{t}</a>'; continue
        con = any(on(k[0]) for k in kids)
        tabs += (f'<div class="dd{" on" if con else ""}"><button type="button" class="ddb" aria-expanded="false" aria-haspopup="true">{t} <i aria-hidden="true">▾</i></button>'
                 f'<span class="ddh">{t}</span><div class="ddm">' + "".join(f'<a href="{kp}" class="{"on" if on(kp) else ""}">{kt}<small>{kd}</small></a>' for kp, kt, kd in kids) + '</div></div>')
    return (f'<nav class="sitenav" id="sitenav"><div class="in"><a class="brand" href="/" aria-label="BetSweep home"><img class="cream" src="/wordmark.png" alt="BetSweep"><img class="ink" src="/wordmark-ink.png" alt="BetSweep"></a>'
            f'<button class="srch" type="button" id="bssrchbtn" aria-label="Find a player" title="Find a player"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="M16.5 16.5L21 21" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg></button>'
            f'<button class="menu" type="button" aria-expanded="false" onclick="var n=document.getElementById(\'sitenav\');n.classList.toggle(\'open\');this.setAttribute(\'aria-expanded\',n.classList.contains(\'open\'))">Menu <span aria-hidden="true">☰</span></button>'
            f'<div class="acct" id="bsacct"></div><div class="tabs">{tabs}<div class="thm" role="group" aria-label="Theme"><span>Theme</span><button type="button" data-thm="auto">Auto</button><button type="button" data-thm="dark">Dark</button><button type="button" data-thm="light">Light</button></div></div></div></nav>\n'
            '<script>(function(){var n=document.getElementById("sitenav");if(window.matchMedia("(max-width:1240px)").matches){var c=n.querySelector(".dd.on");if(c)c.classList.add("open");}n.querySelectorAll(".ddb").forEach(function(b){b.addEventListener("click",function(e){e.stopPropagation();var dd=b.parentNode,o=!dd.classList.contains("open");n.querySelectorAll(".dd.open").forEach(function(x){x.classList.remove("open");x.querySelector(".ddb").setAttribute("aria-expanded","false");});if(o){dd.classList.add("open");b.setAttribute("aria-expanded","true");}});});document.addEventListener("click",function(e){if(e.target.closest&&(e.target.closest("#sitenav .tabs")||e.target.closest("#sitenav .menu")))return;n.querySelectorAll(".dd.open").forEach(function(x){x.classList.remove("open");});});document.addEventListener("keydown",function(e){if(e.key==="Escape")n.querySelectorAll(".dd.open").forEach(function(x){x.classList.remove("open");});});})();</script>\n'
            '<script>(function(){var n=document.getElementById("sitenav"),d=document.documentElement.style;d.setProperty("--bs-inset","0px");d.setProperty("--bs-top","0px");var r=n.getBoundingClientRect(),l=Math.round(r.left),t=Math.round(r.top+(window.scrollY||0));if(l>0)d.setProperty("--bs-inset",l+"px");if(t>0&&t<40)d.setProperty("--bs-top",t+"px");var a=n.querySelector(".tabs a.on"),tb=n.querySelector(".tabs");if(a&&tb&&tb.scrollWidth>tb.clientWidth)tb.scrollLeft=a.offsetLeft-tb.offsetLeft-40;})();</script>\n')

def wrap(body, title, desc, path, og_img):
    body = re.sub(r"https://claude\.ai/artifact/([A-Za-z0-9]+)", lambda m: ART.get(m.group(1), m.group(0)), body)
    # owner 10/30: the page slip (template.html) has the Parlay Builder's Post to BetSweep Social + Short link buttons; their dialog and
    # scripts come from social.py / shortlinks.py (one copy of the code). The builder already carries its own (id="sdlg") - never twice.
    if 'id="postsl"' in body and 'id="sdlg"' not in body:
        import social as _SOC, shortlinks as _SL
        body += "\n<style>" + _SOC.POST_CSS + "</style>\n" + _SOC.POST_HTML + "\n" + _SOC.POST_JS + "\n" + _SL.BTN_JS
    body = body.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
    body = body.replace('<meta name="viewport" content="width=device-width, initial-scale=1">\n', "")   # template.html carries one for raw/artifact views; the site head has its own
    body = re.sub(r'\s*<nav class="archive"[^>]*>.*?</nav>', "", body, count=1, flags=re.S)
    # 11/5 brand pass: "Week 9 · Matchup Boards" -> a small red WEEK 9 over the title in the brand italic (CSS: .mast h1 small / b)
    body = re.sub(r"<h1>Week (\d+) · <b>(.*?)</b></h1>", r"<h1><small>Week \1</small><b>\2</b></h1>", body, count=1)
    body = re.sub(r'(<a href="[^"]*" class="tool">)(.*?) →(</a>)', r"\1\2\3", body)   # arrows out of button text (the swoosh is the arrow)
    # audit 10/26: the 215px banner opened every inner page (first phone screen mostly banner) and cost ~300KB per page; the site header
    # already carries the brand, so the banner stays only in the claude.ai artifact copies
    body = re.sub(r'<div class="banner"><img src="data:image/[a-z]+;base64,[^"]*"[^>]*></div>\s*', "", body, count=1)   # site has the header tabs; the artifact keeps its own links
    head = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{html.escape(desc)}">
<link rel="icon" type="image/png" href="/favicon.png">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#d7332a">
<script>try{{var _t=localStorage.getItem("bs_theme");if(_t==="dark"||_t==="light")document.documentElement.setAttribute("data-theme",_t)}}catch(e){{}}</script>
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"><meta name="apple-mobile-web-app-title" content="BetSweep">
<link rel="canonical" href="{BASE}{path}">
<meta property="og:type" content="website"><meta property="og:site_name" content="BetSweep">
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{BASE}{path}"><meta property="og:image" content="{BASE}{og_img}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{html.escape(desc)}"><meta name="twitter:image" content="{BASE}{og_img}">
<script>window.__BS_ACCOUNT={{url:"{ACCT.SUPABASE_URL}",key:"{ACCT.SUPABASE_ANON}",google:{"true" if ACCT.GOOGLE else "false"}}};</script>
<script defer src="{ACCT.SUPABASE_JS}"></script><script defer src="/account.js"></script><script defer src="/risk.js"></script>
'''
    # the built page starts with <title>; everything up to </style>... is head material, the rest is body
    m = re.search(r"</style>\s*", body)
    headpart, rest = body[:m.end()], body[m.end():]
    foot = '' if path == "/" else '<p style="max-width:1360px;margin:10px auto 40px;padding:0 16px;color:var(--mute);font-size:12px;line-height:1.5">Information and analysis only, not betting advice; no outcome is guaranteed. 21+ (18+ where permitted). Problem gambling help: 1-800-GAMBLER. BetSweep is not affiliated with FanDuel or the NFL. Follow <a href="https://x.com/bet_sweep" style="color:var(--ink)">@bet_sweep on X</a> and <a href="https://www.instagram.com/bet_sweep" style="color:var(--ink)">Instagram</a>. Questions, corrections or a leg that graded wrong: <a href="mailto:support@betsweep.co" style="color:var(--ink)">support@betsweep.co</a>. BetSweep may earn a commission when you bet through links on this site; it never changes a pick or a grade (<a href="/responsible-gambling/" style="color:var(--ink)">disclosures</a>). © 2026 BetSweep LLC. BetSweep™ is a trademark of BetSweep LLC (U.S. Serial No. 50169404). · <a href="/guide/" style="color:var(--ink)">How to read BetSweep</a> · <a href="/terms/" style="color:var(--ink)">Terms</a> · <a href="/privacy/" style="color:var(--ink)">Privacy</a> · <a href="/responsible-gambling/" style="color:var(--ink)">Responsible gambling</a>.</p>'
    if not SHARED: _write_shared()
    headpart = re.sub(r'\s*<link rel="stylesheet" href="https://fonts\.googleapis\.com[^>]*>', "", headpart)   # fonts are self-hosted (site.css @font-face)
    headpart = re.sub(r'\s*<link rel="preconnect" href="https://fonts\.[^>]*>', "", headpart)
    if _TPL_CSS and _TPL_CSS in headpart and "tpl" in SHARED:
        headpart = headpart.replace(_TPL_CSS, "", 1); headpart = headpart.replace("<style>", f'<link rel="stylesheet" href="{SHARED["tpl"]}">\n<style>', 1)
    rest = rest.replace('<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>', _H2C_STUB)
    pre = ('<link rel="preload" href="/s/fonts/barlow-condensed-latin-700-normal.woff2" as="font" type="font/woff2" crossorigin>'
           '<link rel="preload" href="/s/fonts/ibm-plex-sans-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>') if FONT_CSS else ""
    shared_css = f'<link rel="stylesheet" href="{SHARED["site"]}">' if "site" in SHARED else NAV_CSS + BRAND_CSS
    shared_js = f'<script src="{SHARED["app"]}" defer></script>' if "app" in SHARED else APP_JS
    return head + pre + headpart + shared_css + "</head>\n<body>\n" + sitenav(path) + (INSTALL_BAR if path == "/" else "") + rest + foot + apptabs(path) + (_H2C_STUB if ("html2canvas" in rest and _H2C_STUB not in rest) else "") + shared_js + "\n</body>\n</html>\n"

def title_desc(src):
    t = re.search(r"<title>(.*?)</title>", src).group(1)
    d = re.search(r'<div class="mast">.*?<p>(.*?)</p>', src, re.S)
    d = re.sub(r"<[^>]+>", "", d.group(1)) if d else "BetSweep model boards"
    return html.unescape(t), html.unescape(d)[:200]

import hashlib
def externalize(page, dest_dir, path, min_bytes=80000):
    """owner 10/26: move each big inline data block (<script>window.__BS = {...}</script> and friends) into its own file named by a
    content hash (data-<hash>.js next to the page), loaded with a plain <script src>. Same execution order as the inline block, but the
    browser and the service worker (cache-first for non-page files) keep it, so repeat visits within a build skip the download, and the
    page HTML itself shrinks (builder 3.6 MB -> ~0.4 MB). Step 6c deletes the folder before copying, so old hashes never pile up."""
    def rep(m):
        body = m.group(1)
        if len(body) < min_bytes or not body.lstrip().startswith("window.__"): return m.group(0)
        h = hashlib.sha1(body.encode()).hexdigest()[:12]; fn = f"data-{h}.js"
        open(os.path.join(dest_dir, fn), "w").write(body)
        return f'<script src="{path}{fn}"></script>'
    return re.sub(r"<script>(.*?)</script>", rep, page, flags=re.S)
def place(src_html, img_dir, dest_dir, path):
    os.makedirs(dest_dir, exist_ok=True)
    for _old in glob.glob(os.path.join(dest_dir, "data-*.js")): os.remove(_old)
    src = open(src_html).read(); t, d = title_desc(src)
    og = path + "img/summary.png" if os.path.exists(os.path.join(img_dir, "summary.png")) else "/og.png"
    open(os.path.join(dest_dir, "index.html"), "w").write(externalize(wrap(src, t, d, path, og), dest_dir, path))
    if os.path.isdir(img_dir): shutil.copytree(img_dir, os.path.join(dest_dir, "img"), dirs_exist_ok=True)
    return t

made = []
made.append(place(os.path.join(OUT, "matchup-boards.html"), os.path.join(OUT, "img"), os.path.join(SITE, "boards"), "/boards/"))
if os.path.exists(os.path.join(OUT, "season-receipt.html")):
    made.append(place(os.path.join(OUT, "season-receipt.html"), os.path.join(OUT, "img-season"), os.path.join(SITE, "season"), "/season/"))
if os.path.exists(os.path.join(OUT, "builder.html")):
    made.append(place(os.path.join(OUT, "builder.html"), os.path.join(OUT, "img-build"), os.path.join(SITE, "build"), "/build/"))
for _slug, _dir in (("terms", "terms"), ("privacy", "privacy"), ("responsible", "responsible-gambling")):
    if os.path.exists(os.path.join(OUT, f"legal-{_slug}.html")):
        made.append(place(os.path.join(OUT, f"legal-{_slug}.html"), os.path.join(OUT, "img-none"), os.path.join(SITE, _dir), f"/{_dir}/"))
if os.path.exists(os.path.join(OUT, "live.html")):
    made.append(place(os.path.join(OUT, "live.html"), os.path.join(OUT, "img-none"), os.path.join(SITE, "live"), "/live/"))
if os.path.exists(os.path.join(OUT, "team.html")):
    made.append(place(os.path.join(OUT, "team.html"), os.path.join(OUT, "img-none"), os.path.join(SITE, "team"), "/team/"))
    # /fantasy/ is a second address for the same page (the page is named Fantasy; /team/ stays the canonical URL so older links keep working)
    os.makedirs(os.path.join(SITE, "fantasy"), exist_ok=True)
    open(os.path.join(SITE, "fantasy", "index.html"), "w").write('<!doctype html><html><head><meta charset="utf-8"><title>BetSweep Fantasy</title><link rel="canonical" href="https://betsweep.co/team/"><meta http-equiv="refresh" content="0; url=/team/"><script>location.replace("/team/"+location.search+location.hash)</script></head><body><a href="/team/">BetSweep Fantasy</a></body></html>')
if os.path.exists(os.path.join(OUT, "firsttd.html")):
    made.append(place(os.path.join(OUT, "firsttd.html"), os.path.join(OUT, "img-none"), os.path.join(SITE, "firsttd"), "/firsttd/"))
if os.path.exists(os.path.join(OUT, "dfs.html")):
    made.append(place(os.path.join(OUT, "dfs.html"), os.path.join(OUT, "img-none"), os.path.join(SITE, "dfs"), "/dfs/"))
os.makedirs(os.path.join(SITE, "me"), exist_ok=True)
import social as SOCIAL   # /social/ - users' posted slips (owner 10/26)
try: WEEK_NOW = int(json.load(open(os.path.join(OUT, "builder_data.json")))["week"])   # the builder's week: "Load into my slip" writes that week's slip key
except Exception: WEEK_NOW = 0
_sl, _sb = ACCT._base_css()
os.makedirs(os.path.join(SITE, "social"), exist_ok=True)
open(os.path.join(SITE, "social", "index.html"), "w").write(wrap(SOCIAL.page(WEEK_NOW).replace("__BASE__", _sl).replace("__BASECSS__", _sb), "BetSweep Social", "Betslips posted by BetSweep users - tail them on FanDuel and upvote the best. Slips leave the feed once a leg loses or the games end.", "/social/", "/og.png"))
open(os.path.join(SITE, "me", "index.html"), "w").write(wrap(ACCT.me_page(), "My BetSweep", "Your saved betslips, fantasy teams, trade scenarios and Sleeper league - synced to your account when you sign in.", "/me/", "/og.png"))
if os.path.exists(os.path.join(OUT, "trade.html")):
    made.append(place(os.path.join(OUT, "trade.html"), os.path.join(OUT, "img-none"), os.path.join(SITE, "trade"), "/trade/"))
# ---- owner 10/30: /player/<slug>/ pages + directory (build_players.py), /usage/ + /benefits/ (build_usage.py), /guide/ (build_guide.py).
# These pages carry their own <title> and <meta name="description">; the shared player.css / player.js sit in /player/ once.
def place_plain(src_html, dest_dir, path):
    src = open(src_html).read(); t = html.unescape(re.search(r"<title>(.*?)</title>", src).group(1))
    m = re.search(r'<meta name="description" content="([^"]*)">\n?', src); d = html.unescape(m.group(1)) if m else "BetSweep"
    if m: src = src.replace(m.group(0), "", 1)
    os.makedirs(dest_dir, exist_ok=True); open(os.path.join(dest_dir, "index.html"), "w").write(wrap(src, t, d, path, "/og.png")); return t
# owner 11/10: /badbeats/ - 'Missed by one' (badbeats.py, Tuesday after grading)
if os.path.exists(os.path.join(OUT, "badbeats.html")):
    made.append(place_plain(os.path.join(OUT, "badbeats.html"), os.path.join(SITE, "badbeats"), "/badbeats/"))
# owner 11/10: /sweep/ - "Sweep my slip" (build_slipcheck.py): a screenshot of any FanDuel slip -> the builder's verdict on it
if os.path.exists(os.path.join(OUT, "slipcheck.html")):
    made.append(place_plain(os.path.join(OUT, "slipcheck.html"), os.path.join(SITE, "sweep"), "/sweep/"))
# owner 11/8-11/10: /pairs/ - the either-or touchdown pair maker (build_pairs.py, pairs.py): "A or B to score" judged as a pair; /b/pairs.json for the API page
if os.path.exists(os.path.join(OUT, "pairs.html")):
    made.append(place_plain(os.path.join(OUT, "pairs.html"), os.path.join(SITE, "pairs"), "/pairs/"))
    try: os.makedirs(os.path.join(SITE, "b"), exist_ok=True); shutil.copy(os.path.join(OUT, "pairs.json"), os.path.join(SITE, "b", "pairs.json"))
    except Exception as _e: print("note: /b/pairs.json not written:", _e)
# owner 11/10: /simple/ - the Simple view for casual visitors (build_simple.py). Built HERE, last, so it shows this run's final promos, Sweep says
# lines and best parlays whatever order the earlier steps ran in. Full stays the default; the home page's "Simple view" pill switches.
try:
    import build_simple as _SIMPLE
    print(_SIMPLE.build(OUT))
    made.append(place_plain(os.path.join(OUT, "simple.html"), os.path.join(SITE, "simple"), "/simple/"))
except BaseException as _e: print("note: Simple view not built this run:", _e)
# owner 11/10: /survivor/ - the Survivor planner (build_survivor.py): elimination pools, the best pick now and the team to save for each week left
if os.path.exists(os.path.join(OUT, "survivor.html")):
    made.append(place_plain(os.path.join(OUT, "survivor.html"), os.path.join(SITE, "survivor"), "/survivor/"))
# 11/5 (out-of-the-box batch): /teasers/ - the teaser finder (build_teasers.py); /b/teasers.json for the app and the API page
if os.path.exists(os.path.join(OUT, "teasers.html")):
    made.append(place_plain(os.path.join(OUT, "teasers.html"), os.path.join(SITE, "teasers"), "/teasers/"))
    try: os.makedirs(os.path.join(SITE, "b"), exist_ok=True); shutil.copy(os.path.join(OUT, "teasers.json"), os.path.join(SITE, "b", "teasers.json"))
    except Exception as _e: print("note: /b/teasers.json not written:", _e)
# 11/5: /beat/ - Beat the model (build_beat.py); /b/beat.json = the pool and the model's five (frozen into Supabase beat_model by the hourly Edge Function run)
if os.path.exists(os.path.join(OUT, "beat.html")) and os.path.exists(os.path.join(OUT, "beat.json")):
    made.append(place_plain(os.path.join(OUT, "beat.html"), os.path.join(SITE, "beat"), "/beat/"))
    os.makedirs(os.path.join(SITE, "b"), exist_ok=True); shutil.copy(os.path.join(OUT, "beat.json"), os.path.join(SITE, "b", "beat.json"))
# owner 11/1: /team/compare/ - "Who should I start?" (build_startsit.py, run by build_team.py)
if os.path.exists(os.path.join(OUT, "startsit.html")) and os.path.exists(os.path.join(OUT, "startsit.json")):
    made.append(place_plain(os.path.join(OUT, "startsit.html"), os.path.join(SITE, "team", "compare"), "/team/compare/"))
    shutil.copy(os.path.join(OUT, "startsit.json"), os.path.join(SITE, "team", "compare", "data.json"))
    os.makedirs(os.path.join(SITE, "b"), exist_ok=True); shutil.copy(os.path.join(OUT, "startsit.json"), os.path.join(SITE, "b", "startsit.json"))
_PD = os.path.join(OUT, "players")
if os.path.isdir(_PD) and os.path.exists(os.path.join(_PD, "index.html")):
    _np = 0
    for _f in sorted(os.listdir(_PD)):
        if not _f.endswith(".html") or _f == "index.html": continue
        _slug = _f[:-5]; place_plain(os.path.join(_PD, _f), os.path.join(SITE, "player", _slug), f"/player/{_slug}/"); _np += 1
    made.append(place_plain(os.path.join(_PD, "index.html"), os.path.join(SITE, "player"), "/player/"))
    for _f in ("player.css", "player.js"): shutil.copy(os.path.join(_PD, _f), os.path.join(SITE, "player", _f))
    # audit 11/10: a traded player had two team-suffixed pages (/player/marvin-harrison-ari/ and -hou/); plydata keeps one entry now, and the
    # old addresses forward to it (out/players/redirects.json) so shared links and search results still land.
    try:
        for _old, _new in json.load(open(os.path.join(_PD, "redirects.json"))).items():
            _dd = os.path.join(SITE, "player", _old)
            if re.fullmatch(r"[a-z0-9\-]+", _old) and re.fullmatch(r"[a-z0-9\-]+", _new) and os.path.exists(os.path.join(SITE, "player", _new, "index.html")) and not os.path.exists(_dd):
                os.makedirs(_dd)
                open(os.path.join(_dd, "index.html"), "w").write(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>BetSweep</title><link rel="canonical" href="{BASE}/player/{_new}/"><meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url=/player/{_new}/"><script>location.replace("/player/{_new}/"+location.search+location.hash)</script></head><body><a href="/player/{_new}/">This player page moved</a></body></html>')
    except Exception as _e: print("note: player redirects not written:", _e)
    # 11/4 UX audit: the site-wide player search (APP_JS) reads /b/players.json = build_players.py's out/players/index.json
    if os.path.exists(os.path.join(_PD, "index.json")):
        os.makedirs(os.path.join(SITE, "b"), exist_ok=True); shutil.copy(os.path.join(_PD, "index.json"), os.path.join(SITE, "b", "players.json"))
    print(f"player pages: {_np}")
# owner 11/5: /dossier/ + /dossier/<gid>/ (build_dossier.py) - the Game Dossier: similar-defense splits, leaks by role, script, weather, injuries, news, tested spots
_DD = os.path.join(OUT, "dossier")
if os.path.isdir(_DD) and os.path.exists(os.path.join(_DD, "index.html")):
    shutil.rmtree(os.path.join(SITE, "dossier"), ignore_errors=True)
    for _f in sorted(os.listdir(_DD)):
        if _f.endswith(".html") and _f != "index.html": place_plain(os.path.join(_DD, _f), os.path.join(SITE, "dossier", _f[:-5]), f"/dossier/{_f[:-5]}/")
    made.append(place_plain(os.path.join(_DD, "index.html"), os.path.join(SITE, "dossier"), "/dossier/"))
    if os.path.exists(os.path.join(OUT, "dossier.json")):
        os.makedirs(os.path.join(SITE, "b"), exist_ok=True); shutil.copy(os.path.join(OUT, "dossier.json"), os.path.join(SITE, "b", "dossier.json"))
# owner 11/5: /teams/ + /teams/<abbr>/ (build_teams.py) - team stats, results, ATS / over-under and every game's box score; styled by /player/player.css
_TD = os.path.join(OUT, "teams")
if os.path.isdir(_TD) and os.path.exists(os.path.join(_TD, "index.html")):
    _nt = 0
    for _f in sorted(os.listdir(_TD)):
        if not _f.endswith(".html") or _f == "index.html": continue
        _ab = _f[:-5]; place_plain(os.path.join(_TD, _f), os.path.join(SITE, "teams", _ab), f"/teams/{_ab}/"); _nt += 1
    made.append(place_plain(os.path.join(_TD, "index.html"), os.path.join(SITE, "teams"), "/teams/"))
    shutil.copy(os.path.join(_TD, "teams.js"), os.path.join(SITE, "teams", "teams.js"))
    if os.path.isdir(os.path.join(_TD, "box")):
        shutil.rmtree(os.path.join(SITE, "teams", "box"), ignore_errors=True); shutil.copytree(os.path.join(_TD, "box"), os.path.join(SITE, "teams", "box"))
    print(f"team pages: {_nt}")
for _src, _dir in (("usage.html", "usage"), ("benefits.html", "benefits"), ("guide.html", "guide")):
    if os.path.exists(os.path.join(OUT, _src)): made.append(place_plain(os.path.join(OUT, _src), os.path.join(SITE, _dir), f"/{_dir}/"))
if os.path.isdir(os.path.join(OUT, "data")):    # per-week box scores for /me/ slip grading (build_mydata.py)
    shutil.copytree(os.path.join(OUT, "data"), os.path.join(SITE, "data"), dirs_exist_ok=True)
if os.path.isdir(os.path.join(OUT, "promo")):   # promoted-bet cards for X / IG (and the home page's download buttons)
    shutil.copytree(os.path.join(OUT, "promo"), os.path.join(SITE, "promo"), dirs_exist_ok=True)
# ---- /b/ short bet links (shortlinks.py, owner 10/27): one landing page per promoted bet at /b/w<week>-<slot>/ with its square poster
# as the X / OG card, plus /b/ which lists this week's promoted bets and renders builder slips from Supabase (?s=<code>).
# The clone's b/ folder is copied over, never emptied, so last week's links keep working after their promo/ posters are replaced.
import shortlinks as SL
try: _promos = json.load(open(os.path.join(OUT, "promos.json")))
except Exception: _promos = []
# owner 11/1: /b/promos.json - this week's promoted bets leg by leg, for the slip-alerts promo watch (pushes the owner when a LIVE promo leg is hit by
# an injury, a weather turn or an owner note before kickoff)
try:
    os.makedirs(os.path.join(SITE, "b"), exist_ok=True)
    json.dump([{"week": _p.get("week"), "slot": _p.get("slot"), "title": _p.get("title"), "status": _p.get("status", "LIVE"), "sweep": bool(_p.get("sweep")),   # sweep: the day's Daily Sweep (owner 11/10)
                "legs": [{"key": _l.get("key"), "who": _l.get("who"), "market": _l.get("market"), "gid": _l.get("gid"), "ko": _l.get("ko"), "disp": _l.get("disp")} for _l in (_p.get("legs") or [])]}
               for _p in _promos], open(os.path.join(SITE, "b", "promos.json"), "w"))
except Exception as _e: print("note: /b/promos.json not written:", _e)
# 11/4 (owner: price-move alerts): /b/plus.json - the Model's Best plus-money + TD tier legs with the FanDuel price they were built at, so the
# price-moves workflow (.github/price_moves.py, every 30 min from the sheet mirror) can push the owner when the market moves toward one
try:
    _bd = json.load(open(os.path.join(OUT, "builder_data.json"))); _gko = {g["gid"]: g.get("ko") for g in _bd.get("games", [])}
    _plus = [{"key": f"{l['pl']}|{l['m']}|{int(round(l.get('ln') or 1))}", "fdkey": f"{str(l['pl']).lower()}|{l['m']}|{int(round(l.get('ln') or 1))}", "pl": l["pl"], "m": l["m"], "ln": l.get("ln"), "o": l.get("o"), "bk": l.get("bk"), "p": l.get("p"), "raw": l.get("raw_p"),
              "tier": l.get("tier"), "gid": l.get("g"), "ko": _gko.get(l.get("g")), "fd": (l.get("fd") or {}).get("u")}
             for l in _bd.get("legs", []) if l.get("tier") in ("plus", "td") and not l.get("gl") and not l.get("u")]
    json.dump({"week": _bd.get("week"), "built": _bd.get("built"), "legs": _plus}, open(os.path.join(SITE, "b", "plus.json"), "w"))
    print(f"wrote /b/plus.json: {len(_plus)} plus / TD tier legs with their build prices")
except Exception as _e: print("note: /b/plus.json not written:", _e)
# 11/4 (owner: FanDuel affiliate links): /b/aff.json from the sheet's 'AUTO - Settings' row "FanDuel affiliate" (template with {url}, or query params).
# Empty row = {} = the template's click hook does nothing. The deep links themselves are never changed (see template.html).
try:
    _st = json.load(open(os.path.join(IN, "settings.json"))); _st = _st.get("values", _st) if isinstance(_st, dict) else _st
    _aff = next((str(r[1]).strip() for r in _st if len(r) > 1 and str(r[0]).strip().lower() == "fanduel affiliate"), "")
    json.dump({"fd": _aff} if _aff else {}, open(os.path.join(SITE, "b", "aff.json"), "w")); print("wrote /b/aff.json:", "set" if _aff else "empty (no affiliate tag yet)")
except Exception as _e: print("note: /b/aff.json not written:", _e)
# 11/4 context desk: keep this week's trending list and consensus table on the site (data/) so the Tuesday grades (trending_grade.py,
# consensus_grade.py) can read what the model and the market said before the games, from git history if need be.
try:
    os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
    for _fn in glob.glob(os.path.join(OUT, "trending_w*.json")) + glob.glob(os.path.join(OUT, "consensus_w*.json")):
        shutil.copy(_fn, os.path.join(SITE, "data", os.path.basename(_fn).replace("_", "-"))); print("kept", os.path.basename(_fn), "in data/")
except Exception as _e: print("note: context tables not kept:", _e)
# 11/4: /b/live-legs.json - the live page's tracked legs with their pregame chance (build_live.py); pinned per week by the feeds workflow for live_grade.py
try:
    shutil.copy(os.path.join(OUT, "live_legs.json"), os.path.join(SITE, "b", "live-legs.json")); print("wrote /b/live-legs.json (live page tracked legs + pregame chance)")
except Exception as _e: print("live-legs.json skipped:", _e)
_bll, _blb = ACCT._base_css()
def _blpage(inner, title="BetSweep"): return f"<title>{html.escape(title)}</title>\n{_bll}\n<style>{_blb}{SL.CSS}</style>\n{inner}"   # audit 11/10: every short-link page's tab title was just "BetSweep" (wrap() takes <title> from the body)
os.makedirs(os.path.join(SITE, "b"), exist_ok=True)
SHORT_LINKS = []
for _pr in _promos:
    if (_pr.get("checks") or {}).get("block"): continue
    _code = SL.promo_code(_pr); _d = os.path.join(SITE, "b", _code); os.makedirs(_d, exist_ok=True)
    _sq = os.path.join(OUT, "promo", f'{_pr["week"]}-{_pr["slot"]}-square.png'); _og = "/og.png"
    if os.path.exists(_sq): shutil.copy(_sq, os.path.join(_d, "card.png")); _og = f"/b/{_code}/card.png"
    _desc = f'{len(_pr["legs"])}-leg parlay · FanDuel {SL.odds_str(_pr["fd"]) if _pr.get("fd") else ""} · ' + " / ".join(l["who"] for l in _pr["legs"][:6]) + (" …" if len(_pr["legs"]) > 6 else "")
    open(os.path.join(_d, "index.html"), "w").write(wrap(_blpage(SL.promo_page(_pr), f'{_pr["title"]} · BetSweep'), f'{_pr["title"]} · BetSweep', _desc, f"/b/{_code}/", _og))
    SHORT_LINKS.append(SL.promo_url(_pr))
try: _bweek = int(json.load(open(os.path.join(OUT, "builder_data.json")))["week"])
except Exception: _bweek = ""
open(os.path.join(SITE, "b", "index.html"), "w").write(wrap(_blpage(SL.index_page(_promos, _bweek), "BetSweep bet links"), "BetSweep bet links", "Short links for every bet BetSweep posts: the legs, the model's number and one tap to FanDuel.", "/b/", "/og.png"))
try:   # owner 10/30: DraftKings / Hard Rock ids for this week's legs, so every short link gets DK + HR buttons (shortlinks.books_map)
    _bm = SL.books_map(json.load(open(os.path.join(OUT, "builder_data.json"))))
    json.dump(_bm, open(os.path.join(SITE, "b", "books.json"), "w"), separators=(",", ":")); print(f"short links: books.json {len(_bm['m'])} legs with DK/HR ids")
except Exception as _e: print("note: /b/books.json not written:", _e)
if SHORT_LINKS: print("short links: " + ", ".join(SHORT_LINKS))
weeks = []
for f in sorted(glob.glob(os.path.join(OUT, "results-week*.html"))):
    w = int(re.search(r"week(\d+)", f).group(1)); weeks.append(w)
    imgd = os.path.join(OUT, f"img-receipt-week{w}") if os.path.isdir(os.path.join(OUT, f"img-receipt-week{w}")) else os.path.join(OUT, "img-receipt")
    made.append(place(f, imgd, os.path.join(SITE, "receipts", f"week{w}"), f"/receipts/week{w}/"))
# receipts index lists every week in the archive tab too (older receipts already live in the deployed repo)
try:
    for r in json.load(open(os.path.join(IN, "archive.json")))["values"][1:]:
        if len(r) >= 3 and str(r[0]).strip() and ("claude.ai/artifact/" in str(r[2]) or "/receipts/week" in str(r[2])): weeks.append(int(float(r[0])))   # 11/5: rows may point at the site itself
except Exception: pass
weeks = sorted(set(weeks))

# ---- landing page ----
LANDING_CSS = """

:root{--bg:#0e1820;--card:#152230;--chalk:#1c2b3a;--ink:#efe9da;--mute:#97a5b3;--line:#2a3b4b;--red:#d7332a;--redtxt:#f0594e;--good:#5fcf93;--brand:'Barlow','Barlow Condensed',sans-serif;--display:'Barlow Condensed','IBM Plex Sans',sans-serif;--body:'IBM Plex Sans',system-ui,sans-serif;--plays:url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22360%22%20height%3D%22130%22%20viewBox%3D%220%200%20360%20130%22%20fill%3D%22none%22%20stroke%3D%22rgba%28239%2C233%2C218%2C0.16%29%22%20stroke-width%3D%221.6%22%20stroke-linecap%3D%22round%22%3E%0A%3Cpath%20d%3D%22M24%2018l10%2010m0-10l-10%2010M62%2088l10%2010m0-10l-10%2010M150%2020l10%2010m0-10l-10%2010M232%2096l10%2010m0-10l-10%2010M306%2026l10%2010m0-10l-10%2010M330%20100l10%2010m0-10l-10%2010M118%20112l10%2010m0-10l-10%2010%22%2F%3E%0A%3Ccircle%20cx%3D%2252%22%20cy%3D%2248%22%20r%3D%226%22%2F%3E%3Ccircle%20cx%3D%22192%22%20cy%3D%2266%22%20r%3D%226%22%2F%3E%3Ccircle%20cx%3D%22280%22%20cy%3D%2260%22%20r%3D%226%22%2F%3E%3Ccircle%20cx%3D%2296%22%20cy%3D%2226%22%20r%3D%226%22%2F%3E%3Ccircle%20cx%3D%22258%22%20cy%3D%22118%22%20r%3D%226%22%2F%3E%0A%3Cpath%20d%3D%22M52%2042C62%2022%2086%2020%20108%2016%22%20stroke-dasharray%3D%224%204%22%2F%3E%3Cpath%20d%3D%22M100%2013l9%202-5%208%22%2F%3E%0A%3Cpath%20d%3D%22M192%2060C206%2044%20222%2040%20238%2030%22%2F%3E%3Cpath%20d%3D%22M231%2027l9%202-5%208%22%2F%3E%0A%3Cpath%20d%3D%22M280%2066C270%2084%20256%2092%20240%20100%22%20stroke-dasharray%3D%224%204%22%2F%3E%3Cpath%20d%3D%22M247%2092l-8%207%2010%202%22%2F%3E%0A%3Cpath%20d%3D%22M96%2032C104%2050%20120%2060%20140%2066%22%2F%3E%3Cpath%20d%3D%22M132%2068l9-1-3-9%22%2F%3E%0A%3C%2Fsvg%3E");color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg) var(--plays) center/360px 130px repeat;color:var(--ink);font-family:var(--body);-webkit-font-smoothing:antialiased}
.hero{position:relative;width:100%;aspect-ratio:1600/595;min-height:300px;background:#0b0f15 var(--banner) center/cover no-repeat;border-bottom:1px solid var(--line)}
.hero::after{content:"";position:absolute;inset:auto 0 0 0;height:38%;background:linear-gradient(180deg,transparent,var(--bg))}
.pitch{position:relative;max-width:1360px;margin:-40px auto 0;padding:0 16px}
.pitch .card{position:relative;overflow:hidden;background:color-mix(in srgb,var(--card) 92%,transparent);border:1px solid var(--line);border-radius:14px;padding:26px 24px 22px;backdrop-filter:blur(6px)}
.pitch .card .mark{position:absolute;top:18px;right:20px;width:84px;height:84px;border-radius:50%;box-shadow:0 6px 18px rgba(0,0,0,.45);transform:rotate(-8deg)}
.pitch h1{font-family:var(--brand);font-style:italic;font-weight:800;font-size:clamp(28px,4.6vw,44px);letter-spacing:-.02em;margin:0 0 8px;line-height:1.12;max-width:900px;padding-right:100px}
.pitch h1 span{text-decoration:underline;text-decoration-color:var(--red);text-decoration-thickness:3px;text-underline-offset:5px}
.pitch p.lede{font-size:clamp(15px,1.8vw,17px);line-height:1.55;color:var(--mute);max-width:760px;margin:0 0 14px}
.stats{display:flex;flex-wrap:wrap;gap:6px 20px;font-family:var(--body);font-weight:500;letter-spacing:0;text-transform:none;font-size:13.5px;color:var(--mute);margin:0 0 8px}
.stats b{font-family:var(--display);font-weight:700;color:var(--ink);font-size:18px;margin-right:4px;font-variant-numeric:tabular-nums}
.social{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 4px}
.social a{display:inline-flex;align-items:center;gap:6px;min-height:36px;text-decoration:none;color:var(--ink);font-family:var(--display);font-weight:700;font-size:13.5px;letter-spacing:.05em;text-transform:uppercase;border:1.5px solid var(--line);border-radius:8px;padding:0 12px}
.social a:hover{border-color:var(--red)}
.social a small{font-family:var(--body);font-weight:500;text-transform:none;letter-spacing:0;color:var(--mute)}
.sec{max-width:1360px;margin:30px auto 0;padding:0 16px}
.sec h2.t{font-family:var(--display);font-weight:700;letter-spacing:.01em;text-transform:none;font-size:22px;line-height:1.1;color:var(--ink);margin:0 0 14px;padding-bottom:12px;position:relative;display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 12px}
.sec h2.t::after{content:"";position:absolute;left:0;bottom:0;width:54px;height:8px;background:var(--brush) no-repeat left center/100% 100%}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.tile{position:relative;display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;text-decoration:none;color:var(--ink);transition:transform .15s,border-color .15s}
.tile:hover{transform:translateY(-2px);border-color:var(--red)}
.tile img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;object-position:top;border-bottom:1px solid var(--line);filter:saturate(.95)}
.tile .ph{aspect-ratio:16/9;display:grid;place-items:center;background:var(--chalk) var(--plays) center/360px 130px repeat;border-bottom:1px solid var(--line)}
.tile .ph span{font-family:var(--brand);font-style:italic;font-weight:800;font-size:64px;color:var(--red);opacity:.7}
.tile .ph img.bsph{width:84px;height:84px;border-radius:50%;box-shadow:0 6px 18px rgba(0,0,0,.35)}
.tb{padding:14px 16px 16px;display:flex;flex-direction:column;gap:6px;flex:1}
.tb small{font-family:var(--display);font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:11.5px;color:var(--red)}
.tb h2{margin:0;font-family:var(--display);font-weight:700;font-size:24px;letter-spacing:.02em}
.tb p{margin:0;color:var(--mute);line-height:1.5;font-size:14px;flex:1}
.tb b{font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:12.5px;margin-top:4px}
.gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;position:relative}
@media (max-width:560px){.gal{grid-template-columns:repeat(2,1fr)}}
.gal a{display:block;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--chalk)}
.gal a:hover{border-color:var(--red)}
.gal img{display:block;width:100%;aspect-ratio:1/1;object-fit:contain;background:#0b0f15}
.feed{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px 10px;position:relative;overflow:hidden}
.feed::before{content:"";position:absolute;left:-30px;bottom:-40px;width:160px;height:110px;background:var(--red);clip-path:polygon(0 0,70% 30%,100% 100%,0 100%);opacity:.9}
.feed .wrap{position:relative;min-height:120px}
.feed .fallback{color:var(--mute);font-size:14px;line-height:1.5;margin:0}
.feed .fallback a{color:var(--ink)}
.how{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.how div{background:color-mix(in srgb,var(--card) 75%,transparent);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.how h3{margin:0 0 6px;font-family:var(--display);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:12.5px;color:var(--red)}
.how p{margin:0;color:var(--mute);font-size:14px;line-height:1.5}
footer{max-width:1360px;margin:34px auto 0;padding:18px 16px 40px;border-top:1px solid var(--line);color:var(--mute);font-size:12.5px;line-height:1.6}
footer .tag{font-family:var(--display);font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--ink);font-size:13px;margin-bottom:6px}
footer .tag i{color:var(--red);font-style:normal}
@media (max-width:560px){ .tile img,.tile .ph{aspect-ratio:16/6} .tb p{font-size:13px} .pitch{margin-top:-18px} .pitch .card{padding:20px 16px 18px} .pitch .card .mark{width:58px;height:58px;top:14px;right:14px} .pitch h1{padding-right:66px} }
/* audit 11/10: on a phone the 14 "Everything on BetSweep" tiles ran about 5,000px (a picture, a headline and four lines of copy each) -
   a fifth of the home page. Two compact columns there: tag, name, Open. The pictures and the copy stay on wide screens. */
@media (max-width:760px){ .tiles{grid-template-columns:1fr 1fr;gap:8px} .tile img,.tile .ph{display:none} .tile .tb{padding:11px 12px 10px;gap:3px} .tile .tb p{display:none} .tile .tb h2{font-size:18px;line-height:1.12} .tile .tb small{font-size:10.5px} .tile .tb b{font-size:11.5px;margin-top:2px} }
"""

def posts_gallery():
    if not POSTS_DIR or not os.path.isdir(POSTS_DIR): return ""
    files = sorted([f for f in os.listdir(POSTS_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")) and not f.startswith(".")], reverse=True)[:6]
    if not files: return ""
    os.makedirs(os.path.join(SITE, "p"), exist_ok=True)
    shown = []
    for f in files:   # web-size copies (phone uploads are often 3+ MB); originals stay in the repo's posts/ untouched
        src = os.path.join(POSTS_DIR, f); dst = os.path.join(SITE, "p", os.path.splitext(f)[0] + ".jpg")
        try:
            from PIL import Image
            im = Image.open(src).convert("RGB"); im.thumbnail((1000, 1000)); im.save(dst, "JPEG", quality=86, optimize=True); shown.append(os.path.basename(dst))
        except Exception:
            shutil.copy2(src, os.path.join(SITE, "p", f)); shown.append(f)
    return '<div class="gal">' + "".join(f'<a href="https://x.com/bet_sweep" target="_blank" rel="noopener"><img src="/p/{html.escape(f)}" alt="BetSweep post" loading="lazy"></a>' for f in shown) + '</div>'

def landing(weeks):
    import datetime as _dt
    bj = json.load(open(os.path.join(IN, "boards.json")))["values"]; week = int(float(bj[1][1]))
    try: nlegs = len(json.load(open(os.path.join(OUT, "builder_data.json")))["legs"])
    except Exception: nlegs = 0
    try: nftd = json.load(open(os.path.join(OUT, "firsttd_top.json")))["games"]; nftd = sum(1 for _ in open(os.path.join(OUT, "firsttd.html")).read().split('<tr class=')) - 1
    except Exception: nftd = 0
    ngames = len([f for f in glob.glob(os.path.join(OUT, "img", "*-story.png")) if not f.endswith("summary-story.png")])
    stamp = _dt.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%a %-m/%-d %-I:%M %p")
    latest = max(weeks) if weeks else None
    GAL = posts_gallery()
    tiles = [
        ("/boards/", "Matchup Boards", f"Week {week}", "One board per game: projected score, game-script odds, weather, every skill player's projected stats colored by the matchup, the best FanDuel leg for each, and a model-priced same-game slip.", "/boards/img/summary.png"),
        ("/build/", "Parlay Builder", (f"{nlegs:,} legs priced" if nlegs else "Live"), "Every FanDuel player prop on the slate against the model. Filter, fade lines up or down, drag to a target price, see each player's last five games and what the defense allows, then send the slip straight to FanDuel.", ("/build/img/preview.png" if os.path.exists(os.path.join(OUT, "img-build", "preview.png")) else None)),
        ("/live/", "Live", "Game day", "During the games: every leg the model liked that has not happened yet, against the live box score, with the model's chance from here. Built for live betting.", None),
        ("/team/", "Fantasy", "Sleeper import + builder", "Import your Sleeper league or build a lineup by hand and get the model's start/sit calls, the bench moves it would make, and the waiver targets it likes this week.", None),
        ("/trade/", "Trade Calculator", "Rest of season · superflex + TE premium", "Trade values built from the model's own game data, not a vote: points above the replacement starter for your format over the games left, with superflex, TE-premium, scoring and league-size toggles that recompute every value on the page.", None),
        ("/player/", "Players", "One page per player", "Every player with a prop or a role: his lines at FanDuel, DraftKings and Hard Rock against the model, how often he has cleared them, his offense vs the defense, snap share and game log.", None),
        ("/benefits/", "Who Benefits", "Injuries this week", "When a starter is ruled out: where his snaps, targets and carries went in the games he already missed, with each teammate's best-priced leg - books are often slow on the backup.", None),
        ("/usage/", "Usage Trends", "Rising and falling roles", "Whose snaps, targets and carries are growing or shrinking over the last three games, with the injury context that explains a fill-in bump or a dip from playing hurt.", None),
        ("/firsttd/", "First TD", f"{nftd} players" if nftd else f"Week {week}", "Who scores first in every game: the model's first-touchdown probability for every active skill player, the fair odds, and FanDuel's first touchdown scorer price with the edge.", None),
        ("/pairs/", "Either-or TDs", "Two names, one leg", "FanDuel sells \"A or B to score\" as one leg. Pick the two players and see the chance one of them scores, the fair price, and whether the pair is worth more or less than its two singles. Type FanDuel's price and it says what you are paying.", None),   # owner 11/8-11/10
        ("/teasers/", "Teaser Finder", "6, 6.5 and 7 points", "Every spread and total teased 6, 6.5 and 7 points, scored by the model: which teased legs clear your book's two-leg price, and the classic pairs that cross both 3 and 7.", None),
        ("/sweep/", "Sweep My Slip", "Before you place it", "Screenshot any FanDuel slip, yours or one somebody posted, and get a plain verdict: its chance against its price, the weakest leg, and a safer swap one tap applies. The picture is read on your phone and never leaves it.", None),   # owner 11/10
        ("/survivor/", "Survivor Planner", "Elimination pools", "One team a week, never the same team twice: mark who you have used and get the best pick this week and the best team for every week left, so you do not burn one you will need later. Works for any pool you are in.", None),   # owner 11/10
        ("/beat/", "Beat the Model", "Your five vs its five", "Pick five FanDuel player props for the week and go head to head with the model's five. Hits count, not odds; Tuesday grades everyone and the leaderboard keeps the season score.", None),
        ("/receipts/", "Receipts", (f"Week {latest} graded" if latest else "Coming Tuesday"), "What we said before kickoff and what happened. Every projection frozen before the games, graded after, biggest beats and busts included. Nothing is edited after the fact.", (f"/receipts/week{latest}/img/summary.png" if latest else None)),
        ("/season/", "Season to date", "Running record", "Projection error by position week by week and the FanDuel leg record, all from pre-kickoff snapshots.", "/season/img/summary.png"),
        ("/badbeats/", "Missed by one", (f"Week {latest} bad beats" if latest else "Bad beats"), "The week's most painful FanDuel misses: favorites that came up one catch or a few yards short, and our own promos that lost by a single leg.", None),   # owner 11/10 (badbeats.py); audit 11/10: the page had no link anywhere
        ("/guide/", "How to read BetSweep", "New here? Start here", "What every color, rank, percentage and chip on the site means: matchups, model % vs book %, edge, confidence grades, flags and the betslip.", None),
    ]
    # audit 11/10: a tile picture is used only when the file is in this build - /boards/img/summary.png and the latest receipt's
    # summary.png are no longer rendered, and the hard-coded paths showed as two broken images on the home page
    tiles = [(href, name, tag, desc, img if (img and os.path.exists(os.path.join(SITE, img.lstrip("/")))) else None) for href, name, tag, desc, img in tiles]
    tile_html = "".join(
        f'<a class="tile" href="{href}">' + (f'<img src="{img}" alt="" loading="lazy">' if img else '<div class="ph"><img class="bsph" src="/app/icon-192.png" alt="BetSweep"></div>') +
        f'<div class="tb"><small>{html.escape(tag)}</small><h2>{html.escape(name)}</h2><p>{html.escape(desc)}</p><b>Open →</b></div></a>'
        for href, name, tag, desc, img in tiles)
    legs_stat = f'<span><b>{nlegs:,}</b> FanDuel legs priced</span>' if nlegs else ''
    import home as HOME, live as LIVE
    home_html, home_js = HOME.sections(IN, OUT, latest)
    global LANDING_HOME_PARTS
    LANDING_HOME_PARTS = {"home_html": home_html, "home_js": home_js, "tiles": tile_html, "gal": GAL}
    return ('<title>BetSweep</title>\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:ital,wght@1,800&family=Barlow+Condensed:wght@500;600;700;800&family=IBM+Plex+Sans:wght@400;500;600&display=swap">\n'
            '<style>' + LANDING_CSS + HOME.HOME_CSS + LIVE.LIVE_CSS + f'.hero{{--banner:url("data:image/png;base64,{BANNER}")}}' + '</style>\n'
            '<section class="hero" role="img" aria-label="BetSweep - Picks. Data. Edge. Sweep."></section>\n'
            '<section class="pitch"><div class="card"><img class="mark" src="/favicon.png" alt="">\n'
            ' <h1>The model\'s picks, <span>graded against the sportsbooks</span> every week.</h1>\n'
            ' <p class="lede">Every NFL skill player projected, every FanDuel prop priced against it, and the receipts shown afterward. Boards land Thursday morning, refresh through Sunday\'s inactives and get graded Tuesday.</p>\n'
            f' <div class="stats"><span><b>Week {week}</b> on the board</span><span><b>{ngames}</b> games</span>{legs_stat}<span>updated {html.escape(stamp)} CT</span></div>\n'
            ' <div class="social"><a href="https://x.com/bet_sweep" target="_blank" rel="noopener">X <small>@bet_sweep</small></a><a href="https://www.instagram.com/bet_sweep" target="_blank" rel="noopener">Instagram <small>@bet_sweep</small></a></div>\n'
            '</div></section>\n'
            + home_html + '\n'
            '<section class="sec"><h2 class="t">Everything on BetSweep</h2><div class="tiles">' + tile_html + '</div></section>\n'
            '<section class="sec"><h2 class="t">Latest from @bet_sweep</h2><div class="feed"><div class="wrap">' + (GAL or
            '<a class="twitter-timeline" data-theme="dark" data-chrome="noheader nofooter noborders transparent" data-tweet-limit="3" data-dnt="true" href="https://twitter.com/bet_sweep?ref_src=twsrc%5Etfw">'
            '<p class="fallback">Recent posts from <a href="https://x.com/bet_sweep">@bet_sweep on X</a> \u2014 matchup cards, slips and receipts as they drop.</p></a>'
            '<script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>') + '<p class="fallback" style="margin-top:10px;font-size:12.5px">Follow <a href="https://x.com/bet_sweep">@bet_sweep on X</a> and <a href="https://www.instagram.com/bet_sweep">Instagram</a> for cards, slips and receipts as they drop.</p></div></div></section>\n'
            '<section class="sec"><h2 class="t">How it works</h2><div class="how">\n'
            ' <div><h3>Model first</h3><p>Projections come from usage, matchups, game script and injuries \u2014 the price is only used to find where FanDuel is off. Odds are never the input.</p></div>\n'
            ' <div><h3>Edge, not hype</h3><p>Every leg shows the model\'s hit rate next to what the price requires. The difference is the edge; +2 is value, +5 is strong. Nothing is called a lock.</p></div>\n'
            ' <div><h3>Frozen, then graded</h3><p>Projections and legs are snapshotted before kickoff and graded after. The receipts page is the scoreboard \u2014 including the misses.</p></div>\n'
            ' <div><h3>Built to bet from</h3><p>Fade lines, set a target payout, check a player\'s last five and the defense\'s, then send the slip to FanDuel in one tap.</p></div>\n'
            '</div></section>\n'
            '<footer><div class="tag">BetSweep™ · Picks. Data. Edge. <i>Sweep.</i></div><div class="social" style="margin:0 0 10px"><a href="https://x.com/bet_sweep" target="_blank" rel="noopener">X <small>@bet_sweep</small></a><a href="https://www.instagram.com/bet_sweep" target="_blank" rel="noopener">Instagram <small>@bet_sweep</small></a><a href="mailto:support@betsweep.co">Email <small>support@betsweep.co</small></a></div>Information and analysis only, not betting advice; no outcome is guaranteed. 21+ (18+ where permitted). If gambling is a problem for you or someone you know, call 1-800-GAMBLER. BetSweep is not affiliated with FanDuel or the NFL. Questions, corrections or a leg that graded wrong: <a href="mailto:support@betsweep.co" style="color:var(--ink)">support@betsweep.co</a>. BetSweep may earn a commission when you bet through links on this site; it never changes a pick or a grade. <span style="display:block;margin-top:8px">© 2026 BetSweep LLC. BetSweep™ is a trademark of BetSweep LLC (U.S. Serial No. 50169404). · <a href="/terms/" style="color:var(--ink)">Terms of Use</a> · <a href="/privacy/" style="color:var(--ink)">Privacy</a> · <a href="/responsible-gambling/" style="color:var(--ink)">Responsible gambling &amp; disclosures</a></span></footer>\n'
            '<script>' + LIVE.LIVE_JS + '</script>\n' + home_js + '\n')

# receipts index + 404 (audit 10/26): small standalone pages with the site's base styles - they used to reuse the whole boards page
# (838KB with the boards' slip data and betslip script for two links), the 404 still said "Receipts", and "This week's boards" pointed at /.
def _simple(title, inner):
    _link, _base = ACCT._base_css()
    return (f"<title>{html.escape(title)}</title>\n{_link}\n<style>{_base}"
            ".sp{max-width:760px;margin:22px auto 30px}.sp h1{font-family:var(--brand);font-style:italic;font-weight:800;font-size:32px;line-height:1;margin:0 0 8px;letter-spacing:-.01em}"
            ".sp p{color:var(--mute);line-height:1.5;margin:4px 0 14px}.sp .wk{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:12px 0 18px}"
            ".sp .wk a{display:block;padding:14px 16px;border:1px solid var(--line);border-radius:14px;background:var(--card);text-decoration:none;color:var(--ink)}.sp .wk a:hover{border-color:var(--red)}"
            ".sp .wk a b{display:block;font-family:var(--brand);font-style:italic;font-weight:800;font-size:24px;line-height:1;margin-bottom:6px}.sp .wk a small{color:var(--mute);font-size:13px}"
            ".sp .go{display:flex;flex-wrap:wrap;gap:8px}.sp .go a{display:inline-flex;align-items:center;min-height:38px;padding:0 14px;border-radius:8px;border:1.5px solid var(--line);color:var(--ink);text-decoration:none;font-family:var(--display);font-weight:700;font-size:13.5px;letter-spacing:.05em;text-transform:uppercase}.sp .go a:hover{border-color:var(--red)}"
            f"</style>\n<div class=\"sp\">{inner}</div>")
_prw = {}
try:
    _pv = json.load(open(os.path.join(HERE, "in", "promos.json")))["values"]; _ph = {c: i for i, c in enumerate(_pv[0])}
    for _r in _pv[1:]:
        _r = _r + [""] * (len(_pv[0]) - len(_r)); _res = str(_r[_ph["Result"]]).strip().lower()
        if _res not in ("hit", "cashed", "missed", "miss", "lost"): continue
        _w = int(float(_r[_ph["Week"]])); _d = _prw.setdefault(_w, [0, 0]); _d[0 if _res in ("hit", "cashed") else 1] += 1
except Exception: pass
_cards = "".join(f'<a href="/receipts/week{w}/"><b>Week {w}</b><small>{"posted slips " + str(_prw[w][0]) + "–" + str(_prw[w][1]) if w in _prw else "every leg graded"}</small></a>' for w in sorted(weeks, reverse=True)) or "<p>No receipts yet.</p>"
_rec = _simple("BetSweep Receipts", '<h1>Receipts</h1><p>Every week we freeze the model\'s legs and game calls before kickoff, then grade them against the box scores - hits and misses. Pick a week, or see the whole season.</p>'
               f'<div class="wk">{_cards}</div><div class="go"><a href="/season/">Season to date</a><a href="/boards/">This week\'s boards</a></div>')
os.makedirs(os.path.join(SITE, "receipts"), exist_ok=True)
open(os.path.join(SITE, "receipts", "index.html"), "w").write(wrap(_rec, "BetSweep Receipts", "Every weekly receipt: what the model said before kickoff and what happened.", "/receipts/", "/og.png"))
open(os.path.join(SITE, "index.html"), "w").write(wrap(landing(weeks), "BetSweep", "NFL projections priced against FanDuel, graded every week. Matchup boards, a parlay builder with FanDuel links, and receipts.", "/", "/og.png"))
_404 = _simple("Page not found · BetSweep", '<h1>Page not found</h1><p>That page moved or never existed. Try one of these:</p><div class="go"><a href="/">Home</a><a href="/boards/">Matchup boards</a><a href="/build/">Parlay builder</a><a href="/receipts/">Receipts</a></div>'
               # owner 10/31: names on the boards / builder link to /player/<slug>/; a player with no page this week (deep backup) or two players
               # sharing a name (their pages carry a -team suffix) land here - send them to the Players directory searched for that name
               '<script>(function(){var m=location.pathname.match(/^\\/player\\/([a-z0-9-]+)\\/?$/);if(m)location.replace("/player/?q="+encodeURIComponent(m[1].replace(/-/g," ")));})();</script>')
open(os.path.join(SITE, "404.html"), "w").write(wrap(_404, "BetSweep", "Page not found", "/404.html", "/og.png"))
# ---- 11/4 (owner: page weight): the masthead logo (128 KB) and banner (231 KB) were inlined as base64 into every page, 385 pages a build -
# 360 KB per page view that no cache could share. They are now files (/logo.png, /banner.jpg, cached once by the browser and the service
# worker) and every written page points at them. The data: URLs are replaced by exact string match, so nothing else in a page changes.
try:
    _bimg = base64.b64decode(BANNER); _bext = "jpg" if _bimg[:3] == b"\xff\xd8\xff" else "png"
    open(os.path.join(SITE, f"banner.{_bext}"), "wb").write(_bimg); open(os.path.join(SITE, "logo.png"), "wb").write(base64.b64decode(LOGO))
    if _bext != "jpg": open(os.path.join(SITE, "banner.jpg"), "wb").write(_bimg)   # the service-worker shell lists /banner.jpg; a 404 there would break the install
    _reps = [(f"data:image/jpeg;base64,{BANNER}", f"/banner.{_bext}"), (f"data:image/png;base64,{BANNER}", f"/banner.{_bext}"), (f"data:image/png;base64,{LOGO}", "/logo.png")]
    _np = _saved = 0
    for _d, _, _fs in os.walk(SITE):
        for _f in _fs:
            if not _f.endswith(".html"): continue
            _fp = os.path.join(_d, _f); _h = open(_fp, encoding="utf-8").read(); _h2 = _h
            for _a, _b in _reps: _h2 = _h2.replace(_a, _b)
            if _h2 != _h: open(_fp, "w", encoding="utf-8").write(_h2); _np += 1; _saved += len(_h) - len(_h2)
    print(f"inline images -> files: {_np} pages rewritten, {_saved/1e6:.1f} MB of base64 removed (/logo.png, /banner.{_bext})")
except Exception as _e: print("note: inline image pass skipped:", _e)
# 11/4 (owner: "one of the few apps on the phone during football season"): /today/ - the page the installed app opens to (build_today.py)
if os.path.exists(os.path.join(OUT, "today.html")):
    import home as _HOME, live as _LIVE
    _tb = open(os.path.join(OUT, "today.html")).read()
    _tb = _tb.replace("<style>", '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:ital,wght@1,800&family=Barlow+Condensed:wght@500;600;700;800&family=IBM+Plex+Sans:wght@400;500;600&display=swap">\n<style>' + LANDING_CSS + _HOME.HOME_CSS + _LIVE.LIVE_CSS, 1)   # the Today page reuses the landing/home CSS (sections, play cards) and the live score chips
    open(os.path.join(OUT, "today_wrapped.html"), "w").write(_tb)
    # owner 11/5: Today and Home are one page. "/" = Today's day view + the home page's week sections (promos, Model's Best, top plays, next man up,
    # floor legs, best parlay, slate) + the tiles / how-it-works; /today/ redirects to "/" so old links, the installed app and shared links still land.
    try:
        import landing_merge as _LM
        open(os.path.join(SITE, "index.html"), "w").write(wrap(_LM.merge(_tb, LANDING_HOME_PARTS), "BetSweep", "NFL projections priced against FanDuel, graded every week: today's games, the model's plays, promos, news and your slips in one scroll.", "/", "/og.png"))
        os.makedirs(os.path.join(SITE, "today"), exist_ok=True)
        open(os.path.join(SITE, "today", "index.html"), "w").write('<!doctype html><html><head><meta charset="utf-8"><title>BetSweep</title><link rel="canonical" href="/"><meta http-equiv="refresh" content="0;url=/">'
            '<script>location.replace("/" + location.search + location.hash)</script></head><body><a href="/">BetSweep</a></body></html>')
        print("home: Today merged into / (/today/ redirects)")
    except Exception as _e:
        print("WARN home merge failed, Today stays at /today/:", _e)
        made.append(place_plain(os.path.join(OUT, "today_wrapped.html"), os.path.join(SITE, "today"), "/today/"))
    try: shutil.copy(os.path.join(OUT, "today.json"), os.path.join(SITE, "b", "today.json")); print("wrote /b/today.json (morning briefs per game day)")
    except Exception as _e: print("note: /b/today.json not written:", _e)
# ---- 11/5 (out-of-the-box batch): /api/ - a plain page listing every public JSON the site serves, so anyone can build on the numbers ----
_API = [
    ("/b/plus.json", "This week's plus-money and touchdown-tier legs with the price at build time: {week, built, legs:[{pl, m, ln, o, p, tier, ...}]}.", "every rebuild"),
    ("/b/live-legs.json", "Every leg the live page tracks (the model's picks plus saved slips' legs) with the pregame chance; the live page re-prices them from the box score.", "every rebuild"),
    ("/b/players.json", "Player index for search: name, slug (the /player/<slug>/ page), team, position, opponent, whether he has props this week.", "every rebuild"),
    ("/b/today.json", "The morning briefs per game day: {week, briefs:{YYYY-MM-DD:{title, body, url, games}}, days}. Weather risks lead the body.", "every rebuild"),
    ("/b/pairs.json", "Either-or touchdown pairs: every player with an anytime-TD price (model chance, FanDuel price, chance under each game ending, risk score) and the best pairs with the chance that at least one scores. FanDuel's own either-or prices are not included.", "every rebuild"),
    ("/b/teasers.json", "The teaser finder: every spread and total teased 6, 6.5 and 7 points with the model's chance before and after the move, which cross 3 and 7, and the best pairs.", "every rebuild"),
    ("/b/beat.json", "Beat the model: the week's pool (every player prop priced -150 to +150, as [key, player, team, opp, game, market, line, odds, model chance, kickoff]) and the model's five keys.", "every rebuild"),
    ("/b/dossier.json", "Game previews: per game, the model script, weather / injury / news flags, situational spots (tested on 2006-2025), each offense's results against the most similar defenses and each defense's leaks by role.", "every rebuild"),
    ("/b/startsit.json", "Who-should-I-start inputs: {week, players:[{n, t, p, o, fp, av}]} - name, team, position, opponent, projected fantasy points, availability.", "every rebuild"),
    ("/b/books.json", "DraftKings / Hard Rock selection ids for the week's legs, keyed like the slip keys, for deep links.", "every rebuild"),
    ("/b/promos.json", "The promo desk's posted slips with their short links and grades.", "every rebuild"),
    ("/data/price-moves.json", "FanDuel price moves of 3+ points since the build on every tracked leg: {built, moves:[{key, pl, m, ln, from, to, pts, dir, tier, detail}]}.", "every 30 min (GitHub Action)"),
    ("/data/risk-notes.json", "Risk flags per player (questionable tags, weather, role changes) refreshed between builds.", "every 30 min (GitHub Action)"),
    ("/data/box-w<W>.json", "The graded box score per week: every tracked leg's final stat and hit / miss.", "Tuesday"),
    ("/data/close-w<W>.json", "Closing lines per slip key with the build price: {week, close:{key:{o, imp, at}}, build:{key:{o, p}}} - the CLV numbers on /me/.", "Tuesday"),
    ("/data/graded-w<W>.json", "Hit / miss per slip key for the week, the input to Beat the model grading.", "Tuesday"),
    ("/data/weeks.json", "Which weeks have box scores and receipts.", "Tuesday"),
    ("/team/compare/data.json", "The same projections the start/sit page uses (alias of /b/startsit.json).", "every rebuild"),
]
_feeds = [("injuries.json", "Official injury report rows (nflverse), refreshed every 10 minutes on the feeds branch."), ("inactives.json", "Game-day inactives as they post."), ("scoreboard.json", "Live scores and clock per game."),
          ("weather.json", "Kickoff-hour forecast per game: wind, precipitation chance and type, temperature, risk."), ("depthcharts.json", "ESPN depth charts per team."), ("news.json", "The news desk's tagged items."), ("projections.json", "The sheet's current projections snapshot.")]
_rows = "".join(f'<tr><td><code>{html.escape(p)}</code></td><td>{html.escape(d)}</td><td class="r">{html.escape(f)}</td></tr>' for p, d, f in _API)
_frows = "".join(f'<tr><td><code>https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/{html.escape(n)}</code></td><td>{html.escape(d)}</td><td class="r">every 10 min</td></tr>' for n, d in _feeds)
_api_body = f'''<title>API · BetSweep</title>
<meta name="description" content="Every public JSON BetSweep serves: this week's priced legs, live legs, price moves, closing lines, box scores, teasers and the live feeds - free to read, no key.">
<style>.api{{max-width:1100px;margin:16px auto 40px;padding:0 16px}} .api h1{{font-family:var(--brand);font-style:italic;font-weight:800;font-size:32px;margin:0 0 8px}} .api p{{color:var(--mute);line-height:1.5;max-width:76ch}} .api table{{width:100%;border-collapse:collapse;font-size:14px;margin:10px 0 22px}} .api th,.api td{{padding:8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}} .api th.r,.api td.r{{text-align:right;white-space:nowrap;color:var(--mute)}} .api thead th{{font-family:var(--display);font-weight:700;font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute)}} .api code{{font-size:12.5px;background:var(--chalk);padding:2px 6px;border-radius:6px;word-break:break-all}} .api h2{{font-family:var(--display);font-weight:700;font-size:20px;margin:18px 0 4px}}</style>
<main class="api">
<h1>API</h1>
<p>Everything on this site is built from JSON the site also serves. Read it from anything - a spreadsheet, a bot, your own page. No key, no sign-up; same-origin and cross-origin GETs both work. Numbers are the model's, prices are FanDuel's at build time unless the file says otherwise. Please cache for a few minutes and credit betsweep.co. Not betting advice.</p>
<h2>Site JSON</h2>
<table><thead><tr><th>URL</th><th>What it holds</th><th class="r">Refreshed</th></tr></thead><tbody>{_rows}</tbody></table>
<h2>Live feeds</h2>
<p>The feeds live on the <code>feeds</code> branch of the public repo and refresh every ten minutes during the season.</p>
<table><thead><tr><th>URL</th><th>What it holds</th><th class="r">Refreshed</th></tr></thead><tbody>{_frows}</tbody></table>
<h2>Keys</h2>
<p>A slip key is <code>Player|Market|Line</code> with the line rounded to an integer the way JavaScript's <code>Math.round</code> does it (<code>Josh Allen|Passing Yds|250</code>); the same key appears in price moves, closing lines, box scores and saved slips, so the files join on it.</p>
<p>Ideas, bugs, something you built: <a href="/social/" style="color:var(--ink)">post it on Social</a>.</p>
</main>
'''
os.makedirs(os.path.join(SITE, "api"), exist_ok=True); open(os.path.join(SITE, "api", "index.html"), "w").write(wrap(_api_body, "API · BetSweep", "Every public JSON BetSweep serves, free to read.", "/api/", "/og.png")); print("wrote /api/")
# ---- audit 11/10: /how/ ("How BetSweep picks") was a hand-stitched page in the site repo carrying a frozen copy of an old shell (old header and
# menu, the Builder tab lit, Google Fonts). Its text lives in how_body.html here now (a <style> block, then the body) and is wrapped like
# every other plain page, so the header, menu and tabs follow the site. Edit the wording in how_body.html.
_how_src_path = os.path.join(HERE, "how_body.html")
if os.path.exists(_how_src_path):
    try:
        _how_src = open(_how_src_path).read(); _how_m = re.match(r"\s*<style>(.*?)</style>\s*", _how_src, re.S)
        _how_link, _how_base = ACCT._base_css()
        _how_desc = "How the BetSweep model prices FanDuel props, what the graded weeks showed, and how we build the slips we post."
        _how_page = wrap(f"<title>How BetSweep picks</title>\n{_how_link}\n<style>{_how_base}\n{_how_m.group(1) if _how_m else ''}</style>\n" + (_how_src[_how_m.end():] if _how_m else _how_src), "How BetSweep picks", _how_desc, "/how/", "/og.png")
        os.makedirs(os.path.join(SITE, "how"), exist_ok=True)   # written only once wrap() has succeeded: a failure leaves the repo's copy alone
        open(os.path.join(SITE, "how", "index.html"), "w").write(_how_page); shutil.copy(_how_src_path, os.path.join(SITE, "how", "body.html"))
        made.append("How BetSweep picks")
    except Exception as _e: print("WARN /how/ not rebuilt (the repo copy stays):", _e)
# ---- owner 10/30: sitemap.xml + robots.txt so search engines find every page (the 375-odd player pages above all). Every index.html
# this build wrote, except the account page, short-link pages and the 404; receipts the clone already holds are added from in/archive.json weeks.
_today = _dt.date.today().isoformat(); _urls = []
for _d, _, _fs in os.walk(SITE):
    if "index.html" not in _fs: continue
    _rel = os.path.relpath(_d, SITE).replace(os.sep, "/"); _path = "/" if _rel == "." else f"/{_rel}/"
    if _path.startswith(("/me/", "/b/", "/fantasy/", "/p/", "/promo/", "/app/", "/data/")): continue
    try:
        if 'http-equiv="refresh"' in open(os.path.join(_d, "index.html"), encoding="utf-8", errors="ignore").read(600): continue   # audit 11/10: forwarding stubs (/today/, old player addresses) are not pages
    except Exception: pass
    _urls.append(_path)
for _w in weeks:
    if f"/receipts/week{_w}/" not in _urls: _urls.append(f"/receipts/week{_w}/")
if "/how/" not in _urls: _urls.append("/how/")   # 11/4: static page in the repo (how/index.html), not built here
_pri = lambda u: "1.0" if u == "/" else ("0.9" if u in ("/boards/", "/build/", "/player/") else ("0.6" if u.startswith("/player/") else "0.7"))
_freq = lambda u: "monthly" if u.startswith(("/receipts/week", "/terms/", "/privacy/", "/responsible-gambling/", "/guide/", "/how/")) else "daily"
open(os.path.join(SITE, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join(f"<url><loc>{BASE}{html.escape(u)}</loc><lastmod>{_today}</lastmod><changefreq>{_freq(u)}</changefreq><priority>{_pri(u)}</priority></url>\n" for u in sorted(set(_urls)))
    + "</urlset>\n")
open(os.path.join(SITE, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nDisallow: /me/\nSitemap: {BASE}/sitemap.xml\n")
print(f"sitemap: {len(set(_urls))} urls")
n = sum(len(fs) for _, _, fs in os.walk(SITE)); mb = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(SITE) for f in fs) / 1e6
print(f"site: {n} files, {mb:.1f} MB -> {SITE}; pages: {made}; receipts: {weeks}")
