#!/usr/bin/env python3
"""weekgate.py - next week's prices stay out of this week's build.

Why (11/16). FanDuel posts Thursday's game early. On the Monday of Week 10 the sheet's price tabs already held Colts @ Texans (Thu 11/19,
a Week 11 game): 122 Leg Board rows, 285 FanDuel links, 26 first-TD prices, 20 unders, 222 game-line rows, and the other books' prices
for twelve Week 11 games. The Leg Board joins a price to the projection by player, so those rows carried WEEK 10's projection against
Week 10's opponent (Daniel Jones "vs MIA", model 46% on a +230 line), and the builders file a leg under its team's game of the week -
a game that had been played. The first Monday rebuild that was allowed to publish (until that morning the board-shrank check stopped
them all) put 150 of them on the site under two finished games; they were on the home page and led the flag audit's biggest-gaps list.

clean(IN, week) rewrites the price dumps in ./in without the rows whose game is not on the week's schedule. A row belongs to the week
when the two teams named in its Game cell are a pair on the schedule (in/games.csv) and, where the row has a kickoff, that date is
within four days of the scheduled one (the same two teams can meet again a week later in January). A row whose game cannot be read is
kept. Archives of earlier weeks (legsnaps, results_legs, closing) are not touched.

Who calls it: reprice.py right after the mirror is copied in; build_firsttd.py, build_boards.py and build_builder.py as their first
step, so a build run by hand from a fresh copy of the mirror is covered too. It is safe to run twice.

  python3 weekgate.py            clean ./in for the week in in/boards.json and print what was kept out
  python3 weekgate.py --check    print only, change nothing
  python3 weekgate.py selftest
"""
import csv, datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
# the price dumps with a Game column that the current week's pages read
FILES = ("legboard.json", "bestlegs.json", "links.json", "bookodds.json", "gamelines.json", "ftdodds.json", "unders.json")
NEAR_DAYS = 4


def _full():
    import gamelines as GLM
    return GLM.TEAM_FULL


def week_of(IN):
    try: return int(float(json.load(open(os.path.join(IN, "boards.json"), encoding="utf-8"))["values"][1][1]))
    except Exception: pass
    v = json.load(open(os.path.join(IN, "settings.json"), encoding="utf-8"))["values"]
    return int(float(next(r[1] for r in v if r and str(r[0]).strip().lower() == "projection week")))


def schedule(IN, week):
    """{frozenset({away, home}): 'YYYY-MM-DD'} for the week, newest season in in/games.csv (regular season or playoffs)"""
    with open(os.path.join(IN, "games.csv"), newline="") as f: rows = [g for g in csv.DictReader(f) if g.get("week") == str(week)]
    if not rows: return {}
    season = max(g["season"] for g in rows)
    return {frozenset((g["away_team"], g["home_team"])): g.get("gameday", "") for g in rows if g["season"] == season}


def _md(kick):
    m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", str(kick or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def _near(md, gameday):
    try: y, mo, d = (int(x) for x in gameday.split("-")); g = datetime.date(y, mo, d)
    except Exception: return True          # no usable date on the schedule: the pair alone decides
    for yy in (y - 1, y, y + 1):
        try:
            if abs((datetime.date(yy, md[0], md[1]) - g).days) <= NEAR_DAYS: return True
        except ValueError: pass
    return False


def this_week(game, kick, sched, full=None):
    """True = on this week's schedule, False = another week's game, None = cannot tell (the row is kept)"""
    g = str(game or "")
    if " @ " not in g: return None
    full = full or _full()
    a, b = (x.strip() for x in g.split(" @ ", 1))
    ta, tb = full.get(a), full.get(b)
    if not ta or not tb: return None
    pair = frozenset((ta, tb))
    if pair not in sched: return False
    md = _md(kick)
    if md and not _near(md, sched[pair]): return False
    return True


def clean(IN, week=None, write=True, files=FILES):
    """drop next week's rows from the price dumps in IN. Returns {file: {game: rows kept out}} (empty when nothing was out of week)."""
    week = week_of(IN) if week is None else int(week)
    sched = schedule(IN, week)
    if not sched: return {}                # no schedule for the week: nothing can be judged, nothing is touched
    full = _full(); out = {}
    for name in files:
        p = os.path.join(IN, name)
        try: d = json.load(open(p, encoding="utf-8"))
        except Exception: continue
        v = d.get("values") if isinstance(d, dict) else None
        if not isinstance(v, list) or not v or not isinstance(v[0], list): continue
        hdr = [str(x).strip() for x in v[0]]
        if "Game" not in hdr: continue
        gi = hdr.index("Game"); ki = hdr.index("Kickoff (CT)") if "Kickoff (CT)" in hdr else None
        keep, gone = [v[0]], {}
        for r in v[1:]:
            game = r[gi] if isinstance(r, list) and len(r) > gi else ""
            kick = r[ki] if ki is not None and isinstance(r, list) and len(r) > ki else ""
            if this_week(game, kick, sched, full) is False: gone[str(game)] = gone.get(str(game), 0) + 1
            else: keep.append(r)
        if gone:
            out[name] = gone
            if write:
                d["values"] = keep
                with open(p, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False)
    return out


