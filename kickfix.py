#!/usr/bin/env python3
"""kickfix.py - a kickoff the schedule file has wrong is taken from FanDuel (11/22).

in/games.csv is nflverse's schedule, and every page that shows a kickoff, locks a leg, opens the live tracker or times an alert reads
it. On Sunday 11/22 it still had Jaguars @ Giants at 1:00 PM ET and Steelers @ Eagles at 4:25 PM ET after the two games had traded
windows: FanDuel (the game-lines tab pulled that night, and two of the owner's own betslips) listed Jaguars @ Giants at 3:25 PM CT and
Steelers @ Eagles at noon. Left alone, the Eagles game's legs would have read "not played yet" for three hours after kickoff, the live
tracker would have started at 3:10, and the inactives alert (it checks games within 3 hours of kickoff) would have looked at 12:25 for
a game that started at noon.

The schedule row is corrected in ./in before any step reads it (reprice.py, beside weekgate and availfix). Nothing on the sheet or in
the mirror changes; the next run starts from nflverse's file again and repeats the correction only while the two still disagree.

A row is changed only when ALL of this holds
  - the game is in the build's week and has no final score
  - the game-lines tab has MIN_ROWS or more rows for that exact matchup (away @ home, both names known)
  - every one of those rows gives the same kickoff, and the tab was pulled within MAX_AGE_H hours
  - FanDuel's date is within NEAR_DAYS of the schedule's (another week's meeting of the same teams is not this game)
  - the two kickoffs differ by MIN_GAP_MIN minutes or more (FanDuel lists 12:00 for a 12:01 start; that is the same kickoff)
FanDuel's time is Central; games.csv is Eastern. Only that one line of the file is rewritten; every other byte is left as it was.

clean(IN, week, log=print, now=None) -> [{"game": "JAX @ NYG", "was": "2026-11-22 13:00", "now": "2026-11-22 16:25", "fd": "Sun 11/22 15:25",
                                          "rows": 224}, ...]   ("now" is None for a disagreement that was NOT applied, with "why")
The same list is written to out/kickfix.json.   python3 kickfix.py --selftest
"""
import csv, io, json, os, re, sys, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
CT, ET = ZoneInfo("America/Chicago"), ZoneInfo("America/New_York")
MIN_ROWS = 20
MIN_GAP_MIN = 20
NEAR_DAYS = 2
MAX_AGE_H = 72


def _full():
    import gamelines as GLM
    return GLM.TEAM_FULL


def _fd_time(text, near):
    """'Sun 11/22 15:25' (Central, no year) -> an aware Eastern datetime in the year that puts it closest to `near` (a date)"""
    m = re.search(r"\b(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})\b", str(text or ""))
    if not m: return None
    mo, d, h, mi = (int(x) for x in m.groups()); best = None
    for y in (near.year - 1, near.year, near.year + 1):
        try: t = datetime.datetime(y, mo, d, h, mi, tzinfo=CT)
        except ValueError: continue
        if best is None or abs((t.date() - near).days) < abs((best.date() - near).days): best = t
    return best.astimezone(ET) if best else None


def _pulled(text):
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})", str(text or ""))
    if not m: return None
    y, mo, d, h, mi = (int(x) for x in m.groups())
    try: return datetime.datetime(y, mo, d, h, mi, tzinfo=CT)
    except ValueError: return None


def fanduel(IN, full=None):
    """{frozenset({away, home}): {"kicks": {text: n}, "n": rows, "pulled": newest pull, "label": "Away Full @ Home Full"}}"""
    try: v = json.load(open(os.path.join(IN, "gamelines.json"), encoding="utf-8"))["values"]
    except Exception: return {}
    if not v: return {}
    H = {str(h).strip(): i for i, h in enumerate(v[0])}
    gi, ki, pi = H.get("Game"), H.get("Kickoff (CT)"), H.get("Pulled at (CT)")
    if gi is None or ki is None: return {}
    full = full or _full(); out = {}
    for r in v[1:]:
        if len(r) <= max(gi, ki): continue
        g = str(r[gi] or "")
        if " @ " not in g or not str(r[ki] or "").strip(): continue
        a, b = (x.strip() for x in g.split(" @ ", 1)); ta, tb = full.get(a), full.get(b)
        if not ta or not tb: continue
        e = out.setdefault((ta, tb), {"kicks": {}, "n": 0, "pulled": None, "label": g})
        k = str(r[ki]).strip(); e["kicks"][k] = e["kicks"].get(k, 0) + 1; e["n"] += 1
        p = _pulled(r[pi]) if pi is not None and len(r) > pi else None
        if p and (e["pulled"] is None or p > e["pulled"]): e["pulled"] = p
    return out


