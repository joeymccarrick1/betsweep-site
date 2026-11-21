#!/usr/bin/env python3
"""avail_auto.py - official rule-outs go into 'AUTO - Weekly Availability' without waiting for a session (owner 11/19: "Yes on the hourly job").

Why: the hourly reprice only FLAGS injury news. On Wed 11/18 Woody Marks was ruled out at 2:51 PM and the model still projected him as
the Texans' lead back at 1 AM, because only a model run (Tue / Thu / Sat / Sun) or a session wrote the availability tab.

Runs in the sheet-mirror job, BEFORE the pull (so the mirror that follows already holds the recalculated projections and the next
reprice prices from them). It is deliberately narrow:
  WRITES OUT   only for a player on one of the four projection tabs (exact name + team), whose team's game this week has not kicked off,
               when ESPN's team injury page lists him Injured Reserve / suspended / PUP / NFI, or lists him Out AND the report line itself
               says he is out of the game ("ruled out", "will not play", "won't be available for Sunday's game", "placed on injured
               reserve" ...). ESPN's Out tag alone is not enough (11/18: Jordan Addison was tagged Out off a surgery report with no
               stated absence - that stays a session's call).
  NEVER        touches a row whose reason starts with "OWNER"; never lowers a status a person or a model run wrote; never edits any
               column but Availability (E), Reason (J), Source (K), Last Updated (L); never deletes a row.
  LIFTS        only its own rows (reason starts "AUTO HOURLY:") when ESPN no longer lists him out before kickoff: Questionable / Doubtful
               -> QUESTIONABLE, Active -> blank. The reason keeps what it replaced.
  STOPS        (writes nothing, says why) if the feeds are stale or short, the week is unknown, or one run would change more than
               MAX_CHANGES rows - a broken feed must not empty a slate.
Every run leaves out/in/AVAIL_AUTO.json in the mirror: what it wrote, what it held and why. Needs the service account shared on the
sheet as EDITOR; as Viewer it reads, reports "needs Editor" and changes nothing.
Usage: python3 .github/avail_auto.py            (in the workflow)        python3 .github/avail_auto.py --selftest
"""
import json, os, re, sys, time, base64, datetime as dt, urllib.request, urllib.parse, urllib.error
SHEET = "1Tmt5vp--RhvErt6ZGm6vIje7hcrf-aFXovpRrUjENI8"
TAB = "AUTO - Weekly Availability"
FEEDS = "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/"
MAX_CHANGES = 10; FEED_MAX_AGE_MIN = 90
CT = dt.timezone(dt.timedelta(hours=-6))
TEAMS = {"Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
         "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
         "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV",
         "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN", "New England Patriots": "NE",
         "New Orleans Saints": "NO", "New York Giants": "NYG", "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
         "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS"}
RESERVE = ("injured reserve", "suspen", "physically unable", "non-football", "reserve")
DAYS = r"(thursday|friday|saturday|sunday|monday)"
NOTPRAC = r"(?!'?s? (practice|walk-?through|session))"
RULED = re.compile(r"ruled out|will not play|won'?t play|won'?t be available|will be unavailable|will not be available|"
                   r"\bout for " + DAYS + NOTPRAC + r"|will miss " + DAYS + NOTPRAC + r"|will miss (week \d+|this week'?s? game|at least)|"
                   r"(?<!n't be )(?<!not be )(?<!to be )placed on (the )?(injured reserve|ir\b|reserve)|season[- ]ending|has been suspended", re.I)
IN_GAME = re.compile(r"(rest|remainder) of (the |" + DAYS + r"'?s? )?[^.]{0,40}(game|contest|win|loss)|did(n'?t| not) return|won'?t return|will not return", re.I)

def _ts(s):
    try: return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None
def _ct(t): return t.astimezone(CT).strftime("%a %m/%d %I:%M %p").replace(" 0", " ") if t else "time unknown"

