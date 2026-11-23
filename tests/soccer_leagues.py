"""The other soccer leagues - Bundesliga, La Liga, Serie A, MLS - from the job's ESPN files to the four pages. PREVIEWS, as the Premier League's.

Owner 11/23 1:10 AM: "get to building Bundesliga, La Liga, Serie A, and MLS. We'd have NFL, College Football, NBA and Soccer (with these
different leagues)."

Part one, on a made-up league in a temporary folder (no network, no browser):
  - the board builder (sports/soccer/publish.py): the shot-based stand-in for expected goals, which matches are listed and which are
    left off and why, each match's round, whose player a player is, who is listed, the confirmed elevens, what is handed to the grader;
  - the whole step run as the job runs it: a board written, a match locked at kickoff from the board built before it, graded at full
    time, its starters graded from the season file; a league that fails keeps its last board and does not stop the next;
  - the page builder (build_soccer.py): a page only for a board that can be used, the league's own record or none;
  - the wiring: the build list, the small publish for a league's folder, the job's step.
Part two: every league page in SITE is read by the Premier League page's own test (LEAGUE=<folder> tests/epl_board.py) - every card,
every player row, the switch and the league row, at 390x844 in light and dark and on a desktop - with what differs for these leagues.

    python3 tests/soccer_leagues.py [shots_dir]
"""
import contextlib, copy, datetime as dt, io, json, math, os, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); TREE = os.path.join(HERE, ".."); sys.path.insert(0, TREE)
ROOT = os.environ.get("SITE") or os.path.join(TREE, "site"); SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
from sports.soccer import publish as S
from sports.epl import grade as G
import build_epl as K, build_soccer as BS, build_nba as N, sport_nav, switch_want
near = lambda a, b, tol=1e-3: abs(a - b) <= tol
UTC = dt.timezone.utc
iso = lambda t: t.strftime("%Y-%m-%dT%H:%MZ")

