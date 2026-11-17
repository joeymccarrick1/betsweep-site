#!/usr/bin/env python3
"""availfix.py - the team's official injury report outranks the news desk's own "Questionable".

Why (11/17). The news desk enters a player as QUESTIONABLE in 'AUTO - Weekly Availability' from ESPN's team page early in the week
("NEWS DESK: Justin Herbert: Questionable (Finger) - avoided a fracture ...", Mon 11/09). Nothing took that row back when the team's
own report came out without him: Herbert was never on the Chargers' Week 10 report, and the row still said QUESTIONABLE on Monday
night - a "Questionable" flag on every Herbert leg and "LAC QB questionable" in the card's confidence. Week 10 ended with seven such
desk rows; the final reports contradicted five (Herbert, Okonkwo, Mooney, Henry, Mitchell - no game status, the ones with snap
counts in played 56-71%), agreed with one (St. Brown, officially Questionable) and one team was on its bye.

What it does. For every row of the current week whose Availability is QUESTIONABLE and whose reason starts with "NEWS DESK:"
(the desk's own read - never an OWNER row, never a row the injury refresh wrote from the report itself):
  final report in (some player on his team has a game status in nflverse injuries_<season>.csv for the week)
      he has a game status of Out / Doubtful ........ OUT      (Step 2a's own rule for the final report)
      he is Questionable there ..................... stays
      he is listed with no game status ............. CLEARED
      he is not listed at all ...................... CLEARED  (needs the two proofs below)
  practice reports only, no game statuses yet
      not listed, and the note is 3+ days old ....... CLEARED  (needs the two proofs below)
      anything else ................................ stays
A player who is not listed could also be on injured reserve - reserve players are not on the weekly report. So "not listed" clears
only when BOTH hold: the nflverse roster (in/roster_<season>.csv, fetched within the last 60 hours) has him ACT, and ESPN's injury
page (the feeds mirror) does not list him as anything worse than Questionable. If either cannot be read, the row stays as it is.
A listed player with no game status is on the active roster by definition; he is held only when ESPN says Out / IR / Doubtful.

clean(IN, week) rewrites in/avail.json (Availability, reason, date of the changed rows) so every later step reads the corrected
status, and returns the changes with the sheet cells a session writes ('AUTO - Weekly Availability' E / J / L of that row).

Who calls it: reprice.py right after weekgate (the hourly rebuild corrects itself with no session), and a session by hand after
the context desk's rows are applied (RUNBOOK Step 2a-ii). Safe to run twice: a corrected row no longer starts with "NEWS DESK:".

  python3 availfix.py             correct ./in/avail.json for the week in in/boards.json; print each change; write out/avail_fixes.json
  python3 availfix.py --check     print only, change nothing
  python3 availfix.py selftest
"""
import csv, datetime, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/"
NV_TEAM = {"LAR": "LA"}            # the sheet says LAR, nflverse says LA
WAIT_DAYS = 3                      # practice reports only: days after the note before "not listed" counts
ROSTER_MAX_AGE_H = 60              # the roster file has to be this fresh to prove he is on the active roster
ESPN_FINE = {"", "active", "questionable", "day-to-day", "probable"}   # ESPN tags that do not stand in the way of a clear
TAB = "AUTO - Weekly Availability"
NV = "https://github.com/nflverse/nflverse-data/releases/download/"


def ensure(IN, season, log=print):
    """Fetch the two nflverse files this needs when they are missing or old. It runs before the steps that download them, and the
    first rebuild of a UTC day starts with no csv at all - without this the stale status would come back for that one build.
    A failed or odd-looking download changes nothing."""
    for name, url, max_h, need in ((f"injuries_{season}.csv", NV + f"injuries/injuries_{season}.csv", 3, "report_status"),
                                   (f"roster_{season}.csv", NV + f"rosters/roster_{season}.csv", 20, "full_name")):
        p = os.path.join(IN, name); tmp = p + ".part"
        try: age = (time.time() - os.path.getmtime(p)) / 3600
        except Exception: age = None
        if age is not None and age <= max_h: continue
        try:
            subprocess.run(["curl", "-fsSL", "--max-time", "60", "-o", tmp, url], check=True, capture_output=True)
            with open(tmp, newline="", encoding="utf-8", errors="replace") as f: head = f.readline()
            if need in head and os.path.getsize(tmp) > 20000: os.replace(tmp, p)
            else: raise ValueError("not the file expected")
        except Exception as e:
            log(f"[availfix] could not refresh {name} ({str(e)[:80]})" + ("" if age is None else f"; using the copy from {age:.0f} h ago"))
            try: os.remove(tmp)
            except Exception: pass