def kickoffs(scoreboard, week):
    """{team abbr: kickoff (aware datetime)} for this week's games"""
    out = {}
    for ev in scoreboard.get("events") or []:
        if int((ev.get("week") or {}).get("number") or -1) != int(week): continue
        t = _ts(ev.get("date"))
        for c in ((ev.get("competitions") or [{}])[0].get("competitors") or []):
            ab = TEAMS.get((c.get("team") or {}).get("displayName") or "")
            if ab and t: out[ab] = t
    return out

def is_out(status, comment, week):
    """does this ESPN line say, itself, that he is out of this week's game?"""
    st = (status or "").strip().lower(); cm = comment or ""
    if st.startswith(RESERVE): return True
    if not st.startswith("out"): return False
    if not RULED.search(cm) or IN_GAME.search(cm): return False
    wk = re.findall(r"\bweek (\d+)\b", cm, re.I)
    if wk and str(week) not in wk and not re.search(DAYS, cm, re.I): return False   # about another week
    return True

def decide(week, avail, proj, injuries, scoreboard, now):
    """-> (changes, notes). changes: [{"row": sheet row (1-based) or None to append, "player", "what", "E", "J", "K", "L", "new": full row for an append}]
    avail: the tab's rows, header first; proj: {name: [(pos, team)]}."""
    ko = kickoffs(scoreboard, week); changes, notes = [], []
    espn = {}
    for tm in injuries.get("injuries") or []:
        ab = TEAMS.get((tm.get("team") or {}).get("displayName") or "")
        for e in tm.get("injuries") or []:
            nm = ((e.get("athlete") or {}).get("displayName") or "").strip()
            if nm and ab: espn[(nm, ab)] = e
    rows = {}
    for i, r in enumerate(avail[1:], start=2):
        r = list(r) + [""] * (13 - len(r))
        if str(r[0]).strip() == str(week) and str(r[1]).strip(): rows[(str(r[1]).strip(), str(r[2]).strip(), str(r[3]).strip())] = (i, r)
    today = now.astimezone(CT).strftime("%Y-%m-%d"); stamp = _ct(now)
    def line(e): return re.sub(r"\s+", " ", (e.get("shortComment") or "").strip())[:300]
    # 1. new rule-outs
    for (nm, ab), e in sorted(espn.items()):
        st = e.get("status") or ""; cm = line(e)
        if not is_out(st, cm, week): continue
        spots = [(p, t) for p, t in proj.get(nm, []) if t == ab]
        if len(spots) != 1: continue                      # not a model player (or the name is not unique on that team): no effect on projections anyway
        pos = spots[0][0]; k = ko.get(ab)
        if not k: continue                                # bye week / no game listed
        if now >= k: continue                             # kicked off
        typ = (e.get("details") or {}).get("type"); head = f"{nm}: {st}" + (f" ({typ})" if typ else "")
        src = f"ESPN team report {_ct(_ts(e.get('date')))}; written by the hourly job {stamp}"
        cur = rows.get((nm, ab, pos))
        if cur:
            i, r = cur; E = str(r[4]).strip().upper(); J = str(r[9]).strip()
            if J.upper().startswith("OWNER"): notes.append(f"held: {nm} ({ab}) - the owner's row stays {E or 'as set'}; ESPN says {st}"); continue
            if E in ("OUT", "IR"): continue
            was = f" | was: {E or 'no status'}" + (f" - {J[:140]}" if J else "")
            changes.append({"row": i, "player": nm, "what": f"{E or 'no status'} -> OUT", "E": "OUT", "J": f"AUTO HOURLY: {head} - {cm}{was}", "K": src, "L": today})
        else:
            changes.append({"row": None, "player": nm, "what": "new row OUT", "E": "OUT", "J": f"AUTO HOURLY: {head} - {cm}", "K": src, "L": today,
                            "new": [int(week), nm, ab, pos, "OUT", "", "", "", "", f"AUTO HOURLY: {head} - {cm}", src, today, ""]})
    # 2. its own rows, when ESPN no longer has him out before kickoff
    for (nm, ab, pos), (i, r) in sorted(rows.items()):
        J = str(r[9]).strip()
        if not J.startswith("AUTO HOURLY:") or str(r[4]).strip().upper() != "OUT": continue
        e = espn.get((nm, ab)); k = ko.get(ab)
        if not e or not k or now >= k: continue           # gone from the feed is not the same as cleared
        st = (e.get("status") or "").strip(); cm = line(e)
        if is_out(st, cm, week) or st.lower().startswith("out"): continue
        newE = "QUESTIONABLE" if st.lower().startswith(("questionable", "doubtful")) else ""
        changes.append({"row": i, "player": nm, "what": f"OUT -> {newE or 'no status'} (ESPN now {st})", "E": newE,
                        "J": f"AUTO HOURLY (lifted {stamp}): ESPN now lists him {st} - {cm} | was OUT: {J[13:160]}", "K": f"ESPN team report {_ct(_ts(e.get('date')))}; lifted by the hourly job {stamp}", "L": today})
    return changes, notes

