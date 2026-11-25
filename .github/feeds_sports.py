"""ESPN (and Fantasy Premier League) mirrors for the sports beyond the NFL.

Owner 11/22 3:27 PM: "Let's start adding nba, college football, and epl." Asked the same hour whether the site's background jobs may
pull their data: "Yes add them".

Kept apart from .github/feeds.py on purpose - its own workflow (feeds-sports.yml) and its own orphan branch (`feeds-sports`) - so
nothing here can slow, break or overwrite the NFL feed that the alerts function and the live grader read.

Every ~15 minutes, to the branch `feeds-sports` (raw.githubusercontent.com):
  meta.json            {"mirrored": ISO, "files": {"nba/scoreboard.json": {"ok": true, "n": 7}, ...}} - what worked, readable without a log
  nba/scoreboard.json  games from yesterday to tomorrow (US Central days): state, score, teams, tip, and ESPN's posted line with its provider
  nba/injuries.json    the league injury report, one line a player: team, name, status, ESPN's fantasy tag (GTD / OUT / OFS), note, date
  nba/box-<id>.json    every player's line for a game in progress or finished in the last 36 hours (a final is kept, not fetched again)
  nba/board.json       tonight's model board - written by sports/nba/publish.py on the generators branch, in this job's second step
  epl/scoreboard.json  matches from 3 days back to 10 days ahead
  epl/lineups.json     starting elevens and benches for matches within 100 minutes of kickoff, in play, or finished in the last day
  epl/fpl.json         the official Fantasy Premier League list: each player's availability flag, chance of playing and news line
  cfb/scoreboard.json  FBS games from 2 days back to 16 days ahead: ranks, records, bowl / playoff names, ESPN's posted line
  bun/ lal/ sea/ mls/  the Bundesliga, La Liga, Serie A and MLS (11/23), each with: scoreboard.json (fixtures 3 days back to 10 ahead, with
                       the home, draw and away prices ESPN posts), lineups.json (as the Premier League's), and season.json - every
                       finished match of the season with each side's shots and a line for every player who took the field. The season
                       is filled in a few match summaries a run, newest first, and carried forward from the last run.
A file that cannot be fetched this run keeps its last copy (meta says "stale") rather than vanishing.
No keys, no secrets: every address here is public.

    python3 .github/feeds_sports.py            # writes ./out ; reads ./prev (last run's branch) when it is there
    python3 .github/feeds_sports.py --selftest # parsing checks on made-up ESPN answers, no network
"""
import glob, json, os, shutil, subprocess, sys, datetime as dt

E = "https://site.api.espn.com/apis/site/v2/sports"
FPL = "https://fantasy.premierleague.com/api/bootstrap-static/"
OUT, PREV = "out", "prev"
META = {}
HOW = {}


def get(u, agent=None):
    urls = [u] + ([u.replace("site.api.espn.com", "site.web.api.espn.com")] if "site.api.espn.com" in u else [])
    for x in urls:
        try:
            return json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "25"] + (["-A", agent] if agent else []) + [x]))
        except Exception as e:
            print("fail", x, str(e)[:140])
    return None


def central(now):
    try:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo("America/Chicago"))
    except Exception:
        return now.astimezone(dt.timezone(dt.timedelta(hours=-6)))


def when(v):
    try:
        d = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def first(*xs):
    return next((x for x in xs if x is not None), None)


def american(x):
    """an American price as a whole number: '+310', '-145', 'EVEN', 310 -> 310 / -145 / 100; anything else -> None"""
    if isinstance(x, bool): return None
    if isinstance(x, (int, float)): return int(x) if abs(x) >= 100 else None
    t = str(x or "").strip().upper().replace("\u2212", "-")
    if t in ("EVEN", "EV"): return 100
    try:
        v = int(float(t))
        return v if abs(v) >= 100 else None
    except Exception:
        return None


def price(side):
    """the price ESPN shows for one side of a market: the closing one when it is there, else the opening one. The shape is
    {"close": {"odds": "-145", ...}, "open": {"odds": "-150"}}; any key holding an American price is taken, so a renamed key still reads."""
    for part in ("close", "open"):
        d = (side or {}).get(part) if isinstance(side, dict) else None
        if isinstance(d, dict):
            for k in ("odds", "american", "moneyLine", "price"):
                if american(d.get(k)) is not None: return american(d.get(k))
            for v in d.values():
                if isinstance(v, str) and american(v) is not None and not v.strip().lower().startswith(("o", "u")): return american(v)
    return None


def team(c):
    t = c.get("team") or {}
    rec = None
    for r in c.get("records") or []:
        if r.get("type") in ("total", "ytd") or r.get("name") in ("overall", "All Splits", "YTD"):
            rec = r.get("summary"); break
    if rec is None and c.get("records"):
        rec = (c["records"][0] or {}).get("summary")
    rank = (c.get("curatedRank") or {}).get("current")
    return {"id": t.get("id"), "abbr": t.get("abbreviation"), "name": t.get("displayName"), "short": t.get("shortDisplayName"), "color": t.get("color"), "alt": t.get("alternateColor"),
            "ha": c.get("homeAway"), "score": c.get("score"), "winner": c.get("winner"), "rank": rank if isinstance(rank, int) and 0 < rank <= 25 else None, "record": rec,
            "form": c.get("form"), "lines": [x.get("value") for x in (c.get("linescores") or [])]}


def event(e):
    c = (e.get("competitions") or [{}])[0]
    st = e.get("status") or c.get("status") or {}
    ty = st.get("type") or {}
    od = next((o for o in (c.get("odds") or []) if o), None) or {}
    odds = None
    if od:
        ml, tot = od.get("moneyline") or {}, od.get("total") or {}
        odds = {"by": (od.get("provider") or {}).get("name"), "details": od.get("details"), "spread": od.get("spread"), "total": od.get("overUnder"),
                "home_ml": first((od.get("homeTeamOdds") or {}).get("moneyLine"), price(ml.get("home"))), "away_ml": first((od.get("awayTeamOdds") or {}).get("moneyLine"), price(ml.get("away")))}
        # soccer has a third price, and ESPN's newer shape keeps prices under moneyline / total: kept only when they are there, so the other sports' lines read as before
        for k, v in (("draw_ml", first((od.get("drawOdds") or {}).get("moneyLine"), price(ml.get("draw")))), ("over", price(tot.get("over"))), ("under", price(tot.get("under")))):
            if v is not None: odds[k] = v
    return {"id": str(e.get("id")), "date": e.get("date"), "name": e.get("name"), "short": e.get("shortName"), "week": (e.get("week") or {}).get("number"), "stype": (e.get("season") or {}).get("type"),
            "note": [n.get("headline") for n in (c.get("notes") or []) if n.get("headline")], "state": ty.get("state"), "done": bool(ty.get("completed")),
            "detail": ty.get("shortDetail") or ty.get("detail"), "period": st.get("period"), "clock": st.get("displayClock"), "venue": (c.get("venue") or {}).get("fullName"),
            "neutral": c.get("neutralSite"), "tv": [b for x in (c.get("broadcasts") or []) for b in (x.get("names") or [])], "teams": [team(x) for x in (c.get("competitors") or [])], "odds": odds}


def put(path, obj, n=None):
    p = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(obj, open(p, "w"), separators=(",", ":"))
    META[path] = {"ok": True, "n": n}


