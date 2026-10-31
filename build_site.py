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
            "shortcuts": [{"name": "Live", "url": "/live/", "icons": [{"src": "/app/icon-192.png", "sizes": "192x192"}]}, {"name": "Parlay Builder", "url": "/build/"}, {"name": "Matchup Boards", "url": "/boards/"}],
            "categories": ["sports"]}
open(os.path.join(SITE, "manifest.webmanifest"), "w").write(json.dumps(MANIFEST, indent=1))
SW_VERSION = _dt.datetime.now(__import__("zoneinfo").ZoneInfo("America/Chicago")).strftime("%Y%m%d%H%M") if "_dt" in globals() else __import__("datetime").datetime.now().strftime("%Y%m%d%H%M")
SW = r'''// BetSweep service worker: app shell cached for instant open; pages are network-first so the data is always this build's,
// with the last good copy served when the connection drops (stadium wifi). Version: __V__
var V = 'bs-__V__', SHELL = ['/', '/boards/', '/build/', '/live/', '/social/', '/team/', '/firsttd/', '/dfs/', '/receipts/', '/season/', '/player/', '/usage/', '/benefits/', '/guide/', '/offline.html', '/wordmark.png', '/wordmark-ink.png', '/favicon.png', '/app/icon-192.png'];
self.addEventListener('install', function(e){ e.waitUntil(caches.open(V).then(function(c){ return Promise.all(SHELL.map(function(u){ return c.add(u).catch(function(){}); })); }).then(function(){ return self.skipWaiting(); })); });
self.addEventListener('activate', function(e){ e.waitUntil(caches.keys().then(function(ks){ return Promise.all(ks.filter(function(k){ return k !== V; }).map(function(k){ return caches.delete(k); })); }).then(function(){ return self.clients.claim(); })); });
self.addEventListener('fetch', function(e){
  var req = e.request; if(req.method !== 'GET') return;
  var url = new URL(req.url);
  if(url.origin !== location.origin) return;   // ESPN, fonts, FanDuel links: straight to the network
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
open(os.path.join(SITE, "offline.html"), "w").write('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BetSweep · offline</title><style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#141a24;color:#f1e8d8;font-family:"IBM Plex Sans",system-ui,sans-serif;text-align:center;padding:24px}img{width:260px;max-width:80vw}p{color:#a9a294;line-height:1.5}a{color:#f1e8d8}</style></head><body><div><img src="/wordmark.png" alt="BetSweep"><p>You are offline and this page was not saved yet.<br>The pages you opened before are still available from the menu.</p><p><a href="/">Try again</a></p></div></body></html>')

open(os.path.join(SITE, ".nojekyll"), "w").write("")

NAV_ITEMS = [("/", "Home"), ("/boards/", "Matchup Boards"), ("/build/", "Parlay Builder"), ("/player/", "Players"), ("/live/", "Live"), ("/social/", "Social"), ("/team/", "Fantasy"), ("/usage/", "Usage"), ("/trade/", "Trade"), ("/firsttd/", "First TD"), ("/dfs/", "DFS"), ("/receipts/", "Receipts"), ("/season/", "Season")]
NAV_CSS = """<style>""" + ACCT.ACCOUNT_CSS + BIGGER_CSS + """
.sitenav{position:sticky;top:0;z-index:60;margin-left:calc(-1 * var(--bs-inset,0px));margin-right:calc(-1 * var(--bs-inset,0px));margin-top:calc(-1 * var(--bs-top,0px));padding-top:env(safe-area-inset-top,0px);background:#efe9da;border-bottom:3px solid #d7332a;font-family:'Barlow Condensed','IBM Plex Sans',system-ui,sans-serif;box-shadow:0 2px 14px rgba(0,0,0,.25)}
.sitenav .in{max-width:1360px;margin:0 auto;padding:0 16px;display:flex;align-items:center;gap:14px;min-height:50px}
.sitenav .brand{display:inline-flex;align-items:center;text-decoration:none;padding:7px 0}
.sitenav .brand img{height:32px;width:auto;display:block}
.sitenav .brand img.cream{display:none}
.sitenav .tabs{display:flex;gap:4px;margin-left:auto;align-items:center;padding:0;border:0;background:none}
.sitenav .tabs a{color:#4a5260;text-decoration:none;font-weight:700;font-size:15px;letter-spacing:.05em;text-transform:uppercase;padding:14px 10px 11px;border-bottom:3px solid transparent;margin-bottom:-3px}
.sitenav .tabs a:hover{color:#141a24}
.sitenav .tabs a.on{color:#141a24;border-bottom-color:#d7332a}
@media (max-width:1180px){ .sitenav .tabs{gap:0} .sitenav .tabs a{font-size:13.5px;padding:14px 7px 11px;letter-spacing:.04em} }
/* 10/30: Players + Usage made 13 tabs - tighter between 1100 and 1420, the menu button below 1100 */
@media (max-width:1700px){ .sitenav .tabs{gap:0} .sitenav .tabs a{font-size:13px;padding:14px 5px 11px;letter-spacing:.03em} }
@media (min-width:1101px){ .sitenav .brand,.sitenav .acct{flex:none} .sitenav .tabs{min-width:0;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;align-self:stretch} .sitenav .tabs::-webkit-scrollbar{display:none} .sitenav .tabs a{margin-bottom:0;white-space:nowrap;display:flex;align-items:center} }
.sitenav .menu{display:none;margin-left:auto;font:inherit;font-weight:700;font-size:14px;letter-spacing:.06em;text-transform:uppercase;color:#141a24;background:none;border:1.5px solid #141a24;border-radius:4px;padding:6px 10px;cursor:pointer}
@media (max-width:1100px){
  .sitenav .menu{display:inline-flex;align-items:center;gap:6px}
  .sitenav .tabs{display:none;position:absolute;left:0;right:0;top:100%;flex-direction:column;align-items:stretch;gap:0;padding:0;background:#efe9da;border-bottom:3px solid #d7332a;box-shadow:0 12px 30px rgba(0,0,0,.35)}
  .sitenav.open .tabs{display:flex}
  .sitenav .tabs a{display:block;text-align:left;padding:13px 18px;border-bottom:1px solid #d9d1bf;font-size:17px;margin-bottom:0}
  .sitenav .tabs a.on{border-left:4px solid #d7332a;border-bottom-color:#d9d1bf}
  .top{top:calc(50px + env(safe-area-inset-top,0px))}
}
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
</style>
"""
APP_TABS = [("/boards/", "Boards", '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 10v10"/></svg>'),
            ("/build/", "Build", '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/><circle cx="12" cy="12" r="9"/></svg>'),
            ("/live/", "Live", '<svg viewBox="0 0 24 24"><path d="M4 12h3l2-6 4 12 2-6h5"/></svg>'),
            ("/social/", "Social", '<svg viewBox="0 0 24 24"><path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/></svg>'),
            ("/team/", "Fantasy", '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>'),
            ("/receipts/", "Receipts", '<svg viewBox="0 0 24 24"><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/></svg>')]
def apptabs(path):
    def on(p): return path == p or (p != "/" and path.startswith(p)) or (p == "/receipts/" and path.startswith("/season/"))
    return '<nav class="apptabs" aria-label="app tabs">' + "".join(f'<a href="{p}" class="{"on" if on(p) else ""}">{svg}<span>{t}</span></a>' for p, t, svg in APP_TABS) + '</nav>\n'
APP_JS = """<script>
(function(){
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
</script>"""
INSTALL_BAR = '<div class="installbar" id="installbar"><b>App</b><span class="msg"></span><button type="button" class="go" hidden>Install</button><button type="button" class="x" aria-label="dismiss">×</button></div>'
def sitenav(path):
    def on(p): return path == p or (p != "/" and path.startswith(p))
    tabs = "".join(f'<a href="{p}" class="{"on" if on(p) else ""}">{t}</a>' for p, t in NAV_ITEMS)
    return (f'<nav class="sitenav" id="sitenav"><div class="in"><a class="brand" href="/" aria-label="BetSweep home"><img class="cream" src="/wordmark.png" alt="BetSweep"><img class="ink" src="/wordmark-ink.png" alt="BetSweep"></a>'
            f'<button class="menu" type="button" aria-expanded="false" onclick="var n=document.getElementById(\'sitenav\');n.classList.toggle(\'open\');this.setAttribute(\'aria-expanded\',n.classList.contains(\'open\'))">Menu <span aria-hidden="true">☰</span></button>'
            f'<div class="acct" id="bsacct"></div><div class="tabs">{tabs}</div></div></nav>\n'
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
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"><meta name="apple-mobile-web-app-title" content="BetSweep">
<link rel="canonical" href="{BASE}{path}">
<meta property="og:type" content="website"><meta property="og:site_name" content="BetSweep">
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{BASE}{path}"><meta property="og:image" content="{BASE}{og_img}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{html.escape(desc)}"><meta name="twitter:image" content="{BASE}{og_img}">
<script>window.__BS_ACCOUNT={{url:"{ACCT.SUPABASE_URL}",key:"{ACCT.SUPABASE_ANON}",google:{"true" if ACCT.GOOGLE else "false"}}};</script>
<script defer src="{ACCT.SUPABASE_JS}"></script><script defer src="/account.js"></script>
'''
    # the built page starts with <title>; everything up to </style>... is head material, the rest is body
    m = re.search(r"</style>\s*", body)
    headpart, rest = body[:m.end()], body[m.end():]
    foot = '' if path == "/" else '<p style="max-width:1360px;margin:10px auto 40px;padding:0 16px;color:var(--mute);font-size:12px;line-height:1.5">Information and analysis only, not betting advice; no outcome is guaranteed. 21+ (18+ where permitted). Problem gambling help: 1-800-GAMBLER. BetSweep is not affiliated with FanDuel or the NFL. Follow <a href="https://x.com/bet_sweep" style="color:var(--ink)">@bet_sweep on X</a> and <a href="https://www.instagram.com/bet_sweep" style="color:var(--ink)">Instagram</a>. Questions, corrections or a leg that graded wrong: <a href="mailto:support@betsweep.co" style="color:var(--ink)">support@betsweep.co</a>. BetSweep may earn a commission when you bet through links on this site; it never changes a pick or a grade (<a href="/responsible-gambling/" style="color:var(--ink)">disclosures</a>). © 2026 BetSweep LLC. BetSweep™ is a trademark of BetSweep LLC (U.S. Serial No. 50169404). · <a href="/guide/" style="color:var(--ink)">How to read BetSweep</a> · <a href="/terms/" style="color:var(--ink)">Terms</a> · <a href="/privacy/" style="color:var(--ink)">Privacy</a> · <a href="/responsible-gambling/" style="color:var(--ink)">Responsible gambling</a>.</p>'
    return head + headpart + NAV_CSS + "</head>\n<body>\n" + sitenav(path) + (INSTALL_BAR if path == "/" else "") + rest + foot + apptabs(path) + APP_JS + "\n</body>\n</html>\n"

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
_PD = os.path.join(OUT, "players")
if os.path.isdir(_PD) and os.path.exists(os.path.join(_PD, "index.html")):
    _np = 0
    for _f in sorted(os.listdir(_PD)):
        if not _f.endswith(".html") or _f == "index.html": continue
        _slug = _f[:-5]; place_plain(os.path.join(_PD, _f), os.path.join(SITE, "player", _slug), f"/player/{_slug}/"); _np += 1
    made.append(place_plain(os.path.join(_PD, "index.html"), os.path.join(SITE, "player"), "/player/"))
    for _f in ("player.css", "player.js"): shutil.copy(os.path.join(_PD, _f), os.path.join(SITE, "player", _f))
    print(f"player pages: {_np}")
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
_bll, _blb = ACCT._base_css()
def _blpage(inner): return f"<title>BetSweep</title>\n{_bll}\n<style>{_blb}{SL.CSS}</style>\n{inner}"
os.makedirs(os.path.join(SITE, "b"), exist_ok=True)
SHORT_LINKS = []
for _pr in _promos:
    if (_pr.get("checks") or {}).get("block"): continue
    _code = SL.promo_code(_pr); _d = os.path.join(SITE, "b", _code); os.makedirs(_d, exist_ok=True)
    _sq = os.path.join(OUT, "promo", f'{_pr["week"]}-{_pr["slot"]}-square.png'); _og = "/og.png"
    if os.path.exists(_sq): shutil.copy(_sq, os.path.join(_d, "card.png")); _og = f"/b/{_code}/card.png"
    _desc = f'{len(_pr["legs"])}-leg parlay · FanDuel {SL.odds_str(_pr["fd"]) if _pr.get("fd") else ""} · ' + " / ".join(l["who"] for l in _pr["legs"][:6]) + (" …" if len(_pr["legs"]) > 6 else "")
    open(os.path.join(_d, "index.html"), "w").write(wrap(_blpage(SL.promo_page(_pr)), f'{_pr["title"]} · BetSweep', _desc, f"/b/{_code}/", _og))
    SHORT_LINKS.append(SL.promo_url(_pr))