def nn(x):
    x = re.sub(r"[.'’]", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I)
    return re.sub(r"\s+", " ", x).lower().strip()


def _date(s):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(s or ""))
    try: return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    except Exception: return None


def today_ct():
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=6)).date()


def decide(listed, final_in, note_age_days, roster_act, espn):
    """One row's verdict: None (leave it) or (new status, reason).
    listed ........ None when he is not on the team's report, else his game status ('' = listed with no status)
    final_in ...... the team's game statuses are out
    note_age_days . days since the desk wrote the row (None = unknown)
    roster_act .... True = the roster has him ACT and the file is fresh; False = it has him as something else; None = cannot tell
    espn .......... his tag on ESPN's injury page, lower case ('' = not listed there); None = the mirror could not be read"""
    st = (listed or "").strip().lower()
    if final_in and st in ("out", "doubtful"): return ("OUT", f"{st.capitalize()} on the final injury report")
    worse = espn is not None and espn not in ESPN_FINE
    if listed is not None:
        if not final_in or st: return None                      # practice reports only, or officially Questionable: the row is right
        if worse: return None
        return ("CLEARED", "no game status on the final injury report")
    # not listed: he may be healthy, or on injured reserve - clear only with both proofs
    if roster_act is not True or espn is None or worse: return None
    if final_in: return ("CLEARED", "not on the final injury report")
    if note_age_days is not None and note_age_days >= WAIT_DAYS: return ("CLEARED", f"not on the practice report {note_age_days} days after the note")
    return None


def week_of(IN):
    import weekgate
    return weekgate.week_of(IN)


def season_of(IN, week):
    try:
        with open(os.path.join(IN, "games.csv"), newline="") as f:
            return max(int(g["season"]) for g in csv.DictReader(f) if g.get("week") == str(week))
    except Exception: return datetime.date.today().year


def official(IN, season, week):
    """{team: {player: game status}} from the nflverse weekly report; a team with no rows has no report yet (or is on its bye)"""
    out = {}
    try:
        with open(os.path.join(IN, f"injuries_{season}.csv"), newline="") as f:
            for r in csv.DictReader(f):
                if r.get("week") == str(week) and str(r.get("season") or season) == str(season) and (r.get("game_type") or "REG") == "REG":
                    out.setdefault(r["team"], {})[nn(r["full_name"])] = (r.get("report_status") or "").strip()
    except Exception: pass
    return out


def roster(IN, season, now=None):
    """({(player, team): status}, fresh) - fresh is False when the file is missing or older than ROSTER_MAX_AGE_H"""
    p = os.path.join(IN, f"roster_{season}.csv")
    try:
        fresh = ((now or time.time()) - os.path.getmtime(p)) / 3600 <= ROSTER_MAX_AGE_H
        with open(p, newline="") as f: return {(nn(r["full_name"]), r["team"]): r.get("status", "") for r in csv.DictReader(f)}, fresh
    except Exception: return {}, False


def espn_tags():
    """{player: tag in lower case} from the ESPN injury page mirror, or None when it cannot be read"""
    j = None
    try: j = json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "25", RAW + "injuries.json"], stderr=subprocess.DEVNULL))
    except Exception: pass
    if j is None:
        for site in filter(None, (os.environ.get("BS_SITE"), "/home/claude/betsweep-site")):
            for ref, pre in (("origin/feeds", None), ("FETCH_HEAD", ["fetch", "-q", "--depth", "1", "origin", "feeds"])):
                try:
                    if pre: subprocess.run(["git", "-C", site] + pre, check=True, capture_output=True, timeout=60)
                    j = json.loads(subprocess.check_output(["git", "-C", site, "show", f"{ref}:injuries.json"], stderr=subprocess.DEVNULL)); break
                except Exception: continue
            if j is not None: break
    if not isinstance(j, dict) or not isinstance(j.get("injuries"), list): return None
    out = {}
    for t in j["injuries"]:
        for x in (t or {}).get("injuries") or []:
            n = nn(((x or {}).get("athlete") or {}).get("displayName") or "")
            if n: out[n] = str((x or {}).get("status") or "").strip().lower()
    return out