# ------------------------------------------------------------------------------------------------------------ a made-up league
CLUBS = [("11", "AAA", 1.9), ("12", "BBB", 1.5), ("13", "CCC", 1.2), ("14", "DDD", 1.0), ("15", "EEE", 0.8), ("16", "FFF", 0.6)]
STR = {c: s for c, _, s in CLUBS}; AB = {c: a for c, a, _ in CLUBS}
PLACES = ["G", "LB", "CD-L", "CD-R", "RB", "LM", "CM-L", "CM-R", "RM", "CF-L", "CF-R"]          # ESPN's formation places, eleven of them
NOW = dt.datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def lines(tid, rnd, goals, sh, sot):
    """one club's player lines for a match: [team, player, name, place, started, minutes, goals, assists, shots, on target, yellow, red]"""
    out = []
    for k, place in enumerate(PLACES, 1):
        pid = f"{tid}{k:02d}"; name = f"{AB[tid]} Player {k}"
        if k == 11:                                           # the second forward's shirt changes hands at the halfway point of the season
            if tid == "16": pid, name = ("9001", "Moved Striker") if rnd < 5 else ("1611", "FFF Player 11")
            if tid == "11": pid, name = ("1111", "AAA Player 11") if rnd < 5 else ("9001", "Moved Striker ")      # ESPN's stray trailing space
        g = goals if k == 10 else 0
        a = min(goals, 1) if k == 6 else 0
        s, o = ((sh // 2, max(goals, sot // 2)) if k == 10 else ((2, 1) if k == 11 else ((1, 0) if k == 6 else (0, 0))))
        out.append([tid, pid, name, place, 1, 70 if k == 11 else 90, g, a, s, o, 0, 0])
    out.append([tid, f"{tid}12", f"{AB[tid]} Sub", "SUB", 0, 20, 0, 0, 1, 0, 0, 0])                # comes on for the second forward every match
    if rnd < 2: out.append([tid, f"{tid}13", f"{AB[tid]} Fringe", "SUB", 0, 5, 0, 0, 0, 0, 0, 0])   # two cameos in August, nothing since
    return out


def season():
    ids = [c for c, _, _ in CLUBS]; rounds = []
    order = ids[:]
    for r in range(5):                                         # the circle method: five rounds, every pair once
        rounds.append([(order[i], order[5 - i]) for i in range(3)])
        order = [order[0]] + [order[-1]] + order[1:-1]
    rounds += [[(b, a) for a, b in rd] for rd in rounds]       # and again with the sides swapped
    M = {}
    for r, rd in enumerate(rounds):
        d = dt.datetime(2026, 9, 1, 18, 0, tzinfo=UTC) + dt.timedelta(days=7 * r)
        for j, (h, a) in enumerate(rd):
            hs = min(4, max(0, round(1.1 * STR[h] - 0.5 * STR[a] + 0.6))); as_ = min(4, max(0, round(0.9 * STR[a] - 0.5 * STR[h] + 0.4)))
            st = {}
            for me, opp in ((h, a), (a, h)):
                st[me] = {"sh": float(8 + round(4 * STR[me]) - round(STR[opp])), "sot": float(2 + round(2 * STR[me]))}
            M[f"m{r}{j}"] = {"d": iso(d), "h": h, "a": a, "hs": hs, "as": as_, "st": st,
                             "p": lines(h, r, hs, int(st[h]["sh"]), int(st[h]["sot"])) + lines(a, r, as_, int(st[a]["sh"]), int(st[a]["sot"]))}
    return {"matches": M, "teams": [{"id": c, "abbr": a, "name": a + " United", "short": a + " Utd", "color": "112233", "alt": "ffffff"} for c, a, _ in CLUBS] + [{"id": "99", "abbr": "NEW", "name": "Newcomers", "short": "Newcomers"}],
            "results_at": "2026-11-10T11:00:00Z", "season_at": "2026-11-10T11:00:00Z"}


def ev(eid, when, home, away, state="pre", detail=None, score=(None, None), odds=None):
    side = lambda tid, ha, sc: {"id": tid, "abbr": AB.get(tid, "NEW"), "short": AB.get(tid, "NEW") + " Utd", "color": "112233", "alt": "ffffff", "ha": ha, "score": None if sc is None else str(sc), "record": "5-2-3", "form": "WWDLW"}
    return {"id": eid, "date": iso(when), "state": state, "done": state == "post", "detail": detail or {"pre": "Scheduled", "in": "55'", "post": "FT"}[state], "venue": "The Ground",
            "teams": [side(home, "home", score[0]), side(away, "away", score[1])], "odds": odds}


def scoreboard(now=NOW, extra=()):
    d = lambda **kw: now + dt.timedelta(**kw)
    return {"mirrored": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "events": [
        ev("E1", d(days=2), "11", "16", odds={"by": "DraftKings", "details": "AAA -300", "spread": None, "total": 2.5, "home_ml": -300, "away_ml": 700, "draw_ml": 400}),
        ev("E2", d(days=3), "12", "13"),
        ev("E3", d(days=3, hours=2), "14", "15", detail="Postponed"),
        ev("E4", d(days=20), "13", "14"),
        ev("E5", d(days=4), "99", "12"),
        ev("E6", d(hours=-5), "15", "16", state="post", score=(1, 0)),
        ev("E7", d(hours=-1), "13", "15", state="in", score=(1, 1))] + list(extra)}


def put(folder, name, obj):
    os.makedirs(folder, exist_ok=True); json.dump(obj, open(os.path.join(folder, name), "w"))


def run_main(*argv):
    keep = sys.argv; buf = io.StringIO()
    try:
        sys.argv = ["publish"] + list(argv)
        with contextlib.redirect_stdout(buf): S.main()
    finally:
        sys.argv = keep
    return buf.getvalue()


def part_one():
    d = tempfile.mkdtemp()
    try:
        feeds = os.path.join(d, "feeds"); A = season()
        put(os.path.join(feeds, "bun"), "season.json", A); put(os.path.join(feeds, "bun"), "scoreboard.json", scoreboard())
        xi = [{"id": f"11{k:02d}", "pos": PLACES[k - 1]} for k in range(1, 10)] + [{"id": "9001", "pos": "CF-R"}, {"id": "1112", "pos": "CF-L"}]      # the usual sub starts up front; the first forward is on the bench
        put(os.path.join(feeds, "bun"), "lineups.json", {"mirrored": "2026-11-10T11:55:00Z", "matches": [{"id": "E1", "date": iso(NOW + dt.timedelta(days=2)), "state": "pre", "posted": True,
            "teams": [{"abbr": "AAA", "ha": "home", "xi": xi, "bench": [{"id": "1110"}]}, {"abbr": "FFF", "ha": "away", "xi": [{"id": f"16{k:02d}", "pos": PLACES[k - 1]} for k in range(1, 12)], "bench": [{"id": "1612"}]}]}]})

        # ---- the pieces
        check([S.position(x) for x in ("G", "GK", "CD-L", "LB", "RWB", "LM", "AM", "CM-R", "DM", "F", "CF-L", "ST", "SUB", "", None)] == ["GK", "GK", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "FWD", "FWD", "FWD", None, None, None],
              "ESPN's formation places become the page's four positions: keeper, defender, midfielder, forward; a substitute's 'SUB' is no position")
        wk = lambda s: S.week_key(S.when(s))
        check(wk("2026-11-28T14:30Z") == wk("2026-11-29T18:30Z") == wk("2026-12-01T01:00Z") == 20261124 and wk("2026-11-24T01:00Z") == 20261117 and wk("2026-11-25T03:00Z") == 20261124 and wk("2026-12-01T19:00Z") == 20261201,
              "a match's round is the week it is played in, Tuesday to Monday on the Central clock, named by its Tuesday: a weekend and its Monday night together (20261124), a Tuesday match with the weekend after it")

        # ---- specific positions (owner 11/23 7:37 AM: "forward/striker, Right wing/Right mid, center mid/center attacking mid, right back")
        from sports.soccer import roles as RL
        shape = lambda places: [RL.role(x, places) for x in places]
        e4231 = ["G", "LB", "CD-L", "CD-R", "RB", "LM", "RM", "AM-L", "AM", "AM-R", "F"]; e433 = ["G", "LB", "CD-L", "CD-R", "RB", "LM", "CM", "RM", "LF", "F", "RF"]
        e343 = ["G", "CD-L", "CD", "CD-R", "LM", "CM-L", "CM-R", "RM", "CF-L", "F", "CF-R"]; e3412 = ["G", "CD-L", "CD", "CD-R", "LM", "CM-L", "CM-R", "RM", "AM", "CF-L", "CF-R"]
        e442 = ["G", "LB", "CD-L", "CD-R", "RB", "LM", "CM-L", "CM-R", "RM", "CF-L", "CF-R"]; e4141 = ["G", "LB", "CD-L", "CD-R", "RB", "DM", "LM", "CM-L", "CM-R", "RM", "F"]
        e541 = ["G", "LB", "CD-L", "CD", "CD-R", "RB", "LM", "CM-L", "CM-R", "RM", "F"]; e4222 = ["G", "LB", "CD-L", "CD-R", "RB", "CM-L", "CM-R", "AM-L", "AM-R", "CF-L", "CF-R"]
        check(shape(e4231) == ["GK", "LB", "CB", "CB", "RB", "CDM", "CDM", "LW", "CAM", "RW", "ST"] and shape(e433) == ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CM", "LW", "ST", "RW"]
              and shape(e442) == ["GK", "LB", "CB", "CB", "RB", "LM", "CM", "CM", "RM", "ST", "ST"] and shape(e4141) == ["GK", "LB", "CB", "CB", "RB", "CDM", "LM", "CM", "CM", "RM", "ST"],
              "a back four, read by its shape: in a 4-2-3-1 ESPN's LM and RM are the two holding midfielders and AM-L / AM-R the wings; in a 4-3-3 LM and RM are the outer two of a midfield three and LF / RF the wings; "
              "in a 4-4-2 or 4-1-4-1 they are wide midfielders")
        check(shape(e343) == ["GK", "CB", "CB", "CB", "LWB", "CM", "CM", "RWB", "LW", "ST", "RW"] and shape(e3412) == ["GK", "CB", "CB", "CB", "LWB", "CM", "CM", "RWB", "CAM", "ST", "ST"]
              and shape(e541) == ["GK", "LWB", "CB", "CB", "CB", "RWB", "LM", "CM", "CM", "RM", "ST"] and shape(e4222) == ["GK", "LB", "CB", "CB", "RB", "CM", "CM", "CAM", "CAM", "ST", "ST"],
              "three centre-backs: LM and RM are wing-backs (or LB and RB are, when they play too); CF-L and CF-R are the wings beside a central striker and two strikers without one; a pair of AM-L / AM-R with no ten between them are two tens")
        check([RL.role(x, e442) for x in ("SW", "RCF", "M", "SUB", "", None, "XYZ")] == ["CDM", "ST", "CM", None, None, None, None] and set(RL.GROUP) == set(RL.ROLES) and all(r in RL.NAMES for r in RL.ROLES + ("SUB",))
              and [RL.GROUP[r] for r in ("GK", "RWB", "CDM", "CAM", "RW", "ST")] == ["GK", "DEF", "MID", "MID", "FWD", "FWD"],
              "the rarer places are read too (ESPN's SW is a holding midfielder where it appears); a substitute's 'SUB' and anything unknown give no role rather than a guess")
        check(RL.usual(["LB"] * 6 + ["LWB"] * 5) == "LWB" and RL.usual(["ST", "RW", "ST", "RW"]) == "RW" and RL.usual(["CM"] * 3 + ["CDM"]) == "CM" and RL.usual(["RW"] * 12 + ["ST"] * 10) == "ST" and RL.usual([]) is None and RL.usual([None]) is None,
              "a player's usual position is the one he has started most in his last ten starts, a tie going to the more recent; no start, no position")
        club = {RL.fold(n): n for n in ("Pascal Groß", "Ferdi Kadioglu", "Jay Da Silva", "Fatawu Issahaku", "Chema Andrés", "Gabriel Magalhães", "Gabriel Jesus", "Gabriel Martinelli", "Ben White", "Đorđe Petrović", "Martin Ødegaard")}
        f = lambda *names: club.get(RL.find(list(names), club))
        check(f("Pascal Gross") == "Pascal Groß" and f("Ferdi Kadıoğlu", "F.Kadıoğlu") == "Ferdi Kadioglu" and f("Jay Dasilva", "Dasilva") == "Jay Da Silva" and f("Abdul Fatawu", "Fatawu") == "Fatawu Issahaku"
              and f("José María Andrés Baixauli", "Andrés") == "Chema Andrés" and f("Gabriel dos Santos Magalhães", "Gabriel") == "Gabriel Magalhães" and f("Benjamin White", "White") == "Ben White"
              and f("Djordje Petrovic") == "Đorđe Petrović" and f("Martin Odegaard") == "Martin Ødegaard" and f("Gabriel") is None and f("Someone Else", "Else") is None and f("") is None and RL.fold("  Pascal   GROß-Müller ") == "pascal gross muller",
              "the same player under two spellings is found (Groß / Gross, Kadıoğlu, Dasilva / Da Silva, 'Fatawu' for Fatawu Issahaku, 'Andrés' for Chema Andrés); a name three men at the club share is matched to none of them")

        # ---- the board
        B = S.build("bun", feeds, NOW)
        sot = sum(m["st"][t]["sot"] for m in A["matches"].values() for t in (m["h"], m["a"])); off = sum(m["st"][t]["sh"] - m["st"][t]["sot"] for m in A["matches"].values() for t in (m["h"], m["a"]))
        goals = sum(m["hs"] + m["as"] for m in A["matches"].values()); k_off = goals / (3 * sot + off)
        check(B["standin"] == {"on_target": round(3 * k_off, 4), "off_target": round(k_off, 4)} and near(3 * k_off * sot + k_off * off, goals, 1e-6),
              f"the stand-in for expected goals: a shot on target counts three times one off target, scaled so the league's stand-in total is its goals ({goals} goals: {B['standin']['on_target']} and {B['standin']['off_target']} a shot)")
        check((B["sport"], B["league"], B["format"], B["n_clubs"], B["played"], B["with_players"], B["gameweeks"], B["no_availability"], B["data_through"]) == ("bun", "Bundesliga", K.FORMAT, 6, 30, 30, [], True, "2026-11-03")
              and K.usable(B, NOW, sport="bun")[0] and not K.usable(B, NOW, sport="epl")[0] and set(B["base"]) == {"xg", "p"} and near(sum(B["base"]["p"][k] for k in ("home", "draw", "away")), 1, 0.003),
              "the board is in the Premier League board's format under its own league's name, says it has no gameweeks and no injury list, and carries 'every match alike' for the grader")
        keys = [m["key"] for m in B["matches"]]
        check(keys == ["CCC-EEE", "AAA-FFF", "BBB-CCC"] and len(B["checks"]) == 2 and any("Postponed" in c and "DDD v EEE" in c for c in B["checks"]) and any("NEW v BBB" in c and "cannot be rated" in c for c in B["checks"]),
              f"listed: the match being played and the ones in the next {S.AHEAD_DAYS} days, in kickoff order; left off, each with a note: a postponed match and a club with no finished match (one that ended five hours ago and one twenty days out are simply not on it)")
        m1 = next(m for m in B["matches"] if m["key"] == "AAA-FFF"); m0 = B["matches"][0]
        check(m1["p"]["home"] > 0.6 > m1["p"]["away"] and m1["xg"]["home"] > m1["xg"]["away"] and all(near(m["p"]["home"] + m["p"]["draw"] + m["p"]["away"], 1, 0.003) for m in B["matches"])
              and m1["line"]["details"] == "AAA -300" and m1["line"]["draw_ml"] == 400 and m1["gw"] == S.week_key(NOW + dt.timedelta(days=2)) and m1["lineups"] is True and m1["espn"] == m1["id"] == "E1"
              and m0["state"] == "in" and m0["score"] == {"home": "1", "away": "1"} and m0["lineups"] is False and m1["score"] is None,
              f"the best side at home to the worst is a clear favorite ({m1['p']['home']:.0%} / {m1['p']['draw']:.0%} / {m1['p']['away']:.0%}); each match has its round, ESPN's posted line with the draw price, and its score once it is being played")
        T_ = B["teams"]
        check(T_["AAA"]["att"][0] == 1 and T_["FFF"]["att"][0] == 6 and T_["AAA"]["def"][0] < T_["FFF"]["def"][0] and T_["AAA"]["shots_for"][0] == 1 and all(t["out"] == [] and t["doubt"] == [] for t in T_.values())
              and set(T_) == {"AAA", "BBB", "CCC", "EEE", "FFF"} and T_["AAA"]["last"] and T_["AAA"]["record"] == "5-2-3",
              "the clubs on the board are ranked by attack, defence and shots from their own matches; nobody is out or a doubt, because no injury list is read")
        P = {(p["id"], p["match"]): p for p in B["players"]}
        mv = [p for p in B["players"] if p["id"] == "9001"]
        check(len(mv) == 1 and mv[0]["team"] == "AAA" and mv[0]["match"] == "E1" and mv[0]["apps"] == 5 and mv[0]["starts5"] == 5 and mv[0]["name"] == "Moved Striker" and mv[0]["full"] == "Moved Striker"
              and not any(p["id"] == "1111" for p in B["players"]) and ("1611", "E1") in P,
              "a player who changed clubs is his new club's player, on its matches alone, with his name tidied; the man he replaced, with no part in the club's last five, is not listed")
        sub, fr = P.get(("1112", "E1")), [p for p in B["players"] if p["id"].endswith("13")]
        check(sub and sub["starts5"] == 0 and sub["apps5"] == 5 and sub["pos"] == "MID" and not K.regular(dict(sub, xi=None)) and not fr and all(p["starts5"] >= 1 or p["apps5"] >= 1 for p in B["players"]),
              "a substitute with real minutes in the last five is listed (under the line, as not a regular); one with two cameos in August is not")
        f1, f2, dfn, gk = P[("1110", "E1")], P[("9001", "E1")], P[("1102", "E1")], P[("1101", "E1")]
        check(f1["pos"] == "FWD" and dfn["pos"] == "DEF" and gk["pos"] == "GK" and f1["p_goal"] > f2["p_goal"] > dfn["p_goal"] and f1["p_goal2"] < f1["p_goal"] and f1["shots"] >= f1["sot"] > 0
              and [r[1] for r in f1["ladder"]["shots"]] == sorted([r[1] for r in f1["ladder"]["shots"]], reverse=True) and f1["tot"]["goals"] == sum(m["hs"] if m["h"] == "11" else m["as"] for m in A["matches"].values() if "11" in (m["h"], m["a"]))
              and f1["mins"] == 900 and f1["start_min"] == 89 and f2["start_min"] == 72 and len(f1["recent"]) == 5 and f1["recent"][-1][0] == "11/3" and P[("1610", "E1")]["p_goal"] < P[("1110", "E1")]["p_goal"],
              f"player numbers: the scorer of all his club's goals has the best chance ({f1['p_goal']:.0%}), ahead of his strike partner and a defender; shots are no fewer than shots on target; minutes when starting come from his own starts")
        check((f1["role"], f2["role"], dfn["role"], gk["role"], P[("1106", "E1")]["role"], P[("1107", "E1")]["role"], P[("1109", "E1")]["role"], P[("1105", "E1")]["role"]) == ("ST", "ST", "LB", "GK", "LM", "CM", "RM", "RB")
              and sub["role"] == "ST" and P[("1612", "E1")]["role"] == "SUB" and all(p["role"] in RL.ROLES + ("SUB",) for p in B["players"]) and all(p["pos"] in ("GK", "DEF", "MID", "FWD") for p in B["players"])
              and [p["role"] for p in B["players"] if p["id"] == "1212"] == ["SUB"],
              "every row carries the player's specific position beside his group: from his starts (this league plays 4-4-2: ST, LM, CM, RM, LB, RB, GK), from tonight's eleven for a man who starts where he usually does not "
              "(the substitute picked up front is an ST for this match), and SUB for one who has only ever come off the bench")
        check((f1["xi"], f2["xi"], sub["xi"], dfn["xi"], P[("1602", "E1")]["xi"], P[("1612", "E1")]["xi"]) == ("bench", "start", "start", "start", "start", "bench") and all(p["xi"] is None for p in B["players"] if p["match"] != "E1")
              and K.regular(sub) and not K.regular(f1),
              "with the confirmed elevens in for one match, each of its players is marked in the eleven or on the bench - the usual substitute who starts becomes a regular, the forward left out does not - and other matches are untouched")
        few = copy.deepcopy(A); few["matches"] = dict(list(few["matches"].items())[:29]); put(os.path.join(feeds, "zzz"), "season.json", few); put(os.path.join(feeds, "zzz"), "scoreboard.json", scoreboard())
        try: S.build("zzz", feeds, NOW); raised = ""
        except ValueError as e: raised = str(e)
        check("29 finished matches" in raised, "with fewer than 30 finished matches on file a league is not rated at all (the start of a season): the step says so")
        act = S.actuals(A, ["m00", "nope"]); thin = copy.deepcopy(A); thin["matches"]["m00"]["p"] = thin["matches"]["m00"]["p"][:15]
        m00 = A["matches"]["m00"]
        check(list(act) == ["m00"] and act["m00"]["final"] == {"home": m00["hs"], "away": m00["as"]} and len(act["m00"]["players"]) == 26 and act["m00"]["players"]["1110"] == {"min": 90, "started": True, "g": m00["hs"], "a": 0, "sh": int(m00["st"]["11"]["sh"]) // 2, "sot": max(m00["hs"], int(m00["st"]["11"]["sot"]) // 2)}
              and act["m00"]["players"]["1112"]["started"] is False and S.actuals(thin, ["m00"]) == {} and S.actuals(A, []) == {},
              "the grader is handed a finished match's score and every player who played, only when at least 20 starters are on file")

        # ---- the step as the job runs it: board, lock at kickoff, grade at full time
        out = os.path.join(d, "out"); prev = os.path.join(d, "prev"); site = os.path.join(d, "site")
        ko = NOW + dt.timedelta(days=2); t = lambda **kw: (ko + dt.timedelta(**kw)).strftime("%Y-%m-%dT%H:%M:%SZ")
        log1 = run_main("--feeds", feeds, "--out", out, "--prev", prev, "--site", site, "--only", "bun", "--now", t(minutes=-30))
        b1 = json.load(open(os.path.join(out, "bun", "board.json"))); r1 = json.load(open(os.path.join(out, "bun", "record.json")))
        check("bun board: 2 matches" in log1 and "bun grade: locked 0" in log1 and b1["sport"] == "bun" and r1["sport"] == "bun" and r1["total"]["matches"] == 0 and not os.path.exists(os.path.join(out, "epl")),
              "run as the job runs it, the step writes the league's board in its own folder and starts its own grading record there")
        # ---- a board that says nothing new is not written again (each new copy stays on the branch, and each changed page in the site's history)
        first = open(os.path.join(out, "bun", "board.json"), "rb").read()
        outA, prevA = os.path.join(d, "outA"), os.path.join(d, "prevA"); shutil.copytree(os.path.join(out, "bun"), os.path.join(prevA, "bun"))
        logA = run_main("--feeds", feeds, "--out", outA, "--prev", prevA, "--site", site, "--only", "bun", "--no-grade", "--now", t(minutes=-20))
        sameA = open(os.path.join(outA, "bun", "board.json"), "rb").read() == first
        sbp = scoreboard(); next(e for e in sbp["events"] if e["id"] == "E1")["odds"]["details"] = "AAA -320"; put(os.path.join(feeds, "bun"), "scoreboard.json", sbp)
        outB = os.path.join(d, "outB")
        logB = run_main("--feeds", feeds, "--out", outB, "--prev", prevA, "--site", site, "--only", "bun", "--no-grade", "--now", t(minutes=-15)); bB = json.load(open(os.path.join(outB, "bun", "board.json")))
        put(os.path.join(feeds, "bun"), "scoreboard.json", scoreboard())
        nums = lambda b: ([(m["id"], m["xg"], m["p"]) for m in b["matches"] if m["id"] == "E1"], [(p["id"], p["p_goal"], p["p_assist"], p["shots"], p["sot"]) for p in b["players"] if p["match"] == "E1"])
        check(sameA and "unchanged since" in logA and "unchanged" not in logB and bB["built"] == t(minutes=-15) and next(m for m in bB["matches"] if m["id"] == "E1")["line"]["details"] == "AAA -320"
              and K.signature(bB) == K.signature(b1) and nums(bB) == nums(b1) == nums(S.build("bun", feeds, NOW + dt.timedelta(hours=2))),
              "ten minutes later with nothing new, the last board is written again byte for byte; a price that ticks (AAA -300 to -320) makes a new board but not a new page - the page's signature holds - "
              "and no number moves with the clock: matches are weighed as of the latest result")
        bt = S.when(b1["built"]); b9 = copy.deepcopy(b1); b9["matches"][0]["xg"]["home"] += 0.01
        check(S.same_board(dict(b1, built="x", espn_at="y"), b1, bt + dt.timedelta(hours=5)) and not S.same_board(b1, b1, bt + dt.timedelta(hours=S.KEEP_HOURS, minutes=1)) and not S.same_board(b9, b1, bt + dt.timedelta(hours=1))
              and not S.same_board(b1, None, bt) and not S.same_board(b1, b1, bt - dt.timedelta(hours=1)),
              f"an unchanged board is kept for at most {S.KEEP_HOURS} hours, then written under a new stamp (the page wants a board built in the last day); any number that differs makes a new one")
        shutil.copytree(os.path.join(out, "bun"), os.path.join(prev, "bun"))                       # the job: this run's branch is the next run's prev/
        sb2 = scoreboard(); e1 = next(e for e in sb2["events"] if e["id"] == "E1"); e1.update(state="in", detail="12'"); e1["teams"][0]["score"] = "0"; e1["teams"][1]["score"] = "0"
        put(os.path.join(feeds, "bun"), "scoreboard.json", sb2)
        out2 = os.path.join(d, "out2"); shutil.copytree(os.path.join(prev, "bun", "locks"), os.path.join(out2, "bun", "locks")) if os.path.isdir(os.path.join(prev, "bun", "locks")) else None
        shutil.copy(os.path.join(prev, "bun", "record.json"), os.path.join(out2, "bun", "record.json")) if os.path.isdir(os.path.join(out2, "bun")) else (os.makedirs(os.path.join(out2, "bun")), shutil.copy(os.path.join(prev, "bun", "record.json"), os.path.join(out2, "bun", "record.json")))
        log2 = run_main("--feeds", feeds, "--out", out2, "--prev", prev, "--site", site, "--only", "bun", "--now", t(minutes=14))
        L = json.load(open(os.path.join(out2, "bun", "locks", ko.strftime("%Y-%m-%d") + ".json")))["matches"]
        check("locked 1" in log2 and L["E1"]["board_built"] == t(minutes=-30) and L["E1"]["source"] == "the feed, one run earlier" and L["E1"]["minutes_before_ko"] == 30 and L["E1"]["gw"] == S.week_key(ko) and L["E1"]["lineups"] is True
              and len(L["E1"]["players"]) == len([p for p in b1["players"] if p["match"] == "E1"]) and L["E1"]["base"] == b1["base"],
              "after kickoff the match is locked from the board built before it - the one the last run left - with its round, its players and 'every match alike'")
        e1.update(state="post", done=True, detail="FT"); e1["teams"][0]["score"] = "2"; e1["teams"][1]["score"] = "0"
        put(os.path.join(feeds, "bun"), "scoreboard.json", sb2)
        A2 = copy.deepcopy(A); A2["matches"]["E1"] = {"d": iso(ko), "h": "11", "a": "16", "hs": 2, "as": 0, "st": {"11": {"sh": 15.0, "sot": 6.0}, "16": {"sh": 8.0, "sot": 3.0}}, "p": lines("11", 9, 2, 15, 6) + lines("16", 9, 0, 8, 3)}
        put(os.path.join(feeds, "bun"), "season.json", A2)
        log3 = run_main("--feeds", feeds, "--out", out2, "--prev", prev, "--site", site, "--only", "bun", "--now", t(hours=2))
        rec = json.load(open(os.path.join(out2, "bun", "record.json"))); wkk = S.week_key(ko); gf = os.path.join(out2, "bun", f"graded-gw{wkk}.json")
        check("graded 1 match(es) (E1)" in log3 and "players of 1" in log3 and rec["total"]["matches"] == 1 and rec["total"]["pmatches"] == 1 and [(r["gw"], r["ids"], r["pids"]) for r in rec["rounds"]] == [(wkk, ["E1"], ["E1"])]
              and rec["total"]["res"]["top"] == 1 and rec["total"]["pl"]["n"] >= 20 and os.path.exists(gf) and json.load(open(gf))["matches"]["E1"]["final"] == {"home": 2, "away": 0} and K.round_name(wkk).startswith("Week of "),
              f"at full time the match is graded from ESPN's final and - the season file having it - its starters in the same run ({rec['total']['pl']['n']} graded); the record's round is the week ({K.round_name(wkk)})")
        b3 = json.load(open(os.path.join(out2, "bun", "board.json")))
        check(b3["played"] == 31 and b3["data_through"] == ko.strftime("%Y-%m-%d") and "AAA-FFF" not in [m["key"] for m in b3["matches"] if m["state"] == "pre"], "and the next board is fitted on that result too")
        put(os.path.join(prev, "zzz"), "board.json", {"sport": "zzz", "kept": True})
        log4 = run_main("--feeds", feeds, "--out", out2, "--prev", prev, "--site", site, "--only", "zzz,bun", "--now", t(hours=3))
        check("zzz board: FAILED" in log4 and "kept the last run's" in log4 and json.load(open(os.path.join(out2, "zzz", "board.json"))) == {"sport": "zzz", "kept": True} and "bun board: " in log4 and "bun board: FAILED" not in log4,
              "a league that cannot be built keeps its last board and does not stop the next league")

        # ---- the page builder
        keep_out = BS.OUT; BS.OUT = os.path.join(d, "pages")
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                w1 = BS.write("bundesliga", b1, None, {"epl": True, "nba": True}, any_age=True)
                files1 = sorted(os.listdir(BS.OUT)); h1 = open(os.path.join(BS.OUT, "bundesliga-boards.html"), encoding="utf-8").read()
                w2 = BS.write("bundesliga", b1, dict(r1, sport="epl"), {"epl": True}, any_age=True); files2 = sorted(os.listdir(BS.OUT))
                w3 = BS.write("bundesliga", b1, r1, {"epl": True}, any_age=True); files3 = sorted(os.listdir(BS.OUT)); h3 = open(os.path.join(BS.OUT, "bundesliga-boards.html"), encoding="utf-8").read()
                sig3 = json.load(open(os.path.join(BS.OUT, "bundesliga_sig.json")))["sig"]
                BS.write("bundesliga", b1, r1, {"epl": True, "mls": True}, any_age=True); sig4 = json.load(open(os.path.join(BS.OUT, "bundesliga_sig.json")))["sig"]
                w5 = BS.write("bundesliga", dict(b1, built="2026-11-01T00:00:00Z"), r1, {}); files5 = sorted(os.listdir(BS.OUT))
                w6 = BS.write("laliga", b1, None, {}, any_age=True)
            three = ["bundesliga-boards.html", "bundesliga_board.json", "bundesliga_sig.json"]
            check(w1 and files1 == three and "<title>BetSweep · Bundesliga Matchup Boards</title>" in h1 and "Bundesliga preview" in h1 and "shot-based stand-in" in h1 and 'id="nbrec"' not in h1 and "locked at kickoff and graded" not in h1
                  and w2 and files2 == three and w3 and files3 == sorted(three + ["bundesliga_record.json"]) and 'class="nbrec none" id="nbrec"' in h3 and "every match is locked at kickoff and graded against the result first" in h3,
                  "a league's page is written with its board and signature beside it; a record is shipped - and grading claimed - only when it is that league's own (another league's record is ignored)")
            check(sig3 != sig4 and not w5 and files5 == [] and not w6 and "no page written" in buf.getvalue() and "'bun'" in buf.getvalue(),
                  "the signature moves when the leagues linked from the page change; a board built days ago, or one for another league, writes no page and clears the page that was there")
            pills = lambda h, cls: [x for x in __import__("re").findall(r'<a href="([^"]+)"( aria-current="page")?>([^<]+)</a>', h.split(cls)[1].split("</div>")[0])]
            check([p[2] for p in pills(h1, 'aria-label="Sport">')] == ["NFL", "NBA", "Soccer"] and [p for p in pills(h1, 'aria-label="Sport">') if p[1]] == [("/bundesliga/", ' aria-current="page"', "Soccer")]
                  and [(p[0], bool(p[1])) for p in pills(h1, 'aria-label="League">')] == [("/epl/", False), ("/bundesliga/", True)],
                  "its switch: NFL | NBA | Soccer with Soccer current and pointing at this league, then the leagues in the build with this one marked")
        finally:
            BS.OUT = keep_out

        # ---- the wiring
        import reprice as R, sports.job as J
        steps = [x[1].split(" ")[0] for x in R.BUILD]
        check(set(BS.KEYS) == {"bundesliga", "laliga", "seriea", "mls"} and all(k in R.PREVIEWS for k in BS.KEYS) and "build_soccer.py" in steps and [s[1] for s in J.STEPS][-1] == "sports.soccer.publish"
              and set(J.STEPS[-1][2]) == {f"{lg}/board.json" for lg in S.LEAGUES} and {sport_nav.LEAGUE[k]["feed"] for k in BS.KEYS} == set(S.LEAGUES) == set(S.SITE_FOLDER) and all(S.SITE_FOLDER[sport_nav.LEAGUE[k]["feed"]] == k for k in BS.KEYS)
              and [k for k, _, _ in switch_want.LEAGUES] == [k for k, _, _, _ in sport_nav.SOCCER] and [(l, h) for _, l, h in switch_want.LEAGUES] == [(n, h) for _, n, h, _ in sport_nav.SOCCER],
              "the four leagues are in the hourly build, among the preview folders the small publish watches, and in the data job's steps - and the page builder, the board builder and the tests agree on each league's folder and name")
        keep = (R.SITE, R.OUT)
        try:
            R.SITE, R.OUT = os.path.join(d, "s2"), os.path.join(d, "o2"); clone = os.path.join(d, "clone")
            for x in (os.path.join(R.SITE, "laliga"), os.path.join(R.SITE, "mls"), R.OUT, os.path.join(clone, "mls"), os.path.join(clone, "s"), os.path.join(R.SITE, "s")): os.makedirs(x)
            open(os.path.join(R.SITE, "laliga", "index.html"), "w").write("new laliga"); open(os.path.join(R.SITE, "mls", "index.html"), "w").write("new mls"); open(os.path.join(clone, "mls", "index.html"), "w").write("live mls")
            json.dump({"sig": "M1"}, open(os.path.join(R.OUT, "mls_sig.json"), "w")); json.dump({"sig": "M1"}, open(os.path.join(clone, "mls", "sig.json"), "w")); json.dump({"sig": "L1"}, open(os.path.join(R.OUT, "laliga_sig.json"), "w"))
            ch = [n for n in R.PREVIEWS if R.preview_changed(clone, n)]; done = R.copy_only(clone, ch)
            check(ch == ["laliga"] and done == ["laliga"] and open(os.path.join(clone, "laliga", "index.html")).read() == "new laliga" and open(os.path.join(clone, "mls", "index.html")).read() == "live mls",
                  "the small publish: a La Liga page the live site does not have yet goes out on its own; an unchanged MLS page is left as it is")
        finally:
            R.SITE, R.OUT = keep
    finally:
        shutil.rmtree(d, ignore_errors=True)


def part_two():
    """each league's page in SITE, read by the Premier League page's test"""
    drawn = []
    for key in BS.KEYS:
        name = sport_nav.LEAGUE[key]["name"]
        r = subprocess.run([sys.executable, os.path.join(HERE, "epl_board.py")] + ([SHOTS] if SHOTS else []), env=dict(os.environ, LEAGUE=key, SITE=ROOT), capture_output=True, text=True, timeout=240)
        got = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS ", "FAIL "))]
        for ln in got:
            ok[0 if ln.startswith("PASS ") else 1] += 1; print(ln[:5] + f"[{name}] " + ln[5:])
        if r.returncode not in (0, 1) or not got:
            check(False, f"[{name}] the page test did not finish (exit {r.returncode}): {(r.stderr or r.stdout).strip().splitlines()[-1][:200] if (r.stderr or r.stdout).strip() else 'no output'}")
        if os.path.exists(os.path.join(ROOT, key, "index.html")): drawn.append(name)
    print(f"league pages in this build: {', '.join(drawn) or 'none'}")


part_one(); part_two()
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