try: _bweek = int(json.load(open(os.path.join(OUT, "builder_data.json")))["week"])
except Exception: _bweek = ""
open(os.path.join(SITE, "b", "index.html"), "w").write(wrap(_blpage(SL.index_page(_promos, _bweek)), "BetSweep bet links", "Short links for every bet BetSweep posts: the legs, the model's number and one tap to FanDuel.", "/b/", "/og.png"))
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
        if len(r) >= 3 and str(r[0]).strip() and "claude.ai/artifact/" in str(r[2]): weeks.append(int(float(r[0])))
except Exception: pass
weeks = sorted(set(weeks))

# ---- landing page ----
LANDING_CSS = """

:root{--bg:#0f141c;--card:#161d28;--chalk:#1d2633;--ink:#efe9da;--mute:#9aa3b2;--line:#2b3442;--red:#d7332a;--good:#5fcf93;--brand:'Barlow','Barlow Condensed',sans-serif;--display:'Barlow Condensed','IBM Plex Sans',sans-serif;--body:'IBM Plex Sans',system-ui,sans-serif;--plays:url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22360%22%20height%3D%22130%22%20viewBox%3D%220%200%20360%20130%22%20fill%3D%22none%22%20stroke%3D%22rgba%28239%2C233%2C218%2C0.16%29%22%20stroke-width%3D%221.6%22%20stroke-linecap%3D%22round%22%3E%0A%3Cpath%20d%3D%22M24%2018l10%2010m0-10l-10%2010M62%2088l10%2010m0-10l-10%2010M150%2020l10%2010m0-10l-10%2010M232%2096l10%2010m0-10l-10%2010M306%2026l10%2010m0-10l-10%2010M330%20100l10%2010m0-10l-10%2010M118%20112l10%2010m0-10l-10%2010%22%2F%3E%0A%3Ccircle%20cx%3D%2252%22%20cy%3D%2248%22%20r%3D%226%22%2F%3E%3Ccircle%20cx%3D%22192%22%20cy%3D%2266%22%20r%3D%226%22%2F%3E%3Ccircle%20cx%3D%22280%22%20cy%3D%2260%22%20r%3D%226%22%2F%3E%3Ccircle%20cx%3D%2296%22%20cy%3D%2226%22%20r%3D%226%22%2F%3E%3Ccircle%20cx%3D%22258%22%20cy%3D%22118%22%20r%3D%226%22%2F%3E%0A%3Cpath%20d%3D%22M52%2042C62%2022%2086%2020%20108%2016%22%20stroke-dasharray%3D%224%204%22%2F%3E%3Cpath%20d%3D%22M100%2013l9%202-5%208%22%2F%3E%0A%3Cpath%20d%3D%22M192%2060C206%2044%20222%2040%20238%2030%22%2F%3E%3Cpath%20d%3D%22M231%2027l9%202-5%208%22%2F%3E%0A%3Cpath%20d%3D%22M280%2066C270%2084%20256%2092%20240%20100%22%20stroke-dasharray%3D%224%204%22%2F%3E%3Cpath%20d%3D%22M247%2092l-8%207%2010%202%22%2F%3E%0A%3Cpath%20d%3D%22M96%2032C104%2050%20120%2060%20140%2066%22%2F%3E%3Cpath%20d%3D%22M132%2068l9-1-3-9%22%2F%3E%0A%3C%2Fsvg%3E");color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg) var(--plays) center/360px 130px repeat;color:var(--ink);font-family:var(--body);-webkit-font-smoothing:antialiased}
.hero{position:relative;width:100%;aspect-ratio:1600/595;min-height:300px;background:#0b0f15 var(--banner) center/cover no-repeat;border-bottom:1px solid var(--line)}
.hero::after{content:"";position:absolute;inset:auto 0 0 0;height:38%;background:linear-gradient(180deg,transparent,var(--bg))}
.pitch{position:relative;max-width:1360px;margin:-40px auto 0;padding:0 16px}
.pitch .card{position:relative;overflow:hidden;background:color-mix(in srgb,var(--card) 92%,transparent);border:1px solid var(--line);border-radius:12px;padding:26px 24px 22px;backdrop-filter:blur(6px)}
.pitch .card .mark{position:absolute;top:18px;right:20px;width:84px;height:84px;border-radius:50%;box-shadow:0 6px 18px rgba(0,0,0,.45);transform:rotate(-8deg)}
.pitch h1{font-family:var(--brand);font-style:italic;font-weight:800;font-size:clamp(28px,4.6vw,44px);letter-spacing:-.02em;margin:0 0 8px;line-height:1.12;max-width:900px;padding-right:100px}
.pitch h1 span{text-decoration:underline;text-decoration-color:var(--red);text-decoration-thickness:3px;text-underline-offset:5px}
.pitch p.lede{font-size:clamp(15px,1.8vw,17px);line-height:1.55;color:var(--mute);max-width:760px;margin:0 0 14px}
.stats{display:flex;flex-wrap:wrap;gap:8px 22px;font-family:var(--display);font-weight:600;letter-spacing:.06em;text-transform:uppercase;font-size:12.5px;color:var(--mute);margin:0 0 6px}
.stats b{color:var(--ink);font-size:16px;margin-right:4px}
.social{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 4px}
.social a{display:inline-flex;align-items:center;gap:6px;text-decoration:none;color:var(--ink);font-family:var(--display);font-weight:700;font-size:13.5px;letter-spacing:.06em;text-transform:uppercase;border:1px solid var(--line);border-radius:99px;padding:7px 14px;background:var(--chalk)}
.social a:hover{border-color:var(--red)}
.social a small{font-family:var(--body);font-weight:500;text-transform:none;letter-spacing:0;color:var(--mute)}
.sec{max-width:1360px;margin:30px auto 0;padding:0 16px}
.sec h2.t{font-family:var(--display);font-weight:700;letter-spacing:.14em;text-transform:uppercase;font-size:13px;color:var(--mute);margin:0 0 12px;display:flex;align-items:center;gap:12px}
.sec h2.t::after{content:"";flex:1;height:2px;background:linear-gradient(90deg,var(--red),transparent)}
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
        ("/receipts/", "Receipts", (f"Week {latest} graded" if latest else "Coming Tuesday"), "What we said before kickoff and what happened. Every projection frozen before the games, graded after, biggest beats and busts included. Nothing is edited after the fact.", (f"/receipts/week{latest}/img/summary.png" if latest else None)),
        ("/season/", "Season to date", "Running record", "Projection error by position week by week and the FanDuel leg record, all from pre-kickoff snapshots.", "/season/img/summary.png"),
        ("/guide/", "How to read BetSweep", "New here? Start here", "What every color, rank, percentage and chip on the site means: matchups, model % vs book %, edge, confidence grades, flags and the betslip.", None),
    ]
    tile_html = "".join(
        f'<a class="tile" href="{href}">' + (f'<img src="{img}" alt="" loading="lazy">' if img else '<div class="ph"><img class="bsph" src="/app/icon-192.png" alt="BetSweep"></div>') +
        f'<div class="tb"><small>{html.escape(tag)}</small><h2>{html.escape(name)}</h2><p>{html.escape(desc)}</p><b>Open →</b></div></a>'
        for href, name, tag, desc, img in tiles)
    legs_stat = f'<span><b>{nlegs:,}</b> FanDuel legs priced</span>' if nlegs else ''
    import home as HOME, live as LIVE
    home_html, home_js = HOME.sections(IN, OUT, latest)
    return ('<title>BetSweep</title>\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:ital,wght@1,800&family=Barlow+Condensed:wght@500;600;700;800&family=IBM+Plex+Sans:wght@400;500;600&display=swap">\n'
            '<style>' + LANDING_CSS + HOME.HOME_CSS + LIVE.LIVE_CSS + f'.hero{{--banner:url("data:image/png;base64,{BANNER}")}}' + '</style>\n'
            '<section class="hero" role="img" aria-label="BetSweep - Picks. Data. Edge. Sweep."></section>\n'
            '<section class="pitch"><div class="card"><img class="mark" src="/favicon.png" alt="">\n'
            ' <h1>The model\'s picks, <span>graded against the sportsbooks</span> every week.</h1>\n'
            ' <p class="lede">BetSweep projects every NFL skill player, prices every FanDuel prop against those projections, and shows you the receipts afterward. Boards land Thursday morning, refresh through Sunday\'s inactives, and get graded Tuesday.</p>\n'
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
            ".sp{max-width:760px;margin:22px auto 30px}.sp h1{font-family:var(--display);font-size:30px;margin:0 0 6px;letter-spacing:.02em}"
            ".sp p{color:var(--mute);line-height:1.5;margin:4px 0 14px}.sp .wk{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:12px 0 18px}"
            ".sp .wk a{display:block;padding:14px;border:1px solid var(--line);border-radius:10px;background:var(--card);text-decoration:none;color:var(--ink)}"
            ".sp .wk a b{display:block;font-family:var(--display);font-size:22px}.sp .wk a small{color:var(--mute)}"
            ".sp .go{display:flex;flex-wrap:wrap;gap:10px}.sp .go a{padding:10px 14px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);text-decoration:none;font-weight:600}"
            f"</style>\n<div class=\"sp\">{inner}</div>")
_prw = {}
try:
    _pv = json.load(open(os.path.join(HERE, "in", "promos.json")))["values"]; _ph = {c: i for i, c in enumerate(_pv[0])}
    for _r in _pv[1:]:
        _r = _r + [""] * (len(_pv[0]) - len(_r)); _res = str(_r[_ph["Result"]]).strip().lower()
        if _res not in ("hit", "cashed", "missed", "miss", "lost"): continue
        _w = int(float(_r[_ph["Week"]])); _d = _prw.setdefault(_w, [0, 0]); _d[0 if _res in ("hit", "cashed") else 1] += 1
except Exception: pass
_cards = "".join(f'<a href="/receipts/week{w}/"><b>Week {w}</b><small>{"promoted bets " + str(_prw[w][0]) + "–" + str(_prw[w][1]) if w in _prw else "every leg graded"}</small></a>' for w in sorted(weeks, reverse=True)) or "<p>No receipts yet.</p>"
_rec = _simple("BetSweep Receipts", '<h1>Receipts</h1><p>Every week we freeze the model\'s legs and game calls before kickoff, then grade them against the box scores - hits and misses. Pick a week, or see the whole season.</p>'
               f'<div class="wk">{_cards}</div><div class="go"><a href="/season/">Season to date →</a><a href="/boards/">This week\'s boards →</a></div>')
os.makedirs(os.path.join(SITE, "receipts"), exist_ok=True)
open(os.path.join(SITE, "receipts", "index.html"), "w").write(wrap(_rec, "BetSweep Receipts", "Every weekly receipt: what the model said before kickoff and what happened.", "/receipts/", "/og.png"))
open(os.path.join(SITE, "index.html"), "w").write(wrap(landing(weeks), "BetSweep", "NFL projections priced against FanDuel, graded every week. Matchup boards, a parlay builder with FanDuel links, and receipts.", "/", "/og.png"))
_404 = _simple("Page not found · BetSweep", '<h1>Page not found</h1><p>That page moved or never existed. Try one of these:</p><div class="go"><a href="/">Home</a><a href="/boards/">Matchup boards</a><a href="/build/">Parlay builder</a><a href="/receipts/">Receipts</a></div>')
open(os.path.join(SITE, "404.html"), "w").write(wrap(_404, "BetSweep", "Page not found", "/404.html", "/og.png"))
# ---- owner 10/30: sitemap.xml + robots.txt so search engines find every page (the 375-odd player pages above all). Every index.html
# this build wrote, except the account page, short-link pages and the 404; receipts the clone already holds are added from in/archive.json weeks.
_today = _dt.date.today().isoformat(); _urls = []
for _d, _, _fs in os.walk(SITE):
    if "index.html" not in _fs: continue
    _rel = os.path.relpath(_d, SITE).replace(os.sep, "/"); _path = "/" if _rel == "." else f"/{_rel}/"
    if _path.startswith(("/me/", "/b/", "/fantasy/", "/p/", "/promo/", "/app/", "/data/")): continue
    _urls.append(_path)
for _w in weeks:
    if f"/receipts/week{_w}/" not in _urls: _urls.append(f"/receipts/week{_w}/")
_pri = lambda u: "1.0" if u == "/" else ("0.9" if u in ("/boards/", "/build/", "/player/") else ("0.6" if u.startswith("/player/") else "0.7"))
_freq = lambda u: "monthly" if u.startswith(("/receipts/week", "/terms/", "/privacy/", "/responsible-gambling/", "/guide/")) else "daily"
open(os.path.join(SITE, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "".join(f"<url><loc>{BASE}{html.escape(u)}</loc><lastmod>{_today}</lastmod><changefreq>{_freq(u)}</changefreq><priority>{_pri(u)}</priority></url>\n" for u in sorted(set(_urls)))
    + "</urlset>\n")
open(os.path.join(SITE, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nDisallow: /me/\nSitemap: {BASE}/sitemap.xml\n")
print(f"sitemap: {len(set(_urls))} urls")
n = sum(len(fs) for _, _, fs in os.walk(SITE)); mb = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(SITE) for f in fs) / 1e6
print(f"site: {n} files, {mb:.1f} MB -> {SITE}; pages: {made}; receipts: {weeks}")