def plan(rows, week, off, ros, ros_fresh, espn, today):
    """rows = the sheet's values (header first). Returns [{row, player, team, was, to, why, reason, held}] - 'held' rows change nothing"""
    out = []
    for i, r in enumerate(rows[1:], start=2):
        if len(r) < 5 or str(r[0]).strip() != str(week) or str(r[4]).strip() != "QUESTIONABLE": continue
        r = list(r) + [""] * (13 - len(r)); why0 = str(r[9])
        if not why0.startswith("NEWS DESK:"): continue
        team = NV_TEAM.get(r[2], r[2]); rep = off.get(team)
        if not rep: continue                                   # no official report for his team yet, or a bye week
        name = nn(r[1]); listed = rep.get(name); final_in = any(rep.values())
        st = ros.get((name, team)); act = (st == "ACT") if (ros_fresh and st) else None
        tag = None if espn is None else espn.get(name, "")
        d = _date(r[11]); age = (today - d).days if d else None
        v = decide(listed, final_in, age, act, tag)
        if not v:
            if listed is None and (final_in or (age is not None and age >= WAIT_DAYS)):
                hold = ("ESPN lists him " + tag) if (tag is not None and tag not in ESPN_FINE) else ("the roster has him " + st) if (ros_fresh and st and st != "ACT") \
                    else "the roster file is missing or old" if not ros_fresh else "he is not in the roster file" if not st else "ESPN's injury page could not be read"
                out.append({"row": i, "player": r[1], "team": r[2], "was": "QUESTIONABLE", "to": None, "held": f"not on the official report, but {hold}"})
            continue
        to, why = v
        stamp = f"{today.month}/{today.day}"
        reason = (f"{to} {stamp} (auto): {why} ({team}, {len(rep)} listed). Was " + why0)[:480]
        out.append({"row": i, "player": r[1], "team": r[2], "was": "QUESTIONABLE", "to": to, "why": why, "reason": reason, "date": today.isoformat()})
    return out