def keep(path, why):
    """This run could not fetch it: carry last run's copy forward instead of deleting it from the branch."""
    src = os.path.join(PREV, path)
    if os.path.exists(src):
        p = os.path.join(OUT, path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        shutil.copy(src, p)
        META[path] = {"ok": False, "stale": True, "why": why}
    else:
        META[path] = {"ok": False, "stale": False, "why": why}


GRADING = (("nba/locks/*.json", "nba/record.json", "nba/graded-*.json")
           # 11/22 night: the Premier League's (sports/epl/grade.py); 11/23: the same grader, a folder for each of the other leagues
           + tuple(f"{lg}/{pat}" for lg in ("epl", "bun", "lal", "sea", "mls") for pat in ("locks/*.json", "record.json", "graded-*.json"))
           # 11/24: college football's (sports/cfb/grade.py): each postseason game locked at kickoff, and the record
           + ("cfb/locks/*.json", "cfb/record.json"))


def carry():
    """The grading files (sports/nba/grade.py and sports/epl/grade.py in the generators - the second grades every soccer league, each in
    its own folder: each game's numbers locked at tip or kickoff, the running record, the last few nights, gameweeks or weeks player by
    player) live only on this branch, and the branch is rebuilt from
    nothing on every run. They are copied forward here, first, before a fetch or the model step can fail: one bad run must not cost
    the record. Returns how many files it carried."""
    n = 0
    for pat in GRADING:
        for src in sorted(glob.glob(os.path.join(PREV, pat))):
            dst = os.path.join(OUT, os.path.relpath(src, PREV))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst); n += 1
    return n


def prev(path):
    try:
        return json.load(open(os.path.join(PREV, path)))
    except Exception:
        return None


def scoreboard(sport, league, days_back, days_ahead, now, extra=""):
    """Events in a window of Central days, one request a day. ESPN answers 400 to a date range on these scoreboards (both range forms,
    every run of 11/22), so the range is only the fallback now, tried when not one day answers. meta.json says which way worked ("how")."""
    ct = central(now)
    days = [(ct + dt.timedelta(days=k)).strftime("%Y%m%d") for k in range(-days_back, days_ahead + 1)]
    out, seen, answered = [], set(), 0
    for d in days:
        j = get(f"{E}/{sport}/scoreboard?dates={d}{extra}") or get(f"{E}/{sport}/scoreboard?dates={d}&limit=200{extra}")
        if not j or "events" not in j:
            continue
        answered += 1
        for e in j.get("events") or []:
            if str(e.get("id")) not in seen:
                seen.add(str(e.get("id"))); out.append(event(e))
    if answered:
        HOW[league] = f"one request a day ({answered} of {len(days)} days answered)"
        return sorted(out, key=lambda e: str(e.get("date")))
    for how, q in (("range, limit 300", f"limit=300&dates={days[0]}-{days[-1]}"), ("range", f"dates={days[0]}-{days[-1]}")):
        j = get(f"{E}/{sport}/scoreboard?{q}{extra}")
        if j and "events" in j:
            HOW[league] = how
            return [event(e) for e in j.get("events") or []]
    return None


def nba_injuries(j, now):
    rows = []
    for t in j.get("injuries") or []:
        tn = t.get("displayName") or (t.get("team") or {}).get("displayName")
        for x in t.get("injuries") or []:
            d = x.get("details") or {}
            rows.append({"team": tn, "name": (x.get("athlete") or {}).get("displayName"), "status": x.get("status"), "fs": ((d.get("fantasyStatus") or {}).get("abbreviation")),
                         "type": d.get("type"), "note": x.get("shortComment"), "date": x.get("date"), "ret": d.get("returnDate")})
    return {"mirrored": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "injuries": [r for r in rows if r["name"]]}


def nba_box(j, ev):
    """One game's player lines from ESPN's summary: {id, state, done, teams, players: [{team, id, name, pos, starter, dnp, reason, s: {MIN, PTS, ...}}]}"""
    players = []
    for t in ((j.get("boxscore") or {}).get("players") or []):
        ab = (t.get("team") or {}).get("abbreviation")
        for blk in t.get("statistics") or []:
            keys = blk.get("labels") or blk.get("names") or blk.get("keys") or []
            for a in blk.get("athletes") or []:
                at = a.get("athlete") or {}
                players.append({"team": ab, "id": at.get("id"), "name": at.get("displayName"), "pos": (at.get("position") or {}).get("abbreviation"), "starter": bool(a.get("starter")),
                                "dnp": bool(a.get("didNotPlay")), "reason": a.get("reason"), "s": dict(zip(keys, a.get("stats") or []))})
    return {"id": ev["id"], "date": ev["date"], "state": ev["state"], "done": ev["done"], "detail": ev["detail"], "teams": [{"abbr": t["abbr"], "score": t["score"], "ha": t["ha"]} for t in ev["teams"]], "players": players}


def epl_lineup(j, ev):
    teams = []
    for r in j.get("rosters") or []:
        t = r.get("team") or {}
        xi, bench = [], []
        for p in r.get("roster") or []:
            at = p.get("athlete") or {}
            one = {"id": at.get("id"), "name": at.get("displayName"), "pos": (p.get("position") or {}).get("abbreviation"), "no": p.get("jersey"), "on": bool(p.get("subbedIn")), "off": bool(p.get("subbedOut"))}
            (xi if p.get("starter") else bench).append(one)
        teams.append({"abbr": t.get("abbreviation"), "name": t.get("displayName"), "ha": r.get("homeAway"), "formation": r.get("formation"), "xi": xi, "bench": bench})
    return {"id": ev["id"], "date": ev["date"], "state": ev["state"], "teams": teams, "posted": any(len(t["xi"]) >= 11 for t in teams)}


def fpl_trim(j, now):
    teams = {t.get("id"): t for t in j.get("teams") or []}
    el = [{"code": e.get("code"), "id": e.get("id"), "name": e.get("web_name"), "first": e.get("first_name"), "last": e.get("second_name"), "team": (teams.get(e.get("team")) or {}).get("short_name"),
           "pos": e.get("element_type"), "status": e.get("status"), "next": e.get("chance_of_playing_next_round"), "this": e.get("chance_of_playing_this_round"), "news": e.get("news") or None,
           "news_at": e.get("news_added"), "min": e.get("minutes"), "starts": e.get("starts")} for e in j.get("elements") or []]
    gw = [{"id": e.get("id"), "deadline": e.get("deadline_time"), "current": e.get("is_current"), "next": e.get("is_next"), "done": e.get("finished")} for e in j.get("events") or [] if e.get("is_current") or e.get("is_next")]
    return {"mirrored": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "teams": [{"id": t.get("id"), "code": t.get("code"), "name": t.get("name"), "short": t.get("short_name")} for t in teams.values()], "gameweeks": gw, "players": el}


SOCCER = (("ger.1", "bun", "Bundesliga"), ("esp.1", "lal", "La Liga"), ("ita.1", "sea", "Serie A"), ("usa.1", "mls", "MLS"))     # ESPN's league, its folder on the branch, its name
SUMMARY_BUDGET = 110           # match summaries fetched in one run, over all leagues, while a season's past matches are being filled in
RESULTS_EVERY_H = 6            # how often each team's list of results is read again
T0 = dt.datetime.now(dt.timezone.utc)


def minute(txt):
    """a match clock as a whole minute of normal time: "61'" -> 61, "45'+2'" -> 45, "90'+4'" -> 90"""
    import re
    m = re.match(r"\s*(\d+)", str(txt or ""))
    return min(int(m.group(1)), 120) if m else None


