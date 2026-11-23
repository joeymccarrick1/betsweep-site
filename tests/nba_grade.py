"""The nightly NBA grader (sports/nba/grade.py): lock at tip, grade from the box score, keep the record.

Owner 11/22 7:14 PM, after the /nba/ preview went up with "Nothing here is a pick: the projections have to be graded against results first":
"Alright get to what's next!" - this is the grading. Everything here is made-up data in a temporary folder; no network, no pandas, no browser.

What must hold:
  - a game is locked from the LAST board built BEFORE its tip, once, and never touched again;
  - with no board from before the tip in reach the game is MISSED and never graded (a number written after the ball went up is not a projection);
  - a locked game is graded only when its box score is final, and only once;
  - a locked player who did not play is counted on his own line, not in the averages;
  - model and season average are compared on the same players; the totals are always the sum of the nights;
  - a record that cannot be read is left exactly as it is.

  python3 tests/nba_grade.py
"""
import copy, datetime as dt, json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from sports.nba import grade as G
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
T = lambda h, m=0, d=23: dt.datetime(2026, 11, d, h, m, tzinfo=dt.timezone.utc)
iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")


def player(pid, name, team, game, mins, pts, reb, ast, fg3, avg=(20.0, 5.0, 4.0, 2.0), ladder=None):
    return {"id": pid, "name": name, "team": team, "opp": "X", "game": game, "grp": "F", "n": 12, "min": mins, "base_min": mins,
            "proj": {"pts": pts, "reb": reb, "ast": ast, "fg3": fg3}, "avg": None if avg is None else dict(zip(G.STATS, avg)), "l10": {},
            "ladder": ladder or {"pts": [[15, 0.85], [25, 0.5], [35, 0.1]]}, "status": None, "recent": [], "warn": []}


def board(built, pts_a=24.0, day="2026-11-22"):
    return {"sport": "nba", "format": 2, "day": day, "built": iso(built),
            "games": [{"id": "g1", "key": "BOS-GS", "tip": iso(T(1, 30)), "home": "GS", "away": "BOS", "proj": {"BOS": 113.1, "GS": 106.0}, "line": {"by": "DraftKings", "details": "BOS -7.5"}},
                      {"id": "g2", "key": "IND-NY", "tip": iso(T(1, 0)), "home": "NY", "away": "IND", "proj": {"IND": 110.0, "NY": 112.0}, "line": None}],
            "players": [player("1", "Alpha", "BOS", "g1", 34, pts_a, 6.0, 5.0, 2.5), player("2", "Bravo", "BOS", "g1", 20, 9.0, 3.0, 1.0, 1.0), player("3", "Charlie", "GS", "g1", 30, 18.0, 4.0, 6.0, 3.0, avg=None),
                        player("9", "Other Game", "NY", "g2", 30, 15.0, 4.0, 4.0, 1.0)]}


def line(pid, team, mins, pts, reb, ast, threes, dnp=False):
    return {"team": team, "id": pid, "name": "n", "pos": "F", "starter": True, "dnp": dnp, "reason": "", "s": {} if dnp else {"MIN": str(mins), "PTS": str(pts), "REB": str(reb), "AST": str(ast), "3PT": f"{threes}-9", "FG": "1-2"}}


def box(gid, done=True, rows=()):
    return {"id": gid, "date": iso(T(1, 30)), "state": "post" if done else "in", "done": done, "detail": "Final" if done else "3rd", "teams": [{"abbr": "GS", "score": "101", "ha": "home"}, {"abbr": "BOS", "score": "110", "ha": "away"}], "players": list(rows)}


# ---------------------------------------------------------------- the lock
early, prev, now_b = board(T(0, 40), pts_a=22.0), board(T(1, 10), pts_a=24.0), board(T(1, 45), pts_a=30.0)
locks = {}
new = G.lock(locks, [("feed", now_b), ("prev", prev), ("page", early)], T(0, 50))
check(new == [] and locks["2026-11-22"]["games"] == {}, "before any tip nothing is locked")
new = G.lock(locks, [("feed", now_b), ("prev", prev), ("page", early)], T(1, 45))
g1 = locks["2026-11-22"]["games"].get("g1") or {}
check(sorted(new) == [("2026-11-22", "g1", "locked"), ("2026-11-22", "g2", "locked")] and g1.get("source") == "prev" and g1.get("board_built") == iso(T(1, 10)) and g1.get("minutes_before_tip") == 20,
      "after the tip a game is locked from the last board built before it: the 1:10 board for a 1:30 tip, not the earlier one and not the one built after")