# ---------------- the sheet ----------------
# ---- STALE SAMPLES (owner 11/21: "I'd like you to update the small sample projections" / "Yes change the hourly job"). The sheet blends
# last season into a thin sample, so a back or pass catcher who is no longer playing keeps a projection (Michael Carter: one game, three
# carries, projected 8.74). Weeks 4-10: players with two games or fewer on the log and no stat line in the team's last 2+ games had a stat
# line 19% of the time and averaged 0.75 PPR points (309 player-weeks). Such a player gets a NEW row with Forced Role "DEPTH / CONTEXT"
# (availability left blank), which zeroes him and shares his work out. Only for a player with no row of any kind this week, whose team
# has not kicked off; never more than STALE_MAX a run. Rows are per week, so nothing needs lifting: next week is judged afresh.
STALE_MAX = 8
def stale(week, avail, gamelog, tabs, scoreboard, now):
    """tabs = {"RB": rows, "WR": rows, "TE": rows} as read (a header row with "Player" somewhere near the top). Returns new-row changes."""
    out = []
    if not gamelog or gamelog[0][:4] != ["Week", "Player", "Team", "Pos"]: return out
    pw, tw = {}, {}
    for r in gamelog[1:]:
        if len(r) < 4 or not str(r[0]).strip().isdigit(): continue
        w = int(r[0])
        if w >= int(week) or r[3] not in ("RB", "WR", "TE"): continue
        pw.setdefault(str(r[1]).strip(), set()).add(w); tw.setdefault(str(r[2]).strip(), set()).add(w)
    if len(tw) < 20: return out                                   # not a real game log
    have = {str(r[1]).strip() for r in avail[1:] if len(r) > 1 and str(r[0]).strip() == str(week)}
    ko = kickoffs(scoreboard, week); today = now.astimezone(CT).strftime("%Y-%m-%d")
    for pos in ("RB", "WR", "TE"):
        rows = tabs.get(pos) or []; hi = next((i for i, r in enumerate(rows[:6]) if r and r[0] == "Player"), None)
        if hi is None: continue
        H = {c: i for i, c in enumerate(rows[hi])}
        if not {"Team", "Weekly Active", "Proj Fantasy Pts"} <= set(H): continue
        for r in rows[hi + 1:]:
            if len(r) <= max(H["Weekly Active"], H["Proj Fantasy Pts"]) or str(r[H["Weekly Active"]]).strip() != "YES": continue
            nm, tm = str(r[0]).strip(), str(r[H["Team"]]).strip(); ws = pw.get(nm)
            try: pj = float(r[H["Proj Fantasy Pts"]] or 0)
            except Exception: pj = 0.0
            if not nm or nm in have or not ws or len(ws) > 2 or pj <= 0: continue
            idle = sum(1 for w in tw.get(tm, ()) if w > max(ws))
            if idle < 2 or tm not in ko or ko[tm] <= now: continue
            why = (f"STALE SAMPLE (auto): {len(ws)} game{'' if len(ws) == 1 else 's'} with a stat line all season (last Week {max(ws)}), none in {tm}'s {idle} games since. "
                   f"Weeks 4-10: such players had a stat line 19% of the time and averaged 0.75 PPR points; the model had him at {pj:g}.")
            out.append({"row": None, "player": nm, "what": "new row DEPTH / CONTEXT (stale sample)", "E": "", "J": why, "K": "Game-log recency rule (hourly job)", "L": today,
                        "new": [int(week), nm, tm, pos, "", "", "DEPTH / CONTEXT", "", "", why, "Game-log recency rule (hourly job)", today, ""]})
    return out[:STALE_MAX]

