#!/usr/bin/env python3
"""news_desk.py - player / team news into the rebuild (owner 11/4: "I wish you'd take news into account when making projections").

Input: the public `feeds` branch file news.json (.github/feeds.py: ESPN NFL news API + RotoWire NFL RSS, every 10 minutes, rolling 7 days)
plus in/proj_*.json (model players), in/avail.json (this week's availability rows). The sandbox cannot reach ESPN or RotoWire; it can reach
GitHub, so the file comes via raw.githubusercontent.com or `git fetch origin feeds` in the site clone.

What it does (nothing here edits the sheet - it proposes, the rebuild session applies per RUNBOOK Step 2c):
  1. matches every item to model players (RotoWire "Name: headline" titles, ESPN athlete tags, full-name mentions in the text)
  2. sorts each item into a bucket by what it SAYS about role / health, most severe wins per player:
       OUT        ruled out, IR, season-ending, suspended, waived, concussion protocol (watch - protocol is not out)
       QUEST      DNP / limited / questionable / doubtful / game-time decision
       ROLE_DOWN  demoted, lost job, benched, committee, fewer snaps, third-string
       ROLE_UP    named starter, lead back, expanded role, first-team, takes over, QB1
       RETURN     full participant, cleared, activated, designated to return, expected to play
       TRADE      traded / acquired / signed / claimed (-> Step 2a team override check)
       (hype - rankings, start/sit, buy-low, sleeper - is ignored on its own)
  3. writes in/ctx_news.json  - one note per player for flags.py: k good/bad/watch/info, tag "News: ...", text = headline + source + time
     writes out/news_rows.json - PROPOSED 'AUTO - Weekly Availability' rows: OUT only for ruled out / IR / season-ending / suspended;
                                 QUESTIONABLE for DNP / limited / doubtful / GTD when the tab has no row for him yet; QB1 forced role for a
                                 named starting QB. Every row carries the headline, source and link. The rebuild appends them (official status wins)
     writes in/trending.json    - mentions per model player in the last 48 h (ESPN + RotoWire) and the top-20 list; flags.py shows "Trending"
                                 as info; out/trending_w<W>.json is kept on the site (data/) for the Tuesday fade test (trending_grade.py)
Usage: python3 news_desk.py <WEEK>   (prints the proposals and a one-line summary for the run log)
"""
import json, os, re, sys, subprocess, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); IN = os.path.join(HERE, "in"); OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
SITE = "/home/claude/betsweep-site"
RAW = "https://raw.githubusercontent.com/joeymccarrick1/betsweep-site/feeds/"

def fetch(name):
    try: return json.loads(subprocess.check_output(["curl", "-fsS", "--max-time", "30", RAW + name], stderr=subprocess.DEVNULL))
    except Exception: pass
    subprocess.run(["git", "-C", SITE, "fetch", "-q", "origin", "feeds"], check=True)
    return json.loads(subprocess.check_output(["git", "-C", SITE, "show", f"FETCH_HEAD:{name}"], stderr=subprocess.DEVNULL))
def nn(x):
    x = re.sub(r"[.'’]", "", str(x)).strip(); x = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", x, flags=re.I); return re.sub(r"\s+", " ", x).lower().strip()
def vals(n):
    p = os.path.join(IN, n)
    if not os.path.exists(p): return []
    d = json.load(open(p)); return d.get("values", d) if isinstance(d, dict) else d
TEAM_OF = {"Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL", "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI", "Cincinnati Bengals": "CIN",
           "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL", "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB", "Houston Texans": "HOU", "Indianapolis Colts": "IND",
           "Jacksonville Jaguars": "JAX", "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC", "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
           "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG", "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT", "San Francisco 49ers": "SF",
           "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB", "Tennessee Titans": "TEN", "Washington Commanders": "WAS"}
