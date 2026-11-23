"""The Premier League grader (sports/epl/grade.py): lock at kickoff, grade the match from ESPN's final, grade the players when the data set
has them, keep the record.

Owner 11/22 9:32 PM, after the NBA grader: "Get to what's next" - the /epl/ preview went up saying "Nothing here is a pick"; this is the
grading that has to come before anything there is one. Everything here is made-up data in a temporary folder; no network, no browser.

What must hold:
  - a match is locked from the LAST board built BEFORE its kickoff, once, and never touched again;
  - with no board from before kickoff in reach the match is MISSED and never graded;
  - a locked match is graded when ESPN calls it final, once; a match ESPN calls postponed is set aside, not graded;
  - players are graded later, when their results arrive, and ONLY THOSE WHO STARTED (every player number is "if he starts");
    a player who came on or did not play is counted, not graded; with the two sources disagreeing on the score, nobody is graded;
  - model and "every match alike", and model and season average, are compared on the same matches and players; totals are the sum of the rounds;
  - a record that cannot be read is left exactly as it is - and the kickoff is still locked.

  python3 tests/epl_grade.py
"""
import copy, datetime as dt, json, math, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, ".."))
from sports.epl import grade as G
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
T = lambda h, m=0, d=28: dt.datetime(2026, 11, d, h, m, tzinfo=dt.timezone.utc)
iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
near = lambda a, b, tol=1e-3: abs(a - b) <= tol
BASE = {"xg": {"home": 1.54, "away": 1.27}, "p": {"home": 0.42, "draw": 0.28, "away": 0.30, "over15": 0.78, "over25": 0.53, "over35": 0.31, "btts": 0.58}}


def match(mid, espn, key, ko, home=0.50, gw=12):
    h, a = key.split("-")
    return {"id": mid, "espn": espn, "key": key, "gw": gw, "ko": ko.strftime("%Y-%m-%dT%H:%MZ"), "home": h, "away": a, "state": "pre", "line": {"by": "DraftKings", "details": f"{h} +110"},
            "xg": {"home": 1.7, "away": 1.1}, "p": {"home": home, "draw": 0.25, "away": round(0.75 - home, 4), "over15": 0.78, "over25": 0.55, "over35": 0.30, "btts": 0.56},
            "scores": [["1-1", 0.12]], "shots": {"home": 14.0, "away": 11.0}, "lineups": True}


def player(pid, team, mid, **kw):
    p = {"id": pid, "name": "P" + pid, "team": team, "match": mid, "pos": "MID", "xi": None, "starts5": 0, "start_min": 80, "p_goal": 0.10, "p_assist": 0.10, "shots": 1.0, "sot": 0.4,
         "ladder": {"shots": [[1, 0.63], [2, 0.26]], "sot": [[1, 0.33]]}, "mins": 0, "tot": {"goals": 0, "assists": 0, "shots": 0, "sot": 0}, "status": None}
    p.update(kw); return p


def board(built, home=0.50, extra=()):
    ms = [match("m1", "9001", "AAA-BBB", T(15), home), match("m2", "9002", "CCC-DDD", T(17, 30), home), match("m3", "9003", "EEE-FFF", T(13), home)] + list(extra)
    ps = [player("101", "AAA", "m1", pos="FWD", xi="start", starts5=5, p_goal=0.40, p_assist=0.20, shots=3.0, sot=1.2, mins=900, tot={"goals": 5, "assists": 2, "shots": 30, "sot": 12},
                 ladder={"shots": [[1, 0.95], [2, 0.80], [3, 0.58], [4, 0.35]], "sot": [[1, 0.70], [2, 0.34], [3, 0.12]]}),
          player("102", "AAA", "m1", xi="start", starts5=4, start_min=85, p_goal=0.10, p_assist=0.15, mins=100, tot={"goals": 1, "assists": 0, "shots": 2, "sot": 1}),
          player("103", "BBB", "m1", pos="FWD", starts5=3, start_min=75, p_goal=0.30, mins=600, tot={"goals": 3, "assists": 1, "shots": 15, "sot": 6}),
          player("104", "BBB", "m1", pos="DEF", starts5=1, p_goal=0.03),
          player("201", "CCC", "m2", starts5=5), player("301", "EEE", "m3", starts5=5)]
    ps += [player("4" + m["id"][1:], m["home"], m["id"], starts5=5, mins=900, tot={"goals": 2, "assists": 2, "shots": 10, "sot": 4}) for m in extra]
    return {"sport": "epl", "format": 1, "built": iso(built), "base": BASE, "matches": ms, "players": ps}