check([p["name"] for p in g1["players"]] == ["Alpha", "Bravo", "Charlie"] and g1["players"][0]["proj"]["pts"] == 24.0 and g1["players"][0]["avg"]["pts"] == 20.0 and g1["players"][0]["ladder"]["pts"][0] == [15, 0.85]
      and g1["proj"] == {"BOS": 113.1, "GS": 106.0} and g1["line"]["details"] == "BOS -7.5" and g1["key"] == "BOS-GS",
      "the lock holds that game's players only, with the model's numbers, season averages and chance ladders as that board had them, and the game's score and posted line")
g2 = locks["2026-11-22"]["games"]["g2"]
check(g2["source"] == "page" and g2["board_built"] == iso(T(0, 40)) and g2["players"][0]["name"] == "Other Game", "a 1:00 tip takes the 12:40 board: the 1:10 one was built after that game started")
snap = copy.deepcopy(locks)
G.lock(locks, [("feed", board(T(1, 25), pts_a=99.0))], T(3, 0))
check(locks == snap, "a locked game is never touched again, even if another board from before its tip turns up later")
m = {}
new = G.lock(m, [("feed", now_b), ("prev", None), ("page", board(T(1, 5), day="2026-11-21"))], T(2, 0))
check(sorted(x[2] for x in new if x[0] == "2026-11-22") == ["missed", "missed"] and m["2026-11-22"]["games"]["g1"].get("missed") and "players" not in m["2026-11-22"]["games"]["g1"] and m["2026-11-22"]["games"]["g1"]["why"],
      "with only a board built after the tip in reach (and one from another day), the game is marked missed, with the reason, and holds no numbers")
check(G.lock({}, [("a", None), ("b", {}), ("c", {"day": "2026-11-22", "games": [{"id": "z", "tip": "nonsense"}]})], T(5, 0)) == [], "an empty board, no board, and a game with no readable tip time are passed over without an error")

# ---------------------------------------------------------------- a box-score line
check(G.actual(line("1", "BOS", 33, 12, 5, 1, 2)) == {"min": 33, "pts": 12, "reb": 5, "ast": 1, "fg3": 2}, "a box-score line reads as minutes, points, rebounds, assists and threes made (the 2 of \"2-9\")")
check(G.actual(line("1", "BOS", 0, 0, 0, 0, 0, dnp=True)) is None and G.actual(line("1", "BOS", 0, 0, 0, 0, 0)) is None and G.actual(None) is None and G.actual({"s": {"MIN": "12", "PTS": "x"}}) is None,
      "did not play, zero minutes, not in the box score, and a line that cannot be read all count as did not play")

# ---------------------------------------------------------------- grading one game
S, rows = G.grade_game(g1, box("g1", rows=[line("1", "BOS", 36, 30, 4, 5, 4), line("3", "GS", 28, 20, 4, 8, 3), line("2", "BOS", 0, 0, 0, 0, 0, dnp=True)]))
# Alpha: model 24.0 vs 30 -> 6 off; season 20.0 -> 10 off.  reb 6.0 vs 4 -> 2; season 5 -> 1.  ast 5 vs 5 -> 0; season 4 -> 1.  fg3 2.5 vs 4 -> 1.5; season 2 -> 2.
check(S["games"] == 1 and S["players"] == 2 and S["dnp"] == 1, "two of the three locked players played; the one who did not is counted on his own line")
st = S["stats"]
check(st["pts"] == {"n": 1, "model": 6.0, "base": 10.0, "err": -6.0} and st["reb"]["model"] == 2.0 and st["reb"]["base"] == 1.0 and st["ast"]["model"] == 0.0 and st["fg3"] == {"n": 1, "model": 1.5, "base": 2.0, "err": -1.5},
      "misses are the distance from the result for the model and for the season average, on the same player-stats: Charlie, who has no season average, is in neither")