def soccer_match(sm):
    """One finished match from ESPN's summary, small enough to keep a season of: the score, each side's shots, and a line for every
    player who took the field - [team id, player id, name, position, started (1/0), minutes, goals, assists, shots, on target, yellow, red].
    Minutes come from the substitution and red-card marks on each player (normal time only; a starter never taken off has 90)."""
    comp = (((sm.get("header") or {}).get("competitions") or [{}])[0])
    sides = {}
    for c in comp.get("competitors") or []:
        try: sides[c.get("homeAway")] = {"id": str((c.get("team") or {}).get("id") or c.get("id")), "score": int(float(c.get("score")))}
        except Exception: pass
    num = lambda v: (float(v) if str(v).replace(".", "", 1).lstrip("-").isdigit() else None) if v is not None else None
    stats = {}
    for t in (sm.get("boxscore") or {}).get("teams") or []:
        st = {x.get("name"): x.get("displayValue") for x in t.get("statistics") or []}
        stats[str((t.get("team") or {}).get("id"))] = {"sh": num(st.get("totalShots")), "sot": num(st.get("shotsOnTarget")), "pos": num(st.get("possessionPct")), "cor": num(st.get("wonCorners"))}
    players = []
    for r in sm.get("rosters") or []:
        tid = str((r.get("team") or {}).get("id"))
        for p in r.get("roster") or []:
            started, came = bool(p.get("starter")), bool(p.get("subbedIn"))
            if not started and not came: continue
            st = {x.get("name"): x.get("value") for x in p.get("stats") or []}
            on, off = (0 if started else None), 90
            for pl in p.get("plays") or []:
                m = minute((pl.get("clock") or {}).get("displayValue"))
                if m is None: continue
                if pl.get("substitution"):
                    if on is None: on = m                   # a substitute's first mark is his coming on
                    else: off = min(off, max(m, on))        # a starter's, or a substitute's second, is his going off
                elif pl.get("redCard") and on is not None: off = min(off, max(m, on))
            if on is None: on = 89                          # came on with no minute marked: a late change
            g = lambda k: int(st.get(k) or 0)
            at = p.get("athlete") or {}
            players.append([tid, str(at.get("id")), at.get("displayName"), (p.get("position") or {}).get("abbreviation"), int(started), max(1, off - on),
                            g("totalGoals"), g("goalAssists"), g("totalShots"), g("shotsOnTarget"), g("yellowCards"), g("redCards")])
    return {"d": comp.get("date"), "h": (sides.get("home") or {}).get("id"), "a": (sides.get("away") or {}).get("id"), "hs": (sides.get("home") or {}).get("score"),
            "as": (sides.get("away") or {}).get("score"), "st": stats, "p": players}


def soccer_results(sc):
    """a team's finished matches from its schedule: {event id: {d, h, a, hs, as}}"""
    out = {}
    for e in (sc or {}).get("events") or []:
        c = (e.get("competitions") or [{}])[0]
        ty = ((c.get("status") or e.get("status") or {}).get("type") or {})
        side = {}
        for x in c.get("competitors") or []:
            sv = x.get("score"); sv = sv.get("value") if isinstance(sv, dict) else sv
            try: side[x.get("homeAway")] = (str((x.get("team") or {}).get("id") or x.get("id")), int(float(sv)))
            except Exception: pass
        if len(side) == 2 and (ty.get("completed") or ty.get("state") == "post"):
            out[str(e.get("id"))] = {"d": e.get("date"), "h": side["home"][0], "a": side["away"][0], "hs": side["home"][1], "as": side["away"][1]}
    return out


def soccer_league(slug, lg, now, budget, fetch=None):
    """One league: its fixtures and lines (as the Premier League's), line-ups near kickoff, the club list, and season.json - every finished
    match of the season with its player lines, filled in a few summaries a run (newest first) and carried forward. Returns the summaries used."""
    fetch = fetch or get
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    ev = scoreboard(f"soccer/{slug}", lg, 3, 10, now)
    if ev is None: keep(f"{lg}/scoreboard.json", "scoreboard did not answer")
    else: put(f"{lg}/scoreboard.json", {"mirrored": stamp, "events": ev}, len(ev)); META[f"{lg}/scoreboard.json"]["how"] = HOW.get(lg)
    ups = {x["id"]: x for x in ((prev(f"{lg}/lineups.json") or {}).get("matches") or [])}
    got = {}
    for e in ev or []:
        t = when(e["date"])
        if t is None: continue
        mins = (t - now).total_seconds() / 60
        if not (-26 * 60 <= mins <= 100): continue
        old = ups.get(e["id"])
        if old and old.get("posted") and old.get("state") == "post": got[e["id"]] = old; continue
        s = fetch(f"{E}/soccer/{slug}/summary?event={e['id']}")
        if s and s.get("rosters"): got[e["id"]] = epl_lineup(s, e)
        elif old: got[e["id"]] = old
    put(f"{lg}/lineups.json", {"mirrored": stamp, "matches": list(got.values())}, len(got))
    used, said = soccer_season(slug, lg, now, budget, ev, fetch)
    print(f"{lg}: {len(ev or [])} fixtures, {len(got)} line-ups, {said}")
    return used


def soccer_season(slug, lg, now, budget, ev, fetch=None):
    """<lg>/season.json: every finished match of the season with a line for every player who took the field - results from each club's
    schedule (now and then), details from each match's summary (a few a run, newest first), carried forward. `ev` is the league's mirrored
    fixture list, whose finals count too. Returns (summaries used, a line for the log)."""
    fetch = fetch or get
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    A = prev(f"{lg}/season.json") or {}
    if not isinstance(A.get("matches"), dict): A = {"matches": {}, "teams": [], "results_at": None}
    was = json.dumps(A, sort_keys=True)
    last = when(A.get("results_at"))
    if last is None or (now - last).total_seconds() > RESULTS_EVERY_H * 3600 or not A.get("teams"):
        t = fetch(f"{E}/soccer/{slug}/teams")
        teams = [x.get("team") or {} for x in ((((t or {}).get("sports") or [{}])[0].get("leagues") or [{}])[0].get("teams") or [])]
        if teams:
            A["teams"] = [{"id": str(x.get("id")), "abbr": x.get("abbreviation"), "name": x.get("displayName"), "short": x.get("shortDisplayName"), "color": x.get("color"), "alt": x.get("alternateColor")} for x in teams]
            res, answered = {}, 0
            for x in A["teams"]:
                sc = fetch(f"{E}/soccer/{slug}/teams/{x['id']}/schedule")
                if sc is not None: answered += 1; res.update(soccer_results(sc))
            if answered >= max(1, len(A["teams"]) - 2):                     # nearly every club answered: the list of results is good
                for mid, r in res.items():
                    A["matches"].setdefault(mid, {}).update(r)
                A["results_at"] = stamp
    for e in ev or []:                                                      # finals on the scoreboard count too (cup-style rounds the schedules leave out)
        if e.get("state") == "post" and e.get("done"):
            t = {x.get("ha"): x for x in e.get("teams") or []}
            try: A["matches"].setdefault(e["id"], {}).update({"d": e["date"], "h": str(t["home"]["id"]), "a": str(t["away"]["id"]), "hs": int(t["home"]["score"]), "as": int(t["away"]["score"])})
            except Exception: pass
    used = 0
    todo = sorted((mid for mid, m in A["matches"].items() if "p" not in m and m.get("d")), key=lambda mid: str(A["matches"][mid].get("d")), reverse=True)
    for mid in todo:
        if used >= budget or (dt.datetime.now(dt.timezone.utc) - T0).total_seconds() > 330: break
        sm = fetch(f"{E}/soccer/{slug}/summary?event={mid}"); used += 1
        if sm and sm.get("rosters"):
            d = soccer_match(sm)
            if d["p"]: A["matches"][mid].update({k: v for k, v in d.items() if v is not None})
            else: A["matches"][mid]["p"] = []              # a summary with no player lines: not asked for again
    # stamped only when something in it changed: a run that learned nothing writes the same bytes as the last one, so the branch does not
    # gain a megabyte of new file every fifteen minutes (the MLS season alone is that big)
    if json.dumps(A, sort_keys=True) != was or not A.get("season_at"): A["season_at"] = stamp
    have = sum(1 for m in A["matches"].values() if "p" in m)
    put(f"{lg}/season.json", A, len(A["matches"])); META[f"{lg}/season.json"]["with_players"] = have
    return used, f"season {len(A['matches'])} finished matches ({have} with player lines, {len(todo) - min(used, len(todo))} to go), {len(A.get('teams') or [])} clubs"


