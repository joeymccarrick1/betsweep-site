"""/how/ ("How BetSweep picks"): the numbers are counted from the graded legs, never typed (11/17).
Run on Weeks 6-8 alone the count must return the 11/4 audit (RUNBOOK "Deep dig"); the built page carries no unfilled key; with no
snapshots the 11/17 numbers stand in. Needs in/legsnaps.json (the sheet mirror) and, for the page check, a built site."""
import json, os, re, sys, tempfile
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
import how_stats as HS
IN = os.environ.get("IN") or os.path.join(HERE, "in"); SITE = os.environ.get("SITE") or os.path.join(HERE, "site")
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)
L = HS.legs(IN)
check(len(L) >= 4929, f"the mirror holds the graded legs ({len(L):,})")
early = [x for x in L if x["w"] in (6, 7, 8)]
n, h, im, r = HS._s(early); check(n == 4929 and abs(r + 0.081) < 0.002, f"Weeks 6-8, every leg: 4,929 legs at -8.1% ({n:,}, {100*r:+.1f}%)")
n, h, im, r = HS._s([x for x in early if x["m"] == "Rushing Yards"]); check(abs(r + 0.191) < 0.002, f"Weeks 6-8, rushing overs -19.1% ({100*r:+.1f}%, {n} legs)")
pm = [x for x in early if x["o"] >= 150 and x["raw"] is not None and x["raw"] - HS._imp(x["o"]) >= 0.05]; n, h, im, r = HS._s(pm)
check(n == 150 and abs(h - 0.413) < 0.002 and abs(im - 0.318) < 0.002 and abs(r - 0.315) < 0.003, f"Weeks 6-8, plus-money edge legs: 150 at 41.3% vs 31.8%, +31.5% ({n}, {100*h:.1f}% vs {100*im:.1f}%, {100*r:+.1f}%)")
d = HS.stats(IN); weeks = sorted({x["w"] for x in L})
check(d["N_ALL"] == f"{len(L):,}" and str(weeks[-1]) in d["WEEKS"] and d["N_WEEKS_WORD"] == HS._word(len(weeks)), f"the page counts every graded week ({d['N_ALL']} legs, {d['WEEKS']}, \"{d['N_WEEKS_WORD']}\")")
check(set(HS.DEFAULT) == set(d), f"every key the page uses is counted ({len(d)} keys)")
check(all(re.fullmatch(r"[+−]?\d+%", d[k]) for k in ("ROI_ALL", "FLOOR_ROI", "RUSH_ROI", "PLUS_ROI")) and all(d[k] in ("g", "b") for k in ("ALL_C", "FLOOR_C", "RUSH_C", "PLUS_C")), "the four boxes are a signed percent each, coloured by sign")
check((d["PLUS_ROI"].startswith("+")) == (d["PLUS_C"] == "g") and (d["ROI_ALL"].startswith("−")) == (d["ALL_C"] == "b"), f"green only where the return is positive (all {d['ROI_ALL']} {d['ALL_C']}, plus tier {d['PLUS_ROI']} {d['PLUS_C']})")
src = open(os.path.join(HERE, "how_body.html"), encoding="utf-8").read(); keys = set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", src))
check(keys and keys <= set(HS.DEFAULT), f"how_body.html only asks for keys the module has ({len(keys)} used)")
out = HS.fill(src, IN); check("{{" not in out and d["N_ALL"] in out and d["WEEKS"] in out, "fill() leaves no key behind and writes the count and the weeks")
with tempfile.TemporaryDirectory() as t:
    e = HS.fill(src, t); check("{{" not in e and HS.DEFAULT["N_ALL"] in e, "with no snapshots the page still reads whole (the 11/17 numbers)")
ph = HS.plus_phrase(IN, html=False); m = re.fullmatch(r"Weeks? [\d, -]+: (\d+)% hit against a (\d+)% price, [+-]?\d+% at a unit each \(([\d,]+) legs\)", ph)
check(bool(m) and int(m.group(1)) > int(m.group(2)) and "&" not in ph and "\u2212" not in ph, f"the plus tier's record for Model's Best and the builder chip is counted, in plain text for a tooltip ({ph})")
with tempfile.TemporaryDirectory() as t: check("175 legs" in HS.plus_phrase(t, html=False), "and falls back to the 11/17 count when the snapshots are missing")
w = HS.weights_text(); check("touchdowns" in w and "rushing yards" in w and "very little" in w, f"the weights sentence comes from calib.py ({w[:70]}...)")
pg = os.path.join(SITE, "how", "index.html")
if os.path.exists(pg):
    t = open(pg, encoding="utf-8").read(); check("{{" not in t and "graded weeks taught us" in t and d["N_ALL"] in t, f"the built page carries the counted numbers ({d['N_ALL']} legs)")
    check("three graded weeks" not in t or len(weeks) == 3, "the page no longer says three graded weeks")
print(f"{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
