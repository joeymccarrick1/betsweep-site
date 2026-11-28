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
check("filter:drop-shadow" not in css, "no outline or shadow on any logo or wordmark")
check(all(css.count(".wm[data-wm='%s']{background-image:none;background-color:%s;" % (t, c)) == 1 and css.count(":root[data-theme='light'] .wm:not(.dk)[data-wm='%s']{background-image:url(/s/wm/%s.webp);background-color:transparent" % (t, t.lower())) == 1 for t, c in H.WM_DARK.items()) and "BAL" not in H.WM_DARK, "a dark one-colour wordmark is painted in the team's bright colour on the dark theme and shown as the file on the light theme")
check(sorted(H.WM_AR) == sorted(H.TEAMS), "every wordmark has its shape on record")
check(".apptabs{transform:translateZ(0)" in css, "the tab bar has its own layer")
# 11/27 afternoon: saved legs on My BetSweep, promo posters, the Sweep says share card
import posters as PO
row = PO.leg_row({"who": "Jonah Coleman", "disp": "Jonah Coleman anytime TD", "tm": "DEN", "o": -130}, "#fff"); row0 = PO.leg_row({"who": "X", "disp": "X", "tm": "", "o": 100}, "#fff")
check('class="leg lgo"' in row and "data:image/webp;base64," in row and 'class="bar"' in row0 and "base64" not in row0, "a poster leg wears its team's logo; a leg with no team keeps the colour bar")
for f_, pat in (("account.py", "data-pl=\"'+esc(q[0])+'\""), ("account.py", "/data/pteam.json"), ("build_site.py", '"pteam.json"'), ("build_boards.py", "/s/__HMSET__/"), ("build_boards.py", 'replace("__HMSET__"')):
    check(pat in open(os.path.join(HERE, f_), encoding="utf-8").read(), f"{f_}: wired ({pat[:26]})")
# 11/27 evening: colour wash, live strip, weather picture, progress bar, the cashed moment
check(".wmrow .wm[data-wm],h2.wmh .wm[data-wm]{background-size:100% 100%" in css, "two wordmarks side by side fill the same box")
# 11/27 night: jersey numbers - the shirt's two colours are the ones brand.py paints the old badges with, and the tile is drawn only when both the team and the number are known
import ast as _ast, re as _re2
_bt = open(os.path.join(HERE, "brand.py"), encoding="utf-8").read(); _tc = _ast.literal_eval(_re2.search(r"TEAMCOL = (\{.*?\})\n", _bt, _re2.S).group(1))
check(_tc == H.COL and sorted(H.COL) == sorted(H.TEAMS), "helmets.COL is the same 32 pairs of colours as brand.py's TEAMCOL")
_j = H.jersey("PIT", "13")
check('class="jn"' in _j and "--j1:#FFB612" in _j and "--j2:#101820" in _j and "--jk:#101820" in _j and ">13<" in _j and 'aria-label="number 13"' in _j, "a jersey tile carries the team's two colours, a number that reads on them, and says the number aloud")
check(H.jersey("PIT", "") == "" and H.jersey("XYZ", "13") == "" and H.jersey("LAR", 7).count("--j1:#003594") == 1, "no tile without a number or for a name that is not a team; ESPN's LAR is the Rams")
check("--jk:#ffffff" in H.jersey("LV", "89") and "--j2:#A5ACAF" in H.jersey("LV", "89"), "a black shirt gets a white number and keeps its silver trim")
check(".jn{" in css and "clip-path:polygon(" in css and ".h5{" in css, "the shirt shape and the five-bar chart are in the site's shared styles")
_by, _nm = H.numbers(os.path.join(HERE, "in"))
check(H.num(os.path.join(HERE, "in"), "No Such Player", "ARI") == "" and (not _by or all(v.isdigit() for v in _by.values())), f"numbers come from the season roster as digits ({len(_by)} players read); an unknown player has none")
# 11/27 night: the Live field - wordmarks in the end zones, the home logo at midfield
_lv = open(os.path.join(HERE, "build_live.py"), encoding="utf-8").read()
check("/s/wm/' + k + '.webp" in _lv and "/s/__HMSET__/' + hk + '-l.webp" in _lv and 'JS.replace("__HMSET__"' in _lv and "__HMTEAMS__" in _lv, "the Live field draws the end-zone wordmarks and the home logo from the owner's files")
check("if(!k) return '<text" in _lv, "a team without a file keeps its abbreviation in the end zone")
for f_, pat in (("build_boards.py", 'class="hd hmh wash'), ("build_builder.py", 'class="ghd wash"'), ("build_live.py", 'class="ghd2 wash"'), ("home.py", "def strip_js(games)"), ("build_today.py", "HOME.strip_js(games)"), ("home.py", "def _wx_icons()"), ("social.py", "function legPct(l, C)"), ("social.py", "function cashPop()")):
    check(pat in open(os.path.join(HERE, f_), encoding="utf-8").read(), f"{f_}: wired ({pat[:26]})")
check(".hd.wash{background:linear-gradient" in css and "#lstrip{" in css and "prefers-reduced-motion" in css, "the wash and the live strip have their rules, and the pulse stops for reduced motion")
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