# ---------------------------------------------------------------------------------------------------------------------------------
# The NBA's five positions (owner 11/23 7:37 AM: "For nba we can have all 5 standard positions SG, PG, PF, SF, C"). ESPN's box scores
# and rosters list only G / F / C this season; its depth charts name who plays PG, SG, SF, PF and C for each team, first choice first.
# nba/depth.json = {"mirrored", "teams": {"LAL": {"PG": [athlete ids, first choice first], "SG": [...], "SF": [...], "PF": [...], "C": [...]}}}
# Thirty requests, so it is read every DEPTH_EVERY_H hours and written again byte for byte in between.
DEPTH_EVERY_H = 6
NBA_TEAMS = range(1, 31)                       # ESPN's team ids


def nba_depth(now, fetch=None):
    fetch = fetch or get
    path = "nba/depth.json"
    old = prev(path) or {}
    last = when(old.get("mirrored"))
    if old.get("teams") and last is not None and 0 <= (now - last).total_seconds() < DEPTH_EVERY_H * 3600:
        keep(path, f"read every {DEPTH_EVERY_H} hours"); META[path]["ok"] = True
        return 0
    teams = {}
    for tid in NBA_TEAMS:
        j = fetch(f"{E}/basketball/nba/teams/{tid}/depthcharts")
        try:
            ab = ((j or {}).get("team") or {}).get("abbreviation")
            chart = {}
            for k, v in ((((j or {}).get("depthchart") or [{}])[0].get("positions")) or {}).items():
                ids = [str(a.get("id")) for a in (v.get("athletes") or []) if isinstance(a, dict) and a.get("id")]
                slot = str(((v.get("position") or {}).get("abbreviation")) or k).upper()
                if ids and slot in ("PG", "SG", "SF", "PF", "C"): chart[slot] = ids
            if ab and len(chart) == 5: teams[str(ab)] = chart
        except Exception:
            pass
    if len(teams) >= 25:                           # nearly every team answered: the list is good
        put(path, {"mirrored": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "teams": teams}, len(teams))
    else:
        keep(path, f"only {len(teams)} of {len(NBA_TEAMS)} depth charts answered")
    return len(NBA_TEAMS)


