"""The depth chart rule (owner 11/28 1:15 AM: "Yes keep players like Emanuel Wilson off"; his anytime TD at +2000 led Model's Best while
ESPN's depth chart listed him third, behind two backs who had come back). A player the depth chart has moved down - a running back listed
behind others while our numbers still treat him as the lead, or a quarterback who is not the starter - is put forward nowhere: none of
his legs carries a pick tier or the short-priced pool mark, and he is on no pick card on Today or Model's Best. His legs stay in the
builder with the flag.

Everything is read from the built site's own files (the Parlay Builder's data file, the two pages), so the test runs in any week; a
week in which the depth chart moves nobody down has nothing to check. No browser.
  python3 tests/depth_rule.py        (SITE=/path/to/a/published/copy to check that instead of ./site)"""
import html, json, os, re, sys
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ROOT = os.environ.get("SITE") or os.path.join(HERE, "site"); ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
bh = open(os.path.join(ROOT, "build", "index.html"), encoding="utf-8").read(); _m = re.search(r'src="(/build/data-[0-9a-f]+\.js)"', bh)
js = open(os.path.join(ROOT, _m.group(1).lstrip("/")), encoding="utf-8").read(); BS = json.JSONDecoder().raw_decode(js[js.index("{", js.index("window.__BS = ")):])[0]
DOWN = ("Depth chart: demoted", "Depth chart: not the starter")
out = sorted(pl for pl, fs in (BS.get("pf") or {}).items() if any(len(f) > 1 and str(f[1]) in DOWN for f in (fs or [])))
legs = [l for l in BS["legs"] if l.get("pl") in out and not l.get("gl")]
print(f"   week {BS['week']}: the depth chart has moved down {len(out)} player(s) with lines: {', '.join(out) or 'nobody'} ({len(legs)} legs)")
if not out:
    check(True, "nobody is moved down the depth chart this week: nothing to check")
else:
    marked = [(l["pl"], l["m"], l.get("ln"), l.get("tier"), l.get("sp")) for l in legs if l.get("tier") or l.get("sp")]
    check(not marked, f"none of their legs carries a pick tier or the short-priced pool mark ({len(legs)} legs; marked: {marked[:4]})")
    check(len(legs) > 0, "their legs are still in the builder's data, with the flag, for anyone who disagrees with the depth chart")
    def names(path):
        """the players on the pick cards of a page: leg cards and the Model's Best rows"""
        try: h = open(os.path.join(ROOT, path), encoding="utf-8").read()
        except Exception: return None
        got = re.findall(r'<div class="who"><b>(?:<a [^>]*>)?([^<]+)', h) + re.findall(r'class="mbn"[^>]*>([^<]+)', h)
        return {html.unescape(n).strip() for n in got}
    for path, label in (("best/index.html", "Model's Best"), ("index.html", "Today")):
        ns = names(path)
        if ns is None: check(True, f"{label}: no page built"); continue
        hit = sorted(set(out) & ns)
        check(not hit, f"{label}: none of them is on a pick card ({len(ns)} players on the page's cards; found: {hit})")
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