def report(out):
    if not out: return "weekgate: every priced row is on this week's schedule"
    games = sorted({g for v in out.values() for g in v})
    return ("weekgate: kept out " + ", ".join(f"{sum(v.values())} {n[:-5]} rows" for n, v in out.items())
            + f" from {len(games)} game(s) not on this week's schedule (" + "; ".join(games[:4]) + ("; ..." if len(games) > 4 else "") + ")")


def selftest():
    import tempfile
    full = {"Indianapolis Colts": "IND", "Houston Texans": "HOU", "Miami Dolphins": "MIA", "Baltimore Ravens": "BAL", "Los Angeles Chargers": "LAC"}
    sched = {frozenset(("IND", "MIA")): "2026-11-15", frozenset(("BAL", "LAC")): "2026-11-16"}
    n = [0, 0]
    def ok(c, what):
        n[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
    ok(this_week("Los Angeles Chargers @ Baltimore Ravens", "Mon 11/16 7:15 PM", sched, full) is True, "tonight's game is this week's")
    ok(this_week("Indianapolis Colts @ Houston Texans", "Thu 11/19 7:15 PM", sched, full) is False, "Thursday's game between two teams that did not meet this week is out")
    ok(this_week("Miami Dolphins @ Indianapolis Colts", "", sched, full) is True, "a pair on the schedule with no kickoff on the row is kept")
    ok(this_week("Miami Dolphins @ Indianapolis Colts", "Sun 11/22 12:00 PM", sched, full) is False, "the same pair a week later is next week's game")
    ok(this_week("Miami Dolphins @ Indianapolis Colts", "Sat 11/14 19:15", sched, full) is True, "a game moved by a day is still this week's")
    ok(this_week("", "", sched, full) is None and this_week("IND v MIA", "", sched, full) is None, "a row with no readable game is left alone")
    ok(this_week("Springfield Atoms @ Houston Texans", "", sched, full) is None, "an unknown team name is left alone")
    ok(_near((1, 3), "2026-12-31") and not _near((1, 10), "2026-12-31"), "dates compare across the new year")
    with tempfile.TemporaryDirectory() as t:
        with open(os.path.join(t, "games.csv"), "w") as f:
            f.write("season,game_type,week,gameday,away_team,home_team\n2025,REG,10,2025-11-09,IND,HOU\n2026,REG,10,2026-11-15,MIA,IND\n2026,REG,10,2026-11-16,LAC,BAL\n2026,REG,11,2026-11-19,IND,HOU\n")
        json.dump({"values": [["2026"], ["Week", "10"]]}, open(os.path.join(t, "boards.json"), "w"))
        lb = [["Player", "Game", "Kickoff (CT)"], ["A", "Los Angeles Chargers @ Baltimore Ravens", "Mon 11/16 7:15 PM"], ["B", "Indianapolis Colts @ Houston Texans", "Thu 11/19 7:15 PM"], ["C"]]
        json.dump({"values": lb, "range": "x"}, open(os.path.join(t, "legboard.json"), "w"))
        json.dump({"values": [["Key", "Game"], ["k", "Indianapolis Colts @ Houston Texans"], ["j", "Miami Dolphins @ Indianapolis Colts"]]}, open(os.path.join(t, "links.json"), "w"))
        json.dump({"values": [["Week", "Game"], ["9", "Indianapolis Colts @ Houston Texans"]]}, open(os.path.join(t, "legsnaps.json"), "w"))
        import gamelines as GLM
        ok(week_of(t) == 10 and set(schedule(t, 10)) == {frozenset(("MIA", "IND")), frozenset(("LAC", "BAL"))}, "the schedule is the newest season's week (last year's Colts @ Texans in Week 10 does not count)")
        chk = clean(t, write=False)
        ok(chk == {"legboard.json": {"Indianapolis Colts @ Houston Texans": 1}, "links.json": {"Indianapolis Colts @ Houston Texans": 1}} and len(json.load(open(os.path.join(t, "legboard.json")))["values"]) == 4, "--check reports and changes nothing")
        out = clean(t)
        d = json.load(open(os.path.join(t, "legboard.json")))
        ok(out == chk and [r[0] for r in d["values"]] == ["Player", "A", "C"] and d.get("range") == "x", "clean drops next week's rows, keeps the header, short rows and the file's other keys")
        ok([r[0] for r in json.load(open(os.path.join(t, "links.json")))["values"]] == ["Key", "j"], "a dump without a kickoff column is judged on the pair")
        ok(len(json.load(open(os.path.join(t, "legsnaps.json")))["values"]) == 2, "archives of earlier weeks are not touched")
        ok(clean(t) == {}, "a second run finds nothing left to drop")
        ok(clean(t, week=30) == {}, "a week with no schedule touches nothing")
        ok("1 legboard rows" in report(out) and "1 links rows" in report(out) and "Colts @ Houston" in report(out) and "1 game(s)" in report(out), "the report names the files, the counts and the game")
    print(f"{n[0]} passed, {n[1]} failed"); return 1 if n[1] else 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest": sys.exit(selftest())
    IN = os.path.join(HERE, "in")
    print(report(clean(IN, write="--check" not in sys.argv[1:])))
