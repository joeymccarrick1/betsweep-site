"""Which slip a game card shows as its Best parlay, and what the home page says it was built for (11/17 evening).

bp_pick.pick: at or above fair -> the most likely to hit; within 5 cents of fair -> the same; otherwise slips within 3 cents of the
best EV are tied, a slip with a player leg beats two game lines, and the most likely to hit wins. The Week 11 Tuesday candidates
are in here as the first pass printed them (BP_DEBUG=1 python3 build_boards.py). The built cards are checked too: no moneyline
the model has under a coin flip (PHI-PIT read "Model has PIT 21.5-17" over Eagles ML + Over 38.5 at +423).
bp_pick.fit_note: "Built for the game's most likely script" only when it is. Page check needs a build (out/, site/)."""
import json, os, re, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
import bp_pick as BP
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)

P = lambda *rows: [tuple(r) for r in rows]
# 1 - at fair or better
c, plus, near, rule = BP.pick(P((0.30, 0.02, "A"), (0.34, 0.01, "B"), (0.50, -0.01, "C")))
check(c[2] == "B" and rule == 1 and len(plus) == 2 and len(near) == 3, f"a slip at fair or better wins, the most likely of those ({c[2]}, rule {rule})")
# 2 - within 5 cents
c, plus, near, rule = BP.pick(P((0.30, -0.02, "A"), (0.34, -0.049, "B"), (0.60, -0.051, "C")))
check(c[2] == "B" and rule == 2 and not plus and len(near) == 2, f"none at fair: the most likely within 5 cents of fair ({c[2]}, rule {rule})")
# 3 - nothing close: the real Tuesday candidates
phi = P((0.177, -0.074, "Over 38.5 + Eagles ML"), (0.175, -0.085, "Under 38.5 + Eagles ML"), (0.247, -0.098, "PIT -4.5 + Under 38.5"),
        (0.246, -0.099, "Over 38.5 + PHI +4.5"), (0.246, -0.100, "PIT -4.5 + Over 38.5"), (0.243, -0.110, "Under 38.5 + PHI +4.5"))
c, plus, near, rule = BP.pick(phi)
check(c[2] == "PIT -4.5 + Under 38.5" and rule == 3 and not plus and not near, f"PHI-PIT (model PIT 21.5-17): PIT -4.5 + Under 38.5, not the Eagles moneyline at +423 ({c[2]})")
c = BP.pick(P((0.189, -0.075, "Over 41.5 + Jets ML"), (0.243, -0.076, "Over 41.5 + LAC -3.5")))[0]
check(c[2] == "Over 41.5 + LAC -3.5", f"LAC-NYJ: a tenth of a cent no longer picks the Jets moneyline ({c[2]})")
c = BP.pick(P((0.238, -0.076, "Over 46.5 + MIN +3"), (0.293, -0.098, "49ers ML + Under 46.5"), (0.236, -0.079, "Under 46.5 + MIN +3")))[0]
check(c[2] == "49ers ML + Under 46.5", f"MIN-SF: the pair most likely to cash inside the 3-cent tie ({c[2]})")
c = BP.pick(P((0.246, -0.085, "IND +11.5 + Over 44.5"), (0.243, -0.097, "IND +11.5 + Under 44.5")))[0]
check(c[2] == "IND +11.5 + Over 44.5", f"HOU-IND: nothing more likely inside the tie, so the card does not change ({c[2]})")
c = BP.pick(P((0.20, -0.070, "A"), (0.45, -0.101, "B")))[0]
check(c[2] == "A", f"a slip more than 3 cents behind the best does not win on its hit chance ({c[2]})")
c = BP.pick(P((0.20, -0.070, "A"), (0.45, -0.100, "B")))[0]
check(c[2] == "B", f"exactly 3 cents behind still counts as tied ({c[2]})")
# 3 - a player leg beats two game lines inside the tie, and only inside it
hp = lambda x: x[2].startswith("player")
c = BP.pick(P((0.30, -0.060, "lines 1"), (0.22, -0.080, "player slip"), (0.35, -0.085, "lines 2")), has_player=hp)[0]
check(c[2] == "player slip", f"inside the tie a slip with a player leg beats two game lines ({c[2]})")
c = BP.pick(P((0.30, -0.060, "lines 1"), (0.22, -0.095, "player slip"), (0.35, -0.085, "lines 2")), has_player=hp)[0]
check(c[2] == "lines 2", f"a player-leg slip outside the tie does not jump the queue ({c[2]})")
c = BP.pick(P((0.30, 0.01, "lines at fair"), (0.22, -0.01, "player slip")), has_player=hp)[0]
check(c[2] == "lines at fair", f"rules 1 and 2 are untouched by the player-leg preference ({c[2]})")
c, plus, near, rule = BP.pick(P((0.24, -0.061, "only")))
check(c[2] == "only" and rule == 3, "a single candidate is returned as it is")
check(BP.pick(P((0.25, -0.09, "x", ["legs"], [[1]])))[0][3] == ["legs"], "the picked tuple comes back whole (legs and correlations ride along)")

