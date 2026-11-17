"""The weather step fails the build on a wrong-week feed - except once the week's every game has kicked off (11/16).  python3 tests/weather_gate.py"""
import csv, datetime as dt, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import weather_feed as WF
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
T = tempfile.mkdtemp()
def games(rows):
    with open(os.path.join(T, "games.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["season", "game_type", "week", "gameday", "gametime", "away_score", "home_score"]); [w.writerow(r) for r in rows]
U = dt.timezone.utc
games([[2026, "REG", 10, "2026-11-12", "20:15", 17, 20], [2026, "REG", 10, "2026-11-15", "13:00", 38, 18], [2026, "REG", 10, "2026-11-16", "20:15", "", ""], [2026, "REG", 11, "2026-11-19", "20:15", "", ""], [2025, "REG", 10, "2025-11-10", "20:15", "", ""]])
check(WF.week_done(T, 10, dt.datetime(2026, 11, 17, 1, 0, tzinfo=U)) is False, "Monday 8:00 PM Eastern, 15 minutes before the last kickoff: the week is not done")
check(WF.week_done(T, 10, dt.datetime(2026, 11, 17, 1, 16, tzinfo=U)) is True, "one minute after the last kickoff (8:15 PM Eastern = 01:15 UTC): every game has kicked off, score or no score")
check(WF.week_done(T, 11, dt.datetime(2026, 11, 17, 5, 0, tzinfo=U)) is False and WF.week_done(T, 12, dt.datetime(2026, 11, 17, 5, 0, tzinfo=U)) is None, "next week is not done; a week with no games on the schedule cannot be told (None)")
check(WF.week_done(os.path.join(T, "nowhere"), 10) is None, "no schedule file: cannot be told (None), never True")
check(WF.decide(11, 10, True)[0] == 0 and "nothing left to flag" in WF.decide(11, 10, True)[1], "feed on next week + this week all kicked off: the build is not failed, and the message says why")
check(WF.decide(11, 10, False)[0] == 1 and WF.decide(11, 10, None)[0] == 1, "feed on next week while a game is still to come, or when that cannot be told: still fails")
check(WF.decide(12, 10, True)[0] == 1 and WF.decide(9, 10, True)[0] == 1 and WF.decide(None, 10, True)[0] == 1 and WF.decide("x", 10, True)[0] == 1, "any other mismatch (two weeks ahead, a week behind, no week) still fails")
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
