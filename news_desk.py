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
 ("OUT",       6, r"\b(injured reserve\)?$|: out\b|ruled out|out for the (season|year)|out indefinitely|placed on (injured reserve|ir)\b|to injured reserve|season[- ]ending|suspended|waived|released|will not play|won'?t play|will miss (the|this|sunday|monday|thursday)|out (for|this) (week|sunday|monday|thursday)|doubtful)"),
 ("PROTOCOL",  5, r"\bconcussion protocol\b"),
 ("QUEST",     4, r"\b(did not practice|didn'?t practice|dnp\b|limited (participant|in practice|on|wednesday|thursday|friday)|stays limited|listed as limited|questionable|game-?time decision|\bgtd\b|missed practice|sat out practice|not practicing|absent from practice|misses (wednesday|thursday|friday|practice))"),
 ("ROLE_DOWN", 4, r"\b(demoted|los(es|t|ing) (his )?(job|role|starting)|benched|third[- ]string|no\. ?3\b|rb3\b|wr3\b|committee|timeshare|fewer snaps|snap (count|share) (dropped|fell|down)|reduced role|backup role|relegated|phased out|healthy scratch)"),
 ("ROLE_UP",   3, r"\b(named (the )?(starter|starting)|will start|to start (sunday|monday|thursday|at|vs|against)|starting (quarterback|qb|running back|rb)\b|lead back|bell ?cow|workhorse|expanded role|bigger role|larger role|first[- ]team|no\. ?1\b|rb1\b|wr1\b|qb1\b|takes over|taking over|promoted|every[- ]down|three[- ]down)"),
 ("RETURN",    2, r"\b(full participant|practic(ed|es|ing) (in )?full(y)?|cleared|activated|designated to return|expected to (play|return|suit up)|back at practice|returns? to practice|trending (toward|in the right direction)|good to go|removed from (the )?injury report|off the injury report|no (injury )?designation)"),
 ("TRADE",     2, r"\b(traded|trade (to|for|with)|acquired|acquires|signs with|signed (by|with)|claimed|finalizing a trade|dealt to|on the move)"),
]
HYPE = r"\b(rankings|start/sit|start or sit|buy low|sell high|sleeper|waiver|fantasy (buzz|managers)|who should|cheat ?sheet|mock)\b"
def bucket(txt):
    t = txt.lower(); hits = [(sev, name) for name, sev, rx in B if re.search(rx, t)]
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
            clauses = [c for c in re.split(r"(?<=[.!?])\s+|,\s*|;\s*|\s+(?:but|while|whereas|after|because|since|following|behind|in place of|with|alongside|and)\s+", blob) if c.strip()]
            mine = [c for c in clauses if re.search(r"\b" + re.escape(name.split(" ")[-1]) + r"\b", c)]
            sent = " ".join(mine) if mine else blob
            sb = bucket(sent) if mine else (b if len(players) == 1 else None)
            if not sb: continue
            if sb in ("OUT", "QUEST") and re.search(r"rest of (sunday|monday|thursday|saturday|the game|today|tonight)|ruled out for the remainder", sent.lower()): continue   # an in-game exit last week, not this week's status
            sev = {"OUT": 6, "PROTOCOL": 5, "QUEST": 4, "ROLE_DOWN": 4, "ROLE_UP": 3, "RETURN": 2, "TRADE": 2}[sb]
            if k in notes and notes[k]["sev"] >= sev: continue
            src = {"espn": "ESPN", "espn-inj": "ESPN team report", "rotowire": "RotoWire", "cbs": "CBS Sports", "yahoo": "Yahoo Sports", "espn-rss": "ESPN", "pft": "PFT", "nfl": "NFL.com"}.get(it.get("src"), it.get("src") or "news"); when = ts.astimezone(dt.timezone(dt.timedelta(hours=-6))).strftime("%a %m/%d %I:%M %p").replace(" 0", " ") if ts else ""
            head = (it.get("title") or "").strip(); body = re.sub(r"\s*Visit RotoWire.*$", "", (it.get("text") or "").strip(), flags=re.S)[:220]
            kind, tag = {"OUT": ("bad", "News: out"), "PROTOCOL": ("watch", "News: concussion protocol"), "QUEST": ("watch", "News: limited / questionable"), "ROLE_DOWN": ("watch", "News: role down"),
                         "ROLE_UP": ("good", "News: role up"), "RETURN": ("info", "News: back / practising"), "TRADE": ("info", "News: trade / signing")}[sb]
            if sb == "OUT" and re.search(r"\bdoubtful\b", sent.lower()) and not re.search(r"ruled out|out for|injured reserve|season[- ]ending", sent.lower()): kind, tag = "watch", "News: doubtful"
            notes[k] = {"player": name, "team": team, "pos": pos, "k": kind, "tag": tag, "sev": sev, "bucket": sb, "ts": ts.isoformat() if ts else None,
                        "txt": f"{head}. {body} ({src}, {when}).".replace("..", ".").replace(" .", "."), "url": it.get("link"), "src": src}
            # proposed availability rows (official status wins; the rebuild appends only when the tab has no row for him)
            cur = AV.get(k)
            if sb == "OUT" and kind == "bad" and cur not in ("OUT", "IR"):
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
    print(f"news desk week {week}: {len(news)} items, {len(notes)} player notes ({', '.join(f'{k} {v}' for k, v in sorted(c.items()))}), {len(rows)} proposed availability rows, trending top {len(trending)}")
    for n in sorted(notes.values(), key=lambda n: -n["sev"]):
        if n["sev"] >= 2: print(f"  [{n['tag']}] {n['player']} ({n['team']} {n['pos']}): {n['txt'][:150]}")
    if rows:
        print("PROPOSED 'AUTO - Weekly Availability' rows (append only if the tab has no row for him this week; an official status always wins):")
        for r in rows: print("  ", r[1], r[2], r[3], "->", r[4] or r[6], "|", r[9][:110])
    if trending: print("trending:", ", ".join(f"{t['player']} {t['n']}" for t in trending[:12]))
if __name__ == "__main__": main(sys.argv[1] if len(sys.argv) > 1 else 9)