def run(now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(OUT, exist_ok=True)
    carried = carry()

    # ---- NBA
    ev = scoreboard("basketball/nba", "nba", 1, 1, now)
    if ev is None: keep("nba/scoreboard.json", "scoreboard did not answer")
    else: put("nba/scoreboard.json", {"mirrored": stamp, "events": ev}, len(ev)); META["nba/scoreboard.json"]["how"] = HOW.get("nba")
    j = get(f"{E}/basketball/nba/injuries")
    if not j or "injuries" not in j: keep("nba/injuries.json", "injuries did not answer")
    else:
        x = nba_injuries(j, now); put("nba/injuries.json", x, len(x["injuries"]))
    boxes = 0
    for e in ev or []:
        t = when(e["date"])
        if e["state"] not in ("in", "post") or t is None or (now - t).total_seconds() > 36 * 3600: continue
        path = f"nba/box-{e['id']}.json"
        old = prev(path)
        if old and old.get("done") and old.get("players"):
            keep(path, "final, kept from the last run"); META[path]["ok"] = True; boxes += 1; continue
        s = get(f"{E}/basketball/nba/summary?event={e['id']}")
        if not s or not (s.get("boxscore") or {}).get("players"): keep(path, "summary did not answer"); continue
        put(path, nba_box(s, e), None); boxes += 1
    try: nba_depth(now)
    except Exception as e:
        print(f"nba depth charts: FAILED - {str(e)[:200]}")
        if not os.path.exists(os.path.join(OUT, "nba/depth.json")): keep("nba/depth.json", "the depth-chart step failed")
    print(f"nba: {len(ev or [])} games, {boxes} box scores, injuries {'ok' if META.get('nba/injuries.json', {}).get('ok') else 'MISSING'}, "
          f"depth charts {len((prev('nba/depth.json') or {}).get('teams') or {}) if META.get('nba/depth.json', {}).get('stale') else META.get('nba/depth.json', {}).get('n')} teams"
          f"{' (kept)' if META.get('nba/depth.json', {}).get('stale') else ''}")

    # ---- Premier League
    ev = scoreboard("soccer/eng.1", "epl", 3, 10, now)
    if ev is None: keep("epl/scoreboard.json", "scoreboard did not answer")
    else: put("epl/scoreboard.json", {"mirrored": stamp, "events": ev}, len(ev)); META["epl/scoreboard.json"]["how"] = HOW.get("epl")
    ups = {x["id"]: x for x in ((prev("epl/lineups.json") or {}).get("matches") or [])}
    got = {}
    for e in ev or []:
        t = when(e["date"])
        if t is None: continue
        mins = (t - now).total_seconds() / 60
        if not (-26 * 60 <= mins <= 100): continue
        old = ups.get(e["id"])
        if old and old.get("posted") and old.get("state") == "post": got[e["id"]] = old; continue
        s = get(f"{E}/soccer/eng.1/summary?event={e['id']}")
        if s and s.get("rosters"): got[e["id"]] = epl_lineup(s, e)
        elif old: got[e["id"]] = old
    put("epl/lineups.json", {"mirrored": stamp, "matches": list(got.values())}, len(got))
    j = get(FPL, agent="Mozilla/5.0 (X11; Linux x86_64) BetSweep-feeds")
    if not j or "elements" not in j: keep("epl/fpl.json", "the Fantasy Premier League list did not answer")
    else:
        x = fpl_trim(j, now); put("epl/fpl.json", x, len(x["players"]))
    print(f"epl: {len(ev or [])} matches, {len(got)} line-ups, fpl {'ok' if META.get('epl/fpl.json', {}).get('ok') else 'MISSING'}")
    epl_ev = ev

    # ---- college football (FBS)
    ev = scoreboard("football/college-football", "cfb", 2, 16, now, extra="&groups=80")
    if ev is None: keep("cfb/scoreboard.json", "scoreboard did not answer")
    else: put("cfb/scoreboard.json", {"mirrored": stamp, "events": ev}, len(ev)); META["cfb/scoreboard.json"]["how"] = HOW.get("cfb")
    print(f"cfb: {len(ev or [])} games")

    # ---- the other soccer leagues (owner 11/23 1:10 AM: "get to building Bundesliga, La Liga, Serie A, and MLS"). Each on its own: one
    # league failing keeps its last files and does not stop the next.
    left = SUMMARY_BUDGET
    for slug, lg, name in SOCCER:
        try: left -= soccer_league(slug, lg, now, max(0, left))
        except Exception as e:
            print(f"{lg}: FAILED - {str(e)[:200]}")
            for f in ("scoreboard.json", "lineups.json", "season.json"):
                if not os.path.exists(os.path.join(OUT, lg, f)): keep(f"{lg}/{f}", "the league step failed")
    # The Premier League's season as ESPN has it, for ONE thing: where each player lines up (owner 11/23 7:37 AM: "more specific with
    # positions ... forward/striker, Right wing/Right mid, center mid/center attacking mid, right back"). The Premier League's numbers
    # stay on the public match data set; that set and the fantasy list know only goalkeeper, defender, midfielder, forward.
    try:
        used, said = soccer_season("eng.1", "epl", now, max(0, left), epl_ev)
        left -= used; print(f"epl (ESPN, for positions): {said}")
    except Exception as e:
        print(f"epl season: FAILED - {str(e)[:200]}")
        if not os.path.exists(os.path.join(OUT, "epl", "season.json")): keep("epl/season.json", "the season step failed")

    print(f"grading files carried forward: {carried}")
    json.dump({"mirrored": stamp, "carried": carried, "files": META}, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
    return META


# ---------------------------------------------------------------------------------------------------------------------------------
# On an NBA night the site is rebuilt every hour (owner 11/22 9:32 PM: "On nba nights it should refresh hourly").
# The database timer starts the site's rebuild (reprice.yml) hourly on Sunday, Monday and Thursday but only every three hours on the
# other days, and the timer is the owner's to edit. This job already runs four times an hour, so its run in the second half of an hour
# asks for a rebuild when (a) it is between noon and midnight Central, (b) tonight's board has games, (c) no rebuild has started in the
# last 40 minutes or is waiting or running, and (d) the night is not already graded and rebuilt. On the timer's own hours (c) is false,
# so nothing is started twice; the rebuild itself still publishes only what changed.
REBUILD = "reprice.yml"


def rebuild_due(now, board, record, runs):
    """(True or False, why). runs: the latest runs of the rebuild job, [{"created_at", "status"}], newest first."""
    ct = central(now)
    if not 12 <= ct.hour <= 23: return False, "outside noon to midnight Central"
    if ct.minute < 30: return False, "only this job's run in the second half of the hour asks"
    day = (ct - dt.timedelta(hours=4)).date().isoformat()
    if not board or board.get("day") != day or not board.get("games"): return False, f"no NBA games on the board for {day}"
    ages = [(now - t).total_seconds() / 60 for t in (when(r.get("created_at")) for r in runs or []) if t]
    if any(r.get("status") in ("queued", "in_progress", "waiting", "requested", "pending") for r in runs or []): return False, "a rebuild is waiting or running"
    if any(0 <= a < 40 for a in ages): return False, f"a rebuild started {min(a for a in ages if a >= 0):.0f} minutes ago"
    done = all(g.get("state") == "post" for g in board["games"]) and isinstance(record, dict) and record.get("waiting") == 0
    upd = when((record or {}).get("updated")) if isinstance(record, dict) else None
    last = max((t for t in (when(r.get("created_at")) for r in runs or []) if t), default=None)
    if done and upd and last and last > upd: return False, "every game is final and graded, and the site has been rebuilt since"
    return True, f"NBA night ({len(board['games'])} games on {day}'s board) and no rebuild in the last 40 minutes"


def github(method, path, body=None):
    import urllib.request
    req = urllib.request.Request(f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"], "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "BetSweep-feeds"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def rebuild(now=None, dry=False, force=False):
    now = now or dt.datetime.now(dt.timezone.utc)
    load = lambda f: json.load(open(os.path.join(OUT, f))) if os.path.exists(os.path.join(OUT, f)) else None
    runs = [{"created_at": r.get("created_at"), "status": r.get("status")} for r in (github("GET", f"/actions/workflows/{REBUILD}/runs?per_page=5") or {}).get("workflow_runs") or []]
    due, why = rebuild_due(now, load("nba/board.json"), load("nba/record.json"), runs)
    if (due or force) and not dry:
        github("POST", f"/actions/workflows/{REBUILD}/dispatches", {"ref": "main", "inputs": {"publish": "changed"}})
    print(f"nba rebuild: {'asked for' if (due or force) and not dry else ('would ask for' if due or force else 'not asked for')} - {why}" + (" (forced)" if force and not due else ""))
    return due


def selftest():
    ok = [0, 0]
    def check(c, what): ok[0 if c else 1] += 1; print(("PASS " if c else "FAIL ") + what)
    comp = lambda ab, name, ha, score, rank=None: {"team": {"id": "1", "abbreviation": ab, "displayName": name, "shortDisplayName": name.split()[-1], "color": "000000", "alternateColor": "ffffff"}, "homeAway": ha,
                                                   "score": score, "records": [{"type": "total", "summary": "10-5"}], "curatedRank": {"current": rank or 99}, "linescores": [{"value": 30}, {"value": 28}]}
    e = event({"id": 401, "date": "2026-11-23T00:00Z", "name": "Denver Nuggets at Chicago Bulls", "shortName": "DEN @ CHI", "status": {"period": 2, "displayClock": "4:10", "type": {"state": "in", "completed": False, "shortDetail": "4:10 - 2nd"}},
               "competitions": [{"venue": {"fullName": "United Center"}, "competitors": [comp("CHI", "Chicago Bulls", "home", "58"), comp("DEN", "Denver Nuggets", "away", "61", 4)], "notes": [{"headline": "NBA Cup"}],
                                 "odds": [{"provider": {"name": "DraftKings"}, "details": "DEN -6.5", "spread": -6.5, "overUnder": 231.5, "homeTeamOdds": {"moneyLine": 215}, "awayTeamOdds": {"moneyLine": -265}}], "broadcasts": [{"names": ["NBA TV"]}]}]})
    check(e["id"] == "401" and e["state"] == "in" and e["detail"] == "4:10 - 2nd" and e["venue"] == "United Center" and e["note"] == ["NBA Cup"] and e["tv"] == ["NBA TV"], "an event keeps its id (as text), state, clock, venue, note and TV")
    check([t["abbr"] for t in e["teams"]] == ["CHI", "DEN"] and e["teams"][0]["ha"] == "home" and e["teams"][1]["score"] == "61" and e["teams"][0]["record"] == "10-5" and e["teams"][0]["rank"] is None and e["teams"][1]["rank"] == 4, "teams keep side, score, record; a rank only inside the top 25")
    check(e["odds"] == {"by": "DraftKings", "details": "DEN -6.5", "spread": -6.5, "total": 231.5, "home_ml": 215, "away_ml": -265}, "ESPN's posted line is kept with the book that posted it")
    check(event({"id": 5, "competitions": [{}]})["odds"] is None and event({"id": 5})["teams"] == [], "an event with no line or no teams does not break")
    now = dt.datetime(2026, 11, 22, 22, 0, tzinfo=dt.timezone.utc)
    inj = nba_injuries({"injuries": [{"displayName": "Boston Celtics", "injuries": [{"athlete": {"displayName": "Jayson Tatum"}, "status": "Out", "shortComment": "Achilles", "date": "2026-11-20T10:00Z",
                        "details": {"type": "Achilles", "returnDate": "2027-01-01", "fantasyStatus": {"abbreviation": "OFS"}}}, {"athlete": {}, "status": "Out"}]}]}, now)
    check(inj["injuries"] == [{"team": "Boston Celtics", "name": "Jayson Tatum", "status": "Out", "fs": "OFS", "type": "Achilles", "note": "Achilles", "date": "2026-11-20T10:00Z", "ret": "2027-01-01"}] and inj["mirrored"] == "2026-11-22T22:00:00Z",
          "an injury line keeps team, name, status, fantasy tag, note and dates; a line with no name is dropped")
    box = nba_box({"boxscore": {"players": [{"team": {"abbreviation": "DEN"}, "statistics": [{"labels": ["MIN", "PTS", "REB", "AST", "3PT"], "athletes": [
        {"athlete": {"id": "9", "displayName": "Nikola Jokic", "position": {"abbreviation": "C"}}, "starter": True, "didNotPlay": False, "stats": ["36", "31", "14", "11", "2-5"]},
        {"athlete": {"id": "8", "displayName": "Bench Guy"}, "starter": False, "didNotPlay": True, "reason": "COACH'S DECISION", "stats": []}]}]}]}}, e)
    check(box["players"][0] == {"team": "DEN", "id": "9", "name": "Nikola Jokic", "pos": "C", "starter": True, "dnp": False, "reason": None, "s": {"MIN": "36", "PTS": "31", "REB": "14", "AST": "11", "3PT": "2-5"}}
          and box["players"][1]["dnp"] and box["players"][1]["s"] == {} and box["teams"][1] == {"abbr": "DEN", "score": "61", "ha": "away"}, "a box score keeps each player's line under its labels, and who did not play")
    lu = epl_lineup({"rosters": [{"homeAway": "home", "formation": "4-3-3", "team": {"abbreviation": "ARS", "displayName": "Arsenal"},
                                  "roster": [{"starter": True, "jersey": "7", "athlete": {"id": "1", "displayName": "Bukayo Saka"}, "position": {"abbreviation": "F"}}] * 11 + [{"starter": False, "athlete": {"id": "2", "displayName": "Sub"}, "subbedIn": True}]}]}, e)
    check(lu["posted"] and len(lu["teams"][0]["xi"]) == 11 and lu["teams"][0]["bench"][0]["on"] and lu["teams"][0]["formation"] == "4-3-3", "a line-up splits the eleven from the bench and says when it is posted")
    f = fpl_trim({"teams": [{"id": 1, "code": 3, "name": "Arsenal", "short_name": "ARS"}], "events": [{"id": 12, "is_current": True, "deadline_time": "2026-11-21T11:00Z"}, {"id": 1}],
                  "elements": [{"code": 223340, "id": 17, "web_name": "Saka", "first_name": "Bukayo", "second_name": "Saka", "team": 1, "element_type": 3, "status": "d", "chance_of_playing_next_round": 75, "news": "Knock", "minutes": 900, "starts": 10}]}, now)
    check(f["players"][0]["team"] == "ARS" and f["players"][0]["status"] == "d" and f["players"][0]["next"] == 75 and f["players"][0]["code"] == 223340 and len(f["gameweeks"]) == 1, "the Fantasy Premier League list keeps the stable player code, club, flag, chance and news")
    check(when("2026-11-23T00:00Z") == dt.datetime(2026, 11, 23, tzinfo=dt.timezone.utc) and when("nope") is None and central(now).strftime("%Y%m%d %H") == "20261122 16", "times parse, and 22:00 UTC is 4 PM Central in November")
    T = lambda h, m, d=24: dt.datetime(2026, 11, d, h, m, tzinfo=dt.timezone.utc)                     # Tuesday 11/24 in Central = UTC - 6
    brd = lambda day="2026-11-24", states=("pre", "in"): {"day": day, "games": [{"state": x} for x in states]}
    run = lambda mins_ago, at, status="completed": {"created_at": (at - dt.timedelta(minutes=mins_ago)).strftime("%Y-%m-%dT%H:%M:%SZ"), "status": status}
    n = T(1, 38, 25)                                                                                   # 7:38 PM Central, Tuesday
    check(rebuild_due(n, brd(), {"waiting": 2}, [run(78, n)])[0] and rebuild_due(n, brd(), None, [])[0], "an NBA night at 7:38 PM with the last rebuild 78 minutes ago: this run asks for one")
    r = [rebuild_due(n, brd(), None, [run(18, n)]), rebuild_due(n, brd(), None, [run(3, n, "in_progress")]), rebuild_due(n, brd(), None, [run(55, n, "queued")])]
    check(not any(x[0] for x in r) and "18 minutes ago" in r[0][1], "not when a rebuild started in the last 40 minutes (the timer's own hours), or one is running or waiting")
    r = [rebuild_due(T(1, 12, 25), brd(), None, []), rebuild_due(T(16, 38), brd(), None, []), rebuild_due(T(6, 38, 25), brd(), None, []), rebuild_due(T(18, 38), brd(), None, [])]
    check([x[0] for x in r] == [False, False, False, True], "only the run in the second half of the hour asks, and only from noon to midnight Central (10:38 AM and 12:38 AM do not; 12:38 PM does)")
    r = [rebuild_due(n, brd(day="2026-11-25"), None, []), rebuild_due(n, None, None, []), rebuild_due(n, {"day": "2026-11-24", "games": []}, None, [])]
    check(not any(x[0] for x in r), "not on a day with no NBA games: a board for tomorrow, no board, or an empty one")
    late = T(5, 38, 25)                                                                                # 11:38 PM Central, same NBA day
    rec = {"waiting": 0, "updated": (late - dt.timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    check(rebuild_due(late, brd(states=("post", "post")), rec, [run(77, late)])[0] and not rebuild_due(late, brd(states=("post", "post")), dict(rec, updated=(late - dt.timedelta(minutes=90)).strftime("%Y-%m-%dT%H:%M:%SZ")), [run(77, late)])[0]
          and rebuild_due(late, brd(states=("post", "post")), dict(rec, waiting=1), [run(77, late)])[0],
          "with every game final: one more rebuild after the last grading, then none; a game still waiting for its grade keeps the hourly rebuild")
    import tempfile
    global OUT, PREV
    keep_dirs = (OUT, PREV); d = tempfile.mkdtemp()
    try:
        OUT, PREV = os.path.join(d, "out"), os.path.join(d, "prev")
        for f, txt in (("nba/locks/2026-11-22.json", "L1"), ("nba/locks/2026-11-21.json", "L0"), ("nba/record.json", "R"), ("nba/graded-2026-11-21.json", "G"), ("nba/board.json", "B"), ("nba/box-1.json", "X"), ("epl/fpl.json", "F"),
                       ("epl/locks/2026-11-23.json", "EL"), ("epl/record.json", "ER"), ("epl/graded-gw11.json", "EG"), ("epl/board.json", "EB"), ("epl/scoreboard.json", "ES"),
                       ("mls/locks/2026-11-23.json", "ML"), ("mls/record.json", "MR"), ("mls/graded-gw20261117.json", "MG"), ("mls/board.json", "MB"), ("mls/season.json", "MS"),
                       ("bun/record.json", "BR"), ("lal/locks/2026-11-23.json", "LL"), ("sea/graded-gw20261124.json", "SG"), ("sea/lineups.json", "SU")):
            os.makedirs(os.path.dirname(os.path.join(PREV, f)), exist_ok=True); open(os.path.join(PREV, f), "w").write(txt)
        n = carry()
        got = sorted(os.path.relpath(os.path.join(r, f), OUT) for r, _, fs in os.walk(OUT) for f in fs)
        check(n == 13 and got == ["bun/record.json", "epl/graded-gw11.json", "epl/locks/2026-11-23.json", "epl/record.json", "lal/locks/2026-11-23.json", "mls/graded-gw20261117.json", "mls/locks/2026-11-23.json", "mls/record.json",
                                  "nba/graded-2026-11-21.json", "nba/locks/2026-11-21.json", "nba/locks/2026-11-22.json", "nba/record.json", "sea/graded-gw20261124.json"]
              and open(os.path.join(OUT, "nba/record.json")).read() == "R" and open(os.path.join(OUT, "epl/record.json")).read() == "ER" and open(os.path.join(OUT, "mls/record.json")).read() == "MR",
              "the grading files of every sport and league (locks, record, graded nights, gameweeks and weeks) are carried forward from the last run, and nothing else is - not a board, not a season file")
        shutil.rmtree(PREV); check(carry() == 0, "with no last run there is nothing to carry, and that is not an error")
    finally:
        OUT, PREV = keep_dirs; shutil.rmtree(d, ignore_errors=True)
    # ---- the soccer leagues (11/23): prices, minutes, a match's lines, the season archive
    check([american(x) for x in ("+310", "-145", "EVEN", 250, "o3.5", None, "55", True)] == [310, -145, 100, 250, None, None, None, None], "an American price is read from a string or a number; a total's 'o3.5' and anything under 100 are not prices")
    check(price({"close": {"odds": "-145", "link": {}}, "open": {"odds": "-150"}}) == -145 and price({"open": {"odds": "+120"}}) == 120 and price({"close": {"line": "o3.5", "odds": "-110"}}) == -110
          and price({"close": {"value": "+300"}}) == 300 and price(None) is None and price({"close": {"line": "o2.5"}}) is None,
          "a side's price is its closing one when there is one, else its opening one - whatever the key is called - and a line is never mistaken for a price")
    so = event({"id": 9, "competitions": [{"competitors": [], "odds": [{"provider": {"name": "DraftKings"}, "details": "SVW -145", "overUnder": 3.5, "drawOdds": {"moneyLine": 310},
                 "moneyline": {"home": {"close": {"odds": "-145"}}, "away": {"close": {"odds": "+360"}}, "draw": {"close": {"odds": "+310"}}}, "total": {"over": {"close": {"line": "o3.5", "odds": "+105"}}, "under": {"close": {"line": "u3.5", "odds": "-130"}}}}]}]})["odds"]
    check(so == {"by": "DraftKings", "details": "SVW -145", "spread": None, "total": 3.5, "home_ml": -145, "away_ml": 360, "draw_ml": 310, "over": 105, "under": -130},
          "a soccer line keeps all three prices - home, draw, away - and the over and under on the total")
    check([minute(x) for x in ("61'", "45'+2'", "90'+4'", "", None, "7'")] == [61, 45, 90, None, None, 7], "a match clock reads as a minute of normal time")
    ath = lambda i, n: {"id": str(i), "displayName": n}
    stt = lambda **kw: [{"name": k, "value": float(v)} for k, v in kw.items()]
    sub = lambda m: {"clock": {"displayValue": f"{m}'"}, "substitution": True}
    sm = {"header": {"competitions": [{"date": "2026-11-21T14:30Z", "competitors": [{"homeAway": "home", "score": "1", "team": {"id": "598"}}, {"homeAway": "away", "score": "5", "team": {"id": "11420"}}]}]},
          "boxscore": {"teams": [{"team": {"id": "598"}, "statistics": [{"name": "totalShots", "displayValue": "9"}, {"name": "shotsOnTarget", "displayValue": "3"}, {"name": "possessionPct", "displayValue": "41.5"}]},
                                 {"team": {"id": "11420"}, "statistics": [{"name": "totalShots", "displayValue": "17"}, {"name": "shotsOnTarget", "displayValue": "8"}]}]},
          "rosters": [{"team": {"id": "598"}, "roster": [
              {"starter": True, "athlete": ath(1, "Full Ninety"), "position": {"abbreviation": "F"}, "stats": stt(totalGoals=1, totalShots=4, shotsOnTarget=2)},
              {"starter": True, "subbedOut": True, "athlete": ath(2, "Taken Off"), "position": {"abbreviation": "M"}, "stats": stt(goalAssists=1), "plays": [sub(61)]},
              {"starter": False, "subbedIn": True, "athlete": ath(3, "Came On"), "stats": stt(totalShots=1), "plays": [sub(61)]},
              {"starter": False, "subbedIn": True, "athlete": ath(4, "On And Off"), "stats": [], "plays": [sub(46), sub(80)]},
              {"starter": True, "athlete": ath(5, "Sent Off"), "stats": stt(redCards=1), "plays": [{"clock": {"displayValue": "30'"}, "redCard": True}]},
              {"starter": False, "subbedIn": False, "athlete": ath(6, "Unused"), "stats": []},
              {"starter": False, "subbedIn": True, "athlete": ath(7, "Late"), "stats": [], "plays": [sub("90'+3")]}]}]}
    mm = soccer_match(sm)
    check((mm["h"], mm["a"], mm["hs"], mm["as"], mm["d"]) == ("598", "11420", 1, 5, "2026-11-21T14:30Z") and mm["st"]["598"] == {"sh": 9.0, "sot": 3.0, "pos": 41.5, "cor": None} and mm["st"]["11420"]["sh"] == 17.0,
          "a finished match keeps its date, sides, score and each side's shots")
    check(mm["p"] == [["598", "1", "Full Ninety", "F", 1, 90, 1, 0, 4, 2, 0, 0], ["598", "2", "Taken Off", "M", 1, 61, 0, 1, 0, 0, 0, 0], ["598", "3", "Came On", None, 0, 29, 0, 0, 1, 0, 0, 0],
                      ["598", "4", "On And Off", None, 0, 34, 0, 0, 0, 0, 0, 0], ["598", "5", "Sent Off", None, 1, 30, 0, 0, 0, 0, 0, 1], ["598", "7", "Late", None, 0, 1, 0, 0, 0, 0, 0, 0]],
          "its players: a starter never taken off has 90 minutes, one taken off his minute, a substitute the rest, one sent off stops there, an unused substitute is left out, and nobody has less than a minute")
    sched = lambda rows: {"events": [{"id": i, "date": d, "competitions": [{"status": {"type": {"completed": done}}, "competitors": [{"homeAway": "home", "team": {"id": h}, "score": {"value": float(hs)}},
                                                                                                                              {"homeAway": "away", "team": {"id": a}, "score": {"value": float(as_)}}]}]} for i, d, h, a, hs, as_, done in rows]}
    check(soccer_results(sched([(11, "2026-11-01T14:30Z", "1", "2", 2, 0, True), (12, "2026-11-08T14:30Z", "2", "1", 1, 1, True), (13, "2026-11-28T14:30Z", "1", "3", 0, 0, False)]))
          == {"11": {"d": "2026-11-01T14:30Z", "h": "1", "a": "2", "hs": 2, "as": 0}, "12": {"d": "2026-11-08T14:30Z", "h": "2", "a": "1", "hs": 1, "as": 1}},
          "a club's schedule gives its finished matches only, with who was at home and the score")
    d = tempfile.mkdtemp(); keep_dirs = (OUT, PREV); calls = []
    try:
        OUT, PREV = os.path.join(d, "out"), os.path.join(d, "prev"); os.makedirs(OUT); os.makedirs(os.path.join(PREV, "bun"))
        rows = [(100 + k, f"2026-10-{k + 1:02d}T14:30Z", "1", "2", k, 0, True) for k in range(6)]
        def fake(u):
            calls.append(u)
            if u.endswith("/teams"): return {"sports": [{"leagues": [{"teams": [{"team": {"id": "1", "abbreviation": "AAA", "displayName": "A Club"}}, {"team": {"id": "2", "abbreviation": "BBB", "displayName": "B Club"}}]}]}]}
            if "/schedule" in u: return sched(rows)
            if "summary?event=" in u: return dict(sm, header={"competitions": [{"date": "x", "competitors": []}]})
            return {"events": []}
        globals()["get"], real_get = fake, get
        now = dt.datetime(2026, 11, 23, 8, 0, tzinfo=dt.timezone.utc)
        used = soccer_league("ger.1", "bun", now, 4, fetch=fake)
        A = json.load(open(os.path.join(OUT, "bun", "season.json")))
        withp = sorted(m for m, x in A["matches"].items() if "p" in x)
        check(used == 4 and len(A["matches"]) == 6 and withp == ["102", "103", "104", "105"] and A["matches"]["105"]["hs"] == 5 and len(A["matches"]["105"]["p"]) == 6 and [t["abbr"] for t in A["teams"]] == ["AAA", "BBB"]
              and A["results_at"] == "2026-11-23T08:00:00Z" and os.path.exists(os.path.join(OUT, "bun", "scoreboard.json")) and os.path.exists(os.path.join(OUT, "bun", "lineups.json")),
              "a league's first run: every finished match is listed from the clubs' schedules, and player lines are fetched for the newest ones first, up to the run's budget")
        shutil.rmtree(PREV); shutil.copytree(OUT, PREV); shutil.rmtree(OUT); os.makedirs(OUT); n0 = len(calls)
        used = soccer_league("ger.1", "bun", now + dt.timedelta(minutes=30), 10, fetch=fake)
        A = json.load(open(os.path.join(OUT, "bun", "season.json")))
        check(used == 2 and all("p" in x for x in A["matches"].values()) and not any("/schedule" in u or u.endswith("/teams") for u in calls[n0:]) and A["results_at"] == "2026-11-23T08:00:00Z",
              "the next run carries the season forward, fetches only the matches still missing, and does not read the clubs' schedules again inside six hours")
        full = open(os.path.join(OUT, "bun", "season.json"), "rb").read(); at1 = A["season_at"]
        shutil.rmtree(PREV); shutil.copytree(OUT, PREV); shutil.rmtree(OUT); os.makedirs(OUT)
        used = soccer_league("ger.1", "bun", now + dt.timedelta(minutes=45), 10, fetch=fake)
        check(used == 0 and open(os.path.join(OUT, "bun", "season.json"), "rb").read() == full and at1 == "2026-11-23T08:30:00Z",
              "a run that learns nothing writes the season file byte for byte as it was - same stamp - so the branch does not gain a new copy of it every run")
        shutil.rmtree(PREV); shutil.copytree(OUT, PREV); shutil.rmtree(OUT); os.makedirs(OUT); n0 = len(calls); rows.append((200, "2026-11-22T14:30Z", "2", "1", 3, 3, True))
        used = soccer_league("ger.1", "bun", now + dt.timedelta(hours=7), 10, fetch=fake)
        A = json.load(open(os.path.join(OUT, "bun", "season.json")))
        check(used == 1 and "200" in A["matches"] and "p" in A["matches"]["200"] and len(A["matches"]) == 7 and sum(1 for u in calls[n0:] if "/schedule" in u) == 2 and A["season_at"] == "2026-11-23T15:00:00Z",
              "after six hours the schedules are read again, and a newly finished match is added with its player lines")
        # ---- the Premier League's season from ESPN, for positions alone: the season file and nothing else in that folder
        used, said = soccer_season("eng.1", "epl", now, 3, [{"id": "900", "date": "2026-11-22T15:00Z", "state": "post", "done": True, "teams": [{"ha": "home", "id": "1", "score": "2"}, {"ha": "away", "id": "2", "score": "1"}]}], fetch=fake)
        A = json.load(open(os.path.join(OUT, "epl", "season.json")))
        check(used == 3 and sorted(os.listdir(os.path.join(OUT, "epl"))) == ["season.json"] and "900" in A["matches"] and "p" in A["matches"]["900"] and A["matches"]["900"]["hs"] == 2 and "player lines" in said
              and sum(1 for x in A["matches"].values() if "p" in x) == 3,
              "the Premier League's ESPN season is collected the same way into its own file - a final from the fixture list included - without touching that folder's other files")
        # ---- the NBA's five positions, from ESPN's depth charts
        dcalls = []
        def chart(u, short=False):
            dcalls.append(u); tid = int(u.rsplit("/", 2)[1])
            if short and tid > 10: return None
            slot = lambda ab, ids: {"position": {"abbreviation": ab}, "athletes": [{"id": i, "displayName": f"P{i}"} for i in ids]}
            return {"team": {"abbreviation": f"T{tid:02d}"}, "depthchart": [{"id": "1", "positions": {"pg": slot("PG", [tid * 100 + 1, tid * 100 + 2]), "sg": slot("SG", [tid * 100 + 2, tid * 100 + 3]),
                    "sf": slot("SF", [tid * 100 + 4]), "pf": slot("PF", [tid * 100 + 5, tid * 100 + 4]), "c": slot("C", [tid * 100 + 6])}}]}
        asked = nba_depth(now, fetch=chart); D = json.load(open(os.path.join(OUT, "nba", "depth.json"))); first = open(os.path.join(OUT, "nba", "depth.json"), "rb").read()
        check(asked == 30 and len(dcalls) == 30 and dcalls[0].endswith("/basketball/nba/teams/1/depthcharts") and len(D["teams"]) == 30 and D["teams"]["T13"] == {"PG": ["1301", "1302"], "SG": ["1302", "1303"], "SF": ["1304"], "PF": ["1305", "1304"], "C": ["1306"]}
              and D["mirrored"] == "2026-11-23T08:00:00Z" and META["nba/depth.json"]["ok"] and META["nba/depth.json"]["n"] == 30,
              "NBA depth charts: each team's five positions, PG SG SF PF C, with its players' ids first choice first")
        os.makedirs(os.path.join(PREV, "nba"), exist_ok=True); shutil.copy(os.path.join(OUT, "nba", "depth.json"), os.path.join(PREV, "nba", "depth.json")); os.remove(os.path.join(OUT, "nba", "depth.json")); n0 = len(dcalls)
        asked = nba_depth(now + dt.timedelta(hours=2), fetch=chart)
        check(asked == 0 and len(dcalls) == n0 and open(os.path.join(OUT, "nba", "depth.json"), "rb").read() == first and META["nba/depth.json"]["ok"],
              "inside six hours the depth charts are not asked for again: the file is written byte for byte as it was")
        os.remove(os.path.join(OUT, "nba", "depth.json"))
        asked = nba_depth(now + dt.timedelta(hours=7), fetch=lambda u: chart(u, short=True))
        check(asked == 30 and open(os.path.join(OUT, "nba", "depth.json"), "rb").read() == first and META["nba/depth.json"].get("stale") and "only 10 of 30" in META["nba/depth.json"]["why"],
              "when most teams' charts do not answer, the last good file is kept rather than replaced by a part of the league")
        os.remove(os.path.join(OUT, "nba", "depth.json"))
        asked = nba_depth(now + dt.timedelta(hours=7), fetch=chart)
        check(asked == 30 and json.load(open(os.path.join(OUT, "nba", "depth.json")))["mirrored"] == "2026-11-23T15:00:00Z", "after six hours they are read again")
    finally:
        globals()["get"] = real_get; OUT, PREV = keep_dirs; shutil.rmtree(d, ignore_errors=True)
    print(f"{ok[0]} passed, {ok[1]} failed"); sys.exit(1 if ok[1] else 0)


if __name__ == "__main__":
    if "--selftest" in sys.argv: selftest()
    elif "--rebuild" in sys.argv: rebuild(dry="--dry" in sys.argv, force="--force" in sys.argv)
    else: run()
