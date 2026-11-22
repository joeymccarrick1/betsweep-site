"""A posted slip keeps its kickoff times after FanDuel takes its legs off the board.

Found 11/22 4:25 PM by tests/promo_clock.py in a full pre-publish set: build_promo.py took a slip's first and last kickoff only from the
legs still on FanDuel's board, and FanDuel takes a game's player markets down at kickoff. An hour into the early games every slip's
"first kickoff" had jumped to the late window (the cards read Pregame from 1:22 to 3:05 PM with their early legs in play), and by
4:22 PM two of the four Week 11 slips on the live Today page had no kickoff at all and all four read "Pregame" with seven games final.
The Daily Sweep, which finds its day by its first kickoff, was drawn as an ordinary "Side action" card.

The fix (build_promo.kickoff_of): a leg that is off the board gets the kickoff of the game its player is in - his team from the
projection tabs, the game from builder_data.json, which keeps every game of the week. Only ko and kick are filled in.

This test: (1) kickoff_of on made-up tabs and games, taken from build_promo.py's own source (the script cannot be imported: it builds
when it loads); (2) the slips this tree just built (out/promos.json): every leg whose player can be placed has his game's kickoff,
on the board or off it, and each slip's first and last kickoff are the earliest and latest of ALL its legs.

  python3 tests/promo_kickoff.py
"""
import ast, json, os, re, sys, tempfile, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); TREE = os.path.join(HERE, "..")
ok = [0, 0]
def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)


def the_function(in_dir, games):
    """build_promo.kickoff_of with its helpers, compiled from the file's own text into a small namespace"""
    src = open(os.path.join(TREE, "build_promo.py"), encoding="utf-8").read()
    want = ("_TEAM_OF", "_pkey", "kickoff_of")
    nodes = [n for n in ast.parse(src).body if (isinstance(n, ast.FunctionDef) and n.name in want) or (isinstance(n, ast.Assign) and any(getattr(t, "id", "") in want for t in n.targets))]
    ns = {"json": json, "os": os, "re": re, "IN": in_dir, "GAMES": games}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "build_promo.py", "exec"), ns)
    return ns["kickoff_of"] if len(nodes) == 3 else None


def made_up():
    d = tempfile.mkdtemp()
    try:
        tab = lambda rows: {"values": [["Player", "Team", "Opponent", "Games"]] + rows}
        json.dump(tab([["Josh Allen", "BUF", "MIA", "9"]]), open(os.path.join(d, "proj_qb.json"), "w"))
        json.dump(tab([["James Cook", "BUF", "MIA", "9"], ["D'Andre Swift", "CHI", "NO", "9"]]), open(os.path.join(d, "proj_rb.json"), "w"))
        json.dump(tab([["A.J. Brown", "NE", "BYE", "4"], ["Amon-Ra St. Brown", "DET", "TB", "9"], ["Jordyn Tyson", "NO", "CHI", "9"]]), open(os.path.join(d, "proj_wr.json"), "w"))
        # no proj_te.json at all: a missing tab is not an error
        games = {"BUF-MIA": {"gid": "BUF-MIA", "a": "BUF", "b": "MIA", "ko": 1000, "kick": "Sun 12:00 PM"}, "DET-TB": {"gid": "DET-TB", "a": "DET", "b": "TB", "ko": 1000, "kick": "Sun 12:00 PM"},
                 "CHI-NO": {"gid": "CHI-NO", "a": "CHI", "b": "NO", "ko": 2000, "kick": "Sun 3:25 PM"}, "MIN-SF": {"gid": "MIN-SF", "a": "MIN", "b": "SF", "ko": 3000, "kick": "Sun 7:20 PM"}}
        f = the_function(d, games)
        check(f is not None, "build_promo.py has kickoff_of and its two helpers")
        if not f: return
        check(f("James Cook") == {"ko": 1000, "kick": "Sun 12:00 PM"} and f("Josh Allen") == {"ko": 1000, "kick": "Sun 12:00 PM"}, "a player is placed in his team's game: James Cook and Josh Allen kick off with BUF-MIA")
        check(f("D'Andre Swift or Jordyn Tyson") == {"ko": 2000, "kick": "Sun 3:25 PM"} and f("Josh Allen / James Cook")["ko"] == 1000, "an either-or leg takes its players' game (\"A or B\", \"A / B\")")
        check(f("Amon-Ra St. Brown")["ko"] == 1000 and f("amon-ra st brown")["ko"] == 1000 and f("DAndre Swift")["ko"] == 2000, "dots, hyphens, apostrophes and capitals in a name do not matter")
        check(f("A.J. Brown") == {} and f("Nobody Atall") == {} and f("KC -3.5") == {} and f("") == {}, "a player on a bye, a name the tabs do not have, a game line and an empty name get nothing rather than a guess")
        check(f("Nobody Atall or James Cook")["ko"] == 1000, "one unknown name in a pair does not lose the other's game")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def this_build():
    pj, bj = os.path.join(TREE, "out", "promos.json"), os.path.join(TREE, "out", "builder_data.json")
    if not (os.path.exists(pj) and os.path.exists(bj)):
        check(True, "no out/promos.json in this tree (nothing built here) - the made-up checks stand alone"); return
    promos = json.load(open(pj)); bd = json.load(open(bj)); games = {g["gid"]: g for g in bd["games"]}
    f = the_function(os.path.join(TREE, "in"), games)
    if not f: return
    board = {(l["pl"], l["g"]) for l in bd["legs"]}
    n_legs = off = placed = 0; bad = []; badp = []; unplaced = []
    for p in promos:
        kos = []
        for l in p["legs"]:
            n_legs += 1
            want = (games.get(l.get("gid")) or {}).get("ko") if l.get("gid") else (f(l.get("who") or "").get("ko"))
            if not l.get("gid"):
                off += 1
                if want: placed += 1
                else: unplaced.append(f"{l.get('who')} | {l.get('market')}")
            if want and l.get("ko") != want: bad.append((p["title"][:24], l.get("who"), l.get("ko"), want))
            if want: kos.append(want)
        if kos and (p.get("first_ko") != min(kos) or p.get("last_ko") != max(kos)): badp.append((p["title"][:30], p.get("first_ko"), min(kos), p.get("last_ko"), max(kos)))
        if not kos and p.get("legs"): badp.append((p["title"][:30], "no leg could be placed in a game"))
    check(not bad, f"{len(promos)} slips, {n_legs} legs: every leg whose player can be placed has his game's kickoff ({off} leg{'s' if off != 1 else ''} off FanDuel's board, {placed} of them placed by team)" + (f" - off: {bad[:3]}" if bad else ""))
    check(not badp, "each slip's first and last kickoff are the earliest and latest of all its legs, not only the ones still on the board" + (f" - off: {badp[:3]}" if badp else ""))
    # a leg nobody can place (a game line FanDuel no longer lists, a player missing from the tabs) is reported, not failed: it has no kickoff to be wrong about
    if unplaced: print(f"note: {len(unplaced)} leg(s) off the board could not be placed in a game: {unplaced[:4]}")


made_up(); this_build()
print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)
