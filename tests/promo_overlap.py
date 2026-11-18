"""Two open posted slips that lean on the same player are one bet posted twice (owner 11/17, "all four": the overlap check).
The slip log before it: 12 of the last 16 losing slips died on one quarterback's passing night, and both slips posted that Monday
needed him. sweep.shared marks the pair, build_promo prints it, the card says it (sweep.share_note via home.promo_card)."""
import copy, json, os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
import sweep as S
ok = bad = 0
def check(c, msg):
    global ok, bad
    print(("PASS " if c else "FAIL ") + msg); ok += bool(c); bad += (not c)
def P(slot, title, legs, result="", status="LIVE"): return {"slot": slot, "title": title, "status": status, "result": result, "legs": [{"who": w, "market": m} for w, m in legs]}
monday = [P(8, "Daily Sweep: Monday", [("Justin Herbert", "Passing Yards 175+"), ("Over 38.5 (BAL-LAC)", "Total"), ("Justin Herbert", "Passing TDs 1+"), ("Justin Herbert", "Rushing Yards 15+")]),
          P(9, "Piss Missile Monday", [("LAC +7.5", "Spread"), ("Over 40.5 (BAL-LAC)", "Total"), ("Justin Herbert", "Passing Yards 225+"), ("Justin Herbert", "Passing TDs 1+"), ("Zay Flowers", "Receiving Yards 50+"), ("Derrick Henry", "Anytime TD")])]
ps = copy.deepcopy(monday); lines = S.shared(ps)
check(len(lines) == 1 and "Justin Herbert" in lines[0] and "slots 8 and 9" in lines[0], f"the two slips posted Monday 11/16 are flagged as one bet on Justin Herbert ({lines[0][:90] if lines else lines})")
check(ps[0]["shares"] == [{"slot": 9, "title": "Piss Missile Monday", "who": ["Justin Herbert"], "lines": []}] and ps[1]["shares"][0]["slot"] == 8, "each card knows which slip it overlaps with, and on whom")
n = S.share_note(ps[0]); check(n.startswith("Also riding Justin Herbert: Piss Missile Monday.") and "both slips lose" in n, f"the card says it in a sentence ({n})")
check("Over 38.5 (BAL-LAC)" not in lines[0] and "Over 40.5" not in lines[0], "different totals in the same game are not called the same leg")
ps = [P(1, "A", [("Over 44.5 (HOU-IND)", "Total"), ("Nico Collins", "Receptions 5+")]), P(2, "B", [("Over 44.5 (HOU-IND)", "Total"), ("C.J. Stroud", "Passing Yards 200+")])]; lines = S.shared(ps)
check(len(lines) == 1 and ps[0]["shares"][0]["lines"] == ["Over 44.5 (HOU-IND)"] and not ps[0]["shares"][0]["who"] and "Over 44.5 (HOU-IND)" in S.share_note(ps[0]), "the same game line in both counts")
ps = [P(1, "A", [("Derrick Henry or Omarion Hampton", "Either TD")]), P(2, "B", [("Omarion Hampton", "Rushing Yards 25+")])]
check(S.shared(ps) == [] and S.share_note(ps[0]) == "" and ps[1]["shares"] == [], "an either-or leg is not a shared fate with a plain leg on one of the two (the other man can still score)")
ps = [P(1, "A", [("Derrick Henry or Omarion Hampton", "Either TD")]), P(2, "B", [("Derrick Henry or Omarion Hampton", "Either TD")])]
check(len(S.shared(ps)) == 1 and ps[0]["shares"][0]["lines"] == ["Derrick Henry or Omarion Hampton"], "the very same either-or pair in both slips does count")
ps = [P(1, "A", [("Justin Herbert", "Passing Yards 175+")], result="MISSED"), P(2, "B", [("Justin Herbert", "Passing TDs 1+")])]
check(S.shared(ps) == [] and S.share_note(ps[1]) == "", "a graded slip is history: no note against it")
ps = [P(1, "A", [("Justin Herbert", "Passing Yards 175+")], status="HIDDEN"), P(2, "B", [("Justin Herbert", "Passing TDs 1+")])]
check(S.shared(ps) == [], "a slip the owner archived is left out")
ps = [P(1, "A", [("Josh Allen", "Passing Yards 200+")]), P(2, "B", [("James Cook", "Anytime TD")]), P(3, "C", [("Khalil Shakir", "Receptions 3+")])]
check(S.shared(ps) == [] and all(p["shares"] == [] for p in ps) and all(S.share_note(p) == "" for p in ps), "three slips on three players: nothing is said (teammates are the single-slip check's job)")
ps = [P(1, "A", [("Josh Allen", "Passing Yards 200+"), ("James Cook", "Anytime TD")]), P(2, "B", [("Josh Allen", "Passing TDs 2+")]), P(3, "C", [("James Cook", "Rushing Yards 60+"), ("Josh Allen", "Rushing Yards 20+")])]; lines = S.shared(ps)
check(len(lines) == 3 and len(ps[0]["shares"]) == 2 and "(and 1 more slip)" in S.share_note(ps[0]), f"three overlapping slips: every pair is named in the log, the card names the first and counts the rest ({S.share_note(ps[0])[:70]})")
check("Josh Allen and James Cook" in S.share_note(ps[2]) or "James Cook and Josh Allen" in S.share_note(ps[2]) or "Josh Allen" in S.share_note(ps[2]), "two shared players read as a list")
# the built files, when a build is here: every promo carries the field, and a card with a note has it in the page
OUT = os.path.join(HERE, "out"); SITE = os.environ.get("SITE") or os.path.join(HERE, "site"); pj = os.path.join(OUT, "promos.json")
if os.path.exists(pj):
    pr = json.load(open(pj)); check(all("shares" in p for p in pr), f"every promo in this build carries its overlaps ({len(pr)} promos, {sum(1 for p in pr if p.get('shares'))} with one)")
    hp = os.path.join(SITE, "index.html")
    if os.path.exists(hp):
        home = open(hp, encoding="utf-8").read(); want = [p for p in pr if S.share_note(p) and str(p.get("status")) != "HIDDEN"]
        check(all("Also riding" in home for _ in want[:1]) and (("pshare" in home) == bool(want) or not want), f"the home page shows the note exactly when a card has one ({len(want)} this build)")
else: print("SKIP built files (no build here)")
print(f"\n{ok} passed, {bad} failed"); sys.exit(1 if bad else 0)
