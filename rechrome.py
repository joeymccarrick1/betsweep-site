"""rechrome.py - every page with the site menu carries THIS build's menu.

Why (11/11). The owner asked for Ask BetSweep "on the menu of every page". A build wraps the pages it makes; a page it does not make
keeps the menu of the day it was last built: the weekly receipts (made on Tuesdays), /season/ (made when a week is graded) and the
landing pages of earlier weeks' short links. On 11/11 that was 26 live pages on three generations of menu - /receipts/week6/ still had
October's flat ten-tab row, and /season/ had missed the regrouped menu of the night before.

refresh() runs at the end of build_site.py. It looks at every page that will be live after the copy into the clone - the build's copy
when it made one, otherwise the clone's - and, where a page has the site menu but not this build's, writes a copy into ./site with only
the shared furniture replaced:

  the menu block and the small scripts wrap() puts after it            -> sitenav(path)
  the shared stylesheet link (before 11/5: the inline menu styles)      -> this build's /s/site-<hash>.css
  the shared script link (before 11/5: the inline app script)           -> this build's /s/app-<hash>.js
  the bottom tab bar                                                    -> apptabs(path)
  "Where to next", when the page has none and NEXT has doors for it      -> next_strip(path)

Nothing else is touched: the page's own content, styles, data and scripts stay byte for byte. A page whose furniture cannot be found is
left alone and named in the log. The copy step (reprice.copy_into_clone) then publishes these like any page the build made, and prunes
the old hashed stylesheets and scripts once no page links them.

Which pages. A page only the clone has is refreshed when its top-level folder is one the copy step adds to (reprice.MERGE: b/,
receipts/, season/ ...) or one the build did not make at all - those are the pages that stay live. A clone-only page in a folder the
build replaces wholesale (a player who left the index) is on its way out and is not brought back. PROTECTED names (the owner's posts,
the lab, the workflows) are never read.
"""
import os, re

NAV = re.compile(r'<nav class="sitenav"[^>]*>.*?</nav>[ \t]*\n?', re.S)
NAV_SCRIPT = re.compile(r'\s*<script>\(function\(\)\{var n=document\.getElementById\("sitenav"\).*?</script>[ \t]*\n?', re.S)
TABS = re.compile(r'<nav class="apptabs"[^>]*>.*?</nav>[ \t]*\n?', re.S)
SITE_LINK = re.compile(r'<link rel="stylesheet" href="/s/site-[0-9a-f]+\.css">')
APP_TAG = re.compile(r'<script src="/s/app-[0-9a-f]+\.js" defer></script>')
STYLE = re.compile(r'<style>(.*?)</style>[ \t]*\n?', re.S)
SCRIPT = re.compile(r'<script>(.*?)</script>[ \t]*\n?', re.S)
FOOT = '<p style="max-width:1360px;margin:10px auto 40px;'


def _old_chrome_css(css):
    """the inline blocks wrap() wrote before the shared stylesheet existed (11/5): the menu + account styles, and the phone zoom rules"""
    return ".sitenav{position:sticky" in css or css.lstrip().startswith("/* bigger text, less gutter")


def page_path(rel):
    """b/w9-1/index.html -> /b/w9-1/ ; index.html -> /"""
    rel = rel.replace(os.sep, "/")
    return "/" + (rel[:-len("index.html")] if rel.endswith("index.html") else rel)


def rechrome(t, path, sitenav, apptabs, next_strip, shared):
    """one page's HTML with this build's furniture, or (None, why) when a piece could not be found"""
    m = NAV.search(t)
    if not m: return None, "no menu block"
    end = m.end()
    for _ in range(2):                                  # the dropdown script (since 10/30) and the full-bleed inset script
        s = NAV_SCRIPT.match(t, end)
        if not s: break
        end = s.end()
    t = t[:m.start()] + sitenav(path) + t[end:]
    head_end = t.find("</head>")
    if head_end < 0: return None, "no </head>"
    link = f'<link rel="stylesheet" href="{shared["site"]}">'
    if SITE_LINK.search(t): t = SITE_LINK.sub(lambda _m: link, t)
    else:
        head, rest = t[:head_end], t[head_end:]; n = [0]
        def drop(mm):
            if _old_chrome_css(mm.group(1)): n[0] += 1; return ""
            return mm.group(0)
        head = STYLE.sub(drop, head)
        if not n[0]: return None, "no shared stylesheet link and no inline menu styles"
        t = head + link + rest
    tag = f'<script src="{shared["app"]}" defer></script>'
    if APP_TAG.search(t): t = APP_TAG.sub(lambda _m: tag, t)
    else:
        n = [0]
        def drop_js(mm):
            if "navigator.serviceWorker.register('/sw.js')" in mm.group(1): n[0] += 1; return ""
            return mm.group(0)
        t = SCRIPT.sub(drop_js, t)
        if not n[0]: return None, "no shared script link and no inline app script"
        b = t.rfind("</body>")
        if b < 0: return None, "no </body>"
        t = t[:b] + tag + "\n" + t[b:]
    if TABS.search(t): t = TABS.sub(lambda _m: apptabs(path), t, count=1)
    nx = next_strip(path)
    if nx and 'class="nx"' not in t:
        i = t.rfind(FOOT)
        if i < 0: i = t.rfind('<nav class="apptabs"')
        if i > 0: t = t[:i] + nx + t[i:]
    return t, ""


def _pages(root, skip):
    out = {}
    for d, dirs, fs in os.walk(root):
        if d == root: dirs[:] = [x for x in dirs if x not in skip and x != ".git"]
        dirs[:] = [x for x in dirs if x not in ("node_modules", ".git")]
        for f in fs:
            if f.endswith(".html"): out[os.path.relpath(os.path.join(d, f), root).replace(os.sep, "/")] = os.path.join(d, f)
    return out


def refresh(clone, site, sitenav, apptabs, next_strip, shared, merge, protected, t0=0, log=print):
    """write into `site` a re-furnished copy of every page that will be live after the copy step and is not on this build's menu.
    t0 = when this build started: a page in `site` written since then is this build's own and is never touched (wrap() made it).
    Returns (refreshed, skipped) as lists of site-relative paths."""
    if not (shared.get("site") and shared.get("app")): raise ValueError("the shared stylesheet and script are not written yet")
    built = _pages(site, set()); live = _pages(clone, set(protected)) if clone and os.path.isdir(clone) else {}
    made_top = {n for n in os.listdir(site)}
    done, skipped = [], []
    for rel in sorted(set(built) | set(live)):
        top = rel.split("/")[0] if "/" in rel else ""
        if rel not in built:
            if top in protected: continue
            if top and top in made_top and top not in merge: continue          # the build replaces this folder wholesale: the page is going away
        src = built.get(rel) or live[rel]
        if rel in built and t0 and os.path.getmtime(src) >= t0 - 2: continue
        try: t = open(src, encoding="utf-8").read()
        except Exception as e:
            skipped.append(rel); log(f"rechrome: {rel} unreadable ({e})"); continue
        if 'id="sitenav"' not in t: continue
        path = page_path(rel)
        if sitenav(path) in t and shared["site"] in t and shared["app"] in t: continue     # already this build's
        new, why = rechrome(t, path, sitenav, apptabs, next_strip, shared)
        if new is None:
            skipped.append(rel); log(f"rechrome: {rel} left as it is - {why}"); continue
        dst = os.path.join(site, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "w", encoding="utf-8").write(new); done.append(rel)
    return done, skipped