check(S["min"] == {"n": 2, "abs": 4.0, "err": 0.0}, "minutes are graded for everyone who played (34 for 36 and 30 for 28: 4 off in all, 0 on balance)")
# ladders, points: Alpha 30 -> reached 15 (85%: bucket 4) and 25 (50%: bucket 2), not 35 (10%: bucket 0); Charlie 20 -> reached 15, not 25, not 35
check(S["cal"]["pts"] == [[2, 0, 0.2], [0, 0, 0.0], [2, 1, 1.0], [0, 0, 0.0], [2, 2, 1.7]], "every rung of a chance ladder goes in the bucket of the chance it was given, with whether the player reached it")
ra = next(r for r in rows if r["name"] == "Alpha"); rb = next(r for r in rows if r["name"] == "Bravo")
check(ra["pts"] == [24.0, 20.0, 30] and ra["min"] == [34, 36] and rb.get("dnp") is True and rb["min"] == [20, None] and "pts" not in rb, "the player rows keep model, season average and result side by side; a player who did not play has no stat rows")
check(G.bucket(0.19) == 0 and G.bucket(0.2) == 1 and G.bucket(0.5) == 2 and G.bucket(0.8) == 4 and G.bucket(1.0) == 4, "the buckets are under 20%, 20-40, 40-60, 60-80 and 80 and up")

