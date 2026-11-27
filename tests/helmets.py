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
big = [d + "/" + f for d in ("hm", "nfl") for f in os.listdir(os.path.join(HERE, "assets", d)) if os.path.getsize(os.path.join(HERE, "assets", d, f)) > 24000]
check(not big, f"no picture over 20 KB ({big or 'none'})")
css = H.css()
check(all(css.count("url(/s/%s/%s.webp)" % (H.SET, t.lower())) == 1 and css.count("url(/s/%s/%s-l.webp)" % (H.SET, t.lower())) == 1 for t in H.TEAMS), "the shared rule names each picture once")
missn = [t + x for t in H.TEAMS for x in ("", "-l") if not os.path.exists(os.path.join(HERE, "assets", "nfl", t.lower() + x + ".webp"))]
check(not missn, f"the logo set has every team in both sizes ({missn or 'none missing'})")
check(H.SET in ("nfl", "hm"), f"the set that is up is one of the two ({H.SET})")
check("scaleX(-1)" not in css if H.SET == "nfl" else True, "a logo is never mirrored")
_SET = H.SET; H.SET = "hm"; css = H.css(); H.SET = _SET
check(".tm.b [data-hm]" in css and "scaleX(-1)" in css and "[data-hm='LV'],[data-hm='SF']{transform:none !important}" in css, "the right-hand helmet is mirrored to face in, and the two with lettering never are")
try:
    from PIL import Image
    al = [d + "/" + t for d in ("hm", "nfl") for t in H.TEAMS if Image.open(os.path.join(HERE, "assets", d, t.lower() + ".webp")).convert("RGBA").split()[3].getextrema()[0] != 0]
    check(not al, f"every picture has its backdrop cut away (each has clear pixels; off: {al or 'none'})")
except ImportError: print("SKIP backdrop check: no image library here")
css = H.css()
# 11/27 wordmarks: one file per team, one rule per team, the name kept as text; a name that is not a team stays plain text
missw = [t for t in H.TEAMS if not os.path.exists(os.path.join(HERE, "assets", "wm", t.lower() + ".webp"))]
check(not missw and all(css.count(".wm[data-wm='%s']{background-image:url(/s/wm/%s.webp)}" % (t, t.lower())) == 1 for t in H.TEAMS), f"every team has a wordmark file and one rule ({missw or 'none missing'})")
check('data-wm="GB"' in H.wm("GB", "Packers") and ">Packers<" in H.wm("GB", "Packers") and H.wm("XYZ", "A & B") == "<span>A &amp; B</span>", "wm() keeps the name as text and leaves a non-team name plain")
check(H.matchup("DEN", "PIT", at=True).count("data-wm") == 2 and "@" in H.matchup("DEN", "PIT", at=True) and "@" not in H.matchup("DEN", "PIT") and H.matchup("DEN", "XYZ") == "", "matchup() says @ only when told who is visiting")
# 11/27: Social's house cards already use class "wm" for the BetSweep wordmark image - the team rule must not catch it
check("\n.wm{" not in css and not css.startswith(".wm{") and ".wm[data-wm]{" in css, "the wordmark base rule only applies to an element that names a team")
for f_, pat in (("build_stocks.py", 'class="sktb" data-hm="{t}"'), ("build_builder.py", "hmI(any.tm)"), ("build_builder.py", "hmI(l.tm) + esc(l.pl)"), ("social.py", "hmI(l.tm) + legText(l)")):
    check(pat in open(os.path.join(HERE, f_), encoding="utf-8").read(), f"{f_}: a small logo sits by the player or leg ({pat[:24]})")
check("rgba(255,255,255,.75)" not in css and "[data-hm]{filter" not in css and css.count("filter:drop-shadow") == 1, "no outline or shadow on a logo; one faint hairline rule, for the dark wordmarks only")
check(".apptabs{transform:translateZ(0)" in css, "the tab bar has its own layer")
# 11/27 afternoon: saved legs on My BetSweep, promo posters, the Sweep says share card
import posters as PO
row = PO.leg_row({"who": "Jonah Coleman", "disp": "Jonah Coleman anytime TD", "tm": "DEN", "o": -130}, "#fff"); row0 = PO.leg_row({"who": "X", "disp": "X", "tm": "", "o": 100}, "#fff")
check('class="leg lgo"' in row and "data:image/webp;base64," in row and 'class="bar"' in row0 and "base64" not in row0, "a poster leg wears its team's logo; a leg with no team keeps the colour bar")
for f_, pat in (("account.py", "data-pl=\"'+esc(q[0])+'\""), ("account.py", "/data/pteam.json"), ("build_site.py", '"pteam.json"'), ("build_boards.py", "/s/__HMSET__/"), ("build_boards.py", 'replace("__HMSET__"')):
    check(pat in open(os.path.join(HERE, f_), encoding="utf-8").read(), f"{f_}: wired ({pat[:26]})")
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