def clean(IN, week, log=print, now=None, out_dir=None):
    path = os.path.join(IN, "games.csv"); res = []
    raw = open(path, "rb").read().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(nl)
    hdr = next(csv.reader([lines[0]])); H = {h: i for i, h in enumerate(hdr)}
    need = ("season", "week", "gameday", "gametime", "away_team", "home_team")
    if any(k not in H for k in need): raise ValueError("games.csv has no " + ", ".join(k for k in need if k not in H))
    rows = {}
    for i, ln in enumerate(lines[1:], start=1):
        if not ln or f",{week}," not in ln: continue          # cheap first cut; the parsed row decides
        r = next(csv.reader([ln]))
        if len(r) < len(hdr) or r[H["week"]] != str(week): continue
        rows[i] = r
    if not rows: return res
    season = max(r[H["season"]] for r in rows.values())
    fd = fanduel(IN); now = now or datetime.datetime.now(datetime.timezone.utc)
    for i, r in sorted(rows.items()):
        if r[H["season"]] != season: continue
        away, home = r[H["away_team"]], r[H["home_team"]]; e = fd.get((away, home))
        if not e: continue
        if "home_score" in H and str(r[H["home_score"]]).strip() not in ("", "NA"): continue            # played: the schedule's time is history
        try: mine = datetime.datetime.fromisoformat(r[H["gameday"]] + "T" + r[H["gametime"]]).replace(tzinfo=ET)
        except Exception: continue
        label = f"{away} @ {home}"; was = mine.strftime("%Y-%m-%d %H:%M")
        top = max(e["kicks"], key=lambda k: e["kicks"][k]); theirs = _fd_time(top, mine.date())
        if theirs is None: continue
        gap = abs((theirs - mine).total_seconds()) / 60
        if gap < MIN_GAP_MIN: continue
        item = {"game": label, "was": was, "now": None, "fd": top, "rows": e["n"]}
        age = None if e["pulled"] is None else (now - e["pulled"]).total_seconds() / 3600
        why = ("FanDuel has only %d rows for it" % e["n"] if e["n"] < MIN_ROWS else
               "FanDuel's rows give more than one kickoff (%s)" % ", ".join(sorted(e["kicks"])) if len(e["kicks"]) > 1 else
               "the game-lines tab has no pull time" if age is None else
               "the game-lines tab is %.0f hours old" % age if age > MAX_AGE_H or age < -1 else
               "FanDuel's date is %d days from the schedule's" % abs((theirs.date() - mine.date()).days) if abs((theirs.date() - mine.date()).days) > NEAR_DAYS else "")
        if why:
            item["why"] = why; res.append(item); log(f"[kickfix] {label}: schedule {was} ET, FanDuel {top} CT - NOT changed: {why}"); continue
        r[H["gameday"]] = theirs.strftime("%Y-%m-%d"); r[H["gametime"]] = theirs.strftime("%H:%M")
        if "weekday" in H: r[H["weekday"]] = theirs.strftime("%A")
        buf = io.StringIO(); csv.writer(buf, lineterminator="").writerow(r); lines[i] = buf.getvalue()
        item["now"] = theirs.strftime("%Y-%m-%d %H:%M"); res.append(item)
        log(f"[kickfix] {label}: kickoff {was} ET -> {item['now']} ET (FanDuel lists {top} CT on all {e['n']} rows; the schedule file had not caught up)")
    if any(x["now"] for x in res):
        with open(path, "wb") as f: f.write(nl.join(lines).encode("utf-8"))
    try:
        od = out_dir or os.path.join(os.path.dirname(os.path.abspath(IN)), "out")
        if os.path.isdir(od): json.dump({"week": week, "checked": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "games": res}, open(os.path.join(od, "kickfix.json"), "w"), indent=1)
    except Exception: pass
    if not res: log("[kickfix] every kickoff on the schedule agrees with FanDuel" if fd else "[kickfix] the game-lines tab has no kickoffs to compare")
    return res