NICK = {v: k.split(" ")[-1] for k, v in TEAM_OF.items()}; NICK["LA"] = "Rams"; NICK["LAC"] = "Chargers"; NICK["NYG"] = "Giants"; NICK["NYJ"] = "Jets"
# buckets: (name, severity, regex). Severity decides which note a player gets when several items match.
B = [
 ("OUT",       6, r"\b(injured reserve\)?$|: out\b|ruled out|out for the (season|year)|out indefinitely|placed on (injured reserve|ir)\b|to injured reserve|season[- ]ending|suspended|waived|released|will not play|won'?t play|remains? out|still out|will miss (the|this|sunday|monday|thursday)|out (for|this) (week|sunday|monday|thursday)|doubtful|(needs?|to have|will have|having|had|undergo(es|ing)?|underwent|requires?|set for|scheduled for|headed for|opt(s|ed)? for) ([\w'’\-]+ ){0,3}surgery|(will|to|could|may|might|would|expected to|likely to|set to|going to|slated to) miss (at least |the next |about |up to |around |roughly |a minimum of )?(the next |at least )?(\d+(-\d+| to \d+)?|two|three|four|five|six|seven|eight|several|multiple|a few|a couple( of)?) (more |additional )?(games|weeks|months)|(sidelined|out) (for )?(at least |up to |about |around |roughly |a minimum of )?(\d+(-\d+| to \d+)?|two|three|four|five|six|seven|eight|several|multiple|a few|a couple( of)?) (more |additional )?(games|weeks|months)|(will|to|could|may|might|would|expected to|likely to|set to|going to|slated to) miss (more|extended|significant|some) time|another (week|game) without)"),
 ("PROTOCOL",  5, r"\bconcussion protocol\b"),
 ("QUEST",     4, r"\b(did not practice|didn'?t practice|dnp\b|limited (participant|in practice|on|wednesday|thursday|friday)|stays limited|listed as limited|questionable|game-?time decision|\bgtd\b|missed practice|sat out practice|not practicing|absent from practice|misses (wednesday|thursday|friday|practice))"),
 ("ROLE_DOWN", 4, r"\b(demoted|los(es|t|ing) (his )?(job|role|starting)|benched|third[- ]string|no\. ?3\b|rb3\b|wr3\b|committee|timeshare|fewer snaps|snap (count|share) (dropped|fell|down)|reduced role|backup role|relegated|phased out|healthy scratch)"),
 ("ROLE_UP",   3, r"\b(named (the )?(starter|starting)|will start|to start (sunday|monday|thursday|at|vs|against)|starting (quarterback|qb|running back|rb)\b|lead back|bell ?cow|workhorse|expanded role|bigger role|larger role|first[- ]team|no\. ?1\b|rb1\b|wr1\b|qb1\b|takes over|taking over|promoted|every[- ]down|three[- ]down)"),
 ("RETURN",    2, r"\b(full participant|practic(ed|es|ing) (in )?full(y)?|cleared|activated|designated to return|expected to (play|return|suit up)|back at practice|returns? to practice|trending (toward|in the right direction)|good to go|removed from (the )?injury report|off the injury report|no (injury )?designation)"),
 ("TRADE",     2, r"\b(traded|trade (to|for|with)|acquired|acquires|signs with|signed (by|with)|claimed|finalizing a trade|dealt to|on the move)"),
]
HYPE = r"\b(rankings|start/sit|start or sit|buy low|sell high|sleeper|waiver|fantasy (buzz|managers)|who should|cheat ?sheet|mock)\b"
def tidy(t):
    """audit 11/10: wording that only LOOKS like an absence. The Week 10 desk flagged Pat Bryant OUT ("activated ... off injured reserve"),
    Josh Jacobs OUT ("his attorneys released a detailed statement"), Jaylen Wright OUT ("inactive lists ... released") and Cody White OUT
    (released Wednesday, re-signed Thursday). Coming OFF injured reserve is a return; a statement / list / report being released is not a player."""
    # "isn't expected to play" read as "expected to play" (Mike Evans, "back / practising"); "wasn't activated" read as activated (David Njoku)
    t = re.sub(r"\b(isn'?t|is not|aren'?t|not|unlikely to be|no longer)\s+expected to (play|return|suit up)\b", " will not play ", t)
    t = re.sub(r"\b(wasn'?t|was not|won'?t be|will not be|hasn'?t been|has not been|not)\s+activated\b", " remains out ", t)
    t = re.sub(r"\b(activated|activates|activating|returns?|returned|returning|came|comes|coming|back|designated to return)( [\w.'’\-]+){0,5} (off|from) (of )?(the )?(injured reserve|ir)\b", " activated ", t)
    t = re.sub(r"\b(statements?|inactive lists?|inactives|injury reports?|depth charts?|schedules?|videos?|reports?|rankings|odds|lines?)( [\w.'’\-]+){0,4} (was |were |is |are |has been |have been |get |gets )?released\b", " published ", t)
    t = re.sub(r"\b(details?|information|info|footage|audio|names?|results?|findings|updates?|word|nothing|none|no (details|information|word))( [\w.'’\-]+){0,6} released\b", " published ", t)
    t = re.sub(r"\breleased (a|an|the|their|his|its|new|this)( [\w.'’\-]+){0,3} (statements?|inactives?|lists?|reports?|depth charts?|schedules?|videos?|uniforms?|trailers?|rankings|odds)\b", " published ", t)
    if re.search(r"\bre-?sign", t): t = re.sub(r"\b(released|waived)\b", " ", t)   # cut and brought straight back: he is on the team
    t = re.sub(r"\b(offseason|off-season|last (year|season|spring|summer|winter)'?s?|previous|prior)( [\w'’\-]+){0,3} surgery\b|\bsurgery (last|this past|in the|during the) (year|season|offseason|off-season|spring|summer|winter)\b", " ", t)
    return t