def clean(IN=None, week=None, today=None, write=True, log=print, fetch=True):
    IN = IN or os.path.join(HERE, "in"); week = week or week_of(IN); today = today or today_ct()
    p = os.path.join(IN, "avail.json")
    try: doc = json.load(open(p, encoding="utf-8")); rows = doc["values"]
    except Exception as e:
        log(f"[availfix] no avail.json ({e})"); return []
    season = season_of(IN, week)
    desk = [r for r in rows[1:] if len(r) > 9 and str(r[0]).strip() == str(week) and str(r[4]).strip() == "QUESTIONABLE" and str(r[9]).startswith("NEWS DESK:")]
    if desk and fetch: ensure(IN, season, log)
    off = official(IN, season, week)
    if not desk or not off:
        log(f"[availfix] week {week}: {len(desk)} desk Questionable row(s), official report rows for {len(off)} team(s) - nothing to compare"); return []
    ros, fresh = roster(IN, season); espn = espn_tags()
    ch = plan(rows, week, off, ros, fresh, espn, today)
    for c in ch:
        if c["to"]:
            log(f"[availfix] {c['player']} ({c['team']}) QUESTIONABLE -> {c['to']}: {c['why']}")
            if write:
                r = rows[c["row"] - 1]; r += [""] * (13 - len(r)); r[4] = c["to"]; r[9] = c["reason"]; r[11] = c["date"]
        else: log(f"[availfix] held: {c['player']} ({c['team']}) - {c['held']}")
    done = [c for c in ch if c["to"]]
    log(f"[availfix] week {week}: {len(desk)} desk Questionable row(s) checked against {len(off)} team reports - {len(done)} corrected, {len(ch) - len(done)} held"
        + ("" if fresh else "; roster file missing or old") + ("" if espn is not None else "; ESPN mirror not readable"))
    if write and done:
        json.dump(doc, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return ch


def sheet_updates(changes):
    """the cells a session writes, one update_values call per item"""
    return [{"range": f"'{TAB}'!E{c['row']}:L{c['row']}", "values": [[c["to"], None, None, None, None, c["reason"], None, c["date"]]], "player": c["player"]}
            for c in changes if c.get("to")]


def selftest():
    ok = 0; bad = []
    def chk(name, got, want):
        nonlocal ok
        if got == want: ok += 1
        else: bad.append(f"{name}: got {got!r}, wanted {want!r}")
    D = decide
    chk("final, listed Out", D("Out", True, 5, True, ""), ("OUT", "Out on the final injury report"))
    chk("final, listed Doubtful", D("Doubtful", True, 5, True, "")[0], "OUT")
    chk("final, listed Questionable stays", D("Questionable", True, 5, True, "questionable"), None)
    chk("final, listed with no status clears", D("", True, 5, None, "questionable"), ("CLEARED", "no game status on the final injury report"))
    chk("final, listed no status but ESPN says out: held", D("", True, 5, True, "out"), None)
    chk("final, not listed clears with both proofs", D(None, True, 5, True, ""), ("CLEARED", "not on the final injury report"))
    chk("final, not listed, roster unknown: held", D(None, True, 5, None, ""), None)
    chk("final, not listed, on reserve: held", D(None, True, 5, False, ""), None)
    chk("final, not listed, ESPN unreadable: held", D(None, True, 5, True, None), None)
    chk("final, not listed, ESPN injured reserve: held", D(None, True, 5, True, "injured reserve"), None)
    chk("practice only, listed limited stays", D("", False, 5, True, "questionable"), None)
    chk("practice only, not listed, note 1 day old stays", D(None, False, 1, True, ""), None)
    chk("practice only, not listed, 3 days clears", D(None, False, 3, True, "questionable"), ("CLEARED", "not on the practice report 3 days after the note"))
    chk("practice only, not listed, no date stays", D(None, False, None, True, ""), None)
    chk("out on the final report beats an ESPN tag", D("Out", True, 0, None, None)[0], "OUT")
    # rows: Week 10 as it stood on Monday 11/16 (the real statuses), plus rows the rule must not touch
    hdr = ["Projection Week", "Player", "Team", "Pos", "Availability", "", "", "", "", "Reason / Injury", "Source", "Last Updated", "Practice Participation"]
    def row(pl, tm, st, why, d="2026-11-10", wk="10"): return [wk, pl, tm, "WR", st, "", "", "", "", why, "src", d, ""]
    rows = [hdr,
            row("Justin Herbert", "LAC", "QUESTIONABLE", "NEWS DESK: Justin Herbert: Questionable (Finger) - avoided a fracture"),
            row("Chig Okonkwo", "WAS", "QUESTIONABLE", "NEWS DESK: Chig Okonkwo: Questionable (Hip)"),
            row("Amon-Ra St. Brown", "DET", "QUESTIONABLE", "NEWS DESK: Amon-Ra St. Brown: Questionable (Ribs)", "2026-11-12"),
            row("Luther Burden III", "CHI", "QUESTIONABLE", "NEWS DESK: Luther Burden III: Questionable (Concussion)"),
            row("Rhamondre Stevenson", "NE", "QUESTIONABLE", "OWNER 11/10: questionable. Knee"),
            row("Sione Vaki", "DET", "QUESTIONABLE", "ankle - did not practice, no game designation yet", "2026-11-12"),
            row("Puka Nacua", "LAR", "QUESTIONABLE", "NEWS DESK: Puka Nacua: Questionable (Ankle)"),
            row("On Reserve", "LAC", "QUESTIONABLE", "NEWS DESK: On Reserve: Questionable (Knee) - could land on IR"),
            row("Worse Now", "WAS", "QUESTIONABLE", "NEWS DESK: Worse Now: Questionable (Back)"),
            row("Old Week", "LAC", "QUESTIONABLE", "NEWS DESK: Old Week: Questionable", wk="9"),
            row("Already Out", "LAC", "OUT", "NEWS DESK: Already Out: ruled out"),
            row("Ruled Out Friday", "DET", "QUESTIONABLE", "NEWS DESK: Ruled Out Friday: Questionable (Hamstring)")]
    off = {"LAC": {"khalil mack": "", "ladd mcconkey": "Questionable"}, "WAS": {"chig okonkwo": "", "x": "Out"},
           "DET": {"amon-ra st brown": "Questionable", "sione vaki": "Questionable", "ruled out friday": "Out"}, "LA": {"puka nacua": "", "y": "Questionable"}}
    ros = {("justin herbert", "LAC"): "ACT", ("chig okonkwo", "WAS"): "ACT", ("puka nacua", "LA"): "ACT", ("on reserve", "LAC"): "RES", ("worse now", "WAS"): "ACT"}
    espn = {"on reserve": "injured reserve", "worse now": "out", "justin herbert": "questionable"}
    T = datetime.date(2026, 11, 16)
    ch = plan(rows, 10, off, ros, True, espn, T); by = {c["player"]: c for c in ch}
    chk("Herbert cleared (not listed)", (by.get("Justin Herbert") or {}).get("to"), "CLEARED")
    chk("Okonkwo cleared (listed, no status)", (by.get("Chig Okonkwo") or {}).get("to"), "CLEARED")
    chk("St. Brown stays (officially Questionable; the name matches without its dot)", "Amon-Ra St. Brown" in by, False)
    chk("Burden untouched (no report for his team)", "Luther Burden III" in by, False)
    chk("owner row untouched", "Rhamondre Stevenson" in by, False)
    chk("the refresh's own row untouched", "Sione Vaki" in by, False)
    chk("LAR row matched to nflverse LA", (by.get("Puka Nacua") or {}).get("to"), "CLEARED")
    chk("reserve player held", (by.get("On Reserve") or {}).get("to", "x"), None)
    chk("reserve hold names ESPN", "ESPN lists him injured reserve" in (by.get("On Reserve") or {}).get("held", ""), True)
    chk("ESPN out held", (by.get("Worse Now") or {}).get("to", "x"), None)
    chk("another week untouched", "Old Week" in by, False)
    chk("an OUT row untouched", "Already Out" in by, False)
    chk("official Out upgrades", (by.get("Ruled Out Friday") or {}).get("to"), "OUT")
    chk("sheet row number", (by.get("Justin Herbert") or {}).get("row"), 2)
    chk("reason keeps the desk text", "Was NEWS DESK: Justin Herbert" in (by.get("Justin Herbert") or {}).get("reason", ""), True)
    up = sheet_updates(ch)
    chk("sheet update range", up[0]["range"], "'AUTO - Weekly Availability'!E2:L2")
    chk("sheet update writes E, J, L only", [i for i, x in enumerate(up[0]["values"][0]) if x is not None], [0, 5, 7])
    chk("held rows are not written", len(up), len([c for c in ch if c["to"]]))
    # stale roster / unreadable ESPN: only the listed-no-status clear survives
    ch2 = plan(rows, 10, off, ros, False, espn, T); by2 = {c["player"]: c for c in ch2}
    chk("stale roster: Herbert held", (by2.get("Justin Herbert") or {}).get("to", "x"), None)
    chk("stale roster: Okonkwo still cleared", (by2.get("Chig Okonkwo") or {}).get("to"), "CLEARED")
    ch3 = plan(rows, 10, off, ros, True, None, T); by3 = {c["player"]: c for c in ch3}
    chk("no ESPN: Herbert held", (by3.get("Justin Herbert") or {}).get("to", "x"), None)
    chk("no ESPN: Okonkwo still cleared", (by3.get("Chig Okonkwo") or {}).get("to"), "CLEARED")
    # a corrected row is not picked up again
    for c in ch:
        if c["to"]: r = rows[c["row"] - 1]; r[4] = c["to"]; r[9] = c["reason"]
    chk("second pass changes nothing", [c for c in plan(rows, 10, off, ros, True, espn, T) if c["to"]], [])
    for b in bad: print("FAIL", b)
    print(f"availfix selftest: {ok} ok, {len(bad)} failed"); return 1 if bad else 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["selftest"]: sys.exit(selftest())
    check = "--check" in sys.argv[1:]
    changes = clean(write=not check)
    if not check:
        os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
        json.dump({"updates": sheet_updates(changes), "held": [c for c in changes if not c.get("to")]}, open(os.path.join(HERE, "out", "avail_fixes.json"), "w"), indent=1)
        n = len(sheet_updates(changes))
        print(f"wrote out/avail_fixes.json: {n} sheet update(s)" + (" - write each with update_values, then re-read the tab" if n else ""))