def _selftest():
    import tempfile, shutil
    ok = [0, 0]
    def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
    HDR = "game_id,season,game_type,week,gameday,weekday,gametime,away_team,away_score,home_team,home_score,location,stadium"
    BASE = [HDR,
            "2025_11_JAX_NYG,2025,REG,11,2025-11-16,Sunday,13:00,JAX,20,NYG,17,Home,MetLife Stadium",
            "2026_10_BUF_MIN,2026,REG,10,2026-11-15,Sunday,13:00,BUF,24,MIN,20,Home,\"U.S. Bank Stadium, Minneapolis\"",
            "2026_11_JAX_NYG,2026,REG,11,2026-11-22,Sunday,13:00,JAX,,NYG,,Home,MetLife Stadium",
            "2026_11_PIT_PHI,2026,REG,11,2026-11-22,Sunday,16:25,PIT,,PHI,,Home,Lincoln Financial Field",
            "2026_11_MIA_BUF,2026,REG,11,2026-11-22,Sunday,13:00,MIA,,BUF,,Home,Highmark Stadium",
            "2026_11_IND_HOU,2026,REG,11,2026-11-19,Thursday,20:15,IND,23,HOU,20,Home,NRG Stadium",
            "2026_11_CIN_WAS,2026,REG,11,2026-11-23,Monday,20:15,CIN,,WAS,,Home,Northwest Stadium",
            "2026_11_TEN_DAL,2026,REG,11,2026-11-22,Sunday,13:00,TEN,,DAL,,Home,AT&T Stadium",
            "2026_11_LV_DEN,2026,REG,11,2026-11-22,Sunday,16:25,LV,,DEN,,Home,Empower Field",
            "2026_12_TEN_JAX,2026,REG,12,2026-11-29,Sunday,13:00,TEN,,JAX,,Home,EverBank Stadium", ""]
    FULL = {"Jacksonville Jaguars": "JAX", "New York Giants": "NYG", "Pittsburgh Steelers": "PIT", "Philadelphia Eagles": "PHI", "Miami Dolphins": "MIA", "Buffalo Bills": "BUF",
            "Indianapolis Colts": "IND", "Houston Texans": "HOU", "Cincinnati Bengals": "CIN", "Washington Commanders": "WAS", "Tennessee Titans": "TEN", "Dallas Cowboys": "DAL",
            "Las Vegas Raiders": "LV", "Denver Broncos": "DEN"}
    global _full
    real = _full; _full = lambda: FULL
    def gl(*games):
        v = [["Key", "Game", "Kickoff (CT)", "Market", "Side", "Point", "FanDuel odds", "Link", "Market ID", "Selection ID", "Pulled at (CT)"]]
        for g, k, n, pulled in games: v += [["k", g, k, "Moneyline", "x", "", "-110", "", "", "", pulled]] * n
        return {"values": v}
    NOW = datetime.datetime(2026, 11, 22, 7, 40, tzinfo=datetime.timezone.utc); P = "2026-11-22 0:25"
    def run(games, nl="\n"):
        d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "in")); os.makedirs(os.path.join(d, "out")); IN = os.path.join(d, "in")
        open(os.path.join(IN, "games.csv"), "wb").write(nl.join(BASE).encode()); json.dump(gl(*games), open(os.path.join(IN, "gamelines.json"), "w"))
        logs = []; res = clean(IN, 11, log=logs.append, now=NOW); txt = open(os.path.join(IN, "games.csv"), "rb").read().decode()
        again = clean(IN, 11, log=lambda s: None, now=NOW); rep = json.load(open(os.path.join(d, "out", "kickfix.json")))
        shutil.rmtree(d); return res, txt, logs, again, rep
    try:
        swap = [("Jacksonville Jaguars @ New York Giants", "Sun 11/22 15:25", 224, P), ("Pittsburgh Steelers @ Philadelphia Eagles", "Sun 11/22 12:00", 218, P),
                ("Miami Dolphins @ Buffalo Bills", "Sun 11/22 12:00", 200, P), ("Las Vegas Raiders @ Denver Broncos", "Sun 11/22 15:26", 200, P),
                ("Indianapolis Colts @ Houston Texans", "Thu 11/19 15:00", 200, P), ("Tennessee Titans @ Jacksonville Jaguars", "Sun 11/29 15:25", 200, P)]
        res, txt, logs, again, rep = run(swap); L = txt.split("\n")
        check([(x["game"], x["was"], x["now"]) for x in res] == [("JAX @ NYG", "2026-11-22 13:00", "2026-11-22 16:25"), ("PIT @ PHI", "2026-11-22 16:25", "2026-11-22 13:00")],
              f"the two games that traded windows are moved to FanDuel's kickoffs, in Eastern time ({[(x['game'], x['now']) for x in res]})")
        check(L[3] == "2026_11_JAX_NYG,2026,REG,11,2026-11-22,Sunday,16:25,JAX,,NYG,,Home,MetLife Stadium" and L[4] == "2026_11_PIT_PHI,2026,REG,11,2026-11-22,Sunday,13:00,PIT,,PHI,,Home,Lincoln Financial Field",
              "only the time changes on those two lines")
        check([l for i, l in enumerate(L) if i not in (3, 4)] == [l for i, l in enumerate(BASE) if i not in (3, 4)], "every other line of the file is byte for byte what it was (last year's meeting, next week's game, a quoted stadium name)")
        check("2026_11_IND_HOU,2026,REG,11,2026-11-19,Thursday,20:15" in txt, "a game that has been played keeps its time, whatever FanDuel's rows say")
        check("2026_11_LV_DEN,2026,REG,11,2026-11-22,Sunday,16:25" in txt and "2026_11_MIA_BUF,2026,REG,11,2026-11-22,Sunday,13:00" in txt, "a one-minute difference is the same kickoff: no change")
        check(again == [] and rep["games"] == [], "a second run finds nothing left to change")
        check(any("JAX @ NYG: kickoff 2026-11-22 13:00 ET -> 2026-11-22 16:25 ET" in s for s in logs), "the log says what was changed and why")
        res, txt, logs, again, rep = run(swap, nl="\r\n")
        check(txt.count("\r\n") == len(BASE) - 1 and "Sunday,16:25,JAX" in txt, "a file with Windows line ends keeps them")
        res, txt, _, _, _ = run([("Jacksonville Jaguars @ New York Giants", "Sun 11/22 15:25", 5, P)])
        check(res[0]["now"] is None and "only 5 rows" in res[0]["why"] and "Sunday,13:00,JAX" in txt, "a handful of rows is not enough to move a kickoff")
        res, txt, _, _, _ = run([("Jacksonville Jaguars @ New York Giants", "Sun 11/22 15:25", 100, P), ("Jacksonville Jaguars @ New York Giants", "Sun 11/22 12:00", 30, P)])
        check(res[0]["now"] is None and "more than one kickoff" in res[0]["why"] and "Sunday,13:00,JAX" in txt, "rows that disagree with each other move nothing")
        res, txt, _, _, _ = run([("Jacksonville Jaguars @ New York Giants", "Sun 11/22 15:25", 100, "2026-11-17 9:00")])
        check(res[0]["now"] is None and "hours old" in res[0]["why"] and "Sunday,13:00,JAX" in txt, "a game-lines tab pulled days ago moves nothing")
        res, txt, _, _, _ = run([("Jacksonville Jaguars @ New York Giants", "Sun 11/29 15:25", 100, P)])
        check(res[0]["now"] is None and "days from" in res[0]["why"] and "Sunday,13:00,JAX" in txt, "a kickoff a week away is another game: nothing moves")
        res, txt, _, _, _ = run([("New York Giants @ Jacksonville Jaguars", "Sun 11/22 15:25", 100, P), ("Somewhere Else @ New York Giants", "Sun 11/22 15:25", 100, P)])
        check(res == [] and "Sunday,13:00,JAX" in txt, "the matchup has to be the same way round with both teams known")
        res, txt, _, _, _ = run([("Cincinnati Bengals @ Washington Commanders", "Sun 11/22 19:20", 100, P)])
        check(res and res[0]["now"] == "2026-11-22 20:20" and "2026_11_CIN_WAS,2026,REG,11,2026-11-22,Sunday,20:20" in txt, "a game moved to another day takes the new day and weekday too")
    finally: _full = real
    # the real file and tab, when they are here: nothing is written, the file is put back
    IN = os.path.join(HERE, "in")
    if os.path.exists(os.path.join(IN, "games.csv")) and os.path.exists(os.path.join(IN, "gamelines.json")) and os.path.exists(os.path.join(IN, "boards.json")):
        import tempfile, shutil
        d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "in"))
        for f in ("games.csv", "gamelines.json"): shutil.copy2(os.path.join(IN, f), os.path.join(d, "in"))
        try:
            import weekgate as WG
            wk = WG.week_of(IN); before = open(os.path.join(d, "in", "games.csv"), "rb").read()
            res = clean(os.path.join(d, "in"), wk, log=lambda s: print("   " + s)); after = open(os.path.join(d, "in", "games.csv"), "rb").read()
            diff = sum(1 for a, b in zip(before.split(b"\n"), after.split(b"\n")) if a != b)
            check(diff == sum(1 for x in res if x["now"]) and before.count(b"\n") == after.count(b"\n"), f"on this week's real inputs (week {wk}) {diff} line(s) change, one for each kickoff moved")
        finally: shutil.rmtree(d)
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)


if __name__ == "__main__":
    if "--selftest" in sys.argv: _selftest()
    else:
        import weekgate as WG
        IN = os.path.join(HERE, "in"); print(json.dumps(clean(IN, WG.week_of(IN)), indent=1))
