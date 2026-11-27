"""Team helmets (owner 11/26: "I'm going to add a bunch of graphics of logos on helmets. Use this all over the site to represent the
NFL teams"). Checks, with no browser: all 32 pictures are in assets/hm in both sizes, the shared rule names every team once, the badge
markup the generators write carries the team, and hm() answers nothing for a name that is not an NFL team.   python3 tests/helmets.py"""
import os, re, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
import helmets as H
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
check(len(H.TEAMS) == 32 and len(set(H.TEAMS)) == 32, "32 teams, each once")
miss = [t + s for t in H.TEAMS for s in ("", "-l") if not os.path.exists(os.path.join(HERE, "assets", "hm", t.lower() + s + ".webp"))]
check(not miss, f"every team has a small and a large picture ({miss or 'none missing'})")
big = [f for f in os.listdir(os.path.join(HERE, "assets", "hm")) if os.path.getsize(os.path.join(HERE, "assets", "hm", f)) > 20000]
check(not big, f"no picture over 20 KB ({big or 'none'})")
css = H.css()
check(all(css.count("url(/s/hm/%s.webp)" % t.lower()) == 1 and css.count("url(/s/hm/%s-l.webp)" % t.lower()) == 1 for t in H.TEAMS), "the shared rule names each picture once")
check(".tm.b [data-hm]" in css and "scaleX(-1)" in css and "[data-hm='LV'],[data-hm='SF']{transform:none !important}" in css, "the right-hand helmet is mirrored to face in, and the two with lettering never are")
try:
    from PIL import Image
    al = [t for t in H.TEAMS if Image.open(os.path.join(HERE, "assets", "hm", t.lower() + ".webp")).convert("RGBA").getpixel((0, 0))[3] != 0]
    check(not al, f"every picture has its backdrop cut away (corner is clear; off: {al or 'none'})")
except ImportError: print("SKIP backdrop check: no image library here")
for f_, pat in (("build_boards.py", '_hl, _hr = ((b, a) if (_ah and _hg["home_team"] == a) else (a, b))'), ("build_builder.py", "g.home === g.a) ? {l: B, r: A} : {l: A, r: B}"), ("build_live.py", "sw = ah && hm_ === g.a")):
    check(pat in open(os.path.join(HERE, f_), encoding="utf-8").read(), f"{f_}: the header puts the away team on the left and the home team on the right")
check("[data-hm='LAR']" in css and "[data-hm='WSH']" in css, "LAR and WSH are understood as LA and WAS")
check(H.hm("GB").count('data-hm="GB"') == 1 and "aria-label" in H.hm("GB") and H.hm("LAR").count('data-hm="LA"') == 1, "hm() gives a labelled helmet")
check(H.hm("XYZ") == "" and H.hm("") == "" and H.hm('"><b>') == "", "hm() gives nothing for a name that is not an NFL team")
ns = {"E": __import__("html").escape, "HERE": HERE, "os": os}; exec(open(os.path.join(HERE, "brand.py"), encoding="utf-8").read(), ns)
check('data-hm="KC"' in ns["badge"]("KC") and ">KC<" in ns["badge"]("KC") , "the board badge carries its team and keeps the abbreviation as text")
check(sorted(ns["TEAMCOL"]) == sorted(H.TEAMS), "the helmet list is the same 32 names the team colours use")
for f, pat in (("build_builder.py", "data-hm=\"' + t + '\""), ("build_live.py", "data-hm=\"' + t + '\""), ("build_teams.py", 'data-hm="{E(t)}"'), ("build_players.py", 'data-hm="{E(p["team"])}"'), ("build_site.py", "_HMS.css()")):
    check(pat in open(os.path.join(HERE, f), encoding="utf-8").read(), f"{f} is wired")
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
