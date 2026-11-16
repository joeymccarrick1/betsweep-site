"""The Social grading job grades only what is certain (social_grade.py, 11/16). Synthetic finals in a temp folder; no network.
  python3 tests/social_grade.py"""
import csv, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
import social_grade as SG
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
T = tempfile.mkdtemp()
def w(name, cols, rows):
    with open(os.path.join(T, name), "w", newline="") as f:
        x = csv.writer(f); x.writerow(cols); [x.writerow(r) for r in rows]
w("games.csv", ["season", "game_type", "week", "away_team", "away_score", "home_team", "home_score"],
  [[2026, "REG", 10, "LAC", 24, "BAL", 27], [2026, "REG", 10, "PIT", 18, "CIN", 38], [2026, "REG", 10, "NE", 20, "DET", 20], [2026, "REG", 10, "LAR", 30, "SF", 13],
   [2026, "REG", 10, "DAL", "", "PHI", ""], [2026, "REG", 10, "JAC", 10, "TEN", 17], [2025, "REG", 10, "LAC", 3, "BAL", 40]])
SC = ["player_display_name", "season_type", "week", "team", "passing_yards", "passing_tds", "rushing_yards", "rushing_tds", "receptions", "receiving_yards", "receiving_tds"]
w("stats_player_week_2026.csv", SC, [
  ["Justin Herbert", "REG", 10, "LAC", 250, 2, 15, 0, 0, 0, 0], ["Derrick Henry", "REG", 10, "BAL", 0, 0, 88, 1, 1, 6, 0], ["Zay Flowers", "REG", 10, "BAL", 0, 0, 0, 0, 3, 49, 0],
  ["Omarion Hampton", "REG", 10, "LAC", 0, 0, 61, 0, 2, 20, 0], ["Ja'Marr Chase", "REG", 10, "CIN", 0, 0, 0, 0, 7, 110, 2], ["Marvin Harrison Jr.", "REG", 10, "SF", 0, 0, 0, 0, 4, 44, 1],
  ["Josh Allen", "REG", 10, "JAX", 0, 0, 0, 0, 0, 0, 0], ["Josh Allen", "REG", 10, "BUF", 301, 3, 20, 1, 0, 0, 0], ["Jared Goff", "REG", 10, "DET", 222, 1, 0, 0, 0, 0, 0],
  ["Drake Maye", "REG", 10, "NE", 240, 2, 31, 0, 0, 0, 0], ["Matthew Stafford", "REG", 10, "LA", 280, 3, 0, 0, 0, 0, 0], ["Cam Ward", "REG", 10, "TEN", 190, 1, 5, 0, 0, 0, 0],
  ["Justin Herbert", "REG", 9, "LAC", 100, 0, 0, 0, 0, 0, 0], ["Mac Jones", "REG", 10, "SF", 150, 1, 0, 0, 0, 0, 0], ["Aaron Rodgers", "REG", 10, "PIT", 180, 1, 0, 0, 0, 0, 0]])
w("snap_counts_2026.csv", ["game_type", "week", "player", "team", "offense_snaps", "st_snaps"],
  [["REG", 10, "Rashod Bateman", "BAL", 41, 0], ["REG", 10, "Justin Herbert", "LAC", 60, 0], ["REG", 10, "Jared Goff", "DET", 58, 0], ["REG", 10, "Drake Maye", "NE", 61, 0],
   ["REG", 10, "Joe Burrow", "CIN", 66, 0], ["REG", 10, "Aaron Rodgers", "PIT", 55, 0]])