# ---------------------------------------------------------------- whole runs in a folder
d = tempfile.mkdtemp()
try:
    nba = os.path.join(d, "nba"); os.makedirs(nba)
    said = []
    r = G.run(nba, [("feed", prev)], now=T(0, 50), say=said.append)
    rec = json.load(open(os.path.join(nba, "record.json")))
    check(r["new"] == [] and rec["total"]["games"] == 0 and rec["nights"] == [] and not os.path.exists(os.path.join(nba, "locks", "2026-11-22.json")), "before the first tip: an empty record is started and no lock file is written")
    G.run(nba, [("feed", now_b), ("prev", prev)], now=T(1, 45), say=said.append)
    L = json.load(open(os.path.join(nba, "locks", "2026-11-22.json"))); rec = json.load(open(os.path.join(nba, "record.json")))
    check(L["games"]["g1"]["source"] == "prev" and L["games"]["g2"].get("missed") and rec["waiting"] == 1 and rec["missed"] == {"g2": "2026-11-22"} and rec["total"]["games"] == 0,
          "after the tips: g1 is locked, g2 (no board from before its tip) is missed, the record says one game is waiting for its box score")
    json.dump(box("g1", done=False, rows=[line("1", "BOS", 20, 14, 2, 2, 1)]), open(os.path.join(nba, "box-g1.json"), "w"))
    r = G.run(nba, [("feed", now_b)], now=T(2, 30), say=said.append)
    check(r["graded"] == [] and json.load(open(os.path.join(nba, "record.json")))["total"]["games"] == 0, "a game in progress is not graded")
    json.dump(box("g1", rows=[line("1", "BOS", 36, 30, 4, 5, 4), line("3", "GS", 28, 20, 4, 8, 3), line("2", "BOS", 0, 0, 0, 0, 0, dnp=True)]), open(os.path.join(nba, "box-g1.json"), "w"))
    json.dump(box("g2", rows=[line("9", "NY", 30, 15, 4, 4, 1)]), open(os.path.join(nba, "box-g2.json"), "w"))
    r = G.run(nba, [("feed", now_b)], now=T(4, 0), say=said.append)
    rec = json.load(open(os.path.join(nba, "record.json"))); night = json.load(open(os.path.join(nba, "graded-2026-11-22.json")))
    check([x[1] for x in r["graded"]] == ["g1"] and rec["total"]["games"] == 1 and rec["total"]["players"] == 2 and rec["total"]["dnp"] == 1 and rec["graded"] == {"g1": "2026-11-22"} and rec["waiting"] == 0 and rec["since"] == "2026-11-22",
          "once the box score is final the game is graded: 1 game, 2 player-games, 1 did not play; the missed game is not graded although its box score is there")
    check(list(night["games"]) == ["g1"] and night["games"]["g1"]["final"] == {"GS": "101", "BOS": "110"} and len(night["games"]["g1"]["rows"]) == 3 and night["games"]["g1"]["source"] == "prev",
          "the night's file keeps the game player by player, with the final score and which board the numbers were locked from")
    before = open(os.path.join(nba, "record.json")).read()
    r = G.run(nba, [("feed", now_b)], now=T(5, 0), say=said.append)
    check(r["graded"] == [] and json.load(open(os.path.join(nba, "record.json")))["total"] == json.loads(before)["total"], "run again, nothing is graded twice")
    tot = G.empty()
    for n in rec["nights"]: G.add(tot, n)
    check(G.rounded(tot) == rec["total"] and rec["nights"][0]["ids"] == ["g1"], "the totals are the sum of the nights")
    s = G.summary(rec)
    check(s["players"] == 2 and s["games"] == 1 and s["nights"] == 1 and abs(s["stats"]["pts"]["model"] - 6.0) < 1e-9 and abs(s["stats"]["pts"]["base"] - 10.0) < 1e-9 and abs(s["min"]["mae"] - 2.0) < 1e-9 and G.summary({"total": G.empty()}) is None and G.summary(None) is None,
          "the summary the page reads gives mean misses (points: model 6.0, season average 10.0; minutes 2.0), and nothing while no game is graded")
    # a second night adds to the record
    b2 = board(T(0, 40, d=24), day="2026-11-23"); b2["games"] = [dict(b2["games"][0], id="g5", tip=iso(T(1, 0, d=24)))]; b2["players"] = [dict(player("1", "Alpha", "BOS", "g5", 34, 28.0, 6.0, 5.0, 2.5))]
    G.run(nba, [("feed", b2)], now=T(1, 5, d=24), say=said.append)
    json.dump(box("g5", rows=[line("1", "BOS", 30, 25, 6, 5, 2)]), open(os.path.join(nba, "box-g5.json"), "w"))
    G.run(nba, [("feed", b2)], now=T(4, 0, d=24), say=said.append)
    rec = json.load(open(os.path.join(nba, "record.json")))
    check([n["day"] for n in rec["nights"]] == ["2026-11-22", "2026-11-23"] and rec["total"]["games"] == 2 and rec["total"]["players"] == 3 and rec["total"]["stats"]["pts"] == {"n": 2, "model": 9.0, "base": 15.0, "err": -3.0},
          "a second night is a second row, and the totals grow by it (points: 6 + 3 off for the model, 10 + 5 for the season average)")
    # a record that cannot be read is left alone
    open(os.path.join(nba, "record.json"), "w").write("{not json")
    b3 = board(T(0, 40, d=25), day="2026-11-24"); b3["games"] = [dict(b3["games"][0], id="g7", tip=iso(T(1, 0, d=25)))]; b3["players"] = [player("1", "Alpha", "BOS", "g7", 34, 28.0, 6.0, 5.0, 2.5)]
    json.dump(box("g7", rows=[line("1", "BOS", 30, 25, 6, 5, 2)]), open(os.path.join(nba, "box-g7.json"), "w"))
    said.clear(); r = G.run(nba, [("feed", b3)], now=T(4, 0, d=25), say=said.append)
    check(open(os.path.join(nba, "record.json")).read() == "{not json" and r["graded"] == [] and os.path.exists(os.path.join(nba, "locks", "2026-11-24.json")) and any("cannot be read" in x for x in said),
          "a record that cannot be read is left exactly as it is and nothing is graded into a new one; the night's lock is still kept, and the run says so")
    json.dump(rec, open(os.path.join(nba, "record.json"), "w"))
    r = G.run(nba, [("feed", b3)], now=T(4, 30, d=25), say=said.append)
    check([x[1] for x in r["graded"]] == ["g7"] and json.load(open(os.path.join(nba, "record.json")))["total"]["games"] == 3, "with the record readable again the waiting game is graded: nothing was lost")
    # old files are cleared
    for day in ("2026-11-10", "2026-11-11"):
        json.dump({"day": day, "games": {"old": {"missed": True, "why": "x"}}}, open(os.path.join(nba, "locks", f"{day}.json"), "w"))
    for day in ("2026-11-05", "2026-11-06", "2026-11-07"):
        json.dump({"day": day, "games": {}}, open(os.path.join(nba, f"graded-{day}.json"), "w"))
    G.run(nba, [("feed", b3)], now=T(5, 0, d=25), say=said.append)
    left_l = sorted(os.listdir(os.path.join(nba, "locks"))); left_g = sorted(f for f in os.listdir(nba) if f.startswith("graded-"))
    check(left_l == ["2026-11-22.json", "2026-11-23.json", "2026-11-24.json"] and len(left_g) == G.KEEP_NIGHT_FILES and left_g[-1] == "graded-2026-11-24.json" and not any(f.endswith(".tmp") for f in os.listdir(nba)),
          f"locks older than {G.KEEP_LOCK_DAYS} days are dropped and only the last {G.KEEP_NIGHT_FILES} nights' player files are kept; no half-written file is left behind")
finally:
    shutil.rmtree(d, ignore_errors=True)
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