def ev(eid, state="pre", h=None, a=None, detail=None):
    return {"id": eid, "state": state, "done": state == "post", "detail": detail or {"pre": "Scheduled", "in": "63'", "post": "FT"}[state],
            "teams": [{"ha": "home", "abbr": "H", "score": None if h is None else str(h)}, {"ha": "away", "abbr": "A", "score": None if a is None else str(a)}]}


d = tempfile.mkdtemp(); F = os.path.join(d, "epl")
try:
    said = []
    b0, bA, bC = board(T(14, 0), home=0.45), board(T(14, 40), home=0.50), board(T(15, 5), home=0.99)
    boards = [("the feed", bC), ("the feed, one run earlier", bA), ("the published page", b0)]

    # ---- the pieces
    sa = G.season_average(bA["players"][0])
    check(near(sa["p_goal"], 1 - math.exp(-5 * 80 / 900)) and near(sa["p_assist"], 1 - math.exp(-2 * 80 / 900)) and near(sa["shots"], 30 * 80 / 900, 0.01) and near(sa["sot"], 12 * 80 / 900, 0.01)
          and G.season_average(bA["players"][1]) is None,
          f"a season average is his season totals scaled to one start's minutes ({sa}); with under {G.MIN_BASE_MINUTES} minutes played there is none")
    check([G.regular(p) for p in bA["players"][:4]] == [True, True, True, False] and not G.regular({"xi": "bench", "starts5": 5}) and G.regular({"xi": "start", "starts5": 0}),
          "a regular is in the confirmed eleven, or - before it is posted - has three or more starts in the last five")
    check(G.final_score(None) is None and G.final_score(ev("1", "pre")) is None and G.final_score(ev("1", "in", 1, 0)) is None and G.final_score(ev("1", "post", 2, 1)) == {"home": 2, "away": 1}
          and G.final_score(ev("1", "post", detail="Postponed")) == "void" and G.final_score(ev("1", "pre", detail="Abandoned")) == "void" and G.final_score(dict(ev("1", "post", 2, 1), done=False)) is None,
          "ESPN's word: nothing until the match is over, the score once it is final, and 'set aside' when it is postponed or abandoned")

    # ---- 3:10 PM: one kickoff has passed with a board from before it, one passed before any board, one is still to come
    r = G.run(F, boards, scoreboard={"events": [ev("9001", "in", 1, 0), ev("9002"), ev("9003", "post", 0, 0)]}, now=T(15, 10), say=said.append)
    L = json.load(open(os.path.join(F, "locks", "2026-11-28.json")))["matches"]
    check(sorted(x[1:] for x in r["new"]) == [("m1", "locked"), ("m3", "missed")] and "m2" not in L and L["m1"]["board_built"] == iso(T(14, 40)) and L["m1"]["source"] == "the feed, one run earlier"
          and L["m1"]["minutes_before_ko"] == 20 and L["m1"]["p"]["home"] == 0.50 and L["m1"]["base"] == BASE and L["m1"]["lineups"] is True and [p["id"] for p in L["m1"]["players"]] == ["101", "102", "103", "104"],
          "a match is locked once its kickoff has passed, from the LATEST board built BEFORE kickoff - not the newer one built after it, not the older one - with its own players only")
    check(L["m3"].get("missed") is True and "players" not in L["m3"] and "no board built before kickoff" in L["m3"]["why"], "a match that kicked off before any board in reach was built is marked missed, with no numbers kept")
    p1 = L["m1"]["players"][0]
    check(p1["reg"] is True and p1["xi"] == "start" and p1["p_goal"] == 0.40 and p1["ladder"]["shots"][2] == [3, 0.58] and near(p1["base"]["p_goal"], sa["p_goal"]) and L["m1"]["players"][1]["base"] is None
          and L["m1"]["players"][3]["reg"] is False, "a locked player keeps his chances, his ladders, whether the board had him as a regular, and his season average on the same minutes")
    rec = json.load(open(os.path.join(F, "record.json")))
    check(rec["total"]["matches"] == 0 and rec["waiting"] == 1 and rec["pwaiting"] == 0 and rec["missed"] == {"m3": "2026-11-28"} and rec["graded"] == {} and G.summary(rec) is None and G.wanted(F) == ["m1"],
          "while the match is being played nothing is graded: the record says one is waiting and one was missed - a missed match is never graded, final score or not")

    # ---- 5:00 PM: full time, 2-1. The match is graded; the players wait for the data set
    lock_before = json.dumps(L["m1"], sort_keys=True)
    r = G.run(F, [("the feed", board(T(16, 55), home=0.10))] + boards, scoreboard={"events": [ev("9001", "post", 2, 1), ev("9002"), ev("9003", "post", 0, 0)]}, now=T(17, 0), say=said.append)
    rec = json.load(open(os.path.join(F, "record.json"))); t = rec["total"]
    check(r["graded"] == ["m1"] and r["new"] == [] and t["matches"] == 1 and t["pmatches"] == 0 and rec["graded"] == {"m1": "2026-11-28"} and rec["waiting"] == 0 and rec["pwaiting"] == 1 and rec["since"] == "2026-11-28",
          "at full time the match is graded, once; its players are now what is waiting")
    R_ = t["res"]
    check(R_["n"] == 1 and near(R_["brier"], 0.375) and near(R_["base"], 0.5048) and near(R_["ll"], -math.log(0.5)) and near(R_["bll"], -math.log(0.42)) and R_["top"] == 1 and R_["btop"] == 1,
          f"home, draw or away, by hand: a 50/25/25 call on a home win scores 0.375, 'every match alike' at 42/28/30 scores 0.5048 ({R_['brier']}, {R_['base']})")
    check(near(t["o25"]["brier"], 0.2025) and near(t["o25"]["base"], 0.2209) and t["o25"]["hit"] == 1 and near(t["btts"]["brier"], 0.1936) and near(t["btts"]["base"], 0.1764) and t["btts"]["hit"] == 1
          and t["goals"]["n"] == 2 and near(t["goals"]["model"], 0.4) and near(t["goals"]["base"], 0.73) and near(t["goals"]["err"], 0.2),
          "over 2.5, both to score and each side's goals are scored the same way for the model and for 'every match alike'")
    check(t["cal"] == [[0, 0, 0.0], [3, 0, 0.8], [3, 3, 1.61], [1, 1, 0.78], [0, 0, 0.0]], f"all seven match chances go into the band of the chance that was given, with whether they happened ({t['cal']})")
    L2 = json.load(open(os.path.join(F, "locks", "2026-11-28.json")))["matches"]["m1"]
    keep = {k: v for k, v in L2.items() if k not in ("final", "result")}
    check(json.dumps(keep, sort_keys=True) == lock_before and L2["final"] == {"home": 2, "away": 1} and L2["result"] == "home",
          "the lock is not touched by later boards (one built after kickoff gave the home side 10%): only the final score is written beside it")
    gf = json.load(open(os.path.join(F, "graded-gw12.json")))
    check(gf["gw"] == 12 and gf["matches"]["m1"]["final"] == {"home": 2, "away": 1} and gf["matches"]["m1"]["rows"] is None and gf["matches"]["m1"]["p"]["home"] == 0.50, "the gameweek's file has the match, its locked chances and its final, with the players still to come")

    # ---- 5:40 PM: the second match has kicked off - and ESPN says it is postponed
    r = G.run(F, [("the feed", bC)], scoreboard={"events": [ev("9001", "post", 2, 1), ev("9002", "post", detail="Postponed")]}, now=T(17, 40), say=said.append)
    rec = json.load(open(os.path.join(F, "record.json")))
    L = json.load(open(os.path.join(F, "locks", "2026-11-28.json")))["matches"]
    check(r["void"] == ["m2"] and L["m2"]["void"] is True and "Postponed" in L["m2"]["why"] and rec["void"] == {"m2": "2026-11-28"} and rec["total"]["matches"] == 1 and rec["waiting"] == 0 and G.wanted(F) == ["m1"],
          "a locked match ESPN calls postponed is set aside: not graded, not waiting")

    # ---- 11:00 PM: the data set has the match. Starters are graded; the substitute and the absentee are counted
    act = {"m1": {"final": {"home": 2, "away": 1}, "players": {"101": {"min": 90, "started": True, "g": 1, "a": 0, "sh": 4, "sot": 2}, "102": {"min": 90, "started": True, "g": 0, "a": 1, "sh": 0, "sot": 0},
                                                              "103": {"min": 20, "started": False, "g": 1, "a": 0, "sh": 2, "sot": 1}, "999": {"min": 90, "started": True, "g": 0, "a": 0, "sh": 1, "sot": 0}}}}
    r = G.run(F, [("the feed", bC)], scoreboard={"events": [ev("9001", "post", 2, 1)]}, actuals=act, now=T(23), say=said.append)
    rec = json.load(open(os.path.join(F, "record.json"))); P = rec["total"]["pl"]
    check(r["players"] == [("m1", 2, 1, 1)] and rec["total"]["pmatches"] == 1 and rec["pgraded"] == {"m1": "2026-11-28"} and rec["pwaiting"] == 0 and G.wanted(F) == []
          and (P["n"], P["sub"], P["dnp"], P["reg"], P["reg_start"]) == (2, 1, 1, 3, 2),
          "when the results arrive: 2 starters graded, 1 who came on and 1 who did not play counted and not graded (the substitute scored - it does not count for or against); 2 of the 3 regulars started")
    g, a_ = P["goal"], P["assist"]
    check((g["n"], g["hit"], g["bn"]) == (2, 1, 1) and near(g["exp"], 0.50) and near(g["brier"], 0.36) and near(g["base"], (sa["p_goal"] - 1) ** 2)
          and (a_["n"], a_["hit"], a_["bn"]) == (2, 1, 1) and near(a_["exp"], 0.35) and near(a_["brier"], 0.04) and near(a_["base"], sa["p_assist"] ** 2),
          "to score and an assist: every starter goes into expected-against-happened; the model is scored beside the season average only for the starter who has one")
    check(P["shots"]["n"] == 1 and near(P["shots"]["model"], 1.0) and near(P["shots"]["base"], abs(sa["shots"] - 4), 0.01) and near(P["shots"]["err"], 1.0) and near(P["sot"]["model"], 0.8) and near(P["sot"]["base"], abs(sa["sot"] - 2), 0.01)
          and P["min"] == {"n": 2, "abs": 15.0, "err": 15.0},
          "shots and shots on target are the average miss for the model and the season average on the same starter; minutes are scored for both starters")
    check(P["cal"]["goal"] == [[0, 0, 0.0], [0, 0, 0.0], [1, 0, 0.1], [0, 0, 0.0], [1, 1, 0.4]] and P["cal"]["assist"] == [[0, 0, 0.0], [0, 0, 0.0], [1, 1, 0.15], [1, 0, 0.2], [0, 0, 0.0]]
          and P["cal"]["shots"] == [[0, 0, 0.0], [2, 1, 0.61], [1, 1, 0.58], [1, 0, 0.63], [2, 2, 1.75]] and P["cal"]["sot"] == [[1, 0, 0.12], [2, 1, 0.67], [0, 0, 0.0], [1, 1, 0.7], [0, 0, 0.0]],
          f"each chance to score, each chance of an assist and every rung of the shot ladders goes into its band with whether it happened ({P['cal']['shots']})")
    rows = json.load(open(os.path.join(F, "graded-gw12.json")))["matches"]["m1"]["rows"]
    check([(x["id"], x["started"]) for x in rows] == [("101", True), ("102", True), ("103", False), ("104", False)] and rows[0]["got"] == {"min": 90, "g": 1, "a": 0, "sh": 4, "sot": 2} and rows[0]["said"]["p_goal"] == 0.40
          and rows[2]["got"] == {"min": 20} and rows[3]["got"] is None, "the gameweek's file now has every locked player: what the board said and what he did, or that he did not start")
    S = G.summary(rec)
    check(S["matches"] == 1 and S["pmatches"] == 1 and near(S["res"]["model"], 0.375) and near(S["res"]["base"], 0.5048) and S["res"]["top"] == 1 and near(S["goals"]["model"], 0.2) and near(S["goals"]["base"], 0.365)
          and S["pl"]["n"] == 2 and near(S["pl"]["goal"]["model"], 0.36) and near(S["pl"]["shots"]["model"], 1.0) and near(S["pl"]["min"]["mae"], 7.5),
          "the summary the page draws from is the means of those sums")

    # ---- the same run again changes nothing
    before = {f: open(os.path.join(F, f)).read() for f in ("record.json", "graded-gw12.json", os.path.join("locks", "2026-11-28.json"))}
    r = G.run(F, [("the feed", bC)], scoreboard={"events": [ev("9001", "post", 2, 1), ev("9003", "post", 0, 0)]}, actuals=act, now=T(23, 30), say=said.append)
    check(r["graded"] == [] and r["players"] == [] and r["new"] == [] and all(open(os.path.join(F, f)).read() == v for f, v in before.items()), "a later run with the same results grades nothing twice and rewrites nothing")

    # ---- another gameweek; the two sources disagree on one score
    m5, m6 = match("m5", "9005", "GGG-HHH", T(15, 0, 29), 0.30, gw=13), match("m6", "9006", "III-JJJ", T(15, 0, 29), 0.60, gw=13)
    b2 = board(T(14, 30, 29), extra=[m5, m6])
    sb2 = {"events": [ev("9005", "post", 0, 2), ev("9006", "post", 1, 1)]}
    act2 = {"m5": {"final": {"home": 0, "away": 2}, "players": {"45": {"min": 90, "started": True, "g": 0, "a": 0, "sh": 1, "sot": 0}}},
            "m6": {"final": {"home": 2, "away": 1}, "players": {"46": {"min": 90, "started": True, "g": 2, "a": 0, "sh": 3, "sot": 2}}}}
    r = G.run(F, [("the feed", b2)], scoreboard=sb2, actuals=act2, now=T(18, 0, 29), say=said.append)
    rec = json.load(open(os.path.join(F, "record.json")))
    check(sorted(r["graded"]) == ["m5", "m6"] and [x[0] for x in r["players"]] == ["m5"] and r["notes"] and "III-JJJ" in r["notes"][0] and "1-1" in r["notes"][0] and "2-1" in r["notes"][0] and rec["pwaiting"] == 1
          and "m6" not in rec["pgraded"], "when ESPN and the data set disagree on a score the match keeps ESPN's result and its players are left ungraded, and the run says so")
    tot = G.empty()
    for x in rec["rounds"]: G.add(tot, x)
    check([x["gw"] for x in rec["rounds"]] == [12, 13] and [x["matches"] for x in rec["rounds"]] == [1, 2] and [x["ids"] for x in rec["rounds"]] == [["m1"], ["m5", "m6"]] and [x["pids"] for x in rec["rounds"]] == [["m1"], ["m5"]]
          and G.rounded(tot) == rec["total"] and rec["total"]["matches"] == 3 and rec["total"]["res"]["top"] == 2 and rec["total"]["res"]["btop"] == 1,
          "one row per gameweek, each match named once, and the totals are exactly the sum of the rows (the model's likeliest result came in twice in three, the home side once)")

    # ---- a record that cannot be read is left alone - and the kickoff is still locked
    recp = os.path.join(F, "record.json"); good = open(recp).read()
    open(recp, "w").write("{ not json")
    m7 = match("m7", "9007", "KKK-LLL", T(12, 0, 30), 0.40, gw=13)
    r = G.run(F, [("the feed", board(T(11, 30, 30), extra=[m7]))], scoreboard={"events": [ev("9007", "post", 3, 0)]}, now=T(14, 0, 30), say=said.append)
    L30 = json.load(open(os.path.join(F, "locks", "2026-11-30.json")))["matches"]
    check(open(recp).read() == "{ not json" and r["record"] is None and r["graded"] == [] and ("m7", "locked") in [x[1:] for x in r["new"]] and "m7" in L30 and "cannot be read" in said[-1],
          "a record file that cannot be read is left exactly as it is and nothing is graded - but the match that kicked off is still locked, so it can be graded once the record is mended")
    open(recp, "w").write(good)
    r = G.run(F, [("the feed", board(T(13, 55, 30), extra=[m7]))], scoreboard={"events": [ev("9007", "post", 3, 0)]}, now=T(14, 15, 30), say=said.append)
    check(r["graded"] == ["m7"] and json.load(open(recp))["total"]["matches"] == 4, "with the record readable again, that match is graded from the lock taken while it was not")

    # ---- a match the record already holds is never locked again; old locks and old gameweek files go
    for f in os.listdir(os.path.join(F, "locks")): os.remove(os.path.join(F, "locks", f))
    r = G.run(F, [("the feed", board(T(14, 30, 29), extra=[m5]))], scoreboard=sb2, now=T(19, 0, 29), say=said.append)
    check(not any(x[1] in ("m1", "m5") for x in r["new"]) and json.load(open(recp))["total"]["matches"] == 4, "with its lock file gone, a match already in the record is not locked or graded a second time")
    for gw in (8, 9, 10, 11): G.save(os.path.join(F, f"graded-gw{gw:02d}.json"), {"gw": gw, "matches": {}})
    G.save(os.path.join(F, "locks", "2026-11-10.json"), {"day": "2026-11-10", "matches": {"old": {"id": "old", "missed": True}}})
    G.run(F, [], now=T(12, 0, 30), say=said.append)
    left_g = sorted(f for f in os.listdir(F) if f.startswith("graded-")); left_l = sorted(os.listdir(os.path.join(F, "locks")))
    check("2026-11-10.json" not in left_l and len(left_g) == G.KEEP_ROUND_FILES and left_g[-1] == "graded-gw13.json" and not any(f.endswith(".tmp") for f in os.listdir(F) + left_l),
          f"locks older than {G.KEEP_LOCK_DAYS} days are dropped and only the last {G.KEEP_ROUND_FILES} gameweek files are kept; no half-written file is left behind")
    check(all(s.startswith("epl grade:") for s in said) and any("locked 1, missed 1" in s for s in said) and any("players of 1 (m1: 2 starters, 1 came on, 1 did not play)" in s for s in said),
          "every run says in one line what it locked, graded and is waiting for")

    # ---- the board builder's side: what the data set has for a match (needs pandas, as the job has)
    try:
        import pandas as pd
        from sports.epl import publish as PB
    except Exception as e:
        check(True, f"(pandas is not here, so the data-set reader is not exercised: {type(e).__name__})")
    else:
        m = pd.DataFrame([{"match_id": "x1", "finished": True, "home_score": 2.0, "away_score": 1.0}, {"match_id": "x2", "finished": False, "home_score": None, "away_score": None},
                          {"match_id": "x3", "finished": True, "home_score": 0.0, "away_score": 0.0}])
        rows = [{"match_id": "x1", "player_code": 100 + i, "min": 90, "started": i < 22, "goals": 1 if i == 0 else 0, "assists": 0, "shots": 2, "sot": 1} for i in range(27)]
        rows += [{"match_id": "x3", "player_code": 300 + i, "min": 90, "started": True, "goals": 0, "assists": 0, "shots": 0, "sot": 0} for i in range(12)]
        got = PB.actuals_for(m, pd.DataFrame(rows), ["x1", "x2", "x3", "nope"])
        check(list(got) == ["x1"] and got["x1"]["final"] == {"home": 2, "away": 1} and len(got["x1"]["players"]) == 27 and got["x1"]["players"]["100"] == {"min": 90, "started": True, "g": 1, "a": 0, "sh": 2, "sot": 1}
              and got["x1"]["players"]["126"]["started"] is False,
              "the data set's results are handed over only for a finished match with its starters on file: not one still to finish, not one with half its players missing")
finally:
    shutil.rmtree(d, ignore_errors=True)
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
