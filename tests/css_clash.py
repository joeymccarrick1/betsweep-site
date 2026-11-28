"""Site-wide style blocks reach every page: helmets.css(), why.css() and wxfx.css() are added to the one stylesheet all pages load.
A rule there that STARTS with a class name another generator already uses restyles that generator's element as well.

11/28, found by the owner on his phone: the leg cards' reasons list was `.why`; the Parlay Builder's "Flags on this leg" block (and
the boards' slip, and two captions on Today) were also `.why`. The new rules made every flag a two-column grid with a 16px column for
its label. The list is `.legwhy` now.

This test reads the three blocks and fails when a rule starts with a class name that also appears in another generator's markup or
styles, unless the name is on the short list below of names that are meant to be shared (the rule is there to style that very
element: a logo inside a board's team block, the weather layer inside a game header). Adding a rule that starts with an existing
name therefore takes a decision, written down here. No browser.
  python3 tests/css_clash.py"""
import glob, os, re, sys
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."); sys.path.insert(0, HERE)
import helmets, why, wxfx
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)

# names a site-wide rule may start with although other generators use them, and why
SHARED = {
    "helmets": {  # the logo / wordmark / shirt / five-bar pieces themselves (drawn by other generators through helmets.py or its script twin) ...
                "hm", "wm", "h5", "op", "jn", "wmrow", "l", "phm", "wma", "wmh", "sktb", "hmh", "ah",
                # ... and the existing blocks a logo or wordmark is placed inside
                "apptabs", "bqc", "dsum", "game", "ghd", "ghd2", "wash", "gteamlist", "hcard", "hd", "lg2", "pcn", "post", "pp", "sl", "tdir", "tm", "b", "compact"},
    "why": set(),   # the reasons list is this module's alone
    "wxfx": {"wxfx", "wxhost",                                # the layer and its host, emitted by the boards, Live and Today through wxfx.py
             "card", "done", "ghd", "ghd2", "hd", "wash"},      # the game headers the layer sits in; a finished card switches it off
}
BLOCKS = {"helmets": helmets.css(), "why": why.css(), "wxfx": wxfx.css()}
SRC = {os.path.basename(f): open(f, encoding="utf-8", errors="ignore").read() for f in glob.glob(os.path.join(HERE, "*.py")) + [os.path.join(HERE, "template.html")]}

def roots(css):
    """the first compound selector of every rule (the part before any space or combinator), as the set of its class names. A compound
    matches only an element that has ALL its classes, so `.wxfx.r` is as safe as its rarest name."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S); css = re.sub(r"url\([^)]*\)", "", css)
    css = re.sub(r"@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css); css = re.sub(r"@(?:media|supports)[^{]*\{", "", css)
    out = set()
    for sel in re.findall(r"([^{}]+)\{", css):
        for one in sel.split(","):
            one = one.strip()
            if not one or one.startswith("@") or one in ("from", "to") or one[0].isdigit(): continue
            c = frozenset(re.findall(r"\.([A-Za-z_][\w-]*)", re.split(r"\s+|>|\+|~", one)[0]))
            if c: out.add(c)
    return out

def used_elsewhere(name, own):
    """generator files (other than the block's own) where the name is a class in markup, in a selector or in a script"""
    n = re.escape(name); hits = []
    for f, s in SRC.items():
        if f == own + ".py": continue
        if (re.search(r'class=\\?["\'][^"\'<>]*(?<![\w-])' + n + r'(?![\w-])', s) or re.search(r'(?<![\w-])\.' + n + r'(?![\w-])\s*[{,: >.\[]', s)
                or re.search(r"classList\.(?:add|toggle|remove|contains)\('" + n + "'", s) or re.search(r"className = '[^']*(?<![\w-])" + n + r"(?![\w-])", s)):
            hits.append(f)
    return hits

for mod, css in BLOCKS.items():
    comps = roots(css); rs = set().union(*comps) if comps else set(); clash = {}
    for c in sorted(comps, key=sorted):
        if c & SHARED[mod]: continue                      # the rule is for an element on the shared list
        hits = {n: used_elsewhere(n, mod) for n in c}
        if all(hits.values()): clash[".".join(sorted(c))] = sorted(set(sum(hits.values(), [])))   # every name in the compound exists elsewhere: the rule can land on someone else's element
    check(len(comps) > 0, f"{mod}.css(): {len(comps)} different selectors start its rules")
    check(not clash, f"{mod}.css(): no rule starts with a class name another generator also uses, apart from the {len(SHARED[mod])} names listed as shared ({ {n: h[:3] for n, h in list(clash.items())[:4]} })")
    stale = sorted(n for n in SHARED[mod] if n not in rs)
    check(not stale, f"{mod}.css(): every name on the shared list still starts a rule (stale: {stale})")
# the rule that was broken, said plainly: nothing site-wide is called .why, and the Parlay Builder still has its own
allcss = "".join(BLOCKS.values())
check(not re.search(r"(?<![\w-])\.why(?![\w-])", allcss) and ".why{" in SRC.get("build_builder.py", ""), "nothing site-wide is called .why; that name is the Parlay Builder's flags block")
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