# fit_note
g = {"probs": [56.0, 26.0, 13.0, 6.0]}
check(BP.fit_note({"a": "HOU", "b": "IND", "fit": "HOU by 10+"}, g) == "Built for the game's most likely script (HOU by 10+)", "most likely ending: \"Built for the game's most likely script\"")
n = BP.fit_note({"a": "HOU", "b": "IND", "fit": "shootout"}, g)
check(n == "Does best if the game turns into a shootout (13% likely)", f"another ending is named for what it is, with its chance ({n})")
n = BP.fit_note({"a": "PHI", "b": "PIT", "fit": "PHI by 10+"}, {"probs": [15.0, 40.0, 9.0, 36.0]})
check(n == "Does best if PHI wins by 10 or more (15% likely)", f"an unlikely blowout is not called the most likely script ({n})")
n = BP.fit_note({"a": "DEN", "b": "LV", "fit": "close, low"}, {"probs": [50.0, 32.0, 10.0, 8.0]})
check(n == "Does best if the game stays close and low-scoring (32% likely)", f"close and low reads as a sentence ({n})")
n = BP.fit_note({"a": "LAC", "b": "NYJ", "fit": "NYJ by 10+"}, {"probs": [33.0, 38.0, 13.0, 17.0]})
check(n == "Does best if NYJ wins by 10 or more (17% likely)", f"the away side's blowout names the right team ({n})")
check(BP.fit_note({"a": "A", "b": "B", "fit": "A by 10+"}, {}) == "Does best if the game ends A by 10+", "no ending odds on hand: no claim about likelihood")
check(BP.fit_note({"a": "A", "b": "B", "fit": ""}, g) == "" and BP.fit_note({"a": "A", "b": "B"}, g) == "", "no fit on the record: nothing is said")
check(BP.fit_note({"a": "A", "b": "B", "fit": "close, low"}, {"probs": [30.0, 30.0, 20.0, 20.0]}).startswith("Built for"), "a tie for most likely counts as most likely")

# the built pages
OUT = os.path.join(HERE, "out"); SITE = os.environ.get("SITE") or os.path.join(HERE, "site")
bpf, bdf, hp_ = os.path.join(OUT, "best_parlays.json"), os.path.join(OUT, "builder_data.json"), os.path.join(SITE, "index.html")
if all(os.path.exists(x) for x in (bpf, bdf, hp_)):
    bp = json.load(open(bpf)); bp = bp.get("parlays", bp) if isinstance(bp, dict) else bp
    bd = json.load(open(bdf)); G = {x["gid"]: x for x in bd["games"]}
    recs = [p for p in bp if p.get("legs")]
    home = open(hp_, encoding="utf-8").read()
    m = re.search(r'<small>Best same-game parlay</small>.*?<p>(.*?) model gives the full slip', home, re.S)
    if recs and m:
        top = max(recs, key=lambda p: p.get("ev") or 0); want = BP.fit_note(top, G.get(top["gid"], {}))
        got = re.sub(r"<[^>]+>", "", m.group(1)).replace("&#x27;", "'").replace("&#39;", "'").strip().rstrip(";").replace("; the", "").strip()
        check(got == want, f"home page, lead parlay ({top['gid']}): \"{got}\"")
        lab = lambda p: [f"{p['a']} by 10+", "close, low", "shootout", f"{p['b']} by 10+"]
        off = [p["gid"] for p in recs if p.get("fit") in lab(p) and G.get(p["gid"], {}).get("probs") and G[p["gid"]]["probs"][lab(p).index(p["fit"])] < max(G[p["gid"]]["probs"])]
        check("most likely script" not in home or top["gid"] not in off, f"the page says \"most likely script\" only when it is ({len(off)} of {len(recs)} cards lean on another ending this build)")
    else: print("SKIP home page sentence (no lead parlay on this build)")
    dogs = [(p["gid"], l[0], round(l[4], 2)) for p in recs if not (p.get("lean") or {}).get("side") for l in p["legs"] if l[1] == "Moneyline" and l[4] < 0.5]
    check(not dogs, f"no card parlay carries a moneyline the model has under a coin flip ({len(recs)} cards{'; ' + str(dogs) if dogs else ''})")
    brd = os.path.join(OUT, "matchup-boards.html")
    if os.path.exists(brd):
        b = open(brd, encoding="utf-8").read()
        check("this is the closest</span>" not in b, "no card still says \"this is the closest\" (the note names how it was picked)")
else: print("SKIP page checks (no build here)")
print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
