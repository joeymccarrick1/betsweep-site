"""The boards' weather label (owner 11/23, 7:21 PM: "It's raining in DC why does it say clear night"). The label follows the forecast's
rain chance alone, never says Clear, and a card built after kickoff calls it the pre-game forecast. Runs build_boards.wx_block's own text
with the page's data stubbed; then reads the built page.   python3 tests/wx_label.py"""
import os, re, sys, html
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.environ.get("SITE") or os.path.join(HERE, "site")
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
src = open(os.path.join(HERE, "build_boards.py"), encoding="utf-8").read()
m = re.search(r"\ndef wx_block\(a, b, kick_hour\):\n.*?\n(?=\n|# ----)", src, re.S)
check(bool(m), "build_boards.py has wx_block")
NOW = 1_800_000_000_000
ns = {"E": html.escape, "ICONS": {k: "" for k in ("dome", "snow", "rain", "wind", "cloud", "sun", "moon")}, "WX": {}, "kick_ms": lambda a, b: ns["KO"], "KO": NOW + 3600e3,
      "_time": type("T", (), {"time": staticmethod(lambda: NOW / 1000)})}
exec(m.group(0), ns)
def lab(pch, ptype="none", wind=8, gust=15, roof="outdoors", ko_after=True):
    ns["WX"] = {frozenset(["A", "B"]): {"roof": roof, "temp": 50, "wind": wind, "gust": gust, "ptype": ptype, "pch": pch, "risk": "LOW", "updated": "x"}}
    ns["KO"] = NOW + (3600e3 if ko_after else -600e3)
    return re.sub(r"<[^>]+>", "", ns["wx_block"]("A", "B", 20)).split(" · ")[0].split(",")[0].strip()
cases = [((0,), "Dry forecast"), ((3,), "Dry forecast"), ((8,), "8% chance of rain"), ((4, "rain"), "4% chance of rain"), ((25,), "25% chance of rain"),
         ((30,), "Rain possible"), ((59, "rain"), "Rain possible"), ((60,), "Rain likely"), ((90, "rain"), "Rain likely"), ((40, "snow"), "Snow possible"),
         ((10, "none", 18, 25), "Windy"), ((70, "rain", 18, 30), "Rain likely"), ((80, "rain", 5, 5, "dome"), "Dome")]
got = [(a, want, lab(*a)) for a, want in cases]
bad = [g for g in got if g[1] != g[2]]
check(not bad, "the label follows the chance: dry under 5%, 'N% chance of rain' to 30%, possible 30-59%, likely 60%+, windy, dome" + (f" (first off: {bad[0]})" if bad else ""))
check(all("Clear" not in lab(p, t) for p in (0, 3, 8, 20) for t in ("none", "rain", "")), "it never says Clear")
check(lab(8, ko_after=False) == "Pre-game forecast: 8% chance of rain" and lab(0, ko_after=False) == "Pre-game forecast: dry forecast" and lab(80, "rain", 5, 5, "dome", False) == "Dome",
      f"after kickoff it says it is the pre-game forecast ({lab(8, ko_after=False)!r}); a dome stays a dome")
p = os.path.join(SITE, "boards", "index.html")
if os.path.exists(p):
    pg = open(p, encoding="utf-8").read()
    check("Clear night" not in pg and not re.search(r'class="wx[^"]*"[^>]*>(?:<svg.*?</svg>)?Clear', pg), "the built boards page has no Clear label")
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