F = SG.Finals(T)
def leg(pl, m, ln, g, **k): return dict({"pl": pl, "m": m, "ln": ln, "g": g}, **k)
G = lambda l, wk=10: SG.grade_leg(l, wk, F)
check(F.season == 2026 and len(F.games[10]) == 5, f"reads the newest season with finals and skips a game with no score yet ({F.season}, {len(F.games[10])} finals)")
check(G(leg("Justin Herbert", "Passing Yards", 249.5, "BAL-LAC")) == "hit" and G(leg("Justin Herbert", "Passing Yards", 250, "BAL-LAC")) == "hit" and G(leg("Justin Herbert", "Passing Yards", 250.5, "BAL-LAC")) == "miss", "yards against the line: 250 yards clears 249.5 and 250+, and misses 250.5")
check(SG.jsround(0.5) == 1 and SG.jsround(2.5) == 3 and SG.jsround(49.5) == 50, "half lines round up the way the page does (Python's round() would say 0, 2, 50)")
check(G(leg("Derrick Henry", "Anytime TD", 1, "BAL-LAC")) == "hit" and G(leg("Derrick Henry", "2+ TD", 2, "BAL-LAC")) == "miss" and G(leg("Ja'Marr Chase", "2+ TD", 2, "CIN-PIT")) == "hit", "touchdown legs count rushing and receiving scores")
check(G(leg("Justin Herbert", "Passing TDs", 1.5, "BAL-LAC")) == "hit" and G(leg("Justin Herbert", "Passing TDs", 3, "BAL-LAC")) == "miss", "passing touchdowns")
check(G(leg("Omarion Hampton", "Rush + Rec Yards", 80.5, "BAL-LAC")) == "hit" and G(leg("Zay Flowers", "Receiving Yards", 50, "BAL-LAC")) == "miss" and G(leg("Zay Flowers", "Receptions", 3, "BAL-LAC")) == "hit", "combined yards, receiving yards (49 misses 50+), receptions")
check(G(leg("Zay Flowers", "Under Receptions", 3.5, "BAL-LAC")) == "hit" and G(leg("Zay Flowers", "Under Receptions", 2.5, "BAL-LAC")) == "miss", "unders are the other side of the next whole number")
check(G(leg("Marvin Harrison", "Receiving Yards", 40, "LA-SF")) == "hit" and G(leg("Matthew Stafford", "Passing Yards", 275, "LAR-SF")) == "hit", "name suffixes and the Rams' two abbreviations do not lose a player")
check(G(leg("Henry or Hampton", "Either TD", 1, "BAL-LAC")) == ("unknown", "did not play (the book voids the leg)") and G(leg("Derrick Henry or Omarion Hampton", "Either TD", 1, "BAL-LAC")) == "hit" and G(leg("Zay Flowers or Omarion Hampton", "Either TD", 1, "BAL-LAC")) == "miss", "either-or touchdown: one scorer is enough; both known and scoreless is a miss; an unknown name is never a miss")
# game lines
T_ = lambda side, ln: leg(f"{side.title()} {ln}", "Total", ln, "BAL-LAC", gl={"k": "T", "side": side})
check(G(T_("OVER", 40.5)) == "hit" and G(T_("UNDER", 40.5)) == "miss" and G(T_("OVER", 51.5)) == "miss" and G(T_("UNDER", 51.5)) == "hit" and G(T_("OVER", 51)) == "push", "totals both ways (24 + 27 = 51), and a total that lands on the number is a push")
S_ = lambda side, ln, m="Spread", g="BAL-LAC": leg(f"{side} {ln}", m, ln, g, gl={"k": "M", "side": side})
check(G(S_("LAC", 7.5)) == "hit" and G(S_("LAC", 2.5)) == "miss" and G(S_("BAL", -2.5)) == "hit" and G(S_("BAL", -3)) == "push" and G(S_("BAL", -3.5)) == "miss", "spreads from the final (BAL by 3): +7.5 covers, -3 pushes, -3.5 does not")
check(G(S_("BAL", 1, "Moneyline")) == "hit" and G(S_("LAC", 1, "Moneyline")) == "miss" and G(S_("DET", 1, "Moneyline", "DET-NE")) == "push" and G(S_("KC", 1, "Moneyline")) == ("unknown", "game line names a team that is not in the game"), "moneyline; a tie is a push; a team that is not in the game is never graded")
# what must NOT be graded
check(G(leg("Jalen Hurts", "Passing Yards", 200, "DAL-PHI")) == ("unknown", "game not final") and G(leg("Justin Herbert", "Passing Yards", 200, "BAL-LAC"), 11) == ("unknown", "game not final"), "a game with no final score is left alone (and another week's game is not this week's)")
check(G(leg("Rashod Bateman", "Receiving Yards", 20, "BAL-LAC")) == "miss" and G(leg("Rashod Bateman", "Under Receptions", 0.5, "BAL-LAC")) == "hit", "on the field with nothing in the box (snap counts say he played): zero, so an over misses and an under hits")
check(G(leg("Mark Andrews", "Receiving Yards", 20, "BAL-LAC")) == ("unknown", "did not play (the book voids the leg)"), "no stats and no snaps in a game whose stats and snaps are both out: did not play - left, not a miss")
check(G(leg("Brock Bowers", "Receiving Yards", 20, "JAX-TEN")) == ("unknown", "snap counts not published yet") and G(leg("Brock Purdy", "Passing Yards", 200, "LA-SF")) == ("unknown", "snap counts not published yet"), "a missing player is left alone until the snap counts for his game are out")
check(G(leg("Josh Allen", "Passing Yards", 250, "JAX-TEN")) == "miss" and F.player("Josh Allen", {}, 10, F.game(10, "JAX-TEN"))["pass"] == 0, "a name shared by two players resolves to the one in the leg's game (the Jaguars' Josh Allen, not the Bills')")
check(G(leg("Justin Herbert", "First TD", 1, "BAL-LAC"))[0] == "unknown" and G(leg("Zay Flowers", "Longest Reception", 20, "BAL-LAC"))[0] == "unknown" and G(leg("Justin Herbert", "Interceptions", 1, "BAL-LAC"))[0] == "unknown", "first touchdown, longest reception and unknown markets are never guessed")
# whole posts
P = lambda i, legs, o=250, wk=10: {"id": i, "week": wk, "legs": legs, "fd_odds": o}
won = P(1, [leg("Justin Herbert", "Passing Yards", 225, "BAL-LAC"), leg("Derrick Henry", "Anytime TD", 1, "BAL-LAC"), S_("LAC", 7.5)], 308)
check(SG.grade_post(won, F) == ("won", 3.08, None) and SG.grade_post(P(2, won["legs"], -150), F) == ("won", 0.67, None), "every leg hit: won, units = profit on one unit at the posted price (+308 -> 3.08, -150 -> 0.67)")
check(SG.grade_post(P(3, [leg("Zay Flowers", "Receiving Yards", 50, "BAL-LAC"), leg("Mark Andrews", "Receiving Yards", 20, "BAL-LAC"), leg("Jalen Hurts", "Passing Yards", 200, "DAL-PHI")]), F) == ("lost", -1.0, None), "one missed leg loses the slip whatever is unknown elsewhere on it")
r = SG.grade_post(P(4, [leg("Justin Herbert", "Passing Yards", 225, "BAL-LAC"), leg("Mark Andrews", "Receiving Yards", 20, "BAL-LAC")]), F)
check(r[0] is None and "did not play" in r[2], f"all hit but one man did not play: left for the next run with the reason, not called a win ({r[2]})")
r = SG.grade_post(P(5, [leg("Justin Herbert", "Passing Yards", 225, "BAL-LAC"), S_("BAL", -3)]), F)
check(r[0] is None and "pushed" in r[2] and SG.grade_post(P(6, [S_("BAL", -3)]), F) == ("push", 0.0, None), "a pushed leg beside winners is left (the book re-prices it); a slip that is all push is a push")
check(SG.grade_post(P(7, won["legs"], None), F)[0] is None and SG.grade_post(P(8, []), F)[0] is None and SG.grade_post({"id": 9, "legs": won["legs"], "fd_odds": 200}, F)[0] is None, "no price, no legs or no week: left")
# the command itself, from a file: dry by construction, and the secret never appears in its output
pf = os.path.join(T, "posts.json"); json.dump([won, P(3, [leg("Zay Flowers", "Receiving Yards", 50, "BAL-LAC")]), P(4, [leg("Mark Andrews", "Receiving Yards", 20, "BAL-LAC")])], open(pf, "w"))
out = subprocess.run([sys.executable, os.path.join(HERE, "..", "social_grade.py"), "--in", T, "--posts", pf, "--write"], capture_output=True, text=True, env=dict(os.environ, FEED_GRADE_SECRET="s3cr3t-value-for-test"))
S = json.loads([x for x in out.stdout.splitlines() if x.startswith("SOCIALGRADE ")][-1][12:])
check(out.returncode == 0 and (S["posts"], S["won"], S["lost"], S["left"]) == (3, 1, 1, 1) and S["result"] == "graded from a file; nothing written" and "s3cr3t" not in out.stdout + out.stderr, f"the command grades a file of posts, writes nothing, and never prints the secret ({S['result']})")
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