SAFE_CAPS = set("Sunday Monday Tuesday Wednesday Thursday Friday Saturday January February March April May June July August September October November December Week NFL IR ESPN MRI ACL MCL PCL No The He His".split()) \
            | {w for k in TEAM_OF for w in k.split(" ")} | set(TEAM_OF.values()) | {"Rams", "Chargers", "Giants", "Jets"}
def last_of(name):
    p = [x for x in str(name).split(" ") if x and not re.fullmatch(r"(jr|sr|ii|iii|iv|v)\.?", x, flags=re.I)]
    return p[-1] if p else str(name)
def my_clauses(blob, last):
    """the clauses of an item that are about this player. audit 11/10: sentence by sentence (no split after "vs." / "Jr." / an initial), and a
    tail that names nobody else stays with him - "Josh Jacobs to have surgery on fractured finger, out indefinitely" lost "out indefinitely",
    "Kyler Murray out for Monday vs. Bills, week-to-week with hamstring injury" lost "week-to-week" (so Jacobs read as nothing at all)."""
    raw = re.split(r"(?<=[.!?])\s+", blob); sents = []
    for x in raw:
        if sents and re.search(r"(\b(?i:vs|jr|sr|st|no|mr|dr)\.|\b[A-Z]\.)$", sents[-1]): sents[-1] += " " + x
        else: sents.append(x)
    out = []
    for sn in sents:
        prev = False
        for c in [c for c in re.split(r",\s*|;\s*|\s+(?:but|while|whereas|after|because|since|following|behind|in place of|with|alongside|and)\s+", sn) if c.strip()]:
            if re.search(r"\b" + re.escape(last) + r"\b", c): out.append(c); prev = True
            elif prev and not [w for w in re.findall(r"\b[A-Z][A-Za-z]+", c) if w not in SAFE_CAPS]: out.append(c)
            else: prev = False
    return out
def bucket(txt):
    t = tidy(txt.lower()); hits = [(sev, name) for name, sev, rx in B if re.search(rx, t)]
    return max(hits)[1] if hits else None
def parse_ts(s):
    s = str(s or "").strip()
    try: return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception: pass
    m = re.match(r"^\w{3}, (\d{1,2} \w{3} \d{4}) (\d{1,2}:\d{2}(?::\d{2})?) ?(AM|PM)? ?([A-Z]{2,4})?$", s)   # RotoWire: "Wed, 04 Nov 2026 6:15:00 PM PST"
    if m:
        try:
            t = dt.datetime.strptime(m.group(1) + " " + m.group(2) + (" " + m.group(3) if m.group(3) else ""), "%d %b %Y " + ("%I:%M:%S %p" if m.group(3) and m.group(2).count(":") == 2 else "%I:%M %p" if m.group(3) else "%H:%M:%S" if m.group(2).count(":") == 2 else "%H:%M"))
            off = {"PST": -8, "PDT": -7, "EST": -5, "EDT": -4, "CST": -6, "CDT": -5, "UTC": 0, "GMT": 0}.get(m.group(4) or "", -5)
            return t.replace(tzinfo=dt.timezone(dt.timedelta(hours=off)))
        except Exception: pass
    try:
        from email.utils import parsedate_to_datetime
        d = parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception: pass
    return None