def token(sa, scope):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    now = int(time.time()); b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
    hdr = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()); clm = b64(json.dumps({"iss": sa["client_email"], "scope": scope, "aud": sa["token_uri"], "iat": now, "exp": now + 900}).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = b64(key.sign(hdr + b"." + clm, padding.PKCS1v15(), hashes.SHA256()))
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": (hdr + b"." + clm + b"." + sig).decode()}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(sa["token_uri"], data=body), timeout=60))["access_token"]
def api(tok, path, body=None, method=None):
    req = urllib.request.Request(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}/{path}", data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, method=method or ("POST" if body is not None else "GET"))
    return json.load(urllib.request.urlopen(req, timeout=60))
def get(tok, ranges):
    q = "&".join("ranges=" + urllib.parse.quote(r, safe="") for r in ranges) + "&valueRenderOption=FORMATTED_VALUE&majorDimension=ROWS"
    return [v.get("values", []) for v in api(tok, "values:batchGet?" + q)["valueRanges"]]
def feed(name): return json.load(urllib.request.urlopen(FEEDS + name, timeout=60))

def main():
    rep = {"ran": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "wrote": [], "held": [], "status": ""}
    def done(status):
        rep["status"] = status; os.makedirs("out/in", exist_ok=True); json.dump(rep, open("out/in/AVAIL_AUTO.json", "w"), indent=1)
        print("availability auto:", status, "|", len(rep["wrote"]), "rows written"); return 0   # never fails the mirror
    try:
        sa_json = os.environ.get("SHEETS_SA_JSON", "").strip()
        if not sa_json: return done("no service account secret")
        tok = token(json.loads(sa_json), "https://www.googleapis.com/auth/spreadsheets")
        inj, sb = feed("injuries.json"), feed("scoreboard.json"); now = dt.datetime.now(dt.timezone.utc)
        mir = _ts(sb.get("mirrored"))
        if not mir or (now - mir).total_seconds() > FEED_MAX_AGE_MIN * 60: return done("stopped: the ESPN feed is stale")
        if len(inj.get("injuries") or []) < 28: return done("stopped: the ESPN injury feed is short")
        st, av, qb, rb, wr, te = get(tok, ["'AUTO - Settings'!A1:B40", f"'{TAB}'!A1:M1000", "'AUTO - QB Projections'!A2:B300", "'AUTO - RB Projections'!A2:B300", "'AUTO - WR Projections'!A2:B300", "'AUTO - TE Projections'!A2:B250"])
        week = next((int(float(r[1])) for r in st if len(r) > 1 and str(r[0]).strip().lower() == "projection week"), None)
        if not week or not av or av[0][:5] != ["Projection Week", "Player", "Team", "Pos", "Availability"]: return done("stopped: week or availability header not as expected")
        rep["week"] = week; proj = {}
        for pos, v in (("QB", qb), ("RB", rb), ("WR", wr), ("TE", te)):
            for r in v:
                if r and str(r[0]).strip(): proj.setdefault(str(r[0]).strip(), []).append((pos, str(r[1]).strip() if len(r) > 1 else ""))
        changes, notes = decide(week, av, proj, inj, sb, now); rep["held"] = notes
        nreal = len(changes)
        try:
            gl, t_rb, t_wr, t_te = get(tok, ["'AUTO - Player Game Log'!A1:D6000", "'AUTO - RB Projections'!A1:BD300", "'AUTO - WR Projections'!A1:BD300", "'AUTO - TE Projections'!A1:BD250"])
            taken = {c["player"] for c in changes}; st_ch = [c for c in stale(week, av, gl, {"RB": t_rb, "WR": t_wr, "TE": t_te}, sb, now) if c["player"] not in taken]
            changes += st_ch; rep["stale"] = [c["player"] for c in st_ch]
        except Exception as e: rep["held"].append("stale-sample check skipped: " + type(e).__name__ + " " + str(e)[:100])
        if not changes:
            # an empty update changes nothing; it only tells us whether the account may write, so "needs Editor" shows before the day it matters
            try: api(tok, "values:batchUpdate", {"valueInputOption": "USER_ENTERED", "data": []}); rep["can_write"] = True
            except urllib.error.HTTPError as e: rep["can_write"] = False if e.code == 403 else None
            return done("nothing to write" + ("" if rep["can_write"] is not False else " (and it could not: needs Editor)"))
        if nreal > MAX_CHANGES: rep["held"].append("would change: " + "; ".join(f"{c['player']} {c['what']}" for c in changes)); return done(f"stopped: {len(changes)} changes in one run is more than {MAX_CHANGES} - left for a session")
        nxt = len(av) + 1; data = []
        for c in changes:
            if c["row"]: data += [{"range": f"'{TAB}'!E{c['row']}", "values": [[c["E"]]]}, {"range": f"'{TAB}'!J{c['row']}:L{c['row']}", "values": [[c["J"], c["K"], c["L"]]]}]
            else: data.append({"range": f"'{TAB}'!A{nxt}:M{nxt}", "values": [c["new"]]}); nxt += 1
        try: api(tok, "values:batchUpdate", {"valueInputOption": "USER_ENTERED", "data": data})
        except urllib.error.HTTPError as e:
            if e.code == 403: rep["held"].append("would write: " + "; ".join(f"{c['player']} {c['what']}" for c in changes)); return done("needs Editor: the service account can read the sheet but not write it")
            raise
        rep["wrote"] = [{"player": c["player"], "what": c["what"], "reason": c["J"][:200]} for c in changes]
        for c in changes: print("  wrote:", c["player"], "-", c["what"])
        time.sleep(40)   # the projection tabs recalculate before the pull that follows
        return done("wrote")
    except Exception as e:
        return done("error: " + type(e).__name__ + " " + str(e)[:160])

def selftest():
    now = dt.datetime(2026, 11, 19, 3, 0, tzinfo=dt.timezone.utc); bad = 0
    sb = {"events": [{"week": {"number": 11}, "date": "2026-11-20T01:15Z", "competitions": [{"competitors": [{"team": {"displayName": "Houston Texans"}}, {"team": {"displayName": "Indianapolis Colts"}}]}]},
                     {"week": {"number": 11}, "date": "2026-11-22T18:00Z", "competitions": [{"competitors": [{"team": {"displayName": "Minnesota Vikings"}}, {"team": {"displayName": "Dallas Cowboys"}}]}]},
                     {"week": {"number": 11}, "date": "2026-11-19T01:00Z", "competitions": [{"competitors": [{"team": {"displayName": "Chicago Bears"}}, {"team": {"displayName": "Detroit Lions"}}]}]}]}
    def E(n, s, c, typ=None): return {"athlete": {"displayName": n}, "status": s, "shortComment": c, "details": {"type": typ}, "date": "2026-11-18T20:51Z"}
    inj = {"injuries": [{"team": {"displayName": "Houston Texans"}, "injuries": [E("Woody Marks", "Out", "Marks (concussion) has been ruled out for Thursday's game against the Colts.", "Concussion"),
                             E("David Montgomery", "Active", "Montgomery (groin) doesn't have an injury designation and is expected to play."), E("British Brooks", "Injured Reserve", "Brooks was placed on injured reserve."),
                             E("Owner Guy", "Out", "Guy has been ruled out for Thursday."), E("Was Auto", "Questionable", "Auto (knee) is listed as questionable after a limited practice."),
                             E("Some Linebacker", "Out", "Linebacker has been ruled out for Thursday.")]},
                        {"team": {"displayName": "Minnesota Vikings"}, "injuries": [E("Jordan Addison", "Out", "Head coach Kevin O'Connell said Wednesday that Addison underwent thumb surgery earlier this week and won't be placed on injured reserve."),
                             E("Quest Guy", "Out", "Guy won't be available for Sunday's game against the Cowboys, a reporter says.")]},
                        {"team": {"displayName": "Dallas Cowboys"}, "injuries": [E("In Game", "Out", "Game was ruled out for the rest of Sunday's game against the Giants with a knee injury.")]},
                        {"team": {"displayName": "Chicago Bears"}, "injuries": [E("Late News", "Out", "News has been ruled out for Thursday.")]},
                        {"team": {"displayName": "Green Bay Packers"}, "injuries": [E("Bye Guy", "Injured Reserve", "Guy was placed on injured reserve.")]}]}
    proj = {"Woody Marks": [("RB", "HOU")], "David Montgomery": [("RB", "HOU")], "British Brooks": [("RB", "HOU")], "Owner Guy": [("WR", "HOU")], "Was Auto": [("TE", "HOU")], "Jordan Addison": [("WR", "MIN")],
            "Quest Guy": [("WR", "MIN")], "In Game": [("RB", "DAL")], "Late News": [("WR", "CHI")], "Bye Guy": [("TE", "GB")]}
    hdr = ["Projection Week", "Player", "Team", "Pos", "Availability", "Role Limit", "Forced Role", "Replacement For", "Manual Opportunity Adj", "Reason / Injury", "Source", "Last Updated", "Practice Participation"]
    av = [hdr, ["10", "Woody Marks", "HOU", "RB", "QUESTIONABLE"], ["11", "British Brooks", "HOU", "RB", "IR", "", "", "", "", "official"],
          ["11", "Owner Guy", "HOU", "WR", "QUESTIONABLE", "", "", "", "", "OWNER 11/18: questionable"], ["11", "Was Auto", "HOU", "TE", "OUT", "", "", "", "", "AUTO HOURLY: Was Auto: Out - ruled out"],
          ["11", "Quest Guy", "MIN", "WR", "QUESTIONABLE", "", "QB1", "", "", "NEWS DESK: limited", "RotoWire", "2026-11-18", "Limited"]]
    ch, notes = decide(11, av, proj, inj, sb, now); by = {c["player"]: c for c in ch}
    for c, what in ((by.get("Woody Marks", {}).get("row", 0) is None and by["Woody Marks"]["new"][:5] == [11, "Woody Marks", "HOU", "RB", "OUT"] and by["Woody Marks"]["J"].startswith("AUTO HOURLY: Woody Marks: Out (Concussion) - Marks (concussion) has been ruled out"), "a ruled-out model player with no row this week gets a new OUT row (last week's row is not his row)"),
                    ("Jordan Addison" not in by, "ESPN's Out tag with no stated absence (surgery report) writes nothing"),
                    ("British Brooks" not in by and "David Montgomery" not in by, "a player already IR / an active player is left alone"),
                    ("Owner Guy" not in by and any("Owner Guy" in n for n in notes), "an OWNER row is never touched, and the run says it held it"),
                    (by.get("Quest Guy", {}).get("row") == 6 and by["Quest Guy"]["E"] == "OUT" and "was: QUESTIONABLE - NEWS DESK: limited" in by["Quest Guy"]["J"] and set(by["Quest Guy"]) == {"row", "player", "what", "E", "J", "K", "L"}, "a questionable row is raised to OUT in place: only E, J, K, L change and the old reason is kept"),
                    (by.get("Was Auto", {}).get("E") == "QUESTIONABLE" and by["Was Auto"]["row"] == 5 and "lifted" in by["Was Auto"]["J"], "its own OUT row is lifted to QUESTIONABLE when ESPN no longer has him out"),
                    ("In Game" not in by, "'ruled out for the rest of Sunday's game' is last week's exit, not a status"),
                    ("Late News" not in by, "a game that has kicked off is left alone"), ("Bye Guy" not in by and "Some Linebacker" not in by, "a team with no game this week and a player on no projection tab write nothing"),
                    (len(ch) == 3, f"three changes in all ({', '.join(sorted(by))})"),
                    (is_out("Out", "He will miss Sunday's game.", 11) and not is_out("Out", "He will miss practice Thursday.", 11) and not is_out("Out", "He will miss Thursday's practice.", 11) and not is_out("Questionable", "He has been ruled out.", 11) and not is_out("Out", "He has been ruled out for Week 12.", 11) and is_out("Suspension", "", 11), "the wording rule: a missed game counts, a missed practice does not; another week does not; a suspension does")):
        print(("ok   " if c else "FAIL ") + what); bad += 0 if c else 1
    # stale samples
    T = sorted(TEAMS.values())[:24]; glog = [["Week", "Player", "Team", "Pos"]]
    for t in T:
        for w in range(1, 11): glog.append([str(w), f"Starter {t}", t, "RB"])
    glog += [["7", "Stale Guy", "HOU", "RB"], ["9", "Fresh Guy", "HOU", "WR"], ["10", "Fresh Guy", "HOU", "WR"], ["2", "Has Row", "HOU", "WR"], ["3", "Kicked Off", "IND", "RB"], ["4", "Not Active", "HOU", "RB"], ["2", "Vet Back", "HOU", "RB"], ["3", "Vet Back", "HOU", "RB"], ["4", "Vet Back", "HOU", "RB"]]
    hdr = ["Player", "Team", "Proj Fantasy Pts", "Weekly Active"]
    tabs = {"RB": [["title"], hdr, ["Stale Guy", "HOU", "8.74", "YES"], ["Kicked Off", "IND", "5", "YES"], ["Not Active", "HOU", "0", "NO"], ["Vet Back", "HOU", "6", "YES"], ["Starter HOU", "HOU", "15", "YES"]],
            "WR": [hdr, ["Fresh Guy", "HOU", "7", "YES"], ["Has Row", "HOU", "4", "YES"], ["Rookie Zero", "HOU", "3", "YES"]], "TE": []}
    av2 = [["Projection Week", "Player", "Team", "Pos", "Availability"], ["11", "Has Row", "HOU", "WR", "QUESTIONABLE"]]
    sb2 = {"events": [{"week": {"number": 11}, "date": "2026-11-22T18:00Z", "competitions": [{"competitors": [{"team": {"displayName": "Houston Texans"}}, {"team": {"displayName": "Tennessee Titans"}}]}]},
                      {"week": {"number": 11}, "date": "2026-11-20T01:15Z", "competitions": [{"competitors": [{"team": {"displayName": "Indianapolis Colts"}}, {"team": {"displayName": "Dallas Cowboys"}}]}]}]}
    sc = stale(11, av2, glog, tabs, sb2, dt.datetime(2026, 11, 21, 18, 0, tzinfo=dt.timezone.utc))
    for c, what in (([x["player"] for x in sc] == ["Stale Guy"], f"stale: only the one-game back idle for 2+ team games gets a row - not a recent player, one with a row already, a team that has played, an inactive player, a three-game veteran or a rookie with no games ({[x['player'] for x in sc]})"),
                    (bool(sc) and sc[0]["new"][:7] == [11, "Stale Guy", "HOU", "RB", "", "", "DEPTH / CONTEXT"] and sc[0]["new"][9].startswith("STALE SAMPLE (auto): 1 game with a stat line all season (last Week 7), none in HOU's 3 games since.") and len(sc[0]["new"]) == 13, "stale: the row is a 13-column Forced Role DEPTH / CONTEXT row with the reason spelled out"),
                    (stale(11, av2, [["Week", "Player", "Team", "Pos"], ["7", "Stale Guy", "HOU", "RB"]], tabs, sb2, dt.datetime(2026, 11, 21, 18, 0, tzinfo=dt.timezone.utc)) == [], "stale: a game log that is not a whole league's is ignored")):
        print(("ok   " if c else "FAIL ") + what); bad += 0 if c else 1
    print("availability auto selftest:", "ok" if not bad else f"{bad} FAILED"); return bad
if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else main())