def main(week):
    week = int(week); now = dt.datetime.now(dt.timezone.utc)
    news = fetch("news.json").get("items", [])
    # audit 11/10: Yahoo's feed text arrived with HTML entities in it ("Sunday&#39;s"); pages escape on output, so the entity itself showed
    # (home news, dossiers, start/sit). feeds.py now stores plain text; this keeps the desk right even if a feed does it again.
    import html as _html
    for _it in news:
        for _k in ("title", "text"):
            _t = _it.get(_k)
            if isinstance(_t, str) and "&" in _t: _it[_k] = _html.unescape(_html.unescape(_t))
    # ESPN's team injury pages (feeds injuries.json, every 10 min) carry a beat-report line per player - "Allgeier is slated to work as Arizona's
    # No. 1 running back", "Beck will serve as the No. 2 quarterback" - the best role source we have. Each line becomes an item.
    try:
        for tm in fetch("injuries.json").get("injuries", []):
            tname = (tm.get("team") or {}).get("displayName") or ""
            for e in tm.get("injuries") or []:
                nm = (e.get("athlete") or {}).get("displayName"); cm = (e.get("shortComment") or "").strip(); st = e.get("status") or ""
                if not nm or len(cm) < 25: continue
                news.append({"src": "espn-inj", "ts": e.get("date"), "title": f"{nm}: {st}" + (f" ({(e.get('details') or {}).get('type')})" if (e.get('details') or {}).get('type') else ""),
                             "text": cm, "link": f"espn-injuries:{tname}:{nm}:{e.get('date')}", "players": [nm], "teams": [tname]})
    except Exception as e: print("news desk: injuries.json skipped", e)
    # model players
    P = {}   # nn -> (name, team, pos)
    for f, pos in (("proj_qb.json", "QB"), ("proj_rb.json", "RB"), ("proj_wr.json", "WR"), ("proj_te.json", "TE")):
        for r in vals(f)[1:]:
            if r and r[0]: P.setdefault(nn(r[0]), (r[0], r[1] if len(r) > 1 else "", pos))
    by_last = {}
    for k, (name, team, pos) in P.items(): by_last.setdefault(k.split(" ")[-1], []).append(k)
    AV = {}   # this week's availability rows: nn -> status
    for r in vals("avail.json")[1:]:
        if len(r) > 4 and str(r[0]) == str(week): AV[nn(r[1])] = (r[4] or "").strip().upper() or (r[6] or "").strip().upper()
    NICK = {"josh": "joshua", "drew": "andrew", "mike": "michael", "matt": "matthew", "cam": "cameron", "zach": "zachary", "nick": "nicholas", "jake": "jacob", "will": "william",
            "chris": "christopher", "ben": "benjamin", "alex": "alexander", "dan": "daniel", "sam": "samuel", "tim": "timothy", "tony": "anthony", "kenny": "kenneth", "jon": "jonathan"}
    def canon(k):
        parts = k.split(" "); parts[0] = NICK.get(parts[0], parts[0]); return " ".join(parts)
    PC = {}
    for k in P: PC.setdefault(canon(k), k)
    def match_name(raw):
        """a model player for a name in the news: exact, or the same name with a nickname swapped (Josh/Joshua, Drew/Andrew). Never surname-only."""
        k = nn(raw)
        if k in P: return k
        return PC.get(canon(k))
    def who(item):
        """model players an item is about: RotoWire 'Name:' title first, then ESPN athlete tags, then full-name mentions in the text."""
        t = item.get("title") or ""
        m = re.match(r"^([A-Z][\w.'\-]+(?: [A-Z][\w.'\-]+){1,3}):", t)
        if m:
            k = match_name(m.group(1)); return [k] if k else []   # the item is about one named player; not in the model -> not ours
        found = [match_name(a) for a in (item.get("players") or [])]; found = [k for k in found if k]
        if found or item.get("players"): return found
        blob = f"{t} {item.get('text') or ''}"
        for k in P:
            if len(k) > 6 and re.search(r"\b" + re.escape(P[k][0]) + r"\b", blob): found.append(k)
        return found
    # audit 11/10: a weekly status (doubtful, questionable, limited, "won't play in Week 9", "ruled out for Sunday", back at practice) is
    # about ONE game. Items stay in the mirror 7 days, so on a Tuesday rebuild last Sunday morning's "won't play in Week 9" became a
    # "News: out" flag and a proposed OUT row for the NEW week (Kyle Monangai, Cam Skattebo on the Week 10 home page). A weekly status
    # published before the team's most recent kickoff is dropped; lasting news (IR, season-ending, suspended, released, multi-week, surgery)
    # and anything published after that kickoff (in-game and post-game injuries, Monday reports for a Thursday team) stays.
    LASTK = {}
    try:
        import csv, zoneinfo
        _et = zoneinfo.ZoneInfo("America/New_York")
        for r in csv.DictReader(open(os.path.join(IN, "games.csv"))):
            gd = r.get("gameday") or ""
            if len(gd) != 10 or abs((now.date() - dt.date.fromisoformat(gd)).days) > 21: continue
            hh, mm = ((r.get("gametime") or "13:00").split(":") + ["0"])[:2]
            ko = dt.datetime(int(gd[:4]), int(gd[5:7]), int(gd[8:10]), int(hh or 13), int(mm or 0), tzinfo=_et)
            if ko > now: continue
            for t in (r.get("away_team"), r.get("home_team")):
                if t and (t not in LASTK or ko > LASTK[t]): LASTK[t] = ko
    except Exception as e: print("news desk: last kickoffs not read (weekly statuses not expired):", e)
    LASTING = r"injured reserve|\bir\b|season[- ]ending|out for the (season|year)|rest of the season|out indefinitely|indefinitely|suspend|waived|released|surgery|torn|tear\b|fractur|broken|(miss|out|sidelined|without)\W+(\w+\W+){0,4}(\d+(-\d+| to \d+)?|two|three|four|five|six|seven|eight|several|multiple|a few|a couple( of)?)[- ](to[- ]\w+[- ])?(more )?(games|weeks|months)|week[- ]to[- ]week|miss (significant|extended) time|extended absence"
    INGAME = (r"rest of (the |sunday'?s |monday'?s |thursday'?s |saturday'?s |today'?s |tonight'?s )?([\w.'’\-]+ ){0,3}(game|contest|matchup|win|loss|night)|rest of (sunday|monday|thursday|saturday|today|tonight)"
              r"|for the remainder|(questionable|doubtful|probable) to return|(won'?t|will not|not expected to|unlikely to|did not|didn'?t) return|exit(s|ed)? (sunday|monday|thursday|saturday|the game|early|with|in the)"
              r"|left (the|sunday|monday|thursday|saturday)\S* (night'?s? )?(game|contest|matchup)|in the (first|second|third|fourth) quarter|(first|second) half|at halftime|being evaluated|carted off|helped off|locker room")
    stale = 0
    notes = {}; rows = []; mentions = {}; seen_links = set()
    for it in sorted(news, key=lambda x: str(x.get("ts")), reverse=True):
        if it.get("link") in seen_links: continue
        seen_links.add(it.get("link"))
        ts = parse_ts(it.get("ts")); age_h = (now - ts).total_seconds() / 3600 if ts else 999
        if age_h > 6 * 24: continue   # last week's items (the mirror keeps 7 days)
        players = who(it)
        if not players: continue
        blob = f"{it.get('title') or ''}. {it.get('text') or ''}"
        for k in players:
            if age_h <= 48: mentions[k] = mentions.get(k, 0) + 1
        b = bucket(blob)
        if not b and re.search(HYPE, blob.lower()): continue
        if not b: continue
        if len(players) > 3 and it.get("src") == "espn": continue   # roundup / rankings piece naming many players: not a fact about one
        for k in players:
            name, team, pos = P[k]
            # a sentence about THIS player, not a roundup line about someone else
            # the clause about THIS player: "Wilson is in the concussion protocol, but Hall is trending toward a return" are two facts
            mine = my_clauses(blob, last_of(name))
            sent = " ".join(mine) if mine else blob
            sb = bucket(sent) if mine else (b if len(players) == 1 else None)
            if not sb: continue
            if it.get("src") == "espn-inj":   # the title is "Name: <ESPN status> (type)" - the status wins over wording in the comment ("hopeful he will return" on an IR player read as "back / practising")
                st_ = (it.get("title") or "").split(":", 1)[-1].strip().lower()
                if st_.startswith(("injured reserve", "out", "suspend", "physically unable", "non-football", "reserve", "doubtful")): sb = "OUT"
                elif st_.startswith("questionable") and sb not in ("OUT", "PROTOCOL", "QUEST"): sb = "QUEST"
            low = sent.lower(); lk = LASTK.get(team); before = bool(ts and lk and ts < lk)
            if sb == "ROLE_UP" and re.search(r"\b(despite|over|ahead of|instead of|in place of|replac\w+|benching|bench(es|ed)?|from)\s+([\w.'’\-]+\s+){0,3}" + re.escape(last_of(name).lower()), low):
                sb = "ROLE_DOWN"   # "returning to Watson as QB1 despite Sanders' strong fill-in start": the job went to the other man
            head_l = (it.get("title") or "").lower()
            lasting = bool(re.search(LASTING, tidy(low + (" " + head_l if last_of(name).lower() in head_l else "")))) or (it.get("src") == "espn-inj" and (it.get("title") or "").split(":", 1)[-1].strip().lower().startswith(("injured reserve", "suspend", "physically unable", "non-football", "reserve")))
            exit_ = False
            if sb in ("OUT", "QUEST", "PROTOCOL") and re.search(INGAME, low) and not lasting:
                # an in-game exit: not a status for the next game. Before 11/10 these were skipped (two phrasings only) and the rest came out
                # as "News: out" for the new week (Jaylen Waddle "ruled out of the rest of the Panthers game", Rhamondre Stevenson "ruled out
                # of Packers game ... in the third quarter"). From the game just played it is worth a watch flag; an older one is nothing.
                came_back = bool(re.search(r"\breturn(s|ed)\b(?! to practice)", low)) and not re.search(r"(not|n'?t|never|yet to|unlikely to) return", low)
                if before or came_back: continue
                exit_ = True
            elif before and not lasting and sb in ("OUT", "QUEST", "PROTOCOL", "RETURN", "ROLE_UP", "ROLE_DOWN"):
                stale += 1; continue   # a status or a role plan for a game that has been played
            if exit_: sb = "EXIT"
            sev = {"OUT": 6, "PROTOCOL": 5, "QUEST": 4, "ROLE_DOWN": 4, "EXIT": 3, "ROLE_UP": 3, "RETURN": 2, "TRADE": 2}[sb]
            if k in notes and notes[k]["sev"] >= sev: continue
            src = {"espn": "ESPN", "espn-inj": "ESPN team report", "rotowire": "RotoWire", "cbs": "CBS Sports", "yahoo": "Yahoo Sports", "espn-rss": "ESPN", "pft": "PFT", "nfl": "NFL.com"}.get(it.get("src"), it.get("src") or "news"); when = ts.astimezone(dt.timezone(dt.timedelta(hours=-6))).strftime("%a %m/%d %I:%M %p").replace(" 0", " ") if ts else ""
            head = (it.get("title") or "").strip(); body = re.sub(r"\s*Visit RotoWire.*$", "", (it.get("text") or "").strip(), flags=re.S)[:220]
            kind, tag = {"OUT": ("bad", "News: out"), "PROTOCOL": ("watch", "News: concussion protocol"), "QUEST": ("watch", "News: limited / questionable"), "ROLE_DOWN": ("watch", "News: role down"), "EXIT": ("watch", "News: left last game"),
                         "ROLE_UP": ("good", "News: role up"), "RETURN": ("info", "News: back / practising"), "TRADE": ("info", "News: trade / signing")}[sb]
            if sb == "OUT" and re.search(r"\bdoubtful\b", sent.lower()) and not re.search(r"ruled out|out for|injured reserve|season[- ]ending", sent.lower()): kind, tag = "watch", "News: doubtful"
            # "out for Monday vs. Bills, week-to-week" from before that game: he missed it, and this week is open - a watch flag and a
            # QUESTIONABLE proposal, not an OUT (audit 11/10: Kyler Murray was proposed OUT for Week 10 off the Week 9 headline)
            w2w = sb == "OUT" and before and bool(re.search(r"week[- ]to[- ]week|day[- ]to[- ]day", tidy(low + " " + head_l))) and not re.search(r"injured reserve|\bir\b|season[- ]ending|out for the (season|year)|indefinitely|surgery|suspend|waived|released", tidy(low + " " + head_l))
            if w2w: kind, tag = "watch", "News: week-to-week"
            notes[k] = {"player": name, "team": team, "pos": pos, "k": kind, "tag": tag, "sev": sev, "bucket": sb, "ts": ts.isoformat() if ts else None,
                        "txt": f"{head}. {body} ({src}, {when}).".replace("..", ".").replace(" .", "."), "url": it.get("link"), "src": src}
            # proposed availability rows (official status wins; the rebuild appends only when the tab has no row for him)
            cur = AV.get(k)
            if w2w and not cur:
                rows.append([str(week), name, team, pos, "QUESTIONABLE", "", "", "", "", f"NEWS DESK: {head} - {body}", f"{src} {when}: {it.get('link')}", now.strftime("%Y-%m-%d"), ""])
            elif sb == "OUT" and kind == "bad" and cur not in ("OUT", "IR"):
                rows.append([str(week), name, team, pos, "OUT", "", "", "", "", f"NEWS DESK: {head} - {body}", f"{src} {when}: {it.get('link')}", now.strftime("%Y-%m-%d"), ""])
            elif sb in ("QUEST", "PROTOCOL") and not cur and re.search(r"did not|didn'?t|dnp\b|non-participant|won'?t (practice|take part)|not expected to practice|missed|sat out|absent|questionable|doubtful|game-?time|protocol", sent.lower()):
                rows.append([str(week), name, team, pos, "QUESTIONABLE", "", "", "", "", f"NEWS DESK: {head} - {body}", f"{src} {when}: {it.get('link')}", now.strftime("%Y-%m-%d"), "DNP" if re.search(r"did not|didn'?t|dnp|missed|sat out|not practicing|absent", sent.lower()) else ("Limited" if "limited" in sent.lower() else "")])
            elif sb == "ROLE_UP" and pos == "QB" and re.search(r"named|will start|starting quarterback|starting qb|qb1", sent.lower()) and cur not in ("QB1",):
                rows.append([str(week), name, team, "QB", "", "", "QB1", "", "", f"NEWS DESK: {head} - {body}", f"{src} {when}: {it.get('link')}", now.strftime("%Y-%m-%d"), ""])
    # trending: mentions in the last 48 h
    top = sorted(mentions.items(), key=lambda kv: -kv[1])[:20]
    trending = [{"player": P[k][0], "team": P[k][1], "pos": P[k][2], "n": n} for k, n in top if n >= 2]
    for k, n in top:
        if n >= 3 and k not in notes: notes[k] = {"player": P[k][0], "team": P[k][1], "pos": P[k][2], "k": "info", "tag": "Trending", "sev": 0, "bucket": "TREND", "ts": None,
                                                   "txt": f"Named in {n} news items in the last 48 hours (ESPN + RotoWire). Heavily covered players get bet, and bet players get shaded by the book - a reason to check the price, not a reason to fade on its own (graded weekly).", "url": None, "src": "news"}
    json.dump({"week": week, "built": now.isoformat(), "players": list(notes.values()), "games": {}}, open(os.path.join(IN, "ctx_news.json"), "w"), indent=1)
    json.dump(rows, open(os.path.join(OUT, "news_rows.json"), "w"), indent=1)
    json.dump({"week": week, "built": now.isoformat(), "top": trending, "all": {P[k][0]: n for k, n in mentions.items()}}, open(os.path.join(IN, "trending.json"), "w"), indent=1)
    json.dump({"week": week, "built": now.isoformat(), "top": trending}, open(os.path.join(OUT, f"trending_w{week}.json"), "w"))
    from collections import Counter
    c = Counter(n["bucket"] for n in notes.values())
    if stale: print(f"news desk: {stale} weekly statuses dropped (published before the team's last kickoff - about a game already played)")
    print(f"news desk week {week}: {len(news)} items, {len(notes)} player notes ({', '.join(f'{k} {v}' for k, v in sorted(c.items()))}), {len(rows)} proposed availability rows, trending top {len(trending)}")
    for n in sorted(notes.values(), key=lambda n: -n["sev"]):
        if n["sev"] >= 2: print(f"  [{n['tag']}] {n['player']} ({n['team']} {n['pos']}): {n['txt'][:150]}")
    if rows:
        print("PROPOSED 'AUTO - Weekly Availability' rows (append only if the tab has no row for him this week; an official status always wins):")
        for r in rows: print("  ", r[1], r[2], r[3], "->", r[4] or r[6], "|", r[9][:110])
    if trending: print("trending:", ", ".join(f"{t['player']} {t['n']}" for t in trending[:12]))
def selftest():
    """python3 news_desk.py --selftest : the wording cases that went wrong on the Week 10 desk (audit 11/10). Run after editing B / tidy / my_clauses."""
    cases = [   # (player, text, expected bucket for his clauses; None = no note)
     ("Pat Bryant", "Broncos vs. Panthers gameday inactives for Week 9. The Denver Broncos activated wide receiver Pat Bryant off injured reserve.", "RETURN"),
     ("Josh Jacobs", "Josh Jacobs calls more allegations surfacing 'an attack on me'. Jacobs' attorneys released a detailed statement pushing back on the claims.", None),
     ("Jaylen Wright", "Dolphins without Jaylen Wright as inactive lists for Lions game released.", None),
     ("Cody White", "Raiders re-sign WR Cody White, waive TE Carter Runyon. The Raiders released wide receiver Cody White on Wednesday, but his absence from the team was a short one.", None),
     ("Calvin Ridley", "Titans WR Calvin Ridley involved in incident at Nashville airport, details of which have not been released.", None),
     ("Josh Jacobs", "Josh Jacobs to have surgery on fractured finger, out indefinitely.", "OUT"),
     ("Josh Jacobs", "Packers RB Josh Jacobs reportedly needs surgery on fractured finger, out up to 3 weeks.", "OUT"),
     ("Rhamondre Stevenson", "Patriots running back Rhamondre Stevenson will miss multiple weeks with a knee issue.", "OUT"),
     ("Breece Hall", "Breece Hall proclaimed himself ready to play Sunday after missing five games with a quad injury.", None),
     ("Mike Evans", "Mike Evans: Likely to sit Sunday per GM. Evans (Achilles) isn't expected to play Sunday against the Raiders.", "OUT"),
     ("David Njoku", "Njoku (fibula) wasn't activated from IR-designated to return ahead of Sunday's game.", "OUT"),
     ("Kyler Murray", "Kyler Murray out for Monday vs. Bills, week-to-week with hamstring injury.", "OUT"),
     ("Garrett Wilson", "Jets wide receiver Garrett Wilson is in the concussion protocol, but Breece Hall is trending toward a return.", "PROTOCOL"),
     ("Breece Hall", "Jets wide receiver Garrett Wilson is in the concussion protocol, but Breece Hall is trending toward a return.", "RETURN"),
     ("Dyami Brown", "Dyami Brown placed on injured reserve. Dyami Brown to miss at least four games", "OUT"),
     ("Luther Burden III", "Luther Burden III: Questionable (Concussion). Burden has a concussion, head coach Ben Johnson revealed.", "QUEST"),
    ]
    bad = 0
    for name, text, want in cases:
        mine = my_clauses(text, last_of(name)); got = bucket(" ".join(mine)) if mine else None
        if got != want: bad += 1; print(f"FAIL {name}: got {got}, want {want} | {text[:90]}")
    print(f"news desk selftest: {len(cases) - bad}/{len(cases)} ok"); return bad
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--selftest": sys.exit(1 if selftest() else 0)
    main(sys.argv[1] if len(sys.argv) > 1 else 9)
